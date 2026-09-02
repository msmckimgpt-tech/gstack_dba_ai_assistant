"""러너 **배포본이 소스에서 재현되는가** — 그리고 그 빌드가 실제로 배선돼 있는가.

## 계약이 바뀐 이유 (feature-0043 모듈 분할)

종전 계약은 「배포본(`static/agent/`)과 정본(`src/bridge_agent.py`)이 같은 파일인가」였다.
둘 다 **커밋된 바이트 동일 사본**이었기 때문이다. 그 배치는 최근 90일 49개 커밋이 **예외 없이
둘 다** 고치게 만들었고(49/49), 관심사가 서로 다른 두 세션도 264KB 짜리 같은 파일에서 반드시
만나 충돌했다.

이제 소스는 `src/agent/` 패키지 하나이고 **둘 다 빌드 생성물**이다 — 그래서 「둘이 같은가」는
동어반복이 됐다(같은 스크립트가 같은 소스로 만든다). 대신 이 파일이 지키는 것은 그 전환이
만든 **새 실패 모드**들이다:

  - 빌드가 결정적이지 않으면 배포마다 지문이 흔들려 「구버전으로 돌고 있다」 판정이 무의미해진다.
  - 모듈을 추가하고 `_EMIT_ORDER` 에 넣지 않으면 그 코드가 배포본에서 **조용히 사라진다**.
  - Dockerfile 의 빌드 RUN 이 빠지면 **배포는 성공하고 러너 다운로드만 404** 가 된다.
    healthz·soak·대화 스모크는 전부 초록불이다(서버는 멀쩡하므로) — 그 침묵을 여기서 끊는다.
  - 생성물이 다시 커밋되면 충돌 표면이 원상 복구된다.
"""
from __future__ import annotations

import ast
import hashlib
import pathlib
import subprocess
import sys

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_ROOT = _UNIT.parent
CANON = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
SERVED = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_agent.py"
PKG = _UNIT / "feature-0043-external-llm-bridge" / "src" / "agent"
BUILDER = _UNIT / "feature-0002-agent-core" / "src" / "scripts" / "build_bridge_agent.py"
DOCKERFILE = _UNIT / "feature-0002-agent-core" / "src" / "Dockerfile"
DEPLOY = _ROOT / "bin" / "deploy-web.sh"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_built_runner_matches_the_source_package(tmp_path):
    """배포본이 **지금의 소스**에서 나온 것인가 (재현 가능한가).

    실패하면 「우리가 테스트한 것」과 「사용자가 내려받는 것」이 갈렸다는 뜻이다. 루트
    `conftest.py` 가 collection 전에 배치하므로 정상 경로에서는 항상 통과한다 — 실패는
    빌드 스크립트나 소스 패키지가 깨졌다는 신호다.
    """
    assert SERVED.is_file(), "배포본이 없다 — AI 가 내려받을 파일이 존재하지 않는다"
    out = tmp_path / "bridge_agent.py"
    r = subprocess.run([sys.executable, str(BUILDER), "--src", str(PKG), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"빌드 실패: {r.stderr}"
    assert _sha(out) == _sha(SERVED), (
        "배포본이 소스 패키지에서 재현되지 않는다 — `make bridge-agent` 로 재빌드하라")
    assert _sha(CANON) == _sha(SERVED), "정본 경로와 배포 경로의 산출물이 다르다"


def test_build_is_deterministic(tmp_path):
    """같은 소스 → 같은 바이트. 흔들리면 지문(`_self_build`) 대조가 무의미해진다.

    러너는 자기 파일 해시를 서버에 신고하고, 서버는 그것으로 「정확히 그 파일인가」를 판정한다
    (`ai_tools._served_runner_build`). 빌드가 비결정적이면 재빌드마다 지문이 바뀌어 사용자가
    「재설치했는데 구버전이라고 나온다」를 겪는다.
    """
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    for out in (a, b):
        assert subprocess.run(
            [sys.executable, str(BUILDER), "--src", str(PKG), "--out", str(out)],
            capture_output=True, text=True).returncode == 0
    assert _sha(a) == _sha(b), "같은 소스로 두 번 빌드했는데 바이트가 다르다"


def test_every_module_is_in_the_emit_order():
    """패키지에 있는 모듈은 **전부** 번들에 실린다.

    `_EMIT_ORDER` 에서 빠진 모듈은 오류를 내지 않는다 — 그냥 배포본에 없다. 그 침묵이 가장
    비싸므로 여기서 집합 동일성으로 못박는다. (빌드 스크립트도 같은 검사를 하지만, 그건
    빌드를 돌려야 드러난다. 이 테스트는 CI 가 매번 본다.)
    """
    init = PKG / "__init__.py"
    order = None
    for node in ast.parse(init.read_text(encoding="utf-8")).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(t, ast.Name) and t.id == "_EMIT_ORDER" for t in targets):
            order = list(ast.literal_eval(node.value))
    assert order, "__init__.py 에 _EMIT_ORDER 가 없다"
    on_disk = {p.stem for p in PKG.glob("*.py")} - {"__init__"}
    assert set(order) == on_disk, (
        f"_EMIT_ORDER 와 패키지 파일이 어긋난다 — 목록에만={sorted(set(order) - on_disk)} "
        f"파일만={sorted(on_disk - set(order))}. 목록에서 빠진 모듈은 배포본에서 사라진다")
    assert len(order) == len(set(order)), "_EMIT_ORDER 에 중복이 있다(코드가 두 번 실린다)"


def test_module_graph_has_no_cycles():
    """패키지 내부 import 가 비순환인가.

    번들(단일 네임스페이스)에서는 순환이 드러나지 않지만 패키지 형태에서는 `ImportError` 가
    된다 — 그러면 모듈 단위 lint·단위테스트라는 분할의 이득이 사라진다. 가변 전역을 공유하는
    모듈은 `state.py` 처럼 접근자로 분리한다(그 모듈 docstring 참조).
    """
    dep = {}
    for p in sorted(PKG.glob("*.py")):
        if p.stem == "__init__":
            continue
        dep[p.stem] = {n.module for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                       if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module}
    state, cycles = {}, []

    def visit(n, path):
        state[n] = 1
        for m in sorted(dep.get(n, ())):
            if state.get(m) == 1:
                cycles.append(" → ".join(path[path.index(m):] + [m]))
            elif not state.get(m):
                visit(m, path + [m])
        state[n] = 2

    for n in sorted(dep):
        if not state.get(n):
            visit(n, [n])
    assert not cycles, f"모듈 순환 의존: {cycles}"


def test_package_form_imports_cleanly():
    """`agent/` 를 **패키지로도** import 할 수 있는가 — 모듈 분할의 이득이 걸린 지점.

    번들은 단일 네임스페이스라 패키지 형태의 import 오류를 **덮어 버린다**: `from .x import y`
    의 `y` 를 오타내도 번들러가 그 줄을 지우므로 배포본은 멀쩡히 돈다. 그러면 「모듈 단위로
    lint·테스트한다」는 분할의 목적이 조용히 죽는다 — 아무도 패키지를 import 하지 않으므로
    깨진 사실이 드러나지 않는다.

    비순환 검사(`test_module_graph_has_no_cycles`)는 **순환** 축만 본다. 이 테스트는 이름
    해석까지 포함해 「패키지가 실제로 살아 있는가」를 본다.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_bridge_agent_pkg", PKG / "__init__.py",
        submodule_search_locations=[str(PKG)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bridge_agent_pkg"] = mod
    try:
        spec.loader.exec_module(mod)
        assert getattr(mod, "_EMIT_ORDER", None), "_EMIT_ORDER 가 노출되지 않는다"
        # 각 모듈이 실제로 적재됐는가 (import 문만 있고 이름이 안 붙는 경우 방지)
        for name in mod._EMIT_ORDER:
            assert hasattr(mod, name), f"패키지에 {name} 모듈이 붙지 않았다"
    finally:
        for k in [k for k in sys.modules if k.startswith("_bridge_agent_pkg")]:
            del sys.modules[k]


def test_image_build_wires_the_runner_build():
    """Dockerfile 이 러너를 **실제로 만드는가**.

    생성물을 커밋하지 않기로 한 이상, 이 RUN 이 배포본의 유일한 출처다. 빠지면 배포는
    성공하고 러너 다운로드만 404 가 된다 — 서버가 멀쩡하므로 어떤 헬스체크도 울지 않는다.
    (2026-08-12 교훈의 재적용: COPY 되지 않는 경로에 코드를 두면 repo 테스트는 통과하고
    배포만 죽는다.)
    """
    df = DOCKERFILE.read_text(encoding="utf-8")
    assert "build_bridge_agent.py" in df, "Dockerfile 이 러너 배포본을 만들지 않는다"
    assert "COPY unit/feature-0043-external-llm-bridge/src" in df, (
        "러너 소스 패키지가 이미지로 COPY 되지 않는다 — 빌드가 읽을 것이 없다")
    assert df.index("build_bridge_agent.py") < df.index("inject_asset_stamp.py"), (
        "러너 빌드가 자산 스탬프 계산보다 뒤에 있다 — 러너가 static 트리 content-hash 에서 "
        "빠져 종전 동작과 달라진다")


def test_deploy_gate_verifies_the_runner_exists():
    """배포 파이프라인이 baked 이미지의 러너를 검증하는가 (하드 게이트)."""
    sh = DEPLOY.read_text(encoding="utf-8")
    assert "bridge_runner_verify" in sh, "deploy-web.sh 에 러너 배포본 검증 게이트가 없다"
    assert sh.count("bridge_runner_verify") >= 2, (
        "게이트가 정의만 되고 **호출되지 않는다** — 정의는 검증이 아니다")


def test_generated_artifacts_are_ignored():
    """생성물이 다시 커밋되면 충돌 표면이 원상 복구된다.

    이 전환의 목적 자체가 「생성물을 커밋하지 않는다」이므로(AGENTS.md §13.1 «1순위»),
    무시 규칙이 사라지면 90일 49/49 이중 커밋이 그대로 돌아온다.

    `git ls-files` 가 아니라 `.gitignore` 를 읽는 이유: 테스트는 git 이 없는 컨테이너에서도
    돈다(`make test` 의 agent 이미지에 git 이 없다). 도구 부재로 조용히 통과하는 검사보다
    규칙 자체를 보는 편이 확실하다.
    """
    ignored = {l.strip() for l in (_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
    for rel in ("unit/feature-0043-external-llm-bridge/src/bridge_agent.py",
                "unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py",
                "unit/feature-0003-agent-web-ui/src/static/agent/bridge_setup.sh",
                "unit/feature-0003-agent-web-ui/src/static/agent/bridge_setup.ps1"):
        assert rel in ignored, f".gitignore 에 빌드 생성물 {rel} 이 없다 — 다시 커밋된다"


def test_runner_has_no_third_party_imports():
    """stdlib 전용 — `pip install` 이 필요하면 파이썬 환경마다 결과가 갈린다(=환경 차이)."""
    import ast

    tree = ast.parse(CANON.read_text(encoding="utf-8"))
    stdlib = {
        "argparse", "json", "os", "shlex", "ssl", "subprocess", "sys",
        # 2026-08-28 P0-Z4: AI 가 답한 모델·등급 **값의 모양**을 검사한다
        # (내용이 아니라 모양만 — 어떤 모델이 있는지는 그 AI 의 소관이다).
        "re",
        # 2026-08-28: 동시 처리 + 취소 시 자식 프로세스 종료. 둘 다 표준 라이브러리라
        # 무설치 계약은 유지된다(`pip install` 이 필요한 것이 하나도 없다).
        "threading",
        # feature-0045: 연결 복구 백오프·배포 교대 하한(대기가 아니라 실패·교대 경로).
        "time",
        # 2026-08-31: 이 파일 자체의 지문(`_self_build`) — 서버 배포본과 대조해 «구버전으로
        # 돌고 있다» 를 알린다. 표준 라이브러리라 무설치 계약은 그대로다.
        "hashlib",
        # TASK-20260901T140000: 러너 인스턴스 발급(`secrets`) + 종료 시 자기 점유 해제
        # (`atexit`·`signal`). 셋 다 표준 라이브러리 — 무설치 계약은 그대로다.
        "secrets", "atexit", "signal",
        # TASK-20260901T163000: 예외 스택을 사건 원장에 남긴다(`_short_traceback`). 종전엔
        # `str(e)` 만 남아 예외 형과 터진 자리가 통째로 버려졌다. 표준 라이브러리.
        "traceback",
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

    # 허용 목록(2026-08-28 codex 조치로 배압 2종이 늘었다). 전부 **대기가 아닌 경로**다 —
    # 연결 복구 · 배포 교대 · 워커 포화 배압 · 점유 실패 배압 · 제출 재시도.
    allowed = {
        "time.sleep(backoff)",                                        # 연결 복구 백오프
        "time.sleep(_DRAINING_RETRY_FLOOR_SEC)",                      # 배포 교대 / 워커 포화
        "time.sleep(_RECONNECT_BACKOFF_START)",                       # 제출 1회 재시도
        "time.sleep(min(_RECONNECT_BACKOFF_MAX, "
        "_DRAINING_RETRY_FLOOR_SEC * stalled))",                      # 점유 실패 배압
    }
    sleeps = sorted({l.strip() for l in code.split("\n") if "sleep(" in l})
    extra = [s for s in sleeps if s not in allowed]
    assert not extra, (
        f"허용되지 않은 sleep 이 있다: {extra}. 대기 자체에 간격을 두면 그것이 폴링이고, "
        "간격이 곧 환경 차이다. 새 sleep 을 넣으려면 그것이 **대기가 아님**을 여기 명시하라")

    # ★ 핵심 계약: **대기 호출 자체는 sleep 과 붙어 있지 않다.** 위 목록이 늘어나도 이건 불변이다.
    loop = code[code.index("while True:"):]
    wait_line = loop.index('api.call("wait_for_request"')
    window = loop[max(0, wait_line - 300):wait_line]
    assert "sleep(" not in window, (
        "대기 호출 **직전**에 sleep 이 있다 — 그것이 주기 폴링이다(간격이 곧 환경 차이)")
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


def test_runner_reads_the_server_even_while_saturated():
    """포화 중에도 **서버는 읽는다**. tight loop 방지는 디스패치 **뒤**에 있다.

    계약이 2026-08-28 codex 리뷰로 뒤집혔다. 종전은 "자리를 잡은 뒤에 묻는다" 였고, 슬롯이
    2개일 때는 무해했다. 그런데 기본이 1이 되면서 치명적이 됐다 — 작업 하나가 도는 동안 대기
    루프가 통째로 멈춰 **새 질문도 취소 통보도 받지 못한다.** 취소는 이 응답 채널로만 오므로,
    사용자가 중단을 눌러도 최대 `_AI_TIMEOUT_SEC`(1700초) 동안 개인 계정 토큰이 계속 탄다.

    원래 의도(간격 없는 재호출 금지)는 사라지지 않고 **자리를 옮겼다**: 한 건도 시작하지
    못한 라운드에서만 `wait_for_free()` 로 막는다. 서버는 취소를 한 번만 알리고 점유를 놓으므로
    (`ai_tools.wait_for_request` 가 같은 교훈으로 그렇게 고쳐졌다) 할 일 없는 즉시-반환이
    반복되지 않는다.
    """
    import ast

    src = CANON.read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.get_source_segment(src, main) or ""
    loop = body[body.index("while True:"):]
    assert loop.index('api.call("wait_for_request"') < loop.index("pool.try_acquire()"), (
        "자리를 잡은 뒤에 서버를 읽는다 — 포화 중 취소·새 질문을 놓친다")
    # 간격 없는 재호출 금지: 자리가 없으면 짧은 간격을 두고 되돌아온다(블로킹이 아니다 —
    # 막으면 그동안 서버를 못 읽어 취소 인지가 자리 반납에 묶인다).
    guard = loop[loop.index("if sid is None:"):]
    assert "time.sleep(_DRAINING_RETRY_FLOOR_SEC)" in guard[:200], (
        "자리가 없을 때 간격 없이 되돌아온다 — 서버를 두드리는 hot loop 가 된다")


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
    """claude·codex·gemini 를 모두 다룬다(AI 종류에 무관해야 한다).

    ⚠ 로컬 LLM(ollama) 어댑터는 2026-09-01 에 제거했다 — 사용자 결정(미사용). 그 분기는
    HTTP 라 명령 템플릿 하나로 덮이지 않아 자기 몫의 결함을 계속 만들었고, 마지막은
    provenance 라벨을 바꾸다 캐시 쓰기 가드를 뒤집어 목록이 굳은 것이었다.
    """
    src = CANON.read_text(encoding="utf-8")
    for name in ("claude", "codex", "gemini"):
        assert f'"{name}"' in src, f"{name} 어댑터가 없다"
    assert "--cmd" in src, "임의 런타임을 위한 수동 지정 경로가 없다"
    assert '"ollama"' not in src, (
        "제거한 로컬 LLM 어댑터가 되살아났다 — 되살리려면 provenance 두 집합부터 보라")


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
    # 고정 글자수 window 를 쓰지 않는다 — 그 사이에 한 줄만 늘어도(주석 포함) 제출 호출이
    # 창 밖으로 밀려 "제출 경로가 없다" 는 거짓 실패가 난다(2026-08-31 실제로 그랬다).
    # 이 분기가 속한 **함수의 나머지 전체**를 본다.
    fn_tail = src[idx:idx + src[idx:].index("\ndef ")]
    assert "submit_answer" in fn_tail, "실패 시 제출 경로가 없다"
    assert "자동 안내로 대체" in fn_tail, "실패를 사용자에게 알리지 않는다"


# ── 러너 타임아웃 ↔ 서버 점유 lease (2026-08-28, 라이브 실측 후) ────────────────


def _runner_const_expr(name: str) -> str:
    """상수 대입식의 **기본값 리터럴**만 뽑는다(`os.environ.get(..., "0")` 의 "0")."""
    import ast as _ast

    tree = _ast.parse(CANON.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, _ast.Name) and tgt.id == name:
                    # `os.environ.get("KEY", "0")` 의 **두 번째** 인자(기본값)를 본다.
                    for sub in _ast.walk(node.value):
                        if isinstance(sub, _ast.Call) and len(sub.args) >= 2:
                            default = sub.args[1]
                            if isinstance(default, _ast.Constant):
                                return str(default.value)
                    return _ast.unparse(node.value)
    raise AssertionError(f"bridge_agent.py 에서 상수 {name} 을 찾지 못했다")


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


def test_ai_timeout_is_unlimited_by_default():
    """⚠ 계약이 바뀌었다(사용자 요구 2026-08-28).

    직전 계약은 "타임아웃이 lease 안에 있고 그 80% 이상" 이었다 — 즉 **여전히 러너의 시계로
    끊는다**는 전제였다. 사용자 요구는 그 전제 자체를 지웠다:

        "기본적으로 time_out 은 진행되어선 안되며, 각 단계에 대한 갱신을 수신받는 부분을
         기준으로. 연결은 살아있는 상태입니다."

    지금 기본값은 **0(상한 없음)** 이고, 멈춘 것과 일하는 것은 서버가 관측한 **진행 신호**로
    가른다(도구 호출 → lease 갱신 → 멈추면 30분 뒤 회수 → 제출 409 → 러너 하차).
    """
    assert _runner_const_expr("_AI_TIMEOUT_SEC") == "0", (
        "러너가 여전히 고정 상한을 기본값으로 들고 있다 — 일하는 AI 를 시계로 끊는다")


def test_timeout_check_is_skipped_when_unlimited():
    """상한이 0 인데 비교를 그대로 두면 `waited >= 0` 이 첫 tick 에 참이 되어 **즉시** 끊긴다."""
    src = CANON.read_text(encoding="utf-8")
    assert "if _AI_TIMEOUT_SEC and waited >= _AI_TIMEOUT_SEC:" in src, (
        "상한 0(무제한)일 때 검사를 건너뛰지 않는다 — 모든 호출이 즉시 중단된다")
    # (종전 두 번째 단언은 ollama HTTP 경로의 `timeout=(_AI_TIMEOUT_SEC or None)` 을
    #  요구했다. 그 경로는 2026-09-01 에 제거됐다 — 남은 것은 CLI `Popen` 경로뿐이고
    #  그쪽 무제한 계약은 위 단언 하나가 잠근다.)


def test_cancel_still_works_without_a_timeout():
    """무제한이 '사용자가 멈출 수 없다' 를 뜻하면 안 된다."""
    src = CANON.read_text(encoding="utf-8")
    assert "_CANCEL_TICK_SEC" in src and "cancel_check()" in src, (
        "취소 감시가 사라졌다 — 상한이 없는데 멈출 수도 없으면 개인 계정 토큰이 계속 탄다")


def test_timeout_is_opt_in():
    """스스로 상한을 걸고 싶은 사용자를 위한 경로는 남긴다(기본값이 아닐 뿐)."""
    src = CANON.read_text(encoding="utf-8")
    assert "--ai-timeout" in src and "BRIDGE_AI_TIMEOUT_SEC" in src
