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
        "argparse", "json", "os", "shlex", "ssl", "subprocess", "sys", "time",
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
    """**대기**에 sleep·간격이 없어야 한다 — 대기는 서버가 한다(사용자 요구: 폴링 금지).

    feature-0045 로 계약이 한 겹 정밀해졌다. 종전엔 파일 전체에서 `sleep` 을 금지했는데, 그
    금지가 **연결 실패 경로까지** 덮고 있었다: 서버가 배포로 교체되는 몇 초 동안 러너는
    초당 수천 번을 재시도하며 사용자 머신의 CPU 를 태웠다(무한 busy-loop).

    대기와 재연결은 다른 일이다. 그래서 금지 대상을 **간격 있는 대기**로 좁히되,
    허용되는 sleep 은 재연결 백오프 **하나뿐**임을 함께 고정한다 — 넓게 풀면 그 틈으로
    주기 폴링이 돌아온다.
    """
    src = CANON.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.split("\n")
                     if l.strip() and not l.strip().startswith("#"))
    assert "wait_for_request" in code, "블로킹 대기 도구를 쓰지 않는다"

    sleeps = sorted(l.strip() for l in code.split("\n") if "sleep(" in l)
    assert sleeps == ["time.sleep(_DRAINING_RETRY_FLOOR_SEC)", "time.sleep(backoff)"], (
        f"허용되지 않은 sleep 이 있다: {sleeps}. 러너의 sleep 은 **정확히 둘**이다 — "
        "연결 복구 백오프와 배포 교대 하한. 대기 자체에 간격을 두면 그것이 폴링이고, "
        "간격이 곧 환경 차이다")
    # 백오프는 연결 실패에서만 자란다. 정상 응답 경로가 이 값을 건드리면 대기가 느려진다.
    assert "backoff = 0.0" in code, "성공 시 백오프를 되돌리지 않으면 지연이 누적된다"
    assert "_RECONNECT_BACKOFF_MAX" in code, "백오프 상한이 없으면 복구가 무한정 늦어진다"
    # 교대 하한은 **자라지 않는다**(백오프가 아니다). 자라면 배포마다 인지가 점점 늦어진다.
    floor = next(l for l in code.split("\n") if "_DRAINING_RETRY_FLOOR_SEC =" in l)
    val = float(floor.split("=")[1].strip())
    assert 0 < val <= 1.0, (
        f"교대 하한이 {val}s 다 — 1초를 넘으면 질문 인지가 체감될 만큼 늦어지고, 0 이면 "
        "엣지가 후보를 빼기 전 2초 창에서 호출이 폭주해 계정 상한을 태운다")
    # 사용자가 대기 간격을 지정할 수 있으면 그 값이 곧 환경 차이다(러너에는 그런 인자가 없다).
    assert "--poll" not in code, "대기 간격 인자가 생겼다 — 환경 차이를 만든다"


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
