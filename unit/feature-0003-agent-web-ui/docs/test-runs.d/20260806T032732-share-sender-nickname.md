---
run_at: 2026-08-06T12:27:32+09:00
session: ai/claude/share-sender-nickname
scope: share-sender-nickname (공유 링크 화면 발화자 배지 → 메시지별 발신자 닉네임)
verdict: PASS (pre-deploy) · Windows-browser 는 POST-DEPLOY
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

### 미수행 — 실 Windows 브라우저 시각검증 (POST-DEPLOY 로 이월)

- 사유: 정적 자산(`share.js`/`share.css`)이 web 이미지에 baked 되는 배포 구조라, 미머지
  브랜치 상태로는 라이브 `/share/{token}` 이 새 자산을 서빙하지 않는다. 라이브 컨테이너에
  자산을 주입하는 사전 QA 는 다른 세션의 라이브 화면을 오염시키므로 채택하지 않는다
  (선행 선례: `20260805T192000-verdict-badge-postdeploy`).
- 계획(배포 직후 수행, PB-0008 · `bin/win-browser.py` 실 Windows Chrome):
  1. 그룹 발신 각인이 있는 공유 링크에서 **참여자별 닉네임**이 배지에 뜨는지(같은 화면에
     서로 다른 이름이 갈리는지) — 본 요청의 직접 확인.
  2. 각인 없는 메시지(1:1·초기 메시지)가 **대화 소유자명**으로 뜨는지.
  3. 우측 rail dot 툴팁이 말풍선 배지와 **같은 이름**인지(표기 단일 출처).
  4. 긴 사용자명에서 배지가 ellipsis 로 잘리고 **meta 줄(시각·범위 표기)이 밀리지 않는지**
     — 확대 렌더로 대조(§16.7 G9-a 시각 불변식).
  5. assistant 배지가 `어시스턴트` 로 무회귀인지 · 콘솔 에러 0.
