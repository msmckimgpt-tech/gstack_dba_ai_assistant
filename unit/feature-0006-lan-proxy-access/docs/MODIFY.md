---
doc_type: MODIFY
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260520-0010
- Date: 2026-05-21
- Related Requirement: TASK-0006 (= TASK-0087 in feature-0003), REQ-20260520-0002
- Summary: Caddy 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 클라이언트로부터 받은 임의 `X-Forwarded-For` 를 무시하고 본인이 본 TCP peer IP 로 덮어쓴다. 단일 hop XFF 정규화 — multi-hop / 클라이언트 spoof 모두 차단. feature-0003 의 `_get_client_ip()` 조건부 trust (env `WEB_TRUSTED_PROXIES`) 와 dual ownership cycle.
- Files:
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`: `reverse_proxy web:8000` 블록 안에 `header_up X-Forwarded-For {client_ip}` 한 줄 추가 (기존 `header_up X-Forwarded-Proto https`, `header_up X-Forwarded-Port 443` 위에 삽입).
  - `unit/feature-0006-lan-proxy-access/docs/TASK.md`: TASK-0006 신규 entry 추가 (= TASK-0087 in feature-0003).
  - `unit/feature-0006-lan-proxy-access/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0006-lan-proxy-access/docs/REVIEW.md`: REV-20260520-0010 (dual ownership — feature-0003 REVIEW.md REV-20260520-0010 의 cross-ref).
  - `unit/feature-0006-lan-proxy-access/docs/REPORT.md`: §1 Summary 에 TASK-0006 cycle entry 추가.
  - `unit/feature-0006-lan-proxy-access/docs/TEST.md`: TEST-0004 (`caddy validate`) 추가.
  - `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md`: AC-0004 (XFF 정규화) 신설.
- Diff size: Caddyfile +1 line, docs +6 file 갱신.
- Impact:
  - **Multi-hop / spoof 차단**: 외부 클라이언트가 임의 `X-Forwarded-For` 헤더 주입을 시도해도 Caddy 가 그 헤더를 자기가 본 TCP peer IP 로 덮어쓴다. 즉 web 입장에서 XFF 는 항상 "Caddy 가 직접 본 IP" 단일 값.
  - **feature-0003 `_get_client_ip()` 와 정합**: web 의 조건부 trust 로직이 `direct_ip` (= caddy container IP) 가 `WEB_TRUSTED_PROXIES` CIDR 안일 때만 XFF 첫 토큰을 신뢰. 본 Caddy 변경으로 그 첫 토큰이 진짜 client IP (caddy 가 본 peer) 임이 보장.
  - **외부 LAN 노출 시점 대비**: 본 cycle 의 Caddy 정규화는 외부 인터넷 / 미신뢰 LAN 노출 시점에도 그대로 효과. 단 `WEB_TRUSTED_PROXIES` 가 RFC1918 전체로 권장된 본 cycle 의 결정은 사내 dev/staging 전제 — 외부 노출 시점에 별 cycle 에서 `WEB_TRUSTED_PROXIES` 좁히기 + docker-compose port mapping 변경 필요 (SECURITY.md §9.7 참조).
- Rollback Notes:
  - `header_up X-Forwarded-For {client_ip}` 한 줄 제거하면 Caddy 는 클라이언트가 보낸 XFF 를 그대로 전달. 단 feature-0003 의 `_get_client_ip()` 조건부 trust 로직이 그대로 작동하므로 audit 표면은 안전 — direct_ip 가 trusted proxy 일 때만 XFF 신뢰. 다만 multi-hop 시나리오에서 XFF 첫 토큰이 진짜 클라이언트 IP 가 아니라 임의 spoof 값이 될 수 있음. 사내 dev/staging 환경에서는 무영향.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: LAN/TLS 운영 자산을 기능 단위 구조로 이관
- Files: src/caddy/Caddyfile, src/windows/*
- Notes: 인증서와 Caddy 상태 파일은 `../../../../artifacts`에 저장

## CHG-20260424-0002
- Date: 2026-04-24
- Related Requirement: TASK-0005 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — Windows portproxy + Caddy TLS 로컬 dev 구조의 존재 이유, 인증서 artifacts/ 분리 원칙, 프로덕션 cherry-pick 궤적(Caddyfile 유지, windows/ 제외, 공인 인증서 전환) 명시. 대안은 로컬 dev 맥락 유지(nginx/traefik 제외, 프록시 없는 각 서비스 직접 TLS 제외).
- Files: unit/feature-0006-lan-proxy-access/docs/ANCHOR.md, unit/feature-0006-lan-proxy-access/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. "이 feature를 프로덕션으로" 요청 시 §3의 cherry-pick 기준이 onboarding 진입점. dev-specific 경로 제거 판단이 Conflict Protocol 없이 자연 진행.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
