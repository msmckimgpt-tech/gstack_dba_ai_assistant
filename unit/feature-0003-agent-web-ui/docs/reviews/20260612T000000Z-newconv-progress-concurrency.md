---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: newconv-progress-adversarial-concurrency
timestamp: 2026-06-12T00:00:00Z
trigger: UI/screen keyword matched (작업 단계 표시/사이드바) + lazy-create send 동시성 state 전환
verdict: CONCERN
---

### 1. Blocking issues

(no findings)

### 2. Cross-domain concerns

- Evidence: `/api/new_conversation` 성공 후 `/api/ask` 가 throw 하면, 발급된 earlyCid 의 빈 대화(zero-message) row 가 DB/사이드바에 정리 없이 잔존. pure-lazy_create 에서는 cid 가 발급되지 않아 실패 시 고아가 없었으므로 회귀.
  Location: unit/feature-0003-agent-web-ui/src/static/app.js:5549-5601
  Reason: early-cid 일반화로 항상 conv 를 선발급하게 되어, ask 실패 시 빈 대화가 남는 새 노출이 생긴다. 단순 삭제는 worker 모드에서 ask 타임아웃 후에도 살아있는 run 을 파괴할 위험이 있어 부적절.
  Action: `earlyCidActivated` 플래그 도입 — early-cid 가 활성 전환되면 catch 에서 lazy 전용 에러 경로 대신 non-lazy 복구 경로(fetchAskStatus → is_processing 시 대기/취소/즉시답변 다이얼로그)로 분기. 대화는 실제 run 의 컨테이너가 되어 고아화되지 않고, 살아있는 run 은 attachAndWaitForResult 로 회수. (app.js:5411 플래그 선언, 5599 set, 5687 분기, 5728 askCid 보정)

- Evidence: 빈 대화에 명시적 `conversation_id` 로 `/api/ask` 를 호출하는 경로가 user message 를 저장하고 run 을 시작하는지 (백엔드 정합).
  Location: unit/feature-0003-agent-web-ui/src/static/app.js:5564-5568
  Reason: early-cid 후 askBody.lazy_create 를 삭제하고 conversation_id 를 명시 → 기존 대화 경로와 byte-identical. 빈 대화 특수처리로 user message 누락 시 결함.
  Action: 확인 완료 — user message 저장은 `run_agent(user_message=...)` 의 내부 `save_memory_message` 책임 (agent_core.py:1379 save, 2273 호출). conversation 존재/메시지수 무관. 기존 staged-attachment 흐름(TASK-0106)이 동일 패턴(earlyCid+conversation_id 명시)을 이미 production 에서 사용 중 → 검증된 경로. 별도 수정 불요.

### 3. Challenge to current spec

- Evidence: 사용자가 전송 도중 "+ 새 대화" 클릭 시 `state.pendingSentinel !== busyKey` → early 전환 skip → 이 send 는 폴링 미시작.
  Location: unit/feature-0003-agent-web-ui/src/static/app.js:5572
  Reason: 두 번째 컨텍스트 오염 방지를 위해 의도적으로 skip. 첫 대화는 background 로 진행되며 사이드바(refreshWorkspace)에 등재되어 사용자가 클릭 진입 시 loadHistory/폴링 재engage.
  Action: 유지 — TASK-0082/0085 의 기존 멀티컨텍스트 send 설계와 정합. 가시 컨텍스트에서 "시작 중" 고착 없음. spec 변경 불요.

### 4. Verdict

CONCERN — BLOCKER 0. 중복 폴링(sentinel 가드 + seq 가드 이중 차단), 빈 status 조기 종료(falsy 라 stop 조건 아님), 첨부 흐름 회귀(stagedCount>0 게이트 유지), pending bubble race(대화 비귀속) 5개 실패모드는 안전 확인. CONCERN 2건은 코드 수정(#3 earlyCidActivated) + 백엔드 경로 확인(#2)으로 흡수. 잔여 위험: dry-run↔실제 TOCTOU 류 없음. 배포 후 PB-0008 Windows-browser 실측으로 새 대화 첫 요청 단계 실시간 표시 + 사이드바 동작 최종 확인 필요.
