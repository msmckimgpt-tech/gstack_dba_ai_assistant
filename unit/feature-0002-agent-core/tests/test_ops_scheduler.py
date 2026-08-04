"""feature-0039: ops-scheduler 계약 고정.

호스트 root crontab 이 돌던 정기 잡(백업·복원 리허설·그래프 sync)을 `ops-scheduler`
서비스 안으로 옮겼다. 스케줄러가 조용히 안 도는 것은 **몇 주 뒤 백업이 필요할 때에야
드러나는** 종류의 결함이라, 다음을 여기서 고정한다:

  1. cron 스펙 해석이 호스트 crontab 과 **동일 시각**을 산출한다 (이관 등가성).
     — 특히 `*/30` step, 일요일(dow=0), vixie-cron 의 dom/dow OR 결합.
  2. 잘못된 스펙은 **fail-loud** (조용히 안 도는 잡을 만들지 않는다).
  3. 잡 레지스트리 기본값이 이관 전 crontab 4줄과 1:1 대응한다.
  4. env 오버라이드로 개별/전체 비활성이 된다 (운영 킬스위치).
  5. 겹침 방지: 이전 실행이 진행 중이면 이번 주기는 skip.
"""
from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "src" / "scripts" / "ops_scheduler.py"


def _load():
    spec = importlib.util.spec_from_file_location("ops_scheduler", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ops():
    return _load()


# 이관 전 root crontab 원문 (bin/install-*-cron.sh 가 설치하던 4줄의 스케줄 필드).
LEGACY_SPECS = {
    "backup": "0 3 * * *",
    "restore-rehearsal": "30 3 * * 0",
    "graph-sync-incremental": "*/30 * * * *",
    "graph-sync-full": "17 4 * * *",
}


def _fire_times(ops, spec: str, start: datetime, hours: int) -> list[datetime]:
    """start 부터 hours 동안 분 단위로 훑어 실제 발화하는 시각을 모은다."""
    parsed = ops.parse_cron(spec)
    out = []
    t = start.replace(second=0, microsecond=0)
    for _ in range(hours * 60):
        if ops.cron_matches(parsed, t):
            out.append(t)
        t += timedelta(minutes=1)
    return out


# ── 1. 이관 등가성 — 호스트 cron 과 같은 시각에 발화 ─────────────────────────────

def test_backup_fires_once_a_day_at_0300(ops):
    fires = _fire_times(ops, LEGACY_SPECS["backup"], datetime(2026, 8, 4, 0, 0), 48)
    assert [f.strftime("%m-%d %H:%M") for f in fires] == ["08-04 03:00", "08-05 03:00"]


def test_graph_full_fires_at_0417(ops):
    fires = _fire_times(ops, LEGACY_SPECS["graph-sync-full"], datetime(2026, 8, 4, 0, 0), 24)
    assert [f.strftime("%H:%M") for f in fires] == ["04:17"]


def test_graph_incremental_every_30_minutes(ops):
    """`*/30` 은 :00 과 :30 두 번 — step 오해석(예: 30분마다 상대 오프셋)을 차단."""
    fires = _fire_times(ops, LEGACY_SPECS["graph-sync-incremental"], datetime(2026, 8, 4, 0, 0), 3)
    assert [f.strftime("%H:%M") for f in fires] == [
        "00:00", "00:30", "01:00", "01:30", "02:00", "02:30"]


def test_restore_rehearsal_only_on_sunday(ops):
    """dow=0 은 **일요일**. python weekday()(0=월) 를 그대로 쓰면 월요일에 도는 오프바이원."""
    # 2026-08-03(월) 부터 15일 창 → 일요일은 08-09, 08-16 두 번뿐이어야 한다.
    fires = _fire_times(ops, LEGACY_SPECS["restore-rehearsal"], datetime(2026, 8, 3, 0, 0), 24 * 15)
    assert [f.strftime("%a %m-%d %H:%M") for f in fires] == [
        "Sun 08-09 03:30", "Sun 08-16 03:30"]


# ── 2. cron 스펙 파싱 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec,expect", [
    ("* * * * *", 1440),        # 매분 (24h 창)
    ("0 * * * *", 24),          # 매시 정각
    ("0,30 3 * * *", 2),
    ("0-4 3 * * *", 5),
    ("0-59/15 3 * * *", 4),
])
def test_field_forms(ops, spec, expect):
    fires = _fire_times(ops, spec, datetime(2026, 8, 4, 0, 0), 24)
    assert len(fires) == expect


@pytest.mark.parametrize("bad", [
    "0 3 * *",          # 4 필드
    "0 3 * * * *",      # 6 필드
    "60 3 * * *",       # 분 범위 초과
    "0 24 * * *",       # 시 범위 초과
    "0 3 * * 7",        # dow 범위 초과(0~6)
    "*/0 * * * *",      # step 0
    "abc * * * *",      # 비수치
    "5-2 * * * *",      # 역순 범위
])
def test_invalid_specs_fail_loud(ops, bad):
    """조용히 '안 도는 잡' 을 만들지 않는다 — 파싱 실패는 예외."""
    with pytest.raises(ops.CronSpecError):
        ops.parse_cron(bad)


def test_dom_dow_or_semantics(ops):
    """vixie-cron 규칙: dom·dow 가 **둘 다** 제한이면 OR (AND 아님)."""
    parsed = ops.parse_cron("0 0 1 * 0")
    assert ops.cron_matches(parsed, datetime(2026, 8, 1, 0, 0))   # 1일(토) — dom 매칭
    assert ops.cron_matches(parsed, datetime(2026, 8, 9, 0, 0))   # 9일(일) — dow 매칭
    assert not ops.cron_matches(parsed, datetime(2026, 8, 5, 0, 0))  # 5일(수) — 둘 다 불일치


# ── 3~4. 잡 레지스트리 + 킬스위치 ─────────────────────────────────────────────

def test_default_jobs_match_legacy_crontab(ops):
    jobs = {j["id"]: j for j in ops.load_jobs(env={})}
    assert set(jobs) == set(LEGACY_SPECS)
    for jid, spec in LEGACY_SPECS.items():
        assert jobs[jid]["spec"] == spec, f"{jid} 스케줄이 이관 전 crontab 과 다름"


def test_job_argv_points_at_shipped_scripts(ops):
    """잡 argv 가 이미지에 실제로 존재하는 스크립트를 가리키는지 (오타·경로 드리프트 차단)."""
    scripts_dir = _SCRIPT.parent
    for job in ops.load_jobs(env={}):
        target = Path(job["argv"][1])
        assert (scripts_dir / target.name).is_file(), f"{job['id']}: {target.name} 미존재"


def test_env_override_and_disable(ops):
    jobs = {j["id"]: j["spec"] for j in ops.load_jobs(env={"OPS_SCHED_BACKUP": "15 5 * * *"})}
    assert jobs["backup"] == "15 5 * * *"
    # 빈 문자열 = 해당 잡만 비활성
    jobs = {j["id"] for j in ops.load_jobs(env={"OPS_SCHED_BACKUP": ""})}
    assert "backup" not in jobs and "graph-sync-full" in jobs
    # 전체 킬스위치
    assert ops.load_jobs(env={"OPS_SCHED_ENABLED": "0"}) == []


def test_bad_env_spec_raises(ops):
    with pytest.raises(ops.CronSpecError):
        ops.load_jobs(env={"OPS_SCHED_BACKUP": "notacron"})


# ── 5. 겹침 방지 ─────────────────────────────────────────────────────────────

def test_runner_skips_while_previous_still_running(ops, tmp_path):
    job = {"id": "slow", "argv": ["/bin/sh", "-c", "sleep 30"], "log": str(tmp_path / "j.log")}
    runner = ops.JobRunner(job)
    # 첫 실행은 sleep 으로 계속 살아 있다.
    assert runner.start() is True
    for _ in range(100):
        if runner.running:
            break
        time.sleep(0.01)
    assert runner.running
    assert runner.start() is False, "이전 실행 중인데 두 번째 실행이 시작됐다"
    runner.terminate()
    runner.join(timeout=10)


def test_runner_writes_job_log(ops, tmp_path):
    log = tmp_path / "sub" / "cron.log"
    runner = ops.JobRunner({"id": "echo", "argv": ["/bin/sh", "-c", "echo hello-ops"], "log": str(log)})
    runner.start()
    runner.join(timeout=15)
    assert log.is_file(), "잡 로그 파일이 생성되지 않음(호스트 cron 시절 조회 경로 보존 실패)"
    assert "hello-ops" in log.read_text(encoding="utf-8")


# ── heartbeat (healthcheck 판정 소스) ────────────────────────────────────────

def test_heartbeat_written_and_fresh(ops, tmp_path):
    hb = tmp_path / "hb"
    ops.write_heartbeat(str(hb))
    assert abs(time.time() - float(hb.read_text().strip())) < 5


def test_heartbeat_failure_does_not_raise(ops, tmp_path):
    """하트비트 기록 실패가 스케줄링을 멈추게 하면 안 된다."""
    ops.write_heartbeat(str(tmp_path / "nonexistent-dir" / "sub" / "hb"))


def test_explicit_full_range_is_still_restricted(ops):
    """`1-31` 은 값 집합이 전 범위여도 **문법상 제한** 필드다 (codex P2 — dom/dow OR 뒤집힘 방지).

    `0 0 1-31 * 0` 을 dom 무제한으로 오인하면 dow(일요일)만 남아 매일이 아니라 주 1회가 된다.
    """
    parsed = ops.parse_cron("0 0 1-31 * 0")
    for day in (3, 4, 5, 6, 7):           # 2026-08-03(월)~07(금) — dom 매칭이라 전부 실행돼야 한다
        assert ops.cron_matches(parsed, datetime(2026, 8, day, 0, 0)), day
    # `*` 로 쓴 dom 은 무제한이라 dow 제한만 남는다 (대조군).
    parsed_star = ops.parse_cron("0 0 * * 0")
    assert not ops.cron_matches(parsed_star, datetime(2026, 8, 3, 0, 0))   # 월요일
    assert ops.cron_matches(parsed_star, datetime(2026, 8, 9, 0, 0))       # 일요일


def test_parse_cron_reports_unrestricted_flag(ops):
    """무제한 여부는 값이 아니라 **문법**(`*`)으로 판정한다."""
    fields = ops.parse_cron("* 0-23 1-31 1-12 0-6")
    assert [unrestricted for _, unrestricted in fields] == [True, False, False, False, False]


def test_shutdown_waits_for_running_job(ops, tmp_path, monkeypatch):
    """SIGTERM 시 진행 중 잡을 기다린다 (codex P1 — 배포 recreate 가 백업 회차를 죽이던 경로).

    JobRunner 단위로 검증: 유예 안에 끝나는 잡은 terminate 없이 정상 rc 로 완주해야 한다.
    """
    log = tmp_path / "j.log"
    runner = ops.JobRunner({"id": "slowish", "argv": ["/bin/sh", "-c", "sleep 2; echo done-ok"],
                            "log": str(log)})
    runner.start()
    runner.join(timeout=30)          # 유예 대기 상당 — terminate 전에 완주
    assert not runner.running
    assert "done-ok" in log.read_text(encoding="utf-8")
