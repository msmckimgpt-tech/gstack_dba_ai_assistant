---
run_at: 2026-09-08T12:40:00+09:00
session: ai/codex/feature-0043-connect-discovery-ux
scope: DQA AI별 자동 연결·위치 캐시·완료 receipt·내장 창
verdict: PASS (검증 경계 별도 명시)
---

# DQA AI 연결 통합 검증

- 클라이언트 전체: **520 passed**, `DQA_JSDOM=/tmp/dqa-connect-ux-test/node_modules/jsdom/lib/api.js python3 -m pytest unit/feature-0046-native-client/tests -o addopts='' -q --tb=short` (35.59s).
- 러너 전체: **1661 passed, 1 skipped**, `PYTHONPATH=unit/feature-0003-agent-web-ui/src:. DQA_JSDOM=... python3 -m pytest unit/feature-0043-external-llm-bridge/tests -o addopts='' -q --tb=short` (186.80s). skip 1건은 test_console_job_delegation.py의 미배선 종류 거절 케이스다. 현재 모든 종류가 배선되어 적용 대상이 없어 건너뛰었음을 별도 -rs 실행으로 확인했다.
- 웹 인증 회귀: **22 passed**, core/web src PYTHONPATH로 `tests/test_api_token_auth.py` 실행.
- 전체 JS 모듈 DOM **11 시나리오 PASS**: 자동 연결/중복 위치/저장 위치/오류 재시도/플랫폼별 점진 진행/구클라이언트 업데이트/단독 페이지/클라이언트 없는 페이지/상주 안내/receipt 지연·실패/로그아웃 응답 무효화. Node와 jsdom 미설치 환경은 명시 skip한다. CI의 jsdom 설치 계약은 기존과 같아 자동 실행 공백이 있으며, 이번 회차는 DQA_JSDOM을 지정하여 실제 실행했다. TESTED-NOT-CI: 이번 PASS를 원격 CI 실행으로 오인하지 않는다.
- 병렬·경합: 느린 Codex 중 Claude 먼저 publish, 위치 변경 중 구 모델 제거, supervisor 복구 대기 중 3개 선택 보존, disconnect 중 late spawn 차단, PID 변경 후 옛 receipt 무효, pending/실패 선호 위치 미저장.
- 실제 프로세스 갱신/감독 12개 추가 검증 PASS. 테스트의 `_CONF_DIR` 문자열 교체를 제거하고 실제 `BRIDGE_STATE_DIR` 설정을 사용한다.

## 렌더 및 실제 클라이언트

**Environment: Windows-browser** — 실제 Windows Chrome 152.0.7977.75/CDP, 제품 CSS/HTML/연결 모듈을 렌더. desktop1440×1050, mobile390×844, standalone, failure 4개 PASS. 가로 넘침·pageerror 없음. duplicate 선택과 Codex 독립 완료, Escape 닫기 확인. 연결 배지 대비 5.21:1. 스크립트: `tests/windows/verify_connect_visual.py`.

**Environment: Windows-native** — Windows에서 빌드한 DQAConnect.exe 1.2.0 + 동봉 Python + WebView2 152. 실제 로컬 Bridge의 nonce/origin/authenticated identity→runner download/hash→--check→감독 프로세스→모델 협상→heartbeat→ready receipt→JS 카드/toast를 실행했다. 첫 실행은 Codex Windows 자동 연결, Claude Windows/FixtureUbuntu alice 중 WSL 선택. 두 번째 실행은 클라이언트 홈의 캐시/선호 위치 재사용으로 위치 질문 없이 두 플랫폼 자동 연결. 각 회차 완료 toast 두 개, 두 플랫폼 server heartbeat, URL nonce 제거 확인.

대역 경계: 서비스 로그인/API, `app.js` toast stub 및 테스트용 로그인 후 초기화 호출, 벤더 CLI 응답은 fixture다. 실제 서비스 로그인·app.js 초기화 전체나 실제 벤더 계정의 유료 모델 호출을 검증했다고 주장하지 않는다. 사용자 계정의 인증 파일은 열지 않았고 기존 설치본을 교체하지 않았다. 실제 발견 명령은 Windows/WSL 다계정 후보 식별까지 별도 확인했다.

재현: Windows staging 폴더에 `src/`, `static/`, `dist/DQAConnect/`, `rootCA.crt`, `fake-bin/`을 둔다. `FakeAI.cs`를 csc로 claude.exe/codex.exe/wsl.exe 각각 빌드하며 전부 테스트 실행 파일이다. Pillow를 staging/test-deps에 설치한 후 `python verify_connect_native.py <staging>`을 실행한다. 프로필은 실행마다 새로 만들고 한 실행 내 두 회차에서만 공유한다. 테스트 소유 PID 트리만 정리한다. native-evidence/native-results.json을 반환한다. 이 호스트의 native 창 픽셀 캡처는 PrintWindow/화면 영역 두 방식 모두 빈 면을 반환하여 유효한 시각 증거로 사용하지 않았다. 실제 native DOM/Bridge/runner 통합 실행은 PASS이며, 동일 제품 UI의 시각 검증은 앞의 Windows-browser 캡처로 별도 수행했다.

스크린샷·JSON: `unit/feature-0046-native-client/docs/artifacts/20260908-connect-discovery/`. Code-Navigation Map 재생성과 codenav-lint PASS. lint/게이트/배포·반입 지문은 REPORT의 최종 기록을 따른다.
