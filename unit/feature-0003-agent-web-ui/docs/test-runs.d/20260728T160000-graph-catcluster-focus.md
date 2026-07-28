---
run_at: 2026-07-28T16:00:00+09:00
session: ai/claude/feature-0016-catcluster-focus
scope: 접힌 카테고리 클러스터 하위 테이블 추적 시 카메라 승격 대상 교정 (graph-catcluster-focus)
verdict: PASS
---

# Run — graph-catcluster-focus 헤드리스 결정론 (Environment: node vm)

- 신규 `tests/headless/test_graph_ancestor_focus.js` **32 PASS / 0 FAIL**.
  `graph-core.js` 에서 `_metaRenderedIdFor` · `_metaGroupElementFor` · `_metaCategoryElementFor` ·
  `_metaRenderedAncestorFor` · `_metaAncestorKindKo` 본문을 **원본에서 추출**해 vm 격리 실행
  (사본 아님 — `test_graph_reveal.js` · `test_detail_dbgroups.js` 와 동일 패턴).
  - A1 컬럼 → 렌더된 소속 테이블(기존 동작 회귀 없음).
  - **A2 핵심 회귀 — 컨텐츠 카테고리 접힘(테이블 미렌더 · GB: 렌더 · 스키마 combo 렌더)에서
    승격 대상이 `GB:<groupKey>` 이고 스키마 combo 로 새지 않는다**(사용자 보고 증상의 직접 단정).
  - A3 컬럼도 소속 테이블의 GB: 로 승격 · A4 루틴(함수·프로시저) 동형.
  - A5 접힌 스키마 카드 경로는 종전대로 `SC:` (groupOf 미적재 경로 — 회귀 없음).
  - **A6 제품 카테고리 밴드 접힘 → `CAT:<catKey>`**(종전 null = 카메라 미이동).
  - A7 스키마 클러스터가 렌더돼 있으면 밴드보다 스키마가 우선(가장 가까운 조상 규칙 보존).
  - A8/A9 stale 역인덱스 게이팅 — `groupOf`/`catMembers` 에 잔존해도 `renderedIds` 에 없으면
    다음 계층으로(허위 카메라 이동 금지). A10 전 계층 미렌더 → null.
  - A11 사다리 전수(5단) — 계층을 하나씩 걷어낼 때 테이블 → GB → 스키마 → CAT → null 순 강등.
  - A12 상태줄 명칭 매핑 8종(종전 "소속 테이블" 단정 오안내 해소) + **조사 불변식**(호출측이 "…{명칭}로"
    로 붙이므로 전 라벨이 모음 또는 ㄹ 받침으로 끝나야 함 — 받침 있는 라벨이 새로 들어오면 FAIL).
  - A13 정적 회귀 가드 — 사다리에서 두 계층 호출 존재 · `renderedIds` 게이팅 ·
    **승격 경로가 자동 펼침(expand/toggle)을 부르지 않음**(접힘은 지속 의도).
- 회귀: `test_detail_dbgroups.js` **78 PASS** · `test_pixi_adapter.js` **190 PASS** ·
  `test_graph_edge_flow.js` **43 PASS** · `test_graph_reveal.js` **17 PASS** ·
  `test_catcluster_panel_scroll.js` **36 PASS** — 전부 0 FAIL.
  (`test_g6build_*.js` · `test_graph_colnav.js` · `test_detail_colsel.js` 는 인자 없이 실행 시
  `ERR_INVALID_ARG_TYPE`, 인자를 줘도 whole-file vm-eval 이 ES-module 리팩터(ITEM-09) 이후
  동작하지 않는다 — **main baseline 에서 동일 재현**을 확인한 pre-existing 실패로 본 cycle 무관.
  그중 `test_graph_colnav.js` 가 덮던 `_metaRenderedAncestorFor` 커버리지는 본 cycle 의
  신규 스위트가 함수-추출 패턴으로 사실상 복원한다.)
- `node --check`(ESM) — `graph-core.js` · `graph-ctxmenu.js` PASS.

# Run — PB-0008 실 Windows 브라우저 라이브 검증 (Environment: Windows-browser)

- Runner: AI (`bin/win-browser.py` relay)
- Bridge: `relay` @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115 · `doctor.ok=true`
- 스테이징: 라이브 web-a/web-b 무접촉 **격리 컨테이너**(§13.2.9) — `mysql-ai-web:b6882c7d`(현행 서빙
  이미지)로 `web-catfocus-test` 기동(`repo_dbnet`+`llm-shared`+`replica-net`, host `:18098`, env 는
  기존 컨테이너 사본 — 공유 `.env.secret`·`docker-compose.override.yml` 미수정) → 변경 2파일
  (`graph-core.js`·`graph-ctxmenu.js`) `docker cp` → 컨테이너 안에서
  `scripts/inject_asset_stamp.py --root /app/web/static` 재실행(ES import specifier 단일 스탬프
  재기입 — 이중 인스턴스화 회피) → 재시작.
  **서빙 baked 2중 확인**: 서빙 `graph-core.js` 에 신규 심볼 7건 / `graph-ctxmenu.js` 3건,
  `admin.js?v=6f2cb7201d93` = 컨테이너 `.asset-stamp` 일치.
  **모듈 인스턴스 동일성 가드**: 페이지 컨텍스트에서 import 한 `_metaGraph` 가 라이브 렌더러를
  보유(`graph !== null`, renderedIds 실데이터)함을 확인 후에만 조작 — QA 핸들만 window 에 두고
  **소스 무변경**.
- 대상: `/admin` → 그래프 뷰 → 데이터소스 `mssql-web-qa` → 스키마 `masangsoftweb` 펼침
  (테이블·함수 295 · 컨텐츠 카테고리 다수 · 제품 카테고리 밴드 7). 대상 컨텐츠 카테고리 =
  `이벤트 아이템 지급`(be:0, 멤버 40) · 대상 테이블 = `L_DK_EVENT_ITEM_GIVE_160707_RETURN_ITEM` ·
  대상 제품 카테고리 = `PC:117 국내 웹 - QA`(23 DB · 1,056 테이블).
- 조작: 컨텐츠 카테고리 접기는 GX 컨트롤 좌클릭과 **동일 경로**(`groupCollapsed.add` +
  `_metaG6Apply`), 카메라 이동은 상세 패널의 **실 DOM 버튼 `🎯 이 노드로 이동`(`#metaGraphFocusSelBtn`)
  클릭**. 거리 = 요소 bbox 중심의 뷰포트 좌표와 캔버스 중심의 유클리드 거리(px).

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 컨텐츠 카테고리 접힘 → 승격 대상 해소 | 테이블 미렌더 · `GB:` 렌더 · 스키마 combo 렌더 상태에서 `_metaRenderedAncestorFor` = **`GB:…be:0`**, 명칭 = **컨텐츠 카테고리** **PASS** |
| 2 | **핵심 — 카메라 실이동** | `🎯 이 노드로 이동` 클릭 전후로 GB 거리 **1189 → 3px**(정착), 스키마 클러스터 중앙 거리 **40 → 1148px**(오이동 대상에서 결정적으로 이탈) **PASS** |
| 3 | 상태줄 | `→ 'L_DK_EVENT_ITEM_GIVE_160707_RETURN_ITEM' 의 컨텐츠 카테고리로 카메라 이동 (그 클러스터를 펼치거나 확대·검색으로 하위 노드를 직접 탐색할 수 있습니다).` **PASS** |
| 4 | 제품 카테고리 밴드 접힘 | 스키마 클러스터 통째 미방출(`combo` 미렌더 · `SC:` 카드도 미렌더)에서 승격 대상 = **`CAT:PC:117`**, 카메라 거리 **2px** 정착, 상태줄 `… 의 제품 카테고리로 카메라 이동` **PASS** (종전 = 승격 대상 null → 카메라 미이동 + "표시할 수 없습니다") |
| 5 | 회귀(전부 펼침) | 테이블 자신 렌더 · 카메라 거리 **2px** 정착 · 상태줄 `→ … 로 카메라 이동.`(승격 문구 없음) **PASS** |
| 6 | 콘솔 | `pageerror` / `console.error` **0건** |

- Evidence(스크린샷 4매): `artifacts/shared/win-browser-shots-catcluster-focus/`
  - `01_before_focus.png` — 클릭 전(카메라가 다른 위치)
  - `02_group_collapsed_focused.png` — **접힌 컨텐츠 카테고리 `이벤트 아이템 지급 · 40` 밴드가 캔버스 중앙에 정착**
  - `03_catband_collapsed_focused.png` — 접힌 제품 카테고리 밴드 `국내 웹 · QA · 23 DB · 1,056 테이블` 중앙 정착 + 상태줄 안내
  - `04_all_expanded_table_focused.png` — 회귀(전부 펼침 시 테이블 자신)
- 정리: 격리 컨테이너 `docker rm -f` 완료 · 임시 env 파일 삭제 · **라이브 web-a/web-b·공유 checkout
  무접촉**(정리 직후 `repo` = `main` / dirty 0 재확인).
- **재-Run 이력(정직 표기)**: 1차 Run(stamp `867456df13cb`)에서 상태줄 조사가 `카테고리(으)로` 로
  어색함을 실화면 판독으로 포착 → 전 라벨이 모음/ㄹ 받침이라 `로` 가 맞음을 확인하고 정정(+ 테스트
  A12 조사 불변식 추가) → **정정본으로 컨테이너를 재구성해 위 6 시나리오를 전건 재측정**했다.
  위 표는 전부 최종 빌드(stamp `6f2cb7201d93`) 실측이다.
- 한계(정직 표기):
  - 팬 루프는 `requestAnimationFrame` 기반이라 **탭이 백그라운드면 rAF 스로틀**로 1.2s 상한 안에
    2~9 프레임만 돌아 정착이 덜 된다(첫 측정에서 GB 거리 688px 관측). 위 표 수치는 모두
    `bring_to_front()` 로 **탭을 전면화한 뒤**의 실측이며, 스로틀 구간을 실패로 오독하지 않도록 명시한다.
  - 컨텐츠 카테고리 접기를 GX 컨트롤 **합성 클릭**이 아니라 동일 상태 경로(`groupCollapsed.add` +
    `_metaG6Apply`)로 유발했다 — GX 클릭 핸들러(graph-core.js `cat-ctl`/`group-ctl` 분기)가 하는 일과
    동일하지만, 좌표 기반 합성 클릭 자체의 히트테스트는 본 Run 범위 밖(직전 cycle 에서 검증된 경로).
  - `_metaGraphPanToRelation`(상세 패널 관계 행 단일 클릭) 은 모듈 export 가 아니라 직접 호출로
    측정하지 않았다. 다만 그 경로와 hover-pan · 하이라이트 해소는 **동일한
    `_metaRenderedAncestorFor` 를 공유**하며, 시나리오 1·4 가 그 해소 결과를 라이브 렌더 상태에서
    직접 단정한다.
