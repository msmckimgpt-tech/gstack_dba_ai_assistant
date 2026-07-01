---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

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
