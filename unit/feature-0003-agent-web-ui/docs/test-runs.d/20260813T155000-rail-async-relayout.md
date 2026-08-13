---
run_at: 2026-08-13T15:50:00+09:00
session: ai/claude-corp/feature-0003-rail-async-relayout
scope: rail-async-relayout (REQ-20260813T155000-rail-async-relayout)
verdict: PASS
---

# Run 1 — 실브라우저 기하 실측 + 수정 전 재현 (headless chromium)

- **Environment: CLI(headless chromium)** — `tests/headless/verify_point_rail_async_relayout.py`.
  레이아웃 기하 + 비동기 타이밍 축이라 jsdom·정적 스캔이 원리적으로 못 보는 영역이며,
  실 `app.js` 유닛을 정규식 추출(사본 아님) + 실 `css/{base,chat,profile}.css` 를 올려 측정한다.
  화면 정본은 아래 Run 2(Windows-browser).
- **`--baseline` (신설 배선 미주입 = 수정 전) — 결함 재현 FAIL 4**:
  - `T2` mermaid 렌더 후 뱃지 재정합 — **최대 178.2px 오차**(id 4: d_top 171.4 / d_height 178.2,
    id 2: d_top 42.5 / d_height 88.4). 사용자가 본 "우측 스크롤과 뱃지 영역 불일치" 의 수치.
  - `T4` 맨-아래 유지 — `scrollTop=146` vs `maxScrollTop=653` → 최신 답변이 **507px** 밀림.
  - `T5b` 조작 후 재정합 — 178.2px(pin 과 독립된 배치 축도 깨져 있었음).
  - `T7` 이미지 지연 로드 후 재정합 — **97.96px**(mermaid 외 같은 클래스의 두 번째 지연원).
  - `T1`(동기 상태) · `T3`(thumb 판정) · `T5`(조작 존중) 는 baseline 에서도 PASS = 이 변경이
    기존 정상 동작을 건드리지 않았음의 대조.
  - `T8` 재현 판정 **OK** — 배선 제거 시 T2 붕괴 확인(§16.7 G4 경계 양측 · load-bearing 증거).
- **현행 — 26/26 PASS**: T1 · T2a(성장 발생 자체 단정) · T2 · T3 · T4 · T5 · T5b · T7a · T7 ·
  T9a/T9(교체되는 pending 말풍선) · T10(스크롤바 pointerdown) · T11a/T11/T11b(**뷰포트 위쪽 성장**) +
  정적 배선 계약 W1(engage) · W2(observe) · T6(점프 시 release) · W3(prepend) · W4(live-sync) ·
  W5(pointerdown) · W5b(폐기 판별 재발 방지) · W6(pending 포함) · W7(childList 감시) ·
  W8(폴백 settle 창) · H0.  ← T9~T11·W4~W8 은 codex 지적과 라이브 회귀를 잠근 축이다.
- 하네스 자기 검증: 초판이 row 높이를 `min-height` 로 만들어 flex-shrink 가 아이템을 눌러
  **라이브와 거동이 갈렸다**(이미지 성장이 12px 로만 관측됨). 실 콘텐츠(spacer) 기반으로 교체해
  min-content 하한 = 라이브 동형으로 정정하고, "성장이 실제로 일어났는가" 를 T2a/T7a 로 먼저
  단정해 vacuous PASS 를 차단했다.
- 회귀: 기존 프론트 검증 `tests/verify_*.mjs` **57/57 PASS** ·
  feature-0003 pytest 전건 PASS(격리 env `DB_PORT=1` 등, rc=0).

# Run 2 — 실 Windows 브라우저 라이브 실측 + 수정 전 자산 대조 (PB-0008)

- **Environment: Windows-browser** — 실 Chrome/150.0.7871.128, `bin/win-browser.py` CDP 자동
  구동(bridge `relay @ http://172.26.144.1:9223`). §13.2.9 격리 프리뷰 2개(공유 트리 무수정):
  - `web-rail-relayout-preview`(:18097) — **worktree src 마운트 = 수정 후**
  - `web-rail-baseline-preview`(:18096) — **main(`repo/`) src 마운트 = 수정 전 대조군**
  두 컨테이너 모두 라이브 web 이미지(`mysql-ai-web:5f20ee88`) + 라이브 env(`WEB_ALLOWED_HOSTS`
  만 프리뷰용 확장) → **자산만 다른 대조**.
- 신원 대조(§16.6 c): `:18097` 서빙 `app.js` 에 `_observeRailContentResize` **2건**,
  `:18096` 은 **0건** — 각각 자기 빌드임을 확인.
- 데이터: **사용자가 이슈를 보고한 그 대화** — `20260812082809-e4263afd`
  "스키마 개선 BEFORE/AFTER 다이어그램"(소유자 admin · 메시지 11 · mermaid 메시지 2건 ·
  라이브에서 실제 렌더된 `svg[id^=mmd-]` **3개** · 문서 높이 4,967~5,134px / 뷰포트 806~900px).
  PG 조회로 mermaid 포함 대화를 특정해 선택(추정 아님).

**수정 전 ↔ 수정 후 대조 (같은 대화·같은 브라우저·같은 데이터)**

| 축 | 수정 전(:18096) | 수정 후(:18097) |
|---|---|---|
| 뱃지 ↔ 메시지 구간 최대 오차 | **86.58px** | **0.11px** (자기 탭 재측정 0.20px) |
| 진입 시 맨-아래 gap | **1,631px**(최신 답변 화면 밖) | **0px** |
| dot 개별 예: id 2163 | dTop 40.41 (기대 13.50) · dH 45.59 (기대 15.23) | dTop 13.50 / dH 15.22 (기대와 일치) |

**라이브가 자기 회귀를 잡았다 (기록)** — codex [P2] 반영 초판은 "pin 이 설정한 `scrollTop` 과
불일치하면 사용자 조작" 으로 스크롤바 드래그를 판별했다. 그 코드로 같은 화면을 재측정하니
`A_entry gap=1,611px` — **수정 전과 같은 증상**이었다. 원인: 이 대화의 mermaid 는 **뷰포트 위쪽**
에서 자라고, 그때 브라우저 스크롤 앵커링이 `scrollTop` 을 자동 조정하는데 그 조정이 "불일치" 로
읽혀 pin 이 조기 해제됐다. 헤드리스 하네스는 성장이 뷰포트 **아래쪽**에서만 일어나 이 축을
건드리지 않아 26축 전건 통과 상태였다(§16.7 **G4** — 경계축은 "성장이 뷰포트 위인가 아래인가").
→ 판별을 **컨테이너 `pointerdown`** 으로 교체(의미론적으로 "사용자가 눌렀다")하고, 하네스에
**T11**(위쪽 성장 시 pin 유지) + **W5b**(폐기된 scroll-값-비교가 되살아나지 않았는지)를 추가해
클래스를 잠갔다. 교체 후 재측정 `A_entry gap=0` 복귀.

- thumb 정합(수정 후): 뷰포트에 보이는 메시지 2건의 막대가 thumb 구간 `[679.5, 806]` 과
  겹치고 보이지 않는 메시지는 겹치지 않음 — **불일치 0**.
- 상호작용(**확정 코드**, 자기 생성 탭에서 실측 — 위 회귀 교체 후 재실행분):
  - 진입 `gap=0` · worstPx **0.20** · JS 오류 **0**
  - 막대 60% 지점 클릭 → `scrollTop 4206 → 2629` 정밀 점프, pin 이 되돌리지 않음, 정합 유지
  - **실 휠 입력**(합성 이벤트 아님, `page.mouse.wheel`) → `2629 → 1729` 이동 후 유지(pin 개입 0), 정합 유지
  - `End` 키 입력은 위치를 바꾸지 않음 — `#messageLog` 가 키보드 스크롤 대상이 아닌 **앱 기존 동작**
    이며 본 변경과 무관(관측만 기록, 검증 축 아님).
- **§16.6 세션 격리 (MUST) — 위반 근접 사례 기록**: 검증 도중 공유 CDP 의 `pages[0]` 이
  **병렬 세션의 `https://localhost/admin` 탭으로 바뀐 것을 관측**했다(그 탭에 read-only `eval`
  1회 + `messageLog` 부재로 실패한 `scrollTop` 대입 1회가 도달 — 남의 화면을 바꾸지는 않았다).
  즉시 `context.new_page()` 로 **자기 전용 탭**을 만들어 이후 조작·캡처를 그 탭에서만 수행하고
  종료 시 그 탭만 닫았다. 위 상호작용 수치는 전부 자기 탭 측정값이다.
- 증거: `../evidence/pb0008-rail-async-relayout-{1-entry,2-before-after,3-midjump,4-wheel,5-baseline-full}.png`
  — 2번이 수정 전/후 rail+스크롤바를 가로 6배 확대해 나란히 붙인 판독용 캡처다(§16.6 픽셀-클래스
  변경은 element 상태로 대체 불가).
- 라이브 데이터 변경 0 — 열람·스크롤 경로만 사용(발화·편집·삭제 없음).
- 이월: **POST-DEPLOY**(main 머지 후 baked 자산) 재확인은 배포 직후 Run 3 으로 기록한다.
