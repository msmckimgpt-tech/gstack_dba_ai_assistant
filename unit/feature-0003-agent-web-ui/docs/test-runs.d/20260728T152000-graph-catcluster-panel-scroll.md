---
run_at: 2026-07-28T15:20:00+09:00
session: ai/claude/feature-0016-catcluster-panel-scroll
scope: 캔버스 컨텐츠 카테고리(sim-group) 선택 → '스키마 클러스터' 상세 목록 스크롤 동기화 (graph-catcluster-scroll)
verdict: PASS
---

# Run — graph-catcluster-scroll 헤드리스 결정론 (Environment: node vm)

- 신규 `tests/headless/test_catcluster_panel_scroll.js` **36 PASS / 0 FAIL**.
  `graph-ctxmenu.js` 에서 `_META_GKEY_SEP` · `_metaGroupFam` · `_metaGraphFocusPanelGroup`
  본문을 **원본에서 추출**해 vm 격리 실행(사본 아님 — test_detail_dbgroups.js 와 동일 패턴).
  - ① fam 추출: 캔버스 키(`<comboId><fam>`)·패널 키(`panel:<name><fam>`) 양쪽에서
    구분자 뒤 토큰만 취함 · 구분자 부재/null graceful · fam 내부 콜론(`be:12`) 비절단.
  - ② **핵심 계약** — 네임스페이스가 다른 두 키가 fam 으로 매칭되고, 목표 y =
    `scrollTop + (heading.top − box.top) − navH − 6`, `behavior:smooth`, 도착 강조 클래스
    부여 → 1.8s 타이머 해제, 다른 그룹 미강조.
  - ③ sticky 이력 바 표시 시 그 높이(44)만큼 위 여백 확보 / 숨김(이력 ≤1)이면 보정 0.
  - ④ 음수 목표 0 클램프. ⑤ 세대 토큰 — 더 최근 선택이 들어오면 rAF 안의 stale 스크롤·강조 폐기.
  - ⑥ graceful no-op 4종(fam 미지정 · 미매칭 · 스크롤 컨테이너 부재 · 목록 부재) → 기존 동작 보존.
  - ⑦ `prefers-reduced-motion: reduce` → `behavior:auto`, `matchMedia` 미지원 환경도 throw 없음.
  - ⑧ **호출부 인자 매핑**(유닛만 보면 호출부가 fam 을 안 넘겨도 전건 PASS 하는 사각을 차단):
    graph-core GB/GH 좌클릭이 `_metaGraphShowClusterDetailById(sc, gk.slice(sep + 1))` · 우클릭
    '소속 스키마 상세' 가 `(schemaKey, key.slice(sep + 1))` · ById→Render→FocusPanelGroup 전달
    체인 · 패널 헤딩의 `data-group-key` 방출 · 패널 sim-group 의 `panel:` 네임스페이스 전제.
  - ⑨ CSS 강조 클래스(`.amgr-ct-group.is-focus` · `@keyframes amgrCtGroupFocus` ·
    reduced-motion 대응) 존재 — JS 가 붙이는 클래스에 스타일이 없으면 무음 실패한다.
- 회귀: `test_detail_dbgroups.js` **78 PASS / 0 FAIL** · `test_pixi_adapter.js` **190 PASS / 0 FAIL**.
  (`test_g6build_simgroups_p2.js` · `test_detail_colsel.js` 는 인자 없이 실행 시 ERR_INVALID_ARG_TYPE —
  **main baseline 과 동일한 pre-existing 실패**로 확인, 본 cycle 무관.)
- `node --check`(ESM) — 변경 3개 JS 모두 PASS.

# Run — PB-0008 실 Windows 브라우저 라이브 검증 (Environment: Windows-browser)

- Runner: AI (`bin/win-browser.py`)
- Bridge: `relay` @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115 · `doctor.ok=true`
- 스테이징: 라이브 web-a/web-b 를 건드리지 않는 **격리 컨테이너**(§13.2.9) —
  `mysql-ai-web:aa7dc072` 이미지로 `web-catcluster-test` 기동(`repo_dbnet`+`llm-shared`+`replica-net`,
  host `:18099`) → 변경 static 4파일 `docker cp` → 컨테이너 안에서
  `inject_asset_stamp.py --root /app/web/static` 재실행(ES import specifier 까지 단일 스탬프로
  재기입 — **이중 인스턴스화 회피**, AGENTS.md §13.1) → 재시작.
  **서빙 baked 2중 확인**: 서빙 JS 에 `_metaGraphFocusPanelGroup` 2건 / `gk.slice(sep + 1)` 1건,
  `admin.js?v=c6c6868326db` = 컨테이너 `.asset-stamp` 와 일치.
- 대상: `/admin` → 그래프 뷰 → 데이터소스 `mssql-web-qa` → `masangsoftweb` 스키마 펼침
  (테이블·함수 595개 · 컨텐츠 카테고리 **93개** · 패널 목록 595행 · `scrollHeight` 17,277px).
- 조작: 캔버스 합성 좌클릭/우클릭(`PointerEvent` button0/button2 + `contextmenu`) — 대상 요소는
  `getElementPosition` → `getViewportByCanvas` 로 화면 좌표 산출 후 캔버스에 디스패치.
  QA 핸들은 페이지 컨텍스트의 `window.__mg`(barrel `graph.js` 동적 import) — **소스 무변경**.

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 패널 최하단(16,661)에서 캔버스 `문피아 계정 이전`(be:2) 헤더 좌클릭 | scrollTop 16,661 → **1,667 정착**, 해당 헤딩이 뷰포트 상단 **+53px**(= sticky nav 47 + 여백 6), 첫 가시 그룹 = `be:2 문피아 계정 이전` **PASS** |
| 2 | 이어서 `소셜회원관리`(be:51) 헤더 좌클릭 | scrollTop → **12,392**, 해당 헤딩 **+53px**, 첫 가시 그룹 = `be:51` **PASS** |
| 3 | 도착 강조 | 클릭 1.1s 후 `.amgr-ct-group.is-focus` **1건**(라벨 `문피아 계정 이전`) → 1.5s 추가 대기 후 **0건**(자동 해제) **PASS** |
| 4 | 상태줄 | `클러스터: masangsoftweb · 테이블 295개 · 함수·프로시저 300개 · 목록을 '문피아 계정 이전' 위치로 이동` **PASS** |
| 5 | 우클릭 경로 | 컨텐츠 카테고리 우클릭 메뉴 `📋 소속 스키마 상세 / 이 카테고리 위치로 목록 이동` 클릭 → scrollTop 0 → **15,134**, `게임라우팅` 헤딩 **+53px** **PASS** |
| 6 | 회귀(비-대상 경로) | 스키마 카드(`SC:`) 좌클릭은 fam 미전달 → 상태줄에 `위치로 이동` 문구 **없음**, 강제 스크롤 **없음**(해당 클러스터 목록 정상 렌더) **PASS** |
| 7 | 콘솔 | `window.onerror` / `unhandledrejection` **0건** |

- Evidence(스크린샷 5매): `artifacts/shared/win-browser-shots-catcluster-scroll/`
  - `01_before_bottom.png` — 클릭 전(패널 최하단)
  - `02_munpia_focus_highlight.png` — **도착 강조 순간**(패널 `문피아 계정 이전` 파란 강조 + 좌측 바, 캔버스의 동명 그룹 박스 동시 가시, 상태줄 이동 안내)
  - `03_munpia_settled.png` — 정착 상태
  - `04_social_settled.png` — 두 번째 카테고리(`소셜회원관리`) 정착
  - `05_ctxmenu_path_settled.png` — 우클릭 경로 정착(`게임라우팅`)
- 정리: `win-browser.py down` 완료(relay 포함) · 격리 컨테이너 `docker rm -f` 완료 ·
  **라이브 web-a/web-b·공유 checkout 무접촉**(§13.2.9 격리 경로 — `docker-compose.override.yml`·`.env.secret` 미수정).
- 한계(정직 표기): 장거리 smooth 스크롤은 브라우저 애니메이션이라 **클릭 직후 800ms 시점 측정은 이동
  중간값**(2,254 등)이 나온다. 위 표의 수치는 모두 **정착 후**(+2.5s / +3.5s) 실측이며, 중간 프레임을
  실패로 오독하지 않도록 명시한다.
