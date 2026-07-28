---
run_at: 2026-07-28T12:45:00+09:00
session: ai/claude/feature-0002-llm-usage-target-scope
scope: [llm-usage, target-scope, alembic-0047, instrumentation, expand-only]
verdict: PENDING-POST-DEPLOY (단위·정적 PASS / 라이브 계측 실증은 배포 후)
---

### Run (2026-07-28) — llm_usage.target_scope 도입 — 단위·정적 검증

UI 표면 변경 없음(백엔드 계측 + 집계 질의). 관리 콘솔 렌더는 직전 cycle 에서 이미 PB-0008
확정됐고 본 cycle 은 **그 화면이 쓰는 값의 출처**만 바꾼다 — 따라서 pre-deploy 는 단위·정적으로
검증하고, 라이브는 실제 워커가 신규 usage 행을 쓴 뒤 POST-DEPLOY 로 확정한다.

- `migrate-lint` — 0047 **expand-safe PASS**, head 단일성 PASS(revision 47건·중복 0·MAX_MIGRATION 일치)
- pytest **2,719 PASS / 2 skipped** · ruff clean
  - R1 기록값 우선(역해소 질의 미실행) · R2 legacy 역해소 유지 · R3 데이터소스별 행 분리 ·
    R4 컬럼 부재 폴백(rollback + target_scope 미참조 SQL 재조회)
  - 0047 계측 3케이스: 명시 인자 · ContextVar 폴백 · 96자 클립
  - 사다리 단수 회귀 가드(`_ColAbsentConn`): step_gap 부재 → 2회 rollback 후 성공,
    target 부재 → 3회 rollback 후 최소 base 성공
- 실 import + 시그니처 검증: `llm_*` 5종에 `scope_key`, `_record_llm_usage` 에 `target_scope` 존재
- 라이브 사전 상태 확인: `public.alembic_version = 0046_relationship_updated_at_if_changed`,
  `agent_runtime.llm_usage` 13컬럼(target_scope 없음) → 배포 시 0047 적용 예정

**POST-DEPLOY 확정 항목**: ① alembic head = 0047 · 컬럼 생성 ② insight/cluster 워커가 쓴 신규 행의
`target_scope` 채움률 ③ 사용 기록 API 의 `scope_source="recorded"` 등장 ④ 같은 target 이
데이터소스별로 분리되는지 ⑤ 콘솔 이동이 기록된 데이터소스로 정확히 착지.
