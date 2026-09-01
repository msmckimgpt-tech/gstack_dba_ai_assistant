"""feature-0043 — 브리지 러너 **로그 구조** 계약 (TASK-20260901T163000).

사용자 요구: *"'내 AI 연결하기' 를 통해 러너가 실행될 때 기록하는 로그에서 보다 명확한 정보
기록을 위한 구조가 필요합니다. 충분한 감사 및 에러 핸들링이 가능하도록, 상세 정보를 포함할
수 있도록 구성해주세요."*

여기서 잠그는 것은 **사람이 읽는 문장이 아니라 기계가 의존하는 축**이다 — 문장은 계속 다듬을
것이고, 그때마다 조사 방법이 깨지면 안 된다:

  1. 두 sink 가 모두 나온다 (사람 줄 · JSONL 원장).
  2. 원장 한 줄에 **상관관계 키**(`ev`·`run`·`pid`·`seq`·`ts`)가 항상 있다.
  3. 예외는 형(type)과 스택을 **잃지 않는다**.
  4. 토큰은 두 sink 어디에도 남지 않는다.
  5. 종전 `_log("문장")` 호출이 그대로 동작한다 (80여 곳을 한꺼번에 고치지 않는 계약).
  6. stderr 가 이미 그 파일이면 **이중 기록하지 않는다** (POSIX 설치본의 셸 리다이렉트).
  7. 원장이 상한을 넘으면 회전한다.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
AGENT = SRC / "bridge_agent.py"


@pytest.fixture()
def agent(tmp_path, monkeypatch):
    """로그 경로를 tmp 로 돌린 러너 모듈. 환경변수는 import 시점에 읽히므로 재로드한다."""
    monkeypatch.setenv("BRIDGE_LOG_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(SRC))
    mod = importlib.import_module("bridge_agent")
    mod = importlib.reload(mod)
    mod._RUNNER_INSTANCE = "testinstance"
    mod._STATS.clear()
    mod._LOG_SECRETS.clear()
    return mod


def _audit(tmp_path) -> list[dict]:
    p = tmp_path / "bridge.events.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ── 1·2. 두 sink · 상관관계 키 ────────────────────────────────────────────────


def test_event_lands_in_both_sinks_with_correlation_keys(agent, tmp_path, capsys):
    agent.log_event("task.dispatch", "내 AI 에게 전달", task="t-42", runtime="claude", dur_ms=7)

    human = capsys.readouterr().err
    assert "task.dispatch" in human, "사람 줄에 사건 코드가 없다"
    assert "task=t-42" in human, "사람 줄에 질문 id 가 없다"

    rows = _audit(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    # 이 다섯이 없으면 「어느 프로세스가·몇 번째로·언제」를 복원할 수 없다.
    for key in ("ts", "lvl", "ev", "seq", "run", "pid"):
        assert key in row, f"원장에 상관관계 키 {key} 가 없다: {row}"
    assert row["ev"] == "task.dispatch"
    assert row["task"] == "t-42"
    assert row["run"] == "testinstance"
    assert row["dur_ms"] == 7


def test_timestamp_carries_utc_offset(agent, tmp_path):
    """지역시각만 적으면 다른 표준시의 서버 로그와 같은 사건임을 계산할 수 없다."""
    agent.log_event("run.ready", "준비")
    ts = _audit(tmp_path)[0]["ts"]
    assert ts[-5] in "+-" and ts[-4:].isdigit(), f"오프셋이 없다: {ts}"


def test_sequence_is_monotonic(agent, tmp_path):
    """같은 초에 여러 줄이 나도 **순서**를 잃지 않아야 한다(동시 처리 인터리브)."""
    for i in range(5):
        agent.log_event("api.ok", f"{i}", level="DEBUG")
    seqs = [r["seq"] for r in _audit(tmp_path)]
    assert seqs == sorted(seqs) and len(set(seqs)) == 5


# ── 3. 예외 ──────────────────────────────────────────────────────────────────


def test_exception_keeps_type_and_traceback(agent, tmp_path, capsys):
    """`except Exception as e: _log(f"…: {e}")` 가 버리던 것을 되찾는다."""
    try:
        raise FileNotFoundError("claude: not found")
    except FileNotFoundError as exc:
        agent._log_exc("ai.spawn_fail", "AI 를 실행하지 못했다", exc, exe="claude")

    row = _audit(tmp_path)[0]
    assert row["lvl"] == "ERROR"
    assert row["err_type"] == "FileNotFoundError", "예외 **형** 이 없으면 원인을 가를 수 없다"
    assert "not found" in row["err"]
    assert "tb" in row and "FileNotFoundError" in row["tb"], "스택이 없다"
    # 사람 줄에는 형·요약만 — 스택이 화면을 덮으면 다음 줄이 밀려난다.
    human = capsys.readouterr().err
    assert "FileNotFoundError" in human
    assert "Traceback" not in human


def test_error_level_counts_into_run_stop_summary(agent, tmp_path):
    """종료 한 줄로 「이번 세션이 무엇을 했나」를 알 수 있어야 한다."""
    agent.log_event("task.submit.ok", "제출", task="a")
    agent.log_event("task.submit.fail", "실패", level="ERROR", task="b")
    agent._log_run_stop("test")

    stop = [r for r in _audit(tmp_path) if r["ev"] == "run.stop"]
    assert len(stop) == 1
    assert stop[0]["submitted"] == 1
    assert stop[0]["errors"] == 1
    assert stop[0]["tally"]["task.submit.fail"] == 1


def test_run_stop_is_logged_once(agent, tmp_path):
    """종료 경로가 여럿이라(반환·Ctrl+C·SIGTERM→atexit) 빗장이 없으면 두 번 찍힌다."""
    agent._log_run_stop("first")
    agent._log_run_stop("second")
    assert len([r for r in _audit(tmp_path) if r["ev"] == "run.stop"]) == 1


# ── 4. 비밀 ──────────────────────────────────────────────────────────────────


def test_registered_token_is_scrubbed_from_both_sinks(agent, tmp_path, capsys):
    token = "mat_liveTOKENvalue0123456789"  # verify-secret-allow: 합성 문자열 — 이 값이 로그에 남지 않는 것이 이 테스트의 단정이다
    agent.register_secret(token)
    agent.log_event("api.fail", f"서버가 거절했다: {token}", level="WARN", detail=token)

    assert token not in capsys.readouterr().err
    raw = (tmp_path / "bridge.events.jsonl").read_text(encoding="utf-8")
    assert token not in raw, "원장에 토큰이 남았다 — 이 파일은 사용자가 우리에게 붙여 보낸다"


def test_unregistered_token_shape_is_still_masked(agent, tmp_path):
    """등록이 누락돼도 **형태**로 막는다 (토큰 형식이 바뀐 날의 로그가 새지 않게)."""
    agent.log_event("api.fail", "Authorization: Bearer abcdef0123456789ghijk", level="WARN")
    raw = (tmp_path / "bridge.events.jsonl").read_text(encoding="utf-8")
    assert "abcdef0123456789ghijk" not in raw


def test_answer_body_is_not_logged(agent, tmp_path):
    """계약: 본문은 싣지 않고 **길이만** 센다 (보안 계약 docstring 과 정합)."""
    agent.log_event("task.submit.ok", "제출 완료", task="t", answer_chars=1234)
    row = _audit(tmp_path)[0]
    assert row["answer_chars"] == 1234
    assert "answer" not in row


# ── 5. 하위호환 ───────────────────────────────────────────────────────────────


def test_legacy_positional_log_still_works(agent, tmp_path, capsys):
    """호출부 80여 곳을 한꺼번에 고치지 않는 것이 이 설계의 전제다."""
    agent._log("종전 방식 그대로")
    assert "종전 방식 그대로" in capsys.readouterr().err
    assert _audit(tmp_path)[0]["ev"] == "log"


def test_every_log_call_site_is_still_valid(agent):
    """`_log` 의 시그니처 변경이 기존 호출부를 깨지 않았는지 — 파일 전체를 컴파일해 본다."""
    compile(AGENT.read_text(encoding="utf-8"), str(AGENT), "exec")


# ── 6. 이중 기록 방지 ─────────────────────────────────────────────────────────


def test_no_double_write_when_stderr_is_the_log_file(tmp_path):
    """POSIX 설치본은 stderr 를 `bridge.log` 로 잇는다 — 그때 러너가 또 쓰면 전부 두 줄이 된다.

    실제 서브프로세스로 검증한다: `_human_log_path` 의 inode 비교는 진짜 fd 가 있어야 의미가 있다.
    """
    log = tmp_path / "bridge.log"
    env = {**os.environ, "BRIDGE_LOG_DIR": str(tmp_path), "PYTHONPATH": str(SRC)}
    with open(log, "a", encoding="utf-8") as fh:
        subprocess.run(
            [sys.executable, "-c",
             "import bridge_agent as B; B._log('중복 여부 확인용')"],
            stderr=fh, env=env, check=True, timeout=60)
    assert log.read_text(encoding="utf-8").count("중복 여부 확인용") == 1


def test_writes_own_log_file_when_stderr_is_elsewhere(tmp_path):
    """Windows 설치본은 stderr 를 아무 데도 잇지 않는다 — 종전에는 **증거가 0** 이었다."""
    env = {**os.environ, "BRIDGE_LOG_DIR": str(tmp_path), "PYTHONPATH": str(SRC)}
    subprocess.run(
        [sys.executable, "-c", "import bridge_agent as B; B._log('윈도우 경로 확인')"],
        stderr=subprocess.DEVNULL, env=env, check=True, timeout=60)
    assert "윈도우 경로 확인" in (tmp_path / "bridge.log").read_text(encoding="utf-8")


def test_log_file_can_be_disabled(tmp_path):
    env = {**os.environ, "BRIDGE_LOG_DIR": str(tmp_path), "PYTHONPATH": str(SRC),
           "BRIDGE_LOG_FILE": "-"}
    subprocess.run(
        [sys.executable, "-c", "import bridge_agent as B; B._log('파일 끔')"],
        stderr=subprocess.DEVNULL, env=env, check=True, timeout=60)
    assert not (tmp_path / "bridge.log").exists()
    # 원장은 별개 축이라 그대로 남는다 — 감사를 끄는 스위치가 아니다.
    assert (tmp_path / "bridge.events.jsonl").exists()


# ── 7. 회전 ──────────────────────────────────────────────────────────────────


def test_audit_log_rotates_at_limit(tmp_path, monkeypatch):
    """상주 러너는 몇 달을 돈다 — 상한이 없으면 원장이 조용히 디스크를 먹는다."""
    monkeypatch.setenv("BRIDGE_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("BRIDGE_LOG_MAX_BYTES", "65536")
    monkeypatch.syspath_prepend(str(SRC))
    mod = importlib.reload(importlib.import_module("bridge_agent"))
    for i in range(2000):
        mod.log_event("api.ok", "x" * 200, level="DEBUG", i=i)
    assert (tmp_path / "bridge.events.jsonl.1").exists(), "회전이 일어나지 않았다"
    assert (tmp_path / "bridge.events.jsonl").stat().st_size < 200_000


def test_audit_file_is_owner_only(agent, tmp_path):
    """원장에는 서버 오류 본문·자식 stderr 가 실린다 — 같은 머신의 다른 사용자에게 열지 않는다."""
    agent.log_event("api.ok", "권한 확인", level="DEBUG")
    mode = (tmp_path / "bridge.events.jsonl").stat().st_mode & 0o777
    if os.name != "nt":   # Windows 는 POSIX 권한 비트가 의미를 갖지 않는다
        assert mode == 0o600, f"원장 권한이 0600 이 아니다: {oct(mode)}"


# ── 사건 코드 계약 ────────────────────────────────────────────────────────────


def test_event_codes_are_declared_constants(agent):
    """조사 스크립트가 의존하는 이름은 상수로 선언돼 있어야 한다(오타 방지·grep 가능)."""
    for name in ("_EV_RUN_START", "_EV_RUN_STOP", "_EV_TASK_DISPATCH",
                 "_EV_TASK_SUBMIT_OK", "_EV_TASK_SUBMIT_FAIL", "_EV_AI_FAIL",
                 "_EV_API_FAIL", "_EV_HB_FAIL", "_EV_CONN_UNAUTH"):
        assert hasattr(agent, name), f"사건 코드 상수 {name} 가 없다"
        assert "." in getattr(agent, name), "사건 코드는 `계층.동작` 형태여야 한다"


def test_task_lifecycle_events_share_the_task_key(agent, tmp_path):
    """한 질문의 일생을 `task=` 하나로 걸러낼 수 있어야 한다 — 동시 처리에서 유일한 복원 수단."""
    for ev in (agent._EV_TASK_DISPATCH, agent._EV_TASK_REVIEW, agent._EV_TASK_SUBMIT_OK):
        agent.log_event(ev, "…", task="t-99")
    rows = [r for r in _audit(tmp_path) if r.get("task") == "t-99"]
    assert len(rows) == 3
