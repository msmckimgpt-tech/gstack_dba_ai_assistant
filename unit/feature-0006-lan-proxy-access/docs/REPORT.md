---
doc_type: REPORT
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
**2026-06-17 TASK-0299 완료 — 설치 스크립트 실행 버그 2종 수정** (CHG-20260617-0310,
REV-20260617-0310, REQ-0286, AC-0562~0563, **Minor** §12.3). 라이브에서 Windows `.bat` 실행 시
`echo`→`cho`·base64 명령실행 파싱붕괴 제보. ①LF+UTF-8+`chcp 65001`→cmd.exe 코드페이지 오프셋
상실 → ASCII전용+CRLF+chcp제거(trust-bundle.sh CRLF출력+비-ASCII die). ②지문 비교가 PEM **파일**
해시 vs 인증서 **DER** 지문이라 항상 불일치(잠복) → DER SHA-256(win X509Certificate2.RawData, mac
openssl -fingerprint)로 통일. cmd.exe 실측: neuter 후 echo/지문/디코드/지문검증(ACTUAL==FP_HEX)
전구간 정상. 배포=`bin/trust-bundle.sh` 재실행(file_server 즉시 서빙).

**2026-06-17 TASK-0298 완료 — 테스터 Root CA 원클릭 설치 번들** (CHG-20260617-0309,
REV-20260617-0309, REQ-0285, AC-0557~0561, **Major** §12.3, ADR-LAN-0004). 테스터 PC 마다
수동 인증서 이동 번거로움 해소. web 서버가 `http://<host>/trust/` 에서 OS별 단일 자가완결 설치
스크립트(Root CA base64 임베드, 자가-상승, 지문 재검증, certutil/security) + OS감지 다운로드
페이지(지문 대조 안내) 제공. `bin/trust-bundle.sh`(템플릿→`artifacts/trust-bundle/` 조립, 임베드
지문 자가검증) + Caddyfile `:80`/`:443` `/trust/` `file_server` carve-out + compose `/srv/trust`
마운트 + `tls-internal-ca.sh` 자동 호출. **브라우저 방문 자동설치는 OS 보안경계상 불가**(승인 1회
필수) — 신뢰 부트스트랩 한계는 지문 노출+재검증+운영자 out-of-band 공유로 완화. validate=Valid +
one-off 테스트 caddy `/trust/` 200·bare `/trust`→301·앱 200 머지전 검증.

**2026-06-17 TASK-0297 완료 — caddy :443 정식 front door** (CHG-20260617-0308,
REV-20260617-0308, REQ-0284, AC-0554~0556, **Major** §12.3, ADR-LAN-0003). TASK-0296 의
별 cycle 후속 — caddy `:443` 502 해소. 근본 = `ENABLE_WEB_TLS=1`(web 8000 HTTPS) + caddy
평문 `reverse_proxy`. Caddyfile 을 HTTPS-upstream(`transport http { tls; tls_trust_pool
file /certs/rootCA.pem; tls_server_name {$WEB_PUBLIC_HOST} }`)으로 전환(XFF directive 보존).
`.env`(로컬) `ENABLE_WEB_TLS_PROXY=1`+`WEB_TRUSTED_PROXIES=172.18.0.0/16` 로 audit 실 IP 보존
(§9.7). `caddy validate`=Valid + one-off 테스트 caddy(:8443) 런타임 200 머지전 검증. 결과:
포트 없는 `https://mysql-ai.company.local`(caddy :443) + `:18080`(web 직접) 양쪽 신뢰 HTTPS.

**2026-06-17 TASK-0296 완료 — 사내 자체 Root CA HTTPS 신뢰** (CHG-20260617-0307,
REV-20260617-0307, REQ-0283, AC-0549~0553, **Major** §12.3). 사내 테스터 제한 배포 직전 브라우저
"안전하지 않은 연결" 경고의 근본 원인(self-signed 인증서, issuer==subject, CA 체인
없음)을 제거. `.company.local` 내부 도메인이라 공인 CA 발급 불가 → 사내 자체 Root CA
방식 채택(사용자 결정 ADR-LAN-0002). 신규 `bin/tls-internal-ca.sh`(멱등 Root CA 10년
+ Root CA 서명 leaf 825일, SAN=`WEB_PUBLIC_HOST`+`WEB_ALLOWED_HOSTS`, EKU serverAuth,
체인 자동검증) + 테스터 신뢰 설치 가이드 `src/TESTER_TLS_TRUST.md`. web `:18080` 라이브
체인 검증 `Verify return code: 0` + HTTP 200 실측. 개인키 0600·`artifacts/`(gitignore).
배포: web/caddy 재시작(인증서 bind-mount ro, rebuild 불요). **발견(별 cycle)**: caddy
`:443` 502 — `ENABLE_WEB_TLS=1`(web 8000 HTTPS) + 평문 `reverse_proxy web:8000` 불일치,
인증서 무관 기존 라우팅 이슈(핸드셰이크는 :443 도 `Verify code 0`).

**2026-05-21 TASK-0006 (= TASK-0087 in feature-0003) 완료 — Caddy XFF 정규화** (CHG-20260520-0010, REV-20260520-0010, REQ-20260520-0002, **Major** §12.3). `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 받은 임의 `X-Forwarded-For` 를 본인이 본 TCP peer IP 로 덮어쓴다. multi-hop / 클라이언트 spoof 모두 차단. feature-0003 의 `_get_client_ip()` 조건부 trust (env `WEB_TRUSTED_PROXIES`) 와 dual ownership cycle. Codex outside voice review 흡수 (REV-20260520-0010 정본 = feature-0003).

---

Caddy 설정과 Windows LAN 프록시 스크립트를 별도 feature로 이관했고, 인증서/상태 파일은 `../../../../artifacts`로 분리했다.

## 2. Progress
- Planned: 0
- In Progress: 네트워크 운영 시나리오 정리
- Done: 운영 자산 이관, TLS 경로 수정

## 3. Recent Changes
- Caddyfile HTTPS-upstream(Root CA 검증)로 :443 502 해소 + front door 화 (TASK-0297)
- `.env` ENABLE_WEB_TLS_PROXY=1 + WEB_TRUSTED_PROXIES=172.18/16 (audit 실 IP, 로컬)
- `bin/tls-internal-ca.sh` 신규 — 사내 Root CA + 서명 leaf 발급 (TASK-0296)
- `src/TESTER_TLS_TRUST.md` 신규 — 테스터 Root CA 신뢰 설치 가이드
- self-signed → Root CA 서명 인증서로 재발급·배포 (web/caddy 재시작)
- Caddyfile을 feature 경로로 이동
- Windows 스크립트와 문서를 feature 경로로 이동
- 총 변경 횟수: 3

## 4. Open Issues
- 실제 LAN 환경 검증은 후속 운영 시나리오가 필요하다.
- ~~caddy `:443` 502~~ → TASK-0297 해소 (HTTPS-upstream + Root CA 검증).
- 외부/미신뢰 LAN 노출 시 SECURITY.md §7.2/§9.7 보완 선행 (별 cycle) — `WEB_TRUSTED_PROXIES`
  협소화 + web port 비공개 + share/search IP allowlist.

## 5. Test Status
- 자동 테스트: 미구성
- 수동 테스트: `make web`/`make web-tls-up` 수준 구조 검증 예정
- 미검증 항목: 엄격한 네트워크 운영 시나리오

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 실제 LAN 운영 기준과 검증 절차 확정
