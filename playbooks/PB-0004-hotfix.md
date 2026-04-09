---
playbook_id: PB-0004
name: hotfix
description: 긴급 수정 절차
trigger: manual
scope: feature
---

# Playbook: 긴급 수정 (Hotfix)

## Prerequisites
- 프로덕션 또는 main 브랜치에서 즉시 수정이 필요한 결함이 발견되었다.

## Steps

1. `fix/<feature-id>-<short-desc>` 브랜치를 main에서 생성한다.
2. 결함의 원인을 파악하고 `REVIEW.md`에 분석 내용을 기록한다.
3. 최소 범위로 수정을 적용한다 (관련 없는 리팩토링 금지).
4. 수정 사항을 테스트한다.
5. `TEST.md` §3에 테스트 결과를 기록한다.
6. `MODIFY.md`에 변경 이력을 기록한다.
7. `REPORT.md`를 갱신한다.
8. Git 커밋한다.
   ```
   fix(<feature-id>): <결함 요약>

   - <수정 파일>: <변경 내용>
   - docs/MODIFY.md: 이력 기록
   ```
9. main에 병합하고 push한다.
10. 핫픽스 브랜치를 정리한다.

## Validation
- [ ] 결함이 해결되었다
- [ ] 수정 범위가 최소한이다 (불필요한 변경 없음)
- [ ] 테스트가 통과한다
- [ ] MODIFY.md, REVIEW.md에 기록이 완료되었다
- [ ] main에 병합되고 push되었다
