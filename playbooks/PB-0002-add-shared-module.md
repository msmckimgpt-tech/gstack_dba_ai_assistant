---
playbook_id: PB-0002
name: add-shared-module
description: shared/ 공통 모듈 추가
trigger: manual
scope: project
---

# Playbook: shared/ 공통 모듈 추가

## Prerequisites
- 두 개 이상의 기능에서 동일 로직이 사용되거나 사용될 예정이다.
- 모듈의 책임 범위가 명확하다.

## Steps

1. `/repo/shared/<module-name>/`을 생성한다.
2. 모듈 코드를 작성한다.
3. `/repo/shared/README.md`에 모듈 목적과 사용법을 추가한다.
4. `/repo/shared/MODIFY.md`에 변경 이력을 기록한다.
5. 기존 기능에서 중복 코드를 shared 모듈 참조로 교체한다.
6. 영향받는 기능의 `MODIFY.md`에 변경을 기록한다.
7. 영향받는 기능의 `REPORT.md`에 shared 의존 추가를 알린다.
8. `/repo/docs/CODEBASE_MAP.md` §3에 모듈을 등록한다.
9. Git 커밋한다.
   ```
   refactor(shared): <module-name> 공통 모듈 추출 (#<issue-number>)

   - shared/<module-name>/: 신규 공통 모듈
   - <feature-ids>: shared 참조로 전환
   ```

## Validation
- [ ] shared/README.md에 모듈이 문서화되었다
- [ ] shared/MODIFY.md에 이력이 기록되었다
- [ ] 기존 기능의 중복 코드가 제거되었다
- [ ] 영향받는 기능의 테스트가 통과한다
