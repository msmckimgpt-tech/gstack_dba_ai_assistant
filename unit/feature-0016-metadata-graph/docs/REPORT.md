# Report

## 2026-07-03 · 메타데이터 객체 의미 임베딩·클러스터링 (semantic-embed, Phase C, TASK §46, ADR-018)

### 배경 (사용자 3대 개선 中 C)
ADR-013 이 이연한 "컬럼 시그니처·설명 임베딩 기반 백엔드 클러스터링". affix 휴리스틱(클라) 위에 서버측 의미 신호를 additive 로 얹는다.

### 구현 (ultracode 워크플로우 설계 → 구현 → 적대리뷰)
- **시그니처 임베딩(재사용)**: 테이블 시그니처(이름+설명+컬럼+역할, DB-distinct)를 기존 texts 저장소에 적재 → 기존
  embedding 데몬이 bge-m3 1024d 임베딩(신규 경로 0). rag_objects.signature_text_hash(strip-hash 정합).
- **저장(비파괴, alembic 0035)**: rag_objects 3 nullable 컬럼 + 인덱스 2. **클러스터링**: insight-worker 데몬이 scope 별
  kNN(τ)+union-find(degree-cap chaining 억제, N>MAX skip OOM 가드), 6h cadence. **투영·프론트**: AGE Table 정점 →
  scope_roots/schema_tables RETURN → `_metaSimGroups` be: 우선(affix 폴백). un-cluster=명시 null clear(phantom 방지).
- kill switch(AGENT_METADATA_CLUSTER_AUTO=0)·fail-soft·affix 폴백. 클러스터 값은 eventual(데몬 cadence).

### 검증
- node --check·py ast·migrate-lint expand-safe·순수함수 4/4·metadata_graph 회귀 10 PASS.
- **§18.8 2단계 적대검증**: 설계 워크플로우(understand6+design2+적대4) → CRITICAL revision 충돌(0034_routine_objects
  → C=0035)·MAJOR MSSQL 오염·namespace·chaining 반영. 구현 리뷰 → **MAJOR-1 sig strip 정합**(컬럼 없는 테이블 미클러스터
  버그)·**MAJOR-2 phantom be: 그룹 clear**·MINOR-3 OOM 가드 반영. 정본 REVIEW REV-20260703T160303.
- 라이브 마이그(0035) 게이트 + 배포(web+insight-worker) + PB-0008 배포 후.

### 후속 정합 (Phase B)
- Phase B(크로스-데이터소스 관계)가 본 시그니처 임베딩을 재사용해 크로스-ds 후보를 유사도로 발굴(신뢰 게이팅).

## 2026-07-03 · 함수·프로시저 노드 + 그래프/능동분석 UX 4건 (graph-funcproc-uxfix, TASK §45, ADR-016·017)

### 배경 (사용자 요청 5건)
관리 콘솔 > 메타데이터 > 그래프 뷰: ① [추가 구조] **함수 & 프로시저 노드** + 분석·관계 구성 ② [상세
패널] 리사이즈 시 **미니맵 위치 미갱신** 수정 ③ [AI 능동 분석] 재귀로 참조 컬럼이 분석돼도 **부모
테이블이 분석되지 않는 이슈**(테이블까진 분석, 앵커 연관성으로 심화 억제) ④ '재분석' 제거(UX 중복)
⑤ hover 프롬프트 입력 툴팁 → LLM 자율 반영.

### 구현 (BE=feature-0002 · UI=feature-0003 cross-cut)
- ① **routine_objects SSOT**(alembic 0034, 비파괴) ← insight-worker 가 rel_maintenance_due(ADR-007
  cadence) 게이트에서 `INFORMATION_SCHEMA.ROUTINES/PARAMETERS`(MySQL·MSSQL 공통 뷰) introspect
  (`modules/routines.py` 신규, 반환형=PARAMETERS pos0 공통 규약, 스키마-slot=ADR-007) + **정의 파싱
  참조 테이블**(FROM/JOIN=read·INSERT/UPDATE/DELETE/MERGE=write, 실재 테이블만·cap). 투영: AGE
  vlabel `Routine`(key=`schema.name()` — 동명 테이블 충돌 방지 네임스페이스) + `HAS_ROUTINE`·
  `ROUTINE_USES{relation_type}` → schema_tables/검색/이웃 노출 → 그래프 ƒ/⚙ 보라 칩(#7b5cd6)·보라
  잔점선 엣지·범례·상세(유형·파라미터·사용 테이블/사용 루틴 상호 이동)·AI 능동 분석(ROUTINE_USES
  content 0.35 + NODE_ANALYSIS_PROMPT Routine 계약). 토글 `AGENT_ROUTINE_INTROSPECT_ENABLED`(기본 ON)
  ·`AGENT_ROUTINE_INTROSPECT_CAP`(300) — config `__all__` 등재(ADR-007 star-import 계약).
- ② 원인 실증: G6 v5 minimap 플러그인이 컨테이너 생성 시 **inline left/top 을 1회 계산 고정**(vendored
  번들 Z$ 확인) — styles.css 의 right/bottom 앵커가 inline 에 짐. `_metaGraphMinimapAnchor()` 가
  inline 좌표를 auto 로 지워 CSS 앵커 전환(멱등, `_metaG6Apply` post-draw) → 이후 패널 드래그/접기/창
  리사이즈를 레이아웃이 자동 추종.
- ③ `_fetch_context` 가 Column 노드의 HAS_COLUMN 부모 Table 을 parent 메타로 기록 → `_score_candidates`
  가 임계 무관 승격(고정 rel 0.5, 교차 제품 감쇠) → `_enqueue_neighbors` 가 **same-depth** enqueue
  ("소속"은 추가 hop 아님 — depth_budget 마지막 층 컬럼의 테이블도 분석). 승격 테이블의 다음 확장은
  기존 앵커 게이팅(ADR-003)이 차단 — 재귀 심화 억제(ADR-017).
- ④ 분석 완료 box '↻ 재분석' 버튼 + ctxmenu 'AI 재분석' 라벨 제거 — '✨ 능동 분석' 단일 진입점.
- ⑤ 버튼 hover 지침 popover(≤400자·Esc·Ctrl+Enter) → analyze POST `prompt`(audit prompt_len/preview)
  → `node_analysis_runs.user_prompt`(0034, 마이그 창 legacy 폴백) → 앵커 토큰 합류(재귀 방향 반영) +
  payload `user_intent`(LLM "자율 반영·출력 계약 불변" 가드). 진행 중 run 재사용 시 새 지침 무시.
- cache-buster `admin.js?v=20260703-graph-funcproc` / `styles.css?v=20260703-graph-funcproc`.

### 검증
- **§18.8 적대 패널 (ULTRACODE workflow, 3렌즈 + MAJOR+ 교차검증 9 agents)**: BLOCKING 1 + MAJOR 5 +
  MINOR 6 + NIT 3 적발 — 교차검증 전건 real 판정 → **전량 수정**(핵심: Column-루트 parent 승격
  depth-0 flood 차단 / neighborhood 라벨 실존 필터(0034 skew 창 붕괴 방지) / sync_graph 3b poisoned
  트랜잭션 복구 / ROUTINE_USES delete-then-merge + SSOT prune / minimap lazy 생성 재시도 / routine-only
  스키마 펼침). 상세 정본: REVIEW.md REV-20260703T113500-graph-funcproc-uxfix.
- 단위: 신규 `test_graph_funcproc_uxfix.py` **19 PASS**(정의 파싱 read/write·주석 제거·alias-UPDATE
  승격·제외 규칙·store_schema 라벨·sync_routine Cypher 형태+stale 회수·라벨 화이트리스트·parent 승격
  same-depth+depth-0 차단·교차 제품 감쇠·budget 경계·user_prompt 저장/폴백/앵커 토큰·routine_use
  관련도) + 회귀 **107 PASS**(relevance 28[3-tuple 갱신]·role 10·config_star·relationships 57·
  metadata_graph_units 10 등) = 합계 **126 PASS**. `node --check`·`py_compile`·migrate-lint PASS.
- 라이브 검증(AGE·introspect·PB-0008)은 배포 후 수행 — 아래 잔여.

### 잔여
- 배포(deploy_scope: included): main 병합 → `make migrate`(alembic **0034** 도달 검증 — stale agent
  이미지 주의) → web·insight-worker 재빌드 → routine introspect 첫 cadence 후 그래프 확인.
- PB-0008 실 Windows 시각검증(ƒ/⚙ 칩·미니맵 리사이즈 추종·hover popover·재분석 부재).
## 2026-07-03 · 그래프 클러스터 자유 배치 상호작용 복원 (graph-freeplace, TASK §44, ADR-015)

### 배경 (사용자 회귀 보고)
데이터소스 스키마 클러스터 화면에서 "분류 접기/펼치기·분류 drag&drop 위치 이동·분류 내부 노드 이동 반응형 크기 조정"이
사라짐. **조사(git bisect)**: 마지막 정상(abc78b00 graph-simgroups, T42.8 PASS) 이후 admin.js 변경 2건(ds-avg-latency=
데이터소스 상세 패널만·graph-product-cat=제품모드만)은 클러스터 상호작용 코드 미변경 → **내 Phase A/최근 변경 회귀 아님**.
근본원인 = ADR-004 Cytoscape→G6 결정론 배치가 자유배치 persistence 를 미이관한 feature gap. 사용자 "G6 재구현" 결정.

### 구현 (frontend-only, admin.js)
- **결정론 배치 위에 사용자 드래그 offset 레이어**(ADR-015): `clusterOffset`(combo/카드 드래그 → 클러스터 전체 이동,
  build L.x0/L.y0 가산) + `nodePos`(개별 테이블/용어 → place-loop 델타 시프트, combo auto-fit 리사이즈). 접기/펼치기 유지,
  스코프전환·초기화 리셋, 펼침/접기 rebuild 유지. combo:dragstart/dragend + node:dragend 훅.
- cache-buster `20260703-graph-freeplace`.

### 검증
- `node --check` PASS · §18.8 적대 리뷰(REV-20260703T101622): 6축 → **MAJOR 1**(nodePos 절대좌표가 clusterOffset override →
  클러스터 이동 시 소속 nodePos 동반 가산으로 fix)·NIT 1(컬럼 dead 엔트리 제외) 반영 → PASS-WITH-FIXES.
- POST-DEPLOY 실 Windows PB-0008 4-상호작용 수동 검증 예정(라이브 canvas 드래그 자동화 곤란).

## 2026-07-03 · 제품(Products) 단위 카테고리 구분 (graph-product-cat, TASK §43, ADR-014)

### 배경 (사용자 요청 — 3대 개선 中 A)
관리 콘솔 > 메타데이터 > 그래프 뷰: "구분해둔 제품(Products)에 따른 카테고리 단위로 구분이 가능하도록 구성". 실측상
그래프 모델은 `Product`/`Datasource` 라벨·`USES` 엣지를 예약만 하고 실제 투영 안 함(scope=datasource 단위뿐). Product↔
Datasource SSOT 는 MySQL(`WebProducts`·`WebProductDatasources`)에 완비, 그래프는 Postgres `agent_kb` 로 분리.

### 구현 (투영 API 질의시점 합성 + 프론트 개요, 마이그레이션 0)
- **백엔드**([admin_metadata.py](../../feature-0003-agent-web-ui/src/routers/admin_metadata.py)): `admin_metadata_graph`
  에 `conn=Depends(app.get_conn)` + `?mode=products`/`?product=<id>` 분기(PG 이전 early-return). `_product_overview_graph`
  가 MySQL SSOT 로 Product/Datasource 노드 + USES 엣지 합성(datasource dedup). `_products_for_scope` 가 datasource
  진입 응답에 소속 제품(`products`) 첨부. **read-axis 정렬**: scope=`scope_key or 라벨`(DB=해시·.env=라벨).
- **프론트**([admin.js](../../feature-0003-agent-web-ui/src/static/admin.js)): `_metaG6BuildProducts` 전용 2-열 배치
  (combo 미사용, 기존 masonry 무간섭) + `_metaGraphLoadProducts` + 랜딩/노드클릭 라우팅 + datasource 뷰 제품 배너.
  툴바 "🗂 제품 카테고리" 버튼(admin.html) + cache-buster `20260703-graph-product-cat`.

### 검증
- `node --check` PASS · Python ast PASS · 격리 pytest **28 PASS**(DI 권한 맵·metadata_graph 단위 무회귀).
- §18.8 적대 리뷰(general-purpose): **read-axis MAJOR** (.env datasource drill 빈 그래프) + 비숫자 product NIT 반영
  → PASS-WITH-FIXES. 정본 REVIEW REV-20260703T091737.
- POST-DEPLOY 실 Windows 브라우저(PB-0008) 배포 후 기록 예정.

### 후속 정합 (동일 요청의 Phase C·B)
- Phase C(ADR-013 의미 임베딩)·Phase B(크로스-데이터소스 관계)가 본 제품 경계(제품=관련 데이터소스 묶음)를 재사용.

## 2026-07-03 · 중간버튼 카메라 팬 + 테이블 노드 종속 UI 동반 드래그 (graph-drag, TASK §41)

### 배경 (사용자 요청)
관리 콘솔 > 메타데이터 > 그래프 뷰: ① 마우스 **중간(휠) 버튼 드래그를 객체 상호작용이 아닌 카메라 팬**으로, ② **테이블 노드를 옮길 때 하위 종속 UI(접기 "X:" 컨트롤 + 컬럼 노드)도 동반 이동**.

### 구현 (FE 상호작용 전용, admin.js)
- (①) G6 `behaviors` 문자열→object-form + `enable` 오버라이드: `_metaCanvasDragEnable`(중간버튼이면 노드 위에서도 팬)·`_metaElementDragEnable`(중간버튼이면 노드 이동 거부→팬 양보). `_metaEventButtons`/`_metaIsMiddleDrag` 로 buttons 비트마스크(4=중간) 판정. 컨테이너 `mousedown`(button===1) `preventDefault` 로 브라우저 autoscroll 억제(pointer 흐름 유지).
- (②) `_metaGraph.tableDeps`(Table key→종속 id[], `_metaG6Build` 리셋·재채움) + `node:dragstart/drag/dragend`. dragstart 에서 각 종속의 테이블 대비 오프셋(월드) 고정 기록 → drag/dragend `translateElementTo(테이블 현재위치+오프셋)` 절대이동 + dragend 재정합(핸들러 순서 무관, 1-frame lag 제거).
- cache-buster `admin.js?v=20260703-graph-drag`.

### 검증
- `node --check` PASS. §18.8 적대 리뷰 [SUBAGENT: PASS] (G6 v5.1.1 번들 역어셈블 실측 — 4축 BLOCKING 0, NIT 6건 중 N1 주석 정정·나머지 수용) — REVIEW REV-20260703T021144-graph-drag.
- **PB-0008 실 Windows 브라우저(Chrome/149) 라이브 PASS** (머지 전 pre-verify): Test A(중간버튼 팬 — 노드 월드 [0,0] + 화면 팬), Test B(좌클릭 테이블 — 종속 5개 동일 델타 [191.35,-131.55]).

### 잔여
- 배포(web 재빌드, deploy_scope: included) + 라이브 PB-0008 POST-DEPLOY 재확인.
- (병합 메모) origin/main(9e1156d6) 3-way 병합으로 §40=graphux6·§39=cluster-role-prefix·역할 기능 보존, graph-drag 는 §41 로 리넘버·admin.js 자동병합(role grep=2, drag 함수 8 보존).

## 2026-07-03 · AI 능동분석 패널 하단 이동 + 그래프 반응형 높이 + 운영현황 분석 대상 관측 (graphux6-panelbottom-responsive-obs, TASK §40)

사용자 요청 3건. worktree `feature-0016-graphux6-panel-obs`, 등급 Major(③ 마이그레이션 포함). §37~39 와 병렬 진행 → main 병합 시 §37 role-legend-bottom 과 aside 구조 통합.

**① AI 능동 분석 패널 → 상세 패널 하단** ([admin.html](../../feature-0003-agent-web-ui/src/static/admin.html), [styles.css](../../feature-0003-agent-web-ui/src/static/styles.css)): 진행 패널(`#metadataGraphProgress`)이 노드 상세 위에 있어 분석 시작 시 상세를 밀어내던 이슈 → aside 최하단으로 이동. main 의 §37(역할 범례를 하단 `margin-top:auto` 고정)과 병합해 최종 aside 순서 = **detailBody → 역할범례(하단고정) → 진행패널(최하단)**, 둘 다 바닥이라 노드 상세를 밀지 않음. JS 무변경(getElementById).

**② 그래프 반응형 높이** ([styles.css](../../feature-0003-agent-web-ui/src/static/styles.css)): 캔버스·상세 `height: clamp(420px,64vh,760px)` 의 420px 하한이 metadata pane(admin-shell `overflow:hidden`+`100vh`) 가용높이를 초과해 세로 좁은 뷰포트에서 잘리던 이슈 → **flex-fill**(`flex:1 1 auto` + body `grid-template-rows: minmax(0,1fr)`)로 pane 남은 세로를 채워 축소·미절단. 고정 height 제거, 캔버스 `min-height:200`(§18.8 M1 빈 캔버스 방어) — 그래프 블록 자체엔 하한 없음(흔한 노트북 불필요 스크롤 회피, §18.8 round-2). 전너비 `:has()` graph-mode pane 스크롤(캔버스 floor 가 가용높이 초과하는 ≈<560px viewport 에서만 발동, 이중 :not 정밀 가드). G6 `autoResize` 로 JS 무변경. 상세는 #565 flex-column 보존.

**③ 최근 활동 분석 대상 관측** (migration [0032](../../feature-0002-agent-core/alembic/versions/20260703_0032_llm_usage_target.py) / [llm.py](../../feature-0002-agent-core/src/modules/llm.py) / [ai_ops.py](../../feature-0003-agent-web-ui/src/routers/ai_ops.py) / [admin.js](../../feature-0003-agent-web-ui/src/static/admin.js)): '테이블 분석'·'노드 분석'이 라벨만 뜨고 대상이 안 보이던 이유 = `llm_usage.task` 가 저카디널리티 카테고리 키(KPI `GROUP BY task` 의존)라 대상 미포함. → `target VARCHAR(200)` additive nullable 컬럼(task 집계와 분리, 0030 패턴) + `_record_llm_usage(target=)`(schema=스키마·table=schema.table·node=fqn/name, account 은 PII 제외) + **자가치유**(INSERT 실패→rollback→base 재INSERT / SELECT 폴백, stale image 대비) + admin.js 최근활동 행·상세 대상 표시.

**검증**: 컨테이너 `make test` **전건 PASS**(ruff clean). test_ai_ops 17/17(target 통과 + 컬럼부재 폴백 + INSERT 폴백), test_llm_usage_record 7/7(param 순서 보존), test_call_llm 2/2(mock target). **§18.8 적대 2라운드 PASS-WITH-FIXES**(BLOCKING 0 — 빈캔버스·노트북스크롤·가드취약·테스트NIT 전부 수정). verify-completion PASS. alembic 단일 head=0032. 배포(0032 마이그 + web) + PB-0008 실 Windows 3건 + `alembic_version`=0032 검증은 POST-DEPLOY(T40.11).

## 2026-07-03 · 클러스터 상세 테이블 목록 역할 접두사 + 행 클릭 노드 선택 + 범례 hover 툴팁 (cluster-role-prefix, TASK §39)

### 배경 (사용자 후속 요청 3건)
① 스키마 클러스터 상세의 테이블 목록에서 AI 능동 분석 완료 테이블은 역할 칩을 **접두사**로(미분석은 문자열·배치 뒤틀리지 않게 기본 왼쪽 여백). ② 그 목록 **각 테이블 클릭 → 해당 노드 선택**. ③ 역할 **범례 hover 시 상세 툴팁**.

### 구현 (FE — admin.js/admin.html/styles.css)
- `_META_ROLE` 에 `desc` 필드(범례·접두사 툴팁 단일 소스, BE NODE_ROLES 정합). 신규 `_metaRoleChipHTML`.
- `_metaGraphRenderClusterDetail`: 각 행 `<button data-node-key>`, 분석 완료=역할 칩 접두사·미분석=`amgr-role-none`(18px 빈 슬롯 → 라벨 정렬 유지). 클릭 → `_metaGraphShowDetail`(select 하이라이트+상세) + focusElement.
- 신규 `_metaRoleLegendTips()`: 정적 범례 `<li data-role>` 에 `desc` 로 hover title 주입(그래프 진입 시). admin.html `<li>` data-role 추가.
- cache-buster `?v=20260703-cluster-role-prefix`(admin.js·styles.css).

### 검증
- `node --check` PASS. headless playwright 렌더 격리 실증: 분석/미분석 5행 → 전 라벨 left=45px 정렬(`allCodesAligned`), 칩 18px 균일, 전 행 button. 스크린샷 확인.
- §18.8 적대 리뷰 [SUBAGENT] — REVIEW REV-20260703-cluster-role-prefix.
- 부수: graph-rel-layout §38 병합이 MODIFY.md 에 남긴 미해결 conflict 마커 정리(양쪽 CHG 보존).

### 잔여
- 배포(web, deploy_scope: included) + 라이브 PB-0008 실 Windows 육안(접두사·정렬·행 클릭 선택·범례 툴팁).

## 2026-07-03 · 역할 범례를 상세 패널 하단으로 이동 + 확장 시 밀림/뒤틀림 해소 (role-legend-bottom, TASK §37)

### 배경 (사용자 후속 피드백)
role-legend-panel(§36) 배포 후: ① 범례를 상세 패널 **하단**에 배치, ② 범례 **확장 시 기존 UI(노드 상세)를 밀어 내용이 뒤틀림**. 원인 = 범례가 aside 첫 자식(open)이라 고정높이 패널에서 확장이 아래 노드 상세를 밀어냄.

### 구현 (FE 표현 전용)
- admin.html: 범례 `<details>` 를 aside **첫 자식 → 마지막 자식**(detailBody 뒤)으로 이동.
- styles.css: aside `display:flex; flex-direction:column` + `.admin-meta-graph-detail > * {flex-shrink:0}`(자식 압축 금지→컨테이너 스크롤) + 범례 `margin-top:auto`(바닥 고정).
- cache-buster `styles.css?v=20260703-role-legend-bottom`.

### 검증
- headless playwright 렌더 격리 실증: 빈 상세=범례 바닥 고정(위 여백 262px), 긴 상세 30행=노드 상세 온전(firstNodeH 32·미압축)·잘림 없음(dbH==dbScrollH)·패널 스크롤 → 밀림/뒤틀림 없음. 스크린샷 확인.
- §18.8 적대 리뷰 [SUBAGENT] — REVIEW REV-20260703-role-legend-bottom.

### 잔여
- 배포(web, deploy_scope: included) + 라이브 PB-0008 실 Windows 육안(하단 배치 + 확장 시 위 상세 안 밀림).

## 2026-07-03 · 역할 범례를 우측 상세 패널 상단 세로·접힘으로 이전 (role-legend-panel, TASK §36)

### 배경 (사용자 후속 요청)
"그래프 뷰 노드 시각화 개선" — "테이블 역할(AI 분석 완료 시 칩 색)" 범례를 **다른 위치에 세로로 구성 + 접힐 수 있도록**. node-role-viz(§33, PR #555 병합·배포 완료)로 도입된 칩 시각화 위에 얹는 UI 개선. 기존 범례는 툴바 아래 **가로 전폭 2번째 행**으로 그래프 본문을 아래로 밀었음.

### 배치 결정
AskUserQuestion 으로 3안(캔버스 좌하단 오버레이 / 우측 상세 패널 상단 / 툴바 접힘 드롭다운) 제시 → 사용자 **"우측 상세 패널 상단"** 선택(그래프를 안 덮음, 노드 상세와 세로 공존).

### 구현 (FE 표현 전용)
- admin.html: 전폭 `.admin-meta-graph-legend-roles` 행 제거 → `aside#metadataGraphDetail` 최상단에 `<details class="admin-meta-graph-rolelegend" open>`(summary 토글 + 칩 8종 `<ul><li>` 세로 스택) 삽입. 네이티브 접힘(무JS).
- styles.css: 가로 legend-roles 규칙 → 세로·접힘 `.admin-meta-graph-rolelegend` 카드 규칙(커스텀 카펫, marker 제거, 세로 flex, 밝은 dot border).
- cache-buster `styles.css?v=20260703-reldetail-colexpand-role-legend-panel`.

### 검증
- 구조 정합: legend-roles 잔여 참조 0. aside 는 폭 조회로만 참조(innerHTML 교체 없음) → 노드 선택·능동분석 렌더에 범례 wipe 없음.
- §18.8 적대 리뷰 [SUBAGENT] — REVIEW REV-20260703-role-legend-panel.

### 잔여
- 배포(web 재빌드, deploy_scope: included) + 라이브 PB-0008 실 Windows 육안 검증(세로 표시 + 접힘 동작).
- 부작용(수용): "상세 ⇆"로 상세 패널 접으면 범례도 같이 숨음(사용자 선택 위치의 자연 귀결).

## 2026-07-03 · 더블클릭 카메라 팬 반응 지연(~350ms 텀) 제거 — 즉시 시작 + 적응형 follow (graph-dblclick-latency, ADR-011)

### 배경
graph-dblclick-cam2(manual tween) 배포 후 사용자 관찰: 팬은 부드러우나 더블클릭 직후가 아닌 **~350ms 텀 뒤 시작**돼 답답. "렌더러 한계인지" 질의.

### 진단
렌더러 한계 아님. 팬(`_metaGraphAnimateFocus`)이 `_metaGraphExpand` 파이프라인 **맨 끝**에서 시작 — busy → `/graph?depth=2` fetch(~135ms) → ingest → `_metaG6Apply` setData+draw(~200ms) → **그제서야** 팬. 앵커(클릭 노드)는 이미 렌더돼 있는데 fetch·rebuild 를 기다림 → ~350ms 텀.

### 수정 (FE admin.js)
- **fetch 전 즉시 시작**: `_metaGraphExpand` 가 팬을 busy 직후 fetch 를 await 하기 전에 fire-and-forget(await 없이) 호출 → 클릭 즉시 반응. 파이프라인 끝 await 팬 호출 제거.
- **적응형 follow tween**: 고정-duration(delta 1회 캡처) → 매 프레임 앵커 **현재** 뷰포트 위치 재조회 → 잔여 delta K=0.24 translateBy(ease-out). fetch·rebuild 로 앵커가 이동/재생성돼도 최종 위치로 수렴. 종료=수렴(<1.2px)/seq/MAXMS(1200ms) 단일 시간상한. W/H 매 프레임 재조회(리사이즈 대응), API 부재 시 focusElement 폴백.

### 검증
- 헤드리스 실증: fire-and-forget 즉시 시작 + 중간 setData 로 앵커 이동(offset -500) → **24프레임에 최종 중앙 [399,250]≈[400,250] 수렴**. `node --check` PASS. cache-buster `?v=20260703-graph-dblclick-latency`.
- §18.8 적대 7축 BLOCKING 0. **MEDIUM(missStreak 조기포기 — 저사양 rAF 탈동조로 팬 조기중단)** 적발 → 제거(MAXMS 단일상한). NIT(API 폴백·W/H 스테일) 반영. REV-20260703T003000.

### 잔여
- 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 더블클릭 시 카메라가 **텀 없이 즉시** 앵커로 부드럽게 팬하는지 육안 확인.

---

## 2026-07-03 · AI 능동 분석 완료 테이블 역할 시각 표식 (node-role-viz, ADR-010, TASK §33)

### 배경 (사용자 요청 2026-07-02)
그래프 뷰 노드가 "단순 사각형+글자" 라 예측 어렵게 나열되어 가시성 저하 — **AI 능동 분석 완료 노드에
그 테이블이 수행하는 역할을 명시하는 시각 표식**을 웹 리서치 기반으로 검토 후 자율 구성 (entry persona dispatch).

### 리서치 → 설계
- 범주 인코딩 표준 = **색(≤8종 식별 한계)+아이콘 중복 인코딩+범례**(yFiles 지식그래프 가이드·Tom Sawyer·
  CatPAW), 팔레트 = **Okabe-Ito 8색**(색약 안전 표준), 분류체계 = 고전 DB 테이블 분류(master/reference/
  transaction/history)의 게임 운영 DB 조정.
- 8종 고정 NODE_ROLES: master 기준·정의📘 #0072B2 / account 계정·유저👤 #56B4E9 / transaction 거래·행위💳
  #009E73 / log 로그·이력📜 #E69F00 / mapping 매핑·연결🔗 #CC79A7 / config 설정⚙️ #D55E00 / stats 집계·통계📊
  #F0E442 / etc 기타◽ #6e7681. 밝은 색 3종은 라벨 어두운 글자.

### 구현 (BE=feature-0002 · UI=feature-0003 cross-cut)
- 데이터: LLM 분석 계약 `role` enum 추가 → worker `_resolve_role`(LLM 유효값 우선 → 휴리스틱 이름 1-pass·
  본문 2-pass 폴백, **Table 한정**) → `node_analysis_jobs.role`(alembic 0031 비파괴 ADD). 기존 done 행은
  insight-worker 틱 `backfill_roles()` 휴리스틱 백필(LLM 재호출 없음·멱등·자기종결).
- 조회: get_scope_analysis_status(roles 집계)·get_run_status(roles+jobs.role)·get_node_analysis(role) +
  bulk status API `roles` 노출.
- FE: 분석완료 테이블 칩 fill=역할색 + 라벨 앞 아이콘 + 역할 범례 행 + 상세/진행 패널 역할 칩(미분석 teal·
  보라 테두리 유지). 역할은 bake 스타일이라 캐시 서명 `#R=` suffix 로 refreshStates 가 **rebuild 승격**
  (ADR-006 rAF coalesce·~80–200ms). cache-buster `20260703-node-role-viz`.

### 검증
- 단위 13건(test_node_analysis_role.py — 분류 계약·휴리스틱 우선순위·LLM 우선/폴백·Table 한정) + 기존
  relevance 25건 회귀 0. 전체 pytest(0002+0003) exit 0.
- headless harness(실 admin.js + mock API): 미분석 teal / 폴 경로 role bake / sync 경로 / 무효 role 방어
  ALL PASS·pageerror 0 + 시각 스크린샷(8종 칩+범례).

### 잔여
- §18.8 적대 패널 → 배포(alembic 0031 + web·insight-worker 재빌드) → **라이브 PB-0008 실 Windows**(역할 칩
  색/아이콘/범례/상세 패널) → TEST.md POST-DEPLOY Run append.

---

---

## 2026-07-03 · 접힌 상태 관계 표시 + 관계 클릭 추적 + AI 능동 분석 연동 (graph-reltrace)

### 배경 (사용자 후속 3건 — 육안 확인 후)
사용자가 대화-중 학습된 관계(`account`↔`arenabegin`)가 그래프에 표시됨을 육안 확인. 다만 3건 요청:
① 테이블을 **더블클릭(컬럼 펼침)하기 전까지 관계가 안 보임** — 접힌 상태에서도 표시. ② 상세 패널에서
각 관계 클릭 시 **대상 테이블·컬럼을 추적**. ③ **AI 능동 분석으로도 작동**.

### 진단
- ①의 근본원인: REFERENCES 는 Column→Column 이라 `_metaG6Build` 엣지 조립이 **양끝 컬럼이 렌더된
  경우에만** 그렸고, 스키마 펼침 응답(`schema_tables`)은 HAS_TABLE 만 반환 → 접힌 테이블엔 관계
  데이터 자체가 모델에 부재.

### 구현 (백엔드 1 + 프론트 3)
- **백엔드** `schema_tables`: 스키마 펼침에 스키마 내 컬럼의 나가는 REFERENCES 엣지 추가(FK null-status
  포함·broken 제외·cap). 라이브 AGE 실행으로 `account.AccountId→arenabegin.AccountId` 반환 확인.
- **프론트 ①** `_metaG6Build`: REFERENCES 끝점을 렌더 id 로 해소 — 컬럼 미렌더 시 소속 테이블로 승격
  (키에서 부모 도출) + 같은 두 끝점 다수 컬럼-쌍 dedupe(최강 상태·count). 접힌 테이블 간 관계 렌더.
- **프론트 ②** 신규 `_metaGraphTraceRelation`: 관계 클릭 → 대상 테이블 이웃 로드·스키마 펼침·컬럼 전개
  + 대상 컬럼 강조·카메라 focus. 상세 패널 "관계(N)" 행 + "관계 상세" 행 공통 추적.
- **프론트 ③** `_metaGraphLoadNodeAnalysis`: AI 능동 분석 결과에 구조화된 관계를 추적 가능 행으로 노출.

### 검증
- 프론트 엣지 집계 격리 Node 11/11 PASS + 추적 행 산출 검증 + node --check + py_compile + 라이브 Cypher.
- 완료 하드 게이트 = 배포 후 PB-0008 실 Windows(3항목 육안).

### 잔여 (게이트)
- §18.8 적대 패널 → verify-completion → PR/merge → 배포(web+worker) → PB-0008.

## 2026-07-02 · 더블클릭 카메라 애니 no-op 근본수정 — manual rAF tween (graph-dblclick-cam2, ADR-009)

### 배경
graph-dblclick-cam(ADR-008) 배포 후 사용자 재보고: 더블클릭 시 **애니 없이 카메라 순간이동**(수정이 안 먹힘).

### 근본원인(실증)
그래프는 `new G6.Graph({animation:false})`(graph-g6 가 setData 레이아웃 셔플 방지 위해 의도)로 생성 — G6 v5 에서 이 **전역 `animation:false` 가 `focusElement`/`zoomTo` 의 per-call `animation` 인자까지 무효화**한다. 헤드리스 실증: 동일 그래프 `animation:false`→`focusElement({duration:400})`=**2ms(즉시)** / `animation:true`→**412ms(애니)**. 즉 ADR-008 의 `focusElement({duration:420})` 는 no-op 였다.

### 수정 (FE admin.js)
전역 animation ON=셔플 재발, setOptions 토글=tween 창 동시 rebuild 셔플 위험 → **G6 애니 우회 manual rAF tween**. 신규 `_metaGraphAnimateFocus(key, seq)`: 앵커 `getElementRenderBounds` 중심(canvas) → `getViewportByCanvas` → 뷰포트 중앙(`getSize()`/2) delta(client px) 를 requestAnimationFrame 이징 누적 `translateBy`(420ms). setData 미사용·전역상태 무변경. seq 로 연타 중단, 미렌더/API 실패는 즉시 focus 폴백. `_metaGraphExpand` 가 no-op focusElement 대신 이 헬퍼 호출.

### 검증
- manual tween 헤드리스 실증: 앵커가 뷰포트 정중앙에 26프레임/434ms 안착. `node --check` PASS. cache-buster `?v=20260702-graph-dblclick-cam2`.
- §18.8 적대 6축(무한루프·중앙정확·seq/동시성·폴백·줌순서·회귀) BLOCKING 0 — **G6 번들 소스 대조로 tween 수학=G6 자체 focus 공식 동일**(앵커 정중앙 오차 ≤1e-13px). NIT 2건(420ms 중 2차 더블클릭+fetch실패 카메라 중간잔류 자가치유 / 동시 휠줌 정렬 어긋남) 수용. REV-20260702T230000.

### 잔여
- 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 더블클릭 시 카메라가 앵커로 **실제 부드럽게 팬**(순간이동 없음) 육안 확인.

---

## 2026-07-02 · 그래프 더블클릭 카메라 순간이동 재배치 해소 — 앵커-중심 애니 팬 (graph-dblclick-cam, ADR-008)

### 배경
프리즈 해소(graph-expand-perf) 후 사용자 관찰: 테이블 노드 **더블클릭 시 카메라가 순간이동 재배치되어 불편**. "카메라 [고정/애니메이션] 자율 판단하여 개선" 위임.

### 조사·자율판단
- 더블클릭 = `_metaGraphExpand`(additive 이웃 확장). graph-initview(A3)로 이미 "전체-fit 대신 앵커-중심 국소 focus" 였으나 `focusElement`/`zoomTo` 를 **animation=false(즉시)** 로 호출 → 앵커로 카메라 순간 텔레포트.
- 자율판단 = **애니메이션(앵커-중심 팬)**. 고정(무이동)은 additive 확장에서 새 이웃/앵커가 화면 밖이라 부적합 → 앵커-중심 focus 로 클릭 대상 프로미넌트 유지 + 부드러운 전환(고정·애니 두 요구의 절충). ADR-008.
- G6 카메라 애니 API 헤드리스 검증: graph `animation:false` 여도 `focusElement(id,{duration,easing})`/`zoomTo(z,{duration})` per-call 스펙 동작·throw 없음·카메라 실이동.

### 수정 (FE admin.js)
- `_metaGraphExpand` 카메라 블록: `focusElement(fel, false)` → `focusElement(fel, {duration:420, easing:'ease-in-out'})`. 판독 하한 clamp(zoomTo)는 즉시 유지(팬 애니 중첩 회피), seq 가드로 연타 stale 애니 방지.

### 검증
- `node --check` PASS · cache-buster `?v=20260702-graph-dblclick-cam`.
- §18.8 적대 리뷰: **최초 오편집 적발** — 더블클릭이 아닌 우클릭 "중심 보기"(`_metaGraphFocus`) 함수를 편집(라우팅 오인) + 그 함수 `schemaExpanded.add` 누락→앵커 카드렌더→focusElement throw→fit-to-all 폴백(BLOCKING). **교정**: 진짜 더블클릭 `_metaGraphExpand`(앵커 노드 렌더 보장)로 이동 + focus 함수 원복 + 헬퍼 제거. 카메라 op=viewport transform(프리즈 무관). REV-20260702T190000.

### 잔여
- 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 더블클릭 시 카메라가 앵커로 부드럽게 팬(순간이동 없음) 육안 확인.

---

## 2026-07-02 · 신뢰/추정 관계 자기교정 파이프라인 미가동 근본수정 (rel-selfheal)

### 배경 (사용자 검증 요청)
"그래프 뷰의 신뢰/추정 관계가 정상 구성되는지 — Achievement 구조 분석 후 실제 관계 구축·UI 표시·이후
대화 추론 활용을 검증, 아니면 개선 완수" (entry persona dispatch).

### 검증 실측 (라이브)
- `table_relationships` 전체 **2행**(conversation candidate w=0.49, Achievement.UniqueID→AchievementQuest/
  AchievementReward.AchievementID, 07-02 11:02 대화 학습) — **inferred 0·trusted 0·프로브 0회**.
- 그 2행은 스키마-slot='' → AGE 투영이 고아 Column 노드(`<ds>:Achievement.UniqueID`, HAS_COLUMN 부모 0)
  생성 — 실 Table 노드(`<ds>:dk_data_release.Achievement`, 컬럼 4개 보유)와 분리 → **그래프 뷰에서
  Achievement 를 봐도 추정 점선 비가시** + graph_navigate 이웃 미노출.
- UI(G6, 8c45f070 배포): trusted=실선/candidate=점선/broken=숨김 + 상세 배지 — **구현 정상**(데이터 갭).
- digest 주입: 라이브 시뮬레이션 PASS — `[추정 w=0.49]` 태그 2건 주입(leaf-명 매칭이라 스키마 무관).
- 사용자의 Achievement 능동 분석 run(7248b020, 07-01 15:29)은 anchor 게이팅 배포(18:52) **이전** —
  rel 전부 0.000 + Schema 경유 형제 123 테이블 fan-out 기록(현행 코드는 게이팅 활성, 기대 동작).

### 근본원인 (4중)
1. **D1b (치명, 3일 조용한 정지)**: `AGENT_RELATIONSHIP_*` 7종이 `shared/config.py` `__all__` 미등재 →
   `from shared.config import *` 소비자 insight.py 에서 **NameError** → per-schema `except: continue` 가
   삼켜 **스키마 처리 전체(테이블/스키마 인사이트 갱신 + FK introspect + 암묵 추론 + 프로브) 06-29 부터
   정지**. 실증: 라이브 컨테이너 `eval(...insight.__dict__)` NameError + `fact_entries` table_insight
   max(updated_at)=06-29 13:58 / schema_insight=06-29 07:50 (account_insight 는 별도 경로라 07-02 정상).
   `AGENT_SQL_FIX_MODEL`(llm.llm_fix_sql)도 동일 클래스 — SQL 자가수정 조용히 무력화.
2. **D1a (설계 갭)**: 훅 발화조건 = 구조변경/artifact 부재 뿐 → 이미 스캔 완료된 91개 스키마에서 영원히
   미발화. (implicit-edges REPORT "주기 re-probe 후속" 의 본체.)
3. **D2**: `_pk_like` 후보에 `uniqueid` 부재 → 이 게임 DB 관용 PK(`UniqueID`) 미인식 —
   `AchievementID → Achievement.UniqueID` 같은 name_fk 추론 전면 불가.
4. **D3**: 대화 JOIN 학습이 SQL qualifier 를 버리고(파서 leaf 화) default 도 없어 스키마-slot='' 저장 →
   그래프 Table 키(`db.table`) 규약과 불일치(고아 엣지). MSSQL introspect/추론도 실 스키마('dbo') 저장
   시 동일 운명이었음(스키마-slot 규약 미통일).

### 수정 (CHG-20260702T024556, ADR-007)
- config `__all__` 등재(D1b) + `AGENT_RELATIONSHIP_REINFER_SEC`(6h) 주기 cadence(D1a — kv
  `relationship_infer_at` + `_is_refresh_due` OR-게이트, 첫 사이클 = 전 스키마 자연 백필).
- 스키마-slot 규약 통일: MSSQL 저장 라벨 = 순회 DB명(store/query 분리) + 프로브 db_scope 필터·
  연결 DB qualifier 제거(D3 계열 + 교차-DB 오검증 차단).
- 파서 qualifier 캡처 + `default_schema=활성 DB` 학습(D3) + `uniqueid` PK 후보(D2) + 프로브 neutral
  `last_validated_at` 전진(rotation 공정).
- 그래프 투영 앵커링: `sync_relationship` 이 REFERENCES 끝점 Column 을 소속 Table/Schema 체인에
  MERGE(비파괴 — description/source SET 생략) — 미큐레이션 컬럼(target 측 다수)도 점선이 실 테이블에 붙음.
- **회귀 가드 신설** `test_config_star_export.py` — star-import bare 이름의 런타임 해석을 AST 로 전수
  검사(이 결함 클래스 봉인; domain/kb_scope 의 주입-공급 4건은 정당 케이스로 실측 반영).

### 검증
- 단위 43건 PASS(test_relationships — Achievement 실측 스키마의 name_fk 추론 케이스 포함) + 신규 가드
  3건(합산 46) + insight 인접 PASS + py_compile. 웹 자산 무변경(check #13 비대상).

### §18.8 적대 리뷰 패널 + 반영 (REV-20260702T052630, resume 세션)
- 3렌즈(backend/security/qa) 병렬 적대 리뷰 — 원 세션이 dispatch 직후 session limit 중단되어 재실행.
- **backend FAIL(MAJOR 6)** → 필수 전량 수정: ① instance-scan 커서 DB별 분리(B-F1 — MSSQL multi-DB
  첫-DB 독점으로 cadence 목표가 DB#2+ 미달성이던 구조 결함), ② 강화/파단 write-back 스키마-slot 한정
  (B-F2 — 교차-DB 동명 오염), ③ uniqueid shared_key 제외(B-F3 — PK≡PK 쓰레기, 실행 재현),
  ④ 프로브 실행오류 처리(B-F4 — 객체-부재=negative + 전 실패 timestamp 전진; 영구 미파단·큐 기아 차단).
- security/qa PASS-WITH-FIXES → cap/sample/timeout 클램프(Sec-F2), MSSQL slot lower 정규화(QA-F4),
  라이브 테스트 수집 가드(QA-F1), except 경고 로깅(B-F7), 커버리지 +10(QA-F2) — **총 56건 PASS**.
- injection 3경로(파서 격리·dialect 이스케이프·Cypher _cq)는 보안 렌즈가 라이브 적대 실행으로 안전 확증.
- 수용 한계(ADR-007 Consequences ①~④): dbo-only slot 규약 · introspect 케이스 플래핑(SSOT 후속) ·
  실효 cadence ≈30h(window 회전 곱) · LEARNING↔PROBE 결합 권장.

### 잔여 (배포 게이트)
- verify-completion → commit/PR/merge → insight/ask-worker 재빌드 + web 롤링 배포(deploy_scope: included).
- 배포 후 데이터 정정: 기존 2행 스키마 정규화(→dk_data_release) + AGE 고아 Column 3노드 회수 + 재sync.
- 라이브 확인: insight 사이클 후 relationships_inferred>0 · 프로브 신호 · 그래프 점선(Achievement) ·
  digest 태그 — 본 cycle 종료 보고에 기록.

## 2026-07-02 · 그래프 노드 더블클릭 프리즈 잔존 해소 — refreshStates per-node setElementState (graph-expand-perf, ADR-006)

### 배경
graph-perf-bg 배포 후 사용자 후속 보고: `mssql-qa-idc.dk_data_release.Achievement`(analyzed, 형제 246테이블 스키마) **더블클릭 시 2~3초 프리즈 잔존**.

### 진단 (실측으로 후보 배제 → 병목 특정)
- 헤드리스 harness(200노드+127엣지 G6): `setData`+`draw` = **~200ms** → 렌더는 병목 아님.
- web 컨테이너 서버측 계측: AGE 이웃 `neighborhood(depth=2)` = **135ms**(128노드/127엣지) → fetch 도 병목 아님. Achievement 는 HAS_COLUMN 4개(analyzed) → `/graph/columns` introspection **SKIP**.
- **진짜 병목**: `_metaGraphRefreshStates` 가 **전 노드마다 `g.setElementState` 를 개별 호출** — G6 v5 에서 건당 ~50ms(startBatch 로도 안 배칭). **실측 200노드 재적용 = 10,046ms.** 더블클릭 → `_metaG6Apply` 가 `_stateCache` clear → 직후 `_metaGraphSyncAnalysisMarkers`(+2.5s 폴)가 cold 로 전 노드 재-setElementState = 프리즈. (graph-perf-bg 의 diff 캐시가 poll 은 개선했으나 rebuild 직후 cold 경로가 남아 있었음.)

### 수정 (FE admin.js)
- `_metaG6Apply`: setData(build 의 `states:` 로 전 상태 bake) 후 `_stateCache` 를 clear 대신 **방금 bake 된 signature 로 populate** → rebuild 직후 refresh no-op.
- `_metaGraphRefreshStates`: 변화분만 적용 + 변화 노드>4 면 per-node 대신 **`_metaG6Apply(false)` 단일 rebuild** 폴백(전 상태 한 번에 bake, ~80–200ms 상수, 카메라 유지).
- 폴 tick 이중 refresh(markAnalyzed+markRunning) 를 **rAF coalescing** 으로 1회 병합 — 이중 rebuild + in-flight setData/draw 재진입 방지.

### 검증
- 헤드리스 harness 실측: **post-rebuild refresh(마커 무변화)=0ms · bulk 55마커=rebuild 82ms · 구 per-node 200노드=8,890ms** → ~9s→~0–80ms.
- §18.8 적대 2렌즈: 정확성/상태유실 BLOCKING 0(캐시 populate ≡ setData bake, selection 유지, 재귀 없음), 프리즈재발 렌즈의 폴 이중 refresh 지적 → coalescing 반영. NIT(combo/schema 캐시·THRESHOLD 200ms 경계)는 수용. (REV-20260702T133000 [AGENT-TEAM])
- `node --check` PASS. cache-buster `?v=20260702-graph-expand-perf`.

### 잔여
- 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 대량 스키마 노드 더블클릭 시 프리즈 없이 즉시 확장 + AI 능동분석 중 stutter 없음(사용자 육안).
## 2026-07-02 · 그래프 뷰 초기 진입 줌아웃 가시성 개선 — 스키마-우선 진입 (graph-initview)

### 배경 (사용자 보고 + 다각도 검토 → Phase 1+2 통합 결정)
스키마 클러스터 내 테이블·컬럼 노드가 많으면 초기 전체-fit(`fitView`)이 콘텐츠 bbox 에 무제한 종속되어
판독 불가 줌아웃 발생. 5축 검토 후 사용자 결정 **Phase 1+2 통합**(AskUserQuestion, 2026-07-02). 실데이터:
최대 scope `mssql-06656002eda6` = **62 스키마 × ~257 테이블** — 구 진입 뷰는 cap 200 으로 전체의 ~1.2% 만
무통보 부분표시. TASK §25.

### 병렬 세션 정합 (2차 검증 workflow 가 stale-base 적발)
착수 base 가 main 대비 23커밋 stale — 같은 날 병렬 머지된 **graph-g6b(#533, 클러스터 다열 masonry+가변폭
shelf-packing)** 가 B축(레이아웃 밀도)을 선점, **graph-perf-bg(#537, `_opSeq` 세대·busy·_stateCache·O(1)
colsByTable)** 가 동일 블록을 재작성. → merge 재정합: **main 판을 기준으로 C1/A/E 만 재적용**, 자체 wrap/
shelf-packing 폐기(g6b masonry 채택), 세대 가드는 perf-bg `_opSeq` 에 편입.

### 구현 (병합 최종본)
- **C1 스키마-우선 진입**: roots=`?mode=schemas` 경량 뷰 → 스키마 카드(`SC:`+key, 테이블수 배지) → 클릭 시
  `?schema=` per-schema lazy 로드 후 combo 승격("XS:" 접기=카드 복귀, 모델 유지라 재펼침 무-refetch).
  백엔드 `scope_schemas`(count 집계·truncated·집계실패=배지없는 카드)·`schema_tables`(truncated) 신설,
  신규 route 0. 검색/이웃 결과 스키마 자동 펼침(게이팅 모드-독립). 단일 스키마 DS 자동 펼침.
  동일-id 카드↔combo 타입 전환의 G6 setData diff 자식 유실은 `SC:` 네임스페이스로 차단.
- **A 뷰포트 정책**: `zoomRange [0.05,4]` + fit 클램프(0.55 하한/1.0 상한, focusFirst=초기·검색만) +
  이웃확장 앵커 국소 focus(줌아웃 재발 차단). 미렌더 모델키 setElementState 는 renderedIds 매핑으로 차단
  (_metaApplyState/refreshStates 단일 경로).
- **E 내비게이션**: minimap(우하단 카드형) + 줌 툴바(−/+/전체/1:1 — '전체'는 의도적 무클램프 조망) +
  스키마 점프 select.
- **동시성**: ExpandSchema 를 perf-bg `_opSeq` 세대에 편입 — 사용자 클릭=새 세대(++), LoadRoots silent
  자동펼침=부모 세대 상속, await 후 세대 불일치 시 ingest 없이 폐기(**교차 스코프 오염 원천 차단**) +
  진입 scope 가드(이전 scope 카드 stale 클릭 차단) + 연타 in-flight 가드.

### 검증
- 1차 §18.8 적대 리뷰: BLOCKER 0·MAJOR 2(dead-card·roots race)·MINOR 7·NIT 3 — 전건 반영.
- 2차 적대 검증 workflow(3렌즈 병렬): 17 findings(dedup 9) — stale-base MAJOR 포함 전건 반영/해소.
- headless harness(Playwright, 실 마크업+mock API, 200테이블·빈스키마·혼합버전·연타·dead-card fixture)
  병합 최종본 재검증 — TEST.md Run 기록. 라이브 AGE Cypher(count 집계·스키마 필터) 실증 0.23s.
- 단위: metadata_graph units(graceful no-op 포함) PASS.

### 잔여
배포(deploy_scope: included) + PB-0008 실 Windows 시각검증(§21 T21.8 미완분 + graph-g6b·perf-bg 통합 확인).

---

## 2026-07-02 · 그래프 뷰 테이블 노드 펼침 논블로킹 + 성능 최적화 (graph-perf-bg, ADR-005)

### 배경 (사용자 관찰: 펼침 시 렌더 엔진 프리즈)
관리콘솔 > 메타데이터 > 그래프 뷰에서 **테이블 노드 선택→컬럼 펼침 시 브라우저 렌더링 엔진이 멈춤**. 요청: 병목 구간을 백그라운드에서 진행되도록 구성 + 별도 성능 이슈 추가 검증.

### 진단
펼침 임계경로 = `/graph?node=&depth=1` + (미분석 테이블이면) `/graph/columns` **information_schema 라이브 조회(무캐시, 1~5초)** 2왕복 → `setData()`+`draw()` 전체 재구성, 이 전 구간이 busy 페인트 없이 동기적으로 이어져 메인스레드가 얼었다. 부수 병목: `_metaTableHasCols` 매 클릭 O(N) 전노드 스캔, `_metaGraphRefreshStates` 2.5s 폴 포함 매 호출 전노드 개별 `setElementState`.

### 수정 (FE admin.js + BE admin_metadata.py)
- **논블로킹 파이프라인**: busy 하이라이트(teal 점선) 페인트 → double-rAF(`_metaYieldPaint`) 양보 → fetch·재구성. `_opSeq` stale-render 토큰을 await 경계마다 대조(모델 교체 `_metaGraphResetModel`·`_metaGraphLoadRoots` 도 게이팅).
- **O(1) 펼침 인덱스** `colsByTable`(`_metaTableHasCols` 단일소스) — 클릭당 전노드 스캔 제거.
- **상태 적용 diff+batch**(`_metaGraphRefreshStates` 변화분-only + `startBatch`). busy = `_busyKeys`(소유 op) + `_metaStateSig`/`_metaApplyState`(요소적용과 `_stateCache` signature 동기화 — 폴 덮어쓰기·rebuild 재-bake·캐시 불일치 차단).
- **레이아웃 churn 분리**(`_metaG6Build` Pass1 collapsed 배정 / Pass2 real push-down) — 형제 열-점프로 인한 setData update 집합 팽창 억제, shelf-packer 는 real 높이 소비(무겹침).
- **BE introspection TTL 캐시**: `/graph/columns` 성공결과를 `(scope_key, fqn)` 프로세스-로컬 TTL(기본 300s) 캐시 — 반복 펼침·다중 사용자·재진입의 라이브 조회 왕복 제거. 실패·빈결과 미캐시, 상한 512, TTL≤0 비활성, 마이그레이션 없음.

### 검증 (§18.8 적대 패널 — 다단계)
- 3렌즈 패널(race/index-drift/layout+cache): **4건 BLOCKING 적발** — ① reset/search/scope 경로가 `_opSeq` 미증가 → in-flight expand 가 검색·스코프 화면을 덮어씀(stale 렌더), ② 같은 race 로 `colsByTable` 포이즌(재펼침 영구 차단), ③ seq-mismatch early-return 이 busy 하이라이트 영구 잔류, ④ 2.5s 폴이 fetch 중 busy 제거 + `_stateCache` 불변식 위반. index-drift 렌즈는 steady-state 동치 확인, layout+cache 렌즈는 clean(오버랩 없음·캐시 보안/격리/축출 정상).
- 5-agent 재검증 워크플로: 4건 **CLOSED** 확인 + **신규 BLOCKING 1건**(loadRoots reset-vs-reset — 자기 fetch 후 seq 재검 없이 additive ingest → 혼합-스코프 그래프) 적발.
- loadRoots seq 가드 추가 후 최종 재검증: **reset-vs-reset 6조합 CLOSED, 정당 흐름 회귀 없음.** NIT(동시-key busy 깜빡임·후행 syncMarkers 일시 stale 텍스트·BE 캐시키 대소문자 fragmentation·백엔드 key/fqn 계약 의존)은 비-가시회귀로 수용 기록(REVIEW.md).
- `node --check`·`py_compile` PASS. cache-buster `?v=20260702-graph-perf-bg`.

### 잔여
- graph-perf-bg 배포(web 재빌드) + **라이브 PB-0008 실 Windows 시각검증**(대량 스키마 테이블 펼침 무프리즈 + busy 피드백 + 반복 펼침 즉시응답) — 정적 자산이 web 이미지에 baked 라 배포 후 수행.

---

## 2026-07-02 · 그래프 관계 분석 LLM = claude-haiku (node-analysis-haiku)

### 배경 / 근본원인
사용자 보고: 관리콘솔 그래프뷰 상세 패널 "AI 능동 분석"(각 노드·관계 분석)이 **로컬 gemma(alias `edge`)** 로 작동 — 의도하지 않은 구조, claude-haiku 로 전환 요청. 진단 결과 관계 분석 함수 `llm_node_analysis`(`llm.py`)가 모델을 `AGENT_INSIGHT_MODEL or OPENAI_MODEL` 로 해석하는데, 운영 `.env` 의 `AGENT_INSIGHT_MODEL=edge` 가 이를 gemma 로 고정. 이 값은 `llm_schema_insight`/`llm_table_insight`/`llm_account_insight`(부트스트랩 테이블·컬럼 설명)와 **공유**된다.

### 범위 결정 (사용자, 2026-07-02)
**그래프 관계 분석만** claude-haiku 로 전환 — schema/table/account insight 는 공유 `AGENT_INSIGHT_MODEL`(gemma) 유지. (요청 문구 "그래프 뷰에서 각 관계를 분석하는 LLM" 에 정확 대응, 부트스트랩 설명 생성 비용 불변.)

### 변경
- **`shared/config.py`**: 전용 `AGENT_NODE_ANALYSIS_MODEL = os.getenv(...) or "claude-haiku-4"` 신설 + `__all__` 노출. 코드 기본값 자체가 claude-haiku 라 `.env` 미설정이어도 "의도한 구조"로 동작.
- **`llm.py` `llm_node_analysis`**: 모델 = `AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL`. max_tokens/temperature/timeout 경로는 기존과 동일(모델 catalog 가 `claude-*` cap·temperature 처리). insight 3함수는 손대지 않음(격리).
- **`node_analysis.py` `process_pending`**: 저장·표시용 `model` 라벨을 라우팅과 동일 순서(`AGENT_NODE_ANALYSIS_MODEL` 우선)로 해석 — 상세 패널이 실제 사용 모델(claude-haiku)을 표시. 이 순서가 어긋나면 UI 에 gemma 오표시.

### 검증
- 회귀 테스트 4건(`test_llm_env_naming.py`): 기본값=`claude-haiku-4`(그리고 `AGENT_INSIGHT_MODEL=edge` 여도 node analysis 불영향=분리 확인)·env override·공백/whitespace 폴백·`__all__` 노출. **pytest 38 pass**(env-naming + node_analysis_relevance), ruff clean, config/llm/node_analysis compile·import OK.
- 모델 정합: `claude-haiku-4` 는 model_catalog 카탈로그 기본값(`API_DEFAULT_MODEL`)이자 litellm_config.yaml 의 유효 alias(`anthropic/claude-haiku-4-5`).
- §18.8 적대적 코드리뷰(subagent): 격리·touchpoint 완결성·haiku create() 정합·폴백 안전. REVIEW.md.

### 반영 조건 / 비용
반영엔 런타임 `.env` 에 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 반영(코드 기본과 동일 — 명시 권장) + **insight-worker 재빌드·재기동**(코드 baked, 외부영향=배포 confirm). **외부 API 비용 발생**(그래프 노드 분석이 무료 로컬 gemma → Bedrock claude-haiku 유료). node_analysis 예산 캡(depth/node budget·dedupe)으로 run 당 경계. 기존 저장 분석은 이전 라벨 유지, 신규 run 부터 claude-haiku.

### 배포 완료 (2026-07-02, node-haiku-deploy · 사용자 confirm 승인)
resume 세션이 원본(세션 63cc38df — commit/push 직전 사용자 중단)을 인계 → PR #535 main 병합(617e9a74) 후, 사용자 "랜딩+배포" 결정에 따라 라이브 배포·검증:
- `.env` 에 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 추가(코드 기본값과 동일, 명시).
- insight-worker 이미지 재빌드(`repo-insight-worker` b5e23727, 새 코드 baked) + `docker compose up -d --no-deps --force-recreate insight-worker` → **healthy**. web-a/web-b·ask-worker 무영향(insight-worker 만 재생성).
- **smoke PASS**: 컨테이너 env `NODE_ANALYSIS=claude-haiku-4`/`INSIGHT=edge`(격리) · `config.AGENT_NODE_ANALYSIS_MODEL='claude-haiku-4'`·`__all__` 노출 · `llm_node_analysis` 라우팅 소스 `_insight_model=AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL` 확인 · 클린 기동(traceback/critical 0).
- 잔여(사용자 실검증): 관리콘솔 그래프뷰 "AI 능동 분석" 신규 run 의 model 라벨=claude-haiku 육안 확인. 현 WSL 환경은 게임 DB 망 미도달(circuit_open)이라 라이브 LLM run 강제 불가 — 실 브라우저 확인 권장.
---

## 2026-07-02 · 노드 우클릭 상세 상호작용 (graph-ctxmenu, REQ-20260702T113000)

### 배경 (사용자 요청)
그래프 뷰에서 각 노드의 **우클릭 상세 상호작용** — DB 스키마를 아직 파악하지 못한 사용자가
선택 노드의 연관 관계를 상세하게 파악하는 과정을 지원.

### 구현 (frontend-only — admin.js/styles.css/admin.html, TASK.md §24)
- **우클릭 컨텍스트 메뉴**: G6 `node:/combo:/canvas:contextmenu` + container capture 리스너
  (브라우저 기본 메뉴 차단 + 좌표 캡처). kind 별 항목 — Table(상세 보기·관계 상세·관계 확장
  1~3-hop chips·중심 보기·컬럼 펼침/접기·AI 능동 분석·FQN 복사), Column(+소속 테이블 상세),
  GlossaryTerm(이름 복사), 클러스터(클러스터 상세·스키마명 복사), 빈 캔버스(전체 맞춤·초기화).
  HTML 오버레이 메뉴(전부 DOM 생성 — XSS 0, G6 setData 재구성과 무간섭). 뷰포트 clamp +
  Esc/외부클릭/스크롤 dismiss + ↑/↓/Enter 키보드 접근.
- **관계 상세 패널**(핵심): 선택 노드의 관계를 **방향별**(→참조함/←참조받음/연관 용어/주변
  관계)로 그룹해 추정/신뢰 배지 + weight + cardinality + **근거 한글 라벨**(FK 스키마 선언/
  명명 규칙 추정/대화 JOIN 학습/AI 인사이트) + 상대 노드 설명과 함께 나열. 행 클릭 = 상대
  노드 상세로 이동(연쇄 탐색). 상세 카드 head 의 "🔗 관계 상세" 링크로도 진입(발견성).
- **중심 보기**: 모델 리셋 후 앵커 N-hop 만 로드 — 누적된 화면 없이 관심 노드 집중.
- mutation 0(읽기성 탐색 + 기존 AI 분석 트리거 재사용) — RBAC(`metadata.graph.read`)·데이터
  API·백엔드 불변. CONVENTIONS §10.7 pending 대상 아님.

### 검증
- `node --check` PASS · WSL-headless-harness **28/28 PASS**(네이티브 우클릭 이벤트 경로 실증
  포함 — TEST.md). §18.8 적대 패널(ux/design/qa) MAJOR 3 전건 수정 — 엣지 우클릭 메뉴·앵커 측
  조인 컬럼 표기·중심 보기 지속 칩("✕ 전체 보기" 복귀). REV-20260702T121500.
- **PB-0008 라이브 실측 PASS(2026-07-02)**: 배포 16fc1598 후 실 Windows Chrome 에서 우클릭 메뉴 전 항목·관계 상세 패널·중심 보기 칩+복귀·클러스터 메뉴·Escape dismiss 실측(스크린샷 4매 artifacts). 잔여: 추정 관계 데이터 축적 후 관계 행·엣지 메뉴 라이브 재확인(권장).

---
## 2026-07-02 · 그래프 뷰 PB-0008 라이브 검증 + 레이아웃 UX 개선 (graph-g6b)

### PB-0008 실 Windows 브라우저 시각검증 — PASS (핵심 마이그레이션)
graph-g6 무중단 배포(web-a/web-b `8c45f070`) 후, 실 Windows Chrome/149(win-browser relay, `https://localhost/admin` 로그인 세션)로 라이브 검증. 데이터소스 `mssql-06656002eda6`(실데이터 **236 노드·36 클러스터**) → G6 Canvas 렌더 정상, teal 테이블 칩·점선/실선 엣지·클러스터 자연정렬·노드 클릭 **제자리 컬럼 펼침**(예: dt_EventItemWithMonster 컬럼 12개)·"−" 접기 컨트롤 모두 실화면 확인. (초기 접근이 host-header 로 막힌 건 win-browser CLI 인자 오류였고 — `goto --url`/`eval --script` — 정정 후 정상. 최종 도달 URL = `https://localhost/admin`, WEB_ALLOWED_HOSTS ∋ localhost.)

### 레이아웃 UX 개선 (사용자 요청: 기본 디자인·노드확장 가시성·UX)
라이브 실데이터에서 드러난 문제: 구 결정론 배치가 **① 테이블 많은 스키마를 끝없는 세로 1열**로 만들고 **② 36클러스터를 세로로 쌓아 fit-all 시 전부 극소**. 개선:
- **클러스터 내 다열 masonry**(테이블 수 기반 1~4 내부열, 최단열 배치로 높이 균형) — 24테이블 스키마가 24행→8행×3열. 펼친 테이블(컬럼 포함)도 masonry 높이에 반영돼 인접열과 무겹침.
- **가변폭 클러스터 shelf-packing**(좌→우 채우고 폭 초과 시 다음 행) — 클러스터를 넓고 낮게 펼쳐 가로 활용 극대화, fit 가독성↑.
- 검증: WSL-headless-harness(14 클러스터, 테이블 1~24, 확장 포함) 전 플로우 PASS·에러 0. cache-buster `admin.js?v=20260702-graph-g6b`.

---

## 2026-07-02 · 그래프 뷰 렌더링 엔진 교체 Cytoscape(WebGL)→AntV G6 v5 (ADR-004, graph-g6)

### 배경 (사용자 관찰 5건 + 엔진 단위 개선 결정)
① 펼친 테이블 클릭 시 접힘 · ② 펼침이 다른 위치서 일어나고 카메라 점프 · ③ 줌/스크롤 시 HTML 오버레이(클러스터명·닫힘버튼)와 캔버스 갱신단위 불일치(오버레이가 먼저 줌) · ④ 유사 스키마 클러스터(dk_game_release_*) 순서 뒤섞여 난립 · ⑤ 테두리 크기 왜곡. 사용자 결정: "엔진 단위 개선 — 상용/프로덕션급 렌더러 리서치, 세련된 디자인 + 성능 안정 반응형". → 리서치 후 **AntV G6 v5(무료 MIT, 네이티브 combo·리치노드·Canvas)** 채택 + 사용자 승인("바로 G6 마이그레이션").

### 진단
③⑤ 근본원인 = 이전 **WebGL 렌더러**(sprite-atlas 텍스처 스케일 → ⑤; render 이벤트 미emit → 오버레이 동기화 불가 → ③). Cytoscape 는 리치노드(닫힘버튼·컬럼) 네이티브 미지원 → HTML 오버레이 hack 강제(③ 유발). ①②④=상호작용·fcose 힘배치.

### 설계·검증 (POC 우선 — 브라우저 반복)
G6 v5 전 요소를 Playwright headless POC 로 실증. **G6 v5 함정 확정**: element `type` 은 `style` 형제 / `render()` 초기·`draw()` 증분 / **`lineDash:false` 크래시**(실선은 키 생략) / 위치 `style.x/y` / 마커 `states`+node state config. 설계·POC: `../g6-migration/BLUEPRINT.md`·`poc/`.

### 구현 (admin.js + admin.html + styles.css)
- **모델 B(2단)**: 스키마=combo(점선 카드)·테이블=rect 칩·컬럼=circle·"−"=rect 컨트롤. JS 모델 → `_metaG6Build()`(위치 포함) → `setData`+`draw()`. 스키마 자연정렬 grid + 테이블 세로 스택 + 컬럼 세로열(**결정론 = ④ 무-shuffle, ② 제자리**).
- **오버레이 3함수 전량 제거** — 클러스터명·접기·컬럼 모두 G6 네이티브 렌더 → **③ 동기화 지연 구조적 소멸**.
- 상호작용: 단일클릭=상세+펼침 전용(펼침이면 no-op → **① 해소**), "−"만 접기, 더블클릭(320ms)=이웃확장. 마커=node state. 점선/실선 엣지 복원.
- 유지(DOM/API): 상세 카드·진행 패널·AI 분석·클러스터 상세·resizer. 데이터 API 불변.
- admin.html: cytoscape·layout-base·cose-base·fcose 4종 제거 → `g6.min.js?v=5.1.1`. cache-buster `?v=20260702-graph-g6`. styles.css 오버레이 CSS 제거.

### 검증 (dev-loop, Environment: WSL-headless-harness — TEST.md 참조)
포팅된 그래프 코드 + 실 admin.html 마크업 + mock apiFetch 로 전 플로우 **PASS, 에러 0**: roots(grid·마커·엣지)·제자리 펼침·재클릭 무접힘(hasCols 유지)·"−" 접기·검색(유사도 크기). `node --check` PASS, 제거심볼 참조 0.

### 잔여
실앱 배포(web 재빌드) + **PB-0008 실 Windows 시각검증(하드 게이트)** + `verify-completion.sh` + commit. (배포·commit=외부영향 → confirm.)

---

## 2026-07-01 · 컬럼 blob·프레임 거침·느린 줌 수정 (graph-perf2, WebGL 후속)

### 배경 (WebGL 배포 후 사용자 육안 3건)
(1) 프레임 여전히 거침, (3) 17컬럼 테이블 더블클릭 시 컬럼이 세로 스택 아닌 **원형 뭉치(blob)**, (4) 휠 줌 너무 느림.
(2 라벨유지=OK.) → WebGL 로도 거침이 안 잡혀, 병목이 렌더가 아님을 시사.

### 진단 (5에이전트 워크플로: 3렌즈 진단 → 통합설계 → 적대검증)
- blob·거침 **동일 뿌리**: 컬럼 세로정렬을 fcose 제약(alignment/relativePlacement)에 위임 + 화면 전체 테이블 제약을
  numIter 1000 동기 tick 마다 재구성·적용. (a) fcose 가 신규 컬럼 **ring seed**(반경 90 원)를 세로로 못 펼쳐 blob
  잔존, (b) 제약 동기 계산(cose-base runSpringEmbedder while-loop, rAF/yield 0건)이 rAF 를 굶겨 프레임 거침.
  **WebGL 은 렌더만 GPU 화 → 이 계산 병목과 무관**(거침 개선 없던 게 정합). 줌=독립(wheelSensitivity 0.3=기본 1/3 스텝).
- verify(적대): go-with-fixes. 컬럼정렬 공백경로 없음, 제약 '키 제거'가 fcose tile-off 취약성 오히려 제거(더 안전).

### 수정 (admin.js)
- 컬럼 세로정렬을 fcose 제약에서 **제거** → layoutstop `_metaGraphPlaceColumns` **결정론적 세로 배치**(batched, ordinal,
  무게중심 상하대칭·x통일, 전 경로 공통). 신규 컬럼 seed ring→세로. `wheelSensitivity` 제거(기본 1). 박스 겹침 상쇄
  PITCH 22→18 + nodeSeparation 150→220.

### de-risk (실 Windows 브라우저)
17컬럼 + 6이웃 ERD 렌더 → **컬럼 x-spread 0.0px(완벽 세로스택·blob 소멸)** + **박스겹침 2→0**(PITCH18/nodeSep220). 스크린샷 확인.

### 검증
- node --check PASS. 적대 리뷰 BLOCKING 0(REV-20260701T220000). **실 FPS·대규모 겹침·줌 체감은 사용자 실 하드웨어 재확인이 최종.**

## 2026-07-01 · 렌더러 canvas-2D → WebGL 전환 (graph-webgl, 프레임레이트 근본 해소)

### 배경 (사용자 육안 후속)
camfps(카메라 애니 중 라벨 숨김) 배포 후 사용자 육안: "여전히 거친 프레임 + 애니 시작 시 라벨 사라짐(불호) +
렌더링 엔진이 부드러운 프레임 지원하는지 검토". 사용자 직감이 정확했음.

### 진단 확정 — 렌더링 엔진이 구조적 상한
- vendored **Cytoscape 3.30.2 = canvas-2D 렌더러 전용**(`getContext("2d")`, `webgl` grep 0건). 매 프레임 그래프
  전체를 CPU 재래스터.
- 트레이스 재분석: 병목은 레이아웃 계산(fcose self 64ms) 아님 → **Cytoscape 코어 렌더 1040ms**(캔버스 재그리기).
  rAF 60fps인데 표시 ~36fps 드롭. GPU(276ms)·컴포지터 유휴. chrome://gpu HW 가속 ON. = canvas-2D 재그리기+합성
  체인의 지연 상한 → 라벨 숨김 등 미세 튜닝으로 못 넘음.

### 결정 (AskUserQuestion 2단)
① canvas 유지·애니 최소화(A) vs WebGL 업그레이드(B) vs 라벨만 복구(C) → **B**. ② WebGL 은 taxi→bezier·dashed→
미지원 강등이 따름 → 강등 수용(A) / 엣지 재설계(B) / 보류(C) → **엣지 재설계(B)**.

### de-risk (실 GPU) — make-or-break 통과
그래프가 ERD-card compound(스키마>Table>컬럼 2단 중첩)로 진화 → WebGL compound 지원이 관건. **실 Windows 브라우저
(win-browser)에서 cytoscape 3.34.0 + webgl:true + 2단 compound 최소 페이지 렌더** → webglContextDetected=true,
compound 박스·라벨·bezier 엣지 전부 정상(스크린샷). 전체 구현 전 리스크 제거.

### 구현
- vendor cytoscape 3.30.2→**3.34.0**(unpkg 정품, fcose 2.2.0 호환 유지). `renderer:{name:"canvas",webgl:_webglOk}`
  + feature-detect 폴백. 엣지 재설계(bezier·색/투명도 구분). 애니 중 라벨/엣지 숨김 전면 제거(항상 표시). pixelRatio 제거.

### 검증
- node --check PASS. 적대 리뷰 패널(§18.8) → REVIEW.md. PB-0008 실 Windows 브라우저(WebGL 활성·compound·라벨·엣지·
  부드러움·대규모 이웃). **실 FPS 효과는 사용자 실 하드웨어 재측정이 유일 검증**.
## 2026-07-01 · AI 능동 분석 재귀 — 앵커-상대 관련도 게이팅 (node-analysis-anchor)

### 요청·증상
- 관리콘솔 > 메타데이터 > 그래프 뷰 "AI 능동 분석"(node_analysis) 재귀의 기준이 불명확. `dk_data_release.Achievement`
  분석 시, 테이블에 연결된 컬럼을 따라 depth 가 깊어지면 **대상 노드(예 `UniqueID`)를 기준으로 다시 탐색**하는
  동작. 요구: 처음 분석하려던 대상(Achievement/dk 제품) 기준으로 탐색 + 하위 컬럼 기본 분석 + 깊은 확장은
  "dk 제품·Achievement" 연관 높은 대상만 + 단순 컬럼명 일치·상위객체 무연관은 낮은 우선순위.

### 근본원인
- `node_analysis._enqueue_neighbors` 가 방문 노드의 이웃 **전부**(`ctx["neighbors"]`)를 무차별 pending 재큐.
  게이트는 depth_budget/node_budget/UNIQUE dedupe **뿐** — 원래 루트와의 관련도 판단이 전무한 무방향 BFS.
- 결과: 일반 허브 컬럼 `UniqueID`(여러 테이블이 REFERENCES 공유)나 부모 **Schema** 노드(HAS_TABLE 로 형제
  테이블 전량 보유)를 방문하면 그 노드가 **새 중심**이 되어 무관 테이블로 fan-out. Achievement/dk 앵커 상실.

### 조치 (ADR-003, 상세 CHG-20260701T173000)
- 재귀를 **원래 루트(anchor)** 에 고정하는 관련도 게이팅 도입:
  - `_build_anchor`/`_load_anchor`(run 당 캐시) — 루트 scope·table_fqn·이름/설명 토큰.
  - `_relevance(node, meta, anchor)` — 같은 제품(scope)/루트 테이블 서브트리/이름·설명 토큰 겹침(일반어 stoplist
    제외)/GlossaryTerm/REFERENCES 신뢰(ADR-002). 다른 제품 감쇠, Schema·broken=0.
  - `_score_candidates` — 루트 직속 컬럼(depth0 child)은 1.0 무조건 통과(하위 컬럼 기본 분석), 그 외 임계 이상만
    (depth≥2 는 _DEEP 상향) 관련도순 재큐.
  - `node_analysis_jobs.relevance`(alembic 0029) 영속 + claim `depth ASC, relevance DESC` 우선순위.
- 튜닝 노브(env): RELEVANCE_MIN(0.18)/_DEEP(0.34)/CROSS_SCOPE_FACTOR(0.25)/EXPAND_SCHEMA(off).

### 검증
- 단위: `test_node_analysis_relevance.py` **28건 PASS**(pytest, 초기 12 + 2라운드 적대 패널 16). 핵심 — hub 컬럼
  depth1 확장 시 교차-제품/무관 이웃 탈락 + 관련 이웃만 관련도순 유지; 루트 하위 컬럼(UniqueID 포함) 무조건 통과;
  Schema/broken=0; content-gate(신뢰·제품만으론 불통과); 한글 일반어·접두접미 부분연관.
- 적대 검증: 2라운드 패널(REV-20260701T173000) R1 M1~M5 + R2 MAJOR·MINOR 전건 처리, BLOCKER 0.
- **배포·라이브 검증 PASS** (2026-07-01): alembic 0029 라이브 적용(live=0029) · web-a/web-b 무중단 7bca9b2 ·
  insight-worker 7bca9b2 재기동. 실데이터 프로브(insight-worker 내부, LLM 0) — `dk_data_release.Achievement`
  하위 컬럼 4개 rel 1.0 통과 + **부모 Schema(형제 테이블 123개) 탈락 = fan-out 지배 경로 차단 정량 확인**.
  그래프 UI 마커 시각 최종은 PB-0008 후속(웹 자산 무변경, 하드 게이트 아님).

### 범위 밖
- 그래프 UI 마커/진행 패널 표시 자체는 변경 없음(백엔드 재귀 선정만). relevance 는 get_run_status 로 노출만 —
  프론트 우선순위 시각화는 후속 옵션.

## 2026-07-01 · 그래프 애니 프레임레이트 저하 — 카메라 애니 구간 라벨/엣지 숨김 (graphux-camfps, resume 인계)

### 배경 (resume)
이전 세션(2597e01c)이 "노드 수 무관 애니 FPS 저하" 를 8회 반복 진단하다 headless 로 실 FPS 재현 불가 →
사용자에게 DevTools 실측 요청 직후 **컨텍스트 초과("Prompt is too long")로 중단**. 사용자가 트레이스+환경+GPU
샷 제공. resume persona 로 인계해 트레이스 분석부터 재개.

### 진단 (DevTools Performance 트레이스 실측 — Trace-20260701T134334, 10.4s / 70,418 events)
- 메인스레드 busy = 전체의 **20%** (한가). 그중 **Scripting 65%(FunctionCall 1180ms)**, Rendering·Painting 각 1%.
- JS 핫스팟 = Cytoscape 내부: `ts`(캔버스 draw 162ms)·`Cs.apply`/`parsedStyle`/`updateStyleHints`(스타일 재계산)·
  `calculateLabelDimensions`/`boundingBox`(라벨 텍스트 측정·렌더).
- **rAF(메인 JS) = 60fps(median 16.7ms) 로 정상**인데 **실제 표시 프레임(Swap) = ~36fps(median 27.8ms)** → 프레임 드롭.
  대형 잭 189/105/76ms = 데이터 로드/레이아웃 시작 fcose 동기계산.
- chrome://gpu: Canvas·Compositing·Rasterization **HW 가속 ON** (GPU 폴백 아님). rAF 16.7ms 고정 = 사실상 60Hz(144Hz 가설 기각).
- **근본원인**: 레이아웃 애니는 라벨/엣지 숨김 최적화됨(기존)이나 layoutstop 즉시 복원 후 **450ms 카메라 fit 애니가
  라벨·엣지를 켠 채** 돌아 per-frame 텍스트 래스터+엣지 지오메트리 재계산 재발.

### 수정 (admin.js)
- `_metaGraphLayout` layoutstop: 숨김 해제를 카메라 fit 애니 `complete` 후로 지연(`restoreMotion`, guard `!_layoutRunning`,
  setTimeout 650ms fallback). 즉시맞춤/예외 경로는 동기 복원. 이미 레이아웃 애니에 검증된 패턴의 카메라 애니 확장 —
  예전 hideEdgesOnViewport 전역옵션 버그와 무관. 등급 Minor(프론트·비파괴). 캐시버스터 graphux-camfps.

### 검증
- node --check PASS. 적대 리뷰 패널(§18.8) → REVIEW.md. verify-completion → commit/PR/merge → web 재배포.
- **한계(정직)**: 실 FPS 개선은 **사용자 실브라우저에서만 확인 가능** — headless/WSL 은 실 GPU 프레임 미측정(세션이
  막힌 근본 이유). 배포 후 사용자 재측정 필수. PB-0008 은 렌더 정합만 확인.

## 2026-07-01 · 그래프 뷰 컬럼 테이블 하단 실제순서 세로배치 + 부드럽게 꺾이는 엣지 (graphux9/10, 배포 완료)

**요청**: `관리 콘솔 > 메타데이터 > 그래프 뷰` 에서 청색(테이블) 노드에 연결된 회색(컬럼) 노드가 흩어져
순서 판독이 안 되고 타 테이블 엣지와 교차 → (1) **테이블 노드 하단으로 컬럼을 실제 순서대로** 세로 배치,
(2) 연결선을 직선이 아닌 **부드럽게 꺾이는 선**으로.

**구현** (PR #496, `column-ordinal`):
- **컬럼 순서(ordinal)를 관계형 SSOT 에 저장**: alembic **0027** `column_descriptions.ordinal`(비파괴 ADD +
  삽입순 backfill, expand-safe) → `metadata_graph.sync_column` 이 AGE Column 정점에 정수 투영 → 그래프 API →
  프론트 정렬키. 부트스트랩 골격 저장이 `describe_columns`(ORDINAL_POSITION) 순서를 ordinal 로 캡처.
- **프론트(admin.js graphux10)**: `_metaGraphPlaceColumns` 가 각 Table 의 HAS_COLUMN 자식을 ordinal(NULLS
  LAST→name) 정렬해 테이블 바로 아래(우측 54px 들여쓰기) 세로 스택 + lock, `dragfree` 로 테이블 이동 추종.
  `HAS_COLUMN` 엣지 = `round-taxi`(아래→오른쪽 부드럽게 꺾임), 그 외 = `unbundled-bezier`(완만 곡선).
- graphux8b/9(모션 성능·라벨/엣지 트윈 숨김) 정책과 정합(카메라 무애니 `cy.fit` 유지).

**검증**:
- 적대 리뷰 2패널(backend/security + frontend/ux) — 발견 결함 전건 수정(REVIEW.md REV-20260701-0003):
  update_column_desc param 정합·sync_graph graceful·Table drag 컬럼 추종(dragfree)·ordinal 범위가드.
- 순수함수 단위 8건 PASS(ordinal 직렬화·주입안전) · migrate-lint expand-safe · py_compile/node --check OK.
- **배포**(deploy_scope: included): migrate 0027(라이브 적용, 기존 1030 컬럼행 ordinal backfill) + insight-worker
  재빌드 + `metadata-graph-sync`(1030 컬럼 ordinal 투영, errors 0) + web 롤링 재배포(git_commit=47d0f1a,
  edge /healthz 200 안정). ※ 초기 롤링 1회는 동시 재sync 부하로 /healthz 순간 503 → 자동 롤백된 false-positive,
  재sync 종료 후 정상 배포 확정.
- **PB-0008 실 Windows 브라우저 시각검증 PASS**(TEST.md §3): Achievement(4컬럼) 테이블 하단 UniqueID→Type→
  Title→DLC 순 세로배치 + round-taxi 엣지, Item(75컬럼) ordinal 단조 정렬. API 도 1030 컬럼 ordinal 반환 확인.

**주의(발견·복구)**: 최초 작업이 stale `graphux4` base(main 대비 −16커밋) 위에서 진행됨을 배포 직전 발견 →
현재 main(graphux8b/9 + implicit-edges) 위로 재기반(충돌 6+1파일 해소, 성능 결정 존중, 마이그 0026→0027 재번호).

**후속**: MSSQL `column_descriptions.schema_name`(DB명, 예 `dk_data_release`)과 `rag_objects` 투영 테이블 fqn
(예 `dk_data_release_test.*`)의 **키 불일치**로, 일부 테이블은 그래프에서 rag-투영 노드와 curated-컬럼 노드가
서로 다른 Table 키에 걸린다(REPORT 2026-06-30 dbo→DB명 정규화 잔여와 동일 계열). 컬럼이 보이는 것은
curated schema_name 과 일치하는 Table 노드 확장 시 — 근본 정규화는 별도 initiative 권장.

## 2026-07-01 · 암묵 관계(FK 미선언) 추론 + 자기교정 강화 엔진 (implicit-edges cycle)

**요청**: `관리 콘솔 > 메타데이터 > 그래프 뷰` 가 저장하는 연결에서, insight 가 파악한 데이터소스 중
**FK 로 직접 확인 안 되는 뉘앙스적 연결(암묵 JOIN 관계)** 을 파악해 사람·AI 가 쉽게 보게 하되, 그 연결이
정말 올바른지 **항상 검증**해 틀리면 가중치가 약해져 끊어지고(broken) 맞으면 강해져 신뢰(trusted) 관계로
재구성되게 한다.

**배경**: feature-0016 이 남긴 미완 과제(REPORT 하단 "엣지 적재: 현 0 … 대화 JOIN 학습·LLM 추론으로
점증", "T1.6 FK 미선언 보완")의 본체. 게임 운영 DB 8,122 테이블이 FK 를 거의 선언 안 해 그래프에 선이 없다.

**사용자 결정 (2026-07-01, entry persona dispatch)**:
- 검증 방식 = **관찰 + 능동프로브 하이브리드**: AI JOIN 사용 성공(관찰) + insight 워커의 실데이터
  겹침(EXISTS) 프로브(능동)로 양성/음성 신호 생성.
- 범위 = **풀 슬라이스**: 추론 + 강화엔진 + 그래프 가중치 투영 + AI 컨텍스트 필터 + UI 신뢰/추정/파단 구분.

### 설계 (정적 confidence ↔ 동적 weight 분리)
- **스키마 (alembic 0026, 비파괴 ADD COLUMN)**: `table_relationships` 에 `weight`(동적 신뢰),
  `positive_signals`/`negative_signals`, `status`(candidate/trusted/broken), `last_validated_at` 추가 +
  source CHECK 에 `'inferred'` 추가 + 상태/가중 정렬 인덱스. 기존 행 backfill(weight←confidence).
- **추론** (`relationships.infer_implicit_relationships`, 순수): 명명 규칙 2 휴리스틱 — (1) `<base>_id`
  컬럼 → 동명 테이블 PK(name_fk), (2) 접두 있는 키 컬럼 공유(shared_key). 범용 컬럼·과다공유 차원 제외,
  cap 으로 8K 폭주 방지. source='inferred', status='candidate' 로 시작.
- **강화 엔진** (`next_reinforcement_state`, 순수 + `apply_relationship_signal`): 양성 `w+=step*(1-w)`(점근
  상승), 음성 `w*=(1-step)`(더 빠른 감쇠 — 비대칭). w≤0.15 → broken, w≥0.85+양성누적 → trusted.
  **FK 는 권위적 — 강등 없음.** upsert on-conflict 가 강화상태 보존(재추론이 파단 엣지 부활 안 함).
- **"항상 파악" 2 경로**: (a) 대화 — 성공한 JOIN = 양성(`learn_relationships_from_sql` 이 upsert+강화),
  (b) insight 워커 — candidate 를 실데이터 겹침 프로브로 검증(겹침률 ≥0.5 양성 / ==0 음성). 둘 다 guarded.
- **노출**: read·context 주입은 broken 제외 + weight 정렬 + `[추정 w=…]`/`[신뢰]` 태그(AI 가 신뢰수준 인지).
  그래프 투영은 REFERENCES 엣지에 weight/status → UI 신뢰=실선 / 추정=점선 / 파단=숨김 + 범례·상세 배지.
- **config**: `AGENT_RELATIONSHIP_INFERENCE_ENABLED`·`_PROBE_ENABLED`(기본 ON) + `_INFER_CAP`/`_PROBE_CAP`/
  `_PROBE_SAMPLE`.

### 변경 파일
- `feature-0002-agent-core`: `alembic/…0026_relationship_reinforcement.py`(신규), `modules/relationships.py`
  (추론·강화·프로브 엔진), `modules/insight.py`(추론+프로브 훅), `modules/metadata_graph.py`(weight/status
  투영·broken 제외), `modules/dialects.py`(probe_relationship_overlap MySQL/MSSQL).
- `shared/config.py`(플래그 5).
- `feature-0003-agent-web-ui`: `static/admin.js`(엣지 status/weight 데이터·신뢰 배지), `static/admin.html`
  (범례·캐시버스터), `static/styles.css`(신뢰 스타일).

### 검증
- **단위 테스트 PASS** (`test_relationships.py`, 총 38건): 강화 전이(점근 상승·**비대칭 전 구간**·broken
  파단·trusted 승격·FK 불변·50% 오양성에도 파단), 프로브 판정 임계·타임아웃, 추론 휴리스틱(name_fk·
  shared_key·범용/과다공유 제외·cap), digest 신뢰 태그·7-tuple 하위호환, dialect 프로브 SQL(LIMIT/TOP·
  식별자 이스케이프·시간상한).
- py_compile 6 모듈 OK · admin.js `node --check` OK · ruff clean · 전체 suite collection EXIT=0(import 무회귀).
- ON CONFLICT ↔ UNIQUE 불변식 테스트 유지(target 무변경).
- **§18.8 적대 패널(security + backend/qa) 2회 — REV-20260701-0002**: SECURITY 1 MINOR(프로브 statement
  timeout 부재) + BACKEND 4 MAJOR(비대칭 역전·테스트 은폐·파단 엣지 그래프 미회수·downgrade 실패) + 3 MINOR
  (signal race·dead cap config·FK 승격 카운터) — **전건 수정 후 SHIP**. 특히 MAJOR-1(추론 시작 weight 0.30
  구간에서 비대칭 역전 → 틀린 엣지 상승)은 곱셈 감쇠를 고정 감산으로 바꿔 전 구간 down>up 보장으로 해소.

### 잔여 / 후속
- **라이브 e2e = cutover 된 AGE 스택 필요**: alembic 0026 적용 + insight 워커 재빌드 후 `metadata-graph-sync
  --rebuild` → 그래프에 추정 엣지(점선) 출현 확인은 배포 게이트 대상. 프로브는 운영 DB read-only(키 컬럼
  표본 LIMIT 50, cap).
- 주기 re-probe: 현재는 스키마 구조 변경/신규 시 프로브. 상시 재검증은 sync cron 확장(후속).
- PB-0008 실제 브라우저에서 점선/실선·배지 시각 확인(배포 후).

## 2026-06-30 · 라벨 비겹침 펼침 + dbo→DB명 클러스터링

**요청1 (라벨 겹침)**: dbo 클러스터 노드 라벨이 겹쳐 판독 불가 → fcose `nodeDimensionsIncludeLabels:true`
(라벨 박스까지 충돌 회피 = 비겹침 핵심) + `animate:true`(펼침 애니메이션, ~600노드 이하) + nodeSeparation
80→150 · nodeRepulsion 7k→12k · idealEdgeLength 75→120 · tilingPadding 30. cose 폴백도 동일 적용.

**요청2 (dbo 집계 검토)**: **버그 확인 — 의도된 것 아님.** rag_objects(auto-insight)가 MSSQL 에서
schema_name 을 리터럴 'dbo'(기본 스키마)로 저장 → (a) DB 차원 소실(전 테이블 dbo 한 박스) (b) **다중 DB
동명 테이블 충돌**(예: 23개 DB 의 dbo.T_ErrorLog → 1 노드 붕괴, sysdiagrams 16 등). DB명은 object_key
(`<ds>:db.dbo.table`)에 존재. 큐레이션(table_descriptions)은 이미 DB명(AccountDB 등) 사용 → 경로 불일치.
**수정**: `_rag_effective()` 가 object_key 를 파싱해 **DB명을 스키마(클러스터)로 사용** + fqn=`db.table`
(충돌 제거). MySQL(2-seg)은 무변화. 단위 테스트 PASS. 잔여(미세): object_key DB명 소문자(accountdb) vs
큐레이션(AccountDB) 대소문자 차이로 동일 DB 가 2 클러스터 가능 — 후속 정규화 권장(insight-worker 근본수정 동반).

검증: admin.js node --check · metadata_graph.py py_compile · _rag_effective 단위 PASS. 그래프 rebuild 후 라이브 스크린샷.


## 2026-06-30 · 그래프 뷰 UX 개선 (반응형 · 관련도 사이징 · 카테고리 클러스터링)

**요청**: 그래프가 사람이 보기 까다로움 → 반응형 + 키워드 관련도별 노드 크기 + 유사 카테고리 집적.
**웹 리서치**(Neo4j Bloom·Linkurious·Cytoscape): 노드 크기=중요도/관련도·색=카테고리가 표준, 카테고리
집적은 **fcose**(compound force layout, 리서치 1순위)가 정석.

**구현** (admin.html/admin.js/styles.css + vendor):
- **fcose vendoring**(layout-base→cose-base→cytoscape-fcose) — compound 클러스터 force layout. 미등록 시 cose 폴백.
- **카테고리 클러스터링**: 노드를 스키마(scope:schema) compound parent 로 묶음(점선 박스). HAS_TABLE 엣지는
  컨테인먼트로 대체(생략). fcose gravityCompound 로 스키마 내부 집적 강화.
- **관련도 사이징**: 검색 시 노드별 관련도(exact>prefix>contains, name>fqn) 0~1 → 크기 +최대 40·rel≥0.8 테두리 강조.
- **반응형**: ResizeObserver→cy.resize/fit, 캔버스 clamp(420~760px·64vh), 상세패널 접기 토글 + ≤900px 세로 스택, 범례 추가.

**검증**: admin.js node --check OK. fcose 폴백·compound 는 cose 도 지원이라 견고. 라이브 렌더는 배포 후 스크린샷.

## 2026-06-30 · per-datasource 그래프 (rag_objects 투영 + scope 필터)

**배경**: cutover 후 "각 데이터소스 그래프 출현" 검증 중, table_descriptions(큐레이션)는 **단 1개
datasource**(mssql-06656002eda6, 153)만 커버해 나머지 19개 데이터소스 그래프가 비어있음을 발견.
반면 `rag_objects`(auto-insight)는 `datasource_key` 로 **~21개 datasource·8,122 테이블** 커버.

**구현** (metadata_graph.py + app.py + admin.js):
- `sync_graph` step0: **rag_objects 투영**(datasource_key 별 Schema/Table 노드). description=None 으로
  큐레이션 설명 비파괴(table_descriptions 가 같은 key 에 설명 layering). rag_objects 부재 graceful.
- `search_nodes(scope=)` + 신규 `scope_roots(scope)` (datasource 진입 그래프 = Schema→Table 서브그래프, cap).
- API `/api/admin/metadata/graph?scope=` (검색 scope 필터 + scope_roots 모드).
- admin.js 그래프뷰: datasource 선택 시 그 datasource 의 그래프(roots) 즉시 로드 + 검색 scope 격리.
- sync_table description=None 시 미설정(큐레이션 보존). 캐시버스터 bump.

**검증**(throwaway, test_per_datasource_graph.py): per-datasource 투영·scope 격리(dsA/dsB 키 분리)·
HAS_TABLE 엣지·검색 scope·**큐레이션 설명 보존**(rag 투영 무덮어쓰기)·멱등 재sync PASS.
기존 2 모듈 테스트 회귀 0(rag_objects graceful).

## 2026-06-30 · Phase 5 운영 cutover 완료 (사용자 승인 후 실행·검증)

**상태: AGE cutover 라이브 완료.** 사용자 명시 승인("남은 단계 진행 및 검증 완수") 하에 RUNBOOK-cutover.md 따라 실행.

### 실행 (순서대로, 모두 PASS)
1. 백업: `bin/backup.sh` → agent_kb 250M + agent_memory 32M (`artifacts/backups/20260630_154938`).
2. 이미지: `kb-pg-age:pg16` 태그(검증된 AGE 이미지). compose env-var 토글(KB_PG_IMAGE/PRELOAD/REPLICA_PRELOAD, 기본=현행).
3. main 머지: PR #477 → main `0c57e25`.
4. **DB cutover**: `.env` 토글 설정 → postgres·postgres-replica 재생성(AGE 이미지+`shared_preload=...,age`).
   - primary: age preload ✓, **데이터 무손상**(rag_objects=14889, table_descriptions=153), 1s 순단.
   - replica: age preload ✓, streaming ✓, **graph WAL 복제 ✓**, agent_kb_ro Cypher read ✓(pgbouncer-safe).
5. **alembic 0025**(postgres superuser 적용 + stamp): graph=1, labels=13, role search_path 양쪽 적용.
6. worker(ask/insight) 재빌드+재생성 → `bin/metadata-graph-sync.sh` 초기 적재: **153 tables, 0 errors**.
7. web 롤링 재배포(web-a→web-b one-at-a-time, 둘 다 healthy, 무중단). deploy-web.sh 는 본 세션 sandbox 의
   `/tmp` provenance-metadata 이슈로 ABORT(이미지는 정상 빌드) → 수동 health-gated 롤링으로 완수.

### 라이브 검증 (PASS)
- API 라우팅: `GET /api/admin/metadata/graph` → HTTP 401(auth gate, 등록됨).
- 그래프 투영(RO=replica): 실제 게임 테이블 `AccountDB.T_AccountAuth_2`(한국어 설명 포함) 검색 + 34노드 이웃.
- `graph_navigate` AI tool: 등록 ✓, 'AccountAuth' 검색 → 실제 테이블·설명·key 반환.
- 회귀(`make test` 등가): **feature-0016 신규 실패 0건**. route_parity 골든 갱신(+1 route, 정당).
  잔여 4건 `test_attachment_idor` 는 **사전존재**(base c5356a5 동일 실패, 첨부 함수 무관 — feature-0016 무관).

### 잔여 / 후속
- **PB-0008 실제 Windows 브라우저 그래프 UI 검증**: 인프라·API·tool 검증 완료, 시각 렌더는 운영자 브라우저 게이트 권장.
- 엣지 적재: 현 0(게임 DB FK 미선언) — 대화 JOIN 학습·LLM 추론으로 점증. 주기 sync cron 배선(RUNBOOK §4).
- rag_objects(8122 테이블 auto-insight) 그래프 투영 = 후속 enhancement(현 sync 는 curated 메타데이터 153).
- 사전존재 `test_attachment_idor` 4건은 별도 이슈(본 feature 범위 밖).
- 롤백: `.env` KB_PG_* 3줄 제거 + postgres/replica 재생성(관계형 SSOT 무변경). 백업 `20260630_154938`.

## 2026-06-30 · 착수 + Phase 0/1a 검증 (entry persona dispatch)

### 배경 / 결정
- 요청: 관리콘솔 메타데이터(테이블·컬럼 설명) 통합 + 관계 명시(Graph DB) + 그래프 UI·검색 + AI 정합.
- 리서치(4 explore agent + 웹) + 라이브 데이터 조회 → RFC(세션 아티팩트 v2-data-grounded).
- 사용자 결정(2026-06-30): **A3 AGE 즉시 도입 · 한 묶음 · 신규 feature-0016**(0015 선점됨).

### 실데이터 기준선 (라이브)
- 프로덕트 18 · 데이터소스 20(MySQL16/MSSQL4) · 제품DB 195.
- 노드: `rag_objects` 14,889 = 8,122 테이블·91 스키마. 자동 insight `fact_entries` table_insight 14,650.
- **엣지: `table_relationships` 0행** (FK introspection 미실행) — Phase 1c 적재 과제.
- 수작업: `table_descriptions` 153(MSSQL 1소스), columns/glossary/enum 0.

### Phase 0 — 커스텀 AGE+pgvector PG16 이미지 (de-risk) ✅ PASS
- `docker/Dockerfile.pg-age`: `pgvector/pgvector:pg16` + Apache AGE `release/PG16/1.6.0` 소스 빌드 +
  빌드 툴체인 동일 레이어 purge. 이미지 **496MB**, 빌드 ~4분(230s).
- 격리 컨테이너 `verify-age.sql` 검증: **AGE 1.6.0** create_graph + Cypher CREATE/MATCH
  (Table/Column/REFERENCES) + **pgvector 0.8.2**(vector+ivfflat+cosine) + **pg_trgm 1.6**(GIN+similarity)
  공존 회귀 0 = **AC-1 PASS**.

### Phase 1a — alembic 0025 그래프 스키마 + RBAC ✅ PASS
- `20260630_0025_age_metadata_graph.py`: CREATE EXTENSION age + create_graph('metadata_kb') 멱등 +
  **vlabel 6**(Product·Datasource·Schema·Table·Column·GlossaryTerm) + **elabel 7**(USES·HAS_SCHEMA·
  HAS_TABLE·HAS_COLUMN·REFERENCES·RELATED_TERM·DESCRIBES) 사전선언 + role-guarded GRANT. downgrade=drop_graph.
- throwaway 검증: 적용 + **멱등 재적용 OK** + 라벨 13개 확인.
- **RBAC 방어심층**: agent_kb_rw Cypher 쓰기(MERGE node+edge) ✓ · agent_kb_ro 읽기(MATCH) ✓ ·
  agent_kb_ro 쓰기 차단(`permission denied for table Product`) ✓ = **AC-2 부분 PASS**.

### 핵심 인프라 발견 (load-bearing)
1. **`shared_preload_libraries='age'` 필수** — PG 는 비superuser 의 `LOAD 'age'` 를 거부
   ("access to library age is not allowed"). 앱 role(agent_kb_rw/ro)이 AGE 를 쓰려면 서버 preload 필요.
   → Phase 5 cutover 시 postgres·postgres-replica `command:` 에 `-c shared_preload_libraries='age'` 추가
   + 재시작. 앱 코드는 세션마다 `SET search_path = ag_catalog,"$user",public`(LOAD 없이).
2. **create_vlabel/create_elabel 시그니처 = `(cstring, cstring)`** (name 아님). 변수는 `::cstring` 캐스트 필수.
   create_graph 는 `(name)`.
3. 마이그레이션은 AGE 이미지 cutover **이후**에만 적용 가능(현 pgvector 이미지에선 CREATE EXTENSION age 실패).

### 산출물 (worktree)
- `unit/feature-0016-metadata-graph/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- `unit/feature-0016-metadata-graph/docker/{Dockerfile.pg-age,verify-age.sql}`
- `unit/feature-0002-agent-core/alembic/versions/20260630_0025_age_metadata_graph.py`

### Phase 1b — 동기화 + 투영 모듈 (metadata_graph.py) ✅ PASS
- `modules/metadata_graph.py`: 관계형→AGE 동기화(sync_table/column/relationship/glossary/sync_graph) +
  투영(search_nodes·neighborhood). 멱등 MERGE, Cypher injection 방어(`_cq`), 라벨/속성 화이트리스트,
  8K 규모 보호 cap(_NEIGHBOR_NODE_CAP=300, _SEARCH_CAP=80). conn 주입 시 shared.db 미import(단독 가능).
- 라이브 AGE 행위검증(tests/test_metadata_graph_age.py): **ALL ASSERTS PASS**
  {search_orders:3, search_주문:1, nb_nodes:7, nb_edges:9, orders_node_count:1}.
  멱등(3회 재sync 중복 0) · 한국어 · injection escape · k-hop(depth2 REFERENCES 도달) 확인.

### 다음 (Phase 1c~)
- T1.4 `bin/metadata-graph-sync.sh` + insight-worker 주기 훅.
- T1.5/1.6 FK introspection 실행(엣지 적재 — 현 0행) + 대화 학습 + FK 미선언 보완.
- Phase 2 투영 API(app.py 엔드포인트) → Phase 3 Cytoscape UI → Phase 4 AI 정합 →
  Phase 5 측정·**cutover(게이트)**·배포.

## 2026-06-30 (cont.) · Phase 1c→4 순차 구축 (cutover 직전까지)

### Phase 1c — 동기화 파이프라인 ✅
- `scripts/metadata_graph_sync.py`(CLI) + `bin/metadata-graph-sync.sh`(워커 exec) + config
  `AGENT_METADATA_GRAPH_SYNC_ENABLED`(기본 OFF). sync_graph 관계형 read 경로 통합검증 PASS.
- FK introspection·대화학습 = 이미 가동(엣지 0=게임DB FK 미선언, 대화학습으로 점증).

### Phase 2 — 그래프 투영 API ✅
- `GET /api/admin/metadata/graph?q=&node=&depth=&limit=`(app.py, RBAC kb.ingest.manual, _pg_connect_ro,
  graceful). 검색·이웃 모드, cap 강제. py_compile OK. e2e=cutover 후.

### Phase 3 — Cytoscape UI ✅(구조 검증)
- vendor cytoscape 3.30.2 + '🕸 그래프 뷰' 서브탭 + 캔버스 + 통합 엔티티 카드(설명+컬럼+관계+용어) +
  검색(debounce)→투영 API, 노드 클릭→이웃 확장(cose). node --check OK, 요소 5/5. 라이브=cutover 후 PB-0008.

### Phase 4 — AI 정합 ✅
- `graph_navigate` tool(tools.py): read-only search/neighbor, metadata_graph 경유, 플래그 off/AGE 부재 시
  graceful. `_MERMAID_DIAGRAM_GUIDANCE` 에 graph_navigate 추가(대규모 스키마는 subgraph 만 pull). py_compile OK.

### 핵심 발견 2 — pgbouncer transaction-mode 안전성 (Phase 4 검증)
- AGE agtype 연산자(`@>`)는 search_path 로만 해소되고 schema-qualify 불가. pgbouncer 풀링은 세션 SET 을
  잃을 수 있음 → **마이그 0025 에 `ALTER ROLE agent_kb_rw/ro SET search_path = ag_catalog,"$user",public`**
  추가(role 기본값, DISCARD ALL 후에도 유지). 검증: agent_kb_rw 접속 + DISCARD ALL 후 @> 동작 PASS.
- metadata_graph `_cypher` 는 `ag_catalog.cypher`·`ag_catalog.agtype` 정규화 + 방어적 SET 병행.

### 회귀 검증 (adversarial)
- test_metadata_graph_age + test_sync_graph_from_relational 둘 다 fresh 컨테이너 PASS.
  (직전 "dup" 은 T1/T2 컨테이너 공유 + fqn-매칭 단언의 오염 — scope-key 단언으로 견고화, 제품 버그 아님.)

### 검증 상태 요약
- Phase 0·1a·1b·1c·2·3·4 = **격리/라이브 AGE 검증 완료**(worktree-local, 운영 무영향).
- 잔여 = Phase 5 운영 cutover(이미지 교체 + shared_preload + ALTER ROLE 반영 + 마이그 + sync + 재시작 +
  web 재빌드 + PB-0008 + cron). **비가역·외부영향 — 별도 게이트 + 롤백 플랜.** (RUNBOOK-cutover.md 참조)

### 검증 미결 / 리스크
- 이 단계 산출물은 worktree-local 비파괴(운영 무영향). 운영 cutover(이미지 교체+shared_preload+재시작)는
  비가역·외부영향 → Phase 5 별도 게이트 + 롤백 플랜(이미지 revert + drop_graph, 관계형 SSOT 무변경).
- 적대 검증 패널(backend/security/qa)은 Phase 1b 코드 작성 후 수행 예정.

### Post-cutover UX/성능 개선 — graphux3 (2026-06-30)
- **이웃 조회 성능 60x**: AGE 엣지 라벨에 `start_id`/`end_id` btree, vertex 라벨에 `properties` GIN 부재 →
  `(a)-[r]-(b)` traversal 과 `{key:'X'}` 앵커가 전 행 Seq Scan. 측정 Table depth1 **9454ms→151ms**,
  depth2 **18564ms→300ms**, Schema depth1 2673→159ms(Schema depth2 30178→5999ms; schema=compound 라
  클릭 비대상). RO(replica) 경로도 141/264ms — 물리복제로 인덱스 자동 전파(20개 확인).
- **인덱스 영구화**: `metadata_graph._ensure_graph_indexes(cur)` 를 `sync_graph` 시작에서 호출(멱등
  `CREATE INDEX IF NOT EXISTS`, drop_graph 재생성 생존). 인덱스명 = `ix_mkb_<label>_props|start|end`,
  라이브와 정합(`term`→`glossaryterm` 1건 ALTER RENAME, product/datasource GIN 보강). 중복 생성 없음 확인.
- **클릭 동작 분리**(admin.js): 단일 클릭 = `_metaGraphShowDetail`(depth=1 상세 카드만, 그래프 유지),
  더블 클릭 = `_metaGraphExpand`(이웃 그래프 확장/전환, 기존 단일클릭 동작). cytoscape 코어에 dbltap
  부재 → 350ms 윈도우 수동 감지. 힌트/주석/캐시버스터(graphux3) 갱신. node --check·py_compile OK.

### 더블클릭 확장 속도 — graphux4 (2026-07-01, ultracode 3축 조사→적대검증)
사용자 보고 "더블클릭 연결관계 펼치는 속도 느림". 3축 병렬 조사 + 적대 검증(회귀·정합·UX 렌즈)으로 진단:
- **지배 병목=클라이언트 레이아웃**: `_metaGraphLayout` 이 확장마다 fcose `randomize:true`·`quality:proof`·
  `numIter 2500`·`animate 1000ms`·`fit:true` 로 **전체 병합 그래프(루트+신규)를 spectral 재초기화**→기존 노드까지
  재배치·뷰포트 점프(벤더 fcose: `PURE_INCREMENTAL=!randomize`). **수정**: 확장 전용 증분 경로 — 기존 노드
  `fixedNodeConstraint` 고정 + `randomize:false`·`quality:default`·`numIter 400`·`animate 450ms`·`fit:false`,
  신규 노드는 앵커 근처 seed 후 신규 영역으로만 카메라 이동. **초기 로드/검색은 불변**(좌표 없는 재구축이라
  randomize:true 필수 — 검증 blocker: randomize:false 전역화 시 원점 뭉침).
- **서버 쿼리(부차)**: Cypher `MATCH (a)-[r]-(b) WHERE a.key IN [...]` 는 GIN 미활용 Seq Scan(332ms/hop),
  startNode/endNode 방향보존은 3.5x 악화, UNWIND `{key:k}`(변수 containment)는 hang — 실측 확인. **AGE 플래너
  우회 raw graphid id-bound SQL** 로 재작성: key→graphid(`@>` GIN, 파라미터화 injection-safe) → 엣지 라벨
  `start_id/end_id=ANY`(btree) → vertex 라벨 `id=ANY`(pk), UNION ALL 로 왕복 축약. depth2 660→~208ms(3x).
  **방향 버그 동시 해결**: 무방향 -[r]- 이 프론티어 기준 source/target 을 뒤집어 화살표 역전·역중복 엣지를
  만들던 잠재 버그를, start_id=source·end_id=target(물리 방향)+방향정규화 dedup 으로 제거. `ag_label` 앱 role
  권한 없음 → 라벨명은 `_VLABELS`/`_ELABELS` 상수 순회(gid 는 정확히 한 라벨 테이블 소속). 회귀 테스트 추가
  (Table·Column 시작 방향 보존 + 역중복 0). 컬럼 보유 테이블은 depth1 에 컬럼 노출(상세카드 개선).
- **범위 밖(별도 이슈로 보고)**: 형제 테이블 edge-type 필터 제거는 **미채택** — HAS_TABLE 은 이미 비가시
  (compound), 제거 시 노드만 사라지고 컬럼 미투영 99% 테이블 확장이 텅 빔("느림"→"빈 결과"). 데이터 완전성
  갭(REFERENCES=0, HAS_COLUMN 커버 0.78%)은 FK/컬럼 introspect 파이프라인 후속 initiative 로 분리.

### graph sync 부하 분산 — batched commit + incremental (TASK-0308, 2026-07-03, worktree=insight-load-spread)

**문제**: `sync_graph` 가 실측 규모 **Table 15,022 / Column 8,709 / REFERENCES 9,562 / HAS_TABLE 15,022 ≈ 57,000+ 노드·엣지**를 `_rw_conn(autocommit=True)` 로 노드/엣지당 **개별 MERGE** → cron 30분마다 **~5.7만 WAL fsync** 폭주. pg_stat_activity 에 `ag_catalog.cypher('metadata_kb', MERGE (n:Schema ...))` WALSync 대기가 주기적 CPU/디스크 부하 스파이크로 관측됨. 변경감지 없이 full sync(변경 없어도 매번 전량 MERGE).

**수정** ([metadata_graph.py](../../feature-0002-agent-core/src/modules/metadata_graph.py), [metadata_graph_sync.py](../../feature-0002-agent-core/src/scripts/metadata_graph_sync.py), [bin/metadata-graph-sync.sh](../../../bin/metadata-graph-sync.sh), [bin/install-metadata-graph-sync-cron.sh](../../../bin/install-metadata-graph-sync-cron.sh)):
- **batched commit**: `sync_graph` 가 `_SYNC_MERGE_BATCH`(env `AGENT_METADATA_GRAPH_SYNC_BATCH`, 기본 500)개 MERGE 마다 1회 커밋. 인덱스 DDL·`SELECT now()`(워터마크) 이후 `c.autocommit=False` 로 트랜잭션 시작, `_tick(force=True)` 로 잔여 커밋, `finally` 에서 autocommit 복원. **fsync ~5.7만 → ~114**(정합성 불변 — 여전히 전량 MERGE, 트랜잭션 경계만 묶음). **owned=True(자체 conn)에서만** 트랜잭션 관리 → conn 주입(통합 테스트·외부 호출)은 기존 autocommit 동작 그대로.
- **incremental**: `sync_graph(since=...)` 지정 시 각 관계형 SELECT 에 `updated_at > since` 증분 필터 → 변경분만 MERGE(변경 없는 cycle 은 거의 no-op, MERGE 실행 CPU·AGE 처리 절감). 워터마크는 `agent_runtime.kv`(신규 `get_sync_watermark`/`set_sync_watermark`, scope별, 실패 graceful→full 폴백). `synced_at`(서버 `now()`) 반환 → CLI 가 다음 since 로 저장. glossary_relations(created_at only)·삭제/파단 노드는 **full 이 담당**.
- **CLI/wrapper/cron**: `metadata_graph_sync.py` 에 `--incremental`/`--full`(+env `AGENT_METADATA_GRAPH_SYNC_INCREMENTAL`), wrapper `metadata-graph-sync.sh` 가 모든 인자 pass-through(기존 `--scope` 만 처리 → `"$@"`). cron 을 **30분 `--incremental`(변경분만) + 매일 04:17 `--full`(삭제/파단 정리)** 이중 스케줄로 전환.

**검증**: 신규 [test_metadata_graph_load_spread.py](../tests/test_metadata_graph_load_spread.py) **4**(since 증분 필터 유무, batched commit 발생, owned autocommit 복원) + units 10 회귀 PASS. AST OK. 통합(psycopg 필요)은 배포 후 — conn 주입 owned=False 경로가 기존과 동일함을 코드 대조로 확인(통합 테스트는 `autocommit=True` conn 주입).

**정합**: ANCHOR §1 "관계형은 SSOT, AGE 는 **재생성 가능한 투영**" — 투영을 더 효율적으로 재생성하는 변경(정합성·멱등 불변). feature-0002 REPORT TASK-0308(축①② insight/probe)와 동일 cycle.

### 관계 기반 배치 — graph-rel-layout (2026-07-03, worktree=feature-0016-graph-layout)

**문제**: 관계가 쌓일수록 그래프 뷰 가시성 저하(사용자 보고). 배치가 관계 무반영 — 스키마 클러스터
자연정렬 shelf-packing + 클러스터 내 테이블 자연정렬 masonry 라서 연결 노드가 흩어지고 엣지 장거리 교차 양산.

**수정** ([admin.js](../../feature-0003-agent-web-ui/src/static/admin.js) `_metaG6Build` pre-pass, ADR-012):
`_metaRelAdjacency`(REFERENCES→테이블 승격 인접행렬, 유사도 w=trusted 2·그 외 1) → ① `_metaRelSchemaOrder`
greedy seriation(연결 스키마 shelf 인접) ② `_metaRelTableOrder` 컴포넌트 BFS 군집(+외부앵커·고립 자연정렬)
③ `_metaRelOrderAll` barycenter 4-sweep(gpos=schemaIdx+로컬 rank) — 순서 입력만 교체, 결정론 grid·펼침-불변
(ADR-004 ②)·masonry/카드 게이팅 골격 불변. 관계 0 = 기존과 완전 동일, 관계 축적 시 rebuild 마다 관계 기준 수렴.

**검증**: Node 격리 8/8 PASS(회귀0·seriation·군집·상호교차 해소·결정론·벌크 감소·펼침-비의존) + 파라미터
벤치(시드 3 × 랜덤/허브: 2D 세그먼트 교차 12~30% 감소, 1D 층간 역전 59→52, SPAN=1 채택 근거) + node --check.
완료 게이트 = 배포 후 PB-0008 실 Windows 라이브 육안(TASK T38.8).

### 유사 속성 그룹 영역화 — graph-simgroups (2026-07-03, worktree=feature-0016-graph-simgroups)

**문제**: graph-rel-layout 후에도 "균일 칩 평면 나열"이라 군집이 영역으로 안 읽힘(사용자: 유사 속성끼리 +
범위 가시화 + 근본 개선). 게임 DB 는 구분자 없는 연접 테이블명·FK 부분 선언·role 부분 존재.

**수정** ([admin.js](../../feature-0003-agent-web-ui/src/static/admin.js), ADR-013): 3-신호 그룹핑(이름 affix
family 지원도×길이 → 관계 attach → 역할 → 기타) + 그룹 블록 렌더(배경 박스 틴트 8종 + 헤더 칩 `스템 · n`,
GB:/GH: 비상호작용 장식) + 그룹 내부 2-pass masonry·블록 shelf-pack(펼침-불변 배정, ADR-004 ② 계승) +
클러스터 상세 목록 동일 그룹 헤딩. ADR-012 순서 계층(seriation·barycenter)은 컨테이너=그룹으로 재사용.

**검증**: 실 _metaG6Build Node 구동(실측 gunzgame 68 테이블·145 관계) 격리 **25/25 PASS**(§18.8 수정 회귀방지 t10~t12 포함) — 그룹 무결성·bg
무겹침·칩 1-bg 포함·칩/펼침 무겹침·결정론·펼침-불변·평면 폴백·엣지 조립 보존·빌드 5.1ms. 그룹 산출:
character(14)·item(17)·characterinfo(4)·battletimereward…(4)·…shop(3)·mission(4)·clanmember(3) 등 13+기타.
완료 게이트 = 배포 후 PB-0008 실 Windows(TASK T42.8).
