---
run_at: 2026-09-01T11:53:00+09:00
session: ai/claude/sidebar-single-open
scope: 우측 오버레이 사이드 패널 단독 열림 + 접근성·상태복원 — PRE-DEPLOY 격리 실측(§18.8 3라운드 반영)
verdict: PASS
---

# Run — TASK-20260901T1153-side-panel-exclusive

- **Environment**: **Windows-browser** (PB-0008) — Windows Chrome/151.0.7922.170
- **Runner**: AI
- **Bridge**: `relay` @ `http://172.26.144.1:9233`
- **세션 격리(§16.6 a)**: 이 세션이 **직접 띄운** 전용 인스턴스만 조작했다 —
  `WIN_BROWSER_CDP_PORT=9232` · `WIN_BROWSER_RELAY_PORT=9233` ·
  `WIN_BROWSER_PROFILE=C:\Users\mckim\AppData\Local\win-browser-cdp-sidebar-r5` (`"reused": false`).
  최초에 기본 포트(9223)로 붙였을 때 **병렬 세션이 그 탭을 `https://localhost/` 로 가져가는
  것을 관측**해 즉시 전용 인스턴스로 분리했다(§16.6 a·b — 남의 탭 조작 금지).
- **대상**: 격리 검증 컨테이너 `web-verify-sidebar` (`https://localhost:18098`) —
  라이브 이미지 `mysql-ai-web:65641296` + **본 worktree 의 static 트리 read-only 마운트**.
  공유 checkout·라이브 web-a/web-b·`.env.secret`·`docker-compose.override` 무수정(§13.2.9).
- **Evidence**: `artifacts/pb0008-side-panel-exclusive/*.png`
- **Scenario**: `unit/feature-0003-agent-web-ui/src/scenario.side-panel-exclusive.json` (**16 step, 전부 ok**)

## evidence identity 대조 (§16.6 c)

```
performance.getEntriesByType('resource') →
  https://localhost:18098/static/app/side-panels.js?v=dev    (내 빌드의 신규 모듈)
```

패널을 여닫은 것은 페이지가 로드한 **그 모듈**과 정본 `app.js`/`profile.js`/`composer.js` 다.

## BEFORE — 결함 재현 (main `eebbf803` static 마운트, `https://localhost:18099`)

같은 브라우저·같은 계정·같은 대화에서 main 빌드로 동일 조작:

| 조작 | attachSidePanel | stepSidePanel | profileDrawer | profileBackdrop |
|---|---|---|---|---|
| 첨부 목록 열기 | **OPEN** | closed | closed | closed |
| 이어서 「단계 보기 (2)」 | **OPEN** | **OPEN** | closed | closed |
| 이어서 프로필 열기 | **OPEN** | **OPEN** | **OPEN** | **OPEN** |

캡처 `00_BEFORE_attach_and_step_both_open.png` — 화면에는 「실행 단계」만 보이지만 그 **뒤에
첨부 패널이 열린 채 남아** 있다(닫기 버튼·리사이즈 핸들 접근 불가).
`00b_BEFORE_all_three_open.png` — 셋 다 열린 상태.

## AFTER — 시나리오 실측 (내 빌드, `https://localhost:18098`)

> **§18.8 적대 패널 3라운드를 거친 최종본에 대한 측정**이다. 라운드 1·2 는 각각 BLOCK 이었고,
> 아래 표의 접근성(#0 a11y)·상태 복원(#5·#6) 축은 그 지적으로 **추가된** 것이다.

각 단계는 **실제 버튼 클릭 경로**다 (`#composerActionsBtn` → `#composerActionsListItem`,
`.bubble-steps-btn`, `#openProfileBtn`, `#profileBackdrop`). `hidden` 을 직접 만지지 않았다.

| # | 조작 | attach | step | profile | backdrop | 캡처 |
|---|---|---|---|---|---|---|
| 0 | 진입 baseline | closed | closed | closed | closed | — |
| 1 | 첨부 목록 열기 | **OPEN** | closed | closed | closed | `01_attach_only.png` |
| 2 | 「단계 보기 (2)」 | closed | **OPEN** | closed | closed | `02_step_only_attach_closed.png` |
| 3 | 프로필 열기 | closed | closed | **OPEN** | **OPEN** | `03_profile_only_step_closed.png` |
| 4 | 프로필 **닫기 버튼** → 첨부 다시 열기 | **OPEN** | closed | closed | closed | `04_attach_again_profile_closed.png` |

> ⚠ 라운드 2 지적 반영 — 종전에는 backdrop 을 **합성 click** 으로 눌러 「실 사용자 경로」라
> 라벨했다. 저장소 표준 primitive(`modal-dismiss.js`)는 `isTrusted` 로 합성 click 을 배제하므로
> 그 라벨은 성립하지 않는다. `#closeProfileBtn` 클릭으로 교체했다.

### 접근성 (라운드 2 지적 — U-3)

| 시점 | `#attachSidePanel` `aria-hidden` | `inert` |
|---|---|---|
| 진입 baseline(닫힘) | `"true"` | `true` |
| 첨부 열림 | `null` | `false` |
| 배타로 닫힘(단계 열기) | `"true"` | `true` |

이 패널들의 `.hidden` 은 슬라이드 아웃 전환 때문에 `display:flex !important` 를 유지하므로,
이 동기화가 없으면 «한 번에 하나» 계약이 **시각 사용자에게만** 성립한다.

### 상태 복원 (라운드 2 지적 — U-1 / 라운드 3 회귀 — B1)

| # | 측정 | 결과 |
|---|---|---|
| 5 | 휴지통 모드로 열어 둔 뒤 「단계 보기」로 **자동** 닫힘 → 재개방 | `trashBefore=true → trashAfterRestore=true` (복원됨) |
| 6 | 사용자가 **× 로** 닫은 뒤 재개방 | `userCloseResetsTrash=false` (종전대로 리셋 — 그 리셋은 의도) |
| 7 | 자동 닫힘 후 **대화 전환** → 재개방 | `trashAfterConversationSwitch=false` (**스냅샷 폐기** — 다른 대화가 휴지통 모드로 열리지 않는다) |

판정은 시나리오 `eval` step 이 직접 단정한다(사람 눈에 맡기지 않음) — 각 단계에서 «열려야 할
패널 1개 · 나머지 0개» 가 아니거나 위 값이 어긋나면 그 step 이 실패한다. **16/16 ok**.

## 환경 조건 해제 1건 (제품 결함 아님 — 명시)

이 격리 컨테이너에는 개인 AI 브리지 연결이 없어 composer 가 `is-bridge-locked` 로 잠겨
있고(`.composer-wrap.is-bridge-locked button { pointer-events }`), 첨부 메뉴 **진입점**이 클릭
불가였다. 검증 대상은 패널 배타 계약이므로 그 잠금 클래스만 제거한 뒤 **실제 메뉴 → 실제
핸들러** 경로를 그대로 탔고, 시나리오 마지막 step 이 잠금을 원복했다
(`bridgeLockRestored: true`). 패널의 `hidden` 을 직접 벗기거나 opener 를 우회하지 않았다.

## 검증 클래스 (§16.6)

- **픽셀-클래스**: AFTER 4장 모두 전체 뷰포트(1249×1229) 캡처 — 우측 패널 1개만 렌더된 그림이
  판독 가능한 크기로 담겼다. BEFORE 캡처가 대조군.
- **인터랙션 결과**: 정적 렌더가 아니라 **클릭 → 상태 전이**를 측정했다.
- **복수 surface**: 첨부 패널의 닫기 경로 3곳(패널 × 버튼 2 · 빈 목록 자동 닫기)을 한 함수로
  모았고, 열기 경로는 composer 메뉴 1곳뿐임을 구조 가드 S5·S7 이 고정한다.

## 잔류물 (§16.6 f)

- 페이지 DOM: 원복 확인 (`cleaned: true`, 열린 패널 0, `is-bridge-locked` 복원).
- 컨테이너: BEFORE 검증용 `web-verify-sidebar-before` **제거 완료**.
  AFTER 검증용 `web-verify-sidebar`(:18098)는 POST-DEPLOY 대조까지 유지 후 제거 예정.
- 브라우저 프로필: 전용 프로필 5개(`…-sidebar`, `-r2`~`-r5`)가 Windows `%LOCALAPPDATA%` 에
  남았다 — 아래 「PB-0008 함정」의 캐시 회피로 매 라운드 새 프로필을 썼기 때문. 자격증명과
  같은 민감도로 취급(공유·복사 금지).
- 데이터: 대화·첨부·계정 **미변경**(기존 대화 `20260831025448-12af0eb5` 를 읽기만 했다).
  마지막 step 의 「새 대화」 클릭은 클라이언트 상태 전환일 뿐 서버에 대화를 만들지 않는다
  (첫 전송 전까지 생성되지 않는다).

## 미검증 (정직 표기)

- **역방향 «프로필이 열린 상태에서 첨부 열기»** 는 실 클릭으로 도달 불가하다 — 프로필
  backdrop(z 195)이 화면 전체 클릭을 먹기 때문. 그 경로는 방어적 계약이며 jsdom 하네스
  C4(첨부 열기 → 드로어 + **backdrop** 동시 닫힘)가 잠근다. 브라우저 실측 아님.
- 본 Run 은 **PRE-DEPLOY 격리 실측**이다. 라이브(`https://localhost`) 배포본 대조는
  cycle-finalize + 재배포 후 POST-DEPLOY fragment 로 별도 기록한다(§16.3 deploy-backed 완료 기준).

## PB-0008 함정 (기록 — 다음 사람을 위해)

이 컨테이너의 정적 자산 응답에 **`Cache-Control` 헤더가 없다**(`last-modified`/`etag` 만).
그래서 브라우저가 휴리스틱 프레시니스로 ES module 을 캐시했고, 코드를 고친 뒤 시나리오를
다시 돌리자 **구 모듈이 실행돼 거짓 FAIL** 이 났다(`transferSize: 0` 으로 식별). `fetch` 로
받은 파일은 최신인데 페이지가 실행한 모듈은 구본이라, 소스만 보면 원인을 알 수 없다.
회피: `WIN_BROWSER_PROFILE` 을 새 경로로 바꿔 **빈 캐시 인스턴스**를 띄운다.

## §18.8 적대 패널 (3라운드)

라운드 1 `BLOCK ×2`(P1 6, 제품 결함) → 수정 → 라운드 2 `BLOCK ×2`(P1 2, 제품 회귀 1건) →
수정 → 라운드 3 `ux CONCERN` · `design BLOCK ×2`(**제품 동작 건전**, 지적은 가드·문서 정확성) →
수정 → **이 측정**. 사용자가 라운드 상한을 1회 연장했고, 마지막 3라운드 연속으로 두 리뷰어
모두 «제품 동작에 결함 없음» 으로 판정했다. 잔여 개선안은 `docs/REVIEW.md` 「후속 과제」.
지적과 처리는 `docs/REVIEW.md` 의 `REV-20260901T115300-side-panel-exclusive` 참조.
