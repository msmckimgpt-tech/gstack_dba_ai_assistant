---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: implemented
feature_status_date: 2026-09-08
---

# Task

## TASK-20260908-codex-connect-fix

사용자 요청: Codex 연결 실패 수정 후 실제 DQA 클라이언트를 직접 제어해 연결·간단한 요청/응답까지 실측. Permission denied 위치는 자동 연결 제외하되 목록에 표시. CI용 gh-runner는 불필요하면 제거.

## 2.1 Implementation Plan

- Minor: 기존 연결 계약의 결함 수정. 별도 러너/Windows 브라우저는 사용자 절차에 없다.
- `feature-0043/src/agent/lifecycle.py::_negotiate_client_caps`: 카탈로그 성공이 영속 상세를 반환하지 않는 계약을 처리하고 예외 기록을 복구한다. catalog + 빈 detail → 서버 heartbeat 수락 후 ready, stale/실패 위치는 ready 불가.
- `feature-0046/src/client/core.py::{RuntimeState,probe_runtime,verify_answers,login}`: 권한 실패를 안전한 상태 코드로 분리한다. Permission denied → usable=false, 로그인 대행 불가. 실제 응답과 진단 출력만 있는 상태를 구분한다.
- `feature-0046/src/client/discovery.py::{locations,DiscoveryCache}`: CI 계정 gh-runner를 탐색·기존 캐시에서 제외하고 권한 오류를 캐시 재사용으로 덮지 않는다.
- `feature-0003/src/static/app/client-bridge.js::paint`와 client-connect.css: 사용 불가 위치/사유를 연결된 플랫폼에서도 표시하고 선택/자동 연결에서는 제외한다.
- 테스트: catalog→receipt 회귀, 권한 거부/로그인 필요 구별, 오래된 성공 캐시 무효화, gh-runner 기존 캐시 제거, UI 비활성 위치 표시. 실제 앱 메뉴 업데이트 설치 → root Codex 연결 → 새 테스트 대화 요청/응답 실측.
- 패널: backend/security/qa/ux/design, 최대 3회, P1 0 확인. 코드와 실측 증거를 구분한다.

## Requested Scope

- [x] Codex 모델 조회 성공 이후 연결 완료 처리 수정·회귀 검증.
- [x] 권한 거부 위치 자동 연결 제외, 목록에 사유 표시.
- [x] gh-runner 탐색/캐시 제외.
- [x] 제품 PR #1631 병합·8f1116cf 전체 서버 배포·공개1.2.4·실제 DQA1.2.3→1.2.4 업데이트 설치.
- [x] 실제 DQA root Codex 연결·새 대화 응답 `42 DQA_CODEX_42`, 런타임32318ms/서버제출 성공 및 UI 표시 확인.
- [x] 독립 backend/security/QA/UX 검토, 실제 증적 정리·제품 PR1631/표시 보완 PR1633 병합·배포 완료. 최종 비정책 증거 동기화는 이 기록의 후속 PR를 따른다.

## Context

- worktree: /root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0046-codex-connect-fix
- branch: ai/codex/feature-0046-codex-connect-fix; base 49f7fa41
- AGENTS SHA-256: a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2
- 이전 TASK: task-history/20260908-before-codex-connect-fix.md.
- 실제1.2.1 receipt는 Codex failed, 동일 프로세스 로그는 catalog7종 성공 및 사용자 요청 응답 성공. catalog는 의도적으로 영속 detail에서 빠지지만 lifecycle은 detail[name]을 강제 참조한다. 예외 로그 호출도 필수 인자 누락.
- CLI 진단에서 root/claude-corp 모두 홈 기준 로그인·무도구 응답 성공. 사용자의 Permission denied 사례와 동일 실행 경로를 대조하며, 계정 이름으로 불가능하다고 조작하지 않는다. OS 권한 변경은 하지 않는다.
- share-client-entry 소유자에 core.py 영향 심볼 질의 20260908T054858508Z-61b4a3. 창/GUI 파일은 변경 계획 없음.

- Issue #1625. 추가 발견: catalog 건강 오인/진단 JSON 생존 오인, 선택 위치 변경 뒤 재시도 소실, OS PermissionError 형 유실을 함께 수정. 전역 파일 세대는 무관한 AI 조회를 반복하므로 AI별 selection_id로 구현.

- main 통합: PR1628 텍스트 선택/검색 수정·공개1.2.3, PR1629 첨부 전달 수정 통합. 새 버전은1.2.4. 앞 작업 TASK는 task-history/20260908-text-interaction-at-integration.md에 보존.

- [x] 공개1.2.3의 텍스트 선택/검색 개선을 포함한 최신 main 통합 및 문서 충돌 해소. 출하 버전1.2.4.

- [x] main통합 Windows1.2.4 빌드·native544 회귀 완료. heartbeat송신경쟁은 결정적 회귀로 추가 봉인.

- [x] 제품 PR #1631 작성. main1.2.3 통합과1.2.4 빌드/지문 확정, 독립 검토 완료. 설치·요청 실측은 배포 후 수행.

- [x] 최종 출하 대기 중 병합된 PR1627 프롬프트 전달 검증을 추가 통합했다. 네이티브1.2.4 바이너리 변경 없음.

- [x] 최종 main의 프롬프트 전달/클라이언트 선택 회귀39 PASS(30.90s). PR1631 통합 결과 확정.

- [x] 최종 표시 보완7ca6f2a4 웹 배포·실제 설치 앱 재시작·연결창 정상 문구 및 root 재연결 확인. 최신1.2.4 재확인, 원장 기록 완료.
