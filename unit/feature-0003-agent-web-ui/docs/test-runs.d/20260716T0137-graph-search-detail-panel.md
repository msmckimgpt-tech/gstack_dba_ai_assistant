---
run_at: 2026-07-16T01:37:14+09:00
session: ai/claude/feature-0003-graph-search-detail-panel
scope: 그래프 뷰 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성(match_via 배지·유사도·cluster_label·클릭→상세 이동) (20260716T0137-graph-search-detail-panel)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED (Environment: Windows-browser)
---

### Run 1 — 문법/균형 검증 (Environment: node --check + CSS balance)
- `graph-ctxmenu.js` ESM `node --input-type=module --check` PASS (import 심볼 참조·함수 호이스트 정상).
- `graph.css` brace 233:233 밸런스. 신규 규칙(`.amgr-searchlist`/`.amgr-searchres`/`.amgr-via`+3색/`.amgr-searchsub`/`.amgr-searchmeta`/`.amgr-row[data-goto]`)만 추가 — 기존 `admin-meta-graph-card`/`amgr-row`/badge 토큰 재사용.

### Run 2 — 정적·로직 검증 (Environment: 코드 리뷰 + §18.8 적대 리뷰)
- **렌더 훅**: `_metaGraphRenderSearchResults(data.nodes, q)` 는 `seq!==_opSeq`·`q!==lastQuery` 두 stale 가드 뒤(검색어 갱신 트리거만 반영, 연타 stale 폐기). 백엔드가 유사도 내림차순 정렬한 노드를 그대로 렌더.
- **클리어 훅**: 빈 q 진입 시 `#metaGraphSearchResults` 마커 있으면 `_metaGraphRenderDetailEmpty()`. 마커 producer 는 본 함수 2곳(결과/empty 변형)뿐 — 노드 상세(`_metaGraphRenderDetail`)·클러스터 상세는 마커 미생성 → 결과 클릭해 노드 상세 진입 후 클리어 시 상세 보존, 결과뷰 클리어 시 empty 복원(양방향 정확).
- **XSS**: name/fqn/cluster_label/key/q 전부 `esc()`(속성=큰따옴표 delimiter+`&quot;`). 미이스케이프 보간은 상수맵 color·하드코딩 배지 라벨·숫자뿐.
- **리스너**: innerHTML 교체 → 이전 li detach + 지역 클로저 → GC 회수(누수 없음).
- **배지**: match_via(name/category/analysis) → 회색/앰버(검색 글로우 #e8a400 계열)/블루. score>0 만 유사도%; analysis-only(score≈0)는 via 배지만. 결과 0건 전용 메시지.
- **접근성**: role=button·tabindex=0·Enter/Space(Space preventDefault 스크롤 차단).
- **§18.8 적대 리뷰** REV-20260716T013714-graph-search-detail-panel — 7축 중 6축 결함 없음, 1축(#5) 저-심각도 cross-session 조정 항목(병렬 graph-detail-scroll `_metaGraphHistoryCaptureScroll` 마커-스킵 가드 — 후행 병합자 처리, SendMessage 통지). 텍스트 병합 충돌 없음.
- 결과 **PASS(정적)**.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — DEFERRED (배포 후 실행)
- PB-0008 실 Windows Chrome relay(win-browser.py)로 배포본(origin/main deploy-web 후) 그래프 뷰에서 검증 예정:
  1. 검색어 입력 → 상세 패널에 검색 결과 리스트 구성(label 배지·유사도·match_via 배지·카테고리 라벨).
  2. 컨텐츠 카테고리 매칭어(예: 플루토스)·AI 분석 매칭어(예: 코스튬) → 해당 via 배지 표시.
  3. 결과 행 클릭 → 그 노드 상세로 이동.
  4. 검색어 클리어 → 검색결과 뷰 해제(노드 상세 진입 후는 보존).
  5. pageerror 0.
- visual_verification_scope: always — POST-DEPLOY Run 완료 시 PASS 기록으로 갱신.
