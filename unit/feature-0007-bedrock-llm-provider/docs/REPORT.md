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
- 총 변경 횟수: 4

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

<!-- 본 cycle 의 누적 변경 — REPORT.md 는 rewrite 정책 이지만 추가 commit 의
     사항을 §3 Recent Changes 의 last commit 기록 형태로 누적. -->

> CHG-20260522-0003 추가 (2026-05-22): codex P2 follow-up. paired fallback chain
> refactor — `_select_llm_provider()` helper 가 (base_url, api_key) tuple 을
> paired 결정. silent misroute 회귀 차단. .env.example paired 정책 안내.
