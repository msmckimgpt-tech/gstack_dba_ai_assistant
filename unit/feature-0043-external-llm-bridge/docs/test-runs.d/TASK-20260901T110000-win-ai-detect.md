---
run_at: 2026-09-01T11:30:00+09:00
session: ai/claude/feature-0043-win-ai-detect
scope: 설치된 AI 를 못 찾던 결함 3겹(확장자·PATH 밖·축 뒤엉킴) + 옵션 요구 안내 제거
verdict: PASS
---

# Run — TASK-20260901T110000-win-ai-detect

Environment: **Windows-native** (실 Windows PowerShell 5.1 + `Python 3.14` +
`C:\Users\<사용자>\.local\bin\claude.exe` = Claude Code `2.1.70`) · WSL 컨테이너 pytest

> UI 표면 변경 없음 — PB-0008 브라우저 시각검증 대상 아님(러너·설치 스크립트). 대신 이 결함이
> 사는 곳인 **실 Windows** 에서 직접 실측했다. 리눅스 컨테이너에서는 이 클래스(`PATHEXT`,
> `%USERPROFILE%\.local\bin`)를 원리적으로 볼 수 없다.

## 1. 근본 원인 실측 — 사용자 머신 그대로

사용자 제보 로그:

```
[bridge-setup] CA 지문 일치. / 러너 체크섬 일치. / 핸들러를 등록했습니다.
[bridge-setup] 연결을 확인하는 중…
[bridge 2026-09-01 10:43:55] FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.
[bridge-setup] 중단: 연결 확인에 실패했습니다. 토큰이 만료됐다면 …
```

| 확인 항목 | 명령 | 결과 |
|---|---|---|
| AI 가 정말 없는가 | `C:\Users\<사용자>\.local\bin\claude.exe --version` | **`2.1.70 (Claude Code)`** — 설치돼 있고 실행된다 |
| PATH 에서 보이는가 | `Get-Command claude` | **찾지 못함** |
| 사용자 PATH 구성 | `[Environment]::GetEnvironmentVariable('Path','User')` | Python314 · WindowsApps · Azure Data Studio · VS Code · .dotnet\tools — **`.local\bin` 부재** |
| 러너의 감지 구현 | `bridge_agent._which` (수정 전) | `os.path.join(d, name)` — **확장자를 붙이지 않는다** |

**결함이 세 겹이었다.** (a) 확장자 미고려로 윈도우에서는 구조적으로 못 찾고, (b) 설치기가
쓰는 폴더가 PATH 에 없어 PATH 만 보는 어떤 구현도 못 찾으며, (c) AI 감지가 연결 확인
**앞**이라 그 실패가 「연결 확인 실패」로 보고됐다 — 토큰·CA·네트워크가 전부 멀쩡한데.

## 2. 수정 후 실측 — 같은 머신, 실 Windows 파이썬

> ⚠ 이 절은 **codex 적대 리뷰 조치 전** 값이다. 리뷰가 `.cmd`·`.bat` 를 실행 대상에서
> 빼게 했으므로 `exec_exts` 는 지금 `['.com', '.exe']` 다 — 9절이 조치 후 재실측이다.
> 두 값을 나란히 남긴다: 무엇이 왜 좁아졌는지가 그 두 표의 차이로 보인다.

수정된 정본을 그대로 로드해 감지 함수를 구동 (`python.exe` = `Python314`):

```json
{
  "os_name": "nt",
  "exec_exts": [".com", ".exe", ".bat", ".cmd"],
  "install_dirs": ["C:\\Users\\<사용자>\\.local\\bin",
                   "C:\\Users\\<사용자>\\AppData\\Roaming\\npm",
                   "C:\\Users\\<사용자>\\AppData\\Local\\Programs\\Ollama"],
  "which_claude_PATH_only": null,
  "which_ai_claude": "C:\\Users\\<사용자>\\.local\\bin\\claude.exe",
  "detect_ai": "claude",
  "resolved_argv": ["C:\\Users\\<사용자>\\.local\\bin\\claude.exe"]
}
```

`which_claude_PATH_only = null` 이 이 표의 핵심이다 — **PATH 에는 여전히 없다.** 그런데
`_which_ai` 가 찾아냈고, `_resolve_exe` 가 그 경로를 argv[0] 으로 만들었다.

**찾은 것을 실제로 부를 수 있는가** (감지와 호출이 갈리지 않는가):

| 확인 | 결과 |
|---|---|
| `_cli_help_text("claude")` — 실 프로세스 기동 | **7,436자 수신** (PATH 밖 실행 파일이 정말 실행됐다) |
| `--strict-mcp-config` 지원 | 도움말에 존재 → `_ensure_strict_mcp_supported` = True |

**PowerShell 쪽 대칭** (설치 스크립트의 실존 검사):

| 확인 | 결과 |
|---|---|
| `Get-Command claude` (수정 전 로직) | **False** |
| `Test-AiPresent claude` (수정 후 로직) | **True** |
| `Test-AiPresent codex` (실제로 없는 것) | **False** — 넓히기만 하고 무르지 않았다 |

## 3. 스크립트 파싱 (BOM 회귀 방지)

```
[Parser]::ParseFile(bridge_setup.ps1)  → ParseErrors = 0   (Windows PowerShell 5.1)
BOM 첫 3바이트 = efbbbf                                     (정본·배포본 양쪽)
sh -n / bash -n (bridge_setup.sh)      → OK
```

## 4. 회귀 테스트 — 신규 26건

`tests/test_win_ai_detection.py` — **26 passed**. 소스 문자열 검사가 아니라 가짜 실행 파일을
두고 감지를 시키고, `main()` 을 `--check` 로 구동해 연결 호출이 정말 일어났는지 본다.

## 5. 역검증 (§16.7 G11-b) — 뮤테이션 3종

수정을 되돌리면 그 축의 테스트가 **정확히** 죽는가:

| 뮤턴트 | 되돌린 것 | 죽은 테스트 | 판정 |
|---|---|---|---|
| M1 | `_exec_exts` → `[""]` (확장자 미고려 = 종전 `_which`) | `test_which_finds_exe_by_extension_on_windows` · `test_windows_ignores_extensionless_shim` | PASS |
| M2 | `_which_ai` 의 표준 위치 탐색 제거 | `test_finds_ai_installed_outside_path` · `test_found_path_becomes_the_command` · `test_cli_runner_executes_the_resolved_path` | PASS |
| M3 | AI 감지 실패를 연결 확인 **앞**에서 종료 (원 결함 재현) | `test_check_verifies_the_connection_even_without_any_ai` · `test_connection_failure_keeps_its_own_code` · `test_invalid_token_still_wins` | PASS |

M3 가 가장 중요하다 — 원 제보의 오진(「연결 확인에 실패했습니다」)을 그대로 재현했고, 그
상태에서 「연결 호출이 일어났는가」를 보는 단언이 죽었다. 스위트를 되돌리면 다시 전건 green.

## 6. 기존 테스트 4건 교정 (계약 유지, 읽는 방법만)

| 테스트 | 무엇이 걸렸나 | 교정 |
|---|---|---|
| `test_probed_ai_must_exist_on_path` → `..._on_this_machine` | 부재 문구 변경 + **부재의 정의가 넓어짐**(PATH → PATH + 표준 위치) | 「부재」를 만들 때 양쪽 모두에서 없는 이름을 고르도록 + 문구 완화 |
| `test_handle_one_validates_the_runtime_before_switching` | `_which(want_runtime)` 문자열 | `_which_ai(...)` — 「실재를 확인하는가」 계약은 그대로 |
| `test_user_named_cli_is_not_silently_replaced` | `_which(args.ai)` 문자열 | 동일 |
| `test_runner_only_accepts_models_it_itself_offered` | 동일 | 동일 |

넷 다 **계약이 아니라 이름**이 바뀐 자리다. 확인 범위가 넓어졌을 뿐 「검증 없이 실행하지
않는다」는 그대로이며, 넓어진 범위 자체는 위 3절의 allowlist 테스트가 잠근다.

## 7. 전체 스위트

| 항목 | 결과 |
|---|---|
| 컨테이너 전수 (`make test`, py3.11) | **rc=0** |
| ruff | All checks passed |
| 배포본 동일성 (`test_bridge_agent_sync.py`) | 14 passed — 정본 ≡ `static/agent/` (러너·ps1·sh 3종) |

### 무관 flake 1건 (기록)

`feature-0014 …::test_g3b_observed_isolation_that_never_clears_reports_failure` 가 1회
실패했다. **내 변경과 무관**하다 — 같은 커밋의 worktree 에서 3/3 통과, `main` checkout 에서
3회 중 1회 실패. 벽시계 경과(`elapsed >= 3`)에 의존하는 timing flake 다. 이번 cycle 범위 밖.

## 8. 미검증 (정직 표기)

- **첫 사용자의 실제 설치 왕복은 미관측.** 위 실측은 감지·실행 함수를 실 Windows 에서 직접
  구동한 것이고, 유효 토큰으로 `.ps1` 전체를 처음부터 끝까지 돌리지는 않았다(토큰은 웹에서
  사용자가 발급한다). 배포 후 사용자가 [연결 명령 복사] 를 다시 눌러 실행하면 그 왕복이 닫힌다.
- **AI 가 정말 하나도 없는 머신의 안내 화면 실물은 미관측** — exit 4 경로와 문구는 단위
  테스트로 잠갔으나, 그 상태의 실 머신은 손에 없다.
- **적대 검증은 codex 로 수행했다**(9절 · REVIEW REV-20260901T114500) — P1 1건 · P2 4건 적발,
  전건 조치. subagent 패널은 이 세션의 AgentTool 금지로 미수행.
- **npm 전역 설치(`claude.cmd`) 머신은 여전히 감지되지 않는다** — P1 조치로 배치 shim 을
  실행 대상에서 뺐기 때문이다. 회귀는 아니지만(수정 전에도 못 찾았다) 열려 있는 축이다:
  안전하게 부르려면 `node.exe` + 실제 진입점으로 해석해야 하고, 그것은 이번 범위 밖이다.

---

## 9. codex 적대 리뷰 후 재실측 (P1 1건 · P2 4건 조치)

리뷰 조치가 **실 Windows 에서 여전히 통하는가** — 좁힌 확장자 목록이 이번 사용자의 `.exe` 를
계속 찾는지, 새로 넣은 실존 확인이 넓힘을 무르게 하지 않았는지.

| 확인 | 결과 |
|---|---|
| `_exec_exts()` (실 Windows) | `['.com', '.exe']` — **배치 확장자 없음**(P1 조치 반영) |
| `_which_ai("claude")` | `C:\Users\<사용자>\.local\bin\claude.exe` — 여전히 찾는다 |
| `pick_ai("", None)` (자동 감지) | `claude` |
| `pick_ai("claude", None)` (명시 지목, 실재) | `claude` |
| `pick_ai("codex", None)` (명시 지목, **부재**) | **`None`** — 다른 AI 로 갈아치우지 않는다(P2-2 조치) |
| `_resolve_exe(["claude", …])[0]` | 같은 절대경로 |
| `_cli_help_text("claude")` (실 프로세스) | 도움말 수신 성공 |
| `[Parser]::ParseFile` (PS 5.1) · BOM | PARSE OK · `efbbbf` |
| `sh -n` (`bridge_setup.sh`) | OK |

`pick_ai("codex", None) = None` 이 이 표의 핵심이다 — **넓혔지만 무르지 않았다**를 실 머신에서
보인 것이고, P2-2 가 지적한 「없는 것을 있다고 답하던」 경로가 닫혔음을 동시에 보인다.

### 회귀 스위트 (조치 후)

| 항목 | 결과 |
|---|---|
| `test_win_ai_detection.py` | **34 passed** (신규 8건 추가 — P1·P2 각각의 잠금) |
| 컨테이너 전수 `make test` | rc=0 |

### 역검증 (§16.7 G11-b) — 조치분 뮤테이션 4종 추가 (누적 7종)

| 뮤턴트 | 되돌린 것 | 죽은 테스트 | 판정 |
|---|---|---|---|
| M4 | `.cmd`·`.bat` 를 실행 대상에 다시 넣음 (**P1 재도입**) | `test_batch_shims_are_never_executed` | PASS |
| M5 | 확장자 붙은 이름도 무조건 늘림 (P2-1 재도입) | `test_name_that_already_carries_an_extension_is_used_as_is` | PASS |
| M6 | `--ai` 지목의 실존 확인 제거 (P2-2 재도입) | `test_named_ai_that_is_absent_is_reported_as_absent` · `test_named_ai_is_not_replaced_by_another_one` | PASS |
| M7 | `pick_ai` 를 연결 확인 앞으로 되돌림 (P2-3 재도입) | `test_connection_is_checked_before_the_filesystem_is_searched` | PASS |

M4 는 **codex 가 지적한 그 상태를 그대로 복원**한 것이고, 그 상태에서 배치 shim 을 거르는
단언만 죽었다 — 다른 테스트는 전부 통과한다(넓힘 자체는 무해하고, 문제는 그 넓힘이 여는
실행 경로였다는 리뷰의 진단과 일치). 7종 모두 되돌리면 다시 전건 green.
