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
