---
playbook_id: PB-0001
name: new-feature-unit
description: 새로운 기능 유닛 생성
trigger: manual
scope: project
---

# Playbook: 새로운 기능 유닛 생성

## Prerequisites
- 기능 목적과 ID가 결정되었다 (형식: `feature-NNNN-<purpose>`)
- 요구사항(REQ)이 최소 1개 정의되었다

## Steps

1. `/repo/unit/_template`를 `/repo/unit/<feature-id>/`로 복사한다.
2. 복사된 모든 docs/ 파일의 메타데이터에서 `feature_id`를 실제 값으로 치환한다.
3. `FUNCTION.md` §2 Goal에 REQ를 등록한다.
4. `TASK.md` §1의 상태를 `planned`로 설정한다.
5. `/repo/docs/STATUS.md`에 기능 행을 추가한다.
6. `/repo/docs/ARCHITECTURE.md` §6 의존성 맵에 해당 기능을 등록한다 (의존이 있는 경우).
7. `/repo/docs/CODEBASE_MAP.md` §4에 기능 항목을 추가한다.
8. Git 커밋한다.
   ```
   feat(<feature-id>): 기능 유닛 초기화 (#<issue-number>)

   - unit/<feature-id>/: _template 기반 초기 구조 생성
   - docs/STATUS.md: 기능 등록
   ```

## Validation
- [ ] 모든 docs/ 파일의 메타데이터 `feature_id`가 올바르다
- [ ] STATUS.md에 기능이 등록되었다
- [ ] Git 커밋이 완료되었다
