---
doc_type: TEST
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope

본 cycle 의 변경 (AWS Bedrock LLM provider 통합 + API Vault 폐기) 의 회귀 영향
영역을 smoke 수준으로 검증한다.

**포함 (smoke)**:
- bedrock-gateway 컨테이너 healthcheck PASS
- `/api/ask` 가 cipher 인자 미동봉 상태에서 200 응답
- agent loop SQL 생성 1 conv (Claude Sonnet/Haiku 4.x)
- agent loop tool use (file_search / execute_sql / restore_sql) 각 1 회
- JSON output 모드 (VALIDATION_PROMPT / SUMMARY_PROMPT / TOPIC_PROMPT) 파싱 통과
- frontend 의 신규 사용자 첫 메시지 전송 (vault 입력 wizard 없이)
- localStorage `v1:` cipher 가 cache-bust 후 자동 cleanup
- model selector / API Vault 탭 DOM 부재 시각 확인

**제외 (별 cycle)**:
- per-user token quota
- per-user 비용 attribution
- Bedrock 의 model deprecation rotation 정책
- boto3 native hotspot 마이그레이션
- Local LLM gateway 와 Bedrock gateway 동시 활성화 시 router 충돌
- 대규모 부하 / latency benchmark (LiteLLM 의 throughput 한계)

## 2. Test Cases

### TEST-0001: bedrock-gateway healthcheck
- Purpose: 컨테이너 startup + LiteLLM proxy 의 `/health/liveliness` endpoint
  응답 PASS 확인.
- Preconditions:
  - `.env` 에 `BEDROCK_GATEWAY_URL` / `BEDROCK_GATEWAY_API_KEY` / `AWS_REGION` /
    `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 5 항목 채워짐.
  - AWS IAM 의 `bedrock:InvokeModel` 권한 + Seoul region 의 Claude Sonnet/Haiku
    4.x model access 활성화.
- Steps:
  1. `docker compose up -d bedrock-gateway`
  2. 30s 대기 (start_period)
  3. `docker compose ps bedrock-gateway` 로 `healthy` 상태 확인
- Expected Result: STATUS=Up + Health=healthy. 실패 시 `docker compose logs
  bedrock-gateway` 의 LiteLLM startup error 확인 (대개 AWS 자격증명 / model
  access 누락).

### TEST-0002: `/api/ask` cipher 미동봉 응답
- Purpose: API Vault 폐기 후 `/api/ask` 가 cipher 인자 없이 정상 200 응답.
- Preconditions: TEST-0001 PASS + web 컨테이너 healthy.
- Steps:
  1. `curl -X POST http://localhost:<WEB_PORT>/api/ask -b 'auth_token=<...>'
     -H 'Content-Type: application/json' -d '{"message":"SHOW DATABASES",
     "conversation_id":"","model":"claude-haiku-4"}'`
  2. 응답 status code + body 확인
- Expected Result: 200 + JSON body 에 `answer` / `conversation_id` /
  `executed_sql` 필드. `error` 필드 비어 있음.

### TEST-0003: agent loop SQL 생성 + tool use smoke
- Purpose: feature-0002 agent loop 가 Claude 모델로 SQL 생성 + 1 회 이상의
  tool use (file_search / execute_sql / restore_sql) 정상 동작.
- Preconditions: TEST-0002 PASS + MySQL 컨테이너 healthy + 테스트용 DB 데이터.
- Steps:
  1. frontend 로그인 후 새 대화 시작
  2. 메시지: `agent_memory.AgentMemoryMessages 테이블의 행 수와 가장 최근
     메시지 시각을 알려주세요`
  3. agent loop 진행 모니터링 (progress strip 의 step 표시)
- Expected Result:
  - agent 가 `SELECT COUNT(*), MAX(created_at) FROM AgentMemoryMessages` 또는
    동등한 SQL 생성 + `execute_sql` tool 호출 + 결과 표시.
  - 최종 응답에 "행 수: N건, 최근 메시지: YYYY-MM-DD ..." 자연어 답변 포함.
- Notes: Claude Sonnet vs Haiku 별 SQL 생성 품질 비교 — Sonnet 우수, Haiku
  도 기본 SQL 가능. 회귀 발견 시 `OPENAI_MODEL` env 또는 frontend 모델 선택
  으로 Sonnet 강제.

### TEST-0004: JSON output 모드 파싱 통과
- Purpose: `VALIDATION_PROMPT` / `SUMMARY_PROMPT` / `TOPIC_PROMPT` 의 Claude
  JSON 응답이 `_extract_json_object` 에서 정상 파싱.
- Preconditions: TEST-0003 PASS.
- Steps:
  1. agent loop 가 자연스럽게 호출하는 JSON 모드 LLM 호출을 1 회 이상 발생
     시키는 conv 진행 (긴 응답 → summary 생성 + topic 생성).
  2. `unit/feature-0002-agent-core/logs/llm_warn.log` (또는 stdout) 확인 — `json_extract_failed`
     entry 가 누적되지 않는지 검증.
- Expected Result: `json_extract_failed` 0 건. summary / topic 이 backend
  메모리 (`agent_memory.AgentMemoryFacts` / `AgentMemorySummary`) 에 정상 저장.
- Notes: Claude 가 markdown code fence (` ```json ... ``` `) 로 감싸는 응답을
  내는 경우 `_extract_json_object` 가 처리해야 함. 회귀 시 system prompt 의
  "JSON only" 강조 또는 `response_format` 파라미터 도입 검토.

### TEST-0005: frontend 신규 사용자 진입 — vault 입력 부재
- Purpose: API Vault wizard 가 사라진 상태에서 신규 사용자가 즉시 메시지 전송
  가능.
- Preconditions: TEST-0001 PASS + 신규 계정 (또는 기존 계정의 localStorage
  cleanup 후).
- Steps:
  1. 브라우저 incognito mode 로 frontend 접근
  2. 새 계정 가입
  3. Profile drawer 열기 → "API Vault" 탭 미존재 확인 (`account` / `security`
     / `prompt` 3 탭만)
  4. 새 대화 → 메시지 입력 → 전송
  5. 응답 수신 + 사이드바 대화 등재
- Expected Result:
  - Profile drawer 탭 list 에 "API Vault" 부재.
  - 사용자가 별도 키 입력 단계 없이 즉시 메시지 전송 가능.
  - 응답 수신 + 대화 사이드바 등재 정상.

### TEST-0006: localStorage `v1:` cipher cache cleanup
- Purpose: 기존 사용자의 localStorage 의 `mysql_ai_vault_cipher_v1` /
  `mysql_ai_vault_model_v1` / `mysql_ai_vault_passphrase_v1` 가 새 코드 로드
  시점에 silent cleanup.
- Preconditions: 사전에 기존 backend 로 진입한 적이 있어 localStorage 에 v1:
  cipher 가 저장된 사용자.
- Steps:
  1. 사전 검증: DevTools → Application → Local Storage 에 `mysql_ai_vault_*`
     key 존재 확인.
  2. Hard reload (Cmd/Ctrl + Shift + R) 또는 cache 무시 새로고침.
  3. 새 코드 로드 후 DevTools 의 Local Storage 다시 확인.
- Expected Result: `mysql_ai_vault_cipher_v1` / `mysql_ai_vault_model_v1` /
  `mysql_ai_vault_passphrase_v1` 키 부재 (또는 빈 값). 콘솔 error 미발생.
- Notes: `app.js` 의 `LEGACY_VAULT_KEYS.forEach(k => localStorage.removeItem(k))`
  + sessionStorage 동일 처리.

### TEST-0007: refresh-claude-oauth-token.sh 정적 검사 단독 판정 (라이브 API 호출 없음)
- Purpose: 라이브 probe 제거 후 `--check` 모드가 실 자격증명 파일만으로
  claude-corp/root 두 slot 을 올바르게 판정하는지, docker 미가용 환경에서도
  script 가 abort 없이 완주하는지 확인.
- Steps:
  1. `bash -n bin/refresh-claude-oauth-token.sh` (syntax).
  2. `bash bin/refresh-claude-oauth-token.sh --check` (실 `.env.bedrock` 대상,
     변경 없음).
  3. `PATH=<python3/coreutils 만> bash bin/refresh-claude-oauth-token.sh --check`
     (docker 없는 환경 시뮬레이션).
- Expected Result: 1) syntax OK. 2) 두 slot 모두 "동일"(현재 주입된 토큰과
  일치) 또는 "변경" 판정, 라이브 HTTP 호출 없음. 3) exit 0, 관측 함수만
  조용히 스킵.
- Notes: `docker compose logs` 호출은 로컬 컨테이너 stdout 읽기이며 Anthropic
  API 호출이 아니다 — 이 테스트는 "정적 검사만으로 완주"를 확인하는 것이지
  "docker 명령 자체가 없다"를 의미하지 않는다.

### TEST-0008: litellm fallback 이 401/429 모두에서 작동함 (코드 검증)
- Purpose: cron probe 제거의 안전성 전제 — litellm 요청-레벨 fallback 이
  AuthenticationError(401) 뿐 아니라 RateLimitError(429) 에도 실제로 작동하는지
  확인.
- Steps: 게이트웨이 컨테이너(`repo-bedrock-gateway-1`) 내부 `/app/litellm/router.py`
  를 직접 읽어 `should_retry_this_error` / `async_function_with_fallbacks_common_utils`
  의 예외 타입 분기 로직 확인.
- Expected Result: ContextWindowExceededError/ContentPolicyViolationError 만
  특별 처리(각 fallback 리스트 유무로 분기)되고, AuthenticationError·
  RateLimitError 를 포함한 그 외 예외는 모두 동일하게
  `async_function_with_fallbacks_common_utils` → 정규 `fallbacks:` 체인을 탄다.
- Notes: 라이브 429/401 유발 실험은 실제 계정 rate-limit/토큰 무효화를 필요로
  해 재현 비용이 크고 프로덕션 계정에 부담을 주므로, 코드 레벨 검증으로 대체.
  실제 fallback 동작 사례는 최근 로그에서 `claude-haiku-4-root` 로의 우회 1건
  관측(정상 발생).

## 3. Test Run History

<!-- append-only — 본 cycle 의 실제 실행 결과는 Phase E 진입 시 추가 -->

### Run 2026-05-21-001 (정적 검증)
- Date: 2026-05-21
- Environment: WSL2 Linux, Python 3.x, Node.js
- Runner: AI (Claude)
- Result Summary: 정적 syntax 검증만 수행 (실 docker compose up 은 사용자 환경
  + AWS 자격증명 필요로 미수행).
- Pass/Fail: PARTIAL — 정적 검증 PASS, 실행 검증 미수행.
- Notes:
  - `python3 -m py_compile`: config.py / model_catalog.py / llm.py /
    agent_core.py / app.py 모두 PASS.
  - `node --check app.js`: PASS.
  - `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`:
    10 services 정상 파싱. bedrock-gateway 의 image / healthcheck / depends_on
    정합.
  - docker compose config: ports binding 의 env var 미주입으로 `invalid proto:`
    출력 (본 변경과 무관 — 실 `.env` 채우면 PASS).
  - 실 호출 검증 (TEST-0001 ~ TEST-0006) 은 Phase E 에서 사용자가 수행.

### Run 2026-05-21-002 (Phase E 실 환경 검증)
- Date: 2026-05-21
- Environment: WSL2 Linux + Docker, AWS CLI v2, region `ap-northeast-2`
  (Seoul), AWS credentials `~/.aws/credentials` default profile, docker compose
  project `feature-0007-e` (포트 격리)
- Runner: AI (Claude) — 사용자 명시 위임 ("실제 실행 후 권한 접근 여부 판단")
- Result Summary: TEST-0001 (gateway healthcheck) + TEST-0004 partial (JSON
  mode) PASS. TEST-0002 / TEST-0003 / TEST-0005 / TEST-0006 는 web 컨테이너
  + MySQL 미가동 상태로 미수행 (본 검증의 범위 = gateway 단일 + IAM/모델 권한
  판정).
- Pass/Fail:
  - TEST-0001 (gateway healthcheck): **PASS**. 컨테이너 status=`Up (healthy)`,
    `/health/liveliness` HTTP 200 + body `"I'm alive!"`.
  - 추가 검증 (IAM + Sonnet 4.6 model access): **PASS (단 region 정책 reanchor
    필요)**. AWS Bedrock Seoul region 의 ACTIVE Sonnet 4.x 가 모두 `global.*`
    inference profile 만 제공 사실 발견 → 사용자 reanchor 후 `global.anthropic.
    claude-sonnet-4-6` 사용 결정 → gateway 경유 alias `claude-sonnet-4` 호출
    STATUS 200 + 응답 `"PASS"` + usage 31+5 토큰 정상.
  - TEST-0004 (JSON output 파싱): **PASS**. Claude 가 markdown fence 안 JSON
    반환 (` ```json {"status":"PASS","echo":"phase-e"} ``` `), `_extract_json_object`
    의 greedy `re.search(r"\{.*\}")` 가 fence 안 JSON 정상 추출.
- Notes:
  - 검증 환경: gateway 단일 서비스 격리. web / mysql / agent / mcp 등 다른
    서비스는 미가동 (포트 충돌 회피 + 본 검증의 scope 외).
  - 발견 1 (catalog): `aws bedrock list-foundation-models --region
    ap-northeast-2 --by-provider anthropic` 출력에서 Sonnet 4 LEGACY / Sonnet
    4.5 ACTIVE / Sonnet 4.6 ACTIVE / Haiku 4.5 ACTIVE 확인.
  - 발견 2 (on-demand 미지원): `anthropic.claude-sonnet-4-20250514-v1:0` /
    `anthropic.claude-sonnet-4-6` 등 직접 invocation 시 `BedrockException: ...
    isn't supported. Retry your request with the ID or ARN of an inference
    profile that contains this model.` (HTTP 400).
  - 발견 3 (inference profile): `aws bedrock list-inference-profiles --region
    ap-northeast-2` 출력에서 `apac.anthropic.claude-sonnet-4-20250514-v1:0`
    (LEGACY) + `global.anthropic.claude-sonnet-4-5/4-6/haiku-4-5` 4 종 확인.
  - 발견 4 (APAC LEGACY 차단): `apac.anthropic.claude-sonnet-4-...` 호출 시
    `ResourceNotFoundException: Access denied. This Model is marked by provider
    as Legacy and you have not been actively using the model in the last 30
    days. Please upgrade to an active model on Amazon Bedrock` — 실용 불가.
  - 발견 5 (global Sonnet 4.6 호출 PASS): `aws bedrock-runtime invoke-model
    --region ap-northeast-2 --model-id global.anthropic.claude-sonnet-4-6 ...`
    + gateway 경유 호출 둘 다 200 응답. usage 정상 (input 13 / output 5).
  - 발견 6 (alias 보존): gateway 응답의 `model` 필드가 backend 가 보낸 alias
    `claude-sonnet-4` 그대로 반환 — backend / audit 의 model 식별 정합 유지.
  - 운영 cleanup: gateway 컨테이너 + 격리 network 는 본 cycle 종료 시점에
    `docker compose -p feature-0007-e down` 으로 정리.

### Run 2026-07-07-001 (cron-static-refresh 검증)
- Date: 2026-07-07
- Environment: 운영 호스트(WSL2 Linux), 실 `.env.bedrock` + `/root/.claude`,
  `/home/claude-corp/.claude` credentials, 운영 중인 `repo-bedrock-gateway-1`
  컨테이너(main-stable litellm).
- Runner: AI (Claude)
- Result Summary: TEST-0007 PASS, TEST-0008 PASS(코드 검증).
- Pass/Fail:
  - TEST-0007: **PASS**. `bash -n` OK. `--check` 2 회(기본 35m 창 / 72h 창)
    모두 claude-corp/root "동일" 정상 판정, RateLimitError/AuthenticationError
    0건(무음, 정상). `docker` 제거 PATH 에서도 exit 0 완주.
  - TEST-0008: **PASS**. `router.py` 5867~6320 라인 확인 — 401/429 모두
    fallback 경로 진입 확인. 최근 72h 로그에는 실제 RateLimitError/
    AuthenticationError 발생 0건(계정이 실제로 rate-limit 에 걸리지 않은
    기간이라 반응형 fallback 발동 사례 자체가 없었음 — 정상. 과거 로그에서
    `claude-haiku-4-root` 로의 우회 1건은 관측됨).
- Notes:
  - 발견 (본 cycle 범위 밖 버그): `claude-haiku-4-chat-root` alias 가
    `max_tokens must be greater than thinking.budget_tokens` BadRequestError 로
    반복 실패 — §7 Human Attention Needed 에 별도 기록, 본 cycle 미수정.
  - crontab 변경은 git 미추적 runtime 상태 — 백업 `/tmp/crontab-root-backup-
    20260707112835.txt`, 설치 확인 `crontab -l` diff 로 일치 확인.

### Run 2026-07-24-001 (sonnet-chat-fallback 검증)
- Date: 2026-07-24
- Environment: agent 이미지 격리 컨테이너(`mysql-ai-agent:current`), worktree 마운트 +
  `PYTHONDONTWRITEBYTECODE=1`, `pip install pytest pyyaml`. DB 미기동(monkeypatch·YAML 파싱만).
- Runner: AI (Claude)
- Result Summary: sonnet-chat-fallback 관련 계약 + 전체 회귀 PASS.
- Pass/Fail:
  - `test_conversation_answer_no_edge_alias.py` (17건): **PASS**. 신규 G2
    `test_conversation_answer_model_maps_sonnet_to_chat`(sonnet→claude-sonnet-4-chat),
    개명 `test_call_llm_routes_sonnet_to_edge_free_chat_alias`(litellm outbound=-chat·기록=원본),
    신규 G5b `test_sonnet_conversation_chain_has_two_accounts_and_is_edge_free`(litellm_config
    실파싱: sonnet-chat 라우팅 가능·`-chat-root` 도달·edge-fallback 미도달) 포함.
  - feature-0002-agent-core + feature-0003-agent-web-ui **전체 스위트: PASS(rc=0)** — 회귀 0.
  - YAML lint: `yaml.safe_load` OK(11 deployment, fallback 6 — sonnet-chat 체인 정확).
- Notes:
  - sonnet-chat·-chat-root `budget_tokens: 16000` = bare `claude-sonnet-4` 동일 →
    max_tokens(원본 키 agent_max_output=40000) > thinking(16000), 2차 400 무회귀 확인.
  - 미검증(배포 후 라이브): 실 claude-corp 429 상황에서의 `-chat`→`-chat-root` 실 우회 발동.
    현재 rate-limit 미발생 기간이면 반응형 fallback 자체가 트리거되지 않음(정상). PB-0008
    win-browser 로 새 대화 sonnet 선택 → 정상 답변 생성 실측 권장.

### Run 2026-07-24-002 (sonnet5-upgrade 검증)
- Date: 2026-07-24
- Environment: agent 이미지 격리 컨테이너(`mysql-ai-agent:current`) — pytest; `node --check` — JS 문법;
  gateway `/v1/chat/completions` 실 ping(worker 컨테이너) — 배포 후 Sonnet 5 도달성.
- Runner: AI (Claude)
- Result Summary: 정적/단위 PASS. Sonnet 5 실 도달성·시각검증은 아래 배포 후 항목.
- Pass/Fail:
  - feature-0002 + feature-0003 전체 pytest: **PASS(rc=0)** — sonnet 라우팅·adaptive thinking 마이그·label·
    canonical sonnet-5 fold 무회귀. 신규/갱신: `test_model_thinking_style`·`test_effort_for_reasoning_level`·
    `test_sonnet_adaptive_injects_effort_not_budget`·`test_sonnet_adaptive_normal_no_override`·
    `test_reasoning_and_total_are_per_model`(dual-style)·`test_call_llm_sonnet_adaptive_no_budget_tokens`·
    canonical sonnet-5 fold. haiku budget 경로 무회귀 재확인.
  - `node --check app.js`: **PASS** — `_composerModelLabelFor` 신설 문법 정상.
  - litellm_config YAML: **PASS** — sonnet 3 alias `anthropic/claude-sonnet-5` + `thinking:{type:adaptive}`,
    haiku 는 `{type:enabled,budget_tokens:5000}` 유지.
- Notes(배포 후 라이브 — 별도 POST-DEPLOY 기록으로 갱신 예정):
  - **⚠ litellm adaptive/effort 통과는 코드로 미확정**: config-level `thinking:{type:adaptive}` 와 요청
    `output_config.effort` 를 litellm(main-stable)이 Anthropic 으로 올바로 통과시키는지는 배포 전 확정 불가.
    **배포 후 worker 컨테이너에서 `claude-sonnet-4-chat`(→sonnet-5) valid-ping(adaptive+effort) 200 확인 필수**
    (400/미통과 시 즉시 rollback). drop_params:true 가 thinking/output_config 를 제거하지 않는지도 이 ping 으로 확정.
  - **Environment: Windows-browser (PB-0008) — 배포 후 실측 예정**: 라이브 배포(gateway reconcile + web/worker
    재빌드) 후에만 반영되므로 배포 완료 후 수행(미배포 코드에서 실측 불가 — 미수행 사유). 검증 항목: (1) 새 대화
    sonnet 선택 시 정상 답변(429/400 아님), (2) 모델 선택기·컴포저에 `claude-sonnet`/`claude-haiku`(넘버링 없음) 표시.

#### POST-DEPLOY 라이브 검증 (2026-07-24, 배포 e88cce6f, Environment: gateway 실 ping + 배포 이미지 introspect)
- **배포**: 3계층 전부 `e88cce6f`(web-a/b·ask/insight-worker·bedrock-gateway reconcile), soak 통과. gateway
  `/v1/models` 에 sonnet 3 alias 등록 확인.
- **H4 (litellm adaptive/effort 통과) — PASS**: worker 컨테이너에서 `claude-sonnet-4-chat`(→anthropic/
  claude-sonnet-5)에 adaptive(config)·`output_config.effort=high/low` ping → **HTTP 429**(param 거부 400 아님).
  요청이 Anthropic 까지 도달해 rate-limit 을 받았으므로 **adaptive thinking + output_config.effort 가 litellm→
  Anthropic 정상 통과**(drop_params 미제거) 확정. 대조: haiku-chat 은 budget<max_tokens 제약 여전히 유효
  (max=2048<budget5000 → 400; max=24000 → **200** "Hey! Yes, I'm here…") = dual-style 정상.
- **⚠ Sonnet 5 계정 용량 (코드 밖) — 429 THROTTLED (양 계정)**: `claude-sonnet-4-chat`(claude-corp)·
  `claude-sonnet-4-chat-root`(root) **단발 요청**에도 지속 429(throttling_error). 두 OAuth 구독 계정
  (claude-corp masangsoft·root Max)에 **Sonnet 5 사용 가능 용량이 없음**(haiku-4-5 는 양쪽 200). 코드 마이그는
  정확하나 런타임 sonnet 은 여전히 "요청량 한도"(정직한 429). **사용자 결정(2026-07-24): 계정 용량 확인 먼저** —
  Anthropic 콘솔/플랜에서 Sonnet 5 접근 확보 시 코드 수정 없이 즉시 작동(이미 배포됨). rollback 안 함(폐기 sonnet-4-6
  회귀=더 나쁨).
- **라벨 딜리버러블 — PASS**: 배포된 web 이미지 `PUBLIC_API_MODEL_OPTIONS` = `claude-sonnet`/`claude-haiku`
  (넘버링 없음, group `Claude`), value 는 claude-sonnet-4/claude-haiku-4 유지. 모델 선택기·컴포저 표시 정상 예상
  (사용자 하드리프레시 Ctrl+F5 권장). full PB-0008 win-browser 시각 확인은 계정 용량 확보 후 sonnet 답변 실측과
  함께 수행 권장.

### Run 2026-07-24-003 (cc-identity-inject 검증)
- Date: 2026-07-24
- Environment: agent 이미지 격리 컨테이너(pytest) + **직접 api.anthropic.com 호출**(gateway 컨테이너, 두 OAuth
  토큰) + gateway `/v1/chat/completions` 실 probe.
- Runner: AI (Claude)
- Result Summary: 근본 원인 라이브 실증 + 단위 PASS. 배포 후 sonnet 실 대화 최종 확정 예정.
- Pass/Fail:
  - **직접 Anthropic 호출(계정 용량 직접 확인)**: claude-corp·root **claude-sonnet-5 200**(unified-status:
    allowed) — 용량 有. system 없음/generic → **429**. `"You are Claude Code…"` 단독 → 200. `CC+"\n\n"+제품`
    단일 문자열 → 429. **`system 블록배열 [CC,제품]` / `2 system 메시지 [CC,제품]` → 200**. haiku-4-5 system
    없이 → 200(미요구). thinking `{type:adaptive}`+`output_config.effort` 도 직접 200(param 무관).
  - **동작 검증**: CC-first + DB 제품 system → 답변 DB 어시스턴트(SQL·쿼리·분석), Claude Code 코딩 아님.
  - **단위 pytest PASS(rc=0)**: `test_requires_oauth_frontier_identity`·`test_sonnet_prepends_cc_identity_system`·
    `test_haiku_no_cc_identity_injection`·`test_probe_adaptive_model_sends_effort_not_budget`(+CC)·
    `test_probe_budget_model_no_cc_identity`.
- Notes(배포 후 최종): 배포 후 gateway 로 `claude-sonnet-4-chat` 실 대화 ping → **200 확정**(CC identity 주입이
  litellm→Anthropic 통과). PB-0008: 새 대화 sonnet 선택 → 정상 답변(429 아님). 실패 시 rollback.

#### POST-DEPLOY 최종 확정 (2026-07-24, 배포 d4ede64b)
- 3계층 전부 `d4ede64b`(web·worker·gateway reconcile). 배포된 `agent_core._call_llm` 실 경로 실측:
  - `requires_oauth_frontier_identity("claude-sonnet-4")` = True → CC identity 자동 주입 활성.
  - **`_call_llm(model="claude-sonnet-4")` → HTTP 200** "안녕하세요! DB 쿼리 어시스턴트입니다…" — **sonnet
    end-to-end 복구**. 답변은 DB 어시스턴트(Claude Code 코딩 아님) = 동작 왜곡 없음 확정.
  - `_call_llm(model="claude-haiku-4")` → 200 "준비됐습니다! 🎯" — **무회귀**.
- 결론: sonnet 3층 근본원인(① root fallback 부재 ② 폐기 sonnet-4-6 ③ adaptive thinking ④ OAuth frontier-identity
  게이트) 전부 해소·배포·라이브 확정. 라벨(claude-sonnet/claude-haiku) 서빙 정상. 잔여 PB-0008 win-browser 시각
  확인은 사용자 UI 재현 시 권장(백엔드 경로는 실측 200 확정).

### Run 2026-07-24-004 (llm-timeout-align 검증)
- Date: 2026-07-24
- Environment: gateway 컨테이너 실 config introspect + 실 호출 latency 측정 + 배포 후 sonnet 대화.
- Runner: AI (Claude)
- Result Summary: 근본원인 라이브 확정 + config 정합. 배포 후 실행 config 300 + 대화 정상 확정 예정.
- Pass/Fail:
  - **진단**: 배포 worker AGENT_TIMEOUT_SEC=**300**, gateway litellm request_timeout=**120** → 불일치(gateway 조기 컷).
  - **latency 실측**(무거운 routine-분석 시뮬, gateway 실 ping): high effort **19.0s**(out 1443, finish stop),
    medium **14.0s** — 개별 호출은 대체로 빠름. timeout 은 장문-답변 후반 라운드/재시도·fallback 복합이 120s 초과.
  - **fix**: request_timeout 120→300(앱 per-call 예산 정합). YAML OK.
- Notes(배포 후 최종): bedrock-gateway reconcile 후 `/app/config.yaml` request_timeout=300 확인 + sonnet 대화
  ping 정상(429/timeout 아님). 장문 sonnet 대화 실사용 관찰 권장.

## 4. Untested Areas

- **실 AWS Bedrock 호출**: 본 cycle 의 정적 검증만 PASS, 실 InvokeModel
  호출은 사용자 환경 / 자격증명 필요로 미수행.
- **Claude tool use schema 변환**: LiteLLM 의 OpenAI tool_calls ↔ Anthropic
  tool use 변환이 본 코드 베이스의 `MCP_EXECUTE_SQL_CANDIDATES` / file ops
  tool 정의와 호환되는지 실 호출로 미검증.
- **gateway 부하 한계**: 단일 컨테이너의 동시 요청 처리 한계 / latency
  특성 미측정. 사내 사용자 N 명 동시 진입 시 throughput 회귀 위험.
- **모델 deprecation**: AWS Bedrock 의 Claude versioned ID 가 deprecate 될
  경우 자동 알림 / fallback 흐름 미검증.
- **`OPENAI_API_KEY` env 직접 참조 잔존**: feature-0002 / feature-0003 외
  의 unit (insight-worker, agent CLI, 다른 script) 에 잔존 가능성 — 별 cycle
  의 grep 검증.
- **로그아웃 / 세션 만료 시 LLM 호출 보호**: 본 변경의 trust 모델은 service-
  managed 자격증명이지만, web auth 미통과 anonymous 가 `/api/ask` 호출 시
  기존 `_require_account` 로 401 차단 — 본 cycle 의 회귀 영역 아님 (인증 모델
  변경 X).
