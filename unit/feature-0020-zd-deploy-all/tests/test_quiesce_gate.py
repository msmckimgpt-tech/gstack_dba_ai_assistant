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


def _script_text() -> str:
    with open(_DEPLOY_SH, "r", encoding="utf-8") as fh:
        return fh.read()


def _extract_quiesce_block() -> str:
    """quiesce 관련 함수만 떼어낸다(스크립트 전체 source 는 main 실행을 유발)."""
    s = _script_text()
    start = s.index("# ── 진행 중 사용자 run 관측")
    end = s.index("wait_ready() {")
    return s[start:end]


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
_POST_STUBS = textwrap.dedent("""\
    ask_execution_mode() { echo "${MODE_STUB:-worker}"; }
    stale_running_ask_jobs() { echo "${STALE_STUB:-0}"; }
    """)


def _run(body: str, env: dict | None = None) -> subprocess.CompletedProcess:
    script = _STUBS + _extract_quiesce_block() + "\n" + _POST_STUBS + body
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=e)


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

def test_worker_gate_precedes_ask_worker_recreate():
    """게이트가 recreate 뒤에 있으면 이미 죽인 뒤다 — 순서가 곧 계약이다."""
    s = _script_text()
    body = s[s.index("deploy_workers() {"):s.index("rollback_workers() {")]
    gate = body.index('quiesce_gate "ask-worker recreate"')
    recreate = body.index("up -d --no-deps --no-build --force-recreate")
    assert gate < recreate, "quiesce 게이트가 ask-worker recreate 뒤에 있다"
    assert 'if [ "$svc" = "ask-worker" ]' in body, \
        "배경 워커(insight/ops)까지 게이트를 걸면 유휴 대기만 늘고 얻는 게 없다"


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
    s = _script_text()
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
    s = _script_text()
    m = re.search(r'QUIESCE_SETTLE="\$\{DEPLOY_QUIESCE_SETTLE:-(\d+)\}"', s)
    assert m, "settle 간격 knob 이 없다"
    assert 0 < int(m.group(1)) <= 30, "settle 은 짧아야 한다(길면 배포가 무의미하게 늘어난다)"
