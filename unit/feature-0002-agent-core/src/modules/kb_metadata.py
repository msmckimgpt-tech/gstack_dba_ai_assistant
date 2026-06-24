"""ITEM-11 Phase 2 (ROADMAP dba-ai-nl2sql): 테이블/컬럼 설명 사전 (table_descriptions / column_descriptions).

사람이 작성한 테이블·컬럼 의미 설명을 agent_kb(Postgres)에 ds-scoped(scope_key, fact_entries
동일 컨벤션)로 저장하고 두 경로로 주입한다(kb_glossary.py 동형):
  (B) load_table_column_descriptions — _build_knowledge_context 가 질문 매칭 행을 grounding
      섹션에 datamark 주입(주입 펜스는 호출측).
  (A) load_column_descriptions_for_table — describe_table 가 native COLUMN_COMMENT 가 빈
      컬럼을 KB 설명으로 오버레이(MSSQL 빈 comment gap, dialects.describe_columns row[6]='' 해소).

ds-scope: scope_key = **활성 datasource**( cfg.get_active_datasource() ) + 'common' 캐스케이드.
타 datasource 의 설명은 혼입되지 않는다. (CURRENT_FACT_SCOPE_KEY 는 멀티DS 에서 갱신되지
않으므로 쓰지 않는다 — kb_glossary.py:209 BLOCKER.) 저장=RW, 읽기=RO. PG 미가용/미매칭이면 ""(무영향).

한계(launch 볼륨 전제): read 는 scope 당 table 200 / column 500 row 를 fetch 후 Python 매칭 →
그 이상 보유 시 LIMIT 밖 항목은 누락 가능(follow-up: SQL-side 매칭/cap 상향).
"""
from __future__ import annotations

import logging

from modules.utils import _normalize_scope_key, _scope_candidates

_log = logging.getLogger("kb_metadata")

_TABLE_READ_LIMIT = 200
_COLUMN_READ_LIMIT = 500
_INJECT_TABLE_CAP = 40
_INJECT_COLUMN_CAP = 200


def _ro_conn(conn):
    """(conn, owned). conn 미지정이면 agent_kb RO 연결을 연다(owned=True → 호출측 close)."""
    if conn is not None:
        return conn, False
    from modules.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


# ── 관리(RW) — 메타데이터 거버넌스 콘솔 CRUD (ITEM-11 Phase 2) ──────────────────
# admin 콘솔(feature-0003 /api/admin/metadata/tables|columns)이 호출. 읽기와 달리 **단일
# scope_key 만** 다룬다(common 캐스케이드 없음) — 편집/삭제는 정확히 그 scope 행에만 적용돼야
# ds 격리가 깨지지 않는다. 전부 id(PK) 기준 + scope_key 가드로 cross-scope 오작용을 차단한다.
# 호출측(web)이 RBAC(kb.ingest.manual)·audit·commit·conn 수명을 책임진다(코어는 SQL 만).
# kb_glossary.py:80~170 시그니처/주석 패턴 복제.
_TABLE_ADMIN_LIMIT = 1000
_COLUMN_ADMIN_LIMIT = 2000


def list_table_desc_admin(conn, scope_key, limit=_TABLE_ADMIN_LIMIT):
    """admin 목록 — 단일 scope 의 테이블 설명 행(id 포함). 최신 갱신 우선. read 와 달리 캐스케이드 없음."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, description, source, "
            "created_at, updated_at FROM table_descriptions WHERE scope_key = %s "
            "ORDER BY updated_at DESC, id DESC LIMIT %s",
            (_normalize_scope_key(scope_key), int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def list_column_desc_admin(conn, scope_key, limit=_COLUMN_ADMIN_LIMIT):
    """admin 목록 — 단일 scope 의 컬럼 설명 행(id 포함). table/column 순."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, column_name, description, "
            "source, created_at, updated_at FROM column_descriptions WHERE scope_key = %s "
            "ORDER BY table_name, column_name, id LIMIT %s",
            (_normalize_scope_key(scope_key), int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def upsert_table_desc(conn, scope_key, table_name, description,
                      schema_name="", source="manual", created_by=None) -> None:
    """테이블 설명 upsert(ON CONFLICT scope_key,schema_name,table_name)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO table_descriptions "
            "(scope_key, schema_name, table_name, description, source, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, schema_name, table_name) "
            "DO UPDATE SET description = EXCLUDED.description, "
            "source = EXCLUDED.source, updated_at = now()",
            (_normalize_scope_key(scope_key), str(schema_name or "").strip(),
             str(table_name).strip(), str(description).strip(),
             str(source or "manual").strip(), created_by),
        )
    finally:
        cur.close()


def upsert_column_desc(conn, scope_key, table_name, column_name, description,
                       schema_name="", source="manual", created_by=None) -> None:
    """컬럼 설명 upsert(ON CONFLICT scope_key,schema_name,table_name,column_name)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO column_descriptions "
            "(scope_key, schema_name, table_name, column_name, description, source, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name) "
            "DO UPDATE SET description = EXCLUDED.description, "
            "source = EXCLUDED.source, updated_at = now()",
            (_normalize_scope_key(scope_key), str(schema_name or "").strip(),
             str(table_name).strip(), str(column_name).strip(),
             str(description).strip(), str(source or "manual").strip(), created_by),
        )
    finally:
        cur.close()


def update_table_desc(conn, desc_id, scope_key, description,
                      schema_name=None, table_name=None) -> int:
    """테이블 설명 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 호출측 404).

    schema_name/table_name 은 선택 — None 이면 key 컬럼 미수정(설명만 갱신). 둘 다 주어지면
    key 까지 수정 허용 → UNIQUE 충돌 시 호출측이 IntegrityError 를 409 로 변환.
    """
    cur = conn.cursor()
    try:
        if schema_name is None and table_name is None:
            cur.execute(
                "UPDATE table_descriptions SET description = %s, updated_at = now() "
                "WHERE id = %s AND scope_key = %s",
                (str(description).strip(), int(desc_id), _normalize_scope_key(scope_key)),
            )
        else:
            cur.execute(
                "UPDATE table_descriptions SET schema_name = %s, table_name = %s, "
                "description = %s, updated_at = now() WHERE id = %s AND scope_key = %s",
                (str(schema_name or "").strip(), str(table_name or "").strip(),
                 str(description).strip(), int(desc_id), _normalize_scope_key(scope_key)),
            )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def update_column_desc(conn, desc_id, scope_key, description,
                       schema_name=None, table_name=None, column_name=None) -> int:
    """컬럼 설명 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 404).

    key 컬럼(schema/table/column) 은 전부 주어질 때만 수정(부분 None → 설명만 갱신).
    UNIQUE(scope,schema,table,column) 충돌 시 호출측이 409 로 변환.
    """
    cur = conn.cursor()
    try:
        if schema_name is None and table_name is None and column_name is None:
            cur.execute(
                "UPDATE column_descriptions SET description = %s, updated_at = now() "
                "WHERE id = %s AND scope_key = %s",
                (str(description).strip(), int(desc_id), _normalize_scope_key(scope_key)),
            )
        else:
            cur.execute(
                "UPDATE column_descriptions SET schema_name = %s, table_name = %s, "
                "column_name = %s, description = %s, updated_at = now() "
                "WHERE id = %s AND scope_key = %s",
                (str(schema_name or "").strip(), str(table_name or "").strip(),
                 str(column_name or "").strip(), str(description).strip(),
                 int(desc_id), _normalize_scope_key(scope_key)),
            )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def delete_table_desc(conn, desc_id, scope_key) -> int:
    """테이블 설명 삭제(by id, scope 가드, 멱등). 반영 행 수 반환(0=이미 없음 → 멱등 성공)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM table_descriptions WHERE id = %s AND scope_key = %s",
            (int(desc_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def delete_column_desc(conn, desc_id, scope_key) -> int:
    """컬럼 설명 삭제(by id, scope 가드, 멱등). 반영 행 수 반환(0=이미 없음 → 멱등 성공)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM column_descriptions WHERE id = %s AND scope_key = %s",
            (int(desc_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


# ── 읽기(RO) — ds-scoped ────────────────────────────────────────────────────
def _fetch_table_desc(conn, scopes):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT schema_name, table_name, description FROM table_descriptions "
            "WHERE scope_key = ANY(%s) ORDER BY length(table_name) DESC LIMIT %s",
            (scopes, _TABLE_READ_LIMIT),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def _fetch_column_desc(conn, scopes):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT table_name, column_name, description FROM column_descriptions "
            "WHERE scope_key = ANY(%s) ORDER BY table_name, column_name LIMIT %s",
            (scopes, _COLUMN_READ_LIMIT),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def load_table_column_descriptions(user_message, scope_key=None, conn=None) -> str:
    """질문에 매칭되는 테이블/컬럼 설명을 ds-scoped 로 읽어 프롬프트 본문 조립.

    매칭: 테이블명·컬럼명이 질문에 등장(대소문자 무관). 미매칭/미가용 → "".
    datamark·펜스 헤더는 호출측(_build_knowledge_context)이 부여한다(kb_glossary 동형).
    """
    msg = (user_message or "").lower()
    if not msg:
        return ""
    # ds-scope: 명시 scope 없으면 **활성 datasource** 의 scope_key 사용. CURRENT_FACT_SCOPE_KEY 는
    # 멀티DS 에서 갱신되지 않아 ds 격리/매칭이 깨진다(kb_glossary BLOCKER) → get_active_datasource().
    if scope_key is None:
        from modules import config as _cfg
        scope_key = _cfg.get_active_datasource()
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)
        if c is None:
            return ""
        scopes = _scope_candidates(scope_key)  # [active_ds_scope, 'common', '']
        tables = _fetch_table_desc(c, scopes)
        cols = _fetch_column_desc(c, scopes)
    except Exception as exc:
        _log.debug("table_column_desc_read_failed err=%r", exc)
        return ""
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass

    matched_tables = [
        (sch, tb, d) for (sch, tb, d) in tables if tb and str(tb).lower() in msg
    ]
    matched_cols = [
        (tb, col, d) for (tb, col, d) in cols if col and str(col).lower() in msg
    ]
    if not matched_tables and not matched_cols:
        return ""

    lines: list[str] = []
    if matched_tables:
        lines.append("테이블 설명:")
        for sch, tb, d in matched_tables[:_INJECT_TABLE_CAP]:
            label = f"{sch}.{tb}" if sch else str(tb)
            lines.append(f"- {label} — {d}")
    if matched_cols:
        lines.append("컬럼 설명:")
        for tb, col, d in matched_cols[:_INJECT_COLUMN_CAP]:
            lines.append(f"- {tb}.{col} — {d}")
    return "\n".join(lines)


def load_column_descriptions_for_table(schema_name, table_name, scope_key=None, conn=None) -> dict:
    """describe_table 오버레이용 — (scope, schema, table) 의 컬럼 설명 {column_name: description}.

    같은 (scope_key, schema, table) 의 column_descriptions 를 ds-scoped(active∪common) 로 읽어
    column_name→description dict 반환. native COLUMN_COMMENT 가 빈 컬럼만 KB 설명으로 채울 때 사용.
    PG 미가용/실패 → {} (graceful — 기존 출력 유지). schema_name 매칭은 빈 schema('') 도 허용해
    단일 스키마 DB 와 정합.
    """
    tb = str(table_name or "").strip()
    if not tb:
        return {}
    if scope_key is None:
        from modules import config as _cfg
        scope_key = _cfg.get_active_datasource()
    sch = str(schema_name or "").strip()
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)
        if c is None:
            return {}
        scopes = _scope_candidates(scope_key)
        cur = c.cursor()
        try:
            # schema 일치 또는 빈 schema('') 둘 다 허용(단일 스키마 DB 는 schema_name='' 로 저장).
            cur.execute(
                "SELECT column_name, description FROM column_descriptions "
                "WHERE scope_key = ANY(%s) AND table_name = %s "
                "AND (schema_name = %s OR schema_name = '') "
                "ORDER BY (schema_name = %s) DESC LIMIT %s",
                (scopes, tb, sch, sch, _COLUMN_READ_LIMIT),
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()
    except Exception as exc:
        _log.debug("column_desc_for_table_read_failed err=%r", exc)
        return {}
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass

    out: dict[str, str] = {}
    # ORDER BY (schema 일치 우선) → 같은 컬럼이 빈-schema 와 정확-schema 둘 다 있으면 정확 schema 가
    # 먼저 와 setdefault 로 우선 채택된다.
    for col, desc in rows:
        cn = str(col or "").strip()
        if cn and cn not in out:
            out[cn] = str(desc or "").strip()
    return out
