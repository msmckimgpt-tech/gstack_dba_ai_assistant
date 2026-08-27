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

## REV-20260604-0003 [SKIPPED:no-rbac-no-schema-no-secret-handling] — 무권한 auto-relay follow-up
- challenge: 무권한 userspace relay 도입이 새로운 보안 노출을 만드는가 (지난 패널 F1 CRITICAL 재발 여부).
- Related Change: bin/win-browser.py (relay_start/find_win_python/launch auto-relay + ignore-cert), SETUP.md, PB-0008, feature docs.
- 판단: 본 변경은 RBAC/스키마/시크릿 처리 무관한 opt-in 로컬 dev 도구. 신규 relay 의 보안 posture 는
  REV-0001 에서 ACCEPT 된 portproxy 와 **동일** — RELAY_SCRIPT 가 `start_server(vEthernet-IP, 9223)`
  로 vEthernet(WSL) IP 에만 바인딩(0.0.0.0 아님)하여 LAN 노출 없음(F1 정합). 실측에서 `172.28.64.1:9223`
  바인딩 + WSL 도달 + LAN 비노출 확인. relay_stop 의 PS 매칭자(marker)는 상수(주입 없음). 스크립트는
  per-user `%LOCALAPPDATA%` 에 기록(F4 정합). find_win_python 은 Store stub 제외(py 런처/where 필터).
  `--ignore-certificate-errors` 는 전용 격리 프로필 + 로컬 self-signed 대상 한정(env 로 비활성 가능).
  → 신규 보안 표면 없음. 전 패널(REV-0001/0002)의 ACCEPT 범위 내. 별도 패널 불요로 판단(SKIPPED).
- 검증: 실제 Windows Chrome 148 e2e (TEST.md §3 Run 003/004) + 단위 테스트 10/10 + py_compile.
- Human Approval Needed: 아니오.

## REV-20260604-0004 [SKIPPED:no-rbac-no-schema-no-secret-handling] — Playwright MCP 통합 검토·적용
- challenge: 외부 구성요소(Playwright MCP / Claude for Chrome)가 본 환경에 적합한가, 적용 시 신규 위험은.
- Related Change: bin/playwright-mcp.sh, .mcp.json, SETUP.md/CLAUDE.md/PB-0008 문서.
- 판단: 웹 조사(2건) 근거 — **Playwright MCP 채택**(--cdp-endpoint 로 실행 중 브라우저 attach,
  로컬 바이너리 불요, a11y 스냅샷, node/npx; Claude Code project `.mcp.json` 첫 사용 승인). **Claude
  for Chrome 미채택**(Chrome 확장·MCP/API 없음·수동 UI → 프로그래매틱/헤드리스 dev 워크플로 부적합).
  보안: MCP 는 이미 REV-0001/0003 에서 ACCEPT 된 동일 vEthernet 한정 relay 에 attach — 신규 노출
  표면 없음. `.mcp.json` 는 첫 사용 시 사용자 승인 게이트(자동 활성 아님). RBAC/스키마/시크릿 무관.
  → 별도 패널 불요(SKIPPED).
- 검증: MCP 서버 JSON-RPC e2e 스모크 PASS — initialize(serverInfo Playwright) + browser_navigate →
  실제 Windows Chrome 가 https://localhost:18080 로드 + Page Title "DQA — Database Query Assistant" 반환.
- Human Approval Needed: 아니오 (적용은 opt-in 승인 게이트, 사용자가 enable).

## REV-20260828T112000-verify-session [SUBAGENT:general-purpose] — BLOCK → 전건 수정 후 PASS

- Related TASK: feature-0008-windows-browser-testing / `TASK-20260828T103000-verify-session`
- Risk: **Minor** (§12.3) — 기존 자격증명 재사용(새 비밀 0·계정 생성 0), 인증 서버 코드 변경 0,
  검증 도구 한정. 단 **자격증명을 다루는 도구**라 보안 축을 Critical 수준으로 검토했다.
- Human Approval Needed: no (범위 전환은 사용자 결정 2026-08-28 로 확보)
- Timestamp: 2026-08-28T11:20:00+09:00

### 무엇을 만들었나 — 그리고 왜 이 지점인가

문제는 "PB-0008 이 로그인 화면 밖으로 못 나간다" 였다. 드라이버가 **전용 격리 프로필**로
브라우저를 띄우는 것은 옳은 설계(사용자 개인 브라우저 무접촉)지만, 그 프로필에 세션이 없어
검증이 도달 가능한 화면이 로그인 폼뿐이었다. 실측으로 두 cycle 연속(브리지 스크롤 수정,
그 증적 cycle) 화면 실측을 "세션 부재" 사유로 미수행 처리했다 — 완료 게이트 check #13 이
형식만 남는 상태였다.

그래서 세션 발급을 드라이버의 1급 동작으로 올렸다. 계정은 `.env` 의 기존 `WEB_BOOTSTRAP_ADMIN_*`
를 그대로 쓴다(사용자 결정) — 새 비밀·새 계정 없이 관리콘솔까지 한 세션으로 검증된다.

### 채택하지 않은 대안

- **전용 검증 계정 신설** — 최소권한·감사 분리는 낫지만 새 비밀 1건과 계정 생성(인증 인접)이
  들고, operator 권한으로는 `/admin` 검증이 불가해 결국 admin 이 다시 필요하다. 사용자 결정으로 불채택.
- **쿠키를 API 로 받아 주입** — 실제 로그인 폼을 타지 않아 로그인 화면 회귀를 못 본다.
  폼 로그인이 사용자 경로와 같고 부수적으로 그 화면도 검증한다.
- **사용자 개인 브라우저 프로필 재사용** — 격리 원칙을 깬다. FUNCTION §4 에 범위 밖으로 유지.

### 적대 검증 (subagent 1회 — codex 사용량 한도로 대체, 사용자 승인)

판정 **BLOCK**. 내가 못 본 것 두 가지가 결정적이었다.

- **[P1] origin 무검증** — `--origin` 이 검사 없이 `page.fill("#loginPassword", pw)` 로 이어지고
  브라우저는 `--ignore-certificate-errors` 로 뜬다. 이 저장소의 AI 는 대화·MCP 로 신뢰할 수 없는
  입력을 읽으므로, 주입된 지시 하나면 관리자 비밀번호가 공격자 호스트의 같은 id 에 타이핑된다.
  나는 "출력·argv 를 막았다" 로 계약 1을 다 지켰다고 봤는데, **목적지**를 잊고 있었다.
  → loopback + `.env` 선언 host fail-closed 게이트, 확장은 `--allow-remote-origin` 명시.
- **[P1] 내 테스트가 계약을 하나도 잠그지 않았다** — 리뷰가 뮤턴트 5종(`eprint(pw)` / 대기루프
  **밖** 재제출 / exit 0 고정 / 멱등 분기 사망 / `session-logout`→login 오배선)을 **동시에**
  적용하고도 26건 전건 통과시켰다. 내가 앞서 돌린 "뮤테이션 5종 KILL" 은 **내 테스트가 잡도록
  생긴 모양의 뮤턴트만** 고른 자기충족이었다 — 문자열이 그 자리에 있는지는 동작이 그러한지와
  다른 질문이다. → 가짜 page 더블로 명령을 실제 구동하는 스위트로 전면 교체(40건).
- P2 8건(멱등 경로 플래그 누락 · `is_locked` vacuous · 거부/무응답 혼동 · check 프로브 실패 은폐 ·
  logout 무효인데 ok · `.env` 인라인 주석 · 빈 탭 누수 · 플레이북 stale 진입점) 도 전건 수정.

### 검증

- 신규 **40건 PASS** · `make test` exit 0(전체 스위트, feature-0008 을 pytest 경로에 편입).
- **뮤테이션 8종 전건 KILL** — 리뷰가 쓴 5종 전부 + 신규 가드 3종(origin·DEBUG·logout ok).
  ⚠ 초안 검증에서 M4 가 "생존" 으로 보였으나 확인 결과 **치환이 적용되지 않은 것**이었다
  (`diff` 0줄) — 뮤테이션은 적용 여부부터 확인해야 한다.
- 라이브 실증(실 Windows Chrome 151, relay): `logout → check(--require-auth → exit 1) →
  login → check(exit 0)` 왕복 · 허용목록 밖 origin 거부(exit 1) · 멱등 재호출(`already:true`).
- **직전 cycle 의 미수행 항목을 이 세션으로 닫았다** — 브리지 대화에서 사용자가 최상단에 스크롤을
  둔 채 20초 관측: `scrollTop` 20/20 샘플 0(불변), `/api/progress` 가 클라이언트에 보고한
  `run_id: ""`(서버 수정 확증), page error 0. `/api/history` 4회는 무관한 `_liveSyncTick`
  (스크롤 미이동) 으로 출처 확인.
