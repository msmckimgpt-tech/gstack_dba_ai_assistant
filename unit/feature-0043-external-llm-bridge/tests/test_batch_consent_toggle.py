"""feature-0043 (TASK-20260901T190000) — 배경 배치 동의의 **웹 토글** 계약.

사용자 결정(2026-09-01): *"`--batch` 와 같이 명령어를 구성하는 부분과 같이, 접근성이 떨어지는
부분은 별도로 구성합니다. 웹페이지에서 토글할 수 있도록 구성해주세요."*

## 이 파일이 잠그는 것

1. **진리표** — 서버 동의와 머신 override 의 조합이 무엇을 신고하게 하는가.
2. **이음매** — 서버 `shared.bridge_consent` 와 러너 안의 거울 구현이 **같은 입력에 같은 답**을
   내는가. 러너는 단일 파일이라 shared 를 import 하지 못하고 손으로 맞춰 둔 두 구현이다.
   양쪽을 각각 검사하면 한쪽만 고쳐지는 날 조용히 갈린다 — 그 갈림은 프로세스 경계에서만
   드러나고, 단위 테스트가 구조적으로 못 본다(이 feature 가 자가 검증 축에서 이미 겪었다:
   27건 green + 기능 0% 동작).
3. **fail-closed** — 모르는 값은 「받지 않음」으로 떨어지는가. 이 축은 **남의 계정 토큰**을
   태우므로 관대함이 곧 사고다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from shared import bridge_consent as srv
from shared.bridge_tasks import RUNNER_FEATURE_BATCH_JOBS

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_batch_consent", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: (server_consent, local_override) → batch_jobs 를 신고하는가.
_TRUTH_TABLE = [
    (False, None, False),   # 아무 지시 없음 + 서버 꺼짐 → 받지 않는다
    (True, None, True),     # **웹 토글만으로 켜진다** — 이 cycle 의 핵심
    (False, True, True),    # `--batch`: 이 머신에서 명시 허용(서버가 꺼져 있어도)
    (True, False, False),   # `--no-batch`: 이 머신만 예외(서버가 켜져 있어도)
    (None, None, False),    # 서버가 값을 안 줬다 → 모르면 받지 않는다
    ("", None, False),
    ("1", None, True),      # DB TINYINT / 폼 문자열
    (0, None, False),
    ("0", None, False),     # ⚠ 비어 있지 않은 문자열을 참으로 읽으면 여기서 걸린다
]


def test_server_truth_table():
    for consent, override, want in _TRUTH_TABLE:
        feats = srv.apply_consent(("console_jobs", "self_review"),
                                  server_consent=consent, local_override=override)
        assert (RUNNER_FEATURE_BATCH_JOBS in feats) is want, (
            f"server: consent={consent!r} override={override!r} → {feats}")
        # 배치 외의 신고는 **건드리지 않는다** — 건드리면 `--no-self-review` 같은 다른 축이
        # 동의 갱신 한 번에 조용히 되살아난다.
        assert "console_jobs" in feats and "self_review" in feats


def test_runner_mirror_matches_server_exactly():
    """이음매: 러너의 거울 구현이 서버 정본과 **한 칸도 다르지 않다**.

    손으로 맞춰 둔 두 구현이라, 이 대조가 없으면 한쪽만 고쳐지는 날 웹 토글이 켜져 있는데
    러너는 신고하지 않는(또는 그 반대) 상태가 된다.
    """
    runner = _load_runner()
    assert runner.BATCH_FEATURE == srv.BATCH_FEATURE
    for consent, override, _want in _TRUTH_TABLE:
        base = ("console_jobs", "self_review")
        got_srv = srv.apply_consent(base, server_consent=consent, local_override=override)
        got_run = runner.apply_consent(base, server_consent=consent, local_override=override)
        assert got_srv == got_run, (
            f"이음매가 갈렸다 — consent={consent!r} override={override!r}: "
            f"서버 {got_srv} vs 러너 {got_run}")
        assert runner.normalize_consent(consent) == srv.normalize_consent(consent)


def test_runner_cli_override_is_three_valued():
    """`--batch` / `--no-batch` / 무지시 가 **세 값**으로 읽힌다.

    무지시를 `False` 로 접으면 웹 토글이 영영 반영되지 않는다 — 이 cycle 이 없애려는 상태가
    정확히 그것이다(플래그를 붙여 다시 띄워야만 바뀌던 것).
    """
    runner = _load_runner()

    class _Args:
        def __init__(self, batch=False, no_batch=False):
            self.batch = batch
            self.no_batch = no_batch

    assert runner._batch_override_from_args(_Args()) is None
    assert runner._batch_override_from_args(_Args(batch=True)) is True
    assert runner._batch_override_from_args(_Args(no_batch=True)) is False
    # 모순된 지시는 **끄는 쪽**. 남의 계정 사용량을 태우는 방향으로 기울 근거가 없다.
    assert runner._batch_override_from_args(_Args(batch=True, no_batch=True)) is False


def test_heartbeat_without_the_key_does_not_flip_consent():
    """서버 응답에 `batch_consent` 가 **없으면** 러너는 직전 값을 유지한다.

    구 서버·기록 실패 응답에는 이 키가 없다. 없는 것을 `False` 로 읽으면 서버가 잠깐 흔들릴
    때마다 동의가 진동하고, 그 진동이 배급 자격을 30초 단위로 뒤집는다.

    러너 소스에서 **그 가드를 직접 확인한다** — 하트비트 루프는 스레드라 단위 호출로 구동하기
    어렵고, 가드가 사라지면 이 파일의 다른 테스트는 전부 통과한 채 라이브만 깨진다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    assert '"batch_consent" in res' in src, (
        "키 존재 확인이 사라졌다 — 없는 값을 False 로 읽으면 동의가 진동한다")


def test_notice_is_server_owned_and_says_what_it_costs():
    """고지 문구는 서버가 소유하고, **무엇을 태우는지**를 말한다."""
    assert srv.CONSENT_NOTICE
    assert "사용량" in srv.CONSENT_NOTICE, "무엇을 소비하는지 말하지 않으면 동의가 아니다"
    assert "요청하지 않은" in srv.CONSENT_NOTICE
