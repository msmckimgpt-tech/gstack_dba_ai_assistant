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

## CHG-20260901T103000-ai-claude-corp-cert-expiry-monitor — 인증서 만료 감시(leaf + Root CA)

- **날짜**: 2026-09-01
- **REQ**: 사용자 결정 2026-09-01 (AskUserQuestion — «만료 모니터링만»)
- **위험도**: Minor (읽기 전용 감시 추가 · 배포 스파인 무변경 · cron 설치는 사용자 판단)

### 무엇이 비어 있었나

`bin/deploy-web.sh` 의 `preflight_tls()` 가 이미 leaf 만료를 본다. 두 가지가 빠져 있었다:

1. **배포할 때만 돈다.** 배포가 없으면 신호도 없고, 그 사이 만료되면 첫 신호가 전면 outage 다.
2. **Root CA 를 아예 보지 않는다.** CA 만료는 테스터 전원 재설치라 회복 비용이 leaf 보다 크다.

### 변경

- `bin/cert-expiry-check.sh` (신규) — leaf + Root CA 2축, 3단 판정(정상/WARN/CRITICAL)을 종료코드
  0/1/2 로 낸다(cron 알림이 이것으로 갈린다). `--live <host>` 로 **실제 서빙본**도 확인하고,
  디스크와 만료가 다르면 「갱신했으나 미배포」로 보고한다.
  - `set -e` 를 쓰지 않는다 — `openssl -checkend` 의 비-0 는 «만료 임박» 이라는 **정상 신호**이지
    스크립트 실패가 아니다. `-e` 면 첫 경고에서 죽어 나머지 축을 못 본다.
- `bin/install-cert-expiry-cron.sh` (신규) — `install-worktree-audit-cron.sh` 패턴 승계(marker 멱등).
  주 1회(월 09:10). 매일 돌리면 같은 경고가 30번 반복돼 신호가 소음이 된다.
- `Makefile` + `.github/workflows/ci.yml` — `unit/feature-0006-lan-proxy-access/tests` 를
  **양쪽에** 등재. 직전 cycle(CHG-20260901T101500)이 세운 규약의 첫 자가적용이며, 그 parity
  테스트가 이 등재를 실제로 검증했다(한쪽만 했을 때 FAIL 함도 실증).

### 게이트와 감시의 관계를 구조로 잠갔다

감시 임계가 게이트(14일)보다 좁으면 게이트가 먼저 울려 감시가 무의미하다. 그래서
`--leaf-warn < 14` 를 **스크립트가 거절**하고, `deploy-web.sh` 의 `checkend 1209600` 과
감시의 `DEPLOY_GATE_DAYS=14` 가 어긋나면 테스트가 FAIL 한다 — 두 파일이 조용히 갈라지는 것을
막는 유일한 연결이다. (배포 스파인은 **건드리지 않았다** — 위험 대비 이득이 낮다.)

### 왜 CRL/OCSP 가 아닌가 (사용자 결정)

CRL 을 도입하면 폐기가 가능해지지만 **완화 플래그(feature-0043 `--ssl-revoke-best-effort`)를
없애지 못한다** — CRL 은 `nextUpdate` 가 있어 만료·404 시 `CERT_TRUST_REVOCATION_STATUS_UNKNOWN`
으로 되돌아가므로 안전망이 계속 필요하다. 즉 «새 liveness 의존성 + 그 실패 모드가 이번에 고친
버그» 인데, 막는 위협(leaf 키 유출 + MITM)은 저확률이다. 수명 단축도 회전 실패가 전면 outage 다.

### 검증

- **동작 실측**(텍스트 검사 아님): openssl 로 100/20/3일 cert 생성 → exit **0/1/2** 확인.
  CA 단독 임박 → CRITICAL · cert 부재 → 비-0(fail-open 아님) · `--leaf-warn 5` → exit 3 거절.
- 실환경 1회: leaf/rootCA/live 3축 OK(exit 0) — `--live` 경로 포함.
- 신규 테스트 9건 PASS · `bash -n` OK · cron 설치기는 `--print` 로만 확인(**crontab 미변경**).

## CHG-20260902T113500-ai-claude-feature-0006-lan-proxy-access — 포트프록시 동기화를 idempotent 로 (2026-09-02)

REQ-20260902-portproxy-idempotent-sync / TASK-20260902T113500-ai-claude-feature-0006-lan-proxy-access
/ AC-20260902T113500-portproxy-idempotent-1~3 / **Major** §12.3

### 무엇이 문제였나

`src/windows/sync_mysql_ai_web_portproxy.ps1` 는 Windows 예약작업으로 **5분마다** 실행되는데,
매 실행이 조건 없이 `netsh interface portproxy delete` → `add` 였다. `delete` 는 그 리스너를
내리므로 **해당 포트를 지나던 기존 TCP 연결이 전부 끊긴다**. WSL IP 가 바뀌지 않은 평상시에도
5분마다 80/443 의 모든 연결이 한 번씩 끊긴 것이다.

브라우저처럼 짧은 요청은 재시도에 가려 보이지 않았지만, **오래 유지되는 연결**은 그대로 드러났다:
개인 AI 브리지 러너의 대기 호출(`wait_for_request` — 서버가 55초 보류)이 5분 주기로
`RemoteDisconnected` 를 맞았다.

### 실측 근거 (2026-09-02)

- 러너 원장 `bridge.events.jsonl` 19시간분: `api.fail` 289건 · `conn.retry` 209건. 안정 러너
  기준 **시간당 정확히 12건**(= 5분당 1건).
- 실패 시각이 **벽시계 5분 경계**(:04/:09/:14/:19…)에 정렬. 시작 시각이 다른 별개 러너
  프로세스들이 **모두 같은 위상** → 프로세스 내부 타이머가 아니라 외부 스케줄 이벤트.
- 예약작업 heartbeat(`C:\Users\Public\mysqlai_sync.log`)와 대조: WARN 14건 중 **13건이 sync 실행
  후 3~19초 이내**. 나머지 1건은 heartbeat 로그에 해당 실행 줄이 누락된 구간.
- 실패한 대기 호출의 소요는 3~55초 **균등 분포** — 절단이 연결 수명이 아니라 절대 시각에
  걸린다는 신호(55초 주기와 300초 주기는 위상이 무관하다).
- 양쪽 관측이 모두 "상대가 끊었다": Caddy 액세스 로그는 `status:0`(응답 미전송), 러너는
  `RemoteDisconnected`. 중간 단이 끊었다는 뜻이며 그 중간 단이 portproxy 다.

### 무엇을 바꿨나

- `Get-PortProxyEntries` 신설 — `netsh interface portproxy show v4tov4` 를 파싱해
  `listen:port → connect:port` 맵을 만든다. **헤더 문구가 아니라 데이터 행의 «IPv4 포트 IPv4 포트»
  패턴**만 뽑아 로케일 의존을 없앴다(한국어 Windows 는 헤더가 "수신 대기").
- 메인 루프: 원하는 매핑이 **이미 그대로면 `delete`/`add` 를 건너뛴다**. 다르면 종전대로 재설정.
  legacy 포트 삭제도 실제로 존재할 때만 호출한다.
- 출력 JSON 에 관측 필드 추가: `portproxy_changed` · `ports[].portproxy_action` ·
  `portproxy_state_known` · `legacy_ports_deleted`. 기존 필드는 그대로 두었다(스키마 추가만).
- 파일에 **UTF-8 BOM** 추가 — 한글 주석을 넣었기 때문. `bridge_setup.ps1`(한글 260줄 + BOM)이
  이 저장소의 선례다.

### 안전 설계 — 모르면 종전대로 한다

현재 상태를 **읽지 못하면** `Get-PortProxyEntries` 가 `$null` 을 돌려주고, 호출측은 종전처럼
무조건 재설정한다. 빈 딕셔너리("등록된 것이 없다" → 추가해야 한다)와 `$null`("상태를 모른다")을
구분하는 이유가 여기 있다 — 둘을 뭉개면 파싱이 깨진 날 포트포워딩이 조용히 사라진다.
**안전한 실패 방향은 «불필요한 재설정»이지 «필요한 재설정 누락»이 아니다.**

### 검증 (Windows PowerShell 5.1 실측)

| 항목 | 결과 |
|---|---|
| 구문 파싱 (`Parser::ParseFile`) | 오류 0 |
| 한글 주석 인코딩 무결성 | BOM 있음 839자 / **BOM 없음 515자** → BOM 필요 확인 |
| 실 netsh 출력 파싱 (한국어 로케일) | 4개 매핑 전부 정확, `112.185.196.20:443 → 172.26.154.233:443` 포함 |
| 멱등 판정 | 현재 상태 = 원하는 상태 → `delete/add` **SKIPPED** |

라이브 효과 검증(배포 후 관측)은 `TEST.md` Run 기록 참조.

### 후속 수정 — `-IgnoreExitCode` 가 $null 계약을 무력화하고 있었다 (같은 cycle, 자체 적대 검토)

첫 구현은 `Get-PortProxyEntries` 안에서 `Invoke-Netsh ... -IgnoreExitCode` 로 호출했다. 그러면
netsh 가 **비-0 로 끝나도 예외가 오르지 않고 오류 텍스트가 그대로 넘어오고**, 그 텍스트는 행
정규식에 하나도 매칭되지 않아 **빈 맵**이 된다 — "읽지 못했다"가 "등록된 것이 없다"로 둔갑한다.

동작 자체는 안전한 쪽(재설정)으로 떨어지지만, `portproxy_state_known` 이 `true` 라고 **거짓
보고**하게 되어 위에서 문서화한 $null 계약이 실제로는 성립하지 않았다. 「방어를 넣었다」와
「방어가 성립한다」는 다르다. `-IgnoreExitCode` 를 제거해 실패가 실패로 오르게 했다.

**이 수정은 판별력 있는 대조로 확인했다** — 수정 전 사본과 수정본에 «netsh 비-0 종료» 를 주입해
서로 다른 결과가 나오는지 봤다:

| | netsh 비-0 종료 시 결과 |
|---|---|
| 수정 전 | `MAP Count=0` — 상태를 안다고 거짓 주장 |
| 수정 후 | `NULL` — 상태 모름, 종전대로 재설정 |

(첫 시도의 주입 하네스는 stub 이 무조건 throw 해서 **수정 전에도 통과**했다 — 판별력이 없었다.
stub 이 `-IgnoreExitCode` 유무에 따라 다르게 행동하도록 실제 계약을 모사한 뒤에야 두 버전이
갈렸다.)

## CHG-20260902T124500-ai-claude-feature-0006-lan-proxy-access — codex 적대 리뷰 P2 반영 (2026-09-02)

직전 cycle(CHG-20260902T113500) 산출물에 대한 `codex exec` 적대 리뷰 결과를 반영한다.
**Minor** §12.3 (관측 정확성 + 되돌림, 동작 축소 없음).

### P1 — 이미 고쳐져 있었다 (독립 확인)

`-IgnoreExitCode` 가 netsh 비-0 종료를 삼켜 $null 계약이 성립하지 않는다는 지적. **같은 cycle
자체 적대 검토가 먼저 적발해 수정**한 것과 동일 결함이며, codex 자신도 리포트 말미에 "현재
worktree 의 unstaged 변경에는 이미 -IgnoreExitCode 제거가 들어가 있다" 고 적었다. 서로 다른
경로가 같은 결함에 도달했다는 점에서 **독립 확인**으로 기록한다.

### P2-3·P2-4 — legacy skip 최적화를 되돌렸다

직전 cycle 은 legacy 포트 삭제에도 "이미 없으면 건너뛴다" 를 넣었다. 되돌린다:

- **이득이 없다.** legacy 포트는 더 이상 쓰지 않는 포트라 활성 연결이 없고, 없는 매핑에 대한
  `delete` 는 아무 연결도 끊지 않는다. 이 수정이 겨냥한 「기존 연결 절단」은 public 포트에서만
  일어난다.
- **위험은 있다.** netsh 는 `connectaddress` 에 hostname 도 허용하는데(`127.0.0.1 18080
  localhost 18080`), 그런 행은 IPv4 정규식에 안 걸려 `ContainsKey` 가 false → **영영 삭제되지
  않는다**.

즉 skip 은 위험만 도입한 최적화였다. "무해한 호출도 남기지 않는다" 는 동기는 이 자리에서는
근거가 약했다.

또한 삭제 **성공한 것만** `legacy_ports_deleted` 에 기록하도록 `try/catch` 로 감쌌다. 종전에는
netsh 가 실패해도 즉시 목록에 넣어 "지웠다" 는 원장이 거짓이 됐다.

### P2-2 — `portproxy_changed` 가 legacy 삭제를 세지 않았다

public 포트만 세면 18080 을 지운 실행이 `legacy_ports_deleted:[18080]` 과
`portproxy_changed:false` 를 **동시에** 보고해 필드 의미가 자기모순이 된다. legacy 삭제를
포함하도록 고쳤다.

### P2-5 — TOCTOU: 수용하고 주석으로 남겼다

조회 후 판정까지의 창에 다른 도구가 매핑을 지우면 `unchanged` 로 건너뛰어 최대 5분 접근이
끊길 수 있다. netsh 에 원자적 비교-교체가 없어 창을 구조적으로 없앨 수 없고, 이 스크립트 외에
portproxy 를 건드리는 주체가 없는 것이 전제다. **확률적 5분 창과 확정적 5분 절단을 맞바꾼
것**이며, verify 단계의 `Test-NetConnection` 결과가 JSON 에 남아 사후 판별이 가능하다.

### 검증 (PS 5.1 재실행)

구문 0 오류 · 인코딩 무결 · 실 netsh 4매핑 파싱 · legacy 기록이 `try` 안에만 있음 ·
상태 기반 skip 제거됨 · `portproxy_changed` 가 legacy 를 셈 — **6축 PASS**.

## CHG-20260902T140000-ai-claude-feature-0006-lan-proxy-access — 라이브 검증 결과 기록 (2026-09-02)

docs-only. 코드 변경 없음. deploy-backed 완료 기준(§16.3)의 마지막 단계인 **라이브 실측**을 기록한다.

### 배포

`C:\ProgramData\mysql_ai_web_portproxy\sync_mysql_ai_web_portproxy.ps1` 를 main 본으로 교체.
**관리자 권한이 필요했다** — WSL 에서는 기존 파일의 수정·삭제가 ACL 로 거부되고(`Permission
denied`), 비-상승 PowerShell 의 `IsReadOnly=false` 도 거부된다(디렉토리 신규 파일 생성만 가능).
사용자가 관리자 PowerShell 로 `Copy-Item ... -Force` 실행 후 sha256 대조 일치를 확인했다.

### 결과 — 목표 지표 0건

| 구간 (각 22분) | `conn.retry` + `api.fail` |
|---|---|
| 10:30~10:52 · 11:00~11:22 · 11:22~11:44 (배포 전) | 8 · 8 · 8건 |
| 11:44~12:06 (배포 전) | 12건 |
| **13:33~13:55 (배포 후)** | **0건** |

같은 구간에 예약작업은 **5회 정상 실행**(`LastTaskResult=0`)됐다 — 「작업이 멈춰서 0건」이 아니라
「돌면서도 끊지 않은」 것이다. 이 대조가 없으면 두 상태가 같은 숫자로 보인다.

**관통 증거**: 완주한 `wait_for_request` 22건 중 21건이 55초 보류 완주(median 55,402ms).
13:34:00 시작분(55,366ms)은 13:34:34 sync 실행을 관통했다.

### 잔존 WARN 2건은 무관 (은폐하지 않음)

`hb.stale_build`(러너 버전 안내, 1회성) · `ai.cmdline.stdin`(명령줄 상한 초과 시 stdin 전달 —
정상 동작 로그). 사용자가 보고한 3종이 아니다.

⚠ **관측 하네스의 판정이 부정확했다** — 목표 지표가 아니라 모든 `lvl=WARN` 을 세어
`VERDICT: WARN 잔존` 을 냈다. 그대로 받아썼다면 해소된 것을 미해소로 보고했을 것이다.

## CHG-20260909T050000-portproxy-task-repair

- 2026-09-09T06:31:09.941569+00:00; TASK-20260909T050000-portproxy-task-repair. **저장소 코드 변경 0** — Windows 예약작업
  상태 복구 기록이다. 사용자 제보(5분마다 `run_hidden.vbs` 없음 오류창)의 원인은 예약작업
  `mysql_ai_web_portproxy_sync` 의 `UserId=SYSTEM` + `LogonType=InteractiveToken` 손상 조합이었다.
  cmdlet 은 못 보고 `Register-*` 는 거부하며 스케줄러만 실행하는 세 모순이 여기서 나왔다.
- `run_hidden.vbs` 는 **불필요**로 판정(사용자 요청 선행 검토): 정본은 SYSTEM+ServiceAccount 라
  Session 0 격리로 창이 뜨지 않으므로 숨김 래퍼가 필요 없고, vbs 경유는 로그온 전 미동작·권한·
  실패지점 추가라는 대가만 남긴다.
- 조치: `schtasks /delete` 로 손상 작업 제거 → 현재 운영 파라미터(`-ListenAddress 112.185.196.20`
  등)를 승계해 재등록. 매핑·접속은 전 구간 유지.

## CHG-20260909T060000-portproxy-task-rename

- 2026-09-09T07:07:23.228056+00:00; 같은 TASK 의 최종 조치. 이벤트 로그가 `TaskName=\mysql_ai_web_portproxy_sync`·
  `Action=wscript.exe` 를 잡아 **XML(powershell)과 레지스트리 캐시(wscript)의 불일치**를 확정했다.
  같은 이름 재등록이 옛 캐시를 물려받으므로(두 번 재발) **새 이름 `mysql_ai_web_portproxy_sync2`**
  로 등록했고, 그 작업은 `Get-ScheduledTask` 조회가 정상 동작한다(손상 없음).
- sync 스크립트 직접 실행은 **exit 0**(`portproxy_action: unchanged`, 80·443 verify true) — rc=1 은
  스크립트 결함이 아니다. 매핑·접속은 전 구간 유지.
- 재발 종료는 **미확정**으로 남긴다: 관측 창 내내 기존 인스턴스가 살아 `IgnoreNew` 로 새 실행을
  억제해, 「무재발」과 「억제」가 갈리지 않는다.

## CHG-20260909T070000-portproxy-s4u

- 2026-09-09T10:00:50.020856+00:00; TASK-20260909T070000-portproxy-s4u. `register_mysql_ai_web_portproxy_task.ps1` 의 실행
  계정을 `SYSTEM/ServiceAccount` → **사용자 계정/`S4U`** 로 교정하고 `-RunAsUser` 를 신설했다.
  근거: WSL 이 LOCAL SYSTEM 을 지원하지 않아(`WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED`) SYSTEM 등록은
  5분마다 rc=1 로 죽는다(실측). S4U 는 창 없이 WSL 조회가 된다(실측 rc=0).
- 트리거에서 `AtLogOn` 제거(S4U 와 경고·의미 중복), `RepetitionDuration` 1일 → 3650일
  (`[TimeSpan]::MaxValue` 는 등록 실패 — 실측).
- 앞 CHG 의 「`run_hidden.vbs` 불요」 판정을 **정정**한다: 원래 구성에서 vbs 는 필요했다.
  결론(되살리지 않는다)은 유지되나 이유가 다르다 — S4U 가 창 없이 동작하기 때문이다.
- Major(§12.3): 실행 계정 변경. 인증·인가 정책 변경 아님(같은 사용자 권한, 승격 수준 유지).
