---
doc_type: TEST
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- Caddy 설정이 새 feature 경로에서 마운트되는지 확인
- 인증서와 Caddy 상태 파일이 `../../../../artifacts`에 생성되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 caddy 서비스가 `feature-0006-lan-proxy-access/src/caddy/Caddyfile`을 사용한다
- TEST-0002: `Makefile`의 TLS 인증서 생성 경로가 `../../../../artifacts/certs`를 사용한다
- TEST-0003: 엄격한 네트워크 운영 시나리오 정의 필요
- TEST-0004 (TASK-0006 / TASK-0087, **Major** §12.3): Caddyfile 의 `reverse_proxy web:8000` 블록이 `header_up X-Forwarded-For {client_ip}` directive 를 명시한다. 검증:
  - **A1 (syntax)**: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` 가 exit 0 + `{client_ip}` placeholder 인식.
  - **A2 (live header replace)**: Caddy 컨테이너 가동 + 외부 클라이언트가 `curl -H 'X-Forwarded-For: 1.2.3.4' https://<WEB_PUBLIC_HOST>/api/session` → web 측 (`_get_client_ip`) 가 `1.2.3.4` 가 아닌 Caddy container IP (예: 172.18.0.x) 를 반환. live 검증 사용자 위임.

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 네트워크 시나리오는 후속 작성 예정
- 2026-05-21 (TASK-0006 / TASK-0087): Caddyfile static syntax 검증을 사용자 docker 환경에서 진행 권장 — `caddy validate` PASS 후 cycle-finalize.
- 2026-06-17 (TASK-0296): leaf 체인 `openssl verify` OK + 라이브 web `:18080` `Verify return code: 0` + HTTP 200.
- 2026-06-17 (TASK-0297): `caddy validate`=Valid + one-off 테스트 caddy(dbnet, :8443) 런타임 `/healthz`·`/`=200(502 해소). 라이브 caddy `:443`=200·`Verify 0`, web `:18080`=200, HTTP→HTTPS 301.
- 2026-06-17 (TASK-20260617T083954-ai-claude-trust-bundle):
  - Environment: Linux (openssl/curl/one-off caddy). Run: `caddy validate`=Valid; one-off 테스트 caddy(:8080/:8443) → `http://…/trust/`·`install-trust-windows.bat`·`rootCA.crt`=200, bare `/trust`→301 `/trust/`, 그외 HTTP→HTTPS 301, 앱 `:443`=200. 임베드 base64 디코드 지문=실제 Root CA 일치(win .bat·mac .command). placeholder 잔존 0.
  - Environment: Windows-browser (PB-0008). **사유 명시(미수행)**: `/trust/` 는 inline CSS + 단순 OS감지 JS 의 **정적 다운로드 페이지**로 앱 로직/동적 상태 표면 없음. server-side(HTTP 200 + 링크/지문 정확성) 검증으로 충족. 실제 설치(`certutil`/`security`)는 Windows/macOS 클라이언트 권한 동작이라 CI 브리지 불가 — 운영자/테스터 1회 수동 확인 영역. 시각 회귀 우려 낮음(단일 페이지). 후속 운영 검증 시 실제 브라우저 확인 권장.
  - 사후 PB-0008(실 Windows Chrome, win-browser.py): `http://112.185.196.20/trust/`=200 렌더(지문박스·Win/mac/crt 버튼·OS감지 mac카드 숨김), 앱 `https://112.185.196.20/`=200 로그인 렌더. 증거 `artifacts/pb0008-trust/{trust-page-ip,app-login-ip}.png`. (호스트명은 Windows hosts admin 부재로 IP 검증.)
- 2026-06-17 (TASK-20260617T083954-ai-claude-bat-encoding-fix): Environment: Windows cmd.exe (실측). 깨진 .bat 재현(`echo`→`cho`·base64 명령실행) 확인 → ASCII+CRLF+no-chcp 수정본을 neuter(자가상승+certutil 제거) 후 cmd.exe 실행: echo/지문표시/base64 디코드/지문검증 전 구간 정상, `ACTUAL==FP_HEX` 통과(이전 잠복 mismatch 해소), `[OK]` 도달. `file`=ASCII+CRLF 확인. `.command` 는 `base64 -D`(macOS 전용)라 Linux 단위실행 불가 — 지문 로직 openssl 결정적. 실 certutil/security 설치는 관리자 환경 1회 확인 권장.

## Run — TASK-20260901T103000-ai-claude-corp-cert-expiry-monitor (2026-09-01)

Environment: WSL Ubuntu (openssl 3.x) · 라이브 엣지 `112.185.196.20`
> UI 표면 없음(운영 스크립트) — Windows-browser 시각검증 대상 아님.

**동작 실측 — 생성한 cert 로 경계를 넘겨 본다** (텍스트 검사가 아니라 실행 결과):

| 케이스 | 기대 | 실측 |
|---|---|---|
| leaf 100일 | exit 0 (정상) | **0** |
| leaf 20일 | exit 1 (WARN, 30일 임계) | **1** |
| leaf 3일 | exit 2 (CRITICAL, 7일 임계) | **2** |
| leaf 여유 + **rootCA 10일** | exit 2 (CA 축 단독 발동) | **2**, 메시지가 `rootCA` 지목 |
| cert 파일 부재 | 비-0 (fail-open 금지) | **비-0** |
| `--leaf-warn 5` (게이트 14일보다 좁음) | exit 3 거절 | **3**, 사유에 «게이트» 명시 |

**실환경 1회**: `--live 112.185.196.20` → leaf(2028-09-19)·rootCA(2036-06-14)·live 3축 OK, exit 0.

**드리프트 잠금**: `deploy-web.sh` 의 `checkend 1209600`(14일)과 감시의 `DEPLOY_GATE_DAYS=14` 가
어긋나면 FAIL 하는 단언 포함 — 두 파일이 조용히 갈라지는 것을 막는 유일한 연결.

**자가적용 검증**: `unit/feature-0006-lan-proxy-access/tests` 를 Makefile·ci.yml 양쪽에 등재했고,
직전 cycle 의 parity 테스트가 이를 검증했다. **한쪽만 등재한 사본에서 그 테스트가 FAIL 함**도
별도 실증(가드가 실제로 무언가를 잡는다는 근거).

결과: 신규 9건 PASS · `bash -n` 2개 파일 OK · cron 은 `--print` 확인만(**crontab 무변경**).

## Run — TASK-20260902T113500-ai-claude-feature-0006-lan-proxy-access (2026-09-02)

- Environment: WSL Ubuntu + **Windows PowerShell 5.1** (실호스트, 한국어 로케일)
- Scope: `src/windows/sync_mysql_ai_web_portproxy.ps1` 멱등화
- Verdict: **PASS (pre-deploy 4축)** / 라이브 효과 검증은 배포 후 아래 «라이브 관측» 절에 추가

### 진단 재현 (수정 전 상태의 결함 자체를 관측)

| 관측 | 값 |
|---|---|
| `bridge.events.jsonl` 19시간분 WARN | `api.fail` 289 · `conn.retry` 209 |
| 안정 러너 기준 발생률 | **시간당 12건** (= 5분당 1건), 인접 간격 중앙값 300.1초 |
| 실패 시각 위상 | 벽시계 5분 경계(:04/:09/:14/:19…). **시작 시각이 다른 별개 러너들이 동일 위상** |
| sync heartbeat 대조 | WARN 14건 중 **13건이 실행 후 3~19초 이내** |
| 실패한 대기 호출 소요 | 3~55초 **균등 분포** (절단이 연결 수명이 아닌 절대 시각에 걸림) |
| 성공한 대기 호출 소요 | 961건 중앙값 **55.3초** (서버 보류 55초 설계대로 — 타임아웃 여유 충분) |

### 수정 후 검증 (Windows PowerShell 5.1 실행)

| # | 항목 | 방법 | 결과 |
|---|---|---|---|
| 1 | 구문 | `[Parser]::ParseFile()` | **PASS** — 오류 0 |
| 2 | 인코딩 | 한글 문자 수 대조 (BOM 유/무) | **PASS** — BOM 839자 / no-BOM 515자 → BOM 필요 확인 |
| 3 | 파싱 | AST 로 함수 추출 후 **실 netsh 출력**에 적용 | **PASS** — 4개 매핑 정확, `112.185.196.20:443 → 172.26.154.233:443` 포함 |
| 4 | 멱등 판정 | 현재 상태 vs 원하는 상태 비교 | **PASS** — 일치 → `delete/add` SKIPPED |

검증 하네스: `verify.ps1` (AST 함수 추출 + 실 netsh 호출). mock 이 아니라 **실제 로케일의 실제
출력**을 파싱시켜, 로케일 의존 결함이 있으면 그 자리에서 드러나게 했다.

### 라이브 관측 (배포 후)

<!-- 배포 후 3회 sync 주기(15분) 이상 관측 결과를 여기에 기록 -->

### 결손 주입 — $null 계약이 실제로 성립하는가 (판별력 확인 포함)

`Get-PortProxyEntries` 의 계약: netsh 를 읽지 못하면 `$null`(상태 모름 → 종전대로 재설정),
읽었는데 행이 없으면 빈 맵(등록 없음 → 생성). 선언이 아니라 **동작**을 확인했다.

| # | 주입 | 기대 | 결과 |
|---|---|---|---|
| B | netsh **비-0 종료** (오류 텍스트 반환) | `$null` | **PASS** |
| C | netsh exit 0 + 행 없는 배너 텍스트 | 빈 맵(Count=0) | **PASS** |
| D | 로케일 무관 합성 행 2건 (connect 포트가 다른 케이스 포함) | 정확히 2건 파싱 | **PASS** |

**판별력 대조** (테스트가 수정 전 코드에서 실패하는지):

| 코드 | netsh 비-0 종료 시 |
|---|---|
| 수정 전 (`-IgnoreExitCode` 있음) | `MAP Count=0` — 상태를 안다고 거짓 주장 |
| 수정 후 (플래그 제거) | `NULL` — 상태 모름 |

→ 테스트가 두 버전을 구분한다. 첫 하네스는 stub 이 무조건 throw 해 **양쪽 다 통과**시켰고,
그 상태로 "고쳤다"고 보고할 뻔했다. 하네스를 실제 계약 모사로 바꾼 뒤 판별력이 생겼다.

## Run — TASK-20260902T124500-ai-claude-feature-0006-lan-proxy-access (2026-09-02)

- Environment: Windows PowerShell 5.1 (실호스트, 한국어 로케일)
- Scope: codex 적대 리뷰 P2 반영
- Verdict: **PASS (6축)**

| # | 항목 | 결과 |
|---|---|---|
| 1 | 구문 파싱 | PASS — 오류 0 |
| 2 | 인코딩 무결성 (BOM) | PASS |
| 3 | 실 netsh 파싱 | PASS — 4매핑, 브리지 경로 포함 |
| 4 | legacy 기록이 `try` 안에만 (실패 미기록) | PASS |
| 5 | legacy 상태기반 skip 제거 | PASS |
| 6 | `portproxy_changed` 가 legacy 삭제 포함 | PASS |

### 라이브 관측 (배포 후) — 2026-09-02 13:33:30 ~ 13:55:45

- Environment: 라이브 (Windows 예약작업 + WSL 러너 pid 297256 + 엣지 `112.185.196.20`)
- 배포: `C:\ProgramData\mysql_ai_web_portproxy\sync_mysql_ai_web_portproxy.ps1` 를 main 본으로 교체
  (관리자 권한 필요 — 사용자 실행). 무결성 sha256 대조 **일치**.

**목표 지표 = `conn.retry` + `api.fail`** (사용자가 보고한 "서버에 닿지 못했다 / 대기 실패").

| 구간 (각 22분) | 목표 지표 |
|---|---|
| 10:30~10:52 (배포 전) | 8건 |
| 11:00~11:22 (배포 전) | 8건 |
| 11:22~11:44 (배포 전) | 8건 |
| 11:44~12:06 (배포 전) | 12건 |
| **13:33~13:55 (배포 후)** | **0건** |

같은 구간에 예약작업은 **5회 실행**됐다(13:34/13:39/13:44/13:49/13:54, `LastTaskResult=0`) —
작업이 멈춰서 0건이 된 것이 아니라, **돌면서도 연결을 끊지 않았다**.

**관통 증거**: 구간 내 완주한 `wait_for_request` 22건 중 **21건이 55초 보류를 완주**
(dur_ms median 55,402). 특히 13:34:00 시작분(55,366ms)은 13:34:34 sync 실행을 **관통**했다 —
수정 전이라면 그 지점에서 `RemoteDisconnected` 가 났을 구간이다.

**부수 확인**: portproxy 매핑 4개 유지 · `https://112.185.196.20/` HTTP 200.

#### 잔존 WARN 2건 — 이번 이슈와 무관 (은폐하지 않고 명시)

| 시각 | 이벤트 | 성격 |
|---|---|---|
| 13:36:19 | `hb.stale_build` | 러너가 서버 배포본과 다른 버전이라는 **1회성 안내**. 당일 feature-0043 이 수 차례 배포된 결과 |
| 13:38:17 | `ai.cmdline.stdin` | 명령줄 길이 상한 초과 시 질문을 stdin 으로 넘긴다는 **정상 동작 로그**(당일 머지된 winargv-cmdline-limit) |

둘 다 사용자가 보고한 3종("서버에 닿지 못했다 / 대기 실패 / 하트비트 실패")이 아니다.

> ⚠ **관측 하네스의 판정 라벨이 부정확했다** — 스크립트가 목표 지표가 아니라 **모든 `lvl=WARN`**
> 을 세어 `VERDICT: WARN 잔존` 을 출력했다. 위 2건이 무관 이벤트임을 확인해 정정했다.
> 자동 판정을 그대로 받아썼다면 해소된 것을 미해소로 보고할 뻔했다 — **판정식의 모수가
> 목표 지표와 일치하는지**를 먼저 봐야 한다.
