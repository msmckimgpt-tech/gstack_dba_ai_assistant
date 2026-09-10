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

def test_starts_unknown_not_healthy(mod):
    """⭐ 초기값은 «아직 확인되지 않음»(`None`) — **«정상»이 아니다**.

    종전 초기값은 `True`(fail-open) 였고, 그 값이 그대로 하트비트에 실려 화면에
    「대기 중」(정상)으로 나갔다. 그래서 러너 기동 직후 AI 가 실은 응답 불가여도 사용자는
    협상이 끝날 때까지(실측 ~200초) 그 사실을 듣지 못했다.

    사용자 지적(2026-09-03): *"연결되지 않은 상황이 정상 연결되었다고 거짓으로 출력되는
    부분을 수정하는 작업입니다."*
    """
    assert mod.ai_health() == (None, ""), "기동 직후를 «정상»으로 신고하면 그것이 거짓이다"


def test_unknown_does_not_block_questions(mod):
    """⚠ 그러나 「모른다」가 **질문을 막지는 않는다** — 게이트와 표시는 다른 축이다.

    `None` 을 `False` 로 접으면 성공의 근거가 질문 처리뿐이라 첫 질문이 전부 죽는다(교착).
    표시 축만 정직해지고 게이트 축은 종전 fail-open 을 유지해야 한다.
    """
    assert mod.ai_health()[0] is None, "전제: 아직 확인되지 않은 상태"
    assert mod.ai_blocked() == (False, ""), "「모른다」가 질문을 막으면 첫 질문이 전부 죽는다"


def test_caps_failure_marks_unusable(mod):
    """협상 실패는 「답할 수 없다」의 **질문 전 첫 관측**이다."""
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다 — TimeoutExpired")
    ok, why = mod.ai_health()
    assert ok is False
    assert "응답하지 않습니다" in why


def test_single_failure_does_not_lock_the_account(mod):
    """1회 실패로는 막지 않는다 — 순단·한도는 일시적이고, 오탐 비용이 사용자 차단이다.

    ⚠ 판정은 **게이트 축**(`ai_blocked`)으로 본다. 표시 축(`ai_health`)은 3상태라 여기서
      `True` 를 요구하면 「아직 확인되지 않음」을 「정상」으로 요구하는 셈이 되고, 그것이
      바로 이 cycle 이 없앤 거짓이다.
    """
    mod.note_ai_outcome(False, "일시 오류")
    assert mod.ai_blocked()[0] is False, "한 번의 실패로 러너를 못 쓴다고 판정했다"


def test_consecutive_failures_mark_unusable(mod):
    """연속 실패는 「계속 실패한다」의 근거다."""
    for _ in range(mod._AI_FAIL_STREAK_MAX):
        mod.note_ai_outcome(False, "계속 실패")
    assert mod.ai_health()[0] is False


def test_success_heals_immediately(mod):
    """⭐ 성공 한 번이면 **즉시** 복귀한다 — 영구 잠김이 없다(자기 치유)."""
    mod.note_ai_unusable("응답 없음", runtime="claude")
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


def test_unhealthy_runner_answers_immediately_without_calling_the_ai(
        mod, monkeypatch, tmp_path):
    """⭐ 아픈 러너는 **AI 를 부르지 않고 즉시** 답한다 (사용자 지적 2026-09-03).

    > 「사용자 입장에서, 150는 너무 깁니다. (사실, 10초 이상 소요되는 부분도 길다고
    >  체감됩니다.)」

    직전 계약(150초 상한)은 **이미 못 쓴다는 것을 아는 상태에서** 더 기다리게 했다. 그 시간은
    사용자를 위한 것이 아니라 회복 확인이라는 우리 편의였다.
    """
    spawned = []
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda *a, **k: spawned.append(a) or (True, "안 불려야 한다"))
    monkeypatch.setattr(mod, "schedule_health_recheck", lambda *a, **k: True)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다", runtime="claude")

    t0 = time.monotonic()
    ok, msg = mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)
    elapsed = time.monotonic() - t0

    assert spawned == [], "아픈 러너인데 AI 를 호출했다 — 사용자가 그만큼 기다린다"
    assert ok is False
    assert elapsed < 1.0, f"즉시 답하지 않았다({elapsed:.2f}초)"
    assert "응답하지 않습니다" in msg and "다시 로그인" in msg, msg[:200]


def test_fast_fail_schedules_background_recovery(mod, monkeypatch, tmp_path):
    """즉시 실패하면서 **회복 확인을 배경으로** 건다 — 영구 잠김 방지.

    이 배선이 없으면 「즉시 답한다」가 「영원히 아프다」가 된다.
    """
    called = []
    monkeypatch.setattr(mod, "schedule_health_recheck",
                        lambda *a, **k: called.append(a) or True)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    mod.note_ai_unusable("응답 없음", runtime="claude")
    mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)
    assert called, "회복 확인을 걸지 않았다 — 복구돼도 영원히 막힌다"


def test_recovery_recheck_runs_in_background_and_heals(mod, monkeypatch):
    """배경 확인이 성공하면 **다음 질문**부터 정상 경로다."""
    mod.reset_health_recheck()
    monkeypatch.setattr(mod, "_which_ai",
                        lambda n: "/usr/bin/claude" if n == "claude" else None)
    monkeypatch.setattr(mod, "_ask_json", lambda *a, **k: {
        "label": "Claude", "models": [{"value": "opus", "label": "Opus"}],
        "model_flag": ["--model", "{model}"], "efforts": [], "effort_flag": []})
    mod.note_ai_unusable("응답 없음", runtime="claude")
    assert mod.schedule_health_recheck("claude") is True

    for _ in range(200):                     # 배경 스레드가 끝날 때까지
        if mod.ai_health()[0]:
            break
        time.sleep(0.05)
    assert mod.ai_health()[0] is True, "회복했는데 건강 상태가 돌아오지 않았다"


def test_recovery_recheck_has_a_cooldown(mod, monkeypatch):
    """회복 확인은 **AI 를 호출한다** — 매 질문마다 하면 남의 계정 쿼터를 우리가 태운다."""
    mod.reset_health_recheck()
    monkeypatch.setattr(mod, "_which_ai", lambda n: None)   # 실제 질의는 안 일어난다
    assert mod.schedule_health_recheck(None) is True
    assert mod.schedule_health_recheck(None) is False, "쿨다운 없이 연달아 확인한다"


def test_healthy_runner_never_fast_fails(mod, monkeypatch, tmp_path):
    """건강한 러너는 이 경로를 **타지 않는다** — 정상 질문이 안내문으로 바뀌면 안 된다."""
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda *a, **k: (True, "실제 답변"))
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    ok, out = mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)
    assert ok and out == "실제 답변", f"건강한 러너의 답이 바뀌었다: {out!r}"


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
    mod.note_ai_unusable("이 컴퓨터의 claude 가 응답하지 않습니다", runtime="claude")
    api.heartbeat([])

    assert sent.get("ai_ready") is False, f"AI 불가가 신고되지 않았다: {sent}"
    assert "응답하지 않습니다" in str(sent.get("ai_unready_reason") or ""), sent


def _heartbeat_payload(mod, monkeypatch) -> dict:
    sent: dict = {}
    api = mod.Api("https://example.invalid", "mat_x", None)
    monkeypatch.setattr(api, "_post", lambda path, payload=None, timeout=60.0:
                        (sent.update(payload or {}), {})[1])
    api.heartbeat([])
    return sent


def test_heartbeat_reports_unknown_before_verification(mod, monkeypatch):
    """⭐ 확인 전 하트비트는 `ai_ready=None` — **`True` 를 보내지 않는다**.

    이 한 줄이 사용자가 본 거짓의 발원지였다: `body["ai_ready"] = bool(_ai_ok)` 가
    초기값 `True` 를 그대로 실어 보냈고, 서버는 그것을 `RunnerAiReady=1` 로 새겼고,
    화면은 「대기 중」을 띄웠다.
    """
    sent = _heartbeat_payload(mod, monkeypatch)
    assert "ai_ready" in sent, "키 자체가 없으면 서버가 «구 러너»로 읽어 직전 값을 남긴다"
    assert sent["ai_ready"] is None, "확인 전인데 «정상»을 신고했다 — 화면의 거짓이 된다"
    assert sent.get("ai_unready_reason") == ""


def test_heartbeat_reports_healthy_after_success(mod, monkeypatch):
    """확인이 성공하면 `ai_ready=True` — 서버가 엉뚱하게 막지 않게."""
    mod.note_ai_outcome(True)
    sent = _heartbeat_payload(mod, monkeypatch)
    assert sent.get("ai_ready") is True
    assert sent.get("ai_unready_reason") == ""


def test_heartbeat_does_not_squash_unknown_into_false(mod, monkeypatch):
    """⚠ `None` 을 `False` 로 눌러 보내면 정상 러너가 「답할 수 없음」으로 보인다."""
    sent = _heartbeat_payload(mod, monkeypatch)
    assert sent["ai_ready"] is not False, "「모른다」를 «못 쓴다»로 신고했다"


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
    assert mod.ai_health()[0] is None, "전제: 시작은 «아직 확인되지 않음»"

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
    mod.note_ai_unusable("응답 없음", runtime="claude")
    assert mod.ai_health()[0] is False, "전제: 아픈 상태로 시작"

    # ⚠ `ask_local_ai` 가 아니라 **실행 계층**을 직접 부른다 (TASK-20260903T160000).
    #   아픈 러너의 `ask_local_ai` 는 이제 AI 를 부르지 않고 즉시 안내한다(사용자를
    #   기다리게 하지 않기 위해) — 그래서 「성공이 건강을 되돌린다」는 계약은 실제로
    #   호출이 일어나는 이 자리에서 잠근다. 회복의 **트리거**는 배경 재확인이 맡고,
    #   그쪽은 `test_recovery_recheck_runs_in_background_and_heals` 가 본다.
    ok, out = mod._run_cli_cancelable([sys.executable, str(say)], lambda: False)

    assert ok and "답변입니다" in out, f"전제: 이 호출은 성공해야 한다 — {out!r}"
    assert mod.ai_health() == (True, ""), (
        "성공했는데 건강 상태가 그대로다 — 복구된 러너를 계속 아프다고 취급한다")
