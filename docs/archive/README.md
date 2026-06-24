---
doc_type: ARCHIVE_INDEX
scope: project
status: active
edit_policy: append
source_of_truth: false
---

# docs/archive/ — 아카이브 보관소

> SSOT 계약(ADR-0031 §3 + Addendum)의 archived 자산 격리 위치. **git 추적됨**(이력 보존).
> 여기 문서는 정본이 아니다(`source_of_truth: false`, `lifecycle: archived`). 현재 정본은
> `docs/DOC_REGISTRY.md` 참조.

> 주의: `_archive/`(언더스코어)는 `.gitignore` 로 무시되는 **로컬 임시 보관**용이다. 추적 보존은 본
> `docs/archive/`(언더스코어 없음)를 쓴다.

## 보관 목록
| 문서 | 원위치 | 보관 사유 | 보관일 |
|---|---|---|---|
| GOAL.md | repo 루트 | archived (TASK-0133) — 이미 출하된 8기능을 미구현으로 표기해 /goal 오도 유발 | 2026-06-24 |
| OBSERVATIONS.md | docs/ | 2026-03~04 스냅샷, 50일+ stale | 2026-06-24 |
