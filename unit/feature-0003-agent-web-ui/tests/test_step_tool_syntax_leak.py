"""실행 단계에 «도구 호출 표기» 가 그대로 노출되는 것을 잠근다 (사용자 제보 2026-09-08).

## 무엇이 새어 나갔나

제보 화면(실행 단계 패널)에서 단계 제목이 이렇게 보였다:

    describe_table {'schema_name': 'coupon', 'table_name': 'dbo.T_COUPON'}
    search_tables {'keyword': 'masangsoft_member_channeling_gzr'}

라이브 원장(`agent_runtime.steps`) 실측으로 출처가 확정됐다 — 그 행들의 `work_source` 가
`external-ai` 였다. 즉 **연결된 개인 AI 가 `POST /api/ai/tools/<name>` 본문에 실어 보낸
`work` 문자열**이고, 서버는 그것을 그대로 저장했으며 화면은 그대로 그렸다. 브리지 프롬프트는
`reason` 만 규정하고 `work` 는 규정조차 하지 않는다 — **계약이 없는 비신뢰 입력**이다.

같은 화면의 배지도 같은 축이었다: `TOOL_LABEL_MAP` 이 7개뿐이라 `search_tables` ·
`read_task_attachment` 같은 이름이 **식별자 그대로** 배지에 찍혔다.

## 판정 축은 «호출 표기» 이지 «식별자처럼 보임» 이 아니다

초판은 「인용 없는 snake_case 로 시작」을 규칙에 넣었다가 적대 검증에서 폐기했다 — 라이브
원장 **9,759행 전건 재생**에서 그 규칙이 걸러낸 412행 중 **실제 도구 구문은 18행뿐이고
394행(96%)이 정상 제목**이었다(전부 `work_source='llm'`, 제보와 무관한 내부 경로). 이
도메인은 **테이블 이름이 곧 사용자의 어휘**라 그 형태를 금지 서명으로 쓸 수 없다.
지금 서명은 둘뿐이다: (a) 인자 매핑 리터럴 (b) **서버 도구 census 의 이름**.

## 잠그는 계약

  L1  판정기가 실제 유출 문자열을 잡는다 — 도구명을 **하드코딩한 표**로 태운다(입력에서
      도구명을 뽑아 넘기면 규칙 (b)가 항진이 된다).
  L2  **음성 대조군** — 사람이 쓴 정상 문구는 통과한다. 라이브에서 실제로 오탐됐던 문구를
      표본에 넣는다(§16.7 G7 보강).
  L3  `sanitize(derive(x))` 는 고정점이다 — **적대 인자로도**. 파생값도 비신뢰 `args` 에서
      만들어지므로 파생 후 재정화가 없으면 그 자체가 우회로다.
  L4  적재 시점(`_bridge_step_narration`)에서 떨어진다.
  L5  완료·진행 두 표시 경로가 **같은 단일 이음매**(`_step_display_narration`)를 쓴다 —
      census 전 도구 × {정상, 적대} 인자로 제목·출처 동치를 대조한다 (§16.7 G12·G4).
  L6  배지 라벨 표의 모수가 **서버 도구 census 전체**와 일치한다. census 는 손 열거가 아니라
      `modules.tools` 객체 조회로 얻고, 결손을 **산출물(app.js)에 주입**해 FAIL 을 실증한다.
  L7  제목·배지 폴백이 내부 식별자를 되돌려 주지 않는다 — 렌더러 **전수**가 공용 헬퍼를 쓴다.
  L8  행위 하네스가 CI 에서 **실제로 실행**된다(`make test` 가 node 를 설치한다).

L1~L5 는 실제 함수를 실행해 확인한다. L6~L7 은 JS 라 소스 검사이며, 존재 단언은 **주석을
제거한 코드에만** 걸고 결함 주입 대조군을 함께 둔다 (§16.7 G11-a·G11-b).
"""
from __future__ import annotations

import datetime
import importlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest


def _import(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        return importlib.import_module(name)


app = _import("app")
ai_tools = _import("routers.ai_tools")
conv_store = _import("routers._conv_store")

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"
_APP_JS = _STATIC / "app.js"
_HARNESS = pathlib.Path(__file__).resolve().parent / "verify_step_title_no_tool_syntax.mjs"


# 라이브 원장에서 실제로 뽑은 유출 문구 — (문구, 그 단계의 도구).
_LEAKED = [
    ("describe_table {'database': 'coupon', 'schema_name': 'dbo', 'table_name': 'T_EVENT'}",
     "describe_table"),
    ("search_tables {'keyword': 'masangsoft_member_channeling_gzr'}", "search_tables"),
    ('describe_table {"schema_name": "coupon", "table_name": "dbo.T_COUPON"}', "describe_table"),
    ("execute_sql 검증", "execute_sql"),
    ("get_table_indexes 검증", "get_table_indexes"),
    ("list_schemas", "list_schemas"),
    ("read_task_attachment(attachment_id=1286)", "read_task_attachment"),
    # 다른 도구의 이름이 실려도 노출이다 — 모수는 census 전체다.
    ("다음은 search_tables 로 확인한다", "execute_sql"),
    # 전각·제로폭 우회 — 화면상 같은 글자로 보인다.
    ("describe＿table 을 실행했습니다", "execute_sql"),
    ("ｄｅｓｃｒｉｂｅ_ｔａｂｌｅ 실행", "execute_sql"),
]

# 음성 대조군 — 사람이 읽는 문구. **라이브에서 초판이 실제로 오탐한 것**을 표본에 넣는다.
_HUMAN = [
    "`coupon`.`T_COUPON` 구조를 확인한다",
    "첨부 1286 본문 읽기",
    "결과를 검토하고 다음 작업을 정합니다",
    "`masangsoft_sequence` 관련 테이블을 찾는다",
    "`dbo`.`masangsoft_member_channeling_gzr` 구조를 확인한다",
    # ↓ 초판(선두 식별자 규칙)이 라이브 394행에서 지웠던 정상 제목들
    "dk_game_release_240의 Character 테이블 구조 확인 (NOT EXISTS 비교 대상)",
    "log_v2 스키마의 테이블 목록 및 통계 조회",
    "masangsoft_documents에서 module_srl 기준 문서 개수 집계",
    "order_items 테이블에 주문 금액 컬럼이 있는지 확인하기 위해",
]

#: 대표 인자 — census 의 각 도구가 읽는 키를 넉넉히 담는다(모르는 키는 무시된다).
_REPRESENTATIVE_ARGS = {
    "schema_name": "masangsoftweb", "table_name": "masangsoft_member_channeling_gzr",
    "routine_name": "usp_sync_member", "keyword": "masangsoft_sequence",
    "database": "coupon", "filename": "01-dbo.masangsoft_member.sql",
    "object_name": "vw_member", "node": "masangsoft_member",
    "sql": "SELECT COUNT(*) FROM dbo.masangsoft_sequence", "limit": 5,
}

#: **적대 인자** — 파생 문구가 이 값을 그대로 제목에 박으면 유출이 부활한다.
_HOSTILE_ARGS = {
    "schema_name": "describe_table {'schema_name': 'x'}",
    "table_name": "search_tables {'keyword': 'y'}",
    "routine_name": "execute_sql {'sql': 'z'}",
    "keyword": "describe_table {'schema_name': 'coupon', 'table_name': 'dbo.T_COUPON'}",
    "database": "list_schemas",
    "filename": "A" * 5000,
    "object_name": "get_foreign_keys {'a': 'b'}",
    "node": "graph_navigate {'n': 1}",
    "sql": "SELECT " + "x" * 5000,
    "limit": 5,
}


# ── L1·L2 판정기 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,tool", _LEAKED)
def test_l1_detector_catches_real_leaked_strings(text, tool):
    assert app._step_text_is_tool_syntax(text, tool), f"유출 문구를 놓쳤다: {text!r}"
    # 도구 이름을 모르는 옛 행에서도 census 서명만으로 잡혀야 한다.
    assert app._step_text_is_tool_syntax(text, ""), (
        f"도구 이름 없이는 못 잡는다: {text!r} — 옛 행에는 tool 이 비어 있을 수 있다")


@pytest.mark.parametrize("text", _HUMAN)
def test_l2_detector_passes_human_written_narration(text):
    assert not app._step_text_is_tool_syntax(text, "describe_table"), (
        f"정상 문구를 도구 표기로 오판했다: {text!r}")
    assert app._sanitize_step_narration(text, "describe_table") == text.strip()


def test_l2_empty_is_not_tool_syntax():
    """빈 값은 «표기» 가 아니라 «없음» 이다 — 두 상태를 섞으면 출처 표기가 거짓이 된다."""
    assert not app._step_text_is_tool_syntax("", "execute_sql")
    assert not app._step_text_is_tool_syntax(None, "execute_sql")


def test_l2_reason_axis_sees_only_the_args_literal():
    """사유는 도구 이름 «언급» 이 자연스러운 축이라 (b) 를 쓰지 않는다.

    라이브 실측: 「… 단일 execute_sql 쿼리로 UNION 집계하여 …」 같은 정상 사유가 (b) 로
    통째로 지워졌다. 사유에는 (a) 만 적용한다 — 인자 매핑 리터럴은 산문에 우연히 나타나지 않는다.
    """
    prose = ("Gold/GemV2/Currency 모두 dbLog 내 테이블이므로 단일 execute_sql 쿼리로 "
             "UNION 집계하여 모든 재화 소모를 통합 분석")
    assert app._step_text_is_tool_syntax(prose, "execute_sql"), "제목 축에서는 (b) 가 산다"
    assert not app._step_text_is_tool_syntax(prose, "execute_sql", allow_tool_names=False)
    # SQL 산문의 `(KEY='value')` 를 도구 인자로 오인하지 않는다(kwargs 가지 제거).
    sql_prose = "첨부가 만드는 TF_Log_* 가 파티션 상태인지(CREATE_OPTIONS='partitioned') 확정해야"
    assert not app._step_text_is_tool_syntax(sql_prose, "execute_sql", allow_tool_names=False)
    assert not app._step_text_is_tool_syntax(sql_prose, "execute_sql")
    # (a) 는 사유에도 적용된다.
    assert app._step_text_is_tool_syntax("{'schema_name': 'coupon'} 을 봤다", "describe_table",
                                         allow_tool_names=False)


def test_l2_census_comes_from_a_real_query_not_a_hand_list():
    """모수는 **조회**로 얻는다 (§16.7 G12-b).

    폴백 목록을 무조건 합치면 이 단언이 **실패할 수 없게** 된다 — 조회가 통째로 깨져도
    손 목록이 census 를 채우고, 그러면 새 도구가 늘어도 라벨 가드가 결손을 못 본다
    (적대 검증 라운드 2 실측: 조회 17종인데 census 는 무조건 25종이었다).
    그래서 **조회 산출 자체**를 본다.
    """
    queried, complete = app._query_tool_names()
    assert complete, "조회 출처 중 하나가 비었다 — census 가 조용히 좁아진다"
    assert len(queried) >= 20, (
        f"레지스트리 조회가 {len(queried)}건뿐 — `modules.tools._TOOL_HANDLERS` 또는 브리지 "
        "표면 조회가 깨졌다(폴백이 이 결손을 가리지 않게 조회분을 직접 본다)")
    for name in ("scratch_import", "scratch_sql", "scratch_list", "scratch_reset"):
        assert name in queried, (
            f"런타임 스위치에 걸려 조회에서 빠진 도구: {name} — 게이트는 «부를 수 있는가» 를 "
            "정하지 이름을 없애지 않는다")
    for name in ("get_task_context", "read_task_attachment"):
        assert name in queried, f"브리지 표면이 조회 모수에 없다: {name}"
    census = app._tool_name_census()
    assert queried <= census
    # 레지스트리에 없고 코드가 직접 단계로 남기는 이름(라이브 원장 실측)만 상수로 보탠다.
    for name in ("materialize_attachment", "query_sql"):
        assert name in census, f"실제 배출되는 도구가 census 밖이다: {name}"


def test_l2_empty_census_does_not_swallow_every_title():
    """census 가 비면 `(?:)` 가 되어 **모든 문자열**에 매칭된다 — 제목이 전멸한다.

    지금은 폴백 덕에 도달 불가지만, 「손 열거 제거」 리팩터가 반드시 밟는 지뢰이고 실패 모드가
    조용하다(예외 0·로그 0·화면만 뭉개짐). 그래서 여기서 잠근다.
    """
    saved_census, saved_re = conv_store._TOOL_NAME_CENSUS, conv_store._TOOL_NAME_RE
    try:
        conv_store._TOOL_NAME_CENSUS = frozenset()
        conv_store._TOOL_NAME_RE = None
        assert not app._step_text_is_tool_syntax(
            "dk_game_release_240의 Character 테이블 구조 확인", "")
    finally:
        conv_store._TOOL_NAME_CENSUS, conv_store._TOOL_NAME_RE = saved_census, saved_re


# ── L3 파생의 고정점 (정상·적대 인자 양쪽) ────────────────────────────────────

@pytest.mark.parametrize("args,label", [(_REPRESENTATIVE_ARGS, "정상"), (_HOSTILE_ARGS, "적대")])
def test_l3_derived_narration_is_a_fixed_point(args, label):
    """`sanitize(derive(x))` 는 고정점이어야 한다 — **적대 인자로도**.

    파생값은 비신뢰 `args` 에서 만들어진다. 정화가 저장 문구만 막고 파생을 안 보면, 공격자는
    같은 요청에서 필드만 옮기면 된다(적대 검증 실측: `keyword` 에 도구 구문을 넣자 제목으로
    복귀했다).
    """
    offenders = []
    for tool in sorted(app._tool_name_census()):
        work, _ws, _r, _rs = app._step_display_narration(
            {"tool": tool, "args": dict(args), "sql": str(args.get("sql") or ""),
             "work": "", "reason": ""})
        if app._step_text_is_tool_syntax(work, tool):
            offenders.append((tool, work[:80]))
    assert not offenders, f"[{label}] 표시 산출이 자기 판정기에 걸린다: {offenders}"


@pytest.mark.parametrize("args", [_REPRESENTATIVE_ARGS, _HOSTILE_ARGS])
def test_l3_display_work_is_length_capped(args):
    """파생값에도 길이 상한이 걸린다 — 저장 문구만 캡하면 파생이 캡을 우회한다.

    실측(초판): `keyword` 100KB → 제목 100,014자. 이 패널은 폴링마다 통째로 재렌더되므로
    대형 제목 한 건이 매 tick 비용을 곱한다.
    """
    for tool in sorted(app._tool_name_census()):
        work, _ws, reason, _rs = app._step_display_narration(
            {"tool": tool, "args": dict(args), "sql": str(args.get("sql") or ""),
             "work": "", "reason": ""})
        assert len(work) <= 255, f"{tool}: 제목 {len(work)}자"
        assert len(reason) <= 500, f"{tool}: 사유 {len(reason)}자"
        assert reason == "", "사유는 파생하지 않는다 — 없으면 비운다(지어내지 않는다)"


def test_l3_hostile_keyword_does_not_return_through_the_derived_title():
    """적대 검증 B1 의 정확한 재현 케이스 — 이 한 건이 통과하면 수정이 무효다."""
    work, source, _r, _rs = app._step_display_narration({
        "tool": "search_tables",
        "args": {"keyword": "describe_table {'schema_name': 'coupon', "
                            "'table_name': 'dbo.T_COUPON'}"},
        "work": "search_tables 실행", "work_source": "external-ai",
    })
    assert "describe_table" not in work, f"적대 인자가 제목으로 복귀했다: {work!r}"
    assert "{" not in work, work
    assert source == "derived"


def test_l3_tail_never_returns_the_identifier():
    for tool in ("brand_new_tool", "some_future_probe", "read_task_attachment"):
        out = app._derive_step_work_tail(tool, {})
        assert tool not in out, f"폴백이 식별자를 노출한다: {tool} -> {out!r}"
        assert not app._step_text_is_tool_syntax(out, tool), out


def test_l3_display_seam_is_none_safe():
    """행 하나가 죽으면 그 대화의 단계 표시가 통째로 사라진다 — 방어적 계약을 유지한다."""
    assert app._resolve_step_display(None)["work"]
    assert app._step_display_narration(None)[0]


# ── L4 적재 시점 차단 ────────────────────────────────────────────────────────

def test_l4_ingestion_drops_tool_syntax_work():
    args = {"schema_name": "coupon", "table_name": "T_COUPON"}
    body = {
        "work": "describe_table {'schema_name': 'coupon', 'table_name': 'T_COUPON'}",
        "reason": "첨부 변경안의 타입·키를 실제 QA DB 에서 검증하기 위해",
    }
    work, reason = ai_tools._bridge_step_narration(body, args, "describe_table")
    assert work == "", "도구 표기가 적재 경로를 그대로 통과했다"
    assert reason == body["reason"], "정상 사유까지 함께 버렸다"
    assert "work" not in args and "reason" not in args


def test_l4_ingestion_keeps_human_work_and_identifier_led_reason():
    body = {"work": "첨부 1286 본문 읽기",
            "reason": "order_items 테이블에 주문 금액 컬럼이 있는지 확인하기 위해"}
    work, reason = ai_tools._bridge_step_narration(body, {}, "read_task_attachment")
    assert work == "첨부 1286 본문 읽기"
    assert reason == body["reason"], "정상 사유가 지워졌다"


def test_l4_dropped_work_is_replaced_by_derived_korean(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(ai_tools, "_insert_bridge_step",
                        lambda conv, run, entry: recorded.append(entry) or 1)
    args = {"schema_name": "coupon", "table_name": "T_COUPON"}
    work, reason = ai_tools._bridge_step_narration(
        {"work": "describe_table {'schema_name': 'coupon'}", "reason": ""}, dict(args),
        "describe_table")
    ai_tools._record_bridge_step(
        conn=None, task={"conversation_id": "c1", "task_id": "t_abc"},
        tool_name="describe_table", args=args, tool_result="ok", work=work, reason=reason)
    step = recorded[0]
    assert step["work"] and "describe_table" not in step["work"] and "{" not in step["work"]
    assert step["work_source"] == "derived"


# ── L5 두 표시 경로의 동치 ────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, owner):
        self._owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._owner.executed.append((sql, params))

    def fetchall(self):
        return self._owner.rows

    def close(self):
        pass


class _FakePg:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple] = []
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def _row(step_index, tool, work, work_source, reason, args, sql=""):
    return (step_index, "step", tool, f"{tool}: x", work, work_source, reason, "external-ai",
            json.dumps(args, ensure_ascii=False), sql, json.dumps({"rows_returned": 1}), "",
            datetime.datetime(2026, 9, 8, 12, 20, 14))


def _leaky_row(step_index: int = 1):
    args = {"database": "masangsoftweb", "schema_name": "dbo",
            "table_name": "masangsoft_member_channeling_gzr"}
    return _row(step_index, "describe_table",
                "describe_table {'database': 'masangsoftweb', 'schema_name': 'dbo', "
                "'table_name': 'masangsoft_member_channeling_gzr'}",
                "external-ai", "DB와 dbo 스키마를 구분해 현재 정의를 확인하기 위해", args)


def test_l5_live_view_replaces_stored_tool_syntax(monkeypatch):
    monkeypatch.setattr(ai_tools, "_pg", lambda: _FakePg([_leaky_row()]))
    steps, _omitted = ai_tools._bridge_live_steps("t_abc")
    work = steps[0]["work"]
    assert "describe_table" not in work and "{" not in work, work
    assert "masangsoft_member_channeling_gzr" in work, "조사 대상이 사라졌다"
    assert steps[0]["work_source"] == "derived"
    assert steps[0]["reason"], "정상 사유까지 함께 버렸다"
    assert "intent" not in steps[0], "intent 는 식별자를 담는다 — payload 에서 빠져야 한다"
    done = app._resolve_step_display({
        "tool": "describe_table", "args": {"schema_name": "s", "table_name": "t"},
        "intent": "describe_table: describe_table {'schema_name': 's'}", "work": ""})
    assert "intent" not in done, "완료 경로 payload 에 intent 가 남아 있다(진행 경로와 비대칭)"


_WORK_FORMS = [
    ("", "빈 값(파생 가지)"),
    ("describe_table {'schema_name': 'coupon', 'table_name': 'dbo.T_COUPON'}", "적대 저장문구"),
    ("첨부 1286 본문 읽기", "정상 사람문구"),
]


@pytest.mark.parametrize("work,work_label", _WORK_FORMS)
@pytest.mark.parametrize("args,label", [(_REPRESENTATIVE_ARGS, "정상"), (_HOSTILE_ARGS, "적대")])
def test_l5_live_and_completed_paths_agree_for_every_tool(monkeypatch, args, label,
                                                          work, work_label):
    """같은 행이 두 경로에서 **같은 제목·같은 출처**로 나온다 — census 전 도구가 모수다.

    표본 1건으로 이 불변식을 지킬 수 없다는 것이 적대 검증의 지적이었다
    (`read_task_attachment` 의 첨부 파일명이 완료본에서만 사라졌는데 가드는 `describe_table`
    하나만 태워 통과했다).
    """
    mismatched = []
    for tool in sorted(app._tool_name_census()):
        src = "external-ai" if work else ""
        row = _row(1, tool, work, src, "", dict(args), str(args.get("sql") or ""))
        monkeypatch.setattr(ai_tools, "_pg", lambda r=row: _FakePg([r]))
        live = ai_tools._bridge_live_steps("t_abc")[0][0]
        done = app._resolve_step_display({
            "tool": tool, "args": dict(args), "sql": str(args.get("sql") or ""),
            "work": work, "work_source": src, "reason": "", "reason_source": "",
        })
        if (live["work"], live["work_source"], live["reason_source"]) != (
                done["work"], done["work_source"], done["reason_source"]):
            mismatched.append((tool, live["work"][:50], done["work"][:50],
                               live["work_source"], done["work_source"]))
    assert not mismatched, f"[{label}/{work_label}] 진행/완료 불일치: {mismatched}"


def test_l5_live_view_keeps_human_work(monkeypatch):
    row = list(_leaky_row())
    row[4] = "첨부 1286 본문 읽기"
    row[2] = "read_task_attachment"
    monkeypatch.setattr(ai_tools, "_pg", lambda: _FakePg([tuple(row)]))
    steps, _ = ai_tools._bridge_live_steps("t_abc")
    assert steps[0]["work"] == "첨부 1286 본문 읽기"
    assert steps[0]["work_source"] == "external-ai", "정상 문구의 출처를 덮어썼다"


def test_l5_activity_rows_keep_their_label(monkeypatch):
    """`tool == ""` 인 내부 동작 행은 파생 소스가 없다 — 라벨이 사라지면 안 된다."""
    row = list(_leaky_row())
    row[1], row[2], row[5] = "activity", "", "bridge-runtime"
    row[4] = "masangsoft_member 조회 결과를 검토합니다"
    row[8] = "{}"
    monkeypatch.setattr(ai_tools, "_pg", lambda: _FakePg([tuple(row)]))
    live = ai_tools._bridge_live_steps("t_abc")[0][0]
    done = app._resolve_step_display({"tool": "", "args": {}, "work": row[4],
                                      "work_source": "bridge-runtime"})
    assert live["work"] == row[4] == done["work"], (live["work"], done["work"])


# ── L6 배지 라벨 (프런트) ─────────────────────────────────────────────────────

_MAP_BLOCK = re.compile(r"export const TOOL_LABEL_MAP = \{(.*?)\n\};", re.S)
_MAP_KEY = re.compile(r'^\s{2}([a-z][a-z0-9_]*):\s*"([^"]+)"', re.M)

#: 배지 폭 예산(공백 포함). 실측: 헤더가 1줄을 유지하는 배지 폭 임계 ≈ 64.3px = 한글 5자+공백.
_LABEL_BUDGET = 6
#: 의도적 예외 — 예산을 넘기지만 어휘를 훼손하지 않는 편을 택했다 (§16.7 G12-c).
#: 대가: 패널 최소 폭(300px)에서 시각 요소가 다음 줄로 내려간다(배지 자체는 nowrap 이라 불변).
_LABEL_BUDGET_EXEMPT = {"describe_routine", "search_routines"}


def _label_map() -> dict[str, str]:
    src = _APP_JS.read_text(encoding="utf-8")
    block = _MAP_BLOCK.search(src)
    assert block, "app.js 에서 TOOL_LABEL_MAP 블록을 찾지 못했다"
    # 존재 단언이므로 주석 줄은 제외한다 (§16.7 G11-a).
    body = "\n".join(ln for ln in block.group(1).splitlines()
                     if not ln.lstrip().startswith("//"))
    pairs = dict(_MAP_KEY.findall(body))
    assert pairs, "라벨 표에서 키를 하나도 못 읽었다 — 파서가 죽었다"
    return pairs


def _missing_labels(names, labels) -> list[str]:
    return sorted(set(names) - set(labels))


def test_l6_label_map_covers_every_tool_the_server_can_emit():
    missing = _missing_labels(app._tool_name_census(), _label_map())
    assert not missing, (
        f"실행 단계 배지에 내부 식별자가 그대로 나가는 도구가 있다: {missing} — "
        "app.js 의 TOOL_LABEL_MAP 에 한국어 라벨을 추가하라")


def test_l6_negative_control_injects_the_defect_into_the_artifact(tmp_path):
    """결손을 **산출물(app.js)** 에 주입해 같은 파서를 태운다 (§16.7 G11-b).

    모수 쪽에 가짜 이름을 넣는 방식은 집합 연산이 동작함만 보인다 — 실제 실패 모드는
    「라벨 한 줄이 빠지는 것」이므로 그것을 주입해야 가드의 유효성이 증명된다.
    """
    src = _APP_JS.read_text(encoding="utf-8")
    victim = '  search_tables: "테이블 찾기",\n'
    assert victim in src, "주입 대상 라벨을 찾지 못했다 — 대조군이 정본과 어긋났다"
    mutated = tmp_path / "app.js"
    mutated.write_text(src.replace(victim, ""), encoding="utf-8")

    block = _MAP_BLOCK.search(mutated.read_text(encoding="utf-8"))
    body = "\n".join(ln for ln in block.group(1).splitlines()
                     if not ln.lstrip().startswith("//"))
    assert "search_tables" in _missing_labels(app._tool_name_census(),
                                              dict(_MAP_KEY.findall(body)))


def test_l6_labels_are_korean_and_within_budget():
    labels = _label_map()
    over = {k: v for k, v in labels.items()
            if len(v) > _LABEL_BUDGET and k not in _LABEL_BUDGET_EXEMPT}
    assert not over, (
        f"배지 라벨이 폭 예산({_LABEL_BUDGET}자)을 넘는다: {over} — 줄이거나 "
        "_LABEL_BUDGET_EXEMPT 에 사유와 함께 등재하라")
    ascii_only = {k: v for k, v in labels.items() if v.isascii()}
    assert not ascii_only, f"라벨이 한국어가 아니다(내부 어휘 노출 위험): {ascii_only}"


# ── L7 폴백이 식별자를 되돌려 주지 않는다 ─────────────────────────────────────

#: 제목을 그리는 프런트 모듈 **전수**. 모수를 `app.js` 하나로 두면 `app/progress.js` 의
#: 회귀가 무증상 통과한다(적대 검증 라운드 2 실측: 폴백을 되돌려도 48건 전건 PASS).
def _front_modules() -> list[pathlib.Path]:
    mods = [_APP_JS] + sorted((_STATIC / "app").glob("*.js"))
    assert len(mods) >= 3, f"프런트 모듈을 {len(mods)}개밖에 못 찾았다 — 경로가 바뀌었다"
    return mods


#: 주석 제거는 이 저장소의 **검증된 스캐너**를 재사용한다 — `test_side_panel_exclusive.scan_js`
#: 는 문자열·템플릿·정규식 리터럴을 모드 스택으로 세면서 주석만 지우고, 미종료 리터럴을 만나면
#: 예외를 던진다(조용히 틀린 결과를 내지 않는다). 직접 쓴 행 단위 휴리스틱은 블록 주석·중첩
#: 템플릿에서 실제 코드를 잘못 지워 **새 거짓 PASS** 를 만든다 — 그 파일의 docstring 이 같은
#: 경고를 담고 있고, 이 파일도 초판에서 정확히 그 함정을 밟았다.
try:
    from test_side_panel_exclusive import scan_js as _scan_js
except Exception:  # pragma: no cover — 그 파일이 옮겨지면 여기서 fail-loud 한다
    _scan_js = None


def _code_only(text: str) -> str:
    """존재/부재 단언용 — 주석(줄머리·꼬리·블록)을 제거하고 리터럴은 보존한다 (§16.7 G11-a)."""
    assert _scan_js is not None, (
        "공용 JS 스캐너(test_side_panel_exclusive.scan_js)를 import 하지 못했다 — "
        "주석 제거 없이 존재 단언을 걸면 자기 주석이 자기 단언을 통과시킨다")
    return _scan_js(text)[0]


def _fn_body(name: str) -> str:
    src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    m = re.search(rf"export function {name}\((.*?)\n\}}", src, re.S)
    assert m, f"app.js 에서 {name} 을 찾지 못했다"
    return m.group(1)


def test_l7_unknown_tool_badge_does_not_echo_the_identifier():
    body = _fn_body("toolLabel")
    assert 'TOOL_LABEL_MAP[toolName] || "도구"' in body, (
        f"모르는 도구의 배지가 식별자로 떨어진다: {body.strip()!r}")
    assert "|| toolName" not in body, "식별자 폴백이 남아 있다"


def test_l7_step_title_fallback_does_not_echo_the_identifier():
    body = _fn_body("stepTitleInfo")
    assert "toolLabel(s.tool)" in body, "제목 폴백이 라벨을 거치지 않는다"
    assert "isFallback: true" in body, (
        "폴백 여부를 호출측에 알리지 않는다 — 라벨과 나란히 놓을 때 같은 말을 두 번 하게 된다")
    for leak in ("s.intent", "|| s.tool"):
        assert leak not in body, f"제목 폴백이 내부 식별자를 그대로 쓴다: {leak}"


def test_l7_pending_bubble_does_not_repeat_the_label():
    """「테이블 구조 · 테이블 구조 단계」 — 라운드 1 수정이 만든 중복을 잠근다."""
    src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    assert "stepTitleInfo(latest, steps.length - 1)" in src
    assert "(lbl && !info.isFallback)" in src, "폴백 제목을 라벨과 함께 내보내고 있다"


def test_l7_every_step_title_renderer_uses_the_shared_helper():
    """모수는 렌더러 **전수**다 — 프런트 모듈 전체를 본다.

    라운드 2 가 실증했다: 모수를 `app.js` 하나로 두면 `app/progress.js` 의 폴백을 수정 전으로
    되돌려도 48건이 전건 통과한다. 「전수」를 선언한 가드가 한 파일만 보고 있었다.
    """
    offenders = []
    for mod in _front_modules():
        src = _code_only(mod.read_text(encoding="utf-8"))
        for hit in re.findall(r"(?:step|latest|s)\.intent", src):
            offenders.append((mod.name, hit))
    assert not offenders, (
        f"`intent`(=`<도구명>: …`) 를 아직 제목으로 쓰는 렌더러가 있다: {offenders}")
    app_src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    # 제목은 공용 헬퍼가 만든 값만 쓴다(폴백 억제 옵션 도입으로 `titleInfo.text` 경유).
    assert "const titleInfo = stepTitleInfo(step, idx);" in app_src
    assert "title.textContent = titleInfo.text;" in app_src
    # 활동 행도 공용 정화를 거친다(백틱 제거 + 인자 리터럴 강등).
    assert "stripDisplayTicks(step.work).trim()" in app_src
    assert "STEP_ARGS_LITERAL_RE.test(actWork)" in app_src
    # 진행 카드는 공용 헬퍼를 쓴다.
    prog = _code_only((_STATIC / "app" / "progress.js").read_text(encoding="utf-8"))
    assert "stepTitleText(latest" in prog, "progress.js 가 공용 제목 헬퍼를 쓰지 않는다"


def test_l7_display_strips_markdown_ticks():
    """서버 파생 문구의 백틱은 `textContent` 에서 글자 그대로 찍힌다 — 표시층에서 벗긴다."""
    src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    assert "export function stripDisplayTicks(text)" in src
    assert "stripDisplayTicks(s.work)" in src


def test_l7_server_still_keeps_the_ticks_for_the_ledger():
    """서버 원문의 백틱은 남는다 — 벗기는 것은 표시층 책임이다(감사 가치 보존)."""
    work, _s, _r, _rs = app._step_display_narration(
        {"tool": "describe_table", "args": {"schema_name": "s", "table_name": "t"},
         "work": "", "reason": ""})
    assert "`" in work, f"서버 파생에서 백틱이 사라졌다: {work!r}"


# ── L8 행위 하네스 배선 ───────────────────────────────────────────────────────

def _run_harness(app_js: str | None = None):
    node = shutil.which("node")
    argv = [node, str(_HARNESS)] + ([app_js] if app_js else [])
    return subprocess.run(argv, cwd=str(_HARNESS.parent), capture_output=True,
                          text=True, timeout=120)


def test_l7_negative_control_catches_a_progress_js_regression(tmp_path, monkeypatch):
    """`app/progress.js` 의 폴백을 수정 전으로 되돌리면 L7 가드가 **실제로 FAIL** 한다.

    라운드 2 가 지적한 형태 — 「전수」를 선언한 가드가 한 파일만 보고 있어 이 회귀가
    무증상 통과했다. 결손을 그 파일에 주입해 모수 확장이 유효함을 실증한다 (§16.7 G11-b).
    """
    src_dir = tmp_path / "static"
    (src_dir / "app").mkdir(parents=True)
    (src_dir / "app.js").write_text(_APP_JS.read_text(encoding="utf-8"), encoding="utf-8")
    for mod in sorted((_STATIC / "app").glob("*.js")):
        (src_dir / "app" / mod.name).write_text(mod.read_text(encoding="utf-8"), encoding="utf-8")
    prog = src_dir / "app" / "progress.js"
    text = prog.read_text(encoding="utf-8")
    victim = "      const label = stepTitleText(latest, steps.length - 1);"
    assert victim in text, "주입 대상을 찾지 못했다 — 대조군이 정본과 어긋났다"
    prog.write_text(text.replace(
        victim, '      const label = latest.work || latest.intent || latest.tool || "단계";'),
        encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_STATIC", src_dir)
    monkeypatch.setattr(sys.modules[__name__], "_APP_JS", src_dir / "app.js")
    with pytest.raises(AssertionError):
        test_l7_every_step_title_renderer_uses_the_shared_helper()


def test_l8_behaviour_harness_runs():
    """`make test` 는 node 를 설치한다(Makefile) — 부재는 skip 이 아니라 **실패**다.

    초판은 「CI 에 node 가 없다」는 기록을 근거로 탈출구를 뒀는데, 그 전제가 사실이 아니었고
    (같은 날 main 에 node 설치가 들어와 있었다) 그 탈출구가 곧 게이트 무력화 열쇠였다
    (§16.7 G15-b — 도구 부재를 통과로 흘리지 않는다).
    """
    assert _HARNESS.exists(), "행위 하네스 파일 부재"
    assert shutil.which("node"), (
        "node 가 없다 — `make test` 는 node 를 설치하므로 이 조건은 환경 결함이다. "
        "행위 하네스를 돌리지 못한 상태를 통과로 계상하지 않는다")
    proc = _run_harness()
    assert proc.returncode == 0, (
        f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}")


def test_l8_negative_control_harness_fails_on_injected_regression(tmp_path):
    """**결함을 주입한 사본**에 같은 하네스를 태워 FAIL 을 실증한다 (§16.7 G11-b)."""
    assert shutil.which("node"), "node 부재 — 위 테스트가 이미 실패로 표면화한다"
    src = _APP_JS.read_text(encoding="utf-8")
    mutated = src.replace(
        'return TOOL_LABEL_MAP[toolName] || "도구";',
        'return TOOL_LABEL_MAP[toolName] || toolName || "도구";',
    ).replace(
        "  if (s.tool) return { text: `${toolLabel(s.tool)} 단계`, isFallback: true };",
        "  if (s.intent) return { text: String(s.intent), isFallback: false };\n"
        "  if (s.tool) return { text: String(s.tool), isFallback: false };",
    )
    assert mutated != src, "결함 주입이 적용되지 않았다 — 대조군이 정본과 같아졌다"
    copy = tmp_path / "app.js"
    copy.write_text(mutated, encoding="utf-8")
    proc = _run_harness(str(copy))
    assert proc.returncode != 0, (
        "결함을 주입했는데 하네스가 통과한다 — 이 하네스는 무엇도 검사하지 않는다\n"
        + proc.stdout[-2000:])
    assert proc.stdout.count("\nFAIL ") >= 4, (
        f"실패 항목이 너무 적다 — 하네스가 다른 이유로 죽었을 수 있다:\n{proc.stdout[-2000:]}")


def test_l8_python_guards_also_fail_on_injected_regression(tmp_path, monkeypatch):
    """파이썬 층 소스 단언도 결함 주입에 반응하는지 실증한다.

    주입 형태를 「고친 코드는 주석으로만 남기고 결함을 되살리는」 것으로 잡아, 주석 제거가
    실제로 동작함까지 함께 보인다 (§16.7 G11-a — 자기 주석이 자기 단언을 통과시키지 않는다).
    """
    src = _APP_JS.read_text(encoding="utf-8")
    mutated = src.replace(
        'return TOOL_LABEL_MAP[toolName] || "도구";',
        '// return TOOL_LABEL_MAP[toolName] || "도구";\n'
        '  return TOOL_LABEL_MAP[toolName] || String(toolName || "도구");',
    )
    assert mutated != src
    copy = tmp_path / "app.js"
    copy.write_text(mutated, encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "_APP_JS", copy)
    with pytest.raises(AssertionError):
        test_l7_unknown_tool_badge_does_not_echo_the_identifier()


# ── L9 조치의 봉인 (§16.7 G11-b — 되돌리면 붉어져야 한다) ─────────────────────
#
# 라운드 3 확인 검증이 실측했다: 라운드 1~3 이 고친 6건을 되돌려도 55건이 전건 초록이었다.
# 「고쳤다」와 「고친 상태가 유지된다」는 다르다 — 각 조치를 그 조치가 지키는 **관측 가능한
# 결과**로 잠근다. 소스 문자열이 아니라 함수 산출을 본다.

_LIVE_REASONS_WITH_TOOL_NAME = [
    # 라이브 원장에서 뽑은 정상 사유 — (b) 를 사유 축에 켜면 이 문장들이 통째로 사라진다.
    "Gold/GemV2/Currency 모두 dbLog 내 테이블이므로 단일 execute_sql 쿼리로 UNION 집계하여 "
    "모든 재화 소모를 통합 분석",
    "execute_sql의 기본 데이터베이스가 어디인지 확인하기 위해",
]


@pytest.mark.parametrize("reason", _LIVE_REASONS_WITH_TOOL_NAME)
def test_l9_reason_axis_wiring_is_sealed_at_the_seam(reason):
    """이음매가 사유에 `allow_tool_names=False` 를 **실제로 넘기는지** 본다.

    기존 L2 는 판정기를 직접 호출해 축의 «의미» 만 봤다. 이음매의 인자를 뒤집으면 라이브
    사유 21건이 사라지는데 그 배선을 보는 단언이 없었다(라운드 3 F1).
    """
    _w, _ws, out, src = app._step_display_narration(
        {"tool": "execute_sql", "args": {"sql": "SELECT 1"}, "work": "", "reason": reason,
         "reason_source": "llm"})
    assert out == reason, "이음매가 정상 사유를 지웠다 — allow_tool_names 배선이 뒤집혔다"
    assert src == "llm"


def test_l9_server_rule_a_is_anchored():
    """서버 규칙 (a) 의 맨앞 앵커가 살아 있는지 — 앵커를 빼면 산문 속 JSON 이 전부 죽는다.

    같은 계약의 클라이언트 층은 하네스가 이미 잠그고 있었는데 서버 층만 무봉인이었다.
    """
    prose = "설정값 {'theme': 'dark'} 이 든 컬럼을 확인한다"
    assert not app._step_text_is_tool_syntax(prose, "describe_table"), (
        "산문 속 JSON 이 도구 표기로 판정된다 — 규칙 (a) 의 앵커가 사라졌다")
    assert app._step_text_is_tool_syntax("{'schema_name': 'coupon'} 확인", "describe_table"), (
        "호출 형태(맨앞 리터럴)를 놓친다 — 앵커를 너무 좁혔다")
    assert app._step_text_is_tool_syntax(
        "describe_table {'schema_name': 'coupon'}", "describe_table")


#: 조치가 고정한 **문구의 값**. 어휘·길이만 검사하면 조용한 회귀가 통과한다(라운드 3 F2).
_PHRASE_CONTRACT = [
    # (tool, args, 반드시 포함, 절대 포함 금지, 사유)
    ("scratch_sql", {"sql": "DELETE FROM tmp.t"}, "SQL을 실행한다", "조회한다",
     "이 도구는 DELETE/DROP 도 받는다 — 읽기로 기술하면 변경을 조회로 오기술한다"),
    ("scratch_import", {"dest_table": "tmp.orders"}, "tmp.orders", None,
     "인자를 버리면 옆 행은 대상을 말하는데 이 행만 못 말하는 비대칭이 생긴다"),
    ("scratch_reset", {}, "비운다", "삭제",
     "「임시 삭제」는 «임시로 삭제(되돌릴 수 있다)» 로 먼저 읽힌다"),
    ("list_schemas", {}, "DB(스키마)", None,
     "배지 「DB 목록」과 제목의 명사가 갈리면 두 동작으로 읽힌다"),
]


@pytest.mark.parametrize("tool,args,must,must_not,why", _PHRASE_CONTRACT)
def test_l9_phrase_values_are_pinned(tool, args, must, must_not, why):
    work, _ws, _r, _rs = app._step_display_narration(
        {"tool": tool, "args": dict(args), "sql": str(args.get("sql") or ""),
         "work": "", "reason": ""})
    assert must in work, f"{tool}: {why} — 얻은 문구: {work!r}"
    if must_not:
        assert must_not not in work, f"{tool}: {why} — 얻은 문구: {work!r}"


def test_l9_no_derived_phrase_describes_a_write_as_a_read():
    """파생 문구 전수 — 변경을 받을 수 있는 도구를 「조회」로 기술하지 않는다."""
    writes = ("scratch_sql", "scratch_import", "scratch_reset", "update_attachment",
              "materialize_attachment")
    offenders = []
    for tool in writes:
        work, _ws, _r, _rs = app._step_display_narration(
            {"tool": tool, "args": dict(_REPRESENTATIVE_ARGS),
             "sql": _REPRESENTATIVE_ARGS["sql"], "work": "", "reason": ""})
        if "조회한다" in work:
            offenders.append((tool, work))
    assert not offenders, f"변경 가능 도구를 조회로 기술한다: {offenders}"


def test_l9_ask_payload_goes_through_the_display_seam():
    """`/api/ask` 응답의 `steps` 도 이음매를 통과한다 — 그 경로만 우회하면 `intent` 가 샌다."""
    # 파이썬 소스라 JS 스캐너를 쓰지 않는다 — 주석은 `#` 이고, 단언 문자열이 그 파일의
    # 주석에 등장하지 않음을 아래에서 함께 확인한다(§16.7 G11-a).
    conv = (_STATIC.parents[0] / "routers" / "conversations.py")
    src = conv.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "app._resolve_step_display(_s) if isinstance(_s, dict) else _s" in code, (
        "/api/ask 의 steps 가 표시 이음매를 거치지 않는다")


def test_l9_derived_reason_is_visually_distinguished():
    """서버가 역산한 근거를 AI 가 말한 근거와 같은 라벨로 그리지 않는다 (라운드 3 C3)."""
    src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    assert 'String(step.reason_source || "") === "derived"' in src
    assert '"근거(추정)"' in src, "파생 근거의 라벨이 구분되지 않는다"


def test_l9_side_panel_suppresses_the_duplicated_fallback_title():
    """배지가 이미 그려진 자리에서 폴백 제목을 되풀이하지 않는다 (라운드 3 C1)."""
    src = _code_only(_APP_JS.read_text(encoding="utf-8"))
    assert "hideFallbackTitle" in src
    assert "hideFallbackTitle: !!step.tool" in src, "사이드 패널이 옵션을 넘기지 않는다"
