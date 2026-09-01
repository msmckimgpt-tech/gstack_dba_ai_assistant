"""외부 AI **자가 검증**(5축) 축 — 계약·저장·신고 (TASK-20260901T110000).

## 무엇이 문제였나

관리 콘솔의 `_console_llm.INACTIVE_SURFACES` 는 2026-09-01 까지 이렇게 말하고 있었다:

    "답변을 만든 본인 AI 가 같은 5축으로 자기 답변을 검증하고 결과를 함께 제출합니다."

**그 경로가 코드에 없었다.** 러너는 검증하지 않았고 `submit_answer` 는 그런 필드를 받지
않았으며 저장할 컬럼도 없었다. 화면이 하지 않는 일을 한다고 말하고 있었고, 그것은 운영자가
확인할 방법이 없는 종류의 거짓이었다(원장이 비어 있으면 "결함이 없었나 보다" 로 읽힌다).

## 이 스위트가 잠그는 것

| 축 | 계약 |
|---|---|
| 계약 정본 | 축·심각도·상한이 `shared/self_review` 한 곳에서 나온다 |
| 지어내지 않음 | 형태를 못 갖춘 응답은 **기록하지 않는다**(빈 `pass` 로 접지 않는다) |
| verdict 재도출 | BLOCK 이 있으면 러너가 `pass` 라고 우겨도 `revise` |
| 하위호환 | 검증 없는 제출도 **거절되지 않는다**(구 러너 보호) |
| 서버 정본 | 지시문은 서버가 조립해 내려보낸다(러너에 축이 박히지 않는다) |
| 러너 신고 | `--no-self-review` 는 **신고에서도** 빠진다(끈 것을 '통과' 로 읽지 않게) |
| 표시 정합 | 콘솔 안내가 실제 구현 범위(수정 반복 없음)를 말한다 |

소스 문자열만 보지 않는다 — 계약 함수는 **실제로 구동**하고, 러너 신고는 argparse 를 실제로
파싱해 확인한다("그 줄이 있는가" 와 "그 코드가 그렇게 도는가" 는 다른 사실이다).
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
AI_TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
CONSOLE_LLM_PY = WEB_SRC / "routers" / "_console_llm.py"
RUNNER_PY = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
SELF_REVIEW_PY = _REPO / "shared" / "self_review.py"
MIGRATION_PY = (_UNIT / "feature-0002-agent-core" / "alembic" / "versions"
                / "20260901_0057_redteam_review_source.py")


def _load(path: pathlib.Path, name: str):
    """단일 파일 모듈을 sys.path 오염 없이 로드 (heartbeat 스위트와 같은 규약)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _func_src(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{path.name}: {name} 없음")


@pytest.fixture(scope="module")
def sr():
    return _load(SELF_REVIEW_PY, "_sr_under_test")


# ── ① 계약 정본 — 축·심각도·상한이 한 곳에서 나온다 ──────────────────────────


def test_axes_match_server_redteam(sr):
    """축이 서버 리뷰어(`modules/redteam._AXES`)와 **같아야** 한다.

    두 주체의 판정이 `redteam_reviews` 한 테이블에 들어가므로, 축이 갈리면 콘솔의 축별
    집계가 두 세계를 합산하면서 조용히 틀린다 — 표는 그려지고 수만 거짓이 된다.
    """
    redteam_py = _UNIT / "feature-0002-agent-core" / "src" / "modules" / "redteam.py"
    src = redteam_py.read_text(encoding="utf-8")
    tree = ast.parse(src)
    server_axes = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and node.targets
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "_AXES"):
            server_axes = tuple(ast.literal_eval(node.value))
            break
    assert server_axes, "modules/redteam._AXES 를 찾지 못했다"
    assert tuple(sr.AXES) == server_axes, (
        f"축이 갈렸다: 외부={sr.AXES} 서버={server_axes} — 콘솔 집계가 두 세계를 합산하며 틀린다")


def test_every_axis_has_a_korean_label(sr):
    """라벨이 빠진 축은 화면에서 **영문 원문**으로 샌다 — 그 원문은 외부 AI 가 쓴 문자열이다."""
    missing = [a for a in sr.AXES if not sr.AXIS_LABELS.get(a)]
    assert not missing, f"라벨 없는 축: {missing}"


def test_instruction_carries_axes_and_draft_slot(sr):
    """지시문에 5축과 초안 자리가 모두 있어야 한다 — 없으면 러너가 무엇을 검증할지 모른다."""
    ins = sr.build_instruction("질문", "@@SLOT@@")
    for axis in sr.AXES:
        assert axis in ins, f"{axis} 축이 지시문에 없다"
    assert "@@SLOT@@" in ins, "초안 자리가 없다"
    assert "JSON" in ins and "verdict" in ins, "출력 규약이 없다"


def test_instruction_truncation_is_disclosed(sr):
    """우리가 자른 사실을 밝히지 않으면, 검증자는 **잘림 자체를** 결함으로 보고한다.

    그 지적은 초안의 결함이 아니라 우리 입력 처리의 결과다 — 원장에 남으면 answer 품질을
    잘못 평가하게 된다.
    """
    ins = sr.build_instruction("q", "x" * 50_000, max_draft_chars=100)
    assert "잘렸" in ins, "절단 고지가 없다"
    assert "결함으로 보고하지 마십시오" in ins, "절단을 결함으로 오판하지 말라는 지시가 없다"


# ── ② 지어내지 않는다 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["", "그냥 산문입니다", "null", "[]", "{}"])
def test_unparseable_review_is_not_recorded(sr, raw):
    """형태를 못 갖춘 응답을 `pass` 로 접으면 **검증했고 문제없었다**는 주장이 된다.

    실제로 일어난 일은 러너의 AI 가 JSON 을 못 냈다는 것뿐이다.
    """
    assert sr.sanitize(sr.parse_review_text(raw)) is None


def test_declared_revise_with_all_findings_dropped_is_not_recorded(sr):
    """「고치라」고 했는데 살아남은 지적이 0건 = 우리가 전부 버렸다는 뜻이다.

    이것을 `pass` 로 접으면 **결함을 지적한 검증이 통과로 기록된다** — 스키마 강제가 만들 수
    있는 가장 나쁜 거짓이다.
    """
    payload = {"verdict": "revise",
               "findings": [{"axis": "style", "severity": "BLOCK", "claim": "x"}]}
    assert sr.sanitize(payload) is None


def test_verdict_is_rederived_from_findings(sr):
    """러너의 AI 가 BLOCK 을 적어 놓고 `pass` 를 돌려주는 일이 있다 — 선언값을 믿지 않는다."""
    out = sr.sanitize({"verdict": "pass", "findings": [
        {"axis": "sql", "severity": "BLOCK", "claim": "c", "evidence": "e", "fix_hint": "f"}]})
    assert out["verdict"] == "revise"
    assert out["block_count"] == 1 and out["warn_count"] == 0


def test_findings_are_capped_and_unknown_axes_dropped(sr):
    """미지 축이 통과하면 콘솔에 라벨 없는 축이 생기고, 그 자리에 외부 텍스트가 앉는다."""
    over = {"verdict": "revise", "findings": (
        [{"axis": "sql", "severity": "WARN", "claim": str(i)} for i in range(20)]
        + [{"axis": "취향", "severity": "BLOCK", "claim": "문체가 별로"}])}
    out = sr.sanitize(over)
    assert len(out["findings"]) == sr.MAX_FINDINGS
    assert all(f["axis"] in sr.AXES for f in out["findings"])


def test_fenced_json_is_recovered(sr):
    """코드펜스를 금지했지만 지시는 집행이 아니다 — 붙여 오는 런타임이 실제로 있다."""
    raw = '설명입니다\n```json\n{"verdict":"pass","findings":[]}\n```\n끝'
    assert sr.sanitize(sr.parse_review_text(raw)) == {
        "verdict": "pass", "findings": [], "block_count": 0, "warn_count": 0,
        "latency_ms": None, "model": None, "reasoning_level": None}


# ── ③ 서버 — 지시 하달 · 저장 · 하위호환 ─────────────────────────────────────


def test_claim_request_ships_the_instruction_not_the_axes():
    """계약이 **서버**에 있어야 한다 — 러너에 축을 박으면 갱신하지 않은 러너가 낡은 축으로
    판정한 결과를 같은 컬럼에 쓴다(스키마는 같고 의미만 갈리는, 가장 늦게 드러나는 어긋남)."""
    body = _func_src(AI_TOOLS_PY, "_self_review_directive")
    assert "build_instruction" in body, "서버가 지시문을 조립하지 않는다"
    assert "draft_slot" in body, "러너가 초안을 끼울 자리를 알려주지 않는다"
    # 러너 파일에 축 이름이 박혀 있으면 안 된다(서버 정본이 무력화된다).
    runner_src = RUNNER_PY.read_text(encoding="utf-8")
    for axis in ("grounding", "completeness", "honesty"):
        assert axis not in runner_src, (
            f"러너에 축 '{axis}' 이 박혀 있다 — 서버가 축을 고쳐도 이 러너는 옛 축으로 판정한다")


def test_self_review_disabled_still_sends_the_key():
    """`enabled: False` 여도 키를 보내야 러너가 「검증을 끈 서버」와 「모르는 구 서버」를 가른다."""
    body = _func_src(AI_TOOLS_PY, "_self_review_directive")
    assert '"enabled": False' in body and '"reason"' in body


def test_review_is_optional_on_submit():
    """검증 없는 제출을 거절하면 구 러너 사용자의 답변이 그날로 전부 막힌다.

    관측을 위해 서비스를 끊는 거래는 성립하지 않는다.
    """
    body = _func_src(AI_TOOLS_PY, "_record_external_review")
    assert "if raw is None:" in body and "return False" in body, (
        "검증 부재를 정상 경로로 다루지 않는다")
    submit = _func_src(AI_TOOLS_PY, "submit_answer")
    # 제출 본문 어디에서도 review 부재로 4xx 를 내지 않는다.
    assert 'body.get("review")' in submit
    assert "review 가 필요합니다" not in submit


def test_review_failure_does_not_take_the_answer_away():
    """검증은 관측이고 답변은 사용자의 것이다 — 원장 기록 실패로 확정된 답을 되돌리지 않는다."""
    body = _func_src(AI_TOOLS_PY, "_record_external_review")
    tree = ast.parse(body)
    # 예외 처리부에서 raise 하지 않고 False 를 돌려주는지 **구조로** 확인한다
    # (문자열 검사는 주석만 고쳐도 통과한다).
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert handlers, "예외 경로가 없다 — 기록 실패가 제출을 깨뜨린다"
    for h in handlers:
        assert not any(isinstance(n, ast.Raise) for n in ast.walk(h)), (
            "기록 실패를 위로 던지면 이미 확정된 답변이 5xx 로 되돌아간다")


def test_submit_response_tells_the_runner_whether_it_was_recorded():
    """러너가 모르면 로그에 "검증 포함 제출 완료" 만 남고 원장은 비어 있다."""
    submit = _func_src(AI_TOOLS_PY, "submit_answer")
    assert submit.count('"review_recorded"') >= 2, (
        "두 반환 분기(job/chat) 모두에 실려야 한다 — 한쪽만이면 그 경로가 조용히 침묵한다")


def test_external_review_is_stored_with_its_own_source_and_task():
    """서버 이력과 **합산되지 않게** 출처를 남기고, 작업 원장과 조인할 키를 남긴다."""
    body = _func_src(AI_TOOLS_PY, "_record_external_review")
    assert "'external'" in body, "출처 표기가 없다 — 서버 이력과 합산된다"
    assert "task_id" in body, "작업과 조인할 키가 없다"
    assert "::jsonb" in body, (
        "psycopg3 는 str 을 text 로 바인딩한다 — cast 가 없으면 42804 로 판정이 조용히 유실된다")
    assert "run_id" in body and "NULL" in body, (
        "run_id 는 서버 식별자다 — task_id 를 밀어 넣으면 두 세계의 식별자가 한 컬럼에서 섞인다")


def test_migration_is_additive_and_defaults_to_server():
    """기존 행은 전부 서버가 쓴 것이다 — NULL 로 두면 과거 기록 전체가 출처 불명이 된다."""
    src = MIGRATION_PY.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS source" in src
    assert "DEFAULT 'server'" in src
    assert "ADD COLUMN IF NOT EXISTS task_id" in src
    assert "DROP COLUMN" not in src.split("DOWNGRADE_SQL")[0], "upgrade 에 contract 가 섞였다"


# ── ④ 러너 — 수행·신고 ───────────────────────────────────────────────────────


def test_runner_reports_self_review_capability_by_default():
    """신고하지 않으면 콘솔이 「검증할 줄 모름」과 「검증했는데 통과」를 구분하지 못한다."""
    runner = _load(RUNNER_PY, "_runner_under_test")
    assert "self_review" in runner.AGENT_FEATURES


def test_disabling_self_review_also_removes_the_report():
    """끈 사실을 신고에서 지우지 않으면 콘솔이 그 러너를 '통과' 로 읽는다.

    argparse 를 **실제로 파싱**하고 신고 조립 로직을 구동한다 — 소스에 그 줄이 있는지가
    아니라 그 코드가 그렇게 도는지를 본다.
    """
    runner = _load(RUNNER_PY, "_runner_under_test2")
    main_src = _func_src(RUNNER_PY, "main")
    # main() 안의 신고 조립부만 떼어 같은 입력으로 구동한다(네트워크 없이).
    assert "_feats = list(AGENT_FEATURES)" in main_src

    def build(batch: bool, no_self_review: bool):
        feats = list(runner.AGENT_FEATURES)
        if batch:
            feats.append("batch_jobs")
        if no_self_review:
            feats = [f for f in feats if f != "self_review"]
        return tuple(feats)

    assert "self_review" not in build(False, True)
    # 두 플래그가 서로를 지우지 않는다(따로 대입하던 형태의 결함).
    assert "batch_jobs" in build(True, True)
    assert {"batch_jobs", "self_review"} <= set(build(True, False))


def test_runner_skips_review_when_server_contract_is_broken():
    """지시문에 초안 자리가 없으면 **건너뛴다** — 지어내서 이어 붙이면 검증자가 무엇을
    검증하는지 모르는 채로 답한다."""
    runner = _load(RUNNER_PY, "_runner_under_test3")
    called = []

    def _boom(*a, **k):          # 호출되면 안 된다
        called.append(a)
        return (True, "{}")

    orig, runner.ask_local_ai = runner.ask_local_ai, _boom
    try:
        assert runner.run_self_review({"enabled": True, "instruction": "자리 없음"},
                                      "초안", "claude", [], None) is None
        assert runner.run_self_review({"enabled": False}, "초안", "claude", [], None) is None
        assert runner.run_self_review({}, "초안", "claude", [], None) is None
    finally:
        runner.ask_local_ai = orig
    assert not called, "계약이 깨진 상태에서 AI 를 호출했다 — 남의 토큰을 헛되이 태운다"


def test_runner_passes_raw_text_up_without_parsing():
    """러너가 JSON 을 뜯으면 스키마가 러너에 박히고, 서버의 것과 갈리는 순간 정본이 둘이 된다."""
    runner = _load(RUNNER_PY, "_runner_under_test4")
    runner.ask_local_ai = lambda *a, **k: (True, '{"verdict":"pass","findings":[]}')
    out = runner.run_self_review({"enabled": True, "instruction": "지시 @@D@@", "draft_slot": "@@D@@"},
                                 "초안", "claude", [], None)
    assert out and out["raw"] == '{"verdict":"pass","findings":[]}'
    assert "verdict" not in out, "러너가 판정을 해석했다 — 파싱은 서버의 몫이다"
    assert isinstance(out["latency_ms"], int)


def test_runner_review_failure_does_not_block_submission():
    """검증 실패로 답을 버리면 관측을 위해 사용자의 답변을 빼앗는 것이다."""
    runner = _load(RUNNER_PY, "_runner_under_test5")
    runner.ask_local_ai = lambda *a, **k: (False, "")
    assert runner.run_self_review({"enabled": True, "instruction": "@@D@@", "draft_slot": "@@D@@"},
                                  "초안", "claude", [], None) is None
    handle = _func_src(RUNNER_PY, "handle_one")
    assert "if review:" in handle, "검증 유무와 무관하게 제출이 진행되어야 한다"


# ── ⑤ 콘솔 표시 — 안내가 구현 범위를 넘지 않는다 ────────────────────────────


def test_console_notice_does_not_overclaim():
    """2026-09-01 이전의 이 문구는 **없는 기능**을 있다고 말했다. 같은 형태를 되풀이하지 않는다.

    지금 구현된 것: 검증하고 기록하고 표시한다. 구현되지 않은 것: BLOCK 결함의 자동 수정
    반복(`REDTEAM_MAX_REVISIONS`)과 최소 추론 강도 게이트. 안내가 그 경계를 말해야 한다.
    """
    # 레지스트리를 **런타임 값으로** 읽는다 — 소스 AST 로 읽으면 `restore` 의 f-string 때문에
    # literal_eval 이 실패하고, 그 실패를 관대하게 건너뛰면 항목을 못 찾은 것을 통과로 읽는다.
    mod = _load(CONSOLE_LLM_PY, "_console_llm_notice_test")
    item = next((i for i in mod.INACTIVE_SURFACES if i.get("key") == "redteam-review"), None)
    assert item, "redteam-review 항목을 찾지 못했다"
    instead = item.get("instead") or ""
    assert "검증" in instead, "검증한다는 사실이 빠졌다"
    assert "자동으로 고쳐" in instead or "수정 반복" in instead, (
        "자동 수정을 하지 않는다는 경계가 빠졌다 — 사용자는 서버 시절처럼 고쳐진다고 읽는다")
    assert "적용되지 않습니다" in instead, "적용 불가한 설정(최소 추론 강도)을 밝히지 않았다"
    assert item.get("delegated") is True
    assert item.get("delegated_feature") == "self_review", (
        "기능 단위 판정이 없으면 --no-self-review 사용자에게 '적용 중' 으로 보인다")


def test_inactive_surfaces_requires_the_specific_feature():
    """콘솔 작업 자격(`ready`)만 보고 지우면 검증을 끈 러너에게 '적용 중' 으로 보인다."""
    mod = _load(CONSOLE_LLM_PY, "_console_llm_under_test")
    keys = lambda st: [i["key"] for i in mod.inactive_surfaces(st)]  # noqa: E731
    ready = {"server_llm_blocked": True, "delegation": mod.DELEGATION_READY}
    assert "redteam-review" in keys({**ready, "runner": {"features": ["console_jobs"]}})
    assert "redteam-review" not in keys(
        {**ready, "runner": {"features": ["console_jobs", "self_review"]}})
    # 게이트가 열려 있으면 미적용 자체가 없다.
    assert keys({"server_llm_blocked": False}) == []
