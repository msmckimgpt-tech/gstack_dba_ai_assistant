---
doc_type: REPORT
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: append-only
source_of_truth: true
---

# Report

## 2026-07-29 — cycle 착수 (요청 접수 → 계획 확정)

**요청 (사용자, 2026-07-29)**: 관리 콘솔 `시스템 > 설정 > 실행 타임아웃 >
에이전트/쿼리 실행 타임아웃` 값을 AI 작업자가 임의로 조절해 둔 상태에서, 사용자가
assistant 의 추론을 기다리다 Request timeout 블로킹으로 작업 내용이 소실되는 마찰이
빈번. 작업이 타임아웃에 근접(약 80%)하면 "이번 요청은 타임아웃과 무관하게 끝까지
추론할지" 사용자 확인을 받고, 확인이 없으면 그대로 타임아웃, 확인되면 그 요청은
타임아웃을 초과해도 끝까지 수행.

**사용자 결정 (AskUserQuestion)**
- 연장 상한: **무제한** (승인 시 run 예산 검사 사실상 해제, 콘솔 상한 설정은 기본 0=무제한)
- 확인 UI: **컴포저 인라인 배너 + 브라우저 알림**(탭 백그라운드 시)

**현행 코드 확인 (착수 전 조사)**
- run 실행 예산은 `agent_core.run_agent` 의 `run_timeout_sec = AGENT_TIMEOUT_SEC × 3`
  이며, 초과 시 `result["error"] = "타임아웃으로 종료되었습니다."` 로 루프를 break 한다.
- 같은 콘솔 값이 `_call_llm` 의 per-attempt body timeout, `OpenAI(timeout=)` httpx
  총-대기에도 쓰인다(feature-0007 timeout-console-sync) — 시간 축이 3층.
- 사용자→워커 신호는 이미 memory KV 패턴이 있다(`cancel_requested`,
  `finalize_requested` + run_id 짝 검증). 연장 신호는 이 패턴의 미러링으로 붙인다.
- 프론트는 2026-07-09 결정으로 화면 차단 모달을 폐기하고 컴포저 인라인 상시 노출
  (취소/즉시답변)로 전환돼 있다 — 연장 배너도 같은 자리에 붙인다.

**위험도**: Major (§12.3 외부 비용 축 + 3계층 변경 + 신규 권한 코드).

**진행**: `unit/feature-0030-ask-timeout-extension` 신설, 코드는 cross-cut 거주
(feature-0002 agent-core · feature-0003 web-ui · shared/runtime_settings).

## 2026-07-29 — codex 적대 리뷰 반영 (P1×4 · P2×3 전건 수정)

사용자 결정(2026-07-29): 세션의 Agent-tool 제한과 AGENTS.md §18.8 패널 요구가 상충 →
`/codex review` 경로로 독립 검증 수행. 판정 **P1 4건 · P2 3건**, 전건 수정.

가장 중대했던 것은 **P1-3**: 승인 후 per-call 타임아웃을 24시간으로 올린 탓에, 단일 LLM
호출이 도는 동안 루프가 한 바퀴도 돌지 않아 '중단'·'즉시 답변'·`max_steps`·lease fencing 이
전부 무응답이 됐다. 연장의 대가로 탈출구를 잃는 구조였다. 연장이 푸는 것은 **run 전체 예산**
뿐이며 per-call 상한(15분)은 유지하도록 정정했다 — 이 값이 곧 '중단' 의 최대 응답 지연이다.

그 외: 승인 대상 run_id 미검증(P1-1) → 클라이언트 run_id 대조 + 빈 값 wildcard 제거,
KV 단일 슬롯 승인 오염(P1-2) → prompt 가 승인 흔적 리셋, finalize→extend `any` 자동
backfill(P1-4) → `own` 한정, 기능 게이트 fail-open(P2-1) → 503 fail-closed,
프론트 run_id 느슨 비교(P2-2) → 완전 일치만, prompt 발행 지연(P2-3) → 예산 초과 시점
재발행 + 20초 유예(대기 중 취소 매초 검사).

상세·잔여 위험은 `docs/REVIEW.md` REV-20260729-0001 참조.

검증: 신규/갱신 36건 + route-parity 1건 PASS. 전체 회귀는 `main` 대조 실행과 동일한
환경성 실패 15건 외 **회귀 0**. ruff All checks passed.
