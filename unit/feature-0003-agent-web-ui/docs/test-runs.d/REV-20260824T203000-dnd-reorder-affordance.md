---
run_at: 2026-08-24T20:50:00+09:00
session: ai/claude-corp/feature-0003-dnd-reorder-affordance
scope: 드래그&드롭 이동에도 재배치 연출 적용 — CHG-20260824T203000-dnd-reorder-affordance
verdict: PASS (Environment: Windows-browser)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

- 대상: 라이브 web 이미지 + 본 worktree `src/static` bind-mount 컨테이너
  (`web-verify-dnd`, `https://localhost:18097`). 서빙본에 예약 배선 확인은 `docker exec grep`
  으로 **컨테이너 안 파일**을 직접 봤다(호스트 파일만 보면 옛 inode 를 서빙하는 경우를 놓친다).
- 계측: `scratchpad/measure_dnd.py` — rAF 궤적 + 도착 표식.

## 합성 드래그를 쓴 이유

HTML5 DnD 는 네이티브 드래그 세션이라 Playwright `drag_to` 로는 신뢰성이 낮다. 앱이 실제로
구독하는 이벤트(`dragstart` → `dragover` → `drop` → `dragend`)를 **하나의 `DataTransfer`** 로
연결해 합성했다. 앱은 `dragstart` 에서 `state.dqaDrag` 를 채우고 `drop` 에서 그것을 읽으므로,
합성이어도 실제와 같은 경로를 탄다(모듈 상태를 우회하지 않는다).

## 결과 (PASS)

| 항목 | 값 |
|---|---|
| 조작 | 최상위 날짜 그룹의 대화 1건을 임시 폴더로 **드래그&드롭** |
| 이동 | 화면 y **175 → 145**, 도착 그룹 `🗂zz-dnd-임시` |
| 트윈(1차) | 7 프레임(59~158ms = **99ms**) — 계약(30px → 166ms)보다 **짧다**. 이것이 아래 [P1] 의 증거였다 |
| 트윈(리뷰 반영 후) | **8 프레임**(197~328ms = **131ms**) — 잔여 구간은 offset < 1px 이라 계측 해상도 밖 |
| 궤적 | offset +30 → +22 → +15 → +10 → +6 → +4 → +2 (감속, 오버슈트 0) |
| 도착 표식 | **rail + "이동됨" 배지 부여**, 관측 창(2.5초) 내내 유지 |
| 원복 | root 드롭 존(`#newFolderBtn`)으로 다시 빼서 '오늘' 그룹 복귀 |
| 정리 | 임시 폴더 `DELETE` 200 |

## 함께 확인한 것

- 드래그 경로도 이름 변경과 **같은 코디네이터**를 탄다 — 별도 연출 코드가 없다(두 이동 함수에
  예약만 걸었다). 따라서 곡선·길이·표식 수명이 갈라질 여지가 구조적으로 없다.
- 트윈 중 `pointer-events: none` 은 **이동이 끝난 행**에 걸리므로 드롭 자체를 막지 않는다
  (드롭은 이미 처리된 뒤 재배치가 시작된다).

## 미수행

라이브 서빙본 재확인은 배포 후 POST-DEPLOY 로 수행한다.

## 리뷰 반영 후 재실측 + 이 Run 이 놓쳤던 것 (정직 기록)

§18.8 codex 리뷰가 [P1] 3건을 냈고, 그 중 하나는 **이 Run 의 데이터가 이미 증거였다**:
1차 실측의 트윈이 99ms 로 계약(166ms)의 60% 에서 잘렸는데, 나는 "7프레임 트윈 관측" 으로 PASS
판정했다. 원인은 대화 이동의 낙관적 즉시 렌더가 트윈을 시작해놓고 이어지는 `loadConversations`
렌더가 트윈 중인 DOM 을 전량 교체한 것이다. **계약 값과 실측을 대조하지 않고 "움직였다" 로
판정한 것이 이 Run 의 결함**이다.

- 수정(즉시 렌더 제거 → 서버 반영 렌더 한 번) 후 재실측: **197~328ms(131ms), 8 프레임**,
  offset +30 → +1 감속. 도착 표식(rail·배지)은 동일하게 부여·유지.
- 함께 봉인: 주기 unread 동기화가 (a) 대기 중 예약을 가로채 이동 전 상태에서 소비하던 경로와
  (b) 드래그 중 전량 재렌더로 drop 을 씹던 경로 → 진입 가드 2개(`sidebarReorderFocus`·`dqaDrag`).
- 제자리 드롭(같은 폴더로 다시 놓기)은 PATCH·예약 모두 생략 — "이동됨" 표식이 거짓말하지 않는다.
