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
        # 2026-08-28: 동시 처리 + 취소 시 자식 프로세스 종료. 둘 다 표준 라이브러리라
        # 무설치 계약은 유지된다(`pip install` 이 필요한 것이 하나도 없다).
        "threading",
        # feature-0045: 연결 복구 백오프·배포 교대 하한(대기가 아니라 실패·교대 경로).
        "time",
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


def test_runner_waits_for_a_slot_before_asking_the_server():
    """워커가 다 찼으면 **자리를 기다린 뒤** 서버에 묻는다(2026-08-28).

    순서가 반대면 tight loop 가 된다: 열린 질문이 남아 있는 한 `wait_for_request` 는 즉시
    응답하므로, 자리가 없는데 계속 물으면 초당 수십 번 서버를 두드린다. 세마포어는 블로킹이라
    이 대기에도 sleep 이 필요 없다.
    """
    import ast

    tree = ast.parse(CANON.read_text(encoding="utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.get_source_segment(CANON.read_text(encoding="utf-8"), main) or ""
    loop = body[body.index("while True:"):]
    assert "slots.acquire()" in loop, "워커 자리를 기다리지 않는다"
    assert loop.index("slots.acquire()") < loop.index('api.call("wait_for_request"'), (
        "자리를 잡기 전에 서버에 묻는다 — 워커가 다 차면 tight loop 가 된다")


def test_runner_claims_in_the_wait_loop_not_in_the_worker():
    """점유는 대기 루프에서 한다 — 워커로 미루면 같은 task 를 반복해서 받는다.

    점유해야 그 task 가 `wait_for_request` 결과에서 빠진다. 점유를 워커까지 미루면 그 사이
    같은 id 가 계속 돌아오고, 그 반복이 곧 서버를 두드리는 loop 다.
    """
    src = CANON.read_text(encoding="utf-8")
    handle = src[src.index("def handle_one("):]
    handle = handle[:handle.index("\ndef ")]
    assert 'api.call("claim_request"' not in handle, (
        "워커가 점유한다 — 대기 루프에서 점유해야 중복 수신이 사라진다")
    assert 'api.call("claim_request"' in src, "점유 경로 자체가 사라졌다"


def test_runner_abandons_canceled_work_without_submitting():
    """취소된 작업은 **제출하지 않는다**(2026-08-28 사용자 결정).

    제출해도 서버가 409 로 거절하지만, 러너가 먼저 멈춰야 개인 계정 토큰이 덜 탄다.
    실패(`제출한다`)와 취소(`제출하지 않는다`)가 **다른 값**으로 구분되는지도 함께 잠근다 —
    같은 값이면 호출측이 둘 중 하나를 반드시 틀리게 처리한다.
    """
    src = CANON.read_text(encoding="utf-8")
    assert "CANCELED = " in src, "취소를 실패와 구분하는 신호가 없다"
    assert "canceled_task_ids" in src, "서버의 취소 통보를 읽지 않는다"
    handle = src[src.index("def handle_one("):]
    handle = handle[:handle.index("\ndef ")]
    assert "if answer == CANCELED:" in handle, "취소를 실패와 같이 처리한다(=제출해 버린다)"
    # 제출 **직전**에도 한 번 더 본다 — 답을 만드는 동안 취소됐을 수 있다.
    assert handle.index("_canceled()") < handle.index('api.call("submit_answer"'), (
        "제출 직전 취소 재확인이 없다")


def test_runner_kills_the_child_on_cancel():
    """취소되면 진행 중인 AI **프로세스를 죽인다**.

    죽이지 않으면 아무도 볼 수 없는 답을 위해 최대 `_AI_TIMEOUT_SEC` 동안 개인 계정 토큰이
    계속 탄다 — 취소의 실질 목적이 바로 그 낭비를 막는 것이다. `subprocess.run` 은 끝날
    때까지 블로킹이라 이 계약을 만족할 수 없다.
    """
    src = CANON.read_text(encoding="utf-8")
    assert "subprocess.Popen(" in src, "블로킹 실행이라 취소를 반영할 수 없다"
    assert "def _kill(" in src and "proc.kill()" in src, "자식을 종료하지 않는다"
    runner = src[src.index("def _run_cli_cancelable("):]
    runner = runner[:runner.index("\ndef ")]
    assert "cancel_check()" in runner, "실행 중 취소를 확인하지 않는다"
    assert "pump.join(" in runner, "자식 대기가 블로킹이 아니다(sleep 루프 의심)"


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
    # 2026-08-28: 취소 시 자식을 죽이려면 `Popen` 이어야 해서 `capture_output=True` 대신
    # 파이프를 명시한다. 계약의 알맹이는 같다 — **출력을 잡아둔다**(터미널로 새지 않는다).
    assert "stdout=subprocess.PIPE" in src and "stderr=subprocess.PIPE" in src, (
        "출력을 캡처하지 않는다 — 답변을 회수할 수 없고 사용자 터미널로 샌다")


def test_runner_submits_even_on_ai_failure():
    """AI 가 실패해도 **답을 제출한다** — 침묵하면 사용자 화면이 30분간 대기 상태로 남는다."""
    src = CANON.read_text(encoding="utf-8")
    idx = src.index("if not ok or not answer.strip():")
    tail = src[idx:idx + 900]
    assert "submit_answer" in src[idx:idx + 1600], "실패 시 제출 경로가 없다"
    assert "자동 안내로 대체" in tail, "실패를 사용자에게 알리지 않는다"


# ── 러너 타임아웃 ↔ 서버 점유 lease (2026-08-28, 라이브 실측 후) ────────────────


def _runner_const(name: str) -> float:
    """러너 모듈을 import 하지 않고 상수만 읽는다(AST — 실행 부작용 없음)."""
    import ast as _ast

    tree = _ast.parse(CANON.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, _ast.Name) and tgt.id == name:
                    return float(_ast.literal_eval(node.value))
    raise AssertionError(f"bridge_agent.py 에서 상수 {name} 을 찾지 못했다")


def _server_lease_sec() -> float:
    import ast as _ast
    import pathlib as _p

    shared = _p.Path(__file__).resolve().parents[3] / "shared" / "bridge_tasks.py"
    tree = _ast.parse(shared.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, _ast.Name) and tgt.id == "BRIDGE_CLAIM_LEASE_MIN":
                    return float(_ast.literal_eval(node.value)) * 60.0
    raise AssertionError("shared/bridge_tasks.py 에서 BRIDGE_CLAIM_LEASE_MIN 을 찾지 못했다")


def test_ai_timeout_fits_inside_the_claim_lease():
    """러너가 lease **밖에서** 제출하면 그 사이 다른 세션이 같은 질문을 다시 집을 수 있다.

    타임아웃이 lease 를 넘으면, 답을 다 만들고도 제출이 거절되거나 같은 질문이 두 번 처리된다.
    """
    timeout = _runner_const("_AI_TIMEOUT_SEC")
    lease = _server_lease_sec()
    assert timeout < lease, (
        f"AI 타임아웃({timeout:.0f}s)이 서버 점유 lease({lease:.0f}s)를 넘는다")
    # 제출에 쓸 여유가 남아야 한다 — 타임아웃 직후의 submit_answer 도 lease 안에서 끝나야 한다.
    assert lease - timeout >= 60, (
        f"lease 여유가 {lease - timeout:.0f}s 뿐이다 — 제출이 lease 밖으로 밀릴 수 있다")


def test_ai_timeout_uses_most_of_the_lease():
    """너무 이르게 포기하지 않는다 — 서버가 아직 기다리는데 러너만 끊는 구간을 없앤다.

    라이브 실측(2026-08-27): 900초(=lease 의 절반)에서 27단계 조사가 끊겼고, 사용자 화면에는
    "AI 호출이 900초를 넘겨 중단했습니다" 만 남았다. 개인 AI 는 답을 만드는 중이었다.
    """
    timeout = _runner_const("_AI_TIMEOUT_SEC")
    lease = _server_lease_sec()
    assert timeout >= lease * 0.8, (
        f"AI 타임아웃({timeout:.0f}s)이 lease({lease:.0f}s)의 80% 에 못 미친다 — "
        "서버는 기다리는데 러너가 먼저 포기하는 구간이 남는다")
