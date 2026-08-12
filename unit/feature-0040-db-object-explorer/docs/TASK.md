---
doc_type: TASK
feature_id: feature-0040-db-object-explorer
feature_status: review
status: active
edit_policy: rewrite
source_of_truth: true
updated_at: 2026-08-12
---

# Task

## 9. Requested Scope

원 요청(2026-08-12, 사용자):

> 프로젝트 내 서비스에서, assistant가 DB 내부 구조를 탐색할 때 [trigger, event, agent,
> 그 외 실제 객체 등...] 등을 탐색하는 도구가 없는것으로 확인되었습니다.
> 해당 도구를 제공하되, `그래프 뷰` 에서도 해당 객체들을 배치/참조/분석할 수 있도록
> 구성해주세요.

후속 결정(같은 세션):
> 축 1 : 궁극적으로는 모든 DB 시스템에 대응되어야 합니다. 현재까지 분석된 내용을 바탕으로,
> 수행되는 역할에 따라 분류해주세요.
> 축 2 : LLM 비용 또한 궁극적으로 모든 엔드포인트에 대한 분석이 진행되어야 합니다.
> 감수하겠으며, 별도로 제외하진 말아주세요.

항목 분해:

- [x] trigger 탐색 도구 — 산출물: `search_db_objects`/`describe_db_object` role=`trigger`
- [x] event 탐색 도구 — 산출물: role=`schedule`(MySQL `information_schema.EVENTS`)
- [x] agent(작업) 탐색 도구 — 산출물: role=`schedule`(SQL Server Agent Job · msdb 고정 질의)
- [x] 그 외 실제 객체 — 산출물: 뷰·시노님·시퀀스 = role `view`/`alias`/`generator`
- [x] 그래프 뷰 **배치** — 산출물: 스키마 클러스터 구리 칩 + 역할 아이콘 (실 Chrome 실증)
- [x] 그래프 뷰 **참조** — 산출물: `OBJECT_USES`(실선) · `OBJECT_ON`(파선) 분리 투영
- [x] 그래프 뷰 **분석** — 산출물: node_analysis 스키마 시드 편입 + 역할별 payload
- [x] 축1 역할 기반 분류 — 산출물: `db_object_roles.py` 6역할 · 지원상태 4종 · dialect 매핑
- [x] 축2 LLM 분석 미제외 — 산출물: 시드 편입(제외 없음), 기존 schema cap 만 유지

## 1. Current Status

코드·단위검증 + **실 Windows Chrome 시각·인터랙션 검증 완료**(integration-harness 경로 —
`unit/feature-0003-agent-web-ui/docs/test-runs.d/20260812T0310-*.md`). **배포는 미수행**이며,
라이브 실데이터 반영 확인은 배포 후 POST-DEPLOY 대상(TEST.md §3).

## 2. Implementation Plan

### 2.1 변경 파일

**신규**
- `unit/feature-0002-agent-core/src/modules/db_object_roles.py` — 역할 taxonomy SSOT
- `unit/feature-0002-agent-core/src/modules/db_objects.py` — introspection → SSOT
- `unit/feature-0002-agent-core/alembic/versions/20260812_0054_db_objects.py` — 테이블+AGE 라벨
- `unit/feature-0002-agent-core/tests/test_db_object_explorer.py` — 56 케이스
- `unit/feature-0003-agent-web-ui/tests/headless/test_g6build_dbobjects.js` — 21 단언

**수정**
- `modules/dialects.py` — `object_support`/`list_objects`/`object_definition`/`_agent_jobs_sql`
- `modules/tools.py` — 도구 2종 + 핸들러 + 정의 등록 + `_window_routine_output(tool_name=)`
- `modules/metadata_graph.py` — `sync_db_object` · sync step 3c · `schema_tables` · `_node_from_props` · `schema_db_object_keys`
- `modules/insight.py` — introspect 훅 + 허용 DB 목록 산출
- `modules/node_analysis.py` — 시드·실재검증·라벨 폴백·payload·관계 채점
- `shared/config.py` — `AGENT_DB_OBJECT_INTROSPECT_{ENABLED,CAP}`
- `static/graph/{graph-core,graph-roleviz,graph-state,graph-ctxmenu}.js` · `graph.css` · `admin.html`
- `tests/headless/test_catcluster_panel_scroll.js` — 인자 pin 완화(아래 §4)

### 2.2 위험도

**Major** (§12.3) — 다중 파일 + 스키마 추가 + 그래프/프론트. 파괴적 변경·인증 변경 없음.
마이그레이션은 expand-safe(`migrate-lint` PASS).

## 3. 잔여 / 이연

- **라이브 실데이터 반영 확인** — 실 브라우저 렌더·인터랙션 계약은 검증 완료. 배포 +
  마이그레이션 0054 + insight cadence 이후 실 스키마 데이터로 재확인 필요(TEST.md §3).
- **change-reanalysis 3축 확장** — 현재 스냅샷은 테이블·루틴 2축. 역할 객체 변경이
  자동 재분석을 트리거하지는 않는다(주기 introspect 로는 SSOT·그래프에 반영됨).
  `db_objects.introspect_and_store` 는 `inventory_sink` 를 이미 지원하므로 후속 cycle 이
  스냅샷을 3축으로 확장하면 호출부만 바꾸면 된다.
- **PostgreSQL·Oracle 방언** — 역할 축·API 는 수용 가능하게 설계됨. 실제 지원 시 추가.

## 4. 타 feature 파일 수정 사유

`tests/headless/test_catcluster_panel_scroll.js` 의 단언 2건이
`_metaGraphRenderClusterDetail` 의 **인자 목록 전체를 pin** 하고 있어, 무관한 인자
(`dbObjects`) 1개 추가만으로 FAIL 했다. 지키려던 불변식은 "focusFam 이 호출자→렌더러로
관통한다" 이므로 **"focusFam 이 마지막 인자"** 로 좁혔다. 역검증:
- 내 번들 PASS · **baseline 번들도 PASS**(하위호환) · **focusFam 제거 시 FAIL**(보호 유지).

## 7. Completion Checklist

- [x] 모든 REQ 의 AC 가 구현되었다
- [x] 자동 테스트가 통과한다 (아래 TEST.md)
- [x] 웹/UI 변경 시 실제 Windows 브라우저 검증 — **수행**(실 Chrome 150 · WebGL · 스크린샷 2매)
- [x] FUNCTION.md 가 현재 동작과 일치한다
- [x] MODIFY.md 에 변경 이력이 기록되었다
- [x] REVIEW.md 에 판단 근거가 기록되었다
- [x] REPORT.md 에 최종 상태가 반영되었다
- [x] TEST.md 에 테스트 결과가 기록되었다
- [x] BLOCKED 항목 없음
- [x] STATUS.md 에 기능 상태가 갱신되었다
- [x] ANCHOR.md §1~§3 이 채워져 있다
