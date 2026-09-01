---
run_at: 2026-09-01T11:30:00+09:00
session: ai/claude/interrupt-context-preserve
scope: 중단(interrupt) 시 추론·맥락·단계 보존 — /api/cancel 기본값 전환 · 보존 본문 3구획 · 활동 폴백 · 화면 재확인
verdict: PASS (자동) · Windows-browser 는 POST-DEPLOY 로 이월(사유 아래 — 사용자 결정)
---

# Run — TASK-20260901T020746-interrupt-context-preserve (PRE-DEPLOY)

## 1. 컨테이너 pytest — 전량 green

`make test` (compose 프로젝트 `repo-unittest`, 8 디렉토리) 전건 통과, ruff clean.
신규 2 파일 **28건**:

| 파일 | 건수 | 축 |
|---|---|---|
| `feature-0002/tests/test_interrupt_preserves_context.py` | 19 | 보존 본문 계약(실호출) + 취소 분기 배선 |
| `feature-0003/tests/test_cancel_preserve_default.py` | 9 | `/api/cancel` 엔드포인트 실호출 + 프런트·외부 스펙 배선 |

단정 요약:

| 축 | 단정 |
|---|---|
| 기본값 방향 | 플래그 **없는** `/api/cancel` → `mark_cancel_requested(preserve_reasoning=True)` |
| 명시 의사 존중 | `false`·`""`·`0`·`null` → `False` (falsy 를 기본값으로 승격하지 않음) |
| 미완 라벨 | 본문 첫 줄에 "중단"·"완료된 답변이 아니"·"이어지는 지시…따르세요" 3요소 |
| 라벨 위치 | meta 가 아니라 **본문**(recall 이 읽는 텍스트) |
| 진행 단계 | 도구 step 순서·번호·`[도구] 라벨` 형식 · activity step 제외(접이식과 같은 기준) |
| 상한 | 20줄 초과 시 "외 N단계" 명시(무음 절단 금지) · 줄당 160자 · SQL 개행 접기 |
| 활동 폴백 | 도구 step 0 → `진행 상황:` (중복 제거 · **꼬리** 8줄) |
| 우선순위 | 도구 step 이 있으면 활동 라벨로 본문을 늘리지 않음 |
| 빈 손 | 단계·활동·근거·부분답변 전무 → **빈 문자열**(헤더만 남은 말풍선 금지) |
| trail 적재 | 공백 무시 · 상한 초과 시 앞에서 폐기(최신 유지) · strip |
| 배선 | 취소 분기가 `_build_interrupted_note(` + `activity_trail=_activity_trail` + `_save_message` + `_mirror_message` · `_emit_activity` 가 trail 적재 |

## 2. 뮤테이션 역검증 — 3종 전건 KILL

원래 결함이 "계산" 이 아니라 **연결·기본값의 방향**이었으므로, 그 방향을 되돌리는 뮤턴트만 골랐다.

| # | 뮤턴트 | 결과 |
|---|---|---|
| M1 | `data.get("preserve_reasoning", True)` → `data.get("preserve_reasoning")` (결함 원형 복원) | **KILL** — `test_cancel_without_flag_preserves` |
| M2 | 취소 분기에서 `activity_trail=_activity_trail` 인자 제거 | **KILL** — `test_cancel_branch_builds_and_saves_the_note` |
| M3 | `_emit_activity` 의 `_append_activity_trail(...)` 호출 제거 | **KILL** — `test_emit_activity_feeds_the_trail` |

각 뮤턴트 적용 후 `git diff` 로 실제 반영을 확인하고 복원했다(자기충족 회피).

## 3. 적대 리뷰 채널 — codex 3회 시도 실패 → carve-out (사용자 승인)

`codex exec` 2회 · `codex review --uncommitted` 1회 모두 첫 응답 후 결론 없이 종료
(`bubblewrap` 부재 경고 + collab spawn 오류). 세션 상위 지시가 subagent 를 금지하므로
사용자에게 1회 확인해 `[SKIPPED:upstream-tool-carveout]` 승인을 받았다. 상세는 `REVIEW.md`.

## 4. Environment: Windows-browser — **미수행 (POST-DEPLOY 로 이월)**

**사유(사용자 결정 2026-09-01)**: 중단 UX 는 **진행 중인 run 이 실재해야** 검증된다 — 사용자가
질문을 보내고, 단계가 도는 중에 '중단' 을 눌러야 보존 말풍선이 생긴다. 미머지 상태로는 (a) 정적
자산 스탬프가 주입되지 않아 `app.js` 변경이 브라우저에 도달하지 않고, (b) 서버 보존 로직이 라이브
web·worker 에 없어 화면만 바꿔도 관측 대상이 만들어지지 않는다. §16.3 deploy-backed 완료 기준
순서(cycle-finalize → 라이브 재배포 → 실측)와 정합.

**POST-DEPLOY 측정 항목** (먼저 열거 — 사후 합리화 금지):

1. 1:1 대화에서 질문 전송 → 단계 2건 이상 진행 확인 → **'중단' 클릭**.
2. 토스트가 "요청을 중단했습니다. 진행된 내용은 대화에 남습니다." 인가.
3. **새로고침 없이** 보존 말풍선이 화면에 나타나는가(= `_reloadForPreservedInterrupt` 도달).
   나타나기까지의 경과가 1.5s·4s·10s 창 안인가.
4. 말풍선 본문에 ① 미완 라벨 ② `진행 단계:` 목록이 있는가.
5. 그 말풍선의 접이식("실행 단계"/"쿼리 결과")에 중단 전 도구 단계가 그대로 펼쳐지는가
   (= steps 앵커 복구).
6. 이어서 "아까 그거 계속" 질문 → 새 답변이 중단 전 조사를 **알고** 이어가는가(맥락 승계).
7. 반대 방향 질문("아니 다른 걸 물어볼게 …") → 새 답변이 폐기된 가설에 끌려가지 **않는가**
   (미완 라벨의 실효 — 사용자 결정 1의 단서).
8. 도구 호출 전(추론 중) 중단 → `진행 상황:` 폴백이 남는가.
9. 새로고침 후에도 보존 말풍선과 접이식이 유지되는가(deep-link `?conversation=` 로 확인 — 루트
   진입은 거짓 FAIL 을 만든다).
