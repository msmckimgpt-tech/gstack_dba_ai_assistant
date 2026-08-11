---
run_at: 2026-08-11T18:45:00+09:00
session: ai/claude-corp/attach-diff-bubble-chip
scope: assistant 답변 말풍선의 수정본 첨부 칩에서 그 수정 내용(diff 패널)으로 바로 들어가는 버튼
verdict: PASS
---

# Run — attach-diff-bubble-chip

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_bubble_diff_entry.mjs` **47 PASS / 0 FAIL**
  (A 어포던스 노출 조건·시맨틱·순서 · B 칩 다운로드와의 이벤트 격리 · C 체인 해석·preselect
  6경로 · D 구조 계약·CSS) — `_buildMessageAttachChip` 을 jsdom 위에서 **실제 실행**하고
  클릭이 무엇을 호출하는지 관측한다. 정적 문자열 검사는 "버튼을 만든다" 까지만 말하고
  배선(다운로드 억제·preselect 계산·폴백)은 말하지 못한다.
- **뮤테이션 12/12 red** — 각 항목이 실제 결함을 겨냥한다:
  - M1 `verNum > 1` 조건 제거 → v1(신규 생성) 칩에 비교 버튼 = 누를 때마다 실패하는 거짓 어포던스 (A1 red)
  - M2 `stopPropagation` 제거 → 비교를 누르는데 파일이 함께 내려간다 (B1 red, `downloads=1`)
  - M3 preselect 를 `thisVer - 1` 하드코딩 → 중간 버전이 삭제된 체인에서 없는 번호 지정 (C3 red)
  - M4 `from == to` 가드 제거 → 서버가 400 으로 막는 쌍을 preselect (C5 red)
  - M5 원문 폴백 제거 → 구버전이 전부 삭제된 체인에서 눌러도 아무 일 없음 (C6·C6b·C6d·D2b red)
  - M6 실패 토스트 제거 → 조회 실패가 무음 (C7 red)
  - M7 중복 클릭 가드 제거 → (아래 M10 과 같은 축) (C8 red)
  - M8 CSS `flex-shrink: 0` 제거 → 좁은 폭에서 버튼·배지가 먼저 소멸 (D4 red)
  - M9 **403 중복 토스트 가드 제거** → 같은 사유가 두 번 뜨고 두 번째가 첫 번째 표시 시간을 리셋 (C7c red)
  - M10 **재진입 가드 제거(`disabled` 만)** → dispatch 3회에 왕복 3회·모달 3개 (C8b·C8d red)
  - M11 hover 색을 하드코딩 `rgba` 로 되돌림 → 색 토큰 규칙 위반 (D7·D7b red)
  - M12 hover 테두리 신호 제거 → 흰 칩에서 hover 가 사실상 안 보임 (D7c·D7d red)

### 이 라운드에 하네스가 잡은 실제 결함 (역방향 발견)

C8(중복 클릭)의 **첫 판이 vacuous** 였다 — 느린 왕복을 흉내내는 promise 를 만들어 두고
`apiFetch` stub 에 연결하지 않았고, 클릭도 한 번만 보냈다. codex 적대 리뷰가 이를 지목해
게이트를 stub 에 실제로 연결하고 3회 클릭으로 고치자 **구현이 red 로 뒤집혔다**: `disabled`
속성은 trusted 클릭만 막고 프로그램 dispatch 는 리스너를 그대로 실행한다. 그래서 상태
플래그(`dataset.diffBusy`) 재진입 가드를 추가했다. 테스트가 통과하도록 테스트를 고친 것이
아니라, 고친 테스트가 구현의 구멍을 드러낸 사례다.

## Environment: 기존 하네스 회귀 (node18)

- `tests/verify_*.mjs` **전수 50 suite · 체크 1,684건 · 0 FAIL** (변경 전 1,679 → 신규 47 반영 후
  1,684 — 기존 하네스 감소 0).
- `tests/headless/verify_attach_diff_geometry.py` **55 PASS / 0 FAIL** (실브라우저 픽셀 게이트,
  페이지 JS 오류 0) · `tests/headless/verify_attach_version_row_actions.py` **10 조합 PASS**.
- pytest: 백엔드·라우터·권한·스키마 변경 **0**(신규 엔드포인트 없음, 기존
  `GET /api/attachments/{id}/versions`·`/diff`·`/source` 재사용)이므로 본 cycle 의 판정면 밖.

## Environment: Windows-browser (PB-0008)

**PASS** — 실 Windows Chrome/150 (relay @ 172.26.144.1:9223). **bind-mount 프리뷰
컨테이너(`:18099`, 라이브 이미지 `mysql-ai-web:8e88a60e` + worktree `src` 마운트)에서 수행 —
라이브 스택(web-a/web-b/caddy) 무접촉, 라이브 데이터 변경 0**(호출은 전부 읽기 전용
`GET /versions`).

| 축 | 실측 | 판정 |
|---|---|---|
| 칩 렌더 | assistant 말풍선 첨부 칩 4개 전부 `probe_*.sql · 7 KB · v2 · AI 수정 · ⇄ · ↓` | PASS |
| 요소 순서 | `attach-chip-name > size > ver > cmp > dl` (배지 바로 옆이 ⇄, 그 뒤 ↓) | PASS |
| 버튼 시맨틱 | `<button type="button">` · `title="v2 수정 내용 보기 (직전 버전과 비교)"` · `aria-label="probe_a.sql 버전 2 의 수정 내용 비교"` | PASS |
| 히트 영역 | **20 × 17px**(padding `2px 5px`) — 형제 액션(첨부 목록 행 ⬇·🗑 = 22×17)과 동급 | PASS |
| **실제 마우스 클릭 → diff 패널** | `버전 비교 — probe_a.sql` 모달 1개, 기준 `v1 · 사용자` ↔ 비교 `v2 · AI 수정`, 행 6, 통계 `+1 / -0`, 추가 줄(`-- reviewed: 2026-08-07`) 녹색 렌더 | PASS |
| preselect 정확도 | 체인이 **v1~v7** 인데 칩(v2)의 쌍 `1↔2` 를 정확히 선택 — 모달 기본값(직전↔최신 = `6↔7`)이면 이 답변과 무관한 쌍이 열린다 | PASS |
| 체인 전량 전달 | `기준` 셀렉트 옵션 `[1,2,3,4,5,6,7]` — 다른 쌍으로 갈아탈 수 있다 | PASS |
| 페이지 이동 없음 | 클릭 후 `location.pathname === "/"` · 모달 정확히 1개 | PASS |
| hover 렌더 | 배경 `rgb(239,246,255)` · 글자 `rgb(37,99,235)` · `inset 0 0 0 1px rgb(37,99,235)` — **확대 캡처(2.6×)로 비-hover 형제 3칩과 대조 판독**, 차이 명확 | PASS |
| hover 레이아웃 이동 | 폭 Δ0 · 높이 Δ0 · 옆 `↓` 좌표 Δ0 (inset 그림자라 밀림 없음) | PASS |
| 콘솔 | pageerror 0 | PASS |

증거: `docs/evidence/attach-diff-bubble-chip/{01-bubble-chip-with-cmp-button,02-diff-modal-from-bubble-chip,03-chip-cmp-button-zoom-hover}.png`.

**대비 실측이 설계를 바꾼 지점**: hover 를 `--primary-soft` 배경만으로 두면 assistant 칩
배경(`--surface` = 흰색)과의 대비가 **1.09** 여서(실브라우저 토큰 실측) 배경 변화가 사실상
보이지 않는다. 글자색 대비는 4.75(AA 통과)로 확보되지만 그것만으로는 "이 버튼이 반응한다" 는
신호가 약해, 형제 `.message-action-btn:hover` 가 border-color 를 바꾸는 것과 같은 취지로
`inset` 테두리를 더했다. 배경 대비 수치를 재지 않았으면 토큰만 쓰고 통과시켰을 것이다.

## 한계 · 잔여 (정직 표기)

- **trusted hover 는 이 도구에 없다** — `:hover` 발동은 CDP `Input.dispatchMouseEvent(mouseMoved)`
  가 필요하고 `bin/win-browser.py` 에 해당 서브커맨드가 없다. 그래서 hover **선언과 동일한
  규칙을 주입**해 렌더 결과를 캡처·판독했다(선택자 발동만 우회, 렌더는 실제). 마우스를 올렸을
  때의 전이 애니메이션(`.12s`)은 미관측.
- 칩 본체 클릭 → 다운로드가 유지되는지는 jsdom(B2)에서 검증했다. 실브라우저에서는 파일 저장이
  OS 다운로드 경로로 나가 자동 판독이 닿지 않아 미실측(같은 계약을 `stopPropagation`
  뮤테이션 M2 가 잠근다).
- 히트 영역 20×17px 은 WCAG 24×24 미만이다. 저장소 칩·행 액션 전반이 공유하는 **선재
  트레이드오프**(칩 높이 26px 안에 24px 버튼을 넣으면 말풍선 안 칩이 본문보다 커진다)이며
  이 cycle 에서 축을 바꾸지 않았다 — 원장 등재.
- POST-DEPLOY 라이브 재확인(배포본 baked 자산)은 배포 후 Run append.
