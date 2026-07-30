---
doc_type: REVIEW
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260707T112800-oauth-cron-static-refresh [SKIPPED:config-ops-chore]
- Related Change: CHG-20260707-oauth-cron-static-refresh
- Trigger: 사용자 지시 — claude-corp 5시간 세션 윈도우가 24/7 cron 라이브 probe 로
  오염되는 문제의 근본 원인 제거.
- SKIP 근거 (§18.8 패널 면제): 변경 표면이 (1) `bin/refresh-claude-oauth-token.sh`
  내부 판정 로직(라이브 HTTP probe 제거 → 파일 기반 정적 검사만) + 로그 전용
  관측 함수 신설, (2) git 미추적 crontab 주석/설명 정리에 한정. auth/인가 ·
  네트워크 요청 표면 · 데이터 · 스키마 변화 없음 — 오히려 외부 API 호출 경로를
  제거해 표면이 줄었다. `.env.bedrock`/`ANTHROPIC_API_KEY*` 주입 대상·우선순위·
  병행 주입 정책은 CHG-20260703-insight-llm-fallback 에서 이미 검증된 그대로
  무변경.
- 실증 검증 (자체): `bash -n` PASS. `--check` 로 claude-corp/root 두 계정 정적
  검사 정상 선택 확인(라이브 호출 0건 — PATH 에서 `docker`/네트워크 도구를
  제거한 상태로도 정상 완주해 외부 호출 의존이 없음을 간접 확인). `docker`
  미가용 환경에서도 관측 함수가 script 를 abort 시키지 않음(fail-open) 확인.
  litellm 실제 소스(`router.py`) 를 게이트웨이 컨테이너 내부에서 직접 읽어
  401/429 fallback 경로가 예외 타입 무관하게 작동함을 코드 레벨로 확인(본
  REV 대상 코드 변경은 아니지만 probe 제거의 안전성 전제이므로 근거로 첨부).
- Human Approval Needed: no — 사용자 명시 지시(probe 제거 + 정적 검사 전환 +
  crontab 정리)로 본 변경 위임. 개발용 임시 스크립트(헤더에 명시, 정식 배포
  시 제거 예정) 범위 내 조정.

## REV-20260625T171844-llm-account-root [SKIPPED:config-ops-chore]
- Related Change: CHG-20260625T171844
- Trigger: 사용자 지시 운영 chore — LLM 호출 주체 계정 claude-corp → root 일시 전환.
- SKIP 근거 (§18.8 패널 면제): 변경 표면이 (1) `bin/refresh-claude-oauth-token.sh`
  의 `CLAUDE_OAUTH_ACCOUNT` env var → 로컬 credential 파일 **경로 선택** (case 분기,
  외부 입력 파싱 없음), (2) git 미추적 crontab 라인 토글 에 한정. auth/인가 로직 ·
  네트워크 · 데이터 · 스키마 표면 변화 0. 미지정 시 claude-corp 으로 기존 동작
  **완전 보존** (backwards-compatible). 비밀정보는 gitignored `.env.bedrock` 에만
  존재 (추적 산출물 0). 토큰 주입·검증 메커니즘은 CHG-20260623-0001 (REV-20260623-0001
  [SUBAGENT:backend] PASS) 에서 이미 검증된 경로와 동일하며 계정 주체만 상이.
- 실증 검증 (자체): 게이트웨이 토큰 끝6자 == root 토큰 (≠ claude-corp), `bedrock-gateway`
  health=healthy, root 토큰 만료 여유 ~5h. bash -n PASS + 계정 라우팅 단위 확인 3종.
- Human Approval Needed: no — 사용자 명시 지시로 본 전환 위임. ⚠ 개발용 임시.

## REV-20260521-0001
- Related Change: CHG-20260521-0001
- Reason: 사용자 결정 5 항목 (사내 직원 전용 → 비용 책임 운영자 부담 / per-user
  quota 후순위 / 모델 1:1 매핑 보장 X / Seoul region 한정 / API Vault 전면
  폐기) 에 따라 LLM provider trust 모델을 service-managed AWS Bedrock 으로
  전환. 사내 한정 운영에서 사용자별 OpenAI key 입력 wizard 가 진입 장벽이고
  trust 모델이 부적합 판단.
- Alternatives Considered:
  - **Alt-A: OpenAI-compatible gateway (LiteLLM proxy) 채택** — 본 cycle 의
    선택. 본 코드 베이스의 `OpenAI(api_key, base_url)` SDK 패턴 + Local LLM
    gateway 분기를 그대로 재사용 → 코드 변경 범위 최소.
  - **Alt-B: boto3 + bedrock-runtime native 직접 호출** — 폐기. Anthropic
    Messages API / tool use / JSON mode schema 분기 도입 + `llm.py` 의 모든
    호출 사이트에 provider abstraction wrapper 필요. 본 cycle 의 코드 변경
    범위 폭주. 운영 정상화 후 hotspot 만 native 마이그레이션은 별 cycle.
  - **Alt-C: API Vault 유지 + OpenAI 그대로** — 폐기. 사용자 결정.
  - **Alt-D: 하이브리드 (사용자 키 + 서비스 키 병존)** — 폐기. 사용자 결정.
  - **Alt-E: cross-region inference 허용** — 폐기. PIPA 잔류 통제 우선.
- Risks:
  - **gateway SPOF**: `bedrock-gateway` 컨테이너가 단일 장애 지점. web /
    agent / insight-worker 모두 502/503 cascading 위험. mitigation = restart
    policy + healthcheck 12 retry × 10s = 2 min recovery window.
  - **Claude tool use schema 비호환 가능성**: LiteLLM 이 OpenAI tool_calls
    ↔ Anthropic tool use 변환 책임. 변환 실패 시 agent loop 회귀. Phase E
    smoke test 로 확인 필요. 회귀 발견 시 LiteLLM 버전 pin / 변환 hook 커스텀
    / native boto3 hotspot 별 cycle 검토.
  - **AWS credential leak 시 비용 폭주**: per-user quota 부재 + 단일 service
    자격증명 → 자격증명 노출 시 운영자가 무한정 비용 부담. mitigation =
    IAM `bedrock:InvokeModel` 최소 권한 + Bedrock model access 제한 + AWS
    Cost Explorer 모니터링 + 별 cycle 의 per-user quota 도입.
  - **모델 ID drift**: AWS Bedrock 의 Claude versioned model ID (예:
    `-20250514-v1:0`) deprecate 가능. `litellm_config.yaml` 가 single
    source-of-truth — 운영자가 deprecation notice 모니터링 필요.
  - **모델 품질 회귀**: GPT-5.4 → Claude 4.x swap 으로 SQL 생성 / system
    prompt 호환 회귀 가능성. agent loop 의 `SYSTEM_PROMPT_SQL` 이 OpenAI
    JSON mode 가정 — Claude 의 JSON 출력 fidelity 확인 필요. 회귀 발견 시
    prompt 미세 조정 또는 모델 fallback (Sonnet ↔ Haiku).
  - **Frontend 캐시 cleanup**: 기존 사용자의 localStorage `v1:` cipher 가
    cache-bust 후 silent drop. 사용자가 자기 키 backup 안 한 경우 복구 불가
    (단 본 cycle 의 정책 = 사용자 키 폐기이므로 복구 불요).
  - **Local LLM gateway 분기 잔존**: 본 cycle 은 Local LLM (`auto` / `edge` /
    `core` / `code` 4 모델) 분기를 보존 — `LOCAL_LLM_API_BASE` 설정 시 활성.
    `is_local_llm_model()` 검사 패턴 유지. 운영자가 동시 활성화 시 router
    충돌 가능 — fallback chain (`BEDROCK_GATEWAY_*` 우선) 으로 mitigation.
- Open Questions:
  - **Claude 4.x 실 model ID**: `litellm_config.yaml` 의 model ID (예:
    `bedrock/anthropic.claude-sonnet-4-20250514-v1:0`) 가 추정값 — Seoul
    region 의 실 가용 model ID 를 AWS console 에서 사전 확인 필요. 미가용
    시 ID 갱신 + ADR-0022 보강.
  - **gateway healthcheck endpoint**: `/health/liveliness` 가 LiteLLM 의 표준
    endpoint 인지 버전 검증 필요. 미존재 시 healthcheck 명령 변경.
  - **OpenAI legacy 호환**: feature-0003 의 일부 코드가 `OPENAI_API_KEY` env
    직접 참조 (예: 다른 endpoint, init script) 가능성. grep 으로 추가 검증
    필요 — 본 cycle 의 scope 에 미포함 시 follow-up cycle 가 필요.
- Human Approval Needed: PLAN-APPROVED by ms.mckim (via /goal directive) on
  2026-05-21 — 사용자 5 결정 + 모델 family + scope 선택 + /goal 명시 진입을
  근거로 plan-approved 마커 부여. 본 cycle 의 Phase A~D 완료 후 commit /
  PR 단계는 별도 사용자 confirm 유지 (외부 영향 행동).

## REV-20260521-0002 (메모)
- Related Change: CHG-20260521-0001 (사실 검증 메모)
- Reason: AI 의 지식 cutoff (2026-01) 기준 "AWS Bedrock 에서 frontier OpenAI
  GPT-5 시리즈 native 제공 없음" 사실 정정 (사용자가 결정 3 에서 가정한
  "기존 gpt 모델 가용" 정정). 사용자가 이 정정을 수용 후 Claude family 선택.
- Alternatives Considered: GPT-OSS (오픈 가중치, 2025-08 release, Bedrock
  Marketplace 가용 가능성) — Seoul region 가용성 + tool use schema 호환성
  미검증 → 별 cycle 검토 후보.
- Risks: AWS Bedrock 의 frontier 모델 catalog 가 시간에 따라 변경. 본 cycle
  의 Claude 4.x 선택은 2026-05-21 시점의 가용성 가정 — 운영자가 batch 시점
  AWS console 에서 사실 검증 필수.
- Open Questions: GPT-OSS family 의 SQL 생성 품질 + tool use 호환성은 별
  cycle 의 benchmark 대상.
- Human Approval Needed: 본 메모는 사실 정정 기록 — 별 승인 불요.

## REV-20260522-0001 [SUBAGENT:general-purpose]
- Related Change: CHG-20260521-0001, CHG-20260521-0002 (commit-gate panel)
- Reason: AGENTS.md §18.8 verify-completion CHECK#9 요건 — commit 전 outside
  voice 검증. codex review 는 PR 후 사용자 결정으로 진행 예정이라, 본 cycle
  의 commit 전 게이트는 general-purpose subagent panel 로 충족.
- Verdict: **NEEDS-TWEAK / ACCEPT-WITH-NEEDS-TWEAK** (BLOCKER 0 / NEEDS-TWEAK 5
  / PASS 11). Commit 진행 가능 — 5 NEEDS-TWEAK 모두 follow-up cycle 위임 가능.
- Summary: 정적 분석 + Phase E 실 검증 결과 핵심 자격증명/모델 라우팅/UI 회귀
  표면은 모두 일관. NEEDS-TWEAK 5 건은 운영 가능 수준의 정합/안전망 보강 영역.
- NEEDS-TWEAK 항목 (commit 진행 + follow-up cycle 위임):
  1. **docker-compose env_file scoping** ([docker-compose.yml:5-6](../../../docker-compose.yml#L5-L6),
     `x-agent-common` 의 `env_file: - .env` inherit + 다른 서비스 동일 선언) —
     AWS_ACCESS_KEY_ID 가 bedrock-gateway 외 web/agent/insight-worker/mcp/caddy
     의 process env 로도 노출됨. `docs/SECURITY.md:61-63` 의 "gateway 컨테이너
     env 에만 주입" 정책과 실 구성 불일치 (false-claim). 실 leak 가치는 사내
     root 자격증명 전제 하에 낮음 — 정책 doc 정정 또는 bedrock-gateway 만 명시
     `environment:` 화이트리스트 refactor 둘 중 택일. follow-up cycle.
  2. **memory-init startup 지연**
     ([docker-compose.yml:15-19, 77-81](../../../docker-compose.yml#L15-L19)) —
     일회성 schema 초기화에 gateway healthcheck 의존이 부가되어 cold-start ~2분
     지연. memory-init override 로 mysql healthy 만 남기는 1-block patch 권고.
  3. **`/api/session` default_model fallback `'auto'` 잔존**
     (app.py:5102 / 5112 / 5135) — `model_catalog.API_DEFAULT_MODEL='claude-sonnet-4'`
     와 불일치. 3 사이트의 `os.getenv('OPENAI_MODEL', 'auto')` 를 `from .modules.
     model_catalog import API_DEFAULT_MODEL` 후 `'auto'` → `API_DEFAULT_MODEL`
     로 통일 권고. 1-line × 3 patch — 본 cycle immediate 또는 follow-up.
  4. **agent_core 의 OpenAI tool_calls API → Claude tool_use 변환 미검증**
     (agent_core.py:1344-1365) — LiteLLM 의 schema 변환 책임 영역. Phase E
     검증의 `Untested Area` 명시. deploy 후 canary 로 실 사용자 turn 1 회의
     `file_search` / `execute_sql` 검증 후 회귀 시 LiteLLM 버전 pin 또는 boto3
     native hotspot 마이그레이션 (ADR-0022 후속 액션) 즉시 진행.
  5. **`model_catalog.max_tokens_for_model = None`** for Claude (model_catalog.
     py:124-131) — Bedrock Sonnet 4.6 default output cap 미명시. 비용 폭주
     잠재 risk + temperature=0 실제 전달 검증 미수행 (Phase E plain message).
     deploy 후 canary 로 1 회 검증 + 명시적 max_tokens cap (4096/8192) 추가
     권고. follow-up cycle.
- PASS 항목 (11):
  1. _decrypt_api_key / _is_safe_api_key / _is_safe_passphrase 제거 후 잔존
     caller 0 건 (grep verified).
  2. _AUDIT_MASKED_FIELDS_API_KEY 의 doc-code drift 는 실 leak risk 없음 (현
     ChangeJson builder 화이트리스트 외).
  3. `.env.example` 실 자격증명 미포함 (placeholder + 안내 주석만).
  4. config.py 의 LLM_BASE_URL / LLM_API_KEY fallback chain 의도대로 작동.
  5. agent_core.py 의 run_agent / _run_agent_core api_key deprecated signature
     보존 + CLI main() 잔존 호출 0.
  6. litellm_config.yaml alias 와 model_catalog API_MODEL_OPTIONS.value 정확
     일치.
  7. app.js 의 vault 함수 일괄 제거 + jensen call site 잔존 0.
  8. index.html 의 drawer-tabs 3 탭 + 패널 DOM 정합.
  9. styles.css 의 .vault-* 186 줄 제거가 인접 cascade 영향 0.
  10. render.py 의 _extract_json_object 가 markdown fence 안 JSON 정상 추출
      (Phase E PASS).
  11. Phase E Run 2026-05-21-002: 컨테이너 healthcheck + IAM + global Sonnet 4.6
      호출 + alias 보존 + JSON mode 파싱 모두 PASS.
- Blindspots (codex review 가 PR 후 보강 권장):
  1. docker-compose env_file 의 AWS 자격증명 leak 분석 + bedrock-gateway 전용
     environment scoping refactor 의 실 효용 (사내 root 자격증명 전제 하에
     isolation 가치 vs 운영 복잡도).
  2. Claude tool_use (file_search / execute_sql / restore_sql / convo_search)
     변환의 LiteLLM 책임 영역 — 실 사용자 turn 1 회로 검증 + LiteLLM 의 schema
     변환 source 정독 (tool_choice / parallel tool calls / nested args dict).
  3. AWS Bedrock 의 global inference profile 의 데이터 region 흐름 — PIPA 잔류
     관점에서 사내 직원 데이터가 미국/EU 로 transit 되는지 AWS 보안 문서 외부
     voice 검증.
  4. model_catalog 의 max_tokens=None 정책이 Bedrock Claude Sonnet 4.6 의 default
     output cap (운영자 미인지 시점) 과 정합 — 비용 폭주 시나리오 worst-case.
  5. agent loop 의 reasoning content 처리 (agent_core.py:1370) — Claude 가
     LiteLLM 변환 후 reasoning 필드를 노출할지, OpenAI o1-style reasoning
     fallback 이 Claude 응답에 잘못 적용될 가능성.
  6. _AUDIT_MASKED_FIELDS_API_KEY doc-code drift — feature-0007 신규 자격증명
     키가 future audit ChangeJson 에 우연 포함될 때의 redact 보장.
- Risks: 위 NEEDS-TWEAK 5 항목 모두 commit 후 follow-up cycle 위임 가능. 본
  cycle 의 정책 doc (ANCHOR §1~§3, ADR-0022, SECURITY §6.1) 가 risk record
  를 명시 보유.
- Open Questions: codex review (PR 후) 가 blindspots 6 항목을 보강. 결과에
  따라 follow-up cycle 의 우선순위 결정.
- Human Approval Needed: 본 entry 는 PLAN-APPROVED 사용자 결정 후 commit 게이트
  panel — 별 사용자 confirm 불요. commit 결정은 사용자 명시 요청 ((1)+(2) 진행
  지시, 2026-05-22) 으로 충족.

## REV-20260522-0002 [SUBAGENT:codex]
- Related Change: CHG-20260522-0001 (P1 fix), CHG-20260521-0001/0002 (본 cycle 전체)
- Reason: PR #62 push 후 사용자 명시 (3) "codex review 후 full stack 진행 방향
  결정" 요청에 따라 `/codex review --commit 6eca18f` 실행. SUBAGENT panel
  (REV-20260522-0001) 이 위임한 6 blindspot 의 second opinion + BLOCKER 후보
  식별 + NEEDS-TWEAK 우선순위 판정 목적.
- Verdict: **GATE: FAIL** (1 [P1] + 1 [P2]). Codex 의 cross-model verdict 가
  SUBAGENT panel 의 ACCEPT-WITH-NEEDS-TWEAK 를 한 단계 격상.
- Cross-model analysis:
  - **Codex [P1] = SUBAGENT NEEDS-TWEAK #3 의 격상**: `/api/session` 의
    `default_model` fallback `'auto'` 잔존. Codex 가 ship 직후 첫 사용자 turn
    실패 시나리오 명시 — backend `_is_allowed_api_model` 400 차단. SUBAGENT 가
    "1-line × 3 patch follow-up" 으로 분류했던 것을 ship-blocker 로 격상한
    근거가 정확.
  - **Codex [P2] = SUBAGENT 미식별 영역**: `LLM_BASE_URL` 과 `LLM_API_KEY` 의
    독립 fallback chain. `BEDROCK_GATEWAY_URL` 설정 + `BEDROCK_GATEWAY_API_KEY`
    미설정 시 → backend 가 gateway URL 로 OpenAI/Local key 를 전송 → gateway
    401. 사내 한정 운영 + 운영자가 .env 신중 설정 가정 하에 risk 낮음 — 본
    cycle 의 fix 범위 외 (follow-up cycle 의 paired fallback refactor).
- Codex 가 본 run 에서 review 안 한 영역 (P1 발견 후 시야 집중):
  - docker-compose env_file 의 AWS 자격증명 leak vs SECURITY.md §6.1 정합
    (SUBAGENT NT #1, 운영 가치 낮음)
  - Claude tool_use 변환의 LiteLLM 책임 영역 (SUBAGENT NT #4, deploy 후 canary
    검증)
  - AWS Bedrock global inference profile 의 data region (PIPA blindspot 4)
  - `model_catalog.max_tokens=None` worst-case (SUBAGENT NT #5)
  - reasoning content 처리 (blindspot 5)
  - `_AUDIT_MASKED_FIELDS_API_KEY` doc-code drift (blindspot 6)
  → 본 6 항목은 follow-up cycle 또는 별도 `/codex consult` 로 보강 가능.
- Action: 사용자 결정 (2026-05-22) — P1 fix 즉시 진행. CHG-20260522-0001 에
  3 사이트 1-line patch + py_compile PASS. P2 는 follow-up cycle 위임.
- Risks: P1 fix 후에도 잔존 risk:
  - P2 paired fallback (low risk, 사내 운영 신중도 의존).
  - 6 blindspot 의 codex 미review 영역 — full stack smoke + canary 로 보강.
  - SUBAGENT 5 NEEDS-TWEAK (env_file scoping / memory-init 의존 / tool_use
    변환 / max_tokens cap) — follow-up cycle 큐.
- Open Questions: full stack smoke 진행 방향 — 사용자가 (3) 결정 후 다음 cycle
  진입 (TEST-0002~0006 web/mysql/agent full stack 가동 + Claude tool_use 실
  사용자 turn 회귀 검증).
- Human Approval Needed: 본 entry 는 사용자 명시 codex review 결과 기록 + P1
  fix 결정 (사용자 옵션 1 선택) 반영. 별 사용자 confirm 불요. 다음 cycle 진입
  은 사용자 (3) 별 cycle 결정.

## REV-20260522-0003 [SUBAGENT:phase-e-fullstack]
- Related Change: CHG-20260522-0002 (P1 fix v2 보강), Phase E full-stack 검증
- Reason: codex review (REV-20260522-0002) 의 P1 finding 을 CHG-20260522-0001
  로 1차 fix 한 후, 사용자 결정 (A→B→C→D 순서, 2026-05-22) 따라 Phase E
  full-stack smoke 진행. 격리 컨테이너 `-p feature-0007-e` (mysql + bedrock-gateway
  + memory-init + web) 가동 + bootstrap admin seed + curl 직접 호출로 backend
  → gateway → Bedrock Sonnet 4.6 full path 검증.
- Verdict: **PASS** (TEST-0001 ~ TEST-0004 모두 PASS, TEST-0005/0006 은 코드
  trace 갈음). 단 1 차 P1 fix (CHG-0001) 의 운영 .env 잔존 시점 보강 필요성
  발견 → CHG-0002 즉시 추가.
- Findings:
  - **TEST-0001 gateway healthcheck**: PASS (LiteLLM `main-stable` /health/liveliness
    200, container Up healthy).
  - **TEST-0002 `/api/ask` cipher 미동봉 응답**: PASS — bootstrap admin login
    후 cipher 인자 없이 `{model: "claude-sonnet-4"}` 만 보내 200 응답 +
    conversation_id 생성. bedrock-gateway 가 `POST /v1/chat/completions 200 OK`
    응답 로깅.
  - **TEST-0003 agent loop tool_use schema 변환** (codex blindspot #2 + SUBAGENT
    NT #4 의 최대 잠재 회귀 영역): **PASS** — `SHOW DATABASES` 질의 →
    `action=step + tool=execute_sql + sql="SHOW DATABASES"` plan 정상 생성.
    LiteLLM 의 OpenAI tool_calls ↔ Anthropic tool_use 변환 작동 검증. answer
    가 empty 인 건 MCP 컨테이너 미가동 (별 issue 외)— plan generation 자체는
    Claude 가 OpenAI Chat Completions schema 로 정상 응답.
  - **TEST-0004 JSON 파싱**: PASS — `_extract_json_object` 가 Claude 의 plan
    JSON 응답 정상 추출.
  - **TEST-0005 frontend 신규 사용자**: 브라우저 필요 — `app.js` 의 sendPrompt
    가 `state.session?.default_model` 우선 사용 + CHG-0002 가 그 값을 catalog
    안 alias 만 반환 보장 → 첫 turn 부터 정상 동작 (코드 trace 갈음).
  - **TEST-0006 localStorage cleanup**: 브라우저 필요 — `LEGACY_VAULT_KEYS.
    forEach((k) => localStorage.removeItem(k))` 가 페이지 로드 1 회 silent
    실행 (코드 trace 갈음).
- 추가 발견 (panel):
  - 운영 `.env` 가 실제로 `OPENAI_MODEL=auto` 설정 — codex P1 finding 의 회귀
    시나리오 실증. CHG-0001 만으로는 부족 (env 가 set 되어 있으면 fallback
    미발동). CHG-0002 의 catalog 검증 + Local LLM 가용성 cross-check 필수.
  - `_LOCAL_LLM_ENABLED` cache 가 module load 시점 평가 — LOCAL_LLM_API_BASE
    env 변경 시 web 컨테이너 재기동 필수 (운영 안내 후속 cycle).
  - bedrock-gateway 가 LiteLLM `main-stable` (image pull 진행 시점 확인 됨) +
    config.yaml volume mount + healthcheck 정합. 다른 컨테이너 (운영 stack)
    와 격리 port (33306 / 28080 / 38000 / 10080 / 10443 / 25432) PASS.
  - docker compose buildx metadata race 가 본 cycle 에서도 재현 (운영 Makefile
    의 `dc-build` 가드 동일 영역) — `--no-build` 로 회피 가능. follow-up
    Makefile target 갱신 별 cycle.
- Risks:
  - **MCP 컨테이너 미가동** 시 `tool=execute_sql` 의 backend 실 실행이 안 됨 —
    본 검증의 scope 외 (Phase E 의 plan generation 까지). 운영 환경에서는 mcp
    가동 후 turn 검증 필요 (canary).
  - **Local LLM gateway 운영 transition**: `LOCAL_LLM_API_BASE=` 빈 값으로 변경
    + web 재기동 후에야 Bedrock-only 정합. 운영자가 .env 단계적 마이그레이션
    필요 — 안내 doc 별 cycle.
- Open Questions: 
  - Cleanup 시점 (격리 컨테이너 down) — 본 검증 완료 후 즉시 down 진행 권장.
  - B (codex P2 paired fallback) + C (6 blindspot) 진행 후 본 검증 재실행 필요
    여부 — CHG-0002 가 P1 핵심 영역이라 추가 fix 가 행동 변경 없으면 재검증
    불요.
- Human Approval Needed: 본 entry 는 사용자 명시 A→B→C→D 진행 결정의 A 단계
  결과 기록. 별 사용자 confirm 불요. B/C/D 진행은 사용자가 명시한 순서 따라
  자동 진행 (이전 turn 의 user 결정).

## REV-20260522-0004 [SUBAGENT:codex-p2-direct-fix]
- Related Change: CHG-20260522-0003 (codex P2 paired fallback chain refactor)
- Reason: 사용자 결정 (B 단계, 2026-05-22) — codex P2 finding (LLM_BASE_URL ↔
  LLM_API_KEY 독립 fallback 으로 partial 설정 시 silent misroute) 의 follow-up
  보강. 본 entry 는 fix 의 reasoning 정본 (별도 panel 호출 없이 codex 원본
  finding 을 직접 반영하는 [SUBAGENT:codex-p2-direct-fix] 형식).
- Verdict: **PASS** — codex P2 권고 직접 반영. `_select_llm_provider()` helper
  가 paired tuple 보장.
- Codex P2 원문 (REV-20260522-0002 cross-reference):
  > "With `BEDROCK_GATEWAY_URL` set but `BEDROCK_GATEWAY_API_KEY` empty, which
  > is exactly the shape shown in `.env.example` and also plausible for legacy
  > OpenAI/Local deployments, `LLM_BASE_URL` points at the Bedrock gateway
  > while `LLM_API_KEY` falls through to the Local/OpenAI key... the documented
  > fallback chain cannot work unless each provider's URL and key are selected
  > as a matched pair."
- Fix 행동 (config.py + .env.example):
  - `_select_llm_provider() -> tuple[str|None, str|None]` helper 가 paired
    priority chain (Bedrock paired → Local LLM paired → OpenAI direct → None).
  - `LLM_BASE_URL, LLM_API_KEY = _select_llm_provider()` 결정 단일화.
  - `.env.example` Bedrock 섹션에 "paired 설정 필수" 안내 + LLM provider 우선
    순위 3 항목 명시.
- Risks: 본 fix 후에도 잔존 risk:
  - **OPENAI_API_BASE optional** (OpenAI direct 경로) — `OPENAI_API_KEY` 만
    있고 `OPENAI_API_BASE` 미설정 시 (None, KEY) tuple 이고, SDK 가 default
    OpenAI cloud base 사용. 정상 — OpenAI direct fallback path 보존.
  - **legacy 호환**: 운영자가 기존 OPENAI_API_KEY only 설정 환경에서 본 변경
    영향 없음.
- Open Questions: 본 entry 는 single-line 검증 reasoning 기록. 별 cycle 의
  codex consult 로 추가 검증 권장 (전체 fallback chain 정합).
- Human Approval Needed: 사용자 결정 (A→B→C→D 진행, 2026-05-22) 의 B 단계
  완료 기록. 별 confirm 불요. C/D 진행 계속.

## REV-20260522-0005 [SUBAGENT:blindspot-reinforcement]
- Related Change: CHG-20260522-0004 (codex 6 blindspot 보강)
- Reason: 사용자 결정 (C 단계, 2026-05-22) — codex review (REV-20260522-0002)
  가 본 PR diff 검토 외로 위임한 6 blindspot 의 일괄 보강. SUBAGENT panel
  (REV-20260522-0001) 의 follow-up + Phase E full-stack 검증 (REV-20260522-0003)
  의 발견 결합.
- Verdict: **PASS** (코드 3 영역 fix + 분석 3 영역 기록). 각 blindspot 별 결론:
- **Blindspot #1 (env_file scoping vs SECURITY.md §6.1 false-claim)**:
  - **분석**: docker-compose.yml 의 `x-agent-common.env_file: - .env` 가 web /
    agent / memory-init / insight-worker 에 inherit. mcp / caddy 도 동일 env_file
    선언. → AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 가 bedrock-gateway 외
    process env 로도 노출. SECURITY.md §6.1 의 "gateway 컨테이너 env 에만"
    표현이 실 구성과 불일치 (false-claim).
  - **결정**: 정책 doc 정정 채택 (option A) — bedrock-gateway 만 명시
    `environment:` whitelisting 으로 refactor (option B) 는 운영 복잡도 ↑ +
    사내 root 자격증명 전제 하에 isolation 가치 낮음 → 별 cycle 위임.
  - **Fix**: SECURITY.md §6.1 의 표현 정정 + application code 가 AWS_* 미참조
    명시 + 엄격 isolation 필요 시 refactor 별 cycle 안내.
- **Blindspot #2 (Claude tool_use 변환의 LiteLLM 책임)**:
  - **분석**: agent_core.py:1344-1365 가 OpenAI tool_calls API 사용 — LiteLLM
    이 Anthropic tool_use 로 변환. Phase E full-stack TEST-0003 으로 검증:
    `SHOW DATABASES` 질의 → `action=step + tool=execute_sql + sql="SHOW DATABASES"`
    plan 정상 생성 → bedrock-gateway 가 `POST /v1/chat/completions 200 OK`
    응답. 변환 정상.
  - **결정**: 코드 변경 X. Phase E 검증 결과로 충분. 잠재 edge case (parallel
    tool_calls / nested args dict / tool_choice="required") 는 운영 turn
    누적 시 fallback / 별 cycle 검토.
  - **Fix**: 없음 (베이스라인 충족 확인).
- **Blindspot #3 (data region 흐름 PIPA)**:
  - **분석**: AWS Bedrock 의 `global.*` inference profile 은 cross-region routing
    — 미국 / EU / APAC 어느 region 으로든 hit 가능. AWS 보안 문서 (Bedrock
    Inference Profiles docs) 에 따르면 inference 자체는 routing 후 region 안
    잔류 (저장 X). 다만 monitoring / audit log 가 별 region 일 수 있음.
  - **결정**: Phase E reanchor 로 사용자가 명시 수용 — 사내 한정 + 비-개인정보
    SQL 작업 가정. SECURITY.md §6.1 region 정책 reanchor 진행.
  - **Fix**: SECURITY.md §6.1 의 잔존 risk 명시 + 엄격 잔류 필요 시점 별 cycle
    안내 (Provisioned throughput / 별 provider).
- **Blindspot #4 (max_tokens=None worst-case)**:
  - **분석**: `model_catalog.max_tokens_for_model()` 가 Claude alias 에 None
    반환 → Bedrock Sonnet 4.6 의 default cap (64K output) 까지 채울 수 있음.
    사용자 long query 또는 model hallucination 시 worst-case 비용 폭주.
    Sonnet 4.6 의 output rate ($15/M token) 기준 8192 token = ~$0.12 / turn.
    cap 없으면 ~$0.96 / turn (8x).
  - **결정**: task 별 명시 cap 도입.
  - **Fix**: `_CLAUDE_MAX_TOKENS` dict 신설 (agent 8192 / insight 2048 / summary
    1024 / sql_fix 2048 / validate 1024). `max_tokens_for_model()` 가 Claude
    alias 인 경우 본 dict cap 반환.
- **Blindspot #5 (reasoning content 처리)**:
  - **분석**: agent_core.py:1370 의 fallback 이 `response_message.reasoning`
    + `response_message.reasoning_content` 둘 다 check (baseline code). Claude
    가 LiteLLM 변환 후 OpenAI o1-style reasoning field 노출하면 본 path 가
    정상 처리. content 가 empty + reasoning ≥ 20 char 이면 reasoning 을
    answer 로 사용.
  - **결정**: 코드 변경 X — baseline 이 이미 mitigation 보유.
  - **Fix**: 없음 (baseline 충족 확인).
- **Blindspot #6 (`_AUDIT_MASKED_FIELDS_API_KEY` doc-code drift)**:
  - **분석**: docs/SECURITY.md §9.2 가 `bedrock_gateway_api_key`,
    `aws_access_key_id`, `aws_secret_access_key` 를 masked field 로 명시.
    app.py 의 tuple 은 `("openai_api_key", "api_key", "secret")` 만 — drift.
    현 audit ChangeJson builder 가 화이트리스트 기반이라 실 leak risk 0 이나
    future ChangeJson 에 우연 포함 시 redact 미보장.
  - **결정**: 1-line patch — code 측을 docs 명시와 정합.
  - **Fix**: `_AUDIT_MASKED_FIELDS_API_KEY` 에 3 항목 추가.
- 잔존 risk:
  - **env_file scoping refactor**: 별 cycle 위임. 엄격 isolation 필요 시점에
    docker-compose.yml 의 `environment:` whitelist 패턴 도입 (운영 복잡도 ↑).
  - **tool_use parallel / nested args edge case**: 운영 turn 누적 시 발견 시
    LiteLLM 버전 pin 또는 boto3 native hotspot 마이그레이션.
  - **Bedrock global routing 의 region 추적**: AWS Cost Explorer + CloudWatch
    region tag 분석으로 실 routing region 모니터링 (별 cycle).
- Open Questions: D 단계 (PR #62 merge + cycle-finalize) 직전 본 cycle 의 모든
  변경이 정합한지 최종 검증 — Phase E 재실행 또는 코드 trace 갈음.
- Human Approval Needed: 사용자 결정 (A→B→C→D, 2026-05-22) 의 C 단계 완료
  기록. 별 confirm 불요. D 진행 (PR merge + cycle-finalize) 계속.

## REV-20260522-0006 [SUBAGENT:env-scoping-followup]
- Related Change: CHG-20260522-0005 (env_file scoping refactor) + CHG-20260522-0006
  (OpenAI API Key 폐기)
- Reason: feature-0007 의 follow-up cycle. codex blindspot #1 + SUBAGENT NT #1
  (docker-compose env_file inheritance 의 AWS_* leak) 의 최종 refactor +
  사용자 추가 결정 (모든 secret 영역 분리 + OpenAI 미사용).
- Verdict: **PASS** — secret 영역별 5 `.env.*` 분리 + OpenAI direct fallback 제거.
  least privilege 강제 달성.
- Action:
  - .env.bedrock / .env.mysql / .env.postgres / .env.minio / .env.llm 신규
    (각 .example committed, 실 파일 gitignored).
  - docker-compose 의 6 service env_file list 갱신.
  - .gitignore 5 패턴 추가.
  - .env.example 14 secret 행 제거 + 운영자 마이그레이션 가이드.
  - config.py 의 _select_llm_provider() OpenAI direct 분기 제거.
  - SECURITY.md §6.1 reanchor (env_file scoping 정책 + OpenAI 폐기).
  - DECISIONS.md ADR-0026 addendum.
- Risks:
  - **운영자 1 회 마이그레이션 부담**: 기존 단일 .env 의 14 secret 행을 5 분리
    파일로 이동. .env.example 헤더 가이드 + 본 entry 의 명시.
  - **OpenAI 미사용**: 운영 .env 의 잔존 `OPENAI_API_KEY` silent ignore. 운영자
    가 모르고 OpenAI key 설정 시 무시 — 의도된 행동이나 운영 안내 필요.
- Open Questions: 본 cycle 의 ship 후 운영 환경에서 실 마이그레이션 검증 필요.
- Human Approval Needed: 사용자 결정 (2026-05-22) 의 follow-up cycle 명시 진행
  + scope (모든 secret 영역 분리 + OpenAI 폐기) 결정. 별 confirm 불요.

## REV-20260623-0001 [SUBAGENT:backend] — PASS
- Related TASK: feature-0007-bedrock-llm-provider (CHG-20260623-0001)
- Trigger: code change (config/infra) → backend dispatch (임무 명시; embedding/임베딩
  + network/네트워크 신호). litellm ollama embedding 라우팅 + docker network 정합 검증.
- Timestamp: 2026-06-23T08:42:02Z
- Verdict: PASS
- Artifact: unit/feature-0007-bedrock-llm-provider/docs/reviews/20260623T084202Z-backend.md
- Critical issue (if BLOCK/CONCERN): 없음 — 통상 BLOCK 사유(임베딩 공간 혼선)는
  texts/sample_queries embedding 컬럼이 실 데이터 0건이라 실증적으로 무효. litellm
  `ollama/bge-m3`+`api_base` 문법 정확, 네트워크 변경 non-breaking, end-to-end dim=1024.
- Non-blocking follow-ups: ① 배포 후 backfill 실행(현재 vector 검색 trigram-only)
  ② embedding_model provenance 라벨(alias=titan-embed vs 실 bge-m3)
  ③ bge-m3 모델 의존 추적(fresh host provisioning) + litellm 이미지 핀.
- Human Approval Needed: no (사용자 임무 지시로 본 전환 명시 위임. PR 생성·머지·
  gateway restart 는 메인 세션 마감 — 본 cycle scope 외).

## REV-20260703T101500-insight-llm-fallback [SUBAGENT:insight-llm-fallback-adversarial-backend-infra]
- 대상: litellm_config.yaml(3-deployment fallback 체인) + bin/refresh-claude-oauth-token.sh(병행 주입). TASK-0308 후속.
- Round: 7축 적대 검증 — ① fallbacks 동작(429 순서 폴백), ② thinking 파라미터+gemma, ③ refresh 병행주입 셸 정확성(a~d),
  ④ 토큰 만료 처리, ⑤ 기존 동작 회귀, ⑥ 보안, ⑦ 재생성 안전성. 라우팅(llm.py `_resolve_tier_endpoint`)·게이트웨이
  (docker-compose)·edge alias(local_llm router `gemma4:e2b`) 배선 사실 코드 인용 확인.
- VERDICT: **ACCEPT-WITH-NITS** (BLOCKER 0, MAJOR 0). 셸 4개 하위검증(SEL set-e 흡수·탭 매칭·조합 매트릭스·write_env_key
  append) 전부 정확, 게이트웨이 기동 안전(미설정 _ROOT → get_secret None·edge api_base startup probe 안 함 → config
  파싱실패로 sonnet/haiku 함께 안 죽음), fallback 체인·thinking deployment-scoped 격리·라우팅 성립. 크래시/데이터손상/
  기동실패 경로 없음. Ship-able.
- 확정 사실: insight 는 `claude-haiku-4` 를 bedrock-gateway(litellm)로 보냄(`_resolve_tier_endpoint`) → fallbacks 실적용.
  edge `gemma4:e2b` 는 local_llm router 의 default-edge 로 정상 라우팅. insight 는 thinking/temperature 미전송 →
  edge 폴백 시 미지원 파라미터 누출 경로 없음(+drop_params 2차 안전망).
- MINOR/NIT(비차단, 대부분 graceful degradation):
  - MINOR ① **cron 창 밖 강등**: refresh cron(`0,30 10-18 * * 1-5`)은 평일 업무시간만. root accessToken short-lived →
    야간/주말 두 토큰 만료 시 insight 가 edge(gemma)로 **상시 강등**(하드실패 아님, best-effort). "root Max 품질" 이점은
    업무시간+신선 토큰 창에서만. → **FUNCTION §9 · REPORT 에 운영 인지 명시**.
  - MINOR ② **degenerate hop**: claude-corp down 시 PRIMARY 도 root 로 폴백 → ANTHROPIC_API_KEY==ANTHROPIC_API_KEY_ROOT
    → root deployment fallback 이 같은 계정 2번 hop 후 edge. 정합성 버그 아님·자가회복(claude-corp 복구 시 분리).
  - MINOR ③ **첫 배포~첫 refresh 사이**: _ROOT 부재 → root deployment api_key=None → litellm 이 env ANTHROPIC_API_KEY
    (=corp)로 축퇴 → root hop 이 corp 재시도. graceful. (배포 시 refresh 선실행으로 해소.)
  - MINOR ④ edge fallback 은 best-effort: gemma JSON 구조화 품질 낮아 `_extract_json_object` 실패 → insight skip 수렴(무해).
  - NIT: litellm `main-stable` 미고정(fallback 시맨틱 버전 의존) → **배포 후 실 429/401 유발 라이브 fallback 검증 권장**;
    root 이중 probe(최대 2회/cron); .env.bedrock 에 두 OAuth 토큰 평문 병행(마운트 bedrock-gateway 한정·short-lived 완화).
- 배포 전 권장(비차단): (1) 라이브 fallback 실측(main-stable unpinned), (2) cron 창 밖 강등 운영 문서화, (3) litellm 버전 핀.
- Verification: litellm_config YAML OK(5 deployment)·refresh bash -n OK·--check(corp 200/root 200) PASS. ANCHOR §1·§2 무충돌.
- Cross-ref: CHG-20260703-insight-llm-fallback / TASK-0308 / feature-0002 REPORT.

## REV-20260724T105132-sonnet-chat-fallback [SUBAGENT:backend-infra-adversarial] — PASS-WITH-NITS
- 대상: 새 대화 sonnet 선택 시 "서비스 자체의 요청량 한도" 실패(계정 quota 무관) 수정. CHG-20260724T105132-sonnet-chat-fallback 정합.
- 적대 패널(backend/infra, general-purpose subagent) verdict: **PASS-WITH-NITS**. 6개 가설 전부 REFUTED(신규 회귀 0):
  ①max_tokens>thinking(40000>16000, bare sonnet 과 동형·무회귀) ②격리(conversation_answer_model 유일 호출처=_call_llm, probe/node_analysis/insight 미경유; bare sonnet deployment 1바이트 무변경) ③fallback 체인(sonnet-chat→chat-root 종단·edge 미도달·haiku 체인 불변) ④api_key(chat=ANTHROPIC_API_KEY=claude-corp, chat-root=_ROOT — 실 2계정) ⑤usage(원본 claude-sonnet-4 기록→by_model 단가 정상).
  - NIT 대응(본 cycle 반영): (a) G5b 에 bare claude-sonnet-4 단일계정·fallback-미등록 격리 불변식 단정 추가, (b/c) G8b `test_call_llm_sizes_sonnet_budget_from_original_model` 신설(예산 키=원본·max_tokens>16000 실경로 검증).
  - 잔여 NIT(사전존재·본 cycle 미대응): 계정별/일별 비용 뷰가 `COALESCE(resolved_model, model)` 키잉이라 litellm 이 `-chat` alias 를 resp.model 로 에코하면 단가표 미등록으로 $0 오표시 — haiku-chat/-interactive/-root 에 이미 존재하는 gap 의 sonnet 확장(별 cycle, admin_usage `_LLM_PRICE_USD_PER_1M` 에 -chat alias 추가로 해소). REPORT §8 기록.
- 문제 정의: 대화 답변 경로에서 haiku 는 `claude-haiku-4-chat`→`-chat-root` 2계정 edge-free 체인으로 claude-corp 429 를 생존하나, sonnet 은 `conversation_answer_model` 미매핑(identity)이라 bare `claude-sonnet-4`(단일 계정·fallback 미등록)로 나가 429 시 즉시 실패. haiku 대비 sonnet 이 **엄격히 열등한 회복성** — 의도적 설계가 아니라 no-edge-conversation(2026-07-07) 당시 "sonnet 은 edge 폴백 없음"만 보고 root 계정 fallback 부재를 간과한 결함.
- 결정: haiku-chat 패턴과 **동형 parity 복원** — sonnet 에도 `-chat`(claude-corp)→`-chat-root`(root) 2계정 edge-free 체인 부여.
  - 대안 A(채택): 대화 전용 `claude-sonnet-4-chat` alias 신설 + `_CONVERSATION_ANSWER_ALIAS` 매핑. bare `claude-sonnet-4`(probe/OPENAI_MODEL/node_analysis) 무변경으로 격리 — haiku 가 `-chat` 를 신설한 것과 정확히 동일 구조. 무회귀.
  - 대안 B(기각): bare `claude-sonnet-4` 에 직접 fallback 추가. probe·node_analysis 등 비대화 경로까지 root 계정으로 폴백시켜 blast radius 확대. 격리 원칙 위배.
  - 대안 C(기각): sonnet 을 haiku 로 강제 강등. 사용자가 명시 선택한 frontier 모델을 조용히 바꾸는 것은 기대 위반.
- 위험도: **Major(§12.3)** — LLM provider 라우팅 변경. 외부 자격/비용 경계: 신규 자격 없음(기존 두 OAuth 계정 재사용). root 계정(개인 Max 5x)이 sonnet 대화 fallback 트래픽을 받게 됨 — haiku-chat 이 이미 동일 취급이라 정책적 신규 노출 아니나, **sonnet(frontier)은 haiku 대비 root 계정 창을 더 빨리 소진**할 수 있음(운영 인지 항목). 종량 과금 아닌 구독 용량이라 per-token 외부 비용 증가는 없음.
- max_tokens/thinking 정합: sonnet-chat·-chat-root 의 config `budget_tokens: 16000` 은 bare `claude-sonnet-4` 와 동일. 대화 경로 max_tokens 는 원본 `claude-sonnet-4` 키의 `agent_max_output`(default 40000)로 산정(무회귀) → 40000>16000 만족. '일반' 레벨은 override 미주입(config 16000 유지), 명시 레벨은 `_call_llm` 이 min(budget, max_tokens−1024)로 clamp → Anthropic max_tokens>budget 항상 보장. **bare sonnet 과 동일 관계라 2차 400 무회귀.**
- 잠재 사전존재 이슈(본 변경 범위 밖, 미도입): TEST.md §7 의 `claude-haiku-4-chat-root` "max_tokens must be greater than thinking.budget_tokens" 노트는, admin 이 `agent_max_output(model)` 을 config 고정 thinking(haiku 5000 / sonnet 16000) 미만으로 낮췄을 때 발생하는 잠재 조건(모든 thinking alias 공통, bare 포함). sonnet default 40000≫16000 이라 정상 운영에서 미발생. 별도 cycle 로 "config 고정 thinking 대비 agent_max_output 하한 가드" 검토 권장(REPORT §8 기록).
- Verification: YAML lint OK(11 deployment/6 fallback), feature-0002+0003 pytest PASS(rc=0), 신규 G5b 가 sonnet 체인 라우팅·2계정·edge-free 3속성 고정.
- Cross-ref: MODIFY CHG-20260724T105132-sonnet-chat-fallback / TEST.md Run 2026-07-24-001 / shared/model_catalog.py.

## REV-20260724T113513-sonnet5-upgrade [SUBAGENT:backend-infra-adversarial ×2] — PASS-WITH-NITS (라이브 검증 게이트 有)
- 대상: sonnet → Sonnet 5 라우팅 + **thinking API budget_tokens → adaptive/effort 마이그** + 버전-무관 사용자 라벨. CHG-20260724T113513-sonnet5-upgrade 정합.
- 문제 정의: sonnet-chat-fallback 배포 후 라이브서 sonnet 두 계정 모두 429 발견 → 실 원인은 **폐기 모델 `claude-sonnet-4-6` 라우팅**. 1차 수정(sonnet-5 repoint, budget_tokens 유지)을 적대 패널이 **FAIL** 판정: **Anthropic 스펙(claude-api skill 확인)상 Sonnet 5 는 `thinking:{type:enabled,budget_tokens}` 를 400 으로 거부** — 429→400 으로 바뀔 뿐 여전히 실패. adaptive thinking + output_config.effort 로 재설계.
- 2차 적대 패널(adaptive 마이그) verdict: **PASS-WITH-NITS**. 가설 판정:
  - H1 budget_tokens 누출 **REFUTED** — 주입 지점 2곳(agent_core `_call_llm`:3103/probe:463)만 존재하고 둘 다 `_think_style=="budget"` gate. sonnet 3 alias config 전부 adaptive. node_analysis 기본값=claude-haiku-4-interactive(budget). 잔존 누출 경로 0.
  - H3 max_tokens 정합 **REFUTED** — adaptive 는 budget<max 제약 제거, max_tokens(40000)만 유효.
  - H2 style 분류 기본값 **LATENT-DEFECT → 수정 완료**: 미상 claude 를 'budget' 기본 처리하면 미래 adaptive-only(opus-4-8/sonnet-6)에 budget_tokens 주입 → 400. `_BUDGET_THINKING_PREFIXES` 명시 + 미상 claude → **None(안전, 미주입)** 으로 수정. 테스트 `model_thinking_style("claude-opus-4-8")/("claude-sonnet-6") is None` 추가.
  - H7 probe 테스트 부재 **→ 수정 완료**: `test_probe_adaptive_model_sends_effort_not_budget`(effort low·budget 미주입·max_tokens>1) 추가.
  - H6 probe 주석 부정확 **→ 정정**.
  - H5 관리 콘솔 죽은 sonnet budget 슬라이더 **CONFIRMED(minor, 이연)**: cosmetic(400/사용자 영향 없음)이나 fix 가 test_runtime_settings 4곳 cascade → 라이브 배포 앞 회귀위험 회피 위해 **REPORT §8 이연**(effort 스펙 신설 방향 병기).
  - **H4 litellm 통과 CONFIRMED 라이브 게이트(차단)**: litellm(main-stable)이 config-level `thinking:{type:adaptive}` 를 통과시키고 `drop_params:true` 가 요청 `output_config.effort` 를 stripping 하지 않는지는 **코드로 확정 불가**. `adaptive` enum 거부 시 sonnet 전부 400, effort strip 시 추론강도 선택기 sonnet 무음 no-op(회귀). **배포 후 gateway ping(sonnet-4-chat + effort) 200 실측 필수 — 실패 시 rollback.**
- 위험도: **Major(§12.3)** — LLM provider thinking-API 마이그. 신규 자격 없음. 라이브 검증 게이트가 완료 조건.
- Verification: feature-0002+0003 pytest PASS(rc=0, adaptive/effort·dual-style·probe adaptive·H2 안전기본값 테스트 포함), YAML OK, JS OK. H4 는 배포 후 라이브 ping + PB-0008.
- Cross-ref: MODIFY CHG-20260724T113513-sonnet5-upgrade / TEST.md Run 2026-07-24-002 / shared/model_catalog.py `model_thinking_style` / agent_core `_call_llm` / llm_provider_health `probe_provider`.

## REV-20260724T123503-cc-identity-inject [SKIPPED:live-empirical-verification] — PASS
- 대상: Sonnet 5 OAuth frontier-identity 게이트 해소(Claude Code identity 첫 system 블록 주입). CHG-20260724T123503-cc-identity-inject 정합.
- **리뷰 방식 = 라이브 실증(정적 적대리뷰 대신, [SKIPPED] 사유)**: 본 변경의 정확성은 **Anthropic 의 런타임 OAuth-identity 게이트 동작**으로 결정되며 정적 코드리뷰로 판정 불가. 직접 api.anthropic.com + gateway 실 probe 로 다음을 결정적으로 확증:
  - 두 계정 sonnet-5 직접 200(용량 有) · system 없음/generic → 429 · CC 문자열만 → 200 · `CC+제품` 단일 문자열 → 429 · **블록/메시지 분리 `[CC,제품]` → 200** · haiku 미요구.
  - litellm 매핑: 2 system 메시지 또는 system content 블록배열 → Anthropic 첫 블록 CC → 200(구현 채택: 2 system 메시지 prepend).
  - 동작: CC-first + DB 제품 system → 답변 DB 어시스턴트 정상(코딩 아님).
- 판정: sonnet5-upgrade cycle 의 2차 적대패널이 남긴 유일한 라이브 게이트(H4/frontier-identity)를 실증으로 닫음. 코드 변경은 상수 1 + 헬퍼 1 + adaptive-gated 주입 2곳(대화·probe)으로 최소, 단위 테스트가 gating·주입·haiku-미주입·probe 주입 고정.
- 위험도: **Major(§12.3)** — LLM 라우팅/인증 표면. 신규 자격 없음(기존 OAuth 토큰). ToS 경계(구독 토큰에 Claude Code identity)는 사용자 명시 결정(2026-07-24 "identity 주입 구현").
- Verification: feature-0002+0003 pytest PASS(rc=0). 배포 후 gateway 실 대화 ping(sonnet 200) + PB-0008 최종.
- Cross-ref: MODIFY CHG-20260724T123503-cc-identity-inject / shared/model_catalog.py `OAUTH_FRONTIER_IDENTITY`.

## REV-20260724T141420-llm-timeout-align [SKIPPED:minor-config-alignment] — PASS
- 대상: litellm request_timeout 120→300 (Sonnet 5 대화 "Request timed out" 해소). CHG-20260724T141420-llm-timeout-align 정합.
- 리뷰 방식([SKIPPED] 사유): 단일 config 값 정합화(로직 변경 0). 근본원인은 라이브 실측으로 결정적 확정 — 배포 AGENT_TIMEOUT_SEC=300(앱 client) > litellm request_timeout=120(gateway) 불일치로 gateway 가 앱보다 먼저 컷. config 주석이 명시한 "request_timeout ≥ AGENT_TIMEOUT_SEC" 의도를 복원하는 것이라 정적 적대리뷰의 추가 판별력 낮음.
- 대안 검토: (a) effort 를 medium 기본으로 낮춰 latency 단축 — 개별 호출 실측이 19s(high)로 이미 빠르고 답변 품질 저하 우려라 미채택(근본은 타임아웃 불일치). (b) 대화 경로 streaming 전환 — claude-api skill 권장(장문/high max_tokens 타임아웃 회피 정본)이나 agent loop 대규모 리팩터·회귀위험 → REPORT §8 장기 과제로 이연. 본 cycle 은 명백한 불일치(120<300)만 정합화하는 최소·고신뢰 fix.
- 위험도: Minor(§12.3) — 타임아웃 상향, 비파괴. 상향은 느린 호출을 더 기다릴 뿐 회귀 없음(빠른 호출 무영향).
- Verification: YAML OK. 배포 후 실행 config request_timeout=300 + sonnet 대화 정상 확인.
- Cross-ref: MODIFY CHG-20260724T141420-llm-timeout-align / TEST.md Run 2026-07-24-004.

## REV-20260724T054326-timeout-console-sync [SKIPPED:doc-comment-only-code-review-canonical-in-feature-0002] — PASS
- 대상(feature-0007): litellm_config.yaml `request_timeout: 300` **주석만** 갱신(값 무변경). 콘솔 AGENT_TIMEOUT_SEC(live) ↔ gateway upstream 타임아웃 요청 단위 동기화의 config-측 문서화.
- 리뷰 방식([SKIPPED] 사유): feature-0007 변경은 주석-only(로직·값 변경 0). 실제 코드/로직(앱이 요청마다 live body timeout 전달, extra_body 항상-timeout 병합, client/run 예산 live 전환)은 feature-0002 에 거주하며, 그 적대 리뷰가 정본 = **REV-20260724T054326-timeout-console-sync [SUBAGENT:adversarial-general-purpose] SHIP**(7 공격각 CLEAN, NIT 2·3 반영, Finding 1 by-design 수용). 본 feature-0007 엔트리는 config 주석 정합 기록.
- Cross-ref: feature-0002 REVIEW/CHG/TASK-20260724T054326-timeout-console-sync / MODIFY CHG-20260724T054326-timeout-console-sync / TEST.md Run 2026-07-24-timeout-console-sync.

## REV-20260727T184425-opus5-model [SKIPPED:live-empirical-verification+precedent-checklist] — PASS
- 대상: assistant 선택 모델에 Claude Opus 5 추가(3 deployment · 2계정 edge-free 체인 · adaptive thinking · CC identity · 단가 원장). CHG-20260727T184425-opus5-model 정합.
- **리뷰 방식([SKIPPED] 사유)**: 본 변경의 정확성을 결정하는 두 축이 모두 **정적 코드리뷰로 판정 불가**한 런타임 계약이다 — (a) Anthropic OAuth identity 게이트 동작, (b) 계정별 모델 접근성/한도. sonnet 선례(REV-20260724T123503-cc-identity-inject)와 동일하게 **코드 작성 전 라이브 실증**으로 확증했고, 그 위에 **sonnet 4차 수정 이력을 회귀 체크리스트로 역이용**했다. 정적 패널이 추가로 판별할 여지가 낮다고 판단.
- **선례 역이용 체크리스트(sonnet 이 사후에 겪은 4개 결함을 도입 시점에 차단)**:
  1. *bare 단일계정 → claude-corp 429 즉시 실패*(#915) → 도입 시점부터 `-chat`/`-chat-root` 2계정 체인. 단위 테스트 `test_opus_conversation_chain_has_two_accounts_and_is_edge_free` 가 (등록·root 도달·자격 slot 분리·edge 미도달·bare 격리) 5개를 config 실파싱으로 고정.
  2. *폐기 모델 ID 라우팅*(#920) → `claude-api` skill 정본 + 라이브 200 응답의 `model=claude-opus-5` 로 실 ID 확인.
  3. *budget_tokens 400*(#920) → `_ADAPTIVE_THINKING_PREFIXES` 에 `claude-opus`. `test_opus_adaptive_injects_effort_not_budget` / `_normal_no_override` 가 주입 0 을 고정.
  4. *OAuth frontier-identity 게이트 429*(#923) → 사전 실증 후 `requires_oauth_frontier_identity` 자동 적용. `test_call_llm_opus_adaptive_with_cc_identity` 가 첫 메시지 = 별도 CC system 블록임을 고정(단일 문자열 연결 회귀 차단).
- **자기 적대 검토(설계 선택 2건, 의도적 비대칭)**:
  - `_ADAPTIVE_THINKING_PREFIXES` 는 **넓은** `claude-opus`, `canonical_usage_model` 은 **좁은** `claude-opus-5`. 축이 다르다 — 전자는 *안전*(어떤 Opus 버전에도 budget_tokens 를 주입하지 않음; 미분류 시 thinking override 가 조용히 사라지는 회귀), 후자는 *정직*(미등록 Opus 를 Opus 5 단가·비중으로 오귀속하지 않고 self-surface). 두 규칙을 같게 맞추면 어느 한쪽이 손해다. 부작용으로 `model_thinking_style("claude-opus-4-8")` 이 None→adaptive 로 바뀌는데(기존 테스트 1건 갱신), Opus 4.8 도 실제 adaptive-only 라 사실 정합이 개선된다.
  - Opus 를 **대화 경로에만** 노출: `API_DEFAULT_MODEL` 은 haiku 유지, `AGENT_*_MODEL` 배선 없음. 근거 = 단가 5×(vs haiku)가 배치 볼륨에 곱해지는 것이 본 변경의 최대 비용 리스크. `.env.example` 에 금지 주석 명문화.
- **잔여 위험(정직 표기)**:
  - (R1) **root 계정 2순위 체인은 라이브 미검증** — 실증 시점에 root 가 계정 전체 한도 소진(haiku·sonnet 도 429, `unified-status: rejected`)이라 opus 만의 문제가 아님을 격리 확인했을 뿐, opus-chat-root 실 200 은 윈도우 리셋 후 확인 대상(배포 후 TEST Run 에 기록).
  - (R2) **모델별 접근 권한(RBAC) 부재** — 현 카탈로그는 `/api/session` 으로 전 사용자에게 동일 노출된다. `conversation.ask` 보유자면 누구나 Opus 선택 가능 → 조직 단위 비용 노출. per-model RBAC 은 신규 권한 표면(§12.3 Critical)이라 본 cycle 범위 밖 — REPORT §8 후속 과제로 이연하고 사용자에게 표면화.
  - (R3) litellm 이 `anthropic/claude-opus-5` 를 알고 있는지는 배포 후 gateway 실 ping 으로 최종 확정(직접 호출은 200 확인, gateway 경유는 미확인).
- 위험도: **Major(§12.3 — 외부 비용)**. 신규 자격증명 0(기존 두 OAuth slot 재사용), 인증/인가 경계 변경 0, 스키마 변경 0, 전 변경 additive(기존 haiku/sonnet 경로 byte-동치).
- Verification: feature-0002+0003 전체 pytest PASS(rc=0, 2452 tests, fail/error 0) · litellm YAML 파싱 OK(중복 0·dangling 0) · 라이브 직접호출 실증(위).
- Cross-ref: MODIFY CHG-20260727T184425-opus5-model / TEST.md Run 2026-07-27-opus5-model / shared/model_catalog.py `_ADAPTIVE_THINKING_PREFIXES`·`_CONVERSATION_ANSWER_ALIAS` / 선례 REV-20260724T113513-sonnet5-upgrade · REV-20260724T123503-cc-identity-inject.

## REV-20260727T190500-opus5-model-postdeploy [SKIPPED:post-deploy-live-evidence+copy-only] — PASS
- 대상: opus5-model 배포 후 라이브 확정 기록 + 관리 콘솔 pane 헤더 카피 1줄 정정(admin.html).
- 리뷰 방식([SKIPPED] 사유): 코드 변경은 **사용자-facing 카피 1줄**(동작·로직·경계 변경 0)이고, 나머지는 배포 후 관측 사실의 기록이다. 정본 적대 리뷰는 선행 REV-20260727T184425-opus5-model.
- 확정된 것: gateway 경유 200 → 선행 REVIEW 의 잔여 위험 **R3(litellm 이 `anthropic/claude-opus-5` 를 아는가) 해소**. PB-0008 실 브라우저 e2e 로 §16.6 UI-affecting 게이트 충족(시각 캡처 3종 첨부).
- 미해소로 남긴 것(정직 표기): **R1**(root 2순위 체인 — 실증 시점 root 계정 전체 한도 소진) · **R2**(모델별 RBAC 부재 — 사용자 결정 대기, REPORT §7).
- 위험도: Minor(§12.3) — 카피 변경 비파괴.
- Cross-ref: MODIFY CHG-20260727T190500-opus5-model-postdeploy / TEST Run 2026-07-27-opus5-model-POSTDEPLOY / 선행 REV-20260727T184425-opus5-model.

## REV-20260730T191535-ai-claude-feature-0007-llm-edge-free-routing [CODEX:llm-edge-free-routing] — CONCERN
- Related TASK: feature-0007-bedrock-llm-provider (TASK-20260730T191535-llm-edge-free-routing)
- Source: codex exec (OpenAI Codex v0.146.0, gpt-5.6-luna, `model_reasoning_effort=high`, read-only sandbox, `git diff --cached` 자가 수집)
- Trigger: 코드+설정 변경(라우팅 폴백 정책) — §18.8.1 경량 경로. 세션 도구 제약(subagent 미호출)과 무관한 채널을 우선 선택(§18.8.2 1번).
- Timestamp: 2026-07-30T19:15:35+09:00 (1차) / 재리뷰 동일 cycle
- Verdict: CONCERN (1차 P1 3건 → 2건 해소·1건 범위밖 이월 / P2 3건 + 재리뷰 P2 2건 전부 해소)

### 1차 리뷰 지적과 대응

| # | 지적 | 판정 | 대응 |
|---|---|---|---|
| P1-1 | 운영 `.env` 에 `AGENT_INSIGHT_OFFHOURS_MODEL=edge` 가 남아 staged 변경만으로는 라이브 강등이 안 꺼짐 | **유효** | `repo/.env` 값을 비움(백업 `.env.bak-llm-edge-free-20260730-193044`). `docker compose config` 로 `""` 파싱 실측. 인라인 주석이 값으로 새지 않도록 주석은 별 줄로 분리 |
| P1-2 | off-hours 테스트가 env override 존재 시 skip → **운영 환경에서 vacuous pass** | **유효(핵심)** | skip 제거. `test_offhours_downgrade_disabled_in_effective_config` 로 개명하고 **실효 설정**을 검사하도록 반전. 역검증: `AGENT_INSIGHT_OFFHOURS_MODEL=edge` 주입 시 skip 없이 FAIL 확인 |
| P1-3 | 문서가 "모든 LLM 요청은 claude 2계정 체인" 이라 주장하나 bare `claude-sonnet-4`·`claude-opus-5` 는 단일 계정 | **주장은 유효, 결함은 범위 밖** | 문서 주장을 "자동 강등 경로 없음"으로 **정정**(과장 제거). bare alias 단일계정은 *의도적 격리 설계*(probe/비대화 경로가 root 로 새지 않게 — opus5-model 2026-07-27 결정)이자 **가용성 축**이라 edge-free 결정과 직교. 뒤집으려면 별 결정이 필요하므로 REPORT §8 에 후속으로 명시 이월 |
| P2-1 | fallback 검사가 이름 토큰(edge/local/gemma) 문자열만 봐서 `ollama-fallback` 류가 통과 가능 | **유효** | 폴백 대상마다 (a) `model_list` 실재, (b) `litellm_params.model` 이 `anthropic/`, (c) `api_base` 부재를 전수 검증하도록 강화 |
| P2-2 | `_select_llm_provider()` 의 로컬 provider fallback 이 별도로 잔존 | **유효, 별 층** | litellm 폴백 체인과 다른 층(provider 선택). 운영은 `BEDROCK_GATEWAY_URL` 설정으로 미발동. REPORT §8 후속 이월 |
| P2-3 | YAML·config 주석이 "insight 야간·주말 gemma 강등 유지" 로 남아 신결정과 모순 | **유효** | `litellm_config.yaml` 2곳 + `shared/config.py` 1곳에 superseded 표기 |

### 재리뷰 (수정 후) 지적과 대응
- 확인된 것: `.env` 빈 값 · 대상 22건 PASS · `edge` 강제 시 skip 없이 FAIL · fallback 6개 전부 target 실재/`anthropic/`/`api_base` 없음/`edge-fallback` 미참조 · `git diff --cached --check` PASS.
- **[P2] off-hours 로컬 판정이 여전히 문자열 blocklist** → **해소**: allowlist 로 반전(`startswith("claude")` 강제). 역검증 `ollama/mistral` 주입 시 FAIL 확인.
- **[P2] `FUNCTION.md` §9 Error Handling 등에 폐기된 edge fallback 설명 잔존** → **해소**: FUNCTION.md §9 를 2계정 종단으로 재작성(이전 동작은 superseded 로 병기), `llm.py` docstring 이력에 superseded 표기.
- **[P1] bare alias 단일계정** → 위 P1-3 과 동일 항목. 이번 cycle 미해소, REPORT §8 이월(정직 표기).

### 판단 근거 (CONCERN 인 이유)
남은 P1 은 **본 변경이 만들어낸 결함이 아니라 기존 격리 설계의 가용성 갭**이고, 사용자 요청("로컬 LLM 미사용")과 직교한다. 그러나 "미해소" 인 것은 사실이므로 PASS 로 올리지 않고 CONCERN 으로 남기고 REPORT §8 에 명시한다. edge 안전망 제거로 **두 계정 동시 실패 창에서 기능이 실패**하는 trade-off 는 사용자 결정 사항이며 MODIFY/DECISIONS 에 정직하게 기록했다.

- Critical issue: bare `claude-sonnet-4`/`claude-opus-5` 는 fallback 미등록 단일 계정 — 빈 `.env` 기동 환경에서 claude-corp 429 시 즉시 실패(운영 `.env` 는 `-interactive` 지정이라 현재 라이브 영향 없음).
- Human Approval Needed: no (사용자 결정은 이미 수령 — 로컬 LLM 전면 미사용)
- Cross-ref: MODIFY CHG-20260730T191535-llm-edge-free-routing · DECISIONS ADR-003 · TEST Run 2026-07-30-llm-edge-free-routing · REPORT §8(후속 3건).
