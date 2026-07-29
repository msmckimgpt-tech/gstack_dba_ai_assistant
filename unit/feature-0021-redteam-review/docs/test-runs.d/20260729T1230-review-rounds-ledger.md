---
run_at: 2026-07-29T12:30:00+09:00
session: ai/root/feature-0021-review-rounds
scope: 자가검증·재검증 회차 단계 원장(0048) + 콘솔 대화 단위 격리·3계층 접이식 (CHG-20260729-0004)
verdict: PASS
---

### Run 0 — 근본원인 확인 (코드 정독, 라이브 조회 없음)

사용자 리포트("자가 적대 리뷰 활동은 각 대화의 마지막 리뷰사항만 기록된다")를 두 겹으로 환원:

1. **쓰기 측** — `redteam.orchestrate_review` 는 while 루프로 수정→재검증을 반복하지만
   `record_review` 를 **루프 종료 후 1회**만 호출한다(리뷰 호출 실패 경로 제외).
   그 1행의 `findings` 는 최초 리뷰, `verify_findings` 는 `current_review`(=**마지막** 재검증).
   → 2회차 재검증이 무엇을 지적했는지·3회차 수정이 어떤 방식이었는지는 저장되지 않는다.
2. **읽기 측** — `/api/admin/reasoning/redteam` 이 `id DESC` flat keyset 이라 같은 대화의
   리뷰가 목록 곳곳에 흩어지고, "더 보기" 경계에서 한 대화가 쪼개진다. 콘솔은 이 flat 목록을
   그대로 카드로 나열해 회차가 늘수록 스크롤이 폭증한다.

### Run 1 — 단위 검증 (Environment: agent 이미지 격리 컨테이너, `--no-deps`, monkeypatch)

- 명령: `COMPOSE_PROJECT_NAME=repo docker compose run --rm --no-deps -v $(pwd):/work -w /work \
  --entrypoint sh agent -lc 'pip install -q pytest; export PYTHONPATH=…; python -m pytest -q \
  unit/feature-0002-agent-core/tests/test_redteam.py \
  unit/feature-0003-agent-web-ui/tests/test_admin_reasoning.py'`
- 결과 **142 passed, 0 failed** (신규 12건 포함).

신규 테스트가 고정하는 계약:

| 테스트 | 고정하는 것 |
|---|---|
| `test_rounds_ledger_records_every_revision_round` | 2회 반복 수정 시 원장이 `(0,review) (1,revise) (1,verify) (2,revise) (2,verify)` — **회차 asc** 이고, 요약의 `revision_rounds` 와 원장의 revise 회차 수가 일치 |
| `test_rounds_ledger_pass_only_has_initial_review` | 결함 없음이면 0회차 자가검증 1건만 (군더더기 회차 미생성) |
| `test_rounds_ledger_marks_discarded_no_progress_round` | 무진전으로 **폐기된** 회차도 `note='no_progress'` 로 남아 "왜 여기서 멈췄나" 가 원장에서 읽힘 |
| `test_rounds_ledger_records_rederive_method_and_axis` | 도구 재추론 회차의 방식·축·도구 라운드 보존 |
| `test_insert_review_rounds_binds_expected_columns` | JSONB `::jsonb` cast · severity 집계 · `note` 64자 절단 |
| `test_record_review_rounds_failure_keeps_summary` | 원장 INSERT 실패(0048 미적용 stale 이미지)에도 **요약 행은 커밋 유지**, 원장만 롤백 |
| `test_conversation_page_orders_conversations_desc_and_reviews_asc` | 대화는 최근 순 desc, 대화 내 리뷰는 진행 순 asc (사용자 요구 정렬 계약) |
| `test_conversation_page_cursor_and_has_more` | 대화 keyset 페이징 — `HAVING MAX(id) < cursor`, next_cursor = 반환 마지막 그룹의 last_id |
| `test_conversation_page_marks_capped_group` | 대화당 상한 초과분을 `capped=True` 로 표시(무언의 절단 금지) |
| `test_attach_rounds_orders_by_round_index_asc` | 회차 동봉 정렬 `ORDER BY review_id, round_index, id` |
| `test_redteam_response_exposes_conversation_grouping_fields` | 응답 계약(`conversations`/`rounds_available`/`per_conversation_cap`) |

### Run 2 — 전체 회귀 (Environment: 동일 컨테이너, `make test`)

- 본 branch: 신규 12건 포함 전량 실행. **실패 15건은 전부 환경성 baseline** —
  `test_attachment_idor`(4) · `test_attach_inline_honesty`(4) ·
  `test_attachment_user_version_context`(5) · `test_runtime_settings`(1) ·
  `test_runtime_settings_api`(1).
- **baseline 대조**: 같은 컨테이너·같은 명령으로 **main worktree(변경 없음)** 에서 위 5개 파일을
  실행해 **동일한 15건 실패**를 확인했다. 예: `test_missing_snapshot_is_fail_open` 은
  `AGENT_TIMEOUT_SEC == 60` 을 기대하나 로컬 `.env` 가 300 을 주입한다(환경 의존).
  → 본 변경과 인과 없음. 변경 파일(redteam / admin_reasoning / admin.js / styles.css / alembic)
  과 실패 파일은 서로 겹치지 않는다.
- `ruff check unit/feature-0002-agent-core/src unit/feature-0003-agent-web-ui/src` —
  **All checks passed!**

### Run 3 — PB-0008 실 Windows 브라우저 시각검증

`docs/TEST.md` §3 의 별도 Run 기록 참조 (visual_verification_scope: always — 웹 자산 변경).

### 미커버 (정직 표기)

- **라이브 회차 기록 미확인**: 배포 + 실제 답변 1건이 있어야 `redteam_review_rounds` 에 행이
  쌓인다. 배포 후 관측 경로 — `SELECT round_index, phase, verdict FROM
  agent_runtime.redteam_review_rounds WHERE review_id = (SELECT MAX(id) FROM
  agent_runtime.redteam_reviews) ORDER BY round_index, id`.
- **대화당 상한(20)의 실측 부하 미측정**: 리뷰가 20건을 넘는 장기 대화 표본이 아직 없다.
  상한 초과 시 `capped` 안내가 뜨는 경로는 단위 테스트로만 고정했다.
- **회차가 매우 많은 리뷰(14 라운드 등)의 렌더 부하**: 회차가 기본 접힘이라 DOM 은 summary
  수준으로만 늘지만, 실측은 라이브 표본 확보 후에 가능하다.
