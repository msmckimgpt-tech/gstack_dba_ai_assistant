"""DBA Agent Tools — LLM이 호출하는 도구 정의 및 구현.

이 모듈은 OpenAI function calling 형식의 도구 스키마와 실행 함수를 제공한다.
모든 DB 탐색/실행은 이 도구를 통해서만 이루어진다.
"""

from __future__ import annotations

import contextvars
import json
import time
from typing import Any

from shared.config import AGENT_TOP_N, AGENT_MAX_SHOW
from shared.db import execute_sql as _raw_execute_sql, DatasourceCircuitOpen
from .render import save_csv
from . import dialects as _dialects  # Stage 2 P5: engine 별 introspection/sample SQL

__all__ = [
    "TOOL_DEFINITIONS",
    "execute_tool",
    "set_active_schema_allowlist",
    "clear_active_schema_allowlist",
]

# ── 시스템 스키마 ────────────────────────────────────────────────
# 메타데이터 스키마 — Product whitelist 와 무관하게 agent tools 가 항상 접근 가능.
# DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요해 기본 허용한다. MySQL GRANT 가 2차 방어.
_METADATA_SCHEMAS = frozenset({
    "information_schema", "mysql", "performance_schema", "sys",
})
# 에이전트 내부 스키마 — whitelist 로 차단 유지. 타 계정 대화/세션/권한 데이터 보호.
_INTERNAL_SCHEMAS = frozenset({"agent_memory"})
# `_is_user_schema` / `search_tables` 의 "사용자 스키마 아님" 판정에 쓰이는 union.
_SYSTEM_SCHEMAS = _METADATA_SCHEMAS | _INTERNAL_SCHEMAS

# ── Product 단위 스키마 whitelist (None 이면 기존 동작, set 이면 교집합 필터) ──
# TASK-0128 (#2/#8 race): 이전엔 plain 모듈 전역이라 공유 threadpool 에서 동시 ask 가
# 서로의 allowlist 를 덮어쓰는 교차테넌트 레이스가 있었다. ContextVar 로 전환 — asyncio.to_thread
# 가 호출 task 의 context 를 복사해 스레드로 전파하므로 ask 별 격리된다.
_ACTIVE_SCHEMA_ALLOWLIST: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "agent_active_schema_allowlist", default=None
)
# re-gate(4차): 비교는 소문자(case-insensitive)지만, LLM grounding 에는 **원본 케이스** DB명을 보여줘야
# case-sensitive collation 의 SQL Server 에서 3-part 쿼리가 깨지지 않는다(`GameLog_151` vs `gamelog_151`).
_ACTIVE_SCHEMA_ALLOWLIST_DISPLAY: contextvars.ContextVar["list[str] | None"] = contextvars.ContextVar(
    "agent_active_schema_allowlist_display", default=None
)


def set_active_schema_allowlist(schemas: list[str] | set[str] | None) -> None:
    """agent 실행 시작 시 Product 에 배정된 스키마 whitelist 를 설정 (ContextVar, ask 별 격리).

    None 을 넣으면 기존 동작(모든 user schema 접근 가능).
    빈 list/set 을 넣으면 **접근 가능 스키마가 없는 상태** (모든 조회/실행이 거부 — fail-closed).
    비교용은 소문자 set, grounding 표시용은 원본 케이스 list 를 함께 보관한다.
    """
    if schemas is None:
        _ACTIVE_SCHEMA_ALLOWLIST.set(None)
        _ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.set(None)
    else:
        _ACTIVE_SCHEMA_ALLOWLIST.set({str(s).strip().lower() for s in schemas if str(s).strip()})
        # 원본 케이스 보존(중복은 소문자 기준 제거, 순서 유지).
        _seen, _disp = set(), []
        for s in schemas:
            t = str(s).strip()
            if t and t.lower() not in _seen:
                _seen.add(t.lower())
                _disp.append(t)
        _ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.set(_disp)


def clear_active_schema_allowlist() -> None:
    set_active_schema_allowlist(None)


# ── 멀티 datasource (1:N) 런타임 라우터 (TASK-0228) ──────────────────────────────
# 제품이 ≥2 datasource 에 바인딩되면, LLM 이 tool 호출마다 `datasource` 인자로 대상을 고른다.
# 라우터는 그 datasource 의 (연결, 엔진 dialect, 스키마 allowlist) 셋을 **동시에** 활성화해
# 기존 보안 게이트(allowlist·dialect·cross-DB)가 선택된 datasource 기준으로 정확히 동작하게 한다.
#
# **격리 불변식**: tool 실행은 항상 한 datasource 컨텍스트 안에서만 일어난다 — datasource A 의
# allowlist 로는 B 의 스키마를 못 보고, A 연결로는 B 데이터에 못 닿는다. 단일 바인딩(레거시) 제품은
# 라우터를 거치지 않아 동작 0 변경.
_ACTIVE_DS_ROUTER: contextvars.ContextVar["_DatasourceRouter | None"] = contextvars.ContextVar(
    "agent_active_ds_router", default=None
)


class _DatasourceRouter:
    """run-scoped: 라벨 → {ds dict, lazy connection} 매핑 + datasource 별 allowlist/engine 활성화.

    agent_core 가 run 시작에 set_active_ds_router 로 등록하고, finally 에서 close_all + reset 한다.
    연결은 **lazy**(처음 그 datasource 가 선택될 때 connect) — 안 쓰인 datasource 는 연결 안 함.
    """

    def __init__(self, datasources: "list[dict]", connect_fn):
        # datasources: agent_core._resolve_product_datasources 산물(_label/_allow_schemas/_is_primary 포함).
        self._by_label: dict[str, dict] = {}
        self._order: list[str] = []
        for ds in datasources:
            label = str(ds.get("_label") or ds.get("key") or "").strip().lower()
            if label and label not in self._by_label:
                self._by_label[label] = ds
                self._order.append(label)
        self._connect_fn = connect_fn          # (datasource_dict) -> conn  (database=None 강제는 호출부)
        self._conns: dict[str, Any] = {}        # label -> live conn (lazy)
        self._default_label: str = self._order[0] if self._order else ""

    def labels(self) -> "list[str]":
        return list(self._order)

    def describe(self) -> "list[dict]":
        """grounding/프롬프트용 메타(좌표·비밀번호 비노출)."""
        out = []
        for label in self._order:
            ds = self._by_label[label]
            out.append({
                "label": label,
                "engine": str(ds.get("engine") or "mysql"),
                "is_primary": bool(ds.get("_is_primary")),
                "schemas": list(ds.get("_allow_schemas") or []),
                # ITEM-04: 비즈니스 컨텍스트(이 datasource 가 무슨 사업데이터인가) — 라우팅 그라운딩.
                "description": (ds.get("description") or None),
                "domain_tags": list(ds.get("domain_tags") or []),
            })
        return out

    def resolve_label(self, requested: "str | None") -> str:
        """요청 라벨 정규화 — 미지정/미바인딩이면 default(primary)."""
        r = (str(requested).strip().lower() if requested else "")
        return r if r in self._by_label else self._default_label

    def conn_for(self, label: str):
        """그 datasource 의 연결(lazy). database=None 강제(M-1: schema-prefixed only)."""
        ds = self._by_label.get(label)
        if ds is None:
            return None
        if label not in self._conns:
            self._conns[label] = self._connect_fn(ds)
        return self._conns[label]

    def activate(self, label: str) -> None:
        """선택된 datasource 의 allowlist·engine·default_db ContextVar 를 활성화(보안 게이트 기준)."""
        import shared.config as _cfg
        ds = self._by_label.get(label)
        if ds is None:
            return
        set_active_schema_allowlist(ds.get("_allow_schemas") or [])
        _cfg.set_active_datasource(
            (ds.get("scope_key") or ds.get("key") or label),
            engine=ds.get("engine"),
            default_db=ds.get("default_db"),
        )

    def close_all(self) -> None:
        for c in self._conns.values():
            try:
                c.close()
            except Exception:
                pass
        self._conns.clear()


def set_active_ds_router(router: "_DatasourceRouter | None"):
    """run 시작 시 멀티 datasource 라우터 등록(반환 token 으로 reset). None=단일 datasource(라우터 없음)."""
    return _ACTIVE_DS_ROUTER.set(router)


def reset_active_ds_router(token) -> None:
    try:
        _ACTIVE_DS_ROUTER.reset(token)
    except Exception:
        _ACTIVE_DS_ROUTER.set(None)


def get_active_ds_router() -> "_DatasourceRouter | None":
    return _ACTIVE_DS_ROUTER.get()


def _excluded_schemas() -> "frozenset[str]":
    """현재 활성 dialect 기준 '사용자 스키마 아님' 집합 (엔진 시스템 스키마 + 내부 스키마).

    P6: dialect 가 시스템 스키마를 단일 소유(A2/C1). MySQL 은 골든(_METADATA_SCHEMAS 와 동일),
    MSSQL 은 sys/INFORMATION_SCHEMA/guest/db_* 역할 스키마를 사용자 스키마 열거에서 제외한다.
    """
    return _dialects.active().system_schemas() | _INTERNAL_SCHEMAS


def _is_user_schema(name: str) -> bool:
    lower = str(name or "").lower()
    if lower in _excluded_schemas():
        return False
    # re-gate MAJOR4(2차): MSSQL DB-단위 모드에서 allowlist 는 **DB명**이라 스키마명(dbo/sales)과 대조하면
    # 정상 스키마가 전부 사라진다(list_schemas 과차단). MSSQL+active_ds 에서는 시스템 스키마만 제외하고
    # pin 된 DB 안의 사용자 스키마를 모두 노출(접근 경계는 DB 단위 — pin 검증은 _struct_schema_access_error).
    if str(_dialects.active().name).lower() == "mssql" and _cfg_get_active_datasource():
        return True
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    if allow is not None and lower not in allow:
        return False
    return True


def _extract_sql_schema_refs(sql: str) -> set[str]:
    """freeform SQL 의 schema·catalog 네임스페이스 토큰을 **AST 기반**(P6)으로 추출.

    이전 정규식 추출(TASK-0040)은 MSSQL 식별자에서 통째로 우회됐다(DESIGN B-1 실측):
    `[master].[sys].[objects]`→0개, `master.dbo.sysobjects`→{master}(schema 오인),
    `"agent_memory"."x"`→0개. 활성 dialect 로 sqlglot 파싱하면 인용(대괄호/ANSI 큰따옴표/백틱)이
    벗겨진 plain 토큰으로 들어오고 3-part `catalog.schema.table` 이 분해돼 우회가 닫힌다.

    반환: 참조된 schema(db) + catalog 토큰 lowercase set(blunt allowlist 대조·테스트용). 무자격
    table·catalog cross-DB 등 datasource 정책은 _freeform_sql_access_error 가 별도 판정한다.
    """
    from . import sql_guard
    schemas, _has_unqualified, catalogs = sql_guard.collect_schema_refs(
        sql, dialect=_dialects.active().sqlglot
    )
    return set(schemas) | set(catalogs)


def _freeform_sql_access_error(sql: str) -> str | None:
    """freeform LLM SQL 의 스키마 접근 정책 — AST 추출 + (datasource 활성 시) 무자격/cross-DB + allowlist.

    P6 축1 (Codex-1): 활성 datasource(멀티 datasource 경로)에서는
      - **무자격 table-ref 는 fail-closed 거부** — 서버 기본 스키마로 암묵 해석돼 allowlist 를
        우회하는 구멍을 닫는다(스키마 명시 강제).
      - **catalog(3-part DB 차원) cross-DB 차단** — datasource 의 default_db 외 DB 참조 거부.
    레거시 단일 MySQL(active_ds None)에서는 기존 동작 유지(무자격 허용 — 연결 기본 DB + GRANT 가
    backstop). 끝으로 schema 토큰을 Product allowlist 와 대조.
    """
    from . import sql_guard
    import shared.config as _cfg
    schemas, has_unqualified, catalogs = sql_guard.collect_schema_refs(
        sql, dialect=_dialects.active().sqlglot
    )
    active_ds = _cfg.get_active_datasource()
    engine = str(_dialects.active().name).lower()

    # ── re-gate(2차): 영구 차단 — agent_memory(앱 내부) + (MSSQL)시스템 DB. allowlist·pin 무관. ──────
    # agent_memory.dbo.fnLeak()(함수참조), master.dbo.syslogins(시스템DB catalog) 등이 allowlist 에
    # 들어가거나 함수형태로 우회하는 경로를 단일 chokepoint 로 차단. (schemas∪catalogs 전부 대조.)
    hard_forbidden = set(_INTERNAL_SCHEMAS)
    if engine == "mssql":
        hard_forbidden |= _dialects.active().system_databases()
    hard_hit = sorted((set(schemas) | set(catalogs)) & hard_forbidden)
    if hard_hit:
        return (
            f"오류: 접근이 영구 차단된 데이터베이스 참조: {', '.join(hard_hit)} "
            f"(앱 내부/시스템 DB — allowlist 무관 차단)."
        )

    # ── TASK-0206 DB-단위 접근: MSSQL 은 catalog(DB) 가 접근 단위 ──────────────────
    if engine == "mssql" and active_ds:
        # 연결은 제품 primary DB(default_db)로 pin → 2-part `schema.table` 은 그 DB. 다른 허용 DB 는
        # 3-part `db.schema.table`(cross-DB). 무자격(1-part)은 거부(스키마 명시 강제).
        if has_unqualified:
            return (
                "오류: MSSQL 은 테이블을 최소 `스키마.테이블`(현재 DB) 또는 `데이터베이스.스키마.테이블`"
                "(다른 허용 DB)로 명시해야 합니다 (무자격 테이블명 거부)."
            )
        # 유효 allowlist = 저장 allowlist − 시스템 DB − 내부 DB (admin 이 master/agent_memory 를 넣어도 무효).
        allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
        allow_set = ({str(a).strip().lower() for a in allow} if allow else set()) - hard_forbidden
        # re-gate MAJOR6 (M1 보존): 시스템 DB 는 freeform 조회 대상이 아니다(allow_set 에서 이미 제거).
        # fail-closed: allow=None(미설정)도 빈 allowlist 로 취급(데이터 종속: 미바인딩=접근 0).
        blocked = sorted(c for c in catalogs if c and c not in allow_set)
        if blocked:
            allowed_str = ", ".join(sorted(allow_set)) or "(없음)"
            return (
                f"오류: 접근이 허용되지 않은 데이터베이스 참조: {', '.join(blocked)}. "
                f"이 제품에 허용된 DB: {allowed_str}."
            )
        # re-gate(3차) BLOCKER1: pin 검증을 **무조건** 수행한다. 연결은 pin 된 primary DB 로 붙으므로 2-part·
        # 무명세 scalar UDF(`SELECT dbo.fnLeak()` — schemas 비어 과거 검사 우회)·바인딩 모든 쿼리가 pin DB 에서
        # 실행된다. pin 이 유효 allowlist 멤버가 아니면(또는 비었으면) 어떤 쿼리도 미허용 DB 로 새므로 거부.
        pin_err = _mssql_pin_gate()
        if pin_err:
            return pin_err
        # 스키마(db part)는 allowlist 대조 안 함(DB 단위). 단 시스템 스키마(sys/guest/db_*)는 차단 — M1 보존
        # (master.sys.sql_logins 등 freeform 직접 조회 차단; RO GRANT 가 사용자 스키마 경계).
        sysschemas = _dialects.active().system_schemas() - _dialects.active().metadata_schemas()
        blocked_sys = sorted(s for s in schemas if s and s in sysschemas)
        if blocked_sys:
            return (
                f"오류: 시스템 스키마 직접 조회가 차단되었습니다: {', '.join(blocked_sys)} "
                f"(구조 탐색은 list_schemas/describe_table 사용)."
            )
        return None

    # ── MySQL (또는 datasource 없음): DB-단위(schema==database) ──────────────────
    if active_ds and has_unqualified:
        return (
            "오류: 멀티 datasource 모드에서는 모든 테이블을 데이터베이스로 명시해야 합니다 "
            "(무자격 테이블명은 보안상 거부됩니다 — 예: `mydb.mytable`)."
        )
    # re-gate(4차) BLOCKER5: **빈 allowlist = 접근 0** 불변식. allow 가 None(레거시 무제한) 이 아니라
    # 빈 set([]) 이면(auto 모드·미바인딩·해석실패 폴백) 무자격 테이블 조회도 거부한다. 과거엔 datasource
    # 비활성(active_ds None) 경로에서 무자격 `SELECT * FROM Secrets` 가 데이터 계정 기본 DB 로 실행됐다.
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    if allow is not None and len(allow) == 0 and has_unqualified:
        return (
            "오류: 접근 가능한 데이터베이스가 없습니다(빈 접근목록). 무자격 테이블 조회를 거부합니다 "
            "(제품을 선택하거나 접근 가능 데이터베이스를 구성하세요)."
        )
    # MySQL 은 db==schema → schemas + catalogs(3-part 희소) 토큰을 DB allowlist 와 대조.
    return _whitelist_violation(set(schemas) | set(catalogs))


def _whitelist_violation(refs: set[str]) -> str | None:
    """참조된 스키마 중 접근이 허용되지 않은 것이 있으면 에러 메시지 반환.

    메타데이터 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 는
    Product whitelist 와 무관하게 항상 통과한다. 에이전트가 DB 구조를 탐색할 때
    카탈로그·뷰·런타임 통계 조회가 필요하기 때문이다. `mysql` 의 민감 테이블은
    DB 커넥터가 쓰는 MySQL 계정의 GRANT 로 2 차 방어된다.

    `agent_memory` 는 whitelist 로 차단 유지 — 타 계정 대화/세션/권한 override 를
    LLM 이 직접 조회하는 경로를 막는다.

    P6: 항상-허용 메타데이터 스키마는 활성 dialect 가 소유한다(MySQL=information_schema/mysql/
    sys/perf, MSSQL=sys/INFORMATION_SCHEMA 만 — db_* 역할 스키마는 allowlist 통과 필요).

    re-gate BLOCKER4: 앱 내부 DB(`agent_memory`)는 allowlist 멤버십·allow=None 과 **무관하게 항상 차단**.
    (관리자가 실수로 allowlist 에 넣어도, allow=None 레거시 경로라도 — RBAC/대화/PasswordHash 유출 방지.)
    """
    internal = sorted({str(r).strip().lower() for r in refs
                       if r and str(r).strip().lower() in _INTERNAL_SCHEMAS})
    if internal:
        return f"오류: 내부 데이터베이스 직접 조회가 차단되었습니다: {', '.join(internal)} (allowlist 무관 영구 차단)."
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    if allow is None:
        return None
    metadata = _dialects.active().metadata_schemas()
    allowed = set(allow) | set(metadata)
    blocked = [r for r in refs if r and r not in allowed]
    if not blocked:
        return None
    allowed_str = ", ".join(sorted(allow)) or "(none)"
    meta_str = "/".join(sorted(metadata)) or "(none)"
    return (
        f"오류: 접근이 허용되지 않은 스키마 참조: {', '.join(sorted(blocked))}. "
        f"현재 Product 에 허용된 스키마: {allowed_str}. "
        f"메타데이터 스키마({meta_str}) 는 항상 접근 가능."
    )


def _struct_schema_access_error(schema: str) -> str | None:
    """구조화 도구(describe_*/sample/indexes/foreign_keys/search)의 schema_name 접근검사 — DB-단위(TASK-0206).

    - **MySQL**: schema_name = 데이터베이스 → DB allowlist 대조(`_whitelist_violation`, 현행).
    - **MSSQL**: schema_name = pin 된 primary DB 안의 **스키마**(dbo 등) → DB allowlist(=DB명) 와 대조하면
      dbo 가 차단된다. 따라서 allowlist 대조 대신 **시스템 스키마(sys/guest/db_*)만 차단**(M1 보존). 다른 허용
      DB 의 객체는 freeform 3-part 로 탐색(구조화 도구는 primary DB 범위).
    """
    s = str(schema or "").strip().lower()
    # re-gate BLOCKER4: 앱 내부 DB(agent_memory)는 구조화 도구에서도 allowlist 무관 영구 차단
    # (get_sample_rows(schema_name="agent_memory", ...) → WebAccounts.PasswordHash 유출 경로 차단).
    if s in _INTERNAL_SCHEMAS:
        return f"오류: 내부 데이터베이스 직접 조회가 차단되었습니다: {s} (allowlist 무관 영구 차단)."
    if str(_dialects.active().name).lower() == "mssql" and _cfg_get_active_datasource():
        if s in _dialects.active().system_schemas():
            return f"오류: 시스템 스키마는 직접 접근할 수 없습니다: {s} (구조 탐색은 list_schemas 사용)."
        # re-gate BLOCKER1: 구조화 도구는 pin 된 primary DB 안에서 실행된다 — pin 이 유효 allowlist 멤버가
        # 아니면(또는 pin 미설정 → 로그인 기본 DB 로 연결) 미허용 DB 객체를 읽으므로 fail-closed 차단.
        return _mssql_pin_gate()
    return _whitelist_violation({s})


def _mssql_pin_gate() -> str | None:
    """MSSQL active datasource 에서 연결 pin(default_db)이 **유효 allowlist 멤버**인지 검증(fail-closed).

    연결은 pin 된 DB 로 붙으므로(없으면 로그인 기본 DB), pin 이 유효 allowlist 밖이면 모든 쿼리·구조화
    도구가 미허용 DB 에서 실행된다. 유효 allowlist = 저장 allowlist − 시스템 DB − 내부 DB. freeform·구조화
    도구(스키마 인자 유무 무관)가 공통 호출하는 단일 chokepoint.
    """
    import shared.config as _cfg
    if not (str(_dialects.active().name).lower() == "mssql" and _cfg.get_active_datasource()):
        return None
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    hard = _INTERNAL_SCHEMAS | _dialects.active().system_databases()
    allow_set = ({str(a).strip().lower() for a in allow} if allow else set()) - hard
    pinned = (_cfg.get_active_default_db() or "")
    if not (pinned and pinned in allow_set):
        allowed_str = ", ".join(sorted(allow_set)) or "(없음)"
        return (
            f"오류: 현재 연결 데이터베이스('{pinned or '미지정'}')가 이 제품의 접근 허용 목록에 없어 "
            f"조회를 거부합니다. 허용된 DB: {allowed_str}."
        )
    return None


def _cfg_get_active_datasource():
    import shared.config as _cfg
    return _cfg.get_active_datasource()


# ══════════════════════════════════════════════════════════════════
#  OpenAI function calling 도구 스키마
# ══════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # execute_sql을 맨 앞에 배치 — LLM이 첫 번째 도구를 선호하는 경향을 활용.
    # 질문에 바로 답할 수 있는 SQL을 먼저 시도하도록 유도한다.
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "SELECT SQL을 실행하여 데이터를 조회한다. "
                "반드시 `schema`.`table` 형식을 사용한다. "
                "이 도구를 가장 먼저 사용하라 — 시스템 프롬프트의 KNOWN SCHEMAS 정보로 SQL을 즉시 작성할 수 있다. "
                "처음부터 가벼운 쿼리로 작성하라(필요 컬럼만·WHERE 한정·서버측 집계·표본은 LIMIT/TOP). 무거운 쿼리는 "
                "부하 게이트(MySQL EXPLAIN / MSSQL SHOWPLAN 사전 추정)에 걸려 실행되지 않으며 예상 행수가 반환된다 — "
                "그 경우 confirm_heavy 로 강행하지 말고 같은 목적을 달성하는 더 가벼운 쿼리로 재구성해 다시 호출하라."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "실행할 SELECT SQL",
                    },
                    "confirm_heavy": {
                        "type": "boolean",
                        "description": (
                            "최후수단. true 면 무거운 쿼리 부하 게이트를 우회해 그대로 실행한다. 먼저 더 가벼운 쿼리로 "
                            "재구성을 시도하고, 더 가벼운 형태로 목적 달성이 불가능한 전체 스캔이 반드시 필요할 때만 사용."
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": (
                "테이블의 컬럼명, 타입, 키, 인덱스를 반환한다. "
                "execute_sql이 컬럼 오류로 실패했을 때만 사용한다. "
                "동일 테이블에 대해 1회만 호출한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tables",
            "description": (
                "키워드로 테이블을 검색한다 (최후 수단). "
                "시스템 프롬프트의 KNOWN SCHEMAS에 관련 테이블이 이미 있으면 이 도구를 사용하지 않는다. "
                "같은 키워드로 2회 이상 호출하지 않는다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색 키워드",
                    },
                    "schema_name": {
                        "type": "string",
                        "description": "스키마 이름 (선택)",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sample_rows",
            "description": (
                "테이블의 샘플 데이터를 조회한다. "
                "컬럼 내용 형식(예: JSON 구조)을 확인해야 할 때만 사용한다. "
                "대부분의 경우 불필요하다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                    "limit": {"type": "integer", "description": "행 수 (기본 5)"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
]

# 전체 도구 정의 (list_schemas, describe_schema, explain_query 등 추가 도구 포함)
# 작은 모델에서는 TOOL_DEFINITIONS (핵심 4개)만 사용하고,
# 큰 모델에서는 TOOL_DEFINITIONS_FULL을 사용할 수 있다.
TOOL_DEFINITIONS_FULL: list[dict[str, Any]] = TOOL_DEFINITIONS + [
    {
        "type": "function",
        "function": {
            "name": "list_schemas",
            "description": "MySQL 사용자 스키마 목록을 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_schema",
            "description": "스키마의 모든 테이블 목록과 행 수를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                },
                "required": ["schema_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_query",
            "description": "SQL 실행 계획을 분석한다(본 쿼리는 실행하지 않음). MySQL=EXPLAIN, MSSQL=SET SHOWPLAN_ALL 추정 실행계획.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT SQL"},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_indexes",
            "description": "테이블 인덱스 정보를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_foreign_keys",
            "description": "테이블 외래키 관계를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
]


# ── 단계 narration 파라미터 (TASK-0178) ──────────────────────────────
# 실행 단계의 work(무엇을)/reason(왜)을 LLM 이 채우게 하는 표준 경로.
# content 동시 방출(TASK-0177)은 Bedrock gateway 가 tool_use 턴의 text content 를
# strip 해 무력했다(REV-20260610-0177 M2 라이브 확정). tool 호출 인자(arguments)는
# SQL 처럼 안정적으로 전달되므로, 모든 도구 스키마에 optional `reason`/`work` 를
# 주입해 모델이 호출 시 채우게 한다. agent_core 루프가 tool_args 에서 pop 해 step 에
# 기록하고, 실제 도구 실행에는 전달하지 않는다(핸들러는 named-get 이라 무해하지만 명시 pop).
# 미제공 시 _derive_step_reason/_derive_step_work fallback(TASK-0175)이 받는다.
_STEP_NARRATION_PARAMS: dict[str, dict[str, str]] = {
    "reason": {
        "type": "string",
        "description": (
            "이 도구를 호출하는 이유를 사용자의 질문·목표에 비추어 구체적으로 (한국어, 1~2문장). "
            "일반적 도구 설명이 아니라 '이번 질문에 왜 이 단계가 필요한지'. "
            "예: '월별 매출을 집계하려면 주문일자·금액 컬럼명을 먼저 확정해야 하므로'. "
            "모든 도구 호출에 채운다."
        ),
    },
    "work": {
        "type": "string",
        "description": "이 단계가 하는 일을 한 줄로 (한국어). 예: '`db`.`orders` 의 컬럼 구조를 확인'.",
    },
}


def _inject_step_narration_params(tool_defs: list[dict[str, Any]]) -> None:
    """모든 tool 정의의 parameters.properties 앞쪽에 reason/work 를 주입(think-first).
    TOOL_DEFINITIONS_FULL 은 TOOL_DEFINITIONS 의 dict 객체를 공유하므로 FULL 만
    순회해도 전체 8개 고유 도구가 1회씩 갱신된다. required 에는 추가하지 않는다(optional)."""
    for t in tool_defs:
        params = (t.get("function") or {}).get("parameters")
        if not isinstance(params, dict):
            continue
        props = params.get("properties")
        if not isinstance(props, dict):
            continue
        merged: dict[str, Any] = {}
        for key, schema in _STEP_NARRATION_PARAMS.items():
            if key not in props:
                merged[key] = dict(schema)
        merged.update(props)
        params["properties"] = merged


_inject_step_narration_params(TOOL_DEFINITIONS_FULL)


def build_tool_definitions_for_datasources(base_defs: list[dict[str, Any]], labels: list[str]) -> list[dict[str, Any]]:
    """TASK-0228 (1:N): 제품이 여러 datasource 에 바인딩됐을 때, 각 DB 도구에 `datasource` 선택 인자를
    주입한 **깊은 복사본** tool 정의를 만든다(원본 전역 정의 불변 — 단일 datasource run 영향 0).

    LLM 은 execute_sql/describe_table/... 호출 시 `datasource` 에 라벨을 넣어 대상을 고른다. 미지정 시
    런타임 라우터가 primary 로 폴백한다. enum 으로 바인딩된 라벨만 허용(잘못된 값 사전 차단)."""
    import copy
    if not labels or len(labels) < 2:
        return base_defs
    defs = copy.deepcopy(base_defs)
    ds_param = {
        "type": "string",
        "enum": list(labels),
        "description": (
            "조회 대상 데이터소스 라벨. 이 제품은 여러 데이터소스에 연결돼 있다 — "
            f"가능: {', '.join(labels)}. 미지정 시 기본(primary) 데이터소스를 사용한다. "
            "한 질문이 여러 데이터소스를 참조하면 도구를 데이터소스별로 나눠 호출하라."
        ),
    }
    for t in defs:
        params = (t.get("function") or {}).get("parameters")
        if not isinstance(params, dict):
            continue
        props = params.get("properties")
        if not isinstance(props, dict):
            continue
        if "datasource" not in props:
            # datasource 를 맨 앞에 배치(모델이 먼저 고르도록), required 에는 미추가(optional).
            params["properties"] = {"datasource": dict(ds_param), **props}
    return defs


# ══════════════════════════════════════════════════════════════════
#  도구 실행 함수
# ══════════════════════════════════════════════════════════════════

def _format_result_sets(result_sets: list, max_rows: int | None = None) -> str:
    """execute_sql 결과를 텍스트로 변환."""
    if max_rows is None:
        max_rows = AGENT_TOP_N
    parts: list[str] = []
    total_rows = 0
    for kind, col_or_count, rows in result_sets:
        if kind == "rows" and isinstance(rows, list):
            columns = col_or_count if isinstance(col_or_count, list) else []
            total_rows += len(rows)
            if columns:
                parts.append("| " + " | ".join(str(c) for c in columns) + " |")
                parts.append("|" + "|".join("---" for _ in columns) + "|")
            displayed = rows[:max_rows]
            for row in displayed:
                cells = []
                for v in row:
                    s = str(v) if v is not None else "NULL"
                    if len(s) > 100:
                        s = s[:100] + "..."
                    cells.append(s)
                parts.append("| " + " | ".join(cells) + " |")
            if len(rows) > max_rows:
                parts.append(f"\n... ({len(rows)} 행 중 {max_rows}행만 표시)")
            else:
                parts.append(f"\n({len(rows)} 행)")
        elif kind == "rowcount":
            parts.append(f"영향받은 행: {col_or_count}")
    return "\n".join(parts)


def _safe_ident(name: str) -> str:
    """SQL 식별자에서 위험 문자 제거 (구조화 도구의 식별자 인용 신뢰경계).

    구조화 도구(describe_*/sample/indexes/foreign_keys/search)는 schema/table 인자를 AST 게이트가
    아닌 본 함수로만 정제한 뒤 dialect SQL 에 f-string 삽입한다. 따라서 **모든 dialect 의 인용 구분자**
    를 제거해야 한다:
      - MySQL 백틱 `` ` ``, ANSI/MSSQL 큰따옴표 `"`, 문자열 리터럴 `'`, 문장분리 `;`
      - **MSSQL 대괄호 `[` `]`** (REV-0201 B1): MSSQL dialect 는 `[{schema}].[{table}]` 로 인용하는데
        `]` 를 안 지우면 `tbl] UNION SELECT ... --` 로 인용을 닫고 2차 SQLi 가 가능했다(라이브 실증).
        `]` 제거로 주입 토큰이 단일 식별자 안에 갇혀 무력화된다(존재하지 않는 객체명 → 에러).
    """
    return (
        name.replace("`", "").replace(";", "")
        .replace("'", "").replace('"', "")
        .replace("[", "").replace("]", "")
        .strip()
    )


def _tool_list_schemas(conn, _args: dict) -> str:
    # re-gate(3차) BLOCKER3: schema 인자 없는 구조화 도구도 pin 검증 — pin 무효 시 로그인 기본 DB 의
    # 스키마명을 열거하므로 fail-closed.
    pin_err = _mssql_pin_gate()
    if pin_err:
        return pin_err
    sql = _dialects.active().list_schemas_with_counts()
    result_sets, _ = _raw_execute_sql(conn, sql)
    # 시스템 스키마 필터링
    filtered: list[str] = []
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            filtered.append("| schema | tables | approx_rows |")
            filtered.append("|---|---|---|")
            for row in rows:
                schema_name = str(row[0])
                if not _is_user_schema(schema_name):
                    continue
                filtered.append(f"| {schema_name} | {row[1]} | {row[2]} |")
    return "\n".join(filtered) if filtered else "(사용자 스키마가 없습니다)"


def _tool_describe_schema(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    if not schema:
        return "오류: schema_name은 필수입니다."
    err = _struct_schema_access_error(schema)
    if err:
        return err
    sql = _dialects.active().describe_schema_tables(schema)
    result_sets, _ = _raw_execute_sql(conn, sql)
    parts = [f"## 스키마: {schema}\n"]
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            parts.append("| table | approx_rows | engine | comment |")
            parts.append("|---|---|---|---|")
            for row in rows:
                comment = str(row[3] or "")[:40]
                parts.append(f"| {row[0]} | {row[1]} | {row[2]} | {comment} |")
            parts.append(f"\n총 {len(rows)} 테이블")
        elif kind == "rows":
            parts.append(f"스키마 '{schema}'에 테이블이 없거나 스키마가 존재하지 않습니다.")
    return "\n".join(parts)


def _tool_describe_table(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    err = _struct_schema_access_error(schema)
    if err:
        return err

    # 컬럼 정보
    col_sql = _dialects.active().describe_columns(schema, table)
    col_results, _ = _raw_execute_sql(conn, col_sql)

    # 인덱스 정보
    idx_sql = _dialects.active().list_indexes(schema, table)
    try:
        idx_results, _ = _raw_execute_sql(conn, idx_sql)
    except Exception:
        idx_results = []

    # ITEM-11 Phase 2 (오버레이 A): native COLUMN_COMMENT 가 빈 컬럼을 KB(column_descriptions)
    # 설명으로 채운다. MSSQL describe_columns 는 row[6]='' 하드코딩(dialects.py) → comment gap
    # 해소가 목적. PG 읽기 실패는 graceful({}) — 기존 출력 그대로 유지. scope=활성 datasource.
    kb_col_desc: dict = {}
    try:
        from shared import config as _cfg
        from modules.kb_metadata import load_column_descriptions_for_table
        # 오버레이 조회 키는 부트스트랩 저장 규약(metadata-table-desc-fix)과 일치시킨다:
        #   - MySQL: schema_name == database == 도구 schema 인자(그대로).
        #   - MSSQL: 부트스트랩이 schema_name=database(pin 된 primary DB) 로 저장하므로, SQL 스키마
        #     (dbo 등 도구 schema 인자)가 아니라 **현재 연결 DB 명**(get_active_default_db)으로 조회해야
        #     적중한다(이전엔 'dbo' vs 'GunzGame' 축 불일치로 부트스트랩 컬럼 설명이 영영 미주입).
        overlay_schema = schema
        if str(_dialects.active().name).lower() == "mssql":
            overlay_schema = (_cfg.get_active_default_db() or schema)
        kb_col_desc = load_column_descriptions_for_table(
            overlay_schema, table, scope_key=_cfg.get_active_datasource()
        )
    except Exception:
        kb_col_desc = {}

    parts = [f"## `{schema}`.`{table}` 구조\n"]
    parts.append("### 컬럼")
    parts.append("| column | type | nullable | key | default | extra | comment |")
    parts.append("|---|---|---|---|---|---|---|")
    for kind, cols, rows in col_results:
        if kind == "rows" and rows:
            for row in rows:
                default_val = str(row[4]) if row[4] is not None else ""
                comment = str(row[6] or "").strip()
                if not comment:
                    # native comment 가 빈 경우에만 KB 설명으로 채운다(native 우선).
                    comment = str(kb_col_desc.get(str(row[0]).strip(), "") or "")
                comment = comment[:30]
                parts.append(
                    f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | "
                    f"{default_val} | {row[5]} | {comment} |"
                )

    if idx_results:
        parts.append("\n### 인덱스")
        parts.append("| index_name | non_unique | column | seq | cardinality |")
        parts.append("|---|---|---|---|---|")
        for kind, cols, rows in idx_results:
            if kind == "rows" and rows:
                for row in rows:
                    parts.append(
                        f"| {row[2]} | {row[1]} | {row[4]} | {row[3]} | {row[6]} |"
                    )

    # TEXT/JSON 컬럼이 있으면 자동으로 1행 샘플 추가 (JSON 구조 파악용)
    has_complex = False
    for kind, cols, rows in col_results:
        if kind == "rows" and rows:
            for row in rows:
                col_type = str(row[1]).lower()
                if any(t in col_type for t in ("text", "json", "blob", "longtext", "mediumtext")):
                    has_complex = True
                    break
    if has_complex:
        try:
            sample_sql = _dialects.active().sample(schema, table, 1)
            sample_results, _ = _raw_execute_sql(conn, sample_sql)
            sample_text = _format_result_sets(sample_results, max_rows=1)
            if sample_text:
                parts.append("\n### 샘플 데이터 (1행)")
                parts.append(sample_text)
        except Exception:
            pass

    return "\n".join(parts)


def _tool_search_tables(conn, args: dict) -> str:
    keyword = _safe_ident(args.get("keyword", ""))
    schema_filter = _safe_ident(args.get("schema_name", ""))
    if not keyword:
        return "오류: keyword는 필수입니다."
    # re-gate(3차) BLOCKER3: schema_filter 없이도 pin 된 DB 전체 테이블명을 열거하므로 pin 검증(무조건).
    pin_err = _mssql_pin_gate()
    if pin_err:
        return pin_err
    if schema_filter:
        err = _struct_schema_access_error(schema_filter)
        if err:
            return err

    where_schema = f"AND t.TABLE_SCHEMA = '{schema_filter}'" if schema_filter else ""
    # 시스템 스키마 제외 조건 (P6: dialect 별 시스템 스키마 — MSSQL 은 sys/guest/db_* 제외).
    sys_exclude = " AND ".join(
        f"t.TABLE_SCHEMA != '{s}'" for s in sorted(_excluded_schemas())
    )

    sql = _dialects.active().search_tables(keyword, sys_exclude, where_schema)
    result_sets, _ = _raw_execute_sql(conn, sql)

    # 사용 가능한 전체 스키마 목록 조회
    all_schemas: list[str] = []
    try:
        schema_sql = _dialects.active().list_schema_names()
        schema_rs, _ = _raw_execute_sql(conn, schema_sql)
        for kind, _, rows in schema_rs:
            if kind == "rows" and rows:
                all_schemas = [str(r[0]) for r in rows if _is_user_schema(str(r[0]))]
    except Exception:
        pass

    parts = [f"## '{keyword}' 검색 결과\n"]
    found_schemas: set[str] = set()
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            parts.append("| schema | table | approx_rows | comment |")
            parts.append("|---|---|---|---|")
            for row in rows:
                comment = str(row[3] or "")[:40]
                parts.append(f"| {row[0]} | {row[1]} | {row[2]} | {comment} |")
                found_schemas.add(str(row[0]))
            parts.append(f"\n{len(rows)} 테이블 검색됨")
        elif kind == "rows":
            parts.append("검색 결과가 없습니다.")

    # 검색되지 않은 스키마 안내
    if all_schemas and not schema_filter:
        missed = sorted(set(all_schemas) - found_schemas)
        if missed:
            parts.append(f"\n(참고: {', '.join(missed)} 스키마에는 '{keyword}' 매칭 테이블 없음)")
    return "\n".join(parts)


def _tool_get_sample_rows(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    limit = min(max(1, int(args.get("limit", 5))), 20)
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    err = _struct_schema_access_error(schema)
    if err:
        return err
    sql = _dialects.active().sample(schema, table, limit)
    try:
        result_sets, elapsed = _raw_execute_sql(conn, sql)
        formatted = _format_result_sets(result_sets, max_rows=limit)
        # 바이너리 컬럼 감지 → 파싱 힌트 추가
        if "b'" in formatted or "b\"" in formatted or "\\x" in formatted:
            formatted += (
                "\n\n(NOTE: Binary columns detected. To parse binary flags, use: "
                "((ORD(SUBSTRING(binary_col, FLOOR(bit_index/8)+1, 1)) >> (bit_index % 8)) & 1) "
                "where bit_index is the item's order/position.)"
            )
        return formatted
    except Exception as e:
        return f"오류: {e}"


_TOOL_PREVIEW_ROWS = 50


def _estimate_explain_rows(conn, sql: str) -> int | None:
    """엔진별 사전 부하추정 — 본 쿼리를 실행하지 않고 예상 처리 행수를 산출.

    MySQL: EXPLAIN 의 (rows × filtered/100) 곱 = join 후 예상 카디널리티.
    MSSQL: SET SHOWPLAN_ALL 의 (EstimateRows × EstimateExecutions) 최대 operator (TASK-0299).

    엔진별 산출/파싱은 dialect 가 담당하고 tools 는 실행 콜백(_run)만 주입한다(계층 보존 —
    dialects 가 db/tools 를 import 하지 않음). EXPLAIN/SHOWPLAN 모두 본 쿼리를 실행하지 않으므로
    cheap (EXPLAIN ANALYZE 류 실행형은 sql_guard 가 차단). 실패 시 None → caller 가 엔진별
    fail-open(MySQL 골든) / fail-closed(MSSQL gate, `gate_fail_closed_on_estimate_error`) 분기.

    TASK-0172(MySQL 도입) → TASK-0299(MSSQL SHOWPLAN 확장)."""
    dialect = _dialects.active()
    if not dialect.supports_load_estimate:
        return None

    def _run(stmt: str):
        result_sets, _ = _raw_execute_sql(conn, stmt)
        return result_sets

    return dialect.estimate_load_rows(_run, sql)


def _apply_query_cap(conn) -> None:
    """시간 상한(MAX_EXECUTION_TIME, ms)을 **세션 스코프**로 적용(SELECT 한정 효력).
    conn 은 run 전체 공유라 한 번 SET 하면 그 conn 의 이후 SELECT(스키마 탐색 도구 포함)
    에도 sticky 하게 적용된다 — generous 기본이라 빠른 도구엔 무해, 폭주만 차단. 매 호출
    재-SET 은 idempotent. 0/비활성이면 no-op, 실패 시 fail-open. "무거운 쿼리는 감수"
    정책상 기본 generous/off."""
    import shared.config as _cfg
    ms = int(getattr(_cfg, "AGENT_QUERY_MAX_EXECUTION_MS", 0) or 0)
    if ms <= 0:
        return
    try:
        cur = conn.cursor()
        try:
            cur.execute(f"SET SESSION max_execution_time = {int(ms)}")
        finally:
            cur.close()
    except Exception:
        pass


def _dialect_correction_hint(sql: str) -> str:
    """gc-assistant-dialect-context (RC-1): 거부된 SQL 의 방언 오용을 활성 엔진 기준으로 교정 안내.

    활성 datasource 엔진(mysql|mssql)을 명시하고, 반대 엔진의 흔한 마커(TOP/[..]/UNION/CONVERT 등)가
    SQL 에 보이면 올바른 형태를 짚어 준다. LLM 이 같은 dialect 로 맹목 재시도하는 thrashing 을 끊는다.
    """
    try:
        eng = str(_dialects.active().name).lower()
    except Exception:
        eng = "mysql"
    s = (sql or "")
    su = s.upper()
    tips: list[str] = []
    if eng == "mysql":
        if "[" in s and "]" in s:
            tips.append("식별자는 `[브래킷]` 이 아니라 백틱 `` `db`.`table` `` 또는 평문 db.table 을 쓰세요")
        if " TOP " in (" " + su + " ") or su.startswith("SELECT TOP"):
            tips.append("`SELECT TOP n` 대신 `... LIMIT n` 을 쓰세요")
        if "UNION" in su:
            tips.append("최상위 `UNION`/`UNION ALL` 은 허용되지 않습니다 — 쿼리를 나누거나 `SUM(CASE WHEN …)` 조건집계로 합치세요")
        if "CONVERT(" in su or "DATEADD" in su or "GETDATE(" in su:
            tips.append("날짜/형변환은 T-SQL `CONVERT/DATEADD/GETDATE` 가 아니라 MySQL `DATE_FORMAT/DATE_ADD/CAST(x AS DATE)/NOW()` 를 쓰세요")
        if "ISNULL(" in su:
            tips.append("`ISNULL(x, y)`(2-인자 T-SQL) 대신 MySQL `IFNULL(x, y)` 또는 `COALESCE(x, y)` 를 쓰세요")
        head = "이 데이터소스는 **MySQL** 입니다 — MySQL 문법으로 작성하세요."
    elif eng == "mssql":
        if "`" in s:
            tips.append("식별자는 백틱이 아니라 `[schema].[table]` 또는 평문 schema.table 을 쓰세요")
        if " LIMIT " in (" " + su + " "):
            tips.append("`LIMIT n` 대신 `SELECT TOP n ...` 또는 `OFFSET … FETCH` 를 쓰세요")
        if "DATE_FORMAT" in su or "DATE_ADD" in su or "DATE_SUB" in su or "NOW(" in su:
            tips.append("날짜 함수는 MySQL 형이 아니라 T-SQL `CONVERT/FORMAT/DATEADD/GETDATE()` 를 쓰세요")
        head = "이 데이터소스는 **SQL Server(T-SQL)** 입니다 — T-SQL 문법으로 작성하세요."
    else:
        return ""
    if tips:
        return head + " " + " / ".join(tips) + "."
    return head


def _tool_execute_sql(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    # TASK-0128 (#2): LLM 작성 SQL 신뢰경계 — 이전엔 uppercase prefix denylist 뿐이라
    # `/* */ DELETE`, 탭 우회, `SELECT 1; DELETE ...` 다중문, INSERT/UPDATE 가 모두 통과했다.
    # sqlglot AST 가드로 교체: 단일 SELECT/CTE only, 다중문·write verb·lock·INTO·금지함수·
    # 금지스키마(agent_memory 등) reject. (스키마 탐색은 별도 구조화 도구가 담당 — 본 도구는
    # LLM freeform 분석 SELECT 전용.)
    from .sql_guard import validate_sql_for_sandbox
    # agent 는 카탈로그(information_schema/sys 등) 조회가 필요하므로 내부 스키마(agent_memory)만 금지.
    # P6: 활성 dialect(mysql|tsql) 를 주입 — denylist 어휘·파서·금지함수가 엔진별로 적용된다.
    guard = validate_sql_for_sandbox(
        sql, forbidden_schemas=_INTERNAL_SCHEMAS, dialect=_dialects.active().sqlglot
    )
    if not guard.ok:
        # gc-assistant-dialect-context (RC-1): 거부 사유에 **엔진 인지형 방언 교정 힌트**를 덧붙인다.
        # 라이브(group conv 20260625…)에서 LLM 이 MySQL datasource 에 T-SQL(`TOP`/`UNION`/`[..]`/
        # `CONVERT`)을 생성→거부될 때, 단순 "차단됨"만 돌려주면 같은 dialect 로 재시도하며 thrashing 했다.
        # 거부 메시지에 "이 datasource 는 <엔진> 이니 <올바른 형태>" 를 명시해 self-correct 를 유도한다.
        return (
            f"오류: 보안 정책상 차단된 SQL — {guard.error_reason}. "
            f"execute_sql 은 단일 SELECT/CTE 분석 쿼리만 허용됩니다 "
            f"(스키마 구조 탐색은 list_schemas/describe_table 등 전용 도구 사용). "
            f"{_dialect_correction_hint(sql)}"
        )
    # Product 단위 스키마 allowlist (교차 product 격리) — P6: AST 추출 + 무자격/cross-DB 정책.
    err = _freeform_sql_access_error(sql)
    if err:
        return err
    # TASK-0172/0298: 무거운 쿼리 자가규제 — 실행 전 사전 부하추정(MySQL EXPLAIN / MSSQL SHOWPLAN)으로
    # 예상 처리 행수를 구해 임계 초과 시 gate(좁히기 유도) 또는 warn(비용 경고 prepend). confirm_heavy=true 면
    # 추정 무관 실행("무거운 쿼리는 감수" — LLM 이 필요 판단 시 override). guard off=현행.
    import shared.config as _cfg
    guard_mode = str(getattr(_cfg, "AGENT_QUERY_GUARD_MODE", "off") or "off").lower()
    # diff review M1: bool(args.get(...)) 은 LLM 이 문자열 "false" 를 보내면 truthy → 게이트
    # 우회. true/1/yes(대소문자) 또는 bool True 만 confirm 으로 인정.
    _cv = args.get("confirm_heavy")
    confirm_heavy = (_cv is True) or (
        isinstance(_cv, str) and _cv.strip().lower() in ("true", "1", "yes")
    )
    # P6 Codex-6: confirm_heavy 는 LLM tool 인자라 모델이 자기우회한다. 정책이 비-LLM 승인을 요구하면
    # (AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM=false) LLM 의 confirm 을 무시한다(사용자/정책 승인 경로는
    # P7 UI 승인 라운드트립으로 이월 — 그 전엔 hardened 모드에서 무거운 쿼리가 차단됨). 기본 true=현행.
    # config 가 bool 로 파싱하므로 bool 로 읽는다(`or` 폴백 금지 — False 가 truthy 로 되돌아감).
    if not bool(getattr(_cfg, "AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM", True)):
        confirm_heavy = False
    cost_note: str | None = None
    # 사전 부하추정 자체가 불가한 엔진(supports_load_estimate=False)은 gate 모드에서 confirm_heavy 와
    # 무관하게 **하드 차단**한다(추정치 없이 "감수" 판단은 근거 없는 맹목 우회 — Codex-6). gate 는 opt-in
    # (기본 off)이며 운영자가 최대보호를 택한 것 — 정상 쿼리를 원하면 gate off/warn 으로 둔다(P7 사용자 승인 경로).
    # MSSQL 은 TASK-0299 부터 SHOWPLAN 으로 추정 지원(=True) → 본 분기 미해당(미래 엔진 방어용). MSSQL 의
    # *추정 실패* fail-closed 는 아래 est is None 분기(gate_fail_closed_on_estimate_error)가 담당한다.
    _dialect = _dialects.active()
    if guard_mode == "gate" and not _dialect.supports_load_estimate:
        return (
            "⚠ 이 데이터소스 엔진은 사전 부하추정을 지원하지 않아, 부하게이트(gate) 모드에서 "
            "무거운 쿼리를 사전 차단합니다(fail-closed). WHERE 조건·기간·집계 범위를 좁히거나 TOP/행 "
            "제한을 추가해 더 작은 쿼리로 다시 시도하세요."
        )
    if guard_mode in ("warn", "gate"):
        # confirm_heavy=true 면 추정 생략(근거 있는 override)이 기본 — EXPLAIN/SHOWPLAN 오버헤드 0.
        # 단 fail-closed 엔진(MSSQL)은 추정 *실패* 시 confirm_heavy 로도 우회 불가해야 하므로
        # (M-4/Codex-6 — 추정치 없는 맹목 confirm 은 근거 없는 자기우회) 추정을 강제 수행해, None 이면
        # confirm 여부와 무관하게 차단한다. 추정이 성공한 known-heavy 는 근거가 있으므로 confirm override 허용.
        must_estimate = (not confirm_heavy) or (
            guard_mode == "gate" and _dialect.gate_fail_closed_on_estimate_error
        )
        if must_estimate:
            est = _estimate_explain_rows(conn, sql)
            warn_thr = int(getattr(_cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1000000) or 1000000)
            if est is None:
                # 추정 실패. MySQL=fail-open(골든 — EXPLAIN 실패는 드물고 정상 작업 비차단).
                # MSSQL gate=fail-closed(M-4 — SHOWPLAN 미권한/연결 실패 시 무거운 쿼리 무방어 방지).
                # confirm_heavy 로도 우회 불가(must_estimate 가 confirm 시에도 True 라 이 분기 진입).
                if guard_mode == "gate" and _dialect.gate_fail_closed_on_estimate_error:
                    return (
                        "⚠ 사전 부하추정에 실패했습니다 (실행계획 미취득 — SHOWPLAN 권한·연결 확인). "
                        "부하게이트(gate) 모드에서 안전을 위해 차단합니다. WHERE 조건·기간·집계 범위를 좁히거나 "
                        "TOP/행 제한을 추가해 더 작은 쿼리로 다시 시도하세요."
                    )
            elif est > warn_thr and not confirm_heavy:
                # 무거운 쿼리(추정치 보유). gate=실행 전 가로채고 LLM 이 더 가벼운 쿼리로 재작성하도록
                # 코칭(차단이 목적이 아니라 부하 절감 — TASK-0304). confirm_heavy 는 최후수단으로 후순위.
                if guard_mode == "gate":
                    return (
                        f"⚠ 무거운 쿼리로 추정됩니다 (예상 처리 ~{est:,}행 > 임계 {warn_thr:,}행) — 실행하지 않았습니다. "
                        f"같은 목적을 유지하면서 DB 부하가 더 적은 쿼리로 재구성해 다시 실행하세요: 필요한 컬럼만 SELECT, "
                        f"WHERE 로 대상 한정(id/상태/기간), 서버측 집계(COUNT/SUM/GROUP BY), 표본은 LIMIT/TOP n. "
                        f"더 가벼운 형태로 목적 달성이 정말 불가능한 전체 스캔 한정으로만, 최후수단으로 같은 쿼리를 "
                        f"confirm_heavy=true 로 호출하면 실행합니다."
                    )
                cost_note = (
                    f"⚠ 무거운 쿼리 (예상 처리 ~{est:,}행). 가능하면 다음엔 범위를 좁히세요."
                )
    # per-query 시간 cap(폭주 backstop) 적용 — generous/off 기본.
    _apply_query_cap(conn)
    try:
        result_sets, elapsed = _raw_execute_sql(conn, sql)
        csv_paths: list[str] = []
        total_row_count = 0
        for idx, (kind, columns, rows) in enumerate(result_sets, start=1):
            if kind != "rows" or not isinstance(columns, list):
                continue
            total_row_count += len(rows) if isinstance(rows, list) else 0
            csv_rows = []
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, (list, tuple)):
                        csv_rows.append(list(row))
                    else:
                        csv_rows.append([row])
            csv_paths.append(save_csv(f"resultset{idx}", [str(col) for col in columns], csv_rows))
        # LLM에게 미리보기(최대 5행)만 전달, 전체 결과는 CSV 참조
        preview = _format_result_sets(result_sets, max_rows=_TOOL_PREVIEW_ROWS)
        parts: list[str] = [preview] if preview else []
        if csv_paths:
            for path in csv_paths:
                parts.append(f"CSV 저장: {path}")
            if total_row_count > _TOOL_PREVIEW_ROWS:
                parts.append(
                    f"(전체 {total_row_count}행 — 위 표는 미리보기 {_TOOL_PREVIEW_ROWS}행입니다. "
                    f"답변에 전체 표를 삽입하지 말고, CSV 다운로드 링크를 제공하세요.)"
                )
        parts.append(f"(실행 시간: {elapsed:.2f}초)")
        if cost_note:
            parts.insert(0, cost_note)
        return "\n\n".join(parts)
    except Exception as e:
        return f"SQL 실행 오류: {e}"


def _format_mssql_showplan(result_sets) -> str:
    """SET SHOWPLAN_ALL 결과를 사람이 읽기 쉽게 요약 — 핵심 컬럼(연산자·예상행·비용)만.

    SHOWPLAN_ALL 은 18 컬럼이라 그대로 표시하면 노이즈가 크다. StmtText(연산자 트리)/PhysicalOp/
    EstimateRows/EstimateExecutions/TotalSubtreeCost 만 투영하고, 예상 처리 행수(최대 operator)와
    총 추정 비용(첫 행=statement root 의 TotalSubtreeCost)을 요약 라인으로 덧붙인다."""
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).strip().lower() for c in columns]  # m2: 컬럼명 패딩 견고화
        if "estimaterows" not in lcols:
            continue

        def _idx(name):
            return lcols.index(name) if name in lcols else None

        i_stmt, i_op = _idx("stmttext"), _idx("physicalop")
        i_rows, i_exec, i_cost = _idx("estimaterows"), _idx("estimateexecutions"), _idx("totalsubtreecost")
        out_cols = ["StmtText", "PhysicalOp", "EstimateRows", "EstimateExecutions", "TotalSubtreeCost"]
        out_rows: list = []
        max_eff: int | None = None
        root_cost: float | None = None
        for r in rows:
            def _get(i):
                try:
                    return r[i] if i is not None else ""
                except (IndexError, TypeError):
                    return ""
            er, ex, cost = _get(i_rows), _get(i_exec), _get(i_cost)
            out_rows.append([str(_get(i_stmt)).strip()[:80], str(_get(i_op)).strip(), er, ex, cost])
            try:
                exf = float(ex) if ex not in ("", None) else 1.0
                eff = int(round(float(er) * (exf if exf >= 1.0 else 1.0)))
                if max_eff is None or eff > max_eff:
                    max_eff = eff
            except (ValueError, TypeError):
                pass
            if root_cost is None:
                try:
                    root_cost = float(cost)
                except (ValueError, TypeError):
                    pass
        parts = ["추정 실행계획 (SET SHOWPLAN_ALL — 본 쿼리는 실행되지 않음):",
                 _format_result_sets([("rows", out_cols, out_rows)])]
        summary = []
        if max_eff is not None:
            summary.append(f"예상 처리 행수(최대 operator): ~{max_eff:,}행")
        if root_cost is not None:
            summary.append(f"총 추정 비용(TotalSubtreeCost): {root_cost:.4f}")
        if summary:
            parts.append(" · ".join(summary))
        return "\n\n".join(parts)
    return "실행계획을 취득했으나 예상 행수 컬럼(EstimateRows)을 찾지 못했습니다 (SHOWPLAN 형식 확인)."


def _tool_explain_query(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    # P6: AST 추출 + 무자격/cross-DB + allowlist (execute_sql 과 동일 신뢰경계).
    err = _freeform_sql_access_error(sql)
    if err:
        return err
    dialect = _dialects.active()

    def _run(stmt: str):
        result_sets, _ = _raw_execute_sql(conn, stmt)
        return result_sets

    # 엔진별 실행계획 — MySQL=EXPLAIN, MSSQL=SET SHOWPLAN_ALL (둘 다 본 쿼리 미실행, TASK-0299).
    try:
        result_sets = dialect.explain_plan(_run, sql)
    except Exception as e:
        return f"실행계획 조회 오류: {e}"
    if result_sets is None:
        return "이 데이터소스 엔진은 실행계획(EXPLAIN/SHOWPLAN) 조회를 지원하지 않습니다."
    if str(dialect.name).lower() == "mssql":
        return _format_mssql_showplan(result_sets)
    return _format_result_sets(result_sets)


def _tool_get_table_indexes(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    err = _struct_schema_access_error(schema)
    if err:
        return err
    sql = _dialects.active().table_indexes(schema, table)  # P6: dialect 별 인덱스 조회
    try:
        result_sets, _ = _raw_execute_sql(conn, sql)
        return _format_result_sets(result_sets)
    except Exception as e:
        return f"인덱스 조회 오류: {e}"


def _tool_get_foreign_keys(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    err = _struct_schema_access_error(schema)
    if err:
        return err

    # P6: dialect 별 외래키 조회 (MySQL=information_schema, MSSQL=sys.foreign_keys)
    outgoing_sql = _dialects.active().foreign_keys_outgoing(schema, table)  # 이 테이블이 참조하는 FK
    incoming_sql = _dialects.active().foreign_keys_incoming(schema, table)  # 이 테이블을 참조하는 FK
    parts = [f"## `{schema}`.`{table}` 외래키\n"]

    try:
        out_results, _ = _raw_execute_sql(conn, outgoing_sql)
        parts.append("### 참조하는 테이블 (outgoing)")
        parts.append(_format_result_sets(out_results))
    except Exception as e:
        parts.append(f"outgoing 외래키 조회 오류: {e}")

    try:
        in_results, _ = _raw_execute_sql(conn, incoming_sql)
        parts.append("\n### 참조되는 테이블 (incoming)")
        parts.append(_format_result_sets(in_results))
    except Exception as e:
        parts.append(f"incoming 외래키 조회 오류: {e}")

    return "\n".join(parts)


# ── 도구 디스패처 ────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "list_schemas": _tool_list_schemas,
    "describe_schema": _tool_describe_schema,
    "describe_table": _tool_describe_table,
    "search_tables": _tool_search_tables,
    "get_sample_rows": _tool_get_sample_rows,
    "execute_sql": _tool_execute_sql,
    "explain_query": _tool_explain_query,
    "get_table_indexes": _tool_get_table_indexes,
    "get_foreign_keys": _tool_get_foreign_keys,
}


def execute_tool(conn, tool_name: str, arguments: dict[str, Any]) -> str:
    """도구를 실행하고 결과 문자열을 반환한다.

    TASK-0228 (1:N): 멀티 datasource 라우터가 활성이면, tool 인자 `datasource`(라벨)로 대상 datasource 를
    선택해 **그 datasource 의 연결·allowlist·engine** 으로 실행한다. 인자 미지정이면 primary 로 폴백.
    단일 바인딩(라우터 None)이면 종전과 동일하게 인자로 받은 conn 으로 실행(동작 0 변경).
    """
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"알 수 없는 도구: {tool_name}"
    router = _ACTIVE_DS_ROUTER.get()
    if router is not None:
        # 라우터 활성 — datasource 선택 + 그 컨텍스트 활성화. 작업 후 primary 로 복원(다음 tool 기본값 안정).
        import shared.config as _cfg
        requested = ""
        if isinstance(arguments, dict):
            requested = str(arguments.pop("datasource", "") or "").strip()
        label = router.resolve_label(requested)
        # 사용자가 미바인딩 라벨을 명시했으면 명확히 거부(엉뚱한 datasource 로 silent 라우팅 차단).
        if requested and requested.strip().lower() not in router.labels():
            return (
                f"오류: '{requested}' 는 이 제품에 바인딩된 데이터소스가 아닙니다. "
                f"사용 가능: {', '.join(router.labels())}."
            )
        try:
            ds_conn = router.conn_for(label)
        except DatasourceCircuitOpen as e:
            # 회로차단(연결 격리)은 일시 지연·자동복구 — "연결 실패" 프레이밍 회피(신뢰 보호,
            # 보고 2026-06-25). label 접두어도 생략하고 안내형 문구만 LLM/사용자에게 전달.
            return e.user_message()
        except Exception as e:
            return f"데이터소스 '{label}' 연결 실패: {e}"
        if ds_conn is None:
            return f"데이터소스 '{label}' 를 사용할 수 없습니다."
        router.activate(label)
        try:
            return handler(ds_conn, arguments)
        except Exception as e:
            return f"도구 실행 오류 ({tool_name} @ {label}): {e}"
        finally:
            # 다음 tool 호출의 기본값이 흔들리지 않도록 primary 컨텍스트로 복원.
            router.activate(router.resolve_label(None))
    try:
        return handler(conn, arguments)
    except Exception as e:
        return f"도구 실행 오류 ({tool_name}): {e}"
