"""스케줄러(예약 작업) 조회 경로의 **도달 가능성** 회귀 잠금 — conversation_audit 봉인.

라이브에서 관측된 실패는 "도구가 없다" 가 아니었다. `search_db_objects(object_role='schedule')`
는 이미 배포돼 있었고 실제 datasource 에서 대상 작업을 정확히 반환했다. 그런데도 모델은 그
도구를 한 번도 부르지 않고 `msdb` 직접 조회 → 차단 → 6분간 카탈로그 청킹 brute-force 후
"영구 차단이라 확인 불가" 로 단정했다. 사용자는 3턴에 걸쳐 같은 것을 요청했고 목표는 미달성됐다.

원인은 두 겹이고, 이 스위트는 그 둘이 되살아나지 못하게 잠근다:

1. **차단이 대안을 지목하지 않는다.** 거부 메시지의 도구 목록이 도구 카탈로그와 분리돼 있어,
   feature-0040 이 발견 도구를 둘 늘렸는데 안내는 옛 4개에 고정돼 있었다(drift). 안내를
   `_DISCOVERY_TOOL_NAMES` 한 곳에서 파생시키고, **카탈로그와 어긋나면 테스트가 깨지게** 한다.
2. **도구를 불러도 본문에 도달하지 못한다.** 작업명은 식별자가 아니라 `sysjobs.name` 의 임의
   문자열인데 식별자 정제기를 태워 `[DK] Ranking Update` → `DK Ranking Update` 로 훼손됐다.
   관측 서버는 작업 83개 중 73개(88%)가 `[` 접두라 사실상 전량 조회 불가였다.

동시에 **보안 경계 불변**을 함께 잠근다 — `_safe_ident` 의 인용 구분자 제거(REV-0201 B1 의
라이브 SQLi 실증 근거)는 그대로여야 하고, 리터럴 경로는 삽입 지점 이중화로 탈출을 막는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from modules import dialects as _dialects             # noqa: E402
from modules import tools as _tools                   # noqa: E402


# ══════════════════════════════════════════════════════════════════════
#  (1) 거부 피드백이 대안 도구를 지목하는가 — drift 봉인
# ══════════════════════════════════════════════════════════════════════

def test_discovery_hint_covers_every_discovery_tool_in_catalog():
    """안내 목록 == 카탈로그의 발견 도구 집합.

    이 단언이 깨지는 유일한 경우는 **새 `search_*`/`describe_*` 도구가 추가됐는데 거부 안내를
    갱신하지 않은 것**이다 — 정확히 이번 마찰을 만든 drift 다. 실패하면 도구를 지우지 말고
    `_DISCOVERY_TOOL_NAMES` 에 새 이름을 넣어라.
    """
    # 기준은 **상시 노출 세트**(`TOOL_DEFINITIONS`)다. `TOOL_DEFINITIONS_FULL` 에만 있는 확장
    # 도구를 안내하면 모델이 호출할 수 없는 이름을 권하게 돼 새 마찰이 된다 — 안내의 목적은
    # "지금 이 자리에서 쓸 수 있는 대안" 을 주는 것이다.
    catalog = {d["function"]["name"] for d in _tools.TOOL_DEFINITIONS
               if d["function"]["name"].startswith(("search_", "describe_"))}
    assert set(_tools._DISCOVERY_TOOL_NAMES) == catalog, (
        "거부 안내가 도구 카탈로그와 어긋났다 — 모델은 안내에 없는 도구를 대안으로 떠올리지 못한다"
    )
    hint = _tools._discovery_tools_hint()
    for name in catalog:
        assert name in hint


def test_discovery_hint_never_advertises_unexposed_tools():
    """확장 세트 전용 도구는 안내에 들어가면 안 된다 — 부를 수 없는 이름을 권하는 셈."""
    exposed = {d["function"]["name"] for d in _tools.TOOL_DEFINITIONS}
    for name in _tools._DISCOVERY_TOOL_NAMES:
        assert name in exposed, f"{name} 은 상시 노출 세트에 없다"


def test_sys_schema_block_message_is_derived_from_catalog(monkeypatch):
    """`sys` 차단 **메시지 자체**가 카탈로그 파생 안내를 담아야 한다.

    헬퍼만 검사하면 메시지가 옛 하드코딩으로 되돌아가도 통과하는 항진명제가 된다(자체 적대
    검토에서 적발). 그래서 실제 거부 경로를 태워 문자열을 확인한다.
    """
    import shared.config as _cfg
    monkeypatch.setattr(_dialects, "active", lambda: _dialects.MSSQLDialect())
    monkeypatch.setattr(_cfg, "get_active_datasource",
                        lambda: {"key": "x", "default_db": "db1"}, raising=False)
    monkeypatch.setattr(_cfg, "get_active_default_db", lambda: "db1", raising=False)
    tok = _tools._ACTIVE_SCHEMA_ALLOWLIST.set({"db1"})
    tok_d = _tools._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.set(["db1"])
    try:
        # 라이브에서 실제로 차단된 형태(3-part `<허용DB>.sys.<카탈로그뷰>`) — allowlist 게이트를
        # 통과한 뒤 sys 게이트에 도달해야 이 메시지가 나온다.
        out = _tools._freeform_sql_access_error("SELECT name FROM db1.sys.all_columns")
    finally:
        _tools._ACTIVE_SCHEMA_ALLOWLIST.reset(tok)
        _tools._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.reset(tok_d)
    assert out and "시스템 스키마" in out
    for name in _tools._DISCOVERY_TOOL_NAMES:
        assert name in out, f"차단 안내가 {name} 을 지목하지 않는다"


def test_msdb_hard_block_points_to_schedule_tools(monkeypatch):
    """시스템 DB 하드 차단이 **예약 작업의 정당한 경로**를 함께 알려야 한다.

    차단 자체는 불변(보안). 늘어나는 것은 안내뿐이며, 그 안내가 없으면 모델은 "확인 불가" 로
    단정한다 — 라이브에서 실제로 그렇게 끝났다.
    """
    import shared.config as _cfg
    monkeypatch.setattr(_dialects, "active", lambda: _dialects.MSSQLDialect())
    monkeypatch.setattr(_cfg, "get_active_datasource", lambda: {"key": "x"}, raising=False)
    out = _tools._freeform_sql_access_error("SELECT TOP 1 name FROM msdb.dbo.sysjobs")
    assert out and "msdb" in out
    assert "영구 차단" in out                       # 차단은 유지
    assert "search_db_objects" in out               # 대안 경로 지목
    assert "describe_db_object" in out
    assert "schedule" in out


def test_internal_schema_block_does_not_advertise_schedule_path(monkeypatch):
    """앱 내부 스키마(agent_memory) 차단에는 우회 안내가 붙으면 안 된다 — 대안이 없는 차단이다."""
    monkeypatch.setattr(_dialects, "active", lambda: _dialects.MySQLDialect())
    out = _tools._freeform_sql_access_error("SELECT id FROM agent_memory.core_messages")
    assert out and "agent_memory" in out
    assert "search_db_objects" not in out


# ══════════════════════════════════════════════════════════════════════
#  (2) 작업명 정제 — 리터럴 보존 vs 식별자 방어
# ══════════════════════════════════════════════════════════════════════

def test_literal_sanitizer_preserves_bracketed_job_name():
    """`[DK] Ranking Update` 는 한 글자도 잃지 않아야 한다 — 훼손되면 영구 미매칭."""
    assert _tools._safe_literal_value("[DK] Ranking Update") == "[DK] Ranking Update"
    assert _tools._safe_literal_value("  [CC] GuildRankingSchedule_pyron  ") == (
        "[CC] GuildRankingSchedule_pyron")
    # 작은따옴표는 지우지 않는다(정상 이름 훼손 방지) — 이스케이프는 삽입 지점 책임.
    assert _tools._safe_literal_value("O'Brien Job") == "O'Brien Job"


def test_literal_sanitizer_strips_literal_escape_vectors():
    """리터럴 문맥에서 위험한 것만 제거 — 역슬래시(따옴표 이스케이프)·제어문자(주석 결합)."""
    assert "\\" not in _tools._safe_literal_value("job\\")
    assert _tools._safe_literal_value("a\nb--x") == "ab--x"
    assert _tools._safe_literal_value("a\tb\x00c") == "abc"


def test_identifier_sanitizer_unchanged_security_boundary():
    """`_safe_ident` 는 **그대로여야 한다** — 인용 구분자 제거는 라이브 SQLi 실증 기반 방어."""
    assert _tools._safe_ident("tbl] UNION SELECT 1 --") == "tbl UNION SELECT 1 --"
    for ch in ("[", "]", "`", '"', "'", ";", "\\"):
        assert ch not in _tools._safe_ident(f"x{ch}y")


# ══════════════════════════════════════════════════════════════════════
#  (3) 생성 SQL — 이름이 리터럴로 살아 도달하는가
# ══════════════════════════════════════════════════════════════════════

def _job_sql(name: str, allow=("dk_game_integrate",)) -> str:
    return _dialects.MSSQLDialect().object_definition(
        "schedule", name, schema="", db="", allow_dbs=allow)


def test_agent_job_definition_sql_matches_bracketed_name():
    """정의 조회 SQL 의 비교 리터럴에 원본 작업명이 그대로 실려야 한다."""
    sql = _job_sql("[DK] Ranking Update")
    assert "j.name = '[DK] Ranking Update'" in sql
    assert "msdb.dbo.sysjobsteps" in sql              # 단계 본문 경로 유지


def test_agent_job_sql_escapes_single_quote_exactly_once():
    """따옴표 이중화는 삽입 지점에서 **한 번만** — 이중 이스케이프는 다시 미매칭을 만든다."""
    sql = _job_sql("O'Brien Job")
    assert "j.name = 'O''Brien Job'" in sql
    assert "O''''Brien" not in sql


def test_agent_job_sql_keeps_allowlist_boundary():
    """제품 경계(허용 DB 필터)는 이번 변경과 무관하게 유지 — 빈 허용목록은 fail-closed."""
    assert "LOWER(st.database_name) IN ('dk_game_integrate')" in _job_sql("[DK] Ranking Update")
    assert "LOWER(st.database_name) IN ('')" in _job_sql("[DK] Ranking Update", allow=())


def test_hostile_job_names_stay_inside_string_literal():
    """**파서 기준** 봉쇄 — 적대 입력이 값으로만 남고 구문으로 승격되지 않는다.

    문자열 대조가 아니라 `sqlglot` 로 파싱해 ① 값이 문자열 리터럴 노드로 존재하고 ② 문장이
    정확히 1개이며 ③ 고정 조인 밖의 테이블이 등장하지 않음을 단언한다. 리터럴 완화가 인용
    탈출을 여는지 여부는 이 세 축으로만 판정할 수 있다.
    """
    import sqlglot
    from sqlglot import exp

    hostile = [
        "[DK] Ranking Update", "x' OR 1=1 --", "x'; DROP TABLE t; --", "a''b",
        "job\\", "N'x'", "x' UNION SELECT name FROM sys.databases --", "]'--",
        "x’y", "tab\tnew\nline", "O'Brien Job", "'" * 7, "x'/*",
    ]
    allowed_tables = {"sysjobs", "sysjobsteps", "sysjobschedules", "sysschedules"}
    for raw in hostile:
        value = _tools._safe_literal_value(raw)
        sql = _job_sql(value)
        assert len(sqlglot.parse(sql, read="tsql")) == 1, f"문장 분리 주입: {raw!r}"
        tree = sqlglot.parse_one(sql, read="tsql")
        literals = [n.this for n in tree.find_all(exp.Literal) if n.is_string]
        assert value in literals, f"값이 리터럴로 갇히지 않음: {raw!r}"
        tables = {t.name.lower() for t in tree.find_all(exp.Table)}
        assert tables <= allowed_tables, f"고정 조인 밖 테이블 등장: {raw!r} → {tables}"


def test_describe_tool_routes_job_name_through_literal_sanitizer(monkeypatch):
    """도구 진입점이 예약 작업명에 식별자 정제기를 태우지 않는지 — 회귀의 실제 지점."""
    captured: dict = {}

    class _D(_dialects.MSSQLDialect):
        def object_definition(self, role, name, schema="", db="", allow_dbs=()):
            captured["name"] = name
            return ""                                  # 이후 경로는 이 테스트 대상 아님

    monkeypatch.setattr(_dialects, "active", lambda: _D())
    monkeypatch.setattr(_tools, "_mssql_active", lambda: True)
    monkeypatch.setattr(_tools, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(_tools, "_mssql_effective_allow_dbs",
                        lambda: (["dk_game_integrate"], {"dk_game_integrate": "dk_game_integrate"}))
    _tools._tool_describe_db_object(
        None, {"object_role": "schedule", "object_name": "[DK] Ranking Update"})
    assert captured.get("name") == "[DK] Ranking Update"


def test_describe_tool_still_sanitizes_identifier_roles(monkeypatch):
    """식별자 역할(뷰 등)은 종전대로 `_safe_ident` — 리터럴 완화가 번지지 않는다."""
    captured: dict = {}

    class _D(_dialects.MySQLDialect):
        def object_definition(self, role, name, schema="", db="", allow_dbs=()):
            captured["name"] = name
            return ""

    monkeypatch.setattr(_dialects, "active", lambda: _D())
    monkeypatch.setattr(_tools, "_mssql_active", lambda: False)
    _tools._tool_describe_db_object(
        None, {"object_role": "view", "object_name": "v]x", "schema_name": "s"})
    assert captured.get("name") == "vx"
