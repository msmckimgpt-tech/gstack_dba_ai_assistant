---
doc_type: PROJECT_DECISIONS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.10.0
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
