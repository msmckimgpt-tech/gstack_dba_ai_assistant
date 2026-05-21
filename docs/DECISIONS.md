---
doc_type: PROJECT_DECISIONS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.9.0
domain: [architecture, history]
ai_read_priority: 9
---

# Project Decisions

## ADR-0001
- Status: accepted
- Date: 2026-03-25
- Context: 여러 AI와 사람이 동시에 작업할 때 현재 상태와 이력 문서가 섞여 혼란이 발생하기 쉬움
- Decision: 현재 상태 문서와 변경 이력 문서를 분리한다
- Consequences:
  - `FUNCTION.md`, `TASK.md`, `REPORT.md`는 현재 상태를 유지한다
  - `MODIFY.md`, `REVIEW.md`, `DECISIONS.md`는 append-only를 기본으로 한다

## ADR-0002
- Status: accepted
- Date: 2026-03-25
- Context: 에이전트별 정책 파일이 중복되면 지침 충돌이 발생할 수 있음
- Decision: `AGENTS.md`를 정본으로 하고 `CLAUDE.md`는 참조용으로 유지한다
- Consequences:
  - 저장소 수준 정책의 단일 기준점이 생긴다
  - 호환성은 유지하되 정책 중복을 줄인다

## ADR-0003
- Status: accepted
- Date: 2026-03-26
- Context: FIRST_REQUEST.md가 AGENTS.md 내용을 거의 그대로 재서술하여 "중복된 source of truth" 위반 발생
- Decision: FIRST_REQUEST.md를 부트스트랩 진입점 전용으로 축소하고, 신규 기능 시작 / 기존 작업 이어받기 두 시나리오를 분리한다
- Consequences:
  - 정책 내용은 AGENTS.md에만 존재
  - 새 AI는 시나리오에 따라 명확한 온보딩 경로를 가짐

## ADR-0004
- Status: accepted
- Date: 2026-03-26
- Context: "전권 위임" 목표와 §11 승인 필요 항목 간 구조적 모순이 존재
- Decision: 비동기 블로킹 흐름(BLOCKED 상태) + 사전 승인 범위(Pre-approved Scope) + 위험도 등급 분류(Critical/Major/Minor)를 도입한다
- Consequences:
  - AI가 승인 필요 항목에 도달해도 다른 태스크를 계속 진행 가능
  - 사전 승인 범위를 FUNCTION.md에서 기능별로 선언 가능
  - Minor 등급은 AI 자율 진행, Critical은 반드시 사람 승인

## ADR-0005
- Status: accepted
- Date: 2026-03-26
- Context: TASK.md가 source_of_truth: false로 되어 있어 작업 진행 상태의 정본이 모호
- Decision: TASK.md를 작업 진행 상태의 source of truth로 격상한다 (source_of_truth: true)
- Consequences:
  - 새 AI가 현재 진행 상황을 TASK.md에서 확인할 수 있음
  - 완료 체크리스트 섹션을 추가하여 완료 선언 절차를 명확화

## ADR-0006
- Status: accepted
- Date: 2026-03-26
- Context: TEST.md의 edit_policy가 rewrite여서 이전 테스트 실행 결과가 매번 덮어씌워짐
- Decision: TEST.md를 혼합 정책으로 변경 — 케이스 정의(§1, §2)는 rewrite, 실행 결과 이력(§3)은 append-only
- Consequences:
  - 회귀 발생 여부를 과거 테스트 결과와 비교하여 판별 가능
  - 테스트 결과 이력이 보존됨

## ADR-0007
- Status: accepted
- Date: 2026-03-26
- Context: §4 충돌 해석 원칙에서 "상위 문서 우선"과 "구체적 문서 우선"이 병존하여 AI 해석 오류 가능성
- Decision: "상위 문서 우선"을 주 규칙으로 확정하고, "구체적 문서 우선"은 같은 계층 내에서만 적용
- Consequences:
  - AGENTS.md(상위)와 기능 AGENTS.md(하위) 충돌 시 상위 우선이 명확
  - 같은 우선순위 수준에서만 구체성 원칙 적용

## ADR-0008
- Status: accepted
- Date: 2026-03-26
- Context: append-only 문서가 무한 증가하면 AI 컨텍스트 윈도우 소진 위험
- Decision: 20건 초과 시 아카이빙 정책을 도입한다 (_archive/ 디렉토리 사용)
- Consequences:
  - 현행 파일에는 최근 항목만 유지
  - 아카이브 참조 링크로 전체 이력 접근 가능

## ADR-0009
- Status: accepted
- Date: 2026-03-26
- Context: shared/ 디렉토리의 소유권, 변경 절차, 문서 구조가 없어 다중 AI 충돌 위험
- Decision: shared/에 README.md(거버넌스)와 MODIFY.md(변경 이력)를 두고, 변경 시 교차 참조 규칙을 적용한다
- Consequences:
  - shared 변경의 영향 범위를 역참조로 파악 가능
  - 대규모 변경은 별도 unit으로 관리

## ADR-0010
- Status: accepted
- Date: 2026-03-26
- Context: 프로젝트 전체 현황을 한눈에 볼 수 있는 문서가 부재하여 신규 AI의 전체 파악이 어려움
- Decision: `docs/STATUS.md`를 추가하여 기능별 상태, 의존성, 블로킹 항목, 전체 진행률을 관리한다
- Consequences:
  - 신규 AI가 하나의 문서로 프로젝트 전체 상황 파악 가능
  - 각 기능의 REPORT.md로부터 파생하여 갱신

## ADR-0011
- Status: accepted
- Date: 2026-03-26
- Context: `.gitignore`에 `../../artifacts/*` 같은 상위 디렉토리 패턴을 둘 수 없었음
- Decision: artifacts가 repo 외부에 있으므로 .gitignore에서 artifacts 관련 규칙을 제거한다
- Consequences:
  - .gitignore가 실제로 동작하는 규칙만 포함
  - artifacts는 repo 외부이므로 git 추적 대상이 아님

## ADR-0012
- Status: accepted
- Date: 2026-03-26
- Context: 기존 `mysql_ai`는 루트 중심 구조였고, 템플릿은 기능 단위 구조를 요구함
- Decision: 루트는 실행 진입점만 유지하고, 실제 구현은 `unit/<feature-id>/src`로 재배치한다
- Consequences:
  - 기능별 소유권이 명확해진다
  - compose/Makefile/Dockerfile은 새 경로만 참조해야 한다

## ADR-0013
- Status: accepted
- Date: 2026-03-26
- Context: 원본 프로젝트의 `shared/`는 런타임 데이터와 버전관리 자산이 섞여 있었음
- Decision: 런타임 데이터는 `../../artifacts`로 분리하고, `../shared/`는 공용 코드 예약 영역으로 제한한다
- Consequences:
  - 코드 저장소와 런타임 산출물 경계가 분리된다
  - 로그/세션/데이터 파일이 버전관리 대상에서 제외된다

## ADR-0014
- Status: accepted
- Date: 2026-03-26
- Context: 템플릿 이관 과정에서 `repo/.env` 값과 `repo/AGENTS.md` 의미가 원본 루트 프로젝트와 어긋나 포트, 모델, 운영 규칙 정합성이 깨졌음
- Decision: `repo/.env`는 원본 루트 `.env`의 운영 의미를 최대한 보존하고, `repo/AGENTS.md`는 원본 루트 지침을 템플릿 실행 루트 기준으로만 최소 변환한 정본으로 유지한다
- Consequences:
  - 템플릿 사본은 구조만 분리되고 운영 의미는 원본과 일치한다
  - `repo/.env.example`는 대체 기본값이 아니라 민감값 제거 샘플로 취급한다
  - 템플릿 사본은 원본과 동시 기동하지 않는 단독 실행 전제를 문서로 고정한다

## ADR-0015
- Status: accepted
- Date: 2026-03-30
- Context: 기본 템플릿이 v2.0.0으로 개선되어 Git 루트 경계, 환경변수 관리, 자격증명 패턴, artifacts 규칙, 도메인 커스터마이징 가이드 등이 추가됨
- Decision: 템플릿 v2.0.0 마이그레이션을 적용한다. 새 파일 복사, 기존 문서에 섹션 병합, .gitignore 보강을 포함한다
- Consequences:
  - 기능 템플릿에 src/README.md, tests/README.md 추가
  - 프로젝트 문서에 환경변수, 자격증명, artifacts, CI/CD 섹션 추가
  - AGENTS.md에 Git 루트 경계 규칙 추가
  - template_version: v2.0.0으로 갱신

## ADR-0016
- Status: accepted
- Date: 2026-04-13
- Context: 기본 템플릿이 v3.0.0으로 개선되어 AGENTS.md Part A~G 재구성, Plan-Review-Execute 프로토콜, .aiignore, LEARNINGS.md, CODEBASE_MAP.md, playbooks/, 병렬 AI 브랜치 전략, Glob 기반 조건부 규칙 등이 추가됨
- Decision: 템플릿 v3.0.0 마이그레이션을 적용한다. AGENTS.md 재구성, 8개 신규 파일(.aiignore, docs/LEARNINGS.md, docs/CODEBASE_MAP.md, playbooks/ 하위 5개) 추가, unit/_template 갱신(TASK.md §2 Implementation Plan, REPORT.md §8 Suggested Improvements, AGENTS.md §8.1 파일 패턴별 규칙)을 포함한다
- Consequences:
  - AI 위임 흐름이 Plan-Review-Execute 3단계로 구조화됨 (Minor=자율, Major=승인 대기, Critical=REPORT.md 기록)
  - .aiignore로 AI 컨텍스트 윈도우 효율화
  - LEARNINGS.md로 세션 간 교훈 전달 (mistake/pattern/quirk/preference)
  - CODEBASE_MAP.md로 신규 AI 온보딩 시간 단축
  - 반복 작업을 PB-0001~PB-0004 playbook으로 표준화
  - 병렬 AI 작업 시 브랜치 분리/Worktree 격리/문서 잠금 3단계 격리 지침 명문화
  - 섹션 번호 이동: 구 §19 → 신 §15 (도메인 커스터마이징), 구 §20.3 → 신 §16.3 (Git 동기화)
  - template_version: v3.0.0으로 갱신

## ADR-0017
- Status: superseded by ADR-0018 (2026-05-15)
- Date: 2026-04-14
- Context: `AGENTS.md`, `CONTRIBUTING.md`, `docs/GITHUB_AUTOMATION.md`, GitHub Actions 구현 사이에 공개 브랜치 규칙, `status:ready` 의미, 커밋 형식, main 병합 절차가 서로 다르게 정의되어 있었다
- Decision: GitHub 운영 흐름을 `Issue -> issue/<번호>-<slug> -> PR -> status checks -> auto-merge`로 일원화하고, 병렬 AI 작업은 로컬/worktree 전용 내부 `ai/<agent-id>/<issue-number>/<slice>` 브랜치 + 공개 `issue/*` 브랜치의 2계층 모델로 고정한다. 자동화 정본은 `.github/automation-contract.json`으로 관리하고 `policy-contract`에서 문서-자동화 정합성을 함께 검증한다
- Consequences:
  - `main` 직접 push 및 로컬 main 병합 절차를 정책에서 제거한다
  - `status:ready`는 권장 라벨로 유지하되 `ai-execute`의 필수 gate에서는 제외한다
  - 자동/수동 커밋 제목은 `type(scope): summary (#issue-number)` 형식으로 통일한다
  - `policy-contract`는 브랜치/PR 규칙 외에 커밋 제목과 자동화 계약 정합성도 검사한다
  - playbook, README, template 문서를 새 공개 브랜치 규칙과 동기화한다

## ADR-0018
- Status: accepted
- Date: 2026-05-15
- Context: ADR-0017 이 정의한 자동화 스택 (`ai-*` 워크플로, `policy-contract`, `selfhosted-runtime-smoke`, `owner-agent-report`, `automation-contract.json`) 이 self-hosted runner OAuth 만료·인프라 port 충돌·deprecated provider 라벨 등으로 더 이상 신뢰 가능한 머지 게이트로 동작하지 않게 됐다. stale required check 가 정상 PR 병합을 일관되게 차단해 운영 마찰만 키웠다
- Decision: 자동화 워크플로 전체 + `automation-contract.json` + `.github/scripts/*` + `docs/GITHUB_AUTOMATION.md` + AI 프롬프트 자산을 폐기한다. GitHub 운영은 `Issue -> issue/<번호>-<slug> -> PR -> 사람 리뷰 -> 일반 머지` 흐름으로 단순화한다
- Consequences:
  - `agent:claude` / `AI_PROVIDER_DEFAULT` 등 provider 라벨/변수는 더 이상 정책 의미를 가지지 않는다
  - PR 머지에 필요한 status check 는 사람 리뷰 + 로컬 `bin/verify-completion.sh` 결과로 대체한다
  - branch protection 의 required check 는 비워두거나 사용자가 새로 정의한다
  - 후속 작업으로 `playbooks/PB-0004-hotfix.md` 등 `policy-contract` / `ai-review` 를 참조하던 playbook 을 정리한다

## ADR-0019
- Status: accepted
- Date: 2026-05-19
- Context: TASK-0073 (REQ-20260519-0001, Critical §12.3) — 모든 계정의 mutation 행위 (admin 11 endpoint + user 5 endpoint) 와 anonymous share view 가 일관된 audit log 에 등재되어야 한다. 직전 TASK-0072 의 `WebAccountActivity` 는 cross-account body search 한정이라 admin actions (account update / role create / product CRUD / password-reset / system_prompt update) 와 user actions (`/api/ask`, share lifecycle, anonymous public view, share fork) 가 미감사 상태. CEO review 9 trade-off + Codex outside voice 14 findings (5 deadlock scenarios 포함) + Eng review 9 lock-in (E1~E9) 의 합의 진행
- Decision: `WebAuditEvents` 단일 테이블 + `record_audit_event(conn, ...)` dispatcher + ActionCode-specific `build_audit_change_json` builder allowlist + 두 helper (`_audit_admin_mutation` Same tx fail-safe / `_audit_user_action` fail-open best-effort) + `audit.read.own` / `audit.read.any` / `audit.export` / `audit.purge` 4 신규 권한 + permission group `audit` + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate + chunked PK purge with idempotency_key + WebAccountActivity 흡수 migration (dual write 일시 공존)
- Consequences:
  - `_log_search_activity` 의 signature 는 transparent 보존, 본문은 dual write — 기존 `WebAccountActivity` 별 cycle DROP 까지 양쪽 INSERT
  - admin 11 mutation endpoint 의 Same tx 정합 — audit INSERT 실패 = caller `conn.rollback()` + 500 응답 → mutation 전체 atomic
  - user 5 endpoint (`/api/ask` 포함) 는 fail-open — long-running LLM 실행과 audit 실패 격리, stderr log 만
  - `.own` SQL filter `WHERE ActorAccountId = :self OR TargetAccountId = :self` (Eng review E1 B) — admin password-reset / role grant / share revoke 등 admin→user 이벤트가 user 본인 audit 에 보임
  - anonymous share view = ActorType="anonymous" + ActorAccountId NULL + share_token_prefix 8 char (full token 차단)
  - prod 에서 `AGENT_AUDIT_ENABLED=1` 강제 — flag bypass surface 차단 (dev/test 만 toggle)
  - `slow_query_log` 통합은 별 cycle 분리 (Codex C1 — DB-only retention/RBAC 정합 안 됨) → **ADR-0020 (2026-05-20) 에서 Decoupled 채택 (raw SQL PII 차단 1순위)**
  - `WebAccountActivity` 테이블 DROP 은 별 cycle (data backup + dual write 검증 후) → **TASK-0086 (2026-05-20) 에서 DROP 완료**
  - `docs/SECURITY.md §9` (Audit subsystem 정책) 가 sensitive field catalog source-of-truth 가 된다
  - `docs/CONVENTIONS.md §10.6` audit permission group 추가 — admin section 의 관리 권한 묶음에 합류
  - `bin/verify-completion.sh check_11_audit_dispatcher` 가 dispatcher SPOF guard (Eng review E7)

## ADR-0020
- Status: accepted
- Date: 2026-05-20
- Context:
  - TASK-0088 (REQ-20260520-0003, Minor §12.3) — ADR-0019 의 Consequences 에 명시된 "`slow_query_log` 통합은 별 cycle 분리 (Codex C1)" lock-in 의 최종 결론 ADR. TASK-0073 cycle 진행 시 Codex outside voice C1 finding 이 DB-only retention/RBAC (WebAuditEvents 365일 + audit.purge gate + audit.read.any/.own) 과 file-based mysql server log (slow_query_log) 의 정합 불가능성 lock-in.
  - **Current state**: `repo/unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf` 에 `slow_query_log` / `slow_query_log_file` / `long_query_time` / `log_output` 설정 **부재** — MySQL 8.0 default disabled. 본 ADR 은 "현재 운영 로그 통합" 이 아닌 **"향후 slow query 관측을 WebAuditEvents 에 통합할지 여부"** 의 forward-looking 결정.
- Decision: **slow_query_log 를 WebAuditEvents 에 통합하지 않는다 (Option C — Decoupled)**. 주 근거 = **raw SQL text PII 차단** (PasswordHash / Token / API key / 임시 비밀번호 / raw LLM prompt 등이 SQL statement literal 로 들어가는 위험). 운영 성능 관측은 **`performance_schema` / `sys` digest-first** 권유, slow_query_log 는 incident / deep capture 용 제한.
- Options 검토:
  - **Option A — Sidecar ETL** (slow_query_log file → WebAuditEvents row 등재). **Reject**:
    - **raw SQL text PII**: SECURITY.md §9.2 의 redact 정책 (`PasswordHash`/`session_token_hash`/`api_key_*` etc.) 밖. literal 보존 위험.
    - **semantic pollution**: 성능 로그 ≠ 보안 audit. WebAuditEvents 의 actor/target/ResourceType 의미 모델과 충돌.
    - **ChangeJson / table bloat**: 고빈도 slow query 가 audit table 비대화 + ChangeJson size 폭증.
    - **actor/target 의미 부재**: WebAuditEvents schema 는 actor/target 강제, slow query 는 connection-level (account 매핑 불확실).
  - **Option B — 별 endpoint `/api/admin/slow-query-log`** (`audit.read.any` gate, file read + line filter). **Reject**:
    - **raw SQL exfiltration 표면 증가**: read-only mount 라도 endpoint 가 PII 노출.
    - **mount/rotation/race**: logrotate 중 partial read race window.
    - **대용량 파일 DoS**: tail/filter 가 대용량 slow_query_log 에서 timeout 또는 OOM.
    - **권한 의미 오염**: `audit.read.any` 는 "보안 audit 조회" 의도, "성능 로그 원문 조회" 아님 — confused responsibility.
    - **MySQL `log_output=TABLE` destination 도 지원** — file 접근만 차단해도 `mysql.slow_log` table 우회 가능. 별 권한 모델 필요.
  - **Option C — Decoupled (채택)**: 통합 안 함. WebAuditEvents = 보안 audit only. 성능 관측은 별 layer (mysql server log / performance_schema / 외부 분석 도구).
- Recommended performance path:
  - **1차 = performance_schema / sys digest views**: MySQL 8.0 의 `performance_schema.events_statements_summary_by_digest` + `sys.statement_analysis` — digest 기반 집계라 raw SQL text 노출 최소화. 운영자 (mysql root 권한) 가 접근. 단 PS 도 `SQL_TEXT` / `QUERY_SAMPLE_TEXT` 표면 잔존.
  - **2차 = slow_query_log incident 기반 enable**: deep capture 가 필요한 경우 운영자가 명시적으로 enable + 짧은 retention + 즉시 logrotate. host filesystem permission 통제. raw SQL = 민감 로그로 간주.
  - **분석 도구**: `pt-query-digest` (percona toolkit, slow log digest), `sys.statement_analysis` (MySQL 8.0 sys schema). 운영자가 host shell + 권한 으로 실행.
- Security policy:
  - **slow query raw SQL = 민감 로그**. WebAuditEvents / ChangeJson / admin UI 에 복제 금지 (PII 차단).
  - **host/container filesystem permission + 짧은 retention/logrotate** 로 보호.
  - **두 log cross-reference 안 함**: audit row 의 ChangeJson 에 query text 미포함.
- Consequences:
  - slow_query_log 는 현재 상태 (disabled) 유지. 운영자가 incident/deep capture 시점에만 enable.
  - 운영 성능 triage 1차 = `performance_schema` / `sys` digest views.
  - WebAuditEvents schema / RBAC / retention 정책에 slow query 통합 영향 0.
  - `docs/SECURITY.md §9.9` 에 본 ADR cross-reference 추가 — slow_query_log 가 보안 audit 표면 외임을 명시.
  - **외부 SaaS / multi-tenant trigger** (별 cycle 도입 조건): 외부 고객 tenant 운영자가 UI 에서 성능 로그를 봐야 하는 요구가 승인되는 시점 + 다음 모두 선행 충족:
    - 별도 `performance-log.read` permission 신설 (`audit.*` 와 분리, confused responsibility 차단)
    - raw SQL redaction / sampling 정책 (PII literal 제거 또는 hash)
    - retention + endpoint threat model ADR 선행
    - sidecar mount/rotation/race + DoS 대응 인프라
  - ADR-0019 의 lock-in 충실 이행 — Codex outside voice C1 finding 의 final 결론.
- Outside voice review trace: Codex consult mode (model_reasoning_effort=high, 390,785 tokens) 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign. 본 ADR 의 v1 초안이 (1) current state 부재 framing 오류, (2) Option A reject 사유 부정확 (retention/RBAC 가능), (3) Option B reject 약함 (mount/race/DoS/권한 오염 누락), (4) PII 가 주 근거여야 함, (5) performance_schema 누락 — 모두 ACCEPT 흡수. REV-20260520-0007 정본.
