"""자식 AI CLI 가 실패했을 때 **사유가 사용자에게 도달하는가** (TASK-20260901T160000).

## 이 파일이 고정하는 라이브 결함

대화 `…d7010dcf` (2026-09-01 15:38 · 15:39) 에서 사용자는 같은 질문을 두 번 보내고 두 번 다
아래 문장만 받은 뒤 대화를 떠났다.

    AI 가 오류로 끝났습니다(exit 1):

콜론 뒤가 비어 있다. 실제 사유는 `claude` CLI 가 **stdout** 으로 낸
`You've hit your session limit · resets 5:30pm (Asia/Seoul)` 였고, 러너는 stderr 만 실어
보냈다(그 stderr 에는 stdin 안내 한 줄뿐). 한도는 몇 분 뒤 풀리는 회복 가능한 상태였는데,
사용자에게는 «무엇이 잘못됐는지도, 무엇을 하면 되는지도» 없었다.

따라서 잠그는 것은 "한도" 가 아니라 **사유를 버리는 경로**다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 라이브에서 실측한 그 출력 (stdout / stderr 배치까지 동일).
_LIVE_STDOUT = "You've hit your session limit · resets 5:30pm (Asia/Seoul)"
_LIVE_STDERR = ("Warning: no stdin data received in 3s, proceeding without it. "
                "If piping from a slow command, redirect stdin explicitly.")


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_cli_fail", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_case_reason_reaches_the_user():
    """실측 재현: stdout 에만 있는 사유가 사용자 문장에 실린다."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(1, _LIVE_STDOUT, _LIVE_STDERR)
    assert "session limit" in msg, "사유가 사라졌다 — 이 결함이 그대로 돌아왔다"
    assert "5:30pm" in msg, "언제 풀리는지가 사라지면 사용자는 재시도 시점을 모른다"


def test_live_case_never_ends_with_empty_colon():
    """사용자가 실제로 본 표면(빈 콜론)이 다시 나오지 않는다."""
    mod = _load_runner()
    for out, err in ((_LIVE_STDOUT, _LIVE_STDERR), ("", ""), ("", _LIVE_STDERR)):
        msg = mod.describe_cli_failure(1, out, err).strip()
        assert not msg.endswith(":"), f"빈 콜론으로 끝났다: {msg!r}"
        assert "):" not in msg.split("\n")[0], (
            f"사유 자리가 비어 보이는 형태가 남아 있다: {msg!r}")


def test_no_output_at_all_is_stated_not_implied():
    """출력이 정말 없으면 «없다» 고 말한다 — 침묵으로 두지 않는다."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(1, "", "")
    assert "알 수 없습니다" in msg


def test_stderr_noise_alone_does_not_shadow_stdout_reason():
    """stderr 에 잡음만 있으면 stdout 사유가 이긴다 (이 결함의 정확한 기전)."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(1, _LIVE_STDOUT, _LIVE_STDERR)
    assert "no stdin data received" not in msg, "잡음이 사유 자리를 차지했다"


def test_real_stderr_reason_still_wins():
    """stderr 에 **의미 있는** 줄이 있으면 그쪽이 사유다(종전 동작 보존)."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(2, "부분 출력", "error: unknown option --effort")
    assert "unknown option --effort" in msg


def test_recoverable_classes_tell_the_user_what_to_do():
    """회복 가능한 실패는 «다음에 할 행동» 을 준다 — 사유만으로는 재시도 판단이 안 선다."""
    mod = _load_runner()
    assert "다시 보내면" in mod.describe_cli_failure(1, _LIVE_STDOUT, "")
    assert "로그인" in mod.describe_cli_failure(1, "Please run /login", "")
    assert "DQA" in mod.describe_cli_failure(2, "", "unknown option --effort")
    assert "설치" in mod.describe_cli_failure(127, "", "claude: command not found")


def test_unknown_failure_gets_no_invented_advice():
    """맞는 부류가 없으면 안내를 지어내지 않는다(오도가 침묵보다 나쁘다)."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(3, "", "segmentation fault")
    assert "segmentation fault" in msg
    assert msg.count("\n") == 0, f"근거 없는 안내가 붙었다: {msg!r}"


def test_credentials_never_ride_along_in_the_reason():
    """사유를 살리는 일이 토큰 유출이 되면 안 된다 — 답변은 대화에 영구 저장된다."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(
        1, "auth failed for mat_S3cr3tTokenValue with Bearer mat_S3cr3tTokenValue", "")
    assert "mat_S3cr3t" not in msg
    assert "<가려짐>" in msg


def test_reason_is_bounded():
    """거대한 출력이 통째로 대화에 실리지 않는다."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(1, "x" * 50000, "")
    assert len(msg) < mod._FAIL_DETAIL_MAX + 200


def test_failure_path_uses_the_shared_describer():
    """`_run_cli_cancelable` 이 사유 조립을 **한 곳에서** 한다.

    두 벌이 되면 한쪽만 고쳐지고 다른 경로가 조용히 옛 표면으로 남는다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src.split("def _run_cli_cancelable", 1)[1].split("\ndef _kill", 1)[0]
    assert "describe_cli_failure(" in body
    assert "box.get('err', '')[:400]" not in body, "옛 stderr-only 경로가 남아 있다"


def test_hint_matching_does_not_fire_on_incidental_digits():
    """`401` 같은 짧은 토큰이 무관한 숫자에 걸려 엉뚱한 안내를 주지 않는다."""
    mod = _load_runner()
    msg = mod.describe_cli_failure(1, "", "processed 1401 rows then crashed")
    assert "로그인" not in msg, f"우연한 숫자에 인증 안내가 붙었다: {msg!r}"
