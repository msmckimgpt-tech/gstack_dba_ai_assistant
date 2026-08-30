---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, proxy, tls, security]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0006-lan-proxy-access
linked_unit: unit/feature-0006-lan-proxy-access
created: 2026-05-26
sources:
  - ../../unit/feature-0006-lan-proxy-access/docs/FUNCTION.md
  - ../../docs/SECURITY.md
---

# Feature — LAN Proxy Access

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0006-lan-proxy-access |
| 상태 | active |
| 정본 | [[../../unit/feature-0006-lan-proxy-access/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | Caddy TLS proxy · Windows port proxy · 인증서 |

## 1. 개요

**Caddy** TLS 프록시 + **Windows `netsh` port proxy** 자산. 외부 LAN 노출 endpoint 의 TLS 종단 책임 + `X-Forwarded-For` trust 정합 (SECURITY.md §9.7) 의 정본 위치.

## 2. 상세

### 2.1 책임 경계

- **입력**: `WEB_*` env, `ENABLE_WEB_TLS_PROXY`, Windows 포트 프록시 운영 절차
- **출력**: Caddy 프록시 설정, Windows 운영 스크립트, TLS 관련 문서
- **side-effect**: `../../artifacts/certs/` 인증서 디렉토리

### 2.2 핵심 흐름

1. 루트 compose 가 feature 경로 Caddyfile 마운트
2. `make web-tls-cert` 가 `artifacts/certs/` 인증서 생성
3. 운영자가 Windows 스크립트로 LAN port-proxy 설정

### 2.3 X-Forwarded-For trust 정책 (AC-0004, ADR-0017 cascade)

Caddyfile 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` directive 강제 → web upstream 의 `X-Forwarded-For` 는 **항상 단일 hop client_ip**. multi-hop / spoof 방지.

```caddy
https://{$WEB_PUBLIC_HOST}, :443 {
  reverse_proxy web:8000 {
    header_up X-Forwarded-For {client_ip}
  }
}
```

feature-0003 의 [[feature-0003-agent-web-ui|`_get_client_ip()`]] (AC-0205~0207) 와 dual ownership 으로 정합.

## 3. 특징

- TLS 종단 = Caddy 단일 hop (single TLS termination 원칙 — TASK-0057)
- dev 환경은 `docker-compose.override.yml` 로 web 컨테이너 plain HTTP 가동 (browser 자동화 친화)
- Windows scheduled task 로 LAN port-proxy 영속화
- **엣지 보안 헤더 일괄 부착** (2026-08-11, 정본 feature-0003 `TASK-20260811T1830-api-exposure-hardening`) — `Caddyfile` 에서 nosniff · X-Frame-Options · Referrer-Policy · Permissions-Policy 를 일괄 부착 + `Server` 제거 + CSP Report-Only. **HSTS 는 의도적 제외** — `/trust` 평문 CA 번들 배포와 충돌하고 헤더가 호스트 단위라 경로 예외가 불가능하다.
- **평문 HTTP 표면은 두 자리다** (2026-08-28, 정본 feature-0043 P0-AC) — `/trust/*` 에 더해 브리지 설치 스크립트 `/static/agent/bridge_setup.sh`·`.ps1` **두 파일만** 평문으로 연다. 같은 부트스트랩 데드락이기 때문이다: 스크립트가 하는 첫 일이 사내 CA 를 받아 신뢰시키는 것인데 그 스크립트 자신을 https 로만 주면 CA 없는 머신은 받을 수 없다. `/static/*` 를 통째로 열지 않은 이유는 범위가 예외가 감당하려던 것보다 훨씬 넓어지기 때문이고, 평문의 위험은 **지문·체크섬 대조**가 덮는다 — 대조 값은 https(웹 콘솔)로 온 명령에 실려 있어 바꿔치려면 두 채널을 동시에 잡아야 하고, 스크립트는 값이 어긋나면 실행을 중단한다.
- **롤링 배포와의 결합 계약** (2026-08-11, 정본 feature-0014 `20260811T1557-edge-rolling-gate`) — Caddy passive 격리(`fail_duration` 30s)는 값 그대로 유지하고(인하는 실장애 격리를 함께 약화시킨다), 대신 `bin/deploy-web.sh` 가 다음 replica 를 내리기 전에 **엣지 후보 복귀**(admin API `fails==0` + Caddy→replica `/livez` 실도달)를 확인한다. `Caddyfile` 주석이 이 결합 계약을 고정한다 — 종전에는 실측 10초 롤링 간격이 30s 격리 창보다 짧아 available upstream 이 0 이 되며 배포당 12~17초 전면 503 이 났다.

## 4. 사용법

```bash
make web-tls-cert     # 인증서 생성
make caddy-up         # Caddy 기동
# Windows 운영
src/windows/port-proxy-add.bat
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0001-platform-runtime]] — Web/TLS 운영 자산 공유

### 5.2 본 feature 를 의존하는 feature

- [[feature-0003-agent-web-ui]] — `_get_client_ip()` trust 정합 의존
- [[feature-0045-zd-bridge-continuity]] — `ext-tool-mcp-a/b` 2 upstream LB 가 본 feature Caddyfile 거주 ([[../Architecture/Overview|Architecture Overview]] §2.4)
- [[feature-0043-external-llm-bridge]] — 설치 스크립트 2파일의 평문 HTTP 예외가 본 feature Caddyfile 거주 (2026-08-28, P0-AC)

## 6. 관련 정본

- [[../../unit/feature-0006-lan-proxy-access/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../docs/SECURITY|docs/SECURITY.md]] §9.7 — X-Forwarded-For trust 정책

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — trust boundary
- [[../Decisions/ADR-0017-github-automation-stack]]
- [[../Decisions/ADR-0018-github-automation-decommission]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0001-platform-runtime]] · [[feature-0003-agent-web-ui]]

## 9. 외부 link

- [Caddy Server](https://caddyserver.com/)
- [Windows `netsh interface portproxy`](https://learn.microsoft.com/en-us/windows-server/networking/technologies/netsh/netsh-interface-portproxy)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/proxy` · `#domain/security`
