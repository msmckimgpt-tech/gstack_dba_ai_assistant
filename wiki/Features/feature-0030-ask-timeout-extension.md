---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: active
ai_generated: true
feature_id: feature-0030-ask-timeout-extension
linked_unit: unit/feature-0030-ask-timeout-extension
sources:
  - ../../unit/feature-0030-ask-timeout-extension/docs/FUNCTION.md
---

# Feature — 실행 타임아웃 임박 시 사용자 확인 후 연장

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0030-ask-timeout-extension/docs/FUNCTION|unit/feature-0030-ask-timeout-extension/docs/FUNCTION.md]].

## 1. 한 줄 요약

요청 처리가 실행 예산의 80%(설정 가능)에 도달하면 작업 화면에 "계속 추론할까요?"를 **비차단으로**
띄우고, 사용자가 승인한 **그 요청에 한해** 예산 컷을 넘겨 답변을 완주시킨다. 승인이 없으면 종전과
동일하게 타임아웃 처리된다 — 관리 콘솔의 짧은 타임아웃 때문에 추론이 잘려 작업 내용이 소실되던
마찰을 해소한다.

## 2. 상태

- **active** (2026-07-29). 코드 거주: feature-0002(agent_core·memory) · feature-0003(라우터·
  스냅샷·프론트·권한) · `shared/runtime_settings`.

## 3. 책임 경계

- **함:** 예산 임계 도달 시 KV 신호 발행(run 당 1회) · `POST /api/extend` 승인 수신(run_id 대조) ·
  승인 run 의 **run 전체 예산** 해제 · 컴포저 인라인 배너 + 백그라운드 브라우저 알림 ·
  `conversation.extend.{own,any}` 권한 · 콘솔 설정 3종(사용/임계%/추가 허용 상한).
- **안 함:** 개별 LLM 호출 상한 해제(15분 유지 — 취소·즉시답변·lease fencing 의 응답성을 위해
  의도적으로 남긴다) · `max_steps` 완화 · 외부 Conversation API 경로(확인 주체 부재) ·
  콘솔 타임아웃 기본값 변경.

## 4. 관련 정본

- [[../../unit/feature-0030-ask-timeout-extension/docs/FUNCTION|FUNCTION.md]] ·
  [[../../unit/feature-0030-ask-timeout-extension/docs/ANCHOR|ANCHOR.md]] ·
  [[../../unit/feature-0030-ask-timeout-extension/docs/REVIEW|REVIEW.md]]

## 5. 관련 노트

- [[feature-0002-agent-core]] (run 루프·memory KV 정본) ·
  [[feature-0003-agent-web-ui]] (작업 화면 컴포저·인라인 취소/즉시답변 정본) ·
  [[feature-0021-redteam-review]] (반복 수정이 응답을 길게 만드는 반대편 축).

## 6. 설계 메모

- **왜 80% 인가**: 100% 에 물으면 사용자가 버튼을 누르는 사이 run 이 죽는다. 남은 20% 가 사람의
  반응 시간이다.
- **왜 멈추지 않는가**: 2026-07-09 결정으로 화면 차단 타임아웃 모달을 폐기했다. 배너는 알리기만
  하고 추론은 계속된다.
- **왜 시간 3층인가**: `AGENT_TIMEOUT_SEC` 는 run 예산(×3) · per-attempt body timeout ·
  httpx 총-대기 3곳에 쓰인다. run 예산만 풀면 다음 호출이 다른 층에서 잘린다.

## 7. 변경 이력 (이 카드)

- 2026-07-29: 신규 생성.
