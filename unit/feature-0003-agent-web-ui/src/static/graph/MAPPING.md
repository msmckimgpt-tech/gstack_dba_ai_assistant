# ITEM-09 그래프 분리 매핑 v2 (외부 브랜치 hunk 재적용용)

feature-0016 그래프 브랜치(edge-opacity·graph-simcombo 등)가 **구 admin.js 그래프 구간**
좌표의 hunk 를 갖고 있으면 아래 매핑 체인으로 재적용한다. batch1(admin.js→graph.js)과
batch3(graph.js→7모듈) 모두 **pure mechanical move** — 함수 본문·이름·순서 불변이므로
hunk anchor 는 언제나 **함수명 grep** 이 정본이다:

```
grep -rn "function _metaXxx" unit/feature-0003-agent-web-ui/src/static/graph/
```

## 좌표 체인 (batch1 → batch3)
1. **batch1(2026-07-12, PR #738)**: admin.js 라인 3618~9024(5,407줄) → 구 graph.js 라인 `N - 3618 + 6`.
2. **batch3(2026-07-12)**: 구 graph.js(5,416줄)가 7모듈로 섹션-연속 분할. 구 graph.js 라인 → 모듈:

| 구 graph.js 라인 | 모듈 | 내용 |
|---|---|---|
| 7~168 | `graph-state.js` | `_metaGraph` 상태 객체 + 결정론적 배치 상수(`_MET*`) + `_metaNatSort` |
| 169~569 | `graph-roleviz.js` | node-role-viz: 역할 분류 칩·아이콘·범례(`_META_ROLE`·`_metaRole*`) |
| 570~630 | `graph-util.js` | graph-perf-bg 논블로킹 유틸 |
| 631~785 | `graph-rellayout.js` | 관계 기반 배치 pre-pass(barycenter seriation) |
| 786~1027 | `graph-simgroups.js` | 유사 속성 그룹(affix family) |
| 1028~3191 | `graph-core.js` | init·load·`_metaG6Build/Apply`·LOD·anim·미니맵·검색 input 배선 |
| 3192~5414 | `graph-ctxmenu.js` | 우클릭 상호작용·상세/관계 패널·검색 엔진(`_metaCtx`·`_metaGraphCtx*`·`_metaGraphShow*`·`_metaGraphSearch`·`_metaRelevance`) |
| 1~6, 5415~5416 | `graph.js` (barrel) | 헤더·import/export — barrel 이 공개 4심볼 re-export 로 대체 |

모듈 내 오프셋 = (구 graph.js 라인 − 구간시작 + 모듈헤더줄수 + 1). 헤더 줄수가 모듈마다
달라(주석 3 + import 0~5 + G6 bridge 0~1 + 공백 1) **라인 산술보다 함수명 grep 을 쓸 것**.

## 경계 계약(불변)
- **admin.js ↔ graph 공개 표면**: admin.js 는 `graph/graph.js`(barrel)만 import —
  `_metaShowGraph`·`_metaGraphLoadRoots`(graph-core), `_metaRoleLegendTips`(graph-roleviz),
  `_metaGraph`(graph-state)를 barrel 이 re-export. **barrel 경로·심볼 변경 금지.**
- **graph → admin import**: `adminState`·`apiFetch`·`can`·`showToast`(모듈별 필요분만).
  batch1 의 `_metaSubmitForm` import 는 **죽은 import 로 판명(실사용 0)** — batch3 에서 제거.
- **모듈 간 import**: 각 모듈 상단 `import {...} from "./graph-xxx.js?v=dev"` — census
  마스킹 참조 기준 기계 산출. 순환 import(ES live-binding + hoisted 함수 + 호출시점 사용) 안전.
- **상태**: 전 상태변수 const(재할당 0) — cross-module 은 프로퍼티 변이만(`_metaGraph.*`).
  신규 상태를 재할당(let) 로 추가하지 말 것(cross-module 재할당은 ES import 로 불가능).
- **`?v=dev` placeholder**: HTML·ES import specifier 의 스탬프는 소스에서 `?v=dev` 고정 —
  빌드가 content-hash 주입(`scripts/inject_asset_stamp.py`, §13.1 v3.35.1). **수기 bump 금지.**
- **G6/mermaid**: UMD 전역 bridge(`const G6 = window.G6;`)를 필요 모듈 상단에 개별 선언.

## CSS 매핑 (batch2)
- styles.css 구 라인 **8246~8682**(437줄, 그래프 밴드) → `graph/graph.css`(헤더 4줄 뒤,
  구 라인 `N - 8246 + 5`). admin.html 에만 link(`graph.css?v=dev`).
- **예외(공유 잔류)**: 구 8601 `.admin-meta-ai-btn` 크기 규칙(metadata pane AI 자동완성 공용)과
  `.admin-meta-scope-select` 베이스(구 8142~8148, 원래 밴드 밖)는 styles.css 잔류.

## edge-opacity 브랜치 구체 재적용(미머지 origin/ai/root/feature-0016-edge-opacity)
- hunk1: `_META_DIM_OPACITY` 뒤 `_META_EDGE_DIM_OPACITY = 0.12` 상수 추가 →
  **`graph-state.js`** 의 `_META_DIM_OPACITY` 정의부(grep) 뒤에 삽입. 새 상수를
  `_metaG6Build` 가 쓰므로 graph-state.js `export` 목록과 graph-core.js `import` 에 추가.
- hunk2: `_metaG6Build()` 내 edge-style `dimIf` closure(0.12→상수 + lit-edge opacity=1) →
  **`graph-core.js`** `function _metaG6Build`(L39 부근, grep 정본) 내 동일 위치.

## graph-simcombo worktree 미커밋 diff
- patch 보존: `artifacts/worktree-triage/graph-simcombo-uncommitted-20260712.patch` (+TRIAGE.md).
- §43 sim-group 작업은 main 의 §50/ADR-020 group-interact 가 반대 아키텍처로 대체 —
  재적용 전 의미 대조 필수(맹목 재적용 = 회귀). hunk 앵커는 함수명 grep(위 체인).
