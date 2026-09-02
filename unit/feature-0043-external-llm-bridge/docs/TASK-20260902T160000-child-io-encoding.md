---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260902T160000-child-io-encoding
status: done
edit_policy: append-only
---

# TASK-20260902T160000 — 직전 수정이 연 새 실패면: 자식 입출력 인코딩

## 1. 요청 (사용자, 2026-09-02)

> 「powershell 터미널 내 실행을 통해 다시 연결했습니다. 이후 연결이 진행된 부분을 확인하여
>  assistant 요청을 보냈지만, 여전히 답변이 수신되지 않습니다.」

## 2. 직전 cycle 이 고친 것과 남긴 것

`TASK-20260902T140000` 의 두 수정은 **라이브에서 동작했다**(사용자 머신 원장):

```
14:12:44  run.ready  startup_ms=811                      ← 240초 침묵 → 0.8초 (뿌리 ② 해소)
14:33:34  task.system_channel.folded  system_chars=35602 ← 지침 접기 동작
14:33:34  ai.cmdline.stdin  budget=30719 cmd_chars=39252 ← stdin 전환 동작
14:33:34  ai.fail  dur_ms=46  stdout_bytes=0  stderr_tail=     ← 그런데 여기서 죽는다
```

`[WinError 206]` 은 사라졌다. 대신 **새 실패면**이 열렸다.

## 3. 진단 — `exit` 필드의 **부재**가 결정적 단서였다

`ai.fail` 원장에 `exit` 이 **없다**. `_render_fields` 는 `None` 을 생략하므로 이는
`proc.returncode is None` 을 뜻한다 — **자식이 실패한 것이 아니다.** 파이프 스레드가 예외로
죽었고, 그 예외를 아무도 잡지 않았다.

사용자 머신 실측:

| 측정 | 값 |
|---|---|
| `locale.getencoding()` | **cp949** |
| `"⟦".encode("cp949")` | `UnicodeEncodeError: illegal multibyte sequence` |
| `Popen(..., text=True)` + stdin 쓰기 | **`UnicodeEncodeError`** |
| `Popen(..., text=True, encoding="utf-8")` + stdin 쓰기 | **OK** (자식 수신 확인) |

`subprocess(text=True)` 는 **로케일 인코딩**을 쓴다. 우리 프롬프트에는 `compose_prompt` 가
모든 질문에 넣는 `⟦USER-REQUEST⟧`(U+27E6/U+27E7)가 있고, cp949 는 그것을 인코딩할 수 없다.

**왜 지금 처음 드러났나**: 종전에는 프롬프트가 **argv** 로 갔고 그 경로는 `CreateProcessW`
(UTF-16)라 로케일이 개입하지 않는다. 직전 cycle 이 명령줄 상한을 피해 프롬프트를 **stdin 으로**
옮긴 순간 그 인코딩 경로가 **처음 열렸다**. 즉 이것은 **직전 수정이 만든 실패면**이다.

읽기 쪽도 같은 지뢰였다: `claude`·`codex` 는 UTF-8 로 출력하는데 cp949 `strict` 로 디코드하면
한글 섞인 답변에서 터지거나 깨진다(아직 관측 전이었으나 같은 뿌리).

## 4. 조치

| # | 무엇 | 어디 |
|---|---|---|
| ① | 자식 입출력 규약을 **UTF-8 로 명시** (양방향, `errors="replace"`) | `base.CHILD_TEXT_IO` — 자식 호출 **5곳 전부** 이것을 쓴다 |
| ② | 파이프 스레드 예외를 **잃지 않는다** | `invoke._run_cli_cancelable` 의 `pump_exc` + `ai.io_fail` |
| ③ | `returncode is None` 을 **성공으로도, 자식 실패로도** 읽지 않는다 | 같은 함수의 전용 분기 |

②가 없으면 다음 인코딩·파이프 사고도 똑같이 「출력 0인 자식 실패」로 위장된다 — 이번 조사에서
`exit` 필드의 부재만이 유일한 단서였다는 사실이 그 축의 가치를 그대로 보여 준다.

`errors="replace"` 를 고른 이유: 예상 못 한 바이트 **하나**가 사용자의 답변 **전체**를 예외로
날리는 것보다, 그 문자만 대체 기호로 남기고 나머지를 전하는 편이 낫다.

## 5. 완료 조건

- [x] 자식 입출력이 로케일과 무관하게 UTF-8 (양방향) · 자식 호출 5곳 전부 적용
- [x] cp949 인코딩 불가 문자가 자식에 **온전히** 도달 (실 Windows 40,000자 왕복 PASS)
- [x] 자식의 UTF-8 한글 답변 무손상 왕복 · 깨진 바이트가 답변 전체를 날리지 않음
- [x] 파이프 예외가 사유와 함께 보고됨 (자식 종료 실패로 위장 안 함)
- [x] `returncode is None` 이 성공으로 읽히지 않음
- [x] 신규 회귀 8건 + 적대 뮤테이션 **6종 전건 KILL**
- [x] **실 Windows(cp949) 대조 검증** — 수정본 PASS / 수정 전 `UnicodeEncodeError`
- [x] 컨테이너 feature-0043 신규 실패 0 (`main` FAILED 집합과 동일)

## 6. 이월

- **그 머신 `claude` 인증**: 이번 cycle 로 요청이 `claude.exe` 에 **도달**하지만, 그 CLI 는
  로그인 만료 상태다(12:35 `401 OAuth access token has expired` · 14:16 능력 협상
  `TimeoutExpired`). 도달 후의 실패는 이제 `_FAILURE_HINTS` 가 「연결된 AI 에 로그인돼 있지
  않습니다」로 안내한다 — 사용자 조작 영역.
- 관리 콘솔의 시스템 프롬프트 **길이 미표시**(35,602자) — 별 항목 유지.
