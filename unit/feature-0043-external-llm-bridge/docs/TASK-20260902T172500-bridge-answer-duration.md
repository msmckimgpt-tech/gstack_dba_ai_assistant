---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260902T172500-bridge-answer-duration
status: done
edit_policy: append-only
---

# TASK-20260902T172500 — 답변 완수 시 사라진 「총 수행시간」

## 1. 요청 (사용자, 2026-09-02)

> 「프로젝트 내 서비스에서, assistant가 답변을 완수했을 때 해당 답변의 총 수행시간이
>  출력되던 부분이 누락된것으로 확인되어 수정이 필요합니다.」

## 2. 진단 — 표시 코드는 살아 있고, **각인이 끊겼다**

프런트는 그대로다. `app.js` 의 답변 메타 렌더는 `message.meta.duration_ms > 0` 일 때
수행시간(+ `duration_breakdown` 툴팁·보조문)을 그린다 — 코드·CSS 모두 무손상.

끊긴 것은 **서버가 그 값을 각인하는 배선**이다. 답변 경로가 두 갈래인데 한 갈래만 각인한다:

| 답변 경로 | `duration_ms` 각인 | 코드 |
|---|---|---|
| 서버 LLM (`run_agent`) | **한다** — `_compute_duration_breakdown` → `mirror_meta` | `agent_core.py` L9242 |
| 개인 AI 브리지 (`submit_answer`) | **안 한다** — `_meta` 에 그 키가 없다 | `ai_tools.py` `_deliver_web_bridge_answer` L2049 |

feature-0043 이 브리지를 주 경로로 승격(2026-08-26)한 순간, 답변은 전부 아래 갈래로 흘렀고
수행시간 표시는 그날부터 화면에서 사라졌다.

### 라이브 실측 (`agent_runtime.messages`, 2026-09-02)

```
 is_bridge | has_duration | count |   first    |    last
-----------+--------------+-------+------------+------------
 f         | f            |   129 | 2026-07-27 | 2026-08-26
 f         | t            |   326 | 2026-07-24 | 2026-08-26   ← 서버 LLM 경로: 각인됨
 t         | f            |   104 | 2026-08-27 | 2026-09-02   ← 브리지 경로: 전량 미각인
```

`duration_ms` 를 가진 마지막 답변은 **2026-08-26 15:26**(id 2377)이고, 그 이후 104건은
예외 없이 없다. 「출력되던 부분이 누락」이라는 제보와 경계가 정확히 일치한다.

**대기 중 표시는 정상이었다** — 전송 시 `state.pendingBubble` + `startElapsedTimer()` 가
경과를 1초 간격으로 그린다. 그래서 사용자는 처리 중엔 시간을 보고, **답변이 도착하는 순간
그 숫자가 사라지는** 것을 본다.

## 3. 계획 (§7.1)

**위험도: Minor** (§12.3 — 비파괴 additive 각인 1건. 인증·인가·파괴적 데이터·마이그레이션
없음. 기존 표시 코드·CSS 무변경, 프런트 무수정.)

### 다의어 고지 — 「총 수행시간」이 무엇으로 판정되는가 (§7.1 · §16.7 G1)

> **입력**: 웹 대화창에서 질문 전송 → 개인 AI 러너가 집어가 답변 제출
> **기대 출력**: 답변 말풍선 메타에 `Assistant · 2026-09-02 17:30 3분 12초 (대기 8.2초 · 추론 3분 4초)`
> — 즉 **요청 적재(`CreatedAt`) → 답변 제출(`SubmittedAt`)** 의 end-to-end 값 1개 +
> 점유 시각(`ClaimedAt`)으로 가른 2구간.
>
> 판정 핵심: 그 숫자가 **대기 중 보였던 경과 타이머보다 작아지지 않는다**. 서버 LLM 경로가
> TASK-0289 에서 같은 이유로 `run_start` 기준을 버리고 end-to-end 로 바꿨다 — 브리지도
> 같은 기준을 쓴다. 「러너가 실행한 시간」만 각인하면 대기 구간이 빠져 숫자가 줄어든다.

### 영향받는 파일 · symbol

| 경로 | symbol / 변경 | 비고 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | **신규** `_bridge_answer_duration_meta(total_ms, queued_ms)` — 순수 helper | 값 산출은 SQL(`TIMESTAMPDIFF`)이 하고, helper 는 clamp·형식만. tz 혼선 배제 |
| 같은 파일 | `_deliver_web_bridge_answer` — task SELECT 에 소요 2컬럼 추가 + `_meta` 에 각인 | 각인 실패는 fail-open(답변 저장을 막지 않음) — 제품 귀속 각인과 동일 규약 |
| `unit/feature-0043-external-llm-bridge/tests/test_bridge_answer_duration.py` | **신규** — helper 단위 + 배선 단정 | 결손 주입으로 가드 실효 확인 |
| `unit/feature-0043-external-llm-bridge/docs/*` | TASK/MODIFY/REVIEW/TEST/REPORT | |

프런트(`app.js`·CSS)·`_replace_bridge_placeholder`·회수 store 는 **무변경** —
placeholder 덮어쓰기는 `meta_json` 전량 교체라 각인이 그대로 실린다.

### 접근 방법

1. 소요는 **SQL 에서 계산**한다 — `TIMESTAMPDIFF(MICROSECOND, CreatedAt, COALESCE(SubmittedAt, NOW()))`.
   MySQL `datetime` 은 tz-naive 이고 `CreatedAt`(DEFAULT CURRENT_TIMESTAMP)·`SubmittedAt`(NOW())가
   같은 서버 시계에서 나오므로 차이는 안전하다. 파이썬으로 끌어와 `datetime` 산술을 하면
   드라이버·tz 설정에 따라 어긋날 수 있다.
2. helper 는 **방어만** 한다: 값 없음/0 이하 → 각인 생략(거짓 0초 금지), `queued > total` 또는
   `ClaimedAt` 없음(구 task·외부 origin) → 분해 없이 `inference_ms = total`.
3. 키 이름은 서버 LLM 경로와 **동일**하게 둔다(`total_ms` · `queued_ms` · `inference_ms`) —
   프런트 `formatDurationBreakdown` 이 그 세 키만 읽으므로 새 라벨을 만들면 표시가 갈린다.
   브리지에 없는 구간(`init_ms`)은 **싣지 않는다**(0 을 실으면 없는 계측을 있다고 말하는 셈).

### 완료 판정 기준 (acceptance criteria)

| # | 조건 |
|---|---|
| AC-1 | 브리지 답변 저장 시 `meta.duration_ms` 가 `SubmittedAt − CreatedAt`(ms) 로 각인된다 |
| AC-2 | `ClaimedAt` 이 있으면 `meta.duration_breakdown = {total_ms, queued_ms, inference_ms}`, 없으면 `{total_ms, inference_ms}` |
| AC-3 | 소요를 못 구하면(컬럼 부재·NULL·0 이하) 각인을 생략하고 답변 저장은 **그대로 성공** |
| AC-4 | 프런트 무수정으로 말풍선 메타에 수행시간 + 구간 분해가 표시된다 (라이브 확인) |
| AC-5 | 각인 배선을 제거하면 신규 테스트가 FAIL 한다 (결손 주입) |

## 4. 조치 (구현)

| # | 무엇 | 어디 |
|---|---|---|
| ① | 각인 helper — end-to-end 총량 + `ClaimedAt` 으로 가른 «대기/실행» | `ai_tools._bridge_answer_duration_meta` (신규, 순수 함수) |
| ② | 원장 시각 조회 — 계산은 SQL(`TIMESTAMPDIFF`), 실패는 빈 dict | `ai_tools._bridge_task_duration_meta` (신규) |
| ③ | 답변 meta 에 각인 1줄 | `ai_tools._deliver_web_bridge_answer` |

프런트·CSS·`_replace_bridge_placeholder`·회수 store 무변경.

### 계획과 달라진 두 곳 (§3 표는 초안 그대로 남긴다 — append-only)

1. **소요 조회를 주 SELECT 에 얹지 않았다.** 계획은 「task SELECT 에 소요 2컬럼 추가」였는데,
   그러면 `ClaimedAt`/`SubmittedAt` 컬럼 부재(부트스트랩 ALTER 실패)가 **답변 전달 자체를**
   실패시킨다 — fail-open 이라 적어 둔 계약이 그 형태에서는 성립하지 않는다. 별도 함수
   (`_bridge_task_duration_meta`)로 분리했고, 결손 주입 ③ 이 합친 형태의 실패를 실증한다.
2. **테스트는 `unit/feature-0003-agent-web-ui/tests/` 에 뒀다.** feature-0043 의 conftest 가
   feature-0003 의 `src` 를 path 에 올리지 않는다(두 feature 가 각자 최상위 `modules` 패키지를
   가져 서로를 가린다 — 그 conftest 의 명시 규약). 웹 라우터를 실제로 구동하는 테스트는
   그쪽에 두는 것이 이 저장소의 기존 배치다.

## 5. 검증

- 신규 `test_bridge_answer_duration.py` **18 passed** (helper 값 계약 + 실구동 배선).
- 관련 스위트(feature-0003 · 0043 · 0041) **실패 0**.
- **결손 주입 3종 전건 FAIL**: 각인 제거 → 3 FAIL · 기준을 `ClaimedAt` 으로 → 1 FAIL ·
  소요 조회를 주 SELECT 로 합침 → 4 FAIL(답변 전달 실패 로그 동반).
- 상세 증거: `docs/test-runs.d/TASK-20260902T172500-bridge-answer-duration.md`.

## 6. 잔여

배포 후 **실 브리지 답변 1건**으로 라이브 확인(화면 + `agent_runtime.messages.meta_json`).
과거 104건은 소급 각인하지 않는다 — 사후 삽입은 관측이 아니다.
