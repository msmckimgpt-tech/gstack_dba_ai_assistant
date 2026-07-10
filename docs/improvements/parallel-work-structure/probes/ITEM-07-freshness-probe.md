---
doc_type: ACCEPTANCE_PROBE
initiative: parallel-work-structure
item: ITEM-07
created_at: 2026-07-11
---

# ITEM-07 신선도 hard gate 라이브 실증 probe

본 파일은 acceptance (b) "behind ≥ 20 브랜치가 자동 update-branch 경유 후 머지" 의
라이브 재현 산출물이다. 이 PR 의 브랜치는 의도적으로 `main~25` 에서 분기해 생성됐고,
`bin/cycle-finalize.sh` (META-0027) 의 머지 mutex 구간이 behind 를 감지해
`gh pr update-branch` → CI 재확인(CLEAN) → 머지를 강제하는 경로를 실증한다.
이 파일 자체가 그 실행 기록의 증거 artifact 로 저장소에 남는다.
