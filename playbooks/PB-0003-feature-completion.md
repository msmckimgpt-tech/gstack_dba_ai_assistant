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
6. **`/repo/docs/CODEBASE_MAP.md` 갱신 (필수)** — 신규 소스/모듈/외부 인터페이스 추가·삭제 시 §2~§5 표에 반영한다. 파일 구조 변경이 없으면 "변경 없음"을 확인하고 기록은 생략한다.
7. **`/repo/docs/LEARNINGS.md` 갱신 (필수)** — 이번 작업에서 발견한 mistake / pattern / quirk / preference 중 **재사용 가치가 있는 항목**이 있으면 append 한다. 해당 없으면 "추가 없음"을 체크리스트에 기록한다.
   - 항목 ID: `LRN-YYYYMMDD-NNNN`
   - Source: 커밋 해시 또는 TASK-ID 포함
   - Applies to: 영향 받는 경로/파일 명시
8. BLOCKED 항목이 있으면 `REPORT.md`에 정리하여 사람에게 전달한다.
9. AGENTS.md §16.3 Git 동기화 절차를 수행한다.
   - Step 1: 커밋 (항상)
   - Step 2: 원격 동기화 판정
   - Step 3: 자동 동기화 (조건 충족 시)
   - Step 4: 결과 기록

## Validation
- [ ] Completion Checklist 전체 항목이 체크되었다
- [ ] `CODEBASE_MAP.md`가 현재 구조를 반영한다 (또는 "변경 없음" 확인됨)
- [ ] `LEARNINGS.md`에 재사용 가능한 교훈이 기록되었다 (또는 "추가 없음" 확인됨)
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] Git 커밋이 완료되었다
- [ ] REPORT.md에 Git 동기화 결과가 기록되었다
