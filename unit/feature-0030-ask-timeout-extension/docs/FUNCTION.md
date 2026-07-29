---
doc_type: FUNCTION
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

assistant 의 한 요청(run)이 **실행 예산(관리 콘솔 `시스템 > 설정 > 실행 타임아웃 >
에이전트/쿼리 실행 타임아웃` 파생값)의 약 80% 에 도달**하면, 사용자에게 "이번 요청은
타임아웃 값과 관계없이 끝까지 추론할까요?" 를 **비차단(non-blocking)** 으로 묻는다.
사용자가 승인하면 **그 run 한정**으로 타임아웃 컷을 해제해 답변이 끝까지 추론되고,
승인이 없으면 종전과 동일하게 타임아웃 처리된다.

배경: AI 작업자가 콘솔에서 `AGENT_TIMEOUT_SEC` 를 임의로 낮춰 둔 상태에서 사용자가
답변을 기다리면, run 예산 초과로 `"타임아웃으로 종료되었습니다."` 가 되어 그때까지의
추론 산출이 답변으로 이어지지 못하고 소실되는 마찰이 반복 관측됐다.

## 2. Goal

- **REQ-20260729T032307-timeout-extension-prompt**: run 실행 예산의 80%(설정 가능)에
  도달하면 그 run 에 대해 1회 "연장 확인" 신호를 올리고, 사용자에게 비차단으로 노출한다.
- **REQ-20260729T032307-timeout-extension-grant**: 사용자가 승인하면 해당 run 에 한해
  실행 예산·LLM 호출 타임아웃을 해제(무제한)하고 끝까지 추론을 완주시킨다.
- **REQ-20260729T032307-timeout-extension-default-deny**: 사용자의 명시 승인이 없으면
  종전 동작(타임아웃 종료)을 그대로 유지한다 — 승인은 opt-in, 무응답은 기존 경로.

## 3. In Scope

- 웹 작업화면(1:1·그룹 대화)의 assistant run 에 대한 연장 확인·승인 흐름.
- run 예산(`AGENT_TIMEOUT_SEC × 3`) 과 LLM 호출 타임아웃 2층(per-attempt body timeout,
  httpx 총-대기)의 승인 시 확장.
- 관리 콘솔 `실행 타임아웃` 그룹에 기능 on/off·임계 비율·상한 설정 노출.
- 승인 권한 코드(`conversation.extend.own` / `conversation.extend.any`) 신설 및 기존
  `conversation.finalize.*` 보유 역할 backfill.
- 컴포저 인라인 배너 + (탭 백그라운드 시) 브라우저 알림.

## 4. Out of Scope

- 외부 Conversation API(feature-0023) 경로의 연장 승인 — 대화형 확인 주체가 없어
  기존 타임아웃 정책을 유지한다(승인 신호 미발행).
- `max_steps`(도구 호출 상한)·워커 lease·취소/즉시답변 등 **다른 안전장치의 완화** —
  연장은 *시간* 예산만 푼다.
- 관리 콘솔 타임아웃 기본값 자체의 변경.

## 5. Inputs

- `AGENT_TIMEOUT_SEC` (관리 콘솔 live 값) — run 예산 산출 기준.
- `AGENT_TIMEOUT_EXTENSION_ENABLED` (기본 1) — 기능 게이트.
- `AGENT_TIMEOUT_EXTENSION_PROMPT_PCT` (기본 80) — 확인을 띄우는 소진 비율(%).
- `AGENT_TIMEOUT_EXTENSION_MAX_SEC` (기본 0 = 무제한) — 승인 후 추가 허용 시간 상한.
- `POST /api/extend` — `{conversation_id, run_id?}` 사용자 승인 신호.

## 6. Outputs

- memory KV 시그널: `timeout_ext_prompted` / `timeout_ext_run_id` /
  `timeout_ext_deadline_at` / `timeout_ext_granted` / `timeout_ext_granted_at`.
- `/api/ask_status`·`/api/ask_result` 스냅샷의 `timeout_extension` 필드
  (`{prompted, granted, deadline_at, run_id}`).
- activity step: "응답 시간 한도에 근접 — 계속 추론할지 확인 중" / "연장 승인됨 — 한도
  없이 끝까지 추론".

## 7. Main Flow

1. ask-worker 가 run 을 실행하고 루프마다 경과(`elapsed`)를 본다.
2. `elapsed >= run_timeout_sec × pct/100` 이고 아직 미프롬프트면 KV 에 prompted 를
   1회 기록하고 activity 를 emit 한다(루프는 **대기 없이 계속** 진행).
3. 프론트가 진행상황 폴링에서 `timeout_extension.prompted` 를 보고 컴포저 인라인 배너를
   띄운다. 탭이 백그라운드면 브라우저 알림도 함께 띄운다.
4. 사용자가 [계속 추론] 을 누르면 `POST /api/extend` → KV `timeout_ext_granted=1`.
5. 루프가 `elapsed > run_timeout_sec` 에 도달하면 grant 를 확인한다.
   - granted → 예산 컷을 건너뛰고(상한 설정 시 그만큼만) 계속 추론. LLM 호출
     타임아웃 2층도 확장값으로 재설정.
   - 미승인 → 종전대로 `"타임아웃으로 종료되었습니다."` 로 루프 종료.
6. run 이 terminal 에 도달하면 KV 연장 시그널을 정리한다.

## 8. Edge Cases

- **run_id 불일치(stale 신호)**: 이전 run 을 겨냥한 prompted/granted 플래그는
  cancel·finalize 와 동일하게 run_id 짝 검증으로 무시한다.
- **승인 후 취소/즉시답변**: 취소·즉시답변이 우선한다(연장은 시간만 풀 뿐 탈출구를
  막지 않는다).
- **승인이 100% 도달 후 도착**: 루프가 이미 종료됐으면 그 run 에는 효과 없음 —
  프론트는 terminal 스냅샷을 보고 배너를 걷는다.
- **기능 OFF**: 프롬프트를 발행하지 않으며 승인 엔드포인트는 409 로 거절한다.
- **권한 없음**: 배너의 승인 버튼을 access-blocked 로 표시(기존 finalize 패턴 동일).
- **워커 lease 박탈**: 연장 여부와 무관하게 기존 fencing(cancel 플래그)이 우선한다.

## 9. Error Handling

- KV 읽기/쓰기 실패는 **fail-safe(연장 없음)** 로 흡수한다 — 확인 신호 자체가 본
  추론을 깨지 않는다.
- `POST /api/extend` 는 대상 대화 부재 시 404, 기능 OFF 시 409, 권한 미보유 시 403.
- 브라우저 알림 권한 거부/미지원은 조용히 skip(배너는 정상 노출).

## 10. Dependencies

### 내부 기능 의존성
- feature-0002-agent-core — run 루프·memory KV(코드 거주)
- feature-0003-agent-web-ui — 엔드포인트·스냅샷·프론트(코드 거주)
- `shared/runtime_settings.py` — 관리 콘솔 설정 노출

### 외부 의존성
- 없음 (신규 패키지·외부 서비스 없음)

## 11. Pre-approved Changes

- 없음 (전역 `deploy_scope: included` 는 `FIRST_REQUEST.md` 선언을 따른다)
