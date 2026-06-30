---
doc_type: FUNCTION
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
web 서비스를 **무중단(zero-downtime)** 으로 재배포하는 구조를 도입한다. 현재 배포
(`docker compose up -d --no-deps web`)는 단일 web 컨테이너를 recreate 하므로 Caddy 가
그 gap 동안 502 를 반환한다. `deploy_scope: included` 로 머지마다 자동 배포되는 고병렬
환경에서 이 blip 이 빈발한다. 본 기능은 Caddy 뒤에 **2개의 web replica(web-a/web-b)** 를
두고 **한 번에 하나씩 롤링 재시작**하여 항상 ≥1 healthy upstream 을 유지하는 토폴로지와,
그 롤아웃을 안전하게 수행하는 배포 스파인(`bin/deploy-web.sh`)을 구성한다.

본 기능은 단일 호스트 Docker Compose(오케스트레이터 없음) + Caddy + FastAPI 환경에 맞춘다.

## 2. Goal
- REQ-20260630T120000-zero-downtime-web: web 재배포 시 비-스트리밍 경로(주 채팅 `/api/ask`
  포함)에 대해 사용자 체감 중단 0(zero-502)을 달성한다.
- REQ-20260630T120001-safe-unattended-deploy: `deploy_scope: included` 자동 배포 경로에서
  고병렬(동시 머지) 상황에도 안전하게(직렬화·롤백·검증) 무인 배포가 가능하다.
- REQ-20260630T120002-migration-safety: 두 web 버전이 공유 DB 에 잠시 공존하는 롤아웃
  창에서 스키마 비호환(expand/contract 위반)을 게이트로 차단한다.

## 3. In Scope
- Caddy 2-upstream 로드밸런싱 + active health + dial-retry 토폴로지 (Caddyfile).
- `web` → `web-a`/`web-b` compose 분할 (동일 이미지/cert/healthcheck).
- 배포 스파인 `bin/deploy-web.sh`: flock 직렬화·origin/main coalesce, scoped-sudo 단일 경계,
  프로덕션 file-set 격리, TLS preflight, build-once tag-by-commit + last-good,
  migrate 순서 소유, one-at-a-time 롤링, post-cutover soak + 자동 롤백.
- 마이그레이션 안전 게이트 `bin/migrate-lint.sh` + CONVENTIONS expand/contract 규칙.
- `/readyz`(심층) + `/livez`(no-DB) probe + active-stream 카운터 (app.py).
- SSE pre-drain 게이트, 정적 자산 content-hash fingerprint.
- `:18080` web 직접 접속 문 **폐기** → 모든 외부/LAN 접속 Caddy `:443` 단일화.
- cycle-finalize 자동 배포 단계를 deploy-web.sh 로 전환.

## 4. Out of Scope
- 오케스트레이터(Swarm/k8s) 도입.
- DB(MySQL/PG) 자체의 HA/replica 무중단 (KB replica 는 feature-0002 T5 별건).
- worker(ask-worker/insight-worker) 의 무중단 재시작 — web 롤아웃은 `--no-deps`+web 만
  지정하여 worker 를 건드리지 않음. worker GIT_COMMIT divergence 는 WARN + quiet-time 재빌드.
- insight-worker graceful SIGTERM 핸들러 추가 (별건 — web 배포가 worker 를 죽이지 않으므로
  무중단에 불필요).

## 5. Inputs
- 배포 트리거: cycle-finalize(PR 머지 후, deploy_scope: included) 또는 수동 `make web`.
- `origin/main` HEAD commit (배포 대상 — caller worktree commit 아님, coalesce).
- env: `WEB_PUBLIC_HOST`, cert(`artifacts/certs/<host>/{fullchain,privkey}.pem`, `rootCA.pem`).
- scoped NOPASSWD sudoers (wrapper 한정) — 무인 배포 전제.

## 6. Outputs
- Caddy 를 통한 무중단 web 롤아웃 (비-SSE zero-502).
- 이미지 태그: `mysql-ai-web:<git_commit>` / `:last-good` / `:current` (keep-3).
- 상태 파일: `artifacts/locks/deploy-web.lock`, `artifacts/deploy/deploy-web.state`,
  `deploy-web.last-good`.
- 배포/롤백 로그 + REPORT.md 기록.

## 7. Main Flow
1. cycle-finalize 또는 수동 호출 → `sudo -E bin/deploy-web.sh`.
2. flock 획득(전체 배포 감쌈) → `git fetch` → 배포 대상 = `origin/main` HEAD 로 coalesce.
3. 프로덕션 file-set 격리 단언 + TLS preflight + migrate-lint + sudo/ownership preflight.
4. build-once(tag by commit) → migrate(expand) → 양 replica 가 아직 OLD 인지 확인.
5. one-at-a-time: 대상 replica pre-drain(상대 healthy 확인 + active-stream 종료 대기) →
   Caddy rotation 제거 → SIGTERM/recreate → `/readyz`+git_commit 게이트 → 다음 replica.
6. post-cutover soak(60~120s, RestartCount/edge 감시) → 통과 시 OLD 이미지 정리, 실패 시
   last-good 자동 롤백.
7. flock 해제 + REPORT 기록.

## Pre-approved Changes
- deploy_scope: included (전역 FIRST_REQUEST.md 상속) — cycle-final 후 자동 배포.
- reachability_scope: included — 본 기능은 bring-up/도달성이 완료 기준의 핵심이므로,
  완료 시 공개 entry-point(`https://WEB_PUBLIC_HOST/healthz`) end-to-end 도달성 검증 포함.
- release_notes_scope: included — 배포 구조 변경이므로 릴리즈노트 동반.

> **주의 — 라이브 검증 한계**: 실제 롤링 배포의 zero-502 부하 테스트와 non-root WSL2 호스트
> dry-run 은 **운영자가 실 호스트에서 수행**해야 한다. 본 개발 환경(root + NOPASSWD:ALL)은
> sudo/소유권 경계 문제를 은폐하므로 dry-run 이 거짓 통과한다 (적대적 검증 unattended-fit 발견).
