---
run_at: 2026-07-16T01:51:24+0900
session: ai/claude/feature-0016-graph-detail-scroll
scope: unit/feature-0003-agent-web-ui/src/static/graph
verdict: PARTIAL
---

### Run (2026-07-16) — graph-detail-scroll: 상세 패널 [뒤로/앞으로] 스크롤 위치 보존 — **Environment: Windows-browser**

- 방법: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150.0.7871.115, CDP relay `172.26.144.1:9223`) + `docker cp` 로 web-a/web-b 의 `/app/web/static/graph/{graph-ctxmenu,graph-state}.js` 를 본 변경 서빙 사본으로 교체(신규 심볼 존재 확인: `_metaGraphReapplyPendingScroll`×6·`_histNavBusy`×2) → https://localhost/admin → 메타데이터 > 그래프 뷰.
- 확인(PASS):
  - **번들 로드·무에러**: 변경된 서빙 모듈이 실제 그래프 뷰에서 정상 로드·실행 — 그래프 뷰 렌더, 데이터소스 스코프 전환(common → mysql-gz-dev → mssql-dk-dev), 검색까지 전 과정 **콘솔 에러 0**(`window.__errs` 훅 누적=0). 구문/런타임 회귀 없음(파싱 실패 시 그래프 뷰 전체가 죽는데 정상 동작).
  - **스크롤 컨테이너 타깃 정합(라이브)**: 본 변경이 스냅샷/복원 대상으로 삼는 `#metadataGraphDetail` 이 라이브에서 `overflow-y: auto`(실 스크롤 프레임)임을 확인 — 코드가 `#metadataGraphDetailBody`(내용 자식)가 아닌 aside 를 잡는 것이 정합.
  - **nav DOM 배선**: `#metaGraphDetailBack`·`#metaGraphDetailFwd`·`#metadataGraphDetailBody` 존재·배선 확인.
- 미수행(DEFERRED, 환경 제약 — 코드 무관):
  - **전체 상호작용 assertion(뒤로/앞으로 왕복 시 각 화면 scrollTop 복원)**: 본 환경의 AGE 메타데이터 그래프 투영이 조회한 모든 datasource 스코프(mysql-gz-dev·mssql-dk-dev 등)에서 **0개 노드**(테이블-레벨 스키마 그래프 공백, 검색으로도 미populate; common 스코프는 제품/데이터소스 노드만). 상세 패널 이력은 테이블/컬럼/클러스터/관계 노드 상호작용에서 생성되므로, 실제 이력 2개+ 를 만들어 스크롤 왕복을 검증할 데이터가 없음. 그래프-sync 재populate(§82 flock 인시던트 이후 상태) 또는 데이터 보유 스코프 확보 후 재확인 필요(TS.6 후속).
- 보완 근거(상호작용 correctness): §18.8 적대 리뷰 PASS-WITH-FIXES(MAJOR 1 + MINOR 3 전부 수정, REV-20260715T161958) + 3개 show 함수 Record-before-await 순서 코드 확증(725/1651/2266) + 스크롤 컨테이너 요소 CSS·라이브 이중 확인.
- 결과: **PARTIAL PASS** — 서빙 사본 로드·무에러·DOM/CSS 배선 라이브 확인. 전체 스크롤 왕복 육안 검증은 그래프 데이터 부재로 이연(TS.6).
- 스크린샷: scratchpad graph-state0.png / graph-schemas.png (세션 산출물).
