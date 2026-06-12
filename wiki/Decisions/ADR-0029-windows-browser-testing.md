---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, testing, browser, security]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0029
linked_canonical: ../../docs/DECISIONS.md#ADR-0029
status_adr: accepted
created: 2026-06-04
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0029 — 실제 Windows 브라우저 AI 자동 검증 (PB-0008)

> **이 노트는 사람용 mirror 다.** 결정 본문 정본은 [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0029]] 안에 있다. drift 시 정본 우선.

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0029]] |
| 상태 | accepted (feature-0008, REQ-20260604, 2026-06-04) |
| 결정일 | 2026-06-04 |

## 1. 한 문장 요약

웹/UI 변경의 완료 검증을 WSL 내부 headless 가 아닌 **실제 Windows 브라우저를 AI 가 CDP 자동 구동**하는 워크플로(PB-0008)로 강제한다 — headless 와 실 Windows 화면의 렌더링 괴리 해소.

## 2. 결정의 핵심

- **드라이버 `bin/win-browser.py`**: Playwright `connect_over_cdp` 로 Windows Chrome/Edge attach. `doctor` / `launch` / `down` + `goto` / `click` / `type` / `eval` / `text` / `screenshot` + 시나리오 일괄 `run`. 브리지 모드 자동 감지.
- **브리지**: WSL2 Chrome CDP 가 127.0.0.1 에만 바인딩되는 제약을 (A) vEthernet 한정 portproxy relay (`bin/win-browser-setup.ps1`, 관리자 1회) 또는 (B) mirrored networking 으로 해소. 가이드 `bin/WIN-BROWSER-SETUP.md`.
- **환경 분류**: 각 feature `docs/TEST.md` §3 Environment 를 `CLI` / `WSL-headless` / `Windows-browser` 로 구분. **웹/UI 화면 검증은 `Windows-browser` 만 인정** (CLI·WSL-headless 는 서버 계약 검증용).
- **완료 게이트**: AGENTS.md §15.4.1 + §10.5 조건부 규칙 + `bin/verify-completion.sh` check #13 (WARN-only v1). 절차 = **PB-0008**. enforcement 는 wiki check #12 와 동일 staged rollout (후속 cycle MUST 격상).
- **in-loop 대화형 도구**: Playwright MCP (`bin/playwright-mcp.sh` + `.mcp.json`) 가 win-browser.py 무권한 relay 에 attach — 모델 루프에서 `browser_snapshot`/`click`/`type` 직접 사용.

## 3. 보안 경계

- CDP = 무인증 원격제어 채널 → setup.ps1 이 vEthernet 한정 + 방화벽 Private/서브넷으로 LAN 노출 차단. `--remote-debugging-address=0.0.0.0` 미사용, `--remote-allow-origins` 구체 origin, per-user 격리 프로필. (§18.8 security 패널 F1/F2/F4/F5 반영.)
- gstack `/browse` · feature-0004 headless 는 폐기 아닌 **보조**(빠른 탐색)로 공존.

## 4. 영향 받는 영역

- `bin/win-browser.py`, `bin/win-browser-setup.ps1`, `bin/WIN-BROWSER-SETUP.md`, `bin/playwright-mcp.sh`, `.mcp.json`
- 관련 feature: [[../Features/feature-0008-windows-browser-testing]]
- 완료 게이트: `bin/verify-completion.sh` check #13

## 5. 관련 노트

- [[../../docs/DECISIONS|정본]]
- [[../Features/feature-0008-windows-browser-testing]]
- [[../entities/playwright]]
- [[ADR-0026-bedrock-llm-provider]] — 같은 시기 feature 확장 맥락

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- feature-0008 의 정본 ADR (PB-0008 playbook)

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/testing` · `#domain/browser` · `#domain/security`
