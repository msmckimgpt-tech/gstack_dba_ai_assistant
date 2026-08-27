"""배포 quiesce 게이트 — 진행 중 사용자 run 을 죽이지 않는다 (CHG-20260812T140000).

재현한 사고(2026-08-12, conv-audit `FR-llm-transient-failure-kills-run`): 배포가 gateway 를
recreate 하면서 진행 중이던 LLM 호출이 `stop_grace_period` 만료로 SIGKILL 됐고, 사용자는 7분
40초를 기다린 끝에 도구 10회 분량 조사를 잃었다. 같은 기전이 ask-worker 에도 있었다 —
SIGTERM 후 고정 60초만 주는데 **실측 agent run 의 66%가 그보다 길다**(p50 81s · p95 691s).

핵심: **HTTP 요청도 실행 중 run 도 프로세스 간 이전이 불가능하다.** surge replica 는 *신규*
요청만 흡수한다. 그래서 "옮긴다" 가 아니라 **"붙어 있는 게 없을 때 바꾼다"** 로 푼다 —
web 의 `predrain` 이 이미 쓰던 방식(실제 상태 신호 + fail-closed)을 워커·gateway 에 대칭 적용.

합격선:
  1. 진행 중 run 이 0 일 때만 교체가 진행된다.
  2. 상한까지 조용해지지 않으면 **강행이 아니라 중단**한다(구버전이 계속 서빙 = 무중단 유지).
  3. 두 신호 모두 관측 불가면 0 으로 읽지 않는다 — 그것이 곧 vacuous pass 다.
  4. `--force-busy` 는 통과시키되 **무중단이 아니었음을 보고**한다(성공 보고 ≠ 무중단).
  5. 게이트는 recreate **이전** 에 놓인다(뒤에 있으면 이미 죽인 뒤다).
  6. 이 테스트 디렉토리가 `testpaths` 에 등재돼 있다(밖에 있으면 아무것도 지키지 못한다).
"""
import os
import re
import subprocess
import textwrap

import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DEPLOY_SH = os.path.join(_ROOT, "bin", "deploy-web.sh")
_QUIESCE_LIB = os.path.join(_ROOT, "bin", "lib", "quiesce.sh")
_SAFE_RECREATE = os.path.join(_ROOT, "bin", "safe-recreate.sh")


def _script_text() -> str:
    with open(_DEPLOY_SH, "r", encoding="utf-8") as fh:
        return fh.read()


def _lib_text() -> str:
    with open(_QUIESCE_LIB, "r", encoding="utf-8") as fh:
        return fh.read()


def _extract_quiesce_block() -> str:
    """CHG-20260812T200000: 구현이 `bin/lib/quiesce.sh` 로 이동했다 — **배포 밖의 재생성 경로**
    (safe-recreate.sh · make quiesce-guard)도 같은 판정을 써야 하기 때문이다. 라이브러리는
    그대로 source 가능하므로 헤더의 기본값 주입까지 포함해 전체를 쓴다."""
    return _lib_text()


_STUBS = textwrap.dedent("""\
    log()  { printf '[log] %s\\n' "$*" >&2; }
    warn() { printf '[warn] %s\\n' "$*" >&2; }
    err()  { printf '[err] %s\\n' "$*" >&2; }
    step() { printf '[step] %s\\n' "$*" >&2; }
    DC=(true)
    REPLICAS=(web-a web-b)
    replica_cid() { echo "cid-$1"; }
    replica_active_streams() { echo 0; }
    DRY_RUN=0
    FORCE_BUSY=${FORCE_BUSY:-0}
    QUIESCE_TIMEOUT=${QUIESCE_TIMEOUT:-6}
    QUIESCE_POLL=${QUIESCE_POLL:-1}
    QUIESCE_HEARTBEAT_FRESH=90
    QUIESCE_SETTLE=${QUIESCE_SETTLE:-0}
    QUIESCE_PG_SERVICE=postgres
    QUIESCE_REPORT=""
    QUIESCE_FORCED=0
    """)


# 블록 **뒤** 스텁 — 여기 있어야 스크립트의 실제 정의를 덮는다(앞에 두면 반대로 덮인다).
# feature-0045: `bridge_active_total` 은 게이트의 **네 번째 축**이다(브리지로 처리 중인 작업).
# 기본 스텁을 0(조용함)으로 두어 기존 시나리오의 의미를 보존하고, 이 축 자체의 동작은
# feature-0045 테스트가 따로 검증한다. `server_llm_blocked` 는 실행 모드 분기에만 쓰인다.
_POST_STUBS = textwrap.dedent("""\
    ask_execution_mode() { echo "${MODE_STUB:-worker}"; }
    stale_running_ask_jobs() { echo "${STALE_STUB:-0}"; }
    bridge_active_total() { echo "${BRIDGE_STUB:-0}"; }
    server_llm_blocked() { echo "${LLM_BLOCKED_STUB:-no}"; }
    """)


# 라이브러리는 knob 을 `DEPLOY_QUIESCE_*` env 에서 **무조건 재설정**한다(호출측 셸 변수보다 우선).
# 그래서 테스트가 짧은 상한을 주려면 내부 이름이 아니라 그 env 를 써야 한다 — 초판 하네스가
# `QUIESCE_TIMEOUT` 을 셸 변수로만 넣어 라이브러리 기본값 900s 가 이겼고 스위트가 멈췄다.
_KNOB_ENV = {
    "QUIESCE_TIMEOUT": "DEPLOY_QUIESCE_TIMEOUT",
    "QUIESCE_POLL": "DEPLOY_QUIESCE_POLL",
    "QUIESCE_SETTLE": "DEPLOY_QUIESCE_SETTLE",
    "QUIESCE_HEARTBEAT_FRESH": "DEPLOY_QUIESCE_HEARTBEAT_FRESH",
}


def _run(body: str, env: dict | None = None) -> subprocess.CompletedProcess:
    script = _STUBS + _extract_quiesce_block() + "\n" + _POST_STUBS + body
    e = dict(os.environ)
    # 테스트 기본값: 라이브러리 출하 상한(900s)이 스위트를 멈추지 않게 짧게 둔다.
    e.setdefault("DEPLOY_QUIESCE_TIMEOUT", "6")
    e.setdefault("DEPLOY_QUIESCE_POLL", "1")
    e.setdefault("DEPLOY_QUIESCE_SETTLE", "0")
    for k, v in (env or {}).items():
        e[_KNOB_ENV.get(k, k)] = v
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env=e, timeout=120)


# ══════════════════════════════════════════════════════════════════════
#  1) 게이트 판정
# ══════════════════════════════════════════════════════════════════════

def test_quiet_proceeds():
    p = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 0; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """)
    assert "PROCEED" in p.stdout, p.stderr


def test_busy_until_timeout_aborts():
    """상한까지 조용해지지 않으면 **중단** — 강행하면 고치려던 사고가 그대로 재현된다."""
    p = _run("""
        running_ask_jobs() { echo 2; }
        web_active_streams_total() { echo 0; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1"})
    assert "ABORT" in p.stdout, p.stderr
    assert "fresh=2" in p.stderr


def test_becomes_quiet_midway_proceeds(tmp_path):
    """조용해지면 상한 전에 즉시 진행한다(유휴 98% 환경에서 실제로 일어나는 경로).

    카운터는 **파일**로 센다 — `$(...)` 안의 함수는 서브셸이라 셸 변수 증가가 부모로 돌아오지
    않는다(초판 테스트가 이 함정에 걸려 '조용해지지 않는' 시나리오를 검사하고 있었다)."""
    counter = tmp_path / "c"
    counter.write_text("0", encoding="utf-8")
    p = _run(f"""
        running_ask_jobs() {{
          local n; n=$(cat {counter}); n=$((n+1)); echo "$n" > {counter}
          [ "$n" -ge 3 ] && echo 0 || echo 1
        }}
        web_active_streams_total() {{ echo 0; }}
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"QUIESCE_TIMEOUT": "20", "QUIESCE_POLL": "1"})
    assert "PROCEED" in p.stdout, p.stderr
    assert int(counter.read_text()) >= 3, "조용해지기 전에 통과했다(폴링이 돌지 않음)"


def test_web_streams_alone_blocks():
    """실행 dispatch 는 worker/inprocess 두 모드다 — ask_jobs 만 보면 inprocess 에서 공허 통과."""
    p = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 3; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1"})
    assert "ABORT" in p.stdout, p.stderr
    assert "streams=3" in p.stderr


def test_web_probe_failure_counts_as_unknown_not_zero(tmp_path):
    """**자기 적발(2026-08-12)** — 공용 `replica_active_streams` 는 조회 실패도 0 으로 돌려준다.
    그 값을 그대로 쓰면 조회가 깨진 배포는 **항상 '조용함'으로 통과**해 게이트가 무력해진다.
    존재하는 replica 중 하나라도 못 읽으면 합계는 0 이 아니라 unknown 이어야 한다."""
    p = _run("""
        replica_cid() { echo "cid-$1"; }
        replica_active_streams_strict() { [ "$1" = "web-a" ] && echo 0 || return 3; }
        web_active_streams_total
    """)
    assert p.stdout.strip() == "unknown", p.stderr

    ok = _run("""
        replica_cid() { echo "cid-$1"; }
        replica_active_streams_strict() { echo 0; }
        web_active_streams_total
    """)
    assert ok.stdout.strip() == "0", ok.stderr


def test_web_probe_sums_across_replicas():
    p = _run("""
        replica_cid() { echo "cid-$1"; }
        replica_active_streams_strict() { [ "$1" = "web-a" ] && echo 2 || echo 3; }
        web_active_streams_total
    """)
    assert p.stdout.strip() == "5", p.stderr


def test_strict_probe_does_not_swallow_failure_into_zero():
    """전용 probe 는 실패를 **비-0 종료**로 알린다(공용 헬퍼의 `|| echo 0` 관용을 쓰지 않는다)."""
    block = _extract_quiesce_block()
    assert "replica_active_streams_strict" in block
    assert "sys.exit(3)" in block, "두 스킴 실패를 0 으로 뭉개면 안 된다"
    body = block[block.index("web_active_streams_total()"):]
    assert "replica_active_streams " not in body and "$(replica_active_streams " not in body, \
        "관용 헬퍼를 다시 쓰면 자기 적발한 vacuous pass 가 되살아난다"


def test_unobservable_is_not_quiet():
    """**vacuous pass 방지** — 관측 실패를 0 으로 읽으면 게이트가 있으나 마나다."""
    p = _run("""
        running_ask_jobs() { echo unknown; }
        web_active_streams_total() { echo unknown; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """)
    assert "ABORT" in p.stdout, p.stderr
    assert "관측 실패" in p.stderr, "무엇이 관측되지 않았는지 사람이 알아야 진단이 된다"


def test_any_unknown_signal_blocks(monkeypatch):
    """§18.8 패널 P1-2 흡수 — 초판은 한쪽이 관측되면 다른 쪽 unknown 을 0 으로 읽었다.
    두 신호는 **서로 다른 차원**(worker 큐 vs web 스트림)이라 한쪽으로 다른 쪽을 증명할 수 없다.
    unknown 은 '조용함' 이 아니라 '모름' 이고, 모름은 통과 사유가 되지 않는다."""
    for jobs, streams in (("unknown", "0"), ("0", "unknown"), ("unknown", "unknown")):
        p = _run(f"""
            running_ask_jobs() {{ echo {jobs}; }}
            web_active_streams_total() {{ echo {streams}; }}
            quiesce_user_runs "t" && echo PROCEED || echo ABORT
        """, env={"QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1"})
        assert "ABORT" in p.stdout, f"jobs={jobs} streams={streams}: {p.stderr}"
        assert "unknown" in p.stderr


def test_stale_heartbeat_row_blocks_instead_of_being_ignored():
    """§18.8 패널 P1-4 — 살아 있는 워커도 PG 가 흔들리면 heartbeat 를 놓친다. 그 행을 조용히
    제외하면 진행 중 run 을 죽인다. 분리해 세되 **차단**하고, 로그로 구분해 보여준다."""
    p = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 0; }
        stale_running_ask_jobs() { echo 1; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1", "STALE_STUB": "1"})
    assert "ABORT" in p.stdout, p.stderr
    assert "stale=1" in p.stderr


def test_non_worker_execution_mode_is_not_quiet():
    """§18.8 패널 P1-1 — inprocess 모드에서 `/api/ask` 는 ask_jobs 행을 만들지 않고
    `active_streams` 도 그 요청을 세지 않는다(CSV/SSE 전용). 게이트가 아무것도 못 보는데
    '조용함' 으로 통과하면, 있으나 마나가 아니라 **무중단이라고 믿게 만들어 더 나쁘다**."""
    p = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 0; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"MODE_STUB": "inprocess"})
    assert "ABORT" in p.stdout, p.stderr
    assert "inprocess" in p.stderr

    ok = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 0; }
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"MODE_STUB": "worker"})
    assert "PROCEED" in ok.stdout, ok.stderr


def test_settle_recheck_catches_run_started_after_first_sample(tmp_path):
    """§18.8 패널 P1-3 — 스냅샷 1장은 '그 순간' 만 말한다. 첫 표본이 0 이어도 곧바로 넘어가면
    그 사이 들어온 run 이 죽는다. settle 재확인이 그 창을 좁힌다."""
    c = tmp_path / "n"
    c.write_text("0", encoding="utf-8")
    p = _run(f"""
        running_ask_jobs() {{
          local n; n=$(cat {c}); n=$((n+1)); echo "$n" > {c}
          if [ "$n" = "2" ]; then echo 1; else echo 0; fi
        }}
        web_active_streams_total() {{ echo 0; }}
        quiesce_user_runs "t" && echo PROCEED || echo ABORT
    """, env={"QUIESCE_TIMEOUT": "12", "QUIESCE_POLL": "1", "QUIESCE_SETTLE": "1"})
    assert "settle 재확인에서 신규 run 감지" in p.stderr, p.stderr
    assert "PROCEED" in p.stdout, "재확인 후 조용해지면 결국 진행해야 한다"


# ══════════════════════════════════════════════════════════════════════
#  2) --force-busy 와 정직 보고
# ══════════════════════════════════════════════════════════════════════

def test_force_busy_proceeds_but_is_recorded():
    p = _run("""
        running_ask_jobs() { echo 1; }
        web_active_streams_total() { echo 0; }
        quiesce_gate "t" && echo PROCEED || echo ABORT
        quiesce_summary
    """, env={"FORCE_BUSY": "1", "QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1"})
    assert "PROCEED" in p.stdout, p.stderr
    assert "FORCED" in p.stderr
    assert "무중단이 아니었다" in p.stderr, "강행한 배포가 성공처럼만 보이면 안 된다"


def test_quiet_summary_states_nothing_was_cut():
    p = _run("""
        running_ask_jobs() { echo 0; }
        web_active_streams_total() { echo 0; }
        quiesce_gate "t" >/dev/null
        quiesce_summary
    """)
    assert "끊지 않았다" in p.stderr
    assert "FORCED" not in p.stderr


def test_gate_without_force_aborts():
    p = _run("""
        running_ask_jobs() { echo 1; }
        web_active_streams_total() { echo 0; }
        quiesce_gate "t" && echo PROCEED || echo ABORT
    """, env={"FORCE_BUSY": "0", "QUIESCE_TIMEOUT": "2", "QUIESCE_POLL": "1"})
    assert "ABORT" in p.stdout, p.stderr


# ══════════════════════════════════════════════════════════════════════
#  3) 배선 — 게이트가 recreate 앞에 있는가
# ══════════════════════════════════════════════════════════════════════

def test_ask_worker_no_longer_waits_for_global_quiesce():
    """ask-worker 는 이 게이트를 **쓰지 않는다** (CHG-20260814T120000, 이 파일의 범위 축소).

    전역 정적을 기다리는 방식은 ask-worker 에서 배포를 완결시키지 못했다 — 실측 유입(7~10분
    간격) + run p95(691s) 조합에서 낮 시간대에는 상한 900s 안에 정적 창이 생기지 않는다.
    ask-worker 는 HTTP 소켓이 아니라 **PG 큐 소비자**라 받는 쪽(surge)을 먼저 세울 수 있고,
    그러면 기다릴 이유 자체가 사라진다. 계약은 `test_ask_surge_rollout.py` 가 소유한다.

    게이트 자체는 **gateway 에 그대로 남는다** — 거기서는 in-flight 이 소켓에 붙어 있어
    이전이 불가능하고, 그 전제가 이 파일 나머지 테스트의 근거다.
    """
    s = _script_text()
    workers = s[s.index("deploy_workers() {"):s.index("# 모든 워커가 실제로 대상 sha")]
    assert 'quiesce_gate "ask-worker recreate"' not in workers, \
        "ask-worker 가 다시 전역 정적을 기다린다 — 바쁜 시간대 미배포 회귀"
    assert 'quiesce_gate "gateway recreate"' in s, \
        "gateway 게이트까지 사라지면 소켓 in-flight 를 지키는 축이 없다"


def test_gateway_gate_between_surge_healthy_and_main_recreate():
    """surge 가 신규 요청을 받기 시작한 **뒤** 에, 본체를 내리기 **전** 에 있어야 한다."""
    s = _script_text()
    body = s[s.index("deploy_gateway_reconcile() {"):s.index("# ── asset 스탬프 검증")]
    surge_up = body.index('up -d --no-deps "$GATEWAY_SURGE"')
    gate = body.index('quiesce_gate "gateway recreate"')
    recreate = body.index('--force-recreate "$GATEWAY_SERVICE"')
    assert surge_up < gate < recreate


def test_gateway_gate_abort_cleans_up_surge():
    """중단 경로가 surge 를 남기면 leaked surge 가 stale 이미지를 계속 서빙한다(리뷰 M-1 재발)."""
    s = _script_text()
    body = s[s.index("deploy_gateway_reconcile() {"):s.index("# ── asset 스탬프 검증")]
    abort = body[body.index('quiesce_gate "gateway recreate"'):body.index('--force-recreate "$GATEWAY_SERVICE"')]
    assert 'rm -f "$GATEWAY_SURGE"' in abort, "게이트 중단 시 surge 정리가 없다"


def test_summary_is_emitted_on_success_path():
    """LRN-20260811T1557 — 성공 보고에 무중단 여부가 함께 나와야 한다."""
    s = _script_text()
    tail = s[s.index('step "배포 완료:'):]
    assert "quiesce_summary" in tail[:400]


# ══════════════════════════════════════════════════════════════════════
#  4) 상수·SQL 계약
# ══════════════════════════════════════════════════════════════════════

def test_heartbeat_freshness_filter_present():
    """죽은 워커의 running 한 줄이 배포를 영구 차단하면 게이트가 곧 장애가 된다."""
    block = _extract_quiesce_block()
    assert "heartbeat_at > now() - interval" in block
    assert "status='running'" in block


def test_quiesce_timeout_covers_observed_run_tail():
    """실측 agent run p95 = 691s. 상한이 그보다 짧으면 바쁜 시간대에 배포가 항상 중단된다."""
    s = _lib_text()   # knob 정의는 라이브러리 소유(CHG-20260812T200000)
    m = re.search(r'QUIESCE_TIMEOUT="\$\{DEPLOY_QUIESCE_TIMEOUT:-(\d+)\}"', s)
    assert m, "QUIESCE_TIMEOUT 기본값을 찾지 못함"
    assert int(m.group(1)) >= 700, "p95(691s)를 못 덮는 상한 — 바쁜 창에서 항상 ABORT"


def test_force_busy_flag_is_parsed_and_documented():
    s = _script_text()
    assert "--force-busy)    FORCE_BUSY=1" in s
    header = s[:s.index("# Exit codes:")]
    assert "--force-busy" in header, "usage 에 없는 탈출구는 사람이 찾지 못한다"


def test_tests_dir_registered_in_testpaths():
    """feature-0014 가 남긴 교훈의 자기적용 — testpaths 밖 테스트는 존재해도 지키지 못한다."""
    with open(os.path.join(_ROOT, "pyproject.toml"), "r", encoding="utf-8") as fh:
        cfg = fh.read()
    assert "unit/feature-0020-zd-deploy-all/tests" in cfg


def test_deploy_script_is_syntactically_valid():
    p = subprocess.run(["bash", "-n", _DEPLOY_SH], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_rollback_reports_cut_runs_but_does_not_block():
    """§18.8 패널 P1-5(부분 수용) — 롤백에 게이트를 걸면 결함 있는 배포가 그대로 남는다
    (feature-0014 가 엣지 게이트를 롤백 경로에서 비차단으로 둔 것과 같은 근거).
    그래서 **막지 않되 침묵하지도 않는다** — 무엇을 끊고 가는지 수치로 남긴다."""
    s = _script_text()
    body = s[s.index("rollback_workers() {"):s.index("# ── bedrock-gateway 무중단 reconcile")]
    assert "quiesce_sample" in body, "롤백이 무엇을 끊는지 관측조차 하지 않는다"
    assert "quiesce_gate" not in body, "롤백을 차단하면 복구가 막힌다"
    assert "QUIESCE_FORCED" in body, "끊고 간 사실이 최종 보고에 반영되지 않는다"
    cut = body.index("quiesce_sample")
    recreate = body.index("--force-recreate")
    assert cut < recreate, "관측이 recreate 뒤면 이미 끊긴 뒤다"


def test_settle_knob_documented_and_bounded():
    s = _lib_text()   # knob 정의는 라이브러리 소유(CHG-20260812T200000)
    m = re.search(r'QUIESCE_SETTLE="\$\{DEPLOY_QUIESCE_SETTLE:-(\d+)\}"', s)
    assert m, "settle 간격 knob 이 없다"
    assert 0 < int(m.group(1)) <= 30, "settle 은 짧아야 한다(길면 배포가 무의미하게 늘어난다)"


# ══════════════════════════════════════════════════════════════════════
#  7) 배포 밖 경로 봉인 (CHG-20260812T200000)
# ══════════════════════════════════════════════════════════════════════

def test_gate_lives_in_a_shared_library():
    """게이트가 배포 스크립트 **안에만** 있으면 `docker compose up -d`·`make up`·단일 서비스
    재기동 전부가 사각지대다 — 2026-08-12 17:30 사고가 정확히 그 경로였다."""
    assert os.path.exists(_QUIESCE_LIB)
    lib = _lib_text()
    for fn in ("quiesce_gate", "quiesce_user_runs", "quiesce_sample", "ask_execution_mode"):
        assert f"{fn}()" in lib, f"{fn} 이 라이브러리에 없다"
    dep = _script_text()
    # deploy-web.sh 는 구현을 갖지 않고 source 만 한다(중복 구현 = 판정 drift).
    assert "quiesce_user_runs() {" not in dep, "배포 스크립트에 게이트 구현이 남아 있다(drift 위험)"
    assert '. "$_QUIESCE_LIB"' in dep


def test_safe_recreate_uses_the_same_library_and_gates():
    """인가된 out-of-band 경로가 배포와 **같은 판정**을 쓰지 않으면 기준이 갈라진다."""
    with open(_SAFE_RECREATE, "r", encoding="utf-8") as fh:
        sr = fh.read()
    assert '. "$_QUIESCE_LIB"' in sr
    # usage 주석에도 같은 문자열이 있으므로 **실행부**(옵션 파싱 이후)만 본다.
    body = sr[sr.index("set -euo pipefail"):]
    gate = body.index("quiesce_gate ")
    recreate = body.index('"${DC[@]}" "${_args[@]}"')
    assert gate < recreate, "게이트가 recreate 뒤에 있다"
    assert "--force-busy" in sr, "탈출구가 없으면 운영자가 raw docker 로 우회한다"
    assert "_web_count" in sr and "deploy-web" in sr


def test_both_sanctioned_paths_stamp_the_same_file():
    """감사가 대조할 기준이 하나여야 한다 — 두 경로가 다른 파일에 남기면 오탐/미탐."""
    dep = _script_text()
    with open(_SAFE_RECREATE, "r", encoding="utf-8") as fh:
        sr = fh.read()
    assert "recreate-sanctioned.log" in dep and "recreate-sanctioned.log" in sr
    assert "SAFE_RECREATE_STAMP_FILE" in dep and "SAFE_RECREATE_STAMP_FILE" in sr
    # 배포는 web replica·워커·gateway 세 지점 모두 스탬프해야 감사가 오탐하지 않는다.
    assert dep.count("stamp_sanctioned_recreate ") >= 3


def test_recreate_audit_distinguishes_unknown_from_violation():
    """스탬프 도입 이전 기동을 위반으로 세면 경보 피로로 감사 자체가 무시된다."""
    with open(os.path.join(_ROOT, "bin", "recreate-audit.sh"), "r", encoding="utf-8") as fh:
        ra = fh.read()
    assert "unknown" in ra and "UNSANCTIONED" in ra
    assert "exit 1" in ra, "위반이 있어도 exit 0 이면 자동화가 못 잡는다"
    assert "TOLERANCE_SEC" in ra


def test_make_targets_that_recreate_pass_the_gate():
    """`make up`/`down` 은 이미 떠 있는 서빙 컨테이너를 재생성·정지할 수 있다."""
    with open(os.path.join(_ROOT, "Makefile"), "r", encoding="utf-8") as fh:
        mk = fh.read()
    assert re.search(r"^quiesce-guard:", mk, re.M)
    assert re.search(r"^up: quiesce-guard", mk, re.M), "make up 이 게이트를 건너뛴다"
    assert re.search(r"^down: quiesce-guard", mk, re.M), "make down 이 게이트를 건너뛴다"
    assert "bin/lib/quiesce.sh" in mk, "make 가 배포와 다른 판정을 쓴다"
    assert "FORCE_BUSY" in mk, "탈출구가 없으면 운영자가 raw docker 로 우회한다"


# ── 라이브 검증이 잡은 결함 3건 (전부 실측 기반) ──────────────────────────────

def test_error_messages_have_no_backtick_command_substitution():
    """**라이브 적발**: 큰따옴표 안의 backtick 은 명령 치환이다 — 초판이 `/livez` 를 실제로
    실행하려 했고(`No such file or directory`) 메시지도 깨졌다. 주석은 무해하나 코드 줄은 아니다."""
    lib = _lib_text()
    for i, line in enumerate(lib.split("\n"), 1):
        if line.strip().startswith("#"):
            continue
        if re.search(r'(err|warn|log|step)\s+"[^"]*`', line):
            raise AssertionError(f"quiesce.sh:{i} 메시지에 백틱 명령 치환: {line.strip()}")


def test_exec_failure_is_unknown_not_inprocess():
    """**라이브 적발**: 컨테이너가 재생성 중이면 `exec` 가 실패해 빈 값을 준다. 초판은 그것을
    'env 미설정 = inprocess' 로 읽어 **엉뚱한 사유로** 게이트를 막았다(진단이 오도된다)."""
    lib = _lib_text()
    fn = lib[lib.index("ask_execution_mode()"):]
    fn = fn[:fn.index("\n}\n") + 3]
    assert "rc=$?" in fn, "exec 종료코드를 보지 않는다"
    assert 'if [ "$rc" -ne 0 ]' in fn, "exec 실패와 env 미설정을 구분하지 않는다"


def test_library_initializes_report_vars_for_standalone_use():
    """**라이브 적발**: 단독 source 시 `QUIESCE_FORCED` 가 비어 `quiesce_summary` 가
    `[: : integer expression expected` 로 깨졌다."""
    lib = _lib_text()
    assert ': "${QUIESCE_FORCED:=0}"' in lib
    assert ': "${QUIESCE_REPORT:=}"' in lib
