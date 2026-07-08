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

### probe-mssqlfix — MSSQL 프로브 SQL 오류 130 회귀 봉인 (2026-07-02)
- 라이브 실측: insight-worker `probe_edge_failed ... OperationalError(130, ...)` 다수 — 구
  `SUM(CASE WHEN EXISTS ...)` 가 MSSQL 집계식-내-서브쿼리 금지에 저촉(전면 실패).
- 수정 후: `test_dialect_mssql_probe_no_subquery_inside_aggregate`(신규) + 기존 probe shape/escape/
  timeout 3건 정합 유지 — test_relationships.py **53건 PASS**. 라이브 최종 검증 = 워커 재배포 후
  프로브 신호(오류 130 소멸 + pos/neg 전이) 관측.

### graph-reltrace — 접힌 관계 표시 + 관계 클릭 추적 + AI 연동 (2026-07-03)
- **백엔드 라이브 AGE**: dblog 스키마 신규 REFERENCES Cypher 실행 → `account.AccountId → arenabegin.AccountId`
  (conversation·candidate) 반환 확인(FK null-status 포함·broken 제외).
- **프론트 엣지 집계 격리 Node 검증 11/11 PASS**: T1 두 테이블 접힘=테이블-레벨 승격 집계 엣지 1개(status 유지)
  · T2 둘 다 펼침=컬럼-레벨 정밀 · T3 한쪽만 펼침=혼합(컬럼→테이블) · T4 대상 미렌더=엣지 0(graceful)
  · T5 다수 컬럼-쌍 dedupe 1개·count 2·trusted 승급 · T6 intra-table 자기참조 제외.
- **추적 행 산출 검증**: `_metaGraphRelTraceRowsHTML`(실 소스 추출) — self=account 테이블 → 대상
  `arenabegin.AccountId` data-trace 정확·방향화살표·"🔎 추적" 힌트.
- `node --check` admin.js PASS · `py_compile` metadata_graph.py PASS · 신규 함수 참조 심볼 전수 정의 확인.
- **완료 하드 게이트 = PB-0008 실 Windows**(배포 후): 접힌 상태 관계 표시 · 관계 클릭 추적 · AI 결과 추적.

## node-role-viz — AI 능동 분석 완료 테이블 역할 시각 표식 (2026-07-03, TASK §33 / ADR-010)

### 단위 — tests/test_node_analysis_role.py (Environment: CLI, agent 컨테이너) — Run 2026-07-03 PASS
분류체계 계약(NODE_ROLES 8종·규칙 role 정합)·_role_valid 정규화·휴리스틱 이름 1-pass(로그>거래 우선순위,
fqn 세그먼트 폴백)·본문 2-pass·etc 폴백·비-dict analysis 방어·_resolve_role(LLM 유효값 우선/무효 폴백/
Table 외 None) 10건 PASS. 기존 test_node_analysis_relevance.py 28건 회귀 0 (합계 38 PASS).

### 전체 회귀 — pytest feature-0002+0003 (Environment: CLI, agent 컨테이너 worktree 마운트) — Run 2026-07-03 PASS
`python -m pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests` exit 0 (전건 PASS).
(worktree 에 .env 부재로 `make test` 의 dc-build 는 불가 — 기존 agent 이미지 마운트 방식으로 동등 실행.)

### headless harness — 실 admin.html/admin.js/g6.min.js + mock API (Environment: WSL-headless-harness, Playwright chromium) — Run 2026-07-03 ALL PASS · pageerror 0
- T1 미분석 테이블 칩 = teal(#0f7d8c)·라벨 원형·흰 글자 (역할 인코딩 미적용 확인).
- T2 폴 경로: `_metaGraphMarkAnalyzed(keys, roles)` → rAF coalesce → rebuild 로 칩 fill=#E69F00(log)·
  라벨 "📜 PurchaseLog"·어두운 라벨색(#161b22)·캐시서명 `analyzed#R=log`·states=[analyzed] 반영.
- T3 scope sync 경로: `/graph/analyze/status` mock roles → ItemDefine 칩 #0072B2(master)+📘.
- T4 무효 role("banana") 방어: roles 미등록 + 칩 teal 유지.
- 시각 스크린샷: 8종 역할 칩(색+아이콘+보라 분석완료 테두리) + 미분석 teal + 역할 범례 행 렌더 확인.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 배포 후 라이브 Run 을 본 섹션에 append (§15.4.1)
본 cycle 은 deploy_scope: included 로 merge 직후 web+insight-worker 배포 → 라이브 그래프 뷰에서
분석 완료 테이블의 역할 칩 색/아이콘/범례/상세패널 역할 칩을 실 Windows Chrome 으로 육안 확인 예정.
(pre-commit 시점 미수행 사유: 역할 데이터는 alembic 0031 + insight-worker 백필 배포 후에만 라이브에 존재.)

## graph-rel-layout — 관계 기반 배치(교차 최소화) (ADR-012, 2026-07-03)

### Node 격리 로직 (Environment: CLI, node — admin.js 함수 추출) — Run 2026-07-03 **10/10 PASS**
`_metaRelAdjacency`/`_metaRelSchemaOrder`/`_metaRelTableOrder`/`_metaRelOrderAll` 를 소스 추출로 격리 실행:
① 관계 0 → 스키마·테이블 순서가 기존 자연정렬과 동일(회귀 0) ② seriation(B↔D 강연결·C 약연결·A 고립 →
[D,B,C,A]) ③ 컴포넌트 BFS(가중 desc + 외부앵커 + 고립 후미) ④ 나란한 두 클러스터 상호 교차(a↔d,b↔c) sweep
후 0 ⑤ 결정론(같은 입력 2회 = 동일 출력) ⑥ 벌크(30 스키마·300 테이블·시드 고정 400 엣지) 1D 층간 역전
59→52 감소 ⑦ 함수 소스 schemaExpanded 무참조(펼침-비의존 구조 검증) ⑧ `_metaGraphCollapse` 의 REFERENCES 보존(§18.8
패널 MAJOR 회귀 방지 — 접기 제스처의 배치 입력 불변) ⑨ `_metaGraphExpand` rebuild 후 tween-사망 focus 폴백
존재(§18.8 패널 MINOR 회귀 방지). `node --check admin.js` PASS.

### 파라미터 벤치 (Environment: CLI, node — 합성 그래프) — Run 2026-07-03
시드 3종(42/7/20260703) × 토폴로지 2종(랜덤/허브) × SPAN{4096,30,10,1} × barycenter pass 수 매트릭스:
2D 세그먼트 교차(shelf 근사 기하) 전 구성 12~30% 감소, SPAN=1 이 6구성 중 5 최선(채택), 4-pass 수렴 확인.
SPAN=4096 은 1D 층간 역전을 되레 증가(59→74)시켜 기각 — ADR-012 Alternatives 참조.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 배포 후 라이브 Run 을 본 섹션에 append (§15.4.1)
본 cycle 은 deploy_scope: included 로 merge 직후 web 배포 → 라이브 그래프 뷰에서 ① 관계 많은 스키마 카드가
인접 배치 ② 펼친 스키마 안 연결 테이블 군집 ③ 관계선 교차가 자연정렬 대비 감소 를 실 Windows Chrome 으로
육안 확인 예정. (pre-commit 시점 미수행 사유: 배치는 라이브 관계 데이터 규모에서만 육안 판별 가능 — 배포 선행.)


### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — **Run 2026-07-03 PASS (POST-DEPLOY, graph-rel-layout)**
배포 web-a/b `5f439788`(무중단 롤링·soak 통과) 후 실 Windows Chrome/149(relay `http://172.26.144.1:9223`,
`https://localhost/admin` 인증 세션)로 그래프 뷰(mysql-gz-dev · gunzgame 테이블 120 · REFERENCES 165) 검증:
- 신 자산 강제 로드 확인: `admin.js?v=20260703-graph-rel-layout` 서빙.
- **② 관계 군집(핵심)**: 페이지 내 실측정 — 관계쌍(115쌍) 평균 배치 순서 거리 **32.5 → 3.2 (90% 감소)**.
  육안: account·character·usergrade·accountitem·friend / medalshop·cashshop·rentcashshopprice30day·
  cashshopnewitem / item·reward 군집 인접 배치, 관계선 단거리 정돈(스크린샷 pb0008-rel-layout-01-clustered.png).
- **③ 교차 감소**: 군집화로 장거리 관계선 소멸 — 육안 교차 현저 감소(같은 스크린샷).
- **① seriation**: 라이브 전 scope 스키마 간(cross-schema) 관계 0행 실측(SSOT 조회) → 스키마 카드 순서
  자연정렬 유지 = 설계 정합(무관계 강등 없음). 알고리즘 자체는 격리 테스트 t2·t4 검증.
- **④ collapse 불변(§18.8 MAJOR 수정 실증)**: account 컬럼 4개 접기 → REFERENCES **145→145 보존**·배치 순서
  **완전 불변**·관계선 유지(스크린샷 pb0008-rel-layout-02-collapsed-refs-kept.png).
- 회귀 스팟: 이웃 확장(`_metaGraphExpand`) nodes 125→133 정상 병합·pageerror 0 · 검색 모드
  (`_metaGraphSearch('character')`) 스키마 카드 badge 매칭 정상·pageerror 0.

## graph-simgroups — 유사 속성 그룹 영역화 (ADR-013, 2026-07-03)

### Node 격리 (Environment: CLI, node — 실 _metaG6Build 구동 + 실측 fixture) — Run 2026-07-03 **25/25 PASS**
admin.js 에서 _metaG6Build + 의존 25종을 소스 추출해 실측 gunzgame fixture(테이블 68·관계 145, SSOT 조회)로
구동: ① family 유의미성(character·shop suffix·cash 스템) ② 그룹 무결성(전량 1회 커버·misc 후미·싱글턴 흡수)
③ 배경 박스 상호 무겹침·모든 칩 중심이 정확히 자기 그룹 박스 1개 안·헤더 박스 내 포함 ④ 칩 무겹침(68/68)
⑤ 결정론(2회 JSON 동일) ⑥ 펼침-불변(컬럼 3개 펼침 → 전 칩 x 불변·무상승·펼친 후 무겹침) ⑦ 평면 폴백
(유사성 없는 3 테이블 스키마 → GB: 0, 기존 masonry) ⑧ 엣지 조립 보존(REFERENCES 승격 유지·GB/GH 끝점 0)
⑨ 빌드 평균 7.5ms + §18.8 수정 회귀방지 ⑩ view norm 가드(viewer 미절단·view_ 절단) ⑪ 2차 attach 무연쇄(fam1 스냅샷) ⑫ GB:/GH: 클릭 클러스터 상세 위임. `node --check` PASS. 그룹 산출: character(14) item(17) characterinfo(4) battletimereward…(4)
…shop(3) mission(4) clanmember(3) attendence(3) account(3) 등 13 + 기타(2).

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 배포 후 라이브 Run 을 본 섹션에 append (§15.4.1)
본 cycle 은 deploy_scope: included 로 merge 직후 web 배포 → 라이브 그래프 뷰(gunzgame 등)에서 ① 유사 속성
그룹 배경 박스·헤더 칩 렌더 ② 영역 단위 가시성(칩 나열 대비) ③ 컬럼 펼침/접기·테이블 드래그·검색·역할칩
회귀 0 을 실 Windows Chrome 으로 육안 확인 예정. (pre-commit 시점 미수행 사유: 배포 선행 — deploy-web.sh 는
origin/main HEAD 만 배포, 그룹 시각 판별은 라이브 관계·이름 데이터 규모 필요.)

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — **Run 2026-07-03 PASS (POST-DEPLOY)**
배포 web-a/b `abc78b00`(무중단 롤링·soak 통과) 후 실 Windows Chrome/149(relay `http://172.26.144.1:9223`,
`https://localhost/admin` 인증 세션)로 그래프 뷰(mysql-gz-dev · gunzgame 스키마 펼침, 테이블 115) 검증:
- 신 자산 강제 로드: `admin.js?v=20260703-graph-simgroups` 서빙 + `_metaSimGroups` 정의 확인.
- **① 유사 속성 그룹 박스·헤더(핵심)**: 캔버스에 **그룹 배경 박스 22개 + 헤더 칩 22개**(스템 라벨·개수) 렌더 —
  item·21 / character·17 / account·6 / battletimereward… / …grade·2 / blitzkrieg…·4 / …ranking·3 / mission·5 /
  …type(currencytype·gametype·renttype·servertype) / attendence 등. 테이블 칩 115개가 각 그룹 박스로 구획.
  (스크린샷 simgroups-01-boxes.png, 02-detail.png)
- **② 영역 단위 가시성**: "균일 칩 평면 나열"이 색 배경 박스 + 라벨 헤더로 영역화 — 유사 속성 범위가 시각적으로 노출.
- **③ GB/GH 데드존 수정(§18.8 MAJOR 실증)**: 그룹 배경 박스 클릭 → 클러스터 상세 패널 렌더(스키마 클러스터
  표기)·상세 목록에 그룹 헤딩 43개 + role="group" aria + (shown/n) 절단표식 노출. pageerror 0.
- **④ 회귀 0**: account 컬럼 펼침 11개(이웃확장 경로) · 컬럼 접기 후 REFERENCES **145→145 보존**(§38) ·
  검색 모드(`_metaGraphSearch('character')`) 정상 진입 · 전 경로 pageerror 0.

## graph-product-cat — 제품(Products) 단위 카테고리 (ADR-014, TASK §43, 2026-07-03)

### 케이스
- TC-43-1 (백엔드 합성): `?mode=products` 가 활성 제품마다 `Product`(key=`product:<id>`) 노드 + 바인딩
  datasource 마다 `Datasource`(key=`ds:<scope_key>`) 노드(dedup) + `USES` 엣지를 반환. `?product=<id>` 는 단일 제품.
- TC-43-2 (read-axis 정합): 합성 datasource key 의 scope 가 datasource-scoped 그래프 read 축(`scope_key or 라벨`)과
  일치 — `ds:` drill 이 실 스키마 그래프를 로드(빈 그래프 아님). DB-등록=해시·.env=라벨 양쪽.
- TC-43-3 (배너): datasource 진입(scope_roots/schemas) 응답 `products` 필드로 소속 제품명 상태 배너 표시.
- TC-43-4 (프론트 렌더): 제품 개요 진입 시 `_metaG6BuildProducts` 2-열(Product 좌·Datasource 우) + USES 엣지,
  datasource 노드 클릭 → 그 데이터소스 스키마 그래프 drill, Product 클릭 → 단일 제품 focus.
- TC-43-5 (회귀): datasource/schema 그래프 경로·검색·이웃 무영향. 권한 `metadata.graph.read` 보존. mutation 0.

### Run (2026-07-03) — pre-deploy 격리 검증
- `node --check admin.js` **PASS** · `ast.parse admin_metadata.py` **PASS**.
- 격리 pytest(repo-agent 이미지 + worktree 마운트, PYTHONDONTWRITEBYTECODE=1): `test_permission_dependency_map.py`
  + `test_metadata_graph_units.py` **28 PASS**(DI 권한 맵·metadata_graph 단위 무회귀 — 엔드포인트에 `conn=Depends`
  추가가 권한 게이트·투영 모듈 불변 확인).
- §18.8 적대 리뷰(general-purpose): read-axis MAJOR + 비숫자 product NIT 반영 후 PASS-WITH-FIXES (REV-20260703T091737).
- **POST-DEPLOY 실 Windows 브라우저(PB-0008) = PASS(2026-07-03, 배포 `4f34e5fa`)**: 실 Windows Chrome 실측 —
  제품 개요 "제품 카테고리 15개 · 데이터소스 18개" 렌더(Product/Datasource 노드 + USES 엣지 + 툴바 버튼) · datasource
  drill(`mssql-dk-dev`) → **스키마 11개**(비어있지 않음 = read-axis fix 실증) + 제품 배너 "제품: DK온라인 - 개발" ·
  pageerror 0. 정본 Run: feature-0003 TEST.md §3 `Environment: Windows-browser`(스크린샷 pb0008-product-overview.png).

## graph-freeplace — 클러스터 자유 배치 상호작용 복원 (ADR-015, TASK §44, 2026-07-03)

### 케이스
- TC-44-1 (#2 클러스터 드래그): combo 또는 접힌 스키마 카드를 드래그 → clusterOffset 누적 → 클러스터 전체(카드·테이블·
  컬럼·장식) coherent 이동 + 펼침/접기 rebuild 후 위치 유지.
- TC-44-2 (#3 노드 이동 반응형 리사이즈): 클러스터 내부 테이블 드래그 → nodePos 기록 → 테이블+종속(컬럼·"X:") 델타 시프트 +
  combo auto-fit 리사이즈 + rebuild 유지.
- TC-44-3 (#1 접기/펼치기): 스키마 카드↔펼친 combo 전환 유지(회귀 0).
- TC-44-4 (정합 불변식): 테이블 개별 이동 후 클러스터 통째 이동 → 그 테이블도 동반(분리 없음, 리뷰 MAJOR fix).
- TC-44-5 (리셋): 스코프 전환·초기화 버튼 → clusterOffset/nodePos clear(결정론 배치 복귀).

### Run (2026-07-03) — pre-deploy 격리 검증
- `node --check admin.js` **PASS**.
- §18.8 적대 리뷰(general-purpose, 6축): 좌표프레임 정합(getElementPosition=center=build tx/ty, 점프 없음)·offset 수학·
  drag pairing·G6 combo drag 확인. MAJOR 1(nodePos override 분리) + NIT 1(컬럼 dead) 반영 → PASS-WITH-FIXES (REV-20260703T101622).
- **POST-DEPLOY 실 Windows 브라우저(PB-0008)**: 배포 후 4-상호작용 수동 검증 예정(접힌 카드 드래그·combo 드래그·테이블 드래그+
  펼침·접기/펼치기 회귀) — feature-0003 TEST.md §3 `Environment: Windows-browser`. 라이브 canvas 드래그 자동화 곤란 → 실 Windows 게이트.

### Run (2026-07-04) — graph-ux3fix(§45) 격리 검증
- `node --check admin.js` **PASS**. clusterBase 완전 제거(grep 잔존 0)·검색 glow(searchMatchNodes/match state)·loadedScope 배선 무결.
- **§18.8 3-렌즈 적대 리뷰(general-purpose)**: (A) 레이아웃 clusterBase, (B) IA/탭/권한 배선, (C) 검색 highlight — 각 렌즈 diff+함수컨텍스트 제공, 실패 시나리오 요구. 확정결함 3건: (A-HIGH) 위치고정 겹침→②되돌림, (B-MED) 크로스탭 scope stale→loadedScope 수정, (C-LOW) 라벨 넘침→클램프. 나머지 축(dangling ref·권한 가시성·mode 게이팅·G6 shadow 안전·rel 상세배지·req②③④ trace) clean. REV-20260704T014646.
- 격리 알고리즘 테스트(scratchpad): clusterBase sticky 불변식 15/15 PASS(원점 불변·신규 아래 배치·드리프트 0) — 단 적대리뷰가 카드→combo 겹침 회귀를 별도로 적발해 해당 접근을 되돌림(알고리즘 자체는 정합이나 부작용이 치명).
- **PB-0008 실 Windows 시각검증(하드 게이트, visual_verification_scope: always)**: `Environment: Windows-browser` — **무인 세션 3중 라우팅 벽으로 미수행**(TrustedHostMiddleware·인증세션·Windows→WSL). 검증 항목: ① `지식베이스 > 그래프 뷰` 탭 분리·전체 높이·데이터소스 select 로 스키마 그래프 로드 ③ 검색어 입력 시 매칭 노드가 앰버 glow 로 강조(너비 불변)·비검색 복귀 시 glow 소멸. **사용자 육안 확인 후 배포** — 미수행 사유 명시(카고컬트 방지, FIRST_REQUEST.md 정책). 정본 Run: feature-0003 TEST.md §3.
## graph-funcproc-uxfix — 함수·프로시저 노드 + 그래프/능동분석 UX 4건 (2026-07-03, TASK §45 / ADR-016·017)

### 단위 — tests/test_graph_funcproc_uxfix.py (Environment: unit/pytest, DB 불요) — Run 2026-07-03 **19 PASS** (§18.8 패널 수정 반영 후)
- ① 정의 파싱: read/write kind 분류(FROM/JOIN vs INSERT/UPDATE/DELETE)·write 우선 dedupe·임시(#)/변수(@)/
  미존재/자기자신 제외·3-part 인용 식별자 leaf 정규화·빈 입력. introspect_and_store: routine_objects
  upsert 형태(ON CONFLICT 4키·store_schema 라벨·참조 fqn 라벨 접두·params/반환형 pos0).
- ① sync_routine Cypher: `MERGE (n:Routine {key: '...usp_GiveReward()'})`(동명 테이블 충돌 방지 `()`
  네임스페이스)·routine_type SET·HAS_ROUTINE·ROUTINE_USES relation_type·참조 Table 앵커링. 라벨/속성
  화이트리스트(Routine·HAS_ROUTINE·ROUTINE_USES·routine_type/params) 등재 확인.
- ③ parent 승격: _fetch_context 가 Column 의 부모 Table 을 parent 메타로 기록 → _score_candidates 승격
  (rel≥0.5·same_depth=True·교차 제품 감쇠<0.5) → _enqueue_neighbors 가 depth_budget 마지막 층에서도
  부모를 same-depth 로 삽입(일반 이웃은 예산 초과 미삽입 — 경계 검증).
- ⑤ user_prompt: enqueue INSERT 저장(strip·마지막 파라미터)·마이그 창(UndefinedColumn) legacy 폴백·
  _load_anchor 지침 토큰 합류(결제/환불 + 기존 앵커 토큰 보존)·ROUTINE_USES 이웃 content 인정.
- 실행: `python3 -m pytest unit/feature-0002-agent-core/tests/test_graph_funcproc_uxfix.py -q`

### 회귀 — pytest (Environment: unit/pytest) — Run 2026-07-03 **107 PASS · 실패 0** (합계 126 — §18.8 패널 BLOCKING 1·MAJOR 5 전량 수정 후 재실행; 패널 정본 REVIEW.md REV-20260703T113500-graph-funcproc-uxfix)
`test_node_analysis_relevance.py`(28 — _score_candidates 3-tuple 반환 확장에 맞춰 unpack 갱신) ·
`test_node_analysis_role.py`(10) · `test_config_star_export.py`(AST 가드 — 신규 AGENT_ROUTINE_* __all__
등재 통과) · `test_relationships.py`(57) · `test_metadata_graph_units.py`(10). `node --check admin.js`
· `python3 -m py_compile`(변경 py 전건) PASS.

### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 배포 후 라이브 Run 을 본 섹션에 append (§15.4.1)
본 cycle 은 deploy_scope: included 로 merge 직후 web+insight-worker 배포 + alembic 0034 적용 →
라이브 그래프 뷰에서 ① ƒ/⚙ 함수·프로시저 칩 + 보라 잔점선(테이블 사용) ② 상세 패널 리사이즈 시
미니맵 우하단 추종 ③ hover 지침 popover → 분석문 반영 ④ 분석 완료 box 재분석 버튼 부재 를 실
Windows Chrome 으로 육안 확인 예정. (pre-commit 시점 미수행 사유: Routine 노드는 alembic 0034 +
insight-worker routine introspect 첫 cadence 이후에만 라이브에 존재 — 배포 선행 필요.)

## semantic-embed — 메타데이터 의미 임베딩·클러스터링 (Phase C, ADR-018, TASK §46, 2026-07-03)

### 케이스
- TC-46-1 (마이그): alembic 0035 가 rag_objects 에 3 nullable 컬럼+인덱스2 를 비파괴 적용(카탈로그 전용·<1s), head=0035, migrate-lint expand-safe, downgrade DROP.
- TC-46-2 (시그니처): run_signature_backfill_pass 가 table 객체마다 결정론 시그니처를 texts 에 적재(strip-hash=join-key 정합) + signature_text_hash set. 변경 없으면 no-op(멱등).
- TC-46-3 (임베딩): 기존 embedding 데몬이 시그니처 texts 를 bge-m3 1024d 임베딩(신규 경로 0).
- TC-46-4 (클러스터): scope 별 kNN(τ)+union-find, degree-cap chaining 억제, N>FULLMATRIX_MAX_N skip, cluster_id 결정 배정, un-cluster=NULL.
- TC-46-5 (투영·프론트): AGE Table 정점 cluster_id/label → scope_roots/schema_tables RETURN → _metaSimGroups be: 그룹(≥2), 없으면 affix 폴백. un-cluster=phantom 없음.
- TC-46-6 (kill switch/회귀): AUTO=0 데몬 미기동. 기존 pgvector RAG·category_* 무영향.

### Run (2026-07-03) — pre-deploy 격리 검증
- `node --check admin.js` **PASS** · py ast(semantic_cluster/insight/metadata_graph/config/0035) **PASS** · `migrate-lint` **PASS(expand-safe)**.
- 순수함수 격리(컨테이너 numpy) **4/4 PASS**: 시그니처 결정론·commonAffix 라벨·kNN+union-find(degree-cap distinct 노드 분리)·MAJOR-1 strip-hash 정합.
- metadata_graph 회귀(test_metadata_graph_units + test_sync_graph_from_relational) **10 PASS**(sync_table/scope_roots/schema_tables 변경 무회귀).
- §18.8 2단계 적대검증(설계 워크플로우 + 구현 리뷰): MAJOR-1/MAJOR-2/MINOR-3 반영. REV-20260703T160303.
- **POST-DEPLOY**: alembic 0035 라이브 적용 + web/insight-worker 재배포 + PB-0008(그래프 렌더·affix 폴백 무회귀·pageerror 0; 클러스터 값은 데몬 cadence 후 eventual — feature-0003 TEST.md §3 Windows-browser Run).

## crossds-rel — 크로스-데이터소스 관계 (Phase B, ADR-019, TASK §47, 2026-07-04)

### 케이스
- TC-47-1 (마이그 0036): table_relationships 에 source/target_datasource_key + 7-col UNIQUE + CHECK 'manual' + ds 인덱스 2 를 비파괴 적용(backfill src_ds=tgt_ds=datasource_key). head=0036, migrate-lint ACK.
- TC-47-2 (ON-CONFLICT 불변식): upsert 7-col ON CONFLICT == 최신 마이그 UPGRADE 7-col UNIQUE (head-aware 테스트).
- TC-47-3 (프로브 가드): fetch_probe_candidates 가 src_ds=tgt_ds 만 반환 → 크로스-ds candidate 영구 유지(파단 없음).
- TC-47-4 (manual 승격): source='manual' upsert → status='trusted'(_TRUSTED_SOURCES + DO UPDATE). 크로스-ds 유일 승격 경로.
- TC-47-5 (컨텍스트 제외): _fetch_relationships 가 크로스-ds candidate 제외(trusted만), [교차DB] 마커. 9-col caller 호환.
- TC-47-6 (그래프 투영): 크로스-ds 엣지 각 끝점 자기 datasource scope 앵커(cross_ds), neighborhood 자동 노출. intra-ds/794 레거시 scope byte-보존.
- TC-47-7 (추론, 데몬 OFF): infer_cross_datasource — effective schema(MSSQL DB명)·유사도≥MIN_SIM·공통 keyish 컬럼·reverse-dup 카논화·per-ds cap.
- TC-47-8 (UI): 크로스-ds 엣지 마젠타 점선(same-ds candidate 골드와 구분).

### Run (2026-07-04) — pre-deploy 격리 검증
- `node --check admin.js` **PASS** · py ast(relationships/metadata_graph/node_analysis/insight/config/0036) **PASS** · `migrate-lint` **ACK**(서명 annotation, contract 2-phase 전제·fail-soft).
- pytest **67 PASS**(test_relationships 전체 — head-aware ON-CONFLICT==UNIQUE 불변식 포함 + metadata_graph 회귀). semantic_cluster._effective_schema import OK.
- §18.8 2단계 적대검증(설계 워크플로우 + 구현 리뷰): **SHIP for inert deploy**(데몬 OFF). flip-전 블로커 MSSQL effective schema(MAJOR)·negative-decay 가드·reverse-dup·cap 반영. REV-20260704T043653.
- **POST-DEPLOY**: alembic 0036 라이브 적용 + web/insight-worker 재배포 + PB-0008(그래프 렌더·관계 무회귀·pageerror 0; 크로스-ds 엣지는 AUTO=1 flip + 임베딩 populate 후 eventual — feature-0003 TEST.md §3 Windows-browser Run).

## graphux7 — 그래프 뷰 UX 7건 (TASK §48, 2026-07-04)

### 케이스
- TC-48-1 (#1 이력): 노드 A→B→C 상세 조회 후 '뒤로'가 B→A, '앞으로'가 B→C. 새 노드 방문은 forward 분기 절단. 이력≤1 이면 nav 바 숨김, 끝단 버튼 disabled. datasource 전환 시 초기화. 뒤로/앞으로 네비 자체는 이력에 재기록 안 됨(_histNav).
- TC-48-2 (#2 관계 클릭): 관계 행 단일 클릭 = 카메라 팬만(상세 패널 = 원 노드 유지)·더블클릭(≤260ms) = 대상 상세로 전환. 키보드 Enter = 전환. 대상이 접힌 스키마면 그 카드로 팬.
- TC-48-3 (#3 범례 탭): 상단 flat 바 제거·상세 패널 하단 3탭(노드 종류/관계·AI 상태/테이블 역할) 렌더. 탭 클릭·←/→ 로 패널 전환(hidden 토글). pg_trgm 유사도 문구 부재. 역할 칩 hover 툴팁(_metaRoleLegendTips) 동작.
- TC-48-4 (#4 중복 큐잉): 진행 중 노드에 재-분석 클릭 → 새 run 미생성(백엔드 reused) + "이미 진행 중(진행 N/M)" 메시지. 연타 시 in-flight 가드로 동시 POST 1건만. 진행 패널 상태 가시.
- TC-48-5 (#5 라벨): sample-feedback 스코프칩·용어 관계 scope 태그가 해시(mssql-xxxx) 아닌 사용자 라벨 표시. common→'공용'. 미등록 scope→원문.
- TC-48-6 (#7 접기): 스키마 펼침 후 상세 패널(항상 화면 내)에 "▦ 접기" 버튼 표시 → 클릭 시 카드로 축소. 접힌 스키마엔 버튼 미표시. body 클릭으로는 접히지 않음.
- TC-48-7 (#6 무변경 근거): getElementPosition=world 좌표(viewport=world×zoom) 실측 — 클러스터 offset 누적 줌-정합, 앱 좌표 결함 없음. 코드 무변경.

### Run (2026-07-04) — pre-deploy 격리 검증
- `node --check admin.js` **PASS** · `py_compile` node_analysis.py·admin_metadata.py **PASS**.
- 최신 main(7facb804) rebase — 자동 병합 무결(제 상태 필드·#4 와 main Esc-fix·Phase B/C 공존), admin.html cache-buster 충돌만 해소. cache-buster `admin.js?v=20260704-graphux7`·`styles.css?v=20260704-graphux7`.
- §18.8 적대 리뷰 REV-20260704T071838-graphux7. 라이브 관측(win-browser 실 Chrome): #5 라벨·#6 좌표계·#7 "−" off-screen 확인.
- **POST-DEPLOY**: web 재배포(정적 자산 baked, 마이그 없음) + **PB-0008 실 Windows 브라우저** — #1 nav 바·#2 단/더블·#3 3탭 렌더·#4 reused 메시지·#5 라벨·#7 접기 버튼 시각검증, pageerror 0 (feature-0003 TEST.md §3 Windows-browser Run).

## graph-zorder — 그래프 뷰 z-order 의미 정합 (TASK §52, 2026-07-04)

### 케이스
- TC-52-1 (bake 전수): _metaG6Build/_metaG6BuildProducts 산출 전 요소(combos/nodes/edges — SC/XS/GB/GH/GX/X/테이블/루틴/용어/컬럼/제품/데이터소스/전 엣지 스타일)가 _METZ 의미 계층 zIndex 를 갖는다. 삽입순(renderOrder) 의존 없음.
- TC-52-2 (드래그 복원): 테이블/카드/그룹(GB·GH)/combo 드래그 종료 후 대상+종속의 zIndex 가 canonical(_metaZFor)로 복원된다 — 드래그 이력이 z-order 로 잔존하지 않음(내장 frontElement 영구 승격 상쇄).
- TC-52-3 (드래그 중 계층): 드래그 중 대상+종속(컬럼·ctl/그룹 묶음)이 함께 부스트 층(+1000)으로 떠서 칩만 뜨고 컬럼이 남는 계층 찢어짐이 없다.
- TC-52-4 (GB hit-test 회복): 그룹 배경(GB, z1) 빈 공간 드래그 = 그룹 이동(클러스터 아님). 클러스터 이동은 combo 여백/라벨/접힌 카드로 가능. GB 클릭=스키마 상세·우클릭=스키마 메뉴 유지.
- TC-52-5 (성질 변경 불변): 스키마 카드↔combo 전환·그룹 접힘↔펼침·컬럼 펼침·검색·역할(role) 도착 rebuild 후에도 계층 불변(신규 요소가 기존 요소 위로 튀지 않음).
- TC-52-6 (엣지 계층): REFERENCES/ROUTINE_USES/USES 엣지가 배경(combo·GB) 위·컬럼/칩 아래 — 이웃 확장으로 늦게 추가된 엣지도 동일.
- TC-52-7 (오버레이 무회귀): 미니맵(z5)·focus chip(z5)·컨텍스트 메뉴(z10000)·ai-pop/progress(in-flow) 표시 무회귀. pageerror 0.

### Run (2026-07-04) — pre-deploy 격리 검증
- `node --check admin.js` **PASS**. zIndex bake 16개소 정적 전수 확인(빌드 nodes/edges/combos push 지점 대조 — 누락 0).
- vendored g6.min.js API 확인: `setElementZIndex(id→z 맵)`·`getElementZIndex(id)` 존재, 내장 drag-element 의 `frontElement(this.target)` onDragStart 호출 실측(minified 소스 grep) — 근본 원인·복원 경로의 번들 정합 확인.
- §18.8 적대 패널(ux·design·frontend correctness 3-렌즈) — design PASS(MINOR 2 반영), ux FAIL→전건 해소(BLOCKING: 콤보 내부엣지 미복원 → _metaComboEdgesRestore · MAJOR: __terms__ 오판/GB 어포던스 · MINOR: X: ctl NODE 밴드), frontend 잔여 포인트 메인 세션 직접 검증. 상세 REVIEW.md REV entry. 반영 후 node --check 재PASS.
- **PB-0008 실 Windows 시각검증(하드 게이트, visual_verification_scope: always)**: pre-commit 시점 미수행 사유 — 정적 자산이 web 이미지에 baked 되어 라이브 반영은 merge+재배포 선행 필요(§51 graphux7 와 동일 패턴). POST-DEPLOY 에서 수행 후 본 섹션·feature-0003 TEST.md §3 에 Run append 예정.

## routine-dbanalysis — 전 ds routine 가시화 + DB 단위 능동 분석 (TASK §53, 2026-07-04)

### 케이스
- TC-53-1 (backfill 순회): MySQL 비시스템 ROUTINE_SCHEMA 만·MSSQL 사용자 DB 만 introspect, scope/datasource/store_schema 규약(MSSQL=DB명) 준수, per-ds 오류 loud + 계속 진행, --scope 필터·--dry-run 무저장.
- TC-53-2 (prune-safety): 한 store-label 에 복수 ROUTINE_SCHEMA → prune=False (뒤 스키마가 앞 스키마 행을 지우지 않음).
- TC-53-3 (시드): enqueue_schema_analysis 가 run(root=Schema, depth_budget=1, node_budget=planned=enqueued) + Table 잡 depth=1/rel 1.0 시드 — 확장 게이트 remaining=0 → 재귀 0 (same-depth 승격 포함).
- TC-53-4 (비용 가드): only_missing 이 완료 노드 제외, cap 초과 시 planned=cap+capped=true, 전부 완료 시 noop(run 미생성), running run 재사용(reused+progress).
- TC-53-5 (API): analyze-schema dry_run 집계 반환(비기록), 실행 시 audit(node_analysis.enqueue_schema — planned/capped/only_missing), noop=200/시작=202.
- TC-53-6 (UI): 카드/콤보 메뉴·상세 버튼 → confirm(테이블/미분석/이번 실행·cap 안내) → 진행 패널 연동, reused/noop 메시지, __terms__ 제외.
- TC-53-7 (가드): 멀티 ds 플래그 OFF 시 backfill fail-loud(기본 DB 오라벨링 차단).

### Run (2026-07-04) — pre-deploy 격리 검증
- pytest `test_routine_dbanalysis.py` **10 PASS** (시드/캡/noop/reused/dry_run·backfill 시스템 필터/prune-safety/오류 loud/scope·dry-run) + 관련 회귀 `test_node_analysis_relevance·role`·`test_graph_funcproc_uxfix` **57 PASS**.
- `node --check admin.js` PASS · py ast(node_analysis/metadata_graph/routines/routine_backfill/config/admin_metadata) PASS.
- 확장 게이트 코드 검증: `_enqueue_neighbors` 의 `remaining = node_budget - enqueued; if remaining <= 0: return 0` — 스키마 run 은 생성 시점에 remaining=0 → ADR-017 same-depth 승격 포함 추가 enqueue 불가(AC-4).
- §18.8 적대 패널(backend+qa·security·ux 3-렌즈) — REVIEW.md REV entry 참조.

### Run (2026-07-06) — §18.8 패널 적발 반영 후 재검증 (세션 이월 완결)
- 패널 적발 반영: BLOCKING(backfill 레지스트리 MEMORY_DB)·MAJOR 2(worker prune 조건부·진행 패널
  dismissed 해제)·MINOR 5·NIT 4 — 상세 MODIFY CHG-20260704T131948 / REVIEW.md REV entry.
- pytest `test_routine_dbanalysis.py` **16 PASS** (기존 10 + §18.8 회귀 잠금 6: 레지스트리 MEMORY_DB·
  disabled-ds skip/opt-in·dry-run running 감지(reused)·집계 실패 fail-loud·user_prompt 폴백 9-param INSERT·
  워커 `_enqueue_neighbors` budget 소진 시 0 삽입(AC-4 실행 검증, same-depth 승격 포함)).
- 관련 회귀 `test_node_analysis_relevance`·`test_node_analysis_role`·`test_graph_funcproc_uxfix` **57 PASS**.
- `node --check admin.js` PASS · py_compile(routine_backfill/node_analysis/insight/routines/metadata_graph/admin_metadata/config) PASS · `bash -n bin/routine-backfill.sh` PASS.
- **PB-0008(Windows-browser) pre-commit 미수행 사유**: 정적 자산 baked + backfill/분석은 라이브 datasource 필요 — merge+재배포(web+insight-worker)+라이브 backfill 선행. POST-DEPLOY 에서 수행 후 본 섹션·feature-0003 TEST.md §3 에 Run append 예정 — 검증 항목: ① 이전 0행 ds(예: mysql-gz-qa-kr) 스키마 펼침 시 ƒ/⚙ 렌더 ② DB 전체 분석 e2e(confirm→진행 패널→완료 마커) ③ reused/noop 메시지 ④ pageerror 0.

### Run (2026-07-06) — POST-DEPLOY 라이브 검증 — PASS (Environment: Windows-browser)
- 배포: PR #593 → main d1951b7e. `make deploy-web` 무중단 롤링(web-a/web-b 순차 recreate + 90s soak 통과)
  + insight-worker·ask-worker 재빌드(GIT_COMMIT d1951b7e 정합). healthz git_commit=d1951b7e,
  서빙 `admin.js?v=20260704-routine-dbanalysis`.
- **라이브 backfill (T53.6)**: `sudo bash bin/routine-backfill.sh` — **2,201 routines / 도달가능 4 ds /
  18 (DB,스키마) 슬롯 적재, 전 scope graph_synced=True**. mssql-dk-dev 1,449(AccountDB 198·
  dk_data_release_Main 300·ReportServer 237 은 **07-06 최초 적재** — 07-04 worker cadence 가 못 채운
  잔여 3 스키마를 결정론 회수) · mysql-gz-qa-global 313 · mysql-gz-dev 307 · mysql-mv-dev 132.
  insight_enabled=0 ds 2곳 skip(§18.8 MINOR 반영 동작). **미도달 14 ds 는 errors 에 loud**(네트워크
  timeout 110 — kr-an2 계열·mv-qa 계열 등 게이트망; AC-1 의 "실패 ds loud 리포트" 설계 그대로. 도달
  가능 시 재실행 또는 worker cadence 로 수렴, 수단은 확보됨). SSOT↔AGE 정합: routine_objects 카운트 ==
  cypher Routine 노드 카운트(1449/313/307/132 + twin 키).
- **PB-0008 (T53.7, 실 Windows Chrome/149 via relay @172.26.144.1:9223, `https://localhost/admin` 인증
  세션)**: ① **이전 0행 스키마 ƒ/⚙ 렌더** — accountdb(07-06 최초 적재 198행) 펼침 → routine 칩 198
  전수 렌더(ƒ3·⚙195, canonical z=4 NODE 밴드) + dk_game_integrate ⚙51. ② **DB 단위 분석 e2e**
  (pcbang_dkonline, 테이블 2): 우클릭 메뉴 핸들러 경로 → dry_run confirm("테이블 2개 · 미분석 2개 ·
  이번 실행 2개" + "이번 실행 대상 2개 테이블마다") → 진행 패널 "⋯ 대기 2개 (시드 테이블 대기 — 추가
  확장 없음)"(스키마 카피 분기 라이브) → **done 2/2 · 예약 2(상한 2) 고정 = 시드 외 enqueue 0(AC-4
  라이브)** → 보라 마커 2 + 역할 칩(L_Error=📜 log, PCBangIP=📘 master). ③ **reused parity(AC-3)** —
  run 진행 중 패널 ✕ 닫기 후 재트리거: confirm 미표시(허위 승인 차단)·dismissed 해제·패널 즉시 복구
  (§18.8 MAJOR/MINOR 수정 라이브 실증). ④ **noop parity(AC-3)** — 완료 후 재트리거: confirm 0,
  "분석 대상 없음 — 테이블 2개 전부 분석 완료". ⑤ pageerror 0 (window error 수집기, 전 구간).
  방법 주석: `window.confirm` 은 자동화 스텁(문안 캡처 + true)으로 승인 — 그 외 전부 실 UI 핸들러
  (`_metaGraphAnalyzeSchema`)·실 API·실 worker 경로. 증적
  `artifacts/feature-0016-metadata-graph/20260706-routine-dbanalysis/rdba-01~03.png`.

## graph-navfilter-routine — 그래프 뷰 개선 5건 (TASK §54, 2026-07-06)

### 케이스
- TC-54-1 (히스토리): 노드→클러스터→관계→노드 순회 후 뒤로/앞으로가 각 뷰 그대로 복원(+카메라),
  새 선택 시 forward 절단, 접힘/모델리셋 후 복원은 API 재조회(ById), terms combo 비기록.
- TC-54-2 (필터): ⚙/ƒ/🔗 토글 각각 빌드 제외+자리 회수 재배치, 엣지 토글은 테이블 위치 불변,
  localStorage 영속·검색/scope 전환에도 유지, 재토글 복원(루틴 열 말미 append).
- TC-54-3 (검색 보존): 검색→펼침·드래그·확장→재검색/클리어 시 구성·카메라 유지 + pristine 카드만
  회수, rel 은 매칭 한정(비매칭 칩 폭/배지 오염 0), '초기화'만 풀리셋.
- TC-54-4 (Routine 시드): 혼합 집계(total_tables/total_routines/missing), 루틴 잡 node_label='Routine'
  ·키 `()` 접미 규약, cap 테이블 우선, [] 저하 시 테이블-only, payload routine_type/params, 재귀 0
  (node_budget=planned 루틴 포함).
- TC-54-5 (파라미터 수직): 파라미터 있는 루틴만 펼침, XR/RP 합성 노드(z bake 1:1·nodePos 비오염·
  리지드 드래그·우클릭 귀속), realH 반영(아래 행 밀림·GB bbox), 상세 패널 세로 목록(esc 유지).

### Run (2026-07-06) — pre-deploy 격리 검증
- pytest `test_routine_dbanalysis.py` **21 PASS** (기존 16 + §54④ 5: 혼합 집계/루틴 라벨 시드/cap
  테이블 우선/[] 저하/_build_payload routine 필드; 기존 시드 단언은 label 파라미터화로 갱신)
  + 관련 회귀 `test_node_analysis_relevance`·`test_node_analysis_role`·`test_graph_funcproc_uxfix`
  **57 PASS**.
- `node --check admin.js` PASS · py_compile(metadata_graph/node_analysis/llm/admin_metadata/테스트) PASS.
- §18.8 적대 패널(ux·frontend correctness·backend+security 3-렌즈 + BLOCKING/MAJOR 적대 재검증
  Workflow) — REVIEW.md REV entry 참조.
- **PB-0008(Windows-browser) pre-commit 미수행 사유**: 정적 자산(admin.js/admin.html/styles.css) baked
  — merge+재배포(web+insight-worker) 선행 필요. POST-DEPLOY 에서 수행 후 본 섹션·feature-0003 TEST.md
  §3 에 Run append 예정 — 검증 항목: AC-1(뒤로/앞으로 뷰 복원) · AC-2(토글 재배치·영속) · AC-3(검색
  보존) · AC-4(DB 단위 분석 Routine 포함 confirm·마커) · AC-5(파라미터 수직·겹침 0) · pageerror 0.

### Run (2026-07-06) — POST-DEPLOY 라이브 실측 — PASS (Environment: Windows-browser)
- 배포: PR #597 → main 842b9ecf. `make deploy-web` 무중단 롤링(soak 통과) + insight/ask-worker
  재빌드(GIT_COMMIT 842b9ecf 정합). healthz 842b9ecf · 서빙 admin.js/styles.css
  `?v=20260706-graph-navfilter-routine`. 실 Windows Chrome via relay @172.26.144.1:9223,
  eval 게이트 통과, `window.confirm` 만 자동화 스텁 — 그 외 실 UI 핸들러·실 API·실 worker 경로.
- **AC-1(뒤로/앞으로)**: 노드→클러스터→관계→노드 순회 후 뒤로×3 = rel(관계 상세 뷰)→cluster(스키마
  클러스터 카드)→node(#metaGraphRelBtn/AiBox 로 DOM 정밀 판정) 각 뷰 정확 복원 + 앞으로×3 복귀(5/5
  라벨) — view-typed 히스토리 라이브 성립.
- **AC-2(kind 필터)**: dk_game_integrate 펼침(⚙51·ƒ1·테이블19·엣지59)에서 ⚙ 토글 → routine 51→1
  (ƒ만 잔존)·테이블 19 유지·masonry 재배치, **엣지 단독 토글 시 테이블 이동 0**(배치 불변 계약),
  재토글 완전 복원(51/59), localStorage `metaGraphHiddenKinds` 영속, 버튼 is-active/aria-pressed
  동기. 제품 개요에서는 kindctl 숨김(§18.8 MINOR 수정 라이브).
- **AC-3(검색 보존)**: 펼침 상태에서 실 input 검색('Consignment') → 줌·노드 114·펼침 유지 + match
  glow 9 → 클리어 → 구성 그대로·glow 해제·mode 복원·정확한 상태 문구. **products 랜딩 검색→클리어 =
  제품 개요(15+18) 완전 복귀**(§18.8 MAJOR-1 수정 라이브, _searchBase={mode:products} 기록 확인).
- **AC-4(Routine 분석)**: pcbang_dkonline dry_run = 테이블 2(완료 제외)·함수/프로시저 7·이번 실행 7
  — confirm 문안에 혼합 수치. 실행 → **Routine 잡 7 시드·done 7/7·실패 0** → ⚙ 7개 전부 분석완료
  마커 + 분석문 생성(프로시저 의미 정확 기술 실측). 재실행 dry_run missing 0(noop — only_missing
  dedup 이 Routine 키 포함 실증).
- **AC-5(파라미터 수직)**: FN_GetKeyIDToInventoryType(파라미터 4) 단일클릭 → RP: 4행 **21px 스텝
  수직 배치**(z=3 COLUMN 밴드)·XR ctl·아래 행 push-down(겹침 0) → XR 클릭 접힘(RP 0). 상세 패널
  세로 목록 병행.
- pageerror 0 (전 구간 window error 수집기). 증적
  `artifacts/feature-0016-metadata-graph/20260706-graph-navfilter-routine/nfr-01~02.png`.


## graph-category-recursive-refine — 제품 카테고리 + 크로스-DB 관계 + 재귀 분석 refine (TASK §55, 2026-07-06)

### 케이스
- TEST-20260706T210000-graph-cat-refine-1 (A): 다제품 매핑 datasource 진입 시 스키마 카드가 제품 카테고리
  밴드(CAT 배경+🗂 헤더 `제품 · n DB`+CATX)로 세로 스택 배치, 미매핑은 '미분류' 후미, 매핑 전무 시 기존 배치.
  CATH 드래그=밴드 리지드 이동(멤버 clusterOffset 누적), CATX 접기=멤버 미방출·헤더 밴드 유지, 검색 매칭 강제 펼침.
- TEST-20260706T210000-graph-cat-refine-2 (B): 같은 DS 다른 스키마(DB) 간 임베딩 유사 후보가 src_ds==tgt_ds
  로 저장·MSSQL 3-part 프로브 SQL 생성(dbo slot 2-part 가드)·fetch 한끝 OR. 관계 상세 행 ✓신뢰/✕파단 →
  curate API(trust=manual trusted·break=broken+역방향, AGE 즉시 정합, cross_ds 승격 시 AI 컨텍스트 주입 대상).
- TEST-20260706T210000-graph-cat-refine-3 (C): DB 단위 분석 시드 depth0+anchor_key=자기 자신·예산 planned×12
  (cap 2500)·직계 컬럼 게이트 면제 편입·이웃 anchor_key 상속. 모든 잡 previous_analysis 동봉(refine 계약).
  잡 완료 시 인접 thin done 재-pending(pass_no+1, REFINE_MAX 캡, enqueued 단조). suggested_links 3중 가드 통과분만
  llm_insight candidate. 0038 미적용 창 legacy 폴백(재귀 0).
- TEST-20260706T210000-graph-cat-refine-4 (D): 시그니처 백필 미처리(hash NULL) 우선 소진 + remaining 로그 단조 감소.

### Run (2026-07-06) — pre-deploy 격리 검증
- Environment: repo-insight-worker 컨테이너(worktree 마운트) pytest + node 헤드리스. Runner: AI.
- 신규 `test_graph_category_recursive_refine.py` **23 PASS**(thin/parse/latest/related 헬퍼 · back-refine
  재-pending/캡/카운터 · anchor 상속(+legacy) · per-seed 앵커 prompt 상속 · suggested_links 유효/환각/root 연루/캡/
  비-Table skip · xschema intra-DS 후보/같은-DB 제외/min_sim/xds off/reverse-dup · MSSQL 3-part/dbo 가드 ·
  fetch OR-완화 · 백필 정렬) + `test_routine_dbanalysis.py` 계약 갱신 2(신 계약 depth0·legacy 폴백) 포함 **24 PASS**
  + `test_graph_relationship_curate.py` **4 PASS**(Column key 파싱 3-part/2-part/scope lower/invalid).
- 프론트 헤드리스 `_metaG6Build` 카테고리 격리 **17/17 PASS**(scratchpad/test_g6build_category.js — 매핑없음
  무개입·밴드 3종 방출·zIndex CAT_BG(-1)·밴드 세로 분리·헤더 라벨·멤버 밴드 내 포함·접기/재펼침·검색 강제펼침·
  catOrder 안정화(신규 append)·클러스터 offset 반응형 bbox).
- **전체 스위트**(feature-0002 + feature-0003 tests) 컨테이너 pytest **EXIT=0 전건 PASS** — route parity golden 은
  의도적 라우트 +2(analyze-schema §53 누락분 + curate §55) 반영 재생성(195→197, clean main 에서도 실패하던
  §53 baseline drift 동반 치유). node --check(admin.js)·py_compile 전 파일·migrate-lint(0038 expand-safe) PASS.

### Run (2026-07-07) — §18.8 패널 확정·재검증분 반영 후 재검증
- Environment: repo-insight-worker 컨테이너 pytest + node 헤드리스. Runner: AI.
- 패널 수정 9건(BLOCKING 2·MAJOR 4·MINOR 3 — REVIEW REV-20260707T100744 상세) 반영 후:
  회귀 잠금 신규 6건(fetch 4-분기 필터·transient probe 미캐시·모호 alias 차단·xschema 초과-fetch recall·
  xds SQL 경계 유지·curate 매칭) + 헤드리스 T7~T9(zFor CAT canonical·접힘 밴드 드래그 차단·scope 한정
  오배정 방지) — 헤드리스 **26/26 PASS**(하네스 repo 영속화: tests/headless/test_g6build_category.js).
- **전체 스위트(0002+0003) 컨테이너 pytest EXIT=0 · FAILED 0** (패널 수정 반영 최종).
- PB-0008 실 Windows 시각검증: **POST-DEPLOY 예정** (Environment: Windows-browser — 웹 자산이 web 이미지에
  baked 되어 머지·배포 후 라이브 실측이 유일한 유효 검증, §53/§54 관례와 동일). 미수행 사유: pre-commit 시점엔
  변경 자산이 라이브에 미서빙. 배포 후 카테고리 밴드 렌더·접기/드래그·관계 큐레이션·DB 분석 재귀 확장을 실측해
  본 절에 Run 을 append 한다.

### Run (2026-07-07) — POST-DEPLOY 라이브 실측 — PASS (Environment: Windows-browser)
- 배포: PR #599 머지(main 0bd73169) → `make migrate`(**alembic 0038 라이브 head 도달**, anchor_key·pass_no
  컬럼 확인) → `make deploy-web` 무중단 롤링(web-a/b 0bd73169, soak 90s 통과, Caddy blip 0) →
  insight/ask-worker 재빌드·recreate(신 코드 baked 실증: `_backrefine_neighbors`·XSCHEMA 노브 — ask-worker
  GIT_COMMIT 라벨은 snap-docker metadata race 로 unknown, 코드 grep 으로 대체 검증. XDS flip env 활성).
- 실 Windows Chrome/149(win-browser relay @172.26.144.1:9223, bootstrap_admin 로그인). 서빙
  `admin.js/styles.css?v=20260706-graph-cat-refine`·healthz git_commit=0bd73169(edge).
- **AC-1(A 카테고리) PASS**: `mssql-qa-idc`(scope mssql-06656002eda6, 스키마 72·매핑 71) 진입 →
  **제품 카테고리 밴드 6종**(출조낚시왕8·콜오브카오스16·DK온라인31·스키드러쉬1·에이스온라인7·DK집계9 =
  72 전부 배정) CAT/CATH/CATX 각 6 렌더·세로 스택·헤더 라벨(`🗂 제품 · n DB`)·범례 항목 — 스크린샷 육안
  확정(cat-01-bands.png). CATX 접기 → 멤버 클러스터 미방출·헤더 유지 → 재펼침 복원. **z canonical 라이브
  = CAT -1 / CATH 5 / CATX 6**(패널 BLOCKING fix 실증 — ZAssert 승격 없음). 카테고리 상세(DK온라인 31행).
  schema_products 백엔드: 8개 datasource 에서 매핑 반환(다제품 4종 케이스 포함) 확인.
- **AC-2(B 큐레이션) PASS**: 관계 상세 패널에 ✓신뢰/✕파단 버튼 렌더(L_CouponInputFail 7관계 ×2).
  candidate 1건 API 왕복 — **trust: updated=1(기존 행 UPDATE — 중복 행 미생성, 패널 MAJOR fix 실증)** →
  break: updated=1(양방향). 검증 후 원상 복원(SSOT candidate/inferred, AGE 엣지는 다음 sync 재투영).
- **AC-3(C 재귀·refine) PASS**: `confirm_db`(테이블 2) DB 단위 분석 run 833b8d31… → **done 8/8·failed 0**:
  시드 Table 2(depth0·**anchor_key=자기 자신**) → Column 2(depth1·**anchor 상속**=소속 시드) 재귀 편입
  (enqueued 2→8, §53 재귀 0 대비 명확) → **전원 pass_no=1 back-refine 재보충 발화**(초기 thin →
  최종 분석문 423~467자). 카운터 단조(enqueued=8=4신규+4재보충=done).
- **AC-4(D 백필) PASS**: 워커 재기동 직후 signature_text_hash 497→**1,175행**(첫 pass 500 소진 — 미처리
  우선 정렬 실증), 이후 15분 주기 소진 지속(~8h 완주 전망). 워커 Traceback/CRITICAL 0.
- pageerror 0(전 구간). 증적 `artifacts/feature-0016-metadata-graph/20260707-graph-cat-refine/`
  (cat-01-bands.png·cat-02-collapsed-curate.png).

## routine-sync-crossdb — fhgame1 루틴 투영·크로스-DB 참조·재귀 보충 (TASK §56, 2026-07-07)

### 케이스
- TEST-20260707T210000-routine-sync-crossdb-1 (RC1): batched sync 에서 한 행 실패가 뒤 행·타 step 에
  전파되지 않고(SAVEPOINT 격리+step 가드), 커밋/스텝/치명 실패는 step_failures 로 워터마크를 차단.
- TEST-20260707T210000-routine-sync-crossdb-2 (RC2): 프로시저 정의의 [db].[dbo].[T]·db..T·db.T 참조가
  실재 검증 통과 시 크로스-DB ROUTINE_USES 로 저장·투영, 동명 로컬 오귀속 차단, 미상 qualifier 레거시 폴백.
- TEST-20260707T210000-routine-sync-crossdb-3 (RC3/RC4): thin='연결 정보 없음' 동치(back-refine 발화),
  routine_backfill read-axis scope(label 이중 적재·고아 투영 차단).

### Run (2026-07-07) — pre-deploy 격리 검증
- Environment: repo-insight-worker 컨테이너 pytest. Runner: AI.
- 신규 `test_routine_sync_crossdb.py` **20 PASS**(qualifier 4규칙 7종·introspect 배선/TTL·실패 미캐시·
  row-guard 5종(RELEASE·SAVEPOINT 실패 step 계상 포함)·thin·RC4 read-axis 3종) + 기존 계약 갱신
  (`test_graph_funcproc_uxfix.py` 주석) — 영향 스위트 및 **전체 스위트(0002+0003) EXIT=0·FAILED 0**.
- §18.8 적대 패널(ultracode, 27 에이전트): 확정 8건 전건 수정 — REVIEW REV 참조. 마이그 0.
- 웹/UI 자산 변경 없음(백엔드 전용) — PB-0008 은 배포 후 그래프 뷰에서 fhgame1 ƒ/⚙·크로스-DB 엣지
  육안 확인으로 수행(Environment: Windows-browser Run 을 POST-DEPLOY 에 append 예정).

### Run (2026-07-07, 재개 세션) — §56 T56.6 완수 + RC5 적발·수정
- Environment: 재개 세션(Fable) — PR #615 머지·배포(web soak PASS·워커 재빌드·alembic 0039)·healthz 전건 PASS.
- RC4 라이브 정리: SSOT 라벨 이중행 2,201 전건 twin-검증 삭제(dk-dev 케이스 비대칭은 lower 매칭으로 1,449/1,449
  해소) + AGE 라벨 고아 2,814v/4,955e DETACH DELETE — 잔여 0 확인.
- RC2 라이브 실증: 재-introspect(stored 6,910) 후 refs `"cross":1` — fhgame 86·qa-idc 758 루틴.
- **RC5 적발**(e2e 게이트가 목적대로 작동): fhgame1 300→600 케이스-변형 이중행(qa-idc 1,912쌍) →
  TEST-20260707T170500-routine-schema-case-1: backfill mssql store label lower(store/query 분리) ·
  -2: mysql 케이스 보존. 컨테이너 pytest 44 PASS(EXIT=0). e2e 재수행은 T56.8 에서 완결.
- **RC5 패널 반영 후 확장**: normalize_db_label parity·purge SQL 계약·CS-collation prune 강등·
  dry-run slot 원본 케이스 — RC5 계열 6건, 영향 3파일 66 PASS(EXIT=0)·ruff PASS.

### Run (2026-07-07, POST-DEPLOY) — §56 RC1~RC5 라이브 e2e (Environment: live qa-idc/fhgame1)
- 배포: PR #615(fe05d6f8)·#617(94e2e411) → web fbae6f56 롤링 soak PASS·워커 재빌드(코드 grep 실증)·
  alembic 0039·healthz/smoke 전건 PASS.
- RC4/RC5 라이브 정리: RC4 라벨 이중행 2,201 twin-검증 삭제 + AGE 라벨 고아 2,814v/4,955e 회수 →
  RC5 재-backfill case_purged **6,320 전량 자동 회수**(SSOT mixed 0·fhgame1 600→300) + AGE mixed-key
  8,230v 회수(잔여 0).
- RC1: full sync {routines 16,410, errors 0, step_failures 0, ok true, commits 67} — 워터마크
  scope 07-07 19:01·__all__ 19:30 전진(07-06 07:30 고착 해소). RC2: 크로스-클러스터 ROUTINE_USES
  1,041(실측 fhgame1.FHSP_BuyItem_V4→fhdef.FH_ITEM read 등). RC3: 능동 분석 run 6c33317d
  (시드 361·missing 300) 기동 — back-refine 은 run 소화 중 substrate 기반 발화.
- PB-0008(Windows-browser): 백엔드 전용 변경 — 그래프 뷰 육안(fhgame1 ƒ/⚙·크로스 엣지·보충 해소)은
  **사용자 확인 대기**(Environment: Windows-browser Run 은 사용자 확인 후 append).

### Run (2026-07-08) — §56 PB-0008 시각검증 — PASS (Environment: Windows-browser)
- 실 Windows Chrome/149(win-browser relay @172.26.144.1:9223, bootstrap_admin 세션) — AI 직접 수행
  (playwright CDP attach + 앱 정식 경로 `_metaGraphExpandSchema`/`_metaGraphExpand`/`_metaGraphShowDetail`).
- **AC-① fhgame1 ƒ/⚙ PASS**: mssql-qa-idc 진입(카테고리 밴드 6종·스키마 135 카드) → fhgame1 점프(앰버
  글로우) → 펼침: ⚙/ƒ 보라 pill 루틴 노드 대량 렌더(뷰 모델 노드 300·관계 494), 케이스 중복 0
  (fhgame1 단일 클러스터 — fh 계열 fhdef/fhetl/fhlog0·1/fhlogin/fh_ods/fhweb 전부 단일).
- **AC-② 크로스-DB 연결선 PASS**: fhdef 병행 펼침 → 줌아웃에서 fhgame1 루틴 밴드 ↔ fhdef 클러스터 간
  연결선 렌더. FHSP_BuyItem_V4 상세 = 사용 테이블 5(fhgame1.FH_CHAR·FH_CHAR_ITEM 쓰기 + **fhdef.FH_ITEM·
  FH_ITEM_BOAT_OPT·FH_SHOPLIST 읽기**). 역방향 fhdef.FH_ITEM 상세 = **사용하는 함수·프로시저 49**(읽기
  칩 전부) + focus 뷰에서 유입 잔점선 엣지 육안 확정 (증적: pb-20/23/25/26 스크린샷).
- **AC-③ 능동 분석 보충 PASS**: 분석 run 6c33317d done 538/538·failed 0. FHSP_BuyItem_V4 능동 분석 =
  구매 트랜잭션 흐름·관계(5테이블 조합 동작)·활용(운영 추적/디버깅/이상감지)·주의 — '보충설명 필요'
  플레이스홀더가 실질 분석으로 대체.
- **디자인 가시성 검토(사람 수용성)**: 수용 가능 판정 — 노드 타입 구분(teal 테이블/보라 ƒ⚙/파스텔
  그룹밴드/선택 테두리) 명확, 상세 패널 구조(배지·mono 파라미터·읽기/쓰기 칩·분석 prose) 양호,
  탐색 보조(검색·점프·이웃깊이·미니맵·범례·status 안내) 충실. **개선 여지(비차단, 후속 후보)**:
  ① 중간 줌에서 루틴 그리드 관통 엣지 스파게티(300노드·494엣지 밀집 — focus/상세로 완화되나 기본
  펼침 뷰 소음) ② 크로스-DB 엣지가 로컬 사용 엣지와 동일 스타일(보라 잔점선)이라 시각 구분 불가 —
  SSOT cross 플래그의 엣지 속성/색상 반영 후보 ③ 스키마 점프 목록에 AccountDB/accountdb 케이스 중복
  노출 — **테이블 축 케이스 변형**(table_descriptions 'AccountDB' 33행, 06-30 일회성 적재·라이브 writer
  없음·lower twin 없음 → 삭제 아닌 rekey 대상, §56 후속 T56.7c 계열에 위임).

## graph-edge-visibility — 접힘 연결선·하이라이트·크로스·LOD (TASK §57, 2026-07-08)

### 케이스
- TEST-20260708T120000-edge-visibility-1: 양쪽 접힘 카드 사이 SCHEMA_REF 집계 엣지(count 라벨·로그
  굵기), 한쪽 펼침 시 미방출(상세/승격 엣지 대체). 혼합 상태는 3단 승격(컬럼→테이블→SC:)로 연속.
- TEST-20260708T120000-edge-visibility-2: 크로스-DB ROUTINE_USES 마젠타(AGE cross_ds 속성 + 키
  세그먼트 폴백), 로컬 사용선 보라 유지. sync_routine 이 SSOT cross → cross_ds='1' 투영.
- TEST-20260708T120000-edge-visibility-3: 선택 시 1-hop 인접 밖 노드 dimmed·비인접 엣지 흐림,
  빈 캔버스 클릭 해제. LOD(줌<0.35·엣지>120)에서 무상태 FK 축약·의미 신호 보존.

### Run (2026-07-08) — pre-deploy 격리 검증
- Environment: headless node vm(실 admin.js) + repo-insight-worker 컨테이너 pytest. Runner: AI.
- headless 신규 18 PASS + 기존 category 26 PASS(회귀 0). 백엔드 21 PASS(EXIT=0) — cross_ds 투영·
  SCHEMA_REF 집계(intra-schema·무세그먼트 키 제외) 잠금. 집계 성능: 멀티-hop 82s → 1-hop 0.2s 실측.
- PB-0008 은 배포 후 실 Windows 육안(카드 연결선·하이라이트·마젠타·LOD)으로 수행 예정.
- **§18.8 패널 반영 후**: BLOCKING(aftertransform 교체)·MAJOR(이중 렌더 억제)·MINOR 7 수정 —
  headless 22 PASS(+T6/T7/T8)·category 26·백엔드 21 (EXIT=0).

### Run (2026-07-08) — §58 골격 가져오기 라벨 케이스 (Environment: 컨테이너 pytest)
- test_bootstrap_skeleton_mssql_schema_label_lowercased PASS — db_name 'FHGame1' → schema_name 'fhgame1'
  저장, 테이블명 케이스 보존, MySQL 분기 무변경. EXIT=0.

## product-classify-suggest — 분석 기반 분류 제안 (TASK §59, 2026-07-08)

### Run (2026-07-08) — pre-deploy 격리 검증
- 컨테이너 pytest test_product_classify.py 4 PASS: Pending-only 계약(allowlist 무기록·RuleId NULL·
  reason 'ai_suggest:<conf>')·환각 3중 게이트(미입력 스키마/비화이트리스트 pid/임계 미만 폐기·
  최고 신뢰도 1건)·dry-run 무쓰기·LLM 실패 soft. ruff PASS.
- 라이브 실증·PB-0008(제안 블록)은 POST-DEPLOY(데몬 기본 OFF — dry-run CLI 로 확인).
