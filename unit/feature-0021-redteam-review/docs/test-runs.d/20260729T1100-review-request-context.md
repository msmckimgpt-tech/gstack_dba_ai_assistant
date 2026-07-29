---
run_at: 2026-07-29T11:00:00+09:00
session: ai/claude/feature-0021-review-request-context
scope: 다중 턴 요청 맥락 · 첨부 근거 · 앵커 2층 · 붕괴 가드 (review-request-context, CHG-20260729-0001)
verdict: PASS
---

### Run 0 — 라이브 근본원인 진단 (Environment: repo-postgres-1, `agent_runtime`)

사용자 리포트("처음 요청했던 '쿼리 리뷰'는 수행하지 않고 두 번째 대화의 '네 맞습니다.' 에만
정합하게 답변")를 **판정 원장으로** 환원했다. 증상만 보고 프롬프트를 더 손보는 것은 또 한 번의
증상 치료가 되므로(=CHG-20260728-0002 의 실수) 데이터를 먼저 읽었다.

**대화 `20260729013313-2211841a` 턴 구조** (`core_messages`):

| msg id | role | len | 내용 요지 |
|---|---|---|---|
| 5883 | user | 147 | "쿼리 리뷰를 진행해주세요. [DK] Delete_NotExists_AccountCharacter …" (+첨부 `.sql`) |
| 5901 | assistant | 488 | 코드 제공 요청(되물음) |
| 5903 | user | **7** | **"네 맞습니다."** |
| 5908 | assistant | **152** | **"감사합니다. … 상세 분석이 필요하시면 언제든 말씀해주세요."** |
| 5909 | user | 15 | "리뷰 진행 및 답변해주세요." (사용자가 같은 요청을 재차 눌러야 했다) |
| 5910 | assistant | 3170 | 정상 리뷰 |

**red-team 판정** (`redteam_reviews`):

| run | conv | verdict | rounds | stop | reasoning |
|---|---|---|---|---|---|
| 130 | …2211841a | revise | 3 | resolved | max |
| **132** | …2211841a | revise | **14** | **resolved** | max |
| 133 | …2211841a | revise | 2 | downgraded | max |

**모순이 원인을 가리켰다**: run #132 는 `rounds=14`, `stop=resolved`, `unresolved=0` — 원장상
"14 라운드 돌고 결함이 남지 않음" 인데 실제 산출물은 152자 비-답변이다. 즉 **축소가 수렴으로
기록**되고 있었다.

**findings 원문**(같은 행)이 그 이유를 그대로 담고 있었다 — 두 BLOCK 모두 구조적 false positive:

- `completeness` BLOCK — "USER QUESTION 필드에 **'네 맞습니다'만 있고** 사용자 코드 제공 없음.
  DRAFT ANSWER는 … 긴 리뷰 제공." → 리뷰어는 fresh-context 라 대화를 못 보고 **현재 턴 발화만**
  받는다. 후속 턴에 실질 답을 주는 정상 동작이 결함으로 판정된다.
- `honesty` BLOCK — "초안이 **사용자 제출 증거가 없는** SQL 코드에 대해 마치 검증된 분석인 것처럼
  제시함." → 첨부 본문은 knowledge context(**시스템 프롬프트**)로 주입되고 evidence digest 는
  **도구 실행만** 담는다. 첨부 리뷰마다 재발한다.

→ 원인 4축(D1 리뷰어 입력 / D2 앵커 권위 / D3 첨부 근거 부재 / D4 퇴행 경로) 확정. D1·D3 은
**기존 결함**이고 D2(2026-07-28 재앵커)가 그것을 답변 붕괴로 증폭했다.

### Run 1 — 회귀 재현 + 교정 단위 검증 (Environment: agent 이미지 격리 컨테이너, monkeypatch)

- 명령: `sudo docker run --rm -v $(pwd):/work -w /work -e PYTHONDONTWRITEBYTECODE=1 \
  mysql-ai-agent:current … python -m pytest -q unit/feature-0002-agent-core/tests/test_redteam.py \
  unit/feature-0002-agent-core/tests/test_self_review_messages.py`
- 결과 **PASS**. 신규 22건 — 라이브 실패를 그대로 재현하는 케이스 포함:
  - **붕괴 재현**: `test_collapse_guard_rejects_non_answer_revision` — 긴 리뷰 초안 +
    `completeness` BLOCK + 라이브와 동일한 붕괴 문자열("감사합니다. 상세 분석이 필요하시면 …")
    을 내는 revise_fn → 초안이 유지되고 `stop_reason=revise_collapsed`,
    `revision_applied=False`. **수정 전 코드에서는 이 테스트가 붕괴본을 채택해 실패한다**
    (가드가 결함 자체를 검증한다).
  - **정상 축소 무회귀**: `test_collapse_guard_allows_legitimate_shrink` — 50% 축소는 채택되고
    `resolved`. 가드가 정당한 근거 삭제까지 막지 않음을 고정.
  - **앵커 2층**: `..._separates_request_from_latest_utterance` — [이 대화의 요청]이
    [직전 사용자 발화]보다 **앞서고**, 후자에 "답변 범위가 아니다" 가 붙는다. 단일 턴은
    `..._single_layer_when_request_equals_question` 으로 중복 렌더 없음을 고정.
  - **계약 회귀 가드**: `test_answer_contract_forbids_scope_shrink` — "다룰 내용을 좁히지" ·
    "삭제하거나 요약해 줄이지 말 것" · "길이나 범위에 맞춰 답변을 축소하지 말 것" 존재 + 초판의
    축소 유발 문구("묻지 않은 것을 결함 수정을 빌미로")가 **사라졌는지** 를 함께 검사.
  - **리뷰어 입력**: `test_run_review_injects_conversation_request`(CONVERSATION REQUEST 가
    LATEST USER UTTERANCE 보다 앞), `..._omits_conversation_block_when_absent`(미지정 시 무주입),
    `test_review_prompt_forbids_scope_false_positive`(과답변 보고 금지 + "shorter answer is NOT a
    better answer" + REGRESSION 규칙).
  - **첨부 근거**: 매니페스트·발췌·절단 표기 + `..._includes_attachments_even_when_tools_are_huge`
    (도구 digest 40건으로 캡을 채워도 첨부 섹션이 살아남는 예산 선점 검증).
  - **누출 게이트**: `_review_conversation_request`/`_review_attachments` 가 bounded 발신자에
    대해 각각 `""`/`[]` (fail-closed), 폴백 순서(origin→goal→발화), 로더 예외 fail-open.

### Run 2 — 전체 회귀 + 린트 (Environment: 동일 컨테이너)

- **baseline(main HEAD, 동일 컨테이너·동일 명령): 2835 passed, 2 skipped**
- **본 branch: 2857 passed, 2 skipped, 0 failed** → 순증 22 = 신규 테스트 수, **회귀 0**.
- `ruff check unit/ shared/` — **All checks passed!**
- 마이그레이션 없음 — `stop_reason` 은 기존 text 컬럼이고 신규 값(`revise_collapsed`)만 추가된다.
  콘솔은 라벨 맵 1줄 추가(미지 값은 원문 그대로 표시되므로 라벨 없이도 깨지지 않는다).

### 미커버 (정직 표기)

- **라이브 재현 검증 미수행**: 같은 대화에서 턴2 를 다시 태워 붕괴가 사라지는지는 배포 후에만
  확인 가능하다. 단위 테스트는 붕괴 *경로*(가드·앵커·리뷰어 입력)를 고정할 뿐, 리뷰어 LLM 이
  실제로 과답변 BLOCK 을 더 이상 내지 않는지는 판정 표본이 필요하다.
- 관측 경로: `redteam_reviews` 의 `revision_rounds` 분포(14 같은 꼬리 소멸 여부)와
  `stop_reason='revise_collapsed'` 빈도. 후자가 잦으면 리뷰어가 여전히 축소를 유도한다는 신호다.
