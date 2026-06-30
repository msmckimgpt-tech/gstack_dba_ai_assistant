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
