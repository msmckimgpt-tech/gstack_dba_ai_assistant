---
run_at: 2026-07-28T16:13:00+09:00
session: ai/claude/feature-0016-neighbor-depth-budget
scope: unit/feature-0002-agent-core/src/modules/metadata_graph.py (neighborhood) · unit/feature-0003-agent-web-ui/src/{routers/admin_metadata.py,static/graph/graph-ctxmenu.js,static/graph/graph-core.js,static/admin.html}
verdict: PASS
---

### Run (2026-07-28) — graph-hop-budget: '이웃 깊이' 실효성 + 절단 경고 오귀속 — **Environment: Windows-browser**

#### 1. 사용자 질의

> `그래프 뷰` 에서, '보기 옵션' 중 '이웃 깊이' 에 대한 작동이 의미가 있는지 검토해주세요.
> 현재는 '1-hop' 을 초과한 모든 항목에서 "이웃 조회 상한 - 일부만 불러옴" 과 같은 주의문구가 출력됩니다.

#### 2. 진단 (라이브 실측 — 컬럼 투영 Table 40개 표본, seed 고정)

| 지표 | 종전 | 개선 후 |
|---|---|---|
| 1-hop 절단 | 0% | 0% |
| 2-hop 절단 | 50% | **0%** |
| 3-hop 절단 | 60% | **0%** |
| 3-hop 결과 == 2-hop 결과 | 50% | **20%** |
| 2-hop REFERENCES 엣지 합계 | 98 | **98** (정보 손실 0) |

핵심 원인 4가지: ① cap(300)이 hop 경계보다 먼저 걸려 3-hop 이 2-hop 과 동일해짐 ② 2-hop 이 계층 엣지를 따라가 형제 수백 개가 예산 소진(앵커 `masangsoft_documents_20260414`: Routine +258 / Table +0) ③ 절단 순서가 라벨 알파벳 순이라 Table 이 가장 먼저 탈락 ④ **경고가 앵커 직결 목록에 오귀속** — `fhgame1.FH_CHAR` 직결 `ROUTINE_USES` 155건이 depth 1·2·3 모두 155건인데 d2/d3 에서 `truncated=true` 라 완전한 목록 위에 "일부만 불러옴" 이 붙었다.

#### 3. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`bin/win-browser.py doctor` → `ok: true`, no-admin userspace relay)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://localhost/admin` (Windows hosts 에 `mysql-ai.company.local` 미등재 → caddy 를 localhost 로 접근)
- Runner: AI
- Scenario: `unit/feature-0016-metadata-graph/src/scenario.hop-budget.json` (+ 반복 조작은 인라인 시나리오)
- Evidence: `artifacts/feature-0016-neighbor-depth-budget/pb0008/` 4장
  - `step_06_20260728_160620.png` — 도움말 모달에 갱신 문구 렌더("이웃 깊이는 더블클릭·중심 보기에 적용되며, 2단계 이상은 참조·사용 관계만 따라갑니다(단일클릭 상세는 항상 1단계)")
  - `step_06_20260728_161104.png` — `FH_CHAR` 1-hop 상세: "사용하는 함수·프로시저 (155) · 읽기 80 · 쓰기 75", 배너 0
  - `step_08_20260728_161117.png` — 3-hop 확장 후: 배너가 **패널 상단 1개**, 함수·프로시저 섹션 배너 0
  - `step_03_20260728_161311.png` — 문구 중복("이웃 이웃") 수정 후 재확인

#### 4. 결과 (Pass/Fail)

| # | 항목 | 결과 |
|---|---|---|
| a | 그래프 뷰 정상 로드(데이터소스 개요 → 스키마 그래프) | PASS |
| b | depth select `label[title]`·`aria-label` 새 문구 렌더 | PASS |
| c | depth 변경 상태줄이 실제 트리거 명시("더블클릭(또는 우클릭 → '이 노드 중심으로 보기')하면") | PASS |
| d | 도움말 모달 갱신 문구 렌더 | PASS |
| e | `FH_CHAR` 1-hop 상세 — 함수·프로시저 155건 표시 + 배너 0 | PASS |
| f | 3-hop 확장 후 — 배너가 패널 상단 1개("⚠ 3-hop 확장 이웃 135개+ 생략 · 아래 직접 연결 목록은 전량") | PASS |
| g | **함수·프로시저 섹션에 배너 없음**(오귀속 해소) + 목록 155건 불변 | PASS |
| h | 3-hop 확장이 실제 그래프를 확장(fhgame1 프로시저 연결 렌더) | PASS |
| i | pageerror 0 | PASS |

#### 5. Notes / 한계 (정직 기록)

- **커밋 전 검증 방식**: 배포 이미지 컨테이너(web-a/web-b)에 worktree 자산을 임시 주입 → 검증 → `up -d --force-recreate --no-build` 로 배포 이미지 상태 원복(잔재 grep 0 확인). 검증 중 **다른 세션의 배포로 컨테이너가 1회 재생성**되어(16:00, 이미지 `b6882c7d`) 주입이 무효화된 사건이 있었고, 재주입 후 다시 수행했다. 첫 시도의 "구 문구" 관측은 이 재생성 때문이며 코드 결함이 아니다.
- **자산 스탬프**: 소스는 `?v=dev` placeholder 이고 이미지가 빌드 시 스탬프를 주입하므로, 주입 시 컨테이너 스탬프로 치환해 모듈 import URL 일관성을 유지했다(혼재 시 ES 모듈 중복 인스턴스 위험).
- **캔버스 노드 직접 클릭은 미사용**: PixiJS 캔버스에 합성 PointerEvent 를 24~63점 그리드로 시도했으나 노드 상세를 열지 못했다. 대신 검색 결과 목록의 `li.amgr-searchres[data-goto]` 를 클릭하는 **DOM 경로**로 상세를 열었다(PB-0008 레시피 보강 — 노드 상세 검증에는 이 경로가 안정적).
- **미재현**: hop 1 절단 분기 문구("직접 이웃이 조회 상한 초과 — 아래 목록도 일부만")는 대형 스키마 노드(테이블 700개 등)에서 발생하는데, 본 Run 에서는 해당 노드를 열지 않아 **헤드리스 유닛 검증(⑱)에 머문다**.
- `make test` 15건 실패는 main(`2451a1a7`)에서 동일 15건이 실패함을 별도 실행으로 실증한 환경성 baseline(attachment 13 + runtime_settings 2) — 본 변경 무관.

---

### 사후 갱신 (2026-07-28, 세션 이월 후) — 재-rebase + §18.8 적대검증 흡수

위 PB-0008 Run 은 **재-rebase·적대검증 흡수 이전 코드**에서 수행됐다(원 세션 16:06~16:13, 이후 사용량
한도로 중단). 이어받은 세션에서 (a) `origin/main` 10커밋 재-rebase (b) codex 적대검증 4라운드 지적 12건
흡수를 수행했고, 자동 검증은 전량 재실행했다 — pytest 전 스위트 **2809 passed / 0 failed**, 그래프 헤드리스
전 스위트 **865 PASS / 0 FAIL**(`test_detail_dbgroups.js` 95 → 107), ruff clean.

절단 배너 귀속(위 ④ 오귀속 해소)의 렌더 경로는 변하지 않았고 헤드리스 계약이 유지되지만, **'확장할 관계
없음' 힌트의 판정 근거가 바뀌었으므로**(응답 엣지 → 백엔드 hop 실적 `expanded_hops`/`expanded_hop_edges`)
실화면 확인은 배포 후 POST-DEPLOY Run 으로 보완한다. verdict 는 자동검증 기준 PASS 를 유지하되, 위 Run 이
가리키는 코드 상태와 배포본이 다르다는 사실을 여기에 명시해 둔다.
