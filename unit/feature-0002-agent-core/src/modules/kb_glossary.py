"""ITEM-10 (ROADMAP dba-ai-nl2sql): 용어사전(kb_glossary) + ENUM 코드사전(enum_dictionary).

도메인 용어 정의·컬럼 열거형 코드↔라벨 매핑을 agent_kb(Postgres)에 ds-scoped(scope_key,
fact_entries 동일 컨벤션)로 저장하고, 질문/스키마 매칭 시 _build_knowledge_context 가
프롬프트에 주입(datamark 은 호출측). 저장=RW, 읽기=RO. PG 미가용/미매칭이면 "" (무영향).

ds-scope: scope_key = **활성 datasource**( cfg.get_active_datasource() ) + 'common' 캐스케이드.
타 datasource 의 용어/ENUM 은 혼입되지 않는다. (CURRENT_FACT_SCOPE_KEY 는 멀티DS 에서 갱신되지
않으므로 쓰지 않는다 — REV-…-glossary BLOCKER.) 등록(upsert)도 동일 scope_key(=get_active_datasource
또는 'common' 공용)로 저장해야 read 가 매칭된다.

한계(launch 볼륨 전제): read 는 scope 당 glossary 200 / enum 500 row 를 fetch 후 Python 매칭 →
datasource 가 그 이상 보유 시 LIMIT 밖 항목은 누락 가능(follow-up: SQL-side 매칭/cap 상향).
"""
from __future__ import annotations

import logging
from collections import OrderedDict

from modules.utils import _normalize_scope_key, _scope_candidates

_log = logging.getLogger("kb_glossary")

_GLOSSARY_READ_LIMIT = 200
_ENUM_READ_LIMIT = 500
_INJECT_TERM_CAP = 40
_INJECT_ENUM_CAP = 200


def _ro_conn(conn):
    """(conn, owned). conn 미지정이면 agent_kb RO 연결을 연다(owned=True → 호출측 close)."""
    if conn is not None:
        return conn, False
    from modules.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


# ── 저장(RW) — 등록/큐레이션 경로 ────────────────────────────────────────────
def upsert_glossary_term(conn, scope_key, term, definition) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, term, definition) VALUES (%s, %s, %s) "
            "ON CONFLICT (scope_key, term) "
            "DO UPDATE SET definition = EXCLUDED.definition, updated_at = now()",
            (_normalize_scope_key(scope_key), str(term).strip(), str(definition).strip()),
        )
    finally:
        cur.close()


def upsert_enum_entry(conn, scope_key, table_name, column_name, code, label, schema_name="") -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO enum_dictionary "
            "(scope_key, schema_name, table_name, column_name, code, label) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name, code) "
            "DO UPDATE SET label = EXCLUDED.label, updated_at = now()",
            (_normalize_scope_key(scope_key), str(schema_name or "").strip(),
             str(table_name).strip(), str(column_name).strip(),
             str(code).strip(), str(label).strip()),
        )
    finally:
        cur.close()


# ── 읽기(RO) — ds-scoped ────────────────────────────────────────────────────
def _fetch_glossary(conn, scopes):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT term, definition FROM kb_glossary WHERE scope_key = ANY(%s) "
            "ORDER BY length(term) DESC LIMIT %s",
            (scopes, _GLOSSARY_READ_LIMIT),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def _fetch_enums(conn, scopes):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT table_name, column_name, code, label FROM enum_dictionary "
            "WHERE scope_key = ANY(%s) ORDER BY table_name, column_name, code LIMIT %s",
            (scopes, _ENUM_READ_LIMIT),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def load_glossary_enum_context(user_message, scope_key=None, conn=None) -> str:
    """질문에 매칭되는 용어/ENUM 을 ds-scoped 로 읽어 프롬프트 본문 조립.

    매칭: 용어(term)·ENUM 의 column/table 이 질문에 등장(대소문자 무관). 미매칭/미가용 → "".
    datamark·펜스 헤더는 호출측(_build_knowledge_context)이 부여한다.
    """
    msg = (user_message or "").lower()
    if not msg:
        return ""
    # ds-scope: 명시 scope 없으면 **활성 datasource** 의 scope_key 사용. CURRENT_FACT_SCOPE_KEY 는
    # 멀티DS 에서 갱신되지 않아 ds 격리/매칭이 깨진다(REV BLOCKER) → get_active_datasource().
    if scope_key is None:
        from modules import config as _cfg
        scope_key = _cfg.get_active_datasource()
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)  # _pg_connect_ro 예외도 여기서 흡수(docstring 계약)
        if c is None:
            return ""
        scopes = _scope_candidates(scope_key)  # [active_ds_scope, 'common', '']
        gloss = _fetch_glossary(c, scopes)
        enums = _fetch_enums(c, scopes)
    except Exception as exc:
        _log.debug("glossary_enum_read_failed err=%r", exc)
        return ""
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass

    matched_terms = [(t, d) for (t, d) in gloss if t and str(t).lower() in msg]
    matched_enums = [
        (tb, col, code, lab) for (tb, col, code, lab) in enums
        if (col and str(col).lower() in msg) or (tb and str(tb).lower() in msg)
    ]
    if not matched_terms and not matched_enums:
        return ""

    lines: list[str] = []
    if matched_terms:
        lines.append("용어:")
        for t, d in matched_terms[:_INJECT_TERM_CAP]:
            lines.append(f"- {t}: {d}")
    if matched_enums:
        groups: "OrderedDict[str, list]" = OrderedDict()
        for tb, col, code, lab in matched_enums[:_INJECT_ENUM_CAP]:
            groups.setdefault(f"{tb}.{col}", []).append(f"{code}={lab}")
        lines.append("ENUM 코드(컬럼 값↔의미):")
        for key, vals in groups.items():
            lines.append(f"- {key}: " + ", ".join(vals))
    return "\n".join(lines)
