---
doc_type: TASK
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude) / Human approved
- Priority: high (모든 web 배포 차단 중)
- Last Updated: 2026-06-30

## 2. Implementation Plan
### 2.1 Plan
- **영향 파일:** `bin/deploy-web.sh`(build_image 게이트), 본 feature docs.
- **접근:** build 후 exit code 만 die 트리거로 쓰지 않고, `docker image inspect mysql-ai-web:<sha>` 의
  GIT_COMMIT 라벨==sha 로 정합 확인. EXIT≠0 은 로그에 metadata-file race 마커가 있을 때만 양성 무시.
  진짜 실패는 ABORT. (코드베이스 dc-build 우회 패턴과 정합.)
- **위험도:** Major (배포 스파인 — false-positive 로 실패 빌드를 통과시키면 안 됨. 마커+이미지정합 2중 조건 + /readyz 2차 방어).

<!-- PLAN-APPROVED by ms.mckim.gpt (user) on 2026-06-30 — deploy-web.sh build false-failure 수정 -->

## 3. Task Queue
- [x] TASK-20260630T180100-build-gate: build_image 게이트 image-verify 로 보강
- [x] TASK-20260630T180101-validate: positive(metadata-race 재현·양성무시) + negative(이미지 부재 ABORT) 격리 검증
- [ ] TASK-20260630T180102-live: 머지 후 sudo -E deploy-web.sh end-to-end(롤링 swap + /readyz git_commit 전환)

## 4. In Progress
- 문서 → verify-completion → 머지 → 라이브 end-to-end.

## 5. Blocked
- 없음.

## 6. Done
- 근본원인(snap metadata-file race) 확인 + 게이트 수정 + 격리 검증(EXIT1+이미지정상+마커→PASS / 부재→ABORT).

## 7. Next Action
- verify-completion → 머지 → `sudo -E bin/deploy-web.sh` 라이브 완주 검증.

## 8. Completion Checklist
- [ ] 정적검증(bash -n) + 격리 positive/negative 검증
- [ ] FUNCTION/MODIFY/REVIEW/REPORT/TEST 정합
- [ ] STATUS.md 갱신
- [ ] verify-completion PASS
- [ ] commit/push/PR/merge
- [ ] 라이브 end-to-end 배포 검증(롤링 swap 완주 + /readyz git_commit==origin/main HEAD)
