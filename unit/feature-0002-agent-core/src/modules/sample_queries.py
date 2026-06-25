"""ITEM-02 (ROADMAP dba-ai-nl2sql): 샘플쿼리 few-shot 저장소 — 등록·검색·주입·신선도.

NL↔SQL 샘플을 agent_kb(PG)에 ds-scoped(scope_key) + 임베딩(titan-embed, vector(1024))으로
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
    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


def _embed(text, timeout_sec=None):
    """nl_question/질문 임베딩(titan-embed). 미설정/실패 → None(graceful).
    CHG-20260625: timeout_sec 전달 — 상호작용(질의) 경로는 fast-fail timeout 을 쓴다."""
    from modules.kb_retrieval import _embed_query_vector
    return _embed_query_vector(text, timeout_sec=timeout_sec)


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


# ── 관리(RW) — 샘플 거버넌스 콘솔 CRUD (ITEM-11 Phase 2) ───────────────────────
# admin 콘솔(feature-0003 /api/admin/metadata/samples)이 호출. **단일 scope_key 만** 다룬다
# (검색의 common 캐스케이드 없음) — 편집/삭제는 정확히 그 scope 행에만 적용돼야 ds 격리가
# 안 깨진다. id(PK)+scope_key 가드로 cross-scope 오작용 차단. POST(생성) 정본은 ITEM-03 피드백
# 검수 승급 경로(promote_feedback) — 여기는 수정/삭제/목록만. register_sample/set_sample_status/
# search_samples 는 무변경. 호출측(web)이 RBAC(kb.sample.curate)·audit·commit·conn 수명을 책임진다.
_SAMPLE_ADMIN_LIMIT = 1000
_EMBED_SENTINEL = object()  # update_sample 의 embedding 미지정(=touch 안 함) 구분용


def list_samples_admin(conn, scope_key, limit=_SAMPLE_ADMIN_LIMIT):
    """admin 목록 — 단일 scope 의 샘플 행(id 포함). 최신 갱신 우선. 검색과 달리 캐스케이드 없음.

    embedding 본문은 제외(직렬화 부하/불필요). status(신선도)·approved(큐레이션)·weight(가중) 노출.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, nl_question, sql, domain, weight, approved, status, "
            "source_type, created_at, updated_at FROM sample_queries WHERE scope_key = %s "
            "ORDER BY updated_at DESC, id DESC LIMIT %s",
            (_normalize_scope_key(scope_key), int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def update_sample(conn, sample_id, scope_key, *, nl_question=None, sql=None, domain=None,
                  weight=None, approved=None, embedding=_EMBED_SENTINEL) -> int:
    """샘플 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 호출측 404).

    부분 수정 — None 인 필드는 미수정. nl_question 변경 시에만 embedding 인자를 반영한다
    (하이브리드 C: 호출측이 nl 변경 시 동기 임베딩 시도, 실패면 None 전달 → status='stale').
      · embedding=벡터  → embedding 갱신(+status='active')
      · embedding=None  → embedding 무효화(NULL) + status='stale' (재임베딩 대기)
      · embedding 미지정(_EMBED_SENTINEL) → embedding/status touch 안 함(nl 미변경 경로)
    nl_question 변경이 기존 (scope,nl) UNIQUE 와 충돌하면 호출측이 IntegrityError 를 409 로 변환.
    """
    sets: list[str] = []
    params: list = []
    if nl_question is not None:
        sets.append("nl_question = %s")
        params.append(str(nl_question).strip())
    if sql is not None:
        sets.append("sql = %s")
        params.append(str(sql).strip())
    if domain is not None:
        sets.append("domain = %s")
        params.append(str(domain or "").strip())
    if weight is not None:
        sets.append("weight = %s")
        params.append(int(weight))
    if approved is not None:
        sets.append("approved = %s")
        params.append(bool(approved))
    if embedding is not _EMBED_SENTINEL:
        if embedding:
            # %s::vector 캐스트 필수(register_sample 선례) — psycopg3 list→float8[] 불일치 방지.
            sets.append("embedding = %s::vector")
            sets.append("status = 'active'")
            params.append(list(embedding))
        else:
            # 임베딩 실패/무효화 → 검색 대상에서 제외(stale). NULL embedding 은 search WHERE 가 거른다.
            sets.append("embedding = NULL")
            sets.append("status = 'stale'")
    if not sets:
        return 0  # 변경 필드 없음 — no-op(호출측은 404 아님; 입력검증에서 차단 권장)
    sets.append("updated_at = now()")
    params.extend([int(sample_id), _normalize_scope_key(scope_key)])
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE sample_queries SET " + ", ".join(sets)
            + " WHERE id = %s AND scope_key = %s",
            tuple(params),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def delete_sample(conn, sample_id, scope_key) -> int:
    """샘플 삭제(by id, scope 가드, 멱등). 반영 행 수 반환(0=이미 없음 → 멱등 성공)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM sample_queries WHERE id = %s AND scope_key = %s",
            (int(sample_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
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


_QVEC_UNSET = object()  # "벡터 미제공 → 직접 임베딩" 과 "None 전달 → 임베딩 skip" 구분 sentinel


def load_example_queries_context(user_message, scope_key=None, conn=None, top_k=_DEFAULT_TOP_K,
                                 query_vector=_QVEC_UNSET) -> str:
    """질문 임베딩 → approved∧active∧ds-scoped 유사 샘플 top-K → 프롬프트 본문 조립.
    미매칭/미가용/임베딩실패 → "". scope 미지정 시 활성 datasource(get_active_datasource).

    CHG-20260625: query_vector 를 넘기면 그 벡터를 재사용한다(_build_knowledge_context 가
    질의 임베딩을 1회만 계산해 few-shot·account recall 이 공유 → 준비 단계 중복 임베딩
    제거). 미지정(sentinel) 시에만 직접 임베딩하되, 상호작용 fast-fail timeout 을 쓴다."""
    if not str(user_message or "").strip():
        return ""
    if scope_key is None:
        from shared import config as _cfg
        scope_key = _cfg.get_active_datasource()
    if query_vector is _QVEC_UNSET:
        from shared.config import AGENT_KB_QUERY_EMBED_TIMEOUT_SEC
        qvec = _embed(user_message, timeout_sec=AGENT_KB_QUERY_EMBED_TIMEOUT_SEC)
    else:
        qvec = query_vector
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
