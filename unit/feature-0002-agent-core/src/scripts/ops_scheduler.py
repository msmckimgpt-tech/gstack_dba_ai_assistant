#!/usr/bin/env python
"""feature-0039: 운영 정기 잡 인-컨테이너 스케줄러 (`ops-scheduler` 서비스 entrypoint).

**왜 있는가**: 백업/복원 리허설/그래프 sync 는 원래 호스트 root crontab 에서
`cd <repo> && bin/*.sh` 로 돌았다. root 였던 유일한 이유는 그 래퍼들이 `docker exec`
를 쓰는데 이 호스트는 docker 소켓 접근이 root 에만 있기 때문이다
(`bin/install-metadata-graph-sync-cron.sh` 주석). 잡을 컨테이너 안으로 옮기면
docker 소켓 의존 자체가 사라져 root 권한 근거가 소멸한다 — 본 모듈이 그 스케줄러다.

**설계**:
  - 5-필드 cron 스펙(분 시 일 월 요일)만 지원. `*` `n` `a,b` `a-b` `*/n` `a-b/n`.
    호스트 crontab 과 동일 표기라 이관 시 스펙 문자열을 그대로 옮길 수 있다.
  - 컨테이너 로컬 시각(TZ env, 배포값 Asia/Seoul) 기준 — 호스트 cron 과 동일 벽시계.
  - 잡별 겹침 방지: 이전 실행이 끝나지 않았으면 이번 tick 은 skip(로그 남김).
    잡 사이(그래프 sync ↔ 호스트 routine-backfill)의 상호배제는 잡 스크립트 자신의
    flock(호스트와 bind-mount 공유) 책임 — 스케줄러는 자기 중복만 막는다.
  - SIGTERM/SIGINT: 새 실행을 멈추고 진행 중 잡의 종료를 기다린 뒤 내려간다.
  - 잡 출력은 stdout(=`docker logs`, compose json-file 20m×5 rotation) 과 잡별
    로그 파일 양쪽에 남는다. 로그 파일 경로는 호스트 cron 시절과 동일하게 유지해
    (`/artifacts/...` = 호스트 `../artifacts/...`) 운영자의 기존 조회 경로가 안 깨진다.

**환경변수** (전부 선택 — 미설정 시 기본 스케줄):
  OPS_SCHED_ENABLED            "0" 이면 잡을 등록하지 않고 idle (긴급 전면 중단용)
  OPS_SCHED_BACKUP             기본 "0 3 * * *"      — 빈 문자열이면 해당 잡 비활성
  OPS_SCHED_RESTORE_REHEARSAL  기본 "30 3 * * 0"
  OPS_SCHED_GRAPH_INCREMENTAL  기본 "*/30 * * * *"
  OPS_SCHED_GRAPH_FULL         기본 "17 4 * * *"
  OPS_SCHED_TICK_SEC           기본 20 (스케줄 평가 주기)
  OPS_SCHED_HEARTBEAT_FILE     기본 /tmp/ops-scheduler.heartbeat (healthcheck 판정 소스)

Exit: 0 정상 종료(시그널) / 2 잡 정의 오류(잘못된 cron 스펙).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

# 잡 정의: (job_id, 기본 cron 스펙, env 오버라이드 키, argv, 로그 파일)
# 로그 파일은 호스트 cron 시절 경로를 그대로 유지한다(운영자 조회 경로 보존).
JOB_DEFS = (
    {
        "id": "backup",
        "default_spec": "0 3 * * *",
        "env": "OPS_SCHED_BACKUP",
        "argv": ["/bin/bash", str(SCRIPTS_DIR / "ops_backup.sh")],
        "log": "/artifacts/backups/cron.log",
    },
    {
        "id": "restore-rehearsal",
        "default_spec": "30 3 * * 0",
        "env": "OPS_SCHED_RESTORE_REHEARSAL",
        "argv": ["/bin/bash", str(SCRIPTS_DIR / "ops_restore_rehearsal.sh")],
        "log": "/artifacts/backups/cron.log",
    },
    {
        "id": "graph-sync-incremental",
        "default_spec": "*/30 * * * *",
        "env": "OPS_SCHED_GRAPH_INCREMENTAL",
        "argv": ["/bin/bash", str(SCRIPTS_DIR / "ops_graph_sync.sh"), "--incremental"],
        "log": "/artifacts/metadata-graph/cron.log",
    },
    {
        "id": "graph-sync-full",
        "default_spec": "17 4 * * *",
        "env": "OPS_SCHED_GRAPH_FULL",
        "argv": ["/bin/bash", str(SCRIPTS_DIR / "ops_graph_sync.sh"), "--full"],
        "log": "/artifacts/metadata-graph/cron.log",
    },
)

_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))  # 분 시 일 월 요일


class CronSpecError(ValueError):
    """cron 스펙 파싱 실패 — fail-loud(조용히 안 도는 잡을 만들지 않는다)."""


def _parse_field(expr: str, lo: int, hi: int) -> tuple[frozenset[int], bool]:
    """cron 한 필드를 (허용값 집합, 무제한 여부) 로 전개.

    `*` `n` `a,b` `a-b` `*/n` `a-b/n` 지원. **무제한 여부는 값이 아니라 문법으로 판정한다** —
    `1-31` 은 값 집합이 전 범위와 같아도 vixie-cron 규칙상 '제한된' 필드이고, 이를 `*` 로
    오인하면 dom/dow OR 결합이 뒤집힌다(예: `0 0 1-31 * 0` 이 매일이 아니라 일요일만 실행).
    """
    out: set[int] = set()
    unrestricted = expr.strip() == "*"
    for part in expr.split(","):
        part = part.strip()
        if not part:
            raise CronSpecError(f"빈 필드 항목: {expr!r}")
        step = 1
        if "/" in part:
            part, _, step_s = part.partition("/")
            if not step_s.isdigit() or int(step_s) < 1:
                raise CronSpecError(f"잘못된 step: {expr!r}")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part.lstrip("-"):
            a, _, b = part.partition("-")
            if not (a.isdigit() and b.isdigit()):
                raise CronSpecError(f"잘못된 범위: {expr!r}")
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
        else:
            raise CronSpecError(f"해석 불가 항목: {part!r} (필드 {expr!r})")
        if start < lo or end > hi or start > end:
            raise CronSpecError(f"범위 밖: {part!r} (허용 {lo}~{hi})")
        out.update(range(start, end + 1, step))
    if not out:
        raise CronSpecError(f"매칭 값 없음: {expr!r}")
    return frozenset(out), unrestricted


def parse_cron(spec: str) -> tuple[tuple[frozenset[int], bool], ...]:
    """5-필드 cron 스펙을 (분, 시, 일, 월, 요일) 의 (허용집합, 무제한여부) 튜플로 전개."""
    fields = spec.split()
    if len(fields) != 5:
        raise CronSpecError(f"5개 필드가 필요합니다(분 시 일 월 요일): {spec!r}")
    return tuple(_parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, _FIELD_RANGES))


def cron_matches(parsed: tuple[tuple[frozenset[int], bool], ...], when: datetime) -> bool:
    """vixie-cron 규칙: 일(dom)/요일(dow) 중 하나라도 `*` 가 아니면 **OR** 로 결합."""
    (minute, _), (hour, _), (dom, dom_any), (mon, _), (dow, dow_any) = parsed
    if when.minute not in minute or when.hour not in hour or when.month not in mon:
        return False
    dom_restricted = not dom_any
    dow_restricted = not dow_any
    # cron 의 요일은 0=일요일. python weekday() 는 0=월요일이라 isoweekday()%7 로 맞춘다.
    dow_now = when.isoweekday() % 7
    if dom_restricted and dow_restricted:
        return when.day in dom or dow_now in dow
    if dom_restricted:
        return when.day in dom
    if dow_restricted:
        return dow_now in dow
    return True


def load_jobs(env: dict[str, str] | None = None, defs=JOB_DEFS) -> list[dict]:
    """env 오버라이드를 반영해 활성 잡 목록을 만든다. 빈 스펙은 '비활성' 의미."""
    env = os.environ if env is None else env
    if env.get("OPS_SCHED_ENABLED", "1").strip().lower() in ("0", "false", "no", "off"):
        return []
    jobs: list[dict] = []
    for d in defs:
        spec = env.get(d["env"], d["default_spec"]).strip()
        if not spec:
            continue  # 명시적 비활성 (빈 문자열)
        jobs.append({
            "id": d["id"],
            "spec": spec,
            "parsed": parse_cron(spec),
            "argv": list(d["argv"]),
            "log": d["log"],
        })
    return jobs


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ops-scheduler {ts}] {msg}", flush=True)


HEARTBEAT_FILE = os.getenv("OPS_SCHED_HEARTBEAT_FILE", "/tmp/ops-scheduler.heartbeat")


def write_heartbeat(path: str = "") -> None:
    """루프 생존 신호. healthcheck_ops_scheduler.py 가 이 파일의 신선도만 본다.

    PG/MySQL 이 아니라 **자기 루프**를 신호원으로 삼는다 — 스케줄러의 책임은 '제 시각에
    잡을 띄우는 것' 이고, DB 가용성은 잡 자신의 판정 대상이다. DB 를 healthcheck 에
    엮으면 DB 순단이 스케줄러 재시작으로 번져 그 창의 잡을 통째로 잃는다.
    """
    p = Path(path or HEARTBEAT_FILE)
    try:
        p.write_text(f"{time.time():.0f}\n", encoding="utf-8")
    except OSError as exc:  # 하트비트 실패가 스케줄링을 멈추게 하지 않는다
        _log(f"heartbeat 기록 실패({p}): {exc!r}")


class JobRunner:
    """잡 1개의 실행 상태. 겹침 방지(이전 실행 미종료 시 skip)를 담당."""

    def __init__(self, job: dict) -> None:
        self.job = job
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self.running:
                _log(f"{self.job['id']}: 이전 실행이 아직 진행 중 — 이번 주기 skip")
                return False
            self._thread = threading.Thread(
                target=self._run, name=f"job-{self.job['id']}", daemon=True)
            self._thread.start()
            return True

    def _run(self) -> None:
        jid = self.job["id"]
        started = time.monotonic()
        _log(f"{jid}: 시작 ({' '.join(self.job['argv'])})")
        log_path = Path(self.job["log"])
        fh = None
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = log_path.open("a", encoding="utf-8", errors="replace")
        except OSError as exc:  # 로그 파일 못 열어도 잡은 돈다(stdout 은 남는다)
            _log(f"{jid}: 로그 파일 열기 실패({log_path}): {exc!r} — stdout 만 기록")
        try:
            self._proc = subprocess.Popen(
                self.job["argv"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", bufsize=1)
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                line = line.rstrip("\n")
                print(f"[{jid}] {line}", flush=True)
                if fh is not None:
                    fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{jid}] {line}\n")
                    fh.flush()
            rc = self._proc.wait()
        except Exception as exc:  # noqa: BLE001 — 스케줄러가 잡 예외로 죽으면 안 됨
            _log(f"{jid}: 실행 예외 {exc!r}")
            rc = -1
        finally:
            self._proc = None
            if fh is not None:
                fh.close()
        took = time.monotonic() - started
        _log(f"{jid}: 종료 rc={rc} ({took:.1f}s)")

    def terminate(self) -> None:
        p = self._proc
        if p is not None and p.poll() is None:
            p.terminate()

    def join(self, timeout: float) -> None:
        t = self._thread
        if t is not None:
            t.join(timeout)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--list" in argv:  # 진단용: 스케줄 해석 결과만 출력하고 종료
        for j in load_jobs():
            print(f"{j['id']:<24} {j['spec']:<16} {' '.join(j['argv'])}")
        return 0

    try:
        jobs = load_jobs()
    except CronSpecError as exc:
        print(f"[ops-scheduler] 잡 정의 오류: {exc}", file=sys.stderr, flush=True)
        return 2

    if not jobs:
        _log("활성 잡 없음 (OPS_SCHED_ENABLED=0 또는 전 잡 비활성) — idle")
    else:
        _log(f"기동 — TZ={time.tzname[0]} 활성 잡 {len(jobs)}개")
        for j in jobs:
            _log(f"  · {j['id']:<24} {j['spec']}")

    runners = {j["id"]: JobRunner(j) for j in jobs}
    stopping = threading.Event()

    def _on_signal(signum, _frame):
        _log(f"시그널 {signal.Signals(signum).name} 수신 — 신규 실행 중단, 진행 잡 대기")
        stopping.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    tick = max(1, int(os.getenv("OPS_SCHED_TICK_SEC", "20")))
    fired: dict[str, str] = {}  # job_id -> 마지막 발화한 "YYYY-mm-dd HH:MM"

    write_heartbeat()
    while not stopping.is_set():
        now = datetime.now()
        slot = now.strftime("%Y-%m-%d %H:%M")
        write_heartbeat()
        for j in jobs:
            if fired.get(j["id"]) == slot:
                continue  # 같은 분에 두 번 발화 금지 (tick < 60s 이므로 필수)
            if cron_matches(j["parsed"], now):
                fired[j["id"]] = slot
                runners[j["id"]].start()
        # 오래된 발화 기록 정리 (메모리 누적 방지)
        if len(fired) > 4 * len(jobs) + 8:
            cutoff = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
            fired = {k: v for k, v in fired.items() if v >= cutoff}
        stopping.wait(tick)

    # SIGTERM 시 진행 중 잡을 **먼저 기다린다**. 즉시 terminate 하면 배포(deploy-web.sh 가
    # 매번 서비스를 recreate)가 하필 백업·복원 도중이면 그 회차를 통째로 잃고, 다음 주기까지
    # 재시도도 없다. compose 의 stop_grace_period 보다 조금 짧은 예산으로 기다린 뒤,
    # 그래도 안 끝나면 terminate → 마지막에 SIGKILL 은 docker 가 처리한다.
    grace = max(0, int(os.getenv("OPS_SCHED_SHUTDOWN_GRACE_SEC", "50")))
    running = [r for r in runners.values() if r.running]
    if running:
        _log(f"진행 중 잡 {len(running)}개 — 최대 {grace}s 대기: "
             f"{', '.join(r.job['id'] for r in running)}")
        deadline = time.monotonic() + grace
        for r in running:
            r.join(timeout=max(0.0, deadline - time.monotonic()))
        still = [r for r in runners.values() if r.running]
        if still:
            _log(f"유예 초과 — 강제 종료: {', '.join(r.job['id'] for r in still)}")
    for r in runners.values():
        r.terminate()
    for r in runners.values():
        r.join(timeout=10)
    _log("종료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
