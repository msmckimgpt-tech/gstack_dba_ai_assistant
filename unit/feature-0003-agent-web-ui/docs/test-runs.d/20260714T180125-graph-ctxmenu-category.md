---
run_at: 2026-07-14T18:01:25+09:00
session: graph-ctxmenu-category (ai/claude/feature-0003-graph-ctxmenu-category)
scope: 그래프 뷰 '제품 카테고리 밴드'(CAT:/CATH:/CATX:) 우클릭을 전용 카테고리 메뉴로 라우팅 — combo(스키마 클러스터) fall-through / hide stopgap 대체
verdict: PASS (코드/문법/정합) · DEFERRED (Windows-browser 라이브 — 배포 후)
---

### Run (2026-07-14) — graph-ctxmenu-category: 카테고리 밴드 우클릭 전용 메뉴 — **Environment: node --check (ES module) + dispatch 정합 trace**

- 방법: 변경 2파일을 `.mjs` 로 복사 후 `node --check`(ES module 문법 파싱).
- 결과: `graph-ctxmenu.js` OK · `graph-core.js` OK.
- 정합 trace:
  - `graph-ctxmenu.js` L279 `function _metaGraphCtxForCategory(catKey, x, y)` 정의 + export line(2308) — grep 2회(정의+export) 확인.
  - `graph-core.js` L10 import 에 `_metaGraphCtxForCategory` 추가 · L2086 `node:contextmenu` CAT 분기가 `_metaGraphCtxForCategory(String(id).replace(/^CAT(H|X)?:/, ""), p.x, p.y)` 로 라우팅.
  - **dispatch 경로 정적 추적**: Pixi `_pick`(graph-renderer-pixi.js L446-451)은 node hit 우선(`if(n) return n`) → CAT 배경 노드(밴드 전체 bbox `size:[bw,bh]`, hit-grid 는 built.nodes 무필터 포함)가 combo 보다 먼저 히트 → `node:contextmenu`(kindEvt=node) → L2086 전용 라우팅. combo fall-through 불가(node 우선).
  - **의존 심볼 존재**: `_metaGraph.catLabelOf`/`catCollapsed`/`catMembers`(graph-state)·`_metaGraphShowCategoryDetail`(동일 파일 L1711+18)·`_metaG6Apply`·`_metaGraphCopyText`(import·기존 combo 메뉴 사용) 전부 존재.
- 회귀 표면: 좌클릭(CATX 토글·CAT/CATH 상세)·드래그·combo/node/edge 메뉴 무변경(추가만). 백엔드/RBAC/스키마 0.
- 결과: 코드/문법/정합 PASS.

### Run (2026-07-14) — 카테고리 밴드 우클릭 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산)**: 그래프 static JS 는 이미지 baked 라 배포(web 재빌드/재시작) 후에만 라이브 반영. 배포 전 headless/로컬로 실 반영 검증 불가(정적 자산 볼륨 미마운트).
- **배포 후 계획(PB-0008)**: web 재배포 후 win-browser relay(또는 Playwright MCP)로 그래프 뷰(관리 콘솔 > 메타데이터 그래프, 제품 카테고리 밴드가 보이는 스키마→제품 매핑 scope) 진입 →
  - (a) 카테고리 밴드 배경/헤더 칩 **우클릭** = 카테고리 전용 메뉴(헤더 배지 '카테고리' + '카테고리 상세'·'접기/펼치기 (밴드)'·'카테고리명 복사') 노출, **스키마 클러스터 메뉴('클러스터 상세'/'DB 전체 AI 능동 분석' 등) 미노출** 확인.
  - (b) '카테고리 상세' 클릭 = 상세 패널에 멤버 DB 목록 렌더.
  - (c) '접기/펼치기 (밴드)' = 멤버 클러스터 표시/숨김 토글(catCollapsed).
  - (d) **회귀 0**: 스키마 클러스터(combo) 우클릭은 종전대로 클러스터 메뉴 유지.
- 결과: 정적/문법/정합 검증 PASS · 라이브 시각검증 DEFERRED(배포 후).
