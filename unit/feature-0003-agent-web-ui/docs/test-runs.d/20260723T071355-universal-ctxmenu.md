---
run_at: 2026-07-23T16:13:55+09:00
session: ai/claude/feature-0003-universal-ctxmenu
scope: [web-ui, frontend, contextmenu]
verdict: PASS (PRE-COMMIT + POST-DEPLOY 라이브)
---

### Run (2026-07-23) — universal-ctxmenu: 서비스 UI 우클릭 = 보편 확장 메뉴 단축 (대화 목록·폴더='···', 말풍선='☰') (Major §12.3 — feature-0003 web/UI 프론트, frontend-only) — **Environment: Windows-browser**

- **PRE-COMMIT 로컬 검증 (PASS)**: `node --check app.js` PASS(초안 + 리뷰 반영 후 2회). §18.8 적대적 프론트/UX 리뷰(general-purpose, REV-20260723T071355-universal-ctxmenu) verdict **SHIP** (BLOCKING/MAJOR 0) — 앵커 수명(`_floatingMenuAnchorPoint` 1회 소비·finally 방어 해제·left-click 누출 없음)·anchor=null 경로 byte-동치·synthetic click 이 대화 선택/폴더 토글 유발 안 함(우클릭=button2 는 native click 미발화 + 트리거 stopPropagation)·예외 가드(closest/nodeType/querySelector/MouseEvent) 검증 통과. MINOR 3 반영: ①미디어(img/svg/canvas/video) 네이티브 우클릭 양보(이미지 저장·mermaid SVG 보존) ②키보드 contextmenu(0,0) → trigger-rect 폴백 ③`_hasSelectionWithin` → `Range.intersectsNode` 정밀화(다른 곳 stale 선택 과잉차단 제거).
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: 정적 자산(app.js) 이 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산 실측 가능(feature-0003 정적자산 동일 패턴). **POST-DEPLOY PB-0008 라이브 append 예정** — AC:
  - AC-1 좌측 대화 항목 우클릭 → 그 대화 '···' 메뉴(공유/설정/폴더)가 커서 위치에 개방, 항목·권한 게이트가 버튼 클릭과 동일.
  - AC-2 폴더 헤더 우클릭 → 폴더 '···' 메뉴(하위 폴더/이름 변경/지침/삭제).
  - AC-3 말풍선(대화 로그) 우클릭 → '☰' 메뉴(샘플 등록/분기/공유/AI로 고치기); 메뉴 없는 말풍선은 브라우저 기본 우클릭 유지.
  - AC-4 말풍선 내 텍스트 선택 후 우클릭 → 브라우저 기본 메뉴(복사) 유지; 미디어(mermaid SVG·이미지)·링크 우클릭 → 기본 메뉴(저장/열기).
  - AC-5 기존 '···'/'☰' 버튼 클릭 동작·위치 불변(anchor=null byte-동치). pageerror 0.
- **Pass/Fail: PRE-COMMIT 문법 + 적대 리뷰 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 존재 + POST-DEPLOY 계획 — conv-date-tree/paging-scroll 등 직전 feature-0003 정적자산 cycle 과 동일 패턴).

- **[POST-DEPLOY 2026-07-23] universal-ctxmenu 라이브 검증 (PASS, Environment: Windows-browser, AI 직접 — 실 Windows Chrome 150 via bin/win-browser.py relay, https://localhost/ 작업 화면, 배포본 c6f7f98a)**: PR #897 → main **c6f7f98a** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·90s soak PASS·caddy no-op·자산 스탬프 주입). **서빙 자산(curl)**: index.html→`app.js?v=e6d39fde416f`(content-hash 갱신); 서빙 app.js 신규 심볼 `_CTX_MENU_TARGETS`(2)·`_onUniversalContextMenu`(2)·`_floatingMenuAnchorPoint`(5)·`_hasSelectionWithin`(2)·`addEventListener("contextmenu"`(1) 전부 hit. **라이브 우클릭 dispatch(win-browser eval, 실 contextmenu MouseEvent button2)**:
  - **AC-1 PASS** — 대화 항목 우클릭(68,222) → `defaultPrevented=true`(native 억제) + `#convItemMenu` 커서 위치(top 226·left 68·nearCursorX/Y=true) 개방, 항목=[공유·설정·▸폴더·＋새 폴더로 이동], trigger `aria-expanded=true`.
  - **AC-2 PASS** — 폴더 헤더 우클릭(48,164) → `defaultPrevented=true` + `#folderMenu`(top 168·left 48·nearCursor) 항목=[하위 폴더 추가·이름 변경·지침 추가·삭제].
  - **AC-3 PASS** — assistant 말풍선 우클릭(scrollIntoView 후 588,187) → `defaultPrevented=true` + `#bubbleMsgMenu`(top 191·left 588·nearCursor) 항목=[여기서 분기·여기까지 공유·여기부터 공유], `aria-expanded=true`. (초기 시도는 대상이 뷰포트 위로 스크롤돼 viewport 클램프 top=8 동작 — 정상.)
  - **AC-4 PASS** — 말풍선 내 텍스트 663자 선택 후 우클릭 → `defaultPrevented=false`(**native 메뉴 보존**) + `#bubbleMsgMenu` 미개방(bubbleMenuOpen=false). 복사 회귀 없음.
  - **AC-5 PASS** — 기존 '···' 버튼 **click**(anchor 없음) → 메뉴 `menuRight==trigRight`(rightAligned) + `menuTop>=trigBottom`(belowTrigger) = trigger-rect 기준 위치 **byte-동치**(우클릭 앵커와 독립·회귀 0). `closeFloatingMenus` 후 잔존 0.
  - **오류**: `window.__errs` 캡처 **errCount=0**(pageerror 0). 스크린샷 scratchpad/universal-ctxmenu-live.png(199KB).
- **Pass/Fail: PASS** (CHECK#13 충족 — POST-DEPLOY 라이브 실측 완료. 우클릭이 대화/목록('···')·로그('☰') 확장 메뉴를 커서 위치에 개방·기본 우클릭(텍스트 선택) 양보·버튼 클릭 byte-동치 전부 라이브 확증).
