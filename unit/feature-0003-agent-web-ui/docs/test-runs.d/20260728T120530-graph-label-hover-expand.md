---
run_at: 2026-07-28T12:05:30+09:00
session: ai/claude/feature-0003-graph-label-hover-expand
scope: 그래프 뷰 — 잘린 노드 라벨 hover 확장 카드(graph-label-hover-expand)
verdict: PASS (PRE-COMMIT 단위·정적) / POST-DEPLOY PB-0008 잔여
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

### Run — Environment: Windows-browser (PB-0008) — **PRE-COMMIT 미수행 사유 + POST-DEPLOY 잔여**
- **미수행 사유(PRE-COMMIT)**: 본 변경의 사용자 가시 산출물은 **PixiJS v8 WebGL 캔버스에 rAF 로 그려지는 확장
  애니메이션**이다. 캔버스 내부 렌더는 DOM 이 아니라 headless/jsdom 으로 픽셀 실측이 불가능하고
  (§16.6 「렌더-성능/애니메이션 검증」의 헤드리스 rAF 비-정본 조항과 동일 축), 정적 자산은 web 이미지에 baked 라
  머지·배포 전에는 라이브 화면에 존재하지 않는다. 따라서 PRE-COMMIT 은 정적·단위·적대 리뷰로 de-risk 하고,
  실화면 검증은 배포 후 PB-0008 로 수행한다(`visual_verification_scope: always`, `deploy_scope: included`).
- **POST-DEPLOY 검증 계획(잔여)**: `bin/win-browser.py` relay → 실 Windows Chrome `https://localhost/admin` 로그인 →
  메타데이터 > 그래프 뷰 → 이름이 긴 테이블 칩(예 `cc_user_subscription`) hover.
  확인 항목: ① 칩이 부드럽게 좌우로 넓어지며 잘린 뒷글자가 드러남 ② **이웃 노드·클러스터 위치 불변**(확장 전/후
  스크린샷 대조) ③ 확장분이 이웃 칩·클러스터 배경 **위**에 그려짐(z-order) ④ 드러난 영역 클릭 시 그 노드가 선택,
  우클릭 시 그 노드 메뉴 ⑤ 이탈 시 원 폭으로 축소 후 소멸(잔상 0) ⑥ 잘리지 않은 짧은 이름 칩은 무반응
  ⑦ pageerror 0. 스크린샷은 `docs/evidence/` 에 첨부.
