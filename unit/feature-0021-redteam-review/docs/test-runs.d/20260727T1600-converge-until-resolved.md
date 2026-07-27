---
run_at: 2026-07-27T17:40:00+09:00
session: ai/claude/feature-0021-redteam-review
scope: 결함 해소까지 반복 검증(REDTEAM_REVISE_UNTIL_RESOLVED) + 재검증 게이트 일반화(REDTEAM_VERIFY_MIN_LEVEL) + 사용자 '즉시 답변' 탈출구 + 잔존 결함 3중 표면화 + 리뷰어 대화 내부 맥락 기억 (CHG-20260727-0001)
verdict: PASS
---

### Run 0 — 라이브 진단 (Environment: repo-postgres-1, `agent_runtime.redteam_reviews`)

변경 전 실동작을 데이터로 확정. prefill fix 커밋 726c2f1e(2026-07-24 16:17) 배포 **이후** 표본만 분리:

| reasoning_level | n | verdict=revise | 수정 적용 | 재검증 | **재검증에서도 revise** |
|---|---|---|---|---|---|
| max | 7 | 7 | 6 | 6 | **4** |
| normal | 3 | 2 | 2 | **0** | — |
| high | 1 | 0 | — | — | — |

누적(전 기간 111행): normal `revise` 37건 중 재검증 **0건**, high `revise` 3건 중 수정 적용 0건
(07-22 이전 = prefill trap 시기 잔재), max `revise` 11건 중 수정 6 / 재검증 6.

→ 사용자 관측("항상 1회 검증")의 원인 3개를 분리 확정: ① WARN 무조치(설계 의도),
② 일반 강도 재검증 부재(`verify_pass = ordinal >= 2`), ③ 재검증이 결함 잔존을 판정해도
`REDTEAM_MAX_REVISIONS=1` 상한에서 종료. ②③ 을 결함으로 판정해 수정.

### Run 1 — red-team 단위 전량 (Environment: agent 이미지 격리 컨테이너, monkeypatch, DB/LLM 무의존)

- 명령: `docker run --rm -v $(pwd):/work … python -m pytest -q unit/feature-0002-agent-core/tests/test_redteam.py`
- 결과 **PASS — 67 passed** (기존 46 + 신규 21).
  - 게이트 계약: `test_plan_normal_verifies_by_default`(기본 0 → 일반 강도 재검증), `test_plan_verify_min_level_can_restrict`(escape hatch), `test_plan_revise_until_resolved_flag`, `test_plan_max_revisions_zero_disables_unlimited`(차단 스위치 우선). PASS
  - 수렴 루프: `test_unlimited_revise_loops_past_max_until_resolved`(상한 1 을 넘겨 4라운드 후 `resolved`), `test_orchestrate_normal_now_verifies_revision`(일반 강도 find+verify 2회·`revision_rounds=1`). PASS
  - 런어웨이 가드: `test_unlimited_revise_stops_on_no_progress`(공백만 다른 동일 수정본 → `no_progress`), `test_hard_backstop_caps_pathological_loop`(백스톱 3 주입 → `backstop`). PASS
  - 사용자 탈출구: `test_abort_fn_stops_loop_immediately`(2라운드 뒤 즉시 답변 → `aborted`·그 시점 답변 채택), `test_abort_fn_exception_does_not_break_loop`(fail-open 불변). PASS
  - 잔존 결함 표면화: `test_unresolved_notice_appended_when_defect_survives`, `test_unresolved_notice_not_duplicated`, `test_no_notice_when_resolved`, `test_record_receives_convergence_observables`(`unresolved_block_count`/`stop_reason`/`revision_rounds`/`verify_findings` 저장 계층 전달). PASS
  - 리뷰어 기억: `test_run_review_receives_round_history`(2라운드째 호출에 자기 1라운드 findings + 수정본 발췌 동반), `test_history_block_contains_own_rounds_and_conversation`, `test_run_review_prompt_has_memory_rules`(해소 판정 규칙), `test_run_review_injects_history_into_user_block`. PASS
  - 격리·보안: `test_history_requires_conversation_scope`(cid 부재 → 미조회), `test_history_conv_limit_zero_skips_pg`, `test_history_block_strips_sentinel_breakout`(구획 breakout 차단). PASS
  - 회귀 보존: 기존 `test_orchestrate_revises_up_to_max_on_high`·`test_orchestrate_max_revisions_zero_records_only`·rederive 축 라우팅 전건 PASS (`REDTEAM_REVISE_UNTIL_RESOLVED=0` 로 상한 계약 유지).
- 진행 표시: `test_progress_fn_reports_each_round` — 라운드마다 "수정 N회차"/"재검증 N회차" activity 방출. PASS

### Run 2 — 전체 회귀 (Environment: agent 이미지 격리 컨테이너, `.env` 미주입)

- 명령: `python -m pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests`
- 결과 **PASS — 전건 통과, 실패 0**.
- ruff: **clean** (`unit/feature-0002-agent-core/src` · `unit/feature-0003-agent-web-ui/src` · `shared`).

### Run 3 — `.env` 주입 환경 인과 확증 (Environment: `docker compose run` — `.env` 로드)

- worktree 에서 `make test`(compose run, `.env` 주입) 실행 시 4건 실패:
  `test_missing_snapshot_is_fail_open`, `test_get_returns_registry`(둘 다 `AGENT_TIMEOUT_SEC`
  기본 60 단정인데 `.env` 가 300), `test_schema_analysis_fail_loud_on_status_aggregation_failure`,
  `test_auto_happy_200`(라이브 PG 부재).
- **동일 명령을 main(`repo/`)에서 실행해도 같은 2건 이상이 실패**하고, 같은 코드를 `.env` 미주입으로
  실행하면 전건 통과 → 본 변경 무관한 환경 의존임을 확증 (TASK-20260724T0709 cycle 의 동일 관측과 일치).

### Run 4 — §18.8 적대 검증 패널 반영 후 재실행 (Environment: agent 이미지, `.env` 미주입)

- 패널(2 렌즈) 지적 **BLOCKING 4 · MAJOR 6 · MINOR 6** 전건 반영 → 회귀 잠금 테스트 14건 추가.
- 명령: `python -m pytest -q unit/feature-0002-agent-core/tests/test_redteam.py`
- 결과 **PASS — 81 passed** (기존 46 + 1차 신규 21 + 패널 회귀 14).
  - 격리: `test_history_requires_conversation_scope`, `test_history_conv_limit_zero_skips_pg`
    (+ `has_restricted_members` fail-closed 는 라이브 PG 경로라 배포 후 실증 — 아래 잔여).
  - 수렴: `test_history_block_preserves_newest_round_under_cap`(cap 포화에도 최신 라운드 생존),
    `test_rederive_evidence_accumulates_across_rounds`(원본 + 전 라운드 근거 동시 노출). PASS
  - 탈출구: `test_abort_check_failure_streak_stops_loop`, `test_wall_budget_stops_loop`. PASS
  - 인젝션: `test_history_block_is_datamark_fenced`, `test_history_block_flattens_newline_forgery`,
    `test_permission_axis_downgrade_forbidden_in_prompt`. PASS
  - 정직성: `test_max_revisions_zero_does_not_attach_notice`,
    `test_unverified_does_not_assert_unresolved`, `test_downgraded_stop_reason_when_block_becomes_warn`,
    `test_unresolved_notice_idempotency_uses_flag_not_substring`. PASS
  - 추적성: `test_no_progress_round_does_not_leak_rederive_state`,
    `test_adopted_rederive_steps_returned_for_caller`, `test_round_history_how_is_round_local`,
    `test_verify_findings_present_even_without_rounds`. PASS
- 전체 회귀 재실행: **PASS — 전건 통과**. ruff: **clean**.

### Run 5 — 마이그레이션 lint

- 명령: `bash bin/migrate-lint.sh`
- 결과 **PASS** — head 단일성(`0045_redteam_convergence_columns`, revision 45건, 번호 중복 0,
  MAX_MIGRATION 일치) + `20260727_0045_redteam_convergence_columns.py` **expand-safe**.

### 잔여 (배포 후 필수)

- POST-DEPLOY: `alembic_version` 이 `0045_redteam_convergence_columns` 인지 직접 확인
  (stale agent 이미지로 신규 마이그레이션을 놓치는 선례 있음).
- POST-DEPLOY: 공유창 window 격리 fail-closed 실증 — `has_restricted_members=true` 대화에서
  리뷰어 대화 기억이 조회되지 않는지(라이브 PG 경로, 단위 테스트로 커버 불가).
- POST-DEPLOY PB-0008 (Environment: Windows-browser) — 관리 콘솔 감사 > AI 운영 현황 > 추론:
  '결함 잔존 전달 (7d)' 통계 타일 · 타임라인 ④⑤ 문구 · 미해소 지적 블록 렌더 육안 검증
  (`visual_verification_scope: always`, verify-completion check #13 hard gate).
