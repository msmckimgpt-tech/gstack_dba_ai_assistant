"""대화 경로 LLM 일시 실패 재시도 + 히스토리 창 교정
(conv-audit `FR-llm-transient-failure-kills-run` / `FR-agent-history-window-inverted`).

재현한 사고(2026-08-12, 폴더 `쿼리 리뷰 > gz > dev-MasangCreators`): 사용자가 2개 DB 리뷰를
요청해 LLM 5라운드·도구 10회로 스키마와 루틴을 다 조사한 뒤, 6라운드 진행 중 **우리 배포가
게이트웨이를 recreate** 하면서 in-flight 호출이 SIGKILL 됐다. 앱은 그 예외로 run 을 즉시 종결
했고 사용자는 7분 40초를 기다린 끝에 `오류: LLM 호출 오류: Connection error.` 원문만 받았다.
새 게이트웨이는 실패 **1.2초 뒤** 정상이었으므로 한 번의 재호출로 전부 살릴 수 있었다.

합격선:
  1. 일시(transient) 실패는 **같은 라운드 재호출**로 흡수한다 — 누적 messages 는 손대지 않는다.
  2. 사람이 설정을 고쳐야 풀리는 실패(자격증명·인증·모델 라우팅·컨텍스트 초과)는 재시도하지
     않는다 — 사용자를 backoff 만큼 더 붙잡아 두고 결과가 같기 때문.
  3. 타임아웃 계열 재시도는 run 예산에 per-attempt 상한만큼 남았을 때만 한다(연결 절단 계열은
     요청이 도달조차 못 했으므로 무조건 허용).
  4. 전송층 예외 2종이 사용자 친화 메시지로 치환되되 **글로벌 provider 배너는 켜지 않는다**.
  5. 히스토리 로드는 **최신** N행을 집는다(구 PG 경로는 가장 오래된 N행을 집어 긴 대화의 최근
     맥락이 통째로 사라졌다 — 라이브 281행 대화에서 최신 81행 유실 실측).
  6. **출하 상수 계약** — 아래 상수는 fixture 로 낮추지 않고 출하 값을 직접 검증한다. 대기
     상수를 테스트가 조용히 갈아끼우면 "상수를 사고 당시 값으로 되돌리는 뮤턴트"가 전 스위트를
     통과한다(이 저장소의 `test-env-override-skip-vacuous-pass` 선례).
"""
import re

import pytest

import agent_core as AC
from modules import llm as LLM
from modules import llm_provider_health as HEALTH
from modules import runtime_backend as RB


# ── 예외 더블 — OpenAI SDK 의 전송층 예외 2종 형태를 그대로 흉내 낸다 ──────────────
class _APIConnectionError(Exception):
    """openai.APIConnectionError 는 status 를 싣지 않고 기본 메시지가 'Connection error.' 다."""
    def __init__(self):
        super().__init__("Connection error.")


class _APITimeoutError(Exception):
    def __init__(self):
        super().__init__("Request timed out.")


class _StatusError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status_code = status


# ══════════════════════════════════════════════════════════════════════
#  1) 실패 분류 — transient vs permanent, timeout_class
# ══════════════════════════════════════════════════════════════════════

def test_connection_error_is_transient_and_not_timeout_class():
    """사고를 낸 그 예외. 재시도 가치가 가장 높고, 요청이 도달조차 못 했으므로 비용 게이트 없음."""
    info = LLM.classify_agent_llm_failure(_APIConnectionError())
    assert info["kind"] == LLM.FAILURE_TRANSIENT
    assert info["timeout_class"] is False


def test_timeout_is_transient_but_marked_timeout_class():
    info = LLM.classify_agent_llm_failure(_APITimeoutError())
    assert info["kind"] == LLM.FAILURE_TRANSIENT
    assert info["timeout_class"] is True, "재시도가 상한만큼 더 태울 수 있음을 호출측에 알려야 한다"


def test_unclassifiable_network_exception_is_transient():
    """provider 어휘에 없는 드라이버/소켓 예외 — 분류 불가지만 재시도 가치는 가장 높다."""
    info = LLM.classify_agent_llm_failure(OSError("[Errno 104] Connection reset by peer"))
    assert info["kind"] == LLM.FAILURE_TRANSIENT


@pytest.mark.parametrize(
    "exc",
    [
        _StatusError(400, "/chat/completions: Invalid model name passed in model=auto."),
        _StatusError(400, "prompt is too long: 250000 tokens > 200000 maximum"),
        _StatusError(401, "AuthenticationError: invalid api key"),
        _StatusError(403, "AccessDeniedException"),
    ],
    ids=["bad_model", "context_length", "auth", "forbidden"],
)
def test_setting_errors_are_permanent(exc):
    """사람이 고쳐야 풀리는 실패는 재시도하지 않는다 — 대기만 늘리고 결과가 같다."""
    assert LLM.classify_agent_llm_failure(exc)["kind"] == LLM.FAILURE_PERMANENT


def test_throttle_stays_transient():
    """쓰로틀은 backoff 후 풀릴 수 있으므로 transient 유지(상한이 비용을 유계로 만든다)."""
    assert LLM.classify_agent_llm_failure(
        _StatusError(429, "Too many requests")
    )["kind"] == LLM.FAILURE_TRANSIENT


def test_agent_permanent_set_is_stricter_than_node_analysis():
    """전경(대화)과 배경(노드 분석)의 permanent 집합이 다른 것은 의도다 — 같아지면 회귀."""
    assert LLM._NODE_ANALYSIS_PERMANENT_KINDS < LLM._AGENT_LLM_PERMANENT_KINDS
    assert {"auth_invalid", "credential_expired"} <= LLM._AGENT_LLM_PERMANENT_KINDS


# ══════════════════════════════════════════════════════════════════════
#  2) 사용자 표면 — 전송층 예외의 메시지 치환 + 글로벌 배너 비오염
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("exc", [_APIConnectionError(), _APITimeoutError()],
                         ids=["connection", "timeout"])
def test_transport_errors_get_korean_message_not_raw_sdk_string(exc):
    """사고 당시 화면에 뜬 것은 SDK 원문이었다 — 분류가 None 으로 떨어졌기 때문."""
    r = HEALTH.classify_llm_provider_error(exc, provider="openai")
    assert r is not None, "분류되지 않으면 caller 가 raw 예외 문자열을 그대로 노출한다"
    assert r["retryable"] is True
    assert "Connection error" not in r["message"] and "timed out" not in r["message"]
    assert "다시 시도" in r["message"]


@pytest.mark.parametrize("exc", [_APIConnectionError(), _APITimeoutError()],
                         ids=["connection", "timeout"])
def test_transport_errors_do_not_light_global_banner(exc, monkeypatch):
    """단발 순단이 전 사용자에게 보이는 sticky 배너를 켜면 안 된다(confirmed 게이트).

    `_TAG_PAT` 에 APIConnectionError/APITimeoutError 를 넣는 '개선'이 바로 이 계약을 깬다 —
    그 뮤턴트를 잡기 위해 분류 플래그가 아니라 **영속 호출 여부**를 직접 관측한다."""
    r = HEALTH.classify_llm_provider_error(exc, provider="openai")
    assert r["confirmed"] is False

    calls: list[tuple] = []
    monkeypatch.setattr(HEALTH, "record_provider_state",
                        lambda *a, **kw: calls.append((a, kw)))
    HEALTH.record_provider_restricted(r, source="test")
    assert calls == [], "일시 전송 실패가 글로벌 provider health 를 restricted 로 오염시켰다"


def test_confirmed_provider_error_still_lights_banner(monkeypatch):
    """역검증 — confirmed 신호(자격증명 만료)는 종전대로 배너를 켜야 한다(과교정 방지)."""
    r = HEALTH.classify_llm_provider_error(
        _StatusError(403, "ExpiredTokenException: The security token included in the request is expired")
    )
    assert r["confirmed"] is True
    calls: list[tuple] = []
    monkeypatch.setattr(HEALTH, "record_provider_state",
                        lambda *a, **kw: calls.append((a, kw)))
    HEALTH.record_provider_restricted(r, source="test")
    assert len(calls) == 1


def test_transport_pattern_does_not_steal_auth_or_throttle():
    """전송층 매칭이 401/403/429/400 버킷을 훔치면 배너·안내가 통째로 오분류된다."""
    assert HEALTH.classify_llm_provider_error(
        _StatusError(401, "AuthenticationError")
    )["kind"] == HEALTH.KIND_AUTH_INVALID
    assert HEALTH.classify_llm_provider_error(
        _StatusError(429, "rate limit exceeded")
    )["kind"] == HEALTH.KIND_THROTTLED
    assert HEALTH.classify_llm_provider_error(
        _StatusError(400, "prompt is too long")
    )["kind"] == HEALTH.KIND_CONTEXT_LENGTH


# ══════════════════════════════════════════════════════════════════════
#  3) 재시도 판정 — 상한 · backoff · headroom 게이트
# ══════════════════════════════════════════════════════════════════════

_TRANSIENT_CONN = {"kind": LLM.FAILURE_TRANSIENT, "tag": "x", "timeout_class": False}
_TRANSIENT_TIMEOUT = {"kind": LLM.FAILURE_TRANSIENT, "tag": "x", "timeout_class": True}
_PERMANENT = {"kind": LLM.FAILURE_PERMANENT, "tag": "auth_invalid", "timeout_class": False}


def test_connection_failure_retries_up_to_cheap_cap_then_stops():
    """**계약 갱신(2026-08-12 2차 사고)**: 초판은 연결 실패도 `AGENT_LLM_TRANSIENT_RETRY_MAX`(2)
    로 묶었는데, 그 2회(총 4.5초)가 게이트웨이 교체 공백 48초를 못 덮어 154초 추론이 폐기됐다.
    연결 실패는 요청이 도달조차 못 해 재시도 비용이 ~0 이므로 **값싼 실패 전용 예산**을 쓴다.
    예산 세부는 `test_llm_transient_resume.py` 가 소유한다 — 여기서는 "더 이상 작은 상한에
    묶이지 않는다" 만 고정한다(옛 계약으로의 회귀 차단)."""
    cap = AC.AGENT_LLM_TRANSIENT_RETRY_CHEAP_MAX
    assert cap > AC.AGENT_LLM_TRANSIENT_RETRY_MAX
    for n in range(1, cap + 1):
        assert AC._llm_retry_allowed(_TRANSIENT_CONN, n,
                                     remaining_budget_sec=1.0, per_attempt_timeout_sec=300.0)
    assert not AC._llm_retry_allowed(_TRANSIENT_CONN, cap + 1,
                                     remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0)


def test_permanent_failure_never_retries():
    assert not AC._llm_retry_allowed(_PERMANENT, 1,
                                     remaining_budget_sec=9999.0, per_attempt_timeout_sec=300.0)


def test_connection_failure_ignores_budget_headroom():
    """요청이 도달조차 못 했으므로 재호출 비용은 ~0 — 예산이 거의 없어도 한 번은 붙어봐야 한다."""
    assert AC._llm_retry_allowed(_TRANSIENT_CONN, 1,
                                 remaining_budget_sec=0.5, per_attempt_timeout_sec=300.0)


def test_timeout_retry_requires_budget_headroom():
    """예산이 모자란 타임아웃 재시도는 어차피 예산 컷에 걸린다 — 대기만 늘리므로 하지 않는다."""
    assert not AC._llm_retry_allowed(_TRANSIENT_TIMEOUT, 1,
                                     remaining_budget_sec=10.0, per_attempt_timeout_sec=300.0)
    assert AC._llm_retry_allowed(_TRANSIENT_TIMEOUT, 1,
                                 remaining_budget_sec=400.0, per_attempt_timeout_sec=300.0)


def test_timeout_retry_allowed_when_budget_unlimited():
    """사용자가 타임아웃 연장을 승인한 run(remaining=None)은 예산 컷 자체가 없다."""
    assert AC._llm_retry_allowed(_TRANSIENT_TIMEOUT, 1,
                                 remaining_budget_sec=None, per_attempt_timeout_sec=300.0)


def test_backoff_is_exponential_and_capped():
    waits = [AC._llm_retry_backoff_sec(n) for n in range(1, 8)]
    assert waits[0] == pytest.approx(AC.AGENT_LLM_TRANSIENT_RETRY_BASE_SEC)
    assert waits[1] > waits[0], "지수 증가여야 장애 창에서 같은 초에 재요청을 쌓지 않는다"
    assert max(waits) <= AC.AGENT_LLM_TRANSIENT_RETRY_MAX_SEC + 1e-9
    assert all(b >= a for a, b in zip(waits, waits[1:])), "단조 증가"


# ══════════════════════════════════════════════════════════════════════
#  4) 출하 상수 계약 (fixture 로 낮추지 않는다 — vacuous-pass 방지)
# ══════════════════════════════════════════════════════════════════════

def test_shipped_retry_constants():
    """이 값들이 곧 봉인의 실효 강도다. 0 으로 돌리는 뮤턴트는 사고 당시 동작 그 자체다."""
    assert AC.AGENT_LLM_TRANSIENT_RETRY_MAX >= 1
    assert 0.0 < AC.AGENT_LLM_TRANSIENT_RETRY_BASE_SEC <= 5.0
    assert AC.AGENT_LLM_TRANSIENT_RETRY_MAX_SEC >= AC.AGENT_LLM_TRANSIENT_RETRY_BASE_SEC
    # 대기 중 취소 폴링 주기 — 이 값이 커지면 재시도 대기가 새 사각지대가 된다.
    assert 0.0 < AC._LLM_RETRY_CANCEL_POLL_SEC <= 2.0
    assert 0.0 < AC._LLM_SLOW_FAILURE_RATIO <= 1.0


def test_gateway_stop_grace_covers_observed_llm_latency():
    """배포측 축(RC-2). 파일 소유는 feature-0020 이지만 **같은 봉인의 반쪽**이라 여기서 함께
    고정한다 — 앱 재시도만 남고 grace 가 120s 로 되돌아가면 배포마다 8%의 라운드가 다시 죽는다
    (30일 1,210 라운드 중 120초 초과 96건 = 7.9%, p95 181.8s).
    per-attempt 상한(AGENT_TIMEOUT_SEC 기본 300s) 이상이어야 연장 미승인 run 이 전부 drain 된다."""
    import os
    import yaml

    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    with open(os.path.join(root, "docker-compose.yml"), "r", encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)

    for svc in ("bedrock-gateway", "bedrock-gateway-surge"):
        raw = str(compose["services"][svc]["stop_grace_period"])
        secs = int(raw.rstrip("s"))
        assert secs >= 300, (
            f"{svc}: stop_grace_period={raw} — per-attempt 상한(300s)보다 짧으면 "
            f"배포가 진행 중 LLM 호출을 SIGKILL 한다"
        )


def test_retry_wait_total_is_bounded_well_under_run_budget():
    """최악 총 대기(모든 재시도가 실패)가 run 예산을 잠식하지 않아야 한다."""
    total = sum(AC._llm_retry_backoff_sec(n)
                for n in range(1, AC.AGENT_LLM_TRANSIENT_RETRY_MAX + 1))
    assert total <= 60.0, f"재시도 대기 총합 {total}s — 사용자 체감 대기를 늘리는 쪽으로 과대"


# ══════════════════════════════════════════════════════════════════════
#  4b) §18.8 패널 흡수 — 느린 실패 · 탈출구 · SDK 재시도 중첩
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "message",
    ["Gateway timeout", "litellm.Timeout: AnthropicException", "deadline exceeded"],
    ids=["504", "litellm", "deadline"],
)
def test_gateway_side_timeouts_are_timeout_class(message):
    """패널 P1-1: 게이트웨이가 상류 대기를 소진하고 돌려준 실패도 재시도가 예산을 통째로
    한 번 더 태운다 — 클라이언트측 타임아웃과 같은 부류로 게이트해야 한다."""
    assert LLM.classify_agent_llm_failure(_StatusError(504, message))["timeout_class"] is True


def test_slow_failure_gets_headroom_gate_even_if_not_classified_timeout():
    """패널 P1-1 구조 축 — 어휘 매칭은 provider 문구 변경에 drift 하므로 **측정**이 정본이다.
    상한의 절반 이상을 태우고 죽은 실패는 분류가 무엇이든 예산 게이트를 받는다."""
    slow = dict(_TRANSIENT_CONN)          # timeout_class=False (연결 절단으로 분류됨)
    assert not AC._llm_retry_allowed(slow, 1, remaining_budget_sec=10.0,
                                     per_attempt_timeout_sec=300.0,
                                     attempt_elapsed_sec=280.0)
    # 같은 실패라도 빨리 죽었으면(진짜 순단) 예산과 무관하게 재시도한다.
    assert AC._llm_retry_allowed(slow, 1, remaining_budget_sec=10.0,
                                 per_attempt_timeout_sec=300.0,
                                 attempt_elapsed_sec=0.4)


def test_retry_loop_defers_to_outer_loop_on_immediate_answer():
    """패널 P1-2: '즉시 답변' 을 재시도 루프가 소비하면 바깥 루프의 마무리 처리(도구 끄기 +
    최종 답변 지시)가 건너뛰어지고 **도구를 켠 원래 라운드를 다시** 부른다."""
    with open(AC.__file__, "r", encoding="utf-8") as fh:
        src = fh.read()
    block = src[src.index("_llm_defer_to_outer = False"):src.index("if _llm_defer_to_outer:")]
    assert "_clear_finalize_request" not in block, \
        "재시도 루프가 finalize 를 소비하면 바깥 루프가 마무리 경로로 전환하지 못한다"
    # 확인 지점은 **두 곳** 이어야 한다: ① 재시도를 결정하기 전 ② backoff 대기가 끝난 뒤.
    # 하나만 있으면 나머지 창에서 버튼이 먹히지 않는다(둘 중 아무거나 지워도 통과하던 초판 결함).
    checks = [m.start() for m in re.finditer(re.escape("_finalize_requested(mem_conn, cid, run_id)"), block)]
    assert len(checks) == 2, f"'즉시 답변' 확인 지점이 {len(checks)}곳 — 재시도 전/backoff 후 둘 다 필요"
    commit = block.index("_llm_retry_n += 1")
    assert checks[0] < commit, "재시도를 확정한 뒤에 확인하면 이미 긴 호출이 시작된다"
    assert checks[1] > commit, "backoff 대기 뒤 확인이 없다"


def test_retry_rechecks_cancel_after_backoff():
    """패널 P2-1: backoff 마지막 tick 뒤 도착한 중단 신호를 못 보면, 바로 다음 줄의
    블로킹 호출 때문에 사용자가 수 분을 더 기다린다."""
    with open(AC.__file__, "r", encoding="utf-8") as fh:
        src = fh.read()
    block = src[src.index("_wait_left = _llm_retry_backoff_sec"):src.index("if _llm_defer_to_outer:")]
    after_wait = block[block.index("_wait_left -= _tick"):]
    assert "_cancel_requested_for_run" in after_wait, "backoff 종료 후 취소 재확인이 없다"


def test_conversation_client_pins_sdk_retries_to_zero():
    """패널 P2-2: SDK 재시도가 앱 재시도와 중첩되면 provider 호출이 곱해지고 총-대기가
    per-attempt 상한의 배수가 된다(취소·즉시답변이 그 사이 무응답)."""
    with open(AC.__file__, "r", encoding="utf-8") as fh:
        src = fh.read()
    i = src.index("client = OpenAI(")
    ctor = src[i:i + 400]
    assert "max_retries=0" in ctor, "대화 클라이언트가 SDK 재시도 knob 를 그대로 따르고 있다"
    assert "max_retries=max(0, int(AGENT_OPENAI_MAX_RETRIES))" not in ctor


# ══════════════════════════════════════════════════════════════════════
#  5) 히스토리 창 — 최신 N행을 집는가 (FR-agent-history-window-inverted)
# ══════════════════════════════════════════════════════════════════════

_PG_HISTORY_SQL = {
    "linear": RB._PG_LOAD_CORE_MESSAGES,
    "windowed": RB._PG_LOAD_CORE_MESSAGES_WINDOWED,
    "branch": RB._PG_LOAD_CORE_MESSAGES_BRANCH,
}


@pytest.mark.parametrize("name", sorted(_PG_HISTORY_SQL))
def test_pg_history_selects_newest_rows(name):
    """`ORDER BY id ASC LIMIT n` 은 가장 **오래된** n행이다 — 라이브 281행 대화에서 최신 81행이
    통째로 빠졌다(id 3369~3574 만 로드, 3575~3655 유실). LIMIT 을 받는 정렬은 DESC 여야 한다."""
    sql = _PG_HISTORY_SQL[name]
    limit_clause = re.search(r"ORDER BY\s+id\s+(ASC|DESC)\s+LIMIT", sql, re.I)
    assert limit_clause is not None, f"{name}: LIMIT 을 받는 ORDER BY 를 찾지 못함"
    assert limit_clause.group(1).upper() == "DESC", (
        f"{name}: LIMIT 이 오름차순 정렬에 걸려 있으면 최신 맥락이 유실된다"
    )


@pytest.mark.parametrize("name", sorted(_PG_HISTORY_SQL))
def test_pg_history_returns_ascending(name):
    """호출측(`_assemble_core_messages`)은 오름차순 목록을 전제로 tail 을 취한다 — 계약 불변."""
    sql = _PG_HISTORY_SQL[name].rstrip()
    assert re.search(r"ORDER BY\s+id\s+ASC\s*$", sql, re.I), f"{name}: 최종 정렬이 ASC 가 아니다"


def test_pg_history_matches_mysql_direction():
    """같은 대화를 두 백엔드가 다르게 자르면 backend 토글만으로 답변 품질이 바뀐다."""
    src = AC.__file__
    with open(src, "r", encoding="utf-8") as fh:
        body = fh.read()
    assert "ORDER BY id DESC LIMIT %s" in body, "MySQL 경로가 최신 n행을 집는다는 전제가 깨졌다"


def test_visibility_predicates_survive_inside_subquery():
    """가시성 술어가 서브쿼리 밖으로 새면 은닉 구간이 모델에 들어간다(보안 경계)."""
    for name in ("windowed", "branch"):
        sql = _PG_HISTORY_SQL[name]
        head, _, tail = sql.partition("ORDER BY id DESC")
        assert "recall_floor_created_at" in head, f"{name}: 가시성 술어가 LIMIT 앞에 없다"
        assert "floor_ca" in head and "ceil_ca" in head and "joined_ca" in head
        assert "floor_ca" not in tail, f"{name}: 술어가 서브쿼리 밖으로 샜다"


# ══════════════════════════════════════════════════════════════════════
#  6) 배포측 드리프트 표면화 (패널 P1-3)
# ══════════════════════════════════════════════════════════════════════

def _run_grace_drift_warn(tmp_path, grace: str, timeout_line: str) -> str:
    """`bin/deploy-web.sh` 의 경고 함수만 떼어내 합성 입력으로 실행한다."""
    import os
    import subprocess
    import textwrap

    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    with open(os.path.join(root, "bin", "deploy-web.sh"), "r", encoding="utf-8") as fh:
        sh = fh.read()
    start = sh.index("gateway_grace_drift_warn() {")
    end = sh.index("deploy_gateway_reconcile() {")
    fn = sh[start:end]

    (tmp_path / "docker-compose.yml").write_text(textwrap.dedent(f"""\
        services:
          bedrock-gateway:
            image: x
            stop_grace_period: {grace}
          caddy:
            image: y
        """), encoding="utf-8")
    (tmp_path / ".env").write_text(timeout_line + "\n", encoding="utf-8")
    script = "warn() { printf 'WARN: %s\\n' \"$*\" >&2; }\n" + fn + "\ngateway_grace_drift_warn\n"
    p = subprocess.run(["bash", "-c", script], cwd=str(tmp_path),
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stderr


def test_grace_drift_warns_when_timeout_exceeds_grace(tmp_path):
    """운영자가 콘솔에서 타임아웃을 grace 위로 올리면 매 배포가 in-flight 를 죽인다 —
    compose 는 정적이라 아무도 알려주지 않으므로 배포가 표면화해야 한다."""
    out = _run_grace_drift_warn(tmp_path, "330s", "AGENT_TIMEOUT_SEC=600")
    assert "stop_grace_period=330s" in out and "AGENT_TIMEOUT_SEC=600" in out


def test_grace_drift_silent_when_covered(tmp_path):
    """역검증 — 덮이는 정상 구성에서는 경고하지 않는다(경보 피로 방지)."""
    out = _run_grace_drift_warn(tmp_path, "330s", "AGENT_TIMEOUT_SEC=300")
    assert "stop_grace_period" not in out


def test_shipped_env_timeout_is_covered_by_grace():
    """출하 구성 자체는 덮여 있어야 한다(현행 `.env` 기준). `.env` 없으면 skip."""
    import os
    import re

    import yaml

    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env_path = os.path.join(root, ".env")
    if not os.path.exists(env_path):
        pytest.skip(".env 없음(테스트 환경) — 출하 구성 대조 불가")
    with open(env_path, "r", encoding="utf-8") as fh:
        m = re.search(r"^AGENT_TIMEOUT_SEC=(\d+)", fh.read(), re.M)
    if not m:
        pytest.skip("AGENT_TIMEOUT_SEC 미설정")
    with open(os.path.join(root, "docker-compose.yml"), "r", encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)
    grace = int(str(compose["services"]["bedrock-gateway"]["stop_grace_period"]).rstrip("s"))
    assert grace > int(m.group(1)), "출하 타임아웃이 grace 를 넘겨 매 배포가 in-flight 를 죽인다"
