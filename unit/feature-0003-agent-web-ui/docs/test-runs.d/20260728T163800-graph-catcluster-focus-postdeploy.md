---
run_at: 2026-07-28T16:38:00+09:00
session: ai/claude/feature-0016-catcluster-focus-postverify
scope: 접힌 카테고리 클러스터 하위 테이블 추적 카메라 승격 — POST-DEPLOY 라이브 재확인 (graph-catcluster-focus)
verdict: PASS
---

# Run — PB-0008 POST-DEPLOY 라이브 재확인 (Environment: Windows-browser)

- 대상: PR #1013 머지(main `f25c71bf`) + `make deploy-web` 무중단 전체 롤아웃(web 롤링 + 워커 +
  gateway reconcile, **soak 90s 통과**) 이후의 **main 기반 서빙본**.
- **왜 다시 보는가**: 사전 검증은 §13.2.9 격리 컨테이너에서 했고, 그 이미지는 worktree 자산을
  `docker cp` + 재스탬프한 것이라 **빌드 파이프라인(Dockerfile COPY → inject_asset_stamp)을 통과한
  산출물이 아니다**. main 기반 이미지가 실제로 같은 코드를 서빙하는지는 별도 사실이므로 배포 후
  1회 재확인한다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).
- Runner: AI (`bin/win-browser.py` relay) · Chrome/150.0.7871.115 · 대상 URL `https://localhost/admin`
  (라이브 Caddy 경유 서빙본).
- **서빙 baked 2중 확인**: `admin.js?v=bff996bf90f7` · 서빙 `graph-core.js` 에 신규 심볼
  (`_metaGroupElementFor`/`_metaCategoryElementFor`/`_metaAncestorKindKo`) **7건** ·
  `graph-ctxmenu.js` **3건** · `repo-web-a-1` `GIT_COMMIT=f25c71bf`.
- 대상: `mssql-web-qa` / `masangsoftweb` — 컨텐츠 카테고리 `이벤트 아이템 지급`(멤버 40) ·
  테이블 `L_DK_EVENT_ITEM_GIVE_160707_RETURN_ITEM` · 제품 카테고리 `PC:117 국내 웹 - QA`.

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 컨텐츠 카테고리 접힘 → `🎯 이 노드로 이동` | 대상 블록 거리 **1189 → 3px** 정착 · 스키마 클러스터 중앙 거리 **40 → 1148px** 이탈 **PASS** |
| 2 | 상태줄 | `→ '…' 의 컨텐츠 카테고리로 카메라 이동 (그 클러스터를 펼치거나 확대·검색으로 하위 노드를 직접 탐색할 수 있습니다).` **PASS** |
| 3 | 제품 카테고리 밴드 접힘 | 스키마 클러스터 통째 미방출 상태에서 밴드 **2px** 정착 · 상태줄 `… 의 제품 카테고리로 카메라 이동` **PASS** |
| 4 | 회귀(전부 펼침) | 테이블 자신 **2px** 정착 · 승격 문구 없는 기존 상태줄 **PASS** |
| 5 | 콘솔 | `pageerror` / `console.error` **0건** |

- 사전 Run(격리 컨테이너, stamp `6f2cb7201d93`)과 **수치·문구가 전건 동일** — 빌드 파이프라인을 통과한
  산출물에서도 같은 코드가 서빙됨을 실증한다.
- Evidence(스크린샷 4매): `artifacts/shared/win-browser-shots-catcluster-focus-postdeploy/`
  (`01_before_focus.png` · `02_group_collapsed_focused.png` · `03_catband_collapsed_focused.png` ·
  `04_all_expanded_table_focused.png`)
- 정리: 라이브 조작은 **읽기·카메라 전용**(접기/펼치기는 세션 로컬 상태, 서버 mutation 0) ·
  드라이버 탭만 사용하고 다른 세션 탭 무접촉 · 자산 주입 없음(서빙본 그대로 관측).
- 한계(정직 표기): 사전 Run 과 동일하게 `_metaGraphPanToRelation`(관계 행 단일 클릭)·hover-pan 은
  직접 호출하지 않았다 — 동일 `_metaRenderedAncestorFor` 를 공유하며 시나리오 1·3 이 그 해소 결과를
  라이브 렌더 상태에서 단정한다. 컨텐츠 카테고리 접기는 GX 좌표 합성 클릭이 아니라 동일 상태 경로로 유발했다.
