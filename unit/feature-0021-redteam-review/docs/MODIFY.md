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
