---
doc_type: PROJECT_DECISIONS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.53.0
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
## ADR-0021
- Status: accepted (TASK-0018, M1 cycle, 2026-05-20)
- Date: 2026-05-20
- Context: TASK-0015 §2.1 PLAN-APPROVED 의 KB Postgres pgvector 마이그레이션 multi-cycle plan 의 M1 phase 에서 인증/인가 모델이 변경된다. M0 cycle 까지 KB 접근은 agent 컨테이너의 `mysql_connector` 가 root user 로 직접 접근하는 connection-level 권한 (RBAC catalog 외부) 이었다. M1 cycle 부터 KB 정본이 별도 Postgres 인스턴스 (`agent_kb` database) 로 이전되며 두 Postgres role (`agent_kb_rw` / `agent_kb_ro`) 을 신설한다. M-1 baseline 측정 (`artifacts/shared/kb-baseline-2026-05-20.json`) 의 RBAC audit 결과 `PERMISSION_DEFINITIONS` 40건 中 `kb.*` / `memory.*` / `agent_kb.*` = 0건으로 catalog 외부 접근 사실 정량 확인. outside-voice review (Plan subagent, `REV-20260520-0002`) Section D 가 정적 catalog blindspot 으로 식별. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정책의 "권한 모델 변경 plan 은 외부 시각 항상 호출" 적용.
- Decision: KB Postgres 분리 후 RBAC 권한 모델을 **2-layer hybrid** 로 재정의:
  - **Layer 1: connection-level (Postgres role)** — `agent_kb_rw` (SELECT/INSERT/UPDATE/DELETE on 5 KB tables + USAGE schema), `agent_kb_ro` (SELECT only on 5 tables + VIEW). agent 컨테이너의 `_pg_connect()` 가 사용하는 role 은 `AGENT_KB_PG_USER` 환경변수가 결정. M2 dual-write 부터 `agent_kb_rw` 권장 (superuser `postgres` 직접 사용 → `agent_kb_rw` 전환). 사람 audit / debug 는 `agent_kb_ro`.
  - **Layer 2: application-level RBAC catalog** — `PERMISSION_DEFINITIONS` 에 `kb.*` 신규 항목 추가:
    - `kb.read.own` — 자신이 actor 인 conversation 의 fact/RAG 조회 (all roles auto-grant)
    - `kb.read.any` — 전체 계정의 KB 조회 (admin / dba 권한)
    - `kb.mutate.any` — KB 직접 mutation (admin 만; agent 의 자동 write 와 별개 — 사람 직접 수정). 명명 일관성 (outside-voice REV-20260520-0005 권고): `audit.export` / `audit.purge` 같은 명사형 verb 패턴 정합. `write.any` 는 다른 catalog 항목에서 부재.
    - `kb.export` — KB 정본 CSV/JSON dump (admin / dba)
- Consequences:
  - **M2 dual-write 진입 전** `bin/kb-pg-role-bootstrap.sh --create-roles` 실행으로 두 role 생성. `agent_kb_schema.sql` 의 DO $$ block 이 schema 권한 grant 를 멱등 적용. **`--apply-schema` 단독 호출 시 role 미존재면 sql 안의 DO $$ GRANT block 이 silent skip — `--all` 또는 `--create-roles` 선행 필수 (outside-voice review REV-20260520-0005 Section C 권고)**. 호출 후 `\dp fact_entries` 또는 `has_table_privilege('agent_kb_rw', 'fact_entries', 'INSERT')` 로 grant 검증 권장.
  - **`.env` 의 `AGENT_KB_PG_USER`** 가 M2 진입 시점에 `postgres` → `agent_kb_rw` 로 변경. 사용자 명시 동작 (audit 추적성). 비밀번호는 `AGENT_KB_PG_PASSWORD` 가 `agent_kb_rw` 의 password 로 동기화.
  - **Password rotation graceful degradation (outside-voice Section B 권고)**: `bin/kb-pg-role-bootstrap.sh --rotate-password agent_kb_rw <new-pw>` 호출 후 `.env` 의 `AGENT_KB_PG_PASSWORD` 갱신 + `make restart` 까지 동안 agent 의 `_pg_connect()` 가 auth fail. 처리 순서: (1) `_pg_connect()` 가 `psycopg.OperationalError` raise → (2) `_pg_available()` 의 cached True 가 stale — caller 가 OperationalError catch + exponential backoff (1s/2s/4s) 3회 재시도 → (3) M2~M3 단계는 mysql fallback (`_dual_write_kb()` 가 mysql write 만 진행, postgres skip + 추후 reconcile), M4~ 단계는 fail-loud (KB read backend 가 postgres 라 fallback 없음 — 사용자 알림 필수). M2 plan 책임으로 backoff helper 추가.
  - **`PERMISSION_DEFINITIONS` 갱신** 은 본 ADR 의 시행 단계 (별 cycle, M2~M4 사이) 에서 `unit/feature-0003-agent-web-ui/src/app.py` 수정. 신규 4 항목 추가 + `audit` group 처럼 `kb` permission group 신설.
  - **`docs/SECURITY.md` 갱신** — RBAC 정책 표에 `kb.*` 추가, Sensitive field catalog 에 KB embedding 컬럼 (`texts.embedding`) 포함 (M3 backfill 시점부터 활성).
  - **`bin/verify-completion.sh`** 에 신규 check #13 후보: KB endpoint 가 catalog 정의대로 권한 게이트 호출하는지 정적 검증. 본 cycle 의 산출은 아님 — M2~M4 사이 별 cycle.
  - **Cross-DB audit log** (Section C 권고) — KB write 가 발생하면 `WebAuditEvents` (MySQL `agent_memory` DB) 에도 audit row INSERT. Postgres KB write 와 MySQL audit write 가 cross-DB tx 불가 → application-level best-effort 로 명시 (M2 dual-write 의 `_dual_write_kb()` 안에서 explicit audit call). 약화된 정합성은 REPORT.md 의 risk log 에 기록. **SLA 정량 약속 (outside-voice REV-20260520-0005 Section B 권고)**: audit INSERT 미실행 비율 **≤ 0.1% target** (M2 cycle 의 7-day stress run 검증). 초과 시 hard alert + M2 cycle rollback 결정. SLA 측정은 `bin/kb-dual-write-verify.sh --audit-sla` 로 별도 cycle 에서 자동화 — M2 plan 책임.
  - **Cycle 책임 명시 (outside-voice REV-20260520-0008 Blocker 7+8)**: M2-b (TASK-0020) cycle 의 `_DualWriteMirror` 가 audit explicit call **미포함** — `WebAuditEvents` INSERT 책임은 **M2-c cycle (별 cycle, TASK 미할당)** 에 위임. M2-c 산출: (a) `_DualWriteMirror._mirror()` 안에서 mirror 성공 시 `WebAuditEvents` audit row INSERT 추가 (ActionCode `kb.write.mirror`), (b) `bin/kb-dual-write-verify.sh --audit-sla --window-days 7` 의 실 호출 본문 구현, (c) 7-day stress run + miss_rate 측정 + alert threshold ≤ 0.1% 정합. **M2-c 진입 게이트**: M2-b commit + `AGENT_KB_PG_REQUIRED=1` + 사용자 명시 진행. M2-c 미완료 상태로 M4 cutover 진입 금지 (`bin/kb-cutover-readiness.sh` 의 (f) 항목 PASS 필수).
  - **`agent_kb_ro` 의 사용 사례** — 사람 audit / debug 시 `docker exec -e PGPASSWORD=<...> repo-postgres-1 psql -U agent_kb_ro -d agent_kb -c "SELECT ..."` 패턴. PII / sensitive embedding 조회 시 별도 audit trigger (M3+ ADR).
  - **Password rotation** — `bin/kb-pg-role-bootstrap.sh --rotate-password <role> <new-pw>` 가 ALTER ROLE 실행. .env 의 `AGENT_KB_PG_PASSWORD` 동기화는 사용자 책임 + agent 재기동.
  - **M4 cutover gate** — `bin/kb-cutover-readiness.sh` 가 본 ADR 의 시행 완료 (PERMISSION_DEFINITIONS 갱신 + `AGENT_KB_PG_USER=agent_kb_rw` 적용 + `agent_kb_rw` 로 `_pg_connect()` smoke PASS) 를 명시 게이트 항목으로 검증.
  - **M5 cleanup 후** — MySQL `AgentMemoryFactEntries` 등 DROP 후 catalog 에 `memory.*` 권한 신설 하지 않음 (`kb.*` 가 정본). 현재 catalog 에 `memory.*` 부재 — outside-voice REV-20260520-0005 Section E 식별 (text 정확성 정리).
  - **Sprint 4 D RAG namespace 격리 (outside-voice Section D 권고)**: 본 ADR 의 role 권한은 `agent_kb` database 의 `public` schema 기준. Sprint 4 가 별 database (`agent_drag`) 사용 시 `agent_kb_rw` 의 권한이 자연 격리 (database-level CONNECT 권한 미부여). 별 schema 분리 시 (예: 단일 database 안 `kb` / `drag` schema) `agent_kb_rw` 의 `ALTER DEFAULT PRIVILEGES IN SCHEMA public` 가 `kb` schema 만 cover 하도록 명시 — **ADR-0024 후보 (Sprint 4 와의 통합 시점)**.
- Outside-voice rationale: 본 ADR 은 RBAC catalog 변경 + 인증/인가 모델 변경의 결정 정본. outside-voice review (M1 cycle 의 Plan subagent 호출) 가 본 ADR 의 적절성을 검증. 결과는 REVIEW.md `REV-20260520-0005 [SUBAGENT:*]` 에 기록.
- Alternatives 검토 후 폐기:
  - **Single role + application-only RBAC** — Postgres role 1개 (superuser-ish) + 모든 권한 check 를 application layer. 폐기 사유: connection-level enforcement 없음 → SQL injection 또는 application bug 시 KB 전체 노출 risk.
  - **Per-user Postgres role** — 각 계정마다 별 Postgres role. 폐기 사유: 운영 부담 폭증 + agent 의 connection pool 분리 불가능. application layer 가 RBAC 분기 책임이 더 자연.
  - **Read replica 분리** — Postgres physical replica 로 agent_kb_ro 대체. 폐기 사유: M1 단계의 범위 외 — 별 ADR (M5+ 운영 최적화) 후보.
- 후속 액션:
  - **본 cycle (M1, TASK-0018)**: ADR-0021 정본 작성 ✓ + `bin/kb-pg-role-bootstrap.sh` ✓ + `agent_kb_schema.sql` 의 grant block ✓ + outside-voice review (`REV-20260520-0005`) ✓ + NEEDS-TWEAK Critical 4건 반영 ✓.
  - **M2 cycle** (별 cycle): `.env` 의 `AGENT_KB_PG_USER=agent_kb_rw` 전환 + `_dual_write_kb()` 안에 explicit audit call + password rotation backoff helper + `_ensure_pg_schema()` 자동 호출 trigger 결정 (startup? CLI?) + `has_table_privilege()` 검증 query 보강 + ivfflat NULL embedding 비율 게이트 (M3 readiness gate 의 사전 점검).
  - **M2~M4 사이 별 cycle (TASK 미할당 — RBAC catalog cycle)**: `PERMISSION_DEFINITIONS` 의 `kb.*` 4 항목 추가 (`kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`) + `docs/SECURITY.md` 의 RBAC 표 갱신 + audit SLA 측정 자동화.
  - **M2~M4 사이 별 cycle (TASK 미할당 — Dynamic grant blindspot cycle, outside-voice REV-20260520-0005 Section E Critical/Blocker)**: 정적 `PERMISSION_DEFINITIONS` 외에 `WebPermissions IsDynamic=1` row union 패턴 (TASK-0052 Phase 1B 같은 시간 제한부 grant) 의 `kb.*` 적용 검증. 사용자 메모리 정책 `feedback_outside_voice_for_rbac.md` 의 "정적 catalog blindspot 대응" 의 핵심 답. 예: `kb.read.any` 가 dba 만 영구 grant 외에 audit 시점에 한해 staff 임시 grant (24h TTL) 사용 사례. catalog 변경 cycle 보다 후, M4 cutover 게이트 전 완료.
  - **M4 cutover** (별 cycle): `bin/kb-cutover-readiness.sh` 에 본 ADR 시행 완료 게이트 항목 추가 — (a) `PERMISSION_DEFINITIONS` 의 `kb.*` 4 항목 존재, (b) `AGENT_KB_PG_USER=agent_kb_rw` 적용, (c) `agent_kb_rw` 로 `_pg_connect()` smoke PASS, (d) `has_table_privilege()` 검증 PASS, (e) Dynamic grant blindspot cycle 의 산출물 (PR merged) 확인, (f) Cross-DB audit SLA ≤ 0.1% 달성 (M2 stress run 결과).
  - **ADR-0024 후보 (Sprint 4 통합 시점)**: 본 cycle 의 schema 가 `public` schema 기준 — Sprint 4 의 `agent_drag` namespace 결정 시 grant scope 명시.

## ADR-0026
- Status: accepted (feature-0007, 2026-05-21, renumbered from ADR-0022 on
  2026-05-22 due to main branch ADR collision — main 이 분기 이후 ADR-0022/0023/
  0024/0025 추가 (TASK-0094 Sprint 1 Phase 1 MinIO 첨부 + TASK-0019 M2). 본 ADR
  의 번호를 ADR-0026 으로 재부여하여 정합. 본문 내용은 변경 없음.)
- Date: 2026-05-21
- Context: 기존 시스템은 사용자가 Profile drawer 의 "API Vault" wizard 에서 자기 OpenAI API key 를 평문 입력 → 브라우저에서 PBKDF2-SHA256 (100k iter) + AES-GCM 256bit 로 암호화 → `/api/ask` 호출 시마다 cipher + passphrase 동봉 → backend 가 `_decrypt_api_key` 로 transient 복호 → `OpenAI(api_key=...)` 직접 호출. 각 사용자가 OpenAI 비용을 자기 계정으로 부담하는 trust 모델. 본 시스템이 사내 직원 전용 도구로 확정되면서 (사용자 결정 2026-05-21) 운영자가 LLM 비용을 부담하는 단일 service-managed 자격증명 모델이 trust 모델 / UX / 운영 비용 책임 모두에서 자연스럽다고 판단.
- Decision: LLM provider 자격증명 모델을 **per-user OpenAI key → service-managed AWS Bedrock via OpenAI-compatible gateway (LiteLLM proxy)** 로 전환:
  - **Gateway 컨테이너**: `bedrock-gateway` (LiteLLM proxy) 를 `docker-compose.yml` 에 신규 추가. AWS IAM credential (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) 은 본 컨테이너 env 로만 주입. backend / frontend 는 `BEDROCK_GATEWAY_API_KEY` (gateway-token) 만 인지.
  - **모델 카탈로그**: `model_catalog.py` 의 `API_MODEL_OPTIONS` 를 OpenAI GPT-5.4 시리즈 3 종 → Anthropic Claude 4.x 2 종 (`claude-sonnet-4`, `claude-haiku-4`) 으로 교체. `API_DEFAULT_MODEL` 도 Claude alias.
  - **Region**: `ap-northeast-2` (Seoul) 한정 — cross-region inference 금지로 데이터 한국 region 잔류 (PIPA 정합).
  - **API Vault 폐기**: Profile drawer "API Vault" 탭 + step wizard DOM (index.html), `encryptPlainApiKey` / `readVaultState` / `writeVaultState` / `loadVaultOptions` 등 함수 (app.js), `.vault-*` CSS 클래스 (styles.css), `/api/api-vault/options` cipher 시멘틱 + `_decrypt_api_key` / `_is_safe_api_key` / `_is_safe_passphrase` 함수 + `/api/ask` 의 cipher 분기 (app.py) 일괄 제거.
  - **env 단일 소스**: `config.py` 의 `LLM_BASE_URL = BEDROCK_GATEWAY_URL or LOCAL_LLM_API_BASE or OPENAI_API_BASE or None`, `LLM_API_KEY = BEDROCK_GATEWAY_API_KEY or LOCAL_LLM_API_KEY or OPENAI_API_KEY` fallback chain. `_run_agent_core(api_key=...)` 인자 deprecated (받아도 무시).
- Consequences:
  - **사용자 결정 5 항목 정합**: (1) 사내 직원 전용 → 비용 책임 운영자 부담 OK / (2) per-user quota 후순위 (배포 후 별 cycle) / (3) 모델 1:1 매핑 보장 불필요 (사용자가 회귀 risk 수용) / (4) Seoul region 한정 / (5) API Vault 전면 폐기 (하이브리드 X).
  - **위험도 Major (§12.3)**: Critical 후보였던 외부 노출 / PIPA / 비용 폭주 risk 가 사내 한정으로 완화. 단 인증/인가 trust 모델 변경 + 모델 catalog swap 으로 인한 agent loop 회귀 가능성은 잔존 (Phase E 회귀 검증으로 확인).
  - **gateway SPOF**: bedrock-gateway 컨테이너가 단일 장애 지점. healthcheck 실패 시 web / agent / insight-worker 모두 502/503. 운영 mitigation = container 재시작 정책 (`restart: unless-stopped`) + healthcheck 12 retry × 10s = 2 min recovery window.
  - **데이터 잔류**: Seoul region 한정으로 Claude 응답 데이터가 미국 region 으로 전송되지 않음. 단 Bedrock Seoul region 에 특정 Claude 4 versioned model ID 미배포 시 본 cycle 의 default 모델 (`claude-haiku-4-20250514-v1:0`) 가용성을 운영자가 사전 검증 필요. 미배포 시 catalog 교체 + ADR-0022 보강.
  - **모델 ID drift risk**: AWS Bedrock 의 Claude 모델 versioned ID (예: `-20250514-v1:0`) 가 deprecate 될 가능성. `litellm_config.yaml` 의 model ID 가 single source-of-truth — 운영자가 AWS 의 model deprecation notice 를 모니터링 필요. 별 cycle 에서 ID rotation 정책 결정.
  - **per-user 비용 attribution 부재**: Bedrock 자체 기능 없음. 본 cycle 범위 외. 배포 후 비용 가시화 시점에 별 cycle 로 도입 — gateway 의 callback hook 으로 `WebAuditEvents.conversation.ask` ChangeJson 에 `input_tokens` / `output_tokens` 첨부 + per-user token quota 강제.
  - **frontend 모델 selector 단순화**: 구 API Vault 탭의 model selector 가 사라짐. 사용자는 별도 모델 선택 UI 없이 server default (`API_DEFAULT_MODEL = claude-haiku-4`) 사용. 향후 사용자 선택권이 필요해지면 composer 의 product chip 옆에 모델 selector 신설 가능 (별 cycle).
  - **rollback path**: 단일 commit revert + cache-bust 되돌리기. 단 사용자 frontend cache (localStorage v1: cipher) 의 cleanup 이 이미 수행되어 revert 후 사용자가 새로 키 입력 필요. 긴급 시 cherry-pick 가능.
- Outside-voice rationale: 본 ADR 은 RBAC 모델 변경 (사용자별 자격증명 → 단일 service 자격증명) + 비용 책임 이전 + 모델 catalog 전체 swap 의 결정 정본. 사용자 메모리 정책 `feedback_outside_voice_for_rbac.md` 적용 — 본 cycle 의 후속 cycle 또는 `/codex` outside voice 호출로 blindspot 검증 권장 (gateway SPOF / AWS credential leak 시 비용 폭주 시나리오 / Claude tool use schema 미호환 회귀).
- Alternatives 검토 후 폐기:
  - **boto3 + bedrock-runtime native 직접 호출** — provider abstraction wrapper 필요 + Anthropic Messages API / tool use / JSON mode schema 분기 도입. 폐기 사유: 본 cycle 의 코드 변경 범위 폭주. gateway 정상화 후 hotspot 만 native 로 마이그레이션 별 cycle.
  - **API Vault 유지 + OpenAI 그대로** — 폐기 사유: 사용자 결정 — 사내 한정 운영에서 사용자별 키 입력 진입 장벽이 부적합.
  - **하이브리드 (사용자 키 + 서비스 키 병존)** — 폐기 사유: 사용자 결정 — 두 trust 모델 동시 유지 부담 + 사내 효용 낮음.
  - **AWS Bedrock cross-region inference 허용** — 폐기 사유: 사용자 결정 — Seoul region 한정. PIPA 잔류 통제.
- 후속 액션:
  - **본 cycle (feature-0007)**: gateway + backend + frontend + 정책 doc 갱신 ✓. Phase E 회귀 검증 (실 환경 + AWS 자격증명) 은 사용자 수행.
  - **별 cycle (배포 후)**: per-user / per-role token quota + gateway callback hook 으로 token usage audit. AWS Cost Explorer tag 정책. 외부 비용 dashboard.
  - **별 cycle (운영 정상화 후 선택)**: boto3 + bedrock-runtime native 직접 호출로 hotspot 마이그레이션 (latency / cost / streaming 최적화 시 검토).
  - **별 cycle (PIPA 엄격 잔류 필요 시점)**: AWS Bedrock 의 Seoul region Provisioned throughput 예약 또는 별 provider (Anthropic API direct / Azure OpenAI Korea region / on-prem) 재검토. 본 cycle 의 global inference profile 사용은 사내 한정 + 비-개인정보 SQL 작업 가정 전제.

### 2026-05-21 Phase E 검증 결과 (ADR-0022 addendum)

본 ADR 의 초기 의도였던 "Seoul region 한정 + region-pinned model ID" 는 Phase E
실 환경 검증 (`docker compose -p feature-0007-e up -d bedrock-gateway` + 직접
호출 + gateway 경유 호출) 에서 다음 사실로 수정되었다:

1. **AWS Bedrock Seoul region 의 ACTIVE Claude 카탈로그** (`aws bedrock list-foundation-models --region ap-northeast-2 --by-provider anthropic`):
   - `anthropic.claude-sonnet-4-20250514-v1:0` — **LEGACY** (deprecate 진행)
   - `anthropic.claude-sonnet-4-5-20250929-v1:0` — ACTIVE
   - `anthropic.claude-sonnet-4-6` — ACTIVE (frontier)
   - `anthropic.claude-haiku-4-5-20251001-v1:0` — ACTIVE
2. **On-demand 호출 결과**: 4 모델 모두 region-pinned on-demand throughput 미지원
   — `BedrockException: ... isn't supported. Retry your request with the ID or
   ARN of an inference profile that contains this model.`
3. **Inference profile 목록** (`aws bedrock list-inference-profiles --region ap-northeast-2`):
   - `apac.anthropic.claude-sonnet-4-20250514-v1:0` — APAC, ACTIVE (단 LEGACY
     모델이라 30일 미사용 access denied → 실용 불가)
   - `global.anthropic.claude-sonnet-4-5-20250929-v1:0` — global, ACTIVE
   - `global.anthropic.claude-sonnet-4-6` — global, ACTIVE
   - `global.anthropic.claude-haiku-4-5-20251001-v1:0` — global, ACTIVE
4. **결론**: ACTIVE Sonnet 의 region-pinned (Seoul-only) ID 부재. **APAC profile
   도 LEGACY Sonnet 4 만 + 30일 미사용 차단**. ACTIVE Sonnet 사용 시 `global.*`
   inference profile 수용이 유일한 경로.

**사용자 reanchor 결정** (2026-05-21): Global Sonnet 4.6 수용 — 사내 한정 +
비-개인정보 SQL 작업 가정으로 PIPA risk 낮음. 본 ADR 의 "Alternatives 검토 후
폐기" 의 "AWS Bedrock cross-region inference 허용" 항목이 **사실상 채택** 으로
번복됨.

**`litellm_config.yaml` 변경**:
- `claude-sonnet-4` alias → `bedrock/global.anthropic.claude-sonnet-4-6`
- `claude-haiku-4` alias → `bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0`

**Full path 검증 PASS** (alias=`claude-sonnet-4`, system+user message, JSON mode):
- backend SDK → gateway (LiteLLM) → Bedrock `global.anthropic.claude-sonnet-4-6`
- STATUS 200, MODEL=`claude-sonnet-4` (alias 보존), CONTENT=`{"status":"PASS","echo":"phase-e"}`
  (markdown fence 안), FINISH=`stop`, USAGE 정상 (prompt 31 + completion 23 = 54).
- `_extract_json_object` 의 greedy `re.search(r"\{.*\}", ...)` 가 markdown fence
  안 JSON 도 정상 추출 — 별도 코드 변경 불요.

**잔존 risk**:
- Global routing → 데이터가 미국/EU region 으로 갈 수 있음. PIPA 엄격 적용 시
  잔류 보장 X. 사내 한정 + 비-개인정보 SQL 가정으로 본 cycle 수용.
- `apac.*` profile 이 미래에 ACTIVE Sonnet 으로 추가될 가능성 — 운영자가 AWS
  release note 모니터링 후 region-pinned 으로 마이그레이션 별 cycle.
- LiteLLM 의 boto3 retry / error mapping 이 Bedrock-specific error code 를
  HTTP 응답으로 transparently 전달하는지 운영 중 모니터링.
## ADR-0025
- Status: accepted (TASK-0025, M5 cycle, 2026-05-22)
- Date: 2026-05-22
- Context: TASK-0015 §2.1.3 M5 phase + ADR-0021 §Consequences (g) — M4 cutover (read path 전환) 후 MySQL KB 5 정본 (`AgentMemoryTexts` / `AgentMemoryFactEntries` / `AgentMemoryRagDocuments` / `AgentMemoryRagObjects` / `AgentMemoryFacts` VIEW) 의 deprecation 및 정리 timing/조건 결정. M2-d (TASK-0022) audit instrumentation + M3 (TASK-0023) backfill + M4 (TASK-0024) cutover 의 누적 위험 (rollback boundary) 을 본 ADR 에서 명문화. cutover 후 2주일 무회귀 confirm 의 정량 기준 + dual-write 로직 (`_DualWriteMirror`) deprecation timing 동반.
- Decision: **M5 cleanup 진입 게이트 + Stage A/B/C boundary + cleanup script 정책**:
  - **2주일 무회귀 confirm 정책**: M4 cutover 완료 시점 (= `.env` 의 `AGENT_KB_READ_BACKEND=postgres` 전환 + `bin/kb-cutover-readiness.sh` 10-gate PASS) 부터 **14 calendar day** 동안 다음 4 metric 모두 무회귀 (즉 baseline 대비 50% 이내 증가) 시 M5 진입 허용:
    1. `make ask` 5종 baseline 회귀 (M-1 baseline S1~S5)
    2. p99 latency (M2-d `get_mirror_metrics().latency_ms_max`)
    3. agent error rate (insight_route.log `error` 빈도)
    4. KB write SLA (`bin/kb-dual-write-verify.sh --audit-sla` ≤ 1000 ppm 유지)
  - **Stage 의 정의** (ADR-0021 §Consequences 재정의):
    - **Stage A** (M4 진입 직후 ~ M4 cycle 종료): rollback = 1줄 env (`AGENT_KB_READ_BACKEND=mysql`) + agent 재기동. dual-write 가 MySQL 정합 보존.
    - **Stage B** (M4 종료 ~ M5 진입 전, **2주일 monitoring window**): rollback = 동일. dual-write 유지 — read 만 Postgres.
    - **Stage C** (M5 cleanup 후): MySQL 5 정본 DROP 완료 → rollback = mysqldump restore (partial — M5 진입 timestamp 까지의 snapshot 만). 본 Stage 진입 = 데이터 손실 가능 시점.
  - **cleanup script (`bin/kb-cleanup-mysql.sh`)** 의 3 mode + safety:
    - `--dry-run` (default): DROP SQL 출력만, 실 변경 0.
    - `--backup-only`: mysqldump backup 생성만. `artifacts/shared/mysql-kb-backup-<ISO>.sql.gz` (보통 수 MB).
    - `--confirm I_UNDERSTAND_DATA_LOSS`: mysqldump backup → DROP 5 entries → DROP 검증. 정확한 confirm string 필수 (typo 방지). `AGENT_KB_READ_BACKEND=postgres` 확인 (cutover 전이면 진행 차단).
  - **dual-write 로직 deprecation**: 본 ADR 의 M5 진입 = `_dual_write_kb` mirror call 의 caller (utils.py / knowledge.py 5 위치) 코드 삭제 cycle 개시. 단 코드 삭제는 별 **M5-implementation cycle** 의 책임 — 본 cycle 의 `bin/kb-cleanup-mysql.sh` 는 DB 측 정리만 다룸. 코드 cleanup 의 outside-voice review 필수 (audit instrumentation 제거 = RBAC instrumentation 영향).
  - **audit ActionCode `kb.{write,delete,prune}.mirror`** 의 deprecation: M5 cleanup 완료 후 mirror 호출 0건 → audit table 의 `kb.*.mirror` ActionCode 도 자연 정지. `bin/kb-dual-write-verify.sh --audit-sla` 의 분모 → 0 (`INCONCLUSIVE` exit 2). 본 metric 은 M5 종료 시점에 archive (deprecated metric → M2/M3/M4 retrospective 용도 only).
- Consequences:
  - **rollback boundary 의 정량화** — 이전 ADR-0021 §Consequences 의 Stage A/B/C 가 정성적이었으나 본 ADR 이 14-day window + 4 metric 으로 정량화. 운영 자동화 가능 (예: 매일 cron 으로 `bin/kb-dual-write-verify.sh --all` 호출 + 14-day metric 추적).
  - **데이터 손실 boundary 명문화** — Stage C 의 mysqldump restore 는 M5 진입 시점까지의 snapshot 만. M5 이후 PG 측 새 row 는 mysqldump 에 없음 → restore 시 데이터 inconsistency. 이 risk 수용 = M5 진입 결정의 핵심 사람 confirm.
  - **`bin/kb-cleanup-mysql.sh --confirm` 의 정확한 string** — `I_UNDERSTAND_DATA_LOSS` 외 모든 input 거부 (대문자 + underscore). typo 또는 자동 실행 차단 의도.
  - **`_DualWriteMirror` deprecation** — M5 진입 → 코드 cleanup cycle (M5-implementation) → `_dual_write_kb` mirror call site (knowledge.py:633 `_publish_fact` + knowledge.py:598 `_prune_fact_entries_for_key` + utils.py:957 `_text_store_insert` + utils.py:1179 RagDocs + utils.py:1230 RagObjs) 삭제. 본 코드 cleanup 은 별 outside-voice review 필요 (RBAC instrumentation 제거 시점).
  - **`audit ActionCode kb.*.mirror`** archive — M5 후 mirror call 0건 → audit row 도 0 → `--audit-sla` exit 2 (INCONCLUSIVE). 이는 정상 — 본 metric 의 의미가 cutover-window 만 유효함을 명시.
- Alternatives 검토 후 폐기:
  - **M5 cleanup 없이 MySQL deprecated 상태 유지**: MySQL storage / memory / 운영 부담 누적. dual-write 코드도 유지 = M2/M3/M4 의 모든 instrumentation 영구 활성. M4 cutover 의 의미 손실.
  - **자동 cleanup (script 가 14-day monitoring 후 자동 DROP)**: 데이터 손실 boundary 의 사람 confirm 필수 — 자동화 거부. 본 ADR 의 `--confirm I_UNDERSTAND_DATA_LOSS` 가 명시 confirm.
  - **2주일 보다 짧은 monitoring window** (예: 1주일): 다음 회귀 risk:
    1. 운영 day-of-week pattern (월요일 traffic spike) 의 무회귀 확인 어려움
    2. insight_worker cycle 주기 (~수일) 가 충분히 발생하지 않음
    3. agent_memory_facts VIEW 의 multi-row tie-break (S6 시나리오) 의 실 traffic 검증 부족.
- 본 ADR 의 사전 조건:
  - M4 cycle (TASK-0024) 의 cutover readiness 10-gate 모두 PASS.
  - `bin/kb-cutover-readiness.sh` 의 Gate 7 (p99 latency) + Gate 9 (ask 5종 회귀) 가 운영 환경에서 PASS 확인 (현재 INCONCLUSIVE).
  - mysqldump artifact 의 storage path (artifacts/shared) 가 host volume 으로 마운트 + 적정 disk 여유 확인.
- Outside-voice rationale: 본 ADR 은 M5 cycle (TASK-0025) outside-voice review 의 PASS 결과로 채택. RBAC 영향 (audit instrumentation deprecation timing) + 데이터 손실 boundary 명문화 = 메모리 정책 `feedback_outside_voice_for_rbac.md` 정합.
- 후속 액션:
  - **본 cycle (M5, TASK-0025)**: ADR-0025 정본 작성 ✓ + `bin/kb-cleanup-mysql.sh` 생성 ✓ + dual-write deprecation 주석 docstring 갱신 ✓.
  - **M5-implementation cycle (별 cycle)**: `_DualWriteMirror` module + 5 caller mirror call 삭제. outside-voice review 필수.
  - **운영 turn (사용자 책임)**: 14-day monitoring + 4 metric 무회귀 확인 + `bin/kb-cleanup-mysql.sh --backup-only` + `--confirm I_UNDERSTAND_DATA_LOSS` 실행.

### ADR-0025 Addendum — Stage C 완료 (2026-05-27)
- Status: **Stage C 완료 (2026-05-27)**
- Context: 14-day monitoring window 만료 (cutover-date 2026-05-01, 경과 26일 > 14-day gate PASS). `KB_M5_RUN_FROM_HUMAN_SHELL=1 bin/kb-cleanup-mysql.sh --confirm I_UNDERSTAND_DATA_LOSS --cutover-date 2026-05-01` 실행. 스크립트 3종 수정 (commit 947fe6b): SIGPIPE false-negative 임시파일 방식, C-1 MYSQL_PWD env, grep -i 대소문자 무시.
- Outcome:
  - **backup**: artifacts/shared/m5-mysql-kb-backup-2026-05-27T052543Z/ (sha256: 5d760adf)
  - **DROP 완료**: VIEW AgentMemoryFacts + AgentMemoryFactHistory + AgentRAGDocuments + AgentRAGObjects + AgentTexts (5 객체)
  - **MySQL ABSENT**: information_schema TABLES COUNT=0 확인
  - **PG PRESENT**: fact_entries=780, rag_documents=840, rag_objects=780, texts=807
  - **app.py 28개 runtime PG 경로 추가** (commit 7bf7aaf): _get_history 500→200 수정, admin 대화수 PG, product UPDATE PG
  - **owner_account_id 복원**: AR-M5 backup 에서 core_conversations 35건 PG 업데이트
- 다음 단계: P1-T2 (M5-implementation cycle — `_DualWriteMirror` 코드 삭제), P1-T6 (7-day monitoring window 진행 중)

## ADR-0024
- Status: accepted (TASK-0019, M2 cycle, 2026-05-21)
- Date: 2026-05-21
- Context: TASK-0015 §2.1 PLAN-APPROVED 의 D-2 결정 (단일 Postgres cluster + 별 database) 와 outside-voice review `REV-20260520-0005` Section D 권고 ("`agent_drag` namespace 격리 미명시, ADR-0024 후보") 가 본 ADR 의 motivation. 직전 세션의 multi-cycle plan 의 Sprint 4 (D RAG, PGVector 도입) 가 동일 Postgres cluster 안 별 database 또는 schema 로 분리될 예정이지만 정본 위치를 본 cycle 에서 확인 불가 (Blocker B-1). 본 plan 의 `agent_kb` namespace 와 Sprint 4 의 `agent_drag` namespace 가 schema-level vs database-level 격리 중 무엇을 채택해야 KB 의 RBAC role (`agent_kb_rw` / `agent_kb_ro`, ADR-0021) 과 Sprint 4 의 role 이 자연 격리될지 결정.
- Decision: **단일 Postgres cluster + 별 database 격리** 채택. KB 정본 = `agent_kb` database, Sprint 4 D RAG = `agent_drag` database (또는 Sprint 4 의 결정에 따른 다른 명 — 본 ADR 은 `agent_drag` 를 placeholder 로). Postgres role 의 `CONNECT` 권한이 database-level 이라 schema-level 분리보다 격리 강도 높음.
- Consequences:
  - **`agent_kb_rw` / `agent_kb_ro`** (ADR-0021) 의 `CONNECT ON DATABASE agent_kb TO ...` grant 가 `agent_drag` 접근 차단 — 자연 격리.
  - **Sprint 4 의 D RAG role** (별도 신설 예정) — `agent_drag_rw` / `agent_drag_ro` 명 권장 (네이밍 일관성). Sprint 4 의 ADR 책임.
  - **cluster-level fault** (shared_buffers, WAL, connection pool 등) 는 양 도메인 동시 영향 — `pgvector/pgvector:pg16` 단일 컨테이너의 메모리 footprint 가 두 도메인 합산. M4 cutover gate 의 메모리 측정 (Open Q #2) 에 포함.
  - **백업/관측 통합** — `docker exec repo-postgres-1 pg_dump agent_kb` 와 `pg_dump agent_drag` 가 동일 컨테이너에서 호출. 단일 dump volume 사용.
  - **schema-level 분리 옵션 폐기** — 단일 database (예: `agent_pg`) 안 두 schema (`kb`, `drag`) 분리는 role 권한 정의 복잡도 폭증 (`ALTER DEFAULT PRIVILEGES IN SCHEMA kb` + `... IN SCHEMA drag` 양쪽 따로) + 잘못된 schema 접근 risk. database 분리가 더 안전.
  - **별 인스턴스 옵션 폐기** — Topology D-2 의 Alternative B (별 Postgres 인스턴스) 는 운영 부담 2배. 본 plan 규모에서는 과대.
  - **agent 컨테이너의 connection pool** — `agent_kb` connection (`_pg_connect()`) + `agent_drag` connection (Sprint 4 의 helper) 2 pool 자연 분리. memory footprint ~10MB × 2 = ~20MB. 본 plan 의 `_pg_connect()` 에서 database arg 는 명시 (`AGENT_KB_PG_DB` default `agent_kb`). Sprint 4 는 별도 env (`AGENT_DRAG_PG_DB` 권장).
  - **docker-compose `postgres` 서비스** — 본 plan M0 (TASK-0017) 가 `POSTGRES_DB=agent_kb` 로 default. Sprint 4 진입 시 `POSTGRES_DB` 환경변수가 `agent_kb` 만 보장 — Sprint 4 의 D RAG 는 `bin/kb-pg-role-bootstrap.sh` 와 유사한 `bin/drag-pg-role-bootstrap.sh --create-db` 로 별도 database 생성. 본 cycle 의 `kb-pg-role-bootstrap.sh` 가 reference 패턴.
- Alternatives 검토 후 폐기:
  - **단일 database 안 두 schema 분리** — 위 §Consequences 참조. role 권한 복잡도 + cross-schema 접근 risk.
  - **별 Postgres 인스턴스** — 운영 부담 2배.
  - **본 plan 의 KB 가 Sprint 4 의 D RAG schema 와 공유** — 본 cycle 의 schema (fact_entries / texts / rag_documents / rag_objects) 가 Sprint 4 의 D RAG schema 와 column 구조 정합 가정 필요. Sprint 4 plan 정본을 본 cycle 에서 확인 불가 → 검증 안 됨. **자연 격리 (별 database) 가 더 안전**.
- 본 ADR 의 사전 조건 (Sprint 4 와 통합 시점 확인 필요):
  - Sprint 4 의 D RAG 가 본 ADR 의 `agent_drag` database 가정을 수용한다면 자연 호환. Sprint 4 가 별 schema (`agent_pg.drag.*`) 또는 동일 schema 공유 (예: `agent_kb.rag_objects` 를 D RAG 가 같이 INSERT) 결정 시 본 ADR superseded — 그 시점에 ADR-0025 후보.
  - Sprint 4 의 schema 가 본 plan 의 `rag_objects` / `rag_documents` 와 column 정합 — 동일 schema 공유 가능 시 Sprint 4 cycle 에서 본 ADR 의 격리 정책 ALTER.
- Outside-voice rationale: 본 ADR 은 outside-voice review `REV-20260520-0005` Section D 의 Blocker 직접 해소. 본 turn 의 M2 cycle outside-voice review 가 본 ADR 의 적절성을 다시 검증.
- 후속 액션:
  - **본 cycle (M2, TASK-0019)**: ADR-0024 정본 작성 ✓ + Sprint 4 plan 의 D RAG schema 확인 (사용자 직접 — Blocker B-1) 시점에 재검토.
  - **Sprint 4 cycle**: 본 ADR 의 가정 (별 database `agent_drag`) 수용 여부 결정. 다른 결정 시 본 ADR superseded.
  - **M4 cutover gate**: `bin/kb-cutover-readiness.sh` 에 "본 ADR 의 namespace 격리 verify" 명시 항목 추가 — `psql -U agent_kb_rw -d agent_drag` 가 `permission denied for database` 실패 확인 (격리 정상).

## ADR-0022
- Status: accepted (TASK-0094 Sprint 1 Phase 1, 2026-05-21)
- Date: 2026-05-21
- Context: TASK-0094 (REQ-20260521-0001, Critical §12.3 — 첨부 multi-cycle A+B+C+D) Sprint 1 의 prerequisite. BRIEFING §2.2 D1 사용자 직접 확정 "첨부 파일 저장 위치 = S3-compat (MinIO compose +1)". 첨부 객체 (CSV/XLSX/PDF/이미지) 의 영속 저장이 필요하며, AWS S3 의 protocol-compat 자가 호스팅 옵션 중 MinIO 가 docker-compose 단일 service 로 가장 간단. 사내망 다운로드는 signed URL 로 frontend 노출, 외부 LLM 송신은 server-side bytes read 후 base64/files API 로 전달 (BRIEFING D13 — signed URL 외부 송신 금지).
- Decision: docker-compose 에 MinIO 단일 service 도입 (`minio` + `minio-init` one-shot). Bucket: `agent-attachments`. Volume: `../artifacts/minio-data:/data`. Healthcheck 포함. minio-init 부트스트랩이 bucket idempotent 생성 + lifecycle policy 적용 (D6 delete_reason 별 retention) + root credential 비활성화 + app 전용 access key 생성. App key rotation 은 ADR-0023 의 maintenance path 와 별개로 D20 dual-key rotation runbook 따름. 외부 (NAS / SaaS) 옵션은 본 cycle scope 외.
- Consequences:
  - compose service count +2 (`minio` api 9000 / console 9001, `minio-init` one-shot). feature-0001-platform-runtime ANCHOR §1 갱신.
  - `feature-0003-agent-web-ui/src/modules/storage_minio.py` 신규 — boto3 + retry + signed URL helper + backup smoke test.
  - `.env.example` MinIO 14 변수 (MINIO_ROOT_USER/PW bootstrap 전용 + MINIO_APP_ACCESS_KEY/SECRET app rotation 대상 + endpoint/bucket/TTL + ATTACHMENT_MAX_BYTES_* cap 3 + ATTACHMENT_AUDIT_HMAC_KEY + SANDBOX_SQL_* 2).
  - SECURITY.md §7.2 (외부 배포 보완) 갱신 — 사내 IP 만 MinIO 접근 가능. signed URL 은 frontend 다운로드 전용.
  - D20 dual-key rotation runbook 별 cycle subtask (Phase 4 — storage wrapper 와 동시 ship).
- Options 검토:
  - **AWS S3** (or compatible managed) — 운영 의존 + 비용. 사내망 단일 호스트 환경에 비대.
  - **로컬 파일 시스템 (artifacts volume 직접 mount)** — D6 retention / lifecycle / signed URL / RBAC 미흡. backup/restore 곤란.
  - **MinIO (선택)** — single docker service, S3 protocol compat, lifecycle / IAM 지원. boto3 reuse 가능. Self-host 단순.
- Alternatives considered (Sprint 4 D RAG 통합 가능성): MinIO 단일 bucket 으로 attachment + RAG document 객체 모두 수용 가능하나, 본 ADR 은 attachment scope. RAG 객체 저장 (PDF 원본 / chunked text) 은 Sprint 4 plan 에서 별 bucket vs prefix 결정.
- Outside-voice rationale: BRIEFING REV-20260520-0001 Codex Claim #20 "MinIO bootstrap / lifecycle / app key 운영 항목" 흡수 + REV-20260521-0002 Codex F9 "dual-key rotation runbook" 흡수. 본 ADR 은 D20 dual-key rotation 을 Sprint 1 Phase 4 의 ship 조건으로 명시.

## ADR-0023
- Status: accepted (TASK-0094 Sprint 1 Phase 1, 2026-05-21)
- Date: 2026-05-21
- Context: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 의 prerequisite. BRIEFING §2.2 D2 사용자 직접 확정 "Sandbox DB 격리 = 동일 cluster + 별 schema". CSV/XLSX ingest 결과를 query 가능한 SQL 객체 (table) 로 만들기 위해 dynamic schema 생성 필요. 별 cluster (cluster 분리) 는 운영 / backup / migration 비용 2배. 동일 cluster + 별 schema 가 D14 SQL guard (AST allowlist) + D15 grant 정책 + R-Claim4 maintainer wildcard 제거 + R-F4 drift health endpoint 의 조합으로 격리 요구를 충족.
- Decision: Sandbox schema 명명 = `agent_attachment_<sha256(conversation_id)[:32]>`. Mapping table `WebConversationAttachmentsSandboxSchemas(ConversationId, SchemaName, CreatedAt, DroppedAt)`. **D15 maintenance path 분리** (R-Claim4 흡수):
  - `attachment_maintainer` MySQL user — schema 생성/삭제 전용. wildcard `CREATE / DROP SCHEMA on agent_attachment_*` 는 maintainer 전용 grant (writer/reader 와 분리).
  - `attachment_writer` MySQL user — schema 생성 직후 maintenance path 가 **exact backtick schema 명** 으로 `CREATE / ALTER / INSERT / SELECT` (GRANT ALL 금지) per-conversation grant. 신규 schema 만 접근 가능.
  - `attachment_reader` MySQL user — D14 SQL 실행 user. 정본 SELECT-only + sandbox SELECT-only.
  - `attachment_cleanup` MySQL user — DROP SCHEMA only on per-schema grant (reconciliation worker 전용).
- Consequences:
  - 4 MySQL user 신설 — credentials 는 `.env` 만, MODIFY 명시 + cycle CHG 에 grant pattern 명시.
  - R-F4 drift detection: `WebConversationAttachmentsSandboxSchemas` 의 expected grants 와 실제 `information_schema.schema_privileges` 의 drift 를 `attachment_grant_audit` worker 가 5 분 주기로 detect. drift 시 admin alert + `/api/admin/health/attachment-grants` health endpoint.
  - Sprint 1 Phase 10 (sandbox schema + MySQL users) 의 ship 조건.
- Options 검토:
  - **별 cluster** (D2 Alt-A) — 운영 / backup / migration 비용 2배. 본 wedge 에 비대.
  - **단일 schema + per-conv prefix table** (D2 Alt-B) — `<conv_id>_filename` table 명. table 이름 길이 제한 64 글자 + sha256[:32] 도 그 안에 fit 하지만, schema-level isolation 부재라 `attachment_reader` 가 한 user 의 모든 첨부 table 을 다른 user 의 첨부와 동시에 SELECT 가능 → leak 위험.
  - **동일 cluster + 별 schema (선택)** — schema-level grant 로 격리, mapping table 이 lifecycle 추적. ADR-0019 (audit) / ADR-0021 (KB 2-layer hybrid) 의 connection-level grant 패턴과 정합.
- Outside-voice rationale: BRIEFING REV-20260520-0001 Codex Claim #5 (sandbox name collision — hash mapping 흡수) + Claim #4 (wildcard grant — R-Claim4 흡수) + REV-20260521-0002 Codex F4 (grant drift — health endpoint 흡수). 본 ADR 은 R-Claim4 의 writer 최소권한 (CREATE/ALTER/INSERT/SELECT) 을 명시 lock-in.

## ADR-0025
- Status: accepted (TASK-0094 Sprint 1 Phase 1, 2026-05-21) — supersedes ADR-0024 의 attachment scope 부분
- Date: 2026-05-21
- Context: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 4 (D PDF RAG) 의 prerequisite 사전 선언. BRIEFING §2.2 D3 사용자 직접 확정 "vector store = PGVector (Postgres 도입)" + D10 단계적 정책 "dev 1차 = agent_memory 와 동일 컨테이너 + DB 분리, prod = 별 instance 옵션 PLAN gate 재검토". ADR-0021 (KB Postgres + 2-layer hybrid) 와 ADR-0024 (KbBackend ABC + agent_drag namespace) 가 KB 도메인용. **본 ADR 은 attachment RAG 의 vector store 사전 결정** — Sprint 4 cycle 진입 시 ADR-0024 의 `agent_drag` namespace 가정 검증 + attachment-specific schema 결정 진행.
- Decision: attachment RAG 의 vector store 는 **PGVector**. 단계적 도입:
  - **Sprint 4 dev / 1차**: 기존 Postgres 컨테이너 (ADR-0021 의 `agent_kb` 와 같은 instance) + 별 database (`agent_drag` ADR-0024 가정 또는 `agent_attachment_rag` 본 cycle 결정 — Sprint 4 진입 시 lock-in). user 분리 (`rag_writer` / `rag_reader`) 는 ADR-0021 의 `agent_kb_rw` / `agent_kb_ro` 패턴 재사용.
  - **Sprint 4 prod / 2차**: 운영 경계 분리 옵션 — 별 PGVector instance 사용 시 backup/restore/migration 의 독립적 cadence 확보. **PLAN gate 에서 재검토** (Sprint 4 진입 시점).
  - 본 Sprint 1 (Cycle 0/1) 은 PGVector compose service 추가 안 함. Sprint 4 진입 cycle 의 PLAN-APPROVED 가 compose service 추가 trigger.
- Consequences:
  - 본 Sprint 1 Phase 1 에서는 docker-compose.yml 의 minio + minio-init 만 추가. PGVector 는 Sprint 4 진입 시 별 ADR-XXXX (또는 본 ADR 의 후속 갱신) 으로 service 추가.
  - Sprint 4 cycle 의 first action: ADR-0024 의 `agent_drag` namespace 가정 vs 본 ADR 의 `agent_attachment_rag` 가정 정합 확인 + lock-in. 충돌 시 ADR-0024 superseded 또는 본 ADR 의 namespace 변경.
  - 본 ADR 은 D10 의 dev/prod 단계적 정책을 ship 시점 분리 — Sprint 4 cycle 의 PLAN gate 에서 prod 별 instance 옵션 재검토.
- Options 검토:
  - **Pinecone / Weaviate / Milvus / Qdrant (관리형 또는 별 도커)** — 운영 의존 추가. backup/restore policy 별도 학습. 본 wedge 에 비대.
  - **PGVector dev 단계 = agent_memory 와 동일 컨테이너** — D10 1차 정책. backup / restore / migration restart 가 같은 장애 도메인.
  - **PGVector prod 단계 = 별 instance** — D10 prod 단계 PLAN gate. backup / restore / migration restart 의 운영 경계가 컨테이너 단위라 같은 장애 도메인 묶음은 dev-only.
- Alternatives considered: Sprint 4 의 D RAG 가 ADR-0024 의 `agent_drag` namespace 와 통합 가능하다면 본 ADR 의 attachment-specific schema 는 별 cycle 의 schema migration 로 흡수 가능. Sprint 4 cycle 의 ship 조건에 본 ADR 의 가정 검증 항목 명시.
- Outside-voice rationale: BRIEFING REV-20260520-0001 Codex Claim #17 (PGVector dev / prod 운영 경계) 흡수. 본 ADR 은 D10 의 단계적 정책을 사전 선언 — Sprint 4 cycle 의 PLAN gate 가 prod 별 instance 결정의 final lock-in.

### 2026-05-22 env_file scoping + OpenAI API Key 폐기 (ADR-0026 addendum)

feature-0007 의 follow-up cycle (CHG-20260522-0005 / CHG-20260522-0006) 결과
ADR-0026 의 "AWS 자격증명은 bedrock-gateway 만 인지" 정책을 docker-compose 의
실 구성으로 강제:

1. **Secret 영역별 .env 분리** (CHG-0005, 사용자 결정 2026-05-22 — 모든 secret
   영역 분리): `.env.bedrock` (AWS_*) / `.env.mysql` (MYSQL/DB password) /
   `.env.postgres` (KB password) / `.env.minio` (MinIO root + app) / `.env.llm`
   (gateway token). 각 docker-compose service 가 자기 secret 만 inherit.
   `bedrock-gateway` 만 AWS_* 노출.
2. **OpenAI API Key 폐기** (CHG-0006, 사용자 결정 2026-05-22): `_select_llm_provider()`
   의 OpenAI direct fallback 분기 제거. LLM 호출 entry 는 Bedrock gateway
   또는 Local LLM gateway 만. 운영 .env 의 잔존 `OPENAI_API_KEY` silent ignore.
3. **운영자 마이그레이션 1 회**: 기존 단일 .env 의 secret 행을 새 분리 파일들
   로 옮기는 작업. `.env.example` 헤더에 가이드 명시.

본 addendum 후 SECURITY.md §6.1 의 false-claim ("gateway 컨테이너 env 에만
주입") 이 실 구성과 정합 — least privilege 강제 보장.

## ADR-0027
- Status: accepted (TASK-0112, AR-M1 cycle, 2026-05-27)
- Date: 2026-05-27
- Context: TASK-0109 `docs/MIGRATION_AGENT_MEMORY_TO_PG.md` Phase 2 AR plan 의 M1 phase. MySQL `agent_memory` DB 의 6 agent runtime 테이블 (AgentCoreConversations / AgentCoreMessages / AgentMemoryKv / AgentMemoryMessages / AgentMemorySteps / AgentMemorySummary) 을 PostgreSQL `agent_kb.agent_runtime` schema 로 이관하기 위해 DDL 정본 및 RBAC grant 결정이 필요하다. AR-M0 (TASK-0111) 에서 `agent_runtime` schema 와 role grant (USAGE + DEFAULT PRIVILEGES on `agent_kb_rw` / `agent_kb_ro`) 가 기설정됨. 본 ADR 은 M1 의 테이블 구조 설계 결정을 명문화한다. outside-voice review (backend+qa subagent, `REV-20260527-0003`) Verdict PASS — Critical 2건 (C1 kv FK 생략 명시화, C2 meta_json jsonb 전환) 반영 후 apply.
- Decision: **6 테이블 DDL 설계 정책**:
  - **스키마**: 모든 테이블을 `agent_runtime` schema 에 생성 (search_path 전역 변경 없음 — schema-qualified SQL 강제). AR-M2+ 의 dual-write SQL 에서 `agent_runtime.core_conversations` 등 명시 필수.
  - **PK 전략**: conversation_id varchar(128) PRIMARY KEY (core_conversations, summary) — UUID 스타일 string, MySQL 원본 그대로 유지. bigint GENERATED ALWAYS AS IDENTITY (core_messages, messages, steps) — MySQL AUTO_INCREMENT 대체, ALWAYS 정책 (override 금지). 복합 PK (conversation_id, key) (kv) — MySQL 원본과 동일.
  - **타입 변환**: `varchar(N) COLLATE utf8mb4_*` → `varchar(N)` (Postgres default UTF-8), `longtext` → `text`, `timestamp(3) ON UPDATE CURRENT_TIMESTAMP` → `timestamptz + BEFORE UPDATE trigger`, `json` → `jsonb`.
  - **FK 정책**: core_messages, messages, steps, summary 4 테이블에 `CONSTRAINT fk_* FOREIGN KEY (conversation_id) REFERENCES agent_runtime.core_conversations (conversation_id) ON DELETE CASCADE` 명시. **kv 테이블은 FK 의도적 생략** — `conversation_id='__global__'` sentinel (cross-conversation KV; baseline 측정 기준 1588건) 이 core_conversations 에 미존재하므로 FK 적용 시 전체 INSERT 실패. application-level validation 으로 대체 (MySQL 원본 정책 유지). 이 결정을 SQL 파일 주석 및 본 ADR 에 명시하여 향후 reviewer 의 "oversight인지 intentional인지" 혼동 차단.
  - **meta_json 타입**: `agent_runtime.messages.meta_json` 는 `jsonb` (outside-voice C2 반영 — MySQL AgentMemoryMessages.MetaJson 의 내용이 JSON 구조이며, Postgres jsonb 사용 시 `->` / `@>` 연산자 및 압축 이점 확보; AR-M3 backfill 시 JSON 유효성 검증 게이트 추가 예정).
  - **RBAC grant**: `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA agent_runtime TO agent_kb_rw` + `GRANT SELECT ON ALL TABLES IN SCHEMA agent_runtime TO agent_kb_ro` + `GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA agent_runtime TO agent_kb_rw`. 신규 role 신설 없음 — ADR-0021 의 기존 2-layer hybrid (agent_kb_rw / agent_kb_ro) 재사용.
  - **인덱스 전략**: owner_account_id, product_id, updated_at (core_conversations), (conversation_id, id) (core_messages), updated_at (kv), (conversation_id, created_at DESC) (messages), (conversation_id, created_at DESC) + (conversation_id, run_id) (steps). `steps.(conversation_id, run_id, step_index)` 복합 인덱스는 N3 (nice-to-have) — AR-M2+ 실 query pattern 확인 후 추가.
- Consequences:
  - **AR-M2 dual-write 진입 전**: `bin/agent-runtime-schema-compare.sh` PASS 확인 필수. 6 테이블 × 컬럼 정합 검증 (MySQL 원본 PascalCase ↔ Postgres snake_case norm 비교).
  - **AR-M3 backfill**: kv 테이블의 `__global__` 행 (1588건) 을 FK 없이 삽입 — 정상. messages.meta_json 의 jsonb 전환 시 MySQL 측 non-JSON 값이 있으면 CAST 실패 → backfill 에 JSON 유효성 pre-check 게이트 추가 (본 ADR 의 의도적 설계 결과).
  - **search_path 전역 변경 없음** — `_pg_connect()` 및 `_pg_connect_ro()` 의 conninfo 에 `search_path` 파라미터 추가 금지. AR-M2 SQL 작성자는 `agent_runtime.table_name` 형식으로 명시.
  - **superuser vs rw role**: AR-M0 의 `agent_runtime` schema CREATE 는 superuser (`postgres`) 로 실행. AR-M1 DDL apply 도 superuser. AR-M2+ 의 DML (INSERT/UPDATE/DELETE) 은 `agent_kb_rw` role 로 전환 — `_pg_connect()` 의 `AGENT_KB_PG_USER=agent_kb_rw` 설정 기준.
- Alternatives 검토 후 폐기:
  - **kv 에 FK 추가 + __global__ 별 table 분리**: `__global__` scope 를 별도 `agent_runtime.kv_global` 테이블로 분리하면 FK 적용 가능. 폐기 사유 — callsite 54건 (feature-0002) + 105건 (feature-0003) 의 `agent_memory_kv` 접근이 모두 단일 table 가정. 분리 시 AR-M2 dual-write callsite 전수 수정 + AR-M3 backfill 분리 필요 → scope 폭증. MVP 불필요 복잡도.
  - **search_path global 설정**: `ALTER DATABASE agent_kb SET search_path = agent_runtime, public`. 폐기 사유 — agent_kb 에는 agent_runtime schema 외에 pgvector 관련 public 테이블 (fact_entries 등) 이 공존. global search_path 변경 시 KB 5 정본 테이블 접근 SQL 이 `agent_runtime` 안에서 해석되어 "table not found" 오류 유발 가능성.
- 후속 액션:
  - **AR-M2-a** (다음 cycle): `modules/runtime_backend.py` 신규 — Postgres write path. dual-write entry 추가.
  - **AR-M3**: backfill ETL 에 messages.meta_json JSON 유효성 pre-check 게이트 추가 (본 ADR 결정 사항).
  - **AR-M4 cutover 전**: `bin/agent-runtime-schema-compare.sh` 를 `bin/agent-runtime-cutover-readiness.sh` 의 게이트 항목으로 포함 (예정).

### ADR-0027 Addendum — AR-M4 read path cutover 결정 (2026-05-27)
- Status: accepted (TASK-0118, AR-M4 cycle, 2026-05-27)
- Context: AR-M4 (cutover read path) 에서 PG read path 활성화 설계를 결정한다. 6 runtime 테이블 write 는 AR-M2 dual-write 가 완료됨. M3 backfill 은 `bin/runtime-backfill.sh` 로 데이터 동기화. M4 에서 read 를 Postgres 로 전환하는 cutover 결정이 필요.
- Decision: **fail-soft read path cutover 패턴**:
  - **env-driven cutover**: `AGENT_RUNTIME_READ_BACKEND=postgres` (default: `"mysql"`) 로 read 전환. `.env` 한 줄 변경으로 활성화/비활성화 가능.
  - **fail-soft dispatcher**: `_read_runtime_pg(method_name, **kwargs)` — PG 연결 실패, method 미존재, exception 발생 시 모두 `None` 반환. caller 가 None 수신 시 MySQL fallback path 진행.
  - **read-only role 사용**: `_pg_connect_ro()` 우선. 미설정 시 `_pg_connect()` fallback. AR-M5 cleanup 전 read 전용 role 분리 권장 (ADR-0021 §3 2-layer 정책).
  - **JSONB 역직렬화 처리**: psycopg3 JSONB 컬럼은 Python 객체 자동 파싱. `core_messages.tool_calls` 는 PG read 후 `json.dumps()` 로 재직렬화하여 `_normalize_history_rows/_parse_saved_tool_calls` 균일 처리 (MySQL 경로와 동일 코드).
  - **범위**: memory.py (7 read 함수) + agent_core.py (3 함수: `_load_conversation_messages`, `list_all_conversations`, `get_conversation_messages`) + `runtime_backend.py` (`PgRuntimeBackend` 9 read method + dispatcher).
  - **web UI app.py 제외**: feature-0003 `_list_conversations` 는 MySQL `Accounts` 테이블과 cross-DB JOIN 의존 (PG 미이관 테이블). PG-only read 불가 → 별도 sub-cycle (AR-M4b 또는 Phase 3) 책임. 현재 cutover 활성화 시에도 web 경로는 MySQL fallback 유지.
- Consequences:
  - **cutover gate**: `bin/runtime-cutover-readiness.sh` 7 gate PASS 필수 (특히 Gate 2 row count 일치, Gate 4 unit test PASS).
  - **canary 기간**: `AGENT_RUNTIME_READ_BACKEND=postgres` 활성 후 최소 7일 agent loop + insight worker 정상 확인 후 AR-M5 진입 결정.
  - **web UI 제한**: app.py `_list_conversations` 는 MySQL 유지. Phase 3 (18 web\* 테이블 분리) 진입 시점에 전환.
- Alternatives 검토 후 폐기:
  - **read-after-write 보장 단일 connection**: PG write + read 를 같은 connection 트랜잭션 내 처리 — MySQL dual-write 구조와 근본적으로 충돌. AR-M5 cleanup 후 MySQL 제거 시점에서 단일 PG transaction 가능.
  - **web UI app.py 동시 전환**: cross-DB JOIN (AgentCoreConversations + Accounts) 을 Python 단에서 분리 조회 + merge 로 전환 — RBAC 로직, 검색, cursor pagination 전체 재구현 필요. scope 폭증, 별도 cycle 지정.

## ADR-0028
- Status: accepted (TASK-0119, AR-M5 cycle, 2026-05-27)
- Context: AR-M4 cutover read path 완료 후 MySQL `agent_memory` DB 의 agent_runtime 6 테이블을 안전하게 DROP 하는 시점 · 절차 · 실패 모드를 결정해야 한다. KB M5 (ADR-0025) 와 동일한 Stage A/B/C 패턴을 runtime 도메인에 적용.
- Decision: **Stage A/B/C 3단계 cleanup 정책**:
  - **Stage A (dual-write 활성 — AR-M2~AR-M4 기간)**: MySQL + PG 모두 write. MySQL read 유지. rollback = PG write 비활성화만.
  - **Stage B (read cutover 완료 — AR-M4 이후)**: MySQL write 는 dual-write 로 유지되나 read 는 PG 전용. 최소 **14일** 무회귀 monitoring 필수. MySQL 은 hot standby. 이 창에서 `bin/runtime-cutover-readiness.sh` 재실행 + agent loop / insight worker 지표 점검.
  - **Stage C (MySQL DROP — AR-M5)**: `bin/runtime-cleanup-mysql.sh --confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD` 로 mysqldump backup → 6 테이블 DROP. cutover-date 후 14일 미달 시 script 가 exit 2 로 차단. rollback = mysqldump restore (Stage C 진입 후 신규 write 는 PG only 이므로 partial restore).
  - **DROP 순서** (FK 의존 역순): AgentCoreMessages → AgentMemoryMessages → AgentMemorySteps → AgentMemorySummary → AgentMemoryKv → AgentCoreConversations (parent).
  - **사전 조건 gate** (script 강제): (1) `AGENT_RUNTIME_READ_BACKEND=postgres`, (2) `AGENT_RUNTIME_DUAL_WRITE≠1/true/yes`, (3) `--cutover-date` + 14-day window PASS, (4) TTY interactive double-confirm 또는 `RUNTIME_M5_RUN_FROM_HUMAN_SHELL=1`.
  - **backup**: mysqldump `--single-transaction --routines --triggers --hex-blob --default-character-set=utf8mb4`. gzip 압축 + sha256 sidecar. chmod 0600. `gunzip -t` + line count ≥ 10 + 6 테이블 CREATE TABLE 존재 확인.
  - **dual-write 코드 삭제**: `runtime_backend.py` 의 dual-write 경로 코드 삭제는 별 AR-M5-impl cycle 책임 — 본 ADR 의 DB 측 cleanup 이후 별도 PR.
  - **confirm string**: `I_UNDERSTAND_DATA_LOSS` (대문자 + underscore 정확).
- Consequences:
  - **web UI 제한**: feature-0003 app.py `_list_conversations` 는 MySQL 유지 (Accounts cross-DB JOIN). Phase 3 이관 시점에 전환.
  - **AR-M5-impl cycle**: cleanup 완료 후 `runtime_backend.py` dual-write 코드 + `AGENT_RUNTIME_DUAL_WRITE` env 참조 제거.
  - **agent_memory DB 존재**: runtime 6 테이블 DROP 후에도 다른 테이블 (KB 정본 포함) 이 남아있으면 DB 자체는 유지. 완전 DB DROP 은 Phase 3 영역.
- Alternatives 검토 후 폐기:
  - **7-day window**: ADR-0025 의 KB M5 와 동일한 14-day window 적용. 7일은 weekend + 평일 배포 주기를 모두 포함하지 못해 폐기.
  - **즉시 DROP (cutover 당일)**: Stage B 없이 바로 Stage C 진입 — rollback 창 없음, 고객 영향 위험. 폐기.
  - **dual-write 코드 동시 삭제**: DB DROP + 코드 삭제를 같은 PR 에 포함 — diff 복잡도 폭증, outside-voice 2회 병렬 요구. 분리.

### ADR-0028 Addendum — Phase 2 agent* MySQL 완전 제거 (2026-05-27)
- Status: **Phase 2 agent* MySQL 완전 제거 완료 (2026-05-27)**
- 추가 발견: AR-M5 6 테이블 DROP 직후 insight-worker가 memory.py::ensure_memory_schema()와 agent_core.py::_ensure_memory_tables() 를 PG guard 없이 호출하여 10개 테이블 재생성. DUAL_WRITE=0이어도 MySQL이 primary write 경로로 동작 (PG mirror만 bypass) → orphaned data (14:57 run: 25 core_msgs + 15 steps + 9 kv) 발생.
- 대응: memory.py 5함수 + agent_core.py 4함수에 `AGENT_RUNTIME_READ_BACKEND=postgres` guard 추가 → PG direct write + MySQL bypass (commit 0745862). orphaned data PG 마이그레이션 후 10 테이블 DROP.
- 최종 백업: artifacts/shared/agent-memory-final-backup-2026-05-27T061637Z/ (sha256: 104eea69)
- MySQL ABSENT: agent_memory DB 내 agent* 테이블 COUNT=0. web* 18 테이블만 잔존 (Phase 3 대상).
- 다음: AR-M5-impl cycle (runtime_backend.py dual-write 코드 제거) + Phase 3 (web* 테이블 이관)

### ADR-0028 Addendum — AR-M5-impl + P1-T2 dual-write code 완전 제거 (2026-05-27)
- Status: **AR-M5-impl + P1-T2 완료 (2026-05-27)**
- **runtime 측 (AR-M5-impl)**:
  - `runtime_backend.py`: `RuntimeBackend` ABC, `MysqlRuntimeBackend`, `_dual_write_runtime_mirror()`, `AGENT_RUNTIME_DUAL_WRITE`, `AGENT_RUNTIME_DUAL_WRITE_START_TS`, `AGENT_RUNTIME_AUDIT_ENABLED`, `_rt_pg_op_local`, `_log_runtime_write_audit()`, `_build_runtime_audit_resource_id()`, audit 상수 제거. `PgRuntimeBackend` → standalone class; `_execute_upsert_with_branch` 제거 → 직접 `with conn.cursor()`.
  - `memory.py`: `ensure_memory_schema()` MySQL DDL 전체 → `pass`. `save_memory_message/kv/summary/step` PG guard+return 패턴 → 무조건 PG 직접 쓰기 (MySQL else-branch + `_dual_write_runtime_mirror` 호출 제거).
  - `agent_core.py`: `_ensure_memory_tables()` MySQL DDL → `pass`. `_save_message / _ensure_conversation / _update_conversation_topic` MySQL else-branch 제거.
- **KB 측 (P1-T2)**:
  - `kb_backend.py`: `_DualWriteMirror` class (lines 1183-1310) + `_dual_write_kb` singleton + `__all__` 항목 제거.
  - `knowledge.py`: `_dual_write_kb.prune_fact_entries_keep_top()` + `_dual_write_kb.upsert_fact_entry()` 2 call site 제거.
  - `utils.py`: `_dual_write_kb.upsert_text()` + `_dual_write_kb.upsert_rag_document()` + `_dual_write_kb.upsert_rag_object()` 3 call site 제거.
  - `config.py`: `AGENT_KB_DUAL_WRITE` 변수 제거.
  - `.env`: `AGENT_KB_DUAL_WRITE=0`, `KB_DUAL_WRITE_START_TS`, `AGENT_RUNTIME_DUAL_WRITE=0`, `AGENT_RUNTIME_AUDIT_ENABLED=0` 4 항목 제거.
- 코드 순감: −1,630 lines (7 파일). commit 6621ef3.
- 현 상태: agent runtime + KB 모두 Postgres 단독 write/read. MySQL `agent_memory` 에 `web*` 18 테이블만 잔존. dual-write 인프라 코드 없음.

## ADR-0029
- Status: accepted (feature-0008-windows-browser-testing, REQ-20260604, 2026-06-04)
- Context: AI 작업자의 웹/UI 테스트가 CLI(curl)·WSL 내부 headless 브라우저(feature-0004 service, gstack /browse)에 머물러, 실제 사용자가 보는 Windows 브라우저 화면과 자주 괴리가 발생했다 (렌더링·상호작용 차이). 사용자가 "웹브라우저 테스트는 cli·wsl 제외, windows 환경에서, AI 자동 구동 중심" 으로 워크플로 개선을 요청. 신규 Playbook(PB-0008) 추가는 AGENTS.md §4.1 상 본 DECISIONS.md ADR 기록 대상.
- Decision: **실제 Windows 브라우저를 AI 가 CDP 자동 구동하는 검증 워크플로 도입.**
  - **드라이버** `bin/win-browser.py`: Playwright `connect_over_cdp` 로 Windows Chrome/Edge attach. doctor/launch/down + goto/click/type/eval/text/screenshot + 시나리오 일괄 `run`. 브리지 모드(mirrored localhost / NAT portproxy relay) 자동 감지.
  - **브리지**: WSL2 에서 Chrome CDP 가 127.0.0.1 에만 바인딩되는 제약을 (A) vEthernet 한정 portproxy relay(`bin/win-browser-setup.ps1`, 관리자 1회) 또는 (B) mirrored networking 으로 해소. 가이드 `bin/WIN-BROWSER-SETUP.md`.
  - **환경 분류**: 각 feature `docs/TEST.md` §3 `Environment` 를 `CLI` / `WSL-headless` / `Windows-browser` 로 구분. **웹/UI 화면 검증은 `Windows-browser` 만 인정** (CLI·WSL-headless 는 서버 계약 검증용).
  - **완료 게이트**: AGENTS.md §15.4.1 (웹/UI 변경 → Windows-browser 검증 필수) + §10.5 조건부 규칙 row + §16.1/§16.2 체크리스트 + `bin/verify-completion.sh` check #13 (WARN-only v1, web 변경 시 Windows-browser run 누락 경고). 절차 = **PB-0008**.
  - **enforcement staged**: check #13 v1 은 WARN-only (PR block 아님), 후속 cycle MUST 격상 — wiki check #12 와 동일 staged rollout.
- Consequences:
  - 1회 브리지 setup(관리자 portproxy 또는 mirrored + `pip install playwright`)이 환경당 필요. doctor 가 게이팅.
  - **보안**: CDP 는 무인증 원격제어 채널 → setup.ps1 이 LAN 노출을 차단(vEthernet 한정 + 방화벽 Private/서브넷). Chrome `--remote-debugging-address=0.0.0.0` 미사용, `--remote-allow-origins` 구체 origin, per-user 격리 프로필. (§18.8 security 패널 F1/F2/F4/F5 반영.)
  - gstack `/browse`·feature-0004 headless 는 폐기 아닌 보조(빠른 탐색)로 공존.
- Alternatives 검토 후 폐기:
  - **사람 확인 게이트(human-in-the-loop)**: AI 가 브라우저만 열고 사람이 확인. 사용자가 "AI 자동 구동 중심" 명시 → 폐기.
  - **WSLg headful chromium**: 표시는 되나 Linux chromium 이라 실제 Windows Chrome 렌더링과 다름 ("wsl 내부 아닌" 요구 위배) → 폐기.
  - **`*` allow-origins + 0.0.0.0 relay**: 가장 단순하나 무인증 CDP 를 LAN 전체 노출(CRITICAL) → 보안 패널 must-fix 로 폐기.

## ADR-0030

- Status: accepted (TASK-0228, 2026-06-11, **Major §12.3 보안 수준 저하 — 사용자 명시 승인**)
- Context: datasource 생성·연결테스트는 `app._ssrf_check_host` 가 입력 host 를 DNS 해석한 뒤
  사설망(RFC1918)·링크로컬·loopback·reserved·multicast·클라우드 메타데이터 IP 를 차단한다(SSRF/DNS
  rebinding 방어, TASK-0205/0214). 사내 운영 환경은 **대부분 사설망 IP(예: `10.200.50.80`)로 DB
  연결정보를 구성**하므로, 정당한 사내 datasource 생성이 "호스트 차단(SSRF): 사설/링크로컬 IP
  차단(allowlist 필요)" 으로 막힌다. 매 host 를 `AGENT_DATASOURCE_HOST_ALLOWLIST` 에 등재하는 운영
  부담을 줄이고자, 사용자가 **사설망 SSRF 경계 자체를 의도적으로 비활성화**하기로 결정.
- Decision: **사설/링크로컬 SSRF 경계를 env 토글 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED` 뒤로 분기.**
  - **방어 구성은 코드에 그대로 보존**(`_ssrf_check_host` + allowlist 로직 삭제하지 않음). 코드 기본값
    `=1`(활성, secure-by-default) — 미설정/알 수 없는 값이면 차단 동작 유지. 운영 `.env.secret` 에서
    `=0` 으로만 비활성화한다(`0`/`false`/`no`/`off` 인식). 이 ADR 이 그 **복원 태그**다.
  - **현재 상태**: 운영 `.env.secret` 에 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 설정 → 사내 사설망
    datasource 생성 허용.
  - **불변식(토글과 무관하게 항상 유지)**: ① 클라우드 메타데이터 IP(`169.254.169.254`,
    `100.100.100.200`, IPv6-mapped) 하드차단 ② DNS rebinding pin(검증된 IP 로 고정 연결) ③ 빈 host /
    해석 실패 거부. 토글이 끄는 것은 사설/링크로컬/reserved/multicast 차단뿐 — 사내 DB 운영과 무관한
    경계는 끄지 않아 잔존 위험을 최소화.
  - **UI 정합**: `GET /api/admin/datasources` 응답에 `ssrf_private_guard_enabled` 추가, admin 콘솔의
    datasource 안내 문구가 토글 OFF 시 "사설망 IP 허용(메타데이터는 여전히 차단)" 으로 분기.
- 복원 절차 (SSRF 사설 경계 재활성화 요청 시):
  1. 운영 `repo/.env.secret` 의 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` → `=1` (또는 줄 제거 = 기본 활성).
  2. (선택) 정당한 사내 사설 host 는 `AGENT_DATASOURCE_HOST_ALLOWLIST` 에 콤마구분 host/CIDR 로 등재.
  3. `sudo docker compose up -d --build web` (또는 `--no-build` 재시작)로 web 컨테이너 재기동.
  4. 코드 변경 불필요 — 토글·allowlist 메커니즘이 이미 상주.
- Consequences:
  - 토글 OFF 동안 admin(`console.manage`) 이 임의 사설망 IP 를 datasource host 로 등록 가능 → 내부망
    SSRF 표면 증가. 단 datasource 연결은 `console.manage` 보유 admin 만 가능하고, 연결 자격증명은
    envelope 암호화 저장되며, 메타데이터 IP 는 여전히 하드차단된다.
  - 신뢰 가능한 사내 네트워크 전제 — 외부 노출/멀티테넌트 환경에서는 재활성화 필요.
- Alternatives 검토 후 폐기:
  - **단일 IP allowlist 등재**(`AGENT_DATASOURCE_HOST_ALLOWLIST=10.200.50.80`): 최소권한이나 사내 host
    추가마다 운영자 개입 필요 → 사내 사설망 전면 운영 맥락에서 반복 마찰 → 사용자가 경계 비활성화 선택.
  - **CIDR allowlist**(`10.0.0.0/8` 등): 대역 전체 허용이라 토글 OFF 와 노출 표면 유사하나, 경계 ON
    상태로 위장돼 정책 의도가 코드에 드러나지 않음 → 명시적 토글이 감사·복원에 유리.
  - **SSRF 검증 코드 삭제**: 복원 불가 → 사용자 "태그로 기억하고 이후 복원" 요구 위배 → 폐기.

## ADR-0031

- Status: accepted (initiative: ssot-consolidation, 2026-06-23, **META 층위 §18.4 — 사용자 주도**)
- Context: 거버넌스(메타)·제품 두 레이어가 14개월 누적되며 정본이 다중화·비대화·stale 화되어,
  AI 세션이 "무엇이 진실인지(정본)" 판정에 실패 → 작업이 정립되지 못하고 요청을 제대로 수행하지 못하는
  증상이 보고됨. 진단(증거): `docs/improvements/ssot-consolidation/RESEARCH.md`. 적대 리뷰(42 에이전트,
  확정 16/기각 19, blocker 1)로 강화한 실행 계획: 동 디렉토리 `ROADMAP.md`.
  핵심 위반: 의사결정 정본 3곳(DECISIONS+AGENTS §18+wiki), 현황 3곳(unit TASK+STATUS 290KB+wiki),
  아키텍처 3곳, 운영정책 2곳; STATUS.md 290KB·AGENTS.md 189KB 비대화; GOAL.md(archived) 잔존이 실제
  중복구현 사고 유발; wiki 98% mirror 가 자동 동기화 없이 drift; tracked secret 백업 3건이 origin/main+
  원격 브랜치+머지 PR 에 노출(BLOCKER).
- Decision: **Single Source of Truth 계약 4조를 프로젝트 불변 규칙으로 채택한다.**
  1. **한 도메인 = 한 정본.** `source_of_truth: true` 는 도메인당 정확히 1개 문서. 도메인→정본 지도는
     `docs/DOC_REGISTRY.md`(본 ADR 의 운영 정본)가 단일 답.
  2. **참조는 복제하지 않는다.** `source_of_truth: false` 문서(mirror/요약)는 `mirrors:` 또는 `sources:`
     frontmatter 로 정본 경로를 선언하고 정본 내용을 재서술하지 않는다.
  3. **끝난 것은 루트에서 사라진다.** `status|lifecycle: archived` 자산은 `docs/_archive/` 로 격리한다.
  4. **drift 는 기계가 강제한다.** `bin/ssot-lint.sh` 가 (1)~(3) + 'tracked `.env*.bak*`/`*.bak-task*` 0건'
     (노출 자산 가드)을 검사한다. 현재 WARN-only 골격, P1+ 에서 도메인 유일성 정밀 검사로 확장.
  - 적용 순서: Phase 0(본 ADR + DOC_REGISTRY + lint 골격) → P1 문서정본 → P2 worktree 흡수 →
    P3 secret(rotation 1순위, Critical) → P4 wiki 참조-only → P5 코드 재배치+검증.
  - 이 initiative 는 META 층위(§18.4)이므로 각 Phase 는 ai/* worktree + PR + verify-completion check #9
    (REVIEW.md accepted entry)를 거치며, Critical(P3)·Major(P5)는 §12 사람 최종 승인을 받는다.
- Consequences:
  - 신규 AI 세션이 "정본이 어디?" 를 `docs/DOC_REGISTRY.md` 1곳으로 해소 → 컨텍스트 로드 실패·중복작업 감소.
  - 정책/현황을 두 곳에 쓰던 관례 종료(참조는 포인터만) → 갱신 시 drift 가 lint 에서 차단.
  - STATUS.md 는 정본에서 인덱스로 강등(P1) — 상세 현황 정본은 `unit/<feature>/docs/{TASK,REPORT}`.
- Alternatives 검토 후 폐기:
  - **현상 유지**: drift·비대화 누적이 작업 미정립의 직접 원인 → 폐기.
  - **wiki 완전 폐기**: Log/hot/concepts 고유 가치 손실 → 참조-only + 자동 동기화로 대체.
  - **secret rm-only**: 이미 push 된 노출을 제거 못 함 → rotation 1순위로 격상(P3).

### ADR-0031 Addendum — archive 위치 = `docs/archive/` (2026-06-24, Phase 1a)

- §3 의 archive 격리 위치를 `docs/_archive/` → **`docs/archive/`** 로 교정한다.
- 사유: `.gitignore:27` 의 `_archive/` 패턴이 모든 `_archive` 디렉토리를 무시한다(템플릿의 로컬 임시
  보관 관례). SSOT 의 archive 는 **git 추적 보존**(이력 유지)이 목적이므로 gitignore 되는 `_archive/` 는
  부적합. `docs/archive/`(추적됨)로 확정. `bin/ssot-lint.sh` 의 archived 검사도 `*/archive/*` 로 정합.

## ADR-20260625T023049-spec-anchor-timestamp-id

> 본 ADR 자체가 새 형식의 첫 적용 예시다 (기존 순번 ADR 은 소급 재번호 없이 보존).
> **registry 주의**: AGENTS.md §6/§13.1 이 식별자 거버넌스 출처로 인용해 온 "ADR-0024"(순번 유지)·
> "ADR-0025"(timestamp+branch) 번호는 **docs/DECISIONS.md 의 동명 ADR 과 불일치**한다 — 본 레지스트리의
> ADR-0024 는 "Postgres database 격리", ADR-0025 는 두 번 정의(M5 cleanup·pgvector attachment RAG)로
> 식별자 정책과 무관하다. 따라서 본 ADR 은 그 번호를 재인용하지 않고 **정책 위치(AGENTS.md §6·§13.1)와
> 버전(v3.32.0 timestamp+branch 도입)** 으로 직접 참조한다. 이 순번 ADR 의 중복·오참조 자체가 본 전환의
> 동기를 보강한다(순번은 병렬·이력에서 충돌·혼선을 만든다).

- Status: accepted (META §18.4 — 사용자 주도, 2026-06-25). spec 앵커 `REQ`/`AC`/`ADR`/`TEST` 식별자
  형식을 timestamp+slug 로 전환.
- Context: spec 앵커(`REQ-`/`AC-`/`ADR-`/`TEST-`)가 AGENTS.md §6/§13.1 에서 "순번 spec 앵커"로 분류되어
  순번 `*-XXXX` + 감지-후-재번호 규약을 따랐다. 그러나 `feature-0003` 처럼 여러 cycle 이 같은 날 병렬로
  머지되는 고병렬 환경에서, 각 세션이 다음 순번을 독립 할당 → `origin/main` 머지 시 **동일 번호 충돌**이
  반복 관측됨. 실측 사례(2026-06-25): `gc-member-kick-ban` cycle 의 rebase 중 `auto-product-prompt`
  (AC-0623/0624) → `admin-metadata-relocate`(AC-0625) 와 연쇄 충돌하여 AC 를 2회(0625→0626~0629)
  재번호해야 했다. AC 가 가장 빈번했으나 REQ/ADR/TEST 도 같은 순번 충돌 표면을 공유한다(본 레지스트리의
  ADR-0025 중복 정의가 그 산 증거다). 이는 v3.32.0 timestamp+branch 전환이 `TASK-`/`CHG-`/`REV-`/`LRN-` 에
  대해 이미 해소한 것과 동일한 마찰이며, spec 앵커만 순번으로 남아 있던 잔여 표면이었다(사용자 후속 요청:
  "REQ, ADR, TEST 또한 같은 형식").
- Decision: **신규 spec 앵커는 timestamp+slug 형식 `<PREFIX>-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` 로 할당한다**
  (정본 AGENTS.md §6·§13.1):
  - `REQ-<YYYYMMDDTHHMMSS>-<slug>` (cycle 당 1개라 날짜형 `REQ-<YYYYMMDD>-<slug>` 도 허용).
  - `AC-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` — 부모 REQ 의 **slug 를 공유**하고 cycle 의 초 timestamp 를
    붙인다. REQ 당 **AC 가 2개 이상이면 `-<n>`(1-based) 필수, 단일이면 생략 가능**(또는 `-1`). 예:
    `REQ-20260625-gc-member-kick-ban` → `AC-20260625T020410-gc-member-kick-ban-1`,`-2`…(REQ 가 날짜형이어도
    AC 는 cycle 의 초 timestamp `T020410` 을 사용).
  - `ADR-<YYYYMMDDTHHMMSS>-<slug>` (본 ADR 이 첫 예시).
  - `TEST-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (다수면 `-<n>` 필수, 단일 생략 가능).
  cycle 별 timestamp+slug 자연 분기가 병렬 점유-경합을 제거해 감지-후-재번호가 불필요해진다. 본 결정은
  **AGENTS.md §6·§13.1 의 기존 "spec 앵커 순번 유지" 정책을 갱신**하며, v3.32.0 의 timestamp+branch
  컨벤션(TASK/CHG/REV/LRN)을 spec 앵커로 확장한다(상단 registry 주의 참조 — 특정 순번 ADR 번호 비인용).
- Scope/비대상: `feature-NNNN`/`META-NNNN` (수명 길고 추적 참조 많은 폴더/worktree/branch 식별자) 은
  본 ADR 대상이 아니다 — 안정 순번 유지(이전 순번 정책 잔존). 이들만 §13.1 의 감지-후-재번호 대상으로 남는다.
  **기존 순번 `REQ-XXXX`/`AC-NNNN`/`ADR-XXXX`/`TEST-XXXX` 는 소급 재번호하지 않는다** — additive 전환으로
  과거 참조(다른 문서의 인용)는 보존되고 신규 항목부터 새 형식을 적용한다. CHG-/REV-/LRN-/TASK- 는 이미
  timestamp(ADR-0025)라 무영향.
- Consequences:
  - 고병렬 cycle 머지에서 spec 앵커 충돌·재번호 마찰 제거(관찰된 주 마찰 지점 해소).
  - `FUNCTION.md` 의 AC 가 부모 REQ 와 timestamp+slug 로 시각적으로 묶여 추적성 향상.
  - 한 문서 안에 순번(과거)과 timestamp(신규) 항목이 혼재 — 의도된 additive 상태(형식 자체로 구분).
  - ADR 가 timestamp+slug 형식이 되어 짧은 `ADR-XXXX` 토큰보다 길어진다(가독성 trade-off 수용 — 충돌
    제거 우선, 사용자 결정). 기존 ADR 번호 참조는 그대로 유효.
  - 정책 명시 위치: AGENTS.md §6(식별자 표)·§6 prose(spec 앵커 단락)·§13.1(감지-후-재번호 제외) +
    docs/CONVENTIONS.md(식별자 목록) + unit/_template/docs/{FUNCTION.md §11, TEST.md §2}(템플릿 주석) +
    wiki/Glossary/_Index.md(용어집 행) + playbooks/PB-0006-template-migration.md(ADR 작성 절차).

## ADR-20260629T101500-glossary-conversation-autoregistration
- Status: accepted
- Date: 2026-06-29
- Context: 「관리 콘솔 > 메타데이터 > 용어사전」(kb_glossary, ITEM-10) 은 그동안 **수동 등록(권한
  kb.ingest.manual)만** 허용했다 — 등록 내용이 질문/스키마 매칭 시 답변 프롬프트에 주입돼 검색·답변
  정확도에 직접 영향(KB poisoning 면)하므로 "자동학습 없음" 이 의도된 거버넌스였다(app.py 권한 설명·
  sample_feedback.py 헤더에 명시). 사용자 요청(/_template:entry, 2026-06-29): ① 용어사전이 **사용자
  대화로부터 assistant 판단 하에 자율 등록**되도록, ② **역할(role)별 사용 용어가 겹치지 않는 구조**,
  ③ **유사한 의미가 있으면 참조 가능한 구조**. ①은 기존 "자동학습 없음" 거버넌스와 정면으로 맞닿는다.
- Decision (사용자 AskUserQuestion, 2026-06-29):
  - **① 등록 자율성 = 하이브리드 자동승급**. 대화 답변 직후 LLM(`llm_glossary_suggest`)이 용어 후보를
    추론(`agent_core._glossary_autopropose` hook). `confidence ≥ AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD`
    (기본 0.85)이면 용어사전에 **자동 등록(source='auto')** 하되, 모든 자동 등록분을 `glossary_feedback`
    (status='auto_promoted')에 **감사 추적**하여 검수자가 언제든 **되돌리기**(reject 시 source='auto' 행
    회수) 가능. 임계 미만은 **검토 큐(status='pending')** 에 적재 → 권한 `kb.glossary.curate` 보유자가
    promote/reject. 라이브 반영 게이트(검수·되돌리기)를 유지해 기존 poisoning 거버넌스를 깨지 않으면서
    "자율"을 *제안·고신뢰 자동등록의 자율성* 으로 충족(기존 sample_feedback 플라이휠 패턴 재사용).
  - **② 역할 분리 = role_key 차원**. `kb_glossary` 에 `role_key`(varchar, WebRoles.RoleKey 비정규화 —
    glossary=PG/WebRoles=MySQL cross-DB 라 FK 불가) 추가, UNIQUE(scope_key, term) → UNIQUE(scope_key,
    role_key, term) 로 재정의 → **같은 용어를 역할별 독립 namespace 로 보유(겹침 방지)**. `role_key='*'`
    = 공용(모든 역할). 읽기(load_glossary_enum_context)는 role_key 지정 시 [그 역할, '*'] 만 주입(다른
    역할 전용 용어 미노출). **자동 제안된 용어의 기본 귀속 = 공용('*')**(사용자 결정) — 역할 특수 시에만
    관리자가 역할 namespace 로 이동.
  - **③ 유사어 참조 = glossary_relations**. (from_id, to_id, relation_type ∈ {synonym, similar,
    see_also}) 자기참조 테이블 — **역할 경계 횡단 허용**. 역할별 비중복이라도 유사 의미 용어를 교차 참조.
- Consequences:
  - 신규 마이그레이션 0023: kb_glossary.role_key/source ADD + UNIQUE 재정의, glossary_feedback(검토 큐)·
    glossary_relations(참조) CREATE + GRANT(agent_kb_rw/ro). 기존 행은 role_key='*'·source='manual' backfill
    → 동작 불변. cross-cut: 코어/마이그/agent hook = feature-0002, web 엔드포인트/관리 UI = feature-0003.
  - 신규 권한 `kb.glossary.curate`(group=kb, admin seed 자동 보유) — 검토 큐 promote/reject 게이트.
  - 신규 config: AGENT_GLOSSARY_AUTOPROPOSE(기본 on)·AGENT_GLOSSARY_SUGGEST_MODEL·
    AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD(0.85)·AGENT_GLOSSARY_SUGGEST_MAX(5). 비용/오염 우려 시 플래그로 차단.
  - hook 은 best-effort(soft-fail) — LLM/PG 실패가 ask 경로를 절대 막지 않는다. 거부된 후보는 재제안돼도
    되살아나지 않는다(ON CONFLICT WHERE status='pending', curator 결정 존중).
  - trade-off: 매 답변 턴마다 경량 LLM 추론 1회 추가(요약 티어 모델·cap 5). 사용자 응답은 이미 전송된
    뒤 실행되어 사용자 체감 지연 없음(워커 시간만 소폭 증가). 후속(미구현): insight-worker 비동기 이관 옵션.

## ADR-20260710T231146-parallel-id-hygiene

- Status: 승인 (2026-07-10 — 제안·승인 근거: `docs/improvements/parallel-work-structure/ROADMAP.md`
  §6.1 사전 승인(2026-07-10 사용자 지시, PLAN-APPROVED 상당) · ITEM-01. 적대 리뷰
  REV-20260710T180820-improve-parallel-structure 2-round 가 항목 명세를 사전 검증.)
- Context: 대량 병렬 생성 식별자(`TASK-`/`REV-`/`CHG-`/`LRN-`)와 spec 앵커(`REQ-`/`AC-`/`ADR-`/
  `TEST-`)는 timestamp 전환(§13.1 v3.32.0 / §6 v3.34.x)으로 순번 점유-경합이 제거됐으나, 3곳이
  규약 밖에 잔존해 병렬 세션 간 충돌·재번호가 계속 실측됐다 (RESEARCH F-002): ① TASK.md 등
  사이클-append 문서의 최상위 섹션 헤더 `## N.` (`## 33.`/`## 56.` 중복, 재번호 정정 커밋
  e79688f6·0f692942), ② 신규 ADR 의 순번 fallback (`ADR-XXXX`), ③ 아카이브 파일 순번
  (`_archive/<DOC>-archive-NNNN.md` — 날짜 단위면 같은 날 병렬 아카이빙이 재충돌).
- Decision (기존 timestamp 규약의 자연 확장 — 아키텍처·제약·보안 무영향):
  1. **§13.1**: 사이클-append 문서의 신규 최상위 섹션 헤더는 `## <YYYYMMDDTHHMM>-<slug>` 형식.
     순번 `## N.` 신규 사용 금지, 기존 번호 헤더는 불변.
  2. **§5.5**: 아카이브 파일명을 `_archive/<DOC>-archive-<YYYYMMDDTHHMMSS>.md` (초 단위) 로 개정.
     기존 아카이브 파일명 불변.
  3. **§6**: 신규 ADR 은 timestamp-slug 형식만 유효 — 순번 fallback 폐지 (기존 순번 ADR 유효).
- Consequences:
  - 소급 재번호는 하지 않는다 (참조 파손 방지 — 신규 항목부터 적용). 기존 `## N.` 헤더·순번
    ADR·순번 아카이브 파일은 전부 유효하며 `§N` 상호 참조도 그대로 성립한다.
  - AGENTS.md 는 template 계보(v3.37.2) 문서 — 본 개정은 소비자 선행 개정으로, template base
    전파(inbox) 계획은 META-0023 REVIEW 엔트리(meta/REVIEW.md) 에 기록한다 (§13.2.3-A 선례).
  - 후행 관측 (done 판정식 아님): 이후 사이클들의 TASK.md 신규 섹션이 timestamp 헤더로 기록되는지
    — parallel-work-structure 로드맵 후속 항목들이 검증 표본.
## ADR-20260711T042631-append-doc-merge-driver

- Status: 승인 (2026-07-11 — 제안·승인 근거: `docs/improvements/parallel-work-structure/ROADMAP.md`
  §6.1 사전 승인 · ITEM-03. 적대 리뷰 REV-20260710T180820 2-round 가 항목 명세를 사전 검증 —
  특히 B-2 지적(§13.1 v3.35.1 의 driver 허용은 단일-라인 stamp 한정 → 본 확대는 정식 개정 필요)의 이행.)
- Context: append-only 문서(unit MODIFY/REVIEW·LEARNINGS·RELEASE_NOTES)의 말미 블록 append 가
  병렬 브랜치 간 반복 수동 해소되고(7c653ea8), conflict marker 잔존 커밋(a77180ca)까지 발생
  (RESEARCH F-004·F-009). fragment 전환(ITEM-06/META-0026)이 근본 해법이나 전 문서 전환 전
  과도기에 비용 ≈ 0 git 장치로 해소를 자동화한다.
- Decision:
  1. **§13.1 개정**: path-scoped custom merge driver 허용 범위를 "단일-라인 monotonic stamp"
     에서 "append-only 문서의 말미 블록 병합"까지 확대. 조건 — 3종 문서 한정(.gitattributes
     path-scope; LEARNINGS.md 는 섹션-내부 삽입 구조라 제외)·말미-append 케이스만 자동 병존
     (`## ` 블록 단위, ours→theirs 연접·dedup — timestamp 재정렬은 무 ts 블록 재배열 리스크로
     비채택)·그 외 전부 `git merge-file` 위임(default 3-way 동일 — 겹치지 않으면 clean, 충돌은
     표준 marker; 자동 오병합 금지)·전체 파일 merge=union 금지 유지.
  2. **rerere**: 작업자 계정 git 전역 rerere.enabled+autoUpdate 활성화(`bin/setup-git-parallel.sh`,
     멱등). 실측 한계 명기: custom driver 폴백 충돌엔 rerere 가 개입하지 않음(rr-cache 미기록)
     — driver 3종 밖 일반 파일의 반복 충돌이 rerere 커버리지 (단 merge-file 위임 후엔 driver 경로 충돌에도 preimage 기록 실측 — 보수 서술).
  3. **conflict-marker 잔존 게이트**: verify-completion check #14(무조건 실행) — staged/HEAD
     추가 라인의 `<<<<<<< / >>>>>>>` 적발(a77180ca 재발 방지). `=======` 단독은 오탐 잦아 제외.
  4. `.gitattributes` 는 repo 루트 신규 파일 — verify-completion META-경로 인식에 추가.
- Consequences: driver 등록은 clone-로컬 — 세션/클론 시작 시 `bash bin/setup-git-parallel.sh`
  1회(멱등). fragment 전환 완료 문서는 driver 대상에서 제거(브리지 수명). template base 전파
  (inbox) 계획은 META-0024 REVIEW 엔트리에 기록.
## ADR-20260711T053000-test-runs-fragment

- Status: 승인 (2026-07-10 ROADMAP parallel-work-structure §6.1 사전 승인 · ITEM-06.
  **기록 시점 주의**: 본 개정은 PR #683(2026-07-11)으로 이미 반영·머지됐고, §0 "AGENTS.md
  개정 공통 규약"(i) 의 DECISIONS 제안 기록이 그 cycle 에서 누락돼 **본 엔트리로 사후
  완결**한다 — 투명 기록.)
- Context: TEST.md §3 Run 기록 append 가 병렬 세션 최다 충돌 지점(30일 229회 변경, F-004).
- Decision: **§5.3 개정** — 신규 Run 기록은 `unit/<feature>/docs/test-runs.d/<TASK-또는-REV-id>.md`
  항목당 1파일(frontmatter run_at(ISO8601)·session·scope·verdict). verify check #13 은
  TEST.md 추가 라인 **또는** fragment 인정(OR 하위호환 — 일괄 강제 없음, 소급 이동 없음).
  90일 컴팩션은 doc_sync 소관(§5.5 아카이브 + TEST.md 상단 참조 링크).
- Consequences: 병렬 Run 기록 원천 무충돌(towncrier 계열). §18.8 패널 SHIP-WITH-FIXES
  (우회면 없음·honor 모델 등가). template base 전파 후보.

## ADR-20260711T053001-merge-mutex-freshness-gate

- Status: 승인 (2026-07-10 ROADMAP parallel-work-structure §6.1 사전 승인 · ITEM-07)
- Context: 일 18.6 PR 페이스에서 머지 직렬화 장치 부재 — ① 동시 finalize push race 가
  "사용자 수동 직렬화"에 위임(§13.2.5 구판) ② 낡은 base 로 통과한 테스트로 머지되는
  semantic drift 상존(F-005) ③ 실측: mergeStateStatus=UNSTABLE(CI 진행 중) 상태 머지
  가능(PR #682 — 사후 SUCCESS 였으나 적색 머지 가능성). GitHub merge queue 는 Free
  private 불가(W-003) — 전 작업자 동일 호스트라 flock 등가 구현.
- Decision (**§13.2.5 개정** + cycle-finalize/verify 구현):
  1. cycle-finalize 머지 구간(PR 검증→merge→main pull)을
     `flock <git-common-dir>/.merge.lock` critical section 으로 직렬화(timeout 15분
     명시 실패 — 무한 대기 금지, EXIT trap 으로 전 die 경로 락 해제 확정).
  2. 락 안 신선도 hard gate: behind ≥ 20 이면 자동 update-branch + CI 재확인 강제
     (gh 2.57+ `gh pr update-branch`, 구버전은 `gh api PUT pulls/N/update-branch` 폴백
     — 라이브 실증(PR #684)이 이 호스트 gh 2.45 unknown-command 실결함을 적발해 추가,
     폴백 유효성은 probe2 PR #685 로 tip 갱신·behind→0 실증).
  3. mergeStateStatus=CLEAN 재폴링 후에만 머지(UNSTABLE 대기·BEHIND→update·MERGED
     외부 머지 합류·HAS_HOOKS 진행·BLOCKED/DIRTY §16.3 자동 중단·600s 명시 timeout).
  4. verify-completion: behind ≥ 10 비차단 WARN(조기 신호, 로컬 ref — fetch 무).
- Consequences: "최신 base 합산 green 만 main"(W-002) 불변식을 단일 머지 경로에 이식.
  한계: host-local — 원격/CI 발 머지 미보호(문서화). env: MERGE_LOCK_TIMEOUT_SEC·
  MERGE_BEHIND_GATE·MERGE_CLEAN_TIMEOUT_SEC. template base 전파 후보.
## ADR-20260711T051835-wip-hotspot-policy

- Status: 승인 (2026-07-10 ROADMAP parallel-work-structure §6.1 사전 승인 · ITEM-12 —
  당초 defer(C-13)였으나 웹 리서치 정량 근거(Uber 16건→40%·DORA 활성 ≤3·커뮤니티 세션
  상한 2~4, W-006/W-008)로 채택 승격된 항목)
- Context: 충돌 확률의 근본 변수 = 동시 진행량 × 브랜치 수명. feature-0016 graphux 2~10+
  병렬은 임계 초과 상태였고, 인프라(mutex·fragment·driver)는 완화책일 뿐.
- Decision (**§13.2.5-A 신설** + cycle-init soft 게이트 + REGISTRY 부트스트랩):
  (a) 동일 핫스팟 in-flight ai/* ≤ 2 권고 — cycle-init `--hot-paths` 가 REGISTRY 활성
  세션과 대조, 겹침 ≥ 2 경고(**차단 아님** — 처리량 보존) (b) REGISTRY(§13.2.8 정본 경로
  `<project_root>/worktrees/REGISTRY.md`, repo 밖 운영 파일) 활성 entry 에 `hot_paths:`
  필드 — cycle-init 자동 기록·세션당 자기 블록만 수정 (c) 순차 머지 원칙 — `merge_order:`
  사전 선언, 1브랜치 머지 → 잔여 rebase (d) 당일(24h) 랜딩 원칙. + §13.2.3-A 에 META-0025
  구현 존재 표기 편승.
- Consequences: REGISTRY 부재였던 §13.2.8 알림 경로(session_id)도 부트스트랩됨.
  cycle-finalize Step 6 의 기존 REGISTRY 이동 로직이 활성화. hard 차단 없음 — 게이트는
  전부 soft(경고·가시화). template base 전파 후보.

## ADR-20260727T190000-cycle-privilege-adapter

- Status: 승인 (사용자 결정 2026-07-27 — "root 계정을 통한 호출이 아닐 경우, 항상 sudo 로
  작업되도록 구성" + "template-base 에도 적용". 구현 방식은 적대 검증 실측 후 **전체 재실행
  → 범위 축소로 선회**, 사용자 재확인 2026-07-27)
- Context: 같은 프로젝트를 여러 OS 계정(`root` / `claude-corp`)이 번갈아 다룬다. 공유 운영
  파일 `<project_root>/worktrees/REGISTRY.md` 는 `mktemp`(0600) + `mv` 원자 rewrite 를 쓰는데,
  `mv` 가 mktemp 의 모드를 그대로 남겨 **기록 한 번마다 `0600 <직전 실행자>` 로 굳는다**.
  POSIX ACL 배치에서는 `chmod` 의 group 비트가 ACL `mask` 를 `---` 로 눌러
  `user:<other>:rwx` 를 `#effective:---` 로 무효화한다. 2026-07-27 라이브에서 두 번 발현 —
  ① cycle-init REGISTRY 기록 실패, ② cycle-finalize Step 6 이 **권한 실패를 "비-META-0029
  스키마" 로 오진**(grep 이 읽기 실패 시 조용히 false). 두 cycle 이 수기 우회했다.
- Decision (**§13.2.10 신설** + `bin/lib/privilege.sh` 공용 어댑터 — *최소 권한·최소 개입*):
  (a) **`git`·`gh` 는 언제나 원 호출자로 실행**한다. 승격 대상은 오직 "공유 운영 파일이
  다른 계정 소유로 굳어 접근 불가일 때 그 접근권 복구".
  (b) **`priv_ensure_writable`** — 이미 쓸 수 있으면 즉시 반환(정상 상태에서 sudo 호출 0회).
  불가할 때만 ① `chmod 0664`(ACL 배치는 `mask` 복원만으로 해결) → ② 그래도 안 되면
  `chown` 현재 실행자. 소유권 이전은 최후 수단.
  (c) **`priv_share_file`** — `mktemp` 직후·`mv` **전에** 0664 로 되감아 rewrite 순간의
  접근 불가 창과 중간 실패 시 0600 영구화를 함께 없앤다. sudo 불요.
  (d) **비차단 degrade** — `sudo -n` 실패면 경고 후 계속. 우회 `PRIV_NO_SUDO=1`.
  (e) **오진 방지** — `priv_access_reason` 이 `read-denied`/`write-denied`/`ok` 를 구분.
  0664 정규화 이후 남는 실패는 대개 **쓰기** 거부이므로 읽기만 보면 같은 오진이 재발한다.
  (f) **symlink 거부 + `chown --no-dereference`** — `chmod`/`chown` 이 링크를 추종해 임의
  파일의 모드·소유권을 바꿔주는 경로 차단.
  (g) 승격과 함께 **기존 `eval` 구멍**도 닫는다 — `FEATURE_ID`/`AGENT_NAME`
  `^[A-Za-z0-9._-]+$`, `BASE_BRANCH` `^[A-Za-z0-9._/-]+$`. `AGENT_NAME` 기본값은
  `${SUDO_USER:-${USER:-ai}}`.
- 대안 검토 (**폐기: 스크립트 전체 `sudo -E` 재실행**): 처음 구현한 방식이며, §18.8 적대
  검증이 격리 sandbox(no-ACL) 실측으로 결함 3건을 재현해 폐기했다 (REV-20260727T190500).
  ① `sudo` 는 `-E` 를 줘도 `USER`/`LOGNAME` 을 runas 로 덮어써(`HOME` 만 보존) `--agent`
  기본값이 `root` → 브랜치 `ai/root/<feat>` 회귀 + dry-run 프리뷰와 실제 실행 불일치.
  ② `run_or_dryrun` 의 `eval` 이 root 로 실행 → feature slug 한 개가 root 임의 명령 실행
  (`--feature 'a;id>${PWD}pwn'` 로 worktree 밖 uid 0 파일 생성 실증).
  ③ git 이 root 로 돌아 `.git/worktrees/<name>`·`.worktrees`·`FETCH_HEAD`·`refs/heads/*`
  가 root 소유로 남고, no-ACL 배치에서 cycle-init 성공 직후 `git add` 가
  `index.lock: Permission denied` 로 실패 — cycle 의 존재 이유가 파손. 이후
  `PRIV_NO_SUDO=1` fallback 도 영구 실패하며 원인을 "non-fast-forward?" 로 오진(고치려던
  패턴의 재발). 부수적으로 `secure_path` PATH 교체(→ `~/.local/bin` 의 `gh` 상실),
  sudo umask 0022 강제(→ group-write 공유 배치 무력화) 회귀 확인.
  범위를 좁히면 ①②③ + PATH·umask 회귀가 **구조적으로 소멸**한다.
  - *`setfacl` 직접 조작*: 이식성이 낮고(`setfacl` 부재 환경), `chmod 0664` 만으로 `mask`
    가 복원되는 것을 실측 확인해 채택하지 않았다.
- Consequences: 정상 상태의 cycle 은 **동작·소유권·PATH·umask 가 종전과 완전히 동일**하다
  (sudo 경로를 타지 않으므로). 권한이 깨진 경우에만 복구가 개입하고, 복구 불가 시에도
  cycle 은 계속 진행하며 원인을 정확히 보고한다. 승격 범위가 좁아 `-E` 환경 전면 보존
  (`GIT_SSH_COMMAND`·`GIT_CONFIG_*`·`HOME` 이 root git 에 먹히는 문제)도 발생하지 않는다.
  template base 전파 대상 (§13.2.10 + `bin/lib/privilege.sh`).

## ADR-20260728T120000-redteam-gating-not-adopted

- **상태**: accepted (사용자 결정 2026-07-28)
- **맥락**: feature-0026 계측이 답변 지연 141초의 33%(평균 46.4초/답변)가 red-team 자가
  적대 리뷰 파이프라인임을 확정했다. 7일 실측에서 `verdict='BLOCK'` 은 0건이었으나
  `revision_applied` 는 89건 중 21건(24%) — 리뷰가 실제로 답변 수정을 만들고 있었다.
  `REDTEAM_MIN_LEVEL` 을 상향하면(관리 콘솔 런타임 설정, 코드 변경 0) 그 지연을 즉시
  제거할 수 있어 성능 개선 후보로 표면화했다.
- **결정**: **채택하지 않는다.** red-team 게이팅은 현행(기본 추론강도부터 작동) 유지.
- **근거(사용자)**: ① **품질 우선** — 24%의 답변이 실제로 개선되는 값을 지연과 바꾸지
  않는다. ② 이 제품에는 **'즉시 답변' 컴포저 인라인 버튼**이 있어, 기다릴지 지금 받을지의
  **시간적 판단이 이미 사용자에게 위임**돼 있다. 시스템이 일괄로 품질을 낮추는 대신 개별
  사용자가 상황에 맞게 선택하는 구조가 더 낫다.
- **영향**: feature-0027(P0 답변 지연)의 범위에서 red-team 축을 제외했고, 대신 품질과
  무관한 축(post-answer 큐레이션 이연·grounding 연결 공유)만 개선했다. 향후 성능 cycle 도
  이 결정을 뒤집지 않는다 — 지연 예산이 문제면 큐레이션·인프라·전달 경로를 먼저 본다.
- **재검토 조건**: '즉시 답변' 사용률이 매우 높아 사실상 전원이 리뷰를 건너뛰거나,
  revision 적용률이 유의하게 떨어져 리뷰의 품질 기여가 사라진 것이 계측으로 확인될 때.

## ADR-20260805T153000-p5a-closeout

- **결정 (2026-08-05, 사용자 위임 "개발 이력·대화 내역 검토 후 방향 결정" — ssot ROADMAP §4 미결정 #4·#5 종결)**:
  1. **#4 GDPR legal-erasure 사본 = 보존 확정** — feature-0002 `attachment_reconciliation.py`(미배선)는
     삭제·dedup-merge 하지 않는다. 근거: 적대 리뷰(42 에이전트) 판정 "중복 아닌 별개 worker" +
     feature-0011 ANCHOR §3 + CODEBASE_MAP §7 Known Gaps 등재. 보강: 파일 헤더 미배선 라벨(본 ADR 동반).
     wiring 은 별도 compliance 결정 사항으로 유지.
  2. **#5 Dockerfile 분리 = 불채택(단일 이미지 유지)** — P5a Step 6 을 수행하지 않고 P5a 를 종결한다.
     근거: 분리의 원 전제(148 cross-feature import 얽힘·SSOT 경계 불명)는 shared/ 추출(feature-0011
     Step 1~5, 2026-06-25 완성)과 CODEBASE_MAP §7 명시로 해소됐고, 이후 배포 인프라(feature-0014
     asset-stamp·feature-0020 deploy-web 스파인·feature-0039 ops-scheduler)가 단일 이미지 전제로
     구축·안정화됨. web→0002 modules 의존 실측 8종(2026-08-05) — 분리 실익 대비 스파인 전면 재설계
     비용이 큼. 향후 이미지 크기/보안 요구가 실측으로 등장하면 별도 initiative 로 재평가.
  3. **reconciliation env 키 정본 = `ATTACHMENT_RECON_INTERVAL_SEC`** (라이브 0003판 기준,
     .env.example 문서화). 미배선 0002판의 `ATTACHMENT_RECON_POLL_SEC` 는 사양 보존본 내부 명칭 —
     wiring 시 정본 키로 통일하며 별도 alias 배선은 하지 않는다(미배선 코드에 alias 는 무의미).
- **대안**: #4 제거(사양은 문서 보존) — SSOT 이중정본 해소 관점의 후보였으나, 적대 리뷰·ANCHOR 의
  기존 판정("별개 worker·보존")을 뒤집을 신규 근거 부재로 불채택. #5 분리 강행 — 선행(shared/)은
  충족했으나 6주간의 스파인 안정화 실적을 리스크로 되돌릴 실익 부재로 불채택.
- **영향**: ssot ROADMAP ITEM-P5a 종결(§4 미결정 #4·#5 해소), feature-0011 TASK Step 6 불채택 종결.

## ADR-20260825T170000-cc-identity-chokepoint
- Status: accepted
- Date: 2026-08-25
- Context: OAuth 구독 토큰(`sk-ant-oat…`)으로 나가는 frontier 모델(Sonnet 5 · Opus 5)은 Anthropic 이
  **system 첫 블록에 Claude Code identity 문자열**을 요구하며, 없으면 429 `rate_limit_error` 로
  거부한다. 이 429 에는 `anthropic-ratelimit-*` 헤더가 실리지 않아 실제 한도 초과와 형태가 다르다.
  2026-07-24 최초 봉인(ADR 없이 코드만)은 주입을 **호출측 3곳**(대화 답변·redteam 리뷰어·provider
  health probe)에 개별 배치했다. 2026-08-25 **동일 장애가 재발** — 개별 주입이라 그 3곳 밖의 경로는
  무방비였고, 라이브 대화가 18회 재시도(5분) 끝에 실패한 뒤 사용자에게는 원인과 무관한
  데이터소스·VPN 안내가 나갔다. 진단도 오도되어 사용량 소진·계정 한도로 두 차례 오판했다
  (동일 토큰으로 Haiku 200 / 상위 4개 모델 429, 사용률 44% 계정도 동일 → 사용량 축 기각으로 확정).
- Decision: identity 주입을 **provider 전송 직전 단일 관문**으로 접는다.
  1. `shared.model_catalog.ensure_oauth_frontier_identity(messages, model)` — 주입 규칙의 단일 정본.
     멱등(이미 주입돼 있으면 동일 객체 반환)이라 호출측 잔존 주입과 겹쳐도 중복되지 않는다.
  2. `modules.llm.prepare_provider_messages(messages, model)` — identity 주입 + 프롬프트 캐시
     브레이크포인트를 함께 적용하는 관문. **provider 로 나가는 모든 경로가 이 함수를 쓴다.**
  3. `_apply_prompt_cache()` 직접 호출 금지(관문 내부 1회만) — 캐시만 단독으로 거는 코드가 곧
     identity 를 빠뜨린 코드이며 재발의 정확한 형태였다. `test_cc_identity_chokepoint.py` 가 AST 로 강제.
  4. 정책 정본: `AGENTS.md §15.2.1`(도메인 절대 금지사항).
- Consequences:
  - 신규 LLM 호출 경로는 관문만 쓰면 identity 계약을 자동 충족한다.
  - 배선 검사가 **흔한 누락 형태**를 배포 전에 잡는다 — 관문 미경유·반환값 버림·관문 뒤 덮어쓰기·
    첨자 대입 되돌리기(뮤테이션 6종으로 역검증, 전부 KILL). 다만 **정적 검사의 한계는 명시해 둔다**:
    값이 여러 함수·자료구조를 건너 흐르는 정교한 우회까지 잡지는 못한다(적대 리뷰가 실증). 최종
    안전망은 배포 후 라이브 실측이며, 실제 재발 2회는 모두 이 검사가 잡는 단순 누락이었다.
  - 적용 **순서**(identity↔캐시)는 결과에 영향이 없음을 실측 확인했다(뮤턴트 M3 생존 = 동치 뮤턴트).
    잠근 것은 순서가 아니라 **둘 다 누락 없이 적용되는가** 다 — 인위적 순서 단언은 만들지 않았다.
  - 남은 위험: identity 게이트는 Anthropic 측 정책이라 문자열·적용 대상이 예고 없이 바뀔 수 있다.
    변경 시 증상은 다시 429 이므로, `AGENTS.md §15.2.1` 의 진단 순서(ratelimit 헤더 유무 → Haiku 대조)
    를 먼저 따른다.
- 대안: (a) 정식 API 키(`sk-ant-api03…`) 전환 — identity 요구가 사라져 구조적으로 가장 깨끗하나
  과금이 구독→종량제로 바뀌어 운영 결정 필요, 별도 트랙으로 이월. (b) 대화 답변을 budget 계열로 상시
  강등 — 게이트를 우회하지만 품질 저하가 상시화되어 불채택.

## ADR-20260826T220000-vision-ownerless-inline-image-stays-open

- Status: accepted (재확인 — 선행 결정 `REQ-20260814-vision-provenance` 유지)
- Context: `/_dqa:conversation_audit`(2026-08-26) 의 §18.8 적대 리뷰가 **여러 라운드에 걸쳐 반복해서**
  같은 지적을 올렸다 — "소유자 키가 없는 inline image 는 본문이 프롬프트에 들어가는데 provenance
  신호를 세우지 않으므로, 이미지 안의 지시가 `scratch_*` 쓰기 게이트를 우회할 수 있다"([P1]).
  같은 cycle 에서 텍스트 본문 · sandbox 샘플 · 온디맨드 `read_attachment` · 원본 `_v0` 축은 전부
  fail-closed 로 닫았다(`FR-unknown-owner-attachment-trusted-by-provenance-gate`).
- Decision: **이미지 경로의 owner-less 항목은 계속 신호를 세우지 않는다**(열어 둔다).
  - 근거: inline image JSON 은 **web 이 쓰고 worker 가 읽는 파일 계약**이다. 롤링 배포 중에는 구
    형식(소유자 키 없음)과 신 형식이 공존하는 창이 생기고, 그 창에서 owner-less 를 막으면
    **1:1 사용자까지** 쓰기 도구가 통째로 막힌다 — 공유 대화와 무관한 대다수 사용자가 영향받는다.
    `REQ-20260814-vision-provenance` 가 이 가용성 비용을 재고 내린 결정이며
    `test_missing_owner_keeps_previous_behavior` 가 계약으로 고정하고 있다.
  - 텍스트/csv 축에는 같은 비용이 없다: 그 소유자는 **DB 행**(`AccountId`)에서 오고 배포 형식과
    무관하다(라이브 실측 NULL/0 **0 / 1,101**). 그래서 거기만 닫았다 — 비대칭은 의도된 것이다.
- Consequences:
  - 잔여 위험은 **명시적으로 열려 있다**: owner-less inline image 본문이 쓰기 게이트를 통과한다.
    실현 조건은 (a) 롤링 배포 혼합 창 또는 (b) 소유자 키를 잃은 경로가 새로 생기는 것.
  - 닫으려면 **inline JSON 형식 마이그레이션이 선행**돼야 한다(구 형식 소멸 확인 후 fail-closed 전환).
    그것은 배포 순서 의존이 있는 별도 작업이며 사람 결정 대상이다.
  - 이 ADR 의 목적은 §18.8 「의도된 구성은 ADR 로 영구화한다」에 따른 **억제**다 — 근거 없이
    같은 지적이 매 라운드 재상정되는 것을 막되, 지적 자체를 무르게 만들지 않는다. 위 실현 조건이
    관측되면 즉시 재개봉한다.
- 대안: (a) 즉시 fail-closed — 배포 창 동안 1:1 사용자 쓰기 도구 차단, 불채택. (b) owner-less 이미지를
  **주입하지 않음** — 이미지 첨부 기능이 배포 창 동안 사실상 정지, 불채택. (c) 형식 마이그레이션 후
  전환 — **채택 예정**(별 트랙).
