# Report

## 2026-07-13 · 그래프 뷰 미니맵 — 줌인 컬링이 전역 개요를 바꾸던 결함 수정 (graph-minimap-fullview, §77)

### 요청 (사용자)
줌 인 시 그래프 뷰 내부의 뷰포트 컬링(방출 제한)은 확인되나, **미니맵에도 그 컬링이 적용돼 전역적으로 보여야 할 미니맵 구성이 바뀐다** — §74 에서 "전체 이미지 캐싱·재사용"을 요청했지만 현재는 컬링된 그래프 이미지가 사용됨.

### 진단 (기전 2개)
- ① §74 재사용 게이트의 기하 서명(`_miniGeomSig`)이 **컬링된 방출 데이터(_built)** 기준 — 줌인 rebuild 마다 컬링 구성이 달라져 서명이 변하고, 게이트가 열려 G6 v5 minimap 이 **컬링된 부분집합을 재복제**.
- ② plugin `onTransform`(AFTER_TRANSFORM 32ms)의 `setCamera()` 가 미니맵 카메라를 메인 캔버스 `getBounds("elements")` — 컬링 중엔 부분집합 bounds — 에 재적합. 이미지를 지켜도 **카메라가 부분 영역으로 줌인**(vendor 역공학 실측).

### 처리 결과 (frontend-only, graph-core.js)
- build 가 뷰포트 사유로 방출을 실제 누락했는지 추적하는 `_metaGraph._cullPartial` 신설(4 컬 지점 마킹 + 리셋 2곳). `_cullActive`(판정 활성)와 직교.
- **전체-기하 서명** `_miniFullSig`(§76 nodePosAll — 컬링 무관 전 노드 — 기반, build 마다 산정)로 미니맵 보유 이미지의 '현재성' 판정 — boolean 마킹은 접힘 카드 시점 이미지를 펼침 후에도 현재로 오인(라이브 적발 ②).
- `renderMinimap` 게이트: 부분방출 + 전체 이미지 보유 시 재복제 skip(stale 여도 부분 재복제 금지 — 교체는 시딩이 담당). 무컬링 렌더에서만 서명 마킹. 미보유 시 원본 폴백(빈 미니맵·동결 방지).
- `setCamera` 동일 게이트 래핑: 컬링 중 부분 bounds 재적합 차단(두 번째 기전) — 전체 bounds 카메라 유지, 마스크는 요소 bounds 비의존이라 전체 이미지 위 현 뷰포트 위치를 계속 정확 표시.
- **컬링-유예 시딩 build**(`_metaMinimapSeedKick`): fit 이 판독 하한(0.55)으로 클램프되는 대형 모델은 무컬링 build 가 자연 미발생(라이브 적발 ① — 1,249 노드 fit 방출 153)이라 전체 이미지를 1회 전량-방출 build 로 시딩(비용 = pre-§65 빌드 1프레임)·stale 시 재시딩. 시딩-마킹 debounce 경합(라이브 적발 ③ — latch 고착)은 래퍼 stale-skip 분기의 force 재-kick 으로 상호작용 소강 시점 수렴.
- 트레이드오프: 줌인(컬링) 중의 구조 변경은 미니맵에 즉시가 아니라 **~0.5s 내 시딩 build** 로 반영(전량 방출 1프레임 비용) — 전역 개요 정합(사용자 요구) 우선.

### 검증
`test_g6build_minimap_reuse.js` **65 PASS**(Section E 서명 의미론 + F1~F9 시딩·stale 재시딩·경합 수렴 — 라이브 적발 3건 headless 재현·잠금) + 그래프 headless 11 스위트 **279 PASS / 0 FAIL** + `node --check` PASS. graph-split(ITEM-09) 후 headless 번들 실행 레시피 확립. **PRE-LANDING PB-0008 win-browser 라이브 PASS**: qa-idc 1,249 노드 시딩 수렴 → **줌 2.0 컬링 rebuild(방출 1,573→153)에 미니맵 toDataURL 해시 완전 불변** → 팬 불변 → 스코프 전환 재렌더(동결 없음) → pageerror 0 (test-runs.d fragment·스크린샷 2매). POST-DEPLOY 재확인 T77.5 잔여.
## 2026-07-13 · 카테고리 밴드 '컨텐츠 단위' 그룹핑 실동작화 (content-cluster, TASK 20260713T1059 / ADR-20260713T105932)

### 요청 (사용자)
`그래프 뷰`에서 'AI 능동 분석' 후(`mssql-qa-idc.cc_data_main`) '제품 카테고리 밴드'가 일부만 컨텐츠 단위로 묶이고
대부분(특히 함수·프로시저)은 단순 명칭 구분 — 분석 현황·문제 파악 + 컨텐츠 단위로 묶이도록 개선.

### 진단 (라이브 실측 2026-07-13, mssql-06656002eda6/cc_data_main)
- **RC1 numpy 부재(BLOCKING)**: insight-worker 이미지에 numpy 미설치 → `_cluster_edges` 가 ImportError 를 삼키고 빈 엣지 반환 → **전 시스템 semantic_cluster 0건**(cadence kv 마크 20 scope 정상·error=None — 조용한 무산). 시그니처·임베딩은 16k+ 전량 완료 상태였음.
- **RC2 ds-전역 N 가드**: 클러스터 단위가 (scope,ds) 전역이라 본 ds(N=7,055) > FULLMATRIX_MAX_N(2,000) 통째 skip — 표시 단위(스키마=DB 클러스터 내부 sim-group)와 계산 단위 불일치.
- **RC3 루틴 미편입**: cc_data_main 루틴 300 > 테이블 255 인데 routine_objects 에 시그니처/클러스터 컬럼 자체가 없고 role 분류도 Table 전용 → 함수·프로시저는 `nm:` 이름 affix 그룹만.
- **RC4 분석문 미연결**: 능동 분석 done(Table 466·Routine 477, 내용 풍부)이 그룹핑 신호에 미사용 — 테이블 설명 0/255 라 시그니처가 이름+컬럼뿐, 분석을 돌려도 밴드 불변.
- **RC5 라벨**: 서버/프론트 라벨 모두 이름 접두/접미 스템 — 묶여도 컨텐츠로 안 읽힘.

### 처리 결과 (backend-only — 프론트 변경 0)
- numpy requirements 추가 + `_cluster_edges` 부재 시 1회 WARNING(fail-loud).
- `run_semantic_cluster_pass` → **DB(effective schema) 단위 분할**(N 가드 국소화·pass-전역 결정 id) + **루틴 합동 클러스터**(alembic 0040 additive: signature_text_hash/semantic_cluster_id/label + 인덱스 2) — 루틴 시그니처 = 이름+type+params+returns+**touches(참조 테이블 read/write)**+분석문.
- **분석문 시그니처 주입**: node_analysis 최신 done 의 summary+usage(≤400자) — 'AI 능동 분석 → 재임베딩 → 재클러스터' 인과 성립. analysis 줄은 비어있지 않을 때만 append(미분석 해시 byte-불변 → 재임베딩 blast-radius 를 분석 보유분으로 한정).
- **LLM 컨텐츠 라벨**: `llm_cluster_label`(product_classify 동형·JSON-only·untrusted-data 가드) — 멤버 이름+분석 요약로 클러스터당 한국어 명(≤32자), kv 멤버셋-해시 캐시(불변 시 재호출 0)·fail-soft affix 폴백·`AGENT_METADATA_CLUSTER_LABEL_LLM` 게이트(기본 ON).
- 그래프 투영: `sync_routine` cluster props(_UNSET 보존) + `_step_routines` 확장 SELECT(0040 미적용 창 폴백) + `schema_tables` Routine RETURN 에 cluster 필드 — 프론트 ingest(generic)·`_metaSimGroups`(be: 판정이 g.tables=테이블+루틴 전체) 가 무변경으로 소비.
- **chaining 방어(라이브 프로브 적발·수정)**: base τ 단일연결이 DB 전체를 단일 blob(254/255)으로 만들던 것을 mutual-kNN + cap(40) 초과 τ-상승 재분할로 해소 — 재프로브(롤백) cc_data_main **37 클러스터**('buff' 24·'monsterclass' 11·'monsterspawnpoint' 7 등 컨텐츠 응집·총 199/255), ds 전체 1,016 클러스터/74 스키마/skip 0. + non-autocommit conn SAVEPOINT 격리, migrate-lint MAX_MIGRATION.txt 오탐 수정.

### 검증
- 신규 `test_semantic_cluster_content.py` 16 PASS + 전체 스위트 컨테이너 pytest **EXIT=0**(전건 PASS). 상세: `test-runs.d/TASK-20260713T105932-content-cluster.md`.
- §18.8 적대 패널 → REVIEW.md REV entry. POST-DEPLOY: 마이그 0040 → worker/web 재빌드 → cc_data_main 표적 백필+클러스터 pass → DB 카운트 실증 → PB-0008 실 Windows 육안(AC-1 be: 밴드 ≥5·컨텐츠 라벨 / AC-2 루틴↔테이블 동반 배치).

## 2026-07-10 · 그래프 뷰 미니맵 — 구성 불변 시 전체-이미지 재사용 (graph-minimap-reuse, §74/ADR-036, 머지 재번호 §70→§73→§74·ADR-034→ADR-036 §13.1)

### 요청 (사용자)
`그래프 뷰` 의 **미니맵 최적화** — "화면 구성이 갱신되었을 경우, 한 번 draw한 전체 이미지를 재사용하는 방식도 고려."

### 진단
G6 v5 minimap 플러그인(vendor `g6.min.js` 클래스 `tZ`)의 이벤트 바인딩을 번들 역공학으로 실측:
- **팬/줌** → `AFTER_TRANSFORM → onTransform`(throttle 32ms) → `updateMask()`+`setCamera()` **만** — 전체 이미지 재복제 **없음**(이미 최적, 사용자 요구의 팬/줌 부분은 G6 가 이미 충족).
- **draw/render** → `AFTER_DRAW`/`AFTER_RENDER`/`AFTER_ANIMATE → renderMinimap()` → `setShapes` 가 **전 요소 key-shape 를 `cloneNode` 로 전량 재복제**.

낭비 지점: 이 앱은 `_metaG6Apply`(=`setData`+`draw()`)를 **선택·상대하이라이트·역할도착(2.5s 폴 승격, AI 분석 중 지속)·busy 등 상태-only 변경으로도 20+ 지점에서 자주** 돈다. 매 `draw()` 의 `AFTER_DRAW` 가 미니맵을 전량 재복제 — 미니맵이 그리는 **기하가 동일한데도** 수백~수천 노드를 매번 clone. 이게 유일한 남은 재복제 낭비.

### 처리 결과 (frontend-only, admin.js)
- **기하 서명** `_metaMinimapGeomSig(built)` — 미니맵이 depiction 하는 기하(요소 id·부모combo·위치 x/y·크기·엣지 끝점)만 FNV-1a 해시. **시각상태(states/fill/opacity/역할 칩 색) 제외** — 미니맵 스케일서 색은 무의미하고, 사용자 요구가 곧 "구성(기하) 불변이면 재사용." 위치 0.25px 양자화 + `nodes:combos:edges:hash` 프리픽스.
- **플러그인 래핑** `_metaPatchMinimapReuse(graph)` — minimap 인스턴스의 `renderMinimap` 을 1회 래핑(멱등). 서명이 직전 렌더와 같고 캔버스 존재면 skip(이미 그려둔 이미지 재사용), 다르면 원본 render. `_metaG6ApplyOnce` 가 `setData` 직전 같은 built 로 `_miniGeomSig` 세팅. 플러그인에 `key:"minimap"` 부여. 실패 시 no-op → 원본 동작(정확성 보존).
- **호출 시점 = 첫 draw 이후**(적대 리뷰 H1 발견·수정): G6 v5 는 `context.plugin` 을 생성자가 아니라 첫 `draw()` 의 `initRuntime()` 에서 lazy 생성 → init 직후 호출은 patch no-op(최적화 사멸)였다. `await g.draw()` 직후 멱등 호출로 이동해 plugin 존재 시점에 래핑.
- **네이티브 드래그 stale 수정**(적대 리뷰 H2, BLOCK→수정): 노드/콤보 드래그는 `_metaG6Apply` 를 안 거치고 `element.draw({stage:"translate"})` 로 요소를 직접 이동하는데 이것도 `AFTER_DRAW`(stage:"translate")를 발생시켜 renderMinimap 을 부른다 → stale 서명으로 skip → 미니맵이 드래그를 반영 못 하고 얼어붙던 회귀. `graph.on("afterdraw")` 에서 `stage==="translate"` 시 `_miniGeomSig=null` 무효화 → 재복제 폴백으로 해소(node·combo 단일 지점 커버).
- **효과**: 상태-only rebuild(선택/역할도착/busy)는 미니맵 재복제 skip → 이미 그려둔 전체 이미지 재사용. 구성 변경(펼침/접기/드래그/LOD/스코프전환/검색)은 서명 변경 → 정상 재복제. 팬/줌은 원래대로 마스크만 갱신.
- cache-buster (머지 후) `admin.js?v=20260710-mmreuse-layoutmemo`(graph-colnav·layoutmemo 병렬 머지와 결합).

### 검증
- 신규 headless `test_g6build_minimap_reuse.js` **35 PASS**(A 기하 서명 11 + B 실 build 4 + C 패치 10 + **D 드래그 무효화 10**).
- 회귀 **150 PASS**(collod 20·agglod 8·category 26·edge 71·viewportcull 6·vpack 19) · `node --check admin.js` PASS.
- 적대 리뷰가 2건 BLOCK 결함 적발 → 수정: **H1** 패치를 init 시점 호출해 plugin lazy-init 전이라 no-op(최적화 사멸), **H2** 네이티브 드래그가 stale 서명으로 미니맵 재복제 skip(드래그 반영 못 함). 둘 다 수정·테스트 커버. POST-DEPLOY win-browser 실 Windows Chrome 육안(feature-0003 TEST §74 — 미니맵 렌더·뷰포트 추종·상태변경 후 안정·**드래그 반영**·구성변경 반영·pageerror 0).

### 트레이드오프 (사용자 요구와 정합)
역할 칩 색·선택 하이라이트·dim 은 미니맵에 즉시 안 뜨고 **다음 기하 변경 때** 반영 — 미니맵 168×112px 스케일서 색은 시각적으로 무의미하며, 사용자가 명시 요청한 "구성 불변 시 전체-이미지 재사용" 의 본질.

## 2026-07-10 · 그래프 뷰 상세 — 사용(참조) 관계를 읽기/쓰기 그룹으로 분리 (graph-rw-group)

### 요청 (사용자)
`그래프 뷰 > 상세` 에서, 참조 관계를 읽기/쓰기 당 그룹으로 구분하여 목록을 출력.

### 해석 (grounding)
그래프 상세 카드에서 **읽기/쓰기 의미(`relation_type`)를 갖는 관계는 `ROUTINE_USES`(루틴↔테이블 사용)
관계뿐**이다 — REFERENCES(FK/추정 참조)는 참조함(→)/참조받음(←) 방향만 있고 read/write 개념이 없다.
따라서 "사용 테이블"(Routine 상세) / "사용하는 함수·프로시저"(Table 상세) 섹션이 대상. 기존은 **평면 목록에
항목별 `읽기`/`쓰기` muted 꼬리표**만 붙여 흐름 구분이 눈에 안 들어왔다.

### 처리 결과 (frontend-only, admin.js `_metaGraphRenderDetail`)
[admin.js](../../feature-0003-agent-web-ui/src/static/admin.js) ROUTINE_USES 섹션을 `relation_type` 기준
**읽기 그룹 / 쓰기 그룹**으로 분리. 각 그룹은 REFERENCES 방향 그룹(`dirGroup`)과 동일한 `amgr-dir` /
`amgr-dir-head` 스타일을 재사용해 헤더(라벨 + 개수)로 묶는다. 섹션 헤더에 `· 읽기 N · 쓰기 M` 요약 배지 +
안내문 추가. 분류 규칙은 기존 per-item `kindKo` 와 동일(`"write"`=쓰기=루틴→테이블, 그 외 `"read"`·미상=
읽기=테이블→루틴 — 정합 유지). 항목별 꼬리표는 그룹 헤더로 대체돼 제거. 각 그룹 30건 상한 + 초과분
`… 외 N건` 명시(기존 combined 30 **무음 절단** 개선). 행 `data-rtuse` 클릭→대상 상세 바인딩 무손상.
cache-buster `admin.js?v=20260710-graph-rw-group`.

### 검증
- `node --check admin.js` PASS · 재사용 CSS 클래스(`amgr-dir`/`amgr-dir-head`/`amgr-row amgr-plain`/
  `amgr-list`/`admin-meta-detail-note`) 전부 styles.css 존재 확인 · `[data-rtuse]` 클릭 바인딩(L7983) 유지.
- 데이터·거동 무변경(순수 UI 재구성) — REFERENCES/컬럼/용어/AI 분석 섹션·`_metaGraphShowRelations`(관계 상세)
  미변경. 관계 상세 패널의 방향 그룹핑은 별개 관심사(read/write 미노출)라 scope 밖.
- 라이브 브라우저(PB-0008) 시각 검증은 배포 시 동반 권장.
## 2026-07-10 · 상세 패널 "🎯 이 노드로 이동" 카메라 버튼 (graph-focus-selected)

### 요청 (사용자)
`그래프 뷰 > 상세`에서, 선택한 노드로 카메라를 이동시키는 버튼을 구성. **UI 구성이 망가지면 안 됨.**

### 진단 (코드 실측)
노드 단일클릭 → 상세 패널(`<aside id=metadataGraphDetail>`)은 갱신되나 카메라는 이동하지 않음
(`_metaGraphShowDetail` → `_metaGraphSetSelected`, focus/pan 호출 없음). 큰 그래프에서 선택 노드를 화면에서
다시 찾기 어려운 빈틈. 반면 카메라-전용 팬 기계장치는 이미 완비(`_metaGraphAnimateFocus` — 구조·선택 불변,
뷰포트 중앙 tween + 판독 줌 클램프; 관계 행 클릭용 래퍼 `_metaGraphPanToRelation` 이 선례).

### 처리 결과 (frontend-only, admin.js + admin.html)
상세 카드 헤더(`_metaGraphRenderDetail`) `🔗 관계 상세` 옆에 `🎯 이 노드로 이동`(`metaGraphFocusSelBtn`) 추가.
클릭 → `_metaGraphAnimateFocus(self.key, _metaGraph._opSeq)`. 미렌더 노드는 `_metaRenderedIdFor` null 가드로
안내만. **"상세"는 이 UI에서 유일하게 `상세 ⇆` 토글 + 상세 패널로 명명된 표면**이라 요청("상세에서 선택 노드로")에
가장 정합. UI 안전: `.amgr-link`(margin-left:auto)가 2개 될 때의 auto-마진 분할을 신규 버튼 `margin-left:0`로 회피
(기존 관계 상세 버튼만 우측 정렬, 신규는 gap:8px로 그 옆 그룹화). 캐시버스터 `admin.js?v=20260710-graph-focus-selected`.

### 검증
`node --check admin.js` PASS · diff 적대 리뷰(REV-20260710T063659) · **PB-0008 win-browser 는 POST-DEPLOY**
(정적 자산 baked → merge + deploy-web 선행). 배포 후: 그래프 로그인 → 노드 클릭 → 상세 패널에 버튼 노출 →
클릭 시 선택 노드가 뷰포트 중앙으로 팬 + 상태줄 "→ … 로 카메라 이동" + pageerror 0 육안 확인 예정.

### 남은 리스크·후속
없음(순수 추가). 후속: POST-DEPLOY win-browser 육안 PASS 를 TEST §3 에 append.

---

## 2026-07-10 · 상대 하이라이트 시 focus 밖 관계선 제거 — 유령 관계선·성능 낭비 해소 (hl-edge-hide, TASK §66)

### 요청 (사용자 리포트)
그래프 뷰에서 특정 노드 클릭 → 상대 하이라이트 진입 시 '출력되지 않아야 할 관계선'이 투명하게 렌더되고,
마우스 이동에 따라 상태가 바뀜(하이라이트 미적용 시점의 관계선 위치 잔상으로 추정). 성능 손해 검토 후 대응.

### 진단 (코드 전수 + G6 vendor 번들 실측)
- **'투명한 관계선'**: 상대 하이라이트 시 non-focus 엣지를 `dimIf` 가 **제거하지 않고 opacity/strokeOpacity
  0.12 로 침강만** 시킴(§57.6 의도된 dim). 코드 레벨에서 실재 확인 — 버그가 아닌 설계 동작.
- **'stale 위치 + 마우스 이동 시 변화'**: G6 v5 기본 `enableDirtyRectangleRendering:true`(vendor 번들 실측,
  admin.js 어디에도 override 없음)의 dirty-rectangle 잔상. dim 전환(opacity 1→0.12) + 엣지 라벨 제거 시 이전
  원색 엣지 픽셀이 부분 재도색으로 미소거 → 마우스 pointer 이벤트가 영역 재도색 시 flicker. 단일 클릭은 그래프
  구조 불변(노드/엣지 위치 동일)이라 잔상은 레이아웃 변화가 아닌 canvas 렌더 아티팩트로 확정. LEARNINGS/git 이력에
  선행 진단 없던 신규 이슈(§57.7~57.9 하이라이트 작업은 전부 dim 상태 정합만 다룸).

### 성능 판정 (사용자 핵심 질문) — 손해 있음
non-focus 엣지가 거의 비가시(0.12)인데 전량 살아 있어 G6 가 path 지오메트리·quadtree hit-test·매 재도색
페인트를 지속(대형 스코프 수백~수천 엣지에서 순수 낭비) + 잔상 재도색 churn. 대상이 비가시 + 사용자 미희망이라
낭비 성격이 명확.

### 처리 결과 (frontend-only, admin.js — 사용자 결정: 제거(hide))
[admin.js](../../feature-0003-agent-web-ui/src/static/admin.js) `_metaG6Build` 에 `hlHide=(hl)=>!!(fa&&!hl)`
도입 + 4개 keep 판정 지점(SCHEMA_REF·ROUTINE_USES·기타 관계·REFERENCES)에서 상대 하이라이트 활성 시 non-focus
엣지를 build 에서 제외(colLevel·집계 agg 공통 — 같은 (rs,rt)로 승격된 쌍은 동일 keep 이라 keep 판정 지점에서
colLevel push·agg 누적 동시 차단). 잔상 원천 제거 + hit-test/페인트 비용 감축 + 사용자 기대 일치. 노드
dim(0.38, `_metaBakeBaseOpacity`)은 유지 → focus 부분그래프 강조 효과 보존. lodDropped(줌아웃 축약 전용)는
미증가('줌아웃 축약' 오안내 방지). dimIf 의 dim 분기는 방어적 안전망으로 잔존(향후 push site 누락 시 fail-soft).
cache-buster `admin.js?v=20260710-hl-edge-hide`.

### 검증
- headless `test_g6build_edge_visibility.js` **71 PASS**(T4/T10/T13 을 '제거' 단언으로 전환 + §66 불변식:
  focus 밖 엣지 전제거·lit 부분그래프 방출·무선택 전량 방출 대조군·하이라이트-hide lodDropped 미증가 + T13B
  highlight×LOD; **§64 lod-hl-declutter 의 T22 도 병존 PASS** — hlHide 가 LOD 선행이라 줌아웃 declutter 와 정합)
  + 회귀 0(agglod 9·category 26·collod 20·vpack 19·viewportcull 6) · `node --check` PASS.
- fa=null(무선택) 경로는 hlHide 항상 false → 기존 전체 표시·LOD 동작 완전 보존(회귀 표면 없음).
- **§64(lod-hl-declutter)·§65(viewport-cull) 병렬 머지와 rebase 합류**: §64 는 줌아웃 전용 LOD 예외를 self-직접선으로
  좁히고(keepLod/litSelf), 본 §66 은 전 줌 레벨에서 focus 밖 엣지를 build 제외 — 상보. 결합 코드로 전 headless 재검증(위 회귀 0).

### 잔여
- **POST-DEPLOY 사용자 육안 (PB-0008 실 Windows, visual — 무인 도달 차단)**: 노드 클릭 → focus 밖 관계선 완전
  소거·마우스 이동 시 유령 관계선/깜빡임 없음·focus(선택+1-hop) 관계선 선명 유지. 배포(web 정적 자산 baked,
  deploy_scope: included).
- 픽셀 레벨 dirty-rect 잔상 최종 확증은 PB-0008 라이브에서만(WSL headless 는 canvas paint 아티팩트 미재현).

## 2026-07-09 · 스키마 펼침 세로 폭주 해소 (graph-vpack, TASK §60, ADR-028)

### 요청 (사용자 리포트)
관리 콘솔 > 지식베이스 > 그래프 뷰에서 스키마 노드를 펼치면 '스키마 클러스터'가 너무 세로로 펼쳐지고,
여러 스키마 노드를 펼치면 알아보기 힘든 화면이 된다. 원인 상세 파악 + 높은 가시성 확보.
추가 제약: 성질이 다른 노드·클러스터가 겹치지 않아야 한다. 사용자 선택 범위: 전체(컬럼 재분배 포함).

### 근본 원인 (코드 전수 추적 — _metaG6Build 레이아웃)
레이아웃이 "폭=고정 상한, 높이=무한 증가" 철학. ① 전역 shelf 폭 `MAXROWW=2400` 고정 → 여러 클러스터가
높아져도 폭은 고정된 채 shelf 행만 세로로 쌓임(전체 높이 = Σ 행 높이, 무한 증가) ② 클러스터 내부 열
`innerColsFor` 최대 4열 캡 → 테이블 많은 스키마(~8,122 T/21 DS)가 세로로 길어짐 ③ 열 배정을 collapsed
높이로 고정(펼침-불변, ADR-004 ②)해 펼친 테이블 열만 홀로 세로 폭주 ④ 제품 카테고리 밴드 세로 스택이
가중. `fitView` 는 종횡비를 그대로 두고 축소만 해 세로 콘텐츠는 얇은 세로 슬라이버(리포트의 증상).

### 처리 결과 (정본 ADR-028 · admin.js frontend-only)
- **① 적응형 shelf 폭**: `MAXROWW=max(2400, maxClusterW, round(sqrt(총콘텐츠면적×2.0)))` — 많이 펼칠수록
  가로로 퍼져 높이 억제. floor 2400(소량 펼침 현행 보존)·maxClusterW(가장 넓은 클러스터는 자기 행에 —
  클러스터 간 겹침 방지). 3개 shelf-pack 경로(비카테고리·카테고리 밴드·미분류) 공통 적용.
- **② 실높이 기반 열 수**: `colsForHeights=clamp(round(sqrt(ΣrealH/100)),1,cap)`(cap flat 10·group 4).
  펼친 컬럼 반영 → 큰/펼친 스키마는 넓고 낮게, ≤4T 는 1열 유지. 구 innerColsFor/gInnerColsFor/assignH 폐지.
- **③ 실높이 balance 재분배**: 열 배정을 realH 최단 열 단일 패스로(ADR-004 ② 재선회). 펼친 테이블 열이
  형제를 덜 받아 넓고 낮게. 대가로 펼침 시 형제 재배치(약간의 churn) 수용 — 사용자 우선순위 정합.
- **비겹침 불변식 보존**: 열 COLW(224) 간격 + realH push-down + 클러스터 (w,h)=실 bbox → shelf-packer 소비.
  세 규칙 유지로 노드·클러스터 pairwise 비겹침 성립.

### 검증
- §60 headless `test_g6build_vpack.js` **16 PASS**(열>4·1열 보존·컬럼펼침 재분배·적응형 폭 W>2400·노드
  겹침0·클러스터 겹침0·극단 1T×100컬럼 겹침0·카테고리 밴드 세로분리+겹침0·routine 파라미터 펼침 겹침0)
  + 기존 headless(edge-visibility 54 / category 26) 회귀 0 · node --check PASS · 순수-수학 sim 겹침 0(pairwise)
  + before/after 종횡비.
- §18.8 적대 리뷰 패널(SUBAGENT, ux/layout): PASS-WITH-FIXES — R1·R2 구조적 충족·correctness/겹침 BLOCKING 0.
  MINOR(빈 열 폭)·MAJOR 주석 정직화(churn 43~100% 실측)·NIT(테스트 흡수) 반영. 상세 REVIEW.md.
- 실 _metaG6Build before/after: 단일 12T×15컬럼 896→391 높이(56%↓, aspect 0.42→2.10) · 16스키마×40T
  4372→2124(51%↓, 0.41→1.77) · 24스키마×60T 9380→3800(59%↓, aspect 0.19→**1.22**, 세로 띠→landscape).
- POST-DEPLOY 실브라우저(PB-0008) 1차(배포 d5cf0fec): 라이브 5스키마 펼침 — 노드 겹침0·클러스터 겹침0(2618
  노드) 확인. 단 per-cluster 실측이 **simGroups 경로 스키마(cc_* 557T) 822×10272 aspect 0.08 세로폭주 잔존**을
  포착 → 아래 §60.2 로 근본 수정(라이브 검증이 초기 수정의 gap 을 잡아낸 사례).

### §60.2 follow-up — simGroups 경로 세로폭주 해소 (PB-0008 회귀, T60.7)
- 원인: 초기 수정은 flat masonry + 전역 shelf 폭만 적응화 — 그룹 블록 행 폭 `TRW`(고정 4열 상당 ≈938)는
  그대로라 그룹 많은 스키마에서 그룹 행이 세로 스택.
- 수정: ① `TRW` 를 총 블록 면적 기반 적응(`max(TRW, round(sqrt(ΣblockArea×2.0)))`) ② packGroup 열 상한 4→6.
- 검증: headless T9(simGroups landscape) 추가 → §60 **19 PASS** + 회귀 54+26 · 실측 557T/20그룹
  822×7406(0.11)→2690×2544(**1.06**, 66%↓)·557T/4그룹 0.13→1.18. 캐시버스터 20260709-graph-vpack2.
- **POST-DEPLOY 2차 PB-0008 라이브 PASS(배포 ec74a16b)**: mssql-qa-idc 5스키마 펼침 실측 — cc_bonedragon
  557T 822×10272(0.08)→**3590×3320(1.08)**(높이 68%↓)·전 클러스터 landscape·전역 aspect 0.57→**0.99**·노드/
  클러스터 겹침 0·pageerror 0. 미니맵이 얇은 세로 띠 → 2D landscape 블록. **사용자 리포트 라이브 해소 확인.**

## 2026-07-07 · 제품 카테고리 + 크로스-DB 관계 + 재귀 분석 refine (graph-category-recursive-refine, TASK §55, ADR-021)

### 요청 (사용자 4대 — REQ-20260706-graph-category-recursive-refine)
① 데이터소스 선택 시 스키마 클러스터의 명칭순 평면 나열 → 제품(Products)·DB 매핑 기반 **카테고리 단위 구분·배치**
(하위 '유사 속성 그룹' 같은 가시적 구분) ② 스키마 클러스터 내부에 갇힌 'AI 능동 분석'·관계 → **다른 DB 간** 분석/
연결 구축 ③ DB 단위 분석 시 하위 전 노드(테이블·컬럼·함수·프로시저)+관련 노드 **재귀** 분석, 빈약 노드 **후속 보충**,
모든 분석 **override 아닌 refine** ④ ADR-013 후속(Phase C) 정합 검토 + 잔여 후속.

### 처리 결과 (정본 ADR-021 · 마이그 0038 비파괴)
- **A 카테고리**: `WebProductDatabases`(제품별 접근 DB SSOT) 질의시점 합성(`schema_products`) + 그래프 뷰
  **제품 카테고리 밴드**(CAT 배경/🗂 헤더/접기 — 밴드별 shelf-pack·헤더 드래그=밴드 이동·§49 순서 안정화·
  검색 강제펼침·미분류 후미). 매핑 전무 datasource 는 기존 배치 그대로(회귀 0).
- **B 크로스-DB**: 임베딩 추론을 **같은 DS 다른 DB(xschema, 기본 ON — 프로브 검증 가능)** + 크로스-DS 로 일반화,
  MSSQL 3-part `[db].[dbo].[t]` 프로브(레거시 dbo 가드)·fetch 4-분기 필터, **관계 수동 큐레이션**(관계 상세 행
  ✓신뢰/✕파단 → SSOT+AGE 동시 정합 — 크로스-DS 영구 candidate dead-end 해소), XDS 데몬 flip(ADR-019 이행).
- **C 재귀·refine**: DB 단위 분석이 시드(테이블+루틴) depth0 + **per-seed 앵커**로 직계 컬럼·관련 노드 재귀 전개
  (예산 planned×12, cap 2,500) · 모든 재분석에 이전 분석문 동봉+**융합(refine) 프롬프트 계약** · 빈약(thin) 선행
  노드는 후속 발견(related_findings)으로 **back-refine**(run 당 30 캡) · LLM 확신 조인 후보(suggested_links)를
  3중 환각 가드 통과 시 candidate 적재(기존 프로브·자기교정이 후속 판정). 0038 미적용 창 전 지점 legacy 폴백.
- **D Phase C 정합**: 시그니처 백필 정체(3% = 497/16,023, `updated_at DESC LIMIT` 미처리-비우선) 근본수정 —
  미처리 우선 정렬+remaining 로그+배치 500(~8h 소진). 클러스터 채워지면 sim-group `be:`·경계 추론이 실동작 전환.

### 검증
- 단위: 신규 §55 테스트 29 + curate 4 + 계약 갱신 2 + 헤드리스 카테고리 26/26(하네스 repo 영속화) —
  **전체 스위트(0002+0003) 컨테이너 pytest EXIT=0·FAILED 0**. migrate-lint(0038) expand-safe.
- §18.8 적대 패널(ultracode 4렌즈 + 2-refuter, 한도 중단분은 main 직접 재검증): **BLOCKING 2·MAJOR 4·MINOR 3
  전건 수정**(fetch 4-분기·kNN recall 초과-fetch·zFor CAT·접힘 밴드 드래그 차단·curate 레거시 매칭·refine 실패
  done 복원·transient probe 미캐시·모호 alias·scope 한정) + 수용 1. REV-20260707T100744.

### 잔여
- 배포(deploy_scope: included): PR → 머지 → `make migrate`(0038) → web 롤링 + insight/ask-worker 재빌드 →
  **PB-0008 실 Windows POST-DEPLOY**(카테고리 밴드 렌더·접기/드래그·관계 큐레이션 버튼·DB 단위 분석 재귀 확장 확인).
- eventual(수 시간~일): 시그니처 백필 소진 → 의미 클러스터·xschema/xds 후보 발굴 가동(로그 관측 항목).


## 2026-07-04 · 그래프 뷰 3대 UX 개선 (graph-ux3fix, TASK §45)

### 요청 (사용자)
`관리 콘솔 > 지식베이스 > 메타데이터 > 그래프 뷰` 3건: ① 그래프 뷰를 `지식베이스 > 그래프 뷰` 최상위 탭으로 분리(높이 확장) ② 노드 더블클릭 시 전체 재배치 수정(드래그 노드 보존·비조작 노드 우선 밀림) ③ [테이블·컬럼·용어] 검색 시 너비 증가 → 부드러운 하이라이트.

### 처리 결과 (frontend-only, admin.html/js/styles.css)
- **① 완료** — 그래프 뷰가 독립 최상위 탭(`data-admin-pane="graph"`)으로 분리. 자체 pane-head + 데이터소스 select, 서브탭 바 제거로 캔버스가 pane 전체 높이 사용. 권한(`ADMIN_TAB_PERMISSIONS.graph`)·스코프 동기화(`loadedScope` 크로스탭 stale 봉인) 포함.
- **③ 완료** — 검색 매칭 표현을 노드 너비 증가에서 **앰버 soft glow(`node.state.match`)** 로 전환(테이블·컬럼·용어). 폭 고정(rel-무관)으로 setData 재packing·가시성 저하 제거, 라벨 박스 클램프.
- **② 되돌림(후속)** — 1차 접근(클러스터 원점 sticky)이 §18.8 적대 리뷰에서 **회귀 확정**(카드→combo 확장 시 이웃 겹침, 다중 스키마 확장 불가). 요구②의 정합 구현 = 충돌 해소 레이아웃(정교한 엔진 대변경, 라이브 반복 검증 필요) → **사용자 결정으로 ①·③ 먼저, ②는 라이브 후속 cycle**.

### 검증·미결
- `node --check` PASS · §18.8 3-렌즈 적대 리뷰(레이아웃·IA·검색, REV-20260704T014646) 확정결함 3건 반영.
- **미결(하드 게이트)**: PB-0008 실 Windows 시각검증(visual_verification_scope: always) 무인 미수행 → **사용자 육안 확인 후 main 병합·web 롤링 배포**(cache-buster `20260704-graph-ux3fix`). ② 후속 cycle.
## 2026-07-04 · 그래프 뷰 UX 7건 (graphux7, TASK §51)

### 배경 (사용자 요청 7건 — 관리 콘솔 > 지식베이스 > 메타데이터 > 그래프 뷰)
① 상세 패널 '뒤로/앞으로' ② 관계 클릭 시 카메라 이동만·[더블]클릭 시 상세 전환 ③ 상세 패널 아래 범례를 탭으로
(기존 '테이블 역할' + 테이블·컬럼·용어·스키마 카드 등; "크기·라벨%=검색 유사도(pg_trgm)…" 문구 제거) ④ AI 능동 분석
중복 Queueing 방어(프론트 상호작용·상태 가시화 유지, 백엔드 검증 후 메시지) ⑤ 일부 데이터소스가 해시값 그대로 출력되는
이슈를 사용자 지정 식별자로 ⑥ 카테고리 범위 드래그가 줌 스케일과 불일치(커서보다 더 이동) ⑦ 카테고리 범위 전용 축소 버튼
(현재 패널 클릭만으로 접힘).

### 구현 (프론트 admin.js/admin.html/styles.css + 백엔드 node_analysis.py/admin_metadata.py, cross-cut 0003/0002)
- **#1** `_metaGraph` 방문 이력 스택(detailHist/idx/_histNav) — `_metaGraphShowDetail` 진입 시 기록(뒤로/앞으로 네비 중 no-op),
  상세 패널 상단 지속 nav 바 `←뒤로/앞으로→`(이력≤1 숨김·끝단 disabled·이력 N/M), datasource 컨텍스트 전환 시 초기화.
- **#2** 관계 행 단일 클릭 = `_metaGraphAnimateFocus` 카메라 팬만(상세 패널 유지)·더블클릭 = `_metaGraphTraceRelation` 상세 전환.
  260ms 타이머로 단/더블 분리, 키보드 Enter=전환. `_metaGraphBindRelRow` 공통화(상세 패널·관계뷰 행 모두).
- **#3** 상단 flat 범례바 + 하단 `<details>` 역할범례를 상세 패널 하단 **3탭**(노드 종류/관계·AI 상태/테이블 역할)으로 통합.
  `_metaGraphBindLegendTabs()`(멱등·←/→ roving·hidden 토글), pg_trgm 유사도 note 제거. 역할 `<li data-role>` 보존(툴팁 소스 불변). 검색 매칭(앰버 글로우) 칩 parity 유지.
- **#4** 프론트 in-flight 가드 `_metaGraph._analyzePending`(같은 노드 연타 동시 POST 차단) + 백엔드 `reused` 검증 결과로 분기 —
  "이미 이 노드의 AI 능동 분석이 진행 중입니다(진행 N/M)" 가시 메시지(무음 재시작 대신). 백엔드 `enqueue_analysis` reused 분기가
  진행 카운트(`progress:{enqueued,done,failed}`)를 반환하고 엔드포인트가 passthrough. 버튼 상호작용 유지.
- **#5** `_metaDatasourceLabelOf(scope_key)` — `adminState.datasources` 의 {key=라벨, scope_key=해시} 로 해시→라벨 역매핑
  (common→'공용', 미매칭→원문). raw 해시 노출 지점 2곳(샘플 검수 스코프칩·용어 관계 scope 태그) 교정. 스코프 select 는 이미 라벨 표시라 무변경.
- **#7** `_metaGraphRenderClusterDetail(...,comboId)` — 펼쳐진 스키마면 **항상 화면 내인 상세 패널**에 전용 "▦ 접기" 버튼
  (→`_metaGraphCollapseSchema`). 근거(라이브 실측): 큰 스키마 펼침 시 캔버스 combo 우상단 "−" 컨트롤이 뷰포트 밖(y≈-1713)으로
  벗어나 접근 불가. body 클릭으로 접히는 코드 경로는 원래 없음(combo:click=상세, "−"/우클릭=접기) — 유지.
- **#6** **라이브 관측 후 무변경**: win-browser 실 Chrome 로 `getElementPosition` 반환이 world 좌표임을 검증(viewport = world × zoom;
  combo world폭 864.6 → viewport폭 475.6 = zoom 0.55). 따라서 클러스터 offset 누적(`_metaClusterOffsetAccumulate`)은 줌-독립적으로
  정합하며, combo/카드 드래그는 G6 v5.1.1 네이티브 drag-element 가 처리(앱에 커스텀 좌표 계산 없음). **앱 코드에 좌표 결함 없음** —
  최근 graph-drag/graph-freeplace 개편으로 해소된 것으로 판단. 근거 없는 `÷zoom` 추가는 정상 계산을 깨뜨리므로 코드 변경하지 않음.

### 검증
- node --check(admin.js) PASS · py_compile(node_analysis.py·admin_metadata.py) PASS. 최신 main(7facb804: funcproc+Phase B/C+Esc-fix)
  rebase — admin.js/node_analysis.py 자동 병합(제 상태 필드·#4 변경과 main 의 Esc 핸들러·Phase B/C 필드 공존 확인), admin.html cache-buster 충돌만 해소.
- §18.8 적대 리뷰: REVIEW REV-20260704T071838-graphux7.
- 라이브 관측(win-browser): #5 스코프 select 라벨 표시 확인, #6 좌표계 검증(무결), #7 "−" off-screen 재현.

### 잔여
- 배포(deploy_scope: included): main 병합 → web 재배포(정적 자산 baked) → **PB-0008 실 Windows 브라우저 POST-DEPLOY**
  (#1 nav·#2 단/더블·#3 3탭·#4 reused 메시지·#5 라벨·#7 접기 버튼 시각검증; pageerror 0). 마이그 없음.
- #6 실드래그 재현(trusted 입력 — Playwright MCP)은 후속. 현 도구로는 합성 드래그가 G6 를 트리거 못 해 재현 불가. 사용자 #6 의 실대상(sim-group 드래그)은 §50(group-interact)이 해결.

## 2026-07-04 · 크로스-데이터소스 관계 (crossds-rel, Phase B, TASK §47, ADR-019)

### 배경 (사용자 3대 개선 中 B)
"다른 DB 간 관계가 구성될 수 있으니 그 구조를 위한 연결 구축". 관계 엔진이 3중 경계(단일 scope/ds·per-schema 추론·
단일-커넥션 프로브)로 datasource 내부에만 갇혀 있던 것을, Phase C 의미 임베딩 구동으로 데이터소스 경계를 넘게 확장.

### 구현 (ultracode 워크플로우 설계 → 구현 → 적대리뷰 → flip-전 블로커 반영)
- **data model(0036, 비파괴)**: table_relationships 엔드포인트별 datasource + 7-col UNIQUE + CHECK 'manual'.
- **추론(데몬 기본 OFF)**: Phase C 시그니처 임베딩 pgvector 코사인 → 서로 다른 datasource 의 유사 테이블 공통 join-key
  컬럼을 후보(inferred/candidate). effective schema(MSSQL DB명) 정합.
- **신뢰 게이팅**: 프로브 skip(cross-ds 는 검증 불가·오분류 파단 방지) + AI 컨텍스트 trusted-only 주입 + 승격은 manual만.
- **그래프·완화**: 각 끝점 자기 scope 앵커(cross_ds edge) + neighborhood 자동 노출 + node_analysis cross_ds 완화. UI 마젠타 점선.

### 검증
- node --check·py ast·migrate-lint ACK·pytest **67 PASS**(head-aware ON-CONFLICT 불변식). §18.8 2단계 적대검증:
  설계 워크플로우 + 구현 리뷰 **SHIP(inert deploy)**. flip-전 블로커(**MSSQL effective schema MAJOR**·negative-decay
  가드·reverse-dup·cap) 반영. 정본 REVIEW REV-20260704T043653.
- 라이브 마이그 0036 + 배포(web+insight-worker) + PB-0008 배포 후. 크로스-ds 엣지는 AUTO=1 flip + 임베딩 populate 후 eventual.

### 3대 개선 완주
- A(제품 카테고리, ADR-014)·C(의미 임베딩, ADR-018)·B(크로스-ds, ADR-019) — 사용자 3대 개선 모두 출하. ADR-013 정합.

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

## 2026-07-04 · 그래프 뷰 z-order 의미 정합 (graph-zorder, TASK §52)

### 요청 (사용자)
`관리 콘솔 > 지식베이스 > 그래프 뷰` 의 각 요소가 적절한 z-order 로 구성되도록 검토 — 현재 상호작용에
따라 순서가 의미와 정합하지 않게 뒤바뀌고, 요소 성질이 변경되며 z-order 자체가 뒤틀리는 이슈.

### 근본 원인 (조사 확정)
1. **G6 v5 내장 drag-element 의 `frontElement` 영구 승격** — 모든 dragstart 마다 대상 zIndex 를 전역
   max+1 로 올리고 복원하지 않음(반복 드래그 시 단조 증가). 노드 드래그는 종속(컬럼·"X:" ctl)이 함께
   오르지 않아 계층이 찢어지고, combo(클러스터) 드래그는 클러스터 전체가 다른 클러스터 위로 영구 상승
   — **상호작용 이력이 곧 z-order** 가 됨.
2. **캔버스 요소 대부분 zIndex 미지정(z0)** — @antv/g 는 zIndex → 삽입순(renderOrder) 페인팅이라,
   setData diff 로 나중에 추가/재생성되는 요소(펼친 컬럼·카드↔combo 전환·그룹 재펼침·신규 엣지)가
   항상 기존 요소 위로 append — **성질 변경마다 순서 재편**.
3. **GB(그룹 배경) z −2 가 combo(0) 아래** — hit-test 에서 combo 에 삼켜져 §50 그룹 상호작용(배경
   드래그·클릭·우클릭)이 dead, 그룹 배경을 잡으면 클러스터 전체가 이동(의미 불일치).
4. HTML 오버레이(미니맵 z5·focus chip z5·ctxmenu z10000·ai-pop/progress in-flow)는 정합 — 무변경.

### 처리 결과 (frontend-only, admin.js + admin.html cache-buster)
- **의미 z-스케일 `_METZ` 단일 소스**: `COMBO(0) < GROUP_BG(1) < EDGE(2) < COLUMN(3) < NODE(4)
  < GROUP_HD(5) < CTL(6)` — build 가 전 요소(combos/nodes/edges, products 경로 포함)에 bake.
  삽입순 의존 제거 + 잔존 승격 자가 치유(rebuild 재-bake).
- **드래그 transient**: dragstart 에 대상+종속(테이블+컬럼+ctl / 그룹 박스·헤더·컨트롤·멤버·종속)을
  `canonical+1000` 결정론 부스트(내장 frontElement 를 덮음), dragend 에 canonical 복원. combo 드래그는
  내장의 coherent 하위 승격을 드래그 중 그대로 쓰고 종료 시 `_metaComboMemberIds` 로 동일 범위 복원.
- **GB 1 로 상향**: §50 그룹 상호작용(배경 드래그=그룹 이동) hit-test 회복. 클러스터 이동은 combo
  여백·라벨·접힌 카드 경로로 유지.
- **엣지 EDGE(2)**: 이웃 확장/추적으로 나중에 추가된 관계선이 칩 위를 지나던 것 해소(배경 위·칩 아래 고정).

### 검증
- `node --check` PASS · zIndex bake 16개소(빌드 산출 전 요소) · §18.8 적대 패널(ux·design·frontend
  correctness 3-렌즈) — 결과는 REVIEW.md 참조.
- **POST-DEPLOY**: web 재배포(정적 자산 baked, 마이그 없음) + PB-0008 실 Windows 시각검증 — 드래그
  전/중/후 계층, 펼침/접기/검색 rebuild 후 계층 불변, GB 그룹 드래그 회복, pageerror 0.

## 2026-07-04~06 · 전 ds 함수·프로시저 가시화 + DB 단위 AI 능동 분석 (routine-dbanalysis, TASK §53)

### 요청 (사용자)
① 함수/프로시저 노드가 그래프 뷰에 나타나지 않는 문제 해소 ② DB 단위 'AI 능동 분석' 제공.

### 조사 확정 (라이브 재현)
- 백엔드(SSOT·AGE 투영·API)·프론트(ingest·build·렌더) 전 경로 정상 — mysql-gz-qa-global 의 gunzgame
  에서 routine 300개 라이브 렌더 실측. 근본 원인 = **datasource 커버리지**: routine_objects 가 20개 ds 중
  4개만 적재(funcproc 배포 07-03 후 insight-worker 6h cadence+rotation 전파 중, 결정론 수단 부재).

### 처리 결과
- ① `modules/routine_backfill.py` + `bin/routine-backfill.sh` — 등록 전 datasource 즉시 introspect
  (WebDatasources 레지스트리 MEMORY_DB 연결, insight_enabled=False skip, 멀티 ds 플래그 fail-loud 가드)
  + scope 별 sync_graph, per-(ds,DB,schema) loud 리포트. prune-safety: label 공유 복수 스키마 prune=False
  (`routines.introspect_and_store(prune=)` 신설) + worker 경로 `prune=(store label==schema)` 동일 결함 봉인.
- ② `node_analysis.enqueue_schema_analysis`(run root=Schema·depth=1 pre-seed·재귀 0=budget 캡) +
  `POST /api/admin/metadata/graph/analyze-schema`(dry_run·audit·metadata.graph.read) + admin.js UI
  (카드/콤보 우클릭 메뉴·클러스터 상세 버튼·confirm 비용 가시화·기존 진행 패널 연동·reused/noop parity).
  비용 가드 = SCHEMA_CAP 200(hard 500)·only_missing·confirm·audit.
- 원본 세션이 §18.8 패널 대기 중 세션 한도로 중단 → 07-06 재개(resume)로 패널 완결: 적발
  BLOCKING 1(backfill 레지스트리 조회 DB 미지정 → DB 등록 ds silent 누락)·MAJOR 2(worker prune 회귀 /
  진행 패널 dismissed)·MINOR 5·NIT 4 전건 반영 또는 근거 수용 — 상세 MODIFY CHG·REVIEW.md.

### 검증
- pytest 신규 16 PASS(§18.8 회귀 잠금 6종 포함) + 관련 회귀 57 PASS · node --check/py_compile/bash -n PASS.
- POST-DEPLOY 완료(2026-07-06): PR #593→d1951b7e(deploy-web 롤링 soak+insight/ask-worker 재빌드) →
  라이브 backfill **2,201 routines/도달가능 4 ds**(accountdb 등 0행 스키마 3곳 최초 적재, graph_synced
  전건, SSOT==AGE 정합; 미도달 14 ds loud — 게이트망, 도달 시 재실행/cadence) → **PB-0008 라이브 PASS**
  (accountdb ƒ/⚙ 198 전수 렌더 z=4 · DB 단위 분석 e2e done 2/2·예약 고정=재귀 0 · reused confirm 생략+
  dismissed 패널 복구(§18.8 수정 실증) · noop parity · pageerror 0). 증적 artifacts/…/20260706-routine-dbanalysis/.

## 2026-07-06 · 그래프 뷰 개선 5건 — 상세 nav·kind 필터·검색 보존·Routine 분석·파라미터 수직 (graph-navfilter-routine, TASK §54)

### 요청 (사용자)
① 상세 패널 뒤로/앞으로 ② 노드 종류 필터(테이블·컬럼 항상, 관계·함수·프로시저 토글 — 재배치 반응)
③ 검색 변경/클리어 시 그래프 구성(확장·배치) 보존 ④ DB 단위 AI 능동 분석에 함수/프로시저 포함
(pcbang_dkonline 실측 gap) ⑤ 프로시저 파라미터 수직 배치.

### 처리 결과
- Workflow 5-렌즈 병렬 정찰로 스펙 확정 후 구현: ① 기존 노드-전용 히스토리를 view-typed(노드·클러스터·
  관계 상세) 확장 + 카메라 재현 ② hiddenKinds 빌드 입력 제외(자리 자동 회수 재배치) + 툴바 토글 +
  localStorage 영속(스키마 그래프 전용 — 제품 개요에선 숨김) ③ 검색을 additive overlay 로(리셋 회피,
  pristine 만 회수, base 컨텍스트 복원 — products 복귀·중심보기 칩 복원, '초기화'만 풀리셋) ④
  schema_routine_keys 신설 + 혼합 시드(테이블 우선 cap)·payload routine_type/params·confirm 카피 —
  워커 경로는 기존에 라벨 무가정이라 시드만이 결손 ⑤ 파라미터 서브노드 수직 방출(XR:/RP:, 컬럼 관례
  동형, z bake 1:1) + 상세 패널 세로 목록.
- §18.8 적대 패널(3-렌즈 find → BLOCKING/MAJOR 적대 verify Workflow): 적발 MAJOR 3 근본원인
  (products 랜딩 검색→클리어 미복원 / ingest Schema added 미반환 = pristine 회수 dead code / 중심보기
  부분그래프 '전체' 위장) 전건 수정 + MINOR·NIT 10건 반영(수용 1: 필터 재표시 시 열 말미 append —
  AC-2 명세) — 상세 REVIEW.md.

### 검증
- pytest test_routine_dbanalysis **21 PASS**(§54④ 신규 5 포함) + 관련 회귀 57 PASS · node --check ·
  py_compile PASS. POST-DEPLOY: web+insight-worker 재배포 → PB-0008 AC-1~5 라이브 실측(T54.8).

## 2026-07-09 · 노드-레벨 컬럼 LOD — 대규모 노드 성능 (col-lod, TASK §61, ADR-029)
사용자 리포트: "관리 콘솔 > 지식베이스 > 그래프 뷰에서 노드가 많아질수록 부하·지연. 2D 화면 다수 오브젝트
최적화 + 유사 서비스 방식 웹 리서치하며 진행."

### 접근 도출 (진단 → 리서치 → 적대적 검증)
- **진단(read-only)**: 병목 top3 확정 — ① 전체 rebuild `setData(_metaG6Build())`+draw 가 모든 인터랙션
  공통 경로(뷰포트 컬링 전무, draw 지배항=테이블당 최대 500 Column circle) ② 노드-레벨 LOD 부재(엣지만 축약)
  ③ 레이아웃 매 rebuild 비-memoize. 라이브 5스키마=2,618노드·cc_*=557T.
- **웹 리서치**: 대규모 2D 그래프(Sigma.js WebGL 인스턴싱·Cosmograph GPU·KeyLines·G6 native) 공통 플레이북 —
  뷰포트 컬링·LOD·shape 감축·optimize-viewport-transform·증분/배치·Worker 오프로드.
- **적대적 검증(코드·번들 실측)**: 19개 후보 중 16개 반증/보류. WebGL(번들 Canvas 전용·품질회귀)·
  optimize-viewport-transform drop-in(behavior 오분류·지배병목 아님)·뷰포트 컬링(layout 잔존·combo 축소·
  pan churn)·**topology-diff 증분(ADR-004 재검토)** 모두 기각 — 특히 G6 `setData` 는 **이미 draw 단계 diff**
  (변경 요소만 재렌더)라 증분이 지배 draw 를 못 줄이고, ADR-028 vpack 이 펼침을 형제 ~43% re-column 으로 만들어
  bounded-delta 무효, combo 자식 auto-fit 이라 coordinate-identity 불가 → **노드-레벨 컬럼 LOD** 로 수렴
  (사용자 C→A 전환 결정). 상세 근거 ADR-029.

### 구현 (admin.js, frontend-only, 마이그레이션 0)
- 상수 `_META_COL_LOD_ZOOM=0.5`·`_META_COL_LOD_MIN=200`. `_metaG6Build` 초입에 `colLodActive`
  (getZoom + 전체 펼친 컬럼 수 O(1) 합) 산정.
- 개요 밴드에서 Column circle·Routine 파라미터·per-table "X:" 접기 ctl **emission 억제**. `realH`(공간 예약)
  불변 → **테이블 좌표 band-invariant(reflow 0)**, combo 는 테이블이 범위 정의(하단 여백만 tighter).
- 억제 테이블 라벨 `▤N` 컬럼수 배지(labelMaxWidth overflow 차단). 컬럼 끝점 엣지는 `renderEndpoint` 로
  테이블 승격(dangling 0). `_lodBand` 3단(full/collod/lod)·300ms 디바운스·상태줄 밴드별 안내.

### 검증
- headless `test_g6build_collod.js` **신설 18 PASS** — 억제 0방출·**좌표 이동 0(band-invariant)**·▤N 배지·
  엣지 re-anchor·줌/컬럼 게이트·루틴 파라미터. 기존 headless **105 PASS 회귀 0**·`node --check` PASS.
- 캐시버스터 `admin.js?v=20260709-col-lod`. POST-DEPLOY PB-0008(대형 그래프 줌아웃 before/after)는 TEST §61
  (그래프뷰 무인 도달 차단 — 자산 curl + 사용자 육안 게이트).


## 2026-07-10 · 극단 줌아웃 클러스터 집계 (agg-lod, TASK §63, ADR-030)
사용자 후속: "줌아웃으로 개별 식별 무의미하면 상위 집계 객체로 묶어 draw 감축."

### 근원 실측 (추측 제거)
헤드리스로 `_metaG6Build` JS 실행시간 측정 — 대형 모델(557T/1200~9000컬럼) **18–50ms**. 즉 JS 레이아웃
재계산은 병목이 아니고, 병목은 브라우저 `setData`+`draw`(Canvas 렌더)로 **방출 노드 수에 비례**(ADR-006
~1ms/node). col-LOD(§61)는 컬럼만 줄여 대형 스키마의 **테이블 수 floor** 가 남음 → 사용자 "여전히 느림" 정합.
(Playwright 브라우저 하니스로 실제 draw ms 측정을 시도했으나 샌드박스 Chromium 리소스 제약으로 포기 — node
빌드 타이밍 + ADR-006 + 사용자 피드백으로 근거 확립.)

### 구현 (frontend-only, 마이그레이션 0)
극단 줌아웃(zoom<`_META_AGG_ZOOM`=0.15) + 대형 모델(nodes>`_META_AGG_MIN`=60)에서 확장 클러스터를 **단일
집계 카드(SC:)로 강등** — 기존 접힌-카드 경로 재사용. `layouts` 미변경 → 집계 카드를 슬롯 좌상단에 배치해
**reflow 0**. SC:id↔combo id 다른 네임스페이스로 setData add/remove(타입전환 회피). 4단 밴드·상태줄 집계 안내.

### 검증
- headless `test_g6build_agglod.js` **10 PASS**(카드방출·draw급감>10x·reflow-free 위치·비-agg 유지·소형 게이트)
  + 회귀 125 = **134 PASS** · `node --check` PASS.
- diff 2렌즈 적대 리뷰 PASS(BLOCKING/MAJOR 0). MINOR 1 수정(상태줄 마커를 밴드→실제 억제 플래그 게이트).
  NIT 1 수용(agg 중 카드펼침 재집계 시 안내문구 부정합 — 니치). 상세 REVIEW.md.
- 캐시버스터 `admin.js?v=20260710-agg-lod`. POST-DEPLOY 사용자 육안(TEST §63).
- **잔여**: 줌인 대형모델 팬/클릭은 뷰포트 컬링(테이블)이 필요하나 combo auto-fit 이 combo-safe 를 막음 — 별도 검토.


## 2026-07-10 · 뷰포트 컬링 + 집계 supernode + 마커 제거 (§65, ADR-032, 사용자 육안 피드백)
agg-lod(§63) 배포 후 사용자 실화면 피드백 반영. **시각검증 가능 확인**(win-browser.py relay 실 Windows Chrome).

### 변경 (frontend-only)
- (1) 집계 카드가 줌아웃 크기라 작던 문제 → ≈1/zoom supernode 스케일업(슬롯 중앙·클램프·폰트 확대).
- (2) 집계 상태줄 "클러스터 집계" 안내 제거(사용자 "노이즈"). col/edge LOD 마커는 오독-가드로 유지.
- (3) **viewport-cull(§65)**: 줌인 대형모델에서 화면(+마진 0.6) 밖 테이블의 컬럼/파라미터 방출 억제(테이블 칩·combo
  유지 = combo-safe). 병목=draw 방출 수라 보이지 않는 컬럼 미방출로 줌인 클릭/팬 경량화. col-LOD 와 동일 억제
  메커니즘(realH 예약·배지·테이블 유지)을 뷰포트 축으로 확장·OR 결합. renderEndpoint 승격(dangling 0). 팬 재-emit 디바운스.

### 검증
- headless `test_g6build_viewportcull.js` **6 PASS**(컬럼 컬링·combo-safe·band-invariant·게이트) + 회귀 134 = **140 PASS**·node --check.
- diff 2렌즈 적대 리뷰. **win-browser 실 Windows Chrome 육안 검증**(TEST §65).
- 캐시버스터 `admin.js?v=20260710-graph-perf2`.
- 한계: 테이블 자체 컬링은 combo auto-fit 으로 combo-safe 아님 → 컬럼 컬링 한정. 단일 초대형 스키마 테이블-칩 floor 잔존(후속).


## 2026-07-10 · 집계폐기 + 카테고리 밴드 규모 + 테이블 뷰포트 컬링 (§67, ADR-033, 사용자 육안 피드백)
§65 배포 후 사용자 실화면 피드백 반영. win-browser relay 로 combo 거동 육안 확인하며 구현.

### 변경 (frontend-only)
- (A1) 집계-카드(§63/§65) 폐기 — 규모/구조 파악 어렵다는 피드백. aggActive 상시 false(코드 보존). 클러스터 펼침 유지.
- (A2) 제품 카테고리 밴드 헤더에 규모 명시: "N DB" → "N DB · M 테이블"(멤버 schemaTotals 합).
- (B) 테이블/클러스터 뷰포트 컬링(§65 컬럼→테이블 확장): 화면 밖 테이블 칩·전체 화면 밖 클러스터(combo) 미방출로
  줌인 draw 급감. 부분 가시 클러스터는 combo 가시분 auto-fit. 카테고리 밴드 bbox 는 선산정 유지. 팬 재-emit.

### 검증
- headless viewport-cull 6·agglod 8(집계비활성 잠금)·회귀 = **150 PASS**·node --check. diff 2렌즈 적대 리뷰. win-browser 육안(TEST §67).
- 캐시버스터 `admin.js?v=20260710-catband-cull`.
- 트레이드오프: 극단 줌아웃(전체 in-view)은 집계보다 무거움(구조·규모 이해 우선). 줌인은 컬링으로 경량, 카테고리 접기로 완화.

## 2026-07-10 · 상세 패널 관계 중복 병합 (graph-reldedup, TASK §69, 사용자 요청)
`그래프 뷰 > 상세` 에서 같은 노드의 REFERENCES 관계가 두 인라인 섹션에 중복 출력 → 사용자 "확인 후 병합" 요청.

### 확인 (중복 진단)
- #1 `컬럼 (N) > 참조함(→)/참조받음(←)` — 컬럼별·방향별 그룹 + 의미 툴팁(`_metaRelSemanticTip`) + 🔎추적 (relRow/dirGroup, `_metaGraphRenderDetail`).
- #2 `AI 능동 분석 > 연결 관계 추적 (N)` — flat list, `_metaGraphRelTraceRowsHTML(key, null)` 로 모델 전체 REFERENCES 재나열. #1 과 동일 데이터·추적 행·신뢰 배지·클릭 동작 → 순수 중복. (주석의 원래 의도 "AI가 따라간 관계 노출"과 달리 실제로는 모델 전체를 재렌더)
- #3 우클릭 '관계 상세' 팝업(`_metaGraphShowRelations`)은 별도 on-demand 모달 → 인라인 중복 아님, 유지.

### 변경 (frontend-only, 마이그레이션 0)
- #2(AI 박스 flat 목록) 제거 → 추적 관계는 더 풍부한 #1 로 일원화. AI 박스 = 역할 칩 + prose(요약/관계/활용/주의) 고유 가치만.
- orphan `_metaGraphRelTraceRowsHTML` 함수 삭제, no-op `_metaGraphBindTraceRows(box)` 제거, dead CSS `.admin-meta-graph-ai-rels` 제거, stale 주석 정정.
- 병합 방향 사용자 승인(AskUserQuestion 2026-07-10).

### 검증
- `node --check` PASS. diff 13삽입/40삭제·3파일(admin.js/admin.html/styles.css). 캐시버스터 `admin.js?v=20260710-reldedup`·`styles.css?v=20260710-reldedup`.
- 손실 없음: 테이블/컬럼 상세엔 #1 항상 렌더, Routine 노드는 REFERENCES 없어 #2 원래 미표시. POST-DEPLOY PB-0008 육안(feature-0003 TEST §69).

### POST-DEPLOY (2026-07-10, PR #659 → main 5e235953)
- `make deploy-web` 무중단 롤링(web-a/web-b 순차 recreate·90s soak PASS·마이그 0). `/healthz` git_commit=5e235953·mysql_ok·pg_ok.
- 병렬 세션 PR #658(§68 graph-rw-group ROUTINE_USES 읽기/쓰기 분리)가 worktree 생성 후 머지 → origin/main rebase·§68→§69 재지정·admin.js 영역 비겹침 병합(양 변경 라이브 공존).
- **실 Windows Chrome(Chrome/149) POST-DEPLOY 실측**: 서빙 admin.js 실제 render producer `<strong>연결 관계 추적`=0·`function _metaGraphRelTraceRowsHTML`=0 / styles.css 실제 규칙 `.admin-meta-graph-ai-rels {`=0 / 런타임 `typeof _metaGraphRelTraceRowsHTML==="undefined"`·유지 함수 3종 function·`.admin-meta-graph-ai-rels` DOM 0·pageerror 0. 중복 #2 구조적 제거 결정적 실증(feature-0003 TEST §69 POST-DEPLOY).

## 2026-07-10 · 상세 패널 사용관계 행 클릭 시 카메라 이동 (graph-rtuse-camera, TASK §71, 사용자 요청)
사용자 요청 "그래프 뷰 상세에 카메라 이동 버튼 추가" — 상세 패널의 "사용 테이블/사용 함수·프로시저" 행 클릭이 상세 패널만 전환하고 카메라는 안 움직여 큰 그래프에서 대상 노드 재탐색이 어려웠음. §70 은 '선택 노드' 헤더 버튼, 본 작업은 **관계 행 대상**을 카메라로 가져온다.

### 변경 (frontend-only, 마이그레이션 0)
- admin.js `_metaGraphRenderDetail` 의 `[data-rtuse]` 클릭 핸들러: `_metaGraphPanToRelation(k)`(동기 카메라 팬 + 대상 선택) 먼저 → `_metaGraphShowDetail(k)`(async 상세 전환). 기존 shipped 팬 래퍼(graphux7#2) 재사용, 신규 기계장치 0.
- 미렌더 대상(접힌 스키마·컬링)은 pan 이 `_metaRenderedIdFor` null 가드로 안내만·팬 skip, 상세 전환은 정상(graceful). 섹션 안내문 "행 클릭 = 대상 상세." → "+ 카메라 이동".

### 검증
- `node --check admin.js` PASS. inline 적대 diff 리뷰 REV-20260710T163512(순서/race·미렌더 가드·selection idempotent·캐시버스터 PASS, BLOCKING/MAJOR 0, NIT1 비가시 stale 힌트 수용). frontend-only·마이그 0·Minor(§12.3).
- 캐시버스터 `admin.js?v=20260710-graph-rtuse-camera`(CSS 미변경 → styles.css 미bump). POST-DEPLOY PB-0008 육안(feature-0003 TEST §71).
## 2026-07-10 · 상세 패널 관계행 단일클릭 미렌더 컬럼 카메라 이동 (§72 reltrace-colnav, 사용자 리포트)

사용자 리포트: `그래프 뷰 > 상세`에서 관계 행(컬럼)을 **단일클릭**하면, 대상 컬럼의 소속 테이블이 아직 펼쳐지지
않은 상태(컬럼 미렌더)에서 카메라가 이동하지 않고 **"대상 노드가 현재 화면에 없습니다"** 안내만 떠 사용자가
오류로 인지. 더블클릭은 정상 이동. 사용자 결정(AskUserQuestion): ① 단일클릭도 소속 테이블로 카메라 이동(펼치진
않음) ② **선택 상태는 컬럼**, **하이라이트는 상위 종속 객체(테이블)** (하이브리드) ③ 더블클릭은 펼쳐 컬럼 선택.

### 근본 원인
`_metaGraphPanToRelation` 이 `_metaRenderedIdFor(targetKey)`(자기 자신·접힌 스키마 카드 `SC:` 만 해소)로 null 이면
즉시 안내-return. 미펼침 테이블의 컬럼은 렌더되지 않아(접힘 시 컬럼 제거·미펼침 시 미적재) 항상 null → 단일클릭
카메라 이동이 죽음. 추가로 `_metaG6Build` 가 매 빌드 `_metaGraph.selected` 로 focusAdj 를 재산출(§57.5 self-healing)하는데,
selected 가 모델 밖 컬럼이면 focusAdj=null → 선택해도 하이라이트가 사라지는 부작용(적대 리뷰 MINOR#3 적발).

### 변경 (frontend-only, 마이그레이션 0)
- (1) `_metaRenderedAncestorFor(key)` — 미렌더 대상의 화면상 가장 가까운 조상(컬럼→소속 테이블→접힌 스키마 카드) 승격.
- (2) `_metaFocusKeyFor(selKey)` — 하이라이트 기준 키 해소: 모델 밖 컬럼이면 소속 테이블(모델의 Table 노드일 때만)로
  폴백. `_metaGraphSetSelected`(즉시)·`_metaG6Build`(재산출) 양쪽이 공유 → **선택=컬럼·하이라이트=소속 테이블** 일치.
  부모가 Table 아니거나 없으면 null → §57.5 F2(prune 된 선택 정리) 보존.
- (3) `_metaGraphPanToRelation` 재작성: 조상 승격으로 카메라 팬 대상 해소, 오류 톤 메시지 제거, `(renderedSelf || !direct)`
  게이트로 대상 컬럼 선택(접힌 스키마 카드로만 승격된 경우=스키마 대상은 기존대로 선택 없이 팬만).

### 적대 리뷰(§18.8) 반영
REV-20260710T065500 [SUBAGENT: PASS-WITH-FIXES]: (MAJOR) 리뷰 중 §67 catband-scale·§68 graph-rw-group 이 main 에 병렬
머지되어 base(00871661)가 4커밋 stale — **현재 main(c0a3d70f)으로 rebase** 후 재적용·재검증(§67 테이블 뷰포트 컬링과
정합: 화면 밖 테이블은 카드/안내로 degrade). (MINOR#3) 미렌더 컬럼 선택이 하이라이트를 소실시키는 문제 → **하이브리드
(_metaFocusKeyFor 폴딩)** 로 해소. (테스트) 선택 게이트·하이라이트 폴딩 단언을 headless 에 추가.

### 검증
- 신규 headless `test_graph_colnav.js` **22 PASS**(승격 5·키파싱 2·선택게이트 G1~G4 8·하이라이트폴딩 F1 4·직접렌더).
- 회귀 0: edge_visibility 71·agglod 8·category 26·collod 20·vpack 19·viewportcull 6 = **150 PASS**·`node --check` PASS.
- 캐시버스터 `admin.js?v=20260710-graph-colnav`. POST-DEPLOY PB-0008 사용자 육안(TEST §72 T72.5).

## 2026-07-10 · AI 능동 분석 "주의" 자기-불평 제거 + 루틴 payload 보강 + 시드 커버리지 (§69, ADR-034, 사용자 전수 피드백)
사용자 보고: mssql-qa-idc/cc_data_main 능동 분석 결과 대부분 노드의 '주의' 가 "불명확" 계열. 전수 파악 + 근본 개선 요청
(+ "DB 단위 분석 중단으로 미분석 노드 잔존" 검토). PG 전수 조사로 근본원인 3종 확정.

### 근본원인 (전수 근거)
- **caveats 자기-불평(주 원인)**: done 536 중 Table 71%(150/211)·Routine 56%(99/177) 가 "메타데이터 불완전·직접
  검토 필요·불명확" 계열. Table/Routine 빈 caveats 0건. params/참조테이블이 payload 에 정상 도달한 루틴조차 불평 —
  LLM 이 도메인적으로 할 말이 적을 때 caveats 를 "입력 부족" 자기-불평 dumping ground 로 사용(프롬프트 계약 결함).
- **루틴 under-projection**: `returns` 미투영 + 참조테이블이 무구분 `other` 로만 흘러 read/write 소실.
- **시드 커버리지**: cc_data_main 555객체 중 399만 분석 — SCHEMA_CAP=200 + depth-2 재귀 도달성 한계로 156 미커버
  (run 은 done 표시 → "중단" 오인). 실패 11건은 haiku 일시 빈응답(재생성 시 재시도).
- (상류·범위밖) cc_data_main 은 column_descriptions·table_descriptions 0행 — 컬럼/설명 큐레이션 미적재라 테이블이
  FK 컬럼만 노출. 프롬프트 수정으로 불평은 멈추나 실질 풍부화는 후속 큐레이션 필요.

### 변경
- **P1** [`llm.py` NODE_ANALYSIS_PROMPT]: "Analyze-from-what-is-visible" + "Caveats rule" 규칙 신설 — caveats 를
  운영자 대상 데이터/도메인 리스크로 한정, 입력 불완전 언급·"직접 확인 필요"·"불명확" 금지, 위험 없으면 빈 문자열.
  caveats 필드 설명문 + Input JSON(returns/touches) 문서 갱신.
- **P2** [`node_analysis.py`]: Routine `touches:[{table,access}]`(ROUTINE_USES relation_type) + `returns`
  (routine_objects SSOT) payload 투영. 신규 `_fetch_routine_returns` 헬퍼(비차단).
- **P3** [`shared/config.py`]: SCHEMA_CAP 200→1000·SCHEMA_MAX 500→2000·RUN_BUDGET_MAX 2500→4000·BATCH_PER_TICK 4→10.

### 검증
- `make test`/직접 pytest **PYTEST_RC=0**(feature-0002+0003 전체, 회귀 0)·py_compile 3파일 PASS.
- **라이브 LLM**(container shadow-load, 새 프롬프트 monkeypatch): CT_Theatrics(희소Table) 주의 `''`(이전 "정의서
  확인 필수"), sp_GetCashPoint(Get) → "민감 결제·통화 데이터 권한제어·감사로깅"(이전 "확인 불가"),
  sp_DeleteItemAttributeResist(Delete) → "비가역 DELETE 데이터 손실"(양질 유지) — 자기-불평 전멸.
- **라이브 payload**: touches read/write 정확 구분(DELETE→write·Get→read) + returns 투영.
- POST-DEPLOY(T69.5): cc_data_main 재생성(only_missing=false) → 커버리지 555 + 표본 caveats 재확인.

## 2026-07-10 · §71 graph-rtuse-camera POST-DEPLOY 완수 (docs-only, resume 세션)
§71(상세 패널 사용(참조)관계 행 클릭 → 대상 노드 카메라 팬)은 병렬 Codex 세션이 commit(1356717c)→push→PR #662→main 병합(b7d7d871)→web 재배포까지 완주했고, 본 resume 세션이 독립 검증 후 POST-DEPLOY 육안을 마감했다.
- **독립 적대 리뷰(subagent, 동일 코드)**: VERDICT PASS — BLOCKING/MAJOR 0. "showDetail 이 `_opSeq` bump → 예약 팬 취소" 가설 반증(showDetail 무-bump·카메라 미조작 → 더블 팬/되감기 없음). MINOR 2(미렌더 안내 비가시 stale 카피·클릭당 bake 2회) 가시 회귀 아님 → 수용.
- **POST-DEPLOY win-browser 실측(라이브 a24415a5)**: mssql-web-qa `shop_pt.T_ItemInfo` 상세의 `[data-rtuse]` 18행(읽기 12·쓰기 6) 실클릭 → 카메라 중심 [3600,7092]→[2523,7871] 팬 + 상세가 대상 ROUTINE(MSP_ADMIN_ITEM_LIST)으로 전환 동시, pageerror 0. 안내문 "행 클릭 = 대상 상세 + 카메라 이동" 노출. 자산 curl(서빙 버스터·핸들러) 확증. 스크린샷 before/after.
- 원격 브랜치 `ai/claude/feature-0016-graph-rtuse-camera` 는 병합 후 origin 에서 정리 완료.
## §73 graph-layoutmemo — 배치-정렬 함수 위상-서명 메모이즈 (줌인 성능 근본원인) (2026-07-10)
- 사용자 요청(누적): "극단적인 줌 인 상태에서도(밀집 아닌데도) 성능 저하 — 근본 원인을 탐색 후 해소."
- 근본원인(win-browser 실측 함수분해): `_metaG6Build` 의 ~99% 가 `_metaRelOrderAll`(barycenter, ~55%·38ms) + `_metaSimGroups`(affix 유사그룹, ~45%·32ms). 둘 다 **전체 모델 처리**(뷰포트·줌·선택 무관) → 극단 줌인·비밀집에서도 rebuild 당 68~145ms 고정 = "줌인해도 느림"의 정체. §65/§67 컬링(화면 밖만)으론 못 줄이는 축.
- 해소: 두 순수 함수를 **위상-서명(_metaTopoSig: nodes/REFERENCES edges/schemaExpanded/mode) 메모이즈**. 서명 무변경(팬·줌·선택·마커·컬럼토글·드래그) rebuild 는 정렬 재사용 → build 를 방출 비용만 남김. 통짜 layout 캐시는 groupOf/groupMembers side-effect landmine 이라 배제. cull 마진 0.6→0.3(고배율 방출 감축).
- 검증: headless 메모이즈 19 + 회귀 150 = **169 PASS**·node --check. 캐시적중==fresh 좌표완전동일(메모이즈가 출력 불변) 증명. §18.8 적대 리뷰(REV §73: BLOCKING/MAJOR 0 · F1 roles·F2 노드속성 stale 캐시 잡아 서명 확장 수정). POST-DEPLOY win-browser 실측.
- 캐시버스터 `admin.js?v=20260710-layoutmemo`. ADR-035. §65/§67 컬링과 상보(컬링=방출 수↓, 메모이즈=배치 계산↓).

### §73 layoutmemo POST-DEPLOY 실측 (2026-07-10, main e6b7b68f)
win-browser 실 Windows Chrome relay 로 배포본(mssql-qa-idc 882 노드) 검증: 동일 위상 연속 build 함수분해 — **MISS 59ms(relOrderAll 27+simGroups 29) → HIT 8ms(둘 다 0) = 7.4× 급감**(지배 함수 완전 skip), MISS↔HIT 방출 좌표 이동 **0**(band-invariant)·방출 수 동일. 극단 줌인(2.5)도 HIT 8ms·마진 0.3·pageerror 0. 캐시 정상(_simCache 4·_relOrderCache set). "극단 줌인·비밀집인데도 느림" 근본원인이 캐시 적중 시 8ms 로 상시 경량화 — 사용자 요청 근본해소 실증. TEST §73.
## 2026-07-10 · 상세 패널에서도 테이블 노드 내 컬럼 선택 (graph-detail-colsel, TASK §75, 사용자 요청)
- 요청: ``그래프 뷰 > 상세` 패널에서도 테이블 노드 내 컬럼을 선택할 수 있도록 구성`. 캔버스(컬럼 노드 클릭)에서는 선택되나 상세 패널 컬럼 목록에서는 불가하던 빈틈 보완("~에서도"). §71 rtuse-camera(사용관계 행)·§72 reltrace-colnav(관계행→미렌더 컬럼 카메라)와 별개 — 본 항목은 컬럼 목록 자체의 선택 배선.
- 진단(Explore 코드 매핑): 컬럼은 개별 G6 노드이고 선택 상태 `_metaGraph.selected` 는 캔버스·컬럼 공용 단일 변수. 캔버스 컬럼 노드 클릭은 `_metaGraphShowDetail(colKey)` 로 선택(강조+상세전환). 상세 패널(`_metaGraphRenderDetail`)의 컬럼 행만 배선 부재 — plain=정적 텍스트(DOM에 키 없음)·관계=아코디언 토글(`.amgr-col-toggle[data-colrel]`)만.
- 구현: plain 컬럼 → `.amgr-col-select[data-col]` 버튼. 관계 컬럼 → `.amgr-col-head`(flex) 안에서 캐럿(`.amgr-col-caret[data-coltoggle]`, 인플레이스 아코디언 보존)과 선택 버튼(`.amgr-col-select[data-col]`) 분리(캐럿=펼침·이름=선택, VSCode 트리 패턴). 바인딩: `.amgr-col-select[data-col]` → `_metaGraphShowDetail(data-col)`(캔버스·`data-rtuse` 와 동일 선택 경로 재사용) → **새 상태변수 0**, 선택 의미론(history + 캔버스 강조 재베이크 + 상세 컬럼뷰 전환) 무상속. CSS `.amgr-col-select`(plain=block/관계=flex relcount 우측정렬)·`.amgr-col-head`·`.amgr-col-caret`. a11y: 캐럿 `aria-controls`+상태중립 `aria-label`, 선택 버튼 간결 `aria-label`. 캐시버스터 admin.js/styles.css `20260710-graph-detail-colsel`.
- 검증: `node --check` PASS · 신규 헤드리스 격리 렌더 테스트(`test_detail_colsel.js`, vm+`_metaGraph` 주입) 8/8 PASS · 기존 g6build 6종 무회귀 · 적대 diff 리뷰 [SUBAGENT: PASS](REV-20260710T230000, Critical/Major/Minor 0 + a11y nit 2건 반영). main rebase(§71/§72/§73 병렬 머지 후 admin.js 자동병합·재검증). frontend-only·마이그 0·Minor(§12.3).
- 미완(배포 후): T75.4 POST-DEPLOY 실 Windows 육안(PB-0008) — 상세 패널 컬럼 클릭→선택/강조/아코디언 독립 동작.

## §76 graph-cull-refkeep — 컬링 참조·상호작용 보존 (2026-07-10)
- 사용자 요청: "cull 처리된 노드들에 대해서 연결선 또한 사라지는 + 상세 패널에서 상호작용 불가. draw는 하지 않되 참조·상호작용은 가능하도록."
- 진단: 컬링이 화면 밖 노드 미방출 → (a) renderEndpoint 가 앵커 못 찾아 엣지 드롭 (b) _metaRenderedIdFor null 로 상세 네비 팬 skip.
- 수정: (a) focusAdj 예외(선택 노드 1-hop 관계 상대) + **뷰포트 내 노드 엣지 컬링무효**(in-view 노드에 연결된 상대 끝점 _edgeExempt 방출 예외) → 관계선 렌더 + 네비 팬 복원. (b) 팬 재-emit rAF 스로틀(실시간 드래그 컬링). **무선택·무연결 시 예외 0**(컬링 무손실); in-view 연결 상대는 선택 무관 예외(§76 적대리뷰 M1 정정 — 종전 "무선택 예외 0" 은 focusAdj-only 시점 기술). ADR-037.
- 검증: headless cullrefkeep 15(§76 리뷰 M2 dense off-view 컬링유지 보강) + 그래프 회귀 = **249 PASS**(11 스위트)·node --check. §18.8 적대 리뷰 [SUBAGENT: PASS-WITH-FIXES](BLOCKING/MAJOR 0). POST-DEPLOY win-browser. 버스터 `admin.js?v=20260710-cullrefkeep`.

## 문서 아카이빙 압축 정보 (§5.5, 20260711T120531)
- MODIFY 총 118건=아카이브 102+현행 16 · REVIEW 총 118건=아카이브 102+현행 16. verbatim·무손실 md5·timestamp 아카이브명.


## 2026-07-10 POST-DEPLOY · §69 AI 능동 분석 "주의" 개선 배포 + cc_data_main 재생성 완수 (T69.5)
§69(ADR-034) 코드 변경이 PR #664 로 main 병합(a24415a5) 후 라이브 배포·재생성까지 완수됨.
- **배포**: insight-worker 재빌드·재기동(라이브 검증 config CAP 1000·MAX 2000·RUN_BUDGET 4000·BATCH 10 +
  NODE_ANALYSIS_PROMPT 새 계약 5요소 — Caveats rule·Analyze-from-what-is-visible·returns/touches Input·
  untrusted 열거·빈값 선호) + `make deploy-web` 무중단 롤링(web-a/b, soak 90s 통과) + healthz OK. 신규 마이그 0.
- **재생성 run `7c75ddcb`**(cc_data_main, `only_missing=false`): dry_run **planned 555 · capped=false** —
  이전 `SCHEMA_CAP=200` 이면 200 에서 잘려 355 미커버였을 것(P3 커버리지 수정의 라이브 실증). 재귀 확장 포함
  **715 잡 전량 done · 0 failed**. (초기 급속 드레인 시 haiku 빈응답 transient 330건 발생 → 실패분을 pending
  리셋 + 완만 페이스 재처리로 전량 회복. 급속 연속 호출이 원인, 로직 결함 아님.)
- **caveats 품질 재확인**(715 전수): 빈 caveats **400/715**(평범한 노드는 빈 값이 정답 — 계약 의도대로),
  비어있지않음 315 는 전부 실제·가시적 위험(sp_Delete* 비가역·cascade, 민감·현금성 재화, 대량데이터 성능/피크타임
  잠금, candidate/미검증 FK 데이터품질). **옛 자기-불평("메타데이터 불완전·직접 확인 필요·불명확·판단 불가")
  사실상 0** — 전수 스캔 매칭 12건은 전부 candidate FK 관계 데이터품질 caveats(새 계약이 명시 허용하는 가시적
  위험)이며 옛 self-complaint 아님. 사용자 원 리포트("대부분 노드 주의가 불명확") 해소.
- **미결(범위 밖)**: cc_data_main 원천 큐레이션 공백(column/table_descriptions 0행)은 상류 이슈로 별도 후속 —
  프롬프트가 불평을 멈출 뿐 실질 풍부화는 큐레이션/인트로스펙션 보강 필요(ADR-034 한계 절 기재).

## 2026-07-13 · §78 렌더 엔진 PixiJS v8 교체 — 타당성 검토 + 계획 수립 (plan-review)
사용자 리포트(다수): 노드 다수 상태 카메라 이동(팬) 버벅임 잔존 → 외부 엔진(게임/시뮬레이터) 전환 타당성 검토 요청 → 검토 결과 수용 + "G6 과거 디자인 실패 이력, **디자인 무붕괴 + 성능 확보로 PixiJS v8 계획 수립**" 지시.

### 타당성 검토 결론 (read-only, 2026-07-13 세션)
- **잔존 병목**: rebuild 축(§73 메모이즈)·방출 수 축(§61/§65/§67)은 해소 — 남은 것은 G6 Canvas immediate-mode 의 **매 프레임 화면 안 전 도형 CPU 재래스터**(~1ms/노드, ADR-030) + §76 팬 중 rAF 재-emit. 화면 안 500+ 요소 팬은 앱 측 최적화로 60fps 불가(구조적).
- **게임/시뮬레이터 엔진(Unity/Unreal/Godot/Bevy) 기각**: 성능 이득 원천은 "GPU 상주 씬"이라는 WebGL/WebGPU 일반 속성 — 웹 스택으로 동일 획득 가능. 게임엔진 고유 부담(수십 MB WASM·C#/Rust 툴체인·DOM(상세 패널 2,237줄)↔엔진 브리지·한글 IME/접근성·PB-0008 파이프라인 부정합)만 남음.
- **결합도 실측**(서브에이전트 인벤토리): 그래프 JS ≈5,491줄 중 G6 직접 결합 ~700–900줄(15–20%). 레이아웃·메모이즈·LOD 판정·모델·DOM 패널 전부 엔진-중립 → 패리티 이식 국소적.
- G6 WebGL 재번들 스파이크는 사용자 결정으로 기각(과거 디자인 실패 이력 — ADR-004 배경 ③⑤).

### 계획 정착
- `pixi-migration/BLUEPRINT.md` 신설 — 디자인 보존 계약 D1~D6(hard gate: 벡터 테셀레이션·점선 3종 등가·오버레이 hack 무재도입·한글 라벨 전략 POC 확정·상태 bake 철학 유지·커스텀 미니맵) + Phase A(POC, exit gate)/B(SceneAdapter 통합)/C(PB-0008+배포) + 리스크 R1~R7.
- TASK.md §78 Implementation Plan(§7.1) — **plan-review 상태, Major(§12.3), 사람 승인 대기(§12.1)**.
- 순서 게이트(R6): Phase B 는 `feature-0016-minimap-fullview`(graph-core.js 미커밋 수정 중)·`content-cluster` cycle 착지 후. §번호 머지 시 scoped-renumber 허용(§13.1).

### Git 동기화 결과
- 커밋: (본 커밋) `ai/root/feature-0016-graph-pixi` — docs-only(BLUEPRINT/TASK/REPORT/MODIFY/REVIEW).
- Push: **보류** (사유: §16.3 Step 4 — Major plan-review 승인 대기. 승인 후 Phase A cycle 에서 동기화 재개.)

## 2026-07-13 · §78 Phase A POC 완료 — 디자인·성능 exit gate PASS
PLAN-APPROVED(사용자, AskUserQuestion) 직후 같은 세션에서 Phase A 수행.
- **산출물**: `pixi-migration/poc/pixi-poc.html`(정본 스타일 수치 1:1 이식 씬 + 팬/줌 프레임타임 하네스 + `window.poc` 구동 API), `shoot_pixi.py`(Playwright headless 드라이버), `pixi.min.js` 8.19.0 vendored(797KB — g6.min.js 1.38MB 대비 순감).
- **디자인(D1~D5)**: 노드 6종(테이블 역할색 칩·컬럼 dot·루틴 보라칩·SC 카드·combo 점선 카드·ctl)·엣지 6종(trusted/candidate/crossds/routine read/SCHEMA_REF+count)·dim 0.38 bake·한글 라벨 — headless 줌 배율별 + **실 Windows Chrome(PB-0008 relay)** 스크린샷 검수 전항 등가. 과거 WebGL 실패 모드(텍스처 왜곡·점선 소실) 재현 없음(벡터 테셀레이션 + Text resolution 4).
- **성능(실 Windows Chrome)**: idle vsync 18.0/18.1ms(~55Hz) 기준선 대비 — **882노드 등가 씬 팬/줌 p50=p95=18.0/18.1ms = vsync-perfect**(현행 G6 Canvas 는 동급 규모에서 사용자 체감 버벅임이 리포트되던 규모). 11k 스트레스는 무최적화 POC floor 22~31fps(p95 69ms) — GraphicsContext 공유·BitmapText·컬링 도입 전 수치.
- **판정**: BLUEPRINT §4 Exit A 충족(디자인 전항 + 성능 게이트). 다음 = 사용자 육안 확인(win-browser 로 사용자 Chrome 에 디자인 씬 표시함) → Phase B 어댑터 통합. **Phase B 는 R6 순서 게이트**(minimap-fullview·content-cluster cycle 착지) 충족 후 착수.

### Git 동기화 결과 (Phase A)
- 커밋: (본 커밋) `ai/root/feature-0016-graph-pixi` — POC 3파일 + TASK/REPORT/MODIFY 기록.
- Push: 진행 (PLAN-APPROVED Major 진행 중 — BLOCKED 없음, §16.3 Step 4 자동 동기화).

## 2026-07-13 · §78 R6 순서게이트 자연 해소 + 착지분 흡수·테스트 정합
- **R6 해소**: 세션 진행 중 content-cluster(PR #746)·§77 minimap-fullview(PR #747, 배포 c264e3f1 PB-0008 PASS) 가 origin/main 착지 → Phase B blocker 소멸(사용자가 계획한 "나머지 worktree 병합"을 각 소유 세션이 finalize).
- **흡수**: pixi 브랜치 rebase onto origin/main(9커밋). merge-append-doc 드라이버가 TASK/MODIFY/REPORT/REVIEW append 문서를 union 자동병합 — §77/§78 공존·§번호 중복 0. `graph/` 7모듈 origin/main byte-동일 = 착지분 완전 흡수(graph-core.js `nodePosAll`·미니맵 전역개요 실재).
- **테스트 정합**: 그래프 headless 11 스위트 **279 PASS / 0 FAIL**(graph-split 번들 레시피 재현) — 흡수 후 회귀 0.
- **병렬 전략 결론**: SceneAdapter(graph-renderer-pixi.js) 는 신규 파일이라 타 세션과 파일 충돌 0 → Phase B-early(어댑터 신설·scene-spec·adapter 테스트)는 언제든 병렬 가능. graph-core.js **배선**(B-late)만 rebase 재확인 게이트 대상(신규 세션이 그 파일 변경 시). 다른 세션 소유 worktree 병합은 그 세션이 finalize(§13.2 F2 단일 mutator) — 내가 대신 병합하지 않음.

### Git 동기화 결과
- rebase onto origin/main(behind 0) + force-push(내 브랜치·PR 미개설이라 안전). 커밋 3개 유지(해시 재작성).

## 2026-07-13 · §78 Phase B-early — SceneAdapter(PixiJS v8) 신설·실증 완료
사용자 지시(병렬 착수) 수용 — R6 자연해소 후 Phase B 착수. B-early(충돌-독립 신규 파일)부터.
- **산출물**(신규 파일, 타 세션 graph-core.js 변경과 충돌 0): `graph/graph-renderer-pixi.js`(PixiGraphAdapter — G6.Graph 인터페이스 호환, PixiAdapterPure 순수로직 분리) · `graph/SCENE_SPEC.md`(scene-spec 계약) · `tests/headless/test_pixi_adapter.js`(28 PASS) · `pixi-migration/poc/adapter-poc.html`(setScene 실증 하네스).
- **설계 핵심**: scene-spec = `_metaG6Build()` 출력형태(G6 data-shape) 그대로 → B-late 배선이 `setData(built)`→`setScene(built)` 치환만으로 완료(graph-core emission 무변경 목표). combo 는 자식 union bbox 로 auto-fit → G6 auto-fit 제약(ADR-029/030 combo-safe 컬링 제한) 어댑터에서 소멸.
- **검증**: 어댑터 순수 28 PASS(카메라 수학·대시·bbox·hit-grid·diff — 결함 1 적발수정 fitCamera pad:0) + 그래프 회귀 279 PASS 무회귀. 실 Windows Chrome(PB-0008): 디자인 D1~D5 보존(상태 오버레이·한글 라벨·점선 6종·combo)·845 등가 팬/줌 **60fps vsync-perfect(p95 16.8ms)**·이벤트 합성(spatial hit-grid picking) 정확. 이벤트 결함 2 적발수정(좌클릭 팬 클릭소실·dblclick 노드무관).
- **다음**: B-late(graph-core.js 렌더러 seam 배선 + setScene 치환 + admin.html vendor) — 착수 직전 fetch/rebase 로 그래프 변경 재확인(R6 원칙). 이후 미니맵·드래그배치·오브젝트풀·BitmapText 후속 §.

### Git 동기화 결과
- 커밋: `ai/root/feature-0016-graph-pixi` — 어댑터·계약·테스트·POC·docs. Push: 진행(PLAN-APPROVED Major·BLOCKED 없음).
