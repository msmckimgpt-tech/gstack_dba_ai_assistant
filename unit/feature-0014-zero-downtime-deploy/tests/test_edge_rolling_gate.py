"""bin/deploy-web.sh — 엣지(Caddy) 후보 복귀 게이트 회귀 잠금.

배경 (CHG-20260811-edge-rolling-gate):
    "무중단" 롤링이 엣지 관점에서는 성립하지 않고 있었다. 2026-08-11 라이브 실측:

      * Caddy 에러 로그 `no upstreams available` **71건 / 6시간**
      * 배포 창 6회, 각 **12~17초 전면 503**(요청 duration 이 전부 `lb_try_duration`=5.01s
        = 재시도를 다 쓰고 포기)
      * 그 창에서 active health 는 양 replica 모두 `host is up` — 즉 **passive 격리가 유일 원인**
      * 503 종료 시각이 매번 "먼저 내린 replica 의 첫 실패 + fail_duration(30s)" 과 일치

    기전: `recreate_replica` 의 게이트가 **컨테이너 내부 `/readyz`**(앱이 떴다) 까지만 보고,
    **엣지가 그 replica 를 다시 LB 후보로 쓰는지**는 보지 않았다. Caddy 는 실패한 upstream 을
    `fail_duration` 동안 후보에서 뺀다. 롤링 간격(≈10초) < 격리(30초) 이므로 web-a 가 아직
    격리 중인 상태에서 web-b 를 내려 **available upstream 0** 이 됐다.

    자동 게이트가 못 잡은 이유: soak 는 web-b recreate 가 끝난 뒤 시작하고 edge 실패를 "일시
    blip"(EDGE_FLAP_MAX)으로 관용한다. 503 은 격리 타이머로 자연 회복하므로 배포는 매번
    **성공으로 보고**됐다 — 사용자만 아는 무증상 장애였다.

본 스위트가 잠그는 계약 (AGENTS.md §16.7 G10 — 재발 클래스의 구조 가드 승격):
    G1 배선     — `recreate_replica` 가 `wait_edge_available` 을 호출한다(누락 = 재발).
                  호출자(롤링·auto_rollback·--rollback)마다 넣지 않고 recreate 안에 두는
                  구조 자체를 단정한다 — 한 경로만 누락돼도 그 경로에서 503 이 난다.
    G2 파싱     — `edge_upstream_fails` 가 실제 Caddy admin 응답에서 해당 upstream 의 fails 를
                  뽑는다. 다른 upstream 의 값을 오독하지 않고, 형식이 어긋나면 **빈 출력**으로
                  안전 실패한다(→ degrade 경로).
    G3 대기     — fails>0 이면 격리 해제까지 기다리고, 0 이면 즉시 통과한다.
    G4 degrade  — admin API 조회 불가 환경에서도 `fail_duration` 기준 고정 대기로 안전을 유지한다
                  (조회 실패를 "복귀했다"로 오판해 즉시 진행하지 않는다).
    G5 비차단   — 게이트는 배포를 막지 않는다(확인 실패는 경고 후 진행). 배포 가용성 회귀 방지.
    G6 설정정합 — Caddyfile 의 `fail_duration` 이 게이트 상한(EDGE_AVAIL_TIMEOUT)보다 작다.
                  크면 게이트가 timeout 으로 무력화되어 원 결함이 그대로 돌아온다.
    G7 passive  — passive health 설정(max_fails/fail_duration)이 존재한다. 통째로 지우는 것은
                  본 결함의 해법이 아니다(active health 검출 lag 를 메우는 층이 사라진다).
"""

import os
import re
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = REPO_ROOT / "bin" / "deploy-web.sh"
PROBE_LIBRARY = REPO_ROOT / "bin" / "lib" / "caddy-probe.sh"
CADDYFILE = REPO_ROOT / "unit" / "feature-0006-lan-proxy-access" / "src" / "caddy" / "Caddyfile"

LIVE_UPSTREAMS_JSON = (
    '[{"address":"web-a:8000","num_requests":0,"fails":0},'
    '{"address":"web-b:8000","num_requests":0,"fails":0}]'
)


# ── 함수 추출 하네스 ───────────────────────────────────────────────────────────
# deploy-web.sh 는 말미에 `main "$@"` 를 실행하므로 source 할 수 없다(= 실배포). 검증 대상
# 함수만 원문 그대로 뽑아 최소 스텁과 함께 실행한다 — 텍스트 grep 이 아니라 **실제 코드**를
# 돌리므로 파싱·분기 회귀를 잡는다.
def _extract_func(name: str) -> str:
    src = SCRIPT.read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(name)}\(\) \{{.*?^\}}$", src, re.S | re.M)
    assert m, f"{name}() 를 {SCRIPT} 에서 찾지 못했다 — 함수가 사라졌거나 정의 형식이 바뀌었다."
    return m.group(0)


def _mock_docker(tmp_path: Path, *, caddy_running: bool = True, ps_fail: bool = False) -> Path:
    """`docker` 를 가로채는 목 바이너리.

    upstream JSON·라이브 Caddyfile·응답 지연을 env 로 주입한다. `FAKE_HANG` 은 admin API 조회가
    멈추는 상황(적대 검증 P1-1)을 재현해, 게이트가 `timeout` 으로 끊고 빠져나오는지 본다.
    """
    binroot = tmp_path / "mockbin"
    binroot.mkdir(exist_ok=True)
    ps_out = "fake-caddy-cid" if caddy_running else ""
    # f-string 표현식 안에 백슬래시를 두면 **Python 3.11 에서 SyntaxError** 다(PEP 701 은 3.12).
    # CI 러너와 agent 이미지가 모두 3.11 이라, 이 한 줄 때문에 파일 전체가 collection 단계에서
    # 죽어 있었다 — testpaths 에 등재해도, CI 경로에 추가해도 아무것도 지키지 못하는 상태였다
    # (feature-0020, 2026-08-14 발견). 개행을 미리 결합해 f-string 밖으로 뺀다.
    ps_echo = "printf '" + ps_out + "\\n'"
    (binroot / "docker").write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            case "$*" in
              *"ps -q caddy"*) {"exit 1" if ps_fail else ps_echo} ;;
              inspect*) printf 'sha256:fixture-image\\n' ;;
              cp*) python3 -c 'import io, os, sys, tarfile; data=os.environ["FAKE_LIVE_CADDYFILE"].encode(); buf=io.BytesIO(); archive=tarfile.open(fileobj=buf, mode="w"); member=tarfile.TarInfo("Caddyfile"); member.size=len(data); archive.addfile(member, io.BytesIO(data)); archive.close(); sys.stdout.buffer.write(buf.getvalue())' ;;
              *livez*) {"exit 1" if False else 'exit ${FAKE_PEER_LIVE_RC:-0}'} ;;
              *reverse_proxy/upstreams*)
                  [ -n "$FAKE_HANG" ] && sleep "$FAKE_HANG"
                  printf '%s' "$FAKE_UPSTREAMS_JSON" ;;
              *) : ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    (binroot / "docker").chmod(0o755)
    return binroot


def _caddyfile_text(fail_duration_s) -> str:
    inner = f"\t\tfail_duration {fail_duration_s}s\n" if fail_duration_s is not None else ""
    return f"\treverse_proxy web-a:8000 web-b:8000 {{\n{inner}\t\tmax_fails 1\n\t}}\n"


def _run_harness(
    tmp_path: Path,
    body: str,
    *,
    funcs=("caddy_fail_duration_s", "edge_peer_live", "edge_upstream_fails", "wait_edge_available"),
    upstreams_json: str = LIVE_UPSTREAMS_JSON,
    caddy_running: bool = True,
    fail_duration_s=3,
    live_fail_duration_s=None,
    edge_avail_timeout: int = 60,
    degrade_floor: int = 0,
    hang_s: str = "",
    ps_fail: bool = False,
    peer_live_rc: int = 0,
):
    binroot = _mock_docker(tmp_path, caddy_running=caddy_running, ps_fail=ps_fail)
    fake_caddyfile = tmp_path / "Caddyfile"
    fake_caddyfile.write_text(_caddyfile_text(fail_duration_s), encoding="utf-8")
    script = tmp_path / "harness.sh"
    script.write_text(
        "\n".join(
            [
                "set -euo pipefail",
                "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
                "step() { printf '[step] %s\\n' \"$*\" >&2; }",
                "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
                "DRY_RUN=0",
                f'CADDYFILE="{fake_caddyfile}"',
                'CADDY_ADMIN_URL="http://127.0.0.1:2019"',
                f"EDGE_AVAIL_TIMEOUT={edge_avail_timeout}",
                f"EDGE_DEGRADE_FLOOR={degrade_floor}",
                "DC=(docker compose -f docker-compose.yml)",
                f'STATE_DIR="{tmp_path}"',
                f'source "{PROBE_LIBRARY}"',
                'WEB_PUBLIC_HOST="test.local"',
                *[_extract_func(f) for f in funcs],
                body,
            ]
        ),
        encoding="utf-8",
    )
    env = dict(
        os.environ,
        PATH=f"{binroot}:{os.environ['PATH']}",
        FAKE_UPSTREAMS_JSON=upstreams_json,
        FAKE_LIVE_CADDYFILE=(
            _caddyfile_text(live_fail_duration_s) if live_fail_duration_s is not None else ""
        ),
        FAKE_HANG=hang_s,
        FAKE_PEER_LIVE_RC=str(peer_live_rc),
        WEB_PUBLIC_HOST="test.local",
    )
    started = time.monotonic()
    proc = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=env, timeout=180
    )
    return proc, time.monotonic() - started


# ── G1 배선 ────────────────────────────────────────────────────────────────────
def test_g1_recreate_replica_calls_edge_gate():
    """recreate_replica 안에서 엣지 게이트를 부른다 — 호출자별 개별 삽입은 누락에 취약하다."""
    body = _extract_func("recreate_replica")
    assert "wait_edge_available" in body, (
        "recreate_replica 가 wait_edge_available 을 호출하지 않는다. 앱 /readyz 만 게이트하면 "
        "엣지 passive 격리 중인 replica 를 '복귀했다'고 오판해 상대 replica 를 내리고, "
        "available upstream 0 → 전면 503 이 재발한다(2026-08-11 라이브 실측)."
    )
    # 순서 계약: 앱 ready 확인 **뒤**에 엣지 복귀를 본다(반대면 아직 뜨지도 않은 replica 를 기다린다).
    assert body.index("wait_ready") < body.index("wait_edge_available")


def test_g1b_gate_covers_every_recreate_path():
    """롤링·auto_rollback·--rollback 세 경로 모두 recreate_replica 를 경유한다(우회 recreate 금지)."""
    src = SCRIPT.read_text(encoding="utf-8")
    # web replica 를 force-recreate 하는 지점은 recreate_replica 내부와 초기 배포(둘 다 없는 경우) 뿐이어야 한다.
    direct = [
        ln.strip()
        for ln in src.splitlines()
        if "--force-recreate" in ln and ("web-a" in ln or "web-b" in ln) and not ln.strip().startswith("#")
    ]
    assert direct == [], (
        "web replica 를 recreate_replica 밖에서 직접 force-recreate 하는 경로가 있다 — "
        f"그 경로는 엣지 게이트를 우회한다: {direct}"
    )


def test_g1b2_no_replica_recreate_outside_the_gated_helper():
    """web replica 를 recreate 하는 코드는 `recreate_replica` **함수 안**에만 있어야 한다.

    초판은 `--force-recreate` 와 리터럴 `web-a`/`web-b` 가 같은 줄에 있을 때만 봤다. `"$svc"` 를
    쓰는 별도 헬퍼나 `stop`+`up` 조합은 그대로 통과한다(적대 검증 P2). 여기서는 **함수 귀속**으로
    본다 — recreate 계열 명령이 어느 함수 안에 있는지 확인하고 allowlist 와 대조한다.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    # feature-0020 zd-ask-rollout: ask-worker surge 교대 3함수 추가. 이들은 **web replica 를
    # 만지지 않는다**(대상은 ask-worker/ask-worker-surge 뿐) — 즉 이 테스트가 지키는 엣지 게이트의
    # 관할 밖이다. 대신 자기 층의 게이트를 갖는다: surge healthy 확인 → 본체 drain(완주 대기) →
    # 본체 교체. 그 순서는 `test_ask_surge_rollout.py` 가 잠근다.
    # feature-0045 zd-bridge-continuity: 브리지 MCP 표면(`ext-tool-mcp-a/b`) 롤링 함수 추가.
    # 같은 근거로 등재한다 — **web replica 를 만지지 않는다**(대상은 MCP_REPLICAS 뿐). 자기 층의
    # 게이트는 "상대 replica 가 healthy 일 때만 이쪽을 내린다" 이고, 그 전제와 web 미참조는
    # `unit/feature-0045-zd-bridge-continuity/tests/test_bridge_deploy_gate.py` 가 잠근다.
    allowed = {"recreate_replica", "deploy_workers", "rollback_workers", "deploy_gateway_reconcile",
               "reconcile_caddy", "sweep_leaked_surge",
               "rollout_ask_worker_via_surge", "drain_stop_ask", "sweep_leaked_ask_surge",
               "rollout_mcp_replicas"}
    # main 은 통째로 허용하지 않는다 — 초기 dual-start(양 replica 부재 시 동시 기동, 그때는
    # 내릴 상대가 없어 게이트가 무의미) **한 줄만** 예외로 인정한다(적대 검증 P2).
    initial_dual_start = "up -d --no-deps --no-build web-a web-b"
    current = None
    offenders = []
    for ln in src.splitlines():
        m = re.match(r"^([a-z_][a-z0-9_]*)\(\) \{", ln)
        if m:
            current = m.group(1)
        elif ln == "}":
            current = None
        stripped = ln.strip()
        if stripped.startswith("#"):
            continue
        if "--force-recreate" in stripped or re.search(r"\bup -d\b.*--no-build", stripped) \
           or re.search(r"\b(stop|restart)\b.*web-[ab]", stripped):
            if initial_dual_start in stripped:
                continue
            if current not in allowed:
                offenders.append((current, stripped[:90]))
    assert offenders == [], (
        f"게이트가 없는 위치에서 컨테이너를 recreate 한다: {offenders}. "
        "web replica recreate 는 recreate_replica 를 경유해야 엣지 게이트를 탄다."
    )


def _run_predrain(tmp_path: Path, *, peer_cid="peer-cid", peer_ready="1", edge_ok="1"):
    """`predrain` 본문을 원문 그대로 실행한다(스텁 주입). 텍스트 단정으로는 `if false;` 같은
    무력화를 잡지 못해 실행 검증으로 둔다."""
    script = tmp_path / "predrain.sh"
    script.write_text(
        "\n".join([
            "set -euo pipefail",
            "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
            "step() { printf '[step] %s\\n' \"$*\" >&2; }",
            "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
            "err()  { printf '[err] %s\\n' \"$*\" >&2; }",
            "DRY_RUN=0",
            "PREDRAIN_TIMEOUT=5",
            'CADDY_ADMIN_URL="http://127.0.0.1:2019"',
            'replica_cid() { printf \'%s\' "$FAKE_PEER_CID"; }',
            'replica_readyz() { [ "$FAKE_PEER_READY" = "1" ]; }',
            "replica_active_streams() { echo 0; }",
            # feature-0045: predrain 이 브리지 축을 함께 본다. 이 파일이 지키는 계약은
            # **엣지 게이트 3단**(상대 존재·ready·후보 복귀)이므로, 브리지 축은 "조용함" 으로
            # 고정해 그 3단만 남긴다(다른 축의 변화가 이 테스트의 의미를 흐리지 않게).
            "PREDRAIN_FORCED=0", "PREDRAIN_UNVERIFIED=0", 'DRAINED_SVC=""',
            'replica_drain_probe() { echo "0 0 0"; }',
            "replica_active_streams_strict() { echo 0; }",
            "replica_release_drain() { :; }",
            'wait_edge_available() { [ "$FAKE_EDGE_OK" = "1" ]; }',
            _extract_func("predrain"),
            "rc=0; predrain web-a web-b || rc=$?; echo RC=$rc",
        ]),
        encoding="utf-8",
    )
    env = dict(os.environ, FAKE_PEER_CID=peer_cid, FAKE_PEER_READY=peer_ready, FAKE_EDGE_OK=edge_ok)
    return subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env, timeout=60)


def test_g1e_predrain_refuses_when_peer_missing(tmp_path):
    """상대 컨테이너가 없으면 내리지 않는다 — 유일 replica 를 내리는 것이 곧 전면 다운이다.

    초판은 이 검사를 '존재 분기 안' 에 두어 fail-open 이었다(적대 검증 P1). 상대 부재는 초기
    배포가 아니라(main 이 별도 분기로 처리) '한쪽만 살아 있는 비정상 상태' 다.
    """
    proc = _run_predrain(tmp_path, peer_cid="")
    assert "RC=1" in proc.stdout, (
        f"상대 부재인데 predrain 이 통과했다 — 유일 replica 를 내리게 된다. stderr={proc.stderr!r}"
    )
    assert "유일 replica" in proc.stderr


def test_g1e2_predrain_refuses_when_peer_unready(tmp_path):
    """상대가 ready 가 아니면 내리지 않는다 — 경고만 하고 진행하면 healthy upstream 이 0 이 된다."""
    proc = _run_predrain(tmp_path, peer_ready="0")
    assert "RC=1" in proc.stdout, f"상대 unready 인데 통과했다. stderr={proc.stderr!r}"


def test_g1e3_predrain_refuses_when_peer_not_edge_available(tmp_path):
    """상대가 엣지 후보로 복귀하지 않았으면 내리지 않는다(원 사고 기전의 직접 차단)."""
    proc = _run_predrain(tmp_path, edge_ok="0")
    assert "RC=1" in proc.stdout, f"엣지 미복귀인데 통과했다. stderr={proc.stderr!r}"
    assert "available upstream 0" in proc.stderr


def test_g1e4_predrain_proceeds_when_all_three_hold(tmp_path):
    """세 조건이 모두 성립하면 정상 진행한다 — 게이트가 정상 경로를 막으면 배포가 불가능해진다."""
    proc = _run_predrain(tmp_path)
    assert "RC=0" in proc.stdout, f"정상 조건인데 차단됐다. stderr={proc.stderr!r}"


def test_g1c_predrain_is_the_fail_closed_gate():
    """predrain 이 상대의 엣지 복귀를 fail-closed 로 확인한다 — 여기가 '내려도 되는가' 의 결정 지점."""
    body = _extract_func("predrain")
    assert "wait_edge_available" in body, (
        "predrain 이 상대 replica 의 엣지 복귀를 확인하지 않는다. recreate 말미의 선제 대기만으로는 "
        "그 대기가 timeout 된 뒤 그대로 다음 replica 를 내려 전면 503 이 재현된다."
    )
    assert "return 1" in body, "predrain 이 게이트 실패를 호출자에게 알리지 않는다(fail-closed 아님)."


def test_g1d_predrain_failure_aborts_the_rollout():
    """predrain 이 1 을 반환하면 롤링이 **중단**된다 — 강행하면 우리가 고치려는 장애가 그대로 난다."""
    src = SCRIPT.read_text(encoding="utf-8")
    calls = [
        ln.strip()
        for ln in src.splitlines()
        if re.match(r"^\s*predrain\s+web-[ab]\s+web-[ab]", ln)
    ]
    assert len(calls) == 2, f"롤링의 predrain 호출이 2개가 아니다: {calls}"
    for ln in calls:
        assert "|| die" in ln, (
            f"predrain 실패가 무시된다: {ln!r} — 반환값을 버리면 fail-closed 게이트가 무력화된다."
        )


# ── G2 파싱 ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "svc,json_text,expected",
    [
        ("web-a", LIVE_UPSTREAMS_JSON, "0"),                                        # 라이브 실측 형식
        ("web-b", '[{"address":"web-a:8000","num_requests":0,"fails":0},'
                  '{"address":"web-b:8000","num_requests":3,"fails":2}]', "2"),      # 상대 upstream 오독 방지
        ("web-a", '[{"address":"web-a:8000","num_requests":0,"fails":11}]', "11"),   # 두 자리
        ("web-a", '[ { "address": "web-a:8000", "fails": 5 } ]', "5"),               # 공백 포함 JSON
        ("web-c", LIVE_UPSTREAMS_JSON, ""),                                          # 미검출 → 안전 실패
        ("web-a", "", ""),                                                           # 빈 응답 → 안전 실패
        ("web-a", '[{"address":"web-a:8000","num_requests":0}]', ""),                # fails 키 부재
        ("web-a", '[{"fails":9,"address":"web-a:8000"},'
                  '{"address":"web-b:8000","fails":0}]', ""),                        # 필드 순서 역전 → 오독 대신 빈값
    ],
)
def test_g2_edge_upstream_fails_parsing(tmp_path, svc, json_text, expected):
    proc, _ = _run_harness(
        tmp_path,
        f'printf "[%s]" "$(edge_upstream_fails {svc})"',
        funcs=("edge_upstream_fails",),
        upstreams_json=json_text,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"[{expected}]", f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


# ── G3 대기 / G5 비차단 ────────────────────────────────────────────────────────
def test_g3_returns_immediately_when_edge_clear(tmp_path):
    """fails=0 이면 즉시 통과한다 — 정상 경로에 배포 지연을 만들지 않는다."""
    proc, elapsed = _run_harness(tmp_path, "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc")
    assert proc.returncode == 0, proc.stderr
    assert "RC=0" in proc.stdout
    assert "fails=0" in proc.stderr
    assert elapsed < 5, f"fails=0 인데 {elapsed:.1f}s 대기했다(정상 경로 지연)."


def test_g3b_observed_isolation_that_never_clears_reports_failure(tmp_path):
    """격리를 **관측**했는데 상한까지 안 풀리면 1 을 반환한다 — 호출자(predrain)가 중단할 수 있게.

    초판은 여기서 0 을 반환했고, 그러면 게이트가 timeout 된 뒤 그대로 다음 replica 를 내려
    방지하려던 전면 503 이 그대로 재현된다(적대 검증 P1).
    """
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json='[{"address":"web-a:8000","num_requests":0,"fails":2}]',
        edge_avail_timeout=3,
    )
    assert "RC=1" in proc.stdout, (
        "격리가 관측된 채 timeout 인데 성공(0)을 반환했다 — 호출자가 그대로 다음 replica 를 내린다."
    )
    assert "fails=2" in proc.stderr
    assert elapsed >= 3, f"격리(fails=2) 중인데 {elapsed:.1f}s 만에 반환했다 — 대기가 실효하지 않는다."


def test_g5_recreate_does_not_abort_on_gate_miss(tmp_path):
    """recreate_replica 말미의 대기는 **비차단**이다 — 롤백 경로가 게이트 때문에 멈추면 안 된다."""
    body = _extract_func("recreate_replica")
    gate_line = [ln for ln in body.splitlines() if "wait_edge_available" in ln and not ln.strip().startswith("#")]
    assert gate_line, "recreate_replica 에 엣지 대기가 없다."
    assert "|| warn" in gate_line[0] or "|| true" in gate_line[0], (
        f"recreate_replica 의 엣지 대기가 실패를 그대로 전파한다: {gate_line[0]!r} — "
        "롤백(auto_rollback/--rollback)도 이 함수를 타므로 여기서 끊으면 롤백이 중단된다. "
        "차단 판단은 predrain 이 한다."
    )
    assert body.rstrip().endswith("return 0\n}") or "return 0" in body.splitlines()[-2], (
        "recreate_replica 가 게이트 결과를 반환값으로 흘린다 — 마지막 replica 에서 과잉 롤백을 유발한다."
    )


# ── G4 degrade ─────────────────────────────────────────────────────────────────
def test_g4_degrades_to_fixed_wait_when_admin_unreachable(tmp_path):
    """admin API 조회 불가 → '복귀했다'로 오판하지 않고 fail_duration 기준으로 기다린다."""
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json="",           # admin 응답 없음
        fail_duration_s=2,           # degrade 대기 = 2 + 2 = 4s
    )
    assert proc.returncode == 0, proc.stderr
    assert "RC=0" in proc.stdout
    assert "조회 불가" in proc.stderr and "고정 대기" in proc.stderr
    assert elapsed >= 4, (
        f"admin 조회 불가인데 {elapsed:.1f}s 만에 통과했다 — 조회 실패를 복귀로 오판하면 "
        "게이트가 무증상으로 사라진다."
    )


def test_g4b_fail_duration_parsed_from_caddyfile(tmp_path):
    """degrade 대기량은 Caddyfile 실값에서 온다 — 설정이 늘어나면 대기도 함께 늘어야 한다."""
    proc, _ = _run_harness(
        tmp_path, "caddy_fail_duration_s", funcs=("caddy_fail_duration_s",), fail_duration_s=17
    )
    assert proc.stdout.strip() == "17", proc.stdout


def test_g4b2_fail_duration_falls_back_conservatively(tmp_path):
    """파싱 불가면 **관측된 최악값(30)** 으로 떨어진다 — 0/빈값이면 degrade 대기가 통째로 사라진다.

    초판 테스트는 harness 가 Caddyfile 을 다시 덮어써 fallback 을 실제로 타지 않았고, 기대값에
    17 을 허용해 fallback 을 지워도 통과했다(적대 검증 P2-3). 여기서는 fail_duration 지시어가
    아예 없는 Caddyfile 을 harness 로 주입하고 30 만 허용한다.
    """
    proc, _ = _run_harness(
        tmp_path,
        "caddy_fail_duration_s",
        funcs=("caddy_fail_duration_s",),
        fail_duration_s=None,          # repo Caddyfile 에 지시어 없음
        live_fail_duration_s=None,     # 라이브도 조회 불가
    )
    assert proc.stdout.strip() == "30", (
        f"파싱 불가 fallback 이 {proc.stdout.strip()!r} — 30(보수적 상한)이어야 한다. "
        "여기가 0/빈값이 되면 degrade 경로의 대기가 사라져 게이트가 무증상으로 무력화된다."
    )


def test_g4b3_live_caddy_config_wins_when_larger(tmp_path):
    """degrade 기준은 repo 소스가 아니라 **실행 중 Caddy 와의 max** 다.

    이 변경을 처음 배포하는 창에서는 라이브 Caddy 가 아직 옛 설정(더 긴 fail_duration)으로 돌고
    repo 만 새 값이다. repo 값만 믿으면 덜 기다려 원 503 이 그대로 재발한다(적대 검증 P1-3).
    """
    proc, _ = _run_harness(
        tmp_path,
        "caddy_fail_duration_s",
        funcs=("caddy_fail_duration_s",),
        fail_duration_s=3,             # repo = 새 값(짧음)
        live_fail_duration_s=30,       # 라이브 = 옛 값(김)
    )
    assert proc.stdout.strip() == "30", (
        f"라이브(30s)보다 짧은 repo 값({proc.stdout.strip()})을 채택했다 — 배포 창에서 덜 기다린다."
    )
    # 반대 방향도: repo 가 더 크면 repo 를 택한다(설정을 늘리는 배포에서 미리 안전).
    proc2, _ = _run_harness(
        tmp_path,
        "caddy_fail_duration_s",
        funcs=("caddy_fail_duration_s",),
        fail_duration_s=45,
        live_fail_duration_s=30,
    )
    assert proc2.stdout.strip() == "45", proc2.stdout


def test_g4c2_hanging_admin_api_cannot_stall_the_deploy(tmp_path):
    """admin API 가 응답 없이 멈춰도 게이트는 상한 내에 빠져나온다.

    `docker compose exec ... wget` 이 무한 대기하면 while 루프가 deadline 을 재검사하지 못해
    **배포가 flock 을 쥔 채 무기한 정지**한다(적대 검증 P1-1). timeout 2겹(wget -T / exec 전체)이
    그 경로를 끊는지 실제 hang 을 재현해 확인한다.
    """
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        hang_s="60",                   # admin 조회가 60초 멈춘 상황
        fail_duration_s=1,             # degrade 대기 = 1 + 2 = 3s
        live_fail_duration_s=None,
        edge_avail_timeout=5,
    )
    assert "RC=" in proc.stdout, f"게이트가 반환하지 않았다(stdout={proc.stdout!r})."
    assert elapsed < 45, (
        f"admin API hang 60s 인데 게이트가 {elapsed:.1f}s 걸렸다 — timeout 이 끊지 못하면 "
        "배포가 락을 쥔 채 정지한다."
    )


def test_g4c_skips_when_caddy_absent(tmp_path):
    """caddy 미기동이면 게이트는 무의미하므로 즉시 skip(첫 기동 경로를 지연시키지 않는다)."""
    proc, elapsed = _run_harness(
        tmp_path, "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc", caddy_running=False, fail_duration_s=20
    )
    assert "RC=0" in proc.stdout
    assert "skip" in proc.stderr
    assert elapsed < 5, f"caddy 부재인데 {elapsed:.1f}s 대기했다."


# ── G6·G7 설정 정합 ────────────────────────────────────────────────────────────
def _caddy_directive(name: str) -> int:
    m = re.search(rf"^\s*{name}\s+(\d+)s?\s*$", CADDYFILE.read_text(encoding="utf-8"), re.M)
    assert m, f"Caddyfile 에 {name} 지시어가 없다."
    return int(m.group(1))


def _script_default(var: str) -> int:
    m = re.search(rf'^{var}="\$\{{[A-Z_]+:-(\d+)\}}"', SCRIPT.read_text(encoding="utf-8"), re.M)
    assert m, f"deploy-web.sh 에 {var} 기본값이 없다."
    return int(m.group(1))


def test_g6_fail_duration_within_gate_budget():
    """fail_duration 이 게이트 상한을 넘으면 게이트가 timeout 으로 무력화되어 원 결함이 돌아온다."""
    fail_duration = _caddy_directive("fail_duration")
    budget = _script_default("EDGE_AVAIL_TIMEOUT")
    assert fail_duration < budget, (
        f"Caddyfile fail_duration={fail_duration}s 가 EDGE_AVAIL_TIMEOUT={budget}s 이상이다. "
        "격리가 게이트 상한보다 길면 게이트는 매번 timeout 경고만 내고 통과하며, "
        "롤링이 격리 중인 replica 위에서 상대를 내려 전면 503 이 재발한다."
    )


def test_g6b_gate_budget_covers_isolation_with_margin():
    """게이트 상한이 격리 기간을 **여유 있게** 덮어야 degrade 대기(fail_duration+2)도 안에 들어온다."""
    fail_duration = _caddy_directive("fail_duration")
    budget = _script_default("EDGE_AVAIL_TIMEOUT")
    assert budget >= fail_duration + 5, (
        f"EDGE_AVAIL_TIMEOUT={budget}s 가 fail_duration={fail_duration}s + 여유(5s)에 못 미친다. "
        "격리가 정상적으로 풀리는 경우에도 게이트가 먼저 만료되어 매 배포가 fail-closed 중단된다."
    )


def test_g7_passive_health_still_configured():
    """passive 를 통째로 지우는 것은 해법이 아니다 — 검출 공백이 생긴다."""
    text = CADDYFILE.read_text(encoding="utf-8")
    assert re.search(r"^\s*max_fails\s+\d+\s*$", text, re.M), "max_fails 가 사라졌다."
    assert re.search(r"^\s*fail_duration\s+\d+s\s*$", text, re.M), "fail_duration 이 사라졌다."


def test_g4d_degrade_wait_has_a_conservative_floor(tmp_path):
    """degrade 대기에는 floor 가 있다 — 파일 값은 '런타임 값' 이 아니기 때문.

    bind mount 파일이 새 값으로 갱신돼도 Caddy 프로세스는 reload 전까지 옛 값으로 돈다. admin 을
    못 읽는 상황에서는 런타임 값을 확인할 수단이 없으므로 관측된 최악값 이상을 기다려야 한다
    (적대 검증 P1). 덜 기다린 대가는 전면 503, 더 기다린 대가는 배포 지연 — 비대칭이 명백하다.
    """
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json="",
        fail_duration_s=1,      # 파일은 1s 라고 말하지만
        degrade_floor=6,        # floor 가 6s 를 강제 → 8s 대기
    )
    assert "RC=0" in proc.stdout
    assert "floor=6s" in proc.stderr, f"floor 가 로그에 표면화되지 않았다: {proc.stderr!r}"
    assert elapsed >= 8, (
        f"floor=6 인데 {elapsed:.1f}s 만 기다렸다 — 파일 값(1s)만 믿으면 런타임이 옛 설정일 때 "
        "덜 기다려 원 503 이 재발한다."
    )
    assert _script_default("EDGE_DEGRADE_FLOOR") >= 30, (
        "운영 기본 floor 가 30s 미만이다 — 관측된 최악 fail_duration 이 30s 였다."
    )


def test_g4e_ps_failure_is_not_read_as_caddy_absent(tmp_path):
    """`docker compose ps` 실패를 '캐디 없음' 으로 읽지 않는다 — 그러면 stall 이 게이트 우회가 된다."""
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        ps_fail=True,
        upstreams_json="",
        fail_duration_s=1,
        degrade_floor=4,
    )
    assert "RC=1" in proc.stdout, "Caddy 조회 실패로 실제 도달성도 확인하지 못했으면 복귀로 처리하지 않는다."
    assert "단정하지 않고" in proc.stderr, (
        f"ps 조회 실패를 미기동으로 처리했다(즉시 통과) — {proc.stderr!r}"
    )
    assert elapsed >= 6, f"조회 실패인데 {elapsed:.1f}s 만에 통과했다 — 게이트가 우회됐다."


def _run_recreate(tmp_path: Path, *, gate_rc="1"):
    """`recreate_replica` 본문을 실행해 (a) 엣지 대기를 **실제로 호출**하는지, (b) 그 실패가
    반환값으로 새지 않는지(비차단)를 본다. 텍스트 단정은 `: || wait_edge_available` 같은
    무력화를 잡지 못한다."""
    marker = tmp_path / "gate-calls"
    script = tmp_path / "recreate.sh"
    script.write_text(
        "\n".join([
            "set -euo pipefail",
            "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
            "step() { printf '[step] %s\\n' \"$*\" >&2; }",
            "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
            "err()  { printf '[err] %s\\n' \"$*\" >&2; }",
            "DRY_RUN=0",
            "READY_TIMEOUT=1",
            "DC_PROD=(true)",
            "run() { \"$@\"; }",
            "wait_ready() { return 0; }",
            # feature-0045: recreate 성공 시 드레인 추적 전역을 비운다(누수 차단). 이 하네스는
            # 그 전역을 쓰지 않으므로 `set -u` 를 만족시킬 초기값만 준다.
            'DRAINED_SVC=""',
            "stamp_sanctioned_recreate() { :; }",
            f'wait_edge_available() {{ echo CALLED >> "{marker}"; return {gate_rc}; }}',
            _extract_func("recreate_replica"),
            "rc=0; recreate_replica web-a deadbeef || rc=$?; echo RC=$rc",
        ]),
        encoding="utf-8",
    )
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=60)
    calls = marker.read_text().count("CALLED") if marker.exists() else 0
    return proc, calls


def test_g5b_recreate_actually_invokes_the_gate_and_stays_nonblocking(tmp_path):
    """recreate 말미의 선제 대기가 **실제로 호출**되고, 그 실패가 반환값으로 새지 않는다."""
    proc, calls = _run_recreate(tmp_path, gate_rc="1")
    assert calls == 1, (
        f"엣지 대기가 호출되지 않았다(calls={calls}) — 다음 predrain 이 매번 격리 해제를 처음부터 "
        "기다리게 되어 배포가 느려지고, 게이트 배선이 텍스트로만 남는다."
    )
    assert "RC=0" in proc.stdout, (
        f"게이트 실패가 recreate 의 반환값으로 샜다(stdout={proc.stdout!r}) — 롤백 경로도 이 함수를 "
        "타므로 롤백이 중단된다. 차단 판단은 predrain 한 곳이 한다."
    )


def test_g8_gate_requires_active_reachability_not_just_fails_zero(tmp_path):
    """`fails==0` 만으로 통과시키지 않는다 — Caddy→replica 실도달까지 봐야 한다.

    passive 카운터가 0 이어도 active health 가 그 replica 를 제외했을 수 있다(컨테이너 내부
    `/readyz` 는 200 이고 fails 도 0 인데 Caddy→replica 도달이 끊긴 상태). 그 상대를 믿고 다음
    replica 를 내리면 다시 upstream 0 이 된다(적대 검증 P1, 3R).
    """
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json=LIVE_UPSTREAMS_JSON,   # fails=0
        peer_live_rc=1,                        # 그러나 Caddy→web-a /livez 는 실패
        edge_avail_timeout=3,
    )
    assert "RC=1" in proc.stdout, (
        f"fails=0 만 보고 통과했다 — active health 제외 상태를 복귀로 오판한다. stderr={proc.stderr!r}"
    )
    assert "미응답" in proc.stderr


def test_g8b_gate_passes_when_both_axes_hold(tmp_path):
    """두 축(fails=0 + 실도달)이 모두 성립하면 즉시 통과한다 — 정상 경로를 막지 않는다."""
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json=LIVE_UPSTREAMS_JSON,
        peer_live_rc=0,
    )
    assert "RC=0" in proc.stdout, proc.stderr
    assert "/livez 200" in proc.stderr
    assert elapsed < 5, f"정상 경로인데 {elapsed:.1f}s 걸렸다."


# ── 4R 지적 대응 ────────────────────────────────────────────────────────────────
def test_g9_peer_probe_matches_caddy_transport_no_http_fallback():
    """peer probe 는 Caddy 와 같은 조건(https)으로만 붙는다 — http 폴백은 false-pass 를 만든다.

    Caddyfile 의 transport 는 `tls` 고정이라 엣지는 https 로만 붙는다. web 이 TLS 없이 같은 포트에
    HTTP 로 떴다면 Caddy 는 그 replica 를 제외하는데, http 로 폴백하는 probe 는 200 을 받아
    "복귀했다" 고 오판한다(적대 검증 P1, 4R).
    """
    body = _extract_func("edge_peer_live")
    assert "https://" in body, "peer probe 가 https 로 붙지 않는다."
    assert "http://" not in body.replace("https://", ""), (
        "peer probe 에 http 폴백이 있다 — Caddy 가 TLS 로 제외한 replica 를 통과시킨다."
    )
    assert "Host: $WEB_PUBLIC_HOST" in body, (
        "probe Host 가 공개 호스트가 아니다 — 앱 TrustedHost 가 내부 서비스명을 400 거부하므로 "
        "Caddy 의 실제 프로브 조건과 어긋난다."
    )


def test_g9b_all_container_probes_have_kill_after():
    """`timeout` 은 기본 TERM 만 보낸다 — TERM 을 무시하는 자식에는 상한이 강제되지 않는다.

    `docker compose exec` 가 TERM 에 반응하지 않으면 배포가 그대로 멈춘다(적대 검증 P1, 4R).
    컨테이너를 찌르는 모든 조회에 `-k`(kill-after)가 붙어 있어야 한다.
    """
    src = SCRIPT.read_text(encoding="utf-8") + "\n" + PROBE_LIBRARY.read_text(encoding="utf-8")
    bare = [
        ln.strip() for ln in src.splitlines()
        if re.search(r"\btimeout\s+\d", ln) and not re.search(r"\btimeout\s+-k\s", ln)
        and not ln.strip().startswith("#")
    ]
    assert bare == [], f"kill-after 없는 timeout 이 있다(TERM 무시 시 상한 미강제): {bare}"


def test_g9c_degrade_path_still_checks_reachability(tmp_path):
    """degrade(고정 대기) 후에도 실도달을 확인한다 — 대기만 하고 통과하면 active 축이 우회된다.

    admin 조회 실패와 Caddy→replica 연결 실패는 서로 다른 고장이다. 전자만 보고 통과시키면
    "admin 은 죽었고 replica 도 도달 불가" 인 조합에서 predrain 이 통과한다(적대 검증 P1, 4R).
    """
    proc, elapsed = _run_harness(
        tmp_path,
        "rc=0; wait_edge_available web-a || rc=$?; echo RC=$rc",
        upstreams_json="",      # admin 조회 불가 → degrade
        peer_live_rc=1,         # 그리고 Caddy→web-a 도달도 실패
        fail_duration_s=1,
        degrade_floor=2,
    )
    assert "RC=1" in proc.stdout, (
        f"degrade 후 실도달 확인 없이 통과했다 — active 축 우회. stderr={proc.stderr!r}"
    )
    assert "미응답" in proc.stderr


def test_g9d_initial_dual_start_guard_separates_query_failure():
    """양 replica '부재' 판정은 조회 **성공** 을 전제한다 — 조회 실패를 부재로 읽으면 동시 recreate.

    `if [ -z "$(replica_cid web-a)" ] && [ -z "$(replica_cid web-b)" ]` 형태는 조회 실패도 빈
    문자열이라 "초기 배포" 로 오인하고 **양 replica 를 동시에** 올린다(= 전면 다운). `if` 조건
    안이라 set -e 도 막지 않는다(적대 검증 P1, 4R).
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r'if \[ -z "\$\(replica_cid web-a\)" \]', src), (
        "초기 배포 분기가 replica_cid 를 조건 안에서 직접 호출한다 — 조회 실패가 부재로 둔갑한다."
    )
    m = re.search(r'_cid_a="\$\(replica_cid web-a\)"[^\n]*', src)
    assert m and "|| die" in m.group(0), f"web-a 조회 실패를 중단으로 처리하지 않는다: {m.group(0) if m else None}"
    m2 = re.search(r'_cid_b="\$\(replica_cid web-b\)"[^\n]*', src)
    assert m2 and "|| die" in m2.group(0), "web-b 조회 실패를 중단으로 처리하지 않는다."


def test_g10_replicas_share_a_single_cert_source():
    """양 replica 가 **같은 cert 소스**를 쓴다 — `edge_peer_live` 의 CA 갭 수용 근거가 이 전제다.

    probe 는 busybox wget 제약으로 CA 를 검증하지 못한다(5R 적대 검증 P1). 그 갭이 실제 위험이
    되려면 "Caddy 는 CA 검증 실패로 제외했는데 probe 만 200" 이어야 하고, 그건 **replica 마다 다른
    leaf** 를 제시할 때만 성립한다. 이 구성은 두 replica 가 동일 `certs` 마운트 + 동일
    `WEB_TLS_CERT_FILE` 을 쓰므로 성립하지 않는다(cert 교체 시 양쪽이 동시에 영향을 받고, 그 축은
    `preflight_tls` 가 배포 전에 ABORT 한다).

    누군가 replica 별 cert 를 도입하면 그 논거가 무너지므로 여기서 전제를 잠근다.
    """
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    m = re.search(r"^x-web-extra:.*?(?=^services:)", compose, re.S | re.M)
    assert m, "x-web-extra anchor 를 찾지 못했다 — web replica 정의 구조가 바뀌었다."
    block = m.group(0)
    assert block.count("certs:/certs:ro") == 1, (
        "web replica 의 cert 마운트가 단일 공유 소스가 아니다. replica 별 cert 를 쓰면 "
        "edge_peer_live 의 CA 미검증 갭이 실제 false-pass 위험이 된다 — probe 를 CA 검증 가능한 "
        "수단으로 바꾸거나 게이트를 보강해야 한다."
    )
    # web-a/web-b 는 이 anchor 를 그대로 병합할 뿐 자체 cert 를 두지 않는다.
    svc = re.search(r"^  web-a:\n(.*?)^  caddy:", compose, re.S | re.M)
    assert svc, "web-a 서비스 정의를 찾지 못했다."
    assert "WEB_TLS_CERT_FILE" not in svc.group(1), (
        "web-a/web-b 가 replica 별 cert 를 지정한다 — 위 전제가 깨졌다."
    )
