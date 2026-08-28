---
run_at: 2026-08-28T19:30:00+09:00
session: ai/claude/feature-0043-ai-assisted-setup
scope: bridge_setup.{sh,ps1} · compose_probe_setup_instruction · 연결 화면 2곳
verdict: PASS
---

# Run — TASK-20260828T193000-ai-assisted-setup (P0-AD)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) + host (sh 슬라이스 실구동 · pwsh7 파서·동작 실측)
- **대상**: 환경 판단만 그 머신의 AI 에게, 실행은 스크립트가

## 이 기능이 생긴 계기 — 실측된 조합

| | claude CLI | python |
|---|---|---|
| Windows | ❌ 없음 | ✅ 3.14 |
| WSL | ✅ `/usr/local/bin/claude` | ✅ |

브라우저는 Windows, AI CLI 는 WSL. `bridge_setup.sh` 의 `uname` 분기도, `bridge_setup.ps1`
의 레지스트리 등록도 이 조합을 맞히지 못한다. 조합은 열려 있어 열거할 수 없다.

## 검증 방식 — 소스 검사가 아니라 실구동

설치 스크립트에서 검증 구역(`set -eu` → `RUNNER_ARGS=`)만 떼어 **실제 `sh` 에 먹인다**.
네트워크·설치·프로세스 기동은 그 구간 밖이라 일어나지 않고, 검증 로직은 순수하므로 계약이
그대로 확인된다. 결과는 `set --` 로 전개해 **토큰 경계**까지 본다(문자열 포함 여부가 아니라).

```
IN=[--workers 4 --refresh-caps]  -> argv=[--workers][4][--refresh-caps]
IN=[--cmd 'evil --pwn']          -> argv=[]  + stderr: ⚠ '--cmd' 은 허용 목록에 없습니다
IN=[--base http://evil.example]  -> argv=[]  + stderr: ⚠ '--base' 은 …
PY=[python3; rm -rf /]           -> ⚠ 실행 파일 이름·경로 형태가 아닙니다
AI=[rm]                          -> ⚠ 알려진 AI CLI 가 아닙니다(claude codex gemini ollama)
```

ps1 은 pwsh 7 로 파서 검사(PARSE OK)와 필터 함수 실구동을 각각 했다. Windows PowerShell 5.1
파서는 UTF-8 BOM 없는 파일을 ANSI 로 읽어 **원본에서도** 4개 에러를 냈다 — 내 변경 탓이
아님을 main 판과 대조해 확인했다.

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전량 (feature-0002·0003·0008·0014·0020·0023·0041·0043) | **PASS** (exit 0, FAILED 0) |
| ruff | All checks passed |
| feature-0043 스위트 | PASS (신규 93건 — 기본 61 + codex 조치 32) |
| 정본↔배포본 sha256 (`bridge_setup.sh` · `.ps1`) | 일치 |

## 뮤테이션 역검증 — 5종 전건 KILL

| 뮤턴트 | 재발 형태 | 죽은 건수 |
|---|---|---|
| M1 allowlist 무력화(모든 토큰 통과) | `--cmd` 로 임의 명령 실행 | 8 |
| M2 `drop()` 을 stdout 으로 | 차단은 되는데 경고가 사라짐 | 25 |
| M3 AI 실존 검사 제거 | 없는 CLI 지목 → 러너 즉사 | 1 |
| M4 probe 명령에서 빈칸 제거 | 「채워라」인데 채울 자리 없음 | 1 |
| M5 지시문 위임금지 블록 제거 | 대조를 AI 가 대신함 | 1 |

⚠ **이 역검증의 상한**: 뮤턴트는 전부 「내가 만든 조치를 되돌리는」 형태다. 그래서 「내가
애초에 잘못 생각한 축」은 후보에조차 오르지 않는다 — 아래 codex 결과가 그 증거다.

## 구현 중 자체 발견한 결함 2건 (실측으로만 드러남)

1. **`drop()` 이 stdout** — `$(probed_args_filtered)` 명령치환 안의 경고가 치환값에 먹혀
   **차단은 되는데 경고만 사라졌다.** 「조용히 버리지 않는다」를 주석에 적고 바로 아래에서
   그 반대를 구현한 형태. 소스를 읽으면 맞아 보인다.
2. **빈칸 없는 「빈칸을 채워라」** — 지시문은 완성됐는데 명령에 `BRIDGE_PROBED_*` 가 없었다.
   AI 가 변수를 지어 붙이면 오타 하나로 조용히 무시된다(셸은 모르는 변수를 그냥 환경에 실어
   보내고 스크립트는 읽지 않는다).

## codex 적대 리뷰 — 93건 green 상태에서 통과한 값들

| 값 | 결과 |
|---|---|
| `BRIDGE_PROBED_AI=rm` | 통과 → `--ai rm` (러너가 `rm` 을 AI CLI 로 실행) |
| `BRIDGE_PROBED_ARGS='--workers .'` | 통과 |
| `BRIDGE_PROBED_ARGS='--workers 1..2'` | 통과 |
| `BRIDGE_PROBED_ARGS='--workers 999999999'` | 통과 |

P1 3건 · P2 4건 전건 조치. 조치 후 같은 값들을 회귀 32건으로 고정했다
(`test_ai_assisted_setup_codex.py` — 출처를 잃지 않도록 파일을 분리했다).

## 미수행 (정직 표기)

- **라이브 실증** — 실제 AI 에게 조사 지시문을 주고 러너가 뜨는 것까지는 확인하지 못했다.
  러너 재기동에 새 `mat_` 토큰이 필요하고(웹에서 발급), 그 왕복은 사용자 화면에서 완결된다.
- **WSL↔Windows 핸들러 교차 등록** — 이 cycle 의 계기가 그 조합인데도 하지 않았다.
  레지스트리에 `wsl.exe` 경유를 등록하는 것은 쓸 수 있지만 **실 브라우저 클릭 실측**이
  불가능하다(사용자 머신 레지스트리 조작 + 클릭). 실측 못 하는 것을 넣으면 "배포했다 ≠
  도달했다" 가 된다. `_HANDLER=none` 으로 「등록해도 소용없음」을 고를 수 있게만 했다.
- **PB-0008 시각검증** — 연결 모달·단독 페이지에 `<details>` 블록이 추가됐다. 배포 후
  실 Windows 브라우저 확인이 필요하다(아래 feature-0003 fragment 참조).
- **provenance 강제** — 사람 칸(`BRIDGE_ARGS`)은 무검증이고 스크립트는 누가 채웠는지 모른다.
  지시문이 선을 긋지만 게이트가 아니다 — 구조적 한계이고, 숨기지 않고 적었다.
