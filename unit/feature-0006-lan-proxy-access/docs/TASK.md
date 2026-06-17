---
doc_type: TASK
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: medium
- Last Updated: 2026-06-17

## 2. Task Queue
- [x] TASK-0001 Caddy 설정 이관
- [x] TASK-0002 Windows LAN 스크립트 이관
- [x] TASK-0003 루트 TLS 경로를 `../../../../artifacts` 기준으로 수정
- [x] TASK-0004 엄격한 네트워크 운영 시나리오 정의
- [x] TASK-0005 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입, dev → prod cherry-pick 궤적 명시)
- [x] TASK-0006 (= **TASK-0087** in feature-0003, REQ-20260520-0002, **Major** §12.3 — Caddy XFF 정규화). `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가 — Caddy 가 받은 임의 `X-Forwarded-For` 를 본인이 본 TCP peer IP 로 덮어쓴다. multi-hop / spoof 차단. feature-0003 의 `_get_client_ip()` 조건부 trust 와 dual ownership cycle. 본 cycle CHG-20260520-0010, REV-20260520-0010 on `ai/claude/0087-lan-trust-hardening` worktree.
- [x] TASK-0296 (REQ-0283, AC-0549~0553, **Major** §12.3, CHG-20260617-0307/REV-20260617-0307 — 사내 테스터 제한 배포 HTTPS 신뢰). self-signed → 사내 자체 Root CA 서명 leaf 로 전환. `bin/tls-internal-ca.sh`(멱등 Root CA 10년 + leaf 825일, SAN/EKU/체인 검증) + 테스터 신뢰 설치 가이드 `src/TESTER_TLS_TRUST.md`. web `:18080` 라이브 체인 검증 `Verify return code: 0` + HTTP 200. **발견(별 cycle)**: caddy `:443` 는 `ENABLE_WEB_TLS=1`(web 이 8000 서 HTTPS) + 평문 `reverse_proxy web:8000` 불일치로 502 — 인증서와 무관한 기존 라우팅 이슈. 인증서 핸드셰이크 자체는 :443 도 `Verify code 0`.
- [x] TASK-0297 (REQ-0284, AC-0554~0556, **Major** §12.3, CHG-20260617-0308/REV-20260617-0308 — caddy :443 정식 front door). TASK-0296 의 별 cycle 후속. Caddyfile `reverse_proxy` 를 HTTPS-upstream(`transport http { tls; tls_trust_pool file /certs/rootCA.pem; tls_server_name {$WEB_PUBLIC_HOST} }`)으로 전환해 :443 502 해소(XFF directive 보존). `.env` `ENABLE_WEB_TLS_PROXY=1`+`WEB_TRUSTED_PROXIES=172.18.0.0/16` 로 audit 실 클라이언트 IP 보존(§9.7). `caddy validate`=Valid + one-off 테스트 caddy(:8443) 런타임 프록시 HTTP 200 머지전 검증. 결과: 포트 없는 `https://mysql-ai.company.local` + `:18080` 양쪽 신뢰 HTTPS.
- [x] TASK-0298 (REQ-0285, AC-0557~0561, **Major** §12.3, CHG-20260617-0309/REV-20260617-0309, ADR-LAN-0004 — 테스터 Root CA 원클릭 설치 번들). PC 마다 수동 설치 번거로움 해소. `bin/trust-bundle.sh` 가 `src/trust-bundle/*.tmpl`(win .bat·mac .command·index.html — 인증서 base64 임베드·지문 주입) → `artifacts/trust-bundle/` 조립(임베드 디코드 지문 자가검증). Caddyfile `:80`/`:443` 양쪽에 `/trust/` `file_server` carve-out(HTTP 서빙 = CA 미설치 상태 경고 없는 다운로드용) + compose `/srv/trust` 마운트. 단일 자가완결 스크립트(자가-상승·지문 재검증·certutil/security). **브라우저 자동설치는 OS 보안경계상 불가** — 승인 1회 필수. 신뢰 부트스트랩 한계는 지문 노출+재검증+운영자 out-of-band 공유로 완화. validate=Valid + one-off 테스트 caddy(:8080/:8443) `/trust/` 200·bare `/trust`→301·앱 200 머지전 검증. tls-internal-ca.sh 가 끝에서 자동 호출.

## 3. In Progress
- TASK-0004 엄격한 네트워크 시나리오 정의 대기

## 4. Blocked
- 없음

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003

## 6. Next Action
- TLS 프록시와 LAN 접속에 대한 후속 검증 시나리오를 `TEST.md`에 확장한다.

## 7. Completion Checklist
- [x] 운영 자산 이관이 완료되었다
- [x] 루트 compose/Makefile 경로가 반영되었다
- [x] 문서가 현재 구조를 설명한다
- [ ] 엄격한 네트워크 시나리오가 확정되었다
