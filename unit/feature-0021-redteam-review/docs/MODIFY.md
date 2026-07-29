---
doc_type: MODIFY
feature_id: feature-0021-redteam-review
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260715-0001
- Date: 2026-07-15
- Related Requirement: REQ-20260715T140000-redteam-selfreview · REQ-20260715T140001-orchestration ·
  REQ-20260715T140002-memory-notes · REQ-20260715T140003-console-visibility
- Summary: assistant 자가 적대(red-team) 리뷰 + 오케스트레이션 + [세션, 제품] 메모리 노트 +
  지침/스킬 레지스트리 관리 콘솔 조회 최초 구현 (Claude Code 추론 패턴 이식 — fresh-context
  find→verify, effort scaling, auto-memory, progressive disclosure)
- Files:
  - `unit/feature-0002-agent-core/src/modules/redteam.py` (신규 — 리뷰어 프롬프트·게이트·
    오케스트레이터·판정 저장)
  - `unit/feature-0002-agent-core/src/modules/agent_notes.py` (신규 — 세션/제품 노트
    기록·주입·TTL sweep)
  - `unit/feature-0002-agent-core/src/modules/guidance_registry.py` (신규 — 지침/스킬 메타
    레지스트리, 코드 상수 lazy 참조)
  - `unit/feature-0002-agent-core/src/agent_core.py` (choke-point 훅 — `result["answer"]` 확정
    직후 리뷰 오케스트레이션 + 노트 갱신; 프롬프트 조립에 노트 주입 — bounded 발신자 억제)
  - `unit/feature-0002-agent-core/src/modules/ask.py` (reaper cadence 에 노트 TTL sweep 추가)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (`_openai_chat_completion_with_deadline`
    에 conversation_id/run_id 명시 귀속 인자 additive)
  - `unit/feature-0002-agent-core/alembic/versions/20260715_0042_redteam_reviews.py` (신규 —
    `agent_runtime.redteam_reviews` + GRANT rw/ro)
  - `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` (fresh deploy 정합 —
    동일 테이블 CREATE)
  - `shared/runtime_settings.py` (REDTEAM_* 8 spec + redteam 그룹 serialize)
  - `unit/feature-0003-agent-web-ui/src/web_context.py` (권한 `console.reasoning.read` 정의 +
    admin catchup + `_CONSOLE_CATEGORY_ACCESS_LEAVES` system 카테고리 편입)
  - `unit/feature-0003-agent-web-ui/src/routers/admin_reasoning.py` (신규 — guidance/redteam/
    notes 3 read-only endpoint, INCLUDE_ORDER=240)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (AI 추론 탭·pane + 설정 "AI 자가
    리뷰" list-row/article)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (탭 게이트/종속 트리/switchTab/렌더러 +
    설정 redteam 패널 + rerender 배선)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (reasoning pane 스크롤 + reasoning-* 스타일)
  - `unit/feature-0002-agent-core/tests/test_redteam.py`,
    `unit/feature-0002-agent-core/tests/test_agent_notes.py`,
    `unit/feature-0003-agent-web-ui/tests/test_admin_reasoning.py` (신규 단위 테스트)
  - `docs/ROUTEMAP.md` (재생성 — admin_reasoning 3 route)
- Impact: 리뷰 활성(기본 ON, 일반 강도 이상) 시 답변당 haiku 급 리뷰 호출 1회(+BLOCK 시 수정
  1회, 높음+ 재검증 1회) 추가 — 외부 비용 발생(Major). REDTEAM_ENABLED=0 또는 낮음 강도면
  기존 경로와 동치(리뷰 LLM 호출 0). 마이그레이션은 순수 additive.
- Rollback Notes: 런타임 설정 REDTEAM_ENABLED=0 + REDTEAM_NOTES_ENABLED=0 으로 즉시 무효화
  (재배포 불필요). 완전 롤백은 커밋 revert + alembic downgrade 0041 (redteam_reviews DROP —
  판정 이력 소실 허용).

## CHG-20260715-0002
- Date: 2026-07-15
- Related Requirement: (거버넌스 정합 — cycle-final 게이트)
- Summary: cycle-final verify-completion CHECK#7 정합 — ANCHOR.md §4 주석 예시(`### 2026-04-24`
  헤더)가 grace 만료 상태에서 malformed human entry 로 오판되던 것 해소(주석 제거·placeholder
  단일화) + created_at 실 UTC 정합. 근인: `cp -r unit/_template` 복제로 git `--follow` 가
  ANCHOR.md 를 템플릿 rename 으로 추적 → canonical_at=템플릿 최초 커밋(4월) → 24h grace 만료.
- Files: `unit/feature-0021-redteam-review/docs/ANCHOR.md`
- Impact: 문서 전용 (거버넌스 게이트 통과). 코드/동작 무변경.
- Rollback Notes: 불요 (문서).

## CHG-20260716-0003
- Date: 2026-07-16
- Related Requirement: REQ-20260716-console-ia (사용자 요청 — 관리 콘솔 IA 재구성)
- Summary: 단일 '설정 > AI 추론' 탭(4섹션)을 관측/설정 성격별로 분리 —
  ① **감사 > AI 추론**(신규 위치): 자가 적대 리뷰 활동 + 메모리 노트 현황(관측·감사 데이터).
  ② **설정 > 프롬프트 그룹**: [전역 시스템 프롬프트(편집) / 작동 지침(조회) / 스킬(조회)] 통합.
  ③ 설정 > 운영 값 > AI 자가 리뷰(REDTEAM_* 설정): 무변경.
  전역 시스템 프롬프트 비교·검토 결과: 기본 시스템 프롬프트 fallback(system-prompt-base)은
  전역 시스템 프롬프트와 중복이라 작동 지침 목록에서 제외(편집 정본 단일화).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (AI 추론 탭 감사 그룹 이동·pane 리뷰/노트만·
    설정 프롬프트 그룹에 작동 지침/스킬 항목+article)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (권한 맵 감사 재배치·loadReasoning/renderReasoning
    지침·스킬 섹션 제거·설정 mountGuidanceRegistryPanel(guidance/skills)·showGuidanceDetail detailId 파라미터화)
  - `unit/feature-0003-agent-web-ui/src/routers/admin_reasoning.py` (guidance 권한 console.reasoning.read
    → system_prompt.global.read·?kind 필터)
  - `unit/feature-0003-agent-web-ui/src/web_context.py` (console.reasoning.read 감사 카테고리 재배치·
    라벨/설명 감사 성격, group audit)
  - `unit/feature-0002-agent-core/src/modules/guidance_registry.py` (system-prompt-base 항목 제외)
  - `unit/feature-0003-agent-web-ui/tests/test_admin_reasoning.py` (권한 분리·kind 필터·fallback 제외 테스트)
  - `docs/ROUTEMAP.md` (guidance 권한 재생성)
- Impact: UI/IA 재배치 + 권한 카테고리 재배치(read-only, 비파괴). 백엔드 엔드포인트·데이터 무변경.
  기존 admin catchup 은 권한 자체가 동일해 재backfill 불요(카테고리 매핑만 변경).
- Rollback Notes: 커밋 revert. 데이터/마이그레이션 영향 없음.

## CHG-20260716-0004
- Date: 2026-07-16
- Related Requirement: REQ-20260716-console-subtabs (사용자 요청 — 비슷한 구성을 탭으로 묶기)
- Summary: 관리 콘솔에서 유사 성격 항목을 서브탭으로 통합 —
  ① **감사 그룹**: LLM 사용량·AI 운영 현황·AI 추론 3개 최상위 탭 → **'AI 운영 현황' 단일 탭
     (data-admin-tab=ai-console)** + 서브탭 [LLM 사용량 | 운영 현황 | 추론]. 탭 게이트는 3 조회
     권한 OR, 서브탭은 각자 권한 게이팅(initAiConsoleSubtabs).
  ② **설정 > 프롬프트**: list 3항목(전역/지침/스킬) → **단일 '프롬프트' 항목** + detail 서브탭
     [전역 시스템 프롬프트 | 작동 지침 | 스킬] (mountPromptsPanel).
  재사용 서브탭 헬퍼 `bindPaneSubtabs(root, attr, onActivate, {visibleKeys})` 신설(양쪽 공용).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (nav 3탭→1탭·pane 3개→통합 서브탭 pane·
    설정 list 3행→1행·detail 3 article→1 article 서브탭)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (bindPaneSubtabs·initAiConsoleSubtabs·
    mountPromptsPanel·switchTab ai-console 분기·ADMIN_TAB_PERMISSIONS ai-console OR·CATEGORY_ACCESS·
    SETTINGS_PANEL_MOUNTERS prompts·activeTab prompts)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (범용 .admin-subtabs/.admin-subtab/.admin-subpane)
- Impact: UI/IA 통합(프론트 전용). 백엔드 엔드포인트·권한 카탈로그·데이터 무변경. 권한 자체 불변
  (탭 키만 admin.js 에서 통합). ROUTEMAP 무변경. 서브탭 권한 게이팅으로 기존 접근성 보존.
- Rollback Notes: 커밋 revert (프론트 전용, 데이터 영향 없음).

## CHG-20260716-0005
- Date: 2026-07-16
- Related Requirement: REQ-20260716-subtab-sticky (사용자 요청 — 서브탭 화면 상단 sticky)
- Summary: 서브탭 바(.admin-subtabs)를 스크롤 시 스크롤 컨테이너 상단에 sticky 고정.
  'AI 운영 현황'(ai-console pane, overflow-y:auto)·설정 '프롬프트'(detail-col, overflow-y:auto)
  양쪽 서브탭 바가 하위 콘텐츠 스크롤 시 상단에 남는다. 불투명 배경(설정=--surface, ai-console
  pane=--bg 오버라이드) + z-index:6 으로 아래 차트·표를 덮는다.
- Files: `unit/feature-0003-agent-web-ui/src/static/styles.css` (.admin-subtabs position:sticky)
- Impact: CSS 전용. 마크업·JS·백엔드 무변경. 서브탭 바가 스크롤 중에도 접근 가능.
- Rollback Notes: 커밋 revert (CSS 전용).

## CHG-20260722-0001
- Date: 2026-07-22
- Related Requirement: 사용자 요청 (entry arg-given dispatch, 2026-07-22) — 관리 콘솔
  "AI 운영 현황 > 추론"의 "리뷰 실패" 가 내부 에러인지 의도인지 검토 + 에러면 수정.
- Summary: **진단** — "리뷰 실패"(verdict=`error`)는 리뷰어 LLM 호출이 `None` 을 반환할 때만
  기록되는 값이고, 라이브 DB 실측 결과 verdict='error' 8건 **전부 latency 25001~25039ms**
  (24000ms 미만 fast-fail 0건) = **100% 타임아웃**. 근본 원인은 리뷰어 alias
  `claude-haiku-4-chat` 의 고정 extended thinking(budget_tokens=5000)으로 인한 상시 20~25s
  지연(정상 통과도 median ~18.6s). 표시/기록/fail-open 은 **의도된 설계**(버그 아님)이나
  실패율 ~17%(8/47)는 **운영 결함**. **수정(사용자 결정)** — 운영자가 관리 콘솔 '설정 > AI
  자가 리뷰'에서 튜닝하도록 리뷰어 토큰 할당량(`REDTEAM_MAX_TOKENS`) 런타임 설정 신설.
  타임아웃(`REDTEAM_TIMEOUT_SEC`)은 기존 노출 — 설명만 보강.
- Files:
  - `shared/runtime_settings.py` (`_REDTEAM_SPECS` 에 `REDTEAM_MAX_TOKENS` 추가 — category
    "자가 리뷰", default 8192·minimum 6000(리뷰어 thinking 5000 floor 상회 보장)·maximum
    32000·apply_mode live; `REDTEAM_TIMEOUT_SEC` description 에 "리뷰 실패=타임아웃" 안내 보강)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (`_openai_chat_completion_with_deadline`
    에 `max_tokens_override` 인자 additive — 양수면 task 별 카탈로그 cap 대신 사용, None/0 이면
    종전대로 `_max_tokens_kwargs`)
  - `unit/feature-0002-agent-core/src/modules/redteam.py` (`_review_max_tokens()` 헬퍼 신설 +
    `run_review` 가 `REDTEAM_MAX_TOKENS` 를 `max_tokens_override` 로 전달)
  - `unit/feature-0002-agent-core/tests/test_redteam.py` (신규 5건 — `_review_max_tokens`
    read/0-fallback/error 3 + `run_review` override 전달·미설정 None 2)
- Impact: **프론트 무변경** — 설정 패널(`renderRedteamReviewSettings`)이 `data.redteam` 그룹을
  data-driven 자동 렌더하므로 새 spec 이 자동 노출. 하위호환: override 미설정(0) 시 기존
  8192 task cap 과 byte-동치. 배포 대상 = web(설정 직렬화) + worker/ask-worker(리뷰어 호출).
- Rollback Notes: 커밋 revert. 런타임 override 는 콘솔에서 초기화(기본 8192) 가능 — 코드 롤백 없이도 무력화.
## CHG-20260724-0001
- Date: 2026-07-24
- Related Requirement: 사용자 요청 (entry arg-given dispatch, 2026-07-24) — "서비스 assistant
  답변 마무리 red-team 리뷰 시 각 선택된 모델에 정합하게 red-team 모델도 실행. 현재는 항상 haiku 추정."
- Summary: **정합 매핑** — red-team 리뷰어 모델이 이전엔 항상 `claude-haiku-4-chat` 고정
  (`REDTEAM_MODEL` 상수·`AGENT_REDTEAM_MODEL` env 미설정)이라, sonnet 답변을 haiku 리뷰어가
  검증하는 tier 불일치가 있었다. 이제 리뷰어 모델을 **답변 모델에 정합**하게 도출한다
  (`resolve_review_model`: `conversation_answer_model` 재사용 — claude-haiku-4→-chat,
  claude-sonnet-4→-chat). `AGENT_REDTEAM_MODEL` env 설정 시 그 값으로 hard-pin(비용 통제
  escape hatch 보존). **필수 호환 수정 2건**: (1) sonnet(adaptive/frontier) 리뷰어는 OAuth
  토큰으로 나갈 때 첫 system 블록이 Claude Code identity 여야 429 를 안 맞으므로
  `run_review` 가 `requires_oauth_frontier_identity` 시 `OAUTH_FRONTIER_IDENTITY` 를 첫 블록
  주입(`_call_llm` cc-identity-inject 미러) — 없으면 sonnet 리뷰가 조용히 skip. (2) 적대 패널
  MAJOR — sonnet-high 리뷰어는 `REDTEAM_TIMEOUT_SEC`(25s) 안에 못 끝내 timeout→error→리뷰 skip
  (CHG-20260722-0001 이 haiku 에서 8/8 100% 타임아웃으로 이미 관측) + max_tokens 안 thinking 이
  JSON truncate. adaptive 리뷰어에 `output_config.effort=low` 주입(짧은 JSON 판정엔 high 낭비)해
  지연·truncation·비용 동시 완화(모델 tier 정합은 유지). `redteam_reviews.model`/meta 는 실제
  리뷰어 모델 기록(admin 'AI 추론' 탭 관측 정합).
- Files:
  - `unit/feature-0002-agent-core/src/modules/redteam.py` (`resolve_review_model` 신설 +
    `_REDTEAM_MODEL_PIN`/`REDTEAM_MODEL_DEFAULT` 분리 + `_REDTEAM_ADAPTIVE_EFFORT`; `run_review`
    에 `model` 인자·identity 주입·adaptive effort extra_body; `orchestrate_review` 에
    `answer_model` 인자 + review_model 을 find/verify/record/meta 전 경로 스레딩)
  - `unit/feature-0002-agent-core/src/agent_core.py` (choke-point `orchestrate_review(...,
    answer_model=model)` — model = 대화별 사용자 선택 모델, ask.py payload)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (`_openai_chat_completion_with_deadline`
    에 `extra_body` 인자 additive — adaptive 리뷰어 effort 주입 채널, 미전달이면 무변경)
  - `shared/runtime_settings.py` (`REDTEAM_MAX_TOKENS` description 정정 — 리뷰어가 답변 모델에
    정합·sonnet adaptive effort=low 반영, MINOR doc-drift)
  - `unit/feature-0002-agent-core/tests/test_redteam.py` (신규 9건 — resolve 매핑·폴백·env pin 3,
    identity 주입 sonnet/haiku 2, effort 주입 sonnet/haiku 2, orchestrate 스레딩·기본 2)
- Impact: **프론트 무변경**. 하위호환: `answer_model` 미지정(레거시/테스트) 시 기존 haiku-chat
  동작 유지, `extra_body` 미전달 시 llm 호출 무변경, `REDTEAM_MODEL` 상수 보존. `redteam_reviews.model`
  VARCHAR(128) 은 새 alias(≤20자) 수용. 배포 대상 = worker/ask-worker(리뷰어 호출) + web(설정 설명).
  **비용/지연**: sonnet 대화 리뷰가 haiku→sonnet(effort=low). haiku 대화 무변경. `AGENT_REDTEAM_MODEL`
  env pin 으로 전량 haiku 강제 가능.
- Rollback Notes: 커밋 revert. 또는 `AGENT_REDTEAM_MODEL=claude-haiku-4-chat` env 로 코드 롤백 없이
  종전 동작(전량 haiku) 복원. effort 는 `AGENT_REDTEAM_EFFORT` env 로 조정.
## CHG-20260724-0002
- Date: 2026-07-24
- Related Requirement: 사용자 요청 (entry arg-given dispatch, 2026-07-24) — assistant 대화에서
  red-team 리뷰가 BLOCK 을 검출·수정 대상 확인했으나 관리 콘솔 '감사 > AI 운영 현황 > 추론'
  에서 **결함 미수정 상태로 답변 전달**됨. 대화 추적하여 근본 원인 파악 후 수정.
- Summary: **근본 원인 (라이브 추적·확증)** — red-team revise/rederive 재프롬프트가 수정 지시를
  초안(assistant turn) 뒤에 **`role: system` 메시지로 append**. LiteLLM/Anthropic 어댑터가
  trailing system 을 top-level `system` 파라미터로 hoist → 초안 assistant 가 배열의 마지막
  turn = **Anthropic prefill** 이 되어 모델이 재작성 대신 초안을 *이어쓰기* 시도. 완결된
  프로덕션 초안은 이어쓸 게 없어 ~빈 응답을 내고, 호출부가 None→**fail-open 으로 미수정 초안을
  그대로 전달**. 콘솔 '추론' 탭은 이를 정확히 표시(③ 결함 수정 '미적용', ⑤ '답변 전달')한 것 —
  **콘솔 정상, 전달 파이프라인 결함**. 라이브 실측: `agent_runtime.redteam_reviews` verdict='revise'
  42건 중 **35건(83%) revision_applied=false** (매일 일관); 실패 run 의 revise LLM 호출은 전부
  `llm_usage.completion_tokens=3`(사실상 빈 응답). 동일 gateway·모델 재현: trailing system →
  출력이 `\n---\n**자가 검증 통과 후 수정된 답변:**...` 로 시작(초안 이어쓴 prefill·리뷰 과정
  누설), trailing user → 완결된 재작성. **수정** — 지시 메시지 `role: system` → `role: user`
  (코드베이스의 기존 empty-answer 재요청 패턴과 정합; user 는 system 보다 낮은 권한 채널이라
  인젝션 승격 위험도 하락, 무회귀). 메시지 조립을 단일 불변식 헬퍼로 추출해 회귀 고정.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py` (`_build_self_review_messages` 헬퍼 신설 —
    지시를 **trailing user turn** 으로 두는 불변식 + 결함 기전 docstring; `_rt_revise`·`_rt_rederive`
    두 closure 가 기존 인라인 `messages + [assistant, system]` 대신 헬퍼 사용 + closure 가 stale
    outer `answer` 대신 orchestrate 가 넘긴 `draft` 인자 사용)
  - `unit/feature-0002-agent-core/src/modules/redteam.py` (적대 리뷰 WARN 반영 — `orchestrate_review`
    가 revise_fn/rederive_fn 을 `(instruction, draft=final_answer)` 로 호출: 다회 수정
    (REDTEAM_MAX_REVISIONS=2, 높음/매우높음)에서 2회차가 원 초안이 아닌 직전 수정본을 앵커로 받게
    해 stale-draft 오앵커링 차단. 콜백 계약 v2 — 타입힌트 `Callable[[str,str],...]` + docstring)
  - `unit/feature-0002-agent-core/tests/test_self_review_messages.py` (신규 3건 — 지시=trailing
    user turn·system 회귀 가드·base 무변형/보존)
  - `unit/feature-0002-agent-core/tests/test_redteam.py` (콜백 2-arg 계약 반영 + 다회 수정 draft
    앵커링 assert 강화 — `drafts_seen == ["draft","revised-1"]`)
- Impact: **프론트 무변경**. 배포 대상 = worker/ask-worker(답변 파이프라인 = revise/rederive 실행
  경로) + web(동일 이미지). 하위호환: 메시지 구조만 교정 — API·스키마·설정 무변경. 수정 후
  revise 가 정상 동작하면 BLOCK 검출 대화의 답변이 실제로 재작성되어 전달됨(의도된 동작 복원).
- Rollback Notes: 커밋 revert. 런타임 즉시 무력화가 필요하면 콘솔 '설정 > AI 자가 리뷰'에서
  `REDTEAM_MAX_REVISIONS=0`(기록만·수정 안 함) 또는 `REDTEAM_ENABLED=0` 로 리뷰 자체 중지 가능.

## CHG-20260727-0001
- Date: 2026-07-27
- Related Requirement: REQ-20260727-converge-until-resolved, REQ-20260727-reviewer-memory
- Summary: **결함 해소까지 반복 검증 + 리뷰어 대화 내부 맥락 기억**. 사용자 리포트("warning·block
  이 있어도 항상 한 번의 검증 후 답변 도출")를 라이브 판정 데이터로 진단해 세 원인을 분리하고,
  그중 실제 결함 두 가지를 수정했다.
  - **진단 (prefill fix 726c2f1e 배포 = 07-24 16:17 이후 표본)**: 매우높음 7건 전부 BLOCK 검출 →
    6건 수정 → 6건 재검증 → **4건이 재검증에서도 'revise'(결함 잔존)인 채 전달**. 일반 강도 3건은
    수정 2건 / 재검증 **0건**. 누적으로는 일반 강도 revise 37건 중 재검증 0건.
  - 원인① WARN 무조치 = 설계 의도 (BLOCK 만 수정 유발, `_sanitize_findings` verdict 규약) — 유지.
  - 원인② 일반 강도 재검증 없음 (`verify_pass = ordinal >= 2`) → `REDTEAM_VERIFY_MIN_LEVEL`
    (기본 0 = 모든 강도)로 일반화. 기본 강도 대화의 수정본이 무검증 전달되던 공백 해소.
  - 원인③ `REDTEAM_MAX_REVISIONS=1` 상한 → `REDTEAM_REVISE_UNTIL_RESOLVED`(기본 1)로 상한 제거,
    결함이 해소될 때까지 수정→재검증 반복. 탈출구: 사용자 '즉시 답변'/취소(`abort_fn`, 매 라운드
    확인), 무진전(수정본 동일성), 하드 백스톱(기본 50), 수정 무산출, 재검증 실패.
  - **관측**: `stop_reason`·`unresolved_block_count`·`revision_rounds`·`verify_findings` 를 신규
    기록(alembic 0045). 콘솔 타임라인 ⑤가 결함 잔존 시 "개선된 답변 전달"로 포장하지 않고
    "결함 잔존 상태로 전달 — BLOCK N건 미해소 (사유)"로 표시. 답변 말미 정직성 고지
    (`REDTEAM_UNRESOLVED_NOTICE`).
  - **리뷰어 기억**: 리뷰어가 (a) 현재 답변의 라운드 이력(자기 findings + assistant 수정본 발췌),
    (b) 같은 `conversation_id` 의 직전 판정(`REDTEAM_HISTORY_CONV_LIMIT`, 기본 3)을 이어받는다.
    프롬프트에 "해소 여부 먼저 판정 / 이미 고친 것 재보고 금지 / 여러 라운드 생존한 결함은 WARN
    강등" 규칙 추가 — 무제한 반복의 수렴 조건이자 사용자 요청 사항. fresh-context 불변식 유지
    (초안 생성 대화는 여전히 비전달), 대화 격리 유지(다른 대화 미포함, cid 없으면 미조회).
  - 진행 표시: 라운드마다 activity 방출(`progress_fn`) — "검증 1회"로 보이던 UX 오인 해소.
- Files:
  - `unit/feature-0002-agent-core/src/modules/redteam.py` (review_plan 게이트 일반화·수렴 루프·
    abort/progress 콜백·리뷰 기억 조립·미해소 고지·record_review 확장)
  - `unit/feature-0002-agent-core/src/agent_core.py` (`_rt_abort` 즉시답변/취소 배선 +
    `progress_fn=_emit_activity`)
  - `shared/runtime_settings.py` (REDTEAM_REVISE_UNTIL_RESOLVED / REDTEAM_VERIFY_MIN_LEVEL /
    REDTEAM_HISTORY_CONV_LIMIT / REDTEAM_UNRESOLVED_NOTICE 신규 4 spec + MAX_REVISIONS 상한 10)
  - `unit/feature-0002-agent-core/alembic/versions/20260727_0045_redteam_convergence_columns.py`
    (신규 — verify_findings/unresolved_block_count/revision_rounds/stop_reason, additive)
  - `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt`
  - `unit/feature-0003-agent-web-ui/src/routers/admin_reasoning.py` (0045 컬럼 stale-image 폴백
    SELECT + unresolved_7d/revision_rounds_7d 요약)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (stop_reason 라벨·타임라인 ④⑤ 정직화·
    미해소 지적 블록·통계 타일)
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (reasoning-stat--warn / reasoning-unresolved)
  - `unit/feature-0002-agent-core/tests/test_redteam.py` (신규 21건 — 수렴·abort·무진전·백스톱·
    고지·관측 기록·리뷰어 기억·격리)
- Impact: BLOCK 이 검출된 답변에서 수정→재검증이 결함 해소까지 반복되므로 **해당 답변의 지연과
  LLM 비용이 라운드 수에 비례해 증가**한다 (사용자 결정: 신뢰성 최우선, 시간 상한 없음).
  BLOCK 미검출 답변(라이브 표본 다수)은 기존과 동일하게 리뷰 1패스. 일반 강도는 수정이 발생한
  경우에만 재검증 1회가 추가된다. 급증 시 `REDTEAM_REVISE_UNTIL_RESOLVED=0`(상한 복귀) 또는
  `REDTEAM_MAX_REVISIONS=0`(수정 차단)으로 즉시 되돌릴 수 있다. 마이그레이션은 순수 additive.
- Rollback Notes: 런타임 설정으로 무재배포 롤백 — `REDTEAM_REVISE_UNTIL_RESOLVED=0` +
  `REDTEAM_VERIFY_MIN_LEVEL=2` 면 이전 동작(높음+ 만 재검증, 상한 1)과 동치. 완전 롤백은 커밋
  revert + alembic downgrade 0044.

## CHG-20260727-0002
- Date: 2026-07-27
- Related Requirement: REQ-20260727-converge-until-resolved, REQ-20260727-reviewer-memory
  (CHG-20260727-0001 의 in-cycle 보강)
- Summary: §18.8 적대 검증 패널(2 렌즈 병렬) 지적 **BLOCKING 4 · MAJOR 6 · MINOR 6 전건 반영**.
  상세 근거·대안은 REV-20260727T174500-converge-panel.
  - **격리**: `recent_conversation_reviews` 가 `has_restricted_members=true` 대화(공유창 window
    격리 대상)에서는 조회 자체를 skip — 가려진 구간 리뷰가 bounded 멤버의 답변 컨텍스트로 유입되던
    5번째 LLM 도달 경로 봉인 (SECURITY §21, fail-closed).
  - **수렴**: 리뷰 기억 블록이 라운드 이력에 예산을 선점하도록 재구성(최근 3라운드·발췌 300자) —
    cap 포화 시 최신 라운드가 먼저 잘려 수렴 장치가 무력화되던 결함 해소. rederive 근거를
    라운드마다 교체하지 않고 누적(`accumulated_steps`).
  - **탈출구**: 메인 루프가 소비한 '즉시 답변' 신호를 run 스코프 `_finalize_seen` 으로 red-team
    abort 판정까지 전달 + rederive 내부 루프에도 finalize 확인 + abort 확인 연속 실패 시 종료.
  - **인젝션**: 기억 블록을 `<<REVIEW_MEMORY>>` fence 로 구획 + `_flatten_untrusted`(sentinel
    strip + 개행 접기)로 줄 위조 차단. permission 축 WARN 강등 금지를 리뷰어 지침에 명시.
  - **정직성**: `MAX_REVISIONS=0`(차단 스위치)·`unverified`(미검증) 경로에서 미해소 단정·고지
    금지. BLOCK→WARN 강등은 `stop_reason="downgraded"` 로 구분해 '해소'로 위조하지 않음.
  - **추적성**: 폐기(무진전) 라운드의 rederive 도구가 화면 step·`executed_sql` 에 새지 않도록
    caller 계약을 `meta["rederive_steps"]`(채택분만)로 변경.
  - **운영**: `REDTEAM_WALL_BUDGET_SEC`(기본 0=무제한) 안전판 추가 — 반복이 ask-worker 슬롯을
    점유해 다른 사용자 대기가 길어질 때 운영자가 켠다. `_HARD_ROUND_BACKSTOP` env 파싱을
    try/except 로 감싸 오타가 red-team·노트를 무로그 비활성화하지 않게 함.
  - 기타: `%s::text` 캐스팅(PG 파라미터 타입 결정 실패 선례), 고지 멱등을 플래그 기반으로,
    `agent_notes` 의 "1회 수정" 하드코딩 → 실제 라운드 수, 콘솔 `verify_findings` 폴백.
- Files: `redteam.py`, `agent_core.py`, `modules/agent_notes.py`, `shared/runtime_settings.py`,
  `routers/admin_reasoning.py` 무변경, `static/admin.js`, `tests/test_redteam.py`(회귀 잠금 14건 추가)
- Impact: CHG-20260727-0001 의 동작 계약은 유지하되 격리·수렴·정직성 결함을 제거. 공유창 window
  격리 대화에서는 리뷰어 대화 기억이 동작하지 않는다(의도된 fail-closed).
- Rollback Notes: CHG-20260727-0001 과 동일 (런타임 설정 무재배포 롤백).

## CHG-20260727-0003
- Date: 2026-07-27
- Related Requirement: REQ-20260727-converge-until-resolved, REQ-20260727-reviewer-memory
  (CHG-20260727-0001 / -0002 의 POST-DEPLOY 검증 기록 — **docs-only, 코드 무변경**)
- Summary: PR #957 배포분에 대해 test-runs.d 가 "배포 후 필수"로 남겨둔 라이브 검증 3건을
  수행하고 결과를 정본에 반영.
  - **마이그레이션**: 라이브 `alembic_version=0045_redteam_convergence_columns`, 0045 컬럼
    4개 실재 확인.
  - **격리 fail-closed**: `recent_conversation_reviews` 를 라이브 ask-worker 에서 직접 호출해
    4케이스 인과표 확보 — 동일 임시 대화의 `has_restricted_members` 플래그만 TRUE↔FALSE 로
    토글했을 때 조회 0건↔1건으로 갈리는 것을 확인(게이트가 유일 원인). 단위 테스트가 커버할 수
    없던 라이브 PG 경로.
  - **PB-0008 콘솔**: '결함 잔존 전달 (7d)' 타일 · 타임라인 ③"수정 N회 반복"/④"재검증에서 결함
    잔존"/⑤"결함 잔존 상태로 전달 …(stop_reason 한글 라벨)" · "재검증에서 해소되지 않은 지적"
    앰버 블록 · 설정 패널 신규 5항목 렌더를 실 Windows 브라우저로 육안 검증.
- Files: `docs/TEST.md`(§3 POST-DEPLOY Run append + §4 미커버 명시),
  `docs/test-runs.d/20260727T1600-converge-until-resolved.md`(잔여 3건 해소 + Run 6),
  `docs/TASK.md`, `docs/REPORT.md`, `docs/REVIEW.md`, `docs/MODIFY.md`
- Impact: 제품 동작 무변경(문서·검증 기록만). 라이브 DB 에 주입한 실증용 임시 행 2건
  (`zz-tmp-postverify-f0021-isolation`, `zz-tmp-postverify-f0021-render`)은 검증 직후 삭제하고
  잔존 0건을 확인했다 — 기존 대화 245건·리뷰 원장 무변경.
- Rollback Notes: 문서 되돌리기 외 롤백 대상 없음.

## CHG-20260728-0001
- Date: 2026-07-28
- Related Requirement: TASK-20260716-subtab-sticky, §9 후속(revise/rederive prefill 결함)
  — **docs-only, 코드 무변경** (stale 체크박스 정리)
- Summary: TASK.md 에 미완으로 남아 있던 2건이 **실제로는 이미 완료된 작업**임을 확인하고
  근거와 함께 닫았다. 코드·자산 변경 없음.
  - **subtab-sticky**: 커밋 `08704f3d` 로 구현·main 반영 완료. 라이브 배포본
    `/static/styles.css` 와 web 컨테이너 내 파일 양쪽에서 `position: sticky; top: 0;
    z-index: 6` 실재 확인. 스크롤 컨테이너별 배경 오버라이드(ai-console=`--bg`)도 포함.
  - **§9 main 병합 + 배포 + 라이브 재검증**: PR #938 머지(2026-07-24T07:37Z).
    prefill fix 배포(16:20) 이후 `agent_runtime.redteam_reviews` 표본 21건 중
    `revision_applied=true` **15건** 관측 — 수정 전 42건 중 35건이 false 였던 것과 대비되어
    라이브 재검증 조건 충족.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/REPORT.md`
- Impact: 제품 동작 무변경. TASK.md 의 실제 잔여가 정형 Completion Checklist 만 남는다.
- Rollback Notes: 문서 되돌리기 외 롤백 대상 없음.

## CHG-20260728-0002
- Date: 2026-07-28
- Related Requirement: REQ-20260728T093528-answer-origin-realign,
  TASK-20260728T093528-answer-origin-realign
- Summary: 자가 검증을 거쳐 전달되는 답변이 **처음 요청사항이 아니라 직전 문맥(내부 리뷰
  결함 목록)에 응답하는 뉘앙스**를 띠던 결함을 구조적 원인에서 교정했다.
  - **근본 원인**: 수정·재추론 지시는 초안 생성 컨텍스트의 **trailing user turn** 이다
    (`_build_self_review_messages` — 2026-07-24 §9 prefill 회귀 방지 불변식). 따라서 모델의
    생성 지점 최근접 맥락이 "내부 리뷰 결함 목록"이고, 산출물이 원 요청이 아니라 그 직전
    맥락에 응답하는 레지스터로 기운다. 사용자는 그 검증을 본 적이 없어 자기 질문과 어긋난
    답으로 읽는다.
  - **1차 (추가 호출 0)**: `build_request_anchor` + `_ANSWER_CONTRACT` 를 revise/rederive
    지시의 **맨 끝**에 배치 — 같은 recency 지렛대를 반대로 쓴다. 출력이 "리뷰에 대한 회신"이
    아니라 "원 요청에 대한 최종 답변"임을 계약으로 못박고, 메타 표현·직전 맥락 지시어로
    시작 금지 + 답변 구성은 결함 목록이 아니라 원 요청이 결정함을 명시.
  - **2차 (조건부 1회)**: `detect_meta_framing`(결정론·도입부 240자 한정) 이 잔재를 잡으면
    `realign_answer` 가 **내용 보존 재서술 1회**를 요청. 폐기 가드 — 무산출 / 호출 실패 /
    원문 대비 60% 미만 길이(내용 손실 의심) / 재서술본에도 메타 잔존 → 원문 유지(fail-open).
  - **배치 결정**: 재서술을 red-team revise **콜백 내부**에 둬 산출물이 기존 verify 패스를
    그대로 통과하게 했다(수렴 불변식 무손상). 전달 후 별도 다듬기 패스는 채택하지 않았다 —
    근거 없이 문장만 다듬는 리라이터는 red-team 이 방금 강제한 grounding·불확실성 고지를
    지워내 정직성을 되돌린다(REVIEW.md 판단 근거 참조).
  - **누출 게이트**: 보조 앵커 `thread_goal` 은 대화의 (가려졌을 수 있는) 첫 요청에서 파생된
    자유 텍스트라 window 로 자를 수 없으므로 bounded 발신자에게 억제(`_realign_thread_goal`
    정본 — system 프롬프트 CONVERSATION CONTEXT 억제와 동일 축). 재앵커 블록은
    `<<USER_REQUEST>>` sentinel datamark.
  - **비용 가드**: 탐지 없으면 호출 0. 상한 없는 반복 수정 루프에서 **연속 거절 2회**면 그 run
    의 잔여 라운드는 재서술을 시도하지 않는다(성공 시 카운터 리셋). 운영 스위치
    `REDTEAM_ANSWER_REALIGN`(기본 1).
  - **오탐 가드**: 탐지 목적어를 `답변|초안` 으로 한정 — `내용` 을 넣으면 DBA 답변의 정당한
    DML 설명("이 쿼리는 orders 테이블의 내용을 수정합니다")을 오탐한다.
- Files:
  - `unit/feature-0002-agent-core/src/modules/redteam.py` — `build_request_anchor` /
    `_ANSWER_CONTRACT` / `detect_meta_framing` / `_meta_framing_head` /
    `build_reanchor_instruction` / `realign_answer` / `answer_realign_enabled` 신설,
    `build_revision_instruction`·`build_rederive_instruction` 에 `question`/`thread_goal`
    선택 인자(미지정 시 기존 형태 — 레거시 무회귀), `orchestrate_review(thread_goal=…)`,
    `_strip_review_sentinels` 에 요청 sentinel 추가
  - `unit/feature-0002-agent-core/src/agent_core.py` — `_realign_thread_goal` 신설(누출 게이트),
    `_rt_generate`/`_rt_realign` 분리 + `_rt_revise`·`_rt_rederive` 배선(재추론은
    `base=_rd_messages` 로 신 근거 컨텍스트 유지), realign 관측치 `_rt_meta` + stderr
  - `shared/runtime_settings.py` — `REDTEAM_ANSWER_REALIGN` 스펙(0/1, 기본 1, live)
  - `unit/feature-0002-agent-core/tests/test_redteam.py`(신규 20건),
    `unit/feature-0002-agent-core/tests/test_self_review_messages.py`(신규 3건)
  - `unit/feature-0021-redteam-review/docs/{FUNCTION,TASK,REVIEW,MODIFY,REPORT,TEST}.md`,
    `docs/test-runs.d/20260728T0935-answer-origin-realign.md`
- Impact: 답변 **문구·서술 대상**이 바뀐다(사실·수치·근거는 불변 — 재서술은 내용 보존 계약이고
  길이·메타 가드로 폐기된다). 마이그레이션 없음. 프론트 자산 무변경. 리뷰 판정 스키마 무변경.
  추가 LLM 호출은 메타 프레이밍이 탐지된 라운드에서만 1회이며 `REDTEAM_ANSWER_REALIGN=0` 으로
  즉시 차단 가능. 미해소 고지(`_UNRESOLVED_NOTICE`)는 orchestrate 루프 **이후** 부착이라
  재서술이 이를 지울 경로가 없다.
- Rollback Notes: `REDTEAM_ANSWER_REALIGN=0` 으로 2차 방어만 즉시 차단(재배포 불요). 1차
  재앵커까지 되돌리려면 커밋 revert — 프롬프트 문자열 변경이라 데이터 마이그레이션 불요.

## CHG-20260728-0003
- Date: 2026-07-28
- Related Requirement: TASK-20260728T185500-realign-postverify
  — **docs-only, 코드 무변경** (CHG-20260728-0002 배포분의 POST-DEPLOY 검증 기록)
- Summary: answer-origin-realign(PR #1026) 배포 후 라이브 실증 결과를 기록했다.
  - 배포: `make deploy-all`(deploy-web 스파인) — web 롤링 one-at-a-time + 90s soak 통과 +
    워커(insight/ask) 롤아웃 + Caddy·gateway 무드리프트.
  - 반영 확인: web-a/web-b/ask-worker/insight-worker 전부 `GIT_COMMIT=f0b3d3a5`, ask-worker
    baked `modules/redteam.py` 에 신규 심볼 9 매치, web baked `runtime_settings.py` 에
    `REDTEAM_ANSWER_REALIGN` 1 매치, 엣지 `/healthz` 200. (repo 존재만으로 그치지 않고 **이미지
    baked** 까지 확인 — 자산·코드는 빌드 시 baked 되어 repo 와 라이브가 어긋날 수 있다.)
  - PB-0008 실 Windows 브라우저: 관리 콘솔 *설정 > AI 자가 리뷰* 신규 행이 라벨·즉시 반영 배지·
    `0/1` 단위·effective 1(기본 활성)·설명문·스펙 순서대로 렌더되고 잘림/겹침 없음을 육안 확인.
  - **미검증 명시**: 답변 뉘앙스의 실제 교정 효과는 배포 후 표본이 쌓여야 관측된다 — 본 Run 은
    "코드·설정이 라이브에 올랐다" 까지다. TEST.md §4 에 미커버로 남겼다.
- Files: `docs/TEST.md`(§3 Run append), `docs/test-runs.d/20260728T0935-answer-origin-realign.md`
  (Run 4 추가), `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`
- Impact: 제품 동작 무변경(문서·검증 기록만). 라이브 데이터 변경 없음 — 조회·introspection 만
  수행했다(설정 값 저장·대화 생성 없음).
- Rollback Notes: 문서 되돌리기 외 롤백 대상 없음.

## CHG-20260729-0001
- Date: 2026-07-29
- Related Requirement: REQ-20260729T110000-review-request-context,
  TASK-20260729T110000-review-request-context
- Summary: CHG-20260728-0002(answer-origin-realign)의 재앵커가 **다중 턴에서 답변을 붕괴**시키던
  회귀를 라이브 판정 데이터로 진단해 교정했다. 사용자 리포트: "처음 요청했던 '쿼리 리뷰'에 대한
  답변은 수행하지 않고 두 번째 대화의 '네 맞습니다.' 라는 텍스트에만 정합하게 답변".
  - **라이브 기전** (대화 `20260729013313-2211841a`, run #132): 턴1 "쿼리 리뷰를 진행해주세요"
    (+첨부 SQL) → 턴2 "네 맞습니다." 에서 **14 라운드** 수정 후 `stop=resolved`, 최종 **152자**
    ("상세 분석이 필요하시면 말씀해주세요"). 턴3 에서 사용자가 "리뷰 진행 및 답변해주세요" 를
    다시 눌러야 3,170자 정상 리뷰가 나왔다.
  - **원인 ① (기존 결함, CHG-0002 가 증폭)**: 리뷰어는 fresh-context 라 대화를 못 보고 `question`
    으로 **현재 턴 발화만** 받는다 → "USER QUESTION 에 '네 맞습니다'만 있는데 DRAFT 는 긴 리뷰"
    를 `completeness` BLOCK 으로 냈다.
  - **원인 ② (기존 결함)**: 첨부 파일 본문은 knowledge context(**시스템 프롬프트**)로 주입되고
    evidence digest 는 **도구 실행만** 담는다 → "사용자 제출 증거가 없는 SQL 을 검증된 분석인
    것처럼 제시" 를 `honesty` BLOCK 으로 냈다. 첨부 리뷰마다 구조적으로 재발한다.
  - **원인 ③ (CHG-0002 도입)**: 재앵커가 현재 턴 발화를 "원 요청" 으로 싣고 계약이 "답변의
    구성·범위·상세도는 원 요청이 결정한다" + "원 요청이 묻지 않은 것을 늘어놓지 말 것" 이라
    선언 → 모델에게 **답변을 그 발화 크기로 축소할 권한**을 줬다.
  - **원인 ④ (퇴행 경로)**: 내용을 지울수록 반박할 claim 이 사라져 리뷰어가 통과시킨다 —
    **축소가 곧 수렴이 되는 gradient**. 14 라운드가 그 흔적이다.
  - **교정**: (D1) `run_review` 에 `CONVERSATION REQUEST` 주입 + 프롬프트가 "짧은 후속 발화 대비
    과답변" 보고를 금지하고 "삭제로 결함을 해소한 수정본은 REGRESSION → BLOCK" 을 명시.
    (D3) evidence digest 에 `USER-ATTACHED FILES` 매니페스트+발췌, 첨부 섹션이 자기 예산 선점.
    (D2) 재앵커 2층([이 대화의 요청 — 답변이 수행해야 할 일] / [직전 사용자 발화 — 답변 범위가
    아니다]) + 계약을 **addressing 전용**으로 한정. (D4) 붕괴 가드 — 수정본이 초안의 30% 미만이면
    미채택 + `stop_reason=revise_collapsed`.
- Files:
  - `unit/feature-0002-agent-core/src/modules/redteam.py` — `REDTEAM_REVIEW_PROMPT` 다중 턴/삭제-
    회귀 규칙, `run_review(conversation_request=…)`, `build_attachment_digest` 신설 +
    `build_evidence_digest(attachments=…)`, `build_request_anchor` 2층 + `_ANSWER_CONTRACT` 재작성,
    `build_revision/rederive/reanchor_instruction(conversation_request=…)`,
    `orchestrate_review(conversation_request=…, attachments=…)`, `_COLLAPSE_MIN_RATIO` 가드
  - `unit/feature-0002-agent-core/src/agent_core.py` — `_review_conversation_request` /
    `_review_attachments` 신설(누출 게이트 포함) + 호출부 배선
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` — `revise_collapsed` 한글 라벨
  - `unit/feature-0002-agent-core/tests/{test_redteam,test_self_review_messages}.py` — 신규 22건
  - `unit/feature-0021-redteam-review/docs/*`
- Impact: 다중 턴 답변이 더 이상 직전 발화 크기로 축소되지 않는다. 리뷰어의 구조적 false
  positive 2종(과답변·첨부 창작)이 제거되어 불필요한 수정 라운드도 줄어든다. 마이그레이션 없음
  (`stop_reason` 은 기존 text 컬럼, 신규 값만 추가). 프론트는 라벨 1줄.
- Rollback Notes: 커밋 revert. `REDTEAM_ANSWER_REALIGN=0` 은 realign(2차)만 끄므로 본 회귀와는
  무관하다 — 본 교정은 리뷰어 입력·앵커·가드 층이라 설정으로 우회되지 않는다.

## CHG-20260729-0002
- Date: 2026-07-29
- Related Requirement: REQ-20260729T110000-review-request-context (라이브 측정 후속),
  TASK-20260729T120000-review-continuation
- Summary: CHG-20260729-0001 배포 후 **라이브 유도 측정**에서 드러난 반대 방향 과교정을 닫았다.
  대화 요청을 받은 리뷰어가 "이전 턴에서 이미 전달한 리뷰를 이 답변이 다시 주지 않았다" 를
  `completeness` BLOCK 으로 내는 현상(리뷰어는 이전 턴을 보지 못하므로 구조적으로 알 수 없다).
  프롬프트에 continuation 규칙 추가 — "CONVERSATION REQUEST 는 이전 턴에서 이미(부분) 답변됐을
  수 있다 / 짧은 후속 발화에 대한 타당한 continuation 은 정상 / `completeness` 는 답변이 아무
  actionable 도 남기지 않을 때만".
- 측정(동일 초안·모델·evidence, 리뷰어 판정만 반복): 과교정 **2/3 → 1/4**.
- Files: `unit/feature-0002-agent-core/src/modules/redteam.py`(REDTEAM_REVIEW_PROMPT),
  `unit/feature-0002-agent-core/tests/test_redteam.py`(+1),
  `unit/feature-0021-redteam-review/docs/*`
- Impact: 불필요한 수정 라운드 감소. 이 방향의 잔여 오판은 답변을 **늘리는** 쪽이라 붕괴 가드와
  충돌하지 않는다(최악이라도 리뷰 재수록, 파괴 아님). 마이그레이션·프론트 변경 없음.
- Rollback Notes: 프롬프트 문자열 revert.

## CHG-20260729-0003
- Date: 2026-07-29
- Related Requirement: TASK-20260729T120000-review-continuation
  — **docs-only, 코드 무변경** (CHG-20260729-0002 배포분의 POST-DEPLOY 확정)
- Summary: continuation 가드 배포본(`44d70215`)에서 라이브 재확인. 같은 대화에 짧은 후속 발화를
  **연속 2회째**("네, 그렇게 진행하겠습니다.") 태워 판정 `id=140` **pass · rounds=0 · BLOCK 0 ·
  WARN 0** · 답변 566자 실행 체크리스트를 확인했다. Run 3(2/3→1/4 측정)은 배포 **전** 컨테이너에
  프롬프트를 주입해 얻은 값이라 배포본 재확인이 필요했다 — 주입 측정을 배포 검증으로 등치하지
  않는다.
- Files: `docs/TEST.md`, `docs/test-runs.d/20260729T1200-live-induction-measurement.md`(Run 4),
  `docs/MODIFY.md`, `docs/REVIEW.md`
- Impact: 제품 동작 무변경(검증 기록만). 라이브 데이터에는 유도 대화 1건의 턴이 추가됐다
  (검증 목적으로 생성한 전용 대화 — 기존 사용자 대화는 무변경).
- Rollback Notes: 문서 되돌리기 외 없음.

## CHG-20260729-0004
- Date: 2026-07-29
- Related Requirement: TASK-20260729T123000-review-rounds-ledger
- Summary: 자가 적대 리뷰의 **회차 단계 전부**를 원장으로 보존하고, 관리 콘솔 '감사 > AI 운영
  현황 > 추론' 을 **대화 단위 격리 + 3계층 접이식**으로 재구성했다.
  - 이전에는 한 답변(run)당 요약 1행만 남아 `findings`(최초 리뷰)·`verify_findings`(마지막
    재검증)만 관측 가능했다 — 2회차 재검증이 무엇을 지적했고 3회차 수정이 어떤 방식이었는지는
    소실. 콘솔이 "각 대화의 마지막 리뷰만" 보여준 1차 원인.
  - 신규 `agent_runtime.redteam_review_rounds` 에 `(round_index, phase)` = (0,'review') →
    (N,'revise') → (N,'verify') 순서로 append. 채택되지 못한 폐기 라운드도 `note` 로 남겨
    "왜 이 회차가 마지막인가" 가 원장에서 읽힌다.
  - 콘솔 조회를 flat id DESC 에서 **대화 keyset 페이징**으로 전환: 대화는 최근 리뷰 순(desc),
    대화 내부는 진행 순(asc). 대화당 상한 20건이며 초과분은 `capped` 로 표시(무언의 절단 금지).
  - 답변 본문은 저장하지 않고 길이만 기록 — `/api/admin/reasoning/notes` 의 "내용 비반환,
    목록 메타만" 최소 노출 규약과 동일 판단.
- Files:
  - feature-0002: `alembic/versions/20260729_0048_redteam_review_rounds.py`(신규),
    `alembic/versions/MAX_MIGRATION.txt`, `src/scripts/agent_runtime_schema.sql`,
    `src/modules/redteam.py`(`_insert_review_rounds` 신설 · `record_review(rounds=)` ·
    `orchestrate_review` rounds_ledger), `tests/test_redteam.py`(+6)
  - feature-0003: `src/routers/admin_reasoning.py`(`_query_conversation_page`·`_attach_rounds`·
    `_row_to_item` 분리), `src/static/admin.js`(대화 그룹·회차 렌더), `src/static/styles.css`,
    `tests/test_admin_reasoning.py`(+6)
  - feature-0021: `docs/TASK.md`, `docs/FUNCTION.md`, `docs/MODIFY.md`, `docs/REVIEW.md`,
    `docs/REPORT.md`, `docs/TEST.md`, `docs/test-runs.d/20260729T1230-review-rounds-ledger.md`
- Impact: **비파괴 additive**. 요약 행(`redteam_reviews`) 스키마·기록 동작 무변경 —
  기존 통계/타임라인 회귀 0. 회차 원장 INSERT 는 요약 커밋 **후** 별도 트랜잭션이라 실패해도
  요약은 보존된다(0048 미적용 stale agent 이미지 폴백). 콘솔 응답은 `items` 를 유지한 채
  `conversations`/`rounds`/`rounds_available`/`per_conversation_cap` 을 추가했고, 회차 원장이
  없는 이전 기록은 기존 요약 타임라인으로 폴백한다. 답변 지연 영향 없음(라운드마다 PG 왕복을
  만들지 않고 종료 시 1회 배치).
- Rollback Notes: alembic `downgrade` = DROP TABLE (파생 관측 데이터 소실 허용, 0042/0043/0045
  규약 동형). 코드 롤백만으로도 원장 기록이 멈출 뿐 답변 경로·요약 기록에는 영향이 없다.

## CHG-20260729-0005
- Date: 2026-07-29
- Related Requirement: TASK-20260729T123000-review-rounds-ledger
  — **docs-only, 코드 무변경** (CHG-20260729-0004 배포분의 POST-DEPLOY 확정)
- Summary: 회차 원장(0048) 배포본 `f87bf1da` 에서 라이브 실증. 마이그레이션·GRANT 확인 후
  검증 질문 1건을 실제로 태워 `redteam_review_rounds` 에 회차 2단계가 적재되는 것과, 콘솔
  '추론' 탭이 그 회차를 진행 순서로 표시하는 것을 확인했다. 배포 전 검증은 격리 컨테이너 +
  클라이언트 스텁이었으므로, **서버가 실제 원장 행을 내려주는 경로**는 이 Run 이 처음 확인한다
  (repo 에 있음 ≠ 라이브에서 동작함 — 이 프로젝트가 반복해 경계해온 등치 오류).
- Files: `docs/TEST.md`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`
- Impact: 제품 동작 무변경(검증 기록만). 라이브 데이터에는 검증용 질문 1건의 턴과 그에 따른
  리뷰 판정 1건(`id=142`)이 추가됐다.
- Rollback Notes: 문서 되돌리기 외 없음.
