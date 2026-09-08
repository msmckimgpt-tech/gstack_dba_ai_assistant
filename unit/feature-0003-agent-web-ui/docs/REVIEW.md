---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260901T190000-conv-status-dot-wiring [CODEX:frontend-state-wiring] — 사이드바 상태 배지 색 배선 복원 (Minor §12.3)

- **채널**: `/codex review` (gpt-5.6-sol, `model_reasoning_effort=high`, read-only sandbox).
  본 세션은 subagent 호출이 금지되어 있어 §18.8 의 `[CODEX:*]` 경로를 택했다 — 사용자 확인
  (AskUserQuestion, 2026-09-01) 후 진행했다. 1차 시도는 codex 사용량 한도로 실패했고
  2026-09-02 재시도에서 완주했다.
- **Verdict**: **PASS** — `[P1]` 0건, `[P2]` 5건. 다섯 건이 **전부 게이트 자체의 사각지대**를
  가리켰다(구현이 아니라). 다섯 건 모두 사실 확인 후 **수용·수정**했다.

### 지적 5건과 조치 — 요지는 하나였다: 「테스트는 통과하는데 결함은 살아 있다」

| # | codex 지적 | 사실 확인 | 조치 |
|---|---|---|---|
| 1 | T1 이 상태 writer 를 **하드코딩 목록**으로 들고 있어 `routers/conversations.py:1328` 의 실제 writer 를 못 보고, 3번째 인자가 변수인 호출(`modules/ask.py` 의 `_status`)을 조용히 건너뛴다 | ✅ 둘 다 재현 | 파일 목록 → **저장소 전수 탐색**. 변수 인자는 같은 함수 위쪽의 지역 대입을 역추적해 해석하고, **끝내 해석 못 한 호출은 FAIL** (근거를 적어 등재하지 않는 한) |
| 2 | T2 가 **셀렉터 이름의 존재**만 봐서 `.conv-dot.is-done {}` 빈 규칙이나 `color` 만 바꾸는 규칙도 통과한다 — 정작 관측값은 배경색 | ✅ | 규칙의 **선언 본문**을 파싱해 `background`/`background-color` 선언을 요구 (`collect_css_declarations_for`) |
| 3 | 툴팁 이음매(`data-title-status`)를 **아무 테스트도 건드리지 않는다** — 분기를 지워도 green | ✅ | **T5 신설** — 폴링 갱신부의 세 계약(소유자 읽기 · `stale_error` 예외 · 라벨 없을 때 `removeAttribute`) + 사이드바의 소유자 기록 |
| 4 | 감사가 `${...}` 를 통째로 비워, 조건식 안에서만 부여되는 클래스가 **양쪽 집합에서 동시에** 사라진다 — `app/attach-diff.js:336` 의 `${checked ? " is-checked" : ""}` 가 실례 | ✅ CSS 규칙(`chat.css:3318`)을 지워도 T4 가 통과함을 재현 | 보간부를 비우는 대신 **그 안의 문자열 리터럴을 남긴다**(`_resolve_interpolation`). 리터럴이 없는 진짜 동적 조립은 종전대로 「동적 지점」으로 보고 |
| 5 | T3 의 직접-조립 탐지가 **줄 단위**라 줄바꿈된 배정을 놓치고, T3b 최소치(3)가 실제 호출 수(4)보다 낮아 한 경로를 되돌려도 통과한다 | ✅ 둘 다 재현 | 탐지를 **파일 전체 DOTALL** 로. T3b 를 `>=` → **정확한 수**로 묶어, 빠지거나 늘면 계약을 갱신하게 만듦 |

### 뮤테이션 — 지적받은 회귀를 그대로 되살려 6종 전건 KILL

각 뮤턴트 적용 시 `git diff --stat` 으로 실제 적용을 확인한 뒤 실행했다.

| 뮤턴트 | 죽인 축 | 지적 |
|---|---|---|
| `is-done` 을 배경 없는 규칙(`color`)으로 | T2 | #2 |
| 줄바꿈된 직접 조립 부활 | T3 + T3b | #5a |
| 한 seam 만 헬퍼에서 되돌림 | T3 + T3b | #5b |
| 조건식 전용 `is-checked` 의 CSS 규칙 삭제 | T4 | #4 |
| 툴팁 소유권 분기 제거 | T5 | #3 |
| 종전 목록 밖 writer 에 신규 상태(`aborted`) 추가 | T1 | #1 |

앞선 4종(죽은 규칙 `is-completed` 부활 / `is-${status}` 조립 부활 / `.conv-dot.is-error` 삭제 /
서버 신규 상태 미등재)까지 합쳐 **10종 전건 KILL**.

### 남긴 한계 (정직 표기)

**T5 는 소스 형태 검사다.** CI 가 pytest 전용이라 브라우저 실행을 게이트에 넣을 수 없다.
툴팁 이음매의 실제 동작은 PB-0008 실측이 확인했고(`test-runs.d/TASK-20260901T1900-…` §4),
T5 는 그 구조가 조용히 사라지는 것을 막는 역할이다 — 둘을 같은 강도로 읽지 않는다.
이 한계는 테스트 docstring 에도 명시했다.

**codex 는 구현 자체에는 지적이 없었다.** 순환 import/TDZ(leaf 모듈 배치), 상태 어휘의
CSS 도달, 툴팁 경쟁 상태 세 축 모두 `[P1]`·`[P2]` 없이 통과했다.

## REV-20260901T143000-rqrd-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 부재 확인 기록 (doc-only)

- **Trigger**: 코드 변경 **0** — 실측 결과 기록만(`test-runs.d/` fragment + 스크린샷 + TASK/MODIFY/REPORT).
  §18.8 dispatch 표의 어느 축(backend/qa/ux/design/security)도 매칭되지 않는다.
- **채널**: doc-only 이므로 패널 대상 아님. 기록의 근거는 **실측 그 자체**다 — 서빙 사본
  fetch 결과(D1~D3)와 라이브 DOM 계수(PD1~PD4).

### 판단 — 제거 검증은 «전·후 두 번» 이라야 성립한다

「없다」만 관측하면 **애초에 없던 것**과 구별되지 않는다. 그래서 배포 전 fragment 가 제거
대상 4요소를 기준선으로 못 박았고, 이 fragment 가 같은 대화·같은 위치에서 그것들이 0 이
됐음을 못 박는다. 대조 대상을 «같은 대화» 로 고정한 것이 이 쌍의 유효성 조건이다 — 다른
화면을 보면 두 관측이 서로를 증명하지 못한다.

선행 cycle 의 잔여 2축(브리지 진행 중 입구 생성 · 구형 메시지 소실 실측)은 **여전히 미검증**
이며 사유와 함께 남겼다. 4/4 PASS 가 그 둘을 대신하지 않는다.

## REV-20260901T133000-remove-query-result-details [SKIPPED:upstream-tool-carveout] — 말풍선 「▼ 쿼리 결과」 여닫이 제거

- **Trigger**: `UI/화면/레이아웃` keyword matched (사용자 요청이 말풍선 표시면 제거) →
  §18.8 표상 required subagents = `ux, design`.
- **채널 불가 2건 (실측)**:
  1. `codex exec` — `ERROR: You've hit your usage limit … try again at 3:44 PM`(2026-09-01
     14:20 KST 시도). 프롬프트 조립·diff 전달까지 정상 수행 후 상류 한도로 반환.
  2. `ux` · `design` subagent — **이 저장소에 정의가 없다**(`.claude/agents/` 에는
     `improve-fit-reviewer` 뿐). 표가 지정한 두 도메인을 호출할 실체가 부재하다.
- **carve-out**: 위 두 사실을 사용자에게 제시하고 선택을 받았다 —
  「carve-out 승인 후 진행」(2026-09-01). 선례: `REV-20260901T031500` ·
  `REV-20260901T020746` 의 같은 태그.
- **입력 측 ADR 전달**(§18.8): 대상 diff + 「의도된 구성」 3건(제거는 사용자 결정 · CSV 소실은
  고지 후 수용 · `share.js` 는 범위 밖)을 codex 프롬프트에 명시했다. 재실행 시 그대로 쓴다.

### 자체 적대 점검 — 결함 2건 적발 (패널 대체 아님, 보완)

패널을 대신한다고 주장하지 않는다. 아래는 「제거 변경」 고유의 실패 모드 5축을 스스로 겨눈
결과이며, **2건이 실제로 걸렸다**.

| 축 | 결과 |
|---|---|
| 제거 후 조용히 no-op 이 되는 배선 | **적발 → 수정**: `_renderBridgeSteps` 가 여닫이만 그리고 있었다. 그냥 지웠다면 진행 중 말풍선에 단계 진입로가 **0** 이 된다(placeholder 는 `meta.steps` 없이 그려져 app.js 가 버튼을 붙이지 못한다). 패널 갱신 + 버튼 «없으면 생성» 으로 교정. |
| 제거된 심볼/CSS 잔재 참조 | **적발 → 수정**: `messageLogEl` 이 미사용 import 로 남았다(제거된 스크롤 앵커 전용). 그 외 잔재 0 — 함수 9종·CSS 12규칙 전수 grep 로 확인(`share.js` 의 동명 함수는 그쪽 **자체 사본**이며 범위 밖). |
| 남은 표시면 진입로 부재 경계 | 위 수정으로 닫힘. 구조 단언으로 잠금(`test_bubble_always_offers_an_entrance_to_the_panel`). |
| 테스트가 항진명제인가 | 부재 단언 6종은 **제거 전 코드에서 전부 FAIL** 하는 형태(`"function renderMessageDetails(" not in src`)라 항진이 아니다. 존재 단언(`bubble.appendChild(fresh)`)도 마찬가지. |
| 고지되지 않은 동반 소실 | **적발 → 고지**: 구형 메시지 폴백(`meta.sql` → 「실행 SQL」, `meta.csv_paths` → 「결과 파일」)도 이 블록 안에 있었고, 그런 메시지는 `meta.steps` 가 없어 「단계 보기」 버튼조차 없다 → **대체 표시면 부재**. 결정 시 고지된 손실은 CSV 2건뿐이었으므로 TASK/REPORT 에 기록하고 사용자에게 별도 보고했다. |

### 잔여 리스크 (숨기지 않는다)

- ux/design 관점의 **독립** 검토는 받지 못했다. 위 표는 같은 작성자가 자기 변경을 본 것이고,
  「방어를 넣었다 ≠ 방어가 성립한다」는 자체 검토가 구조적으로 약한 축이다.
- 브리지 **진행 중** 화면의 라이브 관측이 없다(개인 AI 러너 미연결). 구조 단언까지만 잠겼다.
- POST-DEPLOY 부재 확인 4항목은 배포 후 수행 — 미수행 상태에서 완료를 선언하지 않는다.

## REV-20260901T121000-interrupt-preserve-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록 (doc-only)

- **Trigger**: 코드 변경 **0** — 실측 결과 기록만(`test-runs.d/` fragment + TASK/MODIFY/REPORT).
  §18.8 dispatch 표의 어느 축(backend/qa/ux/design/security)도 매칭되지 않는다.
- **채널**: doc-only 이므로 패널 대상 아님. 기록의 근거는 **실측 그 자체**다 — 서빙 사본
  fetch 결과(D1~D4)와 Playwright 클릭 실패 로그(`element is not enabled`).

### 판단 — 「미검증」을 적는 것이 이 기록의 요지

도달 4/4 가 PASS 이고 계약 테스트 40건과 뮤테이션 4종이 통과했으므로, 이 상태를 "완료" 로
적고 넘어갈 수 있었다. 그렇게 하지 않은 이유는 **각 축이 서로를 대신하지 못하기** 때문이다:

- 계약 테스트는 함수가 옳음을 말한다 — 사용자가 그 함수에 도달하는지는 말하지 않는다.
- 도달 확인은 자산이 브라우저에 왔음을 말한다 — 그 화면이 의도대로 움직이는지는 말하지 않는다.
- 왕복 검증만이 마지막 축을 덮는데, 그것이 **러너 미연결로 불가능**했다.

이 구분을 흐리면 다음 세션이 fragment 를 보고 "검증됐다" 로 읽는다. 그래서 §3 에 축별
검증/미검증 표를 두고, 미수행 사유를 추정이 아니라 **관측된 문자열**(`is-access-blocked`,
`element is not enabled`, `pgrep` 무응답)로 남겼다.

**재개 조건이 사람 자격에 걸려 있다**: 러너 재기동에는 웹에서 사람이 발급하는 `mat_` 토큰이
필요하고 러너는 그것을 저장하지 않는다. AI 세션이 단독으로 넘을 수 있는 문턱이 아니므로
BLOCKED 로 위장하지 않고 **이월**로 적는다(측정 항목은 이미 사전 열거돼 있어, 연결 직후
그대로 수행하면 된다).

> 이전 기록(389건): [REVIEW-archive-20260711T115053.md](./_archive/REVIEW-archive-20260711T115053.md)

## REV-20260901T031500-interrupt-preserve-bridge [SKIPPED:upstream-tool-carveout] — 라이브 실경로(브리지)까지 보존을 넓힌 근거

- **Trigger**: `Code change` (브리지 취소 경로 본문 조립). §18.8 축 = backend·qa.
- **채널(§18.8.2)**: 앞 cycle 과 동일 carve-out(세션 상위 지시가 subagent 금지 · codex 3회
  환경 실패 · 사용자 승인 2026-09-01). 대체 채널 = 신규 12 PASS · 뮤테이션 1종 KILL ·
  브리지 3축 전수 확인(아래) · `make test` 전건.
- **승인 근거(§12.2)**: `deploy_scope: included`. 위험도 **Minor**(§12.3 — 이미 쓰던 UPDATE 의
  본문 문자열이 길어질 뿐 · 실패는 전부 종전 동작으로 degrade).

### 판단 1 — 이 작업이 «scope 확장» 이 아니라 «요청의 실경로» 인 근거

앞 cycle 을 배포하고 나서야 스모크 로그가 드러냈다:

```
[smoke-conv] [llm-gate] 서버 계정 LLM 호출 차단 — feature-0043 전환
             (추론은 사용자 개인 AI 런타임이 수행)
```

라이브는 서버 LLM 이 꺼진 브리지 모드다. **사용자가 실제로 누르는 '중단' 은 앞 cycle 이 고친
지점을 지나가지 않는다.** 서버 경로만 고치고 완료를 선언했다면, 요청("중단해도 추론·맥락·단계가
손실되지 않게")은 문서상 충족이고 화면에서는 미충족이었다.

**앞 cycle 의 REPORT 가 브리지를 "미커버(구조적으로 부분 추론 없음)" 로 적은 것은 절반만
맞았다.** 부분 추론이 없다는 것은 사실이나, 그로부터 "브리지는 남길 것이 없다" 를 도출한 것이
오류였다 — 개인 AI 가 **우리 도구를 부른 내역**은 우리 안에 있다(`_record_bridge_step` 이
인자·사유까지 담아 `agent_runtime.steps` 에 적재). 그 사실을 이번에 반영한다.

### 판단 2 — 세 축 중 «맥락» 만 비어 있었다 (전수 확인)

브리지 취소를 축별로 추적한 결과, 두 축은 이미 성립하고 있었다:

| 축 | 성립 여부 | 기전 |
|---|---|---|
| 화면·이력 | ○ | `_mark_bridge_placeholders_canceled` 가 대기 말풍선을 취소 안내로 교체(삭제가 아니라 교체) |
| 단계(접이식) | ○ | 그 UPDATE 는 `bridge.canceled`·`bridge.placeholder` 만 건드리고 **`run_id` 각인을 유지**한다 → `_load_steps_for_message` 가 그 task 의 steps 를 붙인다 |
| 다음 요청의 맥락 | **×** | `ai_tools._recent_conversation_context` 는 `_conv_load_messages_raw` 의 **content 텍스트만** 읽는다 — steps 도 meta 도 보지 않는다 |

그래서 고칠 지점은 하나였다: **단계를 말풍선 본문(텍스트)에 적는 것**. 접이식에 이미 보이는
것을 텍스트로도 적는 중복처럼 보이지만, 두 소비자가 다르다 — 접이식은 **사람**이 보고,
본문 텍스트는 **다음 요청의 개인 AI**가 본다.

### 판단 3 — 빌더를 공유하고 머리말만 갈아끼운 근거

`_build_interrupted_note` 에 `header` 파라미터를 추가해 브리지가 자기 문맥의 머리말로 같은
본문 형식을 쓴다. 브리지 전용 렌더러를 따로 만들지 않은 이유는 이 저장소가 반복해 겪은 부류의
결함이기 때문이다 — 같은 사실을 두 벌로 만들면 두 화면이 갈리고, 갈리는 쪽 중 **약한 것이
사용자가 보는 진실**이 된다(P0-R). 기본값(`header=None`)은 서버 경로 라벨을 그대로 유지해
앞 cycle 의 19건이 무회귀로 통과한다.

### 판단 4 — 꼬리를 task 루프 «안» 에서 만든 근거

`_mark_bridge_placeholders_canceled` 의 `notice` 는 호출자가 **하나만** 준다(취소/supersede
두 문구). 그러나 진행 단계는 **task 마다 다르다**. 루프 밖에서 한 번 만들면 여러 대기 질문을
한꺼번에 취소할 때 모든 말풍선이 같은 단계를 갖는다 — 남의 조사가 내 질문 아래 붙는다.
테스트가 `for tid in task_ids` 와 `_bridge_progress_tail(` 의 **순서**를 단언한다.

### 판단 5 — degrade 를 «종전 동작» 으로 고정한 근거

단계 조회 실패(PG 다운)·단계 부재(도구 호출 전 중단) 모두 빈 문자열을 반환해 **종전 취소
안내 그대로**가 된다. 단계 기록은 취소의 조건이 아니다 — 여기서 예외를 올리면 취소 자체가
무를 수 있고, 그러면 사용자는 "취소했다" 는 표시조차 못 본다(브리지 취소는 이미 확정된 뒤다).
머리말도 꼬리와 **함께만** 붙여, 단계가 없을 때 "진행된 내용" 을 단정하지 않는다.

### 미커버 (구조적)

- **개인 AI 의 부분 추론 자체**: 러너 쪽에서 일어나므로 우리는 관측하지 못한다. 우리가 남길 수
  있는 것은 **우리 도구로 관측한 사실**(무엇을 왜 조회했는가)뿐이며, 그것을 추론인 양 적지 않는다.
- **회수 store(core_messages)**: 브리지 안내 말풍선은 의도적으로 표시 store 에만 쓴다(시스템
  안내를 LLM turn 으로 위조하지 않기 위해 — 기존 설계). 브리지의 맥락 조립이 표시 store 를
  읽으므로 이 선택으로도 맥락 승계는 성립한다.

## REV-20260901T020746-interrupt-context-preserve [SKIPPED:upstream-tool-carveout] — 중단 보존의 기본값·라벨·재확인 설계

- **Trigger**: `Code change` (backend 취소 계약 + frontend 중단 UX). §18.8 dispatch 표 매칭 축 =
  backend·qa·ux.
- **채널(§18.8.2)**: 본 세션의 상위 지시가 subagent 호출을 금지한다(`Do not call the AgentTool
  unless the user requested it`). 제약 없는 채널을 먼저 시도 — `codex` 적대 리뷰를 **3회**
  (exec 2회 · review --uncommitted 1회) 호출했으나 전부 첫 응답 뒤 결론 없이 종료했다
  (환경 문제: `bubblewrap` 부재 경고 + collab spawn 오류). **사용자에게 1회 확인**해
  carve-out 승인을 받았다(2026-09-01, AskUserQuestion — 선례 REV-20260831T144500·
  REV-20260812T203000 과 동일). 대체 채널 = ① 신규 테스트 2종 **28 PASS**(동작 19 + 엔드포인트 9)
  ② **뮤테이션 역검증 3종 KILL** ③ 호출 경로 전수 추적(아래) ④ `make test` 전건 통과
  ⑤ 배포 후 PB-0008 실 Windows 브라우저 실측(사용자 결정 — 중단 UX 는 진행 중 run 이 있어야
  검증되므로 라이브에서).
- **승인 근거(§12.2)**: `FIRST_REQUEST.md` `deploy_scope: included` — cycle-final 후 배포까지
  사전 승인 범위. 첫 배포 직전 1줄 표면화 이행. 위험도 **Minor**(§12.3 — 스키마·마이그레이션·
  RBAC·신규 엔드포인트 0, 비파괴 메시지 1건 추가, 롤백 = revert + 재배포).

### 판단 1 — 기본값을 프런트가 아니라 «서버» 에서 뒤집은 근거

증상만 보면 프런트 한 줄(`preserve_reasoning: true` 추가)로 끝난다. 그렇게 하지 않은 이유는
`/api/cancel` 이 **두 표면에 공개**돼 있기 때문이다 — 웹 UI 와 외부 AI 도구 표면
(`ai_discovery.py` 의 discovery 목록 + OpenAPI). 프런트만 고치면 외부 경로는 계속 폐기하고,
"중단하면 진행분이 남는다" 는 계약이 호출자에 따라 갈린다. 갈리는 계약은 느슨한 쪽이 사용자가
보는 진실이 된다(같은 저장소의 P0-R 선례).

그래서 서버 기본값을 `True` 로 두고 **명시 falsy 만 폐기**로 남겼다. 폐기 경로를 없애지 않은
것은 (a) 향후 '버리고 중단' UI 의 자리이고, (b) 명시적 사용자 의사를 무시하지 않기 위해서다.
`""`·`0`·`null` 같은 falsy 를 기본값으로 승격시키지 않는 것도 테스트로 잠갔다 — `data.get(k, True)`
는 "키가 없을 때" 만 기본값을 주므로 이 구분이 코드에 이미 있다.

### 판단 2 — 미완 라벨을 meta 가 아니라 «본문» 에 둔 근거 (사용자 결정 1의 단서)

사용자 결정은 "화면 + 다음 맥락 모두 보존" 이되 **"방향이 틀려서 재요청한 경우도 LLM이 충분히
판단할 수 있는 구조로"** 였다. 보존분은 `_save_message` 로 `core_messages` 에 들어가 다음 run 의
recall 에 실린다. 이때 모델이 보는 것은 **본문 텍스트뿐**이다 — mirror meta 의
`interrupted: true` 는 표시 store 에만 있고 화면 렌더용이다. 라벨을 meta 로만 두면 화면은 알아도
모델은 모르고, 중간 기록을 확정 결론으로 읽어 폐기된 가설 위에서 답을 잇는다.

따라서 헤더 문장이 두 가지를 명시한다: (a) **미완**("완료된 답변이 아니라 … 중간 기록"),
(b) **새 지시 우선**("이어지는 지시가 이와 다른 방향이면 그 지시를 따르세요"). 이 두 문구의 존재를
테스트가 직접 단언한다(문구를 지우면 red).

대안으로 "보존은 하되 recall 에서 제외" 를 검토했으나 사용자 결정 1이 명시적으로 배제했다 —
그러면 "맥락 손실 방지" 요구의 절반만 충족한다.

### 판단 3 — 활동 trail 을 «in-process» 로 든 근거

도구 호출 전 중단을 커버하려면 활동 라벨이 필요한데, 그 값은 이미 `agent_runtime.steps` 에
`action='activity'` 로 저장돼 있다. DB 를 되읽지 않고 in-process 리스트로 든 이유:

| 후보 | 문제 |
|---|---|
| 취소 분기에서 `load_recent_steps` 로 되읽기 | 취소 경로에 DB 왕복이 하나 더 붙는다. 그 경로는 이미 KV·큐·브리지 3축을 건드리며, 한 번의 조회 실패가 보존 자체를 날릴 수 있다(같은 함수의 브리지 취소가 그 이유로 순서를 앞당겼다) |
| activity 를 `steps` 리스트에 함께 담기 | `steps` 는 `result["steps"]`·`_step_csv_paths`·`_summarize_step_rationale` 의 입력이다. 여기에 activity 를 섞으면 세 소비처의 의미가 동시에 바뀐다 |
| **채택: 별도 `_activity_trail` (라벨 문자열만, 상한 40)** | 비용이 문자열 몇십 개. 소비처가 하나(취소 분기)라 파급이 없다 |

상한을 **꼬리 우선**(앞에서 버림)으로 둔 것은 "무엇을 하던 중이었나" 가 중단 직전 라벨에 있기
때문이다. 적재 규칙(공백 무시·상한)은 중첩 함수에 인라인으로 두면 단위 검증이 불가능해
모듈 레벨 `_append_activity_trail` 로 분리했다(경계 3건을 실제 호출로 잠금).

### 판단 4 — 단계 UI 를 «앵커 1건» 으로 복구한 근거 (새 저장 경로를 만들지 않음)

"단계가 손실된다" 는 증상만 보면 단계 스냅샷을 메시지 meta 에 따로 저장하는 설계가 떠오른다.
전수 추적 결과 **그럴 필요가 없었다**:

- 취소해도 `agent_runtime.steps` 행은 남는다 — `_purge_run_steps` 는 정의만 있고 **호출부 0**.
- history 조립부 4경로가 assistant 메시지마다 `_load_step_meta` → `_load_steps_for_message` 로
  그 run 의 steps 를 붙여 `meta.steps` 로 내려보낸다.
- 프런트 `renderMessageDetails` 가 `meta.steps` 로 접이식 "실행 단계"·"쿼리 결과" 를 그린다.

즉 빠져 있던 것은 데이터가 아니라 **앵커가 될 메시지 1건**이었다. 별도 저장·별도 렌더 경로를
만들면 같은 사실의 두 번째 사본이 생겨 어긋날 표면만 늘어난다.

### 판단 5 — 재로드를 «유한 3회» 로 묶은 근거

보존분은 agent 루프가 다음 체크포인트에 도달한 뒤 쓰인다(진행 중 LLM 호출이 끝나야 하므로 수 초~
수십 초). 중단은 같은 turn 에 진행 폴링을 멈추므로 자동 갱신 트리거가 없다 — 다시 읽어 주지
않으면 "대화에 남습니다" 안내가 거짓말이 된다(사용자가 직접 새로고침해야 보인다).

무한 폴링은 배제했다. 이 저장소는 두 엔드포인트가 갈릴 때 재로드가 0ms 순환에 빠져 화면을 매 회
맨 아래로 끌어내린 마찰을 이미 겪었다(bridge-progress-scroll-loop). 그래서 **정해진 3회
(1.5s·4s·10s)** 만 읽고, ① 보존분 도착 ② 대화 이동 ③ 새 요청 시작 중 하나면 즉시 물러난다.
`preserveScroll: true` 로 읽던 위치도 지킨다(브리지 취소 경로가 이미 쓰는 인자).

### 미커버 (의도적)

- **브리지(개인 AI) 축**: 러너가 최종 답변만 제출하므로 웹에 부분 추론이 존재하지 않는다. 중단 시
  대기 말풍선을 취소 안내로 바꾸는 현행 동작(`_mark_bridge_placeholders_canceled`)이 이미 "화면에
  남긴다" 를 충족한다. 보존할 중간 산출물이 없는 것이 구조적 사실이다.
- **재개(이어서 진행) 버튼**: 사용자 결정 3 — 별도 cycle. 재개 지점 정의·중복 실행 방지·브리지
  축 정합이 얽혀 위험도가 다르다.
- **삭제 요청과의 상호작용**: `pending_delete` 면 보존을 건너뛴다(기존 가드 그대로) — 삭제 대상
  대화에 메시지를 남기면 곧 지워질 행을 쓰는 것이고, 삭제 의사가 보존보다 강하다.

## REV-20260831T144500-conv-last-activity-updatedat [SKIPPED:upstream-tool-carveout] — 활동 시각 전진 지점과 표시 축 선택

- **Trigger**: `Code change` (backend write path + 목록 payload). §18.8 dispatch 표 매칭 축 =
  backend·qa. UI 키워드("표시")가 요청문에 있으나 **프론트 코드 변경 0**(표시식 무변경)이라
  ux/design 축은 해당하지 않는다.
- **채널(§18.8.2)**: 본 세션의 상위 지시가 subagent 호출을 금지해(`Do not call the AgentTool
  unless the user requested it`) panel 미호출 — 선례 REV-20260812T203000 과 동일 carve-out.
  대체 채널 = ① 라이브 PG 전수 실측(재현·범위 확정) ② 신규 테스트 2종 20 PASS ③ **뮤테이션
  역검증 3종 KILL** ④ 호출 경로 전수 추적(아래).
- **승인 근거(§12.2)**: `FIRST_REQUEST.md` `deploy_scope: included` — cycle-final 후 배포까지
  사전 승인 범위. 첫 배포 직전 1줄 표면화 이행 예정. 위험도 **Minor**(§12.3 — 스키마·마이그레이션·
  RBAC·엔드포인트·프론트 0, 비파괴·가역).

### 판단 1 — 전진 지점을 «표시 store 쓰기» 로 잡은 근거

후보 3개를 비교했다.

| 후보 | 문제 |
|---|---|
| `save_core_message`(회수 store) | tool turn 까지 담아 한 run 에 수십 건 → 행 UPDATE 가 그만큼 늘고, **화면에 없는 활동**이 "최근 갱신" 을 밀어 올려 사용자가 읽는 값의 의미가 흐려진다 |
| PG 트리거 | 관례상 명시 코드를 쓰는 저장소이고, 두 store 중 어느 쪽을 축으로 삼을지의 **판단이 스키마에 숨는다** |
| **표시 store 쓰기**(채택) | 화면에 뜨는 단위(질문·답변·안내)와 "최근 갱신" 의 의미가 겹치고, `internal` 필터가 호출측에서 이미 걸러진다 |

**호출 경로 전수 확인** — 사용자 가시 turn 이 모두 이 choke-point 를 통과하는지 직접 추적했다:
서버 LLM(`agent_core._mirror_message` — user 7982 · assistant 9102/9393/9435/9473/9487) ·
브리지 질문·대기 안내(`conversations.py` 586/621) · 브리지 답변 전달(`ai_tools.py` 1393) ·
그룹 사람-채팅 미러(`_conv_store._save_group_chat_message_pg`). 누락 0.
MySQL 백엔드는 `save_memory_message` 가 2026-05-27 cutover 로 PG 전용이라 대칭 대상이 없다.

### 판단 2 — UPSERT 재사용을 거부한 이유 (유령 대화)

`_PG_UPSERT_CONVERSATION` 은 행이 없으면 **INSERT** 하고 COALESCE 로 topic·owner·product 를
덮는다. 활동 시각 전진만 필요한 자리에서 쓰면 topic 없는 대화 행이 생긴다. 별도 `UPDATE`(있는
행만)를 새로 두었고, 테스트가 SQL 상수에 다른 컬럼이 섞이지 않는지도 단정한다.

### 판단 3 — fail-soft 로 둔 이유 (저장 성공한 turn 을 실패로 만들지 않는다)

브리지 경로는 표시 store 저장 실패를 **요청 취소**로 읽어 적재된 task 를 지운다
(`conversations.py` `_fail("사용자 메시지를 대화에 저장하지 못해 요청을 취소했다")`). touch 는
표시·정렬용 파생값이므로 예외를 올리면 안 된다 — 흡수 + WARN. autocommit 이라 메시지 INSERT 는
이미 별개 커밋으로 확정된 상태다.

### 판단 4 — 표시 축을 «우선순위» 가 아니라 «max» 로 한 이유

프런트 표시식은 `effective || last_activity_at` 이라 **앞 값이 있으면 뒤를 보지 않는다**. KV 축은
서버 LLM run 이 있었던 대화만 채워지므로:

- KV 단독 → 브리지 경로에서 필드가 비어 종전 폴백으로 돌아간다(수정 전 상태).
- KV 우선 → **서버 LLM 으로 시작해 브리지로 이어간 대화**에서 KV 가 첫 run 시각에 멈춘 채 남아
  같은 결함이 되살아난다. 이 경로가 이번 결함의 가장 그럴듯한 재발 형태라 테스트로 못박았다
  (`test_later_axis_wins_when_row_is_newer`).
- 행 단독 → 진행 중 run 의 step 시각이 행 UPDATE 보다 앞서 가는 AC-0631 개선을 되돌린다
  (`test_later_axis_wins_when_kv_is_newer`).

### 판단 5 — tz 미지 값을 비교에서 뺀 이유

MySQL 경로 `updated_at` 은 naive DATETIME 이다. UTC 로 읽으면 KST 환경에서 **9시간 미래**가 되어
max 를 영구 점거하고, 그때 사용자는 미래 시각을 본다 — AC-0633·AC-0311 이 이미 봉인한 입구의
재발이다. tz 를 아는 값만 비교하고, 그 결과가 없으면 필드를 비워 종전 폴백에 맡긴다.

### 자체 검토에서 나온 지적과 처리

1. **[자체] 반환 id 소실 위험** — touch 를 `with conn.cursor()` 블록 안에 두면 `fetchone()` 결과를
   덮어쓸 수 있었다. INSERT 결과를 먼저 `new_id` 로 확정한 뒤 블록을 닫고 touch 한다. 테스트가
   반환 id 를 단정한다(`assert new_id == 4242`).
2. **[자체] 기존 테스트 3건 파손** — `test_message_branching.py` 가 실행 SQL **목록 전체**를 동등
   비교해 부수 문장 추가마다 깨진다. 그 절의 계약("어느 INSERT 를 타는가")을 유지하며 INSERT 로
   좁혀 단정하고, touch 동반은 **전용 테스트를 새로 추가**해 커버리지를 잃지 않게 했다 — 단언을
   느슨하게만 만들고 끝내면 다음 변경이 touch 를 조용히 잃는다.
3. **[자체] 표시 축 수정이 2경로 중 1곳만이면 백엔드 전환 시 부활** — 구조 단언으로 2곳 모두
   헬퍼를 통과하는지 + raw `_iso_or_empty(last_active)` 잔존 0 을 검사한다.
4. **[미해소·의도] 기존 19건은 코드만으로 교정되지 않는다** — 새 메시지가 오면 자연 전진하지만
   사용자가 지목한 대화의 화면은 그때까지 그대로다. 라이브 백필을 별도 단계로 분리해 표면화한다
   (단조 전진 UPDATE — 마지막 메시지 시각으로, `GREATEST` 로 되돌림 방향 차단).

### 미검증 (정직 표기)

- **라이브 부제 실측**: 배포 후 실제 화면에서 "최근 갱신" 이 마지막 메시지 시각으로 뜨는지는
  배포·백필 이후 확인 대상. 프론트 자산 변경이 없어 `visual_verification_scope` check #13 의
  hard gate 대상은 아니다(웹 자산 diff 0).
- **동시 write 경합**: touch 는 단일 행 UPDATE 이고 값이 `now()` 라 순서에 관계없이 최신이 남는다 —
  별도 잠금 검토 안 함.
- **행 UPDATE 증가분 계측**: turn 당 2~3회(질문·답변·안내) 추가. 단일 행 PK UPDATE 라 무시 가능한
  규모로 판단했고 실측하지 않았다.

## REV-20260812T220000-attach-md-render-post [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록 (doc-only)
- 대상 diff: `feature-0003/docs/{TASK,MODIFY,REPORT}.md` + `docs/test-runs.d/*.md` — **코드 변경 0**.
- §18.8 dispatch 표 1행(비정책 doc-only) → panel SKIP. 실측은 PB-0008 실 Windows Chrome 으로 수행.
- 결론: 배포본 도달 축 종결. 미실측 2건은 사유와 함께 명시했고 완료로 오인 보고하지 않는다.

## REV-20260812T203000-attach-md-render [CODEX:attach-md-render] — 요청 재해석 + 신규 렌더 표면의 보안 판단

- **Trigger**: `UI/screen/layout keyword matched` (§18.8 ux·design) + `Code change` (frontend).
- **채널(§18.8.2)**: 세션의 상위 우선순위 도구 제약 하에서 제약 없는 채널 우선 — `codex` 적대 리뷰
  + PB-0008 실측 + 기계적 CSS 구조 점검. subagent panel 미호출(상위 지시 carve-out).
  ux/design 축은 "렌더 결과가 문서로 읽히는가" 이며 실 Windows Chrome computed·캡처로 직접 실측.
- **가장 중요한 판단 — 무엇이 요청이었나**: 선행 cycle 은 "포맷을 내부적으로 처리" 를 구문
  하이라이트로 읽었다. 사용자가 "잘못 구현되었다" 고 지적한 지점이 정확히 그것이다. 재해석 후에도
  **선행 작업을 되돌리지 않은** 이유: 원문 보기(토글 off)와 **변경이 있는 diff** 는 줄 대조가
  목적이라 렌더하면 기능 자체가 사라진다. 두 기능은 대체가 아니라 **같은 화면의 두 모드**이며,
  그래서 렌더 토글은 diff 화면에서 노출되지 않는다(하네스 G5/G6 가 그 경계를 잠근다).
- **보안 — 이 cycle 의 실질 리스크**: 첨부 본문을 HTML 로 렌더하는 것은 **신규 표면**이다.
  말풍선과 같은 sanitize 를 거치므로 스크립트 실행 축은 닫히지만, **원격 리소스 fetch** 는 닫히지
  않는다 — DOMPurify 는 `<img src=remote>` 를 정상 태그로 통과시키고, 로드 자체가 열람 신호다.
  그룹 대화에서 첨부는 멤버 전원이 열므로 업로더가 멤버 전원의 IP·열람 시각을 수집할 수 있다.
  응답 헤더를 **실제로 조회**한 결과 CSP 는 `report-only` 라 브라우저가 차단하지 않는다 — 이름만
  보고 "CSP 가 있으니 막힌다" 로 넘어갔다면 오판이었다(§16.7 G7-a: 구성 주장은 실 resolve).
  → sanitize **이후** DOM 하드닝으로 직접 중립화하고, 차단 사실을 **숨기지 않고** URL 을 텍스트로
  노출 + 건수 배너. 칩 텍스트는 `textContent` 로만 넣어 하드닝이 새 XSS 경로가 되지 않게 했다.
- **대안과 불채택 근거**:
  - *렌더 전용(토글 없음)*: 원문 확인 수단이 사라진다. 첨부는 계약 문서일 수 있어 **바이트 그대로**
    를 봐야 하는 상황이 있다 → 토글 유지(기본은 요청대로 렌더).
  - *별도 마크다운 파이프라인 신설*: 말풍선과 갈라진다. 같은 `.md` 가 대화에 인용될 때와 첨부로
    열릴 때 다르게 보이면 그 자체가 결함 → `markdownToHtml` 재사용.
  - *원격 이미지 허용(말풍선과 동일)*: 말풍선은 LLM 산출물이고 첨부는 **임의 업로드**다. 같은
    파이프라인을 쓰되 입력의 적대성이 다르므로 하드닝만 첨부 쪽에 얹었다.
  - *mermaid 비활성*: 일관성 손실 대비 이득이 불명확. `securityLevel:'strict'` 단일 소스를 그대로
    쓰되 이번 표본에 mermaid 가 없어 **미실측**임을 TEST fragment 에 명시.
- **리스크**: 렌더 실패 시 빈 화면이 될 위험이 있었으나 원문 표 폴백 + 사유 배너로 닫았다(F축).
  롤백은 토글을 끄면 종전 동작과 동일하고, 코드 롤백도 `opts.md` 분기 제거로 충분.
- **적대 리뷰가 6라운드에 걸쳐 [P1] 7건을 냈고 전건이 실제 결함이었다.** 특히 두 건은 **이 기능의
  목적 자체를 무효화**하고 있었다: ② 라이브 DOM 선파싱(브라우저는 파싱 시점에 요청을 시작하므로
  최종 DOM 에서 지워도 비콘은 나간 뒤) ④ mermaid 후처리가 하드닝 **이후** SVG 를 주입해
  `themeCSS` 외부 `url()` 로 두 방어선을 모두 우회. 첫 구현은 하네스 66건과 PB-0008 을 통과한
  상태였다 — **통과가 안전을 뜻하지 않는다**는 실증이며, 방어를 sanitize *이후* DOM 정리로 설계한
  것이 근본 착오였다(순서가 방어의 본체다).
- **뮤테이션이 살아남아 검사를 고친 것 3건** — 죽은 방어선(프로필이 입력을 먼저 지워 2차 방어선
  미실행) · vacuous 전제(하네스가 `enhanceMermaidBlocks` 미로드라 mermaid 축이 대상 없음) ·
  좁은 구조 검사(특정 문자열만 배제해 `container.innerHTML` 변형 통과). 뮤테이션 생존은 코드가
  아니라 **검사의 결함** 신호로 다뤘다.
- **PB-0008 증거가 한 번 무효였다(기록)**: 초판 시나리오가 하드닝만 정본에서 잘라 오고 렌더는
  손으로 `md.innerHTML = markdownToHtml(...)` 로 다시 써서, **고치기 전 구현을 촬영**하고 있었다.
  정본 함수를 그대로 잘라 실행하도록 재작성 후 재촬영했다 — 검증 코드를 손으로 재현하면 그것은
  더 이상 그 구현의 증거가 아니다.
- **기능 회귀 1건 동반 적발**: `input` 금지가 GFM 작업 목록의 체크 상태를 지워 `- [x]`/`- [ ]` 가
  같아 보였다. 보안 조치가 **요청받은 기능**을 깎은 사례라, 상호작용 없는 글리프로 상태만 살렸다.
- **가장 값진 지적은 마지막이었다(4R)**: "같은 출처면 안전" 이라는 내 전제가 틀렸다 — 이 앱에는
  GET 만으로 상태가 움직이는 인증 엔드포인트가 있어(`oauth_as.py` authorize) 같은 출처 이미지는
  정보 유출이 아니라 **열람자 권한의 행사**가 된다. 미디어 로드를 `data:image/` 로만 좁혀 닫았고,
  잃는 것은 없다(첨부가 참조하는 이미지는 어차피 우리 서버에 없다).
- **5R 은 4R 의 절반만 고쳤음을 드러냈다**: 같은 출처 **이미지**(자동 GET)를 막고 나서도
  같은 출처 **링크**(클릭 GET)는 열려 있었다. 위험의 축은 "자동이냐 수동이냐" 가 아니라
  **"열람자 권한이 쓰이느냐"** 였고, 그 축으로 다시 보니 링크가 남아 있었다 — 부분 수정이
  전체 수정처럼 보이던 사례다(§16.7 G8 적용면 전수감사와 같은 성격).
- **6R 은 방어의 축 자체를 한 번 더 넓혔다**: `style` 속성을 막아도 **클래스**로 같은 일이 된다 —
  앱이 이미 가진 CSS 를 빌리면 되기 때문이다. 사용자 클래스를 걸러내되 렌더러가 만든 클래스는
  남겨야 해서(코드블록 구문색·mermaid 강등이 그것에 의존) allowlist 로 갈랐다.
- **검증**: 신규 102 PASS(실 vendor) · 뮤테이션 전건 KILL · 형제 4종 회귀 0 ·
  PB-0008 PASS — 이제 시나리오가 **기대값 대조를 eval 안에서 수행하고 어긋나면 throw** 한다
  (종전엔 컨테이너 가시성만 봐서 측정 실패도 PASS 할 수 있었다, codex 4R [P2]).
- **캡처 정직성**: 초판 PB-0008 캡처가 `page-fade-in` 도중 촬영돼 **판독 불가**였다. 흐린 캡처를
  근거로 PASS 하지 않고 애니메이션 종료 대기를 시나리오에 넣어 재촬영했다(§16.6 다운그레이드 금지).

## REV-20260812T193000-attach-md-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록 (doc-only)
- **대상 diff**: `unit/feature-0003-agent-web-ui/docs/{TASK,REPORT}.md` + `docs/test-runs.d/*.md` — **코드 변경 0**.
- §18.8 dispatch 표 1행(비정책 doc-only) → panel SKIP. 실측 자체는 PB-0008 실 Windows
  Chrome/150 으로 수행했고 근거는 fragment 에 있다.
- **결론**: 선행 cycle 이 선언한 잔여 2건 종결(배포본 probe 뒤집힘 · 배포본 모듈 직접 렌더).
  남은 1건(라이브 `.md` 첨부를 실 계정으로 여는 조합 대조)은 타 사용자 데이터 접근이라
  수행하지 않고 **미실측으로 명시**했다 — 완료로 오인 보고하지 않는다(§16.3 정직성).

## REV-20260812T183000-attach-md-highlight [CODEX:attach-md-highlight] — GATE PASS (P1 0건 · P2 3건 전건 반영)

- **Trigger**: `UI/screen/layout keyword matched` (§18.8 dispatch 표 3행 → ux·design) +
  `Code change` (frontend). 변경 = `static/code-highlight.js` 토크나이저 신규 + CSS **주석만** +
  하네스/시나리오. 백엔드·API·RBAC·스키마 **0**.
- **채널 선택 근거 (§18.8.2)**: 본 세션에는 상위 우선순위 도구 제약("요청 없이 Agent tool 호출
  금지")이 걸려 있다. §18.8.2 의 해소 순서대로 **제약 없는 채널을 먼저** 썼다 —
  `codex exec -s read-only`(§18.8.1 항목 2, check #9 accepted) + 기계적 cross-ref 점검 +
  PB-0008 실측. 검증 착수 자체는 confirm 대상이 아니므로 되묻지 않고 수행했다(§18.8.2).
  subagent panel(ux/design)은 호출하지 않았다 — 상위 지시 carve-out. **미검증으로 남은 도메인은
  없다**: 이 변경의 ux/design 축은 "색이 실제로 어떻게 보이는가" 이며 PB-0008 실 Windows Chrome
  computed style + 판독가능 확대 캡처로 **직접 실측**했다(bundle-only reviewer 보다 강한 증거).
- **[P1] 0건 → GATE PASS.** [P2] 3건, 전건 반영:
  1. **연속 `|` span 폭증** — `\|+` 로 한 토큰 병합. 실 표는 파이프가 인접하지 않아 화면 무변경,
     병리 입력 4,000 토큰 → 1 토큰(0.83ms → 0.058ms). 회귀 잠금 `B47d`·`I3b`.
  2. **표 정렬행 판정 과대** — **실제 오색 결함**이었다. 초판은 "`|`·`-` 포함 + 문자집합" 만 봐서
     리스트 항목 `- |` 이 **줄 전체 회색**이 됐다. 셀 문법(`:?-+:?`) 확인 + "선두 `|` 없으면 2셀
     이상" 으로 좁혔다. 회귀 잠금 `B47b`·`B47c` + PB-0008 캡처 L27 실물 확인.
  3. **시나리오 fail-open** — 배포 모듈 대신 사본을 주입하므로 배포본 로드 실패에도 PASS 한다는
     지적. 시나리오에 **배포본 실물 probe** step 을 추가해 `has_md`/`langs` 를 기록하게 했고,
     배포 전 baseline(`has_md:false`, `langs:sql,json,yaml,xml,csv,tsv`)을 실측해 두었다 —
     POST-DEPLOY 재실행이 `true` 로 뒤집히는지가 그 축의 종결이다. 배선 축 자체는 jsdom
     `H13/H14` 가 **실 모듈 + 실 `attach-diff.js` 렌더 경로**로 이미 커버한다.
- **판단 근거 (설계 결정 3건)**:
  - **새 팔레트 변수 0** — 기존 9종 재사용. 변수를 늘리면 대비 계산 하네스(G1/G2)의 검증면이
    함께 넓어지는데, markdown 은 기존 토큰 의미(구조/리터럴/이름표)로 전부 표현 가능하므로
    넓힐 이유가 없다. AC-AVD-24(WCAG AA)·AC-AVD-27(적용) 계약이 그대로 상속된다.
  - **`_강조_` 의도적 미지원** — 이 화면에 오는 `.md` 는 DB·SQL 문서가 다수라 `snake_case`·
    `__dunder__` 가 흔하다. 인식하면 **없는 강조**를 만든다. 모듈 선언 "무색이 오색보다 낫다" 를
    따랐고, `B51` 이 그 전제를 negative 로 단정한다.
  - **fence 내부 markdown 판정 수용** — 라인 독립 원칙(맥락 축약 뷰가 중간을 생략하므로 상태를
    이어붙이면 색이 통째로 어긋난다)의 **기존 절충**을 뒤집지 않았다. 대신 fence 줄 자체를 칠해
    경계를 읽히고, 한계를 모듈 헤더·FUNCTION AC-AMD-5·TEST fragment 에 명시했다.
- **리스크**: 없음(비파괴 추가). 롤백은 `LANGS.md` 한 항목 제거로 `.md` 가 종전 무색으로 복귀.
  외부 비용·보안·데이터 영향 0. 2차-효과(캐시 무효화) 없음 — fingerprint 계산 무변경.
- **검증**: 하네스 **146 PASS/0 FAIL** · 형제 3종 회귀 0(77/125/61) · PB-0008 실 Windows
  Chrome/150 PASS · pytest 무관(changeset 에 `.py` 0).

## REV-20260807T183000-gc-guide-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록 (doc-only)
- 대상 diff: `feature-0003/docs/{TASK,MODIFY,REPORT}.md` + `docs/test-runs.d/*.md` — **코드 변경 0**.
- §18.8 dispatch 표 첫 행(비정책 doc-only) → panel SKIP. 사실 정합만 자체 확인: 배포 SHA
  (`f81c5bcb`→`f60d67c5`)·PR 번호(#1190/#1191)·실측 수치(z 40 / 카드 bottom 853 < wrap top 858 /
  linesPerItem [1,1,1,1,1] / `acAfter=false`+`tipAfter=true` / 스탬프 `c2838fc68348`→`4909197d7ea4`)는
  전부 본 세션의 브라우저 실행 로그에서 그대로 옮긴 값이며 추정치가 없다.
- Timestamp: 2026-08-07T18:30:00+09:00
- Verdict: PASS
- Human Approval Needed: no

## REV-20260807T170000-gc-guide-esc-capture [SKIPPED:non-policy-doc] — 1줄 배선 수정 + 하네스 강화
- Related TASK: feature-0003-agent-web-ui (TASK-20260807T1700-gc-guide-esc-capture)
- Trigger: 선행 cycle 의 §18.8 ux·design 패널(REV-20260807T153000)이 이미 이 표면을 검증했고,
  본 변경은 그 패널이 요구한 동작(Esc 양보)을 **실제로 성립시키는 1줄 배선 수정**(버블→capture)
  + 테스트 하네스 강화다. 새 표면·새 로직·권한/데이터 변경 0 → panel SKIP (§18.8 표 첫 행 준용).
- Timestamp: 2026-08-07T17:00:00+09:00
- Verdict: PASS
- Critical issue: 없음. 다만 **선행 하네스가 vacuous pass 였다는 사실 자체가 결함**이므로,
  점수정에 그치지 않고 하네스가 **라이브 합성(경쟁 핸들러 순서)** 을 재현하도록 고쳤다
  (§16.7 G10 재발 클래스 구조 가드 정신 — 되돌림 시 6 red).
- 자체 검증: `node --check` PASS · 하네스 68/68 · 뮤테이션(capture→버블) 6 red ·
  mjs 전수 49 suite exit 0. 배포 후 PB-0008 #8 재실측이 최종 근거.
- Human Approval Needed: no

## REV-20260807T153000-gc-first-use-guide [SUBAGENT:ux] — BLOCK → 반영 후 해소
- Related TASK: feature-0003-agent-web-ui (TASK-20260807T1500-gc-first-use-guide)
- Trigger: UI/screen/layout keyword matched · 화면 (§18.8 dispatch 표 3행 → ux, design)
- Timestamp: 2026-08-07T15:30:00+09:00
- Verdict: BLOCK (반영 완료 — 아래 disposition)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260807T153000-ux.md
- Critical issue: 안내가 뜬 직후 첫 타건이 카드를 **영구 소진**해, 한 줄도 못 읽은 신규
  참여자가 복구 경로 없이 온보딩을 잃는다(B1). + 발화 불가 계정에 거짓 안내로 1회 기회 소비(B2).
- Disposition: B1·B2·M1·M2·M3 수용(닫기≠소진 분리 · `conversation.ask`/`blocked` 게이트 ·
  `aria-live` · Esc 오버레이 양보 · 첨부 문구 F1 정합), m2·m3·m4·m1 수용(앵커·라벨·문구·z-index),
  M4·NIT 은 근거 명시 후 설계 유지. 반영분은 하네스 61 PASS + **뮤테이션 5/5 KILLED** 로 고정.
- Human Approval Needed: no

## REV-20260807T153000-gc-first-use-guide [SUBAGENT:design] — BLOCK → 반영 후 해소
- Related TASK: feature-0003-agent-web-ui (TASK-20260807T1500-gc-first-use-guide)
- Trigger: UI/layout keyword matched · 레이아웃 (§18.8 dispatch 표 3행 → ux, design)
- Timestamp: 2026-08-07T15:30:00+09:00
- Verdict: BLOCK (반영 완료 — 아래 disposition)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260807T153000-design.md
- Critical issue: `z-index:60` 이 같은 자리를 쓰는 `#mentionAutocomplete`(50)를 가려,
  안내가 시킨 `@` 입력의 결과인 멤버 목록이 안내에 덮인다.
- Disposition: z-index 40(멘션 AC·드롭 오버레이 아래) · caret 을 `calc(100% + 6px)` 로
  wrap 밖에 세워 배너 잠식 제거 · 터치 타깃 · 컨테이너 기준 max-width · 모션 anim-pref 규약 ·
  제목 13px 수용. **다크 모드 지적은 실측 후 반대로 조치** — `base.css` 에
  `prefers-color-scheme` 0개(라이트 단일 테마)라 다크 override 는 흰 카드 위 연파랑(≈1.8:1)을
  만든다 → 넣지 않고 토큰화 + 대비를 계산해 본문 9.15:1 확보(제목 15.38 · 닫기 5.17).
  줄바꿈 nowrap 은 클리핑을 낳아 미반영, 렌더 줄 수는 PB-0008 몫으로 정직 표기.
- Human Approval Needed: no

## REV-20260804T070000-prompt-autogen-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 실증 기록 (doc-only)
- 대상 diff: `feature-0003/docs/{TASK,REPORT}.md` · `feature-0002/docs/TASK.md` — **코드 변경 0**.
  선행 2 cycle 의 잔여 체크박스("배포 후 라이브 실증 대기")가 실증 완료로 stale 해진 것을 종결 표기로
  갱신하고(§5.6 staleness), 2단 배포 경과를 REPORT 에 기록.
- §18.8 dispatch 표 첫 행(비정책 doc-only) → panel SKIP. 사실 정합만 자체 확인: 배포 SHA
  (`c4701a17`→`fba8ee9f`)·PR 번호(#1135/#1138)·실증 수치(summary 0→1행, `meta.summary_count` 0→1,
  topic 잡음 0/40)는 모두 본 세션의 실행 로그에서 그대로 옮긴 값이며 추정치가 없다.

## REV-20260804T045449-prompt-autogen-wiring [CODEX:prompt-autogen-wiring] — SHIP-WITH-FIXES (P1 1/P2 3 → 흡수 3·반증 1) + 자체 보안 점검 (TASK-20260804T0454)
- **Trigger**: `schema/query/DELETE` keyword matched (backend, qa) + `performance/cost` keyword matched
  (backend, qa) — code change, §18.8 dispatch 표.
- **채널 선택(§18.8.2)**: 1순위 제약 없는 채널 `codex review --uncommitted` 를 시도했으나 **외부 DNS
  단절**로 실패(`failed to lookup address information: wss://chatgpt.com/...`, 재시도 5/5 소진 — 호스트
  `getent hosts chatgpt.com`·`pypi.org` 동시 실패로 환경 조건 확인). 세션에 "요청 없이 Agent tool 호출
  금지" 제약이 있어 subagent panel 은 사용자 확인 대상으로 표면화하고, 그 사이 **아래 자체 보안·정합
  점검을 인라인 수행**했다(자체 SKIP 아님 — 채널 부재를 검증 생략으로 격상하지 않는다).

### 1. 데이터 노출 경계 — 요약 축 활성화의 실제 효과 (가장 중요한 검토점)
- 본 변경의 핵심은 `agent_runtime.summary` 를 **비어 있던 상태에서 실제로 채우는 것**이다. 그 테이블은
  역할 프롬프트 자동작성에서 `owner_account_id IN (그 역할 소속 계정)` 으로 조회된다 — 즉 생성 컨텍스트에
  **타 사용자 대화 요약(최대 600자 × 5건)** 이 들어간다.
- 이는 신규 노출 경로가 아니라 **TASK-20260625 설계가 이미 승인한 경로**다("원문 메시지가 아닌 집계
  메타(제목·요약)만 사용" — 제품 경로와 동일 privacy house style). 다만 writer 단절 때문에 지금까지
  **비활성이었고, 본 변경이 그것을 실제로 켠다**. 이 사실을 은폐하지 않고 명시한다.
- **인가 실측**: `system_prompt.manage.role.any` 보유 역할은 현재 `admin`(RoleId 3) **단 하나**이며
  그 역할은 `conversation.read.any` + `conversation.list.any` 도 보유한다. 따라서 **오늘 구성에서는
  기존 권한 범위를 넘는 새 열람 경로가 생기지 않는다**(권한 경계 교차 없음).
- **잔여 위험(구조적, 선재)**: 운영자가 향후 `system_prompt.manage.role.any` 를 `conversation.read.any`
  없이 부여하면, 그 보유자는 열람 권한 없는 대화의 요약을 프롬프트 생성 컨텍스트로 보게 된다. 단 이
  비대칭은 **요약 축만의 문제가 아니다** — 같은 게이트로 이미 라이브인 topic(대화 제목) 축이 동일한
  cross-user 노출을 갖는다. 따라서 요약만 별도 게이팅하면 일관성 없는 반쪽 방어가 된다. 본 cycle 은
  사용자 요청 범위(끊긴 배선 복구) 밖의 인가 재설계를 하지 않고 **REPORT §8 개선 제안으로 등재**한다
  (§8.1 — 제안은 기록만, 사용자 지시 없이 실행 안 함).
- account 스코프는 `account_ids=[본인]` 으로 self-scope, product 스코프는 `product.update` 게이트 +
  제품 대화 한정 — 둘 다 변경 없음. `account_ids=[]` 단락(cross-scope 누출 가드)도 그대로.

### 2. 주입·SQL
- 신규 SQL 은 `DELETE FROM WebSystemPrompts WHERE RoleId = %s` 1건 — 파라미터 바인딩 + `int()` 캐스팅,
  경로상 `role_id <= 0` 은 상위에서 400 차단. 문자열 보간 없음.
- `_normalize_signal_topics` 는 순수 문자열 처리(조회 결과 → 표시 문자열)로 실행 경계에 닿지 않는다.
  LLM 프롬프트에 사용자 유래 텍스트가 들어가는 것 자체는 종전과 동일(신규 표면 아님).
- 조회 창 확대(`limit`→`limit*3`, 제품 50→150)는 파라미터 바인딩된 LIMIT 이며 상한이 코드 상수다.

### 3. 로깅
- 신규 `logging.warning` 2곳은 label·model·max_tokens·log_ctx(`role_id=N`/`product_id=N`)·예외 문자열만
  기록한다. **프롬프트 본문·생성 결과·자격증명 미기록**. 스트리밍 쪽은 누적 문자 수만 남긴다(내용 아님).

### 4. 예외 안전·순환 import
- `refresh_conversation_summary` 는 전체를 try 로 감싸 bool 반환(fail-open). 호출부
  `run_post_answer_curation` 도 자체 try/except 로 흡수 — 답변 경로가 요약 실패로 막히지 않는다
  (회귀 테스트 `test_post_answer_curation_survives_summary_failure` 로 고정).
- `_summary_deps()` 는 함수-로컬 import. `memory.py`·`render.py`·`utils.py` 어느 것도 `modules.llm` 을
  import 하지 않음을 확인 — 순환 없음. 모듈 로드 시점 부작용 없음.
- **부수 발견(정직 표기)**: `_set_run_deadline()` 은 저장소 전체에서 호출자가 0 이라
  `CURRENT_RUN_DEADLINE_TS` 가 항상 0.0 → `_near_run_deadline()` 은 항상 False 다. 즉 aux-skip 예산
  가드는 현재 무동작이다. 본 cycle 은 이를 **건드리지 않는다**(요약 배선과 직교, fail-open 방향이라
  안전). REPORT §8 등재.

### 5. 비용·지연 회귀
- 추가 LLM 호출은 **ask 당 1회**(haiku, `AGENT_SUMMARY_MODEL`), 답변 확정 + (worker 경로) job terminal
  전이 **이후** 실행 — 사용자 대기 경로 밖. 7일 실측 기준 `agent` task 392회 대비 동급 증분이며 같은
  기간 `node_analysis` 4,214회의 10% 미만. 게이트(`AGENT_SUMMARY_REFRESH=0`)로 즉시 전면 차단 가능.
- 조회 창 3배 확대는 인덱스된 `ORDER BY updated_at DESC LIMIT n` 이며 상한 150 — 무시 가능.

### 6. over-filtering 반증 (정제기가 실제 신호를 삼키지 않는가)
- placeholder·인사말 판정은 **정규화 후 완전일치**만 — "안녕하세요, 접속 로그 좀 봐주세요" 는 보존됨을
  테스트로 고정. 길이 게이트는 초안 4자에서 실패를 확인하고 **2자로 낮춰** 짧은 한국어 제목("매출",
  "접속 로그")을 보존하도록 정정했다(`test_normalize_keeps_short_korean_topics`).
- `limit=0` 에서 append-후-검사 루프가 1건을 흘리던 엣지를 자체 발견·수정(가드 + 회귀 테스트).

### 7. [CODEX:prompt-autogen-wiring] 외부 채널 적대 리뷰 (DNS 복구 후 재실행 성공) — P1 1 / P2 3
- **[P1] `refresh_conversation_summary` 가 `AGENT_SUMMARY_REFRESH_EVERY` 와 `_near_run_deadline()` 을
  둘 다 우회한다 → 부분 흡수 + 부분 반증.**
  - `AGENT_SUMMARY_REFRESH_EVERY` 는 **스텝 인덱스 샘플러**다(`step_index % EVERY`). 본 호출은 ask 당
    1회이고 step_index 개념이 없어 적용 대상이 아니다 — 반증. docstring 에 명시.
  - `_near_run_deadline()` 은 **의도적으로 넣지 않는다** — 본 함수는 정의상 답변이 끝난 뒤 실행돼
    항상 run 예산 끝에 붙어 있다. 가드를 넣으면 누군가 `_set_run_deadline()` 을 실제로 배선하는 순간
    (현재 호출자 0 이라 상시 False) 요약 쓰기가 **다시 통째로 죽는다** — 이 cycle 이 고치는 결함의
    재발이다. 근거를 docstring 에 남겼다.
  - **다만 지연 주장은 정정했다(흡수)**: "사용자 대기 +0" 은 **worker 경로에만** 참이다. in-process
    경로는 큐레이션이 terminal **전**에 인라인으로 돌므로(§18.8 backend B2 의 의도적 결정) 기존 LLM
    3건에 1건이 더해진다. 운영은 ask-worker 가동(worker 경로)이라 실사용 영향은 +0 이지만, 경로별
    차이를 은폐하지 않고 코드·문서에 분리 표기했다.
- **[P2] 중복 판정은 원문 전체, 출력은 120자 절단 → 앞 120자가 같은 긴 제목이 동일 문자열로 중복 출력
  → 흡수.** dedupe 키를 **출력될 문자열** 기준으로 전환. 회귀 테스트
  `test_normalize_dedupes_on_truncated_display` 추가 + **역검증**(구 키로 되돌리면 FAIL 확인).
- **[P2] 배선 테스트가 실제 완료 경로가 훅을 부르는지는 검증 안 함 → 흡수.** AST 기반
  `test_production_answer_paths_invoke_curation_hook` 추가 — `agent_core`(in-process 분기)·
  `modules/ask.py`(worker terminal 후)의 `run_post_answer_curation` 호출식과 훅 안의
  `_refresh_conversation_summary` 호출식을 세어 "함수는 남고 호출만 사라진" 상태를 실패시킨다.
  **역검증**: 호출 1줄을 주석 처리하면 2개 테스트 FAIL 확인.
- **[P2] `_refresh_summary_after_step` 이 게이트 확인 전에 `_summary_deps()` 실행 → 흡수.** 게이트를
  앞으로 이동 — 기능이 꺼져 있으면 지연 import 자체를 하지 않는다.

### Verdict
- BLOCKER 0. 신규 인가 우회·주입·비밀 노출 없음. 잔여 위험 1건(요약/topic 축의 cross-user 노출이
  `system_prompt.manage.role.any` 단독 보유자에게 열릴 수 있는 **선재적** 비대칭)은 오늘 구성에서
  미발현이며 REPORT §8 로 등재.
- **채널 결과(정직 표기)**: ① codex 외부 채널 **재실행 성공**(위 §7 — P1 1/P2 3, 흡수 3·반증 1)
  ② §18.8 subagent panel 은 세션 도구 제약으로 미호출(codex 가 dispatch 도메인 backend/qa 를 덮음)
  ③ `make test` 표준 호출 전량 회귀 **exit 0 PASS**(초기 1회 관측된
  `test_shutdown_finalizer_marks_this_process_processing` 실패는 비-표준 `COMPOSE_PROJECT_NAME=repo`
  호출에서만 나타났고, 표준 재실행·파일 단독·feature-0003 전량·3스위트 단일 프로세스 어디서도
  재현되지 않음 — flake 로 판정)(1차 실행에서
  `test_shutdown_finalizer_marks_this_process_processing` 1건 FAIL 했으나, 동일 격리 env 로 3스위트
  단일 프로세스 재현 시 **0 실패** — 파일 단독·feature-0003 전량·3스위트 전량 모두 통과. 본 변경은
  종료 finalizer 및 그 의존(`_active_ask_job_conversation_ids`·`_parse_kv_timestamp`)을 건드리지
  않는다. flake 로 판단하되 **단정하지 않고** 재실행으로 확인 예정).

## REV-20260730T162000-test-isolation-hardening [SKIPPED:user-directive] — 테스트→라이브 오염 재발의 남은 층 차단 (TASK-20260730T1620)
- 대상 diff: `Makefile`(전용 compose 프로젝트) · `conftest.py`(DB_PORT 격리 + fail-loud) ·
  `bin/check-test-contamination.sh`(신설) + 문서. **제품 코드 변경 0**.
- **panel SKIP 근거**: 선행 cycle(REV-20260729T141200)에서 사용자가 "패널 생략하고 진행" 을
  선택했고, 본 cycle 은 그 후속(같은 문제의 남은 층)이며 변경 표면도 동일 계열(테스트 인프라·
  빌드 진입점)이다. 세션의 "요청 없이 Agent tool 호출 금지" 지시도 그대로다.
- **어제 수정이 왜 부족했는지에 대한 정직한 진단**: 어제는 "테스트가 라이브에 **쓰지 못하게**"
  값으로 막았다(`DB_PORT=1`, `_connect_memory` 차단, assert 강화). 그 층은 유효했고 실측으로
  닫았지만, **그 방어가 저장소 파일에 산다는 사실 자체**를 다루지 않았다. 파일 방어는 머지 시점에
  존재하는 사본에만 적용되고 이미 분기된 worktree 에는 소급되지 않는다 — 머지 10분 뒤 재발이
  정확히 그 구멍이었다. 이번에는 그 위에 **도달성 층**(전용 compose 프로젝트)을 깔았다. 값이
  아니라 네트워크에서 끊으므로, 값 방어가 한 겹 뚫려도 오염이 성립하지 않는다.
- **DB 레벨 차단을 검토하고 폐기한 이유**: branch 사본 축을 완전히 덮는 유일한 층은 저장소
  밖(DB/인프라)이다. 그래서 MySQL 이 운영/테스트 커넥션을 구분할 수 있는지 먼저 조사했다 —
  `information_schema.PROCESSLIST` + `performance_schema.session_connect_attrs` 를 직접 조회한
  결과 양쪽 모두 `program_name=NULL`·`_client_name=libmysql`·`_pid=1` 로 **동일**했고 IP 도
  동적이라, 트리거 기반 거부는 성립하지 않는다. 계정 분리(운영 전용 자격증명 + root 쓰기 회수)는
  이론상 가능하지만 alembic·백업 경로를 함께 옮기는 대공사라 이 문제(개발 편의 사고)에 비례하지
  않는다고 판단했다. 자격증명 회전도 같은 이유로 보류했다 — 다만 **오래된 `.env` 사본을 즉시
  무력화하는 유일한 수단**이라는 점은 기록해 둔다(향후 필요 시 선택지).
- **fail-loud 를 넣은 이유(설계 의도)**: 남은 구멍은 "내가 예측한 경로" 만이 아니다. 그래서
  마지막 층을 "특정 경로 차단" 이 아니라 **"이 프로세스가 라이브 스택 안에 있는가" 라는 상태
  검사**로 두고, 참이면 테스트를 아예 시작하지 않게 했다. 미래의 미지 우회 경로도 이 검사에
  걸린다. 실측 — 라이브 프로젝트로 pytest 를 돌리면 collection 에서 중단되어 **테스트 0건 실행**.
- **probe 를 env 가 아니라 3306 리터럴로 한 이유**: 같은 블록이 위에서 `DB_PORT=1` 을 덮으므로
  env 기반 probe 는 자기가 방금 쓴 값을 읽는 동어반복이 된다. 확인하려는 명제는 "값이 막혔나"
  가 아니라 "라이브 네트워크 안인가" 이므로 운영 기본 포트를 직접 본다.
- **감지 층을 추가한 이유**: 이번 사건의 실제 피해는 오염 자체보다 **하루의 탐지 지연**이었다
  (07-29 14:33 발생 → 07-30 15:57 발견). 오염은 에러를 남기지 않고 설정 화면 숫자만 바꾸므로
  능동 조회 수단이 없으면 계속 늦게 발견된다. 스크립트는 "복구됨/오염 잔존" 을 구분해 잔존일
  때만 exit 1 한다 — 과거 이력만으로 상시 red 가 되지 않게.
- **미검증·한계(명시)**: 현존 취약 worktree 2개는 **자기 사본에 이 방어가 없다** — 본 PR 머지로
  자동 해소되지 않는다. 사용자 승인(2026-07-30) 하에 머지 후 테스트 인프라 3파일을 그 사본에
  복사한다. 그 이후 새로 분기되는 worktree 는 main 에서 파생하므로 방어를 상속한다.
- Cross-ref: TASK-20260730T1620 / MODIFY CHG-20260730T162000 /
  test-runs.d/20260730T1620-test-isolation-hardening.md / 선행 REV-20260729T141200-test-live-db-isolation.

## REV-20260730T160500-progress-enqpre-handoff-postdeploy [SKIPPED:doc-only-postverify] — POST-DEPLOY 라이브 AFTER 대조 (TASK-20260729T2010 후속)
- 대상 diff: `docs/{TASK,REPORT}.md` + `docs/test-runs.d/20260729T201000-progress-enqpre-handoff.md`.
  **코드 변경 0** — 배포본 실측 결과 기록만.
- panel SKIP 근거: §18.8 dispatch 는 code change 를 전제한다. 원 cycle 의 리뷰는
  `REV-20260729T201000-progress-enqpre-handoff [CODEX:progress-enqpre-handoff]` 가 담당했다.
- **검증 설계가 이번엔 결정적이었던 이유**: 배포 **전에** 같은 브리지·같은 시나리오로 BEFORE 를
  먼저 확보했다(서버 steps 3→6→7 vs 프론트 0). 그래서 AFTER 는 "고쳐진 것 같다" 가 아니라
  **동일 조건 수치 대조**로 판정된다. 선행 cycle 에서 BEFORE 없이 AFTER 만 봤다가 `enqpre-…` 신호를
  놓친 것과 대비되는 개선이며, 이후 타이밍 의존 결함에는 이 순서(BEFORE 선확보)를 기본으로 한다.
- **정직 기록**: ① 큐 대기 구간(t+3s~t+10s) 상태 라벨이 '처리 중'→'시작 중' 으로 바뀌었다 —
  sentinel 을 채택하지 않으니 그 구간엔 실제 실행이 없다는 사실이 그대로 표시된다. 기능·정직성 모두
  개선이나 **사용자 가시 변화이므로 명시**한다. ② codex P1-1(그룹 동시 전송 창 foreign 오귀속)은
  라이브에서 재현하지 않았다(두 계정을 1~2초 창에 맞춰야 함) — 단위 C7·C8 이 현재 동작을 고정하고,
  근본 해결은 서버 `run_is_mine` correlation 후속 과제다.

## REV-20260729T201000-progress-enqpre-handoff [CODEX:progress-enqpre-handoff] — enqueue sentinel → 실제 run 승계 (TASK-20260729T2010)
- 대상 diff: `src/static/app.js`(sentinel 채택 규약) · `tests/verify_enqpre_run_handoff.mjs`(신설) ·
  문서 4. **백엔드·RBAC·스키마·엔드포인트 변경 0**.
- **진단 누락에 대한 정직 기록**: 선행 cycle(progress-poll-resilience)의 PB-0008 1차 관측 로그에
  이미 `runId: "enqpre-ae58dc20…"` 와 `stepText: "시작 중…"` 이 함께 찍혀 있었다. 당시 이를 "아직
  단계가 생기지 않았다" 로 읽고 넘겼는데, 실제로는 **이 결함의 직접 증거**였다. 사용자 재보고
  스크린샷(상태 '처리 중' + 단계 '시작 중…' + 경과 1분 50초)이 "폴링은 살아 있는데 steps 만 안
  온다" 를 특정해 준 뒤에야 가드를 다시 읽었다. 교훈: **관측 로그의 이상값(정체불명 prefix 를 가진
  id)을 그 자리에서 추적하지 않으면 같은 증상을 두 번 고치게 된다.**
- **선행 cycle 과의 관계**: 두 결함은 같은 증상("말풍선이 갱신되지 않고 전환-복귀로만 풀림")을
  공유하지만 **원인이 독립**이다. 선행은 *폴링 채널이 죽는* 축(3연속 실패 후 영구 포기 + 감지기
  dormant), 본 cycle 은 *폴링이 살아 있는데 응답이 버려지는* 축(sentinel 승계 오인). 선행 수정은
  유효하며(라이브 실증 완료) 철회 대상이 아니다 — 순단·배포 창에서는 여전히 그 축이 발현한다.
- **수정 방향 선택 근거**: 후보 3안 중 (A) 가드에 sentinel 예외만 추가 — 최소 변경이지만
  `progressRunId` 에 "어떤 run 도 가리키지 않는 값" 이 남아 `client_run_id` 로 서버에 전송되고
  per-run terminal marker 조회가 헛돌게 된다. (C) enqueue 시점에 실제 run_id 를 미리 발급 —
  가장 근본적이나 `ask_jobs`·`agent_core`·TASK-0241 clobber 가드의 전제를 모두 건드려 blast
  radius 가 크다. → **(B) sentinel 을 추적 id 로 채택하지 않는다** 를 채택. `progressRunId` 의
  의미가 "실제 run" 으로 유지되고, sentinel 구간에는 `client_run_id` 를 안 보내 서버가 현재 run 을
  그대로 돌려주는 자연스러운 흐름이 된다. (A)는 2중 방어로 함께 넣어 구 상태·다른 진입 경로를 덮는다.
- **그룹 foreign-run 불변식 영향 분석**: 가드의 보호 대상(다른 멤버의 실제 run 으로 내 버블이
  갈아타지 않기)은 그대로다 — 판정이 "실제 run vs 실제 run" 으로 좁아졌을 뿐이다. sentinel 구간
  (통상 1~2초)에 다른 멤버가 동시 전송하면 그 run 을 채택할 수 있으나, ① 창이 1~2초로 짧고
  ② 채택 후에도 내 run 이 KV 슬롯을 차지하면 다음 폴에서 되돌아오며 ③ terminal·`loadHistory` 가
  정리한다. 반면 수정 전 결함은 **매 요청 발생**했다 — 우선순위가 명확하다.
- **§18.8**: 세션 지시(Agent tool 금지)와 정책 충돌은 선행 cycle 에서 사용자가 `/codex review`
  대체를 선택했다. 본 cycle 은 그 결정을 승계하되, 변경이 선행 cycle 과 **같은 함수·같은 가드**
  범위이고 신규 표면(권한·엔드포인트·스키마)이 0 이라 자체 적대 검토로 갈음한다:
  - H1 *sentinel 을 안 채택하면 `client_run_id` 부재로 서버가 남의 run 을 줄 수 있다* — 위 불변식
    분석대로 창이 1~2초이고 자기 복구 경로가 3중이다.
  - H2 *`pendingBubble.runId` 를 비우면 "단계 보기"·타임아웃 배너가 깨지나* — 단계 패널은 `steps`
    배열을 쓰고, 배너는 `_extBannerState.runId`/`state.progressRunId` 를 쓴다(`pendingBubble.runId`
    미참조). sentinel 구간엔 서버가 `timeout_extension` 을 비워 보내므로 배너 대조도 무영향.
  - H3 *`_adoptRunId` 가 실제 run 을 빈 문자열로 만들 수 있나* — prefix 매칭만 하므로 `run-…`·
    UUID 형태는 그대로 통과한다(C6 이 양방향 고정).
  - H4 *서버가 prefix 를 바꾸면 조용히 깨진다* — 정적 단언으로 `ENQUEUE_SENTINEL_RUN_PREFIX` 선언을
    고정하고, 서버 계약 위치를 코드 주석에 명시했다. 서버측 상수화는 후속 과제로 남긴다(범위 밖).
- **`/codex review` 결과 — P1 2건 · P2 1건**:
  - **[P1-2 수정 완료] `ask_status` attach 경로가 sentinel 을 `run_id` 로 실었다** — 명확한 버그.
    `/api/ask_result` 는 **정확히 일치하는 run 의 terminal** 만 반환하므로 sentinel 을 실으면 영원히
    timeout 되고, attach 가 상한(`ASK_ATTACH_MAX_TOTAL_SEC`=1800s)까지 유지돼 `busy`/`myAskInFlight`
    가 오래 잔류한다(전송 버튼·중단 라우팅 오상태). `attachAndWaitForResult` 진입 시 `_adoptRunId`
    정제 + timeout 응답의 실제 run 으로 승계(`_served`) + 호출부 3곳(복구·resume·새로고침 복원
    `pendingBubble.runId`) 전부 정제 경유. C9 4단언으로 고정.
  - **[P2 수정 완료] `loadHistory` 의 sentinel 전환 판정이 정상 추적을 리셋했다** — `"" !== "run-A"`
    가 참이 되어 진행 중 실제 run 의 `progressSteps`·`after_step` 을 헛되게 비웠다. 채택값이
    **있을 때만** 비교하도록 수정(`Boolean(_adoptRunId(...)) && …`). C10 으로 고정.
  - **[P1-1 범위 결정 — 프론트 단독 해결 불가, 순개선으로 수용 + 후속 과제]**: sentinel 을 채택하지
    않으면 그 구간에 `client_run_id` 를 보내지 않으므로, 그룹 대화에서 다른 멤버 run 이 1~2초 창에
    KV 슬롯을 점유하면 그 run 을 채택할 수 있다(내 run 은 이후 가드에 막힌다). **구분 신호가 없다**:
    실제 run_id 는 양쪽 다 timestamp 형식이고, `status_at` 도 남의 claim 이 내 enqueue 뒤면 같은
    방향이라 시각으로도 가릴 수 없다. 근본 해결은 **서버가 "이 run 이 요청자 것인가"를 응답에 실어
    주는 것**(`ask_jobs.account_id` 기반 `run_is_mine`) — 응답 shape 변경 + 폴링당 쿼리 1 증가라
    성능 축(feature-0026~0028)과 함께 판단해야 하므로 **후속 cycle 과제**로 남긴다.
    수용 근거 3: ① **순개선** — 수정 전에는 그룹뿐 아니라 **단일 대화에서도 100% 고착**이었다
    (라이브 재현으로 확증). ② **발현 창이 좁다** — enqueue~claim 1~2초 + 그룹 동시 전송.
    ③ **자기 복구된다** — 오귀속된 run 이 terminal 되면 `pollProgress` 가 폴링을 종료하고
    `refreshWorkspace`→`loadHistory` 가 KV 의 내 run(processing)으로 추적을 되돌린다. 영향은
    "그 run 이 끝날 때까지 남의 단계가 내 말풍선에 잠시 표시" 로 한정된다. C7·C8 이 이 동작(오귀속
    발생 + terminal 전이)을 **명시적으로 고정**해, 후속 cycle 이 계약을 바꿀 때 눈에 띄게 만든다.
  - codex 가 지적한 누락 테스트 3건(progressRunId="" 구간 foreign 수신 · sentinel attach ·
    실제 run 추적 중 history sentinel) 전부 추가 — 신규 스크립트 27→**35 PASS**.
- **잔여**: POST-DEPLOY PB-0008 라이브(`visual_verification_scope: always`) — BEFORE 는 이미 라이브
  재현으로 확보했고(§1), 배포 후 같은 시나리오 AFTER 대조로 `tracked` 가 실제 run 으로 전환되고
  `frontSteps` 가 서버 `steps` 를 따라가는지 확인.

## REV-20260729T175000-progress-poll-resilience [CODEX:progress-poll-resilience] — 진행 폴링 영구 정지 → 자가 회복 (TASK-20260729T1750)
- 대상 diff: `src/static/app.js`(폴링·감지기·이벤트 훅) · `tests/verify_progress_poll_resilience.mjs`(신설) ·
  `tests/verify_run_detect_poll.mjs`(계약 갱신) · 문서 3. **백엔드·RBAC·스키마·엔드포인트 변경 0**.
- **§18.8 패널 처리**: 정책상 UI 변경은 ux/design 패널 대상이나 본 세션에 "요청 없이 Agent tool
  호출 금지" 지시가 걸려 있어 충돌한다. 자체 SKIP 하지 않고 **사용자에게 확인 → `/codex review`
  대체 선택**(§18.8.1 경로 2). `[CODEX:progress-poll-resilience]` 결과를 아래 기록.
- **판단 근거 — 왜 "재시도 상한 상향" 이 아니라 "포기 제거" 인가**: 상한을 5회·10회로 올려도
  같은 결함이 남는다(순단이 길면 여전히 죽고, 죽으면 회복 경로가 없다). 결함의 본질은 재시도
  횟수가 아니라 **"폴링이 죽을 수 있는데 아무도 그것을 감시하지 않는다"** 는 구조다. 그래서
  (a) 폴링은 포기하지 않고 백오프만 늘리고, (b) 그럼에도 죽는 경로가 남을 때를 대비해 감지기를
  watchdog 으로 세웠다. 두 겹이라 한쪽이 실패해도 화면이 박제되지 않는다.
- **대안 검토·기각**: ① *서버 SSE/WebSocket 푸시* — 근본적이나 Caddy·2-replica·SSE pre-drain
  (feature-0014)까지 건드리는 별개 cycle. 본 결함은 클라이언트 복원력만으로 해소된다. ② *폴링
  실패 시 사용자에게 토스트로 알리고 수동 재시도 버튼* — 사용자가 이미 겪은 마찰을 UI 로 떠넘기는
  것이라 기각(ask-timeout-nonblocking 의 "모달 제거" 결정과 같은 방향). ③ *`errorCount` 상한만
  상향* — 위 근거대로 결함이 남아 기각.
- **자체 적대 검토 (H1~H7)**:
  - H1 *무한 재시도가 서버를 때리지 않나* — 백오프 상한 60s, 대상은 활성 대화 1건뿐. 정상 폴링이
    1.2s 주기이므로 실패 구간의 부하는 **정상 대비 1/50 수준**. 부하 증가 없음.
  - H2 *watchdog 이 `loadHistory` 를 폭주시키지 않나* — 감지기는 폴러 생존 시 fetch 0회. handoff
    시 `reschedule=false` 로 중복 타이머를 만들지 않고, 재무장은 `loadHistory` 가 단독 관장.
    F1 이후 폴러는 활성 대화가 있는 한 항상 재스케줄되므로 watchdog 이 깨어나는 빈도 자체가 낮다.
  - H3 *dormant 근거를 줄여 정상 경로에 중복 fetch 공백이 생기지 않나* — `pollProgress` 는 첫
    await 이전 동기 구간에서 `progressPollInFlight = true` 를 세우고, `finally` 의
    `scheduleProgressPolling` 이 같은 동기 구간에서 `progressPoller` 를 세운다. 단일 스레드라
    두 신호 사이에 공백이 없다. tick 콜백의 `progressPoller = null` 직후 호출되는 `pollProgress`
    도 동기 구간에서 in-flight 를 세운다. 유일한 공백은 `pollProgress` 초입 early-return
    (활성 대화 없음·seq 무효·이미 in-flight)인데, 이는 폴링이 실제로 무효인 상황이라 감지기가
    깨어나는 것이 **의도된 동작**이다.
  - H4 *baseline 비교 제거가 `sendPrompt` 직후 중복 재로드를 만들지 않나* — `sendPrompt` 는
    `startProgressPolling` 을 먼저 호출해 폴러를 세우므로 감지기는 dormant. 감지기가 fetch 하는
    시점은 폴러 부재 시뿐이라 이 경로는 성립하지 않는다.
  - H5 *그룹 대화 foreign-run 불변식(내 run 갈아타기 금지)을 깨나* — 그 불변식은
    `applyProgressPayload` 의 early-return 가드가 담당하며 **무변경**. 감지기의 handoff 는 종전과
    동일하게 검증된 `loadHistory` 경로 위임이다.
  - H6 *`online` 훅이 중복 폴링을 만드나* — `startProgressPolling` 이 내부에서
    `stopProgressPolling` 을 먼저 호출하고 `progressPollSeq` 를 증가시켜 이전 타이머·in-flight 를
    무효화한다. 멱등.
  - H7 *숨김 탭에서 무한 재시도로 배터리를 먹나* — `visibilitychange` hidden 분기가 폴링을 완전히
    정지시키는 동작은 **무변경**. 숨김 백오프 하한은 그 경계 직전 tick 에만 적용된다.
- **`/codex review` 결과 — P1 1건 · P2 2건, 전건 처리**:
  - **[P1] 그룹 대화 foreign-run 갈아타기 (수정 완료 — 내 변경이 새로 연 경로)**. 내 run `R1` 을
    추적 중 폴러가 죽고 다른 멤버의 `R2` 가 대화 슬롯을 점유하면, watchdog 의 감지 fetch 는
    `client_run_id` 를 싣지 않으므로 `R2` 를 받고 → `loadHistory` 가 `last_run_id=R2` 로 폴링을
    재시작 → 이후 폴링이 남의 run 을 추적해 **내 `R1` 의 per-run terminal marker
    (`_load_run_terminal_marker`, `routers/conversations.py`)를 영영 못 받는다**. 즉 원래 고치려던
    고착이 다른 경로로 재현된다. 수정 전에는 `pendingBubble` dormant 가드가 이 경로를 막고 있었고,
    내가 그 가드를 제거하며 열렸다 — **유효한 지적**.
    **수정 방향은 codex 제안(“`runId !== progressRunId` 면 handoff 금지”)보다 한 걸음 앞에서 끊었다**:
    *죽은 폴러의 회복은 그 폴러를 되살리는 것*이지 서버에 "현재 슬롯 run" 을 묻는 것이 아니다.
    `detectNewRun` 의 dormant 가드 직후에 `state.progressRunId` 가 있으면 **fetch 없이**
    `startProgressPolling({reset:false, runId})` 로 재기동하고 감지기를 재스케줄한다 →
    (a) foreign run 을 받을 기회 자체가 사라지고 (b) 네트워크 비용 0 (c) `client_run_id=R1` 로
    폴링이 재개돼 서버가 내 run 의 종료를 해소한다. 회귀 가드 신설 — 신규 스크립트 Case 6(6건,
    payload 를 `r2-foreign` 으로 두고 handoff·fetch 0 을 단언) + 기존 스위트 S4b/S4c.
  - **[P2] 감지 fetch 가 abort 되지 않아 재무장이 완전 멱등이 아님 (수정 완료)**.
    `stopRunDetectPolling` 이 타이머·플래그만 정리하고 `detectNewRun` 의 `AbortController` 는
    지역 변수라 끊지 못했다 → 재가시/`online` 훅이 in-flight 요청을 남긴 채 새 감지를 띄운다
    (결과는 seq 로 버려져도 HTTP 요청은 나간다). `state.runDetectAbortController` 를 도입해
    `pollProgress`/`stopProgressPolling` 과 동형으로 맞추고, `finally` 는 **자기 controller 일
    때만** 해제해 그 사이 재무장이 건 새 controller 를 보존한다. 정적 계약 4건으로 고정.
  - **[P2] 저빈도 zombie polling (수용 — 의도된 트레이드오프)**. 서버 오류가 지속되면 활성 탭에서
    60초당 1회 요청이 무기한 이어진다. 이를 막으려 다시 "N회 후 포기" 로 돌아가면 **본 cycle 이
    고친 결함이 그대로 복원된다**. 상한을 두려면 "포기" 가 아니라 "사용자에게 표면화 후 수동 재시도"
    가 맞는데, 그건 ask-timeout-nonblocking(2026-07-09)이 모달 제거로 이미 기각한 방향이다.
    또한 서버측 `_compute_display_status` 가 stale 판정으로 `stale_error` 를 돌려주므로 `processing`
    영구 잔존은 성립하지 않고, 숨김 탭에서는 폴링이 완전히 정지한다(무변경). 활성 탭 + 활성 대화
    한정 분당 1요청은 종전 정상 폴링(1.2초 주기)의 1/50 이라 수용한다.
- **기존 테스트 계약을 바꾼 것에 대한 정직 기록**: `verify_run_detect_poll.mjs` 6건이 수정 직후
  FAIL 했다. 그 단언들은 "pendingBubble 존재 → dormant", "processing 분기에서 감지기 정지" 를
  고정하고 있었는데, **이것이 곧 결함의 직접 원인**이다. 테스트를 살리려 코드를 되돌리면 결함이
  남으므로 계약을 갱신했다. dormant 의 본래 의도(중복 fetch 방지)는 폴러 생존 기준으로 보존하고,
  반대 방향 시나리오(S4b: 폴러 사망 → watchdog 회복)를 추가해 새 계약을 고정했다.
- **잔여 리스크(정직)**: 서버측 `/api/ask` 가 200~300초 동기 응답으로 클라이언트/프록시 연결이
  끊기는 문제(라이브 엣지 로그 `status=0` 다수)는 **본 cycle 범위 밖**이다. 본 변경은 그 상황에서
  화면이 죽지 않게 하는 복원력만 제공하며, 근본 지연은 feature-0026~0028 성능 축의 과제다.
- **라이브 검증 미완**: PB-0008 실 Windows 브라우저 검증은 배포 직후 수행(`visual_verification_scope:
  always`). 그전까지 "코드·단위검증 완료" 로만 표기한다.

## REV-20260729T141200-test-live-db-isolation [SKIPPED:user-directive] — `make test` 의 라이브 컨트롤플레인 쓰기 차단 (TASK-20260729T1412)
- 대상 diff: `tests/conftest.py`(autouse 차단 fixture) · `tests/test_live_db_isolation.py`(신설) ·
  `tests/test_runtime_settings_api.py`(assert 강화) · `Makefile`(`TEST_ISOLATION_ENV`) ·
  (cross-unit) `feature-0002-agent-core/tests/test_runtime_settings.py`. **제품 코드 변경 0**.
- **panel SKIP 근거**: §18.8 표상 code change + dispatch 키워드 매칭 0건 → 정책 기본값은 full panel.
  그러나 본 세션에는 "사용자 요청 없이 Agent tool 호출 금지" 세션 지시가 걸려 있어 정책과 충돌한다.
  자체 판단으로 SKIP 하지 않고 **사용자에게 1회 확인**했고(2026-07-29), 사용자가 "패널 생략하고
  진행" 을 선택했다. 변경 표면이 테스트 인프라·빌드 진입점에 한정되고 검증이 라이브 실측으로
  닫혔다는 점이 그 결정의 근거였다.
- **왜 이 수정이 옳은 지점인가**: 오염의 인과 사슬은 `PUT → _save_runtime_setting →
  _reconcile_runtime_settings_snapshot` 이고, 그 앞단의 유일한 게이트가 `get_conn → _connect_memory`
  다. 그래서 차단을 endpoint 나 assert 가 아니라 **커넥션 진입점**에 놓았다 — 저장 경로를 타는
  미래의 다른 테스트도 자동으로 덮인다. assert 강화는 그 위의 2차 방어이지 1차가 아니다.
- **대안 검토와 폐기 사유**:
  - `dependency_overrides[get_conn]` 로 덮기: 실측 결과 기존 검증 패턴 2종을 무력화했다 —
    `_connect_memory` 를 fake 로 monkeypatch 하는 테스트(`test_history_calendar_pg_routing`)와 자체
    fake conn 을 심는 테스트(`test_item11_batch8_update_conv_product`)가 FAIL. monkeypatch 방식은
    "나중 setattr 이 이긴다" 는 성질 덕에 두 패턴을 모두 보존한다 → 채택.
  - `DB_HOST` 를 도달 불가 호스트로: app 이 DB_HOST 를 datasource SSRF allowlist 에 implicit
    등록하므로(TASK-0214) `test_disabled_still_blocks_loopback_linklocal[127.0.0.1]` 가 FAIL 했다.
    포트만 닫는 `DB_PORT=1` 로 대체 — 연결 차단은 직접 실증(`2003 Can't connect to 'mysql:1'`).
  - PG(`AGENT_KB_PG_*`) 동시 차단: 일부 agent-core 테스트가 **라이브 PG 읽기에 의존해 통과** 중이라
    `psycopg.OperationalError` 로 무너진다. 같은 계열의 문제지만 이번 cycle scope 를 넘으므로
    의도적으로 남기고 TASK 잔존 항목에 명시했다(숨기지 않음).
- **검증의 정직성**: "테스트가 라이브를 안 건드린다" 는 코드 리딩으로 단정할 수 없어 **라이브
  네트워크 동등 조건**(`COMPOSE_PROJECT_NAME=repo`)에서 실행 전후 `WebRuntimeSettings` 해시와
  `testclient` audit 카운트를 대조했다(불변 / 0건). 회귀 판정도 인상이 아니라 **main + 동일 격리
  env 로 baseline 전량을 따로 측정**해 FAILED 집합을 diff 했다(15 → 13, 신규 0).
- **작업 중 자기 오염 1건(기록)**: 검증 도중 cwd 가 main worktree 인 상태로 격리 없는 `make test`
  를 1회 실행해 라이브 설정을 다시 90 으로 덮어썼다(audit `512107~512109`). 사용자가 즉시 900 으로
  복구. 이 사건 자체가 "수정 전 코드로는 1회 실행만으로 즉시 오염된다" 는 대조 실증이 됐다.
- **미해결로 남긴 것**: 오염된 라이브 값 2건(`agent_max_output:claude-sonnet-4` 100000 — 사용자
  의도값은 audit 상 128000 / `model_thinking_budget:claude-haiku-4` 30000 — 사람 설정 이력 없음,
  스펙 기본 5000)은 **사용자 결정으로 복구하지 않는다**(2026-07-29 확인). `WebAuditEvents` 의
  testclient 이벤트 150건도 해시 체인(EventHash/PrevHash) 무결성 때문에 삭제하지 않는다.
- Cross-ref: TASK-20260729T1412-test-live-db-isolation / MODIFY CHG-20260729T141200-test-live-db-isolation /
  test-runs.d/20260729T1412-test-live-db-isolation.md

## REV-20260728T172000-graph-hover-flow-postverify [SKIPPED:non-policy-doc] — 상세 패널 hover 강조(방향·읽기/쓰기 + 흐름 애니) POST-DEPLOY PB-0008 검증 기록 (TASK 20260728T1628-graph-hover-flow, 비-정책 doc-only)
- 대상 diff: test-runs.d fragment(POST-DEPLOY 결과) · TASK 항목 · MODIFY CHG. 코드·자산 변경 0 → §18.8 표 첫 행(비-정책 doc-only), panel SKIP.
- **왜 배포본에서 다시 봤는가**: 사전 검증은 §13.2.9 격리 컨테이너(`web-hoverflow-test`:18097)에서 했고 그 이미지는 worktree 자산을 `docker cp` + 재스탬프(`?v=dev` → `?v=28b8c65898a7`)한 것이라 **빌드 파이프라인(Dockerfile COPY → inject_asset_stamp)을 통과한 산출물이 아니다**. main 기반 이미지가 같은 코드를 서빙하는지는 별도 사실이므로 배포 후 1회 재확인했다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).
- **관측 정합**: 사용자 리포트 두 축이 배포본에서 전건 재현 — 방향(같은 노드쌍 참조함/참조받음 **73px** 차 + 화살촉 상대끝↔self끝 반전) · 읽기/쓰기(**5,346px** 차 + bbox 완전 분리) · 흐름 애니(250ms 간격 4구간 **440/434/440/433px**, 정지 대조군 **0px**) · 잔재 **0px** · `pageerror` **0건**. 절대 수치는 사전 Run(441 / 3,517 / 151px)과 다르나 캔버스 해상도·줌·카메라가 다른 데서 오는 차이이고 **부호·구조는 동일**하다.
- **적대적 자기검증 3건(수치를 믿기 전에 깬 가정)**: ① *측정 채널이 노이즈를 섞지 않는가* — 무hover 2프레임 diff **0px**, hover 전/후 원복 **0px** 로 노이즈 하한을 실측해 두었기에 이하 모든 비-0 을 실신호로 단정할 수 있다. ② *캔버스를 맞게 집었는가* — "가장 큰 canvas" 휴리스틱은 관리 콘솔이 대시보드로 리셋되면 **대시보드 차트**를 집어 hover 전후 0-diff 를 만든다. 첫 1:1 줌 측정이 전건 0px 로 나온 것이 바로 이 함정이었고(기능 실패로 오판할 형태), 전량 폐기 후 캡처 대상을 `#metadataGraphCanvas` 하위로 못 박고 매 캡처에 그래프 가시성·상태줄을 동시 기록해 무효 캡처를 raise 하도록 고쳐 재측정했다. ③ *두 참조 행이 같은 선을 강조하는 것 아닌가*(= 원 결함 재발 의심) — fit 줌에서 두 행 차가 **17px** 로 작았다. 줌 3단 확대에서 방향 차 **73→312px**, 참조 2행 차 **17→108px** 로 **차분이 줌에 비례 확대**되고(대조군은 0px 유지), 다른 스키마 루틴 대상과의 대조는 **3,948px** 로 분리됨을 확인해 "근접 배치로 인한 작은 차이"임을 확정했다.
- **미검증으로 남긴 것(정직 표기)**: `prefers-reduced-motion` 정적 폴백은 OS 설정 토글이 공유 Windows 환경에 부작용을 남기므로 라이브 재확인하지 않았다 — 헤드리스 F 섹션(41 PASS)과 사전 Run 이 계약을 잠근다. 또한 #2 의 근-동치가 **컬럼 노드 미렌더 시 승격 대상이 동일 상위로 접힌 결과**인지는 직접 단정하지 않았고, 위 ③ 의 두 대조로 대상 특정 성립만 입증했다.
- Cross-ref: MODIFY CHG-20260728T172000-graph-hover-flow-postverify / test-runs.d/20260728T172000-graph-hover-flow-postdeploy.md / 선행 REV-20260728T1628-graph-hover-flow.

## REV-20260728T163800-graph-catcluster-focus-postverify [SKIPPED:non-policy-doc] — 카메라 승격 교정 POST-DEPLOY PB-0008 검증 기록 (TASK-20260728T160000, 비-정책 doc-only)
- 대상 diff: test-runs.d fragment(POST-DEPLOY 결과) · TASK 항목 · MODIFY CHG. 코드·자산 변경 0 → §18.8 표 첫 행(비-정책 doc-only), panel SKIP.
- **왜 배포본에서 다시 봤는가**: 사전 검증은 §13.2.9 격리 컨테이너에서 했고 그 이미지는 worktree 자산을 `docker cp` + 재스탬프한 것이라 **빌드 파이프라인(Dockerfile COPY → inject_asset_stamp)을 통과한 산출물이 아니다**. main 기반 이미지가 같은 코드를 서빙하는지는 별도 사실이므로 배포 후 1회 재확인했다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).
- **관측 정합**: 사전 Run 과 POST-DEPLOY Run 의 수치(1189→3 / 40→1148 / 2 / 2)와 상태줄 문구가 **전건 동일**했다. 즉 이번 결함의 수정은 자산 주입 경로가 아니라 정식 빌드 산출물에서도 성립한다.
- **미검증으로 남긴 것**: 사전 Run 과 동일 — `_metaGraphPanToRelation`·hover-pan 직접 호출, GX 좌표 합성 클릭. 둘 다 동일 `_metaRenderedAncestorFor` 를 공유하며 시나리오 1·3 이 그 해소 결과를 라이브에서 단정한다.
- Cross-ref: MODIFY CHG-20260728T163800-graph-catcluster-focus-postverify / test-runs.d/20260728T163800-graph-catcluster-focus-postdeploy.md / 선행 REV-20260728T160000-graph-catcluster-focus.

## REV-20260728T170000-graph-catcluster-polish-postverify [SKIPPED:non-policy-doc] — 스크롤 polish POST-DEPLOY PB-0008 검증 기록 (TASK-20260728T162000, 비-정책 doc-only)
- 대상 diff: test-runs.d fragment · TASK 항목 · MODIFY CHG. 코드·자산 변경 0 → §18.8 표 첫 행(비-정책 doc-only), panel SKIP.
- **배포본에서 다시 본 이유**: pre-commit 검증은 격리 컨테이너(§13.2.9)에서 `docker cp` + 재스탬프한 이미지였다 — 빌드 파이프라인(Dockerfile COPY → inject_asset_stamp)을 통과한 산출물이 아니므로, main 기반 이미지가 같은 코드를 서빙하는지는 별개 사실이다.
- **스크롤 속도를 숫자로 남긴 이유**: "빨라졌다" 는 체감 주장이라 회귀를 못 잡는다. 샘플(t=213ms 9,457 / t=414ms 2,070 / t=820ms 2,017)은 EaseOutExpo 의 초반 급가속·후반 감속 형태를 그대로 보여 주며, 이후 누군가 native smooth 로 되돌리면 이 곡선이 무너진다.
- **미검증으로 남긴 것(정직)**: 배포본에서는 좌클릭 1경로만 재현했다(우클릭 '소속 스키마 상세'·reduced-motion 분기는 헤드리스+스테이징에서 확인). 세 경로가 같은 함수로 수렴하고 배포본에서 그 함수가 정상 동작함을 확인했으므로 재현 부담을 줄였다. 파도 **시각 peak** 캡처도 스테이징 Run 이 정본이다 — 배포본 프레임은 tail 이 잡혔다(CSS `animation-delay` 라 프레임 선택이 결정적이지 않음).
- **드라이버 마찰(정직)**: 공유 Windows Chrome 을 병렬 AI 세션 4곳이 점유해 `bin/win-browser.py` 의 `pages[0]` 고정 선택이 남의 탭을 잡았다. 전용 새 탭을 만들어 그 page 객체만 쓰는 단일-스크립트 드라이버로 회피(타 세션 무접촉, `down` 미사용 — 공유 브라우저를 죽인다). 부수 실측: 탭 전환은 trusted click 필요, `domcontentloaded` 직후 클릭은 부트스트랩 전이라 무효.
- 검증: 서빙 baked 2파일 · 스크롤 샘플 4점 · 파도 24행/delay/alpha 선형 · 잔여 0 · 콘솔 에러 0 · 스크린샷 3매.
- Cross-ref: MODIFY CHG-20260728T170000-graph-catcluster-polish-postverify / test-runs.d/20260728T170000-graph-catcluster-scroll-polish-postdeploy.md / 선행 REV-20260728T162000-graph-catcluster-scroll-polish.

## REV-20260728T162000-graph-catcluster-scroll-polish [SKIPPED:session-policy-no-subagent] — 스크롤 280ms EaseOutExpo + 헤딩 점멸/멤버 파도 (TASK-20260728T162000, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8 / §18.8.2 상위 우선순위 지시 carve-out): 하네스 수준에서 `Agent` tool 사용이 금지돼 subagent panel(ux/design)을 호출할 수 없다. 제약 없는 채널로 대체 — 기계 검증(헤드리스 65, rAF 프레임 구동 포함) + PB-0008 실 브라우저 실측 + 아래 자체 적대 검토. 미검증 범위는 정직 표기.
- 판단 근거:
  - **왜 native smooth 를 버렸나**: `scrollTo({behavior:'smooth'})` 의 duration 은 **명세가 정하지 않는다** — Chrome 은 거리에 따라 늘리므로 17,000px 목록에서 수 초가 됐다(실측). 이 프로젝트엔 같은 문제를 이미 푼 정본이 있다(REQ-20260629-point-scroll: 280ms EaseOutExpo). 새 곡선을 만들지 않고 **그 정본을 그대로 재사용**해 대화 뷰와 그래프 뷰의 "점프 이동" 체감을 하나로 맞췄다.
  - **왜 거리 비례가 아니라 고정 280ms 인가**: 사용자가 요청한 정합 대상(대화 뷰 point-rail)이 고정 duration 이다. 거리 비례로 하면 먼 카테고리일수록 느려져 "신속하게" 라는 요구와 반대로 간다. EaseOutExpo 는 초반에 90% 이상을 소화해 **먼 거리에서도 즉답감**을 준다.
  - **왜 알파를 선형으로 감쇠하나**: 사용자 명시("점점 선형적으로 연하게"). 지수 감쇠면 두세 행 뒤로 사실상 0 이 되어 "파도" 로 안 읽힌다. 선형은 마지막 행까지 신호가 이어지면서도 방향(위→아래)을 분명히 준다.
  - **상한 24행의 근거**: 패널 뷰포트가 담는 행 수가 대략 그 정도다(clientHeight ≈ 616px / 행 ≈ 25px). 그 아래는 보이지 않으므로 애니메이션 노드만 늘고 얻는 게 없다. 93 카테고리 × 수백 행 스키마에서 무제한 파도는 순수 낭비다.
  - **CSS 애니메이션 + 인라인 변수 조합인 이유**: 지연·알파가 행마다 달라 정적 CSS 로는 표현할 수 없고, JS 로 매 프레임 그리면 메인 스레드를 먹는다. `animation-delay` + CSS 변수는 **컴포지터가 처리**하고 JS 는 클래스·변수 주입 1회로 끝난다. 애니메이트 대상은 배경색뿐이라 레이아웃·리플로우가 없다.
- 자체 적대 검토:
  - **H1 파도가 스크롤 애니메이션과 경쟁하지 않나** — 스크롤은 `scrollTop`(JS rAF), 파도는 배경색(CSS 컴포지터)이라 서로 다른 파이프라인이다. 라이브 샘플에서 스크롤이 780ms 안에 정착했고 파도는 그 위에서 정상 진행했다(프레임 캡처).
  - **H2 연타 시 파도 중첩** — `_metaWaveNodes` 원장으로 새 연출이 직전 잔여를 **즉시** 원복한다(헤드리스 ⑦). 원장 없이 타이머만 믿으면 두 연출이 겹쳐 알파가 누적된다.
  - **H3 stale 정리 타이머가 새 연출을 지우지 않나** — 정리 타이머는 `fresh()`(세대 토큰)를 확인한 뒤에만 `_metaClearPanelWave` 를 호출한다. 옛 세대의 타이머는 no-op.
  - **H4 재렌더로 노드가 교체되면 잔여가 남나** — 남지 않는다. 목록은 `innerHTML` 교체라 새 `<li>` 는 클래스·인라인 변수가 없는 상태로 생성되고, 원장의 detached 노드 정리는 `try/catch` 로 흡수된다.
  - **H5 24행 상한이 "전부 점멸" 기대를 배신하나** — 요청은 "하위 자식 요소를 파도 형태로 순차적으로" 이고, 선형 감쇠상 24번째 알파는 이미 0 이다. 상한을 늘려도 **보이는 결과가 같다**. 다만 이 절충은 정직 표기 대상이라 여기·Run 기록에 남긴다.
  - **H6 `maxTop` 클램프 신설로 동작이 바뀌나** — 이전엔 `scrollTo` 가 내부적으로 클램프했으므로 결과는 동일하고, 직접 `scrollTop` 을 쓰는 경로에서 오버슛만 막는다(헤드리스 ⑥ 이 단정).
  - **H7 접근성** — 스크롤은 포커스를 옮기지 않고, 강조는 색 단독이 아니라 좌측 3px 바를 동반한다. `prefers-reduced-motion` 은 즉시 점프 + 파도 미주입 + CSS `animation:none` 3중으로 끈다.
  - **H8 duration 상수 이중 정의** — 파도 길이가 JS(`_META_WAVE_DUR_MS=420`, 정리 타이머 계산용)와 CSS(`420ms`, 실제 재생) 양쪽에 있다. 어긋나면 정리가 애니메이션 도중 끊거나 늦어진다 → 헤드리스 ⑪ 이 **두 값의 일치를 단정**해 드리프트를 잡는다.
- **검증 방법의 마찰(정직 표기)**: 같은 Windows Chrome 을 병렬 AI 세션 4곳이 공유 중이라 `bin/win-browser.py`(항상 `contexts[0].pages[0]`)의 eval 이 **남의 탭에서 실행**됐다. 같은 relay 를 쓰되 **내 origin 의 탭만 URL 로 고르는** 전용 드라이버로 수행했고, 타 세션 탭·공유 Chrome 은 건드리지 않았다(`down` 미사용 — 공유 브라우저를 죽인다). 파도 시각 증거는 4-멤버 그룹(총 ≈588ms)에서는 캡처 타이밍이 프레임을 놓쳐, 총 길이가 긴 31-멤버 그룹(≈1.3s)에서 확보했다.
- 검증: 헤드리스 **65 PASS / 0 FAIL** + 회귀 328 PASS · **PB-0008 라이브** 스크롤 샘플(420ms 2,147 → 827ms 1,698 정착) · 파도 delay `90/116/142/168ms` · alpha `0.500/0.333/0.167/0.000`(선형) · 잔여 0 · 콘솔 에러 0 · 프레임 캡처 5매.
- 위험도: **Minor(§12.3)** — 연출·타이밍 전용. 백엔드·API·RBAC·스키마 무변경, 롤백 = static 2파일 + 테스트 1파일 revert.
- Cross-ref: MODIFY CHG-20260728T162000-graph-catcluster-scroll-polish / FUNCTION REQ-20260728T162000(AC-CPS-5~8) / test-runs.d/20260728T162000-graph-catcluster-scroll-polish.md / 선행 REV-20260728T152000-graph-catcluster-panel-scroll.

## REV-20260728T161326-graph-analyzed-halo-fit [SKIPPED:session-policy-no-subagent] — AI 분석 완료 컬럼 노드 상태 테두리 기하 보정 (TASK-20260728T161326, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 본 세션은 하네스 정책상 `Agent` tool 사용이 금지되어 subagent 패널을 띄울 수 없다. 기계 검증(T27 15건 + 그래프 전 스위트 677) + PB-0008 라이브 before/after 대조로 대체하고 범위를 정직 기록.
- 판단 근거:
  - **왜 "두께만 줄이기" 가 아니라 모양 계약을 고쳤나**: 사용자는 "테두리가 비대"로 보고했지만, 코드 확인 결과 halo 는 11px 원형 노드에 **17×30 사각 알약**이었다. 폭 초과(17 vs 11)보다 **높이 초과(30 vs 11)** 가 3배로 컸고, 이것이 컬럼 행 간격(~24px)을 넘어 이웃 halo 와 겹치며 "세로 관" 을 만든 지배 원인이다. 두께만 줄였다면 관이 얇아질 뿐 사라지지 않는다.
  - **왜 비례 계수의 기준이 24 인가**: 테이블·루틴 칩의 높이가 24 다. 24 를 1.0 으로 두면 **모든 rect 노드에서 k=1** 이 되어 기존 수치가 산술적으로 보존된다(T27 이 좌표·radius·lw 를 전건 대조해 잠금). 즉 비례화의 대가로 다른 노드 종류가 흔들리지 않는다.
  - **왜 기하를 순수 함수로 뺐나**: 렌더 경로(Pixi Graphics)는 헤드리스에서 검증하기 어렵다. 좌표 산술만 `PixiAdapterPure` 로 분리하면 `_applyNodeStates` 를 실제로 호출하지 않고도 회귀 0 을 기계로 증명할 수 있다(기존 §78 Phase B 계약과 동일 패턴).
  - **왜 원형 대시를 새로 만들었나**: `dashSegments` 는 폴리라인 전용이라 원에 쓸 수 없다. 각도 = 호길이/r 로 변환하면 반지름과 무관하게 **직선 대시와 같은 화면 대시 길이**가 나온다 — running(4,3)·busy(2,2) 의 시각 아이덴티티가 노드 종류를 넘나들어도 유지된다.
- 자체 적대 검토:
  · **H1 다중 상태 동심링이 작은 노드에서 겹치지 않나(인정·한정)**: k 비례라 11px 컬럼에서 링 간격이 ~0.9px 로 좁아 analyzed+selected 동시 표기 시 부분 겹침이 남는다. 다만 **종전 rect 경로도 lw 3 / inset 2 라 이미 겹쳤고**(비율 동일), 11px 노드에서 두 링을 완전 분리하려면 halo 를 노드의 2배 밖까지 밀어야 해 원 요구("비대")와 정면으로 충돌한다. 겹침 시 나중 페인트(selected)가 위에 보이는 기존 우선순위 계약은 그대로다.
  · **H2 두께 하한 1px 이 hairline 정책과 충돌하나(검증)**: 엣지의 §87 hairline 은 dpr 기반 물리픽셀 보정이고, 여기 하한은 **모델 좌표 하한**이라 축이 다르다. 하한이 없으면 6px 이하 노드에서 링이 0.75px 로 내려가 줌아웃 시 소실된다.
  · **H3 hover 확장 카드 회귀(검증)**: `_showLabelExpand` 는 `{states, style:{size:[w,h]}}` 만 넘겨 `type` 이 없다 → `haloGeom` 이 rect 분기를 타 종전과 동일(T27 "type 미지정 → rect 경로" 로 잠금).
  · **H4 무한 루프·성능(검증)**: `dashArcs` 는 `t += seg` 로 단조 증가하고 seg = min(dash[i], 남은 길이)라 종료가 보장된다. 실제 드로잉 호출 수를 스텁으로 계수 — circle analyzed 2 ops, running 15, busy 23, 4상태 동시 23, rect busy 189(종전과 동일 경로). 런어웨이 없음.
  · **H5 라이브 검증 중 관측된 페이지 이탈이 본 변경 탓인가(반증 완료)**: 주입 QA 중 admin 화면이 대시보드로 되돌아가는 현상이 반복됐다. ① 원본 렌더러로 되돌린 대조에서도 재현 조건이 갈렸고, ② 수정본으로 재주입한 대조에서 `errs=[] · canvas 생존 · nav=navigate` 로 **정상**이었으며, ③ 최종적으로 Chrome 이 121테이블·300루틴 스키마 전개 중 **브리지째 죽는** 것을 확인(도구 `no_bridge`). 원인은 대형 스키마 전개의 브라우저 부하 + 내가 넣었던 `?v=haloqa1` 캐시버스터가 서버 측 asset-stamp 재주입으로 원복되며 생긴 import 불일치이지, 본 변경이 아니다. 가벼운 스키마로 옮겨 AFTER 를 정상 확보했다.
- 검증: 헤드리스 `test_pixi_adapter.js` **205 PASS**(T27 15건 신설) · 그래프 전 스위트 **677 PASS / 0 FAIL** · `make test` pytest 는 attachment/runtime_settings 15건 실패이나 **전부 worktree 격리 네트워크 환경성 baseline**이고 본 변경은 Python 무접촉(ruff PASS) · PB-0008 실 Windows Chrome/150 relay 4× 확대 before/after · 주입 QA **원복 완료**(서빙 `haloGeom` 0건 · `/livez` 200).
## REV-20260728T160000-graph-catcluster-focus [SKIPPED:tool-restricted:ux,design] — 접힌 카테고리 클러스터 하위 테이블 추적 카메라 승격 교정 (TASK-20260728T160000)
- Trigger: `UI/화면/레이아웃` keyword matched (§18.8 표 3행 → ux, design). **패널 미수행 사유**: 본 세션은 하네스 상위 지시로 `Agent` tool 호출이 금지돼 있다 — §18.8.2 "상위 우선순위 지시 carve-out" 에 따라 제약 없는 채널(자체 적대 검토 + 헤드리스 결정론 스위트 + PB-0008 라이브 실측)로 검증하고, 덮지 못한 도메인을 본 태그로 **명시**한다(미검증을 완료로 오인 보고하지 않음).
- **왜 이 결함이 생겼나(설계 관점)**: 승격 사다리가 *모델 계층*(`scope:schema.table.column` — key 파싱)으로만 서 있었고, **렌더 게이팅 계층**(sim-group `groupCollapsed` / 제품 카테고리 `catCollapsed`)은 사다리 밖에 있었다. 두 계층은 key 로 파생되지 않고 **build 가 만드는 역인덱스**(`groupOf` / `catMembers`)로만 알 수 있어서, 키 파싱만 하는 사다리에는 애초에 보이지 않았다. `_metaColParent` 가 테이블 키를 받으면 스키마를 돌려주는 성질(컬럼 전제 함수)이 그 구멍을 조용히 메워, 사다리가 **실패하지 않고 잘못된 대상으로 성공**한 것이 증상이 늦게 발견된 이유다.
- **왜 자동 펼침이 아니라 승격인가**: `groupCollapsed`/`catCollapsed` 는 주석이 명시하듯 **사용자 지속 의도**이고 build 는 검색 매칭일 때만 강제 펼친다. 추적 한 번이 사용자의 접힘 의도를 되돌리면 대량 클러스터에서 화면이 통째로 재배치된다. 사용자 요구 문장도 "카테고리 클러스터로 카메라가 이동" 이지 "펼쳐라" 가 아니다 → **시선만 이동**. 테스트 A13 이 승격 경로에 `expand/toggle` 호출이 없음을 정적으로 고정한다.
- **왜 `renderedIds` 게이팅인가**: `groupOf`/`catMembers` 는 매 build 재구성되지만 카드 강등·flat masonry·카테고리 비활성 build 에서는 **갱신되지 않고 이전 값이 남을 수 있다**. 게이팅 없이 쓰면 존재하지 않는 요소로 카메라를 보내 `getElementRenderBounds` 예외 → 무음 실패가 된다. 두 해소기 모두 `renderedIds.has(...)` 를 통과한 id 만 반환한다(A8/A9 가 단정).
- **자체 적대 검토 H1~H6(전부 in-cycle 반영 또는 근거 기록)**:
  - **H1 [scope]** 사다리에 GB 를 끼우면 *접힘* 뿐 아니라 **뷰포트 컬링으로 미렌더인 테이블**도 GB 로 간다 — 종전엔 스키마 combo 였다. 의도된 개선으로 판단(더 가까운 조상이고 combo 보다 정확)하되 **범위 확대임을 명시**한다. GB 박스는 컬링과 무관하게 전 멤버 place bbox 에서 파생되므로 부분 컬링 상태에서도 대표 위치가 맞다.
  - **H2 [perf]** `_metaCategoryElementFor` 는 `catMembers` 선형 역탐색이다. 카테고리는 수~수십·멤버는 수십~수백이고, **스키마가 미렌더일 때만** 도달하는 마지막 단계라 hover-pan 경로에서도 무시 가능. 역맵 캐시는 build 마다 무효화 관리 비용이 이득보다 커 미채택.
  - **H3 [정합]** 컬럼 키가 `groupOf` 에 들어올 가능성 → 없음(`b.sg.tables` = 테이블·루틴 항목만 적재). 따라서 `_metaGroupElementFor(columnKey)` 는 자연히 null 이고, 컬럼은 **테이블 우선** 규칙이 보존된다(A1 이 단정).
  - **H4 [회귀]** `_metaGraphAnimateFocus` 앵커 해소에 조상 폴백을 넣으면 팬 도중 대상이 렌더되기 시작할 때 목표가 바뀔 수 있다 — 루프가 매 프레임 재해소하므로 **최종 수렴 대상은 노드**이고, 중간 방향 전환은 "재빌드 중에도 최종 위치로 수렴" 이라는 기존 설계 의도와 같은 성질. 반대로 폴백이 없으면 1.2s 를 헛돌다 **카메라가 아예 안 움직이는** 무음 실패라 교체가 명백히 낫다.
  - **H5 [무음 실패]** 상태줄이 승격 대상과 무관하게 "소속 테이블" 로 단정하던 부분은 이번 결함의 *은폐 장치*였다 — 실제로는 스키마 클러스터로 갔는데 안내는 테이블이라 사용자가 오이동을 진단할 단서가 없었다. `_metaAncestorKindKo` 로 실제 대상을 표기해 다음 오이동은 화면에서 즉시 드러나게 한다.
  - **H6 [i18n·라이브 포착]** 1차 라이브 Run 에서 상태줄 조사가 `카테고리(으)로` 로 어색함을 실화면 판독으로 포착 → 현재 전 라벨이 모음/ㄹ 받침이라 `로` 가 맞음을 확인해 정정하고, **받침 있는 라벨이 새로 들어오면 FAIL 하는 조사 불변식 테스트**(A12)를 추가. 정정본으로 라이브 6 시나리오를 **전건 재측정**했다.
- 검증: 헤드리스 신규 32 PASS / 0 FAIL + 회귀 364 PASS(dbgroups 78 · pixi 190 · edge_flow 43 · reveal 17 · catcluster_panel_scroll 36) · `node --check`(ESM) PASS · PB-0008 실 Windows Chrome/150 라이브 6 시나리오 PASS(GB 거리 1189→3px · 스키마 combo 거리 40→1148px · CAT 밴드 2px · 회귀 2px · 콘솔 에러 0).
- **미검증으로 남긴 것(정직 표기)**: ① `_metaGraphPanToRelation`(상세 패널 관계 행 단일 클릭)·hover-pan 은 모듈 export 가 아니라 라이브에서 직접 호출하지 않았다 — 다만 **동일한 `_metaRenderedAncestorFor` 를 공유**하고, 라이브 시나리오 1·4 가 그 해소 결과를 실 렌더 상태에서 직접 단정한다. ② 컨텐츠 카테고리 접기를 GX 컨트롤 **좌표 합성 클릭**이 아니라 동일 상태 경로(`groupCollapsed.add` + `_metaG6Apply`)로 유발했다(GX 히트테스트 자체는 직전 cycle 검증 범위). ③ ux/design 도메인 적대 패널(위 tool-restricted).
- Cross-ref: MODIFY CHG-20260728T160000-graph-catcluster-focus / FUNCTION REQ-20260728T160000-graph-catcluster-focus(AC-CCF-1~4) / test-runs.d/20260728T160000-graph-catcluster-focus.md / 증적 `artifacts/shared/win-browser-shots-catcluster-focus/*.png`.

## REV-20260728T153500-graph-catcluster-scroll-postverify [SKIPPED:non-policy-doc] — 카테고리 선택 스크롤 동기화 POST-DEPLOY PB-0008 검증 기록 (TASK-20260728T152000, 비-정책 doc-only)
- 대상 diff: test-runs.d fragment(POST-DEPLOY 결과) · TASK 항목 · MODIFY CHG. 코드·자산 변경 0 → §18.8 표 첫 행(비-정책 doc-only), panel SKIP.
- **왜 배포본에서 다시 봤는가**: pre-commit 검증은 §13.2.9 격리 컨테이너(라이브 무접촉)에서 했다. 그 이미지는 내 worktree 자산을 `docker cp` + 재스탬프한 것이라 **빌드 파이프라인(Dockerfile COPY → inject_asset_stamp)을 그대로 통과한 산출물이 아니다**. main 기반 이미지가 실제로 같은 코드를 서빙하는지는 별도 사실이므로 배포 후 1회 재확인했다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).
- **정직 표기 — 관측 수치 차이**: 사전 Run 은 대상 헤딩이 뷰포트 `+53px`, 배포본 Run 은 `+6px` 였다. 상수 회귀가 아니라 **상세 패널 이력 바(`.admin-meta-graph-detailnav`) 표시 여부**의 차이다(이력 ≤1 이면 `hidden`). 보정은 `getBoundingClientRect().height` 실측이라 두 경우 모두 "헤딩이 바에 가리지 않는다"는 AC-CPS-1 을 충족한다 — 상수로 굳혔다면 한쪽이 깨졌을 지점이다.
- **미검증으로 남긴 것**: 배포본에서는 좌클릭 경로 1건만 재현했다(우클릭 '소속 스키마 상세' · 두 번째 카테고리 · 스키마 카드 회귀 경로는 사전 Run 에서 확인). 세 경로가 같은 함수(`_metaGraphFocusPanelGroup`)로 수렴하고 배포본에서 그 함수가 정상 동작함을 확인했으므로 재현 부담을 줄였다 — 다만 배포본 실측 범위는 위 표 그대로다.
- 검증: 서빙 baked 3파일 present · 좌클릭 정착 1,673(+6px) · 강조 1건 · 상태줄 문구 · 콘솔 에러 0 · 스크린샷 3매.
- Cross-ref: MODIFY CHG-20260728T153500-graph-catcluster-scroll-postverify / test-runs.d/20260728T153500-graph-catcluster-panel-scroll-postdeploy.md / 선행 REV-20260728T152000-graph-catcluster-panel-scroll.

## REV-20260728T152000-graph-catcluster-panel-scroll [SKIPPED:session-policy-no-subagent] — 캔버스 컨텐츠 카테고리 선택 → 스키마 클러스터 목록 스크롤 동기화 (TASK-20260728T152000, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8 / §18.8.2 상위 우선순위 지시 carve-out): 본 세션은 하네스 수준에서 `Agent` tool 사용이 금지돼 subagent panel(ux/design)을 호출할 수 없다. 제약 없는 채널로 대체했다 — 기계 검증(헤드리스 36 신규 + 268 회귀 단정, **호출부 인자 매핑 포함**) + PB-0008 실 브라우저 라이브 실측 + 아래 자체 적대 검토. 미검증 범위는 `[SKIPPED:session-policy-no-subagent]` 로 정직 표기한다.
- 판단 근거:
  - **왜 fam 만 대조하는가**: 그룹 키는 `_metaSimGroups(schemaId, …)` 의 `schemaId` 로 네임스페이스된다. 캔버스는 `comboId`(`<scope>:<schema>`), 패널은 `"panel:" + schemaName` 을 넘긴다 — **전체 키는 절대 같아질 수 없다**. 구분자 뒤 fam(`be:` 백엔드 클러스터 / `nm:` 이름 family / `role:` / `misc`)은 멤버 집합에서 파생돼 양쪽이 공유하므로 유일한 안정 조인 키다. 네임스페이스를 통일하는 대안은 `groupOrder`·`groupTableOrder`·`panelGroupCollapsed` 등 **기존 상태 키의 의미를 전부 옮겨야** 해서 회귀 표면이 훨씬 크다.
  - **`scrollIntoView` 를 쓰지 않은 이유**: 상세 패널은 `overflow-y:auto` aside 지만 그 조상(관리 콘솔 본문)도 스크롤 가능하다. `scrollIntoView` 는 조상 체인을 함께 움직여 **캔버스가 화면 밖으로 밀리는** 부작용이 있다. aside `scrollTop` 직접 계산은 국소적이고, sticky 이력 바 보정도 자연스럽게 얹힌다.
  - **sticky nav 보정을 상수로 두지 않은 이유**: `.admin-meta-graph-detailnav` 는 이력 ≤1 이면 `hidden` 이라 높이가 0/47 로 갈린다. 실측(`getBoundingClientRect().height`)이 아니면 이력 유무에 따라 헤딩이 바 뒤로 숨거나 과하게 내려간다 — 라이브에서 두 경우 모두 `+53`/`+6` 으로 확인했다.
  - **접힘 상태를 자동으로 펼치지 않은 이유**: 요청은 "위치로 스크롤" 이다. `panelGroupCollapsed` 는 사용자가 명시적으로 만든 상태이고, 스크롤의 부수효과로 그것을 뒤집으면 요청하지 않은 변경이 된다. 접힌 그룹도 헤딩은 렌더되므로 스크롤 목표로서 온전하다.
  - **상태줄 표기를 붙인 이유**: 스크롤이 조용히 일어나면 (특히 smooth 애니메이션 중) 사용자가 "패널이 왜 움직였지" 를 알 수 없다. `목록을 '<라벨>' 위치로 이동` 1줄이 원인을 명시한다. 미매칭이면 문구가 붙지 않아 **거짓 성공 표시가 생기지 않는다**.
- 자체 적대 검토:
  - **H1 캔버스/패널 그룹 분할이 어긋나면?** — ById 경로는 테이블을 API 응답에서, 루틴을 모델에서 모으므로 캔버스의 `gatedTables` 와 멤버 집합이 미세하게 다를 수 있다. fam 이 안 맞으면 `_metaGraphFocusPanelGroup` 이 `null` 을 반환하고 **아무 것도 하지 않는다**(스크롤·강조·상태줄 접미 모두 없음). 잘못된 그룹으로 점프하는 실패 모드는 구조적으로 불가능하다 — 정확 일치만 매칭한다.
  - **H2 이력(뒤로/앞으로) 스크롤 복원과 경합하지 않나** — `_metaGraphHistoryGo` 는 `_metaGraphShowClusterDetailById(ent.k)` 를 **fam 없이** 호출하므로 focus 경로가 아예 발화하지 않고, 그 뒤 `_metaGraphHistoryRestoreScroll` 이 저장된 scrollTop 을 복원한다. 두 rAF 가 같은 프레임에 경쟁하는 조합이 없다.
  - **H3 연타 시 stale 스크롤** — 렌더는 동기지만 스크롤은 rAF 뒤다. 그 사이 다른 카테고리를 클릭하면 이전 rAF 이 옛 목표로 튄다 → `_panelFocusSeq` 세대 토큰으로 폐기(헤드리스 ⑤ 가 단정).
  - **H4 강조 클래스 누수** — 재렌더로 `<li>` 가 교체된 뒤 타이머가 발화하면 stale 노드에서 클래스를 지운다(무해). 새 노드는 `is-focus` 없이 생성되므로 잔상이 남지 않는다. `try/catch` 로 detached 노드 접근도 흡수.
  - **H5 `:hover` 배경과 경쟁** — `.amgr-ct-group:hover` 와 `.amgr-ct-group.is-focus` 는 특이도가 같다. CSS 순서상 `is-focus` 를 뒤에 두어 강조가 이긴다. 1.8s 뒤 클래스가 제거되므로 hover 어포던스가 영구 손상되지 않는다.
  - **H6 접근성** — 스크롤은 시각 이동일 뿐 포커스를 옮기지 않으므로 키보드 사용자의 포커스 위치를 빼앗지 않는다. 강조는 색 단독이 아니라 **좌측 3px 바**(형태)를 동반한다. `prefers-reduced-motion` 은 `behavior:auto` + 애니메이션 없는 정적 강조로 분기한다.
  - **H7 장거리 smooth 스크롤 체감** — 17,000px 목록에서 smooth 는 수 초가 걸릴 수 있다. 그럼에도 즉시 점프(auto)보다 **어디서 어디로 갔는지**를 보여 주는 편이 방향 감각에 낫다고 판단했다(라이브 육안). 모션 민감 사용자는 위 분기로 즉시 이동한다. 측정 시 중간 프레임을 실패로 오독하지 않도록 Run 기록에 정착 시점을 명시했다.
  - **H8 `\u0001` 구분자 하드코딩 중복** — `graph-core`(캔버스 라우팅)·`graph-ctxmenu`(메뉴·패널) 세 곳이 각자 `indexOf` 한다. 본 cycle 은 기존 관례를 따르고 새 상수(`_META_GKEY_SEP`)를 패널 쪽에만 도입했다. 공용화는 모듈 경계(`graph-state`)를 건드려야 해 범위를 넘는다 — 헤드리스 ⑧ 이 세 호출부의 인자 매핑을 단정해 드리프트를 잡는다.
- 검증: 헤드리스 신규 **36 PASS / 0 FAIL** + 회귀 `test_detail_dbgroups` 78 · `test_pixi_adapter` 190 PASS · `node --check` OK · **PB-0008 라이브**(실 Windows Chrome/150, 격리 컨테이너 §13.2.9) 좌클릭 2건·우클릭 1건·강조 부여/해제·상태줄·회귀경로·콘솔 에러 0 — 정착 위치가 모두 헤딩 상단 **+53px**(navH 47 + 6) 로 재현. 스크린샷 5매.
- 위험도: **Minor(§12.3)** — 프론트 표시·네비게이션 전용. 백엔드·API·RBAC·스키마·데이터 fetch 무변경, 롤백 = static 4파일 + 테스트 1파일 revert.
- Cross-ref: MODIFY CHG-20260728T152000-graph-catcluster-panel-scroll / FUNCTION REQ-20260728T152000-graph-catcluster-panel-scroll(AC-CPS-1~4) / test-runs.d/20260728T152000-graph-catcluster-panel-scroll.md.

## REV-20260728T161940-routine-column-edges [SKIPPED:session-policy-no-subagent] — 사용 관계선 컬럼 단위 연결 (TASK-20260728T161940, Major §12.3)
- Panel skip 사유(§18.8): 세션 정책상 `Agent` tool 미허용 — 자체 적대 검토 H1~H6 + 기계 검증(신규 57건·전 스위트 회귀)·실 브라우저 대조로 대체하고 범위를 정직 기록.
- **자체 적대 검토가 실제 결함 2건을 확증**(둘 다 테스트가 적발, in-cycle 수정):
  - **H1 — "접힘은 기존대로" 계약 위반**: 초판이 `ref_columns` 의 read/write 별로 테이블 승격선을 만들어, 컬럼 미렌더 상태에서 선이 1→2개로 갈라졌다(사용자 요구의 전제 파괴). → 렌더된 컬럼이 0이면 분해 포기.
  - **H2 — 부가 기능이 본 경로를 죽임**: `_fetch_columns` 의 `cursor()` 획득이 try 밖이라 컬럼 조회 실패가 상위로 전파돼 그 스키마의 routine upsert 전체가 무산될 수 있었다. → cursor 획득을 try 내부로.
- 반증 시도(기각): **H3 컬럼 오귀속 환각** — alias 재사용이 흔하므로 `_alias_map` 이 같은 alias 의 다른 테이블 바인딩을 감지해 그 alias 를 통째 폐기, 스키마 qualifier(`dbo.T`)는 alias map 부재로 자동 폐기. **H4 성능** — 참조로 채택된 테이블에만 COLUMNS 1회 질의(2-pass·cap 400), 참조 없으면 질의 자체 없음. 프론트 케이스 인덱스도 lazy. **H5 이행 위험** — jsonb additive(마이그 0)·`sync_routine` 이 ROUTINE_USES 전량 회수 후 재-MERGE 라 stale 없음·값 없으면 속성 미SET(기존 엣지와 동치). **H6 파싱 불완전성(수용)** — 동적 SQL·4000자 절단·`SELECT *` 는 폴백으로 흡수되며, 커버리지를 위해 비수식 컬럼을 추정하면 H3 위험이 되살아나므로 추정하지 않는다(사용자 결정).
- **H7(rebase 중 확증·수정)**: 병합된 feature-0030 cyvol 의 `routine_refs_signature` 가 `cols` 를 담지 않아 기존 routine 이 재작성 생략에 걸려 `ref_columns` 가 라이브에서만 투영되지 않는 경로 — 서명 확장으로 수정 + 회귀 4건. 배포 후 첫 sync 1회 재작성 비용을 정직 고지.
- 검증 경로 변경(정직 기록): 라이브 주입 QA 를 시작했으나 병렬 세션 6+ 가 브라우저·라이브 web 을 공유해 `win-browser.py` 의 `pages[0]` 고정이 타 세션 탭을 잡는 것을 실측 → **즉시 원복**(web-a/web-b md5 원본 일치·`/livez` 200) 후 격리 harness + CDP 신규 탭으로 전환. 상세 = test-runs fragment §3.
- 위험도: **Major(§12.3)** — 다중 계층(파서·그래프 투영·렌더)이나 alembic 마이그 0, RBAC/엔드포인트 계약 무변경, 비파괴 additive. 롤백 = 6파일 revert.
- Cross-ref: MODIFY CHG-20260728T161940-routine-column-edges / FUNCTION REQ-20260728T161940-routine-column-edges(AC-RCE-1~5) / test-runs.d/20260728T161940-routine-column-edges.md / 정본 feature-0016 REVIEW REV-20260728T161940-ai-claude-feature-0016-routine-column-edges.

## REV-20260728T152141-graph-edge-hairline [SKIPPED:session-policy-no-subagent] — 줌아웃 관계선 hairline 처리 (TASK-20260728T152141, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 세션 정책상 `Agent` tool 미허용 — 라이브 대조 + 기계 검증으로 대체하고 범위를 정직 기록.
- 판단 근거:
  - **AA 를 켜자는 가설을 먼저 기각한 이유**: 코드 확인 결과 `antialias: true` 가 이미 있었다. 증상이 남아 있다는 사실 자체가 "AA 부재 가설" 의 반증이다. 사용자 질의("과도한 조치일지")에 대한 답은 "과도한 게 아니라 이미 한 조치이고 효과가 없다" 이다.
  - **왜 MSAA 로는 못 고치나**: MSAA 는 픽셀당 N 샘플의 커버리지를 평균한다. 폭 0.3px 선은 커버리지 자체가 30% 라 4 샘플에서 0/25/50/75% 로 양자화되고, 그 튐이 끊김·계단으로 보인다. 샘플 증설은 단계만 촘촘하게 할 뿐 서브픽셀이라는 원인을 없애지 못하며 fill rate 를 먹는다.
  - **왜 hairline 이 정석인가**: 폭을 1물리픽셀로 고정하면 커버리지가 100% 로 균일해져 양자화 자체가 사라진다. 두께 정보는 alpha 라는 연속 채널로 옮겨 손실이 없다. 지도·CAD 렌더러가 수십 년 써 온 기법이다.
  - **base 를 1.0px 로 올린 이유**: 0.6px 는 dpr 1 에서 **모든 줌**이 hairline 경로라, 개수 축(굵기)이 상시 alpha 로 흘러 신뢰도 축과 섞였다. 1.0px 부터 정상 렌더 구간이 생겨 §86 의 채널 직교화가 실제로 성립한다.
- 자체 적대 검토:
  · **H1 alpha 이중 사용(인정·한정)**: 서브픽셀 구간에서 개수·신뢰도가 같은 채널을 공유한다. 다만 그 구간은 굵기 분해가 불가능한 영역이고, 1px 이상에서는 분리된다. 대안(폭을 안 올리고 두는 것)은 증상 존치라 열등하다.
  · **H2 dpr 처리(검증)**: 임계를 `1/dpr` 로 두고 `app.renderer.resolution` 을 1순위로 읽는다. dpr 2 에서 CSS 0.5px 이 임계임을 A13 으로 잠금.
  · **H3 극단 줌아웃에서 다시 화면을 덮지 않나(검증)**: 폭은 1물리픽셀로 고정되지만 alpha 가 계속 감쇠하므로 실효 잉크량은 §86 과 동일하게 zoom 비례로 물러난다(A11 을 잉크 기준으로 재작성해 잠금).
  · **H4 base 상향이 "가늘게" 요구를 깨지 않나(근거)**: 1px 실선은 hairline 이 만들어내던 두께와 같다. 바뀐 것은 끊김 유무뿐이다.
  · **H5 성능(근거)**: 산술 2~3줄. 폭이 굵어지는 구간은 서브픽셀→1px 뿐이라 fill rate 증가가 미미하다.
- 검증: 동일 줌 4× 확대 대조에서 점선 파편 → 연속 실선(라이브 육안) · 1px 구멍 740→635 · `test_graph_edge_flow.js` 73 PASS · 그래프 전 스위트 **656 PASS / 0 FAIL** · 주입 QA 원복(잔재 0).

## REV-20260728T142745-graph-edge-encoding [SKIPPED:session-policy-no-subagent] — 줌 두께 정책 구간 분리 + 인코딩 축 재배치 (TASK-20260728T142745, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 세션 정책상 `Agent` tool 미허용 — 라이브 실측 + 기계 검증으로 대체하고 범위를 정직 기록.
- 판단 근거:
  - **왜 구간 분리인가**: §84(줌아웃 고정)와 §85(전 구간 고정)는 같은 축의 양극이고 각각 반대편에서 깨졌다. 두께의 요구가 줌 방향별로 다르다 — 확대에서는 "더 굵어지지 마라", 축소에서는 "콘텐츠와 함께 물러나라". 단일 정책으로는 둘을 동시에 만족할 수 없다.
  - **MIN 을 0.25px 로 낮춘 이유**: 0.4 로 두면 base(0.6) 대비 비율이 커서 zoom 0.67 이하가 전부 하한에 붙어 **줌아웃 비례 구간이 평탄해진다**(실측으로 확인 — z 0.5 에서 기대 0.3 대신 0.4). 하한은 "완전 소실 방지" 역할만 해야 한다.
  - **왜 굵기를 개수로 옮겼나**: 사용자 지정이자 정보 설계상 옳다 — 개수는 **양적(quantitative)** 이라 크기 채널에, 신뢰도는 **순서적(ordinal)** 이라 명도 채널에 맞는다. 종전에는 반대로 매핑돼 있었고, 개수는 '다발 가닥' 이라는 비표준 채널에 있었다.
  - **다발 제거의 손실**: §83 이 노린 "부모 볼륨" 표현이 사라진다. 다만 그 의미는 개수이고 이제 굵기가 담으므로 정보 손실은 없다. 오히려 다발은 줌아웃에서 픽셀을 3~4배 먹어 이번 리포트의 도포 현상에 기여했다.
- 자체 적대 검토:
  · **H1 줌아웃에서 다시 안 보이지 않나(검증)**: 하한 0.25px + alpha 누적. 밀집 영역은 겹침으로 드러나고, 저밀도 단선은 의도적으로 물러난다 — 전체보기의 목적은 개별 선 추적이 아니라 구조 파악이다.
  · **H2 zoom 경계(ZFULL=1) 불연속(검증)**: `min(1, z)` 은 z=1 에서 연속(값·기울기 모두 이어짐). 체감 점프 없음.
  · **H3 굵기 상한 2.2px 이 부족하지 않나(근거)**: 화면 픽셀 기준이라 줌인해도 그대로다. 100건과 1000건은 라벨(count)이 구분하고, 굵기는 포화시켜 화면 점유를 통제한다.
  · **H4 재페인트 비용(불변)**: §85 의 `_syncEdgeZoom` 임계(≈25%)·rAF 코얼레싱 그대로. 두께 계산만 바뀌었다.
  · **H5 신뢰도 진하기 하한 0.38 이 너무 옅나(근거)**: inferred 는 추정 관계라 물러나는 것이 맞고, 겹치면 누적으로 드러난다. trusted 0.85 와의 격차가 신뢰도 판독의 주 신호다.
- 프로세스 사고(자체 적발·정정): 셸 cwd 가 main worktree 로 되돌아간 상태에서 상대경로 편집 3파일이 `repo/` 에 적용(§13.2.7 F0). `git diff` 추출 → main `git checkout` 복원(status 0) → 본 worktree `git apply` 이관. 커밋 전이라 원격 영향 없음. 재발 방지: 셸 편집은 절대 경로 또는 매 명령 worktree 루트 cd.
- 검증: 라이브 극단 줌아웃 도포 소멸 육안 + fit 잉크 43.19%→38.95% · `test_graph_edge_flow.js` 66 PASS · 그래프 전 스위트 **649 PASS / 0 FAIL** · 주입 QA 원복(잔재 0 · `/livez` 200).

## REV-20260728T142000-graph-hover-anchor-postverify [SKIPPED:non-policy-doc] — 좌변 고정 확장 POST-DEPLOY PB-0008 검증 기록 (TASK-20260728T135222, 비-정책 doc-only)
- 대상 diff: test-runs.d fragment(POST-DEPLOY 결과) · TASK 체크박스 · MODIFY CHG · evidence 2종. 코드·자산 변경 0 → §18.8 표 첫 행(비-정책 doc-only), panel SKIP.
- 선행 cycle 의 `[SKIPPED:tool-restricted:ux,design]` 미검증 범위를 라이브 실측으로 종결. **요구 문구("좌측은 고정 + 우측 모서리부터 확장")를 두 개의 반증 가능한 수치로 고정**했다: (a) 애니 전 구간 카드 좌측 x 가 **단일값 249** — 하나라도 다르면 좌변이 움직인 것 (b) 유의 픽셀 diff 의 **좌측 경계가 원 카드 우측 끝 이후(354)** — 중앙 대칭이었다면 카드 좌측(250) 이전부터 diff 가 났을 것. 두 지표 모두 통과.
- 부수 확인: 확장분이 우측 이웃 카드 위에 그려지는 z-order 가 라이브에서 처음 실증됨(이전 cycle 은 겹침 케이스가 없었다) — 이웃 카드 자체 좌표는 불변.

## REV-20260728T135222-graph-label-hover-anchor [CODEX:graph-label-hover-anchor] — hover 확장 기준점 좌변 고정 전환 (TASK-20260728T135222, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/graph/graph-renderer-pixi.js`(`hoverExpandGeom.left` · `hoverCardCenterX` · `hoverTextOffsetX` · 카드 위치·라벨 정렬 배선) · `tests/headless/test_pixi_adapter.js`(앵커 계약 assert).
- 검증 채널: 세션 도구제약(§18.8.2 상위 지시 carve-out)으로 ux/design subagent 미호출 → `[SKIPPED:tool-restricted:ux,design]`, `codex review --uncommitted` + 기계 검증으로 대체. 시각 확정은 POST-DEPLOY PB-0008.
- **VERDICT: SHIP.** codex 2 라운드 — 1차 **P2 1건**(좌측 기준을 `칩 좌변 + pad/2` 로 잡아 라벨이 칩보다 넓은 루틴 칩에서 hover 시 ~17px 텍스트 점프 = 주장한 "t=0 픽셀 동일" 위반) 적발·수정, 2차 "no discrete regressions found".
- 설계 판단: 사용자 요구는 "좌측 고정 + 우측 모서리부터 확장". 이를 **박스 앵커(카드 좌변)** 와 **텍스트 앵커(원 렌더 라벨 좌측)** 두 축으로 분리해 고정했다. 둘은 일반 칩(labelMaxWidth = w0 - pad)에서는 pad/2 차이로 사실상 일치하지만, 루틴 칩 같은 outlier 에서 갈린다 — 텍스트 앵커를 pad 로 **추정**하지 않고 실렌더 폭에서 **역산**한 것이 이 cycle 의 핵심 수정이다.
- 부수 효과(수용): 좌측 고정이라 확장분이 전부 오른쪽으로 가므로, 우측 이웃 칩을 덮을 확률이 중앙 대칭 대비 높아진다. 카드가 최상단(zIndex 99998)이고 transient 이라 판독성 손해는 없으며, 이는 사용자가 명시 요청한 거동이다.
- 검증: `node --check --input-type=module` PASS · `test_pixi_adapter.js` **190 PASS / 0 FAIL** · 그래프 headless 전 스위트 **639 PASS / 0 FAIL**(회귀 0) · verify-completion `--pre-commit`. Cross-ref: TASK/CHG-20260728T135222-graph-label-hover-anchor · test-runs.d/20260728T135222-graph-label-hover-anchor.md.

## REV-20260728T135111-graph-edge-screenspace [SKIPPED:session-policy-no-subagent] — 굵기 변성 제거 + 프로시저 관계선 실선·LOD 해제 (TASK-20260728T135111, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 세션 정책상 `Agent` tool 미허용 — 라이브 실측 + 기계 검증으로 대체하고 범위를 정직 기록.
- 판단 근거:
  - **왜 §84 의 바닥 보정이 문제를 키웠나**: `max(1, MIN/(REF·zoom))` 는 임계 줌 아래에서만 작동해 굵기 거동이 두 체제로 갈렸다. 사용자가 본 "변성" 은 단순 확대가 아니라 **체제 전환 지점의 불연속**까지 포함한다. 바닥이 아니라 **좌표계**를 바꾸는 것이 원인 대응이다.
  - **왜 재페인트가 필요한가**: 굵기는 페인트 시점 zoom 으로 model 에 bake 된다. world scale 만 갱신하는 팬/줌 경로에서는 화면 두께가 다시 흐르므로, 줌 변화가 유의할 때 엣지 기하를 다시 굽는다. 임계(≈25%)는 프레임 비용과 두께 오차(±12%, 육안 미식별)의 절충.
  - **왜 대시를 전부 없앴나**: 신뢰도가 굵기·대시 두 채널에 흩어져 "점선 = 추정" 인지 "점선 = 루틴" 인지 "점선 = 교차DB" 인지 중의적이었다. 얇고 반투명해진 선 위의 대시는 줌아웃에서 점의 나열로 흩어져 관계 자체를 지웠다. 굵기=신뢰도, 색=종류/교차, 화살촉=방향으로 채널을 직교화했다.
  - **ROUTINE_USES 를 trusted 바로 아래 둔 근거**: AGE 속성이 `relation_type`·`cross_ds` 뿐 — 신뢰도 등급이 아예 없는 **확정 참조**(루틴 본문 파싱)다. 다만 컬럼-레벨 FK 보다 입도가 거칠어 최상단은 아니다.
  - **LOD 제거의 대가**: 줌아웃 엣지 수가 늘어난다. 실선+화면 고정 굵기로 개별 선의 신호가 회복됐고 밀도 누적이 군집을 요약하므로, 축약이 주던 이득보다 "전체보기에서 루틴 관계 소실" 의 손실이 크다고 판단했다.
- 자체 적대 검토:
  · **H1 재페인트 비용(완화)**: 임계 25% + rAF 코얼레싱 + in-place 재사용(destroy/recreate 없음). 대형 스코프 실측은 POST-DEPLOY 이월.
  · **H2 극단 줌인에서 model 굵기 과소(검증)**: zoom 4 → model 0.19 지만 화면은 0.75px 로 일정. A11 로 잠금.
  · **H3 다발 간격도 화면 기준으로 바꾼 이유(근거)**: model 로 두면 줌아웃에서 가닥이 겹쳐 볼륨 표현이 사라진다.
  · **H4 대시 제거로 교차DB 구분 약화(근거)**: 색(마젠타) 채널이 남아 있고, 오히려 대시가 사라져 색 판독이 쉬워진다.
  · **H5 LOD 상태줄 문구(검증)**: `_lodDropped` 는 REFERENCES 축약에서 여전히 증가하므로 안내 문구 정합 유지.
- 검증: 라이브 3 줌 레벨 두께 실측(중앙값 1.0/1.0/2.0px, 리본 소멸 육안) · `test_graph_edge_flow.js` 61 PASS · 그래프 전 스위트 **632 PASS / 0 FAIL** · `node --check` PASS · 주입 QA 원복(잔재 0 · `/livez` 200).
- 잔여: 루틴 표시 스코프에서의 사용선 육안(AC-GES-5) — POST-DEPLOY.

## REV-20260728T123000-graph-label-hover-postverify [SKIPPED:non-policy-doc] — 잘린 노드 명칭 hover 확장 POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260728T123000, 비-정책 doc-only)
- 대상 diff: `docs/test-runs.d/20260728T120530-graph-label-hover-expand.md`(POST-DEPLOY 결과) · `docs/TASK.md`(체크박스 종결 + 종결 섹션) · `docs/MODIFY.md`(CHG) · `docs/evidence/*.png` 3종. **코드·자산 변경 0** → §18.8 dispatch 표 첫 행(비-정책 doc-only) 적용, panel SKIP.
- 선행 cycle(`REV-20260728T120530-graph-label-hover-expand`)이 남긴 **유일한 미검증 범위**(ux/design 렌즈 = `[SKIPPED:tool-restricted:ux,design]`)를 라이브 실측으로 종결한다: 확장 애니·이웃 위치 불변·z-order·클릭 라우팅·원복·무반응·에러 8 항목 전부 PASS(상세 수치는 fragment 표).
- 특기 — **③ 위치 불변의 증명 방식**: "확인함" 선언이 아니라 동일 상태 전/후 전체 화면 픽셀 diff 를 임계(>16)로 이진화해 **유의 변화 영역이 캔버스의 2.75%(306×38px)** 이고 그 박스가 hover 한 칩 자신임을 수치로 고정했다(§16.6 픽셀-클래스 변경은 시각 캡처 필수 + 자기-충족 선언 금지). ⑤ 도 hover 전/후 같은 좌표 클릭의 **대조 실험**으로 tier0 라우팅을 분리 입증.

## REV-20260728T123838-graph-edge-legibility [SKIPPED:session-policy-no-subagent] — 그래프 관계선 육안 검증 후 부정합 3건 보정 (TASK-20260728T123838-graph-edge-legibility, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 본 세션 사용자 환경 정책상 `Agent` tool 미허용 — subagent 패널 대신 **라이브 실측 + 기계 검증**으로 대체하고 범위를 정직 기록한다.
- 판단 근거:
  - **왜 굵기 보정이 근본인가**: alpha 만 올리면 "가늘게+투명" 요구를 해치면서도 서브픽셀 문제는 남는다(zoom 0.25 에서 0.85px → 화면 0.21px 는 어떤 alpha 로도 복구 불가). 화면 기준 굵기 바닥이 원인 대응이고, alpha 는 보조.
  - **왜 전 엣지 동일 배율인가**: 엣지마다 `max(lw, MIN/zoom)` 로 clamp 하면 줌아웃에서 기본선과 trusted 가 같은 굵기로 수렴해 **신뢰 강도 서열이 소실**된다. 기준선 하나로 배율을 뽑아 곱하면 서열 비율이 그대로 유지된다(A11 로 잠금).
  - **왜 바닥값을 실측으로 정했나**: 1차 추정(α0.44/화면 0.85px)이 라이브에서 대비 44/255 에 그쳤다. 안티앨리어싱이 1px 미만 선의 실효 alpha 를 깎기 때문으로, 계산이 아니라 관측으로만 확정 가능한 값이었다.
  - **분석 완료 halo 를 낮추지 않은 이유**: 사용자가 그 표식을 탐색 기준으로 쓰고 있다("분석 완료된 항목 중심"). 강한 쪽을 낮추는 대신 약한 쪽(관계선)을 올려 위계를 좁혔다.
- 자체 적대 검토:
  · **H1 과보정 위험(검증)**: 배율은 `max(1, ...)` 라 확대 구간에서 1 로 수렴 — zoom 2 무보정을 테스트로 잠금. 줌인 시 선이 굵어지는 회귀 없음.
  · **H2 누적 연출 훼손(검증)**: α0.58 에서도 1→2→3→4겹이 0.58/0.82/0.93/0.97 로 단조 증가·미포화. "겹칠수록 진해짐" 계약 유지(B2).
  · **H3 곡률 축소로 왕복 분리 약화(검증)**: 하한(5px)은 불변이고 계수만 0.15→0.13 — 근접 노드 왕복선 분리는 A2/A4 로 그대로 통과.
  · **H4 성능(근거)**: 배율은 페인트당 산술 1회. 굵어진 선의 fill rate 증가는 있으나 줌아웃 구간(엣지가 화면에서 짧음) 한정이라 무시 가능.
  · **H5 dim 경로(검증)**: `dimIf` 가 `min(existing, 0.12)` 라 상향된 alpha 와도 정상 합성.
- 검증: 라이브 전후 픽셀 실측(27→51 · 37→55) · 그래프 전 스위트 **627 PASS / 0 FAIL**(edge_flow 56 신규 포함) · `node --check` PASS · 주입 QA 후 이미지 원본 원복(잔재 0, `/livez` 200).

## REV-20260728T120530-graph-label-hover-expand [CODEX:graph-label-hover-expand] — 그래프 뷰 잘린 노드 명칭 hover 확장 (TASK-20260728T120530-graph-label-hover-expand, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/graph/graph-renderer-pixi.js`(+`hoverExpandGeom`/`hoverCardHit`/`clampCardCenterX` 순수 3종 · `_labelHoverLayer` 오버레이 · hover 파이프라인 12 메서드 · `_pick` tier0 · `pointercancel`) · `tests/headless/test_pixi_adapter.js`(T26 68-assert).
- **검증 채널 선택 근거 (§18.8.2 「상위 우선순위 지시 carve-out」)**: §18.8 dispatch 표상 본 변경(UI/화면/레이아웃 키워드)의 required subagent 는 `ux, design`. 그러나 본 세션에는 **하네스 수준의 "Agent tool 미요청 시 호출 금지" 지시**가 걸려 있어 subagent 패널을 호출하지 않았다 — §18.8.2 는 이 경우 상위 지시가 우선하며, 제약 없는 채널로 가능한 검증을 수행한 뒤 미검증 범위를 명시하도록 정한다. 따라서 ①`codex review --uncommitted`(§18.8.1 item 2, check #9 accepted) ②기계적 정적·단위 검증으로 대체하고, 아래 `[SKIPPED:tool-restricted:ux,design]` 로 미검증 도메인을 표기한다. **디자인·UX 렌즈의 실질 보강은 POST-DEPLOY PB-0008 실화면 검증**(`visual_verification_scope: always` hard gate)이 담당한다.
- **VERDICT: SHIP — 미해소 BLOCKING 0.** codex 적대 리뷰를 **9 라운드** 돌려(적발→수정→재검증) **P1 3건 · P2 8건**을 in-cycle 수정, 최종 라운드 판정 "No discrete correctness issues were identified."
  - **P1-1 확장 영역 hover 이탈** — 드러난 좌우 영역은 원 노드 bbox 밖이라 hit-grid 가 null 을 돌려 "이름 뒷부분을 보려 다가가면 카드가 닫히는" 깜빡임. → `hoverCardHit` 로 카드 사각형을 hover 유지 영역에 편입.
  - **P1-2 leave 후 카드 부활** — `pointerleave` 가 대기 중 프로브 rAF 를 취소하지 않아, 캔버스 안 낡은 좌표로 재판정해 커서가 떠난 뒤 카드가 되살아남. → `_cancelHoverProbe(true)`.
  - **P1-3 유령 카드(프레임버퍼 잔상)** — 축소 진행 카드만 정리한 경로가 `false` 를 반환해 호출부가 렌더를 생략, `autoStart:false` 라 마지막 프레임에 카드가 남음. → 정리 여부 집계에 outgoing 카드 포함.
  - **P2 (8건, 전부 수정)** — ①드래그 중 뒤늦은 rAF 프로브의 유령 카드(`_ptrDown` 가드) ②running desaturate 소실(`_nodeFillAlpha` 를 `_drawNode` 와 공유 + 불투명 베이스 플레이트로 라벨 비침 차단) ③미니맵 조작 시 카드 잔존 ④`pointercancel` 상태 고착 ⑤dim 노드 alpha 램프 중 이중 라벨(카드 상시 불투명으로 단순화) ⑥가장자리 칩 카드 클리핑(뷰포트 클램프) ⑦루틴 칩(`labelMaxWidth 176 > 칩 폭 150`) 역-팝(텍스트 가용폭을 박스 폭과 분리 보간) ⑧리사이즈·비-wheel 카메라 변경 시 클램프/대상 미재판정(`_revalidateHover`) + 미니맵 아래 가림(우측 경계 축소) + 카드 위 클릭이 캔버스/이웃으로 새는 문제(`_pick` tier0).
  - **평가 후 반려 1건 (P2, 코드 변경 없음)**: "`HOVER_EXPAND_MAXW`(460)가 화면 px 가 아니라 zoom 4 에서 1,840 CSS px 이 된다". 카드는 world 자식이라 노드와 **같은 배율**로 스케일되므로 상한을 화면 px 로 잡으면 같은 라벨이 줌마다 다르게 잘려(고배율에서 오히려 안 보임) 확장의 목적을 잃는다. 상한의 의도는 "그래프 대비 상대 크기 고정"(테이블 칩 3배)이며, 주석에 단위·근거를 명시하는 것으로 갈음.
- 요구 제약 2건의 충족 근거(기계적):
  - **「다른 노드의 위치를 뒤틀지 않도록」** — 확장은 `node.style.size/x/y` 를 포함한 scene 모델을 일절 변경하지 않고 별도 오버레이 레이어에만 그린다. 따라서 masonry/shelf-pack 배치·combo auto-fit bbox·`buildHitGrid`·미니맵 투영의 입력이 종전과 동일(reflow 0). 폭 변경을 모델에 반영하는 대안은 feature-0016 §45 가 이미 폐기한 경로(가변 폭 → setData 재packing).
  - **「z-order 유의」** — `_labelHoverLayer.zIndex=99998`. 전 노드 밴드(`_METZ` 최댓값 CTL=6)·엣지·combo 위, detail-hover-fx(99999) 아래. `world.sortableChildren=true` 라 삽입 순서 무관. 상태 halo 도 확장 폭에 맞춰 카드 위에 재구성해 원 노드 halo 가 카드 밖으로 삐져나오는 어긋남을 제거.
- 위험·범위: frontend-only, 서버·데이터·권한 표면 0. 실패 모드는 전부 시각적이며 fail-soft(카드 미생성 = 종전 동작). PixiJS 미배선/비브라우저에서는 no-op(import 부작용 0 계약 유지). G6 폴백 어댑터에는 본 기능이 없다(feature-detect 불필요 — 어댑터 내부 완결).
- §8.1 개선 제안(기록만, 미실행): 컬럼 circle 노드의 **바깥쪽** 라벨(`labelMaxWidth=168`)도 잘리지만, hit 영역이 11px 점이라 hover 로 열기 어려워 이번 범위에서 제외했다. 필요 시 별도 cycle 에서 "라벨 영역까지 hit 확장 + 우측 성장 pill" 로 다룬다.
- 미검증 범위: `[SKIPPED:tool-restricted:ux,design]` — 세션 도구제약으로 ux/design subagent 패널 미호출(위 채널 선택 근거). 시각·인터랙션 품질은 POST-DEPLOY PB-0008 실측으로 확정한다(§16.6 픽셀-클래스 변경 = 시각 캡처 필수).
- 검증: `node --check --input-type=module` PASS · `test_pixi_adapter.js` **180 PASS / 0 FAIL**(baseline 112 회귀 0 + T26 68) · `origin/main`(27 커밋) 리베이스 후 **그래프 headless 15 스위트 621 PASS / 0 FAIL**(같은 시각 landed `graph-edge-flow`(§83)와 동일 파일 auto-merge 정합 확인 — 코드 충돌 0, 문서 append 충돌만 양측 보존) · verify-completion `--pre-commit` PASS. Cross-ref: TASK/CHG-20260728T120530-graph-label-hover-expand · test-runs.d/20260728T120530-graph-label-hover-expand.md.

## REV-20260728T114015-graph-edge-flow [SKIPPED:session-policy-no-subagent] — 그래프 뷰 관계선 방향성 곡선 + 밀도 누적 + 부모 볼륨 다발 (TASK-20260728T114015-graph-edge-flow, Major §12.3, frontend-only 3모듈)
- Panel skip 사유(§18.8): 본 세션 사용자 환경 정책상 `Agent` tool 사용이 허용되지 않아 subagent 패널 미수행. 대신 **기계 검증 + 자체 적대 검토**로 대체하고 그 범위를 아래에 정직 기록한다(패널을 돌린 것처럼 기술하지 않는다).
- 대안 검증: 신규 계약 테스트 48 PASS(곡선 기하·스타일 어휘·빌드 계약 3층) + 그래프 전 스위트 536 PASS/0 FAIL + **적대 프로브**(main 시점 번들 대조 — OLD 는 읽기+쓰기를 1선으로 병합하고 화살표를 둘 다 잃음: `[{start:false,end:false,curve:0}]`, NEW 는 2선·양방향·곡선) + pytest/ruff 전량 PASS + 라이브 PB-0008(곡선·반투명 누적·다발·에러 0).
- 판단 근거 / 채택 대안:
  - **곡률 방향을 "진행방향 왼쪽 고정" 으로 둔 이유**: 읽기/쓰기를 색·대시로만 구분하면 두 선이 **같은 경로에 겹쳐** 하나로 보인다(종전 결함의 본질). 곡률 부호를 방향에 매면 왕복 관계가 기하적으로 갈라져 추가 인코딩 없이 분리된다 — Cytoscape.js 의 평행 엣지 자동 bezier 와 같은 어휘.
  - **강한 edge bundling 미채택**: 번들링이 clutter 를 줄이는 것은 맞지만, 사용자 연구상 **경로 추적 정확도·시간이 나빠진다**. 관계 추적이 이 화면의 핵심 과업이므로 저곡률(0.15, 상한 44px)만 쓰고 군집감은 alpha 누적으로 얻는다.
  - **밀도 인코딩을 alpha 누적에 맡긴 이유**: 별도 히트맵 레이어 없이 서로 다른 엣지 Graphics 가 자연 합성되어 허브 주변이 진해진다. 다만 가닥마다 `stroke()` 를 나눠 호출해야 겹침 대비가 생긴다(한 번에 stroke 하면 균일) — 구현상 함정이라 주석에 명시.
  - **부모 볼륨을 굵기 대신 가닥으로**: 굵기는 상한에서 포화(count 100 vs 1000 구별 불가)되고, 얇은 선 N개가 fill rate 상 유리하며 겹침 누적과도 정합.
  - **기본선 색을 `#cbd2db`→`#94a3b8` 로 진하게**: 굵기·alpha 를 함께 낮추면 옅은 색에서 "겹치기 전까지 아예 안 보이는" 구간이 생긴다. 색을 한 단계 올려 단독 가시성을 유지하고 누적 여지를 남겼다.
- 자체 적대 검토(H1~H8, 전부 반영 또는 근거 기록):
  · **H1 히트테스트 괴리(반영)**: 곡선으로 그리는데 히트 판정이 직선이면 호의 배(최대 44px)만큼 어긋난다 → `hitTestEdge` 를 곡선 인지로 확장, "호 위 점은 히트 / 직선 중점은 미히트" 를 테스트로 잠금(A9).
  · **H2 hover 강조 불일치(반영)**: 상세 패널 hover 강조선이 직선이면 곡선 관계선 옆을 스치는 별개 선이 된다 → `_edgeStyleBetween` 으로 같은 호 위에 겹치고, 역방향 등록 엣지는 곡률 부호를 뒤집어 동일 호를 얻는다(A10).
  · **H3 드래그 저품질 잔존(반영)**: `_refreshIncidentEdges` 가 `_objSig` 를 갱신하므로 lowFi 로 그린 도형이 '서명 동일=재사용' 으로 다음 full draw 에 살아남는다 → `_lowFiTouched` 누적 + `dragend` flush 에서 전량 고품질 재그림.
  · **H4 대시 위상 아티팩트(반영)**: 곡선을 폴리라인으로 쪼개 구간마다 대시를 리셋하면 경계에 대시가 뭉친다 → `dashPolyline` 이 위상을 이어붙이고, 총 on 길이가 직선 `dashSegments` 와 동치임을 테스트(A7).
  · **H5 화살촉 꺾임(반영)**: 곡선 끝에서 직선 각도로 화살촉을 그리면 선과 촉이 어긋난다 → 끝 접선(`b - c`) 각도 사용. 선이 얇아진 만큼 촉도 축소하되 alpha 는 올려 방향 가독성 보존.
  · **H6 얇은 선의 가시성 하락(근거 기록)**: 단독 가시성은 색 보정(H위 기본선)으로 보전했고, trusted/candidate 는 굵기·alpha 를 상대적으로 높게 유지해 신뢰 강도 서열이 종전과 동일하게 읽힌다(B2 테스트).
  · **H7 dim 경로 정합(검증)**: `dimIf` 가 `min(existing, 0.12)` 로 침강시키므로 명시된 `strokeOpacity` 와 정상 합성된다(하이라이트 시 focus 밖은 §67 대로 build 에서 제거되는 경로가 우선).
  · **H8 성능 회귀(근거 기록)**: 실선은 샘플링 0(네이티브 tessellation), 대시만 adaptive, 가닥은 ≤4 이고 집계·부모선에만 부여, 단일 가닥 경로는 배열 할당 제거. 대형 스코프 실측은 POST-DEPLOY 육안/프레임 관측으로 이월.
- 잔여 리스크(정직 표기): 가닥 **내부** 자기 겹침의 alpha 누적은 Pixi 배치 합성 방식에 의존해 헤드리스로 확정 불가 — 서로 다른 엣지 간 누적(요구 ② 의 본체)은 라이브에서 확인됐고, 가닥 내부는 벌어져 있어 영향이 작다. 읽기/쓰기 2선 육안·real-mouse 우클릭·드래그 추종은 POST-DEPLOY PB-0008 로 검증한다.

## REV-20260724T073848-conv-menu-order [SKIPPED:trivial-cosmetic-reorder] — 대화 목록 '···' 확장 메뉴 항목 순서 변경 (TASK-20260724T073848-conv-menu-order, Minor §12.3, frontend-only)
- Panel skip 사유(§18.8): 순수 렌더 순서 재정렬(`공유 → 이동 → 설정`) — 기존 3항목의 append 순서만 교체. 신규 로직·권한 게이트·onSelect 핸들러·action 인자·데이터 흐름·보안 표면 0. `folder.manage.own` 조건부 게이트·`conversation.share`/`conversation.read` action 불변. 적대 리뷰가 표면화할 correctness/security 리스크 없음 → SKIPPED 정당.
- 검증: `node --check` PASS · 항목 3종(공유/이동/설정) 전부 유지 · 순서를 assert 하는 테스트 부재 확인(`verify_settings_archive_leave.mjs` 존재검사만 — 재정렬 무영향; 선존 2 FAIL 은 HEAD 부터의 `makeItem` vs `make` 정규식 drift, 본 변경 무관).

## REV-20260724T053457-metadata-review-ds-scope-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T053457-metadata-review-ds-scope, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + REPORT 완결 + TASK 체크박스 + MODIFY CHG 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T053457-metadata-review-ds-scope(SHIP-WITH-FIXES, 3건 반영).
- 라이브 실측(실 Windows Chrome via `bin/win-browser.py`, https://localhost/admin, 배포 2b22b5ff): 검토 큐 datasource 필터(공용 96→mysql-kr-an1-auth 16, 전 행 해당 scope) · 배지 정합(96→16, Finding 1 MAJOR) · 자동승급 목록 가시(목록 84 중 82 자동등록) · 등록 시각 전 행 표시 · pageerror 0. 사용자 3결함 전부 해소.

## REV-20260724T053457-metadata-review-ds-scope [SUBAGENT:frontend-correctness-security] — 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 (TASK-20260724T053457, Major §12.3) — SHIP-WITH-FIXES (1 MAJOR/2 MINOR in-cycle 반영)
- 범위: `관리 콘솔 > 지식베이스 > 메타데이터 > [용어사전/ENUM/샘플쿼리]` 거버넌스 UI 3결함. 초안=frontend(admin.js): 검토 큐 scope_key 전송(Fix1)·큐↔목록 scope 정합(Fix2)·등록 시각 표시(Fix3).
- **적대 리뷰(general-purpose, frontend/correctness/security 렌즈) verdict = SHIP-WITH-FIXES → 지적 3건 전부 반영 후 SHIP**:
  · **Finding 1 (MAJOR, 반영)**: 검토 큐 리스트는 Fix1 로 scoped 됐으나 pending 배지는 여전히 unscoped(`count_glossary_feedback`/`count_enum_feedback` 가 scope_key 미적용) → 특정 ds 선택 시 리스트 N건 ↔ 배지 전체 건수 지속 불일치(Fix1 의도 정면 위반, 유일한 사용자-가시 오정보). **수정(backend additive)**: 두 count 함수에 `scope_key=None` 파라미터 추가(지정 시 `AND scope_key=%s`·`_normalize_scope_key`) + 엔드포인트(admin_metadata.py glossary-feedback/enum-feedback)가 `scope_filter` 전달 → 배지=scoped pending(리스트와 정합, '공용'=전체). 테스트 monkeypatch 시그니처 2건 동반 갱신(glossary-autoreg/enum-feedback).
  · **Finding 2 (MINOR, 반영)**: datasource 변경 시 배지 미재산정(list 보기·타 서브탭 stale). **수정(frontend)**: `_metaPrimeReviewBadge` 가 `_metaReviewScopeParam` 로 scope 전송 + scope-change 핸들러가 변경 시 배지 재-prime.
  · **Finding 3 (MINOR, 반영)**: sample 큐 날짜(`_sfFmtDt`, 무-prefix)가 glossary/ENUM(`_metaFmtDt`+"등록") 와 포맷·라벨 불일치. **수정(frontend)**: sample 큐 행·상세를 `등록 ${_metaFmtDt}` 로 통일.
- 리뷰 통과(NON-issue, 명시 검증): XSS 없음(전 created_at textContent/mkTag) · 크로스-DS 누출 없음(표시-측 narrowing·백엔드 RBAC=permission-based `kb.*.curate`·'공용'=권한 내 전체) · URL well-formed(`?scope_key`/`&scope_key` 정합·단일 encodeURIComponent) · created_at null-safe(전 가드+`_metaFmtDt` "" 폴백·미존재 시 기존 '수정만' 동작 보존) · 백엔드 3목록/3큐 모두 created_at 반환(no-op 아님) · scope 필터 3큐 균일 · enum bundle 경로 created_at 도달 · auto-promote write↔list read scope 정규화(`_normalize_scope_key`) 동일.
- 검증: `node --check`(ESM) PASS · `verify_metadata_list_detail.mjs` baseline 신규 회귀 0(26 PASS/3 FAIL·[D] crash=pre-existing) · py_compile(kb_glossary/admin_metadata) · pytest(feature-0003 metadata glossary-autoreg/enum-feedback/sample-curation 44 + feature-0002 glossary/enum 72) ALL PASS · 정적 자산 baked → POST-DEPLOY PB-0008 Windows-browser(정본, test-runs.d fragment 20260724T053457).

## REV-20260724T133000-csv-download-wiring-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T123600-csv-download-wiring, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + REPORT 완결 + TASK 체크박스 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T123600-csv-download-wiring(SHIP-WITH-FIXES).
- 라이브 실측(배포 dc316152, `bin/win-browser.py` relay 실 Windows Chrome 150, bootstrap_admin 세션): 대화 `20260724022429-515c0fd9`('도전 던전 전투 로그…' = 배틀 로그 차원별 집계, 16 메시지) 인라인 ```csv``` 블록 아래 "📥 CSV 다운로드" 버튼 렌더(visible·ready=1·linkAfter=false)·클릭 시 Blob `text/csv;charset=utf-8;` size=2603 다운로드 트리거·콘솔 에러 0. 서빙 app.js/share.js/styles.css 신 심볼 curl 확증. 사용자 요청("CSV 다운로드 가능 답변인데 실제 다운로드 수단 없음") 해소.

## REV-20260724T123600-csv-download-wiring [SUBAGENT:adversarial-review] — assistant "CSV 다운로드 가능" 답변의 실제 다운로드 배선 누락 수정 (TASK-20260724T123600-csv-download-wiring, Major cross-cut) — SHIP-WITH-FIXES (2 MAJOR/MINOR in-cycle 반영)
- 범위: 프론트 `static/{app.js,share.js,styles.css}` + cross-cut feature-0002 `agent_core.py`(`_collapse_large_csv_blocks`/`_collapse_result_blocks`)·`modules/tools.py`(가이던스). §18.8 적대 리뷰(general-purpose subagent, 전 파일 Read·양 렌더 파이프라인·sanitize·재사용 헬퍼·테스트 정독).
- **[MAJOR] 반영**: share.js `enhanceCsvBlockDownloads` 가 app.js 의 "`/api/file` 링크 뒤따름 → 버튼 skip" 가드를 누락 → 백엔드가 절단한 5행 미리보기 블록에 공유 뷰가 "CSV 다운로드" 버튼을 붙여 *일부 행만 받는 오해*(markExternalLinks 가 /api/file 링크를 익명 401 외부링크로 만들어 유일 작동 다운로드가 5행 버튼). **수정**: app.js 동형 skip 가드를 share.js 에 미러(nextElementSibling `a[href*="/api/file?"]` → skip + csvDownloadReady 마킹). .mjs 회귀 잠금 2건 추가(share/2).
- **[MINOR] 반영**: `_collapse_large_tables` 와 `_collapse_large_csv_blocks` 가 각자 `used[]` 를 생성 → 한 답변에 같은 결과가 MD표+```csv 양쪽이면 이중 링크(무해) 또는 token-less 동일-컬럼수 2 CSV 엇갈림 오링크(희소). **수정**: `_collapse_result_blocks(answer, csv_paths)` 통합 wrapper 신설 — 공유 `sigs`/`used` 로 두 패스 순차 적용. 두 collapse 함수에 `_sigs`/`_used` optional 파라미터(기본 자체계산 — 단독 호출 테스트 하위호환) 추가. 3 호출부(초안·redteam 수정·최종) 전부 wrapper 로 통일. pytest 회귀 잠금(`test_collapse_result_blocks_shared_used_no_double_link` — 링크 정확히 1개).
- **[MINOR doc drift] 반영**: `feature-0002/docs/AGENT_CORE_INTERNALS.md:127` 의 폐기된 "CSV 링크를 제공하세요" 서술을 새 가이던스(다운로드 버튼 자동 제공·`_collapse_result_blocks`·프론트 `enhanceCsvBlockDownloads`)로 갱신.
- **결함 없음 확인(리뷰어 근거)**: app.js — sanitize 이후 라이브 DOM 동작·`textContent` 만 사용(XSS 무첨가)·skip 로직 정합·비-csv/멱등/빈블록 무영향·BOM+revokeObjectURL. share 누출 축 — `codeEl.textContent`(이미 가시·sanitize된 본문)만 저장, /api/file·step csv_paths 미접근(redaction 무우회, fail-closed). `_collapse_large_csv_blocks` — 미닫힘 펜스/헤더-only/threshold 경계/no-match 원문보존/미리보기 트림 데이터손실 없음·3 red-team 경로 대칭. tools.py — csv_path=None 게이트로 없는 다운로드 약속 안 함.
- 검증: 전체 pytest **2305 passed / 2 skipped** · jsdom `verify_csv_block_download.mjs` **22 PASS**(app 13 + share 4 + static 5, share skip 가드 회귀 잠금 포함) · `node --check`. CHECK#13 = test-runs.d Windows-browser fragment(PRE-COMMIT 자동검증 + POST-DEPLOY 라이브 PB-0008). Verdict: **SHIP-WITH-FIXES → 반영 완료, SHIP**.

## REV-20260724T033500-graph-emoji-color-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T031956-graph-emoji-color, 비-정책 doc-only)
- Panel skip 사유(§18.8): TEST.md POST-DEPLOY 결과 append + TASK 체크박스 완료 + MODIFY 갱신 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T031956-graph-emoji-color(SHIP).
- 라이브 실측(배포 c709ad3f, `bin/win-browser.py` relay 실 Windows Chrome): 서빙 graph-renderer-pixi.js 에 fix(hasEmoji 게이트·emoji 폰트) curl 확증. 버그 유발 조건(dark labelFill `#161b22` + emoji 폰트 스택) canvas fillText chroma 프로브 — 6종 컬러(📊217·💳255·📜75·📘177·📦214·🗂255)·3종 그레이스케일(👤·🔗·⚙️=0, Segoe 폰트 디자인, 실 글리프). 9종 전부 flat 틴트 실루엣 아님 → 사용자 리포트("테이블 노드 일부 이모지 검은색 실루엣") 해소 확인.

## REV-20260724T031956-graph-emoji-color [SUBAGENT:adversarial-frontend] — 그래프 뷰 테이블 노드 역할 이모지 검은 실루엣 렌더 수정 (TASK-20260724T031956-graph-emoji-color, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/graph/graph-renderer-pixi.js`(+`hasEmoji` 순수 헬퍼 · `_makeText` BitmapText 게이트에 `!hasEmoji` · Text 폴백 fontFamily 색 이모지 폰트) · `tests/headless/test_pixi_adapter.js`(T20b 16-assert). §18.8 적대 패널(general-purpose subagent, 정확성+회귀+성능+fillStyle+혼합라벨 5렌즈) — 결함 적발 목적, 실 소스 882줄+소비처 계약+PixiJS v8.19.0 실측 프로브.
- **VERDICT: SHIP — BLOCKING 결함 0.** 5개 렌즈 전부 REFUTED:
  - **정확성 REFUTED**: 실측 프로브로 역할 아이콘 9종(📘👤💳📜🔗📊📦🗂 전부 1F000-1FAFF, ⚙️=2699+FE0F) 전량 매칭·누락 0. 평문/컨트롤(`−`2212·`+`·`ƒ`0192·`×`·한글·col-lod 배지 `▤`25A4·`…`2026) 비매칭 → 과강등 0(BitmapText 최적 경로 보존). 과매칭 가능 심볼(✓/★/⌘)은 `graph-ctxmenu.js` **DOM 버튼**에만 존재, `_makeText` 를 타는 Pixi labelText 엔 0건 → 실현 안 되는 이론적 여지.
  - **회귀 REFUTED**: PixiJS v8.19.0 `Text`·`BitmapText` 는 공통 `AbstractText`(anchor·text·width)+`ViewContainer`(position) 상속 — 소비처(`_label`·`_ellipsize`·`_drawCombo`·`_paintEdge`)가 쓰는 4 API 양쪽 동일 계약. 강등 시 파손 0. (`_ellipsize` 선두 서로게이트 슬라이싱은 **기존** 동작·실 maxW=140 에서 미발동 → 회귀 아님, nit.)
  - **성능 REFUTED-as-blocking**: 이모지는 분석완료 테이블 칩에만 부착(컬럼·미분석표·접힌 카드 0) → 대량 요소 컬럼 라벨은 전부 BitmapText atlas 배칭 유지. 강등분은 viewport-cull(§67) bounded + render-on-demand(매 프레임 아님) → draw-call 폭증 아님. `hasEmoji` 리터럴 regex(V8 캐시) µs.
  - **fillStyle 무시 REFUTED**: 색 이모지 폰트(Segoe COLR/CPAL·Apple sbix·Noto CBDT)는 canvas fillText 시 색 레이어 자체 렌더·fillStyle 무시(표준). Pixi v8 `Text`=canvas2D 래스터(white-base+tint 아님, tint 미설정) → 이모지 색 채널 보존·fill/tint 로 어두워질 위험 0.
  - **혼합 라벨 REFUTED**: "📊 stats_daily" → 평문 "stats_daily" 는 `fill`(dark=#161b22, 노란 칩 대비 확보) 정상 적용, 📊 만 네이티브 색. 평문 색 손실 0.
- 설계 정합: BitmapText 는 색 이모지 미지원 → PIXI.Text 강등이 Pixi v8 문서화 정석. 기존 "비-hex 색→col.valid=false→Text 강등" seam(L189-190) 과 동형 편입.
- 비-blocking 유의(반영): ① **[필수 게이트]** 실 색 렌더 증적은 PB-0008 win-browser 실측 필수(규약 visual_verification_scope=always) — T20b 는 regex 만 커버, 수정전 실루엣 재현→수정후 색 렌더 라이브 캡처는 배포 후 잔여(deploy_scope: included). ② `_ellipsize` nit·③ regex 과매칭 심볼(Pixi 라벨 미사용)=무해 → 코드 수정 불요.
- 검증: `node --check --input-type=module` PASS · `test_pixi_adapter.js` **112 PASS / 0 FAIL**(기존 96 회귀 0 + T20b 16) · verify-completion #1~#16(§16.3) PASS. 라이브 PB-0008 는 배포 후. Cross-ref: TASK/CHG/TEST-20260724T031956-graph-emoji-color.

## REV-20260724T140000-share-scroll-bottom-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260724T112446-share-scroll-bottom, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + MODIFY/REPORT 갱신 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260724T112446-share-scroll-bottom(SHIP-WITH-FIXES).
- 라이브 실측(배포 94b4003a, `bin/win-browser.py` relay 실 Windows Chrome, 실 공유 링크 16-메시지 대화): AC-SSB-1 진입 scrollY 53282==maxY·atBottom=true·pageerror 0 · AC-SSB-3 top 스크롤 후 stayedAtTop(snap-back 없음) · AC-SSB-2 최종 54118px 안착. 서빙 /static/share.js 신 심볼 5종·dead window-load 소멸 curl 확증. 사용자 요청("공유 링크 진입 시 스크롤 맨 아래") 해소.

## REV-20260724T112446-share-scroll-bottom [SUBAGENT:adversarial-frontend] — 공유 대화 링크 진입 시 문서 스크롤 맨 아래 고정 (TASK-20260724T112446-share-scroll-bottom, Minor §12.3 frontend-only) — SHIP-WITH-FIXES
- 대상 diff: `static/share.js` 단일(+70) — 진입 `fetchShare→render` 체인에 `engageInitialBottomPin()` 1회 + `scrollShareToBottom`/`releaseShareBottomPin`/`onShareBottomPinKeydown` 신설 + `pageBranchShare`·`scrollShareMessageIntoCenter` 에서 명시 pin 해제. §18.8 적대 패널(general-purpose subagent, correctness+regression+UX 렌즈 9축) — 결함 적발 목적.
- **헤드라인 회귀 2건 CONFIRMED-OK**: (1) feature-0019 버전 페이징 위치보존(`pageBranchShare` savedY)과 진입 pin 이 싸우지 않음 — 페이저 클릭(마우스 click, wheel/touch/key 아님)이라 명시 `releaseShareBottomPin()`(savedY 캡처 전 선행)이 유일 방어이고 정상 배치·disconnect 후 재-fire 불가. (2) rail dot 점프(`scrollShareMessageIntoCenter`)도 함수 진입 즉시 명시 해제 → eased 스크롤과 무충돌. **BLOCKING/데이터-정확성 defect 0.**
- **누수/멱등 CONFIRMED-OK**: `releaseShareBottomPin` early-return 멱등 · observer disconnect+null · `{passive:true}` add ↔ 옵션 없는 remove 매칭 정상(passive 는 match key 아님) · repin 클로저 `_shareBottomPinActive` 가드. maxY 수식은 파일 내 기존 idiom(L216-217/L388)과 동치 · 빈 공유(messages 0)=maxY 0 no-op CONFIRMED-OK. scroll-behavior:smooth 부재 grep 확인(instant 진입 스크롤 정상, reduced-motion moot). fixed `.share-footer` 는 `.share-container` bottom padding 80px 로 마지막 메시지 안 가림(CONFIRMED-OK).
- **반영한 findings (SHIP-WITH-FIXES → 3건 흡수)**:
  - **[MINOR top-priority, finding#9] 고정 3s 상한이 느린 성장 놓침**: mermaid/외부 이미지가 3s 후 완료되면 pin 해제 후 최신 메시지가 fold 아래로 밀려 무거운 대화에서 "맨 아래" 계약 위배. → **성장 신호(ResizeObserver·img `load` capture)마다 리셋되는 settle 타이머(600ms) + 절대 상한(8s)** 으로 교체(고정 3s 폐기). 이미지 지연 로드 재고정 추가.
  - **[NIT, finding#3] dead `window load` 리스너 제거**: engage 는 resolved fetch promise 안에서 실행돼 window.load 는 이미 발화 → 무효 + 미제거 leak. → 삭제.
  - **[MINOR, finding#5] keydown 과다 트리거 + Tab yank**: any-key 해제가 keyboard/AT 사용자를 조기 해제. → **스크롤 의도 키(PageUp/Down·arrows·Home/End·Space)만** 해제 + **`focusin`** 해제 추가(Tab/클릭 focus 시 헤더로 focus-scroll 을 pin 이 방해하지 않도록).
- 검증: `node --check` PASS(수정 후) · verify-completion #1~#16(§16.3) · CHECK#13 test-runs.d Windows-browser fragment(PRE-COMMIT PASS + POST-DEPLOY 라이브 계획, headless layout 부재 사유). 라이브 PB-0008(AC-SSB-1~3)은 배포 후(deploy_scope: included). Cross-ref: TASK/CHG/TEST-20260724T112446-share-scroll-bottom.

## REV-20260722T105320-share-menu-perm-wiring-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260722T103254-share-menu-perm-wiring, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + evidence PNG 뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260722T103254-share-menu-perm-wiring(SHIP).
- 라이브 실측(배포 066cec5e, https://localhost/ bootstrap_admin, win-browser Chrome relay): 본인 대화 말풍선 ☰ 3항목(`여기서 분기`·`여기까지 공유`·`여기부터 공유`) 모두 `is-access-blocked` 없음(수정 전 공유 2항목 항상 blocked 회귀 복구)·`여기부터 공유` 클릭 → onSelect(beginShareFloor) 실행·floor arm 배너/마커 표시·pageerror 0. 서빙 app.js `conversation.share.create` action 리터럴 0.

## REV-20260722T103254-share-menu-perm-wiring [SUBAGENT:adversarial-security+ux] — 말풍선 ☰ '여기까지/여기부터 공유' 권한 연결(action 매핑) 회귀 수정 (TASK-20260722T103254-share-menu-perm-wiring, Minor §12.3 frontend-only) — SHIP
- 대상 diff: `static/app.js` 2줄(☰ 공유 항목 action `"conversation.share.create"`→`"conversation.share"`) + `tests/test_menu_action_permission_wiring.py` 신규. §18.8 적대 패널(general-purpose subagent, security/ux 렌즈) — 결함 적발 목적.
- **Q1 정확성 CONFIRMED-OK**: `"conversation.share"` → switch(app.js:606-607) → codes `["conversation.share.create"]` 정확 매핑. share.create 는 own/any 분기 없는 단일 flat 권한이라 ownership 분기 불요(rename/delete 와 다름). 형제 conv-item '공유'(app.js:7763)와 동작 동일 — `markAccessBlocked` 가 `blocked=!can("conversation.share.create")=false` 로 정상 활성.
- **Q2 인가 CONFIRMED-OK(무약화)**: `can()`(app.js:977-984)은 display-permissive(인자 무시·로그인=true) — 순수 표시 게이트 수정. diff 는 app.js(프론트)만. 백엔드 `create_conversation_share`(conversations.py:787-818) enforcement 불변·권위적: share.create 403·read.own/any 404·joinable owner 403·bounded-window widen-guard 403. 비권한 사용자는 pre-fix(즉시 client 토스트)→post-fix(백엔드 403 round-trip 토스트)로 **관측 차이만**, 신규 역량 부여 0(`beginShareFloor` 는 client-only, `onShareCeiling`→createConversationShare 는 guarded 엔드포인트).
- **Q3 형제 회귀 CONFIRMED-OK**: app.js `action:` 전수 6개(:7763 share·:7764 read·:7798 ask·:7805 create·:7816/:7821 share) 모두 처리 case. 권한 코드(`*.create`/`*.own`/`*.any`)를 action 으로 넘기는 다른 항목 0 → default 브랜치 히트 없음.
- **Q4 테스트 CONFIRMED-OK**: fixed 3 PASS·pre-fix HEAD 에서 `unresolved:['conversation.share.create']`로 2개 테스트 FAIL → **원 버그를 실제로 잡음**(no false-negative). CI 도달성 확인(collected dir·PYTHONPATH). 잠재 caveat(현재 미트리거·non-blocking): ① whole-file `action:` 정규식이 향후 비-메뉴 `action:` 리터럴에 false-positive 여지 ② double-quote 한정 ③ function-slice 앵커 의존. 코드베이스가 double-quote 통일이라 현 gap 0.
- **결론: SHIP — blocking defect 0.** 정확·인가 무약화(백엔드 권위적·미변경)·형제 회귀 없음·원 버그 잡는 테스트로 잠금. 라이브 실증 = POST-DEPLOY PB-0008. Cross-ref: CHG/TASK/FUNCTION/TEST-20260722T103254-share-menu-perm-wiring · test-runs.d fragment.

## REV-20260717T010501-doc-sync-rn-0717 [SKIPPED:non-policy-doc] — 릴리즈노트 07-16 블록 ‘연결 테스트’ 버튼 회귀 복구 fixed 항목 추가 (TASK-20260717T010501-doc-sync-rn-0717, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·비중복은 doc_sync 가 정본(feature-0003 REPORT/TASK ds-test-gate-fix + 07-13 블록 소개 대조) 대비 직접 검증.
- 적대 대조(정본): ds-test-gate-fix(REPORT 2026-07-16) = 07-13 출하·PB-0008 PASS 한 ‘연결 테스트’ 버튼이 perm-atomic-split(8e01cc24) 부작용으로 미직렬화 state.user.permissions 의존→항상 false→미렌더 회귀(라이브 b8658bee hasPermissions:false 실측), can() display-permissive 로 07-13 동작 복구·백엔드 enforcement 불변·POST-DEPLOY PB-0008 라이브 복구(87cbe5d8). 07-13 블록이 버튼을 type:new/work 로 소개 → 재소개 아닌 ‘보이지 않던 문제 수정’ fixed 프레이밍(중복 아님). feature-id/§/PR#/구현 누출 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(31 releases·07-16 head 5항목[admin 4·work 1]·07-15 보존 7·스키마·누출0) · verify_release_notes.mjs 33/34 PASS·1 FAIL(styles.css 스크롤 정규식 pre-existing false-negative, 본 cycle 미변경·feature-0003 소관).
- **cache-buster**: 소스 `?v=dev` 고정 — ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. index/admin.html 편집 0.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260717T010501-doc-sync-rn-0717 / META REV-20260717T010501-META-0039-doc-sync-0717(별도 commit) / 원천 PR #855/#856. **무인 스케줄 run — landing/배포는 cron wrapper v3 소유(스킬 로컬 commit 만).**

## REV-20260716T052500-ds-test-gate-fix-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 회귀 복구 라이브 기록 (TASK-20260716T051931-ds-test-gate-fix, 비-정책 doc-only)
- Panel skip 사유(§18.8): test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료뿐 — 코드/자산 0. 코드 리뷰 정본 = REV-20260716T051931-ds-test-gate-fix.
- 라이브 실측(배포 e6ca5e4b, https://localhost/ bootstrap_admin console_access, win-browser Chrome relay): DS 테스트 버튼 **14개 재렌더**(수정 전 0 — 회귀 복구)·클릭→"✓ 'mssql-dk-dev' 연결 성공 (13.6ms)" 상단 토스트·pageerror 0. 서빙 app.js `can("datasource.test")` 반영 확인.

## REV-20260716T051931-ds-test-gate-fix [SKIPPED:trivial-regression-fix-display-only] — 작업화면 데이터소스 '연결 테스트' 버튼 렌더 회귀 수정 (TASK-20260716T051931-ds-test-gate-fix, Minor §12.3)
- Panel skip 사유(§18.8): app.js **1줄** 변경(프론트 표시 게이트) — 백엔드 enforcement·스키마·RBAC·엔드포인트 shape 0. 보안 posture 불변(서버 `admin_test_datasource` 는 console.access+datasource.test 계속 요구). 07-13 출하·PB-0008 PASS 동작의 복구라 신규 설계 표면 없음. 라이브 실증은 POST-DEPLOY PB-0008.
- **회귀 진단**: perm-atomic-split(`8e01cc24`, 07-15 Critical)이 DS 테스트 버튼 프론트 게이트를 `Boolean(state.user?.permissions?.["datasource.test"])` 로 작성. `state.user.permissions` 는 이 코드베이스의 `/api/session` 에 부재(TASK-0098 "표시 허용 + backend 403" 컨벤션·`can()` 이 permissions 맵 미사용) → undefined→false → 버튼 전부 미렌더. 라이브 b8658bee 세션 실측 `user.permissions` 부재 확인.
- **수정**: `Boolean(state.user?.permissions?.["datasource.test"])` → `can("datasource.test")`(display-permissive, 컨벤션 정합). 순 게이트 = `!viewOnly && canOpenAdminConsole()`(07-13 동작 복구). datasource.test 미보유자는 백엔드 403 → apiFetch 공통 토스트.
- **관련 flag(별도 feature 소유)**: 동일 커밋 app.js ≈L2006 권한 표시 UI 도 `state.user?.permissions` 를 읽어 동일 부재 — 본 cycle scope 밖(그 기능 소유자에게 위임).
- **VERDICT: SHIP (회귀 복구·display-only·보안 무영향).**

## REV-20260716T120000-graph-search-groups-postverify [SKIPPED:post-deploy-visual-verification-reconciliation] — PB-0008 라이브 PASS 원장 정합 (docs-only, 코드 변경 0)
- Date: 2026-07-16
- Cycle: CHG-20260716T120000-graph-search-groups-postverify (test-runs.d Run 3 DEFERRED→PASS + TASK 체크박스), **Minor §12.3**.
- SKIPPED 사유: 순수 검증 원장 정합 — 런타임 코드 변경 0(§18.4 META docs-only). 기능 코드 적대검증은 REV-20260716T114705-graph-search-panel-groups(SHIP-WITH-FIXES, C1/C2/P1/P2 봉인)에서 완료. 본 cycle 은 배포·PB-0008 라이브(main 89c1e7b0) 결과 기록.
- 검증 결정적(라이브 실측): 8 스키마→카테고리 2단 접기·모두 접기/펼치기(C2 라벨 정합)·검색 이력 뒤로(입력값·28건 복원)/앞으로·verbose 부제 부재·pageerror 0. 상세 test-runs.d/20260716T1147 Run 3.
- Cross-ref: REV-20260716T114705-graph-search-panel-groups / CHG-20260716T120000-graph-search-groups-postverify.

## REV-20260716T114705-graph-search-panel-groups [SUBAGENT:adversarial-frontend-correctness+ux] — 검색 결과 패널 3개선(2단 접기·검색 이력·간결화) SHIP-WITH-FIXES
- Date: 2026-07-16
- Cycle: TASK-20260716T114705-graph-search-panel-groups (검색 결과 2단 접기·검색 이력·설명문 간결화), **Minor §12.3** — 프론트 단독·additive.
- Trigger: §18.8 — UI/패널/상호작용 변경(ux) + 이력 상태머신·렌더 correctness. 적대 코드리뷰(general-purpose outside voice, 6축 REFUTE: XSS·접기 로직·이력 편입 루프/가드/정합·회귀·UX·JS 참조). 이력 시스템·esc·input 배선·`_metaRenderedIdFor` 싱크 교차검증.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0) — CONFIRMED 2 + PLAUSIBLE 2 흡수, 1 수용.
- **흡수한 CONFIRMED**:
  - **C1 (이력 forward 미절단)**: `_metaGraphRecordSearch` in-place 갱신이 `cur.v==="search"` 만 보고 forward 를 안 잘라, "뒤로→검색 항목→질의수정" 시 구 문맥 노드가 forward 에 잔존→앞으로가 무관 노드 복원. **수정**: in-place 시 `detailHistIdx < len-1` 이면 `splice(idx+1)` 로 forward 절단(노드/클러스터 새 방문 절단과 동형, top 갱신은 no-op).
  - **C2 (stale collapsed id 누적)**: `_searchGroupCollapsed` 가 검색 해제에서만 clear 돼, 다른 질의의 접힘 id 가 남아 `collapsed.size>0` 기반 "모두 접기/펼치기" 라벨 오표시·유령 부활. **수정**: 렌더마다 `currentIds`(이번 그룹 id 집합)로 collapsed prune → 현재 그룹만 반영.
- **흡수한 PLAUSIBLE**:
  - **P1 (복원 상태 드리프트)**: `_metaGraphRestoreSearch` 가 패널만 재구성하고 `mode`/`searchMatchNodes` 미복원→이후 클리어 판정(그 상태 의존) 드리프트. **수정**: 복원 시 `mode="search"` + `searchMatchNodes`=결과 key 집합 복원(캔버스 글로우 재적용은 back-nav 비용 회피 위해 생략 — 상태 정합만).
  - **P2 (질의문자열→카메라 focus, benign)**: `_metaGraphHistoryGo` 가 search 항목의 `ent.k`(질의)를 `_metaRenderedIdFor`/`AnimateFocus` 에 넘겨 우연 id 일치 시 오팬 가능. **수정**: `ent.v !== "search"` 가드로 search 항목 focus skip.
- **수용(P3, 무시가능)**: 이력 항목당 결과 노드 참조 캐시(≤50) — deep copy 아님·인메모리 전용(직렬화/localStorage 경로 없음)·`h.shift()` 회수, 연속 검색은 in-place 로 1항목. 무시 가능.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: XSS(전 문자열 esc·상태줄 q 는 textContent·상수 색/배지만 비-esc) · data-toggle/data-box 는 selector 미사용(getAttribute+parentElement)이라 제어문자/따옴표 안전, `\x01`(SOH) cat 구분자가 (scKey,cat) 경계 충돌 확실 차단 · 개별 접기 정합(Set+class+caret+aria 일괄, 헤딩은 body 형제라 이중 토글 없음) · 재검색 루프 없음(value 세팅은 input 미발화) · 항목 폭증 억제(top=search 만 in-place) · finding#5 해소 유효(검색=자기 이력 항목→captureScroll 정합, `_pendingDetailScroll` 은 v==="node" 게이팅) · 회귀 없음(nSchemas 제거 클린·matchBySchema/캔버스 글로우 불변) · 호이스트/import 정합.
- Verification: `node --check`(ESM) PASS · graph.css brace 245:245·comment 76:76 밸런스 · 4개 수정 재검증 PASS. **PB-0008 라이브는 POST-DEPLOY**(test-runs.d/20260716T1147 Run 3, visual_verification_scope: always).
- Cross-ref: CHG-20260716T114705-graph-search-panel-groups / TASK-20260716T114705 / CHG-20260716T013714-graph-search-detail-panel(원 기능·finding#5) / feature-0016(graph-detail-scroll 이력·스크롤).

## REV-20260716T015800-graph-search-detail-postverify [SKIPPED:post-deploy-visual-verification-reconciliation] — PB-0008 라이브 PASS 원장 정합 (docs-only, 코드 변경 0)
- Date: 2026-07-16
- Cycle: CHG-20260716T015800-graph-search-detail-postverify (test-runs.d Run 3 DEFERRED→PASS + TASK 체크박스), **Minor §12.3**.
- SKIPPED 사유: 순수 검증 원장 정합 — 런타임 코드·CSS·백엔드 변경 0(§18.4 META docs-only). 기능 코드 자체의 적대검증은 REV-20260716T013714-graph-search-detail-panel(frontend correctness+ux 7축, SHIP)에서 완료. 본 cycle 은 그 SHIP 후 배포·PB-0008 라이브 시각검증(main 03e8d1b0) 결과를 test-runs fragment 에 기록한 것.
- 검증 결정적(라이브 실측): 검색어 갱신→상세 패널 결과 리스트(코스튬 7건/플루토스 28건), match_via 배지(AI 분석/카테고리)+cluster_label+유사도, 행 클릭→노드 상세, 클리어→뷰 해제, pageerror 0. 상세는 test-runs.d/20260716T0137 Run 3.
- Cross-ref: REV-20260716T013714-graph-search-detail-panel / CHG-20260716T015800-graph-search-detail-postverify.

## REV-20260716T013714-graph-search-detail-panel [SUBAGENT:adversarial-frontend-correctness+ux] — 검색어 갱신 시 상세 패널에 검색 결과 구성 SHIP
- Date: 2026-07-16
- Cycle: TASK-20260716T013714-graph-search-detail-panel (그래프 뷰: 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성), **Minor §12.3** — feature-0003 프론트 단독·additive.
- Trigger: §18.8 — UI/패널/상호작용 변경(ux) + 렌더 correctness(XSS·리스너·stale). 적대 코드리뷰(general-purpose outside voice, 7축 REFUTE: XSS/이스케이프·리스너 누수·stale 레이스·클리어 마커·병렬 hunk·UX/접근성·JS 참조). 백엔드 계약(`search_nodes`/`_node_dict`)·병렬 세션 diff·다크모드 교차검증.
- VERDICT: **SHIP** (BLOCKER 0) — 7축 중 6축 결함 없음, 1축 저-심각도 cross-session 조정 항목.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: ①XSS — 전 사용자/DB 유래 문자열(name/fqn/cluster_label/key/q) `esc()` 통과, 미이스케이프 보간은 전부 상수맵(`_META_GRAPH_COLOR`)·하드코딩 배지 라벨·숫자(score/length)뿐. data-goto 큰따옴표 delimiter+esc 로 속성 탈출 불가, getAttribute 되읽기 이중인코딩 없음. ②리스너 누수 — innerHTML 교체 시 이전 li detach + 클로저가 지역 r 만 캡처 → GC 회수(파일 표준 패턴). ③stale 레이스 — 렌더 훅이 `seq!==_opSeq`·`q!==lastQuery` 두 가드 뒤, 연타 stale 폐기. ④클리어 마커 — `metaGraphSearchResults` id producer 는 내 코드 2곳뿐(showDetail/클러스터 상세 미생성), 결과클릭→노드상세 진입 시 마커 소멸→보존, 결과뷰 클리어 시 empty 복원(양방향 정확). ⑤UX — 배지 색(카테고리=앰버=글로우 계열·분석=블루·이름=회색) 정확, score 0 analysis-only 는 via 배지만·유사도 배지 억제, 결과 0건 전용 메시지, role/tabindex/Enter·Space(스크롤 차단). ⑥JS 참조 — import 심볼·호이스트·백엔드 필드 계약(match_via list·score·cluster_label) 일치, `Array.isArray` 방어.
- **Flagged cross-session (finding #5, PLAUSIBLE low — 양 브랜치 병합 후에만 발현, 타 브랜치 소유)**: 병렬 세션 `ai/claude/feature-0016-graph-detail-scroll`(session claude-session-4126879)이 추가하는 `_metaGraphHistoryCaptureScroll()`(`_metaGraphHistoryRecord` 내부)은 "상세 패널=항상 history 추적 뷰"를 가정해 현재 scrollTop 을 `detailHist[idx]` 에 스냅샷한다. 내 **검색 결과 뷰는 비-history 뷰**로 같은 aside 를 점유 → 결과행 클릭(`_metaGraphShowDetail`)로 history 기록 시 결과 리스트 스크롤이 직전 항목에 잘못 스냅샷돼 뒤로가기 스크롤 오복원 가능. **텍스트 병합 충돌 없음**(내 hunk L459/L572–579/L1260~ vs 저쪽 L625–659, 48줄 간격, 3-way clean). 그 함수는 저쪽 브랜치에만 존재해 내 트리에서 수정 불가 → **후행 병합 세션이 `_metaGraphHistoryCaptureScroll` 에 마커-스킵 가드**(`if (document.getElementById("metaGraphSearchResults")) return;`) 추가로 해소. SendMessage 로 해당 세션 통지 + 본 항목 REPORT 기록.
- **수용(very-low, 회귀 아님)**: (a) `.amgr-via-*` 텍스트 고정 다크 hex — admin 패널이 다크 root 팔레트 미보유(사실상 라이트 단일)라 현재 무해, graph.css 기존 53 하드코딩 hex 선례 정합. (b) `ul>li[role=button]` 이 implicit listitem role 대체 → SR 목록 시맨틱 very-low nit.
- Verification: `node --check`(ESM) PASS · graph.css brace 233:233 밸런스 · 정적/로직 리뷰 PASS. **PB-0008 라이브 시각검증은 POST-DEPLOY**(test-runs.d/20260716T0137-graph-search-detail-panel.md Run 3, visual_verification_scope: always).
- Cross-ref: CHG-20260716T013714-graph-search-detail-panel / TASK-20260716T013714-graph-search-detail-panel / feature-0002 CHG-20260716-graph-search-content-match(match_via 원천) / feature-0016 병렬 세션 graph-detail-scroll(finding #5).

## REV-20260715T140000-graph-ctxmenu-content-category-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T135725-graph-ctxmenu-content-category, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(DEFERRED→실측 PASS) + TASK 체크리스트 close + MODIFY/REVIEW 기록뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T135725-graph-ctxmenu-content-category [SUBAGENT] (SHIP)가 정본.
- 라이브 실측(win-browser Chrome 150, 배포 66722981): ① sim-group "방송 계정·3"(mysql-kr-an2-player dbGame) 우클릭 → **컨텐츠 카테고리** 메뉴(헤더 "방송 계정·테이블 3" + 소속 스키마 상세/접기(묶음)/묶음명 복사) / ② 밴드 위 스키마 클러스터(dbAuth) → **스키마**(band-wins 철회 복원) / ③ 제품 카테고리 밴드 → **카테고리** / 개별 테이블 → **테이블**(흡수 안 됨). 서빙 자산 baked(`_pickContext` 0)+브라우저 fetch 확인. 증거 scratchpad/evidence-content-category-menu.png.
- Cross-ref: REV-20260715T135725-graph-ctxmenu-content-category(기능 정본) · CHG-20260715T140000-graph-ctxmenu-content-category-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T135725-graph-ctxmenu-content-category [SUBAGENT:adversarial-content-category-review] — 그래프 우클릭 3대상 정합: 컨텐츠 카테고리(sim-group) 메뉴 신설 + band-wins 철회 (TASK-20260715T135725-graph-ctxmenu-content-category, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰 — 8가설 전수 공격(band-wins 철회 dead-ref · GX 라우팅 · groupInfo miss · separator · 접기 토글 · 소속 스키마 앵커 · badge 계약 · 테스트 자명통과) + 66/66 헤드리스 + ESM 문법 + 원본 계약 교차검증. **BLOCKING 0, 8가설 전수 REJECTED → SHIP**.
- 가설별(전부 REJECTED): H1 band-wins 철회 무결(pointerdown `down.hit=_pick`, button===2 가 `hit` emit + `_pickEdge`/canvas 폴백 보존, `_pickContext` 런타임 참조 0) · H2 GX 라우팅=사용자 명시 의도("GB/GH/GX 전용") · H3 `groupInfo.set(gm.key)` 와 GB/GH/GX push 가 **동일 forEach** → 우클릭 가능 그룹은 groupInfo 에 반드시 존재(label 빈문자 불가) · H4 separator `\u0001` 이스케이프·리터럴 0x01 0 · H5 접기 토글=GX 좌클릭 정본과 동일(full-key `groupCollapsed` 토글+`_metaG6Apply(false)`) · H6 소속 스키마 앵커=GB/GH 좌클릭(core:2345)과 **동일 추출** → `_metaGraphShowClusterDetailById` 계약 파리티 · H7 badge 필드 형태 카테고리/스키마 메뉴와 일치 · H8 T22 가 tier 로직 실행(GH z5>GB z1)+band-wins witness(pSC→SC:s1·`_pickContext` undefined), 자명통과 아님.
- NIT 처리(4건): ① [pixi:431] button===2 주석 GX 누락 → **수정**(주석에 GB/GH/GX 명시). ② [test:263-281] T22 가 `up()` dispatch 분기를 직접 미구동 + `_pickContext` 이름 결합(다른 이름 승격 재도입 미포착) → **수용**(우클릭이 이제 `_pick` 이라 T21/T22 의 `_pick` 계약이 곧 우클릭 계약; 이벤트 시뮬레이션은 헤드리스 범위 밖 · POST-DEPLOY PB-0008 라이브가 실 dispatch 커버). ③ [ctxmenu:307] groupInfo miss 폴백 label=원시 fam id → **수용**(H3 근거로 miss 도달 불가, 순수 방어·미관). ④ [core:2144] GX 우클릭이 접기 항목 포함 content-category 메뉴 = GX 기능 중복 → **수용**(사용자 명시 "GB/GH/GX 전용", 3요소 일관성 향상, 무해).
- Cross-ref: TASK/CHG-20260715T135725-graph-ctxmenu-content-category · **철회 대상 REV-20260715T114608-graph-ctxmenu-band-priority** · 유지 선행 REV-20260715T102901-graph-ctxmenu-hittest(WYSIWYG `_pick` 3-tier).

## REV-20260715T120000-graph-ctxmenu-band-priority-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T114608-graph-ctxmenu-band-priority, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(이연→실측 PASS)+TASK 체크리스트뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T114608-graph-ctxmenu-band-priority [SUBAGENT] (SHIP)가 정본.
- 라이브 실측(win-browser Chrome 150, 6a950a20): 밴드 위 클러스터 박스 우클릭→카테고리 메뉴 / 펼친 테이블 노드→그 테이블 / 좌클릭→클러스터 펼치기 정상. 사용자 결정 "밴드 우선" 라이브 충족. 증거 스크린샷 확보.
- Cross-ref: REV-20260715T114608-graph-ctxmenu-band-priority(기능 정본) · CHG-20260715T120000-graph-ctxmenu-band-priority-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T114608-graph-ctxmenu-band-priority [SUBAGENT:adversarial-band-wins-review] — 제품 카테고리 밴드 우클릭 band-wins (TASK-20260715T114608-graph-ctxmenu-band-priority, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰 — up()→_pickContext→emit→graph-core dispatch 전 경로 추적 + 68/68 테스트 + 좌표 기하 전수 재계산. 8가설 전수 REJECTED(무결).
- 가설별:
  - H1 좌클릭/드래그 보존: `_pickContext` 는 `d.button===2` 분기에서만 호출; onMove(pan/nodedrag)·좌클릭·더블클릭은 `d.hit`(=`_pick`) 사용 → **우클릭 전용 확정**. T21 이 `_pick` 계약 유지 잠금. (NIT: up 버튼 게이팅 자체는 코드리딩+T21 담보, pure 유닛 아님.)
  - H2 콘텐츠 노드 비흡수: 승격 조건 `__combo||kind==="schema-card"` — table/column/term/routine/ctl 전부 제외. T22 rTbl 가드.
  - H3 헤더/컨트롤: CATH(cat-hd)/CATX(cat-ctl)/GB/GH/GX 승격 대상 아님 → 자기 라우팅 그대로. T22 rHd 가드.
  - H4 밴드 밖 standalone: cat-bg=null→승격 skip. T22 rStand(schema-card) 가드. (NIT: standalone combo 미커버지만 로직상 `__combo` 유지→스키마, 회귀 없음.)
  - H5 미분류 밴드: `CAT:미분류` cat-bg 라 균일 적용 → 미분류 클러스터 우클릭=미분류 카테고리 메뉴. 결함 아님, 사용자 결정과 정합(관찰).
  - H6 _payload/kind 정합(핵심): 승격 시 raw cat-bg 노드(`__combo` 미부여) 반환 → `node:contextmenu`, id`"CAT:key"` → graph-core L2141 `/^CAT/`→`_metaGraphCtxForCategory`. combo→cat-bg 승격이 정확히 카테고리로 라우팅. 미승격 combo/SC 는 각자 경로.
  - H7 재-pick 좌표: button===2 는 finished=null(≤MOVE_THRESH 4px)일 때만 도달 → up 좌표 재-pick 이 down 과 동일. payload model 좌표도 up 이라 정합.
  - H8 T22 신뢰성: 좌표 기하(CAT 0..600×100..500·SC 125..275×170..230·combo 359..541×208..276·standalone 825..975×270..330) 코멘트 일치, 6 assertion 실효 가드. 68 PASS/0 FAIL.
- **판정: SHIP · BLOCKING 0**.
- NIT 처리: (1) up 버튼 게이팅 회귀 방지 = PB-0008 POST-DEPLOY 시나리오에 좌/우 분기 명문화(fragment (d) 좌클릭 펼치기 항목) — 수용. (2) T22 커버리지 갭(standalone combo·column·GB·미분류) = accept(로직상 회귀 없음). (3) 문서 = 본 cycle 에서 TASK/MODIFY/REPORT/FUNCTION/fragment 갱신 완료.
- 트레이드오프(사용자 수용): 밴드 내 클러스터 우클릭 스키마 메뉴는 좌클릭 드릴로 대체. 후속 '통합 메뉴' 여지(§8.1).
- Cross-ref: CHG/TASK-20260715T114608-graph-ctxmenu-band-priority · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md · 선행 REV-20260715T102901-graph-ctxmenu-hittest.

## REV-20260715T110000-graph-ctxmenu-hittest-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260715T102901-graph-ctxmenu-hittest, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY 섹션(이연→실측 PASS)+TASK 체크리스트뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260715T102901-graph-ctxmenu-hittest [SUBAGENT] (SHIP)가 정본.
- 라이브 실측 요지(win-browser Chrome 150, 배포 6ec5da4b→8098aee1): 제품-매핑 데이터소스 스키마그래프 CAT 밴드 2개에서 스키마 클러스터→"스키마" 메뉴 / 밴드 헤더·tint 여백→"카테고리" 메뉴 실증 — 세 사용자 증상(스키마↔카테고리 뒤바뀜) 전부 해소. WYSIWYG. 증거 스크린샷 확보.
- Cross-ref: REV-20260715T102901-graph-ctxmenu-hittest(기능 정본) · CHG-20260715T110000-graph-ctxmenu-hittest-postverify · test-runs.d POST-DEPLOY Run.

## REV-20260715T102901-graph-ctxmenu-hittest [SUBAGENT:adversarial-hittest-review] — 그래프 우클릭 메뉴 오라우팅 hit-test 층서 수정 (TASK-20260715T102901-graph-ctxmenu-hittest, Major §12.3 frontend-only) — SHIP
- Panel(§18.8): general-purpose 서브에이전트 적대 리뷰(코드 교차검증 + 라이브 테스트 62/62). 7가설 전수 판정.
- **핵심 소견**: 이 수정의 본질 = **hit-test 우선순위를 시각 z-페인트 순서와 정확히 정합**(WYSIWYG). `_METZ`(CAT_BG:-1 < COMBO:0 < GROUP_BG:1)에서 combo 는 cat-bg 와 group-bg 사이 유일 요소 → 3-tier(실노드 > combo > cat-bg)가 순수 z-order 를 정확 재현. 수정 전 node-first 는 비-node 인 combo 를 무시해 정합이 깨져 있었음.
- 가설별(전부 REJECTED=문제없음):
  - H1 드래그 회귀: CATH 헤더 리지드 이동·밴드 여백 드래그 tier1/tier3 로 **보존**; 밴드 내부 클러스터 빈배경 드래그는 수정 전 cat-bg 가 가로채 카테고리 통째 이동하던 것을 combo→클러스터 단독 이동으로 **복원**(graph-core L613 설계 주석 정합). 회귀 아님.
  - H2 GB/CAT 공존: GB(group-bg, z=1)는 tier1 유지 — cat-bg 만 tier3. 기존 동작 불변.
  - H3 엣지케이스: 접힌 카테고리(combo 부재→tier3 cat-bg)·terms combo·agg-lod 카드·카드/펼침 모드 전부 정상.
  - H4 `_isCatBg`: `data.kind==="cat-bg"` 방출은 graph-core L490 CAT: 배경 단일 지점; CATH(cat-hd)/CATX(cat-ctl)는 미매칭→tier1 유지(헤더 카테고리 메뉴 보존).
  - H5 성능: pointerdown 만 호출, tier3 단일 bucket 순회 — 무시 가능.
  - H6 증상 해소: "스키마 클러스터 빈배경→카테고리" 확정 해소, "밴드→스키마" 재발 불가(밴드 tint 여백은 tier3 카테고리, 클러스터 페인팅 영역은 tier2 스키마 = WYSIWYG), 헤더→카테고리 보존.
  - H7 테스트: T21 은 실효 가드(witness+실 `_pick` 호출; old 로 되돌리면 "빈배경→combo" FAIL). NIT: 합성 씬 하드코딩이라 data.kind 리네임/z-order drift 는 미포착(단일 방출 지점이라 위험 낮음).
- **판정: SHIP · BLOCKING 0**.
- NIT 처리: (1) diff 주석의 결함 (b)("카드/GB 가 밴드 위 우클릭을 스키마로 샜다→해소") over-claim 지적 → **수정 완료**(주석을 실 기전=combo 가로채기 + WYSIWYG 로 정정, 카드/클러스터가 밴드 위에 보이면 그 요소 메뉴가 정상임을 명시). (2) T21 합성 씬 미-import = accept(단일 방출 지점).
- 권고(비차단): POST-DEPLOY PB-0008 real-mouse 로 3대상(펼친 클러스터 빈배경/밴드 tint/헤더) 우클릭 + 밴드 내부 클러스터 단독 드래그 라이브 실측 → 본 cycle POST-DEPLOY 계획에 반영.
- Cross-ref: CHG/TASK-20260715T102901-graph-ctxmenu-hittest · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md.

## REV-20260714T183808-graph-ctxmenu-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY 라이브 검증 기록 (TASK-20260714T180125-graph-ctxmenu-category, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK 체크리스트 완료 + test-runs.d fragment POST-DEPLOY Run append 뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T180125-graph-ctxmenu-category [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] 가 정본.
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, 배포 154fb916): 배포 전달 + 라이브 도달성 + **수정 핸들러 우클릭 dispatch 파이프라인 실증** PASS. 리터럴 CAT 밴드 위 '카테고리' 메뉴 육안 = DEFERRED(제품-매핑 scope 필요 — 도달 가능 scope 가 전부 미분류라 밴드 미방출; 코드-로직 airtight + 파이프라인 실증으로 고신뢰, 사용자 1-probe 권장).
- Cross-ref: REV-20260714T180125-graph-ctxmenu-category(기능 정본) · CHG-20260714T183808-graph-ctxmenu-postverify · test-runs.d/20260714T180125-graph-ctxmenu-category.md POST-DEPLOY Run.

## REV-20260714T180125-graph-ctxmenu-category [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] — 그래프 카테고리 밴드 우클릭 전용 메뉴 (TASK-20260714T180125-graph-ctxmenu-category)
- Panel skip 사유(§18.8): 프론트 그래프 JS 2파일·additive(신규 메뉴 함수 1 + dispatch 1줄 라우팅 교체)·백엔드/RBAC/스키마/엔드포인트 0·비파괴. 위험 표면 = 우클릭 메뉴 dispatch 한정.
- 적대적 자가검토(4가설 refute): ① "CAT 밴드가 여전히 combo 로 fall-through" → **refute**: Pixi `_pick`(graph-renderer-pixi.js L446-451)은 node hit 을 combo 보다 우선(L448 `if(n) return n`), CAT 배경 노드는 밴드 전체 bbox(size:[bw,bh])이고 hit-grid 는 built.nodes 무필터 포함이라 밴드 영역 우클릭은 반드시 `node:contextmenu`(kindEvt=node) 도달 → L2086 전용 라우팅. combo fall-through 불가. ② "catKey 추출 오류" → **refute**: `id.replace(/^CAT(H|X)?:/, "")` 가 CAT:/CATH:/CATX: 3종 모두 cat.key 로 정규화(좌클릭 핸들러 slice(4/5)와 동치). ③ "의존 심볼 미정의" → **refute**: `_metaGraph.catLabelOf/catCollapsed/catMembers`(graph-state)·`_metaGraphShowCategoryDetail`(동일 파일)·`_metaG6Apply`/`_metaGraphCopyText`(import·기존 combo 메뉴에서 사용) 전부 존재 확인. ④ "접기 토글이 좌클릭 CATX 와 이중 발화" → **refute**: 우클릭 메뉴 onClick 은 catCollapsed 토글+`_metaG6Apply(false)` 1회, 좌클릭 CATX 경로와 독립(동시 발화 없음).
- 근거/대안: 대안A(L2085 hide 유지)=사용자 "밴드 우클릭 무반응/클러스터 오노출" 미해소로 기각. 대안B(combo 핸들러에서 CAT 분기)=hit-test 상 CAT 는 node 이벤트라 부적합. 채택=node 핸들러 전용 라우팅 + 전용 메뉴(combo 메뉴 구조 파리티: 상세·접기/펼치기·복사).
- deploy_scope: included(FIRST_REQUEST) 근거로 cycle-final 후 web 재배포 사전 승인. POST-DEPLOY PB-0008 라이브 잔여.
- Cross-ref: CHG-20260714T180125-graph-ctxmenu-category · test-runs.d/20260714T180125-graph-ctxmenu-category.md.

## REV-20260714T080000-account-subtabs-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260714T074417-account-subtabs, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK 체크리스트 완료 + TEST POST-DEPLOY append + MODIFY -postverify CHG뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T074417-account-subtabs [SUBAGENT] (SHIP)가 정본.
- 라이브 실측 요지: win-browser 실 Windows Chrome, 라이브 53e55bfe. 하위탭 4개·기본 account·각 전환 시 정확히 1 subpane 노출 assertion 전항목 PASS·서빙 심볼 확인·세그먼트 하위탭 바 시각 렌더(스크린샷). 1차 배포 soak false-positive 롤백→재배포 PASS(정적자산 /healthz 무관·동시부하 transient).
- Cross-ref: REV-20260714T074417-account-subtabs(기능 정본) · CHG-20260714T080000-account-subtabs-postverify · TEST Run POST-DEPLOY.

## REV-20260714T074417-account-subtabs [SUBAGENT:adversarial-diff-review] — 프로필 '계정' 탭 하위 세분화(계정/알림/UI/사용 내역) (TASK-20260714T074417-account-subtabs, Minor §12.3, frontend-only) — SHIP
- 렌즈: 적대 코드리뷰 서브에이전트(general-purpose) — diff 한정, 5축(섹션 배치 무손실/id 보존·lazy 렌더 정합·first-open 기본 하위탭·이벤트 배선·DOM/CSS 균형).
- **건전 확인(결함 0):** ① 7섹션이 4 subpane 에 정확히 1회씩 배치·손실/중복 0·필수 element id 20종 전부 정확히 1회(grep 확증). ② lazy 렌더 정합 — 활동 dl 은 openProfile→renderProfile 이 계속 채움(기본 노출 account subpane), 모든 change 핸들러는 initialize() 에서 getElementById/querySelectorAll 로 바인딩(=`.hidden` 무관 유효), renderNotifyPrefs/renderMotionPref/loadProfileUsage 는 display-only(SoT=localStorage/API)라 하위탭 활성 시 렌더 지연이 stale 유발 안 함, `dChk.disabled` interlock 은 change 핸들러+subpane open 에서 재적용, renderProfileTotp 는 innerHTML clear-후-rebind 라 반복 토글 리스너 누수 없음, 기존 테스트가 구 평면 구조 참조 0. ③ first-open — `state.accountSubtab` undefined→'account', 정적 HTML 기본값(account is-active/others hidden)이 switchAccountSubtab('account') 결과와 정확히 일치(오패널 flash 없음). ④ 이벤트 배선 — 하위탭 버튼 initialize() 1회 바인딩(중복 없음), openProfile 기본 prompt 탭+state.accountSubtab 세션 유지로 계정 재진입 시 마지막 하위탭 복원(의도 일치). ⑤ 구조 — pane div 균형 32/32, 전역 button reset 로 `.profile-subtab` UA chrome 없음, `state` 모듈 const.
- **Deferred NIT(비차단, 회귀 아님):** 하위탭 버튼에 role="tab"/aria-selected 는 있으나 subpane 에 role="tabpanel"·aria-controls/labelledby·화살표 roving 미비 — 단 부모 drawer-tab 은 role 자체가 없어 본 변경은 additive(퇴행 아님). 부모 탭 ARIA 정비와 함께 추후 일괄 개선 권장.
- **Verdict: SHIP** (blocking/major/minor 0, deferred a11y NIT 1).
- Cross-ref: TASK/CHG/FUNCTION-20260714T074417-account-subtabs · TEST Run(2026-07-14) account-subtabs · 선행 anim-effect-pref · ANCHOR 0003 무충돌.

## REV-20260714T073000-anim-effect-pref-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260714T065503-anim-effect-pref, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + MODIFY -postverify CHG뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260714T065503-anim-effect-pref [SUBAGENT] (FIX-THEN-SHIP→반영 후 SHIP)가 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지: win-browser 실 Windows Chrome, 라이브 f00519dd. 게이트 로직 assertion 전항목 PASS(off→reduced true·on→false OS무관·os→OS일치·data-motion 반영·select 3옵션+hydration·캘린더/검색 scrollMessagePointIntoCenter 라우팅)·서빙 자산 stamp/심볼 확인·프로필 계정 탭 select 시각 렌더(스크린샷). 한계: 검증 머신 reduce-motion off라 육안 모션 시연 불가(로직은 결정적 실증).
- Cross-ref: REV-20260714T065503-anim-effect-pref(기능 정본) · CHG-20260714T073000-anim-effect-pref-postverify · TEST Run POST-DEPLOY.

## REV-20260714T065503-anim-effect-pref [SUBAGENT:adversarial-diff-review] — 작업 화면 애니메이션 복원 + 인앱 "애니메이션 효과" 설정 (TASK-20260714T065503-anim-effect-pref, Major §12.3, frontend-only) — FIX-THEN-SHIP → 반영 후 SHIP
- 렌즈: 적대 코드리뷰 서브에이전트(general-purpose) — diff 한정, 5축(라우팅 등가성·회귀 표면/TDZ·접근성·UI 배선·null/예외 가드). §18.8 dispatch: UI/화면 신호 → ux/design 후보이나, 프론트 단독·비파괴·서버계약/RBAC/스키마 0 라 단일 적대 코드리뷰로 수행.
- **적발(MAJOR 1건, 반영):** 크로스페이드 고스트에 걸린 별도 CSS 미디어쿼리 `@media (prefers-reduced-motion: reduce) { .messages-switch-ghost { display:none } }`(styles.css) 는 인앱 pref 로 덮이지 않아, **OS reduce-motion ON + 인앱 '항상 켬'** 시나리오에서 JS 가드는 통과해 고스트를 생성하지만 CSS 가 `display:none` 으로 가려 "빈 화면 후 fade-in"(크로스페이드 아님)이 되어 **대표 효과(크로스페이드)가 정작 복원 안 되는** 결함. 이 시나리오가 바로 본 기능의 목적이자 POST-DEPLOY PB-0008 검증 항목. → **수정:** `html:not([data-motion="on"]) .messages-switch-ghost { display:none }` 로 이관(이미 init 배선된 `<html data-motion>` 속성 재사용 — 이로써 data-motion 이 "미래용"이 아니라 현재 필수임도 확인). 크래시/누수 없음(fallback 타이머가 숨은 고스트 정리)이라 순수 시각 결함이었음.
- **건전 확인(결함 없음):** ① 캘린더/검색 점프 라우팅(`scrollMessagePointIntoCenter`)은 기존 native `scrollIntoView({behavior:"smooth",block:"center"})`와 실무상 동형 — 타깃은 항상 `messageLogEl` 내부(point-rail dot 클릭과 동일 패턴)·`off`/reduce 시 `setter(to)` 즉시이동(no-op 아님)·`!messageLogEl` no-op 은 `#messageLog` 안정 요소라 불가. ② TDZ 없음 — `MOTION_PREF_KEY` const 접근자 전부 hoisted 함수 선언·런타임 호출(6124 이전 top-level 호출 경로 없음, `initialize()`는 그 뒤 실행). ③ 기본 `os`=기존 로직 byte-동치(회귀 표면 0). ④ localStorage read/write/setAttribute 전부 try/catch. ⑤ null 가드 존재(renderMotionPref·change 리스너·scrollMessagePointIntoCenter). ⑥ UI 배선 정확(`#motionEffectSelect` ∈ `data-profile-pane="security-and-account"`·renderMotionPref 동일 탭 dispatch). ⑦ 접근성 — 기본 `os`가 OS 신호 보존, 인앱 override 는 내부도구 정당 opt-in. `node --check app.js` PASS·잔여 native smooth-into-center 0(10503/10514 는 `block:"nearest"` 의도적 즉시).
- **Verdict: FIX-THEN-SHIP → MAJOR 반영 완료(styles.css data-motion 가드) → SHIP.**
- Cross-ref: TASK/CHG/FUNCTION-20260714T065503-anim-effect-pref · TEST Run(2026-07-14) anim-effect-pref · ANCHOR 0003 무충돌.

## REV-20260713T101500-ds-conn-test-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260713T094624-ds-conn-test, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 test-runs.d fragment POST-DEPLOY append + TASK.md 체크리스트 완료뿐 — 코드/자산/스키마/RBAC 0. 기능 적대 검증은 REV-20260713T094624-ds-conn-test(AGENT-TEAM 3렌즈 SHIP)가 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지(배포 02a1e585, https://localhost/ bootstrap_admin console_access, win-browser Chrome relay): AC-1 15 DS 배지 전부 `<button.product-dropup-item-ds--test>`(aria-label·min 24px·테두리)·AC-2 클릭→실 probe "✓ 연결 성공(11.8ms)" 토스트 top=66px(composer 769px 위, 입력창 비가림)·단발성 자동숨김·AC-4 제품 미전환(stopPropagation)·AC-5 프론트 쿨다운 "4초 후 다시" 발화·AC-6 admin `#adminToast` 하단 불변·AC-7 pageerror 0. Evidence scratchpad/ds-conn-test-postdeploy.png.

## REV-20260713T094624-ds-conn-test [AGENT-TEAM:backend+frontend+ux 3lens] — 작업화면 제품 드롭업 데이터소스 '연결 테스트' 버튼 + 상단 단발성 토스트 (TASK-20260713T094624-ds-conn-test, Major §12.3)
- §18.8 dispatch(UI/button/toast → ux·design / API·endpoint·throttle → backend·security / frontend correctness → qa) 3-렌즈 적대 패널. **적발 결함 전건 반영 후 SHIP**.
- **설계 결정(AskUserQuestion 2026-07-13)**: ① 연결 테스트 = **A2**(관리자 엔드포인트 `POST /api/admin/datasources/{key}/test` 재사용 — 별도 RBAC 추가 없음) + 남용 방지 프론트/백 재시도 텀. ② 상단 토스트 = **C2**(작업화면 전체 `#toast` 상단 앵커, admin `#adminToast` 하단 불변).
- **backend+security 렌즈 (BLOCKING/MAJOR 0)**: throttle check-and-set 이 이벤트루프 단일스레드에서 원자적(intra-worker TOCTOU 없음)·prune 반복 iteration-safe·성장 bound(≤3072)·conn 은 DI(yield) teardown 이 early-return 마다 close(누수 0)·429 는 authz(403) 이후라 무권한 존재 노출 없음·자격증명 비유출. 반영: **NIT-1** throttled 반환 `max(1.0, round(...))` 로 0.0 pass-sentinel 충돌 제거 · **NIT-2** `retry_after_ms` int 화 · **NIT-3** throttle 을 resolve/SSRF **이후·probe 직전**으로 이동(무-probe 404/SSRF 경로 미소진·404 마스킹 제거) · **NIT-4** 중복 guard 단순화 · **MINOR-1** env 파싱 try/except(오타로 web 모듈 import 죽음 방지). MINOR-2(게이트 폭=console_access ⊃ datasource.manage) 는 "표시 허용 + backend 403 fallback"(app.js `can()` TASK-0098) 관례 준수로 accept(REPORT §8).
- **frontend+QA 렌즈**: **HIGH** — 무조건 `canOpenAdminConsole()` 호출이 `verify_profile_icon_consistency.mjs` 하네스에서 `ReferenceError`(스텁 부재)로 테스트 전체 붕괴 → **하네스에 `canOpenAdminConsole` 스텁(false) 추가**. **MED-HIGH** — `is-testing`의 `pointer-events:none` 가 더블클릭을 부모(제품 선택)로 라우팅 → **실제 `<button>` + `disabled` 로 교체**(disabled 버튼은 클릭이 부모로 안 샘). **MED** — 쿨다운 `|| 0` sentinel 이 `performance.now()`에서 로드 4초 내 첫 클릭 오차단 → **`.has()` sentinel 로 수정**. LOW(단일/멀티 cdKey 상이·느린 테스트 시 진행토스트 조기소멸)=백엔드 429·is-testing 시각단서로 커버, accept. CORRECT 확인: 정상 클릭 stopPropagation·무권한 byte-동치 span·`_prev` 429 배지 상태 유지.
- **UX+a11y 렌즈**: **MAJOR-1** 중첩 인터랙티브(`span[role=button]` in `<button role=menuitem>` = 비적합 HTML+ARIA) → **행을 `<div role=menuitem tabindex>` (click+keydown 선택 복원) + DS 라벨을 실제 `<button>`** 으로(button-in-button 제거). **MAJOR-2** at-rest 어포던스 없음 → **가시 테두리 + hover 틴트**(display-only 배지와 구분). **MAJOR-3** 접근가능한 이름=DS키뿐 → **`aria-label="<key> 연결 테스트"`**. **MINOR-4** 터치타깃<24px → **min-height 24px**(WCAG 2.5.8). **MINOR-6** narrow 뷰포트 토스트 overflow → **`#toast max-width: min(460px, calc(100vw-32px))`**. **NIT-9** 배경색 snap → `#toast` transition 에 background 추가. MINOR-7(짧은 뷰포트 상단 토스트가 위로 열린 드롭업 상단 일부 가림)·NIT-8(테스트/비테스트 배지 2px 정렬차) = 엣지, accept. 확인: `#toast` id specificity 로 admin 격리·`box-sizing:border-box` 로 hover 무-reflow·단발성.
- **검증**: `node --check`(app.js·admin.js module) · `py_compile` · CSS 1780/1780 · 타깃 6/6 · **전체 1902 passed / 2 skipped / 0 failed**(회귀 0). 라이브=POST-DEPLOY PB-0008(win-browser relay 열림).
- **VERDICT: SHIP-WITH-FIXES → 전건 반영 후 SHIP.**

## REV-20260713T061500-attach-user-version-postverify [SKIPPED:non-policy-doc] — POST-DEPLOY PB-0008 라이브 검증 기록 (TASK-20260713T053423-attach-user-version, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 TEST.md §4(Windows-browser Run: 배포 후 잔여 → POST-DEPLOY 라이브 PASS)·TASK.md 체크리스트 완료·MODIFY.md postverify CHG 뿐 — 코드/자산/스키마/RBAC 0. 기능 코드 적대 검증은 직전 REV-20260713T053423-attach-user-version(SUBAGENT:security SHIP)이 정본. 본 엔트리는 배포 후 라이브 실측 결과 기록만.
- 라이브 실측 요지(배포 7f1ed748, https://localhost/ bootstrap_admin, win-browser Chrome/150): AC-AUV-1 v2 체인 편입(root 490)·AC-AUV-2 동일 멱등(491 reused)·AC-AUV-3/5 체인 정합(v1 superseded/v2 최신·목록 최신만)·**AC-AUV-4 assistant 가 v1→v2 diff 정확 인지**(SELECT 1→2·주석 추가; new_attachment_ids 미포함 턴엔 정직 "비교 불가"·환각 0)·AC-AUV-6 UI v2 배지+diff 색상 렌더. Evidence artifacts/shared/win-browser-shots-attach-user-version/01_version_badge_and_assistant_diff.png.

## REV-20260713T053423-attach-user-version [SUBAGENT:security 1lens] — 사용자 재업로드 첨부 버전 관리 (TASK-20260713T053423-attach-user-version, Major §12.3, cross-cut feature-0002)
- §18.8 dispatch(첨부 업로드 경로 + LLM 컨텍스트 + IDOR/인젝션 → security 렌즈) 적대적 리뷰 **VERDICT: SHIP (blocking/major 0)**. 7 렌즈(IDOR·체인무결성·인젝션·dedup누출·SELECT index·byte-동치·fail-soft) 전수 SAFE 판정 + MINOR 2 + NIT 1 → **전건 반영 후 재검 PASS**.
- **설계 결정(사용자 승인 3건, AskUserQuestion 2026-07-13)**: ① 재업로드 인식 = 파일명 자동감지(대화 내 동일 파일명·동일 account 최신 head 와 sha256 대조) ② assistant 인지 = 버전 표식 + 변경점 diff 자동 주입 ③ 과거 버전 비교 = 체인 정합 + assistant 비교(신규 UI 최소). 동일 해시 = 기존 재사용(멱등, "완전히 같은 파일이 아니라면 버전업" 요청 정합).
- **보수적 구현 결정**: 기존 assistant materialize 경로(`_materialize_assistant_attachment_edits`)를 **리팩터하지 않고** 사용자 버전 로직을 업로드 핸들러에 별도 구현 — 보안 리뷰 완료된 delicate 경로의 회귀 위험 회피(중복 ~수십 줄 수용, 향후 공통 `_append_attachment_version` 추출은 REPORT §8 개선 제안으로 기록). 체인 스코프를 `(ConversationId, AccountId, filename)` 로 둬 그룹 대화 타 멤버·타 대화 동명 파일과 혼입 차단(materialize 가드 2 대칭).
- **MINOR-1 (PLAUSIBLE, 수정)**: 동시 재업로드가 같은 `(root, version)` 선점 시 `UQ_WCA_VersionChain` 위반이 raw HTTP 500 으로 전파(materialize 는 graceful skip). **수정**: 버전 INSERT 를 `_insert_attachment_row(_ver)` 클로저로 추출, IntegrityError-류 예외 시 **버전 케이스만 체인 MAX+1 재계산 후 1회 재시도**(실패 시 rollback+깨끗한 500). 표준 업로드(prior 없음) 실패는 기존과 동일 500(rollback 보존). UNIQUE 가 데이터 무결성은 이미 보장 — 본 수정은 losing-request UX(500→성공/재시도).
- **MINOR-2 (CONFIRMED mechanic, 수정)**: `_datamark_untrusted` 이 `content` 만 sentinel strip 하고 `label` 은 미strip → 사용자 제어 파일명이 label 로 들어가면 위조 close 마커로 구획 breakout 가능(기존 `:814` 파일 본문 label 도 동일 벡터 — 본 diff 는 확장). **수정**: `_datamark_untrusted` 이 label 도 strip(전 caller 방어). 파일명이 datamark **밖** header(`### {fname}: vN→vM`)로 노출되는 부분은 기존 파일목록 라인(`file "{fname}"`)과 동일 계열(pre-existing) — 파일명 전역 sanitize 는 REPORT §8 후속 제안으로 기록(본 cycle scope 밖, 그룹은 force_sender_scope 로 cross-account 인젝션만 잔여).
- **NIT (수정)**: version_diff 를 매 턴 모든 버전 첨부에서 주입하면 "방금 변경" 문구 stale·토큰 낭비 → **이번 턴 신규 첨부(`attachment_id in new_ids_set`)에 한정** 주입. 재업로드 그 턴에 diff 주입(AC-AUV-4 충족) + 🔄v{n} 표식은 매 턴 유지(이후 턴 버전 인지·명시 비교는 버전 조회 API). 회귀 가드 테스트 `test_diff_not_injected_for_session_attachment` 추가.
- **검증**: py_compile 4 + node --check PASS · 첨부 버전 31→32 PASS(+session-gate) · `test_prompt_injection_defense`(datamark) 포함 재실행 EXIT=0 · 전체 스위트 EXIT=0(회귀 0). SELECT 컬럼 append 는 row[0..8] 보존 + `len(row)>10` 가드로 기존 9-tuple 테스트 무영향(리뷰 렌즈5 확인).
- Cross-ref: FUNCTION/TASK/REPORT/MODIFY-20260713T053423-attach-user-version · 기반 버전 인프라 TASK-0274/0275/0285/0286 · 스키마 alembic 0008 core_attachments. subagent: security 1lens(general-purpose 적대 리뷰).

## REV-20260707T110534-doc-sync-rn-0707 [SKIPPED:non-policy-doc] — 릴리즈노트 07-03/04/06/07 블록 신규(+29) + 캐시버스터 bump (TASK-20260707T110534-doc-sync-rn-0707, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync attended 재구성이 정본(각 feature REPORT/TASK + git log) 대비 직접 검증.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS(jsdom DOM 테스트 `verify_release_notes.mjs` 는 이 실행 env 에 jsdom 미설치 — 컨테이너 전용, 문법+스키마+블록 순서로 갈음). `generated`=2026-07-07·신규 4블록(07-03/04/06/07)·스키마(type/area/title/detail) 정합·07-02 이하 블록 보존. 누출 0(내부용어 feature-id/G6/AGE/alembic/엔드포인트/권한키/모델명/ADR/step_gap_ms/conn_health/xschema/WebRuntimeSettings 0). 07-03 역할 목록 매핑 포함. aiops-ttft 는 관리자 지표라 사용자 블록 제외(기술문서만).
- Cross-ref: CHG/TASK/FUNCTION-20260707T110534-doc-sync-rn-0707 / 원천 머지 feature-0016 그래프 07-03~07(ADR-010~021·alembic 0031~0038)·feature-0003 ds-avg-latency·aiops-ttft·reasoning-effort·runtime-settings(feature-0018)·feature-0009 gc-join-notice·share-visibility-window·feature-0002/0007 insight/fallback/edge-fallback. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260707T110534-META-0020-doc-sync-0707).
## REV-20260707T120000-runtime-settings-ux [SUBAGENT:design·ux 1lens] (TASK-20260707T120000-runtime-settings-ux — 런타임 설정 pane UI 재설계, web/UI CSS+JS-only, Major §12.3)
- 요청(사용자): "UI 세련도 부족 — 내부 디자인 리뷰 후 사람이 만족할 UI 로 재구성." 사전에 디자인 시스템 매핑(subagent) + 라이브 참조 pane 캡처로 콘솔 디자인 언어(정렬 grid dl·admin-badge·focus-ring 입력·commit-bar)를 근거화.
- §18.8 dispatch(UI/layout → ux·design) **적대 디자인/UX 렌즈 1차 VERDICT NO-SHIP** — 2 MAJOR + 5 MINOR + 4 NIT 적발. **전 항목 수정 후 SHIP**:
  - **MAJOR-1 (반응형 붕괴, styles.css)**: `@media(max-width:560px)` 가 grid-row 를 재설정하지 않아 컨트롤/상태가 라벨/설명과 겹침 → child 별 grid-row 명시(라벨1·설명2·컨트롤3·상태4) 단일열 스택으로 수정.
  - **MAJOR-2 (재-핀 트랩, admin.js)**: "동일값=예약취소" 가 override 케이스만 가드해, no-override 에서 기본값 그대로 입력 시 redundant PUT(override==default 고정, 모델예산 트랩 재현·pending 배지 잔류) → 조건을 `val === item.effective`(has_override 무관)로 일반화해 서버 현재상태 재현 시 항상 예약 해제.
  - **MINOR**: ① invalid-range 분기의 reset 버튼 라벨/동작 불일치("되돌리기"인데 RS_RESET 스테이지) → 라벨 "기본값" 동기화. ② status 11px 저대비(WCAG AA 미달) → 12px + darker(--text-2·--primary-dark·#b45309). ③ 설정 nav row pending 이 색-only 테두리뿐(콘솔 계정/역할 row 는 `•` dot) → `.admin-pending-dot` 추가. ④ 설명 1줄 ellipsis 로 잘림(구 wrapping 회귀) → 2줄 line-clamp. ⑤ 8px 그리드/`.admin-field` 이탈 값 정규화(gap24·col-gap16·padding12·input 8/10·112px·13px).
  - **NIT**: ① input radius --r-sm→--r-md(admin-field 정합) ② rs-unit min-width 제거 ③ rs-reset 터치타깃 padding 4/8 ④ rerenderRuntimeSettingsPanels 를 runtime pending 있을 때만(불필요 재-fetch 가드).
- 리뷰가 확인한 양호점: buildRuntimeSettingControl 깨끗 제거(dead-ref 0, 잔여 admin-quota-*는 별개 LLM-quota 편집기)·토큰 전부 실재·RS_MODEL_PREFIX 키 분류 정확·mountedPanels 미클리어라 rerender-gate 안전·commit-bar 추가 additive+null-guard(계정/역할/프롬프트 무위험)·상태 text-backed(색-only 아님)·aria-label·focus-ring.
- 검증: node --check PASS · CSS 중괄호 균형 · 기능/백엔드/엔드포인트 불변(표현 계층만). 최종 VISUAL 검증은 PB-0008 POST-DEPLOY before/after.
- Cross-ref: CHG/TASK/TEST 동일 slug · 선행 REV-20260706T094937-runtime-settings.

## REV-20260707T121500-runtime-settings-ux-postverify [SKIPPED:doc-only-postverify] (런타임 설정 UI 재설계 POST-DEPLOY PB-0008 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8/§18.4): 선행 UX 재설계(REV-20260707T120000-runtime-settings-ux [SUBAGENT:design·ux] SHIP)의 배포 후 라이브 시각검증 결과를 TEST.md 에 기록할 뿐 코드/자산 무변경(doc-only). 검증 자체(실 Windows Chrome PB-0008 before/after + commit-bar e2e + DB override roundtrip)가 정본 증적.
- Cross-ref: REV-20260707T120000-runtime-settings-ux · CHG-20260707T121500-runtime-settings-ux-postverify.

## REV-20260707T130000-reasoning-budgets [SUBAGENT:backend·ux 1lens] (TASK-20260707T130000-reasoning-budgets — 추론 강도별 예산 설정 + UI 교훈, Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared)
- 요청(사용자): "① 가시성 개선 교훈 기록(LRN-20260707-0001 verified 반영) ② `설정 > 모델별 추론 예산`에 추론 강도별 예산 토큰값 설정 추가."
- §18.8 dispatch(백엔드 precedence·API/RBAC·UI → backend·ux) **적대 렌즈 VERDICT SHIP** — 7개 벡터 정밀 검토, **BLOCKING/MAJOR/MINOR 0**:
  - **B1 무회귀(확인)**: `thinking_budget_for_level('normal')→None` 이라 `_call_llm` 의 reasoning-override 분기(agent_core.py) 미진입 → 모델 override 분기로 낙하. `reasoning_budget:high` 는 'normal'/미지정 요청에 절대 주입 불가(test_reasoning_effort precedence 테스트로 고정).
  - **precedence(확인)**: 명시 레벨이 reasoning 분기 선점 → `_think_budget` 비-None 이라 모델 override 분기 skip → 둘 다 설정 시 레벨이 모델보다 우선. override→12000, 미설정→기본 10000.
  - **clamp 안전(확인)**: override 는 resolver+validate 로 [1024,16000], `_call_llm` 이 `min(budget, max_tokens-1024)` 재-clamp → 16000<agent 20000, 신규 max 노출 없음(기존 effort cap 과 동일).
  - **serialize/endpoint(확인)**: `reasoning_budget:` vs `model_thinking_budget:` 키 startsWith 충돌 없음, 버킷 분리 정확. 기존 PUT/DELETE·validate_value·spec_for·audit 재사용(신규 로직 0). 프론트 `reasoning_budgets` 소비·빈 배열 graceful·pre-fill 정확(기본값이 실제 주입값).
  - **워커 패리티(확인)**: `_payload_to_kwargs → run_agent → 동일 _call_llm` — 별도 extra_body 구성 경로 없음, 우회 없음.
- **NIT 3(인지, 무해 — 미수정)**: ① reasoning row 의 `default_known` 은 프론트 미사용(모델 row 와 row shape 균일 유지 위해 보존) ② 테스트가 `_rs._cache['frozen']` 직접 리셋(기존 snap fixture 와 동일 패턴, 내부 테스트 한정) ③ 일부 테스트 `stmt; assert` one-liner. 모두 기능 무영향 — ship 후 정리 대상.
- 양호점: 기본값을 `thinking_budget_for_level` 로 동적 read(하드코딩 drift 없음), `_reasoning_budget_specs` 가 REASONING_LEVELS 증감에 자동 확장·None 레벨 자동 제외, memoization 유효, 대소문자 정규화 정합.
- 검증: 신규 테스트 +7(레지스트리 4 + _call_llm precedence 3) · **컨테이너 전체 스위트 RC=0** · 로컬 회귀 0. VISUAL 은 PB-0008 POST-DEPLOY(TEST.md §3).
- Cross-ref: CHG/TASK/FUNCTION/TEST 동일 slug · LRN-20260707-0001 · 선행 REV-20260706T094937-runtime-settings·-ux.

## REV-20260707T131500-reasoning-budgets-postverify [SKIPPED:doc-only-postverify] (추론 강도별 예산 POST-DEPLOY PB-0008 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8/§18.4): 선행 REV-20260707T130000-reasoning-budgets [SUBAGENT:backend·ux] SHIP 의 배포 후 라이브 검증 결과를 TEST.md 에 기록할 뿐 코드/자산 무변경(doc-only). 검증 자체(실 Windows Chrome PB-0008 + reasoning-key write-path e2e + 사용자 override 보존)가 정본 증적.
- Cross-ref: REV-20260707T130000-reasoning-budgets · CHG-20260707T131500-reasoning-budgets-postverify.
## REV-20260707T051054-kb-candidate-adoption [AGENT-TEAM:security-authz+backend-correctness+frontend-ux] (TASK-20260707-kb-candidate-adoption — 지식베이스 메타데이터 채택 인박스 + ENUM 대화 자율수집, Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared) — VERDICT: SHIP (BLOCKING 0 · MEDIUM 2 FIXED · LOW 2 FIXED + 1 ACCEPT-RESIDUAL · NIT 2 FIXED)
- §18.8 패널: staged diff(마이그·kb_glossary·llm·config·agent_core·app·admin_metadata·admin.html/js·styles.css) 대상 general-purpose 적대 서브에이전트 3렌즈 병렬 — 보안·인가 / 백엔드·정합성 / 프런트·UX. 각 렌즈는 "승인 아님, 결함 적발" 지시.
- **보안 렌즈**: **[MEDIUM FIXED]** `kb.enum.curate` 가 `_ensure_seed_roles` catchup(app.py) 명시 목록에 부재 → 기존 배포 admin 이 request-time 에 권한 미보유 → enum-feedback 3 엔드포인트 403(fail-closed lockout, 채택 인박스 ENUM 절반 사망). 주석은 "catchup 부여" 라 주장했으나 실제 목록에 없음(kb.glossary.curate·kb.sample.curate 도 동일 잠재 gap — 도입 cycle 누락). **수정**: catchup 목록에 `kb.enum.curate`+`kb.glossary.curate`+`kb.sample.curate` 추가(INSERT IGNORE 멱등, 내 인박스 양쪽 + 기존 glossary/sample lockout 동시 해소). **[LOW ACCEPT-RESIDUAL]** LLM-derived confidence 로 auto-promote(source='auto') 유도 가능(프롬프트 인젝션 "confidence 1.0") — 하이브리드 자동승급 설계 고유 잔여(용어사전 0021 승인 설계와 동일). 완화: auto 행 되돌리기 가능·rejected 재유입 차단(pre-check + ON CONFLICT WHERE pending)·0.9 임계·검토 큐. confidence 는 `llm_enum_suggest` 가 이미 [0,1] clamp → 실 파이프라인 무영향. 결함 아님(설계 인지 잔여). **검증 무결**: 엔드포인트 gating 3/3·least-privilege(operator/sales/pending 미부여·`_METADATA_MANUAL_IMPLIES` 미포함)·마이그 GRANT(0023 parity)·poisoning 순서(REV-20260629 BLOCKER clone)·XSS(textContent-only)·scope 격리(id+FOR UPDATE)·SQL 파라미터화 전부 PASS.
- **백엔드 렌즈**: **정합성 결함 0** — 용어사전 twin(0021/0023) 대비 line-by-line parity 확인(record/auto_promote/promote/reject/list/count SQL·컬럼순서·router r[0..14] 매핑·마이그 체인 0038→0039 단일 head·idempotent·set_updated_at·CHECK 값·`_enum_autopropose` double-wrapped soft-fail·config `__all__`·llm_enum_suggest 필터). **[NIT FIXED]** 마이그 docstring 이 source 도메인을 `manual|auto|auto_promoted` 로 표기(코드는 manual/auto 만·auto_promoted 는 feedback.status) → docstring 정정. **[cosmetic no-action]** `admin_list_enum_feedback` 가 `_metadata_iso` 직접 사용(glossary 는 `_glossary_feedback_iso`) — 후자가 전자의 1-line delegate 라 동작 동일.
- **프런트 렌즈**: **[MEDIUM FIXED]** 탭 pending 배지가 종류 필터로 좁혀진 부분 합계(`pendingTotal`)로 덮어써져, "용어사전" 필터 시 ENUM pending 이 배지에서 사라짐(전역 신호 훼손) → **수정**: `kind==='all'` 일 때만 부분 합계 사용, 좁혀졌으면 `_primeAdoptionBadge`(양쪽 재조회)로 정확도 보존. **[LOW FIXED]** 빈/로딩/오류 placeholder 가 grid 셀(440px)에 갇혀 좁게 렌더 + 로딩 노드가 empty 와 다른 미스타일 → `.admin-adoption-empty` 클래스 통일 + CSS `grid-column:1/-1`. **[NIT FIXED]** `_adoptionBucket(it)` 이중 호출 → 1회 계산. **[NIT no-action]** `.admin-meta-tag-kind` 고정 hex(다크 override 없음) — 기존 형제 태그(-ok/-warn/-role/-stale) 와 동일 규약이라 신규 결함 아님. **검증 무결**: fail-open 방지·first-entry 훅·per-kind 403 경로 없음·XSS·이벤트 배선 멱등(dataset.bound)·재사용 전역(_metaRoleLabel/_metaDatasourceLabelOf/apiFetch/can/showToast) 정의 확인·a11y(aria-label·aria-live) PASS.
- **재검증**: 수정 후 `node --check`·`py_compile` PASS. 관련 43 + 호스트 전체 스위트 **1582 passed**(회귀 0; share_redaction 7 = 컨테이너 `web.app` 경로 host-env 아티팩트, 본 변경 무관). catchup 목록 계약을 검사하는 테스트 없음(추가 3건 무회귀).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260707-kb-candidate-adoption · feature-0002 REPORT(2026-07-07).

## REV-20260707T064745-metadata-console-redesign [AGENT-TEAM:correctness-regression+xss-security+design-consistency] (TASK-20260707-metadata-console-redesign — 메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시, Major §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 1 FIXED · MAJOR 1 FIXED · HIGH 1 FIXED · MED 3 FIXED · LOW 5 FIXED · ACCEPT 1)
- §18.8 패널: 위임 구현(2차 보기 일반화 + ENUM/샘플 검토 큐 편입 + 디자인 폴리시 10종)의 uncommitted diff 대상 general-purpose 적대 서브에이전트 3렌즈 병렬(정합·회귀 / XSS·보안 / 디자인·일관성). 위임 구현이라 특히 엄격 검증.
- **정합 렌즈**: **[BLOCKING FIXED]** `kb.enum.curate` 가 `ADMIN_TAB_PERMISSIONS.metadata` OR-게이트에서 누락 → ENUM 검토 큐를 metadata 탭 하위로 이관했는데 enum-curate 단독 사용자가 metadata 탭 자체를 못 봐 접근 완전 상실(회귀). 대칭성 확증(kb.glossary.curate·kb.sample.curate 는 존재). **수정**: 게이트에 `kb.enum.curate` 추가. **[MAJOR FIXED]** ENUM 그룹핑이 `schema.table` 키+행 code-only 로 column_name 드롭 → 같은 테이블 두 컬럼의 동일 코드 모호. **수정**: `schema.table.column` 그룹 + 헤더 `table.column`. **[MINOR FIXED/ACCEPT]** feedback.status 서브탭 간 이월(수정) · 샘플 배지 백엔드 limit 캡 과소집계(accept — 백엔드 정본). **검증 무결**: dangling 참조 0·디스패치(kind별 로더)·필드 매핑(enum schema/table/column/code/suggested_label)·동적 버튼 idempotency(replaceChildren)·서브탭 가시성 OR·viewBySub 격리·CRUD 보존 전부 PASS.
- **XSS 렌즈**: **CLEAN** — 신규/변경 렌더(renderFeedbackQueue/renderSampleReview/_metaRenderGroupedList/_metaSyncViews/empty·loading·KPI/폼검증) 전부 createElement+textContent(SQL=pre>code.textContent). 오히려 구 innerHTML+esc 경로를 순수 DOM 으로 대체. 신규 innerHTML-with-data 0건.
- **디자인 렌즈**: **[HIGH FIXED]** light-only 콘솔(다크 팔레트 부재)에 `--surface-2`·`--tag-*` 다크 @media override 를 얹어 OS-dark 시 배지 저대비·카드/pill fill 소멸 회귀 → 다크 override **제거**(light 값이 정답). **[MED FIXED×3]** 스켈레톤 shimmer 무효(--surface-2==--border-subtle → 구분 grays) · `.admin-sf-row` 옛 divider 기하(→카드) · 싱글턴 그룹 카드 스팸(→1건은 flat 행). **[LOW FIXED×5]** KPI 가 #metadataCount 중복(→미기재 M 만·없으면 hide) · 카드행 focus-visible 부재(→ring) · role==provenance 파란색 충돌(→provenance=neutral gray) · vote 이모지(→추천/비추천 텍스트) · 글리프/color-mix nit. **잘 된 점**: light hover≠active 3-상태 분리·rich empty·인라인 검증·폼 grid·색-only 아님(텍스트 동반) 실효 확인.
- **재검증**: 수정 후 `node --check` OK · B1 게이트·H1 다크제거·M1 컬럼·L7 neutral·L5 KPI grep 확인 · 호스트 전체 **1637 passed**(회귀 0) · CSS 균형(1897/1897).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260707-metadata-console-redesign.

## REV-20260707T230501-doc-sync-rn-2305 [SKIPPED:non-policy-doc] — 릴리즈노트 07-07 블록 2항목 append(코드값 후보 채택 + 추론 강도별 예산) + 캐시버스터 bump (TASK-20260707T230501-doc-sync-rn-2305, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync(ULTRACODE 8-agent analyze+adversarial-verify 워크플로 wf_731a14ae)가 정본(feature-0002/0003 REPORT/TASK + git log) 대비 직접 검증.
- **적대 검증 반영(중복 catch)**: 워크플로 verify:release 가 초안의 item①(업무 용어+코드값 통합 채택)을 **과대주장으로 반증** — 업무 용어(glossary) 대화 자율수집·검토 큐는 2026-06-29 블록(라인 408·414)에 이미 landed. → item① 을 **코드값(ENUM) 측만으로 rescope**('용어사전' 표현 전량 제거), summary 도 동일 정정. 최종 append=2항목(코드값 채택 + 추론 강도별 예산).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS. jsdom DOM 테스트(`verify_release_notes.mjs`)는 이 실행 env 에 jsdom 미설치(컨테이너 전용) — 문법+스키마+블록 순서(07-07>06>04>03>02)+07-06 이하 보존으로 갈음. 누출 0(내부용어 feature-id/enum_feedback/kb_glossary/_enum_autopropose/kb.enum.curate/alembic/reasoning_budget/ADR/모델명 0). skip(비-사용자): 콘솔 IA(47a63b1a UI reorg)·그래프 화살표(b0d9deb6)·pane 재설계(a2fe4103)·OAuth cron(058fec05)·§56 sync(fe05d6f8·94e2e411).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260707T230501-doc-sync-rn-2305 / 원천 머지 0beb02e3(KB 채택 인박스+ENUM 자율수집)·d9516aee(추론 강도별 예산). META(STATUS·wiki·ARCHITECTURE noChange·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260707T230501-META-0021-doc-sync-0707-2305).

## REV-20260708T012922-metadata-console-polish [SKIPPED:minor-css-polish-post-visual-review] (TASK-20260708-metadata-console-polish — 메타데이터 콘솔 잔여 디자인 폴리시 5건, Minor §12.3 — feature-0003 web/UI 단독)
- Panel skip 사유(§18.4/§18.8): 본 cycle 은 선행 metadata-console-redesign(REV-20260707T064745, [AGENT-TEAM] SHIP + 배포 35e8cb14)의 **PB-0008 실 Windows 브라우저 적대적 미적 검증**(로그인→전 5서브뷰→2차 보기→그룹 카드→편집 폼 라이브 캡처·판정)에서 도출된 잔여 미세 폴리시 5건을 적용할 뿐이다. 즉 **적대적 디자인 리뷰가 이미 선행**됐고 본 변경은 그 findings 의 이행(순수 시각 CSS + confidence 배지 클래스 1개 교체 — 신규 로직 경로·백엔드/RBAC/스키마/구조 0). 코드 적대검증 대상 아님(§18.8 표 `[SKIPPED:*]`).
- 적용 findings: #1 2차 보기 필 위계 역전(borderless 경량화) · #2 list-detail sprawl(메타 전용 스코프 균형) · #3 그룹 cards-in-card nesting(divider 평탄화) · #4 반복 timestamp 노이즈(경량+그룹 내 숨김) · #5 신뢰도 배지 무리 속 매몰(accent 분리). 검증: node --check OK · CSS 균형(1905/1905) · route 골든 불변 · 호스트 1662 passed(회귀 0). POST-DEPLOY PB-0008 라이브 재확인이 본 폴리시의 정본 증적.
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260708-metadata-console-polish · 선행 REV-20260707T064745-metadata-console-redesign.

## REV-20260708T033320-metadata-console-ux2 [SUBAGENT:mainloop-adversarial-correctness+xss+coordination] (TASK-20260708-metadata-console-ux2 — 메타데이터 콘솔 UX 4건, Major §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 0 · MINOR 2 noted)
- 절차 주: 계획한 병렬 서브에이전트 §18.8 패널(정합/XSS/UX 3렌즈)이 **세션 사용량 한도**(reset 12:30 KST)로 스폰 실패. 이에 **메인 루프에서 diff 를 직접 적대 검증**하고, **PB-0008 라이브(배포 후)를 1차 행동 실증**으로 삼는다(한도 리셋 후 서브에이전트 패널 재실행 가능). 자기 재호출 wakeup 은 걸지 않음(CLAUDE.md 정책).
- **정합/coordination**: `_metaRenderReviewDetail`(우측 상세)·`_metaRenderDetail`(3555) 분기 정독 — review view+`reviewSelected.item` 시 상세 렌더(empty/폼/부트스트랩 hide), 아니면 reviewBox hide+clear. `reviewSelected` 초기화 3지점(보기전환 3198·스코프 3254·서브탭 3274) + 큐 (재)렌더 `_metaClearReviewDetail`(2538/8777). 목록 행 클릭(편집 폼)과 검토 행 클릭(read-only 상세)이 #metadataDetail 을 두고 오염 없이 분기. 액션(승급/거부=`_feedbackQueueAction`·승인/거부=`_sampleFeedbackAction`)은 행 핸들러 미러 → 성공 시 큐 리로드가 상세 초기화. **정합 무결**.
- **XSS**: 신규 렌더(review 상세·mermaid) 전부 createElement+textContent. mermaid 는 소스만 `.mermaid-pending` div.textContent 로 넣고 공용 `mermaid-render.js`(securityLevel:strict) 가 SVG sanitize — 원문 innerHTML 경로 0. #3 prefill 은 input.value 만. **clean**.
- **#4 mermaid API 정합**: `mermaid-render.js` 가 소비하는 노드(`.mermaid-pending`, renderMermaidDiagrams:65)와 신규 삽입 노드 일치. lib/헬퍼 부재 시 라벨 코드블록 폴백. `_metaIsMermaid` 정규식은 선두 mermaid 키워드만 — 일반 SQL 오탐면 무시가능(SQL 은 SELECT/WITH 로 시작).
- **MINOR(noted, 무영향)**: ① glossary/enum 상세 액션 버튼은 stopPropagation 미부여(상세 패널은 클릭행 아님 → 무해) ② `_metaIsMermaid` 가 'graph ' 로 시작하는 극단 SQL 을 오탐 가능(실무 무발생).
- Cross-ref: TASK/MODIFY/FUNCTION/TEST-20260708-metadata-console-ux2 · 선행 REV-20260708T012922-metadata-console-polish.

## REV-20260708T230501-doc-sync-rn-0708 [SKIPPED:non-policy-doc] — 릴리즈노트 07-08 블록 3항목 prepend(제품 분류 AI 제안·그래프 접힘 카드 시각화·콘솔 검토 화면 개선) + 캐시버스터 bump (TASK-20260708T230501-doc-sync-rn-0708, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`) + cache-buster(`index/admin.html`) 뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync(ULTRACODE 6-agent write+adversarial-verify 워크플로 wf_3891a205)가 정본(feature-0016 TASK §57/§59·REPORT + feature-0003 TASK/REPORT + git log) 대비 직접 검증.
- **적대 검증(정본 대조)**: 워크플로 verify:release-notes 가 3항목 전부 정본 실재 작업으로 확증(§59 Pending-only·§57 4시각 요소·콘솔 ux2+polish), feature-id/§/테이블/함수/ADR/마이그 누출 0(노출 'ENUM'·'AI 분류 제안'·'+코드 추가'는 실제 온스크린 라벨), 07-07 블록 대비 중복 0, cache-buster 양 파일 동시 bump, node --check PASS. §58(내부/infra)·§56 T56.9(기출시)·META 도구 제외 판정 타당성 확인.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · jsdom `verify_release_notes.mjs` 33/34 PASS(유일 FAIL=styles.css pre-existing·본 변경 무관·회귀 아님).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260708T230501-doc-sync-rn-0708 / 원천 머지 e035de8b(§59 제품 분류)·bd900515(§57 그래프)·7509fa71(콘솔 ux2)·afd3cfe6(폴리시). META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260708T230501-META-0022-doc-sync-0708).

## REV-20260709T113000-graph-toolbar-consolidate [SUBAGENT:frontend-correctness+layout+design-ux 3lens] (TASK-20260709-graph-toolbar-consolidate — 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거, Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016) — VERDICT: SHIP-WITH-FIXES (BLOCKING 0 · MAJOR 0 · MINOR 2 FIXED + 1 FIXED · NIT 1 FIXED + 3 ACCEPT)
- Panel(§18.8): 웹/UI CSS+HTML+JS 변경(사용자 상호작용 표면) → 적대 리뷰 서브에이전트 1기(correctness/regression · reflow·layout · design/ux 3렌즈). 통과 아닌 결함 적발 목적. diff HEAD + 원본 파일 직접 대조.
- **correctness/regression = clean**: 컨트롤 id 14/14 각 1회 보존(`getElementById` 바인딩 전부 resolve), 툴바 핸들러 전부 `if(!_metaGraph.bound)` 안(중복 리스너 0)·팝오버는 `voBtn._bound` 멱등 가드, 문서-클릭 닫힘 핸들러가 종류토글·select 조작에 조기 닫힘 안 함(whitelist), 버튼 open 은 `stopPropagation`.
- **reflow·layout = clean(주장 확증)**: 상태 pill `position:absolute`(흐름 밖) → '텍스트 길이가 아래 UI 밀기' 근원 제거. 캔버스 높이 체인 건전(wide=grid minmax(0,1fr)→wrapper flex:column→canvas flex:1 / narrow=canvas height clamp(dvh)가 basis, min-height:200px §18.8 M1 floor 유지), grid auto-placement(wrapper→col1·resizer→col2·detail→col3) 보존, 미니맵(canvas 내부 right-bottom) 무영향. a11y 개선(줌·상태가 `role=img` 캔버스 **밖 형제**, aria-live 유지).
- **적발 MINOR 2 + NIT 1 → 전부 FIXED**: ① 팝오버가 자기 라벨/여백 클릭에도 닫히던 오발(admin.js 문서-클릭) → 팝오버 내부 클릭은 '제품 카테고리'(뷰 전환 커밋)만 닫도록 수정 ② `.amg-viewopts-menu{left:0}` 이 좁은 pane(≲590px)에서 우측 clip(admin-workspace overflow:hidden) → `right:0` 앵커(좌측 여유로 펼침, 실브라우저 clip 0 실측 menuRight=438<paneRight=1218) ③ LOD '줌아웃 축약' 마커가 6s auto-fade 로 사라지던 것 → 마커 표시 중 fade 타이머 취소(지속 상태 유지). NIT `aria-haspopup="true"`(메뉴 위젯 의미) → disclosure 패턴이라 제거(aria-expanded+aria-controls 유지).
- **ACCEPT-RESIDUAL(NIT 3)**: 배지 표시/숨김 시 버튼 폭 변화로 초기화·상세 수평 이동(수직 reflow 아님 — 사용자 불만 재유발 안 함) · '스키마 이동' 가용성이 배지에 미반영(의도된 통합 tradeoff — 배지는 숨긴 종류만) · <~340px 초협폭 줌·미니맵 근접(현실 admin 폭 이하). 전부 비-차단.
- 검증: `node --check admin.js` PASS · 실 Windows Chrome 149(win-browser relay) 격리 harness 렌더 실측 — toolbar 자식 4·zoom/status `position:absolute`·status `-webkit-line-clamp:2`·494px 캡·팝오버 4행·종류 3버튼 단일행(h29)·배지·`right:0` clip 0. 스크린샷 harness-closed/open2/fixed.
- POST-DEPLOY PB-0008 라이브 확인 항목(TEST.md §3): 상단 4컨트롤·팝오버 개폐(바깥클릭/Esc·라벨클릭 무닫힘)·줌 오버레이·**상태 pill reflow 0(장문 상태에도 캔버스 높이 불변)**·LOD 마커/auto-fade·pageerror 0.

## REV-20260709T120000-graph-toolbar-consolidate-postverify [SKIPPED:doc-only-postverify] (graph-toolbar 배포 ee54b1ff POST-DEPLOY PB-0008 라이브 PASS 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8): 본 commit 은 TEST.md §3 POST-DEPLOY 실측 결과 append + TASK.md 체크박스 갱신뿐 — 코드·자산·정책 변경 0(doc-only). 코드 적대 검증은 원천 REV-20260709T113000-graph-toolbar-consolidate(SUBAGENT 3lens, SHIP-WITH-FIXES) 가 정본. 라이브 실측 provenance 는 TEST.md §3 POST-DEPLOY 갱신 항목.
- 실측 요지(win-browser Chrome/149, `https://localhost/` bootstrap_admin → /admin → 그래프 뷰): toolbarKids=4·zoom/status `position:absolute`·팝오버 open no-clip(menuRight 629<1249)·**reflow0=true(장문 상태 주입 전후 toolbarH 37→37·canvasTop 179→179·canvasH 572→572 불변)**·kindctl 제품개요 scope 맥락 display:none(기존 동작 보존)·pageerror 0. 사용자 리포트 2건(툴바 지저분·상태 reflow) 라이브 해소.

## REV-20260709T130000-ask-timeout-nonblocking [SUBAGENT:mainloop-adversarial-correctness+regression+ux 2round] (TASK-20260709-ask-timeout-nonblocking — 응답 지연 시 화면 전체를 덮던 타임아웃 복구 모달 제거, Minor §12.3 — feature-0003 web/UI 단독) — VERDICT: SHIP (BLOCKING 0 · MAJOR 1 FIXED · NIT 1 ACCEPT)
- Panel(§18.8): 메시지 전송 핵심 경로(sendPrompt catch)의 UI 동작 변경 → 적대 리뷰 서브에이전트 1기(정합/회귀·엣지·UX 3렌즈, 2라운드: 초기 적발 → 수정 → 재검). 통과 아닌 결함 적발 목적. diff + 원본 파일 직접 대조.
- **R1 적발 MAJOR(H1)**: 신규 대화 첫 메시지 타임아웃(earlyCid 활성) 흐름에서 인라인 "중단"(취소) 버튼이 무동작. 근본원인 = pre-existing `myAskInFlight` 키 불일치 — `busyKey`=pendingSentinel 로 add(`8640`)되나 earlyCid 활성 시(`8818~`) `askAbortControllers` 는 earlyCid 로 이관(`8864`)하면서 `myAskInFlight`/`busyConversations` 는 미이관 → `_myAskInFlightHere()`(`595-600`) false → sendBtn 핸들러가 `cancelCurrentRun` 라우팅 skip → 빈 입력 no-op. 구 타임아웃 모달의 "요청 취소"는 `/api/cancel` 직접 호출이라 이 잠복 버그를 가려왔고, 모달 제거가 노출. (즉시답변은 동작·답변 유실 없음 → non-blocking.)
- **수정(H1)**: early-cid 활성 블록에 `busyConversations.add(earlyCid)`/`myAskInFlight.add(earlyCid)`/`renderComposer()` 추가(askAbortControllers 이관과 대칭) + finally 에 `busyConversations.delete(askKey)`/`myAskInFlight.delete(askKey)` 추가(기존 abort/취소flag dual-delete 패턴 동형, leak 방지).
- **R2 재검(전 항목 REFUTED)**: `_myAskInFlightHere()` earlyCid 후 true → "중단" 라우팅 복원·즉시답변 노출(H1 해소). askKey finally 스코프 접근 가능(`const` 8873, try 8878 이전). non-early-cid 는 `askKey===busyKey` 라 dual-delete 가 no-op(무해). sentinel+earlyCid 공존은 소비자 전수(isCurrentConvBusy·R2/R3·9736/10283/10303)가 activeConversationId/isCurrentConvBusy 기반이라 오작동 없음. `renderComposer`(5204-5304)는 promptInput.value/focus 미변경(read-only hasText만)·`dataset.mode` 가드로 thrash 없음. cancelCurrentRun(early-cid)=`activeConversationId=earlyCid` 로 `/api/cancel` 정상.
- **H2~H7 (R1, 모두 REFUTED)**: 답변 유실 없음(attach terminal→refreshWorkspace, runId timeout payload 포착) · else 블록(진짜 실패=showToast+입력복원) 무결 · finally 미변경 정합 · 빈 askCid 도달 불가(+attach `!conversationId` 가드) · 잔존 실참조 0(주석만) · resume 경로(~9410) 독립 attach.
- **NIT(ACCEPT)**: early-cid 활성 시점 `renderComposer()`는 시각상 `8707` 렌더와 동일(실효 fix 는 state-set) — 방어적 재동기화로 정당, 무해.
- 검증: `node --check app.js` PASS(2회) · 코드 내 `showTimeoutRecoveryDialog` 실참조 0.
- Cross-ref: TASK/MODIFY/REPORT-20260709-ask-timeout-nonblocking · DESIGN-entry-points.md 모달 패턴 참조 갱신. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 라이브 실측(타임아웃 유발 시 화면 미가림·답변 자동 수신·기존/신규대화 양 흐름 인라인 취소/즉시답변 동작).

## REV-20260709T140000-ask-timeout-nonblocking-postverify [SKIPPED:doc-only-postverify] (ask-timeout-nonblocking 배포 4b6919ec POST-DEPLOY PB-0008 런타임 PASS 기록, 비-정책 doc-only)
- Panel skip 사유(§18.8): 본 commit 은 TEST.md §3 POST-DEPLOY 실측 결과 append + TASK.md 체크박스 flip + MODIFY 기록뿐 — 코드·자산·정책 변경 0(doc-only). 코드 적대 검증은 원천 REV-20260709T130000-ask-timeout-nonblocking(SUBAGENT 2R, SHIP) 가 정본. 라이브 실측 provenance 는 TEST.md §3 POST-DEPLOY 갱신 항목.
- 실측 요지(win-browser Chrome/149, `https://localhost/`): 무중단 배포 4b6919ec(soak PASS)·`/healthz` git_commit 일치. 서빙 app.js `typeof showTimeoutRecoveryDialog==="undefined"`(모달 런타임 완전 제거 — 사용자 신고 화면 전체 경고창 구조적 노출 불가)·attachAndWaitForResult 보존·composerFinalizeBtn/sendBtn DOM 존재·z-9999 backdrop 부재·pageerror 0. 사용자 리포트(응답 지연 시 화면 전체를 덮는 경고창) 라이브 해소.

## REV-20260711T115053-docs-archive [SKIPPED:mechanical-archiving] — MODIFY/REVIEW §5.5 아카이빙
- Related Change: CHG-20260711T115053-docs-archive. cycle: ai/claude-corp/feature-0003-docs-archive. 승인: 사용자 지시(2026-07-11) + §5.5/§5.6 규약 내 작업.
- SKIPPED 사유: 내용 판단이 없는 기계적 이관 — 검증이 그 자체로 결정적: ① head+archived+kept 재구성 md5 == 원본 md5 (양 문서, 스크립트 assert) ② 이관은 엔트리 경계(^## ) 단위 verbatim ③ 현행 파일 상단 아카이브 링크 + REPORT 압축 정보(§5.5 요건). 런타임 코드 0.
- Human Approval Needed: 아니오 — 비파괴(무손실·가역), append-only 규약 준수(기존 엔트리 의미 변경 0).

## REV-20260712T073000-item09-graph-split [SKIPPED:browser-qa-pending] — admin.js 그래프 분리
- Related: CHG-20260712T073000-item09-graph-split. 승인: 사용자 명시(blocked 해제). 자동검증 GREEN(module 문법·import/export 정합·undefined 0). 브라우저 QA(acceptance a) 사용자 게이트 대기 — 머지 전 필수.

## REV-20260712T190500-item09-batch23-stamp [SKIPPED:mechanical-move-machine-verified] — 그래프 세분화+스탬프 자동화
- Related: CHG-20260712T190500-item09-batch23-stamp. 순수 이동은 4중 기계검증(문법·verbatim·미해결참조·byte-eq)으로 대체, 신규 로직(inject_asset_stamp.py·asset_stamp_verify)은 census 실측(vendor 우연매치 12건 제외·pin 보존) 반영 + 멱등성 확인. PB-0008 실 Windows 브라우저 QA 통과(에러 0). 배포 시 asset_stamp_verify 가 주입 누락을 하드 차단.


## REV-20260713T102249-doc-sync-rn-0713 [SKIPPED:non-policy-doc] — 릴리즈노트 07-10 블록 7항목 prepend(관계도 성능·정리·상세 이동·강조 안정화·상단 툴바 / 타임아웃 모달 제거 / AI 능동 분석 '주의' 실질화 §69 / AI 분석 접속거부 조기 skip) (TASK-20260713T102249-doc-sync-rn-0713, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0016 REPORT/DECISIONS §57.4~76 + feature-0003 REPORT ask-timeout + feature-0002 REPORT mssql-auth-cooldown + feature-0016 §69 T69.5 POST-DEPLOY REPORT + git log) 대비 직접 검증.
- **07-10 run 대비 차이**: (a) §69 AI caveats 편입 — 07-10 run 이 T69.5 미완(라이브 미관측)으로 REJECT 했으나 07-13 PR #744 T69.5 완수(cc_data_main 재생성 715/715·0 failed·옛 자기-불평 사실상 0·사용자 원 리포트 해소)로 라이브 관측 가능 → 7번째 항목으로 편입. (b) cache-buster 수기 bump 제거 — 07-10 run 의 html `?v=` 수기 bump 은 ITEM-09 what#3(inject_asset_stamp.py content-hash 빌드주입) 도입 이전이라 재현 안 함(소스 `?v=dev` 고정). (c) landing/배포 소유=본 attended run(07-10 run 은 cron wrapper 위임).
- 적대 대조(정본): 07-09~10 사용자 화면 신규 = 그래프 §57.4~76(성능·정리·상세 내비·강조 안정화·툴바)·타임아웃 모달 제거·§69 caveats·MSSQL 접속거부 skip. 07-11~13 은 behavior-neutral(feature-0012 완결·ITEM-09 CSS/JS·META)라 사용자향 0. feature-id/§/테이블/함수/ADR/오류코드 누출 0, 07-08/07-09 블록 대비 중복 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · vm 파서 구조검증(블록 순서 07-10>07-09>…·항목 스키마·누출 스캔 0).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260713T102249-doc-sync-rn-0713 / 원천 머지 d87d582e(타임아웃 모달)·§60~76 그래프·10da986e(MSSQL cooldown)·PR #664/#744(§69 T69.5). META(STATUS·wiki·RELEASE_NOTES·meta/REVIEW)는 별도 commit/META mode(REV-20260713T102249-META-doc-sync-0713).

## REV-20260713T181800-graph-perm-split [SUBAGENT:security-lens-adversarial-PASS] — 그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리 (Critical §12.3 인증/인가, 사용자 승인 B안)
- **결정 근거**: 그래프 뷰 별도 탭 분리(feature-0016 §45)에 맞춘 권한 분리 요청. 위험등급 Critical(인증/인가) → 사람 승인 필수. **AskUserQuestion 로 하위호환 방식 확정 = B안(분리 + 기존 접근 보존, 비파괴)** — A안(완전 분리, 기존 보유자 접근 상실) 대비 현재 접근 회수 없음, 프로젝트의 일관된 "기존 배포 무손실" 패턴(task4·ITEM-11 등)과 정합. graph 는 read-only 권한이라 저위험이나, 인증/인가 구조 변경이므로 §18.8 보안 렌즈 적대 리뷰 수행.
- **§18.8 보안 렌즈 적대 서브에이전트(5축: 권한상승·접근상실·멱등/race·enforcement 일관성·SQL) — 라이브 MySQL 8.0.46 실증 포함**:
  - **FINDING A (MEDIUM, 권한상승) 적발·수정**: role 이 묶음 보유 + account 가 묶음 DENY override 인 계정은 분리 전 effective graph=False(묶음 꺼짐→미함의)였는데, 대상1 role backfill 이 role 에 graph.read 를 주면서 account 가 graph.read 를 새로 획득(과잉부여). → **대상3 추가**: 해당 계정(role 이 묶음 보유 + 묶음 DENY override + graph.read override 부재)에 graph.read DENY override 부여로 분리 전 effective(그래프 없음) 고정(role-scoped JOIN 으로 spurious DENY 회피).
  - **FINDING B (LOW, 멱등 방어) 적발·수정**: `bundle_pid/graph_pid` 부재 시 backfill 본문은 skip 되나 마커가 무조건 기록되어 "done" 오기록→backfill 영구 미실행 위험(정상경로 미도달이나 방어적). → **마커 기록을 `if bundle_pid>0 and graph_pid>0:` 본문 안으로 이동**(다음 startup 재시도 보장).
  - **FINDING C (NIT) 적발·수정**: `admin_metadata.py` 그래프 analyze/analyze-schema docstring 2곳이 "(우산 kb.ingest.manual 함의)" stale → "분리 후 독립 권한" 으로 갱신.
  - **CLEAN(적대 REFUTE 통과)**: (2) 접근상실 — 대상1(role 묶음보유)+대상2(계정 묶음 ALLOW override)로 전 보유자 커버, 명시 graph DENY 존중, OLD-True→NEW-False 경로 없음. **2-path 회귀(운영 재기동 fast path 가 slow path 의 `WebSchemaMigrations` DDL 미경유→backfill 영구 skip→전원 접근상실)를 backfill 함수 자체 `CREATE TABLE IF NOT EXISTS` 로 경로 독립화(리뷰 확인).** (3) 멱등/race — 마커 guard 정확, 자체 테이블 생성, 병렬 web-a/web-b 부트스트랩 PK+INSERT IGNORE+NOT EXISTS 로 benign, 마커 INSERT 실패=안전 재시도. (4) enforcement — 백엔드 `require_permission('metadata.graph.read')` 와 프론트 표시 모두 단일 `_apply_permission_overrides`/`_decorate_account_rows` 파생, 8개 graph 엔드포인트 단일 권한 게이트, 잔여 kb.ingest.manual OR-gate 없음, fail-open 없음. (5) SQL — 대상2 self-ref `INSERT...SELECT...NOT EXISTS` 를 **라이브 repo-mysql-1(8.0.46)에서 실행: error 1093 없음·정확 결과**(bundle-allow→graph-allow, 기존 graph-deny 보존, graph-allow skip, bundle-deny skip). admin catchup 여전히 graph.read 명시 부여(admin 무손실).
  - **VERDICT: PASS/SHIP** (MEDIUM/LOW/NIT 3건 전부 수정 반영 후).
- **검증**: 권한 단위테스트(perm-split R3/R3c/R3d·dependency-map t5/m3) + feature-0003 전체 스위트 PASS(회귀 0, env 중립화). 3 findings 수정 후 재실행 GREEN. `py_compile` 3파일 OK.
- **잔여 커버리지 갭(비-차단, 후속 권장)**: backfill SQL(대상1/2/3·마커 guard)은 `--no-deps` 표준 스위트에 자동 통합테스트 부재 — 본 cycle 은 보안 리뷰의 라이브 MySQL 실증 + `_apply_permission_overrides` 단위테스트로 커버. Critical authz 마이그레이션이므로 MySQL 통합테스트(대상3 과잉부여·graph-DENY skip) 후속 추가 권장(TEST.md 기록).
- Cross-ref: CHG/TASK-20260713T181800-graph-perm-split · REPORT §1. Files: `src/web_context.py`, `src/routers/{_bootstrap_schema,admin_metadata}.py`, `src/static/{admin.js,admin.html,release-notes-data.js}`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`.

## REV-20260713T185600-graph-perm-descfix [SKIPPED:bootstrap-robustness-no-authz-surface] — seed catchup 1406 hotfix (권한 설명 255자 초과)
- **적발 경로**: graph-perm-split 배포 후 실증(§16.3 완료 게이트가 아니라 배포 후 검증)이 `WebSchemaMigrations` 미생성·backfill 미실행을 잡아냄 → web 로그 `seed catchup skipped: 1406 Data too long`. 근본원인=내가 `kb.ingest.manual` 설명을 301자로 늘린 것이 `WebPermissions.Description` VARCHAR(255) 초과 → `_ensure_permission_catalog` 던짐 → `_ensure_seed_catchup` 전체 skip.
- **Panel skip 사유(§18.8)**: 본 hotfix 는 신규 authz 로직·enforcement·엔드포인트·스키마 형태 변경 0 — (1) description 문자열 단축(표시 텍스트), (2) `_ensure_permission_catalog` 의 방어적 문자열 클립(부트스트랩 robustness)뿐. 권한 판정(`_apply_permission_overrides`)·게이트·backfill SQL 무변경. 적대 보안 렌즈 대상 아님(표시/부트스트랩 방어). graph-perm-split 본체의 §18.8 PASS(REV-20260713T181800)가 authz 커버리지 정본.
- **자기 검증**: 전 권한 description ≤255·label ≤128 AST 전수 확인(잘림 0) · py_compile OK · feature-0003 전체 스위트 PASS(회귀 0). 근본 fix 실증은 배포 후(catchup 로그 소멸 + WebSchemaMigrations 마커).
- **교훈**: 권한 정의 description/label 은 컬럼 길이 제약이 있고, 초과 시 단일 row 가 전 seed catchup 을 차단한다. CI(`--no-deps`)가 이 DB 제약을 미검출 → 방어적 클립 + (후속) 부트스트랩 통합테스트 필요. graph-perm-split 보안 리뷰가 지적한 "backfill/부트스트랩 DB 통합테스트 부재" 갭이 실제 사고로 실현됨.
- Cross-ref: CHG/TASK-20260713T185600-graph-perm-descfix.


## REV-20260714T024534-doc-sync-rn-0714 [SKIPPED:non-policy-doc] — 릴리즈노트 07-13 블록 +7항목 append(관계도 콘텐츠 밴드 그룹핑·큰 관계도 이동 부드러움·미니맵/상세 hover·첨부 재업로드 버전·데이터소스 연결 테스트·정상 조회 과차단 수정) (TASK-20260714T024534-doc-sync-rn-0714, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0016 TASK §77~81·content-cluster REPORT + feature-0003 TASK attach-user-version/ds-conn-test + feature-0002 TASK readonly-query-shapes + git log #746~#770) 대비 직접 검증.
- 적대 대조(정본): 07-13 오후 사용자 화면 신규 = 콘텐츠 밴드 그룹핑(content-cluster+p2)·렌더러 교체 체감 부드러움(§78)·미니맵(§77/§79)·상세 hover(§81)·첨부 재업로드 버전(attach-user-version)·ds '연결 테스트'(ds-conn-test)·읽기전용 조회 과차단 수정(readonly-query-shapes). 제외=메시지 편집(backend-only)·describe_routine(LLM 내부 도구·사용자 화면 비노출·체감 간접 — item#7 readonly-query-shapes 는 사용자 조회가 직접 안 막히게 되는 화면 체감이라 포함, 구분 기준=사용자 화면 직접 변화 유무)·내부 최적화(§79 pool/§80 BitmapText). feature-id/§/테이블/함수/ADR/라이브러리명 누출 0(vm leak 스캔), 07-10 블록 대비 중복 회피(부드러움 항목은 컬링→렌더러 근본개선 차원 명시).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check release-notes-data.js` PASS · vm 파서 구조검증(28 releases·블록 07-13 head·항목 스키마·07-13 8항목·누출 스캔 0).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 게이트 무력화·해시 불변). 직전 doc-sync(REV-20260713T102249-doc-sync-rn-0713)도 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260714T024534-doc-sync-rn-0714 / META REV-20260714T024534-META-0035-doc-sync-0714(별도 commit) / 원천 PR #746~#770. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**
## REV-20260714T105200-graph-analyze-perm [SUBAGENT:security-lens-adversarial-PASS-after-fix] — AI 능동 분석 실행 권한을 조회에서 하위 분리 (Critical §12.3 인증/인가)
- **결정 근거**: 사용자 요청 "AI 능동 분석 실행 권한을 하위 권한으로 구분 + 무권한 시 버튼 미표시". graph-perm-split 후 graph.read 가 조회+실행을 함께 커버 — 실행(LLM·KB·비용 특권)을 별도 통제. **하위호환 = A안(최소권한, backfill 없음)** — 요청 취지가 "실행 분리 + 무권한 시 버튼 숨김"이라 graph.read 만으론 analyze 딸려오면 안 됨(함의/역함의 없음); admin 은 seed catchup 으로 획득; 현재 graph.read 보유자 admin 뿐이라 실질 영향 0.
- **§18.8 보안 렌즈 적대 서브에이전트(6축: backend 게이트 완결성·frontend 트리거 완결성·FE/BE parity·락아웃·종속/grant 정합·null-safety)**:
  - **FINDING (MEDIUM, 조회 계약 위반) 적발·수정**: 최초 구현이 AI 섹션 **전체**(읽기 전용 결과 box `metaGraphAiBox` 포함)를 `_canAnalyze` 게이트로 감싸 → graph.read-only 뷰어가 **기존 AI 분석 결과를 못 봄**. 그런데 (a) 백엔드 GET `/graph/analyze/node`·`/analyze/status` 는 graph.read 로 결과를 주고, (b) 본 변경이 쓴 graph.read 설명이 "결과·진행 상태 열람 가능"을 명시 → 자기 모순(과잉 제한). → **게이트 분리 수정**: 섹션 컨테이너·결과 box·`_metaGraphLoadNodeAnalysis`(결과 로드)는 항상 렌더(graph.read), 실행 컨트롤(`metaGraphAiBtn`·popover·`_metaGraphBindAiPopover`)만 `_canAnalyze` 게이트. + 회귀 가드 테스트 `test_graph_analyze_fe_gate_split`(결과 로드가 실행 게이트에 안 갇힘·버튼은 게이트) 추가.
  - **CLEAN(적대 REFUTE 통과)**: (1) backend 게이트 완결성 — 실행 POST 2개만 graph.analyze, 읽기 GET 5개 graph.read 유지, `enqueue_analysis`/`enqueue_schema_analysis` 는 그 2개 POST 에만 존재, `relationship/curate`(table.manage)는 LLM/enqueue 없어 무관. (2) frontend 트리거 완결성 — `_metaGraphAnalyze`/`_metaGraphAnalyzeSchema` 호출 UI 5곳 전부 게이트, 그 외 caller 없음. (3) FE/BE parity — 실행 경로 일치(FE 버튼 숨김 ⇔ BE 403). (4) 락아웃 — admin catchup 포함(`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞이라 pid resolve), 기존 admin 무손실; 비-admin graph.read 보유자 없음. (5) 종속/grant — graph.analyze 는 `_METADATA_MANUAL_IMPLIES` 에 없음(kb.ingest.manual 이 실행 함의 안 함, fail-open 없음), 단일 permission check 는 프로젝트 컨벤션 정합. (6) null-safety — bind 는 `_canAnalyze` + `if(!btn)` 이중 가드, load 는 `if(!box||!key)` 가드, 클러스터 버튼 `if(_schemaAiBtn&&comboId)`.
  - **LOW 흡수**: 읽기 GET 4개 docstring 이 "권한 kb.ingest.manual" stale(실제 graph.read) → 4곳 "권한 metadata.graph.read(결과 조회 — 실행은 graph.analyze)" 로 정정. 테스트 갭 → FE 게이트 분리 테스트 추가.
  - **VERDICT: PASS** (MEDIUM 게이트 분리 수정 + LOW docstring/test 반영 후 재검 — 초기 "not approved" 해소).
- **검증**: 권한 단위테스트(graph.read 만으론 analyze 미부여·독립부여·admin catchup·종속 pin·FE 게이트 분리) + feature-0003 전체 스위트 PASS(회귀 0) · py_compile·node --check OK.
- **잔여**: 배포 후 PB-0008 — graph.read-only 계정: 실행 버튼/메뉴 미노출 + **결과 열람은 가능** + POST analyze 403 / graph.analyze 계정: 버튼 노출·실행 정상.
- Cross-ref: CHG/TASK/FUNCTION-20260714T105200-graph-analyze-perm · REPORT §1. Files: `src/web_context.py`, `src/routers/admin_metadata.py`, `src/static/{admin.js,graph/graph-ctxmenu.js}`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`.
## REV-20260714T015432-step-scroll-preserve [SKIPPED:frontend-ui-minor-single-file-no-backend-no-rbac] — 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존 (TASK-20260714T015432-step-scroll-preserve)
- Panel skip 사유(§18.8): 변경은 프론트 단일 파일(`static/app.js`)의 렌더 재작성 사이 스크롤 오프셋 보존 로직뿐 — 백엔드·엔드포인트·RBAC·스키마·마이그·인증/인가·파괴적 데이터 0(§12.3 Minor). §18.8 dispatch 표상 UI/화면 신호는 ux/design 후보이나, (a) 비파괴 UX·표준 DOM scroll semantics, (b) 이미 검증된 동형 패턴(`state.stepResultExpanded` 펼침 영속화)을 스크롤로 확장, (c) 단일 파일이라 적대 코드리뷰의 한계 이득 낮음 → 패널 skip. 대신 소스추출 격리 테스트로 계약을 실증.
- 설계 결정: 근본 재구조화(재렌더를 diff/patch 로 전환) 대신 **스냅샷/복원**을 택함 — (1) 기존 펼침-상태 영속화가 이미 같은 teardown/rebuild 전제 위에서 `_stepResultKey` 로 동작, (2) 스크롤 키를 그와 동일 키에 정합시켜 최소 표면·저위험, (3) diff 렌더 전환은 두 경로(사이드 패널+progress 카드)의 대규모 재작성이라 Minor 범위 초과. 헬퍼는 컨테이너 무관 제네릭으로 두 경로 공용.
- 적대 자가검토(refute 시도): ① "재렌더 후 scrollTop 설정이 layout 전이라 무효?" → `body.scrollHeight` 접근이 동기 reflow 유발, 재-append 후 노드가 DOM 에 있어 설정 유효(기존 `if(wasAtBottom) body.scrollTop=scrollHeight` 가 이미 동일 전제로 동작). ② "접힌 결과 복원이 엉뚱한 값?" → snapshot 이 `wrap.hidden` skip + 비-0 스크롤만 캡처, restore 는 map.has 키만 → 접힘/신규 단계 무영향(테스트 [4][5] 실증). ③ "stepKey 충돌로 A 스크롤이 B 에 복원?" → 키=step_index+created_at(dedup 과 동일), 둘 다 없을 때만 idx fallback — 기존 펼침 영속화가 쓰는 키와 동일해 추가 충돌 표면 없음. ④ "외부 스크롤 prevScrollTop 유지가 새 단계 추가 시 튐?" → 기존 항목은 동일 재렌더라 위쪽 레이아웃 불변, min(prevTop, maxTop) 로 clamp → 안정.
- 검증: `node --check app.js` PASS · `tests/verify_step_result_scroll_preserve.mjs`(jsdom@22, app.js 에서 헬퍼 소스 슬라이스 후 eval) **23/23 PASS** — 정적 배선(양 경로 snapshot 선행·restore 후행·data-step-result-key), 기능(펼친 2개만 캡처·top/left·접힘 제외·240/88 복원·새 단계 D 무영향·null/빈맵 예외 없음). feature-0003 회귀는 verify-completion 게이트.
- 잔여(비-차단): jsdom 은 layout 무계산이라 **외부 목록 스크롤**(scrollHeight 의존)의 픽셀 거동은 미검증 — 내부 결과 스크롤(scrollTop verbatim 저장) 계약만 격리 실증. 외부 목록 + 실제 다단계 폴링 타이밍의 시각 최종확인은 POST-DEPLOY PB-0008(라이브 LLM run 필요·비결정적, visual_verification_scope: always).
- Cross-ref: CHG/TASK/FUNCTION-20260714T015432-step-scroll-preserve · TEST §CHECK#13(2026-07-14) · test-runs.d/20260714T015432-step-scroll-preserve.md · ANCHOR 0003 무충돌.

## REV-20260714T133700-routemap-refresh [SKIPPED:auto-generated-artifact-no-code] — docs/ROUTEMAP.md 재생성(graph-analyze-perm 후속)
- Panel skip 사유(§18.8): 변경은 `bin/gen-routemap.py` 가 라우터 AST 로 자동 생성하는 `docs/ROUTEMAP.md` 2행(analyze POST permission graph.read→graph.analyze 반영)뿐 — 코드·런타임·RBAC enforcement·엔드포인트 shape 무변경. 권한 분리 자체의 authz 검증은 원천 REV-20260714T105200-graph-analyze-perm(§18.8 PASS)가 정본.
- 자기 검증: `gen-routemap.py --check` exit 0 · `codenav-lint.sh` OK · 재생성 diff 가 원천 변경(2 POST 권한)과 정확히 일치.
- 교훈: require_permission 값 변경은 ROUTEMAP drift 이나 verify-completion CHECK#15 는 구조적 route 변경 시에만 gen-routemap --check 를 돌려 로컬 미검출 → CI 에서만 적발. 권한 데코레이터 변경 cycle 은 `gen-routemap.py` 재실행을 명시 수행할 것.
- Cross-ref: CHG-20260714T133700-routemap-refresh · 원천 CHG-20260714T105200-graph-analyze-perm.

## REV-20260714T053522-step-scroll-raf [SKIPPED:frontend-ui-minor-single-file-additive-no-backend] — 펼친 "결과 보기" 가로 스크롤 layout-timing 0-clamp 후속 (TASK-20260714T053522-step-scroll-raf)
- Panel skip 사유(§18.8): 프론트 단일 파일(`static/app.js`), 순수 additive(동기 복원 유지 + rAF 재적용 추가), 백엔드/RBAC/스키마/엔드포인트 0. 표준 DOM scroll 타이밍 처리 → 적대 코드리뷰 한계 이득 낮음.
- **라운드1 실패 정직 기록**: step-scroll-preserve(REV-...T015432) 는 jsdom 23/23 PASS + 배포 자산 서빙 심볼 확인까지 통과했으나 **실브라우저 가로 스크롤은 여전히 초기화**됐다(사용자 재보고). 원인=jsdom 이 `scrollLeft` 를 clamp 없이 verbatim 저장 → 동기 복원의 layout-미확정 0-clamp 결함을 격리 테스트가 놓침. 교훈: scroll 오프셋의 실제 clamp 거동은 jsdom 으로 검증 불가 — layout 의존 동작은 real-browser 또는 배포-후 실측이 정본.
- 적대 자가검토(refute 시도): ① "동기 복원도 남겨두면 0-clamp 값이 최종?" → rAF 콜백이 그 뒤(layout 확정 후) 동일 캡처값을 재적용하므로 최종은 올바른 값(테스트 [7] flush 로 0→88 복구 실증). ② "rAF 가 다음 폴링 재렌더 뒤에 늦게 실행돼 stale DOM 복원?" → rAF≈16ms ≪ 폴링 간격(수 초), 항상 다음 렌더 전 소진(테스트 [7] 큐 소진 확인); 설령 늦어도 캡처값은 콘텐츠 안정 시 동일이라 무해. ③ "additive 가 세로 스크롤/하단추종 회귀?" → `_applyStepPanelScroll` 이 기존 if/else 외부 스크롤 로직을 그대로 이관(atBottom→scrollHeight / else→min(prevTop,maxTop)), 동기 경로 동작 불변. ④ "rAF 미지원 환경?" → `typeof requestAnimationFrame === "function"` 가드, 미지원 시 동기 복원만(라운드1 동작).
- 검증: `node --check app.js` PASS · `verify_step_result_scroll_preserve.mjs` 29/29 PASS. **로컬 real-browser clamp 미재현**(chromium 다운로드 환경 차단) — 근본원인은 well-known layout-timing 클래스이고 수정이 additive(회귀 표면 없음)라 배포 진행, 최종 확인은 사용자/PB-0008 실측(가로 스크롤 유지).
- Cross-ref: CHG/TASK/FUNCTION AC-SSP-4-20260714T053522 · 원천 REQ-20260714T015432 · TEST §CHECK#13(2026-07-14) · test-runs.d/20260714T053522-step-scroll-raf.md · ANCHOR 0003 무충돌.

## REV-20260714T180314-graph-entry-help [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac] — 그래프 뷰 첫 입장 도움말 팝업 + 중간버튼 커서 (TASK-20260714T1803-graph-entry-help)
- Panel skip 사유(§18.8): 프론트 3파일(admin.html/graph.css/graph-core.js) 순수 additive UI, 백엔드/RBAC/스키마/엔드포인트 0. 정보성 도움말 오버레이 + 커서 표식 → 적대 코드리뷰(권한상승·SQL·enforcement) 한계 이득 낮음.
- 적대 자가검토(refute 시도): ① "팝업이 매 진입 노출돼 성가심?" → `_metaGraphMaybeAutoHelp` 가 `localStorage("metaGraphHelpSeen")` 미확인 시에만 자동노출, 닫으면(4경로 모두 `_metaGraphHideHelp`) seen set → 이후 세션 무자동노출, 재확인은 ❓ 버튼만. ② "localStorage 실패(사생활 모드)로 예외?" → get/set 모두 try/catch, 실패 시 '미확인=노출'로 안전 강등(기능 유지·비차단). ③ "이중 바인딩으로 리스너 누적?" → `_metaGraph._helpBound` 가드 + `_metaShowGraph`(admin.js graphInitialized 가드) 1회 진입. Esc keydown 은 표시 중에만 등록·해제(show 시 기존 핸들 제거 후 재등록). ④ "중간버튼 커서가 팬 도중 깜빡이거나 다른 버튼 뗌에 조기 복원?" → mouseup 에서 `buttons & 4` 여전 눌림이면 복원 skip, 중간버튼 뗌(buttons&4=0)·window blur 시만 복원 + 리스너 self-remove. ⑤ "캔버스에 커서 안 먹힘?" → `#metadataGraphCanvas` 명시 cursor 부재 확인 → 자식 `<canvas>`(cursor 미선언)가 컨테이너 grabbing 상속(렌더러 PixiJS/G6 무관, CSS 상속 프로퍼티). ⑥ "기존 그래프 조작 회귀?" → 기존 `mousedown` 핸들러는 preventDefault 유지·additive, 신규 오버레이는 캔버스 role=img 밖 형제(접근성 보존)·hidden 기본·pointer 이벤트 캔버스 미간섭.
- 검증: `node --check --input-type=module`(graph-core.js) PASS · admin.html 도움말 블록 태그 균형(amg-help 20 매치) · graph.css 중괄호 215/215 · 새 심볼 전수 존재. **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 자산 baked, visual_verification_scope: always) — 자동노출·닫기 4경로·재확인·중간버튼 커서·pageerror 0.
- Cross-ref: CHG/TASK-20260714T1803-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260714T184717-graph-help-overlay-fix [SUBAGENT:css-comment-hazard-adversarial-PASS] — 그래프 도움말 팝업 mis-position 근본원인 수정 (TASK-20260714T184717-graph-help-overlay-fix)
- 변경: `graph.css` 주석 1곳의 토큰 구분자 `/`→`·`(`*/` 조기종료 hazard 제거) + 재발방지 NOTE. CSS 선언/선택자/미디어쿼리 무변경(주석 텍스트 국한, diff +4/-2).
- Panel 실행 사유(§18.8): render-path 인접(도움말 오버레이 레이아웃 회귀·라이브 버그 수정) → 적대적 SUBAGENT 검증 실행.
- SUBAGENT 결과(general-purpose, refute 지향): **PASS — BLOCKING 0**. 근거 — ① edited 주석·추가 NOTE 에 의도치 않은 `*/` 서브스트링 없음(byte 확인: `--text*·--primary`=`2a c2b7`, `(*·/)`·`` `*` + `/` `` 는 `·`/백틱으로 분리). ② `/*`:`*/` 정확히 61:61 균형, 모든 `*/` 가 clean end-of-comment(수정 전 62:61 불균형 → 초과 close 제거 확인). ③ `.amg-help-overlay` 규칙 문법 온전·주변 규칙 무영향. ④ git diff 주석 텍스트 국한(선언/선택자/미디어쿼리 0). ⑤ 회귀 sweep: 파일 내 다른 `*`+`/` hazard 없음(모든 asterisk 는 bold 마커 또는 안전 토큰). NIT(비차단): 설명 off-by-one, NOTE 는 prose-only(기계적 lint 없음 — CI `*/` 균형 grep 가드는 out-of-scope).
- 라이브 재검증(win-browser eval, 배포본): (a) 수정본 파싱 시 `.amg-help-overlay` 복구·`position:absolute`(rule 204→205). (b) 규칙 라이브 주입 후 카드 canvas-wrap 정중앙(dx:0 dy:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false, 카드 하단 694 < 줌 상단 704). (c) `/healthz` git_commit=1f705a9e·pageerror 0. POST-DEPLOY 재배포 자산 최종 확인=deploy-web 직후.
- Cross-ref: CHG/TASK-20260714T184717-graph-help-overlay-fix · 원천 CHG-20260714T180314-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md(POST-DEPLOY FIX) · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260714T190916-graph-help-overlay-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 도움말 팝업 mis-position 수정 재배포 자산 실증 기록 (CHG-20260714T190916-graph-help-overlay-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 코드 수정 CHG-20260714T184717-graph-help-overlay-fix 은 이미 REV-20260714T184717 [SUBAGENT:...PASS] 로 적대검증 완료. 본 cycle 은 그 배포 결과를 fragment/TASK 에 기록만.
- 배포본 실증(win-browser eval, 주입 없이, 그래프 뷰 pane 활성): `/healthz` git_commit=8d1285d0 · 서빙 graph.css 스탬프 d5f26a416089(갱신)·소스 byte-identical · `.amg-help-overlay` cssRules 파싱 복구·`position:absolute`·`display:flex`·`align-items:center`·`z-index:40`(수정 전 static/block/normal/auto) · 카드 canvas-wrap 수평 정중앙(dx:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false) · 스크린샷 육안(중앙 모달) · pageerror 0. → PASS.
- Cross-ref: CHG-20260714T190916-graph-help-overlay-postverify · 원천 CHG/REV-20260714T184717-graph-help-overlay-fix · TEST test-runs.d/20260714T180314-graph-entry-help.md · ANCHOR 0003 무충돌.


## REV-20260715T025509-doc-sync-rn-0715 [SKIPPED:non-policy-doc] — 릴리즈노트 07-14 블록 신규 10항목(메시지 편집 Phase 1+2·애니메이션 효과 설정·계정 탭 세분화·첨부 새버전·SQL Server cross-DB·결과보기 스크롤·그래프 첫입장 도움말·카테고리밴드 우클릭·AI분석 권한분리·답변 정확도) (TASK-20260715T025509-doc-sync-rn-0715, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0019 FUNCTION REQ-ME-R1~R3/AC-ME-3~6 + feature-0003 TASK anim-effect-pref/account-subtabs/graph-entry-help/graph-ctxmenu-category/step-scroll/graph-analyze-perm + feature-0002 TASK grounding/mssql-crossdb/attach-versioned + git log 07-14) 대비 직접 검증(ULTRACODE 4-도메인 병렬 draft→적대 재검증 wf_ebf9d553).
- 적대 대조(정본): 07-14 사용자 화면 신규 = 메시지 편집 Phase 1+2 라이브(git bee8a96d/1cf7784b/08443ae1/3f9c55ba)·애니메이션 효과·계정 탭·첨부 새버전·MSSQL cross-DB·결과보기 스크롤·그래프 첫입장 도움말(mis-position 수정 반영)·카테고리밴드 우클릭·AI분석 권한분리(관리자향)·답변 정확도(grounding). 제외=feature-0020 배포(내부)·feature-0016 flock/cluster-label(내부)·@@ 과차단(07-13 블록 detail 포괄·중복회피). feature-id/§/PR#/테이블/함수/권한키/라이브러리명 누출 0(vm leak 스캔).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(29 releases·07-14 head 10항목·07-13 보존·스키마·누출0).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 게이트 무력화·해시 불변). 직전 doc-sync(REV-20260714T024534-doc-sync-rn-0714)도 동일 판단.
- **정본 lag(보고)**: feature-0019 REPORT.md prose 는 07-14 Phase 1 checkpoint 3 에서 멈춰 Phase 2(1cf7784b) 라이브 미반영 — 릴리즈노트/STATUS/wiki mirror 는 FUNCTION 스펙(REQ-ME-R3/AC-ME-6)+git+PB-0008 실측 기준으로 정확 작성. 정본 REPORT Phase 2 completion 섹션 추가는 feature-0019 후속 cycle 권고(doc_sync 정본 미편집).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260715T025509-doc-sync-rn-0715 / META REV-20260715T025509-META-0036-doc-sync-0715(별도 commit) / 원천 PR 07-14. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**
## REV-20260714T181936-perm-category-hier [SKIPPED:panel-usage-limit—inline-adversarial-selfreview+live-mysql-dryrun] — 관리 콘솔 권한 체계 카테고리 '접근' 계층 재구성 (20260714T1819-perm-category-hier, Critical §12.3)

- **대상**: 신규 카테고리 접근 권한 5종(`console.{account,product,audit,kb,system}.access`) + GroupName 재배치 + `_backfill_console_category_access_v1`(1회 멱등) + admin.js 종속 트리/탭 카테고리 AND 게이트. 사용자 승인 A안(B안=표시만 은 "카테고리 최상위 접근 권한" 요건 미충족 기각). 병렬 겹침(ITEM-09 admin.js hot_paths)도 사용자 결정 "그대로 진행".
- **§18.8 수행 형태 정직 보고**: 보안 렌즈 subagent 패널이 세션 한도(usage limit)로 조기 종료 → **inline 적대 자가검토 + 라이브 MySQL dry-run 실증으로 대체 수행** (graph-perm-split 의 라이브 실증 선례 답습). 패널 재실행이 필요하면 후속 cycle 에서 가능.
- **적대 가설 → 판정**:
  - 권한상승(역함의): REFUTE — 함의 로직은 `_apply_permission_overrides` 의 `_METADATA_MANUAL_IMPLIES` 뿐(전수 확인), 접근 권한이 세부 권한을 함의하는 경로 0. 접근 권한 단독이 여는 데이터 표면 0(엔드포인트 require_permission 무변경).
  - 동적 `product.access.<key>` prefix 충돌: REFUTE — 동적 판별은 `IsDynamic` 컬럼 기반(`_resolve_permission_catalog`), `product.access.` prefix 문자열 필터 코드 0건(전수 grep). `console.product.access` 는 정적 카탈로그 별개 code.
  - seed catchup 255자 트랩: REFUTE — 전수 72건 label≤128·desc≤255 실측(신규 5종 desc 89~112자). 방어 클립(graph-perm-descfix)도 유지.
  - 부트스트랩 순서: REFUTE — fast(`_ensure_seed_catchup` L2250)·slow(L820) 양 경로 모두 catalog→seed_roles(말미 backfill) 순서 보장, backfill 시점에 접근 pid 존재.
  - GroupName 이동 회귀: REFUTE — 백엔드에 GroupName 문자열 분기 0건(전수 grep), `_prune_orphaned_permission_catalog` 는 명시 폐기 목록만(신규 무관), admin grid 는 백엔드 group 사용·app.js 는 `PERMISSION_GROUP_OVERRIDES` 명시 매핑 추가.
  - 접근 상실(락아웃) 조합 매트릭스: (role console.access × role 세부 × 계정 override allow/deny/부재) 전 조합 사고실험 — backfill 대상 3종이 오늘 탭이 보이던 모든 조합을 커버(동치 보존), 오늘 안 보이던 조합은 그대로(과잉부여 없음: console.access 없는 operator/sales/pending 의 audit.read.own 은 부여 제외 — least-privilege).
  - grid 저장 계약: REFUTE — disclosure 는 collapse only(저장 경로 hidden row 유지, TASK-0264 계약 미변경 코드).
- **라이브 MySQL 8 dry-run 실증(read-only, `repo-mysql-1`/agent_memory, 감사 카테고리 대표)**: backfill 3종 SELECT 문법·의미 정상(1093 없음). **target1 적중 = admin + 커스텀 role `usermanager`** — usermanager 는 seed catchup 목록에 없는 커스텀 role 이라 catchup 만으론 감사 카테고리 탭을 잃었을 대상 → backfill 이 정확히 구제(설계 필요성 실증). target2 = 계정 1건(leaf ALLOW override) · target3 = 0행. 라이브 role 8종 중 console.access 미보유 role(dev_server/dos_web 등)은 오늘도 콘솔 미진입 → 동치 보존.
- **테스트**: 권한 타깃 50 PASS(M5 backfill 맵↔FE 종속 동치 신설) · feature-0003 785/0 · jsdom 탭 게이팅 47/0 · 컨테이너 make test 4 실패 전건 **환경 기인 확정**(3건=복사 .env `AGENT_RUNTIME_READ_BACKEND=postgres`·`AGENT_TIMEOUT_SEC=300` — env 중립화로 소멸·선례 동일 / 1건=`postgres-replica` DNS — main 코드+격리 네트워크 동일 재현, 격리 프로젝트 네트워크에 replica 부재 기인).
- **Human Approval**: 예 — 본 cycle 시작 시 AskUserQuestion 으로 A안 승인 완료(Critical §12.3 사람 승인 충족).

## REV-20260714T203000-perm-category-hier-postverify [SKIPPED:doc-only-postdeploy-verification-record] — perm-category-hier 배포 후 실증 기록 (PR #801 · 7e375ebc)
- 코드 변경 0(문서 전용). 실증 내용: seed catchup 정상 · `console-category-access-v1` 마커 · 접근 5종 부여(admin catchup / **usermanager = backfill 구제 실증** / dba audit) · override target2 1건 · PB-0008 라이브(grid 계층 depth·상위 토글 → 하위 접힘/펼침·admin 13탭·"변경 없음" 상태 무오염). 상세 = test-runs.d/20260714T181936-perm-category-hier.md POST-DEPLOY Run · TASK 20260714T1819 잔여 박스 close.
- [SKIPPED] 사유: 배포 후 실증의 문서화만 — 신규 코드/경계 0, 패널 불요(선례 REV-20260714T190916-graph-help-overlay-postverify).

## REV-20260715T102912-graph-help-text-responsive [SKIPPED:frontend-ui-minor-css-text-layout-no-logic-no-rbac] — 그래프 도움말 팝업 텍스트 줄바꿈 + 반응형 크기 (TASK-20260715T102912-graph-help-text-responsive)
- Panel skip 사유(§18.8): 프론트 1파일 CSS 텍스트-레이아웃 전용(`.amg-help-card` 의 word-break/overflow-wrap/width). 백엔드/RBAC/스키마/엔드포인트/JS/HTML 0. 로직·경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음.
- 적대 자가검토(refute 시도): ① "keep-all 이 긴 무공백 토큰(URL 등)에서 오버플로?" → `overflow-wrap: anywhere` 동반으로 폭 초과 시 강제 분할, 안내 텍스트엔 그런 토큰 없음(어절마다 공백). ② "clamp width 가 좁은 화면에서 컨테이너 넘침?" → 바깥 `min(..., 100%)` 로 항상 컨테이너 바운드(실측 300px→268·오버플로 0). ③ "카드가 너무 커져 모달감 상실?" → 상한 520px(가독 상한), 1100px 캔버스에서도 520 유지. ④ "keep-all 이 중점(·) 목록('설명·컬럼') 을 한 덩어리로 묶어 넘침?" → 285px 설명폭 대비 짧아 무해, 초과 시 overflow-wrap fallback. ⑤ "다른 규칙/미디어쿼리 회귀?" → diff 는 `.amg-help-card` 선언 2 + 주석 국한, `@media(max-width:520px)` 라벨 스택 등 기존 규칙 무변경. ⑥ "주석 hazard 재발?" → 신규 주석 `/*`:`*/` 63:63 균형·`*` 뒤 `/` 없음(20260714T184717-fix 불변식 준수).
- 검증: graph.css `/*`:`*/` 63:63·중괄호 215:215 균형 · 라이브 win-browser eval(keep-all 어절 줄바꿈 스크린샷 + 반응형 다중 폭 실측 300~1100px, 오버플로 0). **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 baked, visual_verification_scope: always).
- Cross-ref: CHG/TASK-20260715T102912-graph-help-text-responsive · 원천 CHG-20260714T180314-graph-entry-help·CHG-20260714T184717-graph-help-overlay-fix · TEST test-runs.d/20260715T102912-graph-help-text-responsive.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260715T103948-graph-help-responsive-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 도움말 팝업 줄바꿈+반응형 재배포 자산 실증 기록 (CHG-20260715T103948-graph-help-responsive-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 CSS 수정 CHG-20260715T102912 은 이미 REV-20260715T102912 [SKIPPED:...] 로 적대 자가검토 완료. 본 cycle 은 배포 결과를 fragment/TASK 에 기록만.
- 배포본 실증(win-browser eval, 주입 없이): `/healthz` git_commit=6af16762 · 서빙 graph.css 스탬프 92be1efb1249(갱신) · `.amg-help-card` word-break=keep-all(설명 상속)·overflow-wrap=anywhere · 반응형 폭 300→268·360→320·617→520·1100→520(오버플로 0) · 스크린샷 육안(어절 줄바꿈·넓어진 카드·중앙 모달) · pageerror 0. → PASS.
- Cross-ref: CHG-20260715T103948-graph-help-responsive-postverify · 원천 CHG/REV-20260715T102912-graph-help-text-responsive · ANCHOR 0003 무충돌.
## REV-20260715T103406-perm-atomic-split [SKIPPED:panel-usage-limit—inline-adversarial-selfreview] — 권한 최소 단위 원자화 + 레거시 묶음 숨김 (20260715T1034, Critical §12.3)

- **대상**: 원자 23종 + 엔드포인트 enforcement 전환(~38 핸들러) + transitive 함의 + backfill v2 + grid 묶음 숨김. 사용자 결정 2건(전체 분리+숨김 / 검수 단일·원본 read 하위) AskUserQuestion 승인.
- **§18.8 수행 형태**: 직전 cycle 과 동일 사유(패널 subagent 세션 한도)로 inline 적대 자가검토. 적대 가설 → 판정:
  - **원자 DENY 무력화(choke-point fallback)**: 설계 단계에서 기각 — `_account_has_permission` 에 묶음 fallback 을 두면 effective map 의 원자 DENY 를 우회(권한상승). 대신 effective map 함의만 사용(DENY 우선, 테스트 R9 pin).
  - **역할 저장 wipe(숨긴 묶음 grant 소실)**: REFUTE — 역할 저장 경로 preservedHidden(TASK-0300)이 grid 미렌더 코드를 union 보존(admin.js 실코드 확인). override 편집기는 row 단위 upsert 라 무관.
  - **suggest(LLM 비용)가 read 로 격하**: 설계에서 차단 — 가시성 맵(read)과 분리된 `_METADATA_SUGGEST_PERM`(update) 신설.
  - **fresh install 순서 결함**: backfill v2 를 category-access-v1 **선행** 호출로 해결(묶음-only role 이 원자 전개 후 카테고리 접근 leaves 판정에 걸림 — 코드 주석 계약).
  - **테스트 fake 계정 우회로 인한 위장 통과**: 원자 키를 perm dict 에 명시 보강(10파일) — enforcement 는 plain lookup 유지.
  - **잔여 묶음 enforcement**: 전수 grep 0(미사용 legacy 헬퍼 `_metadata_resolve_account` 만 잔존 — 호출처 0 확인).
  - **연결 테스트 게이트**: 기존 '버튼 무게이트+서버 manage 403' 괴리 → datasource.test 로 FE/BE 정합(개선).
- **검증**: 785/0(호스트) · jsdom 47/0 · R9(transitive·DENY 우선)/R10(legacy 3자 parity) 신설 · ROUTEMAP 재생성 --check 0. 컨테이너 make test·배포 후 실증은 TASK 잔여.
- **Human Approval**: 예 — cycle 시작 AskUserQuestion 2건 승인(Critical §12.3 충족).
## REV-20260715T113000-perm-atomic-postverify [SKIPPED:doc-only-postdeploy-verification-record] — perm-atomic-split 배포 후 실증 기록 (PR #810 · 8098aee1)
- 코드 변경 0(문서 전용). 실증: seed catchup 정상 · `atomic-perm-split-v1` 마커 · admin 원자 23종 · 묶음 보유 role=admin 뿐(usermanager 비대상 정상·접근 상실 0) · PB-0008 라이브(레거시 묶음 grid 0건·원자 트리 d1/d2·검수=원본 read 하위·토글 접힘/펼침·상태 무오염). 상세 = test-runs.d/20260715T103406-perm-atomic-split.md POST-DEPLOY Run.
- [SKIPPED] 사유: 배포 후 실증 문서화만 — 신규 코드/경계 0(선례 REV-20260714T203000-perm-category-hier-postverify).
## REV-20260715T110000-attach-new-label-symmetry [SUBAGENT:adversarial-scope/IDOR/correctness] — staged-flush 첨부 new_attachment_ids 라벨 대칭
- 대상: `app.js` lazy-create staged-flush 의 `new_attachment_ids` union(±3줄) + 서버측 소비(agent_core `_build_attachment_context_section`). 적대 서브에이전트 1렌즈(scope/IDOR/correctness, 5축), 양 dispatch 경로(in-process router + ask-worker) 추적.
- **CONFIRMED-DEFECT 0 / 5축 전건 REFUTED**:
  - **① Scope/IDOR — REFUTED**: `new_attachment_ids`(→`_NEW_ATTACHMENT_IDS_CTX`→`_load_new_attachment_ids`→`new_ids_set`)는 **라벨(★/◆)+version-diff 게이트 전용**. 주입 대상 선택 SQL 은 `attachment_ids`(`Id IN (...)`)+ConversationId(IDOR 안전망)만 필터 — new_ids_set 은 이미 fetch 된 행을 라벨만 함. attachment_ids 에 없는 id 는 rows 부재 → 라벨 미방출. 접근 확장 불가.
  - **② uploadedIds 신뢰 — REFUTED**: `_flushStagedAttachmentsToCid` 가 성공 업로드 응답 `Number(resp.id)>0` 만 push. resp 는 `POST /api/conversations/{earlyCid}/attachments`(방금 이 계정용 발급된 earlyCid) 결과 → 이-대화·이-계정 서버-확인 id. stale/foreign 누출 불가.
  - **③ version-diff 오트리거 — REFUTED**: `## FILE UPDATES` 게이트는 `new_ids_set 포함 AND MetaJson.version_diff(unified_diff 비어있지 않음)` 동시 요구. 신규 earlyCid 는 동명 prior 부재 → v1/root=NULL, version_diff 부재 → 라벨이 ★신규여도 게이트 닫힘.
  - **④ dedup/type/ordering — REFUTED**: `new Set([...prev,...uploadedIds].map(Number).filter(n>0))` — 빈-버그케이스=deduped uploadedIds(정확), 기존값 있으면 union. NaN/음수 배제, Set dedup, 삽입순 보존. 인접 attachment_ids union 과 정확 대칭.
  - **⑤ 비-lazy 경로 무영향 — REFUTED**: 추가 블록은 `if(isLazyCreate)`+`if(earlyCid)`+`if(stagedCount>0)` 내부만 — 기존 대화·무-staged send 무변경.
- OVERALL: BLOCKING 0 / MAJOR 0 / MINOR 0. No fix required.
- 검증: `node --check` PASS. 라이브 PB-0008(신규 대화 staged 첨부 ★신규 인지)은 정적자산 baked → 배포 후 실측(TEST.md §3 DEFERRED).
- Human Approval: PLAN-APPROVED(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(라벨-only) → PR/deploy(deploy_scope: included).
- Cross-ref: CHG-20260715T110000-attach-new-label-symmetry(MODIFY) · CHG-20260715T060000-attach-inline-honesty(②-backend, feature-0002) · ANCHOR §1~§3 무충돌.

## REV-20260715T105337-enum-review-bundle [SUBAGENT:backend-security-adversarial — VERDICT SHIP after fixes (1 MAJOR + 2 MINOR 전건 수정)] — ENUM 코드사전 검토 큐 구조 묶음 승인 체크리스트 + 일괄 등록 (20260715T1053-enum-review-bundle, Major §12.3)
- 대상: 신규 `POST /api/admin/metadata/enum-feedback/bulk-promote`(admin_metadata.py) + `bulk_promote_enum_feedback`(kb_glossary.py). 프론트(admin.js 묶음 렌더 + CSS)는 로직·경계 무변경(RBAC/스키마/엔드포인트 shape 0) → 백엔드/보안 축만 적대 패널(§18.8 "API/endpoint → backend, security, qa").
- **적대 패널(general-purpose subagent, 결함 적발 목적)** 결과: BLOCKERS 0, MAJOR 1, MINOR 2. **전건 수정 후 SHIP.**
  - **[MAJOR — 수정됨] 이벤트 루프 블로킹**: 핸들러가 `async def`(body await 필수)인데 최대 200×3 블로킹 psycopg 쿼리(+`FOR UPDATE`, `_pg_connect` 는 lock/statement timeout 미설정)를 이벤트 루프에서 직접 실행 → 경합 lock 시 워커 전체 정지(단건 형제는 `def` 라 threadpool 격리). **수정**: 블로킹 배치를 `run_in_executor(None, _run_bulk, pg)` 로 threadpool 오프로드(connect 는 connect_timeout 로 bounded, 루프에 유지해 503 parity) + 배치 트랜잭션에 `SET LOCAL lock_timeout='5s'`(무한 FOR UPDATE 대기 fail-fast → 롤백 → 재시도 가능 500).
  - **[MINOR — 수정됨] deadlock**: `FOR UPDATE` 를 클라이언트 순서로 획득 → 겹치는 id 를 역순으로 동시 bulk-promote 시 deadlock → 500. **수정**: `ids.sort()` 로 결정적 lock 순서(테스트 `test_enum_feedback_bulk_promote_sorts_ids`).
  - **[MINOR — 수정됨] 선-DoS**: cap 을 dedup 후 개수에 적용 → 초대형 배열 full-parse + O(n) 루프가 400 전에 실행. **수정**: 원본 배열 길이(`len(raw_ids)`)부터 cap(테스트 `_cap_400`) + bool/비정수 float 명시 거부.
- **PASS(결함 없음, 패널 확인)**: 트랜잭션 원자성(단일 commit, 예외 시 rollback+close, 부분 실패 전건 롤백)·연결 수명·RBAC(`kb.enum.curate` 단건과 byte-identical, 우회 없음)·SQL injection(파라미터화 재사용, 신규 interpolation 0)·입력검증(missing/non-dict/non-list/non-int/≤0/dedup)·audit(`_metadata_audit` resource_id=None 허용·change_json 직렬화)·부분 skip 시맨틱(없음/이미처리 → enum_id=None skip, 예외 아님).
- 비파괴 재확인: 미선택(해제) 후보는 pending 유지(거부 아님). 개별 promote/reject·glossary/sample 큐·엔드포인트 shape 불변.
- 검증: agent 컨테이너 pytest — core `test_kb_enum_feedback`(bulk_multi·skips_missing) + web `test_metadata_enum_feedback`(bulk_promote·reports_skips·empty_400·bad_type_400·cap_400·sorts_ids·requires_curate) + route_parity(golden 재생성) **31 passed** · `py_compile` OK · `node --check` admin.js PASS · `gen-routemap --check` up-to-date. **라이브 시각검증 = POST-DEPLOY PB-0008**(정적 baked, visual_verification_scope: always).
- Cross-ref: CHG/TASK/REQ-20260715T105337-enum-review-bundle · FUNCTION AC-ERB-1~3 · 원천 enum_feedback(alembic 0039)·admin_metadata enum-feedback 큐 · TEST test-runs.d/20260715T105337-enum-review-bundle.md · ANCHOR 0003 무충돌.


## REV-20260715T113208-enum-bundle-flex-fix [SKIPPED:frontend-css-layout-single-declaration-no-logic-no-rbac] — ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정 (20260715T1132-enum-bundle-flex-fix, Minor §12.3)
- Panel skip 사유(§18.8): CSS 1선언(`flex-shrink:0`) + 주석. JS/HTML/백엔드/RBAC/엔드포인트 0. 로직·경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음.
- 근본원인 라이브 확정: `#metadataList`(overflow-y:auto·flex-column·height 373px)에서 `.admin-meta-bundle` 기본 flex-shrink:1 → 8카드 압축 + card overflow:hidden 이 내용(164px) 클리핑 → 12px sliver. flex-shrink:0 주입 시 166px 복원(라이브 실측). flat-list `.admin-meta-row`(overflow visible)는 미발현이던 잠복.
- 적대 자가검토(refute): ① "flex-shrink:0 이 목록 스크롤을 깨나?" → `#metadataList overflow-y:auto` 가 컨테이너 스크롤 제공, 카드는 자연 높이(표준 패턴). ② "다건일 때 넘침?" → 컨테이너 스크롤이 흡수(카드 압축 대신). ③ "다른 flex 자식 회귀?" → `.admin-meta-bundle` 한정 선택자, 타 규칙 무변경.
- 검증: POST-DEPLOY PB-0008 라이브(재배포 자산 카드 정상 높이·묶음·체크리스트·등록·pageerror 0).
- Cross-ref: CHG/TASK-20260715T113208-enum-bundle-flex-fix · 원천 REV-20260715T105337-enum-review-bundle · ANCHOR 0003 무충돌.

## REV-20260715T120000-enum-review-bundle-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — ENUM 검토 큐 묶음 승인 체크리스트 + flex-fix POST-DEPLOY 실증 기록 (CHG-20260715T120000-enum-review-bundle-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T105337(백엔드/보안 [SUBAGENT] 적대 패널 완료) + CHG-20260715T113208(CSS [SKIPPED] 적대 자가검토 완료)은 각 REV 로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, bootstrap_admin /api/auth/login 200, 주입 없이): (묶음/체크리스트) 12후보→8묶음·전체 승인 마스터·일부 해제 indeterminate/힌트·등록 count/disabled 라이브 PASS. (flex-fix 재배포 a3c69103) 카드 높이 [166,166,166,205,166,166,298,166]·flex-shrink=0·목록 스크롤(scrollH 1770>clientH 373)·sliver 해소·pageError 0. 스크린샷 육안 정상.
- Cross-ref: CHG-20260715T120000-enum-review-bundle-postverify · 원천 REV-20260715T105337-enum-review-bundle · REV-20260715T113208-enum-bundle-flex-fix · ANCHOR 0003 무충돌.

## REV-20260715T181939-graph-edge-follow-drag [SUBAGENT:pixi-render-lifecycle-adversarial + 적대 자가검토] — 그래프 노드/제품 카테고리 드래그 시 관계선 미추종 수정 (20260715T1819-graph-edge-follow-drag, Minor §12.3)
- 근본원인: PixiJS 엣지는 절대좌표를 Graphics 에 bake 한 world 직속 독립 오브젝트(`_drawEdge`) → 노드 이동으로 미추종. 드래그 경로(`_moveElement`/`translateElementTo`)가 `_render()`(repaint)만 호출, 엣지 재계산은 full `draw()`(줌 rebuild)에서만 발생 → "줌 아웃해야 갱신". 신규 `_refreshIncidentEdges` 로 이동 노드의 incident 엣지만 증분 재그림.
- 적대 자가검토(refute):
  ① "old destroy 후 world 자식 leak/double-destroy?" → 각 엣지 loop 1회 처리(내부 엣지도 edges 배열에서 1회). old 는 `_objs.get(eid)` 로 획득 후 destroy+removeChild, 신규는 addChild+`_objs.set` — draw() 의 recreate lifecycle(550~551)과 동형. leak 없음.
  ② "_objSig 갱신이 이후 full draw() 재사용을 오판?" → draw() 는 committed 위치로 `edgeSig` 재계산: 드래그와 동일 위치면 재사용(시각 동일·정상), 다르면 서명 불일치→recreate(정상). stale 시각 없음. edgeSig/edgeId/pos 계산이 draw() 와 동일 함수라 불일치 0.
  ③ "cross-category 미갱신?" → 판정 `moved.has(source) || moved.has(target)` — 한끝만 이동해도 재그림. 이동 끝점=새 `getElementPosition`, 미이동 끝점=현재 좌표 → 구조 갱신(T23 실증: e2 B이동[500,400]·C미이동[200,200]).
  ④ "카테고리 드래그가 이 chokepoint 를 안 거치면?" → graph-core `_metaNodeDragStart`(CAT/CATH 1768)가 `_metaComboMemberIds` 로 전 구성원 적재→`_metaNodeDrag`(1848) `translateElementTo(to)` → 본 메서드 경유. 커버 확인.
  ⑤ "빈/null/비-node movedIds?" → `new Set(movedIds||[])` + `if(!moved.size) return` 방어. 비-node id 는 어느 엣지 끝점과도 매칭 안 돼 no-op. T23 no-op 케이스 PASS.
  ⑥ 성능(허브 수천 엣지 per-frame): 실 비용 존재하나 full draw() 보다 저렴(콤보/전노드/미니맵 재구성 없음)하고 정확성 필수 최소치 — 수용 가능 트레이드오프로 판정, rAF 스로틀은 deferred(§76).
- [SUBAGENT:pixi-render-lifecycle-adversarial] VERDICT — **correctness 결함 없음**(6축 refute, 73/73 통과). 핵심 불변식 확인: (a) 모든 엣지 끝점은 node id(`graph-core` renderEndpoint 는 node id 또는 `SC:` node 만 반환, combo 는 엣지 끝점 아님), (b) `_refreshIncidentEdges(moved)` 는 방금 `.style` 위치를 바꾼 노드 집합과 **정확히 동일 인자**로 호출 → 위치 바뀐 엣지는 ≥1 끝점이 moved 에 있어 OR 판정으로 100% 포착, stale 잔존 경로 0. 축1(풀 lifecycle/zIndex)·축2(_objSig 재사용: getElementPosition/pos 가 node 끝점에 byte-동일 → 후속 full draw 정확 reuse)·축3(edgeId/edgeSig/좌표 동일 함수)·축4(cross-category OR, T23 실증)·축6(방어) 전부 REFUTED(결함 아님). expanded 스키마 콤보 SCHEMA_REF stale 의심도 refute(양끝 folded=SC: node 일 때만 렌더).
- [SUBAGENT] 잔여 non-blocking: **F1(CONFIRMED, 성능 트레이드오프)** 허브/대형 스키마 드래그 시 프레임당 O(E)×2 스캔 + incident 엣지 destroy/recreate(graph-core `_metaNodeDrag` 종속이동과 이중 호출 — 단 서로 다른 엣지집합). 사용자 드래그로 bound·정확성 무영향 → 수용, deferred 최적화 = 엣지 Graphics 재사용(`.clear()`+재-path, destroy/recreate 회피) 또는 rAF 스로틀. F2(null 끝점 stale, 드래그 중 노드 소멸 거의 도달불가·benign)·F3(비-배열 문자열 movedIds 문자분해, 현 호출자 전부 배열/Set·미도달)·F4(_drawEdge throw 시 다음 draw self-heal, draw() make 경로와 동일 리스크) — 전부 도달난이도 높음/benign, 수정 불요.
- 검증: `node --check` PASS · 헤드리스 T23 7종 ALL PASS 73/0 · [SUBAGENT] 적대 리뷰 결함 없음 · POST-DEPLOY PB-0008 라이브(제품 카테고리 드래그 중 cross-category 관계선 실시간 추종, 잔여).
- Cross-ref: TASK 20260715T1819 · CHG/TEST-20260715T181939-graph-edge-follow-drag · 그래프 도메인 정본 feature-0016 · 선행 graph 렌더러 seam §78(PixiJS) · ANCHOR 0003 무충돌.

## REV-20260715T190000-graph-edge-follow-drag-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 관계선 추종 수정 POST-DEPLOY 라이브 실증 기록 (CHG-20260715T190000-graph-edge-follow-drag-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T181939 은 REV-20260715T181939([SUBAGENT] 적대 리뷰 correctness 결함 없음)로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, 로그인 세션, 주입 없이): PixiJS 루트 뷰에서 제품 카테고리 드래그 → cross-category 관계선이 pointerup 전·줌 없이 새 위치 실시간 추종(옛 위치 잔상 0)·dragend 정합·pageerror 0. 서빙 자산 baked(`_refreshIncidentEdges` grep=4). 스크린샷 육안 정상(graph_middrag 에서 이동 카테고리→데이터소스 관계선이 새 좌표에서 발원).
- Cross-ref: CHG-20260715T190000-graph-edge-follow-drag-postverify · 원천 REV-20260715T181939-graph-edge-follow-drag · ANCHOR 0003 무충돌.

## REV-20260715T211911-graph-cluster-detail-routines [SUBAGENT:graph-cluster-detail-routine-parity-adversarial + 적대 자가검토] — 스키마 클러스터 상세 패널: 함수·프로시저만 있는 컨텐츠 카테고리 누락 수정 (20260715T2119-graph-cluster-detail-routines, Minor §12.3)
- 근본원인: 캔버스 build(`graph-core.js` L64~L78)는 Table+Routine 을 `g.tables` 에 함께 넣어 `_metaSimGroups` 로 컨텐츠 카테고리화하나, 스키마 클러스터 상세 패널 진입점 2곳·렌더가 `label === "Table"` 만 집계 → Routine-only 컨텐츠 카테고리 누락 + 캔버스 불일치. 수정: 두 진입점이 `label === "Routine"` 도 동일 membership predicate 로 수집, 렌더가 `members=tables.concat(routines)` 로 sim-group 계산·렌더.
- **[SUBAGENT] VERDICT — MAJOR 1건 적발 → 수정 반영**:
  - **MAJOR (hiddenKinds parity 위반, 수정 완료)**: 초판이 routine 을 모델에서 **무조건** 수집 — 그러나 캔버스 build(L74-75)는 `_metaGraph.hiddenKinds`(툴바 'ƒ 함수'/'⚙ 프로시저' 토글, localStorage 영속)로 kind 필터를 적용해 숨긴 kind 를 `g.tables`·sim-group 입력에서 제외한다. 초판은 숨긴 routine 을 패널에 계속 표시·집계·sim-group 투입 → 본 변경이 스스로 주장한 "캔버스와 컨텐츠 카테고리 일치" 불변식을 지원되는(비-기본) 모드에서 위반(개수·그룹핑 math 교란, 숨긴 routine 행 클릭 시 렌더 노드 부재로 focus no-op). **수정**: 두 수집 루프에 build 와 동형 guard `!_metaGraph.hiddenKinds.has((n.routine_type==="function")?"function":"procedure")` 추가(graph-ctxmenu.js:977·2245). 재검증 `node --check` PASS.
  - **NIT (수정 완료)**: 설명 문구 "컬럼·파라미터·관계·용어" 가 routine 없는 Table-only 클러스터에도 "파라미터"(routine 전용 개념) 노출 → `_clickHint` 를 `nRoutines` 조건부로("컬럼·파라미터·관계·용어" / "컬럼·관계·용어").
- **[SUBAGENT] 6축 판정(수정 후 유효)**: ① 회귀(Table-only) — `nTables`/`truncNote`/`totalOverride`/`childCols` 전부 `tblList`(테이블) 기준, `members`=tables 복사, `if(members.length)`≡기존 `if(tables&&tables.length)` → **회귀 0**(문구만 확장). ② 정합성 — canvas `g.tables`=Table+Routine 이 `_metaSimGroups` 입력, 패널 `members`=동일; `panel:`+name schemaId 로 stable-order 분리; `_metaRelAdjacency`+routine key 무해(REFERENCES 끝점이 routine 으로 resolve 안 됨). hiddenKinds guard 추가로 **완전 정합**. ③ 누락/중복 — tables(label Table)·routines(label Routine) label-disjoint 무중복; `_metaCatParent===comboId` 로 타 스키마 routine 미유입; flat-scope routine(`_metaCatParent`→null)은 실 comboId 와 불일치라 제외(캔버스 terms 라우팅과 정합); ById terms combo early-return. ④ null/빈값 — `routines||[]`(호출자 2곳 모두 전달 확인), 빈 members 무섹션, 미상 routine_type→⚙/프로시저. ⑤ 80행 cap — members 기준 iterate, 그룹 절단표식 유지, flat fallback `tblList.concat(rtnList)` 라 테이블 우선(routine 이 테이블 밀어내지 않음). ⑥ XSS — routine name/fqn/description/key·group label·tooltip 전부 `esc()`.
- 적대 자가검토(refute): "guard 추가가 status 라인 개수(ById)와 목록 개수를 어긋나게 하나?" → status 의 `routines.length` 도 guard 후 배열 기준이라 목록·설명·status 3자 동일 집합. "hiddenKinds 미초기화 환경?" → `_metaGraph.hiddenKinds` 는 graph-state 초기화 Set(빈 Set 이면 `.has` 항상 false=전량 표시, 캔버스와 동일).
- 검증: `node --check`(module) PASS · [SUBAGENT] 적대 리뷰 MAJOR 1 수정·잔여 correctness 결함 없음 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2119 · CHG/TEST-20260715T211911-graph-cluster-detail-routines · test-runs.d/20260715T2119-graph-cluster-detail-routines.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260715T215241-graph-cluster-detail-cap [SKIPPED:frontend-display-cap-constants-and-heading-emission-no-logic-no-boundary-no-rbac] — 스키마 클러스터 상세: 목록 행 캡이 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 수정 (20260715T2152-graph-cluster-detail-cap, Minor §12.3)
- Panel skip 사유(§18.8): 렌더 캡 상수(80→PER_GROUP 25 + ROW_CAP 500) + "그룹 헤딩 항상 방출" 표시 로직 변경. 데이터/집계/membership/권한/엔드포인트/주입 경계 무변경 → 적대 코드리뷰(권한·주입·enforcement) 이득 없음. 대신 적대 자가검토로 대체.
- 근본원인(라이브 확정): `_metaGraphRenderClusterDetail` sim-group 렌더가 `if (emitted >= 80) return` 로 캡 도달 후 그룹 통째 skip. sim-group 순서 be:(테이블) 우선 → gunzgame(409) 앞쪽 테이블 be: 클러스터 10개가 80행 소진 → 함수·프로시저 컨텐츠 카테고리 전체(헤딩 포함) 렌더 누락(POST-DEPLOY PB-0008 라이브 실측: 렌더 그룹 10개 전부 tbl, rtn=0; aside scrollH 2620·마지막 "전체 순위 (2/3)" 절단).
- 적대 자가검토(refute):
  ① "전역 캡 500 도달 후 그룹은?" → `shown = min(sg.n, 25, max(0, 500-emitted))` = 0 → 헤딩은 방출(카테고리 가시), 멤버 0행 + `(0/n)` 표식. 데이터 손실 아님(개수 정직).
  ② "PER_GROUP=25 가 기존 표시를 줄이나?" → 그룹 멤버 >25 인 그룹만(예 gunzgame 32→25) `(25/32)` 표식으로 정직 절단. ≤25 그룹은 전부 표시(대다수 routine 그룹 = affix family 소형이라 전량 노출). 소형 스키마 회귀 0.
  ③ "개수 모순?" → 헤딩 `sg.n`(전체 개수) 불변, 표식 `(shown/n)` 이 표시분 명시 → 섹션 제목(members.length)·설명(함수·프로시저 N개)·헤딩 개수 3자 정합 유지.
  ④ "패널 폭주(수천 행)?" → ROW_CAP=500 전역 상한 + PER_GROUP=25 이중 바운드. 패널 aside=overflow-y:auto 스크롤(라이브 확인). 500 행 DOM/리스너는 현대 브라우저 수용 범위(기존 80 대비 증가하나 gunzgame 409 실렌더 기준 안전).
  ⑤ "flat 폴백(sgs<2) 정합?" → `slice(0,80)`→`slice(0,500)` 동일 상향, 소형은 무영향.
- [SKIPPED] VERDICT — display-cap 규약 개정, correctness/경계 결함 없음. 캡 도달 후에도 **모든 컨텐츠 카테고리가 헤딩으로 반드시 나타나** 사용자 목표(routine 컨텐츠 카테고리 조회 가능) 달성.
- 검증: `node --check`(module) PASS · POST-DEPLOY PB-0008 라이브(gunzgame 상세에서 함수·프로시저 컨텐츠 카테고리 헤딩+ƒ/⚙ 멤버 행 실렌더·클릭 조회 확인, 잔여).
- Cross-ref: TASK 20260715T2152 · CHG/TEST-20260715T215241-graph-cluster-detail-cap · test-runs.d/20260715T2152-graph-cluster-detail-cap.md · 선행 REV-20260715T211911-graph-cluster-detail-routines · ANCHOR 0003 무충돌.

## REV-20260715T220941-graph-cluster-detail-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 클러스터 상세 함수·프로시저 컨텐츠 카테고리 수정 POST-DEPLOY 실증 기록 (CHG-20260715T220941-graph-cluster-detail-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T211911(routine 집계, [SUBAGENT] hiddenKinds parity MAJOR 수정) + CHG-20260715T215241(cap 개정, [SKIPPED] display-cap 적대 자가검토)은 각 REV 로 검증됨. 본 cycle 은 배포 결과를 원장에 기록만.
- 배포본 실증(win-browser eval, 로그인 세션, 배포 cdee785e, 주입 없이): gunzgame 클러스터 상세에서 함수·프로시저-only 컨텐츠 카테고리 51개 노출(수정 전 0)·⚙/ƒ 칩 멤버 행·⚙ Game_AllItemGet 클릭→routine 노드 상세·캔버스 sim-group 정합·pageerror 0. 스크린샷 육안 정상(gz_routine_groups.png: "계정 조회" 그룹 ⚙ Game_Account*·ƒ Func_IsAccountBoundCustomizeItem 멤버).
- Cross-ref: CHG-20260715T220941-graph-cluster-detail-postverify · 원천 REV-20260715T211911-graph-cluster-detail-routines · REV-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.

## REV-20260715T223744-graph-cluster-detail-fulllist [SUBAGENT:cluster-detail-event-delegation-adversarial + 적대 자가검토] — 스키마 클러스터 상세 컨텐츠 카테고리 목록 전체 출력 + 행 상호작용 이벤트 위임 (20260715T2237-graph-cluster-detail-fulllist, Minor §12.3)
- 근본원인: 직전 cluster-detail-cap 의 전역 상한 500 + 그룹당 25 가 멤버 총합 500 초과 스키마에서 뒤쪽 컨텐츠 카테고리를 `(0/n)`·경계 `(3/5)`로 절단(사용자 스크린샷). 수정: 그룹당 캡 제거 + 전역 상한 500→5000(안전가드)로 전체 멤버 렌더, 행 클릭/hover 를 per-row → 컨테이너 `ul` 이벤트 위임 전환.
- **[SUBAGENT] VERDICT — correctness/회귀 결함 없음(6축 PASS)**:
  - ① 리스너 누적 없음 — 위임을 영속 `el`(#metadataGraphDetailBody) 아닌 **매 렌더 innerHTML 재생성되는 `ul.amgr-cluster-tables`** 에 부착. 직전 ul↔리스너는 외부 참조 없는 자기완결 사이클(블록-local `const _ctUl`)이라 mark-sweep GC 수거. collapse/analyze 버튼은 card head 의 형제(ul 밖)라 위임과 미교차.
  - ② hover 의미 동등 — mouseout `!b.contains(relatedTarget)`(칩↔code 자식 이동 취소 억제, relatedTarget 은 항상 element), 인접행 이동 mouseout(A)→cancel + mouseover(B)→pan 이 원본 mouseleave→enter 순서와 동등(`_metaGraphHoverPan` 이 내부에서 Cancel 선행 — idempotent), `_hoverKey` 로 같은 행 재-pan 억제, window 이탈 relatedTarget=null→cancel. focusout 은 button 만 focusable 이라 안전.
  - ③ 클릭 동등 — `closest(".amgr-ct-row[data-node-key]")` 가 칩/code/desc 클릭 행 승격, 그룹 헤딩(키 없음)→null→no-op. `_metaGraphShowDetail` 은 async(apiFetch await 후 innerHTML 교체)라 클릭 전파 완료 후 ul 교체 — use-after-detach 없음.
  - ④ 전체 출력 — `_metaSimGroups` 반환 `n===tables.length`(동일 배열)라 <5000 스키마는 `shown=len` 전량·trunc 빈값; >5000 은 헤딩 무조건 방출(slice 전) + `(shown/n)` 정직. flat 폴백 `slice(0,ROW_CAP)`.
  - ⑤ 회귀 — 소형 스키마 그룹핑/개수/헤딩 무변경(캡 산술만 변경), `rowHTML`·`esc` byte-동일(XSS·data-node-key round-trip 불변).
  - ⑥ 성능 — 위임 리스너 O(1)(총 5 addEventListener). `_metaSimGroups`/`_metaRelOrderAll` 은 기존에도 전체 멤버 처리(캡은 render-slice 에만 적용)라 신규 알고리즘 비용 0. caveat(결함 아님): ROW_CAP 근처 ~5000 li/button(~20-25k DOM) 1회 innerHTML 동기 렌더는 수백 ms 가능 — "전체 출력" 요청의 수용 트레이드오프, ROW_CAP=5000 가드.
- **NIT 반영**: ROW_CAP 상수를 구획/평면 폴백 공통 스코프로 hoist(리뷰 NIT — 폴백 `5000` 리터럴 하드코딩 drift 위험 제거, 이제 `slice(0, ROW_CAP)`). 잔여 NIT(`_ctUl.contains(b)` 방어적 중복)은 무해로 유지.
- 적대 자가검토: "위임 click 이 재렌더 후에도 stale 참조?" → 클릭은 구 ul 에서 발화·처리 완료 후 재렌더, 신 ul 은 새 위임 획득 — 무해. "5000 초과 실스키마?" → 단일 스키마 테이블+루틴 5000 초과는 비현실(gunzgame 409); 초과 시 헤딩 항상 방출로 discoverability 유지.
- 검증: `node --check`(module) PASS · [SUBAGENT] 적대 리뷰 결함 0 · POST-DEPLOY PB-0008 라이브(500+ 항목 스키마 전 컨텐츠 카테고리 전체 렌더·hover/클릭, 잔여).
- Cross-ref: TASK 20260715T2237 · CHG/TEST-20260715T223744-graph-cluster-detail-fulllist · test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md · 선행 REV-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.
## REV-20260715T231304-graph-cluster-detail-fulllist-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 전체 출력 + 이벤트 위임 POST-DEPLOY 실증 기록 (CHG-20260715T231304-graph-cluster-detail-fulllist-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T223744 은 REV-20260715T223744([SUBAGENT] 6축 결함 0)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 41cf76c5): DK온라인 dk_data_release_main(423항목=123테이블+300함수·프로시저) 상세에서 컨텐츠 카테고리 66그룹 전량·423행·(0/N) 0·routine-only 43그룹·스크롤 12423px; 행 자식 click 위임 승격 조회; pageerror 0. ROW_CAP=5000 결정론적 전체 렌더로 사용자 >500 스키마도 동일 커버.
- Cross-ref: CHG-20260715T231304-graph-cluster-detail-fulllist-postverify · 원천 REV-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.
## REV-20260715T231656-graph-edge-drag-perf [SUBAGENT:pixi-drag-perf-adversarial + 적대 자가검토] — 그래프 드래그 관계선 재그림 per-frame 부하 최적화 (20260715T2316-graph-edge-drag-perf, Minor §12.3)
- 병목: `_refreshIncidentEdges` 프레임당 O(E) 스캔 + incident 엣지 destroy/new Graphics 재생성(GPU 재할당·GC) + 이중 호출. 3 lever(인접 인덱스·in-place 재사용·rAF 코얼레싱)로 공략.
- 적대 자가검토(refute):
  ① "in-place 재사용이 라벨 stale 남기나?" → `_paintEdge` 가 `g.clear()`(geometry) + `g.children.length` 있으면 `removeChildren()`+각 `destroy()`(라벨/bg) 후 재구성. 라벨 없는 대다수 엣지는 children 0 → 오버헤드 0. stale 무.
  ② "재사용 가드가 node/combo 를 오재사용?" → `typeof old.clear==='function'` — Graphics 만 clear 보유(Container 노드/combo 는 없음) + `old.parent===this.world`. edge id↔node id 충돌 시에도 clear 유무로 분기(안전 폴백=destroy+draw). T24 실증.
  ③ "rAF 지연으로 최종 위치 stale?" → dragend `_emitDrag` 가 `_flushEdgeRefresh`(cancel rAF + 즉시 refresh+render)로 최종 위치 동기 반영. destroy 는 `_pendingRaf` cancel. pointerup 후 잔여 rAF 없음.
  ④ "노드 동기·엣지 rAF = 1프레임 괴리?" → 드래그 중 ≤16ms 엣지 지연은 비가시(minimap 뷰포트는 동기). 정확성 무영향. translateElementTo 는 graph-core `_metaNodeDrag`(1849) 단일 호출(드래그 전용)이라 async 안전.
  ⑤ "_edgeIndex stale?" → 토폴로지(source/target) 의존 → 드래그(좌표만 변화) 동안 유효. setData 가 null 무효화 → 다음 draw 재구성. 부재 시 O(E) 폴백(정확성 유지·성능만 degrade). 미해소 끝점 엣지도 인덱스 포함하되 `_refreshIncidentEdges` 의 `if(!a||!b)continue` 가 skip.
  ⑥ "full draw() 회귀?" → `_drawEdge`=`_paintEdge(new Graphics())` — clear/자식정리 no-op(신규) → 종전 byte-동일. draw diff·_objSig·zIndex·sortableChildren 페인트 순서 불변.
- [SUBAGENT:pixi-drag-perf-adversarial] VERDICT — **레버 3종 CONFIRMED correctness 회귀 없음**(8축 refute: node/edge 1프레임 desync·dragend 최종위치·잔여 rAF·_pendingMoved 오염·_edgeIndex stale·guard 오재사용·byte-동일 draw·비-rAF 폴백 전부 clear). `_built.edges` in-place 변이 없음(grep 확증)·setData→draw 항상 후속(graph-core:1108→1116)·translateElementTo 드래그 단일 호출 확인. **반영한 후속 개선(적대 리뷰 지적)**:
  - **P3(perf 실질, 반영)**: `_refreshIncidentEdges` 가 `getElementPosition`(O(N) `nodes.find`)으로 끝점 해소해 실제 O(incident×N)이던 것 → `_nodeById`(draw 구성·setData 무효화) 기반 `_resolvePos` O(1) 로 교체 = O(N+incident). 허브 드래그 이득 실화.
  - **C2(테스트 가능, 반영)**: `draw()` 인라인 인덱스 구성을 순수 `PixiAdapterPure.buildEdgeIndex(edges)` 로 추출 → 자기루프 1회·null/빈·미해소 끝점 포함 계약을 T25 로 잠금.
  - **C1/C3/C4(실-경로 테스트, 반영)**: T24 가 `_paintEdge`/인덱스를 stub 했던 공백을 T25 로 보강 — 실 `_paintEdge`(clear+stale 라벨자식 destroy+재-path·이중렌더 아님)·재사용불가 else 분기(clear 없는 Container→destroy+_drawEdge)·미해소 끝점 skip 실검증.
  - **P1(검증 계약, 조치)**: rAF 지연으로 mid-drag(pointerup 전) 스냅샷이 stale → PB-0008 은 **pointerup 후**(dragend 동기 flush) 또는 프레임 대기 후 캡처. P2(destroy this.world 미null, 도달불가 defense-gap)·N1(edge-id↔node-id 충돌, 기존 동작·본 변경 미도입)은 non-blocking 기록.
- 검증: `node --check`(ESM) PASS · 헤드리스 T24 10종 + T25 13종 + T23 회귀 ALL PASS **96/0** · [SUBAGENT] 적대 리뷰 결함 없음 + 지적 4건 반영 · POST-DEPLOY PB-0008 라이브(대형 스키마 드래그 프레임률·cross-category 추종 정확성 유지, 잔여).
- Cross-ref: TASK 20260715T2316 · CHG/TEST-20260715T231656-graph-edge-drag-perf · 선행 REV-20260715T181939-graph-edge-follow-drag(추종 정확성 정본) · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## REV-20260716T000000-graph-edge-drag-perf-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 그래프 드래그 관계선 재그림 최적화 POST-DEPLOY 라이브 실증 기록 (CHG-20260716T000000-graph-edge-drag-perf-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260715T231656 은 REV-20260715T231656([SUBAGENT] 적대 리뷰 결함 없음 + 지적 4건 반영)로 검증됨. 본 cycle 은 배포 결과 원장 기록만.
- 배포본 실증(win-browser eval, pointerup 후 캡처): 추종 정확성 유지(root 카테고리 + gunzgame 409 dense-edge)·정량 부하개선(40move=30.4ms·burst 중 rAF 0=코얼레싱)·dragend 정합·pageerror 0. 서빙 baked.
- Cross-ref: CHG-20260716T000000-graph-edge-drag-perf-postverify · 원천 REV-20260715T231656-graph-edge-drag-perf · ANCHOR 0003 무충돌.

## REV-20260716T003901-graph-cluster-detail-collapse [SUBAGENT:cluster-detail-collapse-disclosure-adversarial + 적대 자가검토] — 스키마 클러스터 상세: 컨텐츠 카테고리별 접기/펼치기 (20260716T0039-graph-cluster-detail-collapse, Minor §12.3)
- 변경: 컨텐츠 카테고리(sim-group) 헤딩을 접기/펼치기 disclosure(role=button·aria-expanded·캐럿)로, 토글 시 헤딩~다음 헤딩 전 멤버 행 display 토글, 접힘 상태 `_metaGraph.panelGroupCollapsed` 유지, 섹션 헤더 '모두 접기/펼치기'. 기존 `ul` 이벤트 위임 확장.
- **[SUBAGENT] VERDICT — BLOCK/MAJOR 결함 0**. 7축(헤딩vs행 분기·토글 순회·초기 접힘 정합·모두 접기/펼치기·리스너 누적·키보드/포커스·회귀/XSS/CSS) 전부 PASS. MINOR 2 + NIT 1 적발:
  - **MINOR #1 (수정 반영)**: '모두 접기/펼치기' 라벨이 개별 토글 후 stale(동작은 self-consistent·데이터손상 없음, 표시만 오해소지). → `_syncCollapseAllLabel()`(전 그룹 상태로 라벨 재계산)을 `_toggleCtGroup` 말미에서 호출; collapse-all 핸들러의 수동 라벨 설정 제거(중복). 개별·일괄 토글 모두 라벨-동작 정합.
  - **MINOR #2 (수정 반영)**: 함수-지역 `esc`(2262)가 `"` 미이스케이프(파일 내 1358/1648/1774 esc 는 이스케이프). `data-group-key`/`aria-label`/`title` 속성이 상태-키 라운드트립을 실어 나르므로 `"` 포함 식별자 시 속성 breakout 가능(선재 패턴이나 data-group-key 는 새 sink). → esc 에 `.replace(/"/g,"&quot;")` 추가(파일 내 강한 esc 와 정합). 텍스트 노드엔 무해.
  - **NIT #3 (선재·미수정)**: 패널 sim-group/접힘 keyspace 가 comboId 아닌 표시명(`"panel:"+_metaComboName`) 기반 → 동명 스키마 동시 표시 시 충돌 가능. 단 기존 `groupOrder`/`groupTableOrder`(graph-simgroups)가 이미 동일 keyspace 공유 — 본 기능이 상속했을 뿐 새로 유발 안 함(표시명 데이터소스 내 유일 시 무해). 별도 개선 대상.
- **[SUBAGENT] 7축 판정**: ① 헤딩(`.amgr-ct-group`)·행(`.amgr-ct-row-li`) ul 형제·무중첩, 자식 클릭 `closest` 귀속, 헤딩 먼저 판정+return → 오분류 0. ② `nextElementSibling` while 이 다음 `.amgr-ct-group` 에서 정확히 멈춤·마지막 그룹 끝까지·헤딩 사이 이물 노드 없음. ③ `collapsed`(panelGroupCollapsed.has)가 is-collapsed/caret/aria-expanded/행 amgr-ct-collapsed 일관, sg.key 동일 클러스터 결정론 안정. ④ `anyExpanded ? !isCol : isCol` 혼합상태 정확·재렌더 리스너 누적 0. ⑤ _toggleCtGroup 렌더별 새 클로저·위임 `ul` 재생성·collapse-all 새 버튼 재바인딩. ⑥ Enter/Space 헤딩 토글·Space preventDefault·행 button 네이티브 클릭 보존(role=button li 미합성). ⑦ 행 클릭/hover/전체출력/개수 불변·`[data-group-key]` presence 선택자만·CSS `*/` hazard 없음.
- 적대 자가검토: "esc 강화가 텍스트(`<code>`,`<strong>`) 렌더 회귀?" → `"`→`&quot;` 는 텍스트 노드에서 `"` 로 렌더(시각 동일)·속성값에서만 실효. "sync 라벨이 flat 폴백(버튼 부재)서 throw?" → getElementById null-guard + groups.length 가드.
- 검증: `node --check`(module) PASS · [SUBAGENT] 6/6→7/7축 PASS·MINOR 2 수정·NIT 1 선재 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0039 · CHG/TEST-20260716T003901-graph-cluster-detail-collapse · test-runs.d/20260716T0039-graph-cluster-detail-collapse.md · 선행 REV-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.

## REV-20260716T005817-graph-cluster-detail-collapse-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 접기/펼치기 POST-DEPLOY 실증 기록 (CHG-20260716T005817-graph-cluster-detail-collapse-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260716T003901 은 REV-20260716T003901([SUBAGENT] 7축 BLOCK/MAJOR 0·MINOR 2 수정)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 00454608): DK dk_data_release_main(66 컨텐츠 카테고리) 상세에서 헤딩 클릭 접기/펼치기·모두 접기/펼치기(라벨 정합)·재렌더 접힘 유지·키보드 토글·행 클릭 조회 불변·pageerror 0. 스크린샷 육안 정상(접힘 ▸/펼침 ▾ 캐럿 공존).
- Cross-ref: CHG-20260716T005817-graph-cluster-detail-collapse-postverify · 원천 REV-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## REV-20260716T012805-graph-cluster-detail-group-hoverpan [SUBAGENT:cluster-detail-group-hoverpan-adversarial + 적대 자가검토] — 스키마 클러스터 상세: 컨텐츠 카테고리 헤딩 hover-pan (20260716T0128-graph-cluster-detail-group-hoverpan, Minor §12.3)
- 변경: 컨텐츠 카테고리 그룹 헤딩에 hover 시 카메라 팬 추가. 헤딩 `data-pan-key` + 기존 `ul` hover 위임 확장(`_panTargetOf`) → `_metaGraphHoverPan` 재사용.
- **[SUBAGENT] VERDICT — diff 도입 BLOCK/MAJOR/MINOR 결함 0**. 6축(GB키 fam정합·미렌더폴백·hover위임·collapse상호작용·회귀·XSS/제어문자) 전부 PASS. #1 에 **runtime-confirm caveat** 지적: 초판 타깃 = 캔버스 그룹 박스 `GB:comboId+·+fam` — 카드클릭 경로(`_metaGraphShowClusterDetailLocal`, 모델 테이블 = 캔버스 `g.tables` 동일 predicate)는 fam **정확 일치**하나, 콤보/히스토리-뒤로 경로(`_metaGraphShowClusterDetailById`, API depth=1 테이블 우선)는 API↔모델 집합 divergence 시 fam 이 갈려 GB 키 불일치 가능(단 graceful no-op·오타깃 아님·API 집합 그룹핑은 선행 상속이라 신규 결함 아님).
- **설계 변경(caveat 근본 제거)**: 타깃을 **GB 박스 → 그룹 첫 멤버 노드 key(`sg.tables[0].key`)** 로 전환. (a) 첫 멤버는 항상 실 노드라 진입경로·fam 정합 **무관**하게 견고, (b) 행 hover-pan 과 **동일하게 노드로 팬** → 사용자 "다른 객체와 동일하게" 에 더 부합, (c) sim-group 이 캔버스에서 조밀 박스로 팩되므로 첫 멤버 팬 = 그 카테고리 영역 진입, (d) 제어문자(0x01)·String.fromCharCode·fam-매핑 전부 제거(소스 단순·리터럴 0x01 부재 재확인).
- **[SUBAGENT] 6축 판정(설계변경 후 유효)**: ① fam정합 우려 자체가 소거(노드 key 직접) — 리뷰의 "테이블-집합 parity 의존" 무의미화. ② 미렌더/폴백 — 첫 멤버 미렌더(접힘/컬링) 시 `_metaRenderedIdFor`||`_metaRenderedAncestorFor` null → no-op(행 동형). ③ hover 위임 — `_panTargetOf` 행 우선·헤딩 나중, 자식 hover closest 승격, `_hoverKey` 행↔헤딩 재-pan/억제 정합, mouseout 다중선택자+`contains(relatedTarget)`. ④ collapse — click(data-group-key 토글)·hover(data-pan-key 팬) 이벤트/속성 분리, `data-pan-key` collapsed 무관 항상 방출 → 접힌 헤딩·모두접기 후에도 팬. ⑤ 회귀 — `_rowKeyOf`(click 행 전용)·click·collapse·전체출력 미접촉, hover 경로에만 추가. ⑥ XSS — `data-pan-key="${esc(_panKey)}"` esc 적용, 첫 멤버 key 는 기존 `data-node-key` 와 동일 sink.
- 적대 자가검토: "첫 멤버가 API 경로서 미렌더면?" → 펼친 스키마는 모델에 전 테이블 로드·API depth=1 = 동일 테이블이라 렌더됨; 드문 divergence 도 no-op(무해). "헤딩 hover 가 행 hover 와 대상 중복?" → 첫 멤버 노드 = 헤딩 아래 첫 행과 동일 노드라 hover 위치만 다르고 팬 대상 일관(혼란 없음).
- 검증: `node --check`(module) PASS · [SUBAGENT] 6축 결함 0 + caveat 설계변경으로 소거 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0128 · CHG/TEST-20260716T012805-graph-cluster-detail-group-hoverpan · test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md · 선행 REV-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## REV-20260716T015146-graph-cluster-detail-group-hoverpan-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 컨텐츠 카테고리 헤딩 hover-pan POST-DEPLOY 실증 기록 (CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 postdeploy 실증 기록). 실 구현 CHG-20260716T012805 은 REV-20260716T012805([SUBAGENT] 6축 결함 0·GB→첫멤버 전환)로 검증됨. 본 cycle 은 배포 결과 기록만.
- 배포본 실증(win-browser, 배포 d2c72fdc): DK dk_data_release_main 상세에서 66 그룹 전부 data-pan-key=첫 멤버 노드; 헤딩 hover → 카메라 팬("NPC 콘텐츠"↔"게임 콘텐츠 조회" 서로 다른 영역·미니맵 이동); 행 hover/클릭 불변; pageerror 0. 스크린샷 육안 정상(뷰 이동 확인).
- Cross-ref: CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify · 원천 REV-20260716T012805-graph-cluster-detail-group-hoverpan · ANCHOR 0003 무충돌.

## REV-20260716T010501-doc-sync-rn-0716 [SKIPPED:non-policy-doc] — 릴리즈노트 07-15 블록 신규 7항목(관계도 우클릭 정합·상세목록 함수/프로시저 포함+접기·드래그 연결선 추종·ENUM 묶음 승인·권한 '접근'+원자화·'AI 추론' 콘솔·답변 정확도) (TASK-20260716T010501-doc-sync-rn-0716, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피·operational gate 는 doc_sync 가 정본(feature-0003 TASK graph-cluster-detail/ctxmenu/edge-drag/enum-bundle/perm-*·feature-0002 TASK attach-coverage/schema-case/alias-guard·feature-0021 REVIEW/admin_reasoning + git log 07-15~16) 대비 직접 검증(ULTRACODE 3-타깃 병렬 analyze→적대 verify wf_01d7fc19-550).
- 적대 대조(정본): 07-15~16 사용자 화면 신규/개선 = 관계도 우클릭 3대상 정합(#808/815/820)·상세목록 함수프로시저+접기(#827/828/830/835)·드래그 연결선 추종+성능(#824/832)+도움말(#804)·ENUM 묶음 승인(#811/817)·권한 카테고리+원자화(#801/810)·'AI 추론' 콘솔(feature-0021 affeea67·#821 라이브 검증)·답변 정확도(#823/803/809/813/807/826/833·feature-0021 자체점검). 제외=각 *-postverify(문서)·#805 friction-ledger(내부)·probe/throttle 내부 안정성(⑥ 포괄). feature-id/§/PR#/테이블/함수/권한키/라이브러리/red-team 누출 0(vm leak 스캔).
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(30 releases·07-15 head 7항목[admin 6·common 1]·07-14 보존 10·스키마·누출0). item #6 area='common' = 직전 07-14 블록 ⑩ 답변정확도 area='common' 선례 정합(직접 재확인).
- **pre-existing 무관 실패 정직**: `verify_release_notes.mjs` 33/34 PASS·1 FAIL([스크롤] admin release-notes pane overflow-y:auto 정규식) — `styles.css`(본 cycle 미변경) 대상, 규칙(line 4386 `overflow-y:auto`)은 실재하나 선택자~속성 사이 설명 주석(~200자)이 테스트 160자 정규식 창 초과 → false-negative. pristine HEAD(data 편집 stash)에서 동일 FAIL 재현으로 무관 확인. feature-0003 테스트 정규식 brittleness 는 feature cycle 소관(doc_sync 는 product CSS/feature test 미편집).
- **cache-buster**: 소스 `?v=dev` 고정 — 07-12 ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. system-prompt 의 '수동 bump' 지시는 그 정책 이전 모델 기준이라 부적용(수동 변경 시 injector placeholder 매칭 무력화·해당 2파일 캐시무효화 상실). 직전 doc-sync-rn-0713/0714/0715 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260716T010501-doc-sync-rn-0716 / META REV-20260716T010501-META-0037-doc-sync-0716(별도 commit 0cc64c2b) / 원천 PR 07-15~16. **landing/배포 소유=cron wrapper 위임(로컬 commit 만).**

## REV-20260716T140735-doc-sync-rn-0716b [SKIPPED:non-policy-doc] — 릴리즈노트 07-16 블록 신규 4항목(관계도 검색 확대/결과 목록·상세 [뒤로/앞으로] 탐색 UX·카테고리 헤딩 hover 이동·콘솔 유사 화면 서브탭 통합) (TASK-20260716T140735-doc-sync-rn-0716b, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·중복회피는 doc_sync 가 정본(feature-0003 TASK graph-search-panel-groups/graph-search-detail-panel/graph-cluster-detail-group-hoverpan·feature-0016 TASK graph-detail-scroll/nav-sticky/nav-hover-fade/nav-focus-fade-fix·feature-0021 TASK/FUNCTION console-ia/subtabs + git log 07-16 PR #837~#853) 대비 직접 대조 검증.
- 적대 대조(정본): 07-16 낮 사용자 화면 신규/개선 = 그래프 검색 콘텐츠 카테고리·AI 분석 매칭(#837)+상세 패널 검색 결과 리스트(#839)+2단 접기·이력·간결화(#846)·상세 [뒤로/앞으로] 스크롤 보존(#841)·sticky(#843)·hover-fade(#844)+fix(#845)·카테고리 헤딩 hover-pan(#838)·콘솔 IA 감사/설정 분리(#847)+서브탭 통합(#850)+sticky(#852). 제외=각 *-postverify(문서)·권한 재배치 내부 체계. feature-id/§/PR#/권한키/함수명 누출 0.
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(31 releases·07-16 head 4항목[admin 4]·07-15 보존 7·스키마·누출0).
- **cache-buster**: 소스 `?v=dev` 고정 — ITEM-09 what#3(`inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트) 이후 수기 bump 폐지. 직전 doc-sync-rn-0713~0716 동일 판단.
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260716T140735-doc-sync-rn-0716b / META REV-20260716T140735-META-0038-doc-sync-0716b(별도 commit) / 원천 PR #837~#853. **attended run — landing/배포 스킬 소유.**

## REV-20260722T010501-doc-sync-rn-0722 [SKIPPED:non-policy-doc] — 릴리즈노트 07-21 블록 신규 1항목(진행상황 실시간 전파) (TASK-20260722T010501-doc-sync-rn-0722, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(a999594e frontend-only 머지→wrapper 배포로 라이브·별도 활성 불요)·area(work — 대화/작업 화면 가시 변화)·누출 회피는 doc_sync 가 정본(feature-0003 TASK/REPORT realtime-progress-propagation + git log 8f3dd00b..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_b9eb441a 초판 — feature-0022 상태 오류 등 8건 적발 → 정정, wf_97d7d599 정정 재검증).

## REV-20260721T175800-realtime-progress-propagation [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (고위험 결함 0, low-med 2건 반영·1건 정밀화·2건 bounded 문서화)
- 대상: `static/app.js` 유휴 run-감지 폴러 diff(+133/추가 함수 `detectNewRun`·`scheduleRunDetectPolling`·`startRunDetectPolling`·`stopRunDetectPolling`·`clearRunDetectTimer` + `loadHistory`/`selectConversation`/`handleLogout`/`visibilitychange` 배선). 적대 리뷰 프롬프트: 폭주/중복 폴링·lifecycle 누수·baseline race·feature-0009 foreign-run 하이재킹·myAskInFlight 오귀속·비용/백오프·일반 correctness.
- 종합 판정: **핵심 메커니즘 건전** — seq-gating(monotonic `runDetectSeq` + stale bailout)과 4-신호 dormant 가드가 (a) 활성 폴러와의 중복 fetch, (b) 로컬 본인 run 하이재킹("처리 중" 고착)의 두 최악 시나리오를 정확히 차단. runaway-timer/stuck 시나리오 구성 실패(=안전).
- **D1 (low-med, 반영)**: 감지기가 트리거한 `loadHistory()` 가 throw(`/api/history` 네트워크 blip)하면 `reschedule=false`(await 전 설정)+outer catch 삼킴 → 감지기 영구 disarm. **Fix**: `_detectHandoffReload(seq)` 헬퍼 도입 — loadHistory 성공 시 loadHistory 가 감지기 상태 관장(idle 재무장/processing 정지), throw 시 seq 유효하면 재무장. 회귀 테스트 S7 추가.
- **D3 (pre-existing, 정밀화 반영)**: `myAskInFlight.add` 가 `!isGroupConversation` 만 게이트해 **모니터링(타 계정 소유) 1:1** 도 포함 → 유휴 감지기가 loadHistory 자동 트리거 시 관찰자에게 동작 안 하는 중단/즉시답변 버튼 오표시(cosmetic·send/cancel 은 백엔드 권한 차단). 리뷰어 확인 "신규 회귀 아님". **Fix**: 문서화된 의도("본인 대화")대로 `isOwnConversation() && !isGroupConversation()` 로 정밀화(그룹은 종전대로 제외).
- **re-entrancy(반영)**: `detectNewRun` 재진입 가드 부재(리뷰어: 최대 1회 transient 중복 fetch) + `runDetectInFlight` write-only dead-state 지적 → dormant 가드에 `state.runDetectInFlight` 추가(dead-state 를 re-entrancy 가드로 활용). 회귀 테스트 S8 추가.
- **방어(반영)**: `beginPendingConversation`·`_switchToPendingConversationContext` 가 `stopProgressPolling` 만 하고 `stopRunDetectPolling` 누락(리뷰어: activeConversationId="" 로 self-terminate 하므로 현재 무해하나 fragile asymmetry) → lifecycle 대칭 위해 `stopRunDetectPolling()` 추가.
- **D2 (bounded, 문서화)**: 무장 후 첫 폴링에서 `loadHistory`↔첫 `/api/progress` 사이(1 라운드트립) run 이 start+complete 하면 그 terminal run 이 baseline 에 흡수돼 미로드. 첫 폴링 한정·다음 run 에서 self-heal — 원 버그의 축소 잔재(신규 회귀 아님). 완전 봉인은 `/api/history` 가 terminal run_id 도 반환하는 백엔드 변경 필요(feature-0012 라우터분할 충돌 회피 위해 이연). 
- **hide/show gap (bounded, 문서화)**: 탭 숨김 중 run 이 전부 완료되면 재가시 시 다음 run/전환 전까지 미반영(재가시는 미래 감지만 arm). pre-feature 거동과 동일(신규 회귀 아님)·숨김 중엔 "실시간" 관측 불가라 실질 영향 경미.
- **비용(정상)**: 숨김 탭 `stopRunDetectPolling` 로 완전 정지·활성 탭 4s clean reschedule — 백오프 정상. "모든 대화 유휴 폴링" 은 사용자 선택 scope 의 product 결정(구현 결함 아님).
- 반영 후 검증: `node --check` PASS · 유닛 `verify_run_detect_poll.mjs` **28/28**(D1 재무장 S7·re-entrancy S8 포함). feature-0009 그룹 경로 안전(리뷰어 확인 — foreign run 을 progressRunId 로 채택, 5870 가드 무충돌).
- Cross-ref: CHG-20260721T1758-realtime-progress-propagation · ANCHOR feature-0003 §1-§3 무충돌 · TEST §16.6 PB-0008 PASS(실 Windows Chrome 150).

## REV-20260722T020408-msg-edit-textarea-contrast [SKIPPED:trivial-display-only] — 메시지 '수정' 편집 UI 글자 비가시 수정 + 편집 폼 재구성 (20260722T020408-msg-edit-textarea-contrast, Minor §12.3)
- Panel skip 사유(§18.8): 순수 표시 변경 — `styles.css` 색/특이도 규칙 + `app.js` 1행 `classList.add`. 백엔드·엔드포인트·RBAC·스키마·편집 로직(`_submitMessageEdit`·브랜치·IDOR 게이트) 0, 보안 posture 불변. 선례 REV-20260716T051931-ds-test-gate-fix([SKIPPED:trivial-regression-fix-display-only]) 와 동류(§18.8 표: display-only 프론트 표시 수정 → full 패널 skip).
- 적대 자문점 자체점검: ① 특이도 — 신규 `.message.is-user .message-bubble.message-bubble-editing`(0,4,0) > 파랑 `.message.is-user .message-bubble`(0,3,0), 실브라우저 렌더로 bubble bg=흰 서피스(255,255,255) 실측 확인. ② 클래스 충돌 — `message-bubble-editing` unique(기존 `is-editing`(admin dashboard)·`.dashboard-widgets.is-editing` 와 선택자 분리). ③ 잔존 위험 — 재렌더로 클래스 소멸(취소=renderMessages/성공=refreshWorkspace) → 편집 취소 후 말풍선 원래 파랑 복귀. ④ 회귀 — 편집 진입(innerHTML 교체) 컨텍스트에만 적용, 일반 말풍선/컨텐츠 렌더 미접촉. ⑤ 라이트 전용 콘솔(styles.css H1)이라 다크 분기 불요.
- 검증: `node --check` PASS · headless Chromium 실측(수정본 textarea 15.38:1·재답변버튼 5.17:1·편집 말풍선 중립전환 / 수정전 1.0:1 버그 재현) + 스크린샷 · POST-DEPLOY PB-0008 Windows-browser(잔여, visual_verification_scope=always).
- Cross-ref: CHG/TASK/TEST-20260722T020408-msg-edit-textarea-contrast · feature-0019 ANCHOR §1-§3 무충돌.

## REV-20260722T024500-msg-edit-textarea-contrast-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 메시지 편집 UI 대비 수정 POST-DEPLOY 라이브 실증 기록 (CHG-20260722T024500-msg-edit-textarea-contrast-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 코드 리뷰 정본 = REV-20260722T020408-msg-edit-textarea-contrast([SKIPPED:trivial-display-only]). 본 cycle 은 배포(f7a14e9a)+Windows Chrome 150 라이브 실측 결과 append 만.
- 실증: textarea color=rgb(38,37,30) on bg=rgb(255,255,255)(대비 ~15.4:1)·편집 말풍선 `message-bubble-editing`=true·bg=흰 서피스(중립 전환)·재답변버튼 흰글자 on 파랑 + 스크린샷 육안. 사용자 신고(흰 글자 on 흰 배경) 해소 확인.

## REV-20260722T125200-point-rail-range-window [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (Major §12.3 — feature-0003 web/UI, /_template:entry arg-given dispatch)
- 요청 해석: "우측 대화 뱃지" = 메인 뷰 point rail(`app.js`/`styles.css`). 공유 읽기전용 뷰(`share.*`)는 별도 코드라 범위 제외("assistant와 대화를 주고받는 화면"=메인). 3요구 A(범위화)/B(클릭 비례)/C(윈도잉).
- 설계 판단:
  - A: rail 을 대화 세로 미니맵으로. top%/height% 는 messageLog scrollHeight 대비(기존 중심점 top% 와 동일 기준) → rail(뷰포트 높이)에 압축 표시. min-height 로 짧은 메시지 클릭성 보장.
  - B: 신규 `scrollMessagePointToRatio` 로 클릭 y→메시지 [top,bottom] 매핑. 기존 center 함수는 검색/앵커 점프가 재사용하므로 비파괴 유지.
  - C: 신규 DOM 가상화 대신 **기존 `loadHistory` 서버 페이징 재사용**(회귀면 최소화 — 완전 가상화는 첨부/읽음/optimistic/live-poll 상호작용 위험 큼). "화면 4배만 로딩"=초기 로드 목표 높이(하한 채움). 아래로 unload 미수행(요청은 "추가 로딩"만).
- 적대 코드리뷰(REV subagent) 반영: R1(cross-conversation `state.messages` 오염 — `loadHistory` gen-guard)·R2(프로그래매틱 점프 중 자동로드가 목표 어긋냄 — `_pointScrolling`)·B1(전역 `_fillingWindow` 가 빠른 전환 시 새 대화 fill 억제·이전 루프 오염 — 대화별 `_fillToken`). 핵심 우려 preserveScroll flag leak 은 flag 제거 재설계로 원천 소거(리뷰어 moot 확인).
- Known limitation B2 (코너케이스, 미수정): append(과거 자동로드)와 그 대화의 processing 새 run pending-bubble 최초 생성이 동시일 때, `_endAppendScrollPreserve` 의 `delta = scrollHeight - preH` 가 바닥 성장분(pending bubble)을 포함해 소폭 과도 스크롤(뷰가 pending 높이만큼 위로 튐). 발생 조건 희소(유휴 과거 탐색 중 새 run 최초 pending)·자기치유(다음 클린 로드)·영향 경미(pending 높이 소). 별도 cycle 재검토 여지.
- 위험도 Major: 다중 파일·스크롤 로직·회귀 위험(신규 가상화 아님·기존 페이징 재사용으로 완화). 비파괴 additive — 인증/인가/데이터 무영향.

## REV-20260722T135500-point-rail-range-window-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 시각검증 기록 (CHG-20260722T1355-point-rail-range-window-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 코드 리뷰 정본 = REV-20260722T125200-point-rail-range-window([SUBAGENT:general-purpose]). 본 cycle 은 배포(22c3b9cb)+Windows Chrome 150 라이브 실측(A·B 라이브 PASS·C 자동 페이징 20개+ 대화 부재로 미트리거) 결과 append 만.

## REV-20260722T142000-point-rail-range-window-dom-windowing [SUBAGENT:general-purpose] — ACCEPTED-WITH-FIXES (윈도잉 강화, Major §12.3 — feature-0003 web/UI, 사용자 후속 요청)
- 사용자 후속 요청: "다른 대화도 확인하여, 이전 대화가 너무 많이 불러와졌을 경우 일부만 로딩되는지 검증". 라이브 실측에서 이 환경 대화 모두 20개 미만(hasMoreHistory=false)이라 서버 페이징 gap 발견 — 20개 미만이나 높이 4배 초과 대화(conv 14개·높이 20배)가 전부 렌더됨. → `state.renderCount` DOM 윈도잉으로 진짜 4배 상한 구현.
- 적대리뷰(general-purpose subagent) 반영: **발견1(필수·회귀)** `_visibleMsgs.forEach` 의 `_msgIdx` 가 절대→창-상대로 바뀌어 `_precedingUserQuestion`(피드백 Q↔A 매칭)·투표 게이트·공유 range idx 비교가 윈도잉된 긴 대화(주 사용 케이스)에서 깨짐 → `_windowBase` 로 절대 인덱스 복원. 발견2(floor 칩 창밖 — loadHistory renderCount 리셋 시 floor 포함). 발견5(검색 첫 매칭이 optimistic id=null 이면 중단 — skip). 발견6(주석).
- Known limitation(미수정, 엣지): 발견3(윈도잉+위 스크롤 중 live-poll 도착 시 tail 창 슬라이딩으로 scrollTop 보존이 어긋나 소폭 튐)·발견4(`_maybeExpandOrLoadOlder` 확장이 짧은 메시지 다수 시 여러 배치 연쇄 — total 상한이라 무한 아님·순간 부하). 별도 cycle 재검토 여지.
- 위험도 Major: `renderMessages` 렌더 경로 변경(창 렌더). 비파괴 additive — 인증/데이터 무영향.

## REV-20260722T144000-point-rail-window-initial-tuning [SKIPPED:param-tuning-no-logic-change] — 윈도잉 초기 렌더 개수 튜닝
- Panel skip 사유(§18.8): 상수(`WINDOW_INITIAL_RENDER` 8→3) 1개 변경, 로직 불변. 윈도잉 구현 리뷰 정본 = REV-20260722T142000-...([SUBAGENT:general-purpose]). 라이브 실측 근거(conv[2] 초기 8개=높이 13배 → "4배만" 미달)로 초기값만 하향.

## REV-20260722T145000-point-rail-windowing-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 윈도잉 라이브 재검증 기록 (CHG-20260722T1450-point-rail-windowing-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 윈도잉 구현/튜닝 리뷰 정본 = REV-20260722T142000-...([SUBAGENT])·REV-20260722T144000-...([SKIPPED:param-tuning]). 본 cycle 은 배포(66d1e735) 라이브 실측(conv[2] 초기 3개·확장) append 만.

## REV-20260722T192736-history-top-indicator [SKIPPED:trivial-display-only] — 대화 상단 페이드 신호 (Minor §12.3 — feature-0003 web/UI, /_template:entry 후속)
- Panel skip 사유(§18.8): 순수 표시 변경 — 페이드 div 1개(pointer-events:none) + CSS gradient + `_updateHistoryTopIndicator`(renderCount/hasMoreHistory 판정으로 hidden 토글). 백엔드·엔드포인트·RBAC·스키마·편집 로직 0, 보안 posture 불변. 선례 REV-20260722T020408-msg-edit-textarea-contrast([SKIPPED:trivial-display-only])·ds-test-gate-fix 와 동류.
- 설계: 사용자 검토 후 결정 — 페이드만(칩·스피너·텍스트 제거로 난잡함 회피), 점프=캘린더·로드=스크롤 자동. 위에 더 있음 판정 = `renderCount<total || hasMoreHistory` (윈도잉 창 밖 + 서버 미로드 둘 다 포함).

## REV-20260722T195000-history-top-indicator-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 라이브 검증 기록
- Panel skip 사유(§18.8): 코드 0(문서 전용 POST-DEPLOY 실증). 구현 리뷰 정본 = REV-20260722T192736-history-top-indicator([SKIPPED:trivial-display-only]). 배포(029927dc)+라이브 실측(페이드 표시/숨김/무방해) append 만.

## REV-20260722T122635-shared-branch-readonly-paging [SUBAGENT:general-purpose] — SHIP-WITH-FIXES (1 real-defect 반영, 6축 not-a-defect, 신규 누출 0) — 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징 (20260722T122635, Major §12.3, PLAN-APPROVED design-review C)
- §18.8 적대적 **보안** 리뷰(general-purpose, 7축). **익명 공유 뷰 신규 누출 없음** — 변경 전 `_share_load_messages` 는 [floor,anchor] 내 모든 브랜치를 평면 노출했고, 이 변경은 기본 노출을 active 브랜치로 축소 + branch_view 도 동일 id-범위로만 한정(범위 밖 content·존재 차단). 배포 차단 사유(누출) 없음.
  - **[3] real-defect (반영 완료)**: 브랜치된 그룹의 **평문 멤버 채팅**(`_save_group_chat_message_pg`)이 parent 없이·leaf 전진 없이 고아 삽입 → 새 active-path 필터(그룹 enrich)에서 결정론적 은닉(멤버 채팅 사라짐, availability 회귀). 옛 SEC MINOR-B skip 이 이걸 막던 것. **수정**: `_save_group_chat_message_pg` 의 두 store 쓰기를 has_branches 시 active_leaf 에 체인+전진(memory.py 래퍼 로직 답습). 비분기는 parent None(무회귀). 회귀 테스트 2건(체인/비분기) 추가.
  - **[1] 범위 밖 버전 누출 not-a-defect**: `_branch_version_groups(visible_pred)` count/sibling 배제 + `_branch_resolve_readonly_leaf` fail-closed. leaf-범위안·조상/후손-범위밖 우회도 (messages ∩ active_ids) 교집합 + 형제≠후손으로 차단. 존재 oracle 없음(범위밖/미존재 응답 동일).
  - **[2] active-path 조상 누출 not-a-defect**: 교집합 `messages`(상위 window/id-범위 필터됨)가 방어 — 범위 밖 조상은 애초에 messages 부재.
  - **[4] 읽기전용 불변 not-a-defect**: override 경로 로컬 변수만·DB 미기록. `/branch/switch`·reanswer 그룹 400 유지(INV-4).
  - **[5] 주입/타입 not-a-defect**: branch_view int 강제·공유는 try/except→None. resolver SELECT `conversation_id=%s AND id=%s` 로 타대화/음수/거대 무매칭→None. leaf CTE table allowlist+cid 스코프.
  - **[6] 비분기/1:1 회귀 not-a-defect**: has_branches=false 전체 skip. 1:1 owner(window=None→pred None→전체) 페이징·switch 영속 불변. FE 1:1 은 `_switchBranch` 영속 라우팅 유지.
  - **[7] fail-soft not-a-defect**: enrich 예외 시 원본 반환 — 그러나 messages 는 상위 window/id-범위로 이미 잘려 범위 밖 누출 불가(옛 flat 수준으로만, 경계 내).
  - **[3-2] 권고(bounded 문서화)**: 브랜치된 그룹 **동시 @assistant overlap** 시 cross-run fork 로 한쪽 turn 이 비활성 sibling 으로 갈 수 있음(per-run 커서는 run 내부만 봉인 — branch-chain-race fix 의 알려진 경계, [5] version-active 격하). 드묾·availability(누출 아님)·재답변으로 복구 가능. 후속 하드닝(첫 write active_leaf read 를 SELECT FOR UPDATE 직렬화) 여지 — 본 cycle 범위 밖 문서화.
- 반영 후 검증: `py_compile` 5 + `node --check` 2 · 보안 단위 `tests/test_shared_branch_readonly_paging.py` **12 PASS**(id-범위/window 스코핑·resolver fail-closed·[3] 그룹채팅 체인/비분기 무회귀) · feature-0003 전체 회귀(예정).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260722T122635 · feature-0019 ANCHOR INV-4 개정(mutation 잠금 유지+read 가시성 확장) · POST-DEPLOY 양 surface PB-0008.

## REV-20260722T130000-shared-branch-readonly-paging-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 공유 읽기전용 페이징 배포 + 양 surface 라이브 검증 기록 (CHG-20260722T130000)
- Panel skip 사유(§18.8): 코드 0(POST-DEPLOY 실증·TASK 완료). 코드/보안 리뷰 정본 = REV-20260722T122635([SUBAGENT:general-purpose] SHIP-WITH-FIXES, 누출 0).
- 실증(배포본 622b7434): **공유-링크(익명)** pager 메타 1/2·branch_view=1313 읽기전용 전환·999999999 fail-closed. **인앱 그룹(인증)** pager window-scoped·branch_view 전환·active_leaf 불변(읽기전용 확인). 서빙 자산 반영. Windows-browser 시각 스크린샷은 브리지 다운으로 미수행(§15.4.1 escape) — API end-to-end + 단위 12 PASS 로 보완, 시각 확인은 브리지 복구/사용자 브라우저 잔여.

## REV-20260723T010501-doc-sync-rn-0723 [SKIPPED:non-policy-doc] — 릴리즈노트 07-22 블록 신규 6항목(대화 UI 안정화·탐색) (TASK-20260723T010501-doc-sync-rn-0723, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(6항목 전부 owning POST-DEPLOY 커밋으로 라이브 확증; f0a32980 은 브리지 다운 §15.4.1 escape·API e2e+단위 12 보완)·area(work)·누출 회피는 doc_sync 가 정본(각 항목 owning POST-DEPLOY 커밋 + git log cfa647df..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_4ab4d814 — RN 6 INCLUDE holds·feature-0023 등 8 EXCLUDE 사유 정확 confirmed, cross-target cross-fault 회피 스코프).

## REV-20260723T024724-paging-scroll-preserve [SKIPPED:trivial-frontend-ux] — 브랜치 페이징 스크롤 위치 보존 (20260723T024724-paging-scroll-preserve, Minor §12.3)
- Panel skip 사유(§18.8): 순수 프론트 스크롤 UX — `app.js`(loadHistory preserveScroll 옵션·_pageBranch/refreshWorkspace 배선)·`share.js`(window.scrollY 보존). 백엔드·엔드포인트·RBAC·스키마·데이터 0, 보안 표면 없음.
- 자체점검: ① append/일반 로드 경로 무변경(preserveScroll 미지정 시 기존 맨-아래/prepend). ② 1:1 은 refreshWorkspace 유지(사이드바 프리뷰 등 갱신 보존)하고 preserveScroll 만 전달 — behavior 드롭 없음. ③ rAF 복원(layout 확정 후, scroll-restore 규약)·`Math.min(saved,maxTop)` clamp(오버스크롤 방지). ④ 공유 뷰 문서 스크롤도 rAF+clamp. ⑤ 브랜치 대화(has_branches) 페이징에만 preserveScroll — 일반 대화 무영향.
- 검증: `node --check` app.js/share.js PASS · POST-DEPLOY 실브라우저 scrollTop 실측(layout 의존, jsdom 부적합).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260723T024724 · feature-0019 브랜치 페이징(PR#887) 후속 UX.

## REV-20260723T033000-paging-scroll-preserve-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 페이징 스크롤 보존 배포 + 양 surface 라이브 실측 (CHG-20260723T033000)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료). 정본 = REV-20260723T024724-paging-scroll-preserve([SKIPPED:trivial-frontend-ux]).
- 실증(Windows Chrome, 배포본 4ee7ea1d): 인앱 그룹 페이징 scrollTop=0(scrollable maxTop 9538)·스크린샷 육안 상단 pager. 공유-링크 페이징 window.scrollY=0(scrollable maxY 11535). 둘 다 맨-아래 튐 해소(PRESERVED). layout 의존 실브라우저 실측(jsdom 부적합)으로 정본 검증.

## REV-20260723T033143-paging-scroll-longhistory [SKIPPED:trivial-frontend-ux] — 긴 이력 페이징 스크롤 보존 회귀 수정 (20260723T033143-paging-scroll-longhistory, Minor §12.3)
- Panel skip(§18.8): 프론트 렌더창 1줄 로직(preserveScroll 시 renderCount=len). 백엔드·RBAC·스키마 0. 이전 REV(paging-scroll-preserve) 후속 회귀 수정.
- 자체점검: ① 전체 렌더는 preserveScroll(페이징)에만 — append/일반 로드 무변경. ② 형제 버전 분기점-위 이력 동일 → 절대 scrollTop 보존 정확·pager 항상 렌더. ③ 스레드=활성 경로라 크기 bounded(전체 렌더 perf 허용). ④ 공유 뷰(share.js)는 원래 전체 렌더라 무영향(별도 확인).
- 검증: node --check PASS · POST-DEPLOY PB-0008.

## REV-20260723T034500-paging-scroll-longhistory-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 긴 이력 페이징 스크롤 보존 배포+라이브 실측 (CHG-20260723T034500)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료). 정본=REV-20260723T033143-paging-scroll-longhistory.
- 실증(Windows Chrome, 배포본 2cdb7907): '간단한 덧셈 계산' 3→4 페이징 시 전체 렌더(rendered 6)로 pager '4/4' 유지·브랜치 메시지 뷰포트 위치 298px 동일 보존·맨아래 안 튐(maxTop 11286, atBottom=false)·스크린샷 육안. 회귀(pager 소실+스크롤 급변) 해소 확정.

## REV-20260723T034321-conv-date-tree [SUBAGENT:general-purpose] SHIP-WITH-FIXES — 대화목록 날짜 그룹핑 적응형 트리(월/년 집계) (TASK-20260723T034321-conv-date-tree, Major §12.3)
- 적대적 프론트/UX 리뷰(general-purpose, 코드 직접 판독) 6축 점검. 판정: SHIP 아님 → **MAJOR 1건 in-cycle 수정 후 SHIP-WITH-FIXES**.
- **[MAJOR — 수정 완료]** seed × 안정 집계 키의 영속 충돌/파괴: `_seedDateGroupsCollapsedOnce`가 매 로드 최근 그룹 외 전부를 강제 접힘시키는데, 기존 일(日) 키는 매일 바뀌어 무해했으나 `month:`/`year:`는 안정 키라 — ① 사용자가 펼친 6월이 reload 시 재접힘돼 localStorage 와 불일치, ② 이후 무관 그룹 토글 시 `_saveCollapsedGroups`가 in-memory set 전체 저장 → 사용자 영속 펼침 선호를 조용히 collapse 로 덮어씀. **폴더 기능이 이 collapse-영속 모델 위에 세워지므로 근본 수정 필수.** 수정: seed 분리 — 일 단위 키만 로드당 재적용(`_seedDateGroupsCollapsedOnce`가 `_isAggregateGroupKey` 필터), 집계 키는 `_seedAggregateGroupsCollapsedOnce`가 `_seededAggKeys`(신규 localStorage `mad.seededAggGroups.v1`)로 "처음 본 순간 1회만 접힘 seed + 영속" 후 사용자 토글 존중. 결정적 재현 테스트 9/9 PASS(첫 로드 기본 접힘·펼침 영속·reload 강제 재접힘 없음·무관 토글 후 선호 보존).
- **[MINOR — 수정 완료]** 미래 `last_activity_at`(데이터 이상)이 "오늘" 위 정렬/유령 미래 월 노드: `dStart = Math.min(rawStart, today)` clamp 로 미래 날짜를 "오늘" 버킷 합류.
- **[NIT — 수정 완료]** `.conv-date-group-label` inline-flex 하에서 무효였던 `text-overflow: ellipsis`/`overflow`/`white-space`/`min-width` 死코드 제거(라벨 항상 짧음).
- **[NIT — 유지·근거]** 서브 대화 항목(depth1 22px) < 월 서브헤더(24px) 2px: 기존 depth-0 패턴(일 헤더 10px / 항목 8px = 헤더−2px)과 **일관**. 각 depth 에서 항목=헤더−2px 유지가 사이드바 전체 톤과 정합(회귀 아님) + 항목엔 leading dot+gap 이 있어 실제 텍스트는 더 우측. 유지.
- **[NIT — pre-existing·defer]** 날짜 그룹 헤더 키보드 조작 불가(`role=button`+click 만, tabindex/keydown 부재): 기존 owner/date 헤더 전체가 동일 — 이번 diff 신규 결함 아님. 새 집계 노드만 고치면 owner 헤더와 불일치하므로 본 cycle scope 밖. 헤더 전체 a11y 일괄 개선은 후속 항목으로 defer(TODOS 성 기록).
- **[안전 확인]** 키 충돌 없음(top-level 월 노드는 `dY===nowY`·연-자식 월 노드는 else 분기 → `YYYY` 상이로 collapse 상태 공유 불가) · 집계 정확(Map 키 병합 단일 노드·"6월 중복" 소멸) · 리스너 누수 없음(`innerHTML=""` 전체 초기화) · 배지 계산 정확(branch=자식 items 합·leaf=items.length) · 월/연 경계 timestamp 산술로 정확 · 파싱불가→__other__·dangling ref 0 · folder-readiness 재귀 모델 재사용 가능.

## REV-20260723T130200-conv-date-tree-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 대화목록 날짜 그룹핑 적응형 트리 배포 + 라이브 시각검증 (CHG-20260723T130200-conv-date-tree-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T034321-conv-date-tree([SUBAGENT:general-purpose] SHIP-WITH-FIXES).
- 실증(Windows Chrome 150, 배포본 0b15a0ea): 배포본 `_buildOwnDateTree` 합성 6/6 + 실계정 사이드바 단일 "6월"[38]·"5월"[15]·중복 라벨 0(이전 ~10개 소멸) + 6월 토글 4→42(배지 정확) + 스크린샷·pageerror 0. 중복 "6월" 혼잡 해소·월/연 집계·연>월 중첩·개수 배지·토글 라이브 확정.
## REV-20260723T071355-universal-ctxmenu [SUBAGENT:general-purpose] SHIP — 서비스 UI 우클릭 = 보편 확장 메뉴 단축 (TASK-20260723T071355-universal-ctxmenu, Major §12.3)
- 적대적 프론트/UX 리뷰(general-purpose, 코드+diff 직접 판독) 8축 점검. 판정: **SHIP** (BLOCKING/MAJOR 0). 검증 통과: 앵커 수명(`_floatingMenuAnchorPoint` 를 synchronous `dispatchEvent` 로 openFloatingMenu 가 소비·finally 방어 해제 → left-click 누출 경로 없음) · anchor=null 3항 ternary 가 원본 표현으로 환원(byte-동치, (0,0) 우클릭도 truthy 유지) · synthetic click 무-사이드이펙트(우클릭=button2 는 native click 미발화 + 트리거 stopPropagation → 대화 선택/폴더 토글 안 됨) · no-trigger/pending·disabled 항목 graceful 폴백(native 우클릭) · 예외 가드(closest/nodeType/querySelector/MouseEvent) · 단일-fire(호스트 disjoint DOM·첫 매치 return·리스너 1회 등록).
- **[MINOR ×3 — in-cycle 수정 완료]** ① 미디어(img/svg/canvas/video)·assistant 답변 mermaid SVG/이미지 우클릭이 ☰ 로 가로채져 "이미지 저장/링크 열기" native 손실 → 양보 selector 에 `img,svg,canvas,video` 추가. ② 키보드 contextmenu(Menu키/Shift+F10, 일부 브라우저 clientX/Y=0)가 좌상단 오배치 → `fromKeyboard`(coords≤0) 시 anchor=null trigger-rect 폴백. ③ `_hasSelectionWithin` 의 commonAncestor-wrap 분기가 stale 교차-메시지 선택 시 무관 호스트 우클릭 과잉차단 → `Range.intersectsNode`(실제 겹침만·구형 브라우저 containment 폴백)로 교체.
- **[NIT ×2 — 무해 유지]** 우클릭 토글 비대칭(호스트 body 우클릭은 mousedown-close→contextmenu-reopen 재배치 / 트리거 정확 우클릭만 toggle-close) · synthetic click 이 focus 미이동(aria-expanded 정합·ESC focus 복원 동작) — 컨텍스트 메뉴 관례상 무해.
- 검증: `node --check app.js` PASS(리뷰 반영 후) · CHECK#13 POST-DEPLOY PB-0008 (TEST fragment 20260723T071355-universal-ctxmenu, AC-1~5).

## REV-20260723T075215-universal-ctxmenu-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 서비스 UI 우클릭 보편 확장 메뉴 배포 + 라이브 실측 (CHG-20260723T075215-universal-ctxmenu-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T071355-universal-ctxmenu([SUBAGENT:general-purpose] SHIP).
- 실증(win-browser Chrome 150, 배포본 c6f7f98a, https://localhost/): 서빙 app.js(stamp e6d39fde416f) 신규 심볼 5종 전부 hit + 실 contextmenu(button2) dispatch — AC-1 대화항목→'···' 커서(226,68)·AC-2 폴더헤더→폴더메뉴(168,48)·AC-3 말풍선→'☰' 커서(191,588)·AC-4 텍스트 663자 선택 후 우클릭 defaultPrevented=false native 보존·☰ 미개방·AC-5 버튼 클릭 menuRight==trigRight byte-동치·errCount 0. 우클릭=보편 확장 단축·기본 우클릭 양보·버튼 경로 무회귀 라이브 확정.

## REV-20260723T080415-floating-menu-close-fix [SUBAGENT:general-purpose] SHIP — floating 메뉴 닫힘 결함 수정(folderMenu 1급 승격) (TASK-20260723T080415-floating-menu-close-fix, Minor §12.3)
- 신고: universal-ctxmenu 후속 사용자 — 폴더 '···' 메뉴가 열린 뒤 바깥클릭/ESC 로 안 닫힘. 근본원인 = `closeFloatingMenus` 의 하드코딩 id 목록에 `folderMenu`(feature-0024) 누락(pre-existing drift, 우클릭 기능이 표면화).
- 적대적 프론트 리뷰(general-purpose, 코드+diff 판독) 6축(over/under-removal·dataset copy order·toggle/identity·trigger reset·broader callers). 판정: **SHIP** (BLOCKING/MAJOR 0). 검증 통과: `data-floating-menu` 는 openFloatingMenu 단일 지점에서만 set·closeFloatingMenus 단일 지점에서만 read(3개 메뉴 전부 이 primitive 경유 — over/under-removal 없음) · 마커 write 가 caller dataset copy 보다 선행하고 caller 키(folderId/conversationId/messageId)와 비충돌·역방향 leak 없음 · getElementById(id) 기반 toggle/identity 불변 · `.conv-folder-menu-trigger.is-open` 이 실제 부여 클래스와 정합(오히려 stale is-open/aria 영구잔존을 신규 복구).
- **[NIT ×3 — 리뷰 지적, folderMenu 1급 승격 정합으로 in-cycle fold-in]** ① `_attachShareRangeEsc`(8383) 열린-메뉴 가드에 folderMenu 미포함 → 공유범위 arm 중 폴더 메뉴 열고 ESC 시 공유범위까지 취소 → 가드에 folderMenu 추가. ② `_maybeSyncConversationListUnread`(11662) 7s 재렌더 skip 가드가 convItemMenu 만 → 폴더 메뉴 열림 중 재렌더로 트리거 detach(수정 후엔 body-mount 메뉴라 닫힘엔 무해하나 정합) → folderMenu 포함. ③ `styles.css` `.conv-folder-menu-trigger.is-open` keep-visible 규칙 부재 → 열림 중 포인터 이탈 시 '···' 페이드 → conv-item/말풍선과 동형으로 `opacity:1` 추가.
- 검증: `node --check app.js` PASS · CSS 균형 · POST-DEPLOY PB-0008(AC-1~5 폴더 메뉴 바깥클릭/ESC/scroll/토글 닫힘·무회귀). TEST fragment 20260723T080415-floating-menu-close-fix.

## REV-20260723T081500-floating-menu-close-fix-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — floating 메뉴 닫힘 결함 수정 배포 + 라이브 실측 (CHG-20260723T081500-floating-menu-close-fix-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T080415-floating-menu-close-fix([SUBAGENT:general-purpose] SHIP).
- 실증(win-browser Chrome 150, 배포본 57ecc758, https://localhost/): 서빙 app.js(stamp 8373a9f479e2) `data-floating-menu` 2 hit·css `.conv-folder-menu-trigger.is-open` 1 hit + 테스트 폴더(API 생성 id=6, 검증 후 삭제) 실 이벤트 — AC-1 바깥클릭·AC-2 ESC·AC-3 scroll·AC-4 토글 닫힘(+트리거 aria=false·is-open 제거)·AC-5 conv-item 무회귀·errCount 0. 폴더 '···' 메뉴가 정상 닫히고 트리거 상태 복원·타 메뉴 무회귀 라이브 확정 — 사용자 신고 결함 해소.
## REV-20260723T074530-reasoning-timeline [SUBAGENT:general-purpose] SHIP-WITH-FIXES — AI 운영 현황 > 추론 결함수정 전/후·답변개선 과정 가시화 (TASK-20260723T074530-reasoning-timeline, Major §12.3) — panel: frontend-ux-security + backend-qa
- Trigger: UI/화면·레이아웃 keyword matched → ux/design; API/endpoint·response shape keyword matched → backend/qa (§18.8). 적대 general-purpose 2명(프론트/UX/보안, 백엔드/QA) 병렬. 접근 A(기존 `redteam_reviews` 데이터 재구성 — 마이그레이션·계측·답변원문 저장 없음, AskUserQuestion 승인).
- **백엔드/QA panel — 결함 없음(6축 CLEAN)**: 컬럼 인덱스 r[14..16] 정합(0042 base 14 + 0043 3, writer INSERT 순서 일치)·stale-image `information_schema` 폴백·`_pg_connect_ro` autocommit 이라 감지 쿼리 실패가 트랜잭션 abort 안 함(이후 `_query_reviews` 재사용 안전)·회귀0(base 필드 byte-보존, cols 단일 계산으로 cursor/non-cursor 양 경로 정합)·응답계약(rederive 3필드 unconditional 세팅으로 error/폴백 경로도 KeyError 없음)·SQL injection 표면 0(cols=리터럴+bool 게이트, `%s` 바인딩).
  - **[hardening — 반영]** `include_rederive` default `True`→`False`(fail-safe): 유일 caller 가 `_has_rederive` 명시 전달하므로 동작 불변, 미래 caller 가 kwarg 생략해도 stale 이미지에서 UndefinedColumn 안 남.
  - [관찰 defer] 단위테스트 갭(include_rederive 분기·information_schema 감지는 라이브 PG 필요 → POST-DEPLOY 커버) · 기존 rollback 주석 cosmetic(autocommit no-op, 본 cycle 신규 아님·scope 밖).
- **프론트/UX/보안 panel — SHIP 아님 → BLOCK 1 + WARN 2 in-cycle 수정 후 SHIP-WITH-FIXES**. XSS(속성 보간 `esc` 적용·`href` encodeURIComponent·백엔드 axis/severity write sanitize 이중방어)·degrade(findings 비배열·필드 누락·rederive null 전 가드)·접근성(ol/li·aria-hidden·target/rel)·CSS(콘솔 LIGHT-ONLY 확인, 고정 hex 항상 흰 배경 대비 양호·클래스 충돌 0)·회귀(페이징/통계/노트 esc 체인 보존)·딥링크(기존 규약)는 CLEAN.
  - **[BLOCK — 수정 완료] B1** verdict=pass + WARN-only(BLOCK 0)를 단계③에서 "수정 실패·fail-open"으로 오표기 → 상단 "정상 통과"(초록) 배지와 정면 모순(운영자 "하자 초안 그대로 전달" 오독). RC = `hasDefect = verdict==='revise' || nBlock>0 || nWarn>0` 가 WARN 을 결함 취급. 백엔드 verdict 규약(`redteam.py`: BLOCK→revise, WARN-only→pass 자문 신호·수정 대상 아님) 반영: `hasBlock=(verdict==='revise'||nBlock>0)` 로 게이트, `warnOnly` 는 ②"통과 — 경고(자문) N건, 수정 불필요"·③"불필요 (경고성 자문 — 수정 대상 아님)"(na). 미해결 BLOCK(revise·revision_applied=false)만 ③"미적용(수정 실패, fail-open)". harness c7(WARN-only)·c8(미해결 BLOCK) 회귀 케이스 추가 PASS.
  - **[WARN — 수정 완료] W2** 축 집계가 "더 보기" 페이징 후 미갱신 → "현재 목록 N건" 라벨이 거짓(첫 페이지 값 고정). `adminState.reasoning.reviewsAll` 누적 + 페이징마다 `_reasoningAxisSummary` 재계산해 `#reasoningAxisSummaryWrap` 교체.
  - **[WARN — 수정 완료] W4** 단계② "결함 N건" 카운트를 findings severity 에서 일원화(파싱 실패 시만 block_count/warn_count 컬럼 폴백) → 손상 데이터에서 컬럼과의 내부 모순("0건 검출 (BLOCK X)") 방지.
  - **[WARN — 동기화 처리] W3** worktree base stale(cycle-init 시 main=e52e88fc, 이후 universal-ctxmenu PR #897 전진) → `git diff main` 에 무관 app.js 삭제가 stale 아티팩트. 랜딩 전 `git rebase origin/main` + app.js 무변경 확인(아래 Git 동기화 결과).
  - [NIT defer] 모든 링크 동일 문구 "대화 열기 ↗"(WCAG 2.4.4 문맥, 경미) — 후속.
- 재검증: 실제 소스 추출 harness **21/21 PASS**(5단계·rederive·강도 한글화·전후 대비·5축·재검증·pass/error·B1 c7·c8·sentinel·축 집계·XSS·null 안전) · `node --check`(ESM) · `py_compile`.
- 판단: additive read-only API + frontend 표시 재구성. 인증/인가/파괴적/스키마/RBAC/엔드포인트 무변경 → Critical 아님(Major). POST-DEPLOY PB-0008(Environment: Windows-browser, hard gate) 예정.

## REV-20260723T084235-reasoning-timeline-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — AI 운영 현황 > 추론 배포 + 라이브 시각검증 (CHG-20260723T084235-reasoning-timeline-postverify)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료 기록). 정본 = REV-20260723T074530-reasoning-timeline([SUBAGENT:general-purpose] SHIP-WITH-FIXES).
- 실증(Windows Chrome 150, 라이브 e4ef9384): 추론 탭 리뷰 30건 — 진행 타임라인 5단계(stages 150)·전후 대비 47·5축 집계(근거15/SQL6/완전성12/정직성14)·rederive "도구 재추론(SQL)"·대화 딥링크 30·통계 타일 6·pageerror 0. **W2 페이징 축 재계산 47→93** 확증. **B1** verdict pass 카드 "결함 없음—통과" 실렌더(WARN-only 오표기 없음). AC-1~6 라이브 확정.

## REV-20260724T010501-doc-sync-rn-0724 [SKIPPED:non-policy-doc] — 릴리즈노트 07-23 블록 신규 7항목(대화 폴더·탐색·관리 콘솔) (TASK-20260724T010501-doc-sync-rn-0724, 비-정책 doc-only)
- Panel skip 사유(§18.8): 변경은 사용자 노출 릴리즈노트 콘텐츠 데이터(`static/release-notes-data.js`)뿐 — 비-정책 doc-only. 렌더 로직·백엔드·스키마·RBAC·엔드포인트·cache-buster(빌드 자동주입) 0 → 코드 적대 검증 대상 아님(§18.8 표 첫 행 `[SKIPPED:non-policy-doc]`). 콘텐츠 정합·평이화·과대표현·완료형 정당성(7항목 전부 owning POST-DEPLOY 커밋으로 라이브 확증 — 폴더 9392cf51/e3fec503/0a1378f3/1a2f2595·날짜트리 8b384b8a·우클릭 b51f93e9·페이징 fce9ab2b/5d0f8467·추론타임라인 a17fd1a7·DB분석 6da5e621)·area(work 5·admin 2)·누출 회피는 doc_sync 가 정본(owning POST-DEPLOY 커밋 + git log aac76889..HEAD) 대비 직접 검증 + ULTRACODE 타깃별 적대 verify(wf_ded08a66 — RN major 1[graph-node-reveal 자체 POST-DEPLOY PB-0008 미기록 → 사용자 릴리즈노트 hold, 함정 #15] 반영·나머지 INCLUDE holds, cross-target cross-fault 회피 스코프).

## REV-20260724T012954-usage-model-canonical [SUBAGENT:general-purpose] SHIP (MINOR §12.3) — LLM 사용량 '모델별 비중' canonical 집계
- 위험도(§12.3): **Minor** — 읽기전용 분석/표시 집계 + 추정비용 정확화. 인증·인가·파괴적 데이터·마이그레이션·
  외부 비용 구조 변경 없음. admin.js(프론트)·스키마·엔드포인트 계약 무변경. AI 자율 진행 + 본 기록(§12.3).
- 근거(원인): `by_model` 등 사용량 집계가 `COALESCE(resolved_model, model)` 를 그대로 GROUP BY 해, litellm
  라우팅 변형 alias·실 모델 ID·gemma 폴백 실모델이 별도 세그먼트가 되어 한 논리 모델이 도넛을 분점.
  litellm_config.yaml 상 `claude-haiku-4*` 6개 alias 는 모두 anthropic/claude-haiku-4-5 로 라우팅됨을 확인.
- 결정: canonical family 를 SSOT(`shared/model_catalog.py`)에 두고 SQL/Python 양측이 동일 규칙 사용. 실
  서빙 모델 기준(COALESCE(resolved, model))을 유지(TASK-0163 의도 보존)하되 family 로 접음 = "실제 사용량".
- 대안 검토:
  1. 프론트(admin.js) JS 집계 — 기각: 백엔드 by_model/by_day_model/by_account 4곳 + 드릴다운 필터가 백엔드라
     프론트만으론 불완전, 색맵/칩/필터 전면 재작성 필요. 백엔드 canonical 이 프론트 무변경으로 정합.
  2. Python fold(SQL 은 raw 유지) — 기각: run_id distinct 가 canonical 그룹 횡단 시 과대계상, 드릴다운 필터가
     canonical↔raw 매핑 역질의 필요. SQL CASE(starts_with) 그룹핑이 run_id dedup·필터를 한 번에 정합 해결.
  3. LIKE 'x%' — 기각: 파라미터 쿼리(`_query_usage_conversations`)에서 '%' 이스케이프(%%) 필요, no-param
     쿼리와 이스케이프 불일치 footgun. PG `starts_with()` 로 '%' 자체를 제거해 양쪽 안전.
- 리스크/완화: (a) 실 서빙 모델 기준이라 gemma 폴백(haiku 요청→gemma 서빙)은 edge 로 계상 — TASK-0163 의
  기존 규약(resolved 우선)과 정합, 오히려 haiku 단가 과대계상 정정. (b) 미등록/신규 모델은 원본 유지(self-surface)
  로 조용히 사라지지 않음. (c) 프론트 드릴다운 클릭 키(canonical) ↔ 백엔드 필터(canonical) 정합을 test_c4·
  test_q2 로 회귀 가드. profile 도넛도 동일 canonical 화하여 공유 헬퍼(`_query_usage_conversations`) 필터
  변경으로 인한 profile 드릴다운 미매칭 회귀를 예방.
- 검증: 전체 pytest 2280 passed/2 skipped(baseline), 신규 test_c1~c4 + test_q2_model_filter 갱신. 실 PG(90일)
  실측 — 7 세그먼트 → 3 실제 모델(haiku 64.5M·edge 30.4M·sonnet 0.79M) 병합 확인. POST-DEPLOY PB-0008 예정.
- 완료 정합: 코드 변경은 백엔드 .py 만(html/templates/static 무변경) → §10.5 web/UI 트리거(check #13)
  하드 게이트 대상 아님. 다만 산출물이 렌더 도넛이므로 배포 후 라이브 시각검증(PB-0008)을 완료 근거로 첨부.
- Panel(§18.8): backend/qa/correctness 축 [SUBAGENT:general-purpose] 적대 리뷰 수행(diff + 실 소스 + 프론트
  admin.js 호환 + PG 버전 + canonical Python 런타임 실행 + 생성 SQL 문자열 실측). **Verdict: SHIP** —
  BLOCKING/MAJOR 0. 확인: 리터럴 `%` 0개(starts_with)로 param/no-param 쿼리 이스케이프 안전 · GROUP BY=SELECT
  동일 `_canon` 문자열/ordinal · ORDER BY pos 4→3 정정(model 컬럼 제거 shift) · **단가표 키가 canonical family
  키와 정확 일치**(실ID 형태였다면 전부 $0 되는 BLOCKING 이었을 지점 — 안전 확증) · 컬럼 인덱스 r[0..5] 정합 ·
  `_canon` 스코프 정의-후-사용 보장 · 프론트 라운드트립(도넛 라벨=canonical → 클릭 → 백엔드 canonical 필터 매칭) ·
  run_id canonical 그룹 dedup(과대계상 없음, 오히려 완화) · profile 드릴다운 미스매치 회귀 없음.
- Findings fold-in (전부 의도된 동작/ pre-existing — 코드 수정 불요):
  · [MINOR] 사용량 상세표의 "alias → resolved" 화살표는 model==resolved_model 이라 미렌더 — canonical 통일의
    의도된 결과(패널이 "실제 모델 기준"으로 전환). req→resolved 추적은 AI 운영 관제 activity 피드(ai_ops)가 보존.
  · [MINOR·pre-existing] 'edge' 세그먼트 드릴다운은 `conversation_id IS NOT NULL` 강제라 비대화 insight/worker
    usage 가 빈/부분 결과일 수 있음(도넛=전체 vs 드릴=대화귀속분 의미차, canonical 이 edge 를 단일 큰 세그먼트로
    합쳐 더 두드러짐). 코드 결함 아님 — 정직한 표현.
  · [NIT·범위 밖] `ai_ops.py:319` task×model 은 raw GROUP BY 유지(운영 관제 activity 패널). category 롤업이라
    raw granularity 미노출·per-category 비용은 canonical 단가 계상 → 가시 불일치 없음. follow-up(§8.1) 기록.
  · [NIT] SQL(ELSE NULL/'') vs Python('(미상)') 빈값 divergence — model NOT NULL + COALESCE 로 도달 불가(주석 명시).

## REV-20260724T020632-aiops-model-canonical [SUBAGENT:general-purpose] SHIP-WITH-FIXES (MINOR §12.3) — '운영 현황' 서브탭 모델 canonical 정합 (usage-model-canonical 후속)
- 위험도(§12.3): Minor — 읽기전용 표시/집계 정합. 인증·인가·데이터·마이그레이션·계약 변경 없음.
- 범위: 사용자 요청("나머지 범위 또한 실제값과 정합"). 직전 PR#914 가 남긴 유일 raw 모델 그룹핑 = ai_ops('운영 현황').
- 변경: (1) categories 집계 canonical GROUP BY, (2) 활동 feed 주 배지 canonical(req/resolved raw 보존).
- **적대 리뷰(general-purpose) verdict = SHIP-WITH-FIXES → 지적 3건 전부 반영 후 SHIP**:
  · **M1 (MAJOR, 반영)**: `admin.js:2208` 상세 폴백 `srvM = r.resolved_model || r.model` 이 이번에 canonical 화된
    `r.model` 을 끌어와, `resolved_model=NULL` + 비-canonical `req_model`(예 `auto`·보조 task/pre-migration 행)에서
    상세에 **날조된 라우팅 화살표(`auto → edge`)** 를 생성(cycle 의 "상세=raw audit·손실 없음" 계약 위반 — 손실
    아닌 날조). **수정**: `srvM = r.resolved_model || r.req_model` (canonical `r.model` 미참조 → 상세 100% raw).
    resolved NULL 이면 srvM=reqM → 화살표 소거(변경 전 동작 복원), resolved 존재 시 실 라우팅 유지. **실 Windows
    Chrome(win-browser eval) 4시나리오 확증**: 정상변형·gemma폴백=실화살표 / NULL+auto=`auto`(날조 없음) / NULL+haiku=단일.
  · **m1 (MINOR, 반영)**: categories "출력 불변/byte-동일" 주장 정정 — calls/total_tokens 는 정수 sum 이라 완전
    불변이나, cost 는 `_estimate` 가 호출마다 round(…,4) 하여 raw 다중그룹→canonical 단일그룹 재결합 시 최하위
    4번째 소수(≈$0.0001)에서 미세 변동 가능(단일 round 라 오히려 더 정확). ai_ops.py 주석 + 문서 톤다운.
  · **m2 (MINOR, 반영)**: NULL-resolved+비canonical req 케이스 백엔드 회귀 테스트 추가
    (test_query_activity_null_resolved_badge_canonical_raw_preserved) — 배지=canonical('edge'), req=raw'auto',
    resolved=None 유지. unknown passthrough 는 기존 test_c2(merged)로 커버.
- 리뷰 통과 항목: SQL `GROUP BY task,2` ordinal=CASE 정합·starts_with %-이스케이프 안전 / SSOT(Python↔SQL 규칙
  동일) / 비용 일관(배지 canonical ↔ _estimate 내부 canonical) / 정보 복구(resolved 존재 시 라우팅 완전 표시) /
  두 엔드포인트(/ai-ops·/ai-ops/activity) 배지 일관 · categories try/except degrade 온전.
- 검증: 전체 pytest 2287 passed/2 skipped · admin.js `node --check` · Windows-browser modelDetail eval PASS ·
  POST-DEPLOY PB-0008(운영 현황 배지·활동 상세 라우팅 라이브) = 배포 후 후속(test-runs.d fragment).
## REV-20260724T181106-brandnew-script-attachment [AGENT-TEAM: security+backend] SHIP-WITH-FIXES — §18.8 Verification Panel
- **Trigger**: 새 첨부 쓰기 경로(INSERT WebConversationAttachments) + 프롬프트 변경 → dispatch 키워드 `schema/query`(→backend+qa) + 새 write/RBAC 표면(→security); 프롬프트 변경=full-panel default. 렌즈: security, backend correctness.
- **[AGENT-TEAM: security] MAJOR(반영)**: 신규 source-less 경로가 `conversation.attachment.upload.own/any` 권한 미검사 → `conversation.ask`만 가진 주체(또는 그 scope API 토큰)가 첨부 업로드를 우회 생성(편집 경로는 source 소유권으로 간접 게이팅). **Fix**: `_materialize_assistant_attachment_new` 최상단 `_account_can_access_conversation` 업로드 권한 게이트(권한 없으면 skip, 수동 업로드 엔드포인트와 동일). / **검증-SAFE(REFUTED)**: 확장자 allowlist·이중확장자(x.exe.sql→x_exe.sql)·경로traversal·leading-dot·IDOR(account/conv 서버바인딩)·SQL injection(parametrized)·크기/개수 캡·kind/MIME(비클라이언트)·strip parity 전부 방어 확인.
- **[AGENT-TEAM: backend] MINOR(반영)**: (1) 프론트 배지 v1 신규를 "AI 수정"으로 오표기 → "AI 생성"/"AI 수정" 구분(app.js). (2) turn당 개수 cap 편집+신규 이중카운팅(실질 10) → 공유 예산(remaining_count) 합산 ≤5. (3) span 파서 리팩터: 한 블록 본문에 상대 태그 fence-start 줄 포함 시 조기종료(실트리거 ≈0 for SQL/CSV) → 코멘트 정직화 + 회귀 테스트(test_p6)로 동작 고정(더 흔한 공존 케이스 보존 트레이드오프). / **검증-SAFE(REFUTED)**: root INSERT(RootAttachmentId=NULL·v1·UNIQUE NULL-distinct)·history 칩 렌더(message_id display-space 정합)·fail-open·step_index(편집 뒤 +1 충돌無)·mirror/audit 시그니처 전부 확인.
- **판정**: SHIP-WITH-FIXES → 전 findings in-cycle 반영. 보안 회귀 0(가드 불변 + 업로드 권한 게이트 추가). 잔여 라이브 실측=POST-DEPLOY PB-0008(동일입력 재현으로 거부 소멸 확인).
## REV-20260724T180649-share-point-rail-bars [SKIPPED:trivial-display-only-port-of-reviewed-main] — 공유링크 뷰 rail 막대화 + 클릭 비례 (Minor §12.3 — feature-0003 web/UI, /_template:entry 후속)
- Panel skip 사유(§18.8): 메인 뷰 A(막대화)+B(클릭 위치 비례)를 공유 뷰(share.js/share.css)에 **동형 이식** — 원본은 REV-20260722T125200-point-rail-range-window([SUBAGENT:general-purpose]) 적대리뷰 + 라이브 PB-0008 PASS 완료분. 차이는 좌표계뿐(messageLog 내부 스크롤 → window/문서 스크롤): `layoutSharePointRail` topInDoc=rect.top+scrollY·totalHeight=documentElement.scrollHeight·`scrollShareMessageToRatio` window.scrollTo. 백엔드·엔드포인트·RBAC·스키마 0, 순수 표시+간단 인터랙션. anonymous 노출면이나 dot.title/aria-label 은 기존 DOM API(innerHTML 아님) 유지 — XSS 무첨가.
- `scrollShareMessageIntoCenter`(항상 중앙) 는 제거하지 않고 유지(향후 재사용·메인 대칭). 윈도잉(C)은 공유 뷰 범위 밖(read-only 스냅샷·페이징 없음) — 미적용.
## REV-20260724T085937-sonnet-reasoning-budget-guide [SUBAGENT:adversarial-general-purpose] SHIP-WITH-FIXES — '모델별 추론 예산' adaptive(Sonnet 5) 죽은 budget 슬라이더 제거 + guide-note (CHG-20260724T085937, Minor §12.3, cross-feature 정본 feature-0003+shared)
- Trigger(§18.8): shared/runtime_settings.py(spec 생성 필터) + admin UI(사용자 대면) 변경 → 적대 리뷰 1렌즈(general-purpose, 6 공격각 A~F). 판정 **SHIP-WITH-FIXES** — BLOCKER/MAJOR 0.
- **Finding D (MINOR-latent) 반영·수정**: `_budget_thinking_models()` 필터가 `!= "adaptive"` 였는데, 이는 style=None 미상/미래 claude(예: claude-opus-4-8; model_catalog 가 미상 claude 를 안전하게 None 분류)를 budget 스펙에 **포함** → agent_core `_call_llm` 이 None 스타일엔 budget_tokens 를 주입 안 하므로 **똑같은 죽은 슬라이더가 재발**(게다가 `_adaptive_thinking_models` 는 `== "adaptive"` 라 guide-note 도 없음). **수정**: 필터를 `== "budget"`(agent_core budget 분기와 동형)로 변경 → budget 계열만 ②③ 노출, 미상 claude 는 ①(총 출력 live)만·죽은 컨트롤 0. 현 카탈로그(sonnet=adaptive/haiku=budget)에선 결과 동일(haiku-only)이라 무회귀, 미래 재발만 봉인.
- **Finding A/B (MINOR-inert) 수용**: 변경 전 저장됐을 수 있는 sonnet budget override DB 행은 이제 orphan — but 완전 inert(‌`validate_value`→spec None 로 override 로드에서 제외·`serialize_registry` 는 list_specs 만 순회·override resolver 는 spec None 단락 → 누출/크래시 0, 리뷰 A/B 확증). 잔여 wart: DELETE 가 미등록 키 400 이라 UI 로 리셋 불가(UI 는 guide-note 라 reset 버튼 자체 없음)하나 inert 하므로 수용(정리 마이그레이션 불요 — 필요 시 운영자 직접 DB 삭제). REPORT/MODIFY 기록.
- 공격각 CLEAN: A(PUT/validate — 제거 키 400, 테스트 커버), C(프론트 — `adaptive_models` Array 가드·textContent XSS-safe·① 유지·중복렌더 없음), C2(빈 sliderRows forEach no-op), E(테스트 non-vacuous — len==3·sonnet not in·haiku live 20000·clamp 62976/default 5000 실측 일치), F(agent_max_output:claude-sonnet-4 spec·`_call_llm` max_tokens 계약 보존).
- 검증: 수정 후 feature-0002 test_runtime_settings 39/39 + feature-0003 test_runtime_settings_api RC=0. POST-DEPLOY PB-0008(sonnet 카드 guide-note·haiku 슬라이더) 예정.
- Cross-ref: CHG/TASK/TEST-20260724T085937-sonnet-reasoning-budget-guide · shared/feature-0002 MODIFY 동일 slug · subagent id a77c815ebdf2d791f · ANCHOR 0003 무충돌.

## REV-20260724T183000-share-point-rail-bars-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — POST-DEPLOY 공유링크 라이브 검증 기록
- Panel skip 사유(§18.8): 코드 0(문서 전용 POST-DEPLOY 실증). 구현 리뷰 정본 = REV-20260724T180649-share-point-rail-bars([SKIPPED:trivial-display-only-port-of-reviewed-main]). 배포(c1358190)+공유링크 라이브 실측(막대·클릭 비례) append 만.
## REV-20260724T180458-sql-md-highlight [SUBAGENT: SHIP — 6/6축 PASS · BLOCK/MAJOR 0 · 보안·정합성 결함 0] assistant markdown SQL 코드블록 구문 하이라이트 (Minor §12.3, frontend-only)
- **[SUBAGENT] 적대 패널 판정 (§18.8, 보안+프론트 렌즈, 정적분석 + 경험적 테스트 — jsdom 주입 열거 + node ReDoS 1.12M자)**: **VERDICT SHIP**. ① XSS PASS — 토큰 텍스트 `textContent`/`createTextNode` 전용, `tpl.innerHTML` 직렬화가 `<>&` 엔티티 이스케이프 → 주입 payload(`'<img onerror>'`·`</code></pre><script>`·백틱-`</span><script>`·`'"><iframe srcdoc>`) 전부 PRE/CODE/SPAN + `class="sql-tok-*"` 로만 물질화, 금지 태그/속성 0; span class 는 하드코딩 상수(포징 불가); DOMPurify 최종 backstop 유지. ② ReDoS/토크나이저 PASS — unrolled-loop 문자열 패턴(선형)·lazy 블록주석·zero-width 매치 없음(전 분기 ≥1자 소비 + `[\s\S]` fallback)·200k~1.12M자 입력 0.4~64ms 선형·무한루프 없음·미종결 문자열/주석 graceful. ③ 회귀/disjoint PASS — lang 게이트 early-return 로 diff/mermaid/attachment/인라인/plain 무영향, `[class*='language-']` 오탐 없음(`(?:^|\s)language-` 경계), 체인 순서 양파일 정합. ④ 텍스트 무손실 PASS — 전 테스트 100% round-trip(스크립트/`&<>"`/비ASCII/CRLF/탭/이스케이프따옴표/`.5`/`1e`), 트레일링 `\n` strip 은 enhanceDiffBlocks 관례와 동일. ⑤ app.js↔share.js PASS — 마스터 정규식 byte-identical, 함수/Set 동치(차이=app.js 한국어 주석 3줄뿐). ⑥ CSS PASS — 토큰 규칙 `pre.sql-block .sql-tok-*` 이중 조건이라 non-SQL bleed 없음, 사용자 말풍선 override specificity 정합.
- **잔여(수정 안 함 — 코스메틱·text-safe)**: NIT — comment 토큰 `#737aa2`/`#1a1b26` 대비 ≈4.1:1(기존 `.diff-meta` 와 동일 페어 재사용, 의도적 de-emphasis). MINOR(coverage 한계, 결함 아님) — PostgreSQL `$$…$$` dollar-quoted·MySQL `#` 라인주석 미토큰화 시 내부가 일반 SQL 로 색칠될 수 있음(텍스트·안전 무영향, 순수 오색칠). `#` 는 코드 주석에 이미 명시, `$$` 는 향후 확장 여지.
- **결정**: 외부 syntax highlighter 라이브러리(highlight.js/prism) 도입 대신, 기존 `enhanceDiffBlocks`/`enhanceAttachmentEditBlocks` 와 동일한 code-block post-processor 패턴의 경량 토크나이저 `enhanceSqlBlocks` 를 추가한다.
- **대안 검토**:
  - (A) highlight.js/prism vendor 추가 → 번들 크기(+수십~수백KB)·CSP/오프라인 정합·theme CSS 추가 부담·과잉. 서비스가 쓰는 SQL 방언(MySQL/T-SQL/PG) 한정이면 경량 커스텀으로 충분. **불채택**.
  - (B) marked 커스텀 renderer 로 코드 하이라이트 → marked 버전/renderer API 결합 증가, 기존 enhance 체인과 이질. **불채택**.
  - (C) **경량 토크나이저 post-processor(채택)** — 기존 패턴 정합, 의존성 0, 방언 공통 예약어/타입 세트 + `(`휴리스틱 함수 인식. app.js/share.js 로컬 복제는 diff/attachment 선례와 동일.
- **리스크·완화**:
  - XSS: 토큰 텍스트를 `textContent` 로만 span 에 주입(innerHTML 미사용) + 체인 말미 DOMPurify.sanitize 이중 방어. headless 라이브 DOM 실측으로 `<script>/<img>/on*` 0·alert 미발화 확증.
  - ReDoS: 문자열/백틱 토큰을 linear(비-backtrack) 형태(`'[^']*(?:''[^']*)*'`)로, 블록주석은 lazy 로 작성.
  - 방언 충돌: MySQL `#` 라인주석은 T-SQL `#temp` 식별자와 충돌하므로 미지원(`--`,`/* */` 만) — 색만 안 입고 깨지지 않음(무손실).
  - 회귀: lang 필터로 diff/mermaid/attachment/비-SQL/인라인 코드와 disjoint 확인(headless 23/23).
- **테마**: `.message-content pre` 는 라이트/다크 무관 항상 다크(#1a1b26 / share #1e293b)라 diff-block 과 동일 Tokyo Night 팔레트를 재사용, 테마 분기 불필요. 사용자 말풍선(primary 색 위)에 sql 블록이 실릴 경우만 배경을 다크로 고정해 대비 보장.
- **검증**: headless chromium 실 vendor 파이프라인 23/23 PASS · node --check PASS · 시각증거 캡처. POST-DEPLOY PB-0008 라이브(Windows-browser) = 배포 후 정본.

## REV-20260724T184500-sql-md-highlight-postverify [SKIPPED:non-policy-doc] SQL 하이라이트 POST-DEPLOY 라이브 실증 + deploy_scope 근거 기록
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록). 실 구현 리뷰 정본 = REV-20260724T180458-sql-md-highlight([SUBAGENT] 6/6축 SHIP·BLOCK/MAJOR 0). 본 cycle 은 배포(0313b135) 라이브 실측 + §12.2 배포 근거 기록만.
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 cycle-final(PR #946 머지, main 0313b135) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. 첫 배포 직전 "deploy_scope: included 활성" 1줄 표면화 완료. 배포=web-a/web-b one-at-a-time 롤링·90s soak 통과·caddy no-drift·롤백 0.
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: 실 Windows Chrome/150 배포본 `markdownToHtml` eval → sql-tok 26토큰·getComputedStyle Tokyo Night 팔레트 정확(keyword #bb9af7/600·func #7aa2f7·string #9ece6a·number #ff9e64·comment #737aa2·pre #1a1b26)·텍스트 무손실·script 주입 0·콘솔 에러 0. test-runs.d POST-DEPLOY 결과 + evidence/pb0008-sql-highlight-live-20260724.png.

## REV-20260727T010501-doc-sync-rn-0727 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-07-24 블록(대화·공유·관리 UX 8항목) doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(2026-07-24 블록 prepend·generated 갱신) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(29ef0baf 등 선례 동일 토큰).
- **검증**: `node --check` PASS · vm 구조검증(releases +1·head 8항목·이전 블록 보존·스키마 type/area/title/detail·내부용어 누출 0). 8항목 전부 owning POST-DEPLOY PB-0008 라이브검증(sql 35d6453f·csv 8bf643e0·reanswer 28ec78b3·newfolder f697eddf·share-scroll 5c9d5bf2·share-rail 6290ae1e·metadata-review c7e928c8·graph-emoji 791d5761). ULTRACODE 적대검증 wf_2676a918 — RN confirmed·minor 1(graph-emoji 문구 3종 그레이스케일 정합) fold-in.
- **cache-buster**: `?v=dev` 고정(빌드 자동주입·index/admin 편집 0·수동 bump 폐지 ITEM-09).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260727T102027-sql-diff-highlight [SUBAGENT: SHIP-WITH-FIXES — MAJOR(FP)+MINOR 3건 in-cycle 수정, 6축 나머지 PASS] ```diff``` 코드블록 내 SQL 구문 하이라이트 (Minor §12.3, frontend-only)
- **[SUBAGENT] 적대 패널 판정 (§18.8, 보안+프론트, 경험적 실행 검증)**: **VERDICT SHIP-WITH-FIXES**. 1 XSS PASS(sqlTokenizeToFragment 는 createElement/textContent/createTextNode 전용·appendChild 는 안전노드 이동·innerHTML sink 무첨가·DOMPurify 최종) · 2 refactor 등가성 PASS(sqlTokenizeToFragment 추출+thin highlightSqlInto, 트레일링개행 strip 정위치, ```sql 무회귀) · 3 **MAJOR(FP)+MINOR(FN)** · 4 diff 구조 PASS(+MINOR hunk 토큰화) · 5 CSS PASS(+MINOR 2: hunk/meta 색·user-bubble parity) · 6 app/share drift PASS(line-for-line).
- **in-cycle 수정 반영**:
  - **[MAJOR Finding 3 — looksLikeSql 오탐] 수정**: verb∧clause(bare FROM 의존) 게이트가 `import…from`+`.delete()/.create()/.update()`·`Object.values()` 등 ORM/코드 관용구를 SQL 오탐. → **실제 SQL statement '모양' 앵커**로 재작성(`SELECT…FROM`(JSX `<select>` negative lookbehind 배제)·`INSERT INTO`·`UPDATE <tbl>…SET`·`DELETE FROM`·`(CREATE|ALTER|DROP) (TABLE|VIEW|…)`·`TRUNCATE`·`MERGE INTO`·`GRANT/REVOKE…ON`·`WITH cte AS (`). 리뷰 지적 FP 6종(TypeORM/JS/Python/Object.values/JSX/Dockerfile) 전부 false, 실제 SQL 13종(whereless UPDATE·CTE 포함) 전부 true 로 실측 확인.
  - **[MINOR Finding 4 — hunk/meta 토큰화] 수정**: 토큰화를 내용 라인(diff-add/del/ctx)으로 한정 — hunk(`@@`)·meta 라인 미토큰화.
  - **[MINOR Finding 5 — CSS] 수정**: `.diff-sql .diff-line` 색 override 에 `:not(.diff-hunk):not(.diff-meta)` 추가(hunk 파랑·meta 회색 고유색 유지) + `.message.is-user .message-content pre.diff-block.diff-sql { background:#1a1b26 }`(사용자 말풍선 SQL diff 다크 배경 parity).
  - **[MINOR Finding 3 — FN]**: `SELECT NOW()`(FROM 없음) 등 일부 미탐은 benign(색 미적용, 텍스트·안전 무손상) — 잔존 허용.
- **잔여(수정 안 함)**: NIT — looksLikeSql/tokenizer 전용 단위테스트 부재(기존 browser-helper 관례, headless 검증으로 대체). 잔여 초희귀 FP(예: `<select>`+import 가 lookbehind 우회하는 변형)도 consequence=benign 오색칠뿐(안전·무손실 불변).
- **결정 근거**: 외부 하이라이터 무추가·기존 enhanceDiffBlocks 패턴 정합·additive(비-SQL diff 무영향). add/del 신호는 배경·border·gutter 로 유지(color-only override 라 border/::before 불변).
- **검증**: headless chromium(chromium-1208, 실 vendor marked+DOMPurify, app.js 추출 실소스) **22/22 PASS**(회귀·SQL diff 토큰·add/del 보존·평문 기본색·배경 tint·gutter·텍스트 무손실·비-SQL diff 무영향·게이트 오탐0·hunk 미토큰화·XSS 무력화) · `node --check` · 시각증거 evidence/sql-diff-highlight-20260727.png. POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.

## REV-20260727T110000-sql-diff-highlight-postverify [SKIPPED:non-policy-doc] SQL diff 하이라이트 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록). 실 구현 리뷰 정본 = REV-20260727T102027-sql-diff-highlight([SUBAGENT] SHIP-WITH-FIXES·MAJOR+MINOR3 in-cycle 수정).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #948 머지(main 8d69490c) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성" 1줄 표면화 완료. 배포=web-a/web-b 8d69490c 롤링 재생성·healthy·RestartCount 0(롤백 0).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: 실 Windows Chrome/150 배포본 markdownToHtml eval(SQL diff) → diff-sql·sql-tok 9개·getComputedStyle Tokyo Night 색 정확(keyword #bb9af7·string #9ece6a·number #ff9e64)·평문 기본색 #c0caf5·add/del 배경 tint·hunk 미토큰화·gutter 보존·script 0·콘솔 에러 0. test-runs.d POST-DEPLOY 결과 + evidence/pb0008-sql-diff-live-20260727.png.

## REV-20260727T113640-model-persist [SUBAGENT: SHIP-WITH-FIXES — 2라운드 모두 BLOCK, 지적 10건(B1·C1~C4 / B-B·C-A~C-D) 전건 in-cycle 수정] 대화별 "마지막 요청 모델" 보존 + '+ 새 대화'=haiku (Minor §12.3, web/UI + backend additive)
- **[SUBAGENT] 적대 패널 (§18.8, security+backend+qa+ux 4렌즈, 실 소스 추적 검증)** — 2라운드 수행. 두 라운드 모두 **BLOCK** 판정을 받았고 전건 수정 후 재검증했다.
- **1R BLOCK 지적 → 수정**:
  - **B1(high) 랜딩·로그아웃 경로 미커버**: 본 변경이 `state.selectedModel` 을 "명시 클릭으로만 설정" → "대화 로드마다 서버값으로 설정" 으로 바꿔, 대화 삭제/보관/나가기 후 랜딩 및 로그아웃→재로그인(페이지 리로드 없음) 시 직전 대화(직전 **계정**)의 모델이 다음 신규 대화 요청에 실림. → `_resetComposerModelSelection(state)` 신설 + 이탈 경로 4곳 적용.
  - **C1(med) 대화 전환 대기 창**: `activeConversationId` 는 바뀌었으나 hydration 전인 창에서 전송하면 직전 대화 모델이 **대상 대화 KV 에 영구 저장**. → `selectConversation` 에서 전환 즉시 리셋.
  - **C2(med) 기본값 영구 고정**: 웹은 선택기 미상호작용에도 항상 `model` 을 실어 보내므로 모든 대화가 "첫 전송 시점 기본값"에 pin → 이후 기본 모델 상향이 기존 대화에 영원히 미반영. → **기본값 이탈만 저장**(같으면 빈 값으로 해제).
  - **C3(med) 그룹 대화 누출**: 대화 단위 키면 멤버 A 의 선택이 B 의 composer 를 바꾸고 **B 의 토큰 한도로 청구**. → KV 키를 `model:<account_id>` 로 계정별 분리 + `_display_window == "DENY"` 시 미반환.
  - **C4(med) 테스트 위양성**: ask 하네스가 `_is_allowed_api_model`/`_is_safe_model_name` 을 patch 해 무력화(저장이 검증 게이트 위로 올라가는 회귀 미검출), S3 mirror 검출기가 두 조건 모두 false 라 vacuous. → patch 제거 + A1c(거부 alias 400 & KV 미도달)·H2c/H2d 추가, 검출기 재작성 + **S3b 대조군**(추론 강도 미러는 실제 검출되어야 함).
- **2R BLOCK 지적 → 수정** (1R 수정이 만든 회귀 포함):
  - **B-B(med, 자체 회귀) 랜딩 재로드가 미전송 선택 삭제**: `loadHistory` 활성대화없음 분기는 "이탈"이 아니라 랜딩/pending 에 **머무는 동안 반복 호출**되는 재렌더 경로 — 무조건 리셋이 '+ 새 대화'에서 고른 뒤 아직 안 보낸 선택을 사이드바 일괄삭제·제품 롤백 등에서 조용히 삭제. → hydration 경로와 동일 가드 적용(`!_modelHydrationShouldSkip(state, "")`) + R3b/R4/R5 회귀 테스트.
  - **C-A(med) `moveConversationToFolder` hydration 공백**: `loadConversations` 만 호출해 `activeConversationId` 가 hydration 없이 재지정 → 다음 전송이 그 대화의 저장 모델을 기본값으로 clobber. → 폴더 이동 후 `loadHistory()` 추가 + **클래스 차원 가드** `_shouldSendModelField(state, targetConvId, isLazyCreate)`: 신규 대화 / 이 대화에서 명시 선택 / 이 대화 hydration 완료 중 하나일 때만 `askBody.model` 동봉(그 외 생략 → 서버가 기존 저장값 보존).
  - **C-B(med) 최종 fallback 리터럴**: `_composerCurrentModel` 말단 안전망이 `"claude-sonnet-4"` — 카탈로그 로드 실패 시 "새 대화는 haiku" 계약과 반대로 상위 모델 전송. → `"claude-haiku-4"`(서버 `API_DEFAULT_MODEL` 과 동일)로 정정. 나머지 chain 발산은 위 clobber 가드가 흡수.
  - **C-C(low) 열린 메뉴 하위 재렌더**: 매 로드마다 `_renderComposerModelMenu()` innerHTML 재생성 → 열린 상태에서 hover·클릭 대상 노드 교체. → 메뉴가 보일 때만 재렌더(사이드바 unread sync 의 열린-메뉴 skip 과 동일 패턴).
  - **C-D(low) `model:unknown` 공유 슬롯**: 계정 식별 불가 호출자들이 한 키를 공유 → 계정별 분리로 막으려던 것을 재현. → **fail-closed**(빈 키 반환, 저장·복원 모두 skip) + H2e.
  - **B-A(critical, process) 스테이징 누락 지적**: 리뷰어가 index 를 본 시점이 `git add` 전이라 1R 코드가 staged 로 보인 **타이밍 아티팩트**. 현재 10 파일 전부 staged 확증(`git show :…` 마커 grep — `_model_kv_key` 4·`_resetComposerModelSelection` 6·테스트 13(→14)·`index.html` placeholder 1). 지적 자체는 타당한 절차 리스크라 커밋 직전 재확인을 관례로 채택.
- **잔여(수정 안 함 — 문서화)**:
  - **C5 / fix_with_ai 는 기본 모델로 실행**: 'AI 로 고치기'는 model 없이 재dispatch 되므로 정정 run 이 대화의 선택 모델이 아닌 기본값으로 실행된다. 저장값은 덮어쓰지 않으므로(AC-MP-4) 사용자 선택은 보존된다. **본 cycle 에서 바꾸지 않는 근거는 "선존 동작" 만이 아니다 — 계정별 키 도입으로 "그 대화의 모델" 이 더 이상 단일 사실이 아니게 되어, 서버 주도 정정 run 이 어느 멤버의 선호를 택할지가 모호하다. 배포 기본값을 쓰는 편이 오히려 정합적**(리뷰어 §3 수용).
  - **AC-MP-7(b) 기본값 통과 시 명시 선택 해제**: 이탈-인코딩의 알려진 성질. AC 에 명시해 다음 리뷰가 재논쟁하지 않게 고정.
- **결정 근거**: 추론 강도 선택기(대화별 KV + `/api/history` hydration)의 검증된 구조를 재사용하되 **로컬 미러는 의도적으로 두지 않는다** — 미러가 있으면 새 대화가 직전 모델을 상속해 사용자 요구("'+ 새 대화'는 haiku")를 정면으로 깬다. 이 비대칭이 B1 의 근원이기도 했다(미러가 랜딩 상태를 무해하게 만들어 주던 안전망이 모델에는 없었다) → 리셋 헬퍼가 그 자리를 대신한다.
- **대안 검토**: (A) localStorage 미러 — 사용자 요구 위반, 불채택. (B) 대화 단위 단일 키 — 그룹 대화 교차 오염(C3), 불채택. (C) 요청 model 원문 저장 — 기본값 영구 pin(C2), 불채택. (D) **계정별 키 + 기본값-이탈 저장 + 전송 clobber 가드(채택)**.
- **검증**: `test_model_persist.py` 14 PASS · `verify_model_persist.mjs` 32 PASS · `node --check`/`py_compile`/ruff PASS · `make test` 전체 회귀 0(선존 FAIL 4건은 clean main 84f2e5ab 에서 동일 재현 확인 — 본 변경 무관). POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.
- Human Approval Needed: no (Minor §12.3 — 스키마/RBAC/엔드포인트 0, additive 응답 필드 1개).

## REV-20260727T124500-model-persist-postverify [SKIPPED:non-policy-doc] model-persist POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 실증 기록 + 스크린샷 증거). 실 구현 리뷰 정본 = REV-20260727T113640-model-persist([SUBAGENT] 2라운드 BLOCK → 지적 10건 전건 수정).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #953 머지(main **8cfa00b0**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료. 배포 범위 = web 전용(변경 파일이 web 라우터·정적 자산 한정, 워커/agent 코드 무변경).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-MP-1(재로드 복원 — `payload.model=claude-sonnet-4` 서버 왕복 + 라벨 `claude-sonnet`)·AC-MP-2(대화 간 격리·복귀)·AC-MP-3('+ 새 대화'=`claude-haiku`) **PASS**, 시각 증거 2건(`docs/evidence/pb0008-model-persist-{restore,newconv}-20260727.png`). **AC-MP-9 는 라이브 미검증** — 유발 트리거(일괄 삭제·실패 롤백)가 라이브 테넌트에서 파괴적/유발 불가라 단위검증(R3b/R4/R5)만으로 커버하고 그 사실을 test-runs.d 에 명시했다(미수행을 검증으로 오인 금지).
- **부수 확인(선존 동작, 본 변경 무관)**: 인자 없는 새로고침은 `initializeWorkspace` 가 직전 대화를 자동 선택하지 않는 기존 설계(`allowCurrentFallback=false`)라 빈 화면으로 시작한다. 사용자 표현 "새로고침" 의 실질 충족 경로는 (a) deep-link 재로드 즉시 복원 (b) 재로드 후 대화 재진입 시 복원이며 양쪽 모두 PASS.
- Human Approval Needed: no.

## REV-20260727T160748-product-picker-scroll [SKIPPED:session-policy-no-subagent] 제품 선택 드롭업 선택 항목 중앙 스크롤 (Minor §12.3, frontend-only)
- **Panel 처리(§18.8) — 정직 표기**: dispatch 표상 UI/화면/레이아웃 키워드 매칭(ux·design) 대상이나, **본 세션은 사용자 환경 정책으로 subagent(Agent tool) 호출이 금지**되어 [SUBAGENT] 패널을 수행하지 못했다. 대체로 (a) 실 chromium 레이아웃 위 헤드리스 검증 11 케이스(경계·무간섭·무예외 포함)와 (b) 아래 자체 적대 검토(H1~H8)를 수행했다. **패널 미수행 사실을 "검증함"으로 오인하지 않는다** — 다음 cycle 에서 패널 재개 시 본 변경을 대상에 포함할 수 있다.
- **변경 요지**: `scrollProductDropupToSelected(menu)` 신설 + `openProductDropup()`·`renderProductChip()`(열린-상태 재렌더) 2곳 호출 + 검색 입력 `focus({preventScroll:true})`. 계산식 `scrollTop = clamp(selected.offsetTop - (menu.clientHeight - selected.offsetHeight)/2, 0, scrollHeight-clientHeight)`.
- **자체 적대 검토(H1~H8)**:
  - **H1 (재렌더 점프)**: `renderProductChip()` 은 컴포저 상태 갱신 경로(L6658 busy 동기화 등)에서 자주 호출된다 — 메뉴가 열린 채 재렌더되면 위치가 이동한다. 단 이는 **pre-existing**: 재렌더가 항목 DOM 을 새로 만들어 `scrollTop` 이 이미 0(최상단)으로 리셋되므로, 본 변경은 "최상단 점프"를 "선택 항목 중앙 복원"으로 바꿀 뿐 새 점프를 만들지 않는다(요청 취지에 부합). 사용자가 스크롤해 다른 제품을 훑던 중의 위치 손실은 재렌더 자체가 원인이며 본 cycle 범위 밖(개선 여지로 기록).
  - **H2 (검색 필터와의 상호작용)**: `filterProductDropupItems` 는 항목을 `hidden` 토글만 하고 스크롤을 만지지 않는다. 필터로 `scrollHeight` 가 줄면 브라우저가 `scrollTop` 을 자동 clamp 하므로 "빈 영역만 보이는" 상태가 생기지 않는다(결과가 뷰포트보다 짧으면 0). 필터 후 재정렬은 하지 않는다 — 검색 중 커서/포커스를 방해하지 않기 위함(의도).
  - **H3 (`preventScroll` 미지원)**: 옵션 객체를 무시하는 구형 엔진에서는 포커스가 스크롤을 유발할 수 있으나, **포커스 → 중앙 정렬 순서**라 마지막 설정이 이긴다. 예외는 `try/catch` 로 이미 감싸져 있다.
  - **H4 (다중 `.is-selected`)**: `buildProductDropupItem` 은 view-only 그룹을 항상 `selected:false` 로 만들고, auto/pinned 중 하나만 selected 다. `querySelector`(첫 매칭)로 충분하며 오탐 없음.
  - **H5 (숨김 상태 호출)**: `.hidden`(display:none) 상태면 `offsetTop`/`clientHeight` 가 0 이라 `scrollTop=0` — 무해한 no-op. 호출 2곳 모두 표시 상태(`hidden` 제거 후 / `aria-expanded="true"`)라 실제로는 발생하지 않는다.
  - **H6 (좌표계 가정)**: `offsetTop` 은 `offsetParent` 기준이므로 메뉴가 `position:absolute` 여야 `scrollTop` 과 같은 기준이 된다 — 가정을 헤드리스 T1 이 **실측 assert**(`sel.offsetParent === menu`)한다. sticky 검색 wrap 은 항목의 조상이 아니라 형제라 무관(T2b 가 검색칸 유무 양 경로 확인).
  - **H7 (성능)**: 레이아웃 읽기 1회 + `querySelector` 1회, 메뉴 open 시점 한정. 강제 reflow 비용은 이미 발생하는 렌더 경로 안이라 체감 영향 없음.
  - **H8 (접근성·모션)**: 즉시 스크롤이라 애니메이션 없음(reduced-motion 무관). 포커스는 검색칸에 유지되고 DOM/ARIA 를 바꾸지 않아 스크린리더 흐름 무변경.
- **결정 근거**: `scrollIntoView({block:"center"})` 는 한 줄로 끝나지만 **조상 스크롤 컨테이너(페이지/messageLog)까지 스크롤**해 컴포저 주변 화면이 튄다 — 메뉴 자신의 `scrollTop` 만 계산·설정하는 편이 부작용 표면이 좁다. 선택 항목이 없을 때(=auto) 스크롤을 건드리지 않는 것도 의도 — auto 는 목록 최상단 근처라 기존 동작이 이미 최적이며, 불필요한 스크롤 변경을 만들지 않는다.
- **검증**: `tests/headless/verify_product_dropup_scroll.py` **11/11 PASS**(chromium 145, 실 app.js 함수 원문 + 실 styles.css) · `node --check app.js` PASS · 시각 증거 `docs/evidence/product-dropup-scroll-{before,after}-20260727.png`(before=최상단·선택 항목 미표시 / after=선택 항목 중앙). POST-DEPLOY PB-0008(Windows-browser) = 배포 후 정본.
- **스키마/RBAC/백엔드**: 0. Human Approval Needed: no (Minor §12.3).

## REV-20260727T163000-product-picker-scroll-ci-fix [SKIPPED:test-harness-rename-no-runtime-change] 헤드리스 검증 스크립트 rename (CI 수집 회피)
- **Panel skip 사유(§18.8)**: 런타임 코드 변경 0 — 검증 하네스 파일명 rename + 문서 경로 참조 갱신뿐(`src/**` 무변경). 실 구현 리뷰 정본 = REV-20260727T160748-product-picker-scroll.
- **문제**: 신규 검증 스크립트가 `test_` prefix 라 CI pytest 가 수집 → 러너 playwright 부재로 collection error(exit 2) → test job FAIL. **본 cycle 이 직접 유발한 red 이므로 무관 flake 로 분류하지 않고 즉시 수정**했다.
- **수정**: `verify_` prefix 로 rename(프로젝트 `tests/verify_*.mjs` 관례와 동일). 헤드리스 검증은 명시 호출 전용이며, CI 는 pytest 단위테스트만 게이트한다는 기존 계약을 존중한다(헤드리스/브라우저 검증은 로컬·PB-0008 축).
- **대안 검토**: (A) CI 에 playwright 설치 — 러너 시간·유지비 증가, 본 cycle 범위 밖. (B) 파일 상단 `pytest.importorskip` — 수집은 계속 일어나 취약. (C) **rename(채택)** — 수집 자체를 회피, 관례 정합.
- **검증**: rename 후 11/11 PASS 재확인 · ruff PASS · pyproject 에 `python_files` 커스텀 없음 확인(기본 패턴만 수집).
- Human Approval Needed: no.

## REV-20260727T165500-product-picker-scroll-postverify [SKIPPED:non-policy-doc] 제품 선택 드롭업 중앙 스크롤 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록 + 스크린샷 증거). 실 구현 리뷰 정본 = REV-20260727T160748-product-picker-scroll([SKIPPED:session-policy-no-subagent] — 세션 정책상 subagent 패널 미수행, 헤드리스 11 케이스 + 자체 적대 검토 H1~H8 로 대체).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #955 머지(main **b30bb45d**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료. 배포 범위 = web 전용(변경 파일이 정적 자산·문서 한정, 워커/agent 코드 무변경). soak 통과(edge 일시 blip 1회 — 연속 3회 미만 회복, 롤백 0).
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-PPSC-1(중앙 정렬 — centerDelta **0**, scrollTop 254 가 clamp 경계 밖이라 실제 정렬임을 확증)·AC-PPSC-2(양단 clamp — 마지막 항목 선택 시 scrollTop=maxScroll=447, fullyVisible)·AC-PPSC-3(검색 포커스 유지) **PASS**, `offsetParentIsMenu=true` 좌표계 계약 라이브 실측, 페이지 에러 0. 시각 증거 `docs/evidence/pb0008-product-picker-scroll-live-20260727.png`(선택 제품이 목록 한가운데 + 위아래 이웃 제품 동시 노출 — 사용자가 요청한 "상대적인 위치" 파악이 실제로 가능해짐).
- **검증 위생**: 라이브 테넌트 부작용 최소화 — 대화 미선택(랜딩) 상태에서만 제품을 바꿔 owner PATCH 경로를 타지 않게 했고(로컬 pref 만), 검증 후 원래 선택(KR_LIVE)으로 복원 + `win-browser.py down` 으로 드라이버 인스턴스만 종료.
- Human Approval Needed: no.

## REV-20260727T180036-share-bar-layout [SKIPPED:session-policy-no-subagent] 공유 대화 뷰 액션/조회수 재배치 + 바 hover 확장
- Trigger: UI/button/layout/버튼·레이아웃 keyword matched → §18.8 표상 `ux, design` subset 대상.
- **Panel skip 사유(§18.8)**: 본 세션의 사용자 환경 정책이 "Do not call the AgentTool unless the user requested it" 로 subagent 호출을 금지하고 사용자 요청도 없었다. 동일 상황의 선례(REV-20260727T160748-product-picker-scroll)와 같은 처리이며, 대체 검증으로 **헤드리스 chromium 실 레이아웃 8 케이스 + 구조 회귀 5 케이스 + 자체 적대 검토(아래 H1~H7)** 를 수행했다. 미수행을 "검증함"으로 오인하지 않도록 여기에 명시한다.
- **판단 근거**:
  - **액션 그룹 전체 이동(참여/로그인 포함)**: 사용자 원문은 `['링크 복사','내 계정에서 fork']` 2종만 지목했으나, 같은 컨테이너의 나머지 2종(참여·로그인 링크)은 **조건부 노출(hidden)** 이라 사용자 화면에 안 보였을 뿐 성격이 동일한 조작이다. 2종만 옮기면 같은 액션군이 상·하로 쪼개져 일관성이 깨지므로 그룹 전체를 이동했다(요청 확대가 아니라 요청의 자연 경계 적용). 이 판단을 TASK/FUNCTION 에 명시.
  - **바 높이 보존 방식**: 사용자 추가 요청("기존 크기 거의 유지, 필요 시 hover 확장")에 대해 (a) 버튼 규격 축소로 기본 높이를 유지하고 (b) hover/focus 에서만 확장하는 2단 구성을 택했다. `height` 대신 `padding` 을 전이시켜 fixed 바의 리플로우 범위를 줄였다.
  - **접근성 보강(자율 판단)**: `:hover` 만 두면 키보드 사용자는 확장 없이 2px 패딩 버튼을 조작하게 되므로 `:focus-within` 을 함께 걸었고, hover 개념이 없는 터치 환경(`@media (hover:none)`)은 확장 규격을 상시 적용해 타겟 크기를 확보했다. `prefers-reduced-motion` 은 크기 변화는 유지하되 애니메이션만 끈다(기능 손실 없이 모션만 제거).
- **자체 적대 검토(H1~H7, 전건 반영·확인)**:
  - H1 하단 바가 커져 마지막 메시지를 가리는가 → `.share-container` padding-bottom 80px ≥ hover 확장 높이 52.5px, 헤드리스 T7 로 고정.
  - H2 `@media print` 가 헤더 기준으로 `.share-actions` 를 숨겼는데 이동 후 무력화되는가 → 셀렉터가 클래스 기반이라 유효, 이제 `.share-footer` 숨김과 이중 적용(인쇄물에 버튼 미노출 유지).
  - H3 조회수가 `.share-meta-item:empty{display:none}` 규칙에 걸려 안 보이는가 → `share.js` 가 항상 `조회 N회` 를 채우므로 비지 않는다(값 0 도 "조회 0회").
  - H4 우측 스크롤 rail(`.share-point-rail`, z-index 50)이 높아진 바에 가려지는가 → rail z-index 가 footer(10)보다 높아 위에 그려지고 dot 클릭 유지(기존과 동일 관계).
  - H5 좁은 화면에서 버튼이 안내문과 겹치는가 → `flex-wrap:wrap` + 600px 이하에서 안내문 100% 폭 + 액션 우측 정렬로 2줄 분리, 모바일 하단 여백 96px.
  - H6 hover 확장이 커서 아래 콘텐츠를 덮어 클릭을 가로채는가 → 확장분 17px 은 바 자체 영역 내부이고, 확장 트리거가 바 hover 라 커서는 이미 바 위에 있다(콘텐츠 클릭 경로 무간섭).
  - H7 `share.js` 가 DOM 위치에 의존하는가 → `getElementById` 4곳 + 이벤트 바인딩만이며 부모/형제 탐색 없음(`grep` 확인). 구조 이동에 안전.
- **검증**: 구조 회귀 `tests/test_share_bar_layout.py` 5 PASS · 헤드리스 레이아웃 `tests/headless/verify_share_bar_layout.py` **8/8 PASS**(T4 바 높이 35.0→35.2px Δ+0.2 · T5 hover 52.5px · T6 transition 0.18s · T8 버튼 31.5px) · `make test` 전체 실패 15건이 clean main baseline 과 **차집합 0**(회귀 없음) · ruff PASS. 시각 증거 `docs/evidence/share-bar-layout-{before,after,hover}-20260727.png`.
- **검증 환경 정직 기록**: 위는 모두 헤드리스/정적 검증이다. `visual_verification_scope: always`(FIRST_REQUEST.md) 에 따른 **Windows-browser(PB-0008) 라이브 검증은 배포 후 수행**한다 — 정적 자산이 컨테이너 이미지에 포함돼 미배포 코드로는 실 화면 실측이 불가하기 때문(선례와 동일 순서).
- Human Approval Needed: no (Minor §12.3 — 비파괴 frontend 배치 변경).

## REV-20260727T182000-share-bar-layout-postverify [SKIPPED:non-policy-doc] 공유 대화 뷰 하단 바 레이아웃 POST-DEPLOY 라이브 실증 + deploy_scope 근거
- Panel skip 사유(§18.8): 코드 변경 0(문서 전용 POST-DEPLOY 기록 + 스크린샷 증거 4건). 실 구현 리뷰 정본 = REV-20260727T180036-share-bar-layout([SKIPPED:session-policy-no-subagent] — 헤드리스 8 + 구조 5 + 자체 적대 검토 H1~H7 로 대체).
- **§12.2 deploy_scope 근거**: FIRST_REQUEST.md 전역 `deploy_scope: included`(cycle 시작 시점 기존 선언)에 근거해 PR #958 머지(main **486a587c**) 후 `make deploy-web-only` 무중단 배포를 confirm 없이 수행. "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료(원 cycle 세션). 배포 범위 = web 전용(변경 파일이 정적 자산·문서 한정, 워커/agent 코드 무변경). Caddyfile 무변경으로 caddy blip 0, post-cutover soak 90s 통과, 롤백 0.
- **POST-DEPLOY 실증(Windows-browser, PB-0008)**: AC-SBL-1(액션 4종 하단 바 우측 — 바 우측 여백 16px, 안내문보다 오른쪽, 헤더 잔존 액션 0)·AC-SBL-2(`조회 16회` 헤더 `.share-meta` 4번째, y=96 < 바 y=801)·AC-SBL-3(기본 바 높이 **35px** — 변경 전 35.0px 대비 체감 동일)·AC-SBL-4(hover 시 **53px** + 패딩 6→10px + 상단 그림자 + 배경 불투명, `transition … 0.18s`) **전부 PASS**. 추가로 `링크 복사` → `복사됨 ✓`(class `is-copied`) 토글, 최하단 스크롤에서 마지막 메시지 미가림(bottom 732 < 바 top 783), 버튼 `elementFromPoint` hit-test 통과, 페이지 에러 0. 시각 증거 `docs/evidence/pb0008-share-bar-layout-live-{default,hover,header,copied}-20260727.png`.
- **검증 시점 배포본 주의(정직 기록)**: 검증 중 다른 cycle 이 PR #959 를 배포해 서빙 SHA 가 486a587c → **66575331** 로 전진했다. `git merge-base --is-ancestor 486a587c 66575331` 로 본 변경이 서빙본에 포함됨을 확인한 뒤 실측했으므로 검증은 유효하며, 오히려 최신 배포본 기준 실증이다.
- **검증 위생**: fork(신규 대화 생성)·참여(그룹 멤버십 변경) 는 라이브 부작용을 피해 **클릭하지 않고** 노출·좌표·hit-test 로만 확인 — 본 cycle 변경이 HTML 구조 이동 + CSS 뿐이고 `share.js` 무변경이라 클릭 핸들러 자체는 회귀 대상이 아니다(구조 회귀 테스트 L3 가 id·배선 보존을 이미 게이트). 검증 후 `win-browser.py down` 으로 드라이버 인스턴스만 종료.
- Human Approval Needed: no.

## REV-20260727T234439-model-picker-copy [SKIPPED:session-policy-no-subagent] — PASS
- 대상: 모델 선택기 중복 문자열 제거 + 설명 축약 + `word-break: keep-all`. CHG-20260727T234439-model-picker-copy 정합.
- 리뷰 방식([SKIPPED] 사유): §18.8 subagent 패널은 **본 세션의 사용자 환경 정책(Agent tool 미허용)** 으로 미수행. 대체 검증 = 실 Windows 브라우저 **BEFORE/AFTER 정량 실측**(줄 수·문자 수·배지 수·메뉴 높이) + 전체 pytest rc=0 + `node --check` + 아래 자기 적대 검토. 변경면이 표시 문자열 3개·JS 조건 1줄·CSS 1속성이라 정적 패널의 추가 판별력이 낮다.
- 자기 적대 검토:
  - *배지를 무조건 제거하지 않은 이유*: `group` 은 provider 혼재 카탈로그(Local LLM `auto`/`edge`/`core`/`code`)에서 실제 구분 기능을 한다. 지금 무의미한 건 "label 이 이미 group 명으로 시작할 때"뿐이므로 그 조건에서만 생략한다 — 미래에 비-Claude provider 가 카탈로그에 들어오면 배지가 자동으로 다시 살아난다(하드코딩 제거였다면 그때 회귀).
  - *`keep-all` 이 과한가*: 아니다. 문구 단축은 "지금 이 문구·이 폭"에서만 성립하는 완화이고, 근본 원인(한국어 음절 단위 줄바꿈)은 남는다. 두 조치는 중복이 아니라 계층이 다르다.
  - *정보 손실*: "Anthropic"·"Claude"·"frontier" 는 label·배지·형제 행에서 이미 알 수 있는 정보라 제거해도 변별력이 줄지 않는다. 오히려 세 행을 **같은 축**(성능 등급 · 용도)으로 맞춰 비교가 쉬워졌다.
  - *값 오염 없음*: `value`(claude-opus-5 등)는 저장 대화·단가·runtime_settings 키라 손대지 않았다. description 은 표시 전용.
- 위험도: Minor(§12.3) — 표시 문자열·CSS. RBAC·라우팅·스키마 0.
- Verification: PRE-COMMIT Windows-browser 실측 PASS(2줄→1줄, 배지 3→0) · pytest rc=0 · node --check OK. POST-DEPLOY 배포본 육안 재확인 예정.
- Cross-ref: MODIFY CHG-20260727T234439-model-picker-copy / test-runs.d/20260727T234439-model-picker-copy.md.

## REV-20260728T010301-doc-sync-rn-0728 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-07-27 블록에 3항목 append(답변 모델·공유뷰·관계도) doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(기존 2026-07-27 블록 3항목 append·summary 증강·generated 불변) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(351ed406 등 선례 동일 토큰).
- **검증**: `node --check` PASS · vm 구조검증(releases[0] 2026-07-27 items 4→7·releases[1] 2026-07-24 8항목 보존·스키마·enum·내부용어 누출 0). 3항목 전부 owning POST-DEPLOY PB-0008 라이브검증(opus5 413703b9·share-bar 486a587c/2ec5e0aa·detail-db-groups 66575331/42ee04d0). 릴리즈노트 render 테스트 jsdom 미설치로 미실행(render 로직 미변경). ULTRACODE 적대검증 wf_c9bea2de — RN 3항목 CONTENT confirmed·verifier 가 초안 07-28 date framing REJECT→07-27 append 로 정정(제외 4건: model-picker-copy 미배포·change-reanalysis 백엔드·false-truncation unverified-live·feature-0026 측정전용).
- **cache-buster**: `?v=dev` 고정(빌드 자동주입·index/admin 편집 0·수동 bump 폐지 ITEM-09; wrapper 헤더 수기 bump 지시는 07-12 이전 regime 부적용).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260728T024258-model-access-rbac [SKIPPED:session-policy-no-subagent] — PASS
- 대상: 계정/역할별 LLM 모델 사용 권한(동적 `model.access.<value>` RBAC). CHG-20260728T024258-model-access-rbac 정합. **Critical §12.3 — 인가 구조 변경, 사용자 승인 후 착수**(설계 3안 제시 → "전부 기본 부여" 채택).
- 리뷰 방식([SKIPPED] 사유): §18.8 subagent 패널은 본 세션의 사용자 환경 정책(Agent tool 미허용)으로 미수행. 대체 = **인가 판정표를 테스트로 전수 고정**(25 케이스, 판정 5분기 + 경계 4종) + 전체 회귀 rc=0 + ruff + 아래 자기 적대 검토. Critical 등급이므로 검토 항목을 공격각 단위로 나열한다.
- **자기 적대 검토 (공격각 8)**:
  1. *게이트 우회 — 다른 진입점으로 model 을 넣을 수 있나?* 클라이언트 지정 model 경로를 전수 grep: `/api/ask` 의 `data.get("model")` 과 재답변(`_reanswer`)의 forward 뿐이며 후자는 `ask()` 재dispatch 로 동일 게이트를 재통과한다. 저장된 대화 모델 hydration(L256)은 **표시 전용**이고 실제 요청은 다시 ask() 를 탄다. → 단일 choke-point 성립.
  2. *conn 없이 호출해 fail-open 분기를 탈 수 있나?* `conn=None` 이면 row 등록 여부를 확인할 수 없으므로 **미보유는 거부**로 닫았다(G4). fail-open 은 conn 이 있고 "row 가 실제로 없다" 를 확인했을 때만.
  3. *fail-open 이 너무 넓은가?* 두 경우(row 미등록 / 조회 예외)로 한정하고 둘 다 WARNING 을 남긴다. 대안(전원 차단)은 신규 배포 첫 요청부터 모든 대화 403 — 통제 목적보다 큰 사고. 관측 가능성으로 보완.
  4. *재배포가 관리자의 해제를 되살리나?* ← **가장 위험한 조용한 실패**. 제품 권한의 무조건 re-grant 패턴을 그대로 베끼면 발생한다. `rowcount>0` one-time 마커로 차단하고 G7 이 회귀를 고정한다.
  5. *API 토큰이 게이트를 우회하나?* scope 면제는 **positive allowlist 축만** 면제이고 `bool(granted)`·절대 denylist·ask() 게이트는 그대로 AND 로 남는다(G6 3케이스). 저권한 서비스 계정에서 해제하면 토큰도 차단.
  6. *표시 필터가 새 실패 모드를 만드나?* 전부 차단 시 원본 유지 + WARNING — 빈 선택기(사용자에겐 "로딩 중")로 원인 불명 상태를 만들지 않는다. 표시를 관대하게 둬도 집행은 ask() 가 담당하므로 인가 누출 아님.
  7. *400/403 축이 섞이나?* 카탈로그 밖 model 은 본 게이트가 True 를 주고 `_is_allowed_api_model` 이 400 을 낸다(G2). 같은 실패가 두 갈래 메시지로 갈리지 않는다.
  8. *프론트 변경이 기존 그룹을 깨나?* `excludeDynamic` 조건을 **좁히기만** 했다(`is_dynamic` → `is_dynamic && group==='product_access'`) — 제품 경로는 동일 분기를 그대로 타고, 전체 회귀 rc=0 이 뒷받침한다.
- **잔여 위험(정직 표기)**:
  - **POST-DEPLOY 미검증** — 권한 grid 의 모델 row 렌더·'모두 적용' 왕복·해제 후 403/선택기 소멸은 배포 후 PB-0008 로 확인해야 한다(부트스트랩 seed 선행 필요라 사전 검증 불가). 배포 직후 수행 + 기록 예정.
  - **모델별 quota 는 범위 밖** — 본 cycle 은 "선택 가능/불가" 이진 통제다. "역할별 opus 월 N 토큰" 같은 상한은 기존 `quota` 그룹(LLM 사용 한도) 축이라 별 cycle.
- 위험도: **Critical(§12.3 인가 구조 변경)**. 완화: 스키마·마이그레이션 0(기존 테이블 재사용) · 기본 전 부여로 배포 무회귀 · 신규 권한은 운영 권한 묶음(관리 콘솔 접근과 무관) · fail-closed 기본.
- Verification: 단위 25 PASS · 전체 pytest rc=0 · ruff All passed · node --check OK.
- Cross-ref: MODIFY CHG-20260728T024258-model-access-rbac / test-runs.d/20260728T024258-model-access-rbac.md / SECURITY §28 / CONVENTIONS §10.6 / feature-0007 REPORT §7 R2.

## REV-20260728T025614-model-access-seed-fix [SKIPPED:live-root-cause-confirmed+session-policy-no-subagent] — PASS
- 대상: 모델 권한 seed SQL arity 수정 + 컬럼 길이 클립 + 호출부 격리. CHG-20260728T025614-model-access-seed-fix 정합.
- 리뷰 방식([SKIPPED] 사유): 근본 원인이 **라이브 로그 + 컨테이너 내 직접 호출 재현**으로 결정적으로 확정됐고(추정 아님), 수정은 파라미터 1개 바인딩 + 클립 2줄 + try/except 2곳이다. §18.8 subagent 패널은 세션 정책(Agent tool 미허용)으로 미수행.
- **배운 것(이번 cycle 의 핵심 교훈)**: 테스트 더블이 **실 드라이버의 계약을 흉내내지 않으면 단위 테스트가 통과 도장을 찍어준다**. 25개 테스트가 전부 green 이었는데 라이브에서 seed 가 한 번도 성공하지 못했다 — 더블이 SQL 문자열만 보고 arity 를 안 봤기 때문이다. 수정은 버그 자체보다 **더블에 그 검사를 심는 것**이 본질이다(그래서 arity 단정을 두 더블 모두에 넣었다).
- 자기 적대 검토:
  - *fail-open 설계가 결함을 가렸나?* 부분적으로 그렇다 — 403 폭주가 없어 즉시 드러나지 않았다. 그러나 대안(fail-closed)이었다면 이 버그가 **전 사용자 대화 403** 으로 터졌다. 설계는 옳았고, 부족한 것은 **seed 성공 여부의 능동 확인**이었다(POST-DEPLOY 체크리스트에 권한 row 카운트를 추가해 보완).
  - *격리가 실패를 숨기나?* try/except 는 예외를 삼키지만 stderr 에 `seed FAILED` 를 loud 하게 남기고, POST-DEPLOY 가 권한 row 수를 직접 센다. "조용한 skip" 은 남지 않는다.
  - *클립이 의미를 잘라 오해를 만드나?* Label 은 `모델 사용 — <label>` 로 짧고, Description 은 문장 끝이 잘릴 수 있으나 권한의 식별·판단은 Code/Label 로 하며 grid 는 Description 을 보조로만 쓴다. 1406 으로 seed 전체가 죽는 것보다 낫다.
- 위험도: Minor(§12.3) — 선행 Critical cycle 의 버그 수정. 인가 판정 로직·경계 무변경(seed 경로만).
- Verification: 단위 26 PASS · 전체 pytest rc=0 · ruff · ast.parse OK.
- Cross-ref: MODIFY CHG-20260728T025614-model-access-seed-fix / test-runs.d/20260728T025614-model-access-seed-fix.md / 선행 REV-20260728T024258-model-access-rbac.

## REV-20260728T031500-model-access-postverify [SKIPPED:post-deploy-live-evidence+docs-only] — PASS
- 대상: 배포 `8db72012` 의 모델 권한 RBAC 라이브 부여·해제 양방향 검증 기록 + `SECURITY §28.6` 신설.
- 리뷰 방식([SKIPPED] 사유): **코드 변경 0**. 산출물은 (a) 라이브 관측 사실, (b) 그 관측에서 드러난 기존 가드의 상호작용을 운영 규칙으로 옮긴 문서. 정본 적대 리뷰는 선행 REV-20260728T024258-model-access-rbac · REV-20260728T025614-model-access-seed-fix.
- **확정된 것**: ① 기본 전부 부여 무회귀 렌더 ② 역할 해제가 대상 모델에만 적용(`7/8`, 타 모델 `8/8` 유지) ③ 표시 필터 + `/api/ask` **403**, 동시점 sonnet **200** 대조로 **모델 단위 스코프** 확정 ④ 재부여 완전 복귀(`8/8` ×3, override 0). → 선행 REVIEW 들이 POST-DEPLOY 로 이관했던 시각·집행 게이트(§16.6) 충족.
- **새로 드러난 것(정직 표기)**: TASK-0300 권한상승 가드 × `model.access.*` = **관리자 자기 잠금 경로**. 결함이 아니라 기존 가드가 새 동적 그룹에 그대로 적용된 결과(=`product.access.*` 와 동일)이므로 **코드 변경 없이** `SECURITY §28.6` 운영 규칙으로 봉인. 완화하려고 가드에 예외를 두면 escalation 방어에 구멍이 생기므로 **의도적으로 하지 않았다**.
- **검증 방법의 한계(정직 표기)**: 집행 검증은 `일반 사용자` 역할에 소속 계정이 0명이라 **자기 계정 override** 로 대리 수행했다. 역할 경유 집행(계정 → 역할 → 권한)의 라이브 관측은 아니지만, 두 경로는 `_account_permissions` 의 동일 병합 맵으로 수렴하고 역할 쓰기 경로는 ②·④ 에서 DB 로 별도 확정했다.
- 위험도: **Minor(§12.3)** — 문서 전용, 동작 영향 0. 라이브 상태는 착수 전과 동일하게 원복됨.
- Cross-ref: MODIFY CHG-20260728T031500-model-access-postverify / test-runs.d/20260728T031500-model-access-pb0008.md / SECURITY §28.6·§28.7 / feature-0007 REPORT §7 (R1·R2 해소).
## REV-20260728T113819-usage-records-system [SKIPPED:session-policy-no-subagent] — PASS

CHG-20260728T113819-usage-records-system. §18.8 dispatch 키워드(UI/화면/API)에 해당하나 본 세션
정책상 subagent panel 미호출 — 대신 라이브 DB 실측 + PB-0008 로 대체 검증했다. Critical 아님
(읽기 전용 집계 확장 · 신규 RBAC 0 · 마이그레이션 0).

### D1. 시스템 기록을 "여집합" 으로 정의한 이유

`conversation_id IS NULL OR LIKE '__%'` 같은 **열거식** 정의도 가능했으나, 대화 목록이 실제로
쓰는 필터는 `INNER JOIN + owner NOT NULL` 이라 열거식과 미묘하게 어긋난다. 실측에서 그 틈이
드러났다 — 예약 sentinel `__ask_worker__` 가 `core_conversations` 에 **실제 행으로 존재**하고
(topic 까지 있음, owner NULL), 반대로 삭제된 대화 id 를 참조하는 usage 도 있다. 따라서
`NOT(joinable AND owner NOT NULL)` 라는 **정확한 여집합**으로 정의해 두 목록의 합이 항상 차트
막대와 일치하도록 했다. 라이브 검증: 897 + 14,476 = 15,373 = 전체(누락·중복 0).

### D2. 계정/일반 역할 클릭에서 시스템 사용분을 **제외**한 이유

시스템 호출은 계정에 귀속되지 않으므로 특정 계정 몫에 섞어 보이면 그 계정이 쓴 것처럼 오도한다.
`(시스템)` 역할과 모델/일자(무-귀속 차원) 클릭에서만 노출한다. 이 규칙은 백엔드에 고정하고
프론트가 재해석하지 않는다.

### D3. target→데이터소스 해소를 "추측하지 않는다"

`llm_usage.target` 에는 데이터소스 차원이 없다(0032 설계). 3 소스 union 으로 역해소하면 실측
8,399 distinct target 중 유일 해소가 대략 60% 대이고 나머지는 dev/qa 동명 스키마로 **모호**하다.
모호할 때 임의로 하나를 고르면 사용자를 **엉뚱한 데이터소스로 착지**시키므로, 후보 2+ 는
`scope_ambiguous` 로 표시하고 화면까지만 이동한다(행에 "(데이터소스 여럿 — 화면까지 이동)" 명시).
근본 해소는 `llm_usage` 에 데이터소스 컬럼을 추가하는 별도 cycle 이 필요 — 본 cycle 범위 밖으로
남기고 REPORT §후속에 기록.

### D4. nav 를 백엔드 SSOT 로 둔 이유

`task → 화면` 매핑을 프론트에 두면 신규 AI 작업이 생길 때 두 곳을 동기화해야 하고, 누락 시
"클릭해도 아무 일이 없는" 조용한 회귀가 된다. `shared/model_catalog.USAGE_TASK_NAV` 한 줄 추가로
목록·내비게이션에 동시 편입되도록 하고, 미등록 task 는 taxonomy self-surface 와 같은 사상으로
AI 운영 현황 폴백을 준다.

### D5. 응답을 `items` + `system_items` 로 **분리**(단일 배열 통합 아님)

기존 `items` 스키마를 그대로 두면 profile 모달·기존 소비자 회귀가 0 이고, 프론트 배포 순서와
무관하게 호환된다(구 프론트는 새 필드 무시, 신 프론트는 필드 부재를 빈 배열로 폴백). 표시 단계의
통합(한 표·토큰 순 병합)은 프론트에서 수행한다.

### 라이브에서 잡은 결함 2건 (in-cycle 수정)

- **모호 신호 유실**: `scope_ambiguous` 를 record 최상위에만 넣고 `nav` 에 싣지 않아, nav 만 읽는
  프론트에서 "데이터소스 여럿" 안내가 조용히 사라졌다(107행이 무표기). → nav 에 동반 + 회귀 가드 테스트.
- **깨진 대화 링크 위험**: 비-sentinel actor 를 무조건 대화로 링크하면 **삭제된 대화**로 404 를
  보낸다. → `bool_or(c.conversation_id IS NOT NULL)` 로 실재 여부를 판정해 3분기.

### 리스크·한계

- `_USAGE_SYS_LIMIT = 200` 상한 — 초과 시 truncated 안내. 대화 목록 상한(200)과 동일 규모.
- 해소 질의는 표시분(≤200행)의 스키마 IN 목록으로 제한 — 유계 비용(실측 14ms).
- 관리자 대비 대비비는 실측 PASS 이나, **다크 테마 대비는 미실측**(본 콘솔은 라이트 기준 운용).

## REV-20260728T115900-usage-records-postverify [SKIPPED:post-deploy-live-evidence+frontend-css-only] — PASS

CHG-20260728T115900-usage-records-postverify. frontend CSS 2줄 + POST-DEPLOY 실측 종결이라
§18.8 panel 미호출(라이브 증거로 대체).

### 왜 `width:100%` 만으로 풀리지 않았는가 (근본 원인)

1차 수정에서 모달을 반응형(`min(1240px,96vw)`)으로 넓히고 부수 열에 `width:1%` 를 줬는데도
본문 열이 239px 에 머물렀다. 원인은 테이블이 **두 클래스를 동시에 보유**(`admin-usage-table`
`usage-conv-table`)하고, 공용 쪽에 `max-width: 640px` 이 걸려 있던 것. auto table-layout 에서
max-width 가 콘텐츠 최소폭보다 작으면 테이블은 **min-content 로 수축**하고, 그 상태에서는
"남는 폭"이 존재하지 않아 `width:1%`/`width:100%` 배분이 무의미해진다. 즉 폭 배분 규칙이 아니라
**상한 해제**가 선행돼야 했다.

교훈: 공용 테이블 클래스를 재사용하는 화면에서 열 폭이 이상하면, 배분 규칙보다 **상속된
`max-width`/`min-width` 상한**을 먼저 의심한다. 실측 없이 배분 규칙만 덧붙이면 원인이 남는다.

### 선행 cycle 미확정 2건의 사유가 실제로 환경 아티팩트였음

배포본은 `inject_asset_stamp.py` 가 HTML entry 와 `graph/*.js` 의 import specifier 에 **동일
stamp**(`7fc11a708399`)를 주입해 admin.js 가 단일 인스턴스로 로드된다(라이브 확인). 선행 cycle 의
`docker cp` QA 는 이 주입을 우회해 entry 와 import 가 갈라졌고, 캐시된 구 인스턴스가 이벤트를
처리해 신코드가 반영된 것처럼 보이지 않았다. 배포본에서 3분기가 즉시 정상 동작한 것이 이를 확증.

교훈(운영): 미머지 static QA 를 `docker cp` 로 할 때 **JS 는 stamp 재주입 없이는 신뢰할 수 없다**.
CSS 는 단일 파일이라 안전하지만, ES module 은 순환 import 의 고정 `?v=` 때문에 이중 인스턴스가 된다.
## REV-20260728T113000-graph-noise-reduction [SKIPPED:session-policy-no-subagent] — PASS
- Date: 2026-07-28 · Session: `ai/claude/feature-0003-graph-noise-reduction` · CHG-20260728T113000-graph-noise-reduction
- 리뷰 방식([SKIPPED] 사유): 본 세션 사용자 환경 정책상 **Agent(subagent) tool 미허용** — §18.8 검증 패널을 호출할 수 없다(직전 cycle 들과 동일 제약). 대체로 **자체 적대 검토 H1~H9** 를 수행하고 그 실측 결과를 아래에 남긴다. 대상은 frontend-only·비파괴 표시 변경(Minor §12.3)이며 롤백은 static 4파일 revert.
- **자체 적대 검토(H1~H9, 전부 실측)**:
  - **H1 툴팁 문자열 주입** — `_metaSecHelp` 는 `&<>"` 를 이스케이프하고 `title`·`aria-label` 양쪽에 같은 escaped 값을 쓴다. 헤드리스 유닛으로 `a"b<c&d` → `a&quot;b&lt;c&amp;d` 확인(속성 탈출 없음). 주입되는 tip 은 전부 코드 리터럴이라 사용자·DB 입력 경로 없음.
  - **H2 회귀 단정이 무력한가** — 초판 단정("안내 문구가 존재")은 **문단으로 되돌려도 통과**한다. 접근 경로 단정(툴팁 존재 ∧ `admin-meta-detail-note` 부재)으로 교체 + "툴팁으로 보존됨" 4종을 함께 단정해 *정보 소실* 반대 방향도 막았다.
  - **H3 커밋 바가 필요한데 숨는 경우** — `.has-pending` 은 `refreshPendingUI()` 가 `total > 0` 로만 붙이므로 pending 존재 시 항상 노출. 라이브 왕복 실측(0건 `none` → 1건 `flex`+`has-pending`+`1건 pending`+apply 활성)으로 확인. 다른 pane 의 독립 저장 컨트롤(`metadataCancelBtn`·감사/보관 `적용`)은 커밋 바와 무관해 영향 없음.
  - **H4 커밋 바 높이에 의존하는 레이아웃** — `adminCommitBar` 참조는 `classList.toggle` **1곳뿐**(`offsetHeight`·`getBoundingClientRect` 사용 0). `@media print` 에도 관련 규칙 없음. 숨김이 다른 계산을 깨뜨리지 않는다.
  - **H5 죽은 CSS** — 안내 span 제거로 `.admin-meta-ai-pop-foot .admin-meta-graph-muted` 가 매칭 0 이 됨 → 삭제(주석으로 사유 보존). `.admin-meta-detail-note` 규칙은 메타데이터 pane + 절단 경고가 계속 쓰므로 유지(`verify_metadata_list_detail.mjs [C3]` 가 이 규칙 존재를 단정 — PASS 확인).
  - **H6 AI box 문구 축약이 정보를 지우는가** — 권한 없는 사용자에게 이전 문구는 "결과 없음 + 권한 있으면 시작 가능"을 알렸다. 축약본은 상태(`분석 결과 없음`)만 남긴다. **권한 없는 사용자에게는 애초에 실행 컨트롤이 미렌더**라(=시작할 수 없음) 안내가 행동으로 이어지지 않는 정보였다고 판단. 실행 가능한 사용자에게는 `✨ 능동 분석` 버튼 `title` 이 같은 내용을 담는다.
  - **H7 empty-state 축약이 온보딩을 해치는가** — 제거한 클릭/더블클릭/우클릭·읽기전용 설명의 **정본은 ❓ 도움말 오버레이**이며, 그 오버레이는 **첫 진입 시 자동 1회 노출**(localStorage `metaGraphHelpSeen`)된다. 즉 처음 오는 사용자는 이미 전문을 보고, 두 번째부터는 안 봐도 되는 정보였다 — 사용자 요구("한 번 인지한 후 더 확인하지 않아도 되는 설명")의 정확한 대상.
  - **H8 제거 문구를 단정하는 외부 테스트** — 전 테스트 grep 결과 본 cycle 이 갱신한 2개 하네스 외 참조 0. `verify_metadata_scope_single_ds.mjs` 15 PASS, `verify_metadata_list_detail.mjs` 25 passed/3 failed 는 **main baseline 과 실패 항목·개수가 동일**(B4·B4·B5, pre-existing).
  - **H9 ES module 이중 인스턴스화** — 라이브 QA 스테이징에서 소스의 `?v=dev` import specifier 를 그대로 넣으면 baked 스탬프와 달라 `admin.js` 가 두 번 평가된다(AGENTS.md §13.1 경고 사례). 전 static 자산의 스탬프를 단일 값(`?v=qa113855`)으로 재기입해 회피했고, 콘솔 에러 0 으로 확인. **소스 자체는 placeholder 를 유지**(빌드 주입 계약 불변).
- **판단 원칙 — 삭제가 아니라 이동**: 사용자 요구는 "제거 **혹은** hover 툴팁 전환" 이었다. 정보를 실제로 없애면 처음 쓰는 사람이 막히므로, 기본 전략을 *상시 표면 → 요청 시 표면(hover `title`)* 이동으로 잡았다. 실제 삭제는 **다른 곳에 정본이 있는 중복**에만 적용했다 — (a) empty-state 의 클릭/더블클릭/우클릭 안내(정본 = ❓ 도움말 오버레이), (b) 제품 카테고리 일반 케이스 문단(정본 = 카드 헤더 배지 + 범례 탭의 밴드 항목).
- **어디를 건드리지 않았는가(의도)**: ❓ 도움말 오버레이와 범례 3탭은 **사용자가 능동적으로 여는** 표면이라 "한 번 인지 후 안 봐도 되는데 계속 보인다" 는 마찰이 성립하지 않는다. 축약하면 오히려 이관 대상(툴팁·도움말)의 정본이 약해진다. 절단 경고(`amgr-trunc-note`)도 "무음 절단 금지" 계약(리뷰 MAJOR-1)이라 제거 대신 1줄 압축만 했다.
- **ⓘ 어포던스를 붙인 이유**: `<h4>` 자체에 `title` 만 걸면 툴팁이 **발견 불가능**하다(hover 유인이 없음). 11px·opacity .55 의 ⓘ 는 문단 4줄보다 압도적으로 적은 시각 비용으로 "여기 더 있다"를 알린다. 접근성은 `tabindex=0` + `aria-label` 로 보완 — native `title` 은 키보드·스크린리더에서 불균일하다.
- **커밋 바 — 범위가 그래프 뷰보다 넓다(정직 표기)**: 사용자가 지목한 것은 그래프 뷰 하단의 `0건 pending` 바지만, 이 바는 **관리 콘솔 전역** 요소다. 두 선택지를 놓고 비교했다 — ① pane 별 화이트리스트로 그래프 뷰에서만 숨김, ② pending 0 이면 전역 숨김. ②를 골랐다: `0건 pending` + 비활성 버튼 2개는 **어느 pane 에서도** 정보·동작이 0 이고, ①은 "편집 가능한 pane" 목록을 코드에 하드코딩해 pane 추가 때마다 썩는다. ②는 unsaved-changes 액션 바의 보편 관습이며 CSS 1규칙이라 롤백이 자명하다. 상시 상태 표시는 사이드바 `#adminPendingSummary` 가 이미 담당하므로 "지금 저장할 게 있나" 를 잃지 않는다.
- **JS 를 건드리지 않은 것도 의도**: `refreshPendingUI()` 가 이미 `.has-pending` 을 토글하고 있었다. 여기에 `style.display` 조작을 추가하면 상태 소스가 둘로 갈라진다 — CSS 가 클래스 하나만 읽게 두면 JS 회귀 표면이 0 이다.
- **라이브에서 잡은 결함 1건**: 툴팁 문자열을 템플릿으로 합치면서 `${...}을` 로 조사를 고정해 `함수·프로시저**을**` 이 됐다(종성 없는 명사 → `를`). 헤드리스 단정은 통과했고 **PB-0008 실화면 판독에서만** 드러나 분기별 조사 하드코딩으로 정정했다. 문자열 조립 시 한국어 조사는 앞 명사 종성에 종속된다는 점을 재확인.
- **검증 방법의 한계(정직 표기)**: ① native `title` 툴팁은 브라우저 OS 레이어에 그려져 **스크린샷으로 캡처되지 않는다** — 툴팁 *내용*은 DOM 속성 실측(라이브 eval 로 전문 확인)으로, 툴팁 *렌더*는 브라우저 보장에 의존한다. 레이아웃(픽셀 클래스) 변경은 스크린샷으로 확인했다(§16.6 변경-클래스 분기 준수). ② PB-0008 은 라이브 컨테이너에 `docker cp` 로 자산을 스테이징해 수행했고, 검증 중 **다른 세션의 롤링 배포가 3회 발생**해 스테이징이 두 번 덮였다 — 그때마다 재적용 후 재측정했고, 최종 판독은 모두 패치가 서빙되던 시점(`?v=qa113855`)의 것이다. 배포 후 main 기반 재확인은 deploy_scope 사후 확인으로 남긴다.
- **회귀 방지 설계**: 새 단정은 문구가 아니라 **접근 경로**를 본다(`.amgr-sec-help` title 존재 + 본문 `admin-meta-detail-note` 부재). 문구만 단정하면 문단으로 되돌려도 통과하고, 경로를 단정하면 회귀가 바로 FAIL 한다. 동시에 "툴팁으로 보존됨" 4종을 함께 단정해 *제거로 정보가 소실되는* 반대 방향 회귀도 막는다.
- 위험도: **Minor(§12.3)** — 프론트 표시 전용, 백엔드·API·RBAC·스키마·데이터 fetch 무변경, 롤백 = static 4파일 revert.
- Cross-ref: MODIFY CHG-20260728T113000-graph-noise-reduction / FUNCTION REQ-20260728-graph-noise-reduction(AC-GNR-1~6) / test-runs.d/20260728T113000-graph-noise-reduction.md / 선행 REQ-20260716T114705 ③.

## REV-20260728T121500-usage-records-hint-tooltip [SKIPPED:frontend-cosmetic-only+post-deploy-live-evidence] — PASS

CHG-20260728T121500-usage-records-hint-tooltip. 표시 전용 변경(렌더 1블록 제거 + dead CSS 삭제).

- **정보 손실 없음**: 제거한 두 번째 줄의 두 정보(이동 경로 · 데이터소스 모호)를 모두 `title` 로
  옮겼다. 특히 "화면까지만 이동" 은 사용자를 엉뚱한 데이터소스로 착지시키지 않기 위한 **정직 표기**라
  그냥 삭제하면 안 되고 툴팁으로 보존해야 한다.
- **접근성**: 이동 트리거는 여전히 `<button>` 이라 키보드 포커스·Enter 로 동작하고,
  `title` 은 포커스 시에도 노출된다. 링크 여부는 색·밑줄(hover)로 시각 전달된다.
- **이중 escape 동반 수정**: `where = esc(path_label)` 를 title 에서 다시 `esc()` 해
  `&amp;gt;` → 화면에 `&gt;` 로 보이던 결함. 표시 문자열은 **한 경계에서 한 번만** escape 한다는
  규칙으로 정리했다.
- **pre-deploy 라이브 미검증 사유**: `docker cp` 스테이징에서 Chrome 이 동일 URL 의 **컴파일된 ES
  모듈**을 계속 재사용해(HTTP 캐시 강제 갱신에도) 신 렌더가 관측되지 않았다. 배포는 새 asset
  stamp = 새 모듈 URL 이라 이 문제가 없다(직전 cycle 에서 POST-DEPLOY 즉시 정상 관측 확인).
  따라서 본 cycle 도 POST-DEPLOY 검증으로 확정한다.

## REV-20260728T162844-graph-hover-flow [CODEX:graph-hover-flow] — PASS

CHG-20260728T162844-graph-hover-flow. 프론트엔드 렌더 전용(백엔드/RBAC/스키마/엔드포인트 0).

- **Related TASK**: feature-0003-agent-web-ui
- **Trigger**: UI/screen/layout 키워드 매칭 (§18.8 dispatch → ux, design) + code change
- **Source**: `codex review --uncommitted` (§18.8.1 #2 경량 경로)
- **Timestamp**: 2026-07-28T16:28:44+09:00
- **Verdict**: PASS (P1 GATE 0건 — "현재 diff에서 확실히 수정이 필요한 버그는 확인되지 않았습니다")
- **Human Approval Needed**: no

**검증 채널 선택 근거 (§18.8.2)**: 본 세션에는 하네스 수준의 "요청 없이 Agent tool 을 호출하지 말라"
상위 지시가 걸려 있다. §18.8.2 의 *상위 우선순위 지시 carve-out* 에 따라 그 지시를 우선하되 **검증을
건너뛰지 않고**, 도구 제약과 무관한 채널로 수행했다: (a) `codex review --uncommitted` 적대 리뷰,
(b) 기계적 회귀 대조(구현 이전 어댑터 vs 신 어댑터 동일 시나리오 실행), (c) PB-0008 실 브라우저
라이브 검증. dispatch 표가 지정한 ux/design 도메인은 (c) 의 실화면 관측이 경험적으로 덮는다
(정적 렌더 + 인터랙션 결과 + 애니메이션 프레임 대조). subagent 패널 자체는 미수행 —
`[SKIPPED:tool-restricted:ux,design-subagent]` 로 미검증 범위를 명시한다.

**근본 원인 (왜 "하나의 관계선만" 이었나)**: 같은 두 노드 사이의 관계선은 **1:N** 이다.
① 왕복 REFERENCES 는 곡률이 진행방향 왼쪽 고정이라 A→B 와 B→A 가 반대편 호(§83 A2, `curveMin=5` 는
"근접 노드 왕복선도 반드시 갈라지게" 하려는 하한), ② ROUTINE_USES 는 집계 키에 `relation_type` 이
포함돼 읽기/쓰기가 별개 선(§83 C1). 그런데 hover spec 은 `[self끝점, 상대]` 순서라 **어느 쪽이
source 인지** 담지 못했고, `_edgeStyleBetween` 은 `e.source===sid&&e.target===tid` 와 역방향을
**한 루프에서 먼저 만나는 쪽**으로 반환했다. 즉 방향도 종류도 판별 축이 아니었다.

**자체 적대 검토 (H1~H7)**

- **H1 — 순위가 뒤바뀌면?** 방향과 종류 중 무엇이 1순위인가가 정확성을 가른다. 왕복 REFERENCES 는
  방향만이, 루틴 읽기/쓰기는 종류만이 판별 축이다. 둘을 같은 가중치로 두면 한쪽이 깨진다.
  점수식을 `방향(2) > 종류(1)` 로 고정하고, `relType` 이 주어졌는데 정방향 엣지의 종류가 다르면
  (score 3) 역방향+종류일치(score 2)보다 여전히 우선하게 했다 — 실데이터에서 ROUTINE_USES 는 항상
  Routine→Table 이라 이 조합은 발생하지 않지만, 발생해도 방향이 이긴다.
- **H2 — 역방향 정규화의 비대칭.** 곡률 부호만 뒤집고 화살표 키를 그대로 두면 호는 맞는데 **흐름이
  거꾸로** 흐른다. `startArrow`/`endArrow` 를 함께 교환해 `(sid→tid)` 프레임을 완성했고,
  테스트 M7 이 "부호 반전 + 키 교환 + 그래서 흐름도 역류" 3단을 함께 잠근다.
- **H3 — rAF 누수.** hover 는 행마다 발생하므로 정지 경로 누락 하나가 곧 다중 루프다. 4경로
  (hover 해제 · 새 hover 선점 · `draw()` 재빌드 · `destroy()`)에서 `_stopHoverFlow()` 를 **먼저**
  호출하고, 세대 토큰(`this._hoverFlow !== state`)으로 이미 예약된 프레임도 자진 종료시킨다.
  `draw()` 는 좌표가 바뀌어 폴리라인이 stale 이 되는 지점이라 특히 중요하다(분리된 Graphics 에
  계속 페인트하면 보이지 않는 채로 매 프레임 `_render()` 를 유발).
- **H4 — 기존 대시 호출부 회귀.** `dashPolyline` 에 3번째 인자를 더했다. 미지정 시 `phase` 는
  falsy 라 위상 소비 블록 자체를 건너뛰므로 종전 경로와 동치이고(P1 이 이를 잠근다), `dash` 합이 0
  인 병리 입력에서는 `T=0 → p=0` 으로 무한루프에 빠지지 않는다.
- **H5 — XSS.** 새 `data-*` 값은 전부 기존 `esc()`(`& < > "`)를 거치고 속성은 큰따옴표로 감싼다.
  `data-rel-type` 은 삼항식이 만든 리터럴(`"write"|"read"`)이라 외부 입력이 닿지 않는다.
- **H6 — 미렌더 끝점.** 컬럼이 미렌더면 조상(테이블→스키마 카드)으로 승격되는 기존 동작은 그대로다.
  승격 결과 양끝이 **같은 요소**가 되면 연결선 대신 노드 링만 남는다(방향 정보가 의미를 잃는 구간) —
  종전과 동일한 graceful 동작이며, 라이브에서는 테이블 2개가 별개 노드라 문제되지 않았다.
- **H7 — 알려진 한계(미수정, 의도).** 강조 기하는 hover 시점 zoom 으로 model 좌표에 bake 된다.
  hover 중에 줌을 바꾸면 강조선 굵기만 화면 기준에서 어긋난다(본선은 `_syncEdgeZoom` 이 재페인트).
  hover 는 커서가 우측 패널에 있는 transient 상태라 실사용에서 겹치지 않고, §85 의 "페인트 시점 zoom
  bake" 어휘와 일관되므로 추가 리스너를 달지 않았다.

**연출 선택 근거**: 흐름을 "움직이는 대시"로 표현하고 색은 흰색(본선 파랑 위 대비)으로 두었다.
헤일로(α0.16)를 깔아 대시 사이 구간에서도 경로가 끊겨 보이지 않게 했고, 화살촉은 정적으로 유지해
방향이 애니메이션 프레임에 의존하지 않게 했다(모션 민감 사용자·정지 캡처에서도 방향이 읽힌다).
`prefers-reduced-motion` 에서는 rAF 를 아예 걸지 않고 정적 대시 + 화살촉만 남긴다.

**라이브 근거**: PB-0008 실 Windows Chrome 150 — 참조함/참조받음 화살촉 반전 + 강조 픽셀 차 441px,
읽기/쓰기 대상선 분기 3,517px, 같은 hover 420ms 프레임 차 151px(대시 진행), 페이지 에러 0.
`docs/test-runs.d/20260728T162844-graph-hover-flow.md` · `docs/evidence/pb0008-graph-hover-*-20260728.png`.

## REV-20260728T173500-routine-column-edges-postdeploy [SKIPPED:post-deploy-live-evidence+no-code-change] — PASS
- Related TASK: feature-0003-agent-web-ui
- Trigger: POST-DEPLOY 재확인 cycle — 코드·자산 변경 0(docs/evidence only), 검증 자체가 산출물
- Timestamp: 2026-07-28T17:35:00+09:00
- Verdict: PASS
- Human Approval Needed: no

**왜 panel 대신 라이브 증거인가**: 본 cycle 은 새 코드를 만들지 않는다. 검증 대상은 "이미 머지·배포된
코드가 **실 데이터**에서 의도대로 동작하는가" 이며, 그 판정 근거는 정적 리뷰가 아니라 실 데이터소스
재-introspect 후의 라이브 관측이다. 따라서 §18.8 dispatch 표의 code-change 경로가 아니라 라이브 증거로
대체하고, 그 사실을 본 entry 에 명시 트레이스로 남긴다(§18.8.2 4번 — 채널 선택 근거 기록).

**본 cycle 이 실제로 닫은 위험**: 선행 cycle 의 자체 적대 검토가 지적한 최대 잠복 결함은
`metadata_graph.routine_refs_signature` 가 `cols` 를 서명에 담지 않으면 **코드·단위테스트·시각검증이
전부 통과해도 라이브에서만 기능이 죽는** 경로였다(같은 날 병합된 cyvol 최적화가 서명 동일 시
`ROUTINE_USES` 재작성을 통째로 생략). 이 경로는 정의상 배포 후 실데이터에서만 반증 가능하다 —
backfill 후 AGE `ref_columns` 엣지가 29 → 2,725 로 실제 증가했고 화면까지 도달했으므로, 서명 수정이
의도대로 backfill 경로를 열었음이 라이브로 확인됐다.

**혼재는 결함이 아니다(재확인)**: 라이브에서 `websessionkey` 의 참조 컬럼 5개 중 컬럼 정점이 존재하는
것은 `SessionKey` 1개뿐이라, 컬럼선 1 + 테이블 폴백선 1 이 같은 테이블에 공존한다. 이는 (a) 컬럼 정점이
`column_descriptions` SSOT 에서만 오고 (b) 확정하지 못한 참조를 컬럼에 그리지 않는다는 보수적 채택
기준(사용자 결정)의 **직접적 귀결**이다. "없는 관계를 사실처럼 보여주지 않는다"를 커버리지보다 앞에
둔 선택을 라이브 화면이 그대로 보여준다.

**한계(미해소, 의도)**: 미도달 datasource(사내 VPN 경로 밖)는 이번 backfill 에서 채워지지 않았고
per-(ds,DB,schema) 오류로 리포트만 남는다(비차단 설계). 도달 가능 시점의 backfill 또는 worker cadence
로 자연 수렴하며, 별도 작업으로 다루지 않는다.

**라이브 근거**: PB-0008 실 Windows Chrome 150 — 9 시나리오 PASS(컬럼선 끝점 model (2142,449) vs
테이블 끝점 (2195,415) 분리 실측 · 읽기/쓰기 한 컬럼 공존 · 상세 패널 `✎` 5건 · 콘솔 에러 0).
`docs/test-runs.d/20260728T173500-routine-column-edges-postdeploy.md` ·
`artifacts/shared/win-browser-shots-routine-coledges-postdeploy/` (6매).
## REV-20260728T191126-model-pick-early-cid [SUBAGENT:inline-adversarial] — SHIP

- **Trigger**: `contract` keyword matched / 계약(요청 body `model` 필드 동봉 여부) 변경 → backend + security + qa.
  UI 표면화(토스트) 동반이나 레이아웃 변경 0 이라 ux/design N/A.
- **채널**: 인라인 자기 적대검증. 본 세션은 Agent(subagent) tool 사용이 제한돼 §18.8 subagent 패널을
  띄우지 못했다 — §18.8.2 판정 1(사용자 지시 우선)에 따라 제약 없는 채널로 대체하고, 아래 각 지적을
  **코드·라이브 데이터로 직접 반증**했다(추정 기각 금지). 선례: `FR-readonly-query-shapes-overblock`
  (세션 한도로 패널 조기종료 → 인라인 자기검증 완료).
- **대상**: CHG-20260728T191126-model-pick-early-cid (`src/static/app.js` +47행, 테스트 +108행).

### security 렌즈

- **S1 승계가 타 대화·타 계정 선택을 누출하나 → REFUTED.** 승계 조건은 `prev === ""`(pending, 즉 아직
  어느 대화에도 귀속되지 않은 현재 사용자 선택) 또는 `prev === pendingKey`(현 세션 sentinel) 뿐이다.
  다른 실 cid 귀속은 거부하며 회귀 테스트 E5 가 이를 고정한다. 계정 경계는 기존
  `_resetComposerModelSelection`(로그아웃 호출)이 계속 담당한다.
- **S2 승계로 권한 없는 모델이 전송돼 403 회귀가 나나 → REFUTED.** 선택기 표시 목록은 `/api/session`
  이 `_filter_models_for_account_access`(web_context.py:3307)로 이미 계정 인가 범위로 필터한다 →
  고를 수 있는 값은 인가된 값뿐. RBAC 이 런타임에 축소된 경우의 403 은 의도된 fail-closed 이며,
  종전(조용한 haiku 실행)보다 정직하다. 서버 게이트(conversations.py:2761) 무변경.
- **S3 토스트 문자열 XSS → REFUTED.** `showToast`(app.js:752-754)는 `textContent` 대입이며 모델 라벨은
  서버 카탈로그 값이다. 마크업 경로 없음.

### backend/correctness 렌즈

- **C1 승계가 "'+ 새 대화'는 haiku" 계약을 깨나 → REFUTED.** 미선택 상태의 귀속은 `null` 이고 승계
  대상이 아니다(E3/E3b 고정). 사용자가 **명시로 고른** 경우만 그 선택이 살아난다 — 기본값 정책은 불변.
- **C2 pendingSentinel 초기화와의 순서 위험 → 실재, 구현에서 해소.** 첨부 경로는 `state.pendingSentinel
  = null` **이전에** 승계해야 sentinel 키 매칭이 유효하다. 구조 계약 S10 이 소스 오프셋으로 이 순서를
  고정한다(향후 리팩터가 순서를 뒤집으면 테스트 실패).
- **C3 hydration 과의 상호작용 → 정합 확인.** 승계 후 `_modelHydrationShouldSkip` 이 (a) pick 이 더
  최근이면 사용자 선택 유지, (b) hydration 이 더 최근이면 이 대화 KV(승계로 저장된 sonnet)를 복원 —
  **두 분기 모두 sonnet** 이라 결과가 일치한다. 수정 전에는 KV 가 비어 `selectedModel=null` 로
  화면까지 haiku 가 되던 경로였다(증상 "즉시 폴백"의 화면 측 기전).
- **C4 sendPrompt 경로 승계가 본 전송을 바꾸나 → 아니다(의도).** 그 지점은 `askBody` 확정 후라 본
  전송에 무영향이며, hydration 전 연속 전송의 mismatch 예방이 목적이다. 주석에 명시.
- **C5 중복/경합 진입 → REFUTED.** 첨부 경로는 `lazyConvCreating` 가드로 중복 생성이 차단되고, 승계는
  `activeConversationId` 대입과 같은 동기 블록에 있어 await 경계를 넘지 않는다.

### qa 렌즈

- **Q1 E1("결함 재현")이 승계 삭제를 잡지 못한다 → 인정, 설계상 분업.** E1 은 `_shouldSendModelField`
  전제를 고정할 뿐이고, 승계 호출 자체의 존재는 구조 계약 **S9**(전환 지점 수 == 승계 호출 수)가
  강제한다. 새 전환 지점이 승계 없이 추가되면 S9 가 불일치로 실패한다 — 회귀 가드의 정본은 S9.
- **Q2 `console.warn` 상주 → 의도.** C 가드는 "미봉인 신규 경로" 진단용이며 사용자 표면화(토스트)와
  분리된 흔적이다. 무음이 이 결함을 6주간 숨긴 원인이라 로그를 남기는 편이 낫다.
- **NIT 인접 JS 스위트 실패 6건**은 main baseline 과 문자열까지 동일함을 대조 실행으로 확인(pre-existing,
  jsdom 미설치 등 환경 제약). 본 변경 무관.

### 판정

**SHIP** — BLOCKING 0. 변경면이 좁고(FE 상태 이관 + 감지 가드) 서버 계약·보안 경계·기본값 정책 모두
불변이며, 근본이 라이브 데이터로 확정됐다. **잔여 리스크는 하나**: 코드/유닛은 "선택이 전송에 실린다"
까지만 증명하고 "실제 사용자 대화에서 sonnet 으로 실행됨"은 배포 후 실측분이다(TEST.md DEFERRED,
정본 = `llm_usage.model` + `kv model:<acct>`).
## REV-20260729T010301-doc-sync-rn-0729 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-07-28 블록에 6항목 append(관계도 UX·사용 기록·모델 권한·자체 점검) doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(기존 2026-07-28 블록 3→9 items append·summary 증강·generated 불변) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(abcb7d68·351ed406 선례 동일 토큰).
- **검증**: `node --check` PASS · vm 구조검증(releases[0] 2026-07-28 items 3→9·releases[1] 2026-07-27 7항목 보존·releases[2] 07-24 보존·스키마·enum·내부용어 누출 0). 6항목 전부 owning POST-DEPLOY PB-0008 라이브검증(역할배지 2b9693c7·이웃깊이 0bff005e·hover 43efe182/29ceb823·상세hover fb253fe3·클러스터스크롤 9b16b0c0/a36c16ed/429e8c04·라벨LOD 8008402d·헤더라벨 b2f062cc·함수관계선 5a6110a9·사용기록 f3cfc809·모델권한 fcf22ceb·자체점검 6582c69b). 릴리즈노트 render 테스트 jsdom 미설치로 미실행(render 로직 미변경).
- **적대검증**: ULTRACODE wf_63a962eb R1(3-타깃 analyze→타깃-스코프 verify) — RN MAJOR 1(item3 좌우 오귀속 '왼쪽 스키마 목록'→우측 aside, admin.html:847·baedc78b 근거)·MINOR 1(item5 '즉시 반영'→pending→적용) 적발, 오케스트레이터 정본 독립 재검증 후 교정 반영.
- **cache-buster**: `?v=dev` 고정(빌드 자동주입·index/admin 편집 0·수동 bump 폐지 ITEM-09; wrapper 헤더 수기 bump 지시는 07-12 이전 regime 부적용).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260729T113000-model-pick-postdeploy [SKIPPED:post-deploy-live-evidence+no-code-change] — PASS
- Related TASK: feature-0003-agent-web-ui / 20260729T1130-model-pick-postdeploy
- Trigger: POST-DEPLOY 실측 cycle — 실행 코드·자산 변경 0(docs/evidence only), 검증 자체가 산출물
- Timestamp: 2026-07-29T11:30:00+09:00
- Verdict: PASS
- Human Approval Needed: no

**왜 panel 대신 라이브 증거인가**: 본 cycle 은 새 코드를 만들지 않는다. 검증 명제가 "이미 배포된 코드가
실제 사용자 시나리오에서 의도대로 실행되는가"이고, 그 판정 근거는 정적 리뷰가 아니라 라이브 원장
(`llm_usage.model` + `kv model:<acct>`)이다. §18.8 dispatch 표의 code-change 경로가 아니라 라이브 증거로
대체하며 그 선택 근거를 여기 남긴다(§18.8.2 4번).

**이 Run 이 닫은 위험**: 선행 cycle 의 증명 범위는 "고른 모델이 요청에 실린다 + 미동봉이면 표면화된다"
까지였다(코드·단위테스트). "실제 대화가 고른 모델로 **실행**된다"는 정의상 배포본 라이브에서만 반증
가능하고, 바로 그 미검증분이 사용자 재보고와 겹쳐 있었다. 본 Run 이 그 구간을 닫았다.

**관측 채널을 먼저 고정한 이유**: 이 결함은 "화면은 맞고 실행이 다름"이 정의다. 따라서 화면을 근거로
쓰면 검증이 성립하지 않는다. `fetch` wrap(요청 본문 원문) · `showToast` wrap(경보 발동 여부) · 전역
`state` 스냅샷 3중 계측을 깐 뒤 조작을 시작했고, 최종 판정은 브라우저가 아니라 PG 원장에서 냈다.

**결과**: 전 구간 PASS — 모델 선택 직후 `_modelPickedForConvId=""`(결함 전제 재현) → 첨부 업로드가
early-cid `...2e511059` 를 발급하며 **귀속 승계**(구버전이면 `""` 잔류) → 전송 본문 `model="claude-sonnet-4"`
동봉 → `llm_usage` id 69372 `model=claude-sonnet-4` / `resolved_model=claude-sonnet-4-chat`(강등 0) +
`kv model:1=claude-sonnet-4`(행 생성). 무음 강등 경보 미발동(C lever 오탐 0).

**사용자 재보고의 귀속 확정(적대적 자기검증)**: "여전히 폴백된다"를 액면 그대로 받으면 봉인이 실패한
것이 되므로, 먼저 그 주장을 깨려 시도했다 — 재현 대화 첫 전송 **10:33:48** vs 배포 **11:08:44**,
배포 후 신규 대화·첨부 **0건**. 재보고는 구자산 세션 경험이었다. 반대로 같은 오전 대조군
(`...a8b43197` 10:30 첨부 5건 = sonnet 정상 / `...2211841a` 10:33 첨부 1건 = haiku 강등)은 "첨부 유무"가
아니라 **선택→첨부 순서**가 분기점임을 라이브에서 재확인해, 선행 cycle 의 경로 특정을 강화한다.

**지문 판독 보정**: 선행 기록의 "미동봉 = kv 행 부재"는 3분기로 정밀화한다 — 행 부재=미동봉 /
빈 값 행=**기본값과 같은 모델의 명시 동봉**(서버가 기본값 이탈만 저장) / 값 행=비-기본 명시 동봉.
재현 대화에 두 단계(10:33 부재 → 10:59 빈 값)가 모두 남아 원 진단과 정합하며, 향후 빈 값 행을
미동봉으로 오독하는 오진을 막는다.

**미해소(정직 표기)**: 관측 표본 corroboration(30일 오전송 3/5 재측정)은 배포 직후 표본 부재로
다음 `/_dqa:conversation_audit` 이월. 계정별 모델 RBAC 조합은 본 Run 대상 아님.
- Cross-ref: MODIFY CHG-20260729T113000-model-pick-postdeploy ·
  test-runs.d/20260729T1130-model-pick-postdeploy.md · 선행 REV-20260728T191126-model-pick-early-cid ·
  마찰 원장 FR-model-pick-lost-on-early-cid.

## REV-20260729T140200-attach-full-scope — 첨부 참조 스코프 전환의 판단 근거와 남긴 위험

**진단의 확실성**: 사용자 보고("이어서 요청하면 기존 첨부 접근 불가")를 코드에서 두 갈래로 귀속했다.
① 참조 범위가 프론트 selection 에만 의존(D16) — `_composerAttachmentSnapshot` 이 bucket 부재 시
빈 목록을 반환하고, bucket 재수화(`_loadConversationAttachments`)는 `switchConversation` 경로에만
걸려 있다. `loadHistory` 주석이 "이 경로는 switchConversation(→_loadConversationAttachments)을
거치지 않는다"고 스스로 기록하고 있어, 재수화 없는 진입 경로의 실재는 코드가 증언한다.
② 보완재였던 `attachment_scope_all` 은 **백엔드 어디에서도 읽히지 않았다**(Python 전역 grep 0건) —
켜도 동작이 바뀌지 않았다. 사용자가 "구분할 의미가 없다"고 느낀 것과 정확히 일치하며, 이것이
토글 제거 요청의 근거이기도 하다. ①·② 는 정적 증거로 확정했고, 개별 사용자 대화의 재현 로그로는
확증하지 않았다(라이브 실증은 배포 후 PB-0008 Run 에서 수행).

**설계 선택**: 결정 주체를 프론트에서 서버로 옮겼다. 프론트 재수화 경로만 보강하는 대안은 진입
경로가 늘 때마다 같은 결함이 재발하는 구조를 남긴다. 서버가 대화를 스코프로 삼으면 진입 경로의
수와 무관하게 불변식이 성립한다.

**보안 판단**: 스코프 확대가 **경계를 넘지 않도록** 세 가드를 그대로 통과시켰다 — 그룹 발신자
스코프(feature-0009 CSO F1: 타 멤버 첨부를 통한 권한상승 차단), ConversationId 스코프(TASK-0284
IDOR), 공유창 bounded 발신자 억제. 그룹 개방 여부는 CSO 가 명시 결정한 사안이라 임의로 뒤집지
않고 사용자 확인을 받아 **유지**로 확정했다. `read_attachment` 의 권한 경계는 별도 검증이 아니라
**같은 스코프 집합의 재사용**이다 — 경계를 한 곳에서만 계산해 두 경로가 갈라지지 않게 했다.

**비용 판단**: 전량 인라인 대신 도구 조회를 택했다. 프롬프트에 늘어나는 것은 파일당 1줄 메타이고,
매 턴 인라인되는 본문량(텍스트 20개·이미지 5개 상한)은 종전과 동일하다. 대신 모델이 필요하다고
판단할 때만 왕복이 생긴다 — LLM 호출 비용이 예측 가능한 방향으로 늘어난다(Major 로 등급한 이유).

**지연 회귀 차단**: 스코프가 넓어지면 ask 진입 시 동기 ingest 대기(최대 25s)가 과거 failed 첨부를
매 턴 재시도할 수 있었다. 대기 대상을 이번 턴 첨부로 한정해 이 경로를 봉인했다 — 스코프 확대가
응답 지연으로 새는 것을 막는 지점.

**리뷰어 오판 대응**: 인라인 밖 첨부가 늘면 "digest 에 없는 파일 = 창작" 오판(기존에 관측된
honesty false positive)의 표면이 함께 넓어진다. 매니페스트를 예산 선점으로 항상 남기고 리뷰어
지시문에 오판·재첨부 요구 금지를 명시해 상쇄했다.

**미해소(정직 표기)**: ① 라이브 실증(실제 대화에서 이전 턴 첨부 참조 + read_attachment 호출)은
배포 후 PB-0008 Run 으로 수행한다 — 본 cycle 의 검증은 컨테이너 스위트와 정적 계약까지다.
② PG 전용 컷오버 환경에서 `_load_scoped_attachment_rows` 는 MySQL(dual-write 정본)만 조회한다 —
현행 dual-write 전제에서 정합하나, MySQL 미러가 걷히면 PG 경로 추가가 필요하다. ③ 상한 200 은
관측 없이 정한 값이다(현실 대화의 첨부 수를 크게 상회하도록 잡음) — 초과 사례가 관측되면
재평가한다. ④ pdf 본문 조회는 텍스트 추출 경로가 없어 이진 거부로 안내한다(종전과 동일 한계).

- Cross-ref: MODIFY `CHG-20260729T140200-attach-full-scope` · DECISIONS
  `ADR-20260729T140200-attach-full-scope` · FUNCTION `REQ-20260729-attach-full-scope` ·
  TASK `20260729T1402-attach-full-scope`.

## REV-20260729T144500-attach-full-scope-panel [SUBAGENT:security] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1402-attach-full-scope
- Trigger: credential·permission boundary / 권한 경계·노출 범위
- Timestamp: 2026-07-29T14:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T052000Z-security.md
- Critical issue: `client_ids` 무검증 합집합으로 그룹 대화에서 타 멤버 첨부가 발신자 실행 맥락에 유입(CSO F1 우회) — 스톡 UI 가 대화 첨부 전량을 selected 로 보내므로 악의 없이도 도달. 부수: `_load_scoped_attachment_rows` 가 cid 부재 시 스코프 술어 소실(fail-open), 공유창 bounded 발신자에게 도구가 열림.
- 조치: 대화 확정 경로에서 client_ids 합집합 제거(DB 조회만이 진실) · 그룹 해소 실패는 fail-closed · `_load_scoped_attachment_rows` 를 ConversationId 필수(fail-closed)로 · `_suppress_conversation_context` 면 read_attachment 미노출.
- Human Approval Needed: no

## REV-20260729T144500-attach-full-scope-panel [SUBAGENT:backend] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1402-attach-full-scope
- Trigger: query·schema·API contract / 쿼리·응답 계약
- Timestamp: 2026-07-29T14:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T052000Z-backend.md
- Critical issue: ① `build_attachment_digest` 매니페스트가 상한 없이 예산 선점 + 최종 절단 부재 → digest 가 cap 대비 최대 20,641자로 부풀어 도구 근거·첨부 발췌가 동시 소실. ② vision 인라인이 양쪽 백엔드 모두 `ORDER BY id ASC LIMIT 5` 라, 스코프 확대와 함께 "방금 올린 이미지"가 매 턴 탈락(프롬프트는 전달된다고 단정).
- 조치: 매니페스트 선점 비율 상한(`_ATTACH_MANIFEST_BUDGET_RATIO=0.35`) + 최종 `[:cap_chars]` 복원 · vision 정렬을 MySQL·PG 양쪽 `ORDER BY id DESC` 로(텍스트 인라인과 동형). 커넥션 누수·mixed-version 계약·contextvar 패리티는 리뷰에서 정합 확인됨.
- Human Approval Needed: no

## REV-20260729T144500-attach-full-scope-panel [SUBAGENT:qa] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1402-attach-full-scope
- Trigger: test coverage·regression / 테스트 커버리지·회귀
- Timestamp: 2026-07-29T14:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T052000Z-qa.md
- Critical issue: 신설 테스트가 통과하는데도 실질 검증이 얕음 — digest 예산 테스트가 매니페스트 1건만 써서 폭주를 비켜감, 스코프 테스트 7건이 라이브에서 실행되지 않는 MySQL 폴백 분기만 검사(PG 경로 그룹 가드 커버리지 0), 리뷰어 지시문 테스트가 `inspect.getsource` 폴백으로 항상 성립하는 tautology, `test_attach_inline_honesty` 의 `"re-attach" in out` 이 새 **금지문**의 부분문자열로 통과(의미 반전).
- 조치: 매니페스트 200건 규모 예산 테스트 2건 추가 · PG 경로 테스트 3건 신설(상태 필터·그룹 가드·상한) · 리뷰어 프롬프트 상수(`REDTEAM_REVIEW_PROMPT`) 직접 검사 · inline-honesty 계약을 `read_attachment(` + `do NOT ask the user to re-attach` 로 교정.
- Human Approval Needed: no

## REV-20260729T144500-attach-full-scope-panel [SUBAGENT:ux] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1402-attach-full-scope
- Trigger: UI·checkbox 제거 / 사용자 모델
- Timestamp: 2026-07-29T14:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T052000Z-ux.md
- Critical issue: 첨부 pill 의 × ("첨부 제거")가 클라이언트 bucket 만 splice 하므로, 서버가 다음 전송에서 그 첨부를 DB 에서 되살려 assistant 가 그대로 읽는다 — 사용자가 "제거"한 파일이 계속 참조되는 거짓 어포던스. 실삭제 API 는 존재하나 프론트 호출 0건.
- 조치: ×를 실제 삭제(`window.confirm` → `DELETE /api/attachments/{id}`)로 연결 + aria-label/`title` 을 "첨부 삭제"로 · 업로드 중·실패 로컬 항목만 목록 제거 유지 · 삭제 후 사이드패널 재동기화.
- Human Approval Needed: no

## REV-20260729T144500-attach-full-scope-panel [SUBAGENT:design] — CONCERN → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1402-attach-full-scope
- Trigger: layout·visual / 레이아웃·시각 위계
- Timestamp: 2026-07-29T14:45:00+09:00
- Verdict: CONCERN (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T052000Z-design.md
- Critical issue: 구분선 소실 우려는 **반증**(헤더가 자체 `border-bottom` 보유). 그러나 참조 범위를 대화 전량으로 넓히면서 그 사실을 알리던 유일한 UI(토글+토스트)를 함께 제거해 사용자가 노출 범위를 알 길이 없어졌고, 디자인 정본 `DESIGN-entry-points.md` §4.3 이 삭제된 컨트롤을 규정한 채 남았다.
- 조치: `.attach-side-panel-note` 안내 1줄 신설(첨부 존재 시 노출) · DESIGN-entry-points.md §4.3 을 제거·대체·× 실삭제 계약으로 재작성.
- Human Approval Needed: no
## REV-20260729T152000-attach-list-delete [SUBAGENT:ux] — BLOCK → 해소 (권한 1건 사용자 판단 이월)

- Related TASK: feature-0003-agent-web-ui / 20260729T1520-attach-list-delete
- Trigger: UI·button 추가 / 삭제 어포던스
- Timestamp: 2026-07-29T15:35:00+09:00
- Verdict: BLOCK (조치 후 해소 — 권한 축은 안전판 + 이월)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T062000Z-ux.md
- Critical issue: ① 목록 × 가 반환값을 버려 composer bucket 미갱신 → 삭제 후 추가 업로드 시 지운 파일이 pill 로 부활. ② 백엔드 삭제 권한이 업로더가 아니라 "대화 소유 OR 그룹 멤버" 라, 목록 × 상시 노출이 그룹에서 타인 파일 삭제를 한 클릭 거리로 만든다(업로더 신호·restore UI 부재). ③ 권한 거부가 404 라 403 분기는 죽은 코드.
- 조치: ① bucket 정리를 공통 삭제 경로에 편입 ② **1:1 대화에서만 목록 × 노출**(fail-closed) — 근본 해소는 인가 정책 결정이라 사용자 판단으로 이월 ③ 404/403 동시 처리.
- Human Approval Needed: **yes** — 그룹 대화의 첨부 삭제 권한을 업로더 기준으로 좁힐지 여부(현행: 멤버 전원 가능, feature-0009 열람/공유 경계 재사용).

## REV-20260729T152000-attach-list-delete [SUBAGENT:design] — CONCERN → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1520-attach-list-delete
- Trigger: layout·visual / 행 구성·위계
- Timestamp: 2026-07-29T15:35:00+09:00
- Verdict: CONCERN (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T062000Z-design.md
- Critical issue: 삭제 버튼이 `.attach-list-item-info` 폭을 28px(패널 최소폭에선 -21%) 빼앗는데 `.attach-list-item-meta` 에 말줄임 방어가 없어 `version_count>1` 행의 메타줄이 2줄로 터지고, 이름줄 배지(`v2 · AI 수정`)는 말줄임에 먹혀 사라진다. 시각 위계·테마는 PASS(`.pill-remove` 관용구 정합, 콘솔 LIGHT-ONLY).
- 조치: meta 에 `overflow/text-overflow/white-space` 3종 추가 · 이름줄을 flex 로 분리해 텍스트만 말줄임하고 배지는 `flex-shrink:0` 로 보존.
- Human Approval Needed: no

## REV-20260729T160000-attach-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / 20260729T1600-attach-postdeploy
- Reason: changed paths are docs only (test-runs.d fragment + TASK/REVIEW 기록) — 실행 코드·정적 자산 변경 0줄. 검증 대상 코드는 선행 두 cycle 에서 이미 §18.8 패널(security/backend/qa/ux/design 5명 + ux/design 2명)을 거쳤고, 본 cycle 은 그 배포본의 라이브 실측 결과를 기록할 뿐이다.
- Timestamp: 2026-07-29T16:00:00+09:00
## REV-20260729T145500-conv-search-attach-name — 대화 검색 첨부 파일명 축 (Major §12.3)

- Related TASK: feature-0003-agent-web-ui / 20260729T1455-conv-search-attach-name
- Timestamp: 2026-07-29T14:55:00+09:00
- Verdict: SHIP (POST-DEPLOY PB-0008 잔여)

### 왜 Major 인가 (그리고 왜 Critical 은 아닌가)
검색 대상 필드는 `docs/SECURITY.md §8.2` 가 **열거로 고정한 정책 표면**이라, 축 추가는 코드 변경이
아니라 정책 변경이다(§12.3 "보안 수준 저하 가능성"에 대한 사전 검토 대상). 반면 Critical 조건인
인증·인가 구조 변경, 파괴적 데이터 변경, 개인정보 *처리 목적/주체* 변경은 어디에도 해당하지 않는다 —
신규 권한 코드 0 · 엔드포인트 0 · 스키마/마이그레이션 0 · 반환 대화 집합의 결정 로직 무변경.

### 노출면 판정 (핵심 근거)
1. **인가 경계가 유일한 게이트로 남는다.** 첨부 EXISTS 는 owner / 그룹 멤버십 / `.any` WHERE 를
   통과한 대화 *안에서* 평가된다. 즉 "볼 수 없던 대화가 보이게 되는" 경로가 없다.
2. **새 데이터를 노출하지 않는다.** 결과에 오른 대화의 첨부 파일명은 이미
   `GET /api/conversations/{cid}/attachments`(`conversation.attachment.read.{own,any}`) 로 전량
   조회 가능하다. 검색은 기존 데이터에 인덱스를 하나 더 놓는 것이지 새 창을 내는 게 아니다.
3. **가시성 비대칭을 만들지 않는다.** 검색 대상을 첨부 목록과 같은 조건(미삭제 + 버전 최신)으로
   묶었다. 삭제한 파일명이 검색으로만 되살아나면 "삭제했다"는 사용자 기대를 깬다.
4. **공유 window 와의 관계.** feature-0009 `[from,to]` window 는 **메시지** 가시성 장치이고 첨부
   목록은 애초에 window 로 클립되지 않는다(conversation 단위 스토어). 따라서 첨부 축은 window
   격리를 새로 깨지 않는다 — 다만 첨부에 window 를 도입하려면 목록·검색·recall 을 한 번에 다뤄야
   하므로 별 cycle 로 남긴다(현행 한계의 명시적 기록).
5. **잔여 리스크(정직)**: 파일명 자체가 PII 를 담을 수 있다(`홍길동_급여명세.xlsx`). 이는 대화
   제목이 이미 갖는 것과 동급이며, cross-account 검색은 `conversation.search.body` audit 로
   추적된다. 첨부 *내용* 검색은 질적으로 다른 표면이라 범위에서 명시 제외했다.

### 설계 판단
- **매칭 근거를 반환하기로 한 이유**: 파일명으로만 매칭되면 제목·본문 어디에도 검색어가 없어
  기존 `matched_excerpts` 가 항상 빈칸이 된다. 근거 없는 결과 행은 "왜 떴는지 모르는 결과" 라
  검색 품질을 오히려 떨어뜨린다. 그래서 축 추가와 표면화를 한 cycle 로 묶었다.
- **칩 표시 게이트를 `mine || snippet_opt_in` 으로 둔 이유**: 본인 대화는 자기 첨부 목록을 이미
  자유 열람하므로 게이트가 의미 없고, 타 계정 대화는 본문 미리보기와 같은 명시적 opt-in 을
  거치게 해 §8.6 의 기존 정책선을 그대로 잇는다. `.own` only 사용자는 타 계정 대화가 결과에
  없으므로 항상 표시 경로만 탄다(추가 마찰 0).
- **conv 당 3건 cap**: 파일이 많은 대화가 응답과 결과 행을 부풀리지 않게. 최신 우선이라 방금 올린
  파일이 먼저 보인다.
- **fail-soft**: 첨부 수집 실패가 검색 자체를 막지 않게 excerpt 와 동일하게 개별 try/except.
  검색은 조회 기능이라 부분 degrade 가 전면 실패보다 낫다.
- **채택하지 않은 대안**: (a) 첨부 내용(추출 텍스트) 검색 — 노출면이 질적으로 다르고 별 게이트가
  필요. (b) FULLTEXT/trigram 인덱스 — 현행 LIKE/ILIKE 안전망(§8.4 rate limit + 3s 실행 상한)이
  아직 임계에 닿지 않았고, 인덱스 도입은 §8.7 이 이미 trigger 조건과 함께 예약해 둔 후속 항목.
  (c) 백엔드에서 타 계정 파일명 자체를 반환 차단 — 기존 excerpt 가 이미 "백엔드 반환 + 프론트
  게이트" 패턴이라 여기만 다르게 하면 정합이 깨진다(두 축을 함께 바꾸려면 별 cycle).

### 위험·후속
- POST-DEPLOY PB-0008 라이브 시각검증 잔여(`visual_verification_scope: always`) — 칩 렌더·게이트·
  파일명 매칭 결과를 실 Windows 브라우저에서 확인해야 완료.
- 성능: 첨부 EXISTS 는 `ix_core_attachments_conv (conversation_id, deleted_at)` 로 conv 별 소수 행만
  본다. 다만 ILIKE 는 인덱스 미사용이므로 첨부가 극단적으로 많아지면 §8.7 FULLTEXT trigger 와 함께
  재평가한다.
- Human Approval Needed: no (Major — 정책 갱신 근거를 본 REVIEW 와 SECURITY §8.2 에 기록)

## REV-20260729T152000-conv-search-attach-name-codex [CODEX:conv-search-attach-name] 적대 리뷰 — P1 1건 + P2 4건

- Related TASK: feature-0003-agent-web-ui / 20260729T1455-conv-search-attach-name
- Trigger: query/index + API/response shape + UI/screen + 정책 doc(SECURITY.md) — 표상 full panel
- 경로: 세션 상위지시(하네스 `Agent` tool 금지)와 §18.8 패널 요구가 상충 → **사용자에게 1회 확인**
  후 `/codex review`(§18.8.1 경로 2, check #9 accepted `[CODEX:*]`) 채택. subagent 패널만
  `[SKIPPED:tool-restricted:security,backend,qa,ux,design-subagent]`.
- Verdict: **FIX-THEN-SHIP** — P1 포함 4건 in-cycle 수정, 1건(성능) POST-DEPLOY 이월.

**P1 — 첨부 파일명 축이 `conversation.attachment.read.*` 를 우회 (수정 완료)**

초안은 "결과에 오른 대화의 첨부 파일명은 첨부 목록 API 로 이미 열람 가능하다" 를 노출면 판정의
축으로 삼았다. **이 전제가 틀렸다.** `conversation.list.any`(관리자 grant)와
`conversation.attachment.read.any`(설명 그대로 "운영자 한정")는 카탈로그상 독립 코드이고, 전자만
가진 계정이 실재할 수 있다. 그 계정에게 초안은:

1. 첨부 파일명으로 타 계정 대화를 **매칭**시켜 주고(= "그 대화에 이 파일명이 있는가" oracle),
2. `matched_attachments` 로 **파일명 자체를 반환**했다.

프론트의 `mine || snippet_opt_in` 게이트는 UI 절제일 뿐 방어가 아니다(DevTools·직접 API 호출).
→ `app._search_attachment_axis(account)` 단일 판정점을 두고 **검색 EXISTS 자체를 권한으로 게이팅**
했다. 축을 끄면 근거뿐 아니라 매칭 oracle 도 함께 사라진다는 점이 핵심 — 근거만 막고 축을 남기면
파일명 추측 공격이 그대로 성립한다. `own` 스코프는 EXISTS 를 본인 소유·멤버 대화로 좁혀
`_account_can_access_conversation` 의 own 판정과 동형으로 맞췄고, self_id 부재는 fail-closed.

**교훈(정직)**: "이미 열람 가능한 데이터" 라는 논증은 *어떤 권한 조합에서* 열람 가능한지 확인하지
않으면 성립하지 않는다. 초안의 SECURITY §8.2 서술은 그 확인 없이 쓰였고, 리뷰가 그것을 잡았다.
§8.2.1 을 권한 스코프 표로 재작성해 정정했다.

**P2 — PG 경로 LIKE escape 유실 (수정 완료)**: `_list_conversations_pg` 가 `ESCAPE '!'` 없이 raw
패턴을 ILIKE 에 넣어 `%`/`_` 가 wildcard 로 샜다. 이는 SECURITY §8.3("모든 LIKE 는 ESCAPE '!' + 3-char
escape") 위반이며 AR-M4 PG 포팅 때 유실된 것으로 보인다(본 cycle 이 만든 결함은 아니나 같은 함수를
건드리므로 함께 고침). 수집 헬퍼는 escape 를 쓰고 있어 semantics 도 어긋나 있었다 — 대화는 매칭되는데
근거 칩만 조용히 비는 조합. PG 전 축을 escape 적용으로 정합화했다.

**P2 — fail-soft 범위 (수정 완료)**: 헬퍼의 커서 생성·백엔드 판정·결과 변환이 try 밖이라 직접
호출 시 계약이 깨졌다. 경계 전체를 보호.

**P2 — 프론트 캐시 정합 (수정 완료, 테스트가 적발)**: 보강 테스트(excerpt 리셋 지점과 1:1 대응
고정)가 검색 **실패 폴백** 경로의 `matched_attachments` 리셋 누락을 잡았다. 이전 검색의 파일명 칩이
새 검색 실패 후에도 잔존할 수 있었다.

**P2 — 테스트가 tautology (수정 완료)**: 초안 12건이 대부분 `inspect.getsource` 문자열 검사라 실제
동작을 검증하지 못했다. fake 커넥션으로 **실제 SQL·params 를 캡처**하는 실행 기반 26건으로 재작성
했고, 그 결과 위 캐시 누락이 실제로 적발됐다(테스트 품질 개선이 결함 1건을 직접 회수).

**P2 — 성능 (미해소·POST-DEPLOY 이월)**: `ILIKE '%q%'` 는 파일명 인덱스를 못 쓰고
`max_execution_time 3s` 는 응답 상한이지 DB CPU 상한이 아니다. 라이브 `EXPLAIN ANALYZE` 와
worst-case 검색어 벤치를 배포 후 수행한다. 기존 메시지 본문 축이 이미 동일 성질이라 본 변경이
새로 만든 리스크는 아니며, §8.7 이 예약해 둔 FULLTEXT/trigram trigger 와 함께 재평가한다.

- 검증: 신규 26건 PASS · 전체 스위트 baseline diff **신규 실패 0** · ruff PASS.
- Human Approval Needed: no (P1 은 in-cycle 수정 완료 — 노출 상태로 출하되지 않았다)

## REV-20260729T154000-conv-search-attach-name-codex2 [CODEX:conv-search-attach-name] 재검증 (2차)

- Timestamp: 2026-07-29T15:40:00+09:00


수정본을 같은 프롬프트 형식으로 재검토. **P1(첨부 권한 우회) "해결됨" — 권한 판정이 SQL 첨부
EXISTS 와 `matched_attachments` 양쪽에 적용되고, 권한 없음은 EXISTS 자체를 제거해 oracle 도 차단**
으로 확인. escape 3경로 정합·fail-soft 경계·캐시 리셋 4지점도 해결 확인. 신규 P2 3건:

1. **PG/MySQL 동작 불일치 (수정)** — `own` 스코프를 엔드포인트가 items 필드로 판정했는데
   `is_member` 는 **PG 경로만** 싣는다. MySQL 폴백에서는 멤버 대화의 근거가 조용히 비어 AC-4 를
   깬다(누출은 아님). 판정을 SQL 로 내려 백엔드 무관하게 만들었다. *교훈: 인가 스코프를 응답
   payload 필드로 판정하면 그 필드를 채우는 경로에 암묵 의존이 생긴다 — 스코프는 데이터가 나오는
   곳(SQL)에서 거는 게 옳다.*
2. **프론트 응답 경합 (수정)** — 세대 토큰 부재로 늦은 이전 응답이 새 결과를 덮어쓸 수 있었다.
   기존 `matched_excerpts` 도 같은 위험을 안고 있었으므로 가드가 양쪽을 함께 보호한다.
3. **PG runaway 상한 부재 (수정)** — §8.4 의 `max_execution_time` 은 MySQL 연결 전용인데 라이브
   검색은 PG 경로다. `SET statement_timeout = 3000` 을 목록 검색·수집 양쪽에 걸었다. 이는 상한이지
   비용 개선이 아니므로 성능 실측(P2)은 여전히 POST-DEPLOY 로 남는다.

- 재검증 후 30건 PASS · 전체 회귀 신규 실패 0 · ruff PASS.
- Verdict: **SHIP** (POST-DEPLOY = PB-0008 시각검증 + 첨부 EXISTS EXPLAIN 실측)
## REV-20260729T152000-ratelimit-scope-paging [SKIPPED:tool-restricted:backend,qa,ux,design] — security 축은 built-in 채널로 수행, BLOCK → 흡수 후 PASS

- Related TASK: feature-0003-agent-web-ui / 20260729T1520-ratelimit-scope-paging
- Trigger: API/endpoint·performance/throttle keyword matched (API·엔드포인트 / 성능·캐싱·쓰로틀) — rate-limit 상한 조정 + 대화 본문 클라이언트 캐시 신설
- Channel: built-in `/security-review` (제약 없는 채널). 스킬이 요구하는 subagent fan-out 은 본 세션의 상위 우선순위 도구 제약과 충돌 → AGENTS.md §18.8.2 "상위 우선순위 지시 carve-out" 에 따라 직접 코드 리뷰 + 기계적 점검으로 수행, 미검증 도메인은 `[SKIPPED:tool-restricted:backend,qa,ux,design]` 로 명시(대체 증거 병기).
- Timestamp: 2026-07-29T15:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T064500Z-security.md
- Critical issue: 신설한 `_branchViewCache`(대화 **본문** payload 보관)가 세션 경계에서 비워지지 않았다. 이 앱의 `handleLogout` 은 **페이지를 새로 고치지 않으며**(그래서 `state.messages`·모델 선택을 손으로 비운다 — 기존 주석 "공용 단말 계정 간 누출"), 캐시가 살아남으면 공용 단말에서 다음 로그인 계정이 같은 `(cid, versionId)` 로 페이징할 때 **직전 계정 기준으로 필터된 본문**을 렌더한다. 공유창 window 가 계정마다 다른 그룹 대화에서 `_resolve_display_window` 의 fail-closed 가시성 게이트가 클라이언트 캐시로 우회되는 누출 경로.
- 조치: `handleLogout` 에서 `_branchViewCacheClear()` + 지연 사이드바 타이머 취소 · `initializeWorkspace` 진입 시에도 `_branchViewCacheClear()`(세션 만료 후 리로드 없이 재로그인하는 `handleLogin → initializeWorkspace` 경로는 logout 미경유 — 2중 방어).
- 반증된 후보 4건: `scope` 파라미터 신뢰경계(호출부 7곳 전부 모듈 상수) · `Retry-After` 헤더 주입(`str(int)` + 1~60 clamp) · SQL 주입(파라미터 바인딩 + 기존 table allowlist 유효, 442 조합 전수 대조 동등) · 인가 경로 축소(`renderAccessNotice`/`applyProductHydration` 은 표시 계층, 접근 판정은 서버 전담).
- Human Approval Needed: no
## REV-20260729T163000-attach-append-only [SUBAGENT:ux] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1630-attach-append-only
- Trigger: UI·삭제 UI 철회 / append-only 계약
- Timestamp: 2026-07-29T16:45:00+09:00
- Verdict: BLOCK (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T073000Z-ux.md
- Critical issue: append-only 계약 자체는 성립(렌더 게이트 ⇔ 함수 가드 정확한 여집합, 프론트 DELETE 호출·잔재 0건)하나, 새로 붙인 "업로드 취소" ×가 in-flight fetch 를 abort 하지 않아 **파일이 그대로 저장되고 "업로드 완료" 토스트까지 뜬다** — 삭제 UI 가 사라진 상태라 사용자에게 회수 수단이 0개로 영구히 AI 참조 스코프에 남는다.
- 조치: ×의 대상을 `staged`(요청 전)·`failed`(서버에 실물 없음)로 좁히고 `uploading` 제외. 함수 가드를 같은 판정으로 정렬(어떤 경로로 호출돼도 append-only 위반 불가). aria-label/title 문구 통일.
- Human Approval Needed: no

## REV-20260729T163000-attach-append-only [SUBAGENT:design] — CONCERN → 해소

- Related TASK: feature-0003-agent-web-ui / 20260729T1630-attach-append-only
- Trigger: layout·visual / 삭제 UI 철회
- Timestamp: 2026-07-29T16:45:00+09:00
- Verdict: CONCERN (조치 후 해소)
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260729T073000Z-design.md
- Critical issue: `.attach-list-item-meta` 의 nowrap+ellipsis 가 텍스트가 아니라 인라인 **"버전 N개 ▾" 버튼을 잘라내** 버전 이력의 유일한 진입점을 없앤다(패널 최소 폭 240px 에서 약 13px 초과). 그 규칙을 정당화하던 근거(삭제 ×의 폭 점유)는 바로 이 diff 가 제거했는데 규칙과 주석만 남았다. 나머지 4개 축(우측 정렬 비대칭·죽은 스타일·안내 문구 줄바꿈·danger hover 무게)은 실측 PASS.
- 조치: 해당 말줄임 3종을 되돌림(원상복구). 이름줄 flex 분리는 배지 보존 효과가 있어 유지.
- Human Approval Needed: no
## REV-20260729T170000-search-collation-nameerror [SKIPPED:hotfix-single-symbol] 본문 검색 500 근본 수정

- Related TASK: feature-0003-agent-web-ui / 20260729T1700-search-collation-nameerror
- Timestamp: 2026-07-29T17:00:00+09:00
- Verdict: SHIP (배포 후 라이브 재검증 잔여)

**패널 판정**: 변경이 단일 심볼 참조 교정(3줄) + 테스트 신설이고, 신규 표면·인가 경계·스키마
변경이 0이다. §18.8 표의 dispatch 신호에 해당하는 새 설계 결정이 없어 `[SKIPPED:hotfix-single-symbol]`
로 기록하되, 아래 자체 적대 검토를 남긴다. (세션 상위지시로 subagent 패널은 불가 — 직전 cycle 에서
사용자 확인 후 codex 대체 경로를 썼고, 본 hotfix 는 그 검증 중 파생된 3줄 수정이다.)

**자체 적대 검토**
- H1 *"모듈 로컬에 `_COLLATION_AUDIT_DONE = False` 를 두면 더 간단하지 않나"* — 그러면 app.py 의
  동명 전역과 상태가 갈려 once-per-process 보장이 이중화된다. 테스트가 `app._COLLATION_AUDIT_DONE`
  을 리셋해도 라우터 모듈 플래그는 남아 audit 이 영영 skip 될 수 있다. 이 repo 의 패치-단일점
  규약(`app.X` 동적 참조)이 정확히 이 문제를 위한 것이라 그쪽을 택했다. N3 이 이 결정을 고정한다.
- H2 *"같은 유형이 더 있나"* — AST 로 `src/**/*.py` 의 `global X` 선언 대비 module-level 바인딩
  부재를 전수 검사. 수정 후 0건. ITEM-10 계열 이동이 여러 차례 있었으므로 이 검사는 필요했다.
- H3 *"fail-soft 인가"* — audit 은 경고 목적이며 내부 예외를 삼킨다(N5). 다만 **NameError 는
  함수 진입 직후 플래그 읽기에서 나 try 밖이었다** — 그래서 fail-soft 가 작동하지 못하고 500 이
  됐다. 수정 후에는 그 지점 자체가 사라진다.
- H4 *"직전 cycle 이 이 결함을 유발했나"* — 아니다. `git log` 상 원인은 2026-07-11 ITEM-10 p7 이고,
  직전 cycle 은 같은 함수·같은 게이트를 건드리지 않았다. 다만 직전 cycle 의 신규 테스트 30건도
  이 경로를 우회(monkeypatch·직접 호출)해 **잡지 못했다** — 이 점은 정직하게 기록한다.
- H5 *"테스트가 진짜 가드인가"* — 수정을 stash 로 되돌려 재실행, N1/N3/N4 가 NameError 로 실패함을
  확인했다. tautology 아님.

**교훈(LEARNINGS 후보)**: 단위 테스트가 진입 경로의 중간 호출을 monkeypatch 로 지우면, 그 호출이
런타임에 터져도 통과한다. 검색·업로드처럼 **게이트 뒤에서만 실행되는 부수 호출**은 최소 1건은
패치 없이 실제로 타는 테스트를 둔다.

- Human Approval Needed: no
## REV-20260729T172000-append-only-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / 20260729T1720-append-only-postdeploy
- Reason: changed paths are docs only (test-runs.d fragment append + TASK/MODIFY/REVIEW 기록) — 실행 코드·정적 자산 변경 0줄. 검증 대상 코드는 선행 cycle 에서 §18.8 패널(ux·design)을 거쳤고, 본 cycle 은 그 배포본의 라이브 실측 결과를 기록할 뿐이다.
- Timestamp: 2026-07-29T17:20:00+09:00

## REV-20260729T180000-conv-search-postdeploy [SKIPPED:non-policy-doc] POST-DEPLOY 실증 기록 (doc-only)

- Related TASK: feature-0003-agent-web-ui / 20260729T1800-conv-search-postdeploy
- Timestamp: 2026-07-29T18:00:00+09:00
- Verdict: SHIP

코드·정책 문서 변경 0(§18.8 표 첫 행 "비정책 doc-only" → panel SKIP). 기록의 정확성만이 리뷰 대상이라
아래 자체 확인을 남긴다.

- 기록된 라이브 결과는 전부 이 세션에서 실제로 실행한 관측이다 — 검색 응답 JSON(`matched_count`,
  `matched_attachments`), 칩 `innerHTML`(강조 태그 포함), 스크린샷, `EXPLAIN (ANALYZE, BUFFERS)` 출력.
  추정으로 채운 항목 없음.
- **한계 명시**: 성능 실측은 현 규모(첨부 634행/대화 271행) 단일 측정이다. 부하 상태·대규모 데이터의
  worst-case 는 측정하지 않았으며, 그 재평가 트리거(§8.7 FULLTEXT — rate limit 빈발 또는
  statement_timeout 히트)를 TASK 에 명시했다. "성능 문제 없음" 이 아니라 "현 규모에서 첨부 축의 기여가
  0.5% 미만" 이 측정된 사실이다.
- **한계 명시 2**: PB-0008 은 `bootstrap_admin`(admin, `attachment.read.any` 보유) 단일 계정으로 수행했다.
  `.own`-only 계정의 스코프 축소 동작은 단위 테스트(P2/P4/P5)로만 검증됐고 라이브 계정 실측은 아니다.
- Human Approval Needed: no
## REV-20260729T174200-product-picker-keynav [CODEX:product-picker-keynav] 적대 리뷰 — P1 0건 · P2 3건 + P3 1건 in-cycle 흡수

Trigger: UI/키보드 상호작용 keyword matched (UI/화면/버튼 — §18.8 표 `ux, design` 행). 채널 선택은
아래 [SKIPPED:tool-restricted] entry 참조. 대상: `static/app.js`·`static/styles.css`·
`tests/headless/verify_product_dropup_keynav.py` uncommitted diff (codex-cli 0.145.0, `--sandbox read-only`).

**Verdict: PASS (P1 0건)**. 지적 4건 전부 이번 cycle 에서 처리했다.

- **P2-1 문서 리스너 누수 (수정)** — `_select()` 가 `closeProductDropup()` 만 호출하고
  `openProductDropup()` 이 문서에 건 `mousedown`/`keydown` capture 리스너를 해제하지 않았다. 새 Enter
  경로가 같은 `_select` 를 재사용하므로 "열고 → 선택" 을 반복할수록 죽은 클로저가 쌓이고, **닫힌 뒤
  Escape 를 누르면 포커스가 제품 chip 으로 튄다**. 이는 클릭 선택에도 있던 **기존 결함**이지만 내
  변경이 그 경로를 확장하므로 in-cycle 로 흡수했다 — 해제 함수를 모듈 스코프
  `_productDropupDetach` 에 보관하고 `closeProductDropup()` 이 단일 해제 지점이 되게 했다(중복 open
  방어 + `setTimeout` 지연 등록이 이미 닫힌 뒤 도착하면 배선하지 않는 가드 포함). 회귀 가드 T14/T15/T15b.
- **P2-2 테스트가 실 렌더 경로를 안 탄다 (수정)** — 초판 하네스는 항목 DOM 을 자체 `buildMenu()` 로
  흉내내 `renderProductDropupMenu` 의 `innerHTML=""` 재렌더·검색칸 자동 포커스·문서 리스너 배선을
  검증하지 못했다. 하네스를 **실 `renderProductDropupMenu`/`openProductDropup`/`closeProductDropup`
  원문 + state 스텁** 으로 재작성해 실 경로를 그대로 돌린다(T1c 자동 포커스·T16 재렌더 후 배선 유지·
  T15 Escape capture 가 새로 검증 범위에 들어옴). 케이스 19 → 27건.
- **P2-3 IME 판정 취약 (수정)** — `ev.isComposing` 만 보면 일부 브라우저/IME 가 조합 중 keydown 에
  `isComposing=false` + 레거시 `keyCode=229` 만 주는 경우를 놓쳐 한글 조합 중 `↓` 를 가로챌 수 있다.
  두 신호를 모두 확인하도록 가드 확장(T12/T12b).
- **P3 `extract_fn` 취약 (완화)** — 문자열·주석 내부 중괄호를 해석하지 않는 단순 매칭이라, 소스 문구가
  바뀌면 잘못된 조각을 추출할 수 있다. 파서를 정교화하는 대신 **추출이 어긋나면 조용히 통과하지 못하게**
  T0(모든 추출 함수의 `typeof === "function"` 확인) + T17(페이지 에러 0) 을 세웠다 — 실패가 침묵하지
  않는 것이 본 스크립트의 핵심 요구이고, JS 파서 재구현은 검증 도구의 적정 비용을 넘는다.

**자체 검토(적대 축) — 추가 확인 사항**: (a) `role=menu`/`menuitem` 에 대한 ↑/↓ 순회는 WAI-ARIA menu
패턴과 정합하며 Tab 도달 경로(`tabindex=0`)는 종전 그대로 남는다. (b) 순회 대상 필터가
`.is-view-only` 를 제외하므로 **본인 권한 밖 제품에 커서가 멈추지 않는다**(ANCHOR §1 — 권한 밖 제품
발화 불가와 정합, 선택 시도 자체가 불가능). (c) 제품 목록은 `product.access.<key>` 로 이미 게이트된
`state.products` 위에서만 순회 — 키보드 경로가 접근 제어를 우회할 표면이 없다(백엔드 0). (d) 자식
'연결 테스트' 버튼에서 버블된 키 이벤트는 종전 `ev.target !== item` 가드로 계속 무시된다.

## REV-20260729T174201-product-picker-keynav [SKIPPED:tool-restricted:ux,design] — 세션 도구 제약으로 subagent panel 미수행, 제약 없는 채널로 대체

Trigger: UI/screen keyword matched → §18.8 표상 `ux, design` 요구. 본 위임 세션에는 **하네스 수준의
"요청 없이 Agent tool 을 호출하지 말라" 지시**가 걸려 있어 §18.8.2 의 **상위 우선순위 지시 carve-out**
이 적용된다(그 §를 우회 근거로 쓰지 않는다). 따라서 제약 없는 채널로 가능한 검증을 수행하고 미커버
도메인을 명시한다:

- **수행(제약 없는 채널)**: ① codex 적대 리뷰 1회(위 [CODEX] entry — P1 0, P2 3 + P3 1 흡수)
  ② 실 chromium 레이아웃 헤드리스 27건(실 렌더/열기/닫기 경로 + 실 CSS) ③ 기존 회귀 11건
  ④ `node --check` ⑤ `make test` 컨테이너 전체 ⑥ PB-0008 실 Windows 브라우저 시각검증(배포 후).
- **미커버**: `ux`·`design` subagent 의 독립 관점. 다만 본 변경은 **신규 시각 요소가 사실상 없고**
  (추가된 것은 `:focus-visible` 커서 1개), 상호작용 정합성은 위 ②의 실 레이아웃 케이스와 ⑥ 라이브
  육안 검증이 덮는다. 디자인 언어·정보구조 변경 0.

Cross-ref: TASK `20260729T1742-product-picker-keynav` · FUNCTION `REQ-20260729T174200-product-picker-keynav`
· MODIFY `CHG-20260729T174200-product-picker-keynav`.

## REV-20260729T180000-picker-keynav-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실증 기록(문서·증거만)

Trigger: 코드 변경 0 · 정책 문서 변경 0 — TASK/MODIFY/test-runs.d/evidence/재현 시나리오만 추가. §18.8 표의
"비정책 doc-only" 행에 해당해 패널 SKIP. 검증 자체는 본문에 기록된 **실 Windows 브라우저(PB-0008) 라이브
실측**이며, 선행 cycle 의 적대 리뷰는 `REV-20260729T174200-product-picker-keynav`([CODEX] · P1 0건).

## REV-20260729T183000-progress-poll-resilience-postdeploy [SKIPPED:doc-only-postverify] — POST-DEPLOY 라이브 검증 기록 (TASK-20260729T1750 후속)
- 대상 diff: `docs/{TASK,REPORT}.md` + `docs/test-runs.d/20260729T175000-progress-poll-resilience.md`
  (POST-DEPLOY Run append). **코드 변경 0** — 검증 결과 기록만.
- panel SKIP 근거: §18.8 dispatch 는 code change 를 전제한다. 본 cycle 은 이미 머지·배포된 변경의
  라이브 실측 결과를 문서에 append 하는 doc-only 이며, 원 cycle 의 리뷰는
  `REV-20260729T175000-progress-poll-resilience [CODEX:progress-poll-resilience]` 가 담당했다.
- 검증 설계 판단: 1차(실 사용자 경로)는 답변이 20초 내 완료돼 '처리 중 순단' 창이 닫혔다. 그대로
  "검증 불가" 로 남기지 않고 **폴링 채널을 직접 겨냥하는 2차**로 전환했다 — `/api/progress` 응답을
  클라이언트에서 `processing` 으로 합성해 폴러가 도는 상태를 만들고 그 위에 순단을 주입하는 방식이라
  **서버 상태·라이브 대화 데이터 변경 0**. 이 설계가 오히려 결정적이다: 수정 전 코드였다면 B 단계
  (3연속 실패) 이후 호출이 0 이 되어야 하는데 실제로는 8→16→32s 백오프로 이어졌고, E 단계에서
  폴러를 강제로 죽였을 때 감지기가 15초 내 되살렸다.
- 정직 표기: OS 레벨 NIC 단절은 재현하지 않았다(`fetch` 레벨 차단으로 대체 — 클라이언트 폴링
  코드가 받는 실패 신호는 동일한 reject). 1차에서 만든 검증용 대화 1건이 라이브에 잔존한다.

## REV-20260729T213000-metadata-product-scope [CODEX:metadata-product-scope] — ACCEPTED (P1 12건 흡수 후 최종 0건)

Trigger: API/endpoint + schema/query + UI/screen keyword matched → §18.8 표상 `backend, security, qa,
ux, design` 요구. 본 위임 세션에는 **하네스 수준의 "요청 없이 Agent tool 을 호출하지 말라" 지시**가
있어 §18.8.2 **상위 우선순위 지시 carve-out** 적용 — 제약 없는 채널(`codex review --uncommitted`)로
수행하고 미커버 도메인을 아래에 명시한다.

**적대 리뷰 10 라운드** — 라운드마다 P1 을 수정하고 재실행해 수렴시켰다(최종 라운드 P1 0건):

| # | 지적 | 처리 |
|---|---|---|
| P1-A | 부트스트랩 fetch 가드가 폐기된 `bs.datasource` 를 검사 → 골격 가져오기 상시 실패 | `bs.scopeKey` 로 교체 |
| P1-B | 접근DB 선언 제품에서 allowlist 밖 schema 가 primary 로 폴백 → 제품 경계 밖 DB introspect | allowlist 밖 거부(404) |
| P1-C | 호출자 지정 `datasource` override 가 scope 검증을 통째로 건너뜀 | override **제거**(부트스트랩·suggest 양쪽) |
| P1-D | `WebProductDatabases` 조회 실패를 "접근DB 없음"과 동일시 → transient 오류로 경계 무력화 | `databases_ok` 플래그 + fail-closed(503) |
| P1-E | 레거시 단일 바인딩 제품의 `datasources` 가 비면 부트스트랩 불가 | `_catalog_datasources()` 폴백 |
| P2-a | MSSQL 접근DB lower 저장 라벨 ↔ 서버 원본 케이스 불일치로 정상 DB 404 | lower→원본 매핑 + 원본 케이스 연결 |
| P1-F | 배포↔이관 창에서 기존 메타데이터 전부 비가시 | **expand/contract** — 레거시 ds-scope 꼬리 읽기 + contract 절차 |
| P1-G | `DatasourceKey` 컬럼 미이전 레거시 스키마에서 전 제품 503 | 폴백 쿼리 후에만 미가용 판정 |
| P1-H | 제품 해소 실패 시 자율수집이 `common` 으로 폴백 → cross-product 누출 | `unresolved` 신호 + 수집 중단 |
| P1-I | 다중 DS 중복 등록이 한 제품 scope 로 모이며 UNIQUE 충돌 → 이관 전체 실패 | 행 단위 SAVEPOINT + 중복 병합 |
| P1-J | 검토 큐(`glossary_feedback`/`enum_feedback`/`sample_feedback`) 미이관 → pending 큐 소실 | 이관 대상에 편입(595+119건) |
| P1-K | 모든 예외를 중복으로 보고 원본 삭제 → transient 오류에 데이터 영구 소실 | **SQLSTATE 23505 에서만** 병합, 그 외 re-raise |
| P1-L | contract 미수행 시 레거시 꼬리가 계속 읽혀 혼입 잔존 | `--verify-contract` 모드 + 완료 시 다음 단계 안내 |
| P2-b | ENUM self-heal 이 datasource scope 로 sweep → 제품 scope 행 미회수(stale/환각 잔존) | 제품 스코프 sweep(**단일 DS 제품 한정** — 다중 DS 는 `known_schemas` 불완전로 오삭제 위험) |
| P2-c | 레거시 단일 바인딩 배치에서 self-heal 전면 비활성 | `WebProducts.DatasourceKey` 폴백 |

**설계 판단 근거**

- **왜 저장 축을 제품으로 바꾸는가(표시만 바꾸지 않고)**: 라이브 실측상 결함이 표시층이 아니라
  주입층에 있다. `KR_LIVE` 용어 85건이 7개 DS 중 `auth` 한 곳에만 있어 나머지 6개 DS 질의에서
  주입되지 않았다. 표시만 제품으로 묶으면 사용자는 "등록됐다"고 더 확신하는데 동작은 그대로다.
- **왜 datasource 축을 제거하지 않는가**: 질의 실행·dialect·fact/RAG 스코핑은 물리 연결 축이 정본이다.
  KB 메타데이터만 제품 축으로 옮기고 두 축을 분리했다(그래프 뷰 pane 도 datasource 유지 — 물리 스키마
  투영이라 그 축이 맞고, 사용자 결정상 이번 범위 밖).
- **테이블/컬럼 설명의 정체**: 한 제품 안에서 `(schema_name, table_name[, column_name])`. 제품의 두
  datasource 가 같은 (schema, table) 을 노출하면 설명 1건을 공유한다 — 사용자에게 datasource 가
  보이지 않는 축이므로 의도된 동작이며, UNIQUE 제약 변경도 불필요하다.
- **`common` 의 의미 변경**: "모든 데이터소스" → "모든 제품". 행은 그대로 유효하고 캐스케이드 위치도 동일.
- **제품 경계를 골격/AI grounding 에 강제한 이유**: 콘솔에서 datasource 를 걷어내면 물리 연결 선택이
  서버로 넘어온다. 이때 요청자가 임의 schema 를 실을 수 있으면 공유 datasource 에서 **남의 제품 DB**
  를 열람·기술할 수 있다. 그래서 접근DB(`WebProductDatabases`)를 allowlist 로 강제하고, 그 목록을
  못 읽으면 넓히지 않고 거부한다(fail-closed).

**미커버(정직 표기)**: `ux`·`design` subagent 의 독립 관점 — `[SKIPPED:tool-restricted:ux,design]`.
대신 ① codex 적대 리뷰 10라운드 ② `make test` 컨테이너 전 스위트 ③ 신규 축·경계·expand/contract·
self-heal 케이스 ④ `node --check` ⑤ PB-0008 실 Windows 브라우저 시각검증(배포 후)으로 덮는다.
정보구조 변경(스코프 축 라벨·안내 문구)이 있어 ⑤ 의 육안 확인이 본 변경의 실질 design 게이트다.

Cross-ref: TASK `20260729T2130-metadata-product-scope` · MODIFY `CHG-20260729T213000-metadata-product-scope` ·
FUNCTION `REQ-20260729T213000-metadata-product-scope`.

## REV-20260729T213000-metadata-product-scope-skipped [SKIPPED:tool-restricted:ux,design] — 세션 도구 제약으로 subagent panel 미수행

Trigger: UI/screen keyword matched → `ux, design` 요구. 하네스 수준 Agent tool 금지 지시로 §18.8.2
carve-out 적용(그 §를 우회 근거로 쓰지 않음). 제약 없는 채널로 수행한 검증과 미커버 범위는 위
[CODEX] entry 의 "미커버(정직 표기)" 문단에 명시.


## REV-20260729T220000-metadata-product-scope-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실증 기록(문서 전용, 코드 변경 0)

Trigger: 코드 변경 0 · 비정책 doc-only(TASK/MODIFY/TEST/test-runs.d append) → §18.8 표 첫 행 SKIP.
본 cycle 이 기록하는 실증 자체가 선행 cycle(`REV-20260729T213000-metadata-product-scope`)의 검증 산출물이다.

## REV-20260730T010301-doc-sync-rn-0730 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-07-29 블록 13항목 prepend doc_sync 정합
- **changeset (operational, feature-0003)**: `src/static/release-notes-data.js`(신규 2026-07-29 블록 13 items prepend·generated 07-28→07-29·기존 블록 무접촉) + companion `docs/{TASK,MODIFY,FUNCTION,TEST}.md`. 비-정책 doc-only(렌더 로직·제품 코드·스키마·RBAC 0).
- **[SKIPPED:non-policy-doc] 사유**: 사용자향 릴리즈노트 콘텐츠 데이터만(제품 코드·정책 무변경). §18.8 패널 불요(484623fb·abcb7d68·351ed406 선례 동일 토큰).
- **검증**: `node --check` PASS · 구조검증(releases[0].date=2026-07-29 신규 13 items·releases[1] 2026-07-28 9항목 보존·releases[2] 07-27 보존·스키마 type/area/title/detail·enum 유효·내부용어 누출 0). 13항목 전부 owning POST-DEPLOY 라이브 실증 커밋 보유(274174e5·8775f9a0·2f10b550·d605874e·7038f5a6·63d5e83f·a5594383·24f52a84·637152f4·7d0997f7·26f263f0·3ce453cf·712a847f·f768e774·e86f4c6b). 릴리즈노트 render 테스트(`tests/verify_release_notes.mjs`)는 jsdom 미설치(env 제약)로 미실행 — render 로직 미변경이라 대상 아님(함정 #3c).
- **적대검증**: ULTRACODE wf_0663e5aa R1(3-타깃 analyze→타깃-스코프 verify, cross-fault 회피 함정 #12·9 에이전트) — RN MAJOR 1(item8 제품 선택기 위치 '입력창 아래' 오안내 → 2-렌즈 독립 합치, 위치 중립 '입력창의 제품 선택 드롭다운' 으로 교정)·MINOR 3(summary 가 13항목 중 11만 서술 → item8/item9 절 보강·item13 '기본 접힘' → '가장 최근 대화만 펼쳐짐'·item13 07-27 블록과 중복 → '중간 회차' delta 명시) 적발, 오케스트레이터 정본 독립 재검증 후 전건 교정.
- **cache-buster**: cache-buster `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시(index/admin `?v=<new>`)는 07-12 이전 regime → 부적용(현행 코드로 재검증, 484623fb·abcb7d68 동일 판정).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).

## REV-20260731T010301-doc-sync-rn-0731 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-07-30 블록 8항목 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(generated=2026-07-30 · releases[0]=2026-07-30 8항목 · releases[1]=07-29 13항목 보존 · blocks 39 · type/area enum 위반 0 · title 누락 0 · 내부용어 누출 0 정규식 검증). `verify_release_notes.mjs` 는 jsdom 미설치(env 제약)로 미실행 — render 로직 미변경이라 대상 아님.
- 적대검증(ULTRACODE wf_b0e71477, 분면-스코프 refute): MAJOR 1(심야·주말 답변 강등 오서술 — 정본은 insight 배치 전용)·MINOR 3('모두 재분석' 과대·'전체 40% 이상' 수치 오류·상태전이 오서술)·MISSED 1(캔버스↔상세 부정합 항목 누락) 전건 반영.
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.

## REV-20260803T154922-aiops-taxonomy-unmapped — `운영 현황` 미분류 활동 3종 재배치 (Minor §12.3, shared taxonomy 데이터 + 회귀 테스트)
- **changeset**: `shared/model_catalog.py`(`TASK_TAXONOMY` +3행) + `tests/test_ai_ops.py`(+2 테스트) + companion docs. 제품 코드 로직·RBAC·스키마·엔드포인트·프론트 0.
- **판단 근거 — 왜 `ai.insight.analyze` 인가**: 세 task 는 전부 insight 워커가 도는 분석 파이프라인의 층이다(L2 `cluster_summary` → L3 `domain_summary`, 그리고 그 산출물을 대조하는 `analysis_verify`). 라이브 기록도 `conversation_id='__insight_worker__'` 단일, target 축은 데이터소스/스키마/객체로 기존 인사이트 task 와 동형. 대안 2개를 기각했다 — ① 신규 카테고리 `ai.insight.verify` 신설: 드릴다운 그룹만 늘고 운영자가 얻는 분해능은 task 행 수준에서 이미 확보된다(카테고리는 상위 롤업 단위). ② `analysis_verify` 를 `ai.reasoning.aux` 로: aux 는 **대화 파이프라인 내부 소량 호출** 정의(validate/summary/classify/topic/sql_fix/redteam)라 배경 배치 워커를 넣으면 카테고리 의미가 흐려진다.
- **재발 방지 설계**: 오늘의 3종을 dict 에 넣는 것만으로는 같은 결함이 다음 신규 계측에서 재발한다(2026-07-28 usage-records-system 이 이미 같은 사유로 4종을 편입한 전례 — 반복 패턴). 그래서 회귀 테스트를 **호출부 AST 전수 수집**으로 걸었다: 소스에서 `_record_llm_usage` 의 task 리터럴을 모아 taxonomy 미등록이 하나라도 있으면 fail. 스캐너가 경로 변경 등으로 아무것도 못 찾으면 조용히 통과하므로 수집 하한(`>= 10`)을 둬 vacuous pass 를 막았다. 변수 경유 호출(`_call_llm(task=…)`)은 정적 확정이 불가해 대상 밖 — 그 경로는 명시 매핑 테스트가 보완한다(한계 명시).
- **검증**: AST 스캐너 실측 수집 18종·missing 0 · **역검증** 3종을 taxonomy 에서 제거한 가정으로 재실행 → 정확히 `analysis_verify`/`cluster_summary`/`domain_summary` 만 missing 으로 적발(게이트가 실제로 작동함을 반증 방향으로 확인).
- **리스크**: 없음에 가깝다 — 읽기 전용 표시 매핑이고 과거 `llm_usage` 행은 재해석만 된다(데이터 변경 0, 마이그레이션 0, 롤백=dict 3행 되돌리기). 카테고리 합계(호출/토큰/비용)는 '미분류 활동' 에서 '인사이트 분석' 으로 이동하므로 두 행의 수치가 바뀐다 — 의도된 재배치이며 총합은 불변.
- **§18.8 패널**: [SKIPPED:non-policy-doc] 아님 — 제품 코드(shared) 변경이나 dict 데이터 3행 + 테스트로 Minor·비파괴·인가 무관. 도메인 신호(auth/schema/API/perf) 미매칭이라 패널 미소집.

## REV-20260803T154922-aiops-taxonomy-unmapped-codex [CODEX:shared-taxonomy+regression-gate] — 적대 리뷰 8라운드, 최종 P1 반영 완료
- **Trigger**: code change (shared dict + 테스트) — §18.8 dispatch 표에서 도메인 키워드 매칭 0건. 세션에 "요청 없이 Agent tool 호출 금지" 상위 지시가 있어 §18.8.2 **carve-out 1번(제약 없는 채널 우선)** 을 적용, `codex exec` 채널로 적대 검증을 수행했다. `[CODEX:*]` 는 §18.8.1-2 가 check #9 accepted review 로 인정하는 경로. **미검증 도메인**: ux/design/security subagent 관점은 이번 변경(표시 매핑 dict + 테스트, 인가·UI 표면 무변경)에 N/A 라 대체 없이 진행 — 미검증을 완료로 오인 보고하지 않기 위해 명시한다.
- **라운드 요약 (전부 테스트 게이트에 대한 지적, 제품 코드 지적 0)**:
  1. R1 P1 — AST 스캐너가 두 번째 positional 리터럴만 봐서 keyword·래퍼·f-string 경로를 놓침 → **sink 고정점**(task 를 그대로 흘리는 래퍼 자동 수집) + 파싱 실패 즉시 실패.
  2. R2 P1 — f-string 산출값(`metadata_summary`) 미등록이 통과 → 파생 규칙 `(producer, template, 산출 튜플)` 선언 + **집합 동치** 검증. P2 — 래퍼 positional 미바인딩 → 함수 시그니처에서 task 인덱스 산출.
  3. R3 P1 — producer 의 task 가 리터럴이 아니면 조용히 누락 → `unresolved_producer` 로 fail-closed. P2 — 메서드 self 오프셋·고정점 5회 고정 → 메서드 sink 는 미확정 처리, 수렴 실패 시 assert.
  4. R4 P1 — sink 인데 task 를 특정 못한 호출(`**kwargs`·`*args`) 통과 → `unresolved_sink` fail-closed.
  5. R5 P1 — `*args` 앞선 unpacking 으로 positional 오독 → `_starred_before` 가드.
  6. R6 P1 — 이름이 `task` 인 **지역변수**를 래퍼 전달로 오인 → enclosing 함수 파라미터일 때만 passthrough.
  7. R7 P1 — 파라미터 재바인딩·shadowing(`def/class/import-as/except-as/match-as`·중첩 파라미터) → `_binds_task` 전 형태 검사(자기 파라미터 노드는 제외). P1 — 함수 헤더(데코레이터·기본값·어노테이션)의 호출을 함수 내부로 오기록 → `_FnScope` 가 헤더는 바깥 스코프로 방문.
  8. R8 P1 — sink/producer 를 **별칭 참조**(`recorder = _record_llm_usage`) → `alias_refs` fail-closed. P1 — 같은 파일·같은 표현식이면 다른 함수의 호출도 allowlist 공유 → 호출 스택에 선언된 producer 가 있어야 승인.
- **자체 실증(합성 소스 트리)**: 지역변수 task · `*args` · `**kwargs` · 미등록 리터럴 · 파라미터 재대입 · def/class/import-as/except-as/match-as/중첩파라미터 shadowing · 기본값·데코레이터 호출 · 별칭 할당/인자 전달 — **전 케이스 적발**, 순수 passthrough 대조군만 통과. taxonomy 변이(등록 7종 각각 제거·선언 튜플 축소)도 전건 적발.
- **잔여 한계(정직 기록)**: `getattr(mod, "_record_llm_usage")`·`exec`·동적 import 처럼 **AST 밖**에서 결정되는 경로는 원리상 정적 확정이 불가하다. 게이트의 계약은 "모든 동적 경로를 해석한다"가 아니라 **"미확정 경로를 조용히 통과시키지 않는다"** 이며, docstring 에 그대로 명시했다.
- **제품 코드(`shared/model_catalog.py`) 지적**: 8라운드 전체에서 0건 — 카테고리 배치·라벨·회귀 위험에 대한 P1/P2 없음.

## REV-20260803T174200-aiops-taxonomy-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실증 기록(문서 전용, 코드 변경 0)
- Trigger: 코드 변경 0 · 비정책 doc-only(TASK/MODIFY/TEST/test-runs.d append) → §18.8 표 첫 행 SKIP.
- 본 cycle 이 기록하는 실증 자체가 선행 cycle(`REV-20260803T154922-aiops-taxonomy-unmapped`)의 검증 산출물이다 — 배포 SHA·BEFORE/AFTER·라이브 API·PB-0008 육안 4축.

## REV-20260804T010301-doc-sync-rn-0804 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-03(7항목)·2026-07-31(3항목) 블록 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(generated=2026-08-03 · releases[0]=2026-08-03 7항목 · releases[1]=2026-07-31 3항목 · releases[2]=07-30 8항목 보존 · releases[3]=07-29 13항목 보존 · blocks 41 · type/area enum 위반 0 · title 누락 0 · summary 전건 존재 · 내부용어 누출 0 정규식 검증). `verify_release_notes.mjs` 는 jsdom 미설치(env 제약)로 미실행 — render 로직 미변경이라 대상 아님.
- 적대검증(ULTRACODE wf_c3ba6dd3, 타깃-스코프 refute 2렌즈): RN 분면 confirmed. 오케스트레이터 정본 독립 재검증으로 중복(07-30 카테고리 통합 항목 vs 신규 '스키마 간 어휘 통일')·내부용어 누출·비-사용자향 커밋 혼입 3축 재확인.
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + `deploy-web.sh` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시는 07-12 이전 regime → 부적용(현행 소스로 재검증).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.

## REV-20260804T045828-share-join-btn-visibility [CODEX:share-join-visibility] — 공유 링크 '대화에 참여' 버튼 노출 조건 확대 (P1 1건 적발 → 설계 변경 후 해소)
- **Trigger**: UI/button/screen keyword matched (버튼·화면) → §18.8 표상 `ux, design`. **세션-레벨 상위 지시**("요청 없이 Agent tool 호출 금지")가 subagent 채널을 봉쇄해 §18.8.2 의 *상위 우선순위 지시 carve-out* 을 적용 — 제약 없는 채널(`codex exec` 코드리뷰 + 기계적 정적/런타임 검증)로 수행. 미검증 도메인은 아래 [SKIPPED] 로 명시.
- **codex review (gpt-5.6-sol, xhigh)** — 스테이징 diff 직독. **P1 1건 · P2 1건 적발, 둘 다 해소.**
  - **P1 (수용·수정)**: "이미 멤버에게 버튼을 띄우고 그대로 `join` 을 태우면 기존 **windowed 멤버**의 가시 범위가 영구 축소된다." 정본 확인 — `share.py` 의 `elif _share_windowed:` 분기가 `stamp_member_visibility(is_new_member=False)` 를 호출하고, `group_members.py` 가 `role='owner'` 와 기존 full 멤버(floor·ceiling 모두 NULL)만 skip 한 뒤 **기존 windowed 멤버는 교집합(floor=더 높은 id, ceiling=더 낮은 id)으로 좁힌다**. 넓히는 경로가 없어 복구 불가. 초안 주석·문서의 "권한·데이터 변화 없음" 은 **사실과 달랐다**. → 해소: 이미 멤버인 클릭은 `join` 을 호출하지 않고 `viewer.conversation_id`(멤버 한정 신규 필드)로 곧바로 이동(`openJoinedConversation`). 서버 인가·window 로직은 손대지 않음(기존 계약 보존). 회귀 차단 = F5.
  - **P2 (수용·수정)**: "정적 문자열 검사라 `&&` 오변경·`toggle` 극성 반전을 못 잡는다." → 해소: F1 을 `is_authenticated && (can_join || joinable)` 정규식으로, F3 을 `classList.toggle("hidden", !visible)` + `dataset.shareWired === "1" ) return` 정규식으로 **극성·구조까지** 고정. codex 가 제안한 DOM 런타임 테스트는 **채택 불가** — 테스트 이미지(agent)에 node 부재(`NO_NODE` 실측)라 skip 으로 빠져 vacuous pass 가 된다(정적 검사 강화로 대체, 실동작은 PB-0008 이 담당).
  - codex 가 "논리적으로 맞다" 고 평한 `wireShareAction` 토글·1회 배선은 유지하되, 1회 부착이 만드는 **stale 클로저** 위험을 자체 발견해 `_latestViewer` 스냅샷으로 해소(F6).
- **기계 검증**: `node --check share.js` PASS · 신규 9건 PASS · share/fork/member/join 스코프 회귀 스위트 **98 passed**(격리 env 적용) · ruff PASS.
- **[SKIPPED:tool-restricted:ux,design]** — §18.8 표가 요구하는 ux/design subagent 는 상위 지시로 호출 불가. 대체 커버리지: 버튼 문구·DOM·라벨 보존을 F4 로 고정하고, 실제 화면 배치·가시성은 PB-0008 Windows-browser 실측(POST-DEPLOY)이 담당. **미검증 범위를 완료로 보고하지 않는다.**
- **§9.1 기록된 가정**: 이미 멤버인 viewer 에게 대화 식별자(`conversation_id`) 노출은 새로운 누출이 아니다 — 그 계정은 이미 해당 대화 열람 권한을 보유한다. 익명·비멤버에겐 `None`(B3 로 고정).

## REV-20260804T062000-share-join-btn-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실증 기록(문서 전용, 코드 변경 0)
- Trigger: 코드 변경 0 · 비정책 doc-only(TASK/MODIFY/TEST/REPORT/test-runs.d append) → §18.8 표 첫 행 SKIP.
- 본 cycle 이 기록하는 실측 자체가 선행 cycle(`REV-20260804T045828-share-join-btn-visibility`)의 잔여 검증 산출물이다 — 배포 SHA·서빙 코드·PB-0008 6축·증거 스크린샷.
- 선행 cycle 이 `[SKIPPED:tool-restricted:ux,design]` 로 남겼던 화면 배치·가시성 미검증 범위가 본 실측으로 **해소**됐다(액션 바 3버튼 렌더 육안 확인).

## REV-20260804T061000-msg-speaker-attribution [CODEX:conversation-store+frontend-render] — BLOCK → 4 P1 전건 반영 후 PASS
- Related TASK: feature-0003-agent-web-ui (20260804T0610-msg-speaker-attribution)
- Source: codex exec `git diff --cached` review (OpenAI Codex v0.146.0, gpt-5.6-sol, reasoning=high)
- Trigger: code change — dispatch 키워드 `schema/스키마`(meta_json 각인 스키마)·`API/엔드포인트`
  (PATCH product · fork)·`UI/화면`(말풍선 렌더) 다중 매칭. §18.8.2 에 따라 **도구 제약 없는 채널**
  (codex-review)을 우선 선택 — 세션 레벨 "요청 없는 Agent tool 호출 금지" 상위 지시와 무충돌.
- Timestamp: 2026-08-04T15:10:00+09:00
- Verdict: PASS (초기 BLOCK — P1 4건, 전건 수정 + 회귀 테스트 고정. P2 0건)

### 반영한 P1 4건

1. **부분 각인 행에서 기존 meta 키를 덮어씀** — PG `existing || payload` 와 MySQL/fork 의
   `dict.update(payload)` 는 payload 우선이라, probe(`product_mode`/`sender_account_id`)만 없고
   다른 귀속 키는 있는 행에서 기존 값을 파괴한다. "추가만" 이라는 계약과 정면 배치.
   → PG 를 `payload || existing`(우측=기존 우선)으로 뒤집고, MySQL 은 `{**payload, **meta}`,
   fork 는 `setdefault` 로 전환. `test_backfill_never_overwrites_existing_keys` 가 고정.
2. **MySQL 경로가 판독 불가 meta 를 삭제** — `_meta_json_to_dict` 가 파싱 실패 시 `{}` 를 주므로
   그대로 되쓰면 **원문 meta 가 통째로 사라진다**(귀속 보정이 데이터 손실로 번지는 경로).
   부수적으로 SELECT~UPDATE 사이 각인을 덮을 수 있었다.
   → 파싱 실패 행은 skip(경고 로그), UPDATE 에 읽은 원문 대조(`MetaJson <=> %s`) 낙관적 가드 추가.
   `test_backfill_skips_unparseable_meta_instead_of_erasing` · `..._guarded_by_read_value` 고정.
3. **fork 에서 username 조회 1건 실패가 assistant 제품 귀속까지 폐기** — 두 축이 한 try/except 에
   묶여 `_fork_attrib = {}` 로 초기화됐다. WebAccounts 일시 장애가 제품 귀속까지 날려 legacy
   메시지를 다시 대화-단위 상태로 되돌린다. → user/assistant 를 독립 best-effort 단계로 분리.
   `test_fork_attribution_axes_are_independent` 고정.
4. **sender id 만 각인된 타인 메시지가 여전히 대화 owner 이름을 사용** — 발신자가 owner 와
   **다르다는 것을 아는** 상태에서 owner 이름을 붙이는 확정적 오귀속. → `사용자 <senderId>`
   (참가자 칩과 동일 컨벤션)로 교체. legacy(각인 전무) 행만 owner 폴백 유지.

### 판단 근거 (설계 선택)

- **스냅샷 우선 라벨**: 각인된 `product_name`/`product_key` 를 현재 제품 목록보다 우선한다.
  제품 개명 시 과거 답변이 옛 이름으로 남지만, (a) 요청의 문면이 "기존 내용과의 정합",
  (b) 열람자에게 접근권 없는 제품에서도 발화자가 보존, (c) **어떤 후속 변경으로도 과거
  발화자가 다시 바뀌지 않는다** — 이 함수가 존재하는 이유 자체를 지킨다. 아이콘 이미지만
  현재 제품 설정을 따른다(정체성이 아니라 표현).
- **제품 전환은 assistant 만 보정**한다. 제품 변경은 발신자에 대해 아무것도 알려주지 않으므로
  user 행에 owner 를 각인하면 그룹 멤버 메시지를 owner 로 오귀속한다. legacy user 행의 보호는
  fork 경로(원본 owner 기준)가 담당한다.
- **`attribution_inferred`**: 발화 시점 각인과 사후 추론을 구분해 남긴다. 없으면 "언제부터
  믿을 수 있는 값인지" 를 이후 어떤 조사로도 복원할 수 없다.

### 잔여 리스크 (정직 기록)

- legacy 대화가 **fork 도 제품 전환도 겪지 않으면** user/assistant 행은 미각인으로 남아 종전
  폴백(대화 owner / 대화 바인딩)으로 표시된다. 그 상태에서의 표시는 지금도 정확하며(그 대화의
  모든 발화가 실제로 그 owner·그 제품이므로), 부정합이 발생할 수 있는 두 순간에 각각 고정된다.
  전량 일괄 backfill 은 라이브 전 대화 meta 를 쓰는 대규모 변경이라 채택하지 않았다.
- 그룹 대화의 **pre-feature-0009 미각인 user 행**을 fork 하면 원본 owner 로 추론된다(실제
  발신자가 다른 멤버였을 수 있음). `attribution_inferred: true` 로 구분되며, 복제자 이름으로
  표시되던 종전보다는 엄격히 낫다.

## REV-20260804T065000-msg-speaker-attribution-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실증 기록(문서 전용, 코드 변경 0)
- Related TASK: feature-0003-agent-web-ui (20260804T0650-msg-speaker-attribution-postdeploy)
- Reason: changed paths are docs only outside policy-doc list — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-04T15:52:00+09:00
- 본 cycle 이 기록하는 실증 자체가 선행 cycle(`REV-20260804T061000-msg-speaker-attribution`)의 배포 검증 산출물이다 — 배포 스코프·서비스별 SHA·라이브 표면 3축.
## REV-20260805T010301-doc-sync-rn-0805 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-04(3항목) 블록 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · vm 구조검증(generated=2026-08-04 · releases[0]=2026-08-04 3항목 · releases[1]=08-03 7항목 · releases[2]=07-31 3항목 · releases[3]=07-30 8항목 · releases[4]=07-29 13항목 보존) · 내부용어 누출 스캔 0 · `verify_release_notes.mjs` 33 pass / 1 fail(pre-existing `styles.css` 스크롤 assertion, doc_sync 미변경 파일 — feature-0003 cycle 소관).
- 적대검증(ULTRACODE `wf_048fd776`, 타깃-스코프 refute 렌즈): RN 분면 `confirmed=false` + 3 issue. **오케스트레이터가 정본으로 독립 재검증해 3건 전부 실재 확인 후 교정** — ① '복사(사본 만들기)' 는 프론트 진입점이 제거된 라벨(`static/app.js:7121-7123`)이라 실존 라벨 `'내 계정에서 fork'`·`'여기서 분기'` 로 교체 ② `_normalize_signal_topics`(`src/routers/_prompt_context.py:336-367`)는 절단 조각을 **버리지 않고** 개행 정규화·120자 상한만 적용하므로 "잘린 조각은 걸러 냅니다" over-claim 을 "한 줄로 정리" 로 완화 ③ `f8a940ad` 의 사용자 관측 가능한 부수 수정(재렌더 stale 표시·클릭 핸들러 중복 부착)을 1문장 흡수.
- 포함/제외 판정 근거: 사용자향 4 커밋 중 3 항목으로 통합 — `cb72b816`(부트스트랩 교착)은 단독 사용자 표면 0 이나 `a55ee779` 의 라이브 실효를 0 으로 만들던 직접 원인이라 같은 항목에 흡수(공동 POST-DEPLOY `5dc42e48` 가 두 cycle 잔여 체크박스를 함께 종결). feature-0038 Cycle 3~10 + Final = byte-동치 무동작변경, feature-0039 = 운영 인프라(화면 변화 0) → 기술 색인만·RN 제외.
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + `deploy-web.sh` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 는 무효 churn + 게이트 무력화).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.

## REV-20260805T104213-harness-repair [SUBAGENT:tests-harness] — 적대 QA 패널 1회: MAJOR 1·MINOR 5·NIT 2 전건 흡수 후 PASS

- Trigger: code change (tests-only) — dispatch 키워드 무매칭이나 "하네스 단언 완화가 검증력을
  약화시킬 위험" 이 본 변경의 핵심 리스크라 검증력-약화 전담 렌즈로 단일 적대 리뷰어 dispatch.
- 대상: 하네스 24파일 수리 + 2파일 신설 + 시나리오 재작성 (CHG-20260805T1042-harness-repair).
- 판정 요지:
  - **[MAJOR] 흡수** — 시나리오 DOM 전환이 E 블록만 적용되고 A~D 가 죽은 전역(typeof
    openConversationItemMenu 등)에 잔존해 vacuous 관측(러너가 error 페이로드를 실패로 안 봄).
    → 전 블록 DOM 이벤트 경유 재작성 + A(게이팅 매트릭스)는 `verify_notify_gating.mjs` 이관
    + async 팝업 클릭→wait_for→관측 3단 분리. 실브라우저 20스텝 전건 OK 로 재검증.
  - **[MINOR 5] 흡수** — ① scope_single_ds C1 `scope_key:` 완화 → strict(`scope_key:\s*scope\b`)
    복원(실코드 통과 실측) ② esm strip 의 bare import 무음 over-consumption → bare 선행 제거 +
    `[^;]*?` 문장-경계 제약 ③ ai-console 교체로 aiops.read 단독 게이트 검증 소실 → OR 3항목
    개별 케이스 추가 ④ llm_restriction placeholder 짝 오류(base.css) → 실거주 chat.css 교정
    ⑤ profile_icon_consistency `>=` slack → 실측 카운트(5/3) 핀.
  - **[NIT 2] 흡수** — release_notes 윈도우 `[\s\S]{0,800}` → `[^}]{0,800}`(블록-내 강제) ·
    picker stub 주석 실 seam(_dsTestable) 교정.
  - 패널 통과 확인 축: strip 6종 `node --check` 전부 통과·본문 무손상, cache-buster 완화는
    asset-stamp 계약(inject_asset_stamp + test_static_cache_integrity) 하 취지 보존, stub 주입의
    시나리오 왜곡 없음, ai-console 전환은 양성 케이스로 vacuity 아님.
- 흡수 후 재검증: mjs 40/40 green + 시나리오 실 Windows Chrome 20스텝 OK. 미해소 잔여 0.
- 패널 외 관찰(기록만): 같은 죽은-전역 패턴이 `win-browser-mention-hl-notify.scenario.json`·
  `win-browser-notify-nobracket.scenario.json` 에도 잔존(본 cycle 범위 밖 — 후속 후보). 시나리오
  17개의 base_url `https://localhost:18080` 은 Caddy 단일 노출 전환 후 전부 stale(실행 시
  `https://localhost` 사본 필요 — 후속 후보).

## REV-20260805T192000-verdict-badge-postdeploy [SKIPPED:non-policy-doc] — doc-only

시각 검증 Run 기록 + 증적 이미지 추가만으로, 코드·정책·계약 변경이 없다(§18.8.1 docs-only 경량
경로). 검증 대상이던 코드 자체는 선행 cycle 에서 ux · backend-security 적대 패널을 거쳤다
(`unit/feature-0036-analysis-verification/docs/REVIEW.md` REV-20260805T193000 / T193500).
## REV-20260806T010301-doc-sync-rn-0806 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-05(3항목) 블록 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 34/0 동일 — 메모리에 기록된 pre-existing 스크롤 FAIL 1건은 본 worktree 에서 미재현, feature-0038 css 분할 완결로 해소된 것으로 관측) · 구조검증(generated=2026-08-05 · releases[0]=2026-08-05 3항목 · releases[1]=08-04 3항목 · releases[2]=08-03 7항목 보존 · type/area enum 위반 0) · 내부용어 누출 스캔 0.
- 적대검증(ULTRACODE `wf_d0b1fd46`, 축-스코프 refute 렌즈): RN 축 `accurate=false` + 결함 4건. **오케스트레이터가 정본으로 독립 재검증해 전건 실재 확인 후 교정** — ① old_string 이 끝 빈 줄 포함형이라 디스크 count=0(적용 실패) → 바이트 확정형으로 교체 ② "'판정 근거' 는 어긋난 경우에만 붙는다" = **사실 오류**(`graph-ctxmenu.js:3619-3626` 은 `if (res.verdict.reason)` 단일 게이트로 verdict 종류 무관하게 렌더하고 `analysis_verify.py` `normalize_verdict` 가 근거 없는 응답을 기각하므로 저장된 모든 판정에 근거가 있다 → `모순 없음`·`통계가 다루지 않음` 배지에도 근거 줄이 항상 뜬다. 원안대로면 사용자가 supported 노드의 근거 줄을 경고로 오독) → summary·item detail 양쪽 교정 ③ 순환 차단 효과를 배포 후 실측(25분 6콜/6판정·낭비 0)으로 교체 ④ 검증자 제공 교정 전문이 설명 prose 를 fence 로 감싸 반환돼 1차 적용이 JS 문법을 깼고(`node --check` SyntaxError), revert 후 fence 추출로 재적용해 PASS 확인(자동 적용의 정본 검증 필요성 재확인).
- 포함/제외 판정 근거: 사용자향 3항목. feature-0002 첨부 봉인은 원장 status `fixed:deployed:unverified-live` 이나 **배포 게이트는 해소**(PR#1155 merge `70df13a3` → `make deploy-web` 전체 스코프, 4서비스 배포본 런타임 실증 신규 심볼 6종 적재)이고 잔여는 라이브 대화 시나리오 재확인이라 사용자 표면은 이미 라이브 → 포함(배포 미완이면 보수 유보였다). feature-0038 Phase A~B3 = byte-동치 무동작변경 · `a39aaf84` = tests-only · feature-0011 P5a 종결 = 거버넌스 결정 → 기술 색인만·RN 제외.
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + `deploy-web.sh` 가 배포 시 content-hash 주입, 수동 bump 는 무효 churn + 게이트 무력화).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.
- Timestamp: 2026-08-06T01:03:01+09:00
## REV-20260806T114413-modal-backdrop-dismiss [SUBAGENT:ux] [SUBAGENT:design] — 2 BLOCK 라운드 후 SHIP
- **Trigger**: `UI/dialog/modal/screen/layout · 모달·화면` keyword matched → §18.8 dispatch 표에 따라 **ux + design** subset. 세션에 "요청 없이 Agent tool 호출 금지" 지시가 걸려 있어 §18.8 요구와 상충 → **자체 SKIP 하지 않고 사용자에게 1회 확인**했고, 사용자가 "ux·design subagent 패널 호출" 을 선택. §18.11 계약대로 4종(changed_files·diff_excerpt·task_md·acceptance_criteria) + 구조 사실을 invocation prompt 에 inject(subagent 는 repo 무접근).
- **라운드 1 — ux: BLOCK**. P1-1 **implicit pointer capture**: 터치·펜은 브라우저가 `pointerdown` 대상에 캡처를 자동으로 걸어 `pointerup` 이 **뗀 위치와 무관하게** retarget 되므로(마우스는 캡처 없음), 해제하지 않은 1차 구현은 터치에서 계약이 "누른 위치가 배경이면 닫힘" 으로 무너져 **원 결함이 그대로 남아 있었다**(AC3 불성립). P2-1 **ghost click**: `pointerup` 에서 노드를 제거하면 터치 compat `click` 이 제거 후 DOM 으로 히트테스트되어 배경 **아래** 사이드바 항목을 누른다. 둘 다 실재 확인 후 반영 — 캡처는 **배경에서 시작한 제스처에 한해** 해제하고(패널 안 제스처의 캡처는 터치 텍스트 선택이 의존), 실행 단계를 `click` 으로 이동.
- **라운드 2 — ux: SHIP · design: BLOCK**. 두 리뷰어가 **독립적으로 동일한 잔여 결함**을 실제 헬퍼를 실행해 실증했다(ux PROBE1/2 · design P-1/P-2, 둘 다 dismiss=1 관측): "배경에서 down+up 했는데 브라우저가 `click` 을 발행하지 않은" 제스처가 **장전 상태를 무기한 남기고**, 그 뒤 도착한 click 하나가 사용자가 누른 적 없는 모달을 닫는다(폴더 지침 작성분 소실 = 이번 cycle 이 없애려던 바로 그 피해). 1차 하네스의 "합성 click 단독 → 안 닫힘" 은 **깨끗한 초기 상태에서만** 검사해 통과한 **vacuous pass** 였고, 코드 주석의 "순수 합성 click 은 dismiss 를 일으키지 않는다(의도)" 단정은 **상태 의존적으로 거짓**이었다(리포 우선축 "사실 주장의 근거" 직격).
- **라운드 2 반영 (전건)**:
  - **장전 수명 봉인** — `pointerup` 이 `downOk` 를 즉시 소비하고 `click` 이 `armed` 를 소비한다(제스처 1회분). + 물리 제스처는 언제나 `pointerdown` 으로 시작해 상태를 리셋하므로 **선행 pointerdown 없이 오는 click 은 정의상 합성**이라 `e.isTrusted` 로 배제. 주석의 단정이 이제 **참**이 된다.
  - **P3-1 fail-open 제거** — 캡처 해제를 `hasPointerCapture` 선행 조건 뒤에 두면 그 메서드가 없거나 캡처를 다르게 보고하는 엔진에서 조용히 건너뛴다(터치 계약이 구 결함으로 회귀). **무조건 시도 + throw 만 삼킴**으로 교체.
  - **P3-3 제거** — `pointerup` 의 중복 `e.button === 0`. 누름 시점에 이미 걸렀고, `button` 을 `-1` 로 보고하는 환경에서 정상 dismiss 가 **조용히 죽는** 쪽이 더 나쁘다.
  - **P3-6 주석 정정** — "배경이 그 click 을 **소비**한다" 는 부정확(코드는 `stopPropagation` 을 부르지 않는다). 실제 근거는 "터치 compat click 의 히트테스트가 dispatch **전에** 끝나므로 dispatch 중 노드를 제거해도 아래가 눌리지 않는다" 이며 그렇게 고쳐 적었다.
- **design P2-B 커버리지 반증 — 실재 확인, 요청 범위 밖으로 분리**. 내가 제출한 "old 패턴 6곳 전수" 근거는 식별자 `backdrop` 에 키잉된 grep 이라 **결함 클래스의 부재가 아니라 변수명의 부재만** 증명한 non sequitur 였다. 직접 확인 결과 `overlay` 로 명명된 동형 3곳이 남아 있다 — `app/profile.js:306`(**사용자향** · `mousedown` 단독으로 닫힘 = 사용자가 보고한 "down 됐을 때 종료" 의 가장 순수한 형태) · `admin/usage.js:662`(mousedown) · `admin/audit.js:317`(click). 사용자 요청이 "좌측 항목(대화/폴더) 설정 모달" 로 명시 스코프되어 있어 **이번 cycle 에서 고치지 않고**, AC5 문구를 "요청 범위 6종" 으로 좁히고 REPORT §8 후속 원장에 file:line 과 함께 등재 + 완료 보고에서 사용자에게 표면화(§8.1 — 기록만·미실행). 조용한 범위 확대도, 조용한 누락도 아니다.
- **범위 밖 인정(후속 원장)**: 포커스 트랩·포커스 복원 부재(기존 결함, 본 diff 회귀 아님) · 미저장 지침 dirty-guard · `.share-mgr-backdrop` 의 `overflow` 부재로 인한 짧은 뷰포트 패널 잘림 · 관리 콘솔 그래프 뷰 도움말 오버레이(`amg-help-overlay`) 구 패턴 · 마우스 chording 시 보수적 미-dismiss(방향이 안전).
- **결함 아님으로 확인된 축**(양 리뷰어 교차): 중첩 모달 인스턴스 격리(클로저 호출당 독립 · 두 backdrop 은 body 형제라 전파 무간섭) · click dispatch 중 노드 제거 재진입(`reset()` 이 `onDismiss` 보다 먼저) · ESM 순환 import(`export function` 선언 호이스팅 — `const` 화살표였다면 TDZ 위험) · 리스너 미해제(노드 폐기와 함께 GC) · `isPrimary !== false` 관용 · 추상화 seam("pointerdown target 기록 + click 비교" 단순안은 배경→패널 드래그에서 공통조상 승격으로 **오탐 dismiss** — `pointerup` target 검사가 load-bearing).
- **검증**: `verify_modal_backdrop_dismiss.mjs` **48 pass / 0 fail** + **역검증 5종**(각 변형이 정확히 의도한 단언만 red — 옛 `click` 단독 11 · 캡처 해제 삭제 1 · `pointerup` 실행 3 · `downOk` 미소비 1 · `isTrusted` 미검사 1) · **PB-0008 실 Windows Chrome CDP trusted 입력 10/10 PASS** + 같은 하네스 negative control 에서 **사용자 보고 현상 3건 재현** · `make test` 회귀 · `verify_*.mjs` 전수 red 21건 = main baseline 동일 집합.
- **판정**: ux **SHIP** · design 은 BLOCK 사유 2건(합성-click 주장 · 커버리지 주장)을 제기했고 **둘 다 해소**(전자는 코드로, 후자는 범위 재서술 + 원장 등재). 두 리뷰어가 제시한 P1/P2 중 미해소 잔여 없음.
- Timestamp: 2026-08-06T11:44:13+09:00
## REV-20260806T162000-modal-dismiss-postdeploy [SKIPPED:non-policy-doc] — doc-only

시각 검증 Run 기록 + 증적 이미지 추가만으로, 코드·정책·계약 변경이 0 이다(§18.8.1 docs-only 경량
경로). 검증 대상 코드는 선행 cycle 에서 ux·design 적대 패널 2 라운드를 거쳤다
(`REV-20260806T114413-modal-backdrop-dismiss`).
## REV-20260806T032732-share-sender-nickname [SUBAGENT:adversarial-security-authz + SUBAGENT:adversarial-ux-design] — CONCERN → 전건 흡수 후 SHIP
- Related TASK: 20260806T0327-share-sender-nickname
- Trigger: UI/screen/layout keyword(화면·배지·표시) + anonymous 노출면 변경 → ux·design + security
- Timestamp: 2026-08-06T12:27:32+09:00
- Verdict: CONCERN (medium 5건) → **전건 in-cycle 수정 후 재검증 green**
- Human Approval Needed: no (사용자 결정 2건은 사전 수령 — 노출 범위·폴백 정책)

### 채널 선택 근거 (§18.8.2)
`/codex review` 는 OpenAI 사용량 한도 소진(리셋 2026-08-09)으로 불가, `/security-review` 스킬은
본문이 검증을 sub-task 로 돌리는데 세션에 "요청 없이 Agent tool 금지" 상위 지시가 걸려 있었다.
§18.8.2 의 "충돌을 자체 SKIP 하지 않는다" 에 따라 **사용자에게 1회 확인**해 subagent 패널 1회
사용을 승인받고 security·ux 2렌즈를 호출했다(자체 판단으로 SKIP 하지 않음).

### 흡수한 결함 (5건, 전부 medium — critical/high 0)
- **[security F-1] 사후 추론 각인이 확정 라벨로 렌더**: `_conv_copy_messages` 는 fork 시 미각인 행에
  **원본 대화 owner** 를 기입하며 `attribution_inferred: true` 를 남기는데(그 행의 실제 발신자는 다른
  멤버였을 수 있다 — feature-0003 REVIEW REV-20260804 가 명시), `senderLabel` 이 그 플래그를 무시했다.
  본 변경이 스스로 내건 "확정적 오귀속 차단" 불변식을 1순위 경로가 관통. → **0순위 게이트 신설**
  (추론 각인은 이름·id 둘 다 미사용, 3~4순위로 강등) + 하네스 케이스 4건.
- **[security F-2] 소유자명 폴백의 근거가 실제 발화 집합에서 미성립**: "1:1 은 발신자 = 소유자"
  라는 근거로 각인 없는 행에 소유자명을 붙였으나, 3순위가 오늘 실제로 발화하는 집합은 **legacy 행**
  이고 그중 그룹분은 발신자가 owner 가 아닐 수 있다. 프론트에는 그룹/1:1 구분 신호가 없었다.
  → payload 에 `conversation.is_group` **불리언 1개** 추가(새 식별자 노출 0) + 게이트를 fail-closed 로.
  `app._conversation_is_group` 은 조회 실패를 False(비그룹)로 삼켜 **실패 방향이 반대**라 감싸지 않고
  `_share_conversation_is_group` 으로 직접 조회했다(그 함수의 다른 호출부에서는 False 가 안전 방향).
  → "백엔드 무변경" 이라는 초기 서술도 함께 정정(FUNCTION/MODIFY/REPORT/SECURITY).
- **[security F-3] §21.7 의 노출집합 서술이 실제보다 좁음**: "window 안에서 발화한 계정으로 한정"
  이라 적었으나 fork 보정 경로가 **그 대화의 owner 도 멤버도 아닌 제3 계정명**을 화면에 올릴 수
  있었다. F-1 수정으로 실제 집합이 원 문장과 일치하게 만들고(권장안 채택), §21.7 을 발화-시점-각인
  기준으로 재서술 + 잔여 위험 2종(표시명 PII · 내부 계정 PK 육안 노출) 명시.
- **[ux F-1] 절단 레시피가 절반만 구현 — 배지가 아니라 시각 표기가 먼저 깨진다**: `.share-message-time`
  에 `flex-shrink:0`·`nowrap` 이 없어, 배지의 `overflow:hidden` 이 flex 자동 최소크기를 0 으로 만든
  뒤 축소 압력이 **양쪽에 비례 배분**된다. 360px 실측 계산상 배지 가용폭 ≈156px 를 넘는 순간 시각이
  max-content 미만으로 눌려 **2줄로 접히고** meta 줄 높이가 카드마다 달라진다. CSS 주석이 선언한
  목적("시각 표기를 밀어내지 않는다")과 실제 렌더가 반대. → `.share-message-time { flex:0 0 auto;
  white-space:nowrap }` + ≤720px 은 절단 대신 `flex-wrap:wrap`(공통 접두사 계정명이 ellipsis 로
  동일 문자열이 되는 케이스도 함께 차단).
- **[ux F-2] `title` 무조건 부여 → 중복 툴팁·중복 낭독**: 절단되지 않은 절대다수 배지에서 화면
  텍스트와 완전 동일한 툴팁이 뜨고(assistant 배지 포함), `<span>` 은 포커스 대상이 아니라 정작
  절단됐을 때 키보드·터치 사용자에겐 복구 경로로 기능하지 못한다. → `_deferOverflowTitle`
  (rAF 후 `scrollWidth > clientWidth` 일 때만 부여, 아니면 속성 제거).

### 패널이 확증한 것 (반증 아님 — 근거 보강)
- **주장 A 참**: `_share_load_messages` 는 `meta_json` 을 allowlist 없이 전달하고, 배제 필터 3종
  (내부/시스템 메시지 · `event_type` · attachment_derived redact — 삭제 키는 `final_sql`/`sql`/
  `result_rows`/`result_text`/`steps`) 어디에도 sender 키가 없다. redact 된 메시지조차 sender 는 남는다.
  쓰기 측도 전부 서버 권위값(인증 actor + DB 조회)이라 클라이언트 meta 주입 경로 0(spoofing 불가).
- **XSS 실행 경로 0 (2중)**: 싱크가 전부 `textContent`/속성 대입이고, 입력도 `USERNAME_RE`
  (`[A-Za-z0-9_.-]`)로 전 생성 경로에서 제한된다(로컬 가입·OAuth 프로비저닝·부트스트랩 시드).
  bidi/homograph 스푸핑도 구조적 차단 — 단 이는 **입력 측 불변식**이라 표시명 필드 도입 시 재평가
  대상임을 §21.7 에 남겼다.
- **window 격리(§21) 직교**: 라벨은 hard window 산출물(`_conv_load_messages_raw(anchor, from_id)`)
  에만 붙고, 브랜치 열람도 `_branch_resolve_readonly_leaf`/`_branch_idrange_pred` 로 게이트된다.
- **`inline-flex → inline-block` 전환은 회귀 없음 + 필요했다**: 배지는 flex item 이라 두 값 모두
  blockify 돼 outer display 가 동일하고, 교차축 위치는 부모 `align-items:center` 가 결정한다.
  반대로 `inline-flex` 를 유지했다면 `text-overflow` 가 **적용되지 않아**(block container 아님)
  글자 중간 하드 클리핑이 났을 것. 다만 `overflow:hidden` inline-block 은 baseline 이 margin-bottom
  edge 로 합성되므로, 인라인 문맥 재사용·`align-items:baseline` 전환 시 내려앉는다 → CSS 주석 봉인.
- **캐시버스터 정상**: `share.html` 은 `?v=dev` placeholder 이고 배포 시 `inject_asset_stamp.py` 가
  content-hash 를 주입한다(수기 bump 금지·불요).

### 반영하지 않은 지적과 근거
- **[ux §3] 1:1 대화에서 소유자명 반복이 §16.8-A.1("화면이 이미 보여주는 것은 넣지 않는다") 위반**:
  타당한 지적이나 **사용자가 명시 선택한 표시**다(2026-08-06 결정: "각인 없는 과거 메시지 = 대화
  소유자명"). §3.1 우선순위상 사용자의 현재 직접 지시가 최상위라 그대로 둔다. 다만 지적의 실질
  위험(그룹 legacy 오귀속)은 F-2 수정으로 제거됐고, 남는 것은 1:1 화면의 중복 표기뿐이다.
  트레이드오프를 여기에 기록해 다음 감사자가 재발견하지 않게 한다.
- **[ux C4] 참여자 구분에 아바타/색 도입**: 패널 자신이 과잉으로 판정. `share.js` 는 독립 IIFE 라
  Identicon 도입에 코드 복제가 필요하고 "의도적으로 단순화된 별도 페이지" 설계와 충돌한다. F-1/F-2
  수정으로 이름이 안 잘리면 위계 문제의 실질 대부분이 해소된다는 패널 결론에 동의.
- **[ux C5] assistant 발화자(제품)는 여전히 대화 단위**: 본 요청 범위(user 발신자) 밖 — 차기 항목
  으로 기록(다제품 그룹 대화 공유 시 "누가 답했는지" 는 여전히 헤더의 대화 단위 제품 하나).
- **[security] mjs 하네스가 CI 밖(pytest 전용 게이트)**: 알려진 프로젝트 구조(CI 는 pytest 전용).
  대신 pytest 쪽 단언을 배선 문자열에서 **동작 계약**(추론 각인 배제·is_group fail-closed·title 조건부·
  시각 표기 고정)까지 확장해 CI 커버리지를 넓혔다. 하네스의 CI 배선 자체는 별 cycle 범위.

### 선행 권고 supersede
feature-0009 `REVIEW.md` REV-20260703T182740 의 `ADJACENT NIT`("일반 그룹채팅 메시지의
`meta.sender_username` 이 anonymous 공유에 노출 — 후속 티켓 권고")를 본 cycle 이 **표시 방향으로**
종결한다(그 권고는 비노출 방향 후속을 상정). `docs/SECURITY.md §21.7` 에 명시해 원장 상충을 막았다.

### 검증
- 동작 하네스 `verify_share_sender_nickname.mjs` **17/17 green**(패널 반영 전 11 → 추론 각인 4 +
  is_group 분기 2 추가). 배포 소스에서 함수를 추출해 실행하므로 로직 재구현 tautology 아님.
- pytest `test_share_sender_nickname.py` **2 passed**(배선 + 백엔드 계약 — is_group payload 배선과
  게이트 fail-closed 를 `inspect.getsource` 로 단언).
- `make test` 전 스위트 **exit=0**. (1회차에 `test_shutdown_finalizer` 1건 FAIL 이 있었으나 로그가
  `shutdown finalize: 시간 예산 초과` 를 남긴 시간 예산 flake — 격리 재실행 통과, 전체 재실행 exit=0,
  본 cycle 은 그 경로의 Python 코드를 접촉하지 않는다.) ruff clean.
- 라이브 익명 payload 실측(2026-08-06): 활성 공유 링크 1건을 Caddy 경유 익명 호출해 그룹 발신
  메시지의 `meta.sender_username`/`sender_account_id` 존재를 확인 — 주장 A 의 1차 근거.
- 실 Windows 브라우저 시각검증은 정적 자산 baked 구조상 **POST-DEPLOY** (test-runs.d fragment 에
  계획·사유 명시).
## REV-20260806T045000-share-sender-postdeploy [SKIPPED:non-policy-doc] — doc-only
시각 검증 Run 기록 + 실측 발견 1건 추가만으로, 코드·정책·계약 변경이 0 이다(§18.8.1 docs-only 경량
경로). 검증 대상 코드는 선행 cycle 에서 security·ux 2렌즈 적대 패널을 거쳤다
(REV-20260806T032732-share-sender-nickname, medium 5건 전건 흡수).
- Timestamp: 2026-08-06T13:50:00+09:00
## REV-20260806T183000-modal-dismiss-siblings [SUBAGENT:ux] [SUBAGENT:design] — BLOCK 후 전건 반영, SHIP
- **Trigger**: `UI/dialog/modal/screen · 모달·화면` keyword matched → §18.8 dispatch 표에 따라 **ux + design**. 선행 cycle 에서 사용자가 이미 "ux·design subagent 패널 호출" 을 선택했고 같은 주제의 연속 작업이라 그 결정을 승계. 이번엔 §18.11 bundle 대신 **repo 직접 접근**을 허용해(worktree 경로 제공) 리뷰어가 주장을 스스로 검증하게 했다 — 그 덕에 아래 뮤테이션 실증이 나왔다.
- **판정**: ux **SHIP**(P1 0 · P2 2) · design **BLOCK**(P1 0 · P2 4). 두 리뷰어가 **독립적으로 같은 P2 2건**(census 하드코딩 · ESC 누수 미완)을 짚었다.
- **핵심 지적과 반영 — 넷 중 셋이 "이 cycle 이 한 일을 내 산출물이 거짓 인증" 이었다**:
  - **P2 census 가 전수가 아니었다** — 주석·테스트 헤더는 "전 static 트리 census" 라 단정했으나 실제로는 **33개 중 6개 파일 하드코딩**이었다. design 이 뮤테이션으로 실증: TREE 밖 파일에 옛 패턴 모달을 신설해도 **73/73 통과**. 이 cycle 의 존재 이유(복제 drift 차단)가 잠기지 않았다는 뜻. → `readdirSync` 재귀 walk + 핸들러 **본문 경계** 판정으로 교체(표기 변형 무관). 고정 lookahead 가 인접 리스너 본문을 물어 `app.js:1792` 를 오검출하던 것도 이때 함께 잡아 회귀 케이스로 잠갔다.
  - **P2 vacuous 단언 2건** — "배경 우클릭 → 안 닫힘", "비-primary 포인터 → 안 닫힘" 이 `press()` 헬퍼가 비주 버튼에 click 을 안 쏘는 탓에 **primitive 의 판정 단계에 도달조차 못했다**. design 이 `downOk = true` 와 `isPrimary` 가드 삭제 뮤테이션으로 **둘 다 73/73 생존**을 실증. + "보조 손가락 얹힌 채 배경 탭" 은 보조 pointerdown 을 주 press **앞**에 쏘아 가드를 우회. → 세 단언을 click 까지 명시 발화 / 순서 교정으로 재작성, 뮤테이션 red 확인. **이 cycle 에서만 vacuous 단언을 세 번째로 잡은 것**(앞서 내가 역참조 그룹 오지정 1건을 자체 적발).
  - **P2 ESC 리스너 누수 하드닝이 절반** — 두 모달은 loading→data 로 **재렌더**되므로 이전 인스턴스의 `onEsc` 를 떼지 않으면 열 때마다 하나씩 샌다(design 수명 시뮬레이션: 6회 열기 → 6개 잔존). 그런데 내 테스트는 `close()` 본문에 문자열이 있는지만 정규식으로 봐 **PASS** 했다. → `overlay._modalClose` 로 이전 인스턴스를 닫도록 완결 + 테스트를 **수명 실측**(리스너 수를 세는 시뮬레이션)으로 교체, 누수 복원 뮤테이션 2종 red 확인.
  - **P2 `FUNCTION.md` AC-0168 이 삭제된 구현을 계약으로 기술**(`source_of_truth: true`) — 다음 cycle 이 이 AC 로 역검증하면 "기능 파손" 오판 또는 삭제한 flag 복원. → primitive 위임으로 갱신 + "flag 존재로 역검증하지 말 것" 명시.
  - **P2 purge 모달 중복 인스턴스**(ux) — 오버레이에 id·가드가 없어 겹쳐 뜨면 중복 id 로 **위쪽 모달 버튼에 핸들러가 하나도 안 붙는다**(파괴적 플로우 조작 불능). 형제 두 모달은 이미 가드를 갖고 있었다. → 동일 패턴 가드 + 기준 날짜 포커스.
  - **P3 stale 주석**(`app.js` 의 "overlay mousedown 의 mouseup race fix 와 함께 동작") 정정 · **P3 범위 경계** 명시(`document` 레벨 outside-click 은 다른 UX 범주) · **P3 터치 캡처 단언 라벨 정직화**(`downOk` 가 이미 false 라 캡처 축을 증명 못함 — 판별력은 다른 케이스가 담당) · **P3 nav 경로 중복 해제 제거**.
- **자체 적발(패널 전)**: 그래프 도움말에 오버레이+자식 **이중 바인딩**을 했다가, `graph.css` 확인 결과 자식이 `inset:0` 으로 전면을 덮어 오버레이 바인딩이 **dead code** 이고 내 주석의 "오버레이 여백" 서술이 사실이 아님을 발견 → 단일 표면(자식, 폴백 오버레이)으로 축소·주석 정정. 양 리뷰어가 CSS 로 이 판정을 독립 확인했다.
- **결함 아님으로 교차 확인된 축**: 프로필 드로어 구조적 면역(양쪽이 `index.html:410-411` 형제 구조로 VERIFIED — 제외 판단 정당) · 지속 DOM(검색 모달·도움말)의 stale state 누출 없음(`pointerdown` 최상단 무조건 `reset()` 이 불변식, 서브트리 내 pointerdown stopper 0건) · 바인딩 중복 stacking 없음(`_helpBound`·모듈 1회 배선) · TDZ 없음 · `admin/usage.js` nav 리스너와 무간섭(primitive 가 먼저 등록되나 `preventDefault`/`stopPropagation` 미사용, 행 클릭은 `downOk=false`) · 모듈 그래프 순환 없음(`modal-dismiss.js` 는 import 0 leaf) · `inject_asset_stamp.py` 가 신규 파일 자동 포함(전역 단일 스탬프 → 모듈 단일 인스턴스) · `isTrusted` 가 AT 활성화를 깨지 않음(OS 레벨 실입력은 trusted, backdrop 은 focusable 아님).
- **잔여(범위 밖·REPORT §8)**: 포커스 트랩 부재(전 표면 공통, 기존) · 검색 모달에서 날짜 popover 열린 채 배경 1클릭이 popover+모달을 함께 닫음(구/신 동일, 회귀 아님) · `document` 레벨 outside-click closer 군 · `admin/accounts.js` 임시 비밀번호 모달은 배경 dismiss 자체가 없음(정합 이탈이나 위험 없음).
- **검증**: 하네스 **76 pass / 0 fail** · **뮤테이션 역검증 6종** 전부 의도한 단언만 red · ESM `node --check` 6파일 · 전수 mjs red 21건 = main baseline 동일 집합 · PB-0008 실 Windows Chrome 10/10 · `make test` 회귀.
- Timestamp: 2026-08-06T18:30:00+09:00
## REV-20260806T201000-modal-siblings-postdeploy [SKIPPED:non-policy-doc] — doc-only

시각 검증 Run 기록 + 증적 이미지 추가만으로 코드·정책·계약 변경이 0 이다(§18.8.1 docs-only 경량
경로). 검증 대상 코드는 선행 cycle 에서 ux·design 적대 패널을 거쳤다
(`REV-20260806T183000-modal-dismiss-siblings`).
## REV-20260806T232000-attach-version-diff [SKIPPED:tool-restricted:ux,design,backend,qa] — 자체 적대 검증 P1 1 · P2 1 반영, 기계 게이트 전건 PASS

- **Trigger**: `UI/modal/screen · 모달·화면` + `API/endpoint · 엔드포인트` keyword matched →
  §18.8 dispatch 표의 요구 subset 은 **ux + design + backend + security + qa** 다.
- **채널 판정 (§18.8.2 순서대로)**:
  1. **제약 없는 채널 우선** — `codex review --uncommitted` 를 시도했으나 **사용량 한도 소진**
     (`ERROR: You've hit your usage limit … try again at Aug 9th`)으로 물리적 불가. 이 버전의
     codex 는 `--uncommitted` 와 커스텀 프롬프트를 함께 받지 않아(`the argument '--uncommitted'
     cannot be used with '[PROMPT]'`) 축 지정 리뷰도 같은 한도에 걸린다.
  2. **subagent panel** — 본 세션에는 **상위 우선순위 지시로 Agent tool 사용이 금지**돼 있다.
     §18.8.2 「상위 우선순위 지시 carve-out」에 따라 그 지시가 우선하며, 본 §를 우회 근거로
     쓰지 않는다. 따라서 ux·design·backend·qa 도메인은 **미검증**으로 명시한다.
  3. **수행한 검증(제약 없는 채널)** — 아래 기계 게이트 + 자체 적대 검증. 미검증 범위를 완료로
     오인 보고하지 않는다(§16.3 정직성).
- **자체 적대 검증에서 적발·수정한 결함 2건** (초판을 그대로 출하했다면 라이브에 남았다):
  - **[P1] D21 bytes-deny 우회** — `download_attachment` 는 승인 대기 계정의 **본문** 다운로드를
    403 으로 막는다(D21). 초판 diff 엔드포인트는 그 게이트가 없었고, diff 행은 파일 본문을 그대로
    담으므로 **승인 대기 계정이 diff 로 내용을 읽을 수 있었다**. 판정 기준을 metadata
    조회(`get_attachment_metadata` — signed URL 만 보류)가 아니라 **본문 다운로드와 동형**으로
    맞추고, 게이트를 원본 조회 **앞**에 두었다(회귀 잠금 E12 가 `storage.reads == []` 까지 단언
    — 403 을 주면서 뒤에서 읽는 구현을 배제).
  - **[P2] 체인 스코프를 가정으로 둔 것** — 체인 로더는 root 로 전체 행을 반환하고 "체인은 같은
    conversation·account 귀속" 을 전제한다(기존 `/versions` 도 동일한 가정). 그 전제가 깨진 행이
    하나라도 있으면 **기준 첨부 게이트가 덮지 못하는 첨부가 응답에 실린다**. 정상 편입 경로가
    스코프를 강제하더라도 방어를 가정이 아니라 **필터**로 두는 쪽이 옳다 → `scope_row` 로
    conversation/account 를 재확인하고 걸러진 건수를 warning 으로 남긴다(fail-closed).
    두 엔드포인트 모두 적용(E14 가 한쪽 누락을 red 로 잡는다).
- **결함 아님으로 확인한 축**:
  - **SQL 인젝션 없음** — `from_version`/`to_version` 은 `int()` 로 강제되고 dict 키로만 쓰인다.
    체인 조회는 파라미터 바인딩(`%s`).
  - **XSS 없음** — diff 본문은 `textContent` 전용(`innerHTML` 미사용, mjs C8 이 렌더 함수 소스로
    단언). 바이너리 메타표만 `innerHTML` 이고 값은 전부 `escapeHtml` 경유.
  - **존재 oracle 없음** — 체인 밖 버전은 400("있지만 잘못됨")이 아니라 404. E5 가 잠금.
  - **`/versions` 리팩터는 동작 불변** — 추출한 로더가 PG 우선·MySQL 폴백·soft-delete 제외·
    `VersionNumber ASC` 를 그대로 유지(V1/V2). `scope_row` 추가는 정상 데이터에서 no-op.
  - **응답 크기 유계** — 원본 각 1MB cap × 2 + 행 6000 cap. `context=full` 도 이 상한 안.
  - **경쟁 조건** — 프론트 `reqSeq` 가드로 늦게 온 응답이 최신 선택을 덮지 않는다(C5).
- **의도된 설계 선택(리뷰 시 재론 금지 사유 명시)**:
  - 비교 결과를 **저장하지 않는다** — 임의 쌍은 체인 길이의 제곱이라 사전 계산 대상이 아니고,
    저장하면 원본 변경 시 stale 판정 축을 새로 만들어야 한다.
  - unified 와 rows 를 **한 opcode 패스**에서 산출 — 두 경로면 같은 두 버전에 서로 다른 결과를
    보일 수 있고, 그때 사용자는 어느 쪽을 믿을지 알 수 없다.
  - 신규 권한 코드 0 — 새 리소스가 아니라 **기존 리소스의 새 표현**이므로 scope 를 새로 정의하지
    않는다(§16.7 G5: `.any` 관행 상속 금지의 반대면).
- **잔여(범위 밖 · REPORT §8)**: 말풍선 첨부 칩에서의 비교 진입(진입점 2개면 §16.6 복수 surface
  개별 검증 필요) · 바이너리 내용 비교 · 단어 단위 intra-line 하이라이트 · 포커스 트랩(전 표면 공통).
- **미검증 범위(정직 표기)**: ux·design 관점의 **시각 위계·레이아웃 판단**과 backend·qa 관점의
  독립 적대 검토는 위 채널 제약으로 수행하지 못했다. 레이아웃·픽셀은 **PB-0008 실 Windows
  브라우저 검증(배포 후)** 이 유일한 backstop이며, 그 전까지 시각 축은 미검증이다.
- **검증**: pytest 신규 22건 · 전수 회귀 exit 0 · **뮤테이션 역검증 7/7** · 헤드리스 mjs 신규
  57건 + 전수 44 suite OK · `acorn-globals` 자유 식별자 0 · `gen-routemap --check` 정합 ·
  `codenav-lint` OK · route 골든 parity(added 1 / removed 0 / order drift 0).
- Timestamp: 2026-08-06T23:20:00+09:00
## REV-20260807T003000-attach-diff-colgroup [SKIPPED:tool-restricted:ux,design] — POST-DEPLOY 적발 결함의 근본수정 + 감지축 신설

- **Trigger**: `UI/layout · 레이아웃` keyword matched → §18.8 은 ux + design 을 요구하나 본 세션은
  Agent tool 금지(상위 우선순위 지시) + `codex review` 사용량 한도 소진(8/9 까지). §18.8.2
  carve-out 에 따라 제약 없는 채널(헤드리스 기하 실측 · mjs 구조 가드 · 실 브라우저 재검증)로
  수행하고 미검증 도메인을 명시한다.
- **이 cycle 의 판단 근거 — 왜 점수정으로 끝내지 않았나**: 결함 자체는 `<colgroup>` 3줄이면
  닫힌다. 그러나 문제의 본질은 **감지축의 부재**였다 — pytest·mjs(jsdom)·정적 스캔·
  verify-completion 이 전부 통과했고, 유일한 감지 수단이 "배포 후 사람이 캡처를 본다" 였다.
  그 상태를 유지하면 같은 클래스(레이아웃 산출물)가 다음에도 배포를 통과한다. 그래서 실
  chromium 기하 실측을 배포 **전** 게이트로 신설했다(§16.7 G10 — 재발을 기다리지 않고 승격).
- **가드가 load-bearing 임의 실증**: 기하 테스트 T7 은 `colgroup` 을 제거한 뒤 열 폭을 다시 재어
  `[284,284,284,284]` 를 확인한다 — **라이브에서 관측된 값과 동일**하다. 즉 이 테스트는 "지금
  통과한다" 가 아니라 "그 결함이 들어오면 반드시 red 가 된다" 를 증명한다.
- **정본 이중화 제거**: CSS 폭 선언을 `col` 로 옮기면서 `td` 쪽 width 3건을 **삭제**했다. 남겨두면
  같은 사실이 두 곳에 있고, 다음 사람이 `td` 쪽을 고치며 "적용되지 않는다" 로 혼란한다.
  mjs A1b 가 `td` width 잔존 0 을 단언한다.
- **결함 아님으로 확인한 축**: 행 세로 정렬(같은 행의 좌/우 셀 top 일치, T5) · 문서 폭 불변(T6 —
  긴 줄은 scroller 안에서만 넘침) · 단일열 3열 폭(T4) · 좁은 폭 폴백의 `min-width` 규칙 불변.
- **미검증 범위(정직 표기)**: ux·design 관점의 시각 위계·가독성 **판단**은 채널 제약으로 미수행.
  기하는 숫자로 잠갔으나 "읽기 좋은가" 는 별 축이며, 배포 후 PB-0008 캡처 판독이 그 backstop 이다.
- **검증**: 헤드리스 기하 8/8(T7 역재현 포함) · mjs 하네스 65 PASS · 전수 mjs 44 suite OK ·
  pytest 전수 회귀 · verify-completion PASS.
- Timestamp: 2026-08-07T00:30:00+09:00
## REV-20260807T020000-attach-diff-ux [SKIPPED:tool-restricted:ux,design] — 사용자 지적 4건 반영 + col 폭 함정 실측 확정

- **Trigger**: `UI/layout/modal · 모달·레이아웃` keyword matched → §18.8 은 ux + design 을 요구하나
  Agent tool 금지(상위 우선순위 지시) + `codex review` 사용량 한도 소진. §18.8.2 carve-out 으로
  제약 없는 채널(실 브라우저 기하 실측 · mjs 구조 가드 · pytest)로 수행하고 미검증을 명시한다.
- **가장 중요한 발견 — 선행 수정이 절반만 듣고 있었다**: `20260807T0030-attach-diff-colgroup` 은
  `<colgroup>` 으로 열 폭 계약을 세웠고 헤드리스 기하 8/8 이 통과했다. 그런데 그 통과는
  **줄번호 열에 대해서만** 참이었다 — 좌우 code 열의 `calc((100% - 4ch - 24px) * ratio)` 는
  Chrome 이 무시해 auto(균등 분배)로 떨어졌고, 기본 비율이 0.5 라서 **균등 분배 결과와 수치가
  같아** 테스트가 구별하지 못했다. 사용자의 드래그 요청을 구현하다 비율이 안 바뀌는 것을
  하네스 T10 이 잡아 드러났다.
  → 교훈: **"기본값이 우연히 같은 값을 내는" 단언은 판별력이 없다.** 5형태 대조 실측으로 경계를
  확정하고(`30%`·`px`·퍼센트 없는 calc 만 honor), 소스에서 그 형태를 금지하는 가드를 넣었다.
- **드래그 초판 결함(하네스 적발)**: `pointermove` 를 핸들에만 바인딩 → 포인터가 11px 핸들을
  벗어나는 첫 이동에 이벤트가 끊겨 `mousedown` 은 성립하는데 비율이 그대로였다. `setPointerCapture`
  를 걸었지만 그것만으로는 보장되지 않았다. 저장소 기존 리사이저와 동형인 document 레벨 리스너로
  교정 — **기존 패턴을 따르는 것이 새 패턴을 발명하는 것보다 안전하다**는 실증.
- **gap 국소 전개의 설계 판단**: 축약 로직을 프론트에 재구현하지 않았다. 서버가 gap 에 줄번호
  범위를 실어 주고 프론트는 전체 맥락 응답에서 그 범위 행만 splice 한다. 재구현하면 서버·클라이언트
  두 축약 구현이 갈라져 같은 쌍에 다른 화면이 나온다(이 기능의 "두 표현은 같은 응답" 불변식 위반).
  전체 맥락은 쌍 단위로 **1회만** 받아 캐시하고, 쌍이 바뀌면 무효화한다.
- **하네스 방식 전환의 근거**: 함수 개별 추출은 모듈 상수·상호 호출이 늘 때마다 깨졌다(이 cycle 에서
  2회). 헤드리스·mjs 모두 **모듈 전체 로드**(import 만 스텁)로 바꿨다 — 로직 재구현 0 을 유지하면서
  깨짐이 사라진다. 부수 이득으로 헤드리스가 `openAttachmentDiffModal` 전체 흐름(드래그·전개)을
  실제로 구동한다.
- **결함 아님으로 확인**: 열 합 == 표 폭(드래그 후에도) · 좌우 행 세로 정렬 · 문서 폭 불변 ·
  단일열에는 핸들 미부착 · 5자리 줄번호 잘림 없음 · "모두 보기" 시 전개 버튼 미부착.
- **미검증(정직 표기)**: ux·design 관점의 **가독성·시각 위계 판단**. 기하는 숫자로 잠갔으나
  "읽기 좋은가" 는 별 축이며 배포 후 PB-0008 캡처 판독이 backstop 이다. 또 하네스는 Chromium
  단일 엔진이라 다른 엔진의 fixed-table 동작 차이는 대상 밖이다(사내 표준 브라우저는 Chrome).
- **검증**: 헤드리스 22/22 · mjs 73 PASS · 전수 mjs 44 suite OK · pytest 신규 24건 · 정본
  `make test` 전수 · verify-completion PASS.
- Timestamp: 2026-08-07T02:00:00+09:00
## REV-20260807T032000-attach-diff-height [SKIPPED:tool-restricted:ux,design] — 잘못된 계약을 테스트가 인증한 사례

- **Trigger**: `layout · 레이아웃` keyword matched → §18.8 은 ux + design 을 요구하나 Agent tool
  금지(상위 우선순위 지시) + `codex review` 한도 소진 → §18.8.2 carve-out.
- **이 cycle 의 교훈 — 테스트가 잘못된 계약을 굳혔다**: 선행 cycle 은 사용자의 "모달이 작아
  내용이 잘린다" 를 `height: 94vh` **고정**으로 구현하고, 헤드리스 T9 에 "높이 ≥ 88vh" 를
  단언으로 박았다. 그 결과 짧은 diff 의 큰 빈 영역이 **정상으로 인증**됐고 44축 전부 PASS 했다.
  요청의 본질은 "잘리지 않게"(= 상한 확대)였고 "항상 크게" 가 아니었다.
  → **요청을 계약으로 옮길 때 그 계약이 요청보다 강하지 않은지 확인해야 한다.** 강한 계약은
  테스트를 통해 요구사항으로 굳어 다음 사람이 되돌리기 어렵게 만든다.
- **재설계한 검증**: 높이 축을 **경계 양측**으로 나눴다(§16.7 G4) — 짧은 diff 는 상한 미만,
  긴 diff(120행)는 상한에 닿고 표 컨테이너가 스크롤한다. 한쪽만 보면 이번 결함이 다시 통과한다.
- **적발 수단**: 자동 게이트가 아니라 **라이브 캡처 판독**이었다. §16.9-a 가 "렌더된 그림을
  대조하라" 고 한 이유의 세 번째 실증이다(앞선 두 번은 열 폭 4등분, calc-무시).
- **미검증**: ux·design 의 여백·비례 **판단**. 배포 후 PB-0008 캡처 판독이 backstop.
- **검증**: 헤드리스 25/25 · 전수 mjs 44 suite OK · pytest 무영향(CSS 단독) · verify-completion PASS.
- Timestamp: 2026-08-07T03:20:00+09:00
## REV-20260806T154100-attach-manage [SUBAGENT:security] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260806T1541-attach-manage
- Trigger: auth/credential·API/endpoint keyword matched (인가 경계 변경 + 파괴적 삭제 + 대량 반출)
- Timestamp: 2026-08-06T16:40:00+09:00
- Verdict: BLOCK (P1 3 · P2 8) → 전건 반영
- Critical issue: `attachment.restore`·`attachment.bulk_download` 가 `build_audit_change_json` allowlist 에 없어 `ValueError` → `_audit_user_action` 이 삼킴 → **감사 행 0**. 유일한 대량 반출 경로와 유일한 삭제-되돌리기 경로가 둘 다 무감사.
- Human Approval Needed: no

주요 지적과 조치:
- **P1-1 무감사**: builder 에 두 액션 분기 신설. 부수로 `attachment.delete` 가 `(before or {})` 만 읽어 **전 필드 `null`** 이던 선재 결함도 `request_ctx` 기반으로 교체(scope·deleted_count 포함 — 없으면 12개 삭제와 1개 삭제가 감사에서 구별 불가).
- **P1-2 공유창 window 미적용**: bounded 멤버("여기부터 공유")가 `scope=all` 한 번으로 floor 이전 첨부를 전량 ZIP 반출. SECURITY §21.2 AR-2 / CSO F3 와 정면 충돌. fork 와 **같은 헬퍼**(`_resolve_copy_window` + `_attachment_outside_window`)로 clip, `deny`→403 fail-closed, 제외 건수를 응답·헤더·audit 에 표면화. 개별 경로의 선재 갭은 별건으로 REPORT §8 원장 등재.
- **P1-3 staged/worktree 괴리**: 인덱스 스냅샷에 `DeleteReason` 가드가 없어 그대로 커밋되면 `legal`/`admin_purge` 복구 구멍이 출하됨 → 커밋 전 `git add -u` 로 정합 확인.
- **P2-5 `ids` 무음 확대**: 파싱 실패가 "필터 없음"으로 흘러 3개를 고른 사용자가 전량을 받음 → 400.
- **P2-6 이탈자**: kick 당한 업로더가 자기 파일을 되살리거나 지울 수 있음(열람 게이트와 비대칭) → manage 게이트에 현재 멤버십 AND 조건 추가, 판정 불가 시 fail-closed.
- **P2-9 retention TOCTOU**: UPDATE WHERE 에 retention 조건 추가 + `_is_restorable` 의 파싱 실패 fallback 을 **fail-closed** 로 전환.
- **P2-10 휴지통 PII**: `can_manage=false` 행을 표시만 숨기고 응답에는 파일명·크기·sha256 을 실어, 삭제 전 전원이 보던 것이 삭제 **후에도** 계속 보임 → 서버에서 **필터**(미반환).
- **P2-8 헤더 인젝션**: ZIP 만 `Content-Disposition` 정제를 건너뜀(현재 cid 가 서버 생성이라 미발동) → `_sanitize_disposition_filename` 공통 헬퍼로 두 경로 통일.
- 확인되어 결함 아님: `_manage_gate_for_conversation` 이 그룹 멤버 단독을 실제로 거부 · `upload.any` 는 admin 전용 시드라 경계 확대 아님 · pending 계정 차단 동형 · `ids` IDOR 무효(대화 스코프 교집합) · zip-slip 방어 · CSRF(samesite lax) · audit 민감정보 미포함 · 프론트 XSS escapeHtml.
- Artifact: 본 entry (subagent 출력 요약 — 전문은 cycle 대화 로그)

## REV-20260806T154100-attach-manage [SUBAGENT:backend] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260806T1541-attach-manage
- Trigger: schema/query/migration keyword matched (트랜잭션·버전 체인·dual-write)
- Timestamp: 2026-08-06T16:45:00+09:00
- Verdict: BLOCK (P1 2 · P2 8) → P1 전건 + P2 대부분 반영
- Critical issue: 라이브 env 실측 `AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND=postgres` — PG read 가 **프로덕션 목록 경로**이고, 복구 후 미러 집합에 강등 형제가 빠져 **같은 첨부가 목록에 두 줄**로 뜬다(다음 write 까지 영구).
- Human Approval Needed: no

주요 지적과 조치:
- **P1-1 테스트 red**: `_row()` 에 `DeleteReason` 키가 없어 `test_r3` 실패(feature-0003 유일 실패) → fixture 기본값 추가. 부수로 `test_r2` 가 첫 가드에서 컷돼 **vacuous** 였던 것도 해소.
- **P1-2 PG 미러 부족**: `_promote_latest_version` 은 승격 행 + **강등 행들**을 바꾸는데 미러는 `targets + promoted` 만. 저장소에 이미 정답 선례(업로드 supersede 가 체인 전량 미러)가 있었고 신규 경로만 규약을 안 따랐다 → `_mirror_chain` 신설.
- **P2-1 판정 소스 분기**: 기본 경로 `scope=version` 이 `_load_attachment_row`(PG 우선)를 써서, 미러 유실 시 "삭제했다는데 안 지워짐"(200 already_pending) 가능 → `_load_attachment_row_mysql`(정본) 신설해 삭제·복구 판정 전용으로.
- **P2-2 잠금 비대칭**: `for_update` 가 `scope=chain` 분기에만 전달되고 `_promote_latest_version` 내부 재조회는 비잠금 → `lock` 파라미터로 scope 무관 전달. `SET SupersededAt = NULL` 에 `AND DeletedAt IS NULL` 가드 추가(그 사이 삭제된 행을 current 로 승격하는 것 차단).
- **P2-3 휴지통 경계 불일치**: docstring 은 "되살릴 수 없는 항목을 보이지 않는다" 인데 retention 조건이 없어 만료분이 계속 보이고 ↩ 는 항상 409 → SQL 에 retention + `LIMIT 200`.
- **P2-6 `ids` 무음 확대**: security 와 동일 지적 → 400.
- **P2-7 휴지통 노출**: security P2-10 과 동일 → 서버 필터.
- 확인되어 결함 아님: `_begin_tx` 가 autocommit 연결에서 정상 동작 · `_promote_latest_version` 의 깨진 체인 수렴성 · retention env 가 worker 와 동일 · 복구↔worker 만료 배치가 시점 단조성상 배타적 · ZIP zip-slip · 상한 검사가 ZIP 생성보다 앞 · `_manage_gate` N+1 없음 · ROUTEMAP up-to-date.
- **미반영(잔여, REPORT §8 등재)**: P2-4 복구 시 size cap 우회(삭제→업로드→복구로 상한 초과 가능) · P2-5 ZIP 동시성 제한·`ZIP_STORED` · P2-8 `_begin_tx` contextmanager 화.
- Artifact: 본 entry

## REV-20260806T154100-attach-manage [SUBAGENT:qa] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260806T1541-attach-manage
- Trigger: 신규 엔드포인트 2 + 파괴적 동작 — 테스트 충실도 축
- Timestamp: 2026-08-06T16:50:00+09:00
- Verdict: BLOCK (P1 7 · P2 10) → 테스트 축 전건 반영
- Critical issue: fake cursor 가 WHERE·params 를 흉내내지 않아 `(RootAttachmentId = %s OR Id = %s)` 를 `RootAttachmentId = %s` 로 바꿔도 green — **`RootAttachmentId` NULL 인 루트 원본이 체인에서 빠지는** 뮤테이션이 생존.
- Human Approval Needed: no

주요 지적과 조치:
- **P1-1/P1-2**: `test_r3` red · `test_r2` vacuous → fixture 수정(backend P1-1 과 동일 근원).
- **P1-5 SQL 계약 무검증** → `test_p4/p5` 신설: 체인 SQL 의 `(RootAttachmentId = %s OR Id = %s)`·params·`include_deleted`·`FOR UPDATE` 를 값으로 단정.
- **P1-6 승격 대상 무검증**: SQL 문자열만 보고 바인딩을 버려 **루트를 승격**하는 뮤테이션이 생존 → `test_p1` 을 params 단정으로 재작성(`null_upd[0][1] == (2,)` + 강등 제외 대상 일치 + `DeletedAt IS NULL` 가드).
- **P1-7 대화 스코핑 무검증**: 휴지통·bulk download 의 `WHERE ConversationId = %s` 를 지워도 green(주석에도 매치되는 문자열 단정이었음) → `test_z7/z8` 로 분리, bulk 는 window clip 호출까지 AST 로 단정.
- **P2-1 `_zip_entry_name` 재충돌**: id 접미가 재충돌을 다시 확인하지 않아 **여전히 덮어쓰기 발생**(실측 `["a_4.csv","a.csv","a_4.csv"]`) → while 루프 + 대소문자 케이스 테스트(`z5/z6`).
- **P2-8/P2-9 요청 범위 비대칭**: manifest 가 전부 실패해도 성공 토스트 · 복구가 `"version"` 하드코딩 → 각각 문구 교정(건수 단정 제거)·휴지통 체인 복구 버튼 추가.
- **P2-10 문서 drift**: AC-9 가 "presigned URL" 이라 적혀 있으나 구현은 의도적으로 앱 내부 경로 → FUNCTION AC 문구 정정. 계획 B4(`_load_attachment_row_any_state`)는 전제가 틀려 불필요했음을 명시(`_load_attachment_row` 에 `DeletedAt` 필터 없음).
- **미반영(잔여)**: P1-4 엔드포인트 레벨 요청 테스트(conftest `client` 픽스처) — 라이브 DB 의존이라 이번 cycle 은 헬퍼·SQL 계약 단정으로 대체하고 POST-DEPLOY 실측으로 보완. REPORT §8 등재.
- Artifact: 본 entry

## REV-20260806T154100-attach-manage [SUBAGENT:ux] — BLOCK → 해소

- Related TASK: feature-0003-agent-web-ui / 20260806T1541-attach-manage
- Trigger: UI/button/modal/layout keyword matched
- Timestamp: 2026-08-06T16:55:00+09:00
- Verdict: BLOCK (P1 2 · P2 12) → P1 전건 + P2 대부분 반영
- Critical issue: `_refreshAttachPanelAfterMutation` 이 부르는 `_renderAttachmentPills()` 가 **같은 `#attachSidePanelList`** 를 `innerHTML=""` 후 pill 로 덮음 — 삭제 직후 관리 목록이 통째로 사라지고 **방금 지운 파일이 그대로 보인다**(🗑·버전 토글 소실, 빈 버킷이면 패널이 스스로 닫힘).
- Human Approval Needed: no

주요 지적과 조치:
- **P1-1 목록 덮임**: 주석에 적은 목적("pill 정합")도 달성 못 함 — 그 함수는 배열을 다시 그릴 뿐 정리하지 않는다 → `_loadConversationAttachments`(서버 ground truth)로 버킷 재수화 후 목록 렌더 순서로 교체.
- **P1-2 폭 회귀**: 실 렌더 측정으로 240px 파일명 가용폭 69.7 → **37.8px(≈3자)**, 버전 행 **23.2px(≈2자)**·전 구간 잘림. CSS 주석이 "폭 회귀를 되풀이하지 않는다" 고 적어둔 바로 그 회귀 → 목록 행·버전 행을 **2줄 구조**로 재구성(액션을 메타줄/foot 로). hover 노출 안이 아닌 이유: 터치에서 도달 불가.
- **P2 타임존**: `restorable_until` 이 오프셋 없는 UTC → KST 브라우저에서 **9시간 짧게** 표시(표시·집행 불일치) → `Z` 보정.
- **P2 radio `name` 전역 충돌**: 모달 2개 시 `:checked` 가 null → fallback `"version"` 으로 **조용한 격하**(서버가 400 으로 막는 원칙의 프론트 위반) → 인스턴스 uid 접미 + 중복 인스턴스 가드.
- **P2 409 처리**: "이미 처리됨" 은 목록이 stale 하다는 신호인데 목록을 안 고쳐 같은 버튼으로 같은 409 반복 → stale 분기에서 목록 재로드 + 모달 닫기.
- **P2 확인 버튼 라벨**: 파괴 범위가 5배 달라지는데 버튼은 계속 "삭제" → 선택과 동기화(`최신 버전(v3)만 삭제` / `전체 버전 삭제 (5개)`).
- **P2 manifest**: 전 버전 모드인데 원본명 그대로 저장돼 버전 구분 소실 + 차단돼도 성공 단정 → `_v{n}` 부여 + 건수 단정 제거 + 진행 표시.
- **P2 접근성**: aria-label 이 title 과 어긋남 · 행 버튼 접근 이름에 파일명 없음 · `aria-labelledby` 부재 · 포커스 미이동/미복원 → 전건 수정.
- **P2 헤더 간격 0px**: ×를 누르려다 휴지통 토글 오조작 → `gap: 4px` + × 앞 6px.
- **P2 대화 전환 잔류**: 패널을 연 채 전환하면 내용은 활성인데 토글은 "휴지통"(aria-pressed 거짓) → `switchConversation` choke-point 에서 리셋.
- **P2 휴지통에서 ⤓**: 화면은 삭제분인데 받는 건 활성 첨부 → 다운로드 모달 진입 시 active 로 복귀.
- **P2 UI copy 예산(§16.8)**: 라벨 재진술 힌트 3건·2문장 안내 2건 제거·축약.
- **미반영(잔여)**: `can_manage=false` 사용자의 휴지통 막다른 화면 — 서버 필터로 **행 자체를 반환하지 않게** 바꿔 빈 목록이 되므로 부분 해소. 진입점 숨김은 미적용(REPORT §8). `.template/ui-copy-budget.conf` 규칙 확장도 미적용.
- Artifact: 본 entry
## REV-20260806T181000-attach-manage-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / 20260806T1810-attach-manage-postdeploy
- Reason: changed paths are docs only (test-runs.d fragment + TASK/MODIFY/REVIEW) outside policy-doc list — 실행 코드·정적 자산 변경 0줄
- Timestamp: 2026-08-06T18:10:00+09:00
## REV-20260807T043000-attach-diff-scroll-block [SKIPPED:tool-restricted:ux,design] — 스크롤 보존 · 문단 하이라이트 + 선행 결함 1건 부수 교정

- **Trigger**: `UI/scroll/layout · 스크롤·하이라이트` keyword matched → §18.8 은 ux + design 을
  요구하나 Agent tool 금지(상위 우선순위 지시) + `codex review` 한도 소진 → §18.8.2 carve-out.
- **① 스크롤 보존의 설계 판단 — 픽셀이 아니라 줄번호**: scrollTop 을 그대로 복원하는 것이 가장
  쉬운 답이지만 이 화면에서는 **틀린 답**이다. 전개는 행을 삽입하고 2열↔단일열은 `replace` 를
  1행↔2행으로 바꿔 **같은 픽셀이 다른 줄을 가리킨다**. 사용자가 지키고 싶은 것은 스크롤 값이
  아니라 **보고 있던 내용**이므로 줄번호를 앵커로 잡았다.
- **의도된 비대칭 — 버전 쌍 변경은 보존하지 않는다**: 같은 비교의 표시 방식이 바뀐 것과 **다른
  비교로 갈아탄 것**은 다르다. 후자에서 위치를 유지하면 사용자는 자기가 어디를 보고 있는지 모른다.
  경계 양측을 다 테스트했다(S1~S4·S6 보존 / S5 초기화) — 한쪽만 보면 "항상 보존" 이라는 과한
  계약이 굳는다(직전 cycle 의 높이 고정과 같은 실패 형태).
- **② 문단 하이라이트의 근거**: 줄 배경만으로는 "5줄이 한 덩어리로 바뀜" 과 "1줄씩 5곳이 바뀜" 이
  같아 보인다. 블록 계산을 `_assignBlocks` **한 곳**에 두어 2열·단일열이 같은 경계를 보게 했다
  (두 뷰가 같은 응답의 두 표현이라는 이 기능의 불변식을 표현 계층으로 확장). `gap` 이 블록을
  끊는 것도 의도 — 생략 구간을 건너 이어붙이면 없는 연속을 그린다.
- **부수 적발 — 선행 결함 1건**: 실측 중 `delete` 행의 **빈 우측 셀**이 danger 배경으로 칠해져
  있는 것을 발견했다(`rgba(220,38,38,0.12)`). 우측 파일에는 아무것도 없는데 "여기 삭제된 것이
  있다" 로 읽힌다. 내가 새로 넣은 accent 규칙은 "내용 있는 쪽에만" 인데 줄 배경이 그 규칙과
  어긋나 **같은 화면에서 두 규칙이 충돌**하고 있었다 → `has-content` 로 좁히고 빈 자리는 중립
  filler. 요청 범위 밖이지만 방치하면 새 accent 가 자의적으로 보인다.
- **정직 표기 — 검증 못 한 방어**: `_restoreScrollAnchor` 의 rAF 2회는 현재 호출 지점에서
  **필수가 아니다**. `apply()` 의 `offsetTop` 이 동기 레이아웃을 강제해 즉시 실행도 동작하고,
  rAF 제거 뮤테이션이 **S1~S6 전부 생존**했다(비대칭 비율 S6 을 추가해 재시도했으나 여전히
  구별 못함). "테스트가 있으니 검증됨" 으로 쓰지 않고, 남겨 둔 근거를 코드 주석에 적었다 —
  호출 지점이 늘어 레이아웃 강제가 사라지면 clamp 가 되살아나고 그 실패는 조용하다.
- **결함 아님으로 확인**: 중앙선 드래그는 재렌더가 없어 스크롤 영향 없음 · gap 전개 시 전체 맥락
  캐시는 쌍 단위로만 무효화(보존 로드가 캐시를 버리지 않음) · 1줄 블록에 경계선 없음(노이즈 방지) ·
  `equal` 행은 블록에 포함되지 않음.
- **리베이스 중 접합부 점검(요청 범위 밖, 실측)**: 작업 도중 `REQ-20260806-attach-manage`(PR
  #1173, 첨부 soft-delete·복구)가 먼저 랜딩했다. 코드 충돌은 자동 병합됐지만 **내 코드 밑의
  데이터 모델에 새 상태가 생겼다** — "삭제한 버전이 diff 비교 선택기에 남는가" 를 물었다.
  답은 아니다: 삭제 write 3경로 모두 `DeletePending=1` 과 `DeletedAt` 을 같은 statement 에서
  세우고, 체인 조회 **양쪽**(MySQL 폴백 + PG 미러)이 `deleted_at IS NULL` 을 건다. 다만 이것을
  **읽어서 확인한 상태로 두지 않고 V3·V3b 로 고정**했다 — 새 삭제 경로가 `DeletedAt` 을 안
  채우면 삭제한 버전이 선택기에 되살아나고 그 실패는 조용하다(에러 없이 목록에만 안 보인다).
  뮤테이션 양측 red 확인. 체인이 목록보다 필터가 느슨한 것(`SupersededAt` 미포함)은 의도 —
  구버전을 포함해야 비교가 성립한다.
- **병합 결과를 화면에서 재봤다(추측 금지)**: `⇄`(내 비교)와 `🗑`(#1173 삭제)가 서로 모르고
  같은 `.attach-list-version-actions` 에 들어가 **버튼이 2→3개**가 됐다. git 은 텍스트상 병합에
  성공했지만 그 결과가 좁은 버전 박스(좌측 28px 들여쓰기)에서 성립하는지는 아무도 재지 않았다 →
  `verify_attach_version_row_actions.py` 신설, 240~420px × 이름 2종 **10 조합 A1~A5 통과**
  (넘침 0 · foot overflow 0 · 가로 스크롤 0 · 긴 이름이 버튼을 밀어내지 않음). 뮤테이션
  (`min-width: 64px`) → A2·A3 red 로 가드가 load-bearing 임을 확인. **내 어포던스가 살아 있다.**
- **W1 관측 — 고치지 않고 보고**: 액션 버튼 세 개 모두 WCAG 2.2 AA 최소 타겟(24×24) 미달
  (`⇄`17×17 · `⬇`17×17 · `🗑`22×15). **병합이 만든 것이 아니라 선행 상태**다. 고치면 방금
  랜딩한 `attach-manage` 의 버튼 외형까지 바꾸는 일이고 요청 범위 밖이므로 수치만 남긴다.
  (첫 측정에서 내가 쓴 16px 기준은 임의값이었다 — 실제 기준은 24px 이고 그 기준으로 재기록했다.)
- **미검증**: ux·design 의 accent 두께·색 대비 **판단**. 배포 후 PB-0008 캡처 판독이 backstop.
- **검증**: 헤드리스 44/44 · mjs 84 PASS · 전수 mjs 44 suite OK · pytest 26 PASS(접합부 2축 신설) ·
  뮤테이션 5/6 · verify-completion PASS.
- Timestamp: 2026-08-07T04:30:00+09:00
## REV-20260806T183000-ai-claude-attach-multi-upload [SKIPPED:tool-restricted:panel] — 폴더 단위 첨부 · 중복 스킵 UX · 편집본 체인 통합

- Related TASK: feature-0003-agent-web-ui (20260806T1820-attach-multi-upload)
- Trigger: UI/화면·업로드 경로 + 파일명 규칙 변경 → 원래 dispatch 대상은 ux·design + backend·qa
- Timestamp: 2026-08-06T18:30:00+09:00
- Verdict: PASS (인라인 보안 검토 · 기계적 계약 점검 · 뮤테이션 역검증 기준)
- Human Approval Needed: no

**검증 채널 (정직 표기, AGENTS.md §18.8.2 4번)**
- `codex review --uncommitted` — **실행 불가**: 계정 사용량 한도 초과(리셋 2026-08-09). 시도 로그 보유.
- subagent panel — 본 세션의 상위 우선순위 지시(AgentTool 사용 금지)로 제약. §18.8.2 "상위 우선순위
  지시 carve-out" 에 따라 제약 없는 채널로 대체하고 미검증 범위를 여기에 명시한다.
- **수행한 것**: built-in security-review 지침에 따른 **인라인 보안 검토**(서브태스크 미사용) +
  기계적 계약 점검(정적 5축) + **뮤테이션 역검증 3종** + 전 스위트 회귀.
- **미검증 범위**: ux·design 도메인의 독립 관점 리뷰(토스트 문구·요약 정보 밀도), backend 도메인의
  독립 리뷰. PB-0008 라이브 시각검증으로 부분 보완하되, 그것이 패널을 대체하지 않는다.

**인라인 보안 검토 결과 — HIGH/MEDIUM 0건**
- **Path traversal(승계 파일명 → ObjectKey)**: 차단. `storage_minio.make_object_key` 가
  `safe_filename()` 을 거치고 `[A-Za-z0-9._-]` 외 전 문자를 `_` 로 치환한다(`../` 도달 불가).
- **실행파일 확장자 승격(SEC-1)**: **강화**. 편집본이 LLM `filename` 을 전혀 쓰지 않고 source
  `OriginalFilename` 을 승계하므로 프롬프트로 확장자를 주입할 경로가 정의상 소멸. 확장자 없는
  source 의 kind 기반 안전 확장자(txt/csv) 강제는 유지(N4 로 잠금).
- **Content-Disposition 인젝션**: 무변경. `_next_version_filename` 은 stem/ext 재조립만 하고
  CR/LF 를 만들지 않으며, 기존 제어문자 제거 + RFC5987 `quote(safe='')` 방어가 그대로 적용된다.
- **인가 경계**: 무변경. 배치는 파일당 기존 엔드포인트를 호출해 서버
  `conversation.attachment.upload.{own,any}` 게이트를 그대로 통과한다. `silent` 는 토스트 표시만
  억제하고 집행에 관여하지 않으며, 억제된 차단은 요약에 "N개 차단" 으로 표면화된다.
- **하위호환**: 기존 `_v2` 저장명 row 는 불변. 두 접미 함수 모두 idempotent 라 `x_v2_v3` 이중접미가
  생기지 않는다.

**설계 판단**
- **dedup 판정을 완화하지 않았다**: 사용자 전제("내용이 다른데 차단")를 sha256 실측으로 검증한
  결과 지목된 22개가 전부 동일했다(G7-a). 판정을 느슨하게 했다면 진짜 중복이 매번 새 버전으로
  쌓여 버전 이력이 무의미해진다 — 고친 것은 판정이 아니라 **판정 주변의 경로·알림**이다.
- **drop 은 제거가 아니라 위임**: `.composer-wrap` 핸들러를 지우면 `#chatPane` 이 없는 구조에서
  composer 드롭이 죽는다. 조상 관계를 런타임에 확인해 위임하고, 아니면 자체 처리한다(폴백 보존).
- **버전 접미를 표시 계층으로 이동**: 저장명에서 빼야 체인이 하나로 유지되고, 로컬 덮어쓰기는
  다운로드 시점 이름으로 막는다. DB 저장값 불변이라 dedup·체인 스코프에 회귀가 없다.
- **기존 `_v2` 분열 체인 9쌍은 소급 병합하지 않았다** — 파괴적 데이터 변경(§12.3)이라 별도 승인
  대상이다. REPORT §8 에 잔여로 등재한다.

**남은 리스크**
- 배치 업로드 중 lazy-create(새 대화) 경로는 첫 파일이 대화 생성을 겸하므로, 그 사이 도착한
  파일은 `staged` 로 큐잉된다(기존 동작). 요약에서 "N개 첨부 대기" 로 구분 표기한다.
- 단일 토스트 엘리먼트 구조 자체는 그대로다 — 배치가 요약 1회로 줄여 회피할 뿐, 다른 경로에서
  연속 토스트가 겹치는 문제는 별도 축이다.
- Artifact: 본 entry
## REV-20260806T200000-ai-claude-attach-multi-upload-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY 라이브 실측 기록

- Related TASK: feature-0003-agent-web-ui (20260806T1820-attach-multi-upload)
- Trigger: doc-only + 시나리오 JSON 추가 — 실행 코드·정적 자산 변경 0줄
- Timestamp: 2026-08-06T20:00:00+09:00
- Verdict: PASS
- Human Approval Needed: no

배포본 `d3a520fd` 에서 PB-0008 실 Windows Chrome 실측 T1~T6 전건 PASS. 상세는
`docs/test-runs.d/REV-20260806T183000-attach-multi-upload.md` Run 4.

**가장 load-bearing 한 관측 (T4)**: composer 영역에 3개 드롭 시 첫 파일이 서버에 **정확히 1 row**.
수정 전이라면 `.composer-wrap` 과 `#chatPane` 두 핸들러가 같은 drop 을 처리해 2회 업로드 시도가
발생하고 두 번째가 dedup 에 걸려 사용자에게 "이미 첨부된 파일입니다" 오탐이 떴다 — 사용자가 보고한
현상의 기전 중 하나가 라이브에서 닫힌 것을 확인했다.

**정직 표기**: 토스트가 담긴 프레임 캡처는 2.2초 TTL 로 확보하지 못했고, `is-visible` + computed
배경색 실측으로 대체했다(에러 색이 아님을 확인). 본 변경이 토스트의 **문구·색 토큰만** 바꾸고
레이아웃 기하를 건드리지 않는다는 근거를 fragment 에 명시했다. assistant 편집본 승계(AC-AMU-4·5)는
실 LLM 왕복이 필요해 라이브 실측에서 제외 — pytest N3/N5/N6 로 잠갔다.

**라이브 데이터 경계**: 자체 테스트 대화 3건만 생성·사용 후 전부 보관 처리. 사용자 대화 무접촉
(읽기 전용 조회만).
- Artifact: 본 entry
## REV-20260807T062000-attach-diff-unified-bg [SKIPPED:tool-restricted:ux,design] — 단일열 줄 배경 소실 회귀 자기 적발·수정

- [SKIPPED:tool-restricted:ux,design] — Agent tool 세션 금지 + codex 사용량 한도(8/9 까지).
  본 결함이 **시각 판단 축**이었으므로 이 skip 이 실제로 비용을 냈다 — 자동 44축이 전부 PASS 인
  상태로 배포됐고, 배포 후 사람(내)의 확대 캡처 판독이 유일한 검출 지점이었다. 그 판독을
  B9/B9b/A1d 로 자동화해 다음부터는 사람 눈에 의존하지 않게 했다.
- **자기 적발 — 내가 넣고 배포한 회귀**: 직전 cycle 이 "강조는 내용 있는 쪽에만" 규칙을 넣으며
  줄 배경을 `.has-content` 로 좁혔다. 그 클래스를 `_renderSplit` 에만 부여해 단일열의 내용
  있는 변경 줄이 danger/ok 를 잃고 `rgb(240,239,234)` 를 받았다. **색 소실보다 나쁜 의미 반전** —
  내용이 있는데 "대응 내용 없음" 색이 된다. 라이브 실측으로 확정(추측 아님).
- **기전 진단**: 렌더러가 둘(`_renderSplit`/`_renderUnified`)인데 규칙 준수를 **한쪽에서만**
  확인했다. 헤드리스 B8/B8b 는 배경을 2열에서만, B7 은 단일열의 블록 구조만 봤다. "두 뷰가
  같은 규칙을 따르는가" 라는 축 자체가 없었다.
- **재발 차단 2층**: ① 동작층 — 헤드리스 B9/B9b 가 단일열 computed style 을 실측. ② 구조층 —
  mjs A1d 가 `has-content`/`has-block` 부여 지점 **개수**를 세어 한쪽 누락을 정적으로 적발.
  구조층을 둔 이유: 새 렌더러가 추가되면 동작 테스트는 그것을 모르지만 개수는 어긋난다.
- **뮤테이션 역검증 4/4**: 수정 되돌림 → 헤드리스 B9·B9b red(실측 `rgb(240,239,234)`) +
  mjs A1d 2건 red. 이번 cycle 은 **미포착 뮤테이션이 없다**(직전 cycle 의 rAF 항목과 다르다).
- **결함 아님으로 확인**: 패딩된 빈 셀은 여전히 중립 filler(경계 반대편 유지) · 2열 배경 무변경
  (B8/B8b 회귀 없음) · 블록 accent 는 이번 수정과 무관하게 두 뷰 모두 정상(B6/B7).
- **미검증**: 수정된 단일열의 색 대비·가독성 **판단**. 배포 후 PB-0008 확대 캡처 판독이 backstop.
- **검증**: 헤드리스 46/46 · mjs 88 PASS · 전수 mjs suite OK · verify-completion PASS.
- Timestamp: 2026-08-07T06:20:00+09:00
## REV-20260807T010301-doc-sync-rn-0807 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-06(9항목) 블록 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 34/0 동일 = 회귀 0) · 구조검증(`generated`=2026-08-06 == `releases[0].date` · head 9항목 · releases 43→44 · 08-05(3)/08-04(3)/08-03(7) 보존 · type/area enum 위반 0 · 스키마 외 키 0) · 내부용어 누출 스캔 0(19 패턴).
- 적대검증(ULTRACODE `wf_d4d5af5d`, 2 렌즈 — A 사실정확성 / B 사용자언어·구조): 양 렌즈 `REVISE`, 결함 10건. **오케스트레이터가 정본·실코드로 전건 독립 재검증**해 9건 실재 확인·반영, 1건 반증.
  - **[MAJOR 반영]** "글자로 된 파일만 줄 단위로 비교, **스프레드시트**는 비교 불가" = 사실 오류. `routers/_conv_store.py:6714 _VERSION_DIFF_TEXT_KINDS = ("text", "csv")` · `routers/attachments.py:311-314` 상 **CSV 는 줄 diff 대상**이고 목록 아이콘이 xlsx 와 같은 📊 라 CSV 사용자가 "내 파일엔 안 된다"로 정반대 오독 → "글자로 된 파일(텍스트·CSV)은 … 엑셀·PDF·이미지처럼 …" 으로 교정.
  - **[MINOR 반영 ×8]** ① 삭제 선택지 라벨이 실제와 불일치 — 실 라벨은 `최신 버전(v3)만 삭제`/`전체 버전 삭제 (3개)`(`composer.js:1121-1122`)이고 `최신 버전만` 은 **다른 화면**(전체 다운로드)의 라벨(`:1259`)이라 혼선 → 버전·개수 포함형으로 교정 ② `전체 다운로드`·`휴지통` 은 **아이콘 전용 버튼**(`index.html:383-384` title/aria-label 만, 가시 텍스트 0) → ⤓·🗑 표기 병기 ③ 배치 업로드는 개별 토스트를 억제하고 집계 요약만 띄운다(`composer.js:762 silent:batch`·`:769`·`:779`) → `이미 최신입니다(내용 동일)` 는 단건 한정으로 한정하고 배치는 요약 예시 병기 ④ 공유 발신자 이름은 좁은 폭(≤720px)에서 **자르지 않고 줄바꿈**이 의도된 설계(`share.css:168-174` 주석 — 공통 접두사 계정명이 ellipsis 로 동일 문자열이 되면 기능 목적이 깨짐) → "넓은 화면에서는 줄이고, 좁은 화면에서는 줄을 바꿔 전체를 보여 줍니다" ⑤ "전달된 파일은 첨부 칩에서 바로 내려받을 수 있습니다" = 정본이 **미검증으로 명시**한 표면(`unit/feature-0002-agent-core/docs/MODIFY.md:1490` "미검증(정직) … 다운로드 칩 실 렌더" · FRICTION_LEDGER:66) → "붙어 나오도록 연결했습니다" 로 단정 완화 ⑥ 배경 dismiss 원인 서술이 브라우저 공통조상 판정 알고리즘을 노출 → 파일 상단 작성 원칙(내부 동작 비노출)대로 관찰 층으로 재작성 ⑦ '결과 보기' 항목 말미 2문장이 모델 입력 경로(내부 계약)를 서술하고 '알려 주도록' 의 수신 주체가 모호 → 사용자 체감 결과 1문장으로 압축 ⑧ AI 편집본 버전 체인 통합 fix 가 '다중 첨부' 항목 detail 말미에 묻혀 제목만 훑는 사용자가 놓침 + 기존 블록은 버전 체인을 독립 title 로 공지해 온 선례 → 별도 `fixed/work` 항목으로 분리(items 8→9, summary 커버리지도 대칭 보강).
  - **[반증 1건]** 렌즈 B 가 `65d2e5da`(도메인 합성 죽은 클러스터 배제 — 사용자 답변에 부풀려진 개수가 실림) 누락을 결함으로 지목했으나, 정본 `unit/feature-0002-agent-core/docs/TASK.md:24` 의 `- [ ] … 배포 → **라이브 재합성 확인**` 이 미체크다. 이 수정은 L3 합성의 **입력**을 고치므로 배포(`d04ab2f2` ancestor)만으로는 이미 저장된 domain 요약 5건이 갱신되지 않는다 — "머지·배포됐으나 재생성으로만 라이브 반영되는 개선" 은 사용자 릴리즈노트에 완료형으로 쓰지 않는다는 규약대로 제외 유지(제외 사유를 TASK 에 명시). 렌즈 A 는 같은 항목을 "admin UI 렌더 표면 0" 사유로 제외 타당 판정 — 결론 일치, 사유는 오케스트레이터 판정이 더 정확.
- 포함/제외 판정 근거: 사용자향 9항목. 델타 비-머지 23커밋 = 코드 15 + doc-only 8. 코드 15 중 13건이 9항목에 매핑, 2건(`65d2e5da`·`9751211c`)은 위 사유로 제외. 배포 게이트는 오케스트레이터가 **물리 실측**으로 확인 — 델타로 바뀐 static 14종 전부 라이브 서빙본이 `origin/main` 과 byte-identical(빌드 주입 `?v=<hash>` 정규화 후), `/healthz` 200, web-a/web-b/ask-worker/insight-worker 전부 healthy → POST-DEPLOY 커밋이 없는 항목(diff 체인 `40ef1701` 계열·회귀수정 `76a40574`)도 라이브 확인됨.
- **round-2 적대검증(`wf_49645662`, 적용된 diff 2 렌즈)**: RN 렌즈 `REVISE`. R1 교정 9건 착지·신규 문법/스키마 오류 0·`type` 정합(전 43블록 grep 으로 `new` 3건 선례 0 확인)·라벨/방향/권한/상한 재대조는 전건 통과했고, **잔여 정직성 결함 3건**을 추가 적발해 전건 반영: ① item 5 가 완료형 "이어집니다" 만 써서 **이미 갈라진 체인 9쌍은 소급 병합되지 않는다**(정본 `REPORT.md` §8 첫 항목 — `OriginalFilename`/`RootAttachmentId` 재작성이 필요한 파괴적 데이터 변경 §12.3 이라 별도 승인 대상)는 사실이 누락 → caveat 1문장 추가 ② item 6 "따로 전달하므로 … 잘리지 않고" 가 모델의 도구 경로 채택을 무조건 보장으로 단정(정본 `unit/feature-0002-agent-core/docs/MODIFY.md:1490` "미검증(정직) — 모델이 실제로 도구를 채택하는지" + 본문-블록 폴백 생존 `modules/ask.py:327`) → "이 방식으로 전달되면" 조건절로 흡수해 `65d2e5da` 제외 기준과의 비대칭 해소 ③ **item 4 의 배치 요약 예시 수치 `20개/2개` 가 조작된 값**(R1 결함 A2 를 적용하며 오케스트레이터가 만든 것) → 정본 `REPORT.md:15` 실측 예시 `첨부 22개 중 6개 업로드 · 16개 변경 없음(건너뜀)` 으로 교체(포맷 자체는 `app/composer.js:779` 와 일치했으므로 오류는 숫자였다). **교훈: 적대 verifier 의 교정을 적용할 때 오케스트레이터가 채워 넣는 예시 수치도 정본 대조 대상이다.**
- **테스트 env 정직 표기**: 위 `verify_release_notes.mjs` **34 pass / 0 fail** 은 본 cycle 에서 편집 전(baseline)·편집 후 **두 번 실제 실행해 측정한 값**이다. 다만 cycle 후반 재확인 시점에 `/tmp/node_modules/jsdom` 이 사라져(무인 env 의 tmp 정리) 동일 명령이 `MODULE_NOT_FOUND` 로 미가동됐다 — `git stash` 로 **pristine HEAD 에서도 동일 실패가 재현**되므로 본 변경과 무관한 환경 사유다. 콘텐츠 검증은 `node --check` + vm 샌드박스 구조검증(releases 44 · head 9항목 · enum 위반 0 · 내부용어 누출 0)으로 갈음했다.
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + `deploy-web.sh asset_stamp_verify` 가 배포 시 content-hash 주입, 수동 bump 는 무효 churn + 게이트 무력화).
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.
- Timestamp: 2026-08-07T01:03:01+09:00
## REV-20260806T182500-attach-suffix-toggle — 판단 근거 (Minor §12.3)

**요청 해석 (§9.1 자율 판단 + 기록)**

- "접미사가 포함되는 상태로 받을지 토글" 의 **기본값**을 포함(체크됨)으로 뒀다. 근거: 종전
  동작 보존(비파괴 원칙) + 선택이 브라우저에 기억되므로 접미를 싫어하는 사용자는 **1회만**
  끄면 된다. 기본을 제외로 두면 기존 사용자의 파일명이 예고 없이 바뀐다.
- **체크박스를 몇 개 둘 것인가**: 단일용·전체용을 따로 두지 않고 **하나의 상태를 두 표면이
  공유**하게 했다. 별도로 두면 같은 파일을 목록 ⬇ 로 받을 때와 ⤓ 로 받을 때 이름이 달라져,
  사용자가 "왜 어떤 건 붙고 어떤 건 안 붙지" 를 겪는다 — 요청의 "단일/전체 모두 대응" 은
  두 벌의 스위치가 아니라 **한 선택이 두 경로에 다 먹는 것**으로 읽는 게 맞다.
- **`strip` 을 `_v\d+$` 전체 제거로 하지 않은 이유**: 사용자가 원래 `plan_v2.docx` 라는
  이름으로 올린 v1 첨부까지 `plan.docx` 로 바뀐다. 서버는 `VersionNumber` 를 알고 있으므로
  **번호가 일치할 때만** 제거하면 시스템이 붙인 것과 사용자가 지은 것을 구분할 수 있다.
  (이 구분은 `_next_version_filename` 의 정확한 역함수이기도 하다.)

**설계 결정 (D1) — 이름 결정 권위를 서버로**

프론트는 fetch+blob 저장이라 `<a download>` 이름을 스스로 정해야 하고, 그 순간
`Content-Disposition` 은 무시된다. 규칙을 프론트에도 두면 (a) 두 벌이 어긋나고 (b) 버전
번호를 모르는 호출부(말풍선 칩의 user snapshot 은 `version_number` 가 없다)는 규칙을 적용할
수 없다. 그래서 서버가 최종 이름을 계산해 `X-Attachment-Download-Name` 로 실어 보내고
프론트는 그대로 쓴다. 선행 cycle 이 남긴 `_versionedFilename` 은 제거했다 — 그 함수의 주석이
스스로 "두 경로의 결과물이 같은 규칙을 따르게 한다" 고 적고 있었는데, 규칙을 복제하는
방식으로는 그 목표가 유지되지 않는다는 것이 이번 이중접미로 드러났다.

**하위호환 (§16.7 G4 경계)**

일괄 다운로드의 `version_suffix` 미지정 기본을 상수로 두지 않고 **scope 별로** 갈랐다
(all→force, latest→keep). 상수 `keep` 으로 뒀다면 이 파라미터를 모르는 기존 호출자가
`scope=all` 에서 갑자기 버전 없는 이름을 받아 **이름 충돌 fallback(id 접미)** 로 떨어졌을
것이다. 종전 동작 재현을 테스트로 단정했다(E4).

**§16.7 자기-열거 완결성**

- G1/G2 — 요청 항목 2개(체크박스 구성 / 단일·전체 모두)로 분해해 TASK §9 에 배선 확인 기록.
- G3 — "전 버전 다운로드에서만 `_v` 가 붙는다" 는 기존 문서 서술을 그대로 믿지 않고 저장
  경로(`_next_version_filename`)를 읽어 **저장명 자체가 접미를 갖는다**는 사실을 확인한 뒤
  범위를 정했다. 이 실측이 없었으면 최신본 1개 다운로드는 여전히 `_v2` 로 나갔을 것이다.
- G9-b — 접미 제거 시 이름 충돌은 **무음 덮어쓰기 없이** id 구분 접미로 처리되고, 그 사실을
  모달이 미리 알린다(사후 침묵 대신 사전 고지).
- G10 — "같은 규칙이 두 벌" 재발 클래스를 소스 단정으로 잠갔다(G1 테스트: 프론트에
  `_versionedFilename` 류가 되살아나면 red).

**잔여 리스크 (정직 표기)**

- 브라우저 `localStorage` 는 기기·프로필 단위라 다른 기기에서는 기본값(포함)으로 시작한다.
  서버 계정 설정으로 올릴 수 있으나 이번 범위 밖 — 설정 테이블·API 가 필요해 Minor 를 벗어난다.
- 접미 제거 상태에서 `scope=all` ZIP 은 이름이 겹쳐 id 접미가 붙는다. 이는 **의도된 안전
  동작**이지만 "깨끗한 이름" 기대와는 다르다 — 모달 힌트로 고지하는 선에서 멈췄다.
- 실 다운로드 파일명 확인(브라우저 저장 대화상자)은 PB-0008 시각검증 항목으로 이월.

## REV-20260806T193000-attach-suffix-toggle [SUBAGENT:security] — PASS (P3 2건 흡수)

codex 채널 할당량 소진(8/9 리셋 — `ERROR: You've hit your usage limit`)으로 §18.8.2 대체 경로.
세션 지시("요청 없이 Agent 툴 호출 금지")와 상충하므로 **자체 SKIP 하지 않고 사용자에게 1회
확인** 후 subagent 패널로 진행(사용자 승인 2026-08-06).

- **헤더 인젝션 없음** — `_quote(filename, safe="")` 출력 알파벳이 `[A-Za-z0-9_.~-]`+`%XX` 뿐이라
  CR/LF·따옴표·제어문자가 전부 percent-encode 된다(적대 입력 실행 검증). 기존 `ascii_fallback`
  보다 오히려 강하다. **zip-slip 없음** — 정제가 이름함수보다 앞이고, 이름함수가 만들 수 있는
  문자는 `_v{int}` 뿐. **인가 oracle 없음** — 400 응답이 attachment_id 와 무관. **매니페스트 url**
  에 사용자 문자열이 도달할 경로 없음(allowlist 정규화). **노출면 확대 없음** — 새 헤더는 인가
  통과 200 응답에만 실리고 같은 응답의 `Content-Disposition` 이 이미 같은 이름을 담는다.
- **[P3 흡수] 단일 경로 정제 비대칭** — ZIP 에 있는 경로 성분·제어문자 제거가 단일 다운로드
  헤더 산출에는 없었다. 브라우저는 `download` 값을 UA 가 정규화하므로 실피해는 없으나 스크립트
  소비자에겐 그 보호가 없다 → 같은 정제를 단일 경로에도 적용(`test_e6`).
- **[P3 흡수] 400 이 인증보다 앞** — 미인증 요청이 401 대신 400 을 받았다 → `_require_account`
  뒤로 이동(`test_e5`). bulk 경로와 순서 계약도 일치하게 됐다.

## REV-20260806T193000-attach-suffix-toggle [SUBAGENT:backend-qa] — BLOCK → 해소

- **[P2] 핵심 경로에 행위 테스트 0건 (가장 무거운 지적)** — `_zip_entry_name(..., mode="keep")`
  으로 **ZIP 이 토글을 완전히 무시하게** 만들어도 69건 전건 통과했다(패널의 뮤테이션 실증).
  기존 Z1/Z2 는 규칙 함수를 리터럴 mode 로 직접 호출할 뿐 **엔드포인트 배선을 타지 않았고**,
  E4/G2/G4/G5 는 `inspect.getsource`·JS 텍스트 단정이라 소스 문자열의 존재만 봤다.
  → 라우트 함수를 그대로 호출해 **산출물(ZIP namelist·manifest JSON)을 보는** B1~B6 신설.
  같은 뮤턴트를 다시 넣어 **B1·B2·B5 red**, manifest url 하드코딩 뮤턴트에 **B4 red** 확인.
- **[P2] 소스 문자열 단정의 거짓 적색** — `default=("force" if scope_norm == "all" else "keep")`
  에서 공백만 지워도 red, JS 삼항식은 포매터 한 번에 깨진다. `inspect.getsource` 는 실행 중
  편집 시 엉뚱한 본문을 반환하는 알려진 flake 원인이기도 하다 → 배선 사실만 보도록 완화하고
  실제 이름 일치는 B4·B5 가 엔드포인트로 검증.
- **[P2 → 계약 정정] "포함" 인데 안 붙는 경우** — 사용자가 같은 이름으로 재업로드한 버전은
  저장명에 접미가 없어(`_next_version_filename` 은 AI 편집본에만 쓰인다) 토글 ON 이어도 단일
  다운로드에 표시가 나타나지 않는다. 코드를 `force` 로 바꾸면 v1 이 `report_v1.csv` 가 되어
  종전 동작이 깨지므로, **라벨을 실제 동작에 맞췄다**("포함" → "**유지**") + FUNCTION 에 명시.
  "어느 버튼으로 받아도 이름이 같다" 도 "같은 범위에서는" 으로 정정(전 버전 일괄만 force).
- **[P3 흡수] `rsplit(".", 1)` 경계 파괴** — `.env`(v1) force → `_v1.env`(stem 소멸),
  `a.` strip → `a`(점 소실, 접미를 떼지도 않았는데 이름이 바뀐다) → `os.path.splitext` 로 교체
  (`test_f7`). 단일·ZIP 두 경로가 같은 이름을 내는지도 단정(`test_e7`).
- **[P3 흡수] ZIP/매니페스트 `used` 소비 비대칭** — ZIP 은 fetch 실패·키 공백 행을 건너뛰며
  이름을 소비하지 않아 뒤 행의 충돌 재배정이 밀렸다 → 이름을 루프 선두에서 확정(`test_b5`).
- **[P3 흡수] 문서 서술 과장** — "기존 호출자의 결과가 불변" 은 사실이 아니다(이중접미 해소 +
  그로 인한 충돌 재배정). TASK/REPORT 를 "두 예외는 의도된 변경" 으로 정정.
- **[P3 흡수] `_normalize_version_suffix_mode` 가 `default` 를 검증 안 함** → allowlist 밖이면
  `ValueError`. 미래 caller 가 오타를 무음으로 keep 처리하지 않게.

## REV-20260806T193000-attach-suffix-toggle [SUBAGENT:ux] — BLOCK → 해소

- **[P1] 한 화면이 스스로를 부정** — `모든 버전` 라디오의 정적 힌트 "파일명에 v1·v2 가 붙습니다"
  가 토글 OFF 에서도 남아, 20px 아래의 해제된 체크박스와 정면으로 모순됐다. 실제로는 `strip`
  이라 v1·v2 가 아니라 id 구분번호가 붙는다 — **사용자 대면 거짓 진술** → 두 안내를 한
  `syncSuffixHint` 가 함께 관리(`파일명에 v1·v2 가 붙습니다` ↔ `버전 표시 없이 받습니다`).
- **[P2 흡수] localStorage 쓰기 실패 시 표시-집행 괴리** — 사파리 프라이빗·쿠키 차단에서
  `setItem` 예외를 삼킨 뒤 화면만 꺼지고 다운로드는 계속 포함으로 나갔다(세션 내내 복구 불가)
  → 세션 메모리 폴백 `_attachSuffixMemory`.
- **[P2 흡수] 탭 간 동기화 부재** — 다른 탭에서 바꾸면 이 탭 체크박스는 옛 값을 보여주는데
  다운로드는 매 클릭 저장소를 다시 읽어 **바뀐 값**을 따랐다 → `storage` 이벤트 리스너.
- **[P2 흡수] 충돌 경고가 스크린리더에 무음** — `aria-live` 없는 `<em>` 이라 "미리 말한다" 는
  목적이 SR 경로에서 미달 → `aria-live="polite"`.
- **[P3 흡수] 경고 게이트가 실제 충돌 규칙보다 좁음** — `scope=latest` 에서도 접미를 떼면 이름이
  겹칠 수 있는데 경고가 `scope=all` 에만 떴다 → scope 조건 제거. 문구도 "구분 번호"(순번 오해)
  → "파일마다 다른 번호"(실제로는 첨부 id)로 정확화.
- **[P3 흡수] 모달 정렬·높이** — 체크박스가 라디오보다 9px 내어쓰기(실측) → padding 11px 로
  축 정렬. 힌트 등장/소멸이 모달 높이를 약 20px 바꿔 방금 누른 라디오와 버튼이 움직였다 →
  `min-height` 로 자리 예약.
- **[P3 흡수] 패널·모달 라벨 불일치** — "다운로드 파일명에…" vs "파일명에…" → 상수 하나로 통일.
- **결함 없음 판정 2건(근거 보존)**: ① 240px 폭 붕괴 없음 — 라벨 실측 폭 192px, 인라인 가용폭
  약 193px 이라 1~2줄로 접힐 뿐이고 `nowrap`·`ellipsis` 선언이 없다. 과거 회귀는 목록 **행 내부**
  인라인 경쟁이 기전이라 독립 블록인 이 컨트롤에는 해당하지 않는다. ② §16.8 위반 없음 —
  컨트롤 라벨이고 힌트는 1문장 22자로 hint 예산 안.
- **미흡수(범위 밖 · 선재)**: 모달 focus trap 부재와 닫힌 패널의 탭 순서 잔류는 `_attachModalShell`
  과 `.attach-side-panel.hidden` 의 선재 성질이다. 첨부 0건에서 ⤓ 가 disable 되지 않는 것도
  선행 cycle 범위. REPORT §잔여에 원장 등재.

## REV-20260807T004500-attach-suffix-toggle [SUBAGENT:rebase-integration] — main 계약 흡수

머지 대기 중 main 에 `attach-multi-upload` 가 들어와 단일 다운로드가 **v2 이상이면 항상**
`_next_version_filename` 으로 접미를 붙이게 됐다(저장명이 원본명을 승계하는 체인에서 구버전이
로컬 최신본을 덮어쓰는 문제 해결).

- 이는 backend/qa 패널의 P2("토글 ON 인데 사용자 재업로드 체인에는 접미가 안 붙는다")를 main 이
  **먼저 해결한 것**이다. 내 `keep` 을 그대로 두면 미지정 호출자가 main 과 다른 이름을 받는다.
- 그래서 그 규칙을 규칙 함수의 **`auto` 모드로 흡수**하고 경로 기본을 옮겼다: 단일 = `auto`,
  `scope=latest` = `auto`, `scope=all` = `force`(한 압축에 v1 까지 들어가므로 v1 도 구분 필요).
- **부수 이득**: 종전에 어긋나던 "목록 ⬇(v>1 이면 접미)" 와 "⤓ 최신 버전만(접미 없음)" 이 이제
  같은 이름을 낸다. 토글 OFF(`strip`)는 두 경로 모두에서 접미를 뗀다 — 요청의 핵심은 불변.
- 프론트의 `_versionedFilename` 은 main 이 버전 이력 행에도 쓰도록 확장한 상태였으나 제거하고
  서버가 준 이름을 쓴다(규칙 두 벌이 이 cycle 의 출발점이었던 결함).
- 회귀 방어: A1~A4 신설 — `auto` 규칙 · 단일 미지정 기본이 main 재현 · **⬇ 와 ⤓ latest 이름 일치**
  · `auto` 기본 하에서도 토글 OFF 가 접미를 뗀다.
- **선행 테스트 갱신 판단**: main 의 `test_n6` 이 red 가 됐는데, 원인은 계약 위반이 아니라
  그 테스트가 **구현 함수 이름을 문자열로 단정**했기 때문이다(backend/qa 패널이 이 cycle 에서
  지적한 바로 그 패턴). 계약이 유지됨을 A1~A2 가 행위로 증명하므로, 삭제가 아니라 **결과를
  보는 단정으로 재작성**했다 — 계약을 지키는 다음 리팩터링에 다시 red 가 나지 않도록.
## REV-20260807T012000-attach-suffix-postdeploy [SKIPPED:non-policy-doc] — 배포 완료 기록

코드 변경 0 의 doc-only cycle(배포 결과·POST-DEPLOY 실측 기록). 정책 문서 변경 없음.
검증 내용 자체는 `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md` §7 에 실측치로 기록.
## REV-20260806T1853-ai-claude-feature-0003-attach-diff-syntax — 첨부 diff 구문 하이라이트

**판단 근거**

- **왜 vendor 를 안 쓰는가**: highlight.js/prism 은 이 화면 하나를 위해 수십~수백 KB 를 더한다.
  이미 저장소에 경량 SQL 토크나이저 관례가 있고(답변 말풍선), diff 는 **행 단위 짧은 문자열**이라
  범용 하이라이터의 상태 기계가 오히려 맞지 않는다(아래 라인 독립 항).
- **왜 정본을 새 모듈로 옮겼는가**: SQL 예약어 목록이 `app.js`·`share.js` 두 벌로 존재했고, 여기에
  세 번째(첨부 diff)를 더하면 "예약어 하나 추가" 가 세 곳 편집이 된다. `modal-dismiss.js` 가 남긴
  교훈(복제가 곧 결함 기전)을 따라 `code-highlight.js` 를 정본으로 삼고 `app.js` 가 import 한다.
  **`share.js` 는 이번 범위 밖** — classic `<script>` 로 로드되는 번들이라 ESM import 를 쓸 수 없다
  (구조적 제약이지 판단 누락이 아니다). REPORT §8 에 잔여 등재.
- **왜 라인 독립 토큰화인가(절충 명시)**: 맥락 축약 뷰는 중간을 `gap` 으로 생략한다. 행 사이로 상태
  (블록 주석 열림 등)를 이어붙이면 생략 지점 이후 색이 통째로 어긋나는데, 그 오염은 조용하다.
  각 행을 독립 판정하면 멀티라인 주석의 2행 이후가 무색으로 남을 뿐이다 — **무색이 오색보다 낫다.**
- **왜 `code-tok-*` 를 새로 만들고 `sql-tok-*` 를 안 건드렸는가**: 두 표면의 **배경이 다르다**.
  말풍선 코드블록은 항상 어두운 배경(tokyo-night 팔레트가 그래서 밝은 색), 첨부 diff 표는 문서
  배경(라이트)이다. 같은 값을 공유하면 한쪽이 반드시 저대비가 된다. prefix 통합은 CSS 2파일 +
  두 번들의 회귀 표면을 여는 별 축이라 원장으로 넘긴다.
- **왜 다크 override 를 안 넣었는가**: `base.css` 에 전역 다크 팔레트가 없다(다크는 국소 컴포넌트
  patch 만). 첨부 diff 표는 `--surface`/`--text` 를 쓰므로 항상 라이트다. 지금 다크 규칙을 넣으면
  **검증할 수 없는 코드**가 된다. 대신 색을 변수로 모아 전역 다크 도입 시 한 곳에서 끝나게 했다.
- **토글을 둔 이유와 안 둔 것**: 확장자 판정은 틀릴 수 있다(`.config`·`.json5` 변종). 끄기 수단은
  탈출구다. 반대로 **언어를 사용자가 고르는 선택기는 두지 않았다** — 대화당 파일 하나의 유형을
  수동 지정하는 UI 는 얻는 것 대비 어포던스가 무겁고, 오판 사례가 관측되면 그때 레지스트리에
  확장자를 추가하는 것이 정답이다(판정 규칙 개선 > 사용자에게 떠넘기기).

**검증**

- 신규 77 PASS · 기존 diff 하네스 85 PASS · **mjs 전수 46 suite 전건 OK**(회귀 0).
- 뮤테이션 5/5 KILLED — 특히 M5(innerHTML 조립)에서 실제 `<script>` 가 DOM 에 파싱되어 D2/D3 이
  red 가 됐다. XSS 단언이 형식적이지 않음을 실증한 것.
- **fuzz 가 실결함을 잡았다** — 표본 13건은 통과하는데 무작위 1,200건에서 152건이 원문 손실
  (CSV 짝 없는 따옴표). 무손실은 하이라이트에서 **유일하게 조용히 치명적인 축**이라(사용자가 존재
  하지 않는 diff 를 본다) 결정적 PRNG fuzz 를 상설 가드로 남겼다.

**남은 리스크**

- 색 대비·가독성은 jsdom 이 못 본다 — PB-0008 실측 전까지 AC-1 은 미확정으로 둔다.
- 6,000행 × 2열 토큰화 비용은 상한 방어(`MAX_LINE_LEN` 4,000자)만 두었고 실측은 PB-0008 이월.
- `.json5`·주석 있는 JSON(JSONC)은 표준 JSON 토크나이저로 처리되어 주석 줄이 무색이다(오색 아님).
- Artifact: 본 entry

## REV-20260806T213000-ai-claude-feature-0003-attach-diff-syntax [AGENT-TEAM:attach-diff-syntax] — BLOCK → 전건 흡수 후 SHIP

§18.8 적대적 검증 패널 3도메인(security · ux · design) 동시 실행. **VERDICT: BLOCK 2(ux·design) +
CONCERN 1(security)** → P1 4건 · P2 7건 · P3 4건 전건 흡수 후 재검증 통과.

**패널이 확인해 준 것(가정이 아니라 실측)**
- security: XSS 무첨가 주장이 **720 DOM 단언**(적대 payload 25 × 언어 6 × wrapping 5)에서 성립 —
  생성 element 는 span 뿐, 속성은 class 뿐, class 값은 13종 allowlist 안. 재직렬화 경로 0.
- security: 원문 무손실이 **2,309,424 표본**(문자 soup · 유니코드/서로게이트/BOM/NUL · 구조 조각 ·
  단문자 뮤테이션 · 22자 알파벳 3~4자 전수)에서 손실 0. 구조적 근거 = 모든 정규식이 terminal
  `([\s\S])` 로 끝나고 빈 매칭 대안이 없다.
- design: 다크 override 를 넣지 않은 판단이 옳다 — `base.css` 의 `prefers-color-scheme` 0건,
  모달 배경은 조건 없이 `--surface`. 다크 분기는 실행 경로가 없어 **검증 불가 코드**가 된다.
- security: `share.js` 의 SQL 예약어 세 번째 사본은 현재 **byte-identical**(152 kw/50 types, 드리프트
  0)이고 classic `<script>` IIFE 라 구조적으로 import 할 수 없다 — 범위 밖 판단이 회피가 아님을 확인.

**BLOCK 사유였던 것 (내가 놓친 것)**
1. **대비를 계산하지 않았다.** "jsdom 은 색을 못 본다 → PB-0008 이월" 은 **틀린 이월**이었다.
   대비비는 브라우저 없이 계산 가능하고, 계산해 보니 27조합 중 12조합이 AA 미달이었다(type 은 흰
   배경에서도 3.68). 이월은 *측정할 수 없는 것*에만 쓸 수 있다. → 하네스 G2 가 이제 매 실행 재계산.
2. **거짓 어포던스를 다른 축에서 재현했다.** 코드 주석에 "무색 파일에 끄기 버튼을 두면 거짓
   어포던스" 라고 써 두고, 파일명은 지원인데 **본문이 없는** 6종 상태를 같은 결함으로 통과시켰다.
   원칙을 문장으로 적는 것과 판정에 거는 것은 다르다.
3. **토글 축 테스트가 vacuous 했다.** 버튼 속성만 단언해 기능을 무력화하는 4종 뮤테이션이 전부
   생존했다. 뮤테이션 5종을 돌려 "KILLED" 를 확인했는데, 그 5종이 **하이라이트 축에만** 있었고
   토글 축에는 없었다 — 뮤테이션 커버리지도 축별로 봐야 한다는 교훈.
4. **성능 방어가 잘못된 층에 있었다.** `MAX_LINE_LEN` 은 줄 하나를 막지만 비용은 줄 **길이에 2차**로
   붙어 상한 근처에 집중된다. 상한을 두면서 "응답성은 계약" 이라 선언한 것이 방어했다는 착각을
   만들었다 — 근본은 정규식 모호성이었고, 4곳을 고쳐 선형으로 만들었다(최악 7.99ms → 0.609ms).

**흡수 후 상태**: 하네스 108 PASS(A~I 9섹션) · 기존 diff 하네스 85 PASS · mjs 전수 46 suite OK ·
**뮤테이션 9/9 KILLED**(패널이 생존 지적한 M6~M9 포함 — 팔레트 저대비·delim 칩·오색·2차 성능 회귀도
각각 잡힌다). 남은 P3 는 없고, 범위 밖으로 원장 등재한 것은 REPORT §8(share.js 사본 · prefix 이원화 ·
전역 다크 · 확장 대기 유형).

**정직 표기**: 실제 화면 가독성(폰트 렌더링·6,000행 스크롤 중 판독)은 여전히 PB-0008 실측이 정본이며
배포 후 POST-DEPLOY 로 수행한다. 기하 하네스(`verify_attach_diff_geometry.py`)는 이 환경에 playwright
브라우저 바이너리가 없어 미실행 — span 은 inline 이라 열 폭 기하에 영향이 없다는 것이 근거이나
**측정하지 않았다**.
- Artifact: 본 entry
## REV-20260806T200000-ai-claude-attach-chain-merge [SKIPPED:tool-restricted:panel] — 분열 체인 병합 + 첨부 날짜 compact

- Related TASK: feature-0003-agent-web-ui (20260806T2000-attach-chain-merge)
- Trigger: 파괴적 데이터 변경(첨부 메타 rewrite) + UI 표시 추가 → backend·qa·ux 도메인
- Timestamp: 2026-08-06T20:00:00+09:00
- Verdict: PASS (계획·가드 기준) · 라이브 적용 결과는 배포 후 실측으로 확정
- Human Approval Needed: no — 사용자 명시 지시("하나의 체인으로 합쳐주세요") + 조건부 범위 위임

**검증 채널(정직 표기)**: `codex review` 는 여전히 사용량 한도(리셋 2026-08-09), subagent panel 은
상위 우선순위 지시로 제약 → §18.8.2 carve-out. 인라인 검토 + 기계적 계약 점검 + 뮤테이션 역검증으로
대체하고 backend·qa·ux 독립 관점은 미검증으로 남긴다.

**왜 전체 범위인가 (사용자 조건부 지시 해석)**: "범위가 너무 넓다면 최근 1주일" 의 판단을 위해 먼저
전수 실측했다 — 780 활성 row 중 분열 155 row / 62 논리파일 / 14 대화. row 수가 적고 되돌릴 수단이
있으므로 전체를 수행한다. 최근 7일만 하면 오래된 대화는 갈라진 채 남아 "목록에서 한 파일이 여러 줄"
이라는 원 문제가 절반만 해소된다. `--days 7` 경로는 스크립트에 남겨 사용자가 언제든 좁힐 수 있다.

**파괴성에 대한 설계 판단**
- **되돌릴 수 있게 만드는 것이 1순위**였다 — 스냅샷 JSON 과 함께 **사람이 읽고 직접 실행할 수 있는
  롤백 SQL** 을 같이 남긴다. 도구가 없어도 복구되는 상태가 아니면 파괴적 변경을 돌리지 않는다.
- **정렬 기준은 CreatedAt** — 버전 번호는 "언제 올라왔는가" 를 따르는 것이 사용자 정신모델과 일치한다.
  기존 번호를 보존하는 안은 두 체인의 번호가 겹쳐(둘 다 v1 부터) 병합 자체가 성립하지 않는다.
- **SupersededAt 은 다음 버전의 CreatedAt** — `NOW()` 로 일괄 스탬프하면 "이 버전이 언제까지
  최신이었는가" 라는 사실이 지워진다. 사실에 가장 가까운 값을 넣는다.
- **UNIQUE 회피를 2단계로** — 같은 체인 안에서 번호를 재배열하면 중간 상태가 기존 행과 충돌한다
  (v1→v2 를 쓰는 순간 이미 v2 인 행과 부딪침). 오프셋에 `Id` 를 더해 대상 행끼리도 안 겹치게 했다.
- **PG 미러 동기화 필수** — 라이브 목록 read 가 PG 우선이라 미러가 어긋나면 같은 첨부가 두 줄로 남는다
  (선행 cycle `_mirror_chain` 이 같은 이유로 도입됐다). 다만 미러 실패는 fail-soft — MySQL 이 정본이다.
- **제외 규칙을 남긴 이유** — 사용자가 스스로 `draft_v1.sql`·`draft_v2.sql` 로 올렸다면 그것은 분열이
  아니라 의도다. 실측 0건이지만 규칙을 코드와 테스트에 남겨 다음 실행에서 오병합을 막는다
  (C6b 가 "제외 규칙이 과하지 않은지" 를 반대 방향으로 단정한다).

**시간대 (G7-a)**: `created_at` 의 시간대를 기억이 아니라 실측으로 확정했다 — 18:50 업로드가
`2026-08-06T18:50:29`, MySQL `NOW()`=KST, 컨테이너 TZ=Asia/Seoul. 오프셋 없는 ISO 를 `new Date()` 가
로컬로 해석하므로 그대로 넘기면 정합한다. 선행 cycle 의 `restorable_until`(UTC → `Z` 보정 필요)과
**반대**라, 그 보정을 여기 이식하면 9시간 어긋난다 — 뮤테이션 D1 이 그 회귀를 잡는다.

**남은 리스크**
- 병합 후 목록 줄 수가 줄어든다(3줄 → 1줄 + "버전 3개 ▾"). 데이터 손실은 0이지만 **사용자가 보던
  화면이 달라진다** — 의도된 결과이나 그 사실을 완료 보고에 명시한다.
- `MetaJson.version_diff` 는 저장 시점의 "직전 대비" 텍스트다. 시각순 정렬이라 대체로 유지되지만,
  분열 이전에 계산된 diff 가 새 이웃과 어긋날 수 있다. 화면 비교(`/diff`)는 요청 시점 계산이라 무영향.
- 라이브 적용은 배포 후 수행하며, 사후 재검증(잔여 0)과 목록 실측으로 확인한다.
- Artifact: 본 entry

## REV-20260807T004000-ai-claude-attach-chain-merge-rebase [SKIPPED:doc-only] — 형제 결정 흡수 기록

- Related TASK: feature-0003-agent-web-ui (20260806T2000-attach-chain-merge)
- Trigger: rebase 정합 — 형제 cycle 결정 반영 + main red 하네스 수리(실행 코드 1파일)
- Timestamp: 2026-08-07T00:40:00+09:00
- Verdict: PASS
- Human Approval Needed: no

**판단**: 형제 cycle 이 제거한 `_versionedFilename` 을 rebase 에서 되살리지 않았다 — 되살리면
그쪽 결정(저장명 규칙 서버 단일화)을 뒤집는 dead code 부활이고, 토글을 끈 뒤 한쪽 경로에만 접미가
남는 결함이 돌아온다. 선행 cycle 의 내 개선(idempotent 화)이 형제 결정으로 무의미해진 것을 인정하고
삭제했다.

**부수 수리**: 그 제거로 `verify_attach_multi_upload.mjs`(내 선행 산출물)가 **main 에서 실행 불가**
상태였다(`함수 미발견`). dead assertion 을 지우는 데 그치지 않고, (D) 축을 "저장명 생성 함수가
프론트에 없다 · 개별 다운로드가 서버 헤더 이름을 쓴다" 로 **재설계해 형제 결정 자체를 가드로 승격**
했다 — 다음 사람이 규칙을 다시 두 벌로 만들면 red 가 된다.
- Artifact: 본 entry
## REV-20260807T064000-ai-claude-attach-diff-syntax-css-fix [SKIPPED:hotfix-single-line-css] — SHIP

**패널 생략 사유**: 이 diff 는 CSS **주석 2줄**과 테스트 3단언뿐이며 새 사용자 표면·새 코드
경로가 0 이다. 원 변경(`20260806T1853-attach-diff-syntax`)은 직전 cycle 에서 §18.8 3도메인 패널
(security·ux·design)의 BLOCK 2 + CONCERN 1 을 전건 흡수했고, 이번 수정은 **그 패널이 승인한 CSS
규칙이 실제로 적용되게** 만드는 것 외에 아무것도 바꾸지 않는다(팔레트 값·셀렉터·굵기 정책 전부 불변).
패널을 다시 돌려도 검토할 새 판단면이 없다.

**판단 근거**
- 적발은 **PB-0008 라이브 computed style** 이었다 — `code-tok-keyword` 가 `rgb(38,37,30)`/400.
  파일에 규칙이 있는데 적용되지 않는 형태라 문자열 검사로는 원리적으로 보이지 않는다.
- jsdom CSSOM 으로 바꿔도 잡히지 않음을 **실측 확인**했다(cssom 파서가 관대해 깨진 버전도 13 규칙
  인식). 그래서 가드를 CSSOM 이 아니라 **주석 균형 + 셀렉터 위치 오염**에 걸었다 — 이번 실패 모드를
  결정적으로 잡고(재주입 시 F8·F10 red), 앞으로 같은 형태의 편집 사고를 차단한다.
- **한계 명시**: 이 가드는 "CSS 가 적용된다" 를 증명하지 않는다. 그 정본은 실 브라우저의 computed
  style 이며, 그래서 `visual_verification_scope: always` 가 이 저장소의 하드 게이트인 것이다.

**남은 리스크**: 없음(주석 문자 변경 + 테스트 추가).
- Artifact: 본 entry

## REV-20260807T070000-ai-claude-attach-diff-syntax-postdeploy [SKIPPED:non-code-doc] — SHIP

doc-only(실측 결과 기록 + 원장 등재). 코드·CSS·테스트 변경 0 이므로 적대 패널이 검토할 판단면이 없다.

**기록의 요지**: PB-0008 이 이 cycle 의 값을 증명했다 — 108건 하네스 + 3도메인 적대 패널 + 뮤테이션
9/9 를 통과한 변경에서 **실 브라우저만이 잡을 수 있는 결함**(CSS 규칙이 파서에게 삼켜짐)이 나왔다.
`visual_verification_scope: always` 가 형식이 아니라 게이트로 작동한 사례로 남긴다.
- Artifact: 본 entry

## REV-20260807T032000-ai-claude-attach-chain-live-dup [SKIPPED:tool-restricted:panel] — 라이브 적용 + 미러 충돌 수리

- Related TASK: feature-0003-agent-web-ui (20260807T0320-attach-chain-live-dup)
- Trigger: 파괴적 데이터 적용 결과 + 미러 정합 수리
- Timestamp: 2026-08-07T03:20:00+09:00
- Verdict: PASS (라이브 실측 근거)
- Human Approval Needed: no — 선행 cycle 의 사용자 승인 범위

**가장 중요한 교훈 — fail-soft 는 조용히 실패한다**: PG 미러는 설계상 fail-soft(정본은 MySQL)라
UNIQUE 충돌을 삼키고 "ok" 로 보였다. 스크립트의 사후 검증도 **MySQL 기준**이라 잔여 0 을 보고했다.
**MySQL↔PG 를 직접 대조하지 않았다면 29 row 가 옛 상태로 남은 채 완료로 보고됐을 것**이고, 라이브
목록 read 가 PG 우선이라 사용자 화면에서 같은 첨부가 두 줄로 보였을 것이다(§16.7 G8-b — repo 밖
권위 표면을 적용면에 포함). 사후 검증을 정본 한쪽만 보게 설계한 것이 내 실수다.

**미러를 2단계로 만든 이유**: 변경 대상만 밀면 그 자리를 차지한 *기존* 행과 다시 충돌한다 —
영향 대화 전체를 스코프로 잡아야 중간 상태가 풀린다. MySQL 쪽에서 이미 같은 결론을 냈으면서
미러에 이식하지 않은 것이 원인이었다.

**live>1 을 같은 판정에 넣은 이유**: 원인은 다르다(분열은 이름 갈림, 이건 supersede 누락).
그러나 **사용자가 보는 증상**(목록에 같은 파일 두 줄)과 **해소 수단**(체인 재정렬)이 같다.
C10b 로 "정합 체인은 건드리지 않는지" 를 반대 방향에서 단정해 조건이 과하지 않음을 고정했다.

**잔여**: PB-0008 라이브 시각검증(합쳐진 목록 · 날짜 표기).
- Artifact: 본 entry

## REV-20260807T133000-ai-claude-attach-diff-identical-source [SUBAGENT:ux] — CONCERN

- Related TASK: feature-0003-agent-web-ui (20260807T1300-attach-diff-identical-source)
- Trigger: UI/modal/screen keyword matched (모달·화면·표시)
- Timestamp: 2026-08-07T13:30:00Z
- Verdict: CONCERN
- Artifact: `unit/feature-0003-agent-web-ui/docs/reviews/20260807T1330Z-ux.md`
- Critical issue: 줄바꿈 계열 차이를 흡수한 `identical` 위에 "문서 원문" 이라는 더 강한 단정을
  얹었고(판별 근거 sha256 은 이미 응답에 있음), 절단 상태에서 "차이가 많아"/"차이 없음" 이 모순
- Human Approval Needed: no

**대응**: P2 3건 전부 같은 cycle 에서 수정 — `_identicalFlags` 신설(배너·배지 동일 판정) ·
절단 문구 상태별 분기 · 판정면을 `syncHlToggle` 과 동일화 + 초기 호출. P3 접근성·문서도 반영.
메타 요약 표 추가(권고 4)는 요청 범위 밖이라 REPORT.md §8 후속 제안으로 등재.

## REV-20260807T133001-ai-claude-attach-diff-identical-source [SUBAGENT:design] — CONCERN

- Related TASK: feature-0003-agent-web-ui (20260807T1300-attach-diff-identical-source)
- Trigger: UI/modal/layout keyword matched (모달·레이아웃·표시)
- Timestamp: 2026-08-07T13:30:00Z
- Verdict: CONCERN
- Artifact: `unit/feature-0003-agent-web-ui/docs/reviews/20260807T1330Z-design.md`
- Critical issue: 원문 표에 추가한 CSS 가 **no-op** 인데 하네스가 그 문자열 존재만 잠근다(항상
  통과하는 검사) + 절단 상태의 완결성 오진술 + 거짓 어포던스 규칙의 4상태 중 1개 적용
- Human Approval Needed: no

**대응**: dead CSS 삭제 · row dead class(`is-source` → `is-plain`) 정리 · D8 을 DOM 구조 단언으로
교체 · 컨트롤은 숨김이 아니라 **비활성**(ux 리뷰의 레이아웃 흔들림 지적과 수렴) · colgroup 계약
표에 `is-source` 행 추가 · `is-equal` opacity 비대칭을 "의도" 로 명시.
`base.css` 전역 `[hidden]` 종결 규칙(R4)은 기존 9지점 회수를 동반해야 안전해 후속으로 등재.
`is-same` 초록 어휘 충돌(R5)은 절단·해시 불일치 시 warn 으로 내려가 발생 빈도가 줄었고, 최종
판정은 PB-0008 실화면에 맡긴다.

**두 리뷰의 수렴점(가장 중요한 교훈)**: 이번 변경의 진짜 위험은 렌더가 아니라 **말**이었다.
"문서 원문" 은 전량을 봤을 때만 쓸 수 있는 단어인데, 초판은 (a) 행 상한 절단 — 이번 변경으로
**처음 도달 가능해진 상태** — 와 (b) 원본 1MB cap, (c) `splitlines()` 가 흡수하는 줄 종단자
차이 세 경우 모두에서 그 단어를 썼다. 화면의 세 요약(절단 배너·안내 배너·요약 배지)이 각자 다른
근거로 만들어져 서로를 반박한 것이 근본이며, 해소는 **판정을 한 곳(`_identicalFlags`)으로 모으는
것**이었다 — 서버에서 `identical` 판정을 한 번만 하도록 한 것과 같은 처방을 프론트에도 적용.
## REV-20260807T140000-ai-claude-attach-diff-intraline [SUBAGENT:ux,design,frontend,security,backend,qa]

- Trigger: `UI/modal/screen/layout` + `API/response shape` keyword matched (§18.8 dispatch 표)
  → ux+design · frontend+security · backend+qa 3 도메인 병렬 dispatch.
- **채널 결정 근거(정직)**: `codex review` 는 사용량 한도 소진(리셋 2026-08-09)으로 물리적 불가.
  Agent tool 은 이 세션의 상위 지시로 기본 금지라 §18.8 요구와 상충 → **자체 SKIP 하지 않고
  사용자에게 1회 확인**했고, 사용자가 subagent 패널 실행을 선택했다(§12.2 사전 승인 근거).

### 판정: BLOCK 2 (ux+design · backend+qa) + PASS-with-P2/P3 1 (frontend+security) → 전건 흡수

**P1 (4건, 전부 실재·수정)**

1. **탭 위 마크 0px** (ux) — `text-decoration` 밑줄은 탭 advance 위에 그려지지 않는다. 실측:
   마크 구간이 `\t\t` 일 때 span 박스 78×17 에 칠해진 픽셀 **0**(같은 폭 공백 8개는 48px).
   들여쓰기 변경은 이 기능이 정확히 겨냥한 경우인데 화면에 아무것도 없었고, 사용자에겐 "마크가
   없으니 통째로 바뀐 줄" 로 읽힌다. → `inset box-shadow` + `box-decoration-break: clone` 로 교체
   (같은 입력 156px · 줄바꿈 조각 복제 확인 · `background-color` 는 여전히 transparent 라 대비
   논거 유지). 회귀 잠금 = 기하 하네스 **M3b**(스크린샷 픽셀 카운트) + mjs **D6b**.
2. **정밀화 부재로 이 기능의 주 사례가 무응답** (ux) — `-- sha256: …855`→`…856`(한 글자) 이
   변경비율 0.853 > 0.85 에 걸려 세그먼트가 통째로 버려졌고, `work != 0` 이라 배너도 안 떴다.
   → 2단 정밀화 도입(토큰=정렬 앵커, 그 안에서 자소 단위로 좁힘) + 비율 컷을 **정밀화 이후**
   결과로 판정. 이제 `5`/`6` 한 글자만 마크된다. 잠금 = **B30**.
3. **정밀화가 자소 클러스터를 가름** (backend) — 초판 `_intraline_refine` 이 raw code point
   `SequenceMatcher` 라, 토큰화에 세워 둔 클러스터 보호를 정밀화 단계에서 무너뜨렸다. ZWJ 가족
   이모지·keycap·국기 3종에서 경계가 클러스터 **내부**에 떨어져 프론트가 span 을 쪼개면 합자가
   깨진다(가족 이모지 → 낱개 셋). → `_grapheme_clusters` 를 공용 primitive 로 뽑아 토큰화·정밀화
   **양쪽**이 쓰게 했다. 잠금 = **B35**(경계가 클러스터 경계 집합에 속하는지 단언).
   ⚠️ 기존 **B27 이 vacuous** 였다는 지적도 맞다 — 공유 코드포인트 0인 쌍이라 정밀화 경로를
   타지 않았다. B35 가 실제 경로를 태운다.
4. **브랜치 자체 테스트 red** (backend) — 내가 계약을 바꾸면서 B22/B29 를 갱신하지 않았다.
   → 두 테스트를 새 계약으로 재작성(단어 토큰은 *정렬* 단위이지 마크 단위가 아님 · 배너는
   비용 가드에만).

**P2 (5건, 전부 흡수)**

5. **비용 예산이 실제 비용을 못 막았다** (backend, 가장 중요한 구조 지적) — "토큰쌍" 통화가
   대리값으로 실패했다: ① 같은 명목 예산에서 실제 시간 **83배** 차(한글 9.2ms ~ `a,b;c.`
   767.6ms) ② 토큰화가 검사보다 먼저라 **예산을 한 푼도 안 쓰고 1,039ms** 소모 ③ 정밀화 비용이
   게이트 뒤에 더해져 한 행이 전체 예산을 1.33배 초과. → 통화를 셋으로 교체: **행별 문자쌍 컷**
   (토큰화 이전 O(1)) · **패스 경과시간**(대리값이 아니라 지키려는 값 자체) · **응답 바이트**.
   재측정: 2997→5.3ms · 2367→4.1ms · 1079→2.7ms · 1039→2.1ms · 정밀화 탈출 266→0.00ms.
   잠금 = **B33**(비용 가드 표면화) · **B34**(토큰화 전 판정을 monkeypatch 로 실증).
6. **렌더 노드 폭증** (frontend) — 서버 상한은 계산만 막는다. 6,000행 CSV 에서 chunk span
   60,000개 · 노드 222,007개(하이라이트 켜면 438,007), 표는 상호작용마다 전면 재구축.
   → 렌더-측 `MARK_RENDER_BUDGET`(12,000 span) + 초과 시 고지.
7. **배너 톤·문구** (ux) — 정밀도 절단이 내용 절단과 같은 amber `is-warn` 이라 "diff 가
   불완전하다" 와 같은 강도로 읽혔고, 사유를 "길어서" 로 말해 화면과 어긋났다(같은 길이의
   윗줄은 마크되는데 아랫줄만 안 되는 경우가 있다). → `is-note` 톤 분리 + 사유 문구 정정.
   잠금 = **D8b2/D8b3**.
8. **이색형 대비** (ux) — 삭제쪽 마크가 deuteranopia 시뮬레이션에서 저대비. 두 시뮬레이션
   모델의 절대값은 갈렸으나(내 계산 4.66 · 리뷰어 2.63) **방향은 일치**하고, 어느 모델에서도
   통과하도록 삭제쪽을 `#7f1d1d` 로 어둡게 잡아 **명도를 쪽 구분 채널로** 만들었다.
9. **ASCII 단어 vs 한글 글자 비대칭** (ux) — 사용자가 "글자 단위" 를 요청했는데 영문·숫자만
   통짜였다. → 2단 정밀화로 해소(항목 2와 같은 수정). 잠금 = **B22**(어절 통짜 아님) · **B30**.

**P3 (전부 흡수 또는 근거와 함께 수용)**

10. 과장 마킹 — 짧은 equal 흡수가 바뀌지 않은 글자를 칠했다(`년 `·CSV 구분자). → **흡수 규칙
    제거**. 파편화 방어는 정밀화 비율 컷이 이미 담당하므로 필요하지도 않았다. 잠금 = **B31**.
11. 악센트 라틴이 단어 런을 끊어 `café`→`cafe` 가 마크 0개. → `isascii()` 제거. 잠금 = **B32**.
12. 국기(RI 쌍)·emoji tag sequence 미보호. → `_grapheme_clusters` 에 포함. 잠금 = **B36**.
13. 길이만 비교하던 계약 가드 → **문자열 비교**로 강화(같은 길이의 다른 내용이 통과해 엉뚱한
    위치를 칠하는 재현 케이스 제시됨). 서버에서 도달 경로는 확인되지 않았으나 비용이 동일.
14. 무음 실패 → 렌더당 1회 `console.warn`(6,000행에서 매 행 경고하면 콘솔이 무용지물).
15. 재적용 시 chunk 중첩(현재 도달 불가·잠재) → 진입부 가드.
16. 기본 마크색 부재 시 `currentColor` 폴백 → base 규칙에 기본색 박음. 잠금 = **D6d**.
17. 두 렌더러의 세그먼트 전달 분기 불일치(오늘은 동작 동일) → 단일열도 무조건 전달.
18. `total <= 0` 죽은 분기 → 제거.

**수용하되 이번 범위에서 고치지 않은 것 (정직 표기 · REPORT §8 원장)**

- **응답 페이로드 증가**(6,000행 CSV 기준 +1.2MB): 512KB 세그먼트 상한으로 **완화**했으나
  원인 자체(원문 조각 재전송)는 남는다. 델타 인코딩은 계약을 복잡하게 만들어 별 cycle.
- **1~2글자 마크의 시각적 약함**(2px × 6px): 배경을 못 쓰는 제약에서 나온 결과다. 리뷰어도
  "찾을 수는 있다" 로 판정. 굵기는 이 표에서 이미 keyword 전용이라 쓰지 않는다.
- **초록 마크가 teal `number` 토큰과 1.09:1**: 좌/우 위치 중복 인코딩으로 완화되며, 값을 바꾸면
  구문 팔레트의 AA 계산을 다시 흔든다.
- **한쪽만 바뀐 줄의 반대쪽 무마크**: 그쪽은 실제로 바뀐 글자가 없으므로 **정확한 표현**이다.
- **`aria` 노출 부재**(WCAG 1.3.1): 기존 행 단위 색 처리와 동일한 성질이라 이 cycle 신규 회귀
  아님 — 표 전체의 접근성 표기는 별 cycle.

### 검증
- pytest **4,018 PASS / 0 FAIL** · ruff clean (컨테이너 오프라인 이미지, 외부 DNS 단절 우회)
- jsdom `verify_attach_version_diff.mjs` **124 PASS** · mjs 전수 **49 suite 전건 OK**
- 실브라우저 기하 `verify_attach_diff_geometry.py` **54 PASS**(M1~M5+M3b 신규)
- 구문 하이라이트 하네스 **113 PASS**(토큰 대비 G2 무회귀 — 마크가 배경을 안 칠하므로 3면 유지)
- Artifact: 본 entry + `docs/test-runs.d/20260807T1400-attach-diff-intraline.md`


## REV-20260811T113000-ai-claude-attach-diff-intraline-postdeploy [SKIPPED:non-policy-doc]

- doc-only POST-DEPLOY 실측 기록(코드 변경 0) — §18.8 dispatch 표 첫 행("비정책 doc-only")에 해당.
- 기록 대상은 배포본 `9f1622f9` 의 PB-0008 라이브 실측이며, 판정 근거는 그 Run 자체다
  (`docs/test-runs.d/20260807T1400-attach-diff-intraline.md`).
- **정직 표기**: 라이브 표본이 SQL 3버전 체인 1건이라, 탭 들여쓰기 변경·`is-note` 절단 배너·
  6,000행 체감은 이 Run 에서 확인하지 못했다. 각각 헤드리스 M3b · jsdom D8 계열이 잠그고 있으나
  **실 Windows 브라우저 픽셀로는 미확인**이다.
- Artifact: 본 entry
## REV-20260807T193000-ai-claude-attach-source-view [SUBAGENT:security] — CONCERN

- Related TASK: feature-0003-agent-web-ui (20260807T1900-attach-source-view)
- Trigger: API/endpoint keyword matched + 본문 bytes 노출 경로 신설
- Timestamp: 2026-08-07T19:30:00Z
- Verdict: CONCERN
- Artifact: `unit/feature-0003-agent-web-ui/docs/reviews/20260807T1930Z-security.md`
- Critical issue: 본문 응답에 `no-store`/`nosniff` 누락 · `get_object_bytes` 전체 적재로 최대 25×
  증폭 + rate limit 부재 · 절단 프리픽스에서 센 줄 수를 전체로 표기(실측 200,000줄 → "95326줄")
- Human Approval Needed: no

**대응**: P2 4건 중 3건(헤더·ranged read+rate limit·lines_partial) 같은 cycle 반영.
§21 window 미적용은 **첨부 read 계열 4경로 공통의 선재 갭**이라 한 경로만 봉인하면 같은 행의 ⬇ 가
열린 채 보호가 착시가 된다 — `docs/SECURITY.md §21.5` 6번에 수용 근거·봉인 조건·영향 범위와 함께
등재하고 4경로 동시 봉인을 후속 cycle 로 분리. P3 는 splitlines 범위 명시(AC 개정+S5)·ObjectKey
404 가드·except 축소·실물 게이트 테스트(E9) 반영.

**가장 값진 지적**: ranged read 로 바꾸면 `len(raw) > cap` 절단 판정이 **영원히 거짓**이 된다 —
증폭을 고치다 무음 절단을 만들 뻔했다. 판정을 DB 정본 크기(`SizeBytes`)로 옮기고 E10 이 고정한다.

## REV-20260807T193001-ai-claude-attach-source-view [SUBAGENT:ux+design] — CONCERN

- Related TASK: feature-0003-agent-web-ui (20260807T1900-attach-source-view)
- Trigger: UI/modal/screen/layout keyword matched (모달·화면·클릭)
- Timestamp: 2026-08-07T19:30:00Z
- Verdict: CONCERN
- Artifact: `unit/feature-0003-agent-web-ui/docs/reviews/20260807T1930Z-ux-design.md`
- Critical issue: 이 모듈이 **주석·문서로 이미 봉인해 둔 결함 기전 3종**이 새 화면에서 재발
  (스크롤 앵커 미적용 · click target 공통-조상 승격 · 절단 시 "원문" 단정) + 503 문구 도달 불가
- Human Approval Needed: no

**대응**: P2 7건 전부 반영(스크롤 앵커 · 503 payload `error` + 하네스 stub 실계약화 · press-pair
가드 · 파일명만 버튼으로 승격 · 버전 태그 + 버전 이력 행 👁 진입점 · 절단 시 제목/통계 강도 하향 ·
포커스 저장·복귀). P3 는 빈 컨트롤 바 숨김 · 액션 버튼 hover 억제 · kind 별 title · 모션 규약 가드.

**두 패널의 수렴점**: 두 리뷰가 **같은 결함을 다른 축에서** 지적했다 — 절단 상태의 "원문" 단정
(ux P2-6 = security P2-4)과 `role="button"` 중첩(ux P2-4 = security P3-6). 형제 화면이 직전 cycle 에
세운 계약(`_identicalFlags`·`modal-dismiss` press-pair·스크롤 앵커)을 **주석으로 인용하면서 절반만
옮긴 것**이 이번 cycle 의 지배적 실패 양상이다. 새 화면을 만들 때 "같은 primitive 를 쓴다" 는
렌더 함수 재사용만으로 성립하지 않고 **계약 전체**(스크롤·판정·어포던스)를 옮겨야 한다.
## REV-20260811T150000-ai-claude-attach-diff-mark-underscore [SKIPPED:css-only-visual-fix]

- Trigger: `UI/layout` keyword — 그러나 변경은 **CSS 선언 1종(마크 바 위치)** 과 그 회귀 잠금
  테스트뿐이다(백엔드·API·RBAC·스키마 0, JS 로직 0). §18.8 dispatch 표의 code change 행에
  해당하나, 판정에 필요한 근거가 **렌더된 픽셀**이라 bundle-only 리뷰어가 검증할 수 없는 축이다.
- 대신 **실 chromium 실측으로 판정**했다 — 이것이 이 변경에서 유일하게 유효한 증거다:
  - 재현: 실제 프로젝트 CSS 에서 마크 규칙만 `inset` 으로 되돌려 결함을 눈으로 확인.
  - 후보 4종을 같은 표 맥락에 렌더해 비교(윗줄·배경색 간격·padding·바깥 그림자).
  - 채택안에서 **글자 영역 마크색 픽셀 0**(대비 논거 유지) · 탭 도포 192px · 행 높이 불변.
  - 회귀 잠금 M6 를 픽셀 계측으로 신설.
- **정직 표기**: 적대 3자 검토는 받지 않았다. 판정 근거가 시각이라 자체 실측으로 대체했으며,
  그 실측 절차와 수치를 test-runs fragment 에 전부 남겼다. PB-0008 라이브는 배포 후 잔여.
- **부수 적발**: 기하 하네스 **M3b 의 클립 영역**이 span 박스 안쪽만 캡처하고 있어, 바가 박스
  바깥으로 이동하자 마크가 있는데도 0px 로 세어 **거짓 FAIL** 을 냈다. 하네스 아티팩트를
  고쳤다 — 픽셀 검사는 "무엇을 캡처하는가" 가 곧 계약이라는 사례.
- Artifact: 본 entry + `docs/test-runs.d/20260811T1500-attach-diff-mark-underscore.md`


## REV-20260811T160000-ai-claude-attach-diff-underscore-postdeploy [SKIPPED:non-policy-doc]

- doc-only POST-DEPLOY 실측 기록(코드 변경 0) — §18.8 dispatch 표 첫 행에 해당.
- 판정 근거는 배포본 `97e9c718` 의 PB-0008 Run 자체
  (`docs/test-runs.d/20260811T1500-attach-diff-mark-underscore.md`).
- **정직 표기**: 라이브 표본에 탭 들여쓰기 변경이 없어 그 축은 실 Windows 픽셀로 확인하지
  못했다(기하 M3b 가 192px 로 잠금). `is-note` 절단 배너도 동일.
- Artifact: 본 entry
## REV-20260811T130000-ai-claude-attach-version-action-align [SUBAGENT:ux+design] — CONCERN

- Related TASK: feature-0003-agent-web-ui (20260811T1200-attach-version-action-align)
- Trigger: UI/layout keyword matched (버튼 위치·정렬)
- Timestamp: 2026-08-11T13:00:00Z
- Verdict: CONCERN
- Artifact: `unit/feature-0003-agent-web-ui/docs/reviews/20260811T1300Z-ux-design.md`
- Critical issue: `min-width` 는 **바닥**이라 글리프가 넘으면 열이 다시 갈린다(하네스가 그 잘못된
  계약을 잠갔다) · 형제 목록 확장은 픽셀 근거 0 인데 AC 는 충족으로 단정 · [E] 가 소스 정규식이라
  슬롯 오배치를 통과시킨다
- Human Approval Needed: no

**대응**: P2 3건·P3 5건 전부 반영. 폭을 `flex: 0 0 22px; min-width: 0` 으로 못 박고, 휴지통을 실행
테스트로 승격, 활성 목록에 DOM-level control 로 픽셀 근거 확보. 하네스 28 → **34건**, 뮤테이션 7종.

**교훈 — 리뷰어의 수치는 틀렸는데 구조는 옳았다**: 리뷰어는 활성 목록 버튼이 24-25px 라 22px 가
바인딩되지 않는다고 계산했고, 그 수치는 실측(22.00px)으로 **기각**됐다. 그러나 "`min-width` 는
바닥이라 폭 고정이 아니다" 는 구조적 지적은 옳았고, 글꼴 확대 A/B 로 **실제 열 깨짐을 재현**했다
(22→24px, `👁` 1135→1133). 추정 수치가 틀렸다고 지적 전체를 기각했으면 그 결함을 놓쳤을 것이다 —
수치는 검증하고 **기전은 따로 판정**해야 한다.
## REV-20260811T183000-ai-claude-api-exposure-hardening [SKIPPED:subagent-dispatch-disabled]

- Trigger: `auth` · `API/endpoint` · `보안 헤더` 키워드 — §18.8 dispatch 표상 **security + backend +
  qa 패널이 걸리는 변경**이다(익명 표면·인가 경계·DB 계정 권한). 통상이라면 생략 대상이 아니다.
- **정직 표기 — 적대 패널을 받지 않았다.** 본 세션은 subagent 호출이 명시적으로 금지된 조건에서
  실행됐다. §18.4 의 `[SKIPPED:*]` 경로를 쓰되, **이것이 "리뷰 불필요" 판정이 아니라 "리뷰 미수행"
  임을 분명히 기록한다.** 보안 변경에서 3자 적대 검토의 부재는 그 자체로 잔여 리스크다.
- 대신 수행한 검증(패널 대체가 아니라 보완):
  - **라이브 실측으로 결함 재현** — 익명 3종의 종전 응답(provider·public_host·모델 카탈로그·장애
    epoch)을 실제 HTTP 응답으로 확인한 뒤 수정. 루트 응답의 보안 헤더 전무도 실측.
  - **인프라 축 교차검증** — `netsh portproxy` 규칙과 `WEB_ALLOWED_HOSTS` 등재로 외부 노출이 우발이
    아닌 구성임을 확정. 동시에 DB·스토리지 포트는 portproxy 부재로 **공인 도달이 없음**을 확인해
    감사자가 못 본 범위를 양방향으로 좁혔다(과대·과소 평가 모두 회피).
  - **회귀 잠금** — 미인증 축소뿐 아니라 **인증 응답 불변**을 같은 파일에서 단언한다. 축소가 기능을
    깎지 않았음을 테스트가 고정한다.
  - **감사자 지적의 반증** — "DB 읽기 전용 보장 없음" 을 코드로 반증(`sql_guard` sqlglot AST
    allowlist, **sqlglot 부재 시 fail-closed**). 외부 지적을 무비판 수용하면 이미 있는 통제를 중복
    구축했을 것이다. 반대로 처방(전용 SELECT 계정)은 `DB_USER=root` 폴백 실측으로 채택했다.
- **자체 적발(감사자 지적 밖)**: `/api/api-vault/options` 의 예외 처리가 fail-soft 를 넘어
  **fail-open** 이었다 — DB 예외 시 필터 전 전체 카탈로그로 되돌리는 구조라, DB 를 불능으로 만들 수
  있는 요청자가 오히려 전량을 받는다. 익명 축소를 하면서 같은 경로를 함께 닫았고 테스트로 잠갔다.
- **잔여 리스크(정직)**:
  - 적대 3자 검토 부재 — 재개 가능한 세션에서 `security+backend` 패널을 돌리는 것이 바람직하다.
  - CSP 는 Report-Only 라 **현재 강제력이 없다**. 위반 관측 후 enforce 승격이 남았다.
  - HSTS 미적용 — `/trust` 평문 CA 배포와의 충돌 때문이며, CA 배포 채널 변경이 선행 조건이다.
  - RO 계정 전환은 **재시작 전까지 무효**. 전환 후 데이터플레인이 실제로 `agent_ro` 로 나가는지
    (제어 연결은 `DB_USER` 유지인지) 라이브 확인이 남았다.
  - 공인 IP 노출 자체는 미조치(사용자 결정 대기).
- Artifact: 본 entry + `docs/SECURITY.md` §7.3·§7.4 + `tests/test_anonymous_surface_hardening.py`

## REV-20260812T010301-doc-sync-rn-0812 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-11(5항목)·2026-08-07(8항목) 2블록 prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 34/0 동일 = 회귀 0) · 구조검증(`generated`=2026-08-11 == `releases[0].date` · head 5항목 · `[1]`=2026-08-07 8항목 · releases 44→46 · 08-06(9)/08-05(3) 등 기존 44 블록 전량 보존 · type/area enum 위반 0 · 스키마 외 키 0) · 내부용어 누출 스캔 0(19 패턴 — 유일 매치 `report_v2_v2.csv` 는 사용자가 실제로 내려받은 파일명, 정본 `FUNCTION.md:3228`).
- 블록 date 판정: **배포 merge sha 의 날짜** 기준으로 08-07 / 08-11 두 블록으로 분할(author date 아님). `e14b0670`(author 08-07 19:22)은 정본 TASK 가 '배포 완료 2026-08-11 · PR #1196 merge `4c7a8f27`' 를 명시하므로 08-11 블록에 귀속했다. 기존 top block 은 08-06 이고 두 배포일 블록이 모두 부재해 신규 2블록 prepend(선례 `95b1c0d4` = 한 run 2블록).
- 적대검증(ULTRACODE `wf_d01b1421`, 2 렌즈 — A 사실정확성 / B 포함·제외 경계): 양 렌즈 `confirmed=false`, 결함 6건(MAJOR 1 + MINOR 5) + missed 3(전부 '누락 없음 확인' 또는 사유 정밀화 권고). **오케스트레이터가 정본·실코드로 전건 독립 재검증**해 6건 실재 확인, 4건은 사용자 문면에 반영·2건은 companion/판정값 정정.
  - **[MAJOR 반영]** identical(내용 동일) 화면에서 비교 전용 조작이 "나타나지 않습니다" = 사실 오류. `static/app/attach-diff.js:905-928` `syncDiffOnlyControls` 는 `b.disabled = !hasDiff` · `ctxCb.disabled` · `classList.toggle("is-disabled")` 로 **비활성화만** 하고, 같은 블록 주석이 「숨김이 아니라 **비활성**인 이유: … 사라지면 컨트롤 바가 통째로 흔들린다」로 숨김을 명시적으로 기각한다. `css/chat.css:2981-2982` `.attach-diff-ctxtoggle.is-disabled{opacity:.55;cursor:default}` = 흐리게 남는다(`display:none` 아님). → "'좌우 2열'·'단일열'·'동일한 줄도 모두 보기'처럼 비교에만 쓰이는 조작이 **흐리게 바뀌어 눌리지 않습니다**" 로 교정(실제로 컨트롤이 사라지는 것은 별도 원문 전용 모달뿐이고 본 항목이 서술하는 화면이 아니다).
  - **[MINOR 반영]** 배포 창 길이 "배포할 때마다 12~17초" 가 정본이 명시한 outlier 를 지웠다 — `feature-0014 docs/test-runs.d/20260811T1557-edge-rolling-gate.md:19` `| 창 길이 | 12~17초 (12:34 창은 41초) |`. → "12~17초(한 번은 41초)".
  - **[MINOR 반영]** 수정 전/후 대조에서 "같은 규모의 배포 구간" 이 정본의 핵심 논거를 지웠다 — 같은 파일 :75 `| 배포 창 요청 | 111 | 172 |` 와 :86 「트래픽 부족으로 503 이 "안 난" 것이 아니다 — 수정 전 12:40 창(111요청)보다 **많은 172요청**」. "같은 규모" 는 정본이 선제 반박한 해석(트래픽이 적어서 안 났다)을 되살린다. → "고치기 전 배포 구간에서는 **그보다 적은** 111건 중 10건이 실패".
  - **[MINOR 반영·오케스트레이터 재판정]** 아이콘 열 정렬 범위 "어느 행에서나 같은 열" 이 정본 보장 범위를 넘었다 — `docs/FUNCTION.md:3078-3080` 「**체인 간 정렬은 보장하지 않는다** … AC-AVA-1 의 스코프는 **한 체인 안**」. 코드로도 두 슬롯의 스코프가 다르다: `app/composer.js:1131` `canCompare = versions.length > 1`(체인 단위 ⇄ 슬롯) vs `:1693` `anyItemManage = arr.some(...)`(목록 단위 🗑 슬롯). 렌즈 B 의 교정안 '한 목록 안에서는' 도 ⇄ 슬롯 관점에서는 여전히 넓으므로 **정본 문면에 맞춰 '한 파일의 버전 이력 안에서'** 로 좁혔다('체인' 은 내부 용어라 사용자 언어로 치환).
  - **[MINOR 정정 — 적용 텍스트 아님]** draft `notes` 가 블록 수를 "현 39 → 41" 로 적었으나 실측 `grep -c '      date: "'` = **44** → 정확한 기대값은 46. 게이트 판정에 쓰는 값이라 정정하고 적용 후 46 을 실측 확인했다(직전 run 정본 기록 'releases 43→44' 와도 정합).
  - **[MINOR 정정 — companion 사유]** `a730be74`(구문 색 keyword 규칙 hotfix) 흡수 사유가 "배포 전에는 사용자가 색 기능을 본 적 없어" 로 적혔으나 커밋 본문이 「적발 = **배포본 6cd4afd2** PB-0008: keyword computed rgb(38,37,30)/400」 — 깨진 판이 실제로 배포된 뒤 라이브 computed style 로 적발됐다. 머지 실측 `d7f21469`→`6cd4afd2`(08-07 02:51), hotfix→`6a3b1a97`(03:06) = **배포 후 심야 15분 창**이다. 결론(별도 'fixed' 미신설)은 유지하되 TASK 사유 문면을 사실대로 정정했다.
  - **[missed 3건 처리]** ① 렌즈 A 가 `src/static/**` 변경 12커밋을 `git log --name-only` 로 전수 대조해 **미귀속 화면 변경 0** 확인(누락 없음) ② `ce6ae6e0` 제외 사유를 '장애 예방' 이라는 약한 서술에서 '대화 답변은 계정 폴백(`-chat` alias)이 흡수해 화면 증상 0, 실패는 폴백 없는 내부 alias 경로 한정'(정본 `feature-0007 TASK.md:406` bare alias 200 회복 기록)으로 정밀화 ③ `8dbc35ac` 의 미인증 `/api/models` 축소는 auth overlay·프론트 graceful catch·로그인 직후 재조회로 회귀 0 재확인 → 제외 유지.
- 포함/제외 판정 근거: 사용자향 13항목. 델타 비-머지 44커밋(08-07 후반 25 + 08-11 19) = 코드/사용자향 매핑 13항목(18커밋) + 제외 12건(개발자향·운영 가용성 자동화·보안 표면 축소·CI/trailer/형제결정·hotfix 흡수) + doc-only POST-DEPLOY·원장 종결 14건(18+12+14=44, 교집합 0·미귀속 0)(소유 항목에 증거로 흡수). **배포 게이트는 오케스트레이터가 물리 실측** — 델타로 바뀐 서빙 static **8종 전부** 라이브(`https://localhost:443/static/...`)가 브랜치 blob 과 byte-identical(빌드 주입 `?v=<hash>` 정규화 후), `/healthz` 200, 컨테이너 이미지 `d56367c8`(= HEAD)에 `git merge-base --is-ancestor 00431585 d56367c8` YES → 델타 44커밋 전부 라이브 반영 확증(POST-DEPLOY 커밋이 없는 항목까지 커버).
- **테스트 env 정직 표기**: `verify_release_notes.mjs` **34 pass / 0 fail** 은 본 cycle 에서 편집 전(baseline)·편집 후 **두 번 실제 실행해 측정한 값**이다. 다만 cycle 후반 재확인 시점에 무인 env 의 `/tmp` 정리로 `/tmp/node_modules/jsdom` 이 사라져 동일 명령이 `MODULE_NOT_FOUND` 로 미가동됐다 — **정본 HEAD(`d56367c8`) 의 pristine 릴리즈노트로 교체해도 동일 실패가 재현**되므로 본 변경과 무관한 환경 사유다. 측정된 34/0 은 지우지 않고 그대로 남기며, 후반 콘텐츠 검증은 `node --check` + 구조 grep(releases 46 · head date · enum · 기존 블록 보존)으로 갈음했다.
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + `deploy-web.sh asset_stamp_verify` 가 배포 시 content-hash 주입, 수동 bump 는 무효 churn + 게이트 무력화). wrapper system-prompt 의 수동 bump 지시는 07-12 이전 메커니즘 기준이라 부적용.
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.
- Timestamp: 2026-08-12T01:03:01+09:00
## REV-20260811T184500-attach-diff-bubble-chip [CODEX:frontend-ui] — CONCERN (P1 0 · P2 4, 전건 반영)

- Trigger: UI/button/modal/screen 키워드 매칭 (버튼·모달·화면) → §18.8 표상 `ux, design` 도메인.
  **채널 선택 근거(§18.8.2)**: 본 위임 세션에 "요청 없이 Agent tool 을 호출하지 말 것" 이라는
  **상위 우선순위 지시**가 걸려 있어 subagent panel 대신 §18.8.1 의 제약 없는 채널
  (`codex review --uncommitted`, codex-cli 0.146.0)로 검증했다. §18.8 의 "사전 승인" 은 repo
  정책이 부여할 수 있는 범위 안에서만 유효하므로 그 지시를 우회 근거로 쓰지 않았다.
- Scope: `src/static/app/messages.js` · `src/static/css/chat.css` ·
  `tests/verify_attach_bubble_diff_entry.mjs` (uncommitted diff 전량)
- Verdict: **P1(GATE) 0건**. P2 4건 — 전건 반영 후 재검증.
- Findings:
  - **[P2] 403 공통 토스트 중복** (`messages.js`) — `apiFetch` 가 403 에 이미 토스트를 내고
    throw 하는데 catch 가 또 낸다. 같은 사유가 두 번 뜨고 두 번째가 첫 번째의 표시 시간을
    리셋한다. → **반영**: `e.status === 403` 은 재표시하지 않음. 회귀 잠금 C7c·뮤테이션 M9.
  - **[P2] C8(중복 클릭) 테스트가 vacuous** (`verify_attach_bubble_diff_entry.mjs`) — 느린
    왕복 promise 를 만들어 두고 `apiFetch` stub 에 연결하지 않았고 클릭도 1회뿐이라, 두 번째
    in-flight 요청이 통과해도 통과한다(AGENTS.md 의 경계 false-pass 항목). → **반영**: 게이트를
    stub 에 실제 연결 + 3회 dispatch + `API_CALLS === 1` 단언. **이 수정이 구현 결함을 드러냈다**
    — `disabled` 는 trusted 클릭만 막아 dispatch 3회에 왕복 3회·모달 3개였다. 상태 플래그
    재진입 가드(`dataset.diffBusy`) 추가로 해소(C8b·C8d, 뮤테이션 M10).
  - **[P2] hover 에 하드코딩 `rgba`** (`chat.css`) — feature AGENTS.md '색상 / 토큰 규칙' 은
    `:root` 토큰만 허용한다. → **반영**: `--primary-soft`/`--primary` 로 교체(형제
    `.message-action-btn:hover` 와 동일 조합)하고 말풍선별 분기 제거. 회귀 잠금 D7·D7b,
    뮤테이션 M11. **부수 발견**: 토큰화 후 흰 칩(`--surface`)과의 배경 대비가 **1.09** 임을
    실측해 `inset` 테두리 신호를 추가(D7c·D7d, M12) — 리뷰 지적을 따르다 더 나은 결함을 찾았다.
  - **[P2] Windows-browser 검증 기록 부재** (신규 클릭 경로) — `TEST.md`/`test-runs.d` 에 Run
    이 없어 CHECK#13 hard gate 대상. → **반영**: PB-0008 실 Windows Chrome/150 실측 후
    `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md` + `TEST.md` Run 기록.
- Human Approval Needed: no (Minor §12.3 — 비파괴 UI 추가, 신규 권한·엔드포인트·스키마 0)

**교훈 — 리뷰가 테스트를 고치게 하자 구현이 red 가 됐다**: P2 두 번째 지적은 "테스트가
느슨하다" 는 것이었고, 그것만 고치면 끝날 일로 보였다. 그러나 느슨함을 제거한 테스트는
구현이 실제로는 중복 왕복을 허용함을 드러냈다 — `disabled` 속성 하나에 방어를 걸었던 것이
원인이다. **테스트를 통과시키려 테스트를 바꾸는 것과, 테스트를 정직하게 만든 뒤 구현을
고치는 것의 차이**가 이 항목에 있다.

## REV-20260812T003000-attach-diff-bubble-chip-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

- Trigger: doc-only (TASK/TEST/MODIFY + fragment Run 2 + 증거 1매). 코드·정책 doc 변경 0 →
  §18.8 표 첫 행(비정책 doc-only) 적용, panel skip.
- 근거 실측: 라이브 서빙 `messages.js` byte-identical(main `eac20796`) · 칩 `⇄` → diff 패널
  `v1 ↔ v2` PASS · pageerror 0 — 배포 전 프리뷰 결과와 차이 0.
- Human Approval Needed: no

## REV-20260812T172625-ai-claude-corp-db-picker-layout-stability [CODEX:frontend-admin-layout] — CONCERN → PASS (P1 1 · P2 1, 전건 반영 후 재실행 P1 0 · P2 0)

- Trigger: `UI / layout / 화면` keyword matched (§18.8 dispatch 표 — ux, design).
  **채널 선택**: 본 세션에 "요청 없이 Agent tool 을 호출하지 말 것" 이라는 **상위 우선순위
  하네스 지시**가 걸려 있어 §18.8.2 *상위 우선순위 지시 carve-out* 을 적용, subagent panel 대신
  제약 없는 채널로 검증했다 — `codex review --uncommitted`(§18.8.1 경로 2, check #9 accepted)
  + 실 브라우저 기하 실측(PB-0008) + 뮤테이션 역검증. ux/design 렌즈의 **판정 대상**(레이아웃
  이동·가시 행 수·방향 지시어)은 이 채널들이 픽셀·DOM 수준에서 직접 잰다.
- **왜 순서 변경인가 (대안 3안 비교)**: (a) 스크롤 보정 — 변경 전후 rect 델타만큼 스크롤
  조상을 되감는 방식. **불채택**: 위쪽에서 행이 *제거*될 때 필요한 보정량이 현재 `scrollTop`
  보다 크면(예: 상단 근처) 음수 스크롤이 불가능해 **원리적으로 실패**한다. (b) 편집 중 목록
  높이 동결 — 드롭다운이 열린 동안 목록을 고정 높이 스크롤 박스로. **불채택**: 빈 목록에서
  열면 1행짜리 박스가 되고, 열림/닫힘마다 새 점프가 생긴다. (c) 드롭다운을 `position:fixed`
  포털로. **불채택**: TASK-0240 이 클리핑 때문에 절대배치를 **의도적으로 버린** 결정을 되돌리게
  된다. → **(d) 재구성 대상을 picker 뒤로**: 코드 3줄, 사후 계산 0, 모든 스크롤 위치·모든
  변경량(단건·일괄)에서 성립. IA 로도 "액션 → 그 결과 목록" 순서라 자연스럽다.
- **결함 계량이 먼저**: 고치기 전에 실 chromium 으로 38.3 / 37.4 / 114.3 / 42.0px 를 재고
  시작했다. 행 높이 29px 과 비교해야 "성가심" 이 아니라 **오클릭 위험**임이 드러난다 — 임계를
  넘는지 몰랐다면 tolerance 1px 짜리 게이트를 세우고 스스로 만족했을 것이다.
- **하네스가 vacuous 하지 않음을 스스로 증명**: 두 하네스 모두 축마다 "순서를 되돌리면 반드시
  실패" 를 함께 단언한다. jsdom 축의 핵심은 순서 비교가 아니라 **토글 전후 picker 상류 마크업
  바이트 동일** — 나중에 누가 picker 위에 요약 배지를 넣으면 순서 단언은 통과해도 이 축이 red 다.
- **판정 임계는 정직하게**: 수정 후 잔여 이동이 0.3~0.9px 로 관측됐다(무관한 상위 요소의 분수
  픽셀 반올림, 토글 수에 비례 누적하지 않음을 L3 로 확인). 1px 경계 게이트는 잡음에 흔들리므로
  임계를 4px 로 두고 **그 근거를 파일에 적었다** — 결함은 38px, 잔여는 1px 미만, 부분 회귀
  (10px)는 여전히 잡힌다. 정확한 잠금은 DOM 순서 불변식이 담당한다.
- **codex 적대 리뷰 (P1 1 · P2 1, 전건 반영)**:
  - **[P1] Windows-browser 검증 기록 부재** — `visual_verification_scope: always`(FIRST_REQUEST)
    하 check #13 hard gate. → **반영**: PB-0008 실측 후
    `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md` + `TEST.md` Run 기록.
  - **[P2] 방향 지시어 잔존** — `_renderDsAccordion()` 의 "바인딩된 데이터소스 없음 — … **아래에서**
    데이터소스를 선택해 추가하세요" 가 picker 를 accordion 앞으로 옮긴 뒤 **반대 방향을 가리킨다**.
    → **반영**: 문구 교체 + **파일 전수 census**(사용자 문자열의 "아래에서" 잔존 0) 를 회귀 축으로
    신설. 내가 등록 DB 목록 쪽 문구 한 곳만 고치고 끝냈던 것 — 방향 지시어는 위치를 옮길 때마다
    갈라지므로 개별 수정이 아니라 census 로 잠가야 한다는 것이 이 지적의 실질이다.
- **범위 밖으로 남긴 것 (REPORT §8 등재)**: pending 0 → 1 로 넘어가는 **첫** 토글에서 하단 커밋
  바가 나타나며 스크롤 컨테이너가 56px 짧아진다. 컨텐츠 y 는 그대로라 밀림은 아니지만, 바닥까지
  스크롤된 상태였다면 clamp 로 한 번 튈 수 있다. 이는 별개 기전이고 커밋 바 상시 숨김은
  2026-07-28 사용자 요구(graph-noise-reduce)로 **의도적으로 내린 결정**이라, 그 결정을 부수효과로
  뒤집지 않고 관측만 남긴다(§13.1 명시 비활성화 블록 = 운영자 의도 보존).
- **프리뷰 캐시 함정 재확인**: CSS 변경이 프리뷰에서 1차 측정 시 반영되지 않았다(220px). 배포
  스탬프가 같은 URL 이라 `immutable` 로 붙들린 것 — 고유 쿼리 stylesheet 를 새로 붙여 실제 서빙
  파일로 재측정(420px/10행)했고, **배포본 재확인을 POST-DEPLOY 로 이월**했다.
- Human Approval Needed: no (Minor §12.3 — frontend 표현 계층, 권한·엔드포인트·스키마·마이그레이션 0)

## REV-20260812T181000-ai-claude-corp-db-picker-layout-stability-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

- Trigger: doc-only (TASK/TEST/MODIFY + fragment Run 2 + 증거 1매). 코드·정책 doc 변경 0 →
  §18.8 표 첫 행(비정책 doc-only) 적용, panel skip.
- 근거 실측: 라이브 배포본(main `d619259d`)에서 실 Chrome/150 으로 이동 **0px**(역검증 +38px)
  + 드롭다운 420px/가시 10행 — **이월했던 캐시 축을 우회 없이 종결**. 엣지 `no upstreams
  available` 0건. 서버 정본 무변경(pending 미적용).
- Human Approval Needed: no
## REV-20260812T181700-ai-claude-hangul-qwerty-search — 한/영 자판 교차 검색

**판단 1 — primitive 를 왜 `shared/` 에 두는가.** 처음엔 feature-0003 의 `src/modules/` 에
뒀다가, 이미지 레이아웃(`unit/feature-0002-agent-core/src/Dockerfile`)을 확인하고 옮겼다:
`/app/modules` = feature-0002, feature-0003 의 modules 는 `/app/web/modules`(`from web.modules
import …`). 즉 `from modules.hangul_qwerty import …` 는 **런타임에 ImportError** 가 되고,
호출부가 fail-soft 라 예외를 삼켜 "기능이 조용히 죽은 채 배포" 되었을 것이다. 게다가 그래프
검색(feature-0002 `metadata_graph.py`)도 같은 매핑표를 써야 하므로, 두 서비스가 공유하는
`shared/`(Dockerfile 이 정확히 이 용도로 `/app/shared` 에 배치) 가 정답이다. §17 교차참조를
`shared/docs/MODIFY.md` 에 남겼다.

**판단 2 — 후보 최소 길이 2자(오탐 억제).** 자판 변환은 정상 검색에도 새 매칭을 더한다.
한글은 자모가 음절로 합쳐져 **짧은 영문이 1글자 한글**이 되기 쉽고(`dk` → `아`), 그 1글자는
아무 목록에나 걸린다 — 기존 하네스가 이를 실측으로 잡았다(제품 검색 `dk` 가 "DK온라인" 외에
"글로벌 라이브" 까지 매칭). 사용자 의도는 **잘못 친 검색어의 구제**이지 정상 결과의 확장이
아니므로 2자 미만 후보는 채택하지 않는다. 요청 예시 4건은 전부 2자 이상이라 무손실.
- 검토했으나 불채택: "원문 매칭이 0건일 때만 변환 후보로 재시도"(2-패스). 오탐이 0 이 되지만
  서버 검색은 커서 페이징과 rate-limit 이 걸린 단일 쿼리라 2-패스가 페이징 계약을 깨고,
  클라이언트만 2-패스로 하면 같은 검색어가 화면마다 다르게 동작한다. 균일성을 택했다.

**판단 3 — 서버 비용.** 후보가 2개면 LIKE 항이 2배가 된다. EXISTS 서브쿼리를 후보마다 반복하지
않고 **서브쿼리 안쪽에서 컬럼을 OR 전개**(`_like_any_clause`)해, 늘어나는 것은 컬럼 비교뿐이고
서브쿼리 수는 그대로다. 대화 본문 검색은 이미 per-account 10req/min rate limit 과 감사 로깅이
걸린 경로이며(REQ-20260518-0010), 변환 대상이 없는 검색어는 후보가 1개라 종전과 동일한 SQL 이
나간다. `LIKE ANY(ARRAY[…])` 는 PG 문법상 `ESCAPE` 와 병용 불가라 쓰지 않았다(SECURITY §8.3
escape 규약 유지가 우선).

**판단 4 — escape 규약.** 변환은 자판 매핑이라 `%`/`_`/`!` 를 새로 만들지 않지만, escape 는
후보마다 개별 적용한다(단일 진입점 유지). 보관 대화 검색(`admin_conversations`)은 **종전부터
escape 를 걸지 않았고**, 그 동작을 이번 cycle 에서 바꾸지 않았다 — 후보만 늘렸다(범위 밖 변경
회피). 그 비대칭은 `_archive_search_likes` docstring 에 명시했다.

**판단 5 — 하네스 보강 vs 완화.** 기존 하네스 4종이 `searchVariants is not defined` 로 깨졌다.
이는 classic 주입 realm 이 새 import 를 모르기 때문이며(`esm-classic-inject.mjs` 가 "그 시점에
심볼 stub 을 선주입하라" 고 예고한 상황), **stub 대신 정본 소스를 주입**했다 — stub 을 두면
하네스가 검색 동작을 vacuous 하게 통과시킨다. `test_graph_search_content` 2건도 단언을 약화하지
않고 "플레이스홀더 수 = 파라미터 수" 정합으로 **강화**했다.

**범위 밖(의도적 미적용)**: AI 도구가 스스로 만드는 내부 질의 — `modules/file_ops.py`(대화 검색
툴), `modules/schema.py`(테이블 후보 탐색). 사용자 타이핑이 아니라 모델 생성 질의라 자판 오타가
성립하지 않고, 후보 확장은 순수 비용이다.

## REV-20260812T181700-hangul-qwerty-search [CODEX:search-layout-conversion] — CONCERN → PASS (P1 0 · P2 5 · P3 1, 전건 반영)

- Related TASK: feature-0003-agent-web-ui (`20260812T1817-hangul-qwerty-search`)
- Source: codex exec `--sandbox read-only` (staged diff 적대 리뷰, 6축 지정)
- Trigger: `query/쿼리`(SQL LIKE 조립) + `UI/화면`(검색창) keyword matched → dispatch 표상
  backend·qa·ux·design. **채널 선택 근거**: 본 세션에 "요청 없이 Agent tool 호출 금지" 상위
  우선순위 지시가 걸려 있어 §18.8.2 *상위 우선순위 지시 carve-out* 을 적용 — subagent panel
  대신 제약 없는 채널(codex)로 4축을 모두 지정 리뷰했다. `[SKIPPED:tool-restricted:*]` 없음
  (security 축은 본 변경에 인증·권한·세션 표면이 없어 dispatch 대상 아님).
- Timestamp: 2026-08-12T18:17:00+09:00
- Verdict: **CONCERN → PASS** (P1 0건. P2 5 · P3 1 전건 반영 후 재검증)
- Human Approval Needed: no

### 지적 6건과 처리

1. **[P2] 감사 로그 필터 LIKE escape 누락** (`_audit_infra.py`) — 종전부터 escape 가 없어
   검색어의 `%`/`_` 가 와일드카드로 샜다. 내 변경이 그 라인을 건드렸으므로 같은 cycle 에서
   **SECURITY §8.3 규약(`ESCAPE '!'` + 3-char escape)에 맞췄다**. 회귀 테스트 신설.
2. **[P2] 보관 대화 검색 LIKE escape 누락** (`admin_conversations.py`, PG·MySQL 양쪽) — 동일.
   최초 판단은 "종전 동작 보존" 이었으나, 규약 위반 상태를 그대로 두는 것이 아니라 **함께
   봉인**하는 것이 맞다. 두 경로 모두 `ESCAPE '!'` + escape 적용 + 테스트.
3. **[P2] 그래프 relevance 점수가 원문만 반영** (`metadata_graph.py`) — 정확한 지적이며
   **기능 무력화 경로**였다. 변환 후보로 매칭된 노드는 pg_trgm similarity 가 ≈0 이라, 점수
   정렬 후 `limit` 재절단에서 통째로 탈락한다(매칭됐는데 결과에서 사라짐). 점수를 **후보
   집합의 최댓값**으로 산출하도록 수정(후보 1개면 종전 식과 동치).
4. **[P2] 최소 길이 게이트가 후보에만 적용** (`hangul-qwerty.js` · `hangul_qwerty.py`) —
   내 게이트는 후보 길이만 봤다. 반대 방향(1자 원문 `가` → 2자 후보 `rk`)이 열려 있어
   `marketing`·`worker` 같은 무관한 항목이 잡힌다. **원문에도 동일 게이트**를 걸어 1자
   검색어는 확장 자체를 하지 않는다. 요청 예시 4건은 전부 2자 이상이라 무손실.
5. **[P2] 쿼리 비용 과소평가** — 단정 대신 **실측**했다. 라이브 PG(core_conversations 349행 ·
   core_messages 7,164행 · messages 1,956행)에서 `EXPLAIN ANALYZE` 로 대화 검색 WHERE 를
   재현: 후보 1개 **108.2ms** → 후보 2개 **203.2ms**(약 1.88×), PG `statement_timeout`
   3,000ms 대비 **6.8%**. **단일 표본·현행 데이터 규모 기준**이며, 데이터가 10배 규모가 되면
   timeout 에 근접할 수 있다 — 후보는 최대 1개만 추가(상한 2×)되고 원문 2자 게이트가 최악
   케이스를 줄이며 per-account 10req/min rate limit 이 유지되지만, **증가 추세는 재평가
   대상**으로 REPORT §8 에 등재한다(선행 인덱스가 없는 `%…%` 스캔이라는 성질은 본 변경 이전과 동일).
6. **[P3] 결과 강조가 원문만** (`app.js _searchHighlight`) — 반대 자판으로 매칭된 결과는
   원문이 본문에 없어 강조가 하나도 안 붙고, 사용자는 "왜 이게 나왔는지" 를 알 수 없다.
   후보 집합을 하나의 교대 패턴으로 강조하도록 수정(후보 1개면 종전 정규식과 동치).

### 재검증 (반영 후)

- 신규 mjs **49 PASS** · 신규 pytest **41 PASS** · feature-0003 프론트 mjs **54 suite 전건 PASS**
- 전 pytest 스위트 = main 기준선과 동일 실패 집합(`test_oauth_exhaustion_gate` = `chattr` 부재 1건)
## REV-20260812T184500-ai-root-metadata-pane-refresh — 메타데이터 pane 입력 UI 통합 표 재구성 (Major §12.3)

- **Trigger**: 사용자 요청(표현 계층 재구성). frontend 3파일 + 신규 하네스 2종. 백엔드·라우터·
  권한·엔드포인트·스키마·마이그레이션 **0**.
- **판단의 중심 — "촌스럽다" 를 취향이 아니라 계약 위반으로 환원했다**: 색·간격을 눈으로 고르는
  대신, 이 pane 이 **앱이 이미 가진 토큰·계약을 안 쓰는 지점 8개(D1~D8)를 코드 근거로 열거**하고
  각각을 정본 계약에 붙였다. 그래서 "다른 화면에 비해" 라는 사용자 표현이 정확했다 —
  `base.css .field input:focus` 는 3px halo 인데 `.admin-meta-input:focus` 는 `border-color`
  단독이었고, `--tag-*` 시맨틱 토큰이 같은 파일에 있는데 상태는 raw `●`/`○` 텍스트였고,
  `var(--mono)` 가 있는데 식별자는 하드코딩 스택이었고, 다른 pane 은 모두 ASCII `+` 인데 여기만
  전각 `＋` 였다. 이 프레이밍이 없으면 재구성은 다음 사람이 또 뒤집는 취향 변경이 된다.
- **가장 비싼 실패 모드를 구조로 차단**: 골격 그리드의 저장·AI 일괄·힌트·필터·페이징은 전부
  **DOM 순회**다(`.admin-meta-bs-desc[data-kind]` 등). "입력한 설명이 저장에서 조용히 누락" 이
  이 화면의 최악 결함이므로, **셀렉터·dataset 계약을 1개도 바꾸지 않고 시각만 CSS 로 교체**하는
  설계를 택했다. 그 결과 회귀 표면이 정의상 0 이고, 하네스 `[C1-계약]` 12항이 그 동일성을 정적으로
  잠근다. (대안 = 그리드를 `<table>` 로 재작성 → 시각 자유도는 크지만 수집 로직 전면 재작성 +
  페이징의 "전체 DOM 수집" 불변식 재검증이 필요해 비용·위험이 이득을 넘는다. 불채택.)
- **검증 층을 목적별로 나눴다**: 정적 CSS 단언(mjs)은 cascade 승부·픽셀 정렬·대비·줄바꿈을
  **원리적으로** 볼 수 없다(jsdom 은 layout 미계산). 그래서 headless Chromium 실렌더 계측을
  PRE-DEPLOY 보조 게이트로 두고, 완료 게이트는 PB-0008 실 Windows Chrome 으로 유지했다.
  **이 분리가 실제로 결함 2건을 배포 전에 잡았다** — 대비 미달 2건(headless 계산)과 sticky
  padding 띠(PB-0008 캡처 판독). 정적 단언만으로는 둘 다 통과했을 것이다.
- **테스트 자체의 오진을 3번 정정했다 (기록 가치)**:
  1. `rule()` 헬퍼가 indexOf 매칭이라 `.admin-meta-input:focus` 검색이
     `.admin-meta-field.is-error .admin-meta-input:focus` 에 먼저 걸려 **다른 규칙 본문**을 반환했고,
     셀렉터~`{` 사이 공백 2칸에 결속돼 규칙을 못 찾고 "없음" 으로 오판했다 → 규칙 파서 + 정규화
     셀렉터 완전일치로 교체.
  2. headless 합성 페이지가 `body.admin-shell` + `.admin-list-detail` 그리드를 그대로 써서
     **두 번째 트랙이 0 으로 붕괴**(행 폭 24px = padding 합)했고, 정렬 계측이 무의미했다 →
     상세 컬럼 고정 폭으로 변수 제거.
  3. sticky 판정을 **절대 y 를 컨테이너 상단과 비교**해 실패로 읽었다. sticky 는 padding box
     기준이라 `top:0` 이어도 border+padding 아래에 선다 → 판정을 **위치 불변성**(추가 스크롤 후
     동일)으로 바꿨다. 앞선 focus 가 스크롤을 옮겨 before/after 부호가 뒤집힌 오진도 함께 정정.
  교훈: **초록/빨강을 그대로 믿기 전에 그 단언이 무엇을 재는지 확인한다.** 세 번 모두 "코드가
  틀렸다" 가 아니라 "계측이 틀렸다" 였고, 그중 하나(3번)는 실제 결함을 가릴 수도 있었다.
- **대비 승격의 이중 성격**: 상태 라벨 `--text-muted`(4.12:1) 는 **종전 힌트에도 있던 선재 미달**
  이다. 재구성 대상이라 같은 cycle 에서 고쳤고, 이를 "본 변경이 만든 결함 수정" 으로 오기하지 않는다.
- **sticky inset 의 결합을 숨기지 않았다**: `--meta-grid-head-inset: 18px` 는 스크롤러
  `.admin-detail-col` 의 `padding-top` 에 결합돼 있다. 결합 자체를 없앨 수 없으므로(공유 클래스의
  padding 을 이 pane 때문에 바꿀 수 없다) **하네스가 두 값의 동치를 검사**하게 해서 무언의 drift 를
  검증 대상으로 전환했다. 값이 벌어지면 띠가 다시 생기거나 헤더가 카드 테두리를 넘는다.
- **위험·한계 (정직 표기)**:
  - POST-DEPLOY 라이브 재확인 **미완** — 본 Run 은 §13.2.9 격리 컨테이너(베이스 이미지
    `d619259d`) 기준이다. JS/HTML 변경을 포함하므로 `docker cp` 프리뷰는 원리적으로 불충분
    (모듈 캐시·스탬프 미주입)이며, 배포 후 baked 자산 재실측이 완료 조건이다.
  - 반응형(확대 200% · 폭 <720px)은 미측정. 통합 표 열 폭이 `clamp()` 라 붕괴 위험은 낮으나 실측 아님.
  - `.admin-meta-scope-select` 는 **그래프 뷰 pane 과 공유**한다. chevron·halo 개선이 그쪽에도
    적용되며(의도된 정합), 레이아웃 영향은 우측 padding 확보뿐이나 그래프 pane 은 실측하지 않았다.
- **§18.8 dispatch**: UI/레이아웃·표시 계층 단독 변경(ux/design 축)이며 보안·계약·스키마 표면 0.
  대비·정렬·상태 판독성은 **실렌더 정량 계측**(WCAG 계산 · 픽셀 편차 · elementFromPoint)으로
  대체 검증했고, 그 계측이 결함 2건을 실제로 적발했다 → 패널 skip.
- Human Approval Needed: no — 사용자가 진입 시 시각 방향("통합 표 + 프리미티브")과 범위
  ("메타데이터 pane 전체")를 명시 선택했고(TASK.md PLAN-APPROVED 2026-08-12), 구현은 그 두
  선택의 분해로 범위를 확대하지 않았다. §12 승인 항목(인증·인가·파괴적 데이터·개인정보·외부
  비용·롤백 어려운 마이그레이션) 해당 0.

## REV-20260812T191500-ai-root-metadata-pane-refresh-codex [CODEX:metadata-pane-refresh] — CONCERN (P1 0 · P2 3, 전건 반영)

- Related TASK: feature-0003-agent-web-ui
- Source: codex review (codex-cli 0.146.0 `--uncommitted`)
- Trigger: UI/layout/form keyword matched (§18.8 표 "UI, form, layout / 폼, 화면, 레이아웃" 행 →
  ux·design). AgentTool subagent 패널 대신 §18.8.1 이 check #9 accepted 로 인정하는 codex-review
  경로를 썼다 — 본 세션은 subagent 호출이 허용되지 않았고, ux/design 축(대비·정렬·상태 판독)은
  이미 실렌더 정량 계측(WCAG 계산·픽셀 편차·`elementFromPoint`)으로 검증돼 있어 독립 코드 리뷰가
  더 보완적이었다.
- Timestamp: 2026-08-12T19:15:00+09:00
- Verdict: CONCERN (P1 0건 / P2 3건) → **3건 전건 반영 후 재검증**
- P2 지적과 처리:
  1. **잘린 컬럼 식별자의 회수 경로 부재** — 열 정렬을 위해 `.admin-meta-bs-col-name` 을 고정 폭 +
     ellipsis 로 바꿨는데 `metadata.js` 는 `textContent` 만 넣어, 긴 컬럼명이 판독 불가가 된다.
     정렬을 얻고 식별자를 잃으면 순손실이라는 지적이 정확하다. → 컬럼명·타입 모두 `title` 부여
     (tables 모드 테이블명이 이미 쓰던 규약과 통일) + 타입 칸 폭 5.5rem → 7rem. 하네스
     `[C4-D8]` 4항으로 "잘림을 만드는 CSS 와 회수 경로가 같은 요소에 짝지어야 한다" 를 잠갔다.
  2. **동적 라벨의 전각 `＋` 잔존** — 정적 markup 3곳만 고쳤고 `metadata.js` 가 생성하는
     empty-state 문구와 ENUM '코드 추가' 버튼에 글리프가 남아 있었다. 사용자에게는 같은 pane 에서
     여전히 보인다. → JS 동적 문자열 3곳 교체 + 하네스가 **JS 소스까지 스캔**(`[B6-D5]`).
     정적 markup 만 검사하던 초판 단언이 이 누락을 통과시켰다 — 검사 표면이 좁았던 것.
  3. **pane 지역 토큰의 리터럴 색** — `--meta-ring: … rgba(37,99,235,.12)` 처럼 값을 복제했는데,
     `docs/AGENTS.md` §색상/토큰 규칙("모든 색상은 :root 토큰만 사용")·§10("인라인 하드코딩 색상값
     사용" 금지) 위반이고 팔레트 변경 시 이 pane 만 뒤처진다. → 전부 `:root` 파생으로 전환
     (`color-mix(in srgb, var(--primary) 12%, transparent)` 등) + hover 경계 리터럴 `#d4d2ca` 도
     `--meta-border-hover` 파생으로 교체. `:root` 자체를 확장하지 않아 §10 의 ADR 요건 비대상이다.
- **파생 전환이 값을 바꾸지 않았음을 실측으로 확인** (문자열 비교로는 불가 — Chrome 은
  `color-mix()` 를 `oklab()`/`color(srgb …)` 로 직렬화한다): 흰 배경 합성 픽셀 대조로
  headless Δ=0(`[228,236,253]` 양쪽), 실 Windows Chrome Δ=1(base `[228,236,253]` vs meta
  `[228,236,252]` — 1/255 한 채널, srgb `color()` 경로의 반올림이며 지각 불가). 등가 판정을
  **정적 문자열 → 합성 픽셀**로 옮긴 것이 이 cycle 의 계측 개선이다.
- **data URI 안 SVG 색은 파생 불가** — 브라우저가 `url()` 안에서 `var()` 를 해소하지 않고,
  `mask-image` 로 토큰화하면 입력의 배경 fill 을 잃거나 wrapper 요소가 필요해 markup 을 넓게
  건드린다. 이 한 곳만 `--text-muted` 값을 복제하고, 하네스가 base.css 토큰과 **대조 검사**해
  무언의 drift 를 검증 대상으로 전환했다(sticky inset 과 동일 기법).
- 재검증: mjs **90 checks**(뮤테이션 **15/15 KILLED** — 2라운드 누적) · headless **32 checks** ·
  mjs 53 파일 전건 green · pytest 1,390 PASS(feature-0003+0023) · 실 Chrome 재확인
  (columns 모드 title 3종·입력란 시작 x 편차 0.00px·페이지 전체 전각 `＋` 0건·halo 파생 해소).
- Human Approval Needed: no (P1 0 · 표시 계층 · 승인 항목 §12 해당 0)

## REV-20260812T200500-ai-root-metadata-pane-refresh-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

- Trigger: doc-only (TASK/TEST/MODIFY + fragment Run 3 + 증거 1매). 코드·정책 doc 변경 0 →
  §18.8 표 첫 행(비정책 doc-only) 적용, panel skip.
- 근거 실측: 라이브 배포본(main `e250dad7`, 양 replica `mysql-ai-web:e250dad7`)에서 실 Chrome/150
  으로 전 축 재확인 — **프리뷰와 차이 0**(열 정렬 0.00px/30행 · sticky 272==border edge · 토큰
  파생 halo 정상 해소 · 상태 3단 전이 · 전각 `＋` 0). 엣지 `no upstreams available` 0건.
  Run 1·2 가 이월했던 **라이브 baked 자산 축을 종결**했다 — JS/HTML 변경 cycle 이라 이 Run 이
  없으면 완료 판정이 격리 컨테이너 근거에만 의존한다(§16.3 deploy-backed 완료 기준).
- 서버 정본 무변경(저장 미클릭 — 테이블 설명 목록 `1건` 불변).
- Human Approval Needed: no
## REV-20260813T010301-doc-sync-rn-0813 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-12 블록(9항목) prepend doc_sync 정합
- 타깃별 실질 검증(doc_sync Phase 4): `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 34/0 동일 = 회귀 0) · 구조검증(`generated`=2026-08-12 == `releases[0].date` · head 9항목 · releases 46→47 · 08-11(5)/08-07(8) 등 기존 46 블록 전량 보존 · type/area enum 위반 0 · 스키마 외 키 0) · 내부용어 누출 스캔 **0**(22 패턴).
- 블록 date 판정: 델타 창(`7b67918c`..HEAD)의 non-merge 26커밋·머지 22건이 전부 git-date 2026-08-12 이고 그 배포일 블록이 부재 → 신규 1블록 prepend. 오늘(08-13)로 적지 않은 것은 기존 블록들이 **배포일** 기준이기 때문.
- **배포 게이트 = 물리 실측**(본 run 의 핵심 판정): 라이브 이미지 web `105fa2b7` · agent/worker/ops-scheduler `e1372f32`. 9항목 근거 커밋 전건이 해당 이미지의 조상(`git merge-base --is-ancestor` YES). 서빙 static 6종이 라이브에서 브랜치 blob 과 **byte-identical**(`?v=` 정규화 후), `/healthz` 200. alembic 라이브 head `0055_tool_call_usage` = 저장소 `MAX_MIGRATION.txt` · `db_objects` **339행**.
- 적대검증(ULTRACODE `wf_bfcbc1c9`, 2 렌즈 — A 사용자향 언어/비노출 · B 사실정확성/커버리지): 양 렌즈 `ACCEPT_WITH_FIXES`, 결함 13건(blocker 1 + major 4 + minor 8). **오케스트레이터가 정본·실코드·라이브로 전건 독립 재검증** → 언어 6건 반영, 배포 게이트 3건 refute.
  - **[blocker refuted]** 렌즈 B: feature-0040 은 정본 `REPORT.md §1`("코드·단위검증 완료 / 라이브 시각검증·배포 미수행")·`§5`("배포 전제 alembic 0054 적용 필요 · SSOT 데이터 미충전")·`TEST.md` POST-DEPLOY 4항 전건 미체크 → "사용자가 볼 수 없다" 판정. **실측은 반대**: alembic 라이브 head `0055`(= `0054` 적용됨) · `db_objects` **339행 충전** · `graph/graph-roleviz.js`·`graph-core.js` 라이브 byte-identical · `ed5d4bb8` 이 web `105fa2b7`·agent `e1372f32` 양쪽 조상. 정본은 **커밋 시점 스냅샷**이고 그 후 wrapper 가 배포했다. → 항목 유지(관계도 서술 포함), 정본 lag 은 report-only.
  - **[major refuted]** 렌즈 B: conv-audit 2차 `f0147fcc` 의 TASK 마지막 체크박스 `[ ] 배포 + POST-DEPLOY 실증` 이 열림 → 삭제 제안. 실측상 `f0147fcc` 는 agent 이미지 `e1372f32` 의 조상 = **코드는 라이브 가동 중**. 미체크는 배포 부재가 아니라 POST-DEPLOY **실증 기록** 부재다. → 항목 유지하되, 라이브 실증이 없는 강한 주장('소진 시 재개해 답변을 완주')은 보수적으로 문면에서 제외(렌즈 B 교정본 채택).
  - **[major refuted]** 렌즈 B: 한/영 자판(`01ad382e`) 배포 체크박스·실측이 라이브 아님. 실측상 신규 파일 `hangul-qwerty.js` 가 라이브에서 브랜치 blob 과 byte-identical(13,618B) 이고 web·agent 양쪽 이미지 조상. → 항목 유지.
  - **[major 반영]** 렌즈 A: 배포 항목 detail 말미 2문장이 운영자향('일부만 다시 켜는 경우에도 같은 확인')이라 사용자 언어 위반 → 사용자 관점 결론으로 교체(fail-closed 동작은 08-11 블록 문형과 맞춰 보존).
  - **[major 반영]** 렌즈 A: DB 객체 항목의 '관계도에는 정리가 끝난 데이터베이스부터 차례로 나타납니다' 가 불투명('정리가 끝난' 의 지시 대상 부재) → 07-30/07-31 블록의 확립 문형('데이터베이스마다 순서대로 갱신되므로 반영 시점은 조금 다를 수 있습니다')으로 교체.
  - **[minor 반영 ×4]** ① '저장된 처리 절차' → **'함수·프로시저'**(정본 실측 17회 vs 0회) ② 메타데이터 상태 라벨 — 화면에 **'완료' 문자열 없음**(`admin/metadata.js:2613` = `"설명 입력됨"`/`"비어있음"`, 완료는 색점 상태) → 실문자열로 정정 + '옅게' 비문 해소 + '결과 전체'→'목록 전체' ③ 픽셀 수치 → '줄' 단위(정본 2,232행에 '픽셀'·'px' **0회** 실측) ④ 한/영 항목 178자 복문 → 작업 화면/관리 콘솔 2문장 분해.
  - **[판정]** area 재분류: DB 객체 항목 `common`→`work`(정본 실측 — 관계도 title 항목 **45건 전부 `admin`**, 전체 분포 work 160·admin 144·common 25 이고 common 은 배포·보안·로그인 등 서비스 전반용. 본 항목 주축은 AI 탐색 능력이라 work).
  - **[minor 미반영]** 렌즈 B 의 커버리지 원장 지적(26/27 회계, 누락 1건 = doc_sync META 커밋 `27407779`)은 그 자체가 doc_sync 산출물이라 사용자향 대상이 아니다 — 원장 완결성만 본 entry 로 보완.
- 포함/제외 판정: 사용자향 9항목. 제외는 내부 리팩터링·문서 전용(POST-DEPLOY 기록·원장 종결)·적대 리뷰 기록·측정 전용·직전 doc_sync 산출물.
- **테스트 env**: `verify_release_notes.mjs` 34/0 은 본 cycle 에서 편집 전·후 **두 번 실제 실행**한 값이다(`NODE_PATH=/tmp/node_modules`, jsdom 가동 확인).
- **cache-buster**: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime). wrapper system-prompt 의 수동 bump 지시는 07-12 이전 메커니즘 기준이라 부적용.
- **landing/배포**: 무인 cron doc_sync — 로컬 commit 까지, push/merge/deploy=wrapper(v3).
- 비-정책 doc(사용자향 릴리즈노트 데이터)만 변경 — 정책 doc 패널 불요.
- Timestamp: 2026-08-13T01:03:01+09:00
## REV-20260813T122457-attach-source-compare [SKIPPED:tool-restricted:subagent-panel] — PASS

> **채널 표기(§18.8.2 상위 우선순위 지시 carve-out)**: 이 세션에는 "요청 없이 Agent tool 을
> 호출하지 말라" 는 상위 지시가 걸려 있어 subagent panel 채널을 쓰지 않았다. 대신 제약 없는
> 채널로 검증했고 그 커버리지를 아래 「검증」에 명시한다 — 미검증을 완료로 오인 보고하지 않는다.
> ux/design 도메인의 픽셀·지각 축은 **PB-0008 실 브라우저 실측**으로 덮었다(캡처 5매 판독).

- Related TASK: feature-0003-agent-web-ui / `20260813T1224-attach-source-compare`
- Trigger: UI/modal/screen 키워드 매칭(§18.8 표 3행 → ux·design) + API/endpoint(payload 필드) 매칭
- Timestamp: 2026-08-13T12:24:57+09:00

### 설계 판단

- **왜 다른 모달을 띄우지 않았나**: 사용자 문면은 "'문서 원문' 화면에서도 버전 간 비교를 수행할 수
  있도록" 이다. 버튼을 눌러 비교 모달을 여는 것도 "비교를 할 수 있게" 는 되지만, 그러면 보던 위치와
  켜 둔 토글이 리셋되고 요청 후단("같은 버전이나 변경사항이 없으면 원문을 그대로 출력")이 성립하지
  않는다 — 그 문장은 **같은 화면 안에서 원문으로 되돌아오는** 흐름을 전제한다. 그래서 in-place 전환.
- **왜 `/versions` 를 부르지 않고 `/source` payload 를 늘렸나**: `/versions` 는 버전마다 MinIO presign
  을 만든다(다운로드 경로 전용 비용). 선택기는 "무엇을 고를지" 만 알면 되므로 presign 이 필요 없고,
  같은 게이트 안에서 체인 요약을 실으면 **왕복 1회** 라는 기존 계약(`verify_attach_source_view` A8)도
  깨지지 않는다. 노출은 `/versions` 응답의 부분집합이라 정보 표면이 넓어지지 않는다.
- **체인 조회를 fail-soft 로 둔 이유**: 원문 보기가 그 조회에 종속되면 체인 쿼리 한 번의 실패가
  "내용을 볼 수 없음" 으로 번진다. `versions: []` 는 프론트에서 곧 "선택기 없음" = 종전 동작이므로,
  실패의 영향 범위가 **추가된 기능에만** 갇힌다. (§16.7 G9-c 의 "차단 로직의 정상 경로" 와 같은 계열
  판단 — 새 의존이 기존 정상 경로를 막지 않게.)
- **방향 정규화(오래된 → 새로운)**: 기준으로 더 새 버전을 골랐다고 좌우가 뒤집히면 같은 쌍이 진입
  경로에 따라 두 방향으로 보인다. 사용자 요청 ③("가장 원본 → 가장 최신")도 시간 순 선호를 명시한다.
  대안(선택 순서를 그대로 from→to 로 쓰기)은 스왑 버튼이 있는 비교 모달에서는 뜻이 있지만, 스왑이
  없는 이 화면에서는 같은 쌍의 표현이 두 가지가 되는 비용만 남는다.
- **판정면 통합이 이 변경의 절반**: 원문 모달이 비교를 수행하게 되면서 "본문이 있는가/원문 뷰인가/
  diff 표가 있는가" 판정 사본이 **세 벌**이 될 자리였다. 이 저장소가 반복 관측한 결함 기전(같은 규칙의
  사본 중 한쪽만 고쳐짐 — 08-06 `.has-content` 단일열 의미 반전, 08-11 `code-highlight` 로컬 키워드
  복제)이라 `_bodyState` 하나로 모았고, 회귀 잠금을 **함수 정의 개수**로 걸었다(새 사본이 생기면
  개수가 어긋난다 — §16.7 G10 의 구조 가드 승격).
- **두 모달의 diff 전용 컨트롤 노출 정책이 다른 것은 의도**다: 비교 모달은 상시 노출 + 비활성(기본
  화면이 diff 라 위치를 외우고, 숨기면 `margin-left:auto` 로 바가 흔들린다), 원문 모달은 비교 상태에서만
  노출(기본 화면이 원문이라 상시 노출하면 대부분의 시간에 쓸 수 없는 컨트롤이 떠 있다). 이 비대칭을
  주석에 남겼다 — 다음 작업자가 "일관성" 을 이유로 한쪽에 맞추면 각 화면의 근거가 사라진다.
- **원문 모달에 gap 전개를 두지 않은 판단**: 전개는 `context=full` 재요청 + 쌍별 캐시 + 실패 시 버튼
  상태 복구까지 딸린 흐름이다. 여기서 맥락을 더 보려면 `동일한 줄도 모두 보기` 가 있으므로 기능 공백이
  아니고, 버튼을 만들지 않으므로 **눌러서 실패하는 경로가 없다**(거짓 어포던스 금지 원칙과 정합).

### 위험·대안

- 위험도 **Minor**(§12.3): payload 필드 추가(비파괴) + 표시 계층. 신규 엔드포인트 0 · 신규 권한 코드 0 ·
  스키마/마이그레이션 0 · 인가 경계 무변경 · `/diff` 400 계약 불변.
- `/source` 에 체인 쿼리 1회가 추가된다(같은 커넥션·인덱스 조회). `/versions` 별도 왕복 + presign N회
  보다 저렴하고, 실패는 fail-soft 다.
- 대안 A(호출부가 `versions` 를 넘기기): composer 는 이미 체인을 갖고 있으나 말풍선 칩 경로는 갖고
  있지 않다 → 진입 경로에 따라 비교 가능 여부가 갈린다. 기각.
- 대안 B(`/source?version=`): 같은 대상을 가리키는 식별 경로가 둘이 되고 그중 하나만 스코프 검사를
  통과하는 비대칭이 생긴다(선행 cycle 이 명시적으로 금지). 기각 — 유지.

### 검증

- 신규 하네스 `tests/verify_attach_source_compare.mjs` **72 checks green** — 6축(선택기 / 비교 전환 ·
  방향 정규화 / 원문 수렴 2경로 / 컨트롤 상태 · 실패 경로 / 비교 모달 같은-버전 / 계약). **URL 별 응답
  stub** 을 쓴 이유: 한 모달이 `/source` 와 `/diff` 를 모두 부르므로 단일 응답 stub 으로는 "어느 요청에
  어떤 답이 갔는지" 를 구분할 수 없고, 방향 정규화·재요청 0 축이 vacuous 하게 통과한다.
- 기존 첨부 하네스 6종 **559 checks green**. 리팩터로 계약이 옮겨간 소스-grep 축 3건은 **취지를 보존해
  갱신**: C5(토글 노출이 identical 을 배제하지 않음) → `_bodyState.hasBody` 정의에 `identical` 이
  없음을 단정 · D6(판정면 동일) → 두 sync 가 같은 `_bodyState` 를 호출하고 그 정의가 **1개**임을 단정 ·
  B5(머리 진입점 기본 쌍) → 최초→최신 preselect + min 계산 방어를 단정(B5b 신설).
- pytest 신규 5축(C1 체인 적재 · C2 서명URL/ObjectKey 부재 · C3 fail-soft · C4 바이너리 강등에도 체인 ·
  C5 `_version_side` 단일 정본) + 첨부 2파일 **71 passed**.
- 전체 스위트 실패 1건(`test_oauth_exhaustion_gate` — `chattr` 바이너리 부재)은 **pristine main 에서
  동일 재현**(같은 이미지·같은 명령으로 실측) → 환경 의존 선재 red, 본 cycle 귀책 아님.
- **§18.8 채널 선택**: 세션에 "요청 없이 Agent tool 호출 금지" 상위 지시가 걸려 있어 §18.8.2 의
  「상위 우선순위 지시 carve-out」을 적용했다 — subagent panel 대신 제약 없는 채널(기계적 계약 점검 +
  신규/기존 하네스 실행 + pristine 대조)로 검증하고, 그 커버리지를 위 항목에 명시했다. ux/design 도메인의
  **픽셀·지각 축은 PB-0008 실 브라우저로 대체**(아래 잔여).

### 시각검증 (완료)

- **PB-0008 실 Chrome/150 PASS** — `visual_verification_scope: always`(FIRST_REQUEST.md) hard gate 충족.
  컨트롤 바에 항목이 3개 늘어(비교 select + 보기 방식 + 맥락) 정렬·줄바꿈이 **픽셀-클래스 변경**이므로
  (§16.6 기본 추정) 캡처 판독으로 확인했다 — 선택기 215×26px @x=33, 통계·토글 우측 그룹 정렬, 겹침·
  잘림 0, 원문 상태에서 diff 전용 컨트롤 rect 0×0(숨김이 CSS 층에서 실제로 먹는다).
- **세션 격리 실사례**: 검증 도중 공유 CDP 의 `pages[0]` 이 병렬 세션 탭(`/admin`)으로 바뀐 것을 관측
  (§16.6 v3.44.0 이 경고한 그 상황). 남의 탭을 되돌리지 않고 `context.new_page()` 로 자기 생성 탭을
  만들어 그 탭에서만 조작·캡처했으며 종료 시 그 탭만 닫았다. 캡처의 신원은 서빙 모듈 문자열
  (`_bodyState`·`_renderSourceBody`·`attach-source-cmp`)로 대조했다.

### 잔여

- 배포 후 baked 자산에서 **POST-DEPLOY 재실측**(fragment Run 2) — 이번 Run 1 은 격리 프리뷰 컨테이너.
- `identical`(내용 동일) 화면의 **라이브 조합**은 이 체인에 해시 동일 쌍이 없어 하네스에서만 검증했다
  (라이브에서는 같은-버전 경로로 같은 렌더 코드를 실측). 정직 표기.
- Human Approval Needed: no (Minor · 인가/데이터 무변경)
## REV-20260813T113500-ai-claude-corp-usage-metric-charts [CODEX:usage-metric-charts] — CONCERN (P1 2 · P2 5 → 6건 반영 · 1건 부분 refute)

**Trigger**: UI/screen/layout + schema/migration + caching keyword matched (§18.8) → 코드 변경.
채널은 §18.8.1 의 codex-review(check #9 accepted). 판정 기준은 `docs/CODE_REVIEW.md`.

### 판정 요지

codex 초기 판정 **BLOCK**(P1 2 · P2 5). 전건을 **실측으로 독립 재검증**한 뒤 6건 반영, 1건은
근거를 들어 부분 refute 하고 대신 관측 정직성을 고쳤다. 아래 각 항목의 "확인" 은 내가 직접
resolve 한 결과다(리뷰어 주장 그대로 수용하지 않음).

### P1-1 — 모든 SQL 예외를 캐시 컬럼 누락으로 오인 (부분 refute + 수정)

- **주장**: `_usage_cache_exec` 의 광범위 except 가 문법·alias 오류까지 삼켜 캐시 0 으로 위장 성공.
- **확인**: 두 판의 차이는 캐시 표현식뿐이라, 원인이 캐시 컬럼이 아니면 **리터럴 0 판도 같은 예외로
  실패해 그대로 전파**된다 — "무음 0 성공" 은 성립하지 않는다(코드 경로 재확인).
- **다만 타당한 부분**: 첫 실패 시점에 "컬럼 부재" 로 **단정하는 로그**는 근거 없이 원인을 못박는다.
- **반영**: 로그를 **재실행 성공 후로 옮기고** 문면을 "캐시 컬럼 없이 재조회 성공 — 0056 미적용으로
  판단" 으로 바꿔, 판정의 근거가 관측(재실행 성공)에 붙게 했다. 리터럴 0 판도 실패하면 예외는
  삼키지 않고 전파(주석에 명시).

### P1-2 — 모델 부분 선택 시 요청 수 카드와 차트가 다른 모집단 (수용)

- **확인**: 사실. `totals.requests` 는 `by_model.requests` 합으로 재계산되는데 `by_day.requests` 는
  모델로 나눌 수 없어 전체 기준이 남는다. A+B 를 쓴 run 과 B 만 쓴 run 이 있을 때 A 선택 시 카드 1 /
  차트 2 가 되어 **같은 화면의 두 수가 어긋난다**.
- **반영**: 그 조합을 애초에 막는다 — 모델 부분 선택 상태에서 비-가산 지표(요청)는 카드 **비활성 +
  "—"**, 이미 선택돼 있었다면 기본 지표로 강등. 상세 표가 부분 선택 시 요청/호출을 "—" 로 두는
  기존 규칙과 같은 취급이라 화면 안에서 일관된다. 헤드리스 하네스에 회귀 잠금 2건 추가.

### P2-1 — 요청 지표에서 역할·계정 막대가 0 폭 (수용)

- **확인**: 사실. `models[]` 에는 `requests` 가 없어 모든 세그먼트가 0% → 막대가 사라진 것처럼 보인다.
- **반영**: 비-가산 지표는 가로 막대도 모델 분해 없이 **엔티티 값 단일 세그먼트**로 그린다(색은 모델
  색이 아닌 기본 색 — 모델을 뜻하지 않으므로). signature 에 분해모드를 넣어 모드 전환 시 재생성.

### P2-2 — 혼합 형태 응답에서 캐시 한 축 누락 (수용)

- **확인**: 사실. `if read or write: return` 이라 최상위에 read 만 있으면 details 의 write 를 못 본다.
- **반영**: 두 축을 **독립 폴백**(각각 `or`)으로 변경. 회귀 테스트 3건이 세 형태를 고정한다.

### P2-3 — chokepoint 우회 직접 호출 (수용, 주장 자체가 부정확했음)

- **확인**: 사실이며 **내 FUNCTION/docstring 서술이 틀렸다**. "두 chokepoint 가 전부" 라고 썼지만
  `modules/llm.py` 에만 직접 `client.chat.completions.create` 가 **16곳** 있다.
- **실측으로 범위 확정**: 그 16곳의 system 프롬프트 길이를 전부 재보니 캐시 임계(4,000자)를 넘는 것은
  `NODE_ANALYSIS_PROMPT`(9,124자) **하나뿐**이고 나머지는 2,170자 이하(ORIGIN_SHIFT 2170 ·
  ENUM_SUGGEST 1373 · 그 외 1.2k 이하)라 부착해도 캐시가 생성되지 않는 no-op 이다.
- **반영**: `llm_node_analysis` 에 명시 적용(노드마다 9k자 재전송 — 캐시 이득이 가장 큰 경로) +
  docstring 을 "세 적용 지점 + 나머지는 임계 미달로 no-op(실측 수치 병기)" 로 정정. §16.7 G7(a):
  "전부 통과한다" 는 이름·설계 의도였고 실제는 세어 봐야 알 수 있었다.

### P2-4 — 부트스트랩 스키마 미반영 (수용)

- **확인**: 사실. `src/scripts/agent_runtime_schema.sql` 은 alembic 을 경유하지 않는 초기화 경로의
  정본인데 캐시 2컬럼이 없었다. 신규 DB 는 컬럼 없이 떠 계측이 조용히 0 으로 굳는다.
- **반영**: 두 컬럼을 같은 정의(NOT NULL DEFAULT 0)로 추가 + 주석에 "prompt_tokens 에 포함된 내역"
  관계 명시.

### 자율 판단 기록 (§9.1)

- **캐시 단가 계수** — Anthropic 5분 ephemeral 공시 배수(write 1.25x · read 0.1x)를 상수로 둔다.
  단가표 자체가 이미 "추정" 이라 같은 등급의 근사다.
- **캐시 임계 4,000자** — 모델별 최소 캐시 길이가 다르고(Haiku 2048 / Sonnet·Opus 1024 토큰) 한글
  혼재라 토큰 환산이 불확실해, 보수적 문자수로 짧은 helper 호출을 걸러낸다. 미달 시 부착해도
  에러가 아니라 무효라 fail-safe 방향이다.
- **캐시는 입력의 부분집합** — 게이트웨이 실측(`5039 = 37 + 5002`)으로 확인. 화면에서 합산 오해가
  생기지 않도록 캐시 지표 선택 시 1줄 안내(60자 예산 이내).

### 잔여 리스크

- 캐싱 활성화는 **요청 페이로드 형태 변경**이다. 단위·헤드리스로는 "부착 규칙" 까지만 검증되고,
  실제 대화가 캐시를 적중시키는지는 배포 후 라이브 실측으로만 확인된다 → POST-DEPLOY 이월(TEST.md).
- 캐시 지표는 **소급되지 않는다**. 배포 직후 화면에서 0 으로 보이는 것은 정상이며, 신규 호출이
  쌓이면서 채워진다.

## REV-20260813T152000-ai-claude-corp-usage-metric-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

선행 cycle 의 라이브 검증 결과를 TEST.md/TASK.md 에 기록하는 doc-only 변경(코드·정책 doc 무변경) —
§18.8 표 첫 행에 따라 panel skip. 기록된 실측 자체는 라이브 DB·실 브라우저 관측이 근거다.

## REV-20260813T131000-attach-source-compare-postdeploy [SKIPPED:non-policy-doc] — PASS

- Related TASK: feature-0003-agent-web-ui / `20260813T1310-attach-source-compare-postdeploy`
- Reason: changed paths are docs only — 코드·스키마·권한 변경 0(POST-DEPLOY 실측 기록)
- Timestamp: 2026-08-13T13:10:00+09:00

- **판정 근거**: "배포됐다" 를 종료코드가 아니라 **서빙 주체의 실제 SHA + 서빙 자산 문자열**로
  확인했다(web-a·web-b `mysql-ai-web:c5a27e0d`, 라이브 `attach-diff.js`/`composer.js` 에 신규
  심볼 존재). 무중단도 스크립트의 "성공 보고" 가 아니라 엣지 로그 `no upstreams available` **0건**
  으로 실측했다(§16.3 deploy-backed 완료 기준 · feature-0014 RUNBOOK §10 [5]).
- **캡처 byte-identical 의 의미**: POST-DEPLOY 캡처가 Run 1(격리 프리뷰) 캡처와 바이트 동일해
  `git status` 가 dirty 0 이었다. 이는 ① 프리뷰↔라이브 렌더가 픽셀 단위로 같다는 직접 증거이고
  ② 증거 파일을 갱신할 필요가 없어 main worktree mutation 이 0 이라는 뜻이다(§13.2.7 F0 준수).
  캡처를 덮어쓴 뒤 dirty 를 확인하는 순서였기에 위반 여부를 사후가 아니라 그 자리에서 판정할 수 있었다.
- Human Approval Needed: no
## REV-20260813T155000-ai-claude-corp-rail-async-relayout [CODEX:rail-async-relayout] — CONCERN (P1 2 · P2 2 → 4건 전건 반영, 그중 1건은 반영 초판이 라이브 회귀를 유발해 재설계)

- Related TASK: feature-0003-agent-web-ui (20260813T1550-rail-async-relayout)
- Source: codex review (`codex review --uncommitted`)
- Trigger: UI/layout/scroll keyword matched (UI·화면·레이아웃·스크롤) — code change.
  §18.8 dispatch 표는 ux·design subagent 를 요구하지만, 본 세션에는 **상위 우선순위 도구 제약**
  ("Do not call the AgentTool unless the user requested it")이 걸려 있다. AGENTS.md §18.8.2
  「상위 우선순위 지시 carve-out」에 따라 subagent panel 을 호출하지 않고, 제약 없는 채널
  (codex review + 신규 실브라우저 하네스 + PB-0008 라이브 대조)로 검증했다. 미검증 도메인은
  아래 [SKIPPED:tool-restricted:ux,design] 로 명시한다.
- Timestamp: 2026-08-13T15:50:00+09:00
- Verdict: CONCERN (P1 2건이 실제 결함이었고 전건 수정 — 수정 후 재검증 PASS)
- Artifact: `docs/test-runs.d/20260813T155000-rail-async-relayout.md` (Run 1 하네스 26/26 ·
  Run 2 PB-0008 라이브 대조) + `docs/evidence/pb0008-rail-async-relayout-*.png`
- Critical issue (반영 내역):
  - **[P1] live-sync 위치 보존 경로의 pin 미해제** — `_liveSyncTick` 이 사용자가 하단에서 80px
    이상 떨어져 있을 때 `renderMessages()` 후 `prevTop` 을 복원하는데, 그 렌더가 engage 한 pin 이
    살아 있어 뒤이은 성장이 사용자를 하단으로 끌어내린다. → 그 분기에서 `_releaseRailBottomPin()`.
    내가 찾은 release 배선 4곳에 이 경로가 빠져 있었다(적용면 누락 — 지적이 정확했다).
  - **[P1] pending 말풍선 성장 미관찰** — `#pendingAssistantBubble` 은 `data-message-id` 가 없어
    관찰 대상에서 빠지는데 그 높이가 `scrollHeight` 에 들어가므로 progress step 이 쌓이면 확정
    메시지 막대가 stale 해진다. 게다가 progress.js 는 그 row 를 **`replaceChild` 로 교체**하므로
    한 번 observe 해도 연결이 끊긴다. → pending row 를 대상에 포함 + **`MutationObserver`
    (childList) 로 교체·추가를 따라잡아 클래스 전체를 잠갔다**(§16.7 G10 — 호출부마다 재관찰을
    심는 점수정 대신 구조로).
  - **[P2] 네이티브 스크롤바 조작 시 pin 미해제** — 스크롤바 클릭·드래그는 wheel/touch/key 를
    발생시키지 않는다. → **컨테이너 `pointerdown`** 으로 해제.
    ⚠ **반영 초판이 라이브 회귀를 만들었다**: "pin 이 설정한 `scrollTop` 과 불일치 = 사용자 조작"
    휴리스틱으로 구현했더니, **뷰포트 위쪽** 성장 시 브라우저 스크롤 앵커링의 자동 조정이 그
    불일치를 만들어 pin 이 조기 해제됐다 — 라이브 재측정에서 `A_entry gap=1,611px`(수정 전과 같은
    증상). 헤드리스 26축은 성장이 아래쪽에서만 일어나 전건 통과 상태였다(§16.7 **G4** — 진짜
    경계축은 "성장이 뷰포트 위인가 아래인가"였다). scroll 값 비교는 *브라우저 자동 조정*과
    *사용자 조작*을 구분할 수 없다는 것이 결론이고, `pointerdown`(의미론적 "사용자가 눌렀다")으로
    교체 후 `gap=0` 복귀. 하네스에 **T11**(위쪽 성장 시 pin 유지)·**W5b**(폐기 휴리스틱 재발 방지)
    를 추가했다.
  - **[P2] 폴백 환경의 settle 창 부족** — ResizeObserver 부재 시 성장 신호가 `[300,1000,2500]ms`
    타이머로만 오는데 settle 600ms 는 첫 폴백 직후 만료돼 이후 성장에서 스크롤이 새 하단에 못
    붙는다. → 폴백 모드에서 settle 을 `마지막 폴백 + 400ms` 로 연장(ceiling 8s 상한 유지) +
    관계 불변식을 **W8** 로 잠금.
- 자기 판단 기록(반영하지 않은 것 없음): 4건 모두 실제 시나리오로 판단해 전건 반영했다. P2 2건은
  "우선순위 낮음" 이 아니라 **사용자 조작과 자동 스크롤이 싸우는 축**이라 pin 설계의 정합성 자체에
  관계된다고 보았다.
- Human Approval Needed: no

## REV-20260813T155000-rail-async-relayout-panel [SKIPPED:tool-restricted:ux,design] — 미검증 범위 명시

- Related TASK: feature-0003-agent-web-ui (20260813T1550-rail-async-relayout)
- Reason: §18.8 dispatch 표가 UI/layout 키워드에 대해 ux·design subagent 를 요구하나, 본 세션의
  상위 우선순위 도구 제약(AgentTool 금지)으로 panel 을 호출하지 않았다(§18.8.2 carve-out).
  대체 채널로 codex review(위 entry) + 신규 실브라우저 하네스 26축 + PB-0008 라이브 전/후 대조를
  수행했다. **미검증으로 남은 것**: ux·design 관점의 정성 평가(뱃지 시각 언어·상호작용 관례).
  본 변경은 렌더 기하를 바꾸지 않고 **좌표 정합만 복원**하므로(막대 색·폭·형태·클릭 규약 무변경)
  그 도메인의 blast radius 는 낮다고 판단하되, 판단은 판단이고 미검증은 미검증으로 표기한다.
- Timestamp: 2026-08-13T15:50:00+09:00
## REV-20260813T154300-ai-claude-corp-attach-list-name-sort [CODEX:attach-list-name-sort] — PASS

- Related TASK: feature-0003-agent-web-ui / `20260813T1543-attach-list-name-sort`
- Risk: **Minor** (§12.3) — 표시 순서 전용. 권한·스키마·마이그레이션·신규 엔드포인트 0.
- Timestamp: 2026-08-13T15:43:00+09:00

- **정렬을 SQL 이 아니라 파이썬에 둔 이유**: 목록 read 경로가 둘이다(MySQL 정본, PG mirror —
  `read_pg_enabled()` 시 PG 우선). `ORDER BY OriginalFilename` 을 양쪽에 걸면 두 엔진의 collation
  차이가 곧 "경로에 따라 순서가 다름" 이 된다. 게다가 `_02_` < `_10_` 같은 수치 비교는 SQL 로는
  자연스럽게 표현되지 않는다. 두 경로가 합류한 뒤 한 함수로 정렬하면 순서 규칙이 한 곳에만 산다.
- **휴지통에서 정렬과 절단을 분리한 판단**: `LIMIT 200` 은 "무엇을 보여줄지" 의 경계이고, 그 기준을
  이름순으로 바꾸면 이름이 앞선 오래된 삭제분이 200칸을 채워 **방금 지운 파일이 휴지통에서 사라진다**
  (복구 실패 = 데이터 손실 체감). SQL 은 최근 삭제 순으로 두고 표시만 이름순으로 재배열했다.
- **일괄 다운로드에서 체인을 쪼개지 않은 이유**: `scope=all` 은 버전 체인 전량을 담는다. 행별 이름으로
  정렬하면 AI 편집으로 개명된 버전(`report.csv` → `report_v2.csv`)이 제 체인에서 떨어져 ZIP 안에서
  흩어진다. 그룹 대표는 **목록 패널에 보이는 이름**(체인의 최신 이름)으로 잡아 화면과 파일 순서를 맞췄다.
- **프론트에 정렬을 넣지 않았다**: 같은 규칙을 두 벌 두면 한쪽만 갱신되는 것이 이 모듈이 반복 기록한
  결함 기전이다(08-06 `.has-content` 의미 반전, 08-11 `code-highlight` 키워드 복제). 서버 응답 순서를
  SSOT 로 두면 컴포저 첨부 칩·전체 다운로드 매니페스트가 자동으로 따라온다.
- **범위를 넓히지 않은 곳**: `/versions`(버전 순서는 이름과 무관)와 **LLM 컨텍스트 첨부 주입 순서**.
  후자는 화면 목록이 아니라 답변 품질에 영향을 주는 축이라, "정렬" 요청을 이유로 건드리지 않았다.
- **검증의 판별력**: 첫 PB-0008 시도의 대상 대화가 `probe_a~d.sql` 이라 **이미 알파벳순**이었다 —
  통과해도 아무것도 증명하지 못한다. 검색으로 39첨부 대화(`08051122_`·`v2_`·`v2_1_`·`v3_` 접두 혼재)를
  열어 다시 쟀고, **수정 전 코드를 마운트한 baseline 컨테이너(:18098)** 와 같은 대화·같은 브라우저로
  A/B 하여 순서가 코드 차이에서 온다는 것을 직접 보였다. `v2_1_…` 이 `v2_D_…` 앞에 서는 것이
  자연 정렬(숫자 조각 우선)의 실측 증거다.
- **라이브 데이터 변경 0**: 열람 경로만 사용. 대상 대화는 타 계정(kumin) 소유를 read.any 로 **읽기만** 했다.
- **§18.8**: subagent panel 대신 하네스(pytest 12축) + 실 브라우저 A/B 실측 채널로 수행(§18.8.2 carve-out).
  표시 순서 전용 변경이라 보안·권한 표면이 없다.
- Human Approval Needed: no

### codex 적대 리뷰 (2 라운드) — 반영 내역

- **채널**: `codex exec --sandbox read-only`(subagent panel 이 아닌 §18.8.1 경량 경로 —
  본 세션은 상위 지시로 Agent tool 사용이 제한되어 §18.8.2 carve-out 순서상 1번 채널을 썼다).
- **1라운드에서 실제 결함 3건을 끌어냈고 전건 반영**:
  - (P2) **컴포저 pill 목록은 여전히 삽입 순서** — 같은 패널 `#attachSidePanelList` 에 렌더러가
    둘이라는 것을 놓쳤다. 서버 목록만 정렬하면 업로드 직후 `z.txt → a.txt` 로 보이다가 패널을
    다시 열면 순서가 바뀐다. → `_renderAttachmentPills` 의 두 목록 모두 `byName` 정렬 +
    신규 하네스가 **정렬 호출 개수(2)** 로 잠금(렌더러가 2개면 개수로 세라 — 이 모듈의 기존 교훈).
  - (P2) **PG 경로 키 표기 가정** — 현재 alias 는 정확하지만, 어느 read 경로가 snake_case 로
    바뀌면 정렬이 *조용히* 무의미해진다(전 행 빈 이름 → 원래 순서). → 두 표기 fallback + 테스트 S3.
  - (P3) **초장문 숫자열** — 파이썬의 4,300자리 int↔str 제한으로 `ValueError` → 목록 전체 500.
    파일명 255자 제한이라 정상 경로엔 닿지 않지만 legacy/malformed 행 하나로 표면 전체가 죽는
    비용이 방어 1줄보다 크다. → `float("inf")` 강등(0 으로 강등하면 `a1.txt` 보다 앞서는 거짓 순서).
- **2라운드(수정 후 재리뷰)**: **P1 없음(P1_COUNT=0)**.
- **수용(미수정) 기록**:
  - 대형 첨부 목록의 정렬 비용 — 기존에도 전량 fetch 하던 경로에 `O(N log N)` 이 더해질 뿐이라
    별도 상한을 두지 않았다. 페이징이 필요해지는 시점은 정렬이 아니라 fetch 가 먼저 문제다.
  - ZIP 중복 이름의 구분 번호가 어느 첨부에 붙는지가 새 정렬 순서를 따라 바뀔 수 있다 —
    manifest 와 ZIP 이 **같은 배열**을 쓰므로 한 요청 안에서 어긋나지 않는다.
  - 검색 결과의 첨부 chip(`created_at DESC`)은 관련성/최신순 표면이라 범위 밖으로 두었다.

## REV-20260813T170000-attach-name-sort-postdeploy [SKIPPED:non-policy-doc] — PASS

- Related TASK: feature-0003-agent-web-ui / `20260813T1700-attach-name-sort-postdeploy`
- Reason: changed paths are docs only — 코드·스키마·권한 변경 0(POST-DEPLOY 실측 기록)
- Timestamp: 2026-08-13T17:00:00+09:00

- **판정 근거**: "배포됐다" 를 스크립트 종료코드가 아니라 **서빙 주체의 실제 SHA**(web-a·web-b
  `mysql-ai-web:7afed974`)와 **엣지 로그**(`no upstreams available` 0건)로 확인했다.
- **검증의 종착점을 요청 화면에 맞췄다**: 임의의 첨부 대화가 아니라 **사용자가 스크린샷으로 보여준
  그 파일 세트**(`20260709_[MV] Log_v2 이슈 대응_*.sql`)를 라이브에서 열어 `01 → 02 → 03 → 04 →
  08 → 09` 를 확인했다. 요청의 이행은 테스트 통과가 아니라 그 화면에서 증명된다.
- Human Approval Needed: no

## REV-20260813T174100-rail-relayout-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

- Related TASK: feature-0003-agent-web-ui (20260813T1741-rail-async-relayout-postdeploy)
- Reason: changed paths are docs/evidence only outside policy-doc list (코드 변경 0 — 라이브 실측 기록)
- Timestamp: 2026-08-13T17:41:00+09:00
## REV-20260813T160000-ai-claude-feature-0003-graph-expand-perf [CODEX:graph-expand-perf] — PASS

- Related TASK: feature-0003-agent-web-ui / `20260813T1600-graph-expand-perf`
- Source: codex review (codex-cli 0.146.0, uncommitted diff · 2 라운드)
- Trigger: performance/latency/caching keyword matched (성능·지연·캐싱) — §18.8 dispatch
- Timestamp: 2026-08-13T16:00:00+09:00
- Verdict: PASS (반영 후 P1 0건)
- Human Approval Needed: no

**검증 채널 선택 근거 (§18.8.2 상위 우선순위 지시 carve-out)**: 본 세션에는 하네스 수준의
"요청 없이 Agent tool 을 호출하지 말라" 제약이 걸려 있어 subagent panel 을 쓰지 않았다. §18.8.2 가
정한 순서대로 **제약 없는 채널**(codex review — §18.8.1 경로 2, check #9 accepted)로 수행했고,
판정 기준 정본은 `docs/CODE_REVIEW.md` 를 읽도록 지시해 도구 기본 판정으로 흐르지 않게 했다.
subagent 도메인(backend/qa) 미커버 범위는 아래 "채널 한계" 에 명시한다.

**라운드 1 — P1(GATE) 1건 / P2 2건**

- **P1 — 선-fetch 응답의 세대 오염**: `_metaColPrefetch` 가 모델 리셋에서 비워지지 않아, 리셋 전에
  뜬 응답이 TTL 안의 재클릭으로 소비될 수 있었다. → `_metaGraphResetModel` 에서 `_metaColPrefetchClear()`.
  (판정: 키에 scope 가 포함돼 교차-스코프 오염은 불가하고 같은 URL 의 재응답이라 실 피해는 작지만,
  "리셋이 캐시를 남긴다" 는 **클래스 자체**가 구조적 결함이라 수용.)
- **P2 — 중복 GET**: 상세 조회가 이미 `graph?node=&depth=1` 을 쏜다. → 선-fetch promise 를 상세와
  **공유**해 클릭당 왕복을 1건 줄였다(이 중복은 본 변경 이전부터 존재 — 개선 방향으로 흡수).
- **P2 — 부분 펼침 테이블에서 선-fetch 미소비**: 가드를 호출측(340ms 타이머의 `!_metaTableHasCols`)과
  **동일 조건**으로 좁혀 낭비 요청 자체를 만들지 않게 했다.

**라운드 2 — 후속 지적 반영**

- **P2 — 얕은 복사로 aliasing 미차단**: `slice()` 는 배열만 복사하고 노드 객체는 공유돼 `ordinal`
  보완이 원본을 제자리 변형했다. → dedupe 시 **per-node 얕은 복사**(`{ ...x }`). 회귀 테스트 T8.
- **P2 — 검색 prune 경로 캐시 미삭제**: `_metaSearchPrunePristine` 도 모델 변형 경로 → 동일하게
  `_metaColPrefetchClear()`. 회귀 테스트 T9. TTL 도 20s → **8s**(재사용 창 최소화).
- **미수용(선재 결함으로 분류, 본 cycle 범위 밖)**: ① `_metaGraphShowDetail` 이 fetch 후 세대 가드
  없이 렌더하는 것 — `main` 에서도 동일하며 본 변경이 만든 경로가 아니다(공유 promise 는 같은 URL·
  같은 시점 응답). ② 상세 backfill 의 `/columns` 와 펼침의 `/columns` 중복 — 역시 선재.
  둘 다 REPORT.md §후속 에 등재.

**채널 한계 (정직 표기)**: codex 는 diff 정적 분석이며, ①DOM 이 필요한 상세 backfill 경합 ②실
브라우저 렌더 정합은 커버하지 못한다. 그 두 축은 각각 헤드리스 계약 테스트(15건)와 PB-0008 실
Windows 브라우저 시각·인터랙션 검증(TEST fragment)으로 메웠다. backend/qa subagent 관점 중
**서버 부하 축**(클릭당 동시 GET 2건 발생)은 위 "선재 중복 흡수" 로 순증 0 임을 코드로 확인했으나
부하 실측은 하지 않았다 — `[SKIPPED:tool-restricted:backend-load-measurement]`.

## REV-20260813T170000-ai-claude-feature-0003-graph-expand-perf-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / `20260813T1700-graph-expand-perf-postdeploy`
- Reason: changed paths are docs only — 코드·스키마·권한 변경 0(POST-DEPLOY 실측 기록)
- Timestamp: 2026-08-13T17:00:00+09:00

- **판정 근거**: "배포됐다" 를 스크립트 종료코드가 아니라 **서빙 주체의 실제 SHA + 서빙 자산의 신규
  심볼**로 확인했고(web-a·web-b `mysql-ai-web:16da577f`, `nodeShapeSig`/`_metaGraphPrefetchColumns`/
  `_metaColPrefetchClear` 각 2건), 무중단도 엣지 로그 `no upstreams available` **0건**으로 실측했다
  (§16.3 deploy-backed 완료 기준 · feature-0014 RUNBOOK §10 [5]).
- **격리 프리뷰의 예측력 확인**: 배포 전 격리 컨테이너에서 얻은 수치(556/133/35/21/19)와 라이브
  수치(544/134/32.8/21/19)가 사실상 일치했다 — 프리뷰 측정을 라이브 대용으로 쓴 판단이 사후적으로
  검증됐다. 다만 **프리뷰 PASS 를 완료 근거로 삼지는 않았고**, 라이브 재측정을 별도로 수행했다.
- Human Approval Needed: no

## REV-20260813T181200-ai-claude-feature-0024-folder-dnd-shared [SKIPPED:frontend-display-gate-widen-existing-gated-api] SHIP — 공유받은 그룹 대화 폴더 DnD 개방

- Related TASK: feature-0003-agent-web-ui / `20260813T1812-folder-dnd-shared-group`
- Timestamp: 2026-08-13T18:12:00+09:00
- Human Approval Needed: no (Minor §12.3 — 프론트 표시 계층, 백엔드 enforcement·스키마·권한 불변)

**Panel skip 사유(§18.8)**: 신규 엔드포인트·권한·RBAC 게이트·백엔드 로직 0. 변경은 이미 §18.8 리뷰된
폴더 API(REV-20260723T170000 에서 엄격 owner-scope 확정)를 호출하는 **프론트 draggable 부여 조건**
단독이며, 같은 조작이 '···' 메뉴 '이동'(openMoveConversationDialog) 으로 **이미 가능했다** — 즉 새
공격면이 아니라 기존 허용 동작에 두 번째 입력 수단을 붙인 것. 동일 부류 선례:
REV-20260723T190000-folder-ux(DnD 도입), REV-20260723T200000-newfolder-btn. 본 세션은 subagent 호출이
사용자 제약으로 금지돼 있어 아래 적대 점검을 직접 수행하고 근거를 코드로 남긴다.

**직접 적대 점검 (프라이버시 축 — 폴더는 과거 크로스-계정 노출 사고 이력 있음, REV-20260723T170000)**

- **타 계정 뷰 오염?** 없음. 배정은 `assign_conversation(_acct_id(account), cid, folder_id)` →
  `folder_conversation_map` PK `(account_id, conversation_id)` 의 요청자 row upsert/delete 뿐이고,
  목록 보강은 `folder_map_for_account(요청자)` 라 소유자·타 멤버 payload 의 `folder_id` 는 불변.
  폴더 트리 자체도 `GET /api/folders` 가 항상 owner-scope(`.any` 폐지). → 멤버가 자기 폴더에 배치해도
  타 계정 화면에 폴더 이름·구조·배정이 나타나지 않는다.
- **접근 권한 없는 대화를 끌 수 있나?** 없음. 드래그 대상은 서버가 준 목록(접근 가능분)에서만 만들어지고,
  `is_member` 는 서버 계산 필드다. 프론트를 우회해 임의 cid 를 PATCH 해도 라우트가
  `_account_can_access_conversation(conversation.read.own, conversation.read.any)` 로 차단(404).
  대상 폴더도 `_require_folder_owner` 로 요청자 소유만.
- **권한 게이트 회귀?** `can("folder.manage.own")` 는 그대로 AND 조건 — 미보유 계정은 draggable 미부여
  (테스트 case4). 프론트는 display-permissive 컨벤션이고 실제 거부는 백엔드 403/404 가 담당.
- **관리자 `.any` 열람 대화(타 계정 대화 그룹)**: 의도적으로 제외했다. 폴더는 개인 오버레이이며 그
  그룹은 폴더 파티션 대상이 아니라, 배정이 성공해도 폴더 하위에 렌더되지 않아 **무음 실패**가 된다.
  드래그는 막고, 기존 '···' 메뉴 경로의 같은 무음 실패는 선재 결함으로 REPORT §후속 에 등재(§8.1 —
  기록만). 이번 변경이 그 표면을 넓히지 않는다.

**설계 판단 — 점수정 대신 predicate 단일화**: draggable 조건만 `mine → mine || is_member` 로 고치면
파티션(L594)과 게이트(L807)가 여전히 별개 표현으로 남아 한쪽만 바뀌는 재발이 가능하다. 두 지점을
`isFolderScopedConversation` 하나로 묶고 그 사실을 소스 정규식 4건으로 잠갔다(§16.7 G10). `mine` 은
소유 표시·멀티선택·삭제 인덱스에서 여전히 다른 의미이므로 남겼다(과잉 통합 회피).

**검증 채널·한계 (정직 표기)**: jsdom 은 실제 마우스 드래그와 DataTransfer 를 구현하지 않아
`draggable` 속성 + `dragstart` 핸들러의 `state.dqaDrag` 배선까지만 판정한다(정본 코드가
`dataTransfer` 접근을 try 로 감싸는 이유). **드롭 → 배정 → 재렌더 round-trip 은 배포 후 PB-0008 실
Windows 브라우저가 정본**(visual_verification_scope: always). 테스트가 실제 결함을 잡는지는 코드만
되돌려 대상 11건 FAIL·회귀 축 PASS 로 실증했다. 서버 라운드트립·크로스-계정 격리의 **라이브** 실측
(계정 A 가 공유 그룹 대화를 자기 폴더로 이동 → 계정 B 화면 불변)도 POST-DEPLOY 항목이다.
## REV-20260813T184000-ai-claude-feature-0003-folder-dnd-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / `20260813T1840-folder-dnd-postdeploy`
- Reason: changed paths are docs only — 코드·스키마·권한 변경 0 (POST-DEPLOY 실측 기록 + 증적 캡처)
- Timestamp: 2026-08-13T18:40:00+09:00
- Human Approval Needed: no

- **판정 근거**: "배포됐다" 를 스크립트 종료코드가 아니라 **서빙 주체의 실제 SHA + 서빙 자산의 신규
  심볼**(web-a·web-b `mysql-ai-web:763ad65d`, `isFolderScopedConversation` 4매치)로 확인했고, 무중단도
  엣지 로그 `no upstreams available` **0건**으로 실측했다.
- **요청 시나리오를 우회하지 않았다**: admin 계정에는 `is_member` 대화가 0건이어서(148건은 관리자
  `.any` 열람) 그 계정만으로는 대상 케이스를 관측할 수 없었다. DB 에 멤버 row 를 직접 넣는 우회 대신
  **제품 경로**(공유 링크 생성 → 테스트 계정 가입·역할 부여 → join)로 실제 "다른 계정으로부터의 그룹
  대화" 를 만들어 검증했다 — 실사용자 대화·계정을 건드리지 않았고 사후 전량 정리했다.
- **격리는 대조군으로 확인**: 배정 후 admin 재로그인 시 folder 목록이 비어 있고 같은 대화의 folder_id
  가 null 이었다 — "이동이 됐다" 와 "타 계정에 새지 않는다" 를 각각 실측(§16.7 G4 경계 양측).
- **한계 명시**: OS 레벨 native drag 는 재현하지 않았다(CDP `Input.dispatchDragEvent` 미사용).
  native 경로와 합성 경로의 유일한 분기점인 `draggable` 속성 부여를 라이브 DOM 으로 확인해 그 간극을
  좁혔고, 이 사실을 Run fragment 에 그대로 남겼다.

## REV-20260813T193000-ai-claude-feature-0003-member-scope-gates [SKIPPED:frontend-display-gate-align-to-server-boundary] SHIP — 그룹 멤버 권한 게이트 정합

- Related TASK: feature-0003-agent-web-ui / `20260813T1930-member-scope-gates`
- Timestamp: 2026-08-13T19:30:00+09:00
- Human Approval Needed: no — 사용자가 감사 결과를 보고 **A+B+C 수정 범위를 명시 승인**(2026-08-13).
  등급 Minor §12.3(프론트 표시 계층, 백엔드 enforcement·권한 카탈로그·스키마 불변).

**Panel skip 사유(§18.8)**: 신규 엔드포인트·권한 코드·RBAC 카탈로그·백엔드 로직 0. 변경은 프론트
게이트를 **서버가 이미 집행하는 경계**로 맞춘 것이며, 각 액션의 서버 경계를
`_account_can_access_conversation` 33 호출지점 전수 스캔으로 확인했다(아래). 본 세션은 subagent
호출이 사용자 제약으로 금지돼 직접 적대 점검을 수행했다.

**"넓히는" 변경의 과대 개방 위험 점검 (핵심 축)**

- 프론트를 넓히면 서버가 막아야 한다 — 실제로 막는지 라우트별로 확인했다. 넓힌 4종은 전부
  `_account_can_access_conversation(…, ".own", ".any")` **단독** 게이트이고 2차 owner 게이트가 없다
  (`/api/cancel` conversations.py:531 · `/api/finalize` 591 · `/api/extend` 626 · read 계열).
  즉 멤버 허용은 **서버의 기존 결정**이고 프론트가 그것을 부정하고 있었다.
- 반대 방향(과대)으로 새지 않는지도 확인 — `rename`(2999, owner 2차 게이트) · `archive`(4785) ·
  `duplicate`(817, 엄격 `_conversation_owned_by_account`) · 공유 `joinable` 토글 · `…/shares`(1830)
  는 `own` 을 유지했다. 테스트 case3 가 이 비대칭을 잠근다(멤버에게 rename/delete/duplicate 는
  여전히 차단, 내 대화에서는 허용).
- 권한 자체가 없는 계정은 멤버여도 차단됨을 별도 케이스로 확인(case6) — `.own` **권한 보유**가
  여전히 AND 조건이다. 즉 "멤버면 무조건 허용" 이 아니라 "멤버도 `.own` 범위" 로만 넓혔다.
- `.any` 열람 대화(owner·멤버 모두 아님)는 `ownScope=false` 이므로 종전과 동일하게 `.any` 권한자
  (관리자)만 통과 — 일반 사용자에게 새 표면이 열리지 않는다(case4·case5·case7 경계 양측).

**설계 판단 — 왜 predicate 를 하나로 통합하지 않았나**: `own` 을 전부 `ownScope` 로 바꾸면 서버가
2차 owner 게이트로 막는 액션(제목 변경·보관·복제)이 활성으로 보여 **반대 방향 불일치**가 생긴다
(클릭 → 403). 서버 경계가 액션마다 다르므로 프론트도 두 계층을 유지하고, 어느 쪽을 쓸지 판정하는
기준(서버 라우트에 2차 owner 게이트가 있는지)을 predicate 주석에 명문화했다. 구조 잠금 10건이
두 계층의 분기 개수(`codes: ownScope ?` 4 / `codes: own ?` 3)까지 센다 — 한쪽만 늘어나면 FAIL.

**검증 채널·한계 (정직 표기)**: jsdom 은 판정 함수와 `markAccessBlocked`/`makeMenuItem` 의 DOM
효과까지 검증했고, **서버 왕복은 검증하지 않았다**. 멤버 계정으로 실제 버튼을 눌러 200 을 받는
라이브 실측은 POST-DEPLOY PB-0008 항목이다(visual_verification_scope: always). 테스트 판별력은
`git show HEAD:app.js` 를 같은 스크립트로 평가해 수정 전 멤버 제어가 전부 `false` 임을 실측해
확인했다. 실행시간 연장의 "배너는 뜨는데 승인 불가 → 타임아웃" 은 코드 경로 대조로 확정했고
(배너 렌더는 소유 무관, 버튼만 `markAccessBlocked`), 타임아웃까지 기다린 라이브 재현은 하지 않았다.

## REV-20260813T201000-ai-claude-feature-0003-member-leave-branch [SKIPPED:frontend-branch-fix-plus-audit-correction] SHIP — 멤버 '나가기' 분기 복원 + 선행 감사 결론 정정

- Related TASK: feature-0003-agent-web-ui / `20260813T2010-member-leave-branch`
- Timestamp: 2026-08-13T20:10:00+09:00
- Human Approval Needed: no — 사용자 승인 범위(A-4 "멤버 나가기 경로") 내의 원인 정정 수정.

**Panel skip 사유(§18.8)**: 프론트 분기 판정 1줄 + 테스트/문서. 신규 엔드포인트·권한·백엔드 0.

**정정 (§16.5 정직성 — 선행 cycle 의 오진 기록)**

선행 `REV-20260813T193000` 은 A-1~A-4 를 "확정 결함" 으로 서술했다. **그 판정의 전제가 틀렸다** —
`can(permission)` 이 `void permission; return Boolean(state.user)` 라 `can("X.any") || …` 형태는
로그인 사용자에게 항상 true 이고, `markAccessBlocked`·`showPermissionDeniedToast` 는 도달하지 않는다.
따라서 중단·즉시답변·연장은 멤버가 **원래 막히지 않았고**, 배포된 predicate 교체는 그 축에서 no-op
(의미 명료화)이다. 오진 원인은 **판정 함수의 정의를 확인하지 않고** 코드 대조를 "확정" 으로 부른 것 —
그 사실은 auto-memory 에도 있었는데 적용하지 않았다. 재발 방지는 `docs/LEARNINGS.md`
`LRN-20260813-display-permissive-can-invalidates-gate-audit` 규칙 5개로 남겼다.

**본 cycle 이 고치는 것은 실측으로 확정했다**

- 라이브(배포 `fa99ed69`, 멤버 계정 `dqa_memtest`): 설정 팝업 `dangerBtn.textContent === "보관"`,
  `hasLeaveWord: false` — 멤버에게 나가기 진입점이 없다.
- 같은 계정으로 서버 호출: `/api/delete_conversations` → `failed:[{reason:"forbidden"}]`(보관 안 됨),
  `PATCH …/title` → `403 "소유자만 대화 제목을 변경할 수 있습니다."` — 프론트가 내민 버튼이 서버에서
  **항상 거부**됨을 양쪽에서 확인(§16.7 G4).
- 수정 후 하네스로 HEAD 를 평가하면 case2 가 6건 FAIL(멤버가 '보관' + archive 호출) — 판별력 실증.

**설계 판단 — 왜 `canOpenAdminConsole()` 인가**: `.any` 권한 보유를 프론트에서 알 방법은
`console_access` 플래그뿐이다(`/api/session` 이 직렬화하는 유일한 권한성 사실 — `permissions` 맵은
TASK-0098 로 미직렬화). 관리자가 타 계정 그룹 대화를 보관하는 경로를 유지하면서 일반 멤버에게는
나가기를 주는 최소 판정이다. 서버는 여전히 `.any` 로 집행하므로 프론트 판정이 과대해도 403 로 막힌다.

**의도적으로 건드리지 않은 것**: 제목 입력(`titleInput.disabled = !canRename`)은 멤버에게 활성이고
서버가 403 한다. 이는 이 코드베이스가 채택한 display-permissive 컨벤션("넓게 표시 + 백엔드 403")이며
**분기가 아니라 표시**라 나가기 건과 성질이 다르다. 현 동작을 테스트로 고정(case5)해, per-code `can()`
이 도입되면 FAIL 로 함께 재검토되게 했다.

**검증 채널·한계**: jsdom 실 DOM 렌더까지 검증했고 **서버 왕복은 라이브에서 별도 확인**(위 forbidden/
403 실측). 멤버가 '나가기' 를 눌러 실제로 빠지는 end-to-end 는 POST-DEPLOY PB-0008 항목이다.
## REV-20260813T183000-group-attach-scope-window [CODEX:adversarial-security] — 공유 대화 첨부 스코프 확대

- Related Change: `CHG-20260813T183000-ai-claude-feature-0003-group-attach-scope-window`
  (friction-id `FR-group-attach-sender-scope-blocks-members`, 위험등급 **Critical §12.3**).
- Trigger (§18.8 dispatch): changeset 에 `auth/credential/세션`(인가 경계 변경)·`schema/query`
  (신규 PG 게이트 쿼리)·프롬프트 계약 변경이 함께 걸린다 → **security + backend + qa** 렌즈.
  세션 지시로 Agent 도구를 쓰지 않으므로 §18.9 대체 채널인 **codex CLI**(별도 도구)로 집행했다.
- 집행 형태: staged diff 를 codex 가 직접 읽고(`git diff --cached`) 5축(fail-closed 완전성 ·
  SQL 동형성 · 두 분기 적용 · positional index 회귀 · 프롬프트 통제 실효성)을 적대 검증.
  결과 **[P1] 2건 · [P2] 3건**. 게이트 = FAIL → 아래 반영 후 재검증 대상.

### 반영 (5/5)

- **[P1-1] 그룹 판정 실패가 fail-open** — `_conversation_is_group()`/`_is_group_conversation()` 은
  PG 오류 시 `False` 를 돌려주므로 window 게이트를 **건너뛰고 대화 전체로 열린다**. 판정 실패가
  가장 넓은 스코프로 귀결되는 구조였다. → 그룹 여부를 게이트가 **직접** 판정하도록 흡수(멤버 수·
  소유자·window 를 한 쿼리에서). 호출측 선-게이팅 제거(`sender_scope=True` 고정). 1:1·fork 는
  멤버 ≤ 1 로 판정돼 무회귀. **회귀는 아니었다**(종전에도 판정 실패 시 대화 전체였다) — 그러나
  "게이트로 봉인했다" 는 주장과 어긋나므로 수정했다.
- **[P1-2] 프롬프트 통제는 보안 경계가 아니다(confused-deputy 잔존)** — 타당하다. 다만 지적의
  전제 하나는 **부정확**했다: 첨부 본문은 이미 `_datamark_untrusted` 비신뢰 구획에 들어간다
  (`agent_core.py`, TASK-20260619T033714). 방어는 산문 단독이 아니라 datamark + 기존 인젝션 지침 +
  출처 계약 3층이다. 그럼에도 **확률적 완화이지 보장이 아니다**(§14 와 같은 전제) → 타 멤버 파일의
  datamark **구획 헤더에 업로더**를 추가하고, **잔여 위험을 SECURITY §47.4 에 명시**했다.
  provenance 기반 tool 게이트는 별도 설계·승인이 필요한 **후속 과제**로 남긴다(정직 표기).
- **[P2-3] hidden_count 가 `_msg_outside_window` 와 비동형** — floor 존재 시 assistant 답변의
  recall 태그(`recall_full`·`recall_floor_created_at`)로도 메시지가 숨는데 SQL 은 그 축을 세지
  않는다. → **floor 설정 멤버는 은닉 수와 무관하게 sender-only** 로 바꿔 비동형 구간을 구조적으로
  제거했다(그 축까지 SQL 로 재현하면 두 구현이 갈릴 위험이 실익보다 크다). ceiling-only 멤버만
  은닉 구간을 계산하며, 그 축에서는 동형이 성립한다. 라이브 bounded 멤버 2명은 전부 ceiling-only.
- **[P2-4] LEFT JOIN 멤버 행 NULL → 전체 스코프(fail-open)** — → 소유자 판정을 같은 쿼리에 넣고,
  **그룹인데 멤버 행이 없으면(비-owner) sender-only**. 누락·불일치도 좁은 쪽으로 떨어진다.
- **[P2-5] 라벨·계약이 이름 조회 실패 시 함께 사라짐** — 스코프만 열리고 방어가 빠지는 최악 조합.
  → 계약 발동 조건을 **row 사실**(`_has_other_uploader`)로 옮기고, 이름은 있으면 쓰고 없으면
  `another member` 로 적되 **타 멤버라는 사실은 잃지 않게** 했다. 부수 효과로 본인 파일만 있는
  그룹에는 계약이 붙지 않아 프롬프트도 절약된다.

### 확인된 무결 축 (codex 검증)

- 축 3 — `restrict_to_sender` 는 PG(`_conv_store.py:3461`)·MySQL(`:3475`) **양 분기 모두** 적용.
- 축 4 — 업로더 컬럼을 SELECT **끝에** 붙여 기존 `row[0..11]` 소비자 보존, 다른 positional 소비자 없음.

### 검증

- 신규·갱신 테스트 **46 PASS**(게이트 규칙 18 · 스코프 해소 21 · 출처 계약 10 중 중복 제외).
  적대 리뷰가 지적한 5개 경로는 전부 회귀 테스트로 고정했다(fail-open 3종 · 이름 조회 실패 · floor).
- 한계(정직): 게이트 쿼리의 **라이브 실행**은 배포 후 실측 대상이다. 단위 테스트는 fake 커서라
  SQL 문법·계획은 검증하지 못한다(구조 잠금 정규식으로 축만 고정).

## REV-20260813T203000-group-attach-postdeploy [SKIPPED:doc-only] — POST-DEPLOY 실측 기록

- Related Change: `CHG-20260813T203000-ai-claude-feature-0003-group-attach-postdeploy`
- Trigger: §18.8 dispatch 표 키워드 **0건** + **코드 변경 0**(원장·TASK 문서만) → 패널 skip.
  선행 cycle 의 코드 변경은 `REV-20260813T183000-group-attach-scope-window`
  ([CODEX:adversarial-security], P1 2·P2 3 전건 반영)에서 이미 집행됐다.
- 검증: 기록된 수치는 전부 배포본 실행 결과다 — `GIT_COMMIT` 3서비스 · caddy `no upstreams
  available` 0 · 판정 함수 직접 호출 3/3. 기록과 실행 사이에 추정이 없다.
- Human Approval Needed: 아니오 (doc-only, 선행 cycle 의 Critical 승인 범위 내 사후 기록).

## REV-20260813T213000-ai-claude-feature-0003-member-gates-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: feature-0003-agent-web-ui / `20260813T2130-member-gates-postdeploy`
- Reason: changed paths are docs only — 코드·스키마·권한 변경 0 (POST-DEPLOY 실측 기록 + 증적)
- Timestamp: 2026-08-13T21:30:00+09:00
- Human Approval Needed: no

- **판정 근거**: 서빙 주체의 실제 SHA(web-a·web-b `mysql-ai-web:660e9fcf`) + 엣지 무중단 0건 +
  **분기 양방향 실측**(멤버='나가기' → 실제 이탈 / 소유자='보관')으로 확인했다. 앞선 오진의 교훈대로
  "코드가 그러하다" 가 아니라 **배포본에서 두 갈래를 각각 구동**해 판정했다.
- **충돌 해소의 안전성**: 다른 세션 #1260 과의 충돌 4건은 전부 append-only 문서 말미 경합이라 양쪽
  항목을 보존했고(§13.1), 병합 후 프론트 `.mjs` 62개를 재실행해 회귀 0을 확인한 뒤 머지했다.

## REV-20260814T010301-doc-sync-rn-0814 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-08-13 블록 10항목 append doc_sync 정합

- Related TASK: feature-0003-agent-web-ui / `20260814T010301-doc-sync-rn-0814`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + 그 companion 문서).
- Timestamp: 2026-08-14T01:03:01+09:00
- Human Approval Needed: no

- **타깃별 실질 검증**: `node --check` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 34/0 동일 = 회귀 0) · 구조 단언(releases 48 불변 · head date 2026-08-13 · items 1→11 · `generated`==head.date · 기존 47 블록 보존 · enum 위반 0 · 스키마 외 키 0).
- **블록 date 판정**: 델타 창(`807fce6f`..HEAD) 27 커밋의 git-date 가 전부 2026-08-13 이고 그 date 블록이 owning feature 커밋 `0c3b0d01` 의 self-add 로 **이미 존재**했다 → 신규 블록(08-13 중복 헤더 / 08-14 허위 배포일) 대신 **기존 블록에 append**. `generated` 는 top-block date 규약대로 불변.
- **배포 게이트 = 물리 실측으로 판정**(정본 문면이 아니라 라이브): 컨테이너 6종 전부 `:d585250b` = HEAD = origin/main 이므로 10항목의 근거 커밋 전건이 배포본에 포함. 서빙 static md5 파리티 정확 일치 · `/healthz` 200 → **유보 항목 0**.
- **적대검증(ULTRACODE `wf_285f2b56-8df` · 5 에이전트)**: RN 축 refute-first 검증이 결함 6건(P1 2 · P2 4) 적발. 오케스트레이터가 **워크플로 판정을 그대로 신뢰하지 않고 정본으로 독립 재검증**해 전건 CONFIRMED:
  - [P1 확정] `src/static/app.js:1173-1179` — `can(permission)` 은 `void permission; return Boolean(state.user)`(display-permissive, TASK-0098). 따라서 `showPermissionDeniedToast`/`markAccessBlocked` 는 로그인 사용자에게 도달하지 않고, '공유 링크 관리' 토스트는 표시된 적이 없다. `docs/REPORT.md:2472` 정정 배너가 A-1~A-4 를 명시 철회했는데 초안이 A-4 를 사용자향 표면에 되살리고 있었다 → 삭제.
  - [P1 확정] `shared/share_window.py:40` `SCOPE_SENDER_ONLY = "sender-only"  # 발신자 본인 첨부만 (fail-closed / 종전 CSO F1)` — 은닉 구간이 실재하는 멤버는 "볼 수 있는 구간의 첨부" 가 아니라 **본인 첨부만** 받는다. 초안은 미래 정밀화(첨부 시간축 왜곡 해소 후)를 현재 동작으로 적었다 → 실제 동작으로 교정.
  - [P2 확정] 08-07 블록(`release-notes-data.js` "버전 비교에서 두 버전의 내용이 같으면 문서 원문을 보여 줍니다")의 재서술 → 이번 창의 신규분(`from == to` 같은 버전 두 개 선택 경로)만 남기도록 교정.
  - [P2 확정] 미집행 knob 은 `89b7cd54` **같은 커밋 안**에서 머지 전 제거돼 라이브 노출 0 → "화면에 보이던 상한을 없앴다" 서술 삭제(패널 오배치 정정은 `feadc089` POST-DEPLOY 실측이라 유지).
  - [P2 확정] 오도 안내 2곳은 서로 다른 요소 — `src/static/app/composer.js:346` "읽기 전용 대화"(입력창) / `src/static/app.js:2462` "다른 계정의 대화는 조회만 가능합니다"(대화 위쪽 안내줄) → 각각 인용.
  - [P2 확정] `0.1픽셀` 소수점 정밀도(파일 전체 `픽셀` 선례 0) → 사용자 판단에 기여하는 근사치로 교체.
- **포함/제외 판정**: 델타 27 non-merge 중 사용자 체감 변화 10건 채택. 제외 12건은 POST-DEPLOY 실측 기록·증적 전용(코드 변경 0), `86d89b60`/`2c59c183`(안내 정본 URL 화)는 항목 ②의 새 흐름 서술과 같은 사실이라 흡수, `34376206`(라이브 기동 3중 원인)의 사용자 체감분도 항목 ② 말미로 흡수.
- **테스트 env**: 무인 cron(WSL2 컨테이너 호스트). `verify_release_notes.mjs` 는 `unit/feature-0003-agent-web-ui` 에서 실행(jsdom `/tmp/node_modules`). PB-0008 은 TEST.md 에 미수행 사유·대체 검증 명시.
- **cache-buster**: 수기 bump 없음. 소스 `?v=dev` placeholder 고정 + Dockerfile `inject_asset_stamp.py` 빌드 주입 + `bin/deploy-web.sh:1092` 가 placeholder 잔존 시 배포 ABORT(2026-07-12 ITEM-09). 라이브 실측 토큰 `?v=51af138635ba`. `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유(이중 landing/배포 racing 방지). 서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.
## REV-20260813T164000-ai-claude-corp-usage-metric-solo-anim [SKIPPED:non-policy-doc] — 프론트 표시 계층 전환 규칙 정정

**Trigger**: UI/layout keyword — 그러나 변경 표면이 `static/admin/usage.js` 렌더 3함수 +
`css/admin.css` 1선언 + 하네스로, 신규 권한·스키마·엔드포인트·데이터 경로 0. §18.8 표의 코드 변경
행에 해당하나 실질은 **선행 cycle 이 만든 전환 규칙의 경계 결함 수정**이라 경량 경로로 처리하고,
대신 **뮤테이션 역검증으로 검사의 판별력을 실증**했다(수정 전 sig 복원 시 5건 정확히 FAIL).

### 판단 근거

- **왜 signature 를 좁혔나** — 초기 설계는 "세그먼트 정체성이 달라지면 재생성" 이었고 그게 옳다고
  봤다. 실제로는 '요청'이 그 경계를 매 클릭 넘나드는 **일상 경로**였다(사용자가 바로 발견). 막대의
  정체성을 결정하는 것은 세로 구성이 아니라 **가로 배치**(어느 일자 자리에 서는가)이므로, 세로
  구성 변화는 접기/자라기로 표현하는 편이 사용자가 보는 연속성과 맞는다.
- **0 높이 노드를 남기는 비용** — 키 집합이 유한(일자 × (모델+1))하고 지표 전환마다 증가하지
  않는다. 남은 노드는 다음 전환에서 재사용되므로 누적이 아니라 재활용이다.
- **검사도 함께 정정** — "요청 지표는 막대 1개" 같은 기존 단정은 0 높이 노드를 남기는 새 설계와
  맞지 않는다. 다만 완화가 아니라 **사용자에게 보이는 것(height>0)** 기준으로 다시 적었고,
  "모델 세그먼트가 전부 0 높이로 접혔다" 는 단정을 추가해 커버리지를 오히려 넓혔다.

### 잔여

- 도넛에서 값 0 인 모델이 범례에 `0.0%` 로 남는다. 캐시 지표처럼 일부 모델만 값이 있는 경우
  "그 모델은 0" 이라는 사실 표기라 오해가 없다고 판단했다(숨기면 목록이 흔들린다).

## REV-20260813T172000-ai-claude-corp-usage-metric-solo-anim-width [SKIPPED:non-policy-doc] — 폭 흔들림(2차 기전) 수정

**Trigger**: 선행 수정과 같은 표면(`static/admin/usage.js` 렌더 1함수 + 하네스). 신규 권한·스키마·
엔드포인트 0. §18.8 경량 경로 + **뮤테이션 역검증으로 판별력 실증**(2종 KILLED).

### 이번 판단의 핵심 — 1차 수정이 왜 불충분했나

1차에서 "세그먼트 키 집합이 달라도 노드 유지" 를 만들고 헤드리스 32 PASS 를 받았지만, **라이브에선
여전히 재생성**됐다. 두 환경이 갈린 지점은 데이터 크기가 아니라 **스크롤바**였다 — '요청'은 범례가
없어 페이지가 짧아지고, 세로 스크롤바가 사라지면서 차트 폭이 12px 달라진다. 폭이 signature 에 있는
한 그 자체로 매 전환이 재생성이다.

교훈은 "헤드리스 PASS 를 라이브 PASS 로 읽지 말 것" 이다. 헤드리스 픽스처(2일 × 2모델)는 페이지가
짧아 **스크롤바가 애초에 없었고**, 그래서 결함을 만들 조건 자체가 없었다. 라이브에서 sig 를 직접
덤프해 폭 차이를 본 뒤에야 갈라졌다.

### 왜 폭을 signature 에서 빼는 것이 옳은가

막대의 정체성은 "어느 일자 자리에 서는가" 다. 폭은 같은 막대가 **얼마나 넓게 그려지는가** 일 뿐이라
정체성이 아니며, 컨테이너 리사이즈·스크롤바 같은 외부 요인으로 수시로 변한다. 폭 변화는 재생성이
아니라 좌표 재배치로 다루는 것이 맞고, 그래서 in-place 경로가 viewBox·축·x라벨·막대 가로 기하를
새 폭으로 맞춘다(가로는 즉시 반영, 세로만 애니메이션 — 폭이 튀는 것까지 애니메이션하면 리사이즈가
출렁인다).

### 잔여


- **왜 signature 를 좁혔나** — 초기 설계는 "세그먼트 정체성이 달라지면 재생성" 이었고 그게 옳다고
  봤다. 실제로는 '요청'이 그 경계를 매 클릭 넘나드는 **일상 경로**였다(사용자가 바로 발견). 막대의
  정체성을 결정하는 것은 세로 구성이 아니라 **가로 배치**(어느 일자 자리에 서는가)이므로, 세로
  구성 변화는 접기/자라기로 표현하는 편이 사용자가 보는 연속성과 맞는다.
- **0 높이 노드를 남기는 비용** — 키 집합이 유한(일자 × (모델+1))하고 지표 전환마다 증가하지
  않는다. 남은 노드는 다음 전환에서 재사용되므로 누적이 아니라 재활용이다.
- **검사도 함께 정정** — "요청 지표는 막대 1개" 같은 기존 단정은 0 높이 노드를 남기는 새 설계와
  맞지 않는다. 다만 완화가 아니라 **사용자에게 보이는 것(height>0)** 기준으로 다시 적었고,
  "모델 세그먼트가 전부 0 높이로 접혔다" 는 단정을 추가해 커버리지를 오히려 넓혔다.

### 잔여

- 도넛에서 값 0 인 모델이 범례에 `0.0%` 로 남는다. 캐시 지표처럼 일부 모델만 값이 있는 경우
  "그 모델은 0" 이라는 사실 표기라 오해가 없다고 판단했다(숨기면 목록이 흔들린다).

## REV-20260813T172000-ai-claude-corp-usage-metric-solo-anim-width [SKIPPED:non-policy-doc] — 폭 흔들림(2차 기전) 수정

**Trigger**: 선행 수정과 같은 표면(`static/admin/usage.js` 렌더 1함수 + 하네스). 신규 권한·스키마·
엔드포인트 0. §18.8 경량 경로 + **뮤테이션 역검증으로 판별력 실증**(2종 KILLED).

### 이번 판단의 핵심 — 1차 수정이 왜 불충분했나

1차에서 "세그먼트 키 집합이 달라도 노드 유지" 를 만들고 헤드리스 32 PASS 를 받았지만, **라이브에선
여전히 재생성**됐다. 두 환경이 갈린 지점은 데이터 크기가 아니라 **스크롤바**였다 — '요청'은 범례가
없어 페이지가 짧아지고, 세로 스크롤바가 사라지면서 차트 폭이 12px 달라진다. 폭이 signature 에 있는
한 그 자체로 매 전환이 재생성이다.

교훈은 "헤드리스 PASS 를 라이브 PASS 로 읽지 말 것" 이다. 헤드리스 픽스처(2일 × 2모델)는 페이지가
짧아 **스크롤바가 애초에 없었고**, 그래서 결함을 만들 조건 자체가 없었다. 라이브에서 sig 를 직접
덤프해 폭 차이를 본 뒤에야 갈라졌다.

### 왜 폭을 signature 에서 빼는 것이 옳은가

막대의 정체성은 "어느 일자 자리에 서는가" 다. 폭은 같은 막대가 **얼마나 넓게 그려지는가** 일 뿐이라
정체성이 아니며, 컨테이너 리사이즈·스크롤바 같은 외부 요인으로 수시로 변한다. 폭 변화는 재생성이
아니라 좌표 재배치로 다루는 것이 맞고, 그래서 in-place 경로가 viewBox·축·x라벨·막대 가로 기하를
새 폭으로 맞춘다(가로는 즉시 반영, 세로만 애니메이션 — 폭이 튀는 것까지 애니메이션하면 리사이즈가
출렁인다).

### 잔여

- 축·x라벨 갱신이 `innerHTML` 교체라 그 순간 텍스트 노드가 새로 만들어진다. 전환 대상이 아니므로
  시각적 영향은 없다(선·숫자는 제자리에 즉시 그려진다).
## REV-20260813T164000-ai-claude-corp-usage-metric-solo-anim [SKIPPED:non-policy-doc] — 프론트 표시 계층 전환 규칙 정정

**Trigger**: UI/layout keyword — 그러나 변경 표면이 `static/admin/usage.js` 렌더 3함수 +
`css/admin.css` 1선언 + 하네스로, 신규 권한·스키마·엔드포인트·데이터 경로 0. §18.8 표의 코드 변경
행에 해당하나 실질은 **선행 cycle 이 만든 전환 규칙의 경계 결함 수정**이라 경량 경로로 처리하고,
대신 **뮤테이션 역검증으로 검사의 판별력을 실증**했다(수정 전 sig 복원 시 5건 정확히 FAIL).

### 판단 근거

- **왜 signature 를 좁혔나** — 초기 설계는 "세그먼트 정체성이 달라지면 재생성" 이었고 그게 옳다고
  봤다. 실제로는 '요청'이 그 경계를 매 클릭 넘나드는 **일상 경로**였다(사용자가 바로 발견). 막대의
  정체성을 결정하는 것은 세로 구성이 아니라 **가로 배치**(어느 일자 자리에 서는가)이므로, 세로
  구성 변화는 접기/자라기로 표현하는 편이 사용자가 보는 연속성과 맞는다.
- **0 높이 노드를 남기는 비용** — 키 집합이 유한(일자 × (모델+1))하고 지표 전환마다 증가하지
  않는다. 남은 노드는 다음 전환에서 재사용되므로 누적이 아니라 재활용이다.
- **검사도 함께 정정** — "요청 지표는 막대 1개" 같은 기존 단정은 0 높이 노드를 남기는 새 설계와
  맞지 않는다. 다만 완화가 아니라 **사용자에게 보이는 것(height>0)** 기준으로 다시 적었고,
  "모델 세그먼트가 전부 0 높이로 접혔다" 는 단정을 추가해 커버리지를 오히려 넓혔다.

### 잔여

- 도넛에서 값 0 인 모델이 범례에 `0.0%` 로 남는다. 캐시 지표처럼 일부 모델만 값이 있는 경우
  "그 모델은 0" 이라는 사실 표기라 오해가 없다고 판단했다(숨기면 목록이 흔들린다).

## REV-20260813T181000-ai-claude-corp-usage-metric-first-appear [SKIPPED:non-policy-doc] — 첫 등장 전환 + 검사 판별력 정직 표기

변경은 `usage.js` 2줄(rAF → 강제 reflow) + 하네스 검사 1건. 신규 권한·스키마 0.

### 이번 판단에서 중요한 것 — 검사가 vacuous 함을 숨기지 않았다

추가한 검사는 헤드리스에서 **PASS 하지만 뮤턴트(rAF 복원)도 PASS 시킨다**. 헤드리스 Chromium 은
rAF 한 번으로도 transition 이 걸려 결함 조건 자체가 성립하지 않기 때문이다. 이 상태를 "36→37 PASS"
로만 보고하면 커버리지가 늘어난 것처럼 읽히지만 실제 판별은 라이브가 한다. TEST.md 에 그 한계를
명시하고, 검사의 용도를 "회귀 시 라이브에서 같은 스크립트로 재확인" 으로 한정했다.

이번 결함 3건이 전부 **헤드리스 green + 라이브 red** 였다는 점이 이 축의 성격을 보여준다:
① 세그먼트 키 집합(헤드리스도 red — 잡힘) ② 스크롤바발 폭 12px(헤드리스 픽스처엔 스크롤바 없음)
③ rAF 타이밍(헤드리스는 관대). 렌더 타이밍·레이아웃 의존 축은 헤드리스를 **1차 그물**로만 쓰고
최종 판정은 실 브라우저에 둔다는 §16.6 의 원칙이 실증됐다.
## REV-20260814T010000-attach-version-branching [CODEX:adversarial-data-integrity] — 버전 계보 분기

- Related Change: `CHG-20260814T010000-ai-claude-feature-0003-attach-version-branching`
  (REQ-20260814-attach-version-branching, 위험등급 **Major §12.3**).
- Trigger (§18.8 dispatch): `schema/query`(버전 체인 쿼리·신규 계보 조회) + 데이터 생성 경로 변경
  → **backend + qa** 렌즈. 세션 지시로 Agent 도구 미사용 → §18.9 대체 채널 **codex CLI**.
- 집행: staged diff 를 codex 가 직접 읽고 5축(계보 가정 파손 소비자 · supersede 생략의 정합성 ·
  `RootAttachmentId=NULL` 상호작용 · 신규 조회 IDOR · 프롬프트가 코드가 보장 못 하는 것을 말하는가)
  적대 검증. 결과 **[P1] 3건 · [P2] 1건** → 전건 반영(MODIFY 의 반영 절 참조).
- **가장 중요한 적발**: 사용자 재업로드가 AI 계보로 편입되는 경로. 분기를 도입하면서 *반대 방향*
  (사용자 업로드 → 계보 선택)의 역할 스코프를 놓쳤다. 이 하나로 계보 분리가 무너진다.
- 무결 확인(codex): `RootAttachmentId=NULL` ↔ `UNIQUE(Root,Version)` · `WHERE Root=X OR Id=X` 형태 ·
  chain 삭제/diff · ZIP 중복명 · 분기 row 의 PG 미러에서 별도 결함 없음.
- 검증: 신규/갱신 테스트 **20**(계보 프롬프트 13 · 분기 계약 10 중 신규 2 포함 · versioning 2) +
  관련 스위트 61 PASS. 전체 스위트 회귀 실패 0(잔여는 선재 환경 의존 파일 1개).
- 한계(정직): 분기·연장 경로는 MinIO·audit·dual-write 를 함께 태워 fake 로 전 구간을 돌리기 어려워
  **소스 구조 잠금**으로 계약을 고정했다(§16.7 G10 동형). 실제 INSERT/supersede 의 라이브 동작은
  배포 후 실측 대상이다.

## REV-20260813T190000-ai-claude-corp-usage-metric-profile [SKIPPED:non-policy-doc] — 프로필 사용 내역 지표 정합

**Trigger**: UI keyword + profile 집계 라우터. 신규 권한·스키마·엔드포인트 0(기존 응답에 필드 추가).

### 판단 근거 — '정합하게' 를 복제가 아니라 정본으로 풀었다

두 화면에 같은 지표 목록을 각각 적어 넣으면 그 순간은 같아 보이지만, 다음 변경에서 한쪽만 고쳐진다.
저장소가 `modal-dismiss.js`(배경 dismiss)·`hangul-qwerty.js`(자판 교차 검색)에서 확립한 규약 —
**복제가 곧 결함 기전** — 을 지표 정의에도 적용해 `usage-metrics.js` 하나로 두고 두 번들이 import
한다. 하네스는 그 정본을 **stub 이 아니라 소스 그대로** 주입해, "카드가 정본과 동일 순서·라벨" 을
실제로 대조한다(stub 이면 이 검사가 vacuous 해진다).

공유 범위는 **정의까지**다. 렌더는 각자 유지했다 — 관리 화면은 역할/계정 drill 과 넓은 캔버스를,
프로필은 본인 범위 2차트를 갖는다. 렌더까지 합치려 했으면 클래스·크기·상호작용 차이가 옵션 폭발로
돌아왔을 것이다.

### 전환 규칙은 '이식' 이 아니라 '동일 규칙 적용'

관리 화면에서 3차에 걸쳐 밝혀낸 것(① 세그먼트 키 집합 ② 폭 흔들림 ③ 신규 노드 rAF 타이밍)을
프로필에도 처음부터 반영했다 — 일자 집합만 signature, 접기/자라기, 폭은 좌표 재배치, 신규 노드는
강제 reflow 후 목표값. 같은 결함을 두 번 겪지 않기 위한 것이고, 하네스가 그 축들을 프로필에서도
독립적으로 단정한다.

### 잔여

- 프로필은 모델 필터 칩이 없어 '요청' 지표의 부분 선택 충돌(관리 화면의 카드 비활성)이 성립하지
  않는다 — 그 분기를 프로필에 넣지 않았다(없는 상태를 방어하는 죽은 코드가 된다).
## REV-20260814T023000-attach-branch-postdeploy [SKIPPED:doc-only] — POST-DEPLOY 실측 기록

- Related Change: `CHG-20260814T023000-ai-claude-feature-0003-attach-branch-postdeploy`
- Trigger: §18.8 dispatch 표 키워드 0건 + **코드 변경 0**(TASK 문서만) → 패널 skip. 선행 cycle 의
  코드 변경은 `REV-20260814T010000-attach-version-branching`([CODEX:adversarial-data-integrity],
  P1 3·P2 1 전건 반영)에서 집행됐다.
- 검증: 기록된 수치는 전부 배포본 실행 결과다(GIT_COMMIT 3서비스 · caddy 0 · 계보 조회 직접 호출).
- Human Approval Needed: 아니오 (doc-only, 선행 cycle 승인 범위 내 사후 기록).

## REV-20260813T200000-ai-claude-corp-usage-metric-final-postdeploy [SKIPPED:non-policy-doc] — 양 화면 실측 기록

doc-only(코드 0). 기록의 근거는 라이브 DB 조회와 실 Chrome 관측이다.

### 남길 가치가 있는 것 — 두 번 다 "도구를 먼저 의심해야 했다"

이번 요청 전체에서 **코드 결함으로 오인할 뻔한 측정 함정이 2건** 나왔다. 하나는 SVG geometry 를
`getBoundingClientRect()` 로 재서 전환이 없다고 판단한 것, 다른 하나는 `display:none` 조상 아래에서
측정해 프로필 전환이 죽었다고 판단한 것이다. 둘 다 브라우저의 정상 동작이었고, 실제 결함(3건)과
섞여 있었기 때문에 더 헷갈렸다 — 같은 화면에서 어떤 관측은 진짜 결함이고 어떤 관측은 도구 탓이었다.

갈라낸 방법은 같다: **격리 실험**. 새 SVG/rect 를 만들어 같은 조작을 하고, 복제본을 다른 부모로
옮겨 재시도하고, 관리 화면에서 동일 스크립트를 돌렸다. "안 된다" 를 보고하기 전에 "이 도구로 되는
것이 있는가" 를 먼저 확인하는 절차가 없었다면 없는 결함을 고치려 들었을 것이다.
## REV-20260814T090000-usage-records-sort-page — '사용 기록' 표 정렬·페이지네이션 (Minor §12.3)

- 요청: 사용자 — "사용 기록 표를 집계된 결과셋의 column 에 따라 정렬 + 페이지네이션".
- 등급 판정 **Minor**: 프론트 표시층 단독(js 1 + css 1), 백엔드·스키마·RBAC·집계 무변경, 비파괴.
- 설계 결정 ① **클라이언트 정렬/페이징**. 서버 정렬(ORDER BY 파라미터화)은 표시축과 질의축을
  동기화해야 하고, 이미 상한까지 받아 둔 결과셋을 다시 왕복시킨다. 상한(대화 200 + 시스템 200)이
  브라우저에서 정렬·슬라이스하기에 충분히 작다. 대신 **서버가 절단했다는 사실**은 문구로 계속
  밝힌다 — 페이저의 "총 120건" 이 기간 전체 사용량으로 읽히면 안 되기 때문.
- 설계 결정 ② **정렬 키는 표시값 기준**. raw 값으로 정렬하면 사용자가 본 순서와 어긋난다
  (주체 열의 `__ask_worker__` < `__insight_worker__` 는 화면 라벨 "요청 처리 워커"/"인사이트 워커"
  와 순서가 반대다). 하네스 C4 가 이 차이를 직접 단정한다.
- 설계 결정 ③ **기본 화면 무회귀**. 기본 정렬을 토큰 내림차순·1페이지·50행으로 두어, 이 변경을
  모르는 사용자가 열었을 때 종전과 같은 첫 화면을 본다.
- **구현 중 자체 적발(가장 중요)**: `merged` 는 정렬로 순서가 바뀌는데 nav 를 `merged[idx]` 로
  되짚고 있었다 — 정렬 후 시스템 행을 누르면 **다른 객체의 관리 화면**으로 이동한다. jsdom 하네스가
  라벨↔목적지 대조(E4)로 잡았고, 불변 색인(`rowsByIdx`)으로 수정 + pytest L4 로 구조 잠금
  (`merged[Number(` 금지 · `navByIdx` 잔존 금지).
- 검증: node 하네스 **50 PASS**(기본상태 8 · 정렬 7 · 표시-정렬 정합 4 · 페이지네이션 15 · nav
  정체성 5 · 이스케이프 3 · 로드 3) · pytest 정적 가드 **8 PASS** · feature-0003 전체 스위트
  회귀 실패 0.
- 한계(정직): jsdom 은 레이아웃·대비·실제 클릭감을 보지 못한다. sticky 열 머리 안의 button, 정렬
  전환 시 열 폭 흔들림, 페이저 배치는 **PB-0008 실 Windows 브라우저**가 배포 후 확인한다
  (`visual_verification_scope: always`).
- 무결 확인: 이스케이프 경로 무변경(F1~F3) · 모달 close/ESC/배경 dismiss 경로 무변경 ·
  profile(self) 판 미접촉.

## REV-20260814T093000-usage-records-sort-page [CODEX:adversarial-frontend-state] — CONCERN (P1 0건 · P2 1건, 전건 반영)
- Related TASK: feature-0003-agent-web-ui (TASK-20260814T090000-usage-records-sort-page)
- Source: codex exec (staged diff 적대 리뷰 — 정렬/페이지 상태 × DOM 재렌더 5축)
- Trigger: §18.8 dispatch 표가 UI 변경에 ux/design 패널을 요구하나, 본 세션에는 subagent 도구
  사용을 금지하는 상위 지시가 있어 §18.8 의 "제약 없는 채널 우선"(1번) 경로로 codex-review 를
  택했다. 미검증 도메인은 남기지 않았다 — 지적된 축(상태·접근성)은 이 채널이 덮었고, 레이아웃·
  대비는 PB-0008 이 배포 후 덮는다.
- Timestamp: 2026-08-14T09:30:00+09:00
- Verdict: CONCERN — [P1] 0건. [P2] 1건 **포커스 소실**: `renderTable` 이 thead/tbody/페이저를
  `innerHTML` 로 교체하면서 방금 누른 컨트롤이 사라져 포커스가 `body` 로 빠진다. 키보드 사용자는
  정렬 방향 토글도, 연속 페이지 이동도 할 수 없다(CSS `:focus-visible` 은 있으나 대상이 없어짐).
- 반영: `focusToken()`/`restoreFocus()` 추가 — 재렌더 전 어떤 컨트롤이었는지 선택자로 기억했다가
  같은 컨트롤에 되돌린다. 경계로 이동해 그 버튼이 비활성이 되면(마지막 페이지의 '다음') 페이저
  안의 활성 컨트롤로 옮겨 포커스를 문서 최상단으로 떨구지 않는다.
- 회귀 고정: 하네스 G1~G4 신규(정렬 후 포커스 유지 · 이어 누르면 방향 토글 · 페이지 이동 후 유지 ·
  경계 대체 이동). **뮤턴트 검증** — `restoreFocus` 호출을 주석 처리하면 G1~G4 가 정확히 4건 FAIL
  (검출기가 죽지 않았음을 고정).
- codex 가 무결 확인한 축: 정렬 키의 숫자·일시·빈 값 fallback 이 표시값과 일치 · 1건/전체 모드/
  초과 페이지 보정 · `rowsByIdx` 로 정렬 후 nav 목적지 보존 · 대화 링크 · ESC/close/배경 dismiss ·
  이스케이프 · profile(self) 판 무회귀.

## REV-20260814T101500-usage-pager-sticky [SKIPPED:tool-restricted:ux-design] — CSS 1-rule + 마크업 순서
- Related TASK: feature-0003-agent-web-ui (TASK-20260814T090000-usage-records-sort-page 후속)
- Reason: 본 세션은 subagent 도구 사용을 금지하는 상위 지시 하에 있고(§18.8 carve-out), 변경은
  직전 cycle 의 codex 적대 리뷰가 이미 덮은 표면에 대한 **CSS 1 규칙 + 마크업 순서 1줄**이다.
  결함 자체가 라이브 시각 검증(PB-0008)에서 나왔고, 검증도 같은 채널로 되돌아간다 — 미검증으로
  남는 도메인은 ux(레이아웃)이며 이는 배포 후 PB-0008 재실측으로 닫는다.
- Timestamp: 2026-08-14T10:15:00+09:00
- 판단 근거: sticky 요소는 (a) 투명하면 아래 행이 비치고 (b) 안내 문구를 덮을 수 있다 — 둘 다
  배경·경계선 부여와 마크업 순서로 처리하고 구조 테스트(L9)로 잠갔다.
- 한계(정직): 실제 겹침·틈은 실 브라우저에서만 보인다. 배포 후 PB-0008 로 첫 화면 페이저 가시성과
  스크롤 끝 겹침을 재확인한다.

## REV-20260814T104500-usage-sort-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록
- Related TASK: feature-0003-agent-web-ui
- Reason: changed paths are docs + evidence image only (no code, no policy doc)
- Timestamp: 2026-08-14T10:45:00+09:00
## REV-20260813T213000-ai-claude-corp-usage-card-overflow [SKIPPED:non-policy-doc] — 카드 넘침 수정

CSS 1블록 + 신규 하네스. 신규 권한·스키마·JS 0.

### 판단 근거

- **보고보다 넓은 범위였다** — "좁은 공간" 으로 보고됐지만 실측하니 **900px 에서도 6건** 넘쳤다.
  원인이 폭이 아니라 `flex:1` 균등 분배(8장)였기 때문이다. 보고된 조건만 고쳤다면 넓은 화면의
  넘침은 남았을 것이다. 스윕 측정이 범위를 바로잡았다.
- **자르지 않고 줄을 나눈다** — ellipsis 는 공간 문제를 즉시 없애지만 토큰 수·금액은 뒷자리가
  잘리면 값의 의미가 바뀐다. 라벨(짧고 반복)만 ellipsis 를 허용하고 숫자는 전부 노출한다.
- **150px 은 계산이 아니라 실측** — 128px 로 두면 320px 폭에서 2열이 유지되며 12자 값(130px)이
  가용폭(114px)을 넘었다. 150px 이면 그 폭에서 1열로 떨어져 카드가 넓어진다.
- **검증되지 않은 방어는 제거했다** — container query 폰트 축소는 그럴듯했지만 트랙을 150px 로
  올린 뒤 **어떤 케이스도 판별하지 못했다**(뮤턴트 생존). 남겨두면 "방어가 있다" 는 착각만 준다.
- **관리 콘솔은 손대지 않았다** — 같은 압박(8장)을 받지만 `minmax(160px)` 로 이미 안전함을 실측
  확인했다(420~1400px 넘침 0). 하네스에 축만 남겨 미래 회귀를 잡는다(§8.1 — 제안은 기록만).

### 잔여

- 드로어를 320px 미만으로 줄이면 1열에서도 라벨이 ellipsis 될 수 있다. 그 폭은 드로어 리사이즈
  하한 밖이라 검사에 넣지 않았다.

## REV-20260813T221000-ai-claude-corp-usage-card-overflow-tune [SKIPPED:non-policy-doc] — 트랙·폰트 확정


- **보고보다 넓은 범위였다** — "좁은 공간" 으로 보고됐지만 실측하니 **900px 에서도 6건** 넘쳤다.
  원인이 폭이 아니라 `flex:1` 균등 분배(8장)였기 때문이다. 보고된 조건만 고쳤다면 넓은 화면의
  넘침은 남았을 것이다. 스윕 측정이 범위를 바로잡았다.
- **자르지 않고 줄을 나눈다** — ellipsis 는 공간 문제를 즉시 없애지만 토큰 수·금액은 뒷자리가
  잘리면 값의 의미가 바뀐다. 라벨(짧고 반복)만 ellipsis 를 허용하고 숫자는 전부 노출한다.
- **150px 은 계산이 아니라 실측** — 128px 로 두면 320px 폭에서 2열이 유지되며 12자 값(130px)이
  가용폭(114px)을 넘었다. 150px 이면 그 폭에서 1열로 떨어져 카드가 넓어진다.
- **검증되지 않은 방어는 제거했다** — container query 폰트 축소는 그럴듯했지만 트랙을 150px 로
  올린 뒤 **어떤 케이스도 판별하지 못했다**(뮤턴트 생존). 남겨두면 "방어가 있다" 는 착각만 준다.
- **관리 콘솔은 손대지 않았다** — 같은 압박(8장)을 받지만 `minmax(160px)` 로 이미 안전함을 실측
  확인했다(420~1400px 넘침 0). 하네스에 축만 남겨 미래 회귀를 잡는다(§8.1 — 제안은 기록만).

### 잔여

- 드로어를 320px 미만으로 줄이면 1열에서도 라벨이 ellipsis 될 수 있다. 그 폭은 드로어 리사이즈
  하한 밖이라 검사에 넣지 않았다.

## REV-20260813T221000-ai-claude-corp-usage-card-overflow-tune [SKIPPED:non-policy-doc] — 트랙·폰트 확정

### 이번에 배운 것 — 하네스가 라이브보다 관대하면 결정을 검증하지 못한다

선행 커밋에서 트랙 150px·폰트 14px 을 골랐고 검사는 전부 green 이었다. 그런데 뮤테이션을 돌리니
**150px 뮤턴트가 살아남았다** — 하네스의 컨테이너 패딩(16px)이 라이브(실측 32px)보다 좁게 잡혀
있어, 라이브에서 1열로 떨어지는 폭이 하네스에서는 2열로 성립했기 때문이다. 즉 하네스가 라이브보다
**관대**해서 잘못된 값을 통과시켰고, 실제로 배포 후 화면은 1열로 떨어졌다(캡처로 확인).

패딩을 라이브 실측값에 맞춘 뒤 재탐색하니 138px 이 나왔고, 이제 양쪽 뮤턴트(120px 넘침 재발 /
150px 1열 전락)가 각각 다른 검사를 FAIL 시킨다 — **값이 양쪽에서 조여졌다**는 증거다.

교훈은 "하네스 수치는 라이브에서 재서 넣는다" 이다. 임의로 그럴듯한 값을 쓰면 하네스가 통과시키는
범위가 실제와 어긋나고, 그 위에서 고른 결정은 검증된 것처럼 보이지만 아니다.

### 검증되지 않는 것은 되돌렸다

폰트 14px 도 같은 방식으로 걸러졌다 — 어떤 케이스도 더 통과시키지 못했으므로(뮤턴트 생존) 15px 로
되돌렸다. 방어를 남기면 "이유가 있어 작게 했다" 는 잘못된 신호를 주고 가독성만 잃는다.
## REV-20260814T110000-profile-usage-sort-page [CODEX:adversarial-frontend-port] — CONCERN (P1 0건 · P2 4건 → 3건 반영 · 1건 계측으로 반증)
- Related TASK: feature-0003-agent-web-ui
- Source: codex exec (staged diff 적대 리뷰 — 이식 누락/상태·재렌더/경계/회귀/CSS 5축)
- Trigger: §18.8 dispatch 표가 UI 변경에 ux 패널을 요구하나 본 세션에는 subagent 금지 상위 지시가
  있어 §18.8 "제약 없는 채널 우선"(1번)의 codex-review 를 택했다. 레이아웃 도메인은 **실 Chromium
  하네스로 직접 계측**해 덮었고(미검증으로 남기지 않았다), 최종 시각은 PB-0008.
- Timestamp: 2026-08-14T11:00:00+09:00
- Verdict: CONCERN — [P1] 0. [P2] 4건 중
  ① 속성 인젝션(`'` 미이스케이프) → **반영**. 관리 콘솔은 타인 제목을 보므로 stored 경로 실재.
  ② sticky 열 머리가 스크롤러에 미부착 → **반영**(스크롤러 단일화). 뮤턴트로 4건 FAIL 확인.
  ③ 좁은 폭 페이저 넘침 → **반증**. 320/480/640px 실측 통과, 뮤턴트(줄바꿈 제거)도 통과 =
     이 축은 현재 검출력이 없다. 지적을 수용하는 대신 계측 결과를 기록하고, 방어적 줄바꿈만 유지.
  ④ 오래된 응답이 현재 모달을 덮는 경합 → **이월**(아래 한계 참조).
- **판단 기록 — ④를 이번에 고치지 않은 이유**: `openProfileUsageConversations` 의 요청-응답 경합은
  이번 변경이 만든 것이 아니라 **선재 구조**이고, 관리 콘솔 판(`openUsageConversations`)에도 똑같이
  있다. 한쪽만 고치면 "두 화면 규칙을 맞춘다"는 이번 cycle 의 목적과 어긋나고, 양쪽을 고치는 것은
  요청 범위(정렬·페이지네이션 정합) 밖의 확장이다. REPORT 에 이월로 명시한다 — 숨기지 않는다.
- 검증: node 45(profile) + 50(admin 무회귀) · 실 Chromium 12(두 화면 × sticky/폭/가시성, 뮤턴트
  검출력 확인) · pytest 16 · feature-0003 전체 스위트 회귀 0.
- 한계(정직): jsdom·헤드리스는 실 Windows 폰트·스크롤바 폭·DPI 를 반영하지 않는다. 배포 후
  PB-0008 로 두 화면을 모두 재확인한다(관리 콘솔 판은 스크롤러 변경의 영향을 받는다).
## REV-20260813T213000-ai-claude-corp-usage-card-overflow [SKIPPED:non-policy-doc] — 카드 넘침 수정

CSS 1블록 + 신규 하네스. 신규 권한·스키마·JS 0.

### 판단 근거

- **보고보다 넓은 범위였다** — "좁은 공간" 으로 보고됐지만 실측하니 **900px 에서도 6건** 넘쳤다.
  원인이 폭이 아니라 `flex:1` 균등 분배(8장)였기 때문이다. 보고된 조건만 고쳤다면 넓은 화면의
  넘침은 남았을 것이다. 스윕 측정이 범위를 바로잡았다.
- **자르지 않고 줄을 나눈다** — ellipsis 는 공간 문제를 즉시 없애지만 토큰 수·금액은 뒷자리가
  잘리면 값의 의미가 바뀐다. 라벨(짧고 반복)만 ellipsis 를 허용하고 숫자는 전부 노출한다.
- **150px 은 계산이 아니라 실측** — 128px 로 두면 320px 폭에서 2열이 유지되며 12자 값(130px)이
  가용폭(114px)을 넘었다. 150px 이면 그 폭에서 1열로 떨어져 카드가 넓어진다.
- **검증되지 않은 방어는 제거했다** — container query 폰트 축소는 그럴듯했지만 트랙을 150px 로
  올린 뒤 **어떤 케이스도 판별하지 못했다**(뮤턴트 생존). 남겨두면 "방어가 있다" 는 착각만 준다.
- **관리 콘솔은 손대지 않았다** — 같은 압박(8장)을 받지만 `minmax(160px)` 로 이미 안전함을 실측
  확인했다(420~1400px 넘침 0). 하네스에 축만 남겨 미래 회귀를 잡는다(§8.1 — 제안은 기록만).

### 잔여

- 드로어를 320px 미만으로 줄이면 1열에서도 라벨이 ellipsis 될 수 있다. 그 폭은 드로어 리사이즈
  하한 밖이라 검사에 넣지 않았다.
## REV-20260814T040000-attach-createdat-utc [CODEX:adversarial-data-migration] — 첨부 시각 UTC 정정

- Related Change: `CHG-20260814T040000-ai-claude-feature-0003-attach-createdat-utc`
  (REQ-20260814-attach-createdat-utc, 위험등급 **Major §12.3** — 되돌리기 어려운 데이터 마이그레이션).
- Trigger (§18.8 dispatch): `schema/query/마이그레이션` → **backend + qa** 렌즈. 세션 지시로 Agent
  도구 미사용 → §18.9 대체 채널 **codex CLI**.
- 집행: staged diff 를 codex 가 직접 읽고 5축(이중 차감 가능성·상한 정확성·PG 산술과 부분 실패·
  −9h 이동이 깨뜨리는 다른 소비자·offset0/max_id0 처리) 적대 검증. **[P1] 3 · [P2] 1** → 전건 반영.
- **가장 중요한 적발**: 다중 replica 동시 startup 에서의 **이중 차감**. 이 배포는 web-a/web-b 롤링이라
  실재하는 경로였고, 기존 backfill 들의 "SELECT 확인 → 작업" 관행을 그대로 따랐기 때문에 생겼다.
  다른 backfill 은 `INSERT IGNORE` 라 재실행이 무해했지만 **이 작업은 차감이 누적**되어 성격이 다르다.
- **초판 주석의 사실 오류 정정**: "PG 미러 실패는 다음 갱신에서 정정" 이라 적었으나, 미러 upsert 가
  `created_at` 을 갱신하지 않아 성립하지 않는다(codex 가 `attachment_pg_mirror.py` 로 반증).
- 무결 확인(codex): PG `timestamptz - make_interval` 산술 · 빈 테이블 마커 기록 · 보존(DeletedAt 기준)·
  quota(크기 기준)·첨부 페이지 커서 부재 → 추가 결함 없음.
- 검증: `tests/test_attach_createdat_utc.py` **12 PASS**(선점·반납·상한 선확정·서버 오프셋·저장소별
  마커·전송 표기 전부 고정). 전체 스위트 회귀 확인.
- 한계(정직): 실제 차감은 **배포 시 1회** 일어나므로 사전 실측이 불가능하다. 배포 후 모순 건수
  (`CreatedAt > SupersededAt|DeletedAt`)가 **234 → 0** 인지, MySQL↔PG 미러가 일치하는지로 확인한다.

## REV-20260813T225000-ai-claude-corp-usage-card-overflow-postdeploy [SKIPPED:non-policy-doc] — 실측 기록

doc-only. 라이브 드로어 폭 6단계 실측으로 선행 두 커밋의 이월을 종결한다. 근거는 실 Chrome 관측이다.
## REV-20260814T120000-profile-sort-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록
- Related TASK: feature-0003-agent-web-ui
- Reason: changed paths are docs + evidence image only (no code, no policy doc)
- Timestamp: 2026-08-14T12:00:00+09:00
## REV-20260814T060000-attach-version-tree-ui [CODEX:adversarial-ux-authz] — 버전 비교 축 토글

- Related Change: `CHG-20260814T060000-ai-claude-feature-0003-attach-version-tree-ui`
  (REQ-20260814-attach-version-tree-ui, 위험등급 **Major §12.3**).
- Trigger (§18.8 dispatch): UI/form → ux · 신규 비교 경로 = 본문 노출 인가 표면 → security+backend.
  세션 지시로 Agent 도구 미사용 → §18.9 대체 채널 **codex CLI**.
- 집행: staged diff 를 codex 가 직접 읽고 5축(인가·존재 oracle·축 전환 stale·select 값 타입 변경의
  다른 소비자·진입 조건 완화의 안전성) 적대 검증. **[P1] 1 · [P2] 4** → 전건 반영.
- **가장 중요한 적발**: 기능을 만들어 놓고 **거기에 도달하는 버튼을 열지 않았다**. 모달 진입 조건만
  고치고 버튼 노출 조건을 그대로 둬, 이 변경이 겨냥한 대표 시나리오(사용자 v1 ↔ AI v1)가 화면에서
  닿을 수 없었다. 하네스 18건이 전부 통과하는 상태였다 — **모달 안쪽만 검증했기 때문**이다.
  진입점까지 테스트 범위에 넣지 않으면 "동작하지만 쓸 수 없는" 기능이 통과한다.
- 무결 확인(codex): pending(D21) 차단이 side 조회 전에 적용 · `.own/.any` 헬퍼가 양쪽에 각각 호출 ·
  타 대화 id 는 존재/권한과 무관하게 404 로 수렴(oracle 없음).
- 검증: `verify_attach_version_tree_ui.mjs` **24 PASS**(A 노출조건 4 · B 축 전환 6 · C 요청 파라미터 2 ·
  D 배선/구조 6 · **E 적대리뷰 반영 6**) · `test_attach_version_branching.py` 14 PASS.
- 한계(정직): jsdom 은 레이아웃·픽셀을 보지 못한다. 토글이 좁은 폭에서 접히는지, 축 전환 시 표가
  튀지 않는지는 **배포 후 PB-0008** 대상이다.
## REV-20260814T183000-step-panel-timing [SUBAGENT:ux+frontend] — 실행 단계 패널 시간 표기

- Related Change: `CHG-20260814T183000-ai-claude-corp-feature-0003-step-panel-timing`
  (실행 단계 패널 단계별 시각·간격·누적 표기, 위험등급 **Minor §12.3**).
- Trigger (§18.8 dispatch): UI/layout/화면 표기 → ux · 프론트 렌더러/폴링 재렌더 경로 → frontend.
  Agent 도구 가용 → 표준 SUBAGENT 채널(6렌즈: 정확성·파싱·레이아웃·회귀·성능·테스트 검출력).
- 집행: staged diff + 정본 소스를 subagent 가 직접 읽고 **실측 기반** 검증 — V8 로 파싱 12변형
  실행, headless Chromium 300px 실 CSS 렌더 계측(겹침 0·overflow 0·flex-wrap 하강 후 우측
  정렬 유지), 뮤턴트 3종 실제 실행. **P1 0 · P2 1 · P3 6**.
- **가장 중요한 적발(P2-1)**: 기존 fixture 는 레거시 단계가 항상 마지막이라 "NaN 뒤 유효 단계"
  분기(NaN-skip 스캔·anchor-find)가 한 번도 실행되지 않았고, 그 분기를 제거한 뮤턴트 2종이
  30 PASS 전체를 통과했다 — **분기를 지키는 시나리오가 fixture 에 없으면 테스트는 그 분기의
  부재를 감지하지 못한다**. → NaN 혼재 케이스 추가, 3종 뮤턴트 사멸 실증(각 1 FAIL). 34 PASS.
- 반영: P2-1(fixture 보강) · P3-4(Intl 포매터 모듈 상수 hoist — 폴링 재렌더 경로 ~90μs/단계
  실측) · P3-7(첫 단계 툴팁 조건화). 수용 기록: P3-1(60초 이음새 — 기존 선례 일치) ·
  P3-3(MySQL naive datetime — ADR-0028 dead-code) · P3-5(muted 대비 3.84:1 — 인접 기존 토큰
  동일 · LIGHT-ONLY 확인) · P3-6(시계 역행 — 실현 경로 부재, 방어 코드).
- 무결 확인: 파싱(마이크로초 6자리·오프셋 변형 "+00"/"Z"/초단위 전부 정상, NaN 전파 없음 —
  전 산출 Number.isFinite 게이트) · 회귀(스크롤 보존 29 PASS 재실행 · 펼침 영속화 키 불변 ·
  compact 경로 분리) · 성능(prevTs 스캔 amortized O(n) — 각 NaN 칸은 정확히 1회 방문).
- 한계(정직): jsdom·headless 는 실제 폴링 갱신 리듬과 라이브 run 을 보지 못한다 — 라이브 run
  진행 중 표기 갱신·과거 대화 소급 표기는 **배포 후 PB-0008** 대상(TEST.md 확인 축 ①~④).

## REV-20260814T192000-step-panel-timing-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 0 — 변경분은 PB-0008 검증 시나리오 2종(브라우저 검증 하네스 전용,
사용자에게 서빙되지 않음)과 `TEST/TASK/MODIFY` 기록뿐이다. §18.8 dispatch 표의 "비정책 doc-only"
행에 해당해 panel 을 SKIP 한다. 이 cycle 이 검증하는 **제품 코드 자체는 선행 cycle 에서 이미
패널을 거쳤다** — `REV-20260814T183000-step-panel-timing [SUBAGENT:ux+frontend]` (P1 0 · P2 1 반영 ·
P3 6 중 3 반영). 선례: `REV-20260814T120000-profile-sort-postdeploy [SKIPPED:non-policy-doc]`.

**판단 근거(검증의 질)**: SKIP 이 "확인을 덜 했다" 가 되지 않도록, 이번 실측은 다음을 기계 판정으로
잠갔다 — ① 시각 표기 형식 정규식(1번째 시각만 / 이후 `시각 · +간격 · 누적`) ② 기하(헤더 우변 대비
편차·넘침·형제 겹침) ③ computed CSS 계약(`margin-left:auto` 해소·`nowrap`·`tabular-nums`·
`flex-shrink:0`·헤더 `flex-wrap:wrap`) ④ 리사이저 실제 드래그로 최소 폭 클램프·영속 ⑤ 라이브
폴링에서 누적 단조성. 시나리오 step 이 기대와 어긋나면 실패하므로 재실행 가능한 게이트다.

**수용한 한계(정직)**: ② 최소 폭 300px 에서 실 데이터는 아직 한 줄에 들어가므로, 줄바꿈 계약은
도구 배지를 길게 만들어 **경계를 강제**해 확인했다(겹침 0·넘침 0·top 2→25px 하강). 실사용 데이터로
그 경계에 닿는 사례는 아직 관측되지 않았다 — 계약이 지켜진다는 것만 확인했고 "현재 겹치고 있다" 는
주장은 하지 않는다.

## REV-20260814T183000-attach-new-marker-rehydration [CODEX:cross-ref] — 재수화 보존 + 전송 강등 (프론트 축)

- Related Change: `CHG-20260814T183000-attach-new-marker-rehydration`(cross-ref) — 정본 판정·라운드
  전문은 feature-0002 `REV-20260814T183000-attach-change-signal-server-authority`.
- Trigger: §18.8 — 프론트 축이 같은 changeset 에 포함(`composer.js`). 적대 검증은 changeset 전체를
  대상으로 codex 5 라운드로 집행했고, 그중 프론트 지적 4건(R2 [P1] lazy-create 강등 누락 · R4 [P1]
  응답 시점 활성 대화 오강등 · R5 [P1] 전송 스냅샷 밖 id 강등 · R1 계열 없음)을 전건 수정했다.
- Verdict: **PASS** · Timestamp: 2026-08-14T19:55:00+09:00
- 검증: 구조 가드 **7 PASS**(뮤테이션 KILLED) + **PB-0008 라이브**
  (`docs/test-runs.d/REV-20260814T183000-attach-change-signal.md`) — 1턴 `[1203]` → 2턴 `[]` →
  대화 전환 왕복 후 `[1204]`. 라이브 서비스 무접촉(격리 컨테이너), 검증 대화·첨부는 삭제 완료.
- Human Approval Needed: 아니오 (구현 범위 승인 완료 · PR/배포는 feature-0002 cycle 에서 confirm).

## REV-20260817T010301-doc-sync-rn-0817 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-08-16 · 2026-08-14 블록 신규 prepend(18항목) doc_sync 정합

- Related TASK: feature-0003-agent-web-ui / `20260817T010301-doc-sync-rn-0817`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + 그 companion 문서).
- Timestamp: 2026-08-17T01:03:01+09:00
- Human Approval Needed: no

- **타깃별 실질 검증**: `node --check` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 34/0 동일 = 회귀 0) · 구조 단언(블록 48→50 · `releases[0].date`=="2026-08-16" items 1 · `releases[1].date`=="2026-08-14" items 17 · `generated`==`releases[0].date` · 기존 48 블록 **바이트 동일**(편집 전 파일과 `date: "2026-08-13"` 이후 tail 정확 일치) · type/area enum 위반 0 · 스키마 외 키 0 · date 내림차순 정상 — 말미 `label` 블록은 선재 설계상 정상).
- **블록 date 판정**: 델타 창(`6d4fdd87`..HEAD) 어떤 커밋도 `release-notes-data.js` 를 건드리지 않아 편집 전 top 블록이 `date: "2026-08-13"` · `generated: "2026-08-13"` 이었다 → 직전 run 이 적용한 "owning feature self-add 블록에 append" 규칙은 성립하지 않고 **신규 블록**이다. 배포일이 08-14(담당 55커밋)·08-16(`a639272c`·`65c34fff`) 둘이므로 블록도 2개로 갈랐다. `a639272c` 는 author-date 08-14 이나 committer-date·머지(PR #1315 → main `0f784df3`)·배포가 모두 08-16 이라 정본 `unit/feature-0002-agent-core/docs/REPORT.md` 의 배포 기록으로 교차확인해 **rnDate=2026-08-16** 으로 확정했다.
- **배포 게이트 = 물리 실측으로 판정**(정본 문면이 아니라 라이브): 컨테이너 6종 전부 `:6c7413cf` = HEAD = origin/main 이므로 18항목의 근거 커밋 전건이 배포본에 포함. 서빙 static sha 파리티 정확 일치 · `/healthz` 200 → **유보 항목 0**.
- **정본 재확인으로 걸러 낸 허위 위험 3건**(누락이 허위보다 낫다):
  - 정본이 **서로 다른 두 사건에 동일한 '23분'** 을 기록한다 — `unit/feature-0002-agent-core/docs/FUNCTION.md:575`(조기 종료: 45초 폴링 × 23분, 사용자 수동 취소) 와 `:1176`(상한 초과 폐기 후 재시도 성공까지 23분). 두 항목에 같은 수치를 실으면 같은 사건의 중복 서술로 읽히므로 스트리밍 항목에만 남기고 조기 종료 항목은 수치 없이 "직접 취소하실 때까지" 로 적었다.
  - **첨부 `CreatedAt` 로컬→UTC 전환(`7ed68803`)은 사용자향 항목에서 제외**. 정본 TASK 의 적대 리뷰 ④ 가 "저장만 UTC 로 옮기면 화면 시각이 9시간 이르게 뜬다 → 전송 계약도 함께 이동" 을 같은 커밋에서 처리했으므로 **화면 표시 시각은 수정 전후가 동일**하다. 해소된 것은 라이브 모순 행 234건 등 내부 정합이고 사용자 보고도 없다.
  - **surge 교대 배포(`d1501b68` 계열)의 '배포 중 진행 중이던 답변이 완주한다'** 는 정본 POST-DEPLOY 가 "배포 시점 running=0(유휴)이라 그 궤적은 아직 미관측 · 내려간 본체는 구 이미지라 구 drain 시맨틱으로 동작" 이라고 **미관측을 명시**했다. 라이브 실증되지 않은 체감 주장이라 제외.
- **선행 블록과의 중복 회피**: ⑨(타 멤버 첨부 본문 턴의 작업공간 쓰기 제한)는 2026-08-13 블록의 "다른 사람이 올린 파일의 내용은 지시가 아니라 자료로만 다루도록 못박았습니다" 와 **다른 층**(프롬프트 계약 vs 도구 실행 차단)이므로 별도 항목으로 두되 그 문면을 재서술하지 않았다. 이미지·csv/xlsx 축 확장(`582001db`/`88ad8619`)은 같은 게이트의 커버리지 확장이라 별도 항목이 아니라 ⑨ 의 한 문장으로 흡수했다. 08-16 항목은 2026-08-05 블록의 "이어받은 대화에서 새로 올린 첨부 파일을 '변경된 것이 없다'고 답하던 문제" 의 **후속 층**(그 봉인의 4축이 전부 클라이언트 신호 하나에 걸려 있었다)이므로 증상 조건(대화 전환·패널 조작·새로고침)을 명시해 갈랐다. 부하 게이트 코칭 정정(`25637d1c`)은 2026-07-24 블록의 동일 영역 항목과 겹치고 모델 입력 축이라 제외.
- **한계·정직 표기를 사용자 문면에 남긴 항목**: 08-16 항목에 수용 한계 2건(공유창 확대 시 옛 파일 과표시 · 계약 도입 이전 대화의 첫 차례 과표시 후 자기 치유)을, ⑪ 에 "상대 쪽에서 아무것도 보내오지 않는 구간은 종전과 같이 정해진 시간까지 기다린다"(정본 AC-4 채택 한계)를, ⑫ 에 "데이터베이스에 연결할 수 없을 때 진행을 멈추는 것 자체는 종전의 안전 장치"(2026-08-07 사용자 판단 불변)를, ②·③ 에 범위 밖 명시(가지 그림 미제작 · 인라인 진행 카드 무접촉)를 실었다.
- **포함/제외 판정**: 델타 창 non-merge 57 커밋 중 사용자 체감 변화 18항목 채택(근거 커밋 44건). 제외는 문서 정합(`6d79e60c`)·조사/검증 판정(`63808675`/`47b5c891`, 런타임 코드 0)·템플릿 5 hop·LEARNINGS(`3b4ff365`)·POST-DEPLOY 증적 전용 커밋 다수.
- **테스트 env**: 무인 cron(WSL2 컨테이너 호스트). `verify_release_notes.mjs` 는 `unit/feature-0003-agent-web-ui` 에서 실행(jsdom `/tmp/node_modules`). PB-0008 은 TEST.md 에 미수행 사유·대체 검증 명시.
- **cache-buster**: 수기 bump 없음. 소스 `?v=dev` placeholder 고정 + Dockerfile `inject_asset_stamp.py` 빌드 주입 + `bin/deploy-web.sh:1320` 이 placeholder 잔존 시 배포 ABORT(2026-07-12 ITEM-09). 라이브 실측 토큰 `?v=7e6a0de6e2c6`. `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유(이중 landing/배포 racing 방지). 서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.

## REV-20260819T010301-doc-sync-rn-0819 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-08-14 블록 누락 1항목 append(17→18) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260819T010301-doc-sync-rn-0819`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + 그 companion 문서).
- Timestamp: 2026-08-19T01:03:01+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · 구조 단언(`releases` 50 **불변** · `generated`=="2026-08-16"==`releases[0].date` · `releases` 내 `2026-08-14` 블록 items 17→**18**(area work 11 · admin 3 · common 4 / type new 7 · improved 3 · fixed 8) · 스키마 외 키 0 · **`date: "2026-08-13"` 이후 tail 바이트 정확 일치** · `generated` 이전 head 바이트 정확 일치 → 편집이 08-14 블록 내부로 완전 국소화) · 내부용어 누출 0(정규식 기계 검증).
- **검증 한계 정직**: `tests/verify_release_notes.mjs` 는 스크립트 :21 이 `require("/tmp/node_modules/jsdom")` 를 하드코딩하고 이 환경에 그 경로가 없어 **실행 불가**(MODULE_NOT_FOUND). 직전 run 이 기록한 baseline 34 pass / 0 fail 은 **이 세션에서 재확인하지 못했다** — DOM 렌더·그룹 수·접힘 기본값·필터 카운트·XSS 이스케이프 축은 미검증이며, 대신 위 구조·문법·국소성 검증으로 대체했다. 스키마·필드 구성이 기존 항목과 동일하고 렌더 로직 델타가 0 이므로 렌더 경로 회귀 위험은 낮다고 판단했으나, 보증한다고 쓰지 않는다.
- **date 내림차순 판정**: dated 블록 50개의 순서 검사는 `false` 로 나오지만 이는 **선재 조건**이다 — 말미 블록의 `date` 가 문자열 `"이전"` 인 설계상 label 블록이라 정렬 비교에서 뒤로 밀린다. 편집 전(HEAD) 파일에서 동일하게 `false` 이고 date 목록이 편집 전후 **완전 동일**(블록 추가 아님)임을 실측해 본 변경 무관을 확인했다.
- **블록 귀속 판정**: 항목의 배포일이 08-14 이고 그 date 블록이 이미 존재하므로 doc_sync Phase 3 규약대로 **기존 블록 append**(신규 블록·`generated` 변경 금지). 직전 `doc-sync-rn-0817` 이 같은 창 18항목을 적재하며 이 1건을 놓친 prior-window 누락의 보충이다.
- **cache-buster**: 수기 bump 없음. 소스 `?v=dev` placeholder 고정 + 빌드 `inject_asset_stamp.py` content-hash 주입 + `bin/deploy-web.sh` 가 placeholder 잔존 시 배포 ABORT(2026-07-12 ITEM-09). `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유(이중 landing/배포 racing 방지). **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.**

## REV-20260820T010301-doc-sync-rn-0820 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-19 블록 prepend(1항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260820T010301-doc-sync-rn-0820`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + 그 companion 문서).
- Timestamp: 2026-08-20T01:03:01+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · 구조 단언(`releases` 50→**51** · `generated`=="2026-08-19"==`releases[0].date` · top items 1 · 2nd 08-16 items 1 불변 · 3rd 08-14 items 18 불변 · 스키마 외 키 0 · type/area enum 기존 집합 내) · **`tests/verify_release_notes.mjs` 34 pass/0 fail = 편집 전 baseline 34/0 동일 → 회귀 0**(jsdom@24 핀 설치로 실행 — 직전 run 의 '미실행' 한계 해소) · 내부용어 누출 0(정규식 기계 검증).
- **적대검증**: ULTRACODE 워크플로 `wf_50a93244-10c`(8 에이전트 / 974,736 토큰 / 354 tool-use) RN 축 confirmed=true. 검증자 MINOR 2건은 오케스트레이터가 정본에서 독립 재검증해 **전건 반영** — ① "이 안내가 붙은 답변 33건" 은 정본 FUNCTION.md §7.6 의 33(결함 잔존 전달 내역)을 '고지 부착 수' 로 오단정 → "짚인 것이 남은 채 전달된 답변 33건" 으로 정정, ② 고지 규칙 무변경 단정을 완화. 추가로 오케스트레이터가 **분량 초과를 자체 적발·축약**(제안 detail 851자 > 기존 max 714 → 404자, summary 574→285자).
- **블록 귀속 판정**: 대상 머지 `4af53e37`(PR #1317 · merge `22423bd5`)의 커밋일 08-19 에 해당하는 date 블록이 파일에 **부재**(grep 0회)이므로 신규 블록 prepend + `generated` top-block 연동(기존 블록 append 아님). 오늘(08-20) 날짜 블록·publish-date 신설 금지 규약 준수.
- **배포 게이트**: 라이브 이미지 `mysql-ai-agent:22423bd5`·`mysql-ai-web:22423bd5` == HEAD ⊃ 그 머지 → 항목 내용이 이미 서빙 중(유보 없음).
- **RN 제외 판정(정직)**: 창 내 나머지 커밋은 전부 RN 비대상 — `7e30ef13`·`d4a73338`·`74316049`·`920e7974`(doc_sync 산출) · `65c34fff`(배포 기록 doc-only) · `a639272c`(첨부 변경-인지)는 **이미 08-16 블록 1항목에 반영됨**. backfill 누락 추가분 **0**.
- **cache-buster**: 수기 bump 없음(ITEM-09 — 소스 `?v=dev` 고정 + 빌드 content-hash 주입 + 배포 ABORT 가드). `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유(이중 landing/배포 racing 방지). **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.**

## REV-20260824T115000-step-timing-attribution [CODEX:adversarial-timing-attribution] — 단계 시간 귀속 재정의

**Trigger**: Code change — dispatch 키워드 `UI/화면/layout`(실행 단계 패널 렌더) + `performance/성능`
(시간 계측). §18.8.1 대체 경로인 codex 적대 리뷰로 수행(세션에 "요청 없이 Agent 호출 금지"
지시가 있어 채널을 사용자에게 1회 확인 후 선택 — 자체 SKIP 하지 않았다).

**결과: [P1] 0 · [P2] 5 — 전건 반영.**

1. **시각 없는 중간 단계를 건너뛰고 정확한 척** — `activity → (created_at 없는 단계) → tool` 에서
   그 중간 단계가 쓴 몫을 알 수 없는데 `gap − nextTool` 전부를 activity 에 귀속했다. 테스트 F 도
   그 값을 정답으로 고정하고 있었다. → 건너뛴 기록이 있으면 `approx=true`. 테스트에 축 추가.
2. **레거시 `도구→도구` 를 "정확" 으로 확정** — 두 기록 시각의 차이에는 step 저장·로깅·다음 호출
   준비 같은 도구 밖 시간이 섞인다(실행시간의 **상한**). → `approx=true` 로 정직화.
3. **시계 역행 시 누적 감소 · 시작 시각 역전** — `0 → 10초 → 5초` 같은 입력에서 누적이 줄고,
   `elapsed_ms > 기록 간격` 이면 도구 시작이 직전 단계 종료보다 과거가 됐다. 단조성 테스트가
   정상 시계만 봐서 놓쳤다. → 누적 running-max + 시작 시각을 직전 종료로 clamp. 축 2개 추가.
4. **`Number(null) === 0`** — `elapsed_ms` 가 `null`/`""`/`false` 면 값 없음이 "0.0초 로 측정됨"
   으로 둔갑했다. 기존 테스트는 키 부재와 음수만 봤다. → 숫자 타입 검사. `0` 은 살리고 `"430"`
   문자열은 거른다(생산자가 언제나 int 이므로 관대할 이유가 없다). 축 2개 추가.
5. **성립하지 않는 주장** — 주석·테스트·문서가 "예외로 끝난 도구도 step 소요 보존" 이라 했으나,
   `execute_tool` 이 raise 하면 예외가 전파돼 `_build_step_payload`/`_mirror_step` 에 닿지 않아
   **step 기록 자체가 없다**. `finally` 가 지키는 것은 `_inf_add_tool` 누산(duration_breakdown)뿐.
   또 AST 테스트가 **아무 finally** 에 변수명만 있으면 통과했다. → 주장 정정(주석·docstring·
   MODIFY·FUNCTION·TEST) + AST 검사를 `execute_tool` 을 본문에 가진 try 로 한정. 뮤턴트로 재검증.

**반영 후 재검증**: 프론트 70 PASS(+5 축) · 백엔드 23 PASS · 프론트 뮤턴트 **10종**·백엔드 **3종**
전건 사멸 · `verify_step_result_scroll_preserve` 29 PASS 무회귀.

**남긴 판단(정직)**: 5번은 "예외 도구도 step 을 남기게" 고칠 수도 있었지만 하지 않았다 — 그것은
run 의 기록 의미를 바꾸는 별건이고(이 변경 이전부터의 동작), 이번 요청은 시간 **표시**의 오귀속
해소다. 사실과 어긋나던 **주장** 쪽을 고쳤다.

## REV-20260824T130000-step-timing-attribution-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 0 — 변경분은 PB-0008 검증 시나리오 1종(브라우저 검증 하네스 전용,
사용자에게 서빙되지 않음)과 `TEST/TASK/MODIFY` 기록뿐이다. §18.8 dispatch 표의 "비정책 doc-only"
행에 해당해 panel 을 SKIP 한다. 검증 대상 제품 코드는 선행 cycle 에서 codex 적대 리뷰를 거쳤다
(`REV-20260824T115000-step-timing-attribution [CODEX:...]`, [P1] 0 · [P2] 5 전건 반영).
선례: `REV-20260814T120000-profile-sort-postdeploy`.

**이번 실측이 새로 잡은 것(정직)**: 확대 캡처 오버레이가 `document.body` 에 붙지 않아
**단언은 통과하는데 스크린샷에는 오버레이가 없던** 상태를 발견해 고쳤다. detached 노드에서도
`querySelectorAll` 이 개수를 맞게 돌려주는 탓이다 — "캡처를 남겼다" 와 "캡처가 근거가 된다" 는
다르다는 사례로 TEST.md 에 남겼다.

## REV-20260824T142000-stale-threshold-attempt-cap [CODEX:backend+ux-adversarial] — stale 임계 파생 + 마지막 활동 정직화

**Trigger**: `UI/화면` (사이드바 stale 툴팁·대화 부제 표시) + `API/응답 스키마`
(`/api/conversations` payload 신규 필드 `last_activity_effective_at`, `/api/progress` 판정 호출부)
키워드 매칭 → dedupe 시 backend+security+qa+ux+design = **full panel** 대상. 본 세션은 AgentTool
사용이 금지돼 subagent 5인 dispatch 가 불가하므로, §18.8.1 이 check #9 **accepted review** 로
인정하는 **codex 채널**로 대체했다(§18.8.2 제약-없는-채널 우선. 선례:
`REV-20260730T160000-ask-redeploy-handoff`, `REV-20260824T115000-step-timing-attribution`).
scope: `git diff --cached` 전량, `model_reasoning_effort=high`, read-only sandbox.

**결과**: **[P1] 1건 · [P2] 3건 → 전건 흡수**(반영 후 [P1] 0). 2값 언패킹 잔존 0 · 구 payload
필드 부재는 JS 폴백으로 처리됨 · `pendingStatusLabel` 호출 위치 유효 — 세 축은 지적 없음.

1. **[P1] 판정이 상한의 *하락*을 즉시 따라간다** — 1800초로 시작한 호출이 대기하는 중 운영자가
   상한을 60초로 낮추거나 스냅샷 조회가 실패하면 임계가 1200초로 돌아가, **봉인하려던 그 사고가
   그대로 재현**된다. 진행 중 호출은 시작 시점 상한으로 대기하기 때문이다(그 값이
   `_TIER_CLIENT_CACHE` 의 client timeout 에 박혀 있다).
   → **흡수**: 프로세스 수명의 **high-water mark**(`_STALE_CAP_HIGH_WATER`)를 기준으로 삼는다.
   상승은 즉시 반영, **하락은 재기동 경계에서** 반영(그 시점엔 옛 상한으로 대기 중인 호출도 없다).
   조회 실패도 high-water 를 유지해 fail-open 이 오표시를 만들지 않는다.
   **채택하지 않은 대안**: codex 가 제안한 "attempt 시작 시 cap/deadline 을 run 메타에 저장" 이
   더 정확하지만 KV 스키마와 워커 쓰기 경로를 건드려 이 cycle 의 응집 한계를 넘는다. high-water 는
   같은 오표시 창을 표시 계층 안에서 덮는다(정확도-비용 트레이드오프를 기록으로 남긴다).
2. **[P2] clamp 부재** — 콘솔 override 는 스펙 [5,3600] 으로 clamp 되지만 **배포 env baseline 은
   clamp 되지 않는다** → 비정상적으로 큰 `AGENT_TIMEOUT_SEC` 이면 임계가 수년으로 늘어 stale 이
   사실상 영구 미보고(가드 무력화). → **흡수**: `_STALE_CAP_CLAMP_MAX`(스펙 maximum 을 권위로,
   조회 실패 시 3600) 로 clamp + `WEB_PROGRESS_STALE_MARGIN_SECONDS` 도 상한 clamp.
3. **[P2] terminal 상태에서 `last_active=None`** — 완료·오류·취소 대화는 신규 필드가 항상 비어
   표면이 다시 요청 접수 시각으로 폴백 → "실제 마지막 활동" 계약이 processing 에서만 성립하는
   비대칭. → **흡수**: terminal 도 `last_status_at`(마감 시각)을 돌려준다. `_compute_display_status`
   의 terminal 경로는 **step 조회를 하지 않는다**(PG 왕복 불변 — 테스트가 조회 시 실패로 잠금).
   인자형 경로는 step 시각을 이미 받았으므로 둘의 max.
4. **[P2] `_parse_kv_timestamp` 가 offset 을 UTC 변환 없이 strip** — `…T12:00:00+09:00` 을
   `12:00Z` 로 오인해 9시간 미래가 된다. stale 판정이 그만큼 지연되고, 내 신규 직렬화가 그 값을
   "UTC" 로 명시해 내려보내면 **사용자에게도 9시간 틀린 시각**이 보인다. `_last_step_at_for_run`
   의 CHG-20260527-0001 회귀와 같은 부류(그때 step 축, 이번 KV 축). → **흡수**: aware 는
   `astimezone(utc)` 후 naive 화. 라이브 KV 는 현재 `+00:00` 저장이라 실동작 변화 0(실측 확인) —
   저장 형식이 바뀌어도 깨지지 않게 하는 방어다.

**반영 후 재검증**: 관련 3파일 **42 PASS**(신규 19 · 흡수분 6종 테스트 추가 — 하락 무반응 ·
실패 시 high-water 유지 · 비정상 cap clamp · 경계 bound · offset→UTC 4케이스 · terminal 반환
2경로) · 전체 스위트 회귀 확인 · ruff clean.

**남긴 판단(정직)**: high-water 는 **프로세스 전역 상태**라 테스트가 오염되면 실행 순서 의존
flake 가 된다 → 신규 테스트에 autouse fixture 로 저장·리셋·복원을 걸었다. 그리고 상한을 한 번
크게 올렸다 내리면 재기동까지 임계가 보수적으로 남는다 — 표시 판정이므로 수용하고, 진짜 죽은
run 은 `ask_jobs` terminal backstop(`FR-early-return-kv-never-finalized` 봉인 B)과 워커 stale
sweeper 가 별도로 잡는다.

## REV-20260824T152000-stale-threshold-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 **0** — 변경분은 원장 status 전환과 `TASK/MODIFY` 기록뿐이다.
§18.8 dispatch 표의 "비정책 doc-only" 행에 해당해 panel 을 SKIP 한다. 검증 대상 제품 코드는
직전 cycle 에서 codex 적대 리뷰를 거쳤다(`REV-20260824T142000-stale-threshold-attempt-cap`
`[CODEX:backend+ux-adversarial]`, [P1] 1 · [P2] 3 전건 흡수 → 반영 후 [P1] 0).
선례: `REV-20260824T130000-step-timing-attribution-postdeploy`.

**이번 실증이 새로 확정한 것**: 봉인이 "코드에 있다" 와 "라이브에서 선다" 는 다르다 —
배포본 web-a 에서 실 모듈을 import 해 **`threshold_live=1980` > `cap_live=1800`** 을 직접
읽었다(사고 당시 1200 < 1800). 임계는 상수가 아니라 live 설정 파생이므로, 이 한 줄이
"배포됐다" 보다 강한 증거다. 반대로 **라이브 UI 실측은 못 했다**(stale 표면 재현이 데이터
write 를 요구) — 미검증을 검증으로 적지 않고 원장 관측 지표로 이월했다.

## REV-20260824T164437-sidebar-reorder-anim [CODEX:frontend-adversarial] — [P1] 1 · [P2] 4 전건 흡수 → 재실행 [P1] 0

**Trigger**: `UI/화면/레이아웃` keyword matched (§18.8 dispatch 표 — UI/버튼/페이지/모달/화면/
레이아웃 → ux, design). 본 세션에는 "요청 없이 subagent 를 호출하지 말라" 는 도구-사용 제약이
걸려 있어 §18.8.2 의 해소 순서대로 **제약 없는 채널**(codex, subagent 호출 아님)로 수행했다 —
검증 착수는 confirm 대상이 아니고(§18.8.2), 위임된 작업의 완료 조건이므로 자체 SKIP 도 하지 않았다.
판정 기준은 `docs/CODE_REVIEW.md`(§18.8.1 주의) 대신 codex 기본 판정 + 본 cycle 의 위험 축을
프롬프트로 실어 보냈다(예약 누수 · 측정/스크롤 순서 · 접힘 선호 · 인라인 스타일 잔류 · 리플로우 ·
기존 렌더 회귀). codex 는 `git diff --cached` 를 직접 읽고 저장소 하네스까지 실행했다.

### 지적과 처리 (전건 흡수)

- **[P1] 예약이 목표 렌더가 아니라 "다음 아무 렌더" 에 소비된다.** 제목 PATCH 후 예약을 걸고
  `refreshWorkspace` 를 시작하는데, 그 왕복 동안 사용자의 그룹 토글이나 진행 중이던 unread 갱신이
  먼저 `renderConversationList()` 를 호출하면 그 렌더가 예약을 비워, 정작 재배치가 드러나는 렌더는
  전환 없이 순간이동한다. **타당하다** — 목록 데이터 갱신과 렌더가 1:1 이 아니라는 사실을 설계가
  놓쳤다. → 예약을 **데이터 버전**(`state.sidebarDataVersion`)에 귀속시켰다. 버전이 오르지 않은
  렌더는 예약을 그대로 남기고, 만료(TTL)만 정리한다. bump 지점은 데이터가 실제로 교체되는 3곳
  (`loadConversations` · `loadFolders` · 주기 unread 동기화)이며, 그 중 어느 것이든 재배치를 담은
  렌더이므로 애니메이션 대상으로 적격이다.
- **[P2] 자동 접힘 해제가 사용자 선호로 영속된다.** 시야 유지를 위해 목적지 조상을 펼치는 것
  자체는 필요하나 `_saveCollapsedGroups()` 까지 불러 localStorage 를 덮어썼다. **타당하다** —
  "지금 이 항목을 보이게" 하는 세션 조치와 "이 그룹을 펼쳐두고 싶다" 는 선호를 혼동했다.
  → 세션 상태에서만 해제하고 영속은 명시적 토글에만 남겼다.
- **[P2] `transitionend` 가 자식에서 버블링해 FLIP 을 조기 종료.** 이동 중 포인터가 지나가며
  메뉴 트리거의 opacity 전환이 끝나면 부모 리스너가 실행돼 행이 최종 위치로 튄다. **타당하다**
  → `ev.target === el && propertyName === 'transform'` 만 인정 + 리스너 명시 해제.
- **[P2] 정리 watchdog 이 rAF 이후에만 설치된다.** invert 직후 탭이 백그라운드로 가면 rAF 가
  오지 않아 `transition:none` + `translateY(...)` 가 영구 잔류한다. **타당하다** →
  `_armReorderCleanup` 을 invert 적용 시점에 설치.
- **[P2] 강조색 하드코딩.** → `color-mix(in srgb, var(--accent, #2563eb) 22%, transparent)`.
  (주변 `.conv-item` 규칙에도 `rgba(37,99,235,…)` 하드코딩이 남아 있으나 본 cycle 범위 밖 —
  신규 코드만 토큰 기반으로 맞췄다.)

### 봉인의 실효 확인 (뮤테이션)

각 봉인을 되돌리는 뮤테이션 4종을 넣어 하네스가 **전건 red** 임을 확인했다: 데이터 버전 게이트
제거(3 FAIL) · 자동펼침 영속화(3) · transitionend 필터 제거(2) · watchdog invert-시점 제거(4).
초기 5종(예약 1회소비 · 조상 펼침 · 시야 보정 · 스크롤 복원 · reduced-motion 게이트)과 합쳐
9종 전건 KILL. 하네스 73 → **93 PASS**.

### 리뷰가 아니라 **라이브 실측**이 잡은 것 (기록 가치)

[P1] 수정 직후 폴더 경로의 애니메이션이 조용히 사라졌다. `_commitFolderRename` 이 `loadFolders()`
(= 버전 bump) **뒤에** 예약해 자기 갱신을 이미 지나쳤기 때문이다. 하네스는 "예약이 PATCH 성공
경로에 있다" 만 검사했고 **순서**는 보지 않아 green 이었다 — 계약을 새로 만들면 그 계약의
**시간 순서**도 함께 잠가야 한다는 교훈. 순서 계약 2건을 추가하고 뮤테이션으로 KILL 을 확인했다.
같은 실측에서 계측기 자신의 결함도 드러났다: 샘플링 창 안에서 스크린샷을 찍으면 캡처가 렌더를
블로킹해 rAF 가 멈추고 **정상 트윈이 "전환 없음" 으로 오보고**된다(원시 프레임 추적으로 브라우저는
정상이었음을 먼저 확인한 뒤 계측기를 고쳤다 — 코드를 의심하기 전에 계측을 의심해야 했던 사례).

### 판단 근거 (설계 선택)

- **정렬을 바꾸지 않는다.** "제목을 바꿨더니 위로 올라간다" 는 `updated_at` 기반 정렬의 의도된
  결과이고, 사용자 불만은 순서가 아니라 **추적 불가능한 이동**이었다. 정렬 키를 손대면(예: 제목
  변경 시 `updated_at` 보존) 서버 계약과 다른 소비자(검색·API·워커)까지 영향이 번진다.
- **FLIP 을 고른 이유**: 목록이 매 렌더 전량 재구성되므로 요소가 교체된다 — CSS transition 은
  원리적으로 걸리지 않는다. 증분 렌더(요소 재사용)로 바꾸는 대안은 이 cycle 범위를 크게 넘고
  (drag&drop·메뉴·seed 로직이 전부 재구성 전제) 회귀 위험이 크다.
- **접근성**: reduced-motion 에서 트윈·강조는 끄되 **시야 유지는 유지**한다. 접근성 신호는
  "모션을 줄여라" 이지 "항목을 잃어도 좋다" 가 아니다.
- **라이브 데이터 취급**: 검증은 라이브 무접촉 bind-mount 컨테이너에서 했고, 폴더는 생성→삭제로
  정리, 대화 제목은 변경 후 **원복**했다. 다만 `updated_at` 은 되돌릴 수 없어 해당 대화 1건이
  '오늘' 그룹으로 올라간다 — 데이터 손실은 없으나 정직하게 남긴다.

## REV-20260824T173000-sidebar-reorder-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 **0** — 변경분은 `TASK.md` POST-DEPLOY 절과 `MODIFY.md` 기록뿐이다.
§18.8 dispatch 표의 "비정책 doc-only" 행에 해당해 panel 을 SKIP 한다. 검증 대상 제품 코드는
직전 cycle 에서 codex 적대 리뷰를 거쳤다(`REV-20260824T164437-sidebar-reorder-anim`
`[CODEX:frontend-adversarial]`, [P1] 1 · [P2] 4 전건 흡수 → 재실행 [P1] 0).

**이번 실증이 새로 확정한 것**: 직전 cycle 의 시각검증은 라이브 web 이미지 + 변경 자산을
bind-mount 한 **검증용 컨테이너**에서 수행했다(미머지 코드를 라이브 무접촉으로 보기 위함).
그것은 "이 코드가 이렇게 동작한다" 는 증거이지 "라이브가 그 코드를 서빙한다" 는 증거가 아니다.
여기서는 엣지가 실제로 서빙하는 자산(`?v=977b70eee5ae`)으로 같은 조작을 반복해 **16 프레임
트윈**을 다시 관측했고, 서비스별 `GIT_COMMIT`(`f0a9d4f9`)과 무중단 0건을 함께 확인했다.
## REV-20260824T180000-reorder-easing [CODEX:frontend-adversarial] — [P1] 0 · [P2] 2 전건 흡수

**Trigger**: `UI/화면/레이아웃` keyword matched (§18.8). 세션 도구 제약과의 해소는 §18.8.2 순서대로
제약 없는 채널(codex)로 수행. 프롬프트에 이번 변경의 위험 축(오버슈트 ↔ 좌표 계약 · duration ↔
watchdog/강조/TTL · 경계 이탈 · 겹침 · 하네스 실효)을 실었다.

### 지적과 처리

- **[P2] 오버슈트가 이동 거리에 비례해 커진다.** 이 곡선의 최대 편차는 ≈10.5% — 500px 이동에서
  ~52px, 상한 2400px 에서 ~251px 가 목표 밖으로 나간다. 8px 패딩으로는 흡수 못 하고, 반대 방향
  행과 교차하는 구간이 320→420ms 로 늘어 클릭 오전달 창도 커진다. **타당하다** — "오버슈트 폭은
  이동의 10%" 라는 사실을 알면서 상한(2400px)만으로 안전하다고 적은 것이 느슨했다.
  → ① 600px 초과 이동은 ease-out 으로 강등(과장 자체를 끊음), ② 시야 보정 패딩에 오버슈트 폭을
  더함, ③ 트윈 중 포인터 차단. ①은 사용자가 요청한 연출을 **일반적인 이동에서는 그대로 두고**
  극단 케이스만 낮추는 선택이다(사이드바 실사용 이동은 대부분 30~300px).
- **[P2] 하네스가 easing·duration 계약을 실제로 잠그지 않는다.** 소스에서 값을 뽑아 다시 소스와
  비교하니 `420`을 바꾸든 곡선을 바꾸든 통과한다. **타당하다 — 가장 뼈아픈 지적이다.** 직전
  cycle 에서 "뮤테이션으로 KILL 확인" 을 했으면서, 새로 추가한 계약에는 같은 기준을 적용하지
  않았다. → 기대값을 하네스에 독립 고정(420ms · 네 제어점 · ease-out 폴백 · 600px · 1100ms ·
  4000ms)하고 타이머는 지연값(820ms)을 검사한다. 뮤테이션 5종으로 실효 확인.

### 판단 근거

- **duration 320 → 420ms**: 오버슈트는 양끝에 구간을 하나씩 더 만든다. 같은 320ms 안에 넣으면
  되돌아오는 움직임이 1~2 프레임으로 뭉개져 "탄력" 이 아니라 "떨림" 으로 보인다.
- **강등 임계 600px**: 사이드바 한 화면(≈700px)에 가까운 이동이면 이미 화면 전체가 재편되는
  상황이라, 거기에 60px 이상 더 튀는 연출은 정보 전달을 방해한다. 30~300px(실측 대역)은 그대로
  easeInOutBack.
- **포인터 차단 420ms**: 사용자가 방금 이름을 바꾼 직후라 즉시 클릭할 확률이 낮고, 겹침 구간의
  오클릭이 더 나쁘다. 정착·watchdog 양쪽에서 복원해 잠금이 남지 않게 했다.

## REV-20260824T190000-easing-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 **0** — `TASK.md` POST-DEPLOY 절과 `MODIFY.md` 기록뿐이라 §18.8
dispatch 표의 "비정책 doc-only" 행. 대상 코드는 직전 cycle 에서 codex 적대 리뷰를 거쳤다
(`REV-20260824T180000-reorder-easing`, [P1] 0 · [P2] 2 전건 흡수).

**확정한 것**: 검증 컨테이너가 아니라 **엣지가 실제로 서빙하는 자산**(`?v=9ca76406f562`)에서
같은 조작을 반복해 오버슈트 궤적(back-in +3 → 오버슈트 -3)을 재확인했다. easing 은 상수 하나가
번들에 실렸는지로 끝나지 않고 **화면에서 곡선이 그대로 나오는지**가 계약이라, 서빙본 궤적을
정본 증거로 남긴다.

## REV-20260824T190000-reorder-affordance [CODEX:design-critique] — 연출 재설계(되돌림 포함)

**Trigger**: `UI/화면/레이아웃` keyword matched (§18.8). 세션 도구 제약은 §18.8.2 순서대로
제약 없는 채널(codex)로 해소. 이번엔 구현 리뷰가 아니라 **연출 선택 자체**를 비평 대상으로 실었다
(오버슈트가 정보 전달에 기여하는가 · 420ms 가 정당한가 · 눈을 뗀 사용자에게도 알리는 수단 ·
현재 강조가 충분한가 · 재정렬 자체를 피하는 길). 근거는 웹 리서치(모션 가이드·NN/G 지속시간)로 보강.

### 결론 — 직전 cycle 의 easeInOutBack 을 되돌린다

사용자가 직접 요청했던 곡선을 되돌리는 판단이라 근거를 분명히 남긴다.

- **오버슈트는 장식의 언어다.** 단일 요소의 진입·강조에는 어울리지만, 여러 행이 동시에 움직이는
  기능적 재정렬에서는 목록 전체가 출렁여 "무엇이 어디로 갔는지" 를 흐린다. 업계 가이드의 공통
  권고(기능 UI = 감속 곡선)와도 어긋난다.
- **420ms 는 큰 화면 전환용 대역**(NN/G: 400ms 는 "매우 느림", 대형 이동 전용)이다. 사이드바 한
  행의 이동에는 길고, 그동안 행이 입력을 받지 않는 시간도 함께 늘어난다.
- **가장 중요한 지적**: 모션은 **그 순간 화면을 보고 있어야만** 정보를 준다. 사용자가 물은
  "더 명시적인 효과" 의 답은 곡선을 더 꾸미는 것이 아니라 **모션이 끝난 뒤에도 남는 표식**이다.

### 반영 (codex 권고 전건 수용 + 자체 판단)

- 곡선 ease-out · 길이 **거리 적응형 160~280ms**(codex 권고 대역).
- 도착 표식 2층: 펄스(0.9초) + **rail + "이동됨" 배지**(3.5초). rail 은 **형태**, 배지는
  **언어** 신호 — 색만으로 구분하면 hover/active 배경과 의미가 충돌한다는 지적을 반영했다.
  배지에 `aria-label`, `position: absolute`(레이아웃 비침습), hover 시 날짜 tip 에 자리 양보.
- 도착한 **묶음 헤더 동반 펄스** — "어느 그룹으로 갔는지" 를 라벨 위치로 알린다(자체 추가).
- reduced-motion 에서도 표식 유지(codex 가 "특히 잘못된 선택" 이라 지적한 부분 — 직전 구현은
  reduced-motion 에서 강조까지 통째로 껐다).

### 채택하지 않은 것과 이유

- **재정렬 보류/사용자 통제("정렬 적용" 버튼)**: 화면 순서가 서버 정렬과 어긋나 새로고침·다른 탭·
  주기 동기화와 충돌하고 "왜 최신 대화가 위에 없지?" 라는 새 혼란을 만든다(codex 도 기본 동작으로는
  비권장). 불채택.
- **폴더 `sort_order` 를 진짜 수동 순서로**: 가나다 자동 정렬을 기대하는 사용자에게 손질 부담을
  넘긴다. 현 제품 의도(이름순)와 어긋나 불채택.
- **정렬 키와 `updated_at` 분리 (근본 해법)**: 옳은 방향이라고 판단하지만 이 cycle 범위를 넘는다 —
  PG 트리거(`trg_core_conv_updated_at`)가 모든 UPDATE 에서 `updated_at` 을 갱신하므로 별도
  `last_message_at` 신설 + 백필 + 정렬/검색/커서 쿼리 동반 변경이 필요하다. `TASK.md` 에 별도
  과제로 제안(§8.1)하고, 이번엔 서버를 건드리지 않는 표면 개선으로 한정했다.

### 실측이 잡은 결함 2건 (하네스 통과 상태였다)

후처리 복원의 취약성(두 번째 렌더에서 표식 소실)과 세대 없는 만료 타이머(오래된 타이머가 최신
표식 제거)를 라이브에서 잡았다. 둘 다 **하네스는 green** 이었다 — 단일 이동·단일 렌더만 재현했기
때문. 각각 구조 변경(행 생성 시 부여)과 세대 토큰으로 봉인하고 계약을 추가했다. 교훈:
**"상태를 렌더 뒤에 덧칠하는" 설계는 렌더 횟수에 의존하고, 수명 있는 표식은 세대를 가져야 한다.**

## REV-20260824T200000-affordance-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 기록

**Trigger**: 제품 코드 변경 **0**(TASK/MODIFY 기록뿐) → §18.8 표의 "비정책 doc-only" 행.
대상 코드는 직전 cycle 에서 codex 디자인 비평을 거쳤다(`REV-20260824T190000-reorder-affordance`).

**확정한 것**: 직전 cycle 의 검증은 bind-mount 컨테이너였다 — "이 코드가 이렇게 동작한다" 는
증거이지 "라이브가 그 코드를 서빙한다" 는 증거가 아니다. 엣지가 실제로 서빙하는 자산으로 같은
조작을 반복해 **rail + 배지가 재렌더를 견디고 수명 뒤 스스로 사라지는 것**을 다시 확인했다.

**남긴 운영 메모**: `win-browser.py` 의 브리지 host 감지가 `/etc/resolv.conf` nameserver 에
의존해, DNS 가 바뀌면 relay 가 살아 있어도 `bridge_unreachable` 로 보인다. 이때는 default
gateway(`ip route`)로 relay 주소를 확인하고 playwright 로 직접 붙으면 된다.

## REV-20260824T203000-dnd-reorder-affordance [CODEX:frontend-adversarial] — [P1] 3 · [P2] 2 전건 흡수

**Trigger**: `UI/드래그/화면` keyword matched (§18.8). 제약 없는 채널(codex)로 수행(§18.8.2).

### 지적과 처리

- **[P1] 대화 이동 트윈이 두 번째 렌더에 잘린다.** 낙관적 즉시 렌더가 트윈을 시작하고 곧바로
  `loadConversations` 렌더가 DOM 을 갈아엎는다. **타당하며, 가장 뼈아프다** — 내가 낸 실측
  데이터(99ms vs 계약 166ms)가 이미 증거였는데 "트윈 관측됨" 으로 통과시켰다. 계약 값과 실측을
  **대조**하지 않은 판정이었다. → 즉시 렌더·로컬 반영 제거, 서버 반영 렌더 한 번으로 이동.
- **[P1] 주기 unread 동기화가 대기 중 예약을 가로챈다.** `await loadFolders()` 창에서 동기화가
  전역 데이터 버전을 올리고 렌더하면, 그 렌더가 **이동 전 상태로** 예약을 소비한다. 전역 버전
  하나로 여러 데이터원을 대표하는 설계의 한계다. → 동기화 진입 가드에 `sidebarReorderFocus`
  (예약이 대기 중이면 미룬다). 데이터원별 버전 분리는 과설계라 보고 가드로 해소했다.
- **[P1] 드래그 중 재렌더가 drop 을 씹는다.** 동기화에 `dqaDrag` 가드가 없어 전량 재렌더가
  native drag source/target 을 제거한다. **내 변경 이전부터 있던 결함**이지만 DnD 를 연출 대상에
  넣은 이 cycle 에서 함께 고치는 것이 맞다. → 같은 가드에 추가.
- **[P2] 제자리 드롭에도 표식이 생긴다.** → `_sameFolderRef` 조기 반환(PATCH·예약 모두 생략).
- **[P2] 하네스가 배선을 잠그지 못한다.** 문자열·인덱스 검사라 예약을 PATCH 앞으로 옮겨도 통과.
  **타당하다** — 직전 cycle 에서 같은 지적을 받고 기대값을 독립 고정했으면서, 새로 추가한 배선
  계약에는 다시 문자열 검사를 썼다. → 실 함수를 구동하고 스텁 **호출 순서를 기록**하는 실행형
  테스트로 교체(선-렌더 부재 · 실패 시 예약 없음 · 예약 시점 버전 · 제자리 드롭 무동작).

### 봉인 확인

뮤테이션 5종 전건 KILL(즉시 렌더 부활 · 드래그 가드 제거 · 예약 가로채기 가드 제거 · 대화/폴더
제자리 드롭 가드 제거). 하네스 151 → **160 PASS**.

### 남은 한계 (정직)

codex 지적대로 **합성 `dispatchEvent` 는 CSS hit-testing 을 우회**하므로, 네이티브 드래그에서만
드러나는 포인터·레이어 충돌은 이 계측으로 확인할 수 없다. 실사용 관측으로 이월한다.
## REV-20260824T173000-sidebar-rename-focus — 인라인 이름 변경 오확정 봉인 + 대화 '이름 변경'

**요청 판정**: 사용자는 "사용자의 조작이 아닌, DQA 내 별도의 작업으로 인해" 를 **가설로** 제시했다.
검토 결과 그 가설은 사실이었다 — 좌측 목록을 사용자 조작 없이 다시 그리는 경로가 3종 실재하고
(주기 unread 동기화 7s · 전환 catchup 1.2s · AI 응답 진행 중 상태 갱신), 그 재구성이
`innerHTML=""` 전량 방식이라 편집 중 입력이 떨어져 나간다. 결함 주입 사본으로 **미완성 이름이
그대로 PATCH 되는 것을 재현**해 확증했다(추정 아님 — §16.7 G7-a).

**왜 3겹인가 (한 겹으로 끝내지 않은 이유)**:
- ③ 무시(detach·IME blur 비확정)만 두면 오확정은 막히지만, 재렌더가 입력을 **원래 이름으로
  되돌리는** 소실이 남는다(사용자는 타이핑이 사라지는 것을 본다).
- ① 억제만 두면 억제할 수 없는 경로가 남는다 — AI 응답 진행 중 상태 dot 갱신은 실시간이어야
  하므로 편집을 이유로 멈출 수 없다. 이 경로는 ②(보존)가 받는다.
- ② 보존만 두면 복원 타이밍과 blur 발화 순서에 의존하게 되어, 브라우저별 detach-blur 동작 차이
  (Chromium/Firefox 가 다르다)가 그대로 결과를 가른다. ③ 이 그 의존을 끊는다.
셋은 서로 다른 실패 모드를 덮으므로 어느 하나가 다른 하나를 대체하지 않는다.

**포커스 복원을 조건부로 둔 이유**: 매 렌더마다 무조건 `focus()` 하면, 사용자가 폴더 이름을
편집하다 프롬프트 입력창으로 옮겨 타이핑하는 동안 7초마다 포커스를 빼앗는 **새 마찰**이 생긴다.
렌더 직전 `document.activeElement` 가 그 입력이었을 때만 복원한다.

**대화 편집 행을 `<div>` 로 바꾼 판단**: `.conv-item` 은 `<button>` 이고 그 안에 `<input>` 을 넣는
것은 HTML 상 interactive content 중첩이라 클릭·포커스 동작이 브라우저마다 어긋난다. 폴더 헤더가
이미 `div[role=button]` 이라 같은 형태로 맞췄다. `.conv-item` 클래스와 `data-conversation-id` 를
유지해 스타일·FLIP 행 매칭(`_reorderRowKey`)이 그대로 걸린다 — 직전 cycle
(REV-20260824T164437-sidebar-reorder-anim)의 재배치 트윈이 이 행에도 계속 적용된다.

**권한 — fail-open 을 우선 막았다**: 메뉴 항목에 **추상 action**(`conversation.rename`)을 넘겨
`requiredPermissionsFor` 의 `default:` 무음 fall-through 를 만들지 않고(§16.7 G6 — 형제 항목이
권한 코드를 그대로 넘겨 게이트가 조용히 차단되던 회귀가 이 저장소에 이미 있었다), 확정 시점에도
`canRenameConversation` 을 2차 검사해 **권한 없는 계정은 PATCH 자체가 나가지 않는다**. 서버 게이트
(`conversation.rename.own`/`.any`)는 그대로 최종 방어선이다.

**서버 계약 무변경**: 신규 엔드포인트 0, RBAC 정의 0, 스키마·마이그레이션 0. 대화 제목 변경은
설정 팝업이 쓰던 `PATCH /api/conversations/{cid}/title` 을 그대로 재사용하며 두 진입점이 공존한다
(팝업 경로를 제거하지 않은 이유: 그룹 대화 멤버가 팝업에서 '나가기' 등 다른 조작을 하며 제목을
함께 확인하는 흐름이 있다).

**검증의 한계(정직 표기)**: 하네스는 DOM 스텁 위 동작 검사이고, 브라우저가 detach 시점에 blur 를
실제로 어떻게 발화하는지는 **PB-0008 라이브 실측**이 정본이다. 하네스는 "어떤 경로로 blur 가
오더라도 확정되지 않는다" 를 잠그는 쪽으로 설계했다(브라우저 동작 차이에 결과가 의존하지 않게).

## REV-20260824T190500-sidebar-rename-review-fixes [CODEX:frontend-adversarial] — VERDICT: 반영 후 SHIP

**패널**: `codex exec` 적대 리뷰(read-only, reasoning=high) — staged diff 직접 판독.
**결과**: [P1] 1 · [P2] 3, **전건 흡수**. 권한 경로는 "메뉴 게이트 + 확정 2차 검사 + 서버 최종 검사"
3중이라 fail-open 미발견으로 확인됐다.

**[P1] 이 값진 이유**: 우리 봉인은 "재렌더가 와도 편집을 지킨다" 를 값·커서 복사로 달성했는데,
IME 조합은 **노드에 묶인 세션**이라 복사로 옮겨지지 않는다. 즉 한글 사용자에게는 ②(보존)가
작동하는 것처럼 보이면서 조합만 조용히 끊기고, 그 다음 Enter 가 미완성 문자열을 **정상 확정**으로
처리한다 — 우리가 막으려던 바로 그 증상이 IME 경로로 되살아난다. 라이브 프로브가 조합 중
재렌더 2회에도 노드가 유지됨(`same_node: true`)을 보여 수정을 확증했다.

**억제에 상한을 둔 이유**: [P2] 지적대로 "편집 중에는 갱신을 미룬다" 는 편집이 **끝난다는 가정**에
의존한다. 사용자가 편집을 열어둔 채 자리를 비우거나, 대상 행이 사라져 편집을 닫을 표면이
없어지면 억제가 영구화되어 배지·목록이 조용히 낡는다. 두 방어선을 넣었다 — 고아 세션은 렌더
직후 회수하고, 그래도 남는 경우를 위해 억제 자체에 60초 상한을 뒀다(상한 이후에도 ②③ 이
편집을 지키므로 오확정 위험은 늘지 않는다).

**저장/재조회 분리**: PATCH 성공 후 목록 재조회만 실패해도 "실패했습니다" 를 띄우던 것은 **거짓
보고**다(§16.7 G7 — 사실 주장의 근거 등급). 폴더 경로도 같은 구조였으므로 함께 고쳤다(G8 적용면).

**측정 정정**: 1차 실측에서 "편집 종료 후 9초 폴링 1건" 을 억제 해제의 근거로 삼았으나, **편집이
없는 기준선도 16초에 1건**이었다 — 9초 창은 억제/해제를 가르지 못한다. 창을 16초로 늘려
"편집 중 0건 → 확정 후 1건(기준선과 동일)" 로 다시 측정했다. 근거가 약한 수치를 그대로 두지 않는다.

**하네스가 놓쳤던 축**: 51 PASS + 뮤테이션 5종 KILL 로도 이 4건은 잡히지 않았다 — 하네스가
"blur 가 어디서 오든 확정하지 않는다" 는 봤지만 **조합 세션의 물리적 연속성**, **편집이 닫히지
않는 경로**, **오류 보고의 정확성** 은 계약으로 갖고 있지 않았다. 네 축을 계약으로 추가하고
뮤테이션 8종으로 잠갔다(73 PASS).

## REV-20260824T193000-sidebar-rename-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 + 계측기 수정

**Trigger**: 제품 코드 변경 **0** — 변경분은 PB-0008 계측기 1줄(모듈 import URL)과 Run 기록이다.
§18.8 dispatch 표의 "비정책 doc-only" 에 해당해 panel 을 SKIP 한다. 제품 코드는 직전 cycle 에서
codex 적대 리뷰를 거쳤다(`REV-20260824T190500-sidebar-rename-review-fixes`
`[CODEX:frontend-adversarial]`, [P1] 1 · [P2] 3 전건 흡수).

**이번 실증이 새로 확정한 것**: 직전 cycle 의 시각검증은 라이브 web 이미지 + 변경 자산을
bind-mount 한 검증용 컨테이너에서 했다. 그것은 "이 코드가 이렇게 동작한다" 는 증거이지 "라이브가
그 코드를 서빙한다" 는 증거가 아니다. 여기서는 엣지가 실제로 서빙하는 자산(`?v=6ac119f76533`)으로
같은 조작을 반복해 편집 중 재렌더 2회에도 `PATCH` 0건 · 편집 중 16초 폴링 0건 · 우클릭 메뉴 4항목을
다시 관측했고, 서비스별 `GIT_COMMIT`(`27d99bb2`)과 무중단 0건을 함께 확인했다.

**계측기가 정상 코드를 거짓 FAIL 시킨 건**: 라이브 1차 A 단계가 FAIL 로 나왔다. 원인은 제품이
아니라 계측이었다 — 고정 `?v=dev` URL 로 모듈을 import 하면 배포본(content-hash 스탬프)에서는
**별개 ESM 인스턴스**가 생기고, 그 인스턴스가 편집을 모르는 채 목록을 재구성한다. bind-mount
환경에서는 소스가 `?v=dev` placeholder 라 우연히 같은 인스턴스여서 드러나지 않았다. 결함을
제품에서 찾기 전에 **계측이 무엇을 실행하고 있는지** 먼저 확인한 것이 이 건의 유일한 분기점이었다
(직전 cycle 의 "캡처가 rAF 를 멈춰 정상 트윈을 0프레임으로 보고" 와 같은 클래스 — 계측기는
자기 자신도 검증 대상이다).

## REV-20260825T010305-doc-sync-rn-0825 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-24 블록 prepend(8항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260825T010305-doc-sync-rn-0825`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-08-25T01:03:05+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · 구조 단언(`releases` 51→**52** · `generated`=="2026-08-24"==`releases[0].date` · top items 8 · 2nd 블록 items 1 불변 · 스키마 외 키 0 · enum 기존 집합 내) · **`tests/verify_release_notes.mjs` 34 pass/0 fail = 편집 전 baseline 34/0 동일 → 회귀 0** · 내부용어 누출 0(기계 스캔).
- **적대검증**: ULTRACODE 워크플로 `wf_97297b9a-f3a` — 6 에이전트 / 988,185 토큰 / 300 tool-use. 4축 병렬 스윕(릴리즈노트·wiki·정책문서·cross-surface) → 축 교차 2조 refute-first 검증(29 CONFIRMED · 5 REVISE · 7 newFindings · **오케스트레이터 전제 반증 2건**). RN 축에 대한 **P1 적발 1건을 반영**: 초안이 "콘솔에서 값을 바꾸면 재기동 없이 판정 기준이 함께 반영된다" 를 2곳에서 단정했는데 정본 `unit/feature-0002-agent-core/docs/TASK.md`:3081 이 그 시나리오를 `- [ ] **미검증(이월)**` 로 등재 → 두 문장에서 콘솔-변경 주장을 제거(없는 검증을 약속하지 않는다). 검증자의 용어-선례 카운트 3건(Esc·배지·묶음)은 실측과 달라 **커밋 문면에 인용하지 않았다**(방향은 동일 — 선례는 실재).
- **블록 귀속 판정**: 델타 19 커밋의 git-date 가 전부 2026-08-24 이고 그 date 블록이 부재(grep 0회) → 신규 블록 prepend + `generated` top-block 연동. 오늘(08-25) 날짜 블록·publish-date 신설 금지 규약 준수.
- **배포 게이트**: `deploy-web.state` `current=abc1a1a9`(08-24 19:21) · 라이브 `mysql-ai-web:abc1a1a9` ⊇ 8항목 소유 커밋 전건 → 이미 서빙 중. 자체 POST-DEPLOY 실증 커밋이 있는 6 cycle(`a1c5ccfe`·`788e2b0b`·`5ffc31d9`·`09efce70`·`4ebb9cba`·`85ef0174`·`e24be5f5`)과 없는 3건(`f0935560`·`a07d9b3d`·`a87e4331`)을 구분해 판정했고, 후자도 배포 이미지에 baked 되어 있어 '미배포' 가 아니다.
- **RN 제외 판정(정직)**: `b5654b69`(template v3.48.0 업그레이드)·`697fdefe`(cron belt 결함 종결)·POST-DEPLOY 문서 커밋 7건은 사용자 체감 표면 0 → 제외(개발자향·내부 운영). backfill 누락 추가분 0.
- **cache-buster**: 수기 bump 없음. `docs/CONVENTIONS.md`:568 이 "`?v=dev` 고정 · 빌드 `inject_asset_stamp.py` content-hash 주입 · **수기 bump 금지**" 를 명문화하고 `bin/deploy-web.sh` 가 placeholder 잔존 시 ABORT 한다. `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.**

## REV-20260825T103000-ctxmenu-order-parity [SKIPPED:trivial-ui-order] — 메뉴 항목 순서 정합

**Trigger**: 변경은 `openFolderMenu` 의 `appendChild` 4줄 순서와 주석뿐이다 — 로직·권한·서버
계약·DOM 구조가 모두 불변이고, 각 항목의 `onSelect` 배선도 그대로다. §18.8 패널의 대상(결함
탐색)이 될 표면이 없어 SKIP 한다. 대신 **구조 테스트로 잠갔다** — 두 `buildItems` 를 실행해 순서를
대조하는 §9b 를 추가하고 뮤테이션 2종(구 순서 복원 · 설정 중간 배치)이 죽는 것을 확인했다.

**왜 '이름 변경' 만 옮기지 않았나**: 요청은 '이름 변경' 의 순서를 지목했지만, 실측해 보니 공통
항목이 **둘 다** 어긋나 있었다 — `설정` 도 폴더에서는 3번째(중간), 대화에서는 마지막이었다.
'이름 변경' 만 맞추면 같은 성격의 부정합이 그대로 남아 다음 지적을 부른다. 요청의 근본(같은
목록의 같은 조작이 같은 자리에 있어야 한다)에 맞춰 공통 항목 전체를 정합시켰다.

**왜 폴더를 대화에 맞췄나 (반대가 아니라)**: ① '이름 변경' 은 두 메뉴 모두에서 가장 잦은 단일
조작이라 첫 자리가 맞다. ② '설정' 은 하위 팝업을 여는 무거운 항목이라 목록 끝이 관례다.
③ 대화 메뉴가 이미 그 형태였으므로 변경 표면이 작다(폴더 4줄만 이동 — 회귀 위험 최소).

**규칙을 주석으로 남긴 이유**: 순서는 코드로 강제되지 않는 계약이라, 다음에 항목을 추가하는
사람이 규칙을 모르면 다시 어긋난다. 양쪽 `buildItems` 위에 같은 규칙을 적고 구조 테스트가
그것을 지키게 했다(§16.7 G10 — 재발 클래스를 점수정으로 끝내지 않는다).
## REV-20260826T010305-doc-sync-rn-0826 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 2026-08-25 블록 prepend(3항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260826T010305-doc-sync-rn-0826`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-08-26T01:03:05+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · 구조 단언(`releases` 51→**52** · `generated`=="2026-08-25"==`releases[0].date` · top items 3 · 2nd 블록 items 8 불변 · 스키마 외 키 0 · enum 기존 집합 내) · **`tests/verify_release_notes.mjs` 34 pass/0 fail = 편집 전 baseline 34/0 동일 → 회귀 0** · 내부용어 누출 0(7패턴 기계 스캔).
- **적대검증**: ULTRACODE 워크플로 `wf_46129373-398` — 6 에이전트 / 924,479 토큰 / 310 tool-use / 28분. 4축 병렬 스윕(릴리즈노트·wiki·정책문서·cross-surface, 38 finding) → 2조 교차검증(정본대조 렌즈 · 적용안전성 렌즈). RN 축 3 finding 은 양 렌즈 전건 CONFIRMED(oldString `count==1` 실측 · 적용 후 `node --check` 통과 구조 확인 · `generated == releases[0].date` 불변식을 git 이력으로 독립 검증).
- **오케스트레이터 추가 판정 1건**: 검증 두 렌즈가 모두 통과시킨 초안 문장 중 "안내 문구를 다듬는 일 … 이어서 손보고 있습니다" 를 **정본 근거 부재로 삭제**했다(원장 open FR·정본 TASK 후속 절 어디에도 그 두 축이 등재돼 있지 않음). 두 렌즈는 '사실 정확성'과 '적용 안전성'을 봤을 뿐 **미래 약속의 근거**를 축으로 갖지 않았다 — 릴리즈노트 고유 위험이라 오케스트레이터가 닫았다.
- **블록 귀속 판정**: 델타 5 커밋의 git-date 가 전부 2026-08-25 이고 그 date 블록이 부재(grep 0회) → 신규 블록 prepend + `generated` top-block 연동. 오늘(08-26) 날짜 블록·publish-date 신설 금지 규약 준수.
- **배포 게이트**: `deploy-web.state` `current=4c7bd6c0`(08-25 18:38) · 라이브 `mysql-ai-web:4c7bd6c0`(StartedAt KST 18:34, healthy) ⊇ 3항목 소유 커밋 전건(`0f14fa3d`·`93680ba3`·`65c515d8`) → 이미 서빙 중. 후행 `2092df81` 은 그 배포의 라이브 실측을 기록한 문서 전용 커밋이라 사용자 표면 0.
- **RN 제외 판정(정직)**: `2fd86696`(2026-07-23~08-25 상부보고 발표자료 v1)·`2092df81`(배포·라이브 실측 기록) = 사용자 체감 표면 0 → 제외. `65c515d8` 의 `AGENTS.md` §15.2.1·ADR 추가분도 개발자향 정책이라 제외(사용자 체감 축인 '답변 실패' 만 항목화). backfill 누락 추가분 0.
- **cache-buster**: 수기 bump 없음. `docs/CONVENTIONS.md` §14.1 이 "`?v=dev` 고정 · 빌드 `inject_asset_stamp` content-hash 주입 · **수기 bump 금지**" 를 명문화한다(cron wrapper 지시문의 '캐시버스터 bump 를 같은 커밋에 포함' 지시는 이 규약보다 오래된 stale — 따르면 배포 스크립트의 placeholder ABORT 가드를 깬다). `index.html`/`admin.html` 편집 0.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수다.**

## REV-20260827T160500-bridge-progress-scroll [CODEX:feature-0003-web] — PASS (P1 0 잔여) · 브리지 답변 직후 스크롤 최하단 고착

- Related TASK: feature-0003-agent-web-ui / `TASK-20260827T160500-bridge-progress-scroll`
- Risk: **Minor** (§12.3) — 비파괴 · 읽기 경로 1곳 + 프런트 분기 1곳. 인증/인가·데이터·외부계약 무관.
- Human Approval Needed: no
- Timestamp: 2026-08-27T16:05:00+09:00

### 무엇을 고쳤나 — 그리고 왜 그 지점인가

증상은 "답변 직후 스크롤이 계속 맨 아래로 끌려감" 이었지만, 스크롤 코드에는 아무 문제가 없었다.
`renderMessages()` 가 맨 아래로 보내는 것은 채팅 UI 의 정상 계약이고, 브리지 답변 경로는 이미
`loadHistory({ preserveScroll: true })` 로 사용자의 위치를 지키고 있었다. **진짜 원인은 그 뒤에서
아무도 요청하지 않은 재로드가 반복된 것**이다.

서버가 같은 대화를 두 엔드포인트에서 다르게 답한 것이 발단이다 — `/api/progress` 는 "진행 중",
`/api/history` 는 "유휴". 브리지 대화에는 서버 run 이 없어 KV 가 비고(라이브 확인), `/api/progress`
는 steps fallback 을 타는데, 답변 전달 직후 심기는 **사후 원장**(`work_source='bridge-ledger'`)을
"방금 생긴 step = 진행 중" 으로 읽었기 때문이다. 프런트 감지기는 그 불일치를 "화면이 뒤처졌다" 로
해석해 `loadHistory()`(preserveScroll 없음)를 위임했고, 그 재로드가 감지기를 다시 무장시켜
**지연 0ms 순환**이 됐다. 원장이 3분을 넘겨 늙어야 멈춘다 — 제보된 지속 시간과 일치한다.

그래서 두 층을 함께 고쳤다.

1. **서버(정본 수정)** — 끝난 원장을 진행 중이라 말하지 않는다. fallback 집계에서 원장 행을
   제외한다. 제외를 **WHERE 절**에 둔 것이 요점이다: `ORDER BY … LIMIT 1` 이 원장 run 만 뽑아오므로
   가져온 뒤 걸러면 같은 대화의 실 서버 run 을 통째로 잃는다.
2. **프런트(수렴 보장)** — 불일치가 *다른 이유로* 재발해도 화면은 흔들리지 않아야 한다. 감지기는
   한 `(대화, run)` 안에서 이미 본 국면으로는 재로드를 위임하지 않는다.

### 왜 프런트 가드까지 넣었나 (서버만 고쳐도 증상은 사라지는데)

서버 하나만 고치면 이번 증상은 사라진다. 그러나 "유휴/진행이 갈리면 화면이 0ms 로 무한 재로드된다"
는 **구조는 그대로 남는다** — KV 분기·복제 지연·엔드포인트 추가 같은 다른 원인으로 언제든 같은
증상이 재현된다. §16.7 G10(재발 클래스를 점수정으로 종결하지 않는다)에 따라 순환 자체를 잠갔다.

### 채택하지 않은 대안

- **원장 step 을 아예 기록하지 않는다** — 'AI 추론' 탭이 다시 비게 된다. 원장은 사용자에게 가치가
  있고, 잘못은 기록이 아니라 그것을 진행 신호로 읽은 쪽에 있다.
- **가져온 뒤 파이썬에서 필터** — 위 1번의 이유로 오답(실 run 유실).
- **감지기의 재로드를 `preserveScroll: true` 로 바꾼다** — 증상만 가린다. 새 답변이 왔을 때 맨
  아래로 가는 것은 옳은 동작이고, 문제는 "아무것도 안 바뀐 재로드가 반복되는 것" 이다.
- **`_engageRailBottomPin` 완화** — 원인이 아니다. pin 은 8초 상한·사용자 제스처 해제가 이미 있다.

### 적대 검증 (codex 5 라운드 — P1 3 · P2 3, 전건 수정)

라운드마다 실제 결함이 나왔다. 특히 **내 수정이 다른 것을 조용히 깨뜨린** 두 건이 중요하다:

- **3R P1 — 빈 `run_id` 응답이 위임 이력을 초기화**: 일시적 빈 응답 뒤에 오는 같은 run 의 완료
  전이가 "이력 없음" 으로 읽혀 **최종 답변이 영구 미표시**가 될 수 있었다. 빈 run 은 범위를
  건드리지 않도록 바꾸고 S15 로 잠갔다.
- **4R P1 — 형제 하네스 파손**: `verify_progress_poll_resilience.mjs` 가 `detectNewRun` 만 추출해
  실행하는데, 신규 helper 를 주입하지 않아 `ReferenceError` 가 **`detectNewRun` 자신의 `catch` 에
  삼켜져** 40/5 로 조용히 죽어 있었다. 내 하네스(57/0)만 보고 있었으면 못 봤다. helper 주입 +
  추출 fail-loud 단언으로 복구(46/0).
- 1R P1(완료 전이 영구 차단) · 1R P2(SQL 뒤집기 미검출) · 2R P2(국면 흔들림 순환 재발) · 2R P2(문서
  stale) 도 전건 수정. 5R 잔여 지적 0.

### 검증

- `make test` exit 0 (FAILED/ERROR 0건), ruff PASS.
- 하네스 `verify_run_detect_poll.mjs` **57/0**(S9~S15 신규) · `verify_progress_poll_resilience.mjs`
  **46/0**(복구) · main baseline 대비 `verify_*.mjs` 전건 exit-code 동일 → **신규 회귀 0**.
- **뮤테이션 역검증 3종 전건 KILL** — 위임 가드 제거→S9/S12/S13 FAIL · 빈-응답 가드 제거→S15 FAIL ·
  SQL `<>`→`=`→`test_fallback_query_excludes_bridge_ledger` FAIL.
- 라이브 근거(배포 전): 해당 브리지 대화의 KV 에 `last_status*` 부재(키=`created_at`/`model:10`/
  `reasoning_level`/`topic`) · `agent_runtime.steps` 에 `work_source='bridge-ledger'` 19행
  (`run_id=t_LBtWKW0f1sBBfGK-`) · 배포본 `_load_latest_run_id_from_steps('20260827061652-5ab532d1')`
  = `('t_LBtWKW0f1sBBfGK-', False)` → **끝난 브리지 답변이 "최신 run" 으로 읽히고 있음**을 실측.
- 배포 후 같은 호출이 `('', False)` 가 되는 것을 라이브에서 재확인(§16.3 deploy-backed 완료 기준).

## REV-20260827T175500-bridge-scroll-evidence [SKIPPED:non-policy-doc] — 라이브 배포 검증 증적 기록

- Related TASK: feature-0003-agent-web-ui / `TASK-20260827T160500-bridge-progress-scroll`
- Reason: changed paths are docs + evidence 이미지만 — 코드·스키마·권한 변경 0.
- Timestamp: 2026-08-27T17:55:00+09:00
- Human Approval Needed: no
- 내용: 배포본 `eb6412ad` 라이브 실측(`('t_LBtWKW0f1sBBfGK-', False)` → `('', False)`, web-a/web-b)
  + PB-0008 실 Windows Chrome 151 relay Run(도달성·서빙 baked PASS, 로그인 화면 실측 미수행 사유
  명시) + `bin/win-browser.py` Windows host 오탐 발견을 §8.1 개선 제안으로 기록.
- 정직성: 로그인 후 대화 화면의 스크롤 안정성은 **측정하지 않았다** — 서버측 실측·하네스로
  대체 주장하지 않고 미수행으로 표기했다.

## REV-20260828T010305-doc-sync-rn-0828 [SKIPPED:non-policy-doc] — 릴리즈노트 신규 3블록 prepend(19항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260828T010305-doc-sync-rn-0828`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-08-28T01:03:05+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · `verify_release_notes.mjs` **34/0 = 편집 전 baseline 동일(회귀 0)** · 구조 실측(`releases` 53→**56** · `generated`=="2026-08-28"==`releases[0].date` · 신규 3블록 items 4/13/2 · 직전 08-25 블록 items 3 불변 · type/area enum 기존 집합 내 · 스키마 외 키 0 · date 중복 0) · 누출 스캔 7패턴 **0건**(유일 ASCII/고유명 히트는 사용자가 화면에서 그대로 본 오류 문구 'AWS Bedrock 서비스가 일시적으로 응답하지 않습니다' 인용 1건 — 의도적 보존)
- **적대검증**: ULTRACODE 워크플로 `wf_f4ff80dd-6cd` — 7 에이전트 / 1,250,673 토큰 / 469 tool-use / 42분. 4축 병렬 스윕(릴리즈노트·wiki·정책문서·미착륙 prior-window) → 2조 교차검증(서로 다른 축을 적대적으로 반증 + MISS 탐지) → 완결성 비평. 98 findings / 87 verdict(CONFIRMED 81 · REVISE 6 · REFUTED 0) · 신규 MISS 11건.
- **수용한 검증조 지적 3건(전부 사용자향 정직성)**: ① MISS-01 화면 리터럴 오인용 — 실제 문구는 '아직' 없는 '답변할 AI 가 연결되어 있지 않습니다' ② MISS-02 summary 가 '각 항목에 검증 상태를 적었다' 를 단정 → 완화 ③ 직전 08-25 블록의 '확인했습니다' 단정이 정본상 오판이라 08-26 블록에 재발 경위 1문장 삽입.
- **미착륙 prior-window 회수**: 08-27 doc_sync RN 커밋 `88150ddd` 가 origin/main 미착륙이라 그 창의 사용자향 delta 를 이번 창에 흡수 재작성했다. 초안의 제외 판정 1건(첨부 버전 상향)은 정본 재검증에서 사유 불성립으로 뒤집혀 hedge 포함으로 채택.
- **cache-buster**: 수기 bump 없음. `docs/CONVENTIONS.md`:568 이 `?v=dev` 고정·빌드 `inject_asset_stamp` content-hash 주입·**수기 bump 금지**를 명문화하고 `bin/deploy-web.sh`:1627 이 baked 이미지의 placeholder 잔존을 ABORT 한다 — cron wrapper 지시문의 'bump 포함' 은 stale.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수**.

## REV-20260828T230000-ai-root-feature-0003 [CODEX:uncommitted-diff] — CHANGES-REQUESTED → P1 0 · P2 5 전건 조치

`codex exec --sandbox read-only` 로 미커밋 diff 적대 검토(149k 토큰). **P1 0 · P2 5**, 전건 조치.
세션 지시(AgentTool 미사용)와 §18.8 패널 요구가 충돌해 사용자 결정으로 codex 를 패널 대체로 채택.

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| 1 | 계보를 **파일명 완전일치**로 재구성 — 대소문자·확장자 변경은 분리되고, 그룹 대화의 독립 동명 업로드는 한 집합으로 합쳐진다 | **기존 정의와 일치**(내가 만든 괴리 아님) | 서버 `_load_filename_lineage_heads` 도 `(ConversationId, OriginalFilename)` 완전일치 + 활성 head 다. 클라이언트가 **서버 정의를 그대로** 미러한다. 문구도 "같은 이름의 계보" 로 사실만 말한다. 계보 family 를 이름 밖으로 넓히는 것은 서버 계약 변경이라 별도 판단 |
| 2 | 사람이 올린 첨부를 전부 "내 파일/내가 올린 계보" 로 표시 — payload 에 업로더 `account_id` 가 없어 **그룹 대화에서 남의 파일을 내 것이라 거짓말** | **CONFIRMED** | 주체 중립 문구로 교체("업로드한 파일에서 갈라진 계보" / "사용자가 올린 계보"). 회귀로 1인칭 소유권 문구 자체를 금지 |
| 3 | 계보 해소 실패를 로그 없이 `{}` 로 삼킴 → 클라이언트가 "실패" 와 "분기 없음" 을 구별 못 함 | **CONFIRMED** | `warning` 로그 추가(목록은 fail-soft 로 그대로 나간다) |
| 4 | 게이트 테스트가 **토큰 존재만** 검사 — `\|\|` → `&&` 로 회귀해도 통과 | **CONFIRMED** (가장 중요) | 소스 문자열이 아니라 **값**으로 고정: 표현식을 파싱해 `(V,L)` 조합별 진리값을 단언. `&&` 뮤턴트 2종 KILL 확인 |
| 5 | 시각 제목은 축을 따라가는데 dialog `aria-label` 은 "첨부 버전 비교" 고정 — 스크린리더에만 틀린 제목 | **CONFIRMED** | `aria-label` 도 축 추종 + 회귀 |

### 뮤테이션 역검증 — 총 17종 KILL

1차 11종에 더해 codex 조치분 6종(`&&` 회귀 2 · 소유권 문구 2 · 실패 로그 · 접근성 이름).
소유권 문구 2종은 **처음에 생존**했다 — 코드는 고쳤는데 잠그는 회귀를 안 썼기 때문이다.
회귀 추가 후 KILL.

### 이 리뷰가 잡은 것의 성격

5건 중 3건(#2·#4·#5)이 **"고쳤다고 생각한 것이 절반만 고쳐진" 부류**다 — 보이는 제목만 고치고
접근성 이름은 두었고, 게이트는 고쳤지만 테스트는 반대 값도 통과시켰고, 문구는 사실을 말하지만
소유권은 여전히 단정했다. 내 눈으로는 "했다" 로 보이는 자리들이다.

## REV-20260831T010305-doc-sync-rn-0831 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-08-28 블록 items append(11항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260831T010305-doc-sync-rn-0831`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-08-31T01:03:05+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · `verify_release_notes.mjs` **34/0 = 편집 전 baseline 동일(회귀 0)** · 구조 실측(`releases` **56 불변** · `generated`=="2026-08-28"==`releases[0].date` · items[0] 4→**15** · items[1] 13 불변 · type/area enum 기존 집합 내 · 스키마 외 키 0 · date 중복 0) · 누출 스캔 7패턴 **0건**
- **적대검증**: ULTRACODE 워크플로 `wf_b9237e20-af7` — 6 에이전트 / 1,006,922 토큰 / 290 tool-use / 35분. 4축 병렬 스윕(릴리즈노트·wiki·정책문서·정본교차) → 2조 교차검증(정확성 반증 렌즈 + 거버넌스·scope 렌즈, 각자 MISS 능동 탐색). 51 findings / 102 verdict(각 조 46/51 CONFIRMED) · 신규 MISS 9건.
- **수용한 검증조 지적(릴리즈노트 축)**: ① 연결 게이트 항목의 「잠금·안내·**해제** 확인」 단정 — POST-DEPLOY 증적의 「미수행(정직 표기)」 절이 '실 러너 기동 → 잠금 해제 → 질문 왕복' 을 AI 무인 완결 불가로 배제하므로 해제 축을 분리 ② 하트비트 항목의 「배포한 뒤 실제 확인」 단정 — 정본 test-run frontmatter 가 `잔여 — 배포 후 PB-0008 실화면 · 라이브 지속 실측`, 시각검증 fragment 가 `PENDING` 이라 확실성 표기 하향 ③ MISS-05 RN-01/RN-02 단방향 의존(summary 가 items 를 열거) — 두 편집을 한 커밋에 함께 적용.
- **미러 vs 정본 수렴**: 08-27 블록이 '두 항목을 화면에서 감췄습니다'·'첨부 쓰기는 이번에 열지 않았습니다' 로 단정했으나 창이 둘 다 되살렸다. 과거 블록을 고치지 않고(그 시점 사실의 기록) 새 항목에서 경위를 밝혀 수렴했다.
- **report-only(정본 소관)**: feature-0043 `REPORT.md` §1 이 아직 「PB-0008 화면 시각검증만 미수행」으로 단정해 같은 파일 §4-A·§10 과 모순 — 사용자향 문안의 '확인했습니다' vs '회원님의 확인이 필요합니다' 를 가르는 근거가 이 정본이라, 모순이 남는 한 매 창 미러가 재오염된다. 「조회 결과 CSV」에서도 `REPORT.md` §7.0 과 `FUNCTION.md` 가 갈려 미러는 보수적으로 미복원 쪽을 적었다.
- **cache-buster**: 수기 bump 없음. 소스는 `?v=dev` 고정이고 빌드가 content-hash 를 주입하며 `bin/deploy-web.sh` 가 baked 이미지의 placeholder 잔존을 ABORT 한다 — cron wrapper 지시문의 'bump 포함' 은 stale(수기 bump 는 배포를 죽인다).
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수**.

## REV-20260831T163000-conv-last-activity-updatedat-post [SKIPPED:non-policy-doc] — POST-DEPLOY 실측 + 백필 사후 발견 (doc-only)

- 대상 diff: `feature-0002/docs/MODIFY.md` + `feature-0003/docs/{TASK,REPORT,TEST}.md` — **코드 변경 0**.
- §18.8 dispatch 표 1행(비정책 doc-only) → panel SKIP.
- **정정 기록**: 1차 백필이 19행을 실행 시각으로 밀었다. 원인은 `core_conversations` 의
  `trg_core_conv_updated_at`(BEFORE UPDATE → `set_updated_at()`, 무조건 `now()`) — 사전에 이
  트리거를 확인하지 않고 `SET updated_at = GREATEST(...)` 를 실행한 판단 오류다. 즉시 관측하고
  (`updated_at > now() - 20m` 이 정확히 19건) 트리거를 우회해 의도한 값으로 다시 썼으며, 백업과
  대조해 19/19 일치를 확인했다. 다른 대화로의 파급 0.
- **일반화**: 파생 타임스탬프 컬럼을 **과거 값으로** 쓰는 작업은 그 컬럼에 걸린 트리거를 먼저
  조회한다(`pg_trigger`). "UPDATE 하면 그 값이 들어간다" 는 트리거가 있는 테이블에서 성립하지
  않으며, 실패가 조용하다(오류 없이 다른 값이 들어간다).
- 결론: 배포·백필·표면 실측 종결. 미실측 1건(PB-0008 육안)은 사유와 함께 명시했고 완료로 오인
  보고하지 않는다.
## REV-20260831T193000-ai-claude-feature-0003-attach-lineage-viz — 첨부 계보 비교 가시성 재설계 (Minor §12.3)

### 왜 선행 cycle 로 부족했나

REQ-20260828-attach-lineage-ui 는 계보의 **존재**를 화면에 올렸다(배지 `계보 1/2`, 구성 안내문,
단건 계보 비교 진입점). 그런데도 불만이 재수렴했다. **존재를 말하는 것과 견주기 쉬운 것은 다른
문제**이기 때문이다 — 선행 cycle 은 «정보를 추가»했고, 이번 제보는 «구조가 안 보인다»였다.

### 웹 리서치 → 설계 원칙 (디자인적 관점)

| 출처 | 원칙 | 이 화면에 적용 |
|---|---|---|
| NN/g «The Principle of Common Region» | enclosure(테두리·배경)는 **근접성을 압도**한다 | 같은 파일의 계보를 카드로 감쌈 |
| NN/g «Visual Hierarchy» | 무엇이 중요한지는 **크기·색**이 정한다 | 그룹 안 파일명 낮춤 / 계보 칩 승격 |
| GitKraken Commit Graph | 브랜치를 **레인 + 연결선**으로 그린다 | 레일 + elbow + 분기 들여쓰기 |
| GitKraken change gauge | 변경 규모를 **열기 전에** 보여준다 | 크기 델타 칩(정직한 라벨) |
| Google Docs 버전 기록 | **작성자별 색** + 타임라인 + 명명 버전 | 사용자=중립 / AI=파랑 색축 |
| Figma 브랜치 리뷰 | 비교/머지가 **1급 액션** | 그룹 머리의 `⇄ 계보 비교` |

공통 관찰: 성숙한 도구는 모두 **컨테이너가 artifact 이름을 말하고, 행은 그 갈래를 가르는 정보만
싣는다**(Google Docs 는 행에 문서명을 쓰지 않고, GitKraken 은 저장소명을 쓰지 않는다). 우리 화면은
행마다 같은 파일명을 되풀이하며 정작 «누구의 갈래인가»를 서수(`계보 1/2`) 뒤에 감췄다.

### 진단한 결함 7종

1. 평면 형제 행 — 같은 파일의 갈래와 무관한 파일이 시각적 동급
2. 분기가 산문·툴팁에만 — 보려면 읽어야 함
3. 「계보」가 네 곳에서 서로 다른 뜻으로 반복(§16.8 예산)
4. 비교 진입 2단계 — 펼쳐야 버튼이 나타남
5. 작성 주체 색축 미성립 — **정의되지 않은 CSS 토큰**으로 조용히 무효
6. 변경 규모 신호 부재 — 열어 봐야 앎
7. 서수는 정체성이 아님 — 순서가 바뀌면 같은 계보가 다른 번호

### 판단 근거 · 대안

- **왜 카드(enclosure)인가, 간격이 아니라**: NN/g 가 명시하듯 공통영역이 근접성을 압도한다.
  간격만으로는 «같은 파일의 갈래»가 전달되지 않는다 — 이미 그 상태였고 제보가 그 결과였다.
- **왜 행에서 파일명을 지우지 않았나**: 그 요소가 «원문 보기» 클릭 대상이자 접근성 이름이다.
  지우면 a11y 가 깎인다. 대신 **위계를 역전**했다(크기·굵기·색) — 정보는 남기고 시선만 옮긴다.
- **왜 크기 델타인가, 실제 diff 통계가 아니라**: 실 통계(`+182 / -21`)는 계보마다 diff API
  왕복이 필요해 목록 렌더 비용이 계보 수에 비례한다. 크기는 payload 에 이미 있어 **공짜**다.
  대신 «내용 차이» 라고 말하지 않는다 — 같은 크기의 전혀 다른 파일에서 화면이 거짓말하게 된다.
  실 내용 차이는 모달의 `+N / -N` 이 담당하고, 칩의 title 이 그 경로를 안내한다.
- **왜 분기 표식에 글리프 + 파선을 함께 쓰나**: 색 단독 인코딩은 색각 이상 사용자에게 소실된다.
- **버린 대안**: (a) 트리 위젯 — 계보 깊이가 사실상 2단이라 위젯 비용 대비 이득 없음.
  (b) 목록을 계보 기준으로 재정렬 — 사용자가 기억하는 «최근 올린 순»을 깨뜨림. 그래서 그룹만
  첫 멤버 자리에 통째로 넣어 전체 순서를 보존했다.

### 자기 결함 1건 (실측이 잡음)

색축을 넣었는데 **성립하지 않았다** — 인접 규칙이 쓰던 `var(--muted)` 가 이 저장소에 정의되지
않은 토큰이라 조용히 무시됐고, 사용자 계보 칩이 본문색 그대로 렌더됐다. CSS 를 읽는 것만으로는
드러나지 않는다(문법상 완전히 정상). 라이브 `getComputedStyle` 실측이 `rgb(38,37,30)` 을 반환해
잡혔다. 「방어를 넣었다 ≠ 방어가 성립한다」의 CSS 판. 회귀 테스트로 잠갔다.

또한 첫 라이브 시도에서 `groups: 0` 이 관측됐는데, 이를 «미구현»으로 읽지 않고 **캐시 축을
갈라내** asset stamp 재주입으로 재현했다. 서버 파일이 신버전이어도 Chrome 모듈 캐시가 구버전을
실행하는 이 저장소의 기지 함정이다.

### 위험도 · 승인 근거

- **Minor §12.3** — 표현 계층(JS 렌더 + CSS)만. 데이터·스키마·권한·API 계약 변경 0.
  되돌리기 = revert + 재배포. 외부 비용 없음. 캐시-키/fingerprint 변경 없음(§16.3 blast-radius 비대상).
- **배포 사전 승인**: `FIRST_REQUEST.md` 의 `deploy_scope: included` (2026-06-11 사용자 결정,
  cycle 시작 시점에 이미 존재). cycle-final 후 web 재배포까지 사전 승인 범위 — 첫 배포 직전 1줄 표면화.
- 검증: pytest 전건 PASS(신규 18) · `node --check` PASS · PB-0008 실 Windows 브라우저
  구조·픽셀·computed·인터랙션 2 surface — `docs/test-runs.d/TASK-20260831T193000-attach-lineage-visibility.md`

### 출처

- https://www.nngroup.com/articles/common-region/
- https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- https://www.gitkraken.com/features/commit-graph
- https://help.figma.com/hc/en-us/articles/360038006754-View-a-file-s-version-history
- https://help.figma.com/hc/en-us/articles/360063144053-Guide-to-branching
- https://zapier.com/blog/google-docs-revision-history/

## REV-20260831T210000-ai-claude-feature-0003-attach-lineage-viz [CODEX:feature-0003-attach-lineage-visibility] — PASS (2R 조치 완료)

- Related TASK: feature-0003-agent-web-ui (20260831T193000-attach-lineage-visibility)
- Source: codex review (codex-cli 0.146.0, `codex exec` read-only, 판정 기준 = `docs/CODE_REVIEW.md`)
- Trigger: UI/화면/레이아웃 keyword matched → §18.8 dispatch `ux, design`. subagent panel 대신
  codex 채널 사용(§18.8.1 항목 2, check #9 accepted) — 본 세션은 Agent tool 사용이 제한된 환경.
- Timestamp: 2026-08-31T21:00:00+09:00
- Rounds: **2** (§18.8 패널 수렴 계약 (a) — P1 을 수정했으므로 확인 라운드 1회 수행)
- Verdict: **PASS** — 라운드별 P1: 1R **1건** → 2R **2건**(신규) → 전건 조치 + 라이브 실증
- Human Approval Needed: no (Minor §12.3 · 표현 계층 + fail-soft 신호 추가, 파괴적 변경 0)

### 1R (P1 1 · P2 6 · P3 2) — 전건 조치

| 등급 | 지적 | 조치 |
|---|---|---|
| P1 | 파일명이 그룹 키라 **독립 업로드 2건에도 파생 관계를 주장** | 그룹핑은 이름 유지(사용자가 찾는 것은 "이 이름으로 뭐가 있나"), **파생 주장만** 데이터로 — `is-branch` 를 서수 → `_originId > 0` 로, 계보수 title 에서 "갈라진" 제거 |
| P2 | 3+ 계보 깊이가 서수 기반 | **깊이를 주장하지 않는다**(한 단만). 분기 부모 id 가 형제의 중간 버전일 수 있어 목록에서 되짚지 못한다(라이브 실측) — 되짚을 수 없는 관계로 A→B→C 를 그리면 그것도 근거 없는 주장. 의도적 제한으로 코드에 명시 |
| P2 | 비동기 응답 뒤 화면이 바뀌어도 모달이 뜸 | `document.contains(_card.el)` + `activeConversationId` 이중 가드 |
| P2 | SR 에서 계보 정체성 구분 불가 | 행 접근성 이름에 `(AI 계보, 갈라져 나옴, 2개 중 2번째)` 부착 |
| P2 | 카드가 접근성 트리에서 그룹이 아님 | `role="group"` + aria-label |
| P2 | `상세` 토글에 `aria-expanded` 없음 | 3지점(초기·토글·로드완료) 부착 |
| P2 | 크기 미상을 0 으로 오인 | `Number.isFinite` 양측 검사 |
| P2 | 그룹 신호 대비 1.10:1 | 테두리 `#a8a598` · 레일 `#8c8a7c`(3.02:1, 2px) · 칩 `#5a5852`(7.11:1) · 낮춘 파일명 `#6b6960`(5.51:1) |
| P3 | 죽은 `data-lineage-count` · JSDoc | 제거 · 보강 |

### 2R (P1 2 신규 · P2 2 · P3 1) — 전건 조치

1R 조치는 **배선까지 확인되어 재지적 없음**. 새로 드러난 것은 둘 다 「조용한 오답」 축이다.

- **P1 — 계보 비교가 실패 시 버전 비교로 조용히 전환.** 서버의 계보 해소는 fail-soft 라
  `lineages: []` 로 떨어질 수 있는데, 그러면 `preselect.axis` 가 의도적으로 무시되고 **이 계보의
  버전 비교**가 열린다. 사용자가 누른 것과 열리는 것이 다른 조용한 오답. → **못 하면 못 한다고
  말한다**: 호출부가 `lineages.length < 2` 를 검사해 안내 후 열지 않는다.
  라이브 실증(fetch 스텁으로 `lineages: []` 재현): 모달 **미개봉** + 「계보 정보를 불러오지
  못했습니다」 토스트.
- **P1 — 계보 목록 `LIMIT 20` 무음 절단.** 그룹 카드는 목록 기준 전체 계보 수를 말하는데 비교
  API 는 20개에서 말없이 자른다 → 화면이 없는 완전성을 주장. → 로더가 `limit + 1` 을 읽어
  **"마침 20개" 와 "잘림" 을 구분**하고, 응답에 `lineages_truncated` 를 실어 모달이 밝힌다.
  라이브 실증: 로더 `limit=1 → truncated=True` / `limit=2,20 → False`, 모달에 「계보가 많아
  최근 20개만 나열합니다」(role=status) 렌더.
- **P2 — `Number(null) === 0`.** 변환 **뒤** isFinite 검사는 미상을 통과시킨다. 변환 전 가드로
  이동 + 호출부의 `|| 0`(헬퍼 가드를 무력화하던 경로) 제거.
- **P2 — catch 경로 stale 가드 부재.** 실패 토스트도 지금 화면의 것일 때만.
- **P3 — JSDoc 블록 분리** → 함수에 붙는 단일 블록으로 병합.

### 왜 2R 이 필요했나 (수렴 계약의 값)

1R 의 수정이 **새 P1 을 만들지는 않았지만**, 1R 이 못 본 축(조용한 축 격하 · 무음 절단)을 2R 이
잡았다. 「수정한 라운드 자체는 종결 근거가 아니다」(§18.8 (a))가 실제로 값을 냈다. 3R 은 돌리지
않는다 — 2R 지적은 전부 **새 코드가 아니라 기존 fail-soft 경로의 노출**이었고, 조치가 그 경로를
좁히는 방향(열지 않기·밝히기)이라 새 표면을 만들지 않았으며, 각 조치를 라이브에서 **양측**
(정상/실패, 절단/비절단) 실증했다.

### 회귀 (§16.7 G10 — 점수정이 아니라 구조로 잠금)

신규 `test_attach_lineage_group_ui.py` **32건**. 각 지적이 되돌아오는 경로를 개별로 막는다:
서수 기반 분기 판정 복귀 · 계보수 title 의 파생 주장 · stale 가드 순서(성공·실패 양쪽) ·
`role=group` · 행 접근성 이름 · `aria-expanded` 3지점 · 변환 전 미상 가드 + 호출부 `|| 0` ·
절단 신호 3층(로더·응답·모달) · 대비 floor · 축 부재 시 fail-loud.
pytest `feature-0003`+`feature-0002`+`feature-0023` **4997 passed / 5 skipped**.
## REV-20260831T182700-ai-claude-corp-feature-0003-connect-modal-autoclose [CODEX:connect-modal-autoclose] — PASS (3R P1 0건)

- Related TASK: feature-0003-agent-web-ui / `20260831T1827-connect-modal-autoclose`
- Source: codex exec (codex-cli 0.146.0) — 3 라운드 적대 리뷰
- Trigger: UI/모달 키워드 매칭(§18.8 dispatch 표 3행 → ux·design). **세션 도구 제약으로
  subagent panel 대신 §18.8.1 경량 경로(codex)로 수행** — 상위 우선순위 지시가 Agent tool
  사용을 금지하므로 §18.8.2 「상위 우선순위 지시 carve-out」 적용. 미검증 도메인은 아래
  `[SKIPPED:tool-restricted:*]` 로 명시한다.
- Timestamp: 2026-08-31T19:35:00+09:00
- Verdict: **PASS (P1 0건)** — 1R BLOCK(P1 2·P2 4) → 2R 승인불가(P1-1 잔존 + 새 P2 1) → 3R **P1 0**
- Human Approval Needed: no

### 무엇을 바꿨나

「내 AI 연결하기」 모달이 연결 성립(`listening: true`) 시 토스트로 알리고 스스로 닫는다.
**판정 시점을 «토큰 발급» 이 아니라 «대기 중이 됨» 으로** 두었다 — 발급 시점에 닫으면 모달이
스스로 "이 창을 닫으면 다시 볼 수 없습니다" 라고 알린 그 명령이 사라지는데, 정작 연결은 아직
아무 일도 일어나지 않는다.

### 라운드별 지적과 조치

**1R — BLOCK (P1 2 · P2 4)**

- **P1-1 이전 실행 루프가 새 모달을 닫는다**: `[내 AI 실행]` 대기 루프가 창보다 오래 살아,
  창을 닫고 새로 연 뒤 그 루프의 성공 관측이 **새 창**을 닫는다(그 창의 명령이 사라진다).
  → 창 세대 `_modalEpoch` 도입. 루프가 시작 시 캡처해 매 회차 대조 후 불일치면 물러난다.
- **P1-2 실행 버튼이 기준선을 우회한다**: 다른 컴퓨터의 러너가 이미 대기 중이면, 이 컴퓨터용
  새 명령을 발급하고 실행을 누른 순간 **남의 러너 때문에** 즉시 성공으로 닫힌다.
  → **닫기 판정을 `_noteListeningForModal` 한 곳으로 일원화**. 두 P1 은 뿌리가 같았다 —
  판정이 두 곳에 있었고, 한쪽은 «이 창의 전이» 라는 기준선을 몰랐다.
- P2-3 첫 조회 실패 시 그 뒤의 성공을 «기준선» 으로 삼켜 영영 알리지 못함 → 기준선을
  `_lastKnownListening`(직전에 화면에 반영된 값)으로.
- P2-4 폴링이 in-flight 를 무시하고 5초마다 새 요청 → 응답이 6초면 전부 세대 검사에 버려짐
  → `_gateInFlight` 겹침 가드.
- P2-5 중복 토스트 테스트가 항진명제(`_announced` 가드를 지워도 통과) → E3 신설: 오버레이를
  치워 닫기를 불가능하게 만든 뒤 3회 관측 → 알림 1회.
- P2-6 타이머·배선 미검증 → setInterval/clearInterval 계측(E2) · import 경로 실재(E1) ·
  리스너를 실제로 저장·디스패치하는 shim 으로 버튼 경로 구동(F1·F2).

**2R — 승인 불가 (P1-1 잔존 + 새 P2)**

- epoch 검사가 `sleep` 전후에만 있어 **fetch in-flight 중 창 교체** 경합을 안 덮는다. F2 는
  조회 출발 **전에** 닫으므로 그 경합을 검증하지 않는다 — 「막힌다」를 확정할 근거가 없다.
  → `refreshConnState()` 가 출발 시점 epoch 를 캡처해 `_noteListeningForModal` 로 전달(창-경계
  검사를 **응답 처리 지점**으로 내림) + 테스트 F3 신설(응답 1200ms 지연으로 in-flight 상태를
  만든 뒤 창 교체).
- 새 P2: `_gateInFlight` 가 settle 안 되면 폴링을 **영구 정지**시킨다(고치려던 것보다 나쁜 실패).
  → `_raceTimeout` 으로 감싸 반드시 풀리게 하고 성공·실패 양쪽에서 플래그를 내린다.

**3R — PASS (P1 0)**

### 계층을 가른 뮤테이션 실측 (2R 의 「확정할 수 없다」에 대한 답)

| 뮤턴트 | 결과 |
|---|---|
| 응답 epoch 검사만 제거 | 25/0 통과 — `_connSeq` 최신성 검사가 막는다 |
| `_connSeq` 검사만 제거 | 25/0 통과 — epoch 검사가 막는다 |
| **둘 다 제거** | **F3a·F3b·F3c FAIL — 경합이 실제로 재현된다** |

경합은 실재하고, 현재 코드는 **이중으로** 막으며, F3 는 그 중복이 필요한 지점을 정확히 겨눈다.
논증이 아니라 관측으로 닫았다.

전체 뮤테이션 9종: loop-epoch→F2a·F2b / response-epoch→생존(seq 가 1차) / both-epoch→F2a·F2b /
connseq→생존(epoch 이 1차) / seq+respepoch→**F3a·F3b·F3c** / launchrunner-announces→F1c·F1d·F1e /
baseline-first-obs→G1 / announced-guard→E3 / clearinterval→E2b·F2a·F2b.

### 검증

- 신규 행위 테스트 `tests/verify_connect_modal_autoclose.mjs` **25/0 PASS** (A~G) — 실제 모듈을
  최소 DOM shim 위에서 구동. 리스너를 저장·디스패치해 `[내 AI 실행]` 버튼 경로도 실제로 탄다.
- **G11-b 결함 주입 실증**: 수정 전(main) 코드에서 **7건 FAIL**(A3·A4·A5·D1·E2a·E3·G1).
- PB-0008 Windows-browser 라이브 결함 재현(배포본 `1c0864dc`) — 배지가 «내 AI 대기 중» 인데
  모달이 그대로 남고 알림 0. 스크린샷 1장.

### 남은 위험 (정직 표기 — 완료로 오인 보고하지 않는다)

- **`_gateInFlight` 해제 전용 테스트 없음** (codex 3R P2 잔여). 폴링 간격 5초를 테스트에서
  발화시킬 수단이 없어서다. 코드 방어(`_raceTimeout` 상한)는 넣었으나 그 방어를 겨누는 단언은
  없다. 타임아웃 후 원 요청이 늦게 종료될 때의 중첩·부수효과도 후속 보강 대상.
- **실 러너 end-to-end 미수행**: 서버가 스스로 `listening:true` 를 내는 경로(개인 머신에 AI CLI
  설치·인증 후 러너 기동)는 AI 무인 완결 불가. 이번 검증은 「서버가 그 값을 줄 때 화면이 어떻게
  반응하는가」라는 프론트엔드 계약에 한정된다. 그 필드를 내는 서버 계약 자체는 이번 변경 이전부터
  같은 코드가 소비하던 것이라 이번 변경의 위험 표면이 아니다.
- **`_lastKnownListening` 기준선의 stale 위험**: 직전 관측이 stale `false` 인데 실제로는 이미
  연결돼 있었다면, 창을 열자마자 닫힐 수 있다. 그 상태는 배지도 «연결 안 됨» 으로 보이던
  상태라 판정과 화면이 갈리지는 않지만, 새 연결 정보를 만들려던 사용자에게는 마찰이다.
  `visibilitychange`·폴링이 상태를 최신으로 유지하므로 드물다고 판단해 수용했다.

## REV-20260831T182700-connect-modal-autoclose [SKIPPED:tool-restricted:ux-design] — 미검증 도메인 명시

- Related TASK: feature-0003-agent-web-ui / `20260831T1827-connect-modal-autoclose`
- Reason: §18.8 dispatch 표가 UI/모달 변경에 요구하는 `ux`·`design` subagent 는 이 세션의 상위
  우선순위 도구 제약(Agent tool 금지)으로 호출할 수 없다. §18.8.2 「상위 우선순위 지시
  carve-out」 대로 제약 없는 채널(codex 3라운드 + PB-0008 실화면)로 가능한 검증을 수행하고,
  덮지 못한 도메인을 여기 명시한다 — 미검증을 완료로 오인 보고하지 않는다.
- 실제로 덮인 축: 정합성·경합·자원(codex) · 실 렌더/상호작용(PB-0008). 덮이지 않은 축: 시각
  디자인 일관성 심사, UX 카피 톤 심사.
- Timestamp: 2026-08-31T19:35:00+09:00
- Human Approval Needed: no

## REV-20260831T193500-connect-modal-autoclose-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 증적 (docs-only)

- Related TASK: feature-0003-agent-web-ui / `20260831T1827-connect-modal-autoclose`
- Reason: changed paths are docs + 스크린샷 자산만 — 코드·스키마·권한 변경 0.
- Timestamp: 2026-08-31T19:35:00+09:00
- Human Approval Needed: no
- **실측 요지**: 배포본 `0fad9129`(자산 `?v=16960c2c319d`)에서 전이 후 `modal_hidden:true` +
  토스트 「내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다.」 + 배지 «내 AI 대기 중».
  PRE(`1c0864dc`)는 같은 절차에서 모달이 남고 알림 0 이었다 — 두 스크린샷이 그 차이를 담는다.
- **미수행(정직 표기)**: 실 러너 기동 end-to-end. 조회 응답만 가로챈 프론트엔드 계약 검증이며,
  검증 후 `fetch` 원복·모달 닫기·실제 상태 재조회로 브라우저를 원상 복구했다.
- **CI**: PR #1447 은 Actions 전면 미실행(job `steps=0`) 상태에서 `UNSTABLE` 로 머지됐다.
  CI 정적 게이트 4종을 로컬에서 전건 PASS 로 대체 충족했고 Python 변경은 0건이다. 이 사실을
  숨기지 않고 기록한다 — 복구 전까지 모든 PR 이 CI 미검증으로 머지된다(운영 조치 필요).

## REV-20260901T010306-doc-sync-rn-0901 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-08-31 블록 신설(14항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260901T010306-doc-sync-rn-0901`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-09-01T01:03:06+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · `verify_release_notes.mjs` **34/0 = 편집 전 baseline 동일(회귀 0)** · 구조 실측(`releases` 56→**57** · `generated`=="2026-08-31"==`releases[0].date` · `releases[0].items` **14** + summary · `releases[1]`(2026-08-28) items 15 불변 · **08-28 이하 tail 바이트 동일**(9,045B 순증) · type ∈ {new,improved,fixed} · area ∈ {work,admin,common} · 스키마 외 키 0 · date 중복 0) · 누출 스캔 18패턴 **0건**
- **적대검증**: ULTRACODE 워크플로 `wf_8127f38e-d76` — 6 에이전트 / **1,006,536 토큰** / 320 tool-use / 35분. 4축 병렬 스윕(릴리즈노트·wiki·정책문서·정본교차) → 2조 교차검증(정확성 반증 렌즈 / 거버넌스·scope 렌즈, 각자 MISS 능동 탐색). **63 findings · 126 verdict**(정확성 61/63 · 거버넌스 59/63 CONFIRMED) · **신규 MISS 12건**.
- **블록 귀속**: 창 75 커밋의 착륙일이 **전부 2026-08-31**(11:40~19:40)이고 그 date 블록이 **존재하지 않으므로**(최신이 2026-08-28) 기존 블록 append 가 아니라 **신규 블록 prepend**. 전 파일 grep 으로 `2026-08-29`/`08-30`/`08-31` 히트 0 을 사전 확인했다(owning feature self-add 부재).
- **수용한 검증조 지적(릴리즈노트 축)**: 「연결이 요청의 전제조건」 계열 항목에서 회원 머신에서만 확인 가능한 축(실 러너 기동 → 왕복)을 배포 서비스 확인 축과 **분리**해 확실성을 낮췄다. summary 말미에 「대부분은 배포된 서비스에서 눈으로 확인했고, 회원님의 컴퓨터에서만 확인할 수 있는 항목에는 그 사실을 함께 적었습니다」로 미검증 고지를 접힌 요약에도 노출했다.
- **미러 vs 정본 수렴**: 직전 08-28 블록이 「'답변 모델'·'추론 강도' 를 러너 신고 기반으로 **되살렸다**」로 단정했으나 창의 `d35f78dd` 가 그 두 칸이 **여전히 비어 있었음**을 고쳤다. 과거 블록은 그 시점 사실의 기록이므로 고치지 않고, 신규 항목에서 「8월 28일 안내에서 '되살렸다' 고 알려 드린 그 두 칸이 실제로는 여전히 비어 있던 문제」로 **재발을 명시**해 수렴했다.
- **cache-buster**: 수기 bump 없음. 소스는 `?v=dev` 고정이고 빌드 `inject_asset_stamp` 가 content-hash 를 주입하며 `bin/deploy-web.sh` 가 baked 이미지의 placeholder 잔존을 ABORT 한다(정본 `docs/CONVENTIONS.md:568`). 이번 run 의 cron wrapper 지시문이 '캐시버스터 bump 를 같은 커밋에 포함하라' 고 명시했으나 저장소 정본과 정면 충돌하므로 따르지 않았다 — 수기 bump 는 배포를 죽인다.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수**.

## REV-20260901T101500-ai-claude-feature-0003-attach-lineage-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 증적 (doc/test-only)
- Related TASK: feature-0003-agent-web-ui (20260901T101500-attach-lineage-postdeploy)
- Reason: 변경 경로가 `docs/**` 전용(코드·스키마·권한·UI 마크업 델타 0) — §18.8 dispatch 표 첫 행(비정책 doc-only) → panel SKIP.
- 선행 cycle 의 검증 원장은 REV-20260831T210000 [CODEX] 2라운드로 이미 종결됐고, 본 entry 는 그 배포본 실증을 기록만 한다.
- Timestamp: 2026-09-01T10:15:00+09:00

## REV-20260901T033000-ai-claude-corp-connect-modal-launch-close [CODEX:connect-modal-launch-close] — PASS (P1 0)

- Related TASK: feature-0003-agent-web-ui / `20260901T0330-connect-modal-launch-close`
- Source: codex exec (codex-cli 0.146.0) — 트레이드오프 판단 + 새 P1 판정
- Trigger: UI/모달 키워드(§18.8 표 3행). 세션 도구 제약으로 §18.8.1 경량 경로(codex) 사용 —
  `ux`/`design` 도메인은 직전 cycle 과 같이 `[SKIPPED:tool-restricted:*]` 범위로 남는다.
- Timestamp: 2026-09-01T03:30:00+09:00
- Verdict: **PASS (P1 0)**
- Human Approval Needed: no

### 이번 cycle 은 «직전 수정이 낸 회귀» 를 되돌린다

직전 cycle 에서 codex 1R 의 **P1-2**(「다른 컴퓨터의 러너가 이미 대기 중이면 남의 러너 때문에
거짓 성공으로 닫혀 명령을 잃는다」)를 수용해 `[내 AI 실행]` 성공 분기의 닫기를 포기했다.
**그 수정이 라이브 회귀를 냈고 사용자가 제보했다** — 창을 열 때 이미 «대기 중» 으로 알려져
있으면 자동 관측 경로가 «전이 아님» 으로 판정하므로, 실행을 눌러 성공을 확인해도 아무도 닫지
않는다. 남는 것은 성공 문구와 그대로 있는 창이다.

### 판단 — 지적을 수용한 방식이 틀렸다

codex 의 우려 자체는 옳았다. 틀린 것은 **적용 범위**다: 「자동 관측 경로에는 기준선을 적용한다」
로 끝냈어야 할 것을 「모든 경로에 적용한다」로 넓혔다. 사용자가 직접 누른 버튼은 명시적 의도이고,
그 결과를 확인하고도 창을 남기는 것은 성공을 말하면서 아무것도 하지 않는 것이다.

- 명령 손실은 「연결 준비」 재클릭으로 복구되고, 애초에 대기 중이면 그 명령은 필요 없다.
- «성공을 말하면서 아무것도 하지 않는» 것은 복구 경로가 없다. **실측 제보가 그쪽이다.**

codex 독립 확인: 「타당하다. 기준선은 자동 관측 경로에만 적용하고, 사용자가 직접 실행한 성공은
닫는 것이 맞다. … 남의 러너로 인한 오닫힘 위험은 남지만 … 수용 가능한 트레이드오프다.」

### 테스트가 회귀를 «올바름» 으로 잠그고 있었다

구 F1(「남의 러너로 닫히지 않는다」)이 정확히 이 회귀를 단언으로 고정하고 있었다. 지적을 수용해
만든 테스트가 그 수용의 과잉까지 함께 굳힌 것이다. F1 을 제거하고 같은 상황을 **H 가 반대
기대로** 잠근다.

### 뮤테이션이 드러낸 커버리지 구멍

성공 분기에 새로 넣은 창-세대 검사를 지운 뮤턴트가 **처음엔 생존**했다 — F3(창 교체)는
`_connSeq` 가 먼저 걸러 그 분기에 도달하지 않기 때문이다. 그 방어를 단독으로 겨누는 **F4**
(「실행 대기 중 창을 **닫기만** 했을 때 뒤늦게 도착한 성공이 토스트를 띄우는가」)를 신설해
KILL 을 확인했다. codex 2R 이 지적했던 형태(방어는 넣었는데 그것을 겨누는 단언이 없음)를 내가
반복했고, 뮤테이션이 그것을 잡았다.

### 검증

- **25/0 PASS**. 제보 재현 H3·H4 는 **현재 라이브 배포본에서 FAIL** 한다(제보가 실재함을
  배포본으로 확인).
- 뮤테이션 8종: revert-to-reported-bug→H3·H4 / success-epoch→**F4** / loop-epoch→F2a·F2b·F4 /
  response-epoch만→생존(`_connSeq` 가 1차) / **seq+resp 둘 다→F3a·F3b·F3c** /
  baseline-first-obs→G1 / announced-guard→E3 / clearinterval→E2b.

### 남은 위험 (정직 표기)

- **남의 러너로 인한 오닫힘**은 원리적으로 남는다 — 서버의 `listening` 이 «이 계정의 어떤
  러너라도» 를 뜻하는 한 화면은 구분할 수 없다. 의식적으로 수용한 트레이드오프이며, 복구
  경로(「연결 준비」 재클릭)가 있다.
- `_gateInFlight` 해제 전용 단언 없음(직전 cycle 잔여 P2) — 변동 없음.
- `ux`/`design` 도메인 심사 미수행 — 세션 도구 제약(§18.8.2 carve-out).

## REV-20260901T040500-launch-close-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 증적 (docs-only)

- Related TASK: feature-0003-agent-web-ui / `20260901T0330-connect-modal-launch-close`
- Reason: changed paths are docs + 스크린샷 자산만 — 코드·스키마·권한 변경 0.
- Timestamp: 2026-09-01T04:05:00+09:00
- Human Approval Needed: no
- **실측**: 배포본 `ead6e30f` 에서 제보 경로(기준선 true + 실행 버튼 클릭) → `modal_hidden:true`
  + 토스트 1건. 제보하신 「대기 중입니다」 문구는 성공 통로가 합쳐지며 사라졌다.
- **미수행(정직 표기)**: 실 러너 기동 end-to-end. 조회·토큰 응답을 가로챈 프론트엔드 계약
  검증이며 검증 후 브라우저를 원상 복구했다.

## REV-20260901T120000-ai-conn-chip-to-profile-row [SKIPPED:tool-restricted:ux,design] — 연결 칩 자리 이동 (프론트 배치 단독)

- Related TASK: feature-0003-agent-web-ui / `20260901T1200-ai-conn-chip-to-profile-row`
- Trigger: §18.8 dispatch 표의 `UI/button/layout` → `ux`·`design` 도메인. §18.8.2 순서대로
  **제약 없는 채널을 먼저** 시도했다.
- Timestamp: 2026-09-01T12:00:00+09:00
- Human Approval Needed: no (Minor §12.3 — 비파괴 프론트 배치)

### 검증 채널 (§18.8.2)

1. **`codex exec` 적대 리뷰 — 시도했으나 물리적으로 불가**: 핵심 diff 11.5KB 를 프롬프트에
   인라인하고 파일 접근을 금지한 형태(무응답 회피 레시피)로 호출했으나 계정 사용량 한도
   소진으로 즉시 실패(`ERROR: You've hit your usage limit`). 재시도 불가.
2. **subagent panel 미호출** — 세션에 상위 우선순위 도구 제약(요청 없는 Agent tool 호출 금지)이
   걸려 있어 §18.8.2 "상위 우선순위 지시 carve-out" 을 적용했다. `ux`/`design` 도메인 심사는
   **미수행**이며 아래 자체 점검이 그것을 대체하지 못한다.
3. **기계적·실측 채널로 수행한 검증** (아래).

### 기계적 검증

- **뮤테이션 역검증 4/4 KILLED** — ① footer 접힘 조건에 `:has(.ai-conn.hidden)` 복원 →
  `test_connection_chip_is_free_of_the_footer_collapse_rule` FAIL ② `flex-wrap: wrap` 제거 → FAIL
  ③ `flex: 1 0 auto` → `1 1 auto`(shrink 허용) → FAIL ④ 칩을 `.composer-footer` 로 되돌림 → FAIL.
  복원 후 전건 PASS. 계약이 «자리» 와 «양보 방향» 을 실제로 잠근다.
- 컨테이너 `make test` — pytest 전건 PASS(rc=0) + ruff PASS
- `verify_connect_modal_autoclose.mjs` 25/0 · `verify_llm_restriction_surface.mjs` 35/0
- **PB-0008 실 브라우저 실측 16조합** — 4상태 × 계정 4종(5·5·15·21자). 상세는
  `docs/test-runs.d/TASK-20260901T1200-ai-conn-chip-to-profile-row.md`.

### 자체 점검 (ux/design 대체 아님 — 관측 사실만)

- **레이아웃 안정성**: 계정당 네 상태가 같은 줄·같은 행 높이를 유지(65px 또는 90px 고정).
  가로 넘침 전 조합 0. 21자 계정은 이름 ellipsis 로 흡수.
- **클릭·포커스**: DOM 순서가 `[프로필 버튼] → [칩]` 이라 탭 순서가 자연스럽다. 칩은
  `<button>` 그대로이고 `id` 기반 접근(`$("aiConnState")`)이라 JS 배선 변경 0 — 자리만 옮겼다.
  화살표를 절대배치 + `pointer-events: none` 으로 빼는 안은 실측 결함으로 되돌렸다(2.1 참조).
- **문구**: 접두를 뺀 만큼 `title` 이 주어를 진다(네 상태 전부 "내 AI …" 로 시작). 그 계약을
  `test_indicator_has_three_states` 가 `js.count("내 AI") >= 3` 으로 잠근다.
- **명시도**: `.sidebar-profile > .ai-conn`(0,2,0)이 `search-audit.css` 의 `.ai-conn`(0,1,0)보다
  강해 로드 순서(profile → search-audit)와 무관하게 적용된다. `display` 는 건드리지 않아
  `.ai-conn.hidden` 의 숨김이 그대로 이긴다 — 실측 칩 폭 60~81px 로 확인.

### 남은 위험 (정직 표기)

- **`ux`/`design` 도메인 심사 미수행** — 도구 제약(위 2번). 특히 칩 글꼴을 `.78rem → .68rem`
  (12.48px → 10.88px)로 낮춘 것은 가독성 하락이 사실이며, 전문 심사 없이 «프로필 역할 텍스트
  11px 과 같은 눈높이» 라는 근거만으로 채택했다.
- **배포본 자산 재확인 잔여** — 본 cycle 실측은 라이브 페이지에 변경본 CSS 를 주입한 상태의
  측정이다(정적 자산은 web 이미지에 baked). 배포 후 `?v=<hash>` 자산으로 같은 16조합을
  재측정해 POST-DEPLOY fragment 로 남긴다.
- **칩이 화살표 뒤에 선다** — 사용자 스크린샷이 지목한 자리는 화살표 앞이었으나, 그 배치는
  긴 계정명이 화살표 밑으로 들어가는 실측 결함을 낳아 되돌렸다. 완료 보고에 명시한다.

## REV-20260901T124500-ai-conn-chip-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 증적 (docs-only)

- Related TASK: feature-0003-agent-web-ui / `20260901T1200-ai-conn-chip-to-profile-row`
- Reason: changed paths are docs + 스크린샷 자산만 — 코드·스키마·권한 변경 0.
- Timestamp: 2026-09-01T12:45:00+09:00
- Human Approval Needed: no
- **실측**: 배포본 `40340f53` 에서 주입 없이 16조합 재측정 — 배포 전 실측치와 전부 일치.
  `.composer-footer` 전 조합 `display: none`(사용자가 지적한 입력창 아래 여백 해소).
- **선행 cycle 의 잔여 해소**: `REV-20260901T120000-…` 이 "배포본 자산 재확인 잔여" 로 남긴
  항목이 본 Run 으로 닫혔다. **`ux`/`design` 도메인 심사 미수행은 그대로 잔여** — 칩 글꼴
  10.88px 의 가독성 판단은 여전히 전문 심사를 거치지 않았다.

## REV-20260901T125600-ai-claude-glossary-tier-postdeploy [SKIPPED:non-policy-doc] — 증적 기록 전용

- Related TASK: feature-0003-agent-web-ui (`20260901T1256-glossary-tier-postdeploy`)
- Reason: changed paths are docs only (test-runs.d fragment · TASK · MODIFY) — 정책 doc 밖,
  런타임 코드 변경 0. 코드 리뷰는 선행 cycle `REV-20260901T120000-ai-claude-metadata-term-scope`
  가 마쳤고 이후 코드 불변(배포본 `40340f53` 그대로).
- Timestamp: 2026-09-01T12:56:00+09:00
- 기록된 사실의 근거: `alembic_version=0058_glossary_term_tier` · 제품 목록 239건 중 상속 7건 ·
  폼 select 3선택지 · 큐 필터 6선택지 · 캡처 3장(`artifacts/pb0008-glossary-term-tier/`) ·
  배포 체크리스트 [1][2][1b][2b][5] 통과(`no upstreams available` 0건).

## REV-20260901T160000-kb-external-reach [SKIPPED:codex-no-output] — 지식베이스 외부 AI 도달 범위 (web 거주분)

리뷰 정본은 `unit/feature-0002-agent-core/docs/REVIEW.md` REV-20260901T160000-kb-external-reach
(cross-cut cycle — 코어·web 을 한 번에 판정). Cross-ref: CHG-20260901T160000-kb-external-reach
(양 feature) · ANCHOR 무충돌.

web 거주분에 한정한 요점:

- **[BLOCKING·해소] product scope 를 주변 상태에서 읽으면 계정 경계를 넘는다.** MCP 는 계정
  결속 도구다 — `cfg.get_active_product_scope()` 는 **서버 프로세스의** 활성 제품이라 A 계정
  질문에 B 제품 사전을 실을 수 있다. task 의 ProductId 에서만 해석하도록 봉인하고
  (`_bridge_product_scope_key`), 해석 불가 시 **빈 문자열**(= 제품 층 미주입)로 접었다.
- **[MINOR·해소] 헬퍼를 `@router.post` 데코레이터와 함수 사이에 끼워 SyntaxError.** 데코레이터
  아래로 이동. (즉시 발현이라 무해했지만, 편집 위치가 문법을 바꾸는 지점이다.)
- **도구 시그니처 불변이 설계 제약이었다.** `get_task_context` 의 이름·인자를 그대로 두고
  **반환 본문만** 넓혔기 때문에 러너(개인 AI) 재배포 없이 도달한다. 새 도구를 만들었다면
  러너가 그 도구를 부르도록 갱신될 때까지 아무 효과가 없었을 것이다.

Verdict: PASS (정본 판정에 종속).

## REV-20260901T115300-side-panel-exclusive [SUBAGENT:ux+design] — BLOCK ×2 → 수정 → 확인 라운드

- **Trigger**: `Code change` + §18.8 dispatch 표의 `UI, layout, dialog / 화면, 레이아웃` 매칭 →
  축 = **ux, design**. 백엔드·스키마·RBAC 변경 0 이라 security/backend/qa 축은 해당 없음.
- **채널(§18.8)**: 본 세션의 상위 지시가 subagent 호출을 금지한다(`Do not call the AgentTool
  unless the user requested it`). **자체 SKIP 하지 않고 사용자에게 확인**했다 — 1차 답변은
  `/codex review` 대체였으나 codex 사용 한도가 소진(15:44 해제)돼 실행 불가였고, 2차 확인에서
  **이번 단계 한정 AgentTool 패널을 허용**받아 §18.8 정본 경로로 수행했다.
- **1라운드 결과: ux `BLOCK` · design `BLOCK`** (아래 「라운드 1 지적과 처리」). 두 리뷰어
  모두 뮤테이션·격리 사본 실측을 근거로 제시했고, 제품 3건·가드 3건이 실효 결함이었다.
- **§18.8 수렴 계약(a)**: P1 을 수정했으므로 **확인 라운드 1회**를 돌렸다 — 수정한 라운드
  자체는 종결 근거가 아니다(수정이 새 결함을 만들 수 있으므로).

### 라운드 1 지적과 처리 (실효 판정)

| # | 축 | 지적 | 처리 |
|---|---|---|---|
| U-3 | 제품/접근성 | `.hidden` 이 `display:flex !important; translateX(100%)` 라 숨은 패널이 Tab·스크린리더에 남는다 → "하나만 열린다" 가 시각 사용자에게만 성립 | **수정** — 등록부가 `inert`/`aria-hidden` 동기화(배타 경로 동기 + 관찰 그물) |
| U-1 | 제품/UX | 배타 닫힘이 첨부 패널의 휴지통 모드·스크롤을 파기(재개방 시 무조건 `active` 리셋) | **수정** — 자동 닫힘 한정 스냅샷·복원. 사용자 × 닫기의 리셋은 그대로(의도) |
| U-2 | 제품/UX | 업로드 중·실패 pill 이 서버 목록에 없어 재개방 시 소실(실패 항목 회수 경로까지) | **수정** — 복원 경로에서 pending 있으면 pill 뷰로 |
| D-3 | 제품 | `registerSidePanel` 조용한 no-op — `colse:` 오타 하나로 배타 이탈, 증상은 «수정 전» 과 동일 | **수정** — 콘솔 보고 + 사후 단언 + pytest 형태 검증 |
| D-4 | 제품 | `catch {}` 가 close 실패를 완전 무음으로 삼킴 | **수정** — `console.error` + 사후 단언 |
| D-1 | 가드 | 우회 스캔이 `getElementById` 한 형태만 봐 `querySelector`·핸들 import·소유모듈-남의패널 3형태 통과(실측) | **수정** — 세 축 추가, 소유 면제를 자기 패널로 한정 |
| D-2 | 가드 | 스캐너가 «없다» 축에 리터럴 마스크 사용 + 중첩 템플릿 오독으로 파일 전체 마스킹(실측 false PASS) | **수정** — 모드 스택 파서 + 미종료 리터럴 예외 + «없다» 축 마스크 미사용 |
| — | 가드 | census 가 body 직속 `<aside>` 기준이라 `<div>` 오버레이는 밖, 올바른 확장을 오히려 FAIL | **수정** — `data-side-panel` 선언적 표식 |
| — | 가드 | 등록부 leaf 불변식 미강제 · 등록문 실행 여부 미검증 · 하네스 CI 미배선 | **수정 2 + 기록 1** — S1 leaf 단언, 줄머리 앵커, CI gap 은 S6 이 «기록» 을 강제 |
| — | 설계 | `openSidePanel` 로 열기까지 문 하나로 (호출 누락 실패 모드 제거) | **채택** |
| C1 | UX | Esc 로 닫을 수 없다 (3종 전부, 이 변경 이전부터) | **미채택(범위 밖)** — 새 키보드 계약 추가는 요청 범위를 넘는다. 후속 항목으로 기록 |
| §3 | 설계 | 단일 우측 dock + 탭 / `body[data-open-panel]` 단일 상태 정본 재설계 | **미채택(범위 밖)** — 요청은 "하나만 열리게" 다. 대안으로 아래 기록 |
| C4 | UX | ≤680px 에서는 프로필 진입점(좌측 사이드바)이 없어 계약이 관측되지 않는다 | **문서화** — 아래 「검증 범위」 |
| C3 | 검증 | 시나리오가 backdrop 합성 click 을 "실 사용자 경로" 로 라벨 | **수정** — `#closeProfileBtn` 클릭으로 교체, 라벨 정정 |

### 검증 범위 (정직 표기)

- 이 계약이 **관측되는 폭은 ≥681px** 다. ≤680px 에서는 `.sidebar { display:none }` 이라
  프로필 진입점 자체가 없고, 첨부·단계는 `max-width:92vw` 로 서로의 opener 를 덮어 두 번째
  패널을 열 방법이 없다 — 배타 코드가 실행될 일이 없다.
- 「프로필이 열린 상태에서 첨부/단계 열기」는 backdrop(z 195)이 화면 전체 클릭을 먹어 **실
  포인터로 도달 불가**하다. 방어적 계약이며 jsdom C4 가 잠근다.

### 라운드 2 (확인 라운드) 결과 — **BLOCK ×2**, P1 6 → 2 로 단조 감소

두 리뷰어가 **같은 회귀 1건**을 독립으로 지목했다(§18.8 (b) 판정: 비단조 아님 — 라운드를
더 돌린다).

| # | 축 | 지적 | 처리 |
|---|---|---|---|
| B1 | 제품(이 변경이 만든 회귀) | 배타 닫힘 스냅샷이 **대화 전환을 넘어 살아남아** 다른 대화가 휴지통 모드로 열린다 — REQ-20260806-attach-manage 가 없앤 결함의 부활. 두 리뷰어가 각각 정본 소스로 재현 | **수정** — 스냅샷에 `convId` 를 실어 **자기무효화**. 전환 choke-point 에 한 줄을 더하는 대신(다음 전환 경로마다 복제해야 한다) 스냅샷이 스스로 만료되게 했다 |
| B2 | 문서 | `FUNCTION.md` 계약·AC 가 라운드 1 **이전** 설계를 서술 — AC-4 가 구현에 없는 보장을 약속(실측 반증) | **수정** — 계약을 `openSidePanel` 중앙 열기로 다시 쓰고 AC 를 실제 검사 축(6종)·한계와 함께 재작성 |
| C-b | 제품 | 휴지통 모드로 복원할 때 pill 복원이 삭제분 목록을 덮어 «헤더는 휴지통, 본문은 활성» | **수정** — `deleted` 복원 시 pill 복원 건너뜀 |
| C-a/C8 | 제품 | `try { el.inert = … } catch` 는 **도달 불가 코드**(미지원 엔진은 던지지 않는다) → «읽히지 않는데 포커스는 가는» 최악 조합 가능 | **수정** — `"inert" in HTMLElement.prototype` 기능 검출 + 미지원 시 `aria-hidden` 도 걸지 않음 + CSS `visibility:hidden; pointer-events:none` 폴백 |
| C-d | 문서 | 모듈 주석이 세 패널의 `.hidden` 을 한 규칙으로 서술 — 프로필은 base `.hidden{display:none}` 에 걸려 이미 제거 상태 | **수정** — 주석·FUNCTION 정정 |
| C1 | 가드 | 소유 모듈 안에서 «네 번째 열기 지점» 은 여전히 통과(M4) | **수정** — **S7**: `hidden` 해제는 `openSidePanel(` 스팬 안에서만(형태-무관 축) |
| C2 | 가드 | 표식 없는 신규 오버레이는 census 밖(M6) | **수정** — **S8**: body 직속 오버레이 후보는 표식 **강제** |
| C3 | 가드 | `app.js` 면제가 파일 8천 줄 전체(M1) | **수정** — 핸들 획득 **선언 줄만** 면제 |
| C4 | 가드 | `[data-side-panel]`·클래스 선택자·`getElementsByClassName` 축 부재(M2·M3) | **수정** — 세 축 추가 |
| C5 | 가드 | 벤더 번들 9MB 를 손수 렉서로 훑어 무관한 산술이 계약 테스트를 붉게 함(M5) · 3회 중복 스캔 | **수정** — `vendor/` 제외 · 파일별 캐시 · 예외에 파일 경로 · `i++ /`·`}/` 오판 해소 |
| C6 | 가드 | 축약 속성·꼬리 주석에서 «틀린 진단» FAIL | **수정** — 축약형 인정 + 종단 완화 |
| C-c | UX | 「단계」 패널은 복원 대상에서 빠짐(무통보 소실) | **미채택 + 문서화** — 그 화면은 말풍선 「단계 보기」로 전부 재유도되지만 첨부의 목록 모드는 **서버 조회 파라미터**라 재유도할 곳이 없다. 비대칭의 사유를 FUNCTION 에 명시(design S2 의 권고안) |
| S-1/S-2 | 설계 | 「닫힌 원인별 분기」를 대화별 모드로 승격 · 사후 단언 술어를 계산 가시성으로 | **미채택(후속)** — 둘 다 이번 요청 범위 밖. 아래 「후속 과제」 |

### 라운드 3 (확인 라운드) 결과 — ux **CONCERN** · design **BLOCK ×2** → 수정 완료

두 리뷰어 모두 **제품 동작은 건전**으로 판정했고, BLOCK 사유는 «가드·문서가 실제보다 강하게
서술돼 다음 라운드의 판단 근거를 오염시킨다» 에 한정됐다.

| # | 축 | 지적 | 처리 |
|---|---|---|---|
| B-1 | 문서·가드 | 사후 단언이 `_panels` 만 순회해 **등록 누락 패널을 원리적으로 못 보는데**, FUNCTION·docstring 이 그것을 백스톱으로 인용(실측 반증) | **수정** — 열거 출처를 `[data-side-panel]` **DOM 표식**으로 바꿔 «등록 누락» 을 실제로 잡게 했다(하네스 C16). 못 덮는 것(문을 안 탄 열기)은 문장에서 **뺐다** |
| B-2 | 가드 | `scan_file`/`_SCAN_CACHE` 가 **호출자 0 인 dead code** — 「예외에 파일 경로」 보장이 부재 | **수정** — 배선 + `test_n5b` 로 경로가 실리는지 단언 |
| C-1 | 가드 | S7 의 고정 400자 창이 «12줄 떨어진» 평범한 형태를 놓침(실측 P4 생존) | **수정** — 창을 **수신 표현식 판정**으로 교체(인라인 조회 · 같은 함수 안 대입 변수). 하위 요소는 제외 |
| C-2 | 가드 | S8 후보 집합이 문서화된 한계보다 넓게 빔(작은따옴표·`<section>`·`<nav>`·중첩 5형태) | **수정** — `HTMLParser` attrs + **class 토큰** 판정으로 교체(따옴표·태그·중첩 무관). 남은 한계를 FUNCTION 에 실측대로 기재 |
| C-3 | 가드 | `_HANDLE_DECL` 이 줄바꿈·`let` 같은 **정당한 포맷**에 거짓 FAIL | **수정** — `\s*` 관대화 + `const\|let` |
| C-4 | 가드 | mjs 등록문 정규식이 pytest 와 갈려 꼬리 주석 한 줄로 **프로덕션 코드를 삼킴**(CI 미배선이라 조용히) | **수정** — 규약 정렬 + **내용 단언**(`looksLikeRegistration`) 추가 |
| C-5 / ux C3-3 | 제품 | `openFn()` 이 try 밖 — 렌더 예외 시 «남의 패널만 닫힌» 순수 손실 | **수정** — try/catch + 보고(하네스 C15) |
| ux C3-2 | 제품 | 복원 **비동기 꼬리**에 대화 동일성 가드 부재(B1 과 같은 계열의 async 축) | **수정** — 꼬리를 이름 있는 함수로 뽑아 같은 술어 적용(하네스 C18) |
| ux C3-1 | 검증 | pill 복원·scrollTop 축이 **어떤 게이트에도 없음** — 「20종 KILL」이 그 사각을 가림 | **수정** — 꼬리 추출로 구동 가능해져 하네스 C17/C18 이 덮는다. 뮤테이션 3종(pill guard·scroll·async guard) KILL 확인 |
| ux S3-1 | 설계 | A→B→A 왕복에서 스냅샷이 전환 리셋을 이김 | **명시적 선택 + 문서화** — 대화가 같으면 복원한다(AC-7 에 «그 대화의 뷰이지 그 방문의 뷰가 아니다» 로 기재). 시간 축은 후속 과제 「대화별 모드 승격」이 개념째 없앤다 |

### 라운드 4 (사용자 연장 승인, 확인 라운드) — ux **CONCERN** · design **BLOCK ×2** → 수정 완료

두 리뷰어 모두 «라운드 3 수정이 만든 **사용자 가시 회귀는 없다**» 로 판정했다. BLOCK 은
가드가 만든 **거짓 FAIL** 과 문서–코드 역전에 한정됐다.

| # | 축 | 지적 | 처리 |
|---|---|---|---|
| B4-1 | 가드(거짓 FAIL) | `_enclosing_fn_span` 이 `function f(a, { b } = {})` 의 **시그니처 중괄호**를 본문으로 오인 → 파일 전수 폴백 → 8천 줄 안의 동명 `panel` 이 무관한 커밋을 붉게 만든다(실측, `app.js` 는 이미 폴백 안) | **수정** — `extract_fn_span` 과 같은 규약으로 시그니처 괄호를 균형 매칭한 뒤 본문을 잡고, **화살표 함수**도 경계로 인정. 경계 미상은 offender 가 아니라 **«보류»** 로 센다(정적 층은 fail-open, 결과 층이 이중 방어) |
| B4-2 | 문서·가드 | AC-4 가 출하 코드와 **반대**를 서술(`x-side-panel` 을 «census 밖» 이라 했으나 실제로는 잡는다) + `declared_overlays`(정규식·큰따옴표 전용) vs `unmarked_overlays`(HTMLParser) **따옴표 비대칭** → 단일따옴표 마크업의 미등록 패널이 **두 축 모두 조용히 통과** | **수정** — census 를 HTMLParser 단일 경로로 통일(실측: 단일따옴표에서 `declared` 가 표식을 인식) + AC-4 를 출하 규칙·실제 한계로 재기술 |
| C4-1(design) | 가드 | `scan_file`/`_SCAN_CACHE` 가 «호출은 되지만 제거해도 차이 없는» 코드 + 캐시 0 read | **수정** — 삭제. 파일명 귀속은 `strip_comments_only(path=…)` 한 곳으로 통일 |
| C4-2 | 제품 | 사후 단언이 **id 없는 표식 패널**을 버림 | **수정** — 표식값/클래스를 대체 라벨로 |
| C4-3 | 가드 | `looksLikeRegistration` 의 `\bfunction\b` 금지가 `close: function(){}` 에서 pytest 와 다시 갈림 | **수정** — 술어를 «다음 문장을 삼켰는가»(`registerSidePanel(` 출현 1회)로 |
| C4-4 | 제품 | 열기 실패 시 `_syncInteractivity` 를 건너뛰어 «보이는데 inert» 가 남을 수 있음 | **수정** — 성공·실패 양쪽에서 동기화(문장 순서 전제 제거) |
| ux C4-1 | 검증 | 복원 꼬리 **배선** 축이 여전히 열림 — 호출 한 줄을 지워도 전건 green(실측) | **수정** — **S10**: 정의 스팬 밖 호출 존재를 단언 |
| ux C4-2 | 검증 | pill 스텁이 카운터만 세어 «누가 슬롯을 마지막에 썼나» 를 관측 못함 | **수정** — 더블이 실제로 슬롯을 덮게 하고 C17 을 **결과 축**으로(휴지통 마커 생존 단언) |
| ux C4-3 · S4-1 | 설계 | active 분기의 슬롯 클로버 · `activeConversationId` 타입 정규화 | **미채택(후속)** — 둘 다 라운드 2 산이거나 호출부 가드에 의존하는 가정. 「후속 과제」에 추가 |

### 라운드 3 재검증 (실측)

- `make test` **6466 outcome 0 FAIL** (ruff clean) · jsdom 행위 하네스 **66 PASS** ·
  구조 가드 pytest **22 케이스** · PB-0008 실 Windows 브라우저 **16 step ok**.
- **뮤테이션 전건 KILL** — 라운드 2·3 리뷰어가 «생존» 으로 제시한 형태를 전부 포함한다:
  등록 오타 · never-called 등록 · 배타 호출 제거 · 접근성 동기화 제거 · `app.js` peek ·
  `[data-side-panel]` 선택자 · 클래스 선택자 · 소유 모듈 4번째 opener · **12줄 떨어진 opener** ·
  표식 없는 신규 오버레이(**중첩 포함**) · CSS 폴백 제거 · convId 가드 제거 ·
  **async 꼬리 가드 제거** · **pill deleted 가드 제거** · **scrollTop 복원 제거** ·
  **사후 단언 열거 출처 되돌리기** · **openFn try 제거** · 꼬리 주석(정당 포맷, 거짓 FAIL 없음).
  각 주입은 `grep -c` 카운트 변화로 **적용 여부를 확인**한 뒤 판정했다(자기충족 역검증 회피).
- 정상 산술(`i++ / n`)·줄바꿈 선언·꼬리 주석이 거짓 FAIL 을 내지 않음을 대조군으로 확인.

### 후속 과제 (이번 범위 밖 — 기록)

- **Esc 로 닫기** — 세 패널 모두 × 버튼뿐이다. 「우측은 하나뿐」 규칙이 강해질수록 되돌리는
  관용 경로가 필요해진다. 등록부가 «지금 열린 것» 을 아는 유일한 지점이라 자리도 자연스럽다.
- **`_attachListState` 를 대화별(`byConv`)로 승격** — 그러면 «배타/× 닫힘 구분» 과 복원
  스냅샷이라는 개념이 통째로 사라진다(design S-1).
- **사후 단언 술어를 계산 가시성으로** — 지금은 `.hidden` 클래스를 본다. 인라인 스타일이나
  `[hidden]` 으로 감추는 형태가 생기면 조용히 통과한다(design S-2).
- **단일 우측 dock + 탭** 재설계 — 배타가 정의상 성립하고 되돌아가기 비용이 0 이 된다(ux §3).
- **복원 꼬리의 active 분기 슬롯 클로버** — `_renderAttachmentPills` 가 서버 목록을 통째로
  덮는다(라운드 2 산). 스냅샷에 `renderer: "pills" | "server"` 를 실으면 두 분기가 한 규칙이
  된다(ux 라운드 4 C4-3).
- **`activeConversationId` 타입 정규화** — 세 지점이 `(x || null)` 원시 비교를 쓰는데, 그
  술어가 옳으려면 전 경로에서 타입이 같아야 한다(현재는 호출부 `if (cid)` 가 막고 있다).
  `String(cid || "")` 헬퍼로 통일하는 것이 정합적이다(design 라운드 4 S4-1).

### 라운드 2 지적의 처리 상세
- **승인 근거(§12.2)**: `FIRST_REQUEST.md` `deploy_scope: included`. 위험도 **Minor**
  (§12.3 — frontend-only, 비파괴, 가역).

### 대안 분기

- **Alt-A: 각 opener 가 나머지 두 패널의 DOM 을 직접 `hidden` 처리.** 안 고른 이유 — 닫기 규칙이
  세 벌이 되고, 단계 패널의 라이브 티커 정지·프로필 backdrop 내림이 각 사본에서 빠진다.
  실제로 등록부가 DOM 만 감추게 만들면 티커가 화면 없이 계속 돌고 backdrop 이 남아 화면 전체
  클릭이 막힌다 — 하네스 C3·C4 가 그 두 실패를 각각 잠근다.
- **Alt-B: CSS 로만 해결(형제 선택자·`:has()`).** 안 고른 이유 — 보이지 않게 만들 뿐 **상태는
  열린 채**다. 닫기 버튼 접근 불가·티커 잔존 같은 실제 문제는 그대로 남는다.
- **Alt-C: `openSidePanel(key)` 를 등록부가 소유(열기까지 중앙화).** 안 고른 이유 — 열기는
  패널마다 다르다(너비 복원·탭 전환·목록 적재·backdrop). 중앙화하면 등록부가 세 패널의 세부를
  알아야 해 결합이 커진다. **닫기만** 공통화하는 것이 최소 계약이다.
- **좌측 `<aside class="sidebar">` 제외**: in-flow 그리드 컬럼이라 겹치지 않으며, 배타에 넣으면
  첨부를 여는 순간 대화목록이 사라진다. TASK.md 의 [다의어] 블록에 고른/버린 독해와 예시를 기록.

### 검증 채널 (§18.8 대체)

1. **jsdom 행위 하네스** `tests/verify_side_panel_exclusive.mjs` — **정본 소스의 함수 본문**과
   실 등록부 소스를 jsdom realm 에서 그대로 평가(추출·주입, stub 금지). **54 PASS**.
2. **역검증(§16.7 G11-b)** — ① main 원본 소스로 실행 → 추출 5건 FAIL, exit 1.
   ② 계약 호출만 제거한 뮤턴트(주입 여부를 `grep -c` 1→0 으로 **확인**) → 6 FAIL, exit 1.
   뮤턴트가 실제로 적용됐음을 확인한 뒤 판정했다(자기충족 역검증 회피).
3. **구조 가드 pytest** — 주석·문자열 리터럴 안의 계약 호출을 인정하지 않는 스캐너(§16.7 G11-a)
   + **DOM 전수 대조**(`data-side-panel` 표식 ↔ 등록부 + 표식 강제): 향후 4번째 패널이 등록을 잊으면 CI 에서
   걸린다(§16.7 G6 wiring 전수감사와 동형).
4. **적용면 전수감사(§16.7 G8-a)** — 세 패널 DOM 을 `getElementById` 로 집는 모듈이 소유 3모듈
   뿐임을 스캔으로 고정(S5·S7). 우회 열기 경로가 생기면 FAIL.
5. **PB-0008 실 Windows 브라우저** — 격리 컨테이너에 내 빌드를 마운트해 실제 클릭 경로로 4단계
   실측, BEFORE(main) 겹침 재현 캡처 동반. 상세는 `docs/test-runs.d/TASK-20260901T1153-side-panel-exclusive.md`.

### 알려진 gap (기록 — S6 이 이 문장의 존재를 단언한다)

- **side-panel-exclusive: 행위 하네스 CI 미배선** — `tests/verify_side_panel_exclusive.mjs`
  (jsdom 49 케이스)는 `make test` 의 agent 이미지에 **node 가 없어** pytest 에서 실행되지
  않는다(실측: `command -v node` 부재). 그래서 등록 성립·접근성 동기화·사후 단언은 로컬과
  PB-0008 게이트에서만 돌고, CI 에서는 구조 가드(S1~S5)가 그 대리 지표다.
  `tests/test_side_panel_exclusive.py::test_s6_*` 는 node 가 없으면 **조용히 skip 하지 않고**
  이 문장이 저장소에 있는지 단언한다 — 「검증 못 함」이 「검증함」으로 오인되지 않게 한다.

### 남은 리스크

- **역방향(프로필 열린 상태에서 첨부 열기)은 실 클릭으로 도달 불가**하다 — backdrop(z 195)이
  화면 전체 클릭을 먹기 때문. 그 경로는 방어적 계약이며 jsdom C4 가 잠근다(브라우저 실측 아님).
- 등록부는 **협조적**이다 — 새 패널이 `registerSidePanel` 을 부르지 않으면 배타에 참여하지 않는다.
  그 누락을 구조 가드 S3(DOM 전수 대조)가 잡는다. 다만 body 직속 `<aside>` 가 아닌 형태로 새
  오버레이를 만들면 census 밖이다(한계 명시).

## REV-20260901T163000-side-panel-exclusive-merge — origin/main 병합 충돌 자율 해결 (§16.4)

- **상황**: PR #1475 가 `origin/main` 대비 **43 커밋** 뒤처져 `mergeStateStatus=DIRTY`.
  `bin/setup-git-parallel.sh` (append-doc merge driver + rerere) 실행 후 `git merge origin/main`.
- **자동 병합된 것**: `static/app.js` · `app/composer.js` · `css/chat.css` · `index.html` ·
  `docs/STATUS.md` — **코드 충돌 0**.
- **자율 해결 (§16.4 «명료한 충돌» — append-only 양쪽 신규 항목 추가)**:
  `FUNCTION.md` · `MODIFY.md` · `REVIEW.md`(말미 append, main 것 먼저) ·
  `REPORT.md` · `TASK.md`(사이클 § 는 최신이 위) · `wiki/Log.md`(시간순) — 총 9 블록,
  **양쪽 항목 모두 보존**.
- **`wiki/hot.md`** 는 rewrite 문서(≤500자 캐시)라 기계 병합 대상이 아니다 — 양쪽 사실을
  합쳐 최신 2건으로 재작성(645자).
- **사람 판단 필요 항목 0** — 동일 함수/로직 상충 · HUMAN-LOCKED · 보안·비즈니스 로직 충돌
  없음. 병합 후 하네스 **67 PASS** · 구조 가드 **23** 재확인으로 내 변경이 병합에 소실되지
  않았음을 검증(핵심 심볼 `openSidePanel`·`registerSidePanel`·`_applyAttachRestoreAfterLoad`·
  `data-side-panel`·`visibility: hidden` 전수 잔존 확인).

## REV-20260901T163000-ai-claude-attach-lineage-uploader — 설계 판단 근거 (Minor §12.3)

### 왜 "소유권 단정 금지" 를 풀었나

선행 cycle(REQ-20260831)은 계보 문구가 소유권을 단정하지 못하게 막았다. 그 근거는 **목록
payload 에 업로더 account_id 가 없다** 는 사실이었지 원칙이 아니었다 — 없는 사실을 말하지
말라는 것이었다. 이번에 그 사실을 실었으므로 **아는 만큼만** 말하도록 연다. 여전히 지어내지는
않는다: 이름이 해소되지 않으면 「업로더 미상」이지 「내 파일」이 아니다.

### 이 cycle 의 발견 — 결함은 «모델이 모른다» 가 아니었다

사용자 3번째 질문(assistant 가 계보 현황을 파악하는가)을 **코드 읽기가 아니라 실 프롬프트
렌더**로 확인한 것이 나머지 둘의 성격을 바꿨다. `_build_attachment_context_section` 을 라이브
대화(`20260813083932`, 계정 10·50)에 caller 를 바꿔 가며 실행한 결과:

```
• uploaded by jmkimmasangsoft.com — v2 (attachment_id=1149, …)
• uploaded by admin — v1 (attachment_id=1150, …)  ← overall latest (newest by time)
```

per-lineage latest ↔ overall latest 두 축, 타 멤버 read-only 경계까지 이미 있었다. 즉
**같은 화면에서 모델은 업로더로 계보를 가르는데 사용자만 못 보고 있었다.** 그래서 이 작업은
기능 추가가 아니라 **비대칭 해소**이며, 그 원천 계약을 회귀로 함께 잠갔다(화면을 고치면서
프롬프트 쪽을 깨면 비대칭이 반대 방향으로 되살아난다).

### 판단 근거 · 버린 대안

- **왜 공유 대화에서만 이름인가**: 1:1 은 업로더가 늘 자기 자신이라 이름이 정보를 0 만큼 주면서
  240px 이름줄을 먹는다(§16.8). 판정은 저장소 단일 술어 `isGroupConversation` — 사이드바 그룹
  배지·전송 라우팅과 같은 신호를 쓴다(판정이 두 벌이면 화면끼리 어긋난다).
- **왜 행에서 파일명을 지웠나(문구만)**: 카드 머리가 이미 말한 이름을 행이 되풀이하면 좁은
  패널에서 갈래를 가르는 정보를 밀어낸다. 그러나 그 요소는 「원문 보기」 클릭 대상이자 접근성
  이름이라 **지우지 않고 문구만** 바꿨다 — `title`·`aria-label` 은 파일명 그대로다. 화면에서
  지운 것을 AT 에서도 지우면 어포던스가 조용히 사라진다.
- **왜 분기 칩을 좁혔나**: 정체성이 라벨로 올라갔으므로 칩이 정체성을 또 말하면 같은 행에서 같은
  사실이 두 번 나온다(사용자가 지적한 중복 축을 내가 다시 만드는 꼴). 칩은 「갈라졌다」만 진다.
- **버린 대안 (a)** 업로더 아바타(identicon) 표시 — `_msgAvatarEl` 관용구가 있어 가능하지만
  240px 폭에서 아바타가 라벨 폭을 먹고, 이름 텍스트가 이미 식별에 충분하다. 폭이 넉넉한 화면의
  후속 개선으로 남긴다.
- **버린 대안 (b)** 1:1 에서도 이름 표시 — 일관성은 얻지만 정보 0 인 문자열이 상시 폭을 먹는다.

### 노출면 검토 (직접 수행 — codex 채널 사용량 한도)

| 축 | 판정 |
|---|---|
| XSS | username 이 DOM 에 닿는 경로는 **정확히 2곳** — `_linTitle`(칩 title) · `_rowLabel`(행 라벨). 둘 다 `escapeHtml` 경유이며 그 구현이 `& < > " '` 를 모두 치환해 **따옴표 속성 컨텍스트에서도 안전**. |
| SQL injection | `IN ({_am})` 의 `_am` 은 `%s` 플레이스홀더만으로 조립되고 파라미터는 `int()` 강제 — 파라미터 바인딩. |
| 신규 노출면 | `account_id`/`uploader_username` 은 **대화 접근권으로 이미 게이트된** 엔드포인트로만 나간다. 익명 공유 뷰는 첨부 자체를 노출하지 않는다(`share.py`: "file attachments 는 conversation.file.read.* gated 이므로 공유 view 에서 hide"). 같은 사실이 `/versions` 의 `lineages[].account_id` 로 **이미** 나가고 있었고, 그룹 대화는 메시지 아바타로 멤버 username 을 이미 렌더한다(feature-0009). **새 노출 클래스 아님.** |
| 표시-집행 정합 | 삭제 어포던스는 종전대로 서버 `can_manage`(`_gate`) 판정만 따른다 — 업로더 이름 표시가 권한을 바꾸지 않는다. |

### 위험도

**Minor §12.3** — payload 필드 추가(비파괴) + 표현 계층. 스키마·마이그레이션·권한·엔드포인트
변경 0. 되돌리기 = revert + 재배포. 배포 사전 승인은 `FIRST_REQUEST.md` `deploy_scope: included`.

### 검증

pytest `feature-0003`+`feature-0002`+`feature-0023` **5167 passed / 5 skipped**(신규 11건) ·
`node --check` · `ast.parse` · **PB-0008 경계 3경로**(공유/1:1/단독) + 240px 폭 —
`docs/test-runs.d/TASK-20260901T163000-attach-lineage-uploader.md`.

⚠ `test_query_embed_visibility.py` 2건은 **main(`afcd1a42`) 기준선에서도 동일 실패** — 본 변경
무관(스위트 순서 의존, web-ui 테스트의 `sys.modules` 스텁 미정리). 별도 cycle 대상.

## REV-20260901T172000-ai-claude-attach-lineage-uploader [CODEX:feature-0003-attach-lineage-uploader] — PASS (P1 0 · P2 4 전건 조치)

- Related TASK: feature-0003-agent-web-ui (20260901T163000-attach-lineage-uploader)
- Source: codex review (codex-cli 0.146.0 `codex exec`, read-only, 판정 기준 `docs/CODE_REVIEW.md`)
- Trigger: UI/화면/레이아웃 + 정보 노출 keyword → §18.8 dispatch `ux, design`(+security 축).
  subagent panel 대신 codex 채널(§18.8.1 항목 2, check #9 accepted) — 본 세션은 Agent tool 제한.
- Timestamp: 2026-09-01T17:20:00+09:00
- Verdict: **PASS** — P1 **0건** · P2 4건 · P3 1건 → **전건 조치 + 라이브 실증**
- Human Approval Needed: no (Minor §12.3)

### P1 없음 — 노출면은 열리지 않았다

codex 확인: 익명 share 경로는 첨부 목록/serializer 를 통과하지 않아 `uploader_username` 신규
노출 없음 · `/api/conversations/{id}/attachments` 는 기존 대화 접근권 게이트 유지 ·
XSS 는 `escapeHtml`/`textContent`/`setAttribute` 경로로 차단 · 이름 조회는 단일 IN batch(N+1 아님).

### P2 4건 — 조치와 라이브 실증

| # | 지적 | 조치 | 실측 |
|---|---|---|---|
| 1 | `account_id` 를 **공유 serializer** 에 넣어 목록 밖(메타·`versions[]`·휴지통·history)까지 업로더 id 가 번짐 — 「목록에만 추가」 범위를 넘는 최소권한 회귀 | serializer 에서 빼고 **목록 엔드포인트가 자기 응답에만** 부착 | `/versions` 의 `versions[0].account_id` **부재** · `lineages[0].account_id` **유지**(기존 노출 불변) · 목록 `uploader_username="admin"` |
| 2 | 화면은 `Alice`/`Bob` 인데 **접근성 이름은 둘 다 「사용자 계보」** — 이 cycle 이 연 구분이 AT 사용자에겐 닫힌 채 | 화면 라벨과 **같은 출처**(`_selfIdentity`)를 aria 이름에 사용 | `…(jmkimmasangsoft.com, 2개 중 1번째) 원문 보기` / `…(admin, 2개 중 2번째) …` |
| 3 | 공유 여부를 `currentConversation()` 으로 판정 — 응답 지연 중 대화를 옮기면 그룹 A 의 행이 1:1 B 로 분류 | 판정을 `convId` 대응 객체로 + **stale 응답 자체를 버림**(목록이 남의 대화 것이 되는 상위 결함) | 가드 추가 후에도 정상 경로 렌더 확인(그룹 4 · 라벨 정상) |
| 4 | 같은 사람이 같은 이름을 독립 2회 업로드하면 두 행 모두 `Alice` 이고 분기 칩도 없어 **다시 구분 불가** | 라벨이 **겹칠 때만** 서수 덧붙임(흔한 2계보엔 군더더기 없음) + aria 동반 | 스텁 3계보 동일 업로더 → `사용자 업로드 · 계보 1/3·2/3·3/3`, aria `(사용자 업로드, 3개 중 N번째)` |

### P3 — 조치

머리 아이콘이 그룹 전체를 대표하게 됐으므로, 형제들의 `kind` 가 갈리면 첫 행 아이콘 대신
**중립 클립**으로 되돌린다(모르는 것을 단정하지 않는다).

### 자기 지적 — 내가 세운 원칙을 내가 어겼다

P2-2 는 이 cycle 이 MODIFY 에 「화면에서 지운 것을 AT 에서도 지우면 안 된다」고 적어 놓고,
정작 **새로 추가한 업로더 이름을 AT 에 싣지 않은** 것이다. 파일명은 지키면서 새 사실은 안 실은
반쪽 — 원칙을 문장으로 갖는 것과 그 원칙이 성립하는 것은 다르다.

또 P2-3 조치로 넣은 stale 가드는 **차단이 아니라 정상 경로**를 먼저 확인했다(§CODE_REVIEW 2.2):
가드 추가 후 공유 대화가 그대로 렌더되는지를 재실측했다 — 「막는 것만 확인하고 통과를 확인하지
않는」 결함 클래스를 피하기 위해서다.

### 회귀

신규 6건 추가(총 17건) + 기존 계약 4건 갱신. 각 지적의 복귀 경로를 개별로 막는다:
serializer 재오염 · aria/화면 출처 분리 · `currentConversation()` 복귀 · stale 가드 순서 ·
충돌 서수의 분기 이탈 · 혼합 kind 대표. pytest **5173 passed / 5 skipped**.
## REV-20260901T053000-ai-claude-corp-connect-modal-transition [CODEX:connect-modal-transition] — PASS (2R P1 0)

- Related TASK: feature-0003-agent-web-ui / `20260901T0530-connect-modal-transition`
- Source: codex exec (codex-cli 0.146.0) — 2 라운드
- Trigger: UI/모달 키워드(§18.8 표 3행). 세션 도구 제약으로 §18.8.1 경량 경로 —
  `ux`/`design` 은 이전 cycle 들과 같이 `[SKIPPED:tool-restricted:*]` 범위.
- Timestamp: 2026-09-01T05:30:00+09:00
- Verdict: **PASS** — 1R **P1 1** → 2R **P1 0**
- Human Approval Needed: no

### 사용자 요청 2건이 같은 뿌리였다

종전 판정 = «창을 열 때 **고정한** 기준선 대비 `listening` 의 false→true 전이».

- **명령 경로**: 기준선을 고정하므로, 열 때 «대기 중» 이었으면 그 뒤 실제로 끊겼다가 명령으로
  다시 이어져도 전이로 세지 않는다 — 그 창은 영영 닫히지 않는다.
- **«업데이트 필요» 갱신**: 갱신 중 `listening` 은 줄곧 참이고 `runner_stale` 만 풀린다.
  `listening` 만 보는 축은 이 경로를 **통째로** 놓친다.

기준을 **직전 관측**으로, 축을 **«쓸 수 있는 상태»**(`listening && !stale`)로 올려 둘을 한
규칙으로 덮었다. 실행 버튼 경로도 같은 축으로 통일했다 — 두 경로가 다른 축을 쓰면 실행 버튼만
«됐다» 고 말한다.

### codex 1R — P1 1건 (수정이 만든 새 결함)

> `_paintConn()` 이 `epoch` 검증 전에 `_lastObs` 를 갱신한다. 이전 모달의 늦은 응답이 현재
> 모달의 직전 관측으로 오염되면 `!ok → ok` 로 오판해 현재 모달을 **즉시 닫고 명령을 잃을 수
> 있다.**

정확한 지적이다. **판정을 «직전 관측» 기준으로 바꾸면 그 값 자체가 자산이 된다** — 남의 창
응답이 거기 섞이면 일어나지 않은 전이가 만들어진다. 창 세대가 다르면 **기록조차 하지 않도록**
고쳤고(갱신·판정을 함께 세대 검사 안으로), 그 경합을 겨누는 **J1** 을 신설했다.

**2R: P1 0** — 「epoch 불일치 응답은 `_lastObs` 갱신과 전이 판정 모두에 도달하지 않는다.」

### 검증

- **39/0 PASS**. 신설: I1(명령 재연결) · I2(업데이트 갱신) · I3(실행으로 갱신) · I4(낡은 채
  이어진 것은 성공 아님) · H5(실행했는데 낡은 러너) · J1·J2(오염 방지).
- **라이브 배포본에서 6건 FAIL**(I1c·I1d·I2c·I2d·I3b·I4) — 제보 두 경로가 실재함을 배포본으로
  확인.
- 뮤테이션: stale-blind-auto→I2c·I2d·I4 / stale-blind-launch→**H5** / msg-flat-auto→I2d·I3b /
  obs-pollution(P1 되돌림)→**J1**.

### 남은 위험 (정직 표기)

- **실행 경로의 문구 분기**와 **`_lastObserved.ok` 의 stale 검사**는 뮤턴트가 생존한다 — 자동
  관측 경로가 거의 항상 먼저 판정을 끝내 그 분기에 도달하지 않기 때문이다(방어적 중복,
  낡은-응답 경합에서만 쓰인다). 커버리지 구멍임을 숨기지 않는다.
- 남의 러너로 인한 오닫힘(직전 cycle 의 수용한 트레이드오프)은 그대로 남는다 — 서버의
  `listening` 이 계정 단위 판정이라 화면은 러너 소유를 구분할 수 없다.
- `_gateInFlight` 해제 전용 단언 없음 — 변동 없음.
- `ux`/`design` 도메인 심사 미수행 — 세션 도구 제약.

## REV-20260901T061000-transition-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 증적 (docs-only)

- Related TASK: feature-0003-agent-web-ui / `20260901T0530-connect-modal-transition`
- Reason: changed paths are docs + 스크린샷 자산만 — 코드·스키마·권한 변경 0.
- Timestamp: 2026-09-01T06:10:00+09:00
- Human Approval Needed: no
- **실측**: 배포본 `17d36ad8` 에서 A(명령 재연결)·B(«업데이트 필요» 갱신) 두 경로 모두 닫힘 확인.
  B 의 문구가 «최신으로 갱신되었습니다» 로 나와 상황과 일치한다.
- **미수행(정직 표기)**: 실 러너 기동·갱신 end-to-end. 조회·토큰 응답을 가로챈 프론트엔드 계약
  검증이며 검증 후 브라우저를 원상 복구했다.

## REV-20260901T170000-ai-claude-lineage-row-compaction [SKIPPED:non-policy-doc] — 표현 계층 전용 (Minor §12.3)

- Related TASK: feature-0003-agent-web-ui (20260901T170000-lineage-row-compaction)
- Trigger: UI/레이아웃 keyword → §18.8 `ux, design`. 변경이 **표현 계층 전용**(JS 렌더 문구·
  CSS 여백)이고 데이터·권한·API·노출면 델타가 0 이라, 직전 cycle 의 codex 라운드가 이미
  같은 코드 경로(그룹 카드·행 라벨·업로더 노출)를 P1 0 으로 종결했다. 그 위에 얹은 여백·문구
  축소는 새 위험 축을 만들지 않는다 — 판정은 **실측 게이트**(폭 4구간 행 높이·요소 개수)로 한다.
- Timestamp: 2026-09-01T17:00:00+09:00
- Human Approval Needed: no

### 판단 근거

- **왜 파일명을 지웠나**: 카드 하나에서 같은 이름이 6회 실렸다(머리 1 + 계보행 2 + 버전행 3).
  좁은 패널에서 그 반복이 정작 버전·계보를 가르는 정보를 밀어낸다. 지운 것은 **화면 문구**이고
  `title`·`aria-label`·클릭 대상은 그대로다 — 어포던스·AT 를 깎지 않는다.
- **왜 안내문을 지웠나**: 그 네 사실이 카드 머리·행 칩으로 옮겨가 **구조로** 표현됐다.
  REQ-20260828 이 문구를 넣은 근거(화면 어디에도 없다)가 소멸했으므로 문구도 함께 소멸한다.
- **왜 `uploaded` 를 감췄나**: 텍스트 첨부에서 정상이자 영구 상태라 모든 행에 붙는 영문 상수였고
  사용자가 할 것이 없다. 다만 **모르는 enum 은 계속 노출**한다 — 조용히 삼키면 새로 생긴 실패
  상태가 화면에서 사라진다(무음 실패 금지).
- **왜 한 줄을 끝까지 밀어붙이지 않았나**: AI 수정본 행은 **62px** 이 모자란다(필요 268 /
  가용 206). 되찾으려면 `버전 2개 ▾`(52px)·`+8KB`(34px)·`8/31`(30px) 중 무엇을 빼야 하고
  **셋 다 정보 손실**이다. 「잘림 대신 줄바꿈」이 이 패널의 기존 원칙이므로 임의로 자르지 않고,
  부족 폭을 수치로 남겨 **선택을 사용자에게** 돌린다. 한 줄을 위해 정보를 조용히 빼는 것이
  이 cycle 의 목적은 아니다.
- **버린 대안**: 넘칠 때 `text-overflow: ellipsis` 로 자르기 — 「버전 N개」 같은 **유일한
  진입점**이 잘려 사라진다(선행 cycle 이 정확히 그 이유로 말줄임을 되돌린 이력이 있다).

### 자기 지적

분기 칩을 글리프로 줄이면서 **파선 pill 껍데기를 그대로 뒀다** — 캡처에서 «빈 동그라미» 로
드러났다. 문구를 줄이면 그것을 담던 그릇도 다시 봐야 한다는 것을, 캡처가 없었으면 놓쳤다.

### 회귀

신규 4건 + 계약 이전 6건. pytest **5177 passed / 5 skipped**.
⚠ `test_query_embed_visibility.py` 2건은 main 기준선 동일 실패(본 변경 무관).

## REV-20260901T174000-side-panel-exclusive-postdeploy [SKIPPED:non-policy-doc] — POST-DEPLOY 기록

- **Trigger**: 비정책 doc-only (test-runs.d fragment + TASK/MODIFY/REPORT). §18.8 dispatch 표의
  「비정책 doc-only」 행 → panel SKIP.
- **내용**: 선행 cycle 의 §16.3 deploy-backed 완료 조건 2 를 기록. 코드·계약 변경 0.
- **정직 기록**: `bin/deploy-web.sh` 는 **멱등 no-op** 으로 끝났다 — 병렬 세션이 이미 내 머지를
  포함하는 상위 커밋(`d3ead999`)으로 배포한 뒤였다. 그래서 완료 근거를 「내가 배포 명령을
  돌렸다」가 아니라 **「라이브가 내 커밋을 담고 있다」** 4축 실측으로 세웠다(§16.7 G7-a —
  이름·명령 이력이 아니라 실 resolve).

## REV-20260902T010304-doc-sync-rn-0902 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-09-01 블록 신설(17항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260902T010304-doc-sync-rn-0902`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-09-02T01:03:04+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · `verify_release_notes.mjs` **34/0 = 편집 전 baseline 동일(회귀 0)** · 구조 실측(`releases` 57→**58** · `generated`=="2026-09-01"==`releases[0].date` · `releases[0].items` **17** + summary · 총 항목 424→**441** · **08-31 이하 tail 바이트 동일**(순증 25,734B) · type/area enum 위반 0 · 스키마 외 키 0 · date 중복 0) · 누출 스캔 19패턴 실질 **0건**.
- **적대검증**: ULTRACODE 워크플로 `wf_53f46008-931` — 6 에이전트 / **1,076,425 토큰** / 320 tool-use / 42분. 4축 병렬 스윕 → 2조 교차검증(정본대조 렌즈 / 기계적용 렌즈, 각자 MISS 능동 탐색). **60 findings · 120 verdict**(58/60 · 57/60 CONFIRMED · 56 이중 confirm) · 신규 MISS 5건.
- **블록 귀속**: 창 125 커밋 중 **123 건이 2026-09-01 착륙**(나머지 2건은 08-31 20:29~20:30 — 직전 창 컷 19:40 이후에 들어온 경계분)이고 09-01 date 블록이 **부재**하므로(최신 2026-08-31) 기존 블록 append 가 아니라 **신규 블록 prepend**. 경계 2건(첨부 계보 「비교 가시성」 재설계)은 09-01 의 후속 2 cycle(업로더 식별 · 행 압축)과 한 서사로 묶이므로 09-01 블록에 함께 실었다 — 08-31 블록을 소급 수정하지 않는다(과거 블록 불가침).
- **미러 vs 정본 수렴 — 재발 3건**: 직전 08-31 블록이 ① 「'답변 모델'·'추론 강도' 를 고르는 칸에서 바로 보이므로 **없앴습니다**」 ② 연결 창이 「스스로 **닫힙니다**」 ③ 쿼리 결과가 「그 안에서만 스크롤되도록 **가뒀습니다**」로 단정했으나, 창이 셋 다 다시 고쳤다(①은 사용자 머신 설치본이 옛 사본이라 계속 노출 · ②는 실행 성공·명령 경로·업데이트 갱신 세 갈래 미작동 · ③은 그 접이판 자체를 제거). 과거 블록은 그 시점 사실의 기록이므로 고치지 않고 새 항목에서 재발을 명시해 수렴했다.
- **기능 소멸 고지**: ③의 접이판 제거로 **CSV 내려받기 · 전체 데이터 보기 · 구형 메시지의 실행 SQL/결과 파일** 3종이 함께 사라졌다 — 개선 항목 뒤에 숨기지 않고 손실로 명시했다.
- **미검증 고지**: 이번 창 코드는 전부 라이브 도달을 실측했으나(`merge-base --is-ancestor` 로 창 주요 커밋이 배포본 조상임을 확인), **행위 실측**을 못 한 5축(중단 왕복 · 실패 사유 사용자 왕복 · 낡은 러너 겹침 · 인젝션 오판 왕복 · 경량 모델 일부 AI)은 각 항목 detail 과 **접힌 summary 양쪽**에 그 사실을 노출했다.
- **문면 규약**: feature-id·테이블명·함수명·파일명 노출 0건. 인용한 UI 문구(`[내 AI 실행]`·「단계 보기」·「브리지 작업」·「연결 준비」·'▼ 쿼리 결과'·'AI 운영 현황')는 전건 static 파일에서 실제 노출 문자열임을 grep 확인 후 사용했다.
- **cache-buster**: 수기 bump 없음(3창 연속). 소스는 `?v=dev` 고정이고 빌드 `inject_asset_stamp` 가 content-hash 를 주입하며(라이브 실측 `?v=b85ff1d4986d`) `bin/deploy-web.sh` 의 ABORT 가드가 **baked 이미지의 `?v=dev` 잔존 여부로 주입 누락을 판정**한다 — 수기로 실값을 박으면 주입이 실패해도 가드가 통과하므로 규약 위반에 그치지 않고 배포 안전장치를 무력화한다. 이번 run 의 cron wrapper 지시문이 조건 없이 'bump 포함' 을 지시했으나 저장소 정본(`docs/CONVENTIONS.md`)과 정면 충돌하므로 따르지 않았다.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수**(누락 시 사용자가 캐시된 옛 데이터를 본다).

## REV-20260902T110000-kb-prompt-grounding [SKIPPED:codex-no-output] — KB 근거 자동 주입 (web 거주분)

리뷰 정본은 `unit/feature-0002-agent-core/docs/REVIEW.md` 동명 항목(cross-cut cycle).
Cross-ref: CHG-20260902T110000-kb-prompt-grounding · ANCHOR 무충돌.

web 거주분 요점:

- **[BLOCKING·해소] 가드 래퍼로 매칭하면 래퍼가 근거를 만든다.** `claim_request` 안에서 손에
  잡히는 질문 변수는 `marked`(canary + ⟦…⟧ 각인 포함)다. 그걸로 용어를 매칭하면 래퍼 문구
  안의 낱말이 걸려 **질문과 무관한 근거**가 실린다. 각인 전 원문 `question` 으로 고정했고
  뮤턴트 P3 가 이를 잠근다.
- **[의도] 근거 없으면 블록 생략.** 빈 머리글만 남기면 AI 는 「등록된 게 없다」로 읽는다.
  같은 생략이 **옛 서버 호환**(이 필드를 안 보내는 버전)도 지킨다 — 러너가 사용자 머신
  설치본이라 서버·러너 버전 조합이 항상 어긋날 수 있다.
- **[미검증]** 프롬프트 크기 증가의 토큰·지연 영향. 상한은 뒀고 실사용 관측은 배포 후.

Verdict: PASS (정본 판정에 종속).

## REV-20260903T010309-doc-sync-rn-0903 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-09-02 블록 신설(15항목) doc_sync 정합
- Related TASK: feature-0003-agent-web-ui / `20260903T010309-doc-sync-rn-0903`
- Reason: changed paths are docs + 비-정책 static data only — 코드·스키마·권한 변경 0(릴리즈노트 콘텐츠 데이터 + companion 문서).
- Timestamp: 2026-09-03T01:03:09+09:00
- Human Approval Needed: no
- **타깃별 실질 검증**: `node --check` PASS · `verify_release_notes.mjs` **34/0 = 편집 전 baseline 동일(회귀 0)** · 구조 실측(`releases` 58→**59** · `generated`=="2026-09-02"==`releases[0].date` · items **15** + summary · 총 항목 441→**456** · `date: "2026-09-01"` 이하 바이트 동일) · 누출 스캔 47패턴 **0건**.
- **적대검증**: ULTRACODE 워크플로 `wf_0c1fdc18-fd9` — 6 에이전트 / **1,208,678 토큰** / 395 tool-use / 38분. 4축 병렬 스윕 → 2조 교차검증(정본대조 렌즈 / 기계적용+거버넌스 렌즈, 각자 MISS 능동 탐색). 릴리즈노트 축 finding 은 **양 렌즈 CONFIRMED**, 정본대조 렌즈의 MISS 1건(아래 미검증 고지 보강)을 수용했다.
- **블록 귀속**: 착륙일 `2026-09-02` 의 date 블록이 **부재**(최신 09-01 · `grep '2026-09-02'` 히트 0)하므로 append 가 아니라 **신규 블록 prepend** + `generated` 전진. 직전 RN 커밋 `55905283`(09-01 블록)이 델타 창 안에 들어오지만 그 블록이 다룬 원본 작업은 전부 직전 창(`d1a32fc4..d2d43b1f`)에 있어, 이번 창 74커밋 중 09-01 블록에 이미 서술된 것은 **0건**임을 항목별로 대조했다.
- **미러 vs 정본 수렴 — 재발·반증 4건**: 직전 블록들이 ①「'업데이트 필요' 를 누르면 최신으로 갱신됐다고 알려 드립니다」 ②「답을 받지 못한 AI 는 목록에 아예 넣지 않습니다」(4차 재발) ③「콘솔이 맡기는 작업은 가벼운 모델로 처리합니다」 ④「용어와 표 설명이 실제로 전달됩니다」로 단정한 넷을 이 창이 다시 고쳤다. 두 블록이 같은 화면에 연속 렌더되므로 새 항목에서 재발 경위를 명시했다(정본 오판 인정 문면을 근거로 인용).
- **미검증 고지 9건**: `summary` 말미 + 각 `detail` 양쪽에 배치했다(릴리즈노트 UI 가 접힌 상태에서 `summary` 를 먼저 보여주므로 detail 에만 두면 가장 필요한 자리가 무방비다). 적대검증이 추가로 잡은 1건 — 능력 질의 배포 후 재측정이 두 런타임 중 **한쪽만** 성공(다른 쪽은 그 머신 사용량 한도 소진) — 을 보강했다.
- **제외 판정(다음 창이 반증할 수 있게)**: 러너 18모듈 분할·배포본 이중화 제거(개발 충돌 해소 · 화면 무변화) · AI CLI 허용목록 정본 동기화(직전 창 사용자 결정의 잔재 정합 · 웹 자산 변경 0) · datasource health 텔레메트리 유실(관리 콘솔 화면 노출 경로 grep 0건) · 문서·증적·테스트·템플릿 업그레이드 전량 · WIP 중간 커밋(최종 재설계 판본으로 흡수 · 정본이 철회한 분은 미서술).
- **문면 규약**: feature-id·테이블명·함수명·파일명 노출 0건. 인용한 UI 문구는 `static/` grep 으로 실제 렌더 경로 실측 확인했고, 실측에 실패한 초안 2건은 반증돼 교체·삭제했다.
- **cache-buster**: 수기 bump 없음(**4창 연속 동일 판정**). 소스는 `?v=dev` 고정이고 빌드가 content-hash 를 주입하며 `bin/deploy-web.sh` ABORT 가드가 baked 이미지의 `?v=dev` 잔존으로 주입 누락을 판정하므로, 수기 실값은 규약 위반에 그치지 않고 배포 안전장치를 무력화한다. 이 run 의 cron wrapper 지시문도 조건 없이 bump 를 지시했으나 따르지 않았다 — 소유자 정정 대상.
- **landing/배포 소유권**: 무인 cron wrapper v3 — 본 skill 은 로컬 commit 까지만. push·main ff-merge·web 배포·헬스체크는 wrapper 소유. **서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 반드시 수행돼야** 사용자가 새 블록을 본다(committed ≠ serving).


## REV-20260903T210000-ai-claude-corp-feature-0003-conn-chip-css-scope [SKIPPED:tool-restricted:adversarial-subagent] — ACCEPTED

- Related TASK: TASK-20260903T210000 · Timestamp: 2026-09-03T21:00:00+09:00
- Verdict: PASS · Human Approval Needed: no
- Reason: 본 세션은 `Agent` 서브에이전트 호출이 사용자 명시 요청 없이는 금지된다. 대신
  **결손 재주입**(닫는 `}` 제거)으로 「테스트가 이 결함을 실제로 잡는가」를 직접 관측했다.

### 이 cycle 이 스스로에 대해 배운 것

직전 cycle 의 `test_checking_state_has_its_own_style_and_is_not_green` 는 **파일 텍스트에
규칙이 있는지**만 봤다. 있었다. 그래서 초록이었고, 화면은 무스타일이었다 — 이 저장소가
반복해 만든 「방어를 넣었다 ≠ 방어가 성립한다」 부류다. 실 렌더 실측이 그 간극을 열었고,
이제 정적 축(중괄호 깊이)이 커밋 시점에 같은 형태를 잡는다.

초판 판정축은 **항진 검사**였다 — 「`@media` 안에 칩 규칙이 있으면 결함」으로 짰더니
정당한 dark-mode 덮어쓰기 5건이 전부 결함으로 신고됐다. 축을 「무조건 규칙이 있는가」로
바로잡았다. 조치 방향을 뒤집는 그 형태를 이 저장소에서 여러 번 만들었으므로 기록한다.

### 남긴 미검증

- 이 검사는 **정적**이다. 실제 캐스케이드(더 구체적인 셀렉터가 덮는 경우)는 잡지 못한다 —
  그 축은 PB-0008 실 렌더 실측이 담당하며, 이 cycle 도 그것으로 적발했다.
- `search-audit.css` 의 **다른** 컴포넌트에도 같은 형태가 있는지는 보지 않았다.
  중괄호 균형 검사가 파일 전체를 보므로 「블록 미닫힘」 형태는 전부 걸리지만,
  「기본 규칙 없이 조건부만」 축은 `.ai-conn` 에만 적용된다.


## REV-20260903T220000-ai-claude-corp-feature-0003-chip-postdeploy [SKIPPED:docs-only] — ACCEPTED

- Related TASK: TASK-20260903T210000 · Timestamp: 2026-09-03T22:00:00+09:00
- Verdict: PASS · Human Approval Needed: no
- 문서만 바뀌므로 코드 리뷰 대상 없음. 대신 **기록한 숫자가 실측인지**를 자기검증했다 —
  세 조건 전부를 실 브라우저 `getComputedStyle` 로 직접 읽었고, 러너 사건(`caps.liveness_ok`
  /`caps.liveness_fail`)과 서버 원장(`account_ai_health`)을 같은 시점에 대조했다.
- 의심 지점을 넘기지 않았다: 첫 워커가 `checking` 셀렉터 **0건**을 냈는데 계산 스타일은
  적용돼 있었다 — 모순을 그대로 두지 않고 `CSSRule.MEDIA_RULE` 명시 재귀로 고쳐 7건을
  확인했다. 또 계정 10 의 최신 토큰이 NULL 로 회전한 것을 보고 「회전이 판정을 리셋하나」를
  직접 확인했다(리셋하지 않는다 — 읽기가 하트비트 토큰을 본다).
- 미검증을 숨기지 않았다: 다크 모드 실 렌더 미측정 · 질문 발송 후 확인 실패 창(30초)의
  종단 보장은 P0-AK 소관.

## REV-20260904T060000-ai-claude-visual-verified [SKIPPED:검증 기록] — ACCEPTED
- Timestamp: 2026-09-04T06:00:00+09:00
- 미뤄 둔 게이트를 **실제로 닫았다**. 미룰 때 「게이트를 통과시키려 적은 것이 아니다」라고
  썼고, 그 말을 지켰다.
- 재검증 초기에 계속 실패했는데 원인은 **내가 낡은 설치본을 시험**하고 있었다는 것이다.
  코드를 두 번 더 랜딩했는데 설치본은 그 전 것이었다. 「고쳤다」와 「그 고침이 내가 시험하는
  물건에 들어 있다」는 다른 축이고, 이 저장소가 반복해 배운 그 형태다. **해시 대조**로만
  갈라졌다 — 배포본 검증에는 항상 해시를 먼저 본다.

## REV-20260904T010301-ai-claude-doc-sync-20260904-010301 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-09-03 블록 신설 (doc_sync 09-04)
- Related TASK: TASK-20260904T010301-doc-sync-rn-0904
- Timestamp: 2026-09-04T01:03:01+09:00
- 범위: `src/static/release-notes-data.js` **데이터 블록 1개 prepend + `generated` 전진**. 렌더 로직(`release-notes.js`)·HTML·캐시버스터 토큰 **무접촉**. 제품 코드 변경 0.
- **[SKIPPED] 사유**: §18.8 표 첫 행 — 사용자향 릴리즈노트는 비정책 doc(정적 큐레이션 데이터)이라 적대 패널이 볼 코드 표면이 없다. 대신 전용 하네스로 검증했다.
- **검증**: `node --check src/static/release-notes-data.js` PASS · `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34/0**(baseline 동일), 첫 그룹이 「2026년 9월 3일」로 렌더됨을 하네스가 단정. `releases` 59→60 · `generated` 09-02 → 09-03.
- **평이화 준수**: 내부 구현·모듈명·테이블명·feature-id 비노출. 화면에 그대로 나타나는 라벨(「답할 수 있음」·[내 AI 실행] 등)만 그대로 인용.
- **미검증 정직 표기**: 개명 하드 컷오버의 실 OS 핸들러 재등록·옛 잔재 삭제와 네이티브 클라이언트 설치 경로는 **사용자 머신에서만 관측**되므로 해당 항목과 접힌 summary 양쪽에 그 사실을 명시했다.
- **캐시버스터**: 수기 bump 하지 않았다 — 소스 `?v=dev` 고정 + 빌드 주입 + 배포 ABORT 가드 계약(`docs/CONVENTIONS.md`). 수기 실값은 그 안전장치를 무력화한다.
- Human Approval Needed: **아니오**.

## REV-20260904T200000-ai-claude-webshell-verified [SKIPPED:검증 기록] — ACCEPTED
- Timestamp: 2026-09-04T20:00:00+09:00
- 이 cycle 은 코드를 바꾸지 않고 **미룬 검증을 실제로 수행**한다. 미룰 때 「게이트를
  통과시키려 적은 것이 아니다」라고 썼고 그 말을 지켰다.
- 실측하며 드러난 것을 결함/인공물로 **갈라 적었다** — 앱 창의 로그인 화면은 프로필 차이라
  결함이 아니고, gemini 미측정은 커버리지 과장을 피한 결과다. 둘을 뭉뚱그리면 다음 사람이
  「알려진 문제」 목록을 믿지 못한다.


## REV-20260904T200000-ai-claude-standalone-launch [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-04T20:00:00+09:00

**계약 자체가 요구와 어긋나 있었다.** 진입점 테스트는 있었고 통과했다 — 단정이 「인자가
없으면 안내를 낸다」였기 때문이다. 그것이 그때의 계약이었으므로 테스트는 옳았다. 어긋남은
**실행해 본 사람**만 볼 수 있었다. 테스트가 계약을 지킨다는 것은 그 계약이 옳다는 뜻이 아니다.

**편의를 위해 신뢰를 낮추지 않았다.** 「인자 없이도 열려면 주소를 기억해야 한다」에서 가장
쉬운 길은 딥링크를 받자마자 `pin_server` 를 부르는 것이었다. 그러면 **실패한 주소가 고정**되고
다음번에 그것이 「전에 쓰던 곳」으로 신뢰받는다 — TOFU 경고가 뒤집힌다. 키를 갈라, 창을 여는
근거(약함)와 러너를 내려받는 근거(강함)를 분리했다.

**새로 여는 표면 두 개를 인정한다.**
1. 파일에서 읽은 문자열이 브라우저 창의 목적지가 된다 → `http(s)`+호스트 검사.
2. 패널이 연결값을 준다 → `base` 는 아는 서버여야 하고, 사람 확인은 **그대로 남는다**.
   값의 출처가 바뀌었다고 확인이 약해지면 XSS 시나리오의 마지막 방어선이 사라진다.

**단일 인스턴스는 이번 변경이 만든 위험의 가드다.** 인자 없는 실행이 실제로 무언가를 하게
되면서 두 벌이 뜰 수 있게 됐다. 범위를 넓힌 것이 아니라 넓어진 표면을 덮은 것이다.

**정직하게 남기는 것**: 사용자 머신에는 `server.json` 이 **없다**(확인함 — CA·러너는 있는데
고정은 없다). 즉 이 변경만으로는 그 머신의 첫 실행이 여전히 「모른다」로 간다. 그래서
`--service-base` 로 배포 기본값을 동봉해 전달본을 다시 만든다. **그 실측 전까지 이 항목은
완료가 아니다.**


## REV-20260904T210000-ai-claude-standalone-launch-codex — codex 적대 리뷰 (외부) — ACCEPTED
- Timestamp: 2026-09-04T21:00:00+09:00
- 방법: `codex exec --skip-git-repo-check` 에 **위협 모델과 새 코드만** 인라인(334줄). 실행 금지·
  최대 6건·3줄 형식. (전체 diff 를 실으면 무응답이 되는 것을 이미 겪었다.)
- 6건 중 **4건이 실제 결함**이었다. 자가 리뷰가 놓친 것들이고, 놓친 이유가 서로 다르다.

**[HIGH] 딥링크의 `base` 에는 검증이 걸려 있지 않았다 — 수정.**
파일에서 읽은 값에는 `file:`·`javascript:` 차단을 걸어 놓고, **공격자가 가장 쉽게 넣는 쪽**인
링크에는 안 걸었다. `dqa-connect://start?base=file%3A%2F%2F%2FC%3A%2F…` 하나로 로컬 파일이 앱
창에 뜬다. 같은 문자열이 같은 곳(브라우저 창의 목적지)으로 가는데 **한쪽만** 검사하고 있었다 —
가드를 만든 사람이 그 가드가 덮어야 할 입구를 세지 않은 형태다. 이름을 `usable_base` 로 올려
두 입구가 같은 것을 쓴다.

**[HIGH] 링크가 동봉값을 이기는 순서였다 — 수정.**
`pin → last → bundled` 이었다. 그러면 **악성 링크 한 번**이 그 뒤 모든 무인 실행의 목적지를
조용히 바꾼다 — 사용자는 아이콘을 눌렀을 뿐인데 남의 사이트가 「DQA」로 뜬다. 편의를 위해
「받아들인 링크를 기억한다」를 넣으면서, 그 기억이 **설치 시점에 우리가 넣은 값보다 강해지는**
것을 보지 못했다. `pin → bundled → last` 로 바꿨다. 서버가 진짜 옮겨 갔다면 **연결에 성공한
순간** `pin` 이 그것을 반영한다 — 링크만으로는 못 옮긴다.

**[HIGH] 홈의 기록은 인증되지 않는다 — 완화(수용 아님).**
`~/.dqa-connect/server.json` 에 쓸 수 있는 상대가 다음 무인 실행의 목적지를 정할 수 있다.
매 실행 확인창은 답이 아니다(사람이 습관적으로 넘기면 정작 그때도 넘어간다). **동봉값과 다를
때만** 묻는다 — 정상 사용에서는 절대 뜨지 않고, 바뀌었을 때만 주소가 눈에 보인다.
⚠ 완전한 방어는 아니다. 그 홈에 쓸 수 있는 상대는 러너의 `config.json` 도 쥔다. 동봉값이 없는
빌드(개발용)에는 대조할 것이 없어 이 겹이 없다 — 그 사실을 여기 적어 둔다.

**[MEDIUM] 봉투가 지문을 생략하면 기존 기준을 빈 값으로 덮었다 — 수정.**
`install_ca` 는 기대값이 비면 대조를 **건너뛴다**(`if plan.ca_sha256 and …`). 서버가 지문을 못
낸 회차에 봉투가 그 칸을 비워 오면 「받아서 그냥 실행」이 된다. 새 값이 오면 이기고, 안 오면
있던 것을 지킨다. — 새 경로를 열면서 **기존 가드의 전제**(값이 있다)를 함께 옮기지 않은 형태다.

**[MEDIUM] `server.json` 이 잠금 밖 read-modify-write 였다 — 수정.**
기록을 **잠금을 잡은 뒤로** 옮겼다. 두 번째 실행은 어차피 먼저 뜬 창을 다시 열 뿐이므로,
그쪽이 주소를 기록하는 것 자체가 앞뒤가 안 맞았다.

**[LOW] 잠글 수 없으면 fail-open — 수용(문서화된 결정).**
잠금은 **편의이지 안전 장치가 아니다.** 잠금 파일 하나 때문에 앱이 안 뜨는 쪽이 나쁘다.
결과는 브리지·러너가 두 벌 뜨는 것이고, 그것은 보안 경계를 넘지 않는다.

**[HIGH로 보고됐으나 이번 변경이 만든 것이 아님] 첫 링크는 확인 없이 통과한다.**
TOFU 의 정의 그대로이고 `core.server_changed` 에 그 근거가 적혀 있다(물을 근거가 없다).
이번 변경으로 **더 나빠지지는 않았다** — 오히려 위 두 수정으로 「첫 링크가 영구히 자리를
차지하는」 경로가 좁아졌다. 첫 연결의 신뢰를 바꾸는 것은 별도 결정이다.

- 회귀: 뮤테이션 **6/6 KILL**(네 수정 각각 + 잠금 밖 기록 두 형태). 누적 **36/36**.


## REV-20260904T220000-ai-claude-embedded-window [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-04T22:00:00+09:00

**«화면은 서비스에 하나»를 깨지 않았다.** 이 저장소는 러너를 동봉하지 않기로 이미 결정했고,
그 근거(배포가 갈리면 「고쳤는데 그대로」가 재발한다)는 화면에도 그대로 적용된다. 이번에
동봉하는 것은 **창틀**이지 화면이 아니다 — 페이지는 여전히 서버가 서빙한다. 그 구분이
없으면 이 변경은 직전 주기가 기각한 구조로 되돌아가는 것이 된다.

**껍데기가 셋이 됐다 — 그 값을 치를 만한지 따졌다.** 늘리면 드리프트가 는다(이 주기에도
`run_client` 를 쪼개면서 소스 검사 테스트 5건이 엉뚱한 함수를 보게 됐다). 그래도 남긴 이유:
WebView2 런타임이 없는 머신에서 «아무 창도 안 뜨는» 것이 이 프로젝트가 반복해 겪은 최악의
형태이고, 크로미움 계열이 있으면 tkinter 보다 훨씬 낫기 때문이다. 대신 **트레이 메뉴가
셋 다 같은지**를 테스트로 잠갔다 — 사용자에게 이 프로그램은 하나다.

**가장 위험한 한 줄은 `allow_hide` 다.** 닫기를 숨김으로 바꾸는 판단이 트레이 존재와 어긋나면
창도 아이콘도 없는 프로세스가 남는다. 그래서 ① 껍데기가 트레이를 세운 **결과**로만 참이 되고
② 숨기기가 실패하면 닫히는 쪽을 고르며 ③ 뮤테이션으로 세 갈래를 각각 죽였다.

**정직하게 남기는 것**
- 로그인 세션이 브라우저와 갈린다. 사용자는 앱에서 **한 번 더** 로그인해야 한다.
- WebView2 런타임이 없는 머신은 여전히 브라우저 껍데기로 내려간다 — 「내장」이 보편은 아니다.
- `pywebview`·`pythonnet` 이라는 서드파티가 껍데기에 들어왔다. **러너는 그대로 stdlib 전용**
  이고 두 축은 섞이지 않는다(빌드가 각각 검증한다).

## REV-20260907T010301-ai-claude-doc-sync-20260907-010301 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-09-04 블록 신설 (doc_sync 09-07)
- Related TASK: TASK-20260907T010301-doc-sync-rn-0907
- Timestamp: 2026-09-07T01:03:01+09:00
- 범위: `src/static/release-notes-data.js` **데이터 블록 1개 prepend + `generated` 전진**. 렌더 로직(`release-notes.js`)·HTML·캐시버스터 토큰 **무접촉**. 제품 코드 변경 0.
- **[SKIPPED] 사유**: §18.8 표 첫 행 — 사용자향 릴리즈노트는 비정책 doc(정적 큐레이션 데이터)이라 적대 패널이 볼 코드 표면이 없다. 대신 전용 하네스로 검증했다.
- **검증**: `node --check` PASS · `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34/0**(baseline 동일). `releases` 60→61 · `generated` 09-03 → 09-04.
- **평이화 준수**: 내부 명칭 27패턴 기계 스캔 **0건**. 화면에 그대로 나타나는 라벨(「답할 AI 있음」·[종료]·「연결 정보가 없습니다」 등)만 그대로 인용. 「」 23/23 균형 · `**`/`«»` 0(기존 블록 관행 동일).
- **미검증 정직 표기**: 이 서비스 화면에서 연결 프로그램을 받는 자리가 아직 없다는 것 · 미서명 경고 · 앱 창 안 별도 로그인 · 패널 상주 문구가 1회 스냅샷이라는 것 · 풍선 알림과 탐색기 재시작 후 아이콘 재등록 미실측 — 항목 detail + 접힌 summary 양쪽에 명시했다.
- **거짓 명제 해소**: 09-03 블록이 예고한 WSL 「답할 AI 있음」 어긋남을 09-04 블록이 정본 실측(`docs/test-runs.d/TASK-20260904-web-shell.md:16` `✅ ai:ok`, 배포 `5ab60093`, PB-0008)에 근거해 닫았다. 적대 검증에서 다른 축이 이 항목을 「배포 후 실측 잔여」로 유보했으나 정본 대조로 반증했다.
- **캐시버스터**: 수기 bump 하지 않았다 — 소스 `?v=dev` 고정 + 빌드 주입 + 배포 ABORT 가드 계약(`docs/CONVENTIONS.md`). 수기 실값은 그 안전장치를 무력화한다.
- Human Approval Needed: **아니오**.


## REV-20260907T020000-ai-claude-conn-chip-place [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T02:00:00+09:00

**두 결함 모두 「방어를 넣은 자리」의 문제였다.**

칩은 «자리가 모자라면 내려간다» 는 규칙이 있었고 그 규칙대로 동작했다 — 다만 그 규칙이
**기본 폭에서 거의 항상 발동**한다는 것을 아무도 재 보지 않았다. 2026-09-01 의 주석은
「`admin` 은 여백이 100px 넘게 남는다」고 적고 있었는데, 실제로 재 보니 그 계정에서도 계정
행이 폭을 다 썼다. **주석에 적힌 실측이 그 뒤의 변경을 견디지 못했다.**

승인창은 더 전형적이다. 가드를 **입구마다** 붙였고(클릭 경로), 새 입구(자동 경로)가 생겼을
때 그 가드가 따라오지 않았다. 이번에는 출구 하나로 모았다 — 이 저장소가 여러 번 배운 형태다.

**뒤집은 결정을 남긴다.** 칩을 줄어들게 두는 편이 «항상 한 줄» 을 더 쉽게 만들지만, 실측에서
상태 낱말이 잘렸다(«업데이트 필…»). 그 칩은 존재하되 일을 못 한다 — 잘릴 바에는 계정 이름을
더 뭉개는 편이 옳다. 이름은 말줄임으로 남아 앞부분을 읽을 수 있다.

**정직하게 남기는 것**: 칩이 안 보인 원인이 자리 때문인지 확정하지는 못했다. 사용자 창은
실행 중이라 그 프로필(쿠키)을 열 수 없었고, 나는 **같은 배포본의 브라우저**에서만 재현했다.
자리 문제는 실측으로 확인된 사실이고, 그것을 고쳤다. 배포 후 그 창에서 다시 확인한다.

**게이트가 제 일을 했다.** 전제를 뒤집자 회귀 스위트가 즉시 붉어졌다 —
`test_connection_chip_is_free_of_the_footer_collapse_rule` 이 옛 계약을 명시적으로 잠그고
있었기 때문이다. 그 단정이 살아 있는 동안 이 결함은 «버그» 가 아니라 «계약» 이었고, 그래서
아무도 고치지 않았다. 지우지 않고 **이유를 적어 뒤집었다** — 다음 사람이 이 자리를 다시
건드릴 때 무엇이 왜 바뀌었는지 읽을 수 있어야 한다.


## REV-20260907T030000-ai-claude-session-cookie-lifetime [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T03:00:00+09:00

**증상을 두 번 잘못 짚은 뒤에야 원인에 닿았다.** 처음엔 칩의 «자리» 로 읽었고(그것도 실제
결함이라 고쳤다), 다음엔 WebView2 가 loopback 을 막는 줄 알았다(그것은 내 검증 환경의 오염
이었다). 결정적이었던 것은 **사용자 프로필로 직접 연 측정** 하나였다 — 그 전까지는 전부
「브라우저에서는 되는데」 였고, 그 문장이 곧 단서였는데도 나는 UI 축만 봤다.

**서버와 쿠키가 다른 말을 하고 있었다.** 서버는 14일 슬라이딩 + 90일 상한을 정하고 활동마다
만료를 미는 코드까지 갖고 있었다. 그런데 그 정책을 **운반할 쿠키에 수명이 없었다.** 정책을
정한 곳과 그것이 실려 나가는 곳이 갈려 있었고, 브라우저의 세션 복원이 그 간극을 가려 줬다.
가려 주는 것이 사라지는 환경(앱 창)에서 비로소 드러났다.

**보안 축을 무르게 하지 않았다.** 수명을 주는 변경은 「브라우저를 닫으면 로그아웃」을
없앤다 — 그것은 사용자가 명시적으로 고른 교환이다(2026-09-07). 그 대신 `HttpOnly`·
`SameSite=lax`·`Secure` 는 그대로이고, 각각을 무르게 하는 뮤턴트가 테스트에 죽는다.

**정직하게 남기는 것**: 이 수정은 **다음 로그인부터** 적용된다. 이미 발급된 세션 쿠키에는
수명이 없으므로, 사용자는 한 번 더 로그인해야 그 뒤부터 유지된다.


## REV-20260907T040000-ai-claude-cookie-postdeploy [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T04:00:00+09:00

문서 전용 주기. 리뷰할 코드가 없으므로 **기록이 사실인지**만 본다.

이번 건에서 배운 것을 한 줄로 남긴다 — **정책을 정한 곳과 그것을 운반하는 곳이 갈리면,
운반체가 정책을 배신해도 아무도 모른다.** 서버는 14일 슬라이딩을 계산하고 만료를 미는
코드까지 갖고 있었는데 쿠키에는 수명이 없었고, 브라우저의 세션 복원이 그 간극을 몇 달간
가려 주었다. 가려 주는 것이 없는 환경(앱 창)이 생기고서야 드러났다.


## REV-20260907T050000-ai-claude-client-live-verify [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T05:00:00+09:00

문서 전용 주기. 리뷰할 코드가 없으므로 **기록이 사실인지**만 본다.

**«실제 클라이언트에서 봤다» 를 이번에야 말할 수 있다.** 앞선 주기들은 브라우저에서 재현하고
「같은 배포본이니 같을 것」으로 미뤘는데, 정확히 그 간극에 진짜 원인(세션 쿠키)이 숨어
있었다. 앱 창은 devtools 도 없고 프로필도 잠겨 밖에서 볼 수단이 없었다 — 그래서 이번에는
**설치본 자체에 디버깅 포트를 열어** 안을 봤다. 측정 수단이 없으면 만들어야 하고, 만든 것은
측정이 끝나면 거둬야 한다(포트·릴레이·임시물 모두 제거하고 정상 실행으로 되돌렸다).

**정직하게 남기는 것**: 로그인 자체는 기존 검증 헬퍼(`session-login`)가 했고, 그 시점에
사용자 세션이 이미 살아 있어 `already: true` 로 그대로 썼다 — 즉 **사용자 계정의 실제
세션**으로 잰 값이다. 새 자격증명을 만들거나 사용자 상태를 바꾸지 않았다.
## REV-20260907T060000-ai-claude-chip-copy-and-note [CODEX:web-copy] — ACCEPTED
- Timestamp: 2026-09-07T06:00:00+09:00

**같은 문단이 두 번 레이아웃을 깼고, 두 번 다 «자리를 옮겨» 고쳤다.** 2026-09-02 에는
`.composer-box` 안의 플렉스 항목이라 입력창을 옆으로 밀었고(「대화창 UI가 무너진다」),
입력창 위로 옮긴 뒤에는 자기 줄을 차지해 컴포저 **높이**를 바꿨다 — 사이드바 프로필 행과의
하단 정합이 안내가 켜질 때마다 어긋났다(2026-09-07 제보). 두 번째 수정의 주석은 「여기서는
자기 줄을 갖는 블록이므로 그런 일이 구조적으로 일어나지 않는다」고 적었는데, 그 문장이 본
것은 **가로 축**뿐이었다. 세 번째로 자리를 옮기지 않고 **제거**한 이유가 그것이다 — 조건부로
나타나 컴포저 높이를 바꾸는 요소는 어디에 두든 정합을 흔든다.

**대가를 정직하게 남긴다: 「왜 선택기가 없는가」를 말하던 유일한 화면 표면이 사라졌다.**
사용자 지시가 명시적이었고(§3.1 우선순위 1) 같은 주기에 목록이 실제로 뜨게 만들었으므로,
그 문장이 필요한 상태 자체가 드물어진다. 남은 표면은 프로필 행의 연결 칩(상태·다음 행동)과
연결 모달이다 — 같은 사실을 두 자리에서 말하면 한쪽이 낡는다는 §16.8 A-1 과도 정합한다.

**툴팁은 분량이 아니라 «누가 읽는가» 가 문제였다.** 종전 문안은 전부 참이고 정확했다 —
그래서 어떤 정확성 게이트에도 걸리지 않았다(§16.8 의 문제 진술 그대로). 줄이면서 내부
어휘도 함께 낮췄다: 「러너」·「서버 배포본」은 시스템의 이름이지 사용자의 이름이 아니다
(§16.8 B-2 a). 다만 「러너」를 전부 지우지는 않았다 — 사용자 본인이 요청문에서 그 낱말을
쓴다(「연결된 러너 …」). 대상 사용자의 어휘로 판정한다는 규칙을 그대로 적용한 결과다.

**게이트를 두 방향으로 조정했다.** ① 툴팁 문단·문자 예산을 **세는** 단정을 신설했다 —
분량 축은 정확성 게이트가 원리적으로 못 잡으므로 세지 않으면 다시 자란다(§16.7 G10).
② 「안내가 플렉스 항목이 아니다」·「메뉴 role 밖이다」·「컴포저 안에 있다」 3건은 요소가
사라져 **의미를 잃었으므로** 「요소가 없다」 하나로 대체했다. 여기서 조심한 것은 §16.7 의
경고다 — 게이트 전제를 바꾸면 그 게이트를 지키던 테스트가 결함을 계약으로 만든다. 그래서
지우지 않고 **뒤집어** 남겼다: 요소가 되살아나면 이제 그 자체가 FAIL 이다.


**codex 적대 리뷰 결과** (같은 호출, `[CODEX:web-copy]`): 화면 축 지적은 1건 —
「선택기를 숨기는 처리는 유지하면서 사유·다운로드 링크 렌더링을 삭제했다 … 복구 안내가
유실된다」. **by-design 으로 판정**한다: 이 cycle 의 원 요청이 그 UI 의 제거이고(TASK.md §4
인용), 근거는 AI 의 추정이 아니라 **사용자 지시**다(§18.8 「의도된 구성」 조항의 요건).
대가는 위 본문과 REPORT.md 에 명시했다 — 남은 표면은 연결 칩과 연결 모달이며, 같은 주기의
feature-0043 수정이 「목록이 비는 상태」 자체를 드물게 만든다. P1 **0**.


## REV-20260907T063000-ai-claude-chip-copy-and-note [SUBAGENT:ux,design] — ACCEPTED
- Timestamp: 2026-09-07T06:30:00+09:00
- Trigger: `UI/layout/screen/버튼·화면·레이아웃` keyword matched → ux·design
- 상세 원장은 `feature-0043-external-llm-bridge/docs/REVIEW.md` REV-20260907T063000 (한 cycle,
  두 feature). 여기에는 **화면 축 조치**만 적는다.

**P1 — 안내 문단 제거가 «무음 강등» 을 만들었다.** 카탈로그를 못 받으면(fetch 실패) 선택기가
사라지고 사용자가 고른 등급이 전송에서 빠지는데, 그 사실을 말하던 유일한 표면이 방금 지운
문단이었다. 리뷰어가 같은 파일에서 **동형 사례의 선례**를 찾아냈다 —
`_modelSelectionSilentlyDropped` 분기가 토스트를 띄우며 「무음 금지」를 명시하고 있다. 같은
채널로 옮겼다: 토스트는 레이아웃 비용이 0 이라 사용자의 제거 지시와 충돌하지 않는다.
**제거 지시를 지키면서 정보를 되살리는 자리**가 이미 파일 안에 있었던 셈이다.

**P2 — 내가 쓴 문장이 코드보다 넓게 주장했다.** 「칩과 잠금 안내로 일원화한다」고 적었는데,
잠금 안내는 `compose_blocked = bridge_mode and not (connected and listening)` 일 때만 뜨므로
「연결·대기는 성립했는데 목록만 비었다」를 못 덮고, 칩 6문안에는 「모델」이라는 말이 없다.
주석과 `FUNCTION.md` 를 실제 커버리지로 정정하고, 남는 공백을 **대가로 명시**했다.
사실이 아닌 안심 문장은 다음 사람이 그 자리를 다시 보지 않게 만든다.

**P2 — `aria-live` 를 승계하지 않았다.** 지운 문단은 `aria-live="polite"` 를 갖고 있어 상태
변화를 읽어 주었는데, 승계 없이 지우면 「연결 안 됨 → 답할 수 없음」 전이가 스크린리더에 한
마디도 가지 않는다. 칩에 `role="status" aria-live="polite"` 를 얹었다 — 칩은 라벨 자체가
상태이므로 그 자리가 맞고, 레이아웃 비용도 0 이다.

**P2 — 툴팁 예산 게이트가 깨질 수 없는 자리만 잠갔다.** 내가 만든 검사는 JS 문자열 리터럴만
셌는데, 리터럴은 우리가 쓴 것이라 애초에 예산을 안 넘는다. 실제로 넘길 수 있는 것은 러너가
실어 보내는 `aiUnreadyReason`(CLI 원문·최대 300자·여러 줄)이고 나는 그것을 **주석으로 명시
제외**했다. 표시 직전에 한 문단으로 접고(140자) 그 접힘을 실제로 구동하는 테스트를 더했다.

**남긴 것(이 cycle 밖, `REPORT.md §8` 기록)**: `.composer-gate`·`.timeout-extend-banner` 도
정적 흐름이라 켜지면 컴포저 높이를 바꾼다 — 제거의 근거가 그 둘에도 성립하므로 근본 원인
(컴포저 높이 비고정)은 미해결이다. `model_selector_reason`·`runner_download_url` 은 소비처가
0 이 됐다.
## REV-20260907T060000-ai-claude-auto-connect [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T06:00:00+09:00

**보안 겹 하나를 사용자 결정으로 뺐다 — 그 사실을 흐리지 않는다.** 네이티브 확인은 서비스에
XSS 가 생겼을 때 「사람 없이 프로세스가 뜨는 것」을 막던 유일한 겹이었다. origin·nonce 는 XSS
가 통과한다. 나는 그 대가를 먼저 말했고, 사용자는 「없애고 트레이 알림으로 대체」를 골랐다.
남은 것은 **탐지**이지 **차단**이 아니다.

그 대신 알림이 믿을 만하도록 세 가지를 잠갔다 — 실패는 알리지 않고(소음이 되면 사람이 끄는
법을 배운다), 조회는 조용하고, 알림 실패가 동작을 되돌리지 않는다(알림은 관문이 아니다).

**「고를 것이 없으면 묻지 않는다」의 경계를 코드가 알게 했다.** 처음에는 «AI 가 하나뿐일 때»
로 읽힐 수 있었는데, 러너를 읽어 보니 요청마다 런타임을 바꿔 답한다 — 그러므로 서로 다른
플랫폼이 여럿인 것은 갈림이 아니다. 갈림은 **같은 플랫폼이 두 자리**일 때뿐이고, 그때만 묻는다.

**하네스가 제품 실패로 둔갑할 뻔했다.** 자동 연결 테스트가 「연결 기능에 닿지 못했습니다」로
실패했는데, 원인은 가짜 DOM 에 `createTextNode` 가 없어 `paint()` 가 던진 것이었고 그 예외를
제품의 `.catch` 가 잡아 사용자 문구로 바꿔 놓은 것이었다. 하네스의 결함이 제품의 증상을
입는 형태 — 이 저장소가 반복해 겪은 부류라 주석으로 남겼다.

**정직하게 남기는 것**: 「연결 준비·터미널·AI 지시문 전면 제거」는 **다음 주기**다. 한 주기에
섞으면 웹 UI 수술과 클라이언트 동작 변경이 한 diff 에 들어가고, 되돌릴 때 함께 되돌아간다.

**시험할 수 없는 가드는 지웠다.** 「자동은 1회」를 플래그로 막아 두었는데, 뮤테이션이 그것을
**등가**로 드러냈다 — 되메우는 것은 플래그가 아니라 «auto 를 주는 호출이 하나뿐» 이라는 사실
이었다. 남겨 두면 다음 사람은 「여기 방어가 있다」고 읽지만 그 방어는 한 번도 서지 않는다.
지우고, 되메우던 사실 쪽을 단정으로 옮겼다.


## REV-20260907T160000-asset-stamp-reach [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T16:00:00+09:00

**이 결함은 내가 직전 주기를 「검증했다」고 말할 뻔한 자리에서 나왔다.** 단위 413 passed ·
뮤테이션 12/12 · 컨테이너 회귀 EXIT=0 · 배포 soak PASS — 전부 초록인데 사용자 화면의 동작은
0이었다. 초록이 늘어난다고 도달이 늘어나지 않는다.

**갈라낸 방법**: 「서버가 무엇을 서빙하는가」와 「페이지가 무엇을 적재했는가」를 **따로** 물었다.
`fetch(url)` 은 새 파일을 준다(그래서 이것만 보면 정상으로 읽힌다). 결정적인 것은
`await import(url)` — 모듈 맵은 문서가 적재한 **바로 그 인스턴스**를 돌려주므로, export 목록
하나로 갈렸다. 이 구분을 안 했으면 「배포는 됐는데 왜 안 되지」에서 한참을 헤맸을 것이다.

**고치는 자리를 파일이 아니라 계약으로 잡았다.** 토큰 한 개를 붙이는 것으로 증상은 사라지지만,
같은 함정은 «다음에 추가되는 모듈»에 그대로 남는다. 주입기의 docstring 은 이 gap 을 이미
문장으로 알고 있었고 — 아는 것과 지켜지는 것은 다르다 — 지키는 것이 없었다. 전수 검사를 둔다.

**가드가 진짜 잡는지 되돌려 확인했다.** 수정을 원복하니 census 가 정확히 그 한 줄을 지목하며
실패했다(`app/connect-modal.js → ./client-bridge.js`). 스캐너가 깨져 조용히 통과하는 형태를
막기 위해 양성 대조군과 표본 하한(15)도 함께 뒀다 — 실측 표본은 103건이다.

**넓히지 않은 것**: `static_cache.py` 가 「`?v=` 없음」에 `no-cache` 를 부여하도록 정책을 강화할
수도 있었다. 하지만 그것은 캐시 정책의 의미를 바꾸는 변경이고, 이 결함의 원인은 «정책» 이 아니라
«참조가 스탬프 밖에 있었다» 이다. 원인 자리에서 막고, 정책은 건드리지 않는다.
## REV-20260907T190000-remove-terminal-path [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-07T19:00:00+09:00

**지우면서 가장 조심한 것은 「막다른 길」이었다.** 이 저장소에는 그 걱정을 이름으로 가진
테스트가 있었다 — `test_terminal_path_is_not_deleted`(**없애지는 않는다.** 연결 프로그램이
없는 사용자에게는 이것이 유일한 길이다). 사용자가 그 근거를 알고 반대로 골랐으므로 지웠지만,
그 테스트가 옳게 겨누던 것까지 지우지는 않았다: 같은 자리에 **받기 안내가 있는가**를 잰다.
그래도 남는 대가(앱을 못 받는 사용자에게는 길이 없다)는 FUNCTION.md 에 문단으로 적었다 —
말하지 않으면 다음 사람이 그 사실을 사고로 발견한다.

**전제가 뒤집힌 테스트 12건을 지우지 않고 뒤집었다.** 지우면 「이제 무엇이 참인가」를 아무도
지키지 않고, 다음 사람이 지운 경로를 되살려도 초록이다. 뒤집을 때는 **원래 걱정을 옮겼다** —
「지시문을 서버에서 받아라」는 「지시문 표시가 되살아나지 않는가」로, 「닫을 때 토큰을 지워라」는
「토큰을 넣는 자리가 있는가」로. 두 번째 것은 계약이 **강해진** 경우다: 애초에 안 넣으면 지울
것도 없다.

**⚠ 이 주기의 가장 큰 소득은 계획에 없던 것이다.** 행위 하네스 둘이 **2026-09-04 이후 한 번도
돌지 않고 있었다** — `client-bridge.js` 가 생기면서 상대 import 가 해소되지 못해
`ERR_INVALID_URL`/`ERR_MODULE_NOT_FOUND` 로 죽었고, 하나는 인자 없이 부르면 usage 만 찍고
**0 으로 끝나** 「안 돌았다」와 「통과했다」가 겉으로 같았다. 그동안 문서에는 「25/0 PASS」가
그대로 남아 있었다. 오늘의 `?v=` 스탬프 결함(TASK-20260907T160000)과 **같은 계급**이다 —
초록의 출처를 묻지 않으면 초록은 사실을 말하지 않는다.

**하네스를 고치면서 두 번 헛짚었다.** ① F2 실패를 「내 변경의 회귀」로 읽었는데, 실제로는
내가 `last_os` 를 기본값으로 넣어 **로그인 진입 자동 실행**이 처음으로 켜졌고 그 대기가 창을
닫은 것이었다 — 시나리오가 재는 대상이 바뀐 것이지 제품이 깨진 게 아니다. 페이지당 1회라는
실제 시점에 맞춰 먼저 소진시켰다. ② L17 이 「버튼도 못 누른 채」 통과할 뻔했다 — 앞 시나리오의
응답에서 `last_os` 를 빠뜨려 자격이 꺼졌기 때문이다. 둘 다 **하네스가 제품 증상을 입는** 부류다.

**제품 결함도 하나 나왔다.** 창을 여는 순간 상태 조회가 한 번도 끝나지 않았으면 `_offerLaunch`
가 「이력 없음」으로 읽고 물러나, 그 창에는 [내 AI 실행] 이 영영 안 나타난다. 하네스가 그
자리를 짚었고(L1), 알게 된 자리에서 한 번 더 주도록 고쳤다. 라이브에서는 폴링이 대개 먼저
끝나므로 «거의 항상» 괜찮았을 것이다 — 그 «거의» 가 이 저장소가 반복해 겪은 형태다.

**넓히지 않은 것**: 서버는 여전히 `handoff`·`launch.posix/windows/probe` 를 만들어 보낸다.
화면이 안 그릴 뿐이다. 서버까지 걷어내면 되돌리기가 어려워지고, 이 결정이 되돌아올 가능성은
0 이 아니다(사용자가 대가를 알고 골랐다는 것은 그 대가가 실재한다는 뜻이다).
## REV-20260907T185500-kb-search-security [SUBAGENT:security] — PASS
- Related TASK: TASK-20260907T181510-kb-external-search
- Trigger: KB 검색/외부 AI/제품·DB 인가
- Timestamp: 2026-09-07T18:55:00+09:00
- Verdict: PASS
- Artifact: unit/feature-0002-agent-core/docs/reviews/20260907T185500-kb-search-security.md
- Human Approval Needed: no

## REV-20260907T185500-kb-search-backend [SUBAGENT:backend] — PASS
- Related TASK: TASK-20260907T181510-kb-external-search
- Trigger: KB 검색/외부 AI/제품·DB 인가
- Timestamp: 2026-09-07T18:55:00+09:00
- Verdict: PASS
- Artifact: unit/feature-0002-agent-core/docs/reviews/20260907T185500-kb-search-backend.md
- Human Approval Needed: no

## REV-20260907T185500-kb-search-qa [SUBAGENT:qa] — PASS
- Related TASK: TASK-20260907T181510-kb-external-search
- Trigger: KB 검색/외부 AI/제품·DB 인가
- Timestamp: 2026-09-07T18:55:00+09:00
- Verdict: PASS
- Artifact: unit/feature-0002-agent-core/docs/reviews/20260907T185500-kb-search-qa.md
- Human Approval Needed: no

## REV-20260907T190600-kb-trust-boundary [SUBAGENT:security] — PASS
- Related TASK: TASK-20260907T181510-kb-external-search
- Trigger: 질문/이력/KB trust boundary 회귀 검사
- Timestamp: 2026-09-07T19:06:00+09:00
- Verdict: PASS
- Artifact: unit/feature-0002-agent-core/docs/reviews/20260907T190600-kb-search-security-r3.md
- Human Approval Needed: no

## REV-20260907T190600-kb-ci-channel [SKIPPED:channel-unavailable:github-actions]
- Related TASK: TASK-20260907T181510-kb-external-search
- Reason: GitHub Actions run34075693338 job101601208267 annotation에서 계정 결제/지출 한도
  때문에 job이 시작되지 못했다고 확인했다. AGENTS §18.8 채널 불가 판정.
- Alternative: 전체 로컬 CI 7485 PASS/28 skip/1 옛 assertion 실패; 그 검사 정합 후 suite19 PASS.
  KB 관련203 PASS. 전체ruff0, migrate-lint heads/self-test, codenav/routemap PASS.
- verification_debt: 원격 GitHub runner 미실행; retry_after=unknown; 복구 후 다음 cycle에서 확인.

## REV-20260908T010301-ai-claude-doc-sync-20260908-010301 [SKIPPED:non-policy-doc] — 릴리즈노트 2026-09-07 블록 신설 (doc_sync 09-08)
- Related TASK: TASK-20260908T010301-doc-sync-rn-0908
- Timestamp: 2026-09-08T01:03:01+09:00
- 범위: `src/static/release-notes-data.js` **데이터 블록 1개 prepend + `generated` 전진**. 렌더 로직(`release-notes.js`)·HTML·캐시버스터 토큰 **무접촉**. 제품 코드 변경 0.
- **[SKIPPED] 사유**: §18.8 표 첫 행 — 사용자향 릴리즈노트는 비정책 doc(정적 큐레이션 데이터)이라 적대 패널이 볼 코드 표면이 없다. 대신 전용 하네스 + 적대 검증조로 검증했다.
- **검증**: `node --check` PASS · `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34/0**(baseline 동일). `releases` 61→62 · `generated` 09-04 → 09-07.
- **적대 검증(13항목 판정)**: CONFIRMED 10 · PLAUSIBLE 3 — 정정 3건을 전건 반영했다.
  ① 업데이트 채널: 정본 `feature-0046 REPORT.md:36-39` 이 「그 실측은 web-a 컨테이너 내부 포트로 쟀다 — 엣지(caddy) 경유와 web-b 는 재지 않았다」 라 적는데 초안이 「배포된 서버에서 다시 쟀다」 로만 써 바깥 경로 미측정을 감췄다 → 고지 추가.
  ② 모델 목록: 릴리즈노트 **2026-09-02 블록**이 이미 「5분을 10초 안팎으로 줄였다」 로 같은 증상의 해소를 단정했는데 이번 정본 실측이 그 경로가 목록 자체를 못 받음을 보였다 → **재발 명시** 추가.
  ③ summary: 09-04 블록이 고지한 **앱 창↔브라우저 로그인 분리**가 이번 창에 해소되지 않았는데(정본 grep 0건) 초안이 침묵했고, 항목 5(「로그인이 앱 재실행을 견딘다」)와 맞물려 「이제 브라우저와 로그인을 공유한다」 로 오독될 수 있었다 → 고지 복원.
- **평이화 준수**: 내부 명칭 기계 스캔 **0건**. 화면에 그대로 나타나는 라벨(「연결 정보가 없습니다」·[업데이트 확인]·[종료] 등)만 인용했다.
- **미검증 정직 표기**: 첫 실 릴리스 미반입(받기 자리는 열렸으나 서버에 파일 없음) · 미서명 경고 · 설치기 실제 실행 미실측(Windows 빌드 머신 필요) · 라이브 계정 화면의 모델 목록 미관측 · 엣지 경유 채널 미측정 — 항목 detail + 접힌 summary 양쪽에 명시했다.
- **캐시버스터**: 수기 bump 하지 않았다 — 소스 `?v=dev` 고정 + 빌드 주입 + 배포 ABORT 가드 계약(`docs/CONVENTIONS.md`). 수기 실값은 그 안전장치를 무력화한다. wrapper 지시문의 bump 요구는 이 계약에 비추어 stale 이다.
- Human Approval Needed: **아니오**.


## REV-20260908T100000-remove-terminal-path-live [SKIPPED:자기 적대 리뷰] — ACCEPTED
- Timestamp: 2026-09-08T10:00:00+09:00

문서 전용. 실측에서 **부재를 재는 방법**을 조심했다 — `documentElement.innerHTML` 로만 보면
주석에 남긴 결정 근거(「연결 준비」라는 말이 그 안에 있다)가 「아직 남아 있다」로 잡힌다.
주석을 걷어낸 뒤 다시 재서 갈랐고, 두 값을 모두 기록에 남겼다.

**재지 않은 것을 재었다고 하지 않는다**: 브라우저 쪽 노출 규칙은 로그인이 필요해 라이브로
확인하지 못했다. 하네스가 같은 분기를 실제 모듈로 구동하지만, 그것은 라이브가 아니다 —
경계를 그대로 적었다.

**관측했으나 설명하지 못한 것**: 검증 중 클라이언트가 한 번 스스로 종료·재시작했다(약 35초).
원인을 확인하지 못했으므로 추측을 적지 않았다. 결과적으로 러너는 `AI = codex` 로 자동
재연결됐고 사용자 상태는 복구됐다.
## REV-20260908T113000-bridge-token-env-ux [SUBAGENT:ux] — PASS
- Related TASK: TASK-20260908T113000-bridge-token-env / feature-0003-agent-web-ui
- Trigger: UI/클라이언트 안내 keyword matched
- Timestamp: 2026-09-08T11:26:45+09:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T113000-ux.md
- Human Approval Needed: no

## REV-20260908T113000-bridge-token-env-design [SUBAGENT:design] — PASS
- Related TASK: TASK-20260908T113000-bridge-token-env / feature-0003-agent-web-ui
- Trigger: UI/클라이언트 안내 keyword matched
- Timestamp: 2026-09-08T11:26:45+09:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T113000-design.md
- Human Approval Needed: no
## REV-20260908T120000-runner-update-recovery [SUBAGENT:runner_race_review] — PASS
- Related TASK: feature-0003-agent-web-ui
- Trigger: 공유 파일 교체 경합, 자식 프로세스 수명, 단절 표시, 실행파일 신뢰
- Timestamp: 2026-09-08T11:20:00+09:00
- Verdict: PASS
- Artifact: unit/feature-0043-external-llm-bridge/docs/reviews/20260908T112000-runner-race-review.md
- Human Approval Needed: no
- 배포 근거: wrapper FIRST_REQUEST.md의 기존 deploy_scope: included, AGENTS.md §16.5.1. 앱 업데이트 확인 계약은 유지.

## REV-20260908T112500-runner-client-only-verification [SKIPPED:non-policy-doc]
- Related TASK: feature-0003-agent-web-ui
- Reason: 기존 구현·사용 동선을 변경하지 않고 사용자 확인 내용과 실제 검증 결과를 TASK 및 test-runs 기록에 보충한다. FUNCTION·정책·제품 코드 변경 없음.
- Timestamp: 2026-09-08T11:22:45+09:00

## REV-20260908T114000-runner-recovery-postdeploy [SKIPPED:non-policy-doc]

- Related TASK: TASK-20260908T120000-runner-update-recovery.
- Reason: 병합·배포·다운로드 검증 결과 및 완료 상태 기록만 보충한다. 제품 코드·FUNCTION·정책 변경 없음.
- Timestamp: 2026-09-08T11:38:45+09:00


## REV-20260908T123400-connect-discovery-backend [SUBAGENT:backend] — PASS
- Related TASK: feature-0003-agent-web-ui / TASK-20260908T120000-connect-discovery-ux
- Trigger: API/성능/캐싱 keyword matched
- Timestamp: 2026-09-08T12:34:00+09:00
- Verdict: PASS
- Artifact: [review](reviews/20260908T123400-connect-discovery-backend.md)
- Human Approval Needed: no


## REV-20260908T123400-connect-discovery-security [SUBAGENT:security] — PASS
- Related TASK: feature-0003-agent-web-ui / TASK-20260908T120000-connect-discovery-ux
- Trigger: auth/인증/token/세션 keyword matched
- Timestamp: 2026-09-08T12:34:00+09:00
- Verdict: PASS
- Artifact: [review](reviews/20260908T123400-connect-discovery-security.md)
- Human Approval Needed: no


## REV-20260908T123400-connect-discovery-qa [SUBAGENT:qa] — PASS
- Related TASK: feature-0003-agent-web-ui / TASK-20260908T120000-connect-discovery-ux
- Trigger: API/검증/performance/캐싱 keyword matched
- Timestamp: 2026-09-08T12:34:00+09:00
- Verdict: PASS
- Artifact: [review](reviews/20260908T123400-connect-discovery-qa.md)
- Human Approval Needed: no


## REV-20260908T123400-connect-discovery-ux [SUBAGENT:ux] — PASS
- Related TASK: feature-0003-agent-web-ui / TASK-20260908T120000-connect-discovery-ux
- Trigger: UI/화면/모달 keyword matched
- Timestamp: 2026-09-08T12:34:00+09:00
- Verdict: PASS
- Artifact: [review](reviews/20260908T123400-connect-discovery-ux.md)
- Human Approval Needed: no


## REV-20260908T123400-connect-discovery-design [SUBAGENT:design] — PASS
- Related TASK: feature-0003-agent-web-ui / TASK-20260908T120000-connect-discovery-ux
- Trigger: UI/디자인/대비 keyword matched
- Timestamp: 2026-09-08T12:34:00+09:00
- Verdict: PASS
- Artifact: [review](reviews/20260908T123400-connect-discovery-design.md)
- Human Approval Needed: no

## REV-20260908T150000-connect-release-evidence [SKIPPED:non-policy-evidence-only] — ACCEPTED

- TASK: TASK-20260908T120000-connect-discovery-ux / Issue #1615
- 직전 backend/security/QA/UX/design SHIP 이후 코드 변경 없이 이미 수행한 native 2회 결과·설치기 지문·최신 main 통합 결과를 기록한다. 신규 동작·정책·권한 경계가 없어 패널을 반복하지 않는다. 검증 파일의 값과 실행 로그를 대조했다.

## REV-20260908T041713-connect-published [SKIPPED:non-policy-deploy-evidence] — ACCEPTED

- 동일 TASK의 최종 배포·다운로드 증거만 기록했다. 직전 기능 패널 SHIP 후 제품 소스 변경 없음. 실행 종료코드·공개 API·파일 지문을 직접 대조했다. 새 동작이나 정책이 없어 패널을 반복하지 않는다.
## REV-20260908T151500-codex-connect-fix [SUBAGENT:backend,security,qa,ux,design] — ACCEPTED
- Related TASK: TASK-20260908-codex-connect-fix; CHG-20260908T151000-codex-connect-fix; Issue #1625.
- Trigger: API/응답 계약, permission/실행 권한, caching/캐시, UI/연결 화면.
- Dispatch: update_installer_review(backend/security), update_install_qa(qa), connect_ux_review(ux/design). 독립 도메인 검토 및 수정 확인.
- P1 수정: catalog 빈 detail KeyError/남은 성공행/예외 기록 누락, catalog 건강 오인, error JSON 생존 오인, 로그인 필요 위치 소실. P2 수정: 공통 CSS 적용면, OS PermissionError 형 보존, A→B→A 선택 경쟁.
- QA가 후속 선택 실패 후 재시도 소실과 전역 파일 세대의 불필요한 재조회 2건을 적발했다. watcher 백오프와 플랫폼별 selection_id로 수정 후12건 PASS.
- Final: backend/security P1/P2 0, QA12 PASS, UX/design P1/P2 0/DOM12 PASS. 실제 설치본1.2.4 이후 UI/요청은 배포 후 추가 증거로 확인한다. 코드 검토 PASS를 실제 사용자 요청 성공으로 대체하지 않는다.

## REV-20260908T060223-backend [SUBAGENT:backend] — PASS
- Related TASK: TASK-20260908-prompt-layer-delivery (feature-0003-agent-web-ui)
- Trigger: API/엔드포인트 및 query/쿼리
- Timestamp: 2026-09-08T06:02:23.950021+00:00; Session: 01a07f86-30e8-7493-ab26-ae82792def88
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T060223-backend.md
- Human Approval Needed: no

## REV-20260908T060223-security [SUBAGENT:security] — PASS
- Related TASK: TASK-20260908-prompt-layer-delivery (feature-0003-agent-web-ui)
- Trigger: API/응답 및 개인정보 비노출
- Timestamp: 2026-09-08T06:02:23.950021+00:00; Session: 01a07f86-30e8-7493-ab26-ae82792def88
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T060223-security.md
- Human Approval Needed: no

## REV-20260908T060223-qa-ux-design [SUBAGENT:qa-ux-design] — PASS
- Related TASK: TASK-20260908-prompt-layer-delivery (feature-0003-agent-web-ui)
- Trigger: API/계약, 여섯 계층 수용 기준, toast 한 줄 UX/design
- Timestamp: 2026-09-08T06:02:23.950021+00:00; Session: 01a07f86-30e8-7493-ab26-ae82792def88
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T060223-qa-ux-design.md
- Human Approval Needed: no

- 배포 승인 근거: 현재 사용자 개선 위임 + wrapper FIRST_REQUEST.md deploy_scope: included, AGENTS.md §16.5.1. 인증/인가·파괴적 변경 없음.
## REV-20260908T150000-attachment-backend [SUBAGENT:backend] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: API/contract 응답 본문 계약
- Timestamp: 2026-09-08T06:09:53.549929+00:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T150000-attachment-backend.md
- Human Approval Needed: no

## REV-20260908T150000-attachment-security [SUBAGENT:security] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: API/contract 응답 본문 계약
- Timestamp: 2026-09-08T06:09:53.549929+00:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T150000-attachment-security.md
- Human Approval Needed: no

## REV-20260908T150000-attachment-qa [SUBAGENT:qa] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: API/contract 응답 본문 계약
- Timestamp: 2026-09-08T06:09:53.549929+00:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908T150000-attachment-qa.md
- Human Approval Needed: no

## REV-20260908T152700-attachment-deployed [SKIPPED:non-policy-doc] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: 비정책 검증 결과 문서만 변경
- Timestamp: 2026-09-08T06:27:43.349266+00:00
- Verdict: PASS
- Human Approval Needed: no
- 기존 코드 3패널 PASS 후 실행 결과만 기록; 추가 코드/정책 변경 없음.

## REV-20260908T153000-attachment-docs [SKIPPED:non-policy-doc] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: 검증 문서 서식과 원격 동기화 체크만 변경
- Verdict: PASS
- Human Approval Needed: no

## REV-20260908T153500-cycle-list-backend [SUBAGENT:backend] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: lifecycle cleanup SIGPIPE
- Timestamp: 2026-09-08T06:38:22.052443+00:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908-cycle-list-backend.md
- Human Approval Needed: no

## REV-20260908T153500-cycle-list-qa [SUBAGENT:qa] — PASS
- Related TASK: TASK-20260908T150000-attachment-boundary
- Trigger: lifecycle cleanup SIGPIPE
- Timestamp: 2026-09-08T06:38:22.052443+00:00
- Verdict: PASS
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260908-cycle-list-qa.md
- Human Approval Needed: no
