---
doc_type: SECURITY
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.26.0
domain: [security]
ai_read_priority: 4
---

# Security

## 1. 기본 원칙
- 비밀정보를 문서나 코드에 평문으로 저장하지 않는다.
- 최소 권한 원칙을 따른다.
- 파괴적 변경은 사전 검토와 롤백 방안을 요구한다.
- 로그, 보고서, 산출물에 민감정보가 포함되지 않도록 주의한다.

## 2. 비밀정보 처리
- API 키, 토큰, 비밀번호, 인증서는 문서나 샘플 파일에 직접 커밋하지 않는다.
- `../.env`는 로컬 전용 파일로 사용하고, `.gitignore`로 제외한다.
- `../.env.example`에는 민감값을 넣지 않으며, 원본 루트 `.env`의 의미 체계를 보존한 샘플만 둔다.
- 인증서와 세션 파일은 `../../artifacts`에만 저장한다.

## 3. 승인 필요 변경
다음은 사람이 승인해야 한다.
- 인증/인가 변경
- 데이터 삭제 및 파괴적 마이그레이션
- 외부 공개 범위 변경
- 개인정보 처리 변경
- 비용 상승 위험이 큰 외부 연동 변경

## 4. 기록 규칙
보안 관련 우려사항은 숨기지 말고 `REVIEW.md`와 `REPORT.md`에 명시한다.

## 5. 현재 저장 경계
- 코드 및 문서: `repo/`
- 런타임 로그와 출력: `../../artifacts/shared`
- MySQL 데이터: `../../artifacts/mysql-data`
- 인증서: `../../artifacts/certs`

## 6. 자격증명 관리 패턴
- 자격증명 파일(`.cnf`, `.env`, 인증서 등)은 저장소에 커밋하지 않는다.
- 기능별 `src/config/credentials/` 디렉토리에 실제 자격증명을 두되, `.gitignore`로 제외한다.
- `*.example` 파일만 커밋하여 필요한 키와 형식을 문서화한다.
- 자격증명 파일 권한은 `0600` (소유자만 읽기/쓰기)을 유지한다.
- `.gitignore` 패턴 예시:
  ```
  # 자격증명 제외
  **/config/credentials/*.cnf
  **/config/credentials/*.env
  !**/config/credentials/*.example
  ```
- 자격증명 경로와 필요 권한은 해당 기능의 `FUNCTION.md` §10 Dependencies에 명시한다.

### 6.1 LLM provider 자격증명 (feature-0007, REQ-20260521-0001~3)

- LLM 호출 자격증명은 **서비스 단일 env** (`BEDROCK_GATEWAY_API_KEY`) 가
  보유한다. 사용자별 키 입력 (구 API Vault wizard) 패턴은 폐기됨.
- **env_file scoping 정책 (CHG-20260522-0005, feature-0007 follow-up — codex
  blindspot #1 의 최종 해결)**: secret 영역별 `.env.*` 파일 분리. docker-compose
  service 가 자기에게 필요한 secret 파일만 inherit — **least privilege 강제**:
  - `.env`: 비-secret 영역 (port / tuning / public host) — 모든 service inherit.
  - `.env.bedrock` (gitignored): `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` —
    **`bedrock-gateway` service 만** inherit. backend / web / agent /
    insight-worker / mysql / postgres / minio / browser / mcp / caddy 미노출.
  - `.env.mysql` (gitignored): `MYSQL_ROOT_PASSWORD` / `DB_PASSWORD` /
    `REPLICA_DB_PASSWORD` — `mysql` + DB 호출 service (web / agent /
    insight-worker / memory-init / mcp) inherit.
  - `.env.postgres` (gitignored): `AGENT_KB_PG_PASSWORD` / role 별 password —
    `postgres` + KB-using service inherit.
  - `.env.minio` (gitignored): `MINIO_ROOT_PASSWORD` / `MINIO_APP_*` — `minio` +
    `minio-init` + 첨부 read/write service inherit.
  - `.env.llm` (gitignored): `LOCAL_LLM_API_KEY` / `BEDROCK_GATEWAY_API_KEY` —
    LLM 호출 service (web / agent / insight-worker / memory-init / bedrock-gateway)
    inherit.
  각 `.env.*.example` (committed) 는 placeholder 만 보유. 운영자가 사내 시크릿
  관리자 (vault, sealed-secrets, AWS Secrets Manager 등) 에서 발급 후 채운다.
- **`OPENAI_API_KEY` 폐기 (CHG-20260522-0006, 사용자 결정 2026-05-22)**: OpenAI
  direct fallback 제거. `_select_llm_provider()` 의 분기 3 (OpenAI direct)
  삭제. 운영 .env 의 잔존 값은 silent ignore (backward-compat — config.py 의
  import 는 유지하나 분기 외). LLM 호출 entry 는 Bedrock gateway 또는 Local
  LLM gateway 만 허용.
- IAM role 권한은 `bedrock:InvokeModel` 최소 권한 + 모델 access 명시 (Claude
  Sonnet 4.x / Haiku 4.x). `AmazonBedrockFullAccess` 는 권장 안 함.
- region 은 `ap-northeast-2` (Seoul) — `aws_region_name` 설정. 단 ACTIVE
  Claude Sonnet 4.5/4.6 / Haiku 4.5 의 inference profile 이 모두 `global.*`
  만 제공 (Phase E 검증 결과, 2026-05-21). 본 cycle 은 global inference profile
  수용 (사용자 reanchor) — 사내 한정 + 비-개인정보 SQL 작업 가정으로 PIPA risk
  낮음. 엄격 잔류 보장이 필요해지면 별 cycle 의 Provisioned throughput 또는
  별 provider (Anthropic API / Azure OpenAI Korea region / on-prem LLM) 재검토.
- `BEDROCK_GATEWAY_API_KEY` 는 사내 시크릿 관리자에서 발급. backend ↔ gateway
  양쪽이 동일 값을 공유 (gateway 의 `master_key` + backend 의 `LLM_API_KEY`).
- 자격증명 rotation: gateway 컨테이너 재시작으로 1 회 cycle. 기존 in-flight
  요청은 ungraceful (사내 한정 + 짧은 응답 시간 — 운영상 허용).
- **Paired fallback 정책 (CHG-0003)**: `LLM_BASE_URL` 과 `LLM_API_KEY` 는
  `_select_llm_provider()` helper 가 paired tuple 로 결정. provider URL 만
  설정 + key 미설정 시 silent misroute 차단 (다음 provider 로 fallback).
- 본 cycle 범위 외: per-user / per-role token quota (배포 후 별 cycle).

## 7. Anonymous 접근 허용 경로 (allowlist)

본 저장소의 모든 HTTP endpoint 는 기본적으로 로그인 쿠키 검증을 요구한다 (`_require_account` → 401). 다음 경로는 **명시적 예외** 로 anonymous 접근이 허용된다. RBAC refactor 시 실수로 `_require_account` 를 일괄 부착하지 않도록 주의한다.

| 경로 | 메서드 | 인증 | 용도 | 도입 |
|---|---|---|---|---|
| `/share/{token}` | GET | anonymous | 대화 공유 페이지 (`share.html` FileResponse) | TASK-0058 (REQ-20260514-0001) |
| `/api/public/share/{token}` | GET | anonymous | 공유된 대화 read-only 조회 (메시지 + SQL + 결과셋) | TASK-0058 |
| `/api/public/share/{token}/fork` | POST | **로그인 필요** + `conversation.create` | 공유받은 viewer 가 본인 계정으로 fork (`_optional_account` 가 아닌 `_require_account` 사용) | TASK-0058 |

### 7.1 운영 정책

- `/api/public/...` 네임스페이스는 **공유 view 외 다른 anonymous endpoint 추가 금지**. 신규 anonymous endpoint 가 필요하면 본 표를 갱신 + REVIEW.md 등재.
- 공유 페이지는 사내 IP 가정 (운영 LAN 또는 VPN 경유) 으로 활성화돼 있다. 외부 LAN 노출이 발생하면 SQL 원문 + 결과셋이 외부로 그대로 전달된다.
- 공유 페이지의 `share.html` 은 `meta robots noindex,nofollow` 와 fixed footer "사내 공유용 — 외부 IP 로 전달 시 데이터 노출 위험" 안내를 포함한다.

### 7.2 외부 배포 전 보완 (TODO)

외부 LAN / 공개 인터넷 배포가 가시화되면 다음 중 하나 이상의 보완을 본 cycle 전에 추가한다:

1. **IP allowlist**: Caddy / reverse proxy 레벨에서 `/api/public/share/...` 와 `/share/...` 에 대한 사내 CIDR 화이트리스트.
2. **Token 별 비밀번호**: `WebConversationShares` 에 `PasswordHash VARCHAR(255) NULL` 컬럼 + 생성 시 옵션. GET 응답 401 시 password prompt 노출.
3. **시간 기반 만료**: `ExpiresAt DATETIME NULL` 컬럼 + GET 시 `NOW() > ExpiresAt` → 410. 기본은 무기한 + 명시 revoke 그대로 유지.

후속 cycle 결정은 운영 환경 변경 시점에 진행한다 (사용자 직접 결정 필요).

## 8. Cross-account 대화 검색·필터 정책 (TASK-0072)

`/api/conversations` 의 search mode (`q` / `owner_id` / `product_id` / `date_from` / `date_to` / `cursor` 중 하나 이상) 는 admin/operator 의 cross-account 감사 needs 와 PII 보호의 균형을 위해 다음 정책을 강제한다.

### 8.1 권한 모델

- 신규 catalog 없음. 기존 `conversation.list.any` (admin/operator 자동 grant) / `conversation.list.own` (모든 사용자) 재활용.
- `.any` 보유자: cross-account 매칭 + owner facet + snippet opt-in chip 노출.
- `.own` only: 본인 대화 안에서만 매칭. `owner_id` 입력은 SQL 단계에서 self 로 강제 overwrite (sub-spec 1). 응답은 byte-equal regardless of input owner_id (404/403 metadata leak 차단).

### 8.2 검색 표면 한정

- 검색 대상 필드 = `c.topic` + `topic_kv.Value` (제목) + `owner.Username` (계정명, `.any` 한정) + `AgentMemoryMessages.Content` + `AgentCoreMessages.content` (메시지 본문).
- 검색 대상 *비포함* = SQL 텍스트 / 실행 결과셋 / 디버그 로그 — list 단계 표면 최소화.

### 8.3 SQL safety

- 모든 LIKE 는 `LIKE %s ESCAPE '!'` + `!`, `%`, `_` 3 char escape. NO_BACKSLASH_ESCAPES sql_mode 회귀 차단.
- `q` raw input min 3 char + max 200 char + post-escape 0 literal char (`q="%%"`) 거부 (400).
- `WHERE` composition order strict — owner_id 가 q/owner_id/product_id 보다 항상 먼저 AND (`.own` 사용자는 self 강제, `.any` 사용자는 옵션 filter).
- `c.conversation_id NOT IN (hidden_ids)` SQL push (Python post-filter 폐기).
- `WebAccounts.DeletedAt IS NULL` filter 추가 (cross-account leak 추가 layer).

### 8.4 성능 안전망

- `LIMIT 50` 강제 (endpoint clamp 1~100).
- per-account `_search_rate_limit_check` 10 req/min (in-process token bucket, 60 s sliding window). 11 번째 → 429.
- body-search 진입 시 `SET SESSION max_execution_time = 3000` (3 s runaway 차단).
- collation audit process 당 1 회 — `AgentMemoryMessages.Content` / `AgentCoreMessages.content` 가 `utf8mb4_unicode_ci` 아니면 stderr warning.
- cursor pagination keyset on `(c.updated_at DESC, c.conversation_id DESC)`. offset pagination 금지.

### 8.5 PII audit (PIPA §29 준거)

- `WebAccountActivity` 테이블에 모든 body-search + snippet opt-in 활성화 INSERT.
- 컬럼: `Id, AccountId, Action ('conversation.search.body'), TargetOwnerId, QueryHash CHAR(64), MatchedCount, CreatedAt`.
- **`QueryHash` 는 SHA-256 hex 만 저장. 평문 query 저장 금지.** 재현 가능 + 평문 회피.
- 보관 기간: PIPA §29 의 접근기록 1 년 보관 권장. 운영 환경에서 보관 정책 (cron purge / archive) 은 후속 cycle.
- snippet opt-in chip 자체도 audit 대상 (의도 추적).

### 8.6 UI 표면

- Spotlight modal pattern (Cmd/Ctrl+K). 사이드바 conv-list 잠식 0.
- snippet opt-in chip 기본 OFF + `.any` 한정 노출. opt-in 토글 자체가 명시적 user action.
- owner facet chip 도 `.any` 한정. `.own` 사용자는 chip 보지 않음.

### 8.7 외부 배포 전 보완 (TODO)

외부 LAN / 공개 인터넷 배포가 가시화되면 §7.2 의 보완 조치 (IP allowlist / token 비밀번호 / 시간 만료) 가 `/api/conversations` search mode 에도 동일하게 적용된다. 추가로:

1. **FULLTEXT migration** — `ngram` parser + `innodb_ft_min_token_size` 튜닝 후 `AgentMemoryMessages.Content` 에 FULLTEXT index. 본 cycle 의 LIKE 안전망이 rate limit 빈번 진입 또는 `max_execution_time` 빈번 hit 시 trigger.
2. **WebAccountActivity 보관 정책** — cron / archive 자동화.
3. **운영자 사전 고지** — 관리 콘솔 첫 진입 시 "타 계정 대화 본문 검색은 모두 기록됩니다" 1 회 dismiss 안내 (PIPA "처리 사실 인지" 요건 보강).

## 9. Audit subsystem 정책 (TASK-0073)

REQ-20260519-0001 — 모든 admin mutation + user 4 high-signal action (`/api/ask` / share create / share revoke / share public view / share fork) 의 행위가 `WebAuditEvents` 테이블에 통합 기록된다. CEO review · Codex outside voice · Eng review 9 lock-in 의 합의된 정책 정본.

### 9.1 권한 모델 (`audit.*`)

- `audit.read.own` — 모든 role (pending / operator / sales / dba 포함) 자동 grant. `.own` SQL filter = `WHERE ActorAccountId = :self OR TargetAccountId = :self` (Eng review E1, 사용자 결정 B). admin password-reset / role permission grant / share revoke 등 admin→user 이벤트가 user 본인 audit 에 노출 → 보안 가시성 정합.
- `audit.read.any` — admin / dba auto-grant. 전체 row 조회. `.own` superset semantics (TASK-0058 share read-gate 패턴 답습).
- `audit.export` — admin / dba auto-grant. CSV / JSON dump. **TASK-0090 (2026-05-20) StreamingResponse 전환 — hard cap 50k row 제거**, max_id high-water mark + keyset cursor pagination (chunk_size=500) + 64KiB byte-threshold flush + try/finally cleanup + export self-audit (start + complete event 2 건, `action="audit.export.start"` / `audit.export.complete`/`audit.export.aborted`). masked field 정책 유지. 동시 export 제한은 별 cycle (multi-worker semaphore 정합 검토).
- `audit.purge` — admin only auto-grant. retention 초과 row chunked PK 삭제. start/complete self-audit row 동반.
- permission group `audit` 신규 — `docs/CONVENTIONS.md §10.6` admin section "관리 권한" 묶음 합류 + 작업 화면 placeholder (manage section).
- `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출이 `_ensure_seed_roles` 앞 (TASK-0063 회귀 fix 패턴 답습) — 기존 배포의 신규 4 권한 backfill 보장.

### 9.2 Sensitive field catalog (source-of-truth)

`record_audit_event` dispatcher 는 raw request 검증 X. ActionCode 별 `build_audit_change_json(action, before, after, request_ctx)` builder 가 명시 화이트리스트 (Codex C6 minimum-fix). builder source-of-truth = `src/app.py` 의 `_AUDIT_BUILDER_*_FIELDS` 정적 tuple + `_AUDIT_MASKED_FIELDS_*`.

- **`_AUDIT_BUILDER_ACCOUNT_FIELDS`** = (role_id, is_active, username, permission_overrides) — PasswordHash / MustChangePassword / DeletedByAccountId 제외.
- **`_AUDIT_BUILDER_ROLE_FIELDS`** = (name, description, is_active, permission_codes).
- **`_AUDIT_BUILDER_PRODUCT_FIELDS`** = (product_key, name, description, is_active, default_role_access, databases, system_prompt).
- **`_AUDIT_MASKED_FIELDS_PASSWORD`** = (password_hash, temporary_password, raw_password) — `_audit_redact_sensitive` 가 `<redacted>` 로 shallow 치환 + MaskedFields list 명시.
- **`_AUDIT_MASKED_FIELDS_TOKEN`** = (session_token_hash, session_token, token).
- **`_AUDIT_MASKED_FIELDS_API_KEY`** = (openai_api_key, api_key, secret,
  bedrock_gateway_api_key, aws_access_key_id, aws_secret_access_key) —
  feature-0007 도입 시 Bedrock gateway credential 필드 추가.
- **share token** = `token_prefix[:8]` 만 ChangeJson 에 저장. full token 64 char X (PII 차단).
- **system_prompt 본문** = `content_len_before / content_len_after` + `content_preview_after[:120]` 만. full content 는 audit 에 미보존 (size cap).
- **unknown action** = `build_audit_change_json` 가 `ValueError` raise → admin endpoint try/except 가 `conn.rollback()` + 500 응답 (Same tx fail-safe). user endpoint 는 stderr only.

### 9.3 Tx 정책 split (Eng review E5)

- **admin 11 mutation endpoint** = `_audit_admin_mutation()` helper 호출. caller 가 commit 직전 1 line hook. audit 실패 = caller `conn.rollback()` + 500 응답 (Same tx fail-safe). E5 cascade lock 순서 — product delete: WebSystemPrompts → WebProductDatabases → WebRolePermissions → WebAccountPermissionOverrides → WebPermissions → WebProducts → audit INSERT.
- **user 5 endpoint** = `_audit_user_action()` helper (`/api/ask`, share create / revoke / public view (anonymous) / fork). try/except → 실패 시 `conn.rollback()` + stderr log + main flow 진행 (TASK-0072 `_log_search_activity` 패턴). `/api/ask` long-running LLM lock contention 회피 (Codex C3/C4).

### 9.4 Anonymous ActorType (Eng review E4)

- `WebAuditEvents.ActorType VARCHAR(16) NOT NULL DEFAULT 'account'` enum: `"account"` / `"anonymous"` / `"system"`.
- `GET /api/public/share/{token}` (cookie 없음) → ActorType="anonymous" + ActorAccountId NULL + ChangeJson `{share_token_prefix, view_count_after, remote_addr}`.
- `POST /api/public/share/{token}/fork` 는 TASK-0058 의 fork 가 이미 `_require_account` 필수 → ActorType="account".
- `(ActorType, OccurredAt)` index 로 anonymous filter 가능 (`audit.read.any` + `?actor_type=anonymous`).

### 9.5 `audit.purge` self-audit + idempotency (Eng review E8)

- chunked PK loop — 각 chunk 1000 row (clamp [100, 5000]) = 별 tx (Long Running Transaction 회피).
- `audit.purge.start` self-audit row INSERT (시작 시 1 회) + `audit.purge.complete` (끝 시 1 회).
- `idempotency_key = sha256(cutoff + started_at_minute)[:32]` — 1 분 내 동일 cutoff 재호출 시 두 번째 purge 의 idempotency_key 동일 (admin 이 audit log 로 중복 검출).
- `max_runtime_seconds = 30` — deadline 초과 시 partial purge, 다음 호출이 cursor 재시작 (남은 row 존재 시 자연 continue).
- `dry_run=true` 시 COUNT(*) 만 반환 + 실 삭제 X.

### 9.6 `AGENT_AUDIT_ENABLED` prod fail-closed (Codex C5)

- `AGENT_MODE != dev/test` (prod 가정) 에서 `AGENT_AUDIT_ENABLED=1` 가 아니면 `app.py` module load 시점에 `sys.exit(1)` + stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 (AGENT_MODE=...; TASK-0073 Phase A1)`.
- dev / test 만 toggle 허용 — flag bypass surface 차단.
- env state changes 는 audit row 불가 (env 변경 = DB mutation 아님). startup stderr log 로 대체.

### 9.7 RemoteAddr conditional trust (TASK-0087, 2026-05-21)

본 정책은 TASK-0073 Eng review E3 의 후속 cycle (TASK-0087) 에서 다음과 같이 lock-in 됐다.

- **Caddy XFF 정규화**: `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록이 `header_up X-Forwarded-For {client_ip}` 를 명시. Caddy 가 클라이언트로부터 받은 임의 `X-Forwarded-For` 를 무시하고 **Caddy 가 본 TCP peer IP** 로 덮어쓴다. 즉 web 입장에서 `X-Forwarded-For` 는 항상 Caddy 가 정규화한 단일 IP — multi-hop / spoof 모두 차단.
- **web `_get_client_ip()` 조건부 trust**: app.py 의 `_get_client_ip()` 는 direct 연결 IP 가 `WEB_TRUSTED_PROXIES` CIDR 화이트리스트에 포함될 때만 `X-Forwarded-For` 첫 토큰을 사용한다. 그 외 모든 경우 `request.client.host` (= 직접 TCP peer) 그대로 반환.
- **XFF token 검증**: `X-Forwarded-For` 첫 토큰이 `ipaddress.ip_address()` 파싱 실패 (malformed) 면 direct IP 로 fallback. audit IP 가 garbage 값으로 오염되지 않는다.
- **운영 가정 (사용자 명시 결정)**: 본 시스템은 사내 LAN dev/staging 전제로 `WEB_TRUSTED_PROXIES` 권장값을 RFC1918 전체 (`10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`) 로 설정한다. Codex outside voice (REV-20260520-0010) 는 "RFC1918 전체 trust 는 web port 가 LAN publish 되어 있는 한 사내 클라이언트가 직접 web 에 붙어 자기 사설 IP 를 trusted proxy 로 가장해 XFF spoof 가능" 을 Major 로 지적했으나, 본 cycle 의 컨테이너는 테스트 후 정리되고 외부 접속 경로를 유지하는 명시 결정으로 받아들였다. 외부 인터넷 / 미신뢰 LAN 노출이 가시화되는 시점에는 별 cycle 에서 (a) `WEB_TRUSTED_PROXIES` 를 docker bridge subnet (예 `172.18.0.0/16`) 으로 좁히고 (b) docker-compose 의 `web` port mapping 을 `127.0.0.1:${WEB_PORT}:8000` 또는 Caddy network only 로 좁히는 두 조치를 함께 적용해야 한다.
- **malformed env 정책 (mode-aware)**: `WEB_TRUSTED_PROXIES` 에 invalid CIDR 토큰이 섞이면 `AGENT_MODE in {prod, staging}` 에서는 `RuntimeError` startup. `dev/test/""` 에서는 stderr WARNING + 해당 토큰만 skip + 진행.
- **proxy mode + empty env**: `ENABLE_WEB_TLS_PROXY=1` 인데 `WEB_TRUSTED_PROXIES` 가 비어 있으면 audit `IpAddr` 가 Caddy container IP 만 기록 (PIPA §29 접근기록 품질 회귀). prod/staging 은 `RuntimeError` startup, dev/test 는 stderr WARNING.
- **호환 영향 (WebAuditEvents.IpAddr / WebAuthSessions.RemoteAddr)**: 두 컬럼 모두 `VARCHAR(64)` — IPv4/IPv6 문자열 (최대 39자 + 가능 인터페이스 zone) 수용. schema 변경 없음.
- **TASK-0058 share token**: 사내 IP 가정과 동일 trade-off 였으나, 본 cycle 의 conditional trust 가 share token 의 `_get_client_ip()` 호출 경로에도 자동 적용된다. share token IP allowlist (별 cycle 보류) 는 본 정책의 audit IP 정확도 위에 build 한다.

### 9.8 WebAccountActivity 흡수 → DROP 완료 (Codex C2 → TASK-0086, 2026-05-20)

- TASK-0072 의 cross-account body search audit (`WebAccountActivity`) 가 TASK-0073 cycle 에서 `WebAuditEvents` 의 superset 으로 흡수됐고, **TASK-0086 (2026-05-20) 에서 legacy table DROP 완료**.
- `_migrate_web_account_activity_to_audit(conn)` migration helper — 기존 row → `WebAuditEvents` 변환 (ActionCode `conversation.search.body` transparent, ChangeJson `{query_hash, matched_count, _migrated_from, _original_id}`, OccurredAt = waa.CreatedAt). `RequestId='account-activity:<id>'` marker → idempotent. **TASK-0086 후 helper 는 rollback 1~2 cycle window 동안 보존** — `SHOW TABLES LIKE 'WebAccountActivity'` check 가 table-absent 시 silent return 0.
- `_log_search_activity()` — TASK-0072 dual write 패턴 → **TASK-0086 (2026-05-20) 에서 legacy INSERT 제거, dispatcher (`record_audit_event` → WebAuditEvents) 만 primary path**. signature transparent (caller 변경 0). dispatcher fail 시 stderr log + main flow 진행 (user endpoint fail-open).
- DROP 절차 (TASK-0086, Codex outside voice 5 findings 흡수 후 v2):
  1. `mysqldump --single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces` (Codex C4).
  2. scratch restore rehearsal (별 schema import + digest match — `a09e7898d1ce88711f7a850ab5fbcc91`).
  3. legacy ↔ mirror 1:1 정합 검증 (74=74).
  4. 사용자 명시 ack.
  5. 코드 변경 (legacy INSERT 제거 + `_ensure_web_account_activity_schema` 호출/정의 제거).
  6. lightweight import smoke.
  7. `DROP TABLE IF EXISTS WebAccountActivity`.
  8. `SHOW TABLES` = 0 + mirror row 보존 확인.
- Backup file: `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes). Row digest `a09e7898d1ce88711f7a850ab5fbcc91`. Rollback runbook 2 시나리오 (DB restore only / code revert + DB restore) — REPORT.md §1 Summary 참조.

### 9.9 보관 정책 + 외부 배포 보완 (TODO)

- 365 일 retention 권장. 운영자가 별 cycle 에서 cron purge 정책 결정 (PIPA §29 1 년 inherit, TASK-0072 정합).
- chunked PK 정책 + Phase 2 partitioning 은 row 수 100M+ 시 검토.
- `slow_query_log` (별 cycle 분리, Codex C1 lock-in) — DB-only retention / RBAC 정합 안 됨 → **ADR-0020 (2026-05-20) 에서 Decoupled 채택** (`docs/DECISIONS.md` ADR-0020). 주 근거 = **raw SQL text PII 차단** (PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt 가 SQL statement literal 로 들어가는 위험). slow_query_log 는 WebAuditEvents 와 통합 안 함. 운영 성능 관측 = `performance_schema` / `sys` digest views (1차) + slow_query_log incident 기반 enable (2차). raw SQL = 민감 로그로 간주, admin UI / ChangeJson 에 복제 금지.

본 정책 정본은 본 §9. dispatcher / builder / endpoint 정합은 [`unit/feature-0003-agent-web-ui/docs/FUNCTION.md`](../unit/feature-0003-agent-web-ui/docs/FUNCTION.md) AC-0159~AC-0189.

## 10. agent_runtime Postgres schema RBAC (AR-M0, 2026-05-27)

Phase 2 AR-M0 cycle 에서 `agent_kb` DB 안에 `agent_runtime` schema 신설. 기존 `agent_kb_rw` / `agent_kb_ro` role 을 재사용하고 새 schema 에 USAGE 부여.

### 10.1 schema 설계 원칙

- `agent_kb` DB 안 별도 schema 분리 (`agent_runtime`) — public schema 와 KB schema 오염 방지.
- DDL 은 superuser (`postgres`) 전용 — `agent_kb_rw` 는 DML 전용 (SELECT/INSERT/UPDATE/DELETE).
- schema-qualified SQL (`agent_runtime.core_conversations` 등) 로 명시 참조 — `search_path` 전역 변경 없음.

### 10.2 role 권한 (AR-M0 신설)

| Role | agent_runtime schema | 상세 |
|---|---|---|
| `agent_kb_rw` | USAGE + DEFAULT ALL TABLES | AR-M2 dual-write 부터 runtime INSERT/UPDATE. DEFAULT PRIVILEGES 설정으로 이후 생성 테이블에 자동 grant. |
| `agent_kb_ro` | USAGE + DEFAULT SELECT | read-only audit / debug 용. |
| `postgres` (superuser) | ALL | DDL (CREATE TABLE/INDEX) 전용. |

### 10.3 운영 절차

- `bin/agent-runtime-bootstrap.sh` — schema CREATE + role grant + 멱등. AR-M1 DDL 전에 1회 실행.
- AR-M1 DDL (6 runtime 테이블 CREATE) 후: `GRANT ALL ON ALL TABLES IN SCHEMA agent_runtime TO agent_kb_rw;` + `GRANT SELECT ON ALL TABLES IN SCHEMA agent_runtime TO agent_kb_ro;` 추가 실행 (AR-M1 bootstrap.sh 확장 예정).
- outside-voice review (REV-20260527-0002 SKIPPED) — AR-M0 는 기존 role 재사용 + schema 신설만. 신규 role 신설 없음. AR-M1 (DDL + RBAC) 에서 outside-voice 필수 (`feedback_outside_voice_for_rbac.md` 정합).

### 10.4 ADR 참조

- ADR-0021 (`docs/DECISIONS.md`) — KB Postgres role 분리 결정 (agent_kb_rw/ro 원조 정의).
- ADR-0026 (AR-M1 cycle 예정) — agent_runtime schema 분리 결정.
