# ITEM-09 그래프 분리 매핑 (외부 브랜치 hunk 재적용용)

feature-0016 그래프 브랜치(edge-opacity·graph-simcombo 등)가 admin.js 그래프 구간을
수정 중이면, 그 hunk 를 아래 매핑으로 `graph/graph.js` 에 재적용한다. **pure mechanical
move** 이므로 함수 본문·이름·순서 불변 — hunk anchor 가 함수명으로 보존된다.

## 이동 규칙
- admin.js **라인 3618~9024**(5,407줄: feature-0016 그래프 뷰 주석 ~ `_metaFormValues` 직전)이
  통째로 `graph/graph.js` 로 이동.
- `graph/graph.js` 오프셋: admin.js 원본 라인 `N` → graph.js 라인 **`N - 3618 + 6`**
  (graph.js 상단 6줄 = 배너 주석 3 + `import {...core}` 1 + `const G6 = window.G6;` 1 + 공백 1).
- 함수 재적용은 라인 아닌 **함수명으로 anchor**: `git diff` hunk 의 `@@ ... function _metaXxx` 를
  graph.js 에서 `grep -n "function _metaXxx" graph/graph.js` 로 찾아 적용.

## 경계 계약(불변)
- **import surface(admin.js→graph.js)**: `adminState`, `apiFetch`, `can`, `showToast`,
  `_metaSubmitForm`(admin.js `export`) + `window.G6`(bare `G6` bridge, graph.js 상단).
- **export surface(graph.js→admin.js)**: `_metaShowGraph`, `_metaGraphLoadRoots`,
  `_metaRoleLegendTips`, `_metaGraph`(admin.js tab-switch 소비).
- admin.js 는 `type="module"`, `const mermaid = window.mermaid;` bridge. 순환 import(admin↔graph)는
  ES live-binding — 그래프 함수는 호출 시점(런타임) core 사용이라 초기화 안전.

## edge-opacity 브랜치 구체 재적용(미머지 origin/ai/root/feature-0016-edge-opacity)
- hunk1: `_META_DIM_OPACITY` 뒤 `_META_EDGE_DIM_OPACITY = 0.12` 상수 추가 → graph.js 의
  `_META_DIM_OPACITY` 정의부(grep) 뒤에 삽입.
- hunk2: `_metaG6Build()` 내 edge-style `dimIf` closure(0.12→상수 + lit-edge opacity=1) →
  graph.js `function _metaG6Build` 내 동일 위치.
