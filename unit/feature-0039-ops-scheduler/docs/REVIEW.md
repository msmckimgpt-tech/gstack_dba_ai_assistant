---
doc_type: REVIEW
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260804T104000-ai-root-feature-0039-ops-scheduler

### 배경
사용자 요청: crontab 의 `cd <repo> && bin/*.sh` 4개 항목이 호스트 `root` 대신 서비스 내부에서
동작하도록 구성. root 였던 근거는 래퍼들의 `docker exec` + 이 호스트의 docker 소켓 root 독점
하나였다(`bin/install-metadata-graph-sync-cron.sh` 원 주석).

### 판단 근거

**1. docker 소켓 마운트를 택하지 않은 이유 (핵심).** 가장 적은 코드 변경은 "컨테이너에
docker 소켓을 물리고 기존 래퍼를 그대로 실행" 이지만, docker 소켓은 컨테이너→호스트 root
승격 경로다. root 실행을 없애려는 작업이 더 넓은 root 노출을 만드는 자기모순이라 배제하고,
잡을 이미지 안으로 옮겨 `docker exec` 자체를 제거했다.

**2. 전용 서비스 vs 워커 편입.** 사용자 선택(전용 `ops-scheduler`). 761MB pg_dump 가
insight-worker 의 `mem_limit 1g`·heartbeat healthcheck·`restart: on-failure:3` 과 얽히면
백업 실패가 워커 장애로 오진된다. 진단면 분리 > 컨테이너 1개 비용.

**3. pg_dump 메이저를 16 으로 고정한 이유 (실측 근거).** Debian trixie 본 저장소는
`postgresql-client-17` 만 제공한다. pg_dump 17 산출물은 첫머리에 PG17 전용 GUC
`SET transaction_timeout = 0;` 을 넣고, PG16 서버로 복원하면
`ERROR: unrecognized configuration parameter` 로 `ON_ERROR_STOP=1` 복원이 rc=3 으로 죽는다
(격리 컨테이너 실측). 이관 전 `docker exec <postgres> pg_dump` 는 서버 자신의 pg_dump 를 써서
버전 정합이 **자연히** 성립했었다 — 네트워크 클라이언트로 옮기면서 그 성질을 명시적으로
복원해야 한다. PGDG 저장소로 `postgresql-client-16`(16.14, 서버와 동일 패치)을 고정했다.
비용: 빌드 시 `apt.postgresql.org` 외부 의존 1건 추가(기존 deb.debian.org·PyPI 와 동급).

**4. mysqldump 는 이미지의 MariaDB 계열을 그대로 쓴 이유 (실측 근거).** Debian
`default-mysql-client` 는 MariaDB 11.8 이다. DR 경로에 다른 벤더 클라이언트를 쓰는 것이
불안해 **라이브 실측으로 등가성을 확인**했다: 네트워크 MariaDB 덤프와 서버 내장 MySQL 8.0.46
덤프의 `CREATE TABLE`~`) ENGINE` 구간이 **바이트 동일**하고 콜레이션(`utf8mb4_0900_ai_ci`)도
보존된다 — mysqldump 가 `SHOW CREATE TABLE` 을 패스스루하기 때문이다. 헤더의 MariaDB 전용
`/*M!…*/` 주석은 MySQL 파서에 일반 주석이라 무해. 따라서 MySQL 공식 apt 저장소 추가는
불필요한 빌드 의존이라 배제.

**5. flock 을 PG advisory lock 으로 바꾸지 않은 이유.** §82 동시성 가드(2026-07-14 라이브
장애 대응)는 `bin/metadata-graph-sync.sh` 와 **호스트에 남는** `bin/routine-backfill.sh` 가
공유하는 flock 이다. advisory lock 으로 갈아타면 `routine_backfill` 쪽도 함께 고쳐야 하고,
인시던트 대응으로 들어간 가드의 의미론을 건드리게 된다. 대신 lock 디렉터리를 bind-mount 해
**같은 inode** 를 잡게 했다 — flock 은 inode 단위라 호스트/컨테이너 경로가 달라도 상호배제가
성립한다. 3-케이스 실측으로 확인(미마운트 fail-loud / 호스트 보유 skip / 정상 실행).
lock 마운트가 없으면 sync 를 **실행 거부**한다 — 가드 없이 도는 것보다 안 도는 편이 안전하다.

**6. 배포 스파인 편입.** `deploy-web.sh` 의 `WORKERS` 에 넣지 않으면 배포 후에도 정기 잡이
구 이미지로 계속 돈다("배포는 됐는데 잡만 stale" — 조용히 오래 가는 결함). 편입에 따라
healthcheck 가 필요해져 heartbeat 파일 기반 probe 를 신설했다. **DB 를 보지 않는 probe** 로
설계한 것은 의도적이다 — DB 순단이 스케줄러 재시작으로 번지면 그 창의 잡을 통째로 잃는다.

**7. 백업 rc 정책 변경 (의도적 미세 변경).** 이관 전 `bin/backup.sh` 는 덤프가 100B 미만이어도
경고만 하고 rc=0 이었다. 이관본은 rc=1 로 격상했다 — 빈 덤프는 DR 관점에서 실패이고,
스케줄러가 rc 를 로그하므로 이제 신호가 관측 가능해진다.

### 리스크
- **외부 빌드 의존 +1 (PGDG)**: `apt.postgresql.org` 불가 시 이미지 빌드 실패 → web 배포까지
  영향. 기존 deb.debian.org / PyPI 와 동급의 노출이며, 실패는 빌드 시점에 fail-loud 다.
- **이관 창의 중복 실행**: 배포와 crontab 제거 사이에 백업이 2회 돌 수 있다(보존 회전 소모).
  배포 직후 즉시 crontab 을 제거해 창을 최소화한다.
- **잔여**: `bin/routine-backfill.sh` 는 여전히 호스트 수동 실행(cron 미등록이라 요청 범위 밖).

## REV-20260804T104600-ai-root-feature-0039-age-restore

### 배경
이관 등가성 검증 중 컨테이너 복원 리허설이 FAIL. 호스트 cron 로그(`artifacts/backups/cron.log`)
대조 결과 07-05·07-12·07-19·07-26 주간 실행이 **전부 동일하게 FAIL** — 이관 회귀가 아니라
feature-0016 AGE cutover 이후 5주간 방치된 기존 결함으로 확정.

### 근본 원인 (정밀 재현)
`pg_dump --clean` 산출물 365행 `DROP EXTENSION IF EXISTS age;` 가 빈 DB 에서
`ERROR: schema "ag_catalog" does not exist` 로 실패한다. AGE 가 `shared_preload_libraries` 로
프리로드된 서버에서는 그 utility 훅이 `ag_catalog` 를 무조건 조회하므로 `IF EXISTS` 가
단락되지 않는다. 즉 **AGE cutover 가 `pg_dump --clean` 산출물의 신규-DB 복원을 조용히
깨뜨렸다** — 백업 자체는 정상 생성되지만 복원 불가였다.

### 해법과 대안
- 채택: 리허설의 throwaway DB 에 복원 전 `CREATE EXTENSION IF NOT EXISTS age` (실제 DR 에서도
  대상 DB 는 AGE 가 설치된 상태여야 하므로 baseline 재현이 정확하다). 실패 시 경고 후 계속 —
  cutover 전 환경 하위호환.
- 배제 A: 백업에서 `--clean` 제거. 신규 DB 복원은 되지만 **기존 DB 위 복원**(진짜 DR)이
  불가능해져 백업의 쓸모가 줄어든다.
- 배제 B: `ON_ERROR_STOP=0` 으로 오류 무시. '부분 복원 탐지' 라는 리허설의 존재 이유를 없앤다.

### 검증
라이브 실측: 761MB 실 백업으로 전량 복원 → **PASS**, PG 사용자 테이블 67개 · MySQL 32개,
임시 DB 정리 확인. 프로덕션 DB 미접촉.

### 사용자 승인
AGENTS.md §8.1(요청 범위 밖 개선은 기록만) 에 따라 실행 전 사용자에게 확인 →
"이번 cycle 에 함께 수정" 선택 (2026-08-04).

## REV-20260804T115000-ai-root-feature-0039-ops-scheduler [CODEX:review]

§18.8 검증 패널을 `/codex review` (docs-only 아닌 코드 변경이므로 diff 전체 대상, reasoning
effort high) 로 수행. **[P1] 5건 · [P2] 4건**. 세션 지시상 Agent tool 사용이 제한돼 §18.8.1
의 codex-review 대체 경로를 사용했다.

### [P1] 수용·수정 (5/5)

| # | 지적 | 사실 확인 | 조치 |
|---|---|---|---|
| P1-1 | `Makefile` `up`/`start` 의 build·기동 목록에 `ops-scheduler` 부재 → 신규·재부팅 환경에서 cron 만 제거하면 4개 잡 전면 정지 | **확인** — `Makefile:153` 이 서비스를 명시 열거 | build 목록·이미지 검증 루프·`up -d` 블록에 편입(`ENABLE_OPS_SCHEDULER=0` 로만 비활성) |
| P1-2 | SIGTERM 시 진행 잡을 기다리지 않고 즉시 `terminate()` → 배포(deploy-web.sh 가 매번 recreate)가 백업 도중이면 그 회차 소실 | **확인** — 코드가 docstring("진행 중 잡의 종료를 기다린 뒤")과 불일치 | 유예 대기 후 terminate 로 수정(`OPS_SCHED_SHUTDOWN_GRACE_SEC=280`) + `stop_grace_period` 60s→300s |
| P1-3 | 최종 경로에 직접 기록 + 실패한 부분 디렉터리가 보존 회전에 포함 → 반복 실패 시 **정상 백업이 밀려남** | **확인** — 이관 전 `bin/backup.sh` 부터 있던 구조 | `<ts>.partial` staging → 무결성 통과 후 rename. 회전은 완료 백업만 계수, `.partial` 은 24h 경과분만 별도 청소 |
| P1-4 | `../artifacts` 전체를 쓰기 마운트 → 그 아래 라이브 DB 데이터가 있음 | **확인** — `mysql-data`·`postgres-data`·`postgres-replica-data`·`minio-data` 전부 `../artifacts` 하위 | `backups`·`metadata-graph` 두 디렉터리만 마운트 |
| P1-5 | `agent-common` 의 `depends_on` 상속 → 무관한 `bedrock-gateway`·MinIO unhealthy 시 스케줄러 미기동 | **확인** | `depends_on` 을 mysql·postgres 로 override |

### [P2] 수용 2 / 인지 후 보류 2

- **P2-1 수용** — dom/dow 무제한 판정을 값 집합이 아니라 **문법(`*`)** 기준으로 교정.
  `0 0 1-31 * 0` 이 매일이 아니라 일요일만 실행되던 오프바이원. 회귀 테스트 2건 추가.
- **P2-3 수용** — MySQL 암호를 argv → `--defaults-extra-file`(0600 임시파일)로. 같은 컨테이너
  `/proc/*/cmdline` 노출 제거 + 이관 전 `2>/dev/null`(암호 경고를 지우려던 것)을 걷어내
  **진짜 실패 원인이 로그에 남게** 했다.
- **P2-2 보류(인지)** — 같은 분 중복 발화 방지가 in-memory 라 그 분 안에 컨테이너가 재시작되면
  재발화 가능. vixie-cron 도 데몬 재시작에 동일 성질이고, 4개 잡 모두 멱등(백업=새 타임스탬프
  디렉터리, sync=MERGE, 리허설=throwaway DB)이라 지속 상태를 추가할 가치가 낮다.
- **P2-4 보류(설계 의도)** — healthcheck 가 루프 heartbeat 만 보므로 잡이 계속 실패해도 healthy.
  **의도적**이다: DB 를 healthcheck 에 엮으면 DB 순단이 스케줄러 재시작으로 번져 그 창의 잡을
  통째로 잃는다. 다만 지적의 본질(잡 실패가 안 보인다)은 유효하며, 실제로 이번 cycle 에서
  발견한 "5주간 리허설 FAIL 방치" 가 그 증거다 — REPORT.md §8 에 알림·health 승격을 제안으로 남겼다.

### 재검증

수정 후 라이브 재실행: 백업 rc=0(`.partial` 잔존 0 · 761M+46M) · 복원 리허설 rc=0 PASS ·
compose config 렌더 확인(마운트 2개로 축소·depends_on 2개·stop_grace 5m) · pytest 29건 PASS.
