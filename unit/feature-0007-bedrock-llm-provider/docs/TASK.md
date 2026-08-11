---
doc_type: TASK
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: Phase K 완료 (TASK-K7 사후 관찰 대기) — 원 Phase A~J 는 완료/PR 머지 완료
- Owner: AI (Claude)
- Priority: medium-high (배포 전 인프라 변경)
- Last Updated: 2026-07-07

## 2. Implementation Plan
<!-- §7.1 Plan-Review-Execute: 비사소한 작업 (2개 이상 파일 변경) 시 작성한다.
     본 cycle 은 16+ 파일 변경 예정으로 plan-review 필수. -->

### 2.1 Plan

#### 영향받는 파일 (16건)

**인프라 (3건)**
1. `docker-compose.yml` — `bedrock-gateway` 서비스 신규 추가 (LiteLLM image,
   internal network 만, port expose 안 함). `web` 서비스에 `depends_on:
   bedrock-gateway` 추가.
2. `.env.example` — 신규 5 env 추가: `BEDROCK_GATEWAY_URL`,
   `BEDROCK_GATEWAY_API_KEY`, `AWS_REGION=ap-northeast-2`, `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY` (sample value 만, 실 자격증명 X).
3. (신규 파일) `repo/unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`
   — gateway 의 model alias → Bedrock model ID 매핑.

**Backend — feature-0002-agent-core (4건)**
4. `repo/unit/feature-0002-agent-core/src/modules/config.py` — `LLM_BASE_URL` /
   `LLM_API_KEY` 의 default 가 gateway 환경변수로 향하도록 변경. `OPENAI_API_KEY`
   /`OPENAI_API_BASE` 의 fallback 위치 정리 (Local LLM 분기 보존).
5. `repo/unit/feature-0002-agent-core/src/modules/model_catalog.py` —
   `API_MODEL_OPTIONS` 의 GPT-5.4 시리즈 3 개 제거 → Claude Sonnet 4.x / Haiku
   4.x alias 2~3 개 추가. `API_DEFAULT_MODEL` 을 Claude alias 로 교체.
   `model_supports_temperature` 도 Claude 기준 갱신.
6. `repo/unit/feature-0002-agent-core/src/modules/llm.py` — `_get_openai_client`
   의 `effective_key = LLM_API_KEY or OPENAI_API_KEY` 단순화 (per-request key
   분기 제거). 호출 사이트가 env 단일 소스로 정합.
7. `repo/unit/feature-0002-agent-core/src/agent_core.py` — `_run_agent_core`
   signature 에서 `api_key` 인자 의미 변경 (인자 받아도 무시 + deprecation
   warning) 또는 제거. `_get_openai_client()` 호출 시 인자 미동봉.

**Backend — feature-0003-agent-web-ui (1건, 다량 hunk)**
8. `repo/unit/feature-0003-agent-web-ui/src/app.py`:
   - `/api/api-vault/options` endpoint 제거 (또는 deprecation 응답).
   - `_decrypt_api_key`, `_is_safe_api_key`, `_is_safe_passphrase` 함수 제거
     (호출처 없음 확인 후).
   - `_b64decode` 의 vault 전용 헬퍼이면 함께 제거 (다른 호출처 없으면).
   - `/api/ask` (line 5199~5353): `api_key_cipher` / `api_key_passphrase` 파라미터
     처리 분기 + `has_api_key_input` 분기 + `api_key = _decrypt_api_key(...)` 경로
     제거. `_run_agent_core` 호출 시 `api_key` 인자 미동봉.
   - `/api/ask` 의 "API 모델 사용 시 API 키 설정이 필요합니다" 검증 분기 제거.
   - `_is_local_llm_available` 의 의미 재해석 — Bedrock gateway 도 "외부 gateway"
     로 통합. 분기 단순화.

**Frontend — feature-0003-agent-web-ui (3건)**
9. `repo/unit/feature-0003-agent-web-ui/src/static/index.html`:
   - Profile drawer 탭 list 에서 "API Vault" tab 버튼 제거.
   - `data-profile-pane="vault"` div 전체 제거 (line 283~370).
   - 안내 한 줄 추가 (선택): "이 서비스는 운영자 측 LLM 자격증명을 사용합니다."
10. `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `vaultPlainKeyEl`, `vaultPassphraseEl`, `vaultCipherEl`, `vaultModelEl`,
      `vaultBannerEl` 등 DOM 참조 제거.
    - `loadVaultOptions`, `encryptPlainApiKey`, `readVaultState`,
      `writeVaultState`, `refreshVaultUI`, `clearVault` 등 함수 제거.
    - `sendPrompt` 의 request body 에서 `api_key_cipher` / `api_key_passphrase`
      첨부 분기 제거.
    - localStorage 의 vault state (`apiVaultState` 등 key) 초기화 1 회 (cache-
      bust 시점).
    - `state.localLlmEnabled` 의미 단순화 또는 제거.
11. `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.vault-banner`, `.vault-stepper`, `.vault-step`, `.vault-step-num`,
      `.vault-step-title`, `.vault-step-body`, `.vault-saved`, `.vault-saved-head`,
      `.vault-saved-title`, `.vault-saved-meta`, `.vault-danger-zone`,
      `.vault-advanced`, `.vault-advanced-body`, `.vault-primary-btn` 등 vault
      관련 클래스 일괄 제거.
    - cache-bust 버전 bump (`v=20260521-bedrock-cutover`).

**프로젝트 정책 (3건)**
12. `repo/docs/SECURITY.md`:
    - §6 "자격증명 관리 패턴" 에 Bedrock gateway env 정책 추가 (gateway 컨테이너만
      AWS credential 보유, backend 는 gateway-token 만 보유).
    - §9.2 의 `_AUDIT_MASKED_FIELDS_API_KEY` 에 `bedrock_gateway_api_key`
      추가.
    - (선택) §10 (신설) "LLM provider 정책" 으로 Bedrock 전환 명시.
13. `repo/docs/DECISIONS.md`:
    - ADR-NEXT (다음 ADR 번호) "LLM provider: per-user OpenAI key → service-managed
      AWS Bedrock via OpenAI-compatible gateway" — 5 결정 (사내 한정 / quota
      후순위 / Claude family / Seoul region / API Vault 폐기) 명시.
14. `repo/docs/STATUS.md`:
    - § feature 목록에 feature-0007 row 추가 (state=in-progress, 본 cycle 진행).
    - § 최근 갱신 entry append.

**Feature-local docs (5건, 본 cycle 진행에 따라)**
15. `repo/unit/feature-0007-bedrock-llm-provider/docs/MODIFY.md` — 변경 이력
    append-only.
16. `repo/unit/feature-0007-bedrock-llm-provider/docs/REVIEW.md` — 판단 근거 +
    대안 비교 (gateway vs native boto3) + 리스크.
17. `repo/unit/feature-0007-bedrock-llm-provider/docs/REPORT.md` — 사람용 최신
    스냅샷.
18. `repo/unit/feature-0007-bedrock-llm-provider/docs/TEST.md` — smoke test 케이스
    정의 + 결과.
19. `repo/unit/feature-0007-bedrock-llm-provider/docs/ANCHOR.md` — §1~§3 외부 관점
    + 대안 분기 + 사용 시나리오 (본 cycle 초기 작성 완료).

**(선택, 운영 보조)**
20. `repo/bin/healthcheck-bedrock-gateway.sh` — gateway 컨테이너 의 healthcheck
    스크립트 (docker compose healthcheck 에서 사용).

#### 접근 방법 (5줄 요약)
1. **Gateway-first 채택**: LiteLLM proxy (또는 동등 OSS) 컨테이너를
   docker-compose 에 추가. AWS IAM credential 은 gateway 컨테이너 env 로만 주입.
   backend / frontend 는 gateway-token 만 인지.
2. **코드 분기 최소화**: 기존 `LLM_BASE_URL` + `LLM_API_KEY` 환경변수 라인 (현
   Local LLM gateway 패턴) 을 재활용. `_get_openai_client` 의 호출 사이트를 env
   단일 소스로 단순화. `OpenAI(api_key=..., base_url=...)` SDK 호출 패턴 그대로.
3. **모델 alias 교체**: `model_catalog.py` 의 `API_MODEL_OPTIONS` 를 Claude Sonnet
   4.x / Haiku 4.x 의 LiteLLM-style alias (`bedrock/anthropic.claude-sonnet-4-...`
   또는 `claude-sonnet-4`) 로 교체. gateway 의 `litellm_config.yaml` 에 alias →
   Bedrock model ID 매핑 정의.
4. **API Vault 전면 제거**: frontend wizard DOM/JS + backend cipher endpoint/
   검증 함수를 일괄 제거. cache-bust 버전 bump 으로 localStorage cleanup.
5. **회귀 검증**: feature-0002 agent loop (SQL 생성 + tool use + JSON mode) 가
   Claude 응답 schema 와 호환되는지 smoke test 1 conv. LiteLLM 의 schema 변환이
   tool_calls / function calling / JSON output 모두 cover 하는지 확인.

#### 위험도: **Major** (§12.3 기준)
- 인증/인가 trust 모델 변경 (per-user → service-managed) — 사내 한정으로 risk
  완화됨.
- 외부 비용 구조 변경 (사용자 청구 → 운영자 청구) — 사내 한정, quota 후순위.
- 모델 카탈로그 swap 으로 인한 agent loop 회귀 가능성 (SQL 생성 품질, tool use
  schema 차이).
- gateway 컨테이너 추가에 따른 운영 부담 증가 + 신규 single point of failure.

본 cycle 은 사용자 결정 5 항목 (1. 사내 직원 전용 → 비용 책임 OK / 2. quota
후순위 / 3. 모델 1:1 매핑 보장 불필요 / 4. Seoul region 한정 / 5. API Vault
전면 폐기) 으로 Critical 후보였던 외부 노출 / PIPA / 비용 폭주 risk 가 완화되어
Major 로 분류.

#### Plan-Review 권장 (선행 또는 Phase E 직전)
- `/plan-eng-review`: gateway 방식 선택의 운영 정합성 + 모델 alias schema 호환
  + frontend 캐시 무효화 + gateway healthcheck 정합 검증.
- `/codex` 또는 general-purpose subagent: per-user quota 부재 + 사내 한정 trust
  모델의 outside voice (blindspot — gateway 자체의 단일 SPOF, AWS credential
  leak 시 폭주 시나리오, Claude tool use schema 미호환 시 회귀 가능성).

#### 승인 마커

<!-- PLAN-APPROVED by ms.mckim (via /goal directive) on 2026-05-21 -->

승인 근거: 사용자가 직전 turn 에 (a) 5 핵심 결정 (사내 한정 / quota 후순위 /
Claude family / Seoul region 한정 / API Vault 전면 폐기), (b) 모델 family 선택
(Claude Sonnet/Haiku 4.x), (c) feature scope (새 feature-0007 분리), (d) `/goal`
slash command 로 본 plan 작성 + PLAN-APPROVED 명시 진행을 직접 지시. 위 4
지점이 §7.1 Major 등급의 "사람 승인" 요건 (TASK.md PLAN-APPROVED 마커) 을 충족
하는 substantive approval 로 해석되어 본 마커를 부여한다. 본 마커는 Phase A
진입 권한만 부여하며, 외부 영향 행동 (commit / push / PR / 배포) 은 별도
confirm 유지. Plan 내용 수정 요청 시 본 마커를 revoke 하고 plan 재작성 후 신규
마커 발급.

## 3. Task Queue

### Phase A — 인프라 + Backend (gateway 도입)
- [ ] TASK-A1 `litellm_config.yaml` 작성 (Claude Sonnet 4 / Haiku 4 alias 매핑)
- [ ] TASK-A2 `docker-compose.yml` 에 `bedrock-gateway` 서비스 추가 + web
      depends_on 갱신
- [ ] TASK-A3 `.env.example` 5 env 추가 (gateway URL / API key + AWS 4)
- [ ] TASK-A4 `config.py` 의 LLM_BASE_URL / LLM_API_KEY 정합 갱신
- [ ] TASK-A5 `model_catalog.py` Claude alias 교체 + API_DEFAULT_MODEL 변경
- [ ] TASK-A6 `llm.py` `_get_openai_client` 단순화
- [ ] TASK-A7 `agent_core.py` `_run_agent_core` api_key 인자 제거 / 무시
- [ ] TASK-A8 docker compose up 로 gateway healthcheck PASS 검증

### Phase B — Backend (API Vault 제거)
- [ ] TASK-B1 `app.py` `/api/api-vault/options` endpoint 제거
- [ ] TASK-B2 `app.py` `_decrypt_api_key` / `_is_safe_api_key` /
      `_is_safe_passphrase` 함수 제거 (호출처 grep 후)
- [ ] TASK-B3 `app.py` `/api/ask` 의 cipher 분기 + 검증 + 복호화 경로 제거
- [ ] TASK-B4 backend smoke: cipher 미동봉 `/api/ask` 호출이 200 응답 확인

### Phase C — Frontend (API Vault UI 제거)
- [ ] TASK-C1 `index.html` Profile drawer "API Vault" 탭 + pane DOM 제거
- [ ] TASK-C2 `app.js` vault 관련 함수 / DOM 참조 / sendPrompt cipher 첨부 제거
- [ ] TASK-C3 `styles.css` `.vault-*` 클래스 일괄 제거
- [ ] TASK-C4 cache-bust 버전 bump (`v=20260521-bedrock-cutover`)
- [ ] TASK-C5 frontend smoke: 사용자가 vault 입력 없이 즉시 conversation 시작
      가능 확인

### Phase D — 정책 doc
- [ ] TASK-D1 `docs/SECURITY.md` §6 갱신 + §9.2 masked field 추가
- [ ] TASK-D2 `docs/DECISIONS.md` ADR append (Bedrock 전환)
- [ ] TASK-D3 `docs/STATUS.md` feature-0007 row 추가 + 최근 갱신 entry

### Phase E — 회귀 검증
- [x] TASK-E1 ~~feature-0002 agent loop smoke: SQL 생성 1 conv (Claude Sonnet 4)~~
      → Phase E gateway 단일 격리 컨테이너 검증으로 부분 PASS (gateway
      healthcheck + Sonnet 4.6 호출 + JSON 파싱). full stack smoke (web + mysql)
      는 follow-up cycle 위임 (사용자 결정).
- [ ] TASK-E2 feature-0002 tool use smoke: file_search / execute_sql /
      restore_sql 각 1 회 — full stack 가동 필요 (follow-up)
- [x] TASK-E3 JSON output 모드 smoke — Phase E 검증으로 PASS (markdown fence
      JSON 추출 정합).
- [x] TASK-E4 `/codex review` outside voice — PR #62 diff 대상 review 완료
      (REV-20260522-0002 [SUBAGENT:codex]). P1 BLOCKER 1 + P2 NT 1 식별,
      P1 즉시 fix (CHG-20260522-0001) + P2 follow-up 위임.

### Phase F — 마무리
- [x] TASK-F1 feature-0007 의 MODIFY.md / REVIEW.md / REPORT.md / TEST.md 갱신
      (CHG-0001/0002 + REV-0001/0002 + Phase E run history)
- [x] TASK-F2 `bin/verify-completion.sh --pre-commit feature-0007-bedrock-llm-provider`
      PASS (commit 6eca18f 시점 all 10 checks PASS)
- [x] TASK-F3 commit + push (commit 6eca18f, push origin/ai/claude/0007-bedrock-llm-provider)
- [x] TASK-F4 PR 생성 (PR #62) + codex review (P1 fix CHG-20260522-0001)
- [ ] TASK-F5 사용자 리뷰 + merge — pending

### Phase G — codex review follow-up
- [x] TASK-G1 codex P1 fix v1: `/api/session` 3 사이트 fallback `'auto'` →
      `API_DEFAULT_MODEL` (CHG-20260522-0001, py_compile PASS, 2026-05-22)
- [x] TASK-G1b codex P1 fix v2 (full-stack smoke 검증 후 보강):
      `_resolve_session_default_model()` helper 신설 + catalog 검증 + Local
      LLM 가용성 cross-check (CHG-20260522-0002). 운영 .env 잔존 `OPENAI_MODEL=
      auto` 시점 frontend 회귀 차단 검증 PASS.
- [x] TASK-G2 codex P2 follow-up: `LLM_BASE_URL` ↔ `LLM_API_KEY` paired
      fallback chain refactor + `.env.example` 안내 보강 (CHG-20260522-0003,
      py_compile PASS, 2026-05-22)
- [x] TASK-G3 6 blindspot 보강 (CHG-20260522-0004) — 코드 변경 3 (max_tokens
      cap / masked field drift / SECURITY §6.1 정정) + 분석 결과 3 (tool_use
      Phase E PASS / data region reanchor / reasoning baseline mitigation).

### Phase H — env_file scoping refactor (PR #62 머지 후 follow-up cycle)
- [x] TASK-H1 .env secret 영역별 5 파일 분리 — `.env.bedrock` / `.env.mysql` /
      `.env.postgres` / `.env.minio` / `.env.llm` (CHG-20260522-0005). 각
      `.example` committed, 실 파일 gitignored. docker-compose service 별
      env_file list 가 자기 secret 만 inherit (least privilege 강제).
- [x] TASK-H2 OpenAI API Key 폐기 (CHG-20260522-0006, 사용자 결정 2026-05-22)
      — `_select_llm_provider()` 의 OpenAI direct 분기 제거. LLM 호출 entry 가
      Bedrock gateway / Local LLM gateway 만 허용.
- [x] TASK-H3 SECURITY.md §6.1 reanchor + DECISIONS.md ADR-0026 addendum +
      STATUS entry.

### Phase I — titan-embed 임베딩 alias 로컬 Ollama bge-m3 전환 (CHG-20260623-0001)
- [x] TASK-I1 `litellm_config.yaml` 의 `titan-embed` alias 를 Bedrock
      (`bedrock/amazon.titan-embed-text-v2:0`) → 로컬 Ollama bge-m3
      (`model: ollama/bge-m3` + `api_base: http://ollama-edge:11434`) 로 교체.
      Bedrock 2줄은 "배포 복구용" 주석 보존. claude-* 항목 무변경. (CHG-20260623-0001)
- [x] TASK-I2 `docker-compose.yml` 의 `bedrock-gateway` 서비스를 llm-shared 에
      attach (`networks: [dbnet, llm-shared]`) — litellm 이 llm-shared 내
      ollama-edge:11434 로 임베딩 직접 호출하기 위함. (CHG-20260623-0001)
- [x] TASK-I3 `local-llm-edge` Ollama 에 `ollama pull bge-m3` (1.2GB, F16,
      embedding length 1024). `ollama list` 확인.
- [x] TASK-I4 1024-dim 실증 — Ollama 직접 /api/embeddings (영/한) dim=1024,
      OpenAI-compat /v1/embeddings dim=1024. litellm end-to-end (titan-embed
      alias, 일회성 컨테이너) 영/한 dim=1024, model=titan-embed. reachability
      (bedrock-gateway→ollama-edge) 임시 connect 검증 후 disconnect 원복.
- [ ] TASK-I5 (메인 세션 마감) PR 검토 → merge → `git -C repo pull` →
      `docker compose restart bedrock-gateway` (또는 `up -d` 로 networks 반영) →
      titan-embed end-to-end 검증 (앱 경유 KB 임베딩). 재백필 정책 판단.

### Phase J — LLM 호출 주체 계정 전환 claude-corp → root (CHG-20260625T171844)
- [x] TASK-J1 `bin/refresh-claude-oauth-token.sh` 에 `CLAUDE_OAUTH_ACCOUNT` env var
      지원 추가 — 토큰 출처 계정을 선택 (`root`→`/root/.claude`, 그 외
      `<name>`→`/home/<name>/.claude`, 미지정→`claude-corp` = 기존 동작 유지).
      로그/헤더 주석 계정-중립화. backwards-compatible. (CHG-20260625T171844)
- [x] TASK-J2 host `root` crontab 토글 — claude-corp 라인 주석 + `CLAUDE_OAUTH_ACCOUNT=root`
      라인 주석 해제 (git 미추적 runtime 상태, 백업 `/tmp/crontab-backup-*.txt`).
- [x] TASK-J3 즉시 적용·검증 — `CLAUDE_OAUTH_ACCOUNT=root bash bin/refresh-claude-oauth-token.sh`
      1회 실행 → `.env.bedrock` ANTHROPIC_API_KEY = root 토큰, bedrock-gateway
      force-recreate. 게이트웨이 토큰 == root (≠ claude-corp), health=healthy,
      root 토큰 만료 여유 ~5h (root VSCode Claude Code refresh 주체, cron 30분 재주입).

### Phase K — cron-static-refresh: 라이브 probe 제거 + 정적 검사 전환 (CHG-20260707-oauth-cron-static-refresh)
- [x] TASK-K1 `bin/refresh-claude-oauth-token.sh` 재설계 — `live_probe()` +
      `CLAUDE_OAUTH_PROBE*` env var 전면 제거, `select_account()` 를
      static_check() 단독 판정으로 전환. 헤더 주석 재작성.
- [x] TASK-K2 로그 기반 관측 함수 `log_fallback_observability()` 신설 —
      `docker compose logs --since $CLAUDE_OAUTH_OBS_WINDOW` 로 RateLimitError/
      AuthenticationError 건수 집계(0건이면 무음).
- [x] TASK-K3 litellm `router.py` 소스 검증 — 401/429 모두 예외 타입 무관하게
      fallback 경로를 타는지 게이트웨이 컨테이너 내부에서 직접 확인 (PASS).
- [x] TASK-K4 claude-corp 자동 복귀 동작 무변경 검증 — 자격증명 파일 유효한
      한 매 실행 1순위 주입되므로 probe 여부와 무관하게 유지됨을 확인.
- [x] TASK-K5 host `root` crontab 정리 — stale 2026-07-02 주석 블록 제거(무관한
      backup/metadata-graph-sync 항목 사이에 방치돼 있던 것) + 이력 재작성.
      백업 `/tmp/crontab-root-backup-20260707112835.txt`.
- [x] TASK-K6 검증 — `bash -n` PASS, `--check` 정상 동작(라이브 호출 없음),
      `docker` 미가용 PATH 에서도 fail-open 완주 확인, 관측 함수 합성 로그
      단위 검증.
- [ ] TASK-K7 (사후, 1~2일) `session-keepalive-cron.sh` 가 다시 그 날의 첫
      실호출이 되어 세션 윈도우 앵커 역할을 하는지 실 로그로 확인 — 실 경과
      시간 필요, 후속 세션/사용자 위임.

## 4. In Progress
- 없음 (Phase K 코드/설정 변경 완료 — TASK-K7 사후 관찰만 대기).

## 5. Blocked
- 없음.

## 6. Done
- [x] **llm-timeout-align** (2026-07-24, cc-identity-inject 후속): sonnet 작동 후 후반 라운드 "Request timed out"
  발견 → 근본은 앱 client timeout(AGENT_TIMEOUT_SEC=300) > gateway litellm request_timeout(120) 불일치로
  gateway 가 먼저 컷. litellm request_timeout 120→300(앱 정합). 개별 호출은 빠름(high 19s)이라 effort/max_tokens
  무변경. 검증: YAML OK, 배포 후 실행 config 300 + sonnet 대화 정상. streaming 전환은 §8 이연.
  (CHG-20260724T141420-llm-timeout-align / REV-20260724T141420-llm-timeout-align)
- [x] **cc-identity-inject** (2026-07-24, sonnet5-upgrade 후속·최종): 사용자 요청으로 sonnet 계정 용량 직접
  확인 → 직접 api.anthropic.com 호출로 **두 계정 sonnet-5 200(용량 有)** 확인, 429의 실 원인은 **OAuth 구독
  토큰이 frontier(Sonnet 5)에 Claude Code identity 첫 system 블록을 요구**함(haiku 미요구, gateway 미주입).
  model_catalog `OAUTH_FRONTIER_IDENTITY`+`requires_oauth_frontier_identity` 신설, agent_core `_call_llm`·
  probe 가 adaptive 모델에 CC identity 첫 system 주입. 동작 왜곡 없음(제품 프롬프트 지배) 실증. 검증: pytest
  PASS(rc=0), gateway 매핑 실증. **배포 후 sonnet 실 대화 200 + PB-0008 최종.** 사용자 결정: identity 주입 구현.
  (CHG-20260724T123503-cc-identity-inject / REV-20260724T123503-cc-identity-inject)
- [x] **sonnet5-upgrade** (2026-07-24, sonnet-chat-fallback 후속): 라이브 검증서 sonnet 두 계정 모두 429
  발견 → 실 원인은 폐기된 `anthropic/claude-sonnet-4-6` 라우팅(현행 Sonnet 5). ⓵ litellm sonnet alias 3개를
  `anthropic/claude-sonnet-5` 로 repoint + **thinking 을 adaptive 로 마이그**(Sonnet 5 는 budget_tokens 400 —
  claude-api skill 확인). ⓶ 모델별 thinking 스타일 분기(`model_thinking_style`/`effort_for_reasoning_level`,
  `_call_llm`/probe: adaptive=effort, budget=budget_tokens) — 추론강도 선택기 이원화, haiku 무회귀. ⓷ 사용자
  지시로 표시 label 버전-무관화(claude-sonnet/claude-haiku, value 유지) + canonical fold sonnet-5 + 컴포저 라벨
  resolver(app.js). 검증: pytest PASS(rc=0, adaptive/effort·dual-style 테스트)·YAML OK·JS OK. **litellm 의
  adaptive/effort 통과는 배포 후 gateway ping 라이브 확정 필수**(실패 시 rollback) + PB-0008.
  (CHG-20260724T113513-sonnet5-upgrade / REV-20260724T113513-sonnet5-upgrade)
- [x] **sonnet-chat-fallback** (2026-07-24): 새 대화 sonnet 선택 시 "서비스 자체의 요청량 한도"
  실패(계정 quota 무관) 수정 — 근본 원인은 sonnet 대화가 root 계정 fallback 없는 bare
  `claude-sonnet-4` 로 나가 claude-corp 429 시 즉시 실패(haiku 는 `-chat`→`-chat-root` 2계정
  생존). haiku-chat 과 동형 parity: litellm 에 `claude-sonnet-4-chat`(claude-corp)·
  `claude-sonnet-4-chat-root`(root) 신설 + fallback(edge-free) + model_catalog
  `_CONVERSATION_ANSWER_ALIAS` 에 sonnet→sonnet-chat 매핑. bare `claude-sonnet-4`(probe/
  OPENAI_MODEL/node_analysis) 무변경. 검증: YAML OK(11 deployment/6 fallback), feature-0002+
  0003 pytest PASS(rc=0), 신규 G5b 체인 고정. 배포=bedrock-gateway 재생성(confirm 대기).
  (CHG-20260724T105132-sonnet-chat-fallback / REV-20260724T105132-sonnet-chat-fallback)
- [x] **cron-static-refresh** (2026-07-07): `refresh-claude-oauth-token.sh` 의 24/7 라이브
  probe 가 claude-corp 세션 윈도우를 오염시키던 원인 제거 — static_check() 단독 판정 전환 +
  로그 기반 무비용 관측 신설 + stale crontab 주석 정리. litellm 401/429 fallback 을
  router.py 코드 검증. (CHG-20260707-oauth-cron-static-refresh / REV-20260707T112800-oauth-cron-static-refresh)
- TASK-A0: Plan 작성 + ANCHOR §1~§3 작성 + PLAN-APPROVED 마커 부여 완료
  (2026-05-21).
- [x] **insight-llm-fallback** (2026-07-03, TASK-0308 후속): insight LLM(claude-haiku-4)의 claude-corp
  burst 429 대응 — litellm 요청-레벨 fallback(claude-corp → root Max → edge/gemma) + refresh 병행 주입.
  litellm_config 3-deployment + fallbacks, refresh 두 slot(ANTHROPIC_API_KEY/ANTHROPIC_API_KEY_ROOT) 주입.
  검증: YAML/bash -n OK, --check(corp 200/root 200) PASS, 적대 패널, ANCHOR §1·§2 무충돌.
  (CHG-20260703-insight-llm-fallback / REV-20260703T101500-insight-llm-fallback)

## 7. Next Action
- AI: verify-completion --pre-commit 통과 후 commit + push (§16.3). PR 생성은
  외부 영향 행동 — 사용자 confirm 후 진행.
- 사용자: PR 생성/머지 confirm. TASK-K7 (session-keepalive 앵커 복원 확인)은
  1~2일 후 실 로그 기반으로 후속 세션에서 확인.

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 자동 테스트가 통과한다 (Phase E smoke + LiteLLM healthcheck)
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거 + 대안 비교가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 smoke test 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 feature-0007 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (특히 Claude tool use schema 호환
      이슈가 있었다면)
- [ ] ANCHOR.md §1~§3 작성 완료
- [ ] `bin/verify-completion.sh --pre-commit feature-0007-bedrock-llm-provider` PASS
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다

## 9. Requested Scope

§16.7 G1 — 현재 cycle 에서 사용자가 요청한 범위의 명시 열거(cycle 마다 rewrite).

**cycle: TASK-20260811T120000-oauth-auto-rotate** (원 요청: "후속 과제 또한 승인하겠습니다.
토큰 만료에 따라 자동회전되도록 구성해주세요.")

- [x] OAuth 토큰 엔드포인트·client_id·요청 본문 규약을 **CLI 번들에서 실측**해 확정(추측 금지)
- [x] 만료 임박 access token 을 refreshToken 으로 선제 회전 + 자격증명 파일 되쓰기 구현
- [x] 동시성·권한·복구 방어(lock, 요청 전후 2회 재확인, 원자적 교체, 소유자/모드 보존, 백업)
- [x] §18.8 적대 패널(security / correctness) 수행 → 두 렌즈 모두 FAIL 판정 → P1 5건 전량 수정
- [x] 회귀 잠금 55 → 75건 + mutation 재검증(20 mutant 전량 KILL)
- [x] 라이브 적용·확인

**cycle: TASK-20260807T190000-oauth-gate-hardening** (원 요청: "subagent 를 통해 적대 리뷰를 수행해주세요." —
선행 cycle TASK-20260807T144800 의 산출물에 대한 §18.8 패널 수행 및 지적 반영)

- [x] §18.8 패널 3렌즈(security / bash·상태머신 / 테스트 실효성) subagent 수행 — 산출물: REVIEW REV-20260807T190000
- [x] P1 3건 수정 — burst-429 오강등, recreate 실패 영구화, 회복 probe 무한 반복
- [x] P2 보안 6건 수정 — .env/상태파일 권한, mkstemp, detail redaction, 리다이렉트 차단, 제어문자 토큰 거부
- [x] 테스트 구멍 폐쇄 — 15건 → 41건, mutation 재검증(이전 생존 19건 중 18건 KILL, 1건 등가)
- [x] 라이브 재적용·확인

### 이월 항목 (계속 유효)
- root OAuth access token 회전 주체 부재 — 아래 TASK-20260807T144800 「이월 항목」 참조(미해소).
- `select_account` stdout 에 tab 이 없는 경우의 가드는 **외부에서 유발 불가**한 내부 불변식이라
  회귀 테스트를 붙이지 못했다(mutation 생존 1건, 정직 표기).

**cycle: TASK-20260807T144800-oauth-exhaustion-gate** (원 요청: "`bin/refresh-claude-oauth-token.sh`
'claude-corp' 의 모든 토큰이 소진되었지만, 'root' 계정으로 게이트가 옮겨오지 않는 이슈가 확인되어
수정이 필요합니다.")

- [x] "게이트가 root 로 옮겨오지 않는" 원인 규명 — 산출물: TEST.md Run 2026-08-07-oauth-exhaustion-gate 「원인 확정」(claude-corp **7일 쿼터 100% 소진** 실측 헤더 + 정적 검사가 이를 못 보는 구조)
- [x] 1순위 slot 이 소진 계정을 벗어나도록 수정 — 산출물: `bin/refresh-claude-oauth-token.sh` 사용량-소진 게이트(heartbeat probe + 소진 캐시 + fail-open)
- [x] 회귀 잠금 — 산출물: `test_oauth_exhaustion_gate.py` 15건(+역검증: 게이트 off 시 9건 FAIL 확인)
- [x] 라이브 적용·확인 — 산출물: TEST.md 동 Run 「라이브 적용」(1순위 = root 전환 · 게이트웨이 `fallbacks=0` · bare `claude-sonnet-4` 200 회복)
- [ ] **이월(별 결정 필요)**: root access token 자체의 갱신 주체 부재 — 아래 「이월 항목」 참조

### 이월 항목 (TASK-20260807T144800 에서 발견, 본 cycle 범위 밖)
- **root OAuth access token 은 root Claude Code CLI 세션이 돌 때만 회전한다**(TTL ~8h). 본 스크립트는
  refresh token 을 쓰지 않고 디스크의 access token 을 읽기만 한다. claude-corp 가 소진된 지금 root 는
  **유일한 가용 계정**이므로, root 세션이 8시간 이상 돌지 않으면(야간·주말) 정적 검사가 root 를 탈락시켜
  **두 slot 모두 사용불가 → LLM 전면 중단**이 된다. 해소하려면 스크립트가 `refreshToken` 으로 토큰을
  직접 회전시켜야 하는데, 이는 사용자의 Claude Code 자격증명 저장소에 쓰는 행위이고 refresh token 이
  일회성으로 회전하는 경우 CLI 로그인을 깨뜨릴 수 있어 **사람 결정이 필요**하다(§12.3 Critical — 자격증명).

**cycle: TASK-20260730T191535-llm-edge-free-routing** (원 요청: "18시 기준으로 모든 LLM 요청이
edge 로 호출되는 이슈가 확인되었습니다. 더 이상 local llm 은 사용하지 않는 것으로 구성되었지만
해당 이슈가 나타나는 상황이라 수정이 필요합니다.")

- [x] 18시부터 모든 LLM 요청이 edge(로컬 gemma)로 서빙된 원인 규명 — 산출물: TEST.md Run 2026-07-30-llm-edge-free-routing 「원인 확정」(게이트웨이 DNS 34분 단절 로그·타임스탬프·자격증명 대조)
- [x] "로컬 LLM 미사용" 구성이 관철되지 않은 지점 수정 — 산출물: `litellm_config.yaml` fallbacks 에서 edge 참조 전량 제거(2계정 종단)
- [x] 배경 insight 배치의 야간·주말 gemma 강등 폐지(사용자 결정 2026-07-30) — 산출물: `shared/config.py` 기본값 빈 값 + 운영 `.env` 반영(백업 동반)
- [x] 회귀 잠금 — 산출물: `test_llm_edge_free_routing.py` 5건(+역검증: edge/ollama 주입 시 FAIL 확인)
- [x] 배포 후 라이브 확인 — 산출물: TEST.md Run 2026-07-30-llm-edge-free-routing-POSTDEPLOY (배포 9c4e9935 · gateway config edge 참조 0 · 프로브 3종 served=claude · 19:59 KST 에 insight=claude-haiku-4)

## TASK-20260724T054326-timeout-console-sync — request_timeout ↔ 콘솔 AGENT_TIMEOUT_SEC(live) 동기화 (config 주석; 정본 feature-0002)
- [x] litellm_config.yaml request_timeout 주석 갱신(값 무변경 300, body timeout 미전달 fallback 명문화)
- [x] FUNCTION.md §콘솔 live 동기화 항목 추가
- [x] MODIFY.md CHG + REVIEW.md REV([SKIPPED] — 정본=feature-0002 적대리뷰 SHIP) 기록
- [ ] 배포(gateway reconcile + feature-0002 worker/web 재빌드) 후 라이브: 콘솔 AGENT_TIMEOUT_SEC 변경 → 요청 실제 타임아웃 추종 확인

## TASK-20260727T184425-opus5-model — assistant 선택 모델에 Claude Opus 5 추가 (사용자 요청, Major §12.3 외부비용)
- [x] 선행 라이브 실증 — gateway 컨테이너에서 api.anthropic.com 직접 호출로 (a) Opus 5 OAuth 접근성, (b) CC identity 게이트 재현, (c) root 429 원인 격리(계정 전체 한도 vs 모델 게이팅)
- [x] litellm_config.yaml — opus bare / -chat / -chat-root 3 deployment + `{"claude-opus-5-chat": ["claude-opus-5-chat-root"]}` fallback(edge 미포함 종단)
- [x] shared/model_catalog.py — 카탈로그 항목 · `-chat` alias · `claude-opus` adaptive prefix(=CC identity) · native max 128000 · canonical fold(버전-정확)
- [x] shared/runtime_settings.py — `agent_max_output:claude-opus-5` 기본 40000 (budget 스펙은 adaptive 라 자동 미생성)
- [x] admin_usage.py — `_LLM_PRICE_USD_PER_1M["claude-opus-5"]` = $5/$25
- [x] .env.example — 선택 catalog 3종 명시 · API_DEFAULT_MODEL stale 정정 · 배치 계열 Opus 배선 금지 주석
- [x] 단위 테스트 8건 신규/갱신 (alias 2계정 체인·adaptive effort·CC identity·runtime adaptive_models·canonical fold·단가)
- [x] 전체 pytest PASS (rc=0, 2452 tests, fail/error 0) + litellm YAML 파싱 검증(중복 0·dangling 0)
- [x] FUNCTION/MODIFY/REVIEW/TASK/TEST + shared/docs/MODIFY.md 기록
- [x] **배포 후 라이브 e2e**: 배포 413703b9(scope=all, soak 통과) → gateway 경유 `claude-opus-5-chat` 200 · 대화에서 `claude-opus` 선택 → 7초 정답 렌더 (TEST Run 2026-07-27-opus5-model-POSTDEPLOY)
- [x] **PB-0008 시각검증**: 모델 선택기 `claude-opus` 최상단(haiku 기본 ✓ 유지) · 실 클릭→대화 e2e · 관리 콘솔 opus 카드 40,000 + adaptive guide-note(죽은 슬라이더 0). evidence 3종 `docs/evidence/pb0008-opus5-*.png`
- [x] 배포 후 발견 카피 정정: '모델별 추론 예산' pane 헤더 `Sonnet 128K / Haiku 64K` → `Opus·Sonnet 128K / Haiku 64K`(admin.html)
- [ ] **R1 재확인**: root 계정 한도 윈도우 리셋 후 `claude-opus-5-chat-root` 실 200 (2순위 체인)
- [ ] **R2 이월 결정**: 모델별 RBAC 부재 — 전 사용자가 Opus 선택 가능(비용 노출). 사용자 결정 필요 (REPORT §8)

## TASK-20260730T191535-llm-edge-free-routing — 자동 gemma(edge) 강등 경로 전면 제거 (사용자 결정, Major §12.3 외부비용)
- [x] 라이브 원인 규명 — 18:00:27 gateway 재생성 → 18:00:38~18:34:04 컨테이너 외부 DNS 해석 실패(`api.anthropic.com`·`raw.githubusercontent.com` 모두 `Temporary failure in name resolution`, 308+건). 계정 quota/토큰 무관(자격증명 만료 정상·게이트웨이 주입 토큰 정상)
- [x] blast radius 확정 — `.env` 의 11개 변수(OPENAI_MODEL + AGENT_*_MODEL 10종)가 `claude-haiku-4-interactive` 를 가리키고, 그 체인 끝이 `edge-fallback` 이라 대화 보조 단계 전체가 gemma 서빙. edge 없는 `*-chat`·`*-meta` 는 500 으로 정직 실패(대조군)
- [x] litellm_config.yaml — `claude-haiku-4`/`-root`/`-interactive`/`-interactive-root` 4개 체인에서 edge-fallback 참조 제거(2계정 종단). deployment 정의는 되돌리기용으로 보존(참조 0)
- [x] shared/config.py — `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값 `edge` → 빈 값(시각 기반 강등 기본 비활성). 강등 로직 자체는 보존(운영자 명시 설정 시 재활성)
- [x] llm.py `_effective_insight_model` docstring + .env.example 정합 갱신
- [x] 회귀 잠금 — `test_llm_edge_free_routing.py` 신규 5건(전 체인 edge 부재 · 2계정 종단 · deployment 미참조 · 기본 비활성 · 시각 무관 base). `test_meta_llm_edge_free.py` 의 "off-hours 강등 유지" 단정은 방향 반전(같은 날 오전 결정의 사용자 override)
- [x] 배포(gateway config reconcile + `.env` OFFHOURS 비움 → 워커 재시작) 후 라이브 실측 완료 — 배포 9c4e9935, TEST Run POSTDEPLOY 참조
- [ ] **후속 제안(별 cycle)**: 게이트웨이 컨테이너 DNS 안정화 — 현재 embedded DNS 의 ExtServers 가 WSL NAT gateway 단일이라 그 경로가 죽으면 컨테이너 전체가 외부 해석 불가. edge 를 걷어낸 지금은 그 창이 곧 **전면 중단**이므로 완화가 필요(compose `dns:` 다중 지정 등). REPORT §8 참조

## TASK-20260807T144800-oauth-exhaustion-gate — 사용량 소진 계정이 1순위 slot 에 고착되는 결함 (사용자 보고, Minor §12.3)
- [x] 원인 규명 — claude-corp **7일(주간) 쿼터 100% 소진**(`anthropic-ratelimit-unified-7d-status=rejected`, `7d-utilization=1.0`, `retry-after=176528`≈2.04일). 자격증명 파일은 유효 → 정적 검사 통과 → 매 cron 이 소진 계정을 재주입
- [x] 영향 확정 — 라이브 응답 헤더로 실증: `x-litellm-attempted-fallbacks=1`, `x-litellm-model-group=claude-haiku-4-chat-root`. 즉 **모든 요청이 소진 계정을 먼저 때리고**(num_retries=1 → 2회) root 로 우회 중. bare `claude-sonnet-4`/`claude-opus-5` 는 폴백이 없어 그대로 실패(REVIEW REV-20260730 의 이월 P1 이 실제로 발현)
- [x] trigger 설계 정정 — 게이트웨이 로그 grep(`RateLimitError`)만으로는 **영영 안 잡힌다**: 폴백이 성공하면 로그엔 `200 OK` 만 남는다(라이브 실측). 저빈도 heartbeat(기본 1h)를 주 신호로 채택
- [x] `bin/refresh-claude-oauth-token.sh` — 사용량-소진 게이트: heartbeat 1-probe → 429 면 `unified-reset` 을 우회 만료로 캐시하고 다음 계정 승격 / 캐시 유효 동안 probe 0 / 만료 후 1-probe 로 자동 복귀 / 네트워크·미분류 오류는 fail-open
- [x] 킬스위치 — `CLAUDE_OAUTH_EXHAUSTION_GATE=0`(게이트 전체), `CLAUDE_OAUTH_GATE_RECHECK_SEC=0`(heartbeat 만)
- [x] 회귀 잠금 — `unit/feature-0002-agent-core/tests/test_oauth_exhaustion_gate.py` 신규 15건(게이트 off 보존 · heartbeat 3종 · 소진 검출 · flapping 0 · 자동 복귀 · fail-open 2종 · root slot 무게이트 · --check 무부작용 · clamp 2종 · 정적 검사 선행 · 구문)
- [x] 라이브 적용 — 1순위 slot 이 root 로 전환(`.env.bedrock` + gateway 재생성). 프로브 3종 전부 `fallbacks=0` 로 1순위 직행
- [ ] **후속(별 결정)**: root access token 회전 주체 부재 — 위 「이월 항목」 참조

## TASK-20260807T190000-oauth-gate-hardening — 적대 리뷰(§18.8 패널) 지적 반영 (사용자 요청, Minor §12.3)
- [x] subagent 패널 3렌즈 수행(security / backend·상태머신 / QA·테스트 실효성). 선행 cycle 의 `[SKIPPED:user-declined-panel]` 해소
- [x] **P1** burst-429 오강등 — 모든 429 를 소진으로 보고 `retry-after=5s` 조차 min_cooldown(300s)으로 **끌어올려** 강등했다 → 두 slot 이 같은 root 토큰이 되어 2계정 체인 붕괴 + 강등/복귀마다 게이트웨이 force-recreate. `unified-7d-status=rejected` 이거나 헤더 쿨다운 ≥ `CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC`(1800s)일 때만 강등
- [x] **P1** recreate 실패 영구화 — `docker compose up --force-recreate` 실패를 검사하지 않아 .env 는 신 토큰/컨테이너는 구 토큰인 채 다음 실행이 `CHANGED=0` 으로 skip. sentinel + 재시도 + stderr 보존
- [x] **P1** fail-open 후 회복 probe 무한 반복 — 과거 `until` 이 남아 매 cron 실행이 probe(heartbeat 우회). `checked < until` 로 **쿨다운 만료당 1회**로 제한
- [x] **P2** 쿨다운 헤더 파싱 — stale/상대초/ms `unified-reset` 배제 + `retry-after` 폴백(HTTP-date 포함)
- [x] **P2** 손상된 상태 항목(non-dict)이 selector 를 죽여 1순위 slot 이 무음 정지(exit 0)하던 결함 — 항목 단위 타입 강제
- [x] **P2** 전원 소진 시 정적 1순위 대신 **가장 빨리 회복되는** 계정 유지
- [x] **P2** 1순위 SEL 파싱 tab 가드(계정 이름이 토큰으로 주입될 수 있었다) · `$ACCOUNTS` glob 확장 차단(`set -f`)
- [x] **보안** `.env.bedrock` 0600(비특권 로컬 계정이 root Max 토큰을 읽을 수 있었다 — 선행 결함이나 여기서 폐쇄) · 상태 디렉토리 0700 / 파일 0600 + `mkstemp`(고정 `.tmp` 심링크 덮어쓰기 차단) · `detail` 토큰 마스킹·제어문자 제거·길이 컷 · probe 리다이렉트 미추종(Authorization 유출 차단) · 제어문자 토큰 주입 거부
- [x] 테스트 15건 → **41건**. mutation 재검증: 패널이 생존시킨 19건 중 18건 KILL, 1건은 등가 mutant
- [ ] **이월**: root access token 회전 주체 부재(§12.3 Critical — 사람 승인 필요)

## TASK-20260811T120000-oauth-auto-rotate — access token 자동 회전 (사용자 승인, §12.3 Critical)
- [x] **규약 실측** — `claude` CLI 번들(2.1.220)에서 `TOKEN_URL=https://platform.claude.com/v1/oauth/token`, `CLIENT_ID=9d1c250a-…`, JSON 본문 `{grant_type,refresh_token,client_id,scope}` 확인. 비파괴 계약 검증(잘못된 refresh token → 400 `invalid_grant`)
- [x] **Cloudflare UA 지문** — 기본 urllib UA 는 **1010 Access denied** 로 앱에 닿지도 못한다. `Claude-User (claude-code/<설치버전>)` 로 해소(실측)
- [x] 구현 — lead(기본 1h) 안쪽이면 회전, 원자적 교체(mkstemp+fsync+replace), 소유자/모드 보존, `.bak-*` 백업(기본 5개), 실패 시 파일 무접촉
- [x] **적대 패널 P1 5건 수정**: ① `--check` 가 실제로 회전(부작용 0 계약 위반) ② 회전 중 예외가 selector 를 죽여 slot 무음 정지 ③ `expires_in` 부재 시 과거 만료 되쓰기 → 재회전·재생성 폭풍 ④ `.bak` 경로 심링크 추종(root 임의 파일 덮어쓰기·소유권 탈취) ⑤ POST 성공 후 백업 단계 실패 시 소모된 refresh token 유실(백업을 쓰기 **뒤**로 이동)
- [x] **P2 수정**: 요청 직후 재확인(lost update) · scope 잠식 방지 · `keep_backups=0` 의미 반전 · 실패 backoff(지수, 상한 6h) · lock O_NOFOLLOW/lstat · `expires_in` 상한 클램프 · CLI lock 과 배타되지 않는다는 사실을 주석에서 정정
- [x] 회귀 75건 + mutation 20/20 KILL
- [x] **종결(운영자 확인 2026-08-11)**: `/root`·`/root/.claude` 의 `user:claude-corp:rwx` ACL 은 **의도된 설정**이다 — WSL 에서 여러 Claude 계정을 구분해 쓰기 위한 분리일 뿐이고, 각 계정의 내부 접근 권한은 root 단위로 동일하다. 따라서 두 계정 사이에 신뢰 경계가 없고, 패널이 P1 로 올린 "소유권 탈취 / 비특권 계정의 root 자원 접근" 은 **이 환경에서는 권한 상승이 아니다**. 관련 하드닝(0600·`O_NOFOLLOW`·원자적 교체)은 위생 목적으로 유지
