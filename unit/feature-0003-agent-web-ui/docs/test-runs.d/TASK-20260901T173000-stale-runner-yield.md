---
run_at: 2026-09-01T17:35:00+09:00
session: ai/claude/feature-0043-stale-runner-yield
scope: 낡은 러너 양보 + 자가 종료 (REQ-20260901-stale-runner-yield)
verdict: PASS
---

# Run — TASK-20260901T173000 낡은 러너가 최신 러너의 질문을 가로채는 결함

## Environment

- 컨테이너 `repo-unittest-agent:latest`, worktree 마운트(`/work`),
  `PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0003-agent-web-ui/src:/work`,
  `PYTHONDONTWRITEBYTECODE=1` (Makefile `test` 타깃과 같은 배선)
- **Environment: Windows-browser — 미수행(사유)**: `static/**` 변경은 **러너 파이썬 사본 1개**
  뿐이다(브라우저가 실행하지 않고 사용자가 내려받는 파일). HTML·CSS·JS **변경 0** — 렌더·
  레이아웃·상호작용 표면이 없다. 서버 변경도 API 응답 필드·상태코드이며 화면 마크업이 아니다.

## 1. 라이브 근거 (수정의 근거가 된 실측)

| 관측 | 값 |
|---|---|
| 배포본 러너 지문 (`web-a` 안에서 직접 산출) | `d0ac1263d454` |
| 최신 러너 토큰 (account 10) | `d0ac1263d454` · 대기 시작 17:19:51 |
| **옛 러너 토큰 (account 10)** | **`0a4ba732366c`** · 15:42~ · 하트비트 17:23 까지 생존 |
| 17:20:03 질문 처리자 | **옛 러너** (`/root/.mysql-ai-bridge/bridge.log` 17:20:03→17:20:08) |
| 그 답변 형식 | 옛 형식 — `AI 가 오류로 끝났습니다(exit 1):` (사유 없음) |

즉 사용자는 안내대로 「연결 준비」로 최신 러너를 띄웠는데, 옛 러너가 점유 경쟁에서 이겼다.

## 2. 단위 검증

| 대상 | 결과 |
|---|---|
| 신규 `tests/test_stale_runner_yield.py` **20건** | **PASS** |
| `feature-0043` + `feature-0003` + `feature-0041` + `feature-0023` 전량 | **rc=0** |
| ruff (`ai_tools.py`·`oauth_store.py`·`bridge_agent.py`·신규 테스트) | All checks passed |

## 3. 뮤테이션 역검증 (5종 전건 KILL)

| # | 주입 | KILL |
|---|---|---|
| M1 | 상대 판정 → 절대 판정(최신 러너 존재 확인 제거) | ✔ |
| M2 | 후보 질의에서 자기 제외(`TokenHash <>`) 삭제 | ✔ |
| M3 | 취소 통보까지 양보 판정으로 억제 | ✔ |
| M4 | `claim_request` 집행 게이트 무력화 | ✔ |
| M5 | 러너 자가 종료 신호 수신 제거 | ✔ |

M1 이 이 파일의 핵심이다 — 절대 판정으로 되돌리면 「배포 직후 단독 러너가 계속 일한다」가
깨지고, 그것이 곧 전 사용자 서비스 중단이다.

## 4. 배포 후 실측 필요분 (정직 분리)

- 서버 판정(양보·집행·억제)은 **러너 갱신 없이 즉시 발효**한다 — 배포 후 옛 러너가 다시
  나타나는 상황에서 관측 가능.
- 러너 **자가 종료**는 그 러너가 새 사본으로 갱신된 뒤에만 발효한다(지금 도는 옛 프로세스에는
  그 코드가 없다). 그래서 서버 축이 1차 방어이고 자가 종료는 정리 축이다.
- 재측정 축: `WebOAuthTokens` 에서 같은 `AccountId` 에 배포본 지문 러너와 다른 지문 러너가
  **동시에** 하트비트하는 창의 지속 시간(자가 종료가 발효하면 분 단위로 짧아진다).
