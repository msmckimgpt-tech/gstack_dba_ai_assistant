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
- Planned: 인증 성공 흐름·Edge·mirrored/portproxy 모드 실측은 후속.
- In Progress: 없음
- Done: 드라이버 + **무권한 auto-relay** + 워크플로 게이트 + 단위 테스트(10/10) + 검증 패널 반영 + **실제 Windows 브라우저 e2e 검증 완료** + 문서.

## 3. Recent Changes
- CDP 드라이버 + 브리지 자동 감지(mirrored/relay) + 시나리오 엔진.
- **무권한 auto-relay**: `launch` 가 Windows python 으로 vEthernet IP:9223 relay 자동 기동 (admin·WSL재시작 불요) — 지난 cycle 교훈 해소. `--ignore-certificate-errors`(self-signed) 추가.
- 정책 게이트: TEST.md 환경 분류, AGENTS §10.5/§15.4.1/§16, check #13.
- 보안: relay vEthernet 한정(LAN 노출 없음), allow_origins 비-와일드카드, profile per-user, PS injection escape.
- 총 변경 횟수: 2

## 4. Open Issues
- 인증 성공 후 흐름(대화/쿼리)·Edge·mirrored(B)·영속 portproxy(A) 모드는 미실측 (TEST.md §4). 무권한 relay(옵션 0)만 실 검증.

## 5. Test Status
- 자동 테스트: 시나리오 엔진 단위 테스트 10/10 PASS.
- **실 검증(2026-06-04)**: 무권한 relay 로 실제 Windows Chrome 148 → DQA 웹 UI 로드(200) + 로그인 기능 e2e(인증 실패 경로) PASS. 스크린샷 `artifacts/shared/out/win-browser/`. (TEST.md §3 Run 003/004)
- 미검증 항목: 인증 성공 흐름, A/B 브리지 모드.

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- **기본 사용은 setup 불요** — `python3 bin/win-browser.py launch --url …` 한 번으로 무권한 브리지 자동(단, Windows python 필요). 영속/대안은 `bin/WIN-BROWSER-SETUP.md` 옵션 A/B.
- **보안**: CDP 는 무인증 채널. relay 는 vEthernet IP 에만 바인딩(LAN 노출 없음). 수동으로 `listenaddress=0.0.0.0` 개방 금지. 테스트 프로필(`%LOCALAPPDATA%\win-browser-cdp`)에 민감 계정 로그인 금지.

## 8. Suggested Improvements
- check #13 의 strict(MUST) 격상 (현재 v1 WARN-only) — 후속 cycle.
- 세션 단위 ephemeral 브리지(시작 시 setup, 종료 시 `-Remove`) 자동화 래퍼.
- feature-0003-agent-web-ui 의 주요 흐름 시나리오 세트를 src/ 에 비축.
