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
import sys
import threading
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
    assert set(mod._RUNTIME_SPECS) >= {"claude", "codex", "gemini"}, (
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
    """설치되지 않은 런타임은 신고하지 않는다 — 고를 수 없는 것을 보여주지 않기 위해.

    2026-08-31: 여기에 **두 번째 조건**이 붙었다. 설치돼 있어도 그 AI 가 답한 목록이 없으면
    신고하지 않는다(내장 표의 모델 이름은 더 이상 신고에 쓰이지 않는다). 그래서 이 테스트는
    캐시를 함께 준다 — 캐시가 곧 "그 AI 가 답한 적 있다" 는 사실이다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda name: "/usr/bin/x" if name == "codex" else None)
    caps = {"codex": {"label": "Codex", "models": [{"value": "gpt-5.6-sol", "label": "Sol"}],
                      "efforts": [], "model": ["-m", "{model}"], "effort": None,
                      "effort_probed": True, "source": "probe"}}
    assert [r["runtime"] for r in mod.detect_runtimes(cached=caps)] == ["codex"]

    # `--ai` 로 제한하면 그 하나만. 표에 없는 이름이면 제한을 무시한다(오타가 러너를
    # 벙어리로 만들지 않게 — 그때는 감지된 것을 그대로 신고한다).
    assert [r["runtime"] for r in mod.detect_runtimes("codex", cached=caps)] == ["codex"]
    assert [r["runtime"] for r in mod.detect_runtimes("nonexistent-ai", cached=caps)] == ["codex"]

    # 설치돼 있지만 답한 적 없는 런타임은 **신고되지 않는다** — 틀린 목록을 보여주느니
    # 그 그룹이 화면에 없는 편이 낫다(사용자 제보 2026-08-31: 없는 gpt-5.1-* 가 보였다).
    assert mod.detect_runtimes() == []


def test_detect_runtimes_omits_runtimes_with_no_models(monkeypatch):
    """고를 모델이 없는 런타임은 **신고에서 빠진다** — 화면에 빈 그룹을 남기지 않는다.

    probe 가 답을 주지 못한 런타임이 이 경로다(2026-09-01 이전엔 ollama 실조회 실패도
    여기 있었으나 그 런타임은 제거됐다 — 로컬 LLM 미사용, 사용자 결정).
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda name: "/usr/bin/x" if name == "claude" else None)
    monkeypatch.setattr(mod, "probe_runtime_caps", lambda *a, **k: None)
    assert mod.detect_runtimes(cached={}, probe=True) == [], "빈 런타임이 신고에 남았다"

    caps = {"claude": {"label": "Claude", "models": [{"value": "opus", "label": "Opus"}],
                       "efforts": [], "model": ["--model", "{model}"], "effort": None,
                       "source": "probe"}}
    got = mod.detect_runtimes(cached=caps)
    assert [r["runtime"] for r in got] == ["claude"]
    # 등급 플래그가 없으면 신고에도 등급이 없다.
    assert got[0]["efforts"] == []

def test_heartbeat_carries_capabilities_every_time():
    """능력을 **매번** 싣는다.

    처음 한 번만 보내면 서버 재시작·토큰 행 교체 이후 화면의 목록이 영영 비고, 그 빈 목록은
    '러너가 없다' 와 구분되지 않는다. 서버는 값이 같으면 쓰지 않으므로 비용이 없다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    loop = src[src.index("def start_heartbeat("):]
    loop = loop[:loop.index("\ndef ")]
    # 첫 인자가 `runtimes` 이면 된다 — TASK-20260901T140000 이 사망 신고
    # (`released_instances=`)를 같은 호출에 덧붙였으므로 전량 일치로 고정하면
    # 이 계약과 무관한 인자 추가가 곧 실패가 된다.
    call = "api.heartbeat(runtimes"
    assert call in loop, "하트비트가 능력을 싣지 않는다"
    # 루프 밖에서 한 번만 보내는 형태가 아닌지 — 호출이 while 안에 있어야 한다.
    while_at = loop.index("while not stop.is_set():")
    assert loop.index(call) > while_at, "능력 신고가 루프 밖에 있다"


def test_runner_does_not_offer_a_selector_it_cannot_honor(monkeypatch, tmp_path):
    """`--cmd` 로 명령을 통째로 준 사용자는 **신고하지 않는다**.

    그 명령에 모델·등급이 이미 박혀 있어 웹에서 고른 값이 반영되지 않는다. 신고하면 화면에
    선택기가 뜨고, 고른 값은 무시된다 — P0-T 가 지운 상태가 이 경로로 되살아난다.

    ⚠ **행위로 잠근다** (2026-09-02 재작성). 종전에는 `main()` 소스를 «마지막 `if args.cmd:`
    부터 다음 `else:` 까지» 로 잘라 그 안에 `runtimes = []` 이 있는지 문자열로 봤다. 그
    단정은 분기 모양이 바뀌자(`if/elif`, 협상을 배경으로 미룸 — TASK-20260902T140000) 코드가
    여전히 옳은데도 `ValueError` 로 깨졌다. 잠글 것은 «그렇게 쓰였는가» 가 아니라
    «그렇게 동작하는가» 다: 하트비트가 **빈 목록**을 받고, 능력 질의가 **일어나지 않는다**.
    """
    mod = _load_runner()
    seen: dict = {}
    asked: list = []

    def _fake_start_heartbeat(_api, _stop, runtimes=None, **_k):
        seen["runtimes"] = runtimes
        return threading.Thread(target=lambda: None)

    class _Stop(Exception):
        pass

    def _fake_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        if tool == "wait_for_request":
            raise _Stop
        return {}

    monkeypatch.setattr(mod.Api, "call", _fake_call)
    monkeypatch.setattr(mod, "start_heartbeat", _fake_start_heartbeat)
    monkeypatch.setattr(mod, "resolve_caps",
                        lambda *a, **k: asked.append(a) or ([], {}))
    monkeypatch.setattr(mod, "_ensure_strict_mcp_supported", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(mod, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test", "--cmd", "mycli --model big {prompt}"])
    try:
        mod.main()
    except _Stop:
        pass

    assert seen.get("runtimes") == [], (
        f"--cmd 사용자에게도 선택기가 뜬다(반영되지 않을 조작면): {seen.get('runtimes')}")
    assert asked == [], "--cmd 인데 AI 에게 능력을 묻는다(토큰 낭비)"


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
    # 기대값은 표의 base argv 에서 유도한다 — 호출 형태(`--strict-mcp-config` 등)가 바뀌어도
    # 이 테스트가 지키려는 것("신고 밖 값은 인자가 되지 않는다")은 그대로여야 한다.
    base = [a.replace("{prompt}", "질문") for a in mod._RUNTIME_SPECS["claude"]["argv"]]
    assert cmd == base, f"거부되지 않은 값: {model!r}/{effort!r}"


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
    # P0-Z4: 우리 표에 없는 CLI 도 쓸 수 있으므로 "표에 있는가" 만으로는 부족하다 —
    # **아는 호출법이 있는가**(표 또는 질의로 배운 것) + PATH 실재를 함께 본다.
    assert "_known or _learned" in body, "호출법 확인 없이 런타임을 바꾼다"
    # 2026-09-01: 실재 확인의 **범위**가 PATH → PATH + 표준 설치 위치로 넓어져 함수 이름이
    # `_which_ai` 가 됐다(설치기가 PATH 를 못 넣은 머신에서 멀쩡한 AI 를 못 찾던 결함).
    # 확인한다는 계약은 그대로이므로, 잠그는 것도 그대로 「실재를 확인하는가」다.
    assert "_which_ai(want_runtime)" in body, "실재 확인 없이 런타임을 바꾼다"
    assert "_offered" in body, "신고 대조 없이 런타임을 바꾼다"


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
    got = ns["_sanitize_runtimes"]([{"runtime": bad, "source": "probe",
                                   "models": [{"value": "opus"}]}])
    assert got == [], f"거부되지 않은 런타임 이름: {bad!r}"


def test_sanitizer_drops_only_the_bad_option_not_the_whole_runtime():
    """어긋난 항목 **하나**가 정상 런타임을 통째로 지우지 않는다."""
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude", "source": "probe",
        "models": [{"value": "--evil"}, {"value": "opus", "label": "Opus"}, {"value": "x y"}],
        "efforts": [{"value": "low"}, {"value": "hi;gh"}],
    }])
    assert [m["value"] for m in got[0]["models"]] == ["opus"]
    assert [e["value"] for e in got[0]["efforts"]] == ["low"]


def test_sanitizer_flattens_labels_to_one_line():
    """라벨은 화면에 그려진다 — 줄바꿈·제어문자가 레이아웃을 깨지 않게 한 줄로 접는다."""
    ns = _load_sanitizer()
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude", "label": "Cla\nude\t2", "source": "probe",
        "models": [{"value": "opus", "label": "O\n\np\tus"}],
    }])
    assert got[0]["label"] == "Cla ude 2"
    assert got[0]["models"][0]["label"] == "O p us"
    assert "\n" not in json.dumps(got)


def test_sanitizer_caps_the_report_size():
    """개수 상한 — 30초마다 오는 신호가 저장소·화면을 임의로 채우지 못하게."""
    ns = _load_sanitizer()
    huge = [{"runtime": f"rt{i}", "source": "probe",
             "models": [{"value": f"m{j}"} for j in range(200)]}
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
        {"runtime": "claude", "label": "Claude", "source": "probe",
         "models": list(mod._RUNTIME_SPECS["claude"]["models"]),
         "efforts": list(mod._RUNTIME_SPECS["claude"]["efforts"])},
        {"runtime": "codex", "label": "Codex", "source": "probe",
         "models": list(mod._RUNTIME_SPECS["codex"]["models"]),
         "efforts": list(mod._RUNTIME_SPECS["codex"]["efforts"])},
    ]
    got = ns["_sanitize_runtimes"](real)
    # `source` 는 **수신 시점 게이트**용이고 저장 스키마는 4키로 유지한다 — 화면에 그릴
    # 것만 저장한다는 계약이 그대로다. 나머지는 한 글자도 변형되지 않아야 한다.
    expected = [{k: v for k, v in rt.items() if k != "source"} for rt in real]
    assert got == expected, "정상 신고가 변형됐다 — 러너와 서버의 계약이 갈렸다"
    assert all("source" not in rt for rt in got), "출처가 저장 스키마로 새어 들어갔다"


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


class _SqlSpyCursor:
    """실행된 SQL 을 그대로 모으는 커서. 반환 행은 생성자가 정한다."""

    def __init__(self, row=None):
        self.sql: list = []
        self._row = row

    def execute(self, sql, params=None):
        self.sql.append(" ".join(str(sql).split()))

    def fetchone(self):
        return self._row

    def close(self):
        pass


def test_capability_read_shares_the_freshness_rule_with_listening():
    """'연결됨' 판정과 '고를 수 있는 목록' 이 **같은 신선도**를 쓴다.

    갈리면 "연결 안 됨인데 모델은 고를 수 있는"(또는 그 반대) 화면이 되고, 둘 중 하나는
    반드시 사용자를 속인다.

    ## 왜 소스 문자열을 보지 않는가 (2026-09-01 재작성)

    이 검사는 두 번 옮겨졌다 — 질의가 `account_runner_capabilities` → `account_runner_profile`
    → `shared.bridge_tasks.runner_profile_for_account` 로 이동할 때마다 **계약은 그대로인데
    검사만 FAIL** 했다. 검사가 계약이 아니라 **구조를 잠그고** 있었던 것이다.

    그래서 이제 **실제로 나가는 SQL** 을 본다. 정의가 어느 모듈로 옮겨가든, 두 판정이 같은
    술어로 행을 고르는 한 통과한다 — 그리고 술어가 진짜로 갈리면 반드시 실패한다.
    """
    import oauth_store as store

    read_cur = _SqlSpyCursor(row=None)
    store.account_runner_profile(read_cur, 7)
    listen_cur = _SqlSpyCursor(row=(0,))
    store.account_is_heartbeating(listen_cur, 7)
    read_sql = " ".join(read_cur.sql)
    listen_sql = " ".join(listen_cur.sql)
    assert read_sql and listen_sql, "질의가 나가지 않았다 — 검사가 vacuous 하다"
    for fragment in ("t.TokenType = 'access'", "t.RevokedAt IS NULL",
                     "LastHeartbeatAt IS NOT NULL", "DATE_SUB"):
        assert fragment in read_sql and fragment in listen_sql, (
            f"신선도 술어가 갈렸다: {fragment}")
    # 러너가 여럿이면 가장 최근 것 하나 — 합치면 실제로 가져가는 러너에 없는 모델이 섞인다.
    assert "ORDER BY t.LastHeartbeatAt DESC LIMIT 1" in read_sql
    # 래퍼(`account_runner_capabilities`)가 **자기 질의를 갖지 않는다** — 가지면 두 벌이 된다.
    wrap_cur = _SqlSpyCursor(row=None)
    store.account_runner_capabilities(wrap_cur, 7)
    assert wrap_cur.sql == read_cur.sql, "래퍼가 다른 질의를 쓴다(판정 이중화)"


def test_capability_read_survives_corrupted_json():
    """저장된 값이 깨져도 답변 경로는 멀쩡해야 한다(선택기가 숨겨질 뿐).

    소스가 아니라 **결과**를 잠근다: 깨진 값·리스트 아닌 값을 실제로 넣고 돌려 본다.
    """
    import oauth_store as store

    for stored in ('{"not": "a list"}', "이건 JSON 이 아니다", "[", '"문자열"'):
        cur = _SqlSpyCursor(row=(stored, "console_jobs", "2026.09.01"))
        got = store.account_runner_profile(cur, 7)
        assert got["capabilities"] == [], f"깨진 값이 화면으로 나갔다: {stored!r}"
        # 능력이 비어도 **기능·버전은 살아 있다** — 두 축은 수명이 다르다.
        assert got["features"] == ["console_jobs"] and got["listening"] is True


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
    # 계약은 **`runtimes` 축**이다 — 빈 목록(신고했고 고를 것 없음)과 미포함(신고할 처지가
    # 아님)이 구분되는가. 본문 전체 동치로 잠그면 무관한 축이 늘 때마다(기능·버전 신고 등)
    # 이 검사가 깨지는데, 그것은 계약 위반이 아니라 **검사가 너무 넓은** 것이다.
    assert sent[0][1].get("runtimes") == [], "빈 신고가 미신고로 뭉개졌다"
    assert "runtimes" not in sent[1][1], "미신고가 빈 신고로 바뀌었다"
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
    # 기대값은 표의 base argv 에서 유도한다(호출 형태 변경에 깨지지 않게).
    _claude = [a.replace("{prompt}", "Q") for a in mod._RUNTIME_SPECS["claude"]["argv"]]
    # 신고에 없는 런타임의 모델 -> 인자가 되지 않는다(표에는 있다).
    assert mod.build_cmd("claude", "Q", "opus", "max", report) == _claude
    # 신고에 있는 것은 그대로 인자가 된다.
    assert mod.build_cmd("codex", "Q", "gpt-5.1-codex", "low", report) == [
        "codex", "exec", "--skip-git-repo-check",
        "-m", "gpt-5.1-codex", "-c", "model_reasoning_effort=low", "Q"]
    # 신고를 주지 않으면 정적 표로 폴백한다(단위 테스트·구 호출부 호환).
    assert mod.build_cmd("claude", "Q", "opus", None) == \
        _claude[:-1] + ["--model", "opus", "Q"]
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
    got = ns["_sanitize_runtimes"]([{"runtime": "claude", "source": "probe",
                                     "models": bad_models}])
    assert got == [], f"models={bad_models!r} 에서 예외 없이 빈 목록이어야 한다"


def test_sanitizer_strips_bidi_and_control_characters():
    """라벨의 제어·bidi override 문자를 제거한다 (P2-2).

    XSS 는 프론트가 막지만, bidi override 는 **다른 사용자에게 보이는 문자열의 표시 순서**를
    뒤집어 이름을 위장한다(화면에 그려지는 값이라 그 위장이 그대로 보인다).
    """
    ns = _load_sanitizer()
    rlo, rlm, nul, esc = "\u202e", "\u200f", "\u0000", "\u001b"
    got = ns["_sanitize_runtimes"]([{
        "runtime": "claude", "label": f"Op{rlo}us{rlm}", "source": "probe",
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
        [{"runtime": "ollama:spoof", "source": "probe",
          "models": [{"value": "bar"}]}]) == []
    # 모델 **값**에는 `:` 가 필요하다(`llama3:8b` 류) - 그쪽은 계속 허용한다.
    got = ns["_sanitize_runtimes"](
        [{"runtime": "ollama", "source": "probe",
          "models": [{"value": "llama3:8b"}]}])
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


# -- P0-Z4: 목록을 정하는 것은 **그 AI 자신** ------------------------------------
#
# P0-Z3 는 러너의 하드코딩 표를 신고했다. 그 표는 우리가 아는 시점에 멈춰 있어서, 실측에서
# codex 는 표에 없던 모델(`gpt-5.6-*`)을 답했고 claude 는 우리가 빠뜨린 것(`fable`)을 답했다.
# 아래는 "묻고 · 관대하게 받고 · 그래도 안전한가" 를 잠근다.


def test_probe_never_runs_unless_asked():
    """능력 질의는 **명시할 때만** 한다.

    기본값이 켜져 있으면 이 함수를 부르는 모든 자리(테스트 포함)가 실제 AI 를 호출해 수십 초를
    쓰고 사용자 계정 토큰을 태운다. 실제로 이 스위트가 그렇게 멈춘 적이 있다.
    """
    mod = _load_runner()
    src = _RUNNER.read_text(encoding="utf-8")
    sig = src[src.index("def detect_runtimes("):]
    sig = sig[:sig.index(")")]
    assert "probe: bool = False" in sig, "질의가 기본으로 켜져 있다"
    # 실제로도 켜지 않으면 묻지 않는다(외부 호출이 일어나면 이 테스트가 느려진다).
    calls: list = []
    orig = mod.probe_runtime_caps
    mod.probe_runtime_caps = lambda *a, **k: calls.append(a) or None
    try:
        mod.detect_runtimes()
    finally:
        mod.probe_runtime_caps = orig
    assert calls == [], "옵트인 없이 AI 를 호출했다"


@pytest.mark.parametrize("body,expect", [
    ('{"models":[{"value":"opus"}]}', ["opus"]),
    ('```json\n{"models":["opus","sonnet"]}\n```', ["opus", "sonnet"]),
    ('답변드립니다:\n{"models":[{"value":"opus"}]}\n이상입니다.', ["opus"]),
    ('앞에 {깨진 것 } 뒤에 {"models":["x"]}', ["x"]),
    ('{"models": {"opus": "Opus"}}', ["opus"]),
    ('{"models":[{"name":"o3"}]}', ["o3"]),
    ('{"models":[{"id":"gpt-5.1"}]}', ["gpt-5.1"]),
])
def test_probe_accepts_however_the_ai_phrased_it(body, expect):
    """**관대하게 수용한다** (사용자 요구).

    형식을 요구하되, 코드펜스·머리말·맺음말·키 이름 차이·매핑 형태를 전부 받는다. 조금
    어긋났다고 그 런타임을 통째로 버리면 사용자는 이유 없이 선택지를 잃는다.
    """
    mod = _load_runner()
    got = mod._extract_json(body)
    assert got is not None, "AI 응답에서 JSON 을 못 찾았다"
    assert [o["value"] for o in mod._coerce_options(got.get("models"))] == expect


def test_probe_still_refuses_values_that_could_become_flags():
    """관대해도 **모양은 본다** — 옵션처럼 생긴 값·공백·빈 값은 버린다.

    이 값들은 곧 `Popen` 인자가 된다. 내용(어떤 모델인가)은 AI 의 소관이지만, 모양은 우리가
    책임진다.
    """
    mod = _load_runner()
    got = mod._coerce_options(["ok", "--dangerously-skip", "a b", "", "-p", "$(id)"])
    assert [o["value"] for o in got] == ["ok"]


@pytest.mark.parametrize("raw,ph,expect", [
    (["--model", "{model}"], "{model}", ["--model", "{model}"]),
    ("--model {model}", "{model}", ["--model", "{model}"]),
    ("--model={model}", "{model}", ["--model={model}"]),
    ('--model "{model}"', "{model}", ["--model", "{model}"]),   # shlex 가 따옴표를 벗긴다
    (["-c", "reasoning={effort}"], "{effort}", ["-c", "reasoning={effort}"]),
    (["{model}"], "{model}", ["{model}"]),   # 위치 인자로 모델을 받는 CLI
    (["--model"], "{model}", None),          # 치환 자리가 없다 = 값을 넣을 곳이 없다
    ("", "{model}", None),
    (["--model", "{model}", "; rm -rf /"], "{model}", None),   # 공백 포함 토큰
    (42, "{model}", None),
])
def test_flag_shapes_are_coerced_or_refused(raw, ph, expect):
    """AI 가 답한 호출법을 argv 조각으로 맞춘다 — 쓸 수 없으면 None."""
    mod = _load_runner()
    assert mod._coerce_flag(raw, ph) == expect


@pytest.mark.parametrize("evil", [
    ["sh", "-c", "{model}"],                                   # 셸 실행
    ["bash", "{model}"],
    ["python", "{model}"],
    ["--model", "{model}", "--dangerously-skip-permissions"],  # 임의 플래그 편승
    ["--model", "{model}", "--yolo"],
    ["--a", "--b", "--c", "{model}"],                          # 토큰 과다
    ["{model}", "{model}"],                                    # 치환 자리 중복
    ["/bin/sh", "{model}"],
])
def test_flag_shape_refuses_execution_and_hitchhiking(evil):
    """호출법은 **대조할 목록이 없는 유일한 값**이라 형태로만 막는다.

    모델·등급 값은 신고 목록과 대조되지만 플래그는 형태 그 자체다 — 검사 없이 `Popen` 인자가
    된다. 그래서 ① 치환 자리 정확히 1개 ② 토큰 ≤ 2 ③ 나머지는 `-` 로 시작을 강제한다.

    ③이 없으면 `["sh","-c","{model}"]` 이 **셸을 실행**하고, ②가 없으면 임의 플래그가
    따라붙는다. 둘 다 실측에서 통과하던 형태였다(자체 점검으로 발견).
    """
    mod = _load_runner()
    assert mod._coerce_flag(evil, "{model}") is None, f"위험한 호출법이 통과했다: {evil}"


def test_flags_never_leave_the_machine(monkeypatch):
    """**호출법은 서버로 나가지 않는다** — 이번 변경의 신뢰 경계.

    모델 이름은 사람이 골라야 하므로 서버를 거치지만, 플래그 형태까지 보내면 서버가 인자의
    *형태* 를 바꿀 수 있게 된다. 목록(신고)과 호출법(로컬)을 가르는 것이 그 경계다.
    """
    mod = _load_runner()
    caps = {"claude": {"label": "Claude",
                       "models": [{"value": "opus", "label": "Opus"}],
                       "efforts": [{"value": "low", "label": "Low"}],
                       "model": ["--model", "{model}"],
                       "effort": ["--effort", "{effort}"], "source": "probe"}}
    # PATH 에 실제로 claude 가 있는지에 이 계약이 좌우되면 안 된다(컨테이너 CI 에는 없다).
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    reported = mod.detect_runtimes(cached=caps)
    blob = json.dumps(reported, ensure_ascii=False)
    for leak in ("--model", "--effort", "{model}", "{effort}", "model_flag"):
        assert leak not in blob, f"호출법이 신고에 실렸다: {leak}"
    # 신고에는 사람이 고를 것 + **출처**만 있다. `source` 는 값이 아니라 「이 목록이 어떻게
    # 얻어졌는가」라 호출법과 성격이 다르고, 서버가 런타임 단위로 다시 거르는 데 쓴다.
    assert set(reported[0]) == {"runtime", "label", "models", "efforts", "source"}
    assert reported[0]["source"] == "probe"


def test_probe_result_is_cached_so_startup_does_not_burn_tokens():
    """한 번 물으면 다음 기동은 묻지 않는다 — 질의는 사용자 계정 토큰을 쓴다."""
    src = _RUNNER.read_text(encoding="utf-8")
    save = src[src.index("def save_conf("):]
    save = save[:save.index("\ndef ")]
    assert 'payload["caps"] = caps' in save, "질의 결과를 저장하지 않는다(매번 다시 묻는다)"
    assert 'prev = load_conf().get("caps")' in save, (
        "능력을 구하지 않은 실행(`--cmd` 등)이 기존 캐시를 지운다")
    main_src = src[src.index("def main("):]
    assert "--refresh-caps" in src, "갱신 수단이 없다"
    assert "None if args.refresh_caps else" in main_src, "갱신 플래그가 캐시를 무시하지 않는다"


def test_builtin_table_falls_back_for_invocation_only(monkeypatch):
    """내장 표는 **호출법**만 폴백한다 — 모델 이름은 폴백하지 않는다 (2026-08-31).

    종전에는 표의 모델 이름까지 신고했다. 그 표는 우리가 적어 둔 시점에 멈춰 있어서
    라이브에서 codex 가 `gpt-5.1-codex` 로 보였는데, 그 계정이 실제로 쓸 수 있는 것은
    `gpt-5.6-*` 였다(사용자 제보). **없는 모델을 고를 수 있다고 말하는 것**이고, 고른 순간
    CLI 가 거부하거나 조용히 다른 모델로 답한다.

    호출법은 성격이 다르다 — 잘 변하지 않고, 없으면 실행 자체가 불가능하며, 값이 아니라
    형태라 "틀린 선택지를 제시" 하는 문제가 생기지 않는다.
    """
    mod = _load_runner()
    src = _RUNNER.read_text(encoding="utf-8")

    # ⚠ **함수 이름에 결합하지 않는다** (2026-09-02). 초판은 `detect_runtimes` 본문만
    #   떼어 봤는데, 신고 목록 조립이 `_assemble` 로 분리되자(플랫폼 단위 중간 신고를
    #   위해 여러 번 불려야 했다) 이 단정이 **동작 변경 없이** 빨개졌다. 검사하려는 사실은
    #   「폴백 경로가 존재하고 그 출처가 `builtin` 이다」이므로, 그 사실이 사는 함수를
    #   후보로 두고 **하나라도** 만족하면 통과시킨다.
    def _body(name: str) -> str:
        i = src.find(f"def {name}(")
        if i < 0:
            return ""
        rest = src[i:]
        j = rest.find("\ndef ")
        return rest[:j] if j > 0 else rest

    fn = "\n".join(_body(n) for n in ("detect_runtimes", "_assemble"))
    assert fn.strip(), "폴백 경로가 사는 함수를 하나도 찾지 못했다 — 이 단정은 무의미하다"
    assert '"builtin"' in fn, "폴백 경로가 사라졌다(호출법까지 잃는다)"
    # 2026-09-01: 그 자리는 **항상 `builtin`** 이다. 다른 이름으로 바꾸면 바로 아래 캐시
    # 쓰기 가드(`!= "builtin"`)가 뒤집혀 폴백이 영구 캐시된다 — 한 번 그렇게 만들었고
    # 목록이 굳는 결함이 됐다(security 적대리뷰 B1).
    assert '"source": "builtin",' in fn, "폴백 출처가 builtin 이 아니다(캐시 가드가 뒤집힌다)"
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    # 질의도 캐시도 없다 → **신고하지 않는다**(빈 목록으로 그룹만 남기지 않는다).
    assert mod.detect_runtimes(cached={}) == [], "내장 모델 이름이 아직 신고된다"
    # 그래도 호출법은 살아 있어 실행은 가능하다(그것이 이 표의 남은 역할이다).
    assert mod.build_cmd("claude", "Q", None, None) == [
        a.replace("{prompt}", "Q") for a in mod._RUNTIME_SPECS["claude"]["argv"]]


def test_unknown_cli_is_asked_too():
    """우리 표에 **없는** CLI 도 물어본다 (사용자 요구: 플랫폼에 관계없이).

    호출법을 모르므로 가장 흔한 두 형태를 시도하고, 통한 형태를 기억해 실제 질문도 그 형태로
    보낸다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def detect_runtimes("):]
    fn = fn[:fn.index("\ndef ")]
    assert "unknown_argvs" in fn, "표 밖 CLI 를 물어보지 않는다"
    assert '[n, "-p", "{prompt}"]' in fn and '[n, "{prompt}"]' in fn, (
        "표 밖 CLI 의 호출 형태 후보가 없다")
    # ⚠ **리터럴이 아니라 의도를 검사한다** (2026-09-02). 초판은 `got["argv"] = argv` 를
    #   그대로 찾았는데, 질의 전용 인자(`probe_extra`)를 도입하면서 그 우변이
    #   `_pure[_i]`(순수 형태)로 **의도적으로** 바뀌었다 — 인자가 캐시에 남으면 그 계정의
    #   모든 질문이 `model_reasoning_effort=low` 로 돌기 때문이다. 검사하려는 사실은
    #   「통한 호출 형태를 기억한다」이므로 대입의 **존재**를 본다.
    import ast as _ast
    _tree = _ast.parse(src)
    _dr = next((n for n in _ast.walk(_tree)
                if isinstance(n, _ast.FunctionDef) and n.name == "detect_runtimes"), None)
    assert _dr is not None, "detect_runtimes 를 찾지 못했다"
    _stores = [_ast.unparse(a.value) for a in _ast.walk(_dr) if isinstance(a, _ast.Assign)
               for t in a.targets
               if isinstance(t, _ast.Subscript) and _ast.unparse(t).endswith("['argv']")]
    assert _stores, "통한 호출 형태를 기억하지 않는다(실제 질문 때 못 쓴다)"
    # 그리고 **질의 전용 인자가 섞이지 않은** 값이어야 한다 — 이 축이 새로 생긴 계약이다.
    assert all("_with_probe_extra" not in v for v in _stores), (
        f"질의 전용 인자가 캐시된 호출법에 섞인다 — 사용자 질문이 그 인자로 돈다: {_stores}")


def test_unknown_cli_can_actually_be_invoked():
    """표 밖 CLI 로도 인자가 **조립된다** — AI 가 답한 플래그를 그대로 쓴다."""
    mod = _load_runner()
    caps = {"label": "MyCLI",
            "models": [{"value": "big", "label": "Big"}],
            "efforts": [{"value": "deep", "label": "Deep"}],
            "model": ["--use-model", "{model}"], "effort": ["--think", "{effort}"],
            "argv": ["mycli", "-p", "{prompt}"], "source": "probe"}
    report = [{"runtime": "mycli", "label": "MyCLI",
               "models": caps["models"], "efforts": caps["efforts"]}]
    assert mod.build_cmd("mycli", "Q", "big", "deep", report, caps) == [
        "mycli", "-p", "--use-model", "big", "--think", "deep", "Q"]
    # 신고 밖 값은 표 밖 CLI 에서도 거부된다.
    assert mod.build_cmd("mycli", "Q", "--evil", "deep", report, caps) == [
        "mycli", "-p", "--think", "deep", "Q"]


def test_probed_flags_win_over_the_builtin_table():
    """AI 가 답한 호출법이 내장 표를 **이긴다**.

    실측에서 codex 는 `-m` 이 아니라 `--model` 을 답했다. 표가 이기면 그 답이 무의미해진다.
    """
    mod = _load_runner()
    caps = {"models": [{"value": "gpt-5.6-sol"}], "efforts": [{"value": "ultra"}],
            "model": ["--model", "{model}"],
            "effort": ["-c", "model_reasoning_effort={effort}"]}
    report = [{"runtime": "codex", "models": caps["models"], "efforts": caps["efforts"]}]
    got = mod.build_cmd("codex", "Q", "gpt-5.6-sol", "ultra", report, caps)
    assert "--model" in got and "-m" not in got, "내장 표의 플래그가 AI 응답을 덮었다"


def test_probe_timeout_is_not_zero():
    """`float(env or 120)` 함정 — `os.environ.get(k, "0")` 은 문자열 "0"(truthy)이라
    `or` 가 단락되지 않고 timeout 이 0 이 된다.

    그러면 질의가 시작하자마자 죽고 폴백이 조용히 삼켜 "AI 가 답을 안 했다" 로 보인다.
    실측으로 발견해 고친 자리라 값 자체를 잠근다.
    """
    mod = _load_runner()
    assert mod._CAPS_PROBE_TIMEOUT_SEC > 60, (
        f"질의 시간이 너무 짧다({mod._CAPS_PROBE_TIMEOUT_SEC}s) — 실측 codex 112s")


def test_probes_run_in_parallel():
    """여러 CLI 를 동시에 묻는다.

    순차면 기동이 각 응답 시간의 **합**만큼 늦어진다(실측 23s + 112s = 135s). 병렬이면 가장
    느린 하나로 끝난다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def detect_runtimes("):]
    fn = fn[:fn.index("\ndef ")]
    assert "threading.Thread(target=_probe" in fn, "질의가 순차다"
    assert "t.join(" in fn, "질의 스레드를 기다리지 않는다"


def test_cached_caps_are_re_enforced_on_load():
    """저장된 능력도 **로드할 때 다시 강제한다** — 안 하면 캐시 파일이 곧 우회 경로다.

    질의 응답은 `probe_runtime_caps` 가 강제하지만 그 결과는 `config.json` 을 거쳐 다음
    기동으로 돌아온다. 거기 적힌 플래그는 대조할 목록이 없어 그대로 `Popen` 인자가 된다.
    """
    mod = _load_runner()
    got = mod.sanitize_caps({
        # 플래그로 셸을 실행하려는 캐시
        "claude": {"models": [{"value": "opus"}], "model": ["sh", "-c", "{model}"],
                   "argv": ["claude", "-p", "{prompt}"]},
        # 호출 형태로 다른 실행 파일을 부르려는 캐시
        "evil2": {"models": [{"value": "x"}], "model": ["--m", "{model}"],
                  "argv": ["/bin/sh", "-c", "{prompt}"]},
        # 임의 플래그 편승
        "evil3": {"models": [{"value": "y"}], "model": ["--m", "{model}", "--yolo"]},
        # 런타임 이름 자체가 명령
        "; rm -rf /": {"models": [{"value": "a"}]},
        # 정상
        "ok": {"models": [{"value": "z"}], "model": ["--model", "{model}"],
               "argv": ["ok", "-p", "{prompt}"]},
    })
    assert got["claude"]["model"] is None, "셸 실행 플래그가 캐시로 되살아났다"
    assert got["evil2"].get("argv") is None, "다른 실행 파일을 부르는 호출 형태가 통과했다"
    assert got["evil3"]["model"] is None, "임의 플래그 편승이 캐시로 되살아났다"
    assert "; rm -rf /" not in got, "명령 형태의 런타임 이름이 통과했다"
    assert got["ok"]["model"] == ["--model", "{model}"], "정상 캐시까지 버렸다"
    assert got["ok"]["argv"] == ["ok", "-p", "{prompt}"]
    # 모델이 없는 항목은 아예 남기지 않는다(화면에 빈 그룹만 남는다).
    assert mod.sanitize_caps({"x": {"models": []}}) == {}
    assert mod.sanitize_caps("문자열") == {} and mod.sanitize_caps(None) == {}


def test_main_sanitizes_the_cache_it_loads():
    """`main` 이 캐시를 **그대로** 쓰지 않는다(위 강제를 실제로 통과시킨다)."""
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    assert "sanitize_caps(load_conf()" in body, (
        "저장된 능력을 검증 없이 신뢰한다 — 캐시 파일이 우회 경로가 된다")


# -- codex REV-20260828T230000 회귀 방어 (P2 6건) ------------------------------


def test_report_items_are_rebuilt_not_shallow_copied(monkeypatch):
    """신고 항목을 **재구성한다** — 얕은 복사면 오염된 여분 키가 HTTP 본문에 실려 나간다.

    서버 sanitizer 가 저장 전에 지우더라도 **전송은 이미 일어났다**. 그러면 "호출법은 서버로
    나가지 않는다" 는 이 기능의 계약이 거짓이 된다 (codex P2-1).
    """
    mod = _load_runner()
    caps = {"claude": {"label": "C",
                       "models": [{"value": "opus", "label": "Opus",
                                   "model": ["--secret-flag"], "extra": {"deep": 1}}],
                       "efforts": [{"value": "low", "label": "Low", "sneak": "x"}],
                       "model": ["--model", "{model}"],
                       "effort": ["--effort", "{effort}"], "source": "probe"}}
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    got = mod.detect_runtimes(cached=caps)
    blob = json.dumps(got, ensure_ascii=False)
    for leak in ("--secret-flag", "extra", "sneak", "deep"):
        assert leak not in blob, f"여분 키가 신고에 실렸다: {leak}"
    assert set(got[0]["models"][0]) == {"value", "label"}
    assert set(got[0]["efforts"][0]) == {"value", "label"}


def test_builtin_fallback_is_never_cached(monkeypatch):
    """폴백은 캐시하지 않는다 — 일시적 실패가 영구화되면 안 된다 (codex P2-3).

    최초 기동의 인증 지연으로 폴백했는데 그것이 캐시되면, 인증이 복구돼도 다시 묻지 않아
    낡은 내장 목록을 계속 보여준다. 사용자는 그것이 틀렸다는 사실조차 모른다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    detail: dict = {}
    mod.detect_runtimes(cached={}, detail_out=detail)   # 질의 없음 → 전부 builtin 폴백
    assert detail == {}, f"폴백이 캐시에 남았다: {list(detail)}"
    # 물어서 얻은 것은 남는다.
    detail2: dict = {}
    probed = {"claude": {"label": "C", "models": [{"value": "opus"}], "efforts": [],
                         "model": ["--model", "{model}"], "effort": None, "source": "probe"}}
    mod.detect_runtimes(cached=probed, detail_out=detail2)
    assert "claude" in detail2, "질의 결과가 캐시되지 않는다(매번 다시 묻는다)"


def test_probe_shares_one_absolute_deadline():
    """전체 질의에 **하나의 절대 deadline** — 후보를 순차로 시도해도 총량이 늘지 않는다.

    표 밖 CLI 는 후보마다 timeout 을 다 쓸 수 있어(240×2) main 의 대기를 넘긴다. 그러면 main 은
    폴백으로 기동하고, 남은 스레드가 아무도 읽지 않을 답을 위해 토큰을 계속 태운다 (codex P2-4).
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def detect_runtimes("):]
    fn = fn[:fn.index("\ndef ")]
    assert "deadline = time.monotonic()" in fn, "공유 deadline 이 없다"
    assert "left = deadline - time.monotonic()" in fn, "남은 시간을 후보마다 다시 재지 않는다"
    assert "timeout=left" in fn, "남은 시간을 질의에 넘기지 않는다"
    # `probe_runtime_caps` 가 그 값을 실제로 쓴다.
    probe_fn = src[src.index("def probe_runtime_caps("):]
    probe_fn = probe_fn[:probe_fn.index("\ndef ")]
    assert "timeout if timeout and timeout > 0" in probe_fn, "넘겨받은 시간을 무시한다"


@pytest.mark.parametrize("raw,expect_default", [
    ("abc", True),      # 형식 오류 — 종전엔 **import 가 실패**해 러너가 아예 안 떴다
    ("inf", True),      # Thread.join(inf) → OverflowError
    ("nan", True),      # Thread.join(nan) → ValueError
    ("-5", True),       # 기다리지 않고 background probe 를 방치
    ("0", True),
    ("999999", True),   # 범위 밖
    ("60", False),      # 정상
])
def test_probe_timeout_env_is_validated(monkeypatch, raw, expect_default):
    """설정 하나가 기동을 못 하게 만들면 안 된다 (codex P2-6)."""
    mod = _load_runner()
    monkeypatch.setenv("BRIDGE_CAPS_PROBE_TIMEOUT", raw)
    got = mod._probe_timeout_from_env()
    assert got == 240.0 if expect_default else got == 60.0
    # 어떤 값이든 `Thread.join()` 에 넣을 수 있어야 한다(유한 양수).
    assert got > 0 and got == got and got != float("inf")


def test_probe_output_and_json_scan_are_bounded():
    """오작동한 CLI 의 대량 출력이 CPU·메모리를 태우지 않는다 (codex P2-5)."""
    mod = _load_runner()
    assert mod._CAPS_PROBE_MAX_BYTES <= 1024 * 1024
    assert mod._CAPS_JSON_MAX_CANDIDATES <= 256
    # 닫히지 않은 `{` 가 대량이어도 후보 수 상한에서 멈춘다(O(n²) 방지).
    junk = "{" * 5000 + "not json"
    assert mod._extract_json(junk) is None
    # 상한 뒤에 있는 정상 JSON 은 못 찾는다 — 그것이 상한의 의미다(찾으려면 O(n²)).
    assert mod._extract_json("{" * 200 + '{"models":["x"]}') is None
    # 정상 범위에서는 그대로 찾는다.
    assert mod._extract_json("{" * 3 + '{"models":["x"]}')["models"] == ["x"]


def test_user_named_cli_is_not_silently_replaced():
    """`--ai mycli` 를 자동 감지가 갈아치우지 않는다 (codex P2-2).

    갈아치우면 runtime 지정이 없는 요청이 사용자가 고르지 않은 AI 로 처리되고, 캐시에도 틀린
    `kind` 가 남는다 — 사용자는 자기가 지목한 CLI 가 쓰이는 줄 안다.
    """
    # 2026-09-01: 선택 로직이 `main()` 안의 인라인 분기에서 `pick_ai()` 로 빠졌다. 계약은
    # 그대로이므로 **실제로 호출해서** 확인한다 — 소스 문자열 검사보다 견고하고, 이번 개정의
    # 계기가 정확히 「문자열은 맞는데 계약은 새는」 경우였다(표 안 이름은 실존 확인 자체가
    # 없어서 없는 AI 를 «있다» 고 답했다, codex 적대 리뷰 P2).
    mod = _load_runner()
    orig = mod._which_ai
    try:
        # 지목한 것만 없고 다른 AI 는 있는 상황 — 그래도 갈아치우지 않는다.
        mod._which_ai = lambda name: "/somewhere/codex" if name == "codex" else None
        assert mod.pick_ai("mycli", None) is None, "지목한 CLI 가 없자 다른 AI 로 대체했다"
        assert mod.pick_ai("claude", None) is None, "표 안 이름도 실존 확인을 거쳐야 한다"
        # 지목이 실재하면 그 이름을 그대로 쓴다(표 밖이어도).
        mod._which_ai = lambda name: f"/somewhere/{name}"
        assert mod.pick_ai("mycli", None) == ("mycli", ["mycli", "-p", "{prompt}"])
    finally:
        mod._which_ai = orig

    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    # 질의가 알아낸 호출 형태로 교정한다(기본 추정이 아니라).
    assert "_learned and kind not in _RUNTIME_SPECS" in body, (
        "질의는 성공했는데 답변은 추정 형태로 보낸다")


def test_resume_does_not_inherit_the_runtime_limit():
    """`--resume` 이 `ai` 를 **상속하지 않는다** (P0-Z5, 라이브 실측으로 발견).

    P0-Z3 이전에 `ai` 는 "무엇으로 답할까" 하나만 정했으므로 자동 감지 결과를 저장해 두는 것이
    편의였다. P0-Z3 이후 같은 값이 **신고 목록까지 좁힌다** — 의미가 바뀌었는데 저장·상속
    규칙이 그대로라, `--ai` 를 준 적 없는 사용자도 첫 기동의 감지 결과가 굳어 다음 재기동에서
    다른 런타임이 화면에서 사라진다. 라이브에서 실제로 codex 가 사라졌다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    resume_block = body[body.index("if args.resume:"):]
    resume_block = resume_block[:resume_block.index("if not args.base")]
    assert 'conf.get("ai")' not in resume_block, (
        "resume 이 ai 를 상속한다 — 자동 감지 결과가 다음 실행의 제한으로 승격된다")
    # base·ca·cmd 는 그대로 복원한다(그것들은 진짜 '설정' 이다).
    for keep in ('conf.get("base")', 'conf.get("ca")', 'conf.get("cmd")'):
        assert keep in resume_block, f"{keep} 복원이 사라졌다"


def test_only_explicit_ai_is_persisted():
    """저장하는 `ai` 는 **사용자가 명시한 것만** — 자동 감지 결과를 저장하면 제한이 된다."""
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    assert "save_conf(args.base, args.ca, kind, args.cmd)" not in body, (
        "자동 감지된 kind 를 ai 로 저장한다")
    assert body.count("save_conf(args.base, args.ca, (args.ai or \"\"), args.cmd") >= 1, (
        "명시 --ai 만 저장하는 형태가 아니다")


# -- 2026-08-31: 부분 응답이 축을 죽이던 결함 (라이브 실측) ----------------------
#
# 라이브 러너 캐시가 `{"models": [opus,sonnet,haiku], "efforts": [], "effort": null}` 로 굳어
# 있었다. claude 는 `--effort` 를 **실제로 지원한다**(`claude --help` 로 확인). 즉 AI 가 큰
# JSON 하나에서 `effort_flag` 하나를 빠뜨렸고, 종전 코드가 그걸 "지원하지 않음" 으로 읽어
# 등급 목록을 통째로 버린 것이다. 화면에서는 추론 강도 항목이 사라졌고, 사용자에게는
# "쓸 수 있는 effort 가 확인되지 않는" 상태로 보였다.


def test_partial_answer_does_not_kill_the_whole_axis(monkeypatch):
    """모델은 받고 등급은 못 받은 답이 **모델까지** 잃게 하지 않는다.

    반대 방향의 실수도 함께 막는다 — 축이 비었다고 질의 전체를 실패로 돌리면(`return None`)
    호출측이 내장 표로 폴백해, 그 AI 가 실제로 답한 모델 목록이 버려진다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_ask_json", lambda argv, prompt, timeout, reason_out=None: (
        {"label": "Claude", "models": [{"value": "opus"}], "model_flag": ["--model", "{model}"]}
        if prompt is mod._CAPS_PROBE_PROMPT else None))
    # 축 재질의도 실패하고 도움말도 못 읽는 상황 → 축만 비고 모델은 남는다.
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: None)
    got = mod.probe_runtime_caps("claude", ["claude", "-p", "{prompt}"])
    assert got is not None, "축 하나가 비었다고 질의 전체가 실패했다"
    assert [m["value"] for m in got["models"]] == ["opus"]
    assert got["efforts"] == [] and got["effort"] is None
    # 도움말을 **못 읽은** 상황이라 결론이 아니다 — 표지를 남기지 않아 다음 기동이 다시
    # 확인한다 (codex P2-2: 일시적 확인 실패가 영구 미지원으로 굳지 않게).
    assert got["effort_probed"] is False, "확인하지 못한 것을 확정으로 기록했다"

    # 도움말을 읽을 수 있으면 같은 입력이 **확정**으로 끝난다(그리고 축이 복구된다).
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: "  --effort <level>")
    got2 = mod.probe_runtime_caps("claude", ["claude", "-p", "{prompt}"])
    assert got2["effort"] == ["--effort", "{effort}"]
    assert got2["effort_probed"] is True


def test_missing_effort_flag_is_recovered_by_asking_again(monkeypatch):
    """1차에서 빠진 축을 **좁게 다시 물어** 되살린다 (실측: claude 가 이 경로로 답했다)."""
    mod = _load_runner()

    def _fake(argv, prompt, timeout, reason_out=None):
        if prompt is mod._CAPS_PROBE_PROMPT:
            return {"models": [{"value": "opus"}], "model_flag": ["--model", "{model}"]}
        return {"efforts": [{"value": "xhigh", "label": "매우높음"}],
                "effort_flag": ["--effort", "{effort}"]}

    monkeypatch.setattr(mod, "_ask_json", _fake)
    got = mod.probe_runtime_caps("claude", ["claude", "-p", "{prompt}"])
    assert got["effort"] == ["--effort", "{effort}"]
    assert [e["value"] for e in got["efforts"]] == ["xhigh"]


def test_recovery_falls_back_to_the_builtin_pair_only_when_help_confirms_it(monkeypatch):
    """재질의도 실패하면 **내장 표의 짝**을 쓰되, 그 CLI 의 도움말로 실재를 확인한다.

    `left=5.0` — 재질의 최소치(20초) 미만이라 ①은 건너뛰고, 양수라 ②(도움말 확인)는 돈다.
    (`left<=0` 이면 도움말도 부르지 않는다 — codex P1-3, 별도 테스트가 그쪽을 본다.)

    확인 없이 쓰면 우리 표가 낡은 순간(플래그가 사라진 CLI 버전) 고른 값이 조용히 무시되고,
    화면은 반영된다고 말한다. 도움말에 없으면 축을 비우는 것이 정직하다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: None)   # 재질의 실패
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: "  --effort <level>")
    flag, opts, settled = mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 5.0)
    assert flag == ["--effort", "{effort}"]
    assert [o["value"] for o in opts] == ["low", "medium", "high", "xhigh", "max"]
    assert settled is True

    # 도움말에 없다 → 축을 비우고, 그것은 **결론**이다(다시 묻지 않는다).
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: "  --model <name>")
    assert mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 5.0) == (None, [], True)

    # 도움말을 **못 읽은 것**은 "없다" 가 아니다 — 채택하지 않되 결론으로도 기록하지 않는다.
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: None)
    assert mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 5.0) == (None, [], False)


def test_reask_answer_of_no_support_is_checked_against_help(monkeypatch):
    """재질의의 "지정할 수 없다" 는 **`--help` 관측으로 반증될 수 있다**.

    ## ⚠ 이 계약은 2026-09-02 에 **의도적으로 뒤집혔다**

    종전 계약: 「AI 의 명시적 부정이 우리 표를 이긴다」 — 도움말을 아예 보지 않았다
    (그때 이 테스트는 `calls == []` 을 단정했다).

    바뀐 이유: 응답 시간 해소를 위해 능력 질의에 **도구 금지 가드**를 넣었다(제보 4차).
    그러자 claude 가 `{"efforts": [], "effort_flag": []}` 로 **자신 있게** 「없다」고
    답했다 — 그런데 claude 는 `--effort` 를 실제로 지원한다. 가드 이전에는 도구로 자기
    도움말을 읽어 5단계를 답했던 것이다. 라이브 실측: **5단계 → 0단계**로 추론 강도
    선택기가 화면에서 사라졌다.

    즉 **우리가 그 AI 에게 확인 수단을 금지했으므로 그 «없다» 는 관측이 아니라 기억이다.**
    반면 `--help` 는 그 바이너리에 직접 물은 관측이고, 「이 CLI 가 `--effort` 를 받는가」는
    의견이 아니라 **기계적 사실**이다. 기계적 사실에서는 관측이 기억을 이긴다.

    ## P0-Z4 를 깨지 않는다

    「목록의 출처는 연결된 AI」는 **모델 값**에 대한 계약이다(그 계정이 어떤 모델을 쓸 수
    있는지는 우리가 관측할 수 없다). 여기서 뒤집는 것은 **플래그의 존재 여부**뿐이고, 표의
    짝은 `--help` 로 실재를 확인한 뒤에만 채택된다 — 종전 계약이 지키려던 「그 CLI 버전에는
    없을 수 있다」는 그 도움말 검사가 그대로 보장한다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_ask_json", lambda argv, prompt, timeout, reason_out=None: {
        "efforts": [], "effort_flag": []})
    calls: list = []
    monkeypatch.setattr(mod, "_cli_help_text",
                        lambda name, timeout=0: calls.append(name) or "  --effort <level>")
    flag, opts, settled = mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 60.0)
    assert calls == ["claude"], "도구 없이 답한 부정을 도움말로 확인하지 않았다"
    assert flag == ["--effort", "{effort}"] and opts, (
        f"도움말이 `--effort` 를 보여주는데 축이 비었다 — 선택기가 사라진다: {flag}/{opts}")
    assert settled is True

    # 도움말에 **없으면** 그 부정은 참이다 — 표만 보고 채택하지 않는다(버전 안전성 유지).
    calls.clear()
    monkeypatch.setattr(mod, "_cli_help_text",
                        lambda name, timeout=0: calls.append(name) or "  --model <m>")
    assert mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 60.0) == (None, [], True)
    assert calls == ["claude"]

    # 표에 짝이 **없는** CLI 는 반증 근거가 없다 — 도움말을 부르지도 않는다.
    calls.clear()
    assert "mycli" not in mod._RUNTIME_SPECS
    assert mod._settle_effort_axis(
        "mycli", ["mycli", "-p", "{prompt}"], None, [], 60.0) == (None, [], True)
    assert calls == [], "표에 짝이 없는데 도움말을 읽었다 — 붙일 값이 없다"

    # ⚠ 그러나 **누락·오류는 부정이 아니다** (codex P1-2). 빈 객체·필드 누락은 "지원하지
    #   않는다" 가 아니라 "답하지 않았다" 이므로, 도움말 보완 단계로 내려가야 한다.
    for vague in ({}, {"efforts": []}, {"effort_flag": []}, {"efforts": [], "effort_flag": "x"}):
        monkeypatch.setattr(mod, "_ask_json", lambda a, p, t, reason_out=None, _v=vague: _v)
        monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: "  --effort <level>")
        flag, opts, settled = mod._settle_effort_axis(
            "claude", ["claude", "-p", "{prompt}"], None, [], 60.0)
        assert flag == ["--effort", "{effort}"], f"누락 응답({vague})을 미지원으로 오판했다"
        assert settled is True


def test_help_flag_check_uses_word_boundaries():
    """`--effort` 가 `--effort-level` 에 부분일치해 참이 되지 않는다.

    그 오탐은 "있다고 판단했는데 CLI 가 거부하는" 형태라, 사용자에게는 고른 값이 조용히
    무시되는 것으로 보인다(P0-T 가 지운 상태와 같다).
    """
    mod = _load_runner()
    assert mod._help_mentions_flag("  --effort <level>  Effort", ["--effort", "{effort}"]) is True
    assert mod._help_mentions_flag("  --effort-level <x>", ["--effort", "{effort}"]) is False
    # `-c key={effort}` 형태는 `=` 앞까지가 플래그 이름이다.
    assert mod._help_mentions_flag("  -c, --config", ["-c", "reasoning={effort}"]) is True
    # 위치 인자로 받는 형태·도움말 부재는 **판정 불가**(None) — "없다" 와 구분한다.
    assert mod._help_mentions_flag("anything", ["{model}"]) is None
    assert mod._help_mentions_flag(None, ["--effort", "{effort}"]) is None


@pytest.mark.parametrize("caps,expect", [
    ({"effort": None}, True),                              # 구 러너가 남긴 캐시 — 다시 확정한다
    ({"effort": None, "effort_probed": True}, False),      # 물어봤고 "없다" 였다 — 다시 묻지 않는다
    ({"effort": ["--effort", "{effort}"]}, False),         # 이미 있다
    ("문자열", False), (None, False),
])
def test_old_cache_is_recognized_as_unsettled(caps, expect):
    """`effort: null` 이 뭉갠 두 사실을 가른다.

    구분하지 않으면 이 복구가 **기존 사용자에게는 영영 실행되지 않는다** — 캐시가 있으니
    묻지 않고, 묻지 않으니 축이 계속 빈 채로 신고된다.
    """
    mod = _load_runner()
    assert mod._caps_axis_unsettled(caps) is expect


def test_unsettled_cache_is_re_probed_and_the_new_answer_wins(monkeypatch):
    """구 캐시는 축만 다시 확정하고, 그 결과가 캐시를 **이긴다**.

    반대로 두면(캐시 우선) 재확정이 매 기동마다 돌면서도 결과가 버려져, 사용자는 같은 빈
    목록을 계속 본다 — 고쳤는데 화면은 그대로인 가장 나쁜 형태다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    monkeypatch.setattr(mod, "_settle_effort_axis",
                        lambda *a, **k: (["--effort", "{effort}"],
                                         [{"value": "max", "label": "Max"}], True))
    # 전체 질의는 일어나지 않아야 한다 — 모델 목록은 이미 그 AI 가 답한 것이다.
    monkeypatch.setattr(mod, "probe_runtime_caps",
                        lambda *a, **k: pytest.fail("캐시가 있는데 전체를 다시 물었다"))
    stale = {"claude": {"label": "Claude", "models": [{"value": "opus", "label": "Opus"}],
                        "efforts": [], "model": ["--model", "{model}"], "effort": None,
                        "argv": ["claude", "-p", "{prompt}"], "source": "probe"}}
    detail: dict = {}
    got = mod.detect_runtimes(cached=stale, detail_out=detail, probe=True)
    assert [e["value"] for e in got[0]["efforts"]] == ["max"], "재확정 결과가 캐시에 밀렸다"
    assert [m["value"] for m in got[0]["models"]] == ["opus"], "모델 목록까지 다시 물었다"
    assert detail["claude"]["effort_probed"] is True, "표지가 캐시에 남지 않아 매번 다시 묻는다"


def test_sanitizer_preserves_the_settled_marker():
    """축 확정 표지가 캐시 로드에서 **살아남는다**.

    여기서 떨어뜨리면 확정을 마친 캐시가 매 기동마다 미확정으로 되살아나 같은 질의를
    반복한다 — 그리고 그 질의는 사용자 계정 토큰을 쓴다.
    """
    mod = _load_runner()
    got = mod.sanitize_caps({"claude": {
        "models": [{"value": "opus"}], "model": ["--model", "{model}"],
        "effort": None, "effort_probed": True}})
    assert got["claude"]["effort_probed"] is True
    # 표지가 없던 캐시는 없는 채로 남는다(그래야 재확정 대상이 된다).
    got2 = mod.sanitize_caps({"claude": {
        "models": [{"value": "opus"}], "model": ["--model", "{model}"], "effort": None}})
    assert got2["claude"]["effort_probed"] is False


def test_answer_body_carries_no_model_or_effort_note():
    """정상 답변 본문에는 모델·추론등급을 **쓰지 않는다** (사용자 결정 2026-08-31).

    확인 수단은 선택기 라벨이면 충분하고, 그쪽이 답변을 읽기 전에·다음 질문을 보내기 전에
    보인다. 답변마다 붙는 한 줄은 정상 경로에서 아무것도 더하지 않으면서 본문을 밀어낸다.

    **미반영 고지는 남는다** — 그건 다른 사실이다. "고른 값이 반영되지 않았다" 는 화면
    어디에도 드러나지 않으므로 답변이 유일한 통로다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def handle_one("):]
    body = body[:body.index("\ndef ")]
    assert "로 생성했습니다" not in body, "정상 답변에 모델·등급 고지가 남아 있다"
    assert "는 적용됐습니다" not in body, "미반영 고지에 반영 축 설명이 남아 있다"
    # 미반영 고지 자체는 유지된다.
    assert "기본 설정으로 답했습니다" in body, "미반영 사실까지 지웠다"
    # 목록에 있어도 **넘길 플래그가 없으면** 반영이 아니다 (codex P1-5) — 판정은 그대로.
    assert "_model_flag" in body and "_effort_flag" in body, (
        "플래그 유무를 보지 않아 미반영 판정이 느슨해진다")
    # 남은 고지(미반영)도 제목 규약을 밀어내지 않게 **제목 분리 뒤**에 있어야 한다.
    assert body.index("split_title(answer)") < body.index("기본 설정으로 답했습니다")


# -- 2026-08-31 (2차): 없는 모델을 보여주던 폴백 · 그룹 트리 --------------------
#
# 사용자 제보: codex 목록에 `gpt-5.1-*` 이 떴는데 그 계정이 실제로 쓸 수 있는 것은
# `gpt-5.6-sol`·`terra`·`luna`·`5.5`·`5.4` 였다. 원인은 내장 표를 **모델 목록 폴백**으로
# 쓴 것 — 표는 우리가 적어 둔 시점에 멈춰 있다.


def test_unprobed_runtime_is_not_reported_at_all(monkeypatch):
    """답한 적 없는 런타임은 **신고하지 않는다** — 빈 그룹도 남기지 않는다.

    "물어보지 못했다" 와 "이것을 쓸 수 있다" 는 다른 사실이다. 후자로 말하면 사용자는 없는
    모델을 고르고, CLI 는 거부하거나 조용히 다른 모델로 답한다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x")
    assert mod.detect_runtimes(cached={}) == [], "내장 모델 이름이 신고에 남아 있다"
def test_builtin_invocation_survives_so_execution_still_works(monkeypatch):
    """모델 목록은 빼도 **호출법은 남는다** — 없으면 실행 자체가 불가능해진다."""
    mod = _load_runner()
    for rt in ("claude", "codex", "gemini"):
        spec = mod._RUNTIME_SPECS[rt]
        assert spec.get("argv"), f"{rt}: 호출 형태가 사라졌다"
        # `runtimes` 없이 부르는 폴백 경로(단위 테스트·구 호출부)는 그대로 동작한다.
        cmd = mod.build_cmd(rt, "Q", None, None)
        assert cmd[-1] == "Q" and cmd[0] == rt


def test_probe_retries_once_for_table_runtimes():
    """표 안 CLI 도 **한 번 더** 묻는다.

    후보 호출 형태가 하나뿐이라 종전에는 첫 실패가 곧 포기였다. 내장 모델 폴백을 없앤 지금
    그 한 번의 실패는 "그 런타임이 화면에서 통째로 사라짐" 을 뜻한다(실측: codex 는 같은
    조건에서 성공과 실패를 오간다).
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def detect_runtimes("):]
    fn = fn[:fn.index("\ndef ")]
    assert "attempts = attempts * 2" in fn, "표 안 CLI 가 한 번만 시도한다"
    # deadline 검사는 루프 안에 그대로 있어야 한다(재시도가 총량을 넘기지 않게).
    retry_block = fn[fn.index("attempts = attempts * 2"):]
    assert "left <= 5.0" in retry_block, "재시도가 남은 시간을 보지 않는다"


def test_codex_builtin_table_matches_measured_generation():
    """표에 남은 codex 모델은 **실측 세대**다.

    신고에 쓰이지 않더라도 낡은 값이 코드에 남아 있으면 다음 사람이 그것을 현재 목록으로
    읽는다 — 이번 결함이 정확히 그렇게 시작했다.
    """
    mod = _load_runner()
    values = [m["value"] for m in mod._RUNTIME_SPECS["codex"]["models"]]
    assert not any(v.startswith("gpt-5.1") for v in values), "폐기된 세대가 표에 남아 있다"
    assert any(v.startswith("gpt-5.6") for v in values), "실측 세대가 표에 없다"


def test_probe_failure_log_does_not_promise_a_fallback():
    """실패 로그가 **없는 폴백을 약속하지 않는다** (자체 발견 2026-08-31).

    모델 목록 폴백을 없앤 뒤에도 로그는 「내장 기본값을 씁니다」라고 말하고 있었다. 그러면
    사용자는 목록이 있는 줄 알고 선택기를 찾고, 없는 이유를 어디서도 듣지 못한다 — 화면과
    로그가 서로 다른 사실을 말하는 상태다. 다음 행동(재시도 방법)까지 로그가 말해야 한다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    # 주석이 아니라 **사용자에게 나가는 문자열**만 본다 — 주석은 옛 문구를 인용할 수 있다.
    emitted = [ln for ln in src.splitlines()
               if "_log(" in ln or (ln.strip().startswith('"') or ln.strip().startswith("f\""))]
    blob = "\n".join(ln for ln in emitted if not ln.strip().startswith("#"))
    assert "내장 기본값을 씁니다" not in blob, "없는 폴백을 약속하는 문구가 남아 있다"
    fn = src[src.index("def detect_runtimes("):]
    fn = fn[:fn.index("\ndef ")]
    assert "목록에 나오지 않습니다" in fn, "목록에서 빠진다는 사실을 알리지 않는다"
    assert "--refresh-caps" in fn, "다시 시도할 방법을 말하지 않는다"


# -- codex REV-20260831T170000 회귀 방어 -----------------------------------------


def test_model_axis_needs_a_flag_too(monkeypatch):
    """모델 목록만 있고 **넘길 플래그가 없으면** 신고하지 않는다 (codex P1-2).

    목록만 신고하면 화면에는 고를 수 있는 것처럼 나오지만 `build_cmd` 가 인자를 붙이지 못해
    CLI 기본 모델로 답한다 — "고를 수 있는데 반영은 안 되는" 조작면의 재발이다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_cli_help_text", lambda name, timeout=0: None)
    monkeypatch.setattr(mod, "_ask_json", lambda argv, prompt, timeout, reason_out=None: {
        "models": [{"value": "foo"}], "model_flag": []})
    # 표 밖 CLI — 우리 표에도 플래그가 없다 → 목록을 비운다(= 그 런타임은 신고되지 않는다).
    got = mod.probe_runtime_caps("mycli", ["mycli", "-p", "{prompt}"])
    assert got["models"] == [], "넘길 방법이 없는 모델이 목록에 남았다"
    # 표 안 CLI — 우리 표의 플래그로 메운다(호출법 폴백은 유지하기로 한 축이다).
    got2 = mod.probe_runtime_caps("claude", ["claude", "-p", "{prompt}"])
    assert got2["model"] == ["--model", "{model}"]
    assert [m["value"] for m in got2["models"]] == ["foo"]


def test_help_is_not_called_without_time_left(monkeypatch):
    """남은 시간이 없으면 도움말도 부르지 않는다 (codex P1-3).

    종전에는 `left <= 0` 이어도 15초를 새로 줬다 — 호출측은 이미 폴백으로 떠난 뒤라 그
    시간은 아무도 읽지 않을 답을 기다리는 데 쓰인다.
    """
    mod = _load_runner()
    calls: list = []
    monkeypatch.setattr(mod, "_cli_help_text",
                        lambda name, timeout=0: calls.append(timeout) or "--effort")
    flag, opts, settled = mod._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"], None, [], 0.0)
    assert calls == [], "남은 시간이 없는데 도움말을 실행했다"
    assert (flag, opts) == (None, [])
    # 그리고 그것은 **결론이 아니다** — 확정으로 굳으면 다음 기동이 다시 보지 않는다.
    assert settled is False, "확인하지 못한 것을 확정으로 기록했다"


# -- 2026-08-31 (3차): 「재설치했는데 그대로」 ------------------------------------
#
# 사용자가 러너를 다시 받고 연결했는데도 옛 모델 목록(`gpt-5.1-*`)을 봤다. 원인은 그날 러너가
# **세 번** 바뀌었고 `AGENT_VERSION` 은 날짜 단위(`2026.08.31`)라 셋이 전부 같은 버전이었던 것.
# 화면·로그 어디에도 "지금 도는 러너가 배포본과 다르다" 는 사실이 없었다.


def test_runner_reports_its_own_file_fingerprint():
    """러너가 **자기 파일**의 지문을 신고한다 — 버전(날짜)이 답하지 못하는 질문이다."""
    mod = _load_runner()
    got = mod._self_build()
    assert re.fullmatch(r"[0-9a-f]{12}", got), f"지문 모양이 아니다: {got!r}"
    # 파일이 바뀌면 지문도 바뀐다(같은 날 여러 번 배포돼도 구분된다).
    import hashlib
    assert got == hashlib.sha256(_RUNNER.read_bytes()).hexdigest()[:12]


def test_heartbeat_carries_the_fingerprint_every_time():
    """지문을 **매번** 싣는다 — 서버가 언제든 대조할 수 있어야 한다."""
    mod = _load_runner()
    sent: list = []

    class _Api(mod.Api):
        def __init__(self):
            super().__init__("https://x", "t", None)

        def _post(self, path, payload=None, timeout=60.0):
            sent.append(payload)
            return {"ok": True}

    _Api().heartbeat([{"runtime": "claude", "models": [{"value": "opus"}], "efforts": []}])
    assert sent[0].get("agent_build") == mod._self_build(), "지문이 하트비트에 실리지 않는다"
    assert sent[0].get("agent_version") == mod.AGENT_VERSION, "버전 축이 사라졌다"


def test_stale_build_is_announced_once_not_every_beat():
    """구버전 경고는 **세션당 한 번**이다.

    30초마다 반복하면 소음이고, 소음은 곧 무시된다 — 정작 필요한 순간에 읽히지 않는다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def start_heartbeat("):]
    fn = fn[:fn.index("\ndef ")]
    assert "stale_build" in fn, "서버가 알려 준 사실을 러너가 읽지 않는다"
    assert "_stale_said" in fn, "매 하트비트마다 같은 경고를 반복한다"
    assert "배포본과 다릅니다" in fn, "무엇이 문제인지 말하지 않는다"
    # 다음 행동까지 말한다 — "다르다" 만으로는 사용자가 할 일을 모른다.
    assert "다시 받아" in fn or "다시 실행" in fn, "재설치 경로를 안내하지 않는다"


# -- 2026-09-01 (4차): 「연결한 AI 에 없는 모델이 뜬다」 — 런타임별 provenance ---------
#
# 폴백 제거(08-31 2차)와 지문 신고(3차)를 배포하고도 같은 제보가 돌아왔다. 원인은 **우리가
# 사용자 머신의 러너를 갱신할 수 없다**는 것이다: 낡은 빌드가 자기 소스의 내장 표를 계속
# 신고했고 서버는 그것을 그대로 화면에 그렸다.
#
# 처음 조치는 러너가 **전역 자격**(`caps_self_report`)을 선언하고 서버가 그 선언 없는 신고를
# 통째로 감추는 것이었다. 적대 패널 3인 확인 라운드가 그 설계를 기각했다 — 전역 불리언은
# 「이 빌드가 계약을 아는가」에만 답해 다음 포맷 변경에 다섯 번째 이름이 필요하고, 다중 러너
# fail-closed 라는 **제품 안에서 풀 수 없는 잠금**을 만들었다. 남은 것은 런타임 **단위**
# provenance 하나이며, 그것이 같은 클래스를 더 좁게·우아하게 닫는다.


def test_report_provenance_allowlists_match_on_both_sides():
    """런타임별 provenance 허용집합이 러너와 서버에서 **같다**.

    두 곳이 갈리면 한쪽이 조용히 느슨해진다 — 그리고 느슨한 쪽이 사용자가 보는 진실이 된다
    (이 feature 가 P0-R 에서 이미 겪은 형태). 특히 `builtin` 이 어느 한쪽에라도 들어오면
    「목록의 출처는 연결된 AI」 계약이 그 자리에서 깨지고, 서버는 검증 수단이 없다.
    """
    import ast

    mod = _load_runner()
    tree = ast.parse(_AI_TOOLS.read_text(encoding="utf-8"))
    server = None
    for n in ast.walk(tree):
        tgt = None
        if isinstance(n, ast.Assign):
            tgt = [t for t in n.targets if isinstance(t, ast.Name)]
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            tgt = [n.target]          # `X: frozenset = frozenset({...})` 는 AnnAssign 이다
        if tgt and any(t.id == "_SANITIZE_SOURCE_ALLOW" for t in tgt):
            v = n.value
            # `frozenset({...})` 는 리터럴이 아니라 Call 이라 `literal_eval` 이 거부한다.
            inner = v.args[0] if isinstance(v, ast.Call) and v.args else v
            server = set(ast.literal_eval(ast.unparse(inner)))
    assert server is not None, "서버에 provenance allowlist 가 없다"
    assert set(mod._REPORTABLE_SOURCES) == server, (
        f"양쪽 허용집합이 다르다: 러너 {sorted(mod._REPORTABLE_SOURCES)} vs 서버 {sorted(server)}")
    assert "builtin" not in server, (
        "내장 표 출처가 허용집합에 들어왔다 — `gpt-5.1-codex` 가 화면에 뜬 경로가 다시 열린다")
def test_builtin_model_table_never_reaches_the_report(monkeypatch):
    """자격 신고가 **참이어야 한다** — 내장 표의 모델 이름은 신고에 닿지 않는다.

    이 단정이 자격의 유일한 전제다: 서버는 신고 내용의 출처를 검증할 수단이 없고, 러너가
    「내 목록은 AI 가 답한 것뿐」이라 말한 것을 믿는다. 폴백이 되살아나면 그 선언이 거짓이
    되고, 서버 게이트는 거짓을 통과시킨다(§16.7 G11 — 게이트로 쓰는 검사 자체의 진위).

    ollama 는 예외다 — 그 목록은 우리가 적은 값이 아니라 HTTP **실조회** 결과다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x")
    # probe 를 전부 실패시킨다 = 폴백만 남는 조건(라이브에서 codex 가 정확히 이 상태였다).
    monkeypatch.setattr(mod, "probe_runtime_caps", lambda *a, **k: None)

    reported = mod.detect_runtimes(cached={})
    reported_values = {m["value"] for rt in reported for m in rt["models"]}
    builtin_values = {
        m["value"]
        for name, spec in mod._RUNTIME_SPECS.items() if name != "ollama"
        for m in (spec.get("models") or [])
    }
    assert builtin_values, "표가 비어 이 단정이 아무것도 검사하지 않는다(자기충족 방지)"
    assert not (reported_values & builtin_values), (
        f"내장 표의 모델이 신고에 실렸다: {sorted(reported_values & builtin_values)}")
    assert reported == [], "물어보지 못한 런타임이 신고에 남았다"


def test_builtin_table_never_reaches_the_report_on_any_branch(monkeypatch):
    """내장 표가 신고에 닿지 않는다 — **cached·probe 두 분기 모두** (qa M9b).

    종전 판본은 `detect_runtimes(cached={})` 만 불렀고 `probe` 기본값이 `False` 라
    monkeypatch 한 `probe_runtime_caps` 가 **한 번도 호출되지 않았다** — docstring 이
    서술한 「probe 를 전부 실패시킨다」는 진입하지 않는 분기였다. 그리고 러너의 정상 기동
    경로는 바로 그 *cached* 경로다(`--refresh-caps` 가 예외). 그 사이로 뮤턴트 M9b
    (빈 cached 항목을 `_RUNTIME_SPECS` 로 다시 채움)가 생존했다.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x")
    monkeypatch.setattr(mod, "probe_runtime_caps", lambda *a, **k: None)

    builtin = {m["value"] for n, s in mod._RUNTIME_SPECS.items() if n != "ollama"
               for m in (s.get("models") or [])}
    assert builtin, "표가 비어 이 단정이 아무것도 검사하지 않는다(자기충족 방지)"

    stale_cache = {"codex": {"label": "Codex", "models": [], "efforts": [],
                             "model": ["-m", "{model}"], "effort": None, "source": "cache"}}
    for label, kwargs in (("cached-empty", {"cached": {}}),
                          ("cached-stale", {"cached": stale_cache}),
                          ("probe-fail", {"cached": {}, "probe": True})):
        got = mod.detect_runtimes(**kwargs)
        values = {m["value"] for rt in got for m in rt["models"]}
        assert not (values & builtin), f"{label}: 내장 표 모델이 신고에 실렸다 {sorted(values & builtin)}"
        assert got == [], f"{label}: 물어보지 못한 런타임이 신고에 남았다"


def test_report_carries_runtime_provenance(monkeypatch):
    """신고 항목마다 **출처**가 실린다 — 서버가 런타임 단위로 다시 거른다."""
    mod = _load_runner()
    monkeypatch.setattr(mod, "_which", lambda n: "/usr/bin/x" if n == "claude" else None)
    caps = {"claude": {"label": "Claude", "models": [{"value": "opus", "label": "Opus"}],
                       "efforts": [], "model": ["--model", "{model}"], "effort": None,
                       "source": "probe"}}
    got = mod.detect_runtimes(cached=caps)
    assert [r["runtime"] for r in got] == ["claude"]
    assert got[0]["source"] == "probe", "출처가 신고에 실리지 않는다"


# ── codex 적대리뷰 (2026-09-02) — 재설계 뒤에도 남아 있던 fail-open 셋 ──────────────


class _BuildColumnlessCursor:
    """`RunnerBuild` 컬럼이 **없는** 배포를 흉내낸다 — 그 컬럼을 건드리는 문장만 실패한다."""

    def __init__(self):
        self.sql: list = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        flat = " ".join(str(sql).split())
        self.sql.append(flat)
        if "RunnerBuild" in flat:
            raise RuntimeError("Unknown column 't.RunnerBuild' in 'field list'")
        self.rowcount = 1

    def fetchone(self):
        return None

    def close(self):
        pass


def test_report_write_degrades_when_the_fingerprint_column_is_absent():
    """지문 컬럼이 없는 배포에서도 **능력·기능·버전은 새겨진다** (codex P1).

    이 설계의 전제는 「화석 목록은 **첫 하트비트에** 지워진다」이고, 그 지움은
    `set_runner_report` 가 정제된 목록(`[]`)을 쓰는 것으로만 일어난다. 그런데 지문 축은
    `account_runner_build` 가 **컬럼 없는 배포를 명시적으로 지원**(`None` = 판정 안 함)하는데
    쓰기 축이 그 배포에서 통째로 실패하면, 하트비트 핸들러가 예외를 삼키는 동안
    `LastHeartbeatAt` 만 갱신되고 **옛 builtin 목록이 영구히 화면에 남는다** — 이 cycle 이
    닫으려는 바로 그 결함이 그 모집단에서만 살아남는 형태다.

    그래서 한 단 내려가 재시도한다. 「지문을 못 새김」이 「목록을 못 지움」이 되어서는 안 된다.
    """
    import oauth_store as store

    cur = _BuildColumnlessCursor()
    wrote = store.set_runner_report(cur, "tok", "[]", ["console_jobs"], "2026.09.02", "abc123")

    assert len(cur.sql) == 2, f"강등 재시도가 없다 — 실행된 문장 {len(cur.sql)}개"
    assert "RunnerBuild" in cur.sql[0], "첫 시도가 지문을 쓰지 않는다(정상 배포 경로 소실)"
    assert "RunnerBuild" not in cur.sql[1], "재시도가 여전히 지문 컬럼을 건드린다"
    # 나머지 세 축은 **반드시** 남아야 한다 — 그것이 화석을 지우는 유일한 경로다.
    for col in ("RunnerCapabilities", "RunnerFeatures", "RunnerAgentVersion"):
        assert col in cur.sql[1], f"강등 문장이 {col} 을 빠뜨렸다 — 화석이 그대로 남는다"
    assert wrote is True, "강등 경로가 '쓰지 않았다'로 보고한다"


def test_roster_never_calls_a_token_that_never_ran_a_runner_stale():
    """하트비트가 **한 번도 없던** 토큰은 지문 판정 대상이 아니다 (codex P2).

    운영 명부는 러너가 아닌 토큰(등록형 MCP 클라이언트 등)도 일부러 포함한다. 그 행의
    `RunnerBuild` 는 NULL 이고, 「지문 미신고 = 구 러너」 규칙이 그것을 구버전으로 읽으면
    **러너를 띄운 적도 없는 계정**에 「최신 실행 파일로 다시 실행하세요」가 붙는다 —
    모르는 것을 stale 로 부르지 않는다는 이 cycle 자신의 규칙 위반이다.
    """
    import oauth_store as store

    class _RosterCursor:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return self._rows

        def close(self):
            pass

    # (AccountId, Username, LastHeartbeatAt, age_sec, features, version, build, caps)
    rows = [
        (7, "runner_user", "2026-09-02T00:00:00", 10, "console_jobs", "2026.09.02", "", "[]"),
        (9, "mcp_only", None, None, None, None, None, None),
    ]
    got = store.list_live_runners(_RosterCursor(rows), limit=10)
    by_acct = {r["account_id"]: r for r in got}

    assert by_acct[7]["runner_build"] == "", "실제 러너의 «지문 미신고» 가 «모름» 으로 뭉개졌다"
    assert by_acct[9]["runner_build"] is None, (
        "하트비트가 없던 토큰에 빈 지문을 주고 있다 — 명부가 그것을 구버전으로 적는다")

    from routers.ai_tools import runner_build_is_stale
    import routers.ai_tools as ai_tools

    orig = ai_tools._deployed_runner_build
    ai_tools._deployed_runner_build = lambda: "deadbeefcafe"
    try:
        assert runner_build_is_stale(by_acct[7]["runner_build"]) is True
        assert runner_build_is_stale(by_acct[9]["runner_build"]) is False, (
            "러너를 띄운 적 없는 계정에 갱신 지시가 나간다")
    finally:
        ai_tools._deployed_runner_build = orig


def test_missing_catalog_hides_the_selector_through_the_real_entry_point():
    """카탈로그를 못 받으면 **선택기를 숨긴다** — 진입점(`_composerModelSelectorHidden`)에서 (codex P2).

    종전 판본은 `undefined !== "hidden"` 이라는 이유로 「보임」을 돌려줬다. 그러면
    `/api/api-vault/options` 실패 화면이 **목록 없는 선택기 + 서버 기본값 라벨**을 그대로
    내보내고, 같은 이유로 「모델 목록을 불러오지 못했습니다」 안내 분기가 **도달 불가능한
    죽은 코드**가 된다.

    ⚠ 그 분기는 jsdom 하네스가 **직접 호출**해 통과시키고 있었다 — 헬퍼가 옳은 것과
    진입점이 그 헬퍼를 그렇게 부르는 것은 다른 사실이다. 그래서 여기서는 **진입점**을 본다.
    """
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "feature-0003-agent-web-ui" / "src" / "static" / "app" / "composer.js"
           ).read_text(encoding="utf-8")
    fn = src[src.index("function _composerModelSelectorHidden("):]
    fn = fn[:fn.index("\nfunction ")]
    body = "\n".join(ln for ln in fn.split("\n") if not ln.strip().startswith("//"))
    assert "if (!catalog) return true;" in body, (
        "카탈로그 부재를 «보임» 으로 읽는다 — 안내 분기가 도달 불가능해진다")
