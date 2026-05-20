---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260520-0002
- Date: 2026-05-20
- TASK-Cycle: TASK-0016 (M-1 baseline 측정, Minor §12.3 — read-only)
- Summary: §2.1 PLAN-APPROVED 의 **M-1 phase** 사전 baseline 측정 실행. `bin/kb-measure-baseline.sh` (read-only 측정 스크립트) 신규 + 4/5 측정 (rows / EXPLAIN / JOIN audit / RBAC audit) + JSON artifact (`artifacts/shared/kb-baseline-2026-05-20.json`) 저장. Latency baseline (5/5) 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer.
- Worktree: `ai/claude/0002/kb-pg-m-1` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-kb-pg-m-1/`. 사용자 결정 (2026-05-20): "다음 cycle 또한 신규 worktree에서 진행해주세요".
- Files:
  - `bin/kb-measure-baseline.sh` (신규) — 5 mode: `--rows` / `--explain` / `--joins` / `--rbac` / `--all`. main worktree 의 `.env` fallback + `repo-mysql-1` 직접 `docker exec` (docker compose project name 충돌 회피). 미설치 환경에서 wrapper path 자동 detect.
  - `unit/feature-0002-agent-core/docs/TASK.md` — §1.1 cycle 등록 (TASK-0016) + §1.2 cycle-specific plan + §1.3 TASK-0015 summary + §1.4 historical summary + §3 Task Queue + §4 In Progress + §5 Blocked (clear) + §6 Done + §7 Next Action + §8/§9 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md` — `REV-20260520-0003 [SKIPPED:outside-voice-not-required]` append (측정 cycle 의 의사결정 0건 + JSON artifact 의 sanity check).
  - `unit/feature-0002-agent-core/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md` — §1 Summary 의 M-1 measurement 결과 + §4 Open Issues / §7 Human Attention Needed 갱신 (M0 cycle 진입 안내 + Blocker B-1 Sprint 4 schema 확인 reminder).
- Generated artifacts (git 추적 외):
  - `artifacts/shared/kb-baseline-2026-05-20.json` — measurement 정본. M4 cutover gate (`bin/kb-cutover-readiness.sh`) 의 비교 대상.
- Measurement summary (artifact 의 핵심 필드):
  - rows: FactEntries 774 / Texts 798 / RagDocuments 831 / RagObjects 774 / Facts VIEW 774
  - joins: non_kb_to_kb 0 / kb_to_non_kb 0 (expected 0 ✓ — Open Q #9 충족)
  - rbac: kb_permissions 0 / memory_permissions 0 / agent_kb_permissions 0 / permission_definitions_total_approx 40 (outside-voice Section D 정합 — Postgres 분리 후 role 신설 필수)
  - explain: Q1 range, Q2 ref, Q3/Q4/Q5 ALL (full scan — pgvector ANN selectivity 이득 영역)
  - latency: `deferred_to=M0` (docker compose project name 충돌 회피)
- Verification (본 cycle):
  - 본 cycle 의 코드 mutation 0건 (스크립트 신규 추가만). 외부 영향 0건 (LLM 호출 없음, DB read-only).
  - `bin/kb-measure-baseline.sh` 자체 실행 검증 — `--all` 모드 → JSON 정상 parse + 5 mode 개별 실행 PASS.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출.
- 사용자 결정 (2026-05-20): 즉시 자동 commit + push + main ff-merge — 전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족 (M-1 은 Minor).

## CHG-20260520-0001
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3)
- Summary: KB 정본 5종 (`AgentMemoryFacts` view + `FactEntries` + `Texts` + `RagDocuments` + `RagObjects`) MySQL → Postgres pgvector 마이그레이션 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성. 본 cycle 자체는 plan-작성 cycle 이며 코드·schema·데이터 변경 없음. doc 4종 (TASK, REVIEW, MODIFY, REPORT) 만 갱신.
- Worktree: `ai/claude/0002/pgvector-migration-plan` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-pgvector-migration-plan/`. 사용자 결정: "현재 세션에서 신규 Worktree를 생성 및 진입하되, 해당 worktree에서 plan 작성 또한 진행합니다."
- Files:
  - `unit/feature-0002-agent-core/docs/TASK.md`: §1.1 cycle 등록, §1.2 본 plan-작성 plan, §2.1 신규 마이그레이션 plan (M0~M5 phase + 결정 매트릭스 + 영향 파일 + 검증 체크리스트 + Open Questions), §2.2 기존 plan archive, §3 Task Queue TASK-0015 추가, §4 In Progress, §5 Blocked, §6 Done, §7 Next Action, §8 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md`: `REV-20260520-0001` append (3-D 결정 + trade-off + alternatives + outside-voice 호출 사유).
  - `unit/feature-0002-agent-core/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md`: §4 Open Issues + §7 Human Attention Needed 에 plan-review 상태 표면화 + cutover 시 사람 confirm 필요 항목 명시.
- Plan 의 Execute 영향 (참고 — 본 cycle 에서는 변경 없음, 별 cycle 진행):
  - Source: `modules/{memory,knowledge,insight,schema,planner,utils}.py`, `modules/db.py`, `agent_core.py` (7,500+ LOC raw SQL dialect 변환)
  - Infra: `docker-compose.yml` (postgres 서비스 추가), `.env.example` (신규 `AGENT_KB_PG_*` / `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` / `AGENT_KB_EMBEDDING_*` / `AGENT_KB_ANN_*`)
  - Policy (META path): `AGENTS.md §11.3·§14.1·§15.6·§15.7`, `FUNCTION.md §10`, `INSIGHTS.md §4`, `ANCHOR.md §1·§3`, `docs/{DECISIONS,CONVENTIONS,SECURITY,STATUS,CODEBASE_MAP}.md`
  - Tests: `tests/test_pgvector_migration.py` (신규), `tests/test_compose_system_prompt.py` (회귀)
  - Tooling: `bin/{kb-backfill,kb-dual-write-verify,kb-cutover-readiness,kb-schema-compare,kb-pg-healthcheck}.sh` (신규), `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규)
- Verification (본 cycle):
  - 본 cycle 의 deliverable 은 doc 변경만. 코드 검증 불요.
  - outside-voice review (Plan subagent, Software architect agent) ✓ 완료 — `REV-20260520-0002`. Verdict **NEEDS-TWEAK** + 11 Blocker + 5 Nice-to-have. §2.1 본문 + §2.1.11 추적 표에 반영 완료.
  - 사용자 PLAN-APPROVED 마커 ✓ 부여 (2026-05-20 by ms.mckim.gpt@gmail.com) — TASK.md §2.1 직후의 `<!-- PLAN-APPROVED -->` 마커 + §1.2 status `plan-approved` + §8 Completion Checklist 갱신.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출 (PLAN-APPROVED 직후 자동 진행).
  - 사용자 결정 (2026-05-20): "즉시 자동 마커 추가 + commit/push" — verify-completion PASS 시 본 cycle commit + branch push + main ff-merge 자동 진행 (전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족).

## CHG-20260515-0003
- Date: 2026-05-15
- Summary: TASK-0014 (REQ-20260515-0003) Account scope 시스템 프롬프트도 `전 Product 공통 + Product 전용` 누적 방식으로 정정하고, 최종 user request 가 Product/Role/Account 지침 뒤에 보존되는 것을 테스트로 고정.
- Files:
  - `src/agent_core.py`: Account prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Account×Product 전용 지침 뒤 순서로 변경. `_fetch()`는 특정 Product 조회에서 miss 가 나면 공통 fallback 을 반환하지 않도록 정정해 중복 누적을 방지.
  - `tests/test_compose_system_prompt.py`: Product → Role → Account 순서, Account common+specific 누적, 최종 user request 메시지 보존 테스트 추가.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`

## CHG-20260515-0002
- Date: 2026-05-15
- Summary: TASK-0013 (REQ-20260515-0002) Role scope 시스템 프롬프트의 "전 Product 공통" 지침을 fallback 이 아니라 누적 적용으로 전환.
- Files:
  - `src/agent_core.py`: Role prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Role×Product 전용 지침 뒤 순서로 변경. auto 모드는 Product 전용 지침을 건너뛰고 공통 지침만 사용.
  - `tests/test_compose_system_prompt.py`: fake connection 기반으로 pinned 누적 / auto 공통-only 동작 검증.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
  - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 직접 조회로 `PRODUCT CONTEXT` 뒤 `ROLE GUIDANCE` 안에 `### 전 Product 공통`이 포함됨을 확인.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: agent 코어 소스와 Dockerfile을 기능 단위 구조로 이관
- Files: src/agent_cli.py, src/agent_core.py, src/modules/*, src/Dockerfile
- Notes: Web UI는 별도 feature에서 관리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 워크스테이션 Local LLM 지연 완화를 위해 역할별 모델 바인딩과 검증 문서를 정합화
- Files: src/modules/config.py, src/modules/llm.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../feature-0003-agent-web-ui/docs/TEST.md
- Notes: 현재 repo `.env` 의 alias/timeout/worker 값은 로컬 소비자 설정이라 Git 추적 대상이 아니다. 외부 provider 프로필 조정과 direct bench 기록은 `/root/download/docker/local_llm` 저장소에서 별도로 관리한다.

## CHG-20260421-0003
- Date: 2026-04-21
- Summary: insight-worker 누락 복구 경로와 일자별 로그 보관 구조를 추가
- Files: src/modules/insight.py, src/modules/utils.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../../../../AGENTS.md
- Notes: 기존 더티 워크트리는 보존하고 별도 worktree/브랜치에서 구현했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 완전성 검증을 통과할 때만 fingerprint/refresh 성공 마커를 갱신한다.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0012 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — agent-core 책임 범위, web-ui coupling 인정, modules/ 서브디렉토리 책임 구분, insight-worker 복구 순서 시나리오.
- Files: unit/feature-0002-agent-core/docs/ANCHOR.md, unit/feature-0002-agent-core/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. insight-worker 복구 순서를 바꾸려는 향후 요청은 §3과 충돌 감지 대상 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
