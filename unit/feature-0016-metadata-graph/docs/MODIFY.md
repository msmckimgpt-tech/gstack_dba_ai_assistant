---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

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
