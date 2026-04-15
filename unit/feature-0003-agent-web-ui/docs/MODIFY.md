---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: Web UI 앱과 정적 자산을 기능 단위 구조로 이관
- Files: src/app.py, src/static/*
- Notes: 코어 로직은 별도 feature에 유지

## CHG-20260414-0002
- Date: 2026-04-14
- Summary: 메인 워크스페이스를 작업 중심 콘솔 레이아웃으로 재개편하고 로그인/드로어/빠른 액션 UX를 재정의
- Files: src/static/index.html, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md
- Notes: 기존 기능 ID와 JS 결합은 유지하고, 시각 체계와 정보 배치를 전면 수정

## CHG-20260415-0003
- Date: 2026-04-15
- Summary: 계정/권한 체계를 실제 인증 모델로 교체하고, 대화 소유권과 관리자 화면 기준으로 Web UI를 전면 재구성
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env
- Notes: `WebUsers`/`WebKeywords` 런타임 경로를 제거하고 `WebAccounts`/`WebAuthSessions`/`AgentCoreConversations.owner_account_id`를 기준으로 동작하도록 변경. 로컬 LLM 게이트웨이 미가용 시 false positive를 막기 위해 연결 가능 여부를 세션 응답에 반영
