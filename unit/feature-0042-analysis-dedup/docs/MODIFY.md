---
doc_type: MODIFY
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260814-0001
- Date: 2026-08-14
- Related Requirement: REQ-20260814-batch-verdict · REQ-20260814-dedup-verdict · REQ-20260814-cache-spike
- Summary: 워커 LLM 요청 batch 화 검토 → 두 해석 모두 기각. 그 검토가 드러낸 요청당 낭비를 회수할
  후보 3개를 ROADMAP T4 로 등재하고, 각 후보의 전제를 라이브 실측으로 재검사해 판정했다
  (ITEM-13 기각 · ITEM-14 완료 · ITEM-15 방향 확정 후 보류).
- Files:
  - `docs/improvements/analysis-orchestration/ROADMAP.md` (T4 신설 + 판정 반영)
  - `unit/feature-0042-analysis-dedup/docs/{FUNCTION,TASK,TEST,REVIEW,REPORT,MODIFY,DECISIONS,ANCHOR}.md` (신규)
- Impact: **런타임 무영향** — 코드 변경 0건. 변경 파일은 문서뿐이며 실행 경로가 읽지 않는다.
  후속 영향은 ITEM-15 착수 시 발생한다(프롬프트 재구성 + 캐시 계측).
- Rollback Notes: 문서 revert 로 충분. 되돌릴 런타임 상태 없음.

## CHG-20260814-0002
- Date: 2026-08-14
- Related Requirement: REQ-20260814-cache-spike (후속 — ITEM-15 착수 조건 확정)
- Summary: ITEM-15 의 선행 안전망을 두 선택지 중 **출력 계약 회귀 테스트 신설**로 확정했다.
  대안(증거 커버리지 확대)은 워커가 시간을 두고 채우는 축이라 착수 시점을 통제할 수 없고
  ITEM-15 를 무기한 대기시킨다. 회귀 테스트는 지금 만들 수 있고 LLM 없이 결정론적으로 판정한다.
- Files:
  - `docs/improvements/analysis-orchestration/ROADMAP.md` (ITEM-15 선행 확정)
  - `unit/feature-0042-analysis-dedup/docs/REPORT.md` (§4 Open Issues 갱신)
  - `unit/feature-0042-analysis-dedup/docs/TASK.md` (TASK-0007)
- Impact: 런타임 무영향. 다음 cycle 의 착수 대상이 확정됨.
- Rollback Notes: 문서 revert 로 충분.
