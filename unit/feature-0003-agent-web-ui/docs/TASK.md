---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: high
- Last Updated: 2026-04-06

## 2. Task Queue
- [x] TASK-0001 Web UI 코드 이관
- [x] TASK-0002 정적 자산 이관
- [x] TASK-0003 agent 이미지 복사 경로 반영
- [x] TASK-0005 모던 UI/UX 전면 리디자인 (ChatGPT/Linear 스타일, 라이트/다크 테마)
- [x] TASK-0006 사용자 식별 (로그인, 담당, 역할, 목적) 백엔드 + 프론트엔드
- [x] TASK-0007 사내 특수 키워드 학습 구조 (CRUD + UI)
- [x] TASK-0004 엄격한 Web UI 검증 시나리오 정의
- [x] TASK-0008 로그인 버튼 브라우저 호환성 버그 수정

## 3. In Progress
- 없음

## 4. Blocked
- 없음

## 5. Done
- TASK-0001, TASK-0002, TASK-0003
- TASK-0005 (2026-04-06): HTML/CSS 전면 리디자인 - 모던 디자인 시스템, 라이트/다크 테마
- TASK-0006 (2026-04-06): 사용자 인증 API (login/me/logout) + WebUsers DB 테이블
- TASK-0007 (2026-04-06): 키워드 학습 API (CRUD) + WebKeywords DB 테이블 + 관리 UI
- TASK-0004 (2026-04-06): TEST.md에 브라우저 기반 검증 시나리오 8개 확정, 테스트 정책 명시
- TASK-0008 (2026-04-06): CSS/JS 클래스 불일치(hidden vs show) 수정, 누락 HTML 요소 추가, 브라우저 자동화 테스트 통과

## 6. Next Action
- 추가 브라우저 검증 시나리오(TEST-0005~TEST-0008) 실행

## 7. Completion Checklist
- [x] Web UI 코드 이관이 완료되었다
- [x] 루트 실행 경로가 새 구조를 참조한다
- [x] 문서가 현재 구조를 반영한다
- [x] 모던 UI/UX 리디자인이 적용되었다
- [x] 사용자 식별 기능이 구현되었다
- [x] 키워드 학습 구조가 구현되었다
- [x] 엄격한 Web UI 시나리오가 확정되었다
- [x] 로그인 버그가 수정되고 브라우저 테스트가 통과되었다
