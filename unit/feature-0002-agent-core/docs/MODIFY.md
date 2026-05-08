---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: agent 코어 소스와 Dockerfile을 기능 단위 구조로 이관
- Files: src/agent_cli.py, src/agent_core.py, src/modules/*, src/Dockerfile
- Notes: Web UI는 별도 feature에서 관리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 워크스테이션 Local LLM 지연 완화를 위해 역할별 모델 바인딩과 검증 문서를 정합화
- Files: src/modules/config.py, src/modules/llm.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../feature-0003-agent-web-ui/docs/TEST.md
- Notes: 현재 repo `.env` 의 alias/timeout/worker 값은 로컬 소비자 설정이라 Git 추적 대상이 아니다. 외부 provider 프로필 조정과 direct bench 기록은 `/root/download/docker/local_llm` 저장소에서 별도로 관리한다.

## CHG-20260421-0003
- Date: 2026-04-21
- Summary: insight-worker 누락 복구 경로와 일자별 로그 보관 구조를 추가
- Files: src/modules/insight.py, src/modules/utils.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../../../../AGENTS.md
- Notes: 기존 더티 워크트리는 보존하고 별도 worktree/브랜치에서 구현했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 완전성 검증을 통과할 때만 fingerprint/refresh 성공 마커를 갱신한다.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0012 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — agent-core 책임 범위, web-ui coupling 인정, modules/ 서브디렉토리 책임 구분, insight-worker 복구 순서 시나리오.
- Files: unit/feature-0002-agent-core/docs/ANCHOR.md, unit/feature-0002-agent-core/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. insight-worker 복구 순서를 바꾸려는 향후 요청은 §3과 충돌 감지 대상 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
