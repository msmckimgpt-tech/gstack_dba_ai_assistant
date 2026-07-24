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

## TASK-20260724T054326-timeout-console-sync — request_timeout ↔ 콘솔 AGENT_TIMEOUT_SEC(live) 동기화 (config 주석; 정본 feature-0002)
- [x] litellm_config.yaml request_timeout 주석 갱신(값 무변경 300, body timeout 미전달 fallback 명문화)
- [x] FUNCTION.md §콘솔 live 동기화 항목 추가
- [x] MODIFY.md CHG + REVIEW.md REV([SKIPPED] — 정본=feature-0002 적대리뷰 SHIP) 기록
- [ ] 배포(gateway reconcile + feature-0002 worker/web 재빌드) 후 라이브: 콘솔 AGENT_TIMEOUT_SEC 변경 → 요청 실제 타임아웃 추종 확인
