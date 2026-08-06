---
run_at: 2026-08-06T12:27:32+09:00
session: ai/claude/share-sender-nickname
scope: share-sender-nickname (공유 링크 화면 발화자 배지 → 메시지별 발신자 닉네임)
verdict: PASS (pre-deploy + POST-DEPLOY Windows-browser 7항목)
---

### Run (2026-08-06) — 발신자 라벨 분기 동작 — **Environment: CLI**

- 방법: `node unit/feature-0003-agent-web-ui/tests/verify_share_sender_nickname.mjs`.
  배포되는 `static/share.js` 소스에서 `roleLabel`/`senderLabel` 함수 본문을 추출해 그대로
  평가한다(로직을 테스트에 재구현하지 않음 — tautology 회피). 클로저 변수
  `_shareOwnerUsername` 만 주입.
- 확인(17 케이스): ① `sender_username` 각인 → 닉네임 그대로 · 참여자별로 라벨이 갈림
  ② id 만 각인 → `사용자 <id>`(소유자명 오귀속 금지) · 공백뿐인 username 은 미각인 취급
  ③ **1:1** + meta 없음/빈 객체 → 소유자명 폴백 / **그룹** 또는 is_group 미상 → 익명 토큰
  ④ 소유자명 부재 → 종전 `사용자` ⑤ assistant → `어시스턴트` 유지 · 알 수 없는 role ·
  `null` 입력에도 예외 없음 ⑥ 마크업 유사 사용자명 원문 보존(escape 는 렌더 층 `textContent`
  책임) ⑦ **추론 각인(`attribution_inferred: true`)은 이름·id 둘 다 미사용** — 그룹이면 익명
  토큰, 1:1 이면 소유자명, 플래그가 false/부재면 정상 각인 취급.
- 결과: **17 passed / 0 failed** (rc=0). (§18.8 적대 패널 반영 전 11 → ③ 분기 2 + ⑦ 4 추가.)

### Run (2026-08-06) — 배선·계약 회귀 가드 — **Environment: CLI**

- 방법: 컨테이너 pytest — `unit/feature-0003-agent-web-ui/tests/test_share_sender_nickname.py`.
- 확인: 배지가 `senderLabel(msg)` 로 채워지고 `roleLabel(msg.role)` 고정이 제거됐는지 ·
  폴백 배선 3단 + **추론 각인 배제(`attribution_inferred`)** + **is_group 게이트** ·
  `badge.innerHTML` 부재 · `title` 이 **조건부**(`_deferOverflowTitle`, `scrollWidth/clientWidth`)
  이고 무조건 대입이 없는지 · rail `who` 가 동일 라벨 · `render()` 의 `_shareOwnerUsername` 갱신 +
  `_shareIsGroup = conv.is_group !== false`(fail-closed) · `.share-role-badge` 의
  max-width/ellipsis/nowrap **와** `.share-message-time` 의 `flex:0 0 auto`/`nowrap` ·
  `_share_load_messages` 가 응답에 `meta` 를 싣는 계약(백엔드가 strip 하면 표시가 붕괴) ·
  `public_share_view` 의 `is_group` payload 배선 · `_share_conversation_is_group` fail-closed.
- 결과: **2 passed**.

### Run (2026-08-06) — 전체 스위트 회귀 — **Environment: CLI**

- 방법: `make test` (전용 compose 프로젝트, 라이브 네트워크 미참여).
- 1회차: `test_shutdown_finalizer.py::test_shutdown_finalizer_marks_this_process_processing`
  1건 FAIL. 로그가 `shutdown finalize: 시간 예산 초과 — 나머지는 부팅 reconciliation 이 처리`
  를 남겨 **시간 예산 기반 flake**(병렬 부하)로 판정 → 격리 재실행 **통과**(5 passed) →
  **전체 재실행 exit=0**. 본 cycle 은 그 경로의 Python 코드를 접촉하지 않는다.
- 결과: **exit=0** (전체 스위트). ruff: All checks passed.

### Run (2026-08-06) — 익명 공유 payload 실측 — **Environment: CLI (라이브 read-only)**

- 방법: 활성 공유 링크 1건(`scope_mode=full`)을 Caddy 경유로 **인증 없이** 호출
  (`GET /api/public/share/{token}`) 후 `messages[].meta` 검사.
- 확인: 그룹 발신 메시지에 `{"group_chat":true,"sender_username":"admin","sender_account_id":10}`
  이 **본 변경 이전부터** 실려 나오고 있었다 — 즉 서버에 값이 없어서가 아니라 화면이 그 값을
  쓰지 않고 있었다는 진단의 1차 근거. 앞쪽 메시지 2건은 각인 없음(폴백 계층 필요성 실증).
  §18.8 security 패널이 코드로 재확증(배제 필터 3종 어디에도 sender 키 없음).
- 부작용: 해당 share row 의 `ViewCount` +1 (soft metric — 코드 주석이 이미 허용 오차로 명시).
- 결과: **PASS** (주장 "신규 백엔드 노출 없음" 확증).

### Run (2026-08-06, POST-DEPLOY) — 공유 링크 발화자 배지 실화면 — **Environment: Windows-browser**

- 방법: PB-0008 — `bin/win-browser.py run --scenario`(실 Windows Chrome 150, CDP relay),
  배포본 `ddbc6ebe`(web-a/web-b GIT_COMMIT 실측 일치), 서빙 자산 `share.js?v=24613708d61a`
  (§16.6 evidence identity — 자기 빌드 스탬프 대조). 익명(비로그인) 열람 경로로만 접근.
  base_url 은 `https://localhost`(Caddy 단일 노출 — `mysql-ai.company.local` 은 Windows 측
  미해석이라 REVIEW REV-20260805T104213 이 지적한 stale base_url 이슈와 동일 처리).

- **① 발신자 닉네임 표시 (요청의 직접 확인)** — PASS.
  각인 있는 메시지의 배지가 `admin` 으로 렌더(배경 `rgb(37,99,235)` primary pill).
  한 화면 내 라벨 집합 `["사용자","admin"]` — 각인 유무로 갈린다. 증적 `05_named_badge_live.png`.

- **② 사용자 제보 메시지 실물 대조 (§16.7 G3)** — PASS.
  제보 스크린샷의 메시지를 DB 로 특정(`20260804013726-a6fe00cf` id=1965,
  `2026-08-06 01:33:19 UTC` = **10:33:19 KST**, sender_username=`admin` 각인 보유) 후 그 대화의
  공유 링크를 실브라우저로 열어 대조 — **종전 `사용자` → 현재 `admin`**.
  같은 대화 user 8건 중 **5건 닉네임 / 3건 `사용자`**(각인 없는 legacy). 증적 `06_reported_message_after.png`.

- **③ rail 툴팁 = 배지 라벨 (표기 단일 출처)** — PASS. dot 18개, 앞 6개 대조 `match: true`
  (`admin`↔`admin`, `사용자`↔`사용자`, `어시스턴트`↔`어시스턴트`).

- **④ 긴 사용자명 — 시각 불변식 (§16.7 G9-a · ux 패널 F-1)** — PASS.
  50자 계정명을 배지에 주입해 실측: 배지 `width=220px`(max-width 도달) + `scrollWidth>clientWidth`
  (ellipsis 절단 확인), **시각 표기 `width=126px` 불변 · 같은 줄 유지(`same_line: true`) ·
  meta 줄 높이 21px 불변**. 수정 전이라면 여기서 시각이 눌려 2줄로 접혔다. 증적 `03_long_name_ellipsis.png`.
  평상시 페이지 전체 `meta_heights: [21]` 단일값 · `time_widths: [126]` 단일값(카드 간 높이 요동 0).

- **⑤ title 조건부 (ux 패널 F-2)** — PASS. 절단이 없는 평상 상태에서 `truncated_count: 0`,
  `title_count: 0` — 화면 텍스트와 중복되는 툴팁이 붙지 않는다.

- **⑥ 각인 0 대화 — 소유자명 폴백 미발동 (security 패널 F-2 게이트)** — PASS.
  `owner=bootstrap_admin` 인 대화의 user 7건이 전부 `사용자`. `is_group=true` 라 소유자명을
  붙이지 않는다(오귀속 차단이 실제로 발동).

- **⑦ 무회귀** — assistant 배지 `어시스턴트` 유지 · **콘솔 에러 0**(`window.__errs` 훅, 전 페이지).

- 스크린샷: `artifacts/pb0008-share-sender-nickname/{01..06}*.png`.

### [실측 발견] 소유자명 폴백(3순위)은 라이브에서 사실상 발동하지 않는다 — 정직 기록

사용자 결정(2026-08-06)의 "각인 없는 과거 메시지 = 대화 소유자명" 은 `is_group=false` 일 때만
발동하는데, **공유 생성 자체가 `core_conversations.is_group` 을 true 로 set** 한다. 라이브 활성
공유 링크 6건을 실측한 결과 **전부 `is_group=true`**(멤버는 owner 1명뿐인데 플래그가 `t`).
따라서 각인 없는 메시지는 실질적으로 항상 `사용자` 로 표시된다.

- **안전 방향의 미발동**이다 — 오귀속 위험이 0 이고(§18.8 security F-2 가 지적한 그 위험),
  요청의 핵심(각인 있는 메시지의 닉네임 표시)은 그대로 충족된다.
- 다만 사용자 결정의 절반이 화면에 나타나지 않으므로 여기 남긴다. 더 정확한 판정 축은
  "공유 여부"가 아니라 **그 window 안에서 각인된 발신자 계정 수**(owner 1명뿐이면 소유자명이
  안전)다. 채택하려면 별 cycle 에서 사용자 확인 후 진행한다 — 본 cycle 범위 밖(scope 확장).
