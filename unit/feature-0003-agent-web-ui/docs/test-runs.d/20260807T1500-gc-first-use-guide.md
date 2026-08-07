---
run_at: 2026-08-07T15:45:00+09:00
session: ai/claude/feature-0009-join-guide
scope: unit/feature-0003-agent-web-ui/src/static (index.html · app/composer.js · css/chat.css)
verdict: PASS (유닛/계약) / PARTIAL→PASS (Windows-browser — 실측이 결함 1건 적발, 후속 cycle 로 수정)
---

### Run (2026-08-07) — 그룹 대화 기능 첫 사용 1회 안내 툴팁 (gc-first-use-guide)

#### 1. 노출·소진 계약 — **Environment: node (실 함수 본문 + 가짜 DOM/localStorage)**

`tests/verify_gc_first_use_guide.mjs` — 문자열 grep 이 아니라 `app/composer.js` 의 실제 함수
본문을 추출해 클로저에 묶어 구동한다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | 그룹 대화 첫 진입 시 노출 (AC-1) | PASS |
| 2 | 1:1 대화 비노출 + 소진 없음 (AC-4) | PASS |
| 3 | **두 번째 그룹 대화에서 미재노출** (AC-2 — 요구의 핵심) | PASS |
| 4 | 새로고침(새 로드) 후 미재노출 + 저장 형식 = username 배열 (AC-3) | PASS |
| 5 | 다른 계정은 자기 몫의 안내를 받음 | PASS |
| 6 | 계정 미상(세션 전) 노출 보류 · 익명 키 소진 금지 · 세션 확정 후 노출 | PASS |
| 7 | **닫기 ≠ 소진** — 입력/Esc 는 이 로드만, 다음 방문에 재노출 (ux B1) | PASS (4건) |
| 8 | Esc 는 멘션 AC·드롭업 5종이 열려 있으면 양보 (ux M2) | PASS (5건) |
| 9 | 발화 불가(`conversation.ask` 없음 / `blocked`)면 표시·소진 없음 (ux B2) | PASS (5건) |
| 10 | 재렌더가 리스너를 쌓지 않음(요소당 1개) | PASS (2건) |
| 11 | 마크업·문구 — 5줄 · 각 ≤30자 · 일반대화/@assistant 포함 · `aria-live` · 라벨 (AC-5, AC-6) | PASS (11건) |
| 12 | 스타일 — wrap 밖 앵커 · z(40) < 멘션 AC(50) · 컨테이너 기준 max-width · 다크 override 부재 · anim-pref · 터치 타깃 | PASS (10건) |

**61 passed, 0 failed.**

#### 2. 뮤테이션 역검증 — 단언이 형식적이지 않음을 실증

| # | 주입한 결함 | 결과 |
|---|---|---|
| M1 | 입력 dismiss 를 영구 소진으로 되돌림 | **KILLED** (2 red) |
| M2 | `speakable` 발화 게이트 제거 | **KILLED** (2 red) |
| M3 | Esc 의 오버레이 양보 제거 | **KILLED** (5 red) |
| M4 | `z-index: 40 → 60`(멘션 AC 위로) | **KILLED** (1 red) |
| M5 | caret 앵커를 `calc(100% - 4px)`(wrap 안)으로 되돌림 | **KILLED** (2 red) |

**5/5 KILLED**, 복원 후 baseline 61/61 재확인.

#### 3. 정적 검사

- `node --check`(ESM 사본) `app/composer.js` — PASS
- `css/chat.css` brace 균형 624 = 624 — PASS
- 대비 계산(흰 배경 기준): 본문 `#4a4841` **9.15:1** · 제목 `#26251e` **15.38:1** ·
  닫기 `#2563eb` **5.17:1** — 전부 WCAG AA(4.5) 통과. (채택하려던 `--text-muted` `#807d72`
  는 **4.12:1** 로 미달이라 전용 토큰으로 교체했다.)

#### 4. **Environment: Windows-browser (PB-0008) — DEFERRED(배포 후)**

정적 자산(index.html·app/composer.js·css/chat.css)이 web 이미지에 baked 되므로 배포 후에
실 Windows Chrome via `bin/win-browser.py` relay + 로그인 세션에서 실측하고 본 fragment 에
Run 을 append 한다. 이 환경에는 브라우저 바이너리가 없어 렌더 판독을 대체할 수단이 없다
(`visual_verification_scope: always`).

실측할 축(브라우저가 정본인 것만):
1. 그룹 대화 첫 진입 → 컴포저 위 카드 노출 + caret 이 입력창을 가리킴(배너 잠식 없음).
2. **각 안내가 실제로 한 줄로 렌더**되는지(문자열 길이 단언이 못 보는 축 — design MINOR).
3. `@` 입력 시 멘션 자동완성이 카드보다 **위**에 뜨는지(z 40 < 50 실화면 확인).
4. "다시 안 보기" → 다른 그룹 대화 전환 → 미재노출 / 새로고침 후에도 미재노출.
5. 입력만 하고 새로고침 → **다시 뜸**(닫기≠소진 분리의 라이브 확인).
6. 1:1 대화 무노출 회귀 없음.

de-risk 근거: 위 1~3 절(계약 61 PASS · 뮤테이션 5/5 · 대비 계산)로 코드 정합과 색 대비는
확증했고, 남은 것은 실 렌더 기하·스택 순서다.


---

### Run (2026-08-07) — **Environment: Windows-browser (PB-0008)** · 배포본 `f81c5bcb`

실 Windows Chrome/150 via `bin/win-browser.py` relay @ `172.26.144.1:9223`,
`https://localhost/` 로그인 세션 `bootstrap_admin`, 뷰포트 2386×1255 (DPR 1).
대상 그룹 대화 `20260806052006-3f48cbb7`(멤버 2) · 대조 1:1 `20260807035225-9cb592cb`.
서빙 자산 스탬프 `?v=c2838fc68348` 확인.

| # | 축 | 결과 |
|---|---|---|
| 1 | 그룹 대화 첫 진입 → 카드 노출 · 컴포저 위 배치 | **PASS** `hidden=false` · rect `(272,1014) 210×151` · 카드 bottom 1165 / `.composer-wrap` top 1168 → **카드 전체가 wrap 밖**, caret 만 상단 padding(8px) 안으로 3px |
| 2 | **각 안내가 실제로 한 줄로 렌더** (문자열 단언이 못 보는 축) | **PASS** 5항목 전부 `height 17px = lineHeight×1` |
| 3 | `@` 입력 시 멘션 자동완성이 카드보다 **위** | **PASS** 두 박스 overlap 상태에서 `elementFromPoint` = `mentionAutocomplete` (tip z=40 < ac z=50) |
| 4 | "다시 안 보기" → 다른 그룹 대화 2곳 · 새로고침 미재노출 | **PASS** `localStorage=["bootstrap_admin"]`, `a6fe00cf`·`b5f40d99` 모두 `tipShown=false` |
| 5 | 입력만 하고 새로고침 → **다시 뜸**(닫기≠소진 분리) | **PASS** `@` 입력 시 즉시 숨김 + `localStorage=null` 유지 → 재진입 시 `tipShown=true` |
| 6 | 1:1 대화 무노출 + **무소진** | **PASS** 클린 상태로 1:1 방문 후에도 `localStorage=null`, 이어 그룹 진입 시 정상 노출 |
| 7 | Esc → 숨김, 소진 없음 | **PASS** `tipHidden=true`, `localStorage=null` |
| 8 | **Esc 양보 — 멘션 AC 열림 중** | **FAIL → 후속 cycle 에서 수정** (아래) |

증적: `scratchpad/gcguide-01-shown.png`(전체) · `gcguide-01-crop.png`(확대 판독 — 카드·caret·
5줄·"다시 안 보기" 대비).

#### 실측이 적발한 결함 (#8) — 유닛 하네스가 통과시킨 것

멘션 자동완성이 열린 상태에서 Esc 를 누르면 안내까지 함께 닫혔다
(`tipVisibleBefore=true → tipVisibleAfter=false`). 원인은 **핸들러 실행 순서**다 — 우리
Esc 핸들러가 버블 단계라, 먼저 등록된 멘션 AC 의 핸들러가 AC 를 이미 닫은 **뒤에** 돌아
`_gcGuideOtherOverlayOpen()` 이 "열려 있지 않다" 로 오판했다.

**왜 61 PASS 가 이걸 놓쳤나**: 가짜 DOM 에 경쟁 핸들러가 없어, "양보한다" 는 단언이
*우리 함수만 존재하는 세계* 에서만 참인 **vacuous pass** 였다. 단언 자체가 형식적이지
않았음에도(뮤테이션 5/5 KILLED) **합성(composition)을 재현하지 않은 것**이 사각이었다.

**수정(후속 cycle `20260807T1700-gc-guide-esc-capture`)**: 핸들러를 **capture 단계**로 등록
(저장소 선례 `_attachShareRangeEsc` 와 동일 이유). 하네스는 가짜 document 를 capture→bubble
2단계로 바꾸고 경쟁 오버레이 핸들러를 주입해 **라이브 조건**에서 검증하도록 고쳤다.

**피해 범위(정직)**: 이 결함으로도 안내가 **영구 소진되지는 않는다**(`localStorage=null`
실측 확인) — 앞선 ux BLOCKING #1 수정이 그 경로를 이미 끊어 두었다. 잔여 영향은 "그 로드에서
안내가 함께 사라짐" 이었다.
