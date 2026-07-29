---
doc_type: MODIFY
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260729T032307-timeout-extension
- Date: 2026-07-29
- Related Requirement: REQ-20260729T032307-timeout-extension-{prompt,grant,default-deny}
- Summary: 실행 예산의 80%(설정 가능)에 도달하면 사용자에게 "이번 요청만 끝까지 추론할까요?"를
  비차단으로 묻고, 승인한 run 에 한해 시간 축 3층(run 예산 · `_call_llm` per-attempt body
  timeout · httpx 총-대기)의 컷을 해제한다. 승인이 없으면 종전 동작(타임아웃 종료) 유지.
- Files:
  - `unit/feature-0002-agent-core/src/modules/memory.py` — 연장 KV 시그널 5종 신설
    (`mark_timeout_extension_prompted` / `mark_timeout_extension_granted` /
    `_timeout_extension_granted` / `timeout_extension_state` / `_clear_timeout_extension`),
    cancel·finalize 와 동일한 run_id 짝 검증.
  - `unit/feature-0002-agent-core/src/agent_core.py` — `_timeout_extension_settings()` ·
    `_EXTENSION_UNCAPPED_TIMEOUT_SEC` 신설, run 루프에 임계 프롬프트 1회 발행 + 예산 초과
    시점의 grant 게이트, `_call_llm(timeout_override=)` 추가(호출 3곳 배선),
    `client.with_options(timeout=)` 재바인딩, terminal 시 시그널 정리.
  - `shared/runtime_settings.py` — `AGENT_TIMEOUT_EXTENSION_ENABLED` / `_PROMPT_PCT` /
    `_MAX_SEC` 3종을 '쿼리·에이전트 실행' 카테고리에 추가(apply_mode=live).
  - `unit/feature-0003-agent-web-ui/src/routers/conversations.py` — `POST /api/extend` 신설
    (finalize 미러링 + 기능 게이트), `/api/progress` 응답에 `timeout_extension` 동봉.
  - `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py` — ask_status/ask_result 공용
    스냅샷에 `timeout_extension` 필드(`_timeout_extension_snapshot`).
  - `unit/feature-0003-agent-web-ui/src/web_context.py` — `conversation.extend.{own,any}`
    권한 정의 + operator/sales 시드 + `_backfill_extend_perms_v1` 1회 backfill.
  - `unit/feature-0003-agent-web-ui/src/app.py` — memory 헬퍼 re-export.
  - `unit/feature-0003-agent-web-ui/src/static/{index.html,styles.css,app.js,admin.js}` —
    컴포저 위 인라인 배너 + [계속 추론] + 백그라운드 브라우저 알림 + 권한 라벨/종속 매핑.
  - `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` — 골든 갱신(221→222).
  - `docs/ROUTEMAP.md` — 재생성.
- Impact:
  - **기본 동작 무변경**: 승인이 없으면 종전과 동일한 시점에 동일한 메시지로 종료한다.
  - **비용**: 승인된 run 은 더 오래 실행되어 LLM 사용량이 늘 수 있다. 도구 호출 상한
    (`max_steps`) · '중단'/'즉시 답변' · 워커 lease fencing 은 연장 중에도 그대로 작동한다.
  - **인가**: 신규 권한 2종. 기존 배포는 `conversation.finalize.{own,any}` 보유 역할에 1회
    backfill 되어 도입 즉시 사용 가능(시드 밖 배포 전용 역할 포함).
  - 마이그레이션 없음(alembic 무변경). KV·설정만 사용.
- Rollback Notes:
  - 즉시 무력화: 관리 콘솔 `타임아웃 임박 시 사용자 확인 후 연장` = 0 (재배포 불필요, live).
  - 코드 롤백: 본 CHG 의 파일 되돌림. KV 키는 run 종료 시 자동 정리되므로 잔재 없음.
  - 권한 backfill 은 `WebSchemaMigrations` 의 `conversation-extend-perms-v1` 마커로 1회성 —
    롤백 시 권한 행이 남지만 엔드포인트가 없으므로 무해(무권한 코드로 방치).
