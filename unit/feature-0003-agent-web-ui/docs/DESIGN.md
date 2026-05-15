---
doc_type: DESIGN
feature_id: feature-0003-agent-web-ui
scope: feature
status: active
edit_policy: rewrite
source_of_truth: true
---

# Design — Admin Console UI Contract

본 문서는 관리 콘솔 (`src/static/admin.html` / `src/static/admin.js` / `src/static/styles.css`) 의 카테고리 (Accounts, Roles, Products, 이후 추가될 모든 카테고리) UI 표준 정본이다. project-level 정책은 [`../../../docs/CONVENTIONS.md §10`](../../../docs/CONVENTIONS.md) 을 따른다.

## 1. 적용 범위

본 문서는 admin console (`<body class="admin-shell">`) 의 다음 요소를 다룬다:
- **카테고리 pane** (`section.admin-pane[data-admin-pane]`) — 1 카테고리 1 pane.
- **마스터-디테일 리스트** (`.admin-list-detail` > `.admin-list-col` + `.admin-detail-col`).
- **다중선택 (multi-select) UX** — row checkbox / select-all / bulk toolbar / cross-page banner / confirm dialog / RBAC partial-failure UI.
- **키보드 인터랙션 표준**.

다음은 본 문서 범위 밖이다 (해당 정본 참조):
- chat / conversation UI → `FUNCTION.md` §7.
- system prompt 편집기 → `FUNCTION.md` §11 AC-0007 이후.
- 권한 (RBAC) catalog 자체 → `BRIEFING-c5-permission-product-access.md`.

## 2. DOM anchor 표준 구조

모든 다중선택 카테고리는 동일한 5단 구조를 따른다.

```html
<section class="admin-pane" data-admin-pane="<entity>">
  <header class="admin-pane-head">
    <div>
      <div class="drawer-label">...</div>
      <h2>...</h2>
    </div>
    <div class="admin-pane-head-right">
      <!-- ONLY primary action: "+ 새 <entity>" 또는 비움. 동적 bulk action 금지. -->
    </div>
  </header>

  <div class="admin-list-detail">
    <div class="admin-list-col">
      <div class="admin-list-toolbar">
        <!-- 검색 input + 필터 칩 -->
      </div>

      <div class="admin-list-head">
        <label class="admin-list-select-all">
          <input type="checkbox" id="<entity>SelectAll" aria-label="현재 페이지 전체 선택" />
          <span>전체 선택</span>
        </label>
        <span class="admin-list-count" id="<entity>ListCount"></span>
      </div>

      <!-- ★ cross-page selection banner — Set 이 ≥ 2 페이지에 걸칠 때만 -->
      <div class="admin-bulk-cross-page" id="<entity>CrossPageBanner" role="status" aria-live="polite"></div>

      <div class="admin-list" id="<entity>List"></div>

      <!-- ★ bulk toolbar 표준 위치 (list 직하단 sticky) -->
      <div
        class="admin-bulk-actions"
        id="<entity>BulkBar"
        role="toolbar"
        aria-label="<entity> 일괄 작업"
        aria-live="polite"
      ></div>

      <div class="admin-list-pagination" id="<entity>Pagination"></div>
    </div>

    <div class="admin-detail-col" id="<entity>Detail">
      <div class="admin-detail-empty">좌측에서 <entity>를 선택하세요.</div>
    </div>
  </div>
</section>
```

**불변 규칙:**
- `.admin-pane-head-right` = primary action 전용. 동적 bulk action 슬롯 금지.
- Bulk toolbar = `.admin-bulk-actions` 컨테이너 + `role="toolbar"` + `aria-live="polite"`.
- Cross-page banner = `.admin-bulk-cross-page` + `role="status"` + `aria-live="polite"`. `:empty {display:none}`.

## 3. Visual hierarchy 토큰

다음 CSS custom properties 를 `styles.css` 의 `:root` 에 둔다 (또는 기존 토큰 set 에 통합):

| 토큰 | 값 | 용도 |
|---|---|---|
| `--z-bulk-bar` | `12` | bulk toolbar sticky z-index |
| `--z-bulk-banner` | `11` | cross-page banner z-index |
| `--bulk-bar-bottom-offset` | `0` | sticky bottom 기준점 (pagination 아래 고정) |
| `--bulk-bar-elev` | `0 -2px 8px rgba(0,0,0,.06)` | bulk bar 상단 elevation shadow |

`.admin-bulk-actions:not(:empty)` 일 때만 sticky/shadow 적용.

## 4. 자료구조 contract

```js
adminState = {
  ...
  accountSelected: new Set(),     // Set<number>
  roleSelected: new Set(),         // Set<string>  (role key)
  productSelected: new Set(),      // Set<number>  ★ v0.2 신설 — CONVENTIONS.md §10.1 적용 룰 충족
  ...
};
```

**Invariants (모든 카테고리 공통):**
- I-1. `<entity>Selected` 의 KEY 타입은 entity wire-format 기본형. 한 entity 내에서 통일.
- I-2. 데이터 reload 후: `<entity>Selected ← <entity>Selected ∩ visibleAllIds` (stale entry 자동 제거 — 이미 `admin.js:1753, 1758` 패턴 존재. Products 도 동일 적용).
- I-3. 신규 미저장 row (`_isNew`) 는 multi-select 에서 자동 제외 + checkbox `disabled`.
- I-4. 페이지 이동 시 Set **보존**. 페이지 1·2 합산 선택이 ≥ 2 페이지에 걸치면 `<entity>CrossPageBanner` 노출 (§6 참조).

**Runtime assertion (drift 재발 차단):**

```js
function assertBulkBarContract(entity) {
  const bar = document.getElementById(`${entity}BulkBar`);
  if (!bar) throw new Error(`[contract] #${entity}BulkBar missing`);
  if (bar.getAttribute("role") !== "toolbar") throw new Error(`[contract] #${entity}BulkBar role!=toolbar`);
  if (!bar.hasAttribute("aria-live")) throw new Error(`[contract] #${entity}BulkBar aria-live missing`);
  const parent = bar.parentElement;
  if (!parent.classList.contains("admin-list-col")) {
    throw new Error(`[contract] #${entity}BulkBar must be child of .admin-list-col`);
  }
  const headRight = document.querySelector(`[data-admin-pane="${entity}"] .admin-pane-head-right`);
  if (headRight && headRight.querySelector(".admin-bulk-label")) {
    throw new Error(`[contract] bulk label leaked into .admin-pane-head-right (CONVENTIONS §10.2)`);
  }
}
```

`initialize()` 끝에서 `["accounts","roles","products"].forEach(assertBulkBarContract)` 호출. FAIL 시 console.error + 사용자 toast (`UI 표준 위반: <entity>`). 운영 코드 차단은 하지 않음 (best-effort guard).

## 5. Bulk toolbar 컴포넌트 set

`render<Entity>BulkBar()` 함수가 동일한 컴포넌트 set 을 좌→우 순서로 추가한다:

| 순서 | 요소 | class | 조건 |
|---|---|---|---|
| 1 | `<span class="admin-bulk-label">{N}{단위} 선택됨</span>` | `admin-bulk-label` | 항상 (count ≥ 1) |
| 2 | `<button>활성화 pending</button>` | `tool-btn` | `can("<entity>.activate")` |
| 3 | `<button>비활성화 pending</button>` | `tool-btn` | `can("<entity>.deactivate")` |
| 4 | `<button>삭제 pending</button>` | `tool-btn danger` | `can("<entity>.delete")` |
| 5 | `<button>선택 해제</button>` | `tool-btn` | 항상 (count ≥ 1) — 키보드 hint `Esc` inline 표기 |

**단위 어휘** (CONVENTIONS §10.4):
- 사람 entity (Accounts) → "명"
- 시스템 entity (Roles, Products, Conversations) → "개"

**액션 버튼 hint inline 표기 (Linear pattern 차용):**
- "선택 해제" 버튼은 `<span class="kbd-hint">Esc</span>` 를 라벨 옆에 추가한다.

**Empty / loading / error state 처리:**
- `count === 0` 또는 로딩 중 (`adminState.loading.<entity> === true`) → `bar.innerHTML = ""` + `:empty {display:none}` 으로 자동 숨김.
- 로딩 도중 stale Set 깜빡임 방지: render 함수 진입부에서 `if (adminState.loading.<entity>) return;` 가드.

## 6. Cross-page selection (Stripe pattern)

페이지네이션이 있는 카테고리 (Accounts: `ACCOUNT_PAGE_SIZE=15`) 에서 페이지 1·2 모두 선택 row 가 존재하면 banner 노출:

```
[<entity>CrossPageBanner]
  "현재 페이지: 3명 / 전체: 8명 선택됨. [전체 페이지 선택 해제] [현재 페이지만 보기]"
```

**동작:**
- 페이지 1 에서 row 선택 후 페이지 2 이동 → Set 보존 (I-4).
- 페이지 2 에서 또 선택 → banner 자동 노출.
- "전체 페이지 선택 해제" 버튼 → `<entity>Selected.clear()` → renderList + renderBulkBar + banner 숨김.
- "현재 페이지만 보기" 버튼 → 다른 페이지 선택 entry 만 제거 (현재 페이지 Set 유지).

**Bulk action 시 cross-page 영향:**
- "활성화 pending" 등은 Set 전체 대상. 즉 보이지 않는 페이지의 row 도 적용됨.
- 사용자가 인지하지 못한 채 잘못 적용하는 것을 막기 위해 banner 가 visible 일 때 모든 bulk action 은 `confirmDangerAction()` 게이트를 통과해야 한다 (§7).

## 7. Confirm dialog 컨벤션

기존 `window.confirm()` 단일 패턴을 다음으로 표준화:

```js
function confirmBulkAction({ entity, action, count, danger = false }) {
  const unit = entityUnit(entity);  // "명" or "개"
  const verb = ACTION_LABEL[action]; // "활성화" / "비활성화" / "삭제"
  const summary = `${count}${unit} ${verb}`;
  // count echo: 사용자가 메시지 내 N 을 직접 보고 인지
  if (!danger || count < CONFIRM_TYPED_THRESHOLD) {
    return window.confirm(`${summary} pending 반영. 적용 전에는 되돌릴 수 있습니다. 계속할까요?`);
  }
  // danger + 임계치 이상 → typed confirmation
  const expected = String(count);
  const typed = window.prompt(
    `${summary} pending 반영 — 위험 작업입니다. 확인을 위해 ${expected} 를 정확히 입력하세요:`
  );
  return typed === expected;
}
```

**파라미터:**
- `CONFIRM_TYPED_THRESHOLD = 10` (≥ 10 건의 danger 액션은 typed confirm).
- `ACTION_LABEL` = `{ activate: "활성화", deactivate: "비활성화", delete: "삭제" }`.
- `entityUnit(entity)` = `{ accounts: "명", roles: "개", products: "개" }[entity]`.

**적용 위치:**
- `bulkAccountSetActive`, `bulkAccountDelete`
- `bulkRoleSetActive`, `bulkRoleDelete`
- `bulkProductSetActive`, `bulkProductDelete` (신설)

## 8. RBAC partial-failure UI

bulk action 실행 시 일부 row 가 권한 부족 (`can("<entity>.delete")` 는 통과했으나 row-level 제약 — 예: 자기 자신 삭제, system role 보호) 으로 실패할 수 있다. 다음 표준 처리:

**처리 흐름:**
1. `apply<Entity>BulkAction(action)` 시작 — Set 의 각 row 에 대해 row-level 가능 여부 평가 (예: `canTargetRow(action, row)`).
2. **분할**: `[appliedIds, skippedIds]` 로 분리. `appliedIds` 는 pending 반영.
3. **결과 toast** (`showToast`):
   - `skippedIds.length === 0` → `${count}${unit} ${verb} pending 반영` (기존 메시지).
   - `skippedIds.length > 0` → `${appliedIds.length}${unit} 적용 · ${skippedIds.length}${unit} 권한 부족으로 제외`.
4. **Detail (선택)**: skipped row 의 사유 (예: `자기 자신` / `system role`) 를 dashboard pending 영역 또는 dev-mode 로그에 기록. 본격 별 dialog 노출은 v0.3.

**catalog 변경 없음**: 본 컨벤션은 기존 권한 (`<entity>.activate` 등) 의 row-level check 만 활용한다. 새 권한 추가 = RBAC plan = outside voice 필수 영역이므로 별 cycle 로 분리.

## 9. Keyboard map 표준

| Key | Context | 동작 |
|---|---|---|
| `Click` on row | row 외부 (이름·메타·chips) | detail 선택 (selectAccount / selectRole / selectProduct) |
| `Click` on checkbox | row checkbox | multi-select toggle (`ev.stopPropagation()` 으로 row click 차단) |
| `Shift+Click` on checkbox | row checkbox | 직전 click row 부터 현재 row 까지 range 선택 (visible 범위 내) |
| `Cmd/Ctrl+Click` on checkbox | row checkbox | 단일 toggle (현재 click 동작과 동일 — explicit 명시) |
| `Esc` | admin pane 전체 | `<entity>Selected.clear()` (현재 active pane) |
| `Tab` / `Shift+Tab` | bulk bar 내부 | 표준 focus 순회 (role=toolbar 가 그룹화) |

**Shift-click range 구현 노트:**
- `adminState.<entity>LastClickIdx` 에 직전 click row index 저장.
- shift+click 시 `[lastIdx, currentIdx]` 의 visible row 모두 Set 에 추가.

## 10. Accessibility 표준 (WAI-ARIA)

WAI-ARIA Authoring Practices "Grid with Selection" 패턴을 차용한다.

| 요소 | aria attribute |
|---|---|
| `.admin-list` | `role="grid"` (선택), `aria-multiselectable="true"` (다중선택 카테고리만) |
| `.admin-list-row` | `role="row"` (grid 사용 시) |
| Row checkbox | `aria-label="<entity name> 선택"` |
| `#<entity>SelectAll` | `aria-label="현재 페이지 전체 선택"`, `indeterminate` 정확 반영 |
| `#<entity>BulkBar` | `role="toolbar"`, `aria-label="<entity> 일괄 작업"`, `aria-live="polite"` |
| `#<entity>CrossPageBanner` | `role="status"`, `aria-live="polite"` |
| `.admin-list-count` | `aria-live="polite"` (count 변화 announce) |

**Focus management:**
- bulk action 실행 후 focus 는 trigger 버튼 (예: "활성화 pending") 에서 ↓ 행으로 이동 안 함 (focus 유지).
- "선택 해제" 실행 후 focus 는 `#<entity>SelectAll` 로 이동 (선택 해제 buttom 이 자체 DOM 에서 사라지므로).
- `Esc` 로 선택 해제 시도 시 focus 는 현재 위치 유지 (key handler 가 admin pane 전역).

## 11. 렌더 사이클 contract

각 카테고리는 동일한 렌더 함수 set 을 가진다:

```js
filtered<Entity>s()              // 검색·필터 적용 후 entity 리스트
render<Entity>List()             // .admin-list 갱신, 이후 update<Entity>SelectAllCheckbox + render<Entity>BulkBar + render<Entity>CrossPageBanner 호출
update<Entity>SelectAllCheckbox()// #<entity>SelectAll 의 checked / indeterminate 상태 동기화
render<Entity>BulkBar()          // .admin-bulk-actions 갱신 (§5 컴포넌트 set)
render<Entity>CrossPageBanner()  // .admin-bulk-cross-page 갱신 (§6 banner)
selectEntity(id)                 // detail 선택 (단일)
bulk<Entity>SetActive(active)    // §7 confirm + §8 partial-fail 처리
bulk<Entity>Delete()             // §7 confirm + §8 partial-fail 처리
```

**호출 순서 invariant:**
- row checkbox change → Set.add/delete → `render<Entity>BulkBar` + `update<Entity>SelectAllCheckbox` + `render<Entity>CrossPageBanner`
- select-all change → `visible.forEach(.add or .delete)` → 위와 동일
- "선택 해제" 또는 `Esc` → `<entity>Selected.clear()` → `render<Entity>List()` (내부에서 위 3 함수 호출)
- 데이터 reload 후 (`loadAdminData()` 의 응답 후) → I-2 invariant 적용 → `render<Entity>List()`

## 12. Products 마이그레이션 plan

기존 `selectedProductId: number | null` (단일) ↔ 신규 `productSelected: Set<number>` (다중) 동거 단계:

**Phase A (본 cycle 에 포함):**
- `productSelected: new Set()` 신설 (state).
- admin.html 의 products pane 에 row checkbox + `#productsSelectAll` + `#productsBulkBar` + `#productsCrossPageBanner` 추가 (§2 구조).
- admin.js 의 `renderProductList` / `buildProductRow` 에 row checkbox 추가.
- `renderProductBulkBar` / `updateProductSelectAllCheckbox` / `renderProductCrossPageBanner` 신설.
- `bulkProductSetActive` / `bulkProductDelete` 신설 — §7 confirm + §8 partial-fail.
- **단일 선택 (`selectedProductId`) 흐름 유지** — detail panel 은 계속 단일 product 만 표시. 다중 선택 = bulk action 전용.
- Race 회피: detail panel 은 `selectedProductId` 만 신뢰. row click = detail 선택 (단일), checkbox click = multi-select Set (별 흐름).

**Phase B (별 cycle):**
- detail panel 이 다중 선택 시 "{N}개 제품 일괄 편집" 모드를 제공할지 별 평가. 현재는 단일 detail 만 유지 (overhead 회피).

## 13. 후속 / open questions

- **Q-13.1**: cross-page banner 의 "전체 페이지 선택" 버튼 (현재 페이지 + 보이지 않는 페이지 전부 선택) 추가 여부. 사용자가 명시 요청 시 v0.3.
- **Q-13.2**: bulk action 의 undo (toast 내부 "되돌리기" 버튼). pending → apply 까지는 cancel 가능하지만, apply 후 즉시 undo 는 후속 평가.
- **Q-13.3**: keyboard `Shift+Click` range 의 cross-page 동작 (현재 page 만 vs 보이지 않는 page 도 range 에 포함). 일반 GitHub/Linear 는 visible 만 — 본 컨벤션도 visible 만 (Phase A).
- **Q-13.4**: `assertBulkBarContract` 의 CI 화 — e2e 또는 unit (jsdom) 으로 자동 검증. 별 cycle.

## 14. 참조

- Project-level 정책: [`../../../docs/CONVENTIONS.md §10`](../../../docs/CONVENTIONS.md)
- 외부 design 시각 결과 (Linear / GitHub / Notion / Stripe / Vercel / Figma 패턴 대조): 본 cycle 의 design subagent 출력
- WAI-ARIA Authoring Practices Grid with Selection: https://www.w3.org/WAI/ARIA/apg/patterns/grid/
- Stripe Dashboard cross-page selection banner: 모던 레퍼런스
- Linear bulk action floating pill + keyboard hint: 모던 레퍼런스 (본 컨벤션은 floating pill 대신 list-bottom sticky 채택 — §10.2 거부 근거 참조)
