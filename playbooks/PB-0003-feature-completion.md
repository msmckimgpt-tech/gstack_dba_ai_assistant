---
playbook_id: PB-0003
name: feature-completion
description: 기능 완료 점검 및 Git 동기화
trigger: manual
scope: feature
---

# Playbook: 기능 완료 및 동기화

## Prerequisites
- 기능 구현이 완료되었다.
- 테스트가 작성/실행되었다.

## Steps

1. `TASK.md` Completion Checklist를 하나씩 확인하며 체크한다.
2. `FUNCTION.md`가 현재 동작과 일치하는지 검증한다.
3. `TEST.md` §3에 최종 테스트 결과를 기록한다.
4. `REPORT.md`를 최종 상태로 갱신한다.
5. `/repo/docs/STATUS.md`에서 기능 상태를 `done` 또는 `review`로 변경한다.
6. BLOCKED 항목이 있으면 `REPORT.md`에 정리하여 사람에게 전달한다.
7. AGENTS.md §16.3 Git 동기화 절차를 수행한다.
   - Step 1: 커밋 (항상)
   - Step 2: 원격 동기화 판정
   - Step 3: 자동 동기화 (조건 충족 시)
   - Step 4: 결과 기록

## Validation
- [ ] Completion Checklist 전체 항목이 체크되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] Git 커밋이 완료되었다
- [ ] REPORT.md에 Git 동기화 결과가 기록되었다
