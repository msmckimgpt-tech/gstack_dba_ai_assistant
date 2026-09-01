"""ITEM-10 (ROADMAP dba-ai-nl2sql): 용어사전(kb_glossary) + ENUM 코드사전(enum_dictionary).

도메인 용어 정의·컬럼 열거형 코드↔라벨 매핑을 agent_kb(Postgres)에 product-scoped(scope_key,
fact_entries 동일 컨벤션)로 저장하고, 질문/스키마 매칭 시 _build_knowledge_context 가
프롬프트에 주입(datamark 은 호출측). 저장=RW, 읽기=RO. PG 미가용/미매칭이면 "" (무영향).

product-scope (metadata-product-scope): scope_key = **활성 제품**( cfg.get_active_product_scope()
= `product.<ProductKey>` ) + 'common' 캐스케이드. 사용자·메타데이터 관리자가 인식하는 작업 범위가
제품이므로 등록·주입 축을 제품으로 통일한다 — 한 제품이 N개 datasource 에 걸쳐도 그 제품의 모든
질의에 주입되고, 한 datasource 를 N개 제품이 공유해도 남의 제품 용어가 혼입되지 않는다.
(종전 ds-scope 는 양쪽 다 깨졌다: 등록분이 1/N DS 에서만 주입 · 공유 DS 에서 타 제품 혼입.)
등록(upsert)도 동일 scope_key(=제품 스코프 또는 'common' 공용)로 저장해야 read 가 매칭된다.

한계(launch 볼륨 전제): read 는 scope 당 glossary 200 / enum 500 row 를 fetch 후 Python 매칭 →
제품이 그 이상 보유 시 LIMIT 밖 항목은 누락 가능(follow-up: SQL-side 매칭/cap 상향).
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict

from modules.utils import _normalize_scope_key, _kb_scope_candidates, _kb_scope_key

_log = logging.getLogger("kb_glossary")

_GLOSSARY_READ_LIMIT = 200
_ENUM_READ_LIMIT = 500
_INJECT_TERM_CAP = 40
_INJECT_ENUM_CAP = 200
_FEEDBACK_ADMIN_LIMIT = 500

# 역할(role) 차원(0021) — role_key='*' 는 역할 비특정(공용) 용어. WebRoles.RoleKey(admin/operator/…)
# 비정규화 복제(glossary=PG, WebRoles=MySQL cross-DB 라 FK 불가). 읽기 시 [현재 역할, '*'] 캐스케이드.
COMMON_ROLE = "*"

#: 전역 사전 scope. `_kb_scope_candidates()` 읽기 캐스케이드의 두 번째 티어이자, `org` 용어의 저장처.
GLOBAL_SCOPE = "common"


def _normalize_role_key(role_key) -> str:
    """role_key 정규화 — 공백/None → '*'(공용), 그 외 소문자 trim(WebRoles.RoleKey 와 동일 표기)."""
    rk = str(role_key or "").strip().lower()
    return rk or COMMON_ROLE


# ── 용어 통용범위(term_tier) — 0057 ─────────────────────────────────────────────
#
# ## 왜 이 축이 생겼나 (사용자 신고 2026-09-01)
#
# 읽기(`_kb_scope_candidates`)는 `[제품, (레거시 ds), common, '']` **2단** 캐스케이드인데
# 쓰기(`agent_core._glossary_autopropose`)는 **항상 제품 scope 하나**였다. 전역 티어가 읽기에만
# 있고 쓰기에는 없었다 — 그래서 범용 DB 용어(복제 이벤트·Online DDL·시점 복구·트랜잭션·CTE)가
# 제품 scope 에 갇히고, 같은 개념이 제품 수만큼 복제됐다(라이브 실측: 34개 용어가 2~4 scope,
# `멱등성` 한 개념이 표기변형까지 7행).
#
# 프롬프트가 그 비대칭을 증폭했다: confidence 를 "how clearly defined AND **how reusable**" 로
# 정의해 **범용일수록 점수가 올라 자동승급 임계를 넘고, 그렇게 가장 좁은 scope 에 박혔다.**
# 재사용성이 저장 위치를 좁히는 방향으로 작동한 것이 근본 원인이다.
#
# 그래서 두 축을 **직교**시킨다:
#   - `confidence` = 이 턴이 그 용어를 **얼마나 명확히 정의했는가** (등록/보류 판정)
#   - `term_tier`  = 그 용어가 **어디까지 통용되는가** (저장 위치 판정)
TIER_PRODUCT = "product"   #: 이 제품 고유 도메인 어휘 → `product.<key>` 에 저장
TIER_ORG = "org"           #: 제품 무관하되 이 조직/서비스 고유 → `common` 전역 사전
TIER_GENERAL = "general"   #: 범용 RDBMS·업계 표준 지식 → **저장하지 않는다**
TERM_TIERS = (TIER_PRODUCT, TIER_ORG, TIER_GENERAL)

#: `general` 판정 후보의 큐 상태. 조용히 버리지 않는 이유 — 「요즘 용어가 안 쌓인다」와 구별되지
#: 않고, 오분류를 되돌릴 방법도 사라진다. 큐에 남기면 관리자가 사유를 보고 promote 로 되살린다.
STATUS_SKIPPED_GENERAL = "skipped_general"

#: 이 상태들은 이미 사람/시스템의 판정이 끝난 후보 — 재제안해도 되살리지 않는다(poisoning 방어).
_SETTLED_STATUSES = ("rejected", "promoted", "auto_promoted", STATUS_SKIPPED_GENERAL)

_PAREN_TAIL_RE = re.compile(r"\s*[(（].*$", re.S)
_SURFACE_STRIP_RE = re.compile(r"[\s_\-]+")


def normalize_term_tier(tier) -> str:
    """tier 정규화. 미지정·오타·미지원 값은 `product`(가장 좁은 범위)로 접는다.

    **모르면 좁게** — 잘못해서 전역(`org`)에 넣으면 모든 제품 프롬프트가 오염되지만, 잘못해서
    제품에 넣으면 그 제품 하나에 머문다. 판정 불가일 때 피해가 작은 쪽이 기본값이다.
    """
    t = str(tier or "").strip().lower()
    return t if t in TERM_TIERS else TIER_PRODUCT


def normalize_term_surface(term) -> str:
    """표기변형 흡수용 정규화 표면형.

    `멱등성` / `멱등성(Idempotency)` / `멱등성(idempotent)` / `복합 PK` / `복합 PK (Composite
    Primary Key)` 처럼 **같은 개념의 다른 표기**를 한 키로 접는다. 라이브에서 이 변형들이 서로
    다른 행으로 공존해 사전을 부풀렸다(`멱등성` 7행 · `DeleteFlag` 4행 · `CTE` 3표기).

    규칙 (순서 고정):
      1. 첫 여는 괄호(`(` 또는 전각 `（`) 이후를 잘라낸다 — 괄호는 관례적으로 원어·부연이다.
      2. 공백·하이픈·언더스코어 제거 — `복합 PK`↔`복합PK`, `user_id`↔`userID`.
      3. 소문자화.

    ⚠ **이 규칙은 alembic 0057 의 `ix_kb_glossary_term_norm` 함수 인덱스 식과 같아야 한다.**
    갈리면 인덱스가 안 쓰여 느려지거나(양성), 조회 키가 어긋나 중복을 못 잡는다(음성).
    """
    s = _PAREN_TAIL_RE.sub("", str(term or "").strip())
    return _SURFACE_STRIP_RE.sub("", s).lower()


#: 결정적 백스톱 — 이 표면형은 LLM 이 무엇이라 하든 `general` 로 강등한다.
#:
#: ⚠ **부분일치가 아니라 정규화 전체일치다.** 라이브에는 `튜닝인덱스`(무기 강화 단계)·`인덱스
#: 비중`(테이블 인덱스 용량 비율) 같은 **제품 고유** 용어가 있어서, "인덱스" 부분일치로 걸면
#: 정당한 도메인 어휘를 통째로 잃는다. 그래서 개념 하나당 표기를 명시 열거한다.
#:
#: 여기 없는 범용 용어는 LLM 판정에 맡긴다 — 이 목록은 **완전성이 목표가 아니라**, 라이브에서
#: 실제로 오등록된 클래스를 구조적으로 봉인하는 것이 목표다(§16.7 G10 재발 클래스 가드).
_GENERAL_TERM_SURFACES: frozenset = frozenset(
    normalize_term_surface(t) for t in (
        # 트랜잭션·동시성
        "트랜잭션", "transaction", "트랜잭션 롤백", "롤백", "rollback", "커밋", "commit",
        "암묵적 커밋", "implicit commit", "자동 커밋", "autocommit",
        "격리 수준", "isolation level", "트랜잭션 격리 수준", "MVCC",
        "교착 상태", "데드락", "deadlock", "락", "lock", "잠금", "낙관적 잠금", "비관적 잠금",
        # 인덱스·실행계획
        "인덱스", "index", "복합 인덱스", "composite index", "B-tree 인덱스", "B-tree",
        "DESC 인덱스", "내림차순 인덱스", "커버링 인덱스", "covering index",
        "클러스터드 인덱스", "clustered index", "논클러스터드 인덱스", "유니크 인덱스",
        "풀 스캔", "full scan", "full table scan", "테이블 풀 스캔",
        "실행 계획", "execution plan", "explain", "explain plan", "filesort", "카디널리티",
        "cardinality", "선택도", "selectivity", "인덱스 역순 스캔",
        # 복제·백업·복구
        "복제", "replication", "복제 이벤트", "replication event", "증분 복제",
        "incremental replication", "비동기 복제", "반동기 복제", "마스터", "슬레이브",
        "레플리카", "replica", "복제 지연", "replication lag",
        "바이너리 로그", "binlog", "binary log", "GTID",
        "백업", "backup", "전체 백업", "증분 백업", "논리 백업", "물리 백업",
        "복구", "restore", "recovery", "시점 복구", "point in time recovery", "PITR",
        "장애 조치", "failover", "스위치오버", "switchover",
        # DDL·스키마 운영
        "online DDL", "온라인 DDL", "DDL", "DML", "DCL", "TCL",
        "스키마", "schema", "테이블", "table", "뷰", "view", "머티리얼라이즈드 뷰",
        "파티션", "partition", "파티셔닝", "partitioning", "샤딩", "sharding",
        "기본키", "primary key", "복합 PK", "복합 기본 키", "composite primary key",
        "외래키", "foreign key", "참조 무결성", "referential integrity",
        "제약 조건", "constraint", "유니크 제약", "체크 제약",
        "정규화", "normalization", "반정규화", "denormalization",
        # 쿼리 문법
        "CTE", "공통 테이블 표현식", "common table expression",
        "서브쿼리", "subquery", "윈도우 함수", "window function",
        "조인", "join", "내부 조인", "외부 조인", "inner join", "outer join",
        "집계 함수", "aggregate function", "GROUP BY", "ORDER BY", "HAVING",
        "저장 프로시저", "stored procedure", "트리거", "trigger", "커서", "cursor",
        "CONTINUE HANDLER", "EXIT HANDLER FOR SQLEXCEPTION", "핸들러",
        # 엔진·성능 일반
        "InnoDB", "MyISAM", "버퍼 풀", "buffer pool", "슬로우 쿼리", "slow query",
        "쿼리 캐시", "커넥션 풀", "connection pool", "N+1", "N+1 문제",
        "논리적 삭제", "logical deletion", "소프트 삭제", "soft delete",
        "멱등성", "idempotency", "idempotent",
        "배치 처리", "batch processing", "벌크 인서트", "bulk insert",
        # 표준 카탈로그 객체 (제품 고유가 아님)
        "information_schema", "performance_schema", "sys 스키마",
        "TABLE_ROWS", "ROW_COUNT()", "lower_case_table_names", "collation", "charset",
        "문자셋", "정렬 규칙",
    )
)

#: 결정적 강등의 두 번째 축 — 순수 SQL 키워드/구문 토큰. 위 열거에 없어도 이 패턴이면 general.
#: (`SELECT`·`LEFT JOIN`·`ALTER TABLE` 처럼 대문자 SQL 토큰만으로 이뤄진 표면.)
_SQL_KEYWORD_RE = re.compile(
    r"^(?:select|insert|update|delete|merge|truncate|alter|create|drop|rename|grant|revoke|"
    r"union|intersect|except|distinct|limit|offset|where|from|set|values|into|as|on|using|"
    r"left|right|full|cross|natural|inner|outer|join|case|when|then|else|end|null|not|and|or|"
    r"in|between|like|exists|all|any|some|order|by|group|having|with|recursive|table|column|"
    r"index|view|database|begin|start|rollback|commit|savepoint|lock|unlock|explain|analyze|"
    r"describe|show|desc|asc)(?:\s+(?:select|insert|update|delete|merge|truncate|alter|create|"
    r"drop|rename|grant|revoke|union|intersect|except|distinct|limit|offset|where|from|set|"
    r"values|into|as|on|using|left|right|full|cross|natural|inner|outer|join|case|when|then|"
    r"else|end|null|not|and|or|in|between|like|exists|all|any|some|order|by|group|having|with|"
    r"recursive|table|column|index|view|database|begin|start|rollback|commit|savepoint|lock|"
    r"unlock|explain|analyze|describe|show|desc|asc))*$",
    re.I,
)


def classify_term_tier(term, suggested_tier=None) -> "tuple[str, str]":
    """(tier, reason) — 이 용어가 어디까지 통용되는가.

    판정 순서와 그 이유:

    1. **결정적 강등이 먼저다.** LLM 이 `product` 라 해도 `_GENERAL_TERM_SURFACES` 또는 순수 SQL
       키워드에 걸리면 `general` 로 내린다. 라이브에서 오등록된 것이 바로 이 클래스이고, LLM
       판정만 믿으면 프롬프트를 고쳐도 같은 실수가 다시 통과한다(§16.7 G10 — 재발 클래스는
       점수정이 아니라 구조 가드로 잠근다).
    2. 걸리지 않으면 **LLM 판정을 그대로 쓴다.** `org` ↔ `product` 의 구분은 조직 맥락 판단이라
       리터럴 목록으로 대신할 수 없다.
    3. LLM 이 아무 말도 안 했으면 `product` — 「모르면 좁게」(`normalize_term_tier` 참조).

    ⚠ **강등이 곧 폐기가 아니다.** `general` 후보도 `glossary_feedback` 에
    `status='skipped_general'` 로 남아 관리자가 promote 로 되살릴 수 있다. 그래서 이 결정적
    목록이 과잉 차단하더라도 복구 경로가 있고, 반대로 오염은 즉시 막힌다 — 비대칭이 옳은
    방향으로 서 있다.
    """
    surface = normalize_term_surface(term)
    if not surface:
        return TIER_PRODUCT, "empty-surface"
    if surface in _GENERAL_TERM_SURFACES:
        return TIER_GENERAL, "lexicon"
    raw = _PAREN_TAIL_RE.sub("", str(term or "").strip())
    if raw and _SQL_KEYWORD_RE.match(raw):
        return TIER_GENERAL, "sql-keyword"
    if suggested_tier is None:
        return TIER_PRODUCT, "default"
    return normalize_term_tier(suggested_tier), "llm"


def scope_for_tier(tier, product_scope_key) -> str:
    """tier → 저장 scope. `org` 는 전역(`common`), 그 외는 주어진 제품 scope.

    `general` 은 저장하지 않으므로 호출측이 여기 오기 전에 걸러야 한다 — 그래도 방어적으로
    `common` 을 돌려준다(큐 기록의 scope 로 쓰인다: 전역 개념이므로 제품마다 중복 기록되지 않게).
    """
    t = normalize_term_tier(tier)
    if t in (TIER_ORG, TIER_GENERAL):
        return GLOBAL_SCOPE
    return _normalize_scope_key(product_scope_key)


def _ro_conn(conn):
    """(conn, owned). conn 미지정이면 agent_kb RO 연결을 연다(owned=True → 호출측 close)."""
    from shared.db import _pg_conn_pair_ro
    return _pg_conn_pair_ro(conn)


# ── 저장(RW) — 등록/큐레이션 경로 ────────────────────────────────────────────
def upsert_glossary_term(conn, scope_key, term, definition, role_key=COMMON_ROLE, source="manual",
                         term_tier=TIER_PRODUCT) -> None:
    """용어 등록/갱신(단일 scope). `term_tier` 는 통용범위 축(0057) — 저장 scope 는 호출측 책임.

    ⚠ 이 함수는 **주어진 scope 에 그대로 쓴다** — tier 로 scope 를 바꾸지 않는다. 관리자가 콘솔에서
    「이 제품에 이 용어를 전역으로 표시해 등록」하는 것과 「전역 사전에 등록」은 다른 조작이고,
    여기서 자동 재라우팅하면 관리자가 고른 scope 와 저장된 scope 가 갈린다(§16.7 G7 — 화면이 말한
    것과 저장된 것이 달라지는 형태). 자율수집 경로의 라우팅은 `auto_promote_or_queue` 가 한다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source, term_tier) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, role_key, term) "
            "DO UPDATE SET definition = EXCLUDED.definition, source = EXCLUDED.source, "
            "              term_tier = EXCLUDED.term_tier, updated_at = now()",
            (_normalize_scope_key(scope_key), _normalize_role_key(role_key),
             str(term).strip(), str(definition).strip(), str(source or "manual").strip(),
             normalize_term_tier(term_tier)),
        )
    finally:
        cur.close()


def upsert_enum_entry(conn, scope_key, table_name, column_name, code, label, schema_name="",
                      source="manual") -> None:
    # source(0039) — kb_glossary.source 동형. 수동 등록/편집=manual, 자동수집분=auto(_insert_enum_auto).
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO enum_dictionary "
            "(scope_key, schema_name, table_name, column_name, code, label, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name, code) "
            "DO UPDATE SET label = EXCLUDED.label, source = EXCLUDED.source, updated_at = now()",
            (_normalize_scope_key(scope_key), str(schema_name or "").strip(),
             str(table_name).strip(), str(column_name).strip(),
             str(code).strip(), str(label).strip(), str(source or "manual").strip()),
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
            "SELECT id, scope_key, role_key, term, definition, source, created_at, updated_at, "
            "term_tier FROM kb_glossary WHERE " + " AND ".join(clauses) + " "
            "ORDER BY updated_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def list_global_glossary_for_scope(conn, limit=_GLOSSARY_ADMIN_LIMIT, role_key=None):
    """전역 사전(`common`) 의 용어 — **제품 목록 화면에 함께 보여주기 위한** 읽기 전용 조회.

    왜 필요한가: `list_glossary_admin` 은 단일 scope 만 본다(편집·삭제가 정확히 그 scope 행에만
    적용돼야 하므로 — 캐스케이드 금지는 유지한다). 그런데 답변에 실제로 주입되는 것은
    `[제품, common]` **둘 다**다. 목록이 제품 행만 보여주면 관리자는 「이 제품에 이 용어가 없다」고
    읽고 같은 용어를 제품 scope 에 또 등록한다 — 지금의 중복이 만들어진 경로 그 자체다.
    화면은 이 결과를 **읽기 전용 배지**로 구분해 표시한다(편집은 전역 scope 를 선택해야 가능).
    """
    clauses = ["scope_key = %s"]
    params: list = [GLOBAL_SCOPE]
    if role_key is not None:
        clauses.append("role_key = ANY(%s)")
        params.append([_normalize_role_key(role_key), COMMON_ROLE])
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, role_key, term, definition, source, created_at, updated_at, "
            "term_tier FROM kb_glossary WHERE " + " AND ".join(clauses) + " "
            "ORDER BY updated_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def list_enum_admin(conn, scope_key, limit=_ENUM_ADMIN_LIMIT):
    """admin 목록 — 단일 scope 의 ENUM 행(id·source 포함). table/column/code 순."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, column_name, code, label, "
            "source, created_at, updated_at FROM enum_dictionary WHERE scope_key = %s "
            "ORDER BY table_name, column_name, code, id LIMIT %s",
            (_normalize_scope_key(scope_key), int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def list_global_enum_for_scope(conn, limit=_ENUM_ADMIN_LIMIT):
    """전역(`common`) ENUM — **제품 목록 화면에 함께 보여주기 위한** 읽기 전용 조회.

    `list_global_glossary_for_scope` 와 같은 이유다: 답변에 실제로 주입되는 것은
    `[제품, common]` 둘 다인데 목록이 제품 행만 보여주면 관리자는 「이 제품에 이 코드가 없다」로
    읽고 같은 항목을 제품 scope 에 또 등록한다. 편집·삭제는 여전히 단일 scope 정확일치로만
    동작하고, 화면이 이 행들을 읽기 전용으로 그린다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, column_name, code, label, "
            "source, created_at, updated_at FROM enum_dictionary WHERE scope_key = %s "
            "ORDER BY table_name, column_name, code, id LIMIT %s",
            (GLOBAL_SCOPE, int(limit)),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def update_glossary_term(conn, term_id, scope_key, term, definition, role_key=None,
                         term_tier=None) -> int:
    """용어 수정(by id, scope 가드). 반영 행 수 반환(0=비존재/타-scope → 호출측 404).

    role_key 지정 시 역할 귀속까지 변경(공용↔역할 이동). `term_tier` 지정 시 통용범위 표기 변경
    (저장 scope 는 옮기지 않는다 — scope 이동은 삭제+재등록 또는 소급 정리 스크립트의 몫).
    UNIQUE(scope,role,term) 충돌 시 호출측이 IntegrityError 를 409 로 변환.
    수동 수정은 source='manual' 로 마킹(큐레이션 표시).
    """
    sets = ["term = %s", "definition = %s"]
    params: list = [str(term).strip(), str(definition).strip()]
    if role_key is not None:
        sets.append("role_key = %s")
        params.append(_normalize_role_key(role_key))
    if term_tier is not None:
        sets.append("term_tier = %s")
        params.append(normalize_term_tier(term_tier))
    sets.append("source = 'manual'")
    sets.append("updated_at = now()")
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE kb_glossary SET " + ", ".join(sets) + " WHERE id = %s AND scope_key = %s",
            tuple(params) + (int(term_id), _normalize_scope_key(scope_key)),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


# ── 표기변형·교차 scope 중복 조회 (0057) ───────────────────────────────────────
#
# 종전 중복 억제는 `(scope_key, role_key, term)` **정확일치** 하나뿐이었다. 그래서
#   (a) 같은 용어가 제품마다 따로 등록되고(34개 용어 × 2~4 scope),
#   (b) 같은 개념이 표기만 달라도 별 행이 됐다(`멱등성` 7행 · `CTE` 3표기 · `복합 PK` 4행).
# 아래 두 함수가 등록 **직전**에 그 둘을 함께 본다.

def find_glossary_duplicate(conn, scopes, term, role_key=COMMON_ROLE):
    """주어진 scope 목록에서 이 용어의 **정규화 표면형** 중복 행을 찾는다.

    반환: `(id, scope_key, role_key, term, definition, source, term_tier)` 또는 None.
    정렬은 **전역(common) 우선 → 정확일치 우선 → 최신** — 전역에 이미 있으면 제품 등록을
    막는 것이 목적이므로 그쪽을 먼저 본다.

    정규화식은 `normalize_term_surface()` 와 동일해야 하며 alembic 0057 의
    `ix_kb_glossary_term_norm` 이 이 조회를 인덱스로 받는다.
    """
    surface = normalize_term_surface(term)
    if not surface:
        return None
    scope_list = [_normalize_scope_key(s) for s in (scopes or []) if str(s or "").strip()]
    if GLOBAL_SCOPE not in scope_list:
        scope_list.append(GLOBAL_SCOPE)
    roles = [_normalize_role_key(role_key), COMMON_ROLE]
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, role_key, term, definition, source, term_tier "
            "FROM kb_glossary "
            "WHERE scope_key = ANY(%s) AND role_key = ANY(%s) "
            "  AND lower(regexp_replace(regexp_replace(term, '\\s*[(（].*$', '', 'g'), "
            "                           '[[:space:]_-]', '', 'g')) = %s "
            "ORDER BY (scope_key = %s) DESC, (lower(term) = %s) DESC, updated_at DESC, id DESC "
            "LIMIT 1",
            (scope_list, roles, surface, GLOBAL_SCOPE, str(term or "").strip().lower()),
        )
        return cur.fetchone()
    finally:
        cur.close()


def _settled_feedback_status(conn, scopes, term, role_key=COMMON_ROLE):
    """이 용어가 **어느 scope 에서든** 이미 판정된 적이 있는가 → (status, scope_key) 또는 None.

    종전 `_feedback_status` 는 `(scope, role, term)` 정확일치라, 제품 A 에서 거부한 용어가
    제품 B 에서 다시 자동등록됐다. 거부·승급·범용판정은 **용어 자체에 대한 판정**이므로
    scope 를 넘어 존중한다(표기변형도 함께 접는다).
    """
    surface = normalize_term_surface(term)
    if not surface:
        return None
    scope_list = [_normalize_scope_key(s) for s in (scopes or []) if str(s or "").strip()]
    if GLOBAL_SCOPE not in scope_list:
        scope_list.append(GLOBAL_SCOPE)
    roles = [_normalize_role_key(role_key), COMMON_ROLE]
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status, scope_key FROM glossary_feedback "
            "WHERE scope_key = ANY(%s) AND role_key = ANY(%s) AND status = ANY(%s) "
            "  AND lower(regexp_replace(regexp_replace(term, '\\s*[(（].*$', '', 'g'), "
            "                           '[[:space:]_-]', '', 'g')) = %s "
            "ORDER BY updated_at DESC, id DESC LIMIT 1",
            (scope_list, roles, list(_SETTLED_STATUSES), surface),
        )
        row = cur.fetchone()
        return (str(row[0]), str(row[1])) if row else None
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
            "column_name = %s, code = %s, label = %s, source = 'manual', updated_at = now() "
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
    """질문에 매칭되는 용어/ENUM 을 product-scoped(+role-scoped) 로 읽어 프롬프트 본문 조립.

    매칭: 용어(term)·ENUM 의 column/table 이 질문에 등장(대소문자 무관). 미매칭/미가용 → "".
    role_key 지정 시 용어는 [그 역할, '*'(공용)] 로 추가 격리(역할별 비중복) — 다른 역할 전용
    용어는 주입되지 않는다. role_key=None 이면 역할 무관(하위호환). ENUM 은 역할 차원 없음(스키마 귀속).
    datamark·펜스 헤더는 호출측(_build_knowledge_context)이 부여한다.
    """
    msg = (user_message or "").lower()
    if not msg:
        return ""
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)  # _pg_connect_ro 예외도 여기서 흡수(docstring 계약)
        if c is None:
            return ""
        # product-scope: 명시 scope 없으면 **활성 제품** 스코프 사용(_kb_scope_candidates 내부 해소).
        scopes = _kb_scope_candidates(scope_key)  # [active_product_scope, 'common', '']
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
                               approved_by=None, term_tier=TIER_PRODUCT) -> bool:
    """glossary_feedback 큐에 후보 적재/갱신(upsert by scope/role/term).

    같은 (scope,role,term) 기존 행이 'rejected'/'promoted'/'auto_promoted'/'skipped_general' 이면
    갱신하지 않는다 (curator 결정 존중·중복 등록 방지) — ON CONFLICT DO UPDATE WHERE status='pending'.
    신규 term 은 항상 INSERT(주어진 status). 반환: 적재/갱신됨 True, 무시(이미 처리됨) False.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO glossary_feedback "
            "(scope_key, role_key, term, suggested_definition, confidence, status, "
            " source_run_id, conversation_id, promoted_glossary_id, approved_by, term_tier) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, role_key, term) DO UPDATE SET "
            "  suggested_definition = EXCLUDED.suggested_definition, "
            "  confidence = EXCLUDED.confidence, "
            "  status = EXCLUDED.status, "
            "  source_run_id = EXCLUDED.source_run_id, "
            "  conversation_id = EXCLUDED.conversation_id, "
            "  promoted_glossary_id = EXCLUDED.promoted_glossary_id, "
            "  approved_by = EXCLUDED.approved_by, "
            "  term_tier = EXCLUDED.term_tier, "
            "  updated_at = now() "
            "WHERE glossary_feedback.status = 'pending'",
            (_normalize_scope_key(scope_key), _normalize_role_key(role_key),
             str(term).strip(), str(suggested_definition).strip(), float(confidence),
             str(status), source_run_id, conversation_id, promoted_glossary_id, approved_by,
             normalize_term_tier(term_tier)),
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


def _insert_glossary_auto(conn, scope_key, role_key, term, definition, term_tier=TIER_PRODUCT):
    """자동승급 — kb_glossary 에 INSERT(source='auto'). 이미 있으면 보존(덮어쓰지 않음 — 수동
    큐레이션/기존 정의 우선). 반환: glossary id(신규 또는 기존) 또는 None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source, term_tier) "
            "VALUES (%s, %s, %s, %s, 'auto', %s) "
            "ON CONFLICT (scope_key, role_key, term) DO NOTHING RETURNING id",
            (scope_key, role_key, term, definition, normalize_term_tier(term_tier)),
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
                          threshold=None, term_tier=None) -> str:
    """하이브리드 자동승급 라우터(단일 후보).

    반환: `'auto_promoted'` | `'pending'` | `'skipped_general'` | `'duplicate'` | `'skipped'`.

    ## 판정 순서 (0057 — 순서 자체가 계약이다)

    1. **빈 입력** → `skipped`.
    2. **통용범위 판정** (`classify_term_tier`) — LLM 제안 + 결정적 강등.
    3. **`general`** → `kb_glossary` 에 **쓰지 않고** 큐에 `skipped_general` 로만 남긴다.
       조용히 버리면 「요즘 용어가 안 쌓인다」와 구별되지 않고 오분류를 되돌릴 방법도 없다.
    4. **저장 scope 결정** — `org` 는 전역(`common`), `product` 는 주어진 제품 scope.
    5. **판정 이력 선검사(cross-scope)** — 다른 제품에서 이미 거부·승급·범용판정된 용어는
       여기서 멈춘다. 종전엔 `(scope, role, term)` 정확일치라 **제품 A 에서 거부한 용어가 제품
       B 에서 다시 자동등록**됐다(REV-20260629 가 닫은 poisoning 구멍의 scope 축 확장).
    6. **표기변형·교차 scope 중복 선검사** — 이미 전역에 있거나 같은 개념이 다른 표기로 있으면
       `duplicate`. 라이브에서 `멱등성` 이 7행(4 scope)까지 불어난 경로를 여기서 끊는다.
    7. **`org` 는 자동승급하지 않는다** — 전역 사전은 **모든 제품** 프롬프트에 주입되므로 blast
       radius 가 제품의 N배다. 「고신뢰=자동등록」을 더 넓은 면에 그대로 반복하면 지금 고치는
       실수를 규모만 키워 재현한다. 전역 후보는 항상 검토 큐(`pending`)를 거친다.
    8. `product` 는 종전대로 confidence 임계로 자동승급/보류.
    """
    rk = _normalize_role_key(role_key)
    t = str(term or "").strip()
    d = str(definition or "").strip()
    if not t or not d:
        return "skipped"

    tier, tier_reason = classify_term_tier(t, term_tier)
    product_scope = _normalize_scope_key(scope_key)
    target_scope = scope_for_tier(tier, product_scope)
    # 선검사 대상 scope — 제품 + 전역. 판정 이력·중복은 두 축을 함께 봐야 한다.
    lookup_scopes = [product_scope, GLOBAL_SCOPE]

    if threshold is None:
        from shared import config as _cfg
        threshold = getattr(_cfg, "AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD", 0.85)
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0

    # (5) 판정 이력 — scope 를 넘어 존중한다(표기변형 포함).
    settled = _settled_feedback_status(conn, lookup_scopes, t, role_key=rk)
    if settled is not None:
        _log.debug("glossary_candidate_settled term=%r status=%s scope=%s", t, settled[0], settled[1])
        return "skipped"

    # (3) 범용 지식 — 저장하지 않되 사유는 남긴다.
    if tier == TIER_GENERAL:
        record_glossary_suggestion(
            conn, target_scope, rk, t, d, confidence=conf, status=STATUS_SKIPPED_GENERAL,
            source_run_id=source_run_id, conversation_id=conversation_id,
            approved_by=f"auto:{tier_reason}", term_tier=TIER_GENERAL,
        )
        return STATUS_SKIPPED_GENERAL

    # (6) 표기변형·교차 scope 중복.
    dup = find_glossary_duplicate(conn, lookup_scopes, t, role_key=rk)
    if dup is not None:
        _log.debug("glossary_candidate_duplicate term=%r existing_id=%s scope=%s",
                   t, dup[0], dup[1])
        return "duplicate"

    # (7) 전역 후보는 임계와 무관하게 검토 큐.
    if tier == TIER_ORG:
        ok = record_glossary_suggestion(
            conn, target_scope, rk, t, d, confidence=conf, status="pending",
            source_run_id=source_run_id, conversation_id=conversation_id,
            term_tier=TIER_ORG,
        )
        return "pending" if ok else "skipped"

    # (8) 제품 고유 용어 — 종전 하이브리드 자동승급.
    #
    # ⚠ 단 **제품이 해소되지 않은 대화**(제품 없는 1:1·CLI)에서는 `scope_key` 가 'common' 으로
    #   들어온다. 그 상태로 자동승급하면 «제품 고유» 로 판정한 용어를 **전역 사전에** 써넣는
    #   것이 되어, 지금 고치는 오염을 반대 방향으로 재현한다. 이 경우엔 검토 큐로 보낸다 —
    #   관리자가 어느 제품 것인지 보고 옮길 수 있다.
    if target_scope == GLOBAL_SCOPE:
        ok = record_glossary_suggestion(
            conn, GLOBAL_SCOPE, rk, t, d, confidence=conf, status="pending",
            source_run_id=source_run_id, conversation_id=conversation_id,
            term_tier=TIER_PRODUCT,
        )
        return "pending" if ok else "skipped"
    if conf >= float(threshold):
        gid = _insert_glossary_auto(conn, target_scope, rk, t, d, term_tier=TIER_PRODUCT)
        ok = record_glossary_suggestion(
            conn, target_scope, rk, t, d, confidence=conf, status="auto_promoted",
            source_run_id=source_run_id, conversation_id=conversation_id,
            promoted_glossary_id=gid, approved_by="auto", term_tier=TIER_PRODUCT,
        )
        return "auto_promoted" if ok else "skipped"
    ok = record_glossary_suggestion(
        conn, target_scope, rk, t, d, confidence=conf, status="pending",
        source_run_id=source_run_id, conversation_id=conversation_id,
        term_tier=TIER_PRODUCT,
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
            "created_at, updated_at, term_tier FROM glossary_feedback" + where +
            " ORDER BY created_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def count_glossary_feedback(conn, status="pending", scope_key=None) -> int:
    """검토 큐 건수(배지용). status 기본 pending. scope_key 지정 시 그 scope 로 한정 — 검토 큐 목록
    필터(list_glossary_feedback)와 동일 축이라 배지↔리스트 카운트가 datasource 선택 시 정합한다."""
    clauses: list = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(str(status))
    if scope_key:
        clauses.append("scope_key = %s")
        params.append(_normalize_scope_key(scope_key))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cur = conn.cursor()
    try:
        cur.execute("SELECT count(*) FROM glossary_feedback" + where, tuple(params))
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        cur.close()


def promote_glossary_feedback(conn, feedback_id, *, approved_by=None):
    """검토 큐 → 용어사전 승급(by id, FOR UPDATE 동시승인 차단).

    승급 대상 상태는 `pending` 과 **`skipped_general`** 둘이다. 후자를 포함하는 이유: 범용 판정은
    결정적 목록·LLM 판정의 산물이라 오분류가 가능하고(제품 고유 어휘가 범용 낱말과 겹치는 경우),
    그때 관리자가 되살릴 경로가 없으면 그 판정이 사실상 영구 삭제가 된다. 승급분은 큐 행에 기록된
    `term_tier` 를 그대로 옮겨 「무엇으로 판정됐고 무엇으로 등록됐는지」가 갈리지 않게 한다.

    반환: 승급된 glossary id, 또는 None(없음/이미 처리됨). 승급분은 source='manual'(검수 완료).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT scope_key, role_key, term, suggested_definition, term_tier "
            "FROM glossary_feedback "
            "WHERE id = %s AND status IN ('pending', %s) FOR UPDATE",
            (int(feedback_id), STATUS_SKIPPED_GENERAL),
        )
        row = cur.fetchone()
        if not row:
            return None
        sk, rk, term, definition, tier = row
        cur.execute(
            "INSERT INTO kb_glossary (scope_key, role_key, term, definition, source, term_tier) "
            "VALUES (%s, %s, %s, %s, 'manual', %s) "
            "ON CONFLICT (scope_key, role_key, term) "
            "DO UPDATE SET definition = EXCLUDED.definition, source = 'manual', "
            "              term_tier = EXCLUDED.term_tier, updated_at = now() "
            "RETURNING id",
            (sk, rk, term, definition, normalize_term_tier(tier)),
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
    """단일 용어 행(id). scope_key 주면 가드.

    반환: `(id, scope_key, role_key, term, definition, source, term_tier)` 또는 None.
    """
    cur = conn.cursor()
    try:
        if scope_key:
            cur.execute(
                "SELECT id, scope_key, role_key, term, definition, source, term_tier "
                "FROM kb_glossary WHERE id = %s AND scope_key = %s",
                (int(term_id), _normalize_scope_key(scope_key)),
            )
        else:
            cur.execute(
                "SELECT id, scope_key, role_key, term, definition, source, term_tier "
                "FROM kb_glossary WHERE id = %s",
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


def normalize_suggestion_items(items, *, max_terms) -> list:
    """LLM(또는 브리지 러너)이 준 용어 후보 목록을 검증·정규화한다.

    반환 항목: `{term, definition, confidence, term_tier}`. 스키마 위반 항목은 조용히 버린다
    (부분 성공 허용 — 한 항목이 망가졌다고 나머지를 잃지 않는다).

    **왜 별도 함수인가**: 후보의 출처가 둘이 됐다 — 서버 LLM(`llm_glossary_suggest`)과 **개인 AI
    러너**(feature-0043 브리지의 `submit_answer` 동봉). 검증을 각자 하면 한쪽만 느슨해지고, 느슨한
    쪽이 사용자에게 도달하는 진실이 된다(§16.7 G8-a — 결정은 모든 진입점에 적용돼야 한다).
    특히 러너 입력은 **통제 밖 LLM 의 산물**이라 신뢰 경계 밖이다 — 길이·타입·tier 화이트리스트를
    여기 한 곳에서 강제한다.
    """
    out: list = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        term = str(it.get("term", "")).strip()
        definition = str(it.get("definition", "")).strip()
        if not term or not definition or len(term) > 128:
            continue
        try:
            conf = float(it.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        conf = min(1.0, max(0.0, conf))
        out.append({
            "term": term,
            # 정의는 프롬프트에 실리므로 상한을 둔다(러너가 문서 한 편을 보내는 것을 막는다).
            "definition": definition[:2000],
            "confidence": conf,
            # `tier` 는 LLM 스키마 키, `term_tier` 는 저장 컬럼명 — 양쪽 표기를 모두 받는다.
            "term_tier": normalize_term_tier(it.get("term_tier") or it.get("tier") or it.get("scope")),
        })
        if len(out) >= int(max_terms):
            break
    return out


def infer_terminology_suggestions(user_message, assistant_answer, *, max_terms=None) -> list:
    """대화 한 턴(질문+답변)에서 용어사전 후보 추론(LLM 위임).

    반환: `[{term, definition, confidence, term_tier}]`. 미가용/실패/빈 입력 → []
    (호출측 ask 경로 차단 금지). term 길이 cap·개수 cap 적용.
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
    return normalize_suggestion_items(items, max_terms=max_terms)


# ── ENUM 코드사전 대화 자율수집 큐 + 하이브리드 자동승급 (0039) ────────────────────
# 용어사전(glossary_feedback, 0023) 의 ENUM 대칭. 대화 답변 직후 LLM 이 추론한 (table.column) 코드↔라벨
# 후보를, 사용자 결정(하이브리드)에 따라 처리한다:
#   confidence ≥ THRESHOLD → enum_dictionary 자동 등록(source='auto') + enum_feedback(auto_promoted)
#     감사 추적(되돌리기 가능 — reject 시 source='auto' 행 제거).
#   미만 → enum_feedback(pending) 검토 큐 → 관리자가 promote/reject.
# poisoning 방어: 거부(rejected)된 후보는 재제안해도 되살아나지 않는다(ON CONFLICT WHERE pending).
# key = (scope, schema, table, column, code) — enum_dictionary UNIQUE 와 동일 컨벤션.

def record_enum_suggestion(conn, scope_key, schema_name, table_name, column_name, code,
                           suggested_label, *, confidence=0.5, status="pending",
                           source_run_id=None, conversation_id=None, promoted_enum_id=None,
                           approved_by=None) -> bool:
    """enum_feedback 큐에 후보 적재/갱신(upsert by scope/schema/table/column/code).

    같은 key 기존 행이 'rejected'/'promoted'/'auto_promoted' 면 갱신하지 않는다(curator 결정
    존중·중복 방지) — ON CONFLICT DO UPDATE WHERE status='pending'. 신규 key 는 항상 INSERT.
    반환: 적재/갱신됨 True, 무시(이미 처리됨) False.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO enum_feedback "
            "(scope_key, schema_name, table_name, column_name, code, suggested_label, "
            " confidence, status, source_run_id, conversation_id, promoted_enum_id, approved_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name, code) DO UPDATE SET "
            "  suggested_label = EXCLUDED.suggested_label, "
            "  confidence = EXCLUDED.confidence, "
            "  status = EXCLUDED.status, "
            "  source_run_id = EXCLUDED.source_run_id, "
            "  conversation_id = EXCLUDED.conversation_id, "
            "  promoted_enum_id = EXCLUDED.promoted_enum_id, "
            "  approved_by = EXCLUDED.approved_by, "
            "  updated_at = now() "
            "WHERE enum_feedback.status = 'pending'",
            (_normalize_scope_key(scope_key), str(schema_name or "").strip(),
             str(table_name).strip(), str(column_name).strip(), str(code).strip(),
             str(suggested_label).strip(), float(confidence), str(status),
             source_run_id, conversation_id, promoted_enum_id, approved_by),
        )
        return int(cur.rowcount or 0) > 0
    finally:
        cur.close()


def _enum_feedback_status(conn, scope_key, schema_name, table_name, column_name, code):
    """현재 key 의 enum_feedback.status 반환(없으면 None). 자동승급 선검사용."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status FROM enum_feedback WHERE scope_key = %s AND schema_name = %s "
            "AND table_name = %s AND column_name = %s AND code = %s",
            (scope_key, schema_name, table_name, column_name, code),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None
    finally:
        cur.close()


def _settled_enum_status(conn, scopes, schema_name, table_name, column_name, code):
    """이 (schema, table, column, code) 가 **어느 scope 에서든** 판정된 적이 있는가.

    반환: `(status, scope_key)` 또는 None.

    용어 축(`_settled_feedback_status`)의 ENUM 대칭이다. 종전 `_enum_feedback_status` 는
    `(scope, schema, table, column, code)` 정확일치라, 제품 A 에서 거부한 코드가 **제품 B 에서
    다시 자동등록**될 수 있었다 — 거부·승급은 그 코드 자체에 대한 판정이므로 scope 를 넘어
    존중해야 한다.

    ⚠ 지금 라이브에 교차 scope ENUM 중복은 0건이다(키에 schema·table 이 들어가 제품마다 갈리기
    때문). 그러니 이 함수는 관측된 사고를 고치는 게 아니라, **용어 축에서 실제로 터진 구멍의
    같은 형태를 ENUM 축에서 미리 닫는다** — 두 축이 같은 코드 패턴을 공유하는데 한쪽만 고치면
    다음 사람이 「여긴 왜 다르지」에서 시작한다.
    """
    sn, tb = str(schema_name or "").strip(), str(table_name or "").strip()
    col, cd = str(column_name or "").strip(), str(code or "").strip()
    if not tb or not col or not cd:
        return None
    scope_list: list = []
    for s in (scopes or []):
        if not str(s or "").strip():
            continue
        norm = _normalize_scope_key(s)
        if norm not in scope_list:      # 호출부가 sk == GLOBAL_SCOPE 를 넘기면 중복이 된다.
            scope_list.append(norm)
    if GLOBAL_SCOPE not in scope_list:
        scope_list.append(GLOBAL_SCOPE)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status, scope_key FROM enum_feedback "
            "WHERE scope_key = ANY(%s) AND schema_name = %s AND table_name = %s "
            "  AND column_name = %s AND code = %s AND status = ANY(%s) "
            "ORDER BY updated_at DESC, id DESC LIMIT 1",
            (scope_list, sn, tb, col, cd,
             ["rejected", "promoted", "auto_promoted"]),
        )
        row = cur.fetchone()
        return (str(row[0]), str(row[1])) if row else None
    finally:
        cur.close()


def _insert_enum_auto(conn, scope_key, schema_name, table_name, column_name, code, label):
    """자동승급 — enum_dictionary 에 INSERT(source='auto'). 이미 있으면 보존(수동 큐레이션 우선).
    반환: enum id(신규 또는 기존) 또는 None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO enum_dictionary "
            "(scope_key, schema_name, table_name, column_name, code, label, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'auto') "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name, code) "
            "DO NOTHING RETURNING id",
            (scope_key, schema_name, table_name, column_name, code, label),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute(
            "SELECT id FROM enum_dictionary WHERE scope_key=%s AND schema_name=%s "
            "AND table_name=%s AND column_name=%s AND code=%s",
            (scope_key, schema_name, table_name, column_name, code),
        )
        r2 = cur.fetchone()
        return int(r2[0]) if r2 else None
    finally:
        cur.close()


def auto_promote_or_queue_enum(conn, scope_key, schema_name, table_name, column_name, code,
                               label, *, confidence, source_run_id=None,
                               conversation_id=None, threshold=None) -> str:
    """하이브리드 자동승급 라우터(단일 ENUM 후보). 반환: 'auto_promoted' | 'pending' | 'skipped'.

    'skipped' = 빈 입력이거나 이미 거부/처리된 후보(재제안 무시).
    """
    sk = _normalize_scope_key(scope_key)
    sn = str(schema_name or "").strip()
    tb = str(table_name or "").strip()
    col = str(column_name or "").strip()
    cd = str(code or "").strip()
    lb = str(label or "").strip()
    if not tb or not col or not cd or not lb:
        return "skipped"
    if threshold is None:
        from shared import config as _cfg
        threshold = getattr(_cfg, "AGENT_ENUM_AUTOPROMOTE_THRESHOLD", 0.9)
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0
    # ⚠ 거부/처리 선검사 (glossary auto_promote_or_queue 동형 — REV-20260629 BLOCKER): enum_dictionary
    # 자동 INSERT 는 거부 가드보다 반드시 먼저 차단돼야 한다(거부 후보 재유입·중복 자동 INSERT 방지).
    #
    # 2026-09-01: 그 검사를 **scope 를 넘어** 본다(`_settled_enum_status`). 종전 정확일치는
    # 제품 A 의 거부가 제품 B 에 전달되지 않아, 용어 축에서 실제로 터진 것과 같은 구멍이었다.
    settled = _settled_enum_status(conn, [sk, GLOBAL_SCOPE], sn, tb, col, cd)
    if settled is not None:
        _log.debug("enum_candidate_settled key=%s.%s=%s status=%s scope=%s",
                   tb, col, cd, settled[0], settled[1])
        return "skipped"
    if conf >= float(threshold):
        eid = _insert_enum_auto(conn, sk, sn, tb, col, cd, lb)
        ok = record_enum_suggestion(
            conn, sk, sn, tb, col, cd, lb, confidence=conf, status="auto_promoted",
            source_run_id=source_run_id, conversation_id=conversation_id,
            promoted_enum_id=eid, approved_by="auto",
        )
        return "auto_promoted" if ok else "skipped"
    ok = record_enum_suggestion(
        conn, sk, sn, tb, col, cd, lb, confidence=conf, status="pending",
        source_run_id=source_run_id, conversation_id=conversation_id,
    )
    return "pending" if ok else "skipped"


def list_enum_feedback(conn, status="pending", scope_key=None, limit=_FEEDBACK_ADMIN_LIMIT):
    """검토 큐 목록(id 포함). status 필터(기본 pending, 빈값/None=전체), 선택적 scope. 최신 우선."""
    clauses: list = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(str(status))
    if scope_key:
        clauses.append("scope_key = %s")
        params.append(_normalize_scope_key(scope_key))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, schema_name, table_name, column_name, code, "
            "suggested_label, confidence, status, source_run_id, conversation_id, "
            "promoted_enum_id, approved_by, created_at, updated_at FROM enum_feedback" + where +
            " ORDER BY created_at DESC, id DESC LIMIT %s",
            tuple(params) + (int(limit),),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def count_enum_feedback(conn, status="pending", scope_key=None) -> int:
    """검토 큐 건수(배지용). status 기본 pending. scope_key 지정 시 그 scope 로 한정 — 검토 큐 목록
    필터(list_enum_feedback)와 동일 축이라 배지↔리스트 카운트가 datasource 선택 시 정합한다."""
    clauses: list = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(str(status))
    if scope_key:
        clauses.append("scope_key = %s")
        params.append(_normalize_scope_key(scope_key))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cur = conn.cursor()
    try:
        cur.execute("SELECT count(*) FROM enum_feedback" + where, tuple(params))
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        cur.close()


def promote_enum_feedback(conn, feedback_id, *, approved_by=None):
    """검토 큐(pending) → ENUM 코드사전 승급(by id, FOR UPDATE 동시승인 차단).

    반환: 승급된 enum id, 또는 None(없음/이미 처리됨). 승급분은 source='manual'(검수 완료).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT scope_key, schema_name, table_name, column_name, code, suggested_label "
            "FROM enum_feedback WHERE id = %s AND status = 'pending' FOR UPDATE",
            (int(feedback_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        sk, sn, tb, col, cd, label = row
        cur.execute(
            "INSERT INTO enum_dictionary "
            "(scope_key, schema_name, table_name, column_name, code, label, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'manual') "
            "ON CONFLICT (scope_key, schema_name, table_name, column_name, code) "
            "DO UPDATE SET label = EXCLUDED.label, source = 'manual', updated_at = now() "
            "RETURNING id",
            (sk, sn, tb, col, cd, label),
        )
        eid = int(cur.fetchone()[0])
        cur.execute(
            "UPDATE enum_feedback SET status='promoted', approved_by=%s, "
            "promoted_enum_id=%s, updated_at=now() WHERE id=%s",
            (approved_by, eid, int(feedback_id)),
        )
        return eid
    finally:
        cur.close()


def bulk_promote_enum_feedback(conn, feedback_ids, *, approved_by=None) -> list:
    """검토 큐(pending) 다건 → ENUM 코드사전 일괄 승급(구조 묶음 단위 '등록').

    각 id 를 promote_enum_feedback 로 처리하고 결과를 모은다. 단일 트랜잭션(커밋은 호출자):
    하나라도 예외면 호출자가 전체 롤백. 이미 처리됐거나 없는 id 는 enum_id=None 으로 skip 표시
    (예외 아님 — 부분 skip 은 정상). 반환: [{"feedback_id": int, "enum_id": int|None}] (요청 순서).
    """
    results = []
    for fid in feedback_ids:
        eid = promote_enum_feedback(conn, int(fid), approved_by=approved_by)
        results.append({"feedback_id": int(fid), "enum_id": (int(eid) if eid is not None else None)})
    return results


def reject_enum_feedback(conn, feedback_id) -> int:
    """검토 큐 거부(by id). pending 거부 + auto_promoted 되돌리기(자동추가 source='auto' 행 제거).

    수동 큐레이션(source='manual') 행은 보존한다(자동 추가분만 회수). 반환: 처리 행 수(0=대상 아님).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status, promoted_enum_id FROM enum_feedback WHERE id = %s FOR UPDATE",
            (int(feedback_id),),
        )
        row = cur.fetchone()
        if not row:
            return 0
        status, eid = row
        if status not in ("pending", "auto_promoted"):
            return 0
        if status == "auto_promoted" and eid is not None:
            cur.execute("DELETE FROM enum_dictionary WHERE id = %s AND source = 'auto'", (int(eid),))
        cur.execute(
            "UPDATE enum_feedback SET status='rejected', updated_at=now() WHERE id = %s",
            (int(feedback_id),),
        )
        return int(cur.rowcount or 0)
    finally:
        cur.close()


# ── ENUM schema-grounding (환각 DB/테이블 자동등록 차단) ──────────────────────────
# 대화 자율수집(_enum_autopropose)은 LLM 이 답변 프로즈에서 뽑은 (schema, table, column) 을 그대로
# 신뢰해 왔다 → 존재하지 않는 DB/테이블(예: auth scope 에 없는 dbLog.Currency)까지 등록되는 결함.
# 아래 두 순수 함수(SQL-free)는 활성 datasource 의 실제 카탈로그(table_insight fact — agent 가 LLM 에
# 주입하는 grounding 정본)로 (schema, table) 실존을 대조한다. 카탈로그 fetch·prefix strip 은 호출측
# (agent_core._enum_known_table_index)이 수행하고, 여기서는 정규화 전개·판정만 한다(코어 SQL-only 계약).

def build_known_table_index(qualified_names) -> set:
    """알려진 테이블 qualified 이름들 → grounding 매칭용 정규화 인덱스(소문자).

    각 이름 `{schema}.{table}`(MySQL) 또는 `{db}.{schema}.{table}`(MSSQL) 을 여러 매칭 형태로 전개:
      - full            : 원본 전체
      - bare table      : 마지막 segment (schema 미지정 제안 대비)
      - `{first}.{last}`: MSSQL enum 은 (schema_name=db, table_name) 라 `db.table` 로 대조된다
      - `{last two}`    : MySQL `schema.table`
    is_enum_grounded 의 대조 집합. 빈/None 입력 → 빈 set.
    """
    idx: set = set()
    for name in (qualified_names or []):
        low = str(name or "").strip().lower()
        segs = [s for s in low.split(".") if s]
        if not segs:
            continue
        idx.add(low)
        idx.add(segs[-1])
        if len(segs) >= 2:
            idx.add(f"{segs[0]}.{segs[-1]}")
            idx.add(".".join(segs[-2:]))
    return idx


def is_enum_grounded(idx, schema_name, table_name) -> bool:
    """제안된 (schema, table) 이 알려진 카탈로그 idx 에 존재하는가.

    idx=None(카탈로그 미가용) → True(검증 skip, fail-open — false-reject 방지). schema 명시 시 그
    schema 에 해당 table 이 있어야 통과, schema 미지정 시 어떤 schema 든 그 table 이 있으면 통과.
    table 미지정 → False.
    """
    if idx is None:
        return True
    sn = str(schema_name or "").strip().lower()
    tb = str(table_name or "").strip().lower()
    if not tb:
        return False
    if sn:
        return f"{sn}.{tb}" in idx
    return tb in idx


def sweep_ungrounded_enum(conn, scope_key, known_idx, *, dry_run=True) -> dict:
    """scope 의 enum_dictionary + enum_feedback 중 known_idx 로 grounding 되지 않은 (schema, table) 정리.

    소급 정리용(예방 게이트 도입 전 이미 등록된 환각 항목 회수). known_idx = build_known_table_index(...)
    결과를 호출측이 주입(카탈로그 소스는 호출측 — 코어 SQL-only 계약 유지). known_idx=None(카탈로그
    미가용)이면 아무것도 안 함(fail-open, 안전). dry_run=True → 대상 집계만(변경 없음).
    실제 정리(dry_run=False):
      - enum_dictionary: source='auto' 행만 삭제(수동 큐레이션 source='manual' 은 보존).
      - enum_feedback  : status in ('pending','auto_promoted') → 'rejected'(감사 추적 유지, 재유입 차단).
    반환: {"scope", "scanned", "ungrounded": [{schema_name, table_name}], "dict_deleted",
           "feedback_rejected", "dry_run"}.
    """
    sk = _normalize_scope_key(scope_key)
    result = {"scope": sk, "scanned": 0, "ungrounded": [], "dict_deleted": 0,
              "feedback_rejected": 0, "dry_run": bool(dry_run)}
    if not known_idx:
        return result  # fail-open — 카탈로그 없음(None) 또는 빈 set 이면 아무것도 건드리지 않음(파괴 footgun 방지)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT schema_name, table_name FROM enum_dictionary WHERE scope_key = %s "
            "UNION SELECT DISTINCT schema_name, table_name FROM enum_feedback WHERE scope_key = %s",
            (sk, sk),
        )
        pairs = [(str(r[0] or ""), str(r[1] or "")) for r in (cur.fetchall() or [])]
        result["scanned"] = len(pairs)
        for sn, tb in pairs:
            if is_enum_grounded(known_idx, sn, tb):
                continue
            result["ungrounded"].append({"schema_name": sn, "table_name": tb})
            if dry_run:
                continue
            cur.execute(
                "DELETE FROM enum_dictionary WHERE scope_key=%s AND schema_name=%s "
                "AND table_name=%s AND source='auto'",
                (sk, sn, tb),
            )
            result["dict_deleted"] += int(cur.rowcount or 0)
            cur.execute(
                "UPDATE enum_feedback SET status='rejected', updated_at=now() "
                "WHERE scope_key=%s AND schema_name=%s AND table_name=%s "
                "AND status IN ('pending','auto_promoted')",
                (sk, sn, tb),
            )
            result["feedback_rejected"] += int(cur.rowcount or 0)
        return result
    finally:
        cur.close()


def sweep_unknown_schema_enum(conn, scope_key, known_schemas, *, dry_run=True, confirm_lower=None) -> dict:
    """scope 의 enum 중 `schema_name`(=DB)이 **실재하지 않는** 항목 정리 (self-heal 안전판).

    `sweep_ungrounded_enum`(table_insight 점진 카탈로그 기반, 불완전 가능)과 달리, 이 함수는 **완전한**
    실제 스키마/DB 목록(`known_schemas` = load_known_schemas — budget 무관·전량)을 기준으로 DB 존재만
    검증한다 → 목록이 완전하므로 legit enum false-deletion 이 원천적으로 없다. insight-worker self-heal
    (자동·파괴적)의 안전 경로. 예) auth scope 에 실재하지 않는 `dbLog.*` 를 회수하되 실존 `dbAuth.*` 는 보존.

    - `schema_name` 이 **빈** enum(db prefix 미지정)은 건드리지 않는다(어느 DB 인지 판정 불가 — 안전).
      (bare-schema·table-레벨 정리는 운영자 dry-run 검증하는 `scripts/enum_grounding_sweep.py` 담당.)
    - `known_schemas` falsy → no-op(fail-open). MySQL-family 전용(schema==database); MSSQL 은 호출측(insight
      self-heal) 이 제외한다(schema≠database 라 오삭제 위험).
    - `confirm_lower`(선택, 소문자 set): **catalog-shrink 가드** — 주어지면 unknown 스키마 중 이 집합에도
      있는 것(직전 scanned tick 에도 unknown 이었던 것)만 삭제한다. 이번에 처음 관측한 unknown 은 후보
      (`ungrounded`)로만 기록하고 삭제 보류 → 권한 회수/부분조회로 known_schemas 가 일시 축소된 tick 의
      오삭제를 흡수(2회 연속 관측 시에만 삭제). None 이면 게이트 없음(unknown 즉시 삭제 — 운영자 검증 경로용).
    - dry_run=True → 대상만 집계. 실제 정리(dry_run=False): enum_dictionary source='auto' 삭제(수동 보존) +
      enum_feedback pending/auto_promoted → rejected. scope_key 바인딩(타 scope 무영향).
    반환: {"scope","scanned","ungrounded":[{schema_name,table_name:None}](=이번 tick 전체 unknown 후보),
           "dict_deleted","feedback_rejected","dry_run"}.
    """
    sk = _normalize_scope_key(scope_key)
    result = {"scope": sk, "scanned": 0, "ungrounded": [], "dict_deleted": 0,
              "feedback_rejected": 0, "dry_run": bool(dry_run)}
    known = {str(s).strip().lower() for s in (known_schemas or []) if str(s or "").strip()}
    if not known:
        return result  # fail-open — 실제 스키마 목록 없으면 아무것도 건드리지 않음
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT schema_name FROM enum_dictionary WHERE scope_key=%s AND schema_name <> '' "
            "UNION SELECT DISTINCT schema_name FROM enum_feedback WHERE scope_key=%s AND schema_name <> ''",
            (sk, sk),
        )
        schemas = [str(r[0]) for r in (cur.fetchall() or []) if r and str(r[0] or "").strip()]
        result["scanned"] = len(schemas)
        for sn in schemas:
            snl = sn.strip().lower()
            if snl in known:
                continue  # 실재하는 DB — 보존
            result["ungrounded"].append({"schema_name": sn, "table_name": None})  # unknown 후보(전체)
            if dry_run:
                continue
            if confirm_lower is not None and snl not in confirm_lower:
                continue  # 이번 tick 처음 본 unknown — 삭제 보류(다음 scanned tick 재확인 시 삭제)
            cur.execute(
                "DELETE FROM enum_dictionary WHERE scope_key=%s AND schema_name=%s AND source='auto'",
                (sk, sn),
            )
            result["dict_deleted"] += int(cur.rowcount or 0)
            cur.execute(
                "UPDATE enum_feedback SET status='rejected', updated_at=now() "
                "WHERE scope_key=%s AND schema_name=%s AND status IN ('pending','auto_promoted')",
                (sk, sn),
            )
            result["feedback_rejected"] += int(cur.rowcount or 0)
        return result
    finally:
        cur.close()


def infer_enum_suggestions(user_message, assistant_answer, *, max_terms=None) -> list:
    """대화 한 턴(질문+답변)에서 ENUM 코드↔라벨 후보 추론(LLM 위임).

    반환: [{schema_name, table_name, column_name, code, label, confidence}]. 미가용/실패/빈 입력 → [].
    key 필드(table/column/code/label) 가 모두 있어야 채택. term 길이 cap·개수 cap 적용.
    """
    if not str(user_message or "").strip() or not str(assistant_answer or "").strip():
        return []
    # 비용 가드: 코드↔라벨을 설명할 만한 실질 답변이 아닌 짧은 턴은 LLM 추론 자체를 건너뛴다.
    if len(str(assistant_answer).strip()) < 80:
        return []
    if max_terms is None:
        from shared import config as _cfg
        max_terms = getattr(_cfg, "AGENT_ENUM_SUGGEST_MAX", 5)
    try:
        from modules.llm import llm_enum_suggest
        items = llm_enum_suggest({
            "user_message": str(user_message)[:1200],
            "assistant_answer": str(assistant_answer)[:2400],
        })
    except Exception as exc:
        _log.debug("enum_infer_failed err=%r", exc)
        return []
    out: list = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        table_name = str(it.get("table_name", "")).strip()
        column_name = str(it.get("column_name", "")).strip()
        code = str(it.get("code", "")).strip()
        label = str(it.get("label", "")).strip()
        if not table_name or not column_name or not code or not label:
            continue
        if len(table_name) > 128 or len(column_name) > 128 or len(code) > 128:
            continue
        out.append({
            "schema_name": str(it.get("schema_name", "")).strip()[:128],
            "table_name": table_name, "column_name": column_name,
            "code": code, "label": label,
            "confidence": it.get("confidence", 0.5),
        })
        if len(out) >= int(max_terms):
            break
    return out
