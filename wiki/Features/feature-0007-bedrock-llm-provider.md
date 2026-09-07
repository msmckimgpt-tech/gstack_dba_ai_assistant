---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, llm, bedrock, gateway]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0007-bedrock-llm-provider
linked_unit: unit/feature-0007-bedrock-llm-provider
created: 2026-05-26
sources:
  - ../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md
  - ../../unit/feature-0007-bedrock-llm-provider/docs/REPORT.md
  - ../../docs/DECISIONS.md
---

# Feature — Bedrock LLM Provider

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0007-bedrock-llm-provider |
| 상태 | active (draft → substantial via Phase E) |
| 정본 | [[../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | LiteLLM gateway · AWS Bedrock Claude · model catalog · env 분리 |

## 1. 개요

사용자별 OpenAI API key 입력 (API Vault) 패턴을 **전면 폐기** 하고, 서비스가 보유한 단일 **AWS Bedrock** 자격증명 (Seoul region 시도 → ACTIVE Sonnet 부재로 `global.*` inference profile 채택) 으로 모든 LLM 호출을 통합한다. OpenAI-compatible **LiteLLM proxy** 컨테이너 (`bedrock-gateway`) 가 SDK 패턴 reuse 를 제공.

## 2. 상세

### 2.1 책임 경계

- **입력**: `BEDROCK_GATEWAY_URL`, `BEDROCK_GATEWAY_API_KEY` (backend), AWS credentials (gateway 컨테이너만)
- **출력**: LLM 응답 (OpenAI Chat Completions schema), audit row (`conversation.ask` ChangeJson.model)
- **side-effect**: AWS Bedrock 호출 (Anthropic Claude Sonnet 4.6 / Haiku 4.5)

### 2.2 핵심 흐름

1. `/api/ask` → backend 가 model 검증 (`_is_allowed_api_model` Claude alias only)
2. `_run_agent_core(api_key=None)` → `_get_openai_client()` 가 env `LLM_BASE_URL = BEDROCK_GATEWAY_URL` + `LLM_API_KEY = BEDROCK_GATEWAY_API_KEY` 단일 진입
3. agent loop → `client.chat.completions.create(model=<claude-alias>, ...)`
4. gateway → `bedrock-runtime:InvokeModel` Claude 호출
5. gateway 응답 변환 (Bedrock → OpenAI Chat Completions schema)

### 2.3 모델 catalog (`litellm_config.yaml`, ADR-0026 addendum)

- `claude-sonnet-4` → `bedrock/global.anthropic.claude-sonnet-4-6` (2026-08-26 이후 주석 처리 — feature-0043 두 번째 자물쇠)
- `claude-haiku-4` → `bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0` (2026-08-26 이후 주석 처리 — feature-0043 두 번째 자물쇠)

Seoul region 의 ACTIVE Sonnet region-pinned ID 부재 → `global.*` inference profile 채택 (사용자 reanchor 2026-05-21).

> **참고**: 실 운영 배치는 OAuth 계정 기반(claude-corp/root) 2계정 체인으로 위 Bedrock alias 표보다 넓었다 — **2026-08-26 feature-0043 이후 그 두 계정의 chat 호출은 fail-closed 게이트로 전면 차단**됐고 alias 도 전량 주석 처리됐다 — 아래 §2.4·정본(FUNCTION/REPORT) 참조. **2026-07-30 이후 자동으로 로컬 gemma(edge)가 서빙되는 경로는 없다**(ADR-003).

### 2.4 요청-레벨 fallback + 용도별 라우팅 (2026-07-03~04 · 07-30 edge 제거, 정본 REPORT §3·ADR-002/ADR-003 feature-local)

- **요청-레벨 fallback 체인(insight-llm-fallback, 2026-07-03)**: insight-worker LLM(`claude-haiku-4`)의 burst rate-limit(429) 대응 — `claude-haiku-4`(claude-corp) → `claude-haiku-4-root`(root Max) → `edge-fallback`(로컬 gemma `openai/gemma4:e2b` via local-llm-gateway) 3-deployment + `litellm_settings.fallbacks` + `num_retries:1`. `bin/refresh-claude-oauth-token.sh` 가 두 토큰(ANTHROPIC_API_KEY·ANTHROPIC_API_KEY_ROOT)을 **병행 주입**해야 요청-레벨 fallback 성립. 비밀정보는 `.env.bedrock`(gitignored)에만. **(2026-07-30 supersede — ADR-003)** `fallbacks` 의 `edge-fallback` 참조가 **전량 제거**돼 체인은 `claude-haiku-4` → `claude-haiku-4-root` **2계정에서 종단**한다 — 둘 다 실패하면 429/401/도달불가를 그대로 올려 정직하게 실패한다(`edge-fallback` deployment 정의만 되돌리기용으로 보존·참조 0). **(2026-09-07 supersede — local-llm-decommission)** 그 «되돌리기용 보존» 도 종료됐다: 사용자 결정 "로컬 LLM 미사용" 으로 `local_llm` 프로젝트 자체가 폐기(컨테이너 제거 + 모델 16GB 삭제)돼 `api_base` 가 가리키는 `local-llm-gateway` 가 존재하지 않는다 — 정의를 주석 이력으로 강등했다. 같은 cycle 에서 마지막 활성 alias `titan-embed`(→ 로컬 Ollama `bge-m3`)와 그 백엔드 `embed-ollama` 서비스도 제거해 **활성 `model_name` 이 0개**(`model_list: []`)가 됐고, 그 상태로도 게이트웨이가 기동함을 실측했다(liveliness/readiness 200). KB 검색은 `kb_retrieval` 의 2-tier 경로로 `pg_trgm` 강등(기능 유지 · 기존 임베딩 154,365행 보존).
- **용도별 라우팅 분리(llm-routing-interactive-split, 2026-07-04, ADR-002 feature-local)**: insight-worker 가 주말/야간 gemma 로 고착(refresh-oauth cron 평일한정 → 토큰 만료 → 401 → edge 강등)하던 현상 해소. litellm alias 를 **사람 실시간(대화·AI 능동 분석)=`claude-haiku-4-interactive`(+`-root`)로 항상 claude** / **백그라운드 insight 배치=시각 기반(`_effective_insight_model`, 평일 근무 claude·야간/주말 edge)** 로 분리 + fallback 체인 결함(root/interactive-root 미등록 → gemma 미도달) 수정 + refresh/keepalive cron 24/7 확장(토큰 상시 유효). 회귀 `test_insight_offhours_routing.py`(13)·`test_llm_env_naming.py`. **(2026-07-30 supersede — ADR-003 결정 2)** 앱 층의 시각 기반 강등도 **기본 비활성** — `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값이 `"edge"` → 빈 값이 되어 ADR-002 결정 2(배경 insight 배치의 야간·주말 gemma)는 폐지됐다(강등 로직 자체는 보존·되돌림은 사용자 결정 override).

## 3. 특징

- **per-user OpenAI key 폐기** — Profile drawer "API Vault" 탭 / step wizard / `encryptPlainApiKey` / `_decrypt_api_key` 전부 제거
- **서비스 단일 자격증명** — 사내 한정 + 비용 책임 운영자 부담 OK (사용자 결정)
- **env 분리 (CHG-20260522-0005)** — `.env.bedrock` (AWS_*) / `.env.mysql` / `.env.postgres` / `.env.minio` / `.env.llm` 각 docker-compose service 가 자기 secret 만 inherit
- **OpenAI direct fallback 완전 제거** (CHG-20260522-0006) — `_select_llm_provider()` 의 OpenAI 분기 삭제
- **gateway SPOF mitigation**: `restart: unless-stopped` + healthcheck 12 retry × 10s = 2 min recovery window
- **1순위 OAuth slot 의 사용량-소진 게이트 (2026-08-07, `oauth-exhaustion-gate` → `oauth-gate-hardening`, §12.3)**: claude-corp 의 7일 쿼터가 100% 소진(`unified-7d-status=rejected` · retry-after ≈ 2.04일)돼도 **자격증명 파일은 유효**해서, 정적-검사-전용 갱신 로직이 30분마다 소진 계정을 `ANTHROPIC_API_KEY` 에 재주입했다 — litellm 폴백이 흡수하더라도 (a) 매 요청이 소진 계정을 먼저 때리고(`num_retries:1` → 2회 왕복) (b) 폴백 없는 bare alias(`claude-sonnet-4`·`claude-opus-5`)는 그대로 실패했다. 1순위 slot 선택에 저빈도 heartbeat(기본 1h) **1-probe** 게이트를 넣어 429 면 `anthropic-ratelimit-unified-reset` 까지 그 계정을 건너뛰고 다음 계정을 승격하며, 캐시 유효 동안 probe 0(flapping 없음) · 만료 후 1-probe 로 자동 복귀한다. 네트워크·미분류 오류는 **fail-open** — 도달성 장애를 소진으로 오판하지 않는다(2026-07-30 DNS 사고 반영). 킬스위치 `CLAUDE_OAUTH_EXHAUSTION_GATE=0` / `CLAUDE_OAUTH_GATE_RECHECK_SEC=0`. trigger 를 게이트웨이 로그 grep 으로 잡으려던 초안은 라이브에서 폐기했다 — **폴백이 성공하면 로그엔 200 OK 만 남아**(`x-litellm-attempted-fallbacks` 헤더에만 드러난다) 그 신호는 영원히 발화하지 않는다. 이어진 §18.8 3렌즈 패널(security / backend·상태머신 / QA)이 P1 3건을 잡아 전건 수정했다: 모든 429 를 소진으로 보고 `retry-after=5s` 조차 min_cooldown(300s)으로 끌어올린 **burst-429 오강등**(→ 두 slot 이 같은 root 토큰이 되어 2계정 폴백 체인이 1계정으로 붕괴하고 강등/복귀마다 게이트웨이 force-recreate = LLM 순단 · 이제 `7d=rejected` 이거나 헤더 쿨다운이 `CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC`(1800s) 이상일 때만 강등) · `docker compose up` 종료 상태 미검사로 **`.env` 는 신 토큰 · 컨테이너는 구 토큰**인 채 다음 실행이 `CHANGED=0` 으로 skip 되던 **recreate 실패 영구화**(→ sentinel + 재시도 + exit 1 + stderr 보존) · fail-open 후 회복 probe 무한 반복(→ `checked < until` 로 쿨다운 만료당 1회). 부수로 `.env.bedrock` 0600 · 상태 디렉토리 0700/파일 0600 + mkstemp · probe 리다이렉트 미추종(Authorization 유출) · 토큰 마스킹·제어문자 제거. 테스트 15 → 41건, 패널이 생존시킨 뮤턴트 19건 중 18 KILL. 정본 TASK `TASK-20260807T144800-oauth-exhaustion-gate` · `TASK-20260807T190000-oauth-gate-hardening`.
- **access token 만료 자동 회전 (2026-08-11, `oauth-auto-rotate`, **Critical §12.3** — 자격증명 저장소 쓰기·사용자 승인)**: `bin/refresh-claude-oauth-token.sh` 는 디스크의 access token 을 **읽기만** 했고 실제 회전은 그 계정의 Claude Code CLI 세션이 돌 때만 일어났다 — TTL ~8h 라 야간·주말 세션 공백이 생기면 정적 검사가 계정을 탈락시키고, 다른 계정마저 소진돼 있으면 **LLM 이 전면 중단**됐다(2026-08-07~11 실사례). 이제 만료까지 `CLAUDE_OAUTH_ROTATE_LEAD_SEC`(기본 1h) 이하로 남으면 refreshToken 으로 선제 회전해 자격증명 파일에 되쓴다. 규약은 CLI 번들에서 실측했다 — `platform.claude.com/v1/oauth/token` · JSON 본문 · UA `Claude-User (claude-code/<ver>)`(기본 urllib UA 는 Cloudflare 1010 으로 앱에 닿지 못한다). §18.8 2렌즈가 **둘 다 FAIL** 을 내 P1 5건을 전량 수정했다: `--check` 가 실제로 회전해 일회성 refresh token 을 소모 · 회전 중 예외가 selector 를 죽여 1순위 slot 이 `exit 0` 으로 **무음 정지** · `expires_in` 부재 시 과거 만료를 되써 재회전·게이트웨이 재생성 폭풍 · `.bak` 경로 심링크 추종 · **POST 성공 후 백업 단계 실패가 소모된 refresh token 을 유실**(재로그인 외 복구 불가). P2 로 lost update 재확인 · scope 잠식 방지 · `keep_backups=0` 의미 반전 · 실패 backoff · lock `O_NOFOLLOW`/lstat · CLI lock 과 배타되지 않는다는 사실의 주석 정정. 테스트 55 → 75건 · mutation 20/20 KILL · 실 자격증명 사본 preflight 로 소유자·모드 보존과 필드 무손실 확인(소유자 보존 단언은 CI 러너가 비-root 라 root 한정 게이팅) · 킬스위치 `CLAUDE_OAUTH_AUTO_ROTATE=0`. **심각도 재평가(운영자 확인 2026-08-11)**: claude-corp/root 분리는 WSL 에서 복수 Claude 계정을 구분하기 위한 것이고 각 계정의 내부 접근 권한은 root 단위로 동일하므로, 패널이 P1 으로 올린 `.env.bedrock` 월드리더블·`.bak` 심링크 소유권 탈취는 **이 환경에서 권한 상승이 아니다** — 조치(0600 / `O_NOFOLLOW` / 원자적 교체 / 랜덤 백업 접미사)는 비용이 0 이고 권한과 무관한 사고를 여전히 막으므로 되돌리지 않고 근거만 "권한 경계" → "위생" 으로 옮겼다(열린 P1 으로 남겨 두면 다음 패널이 같은 것을 다시 최상위로 올려 실제 결함 탐색 예산을 갉아먹는다). 정본 TASK `TASK-20260811T120000-oauth-auto-rotate`.

## 4. 비교

### 4.1 본 통합 vs 기존 OpenAI direct

| 항목 | 본 통합 (Bedrock gateway) | 기존 (OpenAI per-user) |
|---|---|---|
| trust 모델 | 서비스 단일 자격증명 | 사용자별 API Vault cipher |
| 비용 부담 | 운영자 | 사용자 |
| 데이터 region | global (PIPA 잔류 risk) | OpenAI US |
| 사용자 진입 | 즉시 | API key 입력 필요 |
| 모델 family | Anthropic Claude 4.x | OpenAI GPT-5.4 |

### 4.2 본 통합 vs boto3 native

| 항목 | LiteLLM gateway (채택) | boto3 + bedrock-runtime |
|---|---|---|
| 코드 변경 | OpenAI SDK 패턴 reuse — 최소 | provider abstraction wrapper 추가 |
| latency | gateway overhead 약간 | direct |
| 변경 cost | 본 cycle 적합 | 별 cycle, 최적화 시점 |

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0002-agent-core]] — `llm.py` / `config.py` / `model_catalog.py` 갱신
- [[feature-0003-agent-web-ui]] — `app.py` / `app.js` / `index.html` Vault DOM 제거

## 6. 관련 정본

- [[../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0007-bedrock-llm-provider/docs/TASK|TASK.md]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §6 — credential 관리 정책

## 7. 관련 노트

- [[../Decisions/ADR-0026-bedrock-llm-provider]] — 본 feature 의 정본 ADR
- [[../Architecture/Data-Flow]]
- [[../entities/aws-bedrock]]
- [[../entities/litellm]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0002-agent-core]] · [[feature-0003-agent-web-ui]]

## 9. 외부 link

- [AWS Bedrock — Anthropic models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [LiteLLM proxy](https://docs.litellm.ai/docs/simple_proxy)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/llm` · `#domain/gateway`
