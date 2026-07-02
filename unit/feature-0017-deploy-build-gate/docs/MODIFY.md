---
doc_type: MODIFY
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260630T180000-deploy-build-gate
- Date: 2026-06-30
- Related Requirement: REQ-20260630T180000-build-gate-image-verify
- Summary: deploy-web.sh 빌드 게이트를 exit-only → 이미지 존재·GIT_COMMIT 정합 검증으로 보강
  (snap-docker metadata-file race false-failure 차단 해소).
- Files: `bin/deploy-web.sh`(build_image 게이트 1곳), `unit/feature-0017-deploy-build-gate/docs/*`
- Impact:
  - 배포 차단 해소 — 이 호스트의 모든 web 배포가 다시 가능. 비파괴(빌드 판정 로직만).
  - false-positive 방지: 양성무시는 (EXIT≠0) AND (이미지 존재+GIT_COMMIT==sha) AND (로그 metadata-race
    마커) 3중 조건. 진짜 실패(마커 없음/이미지 부재)는 ABORT. swap 후 /readyz git_commit 가 2차 방어.
  - swap/rollback/soak 경로 무변경.
- Rollback Notes: build_image 게이트를 `build || die` 한 줄로 revert(단 그러면 snap 환경 배포 재차단).

## CHG-20260702T160000-deploy-migrate-gate
- Date: 2026-07-02
- Related Requirement: migrate 게이트에도 build 게이트와 동일한 snap-docker `docker compose run` race 관용 확장(관측 기반 후속).
- Summary: deploy-web.sh `migrate_phase` 를 exit-only die → **1차 exit≠0 시 backoff 후 멱등 재시도로 head 도달 판정**(head 도달=swap 안전 positive evidence)으로 보강. build 게이트(CHG-20260630T180000-deploy-build-gate)와 동일 계보 — `alembic-migrate.sh` 의 `gen_sql`(일회성 agent 컨테이너 `docker compose run` 으로 `alembic --sql` 생성)이 같은 metadata-file race 로 false-ABORT 하던 gap 해소.
- 관측: 2026-07-02 eadb4a9e 첫 배포가 0029→0030(#526 latency_ms) 적용 시 exit≠0 로 false-ABORT(swap **전** 중단 — 라이브 무영향). 마이그레이션은 실제 head 도달(`alembic_version=0030`)했고 재배포로 완주. migrate 게이트가 build 게이트와 달리 race 무관용이던 것이 근본 gap.
- Files: `bin/deploy-web.sh`(migrate_phase 1곳, +19/-1), `docs/STATUS.md`, `unit/feature-0017-deploy-build-gate/docs/*`.
- Impact: migrate 게이트 false-ABORT 해소(멱등 재시도 tolerance + backoff). **안전**: 재시도 exit 0 = 라이브 alembic_version 이 실제로 head 일 때만(alembic-migrate.sh 멱등·head-anchored: no-pending 은 live_current 로 head 확인, apply 는 ON_ERROR_STOP=1 psql 성공 후 fall-through) → 마이그레이션 미적용 상태로 절대 swap 안 함. 진짜 실패(gen-time alembic 오류 / apply-time psql 오류)는 1·2차 모두 die. swap/rollback/soak/build 게이트 무변경.
- Rollback: migrate_phase 를 `run bash bin/alembic-migrate.sh upgrade || die "…"` 한 줄로 revert(단 race false-ABORT 재발).
