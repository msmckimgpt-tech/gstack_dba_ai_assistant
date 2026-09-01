---
run_at: 2026-09-01T12:20:00+09:00
session: ai/claude/interrupt-preserve-bridge
scope: 브리지(개인 AI) 중단이 진행 단계를 다음 요청 맥락으로 넘기는가
verdict: PASS (자동) · Windows-browser 는 POST-DEPLOY (앞 cycle fragment 의 측정 항목과 합쳐 수행)
---

# Run — TASK-20260901T031500-interrupt-preserve-bridge (PRE-DEPLOY)

## 1. 컨테이너 pytest — 전량 green

`make test` (compose 프로젝트 `repo-unittest`, 8 디렉토리) 전건 통과, ruff clean.
신규 `feature-0003/tests/test_bridge_cancel_preserves_progress.py` **12건**:

| 축 | 단정 |
|---|---|
| 꼬리 생성 | steps 2건 → `진행 단계:` + 번호·도구·라벨 · **미완 라벨** 포함 |
| 형식 공유 | `_build_interrupted_note(` 호출 + `header=_BRIDGE_PROGRESS_TAIL_HEADER` (브리지 전용 렌더러 금지) |
| 단계 부재 | `[]`·`None` → 빈 꼬리(있지도 않은 "진행된 내용" 을 지어내지 않음) |
| 조회 실패 | 예외 → 빈 꼬리(취소 안내 자체는 살아남음) |
| 인자 경계 | conversation_id·task_id 중 하나라도 비면 빈 꼬리 |
| 배선(순서) | `for tid in task_ids` **뒤에** `_bridge_progress_tail(` — 루프 밖이면 모든 말풍선이 같은 단계를 갖는다 |
| 각인 보존 | 취소 UPDATE 가 `run_id` 를 건드리지 않음(접이식이 직전 답변 단계로 폴백하던 과거 결함 재발 차단) |
| header 계약 | 커스텀 머리말 / `""` 본문만 / 기본은 서버 라벨 유지(앞 cycle 무회귀) |
| 빈 노트 | 남길 것이 없으면 header 를 줘도 `""` |

## 2. 뮤테이션 역검증 — 1종 KILL

| # | 뮤턴트 | 결과 |
|---|---|---|
| M1 | `_tail = _bridge_progress_tail(...)` → `_tail = ""` (꼬리 미부착) | **KILL** — `test_cancel_notice_appends_the_tail_per_task` |

적용 후 `grep` 으로 실제 반영을 확인하고 복원했다.

## 3. 앞 cycle 무회귀

`feature-0002/tests/test_interrupt_preserves_context.py` **19건 그대로 PASS** —
`header` 파라미터 추가가 서버 경로 기본 동작을 바꾸지 않음을 실제 호출로 확인.

## 4. Environment: Windows-browser — POST-DEPLOY

앞 cycle fragment(`TASK-20260901T020746-interrupt-context-preserve.md` §4)의 측정 항목 9건에
**브리지 전용 3건**을 더해 배포 후 한 번에 수행한다:

10. 브리지(개인 AI) 대화에서 도구 조회가 2건 이상 돈 뒤 '중단' → 취소 안내 말풍선 본문에
    미완 라벨 + `진행 단계:` 가 붙는가.
11. 그 말풍선의 접이식 단계가 **여전히** 그 task 의 것인가(직전 답변 단계로 폴백하지 않는가).
12. 이어서 보낸 질문을 개인 AI 가 열었을 때, 받은 대화 맥락에 그 진행 단계 텍스트가
    포함돼 있는가(러너 측 수신 내용으로 확인).
