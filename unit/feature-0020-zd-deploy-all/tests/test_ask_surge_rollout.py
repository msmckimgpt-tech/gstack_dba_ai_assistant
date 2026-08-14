"""ask-worker surge 교대 — 바쁜 시간대에도 배포가 완결된다 (CHG-20260814T120000).

재현한 결함(2026-08-14 라이브 실측): 배포가 web 은 신 커밋으로 올렸는데 ask-worker 는 구버전에
멈췄고, 순차 롤아웃이라 **그 뒤 ops-scheduler·ext-tool-mcp 까지 연쇄로** 구버전에 묶였다.
재실행해도 같은 자리에서 다시 막혔다. 원인은 전역 quiesce 게이트가 "진행 중 사용자 run 이
시스템 전체에서 0" 을 요구한 것 — 실측 유입 7~10분 간격 + run p95 691s 조합에서 낮 시간대에는
상한 900s 안에 그런 창이 생기지 않는다. 즉 **사용자가 쓸수록 배포가 안 되는 구조**였다.

푸는 방식이 gateway 와 다른 이유: gateway 는 HTTP 소켓에 in-flight 가 붙어 있어 프로세스 간
이전이 불가능하지만, ask-worker 는 **PG 큐 소비자**다. 신규 job 은 `ask_jobs` 에서 오고 claim 은
`FOR UPDATE SKIP LOCKED` + lease_epoch fencing 이라 다중 인스턴스가 exactly-once 다. 그래서
"조용해지기를 기다린다" 가 아니라 **"받는 쪽을 먼저 세운다"** 로 푼다.

합격선:
  1. ask-worker 교체가 전역 정적 대기에 의존하지 않는다(surge 가 신규를 받는다).
  2. 순서: surge healthy → 본체 drain → 본체 교체 → surge 정리. 하나라도 어긋나면 창이 생긴다.
  3. surge 가 본체와 **같은 이미지 핀**을 받는다(아니면 교체 창에 신규 job 이 구 코드로 간다).
  4. 한 워커의 미교체가 **무관한 워커를 막지 않는다**(연쇄 차단 해소).
  5. 부분 완료를 완료로 기록하지 않는다 — `agent_current` 는 실측 검증 뒤에만 쓴다.
  6. 롤백은 surge 를 먼저 없앤다(안 그러면 신 코드가 큐에서 계속 일한다).
  7. drain 예산 초과는 **보고된다**(조용히 넘기면 "무중단이었다" 로 읽힌다).
  8. liveness 판정이 인스턴스별로 격리된다(공유 키면 surge 공존 창에서 서로를 가린다).
"""
import os
import re

import pytest
import yaml

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DEPLOY_SH = os.path.join(_ROOT, "bin", "deploy-web.sh")
_COMPOSE = os.path.join(_ROOT, "docker-compose.yml")
_ASK_PY = os.path.join(_ROOT, "unit", "feature-0002-agent-core", "src", "modules", "ask.py")
_HEALTHCHECK = os.path.join(
    _ROOT, "unit", "feature-0002-agent-core", "src", "scripts", "healthcheck_ask_worker.py")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _script() -> str:
    return _read(_DEPLOY_SH)


def _compose() -> dict:
    return yaml.safe_load(_read(_COMPOSE))


def _fn(name: str, end_marker: str) -> str:
    """deploy-web.sh 의 함수 본문 한 덩어리."""
    s = _script()
    start = s.index(f"{name}() {{")
    return s[start:s.index(end_marker, start)]


# ══════════════════════════════════════════════════════════════════════
#  1) surge 서비스 정의 — 평시 비용 0, 교체 창에는 신 코드
# ══════════════════════════════════════════════════════════════════════

def test_surge_service_exists_and_is_profile_gated():
    """평시에 뜨면 steady-state 리소스가 늘고, 프로필이 없으면 `up` 이 항상 띄운다."""
    svc = _compose()["services"]
    assert "ask-worker-surge" in svc, "surge 서비스가 없다 — 교체 창에 신규 job 을 받을 주체가 없다"
    assert svc["ask-worker-surge"].get("profiles") == ["deploy-surge"], \
        "profile 게이트가 없으면 평시에도 기동한다"
    assert str(svc["ask-worker-surge"].get("restart")) == "no", \
        "restart 정책이 있으면 정리 실패 시 유령 워커가 큐에서 계속 일한다"


def test_surge_runs_the_same_worker_entrypoint():
    """다른 진입점이면 신규 job 을 아예 안 가져간다 — surge 가 있으나 마나가 된다."""
    svc = _compose()["services"]
    assert svc["ask-worker-surge"]["entrypoint"] == svc["ask-worker"]["entrypoint"]
    assert svc["ask-worker-surge"]["environment"]["AGENT_ASK_WORKER_ENABLED"] == "1"


def test_drain_budget_is_symmetric_between_main_and_surge():
    """surge 쪽만 짧으면 본체 구멍을 막고 surge 에 같은 구멍을 남긴다(gateway surge 와 동일 근거).

    교체 창에 들어온 run 은 surge 가 들고 있으므로, surge 를 정리할 때도 같은 완주 예산이 필요하다.
    """
    svc = _compose()["services"]
    assert svc["ask-worker"]["stop_grace_period"] == svc["ask-worker-surge"]["stop_grace_period"]


def test_stop_grace_covers_the_observed_run_tail():
    """종전 70s 는 실측 run 의 66%를 못 덮었다 — 그것이 배포마다 답변을 죽이던 창이다.

    p95 691s 를 넉넉히 넘겨야 '완주 후 종료' 가 예외가 아니라 정상 경로가 된다.
    """
    svc = _compose()["services"]
    grace = int(str(svc["ask-worker"]["stop_grace_period"]).rstrip("s"))
    assert grace >= 700, f"stop_grace_period={grace}s — p95(691s) 를 못 덮어 완주가 예외가 된다"


# ══════════════════════════════════════════════════════════════════════
#  2) 롤아웃 순서 — 창이 생기지 않는가
# ══════════════════════════════════════════════════════════════════════

def test_surge_is_healthy_before_main_is_drained():
    """본체를 먼저 내리면 그 사이 신규 job 을 받을 주체가 없다(= 큐 적체 = 사실상 중단)."""
    body = _fn("rollout_ask_worker_via_surge", "deploy_workers() {")
    surge_up = body.index('up -d --no-deps --no-build "$ASK_WORKER_SURGE"')
    healthy = body.index("wait_ask_surge_healthy")
    drain = body.index('drain_stop_ask "$ASK_WORKER_SERVICE"')
    recreate = body.index('--force-recreate "$ASK_WORKER_SERVICE"')
    assert surge_up < healthy < drain < recreate, \
        "surge healthy → 본체 drain → 본체 교체 순서가 아니다"


def test_surge_cleanup_happens_after_main_is_healthy():
    """본체가 healthy 되기 전에 surge 를 없애면 그 순간 처리 주체가 0 이 된다."""
    body = _fn("rollout_ask_worker_via_surge", "deploy_workers() {")
    main_healthy = body.index('wait_worker_healthy "$ASK_WORKER_SERVICE"')
    cleanup = body.index('drain_stop_ask "$ASK_WORKER_SURGE"')
    assert main_healthy < cleanup


def test_surge_failure_leaves_main_untouched():
    """새 이미지가 못 뜨는데 본체를 내리면, 고칠 수 있었던 배포가 장애가 된다."""
    body = _fn("rollout_ask_worker_via_surge", "deploy_workers() {")
    fail_branch = body[body.index("wait_ask_surge_healthy"):body.index('drain_stop_ask "$ASK_WORKER_SERVICE"')]
    assert 'rm -sf "$ASK_WORKER_SURGE"' in fail_branch, "surge 기동 실패 시 정리가 없다"
    assert "return 2" in fail_branch, \
        "본체 무접촉 중단을 이미지 결함과 같은 코드로 반환하면 멀쩡한 워커까지 롤백된다"


@pytest.mark.parametrize("fn,end", [
    ("rollout_ask_worker_via_surge", "deploy_workers() {"),
    ("drain_stop_ask", "# 직전 배포가 정리 전에 죽었으면"),
    ("sweep_leaked_ask_surge", "rollout_ask_worker_via_surge() {"),
])
def test_ask_surge_helpers_never_touch_web_replicas(fn, end):
    """이 세 함수는 feature-0014 의 recreate allowlist 에 등재돼 있다 — 그 등재의 전제를 잠근다.

    등재 근거는 "web replica 를 만지지 않으므로 엣지 게이트의 관할 밖" 이다. 만약 여기서
    web-a/web-b 를 건드리게 되면 그 replica 는 **엣지 후보 복귀 게이트를 거치지 않고** 재생성되고,
    그것이 정확히 2026-08-11 의 `no upstreams available` 전면 503 기전이다.
    """
    body = _fn(fn, end)
    assert "web-a" not in body and "web-b" not in body, \
        f"{fn} 이 web replica 를 참조한다 — 엣지 게이트를 우회하는 경로가 열린다"
    assert "REPLICAS" not in body, f"{fn} 이 web replica 배열을 참조한다"


def test_surge_gets_the_same_image_pin_as_the_workers():
    """핀이 없으면 compose 가 build 정의로 되돌아가 surge 만 다른(대개 stale) 이미지로 뜬다.

    그러면 교체 창 동안 신규 job 이 **구 코드로** 처리된다 — 무중단이지만 배포는 거짓이 된다.
    """
    body = _fn("write_pin_overlay", "DC_PROD=()")
    assert '"$ASK_WORKER_SURGE" "$agent_img"' in body, "surge 가 agent 이미지 핀을 못 받는다"


# ══════════════════════════════════════════════════════════════════════
#  3) 연쇄 차단 해소 + 완결 판정
# ══════════════════════════════════════════════════════════════════════

def test_ask_worker_deferral_does_not_block_unrelated_workers():
    """2026-08-14 실측 결함의 봉인: ask-worker 하나가 못 바뀌면 뒤 워커가 전부 묶였다.

    ops-scheduler·ext-tool-mcp 는 사용자 run 과 무관하고 ask-worker 에 의존하지도 않는다.
    """
    body = _fn("deploy_workers", "# 모든 워커가 실제로 대상 sha")
    branch = body[body.index("case \"$rc\" in"):body.index("continue\n    fi")]
    assert "deferred+=" in branch and "continue" in branch, \
        "무접촉 중단이 여전히 루프를 끊는다 — 연쇄 미배포 회귀"
    assert re.search(r'2\)\s*\n(?:.*\n)*?\s*deferred\+=', branch), \
        "rc=2(본체 무접촉) 분기가 나머지 워커를 계속 롤아웃하지 않는다"


def test_partial_rollout_is_not_recorded_as_complete():
    """`agent_current` 는 '워커가 이 sha 로 돈다' 는 주장이다.

    부분 완료에서 그것을 쓰면 다음 배포의 멱등 skip 이 그 주장을 믿고 빌드를 건너뛴다 —
    미교체 컨테이너가 조용히 영구 stale 이 되는 경로(라이브에 실재했다: insight 만 신 sha 인데
    state 는 구 sha).
    """
    body = _fn("deploy_workers", "# 모든 워커가 실제로 대상 sha")
    verify = body.index("verify_workers_at_sha")
    record = body.index('state_set agent_current "$sha"')
    assert verify < record, "완결 판정 전에 agent_current 를 기록한다"
    assert "return 1" in body[verify:record], "판정 실패인데도 기록으로 흘러간다"


def test_completion_is_judged_from_live_containers_not_state():
    """state 파일이나 스크립트 진행 상황은 주장이고, 컨테이너의 GIT_COMMIT 이 사실이다."""
    body = _fn("verify_workers_at_sha", "\nrollback_workers() {")
    assert "worker_commit" in body and "container_health" in body
    assert 'for svc in "${WORKERS[@]}"' in body, "일부 서비스만 검증하면 완결 판정이 아니다"


# ══════════════════════════════════════════════════════════════════════
#  4) 롤백 · 정직 보고
# ══════════════════════════════════════════════════════════════════════

def test_rollback_removes_surge_first():
    """롤백은 '신 코드를 라이브에서 뺀다' 는 뜻인데, surge 가 남으면 큐에서 계속 일한다."""
    body = _fn("rollback_workers", "# ── bedrock-gateway 무중단 reconcile")
    remove = body.index('rm -sf "$ASK_WORKER_SURGE"')
    recreate = body.index('--force-recreate "$svc"')
    assert remove < recreate, "surge 를 남긴 채 워커를 되돌린다 — 신 코드가 계속 서빙"


def test_leaked_surge_is_swept_before_rollout():
    """직전 배포가 정리 전에 죽으면 surge 가 구/신 코드로 계속 job 을 가져간다."""
    body = _fn("deploy_workers", "# 모든 워커가 실제로 대상 sha")
    assert "sweep_leaked_ask_surge" in body
    sweep = _fn("sweep_leaked_ask_surge", "rollout_ask_worker_via_surge() {")
    assert "container_health" in sweep, "본체 상태를 안 보고 정리하면 유일 처리 주체를 없앨 수 있다"


def test_drain_timeout_is_reported_not_swallowed():
    """예산을 다 쓰면 SIGKILL 이고 그 run 들은 재큐된다 — 조용히 넘기면 '무중단' 으로 읽힌다."""
    body = _fn("drain_stop_ask", "# 직전 배포가 정리 전에 죽었으면")
    assert "QUIESCE_REPORT" in body and "QUIESCE_FORCED" in body, \
        "끊긴 run 이 배포 말미 요약에 나타나지 않는다(LRN-20260811T1557)"
    assert "DRAIN-TIMEOUT" in body


def test_container_scoped_job_count_does_not_read_failure_as_zero():
    """조회 실패를 0 으로 읽으면 '다 끝났다' 는 거짓 안심이 된다(quiesce 의 vacuous pass 와 동형)."""
    body = _fn("ask_running_jobs_for_host", "# surge/본체를 **완주 예산 안에서**")
    assert "unknown" in body, "관측 실패가 0 과 구분되지 않는다"


def test_drain_captures_hostname_before_stopping():
    """자가 검증(2026-08-14)에서 적발한 결함의 봉인.

    `docker compose ps -q` 는 **running 만** 반환한다(라이브 실측: stop 직후 빈 값, `ps -aq` 는 cid).
    초판은 stop **후** 컨테이너로 job 수를 다시 조회했는데, 그 시점 cid 가 빈 값이라 조기 반환으로
    **`after` 가 항상 0** 이었다. 그러면 "보유 N→0 — 끊긴 run 없음" 은 관측이 아니라 상수다.
    """
    body = _fn("drain_stop_ask", "# 직전 배포가 정리 전에 죽었으면")
    host_capture = body.index('host="$(ask_container_hostname')
    stop_call = body.index('stop -t "$ASK_DRAIN_TIMEOUT"')
    after_read = body.index('after="$(ask_running_jobs_for_host')
    assert host_capture < stop_call < after_read, \
        "hostname 을 stop 전에 확보하지 않으면 drain 후 관측이 상수가 된다"
    assert 'ask_running_jobs_for_host "$host"' in body, \
        "stop 후 조회가 컨테이너에 다시 의존한다 — 정지된 컨테이너는 ps -q 로 안 보인다"


def test_residual_running_after_drain_is_reported_as_cut():
    """정상 종료했는데 그 인스턴스 소유 running 이 남았다면 완주도 반납도 못 한 run 이다.

    role-reclaim 이 회수하지만 **사용자에겐 재실행**이므로 '끊긴 run 없음' 으로 보고하면 안 된다.
    """
    body = _fn("drain_stop_ask", "# 직전 배포가 정리 전에 죽었으면")
    assert "=CUT(" in body, "잔존 run 이 끊긴 것으로 보고되지 않는다"
    assert "drained-unverified" in body, "관측 실패(unknown)를 조용함으로 읽는다"
    # 0 분기에서만 성공(0) 을 반환해야 한다.
    zero_branch = body[body.index("case \"$after\" in"):]
    assert zero_branch.index("return 0") < zero_branch.index("return 1"), \
        "0 이 아닌 잔존에도 성공을 반환한다"


def test_surge_presence_check_includes_stopped_containers():
    """leaked surge 는 대개 'stop 은 됐는데 rm 이 실패한' 형태로 남는다.

    `ps -q` 로 찾으면 정확히 그 형태를 놓치고, 그 컨테이너는 다음 `up -d` 로 되살아나
    큐에서 다시 일한다(라이브 실측 2026-08-14: stop 직후 `ps -q`=빈 값, `ps -aq`=cid).
    """
    body = _fn("ask_surge_cid", "ask_surge_health() {")
    assert "ps -aq" in body, "surge 존재 확인이 running 상태에만 의존한다 — stopped leaked 를 놓친다"
    host_body = _fn("ask_container_hostname", "# 그 **인스턴스가 자기 이름으로")
    assert "ps -aq" in host_body, "정지된 컨테이너의 hostname 을 못 읽는다"


# ══════════════════════════════════════════════════════════════════════
#  5) liveness 격리 — surge 공존 창에서 서로를 가리지 않는가
# ══════════════════════════════════════════════════════════════════════

def test_liveness_stop_is_separate_from_shutdown():
    """drain 은 '죽어가는 중' 이 아니라 '진행 중 run 을 마치는 중' 이다.

    `_SHUTDOWN` 으로 liveness 를 같이 멈추면 살아 있는 컨테이너가 unhealthy 로 보이고,
    배포 스파인이 그 신호로 판정하므로 그냥 오탐이 아니라 잘못된 롤백이 된다.
    """
    s = _read(_ASK_PY)
    assert "_LIVENESS_STOP = threading.Event()" in s
    assert "_LIVENESS_STOP.wait(interval_sec)" in s, "liveness 루프가 자기 신호로 대기하지 않는다"
    # 종료 시점에만 멈춘다 — drain 구간에서 세우면 위 오탐이 그대로 재현된다.
    idx_set = s.index("_LIVENESS_STOP.set()")
    idx_release = s.index('_release_own_leases(worker_id, reason="graceful shutdown")')
    assert idx_release < idx_set, "lease 반납(=drain 종료)보다 먼저 liveness 를 멈춘다"


def test_liveness_thread_starts_before_the_main_loop():
    """부팅 중(role reclaim·warm-up)에도 컨테이너는 살아 있고 healthcheck 는 그것을 알아야 한다."""
    s = _read(_ASK_PY)
    start = s.index("_start_liveness_thread(")
    loop = s.index("while not _SHUTDOWN.is_set():")
    assert start < loop


def test_healthcheck_prefers_container_local_stamp():
    """KV 는 **role 전역 단일 키**라 본체와 surge 가 같은 값을 갱신한다.

    그러면 죽은 쪽도 healthy 로 보이고(false-pass), drain 중인 본체는 unhealthy 로 보인다
    (false-fail). 컨테이너 로컬 파일만이 그 둘을 구조적으로 분리한다.
    """
    s = _read(_HEALTHCHECK)
    file_first = s.index("age = _from_alive_file()")
    kv_fallback = s.index("age = _from_kv()")
    assert file_first < kv_fallback, "KV 를 먼저 보면 공유 키가 판정에 끼어든다"
    assert "if age is None:" in s, "파일이 있으면 KV 를 보지 않는다는 조건이 없다"


def test_worker_writes_the_local_stamp_atomically():
    """판독측(healthcheck)이 반쪽 파일을 보면 배포 중 무작위 unhealthy 가 된다."""
    s = _read(_ASK_PY)
    body = s[s.index("def _touch_alive_file"):s.index("def _start_liveness_thread")]
    assert "os.replace(" in body, "원자 교체가 아니다"


def test_alive_file_is_removed_on_exit():
    """프로세스만 죽고 컨테이너가 남은 상태가 임계(60s)를 기다리면 배포 판정이 그만큼 늦다."""
    s = _read(_ASK_PY)
    assert "os.unlink(AGENT_ASK_WORKER_ALIVE_FILE)" in s


@pytest.mark.parametrize("knob", ["AGENT_ASK_WORKER_ALIVE_FILE", "AGENT_ASK_WORKER_LIVENESS_SEC"])
def test_new_knobs_are_exported(knob):
    """config 의 공개 목록에 없으면 import 경로가 조용히 갈라진다."""
    s = _read(os.path.join(_ROOT, "shared", "config.py"))
    assert f'"{knob}",' in s, f"{knob} 이 config 공개 목록에 없다"
    assert f"{knob} = " in s
