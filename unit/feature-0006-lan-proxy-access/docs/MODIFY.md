---
doc_type: MODIFY
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260617T083954-ai-claude-id-collision-fix
- Date: 2026-06-17
- Related Requirement: TASK-20260617T083954-ai-claude-id-collision-fix (**Minor** §12.3)
- Summary: 동시 세션 문서 ID 충돌 정리 + **비-일련번호(timestamp+branch) 형식 전환**.
- 배경: feature-0002-agent-core(MSSQL SHOWPLAN, PR#309 선머지)가 docs 에서
  `TASK-0299`·`AC-0562`·`AC-0563`·`CHG-20260617-0310`·`REV-20260617-0310` 를 점유,
  추가로 `TASK-0298` 을 test 주석에서 참조. 본 feature-0006 의 동일 6 ID 와 전역 충돌.
- 정책 근거: AGENTS.md §6 / ADR-0025 — 병렬 할당 식별자(TASK·CHG·REV·LRN)는
  `<PREFIX>-<YYYYMMDDTHHMMSS>-<branch>` timestamp+branch 형식으로 순번 점유-경합 제거.
  사용자 결정(2026-06-17, "일련번호가 아닌 형태")에 따라 AC 도 본건 한정 동일 형식 적용
  (ADR-0024 의 AC=순번 기본에서 예외 — 신규·외부 참조 적어 안정성 영향 최소).
- 재번호 매핑(선머지한 feature-0002 는 미변경, feature-0006 만 변경):
  - `TASK-0298` → `TASK-20260617T083954-ai-claude-trust-bundle`
  - `TASK-0299` → `TASK-20260617T083954-ai-claude-bat-encoding-fix`
  - `AC-0562` / `AC-0563` → `AC-20260617T083954-ai-claude-bat-encoding-fix-01` / `-02`
  - `CHG-20260617-0310` → `CHG-20260617T083954-ai-claude-bat-encoding-fix`
  - `REV-20260617-0310` → `REV-20260617T083954-ai-claude-bat-encoding-fix`
- Files: feature-0006 docs 6(FUNCTION/TASK/MODIFY/REVIEW/REPORT/TEST) + src(트러스트 번들
  템플릿 2·README·Caddyfile·TESTER_TLS_TRUST.md) + bin(trust-bundle.sh·tls-internal-ca.sh)
  + docker-compose.yml. 총 14 파일 sed 치환. 비-충돌 ID(TASK-0296/0297·AC-0549~0561·
  CHG/REV-0307~0309) 보존.
- Impact: 코드 주석의 TASK 참조도 변경되어 `bin/trust-bundle.sh` 재실행으로 번들
  (.bat 헤더 주석) 재생성 필요. 기능·동작 무변경(식별자 문자열만).
- Rollback Notes: sed 역치환(timestamp 형식 → 원 순번). 단 feature-0002 와 재충돌.

## CHG-20260617T083954-ai-claude-bat-encoding-fix
- Date: 2026-06-17
- Related Requirement: REQ-0286 / TASK-20260617T083954-ai-claude-bat-encoding-fix / AC-20260617T083954-ai-claude-bat-encoding-fix-01~02 (**Minor** §12.3)
- Summary: TASK-20260617T083954-ai-claude-trust-bundle 설치 스크립트 실행 버그 2종 수정 (라이브 제보).
- 증상: Windows `.bat` 실행 시 `'cho'은(는) 내부 또는 외부 명령...`, base64 가 명령으로 실행됨.
- 근본:
  1. **인코딩/줄바꿈**: `bin/trust-bundle.sh` 가 .bat 를 LF + UTF-8 로 출력 + 템플릿에
     `chcp 65001`. cmd.exe 는 코드페이지를 UTF-8 로 바꾸면 배치 파일의 다음 줄 바이트
     오프셋을 잘못 계산 → 라인 파싱 붕괴(`echo`→`cho`, 긴 base64 줄을 명령으로 실행).
  2. **지문 비교 오류(잠복)**: 스크립트가 `Get-FileHash`/`shasum`(=PEM **파일** 해시)을
     `FP_HEX`(=인증서 **DER** 지문, `openssl -fingerprint`)와 비교 → 정상 인증서에서도 항상
     불일치 → 설치 중단. (인코딩 버그가 가려 그동안 미발현.)
- Files:
  - `unit/feature-0006-lan-proxy-access/src/trust-bundle/install-trust-windows.bat.tmpl`:
    `chcp 65001`/`title <한글>` 제거, 전체 메시지 ASCII(영문)화, 지문 검증을
    `Get-FileHash`(PEM) → `X509Certificate2.RawData` 의 SHA-256(DER)로 교체.
  - `unit/feature-0006-lan-proxy-access/src/trust-bundle/install-trust-macos.command.tmpl`:
    지문 검증 `shasum`(PEM) → `openssl x509 -noout -fingerprint -sha256`(DER)로 교체.
  - `bin/trust-bundle.sh`: .bat 렌더 후 LF→CRLF 변환 + 비-ASCII 바이트 검출 시 die(회귀 가드).
- Diff size: 템플릿 2 + 스크립트 1. 앱 코드 0.
- Impact:
  - `.bat` 가 `file` 기준 "DOS batch file, ASCII text, CRLF" → cmd.exe 파싱 정상.
  - 지문 검증이 인증서 DER SHA-256(브라우저 표시 지문)과 일치 → 정상 설치 진행.
  - **★cmd.exe 실측**: neuter(자가상승+certutil 제외) 후 cmd.exe 로 echo·지문표시·base64
    디코드·지문검증(ACTUAL==FP_HEX) 전 구간 정상 도달(`[OK]` 까지). 파싱 붕괴 0.
- Rollback Notes: 템플릿 2 + trust-bundle.sh 의 CRLF/ASCII 블록 되돌림. 단 .bat 다시 깨짐.
- 배포: 머지 후 `bash bin/trust-bundle.sh` 재실행 → `artifacts/trust-bundle/` 갱신
  (caddy file_server 가 즉시 서빙, 컨테이너 재시작 불필요).

## CHG-20260617-0309
- Date: 2026-06-17
- Related Requirement: REQ-0285 / TASK-20260617T083954-ai-claude-trust-bundle / AC-0557~0561 (**Major** §12.3, ADR-LAN-0004)
- Summary: 테스터 Root CA "원클릭 설치 번들". PC 마다 수동 인증서 이동 번거로움 해소.
  web 서버가 `http://<host>/trust/` 에서 OS별 단일 설치 스크립트 + 다운로드 페이지 제공.
- Files:
  - `bin/trust-bundle.sh` (신규): rootCA.pem → 지문/​base64 주입 → `artifacts/trust-bundle/`
    {index.html, install-trust-windows.bat, install-trust-macos.command, rootCA.crt} 조립.
    임베드 base64 디코드 지문 자가검증.
  - `unit/feature-0006-lan-proxy-access/src/trust-bundle/*.tmpl` (신규): win .bat(자가-상승+
    certutil), mac .command(security add-trusted-cert), index.html(지문 대조+OS감지), README.
    인증서 PEM base64 임베드(단일 자가완결 파일) + 지문 재검증.
  - `src/caddy/Caddyfile`: `:80`/`:443` 양쪽에 `/trust`→`/trust/` 리다이렉트 +
    `handle_path /trust/*`(`root /srv/trust`, `file_server`). HTTP 서빙 = CA 미설치(HTTPS
    경고) 상태에서 경고 없이 받게. 나머지는 :80=HTTPS 리다이렉트, :443=reverse_proxy(불변).
  - `docker-compose.yml`: caddy 에 `../artifacts/trust-bundle:/srv/trust:ro` 마운트.
  - `bin/tls-internal-ca.sh`: 끝에서 trust-bundle.sh 자동 호출(인증서 갱신 시 번들 동반).
  - feature-0006 docs + `src/TESTER_TLS_TRUST.md` (웹 번들 경로 안내 추가).
- Diff size: 신규 스크립트 1 + 신규 템플릿 4 + Caddyfile/compose + docs. 앱 코드 0.
- Impact:
  - 테스터: `http://<host>/trust/` 접속 → OS 스크립트 실행(승인 1회). 파일 수동 이동 불필요.
  - **브라우저 방문 자동설치는 OS/브라우저 보안경계상 불가** — 사용자 승인 필수(설계 한계 명시).
  - `caddy validate`=Valid + one-off 테스트 caddy(:8080/:8443): `/trust/`·스크립트·rootCA.crt
    = 200, bare `/trust`→301 `/trust/`, 그외 HTTP→HTTPS 301, 앱 :443 reverse_proxy=200 머지전 검증.
  - 배포: Caddyfile+compose mount 변경 → `docker compose up -d --force-recreate caddy`.
- 보안(신뢰 부트스트랩): Root CA 최초 배포는 채널 무결성이 본질 한계(HTTP·HTTPS 무관, 미설치
  상태라 암호학적 신뢰 없음). 완화 = 지문 노출 + 스크립트 설치전 지문 재검증 + 운영자가 지문을
  신뢰 채널 공유. 개인키 미포함(rootCA.crt 공개만). 사내 LAN 가정(§9.7), 외부 노출 시 보완 선행.
- Rollback Notes:
  - Caddyfile 의 `/trust` handle 2곳 제거 + compose mount 제거 후 `up -d --force-recreate caddy`.
    앱/인증서 서빙 무영향(번들만 사라짐).
  - `artifacts/trust-bundle/` 는 산출물 — 삭제 가능, `bin/trust-bundle.sh` 로 재생성.

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
