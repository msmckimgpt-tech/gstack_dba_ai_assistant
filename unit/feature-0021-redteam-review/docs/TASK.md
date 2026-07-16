---
doc_type: TASK
feature_id: feature-0021-redteam-review
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_updated: 2026-07-15
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-15

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002: `src/modules/redteam.py`(신규), `src/modules/agent_notes.py`(신규),
    `src/modules/guidance_registry.py`(신규), `src/agent_core.py`(choke-point 훅·노트 주입),
    `src/modules/ask.py`(노트 TTL reaper), `alembic/versions/20260715_0042_redteam_reviews.py`(신규)
  - shared: `runtime_settings.py`(REDTEAM_* 스펙 + serialize 그룹)
  - feature-0003: `src/web_context.py`(권한 1건 + admin catchup), `src/routers/admin_reasoning.py`(신규),
    `src/static/admin.html`(탭/pane), `src/static/admin.js`(패널 wiring + PERMISSION_DEPENDENCIES)
  - repo: `docs/ROUTEMAP.md`(재생성)
- **접근 방법:** Claude Code 의 fresh-context 적대 리뷰(find→verify)·effort scaling·
  auto-memory·progressive disclosure 패턴을 제품 답변 파이프라인의 단일 choke-point
  (`agent_core.py` `result["answer"]` 확정 지점)에 결정론적 오케스트레이션으로 이식.
  리뷰는 fail-open, 기본 haiku 급 저비용 모델, 추론 강도 게이팅. 노트는 /shared 임시
  파일 + ask-worker reaper TTL 정리. 콘솔은 read-only 신규 라우터 + 신규 권한.
- **위험도:** Major (답변당 LLM 호출 추가 = 외부 비용; 완화 — 저비용 모델·강도 게이팅·
  런타임 on/off·fail-open. 인증/인가·파괴적 변경 없음, 마이그레이션 additive)

<!-- PLAN-APPROVED: entry persona arg-given dispatch (사용자 요청 명시 위임, 2026-07-15).
     plan 표면화 후 진행 — AGENTS.md §7.1 Major 절차. -->

## 3. Task Queue
- [x] TASK-20260715T140100-console-panel: 관리 콘솔 "AI 추론" 탭 (admin_reasoning 라우터 +
      권한 + admin.html/admin.js + 설정 패널 "AI 자가 리뷰")
- [x] TASK-20260715T140101-tests-routemap: 단위 테스트 (redteam fail-open/게이팅,
      agent_notes cap/TTL, 라우터 RBAC) + ROUTEMAP 재생성 + make test
- [x] TASK-20260715T140102-deploy-verify: PR #819/#821 병합·배포(23b8faba)·alembic 0042·PB-0008 PASS
- [ ] TASK-20260716-console-ia: 관리 콘솔 IA 재구성 — 감사>AI추론(리뷰/노트) + 설정>프롬프트
      [전역/지침/스킬] 분리, 전역 프롬프트 비교·검토(fallback 중복 제거) (사용자 요청)

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Done
- TASK-20260715T140099-core: redteam/agent_notes/guidance_registry 모듈 + agent_core 훅 +
  runtime_settings 스펙 + alembic 0042 (구현·단위검증 완료)
- 적대 검증 패널 (REV-20260715-0002) — BLOCK2(MAX_MIGRATION·jsonb cast)+MAJOR1(인젝션 승격)+MINOR3 in-cycle 반영·재검증
- 리서치 (Claude Code 공식문서·엔지니어링 블로그·실동작 introspection + 제품 파이프라인/
  콘솔 구조 탐색) — 산출물: DECISIONS.md ADR-20260715T140000, REVIEW.md 근거 기록

## 7. Next Action
- 코어 모듈 구현 → 콘솔 → 테스트 → cycle-final → 배포

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
