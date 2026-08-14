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
- [x] TASK-0014: scratch_sql 결과 CSV export (DQA 마찰 F-5/C-3, 2026-07-22, 코드 feature-0002 거주).
  과거엔 `run_sql` 이 미리보기 상한(200행)까지만 fetch 하고 CSV 미저장 → 대량 cross-DS 병합 결과
  회수 곤란. 해결: `run_sql` 을 export 상한(`AGENT_SCRATCH_MAX_RESULT_ROWS`=100000)까지 전체
  fetch(+`export_truncated`), `_tool_scratch_sql` 이 execute_sql parity 로 `save_csv(
  "scratch_resultset1", …)` → "CSV 저장: <path>" emit. 웹은 기존 `CSV_PATH_RE` 로 다운로드 링크
  생성(프론트 무변경). 미리보기는 execute_sql 표 포매터(50/adaptive) 절단 + 미열람 행 단정 금지 안내.
  테스트 3건(`test_scratch.py`: CSV 경로 추출·대량 전체 export·표 포매터 회귀). 정본 코드 TASK =
  `feature-0002-agent-core/docs/TASK.md` TASK-20260722-dqa-scratch-csv-export.

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
- [x] TASK-0021: 라이브 자율 사용 확인 — cross-source(2 dev DS) import→UNION→합산 중앙값을 assistant 가
  scratch 로 자율 수행(scratch_import×2 + scratch_sql). 검증 후 임시 테스트 제품·잔재 정리.
- [x] TASK-0022: 사용자 피드백 — scratch_sql 결과셋 출력을 execute_sql 동일 표(_format_result_sets)
  형식으로 통일(plain-text ` | ` 나열 → Markdown 표). 죽은 _fmt_scratch_rows 제거·회귀 테스트.

## 20260814T0304-scratch-fork-carryover

사용자 보고: "대화를 분기하면 기존 대화에서 보존되던 assistant 개인 작업 공간(scratch)을 더 이상
참조할 수 없다 — 답변 품질·맥락 보존을 위해 구조적으로 개선". 근본 원인은 분기가 문맥은 복사하면서
작업공간은 이월하지 않아 **문맥에만 존재하는 유령 테이블**이 생기는 것(ADR-SCRATCH-0005).

- [x] TASK-20260814T0304-clone: `scratch.clone_workspace(src, dst)` — 원본 스키마 테이블을
  분기본으로 CTAS 독립 복사. 캡(테이블 수·총 행수·문당 timeout·전체 시간 예산) + 부분 성공 보고
  (`cloned`/`skipped_detail`/`truncated`) + fail-soft(예외 미전파).
- [x] TASK-20260814T0304-hook: `_fork_conversation_impl` 에 이월 훅 — 분기 3 경로(사본 만들기·
  앵커 분기·공유 링크 복제) 공통 적용. 응답에 `scratch_cloned`/`scratch_truncated` 노출.
- [x] TASK-20260814T0304-audit: `share.fork` 감사 기록에 `scratch_tables_copied`(건수만) 추가 —
  교차계정 이월의 forensics(사용자 결정으로 이월 허용, 추적성 보완).
- [x] TASK-20260814T0304-state: `agent_core._scratch_workspace_state_note` — 매 턴 실재 테이블
  목록을 "문맥보다 우선하는 사실" 로 주입. 빈 작업공간은 EMPTY + 재반입 유도, 조회 실패는 침묵.
  TTL 만료로 작업공간이 사라진 대화 재개에도 동일 적용(같은 결함의 두 번째 발현 경로).
- [x] TASK-20260814T0304-settings: 런타임 설정 3종 추가 — `AGENT_SCRATCH_FORK_CARRYOVER`(기본 1),
  `AGENT_SCRATCH_MAX_CLONE_ROWS`(기본 200000), `AGENT_SCRATCH_FORK_BUDGET_MS`(기본 10000).
- [x] TASK-20260814T0304-test: 단위 테스트 13건 추가(이월 캡·부분 실패·fail-soft·방향·상태 주입).
- [x] TASK-20260814T0304-live: 라이브 검증 — 작업공간이 있는 대화를 분기해 이월 확인 + 분기본에서
  이월 테이블 조회 + 상태 주입 문구 반영 확인.

## 9. Requested Scope (요청 범위 자기-열거) — 20260814T0304-scratch-fork-carryover

원 요청: "프로젝트 내 서비스에서 대화를 분기 시, 기존의 대화에서 보존되었던 assistant 의 개인 작업
공간(scratch)이 더 이상 참조할 수 없는 것으로 확인. assistant 의 답변 품질 및 맥락의 보존을 위해
해당 구조적 이슈를 개선."

- [x] `대화 분기 시 작업공간을 참조할 수 없는 구조 결함 해소` — 산출물:
  `modules/scratch.py:clone_workspace` + `routers/_conv_store.py:_fork_conversation_impl` 이월 훅 ·
  배선 확인: 분기 3 경로(사본 만들기 `conversations.py:834` · 앵커 분기 `conversations.py:3068` ·
  공유 fork `share.py:477`)가 모두 이 impl 단일 경로를 타는 것을 호출부 grep 으로 확인 — 훅 1곳이
  전 경로를 덮는다. 단위 테스트가 복사 방향(원본→분기본)·캡·부분 실패 계속을 고정.
- [x] `답변 품질·맥락 보존` — 산출물: `agent_core._scratch_workspace_state_note` 매-턴 주입 ·
  배선 확인: scratch 활성 대화의 시스템 프롬프트 조립부(`_SCRATCH_WORKSPACE_GUIDANCE` 직후)에 연결,
  빈 작업공간/조회 실패/실재 목록 3 분기를 단위 테스트로 고정. 이월 상한 초과·이월 실패·**TTL 만료**
  까지 포함해 "문맥엔 있는데 실물은 없는" 어긋남 일반을 차단한다.
- [x] `라이브 실증` — 산출물: TEST.md §5.4 Live Run log · 배선 확인: 배포 db5d469b 에서 PG 실권한 이월(7행) + 실 사용자 `duplicate` API `scratch_cloned=1` + 분기본 조회 성공 + 상태 주입 문구 2분기 확인, 검증 잔재 전량 정리.

**주장 affordance 실측 (G3)**: 분기 응답이 새로 주장하는 값 `scratch_cloned`/`scratch_truncated` 는
`clone_workspace` 반환값에서 직접 유도되며 단위 테스트가 값 계약(행수 합산·부분 실패 시 개수)을
고정한다. 사용자 대면 UI 문구 추가는 없다(백엔드·프롬프트 변경만).

**경계변수 양측 검증 (G4)**:
- `AGENT_SCRATCH_MAX_TABLES_PER_CONV`(테이블 수 캡) → 이하: 전건 이월(`test_clone_copies_source_
  tables`) / 초과: 초과분 skip + `truncated=True`(`test_clone_respects_table_cap`).
- `AGENT_SCRATCH_MAX_CLONE_ROWS`(행 예산) → 예산 내: 전건 이월 / 소진: 남은 테이블 skip + 남은
  예산이 `LIMIT` 로 SQL 에 반영(`test_clone_respects_row_budget`).
- `AGENT_SCRATCH_FORK_CARRYOVER`(운영자 스위치) → 1: 이월 수행 / 0: DB 미접근 no-op
  (`test_clone_noop_when_carryover_disabled`).
- 작업공간 테이블 수 0 vs ≥1 (상태 주입 분기) → 0: EMPTY 선언 + 재반입 유도 / ≥1: 실재 목록 표기
  (`test_workspace_state_note_declares_empty` / `..._lists_existing_tables`).
