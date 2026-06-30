---
doc_type: REPORT
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
deploy-web.sh 빌드 게이트의 snap-docker metadata-file race false-failure 수정(이미지 존재·정합 검증).
이 버그는 이 호스트의 모든 web 배포를 차단하고 있었다(feature-0003 PR #481 포함). 격리 검증 완료, 라이브
end-to-end 배포 검증 대기.

## 2. Progress
- Done: build_image 게이트 수정 + 격리 검증(positive: EXIT1+이미지정상+마커→양성무시 / negative: 부재→ABORT).
- In Progress: verify-completion → 머지 → 라이브 `sudo -E bin/deploy-web.sh` 완주 검증.

## 3. Recent Changes
- `bin/deploy-web.sh` build_image: `build || die` → build(exit 흡수, tee 로그) + `docker image inspect
  mysql-ai-web:<sha>` GIT_COMMIT 라벨 검증 + metadata-race 마커 조건부 양성무시 + 진짜 실패 ABORT.
- 총 변경 횟수: 1 (CHG-20260630T180000)

## 4. Open Issues
- 라이브 검증은 머지 후 수행(deploy-web.sh 가 origin/main HEAD 로 coalesce 하므로 본 수정이 main 에 있어야).
- snap docker → apt docker-ce 이전은 시스템 영역(코드와 별개, 사용자 결정 권장 — 근본 환경 정비).

## 5. Test Status
- 정적: bash -n OK.
- 격리(main repo, .env 보유 재현): compose build EXIT=1 + `open /tmp/.tmp-compose-build-metadataFile-…:
  no such file`(정확한 보고 에러) + 이미지 GIT_COMMIT 라벨 일치 + 마커 검출 → 새 게이트 PASS(양성무시).
  음성: 존재 안 하는 sha → GIT_COMMIT 빈값 → ABORT(진짜 실패 보존).
- 라이브(배포 시): end-to-end deploy-web.sh 롤링 swap 완주 + /readyz git_commit==origin/main HEAD.

## 6. Git 동기화 결과
- (commit/PR 시 갱신)
