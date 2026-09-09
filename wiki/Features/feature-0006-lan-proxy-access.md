---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, proxy, tls, security]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0006-lan-proxy-access
linked_unit: unit/feature-0006-lan-proxy-access
created: 2026-05-26
sources:
  - ../../unit/feature-0006-lan-proxy-access/docs/FUNCTION.md
  - ../../docs/SECURITY.md
---

# Feature — LAN Proxy Access

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0006-lan-proxy-access |
| 상태 | active |
| 정본 | [[../../unit/feature-0006-lan-proxy-access/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | Caddy TLS proxy · Windows port proxy · 인증서 |

## 1. 개요

**Caddy** TLS 프록시 + **Windows `netsh` port proxy** 자산. 외부 LAN 노출 endpoint 의 TLS 종단 책임 + `X-Forwarded-For` trust 정합 (SECURITY.md §9.7) 의 정본 위치.

## 2. 상세

### 2.1 책임 경계

- **입력**: `WEB_*` env, `ENABLE_WEB_TLS_PROXY`, Windows 포트 프록시 운영 절차
- **출력**: Caddy 프록시 설정, Windows 운영 스크립트, TLS 관련 문서
- **side-effect**: `../../artifacts/certs/` 인증서 디렉토리

### 2.2 핵심 흐름

1. 루트 compose 가 feature 경로 Caddyfile 마운트
2. `make web-tls-cert` 가 `artifacts/certs/` 인증서 생성
3. 운영자가 Windows 스크립트로 LAN port-proxy 설정

### 2.3 X-Forwarded-For trust 정책 (AC-0004, ADR-0017 cascade)

Caddyfile 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` directive 강제 → web upstream 의 `X-Forwarded-For` 는 **항상 단일 hop client_ip**. multi-hop / spoof 방지.

```caddy
https://{$WEB_PUBLIC_HOST}, :443 {
  reverse_proxy web:8000 {
    header_up X-Forwarded-For {client_ip}
  }
}
```

feature-0003 의 [[feature-0003-agent-web-ui|`_get_client_ip()`]] (AC-0205~0207) 와 dual ownership 으로 정합.

## 3. 특징

- TLS 종단 = Caddy 단일 hop (single TLS termination 원칙 — TASK-0057)
- dev 환경은 `docker-compose.override.yml` 로 web 컨테이너 plain HTTP 가동 (browser 자동화 친화)
- Windows scheduled task 로 LAN port-proxy 영속화
- **엣지 보안 헤더 일괄 부착** (2026-08-11, 정본 feature-0003 `TASK-20260811T1830-api-exposure-hardening`) — `Caddyfile` 에서 nosniff · X-Frame-Options · Referrer-Policy · Permissions-Policy 를 일괄 부착 + `Server` 제거 + CSP Report-Only. **HSTS 는 의도적 제외** — `/trust` 평문 CA 번들 배포와 충돌하고 헤더가 호스트 단위라 경로 예외가 불가능하다.
- **평문 HTTP 표면은 두 자리다** (2026-08-28, 정본 feature-0043 P0-AC) — `/trust/*` 에 더해 브리지 설치 스크립트 `/static/agent/bridge_setup.sh`·`.ps1` **두 파일만** 평문으로 연다. 같은 부트스트랩 데드락이기 때문이다: 스크립트가 하는 첫 일이 사내 CA 를 받아 신뢰시키는 것인데 그 스크립트 자신을 https 로만 주면 CA 없는 머신은 받을 수 없다. `/static/*` 를 통째로 열지 않은 이유는 범위가 예외가 감당하려던 것보다 훨씬 넓어지기 때문이고, 평문의 위험은 **지문·체크섬 대조**가 덮는다 — 대조 값은 https(웹 콘솔)로 온 명령에 실려 있어 바꿔치려면 두 채널을 동시에 잡아야 하고, 스크립트는 값이 어긋나면 실행을 중단한다.
- **롤링 배포와의 결합 계약** (2026-08-11, 정본 feature-0014 `20260811T1557-edge-rolling-gate`) — Caddy passive 격리(`fail_duration` 30s)는 값 그대로 유지하고(인하는 실장애 격리를 함께 약화시킨다), 대신 `bin/deploy-web.sh` 가 다음 replica 를 내리기 전에 **엣지 후보 복귀**(admin API `fails==0` + Caddy→replica `/livez` 실도달)를 확인한다. `Caddyfile` 주석이 이 결합 계약을 고정한다 — 종전에는 실측 10초 롤링 간격이 30s 격리 창보다 짧아 available upstream 이 0 이 되며 배포당 12~17초 전면 503 이 났다.
- **인증서 만료 감시 — 게이트와 감시는 다른 축이다** (2026-09-01, `cert-expiry-monitor`) — `bin/deploy-web.sh` 의 `preflight_tls()` 는 **배포할 때만** 돌고 **Root CA 를 아예 보지 않아**, 배포가 없으면 신호도 없고 첫 신호가 전면 outage 였다(CA 만료는 테스터 전원 재설치라 회복 비용이 훨씬 크다). 주기(cron 주 1회) 감시 `bin/cert-expiry-check.sh` 가 leaf 30일 + **Root CA 180일**을 보고 `--live <host>` 로 **실제 서빙본**까지 대조한다 — 디스크 cert 만 갱신하고 배포하지 않으면 사용자가 받는 것은 여전히 옛 cert 다. ⚠ 감시 임계가 게이트(14일)보다 좁으면 게이트가 먼저 울려 감시가 아무것도 더하지 않으므로 스크립트가 그런 설정을 **거절**하고 두 상수의 관계를 테스트가 잠근다. 폐기 인프라(CRL/OCSP) 대신 만료 감시를 고른 근거는 정본 §「왜 CRL/OCSP 가 아니라 만료 감시인가」.
- **포트프록시 동기화가 5분마다 살아있는 연결을 끊고 있었다** (2026-09-02, `portproxy-idempotent-sync`, Major §12.3) — Windows 예약작업 `mysql_ai_web_portproxy_sync` 가 매 실행마다 **조건 없이** `netsh interface portproxy delete`→`add` 를 해, WSL IP 가 바뀌지 않은 평상시에도 80/443 의 기존 TCP 연결을 전부 끊었다. 짧은 요청은 재시도가 가려 주지만 개인 AI 브리지 러너의 55초 블로킹 대기는 그대로 드러나 `RemoteDisconnected` 를 맞았다(WARN 14건 중 **13건이 sync 실행 후 3~19초**, 서로 다른 러너가 같은 벽시계 위상). 이제 **현재 매핑이 이미 원하는 값이면 아무것도 하지 않는다** — 상태를 못 읽으면 종전대로 재설정하는 fail-safe 이고(빈 딕셔너리 「없다」와 `$null` 「모른다」를 구분한다), 파싱은 헤더 문구가 아니라 데이터 행의 «IPv4 포트 IPv4 포트» 패턴이라 **로케일 무관**이며, 한글 주석이 붙으므로 **UTF-8 BOM** 이 필수다(없으면 PS 5.1 이 839자 중 324자를 잃는다 — 실측). ⚠ legacy 포트 삭제에는 멱등 skip 을 **적용하지 않는다**: 활성 연결이 없어 이득이 없고, netsh 가 허용하는 hostname 형태 매핑은 IPv4 정규식에 안 잡혀 skip 하면 **영영 삭제되지 않는다**. 라이브 22분(sync 5회) 실측에서 목표 지표 `conn.retry`+`api.fail` **0건** — 배포 전 같은 길이 구간은 8·8·8·12건이었다. TOCTOU 는 수용 + 주석 기록(원자적 비교-교체 부재 · **확률적 5분 창**과 **확정적 5분 절단**의 교환).
- **예약작업이 5분마다 오류창을 띄웠고, 실행 계정이 애초에 틀려 있었다** (2026-09-09, `portproxy-task-repair` → `portproxy-s4u`) — 사용자 제보는 «`C:\ProgramData\mysql_ai_web_portproxy\run_hidden.vbs` 을(를) 찾을 수 없습니다» 오류창이 5분 정각마다 뜬다는 것이었다. 진단이 두 겹을 벗겼다. ⓐ **정의와 실행이 어긋나 있었다** — 작업 XML 의 액션은 정본대로 `powershell.exe` 직접 실행인데(Tasks 폴더 229개 전수 검색으로 확인) 스케줄러는 레지스트리 `TaskCache` 쪽 액션(`wscript.exe` + 사라진 vbs)을 실행했다(이벤트 로그 `id=200`/`id=129` 로 확정). 이 하나가 세 모순을 설명한다 — `Get-ScheduledTask` 조회 불가 · `Register-*` 의 「이미 있습니다」 거부 · **같은 이름으로 재등록해도 vbs 가 되살아나는 것**. 새 이름 `mysql_ai_web_portproxy_sync2` 로 등록해 벗어났다(저장소 스크립트는 `-TaskName` 을 받으므로 정본 변경 불요). ⓑ **SYSTEM 으로는 애초에 돌지 않는다** — sync 스크립트는 `wsl.exe` 로 WSL 안의 기본 라우트 IP 를 읽는데 **WSL 은 LOCAL SYSTEM 계정을 지원하지 않는다**(`WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED` · `EXIT=-1`, 프로브 작업 실측). SYSTEM 등록은 **겉보기로 정상**이고(스케줄러 상태 「사용」) 실패는 `LastTaskResult` 를 봐야 드러난다 — 라이브가 그 상태였다. 사용자 계정 + `Interactive` 는 조회가 되지만 5분마다 PowerShell 콘솔 창이 뜨고(그것을 숨기려던 우회가 곧 vbs 였다), **사용자 계정 + `S4U`** 는 비밀번호 저장 없이 로그온 세션 없이 실행하므로 **창 없이 조회가 된다**. 정본 등록 스크립트를 `-UserId $RunAsUser -LogonType S4U`(신규 `-RunAsUser` 기본값 = 실행 사용자 · `-RunLevel Highest` 유지 — `netsh interface portproxy` 변경에 승격이 필요하다)로 교정하고, 트리거에서 `AtLogOn` 을 제거(S4U 와 함께 「일부 트리거만 시작」 경고 + 의미 중복)했으며 `RepetitionDuration` 을 1일 → **3650일**로 늘렸다(하루 뒤 반복이 멎던 문제 · `[TimeSpan]::MaxValue` 를 주면 등록 자체가 실패한다 — 실측). ⚠ **앞 TASK 의 「vbs 불요」 판정은 근거가 틀렸었다** — 결론은 유지되지만 이유가 「원래 불필요했다」가 아니라 「SYSTEM 도 Interactive 도 아닌 **제3의 선택지**를 쓰기 때문에 이제 불필요해졌다」다. ⚠ **미해소**: 옛 이름의 유령 작업이 스케줄러 **메모리 캐시**에만 남아 재부팅 전까지 계속 실행된다(디스크·레지스트리는 정리됨 · `MultipleInstances IgnoreNew` 라 「무재발」과 「억제됨」이 관측만으로 갈리지 않아 두 번 착시를 겪었다) · 재부팅 후 S4U 작업 `LastTaskResult` 0 확인이 남았다.

## 4. 사용법

```bash
make web-tls-cert     # 인증서 생성
make caddy-up         # Caddy 기동
# Windows 운영
src/windows/port-proxy-add.bat
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0001-platform-runtime]] — Web/TLS 운영 자산 공유

### 5.2 본 feature 를 의존하는 feature

- [[feature-0003-agent-web-ui]] — `_get_client_ip()` trust 정합 의존
- [[feature-0045-zd-bridge-continuity]] — `ext-tool-mcp-a/b` 2 upstream LB 가 본 feature Caddyfile 거주 ([[../Architecture/Overview|Architecture Overview]] §2.4)
- [[feature-0043-external-llm-bridge]] — 설치 스크립트 2파일의 평문 HTTP 예외가 본 feature Caddyfile 거주 (2026-08-28, P0-AC)

## 6. 관련 정본

- [[../../unit/feature-0006-lan-proxy-access/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../docs/SECURITY|docs/SECURITY.md]] §9.7 — X-Forwarded-For trust 정책

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — trust boundary
- [[../Decisions/ADR-0017-github-automation-stack]]
- [[../Decisions/ADR-0018-github-automation-decommission]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0001-platform-runtime]] · [[feature-0003-agent-web-ui]]

## 9. 외부 link

- [Caddy Server](https://caddyserver.com/)
- [Windows `netsh interface portproxy`](https://learn.microsoft.com/en-us/windows-server/networking/technologies/netsh/netsh-interface-portproxy)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/proxy` · `#domain/security`
