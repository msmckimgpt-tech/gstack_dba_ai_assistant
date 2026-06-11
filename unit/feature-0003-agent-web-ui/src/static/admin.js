/* =====================================================================
 * Admin console (tab + master-detail + pending changes + bulk commit)
 * ===================================================================== */

const ACCOUNT_PAGE_SIZE = 15;

const adminState = {
  me: null,
  permissions: [],
  roles: [],
  accounts: [],
  products: [],
  datasources: [],            // 멀티 datasource (P2): 등록 datasource 키 목록
  datasourcesEnabled: false,  // AGENT_MULTI_DATASOURCE_ENABLED flag
  tab: "dashboard",
  accountFilter: "all",
  accountSearch: "",
  accountPage: 0,
  accountSelected: new Set(),
  selectedAccountId: null,
  roleSearch: "",
  roleSelected: new Set(),
  selectedRoleId: null,
  productSearch: "",
  selectedProductId: null,
  // DESIGN.md §4 / §12 Phase A — Products multi-select (단일 selectedProductId 와 동거)
  productSelected: new Set(),
  // DESIGN.md §9 — shift-click range 의 anchor index (visible 범위 내)
  accountLastClickIdx: -1,
  roleLastClickIdx: -1,
  productLastClickIdx: -1,
  productDbDraft: new Map(),
  availableDatabases: { metadata_schemas: [], user_schemas: [] },
  // TASK-0210: 대시보드 위젯 그리드 상태(서버 집계 + per-account 커스터마이즈).
  overview: null,            // GET /api/admin/overview 응답 {catalog, widgets, window_days}
  dashboardPrefs: null,      // {version, widgets:[{key,visible,order}]} (계정별 영속)
  dashboardDefaults: null,   // 권한 기반 기본 prefs (기본값 복원용)
  dashboardEditMode: false,
  dashboardWindow: 7,        // 집계 기간(일)
  dashboardLoaded: false,
  dashboardLoading: false,
  // TASK-0218 (CloudWatch UX): 신선도/오류/auto-refresh/드래그 상태.
  dashboardLastUpdated: null,
  dashboardError: null,
  dashboardAutoRefreshSec: 0,
  _dashboardAutoTimer: null,
  _dragKey: null,
  pending: {
    accounts: new Map(),
    roles: new Map(),
    newRoles: new Map(),
    productMeta: new Map(),       // productId -> {name?, description?, is_active?, is_default?, sort_order?}
    productDatabases: new Map(),  // productId -> draft array (user schemas only; metadata 4종 자동 bypass)
    systemPrompts: new Map(),     // key "scope:productId:roleId:accountId" -> {scope, productId, roleId, accountId, content}
  },
  nextTempRoleId: 1,
};

const METADATA_SCHEMAS = ["information_schema", "mysql", "sys", "performance_schema"];
const INTERNAL_SCHEMAS = new Set(["agent_memory"]);

function systemPromptPendingKey({ scope, productId = null, roleId = null, accountId = null }) {
  return `${scope}:${productId || 0}:${roleId || 0}:${accountId || 0}`;
}

// TASK-0052 Phase 1D: 'product' 그룹 추가. backend `PERMISSION_DEFINITIONS[*].group` (app.py) 와 키 정합 필수.
// product 그룹은 정적 `product.manage` / `system_prompt.manage.role.any` 외에 동적 `product.access.<key>`
// 코드들 (Phase 1B 의 _ensure_product_access_permissions backfill) 도 자동으로 그룹에 합류된다.
// TASK-0073 Phase C: audit group 추가 — backend PERMISSION_DEFINITIONS 의 group="audit" 와 key 정합.
// TASK-0095: settings group 추가 — 전역 시스템 프롬프트 (system_prompt.global.read/write).
// TASK-0094 Sprint 1 Phase 12: attachment group 추가 (8 group).
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "product", "attachment", "audit", "settings", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  conversation: "대화",
  product: "제품",
  attachment: "첨부",
  audit: "감사",
  settings: "시스템 설정",
  misc: "기타",
};

// CONVENTIONS.md §10.6 — 관리 콘솔 권한 grid 는 "관리 권한 → 운영 권한 → 기타" 2단 section 으로 묶는다.
// 화면 맥락이 "타인의 권한을 배치하는 관리자 시점" 이므로 console·account·role 메타권한이 위로 오고,
// conversation·product 운영 권한은 그 아래로 분리한다. (작업 화면측 정렬은 app.js WORK_SCREEN_PERMISSION_SECTIONS)
const ADMIN_PERMISSION_SECTIONS = [
  // TASK-0073 Phase C: audit 그룹은 관리 권한 section 의 admin 콘솔 책임 — console / account / role 와 같이 배치.
  // TASK-0095: settings 그룹은 시스템 운영 (전역 시스템 프롬프트 등) — manage 와 함께.
  { id: "manage", title: "관리 권한", description: "콘솔 진입 · 계정 · 역할 메타권한 · 감사 · 시스템 설정", groups: ["console", "account", "role", "audit", "settings"] },
  // TASK-0094 Sprint 1 Phase 12: attachment 그룹은 운영 권한 묶음에 포함.
  { id: "operate", title: "운영 권한", description: "대화 · 제품 접근 · 첨부", groups: ["conversation", "product", "attachment"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

/* ── Bulk action contract — CONVENTIONS.md §10 + DESIGN.md §4~§9 ───── */

// DESIGN.md §5 / §10.4 — 카테고리별 단위 어휘
const BULK_ENTITY_UNIT = { accounts: "명", roles: "개", products: "개" };
const BULK_ACTION_LABEL = { activate: "활성화", deactivate: "비활성화", delete: "삭제" };
// DESIGN.md §7 — 위험 액션 typed-confirm 임계치
const CONFIRM_TYPED_THRESHOLD = 10;

function entityUnit(entity) { return BULK_ENTITY_UNIT[entity] || "개"; }
function actionLabel(action) { return BULK_ACTION_LABEL[action] || action; }

// DESIGN.md §7 — bulk action confirm 표준
function confirmBulkAction({ entity, action, count, danger = false }) {
  const unit = entityUnit(entity);
  const verb = actionLabel(action);
  const summary = `${count}${unit} ${verb}`;
  if (!danger || count < CONFIRM_TYPED_THRESHOLD) {
    return window.confirm(`${summary} 반영하시겠습니까?`);
  }
  const expected = String(count);
  const typed = window.prompt(
    `위험 작업: ${expected} 을(를) 입력하세요:`
  );
  return typed === expected;
}

// DESIGN.md §8 — RBAC partial-failure 처리. ids 를 [applied, skipped] 로 분할.
function runBulkActionWithPartialFail({ entity, ids, action, applyFn, canTargetRow }) {
  const applied = [];
  const skipped = [];
  Array.from(ids).forEach((id) => {
    if (canTargetRow && !canTargetRow(id)) { skipped.push(id); return; }
    try { applyFn(id); applied.push(id); }
    catch (_err) { skipped.push(id); }
  });
  const unit = entityUnit(entity);
  const verb = actionLabel(action);
  const baseMsg = `${applied.length}${unit} ${verb} pending 반영`;
  if (skipped.length === 0) {
    showToast(baseMsg);
  } else {
    // skipped chip 은 styles.css .toast-skipped 와 짝
    const skipChip = ` (${skipped.length}${unit} 제외)`;
    showToast(baseMsg + skipChip, false);
  }
  return { applied, skipped };
}

// DESIGN.md §4 — runtime contract assertion (drift 재발 차단)
function assertBulkBarContract(entity) {
  const barId = entity === "roles" ? "roleBulkBar" : `${entity}BulkBar`;
  const bar = document.getElementById(barId);
  if (!bar) { console.warn(`[contract] #${barId} missing`); return false; }
  if (bar.getAttribute("role") !== "toolbar") {
    console.warn(`[contract] #${barId} role!=toolbar (DESIGN.md §10)`); return false;
  }
  if (!bar.hasAttribute("aria-live")) {
    console.warn(`[contract] #${barId} aria-live missing`); return false;
  }
  const parent = bar.parentElement;
  if (!parent || !parent.classList.contains("admin-list-col")) {
    console.warn(`[contract] #${barId} must be child of .admin-list-col (CONVENTIONS §10.2)`);
    return false;
  }
  const paneSel = `[data-admin-pane="${entity}"]`;
  const headRight = document.querySelector(`${paneSel} .admin-pane-head-right`);
  if (headRight && headRight.querySelector(".admin-bulk-label")) {
    console.warn(`[contract] bulk label leaked into .admin-pane-head-right (CONVENTIONS §10.2)`);
    return false;
  }
  return true;
}

// DESIGN.md §6 — generic cross-page banner renderer
function renderCrossPageBanner({ entity, selected, visibleIds, totalCount, onClearAll, onShowCurrentOnly }) {
  const banner = document.getElementById(`${entity}CrossPageBanner`);
  if (!banner) return;
  banner.innerHTML = "";
  const unit = entityUnit(entity);
  const visibleSet = new Set(visibleIds.map((v) => String(v)));
  const currentPageCount = Array.from(selected).filter((id) => visibleSet.has(String(id))).length;
  const totalSelected = selected.size;
  const offPageCount = totalSelected - currentPageCount;
  if (offPageCount <= 0) return;  // 다른 페이지 선택 없으면 banner skip
  const msg = document.createElement("div");
  msg.className = "admin-bulk-cross-page-msg";
  msg.innerHTML = `현재 페이지 <strong>${currentPageCount}${unit}</strong> · 전체 <strong>${totalSelected}${unit}</strong> 선택 (다른 페이지 ${offPageCount}${unit} 포함)`;
  banner.appendChild(msg);
  const clearAllBtn = document.createElement("button");
  clearAllBtn.type = "button";
  clearAllBtn.className = "tool-btn";
  clearAllBtn.textContent = "모두 해제";
  clearAllBtn.addEventListener("click", onClearAll);
  banner.appendChild(clearAllBtn);
  const showCurOnlyBtn = document.createElement("button");
  showCurOnlyBtn.type = "button";
  showCurOnlyBtn.className = "tool-btn";
  showCurOnlyBtn.textContent = "현재 페이지만 보기";
  showCurOnlyBtn.addEventListener("click", onShowCurrentOnly);
  banner.appendChild(showCurOnlyBtn);
}

// DESIGN.md §9 — shift-click range 적용
function applyShiftRangeSelect({ selected, visibleIds, fromIdx, toIdx, addMode = true }) {
  if (fromIdx < 0 || toIdx < 0) return;
  const [lo, hi] = fromIdx <= toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
  for (let i = lo; i <= hi; i++) {
    const id = visibleIds[i];
    if (id === undefined || id === null) continue;
    if (addMode) selected.add(id); else selected.delete(id);
  }
}

/* ── Utility & DOM helpers ───────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);
const adminToastEl = $("adminToast");
let adminToastTimer = null;

function showToast(message, isError = false) {
  adminToastEl.textContent = message;
  adminToastEl.style.background = isError
    ? "rgba(124, 24, 24, 0.94)"
    : "rgba(10, 22, 44, 0.92)";
  adminToastEl.classList.add("is-visible");
  if (adminToastTimer) clearTimeout(adminToastTimer);
  adminToastTimer = window.setTimeout(() => {
    adminToastEl.classList.remove("is-visible");
  }, 2200);
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || response.statusText);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function formatDateTime(value = "") {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function can(permission) {
  return Boolean(adminState.me?.permissions?.[permission]);
}

function groupedPermissions(opts = {}) {
  // TASK-0053 Phase B: dynamic 권한 (`product.access.<key>`) 은 별도 product subcatalog UI 가
  // 처리하므로 일반 권한 grid 에서는 excludeDynamic=true 로 필터링한다. 정적 권한
  // (`product.manage`, `system_prompt.manage.role.any` 등) 은 그대로 product 그룹에 남는다.
  const { excludeDynamic = false } = opts;
  const groups = new Map();
  adminState.permissions.forEach((permission) => {
    if (excludeDynamic && permission.is_dynamic) return;
    const group = permission.group || "misc";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(permission);
  });
  const order = new Map();
  PERMISSION_GROUP_ORDER.forEach((key, idx) => order.set(key, idx));
  return Array.from(groups.entries()).sort((a, b) => {
    const ai = order.has(a[0]) ? order.get(a[0]) : 99;
    const bi = order.has(b[0]) ? order.get(b[0]) : 99;
    if (ai !== bi) return ai - bi;
    return a[0].localeCompare(b[0]);
  });
}

// CONVENTIONS.md §10.6 — groupedPermissions() 결과를 ADMIN_PERMISSION_SECTIONS 기준으로
// 2단 section (관리/운영/기타) 으로 묶어 반환한다. 빈 group / 빈 section 은 자동 제외.
// 반환 형식: [{ section: {id, title, description}, groups: [[groupKey, items], ...] }, ...]
function sectionedGroupedPermissions(opts = {}) {
  const groupsByKey = new Map(groupedPermissions(opts));
  const used = new Set();
  const out = [];
  ADMIN_PERMISSION_SECTIONS.forEach((sec) => {
    const groups = sec.groups
      .filter((g) => groupsByKey.has(g))
      .map((g) => { used.add(g); return [g, groupsByKey.get(g)]; });
    if (groups.length) out.push({ section: sec, groups });
  });
  // ADMIN_PERMISSION_SECTIONS 에 정의되지 않은 group key 가 새로 들어오면 "기타" section 으로 fallback.
  const orphans = Array.from(groupsByKey.entries()).filter(([k]) => !used.has(k));
  if (orphans.length) {
    const miscSec = out.find((e) => e.section.id === "misc");
    if (miscSec) miscSec.groups.push(...orphans);
    else out.push({ section: { id: "misc", title: "기타", description: null }, groups: orphans });
  }
  return out;
}

function dynamicProductPermissions() {
  // TASK-0053 Phase B: product 별 access 권한 row 를 product_id 기준으로 sort 후 반환.
  // `_resolve_permission_catalog` 에서 GroupName='product' 로 묶이고 is_dynamic=true.
  return (adminState.permissions || [])
    .filter((p) => p && p.is_dynamic && (p.group === "product"))
    .map((p) => ({
      ...p,
      product_id: Number(p.product_id || 0),
    }))
    .sort((a, b) => {
      // product_id 순서가 아닌, products 목록의 sort_order 순서를 따른다.
      const products = adminState.products || [];
      const idxA = products.findIndex((pr) => Number(pr.id) === Number(a.product_id));
      const idxB = products.findIndex((pr) => Number(pr.id) === Number(b.product_id));
      if (idxA === -1 && idxB === -1) return String(a.code).localeCompare(String(b.code));
      if (idxA === -1) return 1;
      if (idxB === -1) return -1;
      return idxA - idxB;
    });
}

function statusBadge(text, className = "") {
  const badge = document.createElement("span");
  badge.className = `status-chip ${className}`.trim();
  badge.textContent = text;
  return badge;
}

/* ── Permission grid (collapsible details, from TASK-0027) ───────────── */

function _updateCheckboxGroupSummary(section) {
  const total = section.querySelectorAll("input[type='checkbox']").length;
  const checked = section.querySelectorAll("input[type='checkbox']:checked").length;
  const badge = section.querySelector(".permission-group-counts");
  if (badge) badge.textContent = `${checked}/${total} 선택`;
}

function _updateOverrideGroupSummary(section) {
  const selects = section.querySelectorAll("select[data-override-code]");
  let allow = 0, deny = 0, inherit = 0;
  selects.forEach((s) => {
    if (s.value === "allow") allow += 1;
    else if (s.value === "deny") deny += 1;
    else inherit += 1;
  });
  const badge = section.querySelector(".permission-group-counts");
  if (!badge) return;
  const parts = [];
  if (allow) parts.push(`허용 ${allow}`);
  if (deny) parts.push(`거부 ${deny}`);
  parts.push(`상속 ${inherit}`);
  badge.textContent = parts.join(" · ");
}

function renderPermissionGrid(containerEl, selectedCodes, disabled, mode, overrides, onChange, opts = {}) {
  // TASK-0053 Phase B: opts.excludeDynamic=true 면 dynamic product.access.<key> 권한들을 grid 에서 제외.
  // 그 권한들은 호출처가 별도 buildProductSubcatalog... 함수로 product 카드 형식으로 렌더한다.
  // CONVENTIONS.md §10.6 — group <details> 들은 ADMIN_PERMISSION_SECTIONS 의 2단 section (관리/운영/기타) 으로 묶어 렌더.
  const { excludeDynamic = false } = opts;
  containerEl.innerHTML = "";
  const selected = new Set(selectedCodes || []);
  sectionedGroupedPermissions({ excludeDynamic }).forEach(({ section: sec, groups }) => {
    const sectionEl = document.createElement("section");
    sectionEl.className = "permission-section";
    sectionEl.dataset.permSection = sec.id;
    const sectionHead = document.createElement("header");
    sectionHead.className = "permission-section-head";
    const sectionTitle = document.createElement("h4");
    sectionTitle.className = "permission-section-title";
    sectionTitle.textContent = sec.title;
    sectionHead.appendChild(sectionTitle);
    if (sec.description) {
      const sectionDesc = document.createElement("span");
      sectionDesc.className = "permission-section-description";
      sectionDesc.textContent = sec.description;
      sectionHead.appendChild(sectionDesc);
    }
    sectionEl.appendChild(sectionHead);
    const sectionGroupsEl = document.createElement("div");
    sectionGroupsEl.className = "permission-section-groups";
    sectionEl.appendChild(sectionGroupsEl);
    containerEl.appendChild(sectionEl);

  groups.forEach(([group, items]) => {
    const section = document.createElement("details");
    section.className = "permission-group";
    section.dataset.permGroup = group;

    const summary = document.createElement("summary");
    summary.className = "permission-group-head";
    const title = document.createElement("span");
    title.className = "permission-group-title";
    title.textContent = PERMISSION_GROUP_LABELS[group] || group;
    const counts = document.createElement("span");
    counts.className = "permission-group-counts";
    summary.append(title, counts);
    section.appendChild(summary);

    const bulk = document.createElement("div");
    bulk.className = "permission-bulk-actions";
    if (mode === "checkbox") {
      const allBtn = document.createElement("button");
      allBtn.type = "button";
      allBtn.className = "tool-btn";
      allBtn.textContent = "모두 선택";
      allBtn.disabled = disabled;
      allBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        section.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = true; });
        _updateCheckboxGroupSummary(section);
        if (onChange) onChange();
      });
      const noneBtn = document.createElement("button");
      noneBtn.type = "button";
      noneBtn.className = "tool-btn";
      noneBtn.textContent = "모두 해제";
      noneBtn.disabled = disabled;
      noneBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        section.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = false; });
        _updateCheckboxGroupSummary(section);
        if (onChange) onChange();
      });
      bulk.append(allBtn, noneBtn);
    } else {
      const makeBulk = (val, label) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tool-btn";
        btn.textContent = label;
        btn.disabled = disabled;
        btn.addEventListener("click", (evt) => {
          evt.preventDefault();
          section.querySelectorAll("select[data-override-code]").forEach((s) => { s.value = val; });
          _updateOverrideGroupSummary(section);
          if (onChange) onChange();
        });
        return btn;
      };
      bulk.append(
        makeBulk("allow", "모두 허용"),
        makeBulk("deny", "모두 거부"),
        makeBulk("inherit", "모두 상속"),
      );
    }
    section.appendChild(bulk);

    const list = document.createElement("div");
    list.className = "permission-grid-list";

    items.forEach((permission) => {
      if (mode === "checkbox") {
        const label = document.createElement("label");
        label.className = "permission-toggle permission-toggle-card";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = permission.code;
        input.checked = selected.has(permission.code);
        input.disabled = disabled;
        input.addEventListener("change", () => {
          _updateCheckboxGroupSummary(section);
          if (onChange) onChange();
        });
        const textWrap = document.createElement("span");
        textWrap.className = "permission-text";
        const strong = document.createElement("strong");
        strong.textContent = permission.label;
        const small = document.createElement("small");
        small.textContent = permission.description;
        textWrap.append(strong, small);
        label.append(input, textWrap);
        list.appendChild(label);
      } else {
        const field = document.createElement("label");
        field.className = "field override-field";
        const titleEl = document.createElement("span");
        titleEl.textContent = permission.label;
        const select = document.createElement("select");
        select.dataset.overrideCode = permission.code;
        select.disabled = disabled;
        [
          ["inherit", "상속"],
          ["allow", "허용"],
          ["deny", "거부"],
        ].forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          option.selected = (overrides?.[permission.code] || "inherit") === value;
          select.appendChild(option);
        });
        select.addEventListener("change", () => {
          _updateOverrideGroupSummary(section);
          if (onChange) onChange();
        });
        const hint = document.createElement("small");
        hint.textContent = permission.description;
        field.append(titleEl, select, hint);
        list.appendChild(field);
      }
    });

    section.appendChild(list);
    sectionGroupsEl.appendChild(section);

    if (mode === "checkbox") {
      _updateCheckboxGroupSummary(section);
      const hasSelected = items.some((p) => selected.has(p.code));
      section.open = hasSelected;
    } else {
      _updateOverrideGroupSummary(section);
      const hasNonInherit = items.some((p) => {
        const v = overrides?.[p.code] || "inherit";
        return v === "allow" || v === "deny";
      });
      section.open = hasNonInherit;
    }
  });
  });
}

/* ── Merged state helpers (server data + pending overlay) ────────────── */

function mergedAccount(accountId) {
  const base = adminState.accounts.find((a) => Number(a.id) === Number(accountId));
  if (!base) return null;
  const pending = adminState.pending.accounts.get(Number(accountId)) || {};
  return {
    ...base,
    role_id: pending.role_id !== undefined ? pending.role_id : Number(base.role?.id || 0),
    is_active: pending.is_active !== undefined ? pending.is_active : Boolean(base.is_active),
    permission_overrides: pending.permission_overrides !== undefined
      ? pending.permission_overrides
      : (base.permission_overrides || {}),
    _pending: Object.keys(pending).length > 0,
    _delete: Boolean(pending._delete),
  };
}

function mergedRole(roleKey) {
  if (String(roleKey).startsWith("new:")) {
    const draft = adminState.pending.newRoles.get(roleKey);
    if (!draft) return null;
    return {
      id: roleKey,
      key: draft.role_key || "",
      name: draft.name || "",
      description: draft.description || "",
      is_active: Boolean(draft.is_active),
      is_default_signup: Boolean(draft.is_default_signup),
      permission_codes: draft.permission_codes || [],
      member_count: 0,
      created_at: "",
      updated_at: "",
      _isNew: true,
      _pending: true,
    };
  }
  const base = adminState.roles.find((r) => Number(r.id) === Number(roleKey));
  if (!base) return null;
  const pending = adminState.pending.roles.get(Number(roleKey)) || {};
  return {
    ...base,
    name: pending.name !== undefined ? pending.name : (base.name || ""),
    description: pending.description !== undefined ? pending.description : (base.description || ""),
    is_active: pending.is_active !== undefined ? pending.is_active : Boolean(base.is_active),
    is_default_signup: pending.is_default_signup !== undefined
      ? pending.is_default_signup
      : Boolean(base.is_default_signup),
    permission_codes: pending.permission_codes !== undefined
      ? pending.permission_codes
      : (base.permission_codes || []),
    _pending: Object.keys(pending).length > 0,
    _delete: Boolean(pending._delete),
  };
}

function setAccountPending(accountId, patch) {
  const id = Number(accountId);
  const current = adminState.pending.accounts.get(id) || {};
  const base = adminState.accounts.find((a) => Number(a.id) === id);
  if (!base) return;
  const next = { ...current };
  for (const [key, value] of Object.entries(patch)) {
    next[key] = value;
  }
  // Drop keys that match server value (to avoid noise)
  if (next.role_id !== undefined && Number(next.role_id) === Number(base.role?.id || 0)) {
    delete next.role_id;
  }
  if (next.is_active !== undefined && Boolean(next.is_active) === Boolean(base.is_active)) {
    delete next.is_active;
  }
  if (next.permission_overrides !== undefined) {
    const serverOv = base.permission_overrides || {};
    const curOv = next.permission_overrides;
    const allKeys = new Set([...Object.keys(serverOv), ...Object.keys(curOv)]);
    let same = true;
    for (const k of allKeys) {
      const sv = serverOv[k] || "inherit";
      const cv = curOv[k] || "inherit";
      if (sv !== cv) { same = false; break; }
    }
    if (same) delete next.permission_overrides;
  }
  if (Object.keys(next).length === 0) {
    adminState.pending.accounts.delete(id);
  } else {
    adminState.pending.accounts.set(id, next);
  }
  refreshPendingUI();
}

function setRolePending(roleId, patch) {
  if (String(roleId).startsWith("new:")) {
    const draft = adminState.pending.newRoles.get(roleId) || {};
    adminState.pending.newRoles.set(roleId, { ...draft, ...patch });
    refreshPendingUI();
    return;
  }
  const id = Number(roleId);
  const current = adminState.pending.roles.get(id) || {};
  const base = adminState.roles.find((r) => Number(r.id) === id);
  if (!base) return;
  const next = { ...current, ...patch };
  // Drop keys matching server value
  for (const key of ["name", "description"]) {
    if (next[key] !== undefined && String(next[key]) === String(base[key] || "")) {
      delete next[key];
    }
  }
  for (const key of ["is_active", "is_default_signup"]) {
    if (next[key] !== undefined && Boolean(next[key]) === Boolean(base[key])) {
      delete next[key];
    }
  }
  if (next.permission_codes !== undefined) {
    const serverSet = new Set(base.permission_codes || []);
    const curSet = new Set(next.permission_codes);
    let same = serverSet.size === curSet.size;
    if (same) {
      for (const c of curSet) { if (!serverSet.has(c)) { same = false; break; } }
    }
    if (same) delete next.permission_codes;
  }
  if (Object.keys(next).length === 0) {
    adminState.pending.roles.delete(id);
  } else {
    adminState.pending.roles.set(id, next);
  }
  refreshPendingUI();
}

function pendingChangeCount() {
  return (
    adminState.pending.accounts.size +
    adminState.pending.roles.size +
    adminState.pending.newRoles.size +
    adminState.pending.productMeta.size +
    adminState.pending.productDatabases.size +
    adminState.pending.systemPrompts.size
  );
}

function setProductMetaPending(productId, patch) {
  const id = Number(productId);
  if (!id) return;
  const current = adminState.pending.productMeta.get(id) || {};
  const next = { ...current, ...patch };
  adminState.pending.productMeta.set(id, next);
  refreshPendingUI();
}

function setProductDatabasesPending(productId, draft) {
  const id = Number(productId);
  if (!id) return;
  // Keep a snapshot copy so subsequent mutations don't sneak past pending tracking.
  const snapshot = (Array.isArray(draft) ? draft : []).map((d) => ({ ...d }));
  adminState.pending.productDatabases.set(id, snapshot);
  refreshPendingUI();
}

function setSystemPromptPending(args) {
  const key = systemPromptPendingKey(args);
  adminState.pending.systemPrompts.set(key, {
    scope: args.scope,
    productId: args.productId || null,
    roleId: args.roleId || null,
    accountId: args.accountId || null,
    content: String(args.content ?? ""),
  });
  refreshPendingUI();
}

function getSystemPromptPending(args) {
  return adminState.pending.systemPrompts.get(systemPromptPendingKey(args)) || null;
}

/* ── Tab navigation ──────────────────────────────────────────────────── */

// TASK-0136 (#11): LLM 사용량 패널 — admin 전용(console.usage.read). /api/admin/usage 집계 표시.
// TASK-0184: drill* = 역할 막대 클릭 시 펼치는 계정 drill-down 상태(byAccount 캐시·역할·페이지·검색).
// TASK-0198: selectedModels = 모델 필터(null → 전체, 배열 → 선택 모델 키만). _lastRaw/_lastKey =
//   마지막 응답 캐시(days|gran). 모델 칩 토글은 재조회 없이 캐시로 재렌더(loadUsage({refetch:false})).
adminState.usage = { initialized: false, byAccount: [], drillRole: null, drillPage: 0, drillQuery: "", drillPageSize: 10, _renderDrill: null, selectedModels: null, _lastRaw: null, _lastKey: null };

// TASK-0198: opts.refetch=false → days/gran 동일 캐시(_lastRaw)로 재렌더만(모델 칩 토글용).
//   기간/단위 변경(컨트롤 change) 은 refetch=true(기본) — 새 모델 집합이 올 수 있으므로 선택 초기화.
async function loadUsage(opts) {
  const refetch = !(opts && opts.refetch === false);
  const sel = document.getElementById("usageDaysSel");
  const granSel = document.getElementById("usageGranSel");
  const days = sel ? sel.value : "30";
  const gran = granSel ? granSel.value : "day";
  const summaryEl = document.getElementById("usageSummary");
  const modelEl = document.getElementById("usageByModel");
  const roleEl = document.getElementById("usageByRole");
  const acctEl = document.getElementById("usageByAccount");
  const dayChartEl = document.getElementById("usageDayChart");
  const modelChartEl = document.getElementById("usageModelChart");
  const roleChartEl = document.getElementById("usageRoleChart");
  const roleCostChartEl = document.getElementById("usageRoleCostChart");
  const trendTitleEl = document.getElementById("usageTrendTitle");
  const GRAN_LABEL = { hour: "시간별", day: "일별", week: "주별", month: "월별" };
  if (trendTitleEl) trendTitleEl.textContent = GRAN_LABEL[gran] || "일별";
  if (summaryEl && refetch) summaryEl.textContent = "로딩 중…";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const num = (v) => (Number(v) || 0).toLocaleString();
  const usd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  // TASK-0166: 상용 대시보드식 hover 툴팁 (의존성 0). data-tip 속성을 가진 요소에 마우스.
  const tip = (() => {
    let t = document.getElementById("usageTooltip");
    if (!t) {
      t = document.createElement("div");
      t.id = "usageTooltip";
      t.className = "admin-usage-tooltip";  // TASK-0177: 인라인 cssText → 토큰 클래스
      document.body.appendChild(t);
    }
    return t;
  })();
  const bindTip = (root) => {
    if (!root || root._tipBound) return;
    root._tipBound = true;
    root.addEventListener("mousemove", (e) => {
      const el2 = e.target.closest ? e.target.closest("[data-tip]") : null;
      if (!el2) { tip.style.display = "none"; return; }
      tip.innerHTML = el2.getAttribute("data-tip");
      tip.style.display = "block";
      let x = e.clientX + 13, y = e.clientY + 13;
      if (x + tip.offsetWidth > window.innerWidth) x = e.clientX - tip.offsetWidth - 13;
      if (y + tip.offsetHeight > window.innerHeight) y = e.clientY - tip.offsetHeight - 13;
      tip.style.left = x + "px"; tip.style.top = y + "px";
    });
    root.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  };
  // TASK-0164/0166: 순수 SVG 차트. 색상 — 로컬/시스템(edge·시스템·역할없음)은 회색.
  const CHART_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#0ea5e9", "#f43f5e"];
  const SYS_COLOR = "#94a3b8";
  const colorMapFor = (keys) => {
    const m = {}; let i = 0;
    keys.forEach((k) => {
      if (k === "(시스템)" || k === "(역할 없음)" || k === "edge") m[k] = SYS_COLOR;
      else { m[k] = CHART_COLORS[i % CHART_COLORS.length]; i += 1; }
    });
    return m;
  };
  // TASK-0181: 전역 모델 색맵 — 일별 stacked / 도넛 / 역할·계정 stacked 가 같은 모델은 같은 색.
  // data 수신 후 by_model 등에서 등장 모델 전체로 1회 채운다.
  let modelColor = {};
  const mcol = (k) => modelColor[k] || SYS_COLOR;
  // bucket 라벨 축약 (YYYY- 제거: 'MM-DD', 'MM-DD HH:00'; 월별 'YYYY-MM' 유지).
  const shortLabel = (d) => { const s = String(d); return s.length > 7 ? s.slice(5) : s; };
  // 기간별 토큰 사용량 — 모델별 누적(stacked) 세로 막대 + 막대 총합 라벨 + hover 툴팁.
  const renderStacked = (el, byDayModel) => {
    if (!el) return;
    const rows = byDayModel || [];
    if (!rows.length) { el.innerHTML = "<p style='color:var(--text-muted);'>데이터 없음</p>"; return; }
    const dayMap = {}; const models = [];
    rows.forEach((r) => {
      dayMap[r.day] = dayMap[r.day] || {};
      dayMap[r.day][r.model] = (dayMap[r.day][r.model] || 0) + (r.total_tokens || 0);
      if (!models.includes(r.model)) models.push(r.model);
    });
    const days = Object.keys(dayMap).sort();
    const totalsByDay = days.map((d) => Object.values(dayMap[d]).reduce((a, b) => a + b, 0));
    const maxT = Math.max(1, ...totalsByDay);
    /* TASK-0180: viewBox 폭을 카드 실제 폭에 맞춰 일별 차트가 넓은 카드를 꽉 채우게 한다
       (높이는 H 고정 → SVG width:100%/height:auto 시 정확히 H px). 측정 실패 시 760 폴백. */
    const cw = Math.max(360, Math.round(el.clientWidth || 0) || 760);
    const W = cw, H = 200, pL = 56, pB = 26, pT = 10, pR = 14;
    const plotW = W - pL - pR, plotH = H - pT - pB, n = days.length;
    const step = plotW / n, bw = Math.max(2, Math.min(64, step * 0.66));
    let bars = "", valLabels = "";
    days.forEach((d, di) => {
      const x = pL + di * step + (step - bw) / 2;
      const dayTot = totalsByDay[di];
      let y = pT + plotH;
      models.forEach((m) => {
        const v = dayMap[d][m] || 0; if (v <= 0) return;
        const h = (v / maxT) * plotH; y -= h;
        const pct = dayTot ? (v / dayTot * 100).toFixed(1) : "0";
        bars += `<rect x='${x.toFixed(1)}' y='${y.toFixed(1)}' width='${bw.toFixed(1)}' height='${h.toFixed(1)}' fill='${mcol(m)}' rx='1' data-tip='${esc(d)} · ${esc(m)}<br><b>${num(v)}</b> 토큰 (${pct}%)'/>`;
      });
      if (bw >= 20 && (dayTot / maxT) > 0.05) {
        valLabels += `<text x='${(x + bw / 2).toFixed(1)}' y='${(y - 3).toFixed(1)}' text-anchor='middle' font-size='9' fill='var(--text-2)'>${num(dayTot)}</text>`;
      }
    });
    const axis = `<line x1='${pL}' y1='${pT + plotH}' x2='${W - pR}' y2='${pT + plotH}' stroke='var(--border)'/>`
      + `<text x='${pL - 6}' y='${pT + 9}' text-anchor='end' font-size='10' fill='var(--text-muted)'>${num(maxT)}</text>`
      + `<text x='${pL - 6}' y='${pT + plotH}' text-anchor='end' font-size='10' fill='var(--text-muted)'>0</text>`;
    let xl = "";
    [...new Set(n <= 1 ? [0] : [0, Math.floor(n / 3), Math.floor(2 * n / 3), n - 1])].forEach((di) => {
      const x = pL + di * step + step / 2;
      xl += `<text x='${x.toFixed(1)}' y='${H - 9}' text-anchor='middle' font-size='10' fill='var(--text-muted)'>${esc(shortLabel(days[di]))}</text>`;
    });
    const legend = models.map((m) => `<span style='display:inline-flex;align-items:center;gap:5px;margin:2px 14px 2px 0;font-size:12px;'><span style='width:11px;height:11px;border-radius:2px;background:${mcol(m)};display:inline-block;'></span>${esc(m)}</span>`).join("");
    el.innerHTML = `<svg viewBox='0 0 ${W} ${H}' style='width:100%;height:auto;display:block;'>${axis}${bars}${valLabels}${xl}</svg><div style='margin-top:6px;'>${legend}</div>`;
    bindTip(el);
  };
  // 모델별 비중 — 도넛 + hover 툴팁(토큰·비중·추정비용).
  const renderDonut = (el, byModel) => {
    if (!el) return;
    const rows = (byModel || []).map((r) => ({
      label: (r.resolved_model && r.resolved_model !== r.model) ? r.resolved_model : (r.model || "(미상)"),
      value: r.total_tokens || 0, calls: r.calls || 0, cost: r.cost_usd || 0,
    })).filter((r) => r.value > 0);
    if (!rows.length) { el.innerHTML = "<p style='color:var(--text-muted);'>데이터 없음</p>"; return; }
    const total = rows.reduce((a, b) => a + b.value, 0);

    const R = 54, C = 2 * Math.PI * R, cx = 70, cy = 70;
    let off = 0, segs = "";
    rows.forEach((r) => {
      const len = (r.value / total) * C;
      const costTip = r.cost > 0 ? `<br>추정 ${usd(r.cost)}` : "";
      segs += `<circle cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${mcol(r.label)}' stroke-width='22' stroke-dasharray='${len.toFixed(2)} ${(C - len).toFixed(2)}' stroke-dashoffset='${(-off).toFixed(2)}' transform='rotate(-90 ${cx} ${cy})' data-tip='${esc(r.label)}<br><b>${num(r.value)}</b> 토큰 (${(r.value / total * 100).toFixed(1)}%)<br>${num(r.calls)} 호출${costTip}'/>`;
      off += len;
    });
    const legend = rows.map((r) => `<div style='display:flex;align-items:center;gap:6px;font-size:12px;margin:3px 0;'><span style='width:11px;height:11px;border-radius:2px;background:${mcol(r.label)};display:inline-block;flex:none;'></span><span style='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>${esc(r.label)}</span><strong>${(r.value / total * 100).toFixed(1)}%</strong></div>`).join("");
    el.innerHTML = `<div style='display:flex;align-items:center;gap:18px;flex-wrap:wrap;'><svg viewBox='0 0 140 140' style='width:130px;height:130px;flex:none;'>${segs}<text x='70' y='66' text-anchor='middle' font-size='11' fill='var(--text-muted)'>총 토큰</text><text x='70' y='83' text-anchor='middle' font-size='13' font-weight='700' fill='var(--text)'>${num(total)}</text></svg><div style='flex:1;min-width:150px;'>${legend}</div></div>`;
    bindTip(el);
  };
  // 가로 막대 (역할별/계정별). rows = [{label, value, tip}].
  const renderHBar = (el, rows, valueFmt) => {
    if (!el) return;
    const fmt = valueFmt || num;
    const data = (rows || []).filter((r) => r.value > 0);
    if (!data.length) { el.innerHTML = "<p style='color:var(--text-muted);'>데이터 없음</p>"; return; }
    const max = Math.max(...data.map((r) => r.value));
    const cmap = colorMapFor(data.map((r) => r.label));
    el.innerHTML = data.map((r) => `<div style='margin:6px 0;' data-tip='${r.tip || (esc(r.label) + "<br><b>" + fmt(r.value) + "</b>")}'><div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;'><span>${esc(r.label)}</span><strong>${fmt(r.value)}</strong></div><div style='background:var(--border-subtle);border-radius:4px;height:14px;overflow:hidden;'><div style='width:${(r.value / max * 100).toFixed(1)}%;height:100%;background:${cmap[r.label]};border-radius:4px;'></div></div></div>`).join("");
    bindTip(el);
  };
  // TASK-0181: 모델별 누적(stacked) 가로 막대 — 역할별/계정별 토큰·비용을 어떤 모델로 썼는지 색 분해.
  // rows = [{label, total_tokens, cost_usd, models:[{model, total_tokens, cost_usd}]}]. 모델 색 = 전역 modelColor.
  const renderStackedHBar = (el, rows, valueKey, valFmt, onRowClick) => {
    if (!el) return;
    const fmt = valFmt || num;
    const data = (rows || []).map((r) => ({ label: r.label, value: r[valueKey] || 0, models: r.models || [] })).filter((r) => r.value > 0);
    if (!data.length) { el.innerHTML = "<p class='admin-usage-empty'>데이터 없음</p>"; return; }
    const max = Math.max(...data.map((r) => r.value));
    const clickable = typeof onRowClick === "function";  // TASK-0184: 역할 막대 클릭 → 계정 drill-down.
    el.innerHTML = data.map((r) => {
      const segs = (r.models || []).filter((m) => (m[valueKey] || 0) > 0).map((m) =>
        `<div data-tip='${esc(r.label)} · ${esc(m.model)}<br><b>${fmt(m[valueKey])}</b>' style='width:${(m[valueKey] / max * 100).toFixed(2)}%;background:${mcol(m.model)};height:100%;'></div>`
      ).join("");
      const cls = "admin-usage-hbar-row" + (clickable ? " admin-usage-hbar-row--click" : "");
      return `<div class='${cls}' data-label='${esc(r.label)}'><div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;'><span>${esc(r.label)}</span><strong>${fmt(r.value)}</strong></div><div style='display:flex;background:var(--border-subtle);border-radius:4px;height:14px;overflow:hidden;'>${segs}</div></div>`;
    }).join("");
    bindTip(el);
    if (clickable) {
      el.querySelectorAll(".admin-usage-hbar-row--click").forEach((row, i) => {
        row.addEventListener("click", () => onRowClick(data[i].label));
      });
    }
  };
  // TASK-0184: 계정 drill-down — 역할 막대 클릭 시 그 역할의 계정을 검색·Top-N 페이징으로 펼친다.
  // 역할 키 규칙은 백엔드 _aggregate_usage_by_role 와 동일(시스템/역할 없음/역할명). loadUsage 클로저
  // 안에 둬 renderStackedHBar·num·mcol(모델 색) 을 재사용하고, 컨트롤 바인딩이 호출하도록 _renderDrill 노출.
  const usageRoleKeyOf = (a) => (a.account_id == null ? "(시스템)" : (a.role || "(역할 없음)"));
  const usageAcctLabelOf = (a) => (a.account_id == null ? "(시스템)" : (a.username ? `${a.username} (#${a.account_id})` : `#${a.account_id}`));
  const renderAccountDrill = () => {
    const st = adminState.usage;
    const chartEl = document.getElementById("usageDrillChart");
    const costChartEl = document.getElementById("usageDrillCostChart");
    const toolsEl = document.getElementById("usageDrillTools");
    const pagerEl = document.getElementById("usageDrillPager");
    const hintEl = document.getElementById("usageDrillHint");
    const pageInfoEl = document.getElementById("usageDrillPageInfo");
    if (!chartEl) return;
    const markActive = () => {
      document.querySelectorAll("#usageRoleChart .admin-usage-hbar-row, #usageRoleCostChart .admin-usage-hbar-row").forEach((r) => {
        r.classList.toggle("admin-usage-hbar-row--active", r.getAttribute("data-label") === st.drillRole);
      });
    };
    if (!st.drillRole) {  // 접힘
      chartEl.innerHTML = "";
      if (costChartEl) costChartEl.innerHTML = "";
      if (toolsEl) toolsEl.classList.add("hidden");
      if (pagerEl) pagerEl.classList.add("hidden");
      if (hintEl) hintEl.textContent = "· 위 역할 막대를 클릭하면 해당 역할의 계정이 펼쳐집니다";
      markActive();
      return;
    }
    const all = (st.byAccount || []).filter((a) => usageRoleKeyOf(a) === st.drillRole);
    const q = (st.drillQuery || "").trim().toLowerCase();
    const filtered = q ? all.filter((a) => usageAcctLabelOf(a).toLowerCase().includes(q)) : all;
    const pageSize = st.drillPageSize || 10;
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (st.drillPage >= pages) st.drillPage = pages - 1;
    if (st.drillPage < 0) st.drillPage = 0;
    const start = st.drillPage * pageSize;
    const pageRows = filtered.slice(start, start + pageSize).map((a) => ({
      label: usageAcctLabelOf(a), total_tokens: a.total_tokens || 0, cost_usd: a.cost_usd || 0, models: a.models || [],
    }));
    if (hintEl) hintEl.textContent = `· ${st.drillRole} — ${filtered.length}개 계정${q ? " (검색됨)" : ""}`;
    if (toolsEl) toolsEl.classList.remove("hidden");
    if (pageRows.length) {
      renderStackedHBar(chartEl, pageRows, "total_tokens", num);
      renderStackedHBar(costChartEl, pageRows, "cost_usd", usd);  // TASK-0184: 계정별 비용 차트(역할별과 일관)
    } else {
      chartEl.innerHTML = "<p class='admin-usage-empty'>검색 결과가 없습니다.</p>";
      if (costChartEl) costChartEl.innerHTML = "";
    }
    if (pagerEl) {
      pagerEl.classList.toggle("hidden", filtered.length <= pageSize);
      if (pageInfoEl) pageInfoEl.textContent = filtered.length ? `${start + 1}–${Math.min(start + pageSize, filtered.length)} / ${filtered.length}` : "0 / 0";
      const prevB = document.getElementById("usageDrillPrev");
      const nextB = document.getElementById("usageDrillNext");
      if (prevB) prevB.disabled = st.drillPage <= 0;
      if (nextB) nextB.disabled = st.drillPage >= pages - 1;
    }
    markActive();
  };
  const toggleAccountDrill = (role) => {
    const st = adminState.usage;
    if (st.drillRole === role) { st.drillRole = null; }  // 같은 역할 재클릭 → 접기
    else {
      st.drillRole = role; st.drillPage = 0; st.drillQuery = "";
      const s = document.getElementById("usageDrillSearch"); if (s) s.value = "";
    }
    renderAccountDrill();
  };
  adminState.usage._renderDrill = renderAccountDrill;  // 컨트롤(검색·페이지)이 호출할 현재 클로저 핸들
  // TASK-0163: fmt 에 행 전체(r)도 전달 — "별칭 → 해소모델" 등 다중 필드 표시용.
  // TASK-0177: 인라인 style → .admin-usage-table 클래스 + 숫자 컬럼 우측정렬(align:'right' → td/th.num).
  const tbl = (rows, cols) => {
    if (!rows || !rows.length) return "<p class='admin-usage-empty'>없음</p>";
    const cls = (c) => (c.align === "right" ? " class='num'" : "");
    const head = cols.map((c) => `<th${cls(c)}>${esc(c.label)}</th>`).join("");
    const body = rows.map((r) => "<tr>" + cols.map((c) => `<td${cls(c)}>${esc(c.fmt ? c.fmt(r[c.key], r) : r[c.key])}</td>`).join("") + "</tr>").join("");
    return `<table class='admin-usage-table'><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  };
  const costFmt = (v) => (v && v > 0 ? usd(v) : "—");
  // TASK-0198: by_model row → 차트/색맵에서 쓰는 모델 키(resolved_model 우선, 미상 폴백).
  const modelKeyOf = (m) => ((m.resolved_model && m.resolved_model !== m.model) ? m.resolved_model : (m.model || "(미상)"));
  // TASK-0198: 선택 모델 집합으로 응답을 필터링한 view 를 만든다(백엔드 무변경 — 클라이언트 재계산).
  //   selectedModels=null → 전체. by_model/by_day_model/도넛은 모델 키로 직접 필터,
  //   역할·계정은 models[] 를 추려 토큰/비용을 재합산(선택 모델 기여분만), totals 는 by_model 합으로 재계산.
  const buildView = (data, selSet) => {
    const all = (selSet == null);
    const inSel = (k) => all || selSet.has(k);
    const by_model = (data.by_model || []).filter((m) => inSel(modelKeyOf(m)));
    const by_day_model = (data.by_day_model || []).filter((m) => inSel(m.model));
    const reModels = (models) => (models || []).filter((m) => inSel(m.model));
    const reEntity = (r) => {
      const models = reModels(r.models);
      const total_tokens = models.reduce((a, m) => a + (m.total_tokens || 0), 0);
      const cost_usd = Math.round(models.reduce((a, m) => a + (m.cost_usd || 0), 0) * 10000) / 10000;
      return { ...r, models, total_tokens, cost_usd };
    };
    // 역할·계정: 선택 모델 기여분만 남기고, 그 기여가 0 인 엔티티는 차트/표에서 제외.
    const by_role = all ? (data.by_role || []) : (data.by_role || []).map(reEntity).filter((r) => r.total_tokens > 0 || r.cost_usd > 0);
    const by_account = all ? (data.by_account || []) : (data.by_account || []).map(reEntity).filter((r) => r.total_tokens > 0 || r.cost_usd > 0);
    // totals: 전체면 응답 totals 그대로, 부분 선택이면 by_model 합으로 재계산(prompt/completion/calls/requests/cost).
    let totals;
    if (all) {
      totals = data.totals || {};
    } else {
      const sumK = (k) => by_model.reduce((a, m) => a + (m[k] || 0), 0);
      totals = {
        requests: sumK("requests"), calls: sumK("calls"),
        total_tokens: sumK("total_tokens"), prompt_tokens: sumK("prompt_tokens"),
        completion_tokens: sumK("completion_tokens"),
        cost_usd: Math.round(sumK("cost_usd") * 10000) / 10000,
      };
    }
    return { totals, by_model, by_day_model, by_role, by_account };
  };
  // TASK-0198: 모델 필터 칩 바 — 전체 모델 목록 + 선택 토글. days/gran 동일 캐시로 재렌더(재조회 X).
  const renderModelFilter = (allModelKeys) => {
    const barEl = document.getElementById("usageModelFilter");
    if (!barEl) return;
    const st = adminState.usage;
    const sel = st.selectedModels;  // null=전체
    const isAll = (sel == null);
    // TASK-0204: 칩은 모델명만 — 버튼 내 토큰 개수(admin-usage-chip-tok) 제거(깔끔). 토큰량은
    //   '모델별 비중' 도넛·일별 차트·상세 표에 이미 노출되므로 칩은 순수 필터 토글로 둔다.
    const chip = (key, active) => {
      const sw = `<span class='admin-usage-chip-dot' style='background:${mcol(key)};'></span>`;
      return `<button type='button' class='admin-usage-chip${active ? " is-active" : ""}' data-model-key='${esc(key)}'>${sw}<span class='admin-usage-chip-label'>${esc(key)}</span></button>`;
    };
    const allChip = `<button type='button' class='admin-usage-chip admin-usage-chip--all${isAll ? " is-active" : ""}' data-model-key='__ALL__'>전체</button>`;
    const chips = allModelKeys.map((k) => chip(k, !isAll && sel.has(k))).join("");
    barEl.innerHTML = `<span class='admin-usage-filter-label'>모델</span>${allChip}${chips}`;
    barEl.querySelectorAll(".admin-usage-chip").forEach((b) => {
      b.addEventListener("click", () => {
        const key = b.getAttribute("data-model-key");
        if (key === "__ALL__") { st.selectedModels = null; }
        else {
          const cur = (st.selectedModels == null) ? new Set() : new Set(st.selectedModels);
          if (cur.has(key)) cur.delete(key); else cur.add(key);
          st.selectedModels = (cur.size === 0 || cur.size === allModelKeys.length) ? null : cur;
        }
        st.drillRole = null;  // 모델 변경 시 계정 drill 접기(정합)
        loadUsage({ refetch: false });  // 캐시 재렌더(재조회 X)
      });
    });
  };
  try {
    let data;
    if (refetch) {
      data = await apiFetch(`/api/admin/usage?days=${encodeURIComponent(days)}&gran=${encodeURIComponent(gran)}`);
      const key = `${days}|${gran}`;
      // 기간/단위가 바뀌면 모델 집합이 달라질 수 있으므로 선택을 초기화(전체).
      if (adminState.usage._lastKey !== key) adminState.usage.selectedModels = null;
      adminState.usage._lastRaw = data;
      adminState.usage._lastKey = key;
    } else {
      data = adminState.usage._lastRaw;
      if (!data) { return loadUsage({ refetch: true }); }  // 캐시 없으면 강제 조회
    }
    // TASK-0181: 전역 모델 색맵 — 등장 모델 전체(도넛/일별/stacked 공유)로 1회 구축(원본 기준 — 색 고정).
    const _ms = [];
    (data.by_model || []).forEach((m) => { const k = modelKeyOf(m); if (!_ms.includes(k)) _ms.push(k); });
    (data.by_day_model || []).forEach((m) => { if (m.model && !_ms.includes(m.model)) _ms.push(m.model); });
    (data.by_account || []).forEach((a) => (a.models || []).forEach((m) => { if (m.model && !_ms.includes(m.model)) _ms.push(m.model); }));
    modelColor = colorMapFor(_ms);
    // TASK-0198: 선택 모델 칩 바(원본 모델 전체 기준) + 선택 적용된 view.
    renderModelFilter(_ms);
    const view = buildView(data, adminState.usage.selectedModels);
    const t = view.totals || {};
    const selSet = adminState.usage.selectedModels;
    const isPartial = (selSet != null);
    if (summaryEl) {
      // TASK-0177: dashboard 와 동일한 .metric-card / .summary-metrics 로 통일.
      // TASK-0198: ① 합계 카드(선택 모델 기준) ② 모델별 분리 카드(모델당 토큰/호출/요청/비용).
      const card = (label, val) => `<article class='metric-card admin-usage-metric'><span>${label}</span><strong>${val}</strong></article>`;
      const scopeLabel = isPartial ? `선택 ${selSet.size}개 모델` : "전체 모델";
      const totalsHtml =
        `<div class='admin-usage-summary-head'><span class='admin-usage-summary-scope'>${esc(scopeLabel)}</span></div>` +
        `<div class='summary-metrics'>` +
        card("요청", num(t.requests)) +
        card("호출", num(t.calls)) +
        card("총 토큰", num(t.total_tokens)) +
        card("Prompt", num(t.prompt_tokens)) +
        card("Completion", num(t.completion_tokens)) +
        ((t.cost_usd && t.cost_usd > 0) ? card("추정 비용", usd(t.cost_usd)) : "") +
        `</div>`;
      // TASK-0204: '모델별' 분리 카드 그리드 제거 — 상단 '모델' 칩 바 + '전체' 가 모델별 분리/선택을
      //   이미 담당해 중복이고, hover 결합 dim/접힘(TASK-0202)이 re-render 와 충돌해 잭(즉시 사라짐·
      //   빈 공간·레이아웃 점프)을 유발. 요약은 합계 카드(선택 스코프 기준)만 남긴다.
      summaryEl.innerHTML = totalsHtml;
    }
    // TASK-0164/0166: 일별 stacked / 모델별 도넛 (선택 모델 view 기준).
    renderStacked(dayChartEl, view.by_day_model);
    renderDonut(modelChartEl, view.by_model);
    // TASK-0181: 역할별·계정별 [토큰|비용] 을 모델별 누적(stacked) 막대로 — 어떤 모델로 썼는지 색 분해.
    const roleRows = (view.by_role || []).map((r) => ({
      label: String(r.role == null ? "-" : r.role), total_tokens: r.total_tokens || 0, cost_usd: r.cost_usd || 0, models: r.models || [],
    }));
    // TASK-0184: 계정별 독립 차트 제거 → 역할 토큰/비용 막대 클릭 시 계정 drill-down 펼침.
    renderStackedHBar(roleChartEl, roleRows, "total_tokens", num, toggleAccountDrill);
    renderStackedHBar(roleCostChartEl, roleRows, "cost_usd", usd, toggleAccountDrill);
    // 계정 drill 데이터 보관 후 현재 펼침 상태 재렌더(선택 모델 view 의 by_account 와 정합 유지).
    adminState.usage.byAccount = view.by_account || [];
    renderAccountDrill();
    // 상세 표 — 모델별(별칭→해소 + prompt/completion + 추정비용) / 역할별 / 계정별 (선택 모델 view 기준).
    if (modelEl) modelEl.innerHTML = tbl(view.by_model, [
      { key: "resolved_model", label: "모델", fmt: (v, r) => {
        const alias = r.model == null ? "" : String(r.model);
        const resolved = v == null ? "" : String(v);
        return (!resolved || resolved === alias) ? (alias || "(미상)") : `${alias} → ${resolved}`;
      } },
      { key: "requests", label: "요청", fmt: num, align: "right" }, { key: "calls", label: "호출", fmt: num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "prompt_tokens", label: "prompt", fmt: num, align: "right" }, { key: "completion_tokens", label: "completion", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
    // TASK-0176/0177/0181: 역할별·계정별 표에도 요청(메시지)·호출·추정 비용(차트와 일치).
    // TASK-0198: 부분 모델 선택 시 요청(distinct run_id)·호출은 모델별 분해 불가(대화/호출은 모델 횡단)
    //   → 전체값 노출은 오해 소지라 "—" 로 표시. 토큰·비용은 선택 모델 기여분으로 정확히 재계산됨.
    const dim = () => "—";
    if (roleEl) roleEl.innerHTML = tbl(view.by_role, [
      { key: "role", label: "역할" },
      { key: "requests", label: "요청", fmt: isPartial ? dim : num, align: "right" },
      { key: "calls", label: "호출", fmt: isPartial ? dim : num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
    if (acctEl) acctEl.innerHTML = tbl(view.by_account, [
      { key: "account_id", label: "계정", fmt: (v, r) => (v == null ? "(시스템)" : (r.username ? `${r.username} (#${v})` : `#${v}`)) },
      { key: "role", label: "역할", fmt: (v) => (v == null ? "—" : v) },
      { key: "requests", label: "요청", fmt: isPartial ? dim : num, align: "right" },
      { key: "calls", label: "호출", fmt: isPartial ? dim : num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
  } catch (e) {
    if (summaryEl) summaryEl.textContent = "조회 실패";
  }
}

function switchTab(tabName) {
  adminState.tab = tabName;
  document.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.adminTab === tabName);
  });
  document.querySelectorAll(".admin-pane").forEach((pane) => {
    pane.classList.toggle("is-active", pane.dataset.adminPane === tabName);
  });
  // TASK-0073 Phase C: audit tab 첫 진입 시 첫 페이지 로드.
  if (tabName === "audits" && !adminState.audit.initialized) {
    adminState.audit.initialized = true;
    loadAuditList();
    loadAuditFacets(); // TASK-0158: actor/resource facet 드롭다운 채우기
  }
  // TASK-0136: LLM 사용량 tab 첫 진입 시 로드.
  if (tabName === "usage" && !adminState.usage.initialized) {
    adminState.usage.initialized = true;
    loadUsage();
  }
  // TASK-0095: 설정 tab 첫 진입 시 sub-section 마운트.
  if (tabName === "settings" && !adminState.settings.initialized) {
    adminState.settings.initialized = true;
    mountSettingsSections();
  }
  // TASK-0205: 데이터소스 관리 tab 진입 시 렌더.
  if (tabName === "datasources") {
    renderDatasourcesPane();
  }
}

/* ── TASK-0205/0207: 데이터소스 관리 pane (CRUD, 자격증명 DB 암호화 저장) ─────────────
 * 계정/역할/제품/설정 과 동일한 list-detail nav 패턴 (DESIGN.md §2):
 *   좌측 #datasourceList = 클릭 가능한 .admin-list-row--nav 목록(검색 필터)
 *   우측 #datasourceDetail = 선택 datasource 상세(read) 또는 생성/편집 폼
 * 수정/삭제 액션은 상세 패널 하단에 노출(ds.editable && console.manage 일 때).
 * env 출처(.env 읽기전용) datasource 는 테스트만 가능 — 콘솔에서 수정/삭제 불가. */
function renderDatasourcesPane() {
  const listEl = $("datasourceList");
  const detailEl = $("datasourceDetail");
  if (!listEl || !detailEl) return;
  const canManage = can("console.manage");
  const encReady = Boolean(adminState.datasourcesEncryptionReady);
  const dsList = adminState.datasources || [];

  // 헤더의 "+ 새 데이터소스" 버튼 — 권한 + 암호화키 게이트
  const newBtn = $("newDatasourceBtn");
  if (newBtn) {
    newBtn.style.display = canManage ? "" : "none";
    newBtn.disabled = !encReady;
    newBtn.title = encReady ? "" : "암호화 키(AGENT_DATASOURCE_KEK_V1) 미설정 — 생성 차단";
    newBtn.onclick = () => { adminState._dsSelectedKey = null; _dsSyncListActive(); _dsRenderForm(null); };
  }

  // 검색 input — 한 번만 바인딩(idempotent)
  const searchEl = $("datasourceSearch");
  if (searchEl && searchEl.dataset.bound !== "1") {
    searchEl.dataset.bound = "1";
    searchEl.addEventListener("input", () => { adminState._dsSearch = searchEl.value; _dsRenderList(); });
  }

  _dsRenderList();

  // 상세: 현재 선택이 유효하면 read view, 아니면 안내 empty
  const sel = dsList.find((d) => d.key === adminState._dsSelectedKey);
  if (sel) _dsRenderDetail(sel);
  else { adminState._dsSelectedKey = null; _dsRenderDetailEmpty(); }
}

function _dsRenderList() {
  const listEl = $("datasourceList");
  const countEl = $("datasourceListCount");
  if (!listEl) return;
  const dsList = adminState.datasources || [];
  const q = (adminState._dsSearch || "").trim().toLowerCase();
  const filtered = q
    ? dsList.filter((ds) => (ds.key || "").toLowerCase().includes(q) || (ds.host || "").toLowerCase().includes(q))
    : dsList.slice();
  if (countEl) countEl.textContent = q ? `${filtered.length}/${dsList.length}` : `${dsList.length}`;

  listEl.innerHTML = "";
  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = dsList.length ? "검색 결과 없음" : "등록된 데이터소스가 없습니다.";
    listEl.appendChild(empty);
    return;
  }
  filtered.forEach((ds) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "admin-list-row admin-list-row--nav";
    row.setAttribute("role", "option");
    row.dataset.dsKey = ds.key;
    const isSel = ds.key === adminState._dsSelectedKey;
    if (isSel) row.classList.add("is-active");
    row.setAttribute("aria-selected", isSel ? "true" : "false");

    const main = document.createElement("span");
    main.className = "admin-list-row-main";
    const title = document.createElement("span");
    title.className = "admin-list-row-title";
    const name = document.createElement("span");
    name.className = "admin-list-row-name";
    name.textContent = ds.key;
    title.appendChild(name);
    const eng = document.createElement("span");
    eng.className = "admin-badge"; eng.textContent = ds.engine || "mysql";
    title.appendChild(eng);
    if (ds.source === "env") {
      const b = document.createElement("span"); b.className = "admin-badge admin-badge--muted"; b.textContent = ".env"; title.appendChild(b);
    }
    if (!ds.has_password) {
      const b = document.createElement("span"); b.className = "admin-badge admin-badge--warn"; b.textContent = "비번없음"; title.appendChild(b);
    }
    const meta = document.createElement("span");
    meta.className = "admin-list-row-meta";
    meta.textContent = `${ds.host || "?"}:${ds.port || ""}`;
    main.append(title, meta);
    row.appendChild(main);
    row.addEventListener("click", () => {
      adminState._dsSelectedKey = ds.key;
      _dsSyncListActive();
      _dsRenderDetail(ds);
    });
    listEl.appendChild(row);
  });
}

function _dsSyncListActive() {
  const listEl = $("datasourceList");
  if (!listEl) return;
  listEl.querySelectorAll(".admin-list-row").forEach((r) => {
    const on = r.dataset.dsKey === adminState._dsSelectedKey;
    r.classList.toggle("is-active", on);
    r.setAttribute("aria-selected", on ? "true" : "false");
  });
}

function _dsRenderDetailEmpty() {
  const detailEl = $("datasourceDetail");
  if (!detailEl) return;
  detailEl.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "admin-detail-empty";
  const line = document.createElement("div");
  line.textContent = "데이터소스를 선택하세요.";
  const hint = document.createElement("div");
  hint.className = "admin-detail-hint";
  hint.style.marginTop = "10px";
  hint.textContent = "분석 대상 DB(MySQL·MSSQL)를 등록·수정·삭제합니다. 비밀번호는 envelope 암호화(KEK→DEK)되어 DB 에 저장되고 다시 표시되지 않습니다(write-only).";
  empty.append(line, hint);
  detailEl.appendChild(empty);
}

function _dsKvRow(dl, k, v) {
  const dt = document.createElement("dt"); dt.textContent = k;
  const dd = document.createElement("dd"); dd.textContent = v;
  dl.append(dt, dd);
}

function _dsRenderDetail(ds) {
  const detailEl = $("datasourceDetail");
  if (!detailEl || !ds) return;
  const canManage = can("console.manage");
  const editable = Boolean(ds.editable) && canManage;
  detailEl.innerHTML = "";

  // 헤더 (라벨 + 엔진 뱃지 + 출처)
  const head = document.createElement("div");
  head.className = "admin-detail-head";
  const h = document.createElement("h3");
  h.className = "admin-detail-title";
  h.textContent = ds.key;
  const eng = document.createElement("span"); eng.className = "admin-badge"; eng.textContent = ds.engine || "mysql";
  h.appendChild(eng);
  if (ds.source === "env") { const b = document.createElement("span"); b.className = "admin-badge admin-badge--muted"; b.textContent = ".env 읽기전용"; h.appendChild(b); }
  head.appendChild(h);
  detailEl.appendChild(head);

  // 연결 좌표
  const sec1 = document.createElement("div"); sec1.className = "admin-detail-section";
  const t1 = document.createElement("div"); t1.className = "admin-detail-section-title"; t1.textContent = "연결 좌표"; sec1.appendChild(t1);
  const dl1 = document.createElement("dl"); dl1.className = "admin-kv";
  _dsKvRow(dl1, "호스트", ds.host || "—");
  _dsKvRow(dl1, "포트", ds.port ? String(ds.port) : "—");
  _dsKvRow(dl1, "DB 유저", ds.user || "—");
  // TASK-0213: '기본 참조 DB'(datasource default_db) 폐지 — MSSQL 은 제품 접근가능 DB 로 자동 연결(없으면
  // 중립 tempdb). 데이터소스 레벨 기본 DB 개념 제거.
  sec1.appendChild(dl1);
  detailEl.appendChild(sec1);

  // 출처 · 보안
  const sec2 = document.createElement("div"); sec2.className = "admin-detail-section";
  const t2 = document.createElement("div"); t2.className = "admin-detail-section-title"; t2.textContent = "출처 · 보안"; sec2.appendChild(t2);
  const dl2 = document.createElement("dl"); dl2.className = "admin-kv";
  _dsKvRow(dl2, "출처", ds.source === "env" ? ".env (읽기전용)" : "콘솔 등록 (DB 저장)");
  _dsKvRow(dl2, "비밀번호", ds.has_password ? "설정됨 (write-only)" : "⚠ 없음");
  // TASK-0215: insight-worker 탐색 토글 상태.
  _dsKvRow(dl2, "인사이트 탐색", ds.insight_enabled !== false ? "켜짐 (스키마·테이블 자동 탐색 중)" : "꺼짐 (탐색 안 함)");
  sec2.appendChild(dl2);
  detailEl.appendChild(sec2);

  // 상태 안내 (멀티 datasource flag / 암호화키)
  const note = document.createElement("div");
  note.className = "admin-detail-hint";
  if (!adminState.datasourcesEnabled) {
    note.textContent = "멀티 datasource 비활성(AGENT_MULTI_DATASOURCE_ENABLED=0). 등록은 가능하나 flag 활성화 전까지 동작하지 않습니다.";
  } else if (!adminState.datasourcesEncryptionReady) {
    note.textContent = "⚠ 암호화 키(AGENT_DATASOURCE_KEK_V1) 미설정 — 생성/수정이 차단됩니다. 운영자가 KEK 를 설정하세요.";
  } else {
    note.textContent = "호스트는 사설망/메타데이터 IP 가 차단됩니다(SSRF 방어).";
  }
  detailEl.appendChild(note);

  // 액션
  const actions = document.createElement("div");
  actions.className = "admin-row-actions admin-detail-actions";
  const testBtn = document.createElement("button");
  testBtn.className = "btn-secondary"; testBtn.textContent = "연결 테스트";
  testBtn.addEventListener("click", async () => {
    testBtn.disabled = true; const prev = testBtn.textContent; testBtn.textContent = "테스트 중…";
    try {
      const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(ds.key)}/test`, { method: "POST" });
      showToast(r && r.ok ? `✓ 연결 성공 (${r.elapsed_ms}ms)` : `✗ 실패 (${(r && r.error) || "?"})`, !(r && r.ok));
    } catch (e) { showToast(e.message || "테스트 실패", true); }
    finally { testBtn.disabled = false; testBtn.textContent = prev; }
  });
  actions.appendChild(testBtn);

  if (editable) {
    // TASK-0215: insight-worker 탐색 on/off 토글(즉시 PATCH).
    const _ie = ds.insight_enabled !== false;
    const insightBtn = document.createElement("button");
    insightBtn.className = "btn-secondary";
    insightBtn.textContent = _ie ? "인사이트 탐색 끄기" : "인사이트 탐색 켜기";
    insightBtn.title = _ie
      ? "이 데이터소스를 insight-worker 가 자동 탐색 중 — 클릭 시 탐색 중단"
      : "insight-worker 탐색 비활성 — 클릭 시 탐색 시작";
    insightBtn.addEventListener("click", async () => {
      insightBtn.disabled = true;
      try {
        await apiFetch(`/api/admin/datasources/${encodeURIComponent(ds.key)}`,
          { method: "PATCH", body: JSON.stringify({ insight_enabled: !_ie }) });
        showToast(`'${ds.key}' 인사이트 탐색 ${!_ie ? "활성화" : "비활성화"}됨`);
        await loadAdminData();
        const sel = (adminState.datasources || []).find((d) => d.key === ds.key);
        if (sel) _dsRenderDetail(sel); else _dsRenderDetailEmpty();
      } catch (e) { insightBtn.disabled = false; showToast(e.message || "토글 실패", true); }
    });
    actions.appendChild(insightBtn);

    const editBtn = document.createElement("button");
    editBtn.className = "btn-secondary"; editBtn.textContent = "수정";
    editBtn.addEventListener("click", () => _dsRenderForm(ds));
    const delBtn = document.createElement("button");
    delBtn.className = "btn-danger"; delBtn.textContent = "삭제";
    delBtn.addEventListener("click", () => _dsDelete(ds.key));
    actions.append(editBtn, delBtn);
  } else {
    // 읽기전용 사유 안내 — sticky 액션바 위(앞)에 배치(액션바는 항상 패널 최하단 고정).
    const ro = document.createElement("div");
    ro.className = "admin-detail-hint";
    ro.textContent = ds.source === "env"
      ? ".env 출처 데이터소스입니다 — 콘솔에서 수정/삭제할 수 없습니다. .env.secret 에서 관리하세요."
      : "수정/삭제 권한(console.manage)이 없습니다.";
    detailEl.appendChild(ro);
  }
  detailEl.appendChild(actions);
}

function _dsRenderForm(ds) {
  const detailEl = $("datasourceDetail");
  if (!detailEl) return;
  const isEdit = Boolean(ds);
  detailEl.innerHTML = "";

  const head = document.createElement("div");
  head.className = "admin-detail-head";
  const h = document.createElement("h3");
  h.className = "admin-detail-title";
  h.textContent = isEdit ? `데이터소스 수정 — ${ds.key}` : "새 데이터소스";
  head.appendChild(h);
  detailEl.appendChild(head);

  const form = document.createElement("div");
  form.className = "admin-detail-section admin-ds-form";

  // 신규 생성 시: 라벨은 서버에서 '엔진+호스트+포트' 해시로 자동 생성 → 입력 불필요(이후 수정 가능).
  if (!isEdit) {
    const hint = document.createElement("div");
    hint.className = "admin-detail-hint";
    hint.textContent = "라벨은 엔진·호스트·포트 해시로 자동 생성되며, 이후 자유롭게 변경할 수 있는 표시용 이름입니다. "
      + "데이터소스의 실제 신원은 라벨이 아닌 엔드포인트(호스트·포트)이며, 인사이트·데이터 정합도 엔드포인트 기준으로 유지됩니다.";
    form.appendChild(hint);
  }

  const fields = [
    ...(isEdit ? [["key", "라벨 (표시용 · 변경 가능)", ds.key, false]] : []),
    ["engine", "엔진 (mysql|mssql)", isEdit ? (ds.engine || "mysql") : "mysql", false],
    ["host", "호스트", isEdit ? (ds.host || "") : "", false],
    ["port", "포트", isEdit ? (ds.port || "") : "", false],
    // TASK-0212: user 는 GET 에서 마스킹(보안)돼 수정 시 pre-fill 안 됨 → password 처럼 write-only.
    // 빈값으로 두면 기존 유저 유지(서버도 빈 user 는 무시). 변경 시에만 입력.
    ["user", isEdit ? "DB 유저 (변경 시에만 입력 · RO 권장)" : "DB 유저 (RO 권장)", "", false],
    ["password", isEdit ? "비밀번호 (변경 시에만 입력)" : "비밀번호", "", false],
    // TASK-0213: '기본 참조 DB'(default_db) 필드 폐지 — 접근 DB 는 제품의 '접근 가능 데이터베이스'(allowlist)로
    // 관리하고, MSSQL 연결은 그 중 첫 DB 로 자동(없으면 중립 tempdb). 데이터소스에 기본 DB 를 두지 않는다.
  ];
  const inputs = {};
  fields.forEach(([k, label, val, ro]) => {
    const wrap = document.createElement("label"); wrap.className = "admin-field";
    const span = document.createElement("span"); span.className = "admin-field-label"; span.textContent = label;
    const inp = document.createElement("input");
    inp.type = (k === "password") ? "password" : "text";
    inp.value = val; inp.readOnly = ro; inp.autocomplete = "off";
    if (ro) inp.classList.add("is-readonly");
    wrap.append(span, inp); form.appendChild(wrap); inputs[k] = inp;
  });
  detailEl.appendChild(form);

  const actions = document.createElement("div");
  actions.className = "admin-row-actions admin-detail-actions";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn-primary"; saveBtn.textContent = isEdit ? "저장" : "생성";
  saveBtn.addEventListener("click", async () => {
    const body = {};
    Object.keys(inputs).forEach((k) => {
      const v = inputs[k].value.trim();
      // TASK-0212: password·user 는 write-only(수정 시 GET 마스킹으로 pre-fill 불가) — 빈값이면 미전송(미변경).
      // 빈 user 를 보내면 서버가 DbUser 를 wipe 해 연결 테스트가 깨지던 회귀 방지.
      if (k === "password" || (isEdit && k === "user")) { if (v) body[k] = v; }
      else if (isEdit && k === "key") { if (v && v !== ds.key) body.key = v; }  // 수정: key 변경 시에만 전송
      else if (!isEdit && k === "key") { /* 신규: 서버 자동생성, 미전송 */ }
      else body[k] = v;
    });
    saveBtn.disabled = true;
    try {
      if (isEdit) {
        const updated = await apiFetch(`/api/admin/datasources/${encodeURIComponent(ds.key)}`, { method: "PATCH", body: JSON.stringify(body) });
        // 호스트/포트 변경 시 키(해시)도 변경됨 — 응답의 key 로 선택 동기화.
        const updatedKey = (updated && updated.key) || ds.key;
        showToast(`데이터소스 '${updatedKey}' 수정됨`);
        adminState._dsSelectedKey = updatedKey;
      } else {
        const created = await apiFetch(`/api/admin/datasources`, { method: "POST", body: JSON.stringify(body) });
        // 서버가 엔진+호스트+포트 해시로 key 를 자동 생성해 응답 — 그 canonical key 로 자동 선택.
        const canonicalKey = (created && created.key);
        showToast(`데이터소스 '${canonicalKey}' 생성됨 (라벨 자동 생성)`);
        adminState._dsSelectedKey = canonicalKey;
      }
      await loadAdminData();
      renderDatasourcesPane();
    } catch (e) { saveBtn.disabled = false; showToast(e.message || "저장 실패", true); }
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn-secondary"; cancelBtn.textContent = "취소";
  cancelBtn.addEventListener("click", () => {
    const sel = (adminState.datasources || []).find((d) => d.key === adminState._dsSelectedKey);
    if (sel) _dsRenderDetail(sel); else _dsRenderDetailEmpty();
  });
  actions.append(saveBtn, cancelBtn);
  detailEl.appendChild(actions);
}

async function _dsDelete(key) {
  if (!confirm(`데이터소스 '${key}' 를 삭제할까요?`)) return;
  try {
    await apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}`, { method: "DELETE" });
    showToast(`'${key}' 삭제됨`);
    if (adminState._dsSelectedKey === key) adminState._dsSelectedKey = null;
    await loadAdminData(); renderDatasourcesPane();
  } catch (e) {
    if (e.status === 409) {
      if (confirm(`'${key}' 는 제품에 바인딩되어 있습니다. 강제 삭제(바인딩 해제)할까요?`)) {
        try {
          await apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}?force=1`, { method: "DELETE" });
          showToast(`'${key}' 강제 삭제됨`);
          if (adminState._dsSelectedKey === key) adminState._dsSelectedKey = null;
          await loadAdminData(); renderDatasourcesPane();
        } catch (e2) { showToast(e2.message || "삭제 실패", true); }
      }
    } else { showToast(e.message || "삭제 실패", true); }
  }
}

/* ── Settings pane (TASK-0096 v2: 계정/역할/제품 과 동일한 list-detail 패턴) ─
 * 새 항목 추가 절차:
 *   1) admin.html 의 #settingsList 에 <button class="admin-list-row admin-list-row--nav"
 *      data-settings-tab="X" data-settings-group="..." data-settings-keywords="..."> 추가
 *   2) #settingsDetail 에 <article class="admin-settings-panel" data-settings-panel="X"> 추가
 *   3) SETTINGS_PANEL_MOUNTERS 에 X 키로 마운트 함수 등록
 * 마운트 함수는 panel 이 처음 활성화될 때 1회 실행. 권한 게이트는 함수 내부에서. */

adminState.settings = {
  initialized: false,
  activeTab: "global-prompt",
  mountedPanels: new Set(),
};

const SETTINGS_PANEL_MOUNTERS = {
  "global-prompt": mountGlobalPromptPanel,
};

function mountSettingsSections() {
  bindSettingsList();
  bindSettingsSearch();
  updateSettingsListCount();
  activateSettingsPanel(adminState.settings.activeTab);
}

function bindSettingsList() {
  const list = $("settingsList");
  if (!list || list.dataset.bound === "1") return;
  list.dataset.bound = "1";
  list.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-settings-tab]");
    if (!btn || !list.contains(btn)) return;
    const tab = btn.getAttribute("data-settings-tab");
    if (tab) activateSettingsPanel(tab);
  });
}

function bindSettingsSearch() {
  const input = $("settingsSearch");
  if (!input || input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  input.addEventListener("input", () => {
    applySettingsSearchFilter(input.value);
  });
}

function applySettingsSearchFilter(query) {
  const list = $("settingsList");
  if (!list) return;
  const q = (query || "").trim().toLowerCase();
  list.querySelectorAll(".admin-list-row[data-settings-tab]").forEach((row) => {
    if (!q) {
      row.style.display = "";
      return;
    }
    const haystack = [
      row.getAttribute("data-settings-tab") || "",
      row.getAttribute("data-settings-group") || "",
      row.getAttribute("data-settings-keywords") || "",
      row.textContent || "",
    ].join(" ").toLowerCase();
    row.style.display = haystack.includes(q) ? "" : "none";
  });
  updateSettingsListCount();
}

function updateSettingsListCount() {
  const list = $("settingsList");
  const countEl = $("settingsListCount");
  if (!list || !countEl) return;
  const rows = list.querySelectorAll(".admin-list-row[data-settings-tab]");
  const visible = Array.from(rows).filter((row) => row.style.display !== "none").length;
  countEl.textContent = visible === rows.length
    ? `${rows.length}건`
    : `${visible} / ${rows.length}건`;
}

function activateSettingsPanel(tab) {
  const list = $("settingsList");
  const content = $("settingsDetail");
  if (!list || !content) return;
  adminState.settings.activeTab = tab;
  list.querySelectorAll("[data-settings-tab]").forEach((btn) => {
    const isActive = btn.getAttribute("data-settings-tab") === tab;
    btn.classList.toggle("is-active", isActive);
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  content.querySelectorAll("[data-settings-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.getAttribute("data-settings-panel") === tab);
  });
  if (!adminState.settings.mountedPanels.has(tab)) {
    const mounter = SETTINGS_PANEL_MOUNTERS[tab];
    if (typeof mounter === "function") {
      try {
        mounter();
      } catch (err) {
        console.error("[settings] panel mount failed:", tab, err);
      }
    }
    adminState.settings.mountedPanels.add(tab);
  }
}

function mountGlobalPromptPanel() {
  const mount = $("globalPromptEditorMount");
  if (!mount) return;
  if (!can("system_prompt.global.read")) {
    mount.innerHTML = '<div class="admin-detail-empty">전역 시스템 프롬프트 조회 권한이 없습니다.</div>';
    return;
  }
  mount.innerHTML = "";
  const editor = buildSystemPromptEditor({
    scope: "global",
    title: "본문",
    hint: can("system_prompt.global.write")
      ? "비워두고 적용하면 코드 상수 fallback 으로 회귀합니다. 변경사항은 하단 '모두 적용' 으로 일괄 저장됩니다."
      : "조회 전용 — 수정 권한이 없습니다.",
  });
  if (!can("system_prompt.global.write")) {
    const ta = editor.querySelector("textarea.admin-prompt-textarea");
    if (ta) ta.disabled = true;
  }
  mount.appendChild(editor);
}

/* ── Audit pane (TASK-0073 Phase C) ─────────────────────────────────── */

adminState.audit = {
  items: [],
  selectedId: null,
  nextCursor: null,
  scope: "",
  loading: false,
  initialized: false,
  filters: {
    action_code: "",
    resource_type: "",
    actor_account_id: "",
    actor_type: "",
    from_at: "",
    to_at: "",
    q: "",
  },
};

function _auditEscapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function _auditFormatDt(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ko-KR", { hour12: false });
  } catch {
    return String(iso);
  }
}

function _readAuditFilters() {
  const f = adminState.audit.filters;
  f.action_code = ($("auditFilterAction")?.value || "").trim();
  f.resource_type = ($("auditFilterResourceType")?.value || "").trim();
  f.actor_account_id = ($("auditFilterActorId")?.value || "").trim();
  f.actor_type = ($("auditFilterActorType")?.value || "").trim();
  f.from_at = ($("auditFilterFromAt")?.value || "").trim();
  f.to_at = ($("auditFilterToAt")?.value || "").trim();
  f.q = ($("auditFilterQ")?.value || "").trim();
}

function _clearAuditFilters() {
  ["auditFilterAction", "auditFilterResourceType", "auditFilterActorId",
   "auditFilterActorType", "auditFilterFromAt", "auditFilterToAt", "auditFilterQ"].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  adminState.audit.filters = {
    action_code: "", resource_type: "", actor_account_id: "",
    actor_type: "", from_at: "", to_at: "", q: "",
  };
}

async function loadAuditList(append = false) {
  if (adminState.audit.loading) return;
  adminState.audit.loading = true;
  if (!append) {
    adminState.audit.items = [];
    adminState.audit.nextCursor = null;
    adminState.audit.selectedId = null;
  }
  const params = new URLSearchParams();
  const f = adminState.audit.filters;
  Object.entries(f).forEach(([k, v]) => {
    if (v) params.set(k, v);
  });
  if (append && adminState.audit.nextCursor) {
    params.set("cursor", adminState.audit.nextCursor);
  }
  params.set("limit", "100");
  try {
    const resp = await fetch(`/api/admin/audits?${params.toString()}`);
    if (!resp.ok) {
      showToast(`감사 로그 조회 실패 (${resp.status})`, true);
      adminState.audit.loading = false;
      return;
    }
    const data = await resp.json();
    adminState.audit.scope = data.scope || "";
    adminState.audit.nextCursor = data.next_cursor || null;
    const fresh = data.items || [];
    if (append) {
      adminState.audit.items = adminState.audit.items.concat(fresh);
    } else {
      adminState.audit.items = fresh;
    }
    renderAuditList();
  } catch (exc) {
    showToast(`감사 로그 조회 실패: ${exc}`, true);
  } finally {
    adminState.audit.loading = false;
  }
}

function renderAuditList() {
  const listEl = $("auditList");
  const countEl = $("auditListCount");
  const scopeEl = $("auditListScope");
  const moreBtn = $("auditLoadMoreBtn");
  if (!listEl) return;
  const items = adminState.audit.items;
  if (countEl) countEl.textContent = `${items.length}건`;
  if (scopeEl) scopeEl.textContent = `(scope: ${adminState.audit.scope || "—"})`;
  if (moreBtn) moreBtn.style.display = adminState.audit.nextCursor ? "" : "none";

  // CSV export gate (audit.export 권한 필요 — me 의 permissions 검사).
  const csvBtn = $("auditExportCsvBtn");
  if (csvBtn) {
    const hasExport = Boolean(adminState.me?.permissions?.["audit.export"]);
    csvBtn.style.display = hasExport ? "" : "none";
    if (hasExport) {
      const params = new URLSearchParams();
      Object.entries(adminState.audit.filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      csvBtn.href = `/api/admin/audits/export.csv?${params.toString()}`;
    }
  }
  // TASK-0158: audit.purge 버튼 가시성 (파괴적 — audit.purge 권한자만 노출).
  const purgeBtn = $("auditPurgeBtn");
  if (purgeBtn) {
    purgeBtn.style.display = Boolean(adminState.me?.permissions?.["audit.purge"]) ? "" : "none";
  }

  if (items.length === 0) {
    listEl.innerHTML = '<div class="admin-list-empty">이벤트 없음</div>';
    return;
  }
  // Build rows.
  const rows = items.map((it) => {
    const isSel = String(it.id) === String(adminState.audit.selectedId);
    const klass = "admin-list-row admin-audit-row" + (isSel ? " is-selected" : "");
    return `
      <div class="${klass}" role="row" data-audit-id="${it.id}">
        <div class="admin-audit-row-line">
          <span class="admin-audit-row-action">${_auditEscapeHtml(it.action_code || "")}</span>
          <span class="admin-audit-row-actor">${_auditEscapeHtml(it.actor_type || "")}${
            it.actor_account_id ? " · #" + it.actor_account_id : ""
          }</span>
          <span class="admin-audit-row-ts">${_auditEscapeHtml(_auditFormatDt(it.occurred_at))}</span>
        </div>
        <div class="admin-audit-row-line muted">
          <span class="admin-audit-row-resource">${_auditEscapeHtml(it.resource_type || "")}${
            it.resource_id ? " #" + _auditEscapeHtml(it.resource_id) : ""
          }</span>
          ${it.target_account_id ? `<span class="admin-audit-row-target">→ target #${it.target_account_id}</span>` : ""}
        </div>
      </div>`;
  }).join("");
  listEl.innerHTML = rows;
  listEl.querySelectorAll(".admin-audit-row").forEach((rowEl) => {
    rowEl.addEventListener("click", () => {
      const id = rowEl.dataset.auditId;
      adminState.audit.selectedId = id;
      renderAuditList();
      renderAuditDetail(id);
    });
  });
}

function renderAuditDetail(id) {
  const el = $("auditDetail");
  if (!el) return;
  const item = adminState.audit.items.find((it) => String(it.id) === String(id));
  if (!item) {
    el.innerHTML = '<div class="admin-detail-empty">이벤트를 선택하세요.</div>';
    return;
  }
  // ChangeJson + MaskedFields 안전 직렬화 + HTML escape (TASK-0058 share.html 패턴 답습).
  const changeText = item.change_json == null ? "(없음)" : JSON.stringify(item.change_json, null, 2);
  const maskedText = Array.isArray(item.masked_fields) && item.masked_fields.length
    ? item.masked_fields.join(", ")
    : "(없음)";
  el.innerHTML = `
    <div class="admin-audit-detail">
      <h3>감사 이벤트 #${_auditEscapeHtml(item.id)}</h3>
      <dl class="admin-audit-detail-fields">
        <dt>발생 시각</dt><dd>${_auditEscapeHtml(_auditFormatDt(item.occurred_at))}</dd>
        <dt>Action</dt><dd><code>${_auditEscapeHtml(item.action_code || "")}</code></dd>
        <dt>Actor</dt><dd>${_auditEscapeHtml(item.actor_type || "")}${
          item.actor_account_id ? " · 계정 #" + _auditEscapeHtml(item.actor_account_id) : ""
        }</dd>
        <dt>Target Account</dt><dd>${item.target_account_id ? "#" + _auditEscapeHtml(item.target_account_id) : "(없음)"}</dd>
        <dt>Resource</dt><dd>${_auditEscapeHtml(item.resource_type || "")}${
          item.resource_id ? " #" + _auditEscapeHtml(item.resource_id) : ""
        }</dd>
        <dt>Session</dt><dd>${item.session_id ? "<code>" + _auditEscapeHtml(item.session_id) + "</code>" : "(없음)"}</dd>
        <dt>Remote Addr</dt><dd>${_auditEscapeHtml(item.remote_addr || "(없음)")}</dd>
        <dt>User-Agent</dt><dd class="admin-audit-detail-ua">${_auditEscapeHtml(item.user_agent || "(없음)")}</dd>
        <dt>Request ID</dt><dd>${item.request_id ? "<code>" + _auditEscapeHtml(item.request_id) + "</code>" : "(없음)"}</dd>
        <dt>Masked Fields</dt><dd>${_auditEscapeHtml(maskedText)}</dd>
      </dl>
      <h4>Change JSON</h4>
      <pre class="admin-audit-detail-change">${_auditEscapeHtml(changeText)}</pre>
    </div>`;
}

function attachAuditFilterHandlers() {
  const applyBtn = $("auditFilterApplyBtn");
  const clearBtn = $("auditFilterClearBtn");
  const moreBtn = $("auditLoadMoreBtn");
  if (applyBtn) {
    applyBtn.addEventListener("click", () => {
      _readAuditFilters();
      loadAuditList(false);
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      _clearAuditFilters();
      loadAuditList(false);
    });
  }
  if (moreBtn) {
    moreBtn.addEventListener("click", () => loadAuditList(true));
  }
  // Enter on input → apply.
  ["auditFilterAction", "auditFilterResourceType", "auditFilterActorId", "auditFilterQ"].forEach((id) => {
    const el = $(id);
    if (el) {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          _readAuditFilters();
          loadAuditList(false);
        }
      });
    }
  });
  // TASK-0158: audit.purge 진입점 바인딩 (파괴적 — dry-run 미리보기 + typed-confirm).
  const purgeBtn = $("auditPurgeBtn");
  if (purgeBtn && !purgeBtn.dataset.bound) {
    purgeBtn.dataset.bound = "1";
    purgeBtn.addEventListener("click", () => openAuditPurgeModal());
  }
}

// TASK-0158: 감사 필터 facet — actor/resource 드롭다운 채우기 (GET /api/admin/audits/{actors,resources}).
// 이전엔 두 facet 엔드포인트에 호출자가 없어 필터가 free-text only 였다.
async function loadAuditFacets() {
  const resourceDl = $("auditResourceTypeOptions");
  if (resourceDl) {
    try {
      const r = await apiFetch("/api/admin/audits/resources");
      resourceDl.innerHTML = (r.items || [])
        .map((it) => `<option value="${_auditEscapeHtml(it.resource_type || "")}"></option>`)
        .join("");
    } catch (e) { /* facet 실패는 비차단 */ }
  }
  const actorDl = $("auditActorOptions");
  if (actorDl) {
    try {
      const a = await apiFetch("/api/admin/audits/actors");
      actorDl.innerHTML = (a.items || [])
        .map((it) => `<option value="${Number(it.actor_account_id) || ""}">${_auditEscapeHtml(it.username || "")}</option>`)
        .join("");
    } catch (e) { /* */ }
  }
}

// TASK-0158: audit.purge 모달 — 기준 날짜 → dry-run 미리보기 → 건수 typed-confirm → 실 삭제.
function openAuditPurgeModal() {
  const overlay = document.createElement("div");
  overlay.className = "admin-modal-overlay";
  const d = new Date(Date.now() - 90 * 86400000);
  const defCutoff = d.toISOString().slice(0, 10);
  overlay.innerHTML =
    '<div class="admin-modal" role="dialog" aria-modal="true">' +
    '  <h3>감사 로그 정리 (purge)</h3>' +
    '  <p class="admin-modal-note">기준 날짜 <strong>이전</strong>의 감사 로그를 영구 삭제합니다. 되돌릴 수 없습니다. 먼저 미리보기로 삭제 대상 건수를 확인하세요.</p>' +
    '  <label class="admin-modal-field">기준 날짜 (이 날짜 0시 이전 삭제)' +
    `    <input type="date" id="purgeCutoff" class="field-input" value="${defCutoff}" />` +
    '  </label>' +
    '  <div class="admin-modal-preview" id="purgePreview">미리보기를 눌러 삭제 대상을 확인하세요.</div>' +
    '  <div class="admin-modal-actions">' +
    '    <button type="button" class="btn-secondary" id="purgeCancelBtn">취소</button>' +
    '    <button type="button" class="btn-secondary" id="purgeDryRunBtn">미리보기</button>' +
    '    <button type="button" class="btn-danger" id="purgeRunBtn" disabled>삭제 실행</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  const close = () => {
    if (overlay.parentNode) document.body.removeChild(overlay);
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const cutoffEl = $("purgeCutoff");
  const previewEl = $("purgePreview");
  const runBtn = $("purgeRunBtn");
  let lastCount = -1;
  const cutoffIso = () => (cutoffEl.value ? new Date(cutoffEl.value + "T00:00:00").toISOString() : "");
  $("purgeCancelBtn").addEventListener("click", close);
  $("purgeDryRunBtn").addEventListener("click", async () => {
    const cutoff = cutoffIso();
    if (!cutoff) { showToast("기준 날짜를 선택하세요.", true); return; }
    previewEl.textContent = "미리보기 중…";
    runBtn.disabled = true;
    try {
      const r = await apiFetch("/api/admin/audits/purge", {
        method: "POST", body: JSON.stringify({ cutoff, dry_run: true }),
      });
      lastCount = Number(r.to_purge) || 0;
      previewEl.textContent = `삭제 대상: ${lastCount}건 (${formatDateTime(cutoff)} 이전)`;
      runBtn.disabled = lastCount <= 0;
    } catch (e) {
      previewEl.textContent = "미리보기 실패: " + (e.message || "");
    }
  });
  runBtn.addEventListener("click", async () => {
    const cutoff = cutoffIso();
    if (!cutoff || lastCount <= 0) return;
    const typed = window.prompt(`정말 ${lastCount}건을 영구 삭제하시겠습니까?\n확인하려면 삭제 건수(${lastCount})를 그대로 입력하세요.`);
    if (typed == null) return;
    if (String(typed).trim() !== String(lastCount)) { showToast("입력이 일치하지 않아 취소했습니다.", true); return; }
    runBtn.disabled = true;
    try {
      const r = await apiFetch("/api/admin/audits/purge", {
        method: "POST", body: JSON.stringify({ cutoff, dry_run: false }),
      });
      showToast(`감사 로그 ${Number(r.purged) || 0}건을 삭제했습니다.`);
      close();
      loadAuditList(false);
    } catch (e) {
      runBtn.disabled = false;
      showToast("삭제 실패: " + (e.message || ""), true);
    }
  });
}

// TASK-0158: 첨부 DB 권한 drift 진단 카드 (GET /api/admin/health/attachment-grants, console.access).
async function loadGrantHealth() {
  const el = $("dashboardGrantHealth");
  if (!el) return;
  if (!can("console.access")) { el.innerHTML = ""; return; }
  try {
    const r = await apiFetch("/api/admin/health/attachment-grants");
    const healthy = Boolean(r.healthy);
    const drift = Array.isArray(r.drift) ? r.drift : [];
    const driftCount = Number(r.drift_count) || drift.length;
    const badge = healthy
      ? '<strong class="grant-health-ok">정상</strong>'
      : `<strong class="grant-health-bad">${driftCount}건 drift</strong>`;
    let detail = "";
    if (!healthy && drift.length) {
      detail = '<ul class="grant-health-detail">' + drift.map((dd) =>
        `<li><code>${_auditEscapeHtml(dd.schema_name || "")}</code>: ${_auditEscapeHtml([].concat(dd.missing || [], dd.extra || []).join(", "))}</li>`
      ).join("") + "</ul>";
    }
    el.innerHTML = `<article class="metric-card grant-health-card"><span>첨부 DB 권한 상태</span>${badge}${detail}</article>`;
  } catch (e) {
    el.innerHTML = "";
  }
}

/* ── Dashboard pane (TASK-0210: 카테고리 위젯 그리드 + per-account 커스터마이즈) ──
 *
 * 기존 6개 metric 카드(클라 배열 계산)를 카테고리별 풍부한 위젯 그리드로 대체.
 * 위젯 데이터는 GET /api/admin/overview 가 RBAC-스코프로 반환(보유 권한 위젯만);
 * 표시/순서는 GET·PUT /api/admin/dashboard/preferences 로 계정별 영속.
 *   server 위젯: accounts/roles/products/datasources/conversations/audits/usage
 *   client 위젯: grant_health(별도 엔드포인트)·pending(미저장 변경 — 클라 상태)
 */

function _dashFmtValue(v, fmt) {
  if (fmt === "usd") {
    return "$" + Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  const n = Number(v);
  if (v != null && !Number.isNaN(n)) return n.toLocaleString();
  return String(v == null ? "—" : v);
}

// TASK-0218: 전기간 대비 델타 배지(▲▼%). sentiment 로 색 의미 분기:
//   neutral=증감 무관 회색, bad=증가가 부정(비용)→증가 적색/감소 녹색, good=반대.
function _dashDeltaBadge(pct, sentiment) {
  if (pct == null || Number.isNaN(Number(pct))) return null;
  const n = Number(pct);
  const up = n >= 0;
  let tone = "neutral";
  if (sentiment === "bad") tone = up ? "bad" : "good";
  else if (sentiment === "good") tone = up ? "good" : "bad";
  const span = document.createElement("span");
  span.className = "dashboard-delta delta-" + tone;
  span.textContent = (up ? "▲ " : "▼ ") + Math.abs(n) + "%";
  span.setAttribute("title", `직전 동일 기간 대비 ${up ? "증가" : "감소"} ${Math.abs(n)}%`);
  return span;
}

// TASK-0218: 순수 SVG sparkline(외부 라이브러리 0 — baked 정책). 시계열 ≥2 점일 때만.
function _dashSparkline(values, sentiment) {
  if (!Array.isArray(values) || values.length < 2) return null;
  const w = 96, h = 26, pad = 2;
  const max = Math.max.apply(null, values.concat([1]));
  const min = Math.min.apply(null, values.concat([0]));
  const range = max - min || 1;
  const step = (w - pad * 2) / (values.length - 1);
  const xy = (v, i) => [pad + i * step, h - pad - ((v - min) / range) * (h - pad * 2)];
  const pts = values.map((v, i) => xy(v, i).map((c) => c.toFixed(1)).join(",")).join(" ");
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "dashboard-spark" + (sentiment ? " spark-" + sentiment : ""));
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  const poly = document.createElementNS(ns, "polyline");
  poly.setAttribute("points", pts);
  svg.appendChild(poly);
  const [lx, ly] = xy(values[values.length - 1], values.length - 1);
  const dot = document.createElementNS(ns, "circle");
  dot.setAttribute("cx", lx.toFixed(1));
  dot.setAttribute("cy", ly.toFixed(1));
  dot.setAttribute("r", "2");
  svg.appendChild(dot);
  return svg;
}

// renderDashboard 는 탭 진입/새로고침/pending 변경 때마다 호출된다(기존 호출처 유지).
// 최초 1회 overview+prefs 를 fetch 하고 이후엔 캐시로 즉시 재렌더(pending 위젯만 갱신).
function renderDashboard() {
  wireDashboardControls();
  loadDashboardOverview(false);
}

function wireDashboardControls() {
  if (adminState._dashboardWired) return;
  adminState._dashboardWired = true;
  const win = $("dashboardWindow");
  if (win) {
    win.value = String(adminState.dashboardWindow || 7);
    win.addEventListener("change", () => {
      const d = parseInt(win.value, 10);
      adminState.dashboardWindow = Number.isNaN(d) ? 7 : d;
      adminState.dashboardLoaded = false;
      loadDashboardOverview(true);
    });
  }
  // TASK-0218: 수동 새로고침 — 운영 대시보드는 "지금 데이터"를 직접 갱신할 수 있어야 함.
  const refreshBtn = $("dashboardRefreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => { adminState.dashboardLoaded = false; loadDashboardOverview(true); });
  }
  // TASK-0218: auto-refresh 토글(off/30s/60s). 대시보드 탭일 때만 재조회.
  const auto = $("dashboardAutoRefresh");
  if (auto) {
    auto.value = String(adminState.dashboardAutoRefreshSec || 0);
    auto.addEventListener("change", () => {
      const s = parseInt(auto.value, 10) || 0;
      adminState.dashboardAutoRefreshSec = s;
      _setDashboardAutoRefresh(s);
    });
  }
  const editBtn = $("dashboardEditToggle");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      adminState.dashboardEditMode = !adminState.dashboardEditMode;
      if (editBtn) editBtn.setAttribute("aria-pressed", String(adminState.dashboardEditMode));
      renderDashboardWidgets();
    });
  }
  const saveBtn = $("dashboardSaveBtn");
  if (saveBtn) saveBtn.addEventListener("click", saveDashboardPrefs);
  const resetBtn = $("dashboardResetBtn");
  if (resetBtn) resetBtn.addEventListener("click", resetDashboardPrefs);
}

function _setDashboardAutoRefresh(seconds) {
  if (adminState._dashboardAutoTimer) {
    clearInterval(adminState._dashboardAutoTimer);
    adminState._dashboardAutoTimer = null;
  }
  if (seconds && seconds > 0) {
    adminState._dashboardAutoTimer = setInterval(() => {
      if (adminState.tab === "dashboard" && !adminState.dashboardEditMode && !adminState.dashboardLoading) {
        adminState.dashboardLoaded = false;
        loadDashboardOverview(true);
      }
    }, seconds * 1000);
  }
}

function _fmtClock(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

async function loadDashboardOverview(force) {
  if (adminState.dashboardLoading) return;
  if (adminState.dashboardLoaded && !force) { renderDashboardWidgets(); return; }
  adminState.dashboardLoading = true;
  _updateDashboardMeta();  // "갱신 중…" 표시
  try {
    const days = adminState.dashboardWindow || 7;
    const [overview, prefsResp] = await Promise.all([
      apiFetch(`/api/admin/overview?days=${encodeURIComponent(days)}`).catch((e) => ({ _error: e })),
      apiFetch("/api/admin/dashboard/preferences").catch((e) => ({ _error: e })),
    ]);
    // TASK-0218 fail-loud: overview fetch 실패를 빈 카탈로그로 숨기지 않고 오류 상태로 보존.
    if (overview && !overview._error) {
      adminState.overview = overview;
      adminState.dashboardError = null;
      adminState.dashboardLastUpdated = new Date();
    } else {
      adminState.dashboardError = (overview && overview._error && overview._error.message) || "대시보드 데이터를 불러오지 못했습니다.";
      if (!adminState.overview) adminState.overview = { catalog: [], widgets: {} };
    }
    if (prefsResp && !prefsResp._error && prefsResp.preferences) {
      adminState.dashboardPrefs = prefsResp.preferences;
      adminState.dashboardDefaults = prefsResp.defaults || null;
    } else if (!adminState.dashboardPrefs) {
      adminState.dashboardPrefs = { version: 1, widgets: [] };
    }
    adminState.dashboardLoaded = !adminState.dashboardError;
  } finally {
    adminState.dashboardLoading = false;
  }
  renderDashboardWidgets();
}

// toolbar 의 "마지막 갱신 HH:MM:SS" 라벨 갱신(데이터 신선도 — CloudWatch 패턴).
function _updateDashboardMeta() {
  const el = $("dashboardUpdated");
  if (!el) return;
  if (adminState.dashboardLoading) { el.textContent = "갱신 중…"; return; }
  if (adminState.dashboardError) { el.textContent = "갱신 실패"; return; }
  el.textContent = adminState.dashboardLastUpdated
    ? "마지막 갱신 " + _fmtClock(adminState.dashboardLastUpdated)
    : "";
}

// catalog(서버 권위 위젯 목록) + prefs(표시/순서)를 합쳐 최종 렌더 순서를 만든다.
// catalog 에 없는(권한 없는) 위젯은 제외 → 권한 회수 시 자동 숨김.
function _dashboardRenderOrder() {
  const catalog = (adminState.overview && adminState.overview.catalog) || [];
  const prefs = (adminState.dashboardPrefs && adminState.dashboardPrefs.widgets) || [];
  const prefByKey = new Map(prefs.map((w) => [w.key, w]));
  const items = catalog.map((c, idx) => {
    const p = prefByKey.get(c.key);
    return {
      key: c.key,
      title: c.title,
      source: c.source,
      visible: p ? p.visible !== false : true,
      order: p && typeof p.order === "number" ? p.order : idx,
      catalogIdx: idx,
    };
  });
  items.sort((a, b) => (a.order - b.order) || (a.catalogIdx - b.catalogIdx));
  return items;
}

function renderDashboardWidgets() {
  const wrap = $("dashboardWidgets");
  if (!wrap) return;
  const editing = !!adminState.dashboardEditMode;
  const editBar = $("dashboardEditBar");
  if (editBar) editBar.hidden = !editing;
  const editBtn = $("dashboardEditToggle");
  if (editBtn) editBtn.textContent = editing ? "완료" : "편집";
  _updateDashboardMeta();

  const items = _dashboardRenderOrder();
  wrap.classList.toggle("is-editing", editing);
  wrap.innerHTML = "";

  // TASK-0218 fail-loud: 전체 overview 실패 시 빈 화면 대신 오류 배너 + 재시도.
  if (adminState.dashboardError && !items.length) {
    wrap.appendChild(_buildDashboardErrorBanner());
    return;
  }
  if (adminState.dashboardError) {
    wrap.appendChild(_buildDashboardErrorBanner());
  }

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "표시할 위젯이 없습니다.";
    wrap.appendChild(empty);
    return;
  }
  const shown = editing ? items : items.filter((it) => it.visible);
  if (!shown.length && !editing) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "모든 위젯이 숨김 상태입니다. 우측 상단 “편집”에서 표시할 위젯을 선택하세요.";
    wrap.appendChild(empty);
    return;
  }
  shown.forEach((it, i) => wrap.appendChild(buildWidgetCard(it, i, shown.length)));
  // client-rendered: grant_health 는 별도 엔드포인트로 채운다.
  if ($("dashboardGrantHealth")) loadGrantHealth();
}

function _buildDashboardErrorBanner() {
  const b = document.createElement("div");
  b.className = "dashboard-error-banner";
  b.setAttribute("role", "alert");
  const msg = document.createElement("span");
  msg.textContent = "⚠ " + (adminState.dashboardError || "대시보드 데이터를 불러오지 못했습니다.");
  b.appendChild(msg);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "btn-secondary";
  retry.textContent = "다시 시도";
  retry.addEventListener("click", () => { adminState.dashboardLoaded = false; loadDashboardOverview(true); });
  b.appendChild(retry);
  return b;
}

function buildWidgetCard(it, idx, total) {
  const editing = !!adminState.dashboardEditMode;
  const card = document.createElement("article");
  card.className = "dashboard-widget";
  card.dataset.widget = it.key;
  card.setAttribute("role", "group");
  card.setAttribute("aria-label", it.title + " 위젯");
  if (editing && !it.visible) card.classList.add("widget-hidden");

  const head = document.createElement("header");
  head.className = "dashboard-widget-head";
  const h3 = document.createElement("h3");
  h3.textContent = it.title;
  head.appendChild(h3);

  // server 위젯의 data.tab → drill-down: 헤더 "열기 →" 링크가 해당 관리 탭으로 이동.
  const wdata = (!editing && it.source !== "client" && adminState.overview && adminState.overview.widgets)
    ? adminState.overview.widgets[it.key] : null;
  if (wdata && wdata.tab && typeof switchTab === "function") {
    const open = document.createElement("button");
    open.type = "button";
    open.className = "dashboard-widget-open";
    open.textContent = "열기 →";
    open.setAttribute("aria-label", it.title + " 관리 화면 열기");
    open.addEventListener("click", () => switchTab(wdata.tab));
    head.appendChild(open);
  }

  if (editing) {
    card.setAttribute("draggable", "true");
    card.addEventListener("dragstart", (e) => {
      adminState._dragKey = it.key;
      card.classList.add("is-dragging");
      try { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", it.key); } catch (_) {}
    });
    card.addEventListener("dragend", () => { card.classList.remove("is-dragging"); adminState._dragKey = null; });
    card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drag-over"); });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      card.classList.remove("drag-over");
      const from = adminState._dragKey || (e.dataTransfer && e.dataTransfer.getData("text/plain"));
      if (from && from !== it.key) reorderWidgetBefore(from, it.key);
    });

    const ctrls = document.createElement("div");
    ctrls.className = "dashboard-widget-edit";
    const lbl = document.createElement("label");
    lbl.className = "dashboard-widget-vis";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = it.visible;
    cb.setAttribute("aria-label", it.title + " 위젯 표시");
    cb.addEventListener("change", () => setWidgetVisible(it.key, cb.checked));
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(it.visible ? " 표시" : " 숨김"));
    ctrls.appendChild(lbl);
    // ↑↓ = 키보드/터치 접근성 폴백(drag 단독 의존 회피).
    const up = document.createElement("button");
    up.type = "button";
    up.className = "dashboard-widget-move";
    up.textContent = "↑";
    up.setAttribute("aria-label", it.title + " 위젯 위로 이동");
    up.disabled = idx === 0;
    up.addEventListener("click", () => moveWidget(it.key, -1));
    const down = document.createElement("button");
    down.type = "button";
    down.className = "dashboard-widget-move";
    down.textContent = "↓";
    down.setAttribute("aria-label", it.title + " 위젯 아래로 이동");
    down.disabled = idx === total - 1;
    down.addEventListener("click", () => moveWidget(it.key, 1));
    ctrls.appendChild(up);
    ctrls.appendChild(down);
    head.appendChild(ctrls);
  }
  card.appendChild(head);

  const body = document.createElement("div");
  body.className = "dashboard-widget-body";
  if (it.source === "client") {
    if (it.key === "grant_health") {
      const gh = document.createElement("div");
      gh.id = "dashboardGrantHealth";
      gh.className = "admin-grant-health";
      body.appendChild(gh);
    } else if (it.key === "pending") {
      body.appendChild(buildPendingWidgetBody());
    }
  } else {
    const data = adminState.overview && adminState.overview.widgets
      ? adminState.overview.widgets[it.key]
      : null;
    body.appendChild(buildDataWidgetBody(data));
  }
  card.appendChild(body);
  return card;
}

function buildDataWidgetBody(data) {
  const frag = document.createDocumentFragment();
  // TASK-0218 fail-loud(위젯 단위): 실패 시 재시도 버튼 동반.
  if (!data || data.error) {
    const e = document.createElement("div");
    e.className = "dashboard-widget-error";
    const m = document.createElement("span");
    m.textContent = data && data.error ? "데이터를 불러오지 못했습니다." : "데이터 없음";
    e.appendChild(m);
    if (data && data.error) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "dashboard-retry-btn";
      retry.textContent = "다시 시도";
      retry.addEventListener("click", () => { adminState.dashboardLoaded = false; loadDashboardOverview(true); });
      e.appendChild(retry);
    }
    frag.appendChild(e);
    return frag;
  }
  const metrics = (data.metrics || []).slice();
  const hasList = (data.lists || []).some((l) => (l.rows || []).length);
  if (metrics.length) {
    // 주 metric(primary 플래그, 없으면 첫째) 크게 + 델타 배지 + sparkline.
    let pIdx = metrics.findIndex((m) => m.primary);
    if (pIdx < 0) pIdx = 0;
    const primary = metrics[pIdx];
    const pwrap = document.createElement("div");
    pwrap.className = "dashboard-primary";
    const top = document.createElement("div");
    top.className = "dashboard-primary-top";
    const val = document.createElement("strong");
    val.className = "dashboard-primary-val" + (primary.accent ? " accent-" + primary.accent : "");
    val.textContent = _dashFmtValue(primary.value, primary.fmt);
    top.appendChild(val);
    const badge = _dashDeltaBadge(primary.delta_pct, primary.delta_sentiment);
    if (badge) top.appendChild(badge);
    pwrap.appendChild(top);
    const plab = document.createElement("span");
    plab.className = "dashboard-primary-label";
    plab.textContent = primary.label;
    pwrap.appendChild(plab);
    const spark = _dashSparkline(primary.spark, primary.delta_sentiment);
    if (spark) pwrap.appendChild(spark);
    frag.appendChild(pwrap);

    // 보조 metric 작게.
    const secondary = metrics.filter((_, i) => i !== pIdx);
    if (secondary.length) {
      const swrap = document.createElement("div");
      swrap.className = "dashboard-secondary";
      secondary.forEach((m) => {
        const chip = document.createElement("div");
        chip.className = "dashboard-metric" + (m.accent ? " accent-" + m.accent : "");
        const v = document.createElement("strong");
        v.textContent = _dashFmtValue(m.value, m.fmt);
        const l = document.createElement("span");
        l.textContent = m.label;
        chip.appendChild(v);
        chip.appendChild(l);
        swrap.appendChild(chip);
      });
      frag.appendChild(swrap);
    }
  }
  // Top-N 리스트 — 인라인 비율막대(--bar) 로 상대 비중 시각화.
  (data.lists || []).forEach((lst) => {
    if (!lst || !(lst.rows || []).length) return;
    const lwrap = document.createElement("div");
    lwrap.className = "dashboard-widget-list";
    const t = document.createElement("div");
    t.className = "dashboard-widget-list-title";
    t.textContent = lst.title || "";
    lwrap.appendChild(t);
    const maxV = Math.max.apply(null, lst.rows.map((r) => Number(r.value) || 0).concat([1]));
    lst.rows.forEach((row) => {
      const r = document.createElement("div");
      r.className = "dashboard-list-row";
      const ratio = Math.max(0, Math.min(100, ((Number(row.value) || 0) / maxV) * 100));
      r.style.setProperty("--bar", ratio.toFixed(1) + "%");
      const lab = document.createElement("span");
      lab.className = "dashboard-list-label";
      lab.textContent = String(row.label == null ? "" : row.label);
      const val = document.createElement("span");
      val.className = "dashboard-list-value";
      val.textContent = _dashFmtValue(row.value, row.fmt);
      r.appendChild(lab);
      r.appendChild(val);
      lwrap.appendChild(r);
    });
    frag.appendChild(lwrap);
  });
  if (!metrics.length && !hasList) {
    const e = document.createElement("div");
    e.className = "dashboard-widget-empty";
    e.textContent = "데이터 없음";
    frag.appendChild(e);
  }
  return frag;
}

// 미저장 변경(pending) 위젯 본문 — 기존 dashboard pending 미리보기 로직 보존.
function buildPendingWidgetBody() {
  const frag = document.createDocumentFragment();
  const count = pendingChangeCount();
  const metric = document.createElement("div");
  metric.className = "dashboard-widget-metrics";
  const chip = document.createElement("div");
  chip.className = "dashboard-metric" + (count > 0 ? " accent-warn" : "");
  const val = document.createElement("strong");
  val.textContent = String(count);
  const lab = document.createElement("span");
  lab.textContent = "미저장 변경";
  chip.appendChild(val);
  chip.appendChild(lab);
  metric.appendChild(chip);
  frag.appendChild(metric);
  if (count === 0) {
    const e = document.createElement("div");
    e.className = "dashboard-widget-empty";
    e.textContent = "미저장 변경이 없습니다.";
    frag.appendChild(e);
    return frag;
  }
  const lwrap = document.createElement("div");
  lwrap.className = "dashboard-widget-list";
  const addRow = (text) => {
    const row = document.createElement("div");
    row.className = "dashboard-list-row";
    const lab = document.createElement("span");
    lab.className = "dashboard-list-label";
    lab.textContent = text;
    row.appendChild(lab);
    lwrap.appendChild(row);
  };
  adminState.pending.accounts.forEach((patch, id) => {
    const base = adminState.accounts.find((a) => Number(a.id) === id);
    if (base) addRow(`계정 · ${base.username} · ${describePatchKeys(patch)}`);
  });
  adminState.pending.roles.forEach((patch, id) => {
    const base = adminState.roles.find((r) => Number(r.id) === id);
    if (base) addRow(`역할 · ${base.name} · ${describePatchKeys(patch)}`);
  });
  adminState.pending.newRoles.forEach((draft) => {
    addRow(`신규 역할 · ${draft.role_key || "(키 미입력)"} · ${draft.name || ""}`);
  });
  adminState.pending.productMeta.forEach((patch, id) => {
    const base = adminState.products.find((p) => Number(p.id) === Number(id));
    addRow(`제품 정보 · ${base ? base.name : `#${id}`} · ${describePatchKeys(patch)}`);
  });
  adminState.pending.productDatabases.forEach((draft, id) => {
    const base = adminState.products.find((p) => Number(p.id) === Number(id));
    const c = Array.isArray(draft) ? draft.length : 0;
    addRow(`제품 DB · ${base ? base.name : `#${id}`} · ${c} schema`);
  });
  adminState.pending.systemPrompts.forEach((entry) => {
    const scopeLabel = { product: "제품", role: "역할", account: "계정" }[entry.scope] || entry.scope;
    const target = entry.productId
      ? (adminState.products.find((p) => Number(p.id) === Number(entry.productId))?.name || `#${entry.productId}`)
      : entry.roleId
      ? (adminState.roles.find((r) => Number(r.id) === Number(entry.roleId))?.name || `#${entry.roleId}`)
      : entry.accountId
      ? (adminState.accounts.find((a) => Number(a.id) === Number(entry.accountId))?.username || `#${entry.accountId}`)
      : "(전역)";
    const action = entry.content ? `${entry.content.length}자` : "삭제";
    addRow(`프롬프트 (${scopeLabel}) · ${target} · ${action}`);
  });
  frag.appendChild(lwrap);
  return frag;
}

/* ── Dashboard 편집/영속 ─────────────────────────────────────────────── */

// 현재 렌더 순서를 prefs.widgets 로 물질화(편집이 일관되게 영속되도록).
function _materializeDashboardPrefs() {
  const items = _dashboardRenderOrder();
  adminState.dashboardPrefs = adminState.dashboardPrefs || { version: 1, widgets: [] };
  adminState.dashboardPrefs.widgets = items.map((it, i) => ({ key: it.key, visible: it.visible, order: i }));
  return adminState.dashboardPrefs.widgets;
}

function setWidgetVisible(key, visible) {
  const widgets = _materializeDashboardPrefs();
  const w = widgets.find((x) => x.key === key);
  if (w) w.visible = !!visible;
  renderDashboardWidgets();
}

function moveWidget(key, dir) {
  const widgets = _materializeDashboardPrefs();
  const i = widgets.findIndex((x) => x.key === key);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= widgets.length) return;
  const tmp = widgets[i];
  widgets[i] = widgets[j];
  widgets[j] = tmp;
  widgets.forEach((w, k) => { w.order = k; });
  renderDashboardWidgets();
}

// TASK-0218: drag-and-drop reorder — fromKey 를 beforeKey 앞으로 이동(네이티브 HTML5 DnD).
function reorderWidgetBefore(fromKey, beforeKey) {
  const widgets = _materializeDashboardPrefs();
  const from = widgets.findIndex((x) => x.key === fromKey);
  if (from < 0) return;
  const [moved] = widgets.splice(from, 1);
  let before = widgets.findIndex((x) => x.key === beforeKey);
  if (before < 0) before = widgets.length;
  widgets.splice(before, 0, moved);
  widgets.forEach((w, k) => { w.order = k; });
  renderDashboardWidgets();
}

async function saveDashboardPrefs() {
  const widgets = _materializeDashboardPrefs();
  const btn = $("dashboardSaveBtn");
  if (btn) btn.disabled = true;
  try {
    const resp = await apiFetch("/api/admin/dashboard/preferences", {
      method: "PUT",
      body: JSON.stringify({ version: 1, widgets }),
    });
    if (resp && resp.preferences) adminState.dashboardPrefs = resp.preferences;
    adminState.dashboardEditMode = false;
    renderDashboardWidgets();
    showToast("대시보드 설정을 저장했습니다.");
  } catch (e) {
    showToast("저장 실패: " + (e.message || ""), true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function resetDashboardPrefs() {
  const defaults = adminState.dashboardDefaults || { version: 1, widgets: [] };
  adminState.dashboardPrefs = JSON.parse(JSON.stringify(defaults));
  renderDashboardWidgets();
  try {
    const resp = await apiFetch("/api/admin/dashboard/preferences", {
      method: "PUT",
      body: JSON.stringify(adminState.dashboardPrefs),
    });
    if (resp && resp.preferences) adminState.dashboardPrefs = resp.preferences;
    showToast("기본값으로 복원했습니다.");
  } catch (e) {
    showToast("복원 저장 실패: " + (e.message || ""), true);
  }
}

function describePatchKeys(patch) {
  const labels = {
    role_id: "역할",
    is_active: "활성",
    permission_overrides: "권한 override",
    name: "이름",
    description: "설명",
    is_default_signup: "기본 가입",
    default_role_access: "신규 역할 자동 접근",
    is_default: "기본 제품",
    sort_order: "정렬",
    default_role_access: "신규 역할 자동 접근",
    permission_codes: "권한",
    _delete: "삭제",
  };
  return Object.keys(patch).map((k) => labels[k] || k).join(", ");
}

/* ── Accounts pane ───────────────────────────────────────────────────── */

function filteredAccounts() {
  const q = adminState.accountSearch.trim().toLowerCase();
  return adminState.accounts.filter((account) => {
    const username = String(account.username || "").toLowerCase();
    if (q && !username.includes(q)) return false;
    if (adminState.accountFilter === "active") return account.is_active && !account.deleted_at;
    if (adminState.accountFilter === "inactive") return !account.is_active && !account.deleted_at;
    if (adminState.accountFilter === "deleted") return Boolean(account.deleted_at);
    return true;
  });
}

function renderAccountList() {
  const listEl = $("accountList");
  const paginationEl = $("accountPagination");
  const countEl = $("accountListCount");
  listEl.innerHTML = "";
  paginationEl.innerHTML = "";

  if (!can("account.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>계정 조회 권한 없음</strong><span>현재 계정은 계정 목록을 읽을 수 없습니다.</span>";
    listEl.appendChild(empty);
    countEl.textContent = "";
    return;
  }

  const all = filteredAccounts();
  countEl.textContent = `${all.length}명`;
  if (!all.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>계정 없음</strong><span>검색 조건을 변경하세요</span>";
    listEl.appendChild(empty);
    return;
  }

  const totalPages = Math.max(1, Math.ceil(all.length / ACCOUNT_PAGE_SIZE));
  if (adminState.accountPage >= totalPages) adminState.accountPage = 0;
  const start = adminState.accountPage * ACCOUNT_PAGE_SIZE;
  const visible = all.slice(start, start + ACCOUNT_PAGE_SIZE);

  // DESIGN.md §9 — shift-click range 를 위한 visible id 시퀀스 (현재 페이지)
  const visibleIds = visible.map((a) => Number(a.id));
  visible.forEach((account, visibleIdx) => {
    const merged = mergedAccount(account.id);
    const row = document.createElement("div");
    row.className = "admin-list-row";
    row.dataset.accountId = String(account.id);
    row.dataset.idx = String(visibleIdx);
    row.setAttribute("role", "row");
    if (Number(adminState.selectedAccountId) === Number(account.id)) row.classList.add("is-active");
    if (merged._pending) row.classList.add("has-pending");
    if (merged._delete) row.classList.add("is-to-delete");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-list-row-cb";
    cb.checked = adminState.accountSelected.has(Number(account.id));
    cb.setAttribute("aria-label", `계정 ${account.username} 선택`);
    cb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      // DESIGN.md §9 — shift-click range 처리는 click phase 에서 (change 이전)
      if (ev.shiftKey && adminState.accountLastClickIdx >= 0) {
        const addMode = !cb.checked;  // 곧 toggle 될 새 상태와 같은 방향으로 range 적용
        applyShiftRangeSelect({
          selected: adminState.accountSelected,
          visibleIds,
          fromIdx: adminState.accountLastClickIdx,
          toIdx: visibleIdx,
          addMode,
        });
        // 이번 click 의 default toggle 도 처리하도록 그대로 진행 (browser native)
      }
    });
    cb.addEventListener("change", () => {
      if (cb.checked) adminState.accountSelected.add(Number(account.id));
      else adminState.accountSelected.delete(Number(account.id));
      adminState.accountLastClickIdx = visibleIdx;
      // shift-click range 가 다수 변경했을 수 있으므로 list 재렌더
      renderAccountList();
    });

    const main = document.createElement("div");
    main.className = "admin-list-row-main";

    const title = document.createElement("div");
    title.className = "admin-list-row-title";
    const avatar = document.createElement("span");
    avatar.className = "admin-avatar admin-avatar-sm";
    avatar.textContent = account.username.slice(0, 2).toUpperCase();
    const name = document.createElement("span");
    name.className = "admin-list-row-name";
    name.textContent = account.username;
    const pendingDot = document.createElement("span");
    pendingDot.className = "admin-pending-dot";
    pendingDot.title = "pending 변경 있음";
    pendingDot.textContent = merged._pending ? "•" : "";
    title.append(avatar, name, pendingDot);

    const meta = document.createElement("div");
    meta.className = "admin-list-row-meta";
    const role = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
    meta.textContent = `${role ? role.name : "—"} · ${account.conversation_count || 0}`;

    main.append(title, meta);

    const chips = document.createElement("div");
    chips.className = "admin-list-row-chips";
    chips.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
    if (account.deleted_at) chips.appendChild(statusBadge("deleted", "is-disabled"));

    row.append(cb, main, chips);
    row.addEventListener("click", () => selectAccount(account.id));
    listEl.appendChild(row);
  });

  // Pagination
  if (totalPages > 1) {
    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn-secondary";
    prev.textContent = "이전";
    prev.disabled = adminState.accountPage === 0;
    prev.addEventListener("click", () => {
      adminState.accountPage = Math.max(0, adminState.accountPage - 1);
      renderAccountList();
    });
    const info = document.createElement("span");
    info.className = "page-info";
    info.textContent = `${adminState.accountPage + 1} / ${totalPages}`;
    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn-secondary";
    next.textContent = "다음";
    next.disabled = adminState.accountPage >= totalPages - 1;
    next.addEventListener("click", () => {
      adminState.accountPage = Math.min(totalPages - 1, adminState.accountPage + 1);
      renderAccountList();
    });
    paginationEl.append(prev, info, next);
  }

  updateAccountSelectAllCheckbox();
  renderAccountBulkBar();
  renderAccountCrossPageBanner();
}

// DESIGN.md §6 — Accounts cross-page banner (페이징 있음)
function renderAccountCrossPageBanner() {
  const totalPages = Math.max(1, Math.ceil(filteredAccounts().length / ACCOUNT_PAGE_SIZE));
  if (totalPages <= 1) {
    const banner = $("accountsCrossPageBanner");
    if (banner) banner.innerHTML = "";
    return;
  }
  const start = adminState.accountPage * ACCOUNT_PAGE_SIZE;
  const visible = filteredAccounts().slice(start, start + ACCOUNT_PAGE_SIZE);
  renderCrossPageBanner({
    entity: "accounts",
    selected: adminState.accountSelected,
    visibleIds: visible.map((a) => Number(a.id)),
    totalCount: adminState.accounts.length,
    onClearAll: () => {
      adminState.accountSelected.clear();
      renderAccountList();
    },
    onShowCurrentOnly: () => {
      const visibleSet = new Set(visible.map((a) => Number(a.id)));
      adminState.accountSelected = new Set(
        Array.from(adminState.accountSelected).filter((id) => visibleSet.has(Number(id)))
      );
      renderAccountList();
    },
  });
}

// TASK-0061 Phase 7 (REQ-20260515-0009 / AC-0098): select-all 의 visible 정의를
// 전체 filteredAccounts 가 아닌 현재 페이지 slice 만 대상으로 한다 (사용자 보고 버그 fix).
function currentPageAccounts() {
  const all = filteredAccounts();
  const totalPages = Math.max(1, Math.ceil(all.length / ACCOUNT_PAGE_SIZE));
  const page = Math.min(Math.max(0, adminState.accountPage), totalPages - 1);
  const start = page * ACCOUNT_PAGE_SIZE;
  return all.slice(start, start + ACCOUNT_PAGE_SIZE);
}

function updateAccountSelectAllCheckbox() {
  const visible = currentPageAccounts();
  const selAll = $("accountSelectAll");
  if (!visible.length) {
    selAll.checked = false;
    selAll.indeterminate = false;
    return;
  }
  const selected = visible.filter((a) => adminState.accountSelected.has(Number(a.id))).length;
  if (selected === 0) {
    selAll.checked = false;
    selAll.indeterminate = false;
  } else if (selected === visible.length) {
    selAll.checked = true;
    selAll.indeterminate = false;
  } else {
    selAll.checked = false;
    selAll.indeterminate = true;
  }
}

function renderAccountBulkBar() {
  const bar = $("accountsBulkBar");
  bar.innerHTML = "";
  const count = adminState.accountSelected.size;
  if (!count) return;

  // DESIGN.md §5 — 표준 컴포넌트 set (label → 액션들 → 선택 해제 + Esc kbd-hint)
  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("accounts")} 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false, kbdHint = null) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
    if (kbdHint) {
      const hint = document.createElement("span");
      hint.className = "kbd-hint";
      hint.textContent = kbdHint;
      btn.appendChild(hint);
    }
    btn.addEventListener("click", handler);
    return btn;
  };

  if (can("account.activate")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkAccountSetActive(true)));
  }
  if (can("account.deactivate")) {
    bar.appendChild(makeBtn("비활성화 pending", () => bulkAccountSetActive(false)));
  }
  if (can("account.delete")) {
    bar.appendChild(makeBtn("삭제 pending", () => bulkAccountDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.accountSelected.clear();
    adminState.accountLastClickIdx = -1;
    renderAccountList();
  }, false, "Esc"));
}

// DESIGN.md §7 + §8 — confirm 표준 + partial-fail (deleted/self 보호)
function bulkAccountSetActive(active) {
  const action = active ? "activate" : "deactivate";
  const count = adminState.accountSelected.size;
  if (!confirmBulkAction({ entity: "accounts", action, count, danger: false })) return;
  const meId = adminState.me ? Number(adminState.me.id) : null;
  runBulkActionWithPartialFail({
    entity: "accounts",
    ids: adminState.accountSelected,
    action,
    applyFn: (id) => setAccountPending(Number(id), { is_active: active }),
    canTargetRow: (id) => {
      const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
      if (!base || base.deleted_at) return false;
      if (!active && meId !== null && Number(id) === meId) return false;  // self-deactivate 보호
      return true;
    },
  });
}

function bulkAccountDelete() {
  const count = adminState.accountSelected.size;
  if (!confirmBulkAction({ entity: "accounts", action: "delete", count, danger: true })) return;
  const meId = adminState.me ? Number(adminState.me.id) : null;
  runBulkActionWithPartialFail({
    entity: "accounts",
    ids: adminState.accountSelected,
    action: "delete",
    applyFn: (id) => setAccountPending(Number(id), { _delete: true }),
    canTargetRow: (id) => {
      const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
      if (!base || base.deleted_at) return false;
      if (meId !== null && Number(id) === meId) return false;  // self-delete 보호
      return true;
    },
  });
}

function selectAccount(accountId) {
  adminState.selectedAccountId = Number(accountId);
  renderAccountList();
  renderAccountDetail();
}

function renderAccountDetail() {
  const paneEl = $("accountDetail");
  paneEl.innerHTML = "";
  if (!adminState.selectedAccountId) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "좌측에서 계정을 선택하세요.";
    paneEl.appendChild(empty);
    return;
  }
  const merged = mergedAccount(adminState.selectedAccountId);
  const base = adminState.accounts.find((a) => Number(a.id) === Number(adminState.selectedAccountId));
  if (!merged || !base) {
    paneEl.textContent = "계정 정보를 찾을 수 없습니다.";
    return;
  }

  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  avatar.textContent = base.username.slice(0, 2).toUpperCase();
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = base.username;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  metaEl.innerHTML = `
    <span>생성 ${formatDateTime(base.created_at)}</span>
    <span>최근 로그인 ${formatDateTime(base.last_login_at)}</span>
    <span>대화 ${Number(base.conversation_count || 0)}개</span>
  `;
  idText.append(nameEl, metaEl);
  idBlock.append(avatar, idText);

  const badges = document.createElement("div");
  badges.className = "admin-status-row";
  badges.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (base.deleted_at) badges.appendChild(statusBadge("deleted", "is-disabled"));
  if (merged._pending) badges.appendChild(statusBadge("pending", "role-pending"));
  if (merged._delete) badges.appendChild(statusBadge("삭제 예정", "is-disabled"));

  header.append(idBlock, badges);
  paneEl.appendChild(header);

  if (merged._delete) {
    const note = document.createElement("div");
    note.className = "admin-detail-note";
    note.textContent = "삭제 대기 중. 모두 적용 시 삭제됩니다.";
    const undo = document.createElement("button");
    undo.type = "button";
    undo.className = "tool-btn";
    undo.textContent = "삭제 취소";
    undo.addEventListener("click", () => {
      const id = Number(adminState.selectedAccountId);
      const patch = adminState.pending.accounts.get(id) || {};
      delete patch._delete;
      if (Object.keys(patch).length === 0) adminState.pending.accounts.delete(id);
      else adminState.pending.accounts.set(id, patch);
      refreshPendingUI();
      renderAccountDetail();
    });
    note.appendChild(undo);
    paneEl.appendChild(note);
  }

  const disabledBase = Boolean(base.deleted_at) || !can("console.manage") || !can("account.update");

  // Role select
  const roleField = document.createElement("label");
  roleField.className = "field admin-detail-field";
  const roleLabel = document.createElement("span");
  roleLabel.textContent = "역할";
  const roleSelect = document.createElement("select");
  const currentRoleId = Number(merged.role_id);
  adminState.roles
    .filter((r) => r.is_active || Number(r.id) === currentRoleId)
    .forEach((role) => {
      const opt = document.createElement("option");
      opt.value = String(role.id);
      opt.textContent = `${role.name} (${role.key})`;
      opt.selected = Number(role.id) === currentRoleId;
      roleSelect.appendChild(opt);
    });
  roleSelect.disabled = disabledBase || !can("account.role.assign");
  roleSelect.addEventListener("change", () => {
    setAccountPending(adminState.selectedAccountId, { role_id: Number(roleSelect.value) });
    renderAccountList();
  });
  roleField.append(roleLabel, roleSelect);

  // Active toggle
  const activeToggle = document.createElement("label");
  activeToggle.className = "permission-toggle";
  const activeInput = document.createElement("input");
  activeInput.type = "checkbox";
  activeInput.checked = Boolean(merged.is_active);
  activeInput.disabled = disabledBase || !(can("account.activate") || can("account.deactivate"));
  const activeText = document.createElement("span");
  activeText.textContent = "활성";
  activeToggle.append(activeInput, activeText);
  activeInput.addEventListener("change", () => {
    setAccountPending(adminState.selectedAccountId, { is_active: activeInput.checked });
    renderAccountList();
  });

  const topRow = document.createElement("div");
  topRow.className = "admin-detail-top-row";
  topRow.append(roleField, activeToggle);
  paneEl.appendChild(topRow);

  // Override grid (TASK-0053 Phase B: dynamic product.access.* override 는 product subcatalog 가 담당).
  const overrideSection = document.createElement("div");
  overrideSection.className = "admin-detail-section";
  const overrideTitle = document.createElement("div");
  overrideTitle.className = "admin-detail-section-title";
  overrideTitle.textContent = "권한 Override";
  overrideSection.appendChild(overrideTitle);
  const overrideWrap = document.createElement("div");
  overrideWrap.className = "override-grid";
  renderPermissionGrid(
    overrideWrap,
    [],
    disabledBase || !can("account.permission.override.manage"),
    "override",
    merged.permission_overrides || {},
    () => {
      // TASK-0053 Phase B: grid 의 select[data-override-code] 는 정적 권한만이므로, dynamic
      // product.access.* 의 기존 override (product subcatalog 에서 설정한 값) 는 보존해야 한다.
      const overrides = {};
      const existingDynamic = Object.fromEntries(
        Object.entries(merged.permission_overrides || {})
          .filter(([code]) => String(code).startsWith("product.access."))
      );
      overrideWrap.querySelectorAll("select[data-override-code]").forEach((select) => {
        overrides[select.dataset.overrideCode] = select.value;
      });
      Object.assign(overrides, existingDynamic);
      setAccountPending(adminState.selectedAccountId, { permission_overrides: overrides });
      renderAccountList();
    },
    { excludeDynamic: true }
  );
  overrideSection.appendChild(overrideWrap);
  paneEl.appendChild(overrideSection);

  // TASK-0053 (사용자 follow-up 2026-05-07): 제품별 접근 카드 list 를 권한 grid 의 'product' 그룹 details
  // 안으로 이전. 사용자가 제품 그룹을 collapse 하면 product 별 override 카드도 함께 접힌다.
  const accountProductGroup = overrideWrap.querySelector('details[data-perm-group="product"]');
  const productOverrides = buildAccountProductOverrideList(
    merged,
    disabledBase || !can("account.permission.override.manage"),
    { embed: Boolean(accountProductGroup) },
  );
  if (accountProductGroup) {
    accountProductGroup.appendChild(productOverrides);
  } else {
    // Fallback: product 그룹이 grid 에 없으면 (정적 product.manage 등 권한 부재 시) 별도 section.
    paneEl.appendChild(productOverrides);
  }

  // Per-account actions
  const actions = document.createElement("div");
  actions.className = "admin-detail-actions";

  if (merged._pending) {
    const revertBtn = document.createElement("button");
    revertBtn.type = "button";
    revertBtn.className = "btn-secondary";
    revertBtn.textContent = "이 계정 pending 취소";
    revertBtn.addEventListener("click", () => {
      adminState.pending.accounts.delete(Number(adminState.selectedAccountId));
      refreshPendingUI();
      renderAccountDetail();
      renderAccountList();
    });
    actions.appendChild(revertBtn);
  }

  if (!base.deleted_at && !merged._delete && can("account.delete")) {
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-secondary danger";
    deleteBtn.textContent = "삭제 pending";
    deleteBtn.addEventListener("click", () => {
      if (!window.confirm(`${base.username} 계정을 삭제할까요? (취소 가능)`)) return;
      setAccountPending(adminState.selectedAccountId, { _delete: true });
      renderAccountDetail();
      renderAccountList();
    });
    actions.appendChild(deleteBtn);
  }

  // TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0096): 비밀번호 초기화 버튼.
  // 권한 부족 / 자기 자신 / 삭제된 계정 / pending new account 에서는 hidden.
  const meId = adminState.me ? Number(adminState.me.id) : null;
  if (
    !base.deleted_at &&
    !merged._isNew &&
    can("console.manage") &&
    can("account.update") &&
    meId !== null &&
    meId !== Number(base.id)
  ) {
    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.id = "adminPasswordResetBtn";
    resetBtn.className = "btn-secondary";
    resetBtn.textContent = "비밀번호 초기화";
    resetBtn.title = "임시 비밀번호 생성 및 세션 종료. 1회만 표시됨.";
    resetBtn.addEventListener("click", () => triggerPasswordResetFlow(base));
    actions.appendChild(resetBtn);
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

// TASK-0061 Phase 6 (REQ-20260515-0008): 임시 비밀번호 생성 + 1 회 표시 modal.
async function triggerPasswordResetFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(
    `${account.username} 계정의 비밀번호를 초기화하시겠습니까?\n\n` +
    "임시 비밀번호가 생성되며 세션이 종료됩니다. 복사 후 안전하게 전달하세요."
  )) {
    return;
  }
  let payload;
  try {
    payload = await apiFetch(`/api/admin/accounts/${Number(account.id)}/password-reset`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`비밀번호 초기화 실패: ${error.message || error}`, true);
    return;
  }
  showTemporaryPasswordModal(payload);
}

function showTemporaryPasswordModal(payload) {
  // 기존 modal 제거.
  const prev = document.getElementById("adminPasswordResetModal");
  if (prev && prev.parentNode) prev.parentNode.removeChild(prev);

  const overlay = document.createElement("div");
  overlay.id = "adminPasswordResetModal";
  overlay.className = "admin-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const modal = document.createElement("div");
  modal.className = "admin-modal";
  const title = document.createElement("h3");
  title.textContent = `임시 비밀번호 — ${payload.username || ""}`;
  modal.appendChild(title);

  const note = document.createElement("p");
  note.className = "admin-modal-note";
  note.textContent = "일회용 비밀번호입니다. 지금 바로 복사해 전달하세요.";
  modal.appendChild(note);

  const passwordRow = document.createElement("div");
  passwordRow.className = "temp-password-display";
  const code = document.createElement("code");
  code.textContent = String(payload.temporary_password || "");
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "btn-secondary";
  copyBtn.textContent = "복사";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(String(payload.temporary_password || ""));
      showToast("임시 비밀번호를 클립보드에 복사했습니다.");
    } catch (_err) {
      showToast("자동 복사 실패. 직접 복사하세요.", true);
    }
  });
  passwordRow.append(code, copyBtn);
  modal.appendChild(passwordRow);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "btn-primary";
  closeBtn.textContent = "복사 후 닫기";
  closeBtn.addEventListener("click", () => {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
  });
  modal.appendChild(closeBtn);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

/* ── Roles pane ──────────────────────────────────────────────────────── */

function filteredRoles() {
  const q = adminState.roleSearch.trim().toLowerCase();
  const serverRoles = adminState.roles.filter((role) => {
    if (!q) return true;
    return String(role.name || "").toLowerCase().includes(q) ||
           String(role.key || "").toLowerCase().includes(q);
  });
  return serverRoles;
}

function renderRoleList() {
  const listEl = $("roleList");
  const countEl = $("roleListCount");
  listEl.innerHTML = "";

  if (!can("role.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>역할 조회 권한 없음</strong><span>현재 계정은 역할 목록을 읽을 수 없습니다.</span>";
    listEl.appendChild(empty);
    countEl.textContent = "";
    return;
  }

  const newEntries = Array.from(adminState.pending.newRoles.entries());
  const serverRoles = filteredRoles();
  const total = newEntries.length + serverRoles.length;
  countEl.textContent = `${total}개`;
  if (!total) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>역할 없음</strong><span>새 역할을 생성하세요</span>";
    listEl.appendChild(empty);
    return;
  }

  // DESIGN.md §9 — shift-click range 를 위한 visible id 시퀀스 (newEntries 는 disabled 라 제외)
  const visibleRoleIds = serverRoles.map((r) => String(r.id));
  newEntries.forEach(([tempId, _draft]) => {
    listEl.appendChild(buildRoleRow(tempId, /*visibleIdx=*/-1, visibleRoleIds));
  });
  serverRoles.forEach((role, idx) => {
    listEl.appendChild(buildRoleRow(role.id, idx, visibleRoleIds));
  });

  updateRoleSelectAllCheckbox();
  renderRoleBulkBar();
  // Roles 는 페이징이 없으므로 cross-page banner 는 항상 empty (renderCrossPageBanner 가 off-page 0 으로 skip)
  renderCrossPageBanner({
    entity: "roles",
    selected: adminState.roleSelected,
    visibleIds: visibleRoleIds,
    totalCount: serverRoles.length,
    onClearAll: () => { adminState.roleSelected.clear(); renderRoleList(); },
    onShowCurrentOnly: () => { /* no-op — 페이징 없음 */ },
  });
}

function buildRoleRow(roleKey, visibleIdx = -1, visibleRoleIds = []) {
  const merged = mergedRole(roleKey);
  const row = document.createElement("div");
  row.className = "admin-list-row";
  row.dataset.roleKey = String(roleKey);
  if (visibleIdx >= 0) row.dataset.idx = String(visibleIdx);
  row.setAttribute("role", "row");
  if (String(adminState.selectedRoleId) === String(roleKey)) row.classList.add("is-active");
  if (merged._pending) row.classList.add("has-pending");
  if (merged._delete) row.classList.add("is-to-delete");

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.className = "admin-list-row-cb";
  cb.checked = adminState.roleSelected.has(String(roleKey));
  cb.setAttribute("aria-label", `역할 ${merged.name || merged.key || roleKey} 선택`);
  if (merged._isNew) cb.disabled = true;
  cb.addEventListener("click", (ev) => {
    ev.stopPropagation();
    // DESIGN.md §9 — shift-click range
    if (ev.shiftKey && adminState.roleLastClickIdx >= 0 && visibleIdx >= 0 && !cb.disabled) {
      const addMode = !cb.checked;
      applyShiftRangeSelect({
        selected: adminState.roleSelected,
        visibleIds: visibleRoleIds,
        fromIdx: adminState.roleLastClickIdx,
        toIdx: visibleIdx,
        addMode,
      });
    }
  });
  cb.addEventListener("change", () => {
    if (cb.checked) adminState.roleSelected.add(String(roleKey));
    else adminState.roleSelected.delete(String(roleKey));
    if (visibleIdx >= 0) adminState.roleLastClickIdx = visibleIdx;
    renderRoleList();
  });

  const main = document.createElement("div");
  main.className = "admin-list-row-main";
  const title = document.createElement("div");
  title.className = "admin-list-row-title";
  const avatar = document.createElement("span");
  avatar.className = "admin-avatar admin-avatar-sm";
  avatar.textContent = (merged.key || "NEW").slice(0, 2).toUpperCase();
  const name = document.createElement("span");
  name.className = "admin-list-row-name";
  name.textContent = merged._isNew
    ? `(신규) ${merged.name || merged.key || "새 역할"}`
    : `${merged.name} (${merged.key})`;
  const pendingDot = document.createElement("span");
  pendingDot.className = "admin-pending-dot";
  pendingDot.textContent = merged._pending ? "•" : "";
  title.append(avatar, name, pendingDot);

  const meta = document.createElement("div");
  meta.className = "admin-list-row-meta";
  meta.textContent = merged._isNew
    ? "미저장"
    : `${merged.member_count || 0}명 · ${(merged.permission_codes || []).length}개`;

  main.append(title, meta);

  const chips = document.createElement("div");
  chips.className = "admin-list-row-chips";
  chips.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (merged.is_default_signup) chips.appendChild(statusBadge("기본", "role-admin"));

  row.append(cb, main, chips);
  row.addEventListener("click", () => selectRole(roleKey));
  return row;
}

function updateRoleSelectAllCheckbox() {
  const all = filteredRoles();
  const selAll = $("roleSelectAll");
  if (!all.length) {
    selAll.checked = false;
    selAll.indeterminate = false;
    return;
  }
  const selected = all.filter((r) => adminState.roleSelected.has(String(r.id))).length;
  if (selected === 0) { selAll.checked = false; selAll.indeterminate = false; }
  else if (selected === all.length) { selAll.checked = true; selAll.indeterminate = false; }
  else { selAll.checked = false; selAll.indeterminate = true; }
}

function renderRoleBulkBar() {
  const bar = $("roleBulkBar");
  bar.innerHTML = "";
  const count = adminState.roleSelected.size;
  if (!count) return;

  // DESIGN.md §5 — 표준 컴포넌트 set
  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("roles")} 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false, kbdHint = null) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
    if (kbdHint) {
      const hint = document.createElement("span");
      hint.className = "kbd-hint";
      hint.textContent = kbdHint;
      btn.appendChild(hint);
    }
    btn.addEventListener("click", handler);
    return btn;
  };

  if (can("role.update")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkRoleSetActive(true)));
    bar.appendChild(makeBtn("비활성화 pending", () => bulkRoleSetActive(false)));
  }
  if (can("role.delete")) {
    bar.appendChild(makeBtn("삭제 pending", () => bulkRoleDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.roleSelected.clear();
    adminState.roleLastClickIdx = -1;
    renderRoleList();
  }, false, "Esc"));
}

// DESIGN.md §7 + §8 — confirm + partial-fail (new: 미저장 row 제외)
function bulkRoleSetActive(active) {
  const action = active ? "activate" : "deactivate";
  const count = adminState.roleSelected.size;
  if (!confirmBulkAction({ entity: "roles", action, count, danger: false })) return;
  runBulkActionWithPartialFail({
    entity: "roles",
    ids: adminState.roleSelected,
    action,
    applyFn: (key) => setRolePending(Number(key), { is_active: active }),
    canTargetRow: (key) => !String(key).startsWith("new:"),
  });
}

function bulkRoleDelete() {
  const count = adminState.roleSelected.size;
  if (!confirmBulkAction({ entity: "roles", action: "delete", count, danger: true })) return;
  runBulkActionWithPartialFail({
    entity: "roles",
    ids: adminState.roleSelected,
    action: "delete",
    applyFn: (key) => setRolePending(Number(key), { _delete: true }),
    canTargetRow: (key) => !String(key).startsWith("new:"),
  });
}

function selectRole(roleKey) {
  adminState.selectedRoleId = String(roleKey);
  renderRoleList();
  renderRoleDetail();
}

function startNewRole() {
  const tempId = `new:${adminState.nextTempRoleId++}`;
  adminState.pending.newRoles.set(tempId, {
    role_key: "",
    name: "",
    description: "",
    is_active: true,
    is_default_signup: false,
    permission_codes: [],
  });
  adminState.selectedRoleId = tempId;
  refreshPendingUI();
  renderRoleList();
  renderRoleDetail();
}

function renderRoleDetail() {
  const paneEl = $("roleDetail");
  paneEl.innerHTML = "";
  if (!adminState.selectedRoleId) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "역할을 선택하세요.";
    paneEl.appendChild(empty);
    return;
  }
  const merged = mergedRole(adminState.selectedRoleId);
  if (!merged) {
    paneEl.textContent = "역할 정보를 찾을 수 없습니다.";
    return;
  }

  const disabledBase = !can("console.manage") || (merged._isNew ? !can("role.create") : !can("role.update"));

  // Header
  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  avatar.textContent = (merged.key || "NE").slice(0, 2).toUpperCase();
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = merged._isNew ? `신규 역할` : `${merged.name} (${merged.key})`;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  if (merged._isNew) {
    metaEl.textContent = "모두 적용 시 생성됩니다.";
  } else {
    metaEl.innerHTML = `
      <span>멤버 ${merged.member_count || 0}명</span>
      <span>생성 ${formatDateTime(merged.created_at)}</span>
      <span>수정 ${formatDateTime(merged.updated_at)}</span>
    `;
  }
  idText.append(nameEl, metaEl);
  idBlock.append(avatar, idText);

  const badges = document.createElement("div");
  badges.className = "admin-status-row";
  badges.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (merged._pending) badges.appendChild(statusBadge("pending", "role-pending"));
  if (merged._delete) badges.appendChild(statusBadge("삭제 예정", "is-disabled"));

  header.append(idBlock, badges);
  paneEl.appendChild(header);

  if (merged._delete) {
    const note = document.createElement("div");
    note.className = "admin-detail-note";
    note.textContent = "삭제 대기 중. ";
    const undo = document.createElement("button");
    undo.type = "button";
    undo.className = "tool-btn";
    undo.textContent = "삭제 취소";
    undo.addEventListener("click", () => {
      const id = Number(adminState.selectedRoleId);
      const patch = adminState.pending.roles.get(id) || {};
      delete patch._delete;
      if (Object.keys(patch).length === 0) adminState.pending.roles.delete(id);
      else adminState.pending.roles.set(id, patch);
      refreshPendingUI();
      renderRoleDetail();
    });
    note.appendChild(undo);
    paneEl.appendChild(note);
  }

  // Key (only editable for new roles)
  if (merged._isNew) {
    const keyField = document.createElement("label");
    keyField.className = "field admin-detail-field";
    const keyLabel = document.createElement("span");
    keyLabel.textContent = "role_key";
    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.value = merged.key || "";
    keyInput.placeholder = "예: analyst";
    keyInput.disabled = disabledBase;
    keyInput.addEventListener("input", () => {
      setRolePending(adminState.selectedRoleId, { role_key: keyInput.value.trim() });
      renderRoleList();
    });
    keyField.append(keyLabel, keyInput);
    paneEl.appendChild(keyField);
  }

  // Name
  const nameField = document.createElement("label");
  nameField.className = "field admin-detail-field";
  const nameLabel = document.createElement("span");
  nameLabel.textContent = "표시 이름";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = merged.name || "";
  nameInput.disabled = disabledBase;
  nameInput.addEventListener("input", () => {
    setRolePending(adminState.selectedRoleId, { name: nameInput.value });
    renderRoleList();
  });
  nameField.append(nameLabel, nameInput);
  paneEl.appendChild(nameField);

  // Description
  const descField = document.createElement("label");
  descField.className = "field admin-detail-field";
  const descLabel = document.createElement("span");
  descLabel.textContent = "설명";
  const descInput = document.createElement("input");
  descInput.type = "text";
  descInput.value = merged.description || "";
  descInput.disabled = disabledBase;
  descInput.addEventListener("input", () => {
    setRolePending(adminState.selectedRoleId, { description: descInput.value });
  });
  descField.append(descLabel, descInput);
  paneEl.appendChild(descField);

  // Toggles
  const toggles = document.createElement("div");
  toggles.className = "admin-role-toggle-row";
  const mkToggle = (label, checked, onChange) => {
    const wrap = document.createElement("label");
    wrap.className = "permission-toggle";
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = checked;
    inp.disabled = disabledBase;
    inp.addEventListener("change", () => onChange(inp.checked));
    const span = document.createElement("span");
    span.textContent = label;
    wrap.append(inp, span);
    return wrap;
  };
  toggles.appendChild(mkToggle("활성", merged.is_active, (v) => {
    setRolePending(adminState.selectedRoleId, { is_active: v });
    renderRoleList();
  }));
  toggles.appendChild(mkToggle("기본 가입 역할", merged.is_default_signup, (v) => {
    setRolePending(adminState.selectedRoleId, { is_default_signup: v });
    renderRoleList();
  }));
  // 사용자 의도 (2026-05-06 follow-up): 신규 제품 자동 접근 정책의 주체는 Role 이 아닌 Product.
  // 정책 토글은 Product detail 에 위치 — Role detail 에서는 더 이상 노출하지 않는다.
  paneEl.appendChild(toggles);

  // Permission grid (TASK-0053 Phase B: dynamic product.access.* 는 product subcatalog 가 처리하므로 제외).
  const permSection = document.createElement("div");
  permSection.className = "admin-detail-section";
  const permTitle = document.createElement("div");
  permTitle.className = "admin-detail-section-title";
  permTitle.textContent = "권한";
  permSection.appendChild(permTitle);
  const permWrap = document.createElement("div");
  permWrap.className = "permission-grid";
  renderPermissionGrid(
    permWrap,
    merged.permission_codes || [],
    disabledBase || !can("role.permission.manage"),
    "checkbox",
    {},
    () => {
      // TASK-0053 Phase B: dynamic perms 는 grid 에 노출되지 않으므로 product subcatalog 의
      // 상태 (= permission_codes 에 이미 포함된 product.access.*) 를 보존해야 한다. checked 만으로
      // 새 codes 를 만들면 product 카드의 토글이 무효화됨. 기존 dynamic codes 를 union 으로 유지.
      const checkedStatic = Array.from(permWrap.querySelectorAll("input[type='checkbox']:checked"))
        .map((input) => input.value);
      const existingDynamic = (merged.permission_codes || []).filter((c) =>
        String(c).startsWith("product.access.")
      );
      const codes = Array.from(new Set([...checkedStatic, ...existingDynamic]));
      setRolePending(adminState.selectedRoleId, { permission_codes: codes });
      renderRoleList();
    },
    { excludeDynamic: true }
  );
  permSection.appendChild(permWrap);
  paneEl.appendChild(permSection);

  // TASK-0053 Phase B/C + 사용자 follow-up (2026-05-07): 제품별 접근 + role-scope system prompt 카드를
  // 권한 grid 의 'product' 그룹 details 안으로 이전. 사용자가 '제품' 그룹을 collapse 하면
  // 제품별 카드도 함께 접혀 가시성 향상. fallback: product 그룹이 grid 에 없으면 별도 section.
  if (!merged._isNew) {
    const roleProductGroup = permWrap.querySelector('details[data-perm-group="product"]');
    const productCards = buildRoleProductCardList(
      merged,
      disabledBase || !can("role.permission.manage"),
      { embed: Boolean(roleProductGroup) },
    );
    if (roleProductGroup) {
      roleProductGroup.appendChild(productCards);
    } else {
      paneEl.appendChild(productCards);
    }
  }

  // Actions
  const actions = document.createElement("div");
  actions.className = "admin-detail-actions";

  if (merged._isNew) {
    const discardBtn = document.createElement("button");
    discardBtn.type = "button";
    discardBtn.className = "btn-secondary";
    discardBtn.textContent = "신규 역할 버리기";
    discardBtn.addEventListener("click", () => {
      adminState.pending.newRoles.delete(adminState.selectedRoleId);
      adminState.selectedRoleId = null;
      refreshPendingUI();
      renderRoleList();
      renderRoleDetail();
    });
    actions.appendChild(discardBtn);
  } else {
    if (merged._pending) {
      const revertBtn = document.createElement("button");
      revertBtn.type = "button";
      revertBtn.className = "btn-secondary";
      revertBtn.textContent = "변경 취소";
      revertBtn.addEventListener("click", () => {
        adminState.pending.roles.delete(Number(adminState.selectedRoleId));
        refreshPendingUI();
        renderRoleDetail();
        renderRoleList();
      });
      actions.appendChild(revertBtn);
    }
    if (!merged._delete && can("role.delete")) {
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn-secondary danger";
      deleteBtn.textContent = "삭제 pending";
      deleteBtn.addEventListener("click", () => {
        if (!window.confirm(`${merged.name} 역할을 삭제할까요?`)) return;
        setRolePending(adminState.selectedRoleId, { _delete: true });
        renderRoleDetail();
        renderRoleList();
      });
      actions.appendChild(deleteBtn);
    }
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

/* ── Pending UI refresh ──────────────────────────────────────────────── */

function refreshPendingUI() {
  const total = pendingChangeCount();
  $("commitBarCount").textContent = `${total}건 pending`;
  $("tabCountAccounts").textContent = `${adminState.accounts.length}`;
  $("tabCountRoles").textContent = `${adminState.roles.length + adminState.pending.newRoles.size}`;
  const tabCountProducts = $("tabCountProducts");
  if (tabCountProducts) tabCountProducts.textContent = `${adminState.products.length}`;
  const tabCountDatasources = $("tabCountDatasources");
  if (tabCountDatasources) tabCountDatasources.textContent = `${(adminState.datasources || []).length}`;
  $("adminPendingSummary").textContent = total ? `${total}건 pending` : "변경 없음";
  $("adminCommitBar").classList.toggle("has-pending", total > 0);
  $("commitApplyBtn").disabled = total === 0;
  $("commitCancelBtn").disabled = total === 0;

  const detail = [];
  if (adminState.pending.accounts.size) detail.push(`계정 ${adminState.pending.accounts.size}`);
  if (adminState.pending.roles.size) detail.push(`역할 ${adminState.pending.roles.size}`);
  if (adminState.pending.newRoles.size) detail.push(`신규 역할 ${adminState.pending.newRoles.size}`);
  if (adminState.pending.productMeta.size) detail.push(`제품 정보 ${adminState.pending.productMeta.size}`);
  if (adminState.pending.productDatabases.size) detail.push(`제품 DB ${adminState.pending.productDatabases.size}`);
  if (adminState.pending.systemPrompts.size) detail.push(`프롬프트 ${adminState.pending.systemPrompts.size}`);
  $("commitBarDetail").textContent = detail.length ? `(${detail.join(" · ")})` : "";

  // Dashboard auto-refresh if visible
  if (adminState.tab === "dashboard") renderDashboard();
}

/* ── Commit / cancel ─────────────────────────────────────────────────── */

async function applyAllPending() {
  const accountEntries = Array.from(adminState.pending.accounts.entries());
  const roleEntries = Array.from(adminState.pending.roles.entries());
  const newRoleEntries = Array.from(adminState.pending.newRoles.entries());
  const productMetaEntries = Array.from(adminState.pending.productMeta.entries());
  const productDbEntries = Array.from(adminState.pending.productDatabases.entries());
  const systemPromptEntries = Array.from(adminState.pending.systemPrompts.entries());

  if (
    !accountEntries.length
    && !roleEntries.length
    && !newRoleEntries.length
    && !productMetaEntries.length
    && !productDbEntries.length
    && !systemPromptEntries.length
  ) return;

  const failures = [];
  let ok = 0;

  const applyBtn = $("commitApplyBtn");
  applyBtn.disabled = true;
  applyBtn.textContent = "적용 중…";

  // Delete accounts / other account patches
  for (const [id, patch] of accountEntries) {
    try {
      if (patch._delete) {
        await apiFetch(`/api/admin/accounts/${id}`, { method: "DELETE" });
      } else {
        const body = {};
        if (patch.role_id !== undefined) body.role_id = Number(patch.role_id);
        if (patch.is_active !== undefined) body.is_active = Boolean(patch.is_active);
        if (patch.permission_overrides !== undefined) body.permission_overrides = patch.permission_overrides;
        await apiFetch(`/api/admin/accounts/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      adminState.pending.accounts.delete(id);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "account", id, error });
    }
  }

  // Role patches / deletes
  for (const [id, patch] of roleEntries) {
    try {
      if (patch._delete) {
        await apiFetch(`/api/admin/roles/${id}`, { method: "DELETE" });
      } else {
        const body = {};
        if (patch.name !== undefined) body.name = patch.name;
        if (patch.description !== undefined) body.description = patch.description;
        if (patch.is_active !== undefined) body.is_active = Boolean(patch.is_active);
        if (patch.is_default_signup !== undefined) body.is_default_signup = Boolean(patch.is_default_signup);
        if (patch.permission_codes !== undefined) body.permission_codes = patch.permission_codes;
        await apiFetch(`/api/admin/roles/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      adminState.pending.roles.delete(id);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "role", id, error });
    }
  }

  // New roles
  for (const [tempId, draft] of newRoleEntries) {
    try {
      await apiFetch(`/api/admin/roles`, {
        method: "POST",
        body: JSON.stringify({
          role_key: (draft.role_key || "").trim(),
          name: (draft.name || "").trim(),
          description: (draft.description || "").trim(),
          is_active: Boolean(draft.is_active),
          is_default_signup: Boolean(draft.is_default_signup),
          permission_codes: draft.permission_codes || [],
        }),
      });
      adminState.pending.newRoles.delete(tempId);
      if (adminState.selectedRoleId === tempId) adminState.selectedRoleId = null;
      ok += 1;
    } catch (error) {
      failures.push({ kind: "new_role", id: tempId, error });
    }
  }

  // Product metadata patches
  for (const [productId, patch] of productMetaEntries) {
    try {
      const body = {};
      if (patch.name !== undefined) body.name = patch.name;
      if (patch.description !== undefined) body.description = patch.description;
      if (patch.is_active !== undefined) body.is_active = Boolean(patch.is_active);
      if (patch.is_default !== undefined) body.is_default = Boolean(patch.is_default);
      if (patch.sort_order !== undefined) body.sort_order = Number(patch.sort_order) || 100;
      if (patch.default_role_access !== undefined) body.default_role_access = Boolean(patch.default_role_access);
      if (Object.keys(body).length > 0) {
        await apiFetch(`/api/admin/products/${Number(productId)}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      adminState.pending.productMeta.delete(productId);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "product_meta", id: productId, error });
    }
  }

  // Product databases (full replace per product)
  for (const [productId, draft] of productDbEntries) {
    try {
      await apiFetch(`/api/admin/products/${Number(productId)}/databases`, {
        method: "PUT",
        body: JSON.stringify({ databases: Array.isArray(draft) ? draft : [] }),
      });
      adminState.pending.productDatabases.delete(productId);
      adminState.productDbDraft.delete(Number(productId));
      ok += 1;
    } catch (error) {
      failures.push({ kind: "product_databases", id: productId, error });
    }
  }

  // System prompts (product / role / account scope)
  for (const [key, entry] of systemPromptEntries) {
    try {
      await apiFetch("/api/admin/system-prompts", {
        method: "PUT",
        body: JSON.stringify({
          scope: entry.scope,
          content: entry.content || "",
          product_id: entry.productId || null,
          role_id: entry.roleId || null,
          account_id: entry.accountId || null,
        }),
      });
      adminState.pending.systemPrompts.delete(key);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "system_prompt", id: key, error });
    }
  }

  applyBtn.textContent = "모두 적용";

  if (failures.length) {
    const first = failures[0];
    showToast(`${failures.length}건 실패, ${ok}건 성공`, true);
  } else {
    showToast(`${ok}건 적용됨`);
  }

  try {
    await loadAdminData();
  } catch (error) {
    showToast(error.message || "새로고침 실패", true);
  }
}

function cancelAllPending() {
  if (pendingChangeCount() === 0) return;
  if (!window.confirm("변경사항을 취소하시겠습니까?")) return;
  adminState.pending.accounts.clear();
  adminState.pending.roles.clear();
  adminState.pending.newRoles.clear();
  adminState.pending.productMeta.clear();
  adminState.pending.productDatabases.clear();
  adminState.pending.systemPrompts.clear();
  adminState.productDbDraft.clear();
  if (adminState.selectedRoleId && String(adminState.selectedRoleId).startsWith("new:")) {
    adminState.selectedRoleId = null;
  }
  refreshPendingUI();
  renderAccountList();
  renderAccountDetail();
  renderRoleList();
  renderRoleDetail();
  renderProductDetail();
  showToast("변경사항 취소됨");
}

/* ── Load ────────────────────────────────────────────────────────────── */

async function loadAdminData() {
  const [permissionsPayload, rolesPayload, accountsPayload, productsPayload, databasesPayload, datasourcesPayload] = await Promise.all([
    apiFetch("/api/admin/permissions").catch((error) => {
      if (error.status === 403) return { permissions: [] };
      throw error;
    }),
    apiFetch("/api/admin/roles").catch((error) => {
      if (error.status === 403) return { roles: [] };
      throw error;
    }),
    apiFetch("/api/admin/accounts").catch((error) => {
      if (error.status === 403) return { accounts: [], summary: {} };
      throw error;
    }),
    apiFetch("/api/admin/products").catch((error) => {
      if (error.status === 403) return { products: [] };
      throw error;
    }),
    apiFetch("/api/admin/databases/available").catch((error) => {
      if (error.status === 403 || error.status === 500) {
        return { metadata_schemas: [], user_schemas: [] };
      }
      throw error;
    }),
    // 멀티 datasource (P2): 등록된 datasource 키 목록 (좌표/비밀번호 미노출).
    apiFetch("/api/admin/datasources").catch((error) => {
      if (error.status === 403 || error.status === 404) return { enabled: false, datasources: [] };
      throw error;
    }),
  ]);

  adminState.permissions = Array.isArray(permissionsPayload.permissions) ? permissionsPayload.permissions : [];
  adminState.roles = Array.isArray(rolesPayload.roles) ? rolesPayload.roles : [];
  adminState.accounts = Array.isArray(accountsPayload.accounts) ? accountsPayload.accounts : [];
  adminState.products = Array.isArray(productsPayload.products) ? productsPayload.products : [];
  adminState.datasourcesEnabled = Boolean(datasourcesPayload && datasourcesPayload.enabled);
  adminState.datasourcesEncryptionReady = Boolean(datasourcesPayload && datasourcesPayload.encryption_ready);
  adminState.datasources = Array.isArray(datasourcesPayload && datasourcesPayload.datasources) ? datasourcesPayload.datasources : [];
  // TASK-0205: datasource GET 의 products(datasource_database 포함)를 product 객체에 병합(상세화면 참조 DB 표시용).
  {
    const dsProds = Array.isArray(datasourcesPayload && datasourcesPayload.products) ? datasourcesPayload.products : [];
    const dbById = new Map(dsProds.map((p) => [Number(p.id), p.datasource_database || null]));
    adminState.products.forEach((p) => { p.datasource_database = dbById.has(Number(p.id)) ? dbById.get(Number(p.id)) : (p.datasource_database || null); });
  }
  adminState.availableDatabases = {
    metadata_schemas: Array.isArray(databasesPayload.metadata_schemas) ? databasesPayload.metadata_schemas : [],
    user_schemas: Array.isArray(databasesPayload.user_schemas) ? databasesPayload.user_schemas : [],
  };
  const productIds = new Set(adminState.products.map((p) => Number(p.id)));
  if (adminState.selectedProductId && !productIds.has(Number(adminState.selectedProductId))) {
    adminState.selectedProductId = null;
  }
  // DESIGN.md §4 I-2 — productSelected stale entry 제거 (reload 후 invariant)
  adminState.productSelected = new Set(
    Array.from(adminState.productSelected).filter((id) => productIds.has(Number(id)))
  );
  Array.from(adminState.productDbDraft.keys()).forEach((id) => {
    if (!productIds.has(Number(id))) adminState.productDbDraft.delete(id);
  });
  // GC pending entries for products that no longer exist.
  Array.from(adminState.pending.productMeta.keys()).forEach((id) => {
    if (!productIds.has(Number(id))) adminState.pending.productMeta.delete(id);
  });
  Array.from(adminState.pending.productDatabases.keys()).forEach((id) => {
    if (!productIds.has(Number(id))) adminState.pending.productDatabases.delete(id);
  });
  // GC system prompt pending entries that point to deleted product/role/account.
  const roleIdSet = new Set(adminState.roles.map((r) => Number(r.id)));
  const accountIdSet = new Set(adminState.accounts.map((a) => Number(a.id)));
  Array.from(adminState.pending.systemPrompts.entries()).forEach(([key, value]) => {
    const stale =
      (value.productId && !productIds.has(Number(value.productId)))
      || (value.roleId && !roleIdSet.has(Number(value.roleId)))
      || (value.accountId && !accountIdSet.has(Number(value.accountId)));
    if (stale) adminState.pending.systemPrompts.delete(key);
  });

  // Drop selections that no longer exist
  const accountIds = new Set(adminState.accounts.map((a) => Number(a.id)));
  adminState.accountSelected = new Set(Array.from(adminState.accountSelected).filter((id) => accountIds.has(Number(id))));
  if (adminState.selectedAccountId && !accountIds.has(Number(adminState.selectedAccountId))) {
    adminState.selectedAccountId = null;
  }
  const roleIds = new Set(adminState.roles.map((r) => String(r.id)));
  adminState.roleSelected = new Set(Array.from(adminState.roleSelected).filter((id) => roleIds.has(String(id))));
  if (
    adminState.selectedRoleId &&
    !String(adminState.selectedRoleId).startsWith("new:") &&
    !roleIds.has(String(adminState.selectedRoleId))
  ) {
    adminState.selectedRoleId = null;
  }
  // Drop pending entries for deleted/missing accounts and roles
  Array.from(adminState.pending.accounts.keys()).forEach((id) => {
    if (!accountIds.has(Number(id))) adminState.pending.accounts.delete(id);
  });
  Array.from(adminState.pending.roles.keys()).forEach((id) => {
    if (!roleIds.has(String(id))) adminState.pending.roles.delete(id);
  });

  refreshPendingUI();
  renderDashboard();
  renderAccountList();
  renderAccountDetail();
  renderAccountBulkBar();
  renderRoleList();
  renderRoleDetail();
  renderProductList();
  renderProductDetail();
}

/* ── Products pane ───────────────────────────────────────────────────── */

function filteredProducts() {
  const q = (adminState.productSearch || "").toLowerCase().trim();
  if (!q) return adminState.products.slice();
  return adminState.products.filter((p) => {
    return (
      (p.product_key || "").toLowerCase().includes(q)
      || (p.name || "").toLowerCase().includes(q)
      || (p.description || "").toLowerCase().includes(q)
    );
  });
}

function renderProductList() {
  const listEl = $("productList");
  if (!listEl) return;
  const countEl = $("productListCount");
  listEl.innerHTML = "";
  const items = filteredProducts();
  if (countEl) countEl.textContent = `${items.length} / ${adminState.products.length}`;
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "제품이 없습니다.";
    listEl.appendChild(empty);
    updateProductSelectAllCheckbox();
    renderProductBulkBar();
    renderProductCrossPageBanner();
    return;
  }
  // DESIGN.md §9 — shift-click range 를 위한 visible id 시퀀스
  const visibleProductIds = items.map((p) => Number(p.id));
  items.forEach((p, visibleIdx) => {
    const row = document.createElement("div");
    row.className = "admin-list-row";
    row.dataset.productId = String(p.id);
    row.dataset.idx = String(visibleIdx);
    row.setAttribute("role", "row");
    if (Number(adminState.selectedProductId) === Number(p.id)) row.classList.add("is-active");
    if (!p.is_active) row.classList.add("is-disabled");

    // DESIGN.md §12 Phase A — row checkbox (multi-select 신설), detail panel 은 단일 selectedProductId 유지
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-list-row-cb";
    cb.checked = adminState.productSelected.has(Number(p.id));
    cb.setAttribute("aria-label", `제품 ${p.name} 선택`);
    cb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (ev.shiftKey && adminState.productLastClickIdx >= 0) {
        const addMode = !cb.checked;
        applyShiftRangeSelect({
          selected: adminState.productSelected,
          visibleIds: visibleProductIds,
          fromIdx: adminState.productLastClickIdx,
          toIdx: visibleIdx,
          addMode,
        });
      }
    });
    cb.addEventListener("change", () => {
      if (cb.checked) adminState.productSelected.add(Number(p.id));
      else adminState.productSelected.delete(Number(p.id));
      adminState.productLastClickIdx = visibleIdx;
      renderProductList();
    });

    row.addEventListener("click", () => {
      adminState.selectedProductId = Number(p.id);
      renderProductList();
      renderProductDetail();
    });
    const meta = document.createElement("div");
    meta.className = "admin-list-main";
    const name = document.createElement("div");
    name.className = "admin-account-name";
    name.textContent = `${p.name} (${p.product_key})`;
    const sub = document.createElement("div");
    sub.className = "admin-meta";
    const badges = [];
    if (p.is_default) badges.push("default");
    if (!p.is_active) badges.push("inactive");
    sub.textContent = [p.description || "—", ...badges].filter(Boolean).join(" · ");
    meta.append(name, sub);
    row.append(cb, meta);
    listEl.appendChild(row);
  });
  updateProductSelectAllCheckbox();
  renderProductBulkBar();
  renderProductCrossPageBanner();
}

// DESIGN.md §11 — Products select-all (indeterminate 반영)
function updateProductSelectAllCheckbox() {
  const all = filteredProducts();
  const selAll = $("productSelectAll");
  if (!selAll) return;
  if (!all.length) { selAll.checked = false; selAll.indeterminate = false; return; }
  const selected = all.filter((p) => adminState.productSelected.has(Number(p.id))).length;
  if (selected === 0) { selAll.checked = false; selAll.indeterminate = false; }
  else if (selected === all.length) { selAll.checked = true; selAll.indeterminate = false; }
  else { selAll.checked = false; selAll.indeterminate = true; }
}

// DESIGN.md §5 — Products bulk toolbar
function renderProductBulkBar() {
  const bar = $("productsBulkBar");
  if (!bar) return;
  bar.innerHTML = "";
  const count = adminState.productSelected.size;
  if (!count) return;

  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("products")} 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false, kbdHint = null) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
    if (kbdHint) {
      const hint = document.createElement("span");
      hint.className = "kbd-hint";
      hint.textContent = kbdHint;
      btn.appendChild(hint);
    }
    btn.addEventListener("click", handler);
    return btn;
  };

  // product.manage 권한 1 개로 모든 product mutation 을 통제 (현재 RBAC catalog 기준)
  if (can("product.manage")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkProductSetActive(true)));
    bar.appendChild(makeBtn("비활성화 pending", () => bulkProductSetActive(false)));
    bar.appendChild(makeBtn("삭제 pending", () => bulkProductDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.productSelected.clear();
    adminState.productLastClickIdx = -1;
    renderProductList();
  }, false, "Esc"));
}

// DESIGN.md §6 — Products cross-page banner (현재 페이징 없음, 향후 도입 대비 placeholder)
function renderProductCrossPageBanner() {
  const items = filteredProducts();
  renderCrossPageBanner({
    entity: "products",
    selected: adminState.productSelected,
    visibleIds: items.map((p) => Number(p.id)),
    totalCount: adminState.products.length,
    onClearAll: () => { adminState.productSelected.clear(); renderProductList(); },
    onShowCurrentOnly: () => { /* no-op — 페이징 없음 */ },
  });
}

// DESIGN.md §7 + §8 — confirm + partial-fail
// product.manage 권한이 있어도 다음 row 는 보호: (1) detail panel 에서 미저장 새 product 의 placeholder
function bulkProductSetActive(active) {
  const action = active ? "activate" : "deactivate";
  const count = adminState.productSelected.size;
  if (!confirmBulkAction({ entity: "products", action, count, danger: false })) return;
  runBulkActionWithPartialFail({
    entity: "products",
    ids: adminState.productSelected,
    action,
    applyFn: (id) => setProductMetaPending(Number(id), { is_active: active }),
    canTargetRow: (id) => {
      const base = adminState.products.find((p) => Number(p.id) === Number(id));
      return !!base;
    },
  });
  // pending 반영 후 detail 새로고침 (선택된 product 의 active 상태가 바뀐 경우 UI 일관성)
  if (adminState.selectedProductId) renderProductDetail();
}

function bulkProductDelete() {
  const count = adminState.productSelected.size;
  if (!confirmBulkAction({ entity: "products", action: "delete", count, danger: true })) return;
  // product 삭제는 catalog 영향이 큼 (Role/Account 권한 grid 도 의존). 본 cycle 은 deletion API 가 마련된 경우만 적용.
  // 현재 product.manage 권한 + setProductMetaPending 에 _delete 키 plumbing 이 backend 에 없을 수 있으므로 safety check.
  runBulkActionWithPartialFail({
    entity: "products",
    ids: adminState.productSelected,
    action: "delete",
    applyFn: (id) => setProductMetaPending(Number(id), { _delete: true }),
    canTargetRow: (id) => {
      const base = adminState.products.find((p) => Number(p.id) === Number(id));
      if (!base) return false;
      if (base.is_default) return false;  // default product 삭제 보호
      return true;
    },
  });
  if (adminState.selectedProductId) renderProductDetail();
}

function renderProductDetail() {
  const paneEl = $("productDetail");
  if (!paneEl) return;
  paneEl.innerHTML = "";
  if (!adminState.selectedProductId) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "제품을 선택하세요.";
    paneEl.appendChild(empty);
    return;
  }
  const product = adminState.products.find((p) => Number(p.id) === Number(adminState.selectedProductId));
  if (!product) {
    paneEl.textContent = "제품 없음";
    return;
  }
  const canManage = can("product.manage");

  // Header
  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  avatar.textContent = (product.product_key || "P").slice(0, 2).toUpperCase();
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = `${product.name} (${product.product_key})`;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  metaEl.innerHTML = `
    <span>${product.is_active ? "active" : "inactive"}</span>
    <span>${product.is_default ? "default" : ""}</span>
    <span>정렬 ${product.sort_order}</span>
    <span>생성 ${formatDateTime(product.created_at)}</span>
    <span>수정 ${formatDateTime(product.updated_at)}</span>
  `;
  idText.append(nameEl, metaEl);
  idBlock.append(avatar, idText);
  header.append(idBlock);
  paneEl.appendChild(header);

  // 변경사항은 footer "모두 적용" 버튼으로 일괄 저장된다 (TASK-0029 정책).
  const productPending = adminState.pending.productMeta.get(Number(product.id)) || {};
  const merged = {
    name: productPending.name !== undefined ? productPending.name : (product.name || ""),
    description: productPending.description !== undefined ? productPending.description : (product.description || ""),
    is_active: productPending.is_active !== undefined ? productPending.is_active : !!product.is_active,
    is_default: productPending.is_default !== undefined ? productPending.is_default : !!product.is_default,
    sort_order: productPending.sort_order !== undefined ? productPending.sort_order : (product.sort_order || 100),
    // TASK-0053 (사용자 follow-up 2026-05-06): default_role_access — product 생성 시 모든 role 자동 grant 여부.
    default_role_access: productPending.default_role_access !== undefined
      ? productPending.default_role_access
      : (product.default_role_access !== undefined ? !!product.default_role_access : true),
  };

  // Name
  const nameField = document.createElement("label");
  nameField.className = "field admin-detail-field";
  const nameLabel = document.createElement("span");
  nameLabel.textContent = "표시 이름";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = merged.name;
  nameInput.disabled = !canManage;
  nameInput.addEventListener("input", () => {
    setProductMetaPending(product.id, { name: nameInput.value.trim() });
  });
  nameField.append(nameLabel, nameInput);
  paneEl.appendChild(nameField);

  // Description
  const descField = document.createElement("label");
  descField.className = "field admin-detail-field";
  const descLabel = document.createElement("span");
  descLabel.textContent = "설명";
  const descInput = document.createElement("input");
  descInput.type = "text";
  descInput.value = merged.description;
  descInput.disabled = !canManage;
  descInput.addEventListener("input", () => {
    setProductMetaPending(product.id, { description: descInput.value.trim() });
  });
  descField.append(descLabel, descInput);
  paneEl.appendChild(descField);

  // Toggles + sort
  const toggles = document.createElement("div");
  toggles.className = "admin-role-toggle-row";
  const mkToggle = (label, checked, onChange) => {
    const wrap = document.createElement("label");
    wrap.className = "permission-toggle";
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = checked;
    inp.disabled = !canManage;
    inp.addEventListener("change", () => onChange(inp.checked));
    const span = document.createElement("span");
    span.textContent = label;
    wrap.append(inp, span);
    return wrap;
  };
  toggles.appendChild(mkToggle("활성", merged.is_active, (v) => {
    setProductMetaPending(product.id, { is_active: v });
  }));
  toggles.appendChild(mkToggle("기본 제품", merged.is_default, (v) => {
    setProductMetaPending(product.id, { is_default: v });
  }));
  // TASK-0053 (사용자 follow-up 2026-05-06): 정책 주체를 Role → Product 로 전환.
  // 켜져 있으면 (default) 이 product 가 추가될 때 모든 role 에 자동 grant. 끄면 명시 grant 만으로
  // 접근 가능. **신규 product 생성 시 효력 발휘** — 기존 grant 는 보존.
  toggles.appendChild(mkToggle("신규 역할 자동 접근", merged.default_role_access, (v) => {
    setProductMetaPending(product.id, { default_role_access: v });
  }));
  const sortField = document.createElement("label");
  sortField.className = "field admin-detail-field";
  const sortLabel = document.createElement("span");
  sortLabel.textContent = "정렬 순서";
  const sortInput = document.createElement("input");
  sortInput.type = "number";
  sortInput.step = "1";
  sortInput.value = String(merged.sort_order);
  sortInput.disabled = !canManage;
  sortInput.addEventListener("input", () => {
    setProductMetaPending(product.id, { sort_order: Number(sortInput.value) || 100 });
  });
  sortField.append(sortLabel, sortInput);
  toggles.appendChild(sortField);
  paneEl.appendChild(toggles);

  // TASK-0206: 데이터 소스 → 접근 가능 데이터베이스 의 forward-hook(데이터소스 섹션이 위에 렌더되어
  // 아래 접근-DB 섹션을 갱신). datasource-driven 으로 선택 datasource 의 DB 목록을 반영한다.
  let _refreshAccessibleDbs = () => {};
  let _selectedDatasourceKey = product.datasource_key || "";

  // Database chip editor (datasource-driven, DB-단위)
  const dbSection = document.createElement("div");
  dbSection.className = "admin-detail-section";
  const dbTitle = document.createElement("div");
  dbTitle.className = "admin-detail-section-title";
  dbTitle.textContent = "접근 가능 데이터베이스";
  dbSection.appendChild(dbTitle);
  const dbHint = document.createElement("div");
  dbHint.className = "admin-detail-hint";
  dbHint.textContent = "선택한 데이터 소스에서 이 제품이 접근할 데이터베이스. 시스템 DB(메타데이터)는 고정됩니다.";
  dbSection.appendChild(dbHint);

  // pending 우선, 다음으로 fresh draft, 최후로 서버 값.
  const pendingDraft = adminState.pending.productDatabases.get(Number(product.id));
  const baseDraft = pendingDraft
    ? pendingDraft.map((d) => ({ ...d }))
    : (adminState.productDbDraft.get(Number(product.id)) || (product.databases || []).map((d) => ({ ...d })));
  const draft = baseDraft;
  adminState.productDbDraft.set(Number(product.id), draft);

  const chipWrap = document.createElement("div");
  chipWrap.className = "admin-chip-wrap";

  // 시스템/메타데이터 locked chip 의 기본 소스(데이터 MySQL). datasource-driven 으로 교체됨(_refreshAccessibleDbs).
  const metadataPayload = (adminState.availableDatabases.metadata_schemas || []).slice();
  const _defaultLocked = metadataPayload.length
    ? metadataPayload.map((m) => ({ name: m.schema_name, present: m.present !== false }))
    : METADATA_SCHEMAS.map((name) => ({ name, present: true }));
  // 가변 소스 — datasource 선택에 따라 갱신.
  let lockedChips = _defaultLocked.slice();              // 시스템 DB / 메타데이터(고정칩)
  let availableUserDbs = (adminState.availableDatabases.user_schemas || []).slice();  // 사용자 DB(picker)
  let dsCaseInsensitive = false;                          // MSSQL DB명 대소문자 보존(true=lower 비교만)

  // 체크박스 드롭다운 패널 빌더. 드롭다운은 버튼 클릭 시 열리며, 각 항목에 체크박스로
  // 연속 토글 가능. 선택 즉시 draft 에 반영(추가 버튼 불필요).
  const buildPicker = () => {
    pickerDropList.innerHTML = "";
    const lockedLower = new Set(lockedChips.map((c) => String(c.name).toLowerCase()));
    const userSchemas = (availableUserDbs || [])
      .filter((s) => !lockedLower.has(String(s).toLowerCase()))
      .filter((s) => !METADATA_SCHEMAS.includes(String(s).toLowerCase()))
      .filter((s) => !INTERNAL_SCHEMAS.has(String(s).toLowerCase()));
    if (!userSchemas.length) {
      const empty = document.createElement("div");
      empty.className = "admin-db-picker-empty";
      empty.textContent = "(추가 가능한 DB 없음)";
      pickerDropList.appendChild(empty);
      pickerDropBtn.disabled = !canManage;
      return;
    }
    userSchemas.forEach((name) => {
      const item = document.createElement("label");
      item.className = "admin-db-picker-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      const nameKey = String(name).toLowerCase();
      cb.checked = draft.some((d) => String(d.schema_name).toLowerCase() === nameKey);
      cb.disabled = !canManage;
      cb.addEventListener("change", () => {
        if (cb.checked) {
          const raw = name;
          const v = raw.toLowerCase();
          if (METADATA_SCHEMAS.includes(v) || INTERNAL_SCHEMAS.has(v)) { cb.checked = false; return; }
          if (!dsCaseInsensitive && !/^[a-z_][a-z0-9_]{0,63}$/.test(v)) {
            showToast("스키마 이름 형식이 올바르지 않습니다.", true);
            cb.checked = false;
            return;
          }
          if (!draft.some((d) => String(d.schema_name).toLowerCase() === v)) {
            draft.push({ schema_name: dsCaseInsensitive ? raw : v, description: "", sort_order: (draft.length + 1) * 10 });
            setProductDatabasesPending(product.id, draft);
            redrawChips();
          }
        } else {
          const v = String(name).toLowerCase();
          const idx = draft.findIndex((d) => String(d.schema_name).toLowerCase() === v);
          if (idx !== -1) {
            draft.splice(idx, 1);
            setProductDatabasesPending(product.id, draft);
            redrawChips();
          }
        }
      });
      const lbl = document.createElement("span");
      lbl.textContent = name;
      item.append(cb, lbl);
      pickerDropList.appendChild(item);
    });
    pickerDropBtn.disabled = !canManage;
  };

  const redrawChips = () => {
    chipWrap.innerHTML = "";
    // 시스템 DB / 메타데이터 locked chip 강제 노출(고정 — 항상 접근, 편집 불가).
    lockedChips.forEach((meta) => {
      const chip = document.createElement("span");
      chip.className = "admin-chip is-locked";
      chip.title = meta.present === false
        ? "시스템/메타데이터 (고정, 미감지)"
        : "시스템/메타데이터 (고정)";
      const txt = document.createElement("span");
      txt.textContent = meta.name;
      chip.appendChild(txt);
      const tag = document.createElement("small");
      tag.className = "admin-chip-locked-hint";
      tag.textContent = "고정";
      chip.appendChild(tag);
      chipWrap.appendChild(chip);
    });
    // 사용자 등록 schema chips.
    draft.forEach((entry, idx) => {
      const chip = document.createElement("span");
      chip.className = "admin-chip";
      const txt = document.createElement("span");
      txt.textContent = entry.schema_name;
      chip.appendChild(txt);
      if (canManage) {
        const x = document.createElement("button");
        x.type = "button";
        x.className = "admin-chip-remove";
        x.textContent = "×";
        x.addEventListener("click", () => {
          draft.splice(idx, 1);
          setProductDatabasesPending(product.id, draft);
          redrawChips();
          buildPicker();
        });
        chip.appendChild(x);
      }
      chipWrap.appendChild(chip);
    });
    if (!draft.length) {
      const empty = document.createElement("div");
      empty.className = "admin-meta";
      empty.textContent = "(스키마 없음)";
      chipWrap.appendChild(empty);
    }
  };
  dbSection.appendChild(chipWrap);

  const pickerWrap = document.createElement("div");
  pickerWrap.className = "admin-db-picker-wrap";
  const pickerDropBtn = document.createElement("button");
  pickerDropBtn.type = "button";
  pickerDropBtn.className = "admin-db-picker-btn";
  pickerDropBtn.textContent = "+ 데이터베이스 선택";
  pickerDropBtn.disabled = !canManage;
  const pickerDropList = document.createElement("div");
  pickerDropList.className = "admin-db-picker-list hidden";
  pickerDropBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    pickerDropList.classList.toggle("hidden");
  });
  // 패널 바깥 클릭 시 닫기.
  document.addEventListener("click", function _closePicker(e) {
    if (!pickerWrap.contains(e.target)) {
      pickerDropList.classList.add("hidden");
    }
  });
  pickerWrap.append(pickerDropBtn, pickerDropList);
  dbSection.appendChild(pickerWrap);

  redrawChips();
  buildPicker();

  // TASK-0206: 선택 datasource 의 DB 목록으로 접근가능 DB(고정 시스템칩 + 사용자 picker)을 갱신.
  // 등록 datasource 면 /databases(classified) 사용; 미바인딩이면 데이터 MySQL 기본값으로 환원.
  _refreshAccessibleDbs = async (key) => {
    const ds = (adminState.datasources || []).find((d) => d.key === key);
    if (!key || !ds) {
      // 미바인딩(또는 미등록) → 데이터 MySQL 기본값.
      lockedChips = _defaultLocked.slice();
      availableUserDbs = (adminState.availableDatabases.user_schemas || []).slice();
      dsCaseInsensitive = false;
      redrawChips();
      buildPicker();
      return;
    }
    const isMssql = String(ds.engine || "mysql").toLowerCase() === "mssql";
    dsCaseInsensitive = isMssql;
    try {
      const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}/databases`);
      const classified = (r && r.databases_classified) || null;
      const userDbs = classified ? classified.filter((d) => !d.system).map((d) => d.name) : ((r && r.databases) || []);
      if (isMssql) {
        // MSSQL: 시스템 DB(master/model/msdb)를 고정칩으로(catalog 접근 — sys 스키마는 런타임 차단).
        lockedChips = classified
          ? classified.filter((d) => d.system).map((d) => ({ name: d.name, present: true }))
          : [];
      } else {
        // MySQL: 메타데이터 4종(information_schema 등)을 고정칩으로 유지(DB==스키마, 시스템 스키마 경계).
        lockedChips = _defaultLocked.slice();
      }
      availableUserDbs = userDbs;
    } catch (e) {
      lockedChips = isMssql ? [] : _defaultLocked.slice();
      availableUserDbs = [];
      showToast("데이터소스 DB 목록 조회 실패 — 연결/권한 확인.", true);
    }
    redrawChips();
    buildPicker();
  };

  // ── 멀티 datasource (P2): product → datasource 바인딩 + 연결테스트 (TASK-0206: 접근가능DB 위로 이동) ──
  // 백엔드 PATCH datasource 는 console.manage 권한이라 컨트롤도 그 권한으로 게이트(불일치 방지).
  {
    const canDs = can("console.manage");
    const dsSection = document.createElement("div");
    dsSection.className = "admin-detail-section";
    const dsTitle = document.createElement("div");
    dsTitle.className = "admin-detail-section-title";
    dsTitle.textContent = "데이터 소스 (datasource)";
    dsSection.appendChild(dsTitle);

    const dsHint = document.createElement("div");
    dsHint.className = "admin-detail-hint";
    if (!adminState.datasourcesEnabled) {
      dsHint.textContent = "멀티 datasource 비활성(AGENT_MULTI_DATASOURCE_ENABLED=0). 바인딩은 저장되나 flag 활성화 전까지는 기본 MySQL 로 동작합니다.";
    } else {
      dsHint.textContent = "이 제품의 대화가 분석할 데이터 소스. 데이터는 데이터 소스에 종속됩니다 — 선택하면 아래 '접근 가능 데이터베이스' 목록이 갱신됩니다. RO 유저는 허용 DB 에만 GRANT SELECT 되어야 합니다.";
    }
    dsSection.appendChild(dsHint);

    const dsRow = document.createElement("div");
    dsRow.className = "admin-db-picker-row";
    const dsSelect = document.createElement("select");
    dsSelect.disabled = !canDs;
    const optDefault = document.createElement("option");
    optDefault.value = "";
    optDefault.textContent = "(기본 단일 MySQL)";
    dsSelect.appendChild(optDefault);
    (adminState.datasources || []).forEach((ds) => {
      const opt = document.createElement("option");
      opt.value = ds.key;
      opt.textContent = `${ds.key} — ${ds.engine || "mysql"} @ ${ds.host || "?"}:${ds.port || ""}`;
      dsSelect.appendChild(opt);
    });
    dsSelect.value = product.datasource_key || "";

    const dsResult = document.createElement("span");
    dsResult.className = "admin-ds-test-result";

    // TASK-0206: 별도 "참조 DB" 드롭다운 폐지 — DB 선택은 아래 '접근 가능 데이터베이스'(DB-단위 multi-select)
    // 로 흡수. datasource 변경 시 접근가능DB 목록을 datasource-driven 으로 재구성한다.
    dsSelect.addEventListener("change", async () => {
      const val = dsSelect.value || null;
      dsResult.textContent = "";
      dsResult.className = "admin-ds-test-result";
      try {
        await apiFetch(`/api/admin/products/${product.id}/datasource`, {
          method: "PATCH",
          body: JSON.stringify({ datasource_key: val, datasource_database: null }),
        });
        // 로컬 product 객체 갱신 (재로드 없이 일관). datasource 변경 시 참조 DB 초기화.
        product.datasource_database = null;
        product.datasource_key = val;
        const p = (adminState.products || []).find((x) => Number(x.id) === Number(product.id));
        if (p) { p.datasource_key = val; p.datasource_database = null; }
        _selectedDatasourceKey = val || "";
        showToast(val ? `datasource '${val}' 바인딩됨` : "기본 MySQL 로 환원됨");
        _refreshAccessibleDbs(_selectedDatasourceKey);  // 접근가능DB 목록 datasource-driven 갱신
      } catch (error) {
        dsSelect.value = product.datasource_key || "";
        showToast(error.message || "datasource 바인딩 실패", true);
      }
    });

    const testBtn = document.createElement("button");
    testBtn.type = "button";
    testBtn.className = "btn-secondary";
    testBtn.textContent = "연결 테스트";
    testBtn.disabled = !canDs;
    testBtn.addEventListener("click", async () => {
      const key = dsSelect.value;
      if (!key) { showToast("테스트할 datasource 를 먼저 선택하세요.", true); return; }
      testBtn.disabled = true;
      dsResult.textContent = "테스트 중…";
      dsResult.className = "admin-ds-test-result";
      try {
        const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}/test`, { method: "POST" });
        if (r && r.ok) {
          dsResult.textContent = `✓ 연결 성공 (${r.elapsed_ms}ms)`;
          dsResult.className = "admin-ds-test-result admin-ds-test-ok";
        } else {
          dsResult.textContent = `✗ 실패 (${(r && r.error) || "unknown"})`;
          dsResult.className = "admin-ds-test-result admin-ds-test-fail";
        }
      } catch (error) {
        dsResult.textContent = `✗ ${error.message || "테스트 실패"}`;
        dsResult.className = "admin-ds-test-result admin-ds-test-fail";
      } finally {
        testBtn.disabled = !canDs;
      }
    });

    dsRow.append(dsSelect, testBtn, dsResult);
    dsSection.appendChild(dsRow);
    // TASK-0206 UX: 데이터 소스 섹션을 '접근 가능 데이터베이스' 위로 배치(데이터→데이터소스 종속 흐름 시각화).
    paneEl.appendChild(dsSection);
    paneEl.appendChild(dbSection);
    // 초기 로드: 제품에 바인딩된 datasource 의 DB 목록으로 접근가능DB 구성(미바인딩이면 데이터 MySQL 기본값).
    _refreshAccessibleDbs(_selectedDatasourceKey);
  }

  // Product-scope system prompt
  if (canManage) {
    const promptSection = buildSystemPromptEditor({
      scope: "product",
      productId: Number(product.id),
      roleId: null,
      accountId: null,
      title: "제품 프롬프트",
      fixedProductId: Number(product.id),
      autoGenerateProductId: Number(product.id),
    });
    paneEl.appendChild(promptSection);
  }

  // Delete
  if (canManage) {
    const actions = document.createElement("div");
    actions.className = "admin-detail-actions";
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-secondary danger";
    deleteBtn.textContent = "삭제";
    deleteBtn.addEventListener("click", async () => {
      if (!window.confirm(`${product.name} 제품을 삭제할까요? (참조 대화가 있으면 실패합니다)`)) return;
      try {
        await apiFetch(`/api/admin/products/${Number(product.id)}`, { method: "DELETE" });
        adminState.selectedProductId = null;
        showToast("삭제됨");
        await loadAdminData();
      } catch (error) {
        showToast(error.message || "삭제 실패", true);
      }
    });
    actions.appendChild(deleteBtn);
    paneEl.appendChild(actions);
  }
}

function startNewProduct() {
  const key = (window.prompt("Product Key (A-Z0-9_, 32자 이내)") || "").trim().toUpperCase();
  if (!key) return;
  if (!/^[A-Z][A-Z0-9_]{0,31}$/.test(key)) {
    showToast("Key 형식 오류", true);
    return;
  }
  const name = (window.prompt("표시 이름", key) || "").trim();
  if (!name) return;
  apiFetch("/api/admin/products", {
    method: "POST",
    body: JSON.stringify({ product_key: key, name, description: "" }),
  })
    .then(async (payload) => {
      adminState.selectedProductId = Number(payload.product_id);
      showToast("제품을 생성했습니다.");
      await loadAdminData();
    })
    .catch((error) => {
      showToast(error.message || "생성 실패", true);
    });
}

/* ── Product subcatalog (TASK-0053 Phase B/C — Role / Account detail) ── */

/**
 * Role detail 의 product 카드 — product 별로 접근 토글 + role-scope system prompt 묶음.
 * @param {{role: object, disabled: boolean, onPermissionChange: function}} args
 * role.permission_codes 가 toggle 의 source-of-truth. onPermissionChange(nextCodesArray) 가 호출되어
 * pending 에 반영되도록 caller 가 처리한다.
 */
function buildRoleProductCard({ role, product, perm, disabled, onToggle }) {
  const card = document.createElement("details");
  card.className = "admin-product-card";
  card.dataset.productId = String(product.id);

  const summary = document.createElement("summary");
  summary.className = "admin-product-card-head";
  // 접근 토글 (체크박스) — summary 안에 두어 펼치지 않고도 접근 가능.
  const toggleLabel = document.createElement("label");
  toggleLabel.className = "permission-toggle admin-product-card-toggle";
  // 클릭 시 details 가 토글되지 않도록 stopPropagation
  toggleLabel.addEventListener("click", (e) => e.stopPropagation());
  const toggleInput = document.createElement("input");
  toggleInput.type = "checkbox";
  toggleInput.value = perm.code;
  const granted = Array.isArray(role.permission_codes) && role.permission_codes.includes(perm.code);
  toggleInput.checked = granted;
  toggleInput.disabled = disabled;
  toggleInput.addEventListener("change", () => {
    onToggle(perm.code, toggleInput.checked);
  });
  toggleLabel.append(toggleInput);

  const info = document.createElement("span");
  info.className = "admin-product-card-info";
  const name = document.createElement("strong");
  name.textContent = product.name || product.product_key;
  const meta = document.createElement("small");
  meta.textContent = product.is_default ? "default · " + product.product_key : product.product_key;
  info.append(name, meta);

  summary.append(toggleLabel, info);
  card.appendChild(summary);

  // 본문: role-scope prompt textarea (펼쳤을 때 노출).
  if (role && role.id && !String(role.id).startsWith("new:") && can("system_prompt.manage.role.any")) {
    const promptBody = document.createElement("div");
    promptBody.className = "admin-product-card-body";
    const editor = buildSystemPromptEditor({
      scope: "role",
      roleId: Number(role.id),
      title: `${product.name} × ${role.name || role.key} 프롬프트`,
      hint: `이 제품과 역할에만 적용됩니다.`,
      fixedProductId: Number(product.id),
    });
    promptBody.appendChild(editor);
    card.appendChild(promptBody);
  }
  return card;
}

function buildRoleProductCardList(role, disabled, opts = {}) {
  // 사용자 follow-up (2026-05-07): embed=true 면 권한 grid 의 'product' 그룹 details 안에 inline 배치 —
  // 별도 section title/hint 는 부모 details summary 가 이미 "제품" 라벨을 보여주므로 중복 회피.
  const { embed = false } = opts;
  const wrap = document.createElement("div");
  wrap.className = embed ? "admin-product-card-list admin-product-card-list-embedded" : "admin-product-card-list admin-detail-section";
  if (!embed) {
    const head = document.createElement("div");
    head.className = "admin-detail-section-title";
    head.textContent = "제품별 접근";
    wrap.appendChild(head);
  }
  const hint = document.createElement("div");
  hint.className = "admin-detail-hint";
  hint.textContent = embed
    ? "제품별 접근 및 프롬프트 편집"
    : "제품별 접근 및 프롬프트 편집. 변경은 일괄 저장됩니다.";
  wrap.appendChild(hint);

  const dynamicPerms = dynamicProductPermissions();
  const permByProductId = new Map(dynamicPerms.map((p) => [Number(p.product_id), p]));
  const products = adminState.products || [];

  const onToggle = (code, granted) => {
    const current = new Set((role.permission_codes || []).map(String));
    if (granted) current.add(code);
    else current.delete(code);
    setRolePending(role.id, { permission_codes: Array.from(current) });
    renderRoleList();
  };

  if (!products.length) {
    const empty = document.createElement("div");
    empty.className = "admin-meta";
    empty.textContent = "(없음)";
    wrap.appendChild(empty);
  } else {
    products.forEach((product) => {
      const perm = permByProductId.get(Number(product.id));
      if (!perm) return;
      const card = buildRoleProductCard({ role, product, perm, disabled, onToggle });
      wrap.appendChild(card);
    });
  }

  // "Product 무관" 카드 — role-scope prompt 의 product-agnostic generic.
  if (role && role.id && !String(role.id).startsWith("new:") && can("system_prompt.manage.role.any")) {
    const genericCard = document.createElement("details");
    genericCard.className = "admin-product-card admin-product-card-generic";
    const summary = document.createElement("summary");
    summary.className = "admin-product-card-head";
    const info = document.createElement("span");
    info.className = "admin-product-card-info";
    const name = document.createElement("strong");
    name.textContent = "전체 제품";
    const meta = document.createElement("small");
    meta.textContent = "Product 와 무관하게 이 역할에 누적 적용";
    info.append(name, meta);
    summary.append(info);
    genericCard.appendChild(summary);
    const body = document.createElement("div");
    body.className = "admin-product-card-body";
    const editor = buildSystemPromptEditor({
      scope: "role",
      roleId: Number(role.id),
      title: "전체 제품 프롬프트",
      hint: "모든 제품에 적용됩니다.",
      fixedProductId: 0, // 0 = product 무관 (Phase 1B catalog 의 NULL 매칭)
    });
    body.appendChild(editor);
    genericCard.appendChild(body);
    wrap.appendChild(genericCard);
  }
  return wrap;
}

/**
 * Account detail 의 product 카드 — product 별 access override (allow/deny/inherit).
 */
function buildAccountProductOverrideList(account, disabled, opts = {}) {
  // 사용자 follow-up (2026-05-07): embed=true 면 권한 override grid 의 'product' 그룹 details 안에 inline.
  const { embed = false } = opts;
  const wrap = document.createElement("div");
  wrap.className = embed ? "admin-product-card-list admin-product-card-list-embedded" : "admin-product-card-list admin-detail-section";
  if (!embed) {
    const head = document.createElement("div");
    head.className = "admin-detail-section-title";
    head.textContent = "제품별 접근";
    wrap.appendChild(head);
  }
  const hint = document.createElement("div");
  hint.className = "admin-detail-hint";
  hint.textContent = "역할 권한을 계정별로 재설정합니다.";
  wrap.appendChild(hint);

  const dynamicPerms = dynamicProductPermissions();
  const permByProductId = new Map(dynamicPerms.map((p) => [Number(p.product_id), p]));
  const products = adminState.products || [];
  const overrides = account.permission_overrides || {};

  const onChange = (code, value) => {
    const next = { ...(account.permission_overrides || {}) };
    if (value === "inherit") {
      delete next[code];
    } else {
      next[code] = value;
    }
    setAccountPending(account.id, { permission_overrides: next });
  };

  if (!products.length) {
    const empty = document.createElement("div");
    empty.className = "admin-meta";
    empty.textContent = "(없음)";
    wrap.appendChild(empty);
    return wrap;
  }
  products.forEach((product) => {
    const perm = permByProductId.get(Number(product.id));
    if (!perm) return;
    const card = document.createElement("div");
    card.className = "admin-product-card admin-product-card-flat";
    const info = document.createElement("span");
    info.className = "admin-product-card-info";
    const name = document.createElement("strong");
    name.textContent = product.name || product.product_key;
    const meta = document.createElement("small");
    meta.textContent = product.is_default ? "default · " + product.product_key : product.product_key;
    info.append(name, meta);
    card.appendChild(info);
    const select = document.createElement("select");
    select.dataset.overrideCode = perm.code;
    select.disabled = disabled;
    [
      ["inherit", "상속"],
      ["allow", "허용"],
      ["deny", "거부"],
    ].forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      opt.selected = (overrides[perm.code] || "inherit") === value;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => onChange(perm.code, select.value));
    card.appendChild(select);
    wrap.appendChild(card);
  });
  return wrap;
}


/* ── System prompt editor (공용 — role / product / account scope) ────── */

function buildSystemPromptEditor({ scope, productId = null, roleId = null, accountId = null, title, hint, fixedProductId = null, autoGenerateProductId = null }) {
  const section = document.createElement("div");
  section.className = "admin-detail-section";
  const sectionTitle = document.createElement("div");
  sectionTitle.className = "admin-detail-section-title";
  sectionTitle.textContent = title || "시스템 프롬프트";
  section.appendChild(sectionTitle);
  if (hint) {
    const hintEl = document.createElement("div");
    hintEl.className = "admin-detail-hint";
    hintEl.textContent = hint;
    section.appendChild(hintEl);
  }

  // TASK-0095: GLOBAL scope 는 product/role/account 모두 무시 (force NULL).
  // product select 도 표시하지 않는다 — 단일 row 운영.
  const isGlobal = scope === "global";

  const products = adminState.products || [];
  let currentProductId = productId;
  if (fixedProductId !== null && fixedProductId !== undefined) {
    currentProductId = Number(fixedProductId);
  } else if (!currentProductId && products.length) {
    const def = products.find((p) => p.is_default) || products[0];
    currentProductId = def ? Number(def.id) : null;
  }

  let productSelect = null;
  if (!isGlobal && scope !== "product" && !fixedProductId) {
    const row = document.createElement("div");
    row.className = "admin-inline-row";
    const label = document.createElement("span");
    label.className = "field-label";
    label.textContent = "제품 범위";
    productSelect = document.createElement("select");
    const optNone = document.createElement("option");
    optNone.value = "";
    optNone.textContent = "(모든 제품)";
    productSelect.appendChild(optNone);
    products.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = String(p.id);
      opt.textContent = `${p.name} (${p.product_key})`;
      if (Number(p.id) === Number(currentProductId)) opt.selected = true;
      productSelect.appendChild(opt);
    });
    row.append(label, productSelect);
    section.appendChild(row);
  }

  const textarea = document.createElement("textarea");
  textarea.className = "admin-prompt-textarea";
  textarea.placeholder = "이 스코프에서 누적 적용할 시스템 프롬프트. 비워두고 적용하면 기존 프롬프트가 삭제됩니다.";
  textarea.rows = 6;
  section.appendChild(textarea);

  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  section.appendChild(metaEl);

  if (autoGenerateProductId) {
    const autoBtn = document.createElement("button");
    autoBtn.type = "button";
    autoBtn.className = "btn-secondary";
    autoBtn.textContent = "자동 작성";
    autoBtn.addEventListener("click", async () => {
      autoBtn.disabled = true;
      autoBtn.textContent = "생성 중…";
      try {
        const payload = await apiFetch(
          `/api/admin/products/${autoGenerateProductId}/prompt/generate`,
          { method: "POST" },
        );
        if (payload && payload.prompt) {
          textarea.value = payload.prompt;
          const pid = resolveProductId();
          setSystemPromptPending({ scope, productId: pid, roleId, accountId, content: payload.prompt });
          metaEl.textContent = "(자동 생성됨 — 검토 후 저장하세요)";
        }
      } catch (error) {
        metaEl.textContent = `자동 생성 실패: ${error.message || error}`;
      } finally {
        autoBtn.disabled = false;
        autoBtn.textContent = "자동 작성";
      }
    });
    section.appendChild(autoBtn);
  }

  const resolveProductId = () => {
    if (productSelect) {
      const v = productSelect.value;
      return v ? Number(v) : null;
    }
    return currentProductId || null;
  };

  const refresh = async () => {
    const pid = resolveProductId();
    // pending 우선 — 사용자가 입력한 값이 reload 로 덮어써지지 않도록.
    const pendingEntry = getSystemPromptPending({ scope, productId: pid, roleId, accountId });
    if (pendingEntry) {
      textarea.value = pendingEntry.content;
      metaEl.textContent = "(미저장 변경)";
      return;
    }
    const params = new URLSearchParams({ scope });
    if (pid) params.set("product_id", String(pid));
    if (roleId) params.set("role_id", String(roleId));
    if (accountId) params.set("account_id", String(accountId));
    try {
      const payload = await apiFetch(`/api/admin/system-prompts?${params.toString()}`);
      const row = payload.prompt;
      if (row) {
        textarea.value = row.content || "";
        metaEl.textContent = `마지막 수정: ${formatDateTime(row.updated_at)}`;
      } else {
        textarea.value = "";
        metaEl.textContent = "(없음)";
      }
    } catch (error) {
      metaEl.textContent = `조회 실패: ${error.message || error}`;
    }
  };

  if (productSelect) productSelect.addEventListener("change", refresh);
  refresh();

  textarea.addEventListener("input", () => {
    const pid = resolveProductId();
    setSystemPromptPending({
      scope,
      productId: pid,
      roleId,
      accountId,
      content: textarea.value,
    });
    metaEl.textContent = "(미저장 변경)";
  });

  return section;
}

/* ── Initialize ──────────────────────────────────────────────────────── */

async function initialize() {
  // TASK-0098: admin self endpoint 분리 — `/api/auth/me` 의 permissions 필드가
  // 제거되어도 admin 콘솔 진입이 깨지지 않도록 admin 전용 self endpoint
  // `/api/admin/me` 로 전환. backend 가 console.access 미보유 시 403 → catch.
  const me = await apiFetch("/api/admin/me").catch(() => null);
  if (!me || !me.ok || !me.user?.permissions?.["console.access"]) {
    window.location.href = "/";
    return;
  }
  adminState.me = me.user;

  // Tab switches
  document.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.adminTab));
  });

  // TASK-0073 Phase C: audit pane filter handlers + tab visibility gate.
  attachAuditFilterHandlers();
  const auditTab = $("adminTabAudits");
  if (auditTab) {
    const canRead = Boolean(
      adminState.me?.permissions?.["audit.read.own"] ||
      adminState.me?.permissions?.["audit.read.any"]
    );
    auditTab.style.display = canRead ? "" : "none";
  }
  // TASK-0136: LLM 사용량 tab 가시성 게이트 (admin 전용 console.usage.read).
  const usageTab = $("adminTabUsage");
  if (usageTab) {
    usageTab.style.display = adminState.me?.permissions?.["console.usage.read"] ? "" : "none";
  }
  const usageDaysSel = $("usageDaysSel");
  if (usageDaysSel && !usageDaysSel.dataset.bound) {
    usageDaysSel.dataset.bound = "1";
    usageDaysSel.addEventListener("change", () => loadUsage());
  }
  // TASK-0166: 집계 단위(시/일/주/월) 변경 시 재조회.
  const usageGranSel = $("usageGranSel");
  if (usageGranSel && !usageGranSel.dataset.bound) {
    usageGranSel.dataset.bound = "1";
    usageGranSel.addEventListener("change", () => loadUsage());
  }
  // TASK-0184: 계정 drill-down 컨트롤(검색·페이지 크기·이전/다음). loadUsage 클로저의 _renderDrill 호출.
  const _drillRerender = () => { if (adminState.usage._renderDrill) adminState.usage._renderDrill(); };
  const usageDrillSearch = $("usageDrillSearch");
  if (usageDrillSearch && !usageDrillSearch.dataset.bound) {
    usageDrillSearch.dataset.bound = "1";
    usageDrillSearch.addEventListener("input", () => {
      adminState.usage.drillQuery = usageDrillSearch.value || "";
      adminState.usage.drillPage = 0;
      _drillRerender();
    });
  }
  const usageDrillPageSize = $("usageDrillPageSize");
  if (usageDrillPageSize && !usageDrillPageSize.dataset.bound) {
    usageDrillPageSize.dataset.bound = "1";
    usageDrillPageSize.addEventListener("change", () => {
      adminState.usage.drillPageSize = parseInt(usageDrillPageSize.value, 10) || 10;
      adminState.usage.drillPage = 0;
      _drillRerender();
    });
  }
  const usageDrillPrev = $("usageDrillPrev");
  if (usageDrillPrev && !usageDrillPrev.dataset.bound) {
    usageDrillPrev.dataset.bound = "1";
    usageDrillPrev.addEventListener("click", () => { adminState.usage.drillPage -= 1; _drillRerender(); });
  }
  const usageDrillNext = $("usageDrillNext");
  if (usageDrillNext && !usageDrillNext.dataset.bound) {
    usageDrillNext.dataset.bound = "1";
    usageDrillNext.addEventListener("click", () => { adminState.usage.drillPage += 1; _drillRerender(); });
  }
  // TASK-0158: 대시보드 첨부 권한 drift 진단 카드 (console.access 권한자만, 진입 시 1회 로드).
  loadGrantHealth();

  // Account filter buttons
  document.querySelectorAll("[data-account-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-account-filter]").forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      adminState.accountFilter = btn.dataset.accountFilter;
      adminState.accountPage = 0;
      renderAccountList();
    });
  });

  // Account search
  let accountSearchTimer = null;
  $("accountSearch").addEventListener("input", (ev) => {
    clearTimeout(accountSearchTimer);
    accountSearchTimer = window.setTimeout(() => {
      adminState.accountSearch = ev.target.value;
      adminState.accountPage = 0;
      renderAccountList();
    }, 150);
  });

  // Account select-all — TASK-0061 Phase 7 (AC-0098): 현재 페이지 row 만 대상.
  $("accountSelectAll").addEventListener("change", (ev) => {
    const visible = currentPageAccounts();
    if (ev.target.checked) {
      visible.forEach((a) => adminState.accountSelected.add(Number(a.id)));
    } else {
      visible.forEach((a) => adminState.accountSelected.delete(Number(a.id)));
    }
    renderAccountList();
    renderAccountBulkBar();
  });

  // Role search
  let roleSearchTimer = null;
  $("roleSearch").addEventListener("input", (ev) => {
    clearTimeout(roleSearchTimer);
    roleSearchTimer = window.setTimeout(() => {
      adminState.roleSearch = ev.target.value;
      renderRoleList();
    }, 150);
  });

  // Role select-all
  $("roleSelectAll").addEventListener("change", (ev) => {
    const visible = filteredRoles();
    if (ev.target.checked) {
      visible.forEach((r) => adminState.roleSelected.add(String(r.id)));
    } else {
      visible.forEach((r) => adminState.roleSelected.delete(String(r.id)));
    }
    renderRoleList();
  });

  // New role
  $("newRoleBtn").addEventListener("click", () => {
    if (!can("console.manage") || !can("role.create")) {
      showToast("권한 없음", true);
      return;
    }
    startNewRole();
  });

  // Product search + new product
  const productSearchEl = $("productSearch");
  if (productSearchEl) {
    let productSearchTimer = null;
    productSearchEl.addEventListener("input", (ev) => {
      clearTimeout(productSearchTimer);
      productSearchTimer = window.setTimeout(() => {
        adminState.productSearch = ev.target.value;
        renderProductList();
      }, 150);
    });
  }
  const newProductBtn = $("newProductBtn");
  if (newProductBtn) {
    newProductBtn.addEventListener("click", () => {
      if (!can("product.manage")) {
        showToast("권한 없음", true);
        return;
      }
      startNewProduct();
    });
  }

  // DESIGN.md §12 Phase A — Products select-all
  const productSelectAllEl = $("productSelectAll");
  if (productSelectAllEl) {
    productSelectAllEl.addEventListener("change", (ev) => {
      const visible = filteredProducts();
      if (ev.target.checked) {
        visible.forEach((p) => adminState.productSelected.add(Number(p.id)));
      } else {
        visible.forEach((p) => adminState.productSelected.delete(Number(p.id)));
      }
      renderProductList();
    });
  }

  // DESIGN.md §9 — Esc 글로벌 핸들러: 현재 active pane 의 선택 해제
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    // input/textarea/contenteditable 안에서는 무시 (form 입력 보호)
    const t = ev.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    let cleared = false;
    if (adminState.tab === "accounts" && adminState.accountSelected.size > 0) {
      adminState.accountSelected.clear();
      adminState.accountLastClickIdx = -1;
      renderAccountList();
      cleared = true;
    } else if (adminState.tab === "roles" && adminState.roleSelected.size > 0) {
      adminState.roleSelected.clear();
      adminState.roleLastClickIdx = -1;
      renderRoleList();
      cleared = true;
    } else if (adminState.tab === "products" && adminState.productSelected.size > 0) {
      adminState.productSelected.clear();
      adminState.productLastClickIdx = -1;
      renderProductList();
      cleared = true;
    }
    if (cleared) ev.preventDefault();
  });

  // Commit bar
  $("commitApplyBtn").addEventListener("click", () => {
    applyAllPending().catch((error) => {
      showToast(error.message || "적용 중 오류", true);
    });
  });
  $("commitCancelBtn").addEventListener("click", cancelAllPending);

  // REQ-20260518-0006: refreshAdminBtn / adminLogoutBtn 제거 — 사용자 직접 테스트에서 거의 사용 안 되는 것으로 확인.
  // backToAppBtn 만 유지 (작업 화면 ↔ 관리 콘솔 빠른 전환). 로그아웃은 작업 화면의 프로필 drawer 에서 가능.
  $("backToAppBtn").addEventListener("click", () => {
    if (pendingChangeCount() > 0 && !window.confirm("저장되지 않은 변경사항이 있습니다. 계속하시겠습니까?")) return;
    document.body.classList.add("is-leaving");
    setTimeout(() => { window.location.href = "/"; }, 150);
  });

  window.addEventListener("beforeunload", (ev) => {
    if (pendingChangeCount() > 0) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });

  await loadAdminData();

  // DESIGN.md §4 — runtime contract assertion (drift 재발 차단, best-effort)
  ["accounts", "roles", "products"].forEach((entity) => {
    try { assertBulkBarContract(entity); }
    catch (err) { console.error(err); }
  });
}

initialize().catch((error) => {
  showToast(error.message || "콘솔 로드 실패", true);
});

