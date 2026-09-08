---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
---

# Task

## TASK-20260908T120000-connect-discovery-ux — AI별 자동 연결과 위치 캐시

- 상태: in-progress / 위험도 Minor (기존 인증·인가 계약 유지, 현재 사용자 요청으로 탐색·연결·디자인 변경 위임)
- hot_paths: `client/core.py`, `client/bridge.py`, `static/app/client-bridge.js`, `static/app/connect-modal.js`, `agent/discovery.py`
- 다른 활성 worktree는 읽기 전용으로 확인했으며 이 cycle은 전용 worktree에서 수행한다.

### 2.1 Implementation Plan

1. `unit/feature-0046-native-client/src/client/core.py`의 RuntimeState/discovery/runner env: WSL 배포판·계정을 식별하고 명령을 argv로 전달한다.
2. `src/client/discovery.py`의 DiscoveryCache: 클라이언트 홈에 위치·짧은 검증 캐시·선택을 저장하고, 백그라운드 탐색과 최대 4개 병렬 검증을 병합한다. 토큰·이메일·명령 출력은 저장하지 않는다.
3. `src/client/bridge.py`의 Bridge: 단일 내부 러너의 수명·플랫폼 추가·중복 연결 방지·상태를 관리한다. 선택 위치 JSON을 원자 갱신하고 계정 전환 시 기존 세션 토큰으로 연결됐다고 표시하지 않는다.
4. `unit/feature-0043-external-llm-bridge/src/agent/{base,discovery,caps,lifecycle}.py`: 클라이언트가 고른 WSL 배포판·계정과 분리된 러너 상태를 실제 실행에 전달한다. 배포 bundle 재생성.
5. `unit/feature-0003-agent-web-ui/src/static/app/{client-bridge,connect-modal}.js`, `static/index.html`, `static/css/client-connect.css`: AI별 카드·진행 상태·중복 위치 선택·성공 토스트·키보드 동작을 구현한다.
6. Python 행위 테스트, JS DOM 흐름, 실제 DQA 실행 파일 WebView2 E2E·Windows 렌더 캡처, 리뷰 패널(기본 3R, QA 완료계약 보완/최신 main supervisor 통합 결함의 확인 라운드로 backend 최대 6R), verify-completion, PR/배포/설치기 반입까지 검증한다.

## 9. Requested Scope

- [x] 사용자는 DQA 클라이언트만 실행한다. 로그인 후 앱이 탐색·연결하고 러너/터미널 실행을 요구하지 않는다.
- [x] Claude Windows 1개 + Codex WSL 1개 → 각각 자동 연결·각각 토스트, radio 없음.
- [x] Claude Windows/WSL 두 곳 + Codex 1곳 → Codex는 즉시 연결, Claude만 위치 선택. WSL 계정이 다르면 별도 위치다.
- [x] 성공한 선택은 클라이언트 재시작 후 재사용. 사라진 위치·만료·손상 캐시는 재검증하며 실패/토큰을 성공으로 캐시하지 않는다.
- [x] 후보 열거 완료 후 느린 플랫폼의 검증·모델 조회 때문에 다른 플랫폼의 연결이 대기하지 않는다. 중복 탐색·연결 클릭은 작업 1개로 합친다.
- [x] 실패는 카드에서 재시도 가능하며, 하나 연결됐다고 남은 선택 화면이 닫히지 않는다.
- [x] UI 단독 페이지 진입도 앱 패널과 흐름 정합. 실제 DQA 내장 창에서 로그인·선택·재시작 캐시 흐름과 Windows 렌더 캡처 확보.

### Design references (2026-09-08)

- Raycast Account Management: https://manual.raycast.com/account-management — 서비스별 계정 묶음과 개별 관리.
- Slack Connected accounts: https://slack.com/help/articles/218891278-Connect-to-other-services-using-your-Slack-account — 연결된 서비스 목록과 간단한 상태/관리 동작.
- 적용: 플랫폼 단위 목록, 선택이 필요한 행만 조작 노출, 완료 상태를 그 행에 남기고 토스트 제공. 기존 긴 안내를 1문장으로 축소.


## 세션 경계 및 배포

기존 `/api/ai/connect/token` 응답의 `connection_session`은 연결 수명 비교용 ID다. 인증/인가를 대신하지 않으며 새로운 세션의 토큰은 기존 `--check`를 통과한 뒤 연결을 교체한다. 토큰은 현재 창과 프로세스 메모리에만 유지한다. 클라이언트 1.2.0 설치기를 Windows에서 빌드하여 기존 업데이트 채널에 반입한다. 업데이트 설치에 대한 기존 사용자 확인은 유지한다.

## 이전 TASK

최신 통합 이전 기록: [20260908-before-connect-ux.md](task-history/20260908-before-connect-ux.md).

이전 완료/이연 기록: [20260907-native-client.md](task-history/20260907-native-client.md). 이번 cycle은 위 Requested Scope를 검증한다.

## 통합 및 검증 경계

- Issue #1615 / 공개 브랜치 `issue/1615-dqa-ai-connections`. main `8f49f1fc` 통합. 기존 완료 기록은 task-history에 보존.
- 사용자는 Windows 웹브라우저를 따로 실행하지 않는다. 실제 제품 경로는 DQA 앱의 WebView2다.
- Windows-native E2E는 실제 동결 exe·내장 Python·로컬 Bridge·배포 러너·WSL argv·서버 신고까지 실행한다. 서비스 로그인/API와 벤더 CLI 응답, app.js의 toast stub 및 테스트용 로그인 후 초기화 호출을 격리 대역으로 둔다. 실제 벤더 계정의 유료 모델 질의나 기존 사용자 설치본 교체를 검증했다고 주장하지 않는다.
