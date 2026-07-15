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
