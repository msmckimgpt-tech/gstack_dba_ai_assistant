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
_FEEDBACK_ADMIN_LIMIT = 500

# 역할(role) 차원(0021) — role_key='*' 는 역할 비특정(공용) 용어. WebRoles.RoleKey(admin/operator/…)
# 비정규화 복제(glossary=PG, WebRoles=MySQL cross-DB 라 FK 불가). 읽기 시 [현재 역할, '*'] 캐스케이드.
COMMON_ROLE = "*"


def _normalize_role_key(role_key) -> str:
    """role_key 정규화 — 공백/None → '*'(공용), 그 외 소문자 trim(WebRoles.RoleKey 와 동일 표기)."""
    rk = str(role_key or "").strip().lower()
    return rk or COMMON_ROLE


def _ro_conn(conn):
    """(conn, owned). conn 미지정이면 agent_kb RO 연결을 연다(owned=True → 호출측 close)."""
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


# ── 저장(RW) — 등록/큐레이션 경로 ────────────────────────────────────────────
def upsert_glossary_term(conn, scope_key, term, definition, role_key=COMMON_ROLE, source="manual") -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, role_key, term) "
            "DO UPDATE SET definition = EXCLUDED.definition, source = EXCLUDED.source, updated_at = now()",
            (_normalize_scope_key(scope_key), _normalize_role_key(role_key),
             str(term).strip(), str(definition).strip(), str(source or "manual").strip()),
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


# ── 관리(RW) — 메타데이터 거버넌스 콘솔 CRUD (ITEM-11 MVP-1) ──────────────────
# admin 콘솔(feature-0003 /api/admin/metadata/*)이 호출. 읽기(load_glossary_enum_context)와 달리
# **단일 scope_key 만** 다룬다(common 캐스케이드 없음) — 편집/삭제는 정확히 그 scope 행에만 적용돼야
# ds 격리가 깨지지 않는다. 전부 id(PK) 기준 + scope_key 가드로 cross-scope 오작용을 차단한다.
# 호출측(web)이 RBAC(kb.ingest.manual)·audit·commit·conn 수명을 책임진다(코어는 SQL 만).
_GLOSSARY_ADMIN_LIMIT = 1000
_ENUM_ADMIN_LIMIT = 1000


def list_glossary_admin(conn, scope_key, limit=_GLOSSARY_ADMIN_LIMIT, role_key=None):
    """admin 목록 — 단일 scope 의 용어 행(id·role_key·source 포함). 최신 갱신 우선.

    read 와 달리 캐스케이드 없음. role_key 지정 시 정확히 그 역할 행만(공용 '*' 미포함) — 관리
    화면에서 역할별 필터링용. role_key 미지정이면 scope 의 모든 역할 행(역할 컬럼으로 구분 표시).
    """
    clauses = ["scope_key = %s"]
    params: list = [_normalize_scope_key(scope_key)]
    if role_key is not None:
        clauses.append("role_key = %s")
        params.append(_normalize_role_key(role_key))
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, role_key, term, definition, source, created_at, updated_at "
            "FROM kb_glossary WHERE " + " AND ".join(clauses) + " "
            "ORDER BY updated_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def list_enum_admin(conn, scope_key, limit=_ENUM_ADMIN_LIMIT):
    """admin 목록 — 단일 scope 의 ENUM 행(id 포함). table/column/code 순."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, column_name, code, label, "
            "created_at, updated_at FROM enum_dictionary WHERE scope_key = %s "
            "ORDER BY table_name, column_name, code, id LIMIT %s",
            (_normalize_scope_key(scope_key), int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def update_glossary_term(conn, term_id, scope_key, term, definition, role_key=None) -> int:
    """용어 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 호출측 404).

    role_key 지정 시 역할 귀속까지 변경(공용↔역할 이동). UNIQUE(scope,role,term) 충돌 시
    호출측이 IntegrityError 를 409 로 변환. 수동 수정은 source='manual' 로 마킹(큐레이션 표시).
    """
    cur = conn.cursor()
    try:
        if role_key is not None:
            cur.execute(
                "UPDATE kb_glossary SET term = %s, definition = %s, role_key = %s, "
                "source = 'manual', updated_at = now() WHERE id = %s AND scope_key = %s",
                (str(term).strip(), str(definition).strip(), _normalize_role_key(role_key),
                 int(term_id), _normalize_scope_key(scope_key)),
            )
        else:
            cur.execute(
                "UPDATE kb_glossary SET term = %s, definition = %s, "
                "source = 'manual', updated_at = now() WHERE id = %s AND scope_key = %s",
                (str(term).strip(), str(definition).strip(),
                 int(term_id), _normalize_scope_key(scope_key)),
            )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def update_enum_entry(conn, entry_id, scope_key, table_name, column_name,
                      code, label, schema_name="") -> int:
    """ENUM 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 404).

    key 컬럼(schema/table/column/code)까지 수정 허용 — UNIQUE(scope,schema,table,column,code)
    충돌 시 호출측이 IntegrityError 를 409 로 변환한다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE enum_dictionary SET schema_name = %s, table_name = %s, "
            "column_name = %s, code = %s, label = %s, updated_at = now() "
            "WHERE id = %s AND scope_key = %s",
            (str(schema_name or "").strip(), str(table_name).strip(),
             str(column_name).strip(), str(code).strip(), str(label).strip(),
             int(entry_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def delete_glossary_term(conn, term_id, scope_key) -> int:
    """용어 삭제(by id, scope 가드, 멱등). 반영 행 수 반환(0=이미 없음 → 멱등 성공)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM kb_glossary WHERE id = %s AND scope_key = %s",
            (int(term_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def delete_enum_entry(conn, entry_id, scope_key) -> int:
    """ENUM 삭제(by id, scope 가드, 멱등). 반영 행 수 반환(0=이미 없음 → 멱등 성공)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM enum_dictionary WHERE id = %s AND scope_key = %s",
            (int(entry_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


# ── 읽기(RO) — ds-scoped ────────────────────────────────────────────────────
def _fetch_glossary(conn, scopes, role_key=None):
    """ds-scoped 용어 읽기. role_key 지정 시 [그 역할, '*'(공용)] 으로 추가 격리(역할별 비중복).

    role_key=None 이면 역할 필터 없음(하위호환 — 모든 역할 행). 역할이 식별되는 호출(대화 소유자
    역할)에서는 role_key 를 넘겨 다른 역할 전용 용어가 새지 않게 한다.
    """
    cur = conn.cursor()
    try:
        if role_key is None:
            cur.execute(
                "SELECT term, definition FROM kb_glossary WHERE scope_key = ANY(%s) "
                "ORDER BY length(term) DESC LIMIT %s",
                (scopes, _GLOSSARY_READ_LIMIT),
            )
        else:
            roles = [_normalize_role_key(role_key), COMMON_ROLE]
            cur.execute(
                "SELECT term, definition FROM kb_glossary "
                "WHERE scope_key = ANY(%s) AND role_key = ANY(%s) "
                "ORDER BY length(term) DESC LIMIT %s",
                (scopes, roles, _GLOSSARY_READ_LIMIT),
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


def load_glossary_enum_context(user_message, scope_key=None, conn=None, role_key=None) -> str:
    """질문에 매칭되는 용어/ENUM 을 ds-scoped(+role-scoped) 로 읽어 프롬프트 본문 조립.

    매칭: 용어(term)·ENUM 의 column/table 이 질문에 등장(대소문자 무관). 미매칭/미가용 → "".
    role_key 지정 시 용어는 [그 역할, '*'(공용)] 로 추가 격리(역할별 비중복) — 다른 역할 전용
    용어는 주입되지 않는다. role_key=None 이면 역할 무관(하위호환). ENUM 은 역할 차원 없음(스키마 귀속).
    datamark·펜스 헤더는 호출측(_build_knowledge_context)이 부여한다.
    """
    msg = (user_message or "").lower()
    if not msg:
        return ""
    # ds-scope: 명시 scope 없으면 **활성 datasource** 의 scope_key 사용. CURRENT_FACT_SCOPE_KEY 는
    # 멀티DS 에서 갱신되지 않아 ds 격리/매칭이 깨진다(REV BLOCKER) → get_active_datasource().
    if scope_key is None:
        from shared import config as _cfg
        scope_key = _cfg.get_active_datasource()
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)  # _pg_connect_ro 예외도 여기서 흡수(docstring 계약)
        if c is None:
            return ""
        scopes = _scope_candidates(scope_key)  # [active_ds_scope, 'common', '']
        gloss = _fetch_glossary(c, scopes, role_key=role_key)
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


# ── 대화 자율등록 큐 + 하이브리드 자동승급 (0021) ────────────────────────────────
# 대화 답변 직후 LLM 이 추론한 용어 후보를, 사용자 결정(하이브리드)에 따라 처리한다:
#   confidence ≥ THRESHOLD → kb_glossary 자동 등록(source='auto') + glossary_feedback(auto_promoted)
#     감사 추적(되돌리기 가능 — reject 시 source='auto' 행 제거).
#   미만 → glossary_feedback(pending) 검토 큐 → 관리자가 promote/reject.
# poisoning 방어: 거부(rejected)된 후보는 재제안해도 되살아나지 않는다(ON CONFLICT WHERE pending).

def record_glossary_suggestion(conn, scope_key, role_key, term, suggested_definition, *,
                               confidence=0.5, status="pending", source_run_id=None,
                               conversation_id=None, promoted_glossary_id=None,
                               approved_by=None) -> bool:
    """glossary_feedback 큐에 후보 적재/갱신(upsert by scope/role/term).

    같은 (scope,role,term) 기존 행이 'rejected'/'promoted'/'auto_promoted' 면 갱신하지 않는다
    (curator 결정 존중·중복 등록 방지) — ON CONFLICT DO UPDATE WHERE status='pending'.
    신규 term 은 항상 INSERT(주어진 status). 반환: 적재/갱신됨 True, 무시(이미 처리됨) False.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO glossary_feedback "
            "(scope_key, role_key, term, suggested_definition, confidence, status, "
            " source_run_id, conversation_id, promoted_glossary_id, approved_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, role_key, term) DO UPDATE SET "
            "  suggested_definition = EXCLUDED.suggested_definition, "
            "  confidence = EXCLUDED.confidence, "
            "  status = EXCLUDED.status, "
            "  source_run_id = EXCLUDED.source_run_id, "
            "  conversation_id = EXCLUDED.conversation_id, "
            "  promoted_glossary_id = EXCLUDED.promoted_glossary_id, "
            "  approved_by = EXCLUDED.approved_by, "
            "  updated_at = now() "
            "WHERE glossary_feedback.status = 'pending'",
            (_normalize_scope_key(scope_key), _normalize_role_key(role_key),
             str(term).strip(), str(suggested_definition).strip(), float(confidence),
             str(status), source_run_id, conversation_id, promoted_glossary_id, approved_by),
        )
        return int(cur.rowcount or 0) > 0
    finally:
        cur.close()


def _feedback_status(conn, scope_key, role_key, term):
    """현재 (scope,role,term) 의 glossary_feedback.status 반환(없으면 None). 자동승급 선검사용."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status FROM glossary_feedback "
            "WHERE scope_key = %s AND role_key = %s AND term = %s",
            (scope_key, role_key, term),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None
    finally:
        cur.close()


def _insert_glossary_auto(conn, scope_key, role_key, term, definition):
    """자동승급 — kb_glossary 에 INSERT(source='auto'). 이미 있으면 보존(덮어쓰지 않음 — 수동
    큐레이션/기존 정의 우선). 반환: glossary id(신규 또는 기존) 또는 None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source) "
            "VALUES (%s, %s, %s, %s, 'auto') "
            "ON CONFLICT (scope_key, role_key, term) DO NOTHING RETURNING id",
            (scope_key, role_key, term, definition),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute(
            "SELECT id FROM kb_glossary WHERE scope_key=%s AND role_key=%s AND term=%s",
            (scope_key, role_key, term),
        )
        r2 = cur.fetchone()
        return int(r2[0]) if r2 else None
    finally:
        cur.close()


def auto_promote_or_queue(conn, scope_key, term, definition, *, confidence,
                          role_key=COMMON_ROLE, source_run_id=None, conversation_id=None,
                          threshold=None) -> str:
    """하이브리드 자동승급 라우터(단일 후보). 반환: 'auto_promoted' | 'pending' | 'skipped'.

    'skipped' = 빈 입력이거나 이미 거부/처리된 후보(재제안 무시).
    """
    sk = _normalize_scope_key(scope_key)
    rk = _normalize_role_key(role_key)
    t = str(term or "").strip()
    d = str(definition or "").strip()
    if not t or not d:
        return "skipped"
    if threshold is None:
        from shared import config as _cfg
        threshold = getattr(_cfg, "AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD", 0.85)
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0
    # ⚠ 거부/처리 선검사 (REV-20260629 BLOCKER): kb_glossary 자동 INSERT 는 거부 가드보다 반드시
    # 먼저 차단돼야 한다. 과거에 거부(rejected)된 용어가 고신뢰로 재추론될 때 _insert_glossary_auto 가
    # 먼저 라이브에 써넣으면 poisoning 방어가 본체에서 무력화된다(거부 용어 재유입). 또한 이미 등록된
    # (promoted/auto_promoted) 용어의 중복 자동 INSERT 도 무의미. → 삽입 전에 status 로 게이트.
    existing = _feedback_status(conn, sk, rk, t)
    if existing in ("rejected", "promoted", "auto_promoted"):
        return "skipped"
    # 여기 도달 = existing 이 None(신규) 또는 'pending'(아직 미검수) — 둘 다 진행 가능.
    if conf >= float(threshold):
        gid = _insert_glossary_auto(conn, sk, rk, t, d)
        ok = record_glossary_suggestion(
            conn, sk, rk, t, d, confidence=conf, status="auto_promoted",
            source_run_id=source_run_id, conversation_id=conversation_id,
            promoted_glossary_id=gid, approved_by="auto",
        )
        return "auto_promoted" if ok else "skipped"
    ok = record_glossary_suggestion(
        conn, sk, rk, t, d, confidence=conf, status="pending",
        source_run_id=source_run_id, conversation_id=conversation_id,
    )
    return "pending" if ok else "skipped"


def list_glossary_feedback(conn, status="pending", scope_key=None, role_key=None,
                           limit=_FEEDBACK_ADMIN_LIMIT):
    """검토 큐 목록(id 포함). status 필터(기본 pending, 빈값/None=전체), 선택적 scope/role. 최신 우선."""
    clauses: list = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(str(status))
    if scope_key:
        clauses.append("scope_key = %s")
        params.append(_normalize_scope_key(scope_key))
    if role_key is not None:
        clauses.append("role_key = %s")
        params.append(_normalize_role_key(role_key))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, role_key, term, suggested_definition, confidence, status, "
            "source_run_id, conversation_id, promoted_glossary_id, approved_by, "
            "created_at, updated_at FROM glossary_feedback" + where +
            " ORDER BY created_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def count_glossary_feedback(conn, status="pending") -> int:
    """검토 큐 건수(배지용). status 기본 pending."""
    cur = conn.cursor()
    try:
        if status:
            cur.execute("SELECT count(*) FROM glossary_feedback WHERE status = %s", (str(status),))
        else:
            cur.execute("SELECT count(*) FROM glossary_feedback")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        cur.close()


def promote_glossary_feedback(conn, feedback_id, *, approved_by=None):
    """검토 큐(pending) → 용어사전 승급(by id, FOR UPDATE 동시승인 차단).

    반환: 승급된 glossary id, 또는 None(없음/이미 처리됨). 승급분은 source='manual'(검수 완료).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT scope_key, role_key, term, suggested_definition FROM glossary_feedback "
            "WHERE id = %s AND status = 'pending' FOR UPDATE",
            (int(feedback_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        sk, rk, term, definition = row
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source) "
            "VALUES (%s, %s, %s, %s, 'manual') "
            "ON CONFLICT (scope_key, role_key, term) "
            "DO UPDATE SET definition = EXCLUDED.definition, source = 'manual', updated_at = now() "
            "RETURNING id",
            (sk, rk, term, definition),
        )
        gid = int(cur.fetchone()[0])
        cur.execute(
            "UPDATE glossary_feedback SET status='promoted', approved_by=%s, "
            "promoted_glossary_id=%s, updated_at=now() WHERE id=%s",
            (approved_by, gid, int(feedback_id)),
        )
        return gid
    finally:
        cur.close()


def reject_glossary_feedback(conn, feedback_id) -> int:
    """검토 큐 거부(by id). pending 거부 + auto_promoted 되돌리기(자동추가 source='auto' 행 제거).

    수동 큐레이션(source='manual') 행은 보존한다(자동 추가분만 회수). 반환: 처리 행 수(0=대상 아님).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status, promoted_glossary_id FROM glossary_feedback WHERE id = %s FOR UPDATE",
            (int(feedback_id),),
        )
        row = cur.fetchone()
        if not row:
            return 0
        status, gid = row
        if status not in ("pending", "auto_promoted"):
            return 0
        if status == "auto_promoted" and gid is not None:
            # 되돌리기: 자동 추가된 용어만 회수(수동 편집된 행은 source!='auto' 라 보존).
            cur.execute("DELETE FROM kb_glossary WHERE id = %s AND source = 'auto'", (int(gid),))
        cur.execute(
            "UPDATE glossary_feedback SET status='rejected', updated_at=now() WHERE id = %s",
            (int(feedback_id),),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


# ── 유사어/동의어/참조 링크 (0021) ──────────────────────────────────────────────
# 역할별 비중복 namespace 라도, 유사 의미 용어는 glossary_relations 로 교차 참조한다(역할 경계 횡단 허용).

def get_glossary_term(conn, term_id, scope_key=None):
    """단일 용어 행(id). scope_key 주면 가드. 반환: (id, scope_key, role_key, term, definition, source) 또는 None."""
    cur = conn.cursor()
    try:
        if scope_key:
            cur.execute(
                "SELECT id, scope_key, role_key, term, definition, source FROM kb_glossary "
                "WHERE id = %s AND scope_key = %s",
                (int(term_id), _normalize_scope_key(scope_key)),
            )
        else:
            cur.execute(
                "SELECT id, scope_key, role_key, term, definition, source FROM kb_glossary WHERE id = %s",
                (int(term_id),),
            )
        return cur.fetchone()
    finally:
        cur.close()


def add_glossary_relation(conn, from_id, to_id, relation_type="similar", created_by=None) -> None:
    """용어 간 참조 링크 추가(멱등). relation_type ∈ {synonym, similar, see_also}. 자기참조 불가(DB CHECK)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO glossary_relations (from_id, to_id, relation_type, created_by) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (from_id, to_id, relation_type) DO NOTHING",
            (int(from_id), int(to_id), str(relation_type or "similar").strip(), created_by),
        )
    finally:
        cur.close()


def delete_glossary_relation(conn, relation_id) -> int:
    """참조 링크 삭제(by id, 멱등). 반환: 삭제 행 수."""
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM glossary_relations WHERE id = %s", (int(relation_id),))
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def list_glossary_relations(conn, term_id):
    """해당 용어의 인접 참조(방향 무관) + 상대 용어 정보. 관리 UI 의 '유사어' 표시용.

    반환 row: (relation_id, relation_type, from_id, to_id,
               other_id, other_scope_key, other_role_key, other_term, other_definition).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT r.id, r.relation_type, r.from_id, r.to_id, "
            "       g.id, g.scope_key, g.role_key, g.term, g.definition "
            "FROM glossary_relations r "
            "JOIN kb_glossary g ON g.id = (CASE WHEN r.from_id = %s THEN r.to_id ELSE r.from_id END) "
            "WHERE r.from_id = %s OR r.to_id = %s "
            "ORDER BY r.relation_type, g.term",
            (int(term_id), int(term_id), int(term_id)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def infer_terminology_suggestions(user_message, assistant_answer, *, max_terms=None) -> list:
    """대화 한 턴(질문+답변)에서 용어사전 후보 추론(LLM 위임). 반환: [{term, definition, confidence}].

    미가용/실패/빈 입력 → [] (호출측 ask 경로 차단 금지). term 길이 cap·개수 cap 적용.
    """
    if not str(user_message or "").strip() or not str(assistant_answer or "").strip():
        return []
    # 비용 가드: 용어를 정의할 만한 실질 답변이 아닌 짧은 턴은 LLM 추론 자체를 건너뛴다(불필요 호출 절감).
    if len(str(assistant_answer).strip()) < 80:
        return []
    if max_terms is None:
        from shared import config as _cfg
        max_terms = getattr(_cfg, "AGENT_GLOSSARY_SUGGEST_MAX", 5)
    try:
        from modules.llm import llm_glossary_suggest
        items = llm_glossary_suggest({
            "user_message": str(user_message)[:1200],
            "assistant_answer": str(assistant_answer)[:2400],
        })
    except Exception as exc:
        _log.debug("glossary_infer_failed err=%r", exc)
        return []
    out: list = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        term = str(it.get("term", "")).strip()
        definition = str(it.get("definition", "")).strip()
        if not term or not definition or len(term) > 128:
            continue
        out.append({"term": term, "definition": definition,
                    "confidence": it.get("confidence", 0.5)})
        if len(out) >= int(max_terms):
            break
    return out
