---
run_at: 2026-07-29T14:12:00+09:00
session: ai/root/test-live-db-isolation
scope: make test 가 라이브 컨트롤플레인(agent_memory.WebRuntimeSettings)·공유 스냅샷을 덮어쓰던 근본 원인 차단 (TASK-20260729T1412)
verdict: PASS
---

### Run — 테스트 격리 (Environment: **컨테이너 pytest, 라이브 네트워크 동등 조건**)

웹 자산(HTML/CSS/JS) 변경이 0 이므로 PB-0008 Windows-browser 시각검증은 비대상이다. 대신 본
cycle 의 검증 대상은 **"테스트 실행이 라이브 운영 상태를 바꾸지 않는가"** 라, 그것을 직접
측정할 수 있는 조건 — 운영 스택이 떠 있는 개발 머신 + `COMPOSE_PROJECT_NAME=repo`(라이브
compose 네트워크에 동일 참여) — 에서 실행 전후 라이브 상태를 대조했다.

- Runner: AI · Host: WSL2 · 운영 스택 상시 기동(`repo-mysql-1`, `repo-web-a/b-1`, 워커 전부 up)
- 실행: `cd .worktrees/test-live-db-isolation && COMPOSE_PROJECT_NAME=repo make test`
- 측정 채널: `agent_memory.WebRuntimeSettings` 전 행 md5 + `WebAuditEvents` 의
  `RemoteAddr='testclient'` 신규 건수(사고의 서명 — conftest 기본 계정 id=1, UA=testclient)

#### A. 오염 차단 (본 cycle 의 1차 목표)

| 항목 | 실행 전 | 실행 후 | 판정 |
|---|---|---|---|
| `WebRuntimeSettings` 전 행 md5 | `c682bedad1a9823c4bfc17b391ba1025` | 동일 | PASS |
| `testclient` audit 신규(Id > 512073) | — | **0건** | PASS |
| `AGENT_TIMEOUT_SEC` 라이브 값 | 900 | 900 | PASS |

수정본으로 사고 표면 2 파일만 재실행(`test_runtime_settings_api.py` + `test_live_db_isolation.py`)
→ **21 passed**, 같은 채널로 audit 신규 **0건** 재확인(Id > 512147).

#### B. 회귀 판정 (baseline 대비 FAILED 집합 diff)

인상이 아니라 집합 비교로 닫았다. baseline 은 **main 코드 + 동일 격리 env**(`-e DB_PORT=1`,
`-e RUNTIME_SETTINGS_SNAPSHOT_PATH=/tmp/...`)로 따로 전량 측정 — 이 조건이면 main 코드로도 라이브에
쓰지 못하므로 baseline 측정 자체가 오염을 만들지 않는다.

| | FAILED |
|---|---|
| baseline (main + 격리 env) | **15** |
| 변경 후 (worktree + `make test`) | **13** |
| 변경 후에만 있는 실패(회귀) | **0** |
| baseline 에만 있는 실패(해소) | **2** — `test_missing_snapshot_is_fail_open` · `test_get_returns_registry` |

해소 2건은 `default`(= env 반영 baseline)에 스펙 리터럴 60 을 요구하던 환경 의존 어서션으로,
운영 `.env`(AGENT_TIMEOUT_SEC=300)를 상속하는 컨테이너에서 상시 FAIL 이었다.

잔존 13건은 전부 attachment 계열(`test_attach_inline_honesty` 4 · `test_attachment_idor` 4 ·
`test_attachment_user_version_context` 5)이며, **격리 env 를 걷어내고 돌려도 동일하게 실패**함을
따로 확인했다 → 본 변경과 무관한 기존 baseline. 표본: `test_attachment_context_scopes_by_account`
는 FakeConn 을 넘겨도 `execute` 가 호출되지 않아 `KeyError: 'sql'`(DB·env 무관 경로).

#### C. backstop 실효 직접 확인

`Makefile TEST_ISOLATION_ENV` 의 `DB_PORT=1` 이 실제로 커넥션을 끊는지 쓰기 없이 확인:

```
app.DB_PORT = 1 / config.DB_PORT = 1
app._connect_memory() → DatabaseError 2003 (HY000): Can't connect to MySQL server on 'mysql:1' (111)
```

#### D. 대조 실증 (수정 전 코드는 1회 실행으로 즉시 오염)

검증 도중 cwd 가 main worktree 인 상태로 **격리 없는** `make test` 를 1회 실행했고, 그 즉시
라이브 `AGENT_TIMEOUT_SEC` 이 900 → 90 으로 덮어써졌다(audit `512107~512109`, `testclient`).
사용자가 `14:08:53` 에 900 으로 복구. 의도한 실험은 아니었으나, "수정 전에는 단 1회 실행으로
운영값이 롤백된다" 는 대조군을 그대로 남긴다.

#### E. CI 거짓 FAIL 1건과 가드 조건 정정 (PR #1048 1차 red)

스냅샷 경로 가드의 강제 조건을 처음엔 `os.path.isdir("/shared")` 로 뒀는데, CI 러너는
`app.py` 의 `SESSION_DIR.mkdir()` 를 위해 `sudo mkdir -p /shared` 로 **빈 디렉토리를 만든다**
(`.github/workflows/ci.yml`). 그래서 오염 표면이 없는 CI 에서 가드가 발동해 거짓 FAIL 했다.

조건을 **운영 스냅샷 파일의 실재**(`os.path.exists("/shared/runtime_settings.json")`)로 정정.
"덮어쓸 대상이 실재하는가" 가 오염 표면의 정확한 판별이다. 양방향 실증:

| 조건 | 기대 | 결과 |
|---|---|---|
| 격리 env 有(= `make test` 경로) | PASS | 3 passed |
| 격리 env 완전 부재 + 운영 스냅샷 실재 | **FAIL(가드 발동)** | FAILED — `snapshot_path = /shared/runtime_settings.json` 지목 |

즉 Makefile 에서 `TEST_ISOLATION_ENV` 가 빠지는 회귀는 여전히 잡히고, CI 는 통과한다.

#### 판정

PASS — 오염 차단(A) · 회귀 0(B) · backstop 실효(C) 가 모두 라이브 실측으로 닫혔다.
잔존 13 FAILED 와 PG 격리 미적용은 TASK 잔존 항목으로 명시(숨기지 않음).
