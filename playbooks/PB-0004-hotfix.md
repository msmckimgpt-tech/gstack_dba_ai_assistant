---
playbook_id: PB-0004
name: hotfix
description: 긴급 수정 절차
trigger: manual
scope: feature
---

# Playbook: 긴급 수정 (Hotfix)

## Prerequisites
- 프로덕션 또는 main 기준으로 즉시 수정이 필요한 결함이 발견되었다.
- 해당 결함을 추적할 GitHub bug issue가 있다.

## Steps

1. bug issue 번호를 기준으로 공개 브랜치 `issue/<issue-number>-<short-slug>`를 main에서 생성한다.
2. 병렬 작업이 필요하면 로컬/worktree 전용 내부 브랜치 `ai/<agent-id>/<issue-number>/<slice>`를 사용한다.
3. 결함의 원인을 파악하고 `REVIEW.md`에 분석 내용을 기록한다.
4. 최소 범위로 수정을 적용한다 (관련 없는 리팩토링 금지).
5. 수정 사항을 테스트한다.
6. `TEST.md` §3에 테스트 결과를 기록한다.
7. `MODIFY.md`에 변경 이력을 기록한다.
8. `REPORT.md`를 갱신한다.
9. Git 커밋한다.
   ```
   fix(<feature-id>): <결함 요약> (#<issue-number>)

   - <수정 파일>: <변경 내용>
   - docs/MODIFY.md: 이력 기록
   ```
10. 공개 `issue/*` 브랜치를 push하고 PR을 생성 또는 갱신한다.
11. `policy-contract`, `owner-agent-report`, `ai-review`, `selfhosted-runtime-smoke` 결과를 확인한다.
12. auto-merge 또는 사람 병합 후 내부 브랜치/worktree를 정리한다.

## Validation
- [ ] 결함이 해결되었다
- [ ] 수정 범위가 최소한이다 (불필요한 변경 없음)
- [ ] 테스트가 통과한다
- [ ] MODIFY.md, REVIEW.md에 기록이 완료되었다
- [ ] 공개 `issue/*` 브랜치가 push되었고 PR 상태가 확인되었다
