---
run_at: 2026-07-27T16:20:00+09:00
session: ai/claude/feature-0003-product-picker-scroll
scope: [product-picker, composer, dropup-scroll]
verdict: PRE-COMMIT PASS (헤드리스 chromium 11/11 · node --check) · POST-DEPLOY PB-0008 배포 후 실측 예정
---

### Run (2026-07-27) — product-picker-scroll (제품 선택 드롭업 선택 항목 중앙 스크롤) — **Environment: chromium-headless(레이아웃 실측) + Windows-browser(PB-0008 배포 후 실측 예정)**

cycle: `ai/claude/feature-0003-product-picker-scroll` · 정본 = TASK-20260727T160748-product-picker-scroll ·
REV-20260727T160748-product-picker-scroll · CHG-20260727T160748-product-picker-scroll.

- **변경(`src/static/app.js`)**: `scrollProductDropupToSelected(menu)` 신설(선택 항목 중앙 `scrollTop` 계산
  + `[0, scrollHeight-clientHeight]` clamp) · `openProductDropup()`·`renderProductChip()` 열린-상태 재렌더
  분기 2곳 호출 · 검색 입력 `focus({preventScroll:true})`. 백엔드/RBAC/스키마 0.

- **PRE-COMMIT — `tests/headless/verify_product_dropup_scroll.py` 11/11 PASS**
  (chromium 145.0.7632.6, 실 `app.js` 함수 원문 추출 + 실 `styles.css` 주입 — `offsetTop`/`clientHeight`/
  `scrollHeight` 는 레이아웃 산출물이라 DOM 없는 순수 단위검증으로 대체 불가):
  1. `T9` 실 CSS 가 메뉴를 스크롤 컨테이너로 만듦(clientHeight ≤ 320 < scrollHeight)
  2. `T1` **offsetParent 계약** — 항목의 `offsetParent === #productDropupMenu`(offsetTop/scrollTop 동일 기준)
  3. `T2` 중앙 정렬 — 30개 중 12번째 선택 시 항목 중심 == 뷰포트 중심(±1px)
  4. `T3` 가시성 — 선택 항목이 뷰포트 안에 완전히 표시
  5. `T4` 상단 clamp — 첫 항목 선택 시 `scrollTop=0`(음수 없음)
  6. `T5`/`T5b` 하단 clamp — 마지막 항목 선택 시 최대치, 항목 여전히 표시
  7. `T6` 선택 없음(auto 등) — 기존 `scrollTop`(137) 그대로 유지(무간섭)
  8. `T7` 짧은 목록(3개) — `scrollTop=0`, 스크롤 미발생
  9. `T8` `menu` 부재(null / 없는 id) — 예외 없이 no-op
  10. `T2b` 검색칸 미노출 경로(제품 < `PRODUCT_DROPUP_SEARCH_MIN`)에서도 중앙 정렬 성립
  실행: `PLAYWRIGHT_BROWSERS_PATH=/home/claude-corp/.cache/ms-playwright python3 tests/headless/verify_product_dropup_scroll.py`
- **PRE-COMMIT — `node --check app.js` PASS**(문법).
- **시각 증거(헤드리스, 실 CSS)**: `docs/evidence/product-dropup-scroll-before-20260727.png`(현행 — 최상단,
  선택 항목 P_12 화면 밖) · `docs/evidence/product-dropup-scroll-after-20260727.png`(변경 후 — P_12 가 목록
  세로 중앙, 위아래 이웃 제품이 함께 보여 상대 위치 파악 가능).

- **Environment: Windows-browser (PB-0008) — 배포 후 실측 예정(미수행 사유)**: 본 변경은 라이브 배포(web
  재빌드 → 갱신된 `app.js` 서빙) 후에만 실 화면에 반영되므로 미배포 코드에서는 실측 불가. 헤드리스 검증은
  실 CSS·실 함수 기반이나 **실 사용자 화면(Windows 브라우저)의 정본이 아니다**(§15.4.1). 배포 후 검증 항목:
  1. 제품이 많은 계정으로 작업 화면 진입 → 컴포저 제품 chip 클릭 → 드롭업이 **현재 선택 제품을 중앙에 둔 채** 열림(AC-PPSC-1).
  2. 목록 첫 항목(auto)·마지막 제품이 선택된 상태에서 열면 각각 최상단/최하단에 멈추고 선택 항목이 보임(AC-PPSC-2).
  3. 검색 입력 자동 포커스 유지 + 타이핑 필터 정상, 항목 선택·닫힘 무회귀(AC-PPSC-3).
- **Notes**: §18.8 subagent 패널은 **본 세션의 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW
  REV-20260727T160748 에 [SKIPPED:session-policy-no-subagent] 로 사유와 대체 검증(헤드리스 11 케이스 +
  자체 적대 검토 H1~H8)을 명시했다.
