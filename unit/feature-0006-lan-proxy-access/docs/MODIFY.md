---
doc_type: MODIFY
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260617-0308
- Date: 2026-06-17
- Related Requirement: REQ-0284 / TASK-0297 / AC-0554~0556 (**Major** §12.3)
- Summary: caddy(`:443`) 502 해소 + 정식 front door 화. TASK-0296 의 별 cycle 후속.
  근본 = `ENABLE_WEB_TLS=1`(web 이 8000서 HTTPS) + caddy 평문 `reverse_proxy web:8000`
  프로토콜 불일치. caddy 를 HTTPS-upstream(사내 Root CA 검증)으로 전환.
- Files:
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`: `:443` 블록 `reverse_proxy
    web:8000` 에 `transport http { tls; tls_trust_pool file /certs/rootCA.pem;
    tls_server_name {$WEB_PUBLIC_HOST} }` 추가. caddy 가 web 에 HTTPS 로 붙고 사내 Root CA
    로 leaf 검증(SNI/검증명=공개 호스트, 내부 서비스명 `web` 는 SAN 부재라 tls_server_name
    명시). 기존 `header_up X-Forwarded-For {client_ip}` 등 XFF directive(AC-0004) 보존.
  - `repo/.env` (gitignore, 비커밋): `ENABLE_WEB_TLS_PROXY=0→1`, `WEB_TRUSTED_PROXIES=
    172.18.0.0/16`(caddy dbnet 서브넷) 신설. web 이 caddy XFF 를 신뢰 → audit 실 IP 보존.
  - `unit/feature-0006-lan-proxy-access/docs/{FUNCTION,TASK,DECISIONS,REPORT,REVIEW,MODIFY}.md`.
- Diff size: Caddyfile +7 line + docs. 앱 코드 변경 0. `.env` 는 로컬(비커밋).
- Impact:
  - 테스터가 포트 없는 `https://mysql-ai.company.local`(caddy :443) 사용 가능 + `:18080`(web
    직접 TLS) 유지 — 양쪽 모두 Root CA 신뢰 후 경고 없음.
  - `caddy validate` = `Valid configuration`. one-off 테스트 caddy(:8443, dbnet) 런타임
    프록시 `/healthz`·`/` = HTTP 200 (이전 502 해소) 머지전 검증. 머지후 실 caddy 재시작.
  - audit `IpAddr` 가 caddy 컨테이너 IP(172.18.0.10) 가 아닌 실 클라이언트 IP 기록.
- Rollback Notes:
  - Caddyfile 의 `transport http { ... }` 블록 제거 시 :443 이 다시 502(평문 upstream). web
    직접 `:18080` 경로는 무영향.
  - `.env` `ENABLE_WEB_TLS_PROXY=1→0` + `WEB_TRUSTED_PROXIES` 제거 후 `docker compose up -d
    web caddy`. 단 audit 가 다시 caddy IP 만 기록(품질 회귀).
  - 외부/미신뢰 LAN 노출 시 `WEB_TRUSTED_PROXIES` 를 bridge 서브넷으로 좁히고 web port 비공개
    — SECURITY.md §9.7.

## CHG-20260617-0307
- Date: 2026-06-17
- Related Requirement: REQ-0283 / TASK-0296 / AC-0549~0553 (**Major** §12.3)
- Summary: 사내 테스터 제한 배포 직전 브라우저 "안전하지 않은 연결" 경고 제거. web 이 서빙하던
  self-signed 인증서(issuer==subject, CA 체인 없음)를 **사내 자체 Root CA 서명 leaf** 로 전환.
  `.company.local` 내부 도메인이라 공인 CA 발급 불가 → 사내 Root CA 방식 (사용자 결정 ADR-LAN-0002).
- Files:
  - `bin/tls-internal-ca.sh` (신규): Root CA(멱등, 기본 10년) 생성 + Root CA 서명 leaf(기본 825일)
    발급. SAN = `.env` 의 `WEB_PUBLIC_HOST` + `WEB_ALLOWED_HOSTS`(DNS/IP, 내부 서비스명 `web` 제외),
    `extendedKeyUsage=serverAuth`, `basicConstraints=critical,CA:FALSE`. `openssl verify` 체인 +
    issuer!=subject 자동 검증. 출력 경로는 `.env` 의 `WEB_TLS_CERT_FILE`/`WEB_TLS_KEY_FILE` 정합.
    git-common-dir 기반 경로 해석(main/worktree/비-git cwd 무관 동일 artifacts/ 로 수렴).
  - `unit/feature-0006-lan-proxy-access/src/TESTER_TLS_TRUST.md` (신규): 테스터 Root CA 신뢰 설치
    가이드 (Windows certutil/MMC · macOS Keychain · Firefox 자체 저장소 · hosts/IP 접속).
  - `unit/feature-0006-lan-proxy-access/docs/{FUNCTION,TASK,DECISIONS,REPORT,REVIEW,MODIFY}.md`: 문서.
  - `artifacts/certs/{rootCA.pem,rootCA-key.pem,mysql-ai.company.local/{fullchain,privkey}.pem}` 재생성
    (gitignore — 버전관리 밖). 기존 self-signed 는 `artifacts/certs/_backup-selfsigned-<ts>/` 백업.
- Diff size: 신규 스크립트 1 + 신규 문서 1 + docs 6 갱신. 앱 코드 변경 0.
- Impact:
  - 테스터는 `rootCA.pem` 1회 설치 후 경고 없이 신뢰된 HTTPS. leaf 갱신은 스크립트 재실행 +
    web 재시작으로 transparent(Root CA 유지 → 재설치 불필요).
  - 라이브 web `:18080` 체인 `Verify return code: 0` + HTTP 200 실측. caddy `:443` 핸드셰이크도
    `Verify code 0`(단 502 — 인증서 무관 `ENABLE_WEB_TLS`/`reverse_proxy` 프로토콜 불일치, 별 cycle).
  - 개인키 0600·서버 밖 반출 금지. 앱 인증/인가/RBAC 불변(전송 계층만).
- Rollback Notes:
  - 즉시 롤백: `artifacts/certs/_backup-selfsigned-<ts>/` 의 `fullchain.pem`/`privkey.pem` 를
    `artifacts/certs/mysql-ai.company.local/` 로 복원 후 `docker compose restart web caddy`.
    (단 self-signed 경고가 다시 표시됨 — 롤백은 신뢰 회귀.)
  - 스크립트/문서 제거는 인증서 재발급 능력만 사라질 뿐 서빙 중 인증서엔 영향 없음.
  - Root CA 키(`rootCA-key.pem`) 분실 시 갱신 불가 → 키 백업 운영 권고.

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
