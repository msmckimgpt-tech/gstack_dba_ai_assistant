---
run_at: 2026-08-13T11:21:00+09:00
session: graph-expand-camera-anim (ai/claude-corp/feature-0016-expand-camera-anim)
scope: 그래프 펼침 시 선택 노드 카메라 추종(keep-in-view) + 노드 재배치 이동 애니메이션 — graph-core / graph-ctxmenu / graph-renderer-pixi
verdict: PARTIAL (코드/문법/헤드리스 회귀·뮤테이션 PASS · **Environment: Windows-browser 라이브 시각검증은 POST-DEPLOY 별도 Run** — 아래 사유)
---

### Run (2026-08-13) — PRE-DEPLOY — **Environment: node --check(ES module) + 헤드리스 격리검증(vm) + 뮤테이션**

- **구문**: `node --check`(ESM 복사본) — `graph-core.js` · `graph-ctxmenu.js` · `graph-renderer-pixi.js` PASS.
- **헤드리스 그래프 전 스위트**(30 파일, 7모듈 sed 번들 + 어댑터): **기준선 1155 PASS / 0 FAIL(착수 전 실측)
  → 1290 PASS / 0 FAIL**. 신규 135건 = `test_pixi_adapter.js` T28(선별)·T29(트윈 수명주기)·T30(hit-test
  정합·배선) + 신규 `test_graph_expand_camera.js`(keep-in-view 순수 판정 · 루프 계약 · 4경로 배선) 57건.
- **뮤테이션으로 포착력 실증** — 각 가드가 그 결함을 실제로 잡는지 소스를 되돌려 확인:

  | 뮤턴트 | FAIL |
  |---|---|
  | keep-in-view 를 항상-중앙정렬로 되돌림 | 10 |
  | 큰 요소 중심 판정 제거 | 3 |
  | 씬 교체 가드 제거 / cap 무음 절단 / 가시영역 필터 제거 | 1 / 1 / 2 |
  | 트윈 출발 위치 되감기 제거(= 애니메이션 실종) | 1 |
  | 종단 오버레이 미해제 / 관계선 예산 가드 제거 | 2 / 1 |
  | 프레임마다 오브젝트 재조회 제거(상태 변경 시 노드 정지) | 2 |
  | grid 에서 이동 노드 미제외 / `_pick` 배선 누락 | 3 / 1 |
  | 드래그가 트윈을 선점하지 않음 / dragstart 미종료 | 2 / 2 |
  | `_boundsOf` 트윈 미반영(카메라가 목적지 추종) | 2 |
  | focus 양보를 즉시 포기로 되돌림 | 2 |
  | 카메라 소유권 세대 가드 제거(양방향 진동 788회 관측) | 2 |
  | 사용자 팬 양보 제거 / reduced-motion 무시 / 관측불가 번들 루프 유지 | 1 / 2 / 2 |
  | `_stopMoveTween` 오브젝트 재조회 제거 | 1 |

- **관련 pytest**(agent 이미지에 worktree 마운트): `test_static_cache_integrity` · `test_metadata_perm_split`
  **46 PASS**.
- 회귀 표면: 백엔드·스키마·권한·응답 shape 0. 평시(트윈 없음) 경로는 hit-test·bounds·관계선 모두
  기존 코드 그대로이며, 그 무회귀를 테스트로 별도 단언했다.

### Environment: Windows-browser — 본 Run 에서 **미수행**, POST-DEPLOY 별도 Run 으로 수행

- **사유(브리지 문제 아님)**: 변경 대상이 ES module JS 라 배포 전 `docker cp` 로는 실측할 수 없다 —
  자산 스탬프가 주입되지 않아 모듈이 이중 인스턴스로 로드되고, 브라우저 모듈 캐시 때문에 서버 파일이
  신버전이어도 구버전이 실행된다(본 저장소 실측 quirk). 따라서 **머지·배포 이후**에만 실화면 검증이
  성립한다. `python3 bin/win-browser.py doctor` 로 브리지 준비 상태를 확인한 뒤 수행한다.
- **POST-DEPLOY 에서 확인할 것**(§16.6 인터랙션 + 렌더-성능 축):
  1. 컬럼 펼치기 — 테이블이 화면 안에 남으면 **카메라 정지**(불필요한 점프 0), 밖으로 밀리면 추종.
  2. 스키마 펼치기 — 종전의 무조건 중앙 점프가 사라졌는지(제자리 유지).
  3. 재배치 애니메이션 — 이동이 **눈에 보이는지**, 관계선이 노드를 따라가는지(캡처 첨부).
  4. 애니메이션 중 클릭·hover 가 **보이는 노드**에 떨어지는지.
  5. **CDP 실-paint 프레임 지표** 또는 host-side 실관측 — 헤드리스 rAF-FPS 는 근거로 쓰지 않는다
     (§16.6 렌더-성능 축 · §16.3 proxy≠ground-truth).
- 이 Run 이 완료되기 전까지 **본 변경의 시각검증은 미충족**이며, 완료로 보고하지 않는다.

### Run (2026-08-13, POST-DEPLOY) — **Environment: Windows-browser (win-browser.py relay, Chrome 150.0.7871.128, 배포 3d3adb4b)**

증적 이미지: `artifacts/pb0008/20260813-graph-expand-camera-anim/{01-before-expand,03-after-column-expand,04-panned-target-at-edge,05-after-collapse-keepinview,06-schema-expand-keepinview}.png`

**배포 전달 확인 (PASS)** — web-a·web-b 모두 `GIT_COMMIT=3d3adb4b`, baked 자산에 신규 코드 실측
(`_metaGraphKeepInView` 5회 · `_startMoveTween` 2 · `isElementAnimating` 1). 배포 창 엣지 무중단 실측
`no upstreams available` **0건**.

**① 애니메이션이 라이브에서 실제로 동작 (PASS — 자기 계측 실측값)** — 신규 관측 필드
`window.__META_GRAPH_PERF.move` 가 라이브에서 값을 낸다:
- 스키마 펼침(재배치): `{items:2, moved:2, skipped:0, reason:"", incident:0}`
- 컬럼 펼침(더 큰 재배치): `{items:12, moved:12, skipped:0, reason:"", incident:5}` — 12노드 트윈 + 관계선 5개 추종
- 카테고리 드릴·데이터소스 드릴·스키마 전환: `{items:0, reason:"scene-switch"}` — **비용 가드가 의도대로
  발동**(새 화면은 애니메이션하지 않는다). 상한 절단(`skipped>0`)은 이 규모에선 발생 안 함.

**② 카메라 — "보이면 움직이지 않는다" (PASS, 픽셀 대조)** — `01` → `03`: `billingsummary` 클릭으로 컬럼
4개가 펼쳐지며 sim-group 박스가 x≈570→793 으로 넓어지고 형제 테이블(`errorlog`·`steambillinglog`)이
x≈426→651 로 **약 225px 이동**했는데, 선택한 `billingsummary` 는 **(426,592) 그대로** — 카메라 이동 0.
재배치가 실제로 일어난 상태에서 AC-1 이 성립함을 화면으로 확인.

**③ 사용자 팬 우선 (PASS)** — `04`: 캔버스를 좌로 540px 팬해 대상을 화면 밖으로 밀어낸 뒤, 카메라가
되돌아오지 않음을 확인(추종이 사용자 조작을 덮지 않는다).

**④ 스키마 펼침 중앙 focus 제거는 회귀였다 (FAIL → 정정)** — `06`: 안전영역 밖 `gunzlogin` 카드를
클릭해 스키마를 펼치자 status 는 "테이블·함수 **9개 펼침**" 인데 화면엔 카드만 남고 **펼쳐진 9개가
화면 밖**이었다. 원인은 설계대로다 — 펼친 combo 가 뷰포트보다 커지고, 큰 요소는 중심 기준 판정이라
"중심이 안전영역 안 = 이동 0". 즉 이 경로에서 기존 중앙 focus 를 keep-in-view 로 바꾼 것이
**요청 범위를 넘은 변경이었고 그것이 회귀를 만들었다**. → 후속 cycle 에서 이 경로만 중앙 focus 로
되돌리고, 회귀 재발을 테스트로 잠갔다(`test_graph_expand_camera.js` D 배선 계약 반전).

**⑤ 프레임 페이싱 (부분 측정 — 단일 짧은 표본)** — 실 Windows Chrome 에서 rAF 간격 실측
**p50=p90=max=16.7ms(= 60fps vsync)**. 단 **연속 5프레임 표본**이다: CDP relay 가 호출 사이에
렌더러를 재우므로 360ms 창 전체를 샘플링할 수 없었다(그 사이 rAF 정지). 따라서 "60fps 로 부드럽다"
를 전체 구간의 성질로 단정하지 않는다 — 측정된 것은 *프레임이 도는 동안의 간격*이다.

**⑥ 중간 프레임 시각 캡처 (미확보 — 한계 명시)** — 위 같은 이유로 트윈 중간 위치가 페인트된
프레임을 캡처하지 못했다(캔버스 잉크 무게중심 샘플 3프레임 전부 정착 후 값). 애니메이션의 *실행*은
①의 자기 계측으로 확인됐고, *체감 부드러움*은 이 Run 에서 측정하지 못했다. 사용자 육안 확인이
남은 유일한 항목이다.

**미검증으로 남긴 것**: (a) 위 ⑥ 중간 프레임 시각 증적 (b) 노드가 재배치로 화면을 벗어나는 경우의
추종을 라이브에서 재현하지 못함 — 그 분기는 헤드리스 계약 테스트(C2·C9)로만 검증됐다. 라이브에서
그 조건을 인위적으로 만들려면 대상이 화면 밖으로 밀리는 대규모 shelf 재배치가 필요하고, 본 세션의
소규모 스키마(테이블 3개)에서는 발생하지 않았다.
