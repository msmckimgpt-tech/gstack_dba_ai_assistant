---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, caddy, tls]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [Caddy Server, Caddy v2]
tags: [caddy, tls, proxy]
---

# Caddy

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (OSS, HTTPS server / reverse proxy) |
| 본 프로젝트 사용 | feature-0006 의 TLS 종단 + LAN 노출 진입점 |

## 1. 개요

Go 기반 HTTPS server / reverse proxy. 본 프로젝트의 외부 LAN 노출 endpoint TLS 종단 + `X-Forwarded-For` trust 정합 (ADR-0017 cascade) 책임.

## 2. 상세

### 2.1 본 프로젝트 사용

- `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`
- `reverse_proxy web-a:8000 web-b:8000` (feature-0014 무중단 롤링 LB · active health) + `header_up X-Forwarded-For {client_ip}` directive (AC-0004)
- `/api/ai/mcp*` 는 `ext-tool-mcp-a:8971 ext-tool-mcp-b:8971` 2 upstream (`lb_policy ip_hash` · passive 격리 `fail_duration 5s` — 이 전송은 GET 에 4xx 로 답하는 것이 정상이라 active health 를 두지 않는다, feature-0045) + `Authorization` 헤더 **존재** 요구로 익명 스트림 개설 차단 (feature-0041)
- `/internal/*` 는 엣지에서 `respond 404` — 배포 드레인 제어 창구가 외부로 나가면 그 자체가 서비스 거부다(앱의 loopback 판정이 정본, 엣지는 한 겹 더, feature-0045)
- 인증서 = `artifacts/certs/` (volume mount)

### 2.2 X-Forwarded-For trust 강제

`{client_ip}` placeholder = Caddy 가 본 TCP peer IP 로 덮어씀 → multi-hop chain / 클라이언트 spoof 차단. feature-0003 `_get_client_ip()` 와 dual ownership.

### 2.3 본 프로젝트와의 관계

- single TLS termination 원칙 (TASK-0057)
- dev 환경은 `docker-compose.override.yml` 로 web 컨테이너 plain HTTP 가동 (browser 자동화 친화)

## 3. 특징

- 자동 cert (Let's Encrypt) 또는 수동 cert 모두 지원
- `WEB_PUBLIC_HOST` env 기반 동적 host 분기

## 4. 인용 source

- [[../Features/feature-0006-lan-proxy-access]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §9.7

## 5. 관련 entity

- 없음

## 6. 관련 concept

- [[../concepts/audit-subsystem|audit subsystem (X-Forwarded-For 정합)]]

## 7. 외부 link

- [Caddy Server](https://caddyserver.com/)
- [Caddyfile reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
