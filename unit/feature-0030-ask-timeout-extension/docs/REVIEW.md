---
doc_type: REVIEW
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260729-0001 [CODEX:feature-0030-timeout-extension] — CHANGES-REQUESTED → 전건 반영

- Related Change: CHG-20260729T032307-timeout-extension
- 검증 수단: `/codex review` (OpenAI Codex CLI, `model_reasoning_effort=high`, read-only
  sandbox). staged diff 전량 투입. 사용자 결정(2026-07-29) — 세션의 Agent-tool 제한과
  AGENTS.md §18.8 패널 요구가 상충해 사용자에게 확인 후 codex 경로를 선택.
- 요청 렌즈 5축: 신규 권한 인가·backfill / 비용·DoS 유사 리스크 / KV run_id 경합 /
  미승인 경로 무회귀 / 프론트 배너 stale.
- 판정: **P1 4건 · P2 3건** (전건 수정 완료).

### P1-1 `/api/extend` 가 승인 대상 run_id 를 검증하지 않음
요청의 `run_id` 를 무시하고 `last_status_run_id` 를 그대로 승인 대상으로 삼았다. R1 의 stale
배너를 R2 실행 중에 클릭하면 사용자가 보지도 않은 R2 가 무제한 연장된다. `last_status_run_id`
가 비면 짝 검증이 wildcard 로 퇴화한다.
→ **수정**: 클라이언트가 배너의 `run_id` 를 함께 전송, 서버가 현재 run 과 대조해 불일치·부재 시
409. `mark_timeout_extension_granted` 는 `run_id` 필수 + 현재 prompt 대상과 불일치 시 False.
`_timeout_extension_granted` 는 빈 값 허용을 제거하고 완전 일치만 승인으로 인정.

### P1-2 KV 단일 슬롯이라 동시 run 간 승인이 오염
새 run 의 prompt 가 `timeout_ext_run_id` 만 덮어써서, 이전 run 의 `granted=1` 이 남아 새 run 이
남의 승인을 상속했다.
→ **수정**: `mark_timeout_extension_prompted` 가 승인 흔적(`granted`/`granted_at`)을 함께 리셋.

### P1-3 승인 후 기존 안전장치가 장시간 호출 중에는 무효 (가장 중대)
per-call 상한을 86400s 로 올려, 단일 LLM 호출이 도는 동안 루프가 한 바퀴도 안 돌아 취소·즉시
답변·`max_steps`·lease fencing 이 전부 무응답이 됐다. 승인의 대가로 탈출구를 잃는 구조.
→ **수정**: 연장이 푸는 것은 **run 전체 예산**뿐. per-call 상한은
`_EXTENSION_PER_CALL_TIMEOUT_SEC=900`(15분)으로 유지 — 이 값이 곧 '중단' 의 최대 응답 지연이다.

### P1-4 finalize → extend 자동 backfill 이 과도한 권한 확대
'중단'(finalize)과 '비용 유발 계속 실행'(extend)은 위험 방향이 반대인데 `any` 까지 자동 부여했다.
→ **수정**: backfill 대상을 `own` 으로 축소. `conversation.extend.any` 는 관리자 콘솔 명시 부여.

### P2-1 기능 게이트 조회 실패가 fail-open
워커의 `_timeout_extension_settings()` 는 fail-closed 인데 API 는 예외를 삼키고 승인을 기록했다.
설정 장애 중 생긴 stale 승인이 기능 재활성 때 되살아난다.
→ **수정**: 예외 시 503 거절(양쪽 대칭).

### P2-2 프론트 run_id 검증이 빈 값을 허용
`sameRun` 이 `!ext.run_id || !runId` 를 일치로 처리해, torn snapshot·id 누락 시 이전 run 의
배너·브라우저 알림이 현재 화면에 떴다.
→ **수정**: 양쪽 존재 + 완전 일치일 때만 노출.

### P2-3 prompt 발행이 독립 타이머가 아니라 루프 경계에 묶임
직전 LLM 호출이 길면 임계 통과를 루프가 늦게 봐서, 확인이 종료 직전에야 뜨거나 아예 못 뜬다.
→ **수정(완화)**: 예산 초과 시점에도 미발행이면 그때 발행하고,
`_EXTENSION_GRACE_SEC=20` 만큼만 승인을 더 기다린다(대기 중 취소는 매 초 검사). 어차피 종료될
run 이라 손해가 없고, 사용자가 실제로 답할 창을 보장한다. 독립 heartbeat 타이머로의 전환은
복잡도 대비 이득이 불명확해 채택하지 않음(잔여 위험으로 명시).

### 잔여 위험 (수정하지 않음, 의도적)
- 승인된 run 은 `max_steps` 소진까지 돌 수 있어 LLM 비용이 증가한다 — 이는 기능의 목적이며,
  사용자가 매번 명시로 눌러야 하는 opt-in 이다. 상한이 필요하면 콘솔의 `연장 승인 시 추가 허용
  시간` 을 0 이외로 설정한다.
- prompt 발행 지연은 유예로 완화했을 뿐 제거되지 않았다(단일 LLM 호출이 유예보다 훨씬 길면
  여전히 늦다).

### 검증
- 신규/갱신 테스트 36건 PASS(P1-1·P1-2·P1-3·P1-4·P2-1·P2-2 각각에 회귀 테스트 추가).
- 전체 회귀: 본 변경 전 `main` 대조 실행과 동일한 환경성 실패 15건 외 회귀 0.
