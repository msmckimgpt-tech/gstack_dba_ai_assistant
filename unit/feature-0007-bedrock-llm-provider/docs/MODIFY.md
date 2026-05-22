---
doc_type: MODIFY
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260521-0001
- Date: 2026-05-21
- Related Requirement: REQ-20260521-0001, REQ-20260521-0002, REQ-20260521-0003
- Summary: API Vault (사용자별 OpenAI API key 입력 wizard) 패턴을 전면 폐기하고
  서비스 단일 AWS Bedrock 자격증명 (Seoul region `ap-northeast-2`, LiteLLM proxy
  gateway 경유) 으로 LLM 호출 entry 를 일원화. 모델 카탈로그 GPT-5.4 시리즈 →
  Claude Sonnet/Haiku 4.x 로 교체.
- Files:
  - 신규: `unit/feature-0007-bedrock-llm-provider/docs/{FUNCTION,TASK,ANCHOR,MODIFY,REVIEW,REPORT,TEST,DECISIONS,AGENTS}.md`
  - 신규: `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`
  - 수정: `docker-compose.yml` — `bedrock-gateway` 서비스 추가 + x-agent-common
    의 depends_on 에 healthcheck 추가
  - 수정: `.env.example` — `BEDROCK_GATEWAY_URL` / `BEDROCK_GATEWAY_API_KEY` /
    `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 5 env 추가
  - 수정: `unit/feature-0002-agent-core/src/modules/config.py` — `LLM_BASE_URL` /
    `LLM_API_KEY` fallback chain 에 `BEDROCK_GATEWAY_*` 최우선 추가. `OPENAI_MODEL`
    default `gpt-5-nano` → `claude-haiku-4`
  - 수정: `unit/feature-0002-agent-core/src/modules/model_catalog.py` —
    `API_MODEL_OPTIONS` GPT-5.4 3 종 제거 + Claude Sonnet/Haiku 4.x 2 종 추가.
    `API_DEFAULT_MODEL = "claude-haiku-4"`
  - 수정: `unit/feature-0002-agent-core/src/modules/llm.py` — `_get_openai_client`
    의 `effective_key = LLM_API_KEY or OPENAI_API_KEY` 단순화 (LLM_API_KEY 단일)
  - 수정: `unit/feature-0002-agent-core/src/agent_core.py` — `_run_agent_core`
    의 `api_key` 인자 deprecated (받아도 무시). `use_local` 분기 + per-request
    api_key 결정 로직 → env 단일 소스로 단순화
  - 수정: `unit/feature-0003-agent-web-ui/src/app.py` — `_decrypt_api_key` /
    `_is_safe_api_key` / `_is_safe_passphrase` 함수 제거. `/api/api-vault/options`
    semantic 단순화 (cipher 시멘틱 X, model catalog 만). `/api/ask` 의 cipher
    파라미터 + 검증 분기 + 복호화 경로 + `_run_agent_core(api_key=...)` 인자 제거
  - 수정: `unit/feature-0003-agent-web-ui/src/static/index.html` — Profile drawer
    "API Vault" 탭 버튼 + pane DOM 제거 (탭 list `account` / `security` /
    `prompt` 3 종으로 축소). cache-bust `v=20260519-audit-tab` →
    `v=20260521-bedrock-cutover`
  - 수정: `unit/feature-0003-agent-web-ui/src/static/app.js` — vault DOM 참조
    const / `STORAGE_KEYS` / `readVaultState` / `writeVaultState` /
    `clearVaultState` / `computeVaultReadiness` / `updateVaultReadiness` /
    `syncVaultSteps` / `renderVaultSavedCard` / `refreshVaultUI` /
    `encryptPlainApiKey` 함수 일괄 제거. `loadVaultOptions` 의미 단순화 (model
    catalog 만). `sendPrompt` body 의 `api_key_cipher` / `api_key_passphrase` /
    `vault.model` 제거. LEGACY_VAULT_KEYS cleanup 1 회 추가
  - 수정: `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.vault-banner`
    / `.vault-stepper` / `.vault-step*` / `.vault-primary-btn` / `.vault-saved*`
    / `.vault-danger-zone` / `.vault-advanced*` 186 줄 일괄 제거
  - 수정: `unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust
    버전 bump
  - 수정: `docs/SECURITY.md` — §6.1 LLM provider 자격증명 정책 신설 + §9.2
    `_AUDIT_MASKED_FIELDS_API_KEY` 에 Bedrock gateway / AWS credential 필드 추가
  - 수정: `docs/DECISIONS.md` — ADR-0022 append (Bedrock 전환 정본)
  - 수정: `docs/STATUS.md` — feature-0007 row 추가 + 최근 갱신 entry 1 건
- Impact:
  - 사용자 UX: 신규 사용자 등록 시 API key 입력 진입 장벽 사라짐. 기존 사용자의
    localStorage 의 `v1:` cipher 는 cache-bust 후 자동 cleanup (silent).
  - 운영: AWS IAM credential 1 set 가 `bedrock-gateway` 컨테이너 env 로 주입
    필요. 사내 시크릿 관리자에서 발급. `bedrock:InvokeModel` 권한 + Claude
    Sonnet/Haiku 4.x model access 활성화 사전 필요 (AWS console).
  - 비용 책임: per-user OpenAI 청구 → 서비스 운영자 단일 청구. 사내 한정 환경
    에서 비용 책임 운영자 이전.
  - 회귀 risk: GPT-5.4 → Claude 4.x 모델 swap 으로 SQL 생성 / tool use 품질
    회귀 가능성 (LiteLLM 이 schema 변환 책임). Phase E smoke test 로 확인 필요.
- Rollback Notes:
  - 단일 commit revert + cache-bust 되돌리기로 복구 가능.
  - rollback 후 기존 사용자 frontend cache 가 cleanup 된 상태라 사용자가 새로
    API key 입력 필요 (cache-bust cleanup 1 회 통과 사실 기록).
  - AWS Bedrock 자격증명은 rollback 후 무용 — 운영자가 별도 비활성화 권장.
  - 긴급 시 cherry-pick 으로 부분 rollback 가능 (frontend 만 복구 / backend
    만 복구 등).

## CHG-20260521-0002
- Date: 2026-05-21
- Related Requirement: REQ-20260521-0001~3 (Phase E 검증 결과 반영)
- Summary: Phase E 실 환경 검증 (`docker compose -p feature-0007-e up -d
  bedrock-gateway`) 결과 AWS Bedrock Seoul region 의 ACTIVE Claude Sonnet/Haiku
  4.x 가 모두 `global.*` inference profile 만 제공하는 사실 확인. region-pinned
  on-demand 호출 + APAC profile (LEGACY Sonnet 4) 모두 실용 불가 (LEGACY 의
  30일 미사용 access denied). 사용자 reanchor 후 global Sonnet 4.6 수용으로
  결정 변경 + 정책 doc reanchor.
- Files:
  - 수정: `unit/feature-0002-agent-core/src/modules/model_catalog.py` —
    `API_DEFAULT_MODEL = "claude-haiku-4"` → `"claude-sonnet-4"` (사용자 결정 1
    "Sonnet 모델로 진행").
  - 수정: `unit/feature-0002-agent-core/src/modules/config.py` — `OPENAI_MODEL`
    env default `"claude-haiku-4"` → `"claude-sonnet-4"`.
  - 수정: `unit/feature-0003-agent-web-ui/src/static/app.js` — `sendPrompt` body
    의 model fallback `"claude-haiku-4"` → `"claude-sonnet-4"`.
  - 수정: `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`
    — `claude-sonnet-4` alias 의 실 Bedrock ID 가 `bedrock/anthropic.claude-sonnet-4-6`
    → `bedrock/global.anthropic.claude-sonnet-4-6` (inference profile 강제),
    `claude-haiku-4` 도 `global.anthropic.claude-haiku-4-5-20251001-v1:0` 로 갱신.
  - 수정: `unit/feature-0007-bedrock-llm-provider/docs/ANCHOR.md` — §1 외부 관점
    의 "Seoul region 한정" 표현이 "global inference profile 수용 (사용자 reanchor)"
    로 변경. §2 Alt-E "cross-region inference 허용" 의 "안 고른 이유" 가 "실제
    채택 (사실 검증 후)" 으로 번복.
  - 수정: `docs/SECURITY.md` §6.1 — region 정책의 "cross-region inference 금지로
    데이터 한국 region 잔류" 표현 제거, global routing 수용 + risk 명시로 교체.
  - 수정: `docs/DECISIONS.md` ADR-0022 — "2026-05-21 Phase E 검증 결과 (ADR-0022
    addendum)" 섹션 append. AWS API 호출 결과 (foundation-models / inference-
    profiles list, ResourceNotFoundException 응답 등) 사실 기록.
  - 신규: `.worktrees/0007-bedrock-llm-provider/.env` (gitignore 됨) — Phase E
    검증용 minimal .env. 운영 컨테이너 (`mysql_ai_delegated_dev`) 와 포트 격리
    (`-p feature-0007-e`). AWS 자격증명은 host shell 의 `aws configure get`
    값을 export 후 inline 주입 (.env 평문 미보관).
- Impact:
  - **사용자 결정 4 (Seoul region 한정) 완화**: PIPA 엄격 잔류 → 사내 한정 +
    비-개인정보 SQL 작업 가정으로 risk 수용. 엄격 잔류 필요 시점에는 별 cycle.
  - **frontier 품질 회복**: ACTIVE Sonnet 4.6 사용 가능 (LEGACY Sonnet 4 fall-
    back 불가 — 30일 access denied).
  - **운영 부담**: 운영자가 AWS Bedrock 의 `apac.*` profile 추가 release 모니터링
    필요 — 미래에 ACTIVE Sonnet 의 APAC profile 추가 시 region-pinned 마이그레
    이션 별 cycle 권장.
- Rollback Notes:
  - 본 변경은 CHG-20260521-0001 의 후속이라 단일 commit 안에 묶일 수 있음.
  - revert 시 model ID 가 추정값으로 돌아가지만 실 호출은 LEGACY access denied
    로 실패. 본 cycle 의 model ID 가 정합.
  - global routing 정책을 다시 엄격 잔류로 회귀하려면 별 ADR 로 본 ADR-0022
    addendum 을 superseded 처리 + Provisioned throughput 또는 별 provider 도입
    plan.

## CHG-20260522-0001
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (codex review P1 fix)
- Summary: codex review (PR #62, 2026-05-22) 의 [P1] BLOCKER 발견 — `/api/session`
  endpoint 의 default_model fallback 3 사이트가 `os.getenv("OPENAI_MODEL", "auto")`
  로 정의되어 있어, upgrade 시점 `.env` 의 `OPENAI_MODEL` 미설정 또는 old GPT
  값 잔존 시 frontend 가 invalid model alias 를 `/api/ask` body 에 첨부 → backend
  `_is_allowed_api_model` 의 400 차단 회귀. SUBAGENT panel 의 NEEDS-TWEAK #3
  영역을 codex 가 P1 BLOCKER 로 격상 (ship 직후 첫 사용자 turn 실패) — 즉시
  fix 진행.
- Files:
  - 수정: `unit/feature-0003-agent-web-ui/src/app.py` — `/api/session` 의 3
    사이트 (line 5102 / 5112 / 5135) 에서 `os.getenv("OPENAI_MODEL", "auto")`
    → `os.getenv("OPENAI_MODEL", API_DEFAULT_MODEL)`. `API_DEFAULT_MODEL` 은
    이미 line 44 에서 `from modules.model_catalog` import 되어 있어 추가 import
    불요.
- Impact:
  - **Ship-after 회귀 차단**: upgrade 환경의 `.env` `OPENAI_MODEL` 잔존 / 미설정
    상태에서도 frontend 가 catalog 안 모델 alias 를 사용 → `/api/ask` 의 첫
    사용자 turn 이 정상 200 응답.
  - **single source-of-truth**: `model_catalog.API_DEFAULT_MODEL = "claude-sonnet-4"`
    가 frontend default 의 정본. 운영자가 env 미설정 시 자동 정합.
  - **운영 호환**: 운영자가 `.env` 의 `OPENAI_MODEL` 을 명시 설정한 경우 그 값이
    여전히 우선 — backward-compat 유지 (단 그 값이 catalog 에 포함되어야 정상
    동작 — 운영자 책임).
- Rollback Notes:
  - 1-line × 3 patch. revert 시 `'auto'` fallback 회귀로 첫 turn 실패 재발.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - codex review P1 finding 의 권고 (Option 2: "make `/api/session` return the
    new default") 와 정합.

## CHG-20260522-0002
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (codex P1 보강 + Phase E full-stack 회귀)
- Summary: Phase E full-stack smoke 진행 중 CHG-20260522-0001 의 P1 fix 가
  운영 `.env` 의 `OPENAI_MODEL=auto` 잔존 시점에 fallback 미발동 사실 발견.
  codex P1 권고 옵션 2 ("/api/session 가 invalid model 을 catalog default 로
  대체") 를 정확히 적용한 보강. 신규 helper `_resolve_session_default_model()`
  이 catalog 검증 + Local LLM 가용성 cross-check.
- Files:
  - 수정: `unit/feature-0003-agent-web-ui/src/app.py` — `_resolve_session_default_model()`
    helper 신설 (line 5085 부근, `@app.get("/api/session")` decorator 위쪽).
    `/api/session` 의 3 응답 사이트 (line 5102/5112/5135) 가 `os.getenv("OPENAI_MODEL",
    API_DEFAULT_MODEL)` → `_resolve_session_default_model()` 호출.
- 보강 fix 로직:
  - `OPENAI_MODEL` env 가 미설정 → `API_DEFAULT_MODEL` (= `claude-sonnet-4`)
    fallback (CHG-0001 의 의도)
  - `OPENAI_MODEL` env 가 설정됐지만 catalog (`is_allowed_api_model`) 통과 못
    함 → `API_DEFAULT_MODEL` fallback
  - `OPENAI_MODEL=auto` 류 Local LLM alias + `LOCAL_LLM_API_BASE` 미가용 →
    `API_DEFAULT_MODEL` fallback (Local LLM gateway 비활성화 시점에 invalid
    alias 차단)
  - `OPENAI_MODEL=auto` + Local LLM gateway 가용 → `auto` 반환 (transition 호환)
  - `OPENAI_MODEL=claude-sonnet-4` 등 명시적 valid alias → 그대로 반환
- Impact:
  - **운영 .env 청소 부담 감소**: Bedrock 전환 시 `OPENAI_MODEL` 의 stale 값
    (예: `auto`, `gpt-5.4-nano`) 가 잔존해도 frontend 가 invalid model 을
    `/api/ask` 에 첨부 안 함.
  - **transitional 호환**: Local LLM gateway 동시 가용 시점에는 `auto` 그대로
    사용 가능 — 운영자가 한 번에 모든 env 변경 부담 X.
  - **codex P1 권고 옵션 2 직접 반영**: "make /api/session return the new
    default" 가 본 보강 fix 의 행동.
- Phase E full-stack smoke 결과 (격리 컨테이너 `-p feature-0007-e`):
  - TEST-0001 gateway healthcheck PASS (Phase E Run 2026-05-21-002 이미 PASS)
  - **TEST-0002 `/api/ask` cipher 미동봉**: PASS — bootstrap admin 로그인 후
    `model: claude-sonnet-4` body 로 호출 → 200 응답 + conversation_id 생성
    + bedrock-gateway 가 `POST /v1/chat/completions 200 OK` 로깅.
  - **TEST-0003 agent loop tool_use schema 변환**: PASS — `SHOW DATABASES`
    질의 → Claude Sonnet 4.6 plan generation 결과 `action=step + tool=execute_sql
    + sql=SHOW DATABASES`. LiteLLM 의 OpenAI tool_calls ↔ Anthropic tool_use
    변환 작동 검증 (codex blindspot #2 + SUBAGENT NT #4 의 최대 잠재 회귀
    영역 PASS).
  - **TEST-0004 JSON 파싱**: PASS — agent loop 의 plan 이 markdown fence 안
    JSON 으로 반환되어도 `_extract_json_object` 의 greedy regex 가 정상 추출.
  - **TEST-0005 frontend 신규 사용자 진입 + TEST-0006 localStorage cleanup**:
    브라우저 필요 — 코드 trace 로 갈음 (LEGACY_VAULT_KEYS cleanup 페이지 로드
    1 회 실행 + drawer-tabs 3 탭만 노출 + sendPrompt 의 model fallback chain
    이 `state.session.default_model` (P1 fix 보장) 사용).
- 발견 및 검증된 추가 사실:
  - 운영 `.env` 가 실제로 `OPENAI_MODEL=auto` 로 설정되어 있음 (운영 repo/.env
    확인) — 본 cycle 의 codex P1 finding 의 정확한 회귀 시나리오 검증.
  - `_LOCAL_LLM_ENABLED` cache 가 module load 시점 한 번 평가 — `LOCAL_LLM_API_BASE`
    env 변경 시 web 컨테이너 재기동 필수 (운영 안내 필요 — 별 cycle).
  - LiteLLM `main-stable` 의 `/health/liveliness` endpoint 정상 동작.
  - bedrock-gateway 와 LiteLLM proxy 의 schema 변환이 본 backend 의 system
    prompt + JSON mode + tool_calls 모두 cover.
- Rollback Notes:
  - `_resolve_session_default_model()` 함수 제거 + 3 사이트의 호출을 다시
    `os.getenv("OPENAI_MODEL", API_DEFAULT_MODEL)` 로 변경하면 CHG-0001 상태
    복귀.
  - 운영 `.env` 의 `OPENAI_MODEL=auto` 잔존 + LOCAL_LLM 비활성화 시점에는 첫
    `/api/ask` 가 다시 400 차단 회귀 — rollback 비권장.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - docker compose -p feature-0007-e (격리) 의 full stack smoke 4 case PASS.
