---
doc_type: REVIEW
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260617-0307 [SKIPPED:non-RBAC-TLS-infra] — 사내 자체 Root CA HTTPS 신뢰 (TASK-0296)
- Date: 2026-06-17
- Change: CHG-20260617-0307 (REQ-0283, AC-0549~0553, **Major** §12.3). self-signed 인증서 →
  사내 자체 Root CA 서명 leaf 로 전환하여 브라우저 "안전하지 않은 연결" 경고 제거.
- 변경 산출물:
  - `bin/tls-internal-ca.sh` (신규) — Root CA(멱등, 10년) + leaf(825일) 발급, SAN/EKU/
    체인 자동 검증. 비-secret 코드(개인키 생성 로직만, 키 자체는 artifacts/).
  - `unit/feature-0006-lan-proxy-access/src/TESTER_TLS_TRUST.md` (신규) — 테스터 신뢰
    설치 가이드 (Windows/macOS/Firefox + hosts/IP).
  - FUNCTION/TASK/DECISIONS/REPORT 문서.
  - `artifacts/certs/*` 재생성 (gitignore — 버전관리 밖).
- 보안 자체 점검:
  1. **개인키 격리** — `rootCA-key.pem` / `<host>/privkey.pem` 0600, `artifacts/`
     (gitignore), 서버 밖 반출 금지. 배포 대상은 `rootCA.pem`(공개)만. ✓ SECURITY.md §5/§6.
  2. **Root CA blast radius** — Root CA(CA:TRUE)를 테스터가 신뢰하면 그 CA 가 서명한
     *모든* 도메인 인증서를 신뢰. 사내 한정·소수 테스터·키 격리로 수용(사용자 결정
     ADR-LAN-0002). **하드닝 권고(별 cycle)**: Root CA 에 `nameConstraints=permitted;
     DNS:.company.local` 적용 시 CA 키 유출 시에도 서명 가능 도메인을 제한. 일부 구형
     클라이언트 호환성 검토 필요해 본 배포에서는 보류(경고 제거 우선).
  3. **self-signed 제거 검증** — AC-0550 `issuer != subject` + `openssl verify` OK
     강제. 라이브 web `:18080` 체인 `Verify return code: 0` + HTTP 200 실측. ✓
  4. **leaf 만료 운영** — 825일 후 미갱신 시 테스터 경고 재발. 멱등 재실행으로 transparent
     갱신(Root CA 유지). 운영 메모 TESTER_TLS_TRUST.md + FUNCTION §12 Observability.
  5. **auth/authz 무변경** — 앱 인증·인가 로직, RBAC catalog, 권한 모델 불변. TLS 전송
     계층만. → SECURITY.md §3 "인증/인가 변경" 비해당.
- Outside-voice (Codex/subagent): **SKIPPED** — RBAC/권한 catalog 변경 아님
  (`feedback_outside_voice_for_rbac.md` 트리거 비해당). 앱 코드 미변경(스크립트+문서+
  인증서 재생성). 결정(전략)은 사용자 사전 승인. 보안 위험은 본 self-review 에 명시.
- 미해결(별 cycle): caddy `:443` 502 (`ENABLE_WEB_TLS=1` + 평문 `reverse_proxy web:8000`
  불일치 — 인증서 무관 기존 라우팅). 테스터 경로 = web 직접 TLS `:18080`.
- Risk:
  1. 외부/미신뢰 LAN 노출 시 SECURITY.md §7.2 + §9.7 보완 선행 필요(IP allowlist /
     token 비밀번호 / `WEB_TRUSTED_PROXIES` 협소화).
  2. Root CA 키 분실 → 갱신 불가(새 CA 발급 = 테스터 전원 재설치). 키 백업 운영 권고.

## REV-20260520-0010 [AGENT-TEAM:codex-outside-voice] — dual ownership cross-ref
- Date: 2026-05-21
- Decision: TASK-0006 (= TASK-0087 in feature-0003, REQ-20260520-0002, **Major** §12.3) — Caddy 의 `reverse_proxy` 블록에 `header_up X-Forwarded-For {client_ip}` 추가하여 단일 hop XFF 정규화. Codex outside voice review verdict **NEEDS_REVISION** (6 findings Major 5 + Minor 1) 중 본 feature 에 직접 관련된 Finding (Major #2 Caddy 문법 + Major #3 Caddy `private_ranges` 위험) 흡수.
- Mode: SUBAGENT (Codex CLI consult mode, gpt-5 default, model_reasoning_effort=high, read-only sandbox)
- Reason: TASK-0073 Eng review E3 의 deferred 항목 (사내 LAN + Caddy proxy 전제의 XFF trust 가 외부 LAN 노출 시 IP spoof 위험) 의 reverse proxy 측 해결. feature-0003 의 `_get_client_ip()` 조건부 trust 와 dual ownership.
- 본 feature 관련 finding 흡수:
  - **Major #2 (Caddy 문법 부정확)** — Plan v1 의 `reverse_proxy { trusted_proxies static private_ranges }` 가 Caddy v2 문서 기준 부정확. Caddy 권장은 global option `servers > trusted_proxies static <ranges>`. → **흡수**: trusted_proxies 추가 대신 `header_up X-Forwarded-For {client_ip}` 로 단일 hop XFF 정규화 (더 안전한 대안). multi-hop / spoof 모두 차단.
  - **Major #3 (Caddy `private_ranges` global trust 위험)** — Caddy 가 직접 사내 LAN 클라이언트를 받는 구조에서 `trusted_proxies static private_ranges` global 은 private IP 클라이언트의 XFF 신뢰 → spoof. → **흡수**: global trusted_proxies 추가 안 함 (Major #2 와 동일 결정 — XFF 정규화로 대체).
- Cross-ref: 본 review 의 정본 (전체 6 findings + verdict + 사용자 in-cycle 결정 + 흡수 매트릭스) 은 [`unit/feature-0003-agent-web-ui/docs/REVIEW.md`](../../feature-0003-agent-web-ui/docs/REVIEW.md) REV-20260520-0010 에 lock-in. 본 entry 는 feature-0006 측 cross-ref + Caddyfile 변경 정합성 확인용.
- Risk:
  1. Caddy XFF 정규화의 single-hop 의존성 — Caddy 앞에 upstream proxy (cloudflare/ALB) 가 추가되면 `{client_ip}` 가 upstream proxy IP 가 되어 진짜 클라이언트 IP 가 audit 에서 사라짐. 별 cycle 검토 필요.
  2. Caddyfile 의 `header_up X-Forwarded-For {client_ip}` 가 Caddy v2 의 `{client_ip}` placeholder 에 의존. Caddy major version downgrade 시 동작 차이 가능 — `Dockerfile` 의 Caddy 이미지 pin 확인 필요.
- Alt 거부:
  - global `trusted_proxies static <narrow>`: Caddy 의 XFF 자체를 정규화하지 않으면 web 의 조건부 trust 로직이 클라이언트 spoof XFF 를 한 번 더 검증해야 함 — 두 layer defense 보다 Caddy 가 source-of-truth 로 작동하는 단순 정규화가 더 견고.
  - Caddy v2 `trusted_proxies_strict`: 본 시스템 (Caddy 단일 hop) 에서는 효과 미미.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: 네트워크 운영 자산만 버전관리하고 인증서/상태는 외부 산출물로 둔다
- Reason: 민감 자산과 코드 자산을 분리하기 위함
- Risk: 실제 LAN 환경 검증 전까지 운영 가정이 남아 있다
