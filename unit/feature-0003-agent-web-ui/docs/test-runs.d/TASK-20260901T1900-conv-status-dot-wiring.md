---
run_at: 2026-09-01T19:00:00+09:00
session: ai/claude/conv-status-dot-wiring
scope: "사이드바 대화 상태 dot 의 상태값→색 배선 복원 + 동종 배선 끊김 전수 판정"
verdict: PASS
---

# Run — TASK-20260901T1900-conv-status-dot-wiring

- **Environment**: **Windows-browser**(PB-0008, `bin/win-browser.py` relay → Chrome/151.0.7922.170)
  + 컨테이너 `make test` + node 실행 검증
- **대상 2종**:
  - **배포본(결함 재현)**: `https://localhost/` — 이미지 `mysql-ai-web:5a4d49fc`, repo-web-a/b healthy
  - **수정본(변경 검증)**: `https://localhost:18098/` — 같은 이미지에 **본 worktree 의
    `src/static` 을 read-only bind-mount** 한 별도 컨테이너 `web-verify-convdot`
    (라이브 web-a/web-b 무접촉. 검증 후 제거)
- **도달 확인**: 검증 컨테이너가 실제로 수정본을 서빙하는지 먼저 확인했다 —
  `/static/app/conv-status.js` 응답 본문 존재 + `/static/css/shell.css` 에 `is-done` 규칙 1건.
  ("배포했다"와 "도달했다"는 다른 사실이다.)

## 1. 제보 재현 — 배포본에서 상태가 화면에 도달하지 않는다

사이드바 전 항목(151개)의 dot 클래스별 computed `background-color`:

| dot 클래스 | 건수 | 배포본 색 | 기대 |
|---|---:|---|---|
| `conv-dot is-done` | **110** | `rgb(196,196,201)` — 기본 회색 | 초록 |
| `conv-dot is-error` | **21** | `rgb(196,196,201)` — 기본 회색 | 빨강 |
| `conv-dot is-canceled` | **2** | `rgb(196,196,201)` — 기본 회색 | 회색 계열이되 구분 |
| `conv-dot` (상태 없음) | 18 | `rgb(196,196,201)` | 기본 회색 (정상) |

**133개 항목이 상태를 정확히 알고 있는데 전부 같은 색이다.** 툴팁도 전부 빈 문자열.

배포본이 실제로 갖고 있던 `.conv-dot.is-*` 규칙은 **3개뿐**이었다:

```
.conv-dot.is-processing  { background: var(--warning); }
.conv-dot.is-completed   { background: var(--success); }      ← 아무도 만들지 않는 죽은 규칙
.conv-dot.is-stale-error { background: var(--color-danger, #dc2626); ... }  ← 코드는 is-stale_error 생성
```

서버가 쓰는 완료 리터럴은 `done` 이지 `completed` 가 아니다. 즉 **초록 규칙은 존재하되 어떤
상태에도 걸리지 않았고**, `stale_error` 는 구분자(하이픈 vs 언더스코어)가 어긋나 있었다.

## 2. 수정본 — 같은 데이터, 같은 화면

같은 대화들(53개 항목이 렌더된 구간)의 실측:

| dot 클래스 | 건수 | 수정본 색 | 툴팁 |
|---|---:|---|---|
| `conv-dot is-done` | 33 | **`rgb(22,163,74)`** (`--success`) | `완료` |
| `conv-dot is-error` | 4 | **`rgb(220,38,38)`** (`--danger`) | `오류` |
| `conv-dot is-canceled` | 2 | **`rgb(128,125,114)`** (`--text-muted`) | `취소됨` |
| `conv-dot` (상태 없음) | 14 | `rgb(196,196,201)` | (없음) |

스크린샷 2장(동일 화면 대조): `evidence/convdot-live-defect.png` · `evidence/convdot-fixed-sidebar.png`.

## 3. 요청 전송 시나리오 — 폴링이 실제로 부르는 그 함수로 전이 실측

`app/progress.js:273` 이 매 tick 호출하는 **`_updateConversationStatusDot`** 를 라이브 페이지의
실 대화 행(`20260901091004-51efb4be`)에 그대로 흘렸다. 목(mock)이 아니라 출하되는 경로다.

| 상태 | 클래스 | computed background | opacity | 툴팁 |
|---|---|---|---|---|
| `pending` | `conv-dot is-pending` | `rgb(37,99,235)` | 0.55 | 대기 중 |
| `starting` | `conv-dot is-starting` | `rgb(37,99,235)` | 0.55 | 시작 중 |
| `processing` | `conv-dot is-processing` | `rgb(217,119,6)` | 1 | 처리 중 |
| `done` | `conv-dot is-done` | **`rgb(22,163,74)`** | 1 | 완료 |
| `error` | `conv-dot is-error` | `rgb(220,38,38)` | 1 | 오류 |
| `canceled` | `conv-dot is-canceled` | `rgb(128,125,114)` | 1 | 취소됨 |
| `stale_error` | **`conv-dot is-stale-error`** (하이픈) | `rgb(220,38,38)` + 링 `rgba(220,38,38,.18) 0 0 0 2px` | 1 | 작업 중단 감지 |
| `weird_unknown` | `conv-dot` (modifier 없음) | `rgb(196,196,201)` | 1 | (없음) |

**요청 전송 순서 그대로**: `pending`(파랑) → `starting`(파랑) → `processing`(주황) →
`done`(**초록**). 사용자가 신고한 "상태값에 따라 색이 변하지 않는다" 가 해소된다.

## 4. 실측이 잡은 결함 2건 (수정 전 초판의 결함 — 고친 뒤 재실측)

초판은 `if (label) dot.title = label` 로 라벨이 있을 때만 툴팁을 설정했다. 라이브 구동에서:

- **결함 A** — 모르는 상태로 전이하면 **직전 상태의 툴팁이 그대로 남았다**
  (색은 회색으로 떨어졌는데 글씨는 "작업 중단 감지" 라고 말하는 상태).
- **결함 B** — 반대로 툴팁을 일괄로 덮으면, 사이드바 렌더가 stale_error 에 넣어 둔
  **"마지막 활동: `<시각>`"** 구체 문구가 매 폴링 tick 마다 일반 라벨로 퇴화한다
  (conv-audit FR-stale-threshold 봉인 B 가 세운 계약의 회귀).

→ dot 에 `data-title-status`(지금 붙은 툴팁이 어느 상태의 것인가)를 남겨 둘을 함께 만족시켰다.
수정 후 재실측:

| 단계 | 클래스 | 색 | 툴팁 |
|---|---|---|---|
| stale 구체문구 위에 폴링 `stale_error` | `is-stale-error` | `rgb(220,38,38)` | **`작업이 중단된 것으로 보입니다 — 마지막 활동: 2026-09-01 12:02`** (보존) |
| `stale_error` → `done` | `is-done` | `rgb(22,163,74)` | `완료` (교체) |
| `done` → 미지 상태 | `conv-dot` | `rgb(196,196,201)` | **`''`** (제거) |

## 5. 전송 직후 in-flight 행 (`is-pending-inflight` / `is-pending-failed`)

두 클래스 모두 종전에는 CSS 규칙이 **0건**이었다 — 보내는 중인지 실패했는지가 일반 항목과
똑같이 보였다. 실 렌더 경로(`renderConversationList`)로 구동해 실측:

| | 행 클래스 | opacity | cursor | 제목색 | dot | dot 색 | 툴팁 |
|---|---|---|---|---|---|---|---|
| 전송 중 | `is-pending-inflight` | 1 | pointer | `rgb(90,88,82)` italic | `is-pending` | `rgb(37,99,235)` | 대기 중 |
| 전송 실패 | `+ is-pending-failed` | **0.7** | default | **`rgb(220,38,38)`** | **`is-error`** | `rgb(220,38,38)` | 전송 실패 |

실패 행의 dot 이 종전에는 `is-pending`(대기) 이었다 — 행은 실패를 알고 있는데 점만 대기 색이던
비대칭도 함께 바로잡았다.

## 6. 동종 배선 — `is-inherited` (관리 콘솔 메타데이터 상속 행)

코드가 `is-inherited` 를 부여하고 편집을 막는데 CSS 규칙이 없어, 왜 이 행만 안 눌리는지에 대한
단서가 없었다. 규칙 도달 실측(합성 노드의 computed style):

```
background   color(srgb 0.975098 0.97451 0.972353)   (--text-muted 5% 틴트)
border-style dashed
box-shadow   rgb(230,229,224) 3px 0 0 0 inset        (좌측 rail)
```

## 7. 자동 검증

- **컨테이너 `make test`**: **6828 passed / 15 skipped / 0 failed** (`make` exit 0). 코드 수정
  전후 2회 실행, 두 번 모두 실패 0.
- **배선 계약 테스트 9건** (`tests/test_conv_status_dot_wiring.py`) — 컨테이너 내 개별 실행에서도
  9 passed. CI 가 pytest 전용이라 JS·CSS·백엔드 **소스를 파싱해 대조**한다.
- **회귀 뮤턴트 4종 전건 KILL** (각 적용 시 `git diff --stat` 으로 실제 적용 확인 후 실행):

  | 뮤턴트 (과거 결함 그대로 되살림) | 죽인 축 |
  |---|---|
  | 죽은 규칙 `is-completed` 부활 | T2 + T2b |
  | `is-${status}` 직접 조립 부활(진입점 우회) | T3 |
  | `.conv-dot.is-error` 규칙 삭제 | T2 |
  | 서버에 어휘 미등재 상태(`superseded`) 추가 | T1 |

- **node 실행 검증**: `conversationDotClass` 8상태 + 공백/`null`/대문자/미지값 정규화 실측.
- **문법**: 수정한 3개 JS 파일 `node --check` PASS.

## 8. 잔여 (정직 표기)

- **실 LLM run 을 태운 end-to-end 전이는 미실측** — 이 계정은 개인 AI 브리지 경로이고 러너가
  연결돼 있지 않아 전송 버튼이 `is-access-blocked` 다. 대신 폴링이 부르는 함수 자체를 실 DOM 에
  구동해(§3) 같은 배선을 덮었다. 브리지 러너가 붙은 환경에서의 실 run 은 POST-DEPLOY 잔여.
- **배포본 자산으로의 재확인**은 배포 후 POST-DEPLOY 로 남는다(본 실측은 bind-mount 사본 기준).
