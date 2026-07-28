---
run_at: 2026-07-28T16:28:44+0900
session: ai/claude/feature-0003-hover-rw-edgeflow
scope: unit/feature-0003-agent-web-ui/src/static/graph (graph-renderer-pixi·graph-core·graph-ctxmenu)
verdict: PASS
---

### Run (2026-07-28) — detail-hover-flow: 상세 패널 hover 강조의 (방향·읽기/쓰기) 관계선 특정 + 데이터 흐름 애니메이션 — **Environment: Windows-browser (라이브 2축 PASS)**

#### 1. 헤드리스 격리검증 (Environment: CLI — 계약 잠금)

- 신규 `tests/headless/test_graph_hover_flow.js` **41 PASS / 0 FAIL**
  (번들 인자 = graph 7모듈 sed 연결 레시피, adapter 는 기본 경로):
  - **P. 위상 대시(PixiAdapterPure.dashPolyline phase)** — 위상 미지정=종전 동작 · 한 주기/음수 위상 정규화 ·
    위상 이동 시 선두 대시 절단 및 반주기 이동 · 잉크 총량 보존 · 곡선 폴리라인에서도 주기 동치(§83 A7 연속성 유지).
  - **F. 흐름 방향 어휘(flowForward)** — 쓰기(endArrow)=선언 방향 · 읽기(startArrow)=역류 ·
    무향/양방향/style 부재=선언 방향 폴백.
  - **M. 관계선 특정(_edgeMatchBetween)** — 방향(1순위) > relation_type(2순위) 순위 · 왕복 REFERENCES 에서
    역방향 엣지를 배열 앞에 두어도 (a,b) 조회가 정방향을 고름 · **두 행의 world 호가 서로 반대편**(사용자
    리포트의 직접 회귀 가드) · ROUTINE_USES 읽기/쓰기 분기 · relation_type 부재 read 폴백 ·
    역방향 정규화(곡률 부호 반전 + 화살표 키 교환) · `_edgeStyleBetween` A10 계약 호환.
  - **D/R. 패널 행 계약(graph-ctxmenu)** — 행이 모델 엣지 (source,target)[+relation_type] 을 싣고,
    참조받음 행은 **상대→self** 방향으로 전달 · 구 마크업은 레거시 `[self,상대]` 쌍 폴백.
  - **C. 해소 계약(graph-core `_metaGraphSetHoverHighlight`)** — `{source,target,relType}` 전달 ·
    방향 보존 · 레거시 배열 수용 · 양끝 미해소 시 강조 해제.
- **적대 검증(테스트가 실제 회귀를 포착하는가)**: 동일 시나리오를 `main` 시점 어댑터로 대조 실행 —
  `OLD: 참조함 호 cy = 26.0 | 참조받음 호 cy = 26.0 → 같은 호(버그)` ·
  `OLD: 읽기 화살표 {s:true,e:false} | 쓰기 화살표 {s:true,e:false} → 같은 선(버그)` vs
  `NEW: -26.0 | 26.0 → 반대편 호` · `NEW: 읽기 {s:true} | 쓰기 {e:true} → 다른 선`.
  두 축 모두 OLD 에서 실패 재현 → M 섹션이 회귀를 실제로 잡는다.
- **회귀 0**: 그래프 전 스위트 **733 PASS / 0 FAIL**
  (pixi_adapter 190 · detail_dbgroups 78 · edge_visibility 73 · edge_flow 73 · **hover_flow 41(신설)** ·
  catcluster_panel_scroll 36 · category 26 · colnav 22 · collod 20 · vpack 19 · layoutmemo 19 ·
  reveal 17 · simgroups_p2 16 · cullrefkeep 15 · detail_colsel 9 · agglod 8 · viewportcull 6).
- `node --input-type=module --check` 3모듈 PASS. **Python 변경 0건** → pytest/ruff 해당 없음(PR CI 가 재확인).

#### 2. 라이브 시각검증 (Environment: Windows-browser)

- **브리지**: relay @ `http://172.26.144.1:9223` (`bin/win-browser.py doctor` → `"ok": true`,
  실 Windows Chrome **150.0.7871.115**).
- **대상**: §13.2.9 격리 경로 — 라이브 `web-a`/`web-b` 를 건드리지 않고 동일 이미지
  `mysql-ai-web:b6882c7d` 로 **전용 컨테이너 `web-hoverflow-test`(:18097)** 를 띄우고 변경 3모듈을
  `docker cp` 주입(자산 스탬프 `?v=dev` → `?v=28b8c65898a7` 정규화로 ES 모듈 이중 인스턴스화 회피).
  검증 종료 후 컨테이너 제거(공유 트리·라이브 서비스 무접촉).
- **드라이버 주의(마찰 기록)**: `win-browser.py` 는 `ctx.pages[0]` 를 잡는데 이 호스트의 Chrome 은
  병렬 세션과 공유돼 인덱스 0 이 수시로 다른 탭이 된다(goto 직후 eval 에서 origin 이 바뀌는 것을 실측).
  같은 브리지·같은 실 브라우저를 쓰되 **대상 탭을 URL 로 핀 고정**하는 최소 변형 드라이버로 구동했다.
- **시나리오**: 로그인 → 관리 콘솔 → 그래프 뷰 → 데이터소스 `mssql-qa-idc` → 검색 `AchievementQuest`
  → 테이블 선택 → `🕸 그래프에 펼치기`(노드 300 · 관계 303) → `AchievementID` 컬럼 캐럿 펼침
  (참조함 2 · 참조받음 1) → 각 행 hover.
- **PASS 확인 — ① 방향/종류별로 다른 관계선이 강조된다**:
  - **참조함(→)** `AchievementQuest.AchievementID → Achievement.UniqueID` hover 시 화살촉이 **상대(Achievement) 끝**.
  - **참조받음(←)** `Achievement.UniqueID → AchievementQuest.AchievementID` hover 시 화살촉이 **self(AchievementQuest) 끝**.
  - 두 강조의 캔버스 픽셀 차 **441px**(동일 캔버스, 같은 카메라) — 종전에는 두 행이 같은 선을 그렸다.
  - **읽기/쓰기**: `spGetAchievementQuest`(읽기) 는 테이블→루틴, `spDeleteAchievementQuest`(쓰기) 는
    루틴→테이블로 화살촉이 반대이며 강조선 자체가 다른 대상(픽셀 차 3,517px).
- **PASS 확인 — ② 데이터 흐름 애니메이션**: 같은 hover 를 유지한 채 420ms 간격 2프레임을 캡처하면
  흰 대시가 도착점 쪽으로 이동(픽셀 차 **151px**). 정지 상태(hover 없음) 대비 강조 발생은 6,646px.
- **콘솔**: 전 과정 페이지 에러 0.
- **증거**: `artifacts/shared/win-browser-shots-hoverflow/`
  `c60_base_out_in.png`(무hover | 참조함 | 참조받음 3분할 6× 확대) ·
  `c61_flow_frames.png`(같은 hover 420ms 2프레임 — 대시 진행) ·
  `c70_rt_write_vs_read.png`(쓰기 | 읽기 화살촉 반대) · 원본 `40_fit_base.png` ~ `51_rt_read.png`.

#### 3. 성능 관점

- 흐름 rAF 는 **hover 중에만** 돌고(보통 강조선 1개), 프레임마다 재페인트하는 것은 대시 Graphics 뿐이다
  (헤일로·본선·화살촉·노드 링은 정적 1회). `prefers-reduced-motion` 이면 rAF 를 아예 걸지 않고 정적 대시만 남긴다.
- 정지 경로 3중: hover 해제(`clearHoverHighlight`) · 새 hover 선점(`setHoverHighlight` 진입 즉시) ·
  모델 재빌드(`draw()`) · `destroy()`. 세대 토큰(`this._hoverFlow !== state`)으로 이미 예약된 프레임도 자진 종료.
- 오버레이 Graphics 는 detach 가 아니라 **파기**(`_clearHoverLayer`) — hover 는 행마다 발생해 detach 만 하면
  GPU 지오메트리가 누적된다(`_paintEdge` 자식 정리와 동일 어휘).
- 강조선 굵기·화살촉·대시 주기·속도는 모두 **화면 픽셀 기준**(`1/zoom`) — §85 정책과 정합(종전 model 고정
  3.5px 는 줌인에서 리본, 줌아웃에서 실종).
