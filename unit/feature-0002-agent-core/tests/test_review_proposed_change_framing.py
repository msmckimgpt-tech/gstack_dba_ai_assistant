"""FR-review-frames-live-db-as-spec (conversation_audit 2026-07-30) 봉인 검증.

관측된 마찰(대화 `20260730074631-a2efa955` "SQL 쿼리 코드 리뷰", product 119):
첨부 쿼리 리뷰에서 assistant 가 **곧 적용될 구조**가 아니라 **현재 DB** 를 기준으로 답해,
변경이 스스로 만들어내는 차이(아직 없는 테이블·컬럼·루틴, 스크립트가 추가할 PK, 바뀐 시그니처)를
전부 결함·경고로 보고했다. 결정적 증거는 A/B 대조쌍 — 동일 5개 파일(sha256 일치)·동일 요청문의
두 대화가 3분 간격으로 한쪽은 코드 리뷰, 다른 쪽은 "배포 순서 의존성(가장 중요)" + "아직 존재하지
않습니다" 로 갈렸다. 다른 대화(`…b5f40d99`)에서는 미적용 마이그레이션을 두고 "동적 ALTER 로직이
실제로 실행되지 않았거나 실패한 상태입니다" 라는 **허위 결함 단정**까지 나왔다.

근본원인(L1): 프롬프트가 "첨부 vs 실 DB 주장은 반드시 라이브 검증" 만 정하고 그 **차이의 해석**
(시간 방향)은 정하지 않았다 → 프레임이 모델 재량으로 갈렸다.

본 테스트가 고정하는 것:
  A/B. 시간 방향 계약이 **코드 권위선**으로 항상 주입되고(운영자 global row drift 무관),
       출력 구조(적용 전제 절 분리 · 심각도 배지 귀속)까지 규정한다.
  C.   도구가 미발견 오류/빈 결과에 **분류 교정 힌트**를 붙인다(사실 창작 없이 조건부).
  회귀. 선행 봉인(실 DB 대조 강제·부재 단정 금지)이 약화되지 않는다.
  scan. `search_routines` 가 본문 매칭 문맥 조각을 함께 돌려준다.
"""
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

import agent_core                                            # noqa: E402
from modules import tools as T                               # noqa: E402
from modules import dialects as D                            # noqa: E402

_SRC = (SRC_ROOT / "agent_core.py").read_text(encoding="utf-8")


# ── Lever A/B: 시간 방향 계약 (프롬프트) ────────────────────────────────────

def test_temporal_directive_constant_exists():
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "REVIEWING A PROPOSED CHANGE" in d
    assert "**BEFORE**" in d and "**AFTER**" in d


def test_temporal_directive_forbids_defect_framing_of_intended_deltas():
    """변경이 스스로 만드는 차이 = 적용 전제, 결함 아님 — 마찰의 핵심 계약."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "PRECONDITION" in d
    assert "not a defect" in d or "**not a defect**" in d
    assert "결함/문제/위험" in d, "결함 어휘로 승격하는 것을 명시적으로 금지해야 함"


def test_temporal_directive_forbids_false_script_failure_claim():
    """라이브에서 나온 허위 단정('실행되지 않았거나 실패')을 직접 못박는다."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "실행되지 않았다/실패했다" in d


def test_temporal_directive_defines_output_structure_lever_b():
    """Lever B: 적용 전제는 별도 1개 절 · 심각도 배지는 적용 후 결함에만."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "적용 전제 / 배포 순서" in d, "전제 항목을 묶을 단일 절을 지정해야 함"
    assert "🔴/🟡" in d, "심각도 배지 오남용을 명시적으로 금지해야 함"
    assert "STILL" in d and "after the whole attached set has been applied" in d


def test_precondition_rows_must_be_verified_or_marked_unknown():
    """FR-review-precondition-assumed-not-verified — 전제 절이 추측을 초대하지 않게.

    90일 실측: 객체 상태 주장 84건 중 41건(48.8%)이 그 객체를 조회한 도구 결과 없이
    단정됐고, `미확인` 으로 표기된 행은 **0건**이었다. 라이브 실측에서는 약 148만 행
    실존 테이블을 "현재 미존재" 로 적어 대용량 PK 추가 리스크를 통째로 놓쳤다.
    """
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "EVERY LINE IN THAT SECTION MUST BE A VERIFIED FACT OR MARKED 미확인" in d
    assert "table-shaped invitation to guess" in d, "왜 이 절이 위험한지 이유를 줘야 함"
    assert "an actual tool result for THAT object in THIS run" in d
    assert "미확인` is a first-class value here" in d or "first-class value here" in d


def test_unverifiable_signals_map_to_unknown_not_absence():
    """권한거부·스코프경고·미조회는 `미확인` — 라이브 3건이 전부 이 경로로 틀렸다."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "permission refusal" in d
    assert "접근이 허용되지 않은 스키마" in d, "실제 거부 문구를 지목해야 매핑이 확실해짐"
    assert "simply not having looked" in d
    assert "never \"존재하지 않음\"" in d
    assert "says nothing about existence" in d, "거부→부재 번역 금지를 명시해야 함"


def test_zero_rows_rule_is_scope_qualified_not_blanket():
    """§18.8 codex P2: 0행을 **무조건** 미확인으로 만들면 정당하게 검증된 부재까지 못 말한다.

    정확한 식별자로 조회하고 **도구가 자기 커버리지를 명시**한 0행은 그 범위 내
    부재의 증거다 — 범위를 함께 말하는 조건으로 허용해야 '검증된 사실을 말하라' 와
    충돌하지 않는다.
    """
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "0 rows is not automatically 미확인 either" in d
    assert "EXACT identifier" in d
    assert "states its own coverage" in d
    assert "within that stated" in d
    assert "허용 DB 전체에서 미발견" in d, "범위를 붙여 말하는 예시가 있어야 함"
    assert "guessed" in d and "did not state its coverage" in d


def test_unknown_is_not_a_free_pass_lookup_attempt_required():
    """§18.8 codex P2: '미조회 ⇒ 미확인' 만 있으면 예산 아끼려 전부 미확인 가능."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "미확인 is honest, not free" in d
    assert "MUST attempt at least one lookup" in d
    assert "verify > 미확인 > guess" in d
    assert "never skip straight to 미확인 to save a call" in d
    # 과교정 방지 — 주변 객체·예산 소진 시엔 허용
    assert "peripheral objects" in d and "discovery budget is genuinely spent" in d


def test_attachment_text_is_not_evidence_of_live_state():
    """`CREATE TABLE IF NOT EXISTS x` 는 x 의 현재 존재 여부에 대한 증거가 아니다."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "IF NOT EXISTS" in d
    assert "not evidence about whether" in d


def test_static_mirror_carries_verified_or_unknown_rule():
    """운영자 row 부재(bootstrap) 경로에서도 **같은** 계약이 읽히도록 미러 정합.

    §18.8 codex R2 P2: 초기안 미러는 0행을 무조건 미확인으로 단정하고 lookup 의무가
    없어, bootstrap 경로에서만 (b)(c) 결함이 열려 있었다. 미러도 동적 계약과 같은
    3요소를 담아야 한다.
    """
    p = agent_core.SYSTEM_PROMPT
    assert "every line in it must be a verified fact or marked 미확인" in p
    # 0행 예외가 미러에도 있어야 한다(과교정 방지).
    assert "absence evidence ONLY within a scope the tool itself declared" in p
    assert "guessed name or an unstated scope ⇒ 미확인" in p
    # lookup 의무가 미러에도 있어야 한다(미확인 남발 방지).
    assert "미확인 is not free" in p
    assert "verify > 미확인 > guess" in p


def test_temporal_directive_keeps_live_verification_mandatory():
    """회귀 방지(중요): 라이브 대조를 약화하지 않는다 — 선행 봉인 계보 보존."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "You still MUST verify against the live DB" in d
    assert "never narrate the current-DB side from memory" in d
    # 대조의 목적 3가지(적용 가능성·미접촉 의존성·진짜 선행 누락)가 모두 남아야 한다.
    assert "(a) whether the change can actually be applied" in d
    assert "(b) impact on what the change does NOT touch" in d
    assert "(c) whether a prerequisite is genuinely" in d
    assert "Only (c) is a defect" in d


def test_temporal_directive_requires_checking_sibling_attachments():
    """형제 첨부가 만드는 객체를 '누락'으로 부르지 않게 — 과교정 방지의 반대편 가드."""
    d = agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE
    assert "check the OTHER attached files first" in d
    assert "not created by any attached file" in d


def test_temporal_directive_is_code_authoritative(monkeypatch):
    """운영자 global row 가 base 를 통째로 대체해도 계약이 살아남아야 한다(AUTH-1a)."""
    class _Cur:
        def execute(self, *a, **k):
            self._q = a[0] if a else ""

        def fetchone(self):
            if "WebSystemPrompts" in getattr(self, "_q", ""):
                return ("완전히 다른 운영자 프롬프트 — 코드 상수를 통째로 대체한다.",)
            return None

        def fetchall(self):
            return []

        def close(self):
            pass

    class _Conn:
        def cursor(self):
            return _Cur()

    prompt = agent_core.compose_system_prompt(_Conn(), product_id=None)
    assert "완전히 다른 운영자 프롬프트" in prompt, "base 대체 경로를 실제로 탄 것이 맞는지"
    assert "REVIEWING A PROPOSED CHANGE" in prompt, \
        "base drift 로 시간 방향 계약이 사라지면 마찰이 그대로 재발한다"


def test_static_system_prompt_mirrors_the_contract():
    """base 가 대체되지 않는 통상 경로에서도 §ATTACHED FILES 안에서 읽히도록 미러 1줄."""
    assert "A PROPOSED CHANGE IS THE FUTURE STATE" in agent_core.SYSTEM_PROMPT
    assert "적용 전제" in agent_core.SYSTEM_PROMPT


def test_attachment_section_points_at_the_contract():
    """첨부 본문 바로 옆(요청별 주입 블록)에서도 시간 방향을 가리켜야 한다."""
    # (_SRC 는 소스 텍스트 — 인접 문자열 리터럴이 개행으로 분할되므로 토큰 단위로 검증.)
    assert "live DB is the BEFORE state and this set is the AFTER state" in _SRC
    assert "PROPOSED CHANGE — TIME DIRECTION' rule" in _SRC
    assert "적용 \"\n            \"전제, not 결함" in _SRC or "전제, not 결함" in _SRC


def test_prior_grounding_seals_not_weakened():
    """선행 봉인(FR-partial-evidence · FR-false-absence 계보)이 그대로 있어야 한다."""
    assert "COMPARING an attachment against the live DB" in agent_core.SYSTEM_PROMPT
    assert "Focusing on the attached files does NOT override that grounding rule" in _SRC
    assert "ZERO ROWS IS NOT ABSENCE" in agent_core.SYSTEM_PROMPT


# ── Lever C: 도구 결과 분류 교정 힌트 ───────────────────────────────────────

def test_missing_object_error_gets_classification_hint():
    for err in (
        "1146 (42S02): Table 'gunzlog.steampaymenthistory' doesn't exist",
        "1054 (42S22): Unknown column 'ServerID' in 'field list'",
        "Invalid object name 'dbo.T_BOARD_EVENT'.",
        "Could not find stored procedure 'dbo.MSP_X'.",
    ):
        hint = T._proposed_change_hint(err)
        assert "적용 전제" in hint, f"미발견 오류에 분류 교정이 없다: {err}"
        assert "결함이 아닙니다" in hint


def test_unrelated_errors_get_no_hint():
    """잡음 0 — 미발견과 무관한 오류/빈 문자열에는 붙지 않는다."""
    for err in ("", "보안 정책상 차단된 SQL", "Deadlock found when trying to get lock", None):
        assert T._proposed_change_hint(err) == ""


def test_hint_is_conditional_not_an_assertion():
    """사실을 창작하지 않는다 — 첨부에 그 객체가 있을 때만 성립하는 조건부 문장이어야."""
    hint = T._PROPOSED_CHANGE_HINT
    assert "이면" in hint or "라면" in hint, "무조건 '결함 아님' 이라고 단정하면 진짜 선행 누락을 가린다"
    assert "실제 선행 누락(결함)입니다" in hint, "진짜 결함 경로가 열려 있어야 함"


def test_hint_is_a_two_way_fork_not_a_one_way_excuse():
    """codex 적대 리뷰 P2: 힌트가 무조건 붙으므로 **양방향 분기**여야 부재 규칙을 약화하지 않는다.

    describe_table/describe_routine 의 빈 결과는 권한·스코프·오타로도 난다. 한쪽으로 단정하지
    말라는 지시가 없으면 이 힌트가 선행 봉인(0행≠부재)을 도구 출력에서 되돌린다.
    """
    hint = T._PROPOSED_CHANGE_HINT
    assert "한쪽으로 단정하지 말 것" in hint
    assert "권한" in hint and "스코프" in hint and "대소문자" in hint
    assert "교차확인 전에는" in hint


def test_execute_sql_error_path_carries_hint(monkeypatch):
    def _boom(conn, sql, **kw):
        raise RuntimeError("1146 (42S02): Table 'gunzlog.steampaymenthistory' doesn't exist")

    monkeypatch.setattr(T, "_raw_execute_sql", _boom)
    out = T._tool_execute_sql(None, {"sql": "SELECT 1 FROM gunzlog.steampaymenthistory"})
    assert "SQL 실행 오류" in out
    assert "적용 전제" in out


def test_describe_routine_not_found_carries_hint(monkeypatch):
    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_struct_schema_access_error", lambda *a, **k: None)
    monkeypatch.setattr(T, "_raw_execute_sql", lambda c, s: ([("rows", [], [])], 0.0))
    out = T._tool_describe_routine(
        None, {"schema_name": "gunzgame", "routine_name": "Log_SteamPaymentHistory"})
    assert "저장 루틴(프로시저/함수)이 없습니다" in out
    assert "적용 전제" in out, "신규 프로시저 리뷰의 최빈 미발견 경로 — 결함 승격을 막아야 함"


def test_describe_table_not_found_carries_hint(monkeypatch):
    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_struct_schema_access_error", lambda *a, **k: None)
    monkeypatch.setattr(T, "_raw_execute_sql", lambda c, s: ([("rows", [], [])], 0.0))
    out = T._tool_describe_table(
        None, {"schema_name": "gunzlog", "table_name": "steampaymenthistory"})
    assert "적용 전제" in out


def test_describe_table_found_has_no_hint(monkeypatch):
    """정상 발견에는 붙지 않는다(잡음 0 · 오발동 방지)."""
    def _run(conn, sql, **kw):
        if "COLUMN" in sql.upper() or "columns" in sql:
            return ([("rows", ["c"], [("ID", "int", "NO", "PRI", None, "", "")])], 0.0)
        return ([("rows", [], [])], 0.0)

    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_struct_schema_access_error", lambda *a, **k: None)
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_describe_table(None, {"schema_name": "gunzgame", "table_name": "charactercurrency"})
    assert "적용 전제" not in out


# ── scan: search_routines 매칭 스니펫 ───────────────────────────────────────

def test_mysql_search_routines_sql_selects_match_snippet():
    sql = D.MySQLDialect().search_routines("CharacterCurrency")
    assert "MATCH_SNIPPET" in sql
    assert "LOCATE('CharacterCurrency', COALESCE(ROUTINE_DEFINITION, ''))" in sql
    assert "SUBSTRING(ROUTINE_DEFINITION" in sql


def test_mysql_search_routines_enumeration_has_constant_empty_snippet():
    """keyword 없는 전체 열거에서 LOCATE('', x)=1 의 무의미 머리말이 붙지 않아야 한다."""
    sql = D.MySQLDialect().search_routines("")
    assert "'' AS MATCH_SNIPPET" in sql
    assert "LOCATE(''" not in sql


def test_mssql_search_routines_sql_selects_match_snippet():
    sql = D.MSSQLDialect().search_routines("doc", db="Shop")
    assert "MATCH_SNIPPET" in sql
    assert "CHARINDEX('doc', COALESCE(m.definition, ''))" in sql
    assert "SUBSTRING(m.definition" in sql


def test_snippet_cell_normalizes_for_markdown_table():
    assert T._routine_snippet_cell(("a", "b", "P", "INSERT INTO `X`\n  VALUES (1)")) == \
        "`INSERT INTO 'X' VALUES (1)`"
    # 파이프는 이스케이프(표 파손 방지)
    assert "\\|" in T._routine_snippet_cell(("a", "b", "P", "a | b"))
    # 상한 초과는 절단 표식
    long = "x" * 400
    cell = T._routine_snippet_cell(("a", "b", "P", long))
    assert cell.endswith("…`") and len(cell) < 200


def test_snippet_cell_backward_compatible_with_3col_rows():
    """구 dialect·fake row(3컬럼)에서도 예외 없이 빈 셀."""
    assert T._routine_snippet_cell(("a", "b", "P")) == ""
    assert T._routine_snippet_cell(("a", "b", "P", None)) == ""


def test_mysql_handler_renders_snippet_column(monkeypatch):
    def _run(conn, sql):
        return ([("rows", ["s", "n", "t", "m"],
                  [("gunzgame", "Steam_AccountChargeCash", "PROCEDURE",
                    "INSERT INTO `CharacterCurrency` (ID, CurrencyType, Amount)")])], 0.0)

    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "CharacterCurrency"})
    assert "본문 매칭 위치" in out
    assert "INSERT INTO 'CharacterCurrency'" in out, \
        "왜 이 루틴이 걸렸는지 그 자리에서 보여야 describe_routine 왕복이 준다"


def test_empty_snippet_row_is_not_labeled_name_match(monkeypatch):
    """codex 적대 리뷰 P2: 빈 스니펫을 '(이름 매칭)' 으로 라벨하면 **틀린 단정**이다.

    WHERE 는 이름 OR 본문 OR 주석을 LIKE 로 보는데 스니펫은 본문만 LOCATE 한다 —
    주석 매칭 행이나 LIKE 와일드카드(`%`) 키워드도 빈 스니펫이 된다.
    """
    def _run(conn, sql):
        return ([("rows", ["s", "n", "t", "m"],
                  [("app", "sp_hit", "PROCEDURE", "SELECT 1 -- doc"),
                   ("app", "sp_comment_only", "PROCEDURE", "")])], 0.0)

    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "doc"})
    assert "(본문 외 매칭)" in out
    assert "(이름 매칭)" not in out, "도구가 확인하지 못한 것을 이름 매칭으로 단정하면 안 됨"
    assert "LIKE 와일드카드" in out, "빈 스니펫의 원인을 설명해야 모델이 오독하지 않음"


def test_mysql_handler_keeps_3col_table_when_no_snippet(monkeypatch):
    """이름만 매칭·열거 결과는 종전 3컬럼 표 그대로(출력 계약 회귀 0)."""
    def _run(conn, sql):
        return ([("rows", ["s", "n", "t"], [("app", "sp_x", "PROCEDURE")])], 0.0)

    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "sp_x"})
    assert "| schema | routine | type |" in out
    assert "본문 매칭 위치" not in out


def test_mssql_handler_renders_snippet_column(monkeypatch):
    from shared import config as cfg

    def _run(conn, sql):
        return ([("rows", ["s", "n", "t", "m"],
                  [("dbo", "MSP_SELECT_BOARD_CONTENT", "PROCEDURE",
                    "SELECT * FROM masangsoft_documents WHERE doc_id = @id")])], 0.0)

    cfg.set_active_datasource("prod", engine="mssql")
    try:
        monkeypatch.setattr(T, "_mssql_active", lambda: True)
        monkeypatch.setattr(T, "_mssql_resolve_catalog", lambda a: ("", "", None))
        monkeypatch.setattr(T, "_mssql_effective_allow_dbs", lambda: (["masangsoftweb"], {}))
        monkeypatch.setattr(T, "_raw_execute_sql", _run)
        out = T._tool_search_routines(None, {"keyword": "masangsoft_documents"})
        assert "본문 매칭 위치" in out
        assert "masangsoft_documents" in out
    finally:
        cfg.set_active_datasource(None)
