---
doc_type: REVIEW
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260617T083954-ai-claude-id-collision-fix [SKIPPED:doc-id-hygiene] — 동시세션 ID 충돌 정리 (비-일련번호 전환)
- Date: 2026-06-17
- Change: CHG-20260617T083954-ai-claude-id-collision-fix (**Minor** §12.3). feature-0002
  (PR#309 선머지)와 전역 충돌한 feature-0006 의 6 ID(TASK-0298/0299·AC-0562/0563·CHG/REV-0310)를
  §6/ADR-0025 timestamp+branch(`<PREFIX>-<YYYYMMDDTHHMMSS>-<branch>`) 비-일련번호 형식으로 재번호.
- 자체 점검:
  1. **충돌 전수조사** — feature-0006 의 이번 세션 ID 전체를 다른 feature 와 대조, 실제 충돌 6건만
     식별(TASK-0296/0297·AC-0549~0561·CHG/REV-0307~0309 는 비-충돌 → 보존). 과대 변경 회피.
  2. **선머지 우선** — feature-0002 가 #309 로 먼저 머지 → feature-0006(후행)만 재번호. 타 feature 무변경.
  3. **잔존 검증** — sed 후 충돌 6 ID grep 0건, 비-충돌 ID 보존 확인.
  4. **정책 정합** — TASK/CHG/REV 는 §6 권장 형식 그대로. AC 는 ADR-0024(순번) 기본을 사용자 명시
     결정으로 본건 한정 timestamp 형식 적용(신규·외부참조 적어 안정성 영향 최소). REQ-0283~0286 은
     비-충돌이라 순번 유지(정책 정합).
  5. **무회귀** — 식별자 문자열만 변경, 코드 로직·동작 불변. 번들 재생성으로 .bat 헤더 주석 정합.
- Outside-voice: **SKIPPED** — 문서 ID 하이진(코드 로직/보안/RBAC 무관). 결정(비-일련번호 형식)은
  사용자 명시 지시.
- Risk: 코드 주석 TASK 참조 변경 → 번들 재생성·재배포 1회 필요(반영). feature-0002 의 test 주석
  `TASK-0298` 은 그들 소유라 미변경(soft 참조 — feature-0006 docs 와 더는 동일 anchor 아님).

## REV-20260617T083954-ai-claude-bat-encoding-fix [SKIPPED:minor-bugfix] — 설치 스크립트 실행 버그 2종 (TASK-20260617T083954-ai-claude-bat-encoding-fix)
- Date: 2026-06-17
- Change: CHG-20260617T083954-ai-claude-bat-encoding-fix (REQ-0286, AC-20260617T083954-ai-claude-bat-encoding-fix-01~02, **Minor** §12.3). 라이브 제보 버그 수정.
- 자체 점검:
  1. **버그① 재현·수정 실측** — cmd.exe 로 깨진 .bat 재현(`echo`→`cho`, base64 명령실행) →
     ASCII+CRLF+no-chcp 수정본을 cmd.exe 로 재실행, 파싱 정상·`[OK]` 도달 확인.
  2. **버그② 회귀 테스트가 잡음** — cmd.exe 검증 중 지문 mismatch 노출(PEM 파일해시 vs DER
     지문). DER SHA-256 비교로 수정 후 `ACTUAL==FP_HEX` 통과 확인. (검증 절차가 잠복 버그를
     적발한 사례.)
  3. **회귀 가드** — `trust-bundle.sh` 에 .bat 비-ASCII 바이트 검출 die 추가(향후 템플릿에
     비-ASCII 가 들어오면 빌드 실패).
  4. **macOS .command** — `base64 -D`(macOS 전용 옵션)이라 Linux 단위 실행 불가, 지문 로직은
     openssl 기반으로 결정적(FP_HEX 와 동일 계산식). macOS 실기 검증은 운영자 영역.
  5. **보안 불변** — 지문 재검증 로직이 오히려 정상화(이전엔 항상 중단). 신뢰 부트스트랩 모델
     (지문 노출+out-of-band 공유) 불변. 앱/인증/RBAC 무관.
- Outside-voice: **SKIPPED** — Minor 버그픽스(인코딩/줄바꿈/해시비교), 앱 코드 무관, RBAC 무관.
- Risk: cmd.exe 의 본 검증은 자가상승/certutil 을 neuter 한 상태(관리자·실 설치는 미실행). 실제
  certutil 설치는 Windows 관리자 환경에서 1회 확인 권장(운영자/테스터).

## REV-20260617-0309 [SKIPPED:non-RBAC-infra] — 테스터 Root CA 원클릭 설치 번들 (TASK-20260617T083954-ai-claude-trust-bundle)
- Date: 2026-06-17
- Change: CHG-20260617-0309 (REQ-0285, AC-0557~0561, **Major** §12.3, ADR-LAN-0004).
  테스터 Root CA 원클릭 설치 번들 + caddy `/trust/` HTTP 서빙.
- 변경 산출물: `bin/trust-bundle.sh`, `src/trust-bundle/*.tmpl`(4), Caddyfile(/trust handle ×2),
  compose(`/srv/trust` mount), `bin/tls-internal-ca.sh`(자동 호출), docs.
- 자체 점검:
  1. **자동설치 불가 정직 표명** — 페이지 방문만으로 신뢰 루트 자동 설치는 OS/브라우저 보안
     경계상 불가능(MITM 방지). 사용자 승인 1회 필수. FUNCTION REQ-0285 + ADR-LAN-0004 명시.
  2. **신뢰 부트스트랩 무결성** — Root CA 최초 배포는 채널 무관 암호학적 보장 불가. 완화 3중:
     지문 노출 + 스크립트 설치전 SHA-256 재검증(불일치 die) + 운영자 out-of-band 지문 공유.
     `trust-bundle.sh` 가 임베드 base64 디코드 지문이 실제 CA 와 일치하는지 조립 시 자가검증.
  3. **HTTP 서빙 정당성** — `/trust/` 만 HTTP(나머지 :80 은 HTTPS 리다이렉트 유지). CA 미설치
     상태에서 HTTPS 경고 없이 받게 하기 위함. HTTP/HTTPS 둘 다 부트스트랩 무결성은 동일(미설치).
  4. **개인키 미노출** — 번들엔 `rootCA.crt`(공개)만. `rootCA-key.pem` 포함 안 함.
  5. **앱 라우팅 무회귀** — `:443` reverse_proxy(TASK-0297) 를 `handle {}` 로 감싸 보존.
     one-off 테스트 caddy 로 `/trust/`=200 + 앱 `/healthz`=200 동시 동작 머지전 실측.
  6. **검증** — `caddy validate`=Valid(deprecation 0). 런타임: bare`/trust`→301, `/trust/`/
     스크립트/`rootCA.crt`=200, 그외 HTTP→HTTPS 301, 앱 :443=200. 임베드 인증서 디코드 지문
     =실제 CA 일치(win .bat + mac .command 양쪽).
  7. **auth/authz/RBAC 무변경** — 정적 파일 서빙 + 셸 스크립트 + 문서. 앱 코드 0.
- Outside-voice (Codex/subagent): **SKIPPED** — RBAC/권한 catalog 무관, 앱 코드 미변경.
  결정(원클릭 스크립트 방식)은 사용자 사전 승인. 보안(신뢰 부트스트랩) 위험은 본 self-review +
  ADR-LAN-0004 + README 에 명시.
- Risk:
  1. 신뢰 부트스트랩 — 운영자가 지문 out-of-band 공유를 실제로 안 하면 LAN MITM 시 위조 CA
     설치 가능. 운영 절차(지문 공유) 가 통제점. 사내 LAN 가정.
  2. SmartScreen/Gatekeeper 가 미서명 스크립트 차단 가능 — index.html 에 우회 안내. 코드서명은
     별 cycle(인증서 구매 필요).
  3. 외부/미신뢰 LAN 노출 시 SECURITY.md §7.2/§9.7 보완 선행(번들 HTTP 노출 표면 포함 재평가).

## REV-20260617-0308 [SKIPPED:non-RBAC-infra] — caddy :443 정식 front door (TASK-0297)
- Date: 2026-06-17
- Change: CHG-20260617-0308 (REQ-0284, AC-0554~0556, **Major** §12.3). caddy `:443` 502
  해소 + 정식 front door. ADR-LAN-0003.
- 변경 산출물:
  - `src/caddy/Caddyfile`: `reverse_proxy` HTTPS-upstream(`transport http { tls;
    tls_trust_pool file /certs/rootCA.pem; tls_server_name {$WEB_PUBLIC_HOST} }`).
  - `repo/.env`(로컬·비커밋): `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES=172.18.0.0/16`.
  - feature-0006 docs.
- 자체 점검:
  1. **502 해소 검증** — `caddy validate`=`Valid configuration`(deprecation 0,
     tls_trust_pool 최신 형식) + one-off 테스트 caddy(:8443, dbnet 연결) 런타임 프록시
     `/healthz`·`/` = HTTP 200 을 **머지 전** 실측. 머지 후 실 caddy 재시작 + 라이브 재검증.
  2. **XFF 보존(AC-0004 회귀 방지)** — `header_up X-Forwarded-For {client_ip}` 등 기존
     directive 유지. caddy XFF 정규화(REV-20260520-0010) 불변.
  3. **audit IP 정확도(§9.7)** — `WEB_TRUSTED_PROXIES=172.18.0.0/16` 로 web 이 caddy(172.18.0.10)
     XFF 신뢰 → 실 클라이언트 IP 기록. 미설정 시 caddy IP 만 기록되는 PIPA 품질 회귀를 차단.
  4. **upstream 검증** — `tls_insecure_skip_verify` 대신 사내 Root CA 정식 검증 채택.
     SNI/검증명=`WEB_PUBLIC_HOST`(leaf SAN 일치, 내부명 `web` SAN 미추가 — 최소 노출).
  5. **auth/authz/RBAC 무변경** — 전송/프록시 계층만. SECURITY.md §3 인증/인가 변경 비해당.
- Outside-voice (Codex/subagent): **SKIPPED** — RBAC/권한 catalog 변경 아님
  (`feedback_outside_voice_for_rbac.md` 트리거 비해당). 앱 코드 미변경(Caddyfile + 로컬 .env +
  문서). 결정(front door 전환)은 사용자 사전 승인. 보안/audit 위험은 본 self-review 명시.
- Risk:
  1. caddy 가 단일 hop 가정 — 앞단에 추가 upstream proxy(ALB/CF) 가 생기면 `{client_ip}` /
     trusted proxy 경계 재검토 필요(REV-20260520-0010 Risk 1 과 동일 계보).
  2. 외부/미신뢰 LAN 노출 시 `WEB_TRUSTED_PROXIES` 협소화 + web port 비공개 선행(§9.7).
  3. web leaf 인증서 SAN 에 `web` 부재 — `tls_server_name` 의존. leaf 재발급 시 SAN 정책
     유지 필요(`bin/tls-internal-ca.sh` 기본 SAN 이 `web` 제외).

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

## REV-20260901T103000-ai-claude-corp-cert-expiry-monitor [SUBAGENT:self] — SHIP

- **일시**: 2026-09-01 · **범위**: `bin/cert-expiry-check.sh`·`bin/install-cert-expiry-cron.sh` 신규,
  Makefile/ci.yml 테스트 등재, 회귀 9건
- **Trigger**: 인증서·TLS 만료 감시 — security 인접(자격증명 수명). 배포 스파인 무변경
- **Verdict**: PASS
- **Human Approval Needed**: no

### 판단

- **왜 배포 스파인을 건드리지 않았나.** `preflight_tls()` 의 만료 검사를 공용 스크립트 호출로
  바꾸면 구현이 하나가 되어 드리프트가 사라진다. 그러나 그 파일은 **배포 스파인**이고, 스크립트
  부재·권한 같은 사소한 사유가 배포 전체를 막는다. 얻는 것(중복 제거)보다 잃을 수 있는 것(배포
  불능)이 크다고 봤다. 대신 **상수 관계를 테스트로 잠가** 드리프트만 차단했다 — 중복은 남기되
  «조용히 갈라지는 것»은 막는 절충이다.
- **왜 `set -e` 를 쓰지 않았나.** 이 스크립트에서 비-0 종료는 대부분 **정상 신호**(만료 임박)다.
  `-e` 면 첫 경고에서 죽어 Root CA 축을 영영 못 본다 — 감시 도구에서 `-e` 는 기본값이 아니다.
- **왜 주 1회인가.** 임계(30일/180일) 대비 주 1회면 최악에도 최소 23일 여유가 남는다. 매일이면
  같은 경고가 30회 반복돼 신호가 소음이 되고, 소음이 된 경보는 무시된다.

### 잔여 (정직 표기)

- **cron 은 설치하지 않았다** — `--print` 로 확인만 했고 crontab 은 무변경이다. 설치는 사용자
  판단(운영 호스트의 cron 을 임의로 바꾸지 않는다). 설치 전까지 이 감시는 **수동 실행 전용**이다.
- **알림 채널은 cron 메일뿐** — 메일이 설정돼 있지 않은 호스트면 경보가 로그에만 남는다.
  Slack/webhook 연동은 범위 밖.
- **폐기(revocation) 축은 여전히 없다** — 사용자 결정. leaf 키 유출 + MITM 은 이 감시가 막지
  못한다. 그 판단 근거는 MODIFY.md 의 «왜 CRL/OCSP 가 아닌가» 참조.

### 검증 중 관측 — 무관한 flaky 테스트 1건 (§8.1 기록만)

전수 실행에서 `feature-0003` 의 `test_datasource_test_nonblocking.py::
test_concurrent_probes_do_not_block_event_loop` 가 1회 FAIL 했다. **본 변경과 무관**하다 —
확인 방법: ① 내 diff 는 feature-0003 을 건드리지 않는다 ② **수정 없는 main 체크아웃**에서 같은
테스트가 PASS ③ 내 worktree 에서도 부하 없이 재실행하면 PASS.

원인은 **벽시계 임계**다. 그 테스트는 0.3초 블로킹 probe 5개가 `0.75초` 안에 끝나는지로
«이벤트 루프 비블로킹» 을 판정하는데, 그 순간 호스트에서 이미지 재빌드 + 라이브 스택 +
다른 테스트 컨테이너가 CPU 를 경합하고 있었다. 직렬화(1.5초)와 «느린 머신»(0.75초 초과)을
구분하지 못하는 판정축이다.

제안(기록만, 본 cycle 범위 밖 — feature-0003 소유): 절대 시간 대신 **직렬 대비 비율**로 판정
하거나(같은 워크로드를 순차 실행해 baseline 을 재고 그 절반 미만인지 확인), 임계를 넉넉히
잡고 재시도를 둔다. 지금 형태는 CI 러너가 느릴 때 «비블로킹 회귀» 로 오탐할 수 있다.

## REV-20260902T113500-ai-claude-feature-0006-lan-proxy-access [SKIPPED:tool-restricted:security,backend,qa] — SHIP

- **일시**: 2026-09-02 · **범위**: `src/windows/sync_mysql_ai_web_portproxy.ps1` 멱등화 (+ feature 문서)
- **Trigger**: 5분 주기 포트프록시 재설정이 라이브 TCP 연결을 절단 — 네트워크 접근 경로 변경(§12.3 Major)
- **채널**: 세션에 상위 우선순위 subagent 금지 지시가 걸려 있어 §18.8.2 carve-out 적용.
  제약 없는 채널(기계적 검증 + 자체 적대 검토)로 수행, subagent 도메인(security/backend/qa)은
  **미커버로 명시**. `codex review` 는 시도했으나 시간 예산 내 결론 미도달 — 도착 시 별 entry.
- **Verdict**: PASS (결함 1건 자체 적발 → 같은 cycle 수정, 판별력 대조로 확인)
- **Human Approval Needed**: no (§12.3 Major — 롤백이 스크립트 파일 되돌리기 1건, deploy_scope 기본 included)

REQ-20260902-portproxy-idempotent-sync / **Major** §12.3

### 판단 1 — 이것은 «엄격한 타임아웃» 이 아니라 실제 절단이다

사용자 질문은 "실제 에러인가, 타임아웃 기준이 엄격한 것인가" 였다. 답은 **둘 다 아니다**:

- 클라이언트 상한 `_WAIT_TIMEOUT_SEC = 90s` 는 서버 보류 `_WAIT_MAX_HOLD_SEC = 55s` 보다 넉넉하고,
  실제 성공 호출 961건의 소요 중앙값이 **55.3초**로 설계대로 동작한다. 타임아웃 여유는 충분하다.
- 실패는 `TimeoutError` 가 아니라 `RemoteDisconnected` 다 — 기다리다 지친 것이 아니라 **연결이
  끊긴 것**이다. 타임아웃 값을 늘려도 줄여도 이 실패는 사라지지 않는다.

따라서 "임계값을 완화한다" 는 방향은 증상조차 건드리지 못한다. 원인을 찾아야 했다.

### 판단 2 — 로그 레벨을 낮추는 것은 조치가 아니다

러너 코드에는 `한 번의 실패는 정상 범위다` 라는 주석이 있고 실제로 `streak` 을 센다. 그래서
"1회 순단은 INFO 로 강등" 이 손쉬운 선택지로 보였다. **채택하지 않았다** — 5분마다 규칙적으로
끊기는 것은 «정상 범위의 순단»이 아니라 고칠 수 있는 결함이고, 레벨을 낮추면 그 사실이 보이지
않게 될 뿐이다. 관측을 지우는 것은 원인을 없애는 것과 다르다. 러너는 **한 줄도 바꾸지 않았다**.

### 판단 3 — 왜 «변경 시에만 재설정» 인가

스크립트의 목적은 WSL 재부팅으로 바뀐 IP 를 따라가는 것이다. 매 실행이 리스너를 새로 세우는 것은
그 목적의 수단이었지 목적이 아니다. 이미 맞는 매핑을 다시 쓰는 것은 **아무 것도 바꾸지 않으면서
연결만 끊는다** — 순수한 손실이다. 목적은 그대로 두고 부작용만 없애는 것이 최소 변경이다.

대안으로 «주기를 늘린다»(5분 → 1시간)를 검토했으나 기각: 절단 빈도만 줄고 IP 추종은 느려진다 —
두 축을 동시에 나쁘게 만드는 교환이다. 멱등화는 두 축을 동시에 개선한다.

### 판단 4 — 파싱 실패 시 폴백 방향

`Get-PortProxyEntries` 가 상태를 못 읽을 때 «건너뛴다»와 «재설정한다» 중 후자를 골랐다. 전자는
파싱이 깨진 날 포트포워딩이 **조용히 사라져** 서비스 전면 차단이 되고, 후자는 최악이라도 종전
동작(5분마다 절단)으로 돌아갈 뿐이다. 실패 비용이 비대칭이라 선택은 명확하다.

같은 이유로 빈 딕셔너리와 `$null` 을 구분했다 — PowerShell 에서 둘 다 falsy 로 뭉뚱그리기 쉬운데,
"등록된 것이 없다" 와 "모른다" 는 정반대 조치를 요구한다.

### 판단 5 — 로케일 의존을 처음부터 배제

`netsh` 출력은 OS 표시 언어를 따라간다(이 호스트는 한국어라 헤더가 "수신 대기"). 헤더 문구에
기대는 파서는 언어가 바뀌는 순간 **빈 결과를 조용히 돌려주고**, 그러면 위 폴백이 상시 발동해
수정이 무력화된다. 데이터 행의 IP/포트 형태만 보면 언어와 무관하다.

### 판단 6 — BOM 은 취향이 아니라 요건

한글 주석을 넣으면서 BOM 없이 두면 PS 5.1 이 기본 코드페이지로 읽어 한글이 깨진다. 추측이 아니라
**대조 실측**으로 확인했다: BOM 있을 때 839자, 없을 때 515자. 이 feature 는 REQ-0286 에서 이미
같은 부류(`.bat` 인코딩 → 라인 파싱 붕괴)를 겪었다. `bridge_setup.ps1`(한글 + BOM)이 선례다.

### 범위 밖으로 남긴 것 (§8.1 기록)

`-SkipFirewall` 없이 실행할 때 방화벽 규칙도 매 실행마다 `Remove-NetFirewallRule` → `New-` 로
재생성된다 — **같은 결함 클래스**다. 이번 cycle 에서 고치지 않은 이유: 현재 배포는 `-SkipFirewall`
로 돌아 이 경로가 발동하지 않으므로 **라이브에서 검증할 수 없고**, 검증 못 하는 변경을 네트워크
접근 경로에 넣는 것이 이번 수정의 이득보다 위험하다. `REPORT.md §8` 에 개선 제안으로 기록한다.

### 리스크

- 파싱이 잘못되면 → 폴백으로 종전 동작. 서비스 영향 없음(절단이 남을 뿐).
- 상태를 잘못 "같다"고 판정하면 → IP 변경을 못 따라가 접근 차단. 이를 막으려 비교는 **정확히
  일치**할 때만 skip 하고, 부분 일치·형식 이상은 전부 재설정으로 보낸다.
- 롤백: 스크립트 파일 되돌리기 1건. 배포 산출물이 git 트리 파생이라 원복 경로가 단순하다.

### 검증 채널 선택과 그 결과 (§18.8.2)

본 세션에는 **상위 우선순위 지시로 Agent tool(subagent) 호출이 금지**되어 있다. §18.8.2 의
"상위 우선순위 지시 carve-out" 에 따라 제약 없는 채널로 검증을 수행했다:

1. **기계적 검증 (수행)** — Windows PowerShell 5.1 실호스트에서 구문 파싱 · 인코딩 무결성 ·
   실 netsh 출력 파싱 · 멱등 판정 · **결손 주입 대조**. 상세는 `TEST.md` Run 기록.
2. **자체 적대 검토 (수행, 결함 1건 적발)** — 아래.
3. **codex review (시도)** — `codex exec` 로 diff 를 직접 전달해 적대 리뷰를 요청했으나, 파일
   탐색에 시간을 소모해 10분 예산 안에 결론을 내지 못했다(관측된 codex 특성). 결과가 도착하면
   `[CODEX:...]` entry 로 별도 기록한다.

#### 자체 적대 검토가 잡은 것 — 「방어를 넣었다」 ≠ 「방어가 성립한다」

첫 구현은 "상태를 못 읽으면 `$null` 을 돌려 종전대로 재설정한다" 는 계약을 주석으로 **선언**
했지만, 호출이 `Invoke-Netsh ... -IgnoreExitCode` 였다. 그 플래그가 netsh 의 비-0 종료를 삼켜
**예외가 오르지 않고 오류 텍스트가 반환**되고, 그 텍스트는 행 정규식에 매칭되지 않아 빈 맵이
된다 — 선언한 $null 경로에 **도달할 수 없었다**.

결과가 안전한 쪽(재설정)이라 증상으로 드러나지 않는 종류의 결함이다. 드러나는 것은
`portproxy_state_known` 이 `true` 라고 거짓 보고하는 것뿐이고, 그건 다음 사람이 이 스크립트를
디버그할 때 **정확히 잘못된 방향으로 안내한다**.

#### 주입 하네스 자체의 함정 (기록해 둘 가치가 있음)

이 결함을 잡았다고 생각한 첫 테스트는 **판별력이 없었다** — stub 이 무조건 `throw` 해서 수정 전
코드도 `$null` 을 돌려줬다. 즉 «수정 전에도 통과하는 테스트»로 «고쳤다»를 주장할 뻔했다.
stub 이 실제 `Invoke-Netsh` 의 계약(`-IgnoreExitCode` 면 텍스트 반환, 아니면 throw)을 모사하도록
고친 뒤에야 두 버전이 `MAP Count=0` vs `NULL` 로 갈렸다. **주입 테스트는 「수정 전 코드에서
실패하는지」를 확인해야 비로소 근거가 된다.**

## REV-20260902T124500-ai-claude-feature-0006-lan-proxy-access [CODEX:portproxy-idempotent] — SHIP

- **일시**: 2026-09-02 · **범위**: 직전 cycle 산출물의 적대 리뷰 반영
- **Trigger**: §18.8.1 codex-review 대안 경로 (세션 subagent 제약 하 제약 없는 채널)
- **Verdict**: P1 1건(이미 수정됨 — 독립 확인) · P2 4건 중 **3건 수정 · 1건 수용+기록**
- **Human Approval Needed**: no

### 지적별 처리

| # | 지적 | 처리 |
|---|---|---|
| P1-1 | `-IgnoreExitCode` 가 $null 계약을 무력화 | **이미 수정됨** — 자체 적대 검토가 먼저 적발. codex 도 말미에 인정. 독립 확인으로 기록 |
| P2-2 | `portproxy_changed` 가 legacy 삭제 미포함 | **수정** — 자기모순 필드 해소 |
| P2-3 | 삭제 실패도 `legacy_ports_deleted` 에 기록 | **수정** — `try/catch` 로 성공분만 |
| P2-4 | hostname 형태 매핑을 파서가 누락 → legacy 미삭제 | **수정(되돌림)** — legacy skip 자체를 제거해 근본 회피 |
| P2-5 | TOCTOU (조회~판정 창) | **수용 + 주석 기록** — 아래 |

### P2-5 를 고치지 않은 이유

netsh 에는 원자적 비교-교체가 없다. 창을 없애려면 매 실행 재설정으로 돌아가야 하는데 그것이
바로 이번에 고친 결함이다. 트레이드오프의 실체는 **확률적 5분 창 vs 확정적 5분 절단**이고,
전자가 명백히 낫다. 전제(이 스크립트 외에 portproxy 를 건드리는 주체 없음)가 깨지면 종전
코드에서도 두 주체가 서로를 덮어썼을 것이므로 이번 변경이 만든 문제가 아니다.

### 이 리뷰에서 배운 것 — 「무해한 호출도 남기지 않는다」가 위험을 들여왔다

legacy skip 은 순수한 정리 동기였고 실제로 무해해 보였다. 그러나 그 자리에서는 **얻을 것이
없었고**(legacy 엔 끊길 연결이 없다) **잃을 것이 있었다**(파서가 못 읽는 형태는 영영 미삭제).
"이 최적화가 겨냥하는 문제가 이 자리에 실재하는가" 를 먼저 묻지 않은 것이 원인이다.

## REV-20260902T140000-ai-claude-feature-0006-lan-proxy-access [SKIPPED:docs-only-live-record] — SHIP

- **일시**: 2026-09-02 · **범위**: 라이브 검증 결과 기록 (docs-only, 코드 변경 없음)
- **Trigger**: 배포 후 완료 게이트 — deploy-backed 완료 기준(§16.3)의 라이브 실측 단계
- **Verdict**: PASS — 목표 지표 0건 (배포 전 대조 8·8·8·12건)
- **Human Approval Needed**: no

### 판정을 「0건」으로만 쓰지 않은 이유

관측 구간에 예약작업이 **5회 정상 실행**(`LastTaskResult=0`)됐음을 함께 기록했다. 그것이 없으면
「작업이 멈춰서 0건」과 「돌면서도 끊지 않아 0건」이 구분되지 않는다 — 전자는 더 나쁜 상태인데
같은 숫자로 보인다. 부재를 근거로 쓰려면 **그 부재가 관측될 조건이 실제로 성립했는지**를 같이
보여야 한다.

같은 이유로 `wait_for_request` 완주 22건(21건이 55초 완주)과, 13:34:00 시작분이 13:34:34 sync 를
**관통**한 사실을 별도로 남겼다 — 이건 "안 끊겼다" 의 직접 증거다.

### 관측 하네스가 낸 오판을 기록으로 남긴 이유

자동 판정 스크립트가 목표 지표(`conn.retry`/`api.fail`)가 아니라 **모든 `lvl=WARN`** 을 세어
`VERDICT: WARN 잔존 — 추가 조사 필요` 를 출력했다. 실제 잔존분은 `hb.stale_build`(러너 버전 안내)
와 `ai.cmdline.stdin`(정상 동작 로그)로 이번 이슈와 무관했다.

그대로 받아썼다면 **해소된 것을 미해소로** 보고했을 것이다. 방향은 반대지만 뿌리는 이 cycle 이
두 번 만난 것과 같다 — 「판정식의 모수가 판정 대상과 일치하는가」. 자동 판정의 출력이 아니라
**그 판정이 무엇을 세었는지**를 봐야 한다.

## REV-20260909T050000-portproxy-task-repair [SKIPPED:non-policy-doc] — ACCEPTED

- **일시**: 2026-09-09
- **범위**: Windows 예약작업 복구 기록(문서만). **저장소 코드 변경 0** — 제품 소스·정책 doc 미변경.
- **Trigger**: non-policy-doc → §18.8 표에 따라 panel SKIP. 저장소의 register/sync 스크립트는
  손대지 않았고(정본이 이미 옳다), 변경된 것은 사용자 머신의 작업 등록 상태다.
