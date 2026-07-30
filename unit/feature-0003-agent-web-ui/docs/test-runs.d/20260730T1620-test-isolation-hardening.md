---
run_at: 2026-07-30T16:20:00+09:00
session: ai/root/test-isolation-hardening
scope: 테스트→라이브 런타임 설정 오염 재발 차단 — 도달성 층(전용 compose 프로젝트) + fail-loud + 감지 (TASK-20260730T1620)
verdict: PASS
---

### Run — 재발 벡터 무효화 실증 (Environment: **컨테이너 pytest, 라이브 프로젝트명 강제 시도**)

웹 자산 변경 0 → PB-0008 비대상. 본 cycle 의 검증 명제는 **"재발 벡터(`COMPOSE_PROJECT_NAME=repo`
로 라이브 네트워크 참여)를 실제로 무효화했는가"** 이므로, 그 벡터를 **일부러 재현한 채** 측정했다.

- Runner: AI · 운영 스택 상시 기동 · 측정 채널: `WebRuntimeSettings` 전 행 md5 +
  `WebAuditEvents` 의 `RemoteAddr='testclient'` 신규 건수

#### A. 재발 벡터 무효화 (핵심)

실행: `COMPOSE_PROJECT_NAME=repo make test` — **라이브 프로젝트명을 일부러 지정**.

| 항목 | 기대 | 결과 |
|---|---|---|
| 실제 컨테이너 프로젝트 | `-p repo-unittest` 승리 | `repo-unittest-agent-run-a0c2f09089e6` ✔ |
| 생성 네트워크 | 전용 | `repo-unittest_dbnet` ✔ |
| `WebRuntimeSettings` md5 | 불변 | `2a9d7a4ca79b86589a48c2307001c08e` → 동일 ✔ |
| `testclient` audit 신규(Id > 544242) | 0 | **0건** ✔ |
| pytest | 전량 통과 | **FAILED 0** (`[100%]` 도달, `make exit=0`) ✔ |

#### B. 도달성 층 직접 확인

전용 프로젝트 컨테이너 안에서 라이브 서비스명으로 TCP probe:

```
mysql:3306     -> 도달 불가
pgbouncer:6432 -> 도달 불가
```

`dbnet` 이 external 이 아니라 프로젝트 스코프(`<project>_dbnet`)이므로, 프로젝트를 고정하면
서비스명이 DNS 로 해석되지 않는다. 값 방어(`DB_PORT=1`)보다 **한 층 아래**에서 끊긴다.

#### C. fail-loud 실측 (뚫렸을 때 조용하지 않은가)

라이브 프로젝트(`-p repo`)로 pytest 를 직접 실행 — 즉 도달성 층을 우회한 상황을 재현:

```
ImportError while loading conftest '/work/conftest.py'.
conftest.py:109: in <module>
    _assert_live_stack_unreachable()
E   RuntimeError: 단위 테스트가 라이브 스택 네트워크 안에서 실행되고 있다 (mysql:3306 도달 가능). …
```

**collection 단계에서 중단 → 테스트 0건 실행 → 오염 0.** 특정 경로가 아니라 "라이브 스택 안인가"
라는 상태를 검사하므로, 예측하지 못한 미래의 우회 경로도 같은 지점에 걸린다.

#### D. 감지 층 실측

`bash bin/check-test-contamination.sh --days 3`:

```
최근 3일간 테스트 유입(RemoteAddr=testclient) 150건 감지
  [복구됨]   AGENT_TIMEOUT_SEC: 현재=900 (테스트가 쓴 값 90 아님)
  [오염 잔존] agent_max_output:claude-sonnet-4: 현재=100000 (테스트가 쓴 값) / 사람 최종 설정=128000
  [오염 잔존] model_thinking_budget:claude-haiku-4: 현재=30000 (테스트가 쓴 값) / 사람 설정 이력 없음
exit=1
```

사용자가 복구한 키와 아직 테스트 값인 키를 정확히 갈라낸다. 과거 이력만으로 상시 red 가 되지
않도록 **잔존일 때만** exit 1.

#### E. DB 레벨 차단 가능성 조사 (폐기 근거)

branch 사본 축을 완전히 덮으려면 저장소 밖 층이 필요해, MySQL 이 운영/테스트 커넥션을 구분할 수
있는지 먼저 확인했다:

```
information_schema.PROCESSLIST + performance_schema.session_connect_attrs
→ 운영·테스트 모두 program_name=NULL, _client_name=libmysql, _pid=1 (동일), IP 는 동적
```

구분 신호가 없어 트리거 기반 거부는 성립하지 않는다. 계정 분리·자격증명 회전은 가능하지만
alembic·백업 경로를 함께 옮기는 대공사라 이번 범위에서 제외(REVIEW 에 근거 기록).

#### 판정

PASS — 재발 벡터 무효화(A) · 도달성 차단(B) · 뚫림 시 fail-loud(C) · 잔존 감지(D) 를 모두 라이브
실측으로 닫았다. 현존 취약 worktree 2개는 본 PR 머지로 자동 해소되지 않으며, 사용자 승인 하에
머지 후 테스트 인프라 3파일을 동기화한다(TASK 잔존 항목).
