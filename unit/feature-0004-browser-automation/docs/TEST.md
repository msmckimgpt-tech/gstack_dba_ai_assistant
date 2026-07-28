---
doc_type: TEST
feature_id: feature-0004-browser-automation
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 브라우저 서비스가 새 경로에서 빌드되는지 확인
- `make browser-*` 인터페이스가 유지되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 browser build가 `feature-0004-browser-automation/src/Dockerfile`을 사용한다
- TEST-0002: `Makefile`의 `browser-*` 타깃이 기존 이름을 유지한다
- TEST-0003 (엄격한 브라우저 업무 시나리오, 2026-07-28 확정): 브라우저 서비스가 **업무 왕복
  전 구간**을 수행한다 — `health` → `session` 생성 → `goto`(실 HTTP 요청·status 수신) →
  `eval`(렌더된 DOM 텍스트 추출 + JS 실행) → `close`. 아울러 **음성 케이스**로 비허용
  scheme(`data:`)이 거부되는지 확인한다(SSRF·로컬파일 접근 차단 경계). 판정은 각 단계의
  실제 응답 payload 로 한다.

## 3. Test Run History
- 2026-07-28 (TEST-0003 엄격한 브라우저 업무 시나리오 — Environment: 라이브 `repo-browser-1`):
  - `make browser-health` → `{"ok": true}` **PASS**
  - `make browser-session` → `{"session_id": "..."}` 발급 **PASS**
  - `make browser-goto url="https://caddy/healthz"` → `{"status": 400, ...}` — 실 HTTP 요청이
    나가고 응답 status 를 수신 **PASS** (400 은 앱의 host 헤더 검증 결과이지 브라우저 결함이 아님)
  - `make browser-eval script="document.body.innerText..."` → `"Invalid host header"` —
    **렌더된 DOM 텍스트를 추출**했다. 즉 페이지 로드·렌더·DOM 접근이 end-to-end 로 동작한다 **PASS**
  - `make browser-eval script="String(1+1)+'/'+document.readyState"` → `"2/complete"` —
    **JS 실행 + 로드 완료 상태** 확인 **PASS**
  - 음성 케이스: `make browser-goto url="data:text/html,<h1>hi</h1>"` →
    `HTTP 400 {"detail":"unsupported url scheme"}` — **비허용 scheme 거부 확인 PASS**
    (의도된 보안 가드. 결함 아님)
  - `make browser-close` → `{"ok": true}` **PASS**
  - 판정: **PASS**. TEST-0003 을 placeholder 에서 실 시나리오로 확정하고 본 Run 으로 닫는다.
  - 미커버(의도): 인증이 필요한 사내 대상 사이트의 업무 자동화는 대상 자격증명이 있어야 하며
    본 시나리오 범위 밖이다. 실제 화면 검증이 필요한 웹/UI 완료 게이트는 PB-0008
    (Windows-browser)이 담당한다 — 본 서비스는 WSL 내부 headless 로 그것을 대체하지 않는다.

- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 브라우저 시나리오는 후속 작성 예정
