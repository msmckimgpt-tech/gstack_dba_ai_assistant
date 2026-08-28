"""feature-0043 P0-Z3 — 러너가 신고한 능력으로 모델·추론등급 선택기를 되살린다.

## 무엇을 잠그는가

P0-T 는 "서버가 연결된 런타임을 알 수 없다" 를 전제로 선택기를 숨겼다. P0-Z3 는 그 전제를
**러너가 직접 말하게** 해서 깬다. 그러면 새 실패 모드가 생긴다 — 목록이 신고가 아닌 곳에서
오거나(P0-T 의 재발), 신고한 값이 검증 없이 실행되거나(주입), 신고가 낡았는데 화면이 그대로
보여주거나(없는 모델 선택).

이 스위트는 그 셋을 각각 잠근다. 배선(소스 검사)이 아니라 **동작**으로 잠그는 것을 우선한다 —
`_sanitize_runtimes` 와 `build_cmd` 는 순수 함수라 실제로 돌릴 수 있고, 돌린 결과가 계약이다.

## 왜 sanitizer 를 여기서 세게 보는가

하트비트 본문은 토큰을 쥔 클라이언트가 준 값이다. 그 값은 (1) DB 에 저장되고 (2) 다른
세션의 화면에 그려지고 (3) 러너로 돌아가 `Popen` 인자가 된다. 셋 다 경계를 넘는 이동이라,
모양 강제가 느슨하면 그 느슨함이 세 곳에서 동시에 드러난다.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
_WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
_AI_TOOLS = _WEB_SRC / "routers" / "ai_tools.py"
_SYSTEM = _WEB_SRC / "routers" / "system.py"
_OAUTH_STORE = _WEB_SRC / "oauth_store.py"
_COMPOSER_JS = _WEB_SRC / "static" / "app" / "composer.js"
_STATIC_RUNNER = _WEB_SRC / "static" / "agent" / "bridge_agent.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_under_test", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_sanitizer():
    """`ai_tools` 는 app 의존이 무거우므로 sanitizer 구역만 떼어 실행한다.

    모듈 전체를 import 하면 FastAPI·DB 스텁이 필요해지고, 그러면 이 테스트가 검사하려는
    **순수 로직**이 환경 문제로 빨개진다(그리고 그 빨강은 결국 skip 으로 무마된다).
    """
    src = _AI_TOOLS.read_text(encoding="utf-8")
    start = src.index("#: 능력 신고의 모양 상한")
    end = src.index('@router.post("/api/ai/bridge_heartbeat")')
    ns: dict = {"re": re}
    exec(src[start:end], ns)  # noqa: S102 — 대상 구역을 격리 실행
    return ns


# ── 러너: 무엇을 신고하는가 ──────────────────────────────────────────────────


def test_runtime_specs_declare_everything_the_pipeline_needs():
    """새 플랫폼을 더할 때 손댈 곳이 **이 표 하나**여야 한다.

    감지·신고·인자 조립이 전부 이 표를 읽으므로, 항목 하나가 빠지면 그 런타임은 조용히
    반쪽으로 동작한다(예: 목록엔 뜨는데 인자가 안 붙는다).
    """
    mod = _load_runner()
    assert set(mod._RUNTIME_SPECS) >= {"claude", "codex", "gemini", "ollama"}, (
        "알려진 플랫폼이 표에서 빠졌다")
    for name, spec in mod._RUNTIME_SPECS.items():
        assert spec.get("label"), f"{name}: 화면에 쓸 이름이 없다"
        assert "argv" in spec and "model" in spec and "effort" in spec, (
            f"{name}: 호출·모델·등급 키가 모두 선언돼야 한다(없으면 None 으로 명시)")
        # 등급 목록을 주면서 그걸 넘길 플래그가 없으면, 화면에 '고를 수 있는데 반영 안 되는'
        # 항목이 생긴다 — P0-T 가 지운 바로 그 상태.
        if spec.get("efforts"):
            assert spec.get("effort"), f"{name}: 등급 목록은 있는데 넘길 플래그가 없다"
        for key in ("models", "efforts"):
            for opt in (spec.get(key) or []):
                assert opt.get("value") and opt.get("label"), f"{name}.{key}: 값/라벨 누락"


def test_detect_runtimes_reports_only_what_is_installed(monkeypatch):
    """설치되지 않은 런타임은 신고하지 않는다 — 고를 수 없는 것을 보여주지 않기 위해."""
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda name: "/usr/bin/x" if name == "codex" else None)
    got = mod.detect_runtimes()
    assert [r["runtime"] for r in got] == ["codex"]

    # `--ai` 로 제한하면 그 하나만. 표에 없는 이름이면 제한을 무시한다(오타가 러너를
    # 벙어리로 만들지 않게 — 그때는 감지된 것을 그대로 신고한다).
    assert [r["runtime"] for r in mod.detect_runtimes("codex")] == ["codex"]
    assert [r["runtime"] for r in mod.detect_runtimes("nonexistent-ai")] == ["codex"]


def test_detect_runtimes_omits_runtimes_with_no_models(monkeypatch):
    """모델 목록이 비면 그 런타임을 통째로 뺀다(화면에 빈 그룹만 남기지 않는다).

    ollama 가 이 경로다 — 실조회가 실패하거나 받아 둔 모델이 없으면 신고에서 빠진다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda name: "/usr/bin/x" if name == "ollama" else None)
    monkeypatch.setattr(mod, "_ollama_models", lambda: [])
    assert mod.detect_runtimes() == []

    monkeypatch.setattr(mod, "_ollama_models", lambda: [{"value": "llama3", "label": "llama3"}])
    got = mod.detect_runtimes()
    assert [r["runtime"] for r in got] == ["ollama"]
    assert got[0]["models"] == [{"value": "llama3", "label": "llama3"}]
    # ollama 에는 추론등급 플래그가 없다 — 신고에도 없어야 한다.
    assert got[0]["efforts"] == []


def test_heartbeat_carries_capabilities_every_time():
    """능력을 **매번** 싣는다.

    처음 한 번만 보내면 서버 재시작·토큰 행 교체 이후 화면의 목록이 영영 비고, 그 빈 목록은
    '러너가 없다' 와 구분되지 않는다. 서버는 값이 같으면 쓰지 않으므로 비용이 없다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    loop = src[src.index("def start_heartbeat("):]
    loop = loop[:loop.index("\ndef ")]
    assert "api.heartbeat(runtimes)" in loop, "하트비트가 능력을 싣지 않는다"
    # 루프 밖에서 한 번만 보내는 형태가 아닌지 — 호출이 while 안에 있어야 한다.
    while_at = loop.index("while not stop.is_set():")
    assert loop.index("api.heartbeat(runtimes)") > while_at, "능력 신고가 루프 밖에 있다"


def test_runner_does_not_offer_a_selector_it_cannot_honor():
    """`--cmd` 로 명령을 통째로 준 사용자는 **신고하지 않는다**.

    그 명령에 모델·등급이 이미 박혀 있어 웹에서 고른 값이 반영되지 않는다. 신고하면 화면에
    선택기가 뜨고, 고른 값은 무시된다 — P0-T 가 지운 상태가 이 경로로 되살아난다.
    """
    main_src = _RUNNER.read_text(encoding="utf-8")
    body = main_src[main_src.index("def main("):]
    assert "runtimes = [] if args.cmd else detect_runtimes(" in body, (
        "--cmd 사용자에게도 선택기가 뜬다(반영되지 않을 조작면)")


# ── 러너: 서버가 준 값을 어떻게 다루는가 (신뢰 경계) ─────────────────────────


@pytest.mark.parametrize("model,effort", [
    ("--dangerously-skip-permissions", None),
    ("-p", None),
    ("opus; rm -rf /", None),
    ("$(whoami)", None),
    ("`id`", None),
    ("opus\n--effort\nmax", None),
    (None, "--dangerously-skip-permissions"),
    (None, "high; curl evil.example"),
    ("../../etc/passwd", None),
    ("claude-haiku-4", None),      # 서버 alias — 이 러너의 어휘가 아니다
    ("gpt-5.1-codex", None),       # 다른 런타임의 모델 이름
])
def test_build_cmd_refuses_values_it_did_not_offer(model, effort):
    """신고하지 않은 값은 **어떤 것도** 인자가 되지 않는다.

    서버가 손상됐거나 중간자가 응답을 바꿔도, 러너가 실행하는 것은 자기가 미리 적어 둔
    목록 안의 값뿐이다. 실패는 조용하다 — 버리고 CLI 기본값으로 답한다(답이 아예 오지
    않는 것보다 낫다).
    """
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문", model, effort)
    assert cmd == ["claude", "-p", "질문"], f"거부되지 않은 값: {model!r}/{effort!r}"


def test_build_cmd_keeps_prompt_as_the_last_positional():
    """플래그는 프롬프트 **앞**에 온다.

    뒤에 붙이면 CLI 에 따라 프롬프트의 일부로 먹히고, 그러면 사용자의 질문에 `--model opus`
    라는 문자열이 섞여 들어간 채로 AI 에게 전달된다.
    """
    mod = _load_runner()
    for runtime, model, effort in (
        ("claude", "opus", "max"),
        ("codex", "gpt-5.1-codex", "low"),
        ("gemini", "gemini-2.5-flash", None),
    ):
        cmd = mod.build_cmd(runtime, "질문", model, effort)
        assert cmd[-1] == "질문", f"{runtime}: 프롬프트가 마지막이 아니다 — {cmd}"
        assert cmd.count("질문") == 1


def test_build_cmd_never_invents_a_flag_for_a_runtime_without_one():
    """등급 플래그가 없는 런타임(gemini)에 등급을 줘도 인자가 생기지 않는다."""
    mod = _load_runner()
    cmd = mod.build_cmd("gemini", "질문", "gemini-2.5-pro", "high")
    assert "high" not in cmd and "--effort" not in cmd


def test_handle_one_validates_the_runtime_before_switching():
    """서버가 지정한 런타임은 **표에 있고 PATH 에 실재할 때만** 쓴다.

    이름만 믿고 `Popen` 에 넘기면 임의 실행 파일을 부르는 경로가 된다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def handle_one("):]
    body = body[:body.index("\ndef ")]
    assert "want_runtime in _RUNTIME_SPECS" in body, "표 대조 없이 런타임을 바꾼다"
    assert "_which(want_runtime)" in body, "실재 확인 없이 런타임을 바꾼다"


def test_runner_copies_are_byte_identical():
    """배포본(`static/agent/`)과 정본이 같아야 한다.

    사용자는 배포본을 내려받아 sha256 을 대조한다. 두 사본이 갈리면 그 대조가 실패하고,
    실패한 대조는 "이 파일을 믿어도 되는가" 라는 질문에 답하지 못한다.
    """
    assert _STATIC_RUNNER.read_bytes() == _RUNNER.read_bytes(), (
        "배포 사본이 정본과 다르다 — `cp` 로 동기화해야 한다")


# ── 서버: 신고를 어떻게 받아들이는가 ─────────────────────────────────────────


def test_sanitizer_separates_no_report_from_empty_report():
    """`None`(신고 없음)과 `[]`(고를 것이 없음)은 다른 사실이다.

    전자는 구 러너·`--cmd` 사용자라 **저장하지 않고**(기존 값 보존), 후자는 저장해서 화면이
    선택기를 감추게 한다. 둘을 같은 값으로 뭉개면 한쪽이 반드시 틀린 동작을 한다.
    """
    ns = _load_sanitizer()
    s = ns["_sanitize_runtimes"]
    assert s(None) is None
    assert s([]) == []
    # 리스트가 아닌 것은 신고로 치지 않는다(모양이 계약이다).
    assert s({"runtime": "claude"}) is None
    assert s("claude") is None
    assert s(42) is None


@pytest.mark.parametrize("bad", [
    "claude; rm -rf /",
    "claude rm",
    "--claude",
    "claude\nrm",
    "../claude",
    "",
    "c" * 100,
])
def test_sanitizer_rejects_runtime_names_that_are_not_names(bad):
    """런타임 이름은 러너에서 **실행 파일 조회 키**가 된다 — 이름처럼 생긴 것만 통과."""
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{"runtime": bad, "models": [{"value": "opus"}]}])
    assert got == [], f"거부되지 않은 런타임 이름: {bad!r}"


def test_sanitizer_drops_only_the_bad_option_not_the_whole_runtime():
    """어긋난 항목 **하나**가 정상 런타임을 통째로 지우지 않는다."""
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude",
        "models": [{"value": "--evil"}, {"value": "opus", "label": "Opus"}, {"value": "x y"}],
        "efforts": [{"value": "low"}, {"value": "hi;gh"}],
    }])
    assert [m["value"] for m in got[0]["models"]] == ["opus"]
    assert [e["value"] for e in got[0]["efforts"]] == ["low"]


def test_sanitizer_flattens_labels_to_one_line():
    """라벨은 화면에 그려진다 — 줄바꿈·제어문자가 레이아웃을 깨지 않게 한 줄로 접는다."""
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude", "label": "Cla\nude\t2",
        "models": [{"value": "opus", "label": "O\n\np\tus"}],
    }])
    assert got[0]["label"] == "Cla ude 2"
    assert got[0]["models"][0]["label"] == "O p us"
    assert "\n" not in json.dumps(got)


def test_sanitizer_caps_the_report_size():
    """개수 상한 — 30초마다 오는 신호가 저장소·화면을 임의로 채우지 못하게."""
    ns = _load_sanitizer()
    huge = [{"runtime": f"rt{i}", "models": [{"value": f"m{j}"} for j in range(200)]}
            for i in range(50)]
    got = ns["_sanitize_runtimes"](huge)
    assert len(got) <= ns["_CAPS_MAX_RUNTIMES"]
    assert all(len(r["models"]) <= ns["_CAPS_MAX_MODELS"] for r in got)


def test_sanitizer_keeps_a_realistic_report_intact():
    """정상 신고는 **손상 없이** 통과한다 — 상한이 실사용을 자르면 안 된다."""
    mod = _load_runner()
    ns = _load_sanitizer()
    # 러너가 실제로 만드는 모양을 그대로 넣는다(두 쪽의 계약이 같은지 확인).
    real = [
        {"runtime": "claude", "label": "Claude",
         "models": list(mod._RUNTIME_SPECS["claude"]["models"]),
         "efforts": list(mod._RUNTIME_SPECS["claude"]["efforts"])},
        {"runtime": "codex", "label": "Codex",
         "models": list(mod._RUNTIME_SPECS["codex"]["models"]),
         "efforts": list(mod._RUNTIME_SPECS["codex"]["efforts"])},
    ]
    got = ns["_sanitize_runtimes"](real)
    assert got == real, "정상 신고가 변형됐다 — 러너와 서버의 계약이 갈렸다"


def test_capability_write_is_skipped_when_unchanged():
    """값이 같으면 쓰지 않는다 — 30초 주기가 곧 쓰기 증폭이 되지 않도록.

    첫 신고(NULL → 값)는 놓치지 않아야 하므로 `IS NULL` 분기가 함께 있어야 한다.
    """
    src = _OAUTH_STORE.read_text(encoding="utf-8")
    fn = src[src.index("def set_runner_capabilities("):]
    fn = fn[:fn.index("\ndef ")]
    assert "RunnerCapabilities IS NULL OR" in fn, "첫 신고를 놓친다(NULL 비교는 <> 로 안 잡힌다)"
    assert "<> %s" in fn, "값이 같아도 매번 쓴다"
    assert "_LIVE_TOKEN_PREDICATE" in fn, (
        "유효성 술어가 하트비트와 다르다 — 폐기된 러너의 목록이 화면에 남는다")


def test_capability_read_shares_the_freshness_rule_with_listening():
    """'연결됨' 판정과 '고를 수 있는 목록' 이 **같은 신선도**를 쓴다.

    갈리면 "연결 안 됨인데 모델은 고를 수 있는"(또는 그 반대) 화면이 되고, 둘 중 하나는
    반드시 사용자를 속인다.
    """
    src = _OAUTH_STORE.read_text(encoding="utf-8")
    read_fn = src[src.index("def account_runner_capabilities("):]
    read_fn = read_fn[:read_fn.index("\ndef ")]
    listen_fn = src[src.index("def account_is_heartbeating("):]
    listen_fn = listen_fn[:listen_fn.index("\ndef ")]
    for fragment in ("_LIVE_TOKEN_PREDICATE", "LastHeartbeatAt IS NOT NULL", "DATE_SUB"):
        assert fragment in read_fn and fragment in listen_fn, (
            f"신선도 술어가 갈렸다: {fragment}")
    # 러너가 여럿이면 가장 최근 것 하나 — 합치면 실제로 가져가는 러너에 없는 모델이 섞인다.
    assert "ORDER BY t.LastHeartbeatAt DESC LIMIT 1" in read_fn


def test_capability_read_survives_corrupted_json():
    """저장된 값이 깨져도 답변 경로는 멀쩡해야 한다(선택기가 숨겨질 뿐)."""
    src = _OAUTH_STORE.read_text(encoding="utf-8")
    fn = src[src.index("def account_runner_capabilities("):]
    fn = fn[:fn.index("\ndef ")]
    assert "except (TypeError, ValueError)" in fn, "JSON 파싱 실패가 요청을 500 으로 만든다"
    assert "return parsed if isinstance(parsed, list) else []" in fn, (
        "리스트가 아닌 저장값이 그대로 화면으로 나간다")


# ── 화면: 런타임마다 다른 어휘를 어떻게 그리는가 ─────────────────────────────


def test_composer_reads_reasoning_options_from_the_runner_catalog():
    """추론등급 목록이 서버 상수가 아니라 **신고**에서 온다.

    런타임마다 다르다 — claude 5단계 · codex 3단계 · gemini 없음. 서버 상수
    (low/normal/high/max)를 그리면 claude 의 `medium`·`xhigh` 가 화면에 없고, codex 에는
    있지도 않은 `normal` 이 뜬다.
    """
    src = _COMPOSER_JS.read_text(encoding="utf-8")
    fn = src[src.index("function _composerReasoningOptions("):]
    fn = fn[:fn.index("\n}")]
    assert "reasoning_levels_by_runtime" in fn, "런타임별 목록을 읽지 않는다"
    assert "_composerCurrentRuntime()" in fn, "현재 런타임을 보지 않는다"
    # 렌더가 그 목록을 쓴다(상수를 직접 도는 형태가 남아 있으면 갈린다).
    render = src[src.index("function _renderComposerReasoningMenu("):]
    render = render[:render.index("\n}\n")]
    assert "_composerReasoningOptions()" in render
    assert "REASONING_LEVEL_OPTIONS.forEach" not in render, "상수를 직접 돈다"


def test_composer_decides_runner_mode_from_an_explicit_server_value():
    """카탈로그 모양을 보고 추측하지 않는다 — 서버가 `model_selector_source` 로 명시한다.

    추측하면 서버가 응답 형태를 바꾼 날 화면이 조용히 어긋난다(그리고 그 어긋남은 사용자가
    먼저 본다).
    """
    src = _COMPOSER_JS.read_text(encoding="utf-8")
    fn = src[src.index("function _composerRunnerCatalog("):]
    fn = fn[:fn.index("\n}")]
    assert 'model_selector_source' in fn and '"runner"' in fn
    # 서버도 같은 키를 싣는다(양쪽이 같은 이름을 쓰는지 — 오타 하나로 영영 hidden 이 된다).
    assert '"model_selector_source"' in _SYSTEM.read_text(encoding="utf-8")


def test_changing_the_model_redraws_the_reasoning_menu():
    """모델을 바꾸면 등급 목록·라벨도 다시 그린다.

    안 하면 claude 에서 고른 `xhigh` 가 codex 로 바꾼 뒤에도 라벨에 남고, 그 값은 codex 에
    없어 조용히 무시된다 — 화면은 반영된다고 말하는데 실행은 아닌 상태.
    """
    src = _COMPOSER_JS.read_text(encoding="utf-8")
    handler = src[src.index('item.setAttribute("data-model-value", value);'):]
    handler = handler[:handler.index("menu.appendChild(item);")]
    assert "_updateComposerReasoningLabel()" in handler, "등급 라벨이 갱신되지 않는다"
    assert "_renderComposerReasoningMenu()" in handler, "등급 목록이 갱신되지 않는다"


def test_current_level_falls_back_within_the_offered_list():
    """저장된 등급이 이 런타임에 없으면 **목록 안의 값**으로 떨어진다.

    서버 집합 검사(_isValidReasoningLevel)를 그대로 쓰면 러너 어휘(`medium`·`xhigh`)가 전부
    탈락해 항상 기본값으로 보인다 — 고른 값이 화면에서 사라지는 형태.
    """
    src = _COMPOSER_JS.read_text(encoding="utf-8")
    fn = src[src.index("function _composerCurrentReasoningLevel("):]
    fn = fn[:fn.index("\n}\n")]
    assert "options.some((o) => o.value === v)" in fn, "신고 목록으로 검증하지 않는다"
    assert "options[0].value" in fn, "목록에 없을 때 유효한 값으로 떨어지지 않는다"


# -- codex REV-20260828T170000 회귀 방어 --------------------------------------
#
# 아래는 적대 리뷰가 잡은 결함들이다. 전부 "그럴듯한 코드가 조용히 틀리는" 부류라, 고친 자리에
# 테스트를 두지 않으면 다음 편집에서 그대로 되돌아온다.


def test_empty_report_is_sent_not_swallowed():
    """`[]`(고를 것 없음)이 `{}`(미신고)로 뭉개지지 않는다 (P1-3).

    뭉개지면 `--cmd` 로 갈아탄 러너가 "이제 고를 것이 없다" 를 말하지 못하고, 서버에 남아 있던
    **과거 목록이 계속 신선한 것으로** 노출된다. 사용자는 고를 수 있는데 반영되지 않는 화면을
    본다 - P0-T 가 지운 바로 그 상태가 이 경로로 되살아난다.
    """
    mod = _load_runner()
    sent: list = []

    class _Api(mod.Api):
        def __init__(self):
            super().__init__("https://x", "t", None)

        def _post(self, path, payload=None, timeout=60.0):
            sent.append((path, payload))
            return {"ok": True}

    api = _Api()
    api.heartbeat([])
    api.heartbeat(None)
    api.heartbeat([{"runtime": "claude", "models": [], "efforts": []}])
    assert sent[0][1] == {"runtimes": []}, "빈 신고가 미신고로 뭉개졌다"
    assert sent[1][1] == {}, "미신고가 빈 신고로 바뀌었다"
    assert sent[2][1]["runtimes"], "정상 신고가 실리지 않았다"


def test_build_cmd_checks_the_actual_report_not_the_static_table():
    """대조 대상은 **신고**다 - 정적 표는 신고보다 넓다 (P1-5).

    `--ai codex` 로 제한하면 신고는 codex 뿐이지만 표에는 claude 도 있다. 표를 보면 서버가
    `claude:opus` 를 돌려줬을 때 사용자가 세운 제한을 넘어선다.
    """
    mod = _load_runner()
    report = [{"runtime": "codex", "label": "Codex",
               "models": [{"value": "gpt-5.1-codex", "label": "x"}],
               "efforts": [{"value": "low", "label": "낮음"}]}]
    # 신고에 없는 런타임의 모델 -> 인자가 되지 않는다(표에는 있다).
    assert mod.build_cmd("claude", "Q", "opus", "max", report) == ["claude", "-p", "Q"]
    # 신고에 있는 것은 그대로 인자가 된다.
    assert mod.build_cmd("codex", "Q", "gpt-5.1-codex", "low", report) == [
        "codex", "exec", "--skip-git-repo-check",
        "-m", "gpt-5.1-codex", "-c", "model_reasoning_effort=low", "Q"]
    # 신고를 주지 않으면 정적 표로 폴백한다(단위 테스트·구 호출부 호환).
    assert mod.build_cmd("claude", "Q", "opus", None) == [
        "claude", "-p", "--model", "opus", "Q"]


def test_ollama_path_also_validates_against_the_report():
    """ollama 는 `build_cmd` 를 타지 않는다 - 그 경로에도 대조가 있어야 한다 (P1-5).

    없으면 서버가 준 임의 문자열이 그대로 생성 요청의 모델명이 되어, 이 머신에 없는 모델을
    부르거나 (여러 모델을 받아 둔 머신에서) 사용자가 고르지 않은 모델을 부른다.
    """
    mod = _load_runner()
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return b'{"response": "ok"}'

    def _fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    report = [{"runtime": "ollama", "label": "Ollama",
               "models": [{"value": "llama3", "label": "llama3"}], "efforts": []}]

    import urllib.request as _u
    orig = _u.urlopen
    _u.urlopen = _fake_urlopen
    try:
        # 신고에 있는 모델 -> 그대로 쓴다.
        mod.ask_local_ai("ollama", [], "Q", None, None, model="llama3", runtimes=report)
        assert captured["body"]["model"] == "llama3"
        # 신고 밖 모델 -> 환경 기본값으로 떨어진다(서버 값을 그대로 쓰지 않는다).
        mod.ask_local_ai("ollama", [], "Q", None, None, model="mistral-evil", runtimes=report)
        assert captured["body"]["model"] != "mistral-evil"
    finally:
        _u.urlopen = orig


def test_unhonored_picks_are_disclosed_in_the_answer():
    """반영 못 한 지정을 **밝힌다** (P1-4).

    같은 계정에 러너가 여럿이면 목록을 신고한 러너와 질문을 가져간 러너가 다를 수 있다. 그때
    조용히 기본값으로 답하면 사용자는 자기가 고른 모델로 답이 나온 줄 안다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def handle_one("):]
    body = body[:body.index("\ndef ")]
    assert "unmet" in body, "미반영 목록을 만들지 않는다"
    assert "기본 설정으로 답했습니다" in body, "미반영 사실이 답변에 실리지 않는다"
    # 제목 규약을 밀어내지 않게 **제목 분리 뒤**에 붙여야 한다.
    assert body.index("split_title(answer)") < body.index("기본 설정으로 답했습니다"), (
        "고지가 제목 분리보다 앞이면 `#TITLE:` 규약 위치를 밀어낸다")


def test_capability_write_has_its_own_rate_limit():
    """값 토글로 쓰기 증폭을 만들 수 없다 (P1-6).

    값 비교만 두면 클라이언트가 두 개의 유효한 JSON 을 번갈아 보내 매 요청 UPDATE 를 만든다.
    이 엔드포인트는 원장·시간당 상한 밖이라 다른 통제 장치가 없다.
    """
    src = _OAUTH_STORE.read_text(encoding="utf-8")
    fn = src[src.index("def set_runner_capabilities("):]
    fn = fn[:fn.index("\ndef ")]
    assert "CapabilitiesAt" in fn, "능력 쓰기 시각을 기록하지 않는다(간격을 잴 수 없다)"
    assert "HEARTBEAT_MIN_WRITE_SEC" in fn, "능력 쓰기에 최소 간격이 없다"
    # `LastHeartbeatAt` 재활용은 안 된다 - 30초마다 갱신되므로 항상 '방금 썼다' 가 된다.
    assert "t.LastHeartbeatAt <=" not in fn, "하트비트 시각을 능력 throttle 기준으로 쓴다"
    boot = (_WEB_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    assert "ADD COLUMN CapabilitiesAt" in boot, "throttle 기준 컬럼이 스키마에 없다"


@pytest.mark.parametrize("bad_models", [1, "opus", {"value": "opus"}, None])
def test_sanitizer_survives_wrong_types_in_nested_fields(bad_models):
    """중첩 필드 타입 오류가 하트비트를 500 으로 만들지 않는다 (P2-2).

    연결을 지키려는 신호가 연결을 끊는 장치가 되면 안 된다.
    """
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{"runtime": "claude", "models": bad_models}])
    assert got == [], f"models={bad_models!r} 에서 예외 없이 빈 목록이어야 한다"


def test_sanitizer_strips_bidi_and_control_characters():
    """라벨의 제어·bidi override 문자를 제거한다 (P2-2).

    XSS 는 프론트가 막지만, bidi override 는 **다른 사용자에게 보이는 문자열의 표시 순서**를
    뒤집어 이름을 위장한다(화면에 그려지는 값이라 그 위장이 그대로 보인다).
    """
    ns = _load_sanitizer()
    rlo, rlm, nul, esc = "\u202e", "\u200f", "\u0000", "\u001b"
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude", "label": f"Op{rlo}us{rlm}",
        "models": [{"value": "opus", "label": f"A{nul}B{esc}C"}],
    }])
    label = got[0]["label"]
    model_label = got[0]["models"][0]["label"]
    for ch in (rlo, rlm, nul, esc):
        assert ch not in label and ch not in model_label, f"{ch!r} 가 남았다"
    # 낱말 경계였던 문자는 **공백으로** 바뀐다 - 지우면 없던 단어가 만들어진다.
    assert model_label == "A B C"


def test_runtime_name_cannot_contain_the_pair_separator():
    """런타임 이름에 `:` 를 금지한다 (P2-3).

    화면 값이 `"<runtime>:<model>"` 이라, 런타임에 `:` 가 있으면 적재 시 짝을 가르는 지점이
    첫 `:` 에서 끊어 **다른 조합으로 재해석**된다(`ollama:spoof` + `bar` ->
    runtime=`ollama`, model=`spoof:bar`).
    """
    ns = _load_sanitizer()
    assert ns["_sanitize_runtimes"](
        [{"runtime": "ollama:spoof", "models": [{"value": "bar"}]}]) == []
    # 모델 **값**에는 `:` 가 필요하다(`llama3:8b` 류) - 그쪽은 계속 허용한다.
    got = ns["_sanitize_runtimes"](
        [{"runtime": "ollama", "models": [{"value": "llama3:8b"}]}])
    assert got[0]["models"][0]["value"] == "llama3:8b"


def test_bridge_default_model_comes_from_the_report():
    """브리지 카탈로그의 기본값이 **신고 목록 안**에 있다 (P1-1/P1-2).

    `None` 으로 두면 프론트가 서버 기본값(haiku)으로 폴백하고, 사용자가 선택기를 건드리지 않고
    보낸 첫 질문에 그 alias 가 실려 굳는다 - 러너는 모르는 이름이라 버린다.
    """
    src = _SYSTEM.read_text(encoding="utf-8")
    body = src[src.index("def get_api_vault_options("):]
    assert 'bridge_models[0]["value"] if visible else None' in body, (
        "브리지 기본 모델이 신고 목록에서 나오지 않는다")
    # 프론트도 러너 목록을 우선한다(세션 기본값이 이기면 서버 alias 로 되돌아간다).
    js = _COMPOSER_JS.read_text(encoding="utf-8")
    fn = js[js.index("function _composerCurrentModel("):]
    fn = fn[:fn.index("\n}\n")]
    assert "_composerRunnerCatalog()" in fn, "현재 모델이 러너 카탈로그를 보지 않는다"
    assert fn.index("_composerRunnerCatalog()") < fn.index("state.session?.default_model"), (
        "세션 기본값이 러너 목록보다 먼저 이긴다")


def test_reasoning_hydration_uses_one_predicate():
    """등급 hydration 과 현재값 계산이 **같은 술어**를 쓴다 (P2-1).

    서버 고정 집합으로 검사하면 러너 어휘(`medium`·`xhigh`)가 전부 탈락해, 다른 브라우저에서
    대화를 열 때 사용자가 고른 등급이 사라진다.
    """
    js = _COMPOSER_JS.read_text(encoding="utf-8")
    assert "function _composerReasoningValid(" in js, "공용 술어가 없다"
    fn = js[js.index("function _composerReasoningValid("):]
    fn = fn[:fn.index("\n}\n")]
    assert "_composerRunnerCatalog()" in fn and "_isValidReasoningLevel(" in fn, (
        "브리지/서버 두 어휘를 모두 다루지 않는다")
    app_js = (_WEB_SRC / "static" / "app.js").read_text(encoding="utf-8")
    assert "_composerReasoningValid(_rl)" in app_js, "hydration 이 공용 술어를 쓰지 않는다"
    assert "_isValidReasoningLevel(_rl)" not in app_js, "hydration 이 서버 집합으로 거절한다"
