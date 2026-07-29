---
run_at: 2026-07-29T17:42:00+09:00
session: ai/claude/feature-0003-product-picker-keynav
scope: [product-picker, composer, keyboard-nav, a11y]
verdict: PRE-COMMIT PASS (헤드리스 chromium 27/27 · 기존 회귀 11/11 · node --check · make test) · POST-DEPLOY PB-0008 라이브 검증 예정
---

### Run (2026-07-29) — product-picker-keynav (제품 선택 드롭업 검색 후 방향키 순회 + Enter 선택) — **Environment: chromium-headless(실 렌더 경로 + 실 CSS 레이아웃 실측)** · **Environment: Windows-browser (PB-0008) = 배포 후 수행(아래 사유)**

cycle: `ai/claude/feature-0003-product-picker-keynav` · 정본 = TASK `20260729T1742-product-picker-keynav` ·
FUNCTION `REQ-20260729T174200-product-picker-keynav`(AC-PPKN-1~4) · REVIEW `REV-20260729T174200-product-picker-keynav` ·
MODIFY `CHG-20260729T174200-product-picker-keynav`.

- **변경**: `src/static/app.js` — `productDropupNavItems`/`focusProductDropupItem`/`moveProductDropupFocus`
  신설, 검색칸 `keydown`(ArrowDown, IME 가드), 항목 `keydown` 확장(↑/↓), `closeProductDropup` 이 문서
  리스너 해제 단일 지점(`_productDropupDetach`). `src/static/styles.css` —
  `.product-dropup-item:focus-visible`. 백엔드·RBAC·스키마·엔드포인트 0.

- **PRE-COMMIT — `tests/headless/verify_product_dropup_keynav.py` 27/27 PASS** (chromium headless).
  하네스가 항목 DOM 을 흉내내지 않고 **실 `renderProductDropupMenu`/`openProductDropup`/
  `closeProductDropup` 원문 + 실 `styles.css`** 를 그대로 돌린다(외부 의존만 스텁) — 포커스 추종·
  sticky 가림·재렌더 후 배선은 레이아웃/실배선 산출물이라 DOM 없는 단위검증으로 대체 불가:
  1. `T0` 추출 무결성(모든 실 함수 정의) · `T17` 페이지 에러 0 — 추출이 어긋나면 침묵 통과 불가
  2. `T1`/`T1b` 검색칸 `↓` → 결과 첫 항목 포커스 + `preventDefault` · `T1c` 열림 시 검색칸 자동 포커스(무회귀)
  3. `T2` 필터(`p17`) 후 `↓` → 숨겨진 항목 건너뛰고 검색된 항목으로 진입
  4. `T3` `↓` 연속 → P1→P2→P3 순차 · `T4` 마지막에서 `↓` → 제자리(wrap 없음, 페이지 스크롤 억제)
  5. `T5` `↑` → 이전 항목 · `T6`/`T6b` 최상단 `↑` → 검색칸 복귀 + `scrollTop=0`
  6. `T7`/`T7b` 열람 전용(`is-view-only`) 행 순회 제외(총 5행 중 순회 대상 4)
  7. `T8`/`T8b` `Enter` → `setActiveProduct({mode:"pinned",pinnedId:12})` 1회 + 닫힘(`aria-expanded=false`)
  8. `T9` 30개 목록에서 15회 `↓` 후에도 포커스 항목이 메뉴 뷰포트 안(실 CSS `max-height:320px`)
  9. `T10` 위로 순회 시 sticky 검색칸(`.product-dropup-search-wrap`) 아래로 가려지지 않음
  10. `T11`/`T11b` 검색 결과 0건 → `↓` 미소비·검색칸 유지 + "검색 결과가 없습니다" 노출(무회귀)
  11. `T12`/`T12b` IME 조합 중(`isComposing` · 레거시 `keyCode 229`) `↓` 미개입
  12. `T13`/`T13b` 검색칸 없는 경로(제품 3개)에서도 `↓` 순회, 최상단 `↑` 는 제자리(포커스 소실 없음)
  13. `T14` **선택 후 문서 Escape 리스너 누수 없음**(codex P2-1 수정의 회귀 가드)
  14. `T15`/`T15b` `Escape` 닫기 + chip 포커스 복귀(기존 동작), 닫힌 뒤 `Escape` 무동작
  15. `T16` 열린 상태 재렌더 후에도 순회 배선 유지
  실행: `PLAYWRIGHT_BROWSERS_PATH=/home/claude-corp/.cache/ms-playwright python3 tests/headless/verify_product_dropup_keynav.py`
- **PRE-COMMIT — 기존 `tests/headless/verify_product_dropup_scroll.py` 11/11 PASS**(선택 항목 중앙
  스크롤 회귀 0).
- **PRE-COMMIT — `node --check src/static/app.js` PASS**(문법).
- **PRE-COMMIT — `make test` 컨테이너 전체 회귀**(pytest, 프론트 변경이라 영향면 0 확인용).
- **적대 검증 — codex 1회**: P1 0건, P2 3건 + P3 1건 전부 in-cycle 흡수(문서 리스너 누수 / 하네스가 실
  렌더 경로 미탑승 / IME 판정 취약 / 추출기 취약 → T0·T17 로 침묵 실패 차단). §18.8 `ux`·`design`
  subagent 는 세션 도구 제약으로 `[SKIPPED:tool-restricted:ux,design]`(REVIEW 근거 기록).

- **Environment: Windows-browser (PB-0008) — 배포 후 수행 사유**: 본 변경은 라이브 배포(web 재빌드 →
  갱신된 `app.js`/`styles.css` 서빙) 후에만 실 화면에 반영되므로 미배포 코드에서는 실측이 불가하다.
  헤드리스 검증은 실 CSS·실 함수 기반이나 **실 사용자 화면(Windows 브라우저)의 정본이 아니다**(§15.4.1).
  배포 후 검증 항목:
  1. 제품이 많은 계정으로 작업 화면 진입 → 제품 chip 클릭 → 검색칸에 제품 명칭 일부 입력 → `↓` 로
     결과 첫 항목 진입(파란 포커스 링 육안)(AC-PPKN-1).
  2. `↓`/`↑` 로 결과 순회(숨겨진 항목 건너뜀) → 최상단에서 `↑` → 검색칸 복귀(AC-PPKN-2).
  3. `Enter` → 해당 제품 선택 + 드롭업 닫힘 + chip 라벨 갱신(AC-PPKN-3).
  4. 선택 후 `Escape` 를 눌러도 포커스가 chip 으로 튀지 않음(리스너 누수 수정 실측).
  5. 마우스 클릭 선택·검색 필터·중앙 스크롤 무회귀(AC-PPKN-4).
