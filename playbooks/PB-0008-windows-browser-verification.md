---
playbook_id: PB-0008
name: windows-browser-verification
description: AI 가 실제 Windows 브라우저를 CDP 자동 구동하여 웹/UI 를 검증한다
trigger: manual
scope: feature
---

# Playbook: Windows 브라우저 검증 (AI 자동 구동)

> **보조 호환 검증용 (사용자 결정 2026-09-08)**: 주 서비스 사용 환경은 별도 DQA
> 클라이언트다. UI 완료 검증은 [PB-0009](PB-0009-dqa-client-verification.md)를 따른다.
> 이 문서는 일반 Windows 브라우저 호환성을 별도로 확인할 때만 사용한다. 별도 Chrome/Edge
> 실행은 DQA 앱의 WebView2·세션·로컬 브리지·트레이 검증이 아니다.

## Prerequisites
- 검증 대상 웹앱이 기동 중 (`docker compose ps` 로 `web` 서비스 healthy 확인).
  진입점은 **Caddy `:443` 단일 문**이다 — `https://<WEB_PUBLIC_HOST>` 또는 `https://localhost`.
  (`:18080` web 직접 문은 feature-0014 에서 폐기됐다. `Makefile` 의 `make status` 출력이 정본.)
- 브리지: **기본은 별도 setup 불요** — `launch` 가 무권한 userspace relay 를 자동 기동한다 (Windows python 필요, admin·WSL재시작 불요). 영속/대안은 `bin/WIN-BROWSER-SETUP.md` 옵션 A(portproxy)/B(mirrored).
- `pip install playwright`(host) + Windows Chrome/Edge + Windows python.
- **로그인 세션** — 이 드라이버는 전용 격리 프로필로 브라우저를 띄우므로 그 프로필에는
  세션이 없다. 로그인 뒤 화면을 검증하려면 Step 3.5 로 세션을 먼저 발급한다.

## Steps

1. **Preflight** — `python3 bin/win-browser.py doctor`.
   - chrome / playwright / win_python 가용성과 브리지 상태를 확인. 미비 시 `next_steps` 안내를 따른다.
     미완 상태로 "검증함"을 선언하지 않는다.
2. **대상 앱 기동 확인** — `docker compose ps`. 웹 서비스가 응답하는지
   `curl -skf https://localhost/ -o /dev/null` 로 1차 확인 (self-signed → `-k`).
3. **브라우저 기동 (브리지 자동)** — `python3 bin/win-browser.py launch --url https://localhost/`.
   실제 Windows 브라우저 창이 뜨고, 무권한 relay 가 자동 기동되어 브리지가 성립한다
   (출력 `"bridge_mode": "relay"` + `"relay": "... no-admin"`). self-signed 는 `--ignore-certificate-errors`(기본 on)로 통과. idempotent — 이미 떠 있으면 reuse.
3.5. **검증용 로그인 세션 발급 (로그인 뒤 화면을 볼 때 필수)** —
   `python3 bin/win-browser.py session-login --origin https://<검증 대상>`.
   - `.env` 의 `WEB_BOOTSTRAP_ADMIN_USERNAME`/`PASSWORD` 로 **실제 로그인 폼**을 채워 세션을
     만든다(사용자 경로 그대로 — 로그인 화면 회귀도 함께 드러난다). 비밀번호는 출력되지도,
     argv 로 넘어가지도 않는다.
   - **멱등** — 이미 로그인돼 있으면 폼을 건드리지 않고 `"already": true` 로 끝난다. 매 검증
     앞단에서 그냥 호출하면 된다.
   - **실패해도 재시도하지 않는다** — 연속 실패는 계정을 잠근다(서버 `LOGIN_MAX_FAILED_ATTEMPTS`
     + IP throttle). `login_failed` 가 나오면 `server_message` 를 읽고 자격증명·계정 상태를
     확인한 뒤 사람이 판단해 다시 호출한다.
   - 상태만 볼 때는 `session-check`, 프로필을 비울 때는 `session-logout`.
   - ⚠ **쿠키 경계는 `host` 다** (포트·스킴은 쿠키를 나누지 않는다). 세션을 발급한 host 와
     시나리오가 여는 host 가 다르면(`localhost` vs `mysql-ai.company.local`) 로그인 화면이
     그대로 나온다 — 같은 host 로 맞춘다.
   - 🔒 비밀번호는 **loopback + `.env` 의 `WEB_ALLOWED_HOSTS`/`WEB_PUBLIC_HOST` 로만** 전송된다.
     그 밖의 origin 은 `origin_not_allowed` 로 거부된다(주입된 지시로 자격증명이 외부 호스트에
     타이핑되는 것을 막는 fail-closed 게이트). 의도한 경우에만 `--allow-remote-origin`.
   - ⚠ `session-logout` 은 그 로그인 세션에서 발급된 **AI 연결(`mat_`) 토큰까지 폐기**한다
     (`/api/auth/logout` → `revoke_for_session`). 정리 목적이라도 외부 AI 연동이 끊길 수 있으니
     필요할 때만 쓴다.
   - 남는 위험(수용): 검증 프로필은 **영속**이라 Chrome 이 그 안에 자격증명 상태를 남길 수 있다.
     프로필 경로는 per-user `%LOCALAPPDATA%` (ACL 보호)이며, **이 프로필을 자격증명과 같은
     민감도로 취급**한다(공유·복사 금지).
   - 세션이 없으면 도달 가능한 화면이 로그인 폼뿐이라, 그 상태의 "검증" 은 완료 근거가 되지
     못한다 — TEST.md 에 **미수행 사유**로 명시한다(실측 2026-08-27~28 두 cycle 연속 발생).

4. **시나리오 작성** — 검증할 사용자 흐름을 `unit/<feature-id>/src/scenario.*.json` 으로
   정의한다 (예시: `unit/feature-0008-windows-browser-testing/src/scenario.example.json`).
   각 step 은 `goto|click|type|press|hover|wait_for|eval|assert_text|assert_visible|screenshot`.
   주요 화면 전·후에 `screenshot` 을 넣어 증거를 남긴다.
5. **시나리오 실행** — `python3 bin/win-browser.py run --scenario <file>`.
   - 출력 JSON 의 `ok` 와 step 별 `results` 를 확인한다. 실패 step 은 `error` 로 표시된다.
   - 기본은 **첫 실패 step 에서 중단**(step 의 `stop_on_fail` default true). 전 step 을 끝까지
     돌려 결과를 모으려면 해당 step 에 `"stop_on_fail": false` 를 둔다.
   - 단발 조작은 `goto/click/type/screenshot` 서브커맨드로도 가능.
   - ⚠ 시나리오의 `eval` step 은 실제 브라우저에서 임의 JS 를 실행한다 — 시나리오 파일은
     신뢰 입력으로 취급하고, 테스트 프로필에 민감 계정을 로그인하지 않는다.
6. **증거 수집** — 생성된 스크린샷(`shot_dir`, 기본 `/tmp/win-browser-shots`)을 확인하고,
   필요 시 `artifacts/` 하위로 이동/보관한다.
7. **TEST.md §3 기록** — 해당 feature `docs/TEST.md` §3 에 Run 항목 append:
   - `Environment: Windows-browser`
   - `Runner: AI`
   - `Bridge:` doctor 의 `bridge_mode`(relay|mirrored) + endpoint
   - `Evidence:` 스크린샷 경로
   - `Pass/Fail:` + `Notes:` (관찰된 차이/이슈)
8. **정리** — 검증 종료 후 `python3 bin/win-browser.py down` 으로 **본 드라이버가 띄운
   인스턴스만** 종료한다 (사용자 일반 브라우저는 보존). NAT+relay 모드에서 브리지를
   상시 열어두지 않으려면 관리자 PowerShell 에서 `win-browser-setup.ps1 -Remove` 로
   portproxy + 방화벽 규칙도 닫는다 (mirrored 모드는 인바운드 hole 이 없어 해당 없음).
9. 보조 브라우저 접근 실패는 해당 검증의 한계로 기록한다. 주 경로 DQA-client 검증이
   가능한데 보조 환경 실패만으로 작업 전체를 승인 대기 상태로 만들지 않는다.

## Validation
- [ ] `doctor` 가 `"ok": true` (브리지 동작 확인)
- [ ] (로그인 뒤 화면 검증 시) `session-check` 가 `"authenticated": true`
- [ ] 대상 웹앱이 기동 중이고 응답한다
- [ ] 시나리오가 실제 Windows 브라우저에서 실행되었다 (`run` 의 `bridge_endpoint` 가 relay|mirrored)
- [ ] 주요 화면 스크린샷 증거가 생성되었다
- [ ] feature `docs/TEST.md` §3 에 `Environment: Windows-browser` Run 이 기록되었다
- [ ] 검증 후 `down` 으로 드라이버 인스턴스를 정리했다

## 비고
- 브리지 setup 이 환경상 불가하면(공용 CI 등) `WSL-headless`(feature-0004) 로 1차 검증하되,
  TEST.md 에 `Windows-browser` 미수행 사유를 명시한다 — "검증함"으로 오인되지 않게.
- 현재 완료 gate는 AGENTS.md §15.4.1과 PB-0009가 정본이다. 이 문서의 브라우저 Run을
  새 DQA-client 실행 PASS로 해석하지 않는다.
- **대화형(in-loop) 탐색**은 Playwright MCP(`bin/playwright-mcp.sh` + `.mcp.json`)로 같은 브리지에
  attach 해 browser_snapshot/click/type 도구를 모델 루프에서 직접 쓸 수 있다(`bin/WIN-BROWSER-SETUP.md`).
  단 **반복 가능한 완료 게이트 증거**(TEST.md §3 Run)는 win-browser.py `run --scenario` 로 남긴다.
