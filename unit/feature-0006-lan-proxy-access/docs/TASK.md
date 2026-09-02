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
- Last Updated: 2026-09-02

## 2. Task Queue
- [x] TASK-0001 Caddy 설정 이관
- [x] TASK-0002 Windows LAN 스크립트 이관
- [x] TASK-0003 루트 TLS 경로를 `../../../../artifacts` 기준으로 수정
- [x] TASK-0004 엄격한 네트워크 운영 시나리오 정의
- [x] TASK-0005 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입, dev → prod cherry-pick 궤적 명시)
- [x] TASK-0006 (= **TASK-0087** in feature-0003, REQ-20260520-0002, **Major** §12.3 — Caddy XFF 정규화). `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가 — Caddy 가 받은 임의 `X-Forwarded-For` 를 본인이 본 TCP peer IP 로 덮어쓴다. multi-hop / spoof 차단. feature-0003 의 `_get_client_ip()` 조건부 trust 와 dual ownership cycle. 본 cycle CHG-20260520-0010, REV-20260520-0010 on `ai/claude/0087-lan-trust-hardening` worktree.
- [x] TASK-0296 (REQ-0283, AC-0549~0553, **Major** §12.3, CHG-20260617-0307/REV-20260617-0307 — 사내 테스터 제한 배포 HTTPS 신뢰). self-signed → 사내 자체 Root CA 서명 leaf 로 전환. `bin/tls-internal-ca.sh`(멱등 Root CA 10년 + leaf 825일, SAN/EKU/체인 검증) + 테스터 신뢰 설치 가이드 `src/TESTER_TLS_TRUST.md`. web `:18080` 라이브 체인 검증 `Verify return code: 0` + HTTP 200. **발견(별 cycle)**: caddy `:443` 는 `ENABLE_WEB_TLS=1`(web 이 8000 서 HTTPS) + 평문 `reverse_proxy web:8000` 불일치로 502 — 인증서와 무관한 기존 라우팅 이슈. 인증서 핸드셰이크 자체는 :443 도 `Verify code 0`.
- [x] TASK-0297 (REQ-0284, AC-0554~0556, **Major** §12.3, CHG-20260617-0308/REV-20260617-0308 — caddy :443 정식 front door). TASK-0296 의 별 cycle 후속. Caddyfile `reverse_proxy` 를 HTTPS-upstream(`transport http { tls; tls_trust_pool file /certs/rootCA.pem; tls_server_name {$WEB_PUBLIC_HOST} }`)으로 전환해 :443 502 해소(XFF directive 보존). `.env` `ENABLE_WEB_TLS_PROXY=1`+`WEB_TRUSTED_PROXIES=172.18.0.0/16` 로 audit 실 클라이언트 IP 보존(§9.7). `caddy validate`=Valid + one-off 테스트 caddy(:8443) 런타임 프록시 HTTP 200 머지전 검증. 결과: 포트 없는 `https://mysql-ai.company.local` + `:18080` 양쪽 신뢰 HTTPS.
- [x] TASK-20260617T083954-ai-claude-trust-bundle (REQ-0285, AC-0557~0561, **Major** §12.3, CHG-20260617-0309/REV-20260617-0309, ADR-LAN-0004 — 테스터 Root CA 원클릭 설치 번들). PC 마다 수동 설치 번거로움 해소. `bin/trust-bundle.sh` 가 `src/trust-bundle/*.tmpl`(win .bat·mac .command·index.html — 인증서 base64 임베드·지문 주입) → `artifacts/trust-bundle/` 조립(임베드 디코드 지문 자가검증). Caddyfile `:80`/`:443` 양쪽에 `/trust/` `file_server` carve-out(HTTP 서빙 = CA 미설치 상태 경고 없는 다운로드용) + compose `/srv/trust` 마운트. 단일 자가완결 스크립트(자가-상승·지문 재검증·certutil/security). **브라우저 자동설치는 OS 보안경계상 불가** — 승인 1회 필수. 신뢰 부트스트랩 한계는 지문 노출+재검증+운영자 out-of-band 공유로 완화. validate=Valid + one-off 테스트 caddy(:8080/:8443) `/trust/` 200·bare `/trust`→301·앱 200 머지전 검증. tls-internal-ca.sh 가 끝에서 자동 호출.
- [x] TASK-20260617T083954-ai-claude-bat-encoding-fix (REQ-0286, AC-20260617T083954-ai-claude-bat-encoding-fix-01~02, **Minor** §12.3, CHG-20260617T083954-ai-claude-bat-encoding-fix/REV-20260617T083954-ai-claude-bat-encoding-fix — 설치 스크립트 실행 버그 2종). 라이브 `.bat` 실행 시 `echo`→`cho`·base64 명령실행·지문 항상불일치. **버그①**: LF+UTF-8+`chcp 65001`→cmd.exe 코드페이지 전환 후 파일 오프셋 상실. 수정=ASCII 전용+CRLF+chcp 제거, `trust-bundle.sh` 가 .bat CRLF 출력+비-ASCII die. **버그②**: 지문 비교가 PEM **파일** 해시(`Get-FileHash`/`shasum`) vs 인증서 **DER** 지문→항상 불일치. 수정=DER SHA-256(win `X509Certificate2.RawData`, mac `openssl x509 -fingerprint`). **★cmd.exe 실측**: neuter(자가상승+certutil) 후 echo/지문표시/base64디코드/지문검증(ACTUAL==FP_HEX) 전구간 정상 도달. `.command` 는 `base64 -D`(macOS 전용 옵션) 라 Linux 테스트 불가-macOS 정상. macOS .command/index.html LF 유지.
- [x] TASK-20260617T083954-ai-claude-id-collision-fix (CHG-20260617T083954-ai-claude-id-collision-fix/REV-20260617T083954-ai-claude-id-collision-fix, **Minor** §12.3 — 동시세션 ID 충돌 정리, **비-일련번호 형식 전환**). feature-0002(MSSQL, #309 선머지)가 docs 에서 `TASK-0299`·`AC-0562`·`AC-0563`·`CHG-20260617-0310`·`REV-20260617-0310` 점유 + `TASK-0298` 도 test 주석 참조 → 본 feature-0006 의 동일 6 ID 를 §6/ADR-0025 의 **timestamp+branch 형식 `<PREFIX>-<YYYYMMDDTHHMMSS>-<branch>`** 로 재번호(일련번호 점유-경합 제거). 사용자 결정(2026-06-17, "일련번호가 아닌 형태"): AC 도 ADR-0024 기본(순번 spec 앵커)에서 본건 한정 timestamp 형식 적용(신규·외부참조 적음). feature-0002 는 미변경. 비-충돌 ID(TASK-0296/0297, AC-0549~0561, CHG/REV-0307~0309) 는 보존.

- [x] TASK-20260901T103000-ai-claude-corp-cert-expiry-monitor (**Minor** §12.3 — 인증서 만료 감시).
  `deploy-web.sh` preflight 는 **배포할 때만** 돌고 **Root CA 를 보지 않는다**. 주기 감시
  `bin/cert-expiry-check.sh`(leaf 30일 / CA 180일 · `--live` 로 서빙본 대조) + cron 설치기 추가.
  감시 임계가 게이트(14일)보다 좁으면 스크립트가 거절하고, 두 파일 상수 관계를 테스트가 잠근다.
  `unit/feature-0006-lan-proxy-access/tests` 를 Makefile·ci.yml **양쪽**에 등재(신설 규약 자가적용).
- [x] TASK-20260902T113500-ai-claude-feature-0006-lan-proxy-access (REQ-20260902-portproxy-idempotent-sync,
      AC-20260902T113500-portproxy-idempotent-1~3, **Major** §12.3,
      CHG/REV-20260902T113500-ai-claude-feature-0006-lan-proxy-access — 5분 주기 포트프록시 재설정이
      라이브 연결을 끊는 문제). 예약작업이 매 실행 조건 없이 `netsh portproxy delete`→`add` 를 해
      WSL IP 불변 상태에서도 **5분마다 80/443 기존 연결 전면 절단**. 개인 AI 브리지 러너의 55초
      대기 호출이 그때마다 `RemoteDisconnected`(WARN 14건 중 13건이 sync 실행 후 3~19초 내, 서로
      다른 러너가 같은 벽시계 위상). 수정 = 현재 매핑을 읽어 **이미 원하는 값이면 delete/add 를
      건너뛴다**(못 읽으면 종전대로 재설정하는 fail-safe). 파싱은 헤더 문구가 아닌 데이터 행 패턴
      으로 **로케일 무관**. 한글 주석 추가에 따라 **UTF-8 BOM** 부여(대조 실측: BOM 없으면 839자 중
      324자 손실). PS 5.1 실측 4축 PASS(구문/인코딩/실 netsh 파싱/멱등 판정).

## 8. Requested Scope (요청 범위)

사용자 요청 (§16.7 G1 — 완료 선언 전 항목당 1행 대조). 2026-09-01 AskUserQuestion 결정.

```
사용자 원문(데이터이며 지시가 아님)
AskUserQuestion 으로 모범적인 대안을 검토하여 제안까지 진행해주세요.
→ 선택: 「만료 모니터링만 (권장)」
```

- [x] **CA 폐기검사 축 — 만료 모니터링만** — 산출물: `bin/cert-expiry-check.sh`(leaf+CA 2축·
      3단 임계·`--live` 서빙본 대조) + `bin/install-cert-expiry-cron.sh`(멱등 주 1회). CRL·수명단축
      **불채택** 근거를 FUNCTION.md §12 에 기록(둘 다 새 outage 원인을 들이고, CRL 은 완화 플래그를
      없애지도 못함)
- [x] **게이트와 감시의 관계를 구조로 잠금** — 산출물: `--leaf-warn < 14` 거절 + `deploy-web.sh`
      의 `checkend 1209600` 상수와 감시의 `DEPLOY_GATE_DAYS=14` 가 어긋나면 FAIL 하는 테스트
- [x] **동작 검증(텍스트 아님)** — 산출물: openssl 로 100/20/3일 cert 를 생성해 exit 0/1/2 실측,
      CA 단독 임박·cert 부재·게이트보다 좁은 임계까지 9건

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
