---
run_at: 2026-09-02T13:20:00+09:00
session: ai/claude-corp/feature-0043-winargv-cmdline-limit
scope: Windows 명령줄 32,767자 상한 · 기동 240초 침묵 (사용자 제보 진단 + 수정 검증)
verdict: PASS
---

# Run — TASK-20260902T140000

## Environment

- 진단 대상: 사용자 Windows 머신 (`C:\Users\mckim\.mysql-ai-bridge`, Python **3.14.0**, win32)
- 서버: 라이브 스택 (`repo-web-a-1` / `repo-mysql-1`, 배포 `293a20c8` 시점)
- 단위/회귀: 컨테이너 `repo-unittest-agent:latest` (py3.11) + 호스트 py3.12
- **Environment: Windows-browser — 미수행(사유)**: 이 cycle 의 변경은 사용자 머신에서 도는
  러너(파이썬 5개 모듈)와 그 테스트뿐이다. `static/**`·`templates/**`·html/css/js 변경 **0건**
  이라 브라우저 렌더 표면이 없다(`git status` 로 확인). 러너 배포본(`bridge_agent.py`)은
  `.gitignore` 대상 빌드 산출물이다.

## 1. 진단 — 라이브 증적 3출처 교차

### 1-a 러너 감사 원장 (사용자 머신, 직접 확인)

```
seq  1  12:27:53.049  INFO   run.start      build=4bdb0bace9b9 py=3.14.0 platform=win32
seq  4  12:27:53.800  INFO   log            쓸 수 있는 모델·추론 수준을 물어보는 중…
        ── 침묵 4분: 하트비트 0 · 로그 0 · wait_for_request 0 ──
seq  7  12:31:53.893  INFO   run.ready      startup_ms=240896
seq 11  12:31:54.770  DEBUG  api.ok         claim_request  dur_ms=651
seq 12  12:31:55.294  INFO   task.dispatch  prompt_chars=3494 sys_channel=True
seq 14  12:31:55.308  ERROR  ai.spawn_fail  exe=claude err_type=FileNotFoundError
                                            err=[WinError 206] 파일 이름이나 확장명이 너무 깁니다
seq 15  12:31:55.321  WARN   task.answer.degraded  reason=ai_failed dur_ms=27
```

traceback 은 `_run_cli_cancelable` → `subprocess.Popen` → `_winapi.CreateProcess` 를 지목.

### 1-b 서버 DB — 사용자가 실제로 받은 답변

`WebAiTasks` #130 (`Origin=web`, `AccountId=10`, 12:28:12 생성 · 12:31:54 점유):

```
Answer: ⟦UNTRUSTED-DATA⟧ … AI 실행 실패: [WinError 206] 파일 이름이나 확장명이 너무 깁니다
        (이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)
```

`WebOAuthTokens` — 그 계정의 러너는 배포본과 **동일 지문**(`RunnerBuild=4bdb0bace9b9`
= 배포 `/app/web/static/agent/bridge_agent.py` sha256 앞 12자) → 「구버전 러너」 가설 배제.

### 1-c 지침 길이와 상한 — 둘 다 실측

| 측정 | 방법 | 값 |
|---|---|---|
| 그 계정의 시스템 프롬프트 | 서버에서 `compose_system_prompt(product=119, role=3, account=10)` | **34,962자** |
| Windows 명령줄 상한 | **그 머신에서** `Popen` 인자 길이를 키우며 이진 확인 | 32,600 성공 / **33,000 `[WinError 206]`** / 40,000·60,000 동일 실패 |

예외 형(`FileNotFoundError`)·winerror(206)·메시지가 러너 원장과 **완전히 일치** → 인과 확정.

## 2. stdin 탈출구 — 라이브 실측 (추측 아님)

```
$ printf 'Reply with exactly: OK' | claude -p --strict-mcp-config
OK                                                                      rc=0
$ printf 'Reply with exactly: OK' | codex exec --skip-git-repo-check -
OK                                                                      rc=0
```

claude 는 `{prompt}` 자리를 **비우고**, codex 는 `-` 를 **남긴다**(빼면 대화형). 이 차이를
런타임 명세(`stdin_arg`)가 담는다. `gemini` 는 확인하지 않았으므로 선언하지 않았다.

## 3. 수정 검증

### 3-a 신규 회귀 16건 — 전건 PASS

| 파일 | 건수 | 무엇 |
|---|---|---|
| `test_cmdline_length_limit.py` | 14 | 예산(Windows 분기 직접 측정 포함) · stdin 전환 · overflow 정직 실패 · **배선**(spawn 도달 여부) · 실 subprocess stdin 왕복 · 정상 경로 무회귀 |
| `test_startup_not_blocked_by_caps.py` | 2 | 협상 **중에도** 하트비트·질문 대기가 살아 있는가 · 배경 협상 결과가 신고 목록에 제자리 반영되는가 |

### 3-b 적대 뮤테이션 12종 — 전건 KILL

1차에서 **2종이 살아남았고 그 둘이 실제 커버리지 구멍**이었다:

| 뮤테이션 | 1차 | 최종 |
|---|---|---|
| M1 Windows 예산을 `10**9` 로 | SURVIVED → 예산 함수 직접 측정 테스트 추가 | KILLED |
| M1b 여유 마진 제거(`_WIN_CMDLINE_MAX + 1`) | — | KILLED |
| M5 `overflow` 를 그대로 spawn | SURVIVED → 행위(spawn 여부) 단정 추가 | KILLED |
| M2 claude `stdin_ok` 제거 | KILLED | KILLED |
| M3 `system_channel_fits` 항진명제화 | KILLED | KILLED |
| M4 `stdin=PIPE` 미개방 | KILLED | KILLED |
| M6 codex `stdin_arg` 를 `""` 로 | KILLED | KILLED |
| M7 `communicate(input=…)` 제거 | KILLED | KILLED |
| M8 stdin 판정을 실행에 미전달 | — | KILLED |
| M9 `_fit_cmdline` 우회 | — | KILLED |
| N1 협상을 다시 앞으로(종전 동작) | KILLED | KILLED |
| N2 배경 협상 제거 | KILLED | KILLED |
| N3 제자리 갱신 대신 재대입 | KILLED | KILLED |

### 3-c 무회귀 — 기준선 대조

컨테이너(`repo-unittest-agent`) feature-0043 **1,283건 수집**:

| | FAILED 집합 |
|---|---|
| `main` (기준선) | `test_roster_never_calls_a_token_that_never_ran_a_runner_stale` (1건) |
| 본 브랜치 | 동일 (1건) |
| `comm -13` diff | **공집합 — 신규 실패 0** |

그 1건은 `app.get_conn` AttributeError 로 **양쪽 동일**하게 실패하는 환경성 항목이다.
호스트 전량 실행의 나머지 실패 10건도 기준선과 동일(0041·0043 동시 실행 `sys.modules` 오염 —
REPORT §9 에 이미 기록). ruff 신규 지적 0(기존 `F821` 1건은 `main` 에도 동일).

### 3-d 테스트 더블·구조 단정 정리

- `_run_cli_cancelable`/`_ask_json` 더블 4곳의 시그니처를 새 인자에 맞췄다 — **production
  시그니처를 약화시키지 않았다**(더블 arity 미검증으로 seed 가 조용히 무력화된 선례가 있다).
- `test_runner_does_not_offer_a_selector_it_cannot_honor` 는 `main()` 소스를 문자열로 자르는
  단정이라 분기 모양 변경에 `ValueError` 로 깨졌다. 삭제·skip 하지 않고 **행위 단정으로
  재작성**(하트비트가 빈 목록을 받는가 · 능력 질의가 일어나지 않는가).

## 4. 닫지 못한 것 (정직 표기)

- **사용자 머신 실 왕복 미관측**: 수정은 이 저장소의 러너 소스이고, 그 머신에는 **사용자가
  새 사본을 받아 재기동**해야 도달한다. 그 머신의 브리지 상태를 검증 목적으로 갈아엎지 않았다.
- **그 머신 `claude` 401**: 같은 창에서 `ai.fail … "OAuth access token has expired.
  Re-authenticate to continue."` 를 관측했다. 사용자 자격증명 영역이라 이 cycle 은 사유가
  **보이게** 만드는 데까지다 — 재로그인 전에는 답변 품질이 회복되지 않는다.
- **독립 관점 적대 검증(codex)**: 하네스 제약으로 미수행. 대신 뮤테이션 12종으로 대체
  (`REVIEW.md` `REV-20260902T140000-…` 렌즈 3).
