---
doc_type: DECISIONS
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-LAN-0001
- Date: 2026-03-26
- Decision: LAN/TLS 운영 자산은 feature 내부에 두고 인증서/상태는 `../../../../artifacts`로 분리한다
- Consequence: 보안 경계는 명확하지만 실제 운영 검증이 후속 작업으로 남는다

## ADR-LAN-0002
- Date: 2026-06-17
- Context: 사내 특정 테스터 대상 제한 배포 직전, 브라우저가 "안전하지 않은 연결" 경고를
  표시. 근본 원인 = web 이 서빙하는 인증서가 self-signed(issuer==subject, CA 체인 없음).
  서버 호스트명이 `mysql-ai.company.local`(내부 `.local` 도메인)이라 공인 CA(Let's
  Encrypt)는 발급이 구조적으로 불가능.
- Decision (사용자 결정 2026-06-17): **사내 자체 Root CA** 방식 채택. Root CA 를 1회
  생성하고 그것으로 서버 leaf 인증서를 서명한다. Root CA 공개 인증서(`rootCA.pem`)만
  테스터 PC 신뢰 저장소에 1회 설치하면 경고가 사라진다.
- 대안 거부:
  - **공인 도메인 + Let's Encrypt**: 실제 등록 도메인 + DNS 필요, `.company.local`
    폐기 필요. 내부 도메인엔 발급 불가. (도메인 보유 시 별 cycle 재검토 가능.)
  - **현 self-signed 를 테스터 PC 에 직접 신뢰 등록**: 인증서 교체 시마다 전 PC 가
    깨지고, Chrome 등이 leaf 의 직접 신뢰(basicConstraints CA:FALSE)를 거부할 수 있음.
- Consequence:
  - 테스터는 Root CA 1회 설치 필요(`src/TESTER_TLS_TRUST.md`). 그 외 완전 자동·오프라인.
  - **Root CA 10년 / leaf 825일** 분리 — leaf 갱신은 `bin/tls-internal-ca.sh` 재실행 +
    web 재시작으로 transparent(Root CA 유지 → 테스터 재설치 불필요). 825일은 Apple/macOS
    leaf 유효기간 상한 준수.
  - 개인키(`rootCA-key.pem`, `<host>/privkey.pem`)는 서버 밖 반출 금지(0600). 인증서는
    `artifacts/`(gitignore)에만 — SECURITY.md §5/§6 정합.
  - **외부 인터넷/미신뢰 LAN 노출 시 보완 필요**: SECURITY.md §7.2(IP allowlist / token
    비밀번호 / 만료) + §9.7(`WEB_TRUSTED_PROXIES` 협소화 + web port 비공개) 별 cycle.
- 미해결(별 cycle): caddy `:443` 경로는 `ENABLE_WEB_TLS=1`(web 이 8000 서 HTTPS) + 평문
  `reverse_proxy web:8000` 불일치로 502. 인증서 신뢰와 무관. 테스터 경로는 web 직접 TLS
  `:18080`. 깔끔한 무포트 `https://<host>` 가 필요하면 `ENABLE_WEB_TLS_PROXY` 설계
  (web 평문 8000 ↔ caddy TLS 종료, 또는 caddy→https upstream)를 별 cycle 에서 정리.
  → **ADR-LAN-0003 (TASK-0297) 에서 해소.**

## ADR-LAN-0003
- Date: 2026-06-17
- Context: ADR-LAN-0002 의 미해결 항목 — caddy `:443` 502. 사용자 결정(2026-06-17):
  포트 없는 `https://mysql-ai.company.local` 를 정식 진입점으로 만든다. 근본 = web 이
  `ENABLE_WEB_TLS=1` 로 8000 에서 HTTPS 를 서빙하는데 caddy 가 평문으로 프록시.
- Decision: caddy → web upstream 을 **HTTPS 로 re-encrypt** 하고 사내 Root CA 로 검증.
  `transport http { tls; tls_trust_pool file /certs/rootCA.pem; tls_server_name
  {$WEB_PUBLIC_HOST} }`. web 직접 TLS `:18080` 은 그대로 유지(두 진입점 공존).
  `.env` `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES=172.18.0.0/16` 로 web 이 caddy
  XFF 를 신뢰 → audit 실 클라이언트 IP 보존(§9.7).
- 대안 거부:
  - **web 평문 8000 + caddy 단독 TLS 종료(ENABLE_WEB_TLS=0)**: `:18080` 직접 경로가
    평문 HTTP 로 회귀 → 검증 완료된 테스터 경로 파괴 + secure-context 요건 위배. 기각.
  - **`tls_insecure_skip_verify`**: 내부 hop 이라 위험 낮으나 Root CA 검증을 버릴 이유
    없음. `tls_trust_pool` + `tls_server_name` 으로 정식 검증 채택.
  - **caddy 미실행(profile gating)**: 502 는 사라지나 무포트 URL 도 불가. front door
    제공이라는 목표와 불합치. 기각.
- Consequence:
  - 테스터는 `https://mysql-ai.company.local`(무포트, caddy :443) 또는 `:18080`(web 직접)
    어느 쪽이든 Root CA 신뢰 후 경고 없이 접속.
  - SNI/검증명은 leaf SAN 과 일치하는 `WEB_PUBLIC_HOST` 사용(내부 서비스명 `web` 는 SAN
    부재 — leaf SAN 에 `web` 추가하지 않고 tls_server_name 으로 해결, 최소 노출).
  - **외부/미신뢰 LAN 노출 시**: `WEB_TRUSTED_PROXIES` 를 bridge 서브넷으로 좁히고
    web port 를 Caddy network only / 127.0.0.1 바인드로 비공개 — SECURITY.md §9.7 별 cycle.

## ADR-LAN-0004
- Date: 2026-06-17
- Context: 사용자 — "테스터 PC 마다 인증서 하나하나 설치하기 번거롭다. 웹페이지 방문 시
  자동 설치 안 되나?" 자동설치는 **불가**(OS/브라우저 보안 경계 — 페이지 방문만으로 신뢰
  루트를 심으면 어떤 사이트든 MITM 가능 → 전 OS 금지). 설치는 사용자 명시 승인 필수.
- Decision (사용자 결정): "원클릭 설치 스크립트" 채택. web 서버가 `http://<host>/trust/`
  에서 OS별 **단일 자가완결 설치 스크립트**(Root CA PEM base64 임베드) + 다운로드 페이지를
  제공. 테스터는 URL 접속 → 스크립트 실행(승인 1회). HTTP 로 서빙(아직 CA 미설치 → HTTPS 면
  경고). `bin/trust-bundle.sh` 가 인증서에서 번들을 조립, caddy `file_server` 가 서빙.
- 대안 거부:
  - **공인 인증서(Let's Encrypt)**: 설치 0·자동 신뢰지만 실제 등록 도메인 필요(`.company.local`
    폐기). 사용자가 자체 CA 유지 선택 → 기각(도메인 확보 시 재검토 가능).
  - **GPO/MDM 중앙 push**: 무손이지만 관리형 디바이스 전제. 비관리 PC 환경 → 기각.
  - **파일 수동 배포(USB/메일)**: 번거로움 그대로 → web 서빙으로 대체.
- 신뢰 부트스트랩 한계 (불가피):
  - Root CA 최초 배포는 채널 무결성을 암호학적으로 보장 못 함(HTTP·HTTPS 무관 — 신뢰
    대상 자체를 전달하므로). 완화 = (1) 지문을 페이지·스크립트에 노출, (2) 스크립트가 설치
    전 임베드 인증서 SHA-256 재검증, (3) **운영자가 지문을 신뢰 채널(메신저·구두)로 공유**해
    테스터 대조. 사내 LAN 가정(§9.7). 외부 노출 시 §7.2/§9.7 보완 선행.
- Consequence:
  - `http://<host>/trust/` = 다운로드 페이지(평문, 경고 없음). `https://<host>/trust/` 도 서빙.
  - 단일 파일 다운로드+실행으로 PC당 수작업 최소화(완전 자동 아님 — 승인 1회 불가피).
  - 인증서 갱신 시 `tls-internal-ca.sh` 가 번들 자동 갱신(지문도 자동 반영).
