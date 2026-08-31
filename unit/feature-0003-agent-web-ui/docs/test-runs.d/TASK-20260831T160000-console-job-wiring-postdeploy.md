## Run — TASK-20260831T160000-console-job-wiring (POST-DEPLOY)

- Date: 2026-08-31
- Environment: Windows-browser (PB-0008, `bin/win-browser.py` relay · Chrome/151.0.7922.170)
- Target: `https://localhost/admin` — 배포본 **d550db16**
- Result: **PASS (관측 가능 축 전부)** · 위임 왕복은 미관측(사유 아래)

### 무엇을 확인했나

| 축 | 관측 |
|---|---|
| 신규 ESM 모듈 로드 | `llm-state.js` 가 폴링 헬퍼(`awaitDelegatedResult`)를 포함해 서빙되고, 그 모듈을 import 하는 화면이 **정상 렌더**된다(자유 식별자 ReferenceError 없음) |
| 조작면 게이트 무회귀 | `metadataSuggestBtn` = `disabled` · `is-llm-blocked` · title "메타데이터 AI 자동완성: 연결은 되어 있는데 지금 듣고 있는 AI 가 없습니다…" |
| 폴링 엔드포인트 | `GET /api/admin/ai-jobs/j_nonexistent` → **404** + `{"error":"작업을 찾을 수 없습니다."}` (없는 것과 남의 것을 구분하지 않는 계약 유지) |
| 종류별 위임 판정 | `/api/admin/me` → `delegation:"runner_idle"` · `delegable_jobs:[]` · `inactive_surfaces:4` |
| 러너 배포본 | `/static/agent/bridge_agent.py` 가 `AGENT_FEATURES` 를 포함해 서빙(정본↔배포본 해시 일치) |

### `delegable_jobs: []` 가 **정상**인 이유

`console_llm_state` 는 러너 자격(`delegation == ready`)이 서지 않으면 종류 목록을 접는다.
지금 라이브에는 `console_jobs` 를 신고하는 러너가 없으므로 빈 배열이 맞다 — 그리고 그
상태에서 조작면이 비활성인 것이 **이 설계의 요점**이다(러너 자격만 보고 열면 "눌렀는데 아무
일도 없는" 버튼이 된다).

### 미관측 (정직하게)

**위임 왕복 e2e**(적재 → 러너 수행 → 결과가 폼에 채워짐)는 관측하지 못했다. 그러려면
사용자 머신에서 이 배포본의 `bridge_agent.py` 를 받아 실행해 `console_jobs` 를 신고해야
하는데, 그 러너는 우리가 띄울 수 있는 것이 아니다(AI 는 사용자 계정 자격증명을 갖지 않고,
PB-0008 §41 도 테스트 프로필의 민감 계정 로그인을 금지한다).

함수 수준은 회귀 18건이 덮는다(형식 정합 · 이음매 순서 · 러너 프레이밍 · 프롬프트 평탄화
순서 · 폴링 종료 조건). **왕복 자체는 사용자 확인에 위임한다.**

### 배포 체크리스트

- [1] web-a/web-b = `mysql-ai-web:d550db16` · soak 통과
- [2] 워커 = `mysql-ai-agent:d550db16` (insight · ask · ops-scheduler)
- [1b] 대화 스모크 PASS (전환 모드)
- [2b] surge 잔존 0
- [5] **무중단 실측** `no upstreams available` = **0**
- `/readyz` git_commit = `d550db16`
