"""ITEM-02 (ROADMAP dba-ai-nl2sql): 샘플쿼리 few-shot 저장소 — 등록·검색·주입·신선도.

NL↔SQL 샘플을 agent_kb(PG)에 ds-scoped(scope_key) + 임베딩(titan-embed, vector(1536))으로
저장하고, 사용자 질문 임베딩으로 **approved∧active** 샘플을 cosine top-K(weight 가중) 검색해
_build_knowledge_context 가 `## EXAMPLE QUERIES` 로 주입한다.

가드: ① ds-scope(scope_key=활성 datasource + 'common') ② approved∧active 만 검색
③ **injection-only**(샘플 sql 은 프롬프트 예시일 뿐 직접 실행 절대 금지 — 호출측 datamark+펜스)
④ 신선도: validate_sample_sql 가 깨진 샘플(스키마 drift)을 stale 표기.

성장 루프(피드백→승급)는 sample_feedback.py(ITEM-03). 본 모듈은 저장소+검색+주입+신선도.
"""
from __future__ import annotations

import logging

from modules.utils import _normalize_scope_key, _scope_candidates

_log = logging.getLogger("sample_queries")

_DEFAULT_TOP_K = 5
_INJECT_SQL_CAP = 800   # 주입 시 샘플 SQL 길이 cap(프롬프트 비대 방지)


def _ro_conn(conn):
    if conn is not None:
        return conn, False
    from modules.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


def _embed(text):
    """nl_question/질문 임베딩(titan-embed). 미설정/실패 → None(graceful)."""
    from modules.kb_retrieval import _embed_query_vector
    return _embed_query_vector(text)


# ── 등록(RW) — 큐레이션 게이트 통과분만 approved=True ──────────────────────────
def register_sample(conn, scope_key, nl_question, sql, *, domain="", weight=100,
                    source_type="manual", approved=False, created_by=None,
                    embedding=None) -> None:
    """샘플 upsert. embedding 미제공 시 nl_question 을 임베딩(titan-embed). 단위테스트는
    embedding=[] 등 명시로 Bedrock 우회."""
    vec = embedding
    if vec is None:
        vec = _embed(nl_question)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sample_queries "
            "(scope_key, nl_question, sql, domain, weight, embedding, source_type, approved, created_by) "
            # embedding 은 %s::vector 캐스트 필수 — psycopg3 가 list 를 float8[] 로 보내므로 cast 없으면
            # vector 컬럼과 타입 불일치(REV BLOCKER). search 의 %(qvec)s::vector·kb_backend 선례 정합.
            "VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s) "
            "ON CONFLICT (scope_key, nl_question) DO UPDATE SET "
            "sql = EXCLUDED.sql, domain = EXCLUDED.domain, weight = EXCLUDED.weight, "
            "embedding = EXCLUDED.embedding, source_type = EXCLUDED.source_type, "
            "approved = EXCLUDED.approved, status = 'active', updated_at = now()",
            (_normalize_scope_key(scope_key), str(nl_question).strip(), str(sql).strip(),
             str(domain or "").strip(), int(weight), vec, str(source_type or "manual"),
             bool(approved), created_by),
        )
    finally:
        cur.close()


def set_sample_status(conn, sample_id, status) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE sample_queries SET status = %s, last_validated_at = now() WHERE id = %s",
            (str(status), int(sample_id)),
        )
    finally:
        cur.close()


# ── 검색(RO) — approved∧active, ds-scoped, weight 가중 cosine top-K ──────────
def search_samples(conn, query_vector, scope_key, top_k=_DEFAULT_TOP_K):
    """approved∧active∧ds-scoped 샘플을 (유사도 × weight/100) 내림차순 top-K. 임베딩 없으면 []."""
    if not query_vector:
        return []
    scopes = _scope_candidates(scope_key)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT nl_question, sql, domain, weight, "
            "(1 - (embedding <=> %(qvec)s::vector)) AS sim "
            "FROM sample_queries "
            "WHERE scope_key = ANY(%(scopes)s) AND approved = true AND status = 'active' "
            "AND embedding IS NOT NULL "
            "ORDER BY (1 - (embedding <=> %(qvec)s::vector)) * (weight / 100.0) DESC "
            "LIMIT %(k)s",
            {"qvec": list(query_vector), "scopes": scopes, "k": int(top_k)},
        )
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def load_example_queries_context(user_message, scope_key=None, conn=None, top_k=_DEFAULT_TOP_K) -> str:
    """질문 임베딩 → approved∧active∧ds-scoped 유사 샘플 top-K → 프롬프트 본문 조립.
    미매칭/미가용/임베딩실패 → "". scope 미지정 시 활성 datasource(get_active_datasource)."""
    if not str(user_message or "").strip():
        return ""
    if scope_key is None:
        from modules import config as _cfg
        scope_key = _cfg.get_active_datasource()
    qvec = _embed(user_message)
    if not qvec:
        return ""
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)
        if c is None:
            return ""
        rows = search_samples(c, qvec, scope_key, top_k=top_k)
    except Exception as exc:
        _log.debug("sample_search_failed err=%r", exc)
        return ""
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    if not rows:
        return ""
    lines = []
    for nlq, sql, _domain, _weight, _sim in rows:
        sql_s = str(sql or "").strip()
        if len(sql_s) > _INJECT_SQL_CAP:
            sql_s = sql_s[:_INJECT_SQL_CAP] + " …"
        lines.append(f"-- Q: {str(nlq or '').strip()}\n{sql_s}")
    return "\n\n".join(lines)


# ── 신선도(staleness) — 깨진 샘플 감지 hook (주기 job 은 follow-up) ──────────
_FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create",
              "truncate", "grant", "revoke")


def _is_readonly(sql: str) -> bool:
    import re
    s = (sql or "").strip().rstrip(";").lower()
    if not (s.startswith("select") or s.startswith("with")):
        return False
    for kw in _FORBIDDEN:
        if re.search(rf"(^|[\s(;]){kw}([\s(]|$)", s):
            return False
    return True


def validate_sample_sql(sql, explain_fn=None) -> tuple:
    """샘플 SQL 신선도 판정 → (status, reason).
    - read-only 아님 → ('retired', 'not-readonly') (애초에 잘못 등록)
    - explain_fn(sql) 제공 + 예외 → ('stale', '<err>') (스키마 drift 등 깨짐)
    - 그 외 → ('active', None)
    explain_fn: 샘플 SQL 을 datasource 에 EXPLAIN 하는 콜러블(성공 None, 실패 raise). 주기 job 이 주입."""
    if not _is_readonly(sql):
        return ("retired", "not-readonly")
    if explain_fn is not None:
        try:
            explain_fn(sql)
        except Exception as e:
            return ("stale", repr(e)[:160])
    return ("active", None)
