---
doc_type: MODIFY
feature_id: feature-0004-browser-automation
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: 브라우저 자동화 서비스와 Dockerfile을 기능 단위 구조로 이관
- Files: src/app.py, src/ctl.py, src/requirements.txt, src/Dockerfile
- Notes: 스크린샷 저장 경로는 `/shared/out/browser` 유지

## CHG-20260424-0002
- Date: 2026-04-24
- Related Requirement: TASK-0005 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — browser-automation이 agent로부터 격리된 원격 서비스인 이유, Playwright 이미지 크기 트레이드오프, ctl.py와 HTTP API의 role 구분, 스크린샷 요청 시나리오에서의 경로 선택.
- Files: unit/feature-0004-browser-automation/docs/ANCHOR.md, unit/feature-0004-browser-automation/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. Playwright를 agent-core에 통합하려는 향후 요청은 §1 / §2 Alt-A와 충돌 감지 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
