---
run_at: 2026-09-02T12:10:00+09:00
session: ai/claude/feature-0043-runner-modularization-postdeploy
scope: 러너 모듈 분할 POST-DEPLOY 실측 (배포 ae02c3e1)
verdict: PASS
---

# Run — TASK-20260902T110000 POST-DEPLOY 실측

배포 `ae02c3e1` (전 서비스 SHA 일치 · 대화 스모크 PASS · `no upstreams available` **0건**).
이 cycle 로 러너 배포본이 **커밋 산출물에서 빌드 산출물로** 바뀌었으므로, 「빌드가 정말 만드는가」와
「사용자가 정말 받을 수 있는가」를 배포본에서 실측한다.

## Environment

- 라이브 스택 (Caddy :443 · `mysql-ai-agent:ae02c3e1`)
- **Environment: Windows-browser — 미수행(사유)**: 본 fragment 는 다운로드 경로(HTTP)와 러너
  실행을 검증한다. 브라우저 렌더 표면 변경 0(이번 cycle 의 `static/**` 변경은 추적 해제뿐이며
  내용 동일) — 근거는 `TASK-20260902T110000-runner-modularization.md` 참조.

## 1. 새 배포 게이트 `bridge_runner_verify` — 판별력 실증

정의만 두고 호출되지 않거나, 있어도 아무것도 못 잡으면 게이트가 아니다. 양측을 실측했다.

| 대상 | 기대 | 결과 |
|---|---|---|
| 배포 이미지 `mysql-ai-agent:ae02c3e1` | PASS | `OK — 브리지 러너 배포본 존재·컴파일 확인(러너 + 설치 스크립트 2종).` |
| 러너 없는 대조 이미지 (`python:3.11-slim`) | ABORT | `ABORT: 브리지 러너 배포본 누락 …` · **exit 1** |

> ⚠ 최초 대조 실행은 SURVIVE 로 나왔는데 게이트 결함이 아니라 **하네스 결함**이었다 — 추출한
> 함수에 물린 `die` 스텁이 `exit` 아닌 `return` 이라 ABORT 후에도 실행이 이어졌다. 실제
> `deploy-web.sh` 의 `die()` 는 `err "$*"; exit 1` 이고 호출부(`bin/deploy-web.sh:1843`)는
> 서브셸·`if` 조건이 아닌 평문 문장이라 종료가 그대로 전파된다. 충실한 `die` 로 재실행해 exit 1
> 을 확인했다. (이 cycle 에서 하네스 함정이 잡힌 것은 세 번째다 — 판정 전 하네스 자기검증을
> 먼저 세우지 않으면 «게이트 무력» 오보가 난다.)

## 2. baked 이미지 — 빌드가 실제로 만들었는가

```
/app/web/static/agent/bridge_agent.py    269,768 B
/app/web/static/agent/bridge_setup.sh     54,122 B
/app/web/static/agent/bridge_setup.ps1    39,731 B
python3 -m py_compile bridge_agent.py  → 컴파일 OK
```

소스에 커밋된 사본이 하나도 없는 상태에서 이미지에 실물이 있다 = **Dockerfile 의 빌드 RUN 이
유일한 출처로서 동작한다**.

## 3. 사용자 도달성 — end-to-end

| 경로 | HTTP | 크기 |
|---|---|---|
| `GET /static/agent/bridge_agent.py` | **200** | 269,768 B |
| `GET /static/agent/bridge_setup.sh` | **200** | 54,122 B |
| `GET /static/agent/bridge_setup.ps1` | **200** | 39,731 B |

- **서빙본 = 이미지 산출물**: sha256 `4bdb0bace9b966b7…` 양쪽 일치.
- **내려받은 파일이 실제로 실행된다**: `python3 bridge_agent.py --help` 가 인자 목록을 정상 출력
  (번들 연접이 깨지지 않았음을 파일이 아니라 **실행**으로 확인).

## 4. 무중단

`caddy` 로그 `no upstreams available` **0건** (배포 창 15분).

## 잔여

- 실사용자 머신에서의 「연결 준비 → 러너 재기동 → 하트비트 왕복」 1회는 사용자 조작이 필요하다.
  기존 상주 러너는 `_self_build()` 지문이 바뀌어 다음 하트비트에서 `runner_update` 안내를 받는다
  (동작 변경 아님 — 재설치로 해소).
