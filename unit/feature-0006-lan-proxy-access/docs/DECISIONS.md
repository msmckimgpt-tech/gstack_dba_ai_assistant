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
