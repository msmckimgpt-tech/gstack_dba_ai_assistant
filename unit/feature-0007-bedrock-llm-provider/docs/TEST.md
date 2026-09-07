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

### Run 2026-07-27-opus5-model
- Date: 2026-07-27 18:44 KST
- Environment: CLI (컨테이너 pytest + gateway 컨테이너 라이브 직접호출) — **웹 UI 표면 미검증(PB-0008 배포 후)**
- Scope: assistant 선택 모델 Claude Opus 5 추가 (CHG-20260727T184425-opus5-model)
- Runner: AI (Claude)
- Result Summary: 코드/구성 검증 PASS + Opus 5 OAuth 접근성 라이브 확증. 배포 후 gateway 경유 e2e + PB-0008 잔여.
- Pass/Fail:
  - **라이브 사전 실증**(gateway 컨테이너 → api.anthropic.com 직접, 토큰 미노출):
    - `[corp/claude-opus-5/nosys]` HTTP **429** — `{"type":"rate_limit_error","message":"Error"}`, unified-status 헤더 **없음** (identity 게이트 시그니처)
    - `[corp/claude-opus-5/cc]` HTTP **200** — `model=claude-opus-5`, `stop_reason=end_turn`, `unified-status: allowed` ✅
    - `[root/claude-opus-5/cc]` HTTP 429 — `"would exceed your account's rate limit"`, `unified-status: rejected`
    - 격리 대조 `[root/claude-haiku-4-5]` · `[root/claude-sonnet-5]` **동일 429/rejected**(reset epoch 1785159600)
      → root 429 는 **계정 전체 한도 소진**이지 Opus 모델 게이팅 아님. (R1: 리셋 후 재확인)
  - **단위 테스트**: feature-0002 + feature-0003 전체 `pytest -q` **rc=0, 2452 tests, fail 0 / error 0**.
    신규·갱신 8건 — `test_conversation_answer_model_maps_opus_to_chat`,
    `test_opus_conversation_chain_has_two_accounts_and_is_edge_free`(config 실파싱 5 단정),
    `test_call_llm_opus_adaptive_with_cc_identity`, `test_opus_adaptive_injects_effort_not_budget`,
    `test_opus_adaptive_normal_no_override`, `test_opus_prepends_cc_identity_system`,
    runtime registry/API adaptive_models·budget-스펙-미생성, usage canonical fold + 단가.
  - **litellm config 정적 검증**: YAML 파싱 OK · `model_name` 중복 0 · fallback dangling ref 0 ·
    opus 체인 `claude-opus-5-chat → claude-opus-5-chat-root`(edge 미도달) · bare `claude-opus-5` fallback 미등록(격리).
- Notes(배포 후 확정 대상): ① gateway reconcile 후 `/app/config.yaml` 에 opus 3 deployment 반영 ②
  대화에서 `claude-opus` 선택 → 실 답변 200(gateway 경유 라우팅 확정, R3) ③ PB-0008 — 모델 선택기 노출·
  추론강도 활성·관리 콘솔 '모델 총 출력' opus 행 + guide-note ④ R1 root 2순위 체인 ⑤ 'LLM 사용량' 도넛에
  claude-opus-5 세그먼트 + 비용 > $0.

### Run 2026-07-27-opus5-model-POSTDEPLOY
- Date: 2026-07-27 19:05 KST
- Environment: **Windows-browser** (`bin/win-browser.py`, PB-0008, Chrome/150.0.7871.115 · relay) + 라이브 컨테이너
- Scope: opus5-model 배포 후 확정 (배포 SHA `413703b9`, `bin/deploy-web.sh` scope=all — web 롤링 + 워커 + gateway surge 교체, soak 통과)
- Runner: AI (Claude)
- Result Summary: **PASS** — 사용자 실경로 e2e 성립. 잔여는 R1(root 한도 리셋 후 2순위 체인)뿐.
- Pass/Fail:
  - **gateway config 반영**: `/app/config.yaml` model_list 에 `claude-opus-5` / `-chat` / `-chat-root` 3종 존재 ✅
    (deploy-web 로그: "gateway 드리프트 감지: litellm config 변경 → surge 무중단 교체 완료")
  - **gateway 경유 라우팅**(web-a 컨테이너 → bedrock-gateway): `claude-opus-5-chat` **HTTP 200**
    (`resolved=claude-opus-5-chat`, 본문 `OPUS-LIVE-OK`) · bare `claude-opus-5` **HTTP 200** ✅ → R3 해소
  - **카탈로그 직렬화**(라이브 web): `PUBLIC_API_MODEL_OPTIONS` = opus/sonnet/haiku 3종,
    `API_DEFAULT_MODEL=claude-haiku-4`(기본 불변) · `adaptive_models=['claude-opus-5','claude-sonnet-4']` ·
    `agent_max_output:claude-opus-5` 생성 · `reasoning_budgets` 모델 = haiku 뿐(opus 죽은 스펙 0) ✅
  - **PB-0008 ① 모델 선택기**(실 Windows 브라우저, 로그인 상태): 컴포저 '+' → '모델' 메뉴에
    `claude-opus`(설명 "Anthropic Claude Opus (frontier 최상위, 장기 추론·에이전트 작업)")가 **최상단**,
    `claude-haiku` 에 ✓(기본값 유지) ✅ — evidence `docs/evidence/pb0008-opus5-model-menu-20260727.png`
  - **PB-0008 ② 실 대화 e2e**: 메뉴에서 `claude-opus` 실제 클릭 → 컴포저 라벨 `claude-opus` 전환 →
    프롬프트 전송 → **7초(준비 1.7초 · 추론 5.3초)만에 정답 `OPUS-PB0008-OK` 렌더**, 상태 done ✅
    — evidence `docs/evidence/pb0008-opus5-live-answer-20260727.png`
  - **사용량 원장 계약**(PG `agent_runtime.llm_usage`): `task=agent` 행이 `model=claude-opus-5`(원본 alias 보존) /
    `resolved_model=claude-opus-5-chat`(실 서빙) 로 기록 ✅ — 설계한 표시/집계 계약과 정확히 일치.
    추가로 `task=redteam` 행이 `claude-opus-5-chat` 으로 기록 → **red-team 리뷰어 모델 자동 정합 실동작 확인**
    (코드 변경 0 — `conversation_answer_model` 재사용 경로).
  - **비용 귀속**: 배포 이미지 단가표에 `claude-opus-5={in:5.0,out:25.0}` 반영. 실 행 계상 —
    agent 행 39,552/14 tok → **USD 0.1981**($0 오표시 아님), `-chat` 변형도 canonical fold 로 동일 family.
    1M/1M 기준 opus 30.0 > sonnet 18.0 > haiku 6.0 (tier 순서 정합) ✅
  - **PB-0008 ③ 관리 콘솔**(시스템 > 설정 > 모델별 추론 예산): `CLAUDE-OPUS` 카드 = 라운드당 40,000 tokens ·
    '즉시 반영' 배지 · **'추론 강도 (ADAPTIVE THINKING)' guide-note** 렌더("…모델별 thinking budget(토큰)
    설정은 적용되지 않아 감췄습니다") · **죽은 budget 슬라이더 0** ✅
    — evidence `docs/evidence/pb0008-opus5-admin-budget-pane-20260727.png`
- 발견·수정(같은 cycle): 위 pane 헤더 카피가 `max_tokens, Sonnet 128K / Haiku 64K 까지` 로 남아 Opus 를
  누락(본 변경으로 stale 해진 문구) → `Opus·Sonnet 128K / Haiku 64K` 로 정정(admin.html).
- 잔여(R1): root(개인 Max) 계정이 실증 시점 전 모델 429(`unified-status: rejected`) — 한도 윈도우 리셋 후
  `claude-opus-5-chat-root` 실 200 재확인 필요. 1순위(claude-corp) 경로는 위와 같이 정상.

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

### Run 2026-07-30-llm-edge-free-routing
- Date: 2026-07-30 · Environment: `CLI` (pytest, 컨테이너 `repo-unittest`) + 라이브 게이트웨이 프로브
- Scope: 자동 gemma(edge) 강등 경로 제거 (CHG-20260730T191535-llm-edge-free-routing / ADR-003)
- **원인 확정 (라이브 관측, 수정 전)**
  - `sudo docker inspect repo-bedrock-gateway-1 --format '{{.State.StartedAt}}'` → `2026-07-30T09:00:27Z`(=18:00:27 KST) 재생성.
  - `docker logs --timestamps` grep `name resolution` → 첫 실패 `09:00:38`(기동 시 cost-map fetch), 마지막 `09:34:04`. 10분 윈도우당 **308건**.
  - 실패 메시지: `AnthropicException - Cannot connect to host api.anthropic.com:443 ... [Temporary failure in name resolution]` — 계정 오류(401/429) 아님. 같은 창에서 `claude-haiku-4-meta-root`(edge 없음)는 `500 Internal Server Error` 로 종단 실패.
  - 자격증명 대조: root `expiresAt=2026-07-30 23:30:08`, claude-corp `2026-07-31 01:58:46` — 둘 다 유효. 게이트웨이 주입 토큰(`ANTHROPIC_API_KEY`/`_ROOT`) 존재 확인.
  - 복구 확인(수정 전, 18:47): 컨테이너에서 `getaddrinfo("api.anthropic.com", 443, AF_UNSPEC)` → `['160.79.104.10', '2607:6bc0::10']` 정상. 게이트웨이 프로브 `claude-haiku-4-interactive`(max_tokens=5600 — thinking budget 5000 초과 필수) → **HTTP 200, served=claude-haiku-4-interactive**, `claude-haiku-4-chat` → **200**. 즉 DNS 는 자연 복구됐고 결함은 "그 창에서 edge 로 흐른 구조" 다.
- **단위 검증 (수정 후)**
  - `make test` (컨테이너 `repo-unittest`, 라이브 네트워크 미참여): pytest rc=0 · ruff `All checks passed!`.
  - 대상 3파일(`test_llm_edge_free_routing.py` 신규 · `test_meta_llm_edge_free.py` · `test_insight_offhours_routing.py`) 22건 통과(운영 `.env` 복사 환경이라 env override 로 2건 skip).
  - env override 제거 조건(`AGENT_INSIGHT_OFFHOURS_MODEL=`, `AGENT_NODE_ANALYSIS_MODEL=`)에서 신규·갱신 **10건 PASS, skip 0** — 기본값 계약(강등 기본 비활성)이 실제로 검증됨을 확인.
  - 경계 양측(§16.7 G4): `_effective_insight_model` 을 근무시간 내(화 14:00 KST) · 경계 직후(화 19:00 KST) · 심야(수 03:00 KST) · 주말(토 14:00 KST) 4지점에서 확인 → 전부 `claude-haiku-4`.
- **미수행 / 이월**
  - 배포 후 라이브 재확인(gateway config reconcile + `.env` OFFHOURS 비움 후 서빙 모델 실측)은 배포 단계에서 수행 → 결과는 본 Run 하단 또는 POSTDEPLOY Run 에 추가.
  - UI 표면 변경 없음(설정·라우팅 전용) → PB-0008 Windows-browser 검증 **비해당**(§15.4.1 예외: 변경에 UI 표면 없음).

#### Run 2026-07-30-llm-edge-free-routing — 적대검증 반영 후 재검증 (역검증 포함)
- codex review(2회) 지적 반영 후 재실행. `test_llm_edge_free_routing.py` 5건 PASS.
- **역검증(테스트가 실제로 잠그는지)**: 의도적 위반 주입 시 FAIL 하는지 확인 — `AGENT_INSIGHT_OFFHOURS_MODEL=edge` → FAIL(skip 없음), `=ollama/mistral` → FAIL(allowlist `startswith("claude")` 작동). 통과만 보고 "잠겼다" 고 결론내지 않았다.
- **운영 `.env` 반영**: `repo/.env` 의 `AGENT_INSIGHT_OFFHOURS_MODEL` 을 빈 값으로 변경(백업 `.env.bak-llm-edge-free-20260730-193044`). `docker compose config` 로 `AGENT_INSIGHT_OFFHOURS_MODEL: ""` 파싱 실측 — 인라인 주석이 값으로 새지 않도록 주석은 별 줄로 분리했다.
- fallback 정적 검증: 폴백 6개 전부 (a) `model_list` 실재, (b) `anthropic/` provider, (c) `api_base` 없음, (d) `edge-fallback` 참조 0건.

### Run 2026-07-30-llm-edge-free-routing-POSTDEPLOY
- Date: 2026-07-30 19:59 KST · Environment: `CLI` (라이브 배포본 실측) · 배포 SHA **9c4e9935** (PR #1097 머지 → `bin/deploy-web.sh` scope=all)
- 배포 경로: web 롤링(a→b, soak 통과) → 워커 핀 이미지 롤아웃(`mysql-ai-agent:9c4e9935`) → **bedrock-gateway 드리프트 감지(litellm config `3166d1b9a8a5` ≠ `be14d75dd402`) → surge replica 무중단 교체**.
- **검증 1 — 게이트웨이 실 config (컨테이너 내부 `/app/config.yaml` 파싱)**: fallback 6개 전부 2계정 종단이고 `edge`/`local` 참조 **NONE**.
  ```
  claude-haiku-4             -> ['claude-haiku-4-root']
  claude-haiku-4-interactive -> ['claude-haiku-4-interactive-root']
  claude-haiku-4-meta        -> ['claude-haiku-4-meta-root']
  claude-haiku-4-chat        -> ['claude-haiku-4-chat-root']
  claude-sonnet-4-chat       -> ['claude-sonnet-4-chat-root']
  claude-opus-5-chat         -> ['claude-opus-5-chat-root']
  ```
- **검증 2 — 라이브 프로브(서빙 모델 실측)**: web-a 컨테이너에서 게이트웨이 경유, `max_tokens=5600`(thinking budget 5000 초과 필수 — 작게 주면 400 을 라우팅 고장으로 오진).
  | alias | HTTP | served | edge? |
  |---|---|---|---|
  | `claude-haiku-4-interactive` | 200 | `claude-haiku-4-interactive` | no |
  | `claude-haiku-4` | 200 | `claude-haiku-4` | no |
  | `claude-haiku-4-chat` | 200 | `claude-haiku-4-chat` | no |
- **검증 3 — 앱 층 off-hours 강등 (경계 밖 시각에 실측)**: 목요일 **19:59 KST** = 근무시간 `[10,19)` 밖 = 종전이라면 강등 구간. insight-worker 컨테이너에서 `llm._effective_insight_model()` → **`claude-haiku-4`**, `AGENT_INSIGHT_OFFHOURS_MODEL` → `''`. 즉 강등이 실제로 꺼졌다(단위 테스트의 시각 4지점 검증을 라이브가 확인).
- **검증 4 — 사건 재발 없음**: 배포 후 게이트웨이 로그의 `name resolution` 실패 0건, 최근 10분 `/v1/chat/completions` 응답 전부 200.
- 결론: 사용자 보고("모든 LLM 요청이 edge")의 경로가 게이트웨이·앱 양 층에서 제거됐고 라이브에서 확인됐다. UI 표면 변경 없음 → PB-0008 비해당(§15.4.1 예외).

### Run 2026-08-07-oauth-exhaustion-gate
- Date: 2026-08-07 14:20~14:50 KST · Environment: `CLI` + 라이브 게이트웨이 실측 · 대상 `bin/refresh-claude-oauth-token.sh`

- **원인 확정 (라이브 실측)**
  - claude-corp OAuth 토큰으로 Anthropic `/v1/messages` 직접 호출(haiku, max_tokens=16, CC identity 주입) → **HTTP 429**.
    ```
    anthropic-ratelimit-unified-7d-status      = rejected
    anthropic-ratelimit-unified-7d-utilization = 1.0
    anthropic-ratelimit-unified-7d-reset       = 1786255200   (2026-08-09 15:00 KST)
    anthropic-ratelimit-unified-5h-status      = allowed   / 5h-utilization = 0.0
    retry-after                                = 176528    (≈2.04일)
    ```
    → burst(5h)가 아니라 **주간(7d) 쿼터 전소**. 같은 조건에서 root 는 **HTTP 200**.
  - 자격증명 파일은 정상(`expiresAt` 유효) → 스크립트의 정적 검사는 통과 → 30분 cron 이 소진 계정을 1순위 slot 에 계속 재주입. `/tmp/refresh-oauth.log` 전 구간이 `[claude-corp] 선택` 이었다.
  - **영향 실증(게이트웨이 응답 헤더)**: `claude-haiku-4-chat` 호출 → `x-litellm-attempted-fallbacks=1`, `x-litellm-model-group=claude-haiku-4-chat-root`. 즉 매 요청이 소진 계정을 먼저 때린 뒤 root 로 우회 중이었다.
  - **trigger 설계 정정의 근거**: 위 폴백 성공 요청의 게이트웨이 로그는 `INFO ... "POST /v1/chat/completions HTTP/1.1" 200 OK` 한 줄뿐 — `RateLimitError`/`429` 문자열 **0건**. 로그 grep 기반 trigger 는 이 상태를 영영 못 잡는다는 것을 실측으로 확인하고 heartbeat 를 주 신호로 채택했다.

- **단위 테스트** (`unit/feature-0002-agent-core/tests/test_oauth_exhaustion_gate.py`, 신규 15건)
  - 15 passed. 가짜 Anthropic 엔드포인트(`http.server`)로 200/429/401/500·도달불가를 주입하고, 격리 repo·credentials·mock `docker` 로 `.env` 쓰기와 recreate 까지 전 경로를 탄다.
  - 잠근 계약: 게이트 off 보존 · heartbeat(최근 판정→probe 0 / RECHECK_SEC=0 킬스위치 / 간격 경과→1회) · 소진 검출 후 root 승격 + reset 캐시 · flapping 0 · 자동 복귀 · fail-open 2종 · root slot 무게이트 · `--check` 무부작용 · cooldown clamp 2종 · 정적 검사 선행.
  - **역검증**: `CLAUDE_OAUTH_EXHAUSTION_GATE=0`(=수정 전 동작)으로 실행 시 **9건 FAIL** — 통과만 보고 "잠겼다" 고 결론내지 않았다. 이후 하네스가 `CLAUDE_OAUTH_*` 를 전부 고정하도록 바꿔 운영자 셸 override 로 인한 vacuous pass 도 차단했다(LRN-20260730-0002).
  - `bash -n` PASS · 임베디드 python heredoc 2개 `compile()` PASS · `make test` 완주(ruff `All checks passed!`, 실패 라인 없음 — 단 요약 라인은 미캡처).

- **라이브 적용 (14:48 KST)**
  ```
  [claude-corp] 건너뜀 — 라이브 429 5h=allowed(0.0) 7d=rejected(1.0) claim=seven_day → 2026-08-09 15:00:00 까지 우회
  [root] 선택 — 라이브 확인 통과 (HTTP 200)
  [root → ANTHROPIC_API_KEY] 토큰 갱신
  OAuth 토큰 갱신 완료(1순위=root, root slot=갱신/동일) → bedrock-gateway 재생성
  ```
  - 상태 파일 `/var/lib/dqa-llm-oauth/exhaustion.json`: `claude-corp.until=1786255200`(=7d reset 정확 일치), `root.until=0`.
  - **적용 후 게이트웨이 프로브** (컨테이너 내부, `max_tokens=5100`):
    | alias | HTTP | served (`x-litellm-model-group`) | `attempted-fallbacks` |
    |---|---|---|---|
    | `claude-haiku-4-chat` | 200 | `claude-haiku-4-chat` | **0** |
    | `claude-haiku-4-interactive` | 200 | `claude-haiku-4-interactive` | **0** |
    | `claude-sonnet-4` (bare, 폴백 없음) | 200 | `claude-sonnet-4` | **0** |
    → 적용 전 `claude-haiku-4-chat` 은 `served=claude-haiku-4-chat-root` / `fallbacks=1` 이었다. 낭비 왕복이 사라졌다.
    → bare `claude-sonnet-4` 는 폴백이 없어 소진 계정이 1순위인 동안 429 로 실패할 수밖에 없는 경로였다(계정-레벨 7d 거부이므로 모델 무관) — 이제 200. *단, 적용 전 이 alias 의 실패는 직접 측정하지 않고 계정-레벨 429 사실로부터 추론했다.*

- **미수행 / 이월**
  - root access token 회전 주체 부재(TASK 「이월 항목」) — 사람 결정 필요.
  - UI 표면 변경 없음(운영 스크립트 전용) → PB-0008 Windows-browser 검증 **비해당**(§15.4.1 예외).

### Run 2026-08-07-oauth-gate-hardening
- Date: 2026-08-07 19:00~ KST · Environment: `CLI`(격리 하네스) + 라이브 게이트웨이 · 대상 `bin/refresh-claude-oauth-token.sh`
- **적대 리뷰(§18.8 subagent 패널 3렌즈)**: security / backend·상태머신 / QA·테스트 실효성. 세 렌즈 모두 `CONCERN`, backend 는 "availability 축에서 FAIL 경계". 상세는 REVIEW REV-20260807T190000.
- **단위 테스트**: 15건 → **41건** PASS. 신규 커버: burst-429 미강등 · 긴 429 강등 · 게이트웨이 로그 트리거 (c) 격리(+음성 대조군) · FORCE_PROBE · 401/403 · retry-after 단독/헤더 없음/stale reset/ms reset · fail-open 후 heartbeat 준수 · 전원소진 시 최단 회복 계정 · probe 형태(model·system·anthropic-beta) · 사용 가능 계정 0 → exit 1 무변경 · recreate 변경시에만/실패 재시도 · 손상 상태항목 3종 · 상태 쓰기 실패 · 파일 권한 · 심링크 미추종 · detail redaction · 리다이렉트 미추종 · 개행 토큰 거부.
- **Mutation 재검증** (`/tmp/.../scratchpad/mut4`, 스크립트 사본에 결함 주입 후 전체 스위트 실행):

  | mutant | 이전(15건) | 현재(41건) |
  |---|---|---|
  | gw_dirty 트리거 제거 / GW_DIRTY 배선 사망 / grep 패턴 오타 | SURVIVED ×3 | **KILLED ×3** |
  | 회복 트리거 제거 · FORCE_PROBE 무시 | SURVIVED ×2 | **KILLED ×2** |
  | 401/403 → unknown · retry-after 무시 | SURVIVED ×2 | **KILLED ×2** |
  | 항상 recreate · 사용가능계정0 에 exit 0 · `_as_int` 예외 제거 | SURVIVED ×3 | **KILLED ×3** |
  | anthropic-beta 헤더 제거 · probe 모델 opus 고정 | SURVIVED ×2 | **KILLED ×2** |
  | (신규 계약) burst 강등 · 전원소진 정렬 · entry 타입강제 · .env chmod · stale reset 필터 · 토큰 마스킹 · 제어문자 제거 · mkstemp · 디렉토리 0700 · 리다이렉트 · 개행토큰 거부 · recreate 실패 무시 | — | **KILLED ×12** |
  | `os.chmod(tmp,0600)` 제거 | — | SURVIVED(**등가** — `mkstemp` 가 이미 0600. `mkstemp`→`open` mutant 는 KILLED) |
  | SEL tab 가드 제거 | — | SURVIVED(**외부 유발 불가**한 내부 불변식 — 정직 표기) |

- **자체 발견(정직 표기)**: 처음 작성한 보안 테스트 2건이 **vacuous** 였다 — ① 가짜 엔드포인트가 3-tuple 응답 스펙에서 `ValueError` 로 죽어 스크립트에는 '연결 끊김'으로 보였고 fail-open 경로가 대신 통과했다, ② 302 뒤 urllib 이 POST→GET 으로 바꾸는데 핸들러가 GET 을 기록하지 않아 "리다이렉트를 안 따라갔다"가 항상 참이었다. mutation 이 둘 다 잡아냈다. 하네스에 핸들러 예외 표면화(`errors`)·GET 기록·잉여 probe 감지(`overflow`)를 추가했다.
- `bash -n` PASS · 임베디드 python 2블록 `compile()` PASS.
- **라이브 재적용**: 하단 POSTDEPLOY 항목 참조.
- UI 표면 변경 없음 → PB-0008 비해당(§15.4.1 예외).

### Run 2026-08-11-oauth-auto-rotate
- Date: 2026-08-11 12:00~ KST · Environment: `CLI`(격리 하네스 + 실 자격증명 사본) · 대상 `bin/refresh-claude-oauth-token.sh`
- **규약 실측**: CLI 번들 2.1.220 grep → `TOKEN_URL`/`CLIENT_ID`/JSON 본문 확정. 비파괴 계약 검증 — 잘못된 refresh token 으로 실 엔드포인트 호출:
  - UA `Python-urllib/*` → **HTTP 403 Cloudflare Error 1010**(앱 미도달)
  - UA `Claude-User (claude-code/2.1.220)` → **HTTP 400 `invalid_grant`**(정상 도달)
  → UA 지문이 필수임을 확인하고 구현·테스트에 반영.
- **Preflight(실 자격증명 사본, 원본 무접촉)**: 가짜 토큰 서버로 두 계정 회전 →
  소유자 `claude-corp:claude-corp` / `root:root` 와 모드 `600` **그대로 보존**, 백업도 동일 소유자·모드,
  top-level·oauth 필드 **유실 0**, 원본 파일 mtime 무변경.
- **적대 패널(§18.8 subagent 2렌즈)**: security / correctness 둘 다 **FAIL** 판정. P1 5건 + P2 다수. 상세는 REVIEW REV-20260811T120000.
- **단위 테스트**: 55 → **75건** PASS.
- **Mutation 재검증** (`scratchpad/mut7`·`mut8`):

  | mutant | 결과 |
  |---|---|
  | `--check` 도 회전 / 호출부 가드 제거 / `expires_in` 폴백 제거 / 백업-우선 순서 복귀 | KILLED ×4 |
  | 백업 `O_NOFOLLOW` 제거 / 심링크 creds 허용 / `chown` 제거 / 원자성 제거 | KILLED ×4 |
  | 요청후 재확인 제거 / backoff 제거 / `keep_backups=0` 오동작 / scope 재영속화 | KILLED ×4 |
  | access_token 타입 미검 / 만료토큰 회전 거부 / 에러본문 scrub 제거 / ttl 상한 제거 | KILLED ×4 |
  | (1차 라운드) 회전 미실행·lead 무시·race 재확인·refresh 미영속·타 필드 유실·모드·lock·UA·백업 prune 등 | KILLED |
  | **총계** | **20/20 KILL** |

- **자체 발견(정직 표기)**: 1차 mutation 에서 생존한 5건 중 **3건은 코드가 아니라 내 테스트가 vacuous** 해서였다 — ① `keep_backups=0` 테스트에 지울 백업이 없었고 ② lost-update 테스트의 '지연' 헤더를 서버가 무시했으며 ③ scope 잠식은 아예 테스트가 없었다. 하네스에 응답 지연을 실제로 구현하고 사전 백업을 심어 잡았다.
- UI 표면 변경 없음 → PB-0008 비해당(§15.4.1 예외).


### Run 2026-09-07-local-llm-decommission

**대상**: TASK-20260907T152000-local-llm-decommission (로컬 LLM 전면 폐기)
**환경**: worktree `ai/claude-corp/feature-0007-local-llm-decommission` (base `ab70380c`),
로컬 pytest + 루트 `conftest.py` 격리 2차 방어(`DB_PORT=1`·`AGENT_KB_PG_PORT=1`·read backend=mysql).
컨테이너 `make test` 대신 로컬 경로를 쓴 이유: 같은 `repo-unittest` compose 프로젝트에서 **다른 세션 2개가
동시에 테스트 중**이었고(`repo-unittest-agent-run-*` 9분·24분 경과), `dc-build` 의 이미지 재태깅이 그
실행들을 오염시킬 수 있었다.

#### 1. 폐기 근거 실측 (제거 전)

| 항목 | 측정 | 결과 |
|---|---|---|
| `local-llm-edge` 추론 요청 (7일) | `docker logs --since 168h \| grep -c POST` | **0건** (전체 77,789줄 = `GET /api/tags` healthcheck) |
| `local-llm-edge` 메모리 | `docker stats --no-stream` | 31.5MiB / 12GiB — **모델 미로드** |
| `local-llm-gateway` 트래픽 | `docker logs --since 168h` | 자기 `/health` 뿐 (외부 소비자 0) |
| `litellm_config.yaml` 활성 alias | 비주석 `model_name` 계수 | 1개 (`titan-embed`) |

#### 2. `model_list: []` 기동 실측 — 기존 테스트 가정의 반증

`test_litellm_config_still_parses` 가 "model_list 가 비었다 — 게이트웨이 기동 실패" 를 단정했으나
**가정이었다**. `ghcr.io/berriai/litellm:main-stable` 을 편집본 config 로 직접 기동:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
/health/liveliness -> 200
/health/readiness  -> 200
```

→ 활성 모델 0개는 기동 실패 사유가 아니다. 단언을 "키 존재 + 리스트 타입" 으로 교체했다.

#### 3. 구조 검증

| 검증 | 명령 | 결과 |
|---|---|---|
| compose YAML 구조 | `yaml.safe_load` | services 23 · networks `[dbnet, replica-net]` · volumes `[]` · `embed-ollama` 부재 |
| compose 시맨틱 | `docker compose config` | **rc=0** · `embed-ollama` 0건 · `llm-shared` 0건 |
| Makefile 구문 | `make -n help` | rc=0 (`.env` 부재 경고는 worktree 의 기존 거동) |
| 잔존 참조(비주석) | `grep -vE '^\s*#'` | `llm-shared`/`embed-ollama`/`embed_ollama_models` **0건** (주석 4행만 — 되돌리기 안내) |
| 카탈로그 게이트 | env 를 죽은 주소로 설정 후 import | `_LOCAL_LLM_ENABLED=False` · `auto/edge/core/code` 전부 `is_allowed_api_model=False` · `claude-haiku-4=True` · PUBLIC 3개 무변 |
| provider 선택 | Bedrock 미설정 + `LOCAL_LLM_*` 설정 | `(None, None)` — fail-open 경로 폐쇄 |

#### 4. 회귀 잠금 + 결함 주입 실증 (§16.7 G11-b)

| 단계 | 결과 |
|---|---|
| `test_llm_edge_free_routing.py` (갱신 후) | **6건 통과** |
| 결함 주입 — `edge-fallback` 정의를 `model_list` 에 되살림 | `test_edge_deployment_absent` **FAIL** + `test_no_local_backend_api_base_in_model_list` **FAIL** |
| 원복 후 재실행 | 6건 통과 · `git status` 로 원복 확인 |
| 영향 테스트 17파일 (`grep` 로 수집한 전수) | 초기 **2건 FAIL** → 선행 계약 supersede 후 **전량 통과** |

초기 FAIL 2건은 `feature-0043` 의 `test_llm_gate.py` — `test_litellm_config_keeps_local_embedding_alias`(AC-7,
`titan-embed` 보존 강제)와 `test_litellm_config_still_parses`(빈 model_list 금지). 둘 다 **이번 사용자 결정으로
전제가 이동한 계약**이므로 방향을 반전하고 경위를 docstring 에 남겼다.

#### 5. 운영자 DB row census (§16.7 G8-b)

| 대상 | 결과 |
|---|---|
| `webruntimesettings` override | 25건 — `AGENT_KB_EMBEDDING_MODEL`·`LOCAL_LLM_*` **0건**. 모델 키는 전부 `claude-*` |
| 저장 모델 KV | MySQL 전 스키마에 `%kv%` 테이블 **0건** (있어도 `conversations.py:975-987` 이 탈락 시 기본값 복귀) |
| 보존 데이터 | `texts` 154,365행 전량 임베딩 · `sample_queries` 1행 — **미삭제** |

#### 6. 미검증 (정직 표기)

- **라이브 재배포·healthz**: 본 Run 시점 미수행 — 아래 「후속」 참조.
- **라이브 `.env` 정리**: `.env*` deny rule 로 이 세션 편집 불가 → 미조치. 그로 인해 라이브에는
  `AGENT_KB_EMBEDDING_MODEL=titan-embed` 가 남아 있어 **KB 쿼리마다 경고 1건**이 예상된다
  (결과는 trigram 으로 정상). 배포 후 실측 항목.
- **KB 검색 품질 회귀 측정**: 벡터→trigram 강등의 정량 영향(precision/recall@k)은 측정하지 않았다.
  `make kb-retrieval-eval` 의 벡터 축이 제공자 부재로 무효라 A/B 자체가 성립하지 않는다.
