---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260703T115500-ai-claude-feature-0016-graphux6-postdeploy
- Date: 2026-07-03
- Related Requirement: graphux6-panelbottom-responsive-obs(§40) 배포 후 PB-0008 실 Windows 실측 결과 기록(deploy-backed 증적). 코드 무변경 — doc-only.
- Summary: PR #570 머지(9e1156d6) 후 배포 완수 — `make migrate`(agent 재빌드→live alembic_version 0031→**0032** 확인, stale image 회피) + `make deploy-web`(무중단 롤링, soak 90s 통과) + `make insight-up`(insight-worker 9e1156d6 재빌드, ③ target 기록 반영). **라이브 PB-0008 실 Windows PASS 3/3**: ① progress 최하단(progressIsLastChild) ② 캔버스 flex-fill 415px=pane 바닥(잘림 0)·제약 시 200 floor 축소 ③ 최근활동 '테이블 분석' `schema.table` 실데이터 표시(계정분석 PII 공백). feature-0003 TEST.md §3 Run + TASK §40 T40.11 완료.
- Files: `unit/feature-0003-agent-web-ui/docs/TEST.md`, `unit/feature-0016-metadata-graph/docs/TASK.md`, `unit/feature-0016-metadata-graph/docs/MODIFY.md`.
- Impact: 문서만. 코드·스키마·배포 무변경(배포는 이미 완료된 것을 기록).
- Rollback Notes: 해당 없음(기록).

## CHG-20260703T105541-ai-claude-feature-0016-graphux6-panelbottom-responsive-obs
- Date: 2026-07-03
- Related Requirement: 사용자 요청 3건 — ① 그래프뷰 'AI 능동 분석' 패널을 상세 패널 하단으로(상단 배치가 노드 상세를 밀어냄), ② 그래프 UI 고정높이→화면 반응형(세로 좁은 뷰포트 하단 잘림), ③ AI 운영 현황 최근 활동에 '테이블 분석'·'노드 분석' 대상 표시. 정본 TASK §37.
- Summary:
  - ① [admin.html] `#metadataGraphProgress` 를 `#metadataGraphDetailBody` 위→아래(aside 최하단) 이동(JS 무변경). [styles.css] progress 여백 margin-bottom→margin-top.
  - ② [styles.css] `.admin-meta-graph`·`.admin-meta-graph-body` flex-fill + body `grid-template-rows: minmax(0,1fr)`, 캔버스·상세 고정 height 제거(min-height:0) → pane 가용높이 반응(짧은 뷰포트 축소·미절단). G6 autoResize 로 JS 무변경. 좁은화면(≤900px) 세로스택 보존 + 그래프 모드 `:has()` pane 스크롤.
  - ③ [migration 0032] `agent_runtime.llm_usage.target VARCHAR(200)` additive nullable(task 저카디널리티 KPI 집계와 분리) + 부트스트랩 DDL parity. [llm.py] `_record_llm_usage(target=)` + 자가치유 INSERT(target 실패→rollback→제외 재INSERT), schema/table/node insight call site 대상 추출(account 은 PII 제외). [ai_ops.py] `_query_activity` target SELECT + 컬럼부재 폴백. [admin.js] 최근활동 행·상세 대상 표시.
- Files: `unit/feature-0003-agent-web-ui/src/static/{admin.html,styles.css,admin.js}`, `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py`, `unit/feature-0002-agent-core/src/modules/llm.py`, `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql`, `unit/feature-0002-agent-core/alembic/versions/20260703_0032_llm_usage_target.py`, `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py`.
- Impact: ①② 프론트 비파괴(데이터/API/스키마 불변). ③ additive nullable 마이그레이션(기존 INSERT/SELECT 무영향, 배포순서 역전·stale image 자가치유). KPI·taxonomy 집계 무영향.
- Rollback Notes: 프론트는 커밋 되돌림. 마이그 0032 는 nullable·미참조 무해 — 이미지 롤백만 하고 downgrade 불필요(컬럼 잔존 무영향). 필요 시 `DROP COLUMN IF EXISTS target`.

## CHG-20260703T170000-ai-root-feature-0016-colexpand-postdeploy
- Date: 2026-07-03
- Related Requirement: reldetail-colexpand(§35) 배포 후 PB-0008 실 Windows 실측 결과 기록(deploy-backed 증적). 코드 무변경 — doc-only.
- Summary: feature-0003 TEST.md reldetail-colexpand Run 에 POST-DEPLOY PASS(4항목) 기록 + TASK §35 T35.8 완료. 스크린샷 5매.
- Files: `unit/feature-0003-agent-web-ui/docs/TEST.md`, `unit/feature-0016-metadata-graph/docs/TASK.md`.
- Impact: 문서만. 코드·배포 무변경.
- Rollback Notes: 해당 없음(기록).

## CHG-20260703T165147-ai-root-feature-0016-reldetail-colexpand
- Date: 2026-07-03
- Related Requirement: 사용자 요청 4건 — 상세 패널 관계를 ① 컬럼 클릭 시 펼침 ② 참조함/참조받음 구분
  ③ 방향별 개수 ④ hover 툴팁=관계 의미 분석.
- Summary: `_metaGraphRenderDetail` 관계 렌더를 재구성 — 관계를 self측 컬럼별로 그룹화(colRel), 컬럼(N)
  목록을 아코디언(관계 있는 컬럼 🔗+토글+`→N ←M` 개수 배지, 클릭 펼침)으로, 각 컬럼 안에서 참조함(→)/
  참조받음(←) 분리·개수. 전체 관계 요약 배지. 신규 `_metaRelSemanticTip`(방향 문장+근거+신뢰도+
  cardinality+근거별 의미)를 관계 행 native title 로. 컬럼 self 는 방향 그룹 직접 표시. 아코디언 토글 바인딩.
- Files: `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}`.
- Impact: 프론트 전용·비파괴·마이그레이션 0·백엔드 무변경. 기존 관계 추적(클릭)·AI 박스 무영향. 배포=web.
- Rollback Notes: 코드 롤백 = 이전 커밋 재빌드.

## CHG-20260703T163000-ai-root-feature-0016-reltrace-postdeploy
- Date: 2026-07-03
- Related Requirement: graph-reltrace(§32)+reltrace-tabledetail(§33) 배포 후 PB-0008 실 Windows 라이브
  실측 결과 기록(deploy-backed 완료 증적). 코드 변경 없음 — doc-only.
- Summary: feature-0003 TEST.md reltrace-tabledetail Run 에 POST-DEPLOY PASS(3항목 통합) 기록 +
  TASK §33 T33.5 완료 체크. 스크린샷 5매 아카이브(01 접힌관계·02 테이블상세관계·03/04 추적·05 AI추적).
- Files: `unit/feature-0003-agent-web-ui/docs/TEST.md`, `unit/feature-0016-metadata-graph/docs/TASK.md`.
- Impact: 문서만. 코드·배포 무변경.
- Rollback Notes: 해당 없음(기록).

## CHG-20260703T160000-ai-root-feature-0016-reltrace-tabledetail
- Date: 2026-07-03
- Related Requirement: graph-reltrace(CHG-20260703T152607) PB-0008 후속 — 테이블 노드 단일클릭 상세에
  "관계(N)" 섹션 미표시 갭(depth=1 fetch 는 테이블 기준 2-hop REFERENCES 미포함).
- Summary: `_metaGraphRenderDetail`/`_metaGraphShowRelations` 가 fetched edges 에 더해 **모델
  (_metaGraph.edges)에서 self(테이블이면 자기 컬럼 포함)에 닿는 REFERENCES 를 병합**(dedup·broken 제외)
  → 테이블 단일클릭 상세/관계 상세에 관계 행 표시(기존 추적 행 렌더 그대로). counter 노드명 모델 폴백.
- Files: `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html}`.
- Impact: 프론트 전용·비파괴·마이그레이션 0. 배포 = web 재빌드만.
- Rollback Notes: 코드 롤백 = 이전 커밋 재빌드.

## CHG-20260703T152607-ai-root-feature-0016-graph-reltrace
- Date: 2026-07-03
- Related Requirement: 사용자 후속 3건 — ① 테이블 접힌 상태에서도 연결 관계 표시(더블클릭 전 미표시 이슈),
  ② 상세 패널 관계 클릭 시 대상 테이블·컬럼 추적, ③ AI 능동 분석으로도 작동.
- 근본원인(①): REFERENCES 는 Column→Column 이라 `_metaG6Build` 가 양끝 컬럼 렌더 시에만 엣지를 그렸고,
  `schema_tables`(스키마 펼침)는 HAS_TABLE 만 반환 → 접힌 테이블엔 관계 데이터 자체가 모델에 없었다.
- Summary:
  (1) **백엔드**(metadata_graph.py `schema_tables`): 스키마 펼침 응답에 스키마 내 컬럼에서 나가는
  REFERENCES 엣지(Column→Column, FK null-status 포함·broken 제외·`edge_cap` 캡)를 추가.
  (2) **프론트 ①**(`_metaG6Build`): REFERENCES 끝점을 렌더된 id 로 해소 — 컬럼 미렌더 시 소속 테이블로
  승격(키 문자열에서 부모 도출), 같은 두 끝점 다수 컬럼-쌍은 하나로 dedupe(최강 상태·count·pairs).
  intra-table 자기참조 제외. → 접힌 테이블 간 관계 엣지 렌더.
  (3) **프론트 ②**(신규 `_metaGraphTraceRelation`/`_metaGraphBindTraceRows`): 관계 클릭 → 대상 테이블을
  이웃과 함께 화면에 가져오고 컬럼 전개 + 대상 컬럼 강조·카메라 focus. 상세 패널 "관계(N)" 행 +
  "관계 상세" 행 공통 추적(showDetail→trace 통일).
  (4) **프론트 ③**(`_metaGraphLoadNodeAnalysis`): AI 능동 분석 결과 박스에 구조화된 관계를 추적 가능 행
  (`_metaGraphRelTraceRowsHTML`)으로 노출 → 분석 결과에서도 대상 추적.
  (5) styles.css 추적 행 hover·힌트 + admin.html 캐시버스터 `20260703-graph-reltrace`.
- Files: `unit/feature-0002-agent-core/src/modules/metadata_graph.py`,
  `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}`.
- Impact: 데이터 비파괴·마이그레이션 0. 백엔드는 schema_tables 응답에 엣지 추가(읽기 전용 투영).
  배포 = web 재빌드(백엔드 metadata_graph 포함 → 워커도 재빌드 권장). 접힌 관계 데이터 피드가 늘어
  스키마 펼침 payload 소폭 증가(cap 으로 제한).
- Rollback Notes: 코드 롤백 = 이전 커밋 재빌드. 프론트 캐시버스터 되돌림.

## CHG-20260702T100500-ai-root-feature-0016-probe-mssqlfix
- Date: 2026-07-02
- Related Requirement: rel-selfheal(CHG-20260702T052630) 배포 후 라이브 검증에서 적발된 잠복 결함 —
  MSSQL 프로브 SQL 이 오류 130("Cannot perform an aggregate function on an expression containing
  an aggregate or a subquery")으로 **전면 실패**(insight-worker 로그 다수 실측; B-F7 경고 로깅이
  노출 — 파이프라인 정지 동안 한 번도 실행되지 않아 숨어 있던 결함).
- Summary: `dialects.MSSQLDialect.probe_relationship_overlap` 재작성 — `SUM(CASE WHEN EXISTS ...)`
  (집계식이 서브쿼리 포함 = MSSQL 금지)를 CASE/EXISTS 를 파생 테이블 내부로 내리고 바깥에서
  `SUM(s.m)` 단순 컬럼 집계로 변경. 의미(표본 TOP n 중 tgt 겹침 수) 동일. MySQL 경로 무변경.
  회귀 테스트 1건 추가(집계가 서브쿼리 식을 직접 감싸지 않음 + CASE 는 파생 테이블 내부).
  실패 기간의 후보들은 B-F4/R-1 가드 덕에 failed 집계+timestamp 전진만 발생(오파단 0) —
  hotfix 후 rotation 으로 자연 재프로브된다.
- Files: `unit/feature-0002-agent-core/src/modules/dialects.py`,
  `unit/feature-0002-agent-core/tests/test_relationships.py`.
- Impact: 백엔드 전용·비파괴. MSSQL 프로브(자기교정의 능동 검증 경로) 최초 실가동. 배포 =
  insight/ask-worker 재빌드.
- Rollback Notes: 코드 롤백 = 이전 커밋 재빌드(구 SQL 은 MSSQL 에서 전면 실패라 롤백 실익 없음).

## CHG-20260702T052630-ai-claude-feature-0016-rel-selfheal
- Date: 2026-07-02
- Related Requirement: CHG-20260702T024556 의 §18.8 적대 리뷰 패널(3렌즈 backend/security/qa, resume
  세션 재실행 — 원 세션은 dispatch 직후 session limit 중단) 발견 반영. backend verdict **FAIL**(MAJOR 6,
  2건 실행 재현) — 필수 발견 전량 수정 + 커버리지 보강.
- Summary:
  (1) **B-F1**: instance-scan interval 커서를 DB(catalog)별 분리(`insight._instance_scan_cursor_key`) —
  ds-단위 단일 커서는 MSSQL multi-DB 순회에서 같은 cycle 의 첫 DB 스탬프가 나머지 DB 를 영원히 가로채
  (항상 DB#1 만 interval 스캔), cadence 목표(기존 스키마 상시 유지보수)가 DB#2+ 에서 구조적 미달성.
  MySQL 은 기존 키 불변(하위호환).
  (2) **B-F2**: `apply_relationship_signal(a_schema=, b_schema=)` — 강화/파단 write-back 을 스키마-slot
  까지 한정('' 레거시=wildcard, 미지정=기존 동작). 프로브·대화학습 호출부가 slot 전달 — 교차-DB 동명
  테이블(23-DB dbo.T_ErrorLog 류) 오염 전파 차단.
  (3) **B-F3**: `_GENERIC_KEY_COLS` 에 `uniqueid`/`unique_id` — heuristic-2(shared_key)의 PK≡PK
  pairwise 쓰레기(실행 재현: Achievement 3테이블에서 3건) 차단. name_fk 타깃 역할은 유지.
  (4) **B-F4**: 프로브 실행 예외 처리 — 객체-부재류(`_PROBE_MISSING_OBJECT_RE`: invalid object/
  doesn't exist/42S02 등)는 **negative 신호**, 그 외 transient 는 failed 집계, 모든 실패에
  `last_validated_at` 전진(`_touch_validated`) — 실행 불가 edge 의 영구 미파단 + NULLS FIRST 큐
  head 고착(프로브 기아) 동시 차단.
  (5) **Sec-F2**: probe_and_reinforce 에 cap≤500·sample≤200·timeout≤60s 코드 클램프.
  (6) **QA-F4**: `learn_relationships_from_sql(normalize_schema_lower=)` — MSSQL 경로(agent_core 가
  engine 판단) slot lower() 정규화, phantom 중복 노드 차단. MySQL 은 타이핑 케이스 보존.
  (7) **QA-F1**: `test_anchor_relationship_live.py` 를 sibling 관례(main()+__name__ 가드)로 —
  pytest 수집 시 KeyError/라이브 변조 부작용 제거.
  (8) **B-F7/B-F11**: insight 신규 except 2곳 경고 로깅(조용한 정지 재발 방지) + 프로브
  neutral/failed report 집계.
  (9) **QA-F2 커버리지**: test_relationships.py +7(B-F2/B-F3/B-F4/Sec-F2/QA-F4/default_schema 채움) +
  신규 `test_insight_rel_cadence.py` 3건(B-F1 커서 키·D1a 게이트 의미론) = **총 56건 PASS**.
  (10) **B-F10**: star-export AST 가드 한계(지역 재바인딩 위음성) docstring 명시 — 명시 이름 고정
  테스트가 최종 방어선.
  (11) **재검증 R-1**(수정분 적대 재검증이 적발한 신규 결함): (4) 의 객체-부재→negative 가 ''-slot
  wildcard fetch 와 결합해 MSSQL catalog 순회에서 레거시 실관계를 오답 catalog 프로브 2회만에 영구
  broken 오파단 → negative 를 slot-확정 후보로 한정(`_slots_resolved` 가드), ''+db_scope 는
  failed/touch-only. 테스트 2건.
  (12) **재검증 R-2**: 1:N 라우터의 primary 복원 후 learn 이 ContextVar 를 읽어 라우팅된 SQL 에
  primary engine/DB/scope 오각인 → tools.py 실행-시점 스냅샷(`_snapshot_sql_exec_ctx`/
  `get_last_execute_sql_context`) + agent_core 학습이 스냅샷 사용(scope_key 오귀속 부수 해소,
  부재 시 default_schema 미채움 안전 폴백). 테스트 2건(`test_tools_exec_ctx.py` 신규).
  최종 재검증: **61건 PASS** + ruff clean.
- 수용 한계(수정 안 함, ADR-007 Consequences ①~④ 기록): dbo-only slot 규약(비-dbo/교차-스키마 후보
  영구 미프로브 — 후속 initiative), introspect 테이블명 케이스 플래핑(SSOT 레벨, TASK-0305 계열),
  실효 cadence ≈30h(window 회전 곱), LEARNING↔PROBE 결합 권장.
- Files: `unit/feature-0002-agent-core/src/modules/{insight,relationships}.py`,
  `unit/feature-0002-agent-core/src/agent_core.py`,
  `unit/feature-0002-agent-core/src/modules/tools.py`,
  `unit/feature-0002-agent-core/tests/{test_relationships,test_config_star_export,test_insight_rel_cadence,test_tools_exec_ctx}.py`,
  `unit/feature-0016-metadata-graph/tests/test_anchor_relationship_live.py`, ADR-007(DECISIONS.md).
- Impact: 백엔드 전용·비파괴(마이그레이션 0). B-F1 로 첫 배포 사이클에 MSSQL 전 DB interval 스캔
  백필(기존에도 cadence 백필 예정이었음 — 범위 동일, 커서만 정확해짐).
- 재번호(§13.1 감지-후-재번호): 병렬 세션이 ADR-005/006·TASK §22~§28 을 선점 — 본 cycle 의
  ADR 은 **ADR-007**, TASK 섹션은 **§29** 로 재번호 (main 병합 시점 2026-07-02).
- Rollback Notes: CHG-20260702T024556 와 동일(코드 롤백 = 이전 커밋 재빌드).

## CHG-20260702T024556-ai-claude-feature-0016-rel-selfheal
- Date: 2026-07-02
- Related Requirement: 사용자 검증 요청 — 그래프 뷰 '신뢰/추정 관계'가 실제 구축·표시되고 이후 대화에서
  assistant 추론에 활용되는지 검증, 아니면 의도대로 작동하도록 개선. 실측: inferred/trusted **0건**,
  대화학습 2행(Achievement→Quest/Reward)은 스키마 미해석으로 **AGE 고아 엣지**(그래프 점선 비가시).
- 근본원인: ① `AGENT_RELATIONSHIP_*` 가 config `__all__` 미등재 → star-import 소비자 insight.py 에서
  NameError → per-schema `except: continue` 가 삼켜 **insight 스캔 스키마 처리 전체가 06-29 부터 조용히
  정지**(table_insight max(updated_at)=06-29 13:58 실측; FK introspect·추론·프로브 0회의 1차 원인).
  ② 훅 발화조건(구조변경/artifact 부재)이 기존 스캔완료 스키마에서 영원히 거짓(설계 갭). ③ `_pk_like` 가
  게임 DB 관용 PK `UniqueID` 미인식 → name_fk 추론 불가. ④ 대화 JOIN 학습이 qualifier 를 버리고
  default 도 없어 스키마-slot='' 저장 → 그래프 Table 키(`db.table`)와 불일치(고아 Column 노드).
- Summary: (1) config `__all__` 에 관계 플래그 7종+`AGENT_SQL_FIX_MODEL`(동일 클래스, llm_fix_sql 무력화)
  등재 + 신규 `AGENT_RELATIONSHIP_REINFER_SEC`(6h, ≤0 off). (2) insight 훅에 주기 cadence
  (`relationship_infer_at` kv + `_is_refresh_due`) OR-게이트 — 첫 사이클이 전 스키마 백필.
  (3) 스키마-slot 규약 통일: MSSQL 저장 라벨=순회 DB명(`store_schema` 질의/저장 분리), 프로브
  `db_scope` 후보 필터+연결 DB qualifier 제거(교차-DB 오검증 차단). (4) 파서 qualifier 캡처
  (`_alias_map` → (leaf, qual)) + `learn_relationships_from_sql(default_schema=활성 DB)`.
  (5) `_pk_like` 에 `uniqueid`/`unique_id`. (6) 프로브 neutral 도 `last_validated_at` 전진(rotation 공정).
  (7) 회귀 가드 신설 `tests/test_config_star_export.py` — star-import bare 이름 런타임 해석 AST 검사.
  (8) `sync_relationship` REFERENCES 끝점 앵커링(`_anchor_relationship_column`) — 미큐레이션 컬럼도
  Table/Schema 체인(HAS_TABLE/HAS_COLUMN) MERGE 로 점선이 실 테이블에 붙음(SET 생략으로 비파괴).
- Files:
  - `shared/config.py` (__all__ 등재 + AGENT_RELATIONSHIP_REINFER_SEC)
  - `unit/feature-0002-agent-core/src/modules/insight.py` (cadence 게이트·store_schema·db_scope·스탬프)
  - `unit/feature-0002-agent-core/src/modules/relationships.py` (qualifier 캡처·default_schema·store_schema·
    db_scope 필터·uniqueid PK·neutral 터치)
  - `unit/feature-0002-agent-core/src/modules/metadata_graph.py` (REFERENCES 끝점 Table/Schema 앵커링)
  - `unit/feature-0002-agent-core/src/agent_core.py` (대화 학습 default_schema 전달)
  - `unit/feature-0002-agent-core/tests/test_relationships.py` (+8 케이스, alias_map tuple 갱신)
  - `unit/feature-0002-agent-core/tests/test_config_star_export.py` (신규 회귀 가드)
- Impact: 백엔드 전용·비파괴(스키마 마이그레이션 0, 웹 자산 무변경). insight 파이프라인의 **인사이트
  갱신 재개**(부수 복구) + 관계 추론·프로브 최초 실가동. 운영 DB 프로브(read-only EXISTS, cap 40/스키마·
  timeout 5s)가 cadence 마다 실제 발생 — 기존 설계 승인 범위(ADR-002), env 로 조절 가능. 배포 =
  insight-worker·ask-worker 재빌드 + web 롤링. 배포 후 데이터 정정(기존 2행 스키마 정규화 + AGE 고아
  Column 3노드 회수 + 재sync) 필요 — REPORT 참조.
- Rollback Notes: config `__all__` 등재는 유지해도 무해(이름 노출뿐). cadence 는
  `AGENT_RELATIONSHIP_REINFER_SEC=0` 으로 off(기존 트리거만). 코드 롤백 시 이전 커밋으로 재빌드.
  데이터 정정은 관계형 SSOT UPDATE 2행 — 역방향 UPDATE 로 복원 가능, AGE 는 재생성 가능 투영.

## CHG-20260702-node-haiku-deploy
- Date: 2026-07-02
- Related Requirement: node-analysis-haiku(CHG-20260702-node-analysis-haiku-model)의 배포 게이트 T22.7 완수 — 사용자 "랜딩+배포" confirm 승인.
- Summary: PR #535 main 병합(617e9a74) 후 라이브 배포. `.env` 에 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 반영 + insight-worker 이미지 재빌드(새 코드 baked)·`--no-deps --force-recreate` 재기동(healthy). smoke 실증(env 격리·config 값·라우팅 소스·클린 기동). 코드/스키마 변경 없음 — 배포 실행 + 정본 doc-status 갱신(TASK T22.7 완료 표시·T22.8 사용자 실검증 잔여, REPORT 배포 결과).
- Files:
  - `repo/.env` (런타임, non-versioned) — `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 추가
  - `unit/feature-0016-metadata-graph/docs/{TASK,REPORT}.md` (배포 완료 기록)
- Impact: 운영 insight-worker 가 그래프 관계 분석을 claude-haiku 로 실제 라우팅. 외부 API 비용 발생 시작(예산 캡 경계). web/ask-worker·데이터·스키마 무영향.
- Rollback Notes: `.env` `AGENT_NODE_ANALYSIS_MODEL=edge` override 후 insight-worker 재기동(즉시 gemma 환원) 또는 CHG-20260702-node-analysis-haiku-model 코드 revert.

## CHG-20260701T220000-ai-claude-feature-0016-graph-perf2
- Date: 2026-07-01
- Related Requirement: WebGL 배포 후 사용자 육안 후속 3건 — (1) 프레임 여전히 거침, (3) 17컬럼 테이블 더블클릭 시 컬럼이 세로 스택 아닌 **원형 뭉치(blob)**, (4) 휠 확대/축소 너무 느림. (2 라벨유지는 OK.)
- 근본원인 (진단 워크플로 5에이전트 적대 검증): blob·거침은 **동일 뿌리** — 컬럼 세로정렬을 fcose 제약(alignment/
  relativePlacement)에 위임하고 그 제약을 화면 전체 테이블에 매 tick(numIter 1000) 적용. (a) fcose 는 다수 컬럼의
  ring seed 에서 세로 라인 수렴 보장 못 해 blob 잔존, (b) 제약 동기 계산(cose-base runSpringEmbedder while-loop,
  rAF/yield 0)이 프레임 거침. WebGL 은 렌더만 GPU 화라 이 계산 병목과 무관(→ 거침 개선 없던 게 정합). 줌은 독립:
  wheelSensitivity 0.3 = 기본(1)의 1/3 스텝.
- Summary: (1) 컬럼 세로정렬을 fcose 제약에서 **완전 제거**하고 layoutstop 의 **결정론적 세로 배치**(`_metaGraphPlaceColumns`,
  batched, ordinal 정렬, 무게중심 기준 상하대칭)로 이관 → blob 해소 + tick 당 제약 부하 소멸로 거침 완화. (2) 신규
  컬럼 seed 를 ring→세로 스택으로. (3) 정렬 비교자·정렬맵을 단일 헬퍼(`_metaGraphColCmp`/`_metaGraphOrderedColumns`)로.
  (4) `wheelSensitivity:0.3` 제거→기본 1(줌 3배 빨라짐). (5) 박스 겹침 상쇄: `_META_COL_PITCH` 18 + nodeSeparation
  150→220. de-risk(실 Windows 브라우저): 17컬럼 x-spread 0.0px(완벽 세로스택, blob 소멸) + 박스겹침 0/7 실측.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (컬럼 결정론 배치 헬퍼 3종, fcose 제약 제거, 세로 seed, wheelSensitivity 제거, PITCH/nodeSeparation)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캐시버스터 graph-perf2)
- Impact: 프론트 전용·비파괴. 그래프 레이아웃/입력 semantics 만 변경(컬럼 정렬 주체 이전, 줌 배율 복원). 백엔드/API/데이터
  무변경. WebGL 렌더러 유지(position set 은 렌더러 무관). 배포=web 재빌드만. **실 FPS·박스겹침·줌 체감은 사용자 실 하드웨어 재확인이 최종 검증.**
- Rollback Notes: 컬럼 제약(_metaGraphColumnConstraints)·_ccCfg 병합 복원 + placeColumns/세로seed/PITCH/nodeSeparation/
  wheelSensitivity 되돌림(graph-webgl 상태로). DB/백엔드 무관.
## CHG-20260701T233000-ai-claude-feature-0016-node-analysis-anchor-liveverify
- Date: 2026-07-01
- Author: ai/claude (worktree ai/claude/feature-0016-node-analysis-anchor)
- Grade: 문서 전용(코드 무변경) — node-analysis-anchor 배포 후 라이브 검증 결과 기록.
- 내용: CHG-20260701T173000 배포 완료 후 라이브 실데이터 검증 결과를 REPORT/TEST/TASK 에 기록.
  alembic 0029 라이브 적용(live=0029)·web-a/web-b 무중단 7bca9b2·insight-worker 7bca9b2 재기동.
  실데이터 프로브(insight-worker 내부, LLM 0): `dk_data_release.Achievement` 하위 컬럼 4개 rel 1.0 통과 +
  부모 Schema(형제 테이블 **123개**) 탈락 = fan-out 지배 경로 차단 정량 확인. AchievementReward 17컬럼 통과.
- Files: REPORT.md / TEST.md / TASK.md(T16.8·T16.9 완료) / REVIEW.md([SKIPPED:docs-only] 항목).
- Impact: 문서 전용, 코드·스키마·계약 무변경. ANCHOR §4 는 human 외부검증 전용이라 미기입(AI 프로브는 TEST/REPORT 기록).
- Rollback Notes: 문서 되돌림 외 없음.

## CHG-20260701T210000-ai-claude-feature-0016-graph-webgl
- Date: 2026-07-01
- Related Requirement: 그래프 뷰 애니 프레임레이트 근본 해소 + 애니 중 라벨 유지 (사용자 육안 후속 — camfps 배포 후에도 거침 + 라벨 사라짐 불호 + 렌더링 엔진 검토 요청).
- 근본원인 확정: vendored Cytoscape **3.30.2 = canvas-2D 렌더러 전용**(WebGL 코드 0). 매 프레임 CPU 재래스터가
  구조적 상한(트레이스: rAF 60fps인데 표시 ~36fps, Scripting busy 65%=Cytoscape 렌더, GPU/컴포지터 유휴). 미세 튜닝
  불가 → 엔진 교체 필요.
- 사용자 결정(AskUserQuestion 2단): WebGL 업그레이드 + 엣지 재설계(강등 수용).
- Summary: (1) vendor cytoscape **3.30.2→3.34.0**(WebGL 렌더러 지원). (2) `renderer:{name:"canvas",webgl:_webglOk}`
  활성 — `_webglOk`=webgl2/webgl feature-detect(미지원 시 canvas-2D graceful 폴백). pixelRatio 제거. (3) 엣지 WebGL
  호환 재설계: curve-style unbundled-bezier→bezier, candidate/RELATED_TERM dashed 제거→색·투명도·두께 구분. (4) 애니
  중 라벨/엣지 숨김(anim-hide-* + camfps gen/clearMotionHide/restoreIfCurrent) **전면 제거** → 항상 표시. de-risk:
  실 Windows 브라우저 WebGL 로 2단 compound+라벨+bezier 정상 렌더 확인(스크린샷).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/vendor/cytoscape.min.js` (3.30.2→3.34.0, unpkg 정품)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (renderer webgl + feature-detect, 엣지 재설계, anim-hide 제거)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캐시버스터 cytoscape 3.34.0 + admin.js graph-webgl)
- Impact: 프론트 전용·비파괴. 렌더러 GPU 가속 전환(라벨 유지한 채 부드러운 애니 목표). 백엔드/API/데이터 무변경.
  트레이드오프: WebGL 미지원 엣지 스타일(taxi/dashed) 강등(bezier/색 구분). WebGL 미지원 환경은 canvas-2D 폴백.
  배포=web 재빌드만(정적 자산). **실 FPS 개선은 사용자 실 하드웨어 재측정이 유일 검증.**
- Rollback Notes: cytoscape.min.js 3.30.2 환원 + admin.html/admin.js 캐시버스터 revert + renderer/엣지/anim-hide
  변경 되돌림(erd-box-spread-tap 상태로). DB/백엔드 무관.

## CHG-20260701T210000-ai-claude-feature-0016-erd-box-spread-tap-deploy-record
- Date: 2026-07-01
- Related Requirement: CHG-...-erd-box-spread-tap 의 배포·검증 결과 기록(문서 전용, 코드 무변경).
- Summary: box-spread + box-click 변경을 web 무중단 롤링 배포(`git_commit=a6bf0eb`, PR #511, soak 90s 통과, /healthz 200).
  배포 자산 서빙 검증: `GET /static/admin.js?v=20260701-erd-spread` 에 `newAddsBox` 마커 3건 baked(HTTP 정본). 그래프 뷰
  UI 로드 sanity(실 Windows Chrome relay screenshot) PASS. **라이브 canvas 인터랙션(박스 클릭/더블클릭·확장 스프레드)
  PB-0008 은 이번 세션 자동화 차단** — Chrome 149.0.7827.200 자동업데이트가 win-browser Playwright eval(주입 검증)
  UtilityScript 를 파손 + tool 이 canvas 좌표클릭·더블클릭·native select datasource 전환 미지원. 코드 정합은 배포 전
  인젝션 실측(886→0)+적대리뷰(REV-...-erd-box-spread-tap, MAJOR 수정)로 확증. 화면 동작 정본은 사용자 실브라우저 확인.
- Files: `unit/feature-0003-agent-web-ui/docs/TEST.md`·`unit/feature-0016-metadata-graph/docs/TEST.md`(배포·검증 상태 기록).
- Impact: 문서 전용. 코드/배포 산출물 무변경(이미 a6bf0eb 로 라이브).
- Rollback Notes: 해당 없음(문서). 코드 롤백은 CHG-...-erd-box-spread-tap 참조.

## CHG-20260701T200000-ai-claude-feature-0016-erd-box-spread-tap
- Date: 2026-07-01
- Related Requirement: 사용자 후속(4·5회차) — (4) ERD 카드 배포 후 밀집 뷰에서 **테이블 박스끼리 겹침**(사용자 결정
  AskUserQuestion: **박스 벌림 튜닝 투자**, 문맥·프레임 일부 감수). (5) **박스 클릭/더블클릭 동작이 기존 노드와 정합하지 않음**.
- Summary:
  (A) box-spread — 근본원인 = 증분(더블클릭 확장) 경로가 국소 relax(먼 노드·앵커 고정)라 **중첩 compound(tall ERD
  박스)를 벌리지 못해** 밀집 시 박스겹침 누적(실측 141테이블 886쌍). 해법 = 증분 경로를 분기: **compound(ERD 카드) 존재
  시 전체-스프레드**(`randomize:false`·`packComponents:true`·`numIter:1000`·`nodeRepulsion 18000`·고정 없음)로 박스를 벌리고,
  compound 미존재(순수 노드 확장) 시 기존 국소 relax 유지. `randomize:false` 라 현 배치에서 완화(전면 재무작위화보다 덜 튐),
  카메라는 layoutstop focus-fit 이 앵커+신규 이웃으로 추종(문맥 추적 유지). 실측(141테이블 compound): 박스겹침 886→0, 109ms.
  (B) box click/dblclick 정합 — 근본원인 = tap 핸들러가 `if (t.isParent()) return` 으로 **모든 compound 부모를 무시** →
  Table ERD 카드 박스 클릭이 무반응(일반 테이블 노드는 상세/확장 동작 → 불일치). 해법 = `t.data("label") !== "Table"` 조건 추가
  → Table 박스는 일반 노드와 동일(단일=상세, 더블=확장), Schema 컨테이너(조직용)만 무시 유지. 박스 안 컬럼 클릭은 target=컬럼.
- Files: `unit/feature-0003-agent-web-ui/src/static/admin.js`(_metaGraphLayout 증분 경로 hasCompound 분기+전체-스프레드 cfg,
  tap 핸들러 Table 예외), `unit/feature-0003-agent-web-ui/src/static/admin.html`(캐시버스터 erd-spread).
- Impact: 프론트 전용, 비파괴. 더블클릭 확장 시 ERD 카드 박스가 전체 재-스프레드되어 박스겹침 해소(문맥 일부 이동은 사용자 승인
  트레이드오프). Table 박스가 클릭/더블클릭에 일반 노드처럼 반응. 순수 노드(컬럼 미보유) 확장은 기존 국소 relax 불변.
- Rollback Notes: admin.js 증분 경로를 단일 국소-relax 로 환원 + tap 핸들러를 `if (t.isParent()) return` 로 환원 + 캐시버스터 환원. DB/백엔드 무관.
## CHG-20260701T173000-ai-claude-feature-0016-node-analysis-anchor
- Date: 2026-07-01
- Author: ai/claude (worktree ai/claude/feature-0016-node-analysis-anchor)
- Grade: **Major** (재귀 탐색 동작 변경 + 비파괴 additive 마이그레이션). 파괴적 아님 — 기존 예산 캡·PG
  미가용 no-op 보존, 인증/데이터 삭제 없음.
- Request(2026-07-01): 관리콘솔 > 메타데이터 > 그래프 뷰 "AI 능동 분석" 재귀 탐색이 **원래 분석 대상**에
  앵커되지 않고, 방문한 허브 노드(예 일반 컬럼 `UniqueID`, 부모 Schema)를 새 중심으로 무관 테이블까지
  fan-out 하는 문제 해소. 하위 컬럼은 기본 분석하되, 깊은 확장은 "dk 제품(scope)·대상 엔티티(Achievement)"
  연관 높은 대상으로만. 단순 컬럼명 일치·상위객체 무연관은 낮은 우선순위.
- Root cause: `node_analysis._enqueue_neighbors` 가 방문 노드의 이웃 **전부**를 무차별 재큐(게이트=예산/dedup
  뿐, 루트 관련도 판단 부재) → 무방향 BFS 라 허브에서 재-앵커링. 일반 컬럼/Schema 가 fan-out 진입점.
- Decision: **앵커-상대 관련도 게이팅**(ADR-003). 재귀를 원래 루트(anchor)에 고정하고 후보 이웃을 루트와의
  관련도(0~1)로 게이트·우선순위화.
  1. `_build_anchor`/`_load_anchor` — run 의 루트 서술자(scope·table_fqn·이름/설명 토큰)를 run 당 1회 캐시.
  2. `_relevance(node, meta, anchor)` — 같은 제품(scope) · 루트 테이블 서브트리 · 이름/설명 토큰 겹침(일반어
     stoplist 제외) · GlossaryTerm · REFERENCES 신뢰(ADR-002 weight/status). 다른 제품 곱셈 감쇠, Schema·broken=0.
  3. `_score_candidates` — 루트 직속 컬럼(depth 0 child)은 relevance 1.0 무조건 통과(하위 컬럼 기본 분석),
     그 외는 임계 이상만(이웃 depth≥2 는 _DEEP 임계 상향) 관련도순 재큐.
  4. `node_analysis_jobs.relevance`(alembic 0029) 영속 + claim `ORDER BY depth ASC, relevance DESC` → 예산을
     가장 관련 높은 노드에 우선 소비(사용자 "낮은 우선순위로 판단" 요구의 영속 구현).
- Files:
  - `shared/config.py` (RELEVANCE_MIN 0.18 / _DEEP 0.34 / CROSS_SCOPE_FACTOR 0.25 / EXPAND_SCHEMA=off, 전부 env override)
  - `unit/feature-0002-agent-core/src/modules/node_analysis.py` (토크나이저·stoplist·_build_anchor·_load_anchor·
    _relevance·_score_candidates·_enqueue_neighbors 재작성·_fetch_context neighbor_meta·process_pending claim 정렬·
    enqueue root relevance=1.0·get_run_status relevance 노출)
  - `unit/feature-0002-agent-core/alembic/versions/20260701_0029_node_analysis_relevance.py` (신규 — ADD COLUMN
    relevance real DEFAULT 0 + ix_node_analysis_jobs_claim_priority, expand-only, GRANT 는 0028 테이블단위 커버)
  - `unit/feature-0002-agent-core/tests/test_node_analysis_relevance.py` (신규 순수함수 12건 — 토큰화·anchor·
    관련도·게이팅. 핵심: hub 컬럼 depth1 확장 시 교차-제품/무관 이웃 탈락 + 루트 하위 컬럼 무조건 통과)
- Impact: 비파괴 additive. 구버전 코드가 relevance 미지정 INSERT 해도 DEFAULT 0 안전(expand 단계). 그래프는
  재생성 투영이라 즉시 반영. 외부 계약/인증/데이터 파괴 없음. 배포=alembic 0029 + web/insight 재배포.
- Rollback Notes: alembic downgrade(0029 → DROP INDEX + DROP COLUMN relevance, 비파괴) + node_analysis.py 환원.
  진행 중 run 은 relevance 소거돼도 claim 은 depth/created_at 로 graceful. 관계형 SSOT·그래프 무손상.
- Hardening (2라운드 적대 패널 REV-20260701T173000, R1 M1~M5 + R2 재적대):
  - **M1(MAJOR) content-gate**: `_relevance` 를 재작성 — content(서브트리·이름·설명·용어) 신호 0 이면 즉시 0.0,
    신뢰(REFERENCES)/제품(scope)은 **부스터**로만. 신뢰·구조 링크만으론 재귀 불통과(사용자 요구 정합).
  - **MAJOR(2R) 한글 일반어**: `_GENERIC_TOKENS` 라틴 전용 hole 로 M1 이 한글 경로 재발(설명 booster 가 게임/
    정의/테이블 겹침으로 content 조작) → 한글 일반어·구조어 45+ 추가.
  - M3 deep 임계 깊이 스케일(+0.06/depth, 상한 0.7) · M4 한글↔라틴 split + 접두/접미 부분연관(중간삽입 배제:
    회원⊄비회원구매·업적⊄기업적자) · M5 tiebreak ordinal→name→key 전순서 결정 · M2 claim 공정성 주석 · meta None 방어.
  - 테스트 12→28건(pytest PASS). 잔여 BLOCKER 0. 의도된 precision 트레이드오프(신뢰 FK 라도 내용 발산 시 제외) 고정.

## CHG-20260701T170000-ai-claude-feature-0016-erd-card
- Date: 2026-07-01
- Related Requirement: 사용자 후속(3회차) — 더블클릭 시 컬럼 세로 스택이 이웃 테이블과 여전히 겹침(스크린샷).
  사용자 결정(AskUserQuestion): **ERD 카드(테이블 compound 박스 안 컬럼)** 로 전환.
- Summary: 근본원인 = 위성 컬럼을 layoutstop **후** 배치해 force 가 그 공간(우측 라벨 폭 ~160px)을 예약 못 함 →
  이웃 테이블 침범. 사후 밀어내기(declutter)는 적대검증상 인접 스택 진동 or 노드 쏠림(겹침을 옮길 뿐)으로 REJECT.
  **해법 = 컬럼을 소속 테이블의 compound 자식**으로 만들고(부모=테이블 key, `_metaColParent`), fcose
  `alignmentConstraint.vertical`(컬럼 동일 x) + `relativePlacementConstraint`(위→아래 gap, ordinal 순)로 박스 안
  ordinal 세로 정렬 → fcose 가 **각 테이블 박스 bounds 로 이웃 공간을 확보**해 겹침을 원천 차단. HAS_COLUMN
  엣지·placeColumns·declutter·round-taxi 제거(컨테인먼트로 대체). 실측: 컬럼 순서 top→bottom 보존·박스 겹침 1쌍·131ms.
- Files: `unit/feature-0003-agent-web-ui/src/static/admin.js`(_metaColParent·_metaGraphColumnConstraints 신규,
  _metaGraphAddElements 2-pass+컬럼 테이블-부모, _metaGraphLayout 제약 병합, placeColumns/declutter/round-taxi/dragfree 제거,
  Table compound 박스 스타일), `unit/feature-0003-agent-web-ui/src/static/admin.html`(캐시버스터 erd-card).
- Impact: 프론트 전용, 비파괴. 테이블(컬럼 보유)이 compound 박스(ERD 카드)로 렌더 — 이름 상단, 컬럼 목록 내부.
  스키마(점선 남색) > 테이블(teal 실선) > 컬럼 2단 중첩 compound. 컬럼 미보유 테이블은 평범 노드 유지. 상세 패널은
  API 응답 edges 사용이라 무영향. round-taxi 꺾이는 선은 사용자 결정으로 컨테인먼트 대체(겹침 제거 우선).
- Rollback Notes: admin.js 를 satellite 방식(위성 컬럼+placeColumns+round-taxi)으로 revert + 캐시버스터 환원. DB/백엔드 무관.
## CHG-20260701T190000-ai-claude-feature-0016-graphux5-panelmove-showfix
- Date: 2026-07-01
- Related Requirement: panelmove 세션 독립 폴 재개 시 진행 패널이 **표시되지 않던 버그** 수정(라이브 검증 중 적발 — status 바는 갱신되나 패널 숨김).
- Summary: `_metaGraphRenderProgress` 가 렌더 시 `panel.style.display = ""` 를 직접 설정. 기존엔 `_metaGraphAnalyze`(버튼) 경로만 display 를 풀어, 노드 클릭으로 폴을 재개(fix B)한 세션 독립 경로에서 초기 `display:none` 이 안 풀려 패널이 populated 되고도 숨겨졌다.
- Files: `unit/feature-0003-agent-web-ui/src/static/admin.js`.
- Impact: 프론트 1줄·비파괴. 세션 독립(다른 탭/새로고침) 및 재개 경로에서 진행 패널이 정상 표시. 버튼 경로는 무변화(중복 display 설정, 무해).
- Rollback Notes: 해당 라인 제거. 백엔드/DB 무변경.

## CHG-20260701T180000-ai-claude-feature-0016-graphux5-panelmove
- Date: 2026-07-01
- Related Requirement: AI 능동 분석 진행 화면을 **우측 상세정보 패널에 구성**. 상단 full-width 진행 바가 그래프를 밀어내 구성이 무너지고 여백이 낭비되던 이슈 해소 (사용자 피드백).
- Summary: (1) 진행 패널(`#metadataGraphProgress`)을 legend 아래 상단 바에서 **제거**하고 우측 상세 aside(`#metadataGraphDetail`) **상단**으로 이동. 노드 상세는 신규 `#metadataGraphDetailBody` 서브컨테이너로 분리 — 노드 클릭 시 body 만 교체되고 진행 패널은 유지. 미분석 시 패널 `display:none` 이라 여백 낭비 0. (2) **후속 이슈 수정** — (a) **fairness**: `process_pending` claim 순서 `depth ASC` 우선(대형 run 의 깊은 recursion 독점 → 이후 단일노드 run root 미처리 starvation 해소, 즉시 진행 표시), (b) **세션 독립**: `_metaGraphLoadNodeAnalysis` 가 pending/running 노드 run_id 로 폴링 자동 재개(다른 탭/새로고침에서도 진행 패널·주황 마커·진행률 표시).
- Files: `unit/feature-0002-agent-core/src/modules/node_analysis.py`(claim depth 우선); `unit/feature-0003-agent-web-ui/src/static/{admin.html,admin.js,styles.css}`.
- Impact: 프론트 레이아웃 + 워커 claim 정렬 변경(비파괴). 진행률 0% 고착·세션 종속 표시 해소. 기존 마커·폴링·백엔드 저장 무변경. 그래프가 상단 바에 밀리지 않음.
- Rollback Notes: admin.html 구조·렌더 타깃 환원 + claim `ORDER BY created_at ASC` 환원 + 캐시버스터 환원. DB/마이그레이션 무변경.

## CHG-20260701T170000-ai-claude-feature-0016-graphux-camfps
- Date: 2026-07-01
- Related Requirement: 그래프 뷰 애니메이션 프레임레이트 저하 — "노드 수와 무관하게 애니메이션만 FPS 낮음(수동 팬은 매끄러움)" (사용자 보고, 이전 세션 컨텍스트 초과로 진단 중단분 인계).
- 근본원인 (DevTools Performance 트레이스 실측, Trace-20260701T134334, 10.4s/70418 events): 메인스레드 busy 20%
  중 **Scripting 65%(FunctionCall 1180ms) = Cytoscape 캔버스 재렌더**(핫스팟 `ts`/스타일 재계산/`calculateLabelDimensions`),
  Rendering·Painting 각 1%. rAF 는 60fps(16.7ms) 인데 실제 표시 프레임 ~36fps(27.8ms)로 드롭. GPU HW 가속 ON(chrome://gpu),
  디스플레이 사실상 60Hz. → 레이아웃 애니는 라벨/엣지 숨김 최적화됨(기존)이나, **그 직후의 450ms 카메라 fit 애니가
  라벨·엣지를 켠 채 돌아** 매 프레임 텍스트 래스터+엣지 지오메트리 재계산 재발 = 저프레임 구간.
- Summary: `_metaGraphLayout` 의 `layoutstop` 콜백에서 라벨(`anim-hide-label`)·엣지(`anim-hide`) 숨김 해제를
  즉시 하지 않고 **뒤이은 카메라 fit 애니(450ms)의 `complete` 후로 미룸**. 즉시맞춤(`cy.fit`)·예외 경로는 동기 복원.
  연타 경합 방지 guard(`!_layoutRunning`) + complete 미발화 대비 `setTimeout(650ms)` fallback(라벨/엣지 영구 숨김 회귀 차단).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraphLayout` layoutstop: restoreMotion 지연 복원)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캐시버스터 graphux-progress → graphux-camfps)
- Impact: 프론트 전용·비파괴. 애니 렌더 semantics 만 변경(라벨/엣지가 레이아웃 애니 + 직후 카메라 애니 동안 숨겨졌다
  정착 시 복원 — 기존은 카메라 애니 중 표시). 백엔드·계약·인증·데이터 무변경. 배포=web 재빌드만(alembic/worker 무관).
- Rollback Notes: admin.js layoutstop 콜백을 즉시-복원 형태로 환원 + 캐시버스터 graphux-progress 로 되돌림. DB·API 무관.

## CHG-20260701T160000-ai-claude-feature-0016-graphux5-progress
- Date: 2026-07-01
- Related Requirement: AI 능동 분석 진행 현황을 **화면에 라이브 갱신** + 단순 % 대신 **어떤 항목이 어느 상태인지 상세** 표시 (사용자 요청, graphux5 후속).
- Summary: `get_run_status` 가 노드별 상세(`jobs[]`: node_key/label/name/status/depth) + `running_keys` 추가 반환. 프론트에 **지속 진행 패널**(`#metadataGraphProgress`) 신설 — 노드 선택과 무관하게 매 폴 틱(2.5s) 라이브 갱신, 진행바 + 완료/분석중/대기/실패 카운트 + **항목별 상세 리스트**(테이블/컬럼/스키마/용어 한글 라벨 + 상태 아이콘 + 깊이). 그래프에 **분석중 노드 주황 점선 마커**(aiRunning) + 완료 보라 마커. 닫기 버튼(run 별 dismiss).
- Files: `unit/feature-0002-agent-core/src/modules/node_analysis.py`(get_run_status jobs); `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`.
- Impact: 비파괴 additive(응답 필드 추가 + 표시 패널). GET /analyze status 는 `JSONResponse(st)` 통과라 API 변경 불필요. 기존 마커/폴링 회귀 0. LLM 비용 무변화(분석은 기존 그대로, 표시만 상세화).
- Rollback Notes: admin.js/html 캐시버스터 이전값 환원 + get_run_status jobs SELECT 제거. DB/마이그레이션 무변경.

## CHG-20260701T140000-ai-claude-feature-0016-graphux-expand-relax
- Date: 2026-07-01
- Related Requirement: 사용자 후속 요청 — 더블클릭 확장 시 (1) 컬럼이 세로로 안 펼쳐지고 (2) 신규 노드가
  기존 노드와 겹쳐 가시성 저하. "신규 노드를 나타낼 때 주변 노드를 부드럽게 밀어내 달라".
- Summary: `_metaGraphLayout` 증분(더블클릭) 분기를 **기존 노드 전부 고정(fixedNodeConstraint) → 앵커만
  고정 + 나머지 relax** 로 변경. 신규 노드 반발력(nodeRepulsion 12000→20000)이 주변 기존 노드를 부드럽게
  밀어내 겹침 해소. randomize:false 로 현 배치에서 국소 완화(문맥 보존), animate 유지(hideMotion 로 트윈 비용
  절감). 컬럼은 layout 전 공통 unlock(force 참여·테이블 이동 추종) → layoutstop 에서 세로 재-스택+재-lock.
  `_metaGraphExpand` 가 `anchorId` 전달. (근본원인: 이전 rigid-fix 로 신규 노드가 앵커 주변에 몰려 겹침 —
  실측 512 노드 seed 겹침쌍 502 → relax 후 0.)
- Files: `unit/feature-0003-agent-web-ui/src/static/admin.js`(_metaGraphLayout 증분 relax·공통 컬럼 unlock·
  _metaGraphExpand anchorId), `unit/feature-0003-agent-web-ui/src/static/admin.html`(캐시버스터).
- Impact: 프론트 전용, 비파괴. 더블클릭 확장 시 기존 배치가 국소적으로 완화(문맥 대체로 보존, 앵커 고정).
  실측 성능 fcose 68ms(128노드) — 다른 세션의 프리즈 완화 임계(250~400ms) 내. 초기로드/검색 경로 무변경.
- Rollback Notes: admin.js 증분 분기를 fixedNodeConstraint(전체) 로 환원 + 캐시버스터 revert. DB/백엔드 무관.


- Date: 2026-07-01
- Related Requirement: REQ-20260701-graphux5 (관리콘솔 > 메타데이터 > 그래프 뷰 UX 4항목 개선)
- Summary: (1) 검색 유사도 명시 — pg_trgm 실측 score + 노드 라벨 `이름 NN%`·상세 헤더 배지. (2) AI 능동 분석 — 상세 패널 "✨ 능동 분석" 트리거 → insight-worker 백그라운드가 선택 노드에서 관련 노드를 **재귀 탐색**하며 노드별 LLM 분석(경계: depth/node 예산 + visited dedupe). (3) 미큐레이션 Table 더블클릭 시 컬럼 즉석 introspection. (4) 이웃 깊이 드롭다운 변경 시 즉시 재전개.
- Files: `shared/config.py`; `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis(신규),llm,insight}.py`; `unit/feature-0002-agent-core/alembic/versions/20260701_0028_node_analysis.py`; `unit/feature-0003-agent-web-ui/src/app.py`; `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`.
- Impact: 비파괴 추가(신규 테이블 `node_analysis_runs`/`node_analysis_jobs` + GRANT). 외부 LLM 비용은 능동 분석 트리거 시에만 발생(예산 캡). RBAC `kb.ingest.manual` 재사용. 기존 그래프/검색/투영 경로 회귀 0(검색 `score` 는 additive 필드).
- Rollback Notes: `alembic downgrade -1` 로 0028 DROP(관계형 SSOT·AGE 그래프 무영향). `AGENT_NODE_ANALYSIS_ENABLED=0` 으로 기능 비활성. 프론트는 admin.js/html 캐시버스터 revert.

## CHG-20260701-0002
- Date: 2026-07-01
- Related Requirement: REQ-20260701-implicit-edges (그래프 뷰 — FK 없는 암묵 JOIN 관계 추론 + 자기교정)
- Summary: FK 미선언 관계를 명명 규칙으로 추론(source='inferred')하고, 정적 confidence 와 분리된 동적
  weight 를 관찰(대화 JOIN 사용 성공) + 능동 프로브(실데이터 EXISTS 겹침)로 강화/감쇠. weight≤0.15 broken
  (주입·그래프 제외), ≥0.85+양성누적 trusted. FK 는 권위적 불변. 그래프/UI/AI 컨텍스트에 신뢰/추정 구분 노출.
- Files:
  - `feature-0002-agent-core/alembic/versions/20260701_0026_relationship_reinforcement.py` (신규, 비파괴 ADD)
  - `feature-0002-agent-core/src/modules/relationships.py` (추론·강화·프로브 엔진 + weight-aware read/digest)
  - `feature-0002-agent-core/src/modules/dialects.py` (probe_relationship_overlap MySQL/MSSQL)
  - `feature-0002-agent-core/src/modules/insight.py` (추론+프로브 훅)
  - `feature-0002-agent-core/src/modules/metadata_graph.py` (weight/status 투영, broken 제외)
  - `feature-0002-agent-core/tests/test_relationships.py` (+21 단위 테스트)
  - `shared/config.py` (플래그 5)
  - `feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}` (신뢰 시각화 + 범례 + 배지)
- Impact: 비파괴 DB 스키마 추가(기존 관계 데이터·경로 무변경). 그래프에 추정 엣지(점선) 신규 표출. AI SQL
  컨텍스트에 신뢰 태그. 프로브는 운영 DB read-only(키 컬럼 표본 LIMIT 50, cap). 플래그로 전면 비활성 가능.
- Rollback Notes: alembic downgrade 0026 (신규 컬럼·CHECK·인덱스 DROP, 원 0024 CHECK 복원 — 관계 데이터
  보존). 또는 `AGENT_RELATIONSHIP_INFERENCE_ENABLED=0`·`AGENT_RELATIONSHIP_PROBE_ENABLED=0` 로 런타임 무력화.
  그래프는 `metadata-graph-sync --rebuild` 로 SSOT 에서 재생성.

## CHG-20260701-graphux5-column-ordinal
- Date: 2026-07-01
- Related Requirement: 그래프 뷰 컬럼 세로 정렬(실제 순서) + 부드럽게 꺾이는 연결선 (사용자 요청, TASK §9).
- Summary: 컬럼 순서(ordinal)를 관계형 SSOT(column_descriptions)에 저장해 AGE 그래프로 투영하고,
  그래프 뷰에서 Column 노드를 Table 노드 하단에 ordinal 순으로 세로 스택 배치 + HAS_COLUMN 엣지를
  round-taxi(부드럽게 꺾임)로, 그 외 엣지를 unbundled-bezier(완만 곡선)로 렌더.
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260701_0026_column_ordinal.py` (신규, ordinal ADD + 삽입순 backfill)
  - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (ordinal 컬럼 + 방어 ALTER)
  - `unit/feature-0002-agent-core/src/modules/kb_metadata.py` (upsert/update/list 에 ordinal)
  - `unit/feature-0002-agent-core/src/modules/metadata_graph.py` (_PROP_KEYS/_props_set 정수·sync_column·sync_graph·node 직렬화)
  - `unit/feature-0003-agent-web-ui/src/app.py` (columns POST/PUT/GET ordinal 배선)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (_metaGraphPlaceColumns·round-taxi·bootstrap ordinal 캡처)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캐시버스터 graphux5)
  - `unit/feature-0016-metadata-graph/tests/test_metadata_graph_units.py` (신규 순수함수 8건), `test_metadata_graph_age.py` (ordinal assert)
- Impact: 비파괴 additive. ordinal 미상 컬럼은 삽입순 근사→graceful fallback(name 순). 그래프는 재생성 투영이라
  재sync 로 반영. 외부 계약/인증/데이터 파괴 없음. 배포=alembic 0026 + graph re-sync + web 재배포.
- Rollback Notes: alembic downgrade(0026 → DROP COLUMN ordinal, 비파괴) + admin.js 캐시버스터 graphux4 환원.
  관계형 SSOT·그래프 노드 자체는 무손상(ordinal 속성만 소거).

## CHG-20260702-graph-g6-engine-swap
- Date: 2026-07-02
- Related Requirement: 그래프 뷰 사용자 관찰 5건(①클릭접힘 ②위치점프 ③줌 동기화지연 ④클러스터 뒤섞임 ⑤테두리 왜곡) → 엔진 단위 개선. DECISIONS ADR-004.
- Summary: 관리콘솔 그래프 뷰 렌더링 엔진을 **Cytoscape.js(WebGL) → AntV G6 v5.1.1(Canvas)** 로 교체.
  모델 B(2단): 스키마=combo·테이블=rect 칩·컬럼=circle·"−"=rect 컨트롤. JS 모델 → `_metaG6Build()`(위치 포함
  결정론 grid) → `setData()`+`draw()`. HTML 오버레이(클러스터명·접기버튼) 전량 제거 → G6 네이티브 렌더(③ 소멸).
  단일클릭=상세+펼침 전용(펼침이면 no-op → ①), "−"만 접기, 더블클릭(320ms)=이웃확장. 점선/실선 엣지 복원.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/vendor/g6.min.js` (신규 vendored, G6 5.1.1 UMD, MIT)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraph*` 엔진 전면 재작성 −762/+476; 오버레이·fcose·cy 로직 제거, DOM/API 함수 유지)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cytoscape·layout-base·cose-base·fcose 4종 제거 → g6.min.js; cache-buster `?v=20260702-graph-g6`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (오버레이 CSS 제거; cache-buster)
  - `unit/feature-0016-metadata-graph/g6-migration/{BLUEPRINT.md, poc/}` (신규 설계·POC 참조)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-004),TASK(§21),REPORT,TEST}.md`
- Impact: 프론트엔드 정적 자산만. 데이터 API(`/api/admin/metadata/graph*`) **불변**. 인증/데이터 파괴 없음.
  검증: WSL-headless-harness(실 마크업+mock API) 전 플로우 PASS·에러 0(TEST.md). 배포=web 재빌드(정적 자산). 완료 게이트=PB-0008 실 Windows 시각검증.
- Rollback Notes: admin.html 스크립트를 cytoscape 4종으로 환원 + admin.js/styles.css git revert + cache-buster 이전값. 데이터·API 무손상(렌더 계층만).

## CHG-20260702-graph-g6b-masonry-layout
- Date: 2026-07-02
- Related Requirement: 사용자 요청(라이브 PB-0008 후) — 그래프 뷰 기본 디자인·노드확장 가시성·UX 개선. 실데이터(236노드/36클러스터)에서 구 배치의 세로 과길이·fit 극소 문제 관측.
- Summary: `_metaG6Build` 레이아웃 재작성 — (1) **클러스터 내 다열 masonry**(테이블 수 기반 1~4 내부열, 최단열 배치로 높이 균형; 펼친 테이블 컬럼 높이 반영), (2) **가변폭 클러스터 shelf-packing**(좌→우, 폭 MAXROWW 초과 시 래핑). 끝없는 세로 1열·fit 극소 해소, 자연정렬·제자리 펼침·"−" 접기 불변.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaG6Build` 배치 로직 masonry+shelf-pack, `_METLAY` 보강)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260702-graph-g6b`)
  - `unit/feature-0016-metadata-graph/docs/{REPORT,TEST,TASK}.md`
- Impact: 프론트 렌더 계층만(데이터 API 불변). 검증: WSL-headless-harness(14클러스터 스케일 mock, 확장 포함) 전 플로우 PASS·에러 0 + 라이브 PB-0008(실 Windows, 236노드) 확인. 배포=web 재빌드.
- Rollback Notes: `_metaG6Build` git revert(단일 세로열 배치로 환원) + cache-buster graph-g6. 데이터·API 무손상.

## CHG-20260702-graph-perf-bg-nonblocking-expand
- Date: 2026-07-02
- Related Requirement: 사용자 관찰 — 관리콘솔 > 메타데이터 > 그래프 뷰에서 테이블 노드 선택→펼침 시 브라우저 렌더 엔진 프리즈. "병목 구간 백그라운드화 + 별도 성능 이슈 추가 검증" 요청. 정본: DECISIONS ADR-005.
- Summary: 그래프 뷰 펼침 임계경로를 논블로킹화하고 반복 병목을 제거. (FE) ① 논블로킹 파이프라인 — busy(teal 점선) 페인트 후 double-rAF(`_metaYieldPaint`) 양보 → fetch·`setData`+`draw`; ② stale-render 무효화 토큰 `_opSeq`(await 경계마다 대조, **`_metaGraphResetModel`·`_metaGraphLoadRoots` 도 게이팅**); ③ O(1) 펼침 인덱스 `colsByTable`(전 노드 O(N) 스캔 제거); ④ `_metaGraphRefreshStates` 변화분-only + `startBatch`; ⑤ busy 를 `_busyKeys`(소유 op) + `_metaStateSig`/`_metaApplyState` 로 표현(폴 덮어쓰기·rebuild 재-bake·`_stateCache` 불일치 차단). (BE) ⑥ `/api/admin/metadata/graph/columns` introspection 성공 결과를 `(scope_key, fqn)` 키 프로세스-로컬 TTL 캐시(기본 300s, 실패·빈결과 미캐시, 상한 512, TTL≤0 비활성).
- Files:
  - `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py` (`/graph/columns` TTL 캐시 `_COLUMNS_CACHE*` + get/put/ttl 헬퍼 + 엔드포인트 캐시-히트 early-return; +65)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraph` 모델에 `colsByTable`/`_opSeq`/`_stateCache`/`_busyKeys` + `_metaStateSig`/`_metaApplyState`/`_metaSetBusy`(소유권)/`_metaYieldPaint` + `_metaG6Build` 레이아웃 Pass1(collapsed 배정)/Pass2(real push-down) + toggle/expand 논블로킹·seq 가드 + `_metaGraphResetModel`/`_metaGraphLoadRoots` opSeq 게이팅 + `_metaTableHasCols` O(1) + `_metaGraphRefreshStates` diff+batch + `_metaGraphSetSelected` `_metaApplyState` 경유; +215/−51)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260702-graph-perf-bg`)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-005),TASK(§22),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 렌더/상호작용 계층 + BE 라우터 캐시 층만. 데이터 API 계약·그래프 스키마 **불변**. 권한/스코프 격리 불변(캐시-히트는 `Depends(require_permission)` 해소 후, 페이로드=물리 스키마만). 캐시=프로세스-로컬 → **마이그레이션 없음**(alembic 병렬 충돌 회피). 검증: §18.8 적대 패널(3렌즈 + 5-agent 재검증 + reset-vs-reset 후속) 4+1 BLOCKING 수정·재검증 PASS(REVIEW REV-20260702T120000). 배포=web 재빌드(정적 자산) — BE 캐시는 기존 web 프로세스에 포함. 완료 게이트=PB-0008 실 Windows 시각검증(펼침 무프리즈 + busy 피드백).
- Rollback Notes: admin.js/admin_metadata.py git revert + cache-buster 이전값(graph-g6b). 데이터·API·스키마 무손상(렌더/캐시 계층만). BE 캐시만 비활성화하려면 env `METADATA_GRAPH_COLUMNS_CACHE_TTL=0`.

## CHG-20260702-node-analysis-haiku-model
- Date: 2026-07-02
- Related Requirement: 사용자 요청 — 관리콘솔 그래프뷰 "각 관계를 분석하는 LLM" 을 claude-haiku 로 작동하도록 구성. 로컬 gemma(edge) 로 작동하던 것은 의도하지 않은 구조. (범위 결정 2026-07-02: **그래프 관계 분석만** — schema/table/account insight 는 공유 `AGENT_INSIGHT_MODEL` 유지.)
- Summary: 그래프 노드 능동 분석(`llm_node_analysis`)이 4개 insight 함수와 공유하던 `AGENT_INSIGHT_MODEL`(운영 `.env`=`edge`=로컬 gemma)에 묶여 gemma 로 작동. 전용 config **`AGENT_NODE_ANALYSIS_MODEL`(기본 `claude-haiku-4`)** 을 신설해 그래프 관계 분석만 claude-haiku 로 분리 라우팅. `.env` 미설정 시에도 기본 claude-haiku 로 동작(=의도한 구조). 저장·표시용 model 라벨도 동일 순서로 해석해 상세 패널이 실제 사용 모델을 표시.
- Files:
  - `shared/config.py` (`AGENT_NODE_ANALYSIS_MODEL` 신설 + `__all__` 노출)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (`llm_node_analysis` 모델 라우팅 = `AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL`)
  - `unit/feature-0002-agent-core/src/modules/node_analysis.py` (`process_pending` 저장 model 라벨 동일 순서 해석)
  - `unit/feature-0002-agent-core/tests/test_llm_env_naming.py` (전용 모델 기본값/override/공백폴백/노출 회귀 테스트 4건)
  - `unit/feature-0016-metadata-graph/docs/{REPORT,TASK,MODIFY,REVIEW}.md`
- Impact: 백엔드 모델 라우팅 계층만. schema/table/account insight·에이전트 추론·요약 등 다른 LLM 경로 불변(격리 확인). **외부 API 비용 발생**(그래프 노드 분석이 로컬 무료 gemma → Bedrock claude-haiku 유료 호출). 비용은 기존 node_analysis 예산 캡(depth_budget/node_budget/dedupe)으로 경계. 반영 조건: 런타임 `.env` 에 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 반영(코드 기본값과 동일이므로 선택적·명시 권장) + **insight-worker 재빌드·재기동**(코드 baked). 기존 저장된 분석은 이전 model 라벨(gemma) 유지, 신규 run 부터 claude-haiku.
- Rollback Notes: `AGENT_NODE_ANALYSIS_MODEL=edge` 로 .env override(즉시 gemma 환원, 재기동만) 또는 3개 코드 파일 git revert. 데이터·스키마 무손상(마이그레이션 없음).
## CHG-20260702T120000-ai-claude-feature-0016-graph-ctxmenu
- Date: 2026-07-02
- Related Requirement: REQ-20260702T113000-graph-ctxmenu (TASK.md §24 — §13.1 재번호 22→24) — 그래프 뷰 노드 우클릭
  상세 상호작용. 스키마 미숙지 사용자의 선택 노드 연관 관계 파악 지원.
- Summary: (1) **우클릭 컨텍스트 메뉴** — node/combo/canvas `contextmenu` G6 이벤트 + container
  capture 리스너(기본 메뉴 차단·좌표 캡처), kind 별 항목(Table=상세·관계 상세·관계 확장 1~3-hop
  chips·중심 보기·컬럼 펼침/접기·AI 능동 분석·FQN 복사 / Column=+소속 테이블 상세 / Term /
  Combo / Canvas). HTML 오버레이(DOM 생성, innerHTML 미사용)라 G6 setData 재구성과 무간섭.
  뷰포트 clamp + Esc/외부클릭/스크롤 dismiss + ↑/↓/Enter 키보드. (2) **관계 상세 패널**
  (`_metaGraphShowRelations`) — depth=1 관계를 방향별(참조함→/참조받음←/연관 용어/주변 관계)로
  그룹, 추정/신뢰 배지 + weight + cardinality + 근거 한글 라벨(fk_introspect/inferred/
  conversation/llm_insight) + 상대 노드 설명, 행 클릭 = 상대 노드 상세 이동. 상세 카드 head 에
  "🔗 관계 상세" 진입 링크(비-우클릭 발견성). (3) **중심 보기**(`_metaGraphFocus`) — 모델 리셋
  후 앵커 N-hop 만 로드(누적 confusion 없이 관심 노드 집중). (4) 빈상태 안내·상태줄에 우클릭 힌트.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaCtx*`/`_metaGraphCtx*` 메뉴 인프라,
    `_metaGraphShowRelations`/`_metaGraphRenderRelations`, `_metaGraphFocus`, `_metaInitGraph`
    contextmenu 바인딩, `_META_EDGE_SOURCE_KO`/`_META_EDGE_TYPE_KO`, 상세 카드 rel 링크)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.admin-meta-graph-ctxmenu`/`.amgc-*`,
    `.amgr-*` 관계 패널·진입 링크)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (빈상태 우클릭 안내, cache-buster
    `styles.css` → `?v=20260702-graph-ctxmenu`, `admin.js` → `?v=20260702-graph-ctxmenu2`(perf-bg 병합 후 재부여))
  - `unit/feature-0016-metadata-graph/docs/{TASK,TEST,REVIEW,REPORT,MODIFY}.md`
- Impact: frontend-only(데이터 API·RBAC·백엔드 불변 — 기존 `metadata.graph.read` 읽기 표면만
  사용, mutation 0 = CONVENTIONS §10.7 대상 아님). 검증: node --check + WSL-headless-harness
  **28/28 PASS**(네이티브 우클릭 이벤트 경로 포함) + §18.8 적대 패널 MAJOR 3 전건 수정(엣지
  우클릭 메뉴·로컬 조인 컬럼 표기·중심 보기 지속 칩 — REV-20260702T121500). 배포=web 재빌드
  후 PB-0008 실 Windows 시각검증(TEST.md).
- Rollback Notes: admin.js/styles.css/admin.html git revert + cache-buster 환원(graph-g6b·
  aiops-scroll). 데이터·API 무손상.
## CHG-20260702T140000-ai-claude-feature-0016-graph-ctxmenu-pb
- Date: 2026-07-02
- Related Requirement: graph-ctxmenu(CHG-20260702T120000, PR #538)의 배포·PB-0008 라이브 실측 완수 기록 — 문서 전용, 코드 무변경.
- Summary: PR #538 main 병합(16fc1598) → deploy-web.sh 무중단 롤링 배포(soak 90s 통과) → 자산 서빙 검증(admin.js ctxmenu2 심볼 10건·styles.css 클래스 20건) → **실 Windows Chrome 라이브 실측 PASS**(우클릭 메뉴 전 항목·관계 상세 패널·중심 보기 지속 칩+복귀·클러스터 메뉴·Escape dismiss — Chrome 149 Playwright eval 회귀 해소 확인, 스크린샷 4매 artifacts). TEST×2/TASK(T24.5·T24.6 완료)/REPORT/wiki(Log·hot) 정합.
- Files: `unit/feature-0003-agent-web-ui/docs/TEST.md`, `unit/feature-0016-metadata-graph/docs/{TEST,TASK,REPORT,REVIEW,MODIFY}.md`, `wiki/{Log,hot}.md`
- Impact: 문서 전용. 코드/배포 산출물 무변경(이미 16fc1598 라이브).
- Rollback Notes: 문서 되돌림 외 없음.
## CHG-20260702T114500-graph-initview
- Date: 2026-07-02
- Related Requirement: 사용자 보고 — 스키마 클러스터 내 테이블·컬럼 노드가 많을 때 초기 전체-fit 과도 줌아웃으로
  초반 가시성 붕괴. 다각도 검토 후 사용자 결정 "Phase 1+2 통합"(TASK §25, PLAN-APPROVED 2026-07-02).
- Summary: 그래프 뷰 초기 진입을 **스키마-우선(카드+테이블수 배지 → per-schema lazy 펼침, "XS:" 접기)** 으로
  재설계하고 **판독 줌 클램프**(fit 후 0.55 하한·1.0 상한, zoomRange [0.05,4]) + 이웃확장 **앵커 국소 focus** 로
  줌아웃 재발을 차단, **미니맵·줌 툴바·스키마 점프** 추가. 레이아웃 밀도(다열)는 병렬 머지된 graph-g6b(#533)
  masonry 를 채택(자체 구현 폐기)하고 graph-perf-bg(#537) `_opSeq` 세대에 ExpandSchema 를 편입(교차 스코프
  오염·stale 렌더 차단), graph-ctxmenu(#538)와 정합. 카드↔combo 동일-id 타입 전환의 G6 setData diff 자식
  유실은 `SC:` id 네임스페이스로 차단.
- Files:
  - `unit/feature-0002-agent-core/src/modules/metadata_graph.py` (`scope_schemas` count 집계·limit+1 truncated·집계실패
    배지강등 / `schema_tables` truncated 신설)
  - `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py` (`?mode=schemas`/`?schema=` 분기 — 신규 route 0)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaG6Build` 카드 게이팅(masonry 통합)·`SC:`/`XS:` 라우팅·
    `_metaGraphExpandSchema`/`CollapseSchema`/`ShowClusterDetailLocal`·`_metaGraphFitClamped`·renderedIds 매핑·
    minimap/zoomRange/줌툴바/점프 바인딩·검색/이웃 스키마 자동펼침)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (툴바 줌컨트롤·점프 select·범례; cache-buster `?v=20260702-graph-initview2`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (줌 툴바·스키마카드 범례·minimap 카드 CSS)
  - `unit/feature-0016-metadata-graph/{docs/*,tests/test_metadata_graph_units.py}` (§25·검증 기록·graceful 단위테스트)
- Impact: 비파괴 additive — 기존 API 3모드(q/node/scope) 응답 shape 불변(`truncated` 필드만 추가), 신규 쿼리
  파라미터만 추가. 혼합버전 안전: 구 백엔드+신 admin.js 는 mode 무시 응답을 카드 게이팅이 흡수(강등 동작,
  loaded 미마킹으로 재시도 보존), 구 admin.js+신 백엔드는 기존 scope_roots 경로 그대로. 인증/데이터 파괴 없음.
  배포=web 재빌드. 1·2차 적대 리뷰/검증 전건 반영(REVIEW.md), stale-base merge 재정합 2회(#533/#537, #538) 포함.
- Rollback Notes: git revert(프론트 3파일+백엔드 2파일) + cache-buster 이전값(graph-ctxmenu2). 데이터·그래프 무손상.

## CHG-20260702T172500-schema-card-ctxmenu
- Date: 2026-07-02
- Related Requirement: 사용자 요청 — ① 미펼침 스키마 카드 우클릭 동작, ② 카드 "테이블" 문자열 공간 과점유 개선. TASK §26.
- Summary: (1) `node:contextmenu` 가 스키마 카드 렌더 id 의 `SC:`/`XS:` prefix 를 벗기지 않아 우클릭이 무반응이던
  결함 수정 — 신규 `_metaGraphCtxForSchema`(펼치기/접기·클러스터 상세·스키마명 복사) 로 라우팅, `_metaGraphCtxForCombo`
  에 접기 파리티 추가. (2) 카드 라벨을 스키마명 전용으로 두고 테이블 개수를 우상단 **G6 badge** 로 이전 —
  인라인 "· 테이블 N" 의 폭 과점유·이름 truncate 완화. 집계 실패는 badge 없음(배지없는 카드 강등 §25 V-H 정합).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`node:contextmenu` SC:/XS: 라우팅·`_metaGraphCtxForSchema` 신설·
    `_metaGraphCtxForCombo` 접기 파리티·`_metaG6Build` 카드 라벨=이름+개수 badge)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `?v=20260702-schema-card-ctxmenu`)
- Impact: frontend-only 비파괴 추가. 데이터 API·백엔드 무변경. 기존 combo/노드/엣지/캔버스 우클릭·좌클릭 회귀 없음
  (harness 확인). 배포=web 재빌드(정적 자산).
- Rollback Notes: admin.js 두 함수 diff revert + 카드 라벨 원복 + cache-buster 이전값(graph-initview2). 데이터 무손상.

## CHG-20260702T173000-search-badge
- Date: 2026-07-02
- Related Requirement: 사용자 보고 — 검색 시 접힌 스키마 카드 테이블 개수 badge 소실. 요청 표기: 검색 없음 `[전체]`, 검색 `[매칭/전체]`. TASK §27.
- Summary: 그래프 검색을 **스키마 카드 필터 뷰**로 재설계 — 이전엔 매칭 스키마를 combo 로 auto-expand 해 카드·badge 가 사라졌음.
  이제 매칭을 스키마별로 집계해 카드를 유지하고 badge 를 `매칭/전체`(teal)로 표기, 검색 없을 땐 `전체`(남색). scope별 전체
  테이블수를 `schemaTotals` 캐시(roots 재구축, resetModel 보존)로 유지해 검색 모델 리셋 후에도 분모(전체 개수)를 안다.
  펼친 스키마 안에서 매칭 테이블은 rel 부스트로 크게 강조. GlossaryTerm/기타 매칭은 terms 로 표시.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraph` schemaTotals/searchMatch/searchMatchTables 필드·
    resetModel 초기화(schemaTotals 보존)·loadRoots schemaTotals 재구축·`_metaGraphSearch` 카드필터 재설계·`_metaG6Build`
    카드 badge 매칭/전체·매칭 테이블 rel 강조)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `?v=20260702-search-badge`)
- Impact: frontend-only 비파괴. 데이터 API·백엔드 무변경(기존 search_nodes 응답 그대로 사용). 검색 UX 변경: 매칭 테이블
  노드 직접 나열 → 스키마 카드(매칭/전체) 필터 후 카드 클릭 드릴다운(8K 규모 정합). 배포=web 재빌드.
  알려진 한계: search_nodes cap(80) 초과 광역 검색은 매칭 카운트가 부분값(카드 클릭 펼침 시 실제 매칭은 rel 강조로 식별).
- Rollback Notes: admin.js search/build/resetModel/loadRoots diff revert + cache-buster 이전값(schema-card-ctxmenu). 데이터 무손상.

## CHG-20260702T175500-search-badge-pb0008
- Date: 2026-07-02
- Related Requirement: search-badge(CHG-20260702T173000, PR #544) 배포 후 PB-0008 실 Windows 시각검증 결과 기록. TASK §27 T27.7.
- Summary: docs-only — 코드 변경 없음. 검색 시 스키마 카드 badge 매칭/전체(teal, cap `+`) 라이브 실측 PASS 를
  feature-0003/feature-0016 TEST.md 에 POST-DEPLOY 갱신, TASK §27 T27.6/T27.7 완료 체크.
- Files: `unit/feature-0016-metadata-graph/docs/{TASK,TEST}.md` · `unit/feature-0003-agent-web-ui/docs/TEST.md` (Run 기록만).
- Impact: 문서만. 코드·자산·데이터 무변경. 배포 불요.
- Rollback Notes: 해당 Run/체크 라인 revert(무영향).
## CHG-20260702-graph-expand-perf-refreshstates
- Date: 2026-07-02
- Related Requirement: 사용자 관찰(graph-perf-bg 배포 후) — `mssql-qa-idc.dk_data_release.Achievement` 테이블 노드 더블클릭 시 **2~3초 프리즈 잔존**, 개선 요청. 정본: DECISIONS ADR-006.
- Summary: 실측 진단으로 프리즈 근본원인을 특정 — `_metaGraphRefreshStates` 의 **전 노드 개별 `g.setElementState`**(G6 v5 건당 ~50ms, 실측 200노드=10,046ms). fetch(AGE depth=2=135ms)·render(setData+draw≈200ms)·introspection(analyzed 라 skip) 모두 병목 아님. 수정: (1) `_metaG6Apply` 가 setData 후 `_stateCache` 를 clear 대신 **방금 bake 된 signature 로 populate** → rebuild 직후 refresh no-op, (2) `_metaGraphRefreshStates` 변화분만 적용 + 변화>4 면 per-node 대신 **`_metaG6Apply(false)` 단일 rebuild** 폴백(전 상태 한 번에 bake), (3) 폴 tick 이중 refresh 를 **rAF coalescing** 으로 1회 병합(재진입 방지). 결과 ~9s→~0–80ms.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaG6Apply` 캐시 populate; `_metaGraphRefreshStates` → 변화분+rebuild 폴백+rAF coalesce, 본문은 `_metaGraphRefreshStatesNow`)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260702-graph-expand-perf`)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-006),TASK(§24),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 렌더 상태-갱신 계층만. 데이터 API·그래프 스키마·마커 시맨틱 **불변**. setElementState 사용처를 단일노드(_metaApplyState) + refreshStates(변화분/폴백) 로 한정. 마이그레이션 없음. 검증: 헤드리스 harness 실측(9s→82ms) + §18.8 적대 2렌즈(정확성 상태유실 BLOCKING 0 / 프리즈재발 — 폴 이중 refresh 지적→coalescing 반영). 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows(대량 스키마 노드 더블클릭 무프리즈).
- Rollback Notes: admin.js git revert(graph-perf-bg 상태로) + cache-buster 이전값(graph-perf-bg). 데이터·API·스키마 무손상(상태-갱신 계층만).

## CHG-20260702-graph-dblclick-cam-anim
- Date: 2026-07-02
- Related Requirement: 사용자 관찰(프리즈 해소 후) — 테이블 노드 더블클릭 시 카메라가 순간이동 재배치되어 불편. "카메라 [고정/애니메이션] 자율 판단하여 개선" 위임. 정본: DECISIONS ADR-008.
- Summary: 더블클릭 이웃 확장(`_metaGraphExpand`)의 앵커-중심 국소 focus 를 **즉시(animation=false) → 애니메이션(`{duration:420,easing:'ease-in-out'}`)** 으로. 판독 하한 clamp(zoomTo)는 즉시 유지(팬 애니 중첩 회피), seq 가드로 연타 stale 애니 방지. 자율 판단 = 애니(고정은 새 이웃이 화면 밖이라 부적합; 앵커-중심 focus 로 클릭 대상 프로미넌트 유지 + 부드러운 전환). 적대 검증이 최초 오편집(우클릭 `_metaGraphFocus` 함수 수정)을 적발 → 진짜 더블클릭 `_metaGraphExpand` 로 교정 + focus 함수 원복.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraphExpand` 카메라 블록: `focusElement(fel, false)` → `focusElement(fel, {duration:420,easing})` + seq 가드)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260702-graph-dblclick-cam`)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-008),TASK(§30),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 카메라 거동만(더블클릭·depth-select 재확장 경로). 데이터 API·스키마·마커·다른 fit 경로(loadRoots/검색/리사이즈/우클릭 중심보기) **불변**. `focusElement`/`zoomTo` 는 viewport transform 만이라 노드 재렌더·프리즈 무관(ADR-006 무간섭). 마이그레이션 없음. 검증: `node --check` PASS · G6 카메라 애니 API 헤드리스 검증(animation:false 그래프에서 per-call 애니 스펙 동작) · §18.8 적대 리뷰(라우팅 오류 적발→교정, 앵커 노드 렌더 보장 확인). 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows(더블클릭 부드러운 팬).
- Rollback Notes: `_metaGraphExpand` focus 애니 인자를 `false` 로 환원 + cache-buster 이전값(graph-expand-perf). 데이터·API 무손상.

## CHG-20260702-graph-dblclick-cam2-manual-tween
- Date: 2026-07-02
- Related Requirement: 사용자 재보고 — graph-dblclick-cam 배포 후에도 더블클릭 시 **애니 없이 카메라 순간이동**. 근본원인: graph config `animation:false` 가 per-call 카메라 애니(focusElement/zoomTo 의 animation 인자)까지 무효화 → 지난 `focusElement({duration:420})` 는 no-op. 정본: DECISIONS ADR-009.
- Summary: 실증(headless: animation:false→focusElement 2ms 즉시 / true→412ms 애니)으로 no-op 원인 특정. 전역 animation ON 은 setData 셔플 재발, setOptions 토글은 tween 창 동시 rebuild 셔플 위험 → **G6 애니 우회 manual rAF tween** 채택. 신규 `_metaGraphAnimateFocus(key, seq)`: 앵커 `getElementRenderBounds` 중심 → `getViewportByCanvas` → 뷰포트 중앙(`getSize()`/2) delta 를 rAF 이징 누적 `translateBy`(420ms). `_metaGraphExpand` 가 no-op focusElement 대신 이 헬퍼 호출. setData 미사용·전역상태 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraphAnimateFocus` 신규 헬퍼 + `_metaGraphExpand` 카메라 블록 1줄 교체; +45/−13)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260702-graph-dblclick-cam2`)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-009),TASK(§31),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 카메라 거동만(더블클릭·depth-select 재확장). 데이터 API·스키마·마커·다른 카메라 경로(loadRoots/검색/리사이즈/우클릭 중심보기) **불변**. 마이그레이션 없음. tween=viewport transform 만(노드 재렌더·프리즈 무관, ADR-006 무간섭). 검증: `node --check` PASS · manual tween 헤드리스 실증(앵커 정중앙 26프레임/434ms) · §18.8 적대 6축 BLOCKING 0(G6 번들 소스 대조 — tween 수학=G6 focus 공식 동일). 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows(부드러운 팬 육안).
- Rollback Notes: `_metaGraphAnimateFocus` 호출을 `focusElement(fel, false)`(즉시) 로 환원 + 헬퍼 제거 + cache-buster 이전값(graph-dblclick-cam). 데이터·API 무손상.

## CHG-20260703-node-role-viz
- Date: 2026-07-03
- Related Requirement: 사용자 요청(2026-07-02) — 그래프 뷰 노드가 단순 사각형+글자라 가시성 저하. **AI 능동 분석 완료 노드에 테이블 역할을 명시하는 시각 표식**을 웹 리서치 기반으로 구성. 정본: DECISIONS ADR-010, TASK §32.
- Summary: 테이블 역할 8종 고정 분류(NODE_ROLES: master/account/transaction/log/mapping/config/stats/etc)를 도입하고 분석 완료 테이블 칩을 **역할색(Okabe-Ito 색약 안전 팔레트) + 라벨 앞 역할 아이콘 + 범례 행 + 상세/진행 패널 역할 칩**으로 인코딩. 데이터 경로: LLM 분석 계약(NODE_ANALYSIS_PROMPT)에 `role` enum 추가 → worker `_resolve_role`(LLM 유효값 우선, 무효/누락은 `classify_role_heuristic` 이름·본문 2-pass 폴백, Table 외 NULL) → `node_analysis_jobs.role`(alembic 0031 비파괴 ADD) 저장. 기존 done 행은 insight-worker 틱 `backfill_roles()`(휴리스틱, LLM 재호출 없음, 틱당 200행, 멱등·자기종결) 백필. 조회(get_scope_analysis_status/get_run_status/get_node_analysis) + bulk status API 에 roles 노출. FE 는 캐시 서명 `#R=` suffix 로 역할 도착 시 rebuild 승격(역할은 bake 스타일 — setElementState 불가).
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260702_0031_node_analysis_role.py` (신규 — ADD COLUMN role)
  - `unit/feature-0002-agent-core/src/modules/node_analysis.py` (NODE_ROLES·_ROLE_RULES·classify_role_heuristic·_resolve_role·role 저장·조회 3함수 확장·backfill_roles)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (NODE_ANALYSIS_PROMPT role 계약 + docstring)
  - `unit/feature-0002-agent-core/src/modules/insight.py` (틱에 backfill_roles 배선)
  - `unit/feature-0002-agent-core/tests/test_node_analysis_role.py` (신규 13건)
  - `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py` (bulk status 응답 roles)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (_META_ROLE·roles Map·_metaTableStyle(role)·_metaG6Build 아이콘 라벨·_metaCacheSig/#R= 서명·refreshStates rebuild 승격·마커 3경로 배선·상세/진행 패널 역할 표기)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (역할 범례 행 + cache-buster 20260703-node-role-viz)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§32),DECISIONS(ADR-010),REPORT,REVIEW,TEST,FUNCTION}.md`
- Impact: 비파괴 — 미분석 노드·기존 마커·데이터 API 계약(추가 필드만)·RBAC(`metadata.graph.read` dependency 불변)·그래프 스키마(AGE) 무변경. 마이그레이션 = ADD COLUMN 1개(expand-only, §12 사전승인). 배포 = alembic 0031 + web·insight-worker 재빌드. 검증: 단위 13건 + 전체 pytest 회귀 exit 0 + headless harness(실 admin.js + mock API) 4 시나리오 PASS·pageerror 0. 완료 게이트 = PB-0008 실 Windows 시각검증.
- Rollback Notes: admin.js/admin.html/라우터/모듈 git revert + cache-buster 이전값. alembic downgrade = DROP COLUMN role(분류값만 소실 — 분석문 무손상, 재백필 가능).
## CHG-20260703-graph-dblclick-latency
- Date: 2026-07-03
- Related Requirement: 사용자 관찰(graph-dblclick-cam2 배포 후) — 카메라 팬이 부드럽긴 하나 더블클릭 직후가 아닌 **~350ms 텀을 두고 시작**돼 답답. 정본: DECISIONS ADR-011.
- Summary: 원인 = 팬이 파이프라인 맨 끝(fetch+rebuild 후)에서 시작. 수정: (1) `_metaGraphExpand` 가 카메라 팬을 busy 직후 **fetch 전 fire-and-forget** 으로 시작(앵커 이미 렌더 → 즉시 반응), 파이프라인 끝 await 호출 제거. (2) `_metaGraphAnimateFocus` 를 고정-duration → **적응형 follow**(매 프레임 앵커 현재 위치 재조회 → 잔여 delta K=0.24 translateBy, ease-out)로 재작성 — rebuild 로 앵커 이동/재생성돼도 최종 위치 수렴. 종료=수렴/seq/MAXMS(1200ms) 단일 시간상한(프레임카운트 조기포기 제거 — 저사양 대비). W/H 매 프레임 재조회, API 부재 시 focusElement 폴백.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_metaGraphAnimateFocus` 적응형 follow 재작성 + `_metaGraphExpand` 팬 호출을 fetch 전 fire-and-forget 으로 이동, 끝 await 제거)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260703-graph-dblclick-latency`)
  - `unit/feature-0016-metadata-graph/docs/{DECISIONS(ADR-011),TASK(§34),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 카메라 거동만(더블클릭·depth-select 재확장). 데이터 API·스키마·마커·다른 카메라 경로 **불변**. 마이그레이션 없음. tween=viewport transform 만(ADR-006 프리즈 무관). 검증: `node --check` PASS · 적응형 follow 헤드리스 실증(fire-and-forget 즉시 시작 + 중간 setData 앵커 이동 → 24프레임 중앙 수렴) · §18.8 적대 7축 BLOCKING 0(MEDIUM missStreak 조기포기→제거, NIT API폴백·W/H→반영). 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows(더블클릭 즉시 부드러운 팬).
- Rollback Notes: `_metaGraphAnimateFocus` 를 이전(고정-duration) 으로 환원 + expand 팬 호출을 파이프라인 끝 await 로 복귀 + cache-buster 이전값(graph-dblclick-cam2). 데이터·API 무손상.

## CHG-20260703-role-legend-panel
- Date: 2026-07-03
- Related Requirement: 사용자 요청(그래프 뷰 노드 시각화 개선) — "테이블 역할(AI 분석 완료 시 칩 색)" 범례를 **다른 위치에 세로로 구성 + 접힐 수 있도록**. node-role-viz(CHG-20260703-node-role-viz, PR #555 병합·배포 완료) 위에 얹는 UI 개선. 배치 위치는 사용자가 "우측 상세 패널 상단" 선택.
- Summary: 역할 범례를 툴바 아래 **가로 전폭 2번째 범례 행**(`.admin-meta-graph-legend-roles`)에서 **우측 상세 패널**(`aside#metadataGraphDetail`) **최상단**의 **세로 스택 + 네이티브 접힘**(`<details class="admin-meta-graph-rolelegend" open>`) 카드로 이전. summary=토글 헤더(커스텀 카펫 `▸`/rotate, `::-webkit-details-marker` 제거), 칩 8종(색+아이콘+라벨)은 `<ul><li>` 세로 스택으로 유지. 전폭 행 제거로 그래프 세로 공간 확보. 무JS(네이티브 details). 범례는 detailBody 의 형제(위)라 노드 선택·능동분석 렌더(detailBody/progress 만 innerHTML 교체)에 지워지지 않음.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (전폭 `.admin-meta-graph-legend-roles` 행 제거 → `aside#metadataGraphDetail` 최상단 `<details>` 범례 삽입 + cache-buster `styles.css?v=20260703-reldetail-colexpand-role-legend-panel`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.admin-meta-graph-legend-roles` 가로 규칙 2줄 제거 → `.admin-meta-graph-rolelegend` 세로·접힘 카드 규칙 추가)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§35),REPORT,REVIEW}.md`
- Impact: 프론트 **표현 전용**(admin 그래프 뷰 역할 범례 위치·레이아웃만). 데이터 API·스키마(AGE)·마커·칩 색/아이콘 인코딩·RBAC·JS 로직 **전부 불변**. 마이그레이션 없음. `.admin-meta-graph-legend-roles` 잔여 참조 0(html/css/js grep). aside 는 폭 조회(`d.clientWidth`)로만 참조되고 innerHTML 교체 없음 → 범례 wipe 없음. 부작용: "상세 ⇆"(`#metadataGraphDetailToggle`)로 상세 패널 접으면 범례도 같이 숨음(패널 종속 — 사용자 선택 위치의 자연 귀결). 검증: 구조 정합(무JS·`<details>` 관용구 기존 line 512 재사용) + §18.8 적대 리뷰 [SUBAGENT](REVIEW REV 참조) + 배포=web 재빌드 + 완료 게이트 PB-0008 실 Windows.
- Rollback Notes: admin.html/styles.css git revert + cache-buster 이전값(reltrace-tabledetail). 데이터·API·JS 무손상(표현 전용이라 revert 리스크 최소).

## CHG-20260703-graph-rel-layout
- Date: 2026-07-03
- Related Requirement: 사용자 요청(관리 콘솔 > 메타데이터 > 그래프 뷰) — 관계 연결이 복잡해질수록 가시성 저하, 스키마 카드 내 테이블의 단순 나열이 이를 악화. ① 연결선이 되도록 교차하지 않게 ② 관계가 확보될수록 연결·유사도 기준으로 노드 배치. 정본: DECISIONS ADR-012 / TASK §38.
- Summary: `_metaG6Build` 의 배치 순서를 자연정렬 → **관계(REFERENCES) 가중치의 순수 함수**로 승격. (1) `_metaRelAdjacency`: 엣지 끝점을 테이블로 승격해 무향 인접행렬(유사도 w=trusted 2·그 외 1). (2) `_metaRelSchemaOrder`: greedy attachment seriation — 관계 많은 스키마끼리 shelf 순서 인접. (3) `_metaRelTableOrder`: 클러스터 내부를 관계 연결 컴포넌트 BFS(가중 desc) 군집 + 외부앵커 + 고립 자연정렬. (4) `_metaRelOrderAll`: barycenter 4-sweep(gpos=schemaIdx+로컬 rank, SPAN=1) 으로 이웃 위치 가중평균 재정렬 — 나란한 클러스터 간 상호 교차 해소. 관계 0 이면 기존 자연정렬과 완전 동일(강등 없음), 관계가 쌓일수록 rebuild 시 배치가 관계 기준으로 수렴(사용자 요청 ②의 자연 구현).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (신규 `_metaRelTableKeyOf`/`_metaRelAdjacency`/`_metaRelSchemaOrder`/`_metaRelTableOrder`/`_metaRelOrderAll` + `_metaG6Build` ids·items 배선)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (cache-buster `admin.js?v=20260703-graph-rel-layout`)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§38),DECISIONS(ADR-012),MODIFY,REPORT,TEST,REVIEW}.md`
- Impact: 프론트 **배치 순서 전용** — 데이터 API·AGE 스키마·마커·상태·RBAC·마이그레이션 전부 불변. 결정론 grid(setData+draw)·펼침-불변(ADR-004 ②)·카드 게이팅·masonry/shelf-pack 골격 유지(순서 입력만 교체). 배치 변화는 관계 데이터가 늘어난 rebuild 시점뿐(기존 shelf 재배치 시야고정 경로가 흡수). 검증: Node 격리 8/8 + 벤치(2D 교차 12~30% 감소) + node --check. 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows.
- §18.8 패널 후속 수정(같은 cycle): ① `_metaGraphCollapse` — 컬럼 접기 시 REFERENCES 모델 엣지 **보존**(containment 만 삭제; 접기 제스처의 배치 재셔플(MAJOR)과 접힌 테이블 관계 표시 소실을 동시 해소) ② `_metaGraphExpand` — rebuild 후 follow tween 사망 시 무애니 focusElement 폴백(`_metaGraph._focusLive` 생존 마커, `_metaGraphAnimateFocus` 를 marker 래퍼+`_metaGraphAnimateFocusRun` 으로 분리) ③ `_metaG6Build` — itemsNat 중복 정렬 제거(relOrder 직접 소비). 격리 테스트 10/10(구조 회귀 방지 t8·t9 포함).
- Rollback Notes: admin.js 신규 함수 5종 제거 + `_metaG6Build` 의 ids/items 를 자연정렬로 환원 + collapse/expand/AnimateFocus 를 이전 형태로 복원 + cache-buster 이전값(20260703-reldetail-colexpand). 데이터·API 무손상(표현 전용).

## CHG-20260703-role-legend-bottom
- Date: 2026-07-03
- Related Requirement: 사용자 후속 피드백(role-legend-panel 배포 후) — ① 역할 범례를 상세 패널 **하단**에 배치, ② 범례 **확장 시 기존 UI(노드 상세)를 밀어 내용이 뒤틀리는 문제** 해소. role-legend-panel(CHG-20260703-role-legend-panel) 위 후속 개선.
- Summary: 역할 범례 `<details class="admin-meta-graph-rolelegend">` 를 `aside#metadataGraphDetail` **최상단(progress/detailBody 앞) → 최하단(마지막 자식)**으로 이동. aside 를 `display:flex; flex-direction:column` 으로, 범례에 `margin-top:auto`(콘텐츠 짧을 때 패널 **바닥 고정**), `.admin-meta-graph-detail > * { flex-shrink:0 }`(자식 압축 금지 → overflow 시 컨테이너 스크롤, 노드 상세가 눌려 잘리는 뒤틀림 방지). 범례가 **마지막 자식**이라 접힘/펼침이 위의 progress·노드 상세를 **밀지 않음** → "확장 시 뒤틀림" 근본 해소.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (범례 블록을 aside 첫 자식 → 마지막 자식(detailBody 뒤)으로 이동 + cache-buster `styles.css?v=20260703-role-legend-bottom`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.admin-meta-graph-detail` 에 `display:flex; flex-direction:column` + `.admin-meta-graph-detail > * {flex-shrink:0}` + `.admin-meta-graph-rolelegend` `margin-bottom:12px` → `margin-top:auto`)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§38),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 **표현 전용**(상세 패널 내부 레이아웃만). 데이터 API·스키마·마커·칩 인코딩·RBAC·JS 로직 **전부 불변**. 마이그레이션 없음. 범례는 여전히 detailBody 형제(이제 아래)라 innerHTML 교체(detailBody/progress 만)에 지워지지 않음. 검증: **headless playwright 렌더 격리 실증** — 빈 상세=범례 바닥고정(pinnedNearBottom, 위 여백 262px), 긴 상세 30행=노드 상세 firstNodeH 32(온전·미압축)·dbH==dbScrollH(983, 잘림 없음)·aside canScroll=true(스크롤) → 밀림/뒤틀림 없음. + §18.8 적대 리뷰 [SUBAGENT](REVIEW REV 참조) + 배포=web 재빌드 + 완료 게이트 PB-0008 실 Windows.
- Rollback Notes: admin.html(범례 위치 원복)·styles.css(flex/margin 원복) git revert + cache-buster 이전값(reldetail-colexpand-role-legend-panel). 데이터·API·JS 무손상.

## CHG-20260703-cluster-role-prefix
- Date: 2026-07-03
- Related Requirement: 사용자 후속 요청(그래프 뷰) 3건 — ① 스키마 클러스터 상세의 테이블 목록에서 AI 능동 분석 완료 테이블은 역할 칩을 **접두사**로(미분석은 동일 폭 빈 슬롯 → 라벨 정렬 유지, 뒤틀림 방지) ② 그 목록 **각 행 클릭 → 해당 노드 선택** ③ 역할 **범례 hover 툴팁**.
- Summary: (1) `_META_ROLE` 에 `desc`(역할 설명) 필드 추가 — 범례 툴팁·접두사 툴팁 단일 소스(BE node_analysis.NODE_ROLES 휴리스틱 정합). (2) 신규 `_metaRoleChipHTML(role,esc,small)` 역할 칩 조립 헬퍼. (3) `_metaGraphRenderClusterDetail` 테이블 목록: 각 행을 `<button class="amgr-ct-row" data-node-key>` 로, `_metaRoleOf(key)` 있으면 역할 칩 접두사, 없으면 `amgr-role-none`(transparent, 18px 폭 유지) → `<code>` 라벨 좌측 정렬 보존. innerHTML 직후 행 클릭 바인딩 → `_metaGraphShowDetail(key)`(setSelected 하이라이트+상세) + 렌더 시 `focusElement`. (4) 신규 `_metaRoleLegendTips()` — 정적 범례 `<li data-role>` 에 `_META_ROLE.desc` 로 hover `title` 주입, 그래프 뷰 진입 시 1회 호출. admin.html 범례 `<li>` 에 `data-role` 추가.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (`_META_ROLE.desc` + `_metaRoleChipHTML` + `_metaRoleLegendTips`(진입 함수 배선) + `_metaGraphRenderClusterDetail` 테이블 목록 접두사·행 버튼·클릭 바인딩)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (범례 `<li>` 에 `data-role` 8개 + cache-buster `admin.js`·`styles.css` `?v=20260703-cluster-role-prefix`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.amgr-cluster-tables`/`.amgr-ct-row`/`.amgr-role-chip(-sm)`/`.amgr-role-none`/`.amgr-ct-desc` 규칙)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§39),REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 **표현 + 클릭 상호작용**(클러스터 상세 목록 + 범례 툴팁). 데이터 API·AGE 스키마·RBAC·마이그레이션 **불변**. `_META_ROLE.desc` 추가는 기존 소비처(칩 색·배지) 무영향(신규 필드). 클릭은 기존 `_metaGraphShowDetail` 재사용(선택 semantics 동일). 미분석 테이블 정렬 = `amgr-role-chip-sm` 고정 18px 슬롯. 검증: `node --check` PASS + **headless playwright 렌더 격리 실증**(분석/미분석 5행 → 전 라벨 left=45px 정렬 `allCodesAligned`, 칩 18px 균일, 전 행 button) + §18.8 적대 리뷰 [SUBAGENT](REVIEW REV 참조) + 배포=web 재빌드 + 완료 게이트 PB-0008 실 Windows. (부수: 이 cycle 이 편집한 MODIFY.md 에 graph-rel-layout §38 병합이 남긴 미해결 conflict 마커를 함께 정리 — 양쪽 CHG 보존.)
- Rollback Notes: admin.js(3함수/헬퍼 제거·클러스터 목록 원복)·admin.html(data-role·버스터)·styles.css(amgr-* 규칙) git revert + 버스터 이전값(role-legend-bottom). 데이터·API 무손상.

## CHG-20260703-graph-rel-layout-postdeploy
- Date: 2026-07-03
- Related Requirement: CHG-20260703-graph-rel-layout 의 완료 게이트(TASK §38 T38.8) — 배포 후 PB-0008 라이브 실측 기록.
- Summary: doc-only — 배포 web-a/b `5f439788`(무중단 롤링·soak) 후 실 Windows Chrome PB-0008 라이브 검증 전건 PASS 를 TEST.md(POST-DEPLOY Run)·TASK §38(T38.8 [x])·REVIEW(REV-…-postdeploy) 에 기록. 핵심 실측: 관계쌍 평균 배치 순서 거리 32.5→3.2(90% 감소, gunzgame 115쌍)·군집 육안·collapse REFERENCES 145→145 보존·배치 불변·이웃확장/검색 pageerror 0.
- Files: `unit/feature-0016-metadata-graph/docs/{TASK,TEST,REVIEW,MODIFY}.md` · `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 문서 전용(코드·자산 무변경) — 배포 불요.
- Rollback Notes: 해당 doc 라인 revert.

## CHG-20260703-graph-drag
- Date: 2026-07-03
- Related Requirement: 사용자 요청(관리 콘솔 > 메타데이터 > 그래프 뷰) — ① 마우스 중간(휠) 버튼 드래그를 객체 상호작용이 아닌 **카메라 드래그(팬)**로, ② **테이블 노드 이동 시 하위 종속 UI(접기 "X:" 컨트롤 + 컬럼 노드) 동반 이동**. 정본: TASK §41 / REVIEW REV-20260703T021144-graph-drag.
- Summary: (①) G6 `behaviors` 를 문자열 → object-form 으로 전환 + `enable` 오버라이드 — `_metaCanvasDragEnable`(중간버튼이면 targetType 무관 팬 허용, 아니면 기존대로 빈 캔버스만) + `_metaElementDragEnable`(중간버튼이면 노드 이동 거부 → 팬에 양보). `_metaEventButtons`/`_metaIsMiddleDrag` 로 buttons 비트마스크(4=중간) 견고 판정(G dragstart 의 button=-1 대비 buttons·nativeEvent fallback). 컨테이너 `mousedown`(button===1) `preventDefault` 로 브라우저 autoscroll(팬 커서) 억제 — pointer 이벤트 흐름은 유지되므로 drag-canvas 정상. (②) `node:dragstart/drag/dragend` 리스너 + `_metaGraph.tableDeps`(Table key → 종속 노드 id[], `_metaG6Build` 매 재구성 리셋·재채움). dragstart 에서 각 종속의 테이블 대비 오프셋(월드) 기록, drag/dragend 에서 `translateElementTo(테이블 현재위치 + 오프셋)` 절대이동 — 핸들러 실행 순서 무관(dragend 재정합으로 1-frame lag 제거).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (behaviors object-form + `_metaEventButtons`/`_metaIsMiddleDrag`/`_metaCanvasDragEnable`/`_metaElementDragEnable`/`_metaNodeDragStart`/`_metaNodeDrag`/`_metaNodeDragEnd` 신규 + `_metaGraph.tableDeps`/`_drag` 필드 + `_metaG6Build` tableDeps 배선 + 컨테이너 mousedown·node:drag 리스너)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§41),MODIFY,REPORT,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 **상호작용 전용** — 데이터 API·AGE 스키마·마커·상태·칩 인코딩·RBAC·마이그레이션 전부 불변. 결정론 grid(setData+draw)·기존 zoom-canvas/node:click/contextmenu/미니맵/우클릭 메뉴 무변경. 종속 동반 이동은 drag-element 단일 노드 이동과 동일하게 transient(다음 setData 재구성 시 grid 로 복귀). 검증: `node --check` + §18.8 적대 리뷰 [SUBAGENT: PASS](G6 v5.1.1 번들 실측 4축 BLOCKING 0) + **라이브 실 Windows 브라우저(Chrome/149) PB-0008 PASS**(Test A 중간버튼 팬: 노드 월드 [0,0] + 화면 팬 / Test B 좌클릭 테이블: 종속 5개 동일 델타 [191.35,-131.55]). 배포=web 재빌드.
- Rollback Notes: admin.js 신규 7함수 + `tableDeps`/`_drag` 필드 + behaviors object-form + 두 리스너 제거, behaviors 를 `["drag-canvas","zoom-canvas","drag-element"]` 문자열로 환원. 데이터·API 무손상(상호작용 전용).

## CHG-20260703-graph-simgroups
- Date: 2026-07-03
- Related Requirement: 사용자 후속 요청(graph-rel-layout 뒤) — "테이블 노드가 나열되는 배치라 여전히 낮은 가시성. 각 테이블이 서로 유사한 속성끼리 배치되도록(속성 범위가 가시적으로 나타나도록) 근본적인 개선". 정본: DECISIONS ADR-013 / TASK §42.
- Summary: 스키마 클러스터 내부를 **유사 속성 그룹 블록**(색 배경 박스 + 헤더 칩 `스템라벨 · n`)으로 분할 — 군집을 '순서'에서 '가시적 영역'으로 승격. 그룹핑 = (테이블명 affix family 4~16자 지원도×길이) → (관계 가중 attach) → (역할) → (기타), 순수 함수·결정론. 그룹 순서/내부 순서는 ADR-012 seriation·barycenter 컨테이너 재사용. 그룹 블록 2-pass masonry + shelf-pack(펼침-불변 배정·실높이 push-down, ADR-004 ② 계승). 클러스터 상세 목록도 동일 그룹 헤딩. 그룹 <2 스키마·terms 는 기존 평면 masonry(회귀 0).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (신규 `_metaSimFamilies`/`_metaSimGroups`/`_META_GROUP_TINTS` + `_metaG6Build` 그룹 블록 레이아웃(packGroup·place 정규화)·GB:/GH: 장식 노드 + 클릭/ctx/드래그 GB:/GH: 무시 + `_metaGraphRenderClusterDetail` 그룹 헤딩)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캡션 범례 "색 배경 박스=유사 속성 그룹" + cache-buster admin.js/styles.css `20260703-graph-simgroups`)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.amgr-ct-group` 헤딩 행)
  - `unit/feature-0016-metadata-graph/docs/{TASK(§42),DECISIONS(ADR-013),MODIFY,REPORT,TEST,REVIEW}.md` + `unit/feature-0003-agent-web-ui/docs/TEST.md`
- Impact: 프론트 배치·표현 전용 — 데이터 API·AGE 스키마·RBAC·마이그레이션·graph-drag 종속 UI 계약(tableDeps) 불변. GB:/GH: 는 비상호작용 장식(이벤트 무시·드래그 불가·엣지 끝점 불가). 검증: 실 _metaG6Build Node 구동 격리 22/22(무겹침·포함·결정론·펼침-불변·평면 폴백·5.1ms) + node --check. 배포=web 재빌드. 완료 게이트=PB-0008 실 Windows.
- §18.8 패널 후속 수정(같은 cycle, REVIEW REV-20260703T043659): ① GB:/GH: 클릭→`_metaGraphShowClusterDetailById`·우클릭→`_metaGraphCtxForSchema` 위임(combo 배경 데드존 방지) ② 2차 관계 attach 를 1차 스냅샷 `fam1` 참조로 무연쇄화 ③ view 정규화를 공용 `_metaViewNorm`(view_ 접두만) 으로 통일(viewer 미절단) ④ 패널 그룹 헤딩 aria-hidden 제거·role="group"/aria-label·80행 그룹경계 절단표식. 회귀방지 t10~t12(25/25).
- Rollback Notes: admin.js 신규 함수·GB:/GH: 방출·핸들러 분기(클릭/우클릭 위임 포함)·패널 헤딩 revert + admin.html/styles.css cache-buster 이전값(20260703-graph-drag / 20260703-cluster-role-prefix). 데이터·API 무손상.
