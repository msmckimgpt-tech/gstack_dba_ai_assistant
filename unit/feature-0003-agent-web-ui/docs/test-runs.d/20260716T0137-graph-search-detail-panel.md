---
run_at: 2026-07-16T01:37:14+09:00
session: ai/claude/feature-0003-graph-search-detail-panel
scope: 그래프 뷰 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성(match_via 배지·유사도·cluster_label·클릭→상세 이동) (20260716T0137-graph-search-detail-panel)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 PASS (Environment: Windows-browser, main 03e8d1b0)
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

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **PASS**
- 배포: PR #839 → main 03e8d1b0 + `sudo -E bin/deploy-web.sh` 무중단 롤링(web-a/web-b·워커 recreate·soak 통과). 서빙 자산 확인(web-a): `graph-ctxmenu.js` 신규 심볼(metaGraphSearchResults/_metaGraphRenderSearchResults) grep=6 · `graph.css` `amgr-via-category` grep=1.
- 방법: win-browser.py 실 Windows Chrome relay(Chrome/150), https://localhost/admin(로그인 세션) → 지식베이스 > 그래프 뷰(데이터소스 공용/common — 전역 검색).
- 결과 **PASS**:
  1. **검색어 갱신 → 상세 패널 결과 구성**: `#metadataGraphSearch` 에 "코스튬" 입력(300ms 디바운스) → 상세 패널(`#metadataGraphDetailBody`)에 `#metaGraphSearchResults` 컨테이너 렌더, 헤더 "🔎 검색 결과 7건", 7행. (마커·행 DOM 실측.)
  2. **AI 능동 분석 매칭 배지**: "코스튬" 7행 전부 `via=["AI 분석"]` — 노드명은 영문(Hero·CostumeStorageSlot·Costume·HairCostume·usp_add_bonus_costume 등)이라 analysis 본문으로만 매칭(name/fqn 미포함). 백엔드 라이브(feature-0002 검증)와 일치.
  3. **컨텐츠 카테고리 매칭 배지 + 유사도 + cluster_label**: "플루토스" 재검색 → 28행(헤더 "🔎 검색 결과 28건"), viaAgg={카테고리:26, AI 분석:4}. 예: `UT_PlutosCommRank` 테이블 배지 + "유사도 63%" + 앰버 "카테고리" 배지 + meta "카테고리: 플루토스 상업". 영문 노드명이 한글 cluster_label 로 매칭(구 로직 0건).
  4. **결과 행 클릭 → 노드 상세 이동**: 첫 행(`data-goto="mssql-06656002eda6:cc_obt.UT_PlutosCommRank"`) 합성 클릭 → `_metaGraphShowDetail` → 마커 제거(markerGone=true) + 상세 카드 "TABLE UT_PlutosCommRank · 🔗 관계 상세 · 🎯 이 노드로 이동" 렌더.
  5. **검색어 클리어 → 검색결과 뷰 해제**: 검색어 비움 → `#metaGraphSearchResults` 마커 부재 + 상세 패널 empty 상태("검색 후 노드를 클릭하면…") 복원.
  6. **pageerror 0** · `document.readyState=complete`.
  7. 스크린샷 육안(search-detail-category.png): 우측 상세 패널에 "🔎 검색 결과 28건" + 부제(이름·FQN·컨텐츠 카테고리·AI 능동 분석 매칭) + 각 행 [테이블] 배지·이름·유사도 63%·[카테고리] 앰버 배지·"카테고리: 플루토스 상업/거래/통신/순위" 공존.
- visual_verification_scope: always — 충족. (evidence: /tmp/win-browser-shots/search-detail-{analysis,category}.png — PNG 는 repo 미커밋 관례 준수, 판정은 본 Run 실측.)
