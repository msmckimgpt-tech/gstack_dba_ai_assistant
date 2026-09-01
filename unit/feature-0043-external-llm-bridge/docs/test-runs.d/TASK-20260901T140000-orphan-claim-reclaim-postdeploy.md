# TASK-20260901T140000-orphan-claim-reclaim — POST-DEPLOY 라이브 실측

- **Environment: Windows-browser** (`bin/win-browser.py` relay → Chrome/151.0.7922.170,
  `https://localhost/` · 계정 `bootstrap_admin`)
- **일시**: 2026-09-01 14:35~14:40 KST
- **배포본**: `9c04b52c` (`make deploy-web`, rc=0 · scope=all · soak 통과 · 대화 스모크 PASS)
- **자산 스탬프**: `da49561ff923` → **`cd84170acd28`** (갱신 확인)

## 0. 배포 도달

| 서비스 | GIT_COMMIT |
|---|---|
| web-a · web-b | `9c04b52c` |
| insight-worker · ask-worker · ops-scheduler | `9c04b52c` |
| ext-tool-mcp-a · ext-tool-mcp-b | `9c04b52c` |
| 엣지 `no upstreams available` (최근 10분) | **0건** |

## 1. 코드 도달 (라이브 컨테이너 grep)

| 축 | 배포 전 | 배포 후 |
|---|---|---|
| `ai_tools.py` 의 `stalled` | 0 | **4** |
| `composer.js` 의 `phase === "stalled"` | 0 | **1** |
| `static/agent/bridge_agent.py` 의 `init_runner_instance` | 0 | **2** |
| `SUBSTRING_INDEX(ClaimedClient` | 0 | **2** (제출 · 취소 통보) |
| `_NO_PROGRESS_ANNOUNCED` 가드 | 0 | **7** |
| lease 초과 상한(`_BRIDGE_CLAIM_LEASE_MIN * 60`) | 0 | **1** |

프론트 자산은 브라우저에서 **실제로 받아** 확인했다(`fetch('/static/app/composer.js?v=cd84170acd28')`
→ 194,266자 · `phase === "stalled"` 있음 · 토스트 문구 「진행 신호가 끊겼습니다」 있음).
서버 고지 문구(「…분째 진행 신호가 없습니다」 · 「자동으로 다시 배달됩니다」)도 배포본에 존재.

## 2. 배포본 함수 직접 구동 (`docker exec repo-web-a-1`)

```
compose            : console-manual#abc123def456
instance 추출       : abc123def456
구 러너(미신고)      : console-manual          ← 종전 값 그대로 (호환)
match new/old/foreign: True True False
LIKE 메타문자 무시   : "a%b" → console-manual 접미 없음
임계 창             : 621 < 900 < 1800  → True
release            : ['t_a']  committed=True
release 경계        : ClaimedBy=%s · SubmittedAt IS NULL · 패턴 "%#inst1"
빈 신고 no-op       : [] · SQL 0회
```

## 3. 국면 판정 — 배포본 `_bridge_phase` 를 라이브 컨테이너에서 실행

| `claimed_age_sec` | 결과 | 기대 | |
|---|---|---|---|
| 5 | `working` | `working` | OK |
| 899 | `working` | `working` | OK |
| **901** | **`stalled`** | `stalled` | OK |
| `None` | `working` | `working` | OK (관측 불가는 단정하지 않는다) |
| `canceled` 상태 + age 99999 | `canceled` | 종결 우선 | OK |
| `submitted` + age 99999 | `done` | 종결 우선 | OK |

**ALL: PASS**

## 4. 점유자 대조 술어 — **실 MySQL 서버**에서 검증 (P1-1·P1-2 회귀 차단)

`submit_answer` / `read_task_attachment` 의 WHERE 술어를 라이브 MySQL 에서 그대로 평가:

| `ClaimedClient` 형식 | 통과 |
|---|---|
| `console-manual#abc123` (인스턴스 신고) | **1** |
| `console-manual` (구 러너) | **1** |
| `other-cli#abc123` (다른 세션) | **0** |
| `NULL` (컬럼 추가 이전) | **1** |

→ 인스턴스 접미가 붙어도 제출·첨부 읽기가 막히지 않고, 남의 세션은 여전히 차단된다.
이것이 자체 적대 검증에서 잡힌 **서비스 정지급 P1 두 건**의 회귀 차단선이다.

## 5. 라이브 화면

배포 후 화면 재렌더 확인(스탬프 `cd84170acd28`), 연결 배지 **「● 대기 중」**(러너 청취 중),
컴포저 활성. 스크린샷 `/tmp/pb0008-post-orphan.png`.

## 6. 미검증으로 남긴 것 (정직 표기)

| 항목 | 왜 못 했나 |
|---|---|
| **러너 재기동 → 고아 회수 end-to-end** (`released_claims` 응답 + 러너 로그 「직전 러너가 붙들고 있던 질문 N건을 되살렸습니다」) | 설치된 러너 사본이 **구버전**(`cb1afd3a727e` ≠ 배포본 `f6c1d196cbe8`)이라 인스턴스를 신고하지 않는다. 러너는 **사용자 머신의 파일**이므로 우리 배포로 갱신되지 않는다 — 사용자가 원클릭 명령으로 다시 받아야 하고, 서버는 이미 하트비트 응답 `runner_update.stale_build` 로 그 사실을 러너 로그·연결 칩에 알린다 |
| **`stalled` 말풍선 라이브 관측** | 그 상태를 만들려면 「점유됐고 15분 무진행인 task」가 필요하다. 지금은 대기 중 task 가 없고, 인위적으로 만들려면 라이브 DB 를 직접 조작해야 한다. 더구나 **같은 호스트에 다른 세션 6곳이 동시 작업 중**(REGISTRY 활성 · `:18095` 검증 인스턴스 · 검증용 러너 3개)이라 공용 제품 경로에 질문을 주입하면 남의 검증과 충돌한다. 판정 로직은 §3 에서 배포본으로 실행해 확인했고, 표시층은 §1 에서 브라우저가 받은 실물 자산으로 확인했다 |

## 7. 범위 밖 — 이미 다른 cycle 이 다루고 있다

PRE-DEPLOY 에서 발견한 「러너의 AI 가 브리지 프롬프트를 프롬프트 인젝션으로 판정해 거부」는
별도 worktree `ai/claude/feature-0043-bridge-injection-falsepositive` (14:01 개시) 가 이미
작업 중이다. 중복 cycle 을 열지 않는다.
