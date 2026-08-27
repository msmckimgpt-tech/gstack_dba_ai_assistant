"""러너 배포본이 정본과 **같은 파일**인가.

`static/agent/bridge_agent.py` 는 AI 가 내려받는 실물이고, `src/bridge_agent.py` 는 정본이다.
둘이 갈리면 **사용자가 받는 것과 우리가 테스트한 것이 달라진다** — 그 순간 모든 검증이 무의미해진다.
"""
from __future__ import annotations

import hashlib
import pathlib

_UNIT = pathlib.Path(__file__).resolve().parents[2]
CANON = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
SERVED = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_agent.py"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_served_runner_is_identical_to_canonical():
    assert SERVED.exists(), "배포본이 없다 — AI 가 내려받을 파일이 존재하지 않는다"
    assert _sha(SERVED) == _sha(CANON), (
        "배포본과 정본이 다르다. 정본을 고쳤으면 배포본도 갱신해야 한다 — "
        "cp unit/feature-0043-external-llm-bridge/src/bridge_agent.py "
        "unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py")


def test_runner_has_no_third_party_imports():
    """stdlib 전용 — `pip install` 이 필요하면 파이썬 환경마다 결과가 갈린다(=환경 차이)."""
    import ast

    tree = ast.parse(CANON.read_text(encoding="utf-8"))
    stdlib = {
        "argparse", "json", "os", "shlex", "ssl", "subprocess", "sys",
        "urllib", "urllib.error", "urllib.parse", "urllib.request", "__future__",
    }
    external = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            external += [a.name for a in node.names if a.name.split(".")[0] not in
                         {m.split(".")[0] for m in stdlib}]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] not in {m.split(".")[0] for m in stdlib}:
                external.append(node.module)
    assert not external, f"외부 의존성이 들어왔다: {external}"


def test_runner_does_not_poll():
    """러너에 sleep·간격이 없어야 한다 — 대기는 서버가 한다(사용자 요구: 폴링 금지)."""
    src = CANON.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.split("\n")
                     if l.strip() and not l.strip().startswith("#"))
    assert "time.sleep" not in code and "sleep(" not in code, (
        "러너가 잠들며 기다린다 — 그것이 폴링이고, 간격이 곧 환경 차이다")
    assert "wait_for_request" in code, "블로킹 대기 도구를 쓰지 않는다"


def test_runner_covers_every_runtime():
    """claude·codex·gemini·로컬 LLM 을 모두 다룬다(AI 종류에 무관해야 한다)."""
    src = CANON.read_text(encoding="utf-8")
    for name in ("claude", "codex", "gemini", "ollama"):
        assert f'"{name}"' in src, f"{name} 어댑터가 없다"
    assert "--cmd" in src, "임의 런타임을 위한 수동 지정 경로가 없다"


def test_runner_passes_prompt_as_argv_not_shell():
    """프롬프트를 셸로 넘기지 않는다 — 질문 본문에 셸 메타문자가 섞이면 명령 주입이 된다."""
    src = CANON.read_text(encoding="utf-8")
    assert "shell=True" not in src, "셸을 거쳐 실행한다(명령 주입 경로)"
    assert "capture_output=True" in src


def test_runner_submits_even_on_ai_failure():
    """AI 가 실패해도 **답을 제출한다** — 침묵하면 사용자 화면이 30분간 대기 상태로 남는다."""
    src = CANON.read_text(encoding="utf-8")
    idx = src.index("if not ok or not answer.strip():")
    tail = src[idx:idx + 900]
    assert "submit_answer" in src[idx:idx + 1600], "실패 시 제출 경로가 없다"
    assert "자동 안내로 대체" in tail, "실패를 사용자에게 알리지 않는다"
