"""feature-0045 — 배포 스파인이 브리지 축을 실제로 보고 기다리는지.

이 파일의 테스트는 대부분 **원문을 실행**한다. 텍스트 단정만으로는 `if false;` 나 상수
치환 같은 무력화를 잡지 못하고, 이 게이트의 결함은 조용하다 — 배포는 성공으로 끝나고
사용자만 답을 못 받는다.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPINE = REPO_ROOT / "bin" / "deploy-web.sh"
QUIESCE = REPO_ROOT / "bin" / "lib" / "quiesce.sh"


def _extract_func(name: str, src: str | None = None) -> str:
    text = src if src is not None else SPINE.read_text(encoding="utf-8")
    start = text.index(f"\n{name}() {{")
    end = text.index("\n}\n", start) + len("\n}\n")
    return text[start:end]


# ── pre-drain 이 브리지 in-flight 를 기다리는가 (실행 검증) ─────────────────

def _run_predrain(tmp_path: Path, probe_seq: list[str], *, timeout_s: int = 6):
    """`predrain` 원문을 스텁과 함께 실행한다. `probe_seq` 는 호출마다 돌려줄 probe 출력
    ("<active_streams> <bridge_inflight> <bridge_waiters>") 목록이다."""
    seq = tmp_path / "seq"
    seq.write_text("\n".join(probe_seq) + "\n", encoding="utf-8")
    cnt = tmp_path / "probe-count"
    cnt.write_text("0", encoding="utf-8")
    script = tmp_path / "predrain.sh"
    # ⚠ probe 호출은 명령 치환(`$(...)`) 안에서 일어나 **서브셸**이다 — 셸 변수로 세면 부모에
    #   반영되지 않아 항상 0 이 된다(이 하네스의 실제 함정이었다). 파일로 센다.
    script.write_text(
        "\n".join([
            "set -uo pipefail",
            "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
            "step() { printf '[step] %s\\n' \"$*\" >&2; }",
            "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
            "err()  { printf '[err] %s\\n' \"$*\" >&2; }",
            "DRY_RUN=0",
            f"PREDRAIN_TIMEOUT={timeout_s}",
            "PREDRAIN_FORCED=0",
            'CADDY_ADMIN_URL="http://127.0.0.1:2019"',
            'replica_cid() { echo "cid-$1"; }',
            "replica_readyz() { return 0; }",
            "wait_edge_available() { return 0; }",
            "replica_active_streams() { echo 0; }",
            'replica_drain_probe() {',
            f'  local n; n=$(( $(cat {cnt}) + 1 )); echo "$n" > {cnt}',
            f'  local line; line="$(sed -n "${{n}}p" {seq})"',
            f'  [ -n "$line" ] || line="$(tail -1 {seq})"',
            '  printf "%s" "$line"',
            '}',
            _extract_func("predrain"),
            "rc=0; predrain web-a web-b || rc=$?",
            f'echo "RC=$rc FORCED=$PREDRAIN_FORCED PROBES=$(cat {cnt})"',
        ]),
        encoding="utf-8",
    )
    return subprocess.run(["bash", str(script)], capture_output=True, text=True,
                          env=dict(os.environ), timeout=90)


def test_predrain_waits_for_bridge_tool_calls(tmp_path):
    """진행 중인 개인 AI 왕복이 끝날 때까지 replica 를 내리지 않는다.

    종전 게이트는 `active_streams` 만 봤고, 그 카운터는 브리지 도구 호출을 세지 않는다 —
    즉 **사용자가 답을 기다리는 중에도 '조용함(0)'** 으로 읽고 그대로 내렸다.
    """
    # 루프 간격이 3초이므로 상한을 넉넉히 준다 — 여기서 보려는 것은 "기다리는가" 이지
    # "얼마나 빨리 포기하는가" 가 아니다(그건 아래 강행 테스트가 본다).
    proc = _run_predrain(tmp_path, ["0 2 1", "0 1 1", "0 0 1"], timeout_s=12)
    assert "RC=0" in proc.stdout, f"조용해졌는데 통과하지 못했다. stderr={proc.stderr!r}"
    assert "FORCED=0" in proc.stdout, "정상 드레인인데 강행으로 기록됐다"
    assert "PROBES=3" in proc.stdout, (
        f"in-flight 가 남아 있는데 기다리지 않았다(probe 1회로 통과). stdout={proc.stdout!r}")
    assert "bridge_inflight" in proc.stderr, "무엇을 기다리는지 로그에 남지 않는다"


def test_predrain_does_not_wait_for_waiters(tmp_path):
    """대기(waiters)는 기다리지 않는다 — 드레인 신호로 즉시 비고, 기다리면 배포가 매번
    최대 55초씩 늦어진다(연결이 여럿이면 그만큼 겹친다)."""
    proc = _run_predrain(tmp_path, ["0 0 7"])
    assert "RC=0" in proc.stdout, f"대기만 남았는데 통과하지 못했다. stderr={proc.stderr!r}"
    assert "PROBES=1" in proc.stdout, "대기를 기다리느라 폴링을 반복했다"


def test_predrain_records_forced_when_it_gives_up(tmp_path):
    """상한을 넘겨 강행했으면 **그 사실이 기록**되어야 한다.

    이 플래그가 곧 배포 말미 점유 회수(`reclaim_bridge_claims`)의 발동 조건이다. 기록하지
    않으면 끊긴 작업이 30분 lease 동안 "가져갔는데 답이 없는" 상태로 갇힌다.
    """
    proc = _run_predrain(tmp_path, ["0 3 0"], timeout_s=2)
    assert "RC=0" in proc.stdout, "강행은 중단이 아니라 진행이다(구버전 유지가 아님)"
    assert "FORCED=1" in proc.stdout, f"강행이 기록되지 않았다. stdout={proc.stdout!r}"
    assert "timeout" in proc.stderr


def _run_predrain_fallback(tmp_path: Path, strict_body: str, *, timeout_s: int = 4):
    """드레인 probe 가 실패할 때의 대체 판정을 원문으로 실행한다."""
    script = tmp_path / "fallback.sh"
    script.write_text(
        "\n".join([
            "set -uo pipefail",
            "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
            "step() { :; }", "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
            "err()  { printf '[err] %s\\n' \"$*\" >&2; }",
            "DRY_RUN=0", f"PREDRAIN_TIMEOUT={timeout_s}",
            "PREDRAIN_FORCED=0", "PREDRAIN_UNVERIFIED=0",
            'replica_cid() { echo "cid-$1"; }',
            "replica_readyz() { return 0; }",
            "wait_edge_available() { return 0; }",
            "replica_drain_probe() { return 1; }",
            f"replica_active_streams_strict() {{ {strict_body}; }}",
            "replica_active_streams() { echo 0; }",
            _extract_func("predrain"),
            "rc=0; predrain web-a web-b || rc=$?",
            'echo "RC=$rc FORCED=$PREDRAIN_FORCED UNVERIFIED=$PREDRAIN_UNVERIFIED"',
        ]),
        encoding="utf-8",
    )
    return subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=90)


def test_predrain_fallback_uses_the_strict_probe(tmp_path):
    """probe 실패 시 기존 게이트로 대체하되, **fail-open 헬퍼는 쓰지 않는다**.

    `replica_active_streams` 는 조회 실패도 0 으로 돌려준다. 드레인 중 `/livez` 는 우리가
    만든 503 이라 그 조회는 항상 실패한다 — 즉 "드레인을 걸고 나면 대체 게이트가 항상 통과"
    라는 최악의 조합이 된다. strict(실패를 비-0 종료로 구분)를 쓰고, 통과했더라도 브리지 축을
    확인하지 못한 사실을 기록한다.
    """
    proc = _run_predrain_fallback(tmp_path, "echo 0")
    assert "RC=0" in proc.stdout, f"조용한데 진행하지 못했다. stderr={proc.stderr!r}"
    assert "UNVERIFIED=1" in proc.stdout, (
        f"드레인을 못 건 채 진행한 사실이 기록되지 않았다. stdout={proc.stdout!r}")
    assert "브리지 축은 미확인" in proc.stderr


def test_predrain_fallback_waits_when_it_cannot_read_either(tmp_path):
    """둘 다 못 읽으면 **기다린다** — '조용한지 알 수 없다' 를 '조용하다' 로 읽지 않는다."""
    proc = _run_predrain_fallback(tmp_path, "return 3", timeout_s=4)
    assert "FORCED=1" in proc.stdout, (
        f"관측 불가인데 즉시 통과했다(vacuous pass). stdout={proc.stdout!r}")
    assert "미확인/비-0" in proc.stderr


# ── 드레인 제어 창구 ─────────────────────────────────────────────────────────

def test_drain_probe_does_not_read_livez():
    """드레인 중 `/livez` 는 **503** 이다(그것이 Caddy 를 후보에서 빼는 수단이다).

    같은 창구로 카운터를 읽으면 게이트가 자기가 만든 503 에 걸려 조회 실패로 읽는다.
    """
    body = _extract_func("replica_drain_probe")
    assert "/internal/bridge-drain" in body
    assert "/livez" not in body, (
        "드레인 probe 가 /livez 를 읽는다 — 드레인을 켠 순간 자기 조회가 깨진다")


def test_failed_recreate_releases_the_drain():
    """recreate 가 실패하면 구 프로세스가 **드레인된 채로 살아남는다**(문이 닫힌 replica).

    그대로 두면 다음 배포가 상대를 내리는 순간 available upstream 이 0 이 된다.
    """
    src = SPINE.read_text(encoding="utf-8")
    for svc in ("web-a", "web-b"):
        line = next(l for l in src.splitlines()
                    if f"recreate_replica {svc} " in l and "||" in l)
        assert f"replica_release_drain {svc}" in line, (
            f"{svc} recreate 실패 경로가 드레인을 되돌리지 않는다: {line.strip()[:120]}")
    assert "clear_stale_drain" in src, "롤링 시작 전 잔존 드레인 청소가 없다"


def test_reclaim_runs_only_after_a_forced_predrain():
    """평상시에는 점유를 건드리지 않는다 — 정상 진행 중인 작업을 재노출하면 하나뿐인
    연결이 자기가 처리 중인 질문을 다시 가져가는 중복이 생긴다."""
    body = _extract_func("reclaim_bridge_claims")
    assert '[ "$PREDRAIN_FORCED" -gt 0 ] || [ "$PREDRAIN_UNVERIFIED" -gt 0 ] || return 0' in body, (
        "강행·미확인 여부와 무관하게 회수가 돈다")
    assert "grace_sec=60" in body, "배포 직후 막 시작된 정상 작업까지 회수 대상이 된다"


def test_reclaim_is_wired_into_the_deploy_tail():
    src = SPINE.read_text(encoding="utf-8")
    assert re.search(r"^\s*reclaim_bridge_claims\s*$", src, re.M), "배포 말미에 호출되지 않는다"
    assert re.search(r"^\s*bridge_continuity_summary\s*$", src, re.M), (
        "브리지 축 결과가 배포 보고에 나타나지 않는다 — 강행을 조용히 넘긴다")


# ── MCP 표면 롤링 ────────────────────────────────────────────────────────────

def test_mcp_rollout_never_touches_web_replicas():
    """`test_edge_rolling_gate.py` 의 recreate allowlist 등재 근거를 여기서 잠근다.

    등재 이유는 "web replica 를 만지지 않으므로 엣지 게이트의 관할 밖" 이다. 그 전제가
    깨지면 web replica 가 엣지 후보 복귀 게이트를 거치지 않고 재생성되고, 그것이 정확히
    2026-08-11 의 `no upstreams available` 전면 503 기전이다.
    """
    body = _extract_func("rollout_mcp_replicas")
    assert "web-a" not in body and "web-b" not in body
    assert "REPLICAS[" not in body.replace("MCP_REPLICAS[", ""), (
        "web replica 배열을 참조한다")


def test_mcp_rollout_is_fail_closed_on_peer_health():
    """상대가 healthy 가 아니면 이쪽을 내리지 않는다 — 내리면 MCP 후보가 0 이고,
    그 순간 개인 AI 연결이 전면 단절된다."""
    body = _extract_func("rollout_mcp_replicas")
    assert 'container_health "$other"' in body
    assert "return 1" in body
    assert "전면 단절" in body, "왜 중단하는지가 로그에 없다"


def test_mcp_is_out_of_the_bulk_worker_loop():
    """WORKERS 일괄 recreate 에 남아 있으면 배포마다 MCP 가 통째로 끊긴다."""
    src = SPINE.read_text(encoding="utf-8")
    workers = next(l for l in src.splitlines() if l.startswith("WORKERS=("))
    assert "ext-tool-mcp" not in workers, f"MCP 가 아직 일괄 롤아웃 대상이다: {workers}"
    assert "MCP_REPLICAS=(ext-tool-mcp-a ext-tool-mcp-b)" in src


def test_mcp_replicas_are_in_the_completion_verdict():
    """완결 판정에서 빠지면 "배포는 됐는데 개인 AI 가 붙는 표면만 구코드" 가 조용히 지나간다."""
    body = _extract_func("verify_workers_at_sha")
    assert '"${MCP_REPLICAS[@]}"' in body


# ── quiesce 게이트의 네 번째 축 ──────────────────────────────────────────────

def test_quiesce_counts_bridge_work():
    """브리지 전환 이후 `ask_jobs` 와 `active_streams` 는 사용자 작업을 대변하지 않는다.

    그 둘만 보는 게이트는 사용자가 답을 기다리는 중에도 '조용함' 으로 통과한다 —
    있으나 마나가 아니라, 무중단이라고 **믿게 만들기 때문에** 더 나쁘다.
    """
    lib = QUIESCE.read_text(encoding="utf-8")
    assert "bridge_active_total" in lib
    sample = _extract_func("quiesce_sample", lib)
    assert "bridge_active_total" in sample, "표본에 브리지 축이 없다"
    quiet = _extract_func("quiesce_sample_is_quiet", lib)
    assert re.search(r'\[ "\$b" -eq 0 \]', quiet), "브리지 축이 조용함 판정에 반영되지 않는다"


def test_quiesce_unknown_bridge_is_not_quiet():
    """`unknown` 은 조용함이 아니다 — 관측 실패를 0 으로 읽으면 그것이 곧 vacuous pass 다."""
    lib = QUIESCE.read_text(encoding="utf-8")
    quiet = _extract_func("quiesce_sample_is_quiet", lib)
    script = "\n".join([
        quiet,
        'quiesce_sample_is_quiet "0|0|0|unknown" && echo QUIET || echo NOTQUIET',
        'quiesce_sample_is_quiet "0|0|0|0" && echo QUIET || echo NOTQUIET',
        'quiesce_sample_is_quiet "0|0|0|2" && echo QUIET || echo NOTQUIET',
    ])
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert proc.stdout.split() == ["NOTQUIET", "QUIET", "NOTQUIET"], proc.stdout


def test_bridge_mode_does_not_permanently_block_the_gate():
    """서버 LLM 차단(브리지) 운영에서 `ask_jobs` 축은 **원래 비어 있는 것이 정상**이다.

    종전 판정("worker 모드가 아니면 무조건 중단")은 브리지 전환 이전 세계를 전제로 쓰였고,
    그대로 두면 이 게이트가 배포를 영구 차단한다. 대신 브리지 축이 관측되는지를 본다 —
    그것마저 못 읽으면 아무것도 못 보는 것이므로 종전과 같이 중단한다(fail-closed 유지).
    """
    lib = QUIESCE.read_text(encoding="utf-8")
    body = _extract_func("quiesce_user_runs", lib)
    assert "server_llm_blocked" in body
    assert 'bridge_active_total' in body
    assert 'unknown' in body and 'return 1' in body, (
        "브리지 축도 못 읽는 경우의 fail-closed 분기가 없다")


# ── 적대 리뷰 반영분 (2026-08-27) ────────────────────────────────────────────
#
# 아래는 전부 "게이트가 있는데 작동하지 않는" 부류였다. 그 종류의 결함은 배포를 성공으로
# 끝내고 사용자만 답을 못 받게 하므로, 여기서 값과 실행으로 고정한다.

def test_mcp_replicas_are_pinned_to_the_built_image():
    """pin overlay 에 없으면 그 서비스는 **참조할 이미지가 없다**.

    compose anchor 는 `build:` 만 갖고 `image:` 는 pin 이 준다. MCP replica 가 빠지면
    `--no-build` 기동이 pull 을 시도해 실패하거나 stale 로컬 이미지로 떠서 GIT_COMMIT
    불일치로 완결 판정에 걸린다 — 즉 **모든 배포가 워커 단계에서 실패**한다.
    """
    body = _extract_func("write_pin_overlay")
    assert '"${MCP_REPLICAS[@]}"' in body, "MCP replica 가 이미지 핀에서 빠졌다"


def test_mcp_rollout_precedes_the_edge_switch():
    """Caddyfile 이 `ext-tool-mcp-a/b` 를 가리키도록 바뀌는데 그 컨테이너가 없으면 502 다.

    그 창은 soak(90s) + 워커 롤아웃 전체로 이어진다 — "배포마다 AI 연결이 끊긴다" 를 고치는
    배포가 바로 그 연결을 가장 길게 끊는 셈이 된다.
    """
    src = SPINE.read_text(encoding="utf-8")
    body = src[src.index("if [ \"$web_skip\" -eq 0 ]; then"):]
    assert body.index("rollout_mcp_phase") < body.index("reconcile_caddy"), (
        "MCP 롤아웃이 엣지 전환 뒤에 있다")
    # 파괴는 생성 뒤에 — 먼저 지우면 기동 실패가 곧 '두 세대 모두 없음' 이 된다.
    phase = _extract_func("rollout_mcp_phase")
    assert phase.index("rollout_mcp_replicas") < phase.index("sweep_legacy_ext_tool_mcp")


def test_mcp_peer_guard_sees_stopped_containers():
    """`ps -q` 는 running 만 준다 — 상대가 죽어 있을 때 가드가 통째로 건너뛰어졌다.

    즉 "상대가 healthy 가 아니면 내리지 않는다" 는 불변식이 **가장 필요한 순간에만** 무효였다.
    """
    body = _extract_func("rollout_mcp_replicas")
    assert 'ps -aq "$other"' in body, "죽은 상대를 못 보는 가드다"
    assert 'ps -q "$other"' not in body


def test_predrain_fallback_does_not_read_the_draining_livez():
    """대체 게이트가 `replica_active_streams` 를 쓰면 **드레인을 켠 순간 항상 통과**한다.

    그 헬퍼는 조회 실패도 0 으로 돌려주는데(fail-open), 드레인 중 `/livez` 는 우리가 만든
    503 이라 항상 실패한다 — 최악의 조합이다. strict probe 를 쓰고, 못 읽으면 기다린다.
    """
    body = _extract_func("predrain")
    assert "replica_active_streams_strict" in body
    assert 'n="$(replica_active_streams "$target")"' not in body, (
        "fail-open 헬퍼로 대체 판정을 한다")
    assert "PREDRAIN_UNVERIFIED" in body, "드레인을 못 건 채 진행한 사실이 기록되지 않는다"


def test_unverified_predrain_also_triggers_reclaim_and_is_reported():
    """드레인을 못 걸었으면 끊김이 없었다고 **단정할 수 없다**."""
    reclaim = _extract_func("reclaim_bridge_claims")
    assert 'PREDRAIN_UNVERIFIED' in reclaim, "미확인 배포에서 회수가 돌지 않는다"
    summary = _extract_func("bridge_continuity_summary")
    assert "PREDRAIN_UNVERIFIED" in summary, "미확인 사실이 보고에서 빠진다"


def test_reclaim_is_scoped_to_the_deploy_window():
    """상한만 두면 배포와 무관하게 오래 조사 중이던 작업까지 되돌린다.

    그 작업이 재점유되면 원 소유자의 제출이 `ClaimedClient` 불일치로 409 가 된다 —
    끊기지도 않은 작업을 배포가 버리는 셈이다.
    """
    src = SPINE.read_text(encoding="utf-8")
    assert "DEPLOY_WINDOW_START=" in src, "배포 창 시작 시각을 기록하지 않는다"
    body = _extract_func("reclaim_bridge_claims")
    assert "since_epoch" in body and "DEPLOY_WINDOW_START" in body, (
        "회수 범위가 배포 창으로 좁혀지지 않는다")


def test_reclaim_runs_right_after_the_web_rolling_not_at_the_very_end():
    """배포 꼬리에 두면 이후 단계(워커·gateway·스모크)가 실패했을 때 회수가 아예 안 돈다.

    끊긴 질문은 lease 만료(30분)까지 "가져갔는데 답이 없는" 상태로 갇힌다.
    """
    src = SPINE.read_text(encoding="utf-8")
    body = src[src.index("if [ \"$web_skip\" -eq 0 ]; then"):]
    assert body.index("reclaim_bridge_claims") < body.index("deploy_workers"), (
        "회수가 워커 롤아웃 뒤로 밀려 있다")


def test_drain_leak_is_closed_on_abnormal_exit():
    """`predrain` 은 최대 180s 를 기다린다 — 그 사이 중단될 창이 넓다.

    드레인된 replica 가 남으면 `/readyz`·`/healthz`·`container_health` 어디에도 안 잡혀
    **무증상으로 실질 용량이 절반**이 된다.
    """
    src = SPINE.read_text(encoding="utf-8")
    assert "trap 'on_exit_cleanup' EXIT" in src
    assert "INT TERM" in src, "중단 신호에서 드레인이 회수되지 않는다"
    cleanup = _extract_func("on_exit_cleanup")
    assert "replica_release_drain" in cleanup
    # 같은 sha 재배포(web_skip=1)·no-op 종료에서도 잔존 드레인이 청소되어야 한다.
    body = src[src.index("write_pin_overlay \"$web_img\""):]
    assert body.index("clear_stale_drain") < body.index("local web_skip=0"), (
        "청소가 web_skip 판정 뒤에 있어, 같은 sha 재배포가 lame-duck 을 영구 방치한다")


def test_server_llm_blocked_reads_unset_as_blocked_not_unreadable():
    """`printenv NAME` 은 **미설정이면 exit 1** 이다.

    이 프로젝트는 그 변수를 어디에도 설정하지 않는다(차단이 코드 기본값이므로). 즉
    "정상 운영 = 미설정" 인데 초판은 그 exit 1 을 "못 읽었다" 로 읽어 **항상 unknown** 이었다 —
    브리지 분기 전체가 죽은 코드였다.
    """
    lib = QUIESCE.read_text(encoding="utf-8")
    body = _extract_func("server_llm_blocked", lib)
    assert "__UNSET__" in body, "미설정과 조회 실패를 구분하지 않는다"
    assert "printenv AGENT_SERVER_LLM_ENABLED" not in body, (
        "exit 1 을 관측 실패로 오독하는 형태가 남아 있다")

    def _run_stub(shell_out: str, exec_rc: int) -> str:
        script = "\n".join([
            'DC_PROD=(true)', 'REPLICAS=(web-a)', 'replica_cid() { echo cid; }',
            body.replace(
                '"${DC_PROD[@]}" exec -T "$svc" sh -c \'printf "%s" "${AGENT_SERVER_LLM_ENABLED-__UNSET__}"\' 2>/dev/null',
                f'sh -c \'printf "%s" "{shell_out}"; exit {exec_rc}\''),
            "server_llm_blocked",
        ])
        return subprocess.run(["bash", "-c", script], capture_output=True,
                              text=True, timeout=30).stdout.strip()

    assert _run_stub("__UNSET__", 0) == "yes", "미설정을 차단으로 읽지 않는다"
    assert _run_stub("1", 0) == "no"
    assert _run_stub("0", 0) == "yes"
    assert _run_stub("", 1) == "unknown", "exec 실패는 관측 불가여야 한다"


def test_quiesce_counts_only_live_bridge_claims():
    """유령 점유(노트북을 닫은 AI)가 배포를 lease 만료까지 막으면 안 된다.

    quiesce 상한(15분) < lease(30분) 이라 그 대기는 **구조적으로 성공할 수 없다**.
    """
    lib = QUIESCE.read_text(encoding="utf-8")
    body = _extract_func("bridge_active_total", lib)
    assert '"claimed"' in body and '"stale"' in body, (
        "fresh/stale 을 구분하지 않는다 — 유령 점유가 배포를 막는다")


def test_legacy_sweep_never_kills_the_deploy(tmp_path):
    """정리 실패가 **배포를 죽이지 않는다** (라이브 실측 2026-08-27).

    서비스가 compose 정의에서 사라졌으므로 `docker compose ps -aq <name>` 은
    `no such service` + **exit 1** 이다. `set -euo pipefail` 하에서 그 명령 치환이 실패하면
    스크립트가 그 자리에서 죽는다 — 첫 전환 배포가 정확히 그렇게 MCP 롤아웃 직후 중단됐고
    워커·gateway 가 구 코드로 남았다. 정리는 best-effort 이지 게이트가 아니다.
    """
    script = tmp_path / "sweep.sh"
    script.write_text("\n".join([
        "set -euo pipefail",                      # 배포 스크립트와 **같은** 옵션으로 실행한다
        "log()  { printf '[log] %s\\n' \"$*\" >&2; }",
        "warn() { printf '[warn] %s\\n' \"$*\" >&2; }",
        "run() { \"$@\"; }",
        "DRY_RUN=0",
        f'REPO_ROOT="{tmp_path}"',
        'MCP_LEGACY_SERVICE="ext-tool-mcp"',
        # compose 는 없는 서비스에 대해 실패한다(실측 재현), docker 는 빈 결과.
        "DC_PROD=(sh -c 'echo \"no such service\" >&2; exit 1' --)",
        "docker() { return 0; }",
        _extract_func("sweep_legacy_ext_tool_mcp"),
        "sweep_legacy_ext_tool_mcp",
        "echo SURVIVED",
    ]), encoding="utf-8")
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=60)
    assert "SURVIVED" in proc.stdout, (
        f"정리 조회 실패가 배포를 죽였다 — rc={proc.returncode} stderr={proc.stderr[:300]!r}")
    assert proc.returncode == 0
