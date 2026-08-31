## Run — TASK-20260831T100000-console-llm-parity (POST-DEPLOY)

- Date: 2026-08-31
- Environment: Windows-browser (PB-0008, `bin/win-browser.py` relay · Chrome/151.0.7922.170)
- Target: `https://localhost/admin` (Caddy :443 any-host) — 배포본 **5e806c6a**
- Scope: feature-0043 TASK-20260831T100000 — 관리 콘솔 LLM 정합 (A 정직화 · B 관측축)
- Result: **PASS (4/4 축)**

### 왜 실화면이어야 했나

이 cycle 의 산출물은 전부 **화면이 자기 상태를 말하는가**에 관한 것이다. 단위 테스트는
"함수가 옳은 값을 돌려주는가" 를 잠그지만, 이 feature 가 반복해 겪은 결함은 값이 아니라
**연결**이었다(P0-E·P0-U: 헬퍼는 멀쩡한데 아무도 부르지 않았다). 배지가 붙는가·버튼이
잠기는가·배너가 뜨는가는 렌더까지 가 봐야 참이 된다.

### 관측

| 축 | 확인한 것 | 실측값 |
|---|---|---|
| A2 조작면 | `metadataSuggestBtn` 이 **누르기 전에** 잠기고 사유를 단다 | `disabled=true` · `is-llm-blocked` · title = "메타데이터 AI 자동완성: 연결은 되어 있는데 지금 듣고 있는 AI 가 없습니다. 본인 머신에서 AI 를 실행해 주세요." |
| A3 미적용 표시 | 패널 배지 + 사유 dropdown + 최하단 집계 | 배지 3 · `.admin-llm-detail` 7 · `#adminLlmInactiveSummary` "현재 미적용 기능 **4**" (모델별 추론 예산 · AI 자가 리뷰 · 모델별 접근 권한 · 실행 타임아웃) |
| A4 관측 오독 | 사용량·추론 배너 | 사용량: "…값이 0 에 가까운 것은 사용이 없다는 뜻이 아닙니다…" / 추론: "서버 측 자가 리뷰는 실행되지 않습니다(고장이 아닙니다). 아래 수치는 전환 이전 기록입니다." |
| B 관측축 | `AI 운영 현황` 에 브리지 축 + KPI | 축 `외부 AI 브리지` 렌더 · KPI `연결된 AI` · `대기 / 처리중` 존재 |

### 이 실측이 **추가로** 증명한 것

툴팁이 `no_connection`("본인 AI 를 연결하면") 이 아니라 **`runner_idle`**("연결은 되어
있는데 지금 듣고 있는 AI 가 없습니다") 로 나왔다. 즉 라이브 데이터에서 두 상태가 실제로
갈렸다 — 토큰은 살아 있고 러너만 꺼진 창이다.

이 구분은 `_console_llm._classify` 가 바깥 원인부터 판정하도록 설계한 결과이고, 하나로
합쳤다면 이미 연결한 운영자에게 "연결하세요" 라고 말했을 것이다(P0-G 가 대화 축에서 고친
형태와 같다). 픽스처가 아니라 **라이브 상태**가 그 분기를 탄 것이 증적의 핵심이다.

### 배포 체크리스트 (feature-0014 RUNBOOK §10)

- [1] web-a/web-b = `mysql-ai-web:5e806c6a` · soak 통과
- [2] 워커 롤아웃 = `mysql-ai-agent:5e806c6a` (insight · ask · ops-scheduler · ext-tool-mcp a/b)
- [1b] 대화 스모크 PASS — 전환 모드(서버 계정 LLM 차단 확인)
- [2b] surge 잔존 0
- [3] 신규 자산 서빙: `/static/admin/llm-state.js` 200 (11,657 B) · `admin.css` 배지 규칙 매칭
- [4] 실 사용자 표면 = 본 문서
- [5] **무중단 실측**: `caddy | grep -c 'no upstreams available'` = **0**
- `/readyz` = `{"status":"ready","git_commit":"5e806c6a","mysql_ok":true,"pg_ok":true}`

### 미검증 (정직하게)

- **위임 경로 e2e** — `JOB_SPECS[...]["wired"]` 가 전부 False 라 콘솔 작업은 적재되지 않는다.
  위임이 실제로 도는 화면(작업 적재 → 러너 수행 → 결과 반영)은 C7~C10 배선 후에야 관측 가능.
- **`delegation=ready` 분기의 화면** — 콘솔 작업 기능을 신고하는 러너가 아직 없다(러너
  `bridge_agent.py` 의 `features` 신고가 C10). 지금 관측한 것은 `runner_idle` 분기다.
