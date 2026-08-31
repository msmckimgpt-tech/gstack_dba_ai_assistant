---
run_at: 2026-08-31T18:42:00+09:00
session: ai/claude-corp/feature-0043-schannel-postdeploy
scope: POST-DEPLOY — 라이브 배포본(b28c3fab)에서 사용자 시나리오 재현
verdict: PASS
---

# Run (POST-DEPLOY) — TASK-20260831T175500-schannel-revocation

Environment: **Windows-native** (실 Windows PowerShell 5.1 + 윈도우 동봉 curl 8.13.0 Schannel)
· 라이브 엣지 `https://112.185.196.20` · 배포 커밋 **`b28c3fab`**

배포 전 실측(같은 TASK 의 pre-deploy fragment)은 **워킹트리 사본**으로 돌렸다. 이 fragment 는
**사용자가 실제로 내려받는 배포본 바이트**로 같은 시나리오를 다시 돌린 기록이다 — §16.3
deploy-backed 완료 기준(push/merge ≠ 배포 완료).

## 1. 배포 반영 확인

| 확인 | 결과 |
|---|---|
| 배포 이미지 | `mysql-ai-web:b28c3fab` (GIT_COMMIT 일치) |
| 양 replica `GIT_COMMIT` | `repo-web-a-1` = **b28c3fab** · `repo-web-b-1` = **b28c3fab** |
| 마이그레이션 게이트 | migrate-lint PASS · pending 0 (`current == head == 0056`) |
| asset stamp | baked 주입 확인 (`?v=dev` 잔존 **0**) |
| 엣지 `/healthz` | **HTTP 200** |
| soak (90s) | **통과 — 배포 안정** |
| **무중단 실측** | caddy `no upstreams available` = **0건** (배포 스크립트 [5] 항목 — soak 는 blip 을 관용하므로 별도 확인) |
| RestartCount | web-a=0 · web-b=0 · caddy=0 |

## 2. 서빙 바이트 동일성 — replica 내부 직접 해시

롤링 배포 창에서 구 replica 가 신 요청에 구 콘텐츠를 주는 함정이 이 저장소의 실측 이력이다.
그래서 엣지 응답만 보지 않고 **각 컨테이너 안의 파일을 직접** 해시했다.

| 대상 | `bridge_setup.ps1` | `bridge_setup.sh` |
|---|---|---|
| main 정본 | `b9ab7961…f390a` | `d54ca604…2f162` |
| `repo-web-a-1` 내부 | **동일** | **동일** |
| `repo-web-b-1` 내부 | **동일** | **동일** |
| 엣지 응답 ×6 | **6/6 동일** | — |

## 3. 사용자 시나리오 재현 — **배포본 바이트로**

사용자가 받는 경로 그대로 평문 HTTP 로 설치 스크립트를 받고(부트스트랩 데드락 회피 경로),
그 **배포본에서** 수신 함수 구간을 떼어 실 Windows PowerShell 5.1 에서 구동했다.

```
받은 bridge_setup.ps1 SHA256 = b9ab79610c6ae77b6ff5c5169f9c01a8890ef379ee1ffb5864220751ba4f390a  (정본 일치)
BOM = efbbbf                                                                    (5.1 이 CP949 로 읽지 않는다)

DETECTED      = [--ssl-revoke-best-effort]
USER-SCENARIO : via=curl  bytes=167906  ← 수정 전 이 지점이 exit 60 으로 죽었다
BOGUS-CA      : failed as expected (pin holds)
```

**`via=curl`** 이 핵심이다 — 폴백이 아니라 **curl 경로 자체가 살아났다**. 사용자가 겪은
`curl: (60) … CERT_TRUST_REVOCATION_STATUS_UNKNOWN` 은 재현되지 않는다.

### 3-1. 수신 파일 무결성 — 3자 대조

| 출처 | SHA256 | bytes |
|---|---|---|
| main 정본 `bridge_agent.py` | `f38b984d…8e7db` | 167,906 |
| 라이브 서빙본 | **동일** | 167,906 |
| **Windows 가 실제로 받은 파일** | **동일** | 167,906 |

> ⚠ 검증 중 자기정정 1건: 하네스에 박아 둔 기대 해시가 `af7c3fe1…`(162,942 bytes)였고
> `sha=MISMATCH` 가 났다. 그 값은 **배포 전** 러너의 것이었고, 이번 롤아웃에 PR #1443·#1444 가
> 함께 실려 러너 본체가 정당하게 바뀐 결과였다. 위 3자 대조로 «수신 실패» 가 아니라
> «상수 stale» 임을 확정했다 — 불일치를 WARN 으로 강등하지 않고 원인을 갈랐다(§16.3 (b)).

### 3-2. 완화 범위가 여전히 폐기검사에 한정되는가 (배포본에서 재확인)

무관한 CA 를 pin 한 대조군이 배포본에서도 **실패**했다 — `--ssl-revoke-best-effort` 가 켜져
있어도 root 신뢰 축은 그대로다. pin 이 살아 있다는 것을 배포 후에도 실측으로 보였다.

## 4. 배포본 배선 확인 (주장 아닌 실측)

```
repo-web-a-1:/app/web/static/agent/bridge_setup.ps1
  'ssl-revoke-best-effort' 출현 = 3        (감지 후보 목록 · 실호출 · 안내문)
  'Invoke-WebRequest'      출현 = 2  →  278행 = §1 CA 평문 HTTP 수신(정당)
                                        412행 = «폴백으로 두지 않는다» 경고 주석
                                     즉 러너 수신 경로에는 0건 — pin 우회 경로 부재
```

## 5. 미검증 (정직 표기)

- **첫 실사용자의 전체 설치 왕복은 여전히 미관측** — 이 검증은 수신 구간을 배포본 바이트로
  구동한 것이고, `.ps1` 전체(파이썬 탐지 → 핸들러 등록 → 러너 상주 → 웹 상태 '내 AI 대기 중')를
  처음부터 끝까지 돌리지는 않았다. 이 머신의 기존 브리지 상태를 검증 목적으로 갈아엎지 않는다.
- **PB-0008 브라우저 시각검증 없음** — 이번 변경에 HTML/CSS/JS 변경 0건이고 렌더 표면이 없다
  (사유는 feature-0003 쪽 fragment 에 기록).
- **CI 미검증** — GitHub Actions 가 결제/지출 한도로 15:05 KST 부터 전 브랜치 job 미시작
  (`steps: 0`, 3초 종료, main 포함 26연속 실패). 사용자 결정으로 머지·배포 진행했고, 대체
  근거는 컨테이너 전수 pytest rc=0 ×3 + verify-completion PASS + 위 라이브 실측이다.
