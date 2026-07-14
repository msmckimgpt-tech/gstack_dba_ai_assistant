---
run_at: 2026-07-14T18:03:14+09:00
session: graph-entry-help (ai/claude/feature-0003-graph-entry-help)
scope: 그래프 뷰 첫 입장 조작 도움말 팝업(닫기·재확인 가능, localStorage 1회 자동노출) + 중간버튼 팬 커서 grabbing 표식 (feature-0003 web/UI 프론트, 그래프 도메인 정본 feature-0016)
verdict: PASS (코드/정적 + POST-DEPLOY 라이브 — 로직(자동노출·닫기·커서) PASS; 팝업 위치는 POST-DEPLOY 에서 mis-position 발견 → CSS 주석 `*/` hazard 수정(20260714T184717-graph-help-overlay-fix) → 중앙정렬·줌 미겹침 재검증 PASS)
---

### Run (2026-07-14) — graph-entry-help: 첫 입장 도움말 팝업 + 중간버튼 커서 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, additive) — **Environment: node --check + 정적 구조 검증**

- 변경 파일(3, additive): `static/admin.html`(❓ 도움말 버튼 + `#metadataGraphHelp` 오버레이 마크업) · `static/graph/graph.css`(`.amg-help-*` 스타일) · `static/graph/graph-core.js`(`_metaGraphShowHelp`/`Hide`/`MaybeAutoHelp`/`BindHelp` + `_metaShowGraph` 훅 + 중간버튼 `mousedown` 커서 표식).
- 문법/구조: `node --check --input-type=module`(graph-core.js) **PASS** · admin.html 도움말 블록 `amg-help` 20 매치·태그 균형 · graph.css 중괄호 **215/215 균형** · 새 심볼(`_metaGraphBindHelp`/`MaybeAutoHelp`/`ShowHelp`/`HideHelp`/`_META_HELP_SEEN_KEY`) 전수 존재.
- 로직 계약(코드 정독 확인):
  - 첫 진입 자동노출: `_metaShowGraph`(진입 1회, admin.js `graphInitialized` 가드) → `_metaGraphMaybeAutoHelp` → `localStorage("metaGraphHelpSeen") !== "1"` 일 때만 표시. localStorage 접근 실패는 try/catch 로 '미확인=노출' 안전 강등(기존 metaGraphHiddenKinds/metaGraphDetailW 관례 동일).
  - 닫기 4경로: ✕(`#metadataGraphHelpClose`)·"알겠습니다"(`#metadataGraphHelpOk`)·배경(`data-amg-help-close`/오버레이 여백 target 판정)·Esc(document capture keydown, 표시 중에만 등록·해제). 모든 닫기가 `_metaGraphHideHelp` → seen 플래그 set + ❓ 버튼 포커스 복귀.
  - 재확인: ❓ `#metadataGraphHelpBtn` → `_metaGraphShowHelp`(seen 무관 항상 표시).
  - 바인딩 멱등: `_metaGraph._helpBound` 가드(재진입 이중 바인딩 차단).
  - 중간버튼 커서: `#metadataGraphCanvas` `mousedown` button===1 → `preventDefault`(기존 autoscroll 억제) + `cursor="grabbing"`; 복원은 mouseup(단 `buttons & 4` 여전 눌림이면 유지 — 팬 중 깜빡임 방지)·window `blur`(뗌 이벤트 유실 대비). 캔버스 명시 cursor 부재 → 자식 `<canvas>` 상속(렌더러 무관).
- 비변경: 백엔드/엔드포인트/RBAC/스키마 0 · 기존 그래프 상호작용(팬·노드드래그·우클릭·줌·미니맵)·이벤트 바인딩 0 · cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- §18.8: 3파일·비파괴·additive·백엔드/RBAC 무변경 Minor → 패널 skip.
- 결과: 코드/정적 검증 **PASS**.

### Run (2026-07-14) — 도움말 팝업·중간버튼 커서 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산)**: 정적 자산(admin.html/graph.css/graph-core.js)은 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산·런타임 실측 가능(feature-0003 web/UI 자산의 확립 패턴). win-browser relay 로 라이브 시각검증 가능(PB-0008) → **POST-DEPLOY 라이브 append 예정**.
- **배포 후 계획(PB-0008, win-browser.py relay @ https://localhost/admin 그래프 뷰)**:
  - (a) **첫 입장 자동노출**: `localStorage.removeItem("metaGraphHelpSeen")` 후 그래프 뷰 진입(또는 새 프로필/시크릿) → 조작 안내 팝업 자동 1회 노출.
  - (b) **닫기 4경로**: ✕·"알겠습니다"·배경 클릭·Esc 각각으로 닫힘 + `localStorage.getItem("metaGraphHelpSeen")==="1"` 확인.
  - (c) **재진입 무자동노출·재확인**: 닫은 뒤 탭 이탈→재진입 시 자동노출 없음, ❓ 도움말 버튼 클릭 시 재노출.
  - (d) **중간버튼 커서**: 캔버스에서 가운데 버튼 누른 채 드래그 → 커서 `grabbing`·팬 동작 정상, 버튼 뗌 시 커서 복원(getComputedStyle 캔버스 cursor eval).
  - (e) **회귀/무결**: 그래프 렌더·기존 상호작용 정상, pageerror 0, 스크린샷.
- 결과: 정적 검증 PASS · 라이브 시각검증 **DEFERRED(배포 후)**.

### Run (2026-07-14 POST-DEPLOY) — 도움말 팝업·중간버튼 커서 라이브 PASS — **Environment: Windows-browser (AI 직접 — 실 Windows Chrome via bin/win-browser.py relay @ 172.26.144.1:9223)**

- 배포: PR #795 머지 → main **1f705a9e** → `deploy-web.sh --web-only` 무중단 롤링(web-a/web-b one-at-a-time recreate·90s soak PASS·Caddyfile 무변경 no-op·asset 스탬프 주입 `?v=dev` 잔존 0). `/healthz` git_commit=**1f705a9e**·mysql_ok·pg_ok.
- **서빙 자산 실측(curl https://localhost/)**: admin.html 에 `metadataGraphHelpBtn` 존재 · `graph-core.js?v=4335ea1dac52`/`graph.css?v=4335ea1dac52`(content-hash 스탬프 주입) · 서빙 graph-core.js 내 도움말/커서 심볼(`_metaGraphBindHelp`/`_metaGraphMaybeAutoHelp`/`cursor = "grabbing"`/`metaGraphHelpSeen`) 7 hit.
- **런타임 assertion(win-browser eval, https://localhost/admin bootstrap_admin 세션, 그래프 뷰 pane)**:
  - **첫 입장 자동노출**: `localStorage.removeItem("metaGraphHelpSeen")` + 새로고침 → 그래프 탭 클릭 → `#metadataGraphHelp` **자동 노출**(popupAutoShown=true), 조작 항목 8개, 제목 "그래프 뷰 조작 안내", ❓ 버튼 노출, seen 플래그 미설정(자동노출 직후).
  - **닫기 4경로 + seen**: "알겠습니다" 클릭→hidden + **seen="1"** set / ❓ 버튼→재노출 / ✕→hidden / Esc→hidden / 배경(data-amg-help-close) 클릭→hidden. 4경로 전부 PASS.
  - **재진입 무자동노출**: seen="1" 상태에서 새로고침+그래프 탭 재진입 → 자동노출 **false**(reentry_autoShown=false). 재확인은 ❓ 버튼만.
  - **중간버튼 커서**: 캔버스 `mousedown(button=1,buttons=4)` → 커서 `auto`→**`grabbing`** / `mouseup(buttons=0)` → 복원(빈 문자열=상속 auto). PASS.
- **시각(초기 관측 — 결함)**: 로직은 통과했으나 **팝업 카드가 중앙 모달로 뜨지 않고 캔버스 아래로 밀려** 좌하단 줌 컨트롤과 겹침. 초기엔 "짧은 뷰포트에서 카드가 canvas-wrap 높이를 초과해 내부 스크롤되는 minor UX" 로 오진했으나, 사용자 지적("도움말 팝업을 그래프 뷰 중앙에 위치·좌하단 줌 컨트롤 겹침 해결")으로 재조사 → `.amg-help-overlay` 의 `position:absolute` 가 런타임에서 `static` 으로 폴백(규칙 자체 미적용)임을 win-browser eval 로 확인. pageerror 는 0(파싱 오염은 조용히 규칙만 드롭).
- **근본원인·수정**: 아래 "POST-DEPLOY FIX" 섹션 참조 — CSS 주석 내 `--text*/` 의 `*/` 조기 종료로 바로 뒤 규칙이 드롭됨. 20260714T184717-graph-help-overlay-fix 에서 수정·재검증.
- 결과: **로직 라이브 PASS(자동노출·닫기 4경로·seen·재진입·중간버튼 커서)** · **팝업 위치는 결함 발견 → 수정(다음 섹션)**.

### Run (2026-07-14 POST-DEPLOY FIX) — 도움말 팝업 mis-position 근본원인 수정·재검증 — **Environment: Windows-browser (AI 직접 — 실 Windows Chrome via bin/win-browser.py relay @ 172.26.144.1:9223) + graph.css parse 분석**

- **증상**: 배포본(1f705a9e) 그래프 뷰에서 `#metadataGraphHelp` 오버레이가 중앙 정렬 대신 캔버스 아래로 흘러 줌 컨트롤(y=708) 위에 겹침.
- **진단(라이브 CDP)**: `getComputedStyle(overlay)` → `position:static`, `display:block`, `z-index:auto`, `align-items:normal` = `.amg-help-overlay` 규칙 **전 속성이 기본값** = 규칙 미적용. graph.css 는 로드됨(styleSheets 존재)·서빙본은 소스와 byte-identical(493L/38580B). `sheet.cssRules` 검사 → `.amg-help-overlay[hidden]`·`.amg-help-backdrop` 등은 파싱되나 **bare `.amg-help-overlay` 만 cssRules 에 부재**(파서 드롭). 격리 파싱 시엔 정상 → 규칙 텍스트가 아니라 **직전 문맥** 문제로 특정.
- **근본원인(확정)**: 규칙 바로 위 주석(line ~447)의 토큰 목록 `토큰(--surface/--border/--text*/--primary)만` 에서 `--text*` 뒤 `/` 와 만나 **`*/` 서브스트링 형성 → CSS 주석이 조기 종료** → 이후 텍스트(`--primary)만 써서…조작). */`)가 깨진 CSS 로 유입 → 바로 아래 `.amg-help-overlay { position:absolute … }` 규칙 통째 드롭 → position static 폴백 → flex column 흐름에서 캔버스 아래 렌더·줌 겹침. (`/*`:`*/` 개수 수정 전 61:62 불균형 → 수정 후 61:61.)
- **수정**: 주석 토큰 구분자 `/` → `·`(`--surface·--border·--text*·--primary`), `*/` 서브스트링 제거 + 재발 방지 NOTE 삽입. **CSS 선언·선택자·미디어쿼리 무변경**(주석 텍스트 국한, git diff +4/-2).
- **재검증(win-browser eval, 라이브 페이지)**:
  - **파싱 복구**: 수정본 파싱 시 `.amg-help-overlay` 규칙 존재(`has:true`)·`position:absolute` 복구(rule count 204→205).
  - **실제 geometry(수정 규칙 라이브 주입 후 측정)**: overlay `position:absolute`·`display:flex`; 카드가 canvas-wrap **정중앙**(카드 center=wrap center, `dx:0 dy:0`); **카드 ↔ 줌 컨트롤 미겹침**(`card_overlaps_zoom:false`; 카드 하단 y=694 < 줌 상단 y=704).
- **§18.8 적대적 검증**: SUBAGENT PASS — 주석 델리미터 61/61 균형, edited 주석·NOTE 에 의도치 않은 `*/` 없음(byte 확인: `*·`/`` `*` + `/` `` 분리), diff 주석 국한, 잔여 `*`+`/` hazard 없음. NIT(prose-only NOTE, CI grep 가드는 out-of-scope).
- 결과: **POST-DEPLOY FIX — 팝업 중앙정렬·줌 미겹침 라이브 재검증 PASS**.
- **재배포 자산 최종 확인(2026-07-14, PR #798 머지 → main 8d1285d0 → deploy-web --web-only soak PASS)**: `/healthz` git_commit=**8d1285d0**·mysql_ok·pg_ok. 서빙 `graph.css` 스탬프 `4335ea1dac52`→**`d5f26a416089`**(content-hash 갱신)·소스와 byte-identical·`/*`:`*/` 61:61 균형. **주입 없이** 배포본 런타임 측정(win-browser eval, 그래프 뷰 pane 활성): `sheet.cssRules` 에 `.amg-help-overlay` **파싱 복구**(overlayRuleParsed=true) · `getComputedStyle` = `position:absolute`·`display:flex`·`align-items:center`·`z-index:40`(수정 전 static/block/normal/auto) · 카드 canvas-wrap **수평 정중앙**(dx:0)·수직 dy:6px(447px 카드 기준 사실상 중앙) · **줌 컨트롤 미겹침**(card_overlaps_zoom=false, 카드 하단 694 < 줌 상단 704) · ❓ 버튼→팝업 노출 스크린샷 육안 확인(중앙 모달+backdrop, 하단 줌 컨트롤 비겹침). pageerror 0. → **배포본 실증 PASS**.
