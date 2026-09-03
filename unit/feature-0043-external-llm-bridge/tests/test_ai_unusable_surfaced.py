"""응답하지 않는 AI 를 **영원히 기다리지 않는다** (TASK-20260903T140000).

## 이 파일이 고정하는 라이브 결함 (사용자 지적 2026-09-03)

> 「결국, 모델을 탐색하는데 실패했다는거네요. 이러한 사실이 사용자에게는 알려지지 않고
>  영원히 기다리게 됩니다. 작동에 이슈가 나타난 사실이 해소되지 않았으니 명백한 오류입니다.」

실측된 구조적 원인:

| # | 관측 |
|---|---|
| 1 | 능력 협상 실패는 **모델 선택기만 숨겼다** — 「답할 수 없다」로 취급되지 않았다 |
| 2 | 그래서 러너가 질문을 정상 점유했고 `claude.exe -p` 가 무한 응답 없음(300초 실측, 출력 0바이트) |
| 3 | 러너 AI 호출 상한 `_AI_TIMEOUT_SEC` **기본 0 = 무제한** · 무진전 감시 없음 |
| 4 | 서버 `BRIDGE_NO_PROGRESS_SEC=900` 은 주석대로 **"표시 경계이지 종료 조건이 아니다"** |
| 5 | lease 30분 만료 → **재배달** → 시도 횟수 상한도, 종결 상태도 없음 |

## 설계 — 왜 「무출력 N초」가 아니라 「아플 때만 짧게」인가

무출력만으로는 「생각 중」과 「멈춤」을 가를 수 없다(`claude -p` 는 답을 끝에 한 번에 낸다).
고정 상한은 실제로 27단계 조사를 죽인 이력이 있다. 그래서 시간이 아니라 **관측된 건강
상태**로 가른다 — 건강하면 종전 그대로 무제한, 응답 없음이 관측됐으면 짧은 상한.

핵심은 **자기 치유**다: 「못 쓴다」로 판정돼도 그 짧은 상한 안에서 계속 시도하므로, 실제로
복구되면 즉시 정상으로 돌아온다. 영구 잠김이 없다.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_aihealth", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    m = _load_runner()
    m.reset_ai_health()
    return m


# ── 1. 건강 상태 판정 자체 ───────────────────────────────────────────────────

def test_starts_healthy(mod):
    """초기값은 «사용 가능» — fail-open.

    「증명될 때까지 불가」로 두면 성공의 근거가 질문 처리뿐이라 첫 질문을 받을 방법이 없다
    (교착). 대신 능력 협상이 질문 **전에** 첫 관측을 준다.
    """
    assert mod.ai_health() == (True, "")


def test_caps_failure_marks_unusable(mod):
    """협상 실패는 「답할 수 없다」의 **질문 전 첫 관측**이다."""
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다 — TimeoutExpired")
    ok, why = mod.ai_health()
    assert ok is False
    assert "응답하지 않습니다" in why


def test_single_failure_does_not_lock_the_account(mod):
    """1회 실패로는 막지 않는다 — 순단·한도는 일시적이고, 오탐 비용이 사용자 차단이다."""
    mod.note_ai_outcome(False, "일시 오류")
    assert mod.ai_health()[0] is True, "한 번의 실패로 러너를 못 쓴다고 판정했다"


def test_consecutive_failures_mark_unusable(mod):
    """연속 실패는 「계속 실패한다」의 근거다."""
    for _ in range(mod._AI_FAIL_STREAK_MAX):
        mod.note_ai_outcome(False, "계속 실패")
    assert mod.ai_health()[0] is False


def test_success_heals_immediately(mod):
    """⭐ 성공 한 번이면 **즉시** 복귀한다 — 영구 잠김이 없다(자기 치유)."""
    mod.note_ai_unusable("응답 없음")
    assert mod.ai_health()[0] is False
    mod.note_ai_outcome(True)
    assert mod.ai_health() == (True, ""), "복구됐는데도 계속 막으면 사용자에게 거짓이다"


# ── 2. 상한 적용 — 아플 때만 ─────────────────────────────────────────────────

def test_healthy_runner_keeps_the_previous_unlimited_contract(mod, monkeypatch, tmp_path):
    """건강한 러너는 **종전 그대로** — 상한 인자를 넘기지 않는다(회귀 0).

    이 단정이 「일하는 AI 를 끊지 않는다」를 지킨다.
    """
    seen = {}
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda *a, **k: (seen.update(k), (True, "ok"))[1])
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)
    assert seen.get("timeout_sec") is None, (
        f"건강한 러너에 상한이 걸렸다({seen.get('timeout_sec')}) — 긴 조사가 끊긴다")


def test_unhealthy_runner_gets_a_finite_cap(mod, monkeypatch, tmp_path):
    """응답 없음이 관측된 러너는 **유한 상한**을 받는다 — 무한 대기가 사라진다."""
    seen = {}
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda *a, **k: (seen.update(k), (True, "ok"))[1])
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.note_ai_unusable("응답 없음")
    mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)

    cap = seen.get("timeout_sec")
    assert cap, "아픈 러너인데 상한이 없다 — 사용자는 영원히 기다린다"
    assert 0 < float(cap) <= 600, f"상한이 사용자 인내 범위를 넘는다: {cap}"


#: 매달리는 자식의 수명. **유한하게** 둔다 — 아래 주석 참조.
_HANG_CHILD_SEC = 25
#: 이 테스트가 적용하는 상한.
_HANG_CAP_SEC = 3.0
#: 「끊었다」로 인정할 상한. 자식 수명보다 충분히 작아야 판별력이 있다.
_HANG_VERDICT_SEC = 12.0


def test_hanging_child_is_killed_and_reported(mod, monkeypatch, tmp_path):
    """⭐ 실제로 매달리는 자식을 **끊고 정직하게 답한다** (라이브 재현).

    `claude.exe` 가 출력 없이 매달리던 그 상황을 자식 프로세스로 재현한다.

    ## 왜 자식 수명이 유한하고, 왜 **경과 시간**을 단정하는가

    초판은 자식을 `sleep(600)` 으로 두고 반환값만 단정했다. 그러면 상한이 사라지는 회귀에서
    이 테스트는 **실패하지 않고 600초 매달린다** — 적대 뮤테이션 스윕이 그 자리에서 죽었고
    (실측), CI 에서도 같은 결과가 된다. **매달리는 테스트는 실패하는 테스트보다 나쁘다**:
    무엇이 깨졌는지 말해 주지 않으면서 파이프라인을 멈춘다.

    그래서 (a) 자식 수명을 유한하게 두어 최악이 «느린 실패»가 되게 하고, (b) 판정을
    **경과 시간**으로 한다 — 상한이 없으면 자식 수명까지 걸리므로 그 사실이 곧 단정 위반이다.
    """
    hang = tmp_path / "hang.py"
    hang.write_text(f"import time; time.sleep({_HANG_CHILD_SEC})", encoding="utf-8")
    monkeypatch.setattr(mod, "_AI_UNHEALTHY_TIMEOUT_SEC", _HANG_CAP_SEC)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.note_ai_unusable("응답 없음")

    t0 = time.monotonic()
    ok, msg = mod.ask_local_ai("custom", [], "질문",
                               f"{sys.executable} {hang}")
    elapsed = time.monotonic() - t0

    assert elapsed < _HANG_VERDICT_SEC, (
        f"상한이 걸리지 않아 {elapsed:.1f}초를 기다렸다(자식 수명 {_HANG_CHILD_SEC}초) — "
        "라이브의 무한 대기가 그대로 돌아왔다")
    assert ok is False
    assert "응답하지 않아 중단" in msg, f"정직한 사유가 아니다: {msg!r}"
    assert "다시 로그인" in msg, f"다음 행동이 없으면 막다른 길이다: {msg!r}"


def test_timeout_notice_differs_by_health(mod):
    """건강한 러너의 상한 초과는 **다른 사실**이다 — 재인증 안내를 붙이지 않는다."""
    healthy = mod._timeout_notice(900, False)
    sick = mod._timeout_notice(150, True)
    assert "다시 로그인" not in healthy, "정상 러너에 엉뚱한 재인증 안내를 붙였다"
    assert "다시 로그인" in sick


# ── 3. 신고 — 서버가 알 수 있는가 ────────────────────────────────────────────

def test_heartbeat_carries_ai_health(mod, monkeypatch):
    """하트비트가 `ai_ready` + 사유를 **항상** 싣는다.

    살아 있음(`listening`)과 **다른 사실**이다 — 러너는 멀쩡히 돌면서 자기 AI 만 죽어 있을
    수 있고, 라이브에서 정확히 그 상태가 사용자를 무한 대기시켰다.
    """
    sent = {}
    api = mod.Api("https://example.invalid", "mat_x", None)
    # ⚠ `heartbeat` 는 `call`(도구 경로)이 아니라 `_post` 로 나간다 — 그 seam 을 잡아야 한다.
    monkeypatch.setattr(api, "_post", lambda path, payload=None, timeout=60.0:
                        (sent.update(payload or {}), {})[1])
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다")
    api.heartbeat([])

    assert sent.get("ai_ready") is False, f"AI 불가가 신고되지 않았다: {sent}"
    assert "응답하지 않습니다" in str(sent.get("ai_unready_reason") or ""), sent


def test_heartbeat_reports_healthy_by_default(mod, monkeypatch):
    """정상 러너는 `ai_ready=True` + 빈 사유 — 서버가 엉뚱하게 막지 않게."""
    sent = {}
    api = mod.Api("https://example.invalid", "mat_x", None)
    monkeypatch.setattr(api, "_post", lambda path, payload=None, timeout=60.0:
                        (sent.update(payload or {}), {})[1])
    api.heartbeat([])
    assert sent.get("ai_ready") is True
    assert sent.get("ai_unready_reason") == ""


# ── 4. 배선 — 판정 함수가 **실제로 불리는가** ────────────────────────────────
#
# ⚠ 아래 두 단정이 없으면 뮤테이션 G3·G8 이 **살아남는다**(실측). 위 §1 은 판정 함수의
#   «계산»만 보므로, 그 함수를 부르는 자리가 사라져도 전부 통과한다 — 이 저장소가 반복해서
#   겪은 「로직은 맞는데 배선이 없다」 부류다. 그래서 **행위**를 잠근다.

def test_caps_failure_actually_marks_the_runner(mod, monkeypatch):
    """협상 실패가 **실제로** 건강 상태를 내린다 (뮤테이션 G3).

    `note_ai_unusable` 이 옳게 계산해도 `caps` 가 그것을 부르지 않으면 러너는 답할 수 없는
    상태로 질문을 계속 집어간다 — 라이브의 무한 대기가 그대로 돌아온다.
    """
    monkeypatch.setattr(mod, "_which_ai",
                        lambda n: "/usr/bin/claude" if n == "claude" else None)
    # 협상이 답하지 않는다 = 라이브의 `TimeoutExpired` 와 같은 결말.
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: None)
    assert mod.ai_health()[0] is True, "전제: 시작은 건강하다"

    mod.detect_runtimes(cached=None, probe=True)

    ok, why = mod.ai_health()
    assert ok is False, "협상이 실패했는데 러너는 여전히 «답할 수 있다» 고 신고한다"
    assert "claude" in why, f"어느 런타임이 응답하지 않는지가 사유에 없다: {why!r}"


def test_successful_call_actually_heals_the_runner(mod, monkeypatch, tmp_path):
    """성공한 AI 호출이 **실제로** 건강 상태를 되돌린다 (뮤테이션 G8).

    이 배선이 없으면 한 번 「못 쓴다」로 판정된 러너가 복구돼도 계속 짧은 상한을 받고,
    사용자는 「이 컴퓨터의 AI 가 응답하지 않습니다」를 영구히 본다 — 거짓 안내다.
    """
    say = tmp_path / "ok.py"
    say.write_text("import sys; sys.stdout.write('답변입니다')", encoding="utf-8")
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.note_ai_unusable("응답 없음")
    assert mod.ai_health()[0] is False, "전제: 아픈 상태로 시작"

    ok, out = mod.ask_local_ai("custom", [], "질문", f"{sys.executable} {say}")

    assert ok and "답변입니다" in out, f"전제: 이 호출은 성공해야 한다 — {out!r}"
    assert mod.ai_health() == (True, ""), (
        "성공했는데 건강 상태가 그대로다 — 복구된 러너를 계속 아프다고 취급한다")
