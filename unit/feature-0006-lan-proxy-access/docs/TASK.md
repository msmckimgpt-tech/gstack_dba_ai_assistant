---
doc_type: TASK
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## TASK-20260910T100000-portproxy-closeout — 재부팅 후 종결 확인

사용자 재부팅(2026-09-09 22:51) 후 2026-09-10 10:01 실측. **전건 해소 확인.**

| 축 | 관측 | 판정 |
|---|---|---|
| 유령 작업(오류창) | 부팅 후 **669.7분(약 11시간)** 경과, `wscript.exe` **0건** | **소멸** — 5분 주기라면 130회 넘는 실행 기회가 있었고, 살아 있는 인스턴스가 없어 `IgnoreNew` 억제 가설도 배제된다 |
| S4U 동기화 작업 | `state=Ready` · `logon=S4U user=mckim runlevel=Highest` · `repeat=PT5M dur=P3650D` · **`lastrun=09/10 09:59:59 rc=0`** · `next=10:04:04` · **`missed=0`** | **정상 동작** — SYSTEM 시절 rc=1 이던 것이 rc=0 |
| portproxy 매핑 | `112.185.196.20:80/443 → 172.26.154.233` | 유지 |
| 옛 이름 잔재 | XML 없음 · `TaskCache\Tree\<옛이름>` **이미 소멸**(재부팅 시 스케줄러가 빈 껍데기 정리) | 정리 완료 |

### 이 cycle 의 판정 규칙이 실제로 필요했다

앞 두 창(15:15~15:27 · 15:57~16:05)에서 「무재발」로 두 번 오판했는데, 그때는 **떠 있는 오류창
인스턴스가 `MultipleInstances IgnoreNew` 로 새 실행을 억제**하고 있었다. 이번 판정이 신뢰되는
이유는 ① 인스턴스가 0건이라 억제할 것이 없고 ② 관측 창이 11시간(경계 130회 이상)이기 때문이다.
**「무재발」은 관측 길이와 억제 상태를 함께 적어야 근거가 된다.**

- [x] 재부팅 후 유령 소멸 · S4U rc=0 · 매핑 유지 확인 — 종결

## TASK-20260909T070000-portproxy-s4u — 실행 계정 교정 (SYSTEM → 사용자 + S4U)

앞 TASK(`…-portproxy-task-repair`)의 **판정 하나를 정정**한다.

### 정정 — 「`run_hidden.vbs` 불요」는 근거가 부족했다

앞 TASK 는 「정본이 SYSTEM+ServiceAccount 로 등록하므로 Session 0 격리로 창이 안 뜬다 → vbs 불요」
로 판정했다. **그 전제가 틀렸다.** SYSTEM 으로는 애초에 이 스크립트가 동작하지 않는다:

| 실행 계정 | WSL 조회 | 콘솔 창 | 근거 |
|---|---|---|---|
| SYSTEM | **불가** | — | `WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED` · `EXIT=-1` (프로브 작업 실측) |
| 사용자 + Interactive | 가능 | **뜸** | `inet 172.26.154.233/20` · `EXIT=0` |
| **사용자 + S4U** | **가능** | **안 뜸** | `Register-ScheduledTask … -LogonType S4U` 후 실행 rc=0 |

즉 원래 구성(사용자 계정 + vbs 숨김)은 **비정본 우회가 아니라 SYSTEM 제약을 피한 실용적 해법**
이었고, vbs 는 그 구성에서 필요했다. 그것을 「불요」로 단정한 것은 오판이다.

**다만 결론(=vbs 를 되살릴 필요는 없다)은 유지된다** — 이유가 다르다. S4U 라는 제3의 선택지가
창 없이도 WSL 조회를 가능하게 하므로 vbs 가 필요 없어진다. 「원래 불필요했다」가 아니라
「이제 불필요해졌다」이다.

### 변경

- `src/windows/register_mysql_ai_web_portproxy_task.ps1`
  - `-UserId "SYSTEM" -LogonType ServiceAccount` → `-UserId $RunAsUser -LogonType S4U`
  - `-RunAsUser` 파라미터 신설(기본값 = 실행 사용자). `-RunLevel Highest` 유지.
  - 트리거에서 `AtLogOn` 제거(S4U 와 「일부 트리거만 시작」 경고 · 의미 중복),
    `RepetitionDuration` 1일 → 3650일(하루 뒤 반복이 멎던 문제).
- `docs/FUNCTION.md` — 실행 계정 계약 절 신설(위 표 + 등록 계약).

### 라이브 적용

사용자 머신의 `mysql_ai_web_portproxy_sync2` 를 S4U 로 재등록했다(`logon=S4U user=mckim
runlevel=Highest`, `repeat=PT5M dur=P3650D`). 매핑·접속은 유지된다.

### 남은 것

- **유령 작업은 재부팅 전까지 계속된다** — 옛 이름 `mysql_ai_web_portproxy_sync` 가 스케줄러
  메모리에만 남아 wscript 를 실행한다(디스크·레지스트리는 정리됨, `schtasks /change` 는
  「시스템에 없습니다」). 사용자가 재부팅하기로 했다.
- 재부팅 후 S4U 작업의 `LastTaskResult` 가 0인지 확인이 남는다(재등록 직후 조회는 `267009`
  = 실행 중 상태였다).

- [x] SYSTEM 불가 실증 + S4U 대안 실증 (사용자 요청 "먼저 실증")
- [x] 정본 등록 스크립트 교정 + FUNCTION 계약 명시
- [x] 라이브 작업 S4U 재등록
- [x] **재부팅 후 종결 확인 (2026-09-10 10:01)** — 아래 §종결 실측

## TASK-20260909T050000-portproxy-task-repair — 예약작업 손상으로 5분마다 오류창 (사용자 제보)

사용자 제보(스크린샷): `Windows Script Host — 스크립트 파일 "C:\ProgramData\mysql_ai_web_portproxy\run_hidden.vbs"을(를) 찾을 수 없습니다.` 가 반복 표시.

### 진단 — 「등록은 있는데 목록에 없는」 손상 작업

| 관측 | 값 |
|---|---|
| `wscript.exe` 부모 | `svchost.exe`(PID 2464) → 그 서비스는 **`Schedule`(Task Scheduler)** |
| 실행 주기 | 5분 정각(12:14:00 · 12:19 · 12:24 · 13:59 · 15:04 · 15:09) |
| 소유자 / 세션 | `DESKTOP-CK5SFCJ\mckim` / **SessionId 1**(사용자 대화형) |
| `run_hidden.vbs` 실물 | **없음**(`C:\ProgramData\mysql_ai_web_portproxy\` 에는 ps1 3개 + 백업만) |
| 저장소 자산 | register/sync 모두 **vbs 를 쓰지 않는다** — `powershell.exe` 직접 실행. 배포본도 동일(md5·크기 일치) |
| `Get-ScheduledTask` | `mysql_ai_web_portproxy_sync` **조회 불가** |
| `schtasks /query /tn` | **조회됨** — 액션은 정본과 동일한 powershell 직접 실행 |
| `Register-ScheduledTask` | `파일이 이미 있으므로 만들 수 없습니다` (= 등록은 존재) |
| 작업 XML | `<UserId>S-1-5-18</UserId>`(SYSTEM) + **`<LogonType>InteractiveToken</LogonType>`** |

**근본 원인**: `SYSTEM` + `InteractiveToken` 은 유효하지 않은 조합이다. 이 상태에서
① cmdlet 은 그 작업을 파싱하지 못해 목록에서 사라지고 ② `Register-*` 는 "이미 있다"며 거부하고
③ Task Scheduler 서비스는 실행은 시도한다 — 세 모순이 한 원인에서 나온다. 정본 등록 스크립트는
`New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest` 이므로
**이 상태는 정본이 만든 것이 아니다**.

### `run_hidden.vbs` 는 필요한가 — 아니다 (사용자 요청으로 선행 검토)

vbs 래퍼의 용도는 **콘솔 창 숨김**이다. 사용자 계정 + 대화형으로 등록하면 5분마다 PowerShell
검은 창이 뜨므로 `wscript` 로 감싼다. 그러나 정본은 **SYSTEM + ServiceAccount** 로 등록하고,
SYSTEM 작업은 **Session 0 격리**라 사용자 데스크톱에 창을 띄우지 못한다 → 숨김 래퍼가 원천적으로
불필요하다. 오히려 vbs 경유는 세 가지를 잃는다:

1. **로그온 전 동작 불가** — 정본 트리거는 부팅·로그온·5분주기 3종. 사용자 계정 작업은 로그인해야 돈다.
2. **권한** — `netsh interface portproxy` 변경은 승격 필요. 정본은 `RunLevel Highest`.
3. **실패 지점 추가** — 파일 하나가 사라지면 5분마다 오류창(= 이번 증상).

즉 vbs 는 **비정본 등록 방식의 증상**이지 복원 대상이 아니다.

### 조치

- `schtasks /delete` 로 손상 작업 제거(cmdlet 은 못 지운다) → XML 소멸 확인.
- 정본 파라미터를 **현재 운영값 그대로 승계**해 재등록: `-ListenAddress 112.185.196.20`
  (정본 기본값 `127.0.0.1` 을 쓰면 LAN 접속 경로가 끊긴다) · `-DistroName Ubuntu` ·
  `-RemoteAddresses LocalSubnet`. sync 는 80/443(+레거시 18080)만 다루므로 `0.0.0.0:6379`·
  `0.0.0.0:28080` 매핑은 무영향.
- **매핑·접속은 전 구간 유지**(`112.185.196.20:80/443 → 172.26.154.233`, healthz 200).

### ⚠ 진짜 원인 — 「XML 과 레지스트리 캐시의 불일치」 (이벤트 로그로 확정)

작업 스케줄러 이벤트 로그(임시 활성화)가 결정적 증거를 냈다:

```
EV id=200  TaskName=\mysql_ai_web_portproxy_sync  Action=C:\Windows\System32\wscript.exe
EV id=129  TaskName=\mysql_ai_web_portproxy_sync  PID=35340
```

같은 작업의 **XML 파일 내용은 `Command=powershell.exe`** 다(`C:\Windows\System32\Tasks` 229개
파일 전수 검색으로 확인 — 매칭 1건, 그 안에 vbs 없음). 즉 **정의(XML)와 실행 액션(레지스트리
`TaskCache`)이 어긋나 있고 스케줄러는 캐시 쪽을 실행한다.**

이것이 모든 모순을 설명한다 — 왜 `Get-ScheduledTask` 로 안 보이는지, 왜 `Register-*` 가
「이미 있다」며 거부하는지, 그리고 **왜 삭제 후 같은 이름으로 재등록해도 vbs 가 되살아나는지**
(같은 이름이 옛 캐시를 물려받는다). 이 cycle 에서 두 번 복원했는데도 재발한 이유가 이것이다.

관측된 재발 시각: 12:14 · 12:19 · 12:24 · 13:59 · 15:04 · 15:09 · 15:34 · 15:49 · 15:54 — 5분 정각.
중간의 공백은 **떠 있는 오류창 인스턴스가 `MultipleInstances IgnoreNew` 로 새 실행을 억제**한
것이며(닫으면 다음 경계에 다시 뜬다), 이를 「해결됨」으로 오독하지 않도록 매번 창을 닫고 재관측했다.

### 최종 조치 (사용자 결정 2026-09-09)

1. **새 이름으로 등록** — 옛 이름은 캐시가 오염됐으므로 `mysql_ai_web_portproxy_sync2` 로
   `schtasks /create /sc MINUTE /mo 5 /ru SYSTEM /rl HIGHEST`. 등록 후 **`Get-ScheduledTask` 조회가
   정상 동작**(=손상 없음)함을 확인했다. 저장소 등록 스크립트는 `-TaskName` 파라미터를 받으므로
   정본 변경은 필요 없다.
2. **레지스트리 고아 항목 제거** — 옛 이름 작업을 지우고 XML 이 사라진 뒤에도 그 이름으로 실행이
   계속됐으므로(15:54 실측), `TaskCache\{Tree,Tasks,Plain,Boot,Logon,Maintenance}` 의 해당 GUID
   항목을 **`reg export` 백업 후** 삭제했다.

### 실측 결과 (2026-09-09 15:51~16:06)

| 항목 | 결과 |
|---|---|
| 새 작업 `mysql_ai_web_portproxy_sync2` | 등록 성공 · **`Get-ScheduledTask` 조회 정상**(= 손상 없음) · SYSTEM · 5분 주기 |
| 옛 이름 작업 | `schtasks /delete` 성공 · **XML 소멸 확인** · `TaskCache\Tree\<옛이름>` 은 **Id·속성이 빈 껍데기**만 남음(실행 근거 아님) |
| 레지스트리 고아 항목 | `Tree` Id 조회·`Tasks` 역탐색 모두 **0건** — 삭제 대상이 이미 없었다(앞선 `schtasks /delete` 가 함께 지웠다) |
| sync 스크립트 직접 실행 | **exit 0** · `portproxy_action: "unchanged"`(멱등) · 80·443 `verify_listen`·`verify_connect` 모두 `true` |
| 매핑·접속 | 전 구간 유지 — `112.185.196.20:80/443 → 172.26.154.233`, `healthz 200` |
| 8분 재발 관측(15:57~16:05) | **0건** |

### ⚠ 재발 종료는 아직 단정하지 않는다 (정직 표기)

8분 무재발은 관측됐으나, **그 창 내내 15:54:00 에 뜬 인스턴스(pid 4896)가 살아 있었다.** 이 작업은
`MultipleInstances IgnoreNew` 라 살아 있는 인스턴스가 새 실행을 억제하므로, 「무재발」과
「억제됨」이 관측만으로 갈리지 않는다. 이 cycle 에서 같은 착시를 두 번 겪었다(15:15~15:27 ·
15:57~16:05) — **떠 있는 창을 닫은 뒤 5분 경계를 2회 이상 지켜봐야 확정된다.**

남은 확인은 사용자가 화면의 오류창에서 [확인]을 누른 뒤 10분 관찰하는 것으로 충분하다.
다시 뜬다면 스케줄러 서비스의 메모리 캐시가 원인이며(서비스 재시작은 보호되어 불가), 그때는
**재부팅**이 남은 수단이다.

### 미해소 · 주의

- `Register-ScheduledTask`(cmdlet)는 이 머신에서 계속 `매개 변수가 틀립니다`(0x80070057)로 실패해
  `schtasks /create` 로 등록했다. 등록 후에도 **cmdlet 조회는 여전히 안 된다**(`schtasks` 로는 정상).
  작업 정의가 아니라 이 머신의 조회 계층 문제로 보이나 원인 미규명.
- 레지스트리 `TaskCache\Tasks` 229건 전수 스캔에서 `run_hidden` 참조 **0건** — 고아 항목 가설은 기각.
- 작업 스케줄러 이벤트 로그(임시 활성화 후 원복)로 12분 관측 시 잡힌 wscript 실행 작업은
  `\WSL Load Monitor`(1분 주기, `E:\wsl-load-monitor\Run-WslLoadMonitorHidden.vbs`, 파일 존재, 무관)뿐.
- **재발 종료 여부는 별도 관측으로 판정한다** — 12분 무출현이 관측됐으나 그 시점 기존 인스턴스가
  살아 있어 `MultipleInstances IgnoreNew` 로 억제됐을 가능성을 배제하지 못했다.

- [x] 원인 진단 + `run_hidden.vbs` 필요성 검토(불요 판정)
- [x] 손상 작업 제거 + 정본 파라미터 승계 재등록 + 매핑·접속 무결 확인
- [x] 새 이름(`_sync2`)으로 정상 등록 + sync 직접 실행 exit 0 + 매핑·접속 무결
- [ ] **재발 종료 확정** — 떠 있는 인스턴스가 억제 중이라 미확정. 창을 닫고 5분 경계 2회 관측 필요.
      재발 시 남은 수단은 재부팅(스케줄러 메모리 캐시).

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
- [x] TASK-20260902T124500-ai-claude-feature-0006-lan-proxy-access (REV-20260902T124500-... [CODEX:portproxy-idempotent] — 적대 리뷰 P2 반영, **Minor** §12.3). 직전 cycle 산출물에 codex 적대 리뷰 P1 1건(이미 자체 적발·수정한 `-IgnoreExitCode` — **독립 확인**) + P2 4건. P2 중 3건 수정: ①legacy 삭제 skip 최적화 **되돌림**(이득 없음 — legacy 엔 활성 연결이 없고 없는 매핑 delete 는 아무 것도 끊지 않는다 / 위험만 있음 — hostname 형태 매핑을 파서가 못 읽어 영영 미삭제) ②legacy 삭제 **성공한 것만** 기록(실패도 기록해 원장이 거짓말하던 것) ③`portproxy_changed` 가 legacy 삭제를 포함(`legacy_ports_deleted:[18080]` + `changed:false` 자기모순 해소). P2-5 TOCTOU 는 **수용 + 주석 기록**(원자적 CAS 부재 · 확률적 5분 창 vs 확정적 5분 절단의 교환). PS 5.1 재검증 6축 PASS.
- [x] TASK-20260902T140000-ai-claude-feature-0006-lan-proxy-access (**라이브 검증 완료** — 배포 + 22분 실측). Windows 배포본 교체는 **관리자 권한 필요**(WSL 은 기존 파일 ACL 에 막힌다) — 사용자 실행 후 sha256 대조 일치. 라이브 관측 13:33:30~13:55:45(sync 5회 정상 실행, `LastTaskResult=0`)에서 **목표 지표(`conn.retry`+`api.fail`) 0건** — 배포 전 동일 길이 구간은 8·8·8·12건이었다. 완주 wait 22건 중 21건이 55초 보류 완주, 13:34:00 시작분은 13:34:34 sync 를 **관통**했다. 잔존 WARN 2건(`hb.stale_build`·`ai.cmdline.stdin`)은 이번 이슈와 무관하며 TEST.md 에 명시. ⚠ 관측 하네스가 목표 지표가 아닌 전 WARN 을 세어 오판 라벨을 냈던 것도 함께 기록.

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

## TASK-20260910-listener-recovery — 아이콘 배포 중 공인 주소 접근 복구

1.3.1 출하 검수에서 Windows112.185.196.20:80/443은 연결 거부, localhost와 WSL 직접 주소는 정상임을 확인했다. 설정값 존재와 예약작업 rc0은 실제 리스너 정상의 근거가 아니었다. 기존 10:01 종결 기록의 범위를 설정·예약작업 상태 확인으로 한정한다.

### 2.1 Implementation Plan
- 위험도 Minor. 기존 공개 주소/포트/전달 대상을 유지하며 없는 리스너만 복구한다. 다른 포트·방화벽·서비스 재시작은 변경하지 않는다.
- 동기화 스크립트: 매핑과 실제 TCP 리스너가 모두 맞을 때만 unchanged. 설정은 같지만 리스너가 없으면 활성 연결을 확인하고, 0건일 때 해당 포트만 recovered. 재등록 뒤에도 없으면 nonzero. 실제 연결 검사 실패도 nonzero.
- 운영 복구는 RepairOnly: 상태 조회 실패·대상 불일치·방화벽/legacy 변경 요청을 거절한다. 기존 정기 WSL IP 동기화 기본 계약은 유지한다.
- 관리자 적용: 소스/기존 배포본 SHA 고정 검사, 대상 매핑·WSL 직결 확인, ProgramData 백업·정본 배포, 80/443 한정 호출, 다른 매핑·6379/28080 리스너 보존 대조.
- Windows 비승격 mock 6건 및 독립 QA/security 검토. 실제 적용은 UAC를 통해 Windows 사용자가 승인해야 한다. 일반 토큰 administrator=false, ProgramData write/예약작업 조회 Access denied.

- [x] 원인 확인·리스너 조건과 엄격 복구 옵션 구현·Windows mock 6건 및 독립 리뷰
- [x] 관리자 적용·공인 주소 HTTPS 다운로드·실제 DQA 기본 진입 검증 — 사용자 UAC 승인, 80/443 recovered 및 타 포트 보존, 기본 실제 DQA 화면 PASS

- [x] 최신 c684d12a 제품 및 1.4.0 출하 소유권 보존, 운영 배포본 SHA 동일 확인

- [x] 통합6bdcc7ba의 양 부모 보존·충돌 해소 독립 검토 및 최종 출하 기록 확인
