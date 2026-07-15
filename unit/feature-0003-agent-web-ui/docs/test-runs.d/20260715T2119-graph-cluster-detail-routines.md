---
run_at: 2026-07-15T21:19:11+09:00
session: ai/claude/feature-0003-graph-cluster-detail-routines
scope: 스키마 클러스터 상세 패널이 함수·프로시저(Routine)만 있는 컨텐츠 카테고리를 목록에 표시하도록 — Table+Routine 병합집합으로 sim-group 계산 (20260715T2119-graph-cluster-detail-routines)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED
---

### Run 1 — 문법 검증 (Environment: node --check, ESM)
- 명령: `cp graph-ctxmenu.js <scratch>/graph-ctxmenu.mjs && node --check <scratch>/graph-ctxmenu.mjs`
- 결과 **PASS** — `graph-ctxmenu.js` ESM 문법 OK. 단일 파일 변경(50 insert / 17 delete).

### Run 2 — 정적·로직 검증 (Environment: 코드 리뷰 + 데이터흐름 추적)
- 진입점 2곳(`_metaGraphShowClusterDetailById`·`_metaGraphShowClusterDetailLocal`)이 `label === "Routine" && _metaCatParent(n.key,n.fqn)===comboId` 로 routine 수집 — build(`graph-core.js` L64~L78)가 Table+Routine 을 `g.tables` 에 함께 넣는 것과 동일 membership(`_metaSchemaComboOf(Routine)`==`_metaCatParent(...)`, graph-state.js L154-162).
- 렌더 `_metaGraphRenderClusterDetail(...,routines)`: `members = tables.concat(routines)` 를 `_metaSimGroups("panel:"+name, members, _metaRelAdjacency(map))` 에 투입 → Routine-only 컨텐츠 카테고리도 그룹 헤딩으로 방출.
- **회귀 방어 확인(Table-only 스키마)**: `routines=[]` → `members=tables`, `nRoutines=0` → 설명 `_rtnDesc=""`·섹션 제목 `테이블 (tblList.length)`·sim-group 입력=tables·rowHTML 테이블 분기 = 기존과 동일. `nTables`/`truncNote`/`totalOverride`/`childCols` 는 `tblList`(테이블) 기준 유지 → cap 절단 정확성 불변.
- **kind 필터(hiddenKinds) 정합(§18.8 적대 리뷰 MAJOR 반영)**: 두 수집 루프에 build(graph-core L74-75)와 동형 guard `!_metaGraph.hiddenKinds.has((routine_type==="function")?"function":"procedure")` — 사용자가 툴바 'ƒ 함수'/'⚙ 프로시저'를 숨기면 캔버스에서 빠진 routine 이 패널에서도 빠져 목록·개수·sim-group 이 계속 일치. status 라인·설명·목록 3자 동일 집합.
- **행 클릭**: `.amgr-ct-row[data-node-key]` → `_metaGraphShowDetail(key)` 는 `/api/admin/metadata/graph?node=<key>&depth=1` 조회형이라 routine 키에도 동작(`_metaGraphRenderDetail` 이 routine 파라미터 렌더 지원).
- **escape**: routine name·description·routine_type 전부 `esc()` 경유(rowHTML). Routine 아이콘/라벨은 `_metaRoutineIcon`/`_metaRoutineKo`(미상 routine_type → ⚙/프로시저 기본).
- 결과 **PASS(정적)** — correctness/회귀 결함 미발견. §18.8 적대 리뷰 결과는 REVIEW.md 참조.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **DEFERRED(배포 후 수행)**
- 대상: 정적 자산 baked 이미지(web-a/web-b) 재배포 후 서빙 자산 반영 확인 → win-browser.py 실 Windows Chrome relay 로 `https://localhost/admin` > 지식베이스 > 그래프 뷰.
- 확인 항목(예정):
  1. 함수·프로시저가 다수인 스키마 클러스터(예: gunzgame)를 상세 패널로 진입(combo 클릭 또는 카드) → 설명에 "함수·프로시저 M개" 노출, 섹션 제목 "테이블·함수·프로시저 (N)".
  2. **캔버스에는 보이나 기존 패널엔 없던 함수·프로시저-only 컨텐츠 카테고리**(예: "상점 아이템 명칭")가 상세 패널 목록에 그룹 헤딩 + 멤버(ƒ/⚙ 칩)로 표시.
  3. 캔버스 sim-group 과 패널 컨텐츠 카테고리 목록 일치.
  4. routine 행 클릭 → 해당 함수·프로시저 노드 상세(파라미터 등) 조회.
  5. Table-only 스키마 상세는 회귀 0(기존 목록 동일), pageerror 0.
- visual_verification_scope: always (§10.5 web/UI 완료 게이트) — 배포 후 충족 예정. 미수행 사유: 정적 자산이 이미지 baked 라 web 재배포(외부 영향 행동, confirm) 후에만 서빙 반영.
