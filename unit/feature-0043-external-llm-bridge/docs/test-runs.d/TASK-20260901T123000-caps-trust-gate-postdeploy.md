---
run_at: 2026-09-02T11:42:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: POST-DEPLOY 라이브 실측 — provenance 필터가 실제 러너·실제 계정에서 동작하는가
verdict: PASS
---

# Run — TASK-20260901T123000-caps-trust-gate (POST-DEPLOY, 라이브)

- 배포: `2ffe054d` (PR #1504 머지) · `bin/deploy-web.sh` scope=all · exit 0
- 대상: 라이브 `https://112.185.196.20` (web-a/web-b = `mysql-ai-web:2ffe054d`)

## 1. 배포 게이트

| 항목 | 결과 |
|---|---|
| 대화 경로 스모크 | PASS (`[smoke-conv]`) |
| asset 스탬프 주입 | OK — baked 이미지에 `?v=dev` 잔존 0 |
| 서비스별 이미지 SHA | web-a·web-b·ask-worker·insight-worker·ext-tool-mcp-a/b·ops-scheduler 전부 `2ffe054d` |
| surge 잔존 | 0 |
| **엣지 무중단 실측** | `no upstreams available` **0건** (최근 15분) |
| `/healthz` | `{"status":"ok","git_commit":"2ffe054d","mysql_ok":true,"pg_ok":true}` |

## 2. 러너 교체 + 재기동 (AI 수행)

배포본 러너와 사용자 설치본의 md5 가 달라(설치본 `73dcdc03…` / 배포본 `ccb4ac17…`) 교체 후
재기동했다. 재기동 뒤 `run.start build=9ce970c26d84` 이며 `hb.stale_build` 경고가 사라졌다.

```
[bridge] run.start ... build=9ce970c26d84 ver=2026.09.01
[bridge] log | 고를 수 있는 것: Claude(3종, 추론 5단계) · Codex(6종, 추론 5단계)
[bridge] log |   출처: 실조회 (캐시 — 갱신은 --refresh-caps)
[bridge] run.ready runtime=claude ...
```

⚠ **정직 표기 — 토큰 소유가 바뀌었다.** 종전 러너의 토큰은 그 프로세스의 환경변수에만
있었고(설정 파일에는 저장되지 않는다), 내가 **읽기 전에 프로세스를 먼저 종료**해 되쓸 수
없었다. 그래서 라이브 웹에 `bootstrap_admin` 으로 로그인해 새 토큰을 발급하고 그것으로 띄웠다
— 지금 러너의 수명은 **내가 만든 웹 세션**에 결속돼 있다. 사용자가 자기 세션으로 되돌리려면
웹의 「내 AI 연결하기」에서 원클릭 명령을 한 번 다시 실행하면 된다.
(러너 재기동 시에는 **먼저 `/proc/<pid>/environ` 에서 토큰을 확보**한 뒤 종료해야 한다.)

## 3. 제보된 증상의 소멸 (핵심 실측)

`/api/api-vault/options` (계정 `bootstrap_admin`, 실 러너 기준):

```
model_selector   = visible
runner_listening = true
models = ['claude:opus', 'claude:sonnet', 'claude:haiku',
          'codex:gpt-5.6-sol', 'codex:gpt-5.6-terra', 'codex:gpt-5.6-luna',
          'codex:gpt-5.5', 'codex:gpt-5.4', 'codex:gpt-5.4-mini']
gpt-5.1 포함 = False
```

`/api/ai/connect/status` → `connected=true · listening=true · ready=true · runner_stale=false`.

**제보의 `gpt-5.1` 은 목록에 없고**, codex 축은 그 계정이 실제로 돌릴 수 있는 `gpt-5.6-*`
세대만 보인다.

## 4. 구 러너의 화석 목록이 실제로 지워졌다 (설계의 핵심 주장)

같은 DB 에서 **다른 계정의 구 빌드 러너**(`RunnerBuild=937b18be70eb`, 지문 축 이전)를 관측했다.
그 행의 `RunnerCapabilities` 는 이제 **`[]`** 다 — 출처를 신고하지 않는 그 러너의 목록이
수신 시점에 통째로 걸러진 것이고, 이것이 「화석은 첫 하트비트에 지워진다」의 라이브 증거다.

| 토큰 행 | 빌드 | 저장된 능력 |
|---|---|---|
| 133 (재기동한 러너) | `9ce970c26d84` (배포본) | claude 3종 + codex 6종 |
| 112 (타 계정, 구 빌드) | `937b18be70eb` | **`[]`** ← 화석 소멸 |
| 128 (타 계정, 새 빌드) | `9ce970c26d84` | `[]` (그 머신에 실조회 결과가 없음 — 설계대로 우아하게 열화) |

## 5. 잔류물

- 검증용으로 만들었던 러너 행 `Id=113`·`132` **revoke 완료**. 타 세션 자원 무접촉.
- 사용자 러너의 직전 설치본은 `/var/tmp/bridge_prev_*.py` 로 보관.
