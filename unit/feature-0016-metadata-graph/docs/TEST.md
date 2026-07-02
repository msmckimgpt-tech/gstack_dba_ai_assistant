---
doc_type: TEST
feature_id: feature-0016-metadata-graph
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 통합 테스트 (라이브 AGE 필요 — CI 에서 AGE 없으면 skip)

### docker/verify-age.sql — Phase 0 (AC-1)
격리 AGE 컨테이너에서 AGE create_graph + Cypher + pgvector(ivfflat/cosine) + pg_trgm(GIN/similarity)
공존 회귀. 실행:
```bash
docker build -f docker/Dockerfile.pg-age -t pg-age:0016-test docker/
docker run -d --name v -e POSTGRES_PASSWORD=v pg-age:0016-test
docker exec -i v psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f - < docker/verify-age.sql
```
2026-06-30 결과: `AGE+pgvector+pg_trgm coexist: PASS` (AGE 1.6.0 · pgvector 0.8.2 · pg_trgm 1.6).

### alembic 0025 — Phase 1a (AC-2 부분)
throwaway 에 마이그 적용 → 멱등 재적용 → 라벨 13개(v6/e7) 확인 → RBAC(rw쓰기/ro읽기/ro쓰기차단).
2026-06-30 결과: 적용+멱등 OK, RBAC 방어심층 PASS(`permission denied for table Product`).
전제: `shared_preload_libraries='age'` 로 기동(앱 role LOAD 불가).

### tests/test_metadata_graph_age.py — Phase 1b (AC-4 부분)
metadata_graph 모듈을 라이브 AGE 에 대해 행위 검증(모듈은 conn 주입 시 shared.db 미import → 단독 가능).
검증: sync 노드/엣지 MERGE · 멱등(노드 중복 0) · 한국어 · Cypher injection 방어 · 검색 · k-hop 이웃.
실행:
```bash
docker run -d --name pgage-t -e POSTGRES_PASSWORD=v -e POSTGRES_DB=agent_kb \
  pg-age:0016-test -c shared_preload_libraries=age
docker exec -i pgage-t psql -U postgres -d agent_kb -f - < <UPGRADE_SQL of 0025>
docker run --rm --network container:pgage-t \
  -v .../metadata_graph.py:/app/metadata_graph.py:ro \
  -v .../test_metadata_graph_age.py:/app/test_metadata_graph_age.py:ro \
  -e PYTHONPATH=/app -e DSN="host=localhost port=5432 dbname=agent_kb user=postgres password=v" \
  python:3.11-slim bash -c "pip install -q 'psycopg[binary]' && python /app/test_metadata_graph_age.py"
```
2026-06-30 결과: `ALL ASSERTS PASS {search_orders:3, search_주문:1, nb_nodes:7, nb_edges:9, orders_node_count:1}`.

## 단위 테스트 (AGE 불요 — 순수 함수)
- `tests/test_metadata_graph_units.py` — `_props_set`(ordinal 정수 리터럴·None 생략·비정수 주입차단) ·
  `_as_int` · `_node_dict`/`_node_from_props`(ordinal 반환). AGE·DB 불요.
  실행: `PYTHONPATH=unit/feature-0002-agent-core/src/modules python3 unit/feature-0016-metadata-graph/tests/test_metadata_graph_units.py`
  **2026-07-01 결과: PASS (8 tests)** — graphux5 ordinal 직렬화·주입방어 검증.
- (예정) `_cq()` 이스케이프 · `_vkey()` 추가 커버.

### graphux5 — 컬럼 세로정렬 + ordinal + 부드러운 엣지 (2026-07-01)
- **순수 함수(위 test_metadata_graph_units.py)**: PASS (8). ordinal 정수 리터럴 SET·주입안전·노드 직렬화.
- **AGE 통합(test_metadata_graph_age.py 검증 4d 추가)**: sync_column(ordinal=1/2) → neighborhood 노드가
  ordinal 보유. **컨테이너 재실행 필요**(AGE) — 배포 시 metadata-graph-sync 후 확인.
- **admin.js 구문**: `node --check` OK.
- **py_compile**: kb_metadata·metadata_graph·app.py·alembic 0027 OK.
- **API e2e (배포 후, 인증 브라우저)**: `GET /api/admin/metadata/columns?scope_key=mssql-06656002eda6` → HTTP 200,
  1030 컬럼 전건 `ordinal` 반환(예: Item 75컬럼 1:TemplateID·2:SortNum·3:Name…, DDL 순). ordinal 파이프라인
  (migration 0027 → column_descriptions → sync → API) 정합 확인.

#### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 2026-07-01 PASS
- 절차: `bin/win-browser.py launch` (Chrome 149, relay mode) → 관리콘솔 `메타데이터 > 🕸 그래프 뷰` →
  데이터소스 `mssql-qa-idc` 선택 → 검색/확장(`_metaGraphExpand`).
- **케이스1 `dk_data_release.Achievement`(4컬럼)**: Table 노드 하단으로 컬럼이 **실제 순서대로 세로 배치** —
  UniqueID(ord1,y65)→Type(ord2,y95)→Title(ord3,y125)→DLC(ord4,y155), x=172(테이블 x=118 +54 들여쓰기).
  Table→Column 연결선이 **직선이 아닌 부드럽게 꺾이는 선(round-taxi)** 으로 아래→오른쪽 트리 라우팅.
  스크린샷: `scratchpad/pb0008-03-columns-below-table.png`(세션 아티팩트).
- **케이스2 `dk_data_release.Item`(75컬럼) 스케일**: 75 HAS_COLUMN 엣지, ordinal top→bottom **단조 정렬**
  (1,2,3…73,74,75) — 대량 컬럼도 순서 정확. (긴 세로 스택은 줌으로 탐색, N1 판독성 MINOR 는 허용범위.)
- **결과: PASS** — 두 사용자 요구(①컬럼 테이블 하단 실제순서 세로배치 ②부드럽게 꺾이는 연결선) 모두 라이브 충족.
  배포 커밋 `git_commit=47d0f1a`, 자산 `admin.js?v=20260701-graphux10`, edge /healthz 200 안정.

#### 박스 벌림 + 박스 클릭/더블클릭 정합 (erd-box-spread-tap) — PB-0008 (Environment: Windows-browser) 예정
- 정적: `node --check admin.js` OK. 실측(라이브 인젝션) 141테이블 compound 전체-스프레드 → 박스겹침 886→0, 109ms. 캐시버스터 `admin.js?v=20260701-erd-spread`.
- **라이브 케이스A (box-spread)**: 밀집 ERD(다수 테이블 박스)에서 테이블 박스 더블클릭 확장 → 신규 박스 등장 시 **박스끼리 겹치지 않게 벌어짐**(카메라는 앵커+신규 이웃으로 프레이밍). term/순수 노드 확장은 전체가 튀지 않고 국소 push(적대리뷰 MAJOR fix 확인).
- **라이브 케이스B (box click/dblclick 정합)**: Table ERD 카드 박스 **단일 클릭 → 상세 카드 갱신**, **더블클릭 → 이웃 확장** (일반 테이블 노드와 동일 동작). 박스 안 컬럼 클릭 → 컬럼 상세. Schema 컨테이너 클릭은 무반응(조직용).
- **검증 게이트**: 위 A·B 모두 실 Windows 브라우저(Chrome relay)에서 확인 후 PASS 기록 + 배포 git_commit·자산 버전 명기.
- **배포 완료(2026-07-01)**: `git_commit=a6bf0eb`(PR #511), soak 통과, 자산 `admin.js?v=20260701-erd-spread` HTTP 서빙 검증(newAddsBox 3건). 그래프 뷰 UI 로드 sanity screenshot PASS.
- **라이브 A·B 인터랙션은 사용자 실화면 확인 요망**: canvas 노드 클릭/더블클릭 필요 → 이번 세션 win-browser eval(Chrome 149.0.7827.200/Playwright UtilityScript 파손)·좌표클릭·native select 전환 미지원으로 자동 불가(메모리 project-pb0008-eval-regression-chrome200). 코드 정합은 인젝션 실측(886→0)+적대리뷰로 확증, 화면 동작 정본은 사용자 확인.

## graphux5 UX 개선 (Phase 6, 2026-07-01)

### 정적 검증 (AGE/라이브 불요)
- [x] py_compile: `shared/config.py`, `modules/{metadata_graph,node_analysis,llm,insight}.py`,
      `alembic/.../0026_node_analysis.py`, `app.py` — ALL OK.
- [x] `node --check static/admin.js` — OK.
- [x] `bin/migrate-lint.sh --base main` — 0026 **expand-safe PASS**(순수 CREATE TABLE/INDEX/GRANT, 비가산 없음).

### 라이브 검증 대상 (AGE + web 컨테이너 필요 — cutover 완료 상태)
- 항목1: `GET /api/admin/metadata/graph?q=<term>` 응답 node 에 `score`(0~1) 존재 + score DESC 정렬.
  프론트: 노드 라벨 `이름  NN%` 표시, 상세 헤더 "유사도 NN%" 배지.
- 항목2: 상세 "✨ 능동 분석" → `POST .../graph/analyze` 202 + run_id. insight-worker 틱이 node_analysis_jobs
  소비 → 이웃 재귀 enqueue(예산 캡). `GET .../graph/analyze?run_id=` done_keys 증가, 완료 노드 보라 마커.
  `GET .../graph/analyze/node?node=` 에 summary/relationships/usage/caveats.
- 항목3: 컬럼 미큐레이션 Table 더블클릭 → `GET .../graph/columns` 즉석 introspection → Column 노드 전개.
  실패 시 status 에 명확 사유(silent no-op 아님).
- 항목4: 이웃 깊이 드롭다운 변경 → 선택/최근 노드 즉시 새 깊이 재전개(화면 갱신).

### 단위 테스트 (예정 — 순수 함수)
- `node_analysis._clamp` 경계 · `_build_payload` 이웃 cap · enqueue 중복 run 재사용.

### 앵커-상대 관련도 게이팅 (node-analysis-anchor, 2026-07-01)
- 단위: `unit/feature-0002-agent-core/tests/test_node_analysis_relevance.py` (순수함수, DB 불요, pytest testpaths 수집).
  - 실행: `python3 -m pytest unit/feature-0002-agent-core/tests/test_node_analysis_relevance.py -q`
  - Run 2026-07-01 (Environment: unit/pytest): **28 passed** (초기 12 + 2라운드 적대 패널 반영 16). 커버:
    - 토큰화 camel/snake 분해 + 일반어(id/uniqueid/createdAt) drop.
    - `_build_anchor` scope/table_fqn/tokens 도출.
    - `_relevance`: 같은 테이블 컬럼 高 · 교차-제품 UniqueID < _DEEP 임계 · 이름연관 테이블 통과 · 같은제품
      무관 테이블 < _DEEP · Schema=0 · broken=0.
    - `_score_candidates`: **depth0 루트 직속 컬럼(일반명 UniqueID 포함) 무조건 통과(relevance 1.0)** ·
      **depth1 hub 컬럼 확장 시 교차-제품/무관 이웃 탈락, 관련 이웃만 관련도순** · anchor=None 보수적 저하.
    - 2라운드 hardening: content-gate(신뢰·제품만으론 불통과) · 한글 일반어 stoplist(게임/정의/테이블 겹침 배제) ·
      한글 접두/접미 부분연관(중간삽입 회원⊄비회원구매·업적⊄기업적자 배제) · depth ramp nd3 경계 고정 ·
      tiebreak key 전순서 결정 · 신뢰FK 내용발산 제외(precision 트레이드오프 고정).
- 라이브 실데이터 검증 **PASS** (2026-07-01, Environment: 배포된 insight-worker 7bca9b2 내부 프로브, LLM 비용 0):
  실 AGE 그래프 `mssql-06656002eda6:dk_data_release.Achievement`(사용자 예시) → 하위 컬럼 4개 relevance 1.0 통과 +
  **부모 Schema `dk_data_release`(형제 테이블 123개) 탈락(rel 0.0)** = fan-out 지배 경로 차단 정량 확인 +
  AchievementReward(이웃 18) 17컬럼 통과·Schema 탈락. alembic 0029 라이브 적용(live=0029)·web-a/web-b 7bca9b2·
  insight-worker 7bca9b2 재기동 확인.
- 그래프 UI 마커 시각 최종(PB-0008): 웹 자산 무변경이라 이번 cycle 하드 게이트 아님 — 후속 시각 확인 권장.

## G6 렌더링 엔진 교체 (ADR-004, 2026-07-02)

Cytoscape(WebGL) → AntV G6 v5.1.1(Canvas) + 결정론적 배치. 설계·POC: `../g6-migration/BLUEPRINT.md`.

### admin.js 구문 — `node --check admin.js` PASS. 제거된 심볼(cy/오버레이/fcose) 참조 0 (grep clean).

### dev-loop 검증 (Environment: WSL-headless-harness, Playwright chromium) — 2026-07-02 PASS
포팅된 admin.js 그래프 서브시스템(블록 추출) + 실 admin.html 그래프 마크업 + mock apiFetch(실 응답 shape)로 전 플로우 실증. 스크린샷 `../g6-migration/poc/`.
- **roots**: 스키마 5클러스터 자연정렬 grid(무-shuffle, ④) · 테이블 teal 칩 · 점선(candidate)+실선(trusted) 엣지 복원 · AI 마커 자동(보라 analyzed / 주황 running, `/analyze/status`) · 선명 테두리(2x DPR, ⑤) · **에러/경고 0**.
- **제자리 컬럼 펼침**(②): Payment 펼침 시 위치 유지 + 컬럼 4개 아래 스택 + 타 클러스터 무-재배치 + 카메라 무점프. "−" 컨트롤 표시.
- **재클릭 무접힘**(①): 펼친 테이블 body 재클릭 → `hasCols` 유지(true) = 클릭으론 안 접힘.
- **"−" 접기**: `hasCols` false 로 환원.
- **검색**: `q=achiev` → 매칭 3클러스터만 grid, 정확매치 유사도 크기 가산 + 마커 유지.
- 판정: 관찰 5건(①②③④⑤) + 점선 엣지 복원 전부 통과. ③(오버레이 동기화 지연)은 오버레이 전량 제거로 구조적 소멸(회귀 불가).

> harness 는 WSL headless 라 실 Windows 화면검증을 **대체하지 않음**(AGENTS.md §15.4.1). 아래 PB-0008 이 완료 하드 게이트.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 예정 (실앱 배포 후)
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 확인: roots grid·제자리 펼침·재클릭 무접힘·"−" 접기·더블클릭 이웃확장·검색 유사도 크기·AI 마커·줌/스크롤 동기화(오버레이 지연 소멸)·테두리 선명·점선/실선 엣지.
- 게이트: `bin/win-browser.py` + PB-0008. PASS 기록 시 배포 `git_commit`·자산 버전(`admin.js?v=20260702-graph-g6`) 명기. 브리지 불가 시 미수행 사유 명시(카고컬트 방지) 또는 `GSTACK_SKIP_VISUAL_VERIFICATION=1`.

## 초기 진입 줌아웃 가시성 개선 (graph-initview, 2026-07-02)

스키마-우선 진입(카드→per-schema lazy)+판독 줌 클램프+미니맵/툴바/점프(레이아웃 밀도는 graph-g6b masonry 채택). TASK §25.

### dev-loop 검증 (Environment: WSL-headless-harness, Playwright chromium) — 2026-07-02 **31/31 PASS · 에러 0**
실 admin.html 그래프 마크업 + admin.js `_metaGraph*` 블록(main graph-g6b masonry + graph-perf-bg `_opSeq` 와
병합된 최종본) + mock apiFetch(실 응답 shape) + **대규모 fixture(7 스키마: 200/40/33/12/5/2/0 테이블)**:
- roots: 스키마 카드 7장(테이블수 배지) 렌더, **zoom 0.60(판독선 0.55~1.0 클램프)**, 점프 select 채움(7+1).
- 카드 클릭(`SC:` 라우팅): billing 12 테이블 per-schema lazy 펼침(combo 승격+"XS:" ctl), schemaExpanded 반영.
- 200 테이블 스키마 펼침: **masonry 4열**·truncated 안내·**펼침 전후 zoom 불변(카메라 불점프)**.
- 줌 툴바(실 DOM 클릭): '전체'=클램프 없는 조망(zoom 0.27 허용)·'1:1'=1.0·'−'=0.8·'+'=1.0. 스키마 점프 정상.
- 검색: 결과 3스키마 자동 펼침·유사도 크기·zoom 클램프. 이웃확장: REFERENCES 2엣지(실선/점선) 렌더·교차
  스키마 자동 펼침·**앵커 국소 focus(전체-fit 줌아웃 재발 없음)**. "XS:" 접기 → 카드 복귀. **미니맵 True**.
- 리뷰 회귀 시나리오: **dead-card 복구**(Schema 노드 없는 combo 접기→카드 재클릭 재펼침) · **빈 스키마**
  (미펼침+카드 유지+안내, loaded 비고착) · **카드 연타 단일 fetch**(in-flight 가드) · **혼합버전 구백엔드**
  (mode 무시 응답 → 카드 진입+강등 펼침+loaded 미마킹) · **stale-scope 카드 클릭 blocked**(V-B, 교차 스코프
  오염 없음). pageerror/console error 0.
- harness 로 적발·수정한 결함: ① 동일 스키마 key 의 카드(노드)↔combo 타입 전환 시 G6 setData diff 자식 유실
  → `SC:` 네임스페이스 분리. ② 미렌더 요소 `setElementState` async reject 가 pageerror 로 누출 → renderedIds
  매핑+catch(_metaApplyState/refreshStates 단일 경로).

### 라이브 AGE Cypher 검증 (Environment: live-pg-replica) — 2026-07-02 PASS
`scope_schemas` 의 `count(t)` 집계·`schema_tables` 의 스키마 필터 쿼리를 replica psql 로 실증 —
최대 scope `mssql-06656002eda6`(62 스키마·스키마당 ~257 테이블)에서 301행 0.23s. 구 진입 뷰가 cap 200 으로
전체의 ~1.2% 만 표시하던 규모 실측.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — **Run 2026-07-02 PASS**
- 배포 `git_commit=95b18045`(deploy-web.sh 무중단 롤링+soak 통과), 자산 `admin.js?v=20260702-graph-initview2`·
  `styles.css?v=20260702-graph-initview2` 서빙 확인. 실 Windows Chrome 149(relay). 스크린샷 5매:
  `artifacts/feature-0016-metadata-graph/20260702-graph-initview-pb0008/`.
- **최악 케이스 실측(mssql-06656002eda6, 62 스키마×~257 테이블)**: 그래프 뷰 진입 → **스키마 카드 62장,
  zoom 0.550(판독 클램프 정확 발동)** — 카드 라벨("cc_test · 테이블 257" 등) 전부 판독 가능. 종전 전체-fit
  줌아웃 붕괴(cap 200 테이블 세로 1열, ~1.2% 무통보 표시) 해소를 라이브 확인.
- 카드 클릭(cc_tortusa) → **258 테이블 per-schema lazy 펼침(masonry 4열), zoom 0.550 유지(카메라 불점프)**,
  상태줄 "258개 펼침 — '−' 로 접기" + 우측 클러스터 상세 로컬 렌더(테이블 258 목록). truncated 없음(258<300 정확).
- 줌 툴바 실클릭: **'전체'=0.144 무클램프 조망**(62카드+펼친 combo 전경) · **'1:1'=1.000** · −/+ 동작.
  **스키마 점프** → accountdb 카드 중앙 복귀(판독 줌 보장). **"XS:" 접기** → 카드 복귀+상태줄 안내.
- **미니맵 렌더 확인**, analyzed 마커가 접힌 카드(SC:)에 매핑(accountdb 보라 테두리) — §21 T21.8 미완분(G6 엔진)
  및 masonry(g6b)·논블로킹(perf-bg)·ctxmenu 공존 상태의 통합 시각검증 겸함.
- 실측 방법: 화면 전환·툴바는 실 DOM 클릭, 캔버스 노드 상호작용은 클릭 핸들러 경로 호출(raw CDP eval — 실
  사용자 클릭과 동일 코드 경로; 브리지가 canvas 좌표클릭 미지원, 기존 세션 관례와 동일) + 스크린샷 육안 대조.
  참고: Chrome 200 eval 회귀는 Playwright UtilityScript 한정 — 본 드라이버(raw CDP)의 eval 은 정상(메모리 갱신 근거).

## 후속 (Phase 2~5)
- 투영 API 계약 테스트(cap·scope 격리·빈 그래프 graceful).
- KB 회귀 스위트(`make test`) — AI 정합(Phase 4) 후.
- PB-0008 라이브 브라우저 검증(그래프 UI) — cutover 후.

## graph-ctxmenu — 노드 우클릭 상세 상호작용 (REQ-20260702T113000, 2026-07-02)

우클릭 컨텍스트 메뉴(kind 별) + 관계 상세 패널(방향·신뢰도·근거) + 중심 보기. frontend-only.

### admin.js 구문 — `node --check admin.js` PASS.

### dev-loop 검증 (Environment: WSL-headless-harness, Playwright chromium) — 2026-07-02 PASS (28/28, 적대 패널 반영 후)
그래프 블록 추출 + 실 admin.html 그래프 마크업 + mock apiFetch(실 응답 shape — AGE neighborhood
서브그래프 내부 엣지 포함) harness. 스크린샷·드라이버: scratchpad `harness/` (shot-1~4).
- **A 네이티브 우클릭 경로**: 빈 캔버스 우클릭 → canvas 메뉴(전체 맞춤·초기화) 표시 + 브라우저
  기본 메뉴 차단(capture preventDefault) + Escape dismiss. **PASS**
- **B 노드 우클릭(네이티브)**: `getElementPosition`→뷰포트 환산 좌표 실클릭으로 node:contextmenu
  발화 → 테이블 메뉴(상세/관계 상세/관계 확장 1·2·3-hop chips/중심 보기/컬럼 펼치기/AI 능동
  분석/FQN 복사) 전 항목 표시. **PASS** (emit 폴백 아님 — 실 이벤트 경로)
- **C 관계 상세 패널**: 방향별 그룹(→참조함/←참조받음) + 추정/신뢰 배지·w 값 + 근거 한글
  라벨(FK 스키마 선언/명명 규칙 추정/대화 JOIN 학습) + 상대 노드 설명 + 연관 용어 + 주변
  관계(이웃-이웃) + 행 클릭 = 상대 노드 상세 이동 + 상세 카드 "🔗 관계 상세" 진입 링크. **PASS**
- **D 중심 보기**: 모델 리셋 후 앵커 N-hop 만 로드, 앵커 선택 강조, 상태줄 복귀 안내. **PASS**
- **E hop chip**: 1-hop chip 클릭 → depth=1 로 1회성 확장, 툴바 깊이 select 는 불변(전역 오염
  없음 — 패널 반영). **PASS**
- **F kind 별 메뉴**: Column(소속 테이블 상세·관계 확장, 컬럼 펼치기 없음)·GlossaryTerm(이름
  복사·관계 확장)·클러스터 combo(클러스터 상세·스키마명 복사). **PASS**
- **G 회귀**: 단일클릭 상세+컬럼 펼침 · "−" 접기 정상. **PASS**
- **적대 패널 반영분**(REV-20260702T121500): C9 로컬 조인 컬럼 표기(`customer_id → s1.customers.id`) ·
  D3/D4 중심 보기 지속 칩 + "✕ 전체 보기" 복귀 · H1 엣지 우클릭 메뉴(신뢰/추정 w·근거·양끝
  노드 이동). **PASS**
- **Z 콘솔/페이지 에러 0.**

> harness 는 WSL headless 라 실 Windows 화면검증을 대체하지 않음(AGENTS.md §15.4.1). 아래 PB-0008 이 완료 하드 게이트.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser)
- 커밋 시점 미수행 사유: 배포 스파인(`bin/deploy-web.sh`)이 origin/main HEAD 만 배포하므로
  본 변경은 머지 전 라이브 반영 불가 — **머지·배포 직후 본 세션에서 즉시 수행**하고 Run 결과를
  본 섹션에 후속 기록한다(카고컬트 방지 — 미수행을 수행으로 기재하지 않음).
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 확인: 노드/컬럼/용어/클러스터/빈캔버스 우클릭 메뉴 ·
  관계 상세 패널(방향·신뢰 배지·근거·행 클릭 이동) · 중심 보기 · hop chips · 기본 메뉴 차단 ·
  기존 클릭/더블클릭/접기 회귀 · 자산 버전(`admin.js?v=20260702-graph-ctxmenu2`·`styles.css?v=20260702-graph-ctxmenu`).
- **Run 2026-07-02 (Environment: Windows-browser) — PASS**: 배포 16fc1598(soak 통과) 후 실 Windows Chrome(relay)
  라이브 실측 — 테이블 노드 우클릭 메뉴 전 항목·관계 상세 패널(빈 상태 안내)·중심 보기 지속 칩+"✕ 전체 보기"
  복귀·클러스터 combo 메뉴·Escape dismiss·기본 메뉴 차단·자산 버스터 서빙. 상세·스크린샷 경로는
  feature-0003 `docs/TEST.md` POST-DEPLOY 항목 + `artifacts/feature-0016-metadata-graph/20260702-graph-ctxmenu-pb0008/`.

## graph-initview 후속 — 스키마 카드 우클릭 + 카드 라벨 압축 (schema-card-ctxmenu, 2026-07-02)

미펼침 스키마 카드 우클릭 메뉴 + 카드 라벨의 "테이블" 문자열 제거(개수→우상단 badge). TASK §26.

### admin.js 구문 — `node --check` PASS.

### dev-loop 검증 (Environment: WSL-headless-harness, Playwright chromium) — 2026-07-02 **ctx 10/10 PASS + initview 회귀 31/31 PASS · 에러 0**
그래프 블록 추출 + 실 admin.html 그래프 마크업 + mock apiFetch(7 스키마 fixture, zempty 포함):
- **카드 badge**: `SC:` 카드 라벨=스키마명만("테이블" 문자열 없음), 개수는 우상단 badge(billing→"12", big_schema→"200", 빈 스키마 zempty→"0"). 이름이 카드 전체 폭 확보.
- **접힌 카드 우클릭**: `node:contextmenu`(SC: 라우팅) → 메뉴 열림 — 헤더(스키마 배지+"billing · 테이블 12") + 펼치기(테이블 표시)/클러스터 상세(펼치지 않음)/스키마명 복사. 종전 무반응 결함 해소.
- **펼친 스키마 우클릭**: 펼침 후 "접기 (카드로)" 항목 노출(XS: ctl·combo 양 경로).
- initview 전체 플로우(카드 진입·per-schema 펼침·masonry·줌 클램프·툴바·점프·검색·이웃·접기·미니맵·stale-scope) 회귀 없음.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — **Run 2026-07-02 PASS**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 확인: 스키마 카드 라벨=이름+개수 badge(테이블 문자열 없음)·**접힌 카드 우클릭 메뉴**(펼치기/클러스터 상세/스키마명 복사)·펼친 스키마 우클릭 접기·기존 우클릭(노드/엣지/combo/캔버스)·좌클릭 회귀.
- 게이트: `bin/win-browser.py` + PB-0008. PASS 기록 시 배포 git_commit·자산 버전(`admin.js?v=20260702-schema-card-ctxmenu`) 명기.
- **Run 2026-07-02 PASS**: 배포 100535f8(soak 통과) → 실 Windows Chrome 149(relay) 라이브: 62 카드 라벨=이름+개수 badge("테이블" 문자열 0)·접힌 카드 우클릭 메뉴(펼치기/클러스터 상세/스키마명 복사) 표시·"펼치기" 클릭 58테이블 라이브 펼침·펼친 스키마 XS 우클릭 "접기" 항목. 종전 무반응 결함 라이브 해소. 스크린샷 `artifacts/feature-0016-metadata-graph/20260702-schema-card-ctxmenu-pb0008/`.

## graph-initview 후속 — 검색 시 스키마 카드 badge 매칭/전체 (search-badge, 2026-07-02)

검색 시 스키마 카드가 사라지지 않고 badge=`매칭/전체` 로 필터 표기. TASK §27.

### admin.js 구문 — `node --check` PASS.

### dev-loop 검증 (Environment: WSL-headless-harness, Playwright chromium) — 2026-07-02 **initview 33/33 PASS + ctxmenu 회귀 10/10 PASS · 에러 0**
- **검색 카드 필터 뷰**: `search('pay')` → 매칭 스키마 3장 **카드 유지**(combo 0, auto-expand 안 함), badge = **매칭/전체**(billing `2/12`·dbo `1/40`·game_log `1/33`, teal bg). status "스키마 3개 매칭 · badge=매칭/전체".
- **검색 클리어→roots**: `search('')` → roots 복귀, 카드 badge = **전체**(billing `12`, 남색). 검색 없음 표기 원복 확인.
- 회귀: roots 카드 badge 전체·스키마 1개 자동펼침·stale-scope 차단·dead-card 복구·빈 스키마·혼합버전·이웃 확장(neighbor auto-expand 유지)·ctxmenu(SC/XS 우클릭) 전부 PASS.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — **Run 2026-07-02 PASS**
- 대상: 그래프 뷰 검색 시 스키마 카드 badge 매칭/전체. 게이트: `bin/win-browser.py` + PB-0008.
- **Run 2026-07-02 PASS**: 배포 8fcda59c(soak 통과) → 실 Windows Chrome 149(relay, eval 1+1=2 OK), 자산 `admin.js?v=20260702-search-badge` 서빙 확인. `mssql-06656002eda6`(62 스키마): ① roots 카드 badge=**전체**(accountdb 58·AccountDB 33, 남색) ② 검색 `user` 입력 → **스키마 카드 12장 유지(combo 0), badge=매칭/전체(teal)** — accountdb `1+/58`·atum2_db_1 `11+/136`·atum2_db_7 `12+/137`, cap 도달분 `+`(부분 카운트) + status "결과 상한(부분 카운트)" 안내 ③ 검색 클리어 → roots 복귀·accountdb badge `58`(전체 원복). 종전 '검색 시 badge 소실' 결함 라이브 해소 확인. 스크린샷: `artifacts/feature-0016-metadata-graph/20260702-search-badge-pb0008/pb-search-badge-live.png`.

## rel-selfheal 단위 테스트 (2026-07-02, AGE·DB 불요)
- `unit/feature-0002-agent-core/tests/test_relationships.py` — **43건 PASS**(신규 +5; star-export
  3건 합산 시 46 — 이전 "46건" 표기는 합산치였음, QA-F6 정정). 신규: `uniqueid` PK
  name_fk 추론(Achievement/AchievementQuest/AchievementReward 실측 스키마), 파서 qualifier 캡처
  (3-part=db · 2-part 비-dbo 보존 · dbo→'' · 미qualify=''), `_alias_map` (leaf, qual) tuple 갱신.
- `unit/feature-0002-agent-core/tests/test_config_star_export.py` (신규 회귀 가드, 3건 PASS) —
  star-import 소비 모듈이 bare 로 쓰는 config 이름의 **런타임 해석**을 AST 로 전수 검사.
  배경: `AGENT_RELATIONSHIP_*` __all__ 누락 → insight per-schema NameError 3일 조용한 정지(REPORT).
- insight 인접 58건 PASS (test_insight_degraded_backoff / test_mssql_three_tier_insight /
  test_node_analysis_relevance / test_task0255_insight_edge_log / test_task0305_insight_bottleneck).
- 실행(worktree, 워커 이미지 마운트):
  `sudo docker run --rm --entrypoint sh -v <worktree>:/wt -e PYTHONPATH=/wt/unit/feature-0002-agent-core/src:/wt -w /wt repo-ask-worker -c "pip install -q pytest; python -m pytest unit/feature-0002-agent-core/tests/test_relationships.py unit/feature-0002-agent-core/tests/test_config_star_export.py -q"`
- 웹 자산 무변경 — check #13(Windows-browser) 비대상. 라이브 e2e(추론 적재·프로브 신호·그래프 점선)는
  배포 후 REPORT rel-selfheal 항목에 기록.

### tests/test_anchor_relationship_live.py — rel-selfheal 앵커링 (라이브 AGE, throwaway)
`sync_relationship` REFERENCES 끝점의 Table/Schema 앵커링 검증: qualified fqn → Schema→HAS_TABLE→
Table→HAS_COLUMN→Column 체인 생성 · 기존 Table description/source 비파괴(SET 생략) · 레거시 ''-slot
은 Table 미생성(Column 만) · 멱등(재실행 중복 0). 실행: throwaway `kb-pg-age:pg16`(+create_graph/라벨)
에 metadata_graph.py 와 본 파일 마운트(python:3.11-slim, TEST.md 상단 harness 동형).
**2026-07-02 결과: ANCHOR LIVE: ALL ASSERTS PASS.**

### rel-selfheal 적대 패널 반영 후 재검증 (2026-07-02, REV-20260702T052630)
- test_relationships.py **52건**(+9: B-F2 slot 한정 SQL·B-F3 uniqueid shared_key 부정 단언·B-F4
  객체-부재→negative/transient→failed·Sec-F2 클램프·QA-F4 lower 정규화/케이스 보존·default_schema 채움·
  재검증 R-1 미확정-slot failed 유지/확정-slot negative 2건)
  + test_config_star_export.py 3건 + **신규 test_insight_rel_cadence.py 3건**(B-F1 커서 DB별 분리·
  D1a `_is_refresh_due` 게이트 의미론·REINFER≤0 off) + **신규 test_tools_exec_ctx.py 2건**(재검증
  R-2 실행-시점 스냅샷 — primary 복원 후 생존·default_db 폴백) ≈ 서브셋 61건 PASS
  (feature-0002 tests 전체 EXIT=0). py_compile + ruff clean.
- test_anchor_relationship_live.py 는 main()+__name__ 가드로 재구성(QA-F1 — pytest 수집 안전).
  라이브 재실행은 배포 후 정정·재sync 검증과 함께.
