---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

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
- 수용 한계(수정 안 함, ADR-005 Consequences ①~④ 기록): dbo-only slot 규약(비-dbo/교차-스키마 후보
  영구 미프로브 — 후속 initiative), introspect 테이블명 케이스 플래핑(SSOT 레벨, TASK-0305 계열),
  실효 cadence ≈30h(window 회전 곱), LEARNING↔PROBE 결합 권장.
- Files: `unit/feature-0002-agent-core/src/modules/{insight,relationships}.py`,
  `unit/feature-0002-agent-core/src/agent_core.py`,
  `unit/feature-0002-agent-core/src/modules/tools.py`,
  `unit/feature-0002-agent-core/tests/{test_relationships,test_config_star_export,test_insight_rel_cadence,test_tools_exec_ctx}.py`,
  `unit/feature-0016-metadata-graph/tests/test_anchor_relationship_live.py`, ADR-005(DECISIONS.md).
- Impact: 백엔드 전용·비파괴(마이그레이션 0). B-F1 로 첫 배포 사이클에 MSSQL 전 DB interval 스캔
  백필(기존에도 cadence 백필 예정이었음 — 범위 동일, 커서만 정확해짐).
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
