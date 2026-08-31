---
run_at: 2026-08-31T18:10:00+09:00
session: ai/claude-corp/feature-0043-schannel-revocation
scope: Windows 러너 수신 — Schannel 폐기검사 완화 + 신뢰 경로 단일화 + 조용한 결함 3종
verdict: PASS
---

# Run — TASK-20260831T175500-schannel-revocation

Environment: **Windows-native** (실 Windows PowerShell 5.1 `5.1.19041.6456` + 윈도우 동봉
`curl 8.13.0 Schannel` + `Python 3.14`) · 라이브 엣지 `https://112.185.196.20`

> UI 표면 변경 없음 — PB-0008 브라우저 시각검증 대상 아님(설치 스크립트·TLS 경로). 대신 이
> 결함이 사는 곳인 **실 Windows PowerShell** 에서 직접 실측했다. WSL 내부 검증으로는 이
> 클래스를 원리적으로 볼 수 없다(WSL curl 은 OpenSSL 이라 폐기검사를 하지 않는다).

## 1. 근본 원인 실측

| 확인 항목 | 명령 | 결과 |
|---|---|---|
| 윈도우 curl 백엔드 | `curl.exe --version` | `curl 8.13.0 (Windows) libcurl/8.13.0 **Schannel** zlib/1.3.1 WinIDN` |
| 사내 root CA 확장 | `openssl x509 -text` | CRL Distribution Points **부재** · Authority Information Access **부재** |
| 엣지 leaf 확장 | `openssl s_client` → `x509 -text` | 동일 — 폐기 정보 배포점 부재 |
| 폐기검사 완화 옵션 지원 | `curl.exe --help all \| grep revoke` | `--ssl-no-revoke` · `--ssl-revoke-best-effort` 둘 다 존재 |

## 2. 재현 → 수정 (curl 직접 호출)

| 케이스 | rc | 결과 |
|---|---|---|
| `--cacert` 만 (**사용자가 겪은 것**) | **60** | `curl: (60) schannel: CertGetCertificateChain trust error CERT_TRUST_REVOCATION_STATUS_UNKNOWN` |
| `--cacert --ssl-revoke-best-effort` | **0** | 162,942 bytes 수신 |
| `--cacert --ssl-no-revoke` | **0** | 162,942 bytes 수신 |

## 3. 스크립트 파싱 (BOM 회귀 방지 — 한글 주석이 크게 늘었다)

```
[Parser]::ParseFile(bridge_setup.ps1)  → ParseErrors = 0
Get-Content -Raw → U+B7EC('러') 존재 = True     (BOM 첫 3바이트 = efbbbf)
```

## 4. 동작 매트릭스 — 새 함수 3개를 실 PowerShell 5.1 에서 직접 구동

정본에서 `Invoke-NativeCapture` ~ `Get-RemoteFile` 구간을 그대로 떼어 dot-source 한 뒤,
라이브 엣지에서 수신. 기대 SHA256 = `af7c3fe1980838de343113155396640bc2f8e975351e11de74dd6ba8f996ae7c`.

| 케이스 | 조건 | 결과 | 판정 |
|---|---|---|---|
| A | 폐기검사 옵션 감지 | `[--ssl-revoke-best-effort]` (좁은 쪽 채택) | PASS |
| B | curl + 감지 옵션 = **정상 경로** | `via=curl` · **sha OK** | PASS |
| C | 옵션 제거 = **수정 전 재현** | curl exit 60 → `via=python` · **sha OK** | PASS |
| D | curl 부재 | `via=python` · **sha OK** | PASS |
| E | **무관한 CA 를 pin** | **THROW** — `curl (exit 60): … CERT_TRUST_IS_UNTRUSTED_ROOT` + `python (exit 1): … CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate` | PASS (pin 이 지켜진다) |
| F | 옵션 제거 + 파이썬 불가 | **THROW** — `curl (exit 60): … CERT_TRUST_REVOCATION_STATUS_UNKNOWN` + `python (exit 127): … 인식되지 않습니다` | PASS (원 사유가 사용자에게 도달) |
| G | 임시 파일 잔재 | `_download.py` leftover = **False** | PASS |

**E 가 이 표의 핵심이다** — 완화가 폐기검사 축에만 적용됨을 «주장» 이 아니라 실 TLS
핸드셰이크로 보였다. `--ssl-revoke-best-effort` 가 켜진 상태에서도 신뢰 실패는 실패다.

## 5. 이 실측이 **잡아낸** 결함 (정적 자기검토가 통과시킨 것들)

초안은 A~G 를 돌리기 전까지 «완성» 으로 보였다. 실측이 3건을 되돌렸다:

1. **pin 우회** — 초안의 `Invoke-WebRequest` 폴백이, 사내 CA 가 `CurrentUser\Root`·
   `LocalMachine\Root` 에 이미 있는 이 머신에서 **무관한 CA 를 pin 해도 수신을 성공**시켰다
   (E 케이스가 `!! 통과했다 — pin 우회 via=iwr` 를 냈다). → IWR 제거.
2. **fail-open** — 없는 파이썬 경로로 부르니 `via=python` **성공 반환**(파일 없음).
   `$LASTEXITCODE` 는 실행 실패 시 건드려지지 않아 초기값 0 이 «성공» 이 됐다.
   → 초기값 127 + `Test-Downloaded`.
3. **사유 유실** — curl exit 60 인데 회수 길이 **0**. `SilentlyContinue` 아래 파이프가
   네이티브 stderr 의 ErrorRecord 를 버린다(3-way 실측: Stop=던짐 / SilentlyContinue=len 0 /
   **Continue=len 727 원문 확보**). → `Continue` + ErrorRecord 원문 추출.

## 6. 회귀 스위트

| 항목 | 결과 |
|---|---|
| `test_windows_tls_revocation.py` (신규 18건) | **18 passed** |
| 동일 스위트를 **수정 전(HEAD) 코드**에 적용 (§16.7 G11-b) | **13 failed / 5 passed** — 수정을 인코딩한 단언 전부 FAIL |
| `_ps_code` 주석 스트리퍼 ↔ 실 PowerShell `[PSParser]::Tokenize` 대조 | 토큰 2,602 · tokenizeErrors 0 · 프로브 3종 분류 일치 |
| feature-0043 디렉토리 (로컬 py3.12) | 918 passed / 3 failed — **3건은 내 파일 제외 시에도 동일**(기준선 900+3, 격리 실행 시 24/24 PASS = 교차오염 아티팩트) |
| 컨테이너 전수 (py3.11, 등재 8 디렉토리) | rc=0 |
| `sh -n` · `bash -n` (`bridge_setup.sh`) | OK |

### G11-b 세부 — 수정 전 FAIL 한 13건

`test_ps_code_actually_removes_this_files_own_comments` ·
`test_windows_installer_relaxes_schannel_revocation` ·
`test_narrow_revoke_option_is_tried_before_the_blunt_one` ·
`test_revoke_option_is_feature_detected_not_assumed` ·
`test_revoke_relaxation_still_passes_the_pinned_ca` ·
`test_runner_download_never_uses_invoke_webrequest` ·
`test_python_fallback_uses_the_same_trust_anchor_as_the_runner` ·
`test_launch_failure_is_not_reported_as_success` ·
`test_exit_zero_alone_is_not_treated_as_downloaded` ·
`test_checksum_retry_checks_its_own_failure` ·
`test_stderr_reason_is_not_discarded` ·
`test_failure_report_collects_every_attempted_path` ·
`test_posix_installer_explains_the_divergence`

수정 전 코드에서도 PASS 한 5건은 «수정과 무관한 축을 지키는» 단언이다(스트리퍼 자체 검사 ·
POSIX 판 부재 단언 · 서빙 사본 동일성 2건 · BOM). 의도된 결과다.

## 7. 미검증 (정직 표기)

- **첫 실사용자의 실제 설치 왕복은 미관측.** 위 실측은 수신 함수를 직접 구동한 것이고,
  `.ps1` 전체를 처음부터 끝까지(핸들러 등록 + 러너 상주 포함) 돌리지는 않았다 — 이 머신의
  기존 브리지 상태를 검증 목적으로 갈아엎지 않는다는 판단이다.
- **독립 관점의 적대 검증 미수행** — 하네스 제약(Agent 도구 금지)으로 subagent 패널을
  돌리지 못했다. 위 5절이 보여주듯 이 cycle 의 결함 3건 중 2건은 자기검토를 통과했다.
