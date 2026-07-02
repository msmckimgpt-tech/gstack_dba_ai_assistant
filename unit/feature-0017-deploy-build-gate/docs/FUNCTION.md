---
doc_type: FUNCTION
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
무중단 배포 스파인(`bin/deploy-web.sh`, feature-0014)의 빌드 게이트가 **snap-docker metadata-file
race** 로 모든 web 배포를 false-failure 차단하던 버그를 수정한다. compose 가 이미지를 정상 빌드·태깅한
뒤 `/tmp` metadata 파일을 (snap confinement 의 다른 mount ns 라) 못 읽어 EXIT 1 을 반환하는데, 기존
게이트가 exit code 만 신뢰해 "이미지 빌드 실패. ABORT" 로 죽었다. → 게이트를 **이미지 존재·정합
검증**으로 보강(exit code 보조).

## 2. Goal
- REQ-20260630T180000-build-gate-image-verify: build 게이트가 exit code 만으로 판정하지 않고, 기대 태그
  (`mysql-ai-web:<sha>`)의 존재 + GIT_COMMIT 라벨==sha 로 정합 확인. EXIT≠0 은 **로그에 metadata-file
  race 마커가 있을 때만** 양성 무시. 진짜 빌드 실패(마커 없음/이미지 부재/GIT_COMMIT 불일치)는 ABORT.

## 3. In Scope
- `bin/deploy-web.sh` `build_image()` 의 빌드 게이트 1곳(line ~242): exit-only → image-verify.
- 회귀 가드: TEST 에 positive(metadata-race 양성무시)/negative(진짜 실패 ABORT) 케이스.

## 4. Out of Scope
- snap docker confinement 정비 / apt docker-ce 이전(시스템/admin 영역 — 코드 수정과 별개, 사용자 결정).
- 다른 빌드 경로(make up/web 는 이미 동일 패턴으로 absorb — 무영향).

## 5. Inputs / 6. Outputs
- (in) `docker compose build web-a` 의 exit code + 로그 + 산출 이미지.
- (out) 이미지 정상 산출 시 통과(EXIT≠0 라도 metadata-race 면 warn+통과), 진짜 실패 시 ABORT.

## 7. Main Flow
- 빌드 → exit code 보조 + `docker image inspect mysql-ai-web:<sha>` GIT_COMMIT 라벨 검증 → 판정.
- 2차 방어: swap 후 /readyz git_commit==target sha 게이트(기존, 무변경).

## Pre-approved Changes
- 사용자 승인(2026-06-30): deploy-web.sh build false-failure 수정. deploy_scope: included.
- 본 수정 머지 후 `sudo -E bin/deploy-web.sh` 가 origin/main HEAD(대기 중 PR #481 포함)를 무중단 롤링
  배포하는 것이 라이브 검증 겸 그 배포 완수.

> 근거: snap-docker(29.3.1/compose v5.1.1/buildx v0.31.1) strict confinement 의 /tmp metadata-file
> 처리 race. dc-build 가 이미 동일 우회(`grep compose-build-metadataFile` → EXIT 무시)를 쓴다.

## migrate_phase — snap-docker `docker compose run` race 관용 (CHG-20260702T160000)
- `bin/deploy-web.sh` `migrate_phase()`: swap 전 `bin/alembic-migrate.sh upgrade` 로 expand 마이그레이션 적용. 기존엔 exit≠0 즉시 `die`(build 게이트와 달리 race 무관용).
- 보강: 1차 exit≠0 → `${MIGRATE_RETRY_BACKOFF:-5}`s backoff 후 **1회 멱등 재시도**. 재시도 exit 0 = 라이브 `alembic_version` head 도달(positive evidence; build 게이트의 image+GIT_COMMIT 정합에 대응) → swap 진행. 재시도도 실패 = 진짜 실패 → `die`(마이그레이션 미적용 상태로 절대 swap 안 함).
- 정합근거를 marker-gating 이 아닌 **head-도달 검증**으로 둔 이유: head 도달은 원인(race/transient) 무관하게 swap 안전을 참 보장하고, marker-only 는 self-healing transient 를 false-ABORT 해 더 약하다.
> 근거: `alembic-migrate.sh` 의 `gen_sql`(일회성 agent 컨테이너 `docker compose run` → `alembic --sql`)이 build 와 동일한 snap-docker /tmp metadata-file race 로 작업 성공에도 EXIT≠0 를 낼 수 있다. 2026-07-02 첫 0029→0030 적용이 이 사유로 false-ABORT(마이그레이션은 실제 head 도달).
