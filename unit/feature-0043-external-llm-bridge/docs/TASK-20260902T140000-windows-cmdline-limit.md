---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260902T140000-windows-cmdline-limit
status: done
edit_policy: append-only
---

# TASK-20260902T140000 — 「연결은 됐는데 답도 로그도 없다」의 두 뿌리

## 1. 요청 (사용자, 2026-09-02)

> 「powershell 을 통한 연결이 수행되었지만, 실제 assistant 요청을 보내도 답변이 오지 않고
>  러너 로그에도 별도의 기록이 쌓이지 않는 이슈가 확인되어 수정이 필요합니다.」

제보의 두 절반이 **서로 다른 결함**이었다 — 「답변이 오지 않는다」와 「로그가 쌓이지 않는다」.

## 2. 실측 — 사용자 머신의 러너 원장이 둘을 갈라 준다

증적: `C:\Users\mckim\.mysql-ai-bridge\bridge.log` · `bridge.events.jsonl` (직접 확인) +
서버 DB(`WebAiTasks` #130 · `WebOAuthTokens` 계정 10).

```
12:27:53  run.start          build=4bdb0bace9b9 py=3.14.0 platform=win32
12:27:53  쓸 수 있는 모델·추론 수준을 물어보는 중… (claude — 최초 1회, 수십 초)
   ── 침묵 4분: 하트비트 0건 · 로그 0줄 · 질문 미수령 ──
12:28:12  (웹에서 질문 도착 → WebAiTasks #130 Status='open' 으로 대기)
12:31:53  run.ready          startup_ms=240896
12:31:54  claim_request      #130 점유 (질문이 온 지 3분 42초 뒤)
12:31:55  task.dispatch      prompt_chars=3494 sys_channel=True
12:31:55  ai.spawn_fail      exe=claude err=[WinError 206] 파일 이름이나 확장명이 너무 깁니다
12:31:55  task.answer.degraded  reason=ai_failed
```

사용자 말풍선에 실제로 저장된 답변(`WebAiTasks.Answer` #130):

> `AI 실행 실패: [WinError 206] 파일 이름이나 확장명이 너무 깁니다`

### 뿌리 ① — Windows 명령줄 32,767자 상한 (= 「답변이 오지 않는다」)

운영자 지침(5단계 시스템 프롬프트)은 `--append-system-prompt <지침>` 으로 **인자에** 실린다.
그 계정의 지침은 **34,962자**였다(실측: `compose_system_prompt(product=119, role=3,
account=10)`). Windows `CreateProcess` 의 명령줄 상한은 32,767자다.

**그 머신에서 직접 경계를 쟀다** (Python 3.14.0, 같은 `subprocess.Popen` 경로):

| 인자 길이 | 결과 |
|---|---|
| 32,600 | 성공 |
| 33,000 | `FileNotFoundError [WinError 206]` ← 러너 원장과 **동일 예외** |
| 40,000 · 60,000 | 동일 실패 |

즉 그 계정의 **모든** 질문이 spawn 단계에서 죽는다. POSIX 는 `ARG_MAX` 가 2MB 대라 같은
코드가 멀쩡히 돈다 — **Windows 전용 divergence** 이고, 그래서 POSIX 로만 검증한 이전 cycle
전부를 통과했다.

> 같은 창에서 이어진 `ai.fail exit=1 … "OAuth access token has expired. Re-authenticate to
> continue."` 는 **별개 사실**이다(자가 검증 호출). 그 머신의 `claude` 로그인 만료는 사용자
> 조치 영역이므로 이 cycle 이 고치지 않는다 — 다만 사유가 **보이게** 만든다(§3의 ③).

### 뿌리 ② — 기동이 능력 협상에 막혀 240초 침묵 (= 「로그가 쌓이지 않는다」)

능력 협상(`resolve_caps`)이 하트비트·대기 루프보다 **앞**에 있었고, 협상은 실패해도
데드라인(`_CAPS_PROBE_TIMEOUT_SEC` = 240초)을 **전부** 소진한다. 그 계정의 `claude` 는 로그인이
만료돼 매번 끝까지 갔다. 그 4분 동안 러너는:

- 하트비트를 보내지 않는다 → 웹은 「연결 안 됨」
- 로그를 쓰지 않는다 → **제보 그대로** "로그에 기록이 쌓이지 않는다"
- 질문을 가져가지 않는다 → 답변 없음

그런데 설치 스크립트(`bridge_setup.ps1`)는 `--check` 성공 뒤 **2초**만 보고 「완료. 웹 화면의
표시가 '내 AI 대기 중' 으로 바뀌면 질문을 보낼 수 있습니다」를 출력한 상태였다. 사용자가
「연결은 수행되었다」고 판단한 근거가 정확히 그 문장이다.

실패한 협상은 **캐시되지 않으므로**(`config.json` 에 `caps` 키 부재 — 실측) 재기동마다 4분이
반복된다. 사용자가 조급해 재실행할수록 준비 상태에 도달하지 못한다.

## 3. 조치

| # | 무엇 | 어디 |
|---|---|---|
| ① | 명령줄 예산을 재고, 넘치면 **질문을 stdin 으로** 넘긴다 | `invoke._fit_cmdline` · `runtimes` 의 `stdin_ok`/`stdin_arg` |
| ①-a | 지침이 인자에 안 들어가면 **본문으로 접는다**(판정은 조립 전에) | `invoke.system_channel_fits` → `handler` |
| ①-b | 줄일 수단이 없으면 예외를 맞으러 가지 않고 **정직하게 말한다** | `invoke._CMDLINE_OVERFLOW_MSG` |
| ② | 하트비트·대기를 **협상보다 먼저**, 협상은 배경으로 | `lifecycle.main` |
| ③ | 협상 실패 **사유**를 로그에 싣는다 | `caps._ask_json(reason_out=…)` |

### ① stdin 은 추측이 아니라 실측이다

두 런타임 모두 이 머신에서 **직접 돌려 확인**했다:

```
printf 'Reply with exactly: OK' | claude -p --strict-mcp-config          → OK   (rc=0)
printf 'Reply with exactly: OK' | codex exec --skip-git-repo-check -     → OK   (rc=0)
```

claude 는 `{prompt}` 자리를 **비우고**, codex 는 `-` 를 **남긴다**(빼면 대화형으로 뜬다).
그래서 자리표시자 처리를 런타임 명세(`stdin_arg`)가 정한다. `gemini` 는 확인하지 않았으므로
선언하지 않았다 — 그 런타임은 상한을 넘으면 ①-b 의 정직한 실패로 간다.

### ①-a 무엇을 잃고 무엇을 얻나 (명시)

지침을 본문으로 접으면 `TASK-20260901T140000` 이 시스템 채널로 옮겨 얻은 **인젝션 오판
방지를 잃는다**. 그럼에도 접는 이유: 접지 않으면 그 계정은 답을 **한 건도** 받지 못한다.
그리고 이 폴백은 **넘칠 때만** 발동한다 — POSIX 와 지침이 평범한 크기인 Windows 계정은
종전 그대로 시스템 채널을 쓴다(테스트가 양방향을 잠근다).

### ② 무엇이 협상을 정말로 기다리는가

**호출 형태(`argv`)뿐이다.** 표 안 런타임(claude·codex·gemini)은 `_RUNTIME_SPECS` 에 argv 가
이미 있어 협상 없이도 답할 수 있다 — 협상이 정하는 것은 «웹 선택기에 무엇을 띄울까» 이고
그것은 나중에 도착해도 된다. 표 **밖** CLI 만 argv 를 협상에서 배우므로 그때만 기다린다.

협상 결과는 하트비트가 들고 있는 **그 리스트 객체를 제자리 갱신**(`runtimes[:]`)해서 반영한다.
새 리스트를 대입하면 하트비트가 옛 객체를 계속 실어 선택기가 영영 빈다 — 미루기만 하고
반영하지 않으면 고치려던 것과 다른 결함을 새로 만드는 셈이다(테스트로 잠금).

## 4. 완료 조건

- [x] Windows 예산 밖 지침은 시스템 채널을 쓰지 않는다 (양방향: 평범한 크기는 그대로 쓴다)
- [x] 넘치는 본문이 stdin 으로 나가고, **자식이 실제로 받는다**(실 subprocess 왕복)
- [x] `overflow` 는 spawn 에 도달하지 않고 행동 가능한 문장을 낸다 (배선까지 잠금)
- [x] 협상이 **끝나기 전에** 하트비트·질문 대기가 이미 살아 있다
- [x] 뒤로 미룬 협상이 수행되고 신고 목록에 제자리 반영된다
- [x] 협상 실패 사유가 로그에 남는다
- [x] 정상 경로 무회귀 (짧은 프롬프트는 인자 그대로 · stdin 파이프 미개방)
- [x] 신규 회귀 16건 + **적대 뮤테이션 12종 전건 KILL**
- [x] feature-0043 컨테이너 1,283건 — 신규 실패 **0** (`main` 기준선과 FAILED 집합 동일)

## 5. 이월 — 이 cycle 이 만들지 않은 것

- **그 머신의 `claude` 로그인 갱신**: 사용자 조치 영역(`claude` 재로그인). 이 cycle 은 그
  사유가 **보이게** 만드는 데까지다(§3의 ③).
- **`gemini` stdin 지원**: 확인하지 않은 것을 선언하지 않았다. 확인하면 한 줄 추가로 끝난다.
- **지침 길이 자체의 상한**: 34,962자가 «정상» 인지는 별 판단이다. 관리 콘솔이 길이를 보여
  주지 않아 운영자가 자기 설정이 그 크기인지 알 수 없다 — 별 항목으로 남긴다.
- **PB-0008 시각검증**: 웹 자산(html/css/js/template) 변경 **0** — 이 cycle 의 변경은 사용자
  머신에서 도는 러너(파이썬)와 그 테스트뿐이다. 화면 검증 대상 표면이 없다.
