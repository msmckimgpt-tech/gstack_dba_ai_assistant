---
run_at: 2026-07-28T12:45:00+09:00
session: ai/claude/feature-0002-llm-usage-target-scope
scope: [llm-usage, target-scope, alembic-0047, instrumentation, expand-only]
verdict: PASS (배포본 754263ab 에서 마이그·계측·API 전 항목 라이브 실증)
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


---

### POST-DEPLOY 확정 (2026-07-28, 배포본 `754263ab`) — **PASS**

`bin/deploy-web.sh` 무중단 롤아웃 로그에
`UPDATE alembic_version SET version_num='0047_llm_usage_target_scope' WHERE ... '0046_...'` 확인.
web-a/web-b·insight-worker·ask-worker 전부 `754263ab`, soak 통과.

#### ① 마이그레이션 적용 — PASS

```
public.alembic_version        = 0047_llm_usage_target_scope
agent_runtime.llm_usage.target_scope = character varying(96)
```

#### ② 계측 e2e (배포본 코드로 실 LLM 호출) — PASS

`docker exec repo-insight-worker-1` 에서 배포된 `modules.llm` 을 그대로 호출:

| 경로 | 호출 | 기록된 target_scope |
|---|---|---|
| 명시 인자 | `llm_table_insight(payload, scope_key="diag-scope-explicit")` | `diag-scope-explicit` |
| ContextVar 폴백 | `set_active_datasource("diag-scope-ctxvar")` → `llm_table_insight(payload)` | `diag-scope-ctxvar` |

```
 id   |     task      |         target         |    target_scope
67604 | table_insight | diag_schema.diag_table | diag-scope-ctxvar
67603 | table_insight | diag_schema.diag_table | diag-scope-explicit
```

#### ③ 웹 API 노출 + 데이터소스별 행 분리 — PASS

`GET /api/admin/usage/conversations?days=1&gran=hour&day=2026-07-28 14:00`:

```json
[{"task":"table_insight","target":"diag_schema.diag_table","scope_key":"diag-scope-explicit",
  "src":"recorded","ambiguous":false,"navScope":"diag-scope-explicit","calls":1},
 {"task":"table_insight","target":"diag_schema.diag_table","scope_key":"diag-scope-ctxvar",
  "src":"recorded","ambiguous":false,"navScope":"diag-scope-ctxvar","calls":1}]
```

- `scope_source="recorded"` — 역해소가 아니라 **기록값**임이 응답에서 구분된다.
- `scope_ambiguous=false` — 기록값이므로 모호 저하가 사라진다(종전 이 부류는 107행이 모호였다).
- `nav.scope_key` 가 기록값 → 콘솔이 **정확한 데이터소스**로 착지한다.
- **같은 `target` 이 scope 별로 2행 분리** — R3(fold 키에 scope 포함)의 라이브 확증.
  0047 이전에는 한 줄로 합산돼 2호출로 뭉개졌다.

#### ④ 원장 위생

위 진단은 실 LLM 호출이라 usage 원장에 합성 2행이 남으므로 검증 후 삭제했다
(`DELETE ... WHERE target='diag_schema.diag_table' AND target_scope IN (...)` → 2행,
잔여 0 확인). 비용 집계 오염 없음.

#### ⑤ 이후 채움은 워커의 자연 진행에 의존 (정직 표기)

검증 시점의 insight 워커는 datasource 스캔 단계였고(일부 원격 DB 접속 실패로 순회 중),
아직 분석 LLM 단계에 도달하지 않아 **조직적(organic) 신규 행은 0**이다. 소급 백필을 하지 않는
설계이므로 `target_scope` 채움률은 워커가 분석을 수행하는 만큼 시간에 따라 올라간다. legacy 행은
그동안 종전 역해소로 동작한다(2단 폴백).
