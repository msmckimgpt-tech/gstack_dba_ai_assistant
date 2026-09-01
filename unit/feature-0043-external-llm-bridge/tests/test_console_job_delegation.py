"""feature-0043 TASK-20260831T100000 — 콘솔 작업 **위임 배선** 계약.

이 cycle 이 여는 것은 "AI 가 잘 답하는가" 가 아니라 **배선이 끝까지 이어지는가** 다. 이
feature 가 반복해 겪은 결함(P0-E·P0-U)이 값이 아니라 연결이었고, 그 부류는 헬퍼 단위
테스트를 전부 통과하기 때문이다.

그래서 여기서는 이음매만 본다: 조립부와 위임이 **같은 형식**을 말하는가 · 위임이 종전
경로를 가로채지 않는가 · 미배선 종류가 대기열에 들어가지 않는가.
"""
from __future__ import annotations

import pathlib

import pytest

from shared import bridge_tasks as bt


_SRC = pathlib.Path(__file__).resolve().parents[2]
_ADMIN_META = _SRC / "feature-0003-agent-web-ui" / "src" / "routers" / "admin_metadata.py"
_PROMPT_CTX = _SRC / "feature-0003-agent-web-ui" / "src" / "routers" / "_prompt_context.py"
_CONSOLE_JOBS = _SRC / "feature-0003-agent-web-ui" / "src" / "routers" / "_console_jobs.py"
_RUNNER = _SRC / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


# ── 레지스트리: 선언과 실제 배선이 어긋나지 않는다 ────────────────────────────────────

def test_every_wired_kind_has_a_store_route_or_is_review():
    """`wired` 인 종류는 **결과가 도달할 곳**이 있어야 한다.

    자동기입형(`apply='store'`)인데 반영 경로가 없으면 AI 는 실제로 작업을 수행하고
    산출물은 어디에도 도달하지 않는다 — "제출됐지만 반영 실패" 만 남는 형태.
    """
    src = _CONSOLE_JOBS.read_text(encoding="utf-8")
    for kind, spec in bt.JOB_SPECS.items():
        if not spec.get("wired"):
            continue
        if spec["apply"] == "store":
            assert f'"{kind}"' in src, (
                f"{kind} 는 자동기입형인데 _STORE_ROUTES 에 경로가 없다")


def test_unwired_kinds_are_refused_at_enqueue():
    """미배선 종류는 **대기열에 들어가지 않는다**.

    넣으면 개인 AI 가 실제로 가져가 토큰과 시간을 쓰고, 남는 것은 반영 실패뿐이다
    (P0-S 의 "아무도 못 집는 작업을 쌓지 않는다" 를 반영 축으로 옮긴 것).
    """
    unwired = [k for k, v in bt.JOB_SPECS.items() if not v.get("wired")]
    if not unwired:
        pytest.skip("현재 미배선 종류 없음 — 전 종류 배선 완료")
    with pytest.raises(bt.ConsoleJobRejected):
        bt.enqueue_console_job(None, account_id=1, job_kind=unwired[0], prompt="x")


def test_unknown_kind_is_refused_not_guessed():
    """모르는 종류를 관대하게 받지 않는다 — 추측하면 산출물이 어디에도 도달하지 않는다."""
    with pytest.raises(bt.ConsoleJobRejected):
        bt.enqueue_console_job(None, account_id=1, job_kind="no_such_kind", prompt="x")


def test_empty_prompt_is_refused():
    """빈 프롬프트로 적재하면 AI 가 빈 작업을 가져간다."""
    with pytest.raises(bt.ConsoleJobRejected):
        bt.enqueue_console_job(None, account_id=1, job_kind="metadata_suggest", prompt="   ")


# ── 형식 계약: 조립부와 위임이 같은 말을 한다 ─────────────────────────────────────────

def test_metadata_suggest_is_text_not_json():
    """단건 자동완성의 기존 프롬프트는 **본문만** 요구한다 — 위임도 같은 형식이어야 한다.

    `json` 으로 잡으면 위임 프롬프트가 조립부와 **모순된 형식**을 요구하고, AI 가 무엇을
    내든 한쪽이 틀린다(그리고 그 실패는 폼에 이상한 값이 채워지는 것으로만 보인다).
    """
    assert bt.JOB_SPECS["metadata_suggest"]["response"] == "text"
    body = _ADMIN_META.read_text(encoding="utf-8")
    fn = body[body.index("def _metadata_suggest_messages("):]
    fn = fn[:fn.index("\ndef ")]
    assert "본문만 출력" in fn or "텍스트만 출력" in fn, (
        "조립부가 더 이상 본문만 요구하지 않는다 — response 형식을 재확인하라")


def test_metadata_bulk_is_json_because_the_server_parses_it():
    """일괄은 서버가 `_metadata_parse_json_object` 로 판다 — JSON 이 맞다."""
    assert bt.JOB_SPECS["metadata_bulk"]["response"] == "json"
    body = _ADMIN_META.read_text(encoding="utf-8")
    assert "_metadata_parse_json_object(text)" in body


# ── 이음매: 위임은 조립 뒤·호출 앞 한 지점에만 ───────────────────────────────────────

def test_delegation_sits_between_assembly_and_llm_call():
    """위임 훅이 `messages` 조립 **뒤**, LLM 호출 **앞**에 있다.

    앞에 두면 조립부의 자산(스키마 grounding·제품 바인딩)을 못 쓰고, 뒤에 두면 게이트가
    닫힌 배포에서 위임할 기회 없이 503 이 된다.
    """
    body = _ADMIN_META.read_text(encoding="utf-8")
    for msg_var, call in (("_metadata_suggest_messages(", "task=\"summary\""),
                          ("_metadata_bulk_describe_messages(", "task=\"prompt_gen\"")):
        i_assemble = body.index(msg_var)
        i_delegate = body.index("_console_jobs.maybe_delegate(", i_assemble)
        i_call = body.index(call, i_assemble)
        assert i_assemble < i_delegate < i_call, f"{msg_var} 이음매 순서가 어긋났다"


def test_prompt_assemblers_delegate_before_acquiring_a_client():
    """세 프롬프트 조립부 모두 클라이언트 취득 **앞**에서 위임을 시도한다."""
    body = _PROMPT_CTX.read_text(encoding="utf-8")
    # ⚠ **호출부만** 센다. 정의부(`def _maybe_delegate_prompt(delegate_ctx, messages):`)도
    #   같은 부분문자열을 포함하므로, 그것까지 세면 개수 계약이 1 만큼 어긋난다(실제로 그랬다).
    call = "_delegated = _maybe_delegate_prompt(delegate_ctx, messages)"
    assert body.count(call) == 3, (
        f"세 조립부 중 {body.count(call)}곳만 위임 훅을 갖는다 — 경로에 따라 되기도 안 되기도 한다")
    for m in _iter_positions(body, call):
        nxt = body.index("openai_client = _get_llm_client(model=llm_model)", m)
        assert m < nxt


def test_autonomous_sweep_is_not_delegated():
    """무인 sweep 은 위임 대상이 아니다.

    그 자리에는 결과를 기다릴 사람이 없고, 남의 계정 러너를 배경 작업에 태울 근거도 없다
    (배치는 `batch_jobs` **명시 동의**를 받은 별도 축이다).
    """
    body = _PROMPT_CTX.read_text(encoding="utf-8")
    fn = body[body.index("def _auto_prompt_sweep_once("):]
    fn = fn[:fn.index("\ndef ")]
    assert "delegate_ctx" not in fn, "무인 sweep 이 위임 컨텍스트를 넘긴다"


def _iter_positions(hay: str, needle: str):
    i = hay.find(needle)
    while i >= 0:
        yield i
        i = hay.find(needle, i + 1)


# ── 러너: 콘솔 작업에 대화 프레이밍을 씌우지 않는다 ─────────────────────────────────

def test_runner_declares_features_and_version():
    """러너가 기능·버전을 신고한다 — 그것이 서버의 배급 자격이다.

    ⚠ 버전은 하한과 **같아야 하는 것이 아니라 하한 이상**이어야 한다
    (TASK-20260901T110000). 종전 단언은 등호였는데, 그러면 러너를 고칠 때마다 서버 하한을
    함께 올리도록 강제되고 — 하한이 오르는 순간 **아직 갱신하지 않은 전 사용자의 콘솔 작업이
    끊긴다.** 두 값은 다른 질문에 답한다: 하한은 "무엇을 거절하는가", 버전은 "이 파일이
    무엇인가". 판정은 서버의 비교 함수(`_console_llm.version_at_least`)를 그대로 쓴다 —
    여기서 새로 비교하면 두 곳의 순서 규칙이 갈릴 준비를 마친다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    feats_line = src.split("AGENT_FEATURES: tuple")[1].split("\n")[0]
    assert '"console_jobs"' in feats_line, "콘솔 작업 자격을 신고하지 않는다"

    import importlib.util
    import pathlib as _pl
    _cl = _pl.Path(__file__).resolve().parents[2] / "feature-0003-agent-web-ui" / "src" / \
        "routers" / "_console_llm.py"
    spec = importlib.util.spec_from_file_location("_cl_ver", _cl)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    version = src.split('AGENT_VERSION = "')[1].split('"')[0]
    assert mod.version_at_least(version, bt.RUNNER_MIN_AGENT_VERSION), (
        f"러너 버전 {version} 이 서버 하한 {bt.RUNNER_MIN_AGENT_VERSION} 미만 — "
        "자기 배포본이 자격 미달이 된다")
    assert 'body["features"] = list(self.features)' in src
    assert 'body["agent_version"] = AGENT_VERSION' in src


def test_batch_consent_is_opt_in_on_the_runner():
    """배치 동의는 **기본이 아니다** — 그 작업은 사용자가 요청한 적 없고 자기 토큰을 쓴다.

    소스 한 줄을 문자열로 박제하지 않는다(TASK-20260901T110000 에서 신고 조립이 두 축
    (`--batch` · `--no-self-review`)으로 늘며 그 줄이 사라졌다). 잠글 것은 **결과**다:
    기본 신고에 배치가 없고, 플래그를 켜면 들어오고, 다른 축을 꺼도 배치가 살아남는다
    (따로 대입하던 형태에서는 나중 대입이 앞의 것을 지웠다).
    """
    src = _RUNNER.read_text(encoding="utf-8")
    assert '"batch_jobs"' not in src.split("AGENT_FEATURES: tuple")[1].split("\n")[0], (
        "기본 신고에 배치가 들어 있다 — 동의 없이 남의 작업을 가져간다")
    assert 'ap.add_argument("--batch"' in src, "배치 동의를 켤 방법이 없다"

    import importlib.util
    spec = importlib.util.spec_from_file_location("_runner_batch_test", _RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    def build(batch: bool, no_self_review: bool):
        feats = list(runner.AGENT_FEATURES)
        if batch:
            feats.append("batch_jobs")
        if no_self_review:
            feats = [f for f in feats if f != "self_review"]
        return set(feats)

    assert "batch_jobs" not in build(False, False)
    assert "batch_jobs" in build(True, False)
    assert "batch_jobs" in build(True, True), "다른 축을 끄면서 배치 동의가 함께 지워졌다"
    # main() 이 실제로 이 형태로 조립하는지 — 조립부가 사라지면 위 재현은 무의미해진다.
    assert "_feats = list(AGENT_FEATURES)" in src and "api.features = tuple(_feats)" in src


def test_runner_does_not_wrap_console_jobs_in_chat_framing():
    """`kind='job'` 이면 프롬프트를 **그대로** 쓴다.

    대화용 프레이밍(사내 DB 어시스턴트 · 제목 마커 · 답변 규약)을 덧씌우면 서버가 보낸 형식
    요구와 충돌해 JSON 을 요구했는데 산문이 오거나 끝에 제목 줄이 붙는다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def compose_prompt("):]
    fn = fn[:fn.index("\ndef ")]
    # ⚠ **주석을 제외하고** 본다. 첫 작성본은 프레이밍 문구를 문자열로 찾았는데, 그 문구가
    #   바로 위 설명 주석에도 있어 "가드가 프레이밍보다 뒤" 라는 거짓 실패가 났다. 구조
    #   단언은 문구가 아니라 **행위**(어느 코드가 먼저 실행되는가)를 잠가야 한다.
    code = "\n".join(ln for ln in fn.split("\n") if not ln.lstrip().startswith("#"))
    i_guard = code.index('if str(task.get("kind") or "chat") == "job":')
    i_build = code.index("parts: list[str] = []")
    assert i_guard < i_build, "job 분기가 대화 프롬프트 조립보다 뒤에 있다"
    # 분기가 **즉시 반환**해야 한다(아래 조립이 이어붙지 않게).
    assert 'return str(task.get("question") or "")' in code[i_guard:i_build]


# ── 프롬프트 평탄화: 지침이 앞, 형식 요구가 뒤 ───────────────────────────────────────

def _flatten(messages, fmt="text"):
    import sys
    sys.path.insert(0, str(_SRC / "feature-0003-agent-web-ui" / "src"))
    from routers._console_jobs import messages_to_prompt

    return messages_to_prompt(messages, fmt)


def test_system_messages_come_first_regardless_of_input_order():
    """운영자 지침은 **맨 앞**이다 — 뒤에 두면 앞의 지시가 이기고 설정이 무시된다(P0-P 와 같은 축).

    입력 순서가 user→system 이어도 결과는 system 이 앞이어야 한다. 이 순서가 자료구조로
    보장되지 않으면 리팩터가 조용히 뒤집는다.
    """
    out = _flatten([
        {"role": "user", "content": "질문본문"},
        {"role": "system", "content": "지침본문"},
    ])
    assert out.index("지침본문") < out.index("질문본문"), "지침이 질문보다 뒤에 온다"


def test_format_note_is_last_and_matches_the_declared_format():
    """형식 요구는 **맨 뒤**다 — 앞에 두면 뒤의 본문이 그것을 덮어쓴다."""
    out_json = _flatten([{"role": "user", "content": "본문"}], "json")
    assert "JSON" in out_json.split("\n\n")[-1], "형식 요구가 마지막이 아니다"
    out_text = _flatten([{"role": "user", "content": "본문"}], "text")
    assert "JSON" not in out_text, "text 작업에 JSON 을 요구한다 — 조립부와 모순"


def test_blank_and_malformed_messages_are_dropped_not_rendered():
    """빈 content·비-dict 는 버린다 — 빈 줄만 남는 프롬프트를 AI 에게 보내지 않는다."""
    out = _flatten([None, {"role": "user", "content": "  "}, {"role": "user", "content": "실체"}])
    assert "실체" in out
    assert out.count("\n\n") == 1, "빈 항목이 구분자만 남겼다"


# ── 폴링: 재시도해도 달라지지 않는 상태에서 기다리지 않는다 (codex P2 x2) ─────────────

_LLM_STATE_JS = (_SRC / "feature-0003-agent-web-ui" / "src" / "static" / "admin" / "llm-state.js")


def _await_fn() -> str:
    src = _LLM_STATE_JS.read_text(encoding="utf-8")
    fn = src[src.index("export async function awaitDelegatedResult("):]
    return fn[:fn.index("\n}\n")]


def test_auth_failures_stop_immediately_instead_of_retrying_to_timeout():
    """401·403·404 를 일시 오류로 다루지 않는다.

    다루면 상한(10분)까지 매 tick 재요청하고, 사용자에게는 **원인 대신 타임아웃**이 뜬다 —
    그가 할 일은 다시 로그인하는 것인데 화면은 기다리라고 말한다.
    """
    fn = _await_fn()
    for code in ("401", "403", "404"):
        assert f"res.status === {code}" in fn, f"{code} 를 종료 사유로 다루지 않는다"
    assert "로그인이 만료" in fn, "401 에 조치 경로가 없다"


def test_unknown_phase_does_not_wait_until_timeout():
    """모르는 국면에서 계속 돌지 않는다(allowlist).

    서버가 국면을 늘리면(예: `failed`) 그것을 진행 중으로 읽고 상한까지 도는데, 그러면
    실패가 **타임아웃으로 위장**되고 그 위장은 서버를 고친 사람에게 보이지 않는다.
    """
    fn = _await_fn()
    assert 'body.phase !== "waiting" && body.phase !== "working"' in fn, (
        "진행 국면 allowlist 가 없다 — 모르는 국면에서 상한까지 기다린다")


def test_terminal_errors_are_marked_by_value_not_by_message():
    """종료 사유 판정이 **문구가 아니라 값**이다.

    메시지 문자열로 구분하면 문구를 고치는 날 재시도 루프가 조용히 되살아난다.
    """
    src = _LLM_STATE_JS.read_text(encoding="utf-8")
    assert "err.terminal = true" in src
    assert "e.terminal === true" in _await_fn()
    assert "test(e.message)" not in src, "메시지 regex 로 종료 여부를 판정한다"
