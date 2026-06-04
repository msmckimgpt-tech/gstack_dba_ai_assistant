---
playbook_id: PB-0008
name: windows-browser-verification
description: AI 가 실제 Windows 브라우저를 CDP 자동 구동하여 웹/UI 를 검증한다
trigger: manual
scope: feature
---

# Playbook: Windows 브라우저 검증 (AI 자동 구동)

> 웹/UI(화면·상호작용) 변경의 완료 검증은 WSL 내부 headless 가 아닌 **실제 Windows
> 브라우저**에서 수행한다 — AI 의 검증 화면 == 사용자가 보는 화면 (관점 괴리 방지).
> 본 Playbook 은 AI 가 `bin/win-browser.py` 로 Windows Chrome/Edge 를 CDP 자동 구동하는
> 절차다. 환경 분류·게이트는 AGENTS.md §15.4, 각 feature `docs/TEST.md` §3.

## Prerequisites
- 검증 대상 웹앱이 기동 중 (`docker compose ps` 로 `web` 서비스 healthy 확인; 기본 `localhost:18080`).
- 브리지 1회 setup 완료 — `bin/WIN-BROWSER-SETUP.md` (옵션 A relay 또는 B mirrored).
- `python3 bin/win-browser.py doctor` 가 `"ok": true`.

## Steps

1. **Preflight** — `python3 bin/win-browser.py doctor`.
   - `"ok": false` 면 출력의 `next_steps` 를 따라 setup 을 먼저 완료한다. 미완 상태로
     "검증함"을 선언하지 않는다.
2. **대상 앱 기동 확인** — `docker compose ps` (또는 프로젝트 기동 명령). 웹 서비스가
   `localhost:<port>` 로 응답하는지 `curl -sf http://localhost:18080/ -o /dev/null` 로 1차 확인.
3. **브라우저 기동** — `python3 bin/win-browser.py launch --url http://localhost:18080/`
   (idempotent — 이미 떠 있으면 reuse). 사용자 화면에 실제 Windows 브라우저 창이 뜬다.
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
9. **BLOCKED 처리** — 브리지 setup 이 불가하거나(예: 관리자 권한 없음) 화면 검증에서
   결함 발견 시 `REPORT.md` 에 `BLOCKED` 로 정리하여 사람에게 전달한다.

## Validation
- [ ] `doctor` 가 `"ok": true` (브리지 동작 확인)
- [ ] 대상 웹앱이 기동 중이고 응답한다
- [ ] 시나리오가 실제 Windows 브라우저에서 실행되었다 (`run` 의 `bridge_endpoint` 가 relay|mirrored)
- [ ] 주요 화면 스크린샷 증거가 생성되었다
- [ ] feature `docs/TEST.md` §3 에 `Environment: Windows-browser` Run 이 기록되었다
- [ ] 검증 후 `down` 으로 드라이버 인스턴스를 정리했다

## 비고
- 브리지 setup 이 환경상 불가하면(공용 CI 등) `WSL-headless`(feature-0004) 로 1차 검증하되,
  TEST.md 에 `Windows-browser` 미수행 사유를 명시한다 — "검증함"으로 오인되지 않게.
- verify-completion check #13 (WARN-only, v1) 이 웹 대상 변경에 `Windows-browser` Run 누락 시
  경고한다. 후속 cycle 에서 strict 격상 예정.
