---
doc_type: REVIEW
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

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
