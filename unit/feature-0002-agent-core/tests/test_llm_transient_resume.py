"""일시 LLM 장애에서 **작업 내역을 보존한 채 추론을 재개**한다
(conv-audit `FR-llm-transient-exhaustion-discards-run`).

재현한 2차 사고(2026-08-12 17:30, 첨부 6건 `20260709_[MV] Log_v2 이슈 대응_*.sql`):
게이트웨이가 배포 스파인 **밖에서** recreate 되어 17:30:05~17:30:53 동안 부재했다.
1차 봉인의 재시도는 정상 발화했지만(`llm_transient_retry attempt=1/2`) 총 대기가
**4.5초**(1.5s+3.0s)뿐이라 **48초+ 공백을 덮지 못했고**, 라운드 1의 **154.2초 추론
(prompt 71,960 tok)** 과 도구 3건이 통째로 폐기됐다. 사용자는 2분 40초를 기다려 오류만 받았다.

두 축으로 봉인한다:
  1. **예산을 실패 비용에 맞춘다** — `attempt_elapsed=0.0s` 로 즉시 거부된 실패는 요청이
     provider 에 도달조차 못 해 재시도 비용이 ~0 이다. 그런 실패에 상한-소진(timeout) 실패와
     같은 예산을 줄 이유가 없다. 값싼 실패는 **인프라 교체 공백을 덮을 만큼** 버틴다.
  2. **소진되면 버리지 않고 재개한다** — 누적 도구 호출·결과는 이미 `core_messages` 에
     영속돼 있고 히스토리 로더가 replay 한다(라이브 실증). job 을 재큐하면 재개 run 이 그
     맥락을 이어받아 처음부터 다시 하지 않는다.

합격선:
  - 값싼 실패의 총 대기 예산이 **실측 공백(48초)을 덮는다**.
  - 비싼(timeout) 실패는 종전 예산 유지 — 사용자를 상한×N 만큼 붙잡지 않는다.
  - 재큐는 self-lease + `attempts < cap` 가드를 갖고, `resume_hint` 를 payload 에 심는다.
  - 재큐 경로는 **KV terminal 을 찍지 않는다**(찍으면 프런트가 종료로 보고 재개 결과를 못 받음).
  - 재큐 예정인 오류는 **core_messages 에 남기지 않는다**(LLM recall 오염 — 라이브 실증).
  - 재개 run 은 "이미 조회한 것 재조회 금지" 지시를 받는다(보존만으로는 재사용되지 않는다).
"""
from __future__ import annotations

import json
import re

import pytest

import agent_core as AC
import modules.ask_jobs as aj
from modules import llm as LLM


_CHEAP = {"kind": LLM.FAILURE_TRANSIENT, "tag": "unavailable", "timeout_class": False}
_EXPENSIVE = {"kind": LLM.FAILURE_TRANSIENT, "tag": "unavailable", "timeout_class": True}
_PERMANENT = {"kind": LLM.FAILURE_PERMANENT, "tag": "auth_invalid", "timeout_class": False}

# 사고 실측: gateway created 17:30:05 → started 17:30:53 (healthy 는 그 이후).
_OBSERVED_GAP_SEC = 48.0


# ══════════════════════════════════════════════════════════════════════
#  1) 값싼 실패 / 비싼 실패의 예산 분리
# ══════════════════════════════════════════════════════════════════════

def test_cheap_classification():
    """요청 미도달(즉시 거부) = 값싸다. 상한 소진 = 비싸다."""
    assert AC._llm_retry_is_cheap(_CHEAP) is True
    assert AC._llm_retry_is_cheap(_EXPENSIVE) is False


def test_cheap_failure_retries_far_beyond_the_old_budget():
    """1차 봉인은 2회에서 멈췄다 — 그것이 이 사고의 직접 원인이다."""
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX > AC.AGENT_LLM_TRANSIENT_RETRY_MAX
    for n in range(1, AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX + 1):
        assert AC._llm_retry_allowed(_CHEAP, n, remaining_budget_sec=1.0,
                                     per_attempt_timeout_sec=300.0,
                                     attempt_elapsed_sec=0.0, waited_total_sec=0.0)
    assert not AC._llm_retry_allowed(_CHEAP, AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX + 1,
                                     remaining_budget_sec=9999.0,
                                     per_attempt_timeout_sec=300.0,
                                     attempt_elapsed_sec=0.0, waited_total_sec=0.0)


def test_cheap_total_wait_covers_the_observed_gateway_gap():
    """**이 테스트가 사고의 핵심 회귀 게이트다.** 값싼 실패의 총 대기 가능 시간이 실측
    교체 공백(48초)을 못 덮으면 같은 사고가 그대로 재발한다."""
    total = 0.0
    for n in range(1, AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX + 1):
        total += AC._llm_retry_backoff_sec(n, cheap=True)
    assert total > _OBSERVED_GAP_SEC, (
        f"값싼 실패 총 대기 {total:.1f}s ≤ 실측 공백 {_OBSERVED_GAP_SEC}s — "
        f"게이트웨이 교체를 못 버틴다(2026-08-12 17:30 사고 재현)"
    )
    # 예산 상한도 같은 공백을 덮어야 한다(횟수만 늘리고 예산으로 잘라내면 무의미).
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_BUDGET_SEC > _OBSERVED_GAP_SEC


def test_cheap_budget_is_bounded():
    """무한정 붙잡지 않는다 — 소진되면 재개 경로로 넘긴다."""
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_BUDGET_SEC <= 600.0
    assert not AC._llm_retry_allowed(
        _CHEAP, 1, remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0,
        attempt_elapsed_sec=0.0,
        waited_total_sec=AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_BUDGET_SEC,
    ), "총 누적 대기 예산을 넘겼는데도 계속 재시도한다"


def test_cheap_backoff_cap_is_higher_than_expensive():
    """값싼 실패는 긴 공백을 버티려면 backoff 상한이 더 커야 한다."""
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX_SEC > AC.AGENT_LLM_TRANSIENT_RETRY_MAX_SEC
    hi = max(AC._llm_retry_backoff_sec(n, cheap=True) for n in range(1, 10))
    lo = max(AC._llm_retry_backoff_sec(n, cheap=False) for n in range(1, 10))
    assert hi > lo


def test_expensive_failure_keeps_the_small_budget():
    """상한 소진 실패는 재시도가 상한만큼 더 태운다 — 예산을 늘리면 사용자 대기가 배로 늘어난다."""
    assert not AC._llm_retry_allowed(
        _EXPENSIVE, AC.AGENT_LLM_TRANSIENT_RETRY_MAX + 1, remaining_budget_sec=9999.0,
        per_attempt_timeout_sec=300.0, attempt_elapsed_sec=300.0, waited_total_sec=0.0)


def test_slow_failure_is_not_treated_as_cheap():
    """`timeout_class=False` 여도 상한의 절반 이상 태우고 죽었으면 값싸지 않다 —
    값싼 경로로 새면 그 비싼 실패를 6회까지 재시도한다."""
    assert not AC._llm_retry_allowed(
        _CHEAP, 1, remaining_budget_sec=10.0, per_attempt_timeout_sec=300.0,
        attempt_elapsed_sec=280.0, waited_total_sec=0.0)


def test_permanent_never_retries_regardless_of_budget():
    assert not AC._llm_retry_allowed(
        _PERMANENT, 1, remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0,
        attempt_elapsed_sec=0.0, waited_total_sec=0.0)


# ══════════════════════════════════════════════════════════════════════
#  2) 재큐 SQL 계약
# ══════════════════════════════════════════════════════════════════════

class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.one_results.pop(0) if self.conn.one_results else None


class _FakeConn:
    def __init__(self, one_results=None):
        self.executed = []
        self.one_results = list(one_results or [])

    def cursor(self):
        return _FakeCursor(self)


def _requeue_sql(one_results):
    c = _FakeConn(one_results=one_results)
    ok = aj.requeue_ask_job_for_resume(c, 42, 7, attempts_cap=3)
    return ok, c.executed[0][0], c.executed[0][1]


def test_requeue_returns_true_when_row_updated():
    ok, _, params = _requeue_sql([(42,)])
    assert ok is True
    assert params["id"] == 42 and params["lease"] == 7 and params["cap"] == 3


def test_requeue_returns_false_when_no_row():
    """lease 박탈 또는 attempts cap → 재큐 안 됨. 호출측이 정상 terminal 로 닫아야 한다."""
    ok, _, _ = _requeue_sql([None])
    assert ok is False


def test_requeue_sql_contract():
    _, sql, _ = _requeue_sql([(42,)])
    norm = " ".join(sql.split())
    # pending 으로 되돌리고 claim 흔적을 지운다.
    assert "status = 'pending'" in norm
    assert "claimed_by = NULL" in norm and "started_at = NULL" in norm
    assert "finished_at = NULL" in norm, "finished_at 잔재는 ops view 를 오독시킨다"
    # fencing + 무한 재큐 방지 + 대상 상태 가드.
    assert "lease_epoch = lease_epoch + 1" in norm
    assert "lease_epoch = %(lease)s" in norm, "self-lease 가드 없이 남의 job 을 되돌린다"
    assert "attempts < %(cap)s" in norm, "cap 가드 없이 무한 재큐된다"
    assert "status = 'running'" in norm
    # 재개 run 이 자기가 재개임을 알 수 있어야 한다.
    assert "resume_hint" in norm
    assert "payload" in norm and "||" in norm, "payload 를 덮어쓰면 원래 run kwargs 가 사라진다"


def test_requeue_does_not_touch_attempts():
    """attempts 는 claim 시점에 증가한다 — 여기서 더하면 cap 을 이중 소모한다."""
    _, sql, _ = _requeue_sql([(42,)])
    assert "attempts = attempts" not in sql and "attempts + 1" not in sql


# ══════════════════════════════════════════════════════════════════════
#  3) 워커 배선 — 순서와 게이트
# ══════════════════════════════════════════════════════════════════════

def _ask_src() -> str:
    import modules.ask as ask_mod
    with open(ask_mod.__file__, "r", encoding="utf-8") as fh:
        return fh.read()


def test_requeue_precedes_terminal_finalize():
    """`_finalize_deferred_terminal` 이 먼저 돌면 KV terminal 이 찍혀 프런트가 종료로 보고
    스피너를 내린다 — 재개 결과가 와도 사용자는 못 받는다(= 여전히 실패)."""
    s = _ask_src()
    requeue = s.index("requeue_ask_job_for_resume(")
    finalize = s.index("_finalize_deferred_terminal(cid, run_id, result)")
    assert requeue < finalize, "재큐 분기가 KV terminal 기록 뒤에 있다"


def test_requeue_drops_deferred_terminal_marker():
    """마커를 남기면 이후 경로가 terminal 을 찍을 수 있다 — 이 run 은 종료가 아니라 인계다."""
    s = _ask_src()
    seg = s[s.index("requeue_ask_job_for_resume("):s.index("if not raised:\n        try:\n            _postprocess_attachment_blocks")]
    assert '_deferred_terminal' in seg and 'pop(' in seg


def test_requeue_branch_returns_without_terminal():
    s = _ask_src()
    seg = s[s.index("requeue_ask_job_for_resume("):]
    seg = seg[:seg.index("if not raised:")]
    assert re.search(r"\n\s+return\s", seg), "재큐 후에도 terminal 경로로 계속 내려간다"


def test_resume_allowed_is_gated_by_attempts_cap():
    """cap 에 닿았으면 run 이 오류 turn 을 남겨 사용자에게 실패를 알려야 한다 —
    '재큐도 못 했는데 아무 것도 안 남는' 창이 생기지 않게 하는 게이트."""
    s = _ask_src()
    seg = s[s.index('kwargs["resume_allowed"]'):]
    seg = seg[:400]
    assert "AGENT_ASK_WORKER_ATTEMPTS_CAP" in seg
    assert "attempts" in seg
    assert "AGENT_ASK_RESUME_ON_TRANSIENT" in seg


# ══════════════════════════════════════════════════════════════════════
#  4) run 측 계약 — 오류 turn 억제 + 재개 지시
# ══════════════════════════════════════════════════════════════════════

def _core_src() -> str:
    with open(AC.__file__, "r", encoding="utf-8") as fh:
        return fh.read()


def test_resume_path_does_not_persist_error_turn_to_core():
    """라이브 실증: 오류 turn 이 `core_messages` 에 남아 **LLM recall 로 replay** 됐다
    (재개 맥락의 마지막 turn = "오류: …"). 재개 run 이 그걸 근거로 삼으면 안 된다."""
    s = _core_src()
    branch = s[s.index('elif result["error"] and resume_allowed and result.get("resumable"):'):]
    branch = branch[:branch.index('elif result["error"]:')]
    assert "_save_message(" not in branch, "재개 경로가 오류 turn 을 core 에 쓴다(recall 오염)"
    assert "set_run_status(" not in branch, "재개 경로가 KV terminal 을 찍는다(프런트 종료)"
    assert "_mirror_message(" in branch, "화면에는 무슨 일인지 남겨야 한다"


def test_normal_error_path_still_persists_and_finalizes():
    """역검증 — 재개 불가 실패는 **종전대로** 오류를 남기고 terminal 을 찍어야 한다."""
    s = _core_src()
    branch = s[s.index('elif result["error"]:'):]
    branch = branch[:branch.index("elif pending_delete") if "elif pending_delete" in branch[:4000] else 4000]
    assert "_save_message(" in branch and "set_run_status(" in branch


def test_resume_hint_instructs_continuation_not_restart():
    """보존만으로는 부족하다 — 지시가 없으면 모델은 같은 조회를 처음부터 다시 한다."""
    s = _core_src()
    assert "if resume_hint:" in s
    seg = s[s.index("if resume_hint:"):]
    seg = seg[:1400]
    low = seg.lower()
    assert "do not repeat" in low or "do not repeat lookups" in low
    assert "from scratch" in low
    assert '"role": "system"' in seg, "이어가기 지시는 system turn 이어야 한다"


def test_resume_hint_is_appended_after_history_and_user_turn():
    """도구 결과와 사용자 질문을 **본 뒤**에 지시를 받아야 효력이 있다."""
    s = _core_src()
    hist = s.index("messages.extend(history)")
    user = s.index('messages.append({"role": "user", "content": _live_user_content})')
    hint = s.index("if resume_hint:")
    assert hist < user < hint


def test_exhaustion_marks_resumable_only_for_transient():
    s = _core_src()
    seg = s[s.index('waited_total_sec=_llm_waited_total):'):]
    seg = seg[:1400]
    assert '_LLM_FAILURE_TRANSIENT' in seg, "permanent 실패까지 재개 대상으로 삼으면 무한 재큐"
    assert 'result["resumable"] = True' in seg


def test_retry_wait_accumulates_for_budget_gate():
    """누적 대기를 세지 않으면 예산 게이트가 무력해진다(횟수만 남는다)."""
    s = _core_src()
    assert "_llm_waited_total += _tick" in s
    assert "waited_total_sec=_llm_waited_total" in s


# ══════════════════════════════════════════════════════════════════════
#  5) 출하 상수 계약 (fixture 로 낮추지 않는다)
# ══════════════════════════════════════════════════════════════════════

def test_shipped_resume_constants():
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX >= 4
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX_SEC >= 15.0
    assert AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_BUDGET_SEC >= 60.0
    from shared import config as cfg
    assert cfg.AGENT_ASK_RESUME_ON_TRANSIENT is True, "출하 기본값이 꺼져 있으면 봉인이 무효"
    assert int(cfg.AGENT_ASK_WORKER_ATTEMPTS_CAP) >= 2, "cap 이 1 이면 재개가 한 번도 못 일어난다"


def test_inline_temp_files_survive_until_requeue_decision():
    """**자기 적발(2026-08-12)** — `_cleanup_inline_paths` 는 "terminal 직전에만" 호출된다는
    전제로 `finally` 에 있었는데, 재개 재큐가 그 전제를 깼다. 지워버리면 재개 run 이 첨부
    인라인 본문을 read-after-delete 로 잃는다(사고 대화는 첨부 6건). resumable 이면 보류하고,
    재큐가 실패해 실제 종료로 내려갈 때 그 자리에서 지워야 한다."""
    s = _ask_src()
    # finally 의 정리는 **resumable 가드 안**에 있어야 한다(무조건 삭제 금지).
    guard = 'if not (isinstance(result, dict) and result.get("resumable")):\n            _cleanup_inline_paths(payload)'
    assert guard in s, "finally 의 임시파일 정리가 resumable 가드 없이 무조건 실행된다"
    # 재큐 실패(정상 종료) 경로에서 보류분이 반드시 정리된다 — 누수 방지.
    # **범위를 except 앞까지로 좁힌다**: 예외 핸들러의 정리가 이 검사를 대신 통과시키면
    # "정상 fall-through 는 누수" 인 뮤턴트가 살아남는다(초판 테스트가 그랬다).
    tail = s[s.index("정상 terminal 경로로 진행."):]
    fallthrough = tail[:tail.index("except Exception as exc:")]
    assert "_cleanup_inline_paths(payload)" in fallthrough, \
        "재큐 실패(정상 fall-through) 시 임시파일이 누수된다"


def test_cleanup_is_not_dropped_on_exception_path():
    """예외 경로에서도 임시파일은 반드시 정리된다(누수 = /shared 잠식)."""
    s = _ask_src()
    seg = s[s.index("except Exception as exc:\n            log.warning(\"ask-worker: 재개 재큐 실패"):]
    seg = seg[:400]
    assert "_cleanup_inline_paths(payload)" in seg


# ══════════════════════════════════════════════════════════════════════
#  6) §18.8 패널 흡수 (P1 3 · P2 2)
# ══════════════════════════════════════════════════════════════════════

_THROTTLED = {"kind": LLM.FAILURE_TRANSIENT, "tag": "throttled", "timeout_class": False}


def test_throttle_is_not_cheap():
    """패널 P1-1 — 429 는 요청이 **도달해서** 거부된 것이다. 값싼 부류로 넣으면 6회 재시도로
    쓰로틀을 증폭한다(가장 하면 안 되는 대응)."""
    assert AC._llm_retry_is_cheap(_THROTTLED) is False
    # 값싼 예산(6회)이 아니라 종전 짧은 예산(2회)을 써야 한다.
    assert not AC._llm_retry_allowed(
        _THROTTLED, AC.AGENT_LLM_TRANSIENT_RETRY_MAX + 1, remaining_budget_sec=9999.0,
        per_attempt_timeout_sec=300.0, attempt_elapsed_sec=0.0, waited_total_sec=0.0)
    # 전송층(unavailable)은 여전히 값싸다 — 과교정 방지 역검증.
    assert AC._llm_retry_is_cheap(_CHEAP) is True


def test_cheap_budget_includes_the_next_backoff():
    """패널 P2-2 — 이미 쓴 대기만 비교하면 다음 대기가 예산을 넘겨도 통과한다
    (예산 10s 에서 10.5s 까지 대기). 문서가 선언한 절대 상한과 동작을 일치시킨다."""
    budget = AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_BUDGET_SEC
    nxt = AC._llm_retry_backoff_sec(1, cheap=True)
    # "예산 - 다음대기" 보다 조금 더 쓴 상태면 더 이상 재시도하지 않아야 한다.
    assert not AC._llm_retry_allowed(
        _CHEAP, 1, remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0,
        attempt_elapsed_sec=0.0, waited_total_sec=budget - nxt + 0.01)
    # 여유가 있으면 통과 — 게이트가 과도하게 좁혀지지 않았는지 역검증.
    assert AC._llm_retry_allowed(
        _CHEAP, 1, remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0,
        attempt_elapsed_sec=0.0, waited_total_sec=0.0)


def test_cancel_during_final_attempt_is_not_resumed():
    """패널 P1-2 — 사용자가 취소했는데 워커가 재큐해 계속 진행하면 취소가 무의미해진다.
    resumable 을 세우기 **전에** 취소를 보고, 취소면 그 경로로 넘겨야 한다."""
    s = _core_src()
    seg = s[s.index('waited_total_sec=_llm_waited_total):'):]
    seg = seg[:seg.index('result["resumable"] = True')]
    assert "_cancel_requested_for_run(mem_conn, cid, run_id)" in seg, \
        "취소 확인 없이 재개 대상으로 표시한다"
    assert "canceled_by_user = True" in seg


def test_resumable_is_gated_by_resume_allowed():
    """패널 P2-1 — 재큐가 일어나지 않을 상황(토글 off·cap 도달)에서 resumable 을 세우면
    하류(임시파일 정리·terminal 기록)가 '재개될 것'으로 오판한다."""
    s = _core_src()
    idx = s.index('result["resumable"] = True')
    line_start = s.rindex("if ", 0, idx)
    guard = s[line_start:idx]
    assert "resume_allowed" in guard, "resume_allowed 게이팅 없이 resumable 을 세운다"


def test_requeue_giveup_writes_kv_terminal():
    """패널 P1-3 — resume 경로 run 은 KV terminal 을 찍지 않고 지연 마커도 만들지 않는다.
    재큐가 실패/no-op 이면 `last_status` 가 processing 에 고착돼 프런트가 무한 '처리 중' 이 된다."""
    s = _ask_src()
    assert "def _resume_giveup_finalize(" in s
    fn = s[s.index("def _resume_giveup_finalize("):]
    fn = fn[:fn.index("def _reap_orphan_inline_files")]
    assert "set_run_status(" in fn
    assert "only_if_current_run=True" in fn, \
        "lease 박탈 시 새 소유자의 상태를 덮어쓴다"
    # no-op 경로와 예외 경로 **둘 다** 호출해야 한다.
    tail = s[s.index("정상 terminal 경로로 진행."):]
    tail = tail[:tail.index("if not raised:")]
    assert tail.count("_resume_giveup_finalize(") == 2, \
        "재큐 no-op / 예외 두 경로 중 한쪽이 KV 를 고착 상태로 남긴다"
