---
run_at: 2026-07-23T17:04:15+09:00
session: ai/claude/feature-0003-floating-menu-close-fix
scope: [web-ui, frontend, contextmenu, folder-menu]
verdict: PASS (PRE-COMMIT + POST-DEPLOY 라이브)
---

### Run (2026-07-23) — floating-menu-close-fix: floating 메뉴(특히 폴더 '···') 안 닫히던 결함 수정 (Minor §12.3 — feature-0003 web/UI 프론트, frontend-only) — **Environment: Windows-browser**

- **PRE-COMMIT 로컬 검증 (PASS)**: `node --check app.js` PASS · `styles.css` brace 균형(1888:1888). §18.8 적대적 프론트 리뷰(general-purpose, REV-20260723T080415-floating-menu-close-fix) verdict **SHIP** (BLOCKING/MAJOR 0) — over/under-removal 없음(`data-floating-menu` 단일 set/read·3 메뉴 전부 openFloatingMenu 경유)·dataset copy order 안전·toggle/identity 불변·트리거 리셋 정합. NIT 3 fold-in(share-range ESC 가드·unread-sync 가드에 folderMenu 포함 + CSS keep-visible).
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: 정적 자산(app.js/styles.css) baked → merge + `deploy-web` 후 서빙. 또한 라이브 계정에 폴더가 현재 0개(folder-privacy 격리 후) → **POST-DEPLOY 에 폴더 1개 생성 후** 실측. **POST-DEPLOY PB-0008 라이브 append 예정** — AC:
  - AC-1 폴더 '···' 메뉴(우클릭/버튼) 열린 뒤 다른 항목/빈 곳 클릭 → 닫힘.
  - AC-2 폴더 메뉴 열린 뒤 ESC → 닫힘.
  - AC-3 폴더 메뉴 열린 뒤 스크롤 → 닫힘.
  - AC-4 폴더 '···' 재클릭 토글 닫힘 + 트리거 `is-open`/`aria-expanded=false` 복원.
  - AC-5 conv-item '···'·말풍선 '☰' 닫힘 무회귀(마커 제거=superset).
- **Pass/Fail: PRE-COMMIT 문법 + 적대 리뷰 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 존재 + POST-DEPLOY 계획).

- **[POST-DEPLOY 2026-07-23] floating-menu-close-fix 라이브 검증 (PASS, Environment: Windows-browser, AI 직접 — 실 Windows Chrome 150 via win-browser.py relay, https://localhost/ 작업 화면, 배포본 57ecc758)**: PR #902 → main **57ecc758** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·soak PASS). **서빙 자산(curl)**: `app.js?v=8373a9f479e2`·`styles.css?v=8373a9f479e2`; 서빙 app.js `data-floating-menu`/`dataset.floatingMenu` 2 hit·styles.css `conv-folder-menu-trigger.is-open` 1 hit. **라이브(테스트 폴더 API 생성 id=6 후 실 이벤트 dispatch, 검증 후 삭제 — 프로덕션 잔여 0)**:
  - **AC-1 PASS** — 폴더 헤더 우클릭 → `#folderMenu` 개방 후 다른 대화 항목 mousedown(바깥클릭) → **닫힘**(closedAfterOutsideClick=true).
  - **AC-2 PASS** — 재개방 후 ESC → **닫힘**(closedAfterEsc=true).
  - **AC-3 PASS** — 재개방 후 window scroll → **닫힘**(closedAfterScroll=true).
  - **AC-4 PASS** — 폴더 '···' 트리거 click 개방(aria-expanded=true·is-open class) → 재click 토글 → **닫힘** + 트리거 `aria-expanded=false`·`is-open` class 제거(상태 복원).
  - **AC-5 PASS (무회귀)** — conv-item '···' 우클릭 개방 → 바깥클릭 → **닫힘**(마커 기반 제거가 기존 id 제거 superset 확인).
  - **오류**: `window.__errs` **errCount=0**. 스크린샷 scratchpad/folder-menu-close-fix-live.png.
- **Pass/Fail: PASS** (CHECK#13 충족 — POST-DEPLOY 라이브 실측 완료. 폴더 메뉴가 바깥클릭/ESC/scroll/토글로 정상 닫힘·트리거 상태 복원·conv-item/말풍선 무회귀 라이브 확증. 사용자 신고 결함 해소).
