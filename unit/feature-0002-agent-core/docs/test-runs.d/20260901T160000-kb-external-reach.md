---
run_at: 2026-09-01T16:00:00+09:00
session: ai/claude/kb-external-reach
scope: 지식베이스가 외부 AI 프롬프트에 실린다 — F1(get_task_context 확장)·F2(L0 통계 게이트 분리)·F4(전역 상속 4축)·F5(ENUM 판정 cross-scope) (20260901T160000-kb-external-reach)
verdict: PASS
---

### Run 1 — 대상 단위 (Environment: bare-runner pytest, 대역만 · 라이브 DB/LLM 무접촉)
- 명령: `PYTHONPATH=<f0002>/src:<f0003>/src:. python3 -m pytest -q unit/feature-0003-agent-web-ui/tests/test_kb_external_reach.py unit/feature-0002-agent-core/tests/test_priority_stats_collection.py unit/feature-0002-agent-core/tests/test_metadata_glossary_enum.py unit/feature-0002-agent-core/tests/test_glossary_term_tier.py`
- 결과 **PASS**
  - `test_kb_external_reach.py` **13 passed** — 층 조립(5층·축 분리)·product scope 를 task 에서만 해석·층별 fail-soft + 이름 있는 notes·번들 상한/절단 고지 · **배선 2건**(핸들러가 실제로 `_kb_grounding_sections` 를 부르고 결과를 번들에 싣는가 / focus 를 question 으로 넘기는가).
  - `test_priority_stats_collection.py` **7 passed** — 대상별 수집·규약 이탈 키 skip·knob off·ds 미해석·수집 예외 fail-soft·payload 카운터 초기화 · **배선 1건**(게이트로 `enqueue_change_analysis` 가 막혀도 수집은 일어난다).
  - `test_metadata_glossary_enum.py` **18 passed** — ENUM/테이블·컬럼 설명 목록의 전역 상속 노출(`inherited`·`inherited_count`).
  - `test_glossary_term_tier.py` **19 passed** — 용어 축 회귀 + ENUM 판정 cross-scope.

### Run 2 — 뮤테이션 실증 (§16.7 G11-b) (Environment: scratchpad 사본에 뮤턴트 적용, 소스 무손상)
- 방법: 정상 소스를 scratchpad 로 복제 → 뮤턴트 1종씩 적용 → **적용 여부를 파일 비교로 확인**
  → 테스트는 정본을 쓰고 코드만 뮤턴트. 총 14종 시행.
- 결과 **12 KILL + 등가 2종**

  | # | 뮤턴트 | 판정 |
  |---|---|---|
  | M1 | `get_task_context` 에서 `_kb_grounding_sections` 호출 삭제 | KILL |
  | M2 | 관계 층을 product 축 scope 로 조회 | KILL |
  | M3 | `_seed_coverage_targets` 에서 `_collect_priority_stats` 호출 삭제 | KILL |
  | M4 | ENUM 축 상속 노출 제거 | KILL |
  | M5* | ENUM 판정 이력을 자기 scope 로 완전 축소 | KILL |
  | M5′ | `_settled_enum_status` 내부 전역 보장선 제거 | KILL |
  | M6 | 제품 해소 **실패**를 「제품 없음」과 동일 취급 | KILL |
  | M7 | 상속분 조회 실패를 빈 목록으로 접기 | KILL |
  | M8 | 안내 분기를 `not sections and not notes` 로 원복 | KILL |
  | M9 | 계측을 `finally` → 성공 경로로 되돌림 | KILL |
  | M10 | scope 목록 dedup 제거 | KILL |
  | M11 | 제품 축 3층을 ds scope 로 조회 | KILL |
  | (등가) | 호출부가 `GLOBAL_SCOPE` 미전달 | 동작 불변 — 헬퍼 보장선이 되메움 |
  | (등가) | dedup 이 전역을 걸러냄 | 동작 불변 — 〃 |

- ⚠ **1차 라운드에서 M1·M3 이 생존했다**. 테스트가 헬퍼를 **직접** 호출해 검사했기 때문에
  「헬퍼는 옳은데 아무도 부르지 않는 상태」를 통과시켰고, 그 상태가 정확히 이 cycle 이 고치는
  결함이다. 진입점을 구동하는 배선 테스트 3건을 추가해 해소.
- ⚠ **등가 뮤턴트 2건을 처음엔 테스트 구멍으로 오독했다**. 생존을 보고 곧바로 테스트를 늘리는
  대신, 그 뮤턴트가 **관측 가능한 동작을 바꾸는지**를 먼저 확인했어야 한다. 실제 계약은 두
  지점을 함께 지운 M5* 가, 보장선 자체는 헬퍼를 직접 부르는 M5′ 가 검사한다.

### Run 3 — 컨테이너 전건 (Environment: `COMPOSE_PROJECT_NAME=repo make test`, worktree 에 `.env*` 복사)
- 결과 **PASS — rc=0 · FAILED 0 · 6,672 tests · ruff `All checks passed!`**
- 이 게이트가 **로컬 대상 실행이 못 잡은 실패 2건**을 잡았다:
  `test_kb_enum_feedback.py::test_enum_auto_promote_skips_{rejected,already_promoted}` —
  `_settled_enum_status` 가 반환을 `status` → `(status, scope_key)` 로 넓히면서 기존 1-tuple
  스크립트가 IndexError. 계약 확장에 맞춰 갱신 + 교차 scope 조회 자체를 검사하는 테스트 추가.

### Run 4 — 독립 채널 적대 리뷰 (codex) — **미수행**
- `codex exec --sandbox read-only` 시도 → `ERROR: You've hit your usage limit ... try again at
  3:44 PM` (2026-09-01 14:35 KST). ⚠ **프로세스 exit 는 0** 이라 출력을 안 읽었으면 「리뷰 통과」로
  오독할 수 있었다.
- 대체: 자체 적대 검증(위 결함 7건 적발·해소). 한계는 REVIEW §4 에 명시.
- 후속: 한도 해제 후 같은 diff 를 codex 에 재투입.

### Run 5 — POST-DEPLOY 라이브 (PB-0008) — 배포 후 기록
