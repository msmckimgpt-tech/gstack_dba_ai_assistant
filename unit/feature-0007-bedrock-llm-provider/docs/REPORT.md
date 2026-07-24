---
doc_type: REPORT
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

API Vault (사용자별 OpenAI API key 입력 wizard) 패턴을 전면 폐기하고 서비스가
보유한 단일 AWS Bedrock 자격증명 (Seoul region `ap-northeast-2`, LiteLLM proxy
gateway 경유) 으로 모든 LLM 호출을 라우팅하도록 provider 통합을 변경한 cycle.
사내 직원 전용 운영 환경 가정 + per-user quota 후순위 + API Vault 전면 폐기
사용자 결정 5 항목 정합. Phase A (gateway + config + model catalog) + Phase B
(backend API Vault 제거) + Phase C (frontend UI 제거) + Phase D (정책 doc 갱신)
완료. Phase E (실 환경 회귀 검증) 사용자 위임. 위험 등급 Major (§12.3) —
Critical 후보였던 외부 노출 / PIPA / 비용 폭주 risk 가 사내 한정으로 완화.

**후속 (llm-routing-interactive-split, 2026-07-04, ADR-002)**: insight-worker 가
주말/야간 내내 gemma 로 고착(refresh-oauth cron 평일한정 → 토큰 만료 방치 → litellm
401 → edge-fallback 강등)하던 현상을 진단하고 용도별 모델 라우팅을 재구성했다.
① litellm alias 분리 — 사람 실시간 호출(대화·AI 능동 분석)은 `claude-haiku-4-interactive`
(+`-root`)로 항상 claude, 백그라운드 insight 배치는 시각 기반(`_effective_insight_model`,
평일 근무 claude / 야간·주말 edge) 강등. ② fallback 체인 결함(`No fallback model group
found for claude-haiku-4-root`) 수정 — root/interactive-root 명시 등록으로 gemma 도달 보장.
③ 운영: `.env` 대화/분석 모델을 interactive 로 재배치 + refresh/keepalive cron 24/7 확장
(토큰 상시 유효화). 단위 회귀 `test_insight_offhours_routing.py`(13) + `test_llm_env_naming.py`.

**후속 (cron-static-refresh, 2026-07-07)**: 위 24/7 확장이 `refresh-claude-oauth-token.sh`
의 라이브 probe(2026-06-29 도입)와 결합해, claude-corp 세션 윈도우가 30분마다 실 API
호출로 재고정되어 `session-keepalive-cron.sh` 앵커 핑이 무력화되는 부작용을 진단하고
제거했다. probe 는 2026-07-03 insight-llm-fallback 이후 litellm 요청-레벨 fallback 과
구조적으로 중복이었음을 litellm 소스(`router.py`) 직접 확인으로 검증 — 401/429 모두
예외 타입 무관하게 fallback 이 작동한다. 스크립트를 static_check() 단독 판정으로
재설계 + bedrock-gateway 로그 기반 무비용 관측(RateLimitError/AuthenticationError
카운트) 신설 + stale crontab 주석 정리.

## 2. Progress
- Planned: Phase E (실 환경 + AWS 자격증명 회귀 검증), Phase F (verify-completion
  PASS + commit + PR).
- In Progress: 없음 (Phase A~D 완료 후 정지 상태).
- Done:
  - **Phase A** (gateway + config + model catalog): 8 task — litellm_config.yaml
    작성, docker-compose.yml `bedrock-gateway` 서비스 추가, .env.example 5 env
    추가, config.py `LLM_BASE_URL` / `LLM_API_KEY` fallback chain 갱신,
    model_catalog.py Claude alias 교체, llm.py `_get_openai_client` 단순화,
    agent_core.py `_run_agent_core` api_key 인자 deprecated, docker compose
    config YAML schema 검증 PASS.
  - **Phase B** (backend API Vault 제거): 4 task — `/api/api-vault/options`
    semantic 단순화, `_decrypt_api_key` / `_is_safe_api_key` / `_is_safe_passphrase`
    함수 제거, `/api/ask` cipher 분기 + 검증 + 복호화 경로 제거, py_compile
    PASS.
  - **Phase C** (frontend API Vault UI 제거): 5 task — index.html Profile drawer
    "API Vault" 탭 + pane DOM 제거, app.js vault DOM 참조 / readVaultState /
    encryptPlainApiKey 등 함수 일괄 제거, styles.css `.vault-*` 186 줄 제거,
    cache-bust 버전 bump (`v=20260521-bedrock-cutover`), node --check PASS.
  - **Phase D** (정책 doc): 3 task — docs/SECURITY.md §6.1 신설 + §9.2 갱신,
    docs/DECISIONS.md ADR-0022 append, docs/STATUS.md feature-0007 row 추가 +
    최근 갱신 entry.
  - feature-0007 docs (FUNCTION / TASK / ANCHOR / MODIFY / REVIEW / REPORT)
    작성.

## 3. Recent Changes
- **CHG-20260707-oauth-cron-static-refresh** (2026-07-07): `refresh-claude-oauth-token.sh`
  cron(24/7, 30분 주기)의 라이브 probe(Anthropic `/v1/messages` 실호출, 2026-06-29 도입)가
  claude-corp 5시간 rolling 세션 윈도우를 `:00`/`:30` 격자에 계속 재고정해
  `session-keepalive-cron.sh`(07:35/12:35 앵커) 를 무력화하던 원인을 근본 제거. 이 probe 는
  2026-07-03 insight-llm-fallback 이후 litellm 요청-레벨 `fallbacks:` 체인과 구조적으로
  중복이었다 — litellm 소스(`router.py` `should_retry_this_error`/
  `async_function_with_fallbacks_common_utils`) 직접 확인 결과 AuthenticationError(401)·
  RateLimitError(429) 모두 예외 타입 무관하게 fallback 경로를 탄다. 변경: **(1)**
  `bin/refresh-claude-oauth-token.sh` — `live_probe()` + `CLAUDE_OAUTH_PROBE*` env var
  전면 제거, static_check() 단독 판정(네트워크 호출 0). `log_fallback_observability()`
  신설 — 매 실행 시 `docker compose logs` 로 최근 bedrock-gateway 로그의
  RateLimitError/AuthenticationError 건수만 집계(로컬 읽기, 과금·네트워크 없음), 0건이면
  무음. **(2)** host `root` crontab — 2026-07-02 stale 주석 블록 제거(실제로는 이미
  2026-07-04 24/7 로 대체돼 무관한 backup/metadata-graph-sync 항목 사이에 방치돼 있었음)
  + 이력 재작성. claude-corp 자동 복귀 동작은 무변경(자격증명 파일 유효한 한 매 실행
  1순위 주입 — probe 여부와 무관하게 항상 그래왔음). 검증: `bash -n` PASS, `--check`
  정상 동작(정적 검사만), `docker` 미가용 PATH 에서도 관측 함수 fail-open 확인.
- **CHG-20260703-insight-llm-fallback** (2026-07-03): insight-worker LLM(`claude-haiku-4`)의 claude-corp
  **burst rate-limit(429)** 대응 — **litellm 요청-레벨 fallback 체인** 구성. TASK-0308(insight 부하 분산)
  후속: insight 를 `AGENT_INSIGHT_MODEL=claude-haiku-4` 로 돌리자 schema/table 생성 burst 가 claude-corp
  OAuth 의 RPM/TPM 을 초과해 429(200 성공 0)로 완전 차단됐다(계정 자체는 probe 200 = 유효). 기존
  refresh 스크립트의 계정-폴백은 계정 **완전 소진(probe 429)** 시만 작동해 burst 를 못 잡음 → 요청-레벨 필요.
  변경 2건: **(1) `litellm_config.yaml`** — `claude-haiku-4`(claude-corp, api_key=ANTHROPIC_API_KEY) →
  `claude-haiku-4-root`(root Max, api_key=ANTHROPIC_API_KEY_ROOT) → `edge-fallback`(로컬 gemma
  `openai/gemma4:e2b` via local-llm-gateway, api_key 리터럴)의 3-deployment + `litellm_settings.fallbacks:
  [{"claude-haiku-4":["claude-haiku-4-root","edge-fallback"]}]` + `num_retries:1`. **(2)
  `bin/refresh-claude-oauth-token.sh`** — 기존 단일-slot 택일 폴백 → **병행 주입**: ANTHROPIC_API_KEY ←
  우선순위($ACCOUNTS) 첫 사용가능, ANTHROPIC_API_KEY_ROOT ← root 전용. 각 slot 독립 검사(static+라이브
  probe), 사용가능 시만 갱신, 둘 다 불가면 exit 1. 두 토큰이 각 env 에 동시 존재해야 요청-레벨 fallback
  성립. cron(`0,30 10-18 * * 1-5`) 주기 갱신 유지. ANCHOR §1(운영자 자격 일원화)·§2(LiteLLM gateway) 정합
  — 사용자별 키 아님(운영자 두 계정 + 로컬). 비밀정보는 `.env.bedrock`(gitignored)에만.
- **CHG-20260625T171844** (2026-06-25): 개발 단계 LLM provider **호출 주체** 임시 전환 —
  claude-corp 회사 OAuth → **root 개인 OAuth** (`/root/.claude/.credentials.json`,
  subscriptionType `max`). 사용자 지시 (DQA LLM 게이트를 개인 계정으로 일시 우회 —
  crontab 의 사전 배치된 `CLAUDE_OAUTH_ACCOUNT=root` 라인 활성화 요청). 변경 2건:
  **(1) `bin/refresh-claude-oauth-token.sh`** — `CLAUDE_OAUTH_ACCOUNT` env var 로 토큰 출처
  계정 선택 추가. 미지정 시 `claude-corp` (= 기존 동작 유지, backwards-compatible),
  `root`→`/root/.claude`, 그 외 `<name>`→`/home/<name>/.claude`. 로그·헤더 주석도
  계정-중립화. 비밀정보 미포함 (토큰은 `.env.bedrock`=gitignored 에만 주입).
  **(2) host `root` crontab** (git 미추적 runtime 상태) — 기존 claude-corp 라인 주석 처리 +
  `CLAUDE_OAUTH_ACCOUNT=root` 라인 주석 해제. 백업 `/tmp/crontab-backup-*.txt`.
  **즉시 적용**: `CLAUDE_OAUTH_ACCOUNT=root bash bin/refresh-claude-oauth-token.sh` 1회
  실행 → `.env.bedrock` `ANTHROPIC_API_KEY` 를 root 토큰으로 교체 + `bedrock-gateway`
  force-recreate. **검증**: 게이트웨이 토큰 == root 토큰 (≠ claude-corp 토큰), 컨테이너
  `health=healthy`, root 토큰 만료 여유 ~5h. 토큰 생명주기: root 의 VSCode Claude Code 가
  access token 자동 refresh → 동 cron(30분 주기)이 최신 토큰 재주입 (claude-corp 때와 동일
  메커니즘, 계정만 상이). ⚠ **개발용 임시** — 구독 OAuth 는 약관/rate limit 상 서비스 운용
  부적합. 전제: root VSCode Claude Code 세션 유지 (토큰 refresh 주체).
  **claude-corp 복귀 절차**: crontab 두 라인 토글 역전 (root 라인 주석 + claude-corp 라인
  주석 해제) + `bash bin/refresh-claude-oauth-token.sh` 1회 실행 (env var 없이 → claude-corp).
- **CHG-20260623-0001** (2026-06-23): 개발 단계 LLM provider 임시 전환 — AWS Bedrock
  → claude-corp Anthropic OAuth (회사 발급 Claude Team 계정 `masangsoft.com`). 배포 전
  개발 운용 목적 (Bedrock API 키 / Console API key 미발급 상황). 변경: litellm_config.yaml
  의 `claude-sonnet-4` / `claude-haiku-4` 를 `anthropic/` provider 로 전환 (배포용 Bedrock
  라인은 주석 보존), `titan-embed` 비활성 주석 (Anthropic 임베딩 미제공 → KB 검색 보류,
  최근 트래픽 0). `.env.bedrock` 에 `ANTHROPIC_API_KEY` (sk-ant-oat OAuth token) 주입 —
  litellm 1.85.1 이 OAuth 토큰 감지해 `Authorization: Bearer` + `oauth-2025-04-20` 로 전송.
  토큰 생명주기: claude-corp 의 VSCode Claude Code 가 access token 자동 refresh →
  `bin/refresh-claude-oauth-token.sh` (host root cron 30분 주기) 가 `credentials.json` 의
  최신 토큰을 게이트웨이에 반영 (토큰 변경 시에만 `up -d --force-recreate`). 검증: 앱 →
  게이트웨이 → Anthropic (claude-corp 계정) HTTP 200 성공, thinking 정상.
  ⚠ **개발용 임시** — 구독 OAuth 는 약관 / rate limit 상 서비스 운영 부적합. 전제: claude-corp
  VSCode Claude Code 세션 유지 (토큰 refresh 주체).
  **배포 복구 절차**: (1) litellm_config.yaml `model:` 주석 토글 (anthropic → bedrock 2줄),
  (2) `.env.bedrock` 의 `AWS_BEARER_TOKEN_BEDROCK` 에 Bedrock 장기 API 키 채움, (3) `crontab`
  에서 `refresh-claude-oauth` 라인 제거, (4) `docker compose up -d --force-recreate
  bedrock-gateway`. git: `litellm_config.yaml`(M) + `bin/refresh-claude-oauth-token.sh`(신규)
  는 환경 특정 개발 구성이라 commit 안 함 (로컬 유지). 선행 작업: 동 cycle 에서 의도치 않은
  IAM access key (`mckim` AKIA…) 인증 경로 제거 → bearer 방식 전환 (`.env.bedrock` IAM 키
  삭제). 기존 IAM 키 AWS 콘솔 Deactivate→Delete 는 사용자 후속.
- **CHG-20260522-0001** (2026-05-22): codex review P1 fix — `/api/session` 의
  default_model fallback 3 사이트가 `os.getenv("OPENAI_MODEL", "auto")` →
  `os.getenv("OPENAI_MODEL", API_DEFAULT_MODEL)`. ship 직후 첫 사용자 turn
  실패 회귀 차단. py_compile PASS.
- **CHG-20260521-0002** (2026-05-21): Phase E 검증 결과 반영. global Sonnet 4.6
  inference profile 수용 + `API_DEFAULT_MODEL = claude-sonnet-4` + 정책 doc
  reanchor.
- **CHG-20260521-0001** (2026-05-21): AWS Bedrock LLM provider 통합 + API Vault
  전면 폐기. 18 파일 변경 (인프라 3 + backend 5 + frontend 3 + 정책 doc 3 +
  feature-0007 docs 4). py_compile + node --check + YAML schema PASS.
- 총 변경 횟수: 5

## 4. Open Issues
- ~~**Claude 4.x 실 model ID 미확정**~~: **Phase E 검증으로 확정** —
  `bedrock/global.anthropic.claude-sonnet-4-6` (frontier) + `bedrock/global.
  anthropic.claude-haiku-4-5-20251001-v1:0`. region-pinned 부재 사실 확인.
- ~~**gateway healthcheck endpoint 버전 검증**~~: **PASS** — LiteLLM
  `main-stable` 의 `/health/liveliness` 가 200 + `"I'm alive!"` 응답.
- ~~**`/api/session` default_model fallback `'auto'` 잔존 (SUBAGENT NT #3 /
  Codex P1)**~~: **fix 완료 (CHG-20260522-0001)** — 3 사이트가
  `API_DEFAULT_MODEL` fallback 사용.
- **Codex P2 (paired fallback chain)**: `LLM_BASE_URL` ↔ `LLM_API_KEY` 의 독립
  fallback 으로 `BEDROCK_GATEWAY_URL` 만 설정 + `BEDROCK_GATEWAY_API_KEY` 미
  설정 시 misroute 위험. 사내 한정 운영 가정으로 risk 낮음 — follow-up cycle.
- **6 blindspot (codex 미review 영역)**: docker-compose env_file leak / Claude
  tool_use 변환 / data region / max_tokens / reasoning / masked field drift —
  follow-up cycle 또는 별도 `/codex consult`.
- **OpenAI legacy 호환 잔존 가능성**: feature-0003 외 다른 unit (insight-worker,
  agent CLI 등) 가 `OPENAI_API_KEY` env 직접 참조하는지 grep 추가 검증 필요.
- **APAC inference profile 추적**: 미래에 ACTIVE Sonnet 의 APAC profile 추가
  시 region-pinned 마이그레이션 별 cycle 권장. AWS Bedrock release note
  모니터링.

## 5. Test Status
- **자동 테스트 (정적)**:
  - py_compile PASS: config.py, model_catalog.py, llm.py, agent_core.py, app.py
  - node --check PASS: app.js
  - YAML schema PASS: docker-compose.yml (services 10 개 — bedrock-gateway 포함)
- **cron-static-refresh 검증 (2026-07-07)**:
  - `bash -n bin/refresh-claude-oauth-token.sh` PASS.
  - `--check` 모드로 claude-corp/root 두 계정 정적 검사 정상 선택 확인(실
    `.env.bedrock`·자격증명 파일 대상, 라이브 API 호출 없음).
  - PATH 에서 `docker` 제거 후 실행 — 관측 함수(`log_fallback_observability`)가
    fail-open 으로 script 를 abort 시키지 않고 정상 완주(exit 0) 확인.
  - 관측 함수의 grep-count 로직을 합성 로그 문자열로 단위 검증(RateLimitError 1건
    + AuthenticationError 1건 입력 → 정확히 카운트).
  - bedrock-gateway 컨테이너의 실제 최근 72h 로그를 조회해 RateLimitError/
    AuthenticationError 미발생(0건, 무음 정상 경로) 확인.
  - **litellm 소스 검증(라이브 API 호출 아님, 코드 리딩)**: 게이트웨이 컨테이너
    내부 `/app/litellm/router.py` 를 직접 읽어 `should_retry_this_error` /
    `async_function_with_fallbacks_common_utils` 확인 — AuthenticationError(401)·
    RateLimitError(429) 모두 예외 타입 무관하게 fallback 경로를 탐(Context
    WindowExceededError/ContentPolicyViolationError 만 별도 특별 처리). 401/429
    둘 다 fallback 이 작동한다는 기존 주석의 주장이 코드 레벨로 확인됨.
- **Phase E 실 환경 검증 (2026-05-21)**:
  - **TEST-0001 (gateway healthcheck): PASS** — `docker compose -p
    feature-0007-e up -d bedrock-gateway` → `Up (healthy)`, 8080
    `/health/liveliness` 200.
  - **추가 검증 (IAM + Sonnet 4.6 model access): PASS** — `global.anthropic.
    claude-sonnet-4-6` inference profile 직접 호출 + gateway 경유 alias 호출
    둘 다 200, 응답 정상.
  - **TEST-0004 (JSON 파싱): PASS** — Claude 의 markdown fence JSON 출력을
    `_extract_json_object` 가 정상 추출.
  - **사용자 reanchor**: Seoul region 한정 → global routing 수용 (사내 한정 +
    비-개인정보 SQL 작업 가정으로 PIPA risk 낮음).
- **미검증 항목 (Phase E 추가 필요 — full stack 가동 후)**:
  - TEST-0002 `/api/ask` cipher 미동봉 응답 — web + mysql 컨테이너 가동 필요.
  - TEST-0003 agent loop SQL 생성 + tool use — full stack + 테스트 DB 필요.
  - TEST-0005 frontend 신규 사용자 진입 — full stack 가동 필요.
  - TEST-0006 localStorage cleanup — 실 브라우저 세션 필요.

## 6. Blocked Items
- 없음 (Phase A~D 자율 진행 완료).

## 7. Human Attention Needed
- **Phase E 회귀 검증** (사용자 수행): AWS 자격증명 주입 + Bedrock model access
  활성화 (Claude Sonnet 4.x + Haiku 4.x) + docker compose up 후 healthcheck
  PASS + `/api/ask` smoke test 1 conv. 회귀 발견 시 본 cycle 로 fix iteration.
- **AWS console 사전 점검**: (a) Seoul region 의 Claude 4.x model 정확한
  versioned ID, (b) IAM credential 의 `bedrock:InvokeModel` 최소 권한 + model
  access 활성화 여부.
- **commit + PR**: 본 cycle 의 작업 결과를 commit (외부 영향 행동 — 사용자 명시
  confirm 후 진행). PR 생성 시 별 cycle 의 `/codex review` outside voice 호출
  권장 (gateway SPOF + AWS credential leak + Claude tool use schema 의 blindspot
  검증).
- **cron-static-refresh 사후 관찰 (1~2일, 사용자/후속 세션)**: probe 제거 후
  `session-keepalive-cron.sh`(07:35/12:35) 가 다시 그 날의 첫 실호출이 되어
  claude-corp 5시간 윈도우의 예측 가능한 앵커 역할을 하는지, `/tmp/refresh-oauth.log`
  및 `~/.local/bin/artifacts/session-keepalive/` 의 실제 로그로 확인 필요 — 실
  경과 시간이 필요한 검증이라 본 cycle 내 완결 불가.
- **(참고 발견, 본 cycle 범위 밖)** bedrock-gateway 로그 조사 중 `claude-haiku-4-chat-root`
  alias 가 `max_tokens must be greater than thinking.budget_tokens` BadRequestError
  로 반복 실패하는 것을 확인(요청에 `max_tokens` 미지정 추정, thinking.budget_tokens=5000
  보다 작게 기본값이 잡히는 것으로 보임). 이 alias 는 fallback 체인 종단(edge 없음,
  2026-07-07 사용자 결정)이라 실패가 그대로 사용자에게 노출될 수 있음 — 본 cycle 의
  probe 제거와 무관한 별도 버그로 보이며, 별 cycle 에서 조사 권장.

## 8. Suggested Improvements
- **per-user token quota** (배포 후 별 cycle): gateway 의 callback hook 으로
  `WebAuditEvents.conversation.ask` ChangeJson 에 `input_tokens` / `output_tokens`
  / `bedrock_model` 첨부. role 별 token tier (admin/operator 무제한, sales 제한).
- **gateway healthcheck 강화**: 단순 liveness 외에 `models/list` endpoint 호출
  으로 Bedrock 연결 동작성 검증 (gateway 가 띄워졌지만 Bedrock 인증 실패 상태
  탐지).
- **모델 ID rotation 정책**: AWS Bedrock 의 Claude versioned model ID 가
  deprecate 시 자동 알림 + ID 갱신 cycle. 운영자 매뉴얼에 명시.
- **boto3 native hotspot 마이그레이션** (운영 정상화 후): latency / cost /
  streaming 최적화 여지가 큰 hotspot (예: agent loop 의 plan 호출) 만 selective
  native 전환. `llm.py` 의 wrapper 도입 비용 vs 운영 이득 비교.
- **모델 selector UI 신설** (사용자 요청 발생 시): 현 구현은 server default
  (`claude-haiku-4`) 사용. 사용자가 turn 별로 Sonnet ↔ Haiku 선택권 필요 시
  composer chip 옆에 모델 selector dropup 신설.
- **node_analysis(AI 능동 분석)도 bare `claude-sonnet-4` 사용 — 동일 취약성 잔존**
  (sonnet-chat-fallback 2026-07-24 발견): `AGENT_NODE_ANALYSIS_MODEL=claude-sonnet-4`
  는 `conversation_answer_model` 을 거치지 않아 여전히 root 계정 fallback 없는 단일 계정
  bare alias 로 나간다. 대화(agent)만 본 cycle 에서 `-chat` 2계정 체인으로 격리했으므로,
  claude-corp 429 시 node_analysis 는 아직 즉시 실패 가능(백그라운드 경로라 사용자 차단은
  아니나 분석 누락). 필요 시 별 cycle 로 `-interactive` 계열처럼 sonnet 분석 alias 에도
  2계정 체인 부여 검토.
- **config 고정 thinking budget 대비 `agent_max_output` 하한 가드**(모든 thinking alias
  공통, sonnet-chat-fallback 시 재확인): admin 이 `agent_max_output(model)` 을 litellm
  config 의 고정 `budget_tokens`(haiku 5000 / sonnet 16000) 미만으로 낮추면 '일반' 레벨
  요청이 `max_tokens < thinking.budget_tokens` BadRequestError(2차 400)로 실패한다
  (TEST.md §7 haiku-chat-root 노트의 근인 후보). runtime_settings 에서 하한을 모델별
  config thinking 이상으로 clamp 하는 가드를 별 cycle 로 검토 권장.
- **`_LLM_PRICE_USD_PER_1M` 에 `-chat`/-chat-root alias 단가 미등록**(sonnet-chat-fallback 시
  적대 패널 재확인): 관리 콘솔 비용 뷰 중 계정별/일별은 `COALESCE(resolved_model, model)` 로
  키잉하는데, litellm 이 서빙 alias 를 `resp.model`(=resolved_model)로 에코하면
  `claude-sonnet-4-chat`·`claude-haiku-4-chat`(-root/-interactive 포함)가 단가표에 없어 **$0
  으로 오표시**된다(by_model 차트는 원본 model 키라 정상). 기존 gap 의 sonnet 확장 —
  `admin_usage._LLM_PRICE_USD_PER_1M` 에 alias→원본 단가 매핑(또는 resolved→원본 정규화)을
  추가해 일괄 해소 권장(별 cycle).

<!-- 본 cycle 의 누적 변경 — REPORT.md 는 rewrite 정책 이지만 추가 commit 의
     사항을 §3 Recent Changes 의 last commit 기록 형태로 누적. -->

> CHG-20260522-0003 추가 (2026-05-22): codex P2 follow-up. paired fallback chain
> refactor — `_select_llm_provider()` helper 가 (base_url, api_key) tuple 을
> paired 결정. silent misroute 회귀 차단. .env.example paired 정책 안내.
