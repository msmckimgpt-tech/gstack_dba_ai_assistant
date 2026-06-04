---
doc_type: REVIEW
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260604-0001 [SUBAGENT:security-reviewer] — REQUEST-CHANGES → 반영 후 ACCEPT
- challenge: WSL→Windows CDP 브리지가 사용자 실제 브라우저를 무인증 원격제어에 노출하는지 적대적 점검.
- Related Change: bin/win-browser.py, bin/win-browser-setup.ps1, bin/WIN-BROWSER-SETUP.md, AGENTS.md §15.4.1
- Findings (verdict: 초기 NOT-shippable, must-fix 반영 후 shippable):
  - **F1 CRITICAL** — relay `listenaddress=0.0.0.0` + 방화벽 `-Profile Any` + Chrome `--remote-debugging-address=0.0.0.0` 가 무인증 CDP 를 LAN 전체에 노출 (쿠키/세션 탈취·임의 JS). → **반영**: setup.ps1 이 vEthernet(WSL) IP 에만 바인딩 + 방화벽 `-Profile Private` + `-RemoteAddress` WSL 서브넷 한정; win-browser.py launch 에서 `--remote-debugging-address=0.0.0.0` 제거(Chrome 은 127.0.0.1 유지, relay 가 forward).
  - **F2 HIGH** — `--remote-allow-origins=*` 가 DNS-rebinding 방어 무력화. → **반영**: `allow_origins()` 가 loopback+relay 의 구체 origin 만 생성(와일드카드 제거), `WIN_BROWSER_ALLOW_ORIGINS` override.
  - **F4 MEDIUM** — 프로필이 예측가능·world-writable `C:\temp`. → **반영**: `profile_path()` 가 per-user `%LOCALAPPDATA%\win-browser-cdp` 해석(폴백 C:\temp).
  - **F5 MEDIUM** — `down` 의 PS `-Command` 에 `WIN_BROWSER_PROFILE` 유래 marker 주입 가능. → **반영**: single-quote escape(`'`→`''`).
  - **F7 HIGH** — relay/방화벽이 상시 개방, `down` 이 teardown 안 함. → **반영(부분)**: F1 으로 노출이 WSL 서브넷 한정으로 축소; SETUP.md/PB-0008 에 `-Remove` teardown + mirrored 권장 명시. ephemeral 자동화는 REPORT §8 후속.
  - **F6 LOW** — `eval` 임의 JS(설계상). → **반영**: PB-0008 에 신뢰경계 주의 1줄.
- Risks (잔여): 무인증 CDP 의 근본 방어는 네트워크 계층 — vEthernet 한정 바인딩 정확성에 의존. mirrored 모드 권장으로 완화.
- Human Approval Needed: 아니오 (opt-in 도구 + WARN-only 게이트, must-fix 반영 완료).

## REV-20260604-0002 [SUBAGENT:qa-reviewer] — ACCEPT (must-fix before strict 격상)
- challenge: 워크플로 게이트(check #13)·드라이버·정책 표면의 정합성과 논리 버그 점검.
- Related Change: bin/verify-completion.sh(check #13), bin/win-browser.py, AGENTS.md(§10.5/§15.4.1/§16), unit/_template/docs/TEST.md, playbooks/PB-0008
- Findings (verdict: v1 WARN-only 로 shippable; strict 전 must-fix 2건):
  - **check #13 비웹 cycle PASS 확인** — 본 feature-0008 changeset 으로 regex 0 매칭 → PASS, WARN-only 로 절대 block 안 함(check #12 모델과 동일).
  - **MEDIUM (반영)** — TEST.md 템플릿 메뉴 라인 `Environment: CLI | WSL-headless | Windows-browser` 이 검출 regex 에 매칭되어 미작성 placeholder 가 false-PASS. → `grep -v '|'` 로 메뉴 라인 제외.
  - **MEDIUM (반영)** — §10.5 glob + check #13 regex 가 Jinja/.j2/.tpl/.tmpl 등 비-/templates/ 서버사이드 템플릿 누락. → check #13 regex 에 `jinja2?|j2|tpl|tmpl|hbs|ejs|astro` 추가.
  - **LOW (반영)** — check #13 표시 문자열 대소문자 불일치. → `Windows-browser verification` 으로 통일.
  - **LOW (반영)** — `run` 의 `stop_on_fail` 기본 동작 미문서화. → PB-0008 에 1줄 추가.
  - 라벨 일관성(`CLI`/`WSL-headless`/`Windows-browser`), PB-0008 ↔ CLI 서브커맨드/플래그 정합 — clean.
- Risks (잔여): 비-UI `.ts/.js` 변경 시 spurious WARN(WARN-only 라 무해). §10.5 에 jinja glob 후속 보강 권장.
- Human Approval Needed: 아니오.
