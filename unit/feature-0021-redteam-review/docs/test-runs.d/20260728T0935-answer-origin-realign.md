---
run_at: 2026-07-28T18:35:00+09:00
session: ai/claude/feature-0021-answer-origin-realign
scope: 원 요청 재앵커 + 메타 프레이밍 탐지 + 내용 보존 재서술 1회 (answer-origin-realign, CHG-20260728-0002)
verdict: PASS
---

### Run 0 — 근본 원인 확정 (Environment: 코드 정적 추적, `agent_core.py` / `redteam.py`)

사용자 관측("추론·자가적대리뷰 완수 후 전달되는 답변이 처음 요청사항의 문맥보다 **직전 문맥**에
답변하는 뉘앙스")을 코드 경로로 환원했다. 추정이 아니라 메시지 배열의 실제 형태로 확정:

`_build_self_review_messages(messages, draft, instruction)` (agent_core.py) 는

```
base_messages   # system + 히스토리 + 원 사용자 질문 + 도구 결과
assistant: <초안>
user: "[내부 자가 검증] … 결함을 고친 최종 답변 전문을 다시 작성하라 … <<REVIEW_FINDINGS>>"
```

를 만든다. 즉 **모델의 생성 지점 최근접 turn 이 내부 리뷰 결함 목록**이다. 이 배치 자체는
2026-07-24 §9(prefill 회귀 방지)에서 의도적으로 고정한 불변식이라 바꾸지 않는다 — 지시를
trailing `system` 으로 되돌리면 초안이 Anthropic prefill 이 되어 미수정 전달 결함이 재발한다.

→ 원인은 "프롬프트 문구 부족"이 아니라 **recency 배치**다. 따라서 같은 지렛대를 반대로 쓰는
방향(원 요청을 지시의 맨 끝에 배치)을 채택. 재추론(rederive) 경로는 도구 결과 turn 이 추가로
쌓이므로 원 요청이 한층 더 멀어진다 — 동일 교정을 양 경로에 적용.

### Run 1 — red-team 단위 전량 (Environment: agent 이미지 격리 컨테이너, monkeypatch, DB/LLM 무의존)

- 명령: `sudo docker run --rm -v $(pwd):/work -w /work -e PYTHONDONTWRITEBYTECODE=1 \
  mysql-ai-agent:current … python -m pytest -q unit/feature-0002-agent-core/tests/test_redteam.py`
- 결과 **PASS**. 신규 20건 포함:
  - **재앵커 지시**: `test_revision_instruction_anchors_request_last` /
    `test_rederive_instruction_anchors_request_last` — findings 블록보다 **뒤**에 요청 블록이
    오는 순서를 인덱스로 고정(recency 계약이 코드로 박히게). PASS
  - **레거시 무회귀**: `test_revision_instruction_without_question_is_unchanged_shape` —
    인자 미지정 호출은 재앵커 없이 기존 형태 유지. PASS
  - **datamark**: `test_request_anchor_strips_forged_sentinel_breakout` — 사용자 발화에 심은
    `<<END_USER_REQUEST>>` 위조가 제거되어 구획을 빠져나갈 수 없고, 블록의 마지막 줄이 내부
    지시로 끝남을 확인. PASS
  - **누출 게이트**: `test_request_anchor_suppressed_goal_not_leaked` — caller 가 goal 을 빈
    값으로 넘기면 대화 목표가 실리지 않음. PASS
  - **탐지기**: `test_detect_meta_framing_catches_back_reference_openers`(7 케이스) /
    `_skips_leading_heading`(제목 뒤 은닉) / `_allows_normal_db_answer`(정상 DB 답변 3종) /
    `_allows_dml_description_opening`(오탐 가드 — "내용을 수정합니다") / `_empty_is_none`. PASS
  - **재서술 계약**: `test_realign_skips_when_no_meta_framing`(탐지 없으면 **호출 0**) /
    `_disabled_setting_passthrough`(스위치 OFF 시 호출 0) / `_applies_rewrite_and_passes_anchor`
    (앵커·"삭제하지 말 것" 문구 전달 확인) / `_rejects_content_loss`(60% 미만 폐기) /
    `_rejects_still_meta_rewrite` / `_fail_open_on_empty_and_exception` / `_no_rewrite_fn_is_noop`.
    PASS
  - **오케스트레이터 배선**: `test_orchestrate_threads_question_and_goal_into_instructions` —
    `question`/`thread_goal` 이 실제 수정 지시 본문에 실림. PASS

### Run 2 — 누출 게이트 회귀 (Environment: 동일 컨테이너, `test_self_review_messages.py`)

- 신규 3건: `_suppressed_for_bounded_sender`(True → `""`) / `_passthrough_for_unbounded_sender` /
  `_normalizes_empty`. **PASS**.
- 이 게이트가 본 cycle 의 유일한 신규 노출면이다 — `thread_goal` 은 대화의 (가려졌을 수 있는)
  첫 요청 파생이라 window 로 clip 불가하므로, system 프롬프트 CONVERSATION CONTEXT 와 동일
  조건에서 fail-closed 되어야 한다. 함수로 추출해 테스트로 고정했다(인라인 삼항이면 회귀 감지 불가).

### Run 3 — 전체 회귀 + 린트 (Environment: 동일 컨테이너)

- 대상: `unit/feature-0002-agent-core/tests` + `unit/feature-0003-agent-web-ui/tests` +
  `unit/feature-0023-conversation-api-access/tests`
- **baseline(main HEAD 44fe939d, 동일 컨테이너·동일 명령): 2791 passed, 2 skipped**
- **본 branch: 2814 passed, 2 skipped, 0 failed** → 순증 23건 = 신규 테스트 수와 일치,
  **회귀 0**. baseline 을 같은 방식으로 실측해 대조한 이유는 "전부 통과"가 기존 실패를 가릴 수
  있기 때문이다(수치 대조 없이는 무회귀를 주장할 수 없다).
- `ruff check unit/ shared/` — **All checks passed!**
- 마이그레이션 없음(alembic 무변경) → `migrate-lint` 대상 아님.

### 미커버 (정직 표기)

- **라이브 효과 측정 미수행**: 1차 재앵커가 실제 답변의 뉘앙스를 얼마나 교정하는지, 2차 재서술
  발동률이 얼마인지는 **배포 후 트래픽이 쌓여야** 관측 가능하다. 단위 테스트는 *계약*(순서·게이트·
  폐기 조건)을 고정할 뿐 LLM 산출물의 문체를 판정하지 못한다. 관측 경로는 stderr
  `[redteam] answer-realign …` 라인과 `_rt_meta.realign_*` 이며, 콘솔 노출은 후속 cycle
  (TASK.md §10 잔여 — DB 컬럼 신설 필요).
- **웹 자산 무변경**: static/template/html 변경 0 → PB-0008 시각검증 hard gate(check #13) 대상
  아님. 다만 신규 설정 행(`REDTEAM_ANSWER_REALIGN`)이 관리 콘솔 '설정 > AI 자가 리뷰' 에
  data-driven 으로 렌더되므로 POST-DEPLOY 에 그 행의 실제 표출을 확인한다(아래 Run 4).
