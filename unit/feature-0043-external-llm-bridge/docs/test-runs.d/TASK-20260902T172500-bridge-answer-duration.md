---
run_at: 2026-09-02T17:35:00+09:00
session: ai/claude/feature-0043-bridge-answer-duration
scope: 브리지 답변 총 수행시간 각인 (`_bridge_answer_duration_meta` · `_bridge_task_duration_meta` · `_deliver_web_bridge_answer`)
verdict: PASS (단위 + 결손 주입) / 잔여 — 배포 후 실 브리지 답변 1건 라이브 확인
---

# Run — 답변 총 수행시간 각인 (TASK-20260902T172500)

Environment: container (`repo-unittest-agent` 이미지 + worktree 마운트, `PYTHONDONTWRITEBYTECODE=1`)

## 결과

| 스위트 | 결과 |
|---|---|
| `tests/test_bridge_answer_duration.py` (신규) | **18 passed** |
| `unit/feature-0003-agent-web-ui/tests` + `feature-0043` + `feature-0041` 전체 | **실패 0** (exit 0, FAILED/ERROR 0건) |

## 결손 주입 — 가드가 실제로 결함을 잡는가

「방어를 넣었다」와 「방어가 성립한다」는 다르다. 세 가지를 주입해 각각 FAIL 을 확인했다
(주입 후 원본 복원, `git diff --stat` 으로 잔재 0 확인).

| 주입 | 무엇이 깨지는가 | 결과 |
|---|---|---|
| ① `_meta.update(_bridge_task_duration_meta(...))` 제거 | 각인 배선 소실 = **이 cycle 이 고친 결함 그 자체** | **3 FAIL** (`wiring` · `unclaimed` · `separate_query`) |
| ② 총량 기준을 `CreatedAt` → `ClaimedAt` | 대기 구간이 총량에서 빠져 표시 숫자가 조용히 줄어든다 | **1 FAIL** (`basis`) |
| ③ 소요 조회를 전달 경로의 주 SELECT 로 합침 | 컬럼 부재 시 **답변 전달 자체가 실패** | **4 FAIL** — 로그에 `[bridge] 답변을 대화에 전달하지 못했다 … Unknown column 'ClaimedAt'` |

③ 이 특히 load-bearing 이다. 초안은 소요를 주 SELECT 에 얹었는데, 그 형태는 부트스트랩 ALTER
가 실패한 환경에서 **관측을 얻으려다 사용자 대면 산출물을 잃는다**. 테스트가 그 교환을 거부한다.

## 확인한 사실 (증거)

- **결함 실측 (라이브 `agent_runtime.messages`)**: `duration_ms` 보유 마지막 답변 = id 2377 /
  2026-08-26 15:26. 이후 브리지 답변 104건(2026-08-27 ~ 09-02) **전량 부재**. 서버 LLM 경로
  326건은 각인됨 — 두 경로의 비대칭이 그대로 관측된다.
- **표시 코드 무손상**: `app.js` 의 `durationMs > 0` 게이트와 `.message-meta-duration` CSS
  모두 현행. 프런트를 고칠 이유가 없음을 코드로 확인한 뒤 백엔드만 만졌다.
- **키 정합**: 프런트 `formatDurationBreakdown` 이 읽는 축은 `queued_ms`·`init_ms`·
  `inference_ms` 뿐 — 신규 각인이 그 집합을 벗어나지 않음을 테스트가 단정한다.
- 편집 파일 AST 구문 검증 통과.

## 미수행 (정직 표기)

- **라이브 확인** — 배포 후 실 브리지 답변 1건이 필요하다(사용자 머신 러너가 제출해야 발생).
  「단위 통과」는 배선 성립까지이고, 화면에 숫자가 뜨는 것은 그것으로 갈음하지 않는다.
- **PB-0008 시각검증** — 웹 자산(static/template) 변경 0이라 `visual_verification_scope: always`
  의 대상 표면이 없다(verify-completion check #13 도 skip 판정). 다만 결과가 화면 표시이므로
  배포 후 라이브 대화에서 눈으로 확인한다.
- **과거 104건 소급 각인 안 함** — 지나간 task 의 시각으로 사후 삽입하면 그 값이 관측인지
  추정인지 구분되지 않는다. 표시는 이번 수정 이후 답변부터 나타난다.
