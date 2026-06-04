---
doc_type: REPORT
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
AI 가 WSL 에서 **실제 Windows 브라우저**를 CDP 자동 구동해 웹/UI 를 검증하는 워크플로
도입. 드라이버(`bin/win-browser.py`) + 1회 브리지 setup + 검증 절차(PB-0008) + 완료
게이트(AGENTS §15.4.1, TEST.md 환경 분류, verify-completion check #13 WARN-only).
"CLI/WSL-headless 만으로 검증함" → "실제 Windows 화면 검증" 으로 관점 괴리를 차단.

## 2. Progress
- Planned: 실 환경 브리지 1회 setup 후 첫 Windows-browser run (TEST-0004, 후속).
- In Progress: 없음
- Done: 드라이버, 브리지 setup(A/B), 워크플로 게이트, 단위 테스트(10/10), 검증 패널 반영, 문서.

## 3. Recent Changes
- CDP 드라이버 + 브리지 자동 감지(mirrored/relay) + 시나리오 엔진.
- 정책 게이트: TEST.md 환경 분류, AGENTS §10.5/§15.4.1/§16, check #13.
- 보안 강화(검증 패널 반영): relay vEthernet 한정, allow_origins 비-와일드카드, profile per-user, PS injection escape.
- 총 변경 횟수: 1

## 4. Open Issues
- 실 Windows 브라우저 CDP wire end-to-end 는 브리지 1회 setup(관리자 portproxy 또는 mirrored) 후 검증 가능 (TEST.md §4). 본 cycle 미수행.

## 5. Test Status
- 자동 테스트: 시나리오 엔진 단위 테스트 10/10 PASS.
- 수동 테스트: doctor 진단 + spike(Windows Chrome 기동 + CDP 127.0.0.1 바인딩) 확인.
- 미검증 항목: 실 CDP wire (브리지 setup 의존, 후속).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- **1회 브리지 setup**: `bin/WIN-BROWSER-SETUP.md` 옵션 A(관리자 PowerShell `win-browser-setup.ps1`) 또는 B(`.wslconfig` mirrored + `wsl --shutdown`). 이후 AI 자동 구동 활성.
- **보안**: CDP 는 무인증 원격제어 채널. setup.ps1 이 LAN 노출을 차단(vEthernet 한정)하나, 수동으로 `listenaddress=0.0.0.0` 으로 열지 말 것. 테스트 프로필에 민감 계정 로그인 금지.

## 8. Suggested Improvements
- check #13 의 strict(MUST) 격상 (현재 v1 WARN-only) — 후속 cycle.
- 세션 단위 ephemeral 브리지(시작 시 setup, 종료 시 `-Remove`) 자동화 래퍼.
- feature-0003-agent-web-ui 의 주요 흐름 시나리오 세트를 src/ 에 비축.
