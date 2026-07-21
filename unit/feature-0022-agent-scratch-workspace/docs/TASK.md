---
doc_type: TASK
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Task

## 진행 상태
- [x] TASK-0001: 설계 확정 — 전용 DB `agent_scratch` + 대화별 스키마 + 24h 시간기반 reaper
  (사용자 3-decision 승인, 2026-07-21).
- [x] TASK-0002: PG bootstrap — `bin/scratch-pg-bootstrap.sh` + `agent_scratch_schema.sql`
  (DB/role 생성·CONNECT 격리·레지스트리 스키마).
- [x] TASK-0003: shared 배선 — `config.AGENT_SCRATCH_*` + active conversation ContextVar,
  `db._pg_connect_scratch`.
- [x] TASK-0004: `modules/scratch.py` 코어 — 대화 스키마 lifecycle·materialize(타입추론·캡)·
  scratch guard·run_sql·list·reset·TTL reaper.
- [x] TASK-0005: 런타임 설정 `AGENT_SCRATCH_*` 스펙 + ask-worker reaper 훅.
- [x] TASK-0006: 도구 4종(`scratch_import`/`scratch_sql`/`scratch_list`/`scratch_reset`)
  schema·handler + agent_core 노출(활성 시)·대화 ContextVar set/reset.
- [x] TASK-0007: 단위 테스트(guard/스키마명/타입추론/enabled 게이트) 15건 + make test 회귀 대조
  (feature-0002/0003 RC=0, 회귀 0).
- [x] TASK-0008: unit 문서(FUNCTION/TASK/DECISIONS/TEST/ANCHOR/REVIEW) + wiki 카드.

## 다음 액션 (활성화 — 운영자/후속 cycle)
- [ ] TASK-0009: 배포 호스트에서 `bin/scratch-pg-bootstrap.sh` 실행(agent_scratch DB/role 생성)
  + `.env` 에 `AGENT_SCRATCH_PG_USER`/`AGENT_SCRATCH_PG_PASSWORD` 설정.
- [ ] TASK-0010: 관리 콘솔 설정에서 `AGENT_SCRATCH_ENABLED=1` 로 활성화.
- [ ] TASK-0011: 라이브 e2e — 두 datasource 반입→JOIN→TTL 만료 DROP 실증(+ 격리·guard 라이브 확인).
- [ ] TASK-0012(후속): 관리 콘솔 작업공간 현황 관측 UI.
- [ ] TASK-0013(후속·보안 강화): 대화별 전용 PG role + s_* USAGE 로 **PG 레벨** 대화 격리 승격
  (적대 리뷰 권장 — 현재는 scratch_guard allowlist 가 격리 강제).

## 적대적 보안 리뷰 대응 (feature-0021 §18.8, 2026-07-21)
- [x] BLOCK: `CREATE FUNCTION` 문자열 본문 cross-schema 은닉 → scratch_guard **allowlist 반전**
  (허용 root 명시 + CREATE/DROP=TABLE/INDEX kind 한정 + 함수/프로시저/뷰/DO/CALL/EXTENSION 거부).
- [x] HIGH: `pg_catalog` 무자격 참조 열거 → 테이블명·함수명 `pg_` 접두 차단.
- [x] MEDIUM: CONNECT 격리 문서 정확성 정정 + `--harden-kb-isolation` sibling DB(agent_runtime/
  agent_memory/web) 확대(opt-in).
- [x] MEDIUM: scratch_import 에 execute_sql parity heavy-query 게이트 추가.

## 후속 cycle (guidance + bootstrap fix, 2026-07-21)
- [x] TASK-0014: scratch 사용 guidance(`_SCRATCH_WORKSPACE_GUIDANCE`) agent_core 조건부 주입 —
  assistant·ask-worker 가 cross-source JOIN 시 적극 사용하도록 유도(사용자 요청).
- [x] TASK-0015: bootstrap superuser 결함 수정(운영 AGENT_KB_PG_USER=non-superuser → createdb
  permission denied) — 전용 superuser override + 소켓 trust 연결.

## 라이브 활성화 (2026-07-21) — 배포·스모크
- [x] TASK-0016: 배포 (make deploy-all, main ba60f4b9 — web-a/b·ask/insight-worker healthy).
- [x] TASK-0017: agent_scratch DB/role/레지스트리 생성 + KB PUBLIC CONNECT harden(격리 3중 검증).
- [x] TASK-0018: .env AGENT_SCRATCH_PG_* (postgres 직결 — pgbouncer 우회, userlist 미등록 회피).
- [x] TASK-0019: AGENT_SCRATCH_ENABLED=1 (WebRuntimeSettings DB + 스냅샷).
- [x] TASK-0020: 라이브 스모크가 run_sql SET 버그 적발 → 수정(CHG-runsql-fix) → 재배포·재스모크.
