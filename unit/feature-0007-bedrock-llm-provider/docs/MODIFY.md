---
doc_type: MODIFY
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260707-oauth-cron-static-refresh
- Date: 2026-07-07
- Related Requirement: (운영 chore — 사용자 지시) claude-corp 세션 윈도우 오염 원인 제거
- Summary: `refresh-claude-oauth-token.sh` 의 24/7 30분 주기 cron 이 매 실행마다
  Anthropic `/v1/messages` 라이브 probe(2026-06-29 도입)를 호출해, claude-corp
  계정의 5시간 rolling 세션 윈도우 경계가 `:00`/`:30` 격자에 계속 재고정되고
  `session-keepalive-cron.sh`(07:35/12:35 앵커 핑)가 그 날의 첫 실호출이 되지
  못해 리셋 시각이 드리프트하는 문제를 근본 제거. 2026-07-03 insight-llm-fallback
  이후 이 probe 는 litellm 요청-레벨 fallback(`fallbacks:` 체인)과 구조적으로
  중복이었음을 확인 — probe 를 전면 제거하고 파일 만료 여부만 검사하는
  static_check() 단독 판정으로 재설계했다.
- Files:
  - 수정: `bin/refresh-claude-oauth-token.sh` — `live_probe()` 함수 + `CLAUDE_OAUTH_PROBE`
    / `CLAUDE_OAUTH_PROBE_MODEL` / `CLAUDE_OAUTH_PROBE_TIMEOUT` env var 전면 제거.
    `select_account()` 가 static_check() 만으로 판정(네트워크 호출 0). 헤더 주석을
    새 설계 + 제거 배경으로 재작성. 로그 기반 관측 함수 `log_fallback_observability()`
    신설 — 매 실행 시 `docker compose logs --since $CLAUDE_OAUTH_OBS_WINDOW(기본 35m)
    bedrock-gateway` 를 읽어(실 API 호출 아님, 로컬 컨테이너 stdout) RateLimitError/
    AuthenticationError 발생 건수를 집계, 0건이면 무음(로그 비대화 방지).
  - (git 미추적) host `root` crontab — `refresh-claude-oauth-token.sh` 항목 위에 남아있던
    2026-07-02 stale 주석 블록("평일 10:00~19:00" 스케줄 설명, 실제로는 2026-07-04 에 이미
    24/7 로 대체돼 무관한 backup/metadata-graph-sync cron 항목들 사이에 낀 채 방치돼
    있었음) 제거 + 2026-07-04/2026-07-07 변경 이력을 실제 스케줄(24/7 `*/30`)과
    일치하도록 재작성. 백업 `/tmp/crontab-root-backup-20260707112835.txt`.
- Verification: `bash -n` PASS. `--check` 모드로 정적 검사만으로 claude-corp/root
  두 계정 정상 선택 확인(라이브 API 호출 없음). `docker` 미가용 PATH 에서도
  스크립트가 abort 없이 정상 완주(관측 함수 fail-open 확인). litellm 소스
  (`router.py` `should_retry_this_error` / `async_function_with_fallbacks_common_utils`)
  직접 확인 — AuthenticationError(401)·RateLimitError(429) 모두 예외 타입과
  무관하게 fallback 경로를 탐(ContextWindowExceededError/ContentPolicyViolationError
  만 별도 특별 처리). 실 계정 회복(claude-corp 자동 복귀) 동작은 무변경 — 자격증명
  파일이 유효한 한 매 실행마다 계속 1순위로 주입되므로 별도 로직 불필요.
- Rollback: 이전 커밋의 `bin/refresh-claude-oauth-token.sh` 로 되돌리고 crontab 에
  `CLAUDE_OAUTH_PROBE=1` (또는 무지정, 구버전 기본값) 을 명시.
- Risk: Minor (§12.3) — 개발 단계 전용 임시 스크립트(헤더에 명시)의 내부 판정
  로직 단순화. auth/네트워크/보안 표면 변화 없음(오히려 외부 API 호출 제거로
  표면 축소). 실 429/401 대응은 이미 검증된 litellm 요청-레벨 fallback 이 전담.

## CHG-20260625T171844
- Date: 2026-06-25
- Related Requirement: (운영 chore — 사용자 지시) DQA LLM 게이트 호출 주체 일시 우회
- Summary: 개발 단계 LLM provider 호출 주체를 claude-corp 회사 OAuth → root 개인
  OAuth (`/root/.claude`, subscriptionType `max`) 로 임시 전환. `refresh-claude-oauth-token.sh`
  에 `CLAUDE_OAUTH_ACCOUNT` env var 기반 토큰 출처 계정 선택을 추가 (미지정 시
  claude-corp = 기존 동작 유지). crontab 의 사전 배치된 root 라인 활성화 + claude-corp
  라인 비활성화. 즉시 1회 실행으로 root 토큰 주입 + gateway force-recreate.
- Files:
  - 수정: `bin/refresh-claude-oauth-token.sh` — `ACCOUNT="${CLAUDE_OAUTH_ACCOUNT:-claude-corp}"`
    + `case` 분기로 `CRED` 경로 선택 (root→`/root/.claude/.credentials.json`,
    그 외→`/home/<name>/.claude/.credentials.json`). 헤더 주석·로그를 계정-중립화.
  - (git 미추적) host `root` crontab — claude-corp 라인 주석 + `CLAUDE_OAUTH_ACCOUNT=root`
    라인 주석 해제. 백업 `/tmp/crontab-backup-*.txt`.
  - (git 미추적) `.env.bedrock` `ANTHROPIC_API_KEY` — 스크립트가 root 토큰으로 교체 (gitignored).
- Verification: 게이트웨이 토큰 끝6자 == root 토큰 (≠ claude-corp), `bedrock-gateway`
  health=healthy, root 토큰 만료 여유 ~5h. 토큰 생명주기는 claude-corp 때와 동일
  메커니즘 (계정 주체만 상이 — root VSCode Claude Code refresh + cron 30분 재주입).
- Rollback: crontab 두 라인 토글 역전 + `bash bin/refresh-claude-oauth-token.sh` (env 없이 → claude-corp).
- Risk: Minor (§12.3) — backwards-compatible, auth/네트워크/보안 표면 변화 0, 비밀정보
  미추적. ⚠ 개발용 임시 (구독 OAuth 는 서비스 운용 부적합).

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

## CHG-20260522-0003
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (codex P2 follow-up — paired
  fallback chain)
- Summary: codex review (REV-20260522-0002) 의 [P2] finding — `LLM_BASE_URL`
  과 `LLM_API_KEY` 의 독립 fallback chain 으로 partial 설정 시 silent misroute
  위험 — 의 follow-up 보강. 신규 helper `_select_llm_provider()` 가 (base_url,
  api_key) tuple 을 paired 결정. .env.example 도 paired 정책 명시 안내 추가.
- Files:
  - 수정: `unit/feature-0002-agent-core/src/modules/config.py` — `LLM_BASE_URL`
    / `LLM_API_KEY` 결정을 `_select_llm_provider()` paired tuple 로 교체. 우선
    순위: Bedrock paired → Local LLM paired → OpenAI direct (API_KEY only,
    BASE optional).
  - 수정: `.env.example` — Bedrock 섹션에 "paired 설정 필수" 안내 + LLM provider
    우선순위 3 항목 명시.
- Impact:
  - **Silent misroute 차단**: BEDROCK_GATEWAY_URL 만 설정 + BEDROCK_GATEWAY_API_KEY
    비어있는 경우 → Bedrock 분기 skip → 다음 provider (Local LLM 또는 OpenAI)
    선택. gateway 가 잘못된 key 받아 401 응답하던 회귀 차단.
  - **운영 안내 명확화**: .env.example 의 주석이 paired 정책을 명시하여 운영자
    가 부분 설정 시 행동 예측 가능.
  - **transitional 호환**: 기존 운영 (OPENAI_API_KEY only) 환경은 본 변경
    영향 없음 — `_select_llm_provider()` 의 fallback 3 단계가 OpenAI direct.
- Rollback Notes:
  - `_select_llm_provider()` 함수 제거 후 이전 `LLM_BASE_URL = X or Y or Z`
    /`LLM_API_KEY = X or Y or Z` 패턴 복원 가능. 단 codex P2 의 silent misroute
    회귀 재발.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py`
    PASS.
  - Web container 에서 module reload 후 `LLM_BASE_URL` / `LLM_API_KEY` 둘 다
    Bedrock gateway 값으로 paired 출력 확인 (BEDROCK_GATEWAY_API_KEY 채워진
    환경 → Bedrock 분기 선택 정상).

## CHG-20260522-0004
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (codex 6 blindspot 보강)
- Summary: codex review (REV-20260522-0002) 가 본 PR diff 검토 외로 위임한 6
  blindspot 의 일괄 보강. 코드 변경 3 영역 (max_tokens cap / masked field
  drift / 정책 doc reanchor) + 분석 결과 3 영역 (tool_use 변환 / data region
  / reasoning content) 의 REVIEW.md 기록.
- Files (코드 + 정책 doc):
  - 수정: `unit/feature-0002-agent-core/src/modules/model_catalog.py` —
    blindspot #4 (max_tokens cap). `_CLAUDE_MAX_TOKENS` dict 신설 (task 별 cap:
    insight 2048 / agent 8192 / summary 1024 / sql_fix 2048 / validate 1024).
    `max_tokens_for_model()` 가 Claude alias (`claude-` prefix) 인 경우 본
    dict 의 cap 반환 — 비용 폭주 worst-case 차단.
  - 수정: `unit/feature-0003-agent-web-ui/src/app.py` — blindspot #6
    (`_AUDIT_MASKED_FIELDS_API_KEY` doc-code drift). tuple 에 `bedrock_gateway_api_key`,
    `aws_access_key_id`, `aws_secret_access_key` 3 항목 추가. SECURITY.md §9.2
    명시와 code 정합.
  - 수정: `docs/SECURITY.md` §6.1 — blindspot #1 (env_file scoping vs SECURITY
    policy false-claim). "gateway 컨테이너 env 에만 주입" 표현을 정확한 사실로
    교체: `env_file: - .env` inherit 으로 AWS_* 가 다른 컨테이너 process env
    에도 노출되나, application code 는 이를 참조하지 않음 + 사내 root 자격증명
    전제 하에 isolation 가치 낮음 명시. 엄격 isolation 필요 시점은 별 cycle
    명시. Paired fallback 정책 (CHG-0003) 도 부가 명시.
- Files (분석 결과 REVIEW.md 기록 — 코드 변경 X):
  - blindspot #2 (Claude tool_use 변환): Phase E full-stack TEST-0003 으로
    PASS 확인. LiteLLM 이 OpenAI tool_calls ↔ Anthropic tool_use 변환 정상.
  - blindspot #3 (data region): Phase E 검증으로 `global.*` inference profile
    수용 사용자 reanchor + SECURITY.md §6.1 region 정책 갱신 완료. AWS Bedrock
    의 global routing 은 미국/EU/APAC 어느 region 에든 hit 가능 — PIPA 엄격
    잔류 시점은 별 cycle.
  - blindspot #5 (reasoning content): agent_core.py:1370 의 fallback 이 이미
    `response_message.reasoning` + `response_message.reasoning_content` 둘 다
    check. Claude 가 LiteLLM 변환 후 OpenAI o1-style reasoning_content 노출
    하면 본 fallback path 가 정상 처리 — 별도 코드 변경 불요.
- Impact:
  - **비용 안전망 (max_tokens cap)**: Claude Sonnet 4.6 의 default cap 64K
    까지 채우는 worst-case 비용 폭주 차단. task 별 cap 으로 운영 비용 예측
    가능 (agent loop turn 당 최대 8192 output token).
  - **Audit redact 정합**: AWS credential 필드가 우연 ChangeJson 에 포함될 때
    `<redacted>` 마스킹. masked_fields list 에도 명시.
  - **정책 doc 정확성**: SECURITY.md §6.1 의 isolation 주장이 실 구성과 일치
    하지 않던 false-claim 정정. 운영자 / audit 신뢰도 회복.
- Rollback Notes:
  - 각 change 가 독립 — 부분 revert 가능. max_tokens cap revert 시 비용 worst-
    case 노출. masked field revert 시 doc-code drift 재발.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/model_catalog.py`
    PASS.
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - codex 의 6 blindspot 중 5 가 직접 보강, 1 (reasoning content) 은 baseline
    code 가 이미 처리 — 별 코드 변경 X.

## CHG-20260522-0005
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (env_file scoping refactor — codex
  blindspot #1 + SUBAGENT NT #1 의 최종 해결)
- Summary: feature-0007 의 follow-up cycle. codex blindspot #1 (docker-compose
  의 env_file inheritance 가 AWS_* / 다른 secret 을 모든 컨테이너에 노출) 의
  최종 refactor. secret 영역별 5 `.env.*` 파일 분리 + docker-compose service 별
  env_file list 가 자기에게 필요한 secret 만 inherit (least privilege).
- Files:
  - 신규: `.env.bedrock.example` (committed, placeholder) — `AWS_ACCESS_KEY_ID`,
    `AWS_SECRET_ACCESS_KEY` (bedrock-gateway 전용).
  - 신규: `.env.mysql.example` — `MYSQL_ROOT_PASSWORD`, `DB_PASSWORD`,
    `REPLICA_DB_PASSWORD`.
  - 신규: `.env.postgres.example` — `AGENT_KB_PG_PASSWORD`, role 별 password.
  - 신규: `.env.minio.example` — `MINIO_ROOT_PASSWORD`, `MINIO_APP_ACCESS_KEY`,
    `MINIO_APP_SECRET_KEY`.
  - 신규: `.env.llm.example` — `LOCAL_LLM_API_KEY`, `BEDROCK_GATEWAY_API_KEY`.
  - 수정: `.gitignore` — `.env.bedrock` / `.env.mysql` / `.env.postgres` /
    `.env.minio` / `.env.llm` 5 패턴 추가.
  - 수정: `.env.example` — 헤더에 secret 영역별 분리 정책 + 운영자 마이그레이션
    가이드. 본 파일에서 14 secret 행 (MYSQL_ROOT_PASSWORD / DB_PASSWORD /
    REPLICA_DB_PASSWORD / AGENT_KB_PG_PASSWORD / AGENT_KB_PG_RW_PASSWORD /
    AGENT_KB_PG_RO_PASSWORD / MINIO_ROOT_PASSWORD / MINIO_APP_ACCESS_KEY /
    MINIO_APP_SECRET_KEY / OPENAI_API_KEY / LOCAL_LLM_API_KEY / BEDROCK_GATEWAY_API_KEY
    / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) 제거. 본 파일 = 비-secret + URL
    + tuning + port.
  - 수정: `docker-compose.yml` — 6 service 의 `env_file` 갱신:
    - `x-agent-common` (agent / web / insight-worker / memory-init): `[.env,
      .env.mysql, .env.postgres, .env.minio, .env.llm]`
    - `mysql`: `[.env, .env.mysql]`
    - `postgres`: `[.env, .env.postgres]`
    - `minio` + `minio-init`: `[.env, .env.minio]`
    - `mcp`: `[.env, .env.mysql]` (DBHUB_DSN 의 DB_PASSWORD 치환).
    - `bedrock-gateway`: `[.env, .env.bedrock, .env.llm]`
    - `caddy` / `browser`: `[.env]` 그대로.
- Impact:
  - **least privilege 강제**: bedrock-gateway 만 AWS_* 노출. 다른 11 service 의
    process env 에 AWS_* 부재. SECURITY.md §6.1 의 정책과 실 구성 완전 일치.
  - **secret rotation 분리**: 각 영역별 (AWS / MySQL / Postgres / MinIO / LLM)
    rotation cycle 독립. 한 영역 rotation 이 다른 영역 영향 없음.
  - **운영 부담 1 회 ↑**: 운영자가 기존 .env 의 secret 행을 5 새 파일로 옮기는
    1 회 마이그레이션 필요. .env.example 헤더에 가이드.
- Rollback Notes:
  - 단일 .env 로 회귀 시 docker-compose service 의 `env_file` list 를 `[.env]`
    로 되돌리고 .env 에 secret 행 복원. 본 cycle 의 git revert 가능.
- Verification:
  - YAML schema: docker-compose 의 12 service 모두 정상. agent / bedrock-gateway
    / mysql / minio env_file list 확인.
  - `python3 -m py_compile config.py` PASS.

## CHG-20260522-0006
- Date: 2026-05-22
- Related Requirement: REQ-20260521-0001~3 (OpenAI API Key 폐기, 사용자 결정
  2026-05-22)
- Summary: 사용자 결정 (2026-05-22) — OpenAI API Key 미사용. `_select_llm_provider()`
  의 OpenAI direct fallback 분기 제거. LLM 호출 entry 는 Bedrock gateway 또는
  Local LLM gateway 만.
- Files:
  - 수정: `unit/feature-0002-agent-core/src/modules/config.py` —
    `_select_llm_provider()` 의 분기 3 (OpenAI direct: `OPENAI_API_KEY` 만 설정
    시 fallback) 제거. docstring 갱신.
  - 수정: `.env.llm.example` — `OPENAI_API_KEY=` 행 제거 + 안내 명시 (OpenAI
    미사용).
  - 수정: `.env.example` — LLM provider 우선순위 안내 3 → 2 옵션.
- Impact:
  - **OpenAI 미사용**: backend 가 OpenAI cloud direct 호출 안 함. Bedrock
    gateway / Local LLM gateway 만 사용.
  - **backward-compat**: 운영 .env 의 잔존 `OPENAI_API_KEY` 값은 silent ignore.
    config.py 의 import 는 유지하여 코드 NameError 회피.
  - **운영 안내**: 운영자가 `OPENAI_API_KEY` env 를 명시 정리 권장.
- Rollback Notes:
  - `_select_llm_provider()` 의 분기 3 복원으로 회귀 가능. 단 사용자 결정 위반.
- Verification:
  - `python3 -m py_compile config.py` PASS.

## CHG-20260623-0001
- Date: 2026-06-23
- Related Requirement: REQ-20260521-0001 (LLM 호출 gateway 일원화) 후속 — KB
  임베딩 가용성 복구 (TASK-0135 #13 의 운영 연속성).
- Summary: `titan-embed` 임베딩 alias 를 Bedrock(`bedrock/amazon.titan-embed-text-v2:0`)
  에서 **로컬 Ollama bge-m3 (1024-dim)** 로 전환. "전환"으로 chat 은 Anthropic-direct
  (claude-corp OAuth)로 이동했으나 Anthropic API 는 임베딩 미제공 → titan-embed 만
  Bedrock 에 잔존, AWS 키 제거 후 401(credential 부재)로 실패. Bedrock 의존 없이
  로컬 Ollama bge-m3 로 대체해 KB 벡터 임베딩 경로를 복구. 차원은 1024 로 동일 →
  texts/sample_queries 의 vector(1024) 스키마 및 기존 백필과 호환 (재임베딩 불필요
  여부는 모델 변경에 따른 임베딩 공간 차이로 운영 판단 — 본 변경은 인프라 경로 복구
  범위, 재백필 정책은 메인 세션 결정).
- Files:
  - 수정: `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`
    — `titan-embed` model_list 항목을 `model: ollama/bge-m3` +
    `api_base: http://ollama-edge:11434` 로 교체. 기존 Bedrock 2줄
    (`bedrock/amazon.titan-embed-text-v2:0` / `aws_region_name: ap-northeast-2`)
    은 "배포 복구용" 주석으로 보존 (AWS_* 자격 확보 후 토글 복구, 차원 동일 1024).
    claude-sonnet-4 / claude-haiku-4 항목은 무변경.
  - 수정: `docker-compose.yml` — `bedrock-gateway` 서비스 `networks: [dbnet]` →
    `networks: [dbnet, llm-shared]`. litellm 이 `api_base` 의 `ollama-edge:11434`
    (llm-shared 내 local-llm-edge 컨테이너 alias) 로 임베딩을 직접 호출하려면
    bedrock-gateway 가 llm-shared 에 attach 돼야 함. dbnet(앱·DB 인증 트래픽)은 유지.
  - 인프라 (코드 외, 영속): `local-llm-edge` Ollama 에 `ollama pull bge-m3`
    (1.2GB, F16, embedding length 1024) — git 미추적, 컨테이너 볼륨 상주.
- Impact:
  - 운영: AWS Bedrock 자격 없이 KB 임베딩 동작. bge-m3 는 BAAI 다국어 임베딩으로
    한국어 입력 정상 (실측 dim=1024). chat(Anthropic-direct)과 임베딩(로컬 Ollama)
    이 서로 다른 provider 로 분리됨.
  - 네트워크: bedrock-gateway 가 llm-shared 에도 합류 (앱 컨테이너 web/ask/insight
    와 동일 패턴). Bedrock 복구 시에도 llm-shared 잔류는 무해 (Bedrock 라우팅은
    외부 AWS endpoint).
  - 호환: 임베딩 차원 1024 불변 → 스키마(vector(1024)) 호환. 단 모델이 다르면
    임베딩 벡터 공간이 달라 기존 백필 벡터와 신규 쿼리 벡터의 cosine 정합성은
    저하 가능 — 일관성 위해 재백필(kb_embedding_worker)이 권장될 수 있음(메인 세션
    운영 판단).
- Rollback Notes:
  - litellm_config.yaml 의 titan-embed 항목을 주석 보존된 Bedrock 2줄로 복원 +
    docker-compose.yml networks 를 `[dbnet]` 으로 환원 + AWS_* 자격 재주입으로
    원복. 차원 동일(1024)이라 스키마 변경 불필요.
- Verification:
  - `ollama show bge-m3`: embedding length 1024 (F16).
  - Ollama 직접 `/api/embeddings` (영어/한국어) dim=1024, OpenAI-compat
    `/v1/embeddings` dim=1024 (2026-06-23 host probe).
  - reachability: `repo-bedrock-gateway-1` 을 llm-shared 에 임시 connect 후
    `http://ollama-edge:11434/api/tags` 에 bge-m3 노출 + embeddings dim=1024 확인
    → 검증 후 disconnect 원복 (compose 미적용 상태로 런타임 복원).
  - end-to-end: 신규 config 로 일회성 litellm 컨테이너(llm-shared) 기동 →
    `/v1/embeddings {"model":"titan-embed"}` 영어/한국어 모두 dim=1024,
    응답 model=titan-embed (2026-06-23). 검증 후 컨테이너 제거.
  - `docker compose config` (env symlink 보강) PASS — bedrock-gateway networks =
    [dbnet, llm-shared] 파싱 확인.

## CHG-20260703-insight-llm-fallback
- Date: 2026-07-03
- Related: TASK-0308(insight 부하 분산) 후속 — insight LLM burst 429 대응.
- Summary: insight-worker LLM(`claude-haiku-4`)의 claude-corp **burst rate-limit(429)** 대응
  **litellm 요청-레벨 fallback 체인**. **(1) `litellm_config.yaml`**: `claude-haiku-4`(claude-corp) →
  `claude-haiku-4-root`(root Max) → `edge-fallback`(로컬 gemma `openai/gemma4:e2b` via local-llm-gateway)
  3-deployment + `litellm_settings.fallbacks: [{"claude-haiku-4":["claude-haiku-4-root","edge-fallback"]}]`
  + `num_retries:1`. deployment 별 `api_key` 명시(ANTHROPIC_API_KEY / ANTHROPIC_API_KEY_ROOT), edge 는
  `local-no-key` 리터럴(로컬 게이트웨이·비밀 아님). **(2) `bin/refresh-claude-oauth-token.sh`**: 단일-slot
  택일 폴백 → **병행 주입**(ANTHROPIC_API_KEY ← 우선순위($ACCOUNTS) 첫 사용가능, ANTHROPIC_API_KEY_ROOT ←
  root 전용). 각 slot 독립 검사(static+라이브 probe), 사용가능 시만 갱신, 둘 다 불가면 exit 1. header 주석
  병행 주입 반영.
- 근거: insight `AGENT_INSIGHT_MODEL=claude-haiku-4` 전환 시 schema/table 생성 burst 가 claude-corp
  RPM/TPM 초과 → 429(200 성공 0, 라이브 관측). 계정 자체 유효(probe 200) but burst 차단. 기존
  refresh 계정-폴백은 계정 **완전소진(probe 429)** 시만 작동 → 요청-레벨 fallback 필요.
- Verification: `litellm_config` YAML OK(5 deployment, fallbacks 정확), refresh `bash -n` OK, `--check`
  병행주입 진단(claude-corp 200 / root 200, root slot 신규 주입 예정) PASS. 적대 backend+infra 패널
  (REV-20260703T101500-insight-llm-fallback). fallback 동작은 배포 후 라이브 검증.
- Deploy(외부영향 — 사용자 confirm): refresh 실행(root slot 주입) + bedrock-gateway 재생성(litellm_config 반영).
- Rollback: litellm_config 의 root/edge deployment·fallbacks 제거 + refresh 단일-slot 복원 + (또는)
  `AGENT_INSIGHT_MODEL=edge`.
- ANCHOR 정합: §1(운영자 자격 일원화 — 사용자별 키 아님, 운영자 두 계정 + 로컬)·§2(Alt-A LiteLLM gateway) 무충돌.

## CHG-20260707T100640-no-edge-conversation-answer (litellm_config: 대화 답변 전용 edge-free alias 신설 — cross-feature, primary=feature-0002-agent-core)
- Date: 2026-07-07. `/_dqa:conversation_audit`(FR-edge-fallback-conversation-context-loss). 사용자 대면 대화 답변(task='agent')이 두 claude 계정 429 시 `edge-fallback`(gemma4:e2b, ctx 4096)으로 silent 강등돼 히스토리 절단·맥락 파괴(실측 conv …9e0883bb). 사용자 결정(2026-07-07): 대화 답변에 gemma 완전 차단·명백한 실패처리.
- 변경(litellm_config.yaml): deployment `claude-haiku-4-chat`(claude-corp)·`claude-haiku-4-chat-root`(root) 신설 + fallback `{"claude-haiku-4-chat": ["claude-haiku-4-chat-root"]}`(**edge 미포함**, chat-root fallback 미등록 → 429/401 raise). 기존 `claude-haiku-4`(insight 배치)·`claude-haiku-4-interactive`(분석)·`edge-fallback` 체인 **무변경** — insight/분석의 gemma 강등 유지(2026-07-03/07-04 결정 보존). 대화(_call_llm)만 agent_core 가 `claude-haiku-4-chat` 로 라우팅.
- Verification: YAML lint OK(9 deployment·5 fallback). 배포=bedrock-gateway 재생성(config bind-mount 반영, 외부영향 confirm — Major override 불가).
- ANCHOR 정합: §1(운영자 자격 일원화 — chat alias 도 동일 두 계정 OAuth, 신규 자격 없음)·§2(Alt-A LiteLLM gateway) 무충돌. 폴백 경로 **축소**(edge 제거)라 보안·자격 경계 확장 없음.
- Cross-ref(정본): unit/feature-0002-agent-core/docs/MODIFY.md CHG-20260707T100640-no-edge-conversation-answer · shared/docs/MODIFY.md 동일 · feature-0002 REVIEW.md REV-20260707T100640-no-edge-conversation-answer.

## CHG-20260724T105132-sonnet-chat-fallback (litellm_config + model_catalog: sonnet 대화 2계정 fallback parity — cross-feature, primary=shared+feature-0002)
- Date: 2026-07-24. 사용자 보고: 새 대화에서 **sonnet 모델** 선택 시 "서비스 자체의 요청량 한도에 도달했습니다"로 실패(대화 상태 error). 기본값(haiku)은 정상. 사용자 계정 잔여 quota 90%(=계정 단위 `_check_account_token_quota`) — 이 메시지는 **provider throttle(429)** 이라 주체가 다름.
- 근본 원인(비대칭): 대화 답변 경로 `agent_core._call_llm` 의 `conversation_answer_model()` 이 haiku 는 `claude-haiku-4-chat`(→ `-chat-root` 2계정 체인)로 치환하지만, sonnet 은 `_CONVERSATION_ANSWER_ALIAS` 미매핑이라 **identity(`claude-sonnet-4`)** 로 통과. litellm 의 bare `claude-sonnet-4` 는 **단일 계정(claude-corp, api_key 미명시=기본 ANTHROPIC_API_KEY)이고 fallbacks 미등록**. claude-corp OAuth 가 5h rolling rate-limit(429)에 걸리면 haiku 는 root 로 우회 생존, **sonnet 은 fallback 없어 즉시 429 raise** → `classify_llm_provider_error`(status==429) → `KIND_THROTTLED` → 그 메시지. (기존 model_catalog 주석이 "sonnet 은 edge 폴백 없음"만 보고 root 계정 fallback 부재를 간과.)
- 변경 ①(shared/model_catalog.py): `_CONVERSATION_ANSWER_ALIAS` 에 `"claude-sonnet-4": "claude-sonnet-4-chat"` 추가 + 주석/docstring 갱신. 예산/usage/max_tokens 는 원본 `claude-sonnet-4` 로 키잉(무회귀, haiku 패턴 동형).
- 변경 ②(litellm_config.yaml): deployment `claude-sonnet-4-chat`(claude-corp, `api_key=ANTHROPIC_API_KEY`)·`claude-sonnet-4-chat-root`(root, `ANTHROPIC_API_KEY_ROOT`) 신설, 둘 다 `budget_tokens: 16000`(bare `claude-sonnet-4` 와 동일 — max_tokens 관계 불변). fallback `{"claude-sonnet-4-chat": ["claude-sonnet-4-chat-root"]}`(**edge 미포함**, chat-root fallback 미등록 → 두 계정 실패 시 429/401 raise, 2026-07-07 gemma 배제 정책 정합). bare `claude-sonnet-4` 는 probe(`llm_provider_health`)·`OPENAI_MODEL` 기본값·node_analysis 등 비대화 경로 전용으로 **무변경(격리)**.
- 변경 ③(feature-0002 tests/test_conversation_answer_no_edge_alias.py): G2 를 sonnet→sonnet-chat 매핑으로 갱신, `test_call_llm_routes_sonnet_to_edge_free_chat_alias` 로 개명, G5b `test_sonnet_conversation_chain_has_two_accounts_and_is_edge_free` 신설(라우팅 가능·2계정·edge-free 고정).
- Verification: YAML lint OK(11 deployment·6 fallback). feature-0002+0003 전체 pytest PASS(rc=0, agent 이미지 격리 컨테이너). 배포=bedrock-gateway 재생성(config bind-mount 반영, 외부영향 confirm).
- Rollback: model_catalog `_CONVERSATION_ANSWER_ALIAS` 의 sonnet 라인 제거 + litellm_config 의 sonnet-chat 2 deployment·fallback 제거 → sonnet identity 복원.
- ANCHOR 정합: §1(운영자 자격 일원화 — chat alias 도 동일 두 계정 OAuth, 신규 자격 없음)·§2(Alt-A LiteLLM gateway) 무충돌. 폴백은 haiku-chat 과 동형 축소 체인(edge 없음)이라 보안·자격 경계 확장 없음.
- Cross-ref(정본 코드): shared/model_catalog.py `_CONVERSATION_ANSWER_ALIAS` · agent_core.py `_call_llm` 라우팅 · REVIEW.md REV-20260724T105132-sonnet-chat-fallback.

## CHG-20260724T113513-sonnet5-upgrade (sonnet → Sonnet 5 라우팅 + adaptive thinking 마이그 + 버전-무관 사용자 라벨 — cross-feature, primary=feature-0007+shared+feature-0002+feature-0003)
- Date: 2026-07-24. 후속 진단(사용자 확인): sonnet-chat-fallback 배포 후 라이브 검증에서 sonnet 두 계정(claude-corp/root) 모두 429(rate_limit) — 그러나 사용자는 sonnet 미사용·quota 여유. haiku-4-5 는 양 계정 200 정상. **실 원인: sonnet alias 가 폐기된 `anthropic/claude-sonnet-4-6` 으로 라우팅**(현행은 Sonnet 5). 폐기 모델이 429 를 반환해 sonnet 대화(+node_analysis/probe 도 bare claude-sonnet-4 사용)가 실패한 것. sonnet-chat-fallback 의 2계정 체인은 정상 작동했으나 두 계정 모두 같은 폐기 모델이라 무의미했다.
- 변경 ①(litellm_config.yaml): sonnet alias 3개(`claude-sonnet-4`, `claude-sonnet-4-chat`, `claude-sonnet-4-chat-root`)의 `model` 을 `anthropic/claude-sonnet-4-6` → **`anthropic/claude-sonnet-5`** + `thinking` 을 `{type:enabled, budget_tokens:16000}` → **`{type:adaptive}`**. **Anthropic 스펙(claude-api skill 확인): Sonnet 5 는 thinking budget_tokens 를 400 으로 거부** — adaptive thinking + output_config.effort(기본 high)만 지원. Haiku 4.5(pre-Sonnet-5)는 budget_tokens 유지. api_key·fallback 체인 무변경. **내부 alias 이름은 claude-sonnet-4 유지**(하위호환 — 저장 대화·node_analysis·probe·단가·runtime_settings 키 무변경).
- 변경 ①b(thinking-API 마이그 — shared/model_catalog + agent_core + probe): `model_thinking_style(model)`('adaptive' Sonnet5계열/'budget' Haiku등/None) + `effort_for_reasoning_level(level)`(low/high/max→effort, normal/None→미주입) 신설. `agent_core._call_llm` 의 thinking 주입을 style 분기 — budget 계열은 기존 budget_tokens 로직, **adaptive 계열은 budget_tokens 절대 미주입**하고 명시 추론강도만 `extra_body.output_config.effort` 로 전달('일반'=미주입=기본 high, B1 무회귀 동형). `llm_provider_health.probe_provider` 도 동일 분기(adaptive→effort low ping, budget→budget_tokens, else→max_tokens=1). feature-0003 추론강도 선택기는 sonnet 에서 budget→effort 로 전환, haiku 는 기존 budget 유지. 관리 콘솔 budget override(reasoning_budget/model_thinking_budget)는 adaptive sonnet 에서 무시(effort 사용).
- 변경 ②(shared/model_catalog.py): 사용자 지시(2026-07-24 "제공 alias 명칭은 넘버링 없이 모델 그대로")에 따라 API_MODEL_OPTIONS 의 **표시 label 을 버전-무관하게** — sonnet `claude-sonnet-5`(초안)→`claude-sonnet`, haiku `claude-haiku-4`→`claude-haiku`, group→`Claude`, description 버전 제거. **value 는 claude-sonnet-4/claude-haiku-4 유지**(내부 라우팅·저장·단가 키). 또 `canonical_usage_model`(+`_sql` SSOT)에 `claude-sonnet-5*` → `claude-sonnet-4` fold 추가(resolved_model 이 sonnet-5 실 ID 로 와도 단가표 `claude-sonnet-4`($3/$15) 매칭 유지, $0 오표시 방지).
- 변경 ③(feature-0003 app.js): `_composerModelLabelFor(value)` 신설 — 컴포저 현재-모델 표시가 raw value(claude-sonnet-4, 넘버링) 대신 카탈로그 label(claude-sonnet)을 노출. 카탈로그 미로드/미등록 value 는 value fallback(안전). selectedModel 은 여전히 value 로 저장/전송(무회귀).
- 변경 ④(feature-0003 tests): test_usage_conversations 의 canonical 테스트에 sonnet-5 실 ID·-chat 변형 fold 커버리지 추가.
- Verification: YAML OK(sonnet 3 alias→sonnet-5·thinking=adaptive), feature-0002+0003 pytest PASS(rc=0, adaptive/effort·dual-style 테스트 포함), app.js `node --check` OK. **⚠ litellm(main-stable)이 config-level `thinking:{type:adaptive}` 및 요청 `output_config.effort` 를 Anthropic 으로 올바로 통과시키는지는 코드만으론 불확실 — 배포 후 gateway ping(claude-sonnet-4-chat + effort)으로 라이브 확정(실패 시 즉시 rollback)** + PB-0008(새 대화 sonnet 정상 답변). CHECK#13 web/UI 변경 → PB-0008 Windows-browser Run 기록.
- Rollback: litellm sonnet `thinking:{type:adaptive}`·`model:sonnet-5` 되돌림 + model_catalog style 헬퍼/agent_core 분기/probe/label/canonical/JS revert. (단 sonnet-4-6 은 폐기라 429 재발 → rollback 은 sonnet 미작동 상태로 복귀.)
- ANCHOR 정합: §1(운영자 자격 일원화 — 동일 두 OAuth 계정, 신규 자격 없음)·§2(Alt-A LiteLLM gateway) 무충돌. 모델 버전 갱신은 자격/보안 경계 변경 없음.
- Cross-ref(정본 코드): litellm_config.yaml(sonnet adaptive) · shared/model_catalog.py `model_thinking_style`/`effort_for_reasoning_level`/`canonical_usage_model`/`API_MODEL_OPTIONS` · agent_core.py `_call_llm` style 분기 · llm_provider_health.py `probe_provider` · feature-0003 app.js `_composerModelLabelFor` · REVIEW.md REV-20260724T113513-sonnet5-upgrade.

## CHG-20260724T123503-cc-identity-inject (Sonnet 5 OAuth frontier-identity 게이트 해소 — cross-feature, primary=shared+feature-0002)
- Date: 2026-07-24. sonnet5-upgrade 배포 후 라이브 검증서 sonnet 여전히 429. **사용자 요청으로 계정 용량 직접 확인** → 직접 api.anthropic.com 호출로 근본 원인 확정:
  - 두 OAuth 계정(claude-corp/root) 모두 **claude-sonnet-5 직접 호출 200**(unified-status: allowed) — **계정 용량 충분**(사용자 지적 정확). 429는 계정 한도 아님.
  - **결정적 격리 실증**: sonnet-5 는 sk-ant-oat OAuth 구독 토큰에서 **system 의 첫 블록이 정확히 "You are Claude Code, Anthropic's official CLI for Claude." 여야** 200. system 없음/generic → 429. `CC+"\n\n"+제품`(단일 문자열) → 429. **블록/메시지 분리 `[CC, 제품]` → 200**. Haiku 4.5 는 미요구(그래서 정상). litellm gateway 가 이 identity 블록을 안 보내서 sonnet 만 429였다.
  - 동작 검증: CC-first-block + 제품(DB assistant) system → 답변이 완전한 DB 어시스턴트(SQL·쿼리·분석), Claude Code 코딩 아님 — 제품 프롬프트가 실 동작 지배.
- 변경(shared/model_catalog.py): `OAUTH_FRONTIER_IDENTITY`("You are Claude Code…") 상수 + `requires_oauth_frontier_identity(model)`(adaptive 계열=Sonnet 5만 True) 신설.
- 변경(agent_core `_call_llm`): adaptive 모델이면 `effective_messages` 첫 블록으로 `{role:system, content:CC}` 주입(제품 system 앞). litellm 이 Anthropic system 첫 블록으로 매핑(라이브 검증). haiku 미주입(working 무영향).
- 변경(llm_provider_health `probe_provider`): adaptive 모델 probe 도 CC system 첫 주입(없으면 probe 429 → 배너 자동복구 무력화 방지).
- 사용자 결정(2026-07-24): "Claude Code identity 주입 구현" — OAuth 구독 토큰에 Claude Code identity 를 실어 frontier(Sonnet 5) 사용(ToS 경계 인지·수용).
- Verification: feature-0002+0003 pytest PASS(rc=0, requires_oauth_frontier_identity·CC 주입·probe CC·haiku 미주입 테스트), py 구문 OK. gateway 라이브 매핑 실증(2 system msgs / system blocks → 200, 단일 문자열 → 429). **배포 후 gateway ping(claude-sonnet-4-chat 실 대화) 200 + PB-0008 최종 확정.**
- Rollback: model_catalog 상수/헬퍼 + agent_core/probe 주입 revert → sonnet 429 복귀(단 코드-정확 상태로).
- ANCHOR 정합: §1(운영자 자격 일원화 — 동일 OAuth 계정, 신규 자격 없음)·§2(Alt-A gateway) 무충돌. system 첫 블록 identity 주입은 라우팅/인증 경계 확장 아님(기존 OAuth 토큰 사용).
- Cross-ref(정본 코드): shared/model_catalog.py `OAUTH_FRONTIER_IDENTITY`/`requires_oauth_frontier_identity` · agent_core.py `_call_llm` · llm_provider_health.py `probe_provider` · REVIEW.md REV-20260724T123503-cc-identity-inject.

## CHG-20260724T141420-llm-timeout-align (litellm request_timeout 120→300 — Sonnet 5 대화 "Request timed out" 해소)
- Date: 2026-07-24. cc-identity-inject 로 sonnet 이 작동(tool use 여러 단계)하기 시작한 뒤, 후반 라운드에서 "LLM 호출 오류: Request timed out" 발견(사용자 신고, 상태 error). 진단: 배포 **AGENT_TIMEOUT_SEC=300**(앱 client timeout, `_get_llm_client`)인데 gateway **litellm request_timeout=120** — gateway 가 앱보다 먼저 120s 에서 Anthropic 응답을 컷. Sonnet 5 adaptive thinking 대화의 장문-답변 후반 라운드(전체 컨텍스트+심층 추론+긴 산출)가 120s 초과 → timeout. num_retries=1·fallback 겹치면 120s×N 이 앱 300s 를 넘겨 조기 실패도 유발. 개별 호출 latency 실측은 19s(high)/14s(medium)로 대체로 빠르나, 장문 답변 라운드가 예외적으로 김.
- 변경(litellm_config.yaml): `litellm_settings.request_timeout` 120 → **300**(앱 AGENT_TIMEOUT_SEC 와 정합 — config 주석의 "짧게 잡지 않는다" 의도 복원). 총 run 예산은 앱측 AGENT_TIMEOUT_SEC*3=900s 가 라운드 합계로 별도 강제(무변경). effort/max_tokens 무변경(개별 호출은 빠름 — 근본은 gateway<app 타임아웃 불일치).
- Verification: YAML OK(request_timeout=300). 배포=bedrock-gateway reconcile(config bind-mount). 배포 후 실행 config request_timeout=300 확인 + sonnet 대화 정상.
- Rollback: request_timeout 120 복원(단 장문 sonnet 대화 timeout 재발).
- ANCHOR 정합: §1·§2 무충돌. 타임아웃 상향은 자격/보안/라우팅 경계 변경 아님.
- Cross-ref(정본): litellm_config.yaml `litellm_settings.request_timeout` · shared/config.py AGENT_TIMEOUT_SEC(300) · REVIEW.md REV-20260724T141420-llm-timeout-align.

## CHG-20260724T054326-timeout-console-sync (litellm request_timeout ↔ 관리 콘솔 AGENT_TIMEOUT_SEC(live) 요청 단위 동기화 — 주석만 변경, 정본 로직=feature-0002)
- Date: 2026-07-24. 사용자 요청: "`request_timeout` 또한 `설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃` 설정값과 동기화되도록 구성". 선행 llm-timeout-align(CHG-20260724T141420) 이 request_timeout 을 정적 300 으로 올렸으나, gateway 는 앱과 별도 프로세스라 콘솔 live 변경을 추종 못 하는 drift 잔존.
- 진단(라이브 결정 실험): litellm 은 요청 body 의 `timeout` 을 per-attempt upstream 타임아웃으로 존중(body=5→408·=200→200 @11.7s) → 앱이 요청마다 live 값을 body 로 전달하면 gateway 재기동·재배포 없이 즉시 동기화(정적 config 로는 불가능).
- 변경(litellm_config.yaml): `litellm_settings.request_timeout: 300` **값 무변경**. 주석만 갱신 — 앱(`agent_core._call_llm`)이 요청마다 live body timeout 을 전달하며, config request_timeout 은 body timeout 미전달 경로(외부 소비자 등)의 정적 fallback ceiling 임을 명문화. 앱 대화·probe 경로는 body timeout(live)이 override.
- 정본(코드·로직·테스트): **feature-0002** `src/agent_core.py _call_llm`(extra_body 항상 timeout + thinking/effort 병합)·ask() client·run 예산 live 전환 + tests. feature-0002 CHG/REV/TASK-20260724T054326-timeout-console-sync.
- Verification: YAML 파싱 OK(request_timeout=300 무변경). 배포=bedrock-gateway reconcile(config bind-mount, 주석변경이라 동작 무영향) + feature-0002 worker/web 재빌드. 배포 후 라이브: 콘솔 AGENT_TIMEOUT_SEC 변경 → 요청 실제 타임아웃 추종 확인.
- Rollback: 주석 원복(기능 영향 0). 로직 rollback 은 feature-0002 CHG 참조.
- ANCHOR 정합: §1·§2 무충돌(자격/보안/라우팅 경계 변경 아님).
- Cross-ref(정본): feature-0002 MODIFY/REVIEW/TASK-20260724T054326-timeout-console-sync · litellm_config.yaml `litellm_settings.request_timeout` 주석 · 선행 CHG-20260724T141420-llm-timeout-align · REVIEW.md REV-20260724T054326-timeout-console-sync.

## CHG-20260727T184425-opus5-model (assistant 선택 모델에 Claude Opus 5 추가 — claude-corp + root 2계정 edge-free 체인)
- Date: 2026-07-27. 사용자 요청: "서비스 내 assistant 의 llm 모델에 claude opus 도 포함 … 이전의 sonnet 을 추가했던 사례를 검토하여 꼼꼼하게 (`claude-corp` 및 `root` 계정 포함)". sonnet 추가 이력(CHG-20260724T…-sonnet-chat-fallback → -sonnet5-upgrade → -cc-identity-inject → -llm-timeout-align)이 **4차에 걸쳐 사후 수정**된 원인(bare 단일계정 · 폐기 모델 ID · budget_tokens 400 · OAuth identity 게이트)을 전부 도입 시점에 선반영했다.
- **선행 라이브 실증(코드 작성 전, gateway 컨테이너에서 api.anthropic.com 직접 호출)**:
  - claude-corp(`ANTHROPIC_API_KEY`) + `claude-opus-5` + **system 없음 → 429**(`{"type":"rate_limit_error","message":"Error"}`, unified-status 헤더 없음).
  - claude-corp + `claude-opus-5` + **Claude Code identity 첫 system 블록 → 200**(`model=claude-opus-5`, `anthropic-ratelimit-unified-status: allowed`). → **Opus 5 도 Sonnet 5 와 동일한 OAuth frontier-identity 게이트**.
  - root(`ANTHROPIC_API_KEY_ROOT`) → opus/sonnet-5/haiku-4-5 **전부 429**(`unified-status: rejected`, "would exceed your account's rate limit", reset epoch 1785159600) = **계정 전체 한도 소진**이지 Opus 모델 게이팅 아님(모델별 격리 probe 로 확인). 윈도우 리셋 후 2순위 체인 정상 동작 예상 — 배포 후 재확인 대상.
- 변경(`unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`): opus 3 deployment 신규 —
  `claude-opus-5`(bare, `ANTHROPIC_API_KEY`, fallback 미등록=비대화 격리) / `claude-opus-5-chat`(`ANTHROPIC_API_KEY`) / `claude-opus-5-chat-root`(`ANTHROPIC_API_KEY_ROOT`). 전부 `model: anthropic/claude-opus-5` + `thinking:{type:adaptive}`. `litellm_settings.fallbacks` 에 `{"claude-opus-5-chat": ["claude-opus-5-chat-root"]}` 추가(edge 미포함 종단).
- 변경(`shared/model_catalog.py`): ① `API_MODEL_OPTIONS` 선두에 `claude-opus-5`(label `claude-opus`, group `Claude`, supports_temperature=False, supports_vision=True) ② `_CONVERSATION_ANSWER_ALIAS["claude-opus-5"]="claude-opus-5-chat"` ③ `_ADAPTIVE_THINKING_PREFIXES` 에 `claude-opus` prefix(전 Opus 버전 adaptive-only — budget_tokens 400 방지; `requires_oauth_frontier_identity` 도 동일 집합이라 CC identity 자동 주입) ④ `_CLAUDE_MODEL_MAX_OUTPUT["claude-opus-5"]=128000` ⑤ `canonical_usage_model`/`_sql` 에 **버전-정확** `claude-opus-5*` fold(미등록 Opus 는 self-surface 유지).
- 변경(`shared/runtime_settings.py`): `_AGENT_MAX_OUTPUT_DEFAULT["claude-opus-5"]=40000`(sonnet 동형; 상한은 native 128000). budget 계열 스펙은 `_budget_thinking_models()` 가 adaptive 를 제외하므로 자동 미생성 → admin UI 는 guide-note(죽은 슬라이더 0).
- 변경(`unit/feature-0003-agent-web-ui/src/routers/admin_usage.py`): `_LLM_PRICE_USD_PER_1M["claude-opus-5"]={"in":5.0,"out":25.0}`(공시가). canonical family 키와 동일해 `-chat`/`-chat-root`/실ID 도 같은 단가로 계상.
- 변경(`.env.example`): 선택 가능 catalog 3종 명시 + `API_DEFAULT_MODEL` stale 표기(`claude-sonnet-4`) → 실제값 `claude-haiku-4` 정정 + 전역 기본 상향 시 비용 파급 경고 + 백그라운드 `AGENT_*_MODEL` 계열에 Opus 배선 금지 주석.
- **코드 변경 불필요(카탈로그 자동 파급) — 검증만**: 모델 선택기(`/api/session` → `PUBLIC_API_MODEL_OPTIONS`, index.html 은 빈 컨테이너) · 컴포저 라벨(`_composerModelLabelFor`) · 추론강도 활성 판정(`model_supports_thinking`) · red-team 리뷰어 정합(`redteam.resolve_review_model` → `conversation_answer_model`) · 재답변 모델 승계 · 대화별 모델 보존 · admin runtime-settings pane(`adaptive_models`).
- Verification: feature-0002+0003 **전체 pytest PASS(rc=0, 2452 tests, 0 fail/0 error)** — 신규 opus 테스트 8건 포함. litellm YAML 파싱 OK(model_name 중복 0 · fallback dangling ref 0). 라이브 사전 실증(위). **배포 후 e2e(대화에서 claude-opus 선택 → 200 답변) + PB-0008 최종 확정 필요.**
- Rollback: 본 CHG 의 5 파일 revert → opus 선택지 소멸(기존 haiku/sonnet 경로 무영향 — 전부 additive).
- ANCHOR 정합: §1(운영자 자격 일원화 — 신규 자격 0, 기존 두 OAuth slot 재사용)·§2(Alt-A gateway 경유) 무충돌. 신규 모델 alias 추가는 라우팅 표면 확장이나 인증/인가 경계 변경 아님.
- Cross-ref: REVIEW.md REV-20260727T184425-opus5-model · TEST.md Run 2026-07-27-opus5-model · shared/docs/MODIFY.md 동일 CHG.

## CHG-20260727T190500-opus5-model-postdeploy (opus5-model POST-DEPLOY 확정 + 관리 콘솔 카피 정정)
- Date: 2026-07-27. 선행 CHG-20260727T184425-opus5-model 의 배포 후 라이브 확정 기록 + 그 과정에서 발견한 stale 카피 1건 정정.
- 배포: `bin/deploy-web.sh`(scope=all) → **413703b9**. web-a/web-b 롤링(one-at-a-time) + soak 90s 통과 · 워커(insight/ask) `mysql-ai-agent:413703b9` 롤아웃 · **bedrock-gateway 드리프트 감지 → surge replica 무중단 교체**(litellm config 변경 반영).
- 라이브 확정(상세 TEST Run 2026-07-27-opus5-model-POSTDEPLOY): gateway 경유 `claude-opus-5-chat` **200** · PB-0008 실 브라우저 모델 선택기 노출 + 실 클릭 → 대화 e2e **7초 정답** · `llm_usage` 가 `model=claude-opus-5` / `resolved_model=claude-opus-5-chat` 로 기록(설계 계약 일치) · red-team 리뷰어도 opus 로 자동 정합(코드 변경 0) · 비용 USD 0.1981 계상($0 오표시 아님) · 관리 콘솔 opus 카드 + adaptive guide-note(죽은 슬라이더 0).
- 변경(`unit/feature-0003-agent-web-ui/src/static/admin.html`): '모델별 추론 예산' pane 헤더 힌트 `max_tokens, Sonnet 128K / Haiku 64K 까지` → `max_tokens, Opus·Sonnet 128K / Haiku 64K 까지`. 카탈로그에 Opus 가 추가되면서 본 문구가 실제 지원 모델을 누락(본 변경으로 stale 해진 문구) — 카피 1줄, 동작 영향 0.
- Verification: PB-0008 evidence 3종(`docs/evidence/pb0008-opus5-{model-menu,live-answer,admin-budget-pane}-20260727.png`). 카피 정정은 재배포 후 육안 재확인.
- 잔여(R1): root 계정 한도 윈도우 리셋 후 `claude-opus-5-chat-root` 실 200 재확인(1순위 claude-corp 경로는 정상 확정).
- Cross-ref: 선행 CHG-20260727T184425-opus5-model · REVIEW REV-20260727T190500-opus5-model-postdeploy · TEST Run 2026-07-27-opus5-model-POSTDEPLOY.

## CHG-20260730T191535-llm-edge-free-routing (자동 gemma(edge) 강등 경로 전면 제거 — 사용자 결정)
- Date: 2026-07-30. 사용자 보고 "18시 기준으로 모든 LLM 요청이 edge 로 호출된다. 더 이상 local llm 은 사용하지 않는 것으로 구성되었지만 해당 이슈가 나타난다" 에서 출발.
- **관측(라이브 근거)**: `bedrock-gateway` 컨테이너가 **18:00:27 재생성** 직후 **18:00:38~18:34:04**(약 34분) 동안 외부 DNS 해석에 실패했다 — `api.anthropic.com` 뿐 아니라 `raw.githubusercontent.com`(기동 시 cost-map fetch)도 `[Errno -3] Temporary failure in name resolution`. 실패 건수는 10분 윈도우당 308건. **계정 문제가 아니다**: 두 OAuth 자격증명의 `expiresAt` 은 유효(root 23:30 / claude-corp 익일 01:58)했고 게이트웨이 주입 토큰도 정상, 429 는 0건이었다. 도달성(reachability) 장애다.
- **결함의 실체**: 그 34분간 `claude-haiku-4-interactive` 체인이 끝의 `edge-fallback` 으로 흘러 **대화 보조 단계 전체가 gemma 로 서빙**됐다. `.env` 의 **11개 변수**(`OPENAI_MODEL` + `AGENT_OBJECT_RESOLVE/SQL_COMPOSE/SQL_REVIEW/PLAN/TASK_CLASSIFY/SQL_FIX/ANSWER/STEP_GRADE/SUMMARY/TOPIC_MODEL`)가 이 alias 를 가리키므로 blast radius 가 파이프라인 전체였다. 대조군: edge 가 없는 `*-chat`(2026-07-07)·`*-meta`(2026-07-30 오전)는 500 으로 정직하게 실패했다 — 같은 장애에서 두 규약의 거동 차이가 그대로 드러났다.
- **사용자 결정(2026-07-30)**: "로컬 LLM 을 더 이상 사용하지 않는다" — 2026-07-04 ADR-002 의 "배경 insight 배치는 야간·주말 gemma 강등(비용 절감)" 까지 포함해 override. 따라서 **앱·게이트웨이 두 층 모두**에서 자동 강등 경로를 제거한다.
- 변경 (5 파일):
  - `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`: `fallbacks` 에서 `claude-haiku-4` → `["claude-haiku-4-root"]`, `claude-haiku-4-interactive` → `["claude-haiku-4-interactive-root"]` 로 축소하고 `claude-haiku-4-root`·`claude-haiku-4-interactive-root` 항목을 제거해 **체인 종단**(`*-chat-root` 와 동일 규약)으로 되돌렸다. `edge-fallback` **deployment 정의는 보존**(참조 0) — 되돌리기 경로를 남기되 라우팅되지 않는다.
  - `shared/config.py`: `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값 `"edge"` → `""`. 빈 값이면 `_effective_insight_model` 이 시각과 무관하게 base 를 반환하므로 시각 기반 강등이 기본 비활성이 된다. **강등 로직 자체는 보존** — 운영자가 값을 채우면 재활성(그 행위가 곧 사용자 결정 override 임을 주석에 명시).
  - `unit/feature-0002-agent-core/src/modules/llm.py`: `_effective_insight_model` docstring 을 "기본 비활성" 사실 + 이력으로 갱신(동작 변경 없음).
  - `.env.example`: 라우팅 정책 블록과 `AGENT_INSIGHT_OFFHOURS_MODEL` 주석을 edge-free 기준으로 재작성.
  - 테스트: `unit/feature-0002-agent-core/tests/test_llm_edge_free_routing.py` **신규 5건**(전 체인 edge 부재 · 2계정 종단 · deployment 정의는 있되 미참조 · 기본 비활성 · 시각 4지점 무관 base). `test_meta_llm_edge_free.py` 의 `test_background_insight_keeps_offhours_edge_downgrade` 는 **방향 반전**해 `..._no_longer_downgrades_to_edge` 로 대체(같은 날 오전 잠금의 사용자 override — 헤더에 superseded 명시). `test_insight_offhours_routing.py` 는 monkeypatch 로 값을 주입하므로 로직 계약 검증은 그대로 유효(헤더에 "기본 비활성" 주석만 추가).
- 운영 반영(코드 밖): 라이브 `.env` 의 `AGENT_INSIGHT_OFFHOURS_MODEL=edge` 를 빈 값으로 바꾸고 워커를 재시작해야 앱 층 강등이 실제로 꺼진다(`.env` 는 gitignored — 배포 단계에서 수행).
- Verification: `make test` PASS(ruff clean) + 대상 3파일 22건 PASS, env override 제거 조건에서 신규·갱신 10건 skip 0 PASS. 라이브 프로브(배포 후): gateway 경유 `claude-haiku-4-interactive` 200 · `served=claude-haiku-4-interactive`.
- **Trade-off (정직 표기)**: edge 안전망을 걷어냈으므로 **두 계정이 모두 도달 불가한 창에서는 해당 기능이 실패한다**(gemma 로 연명하지 않는다). 이는 사용자 결정이자 `*-chat` 규약과 동일한 선택이며, 대신 "조용히 품질이 무너진 답변" 이 사라진다. 그러나 이번 사건의 촉발 조건(게이트웨이 DNS 34분 단절)이 재발하면 그 창은 곧 **전면 중단**이므로, DNS 안정화가 후속 과제로 남는다(REPORT §8).
- Rollback: 본 CHG revert(`fallbacks` 4줄 + config 기본값 1줄) → 종전 강등 거동 복귀. deployment 정의를 남겨 두었으므로 config 한 줄로도 부분 복구 가능.
- ANCHOR 정합: §1(운영자 자격 일원화)·§2(Alt-A gateway 경유) 무충돌 — 라우팅 폴백 정책 변경이며 인증/인가 경계 변경 아님.
- Cross-ref: REVIEW REV-20260730T191535-llm-edge-free-routing · TASK `## TASK-20260730T191535-llm-edge-free-routing` · DECISIONS ADR-003 · TEST Run 2026-07-30-llm-edge-free-routing · shared/docs/MODIFY.md 동일 CHG · 선행 ADR-002(2026-07-04, 부분 superseded) · feature-0002 `test_meta_llm_edge_free.py`(2026-07-30 오전).

## CHG-20260730T200500-llm-edge-free-routing-postdeploy (edge-free 라우팅 배포 후 라이브 확정 기록)
- Date: 2026-07-30. 선행 CHG-20260730T191535-llm-edge-free-routing 의 배포 후 확정. **코드 변경 0 — 문서 전용**(TEST Run 추가 · TASK 체크박스 완료 · LEARNINGS 2건).
- 배포: PR #1097 머지(main **9c4e9935**) → `sudo -E bin/deploy-web.sh`(scope=all). web 롤링 + soak 통과 → 워커 핀 이미지(`mysql-ai-agent:9c4e9935`) 롤아웃 → **bedrock-gateway 드리프트 감지(litellm config `3166d1b9a8a5`≠`be14d75dd402`) → surge replica 무중단 교체**(config 변경이 실제로 반영된 경로).
- 라이브 확정(상세 TEST Run 2026-07-30-llm-edge-free-routing-POSTDEPLOY):
  - 게이트웨이 컨테이너 내부 `/app/config.yaml` 파싱 → fallback 6개 전부 2계정 종단, `edge`/`local` 참조 **NONE**.
  - 프로브 3종(`-interactive`/`claude-haiku-4`/`-chat`) 전부 **200 + served=claude-\***(edge 아님). `max_tokens=5600`(thinking budget 5000 초과)로 호출 — 작게 주면 400 이 나 라우팅 고장으로 오진한다.
  - **경계 밖 시각 실측**: 목 19:59 KST(근무시간 `[10,19)` 밖 = 종전이라면 강등 구간)에 insight-worker 의 `_effective_insight_model()` → `claude-haiku-4`, OFFHOURS env `''`. 단위 테스트의 시각 4지점 검증을 라이브가 확인.
  - 사건 재발 없음: 배포 후 게이트웨이 `name resolution` 실패 0건, 최근 10분 응답 전부 200.
- LEARNINGS: `docs/LEARNINGS.md` LRN-20260730-0001(폴백 안전망이 도달성 장애를 조용한 품질 저하로 번역 — 같은 사건 안의 대조군) · LRN-20260730-0002(env override 시 skip 하는 테스트의 vacuous pass — 실효 설정 검사 + allowlist + 역검증).
- 잔여: REPORT §8 의 후속 3건(게이트웨이 DNS 안정화 **우선** · bare alias 단일계정 · provider-선택 층 로컬 fallback). 전부 별 cycle.
- Cross-ref: 선행 CHG-20260730T191535-llm-edge-free-routing · DECISIONS ADR-003 · REVIEW REV-20260730T200500-postdeploy · TEST Run POSTDEPLOY.

## CHG-20260807T144800-oauth-exhaustion-gate (사용량 소진 계정이 1순위 slot 에 고착되는 결함 수정)
- Date: 2026-08-07. 사용자 보고 "claude-corp 의 모든 토큰이 소진되었지만 root 계정으로 게이트가 옮겨오지 않는다" 에서 출발.
- **관측(라이브 근거)**: claude-corp OAuth 토큰으로 Anthropic `/v1/messages` 직접 호출 → **429**, 헤더가 원인을 확정한다 — `anthropic-ratelimit-unified-7d-status=rejected`, `7d-utilization=1.0`, `7d-reset=1786255200`(2026-08-09 15:00 KST), `retry-after=176528`(≈2.04일), 반면 `5h-status=allowed`/`5h-utilization=0.0`. 즉 burst(5h)가 아니라 **주간(7d) 쿼터 전소**이고, **일 단위로 지속되는 상태**다. 같은 조건에서 root 는 HTTP 200.
- **결함의 실체**: 본 스크립트는 2026-07-07 이후 **정적 검사(파일 존재·만료)만** 한다. 소진은 자격증명 파일에 아무 흔적을 남기지 않으므로 claude-corp 는 계속 "사용 가능" 으로 판정돼 30분마다 `ANTHROPIC_API_KEY`(1순위 slot)에 재주입됐다. 당시 근거였던 "litellm 요청-레벨 fallback 이 흡수한다" 는 **부분적으로만 참**이다:
  - 흡수는 되지만 **매 요청이 소진 계정을 먼저 때린다** — 라이브 응답 헤더 실측 `x-litellm-attempted-fallbacks=1`, `x-litellm-model-group=claude-haiku-4-chat-root`. `num_retries=1` 이라 폴백 전 2회 왕복이 붙고, 대화 한 턴의 보조 단계(plan/classify/sql_*/answer/…) 전부에 곱해진다.
  - **폴백이 없는 alias 는 그대로 죽는다** — bare `claude-sonnet-4`/`claude-opus-5`(의도적 격리). REV-20260730T191535 가 "이월 P1" 로 남겨 둔 그 갭이 이번에 실제로 발현했다.
- **trigger 설계에서 한 번 틀렸다가 실측으로 정정한 것(중요)**: 최초 구현은 게이트웨이 로그의 `RateLimitError` grep 을 probe trigger 로 삼았다. 라이브에서 확인해 보니 **claude-corp 가 429 여도 litellm 이 root 로 성공 폴백하면 게이트웨이 로그에는 `200 OK` 한 줄만 남는다**(폴백 사실은 응답 헤더에만). 즉 "매 요청이 소진 계정을 때리는" 바로 그 상태가 로그상 완전 무증상이라 그 trigger 는 영원히 발화하지 않는다. → 저빈도 **heartbeat** 를 주 신호로 바꾸고 로그 grep 은 보조로 강등했다.
- 변경 (2 파일):
  - `bin/refresh-claude-oauth-token.sh`: 1순위 slot 선택에 **사용량-소진 게이트** 추가.
    - probe 조건: (a) heartbeat — 마지막 라이브 판정 후 `CLAUDE_OAUTH_GATE_RECHECK_SEC`(기본 3600s) 경과 / (b) 소진 캐시 만료(복구 확인 1회) / (c) 게이트웨이 로그 오류 관측(보조) / (d) `CLAUDE_OAUTH_FORCE_PROBE=1`.
    - 판정: 200 → 사용(+캐시 해제) / 429 → `anthropic-ratelimit-unified-reset`(없으면 `retry-after`)을 우회 만료로 캐시하고 **다음 계정 승격** / 401·403 → 짧은 우회 / **그 외·네트워크 오류 → fail-open**(상태 미변경, 정적 결과 유지).
    - 소진 캐시가 유효한 동안은 **probe 0회** → 로그가 깨끗해져도 30분마다 소진 계정으로 되돌아가는 flapping 이 없다.
    - `ANTHROPIC_API_KEY_ROOT`(2순위 slot)는 **게이트 미적용** — "체인 종단 = root" 고정 배선이라 바꿀 여지가 없고, 소진돼도 주입을 멈추면 stale 토큰만 남는다.
    - 후보 전원이 소진이면 게이트를 무시하고 정적 1순위를 유지(주입 중단이 더 나쁘다).
    - 상태 파일 `CLAUDE_OAUTH_STATE_FILE`(기본 `/var/lib/dqa-llm-oauth/exhaustion.json`) — `{until, checked, detail}`. 소실돼도 다음 실행이 heartbeat 로 복구(내구성 요구 없음).
    - 테스트/스테이징 훅(운영 기본값 무변경): `CLAUDE_OAUTH_CRED_ROOT` · `CLAUDE_OAUTH_PROBE_URL` · `CLAUDE_OAUTH_REPO`.
  - `unit/feature-0002-agent-core/tests/test_oauth_exhaustion_gate.py`: **신규 15건**. 하네스가 `CLAUDE_OAUTH_*` 를 전부 고정해 운영자 셸 override 로 인한 vacuous pass 를 차단한다(LRN-20260730-0002 반영).
- **2026-07-07 결정과의 관계**: 그때 probe 를 없앤 이유는 30분 주기 호출이 claude-corp 5h 윈도우를 :00/:30 격자에 재고정해 `session-keepalive-cron.sh`(07:35/12:35 정렬 핑)를 무력화한다는 것이었다. 그 keepalive cron 은 **현재 crontab 에 없고**(2026-08-07 확인) 서비스는 24/7 실 트래픽으로 이미 윈도우를 연다. 그래도 남는 우려에는 `CLAUDE_OAUTH_GATE_RECHECK_SEC=0` 킬스위치를 뒀다. probe 빈도는 30분→최대 1시간, 소진 기간 중에는 0 이다.
- Verification: 대상 15건 PASS · **역검증**(게이트 off 로 실행 시 9건 FAIL — 테스트가 실제로 신 계약을 잠근다) · `bash -n` PASS · ruff `All checks passed!`. 라이브: 1순위 slot 이 root 로 전환됐고 게이트웨이 프로브 3종이 `fallbacks=0` 으로 1순위 직행(상세 TEST Run 2026-08-07-oauth-exhaustion-gate).
- **Trade-off (정직 표기)**: 정상 상태에서 1순위 후보에 대해 **최대 시간당 1회 최소 ping**(max_tokens=16, haiku)이 발생한다 — 2026-07-07 의 "라이브 호출 0" 은 더 이상 성립하지 않는다. 대가로 소진이 일 단위로 고착되는 상태를 최대 1시간 안에 해소한다.
- **미해소(이월)**: root access token 은 root Claude Code CLI 세션이 돌 때만 회전한다(TTL ~8h). claude-corp 소진 기간 동안 root 가 유일 가용 계정이므로, root 세션 공백이 8시간을 넘으면 정적 검사가 root 를 탈락시켜 **전면 중단**이 된다. 스크립트가 `refreshToken` 으로 직접 회전하는 해법은 사용자 자격증명 저장소 쓰기(§12.3 Critical)라 사람 결정 필요 — TASK 「이월 항목」.
- Rollback: `CLAUDE_OAUTH_EXHAUSTION_GATE=0`(즉시, 재배포 불요) 또는 본 CHG revert → 2026-07-07~2026-08-06 정적-검사-전용 동작 복귀.
- ANCHOR 정합: §1(운영자 자격 일원화)·§2(Alt-A gateway 경유) 무충돌 — 어느 자격증명을 주입할지의 선택 로직이며 인증/인가 경계 변경 아님.
- Cross-ref: REVIEW REV-20260807T144800-oauth-exhaustion-gate · TASK `## TASK-20260807T144800-oauth-exhaustion-gate` · TEST Run 2026-08-07-oauth-exhaustion-gate · 선행 CHG-20260707(정적 검사 전환)·REV-20260730T191535(bare alias 단일계정 이월 P1 이 본 건으로 발현).

## CHG-20260807T190000-oauth-gate-hardening (사용량-소진 게이트 적대 리뷰 지적 반영)
- Date: 2026-08-07. 사용자 요청 "subagent 를 통해 적대 리뷰를 수행해주세요" 로 선행 CHG-20260807T144800 에 §18.8 패널(3렌즈 subagent)을 돌리고 그 지적을 반영한 후속.
- **패널이 잡은 P1 3건 (전부 수정)**:
  1. **burst-429 오강등** — 모든 429 를 "소진"으로 보고, `retry-after: 5` 조차 `min_cooldown`(300s)으로 **끌어올려** 계정을 강등했다. 계정이 2개뿐이고 root slot 이 root 고정이라, 1순위를 강등하면 `ANTHROPIC_API_KEY == ANTHROPIC_API_KEY_ROOT` 가 되어 alias→alias-root 2계정 체인이 **1계정으로 붕괴**한다(같은 계정에 4회 시도). 강등/복귀마다 `--force-recreate`(LLM 순단)가 붙어 cron 주기당 최대 2회, 하루 48회까지 가능했다. 5h 버스트 캡은 이 시스템의 config 주석이 스스로 "정상 이벤트"로 기술하는 흔한 상황이라 가설이 아니다. → `unified-7d-status=rejected` 이거나 헤더가 말하는 쿨다운이 `CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC`(기본 1800s) 이상일 때만 강등하고, 짧은 429 는 `transient` 로 분류해 litellm 에 맡긴다. 클램프는 강등이 확정된 뒤에만 적용한다.
  2. **recreate 실패 영구화** — `docker compose up -d --force-recreate` 의 종료 상태를 검사하지 않고 출력도 버려서, 한 번 실패하면 `.env` 는 새 토큰인데 컨테이너는 옛 토큰을 물고 있고 다음 실행은 `CHANGED=0` 으로 "변경 없음 skip" 하며 **영구히 재시도하지 않았다**(토큰 만료 후 전량 401). → sentinel(`.env.bedrock.needs-recreate`) + 다음 실행 재시도 + 실패 시 exit 1 + stderr 보존.
  3. **fail-open 후 회복 probe 무한 반복** — 쿨다운 만료 시점의 probe 가 네트워크 오류로 판정 보류되면 과거 `until` 이 그대로 보존돼, 이후 **매 cron 실행마다** probe 가 나갔다(heartbeat 우회, 코드 자신의 주석과 모순). → `checked < until` 을 함께 봐 **쿨다운 만료당 정확히 1회**로 제한.
- **P2 (수정)**: 쿨다운 헤더 파싱 견고화(stale·상대초·ms `unified-reset` 배제 + `retry-after` 폴백, HTTP-date 포함) · 손상된 상태 항목(non-dict)이 selector 를 죽여 1순위 slot 이 무음 정지하던 결함 · 전원 소진 시 **가장 빨리 회복되는** 계정 유지 · 1순위 SEL tab 가드(계정 이름이 토큰으로 주입될 수 있었다) · `$ACCOUNTS` glob 확장 차단.
- **보안 (수정)**: `.env.bedrock` 0600 — 이 호스트에는 `docker` 그룹이 아닌 비특권 계정 `claude-corp`(에이전트 세션 신원)이 있고, `namei -m` 상 경로 전 구간이 o+x 이며 파일이 0664 라 **root 개인 Max 계정 OAuth 토큰을 그대로 읽을 수 있었다**(자격증명 원본은 0600 root:root — OS 경계를 .env 가 우회). 선행 결함이지만 본 cycle 이 그 파일을 쓰므로 여기서 닫는다. 그 외: 상태 디렉토리 0700 / 파일 0600 + `mkstemp`(고정 `.tmp` 심링크로 임의 파일 덮어쓰기 — 실증됨) · `detail` 의 `sk-ant-*` 마스킹·제어문자 제거·200자 컷(자격증명이 깨지면 예외 메시지에 Bearer 헤더 전체가 실린다 — 실증됨) · probe 리다이렉트 미추종(urllib 은 3xx 에서 `Authorization` 을 **타 호스트로도** 재전송 — 실증됨) · 제어문자 토큰 주입 거부.
- 변경 (2 파일): `bin/refresh-claude-oauth-token.sh`, `unit/feature-0002-agent-core/tests/test_oauth_exhaustion_gate.py`.
- 새 knob: `CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC`(기본 1800).
- Verification: 41건 PASS(15→41). **mutation 재검증** — 패널이 생존시킨 19개 mutant 중 18개 KILL, 1개(`os.chmod(tmp,0600)`)는 `mkstemp` 가 이미 0600 을 보장하는 **등가 mutant**(같은 경로를 `mkstemp`→고정 `open` 으로 바꾸는 mutant 는 KILL 됨). 자체 발견: 새로 쓴 보안 테스트 2건이 처음엔 **vacuous** 였다(가짜 서버가 3-tuple 응답에서 죽어 '연결 끊김'으로 위장 / 302 이후 GET 을 기록하지 않음) — mutation 이 잡아냈고, 하네스에 핸들러 예외 표면화·GET 기록·잉여 probe 감지를 추가했다.
- **미해소(이월)**: root access token 회전 주체 부재(§12.3 Critical). `select_account` stdout 의 tab 가드는 외부 유발 불가한 내부 불변식이라 회귀 테스트 미부착(mutation 생존 1건, 정직 표기).
- Rollback: 본 CHG revert 또는 `CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC=0`(강등 기준만 종전으로).
- Cross-ref: REVIEW REV-20260807T190000-oauth-gate-hardening · TASK `## TASK-20260807T190000-oauth-gate-hardening` · TEST Run 2026-08-07-oauth-gate-hardening · 선행 CHG-20260807T144800.

## CHG-20260811T120000-oauth-auto-rotate (access token 자동 회전 — 사용자 승인, §12.3 Critical)
- Date: 2026-08-11. 사용자 승인 "후속 과제 또한 승인하겠습니다. 토큰 만료에 따라 자동회전되도록 구성해주세요."
- **문제**: 이 스크립트는 디스크의 access token 을 읽기만 했고 실제 회전은 그 계정의 Claude Code CLI 세션이 돌 때만 일어났다. TTL ~8h 라 야간·주말 세션 공백이 생기면 정적 검사가 계정을 탈락시키고, 다른 계정마저 소진돼 있으면 LLM 전면 중단이 됐다(2026-08-07~11 실사례).
- **규약은 실측으로 확정**(추측 금지): CLI 번들 2.1.220 에서 `TOKEN_URL=https://platform.claude.com/v1/oauth/token`, `CLIENT_ID=9d1c250a-e61b-44d9-88ed-5944d1962f5e`, JSON 본문 `{grant_type,refresh_token,client_id,scope}`. 비파괴 확인: 잘못된 refresh token → `400 invalid_grant`. **UA 필수** — 기본 urllib UA 는 Cloudflare 1010 으로 앱 미도달, `Claude-User (claude-code/<ver>)` 필요.
- **구현**: 만료까지 `CLAUDE_OAUTH_ROTATE_LEAD_SEC`(기본 3600) 이하면 선제 회전. 원자적 교체(mkstemp+fsync+`os.replace`), 소유자·모드 보존(root 소유로 바꾸면 계정 CLI 로그인이 깨진다), `.bak-*` 백업(기본 5), 실패 시 파일 무접촉, 지수 backoff.
- **적대 패널(§18.8, subagent 2렌즈) 결과 두 렌즈 모두 FAIL — P1 5건 전량 수정**:
  1. **`--check` 가 실제로 회전**했다. 부작용 0 계약 위반이자, 인시던트 진단 중 운영자가 부르는 명령이 일회성 refresh token 을 태웠다. → `check_only` 면 즉시 skip.
  2. **회전 중 예외가 selector 를 죽였다**. 서버가 돌려준 응답 하나(`scope` 가 배열, 본문이 배열/`null`)만으로 파이썬 블록이 죽고, bash `SEL="$(...)" || SEL=""` 가 삼켜 1순위 slot 이 **exit 0 으로 조용히 갱신 정지**했다(`:742-744` 가 이미 한 번 고쳤다고 적어 둔 그 구멍). → 호출부 try/except + payload 타입 검사.
  3. **`expires_in` 부재 시 과거 만료를 되썼다**. 회전한 이유가 "곧 만료"이므로 그 값을 되쓰면 방금 받은 멀쩡한 토큰이 만료로 판정된다 → 매 실행 재회전 + 게이트웨이 재생성 폭풍(3런 3회 실측). → 기본 TTL 폴백 + 상한 클램프.
  4. **`.bak` 경로 심링크 추종**. 이름이 `…bak-<epoch>` 로 완전 예측 가능하고 `shutil.copy2`/`chmod`/`chown` 이 전부 심링크를 따라가, 비특권 계정이 root 로 임의 파일 덮어쓰기 + **소유권 탈취**를 할 수 있었다(실증). → `O_CREAT|O_EXCL|O_NOFOLLOW` + 랜덤 접미사, `os.lstat`.
  5. **POST 성공 후 백업 단계에서 실패하면 소모된 refresh token 이 유실**됐다(재로그인 외 복구 불가). 백업이 durable write 보다 **앞**이었다. → 원자적 쓰기를 먼저 끝내고, 백업은 메모리에 든 직전 바이트로 best-effort.
- **P2 수정**: 요청 **직후** 재확인 추가(HTTP 왕복 동안 CLI 가 쓴 결과를 우리 스냅샷이 덮어쓰던 lost update) · 서버가 좁힌 `scope` 를 영속화하지 않음(RFC 6749 §5.1 — 저장하면 되돌릴 수 없다) · `keep_backups=0` 이 오히려 전부 보관하던 의미 반전 · 실패 backoff(지수, 상한 6h)로 무한 재시도 차단 · lock 을 `O_NOFOLLOW`/`lstat` 로 · **"CLI 와 같은 lock 규약" 주석이 거짓이었음을 정정**(CLI 는 `.oauth_refresh.lock` 을 쓴다 — 실제 방어는 lock 이 아니라 요청 전후 2회 재확인).
- 변경 (2 파일): `bin/refresh-claude-oauth-token.sh`, `unit/feature-0002-agent-core/tests/test_oauth_exhaustion_gate.py`.
- 새 knob: `CLAUDE_OAUTH_AUTO_ROTATE`(킬스위치) · `ROTATE_LEAD_SEC` · `TOKEN_URL` · `CLIENT_ID` · `USER_AGENT` · `ROTATE_KEEP_BACKUPS` · `ROTATE_DEFAULT_TTL` · `ROTATE_BACKOFF_BASE/MAX` · (테스트 훅) `ROTATE_RACE_DELAY_SEC`.
- Verification: 55 → **75건** PASS. **mutation 20/20 KILL**(패널이 남긴 5개 생존 mutant 포함 — 그중 3개는 내 테스트가 vacuous 해서 살아 있었고 하네스를 고쳐 잡았다). 실 자격증명 **사본**으로 write-back preflight: 필드 유실 0, 소유자·모드 보존, 원본 무접촉.
- **미해소(이월)**: 패널이 발견한 선행 상태 — `/root/.claude` 와 `/root` 의 POSIX ACL 이 `claude-corp` 에 rwx 를 부여한다. 본 변경이 만든 것이 아니지만 계정 분리 전제를 무너뜨리므로 별도 검토 필요.
- Rollback: `CLAUDE_OAUTH_AUTO_ROTATE=0`(즉시) 또는 본 CHG revert. 자격증명은 `.bak-*` 로 되돌릴 수 있다.
- Cross-ref: REVIEW REV-20260811T120000 · TASK `## TASK-20260811T120000-oauth-auto-rotate` · TEST Run 2026-08-11-oauth-auto-rotate · 선행 CHG-20260807T190000.

## CHG-20260811T140000-oauth-acl-intent-record (계정 분리의 신뢰 경계 부재를 명문화 — 문서 전용)
- Date: 2026-08-11. **코드 변경 0.** 선행 CHG-20260807T190000 / CHG-20260811T120000 의 적대 리뷰가 P1 로 올린 두 항목의 **심각도를 운영자 확인에 따라 재평가**한 기록.
- **운영자 확인(2026-08-11)**: "권한은 의도된 설정이다. WSL 환경에서 여러 claude 계정을 구분하여 사용하기 위해 분리해두었으며, 각 계정이 내부적으로 접근하는 권한은 모두 root 단위로 동일하다."
- **따라서 재평가되는 것**:
  - `.env.bedrock` 0664 → 비특권 `claude-corp` 가 root Max OAuth 토큰을 읽을 수 있다(REV-20260807T190000 security P1). **권한 상승 아님** — 두 계정 사이에 신뢰 경계가 없다. 0600 조치는 유지하되 근거는 "권한 경계" 가 아니라 **위생·최소노출**이다.
  - `.bak` 심링크 추종에 의한 "소유권 탈취"(REV-20260811T120000 security P1). **권한 상승 아님**. 다만 임의 파일 덮어쓰기는 여전히 **사고 유발 요인**(예측 가능한 이름 + 심링크 오작동)이므로 `O_CREAT|O_EXCL|O_NOFOLLOW` + 랜덤 접미사 조치는 유지한다.
  - `/root`·`/root/.claude` 의 `user:claude-corp:rwx` ACL. **의도된 구성** — 조치 불요. 이월 항목 종결.
- **유지되는 결함 판정(재평가 대상 아님)**: 같은 리뷰의 나머지 P1 — burst-429 오강등, recreate 실패 영구화, `--check` 가 회전, selector 사망에 의한 slot 무음 정지, `expires_in` 과거 만료 되쓰기, POST 후 백업 실패로 refresh token 유실 — 은 전부 **권한과 무관한 가용성·정합성 결함**이고 이미 수정됐다.
- **왜 기록하는가**: 원장에 열린 P1 으로 남겨 두면 다음 적대 패널이 같은 것을 다시 최상위로 올려 실제 결함 탐색 예산을 갉아먹는다. 향후 리뷰어는 이 항목을 **환경 전제**로 읽어야 한다.
- Cross-ref: REVIEW REV-20260811T140000 · TASK `## TASK-20260811T120000-oauth-auto-rotate` 이월 종결 · 선행 REV-20260807T190000 / REV-20260811T120000.
