---
run_at: 2026-08-28T17:15:00+09:00
session: ai/claude/feature-0043-tool-permission-friction
scope: bridge-runner · compose_prompt · _RUNTIME_SPECS
verdict: PASS
---

# Run — TASK-20260828T171500-tool-permission-friction

- **일시**: 2026-08-28
- **Environment**: container (`make test`) + host (`claude -p` 직접 구동 실측)
- **대상**: 「도구 사용 승인을 사용자에게 요구하는」 답변 제거

## 원인 실증 — 권한 게이트가 아니었다

제보된 증상은 「권한을 승인해 달라」였지만, 실제로 무엇이 막혔는지는 직접 물어봐야 알 수 있다.
러너와 같은 머신·같은 CLI(`claude -p`, cwd `/root`)로 두 번 구동했다.

```
$ claude -p "Bash 도구로 'echo BRIDGE_PERM_PROBE_OK' 를 실행하고 그 출력만 답하라."
BRIDGE_PERM_PROBE_OK                                  ← 도구 승인 프롬프트 없음

$ claude -p "mcp__mysql-ai__list_open_requests 도구를 limit=1 로 호출하고,
             성공/실패 여부와 오류메시지를 그대로 한 줄로 답하라."
실패 — {"error": "HTTP 401",
        "detail": "{\"error\":\"유효하지 않거나 만료된 토큰입니다.\"}"}
```

**두 번째가 결정적이다.** 도구는 승인 없이 호출됐고, 실패는 인증(401)이었다. 즉 라이브의
「권한 승인 요청」은 권한 거부의 표면화가 아니라 **401 을 모델이 오역한 결과**다. 사용자가
"승인할 이유가 없다" 고 한 것이 문자 그대로 맞았다 — 승인할 대상이 존재하지 않았다.

경합의 실체:

| 경로 | 토큰 | 상태 |
|---|---|---|
| 러너 프롬프트 (`compose_prompt`) | 이 task 에 결속, 웹 세션 결합 | 유효 (러너 하트비트 정상) |
| 상주 MCP 서버 (`~/.claude.json`) | 별개 `mat_` (54자) | **만료 → 401** |

모델은 프롬프트의 HTTP 안내보다 **붙어 있는 도구**를 먼저 집었다.

## 조치 실증 — MCP 표면이 실제로 사라지는가

```
$ claude -p --strict-mcp-config "너에게 이름이 mcp__mysql-ai__ 로 시작하는 도구가
                                 하나라도 있는가? 있으면 'YES <개수>', 없으면 'NO' 만 답하라."
NO
```

대조군은 위 401 호출 자체다(플래그 없이는 그 도구를 실제로 집었다). `--mcp-config` 를 함께
주지 않았으므로 배제이지 교체가 아니다.

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전량 (feature-0002·0003·0008·0014·0020·0023·0041·0043) | **PASS** (exit 0, FAILED 0) |
| ruff | All checks passed |
| feature-0043 스위트 | 651건 PASS (신규 40건) |
| 배포 사본 sha256 대조 | 정본과 일치 |

### 도중 1회 관측된 flake (내 변경과 무관 — 근거 함께)

2회차 전량 실행에서 `feature-0014 test_edge_rolling_gate.py::
test_g3b_observed_isolation_that_never_clears_reports_failure` 가 1건 실패했다
(`elapsed >= 3` 인데 `1.007s` 반환 — 벽시계 임계 단언).

무관하다고 보는 근거 두 가지. **둘 다 없으면 무관하다고 쓰지 않는다.**

1. **인과 배제** — 이번 cycle 의 staged 파일 13개에 `bin/` 이 **하나도 없다**. 그 테스트는
   `bin/` 의 배포 스크립트를 subprocess 로 돌려 경과 시간을 잰다.
2. **재현 실패** — 해당 파일 단독 재실행 39건 전건 PASS, 전량 재실행도 `exit 0` / FAILED 0.

부하 상황에서 벽시계 임계가 흔들린 것으로 본다. 이 flake 자체는 이 cycle 의 범위가 아니라
그대로 남긴다 — 숨기지 않고 적는 것이 여기서 할 수 있는 일이다.

## 뮤테이션 역검증 — 8종 전건 KILL

각 뮤턴트는 치환 앵커를 `assert` 로 확인해 **적용 여부를 증명**한 뒤 실행했고, 매번 원본
sha256 복원을 확인했다.

⚠ **이 절차의 상한을 먼저 적는다**: 뮤턴트를 내가 골랐고, 내 뮤턴트는 전부 「내가 만든 조치를
되돌리는」 형태였다. 그래서 내가 **만들지 않은 경로**(caps 학습 플래그·`--cmd`)는 후보에조차
오르지 않았고, codex 가 정확히 거기서 들어왔다(REV-20260828T171500 P1-1·P1-2). 아래는
커버리지의 증거가 아니라 **내가 생각한 범위 안에서의** 증거다. M6~M8 은 codex 지적 이후
추가한 것이다.

| 뮤턴트 | 재발 형태 | 죽은 테스트 |
|---|---|---|
| M1 `--strict-mcp-config` 제거 | 조치 되돌림 | `..._invoked_with_strict_mcp_config` · `..._survives_model_and_effort` |
| M2 플래그를 프롬프트 **뒤**로 | 질문의 일부로 먹힘(모델 선택 사용자만 재발) | `..._survives_model_and_effort` |
| M3 승인금지 문구 제거 | codex 등 플래그 없는 런타임에서 재발 | `..._forbids_asking_the_user` · `..._regardless_of_attachments` · `..._runtime_agnostic[3]` |
| M4 자격증명 단일화 문구 제거 | 교차 계정 응답 | `..._declares_its_token_the_only_credential` · `..._regardless_of_attachments` |
| M5 실패 시 대체행동 제거 | 침묵 또는 조사 날조 | `..._tells_the_ai_what_to_do_when_a_tool_fails` |
| M6 denylist 무력화(빈 튜플) | 학습 플래그로 MCP·권한 축 재개방 | 11건 |
| M7 감지 배선 제거 | 승인 요구 답변이 그대로 화면에 | 1건 |
| M8 `--cmd` 경고 무력화 | 그 사용자만 원인 모를 재발 | 2건 |

## 미수행 (정직 표기)

- **라이브 실증** — 배포 후 **러너 재기동**이 선행되어야 하고(러너는 기동 시점의 스크립트를
  실행한다), 재기동 뒤 실제 첨부 질문을 웹에서 보내야 확인된다. 그 왕복은 사용자 화면에서만
  완결된다. `TASK.md` 에 미완 항목으로 남겼다.
- **PB-0008 시각검증** — 이번 변경에 렌더되는 웹 자산이 없다. 건드린
  `static/agent/bridge_agent.py` 는 브라우저가 그리는 자산이 아니라 **사용자가 내려받는 러너
  스크립트**다(경로만 `static/` 이다). 화면 요소·상호작용 변경 0.
- **codex 런타임의 실행 측 배제** — 대응 플래그가 없다(실측 `codex exec --help`). 그
  런타임에서는 프롬프트 계약 + 제출 경로 감지가 방어선이며, 그 사실을 코드 주석에 남겼다.
- **`--cmd` 경로** — 사용자가 명령을 통째로 준 것이라 고치지 않는다. 1회 경고만 한다.
- **감지의 한계** — `annotate_approval_request` 는 알려진 표현 7종만 잡는다. 모델이 다른
  말로 승인을 요구하면 통과한다. 답을 지우지 않는 설계라 오탐 비용은 한 줄이지만, **미탐은
  라이브 증상 그대로**다.
