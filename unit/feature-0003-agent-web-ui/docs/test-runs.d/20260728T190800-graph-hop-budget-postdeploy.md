---
run_at: 2026-07-28T19:08:00+09:00
session: ai/claude-corp/feature-0016-hopbudget-postverify
scope: POST-DEPLOY 라이브 검증 — graph-hop-budget ('이웃 깊이' 예산 우선순위 + 절단 경고 오귀속 제거, PR #1024 → main 3687c43b)
verdict: PASS (부분 — 힌트 축은 실 마우스 영역으로 이월)
---

### Run (2026-07-28 19:08) — graph-hop-budget POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상 / 배경

PR #1024 (main `3687c43b`) 머지 → `deploy-web.sh` 롤링 배포(`9cb3d4ea`, soak PASS)한 **배포본**에서 검증.
cycle 내 PB-0008(원 세션 16:06~16:13, `docs/test-runs.d/20260728T161300-graph-hop-budget.md`)은 재-rebase·
§18.8 적대검증 흡수 **이전** 코드 기준이었고, 그 뒤 '확장할 관계 없음' 힌트의 판정 근거가
응답 엣지 → 백엔드 hop 실적(`expanded_hops`/`expanded_hop_edges`)으로 바뀌었으므로 배포본 재확인이 필요했다.

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`bin/win-browser.py doctor` → `ok: true`, `cdp_version` Chrome/150.0.7871.115)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://localhost/admin` (Windows hosts 에 `mysql-ai.company.local` 미등재 → caddy 를 localhost 로 접근)
- 배포본: healthz `git_commit=9cb3d4ea` · web-a/web-b/insight-worker/ask-worker 전부 `:9cb3d4ea` · 자산 스탬프 `?v=4218060f8e43`(서빙 HTML·ES 모듈 import 동일)
- 데이터: `mysql-gz-dev`(건즈 실데이터 — gunzgame/gunzlog), 스키마 그래프 176 노드
- Runner: AI
- Evidence: `artifacts/feature-0016-neighbor-depth-budget/pb0008-postdeploy/postdeploy_detail_nobanner.png`

#### 3. 결과

| # | 축 | 결과 |
|---|---|---|
| P1 | **배포본 API 가 신규 필드를 서빙** | `/api/admin/metadata/graph` 응답 키에 `truncated_hop` · `omitted_nodes` · `expanded_hops` · `expanded_hop_edges` **4개 전부 존재** — PASS |
| P2 | **깊이 선택이 실제로 다른 결과를 낸다** (핵심 요청) | `gunzgame.character` — d1 = 61n/60e, d3 = **199n/274e**, 양쪽 `truncated=false`, `expanded_hops=[60,40,98]` = **hop 마다 실제 증가**. 종전 구조라면 2-hop 이 계층 형제로 cap 300 을 소진해 절단되고 3-hop 이 2-hop 과 동일해졌을 앵커다. `gunzgame.account` 도 d1 22n → d3 130n, `expanded_hops=[21,20,88]` — PASS |
| P3 | **직결 정보 무손실** | `gunzgame.character` 직결 `ROUTINE_USES` d1 = 57 → 상세 패널 "사용하는 함수·프로시저 **(57)** · 읽기 39 · 쓰기 18" 이 **전 항목 실명 열거**(`… 외 N건` 0건) — PASS |
| P4 | **절단 경고 오귀속 해소** (사용자 리포트의 정체) | **depth select = 3** 상태에서 위 상세를 열었을 때 `.amgr-trunc-note` **0개** — 완전한 목록 위에 "일부만 불러옴" 이 붙지 않는다. 사용자가 보고한 "1-hop 초과 모든 항목에서 경고" 증상이 배포본에서 사라진 것을 실화면 확인 — PASS |
| P5 | **단일클릭 상세는 항상 1단계** (문구-동작 정합) | depth select 가 3 인데도 단일클릭 상세 상태줄이 `이웃 60개`(= d1 값) — 문구가 약속한 대로 동작 — PASS |
| P6 | **depth select 안내 문구** | `aria-label` = "이웃 확장 깊이 — 더블클릭·중심 보기에 적용" (종전 "노드를 선택/더블클릭하면 이 깊이로" 거짓 안내 제거) — PASS |
| P7 | **❓ 도움말 모달 문구** | 실렌더 확인: "상단 바에서 노드를 검색하고 이웃 깊이·표시 종류를 조절합니다. **이웃 깊이는 더블클릭·중심 보기에 적용되며, 2단계 이상은 참조·사용 관계만 따라갑니다(단일클릭 상세는 항상 1단계).**" — PASS |
| P8 | **'확장할 관계 없음' 힌트** (R2-c/R3-b 흡수분) | **부분 — 라이브 미확인.** 힌트는 확장·중심보기 경로의 상태줄에서만 발화하고, 그 경로는 PixiJS 캔버스의 더블클릭/우클릭이라 **합성 PointerEvent 로 열리지 않았다**(canvas 중심 + 7×7 격자 우클릭 49점 전부 컨텍스트 메뉴 미개방 — 알려진 제약). 대신 **힌트 조건이 라이브 데이터에서 실제로 성립함을 API 로 실측**: `gunzlog.gamblelog` d3 → `expanded_hops=[2,0]` · `expanded_hop_edges=[2,0]` · `truncated=false` (= 2-hop 이후 실적 0 → 힌트 표시 조건), 대조군 `gunzgame.accounthonor` d3 → `expanded_hops=[5,2,0]` · `expanded_hop_edges=[5,3,0]` (= 실적 있음 → 힌트 미표시 조건). 렌더 판정 로직은 헤드리스 `test_detail_dbgroups.js` ⑳㉑ 9건이 잠근다(절단 시 억제·엣지-only 실적·구 응답 폴백·형 방어 포함). |

#### 4. 판정

**PASS (P8 부분)** — 사용자 요청의 본질인 두 축(① 깊이 선택이 실제로 다른 결과를 낸다 ② 완전한 목록에
절단 경고가 붙지 않는다)은 배포본 실화면으로 확증됐다. 잔여는 힌트 문구의 실화면 발화 1건이며, 그 조건 성립은
라이브 API 로, 렌더 판정은 헤드리스 계약으로 각각 확인됐다. 실 마우스 조작이 가능한 다음 브라우저 세션에서
`gunzlog.gamblelog` 를 depth 3 으로 더블클릭해 상태줄 문구를 눈으로 확인하면 종결된다.
