---
doc_type: TASK
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-29
feature_status_note: 실행 타임아웃 80% 도달 시 사용자 확인 후 그 run 한정 무제한 연장 — KV 시그널(cancel/finalize 미러링)·run 예산+LLM 타임아웃 2층 해제·컴포저 인라인 배너+백그라운드 브라우저 알림·conversation.extend.* 권한 신설
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (root, 사용자 지시 2026-07-29 "타임아웃 근접 시 사용자 확인 후 끝까지 추론 허용")
- Priority: high
- Last Updated: 2026-07-29

## 2. Implementation Plan

### 2.1 Plan (§7.1)

**영향 파일 · symbol**

| 파일 | 변경 symbol | 내용 |
|---|---|---|
| `unit/feature-0002-agent-core/src/modules/memory.py` | `mark_timeout_extension_prompted` · `mark_timeout_extension_granted` · `timeout_extension_state` · `_timeout_extension_granted` · `_clear_timeout_extension` | 연장 KV 시그널 5종 (cancel/finalize 패턴 미러링, run_id 짝 검증) |
| `unit/feature-0002-agent-core/src/agent_core.py` | `run_agent` 루프 (`run_timeout_sec` 게이트) · `_call_llm` body timeout · `OpenAI(timeout=)` | 80% 프롬프트 1회 발행, grant 시 예산 컷 해제 + LLM 타임아웃 2층 확장 |
| `shared/runtime_settings.py` | `_TIMEOUT_SPECS` | `AGENT_TIMEOUT_EXTENSION_ENABLED` / `_PROMPT_PCT` / `_MAX_SEC` 3종 추가 |
| `unit/feature-0003-agent-web-ui/src/routers/conversations.py` | `extend_request` (신규 `POST /api/extend`) | 사용자 승인 수신 → KV grant (finalize_request 미러링) |
| `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py` | `_build_ask_status_snapshot` | `timeout_extension` 필드 노출 (ask_status·ask_result 공용) |
| `unit/feature-0003-agent-web-ui/src/app.py` | 권한 카탈로그 · export | `conversation.extend.own/any` 정의 + finalize 보유 역할 backfill |
| `unit/feature-0003-agent-web-ui/src/static/app.js` | 진행 폴링 핸들러 · 컴포저 | 인라인 배너 + [계속 추론] + 백그라운드 브라우저 알림 |
| `unit/feature-0003-agent-web-ui/src/static/style.css` | `.composer-extend-*` | 배너 스타일 |

**접근 (5줄)**

1. 기존 `cancel`/`finalize` 가 쓰는 memory KV 시그널 패턴을 그대로 미러링해 `prompted`
   (워커→사용자) 와 `granted`(사용자→워커) 2방향 플래그를 만든다. run_id 짝 검증으로
   stale run 신호를 격리한다.
2. run 루프는 **어디서도 블로킹하지 않는다** — 80% 에서 플래그만 올리고 계속 추론하며,
   100% 도달 순간에만 grant 를 읽어 통과/종료를 가른다.
3. grant 통과 시 시간 3층(run 예산, `_call_llm` body timeout, httpx 총-대기)을 함께
   풀어야 실효가 있다 — 한 층만 풀면 다른 층에서 잘린다.
4. 프론트는 기존 진행 폴링 스냅샷에 실린 상태만 읽어 배너를 그리므로 새 폴링 경로가 없다.
5. 전부 게이트 뒤(`AGENT_TIMEOUT_EXTENSION_ENABLED`)이며 미승인 경로는 종전과 byte-동치.

**완료 판정 기준 (acceptance criteria)**

- **AC-1**: 콘솔 타임아웃을 낮게 설정한 상태에서 긴 요청을 보내면, 예산 80% 시점에
  컴포저 인라인 배너가 뜬다(탭 백그라운드면 브라우저 알림도).
- **AC-2**: 배너를 무시하면 종전과 동일하게 `"타임아웃으로 종료되었습니다."` 로 끝난다.
- **AC-3**: [계속 추론] 승인 후에는 100% 를 넘겨도 루프가 계속 돌고 답변이 완주한다.
- **AC-4**: 승인은 그 run 한정 — 다음 요청은 다시 기본 타임아웃으로 동작한다.
- **AC-5**: 승인 권한이 없는 계정에는 승인 버튼이 access-blocked 로 표시된다.
- **AC-6**: `AGENT_TIMEOUT_EXTENSION_ENABLED=0` 이면 프롬프트가 발행되지 않고 종전 동작.

**위험도: Major** (§12.3 — 타임아웃 해제는 LLM 토큰 외부 비용에 영향, 백엔드·웹·프론트
3계층 변경). 신규 권한 코드 포함 → §18.8 backend + security + qa 렌즈 대상.

<!-- PLAN-APPROVED by user on 2026-07-29 (AskUserQuestion: 연장 상한=무제한, 확인 UI=인라인 배너+브라우저 알림) -->

## 3. Task Queue

- [x] TASK-20260729T032307-ext-a memory.py 연장 KV 시그널 5종
- [x] TASK-20260729T032307-ext-b agent_core.py 80% 프롬프트 + grant 시 3층 타임아웃 해제
- [x] TASK-20260729T032307-ext-c runtime_settings.py 콘솔 설정 3종
- [x] TASK-20260729T032307-ext-d POST /api/extend + conversation.extend.* 권한 + backfill
- [x] TASK-20260729T032307-ext-e 진행 폴링 + ask_status 스냅샷 timeout_extension 필드
- [x] TASK-20260729T032307-ext-f app.js 인라인 배너 + 브라우저 알림 + 승인 호출
- [x] TASK-20260729T032307-ext-g 테스트 26건 PASS(신규 25 + route-parity 골든 갱신)
- [x] TASK-20260729T032307-ext-h codex 리뷰 + verify-completion + 배포(80cc7aeb) + PB-0008 라이브 PASS

## 4. Blocked
- 없음

## 5. Done
- (진행 중)

## 6. Notes

- **왜 80% 에서 블로킹하지 않는가**: 2026-07-09 사용자 결정(ask-timeout-nonblocking)이
  화면 차단 모달을 폐기했다. 확인 요청도 같은 원칙 — 배너는 알리기만 하고 추론은 계속된다.
- **왜 3층을 다 푸는가**: `AGENT_TIMEOUT_SEC` 는 (a) run 예산 ×3, (b) `_call_llm` 의
  per-attempt body timeout, (c) httpx 총-대기 3곳에 쓰인다(feature-0007
  timeout-console-sync). (a) 만 풀면 (b)/(c) 에서 개별 LLM 호출이 잘려 실효가 없다.

## 7. Completion Checklist

- [x] AC-1·AC-4·AC-5·AC-6 라이브 실증 / AC-2·AC-3 은 단위 테스트 커버(라이브 미재현 사유는
      TEST.md §3·test-runs.d fragment §3 에 정직 표기)
- [x] make test 회귀 0 (환경성 baseline 15건은 main 대조 실행과 동일) + ruff PASS + CI SUCCESS
- [x] 독립 적대 검증 — codex review (사용자 결정: 세션 Agent-tool 제한 ↔ §18.8 상충 시 codex 경로).
      P1×4·P2×3 전건 반영 → REVIEW.md REV-20260729-0001
- [x] verify-completion --pre-commit PASS
- [x] PB-0008 라이브 시각검증 PASS (배포 80cc7aeb 후 — 배너 노출·승인 전환·중단 2초 반영)
