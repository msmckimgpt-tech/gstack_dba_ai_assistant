---
run_at: 2026-07-28T12:05:30+09:00
session: ai/claude/feature-0003-graph-label-hover-expand
scope: 그래프 뷰 — 잘린 노드 라벨 hover 확장 카드(graph-label-hover-expand)
verdict: PASS (PRE-COMMIT 단위·정적 + POST-DEPLOY PB-0008 라이브)
---

### Run — 확장 기하·hover 수명주기 순수 로직 (Environment: node vm)
- `node --check --input-type=module unit/feature-0003-agent-web-ui/src/static/graph/graph-renderer-pixi.js` PASS.
- `node unit/feature-0003-agent-web-ui/tests/headless/test_pixi_adapter.js` → **180 PASS / 0 FAIL**
  (baseline 112 회귀 0 + 신규 T26 68-assert).
- T26 커버리지:
  - `hoverExpandGeom` — 확장 기하(중심 고정 좌우 대칭·시작 폭=원 칩·목표 폭=전체 라벨+원 여백)·상한 클램프(capped)·
    텍스트 가용폭 보간 구간 `[inner0=원 labelMaxWidth → inner1=종단 안쪽 폭]`·`pad` 하한 8px·
    확장 불필요 전 케이스 null(이미 다 보임 / minGain 미만 / 라벨 없음 / labelMaxWidth 미설정 / 우측 라벨(컬럼) /
    circle / combo / 폭 측정 실패) · 루틴 칩(labelMaxWidth 176 > 칩 폭 150) 역-팝 회귀.
  - `hoverCardHit` / `clampCardCenterX` / `_clampCardX` — 확장 영역 hover 유지, 뷰포트 좌·우 클램프,
    뷰포트보다 넓은 카드 좌측 정렬, 미니맵 세로 겹침 시 우측 경계 축소, 뷰포트 미확정(0) 폴백.
  - `_fitText` — 폭 증가에 따른 글자 순차 노출(단조)·전체 문자열 기준 재계산.
  - `_setLabelHover` / `_probeHover` / `_cancelHoverProbe` / `_revalidateHover` — 대상 변화 시에만 재구성(dedupe),
    잘리지 않은 노드는 카드 미생성, 불필요 렌더 억제(render-on-demand 보존), cat-bg·미니맵 제외,
    `hitTestCombo` 미호출(매 pointermove O(combos×nodes) 회피), 눌림 중 무동작·해제 후 복귀,
    pointerleave 시 대기 프로브 무효화, 카메라 변화 재판정.
  - `_clearLabelHoverVisual` / `_tweenCard` / `_destroyCard` — 카드 1장·축소 카드 1장 불변식, rAF 부재 종단 즉시 적용,
    축소 카드만 정리해도 렌더 유발(유령 카드 방지), `_clearLabelHover` 전체 초기화.
  - `_nodeFillAlpha` — running desaturate(0.45) 공유, state config 우선, 비-running style 존중.
  - `_pick` tier0 — 확장 카드 위 클릭/우클릭/드래그의 원 노드 라우팅 + 카드 없을 때 종전 동작 보존.
### Run — 그래프 headless 전 스위트 회귀 (Environment: node vm, origin/main 리베이스 후)
- 7모듈 sed 번들(`graph-state·util·roleviz·simgroups·rellayout·core·ctxmenu`, `import`/`export`/중복 `const G6` 제거)
  + adapter 기본 경로로 15 스위트 재실행 → **441 PASS / 0 FAIL** · `test_pixi_adapter` 180 포함 **총 621 PASS / 0 FAIL**.
  (edge_visibility 73 · detail_dbgroups 78 · minimap_reuse 65 · edge_flow 48 · category 26 · colnav 22 · collod 20 ·
   layoutmemo 19 · vpack 19 · reveal 17 · simgroups_p2 16 · cullrefkeep 15 · detail_colsel 9 · agglod 8 · viewportcull 6.)
- 본 cycle 은 `origin/main` 27 커밋 뒤처진 base 에서 착수 → 커밋 후 `git rebase origin/main`. **코드 충돌 0**
  (같은 시각 landed 된 `graph-edge-flow`(§83)가 같은 파일의 `PixiAdapterPure`·`_paintEdge` 를 건드렸으나 auto-merge),
  충돌은 append-only 문서 4종(FUNCTION/MODIFY/REVIEW/TASK)의 인접 append 뿐 — 양측 보존으로 해소(§16.4).
  리베이스 후 위 621 PASS 로 병합 결과의 의미적 정합까지 재확인.

- 레이아웃 불변식(기계적 확인): scene 모델(`node.style.size`/`x`/`y`)·`_built`·`buildHitGrid` 입력 무변경 →
  masonry/shelf-pack 재배치·combo bbox·미니맵·hit-grid 산출이 전부 종전과 동일(reflow 0). 확장은 `_labelHoverLayer`
  (world 자식, `zIndex=99998`, `eventMode="none"`) 오버레이 전용.

### Run — §18.8 적대 검증 (Environment: CLI, codex review --uncommitted)
- 9 라운드 반복(적발 → 수정 → 재검증). **P1 3건 · P2 8건 수정**, 최종 라운드 "No discrete correctness issues were identified."
- 상세·판정 근거는 `REVIEW.md` `REV-20260728T120530-graph-label-hover-expand [CODEX:graph-label-hover-expand]`.

### Run — Environment: Windows-browser (PB-0008) — **POST-DEPLOY PASS**
- **PRE-COMMIT 미수행 사유(기록 보존)**: 사용자 가시 산출물이 PixiJS v8 WebGL 캔버스에 rAF 로 그려지는 확장
  애니메이션이라 headless/jsdom 픽셀 실측이 불가능하고(§16.6 헤드리스 비-정본 조항과 같은 축), 정적 자산은 web
  이미지에 baked 라 머지·배포 전에는 라이브 화면에 존재하지 않는다. → 배포 후 실측(아래).
- **배포**: PR #993 → main `d980ebe4` → `make deploy-web-only` 무중단 롤링(web-a·web-b 모두 `git_commit=d980ebe4`,
  Caddyfile 무변경 no-op, 90s soak 통과). 서빙 자산 확증: `https://localhost/static/graph/graph-renderer-pixi.js?v=1659a75f6c2f`
  (80,232 B) 에 `hoverExpandGeom`·`_labelHoverLayer`·`_probeHover` 존재.
- **방법**: `bin/win-browser.py` relay(실 Windows Chrome **150.0.7871.115**, CDP `172.26.144.1:9223`) →
  `https://localhost/admin` → 지식베이스 > 그래프 뷰 → 데이터소스 `mysql-local` → 스키마 `cc_bonedragon` 펼침
  (테이블 257 · 함수·프로시저 300). 캔버스 615×687. 대상 = 잘려 있던 루틴 칩 `sp_GetCurrentItemUniqueID…`.

| # | 확인 항목 | 결과 |
|---|---|---|
| ① | **잘린 명칭 hover → 전체 노출** | PASS — `sp_GetCurrentItemUniqueID…`(잘림) → **`sp_GetCurrentItemUniqueID_New`**(전체) 렌더. 증적 `evidence/pb0008-graph-label-hover-{before,after}-20260728.png` |
| ② | **부드러운 확장(애니)** | PASS — rAF 프레임별 칩 가로폭 실측: `t=44·87ms → 223px`(hover-intent 대기) · `t=176ms → 216px`(카드 생성, 원 폭에서 시작) · `t=251ms → 297px` · `t=326ms 이후 → 303px 안착`. 단계적 증가 = 즉시 전환이 아닌 트윈 |
| ③ | **다른 노드 위치 불변** | PASS — 동일 상태 전/후 전체 화면 픽셀 diff 의 **유의(>16) 변화 영역이 캔버스의 2.75%(306×38px)** 에 국한, 그 박스 = hover 한 칩 자신. 바로 위 이웃 칩 `sp_GetAuctionMaxIndex`·클러스터 박스·관계선 좌표 전부 동일 |
| ④ | **z-order** | PASS — 확장분이 클러스터 경계선·점선 관계선 **위**에 그려짐(after 캡처에서 확장 영역이 배경 선을 덮음) |
| ⑤ | **확장 영역 클릭 라우팅(`_pick` tier0)** | PASS — 대조 실험: 같은 좌표(canvas 330,489) 클릭이 **hover 전** = `클러스터: cc_bonedragon`(combo 폴백) / **hover 확장 후** = `상세: sp_GetCurrentItemUniqueID_New`(원 노드). 드러난 영역이 캔버스·이웃으로 새지 않음 |
| ⑥ | **이탈 시 원복(잔상 0)** | PASS — 커서 이탈 후 화면이 hover 이전과 **픽셀 동치**(유의 diff `None`, 최대 채널차 1/255 = AA 노이즈) |
| ⑦ | **잘리지 않은 칩은 무반응** | PASS — 스키마 카드 `cc_bonedragon`(12자, 미잘림) hover 시 화면 변화 0 |
| ⑧ | **pageerror** | PASS — `error`/`unhandledrejection` 리스너 수집 결과 **0건** |

- 원본 캡처·전수 프레임 로그: `artifacts/feature-0003-graph-label-hover-expand/`.
