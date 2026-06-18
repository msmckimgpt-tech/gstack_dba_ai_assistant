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
  // TASK-0244: '+ 데이터소스 추가' 드롭다운의 연결 상태 캐시 (key(lower) -> {state:'checking'|'ok'|'fail', elapsed_ms, error}).
  //  드롭다운 열림 시 /test 로 lazy probe → 배지로 표면화. 세션 내 재사용(매 토글마다 재probe 방지), 헤더 ↻ 로 강제 갱신.
  datasourceConnStatus: new Map(),
  // TASK-0255 R2: insight-worker 가 PG 에 영속한 datasource 스캔 health (key(lower) -> insight_health dict).
  //   web live conn_status 와 별개 — "연결 불안정 미커버" vs "권한 실패" 를 구분 표시.
  datasourceInsightHealth: new Map(),
  datasourcesEnabled: false,  // AGENT_MULTI_DATASOURCE_ENABLED flag
  datasourcesSsrfPrivateGuard: true,  // TASK-0219: 사설/링크로컬 SSRF 경계 활성 여부(안내 문구 정합)
  tab: "dashboard",
  accountFilter: "all",
  accountSearch: "",
  accountPage: 0,
  accountSelected: new Set(),
  selectedAccountId: null,
  roleSearch: "",
  roleFilter: "all",            // 계정 탭과 동형: all|active|inactive (역할엔 soft-delete 없음 → 삭제됨 분기 없음)
  roleSelected: new Set(),
  selectedRoleId: null,
  productSearch: "",
  productFilter: "all",         // 계정 탭과 동형: all|active|inactive (제품도 hard-delete 라 삭제됨 분기 없음)
  selectedProductId: null,
  // DESIGN.md §4 / §12 Phase A — Products multi-select (단일 selectedProductId 와 동거)
  productSelected: new Set(),
  // TASK-0278 — Datasources multi-select (단일 _dsSelectedKey 와 동거). key 는 문자열.
  datasourceSelected: new Set(),
  // DESIGN.md §9 — shift-click range 의 anchor index (visible 범위 내)
  accountLastClickIdx: -1,
  roleLastClickIdx: -1,
  productLastClickIdx: -1,
  datasourceLastClickIdx: -1,
  productDbDraft: new Map(),
  // TASK-0223: 제품별 insight-worker 분석 완료율 (productId -> {pct, analyzed_objects, total_objects, per_db[], measurable, reason, engine}).
  productCoverage: new Map(),
  // TASK-0253: 완료율 로딩 상태를 **제품별**로 추적(productId 집합). 이전엔 전역 bool 하나라
  //  모든 제품을 한 번에 fetch → 가장 느린 제품이 끝나야 빠른 제품 배지도 갱신되는 head-of-line
  //  이 있었다. 이제 제품마다 단건 API 를 병렬 호출하고, 각 제품이 끝나는 즉시 그 제품 배지만
  //  settle 한다. _isProductCoverageLoading(pid) 로 조회.
  productCoverageLoadingIds: new Set(),
  // TASK-0242: 제품 datasource 별 DB insight 파악 내용 (key `${pid}::${dsKey}` -> {ok, by_db{<db>:{...}}, worker, scope, engine}).
  //  coverage 가 '얼마나'면 이건 '무엇을(역할/도메인)' — 각 DB 행 한 줄 설명 + 추가 picker 상태 표시용.
  productDbInsights: new Map(),
  productDbInsightsLoading: new Set(),   // 로딩 중인 key(`${pid}::${dsKey}`) 집합
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
    productDatasources: new Map(),// TASK-0239: productId -> {baseline:[{key,is_primary}], desired:[{key,is_primary}]} (바인딩 추가/제거/기본지정 일괄 적용)
    systemPrompts: new Map(),     // key "scope:productId:roleId:accountId" -> {scope, productId, roleId, accountId, content}
  },
  nextTempRoleId: 1,
};

const METADATA_SCHEMAS = ["information_schema", "mysql", "sys", "performance_schema"];
const INTERNAL_SCHEMAS = new Set(["agent_memory"]);

// ── TASK-20260618T025755: '+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택 ──────────
//  사내 서비스는 데이터소스의 DB 추가/삭제가 잦아, 후보 DB 가 많을 때 원하는 DB 를 빠르게
//  찾거나(검색) 패턴으로 한 번에 선택(정규식)할 수 있게 한다. 후보가 이 수 이상일 때만
//  toolbar 를 노출한다(소수 목록은 불필요). 자매 제품 드롭업 검색필터(PRODUCT_DROPUP_SEARCH_MIN)
//  와 동일 idiom. 아래 4개는 순수/DOM helper — admin.js 상태에 의존하지 않아 jsdom 으로 검증한다.
const DB_PICKER_SEARCH_MIN = 6;

// 검색 부분일치(대소문자 무시). 순수 함수 — 일치하는 이름만 반환.
function dbPickerFilterNames(names, query) {
  const q = String(query == null ? "" : query).trim().toLowerCase();
  if (!q) return (names || []).slice();
  return (names || []).filter((n) => String(n).toLowerCase().includes(q));
}

// 정규식 다중 매칭(대소문자 무시 'i'). 순수 함수 — { ok, matches, error }.
//  ok=false 면 정규식 컴파일 실패(error 메시지). 빈 패턴은 ok=true + 빈 matches.
function dbPickerRegexMatches(names, pattern) {
  const pat = String(pattern == null ? "" : pattern).trim();
  if (!pat) return { ok: true, matches: [], error: null };
  let re;
  try {
    re = new RegExp(pat, "i");
  } catch (e) {
    return { ok: false, matches: [], error: (e && e.message) || "정규식 오류" };
  }
  const matches = (names || []).filter((n) => re.test(String(n)));
  return { ok: true, matches, error: null };
}

// 드롭다운 항목(.admin-db-picker-item)에 검색어 적용 — .hidden 토글 + 표시 개수 반환.
//  item.dataset.search 는 buildPicker 가 채운 소문자 DB명.
function applyDbPickerSearch(listEl, query) {
  const q = String(query == null ? "" : query).trim().toLowerCase();
  let shown = 0;
  (listEl ? listEl.querySelectorAll(".admin-db-picker-item") : []).forEach((it) => {
    const hay = it.dataset.search || "";
    const hit = !q || hay.includes(q);
    it.classList.toggle("hidden", !hit);
    if (hit) shown += 1;
  });
  return shown;
}

// 정규식 일치 항목에 .is-regex-match 하이라이트(적용 전 미리보기 = "조회 가능").
//  반환: { ok, count, error }. 빈/오류 패턴이면 하이라이트 전부 해제.
function applyDbPickerRegexHighlight(listEl, pattern) {
  const items = listEl ? Array.from(listEl.querySelectorAll(".admin-db-picker-item")) : [];
  const names = items.map((it) => it.dataset.dbname || "");
  const res = dbPickerRegexMatches(names, pattern);
  const active = !!String(pattern == null ? "" : pattern).trim() && res.ok;
  const matchSet = new Set((res.matches || []).map((n) => String(n).toLowerCase()));
  items.forEach((it) => {
    it.classList.toggle("is-regex-match", active && matchSet.has(it.dataset.dbname || ""));
  });
  return { ok: res.ok, count: active ? matchSet.size : 0, error: res.error };
}

function systemPromptPendingKey({ scope, productId = null, roleId = null, accountId = null }) {
  return `${scope}:${productId || 0}:${roleId || 0}:${accountId || 0}`;
}

// TASK-0052 Phase 1D: 'product' 그룹 추가. backend `PERMISSION_DEFINITIONS[*].group` (app.py) 와 키 정합 필수.
// product 그룹은 정적 `product.manage` / `system_prompt.manage.role.any` 외에 동적 `product.access.<key>`
// 코드들 (Phase 1B 의 _ensure_product_access_permissions backfill) 도 자동으로 그룹에 합류된다.
// TASK-0073 Phase C: audit group 추가 — backend PERMISSION_DEFINITIONS 의 group="audit" 와 key 정합.
// TASK-0095: settings group 추가 — 전역 시스템 프롬프트 (system_prompt.global.read/write).
// TASK-0094 Sprint 1 Phase 12: attachment group 추가 (8 group).
// TASK-0269: 대화 그룹을 own/any 로 분리 — conversation → conversation_own(내 대화 권한) + conversation_any(전체 대화 권한).
// TASK-0288: datasource 그룹 신설(관리 콘솔 데이터소스 권한) + 제품 권한 2축 분리 —
//   product(제품 관리, 관리 콘솔 구성: product.read/manage) ↔ product_access(제품 사용,
//   작업 화면에서 요청 전송: 동적 product.access.<key>). 사용자 결정 2026-06-16.
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "datasource", "audit", "settings", "product", "conversation_own", "conversation_any", "product_access", "attachment", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  datasource: "데이터소스",
  conversation_own: "내 대화 권한",
  conversation_any: "전체 대화 권한",
  product: "제품 관리",
  product_access: "제품 사용 (작업 화면)",
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
  // TASK-0288: datasource(데이터소스 관리) + product(제품 관리, 관리 콘솔 구성)는 관리 권한 section.
  { id: "manage", title: "관리 권한", description: "콘솔 진입 · 계정 · 역할 · 데이터소스 · 제품 관리 · 감사 · 시스템 설정", groups: ["console", "account", "role", "datasource", "audit", "settings", "product"] },
  // TASK-0094 Sprint 1 Phase 12: attachment 그룹은 운영 권한 묶음에 포함.
  // TASK-0288: 작업 화면 제품 사용(product_access)은 운영 권한 section — 관리 콘솔 제품 관리(product)와 분리.
  { id: "operate", title: "운영 권한", description: "내 대화 · 전체 대화 · 제품 사용 · 첨부", groups: ["conversation_own", "conversation_any", "product_access", "attachment"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

// 권한 점진적 세분화 (progressive disclosure) — 종속성 선언 맵 (childCode -> 선행 parentCode).
// renderPermissionGrid 가 각 권한 row 를 "선행 권한이 충족돼야(체크 / override=허용) 표시" 하도록 접는다.
// 비파괴 원칙: 이미 명시 설정된(체크 / override=허용·거부) row 와 그 조상은 게이트 상태와 무관하게 항상 표시 →
//   부여된 권한이 조용히 숨겨지지 않는다. 각 그룹의 숨은 row 는 "세부 권한 N개 더 보기" 로 강제 노출 가능.
//
// 구조 (CONVENTIONS.md §10.6 의 group/section 정렬은 그대로 — 본 맵은 group 내부의 표시 단계만 정의):
//  · 관리 권한 section: `console.access`(관리 콘솔 접근) 가 마스터 게이트.
//      account.read / role.read / audit.read.own / system_prompt.global.read 의 부모 = console.access →
//      console.access 가 꺼지면 계정·역할·감사·시스템설정 그룹 전체가 접혀 "관리 콘솔" 그룹만 남는다.
//      각 그룹 base 권한(account.read 등) 이 다시 그 그룹의 세부 권한을 연다.
//  · 운영 권한 section: 마스터 게이트 없음. `.any`(전체) 권한은 대응 `.own`(내) 권한을 선행으로 둔다
//      (any ⊇ own 의 참 종속). 제품·첨부는 평면.
// 백엔드 PERMISSION_DEFINITIONS(app.py) 의 code 와 1:1 정합 필수 — 회귀 테스트
//   test_permission_dependency_map.py 가 모든 key/value 가 실제 권한 code 인지 검증한다.
const PERMISSION_DEPENDENCIES = {
  // ── 관리 권한 (마스터 게이트 = console.access) ──
  "console.manage": "console.access",
  "console.usage.read": "console.access",
  "insight.reset": "console.access",
  "account.read": "console.access",
  "account.update": "account.read",
  "account.delete": "account.read",
  "account.activate": "account.read",
  "account.deactivate": "account.read",
  "account.role.assign": "account.read",
  "account.permission.override.manage": "account.read",
  "role.read": "console.access",
  "role.create": "role.read",
  "role.update": "role.read",
  "role.delete": "role.read",
  "role.permission.manage": "role.read",
  // TASK-0288: 데이터소스 — datasource.read 가 그룹 게이트(console.access 하위), manage 는 read 선행.
  "datasource.read": "console.access",
  "datasource.manage": "datasource.read",
  // TASK-0288: 제품 관리 — product.read 가 그룹 게이트(console.access 하위), manage/프롬프트는 read 선행.
  "product.read": "console.access",
  "product.manage": "product.read",
  "system_prompt.manage.role.any": "product.read",
  "audit.read.own": "console.access",
  "audit.read.any": "audit.read.own",
  "audit.export": "audit.read.own",
  "audit.purge": "audit.read.own",
  "system_prompt.global.read": "console.access",
  "system_prompt.global.write": "system_prompt.global.read",
  // ── 운영 권한 (TASK-0269 — own/any 그룹 분리 + "목록 조회" 게이트) ──
  //   내 대화 권한(conversation_own): "내 대화 목록 조회"(list.own) 가 게이트 → 동작 권한 노출.
  //     "대화 생성"(create)·"내 대화 목록 조회"(list.own) 는 루트(기반, 항상 표시).
  "conversation.read.own": "conversation.list.own",
  "conversation.ask": "conversation.list.own",
  "conversation.file.read.own": "conversation.list.own",
  "conversation.rename.own": "conversation.list.own",
  "conversation.delete.own": "conversation.list.own",
  "conversation.cancel.own": "conversation.list.own",
  "conversation.finalize.own": "conversation.list.own",
  "conversation.duplicate.own": "conversation.list.own",
  "conversation.share.create": "conversation.list.own",
  "conversation.attachment.upload.own": "conversation.list.own",
  "conversation.attachment.read.own": "conversation.list.own",
  //   전체 대화 권한(conversation_any): "전체 대화 목록 조회"(list.any) 가 게이트(루트).
  "conversation.read.any": "conversation.list.any",
  "conversation.file.read.any": "conversation.list.any",
  "conversation.rename.any": "conversation.list.any",
  "conversation.delete.any": "conversation.list.any",
  "conversation.archive.read.any": "conversation.list.any",
  "conversation.cancel.any": "conversation.list.any",
  "conversation.finalize.any": "conversation.list.any",
  "conversation.duplicate.any": "conversation.list.any",
  "conversation.attachment.upload.any": "conversation.list.any",
  "conversation.attachment.read.any": "conversation.list.any",
};

/* ── Bulk action contract — CONVENTIONS.md §10 + DESIGN.md §4~§9 ───── */

// DESIGN.md §5 / §10.4 — 카테고리별 단위 어휘
const BULK_ENTITY_UNIT = { accounts: "명", roles: "개", products: "개", datasources: "개" };
const BULK_ACTION_LABEL = { activate: "활성화", deactivate: "비활성화", delete: "삭제", insight_on: "인사이트 탐색 켜기", insight_off: "인사이트 탐색 끄기" };
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

// TASK-20260615T-profile-icon: Identicon — seed(문자열) 해시 기반 결정론적 5x5 대칭 SVG(외부 의존 0).
//   app.js 의 동명 헬퍼(_identiconHash/identiconSvg/applyAvatar)와 byte-identical — 작업화면 프로필과
//   관리 콘솔 제품 아이콘의 시각 정합을 위해 이식. 같은 seed → 항상 같은 패턴/색.
function _identiconHash(seed) {
  let h = 5381;
  const s = String(seed || "");
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h >>> 0;
}
function identiconSvg(seed, size) {
  const h = _identiconHash(seed);
  const hue = h % 360;
  const fg = `hsl(${hue},58%,52%)`;
  const bg = "#eef2f7";
  const cells = [];
  // 5열 중 좌측 3열만 결정 후 대칭 → 5x5 대칭 패턴.
  let bits = h;
  for (let col = 0; col < 3; col++) {
    for (let row = 0; row < 5; row++) {
      const on = (bits & 1) === 1; bits = bits >>> 1;
      if (on) {
        cells.push([col, row]);
        if (col < 2) cells.push([4 - col, row]);  // 대칭
      }
    }
  }
  const sz = size || 100;
  const cell = sz / 5;
  const rects = cells.map(([c, r]) =>
    `<rect x='${(c * cell).toFixed(2)}' y='${(r * cell).toFixed(2)}' width='${cell.toFixed(2)}' height='${cell.toFixed(2)}' fill='${fg}'/>`
  ).join("");
  return `<svg viewBox='0 0 ${sz} ${sz}' width='100%' height='100%' xmlns='http://www.w3.org/2000/svg' style='display:block;'><rect width='${sz}' height='${sz}' fill='${bg}'/>${rects}</svg>`;
}
// applyAvatar: el 에 이미지(url 있으면 <img>) 또는 Identicon(seed 해시) 렌더. app.js 와 동형.
//   url=설정된 이미지 API path. seed=fallback identicon 시드(username/product_key). initials=이미지 로드 실패 시 폴백.
function applyAvatar(el, { url, seed, initials }) {
  if (!el) return;
  el.textContent = "";
  el.classList.add("has-avatar-img");
  if (url) {
    const img = document.createElement("img");
    img.className = "avatar-img";
    img.alt = "";
    img.loading = "lazy";
    img.src = url;
    img.onerror = () => {
      // 이미지 로드 실패 → Identicon 폴백.
      el.removeChild(img);
      el.innerHTML = identiconSvg(seed || initials || "", 100);
    };
    el.appendChild(img);
  } else {
    el.innerHTML = identiconSvg(seed || initials || "", 100);
  }
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
  // TASK-0288: product_access(제품 사용) 그룹은 동적 권한(product.access.*) 전용이라
  // excludeDynamic 시 멤버가 0이 되어 <details> 컨테이너가 렌더되지 않는다. 그 안에 per-product
  // 접근 카드(buildRoleProductSubcatalog / buildAccountProductOverrideList)가 임베딩되므로,
  // 동적 제품 권한이 존재하면 빈 그룹이라도 컨테이너를 보장한다(임베딩 타겟).
  if (excludeDynamic && !groups.has("product_access")
      && (adminState.permissions || []).some((p) => p && p.is_dynamic && p.group === "product_access")) {
    groups.set("product_access", []);
  }
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
  // TASK-0288: 동적 제품 접근 권한은 GroupName='product_access'(제품 사용, 작업 화면) 으로 분리됨.
  return (adminState.permissions || [])
    .filter((p) => p && p.is_dynamic && (p.group === "product_access"))
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

/* ── 권한 점진적 세분화 (progressive disclosure) ─────────────────────────
   각 권한 row 를 PERMISSION_DEPENDENCIES 의 선행 권한 충족 여부에 따라 접고 편다.
   §10.6 의 group/section 정렬·DOM 구조는 그대로 두고 row 단위 hidden 토글로만 동작 →
   레이아웃 뒤틀림 없음. 비파괴: 명시 설정된 권한·그 조상은 항상 표시. */

// 그룹/섹션 가시성 + "세부 권한 N개 더 보기 / 접기" 토글 갱신.
// mode 분기 (적대 리뷰 REV MAJOR 흡수): 그룹/섹션 통째 숨김(vanish)은 **checkbox(역할) 모드만**.
//   checkbox 모드는 마스터 게이트 console.access 체크박스가 항상 보이는 복원 레버라 trap 없음.
//   override(계정) 모드는 게이트가 그 자신도 접힐 수 있는 select 라 그룹을 숨기면 "더 보기" 탈출구까지
//   같이 사라져 도달 불가 → override 모드는 그룹/섹션을 숨기지 않고(§10.6 "전체 표시" 정합) 행만 접는다.
function _refreshGroupDisclosure(containerEl, showAll, recompute, mode, isExplicit) {
  const collapseGroups = mode === "checkbox";
  containerEl.querySelectorAll("details.permission-group").forEach((groupEl) => {
    const rows = Array.from(groupEl.querySelectorAll("[data-perm-code]"));
    if (!rows.length) return; // 권한 row 없는 그룹(예: 제품 카드 only)은 건드리지 않음
    const groupKey = groupEl.dataset.permGroup;
    const hiddenCount = rows.filter((r) => r.hidden).length;
    const grantedCount = rows.filter((r) => isExplicit(r.dataset.permCode)).length;
    // checkbox 모드: 보이는 권한 row 0 이면 details 자체를 감춘다 → 마스터 게이트 OFF 시 계정·역할 등 묶음이 사라짐.
    // 단, 부여된 권한이 하나라도 있으면 그룹을 유지한다 → 부여된 권한이 영구히 가려지지 않고
    //   "더 보기 · N개 부여됨" 으로 도달 가능(TASK-0264 — forceVisible 제거 후 도달성 보장).
    // override 모드: 절대 숨기지 않음(아래 "더 보기"로 항상 도달 가능).
    groupEl.hidden = collapseGroups && hiddenCount === rows.length && grantedCount === 0;
    const isShowAll = showAll.has(groupKey);
    const list = groupEl.querySelector(".permission-grid-list");
    let more = groupEl.querySelector(".permission-group-more");
    if (hiddenCount === 0 && !isShowAll) {
      if (more) more.remove();
      return;
    }
    // 숨겨진 row 중 부여된 개수 — "더 보기" 뒤에 부여된 권한이 있음을 표면화(도달성 단서).
    const hiddenGranted = rows.filter((r) => r.hidden && isExplicit(r.dataset.permCode)).length;
    if (!more) {
      more = document.createElement("button");
      more.type = "button";
      more.className = "permission-group-more";
      more.addEventListener("click", (evt) => {
        evt.preventDefault();
        if (showAll.has(groupKey)) showAll.delete(groupKey);
        else showAll.add(groupKey);
        recompute();
      });
    }
    if (list) list.appendChild(more); // 항상 list 마지막으로
    more.textContent = isShowAll
      ? "세부 권한 접기"
      : `세부 권한 ${hiddenCount}개 더 보기${hiddenGranted ? ` · ${hiddenGranted}개 부여됨` : ""}`;
    more.classList.toggle("has-granted", !isShowAll && hiddenGranted > 0);
    more.setAttribute("aria-expanded", isShowAll ? "true" : "false");
  });
  if (!collapseGroups) return; // override 모드는 섹션도 숨기지 않음
  // 섹션: 보이는 그룹이 하나도 없으면 섹션 자체를 감춘다(방어적 — 실제로는 console/conversation 그룹이 항상 남음).
  containerEl.querySelectorAll("section.permission-section").forEach((secEl) => {
    const groups = Array.from(secEl.querySelectorAll("details.permission-group"));
    if (groups.length) secEl.hidden = !groups.some((g) => !g.hidden);
  });
}

// containerEl 전체 grid 에 disclosure 를 1회 적용(초기 + 매 변경 시 호출).
// inheritedGrants(TASK-0270): override(계정) 모드에서 "상속(허용)" 판정용 — 계정 역할이 부여한 권한 code Set.
//   상속 값은 역할이 부여하면 effective 허용 → 게이트로 동작(자식 펼침).
function _applyPermissionDisclosure(containerEl, mode, showAll, inheritedGrants) {
  const inherited = inheritedGrants || new Set();
  const wrappers = Array.from(containerEl.querySelectorAll("[data-perm-code]"));
  if (!wrappers.length) return;
  const state = new Map();
  const byCode = new Map();
  wrappers.forEach((w) => {
    const code = w.dataset.permCode;
    byCode.set(code, w);
    if (mode === "checkbox") {
      const cb = w.querySelector("input[type='checkbox']");
      state.set(code, cb && cb.checked ? "on" : "off");
    } else {
      const sel = w.querySelector("select[data-override-code]");
      state.set(code, sel ? sel.value : "inherit");
    }
  });
  // explicit = 관리자가 명시 설정(checkbox 체크 / override 허용·거부). 그룹 도달성·"부여됨" 배지에 사용.
  const isExplicit = (code) => {
    const s = state.get(code);
    return mode === "checkbox" ? s === "on" : (s === "allow" || s === "deny");
  };
  // gateSatisfied = 자식을 여는 effective 허용.
  //   checkbox(역할): 체크. override(계정, TASK-0270): "허용" 또는 "상속"이면서 역할이 그 권한을 부여(상속(허용)).
  const gateSatisfied = (code) => {
    const s = state.get(code);
    if (mode === "checkbox") return s === "on";
    return s === "allow" || (s === "inherit" && inherited.has(code));
  };
  // 가시성(TASK-0264 — "최대한 단순화"): 게이트 체인이 충족(=선행 권한이 모두 양성)돼야만 노출한다.
  //   부여 여부와 무관 — 게이트 OFF 면 부여된 세부 권한도 "더 보기" 뒤로 숨긴다(이전 forceVisible 제거).
  //   부여된 권한이 영구히 가려지지 않도록, _refreshGroupDisclosure 가 부여 항목이 있는 그룹을 비숨김 유지하고
  //   "더 보기 · N개 부여됨" 으로 도달성을 보장한다. 저장 경로는 hidden row 의 상태도 그대로 읽어 누락 0.
  const visCache = new Map();
  const isVisible = (code) => {
    if (visCache.has(code)) return visCache.get(code);
    visCache.set(code, false); // 사이클 방어(트리라 미발생이나 안전)
    const parent = PERMISSION_DEPENDENCIES[code];
    let v;
    if (!parent) v = true;                   // 루트(그룹 base) — 항상 표시
    else if (!byCode.has(parent)) v = true;   // 부모가 grid 에 없음(방어) — 표시
    else v = gateSatisfied(parent) && isVisible(parent);
    visCache.set(code, v);
    return v;
  };
  byCode.forEach((w, code) => {
    const groupEl = w.closest("details.permission-group");
    const groupKey = groupEl ? groupEl.dataset.permGroup : null;
    const forceShow = Boolean(groupKey && showAll.has(groupKey));
    w.hidden = !(forceShow || isVisible(code));
  });
  _refreshGroupDisclosure(containerEl, showAll, () => _applyPermissionDisclosure(containerEl, mode, showAll, inherited), mode, isExplicit);
}

// 그룹 내 권한을 PERMISSION_DEPENDENCIES 트리 순서(부모 먼저, 자식 들여쓰기)로 정렬한다 (TASK-0267).
// 반환: [{ permission, depth }] — depth 0 = 그룹 내 루트(부모가 같은 그룹에 없음), depth N = 자식 단계.
// 트리(단일 열) 렌더 → 자식 숨김 시 부모는 제자리 유지, 가로 reflow(2열 grid 뒤틀림) 없음.
function _orderItemsAsTree(items) {
  const inGroup = new Set(items.map((p) => p.code));
  const childrenOf = new Map(); // parentCode -> [child permission] (카탈로그 순서)
  const roots = [];
  items.forEach((p) => {
    const parent = PERMISSION_DEPENDENCIES[p.code];
    if (parent && inGroup.has(parent)) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, []);
      childrenOf.get(parent).push(p);
    } else {
      roots.push(p); // 부모 없음 / 부모가 다른 그룹(예: account.read 의 부모 console.access) → 그룹 내 루트
    }
  });
  const out = [];
  const seen = new Set();
  const visit = (p, depth) => {
    if (seen.has(p.code)) return; // 사이클 방어(트리라 미발생)
    seen.add(p.code);
    out.push({ permission: p, depth });
    (childrenOf.get(p.code) || []).forEach((ch) => visit(ch, depth + 1));
  };
  roots.forEach((r) => visit(r, 0));
  // 안전망: 어떤 이유로 누락된 항목은 depth 0 으로 말미에 추가(렌더 누락 0 보장).
  items.forEach((p) => { if (!seen.has(p.code)) { seen.add(p.code); out.push({ permission: p, depth: 0 }); } });
  return out;
}

function renderPermissionGrid(containerEl, selectedCodes, disabled, mode, overrides, onChange, opts = {}) {
  // TASK-0053 Phase B: opts.excludeDynamic=true 면 dynamic product.access.<key> 권한들을 grid 에서 제외.
  // 그 권한들은 호출처가 별도 buildProductSubcatalog... 함수로 product 카드 형식으로 렌더한다.
  // CONVENTIONS.md §10.6 — group <details> 들은 ADMIN_PERMISSION_SECTIONS 의 2단 section (관리/운영/기타) 으로 묶어 렌더.
  // inheritedGrants(TASK-0270): override(계정) 모드에서 "상속(허용)" 게이트 판정용 — 역할이 부여한 code Set.
  // TASK-0300: allowedCodes 가 주어지면(계정/역할 권한 편집) 편집 주체(admin)가 보유한 권한 code
  //   Set 이다. 그 집합에 없는 권한 행은 grid 에서 숨긴다(privilege escalation 방지 — 본인 보유
  //   범위 밖 권한은 표시·설정 불가). null/미지정이면 필터 없음(하위호환).
  const { excludeDynamic = false, inheritedGrants = new Set(), allowedCodes = null } = opts;
  containerEl.innerHTML = "";
  const selected = new Set(selectedCodes || []);
  // 점진적 세분화: 그룹별 "세부 권한 더 보기" 강제표시 set + 재계산 클로저. 매 변경 핸들러가 호출.
  const showAll = new Set();
  const recompute = () => _applyPermissionDisclosure(containerEl, mode, showAll, inheritedGrants);
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
    // TASK-0300: 본인 미보유 권한 행 숨김. originally-empty 컨테이너(product_access: 제품 카드
    //   임베드 타겟)는 보존하고, 필터로 비워진 그룹만 제외한다.
    const renderItems = allowedCodes ? items.filter((p) => allowedCodes.has(p.code)) : items;
    if (items.length > 0 && renderItems.length === 0) return;
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
        recompute();
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
        recompute();
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
          recompute();
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

    _orderItemsAsTree(renderItems).forEach(({ permission, depth }) => {
      if (mode === "checkbox") {
        const label = document.createElement("label");
        label.className = "permission-toggle permission-toggle-card";
        label.dataset.permCode = permission.code;
        label.dataset.permDepth = String(depth);
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = permission.code;
        input.checked = selected.has(permission.code);
        input.disabled = disabled;
        input.addEventListener("change", () => {
          _updateCheckboxGroupSummary(section);
          recompute();
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
        field.dataset.permCode = permission.code;
        field.dataset.permDepth = String(depth);
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
          recompute();
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
      const hasSelected = renderItems.some((p) => selected.has(p.code));
      section.open = hasSelected;
    } else {
      _updateOverrideGroupSummary(section);
      const hasNonInherit = renderItems.some((p) => {
        const v = overrides?.[p.code] || "inherit";
        return v === "allow" || v === "deny";
      });
      section.open = hasNonInherit;
    }
  });
  // TASK-0300: 필터로 모든 그룹이 비워진 section 은 빈 헤더만 남으므로 제거.
  if (!sectionGroupsEl.children.length) sectionEl.remove();
  });
  // 초기 진입 시 disclosure 1회 적용 — 게이트 OFF 인 세부 권한은 접고, 부여된 권한 체인은 펼친다.
  recompute();
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
    datasourceDirtyProductCount() +
    adminState.pending.systemPrompts.size
  );
}

// TASK-0239: datasource 바인딩 desired ≠ baseline 인 제품 수(일괄 적용 dirty 카운트).
//  추가/제거/기본지정이 모두 desired 에 스테이징되고, baseline 과 같아지면 자동으로 dirty 아님.
function _dsBindNorm(list) {
  // 비교용 정규화: 키 소문자 + primary 플래그, 키 정렬.
  return (list || [])
    .map((d) => ({ key: String(d.datasource_key || d.key || "").trim().toLowerCase(), is_primary: !!d.is_primary }))
    .filter((d) => d.key)
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
}
function _dsBindEqual(a, b) {
  const na = _dsBindNorm(a), nb = _dsBindNorm(b);
  if (na.length !== nb.length) return false;
  for (let i = 0; i < na.length; i += 1) {
    if (na[i].key !== nb[i].key || na[i].is_primary !== nb[i].is_primary) return false;
  }
  return true;
}
function datasourceDirtyProductCount() {
  let n = 0;
  adminState.pending.productDatasources.forEach((e) => {
    if (e && !_dsBindEqual(e.baseline, e.desired)) n += 1;
  });
  return n;
}

function setProductMetaPending(productId, patch) {
  const id = Number(productId);
  if (!id) return;
  const current = adminState.pending.productMeta.get(id) || {};
  const next = { ...current, ...patch };
  adminState.pending.productMeta.set(id, next);
  refreshPendingUI();
}

function setProductDatabasesPending(productId, draft, dsKey) {
  const id = Number(productId);
  if (!id) return;
  // TASK-0228 (1:N): pending 키를 (productId, datasourceKey) 복합으로 — datasource 별 접근DB 를
  // 독립 편집/저장. dsKey 미지정(레거시 단일)은 빈 문자열로 정규화(키 `id::`).
  const dk = String(dsKey || "").trim().toLowerCase();
  const pkey = `${id}::${dk}`;
  // Keep a snapshot copy so subsequent mutations don't sneak past pending tracking.
  const snapshot = (Array.isArray(draft) ? draft : []).map((d) => ({ ...d }));
  // 스냅샷에 datasource 차원을 부착(commit 시 PUT body 에 사용).
  snapshot._dsKey = dk;
  adminState.pending.productDatabases.set(pkey, snapshot);
  refreshPendingUI();
}

// TASK-0239: datasource 바인딩 desired-state 헬퍼 — 추가/제거/기본지정을 즉시 API 대신 pending 에 스테이징.
//  baseline 은 최초 진입 시 서버 정본 1회 스냅샷. 이후 desired 만 변형. "모두 적용" 시 diff 로 최소 호출.
function _ensureDatasourcePending(productId, serverBindings) {
  const id = Number(productId);
  if (!id) return null;
  let e = adminState.pending.productDatasources.get(id);
  if (!e) {
    const snap = (serverBindings || []).map((d) => ({
      datasource_key: String(d.datasource_key || d.key || "").trim().toLowerCase(),
      is_primary: !!d.is_primary,
    })).filter((d) => d.datasource_key);
    e = { baseline: snap.map((d) => ({ ...d })), desired: snap.map((d) => ({ ...d })) };
    adminState.pending.productDatasources.set(id, e);
  }
  return e;
}
// desired 가 baseline 과 같아지면 엔트리 제거(dirty 해소). UI 갱신.
function _settleDatasourcePending(productId) {
  const id = Number(productId);
  const e = adminState.pending.productDatasources.get(id);
  if (e && _dsBindEqual(e.baseline, e.desired)) {
    adminState.pending.productDatasources.delete(id);
  }
  refreshPendingUI();
}
// 현재 표시할 바인딩(desired 가 있으면 그것, 없으면 서버 정본). accordion 렌더가 이걸 본다.
function effectiveProductDatasources(product) {
  const e = adminState.pending.productDatasources.get(Number(product.id));
  if (e) {
    return e.desired.map((d) => ({ datasource_key: d.datasource_key, is_primary: !!d.is_primary }));
  }
  return (product.datasources || []).map((d) => ({
    datasource_key: d.datasource_key, is_primary: !!d.is_primary,
  }));
}
// 추가: desired 에 키 append(이미 있으면 no-op). 첫 바인딩이면 자동 primary.
function stageAddDatasource(product, key) {
  const e = _ensureDatasourcePending(product.id, product.datasources);
  if (!e) return;
  const k = String(key || "").trim().toLowerCase();
  if (!k || e.desired.some((d) => d.datasource_key === k)) return;
  const firstBind = e.desired.length === 0;
  e.desired.push({ datasource_key: k, is_primary: firstBind });
  _settleDatasourcePending(product.id);
}
// 제거: desired 에서 키 제외. 제거 대상이 primary 였으면 남은 첫째를 primary 승격.
function stageRemoveDatasource(product, key) {
  const e = _ensureDatasourcePending(product.id, product.datasources);
  if (!e) return;
  const k = String(key || "").trim().toLowerCase();
  const wasPrimary = e.desired.some((d) => d.datasource_key === k && d.is_primary);
  e.desired = e.desired.filter((d) => d.datasource_key !== k);
  if (wasPrimary && e.desired.length && !e.desired.some((d) => d.is_primary)) {
    e.desired[0].is_primary = true;
  }
  _settleDatasourcePending(product.id);
}
// 기본 지정: 키를 primary 로, 나머지 해제.
function stageSetPrimaryDatasource(product, key) {
  const e = _ensureDatasourcePending(product.id, product.datasources);
  if (!e) return;
  const k = String(key || "").trim().toLowerCase();
  if (!e.desired.some((d) => d.datasource_key === k)) return;
  e.desired.forEach((d) => { d.is_primary = (d.datasource_key === k); });
  _settleDatasourcePending(product.id);
}

// ── TASK-0244: datasource 연결 상태 probe + 배지 ────────────────────────────
//  '+ 데이터소스 추가' 목록과 ⋯ 메뉴가 공유하는 단일 경로. 결과는 adminState.datasourceConnStatus
//  에 캐시(매 토글/재오픈마다 재probe 방지). 동일 key 진행 중 호출은 in-flight 프라미스로 dedup.
const _dsConnInflight = new Map();

// 동시 probe cap(REV-0244 nit): 서버 probe 는 도달불가 시 최대 8s(db.py connection_timeout) 점유.
//  datasource 가 많고 다수 unreachable 이면 web 스레드/연결이 동시에 묶일 수 있어, 클라이언트에서
//  동시 probe 를 4개로 제한한다(나머지는 큐 대기 — 배지는 그동안 '확인 중'). 캐시 hit 는 이 게이트 무관.
const _DS_CONN_MAX = 4;
let _dsConnActive = 0;
const _dsConnWaiters = [];
function _dsConnAcquire() {
  if (_dsConnActive < _DS_CONN_MAX) { _dsConnActive += 1; return Promise.resolve(); }
  return new Promise((resolve) => { _dsConnWaiters.push(resolve); });
}
function _dsConnRelease() {
  const next = _dsConnWaiters.shift();
  if (next) { next(); return; }   // 활성 카운트는 유지(대기자가 슬롯 인계)
  _dsConnActive = Math.max(0, _dsConnActive - 1);
}

// 주어진 <span> 에 캐시 entry 의 연결 상태를 그린다(노드 교체 없이 in-place — 비동기 probe 완료 시 같은 노드 갱신).
//  conn-tristate 3단계: ok(초록 "연결 정상") / unstable(빨강 "연결 불안정" — 느림·간헐) /
//  down(회색 "연결 끊김" — 도달 불가) + checking(확인 중). (레거시 "fail" 은 down 으로 폴백.)
function _paintDsConnBadge(el, entry) {
  if (!el) return;
  el.className = "admin-ds-conn";
  const st = entry && entry.state;
  if (!entry || st === "checking") {
    el.classList.add("is-checking");
    el.textContent = "확인 중…";
    el.title = "연결 상태 확인 중";
    return;
  }
  if (st === "ok") {
    el.classList.add("is-ok");
    el.textContent = (entry.elapsed_ms != null) ? `연결 정상 · ${entry.elapsed_ms}ms` : "연결 정상";
    el.title = "연결 정상";
    return;
  }
  if (st === "unstable") {
    el.classList.add("is-unstable");
    el.textContent = (entry.elapsed_ms != null) ? `연결 불안정 · ${entry.elapsed_ms}ms` : "연결 불안정";
    el.title = entry.error ? `연결 불안정: ${entry.error}` : "연결 불안정 (느리거나 간헐적)";
    return;
  }
  el.classList.add("is-down");
  el.textContent = "연결 끊김";
  el.title = entry.error ? `연결 끊김: ${entry.error}` : "연결 끊김 (도달 불가)";
}

// 데이터소스 목록 행 leading 의 네트워크 상태 도트(텍스트 없는 아이콘 배지) — 색상=상태,
//  title/aria-label=접근성(색맹 대비). _paintDsConnBadge 의 텍스트 라벨 변형(가변폭)과 달리
//  고정폭 도트라 행 leading 컬럼 정렬이 안정적이다.
function _paintDsConnDot(el, entry) {
  if (!el) return;
  el.className = "ds-conn-dot";
  const st = entry && entry.state;
  let label;
  if (st === "ok") {
    el.classList.add("is-ok");
    label = (entry.elapsed_ms != null) ? `연결 정상 · ${entry.elapsed_ms}ms` : "연결 정상";
  } else if (st === "unstable") {
    el.classList.add("is-unstable");
    label = (entry.elapsed_ms != null) ? `연결 불안정 · ${entry.elapsed_ms}ms` : "연결 불안정";
  } else if (st === "down" || st === "fail") {
    el.classList.add("is-down");
    label = entry.error ? `연결 끊김: ${entry.error}` : "연결 끊김";
  } else {
    el.classList.add("is-checking");
    label = "연결 상태 확인 중";
  }
  el.title = label;
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", `네트워크 상태: ${label}`);
}

// datasource 연결 테스트(/test) — 캐시 우선. force=true 면 캐시 무시 재probe. 항상 결과 객체로 resolve.
function _probeDatasourceConn(key, { force = false } = {}) {
  const k = String(key || "").trim().toLowerCase();
  if (!k) return Promise.resolve({ state: "fail", error: "키 없음" });
  const cache = adminState.datasourceConnStatus;
  if (!force) {
    const prev = cache.get(k);
    // 확정된 상태(ok/unstable/down — checking 아닌 것)면 재사용.
    if (prev && prev.state && prev.state !== "checking") return Promise.resolve(prev);
  }
  // TASK-0253 (REV MINOR-2): in-flight dedup 은 force 와 무관하게 적용한다. force 는 "캐시 무시
  //  재probe" 의미이지 "이미 도는 probe 를 무시하고 또 띄워라"가 아니다. 이전엔 force 경로가 이
  //  가드를 건너뛰어, ↻ 연타나 force 렌더 중첩 시 같은 key 가 2벌 이상 probe 돼 4-cap 세마포어를
  //  중복 점유했다(이번에 고친 중복의 변형). 진행 중이면 그 Promise 에 합류한다.
  if (_dsConnInflight.has(k)) return _dsConnInflight.get(k);
  cache.set(k, { state: "checking" });
  const p = (async () => {
    await _dsConnAcquire();   // 동시 probe 4개 cap — 슬롯 확보까지 '확인 중' 유지.
    try {
      const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(k)}/test`, { method: "POST" });
      // conn-tristate: 백엔드가 3단계 status(healthy/unstable/down)를 분류해 반환. 구버전(status
      //  필드 부재)은 ok→healthy / !ok→down 폴백. status→배지 state 매핑.
      const _st = (r && r.status) || (r && r.ok ? "healthy" : "down");
      const _stateMap = { healthy: "ok", unstable: "unstable", down: "down" };
      const res = {
        state: _stateMap[_st] || (r && r.ok ? "ok" : "down"),
        elapsed_ms: (r && r.elapsed_ms != null) ? r.elapsed_ms : undefined,
        error: (r && r.error) || undefined,
      };
      cache.set(k, res);
      return res;
    } catch (e) {
      const res = { state: "down", error: (e && e.message) || "테스트 실패" };
      cache.set(k, res);
      return res;
    } finally {
      _dsConnRelease();
      _dsConnInflight.delete(k);
    }
  })();
  _dsConnInflight.set(k, p);
  return p;
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

  // ── TASK-0263: 사용량 차트 클릭 → 집계 기여 대화목록 모달 ──────────────────
  // bindUsageDrill: 차트 컨테이너에 위임 클릭 — data-usage-model/data-usage-day 후크를 가진
  // 요소 클릭 시 그 차원(현 days/gran context)으로 admin 대화 모달을 연다.
  const bindUsageDrill = (root) => {
    if (!root || root._drillBound) return;
    root._drillBound = true;
    root.addEventListener("click", (e) => {
      const el2 = e.target.closest ? e.target.closest("[data-usage-model],[data-usage-day]") : null;
      if (!el2) return;
      const model = el2.getAttribute("data-usage-model") || null;
      const day = el2.getAttribute("data-usage-day") || null;
      const parts = [];
      if (model) parts.push(model);
      if (day) parts.push(day);
      openUsageConversations({ scope: "admin", model, day, title: parts.join(" · ") || "사용량" });
    });
  };

  // openUsageConversations: 차원 필터로 대화목록 엔드포인트 호출 → 모달 렌더.
  //   scope=admin → /api/admin/usage/conversations, scope=self → /api/profile/usage/conversations.
  const openUsageConversations = async (opts) => {
    const o = opts || {};
    const scope = o.scope === "self" ? "self" : "admin";
    const base = scope === "self" ? "/api/profile/usage/conversations" : "/api/admin/usage/conversations";
    const params = new URLSearchParams();
    params.set("days", String(days));
    params.set("gran", String(gran));
    if (o.model) params.set("model", o.model);
    if (o.day) params.set("day", o.day);
    if (o.account_id != null) params.set("account_id", String(o.account_id));
    if (o.role) params.set("role", o.role);
    showUsageConvModal({ loading: true, title: o.title || "대화 목록" });
    try {
      const data = await apiFetch(`${base}?${params.toString()}`);
      showUsageConvModal({ data, title: o.title || "대화 목록", scope });
    } catch (err) {
      showUsageConvModal({ error: (err && err.message) || "대화목록 조회 실패", title: o.title || "대화 목록" });
    }
  };
  // 기간별 토큰 사용량 — 모델별 누적(stacked) 세로 막대 + 막대 총합 라벨 + hover 툴팁.
  const renderStacked = (el, byDayModel) => {
    if (!el) return;
    const rows = byDayModel || [];
    if (!rows.length) { el.innerHTML = "<p style='color:var(--text-muted);'>데이터 없음</p>"; return; }
    const dayMap = {}; const costMap = {}; const models = [];  // TASK-0263: costMap = day→model→cost
    rows.forEach((r) => {
      dayMap[r.day] = dayMap[r.day] || {};
      dayMap[r.day][r.model] = (dayMap[r.day][r.model] || 0) + (r.total_tokens || 0);
      costMap[r.day] = costMap[r.day] || {};
      costMap[r.day][r.model] = (costMap[r.day][r.model] || 0) + (r.cost_usd || 0);
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
        // TASK-0263: hover 에 모델별 비용 + 클릭 시 그 일자·모델 기여 대화 모달(data-usage-* 후크).
        const cst = costMap[d][m] || 0;
        const costTip = cst > 0 ? `<br>추정 ${usd(cst)}` : "";
        bars += `<rect class='admin-usage-clickable' x='${x.toFixed(1)}' y='${y.toFixed(1)}' width='${bw.toFixed(1)}' height='${h.toFixed(1)}' fill='${mcol(m)}' rx='1' data-tip='${esc(d)} · ${esc(m)}<br><b>${num(v)}</b> 토큰 (${pct}%)${costTip}<br><span style="opacity:.8">클릭: 대화 보기</span>' data-usage-day='${esc(d)}' data-usage-model='${esc(m)}'/>`;
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
    bindUsageDrill(el);  // TASK-0263: 막대 클릭 → 그 일자·모델 기여 대화 모달.
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
      // TASK-0263: 도넛 세그먼트 클릭 → 그 모델 기여 대화 모달(data-usage-model). 라벨=COALESCE(resolved,model)=백엔드 필터 키.
      segs += `<circle class='admin-usage-clickable' cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${mcol(r.label)}' stroke-width='22' stroke-dasharray='${len.toFixed(2)} ${(C - len).toFixed(2)}' stroke-dashoffset='${(-off).toFixed(2)}' transform='rotate(-90 ${cx} ${cy})' data-tip='${esc(r.label)}<br><b>${num(r.value)}</b> 토큰 (${(r.value / total * 100).toFixed(1)}%)<br>${num(r.calls)} 호출${costTip}<br><span style="opacity:.8">클릭: 대화 보기</span>' data-usage-model='${esc(r.label)}'/>`;
      off += len;
    });
    const legend = rows.map((r) => `<div class='admin-usage-clickable' data-usage-model='${esc(r.label)}' style='display:flex;align-items:center;gap:6px;font-size:12px;margin:3px 0;'><span style='width:11px;height:11px;border-radius:2px;background:${mcol(r.label)};display:inline-block;flex:none;'></span><span style='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>${esc(r.label)}</span><strong>${(r.value / total * 100).toFixed(1)}%</strong></div>`).join("");
    el.innerHTML = `<div style='display:flex;align-items:center;gap:18px;flex-wrap:wrap;'><svg viewBox='0 0 140 140' style='width:130px;height:130px;flex:none;'>${segs}<text x='70' y='66' text-anchor='middle' font-size='11' fill='var(--text-muted)'>총 토큰</text><text x='70' y='83' text-anchor='middle' font-size='13' font-weight='700' fill='var(--text)'>${num(total)}</text></svg><div style='flex:1;min-width:150px;'>${legend}</div></div>`;
    bindTip(el);
    bindUsageDrill(el);  // TASK-0263
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
      const segs = (r.models || []).filter((m) => (m[valueKey] || 0) > 0).map((m) => {
        // TASK-0263: 토큰 차트 hover 에도 모델별 추정 비용 병기(valueKey 가 cost_usd 면 이미 비용이라 중복 생략).
        const extraCost = (valueKey !== "cost_usd" && (m.cost_usd || 0) > 0) ? `<br>추정 ${usd(m.cost_usd)}` : "";
        return `<div data-tip='${esc(r.label)} · ${esc(m.model)}<br><b>${fmt(m[valueKey])}</b>${extraCost}' style='width:${(m[valueKey] / max * 100).toFixed(2)}%;background:${mcol(m.model)};height:100%;'></div>`;
      }).join("");
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
      _account_id: a.account_id,  // TASK-0263: 클릭 시 대화 모달 필터용(라벨에서 파싱하지 않고 직접 보존)
    }));
    if (hintEl) hintEl.textContent = `· ${st.drillRole} — ${filtered.length}개 계정${q ? " (검색됨)" : ""} · 계정 클릭 시 대화 보기`;
    if (toolsEl) toolsEl.classList.remove("hidden");
    // TASK-0263: 계정 막대 클릭 → 그 계정의 기여 대화 모달(현재 모델 필터 context 동반).
    const onAcctClick = (label) => {
      const row = pageRows.find((r) => r.label === label);
      if (!row || row._account_id == null) return;
      openUsageConversations({ scope: "admin", account_id: row._account_id, title: label });
    };
    if (pageRows.length) {
      renderStackedHBar(chartEl, pageRows, "total_tokens", num, onAcctClick);
      renderStackedHBar(costChartEl, pageRows, "cost_usd", usd, onAcctClick);  // TASK-0184: 계정별 비용 차트(역할별과 일관)
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

// TASK-0263: 사용량 차트 클릭 → 집계 기여 대화목록 모달. admin/profile 공용 렌더(scope 로 분기).
//   각 대화 행은 메인 UI deep-link(/?conversation=<id>)로 이동(새 탭). 대화 제목/일시/소유자/
//   기간내 usage(호출·토큰·추정비용)만 표시 — 메시지 본문 미포함.
function showUsageConvModal(state) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (v) => (Number(v) || 0).toLocaleString();
  const usd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtDt = (s) => {
    if (!s) return "—";
    try { const d = new Date(s); return isNaN(d.getTime()) ? esc(s) : d.toLocaleString(); } catch (_) { return esc(s); }
  };
  // 기존 모달 제거(중복 방지).
  const prev = document.getElementById("usageConvModalOverlay");
  if (prev) prev.remove();
  const overlay = document.createElement("div");
  overlay.id = "usageConvModalOverlay";
  overlay.className = "admin-modal-overlay";
  const title = esc(state.title || "대화 목록");
  let bodyHtml;
  if (state.loading) {
    bodyHtml = "<p class='admin-modal-note'>대화목록을 불러오는 중…</p>";
  } else if (state.error) {
    bodyHtml = `<p class='admin-modal-note usage-conv-error'>${esc(state.error)}</p>`;
  } else {
    const items = (state.data && state.data.items) || [];
    const truncated = !!(state.data && state.data.truncated);
    const isAdmin = (state.scope === "admin");
    if (!items.length) {
      bodyHtml = "<p class='admin-modal-note'>이 집계에 해당하는 대화가 없습니다. (insight·시스템 호출은 대화에 귀속되지 않습니다.)</p>";
    } else {
      const rows = items.map((it) => {
        const cid = esc(it.conversation_id);
        const topic = esc(it.topic || "(제목 없음)");
        const owner = isAdmin
          ? `<td class='usage-conv-owner'>${esc(it.owner_username || ("#" + (it.owner_account_id == null ? "?" : it.owner_account_id)))}${it.owner_role ? " · " + esc(it.owner_role) : ""}</td>`
          : "";
        const blocked = it.blocked ? " <span class='usage-conv-badge'>차단</span>" : "";
        return `<tr>`
          + `<td class='usage-conv-topic'><a href='/?conversation=${encodeURIComponent(it.conversation_id)}' target='_blank' rel='noopener' title='${topic}'>${topic}</a>${blocked}</td>`
          + owner
          + `<td class='num'>${num(it.calls)}</td>`
          + `<td class='num'>${num(it.total_tokens)}</td>`
          + `<td class='num'>${it.cost_usd > 0 ? usd(it.cost_usd) : "—"}</td>`
          + `<td class='usage-conv-when'>${fmtDt(it.last_used_at || it.updated_at)}</td>`
          + `</tr>`;
      }).join("");
      const ownerHead = isAdmin ? "<th>소유자</th>" : "";
      bodyHtml = `<div class='usage-conv-tablewrap'><table class='admin-usage-table usage-conv-table'>`
        + `<thead><tr><th>대화</th>${ownerHead}<th class='num'>호출</th><th class='num'>토큰</th><th class='num'>추정 비용</th><th>최근 사용</th></tr></thead>`
        + `<tbody>${rows}</tbody></table></div>`
        + (truncated ? `<p class='admin-modal-note usage-conv-trunc'>상위 ${num(items.length)}건만 표시합니다(기간내 토큰 큰 순). 기간을 좁혀 보세요.</p>` : "")
        + `<p class='admin-modal-note usage-conv-hint'>대화 제목을 클릭하면 새 탭에서 해당 대화로 이동합니다.</p>`;
    }
  }
  overlay.innerHTML =
    '<div class="admin-modal usage-conv-modal" role="dialog" aria-modal="true" aria-label="' + title + ' 대화 목록">'
    + '  <div class="admin-modal-head"><h3>' + title + ' · 대화 목록</h3>'
    + '    <button type="button" class="admin-modal-close" id="usageConvModalClose" aria-label="닫기">×</button></div>'
    + '  <div class="usage-conv-body">' + bodyHtml + '</div>'
    + '</div>';
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
  const closeBtn = document.getElementById("usageConvModalClose");
  if (closeBtn) closeBtn.addEventListener("click", close);
  const onEsc = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", onEsc); } };
  document.addEventListener("keydown", onEsc);
}

// TASK-0288: 관리 콘솔 탭 → 필요 권한 매핑. 값은 "하나라도 보유하면 표시"(OR) 권한 배열.
// 매핑 없는 탭(dashboard)은 항상 표시(console.access 보유 = 콘솔 진입 가능자 — overview 는 위젯별
// RBAC 스코프). 백엔드 엔드포인트 권한과 1:1 정합 — 탭은 보이는데 데이터는 403 인 괴리를 차단한다.
const ADMIN_TAB_PERMISSIONS = {
  accounts: ["account.read"],
  roles: ["role.read"],
  products: ["product.read", "product.manage"],
  datasources: ["datasource.read", "datasource.manage"],
  audits: ["audit.read.own", "audit.read.any"],
  usage: ["console.usage.read"],
  archives: ["conversation.archive.read.any"],
  settings: ["system_prompt.global.read", "system_prompt.global.write"],
};

function canSeeTab(tabKey) {
  const perms = ADMIN_TAB_PERMISSIONS[tabKey];
  if (!perms || !perms.length) return true; // 매핑 없음(dashboard) = 항상 표시.
  return perms.some((p) => can(p));
}

// 관리 콘솔 좌측 탭 nav 의 가시성을 권한 기준으로 일괄 적용.
// (1) 각 탭 버튼 표시/숨김 — 기존 게이팅과 동일하게 inline style.display 사용([hidden] CSS override
//     함정 회피, TASK-0257 선례). (2) 그룹 라벨/구분선 — 그룹 내 표시 탭이 0이면 라벨+직전 구분선 숨김.
// (3) 활성 탭이 숨겨졌으면 첫 표시 탭으로 전환(빈 본문 방지).
function applyAdminTabVisibility() {
  const nav = $("adminTabs");
  if (!nav) return;
  nav.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.style.display = canSeeTab(btn.dataset.adminTab) ? "" : "none";
  });
  // 그룹 경계 = .admin-tab-group-label (직전 .admin-tab-group-divider 동반 가능).
  let pendingDivider = null;
  let currentLabel = null;
  let leadingDivider = null;
  let groupVisibleTabs = 0;
  const finalize = () => {
    if (!currentLabel) return;
    const show = groupVisibleTabs > 0;
    currentLabel.style.display = show ? "" : "none";
    if (leadingDivider) leadingDivider.style.display = show ? "" : "none";
  };
  Array.from(nav.children).forEach((el) => {
    if (el.classList.contains("admin-tab-group-divider")) {
      pendingDivider = el;
    } else if (el.classList.contains("admin-tab-group-label")) {
      finalize();
      currentLabel = el;
      leadingDivider = pendingDivider;
      pendingDivider = null;
      groupVisibleTabs = 0;
    } else if (el.classList.contains("admin-tab")) {
      // currentLabel === null 이면 그룹 라벨 없는 선행 탭(dashboard) — 그룹 집계 제외.
      if (currentLabel && el.style.display !== "none") groupVisibleTabs += 1;
    }
  });
  finalize();
  // 활성 탭이 숨겨졌으면 첫 표시 탭으로 전환.
  const active = nav.querySelector(".admin-tab.is-active");
  if (active && active.style.display === "none") {
    const firstVisible = Array.from(nav.querySelectorAll(".admin-tab"))
      .find((b) => b.style.display !== "none");
    if (firstVisible) switchTab(firstVisible.dataset.adminTab);
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
  // TASK-0273: 보관 대화 tab 첫 진입 시 로드.
  if (tabName === "archives" && !adminState.archivesInitialized) {
    adminState.archivesInitialized = true;
    loadArchivedConversations();
  }
  // 릴리즈 노트 — 정적 콘텐츠라 진입 시 렌더(가벼움). 렌더러는 release-notes.js, 작업 화면과 공유.
  if (tabName === "release-notes" && window.ReleaseNotes) {
    window.ReleaseNotes.render(document.getElementById("adminReleaseNotesBody"));
  }
}

// TASK-0273: 보관 대화 목록 로드 + 렌더(conversation.archive.read.any).
// TASK-0276: 보관 대화 상태 — audits 동형(items/selectedId/q/truncated). list-detail 2단 렌더.
adminState.archives = { items: [], selectedId: null, q: "", truncated: false, loading: false };

function _archiveEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function _archiveFmtDt(s) {
  if (!s) return "—";
  try { const d = new Date(s); return isNaN(d.getTime()) ? _archiveEsc(s) : d.toLocaleString(); } catch (_) { return _archiveEsc(s); }
}
function _archiveOwnerLabel(it) {
  return it.owner_username || (it.owner_account_id == null ? "(시스템)" : "#" + it.owner_account_id);
}
function _archiveByLabel(it) {
  return it.archived_by_username || (it.archived_by_account_id == null ? "—" : "#" + it.archived_by_account_id);
}

async function loadArchivedConversations() {
  const listEl = document.getElementById("archiveList");
  if (!listEl) return;
  const q = (document.getElementById("archiveSearch") || {}).value || "";
  adminState.archives.q = q.trim();
  adminState.archives.loading = true;
  listEl.innerHTML = '<div class="admin-list-empty">로딩 중…</div>';
  try {
    const data = await apiFetch(`/api/admin/conversations/archived?q=${encodeURIComponent(adminState.archives.q)}`);
    adminState.archives.items = (data && data.items) || [];
    adminState.archives.truncated = Boolean(data && data.truncated);
    // 선택 유지: 현재 선택이 새 목록에 없으면 해제.
    if (adminState.archives.selectedId
        && !adminState.archives.items.some((it) => String(it.conversation_id) === String(adminState.archives.selectedId))) {
      adminState.archives.selectedId = null;
    }
  } catch (err) {
    adminState.archives.items = [];
    adminState.archives.truncated = false;
    listEl.innerHTML = `<div class="admin-list-empty">${_archiveEsc((err && err.message) || "보관 대화 조회 실패")}</div>`;
    const countEl = document.getElementById("archiveListCount");
    if (countEl) countEl.textContent = "";
    return;
  } finally {
    adminState.archives.loading = false;
  }
  renderArchiveList();
  renderArchiveDetail(adminState.archives.selectedId);
}

function renderArchiveList() {
  const listEl = document.getElementById("archiveList");
  const countEl = document.getElementById("archiveListCount");
  const scopeEl = document.getElementById("archiveListScope");
  if (!listEl) return;
  const items = adminState.archives.items;
  if (countEl) countEl.textContent = `${items.length}건`;
  if (scopeEl) scopeEl.textContent = adminState.archives.truncated ? "(상위 일부 — 검색으로 좁혀 보세요)" : (adminState.archives.q ? `(검색: ${_archiveEsc(adminState.archives.q)})` : "");

  if (!items.length) {
    listEl.innerHTML = '<div class="admin-list-empty">보관된 대화가 없습니다.</div>';
    return;
  }
  const rows = items.map((it) => {
    const isSel = String(it.conversation_id) === String(adminState.archives.selectedId);
    const klass = "admin-list-row admin-archive-row" + (isSel ? " is-selected" : "");
    return `
      <div class="${klass}" role="row" data-archive-id="${_archiveEsc(it.conversation_id)}">
        <div class="admin-archive-row-line">
          <span class="admin-archive-row-topic">${_archiveEsc(it.topic || "(제목 없음)")}</span>
          <span class="admin-archive-row-ts">${_archiveEsc(_archiveFmtDt(it.archived_at))}</span>
        </div>
        <div class="admin-archive-row-line muted">
          <span class="admin-archive-row-owner">소유자 ${_archiveEsc(_archiveOwnerLabel(it))}</span>
          <span class="admin-archive-row-by">보관 ${_archiveEsc(_archiveByLabel(it))}</span>
        </div>
      </div>`;
  }).join("");
  listEl.innerHTML = rows;
  listEl.querySelectorAll(".admin-archive-row").forEach((rowEl) => {
    rowEl.addEventListener("click", () => {
      adminState.archives.selectedId = rowEl.dataset.archiveId;
      renderArchiveList();
      renderArchiveDetail(adminState.archives.selectedId);
    });
  });
}

function renderArchiveDetail(id) {
  const el = document.getElementById("archiveDetail");
  if (!el) return;
  const item = adminState.archives.items.find((it) => String(it.conversation_id) === String(id));
  if (!item) {
    // TASK-0277: header↔filter 사이 안내(admin-pane-note) 제거 대신, 빈 상태에 안내를 둬 정보 보존 + 밀도 정합.
    el.innerHTML = '<div class="admin-detail-empty">보관된 대화를 선택하세요.'
      + '<p class="admin-archive-detail-note">사용자가 "삭제"한 대화는 hard-delete 되지 않고 보관됩니다. 데이터·첨부는 보존되어 오용 방지 감사·맥락 참조에 사용됩니다. 소유 계정 목록에서는 숨겨지고 새 메시지 진행이 차단됩니다.</p>'
      + '</div>';
    return;
  }
  el.innerHTML = `
    <div class="admin-archive-detail">
      <h3>${_archiveEsc(item.topic || "(제목 없음)")}</h3>
      <dl class="admin-archive-detail-fields">
        <dt>대화 ID</dt><dd><code>${_archiveEsc(item.conversation_id)}</code></dd>
        <dt>소유자</dt><dd>${_archiveEsc(_archiveOwnerLabel(item))}</dd>
        <dt>보관 시각</dt><dd>${_archiveEsc(_archiveFmtDt(item.archived_at))}</dd>
        <dt>보관 수행자</dt><dd>${_archiveEsc(_archiveByLabel(item))}</dd>
        ${item.created_at ? `<dt>생성 시각</dt><dd>${_archiveEsc(_archiveFmtDt(item.created_at))}</dd>` : ""}
        ${item.message_count != null ? `<dt>메시지 수</dt><dd>${_archiveEsc(item.message_count)}</dd>` : ""}
      </dl>
      <p class="admin-archive-detail-note">보관된 대화는 소유 계정 목록에서 숨겨지고 새 메시지 진행이 차단됩니다. 데이터·첨부는 보존되어 오용 방지 감사·맥락 참조(fork)에 사용됩니다. 본문은 본 화면에서 표시하지 않습니다(메타데이터 전용).</p>
    </div>`;
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
  // TASK-0288: datasource mutation UI 는 datasource.manage 게이트(백엔드 _ds_write_common 정합).
  // datasource.read 만 보유한 뷰어는 목록은 보되 생성/수정/삭제 버튼은 숨겨진다.
  const canManage = can("datasource.manage");
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

// TASK-0278 — 검색 필터를 적용한 visible datasource 목록(select-all / bulk / shift-range 공용).
function _dsFiltered() {
  const dsList = adminState.datasources || [];
  const q = (adminState._dsSearch || "").trim().toLowerCase();
  return q
    ? dsList.filter((ds) => (ds.key || "").toLowerCase().includes(q) || (ds.host || "").toLowerCase().includes(q))
    : dsList.slice();
}

function _dsRenderList() {
  const listEl = $("datasourceList");
  const countEl = $("datasourceListCount");
  if (!listEl) return;
  const dsList = adminState.datasources || [];
  const q = (adminState._dsSearch || "").trim().toLowerCase();
  const filtered = _dsFiltered();
  if (countEl) countEl.textContent = q ? `${filtered.length}/${dsList.length}` : `${dsList.length}`;

  // 데이터 reload / 삭제로 사라진 key 는 선택에서 prune (renderProductList 의 stale 제거와 동형).
  const liveKeys = new Set(dsList.map((d) => d.key));
  Array.from(adminState.datasourceSelected).forEach((k) => { if (!liveKeys.has(k)) adminState.datasourceSelected.delete(k); });

  listEl.innerHTML = "";
  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = dsList.length ? "검색 결과 없음" : "등록된 데이터소스가 없습니다.";
    listEl.appendChild(empty);
    updateDatasourceSelectAllCheckbox();
    renderDatasourceBulkBar();
    renderDatasourceCrossPageBanner();
    return;
  }
  // DESIGN.md §9 — shift-click range 를 위한 visible key 시퀀스.
  const visibleDsKeys = filtered.map((ds) => ds.key);
  filtered.forEach((ds, visibleIdx) => {
    // 계정/역할/제품 목록과 동일하게 <div role=row> + 행 체크박스(다중 선택). 단일 상세 선택은 _dsSelectedKey 유지.
    const row = document.createElement("div");
    row.className = "admin-list-row";
    row.dataset.dsKey = ds.key;
    row.dataset.idx = String(visibleIdx);
    row.setAttribute("role", "row");
    const isSel = ds.key === adminState._dsSelectedKey;
    if (isSel) row.classList.add("is-active");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-list-row-cb";
    cb.checked = adminState.datasourceSelected.has(ds.key);
    cb.setAttribute("aria-label", `데이터소스 ${ds.key} 선택`);
    cb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (ev.shiftKey && adminState.datasourceLastClickIdx >= 0) {
        const addMode = !cb.checked;
        applyShiftRangeSelect({
          selected: adminState.datasourceSelected,
          visibleIds: visibleDsKeys,
          fromIdx: adminState.datasourceLastClickIdx,
          toIdx: visibleIdx,
          addMode,
        });
      }
    });
    cb.addEventListener("change", () => {
      if (cb.checked) adminState.datasourceSelected.add(ds.key);
      else adminState.datasourceSelected.delete(ds.key);
      adminState.datasourceLastClickIdx = visibleIdx;
      _dsRenderList();
    });

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
    // 행 leading: 체크박스(다중선택) + 네트워크 상태 도트(#251 통합). loadAdminData 가 백엔드
    //  사전계산 conn_status 를 캐시에 넣어두므로 대부분 probe 없이 즉시 표시; unknown(캐시 miss)만
    //  기존 4-cap lazy probe 재사용(in-flight dedup). 재렌더로 노드가 떨어지면(isConnected=false) skip.
    const dsk = String(ds.key || "").trim().toLowerCase();
    const dot = document.createElement("span");
    _paintDsConnDot(dot, adminState.datasourceConnStatus.get(dsk));
    // TASK-20260618T030534: 연결 상태 도트 우측에 엔진 서비스 브랜드 아이콘(목록 식별 보조).
    //  '새 데이터소스' 드롭다운(_dsBuildEngineField)과 동일한 engineMeta(아이콘 + 브랜드색)를
    //  재사용한다. 행 grid 는 [체크박스 · 도트 · 엔진아이콘 · main] 4열(styles.css 동반 갱신).
    const em = engineMeta(ds.engine);
    const engIcon = document.createElement("span");
    engIcon.className = "ds-list-engine-icon";
    engIcon.style.color = em.color;
    engIcon.innerHTML = em.icon;
    engIcon.title = `엔진: ${em.label}`;
    engIcon.setAttribute("role", "img");
    engIcon.setAttribute("aria-label", `엔진: ${em.label}`);
    row.append(cb, dot, engIcon, main);
    _probeDatasourceConn(dsk).then((res) => { if (dot.isConnected) _paintDsConnDot(dot, res); });
    row.addEventListener("click", () => {
      adminState._dsSelectedKey = ds.key;
      _dsRenderList();
      _dsRenderDetail(ds);
    });
    listEl.appendChild(row);
  });
  updateDatasourceSelectAllCheckbox();
  renderDatasourceBulkBar();
  renderDatasourceCrossPageBanner();
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

/* ── TASK-0278: 데이터소스 목록 다중 선택 (계정/역할/제품과 동일 bulk 계약) ─────────
 * CONVENTIONS.md §10 + DESIGN.md §4~§12. 단일 상세 선택(_dsSelectedKey)과 동거.
 * 핵심 차이: 제품 bulk 는 pending-commit, 데이터소스는 즉시 CRUD(삭제·insight PATCH)이므로
 * 동기 runBulkActionWithPartialFail 대신 async runner(_runDatasourceBulkAsync)로 처리한다. */

// 일괄 작업 대상 가능 여부 — 편집 가능(비-env) datasource 만. console.manage 게이트는 bulk bar 노출에서 적용.
function _dsBulkTargetable(key) {
  const ds = (adminState.datasources || []).find((d) => d.key === key);
  return Boolean(ds && ds.editable);
}

// DESIGN.md §11 — Datasources select-all (indeterminate 반영, 현재 필터 기준)
function updateDatasourceSelectAllCheckbox() {
  const all = _dsFiltered();
  const selAll = $("datasourceSelectAll");
  if (!selAll) return;
  if (!all.length) { selAll.checked = false; selAll.indeterminate = false; return; }
  const selected = all.filter((d) => adminState.datasourceSelected.has(d.key)).length;
  if (selected === 0) { selAll.checked = false; selAll.indeterminate = false; }
  else if (selected === all.length) { selAll.checked = true; selAll.indeterminate = false; }
  else { selAll.checked = false; selAll.indeterminate = true; }
}

// DESIGN.md §5 — Datasources bulk toolbar (즉시 적용)
function renderDatasourceBulkBar() {
  const bar = $("datasourcesBulkBar");
  if (!bar) return;
  bar.innerHTML = "";
  const count = adminState.datasourceSelected.size;
  if (!count) return;

  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("datasources")} 선택됨`;
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

  // TASK-0288: datasource.manage 로 모든 datasource bulk mutation 을 통제(상세 패널 액션과 동일 게이트).
  if (can("datasource.manage")) {
    bar.appendChild(makeBtn("인사이트 탐색 켜기", () => bulkDatasourceSetInsight(true)));
    bar.appendChild(makeBtn("인사이트 탐색 끄기", () => bulkDatasourceSetInsight(false)));
    bar.appendChild(makeBtn("삭제", () => bulkDatasourceDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.datasourceSelected.clear();
    adminState.datasourceLastClickIdx = -1;
    _dsRenderList();
  }, false, "Esc"));
}

// DESIGN.md §6 — Datasources cross-page banner (현재 페이징 없음, 향후 대비 placeholder)
function renderDatasourceCrossPageBanner() {
  const items = _dsFiltered();
  renderCrossPageBanner({
    entity: "datasources",
    selected: adminState.datasourceSelected,
    visibleIds: items.map((d) => d.key),
    totalCount: (adminState.datasources || []).length,
    onClearAll: () => { adminState.datasourceSelected.clear(); _dsRenderList(); },
    onShowCurrentOnly: () => { /* no-op — 페이징 없음 */ },
  });
}

// DESIGN.md §8 — RBAC/상태 partial-failure 처리(async 변형). keys 를 [applied, excluded, failed] 로 분할.
//   excluded = 대상 불가(비-env editable 아님), failed = API throw(예: 바인딩 409). 양쪽 모두 "제외" 로 합산.
async function _runDatasourceBulkAsync({ action, keys, applyKey }) {
  const applied = [];
  const excluded = [];
  const failed = [];
  for (const key of Array.from(keys)) {
    if (!_dsBulkTargetable(key)) { excluded.push(key); continue; }
    try { await applyKey(key); applied.push(key); }
    catch (_err) { failed.push(key); }
  }
  const unit = entityUnit("datasources");
  const verb = actionLabel(action);
  const skipped = excluded.length + failed.length;
  const baseMsg = `${applied.length}${unit} ${verb} 완료`;
  if (skipped === 0) showToast(baseMsg);
  else showToast(`${baseMsg} (${skipped}${unit} 제외)`, false);
  // 즉시 적용 후 서버 상태 재동기화 + 재렌더(삭제된 key 는 _dsRenderList 가 prune).
  await loadAdminData();
  renderDatasourcesPane();
  return { applied, excluded, failed };
}

// 일괄 인사이트 탐색 on/off — 편집 가능 datasource 만 대상(env 제외). 즉시 PATCH.
function bulkDatasourceSetInsight(enabled) {
  const action = enabled ? "insight_on" : "insight_off";
  const count = adminState.datasourceSelected.size;
  if (!confirmBulkAction({ entity: "datasources", action, count, danger: false })) return;
  _runDatasourceBulkAsync({
    action,
    keys: adminState.datasourceSelected,
    applyKey: (key) => apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}`,
      { method: "PATCH", body: JSON.stringify({ insight_enabled: enabled }) }),
  });
}

// 일괄 삭제 — 편집 가능 datasource 만. 제품 바인딩(409) 은 강제삭제하지 않고 "제외" 처리(개별 삭제에서 force 가능).
function bulkDatasourceDelete() {
  const count = adminState.datasourceSelected.size;
  if (!confirmBulkAction({ entity: "datasources", action: "delete", count, danger: true })) return;
  _runDatasourceBulkAsync({
    action: "delete",
    keys: adminState.datasourceSelected,
    applyKey: (key) => apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}`, { method: "DELETE" }),
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

// TASK-0255 R2: insight-worker 가 PG 에 영속한 datasource 스캔 health 를 사람-친화 한글 라벨로.
//   "연결 불안정"(circuit_open/unstable) ↔ "권한 필요"(perm_failed) 를 명시 구분 — 운영자 진단.
function _dsInsightHealthLabel(ih) {
  if (!ih) return "— (insight 미기록)";
  const o = ih.scan_outcome;
  const st = ih.status;
  if (o === "circuit_open" || st === "unstable") return "⚠ 연결 불안정 (미커버 — 자동 재시도 대기)";
  if (o === "perm_failed") return "⚠ 권한 필요 (연결됨, RO GRANT 누락)";
  if (o === "other_failed") return "⚠ 스캔 실패 (기타 오류)";
  if (o === "skipped_no_db") return "등록 DB 없음 (스캔 대상 없음)";
  if (o === "ok") return "정상 (분석됨)";
  return st ? `연결 ${st}` : "—";
}

function _dsRenderDetail(ds) {
  const detailEl = $("datasourceDetail");
  if (!detailEl || !ds) return;
  // TASK-0288: 상세 패널의 수정/삭제 액션도 datasource.manage 게이트.
  const canManage = can("datasource.manage");
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
  // TASK-0255 R2: insight-worker 가 PG 에 영속한 마지막 스캔 health — 미커버 사유를 "연결 불안정" vs "권한 실패"
  // 로 구분 표시(운영자 진단). insight 미기록(신규 datasource·PG 미가용)이면 "—".
  if (ds.insight_enabled !== false) {
    const _ih = adminState.datasourceInsightHealth.get(String(ds.key || "").trim().toLowerCase());
    _dsKvRow(dl2, "인사이트 스캔 상태", _dsInsightHealthLabel(_ih));
  }
  sec2.appendChild(dl2);
  detailEl.appendChild(sec2);

  // 상태 안내 (멀티 datasource flag / 암호화키)
  const note = document.createElement("div");
  note.className = "admin-detail-hint";
  if (!adminState.datasourcesEnabled) {
    note.textContent = "멀티 datasource 비활성(AGENT_MULTI_DATASOURCE_ENABLED=0). 등록은 가능하나 flag 활성화 전까지 동작하지 않습니다.";
  } else if (!adminState.datasourcesEncryptionReady) {
    note.textContent = "⚠ 암호화 키(AGENT_DATASOURCE_KEK_V1) 미설정 — 생성/수정이 차단됩니다. 운영자가 KEK 를 설정하세요.";
  } else if (!adminState.datasourcesSsrfPrivateGuard) {
    // TASK-0219: 사설망 경계 비활성(사내 사설망 운영). 메타데이터 IP 는 여전히 차단.
    note.textContent = "사설망 IP 허용(SSRF 사설 경계 비활성, 사내망 운영). 클라우드 메타데이터 IP 는 여전히 차단됩니다.";
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

/* ── 데이터소스 엔진 카탈로그 (TASK-20260618T022006) ──────────────────────────
 * '새 데이터소스' 폼의 엔진 입력을 자유 텍스트 → 아이콘 드롭다운으로 전환한다.
 * 백엔드 화이트리스트(app.py POST/PATCH /api/admin/datasources: engine in mysql|mssql)
 * 와 1:1 로 맞춘다 — 엔진 추가 시 여기 + 백엔드를 함께 갱신해야 한다.
 *
 * 아이콘은 공식 서비스 브랜드 마크를 inline SVG 로 baking 한다(외부 CDN 핫링크 금지 —
 * dashboard sparkline·프로필 identicon 과 동일한 "외부 의존 0" baked 정책). 출처:
 *   MySQL  = simple-icons 'mysql'(돌고래 마크) · 브랜드 teal #00758F
 *   MSSQL  = devicon 'microsoftsqlserver'(공식 SQL Server 마크) · 브랜드 red #EE352C
 * 둘 다 단색 path 라 fill="currentColor" 로 두고 .engine-icon 의 color 로 브랜드색 부여한다. */
const ENGINE_ICON_MYSQL = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path fill="currentColor" d="M16.405 5.501c-.115 0-.193.014-.274.033v.013h.014c.054.104.146.18.214.273.054.107.1.214.154.32l.014-.015c.094-.066.14-.172.14-.333-.04-.047-.046-.094-.08-.14-.04-.067-.126-.1-.18-.153zM5.77 18.695h-.927a50.854 50.854 0 00-.27-4.41h-.008l-1.41 4.41H2.45l-1.4-4.41h-.01a72.892 72.892 0 00-.195 4.41H0c.055-1.966.192-3.81.41-5.53h1.15l1.335 4.064h.008l1.347-4.064h1.095c.242 2.015.384 3.86.428 5.53zm4.017-4.08c-.378 2.045-.876 3.533-1.492 4.46-.482.716-1.01 1.073-1.583 1.073-.153 0-.34-.046-.566-.138v-.494c.11.017.24.026.386.026.268 0 .483-.075.647-.222.197-.18.295-.382.295-.605 0-.155-.077-.47-.23-.944L6.23 14.615h.91l.727 2.36c.164.536.233.91.205 1.123.4-1.064.678-2.227.835-3.483zm12.325 4.08h-2.63v-5.53h.885v4.85h1.745zm-3.32.135l-1.016-.5c.09-.076.177-.158.255-.25.433-.506.648-1.258.648-2.253 0-1.83-.718-2.746-2.155-2.746-.704 0-1.254.232-1.65.697-.43.508-.646 1.256-.646 2.245 0 .972.19 1.686.574 2.14.35.41.877.615 1.583.615.264 0 .506-.033.725-.098l1.325.772.36-.622zM15.5 17.588c-.225-.36-.337-.94-.337-1.736 0-1.393.424-2.09 1.27-2.09.443 0 .77.167.977.5.224.362.336.936.336 1.723 0 1.404-.424 2.108-1.27 2.108-.445 0-.77-.167-.978-.5zm-1.658-.425c0 .47-.172.856-.516 1.156-.344.3-.803.45-1.384.45-.543 0-1.064-.172-1.573-.515l.237-.476c.438.22.833.328 1.19.328.332 0 .593-.073.783-.22a.754.754 0 00.3-.615c0-.33-.23-.61-.648-.845-.388-.213-1.163-.657-1.163-.657-.422-.307-.632-.636-.632-1.177 0-.45.157-.81.47-1.085.315-.278.72-.415 1.22-.415.512 0 .98.136 1.4.41l-.213.476a2.726 2.726 0 00-1.064-.23c-.283 0-.502.068-.654.206a.685.685 0 00-.248.524c0 .328.234.61.666.85.393.215 1.187.67 1.187.67.433.305.648.63.648 1.168zm9.382-5.852c-.535-.014-.95.04-1.297.188-.1.04-.26.04-.274.167.055.053.063.14.11.214.08.134.218.313.346.407.14.11.28.216.427.31.26.16.555.255.81.416.145.094.293.213.44.313.073.05.12.14.214.172v-.02c-.046-.06-.06-.147-.105-.214-.067-.067-.134-.127-.2-.193a3.223 3.223 0 00-.695-.675c-.214-.146-.682-.35-.77-.595l-.013-.014c.146-.013.32-.066.46-.106.227-.06.435-.047.67-.106.106-.027.213-.06.32-.094v-.06c-.12-.12-.21-.283-.334-.395a8.867 8.867 0 00-1.104-.823c-.21-.134-.476-.22-.697-.334-.08-.04-.214-.06-.26-.127-.12-.146-.19-.34-.275-.514a17.69 17.69 0 01-.547-1.163c-.12-.262-.193-.523-.34-.763-.69-1.137-1.437-1.826-2.586-2.5-.247-.14-.543-.2-.856-.274-.167-.008-.334-.02-.5-.027-.11-.047-.216-.174-.31-.235-.38-.24-1.364-.76-1.644-.072-.18.434.267.862.422 1.082.115.153.26.328.34.5.047.116.06.235.107.356.106.294.207.622.347.897.073.14.153.287.247.413.054.073.146.107.167.227-.094.136-.1.334-.154.5-.24.757-.146 1.693.194 2.25.107.166.362.534.703.393.3-.12.234-.5.32-.835.02-.08.007-.133.048-.187v.015c.094.188.188.367.274.555.206.328.566.668.867.895.16.12.287.328.487.402v-.02h-.015c-.043-.058-.1-.086-.154-.133a3.445 3.445 0 01-.35-.4 8.76 8.76 0 01-.747-1.218c-.11-.21-.202-.436-.29-.643-.04-.08-.04-.2-.107-.24-.1.146-.247.273-.32.453-.127.288-.14.642-.188 1.01-.027.007-.014 0-.027.014-.214-.052-.287-.274-.367-.46-.2-.475-.233-1.238-.06-1.785.047-.14.247-.582.167-.716-.042-.127-.174-.2-.247-.303a2.478 2.478 0 01-.24-.427c-.16-.374-.24-.788-.414-1.162-.08-.173-.22-.354-.334-.513-.127-.18-.267-.307-.368-.52-.033-.073-.08-.194-.027-.274.014-.054.042-.075.094-.09.088-.072.335.022.422.062.247.1.455.194.662.334.094.066.195.193.315.226h.14c.214.047.455.014.655.073.355.114.675.28.962.46a5.953 5.953 0 012.085 2.286c.08.154.115.295.188.455.14.33.313.663.455.982.14.315.275.636.476.897.1.14.502.213.682.286.133.06.34.115.46.188.23.14.454.3.67.454.11.076.443.243.463.378z"/></svg>`;
const ENGINE_ICON_MSSQL = `<svg viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path fill="currentColor" d="M52.935 0v.002c-.426-.058-7.306 2.42-11.742 4.223-5.988 2.44-10.636 4.766-13.504 6.78-.926.657-2.054 1.75-2.475 2.37l-.007-.021a1.424 1.424 0 0 0-.069.148c-.022.04-.052.086-.066.12a1.812 1.812 0 0 0-.115.66l.064.06c.017.207.065.44.168.695.252.62.988 1.376 1.822 2.15 0 0 8.621 8.409 9.668 9.61 4.766 5.503 6.84 10.927 7.034 18.406.117 4.805-.796 9.03-3.063 13.932-4.03 8.796-12.535 18.504-25.652 29.276l.199-.067c-.09.072-.208.174-.295.242-1.57 1.24-3.896 3.565-5.078 5.038-1.764 2.209-3.157 4.553-3.758 6.355-1.066 3.255-.543 6.548 1.51 9.59 2.636 3.875 7.887 7.83 14.01 10.521 3.12 1.377 8.368 3.14 12.322 4.127 6.567 1.667 19.28 3.469 26.273 3.739 1.414.059 3.312.059 3.39 0 .155-.097 1.241-2.168 2.501-4.744 4.3-8.778 7.399-17.013 9.086-24.047 1.007-4.262 1.801-9.94 2.324-16.663.136-1.88.194-8.177.078-10.308-.175-3.487-.483-6.316-.968-9.086a4.17 4.17 0 0 1-.07-.573c15.578-4.628 32.768-8.821 44.187-10.568l1.764-.271-.272-.428c-1.55-2.403-2.615-3.894-3.894-5.483-3.72-4.61-8.233-8.349-13.756-11.449-7.595-4.244-17.419-7.557-29.858-10.018-2.344-.465-7.495-1.357-11.68-1.996l-.39-.699c-2.287-4.03-4.805-9.027-6.278-12.398-1.142-2.616-2.228-5.639-2.828-7.809C53.187.098 53.15.02 52.935 0Zm-.31.988h.02c.018.02.095.564.173 1.203.33 2.712.931 5.328 1.881 8.157.716 2.13.716 2.015-.117 1.763-1.976-.542-10.83-2.072-17.244-2.964-1.027-.135-1.899-.271-1.899-.291-.077-.078 4.63-2.537 6.703-3.506 2.654-1.22 9.94-4.265 10.483-4.362ZM33.947 9.67l.756.252c4.108 1.395 14.434 3.373 20.13 3.838.64.058 1.182.115 1.2.115.02.02-.52.31-1.219.639-2.75 1.376-5.775 3.061-7.867 4.36-.476.296-.912.546-1.127.648a1193.726 1193.726 0 0 1-1.932-.315l-1.824-1.787a803.536 803.536 0 0 0-7.11-6.84zm-.775.602 2.732 3.41c1.492 1.88 3.003 3.72 3.332 4.127.291.359.503.622.543.7-1.935-.337-4.006-.708-5.6-1.052-1.163-.252-3.39-.775-5.134-1.375-.18-.07-.385-.146-.58-.219v-.205c.02-1.3 1.666-3.238 4.455-5.213zm23.173 4.646c.015-.007.03-.006.04.004.077 0 .172.172.404.695.66 1.453 2.715 5.367 3.219 6.123l.064.104a1193.726 1193.726 0 0 1-10.977-1.79 2.86 2.86 0 0 1 .372-.232c2.035-1.124 4.088-2.557 5.91-4.088.445-.368.851-.715.93-.773a.097.097 0 0 1 .038-.043zm-26.138 3.275c.019-.018.329.1.736.235a50.336 50.336 0 0 0 2.81.851 142.909 142.909 0 0 0 2.557.678c1.162.29 2.132.563 2.15.563.137.136 2.094 6.394 2.753 8.797.252.91.446 1.685.427 1.685-.02.02-.234-.31-.486-.756-2.267-3.99-5.851-8.04-9.998-11.297-.542-.387-.95-.736-.95-.756zm9.513 2.618c0 .038 0 .02.02.02.098 0 .524.057 1.047.173 3.293.736 9.203 1.86 12.98 2.5.64.097 1.143.214 1.143.252 0 .04-.23.175-.522.33-.64.33-3.217 1.86-4.07 2.44-2.15 1.435-4.087 2.983-5.482 4.378a79.99 79.99 0 0 1-1.047 1.028s-.115-.33-.213-.737c-.697-2.694-2.15-6.684-3.469-9.494-.213-.445-.387-.852-.387-.89zm16.8 3.215c.115.04.31.699.697 2.152a31.732 31.732 0 0 1 .93 8.873c-.04.814-.079 1.57-.118 1.668l-.057.191-1.007-.33c-2.073-.658-5.444-1.645-8.33-2.459-1.648-.446-2.985-.852-2.985-.89 0-.117 2.403-2.52 3.43-3.43 1.956-1.725 7.264-5.832 7.44-5.775zm1.335.195c.058-.058 8.024 1.316 11.647 2.014 2.694.523 6.607 1.338 6.84 1.435.115.04-.291.269-1.59.852-5.115 2.305-8.914 4.38-12.692 6.898-.988.66-1.822 1.201-1.84 1.201-.02 0-.039-.562-.039-1.24 0-3.681-.734-7.401-2.091-10.54-.136-.31-.254-.601-.235-.62zm20.596 4.068c.058.057-.193 1.629-.426 2.559-.698 2.887-2.576 7.17-4.88 11.2-.409.716-.778 1.297-.817 1.316-.038.02-.558-.273-1.16-.622-2.247-1.318-4.806-2.555-7.596-3.718-.775-.33-1.454-.601-1.473-.641-.136-.115 6.104-4.242 9.397-6.219 2.617-1.589 6.879-3.952 6.955-3.875zm1.475.233c.174 0 3.7.968 5.54 1.511 4.554 1.356 9.784 3.275 13.194 4.825l1.414.638-.986.233c-8.33 1.918-15.463 4.129-22.342 6.918-.562.233-1.066.425-1.104.425-.039 0 .157-.444.409-.986 2.073-4.399 3.408-8.991 3.738-12.906.019-.368.079-.658.137-.658zm-35.11 8.06c.058-.058 2.751.582 4.205.989 2.21.62 6.899 2.19 6.899 2.304 0 .02-.525.466-1.145 1.008-2.538 2.112-4.98 4.341-7.906 7.17-.871.833-1.606 1.51-1.645 1.51-.04 0-.059-.115-.04-.27.445-3.255.35-7.44-.27-11.683-.06-.543-.117-1.009-.098-1.028zm56.596.059c.038.039-1.24 2.052-2.055 3.195-1.162 1.667-2.867 3.877-6.722 8.72a1289.46 1289.46 0 0 0-5.076 6.413c-.775.969-1.415 1.783-1.436 1.783-.018 0-.27-.35-.541-.775-2.17-3.256-4.767-6.103-7.848-8.66a44.534 44.534 0 0 0-1.431-1.164c-.214-.155-.39-.31-.39-.33 0-.057 3.294-1.472 5.794-2.479 4.38-1.783 10.345-3.913 14.822-5.29 2.344-.735 4.844-1.452 4.883-1.413zm1.492.387c.077-.02.543.214 1.104.543 4.709 2.693 9.32 6.162 12.963 9.726 1.027 1.008 3.564 3.641 3.525 3.66 0 0-.891.08-1.937.157-8.157.62-18.6 2.343-28.635 4.765-.68.155-1.28.291-1.319.291-.038 0 .716-.756 1.666-1.666 5.89-5.677 8.583-9.261 11.76-15.656.446-.948.834-1.762.873-1.82zm-43.148 4.418c.27.058 2.788 1.239 4.687 2.189 1.744.871 4.361 2.266 4.496 2.383.02.019-.91.503-2.054 1.066a135.033 135.033 0 0 0-10.018 5.522c-.93.562-1.704 1.027-1.723 1.027-.078 0-.058-.078.465-1.027 1.744-3.177 3.14-6.975 3.934-10.676.077-.29.155-.484.213-.484zm-2.52.464c.058.058-.6 2.442-1.008 3.74-.795 2.46-2.131 5.54-3.43 7.866-.31.542-.775 1.338-1.027 1.783l-.484.774-1.084-1.045c-1.26-1.22-2.287-1.978-3.604-2.657-.524-.27-.93-.502-.93-.54 0-.156 3.314-3.159 5.852-5.329 1.82-1.57 5.657-4.65 5.715-4.592zm15.404 6.336.95.62c2.17 1.414 4.726 3.295 6.683 4.94 1.104.91 3.235 2.83 3.662 3.294l.233.252-1.57.447c-8.874 2.46-15.733 4.649-23.735 7.594-.892.33-1.647.6-1.705.6-.116 0-.213.096 1.783-1.745 5.115-4.707 9.65-9.898 13.022-14.955zm-4.05 1.008c.04.04-2.614 3.777-4.203 5.889-1.9 2.519-5.272 6.743-7.598 9.494-.968 1.144-1.8 2.092-1.84 2.111-.058.02-.078-.27-.078-.716 0-2.344-.599-4.844-1.645-6.975-.446-.891-.523-1.104-.425-1.201.368-.33 6.004-3.545 9.568-5.463 2.404-1.28 6.163-3.177 6.22-3.139zM44.1 55.26c.057 0 .502.233 1.007.504a21.28 21.28 0 0 1 3.332 2.248c.04.038-.464.446-1.123.93-1.84 1.317-4.63 3.43-6.258 4.728-1.705 1.356-1.763 1.394-1.57 1.104 1.28-1.957 1.92-3.062 2.598-4.477a36.066 36.066 0 0 0 1.627-4.05c.155-.56.347-.987.386-.987zm6.53 5.113c.097-.018.213.157.735.932 1.104 1.647 1.957 3.857 2.17 5.639l.039.386-2.654 1.028c-4.747 1.84-9.126 3.662-12.09 5.02a217.067 217.067 0 0 0-3.237 1.548c-.95.484-1.724.853-1.724.834 0-.02.6-.465 1.336-1.008 5.794-4.204 10.813-8.816 14.572-13.427.407-.484.775-.93.813-.95zm-3.003.737v.002c.078.077-2.132 2.576-3.643 4.107-3.74 3.816-7.441 6.801-12.033 9.707-.582.368-1.104.697-1.162.735-.135.078.038-.116 2.054-2.305a52.694 52.694 0 0 0 3.352-3.97c.736-.95.871-1.086 1.937-1.84 2.85-2.056 9.418-6.513 9.495-6.436zm25.974 2.3c.274 1.057.78 6.126.918 9.481.04.795.019 1.318-.021 1.318-.154 0-3.273-1.84-5.5-3.236-1.93-1.215-5.579-3.634-6.18-4.113a358.495 358.495 0 0 1 10.783-3.45zm-12.867 4.192c.254.11.635.32 1.404.795 3.991 2.5 9.418 5.522 11.743 6.53.716.31.793.193-.854 1.318-3.526 2.402-7.924 4.765-13.31 7.148-.95.426-1.745.756-1.764.756-.04 0 .077-.486.232-1.067 1.297-4.825 2.036-9.705 2.075-13.619.01-.977.014-1.46.039-1.707l.435-.154zm-2.965 1.055c.094.476.021 4.368-.127 5.494a49.361 49.361 0 0 1-1.78 8.428c-.214.717-.41 1.319-.448 1.357-.078.097-2.732-2.5-3.604-3.508-1.51-1.744-2.692-3.486-3.564-5.191-.404-.79-.987-2.205-1.055-2.518a345.346 345.346 0 0 1 8.592-3.355c.617-.232 1.343-.473 1.986-.707zm-12.603 4.9c.047.069.163.327.271.652.62 1.685 2.013 4.165 3.215 5.754 1.318 1.744 3.043 3.605 4.477 4.825.465.387.89.756.949.814.116.117.155.097-3.004 1.299-3.66 1.395-7.652 2.79-12.225 4.262a609.84 609.84 0 0 0-3.275 1.066c-.175.058-.114-.04.389-.834 2.267-3.544 5.714-10.5 7.652-15.422.33-.853.659-1.706.717-1.9.027-.095.066-.15.103-.211l.73-.305zm-4.01 1.7c-.132.39-.973 2.151-1.842 3.853-1.88 3.663-3.933 7.267-6.684 11.646-.466.755-.91 1.453-.97 1.53-.096.136-.135.098-.446-.502-.659-1.3-1.2-2.965-1.492-4.496-.29-1.511-.232-4.146.098-5.774.15-.717.216-.987.36-1.16a225.041 225.041 0 0 1 10.976-5.098zm33.479 1.2v.813c0 4.321-.465 10.25-1.143 14.57-.116.756-.213 1.377-.232 1.397 0 0-.563-.156-1.221-.35a49.985 49.985 0 0 1-8.912-3.816c-1.88-1.027-4.61-2.714-4.533-2.791.019-.02.832-.445 1.78-.95 3.799-1.975 7.441-4.107 10.6-6.22 1.182-.794 2.963-2.071 3.35-2.42zm-48.048 5.737c.074.004.052.163-.062.851a27.507 27.507 0 0 0-.213 2.07c-.155 2.83.31 4.925 1.705 7.792.388.794.698 1.453.678 1.472-.135.117-12.962 3.875-16.992 4.979-1.201.33-2.247.62-2.325.639-.136.04-.155.021-.097-.309.446-2.848 2.617-6.568 5.64-9.707 2.014-2.093 3.622-3.314 6.373-4.883.921-.524 2.066-1.163 3.057-1.71.737-.401 1.484-.799 2.236-1.194zm30.221 5.404h.002c.02-.02.483.232 1.045.56 4.147 2.404 9.921 4.633 14.842 5.776l.445.096-.619.35c-2.576 1.433-11.045 4.96-19.705 8.195-1.26.465-2.498.93-2.73 1.027-.233.097-.448.155-.448.135 0-.02.35-.698.795-1.531 2.422-4.534 4.863-10.055 6.104-13.891.155-.368.25-.697.27-.717zm-3.08 1.006h.002c.02.02-.136.428-.33.893-1.686 4.088-3.895 8.545-6.724 13.543-.716 1.28-1.317 2.306-1.336 2.306-.02 0-.601-.35-1.3-.775-4.106-2.52-7.75-5.62-10.132-8.623l-.35-.426 1.764-.484c6.316-1.724 11.684-3.584 17.012-5.87.756-.31 1.375-.564 1.394-.564zm19.143 6.686c.02.446-.967 4.437-1.781 7.324-.678 2.422-1.26 4.32-2.327 7.672-.464 1.474-.87 2.693-.89 2.693-.02 0-.135-.018-.252-.056-5.754-1.047-10.908-2.501-15.752-4.438-1.356-.543-3.293-1.415-3.41-1.512-.038-.039 1.124-.581 2.597-1.22 8.816-3.856 17.96-8.235 21.1-10.114.368-.233.657-.35.715-.35zM28.677 96.8c.04.04-2.423 3.585-5.87 8.41-1.203 1.686-2.597 3.661-3.12 4.397a77.468 77.468 0 0 0-1.764 2.596l-.814 1.261-.871-.738c-1.027-.853-2.809-2.673-3.604-3.68-1.666-2.073-2.791-4.264-3.236-6.26-.214-.93-.214-1.394-.02-1.45a1459.308 1459.308 0 0 1 10.31-2.424 861.655 861.655 0 0 0 6.935-1.627c1.124-.271 2.035-.485 2.054-.485zm2.479.95.621.697c2.79 3.12 5.637 5.425 9.086 7.44.62.35 1.086.659 1.047.679-.135.096-11.974 4.3-17.457 6.2a462.503 462.503 0 0 1-5.639 1.956c-.019 0-.194-.117-.387-.252l-.35-.252.563-.814c1.82-2.635 4.107-5.521 9.086-11.528zm15.463 11.062c.019-.02.87.29 1.918.68 2.519.949 4.513 1.55 7.187 2.228 3.294.833 8.061 1.646 10.872 1.88.426.037.657.076.58.134-.136.077-2.985 1.028-5.077 1.686-3.333 1.047-13.504 4.05-21.797 6.433a218.736 218.736 0 0 1-2.925.834c-.194.038-.834-.138-.834-.215 0-.038.465-.638 1.027-1.297 2.79-3.333 5.561-7.054 7.867-10.58.64-.969 1.182-1.764 1.182-1.783zm-3.412.098h.002c.019.02-1.357 2.227-3.76 6.025-1.026 1.608-2.17 3.432-2.576 4.07-.388.62-.971 1.59-1.3 2.131l-.56.987-.29-.076c-.699-.195-5.601-1.919-6.9-2.442a48.226 48.226 0 0 1-4.513-2.072c-1.55-.834-3.487-2.074-3.332-2.113.038-.02 2.692-.736 5.889-1.608 8.485-2.306 13.194-3.642 16.275-4.611.562-.175 1.046-.311 1.065-.291zm24.123 5.656h.021c.077.195-3.063 8.913-4.207 11.664-.25.62-.348.776-.484.756-.33-.02-4.881-.657-7.652-1.064-4.824-.736-12.925-2.15-14.958-2.616l-.464-.097 2.886-.659c6.2-1.395 9.184-2.15 12.207-3.08a86.251 86.251 0 0 0 11.413-4.4c.6-.27 1.102-.483 1.238-.502z"/></svg>`;
const ENGINE_CATALOG = [
  { value: "mysql", label: "MySQL", defaultPort: 3306, color: "#00758F", icon: ENGINE_ICON_MYSQL },
  { value: "mssql", label: "Microsoft SQL Server", defaultPort: 1433, color: "#EE352C", icon: ENGINE_ICON_MSSQL },
];
const ENGINE_BY_VALUE = new Map(ENGINE_CATALOG.map((e) => [e.value, e]));

// 엔진 값 → 메타(미지정/미지원 값은 카탈로그 첫 항목 mysql 으로 폴백 — 백엔드 기본값과 정합).
function engineMeta(value) {
  return ENGINE_BY_VALUE.get(String(value == null ? "" : value).trim().toLowerCase()) || ENGINE_CATALOG[0];
}

// 엔진 선택용 커스텀 드롭다운(아이콘 + 라벨). 반환 { wrap, valueHolder }.
//  valueHolder 는 hidden <input> — _dsRenderForm 의 save 핸들러가 `inputs.engine.value` 로
//  그대로 읽어가도록 기존 텍스트 input 과 동일한 .value 계약을 유지한다.
//  토글/외부클릭-닫기 패턴은 admin-db-picker(데이터베이스 추가 드롭다운)와 동일하게 미러링한다.
function _dsBuildEngineField(currentValue, opts) {
  opts = opts || {};
  const selected = engineMeta(currentValue).value;

  const wrap = document.createElement("label");
  wrap.className = "admin-field admin-field--engine";
  const labelEl = document.createElement("span");
  labelEl.className = "admin-field-label";
  labelEl.textContent = opts.label || "엔진";
  wrap.appendChild(labelEl);

  const picker = document.createElement("div");
  picker.className = "engine-picker";

  const hidden = document.createElement("input");
  hidden.type = "hidden";
  hidden.value = selected;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "engine-picker-btn";
  btn.setAttribute("aria-haspopup", "listbox");
  btn.setAttribute("aria-expanded", "false");

  const list = document.createElement("div");
  list.className = "engine-picker-list hidden";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "엔진 선택");

  const _iconSpan = (meta) => {
    const ic = document.createElement("span");
    ic.className = "engine-icon";
    ic.style.color = meta.color;       // 단색 path(currentColor)에 브랜드색 부여.
    ic.innerHTML = meta.icon;
    return ic;
  };

  const _paintBtn = (val) => {
    const meta = engineMeta(val);
    btn.innerHTML = "";
    const lab = document.createElement("span");
    lab.className = "engine-picker-label";
    lab.textContent = meta.label;
    const caret = document.createElement("span");
    caret.className = "engine-picker-caret";
    caret.textContent = "▾";
    btn.append(_iconSpan(meta), lab, caret);
  };

  const _close = () => { list.classList.add("hidden"); btn.setAttribute("aria-expanded", "false"); };
  const _open = () => {
    list.classList.remove("hidden");
    btn.setAttribute("aria-expanded", "true");
    const cur = list.querySelector('.engine-option[aria-selected="true"]') || list.querySelector(".engine-option");
    if (cur) cur.focus();
  };

  const _choose = (val) => {
    hidden.value = engineMeta(val).value;
    _paintBtn(hidden.value);
    list.querySelectorAll(".engine-option").forEach((o) =>
      o.setAttribute("aria-selected", o.dataset.engine === hidden.value ? "true" : "false"));
    _close();
    btn.focus();
    if (typeof opts.onChange === "function") opts.onChange(hidden.value);
  };

  ENGINE_CATALOG.forEach((meta) => {
    const opt = document.createElement("button");
    opt.type = "button";
    opt.className = "engine-option";
    opt.dataset.engine = meta.value;
    opt.setAttribute("role", "option");
    opt.setAttribute("aria-selected", meta.value === selected ? "true" : "false");
    const txt = document.createElement("span");
    txt.className = "engine-option-text";
    const name = document.createElement("strong"); name.textContent = meta.label;
    const sub = document.createElement("small"); sub.textContent = `기본 포트 ${meta.defaultPort}`;
    txt.append(name, sub);
    opt.append(_iconSpan(meta), txt);
    opt.addEventListener("click", () => _choose(meta.value));
    list.appendChild(opt);
  });

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (list.classList.contains("hidden")) _open(); else _close();
  });

  // 키보드: ↓/↑ 이동, Enter/Space 선택, Esc 닫기(admin a11y 표준).
  picker.addEventListener("keydown", (e) => {
    const items = Array.from(list.querySelectorAll(".engine-option"));
    const idx = items.indexOf(document.activeElement);
    if (e.key === "Escape") { _close(); btn.focus(); }
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (list.classList.contains("hidden")) { _open(); }
      else { (items[idx + 1] || items[items.length - 1]).focus(); }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!list.classList.contains("hidden")) (items[idx - 1] || items[0]).focus();
    } else if ((e.key === "Enter" || e.key === " ") && document.activeElement.classList.contains("engine-option")) {
      e.preventDefault(); _choose(document.activeElement.dataset.engine);
    }
  });

  // 패널 바깥 클릭 시 닫기(admin-db-picker 와 동일 패턴).
  document.addEventListener("click", function _closeEnginePicker(e) {
    if (!picker.contains(e.target)) _close();
  });

  _paintBtn(selected);
  picker.append(btn, list, hidden);
  wrap.appendChild(picker);
  return { wrap, valueHolder: hidden };
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

  const inputs = {};
  const addTextField = ([k, label, val, ro]) => {
    const wrap = document.createElement("label"); wrap.className = "admin-field";
    const span = document.createElement("span"); span.className = "admin-field-label"; span.textContent = label;
    const inp = document.createElement("input");
    inp.type = (k === "password") ? "password" : "text";
    inp.value = val; inp.readOnly = ro; inp.autocomplete = "off";
    if (ro) inp.classList.add("is-readonly");
    wrap.append(span, inp); form.appendChild(wrap); inputs[k] = inp;
    return inp;
  };

  // 1) 라벨(편집 시에만 — 신규는 서버가 엔진+호스트+포트 해시로 자동 생성).
  if (isEdit) addTextField(["key", "라벨 (표시용 · 변경 가능)", ds.key, false]);

  // 2) 엔진 — 자유 텍스트 → 아이콘 드롭다운(TASK-20260618T022006). 식별 용이 + 오타로 인한
  //    잘못된 엔진 차단(백엔드도 mysql|mssql 만 허용하나 FE 에서 선제 가드). save 핸들러는
  //    inputs.engine.value 를 기존처럼 읽는다(hidden input 계약 동일).
  const engineField = _dsBuildEngineField(isEdit ? (ds.engine || "mysql") : "mysql", {
    label: "엔진",
    onChange: (val) => {
      // 포트 미입력 시 엔진 기본 포트를 placeholder 로 안내(사용자 입력값은 강제 변경하지 않음 —
      //   백엔드도 빈 포트는 엔진 기본값으로 채운다: mysql=3306 / mssql=1433).
      if (inputs.port) inputs.port.placeholder = String(engineMeta(val).defaultPort);
    },
  });
  inputs.engine = engineField.valueHolder;
  form.appendChild(engineField.wrap);

  // 3) 나머지 접속 필드.
  //    TASK-0212: user 는 GET 에서 마스킹(보안)돼 수정 시 pre-fill 안 됨 → password 처럼 write-only.
  //      빈값으로 두면 기존 유저 유지(서버도 빈 user 는 무시). 변경 시에만 입력.
  //    TASK-0213: '기본 참조 DB'(default_db) 필드 폐지 — 접근 DB 는 제품의 '접근 가능 데이터베이스'(allowlist)로
  //      관리하고, MSSQL 연결은 그 중 첫 DB 로 자동(없으면 중립 tempdb). 데이터소스에 기본 DB 를 두지 않는다.
  [
    ["host", "호스트", isEdit ? (ds.host || "") : "", false],
    ["port", "포트", isEdit ? (ds.port || "") : "", false],
    ["user", isEdit ? "DB 유저 (변경 시에만 입력 · RO 권장)" : "DB 유저 (RO 권장)", "", false],
    ["password", isEdit ? "비밀번호 (변경 시에만 입력)" : "비밀번호", "", false],
  ].forEach(addTextField);

  // 포트 placeholder 를 현재 엔진 기본값으로 초기화(미입력 시 어떤 값이 적용될지 안내).
  if (inputs.port) inputs.port.placeholder = String(engineMeta(inputs.engine.value).defaultPort);

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
  adminState.pending.productDatabases.forEach((draft, pkey) => {
    // TASK-0228 (1:N): 복합 키 `productId::dsKey` 파싱(레거시 단일 id 키 호환).
    const _ps = String(pkey).split("::");
    const id = Number(_ps[0]);
    const dk = (_ps.length > 1 ? _ps[1] : "");
    const base = adminState.products.find((p) => Number(p.id) === Number(id));
    const c = Array.isArray(draft) ? draft.length : 0;
    addRow(`제품 DB · ${base ? base.name : `#${id}`}${dk ? ` · [${dk}]` : ""} · ${c} schema`);
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
    // TASK-0293: 아바타 이미지(설정 시) 또는 username 시드 Identicon — 작업화면 프로필과 동일 시드/폴백.
    //   기존 이니셜 텍스트는 작업화면에서 바꾼 아바타가 관리 콘솔에 반영 안 되던 조회 버그의 원인.
    applyAvatar(avatar, { url: account.avatar_url, seed: account.username, initials: account.username.slice(0, 2).toUpperCase() });
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
  renderAccountList();  // TASK-0302: pending 점(•) 즉시 반영
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
  renderAccountList();  // TASK-0302: pending 점(•)/삭제대기 표시 즉시 반영
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
  // TASK-0293: 아바타 이미지 또는 username 시드 Identicon (작업화면 프로필 정합).
  applyAvatar(avatar, { url: base.avatar_url, seed: base.username, initials: base.username.slice(0, 2).toUpperCase() });
  // 관리자(console.manage + account.update)면 대상 계정의 아바타 변경/제거 — 제품 아이콘과 동일 ✎ 오버레이 패턴.
  let avatarNode = avatar;
  let avatarRemoveBtn = null;
  if (can("console.manage") && can("account.update") && !base.deleted_at) {
    const avatarWrap = document.createElement("div");
    avatarWrap.className = "profile-avatar-edit";
    const fileInput = document.createElement("input");
    fileInput.type = "file"; fileInput.accept = "image/png,image/jpeg,image/webp"; fileInput.hidden = true;
    const changeBtn = document.createElement("button");
    changeBtn.type = "button"; changeBtn.className = "profile-avatar-change"; changeBtn.textContent = "✎";
    changeBtn.title = "프로필 아바타 변경"; changeBtn.setAttribute("aria-label", "프로필 아바타 변경");
    changeBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      if (f.size > 2 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 2MB).", true); fileInput.value = ""; return; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await apiFetch(`/api/admin/accounts/${Number(base.id)}/avatar`, { method: "PUT", body: fd });
        base.avatar_url = r.avatar_url || null;
        renderAccountDetail();
        renderAccountList();
        showToast("프로필 아바타를 변경했어요.");
      } catch (err) { showToast(err.message || "아바타 변경 실패", true); }
      finally { fileInput.value = ""; }
    });
    avatarWrap.append(avatar, changeBtn, fileInput);
    avatarNode = avatarWrap;
    if (base.avatar_url) {
      avatarRemoveBtn = document.createElement("button");
      avatarRemoveBtn.type = "button"; avatarRemoveBtn.className = "profile-avatar-remove"; avatarRemoveBtn.textContent = "아바타 제거";
      avatarRemoveBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/admin/accounts/${Number(base.id)}/avatar`, { method: "DELETE" });
          base.avatar_url = null;
          renderAccountDetail();
          renderAccountList();
          showToast("프로필 아바타를 제거했어요.");
        } catch (err) { showToast(err.message || "아바타 제거 실패", true); }
      });
    }
  }
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
  if (avatarRemoveBtn) idText.appendChild(avatarRemoveBtn);
  idBlock.append(avatarNode, idText);

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
  // TASK-0300 (사용자 결정 2026-06-17): 역할 배정 경유 escalation 차단의 UX 면 — 본인 보유 권한
  //   범위를 초과하는 권한을 가진 역할은 드롭다운에서 숨긴다(설정 불가). 현재 배정된 역할은
  //   상태 표시를 위해 초과해도 유지(변경 안 하면 백엔드 no-op). 백엔드가 최종 정본(403).
  const _actorAllowed = new Set(
    Object.entries(adminState.me?.permissions || {}).filter(([, g]) => g).map(([c]) => c)
  );
  const _roleAssignable = (role) => (role.permission_codes || []).every((c) => _actorAllowed.has(c));
  adminState.roles
    .filter((r) => (r.is_active || Number(r.id) === currentRoleId)
      && (Number(r.id) === currentRoleId || _roleAssignable(r)))
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
  // TASK-0300: 본인 보유 권한만 표시·설정. 미보유 권한은 숨김 처리됨을 알리는 안내.
  const overrideHint = document.createElement("div");
  overrideHint.className = "admin-detail-hint";
  overrideHint.textContent = "본인이 보유한 권한만 표시·설정할 수 있습니다.";
  overrideSection.appendChild(overrideHint);
  // TASK-0300: 편집 주체(admin)가 보유한(effective=true) 권한 code 집합 — grid 숨김 필터의 상한.
  const _selfAllowed = new Set(
    Object.entries(adminState.me?.permissions || {})
      .filter(([, granted]) => granted)
      .map(([code]) => code)
  );
  const overrideWrap = document.createElement("div");
  overrideWrap.className = "override-grid";
  // TASK-0270: "상속(허용)" 게이트 판정용 — 계정 역할이 부여한 권한 code Set(상속 baseline).
  //   override 값이 "상속"이고 역할이 그 권한을 부여하면 effective 허용 → 게이트로 동작(자식 펼침).
  const _ovRole = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
  const _inheritedGrants = new Set((_ovRole && _ovRole.permission_codes) || []);
  renderPermissionGrid(
    overrideWrap,
    [],
    disabledBase || !can("account.permission.override.manage"),
    "override",
    merged.permission_overrides || {},
    () => {
      // grid 의 select[data-override-code] 에서 현재 값을 수집한다. (제품 접근 카드의 select 도
      // product_access 그룹 안에 임베드돼 함께 잡힌다 — dynamic product.access.* 포함.)
      const overrides = {};
      const seen = new Set();
      overrideWrap.querySelectorAll("select[data-override-code]").forEach((select) => {
        overrides[select.dataset.overrideCode] = select.value;
        seen.add(select.dataset.overrideCode);
      });
      // TASK-0300: grid 에 렌더되지 않은(본인 미보유라 숨긴) 권한의 기존 override 는 보존한다.
      //   payload 에서 누락되면 백엔드 delete-all-then-insert 로 삭제되므로 명시 보존.
      //   (백엔드도 _enforce_override_self_scope 로 merge 하지만 pending 표시 정합을 위해 여기서도.)
      Object.entries(merged.permission_overrides || {}).forEach(([code, value]) => {
        if (!seen.has(code)) overrides[code] = value;
      });
      setAccountPending(adminState.selectedAccountId, { permission_overrides: overrides });
      renderAccountList();
    },
    { excludeDynamic: true, inheritedGrants: _inheritedGrants, allowedCodes: _selfAllowed }
  );
  overrideSection.appendChild(overrideWrap);
  paneEl.appendChild(overrideSection);

  // TASK-0053 (사용자 follow-up 2026-05-07): 제품별 접근 카드 list 를 권한 grid 의 제품 접근 그룹 details
  // 안으로 이전. 사용자가 제품 그룹을 collapse 하면 product 별 override 카드도 함께 접힌다.
  // TASK-0288: 제품 접근 카드는 'product_access'(제품 사용, 작업 화면) 그룹으로 이전 — 관리 콘솔
  // 제품 관리(product) 그룹과 분리. (groupedPermissions 가 빈 컨테이너를 보장한다.)
  const accountProductGroup = overrideWrap.querySelector('details[data-perm-group="product_access"]');
  const productOverrides = buildAccountProductOverrideList(
    merged,
    disabledBase || !can("account.permission.override.manage"),
    { embed: Boolean(accountProductGroup), allowedCodes: _selfAllowed },
  );
  if (accountProductGroup) {
    accountProductGroup.appendChild(productOverrides);
    // TASK-0303: 카드(select[data-override-code])는 grid 렌더 이후 임베드되므로 배지를 다시 집계하고,
    //   allow/deny override 가 있으면 그룹을 펼친다(역할 카드 동형).
    _updateOverrideGroupSummary(accountProductGroup);
    const _ov = accountProductGroup.querySelectorAll("select[data-override-code]");
    let _hasNonInherit = false;
    _ov.forEach((s) => { if (s.value === "allow" || s.value === "deny") _hasNonInherit = true; });
    if (_hasNonInherit) accountProductGroup.open = true;
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
    // 계정 탭 filteredAccounts() 와 동형: 상태 필터 먼저, 그다음 검색어 매칭.
    if (adminState.roleFilter === "active" && !role.is_active) return false;
    if (adminState.roleFilter === "inactive" && role.is_active) return false;
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
  // TASK-0293: 역할 아이콘 이미지(설정 시) 또는 role_key 시드 Identicon (이니셜 텍스트 폐기).
  applyAvatar(avatar, { url: merged.icon_url, seed: merged.key || "", initials: (merged.key || "NEW").slice(0, 2).toUpperCase() });
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
  renderRoleList();  // TASK-0302: pending 점(•) 즉시 반영
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
  renderRoleList();  // TASK-0302: pending 점(•)/삭제대기 표시 즉시 반영
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
  // TASK-0293: 역할 아이콘 이미지 또는 role_key 시드 Identicon.
  applyAvatar(avatar, { url: merged.icon_url, seed: merged.key || "", initials: (merged.key || "NE").slice(0, 2).toUpperCase() });
  // 관리자(console.manage + role.update)면 역할 아이콘 변경/제거 — 제품 아이콘과 동일 ✎ 오버레이 패턴.
  //   신규(미저장) 역할은 role_id 가 없어 업로드 불가 → 먼저 저장 후 아이콘 설정.
  let avatarNode = avatar;
  let iconRemoveBtn = null;
  if (!merged._isNew && can("console.manage") && can("role.update")) {
    const avatarWrap = document.createElement("div");
    avatarWrap.className = "profile-avatar-edit";
    const fileInput = document.createElement("input");
    fileInput.type = "file"; fileInput.accept = "image/png,image/jpeg,image/webp"; fileInput.hidden = true;
    const changeBtn = document.createElement("button");
    changeBtn.type = "button"; changeBtn.className = "profile-avatar-change"; changeBtn.textContent = "✎";
    changeBtn.title = "역할 아이콘 변경"; changeBtn.setAttribute("aria-label", "역할 아이콘 변경");
    changeBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      if (f.size > 5 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 5MB).", true); fileInput.value = ""; return; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await apiFetch(`/api/admin/roles/${Number(merged.id)}/icon`, { method: "PUT", body: fd });
        const baseRole = adminState.roles.find((rr) => Number(rr.id) === Number(merged.id));
        if (baseRole) baseRole.icon_url = r.icon_url || null;
        renderRoleDetail();
        renderRoleList();
        showToast("역할 아이콘을 변경했어요.");
      } catch (err) { showToast(err.message || "아이콘 변경 실패", true); }
      finally { fileInput.value = ""; }
    });
    avatarWrap.append(avatar, changeBtn, fileInput);
    avatarNode = avatarWrap;
    if (merged.icon_url) {
      iconRemoveBtn = document.createElement("button");
      iconRemoveBtn.type = "button"; iconRemoveBtn.className = "profile-avatar-remove"; iconRemoveBtn.textContent = "아이콘 제거";
      iconRemoveBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/admin/roles/${Number(merged.id)}/icon`, { method: "DELETE" });
          const baseRole = adminState.roles.find((rr) => Number(rr.id) === Number(merged.id));
          if (baseRole) baseRole.icon_url = null;
          renderRoleDetail();
          renderRoleList();
          showToast("역할 아이콘을 제거했어요.");
        } catch (err) { showToast(err.message || "아이콘 제거 실패", true); }
      });
    }
  }
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
  if (iconRemoveBtn) idText.appendChild(iconRemoveBtn);
  idBlock.append(avatarNode, idText);

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
  // TASK-0300: 본인 보유 권한만 표시·부여. 미보유 권한은 숨김 처리됨을 알리는 안내.
  const permHint = document.createElement("div");
  permHint.className = "admin-detail-hint";
  permHint.textContent = "본인이 보유한 권한만 표시·부여할 수 있습니다.";
  permSection.appendChild(permHint);
  // TASK-0300: 편집 주체(admin)가 보유한 권한 code 집합 — 역할 권한 grid 숨김 필터의 상한.
  const _selfAllowedRole = new Set(
    Object.entries(adminState.me?.permissions || {})
      .filter(([, granted]) => granted)
      .map(([code]) => code)
  );
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
      const renderedStatic = new Set(
        Array.from(permWrap.querySelectorAll("input[type='checkbox']")).map((input) => input.value)
      );
      // TASK-0303: 보존 대상(dynamic product.access.* + 숨긴 권한)은 렌더 시점 merged 스냅샷이 아니라
      //   라이브 mergedRole(pending 오버레이) 에서 읽어야 한다. 정적 권한 체크박스를 토글하기 전에
      //   제품 접근 카드를 켰다면 그 pending 이 merged 스냅샷엔 없어, 여기서 정적 변경 시 union 에서
      //   누락→제품 토글이 사라진다(정적↔제품 상호 클로버). 라이브로 읽어 양쪽 편집을 보존한다.
      const _liveRole = mergedRole(adminState.selectedRoleId);
      const _liveCodes = (_liveRole && Array.isArray(_liveRole.permission_codes))
        ? _liveRole.permission_codes : (merged.permission_codes || []);
      const existingDynamic = _liveCodes.filter((c) =>
        String(c).startsWith("product.access.")
      );
      // TASK-0300: grid 에 렌더되지 않은(본인 미보유라 숨긴) 기존 역할 권한은 보존한다 —
      //   숨긴 권한이 payload 에서 누락돼 제거되는 것 방지. 백엔드도 merge 하지만 pending 정합용.
      const preservedHidden = _liveCodes.filter(
        (c) => !renderedStatic.has(c) && !String(c).startsWith("product.access.")
      );
      const codes = Array.from(new Set([...checkedStatic, ...existingDynamic, ...preservedHidden]));
      setRolePending(adminState.selectedRoleId, { permission_codes: codes });
      renderRoleList();
    },
    { excludeDynamic: true, allowedCodes: _selfAllowedRole }
  );
  permSection.appendChild(permWrap);
  paneEl.appendChild(permSection);

  // TASK-0053 Phase B/C + 사용자 follow-up (2026-05-07): 제품별 접근 + role-scope system prompt 카드를
  // 권한 grid 의 제품 접근 그룹 details 안으로 이전. 사용자가 그룹을 collapse 하면 카드도 함께 접힘.
  // TASK-0288: 제품 접근 카드는 'product_access'(제품 사용) 그룹으로 이전 — 관리 콘솔 제품 관리와 분리.
  if (!merged._isNew) {
    const roleProductGroup = permWrap.querySelector('details[data-perm-group="product_access"]');
    const productCards = buildRoleProductCardList(
      merged,
      disabledBase || !can("role.permission.manage"),
      { embed: Boolean(roleProductGroup), allowedCodes: _selfAllowedRole },
    );
    if (roleProductGroup) {
      roleProductGroup.appendChild(productCards);
      // TASK-0303: 카드는 grid 렌더(_updateCheckboxGroupSummary 1차 실행) *이후* 임베드되므로
      //   배지가 "0/0" 으로 고정됐었다. 임베드 직후 다시 집계해 실제 N/M(부여 제품/전체)을 표시하고,
      //   부여가 있으면 그룹을 펼친다(다른 그룹과 동일 동작).
      _updateCheckboxGroupSummary(roleProductGroup);
      const _granted = roleProductGroup.querySelectorAll("input[type='checkbox']:checked").length;
      if (_granted > 0) roleProductGroup.open = true;
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
  // TASK-0291: 계정 탭 배지는 활성 계정만 집계 (비활성·삭제 대상은 목록 필터에서 확인 가능).
  // active 정의는 filteredAccounts() 의 'active' 분기와 동일: is_active && !deleted_at.
  const activeAccountCount = adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length;
  $("tabCountAccounts").textContent = `${activeAccountCount}`;
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
  const dsDirty = datasourceDirtyProductCount();
  if (dsDirty) detail.push(`데이터소스 바인딩 ${dsDirty}`);
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
  // TASK-0239: datasource 바인딩 — desired≠baseline 인 제품만(실제 변경).
  const datasourceEntries = Array.from(adminState.pending.productDatasources.entries())
    .filter(([, e]) => e && !_dsBindEqual(e.baseline, e.desired));

  if (
    !accountEntries.length
    && !roleEntries.length
    && !newRoleEntries.length
    && !productMetaEntries.length
    && !productDbEntries.length
    && !datasourceEntries.length
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

  // Product metadata patches / deletes
  for (const [productId, patch] of productMetaEntries) {
    try {
      if (patch._delete) {
        // TASK-0302: bulk "삭제 pending" 가 _delete 플래그만 스테이징했으나 이 루프가 _delete 를
        //   처리하지 않아 빈 body → 요청 0건 → pending 만 조용히 비워짐(삭제가 전혀 안 됨).
        //   account/role 루프와 동일하게 DELETE 를 호출한다(단일 삭제=제품 상세 '삭제' 버튼과 동일
        //   엔드포인트; 참조 대화는 서버가 '차단'으로 전환). 혼합 편집(다른 제품 메타 수정 + 다중
        //   삭제) 시 '마지막으로 수정한 제품만 적용' 처럼 보이던 증상의 근본 원인.
        await apiFetch(`/api/admin/products/${Number(productId)}`, { method: "DELETE" });
      } else {
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
      }
      adminState.pending.productMeta.delete(productId);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "product_meta", id: productId, error });
    }
  }

  // TASK-0239: datasource 바인딩 변경(추가/제거/기본지정)을 baseline↔desired diff 로 일괄 적용.
  //  순서: ① 제거(제거 시 서버가 그 datasource 의 접근DB 도 삭제) → ② 추가 → ③ primary 재지정.
  //  제품 DB(productDatabases) 적용보다 **먼저** 수행해야 추가된 바인딩에 DB 를 PUT 할 수 있고,
  //  제거된 바인딩의 DB draft 는 아래에서 skip 한다(서버가 이미 삭제 — 재생성 방지).
  const _removedDsByProduct = new Map();  // productId -> Set(removed lower keys)
  for (const [productId, e] of datasourceEntries) {
    const pid = Number(productId);
    const baseKeys = new Set(_dsBindNorm(e.baseline).map((d) => d.key));
    const desiredKeys = new Set(_dsBindNorm(e.desired).map((d) => d.key));
    const toRemove = [...baseKeys].filter((k) => !desiredKeys.has(k));
    const toAdd = [...desiredKeys].filter((k) => !baseKeys.has(k));
    const desiredPrimary = (_dsBindNorm(e.desired).find((d) => d.is_primary) || {}).key || null;
    const removedSet = new Set();
    let pidFailed = false;
    try {
      // ① 제거
      for (const k of toRemove) {
        await apiFetch(`/api/admin/products/${pid}/datasources/${encodeURIComponent(k)}`, { method: "DELETE" });
        removedSet.add(k);
      }
      // ② 추가 (첫 바인딩이면 백엔드가 자동 primary; primary 의도는 ③에서 확정)
      const hadAnyAfterRemove = [...baseKeys].some((k) => !removedSet.has(k));
      let firstAdd = !hadAnyAfterRemove;
      for (const k of toAdd) {
        if (firstAdd) {
          // 바인딩이 0개였다면 첫 추가는 PATCH(레거시 단일 경로와 정합 — WebProducts.DatasourceKey 포인터도 세팅).
          await apiFetch(`/api/admin/products/${pid}/datasource`, {
            method: "PATCH", body: JSON.stringify({ datasource_key: k, datasource_database: null }),
          });
          firstAdd = false;
        } else {
          await apiFetch(`/api/admin/products/${pid}/datasources`, {
            method: "POST", body: JSON.stringify({ datasource_key: k, is_primary: false }),
          });
        }
      }
      // ③ primary 재지정 — desired primary 가 이미 primary 가 아니면 명시 지정.
      if (desiredPrimary) {
        const basePrimary = (_dsBindNorm(e.baseline).find((d) => d.is_primary) || {}).key || null;
        const addedPrimary = toAdd.includes(desiredPrimary) && !hadAnyAfterRemove && desiredPrimary === toAdd[0];
        if (desiredPrimary !== basePrimary || removedSet.size) {
          // 추가 직후 자동 primary 였던 첫 케이스가 아니면(또는 제거로 primary 가 바뀌었으면) 명시 지정.
          if (!addedPrimary) {
            await apiFetch(`/api/admin/products/${pid}/datasources`, {
              method: "POST", body: JSON.stringify({ datasource_key: desiredPrimary, is_primary: true }),
            });
          }
        }
      }
      adminState.pending.productDatasources.delete(pid);
      ok += 1;
    } catch (error) {
      pidFailed = true;
      failures.push({ kind: "product_datasource", id: pid, error });
    }
    if (removedSet.size) _removedDsByProduct.set(pid, removedSet);
    if (pidFailed) { /* 부분 실패 — loadAdminData 가 서버 정본으로 재동기화 */ }
  }

  // Product databases (full replace per (product, datasource))
  for (const [pkey, draft] of productDbEntries) {
    // TASK-0228 (1:N): 복합 키 `productId::dsKey` 파싱. 레거시(단일 id) 키도 호환.
    const _ps = String(pkey).split("::");
    const productId = Number(_ps[0]);
    const dsKey = (draft && draft._dsKey != null) ? String(draft._dsKey) : (_ps.length > 1 ? _ps[1] : "");
    // TASK-0239: 방금 제거된 datasource 의 접근DB draft 는 skip — 서버가 바인딩과 함께 삭제했으므로
    //  재PUT 하면 고아 행을 되살린다(혹은 미존재 바인딩 PUT 으로 오류). pending 만 정리.
    const _rm = _removedDsByProduct.get(productId);
    if (_rm && dsKey && _rm.has(String(dsKey).trim().toLowerCase())) {
      adminState.pending.productDatabases.delete(pkey);
      adminState.productDbDraft.delete(`${productId}::${String(dsKey).trim().toLowerCase()}`);
      continue;
    }
    try {
      // TASK-20260618T044318 (B4): 수동 저장 body 는 manual 행만 — 규칙(rule) 자동 동기화 행은 제외해
      //   백엔드가 보존하도록 한다(manual PUT 이 rule 행을 manual 로 승격/덮어쓰지 않게).
      const body = { databases: Array.isArray(draft)
        ? draft.filter((d) => String((d && d.source) || "manual") !== "rule").map((d) => ({ ...d }))
        : [] };
      // datasource 차원이 지정됐으면 함께 전송(백엔드가 그 datasource 행만 교체). 빈 문자열은 레거시 단일.
      if (dsKey) body.datasource_key = dsKey;
      await apiFetch(`/api/admin/products/${productId}/databases`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      adminState.pending.productDatabases.delete(pkey);
      adminState.productDbDraft.delete(`${productId}::${dsKey}`);
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
  adminState.pending.productDatasources.clear();
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
  // TASK-0219: 미전달(구버전 백엔드)이면 기본 활성으로 간주(secure-by-default 안내).
  adminState.datasourcesSsrfPrivateGuard = !datasourcesPayload || datasourcesPayload.ssrf_private_guard_enabled !== false;
  adminState.datasources = Array.isArray(datasourcesPayload && datasourcesPayload.datasources) ? datasourcesPayload.datasources : [];
  // conn-health-monitor: 백엔드가 첨부한 사전계산 연결상태를 캐시에 반영 → 배지가 즉시 표시
  //  (per-item /test lazy probe + 세마포어 대기 폐기). conn-tristate 3단계 매핑:
  //  healthy→ok(초록) / unstable→unstable(빨강, 느림/간헐) / down→down(회색, 끊김) / unknown→확인중.
  adminState.datasources.forEach((ds) => {
    const k = String(ds && ds.key || "").trim().toLowerCase();
    const cs = ds && ds.conn_status;
    const ih = ds && ds.insight_health;  // TASK-0255 R2: insight 스캔 관점(PG 정본)
    if (!k) return;
    if (ih) adminState.datasourceInsightHealth.set(k, ih);
    else adminState.datasourceInsightHealth.delete(k);
    if (!cs || !cs.status) return;
    if (cs.status === "healthy") {
      adminState.datasourceConnStatus.set(k, { state: "ok", elapsed_ms: cs.elapsed_ms });
    } else if (cs.status === "unstable") {
      adminState.datasourceConnStatus.set(k, { state: "unstable", elapsed_ms: cs.elapsed_ms, error: "연결 불안정" });
    } else if (cs.status === "down") {
      adminState.datasourceConnStatus.set(k, { state: "down", error: "연결 끊김" });
    } else if (ih && ih.scan_outcome === "circuit_open") {
      // web live 모니터는 unknown 이나 insight 가 최근 circuit-open 관측 — 연결 불안정으로 표시.
      adminState.datasourceConnStatus.set(k, { state: "unstable", error: "연결 불안정(insight)" });
    } else {
      // unknown — 아직 probe 전. 기존 캐시가 있으면 유지, 없으면 미설정(배지=확인 중).
      if (!adminState.datasourceConnStatus.has(k)) adminState.datasourceConnStatus.delete(k);
    }
  });
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
  // TASK-0239: 삭제된 제품의 datasource 바인딩 pending GC.
  Array.from(adminState.pending.productDatasources.keys()).forEach((id) => {
    if (!productIds.has(Number(id))) adminState.pending.productDatasources.delete(id);
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
  // TASK-0223: 분석 완료율은 라이브 DB 조회라 page 렌더를 막지 않게 fire-and-forget 으로 뒤따라 채운다.
  loadProductInsightCoverage();
}

/* ── Products pane ───────────────────────────────────────────────────── */

// TASK-0253: 특정 제품의 완료율이 로딩 중인지. 배지/상세가 "측정 중…" 표시 여부 판정에 쓴다.
function _isProductCoverageLoading(productId) {
  return adminState.productCoverageLoadingIds.has(Number(productId));
}

// TASK-0253 (REV MAJOR-2): 완료율 단건 fetch 동시성 cap. 제품별 병렬 fan-out 이 head-of-line 을
//  없애지만, 제품 수가 많으면 N개 동시 요청이 백엔드 공용 스레드풀(anyio 기본 40)을 한꺼번에
//  점유해 한 레이어 위에서 다시 직렬화될 수 있다. datasource probe 의 _DS_CONN_MAX(4)와 동형으로
//  클라이언트에서 동시 요청 수를 제한한다(초과분은 큐 대기 — 그동안 배지는 '측정 중'). 작은 풀
//  규모에선 사실상 전부 동시, 큰 규모에선 백엔드 보호.
const _COV_FETCH_MAX = 4;
// items 를 limit 동시성으로 worker(item) 실행. 각 item 의 결과/예외는 worker 내부에서 처리한다고 가정.
async function _runWithConcurrency(items, limit, worker) {
  const queue = items.slice();
  const runners = new Array(Math.min(limit, queue.length)).fill(0).map(async () => {
    while (queue.length) {
      const item = queue.shift();
      await worker(item);
    }
  });
  await Promise.all(runners);
}

// TASK-0223: 제품별 insight-worker 분석 완료율 로드 (목록/상세 배지·breakdown).
// TASK-0253: head-of-line 제거 — 전체를 한 번에 받는 대신 **제품마다 단건 API 를 병렬 호출**하고,
//  각 제품이 끝나는 즉시 그 제품 배지만 갱신한다. productId 지정 시 단건만, 미지정 시 전 제품 fan-out.
//  백엔드 admin_products_insight_coverage 는 일반 def 핸들러라 Starlette 스레드풀에서 자동 병렬 처리되어
//  단건 N개 동시 요청이 가장 느린 1건 시간 안에 끝난다(직렬 합산 아님). 동시성은 _COV_FETCH_MAX 로 cap.
//  ※ 대규모(제품 수십~수백) 확장 방향은 feature-0003 REPORT.md(TASK-0253) 참조 — background 사전계산
//    worker + Redis 공유 캐시.
async function loadProductInsightCoverage({ refresh = false, productId = null } = {}) {
  if (!can("console.access")) return;
  // TASK-0242: 완료율 새로고침 시 DB insight 캐시도 무효화 → 재렌더(_ensureDbInsights)가 최신 파악내용 재조회.
  if (refresh) {
    const _pfx = productId ? `${Number(productId)}::` : null;
    Array.from(adminState.productDbInsights.keys()).forEach((k) => {
      if (!_pfx || String(k).startsWith(_pfx)) adminState.productDbInsights.delete(k);
    });
  }

  // 로드 대상 제품 id 목록 결정: 단건 지정이면 그 하나, 아니면 현재 알고 있는 전 제품.
  let targetIds;
  if (productId != null) {
    targetIds = [Number(productId)];
  } else {
    targetIds = (adminState.products || []).map((p) => Number(p.id));
  }
  if (!targetIds.length) return;

  // 각 제품을 '측정 중'으로 마킹 후 즉시 1회 렌더(빠른 제품이 먼저 채워질 무대를 깐다).
  targetIds.forEach((pid) => adminState.productCoverageLoadingIds.add(pid));
  renderProductList();
  if (adminState.selectedProductId) renderProductDetail();

  // 한 제품의 완료율을 단건 API 로 가져와 settle. 끝나는 즉시 그 제품만 갱신(head-of-line 없음).
  const _loadOne = async (pid) => {
    try {
      const qs = ["product_id=" + encodeURIComponent(pid)];
      if (refresh) qs.push("refresh=1");
      const url = "/api/admin/products/insight-coverage?" + qs.join("&");
      const payload = await apiFetch(url).catch((error) => {
        if (error.status === 403) return { coverage: {} };
        throw error;
      });
      const cov = (payload && payload.coverage) || {};
      // 단건이라도 응답은 { coverage: { "<pid>": {...} } } 형태 — 받은 키를 그대로 반영.
      Object.keys(cov).forEach((k) => adminState.productCoverage.set(Number(k), cov[k]));
    } catch (error) {
      // 측정 실패는 치명적이지 않음 — 콘솔만 남기고 UI 는 "측정 불가" fallback.
      console.warn(`insight coverage 로드 실패 (product ${pid}):`, error);
    } finally {
      adminState.productCoverageLoadingIds.delete(pid);
      // 끝난 제품만 즉시 반영 — 목록 배지 + (선택 중이면) 상세.
      renderProductList();
      if (Number(adminState.selectedProductId) === Number(pid)) renderProductDetail();
    }
  };

  // 동시성 cap 하 병렬 발사 — 각 제품이 끝나는 즉시 그 배지만 settle(head-of-line 없음). 일부 실패해도 전체는 진행.
  await _runWithConcurrency(targetIds, _COV_FETCH_MAX, _loadOne);
}

// TASK-0242: 제품의 한 datasource scope 에서 DB(schema)별 insight 파악 내용 로드.
//  key = `${pid}::${dsKey}`(dsKey 미지정 = primary/legacy). 캐시 + 진행 중 중복요청 차단.
function _dbInsightsKey(pid, dsKey) {
  return `${Number(pid)}::${String(dsKey || "").trim().toLowerCase()}`;
}
async function loadProductDbInsights({ productId, datasourceKey = "", refresh = false, onDone = null } = {}) {
  if (!can("console.access")) { if (onDone) onDone(); return; }
  const key = _dbInsightsKey(productId, datasourceKey);
  if (!refresh && adminState.productDbInsights.has(key)) { if (onDone) onDone(); return; }
  if (adminState.productDbInsightsLoading.has(key)) return;  // 진행 중 — 중복요청 차단
  adminState.productDbInsightsLoading.add(key);
  try {
    const dsk = String(datasourceKey || "").trim();
    const url = `/api/admin/products/${encodeURIComponent(productId)}/db-insights`
      + (dsk ? `?datasource=${encodeURIComponent(dsk)}` : "");
    const payload = await apiFetch(url).catch((error) => {
      if (error.status === 403 || error.status === 400) return { ok: false, by_db: {}, worker: {} };
      throw error;
    });
    adminState.productDbInsights.set(key, payload || { ok: false, by_db: {}, worker: {} });
  } catch (error) {
    // 파악 내용 로드 실패는 비치명적 — 콘솔만 남기고 "역할 미파악" fallback.
    console.warn("db insight 로드 실패:", error);
    adminState.productDbInsights.set(key, { ok: false, by_db: {}, worker: {} });
  } finally {
    adminState.productDbInsightsLoading.delete(key);
    if (onDone) onDone();
  }
}

// 완료율 → 색상 등급 (시각 위계: 낮음=경고, 높음=정상).
function _coverageTone(pct) {
  if (pct === null || pct === undefined) return "muted";
  if (pct >= 80) return "ok";
  if (pct >= 40) return "warn";
  return "low";
}

// 목록 row 용 컴팩트 배지 element 생성.
function buildCoverageBadge(productId) {
  const span = document.createElement("span");
  span.className = "cov-badge";
  const cov = adminState.productCoverage.get(Number(productId));
  if (cov === undefined) {
    span.classList.add("cov-muted");
    span.textContent = _isProductCoverageLoading(productId) ? "분석 측정 중…" : "분석 —";
    return span;
  }
  if (!cov.measurable) {
    span.classList.add("cov-muted");
    span.textContent = "분석 측정 불가";
    span.title = cov.reason || "";
    return span;
  }
  if (cov.total_objects === 0) {
    span.classList.add("cov-muted");
    const hasConnFail = (cov.per_db || []).some((d) => d.connected === false);
    span.textContent = hasConnFail ? "분석 연결 불가" : "분석 대상 없음";
    span.title = cov.reason || (hasConnFail ? "접근 가능 DB 연결 실패(권한/도달)" : "접근 가능 데이터베이스 없음");
    return span;
  }
  const pct = cov.pct;
  span.classList.add(`cov-${_coverageTone(pct)}`);
  span.textContent = `분석 ${pct}%`;
  const failN = (cov.per_db || []).filter((d) => d.connected === false).length;
  span.title = `${cov.analyzed_objects} / ${cov.total_objects} 객체 분석 완료`
    + (failN ? ` · 연결 불가 DB ${failN}개` : "");
  return span;
}

// 제품 상세 — 접근 가능 DB 섹션의 insight 분석 완료율 "요약 헤더"(제목 + 전체 % 배지
// + 새로고침 + 전체 진행 바). per-DB 진척은 통합 DB 리스트(redrawChips)의 각 행으로 흡수됐다.
function buildProductCoverageDetail(product) {
  const wrap = document.createElement("div");
  wrap.className = "cov-detail";

  const head = document.createElement("div");
  head.className = "cov-detail-head";
  const title = document.createElement("span");
  title.className = "cov-detail-title";
  title.textContent = "insight 분석 완료율";
  head.appendChild(title);

  const cov = adminState.productCoverage.get(Number(product.id));
  const summaryChip = document.createElement("span");
  summaryChip.className = "cov-badge";
  if (cov === undefined) {
    summaryChip.classList.add("cov-muted");
    summaryChip.textContent = _isProductCoverageLoading(product.id) ? "측정 중…" : "—";
  } else if (!cov.measurable) {
    summaryChip.classList.add("cov-muted");
    summaryChip.textContent = "측정 불가";
  } else if (cov.total_objects === 0) {
    summaryChip.classList.add("cov-muted");
    summaryChip.textContent = (cov.per_db || []).some((d) => d.connected === false) ? "연결 불가" : "대상 없음";
  } else {
    summaryChip.classList.add(`cov-${_coverageTone(cov.pct)}`);
    summaryChip.textContent = `${cov.pct}%`;
  }
  head.appendChild(summaryChip);

  const refreshBtn = document.createElement("button");
  refreshBtn.type = "button";
  refreshBtn.className = "tool-btn cov-refresh";
  refreshBtn.textContent = "새로고침";
  refreshBtn.disabled = _isProductCoverageLoading(product.id);
  refreshBtn.addEventListener("click", () => {
    loadProductInsightCoverage({ refresh: true, productId: product.id });
  });
  head.appendChild(refreshBtn);
  wrap.appendChild(head);

  if (cov === undefined) {
    const p = document.createElement("div");
    p.className = "admin-detail-hint";
    p.textContent = _isProductCoverageLoading(product.id) ? "분석 완료율 측정 중…" : "분석 완료율 정보가 아직 없습니다.";
    wrap.appendChild(p);
    return wrap;
  }
  if (!cov.measurable) {
    const p = document.createElement("div");
    p.className = "admin-detail-hint cov-reason";
    p.textContent = `측정 불가: ${cov.reason || "데이터소스 연결/해석 실패"}`;
    wrap.appendChild(p);
    return wrap;
  }
  if (cov.total_objects > 0) {
    // 전체 진행 바 + 객체 수 (개별 DB 진척은 아래 통합 리스트의 각 행에서)
    const overall = document.createElement("div");
    overall.className = "cov-bar-row";
    const bar = document.createElement("div");
    bar.className = `cov-bar cov-${_coverageTone(cov.pct)}`;
    const fill = document.createElement("div");
    fill.className = "cov-bar-fill";
    fill.style.width = `${Math.max(0, Math.min(100, cov.pct || 0))}%`;
    bar.appendChild(fill);
    const barLabel = document.createElement("span");
    barLabel.className = "cov-bar-label";
    barLabel.textContent = `${cov.analyzed_objects} / ${cov.total_objects} 객체 (DB + 테이블)`;
    overall.append(bar, barLabel);
    wrap.appendChild(overall);
  } else {
    // 측정 가능한 DB 0개(전부 연결 실패 등) — 진행바 생략, 사유만 표시(개별 상태는 아래 리스트).
    const p = document.createElement("div");
    p.className = "admin-detail-hint cov-reason";
    p.textContent = cov.reason || "접근 가능 데이터베이스에 연결할 수 없습니다(권한/도달 확인).";
    wrap.appendChild(p);
  }

  if (cov.engine === "mssql") {
    const note = document.createElement("div");
    note.className = "admin-detail-hint cov-engine-note";
    note.textContent = "MSSQL: RO 로그인에 GRANT 되지 않았거나 도달 불가한 DB는 '연결 불가'로 표시되며 완료율 집계에서 제외됩니다. (insight 스코프는 데이터소스 엔드포인트 단위)";
    wrap.appendChild(note);
  }
  return wrap;
}

// 통합 DB 리스트의 한 행에 붙일 "분석 진척" 요소(마이크로바 + 통계 + 상태칩)를 만든다.
// covRow = 백엔드 per_db 항목(없으면 null=측정 대기). 사용자 등록 DB chip 과 1:1.
function buildDbCoverageCells(covRow, measuring) {
  const frag = document.createDocumentFragment();
  const bar = document.createElement("span");
  bar.className = "cov-microbar";
  const fill = document.createElement("span");
  fill.className = "cov-microbar-fill";
  bar.appendChild(fill);
  const stat = document.createElement("span");
  stat.className = "cov-db-stat";
  const status = document.createElement("span");
  status.className = "cov-db-status";

  if (!covRow) {
    // per_db 에 아직 없음 — 측정 전/대기.
    bar.classList.add("is-pending");
    stat.textContent = "—";
    status.classList.add("cov-db-status-muted");
    status.textContent = measuring ? "측정 중" : "측정 대기";
    frag.append(bar, stat, status);
    return frag;
  }
  if (covRow.connected === false) {
    // 연결 불가 — 점선 트랙, 통계 없음.
    bar.classList.add("is-offline");
    stat.textContent = "—";
    status.classList.add("cov-db-status-low");
    status.textContent = "연결 불가";
    status.title = covRow.note || "연결 불가(RO 권한/도달 확인)";
    frag.append(bar, stat, status);
    return frag;
  }
  const tt = covRow.tables_total || 0;
  const ta = covRow.tables_analyzed || 0;
  const tpct = tt > 0 ? Math.round((100 * ta) / tt) : (covRow.schema_analyzed ? 100 : 0);
  const tone = _coverageTone(tt === 0 && !covRow.schema_analyzed ? null : tpct);
  fill.classList.add(`cov-${tone}`);
  fill.style.width = `${Math.max(0, Math.min(100, tpct))}%`;
  stat.textContent = `${ta}/${tt}`;
  status.classList.add(`cov-db-status-${tone === "ok" ? "ok" : (tone === "muted" ? "muted" : "warn")}`);
  if (tt === 0 && !covRow.schema_analyzed) {
    status.textContent = "대상 없음";
  } else {
    status.textContent = covRow.schema_analyzed ? "DB✓" : "DB✗";
  }
  frag.append(bar, stat, status);
  return frag;
}

// TASK-0242: 등록 DB 행의 "insight-worker 설명" 한 줄 셀. insRow = by_db[<db_lower>] (없으면 null).
//  파악된 역할/도메인을 한 줄로(overflow ellipsis), 전문은 hover title(detail_text)로.
function buildDbRoleCell(insRow, { loading = false } = {}) {
  const el = document.createElement("span");
  el.className = "cov-db-role";
  if (insRow && insRow.description) {
    el.textContent = insRow.description;
    el.title = insRow.detail_text || insRow.description;
  } else if (loading) {
    el.classList.add("cov-db-role-muted");
    el.textContent = "역할 파악 중…";
  } else {
    el.classList.add("cov-db-role-muted");
    el.textContent = "역할 미파악";
    el.title = "insight-worker 가 아직 이 DB 의 역할을 파악하지 않았습니다.";
  }
  return el;
}

// TASK-0242: 추가 picker 항목의 도메인 힌트 + 분석 상태(미분석/분석중/분석됨) 메타.
//  분석됨 = rag_objects 보유(analyzed_objects>0). 분석중 = 보유 0 + insight-worker 활성(heartbeat fresh). 그 외 미분석.
function buildPickerInsightMeta(insRow, worker) {
  const frag = document.createDocumentFragment();
  const analyzed = !!(insRow && (insRow.analyzed_objects || 0) > 0);
  const alive = !!(worker && worker.alive);
  const dom = insRow && insRow.domain;
  if (dom) {
    const d = document.createElement("span");
    d.className = "admin-db-picker-domain";
    d.textContent = dom;
    d.title = (insRow && insRow.description) || dom;
    frag.appendChild(d);
  }
  const st = document.createElement("span");
  st.className = "admin-db-picker-status";
  if (analyzed) {
    st.classList.add("is-done");
    st.textContent = "분석됨";
    st.title = (insRow && insRow.description) || `분석 객체 ${insRow.analyzed_objects}개`;
  } else if (alive) {
    st.classList.add("is-running");
    st.textContent = "분석중";
    st.title = "insight-worker 가 활성 상태입니다. 추가하면 다음 cycle 에 분석됩니다.";
  } else {
    st.classList.add("is-none");
    st.textContent = "미분석";
    st.title = "아직 분석된 내용이 없습니다. 추가하면 insight-worker 가 분석합니다.";
  }
  frag.appendChild(st);
  return frag;
}

// 시스템/메타데이터 고정 DB 묶음 칩(단일). 개별 DB 이름은 hover/focus 툴팁 + title + aria-label.
// lockedChips = [{name, present}]. count 0 이면 null 반환(렌더 생략).
function buildSystemDbChip(lockedChips) {
  const chips = (lockedChips || []).filter((c) => c && c.name);
  if (!chips.length) return null;
  const names = chips.map((c) => c.name);
  const wrap = document.createElement("div");
  wrap.className = "sysdb-chip";
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "group");

  const label = document.createElement("span");
  label.className = "sysdb-chip-label";
  label.textContent = `시스템 DB ${chips.length}개`;
  const tag = document.createElement("small");
  tag.className = "sysdb-chip-tag";
  tag.textContent = "고정";
  wrap.append(label, tag);

  // 네이티브 title (마우스 hover) + aria-label (스크린리더).
  wrap.title = "고정 시스템 데이터베이스 (분석 대상 아님)\n" + names.join("\n");
  wrap.setAttribute(
    "aria-label",
    `고정 시스템 데이터베이스 ${chips.length}개: ${names.join(", ")}. 분석 대상이 아닙니다.`,
  );

  // 커스텀 툴팁 카드 (hover + 키보드 focus 둘 다 노출 — 접근성).
  const tip = document.createElement("div");
  tip.className = "sysdb-chip-tip";
  const tipTitle = document.createElement("div");
  tipTitle.className = "sysdb-chip-tip-title";
  tipTitle.textContent = "고정 시스템 DB · 분석 대상 아님";
  tip.appendChild(tipTitle);
  const ul = document.createElement("ul");
  ul.className = "sysdb-chip-tip-list";
  chips.forEach((c) => {
    const li = document.createElement("li");
    li.textContent = c.present === false ? `${c.name} (미감지)` : c.name;
    ul.appendChild(li);
  });
  tip.appendChild(ul);
  wrap.appendChild(tip);
  return wrap;
}

// TASK-0230: 접근 가능 DB 단위 insight 분석 초기화 (파괴적 — dry-run 미리보기 + typed-confirm).
// 1) dry-run 으로 삭제 대상 건수 조회 → 2) DB 이름 typed-confirm → 3) 실제 삭제 → 완료율 새로고침.
async function resetProductDbInsight(product, db) {
  if (!can("insight.reset")) {
    showToast("insight 분석 초기화 권한이 없습니다.", true);
    return;
  }
  const pid = Number(product.id);
  const url = `/api/admin/products/${encodeURIComponent(pid)}/insight-reset`;
  // 1) dry-run 미리보기
  let preview;
  try {
    preview = await apiFetch(url, {
      method: "POST",
      body: JSON.stringify({ db, dry_run: true }),
    });
  } catch (error) {
    showToast(`삭제 대상 조회 실패: ${error.message || error}`, true);
    return;
  }
  const td = (preview && preview.to_delete) || {};
  const total = Number(td.total) || 0;
  if (total === 0) {
    showToast(`'${db}' 에 삭제할 insight 분석 데이터가 없습니다.`, false);
    return;
  }
  // 2) typed-confirm (DB 이름 입력) — audit.purge 패턴 답습.
  const detail = `fact ${td.fact_entries || 0} · rag문서 ${td.rag_documents || 0} · rag객체 ${td.rag_objects || 0} · 상태키 ${td.kv || 0}`;
  const typed = window.prompt(
    `'${db}' 의 insight 분석 ${total}건(${detail})을 삭제합니다.\n` +
    `같은 데이터소스·DB를 공유하는 다른 제품의 완료율도 함께 0이 됩니다.\n` +
    `삭제 후 insight-worker 가 다음 cycle 에 자동 재분석합니다.\n\n` +
    `확인하려면 데이터베이스 이름(${db})을 그대로 입력하세요.`,
  );
  if (typed === null) return; // 취소
  if (String(typed).trim() !== String(db)) {
    showToast("입력이 일치하지 않아 취소했습니다.", true);
    return;
  }
  // 3) 실제 삭제
  try {
    const res = await apiFetch(url, {
      method: "POST",
      body: JSON.stringify({ db, dry_run: false }),
    });
    const n = Number(res && res.total_deleted) || 0;
    showToast(`'${db}' insight 분석 ${n}건 초기화 완료. 다음 cycle 에 자동 재분석됩니다.`, false);
    // 완료율 즉시 새로고침 (캐시는 서버가 무효화함).
    loadProductInsightCoverage({ refresh: true, productId: pid });
  } catch (error) {
    showToast(`초기화 실패: ${error.message || error}`, true);
  }
}

function filteredProducts() {
  const q = (adminState.productSearch || "").toLowerCase().trim();
  return adminState.products.filter((p) => {
    // 계정 탭 filteredAccounts() 와 동형: 상태 필터 먼저, 그다음 검색어 매칭.
    if (adminState.productFilter === "active" && !p.is_active) return false;
    if (adminState.productFilter === "inactive" && p.is_active) return false;
    if (!q) return true;
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
    // TASK-0302: 제품 행도 계정/역할처럼 pending 변경/삭제대기 시각 표시(외부리뷰 MINOR — 이전엔 제품
    //   행에 pending 마커가 없어 bulk staging 후 renderProductList 재렌더가 무표시였다). productMeta pending 기준.
    const _pmPending = adminState.pending.productMeta.get(Number(p.id));
    if (_pmPending) {
      row.classList.add("has-pending");
      if (_pmPending._delete) row.classList.add("is-to-delete");
    }

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
    meta.className = "admin-list-row-main";
    // product-icon-chip 뒤틀림 수정: avatar 를 row 최상위(3열 grid 깨짐)가 아니라 meta 첫 줄에
    //   name 과 함께 가로 flex(admin-list-row-title)로 묶는다 — 계정 목록 행과 동형. row 는
    //   다시 [cb, meta] 2자식이라 grid `auto 1fr auto` 정상.
    const titleRow = document.createElement("div");
    titleRow.className = "admin-list-row-title";
    const avatar = document.createElement("span");
    avatar.className = "admin-avatar admin-avatar-sm";
    applyAvatar(avatar, { url: p.icon_url, seed: p.product_key || p.name || "", initials: (p.product_key || "P").slice(0, 2).toUpperCase() });
    const name = document.createElement("span");
    name.className = "admin-list-row-name";
    name.textContent = `(${p.product_key}) ${p.name}`;
    const pendingDot = document.createElement("span");  // TASK-0302: pending 변경 표시(계정/역할 행과 동형)
    pendingDot.className = "admin-pending-dot";
    pendingDot.title = "pending 변경 있음";
    pendingDot.textContent = _pmPending ? "•" : "";
    titleRow.append(avatar, name, pendingDot);
    const sub = document.createElement("div");
    sub.className = "admin-meta";
    const badges = [];
    if (p.is_default) badges.push("default");
    if (!p.is_active) badges.push("inactive");
    sub.textContent = [p.description || "—", ...badges].filter(Boolean).join(" · ");
    // TASK-0223: insight 분석 완료율 배지 (라이브 측정값이 비동기로 채워짐).
    const covLine = document.createElement("div");
    covLine.className = "admin-meta cov-line";
    covLine.appendChild(buildCoverageBadge(p.id));
    meta.append(titleRow, sub, covLine);
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
  // TASK-0302: pending 스테이징 후 목록 재렌더 — 선택 행의 pending 점(•)/상태를 즉시 반영
  //   (상세 편집 경로는 renderXList 를 호출하나 bulk 경로는 누락돼 "반영 안 된 듯" 보이던 불일치).
  renderProductList();
  if (adminState.selectedProductId) renderProductDetail();
}

function bulkProductDelete() {
  const count = adminState.productSelected.size;
  if (!confirmBulkAction({ entity: "products", action: "delete", count, danger: true })) return;
  // product 삭제는 catalog 영향이 큼 (Role/Account 권한 grid 도 의존). _delete 플래그를 pending 에
  //   스테이징하고 "모두 적용"(applyAllPending)이 DELETE /api/admin/products/{id} 로 일괄 실행한다
  //   (TASK-0302 — 이전엔 applyAllPending 이 _delete 를 무시해 삭제가 조용히 무효였다). default product 보호.
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
  renderProductList();
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
  const canReset = can("insight.reset");  // TASK-0230: insight 초기화 권한(admin 한정)

  // Header
  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  // TASK-0268 + profile-icon 정합: 제품 아이콘 이미지(설정 시) 또는 Identicon(product_key 시드).
  //   작업화면 프로필(applyAvatar/identiconSvg)과 동일 폴백 — 이니셜 텍스트가 아니라 결정론적 Identicon.
  applyAvatar(avatar, { url: product.icon_url, seed: product.product_key || product.name || "", initials: (product.product_key || "P").slice(0, 2).toUpperCase() });
  // TASK-0283: product.manage 면 아이콘 변경/제거 컨트롤.
  //   유저 프로필 아바타 편집(index.html .profile-avatar-edit)과 동일한 ✎ 오버레이 패턴으로 통일.
  //   기존 "아이콘"/"제거" 텍스트 pill 은 36px 아이콘 영역을 침범 → 폐기.
  let avatarNode = avatar;
  let removeBtn = null;
  if (canManage) {
    // .profile-avatar-edit: position:relative 래퍼 — ✎ 버튼을 아바타 우하단에 오버레이.
    const avatarWrap = document.createElement("div");
    avatarWrap.className = "profile-avatar-edit";
    const fileInput = document.createElement("input");
    fileInput.type = "file"; fileInput.accept = "image/png,image/jpeg,image/webp"; fileInput.hidden = true;
    const changeBtn = document.createElement("button");
    changeBtn.type = "button"; changeBtn.className = "profile-avatar-change"; changeBtn.textContent = "✎";
    changeBtn.title = "제품 아이콘 변경"; changeBtn.setAttribute("aria-label", "제품 아이콘 변경");
    changeBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      if (f.size > 5 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 5MB).", true); fileInput.value = ""; return; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await apiFetch(`/api/admin/products/${Number(product.id)}/icon`, { method: "PUT", body: fd });
        product.icon_url = r.icon_url || null;
        renderProductDetail();
        showToast("제품 아이콘을 변경했어요.");
      } catch (err) { showToast(err.message || "아이콘 변경 실패", true); }
      finally { fileInput.value = ""; }
    });
    avatarWrap.append(avatar, changeBtn, fileInput);
    avatarNode = avatarWrap;
    // 제거는 유저 프로필("사진 제거")과 동일하게 텍스트 링크(.profile-avatar-remove)로, idText 블록 하단에 둔다.
    if (product.icon_url) {
      removeBtn = document.createElement("button");
      removeBtn.type = "button"; removeBtn.className = "profile-avatar-remove"; removeBtn.textContent = "아이콘 제거";
      removeBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/admin/products/${Number(product.id)}/icon`, { method: "DELETE" });
          product.icon_url = null;
          renderProductDetail();
          showToast("제품 아이콘을 제거했어요.");
        } catch (err) { showToast(err.message || "아이콘 제거 실패", true); }
      });
    }
  }
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = `(${product.product_key}) ${product.name}`;
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
  if (removeBtn) idText.appendChild(removeBtn);
  idBlock.append(avatarNode, idText);
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

  // ══════════════════════════════════════════════════════════════════════════
  // TASK-0238 데이터 소스 & 접근 가능 데이터베이스 — 통합 accordion 재설계.
  //   (이전: "데이터 소스" 섹션 칩 + "접근 가능 데이터베이스" 섹션 헤더배지 + 편집대상 select
  //    = datasource 정보 3중 중복 + pill/점선pill/둥근행 3가지 모양. /design-review 지적.)
  //   재설계: 단일 섹션 안에 datasource = 펼침 accordion 행(= 선택기 = 상태표시). 펼치면 그
  //   datasource 의 접근 DB 편집기가 인라인. datasource 정보 1곳, 액션은 행별 ⋯ 메뉴로 통일.
  // 편집 로직(draft/_refreshAccessibleDbs/redrawChips/buildPicker/_switchEditDs)은 보존하고
  // **표현 계층만** accordion 으로 교체한다(동작 회귀 최소화).
  // ══════════════════════════════════════════════════════════════════════════
  const canDs = can("console.manage");
  let _refreshAccessibleDbs = () => {};
  let _renderDsAccordion = () => {};
  let _ensureDbInsights = () => {};  // TASK-0242: 편집 대상 datasource 의 DB insight 지연로드 hook(정의 후 채움)
  // TASK-0239: 초기 펼침 대상 = effective(desired 우선) 바인딩의 primary(또는 첫째). 스테이징된
  //  추가/제거/기본지정이 있으면 그 상태를 반영해 패널 재진입 시에도 일관되게 펼친다.
  const _effInit = effectiveProductDatasources(product);
  const _effPrimaryKey = ((_effInit.find((d) => d.is_primary) || _effInit[0] || {}).datasource_key) || product.datasource_key || "";
  let _selectedDatasourceKey = _effPrimaryKey;

  const dbSection = document.createElement("div");
  dbSection.className = "admin-detail-section";
  const dbTitle = document.createElement("div");
  dbTitle.className = "admin-detail-section-title";
  dbTitle.textContent = "데이터 소스 & 접근 가능 데이터베이스";
  dbSection.appendChild(dbTitle);
  const dbHint = document.createElement("div");
  dbHint.className = "admin-detail-hint";
  if (!adminState.datasourcesEnabled) {
    dbHint.textContent = "멀티 datasource 비활성(AGENT_MULTI_DATASOURCE_ENABLED=0). 바인딩은 저장되나 flag 활성화 전까지는 기본 MySQL 로 동작합니다.";
  } else {
    dbHint.textContent = "이 제품이 분석할 데이터소스와 각 데이터소스의 접근 가능 데이터베이스. 데이터소스를 클릭하면 펼쳐서 DB 를 편집합니다.";
  }
  dbSection.appendChild(dbHint);

  // TASK-0223: 제품 전체 insight 분석 완료율(전 datasource 합산) — 섹션 상단 1개.
  dbSection.appendChild(buildProductCoverageDetail(product));

  // 편집 중(펼친) datasource. 기본 = effective primary. 단일/미바인딩이면 primary(또는 '').
  let _editDsKey = _effPrimaryKey;
  // 펼친(편집 대상) datasource 의 DB 편집기 body 접힘 여부. 기본 true(=접힘) — 제품을 선택해
  //  상세를 열면 DB 목록을 접은 상태로 시작해 하단 UI(데이터소스 추가·제품 프롬프트·삭제)에
  //  바로 접근할 수 있게 한다(사용자 요청). 데이터소스 행의 머리를 클릭하면 펼침/접힘 토글되고,
  //  다른 datasource 로 전환하면 자동으로 펼쳐진다(_switchEditDs / _afterBindChange 에서 false 로 리셋).
  let _dsBodyCollapsed = true;
  let _switchEditDs = () => {};  // forward hook (정의 후 채움)
  const _serverDbsFor = (dsk) => {
    const want = String(dsk || "").trim().toLowerCase();
    return (product.databases || [])
      .filter((d) => String(d.datasource_key || "").trim().toLowerCase() === want)
      .map((d) => ({ ...d }));
  };
  // draft 는 letrec — 편집 대상 datasource 변경 시 재구성(재할당). pending 우선, 다음 fresh draft, 최후 서버.
  const _draftKeyFor = (dsk) => `${Number(product.id)}::${String(dsk || "").trim().toLowerCase()}`;
  const _loadDraft = (dsk) => {
    const pend = adminState.pending.productDatabases.get(_draftKeyFor(dsk));
    if (pend) return pend.map((d) => ({ ...d }));
    const fresh = adminState.productDbDraft.get(_draftKeyFor(dsk));
    if (fresh) return fresh;
    return _serverDbsFor(dsk);
  };
  // draft 는 in-place 변경하는 안정 컨테이너(closure 가 참조 유지). datasource 전환 시 내용만 교체.
  const draft = [];
  const _swapDraftContents = (arr) => { draft.length = 0; (arr || []).forEach((d) => draft.push(d)); };
  _swapDraftContents(_loadDraft(_editDsKey));
  adminState.productDbDraft.set(_draftKeyFor(_editDsKey), draft);

  const chipWrap = document.createElement("div");
  chipWrap.className = "cov-db-wrap";

  // 시스템/메타데이터 locked chip 의 기본 소스(데이터 MySQL). datasource-driven 으로 교체됨(_refreshAccessibleDbs).
  const metadataPayload = (adminState.availableDatabases.metadata_schemas || []).slice();
  const _defaultLocked = metadataPayload.length
    ? metadataPayload.map((m) => ({ name: m.schema_name, present: m.present !== false }))
    : METADATA_SCHEMAS.map((name) => ({ name, present: true }));
  // 가변 소스 — datasource 선택에 따라 갱신.
  let lockedChips = _defaultLocked.slice();              // 시스템 DB / 메타데이터(고정칩)
  let availableUserDbs = (adminState.availableDatabases.user_schemas || []).slice();  // 사용자 DB(picker)
  let dsCaseInsensitive = false;                          // MSSQL DB명 대소문자 보존(true=lower 비교만)
  // TASK-20260618T025755: picker 검색/정규식 입력값 — buildPicker 재렌더(비동기 insight 도착 등) 간 보존.
  let _dbPickerQuery = "";
  let _dbPickerRegex = "";

  // 체크박스 드롭다운 패널 빌더. 드롭다운은 버튼 클릭 시 열리며, 각 항목에 체크박스로
  // 연속 토글 가능. 선택 즉시 draft 에 반영(추가 버튼 불필요).
  const buildPicker = () => {
    pickerDropList.innerHTML = "";
    // TASK-0242: 추가 후보 DB 의 분석 상태/도메인 힌트(편집 대상 datasource 의 insight 캐시).
    const _pkIns = adminState.productDbInsights.get(_dbInsightsKey(product.id, _editDsKey)) || null;
    const _pkByDb = (_pkIns && _pkIns.by_db) || {};
    const _pkWorker = (_pkIns && _pkIns.worker) || {};
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

    // ── TASK-20260618T025755: 검색 필터 + 정규식 일괄 선택 toolbar ──────────────────
    //  후보 DB 가 많을 때만(빈번한 DB 구성 변경 대응) 노출. selectedCountEl 은 toolbar 가
    //  없을 땐 null → _refreshSelectedCount/_applySearch 는 no-op 으로 안전 동작한다.
    let noResultEl = null, regexErrEl = null, regexCountEl = null, selectedCountEl = null;
    const _refreshSelectedCount = () => {
      if (selectedCountEl) {
        selectedCountEl.textContent = `선택됨 ${draft.filter((d) => d && d.schema_name).length}개`;
      }
    };
    const _applySearch = () => {
      const shown = applyDbPickerSearch(pickerDropList, _dbPickerQuery);
      if (noResultEl) noResultEl.classList.toggle("hidden", shown !== 0);
    };
    const _applyRegexPreview = () => {
      const res = applyDbPickerRegexHighlight(pickerDropList, _dbPickerRegex);
      if (regexErrEl) {
        regexErrEl.textContent = res.ok ? "" : "정규식이 올바르지 않습니다.";
        regexErrEl.classList.toggle("hidden", res.ok);
      }
      if (regexCountEl) {
        regexCountEl.textContent = (!String(_dbPickerRegex).trim() || !res.ok) ? "" : `${res.count}개 일치`;
      }
    };
    // 정규식 일치 DB 를 draft 에 일괄 추가(additive — 기존 선택은 해제하지 않음).
    //  체크박스 단일 추가와 동일한 검증(시스템/내부 스키마 제외, 비-MSSQL 이름 형식)을 통과한 것만.
    const _applyRegexSelect = () => {
      const res = dbPickerRegexMatches(userSchemas, _dbPickerRegex);
      if (!res.ok) { showToast("정규식이 올바르지 않습니다.", true); return; }
      if (!res.matches.length) { showToast("정규식과 일치하는 DB 가 없습니다."); return; }
      let added = 0;
      res.matches.forEach((raw) => {
        const v = String(raw).toLowerCase();
        if (METADATA_SCHEMAS.includes(v) || INTERNAL_SCHEMAS.has(v)) return;
        if (!dsCaseInsensitive && !/^[a-z_][a-z0-9_]{0,63}$/.test(v)) return;
        if (!draft.some((d) => String(d.schema_name).toLowerCase() === v)) {
          draft.push({ schema_name: dsCaseInsensitive ? raw : v, description: "", sort_order: (draft.length + 1) * 10 });
          added += 1;
        }
      });
      if (added > 0) {
        setProductDatabasesPending(product.id, draft, _editDsKey);
        redrawChips();
        buildPicker();   // 체크박스/카운트 재반영(검색·정규식 입력값은 closure 로 보존·복원).
      }
      showToast(`정규식 일치 ${res.matches.length}개 중 ${added}개를 선택에 추가했습니다.`);
    };

    if (userSchemas.length >= DB_PICKER_SEARCH_MIN) {
      const toolbar = document.createElement("div");
      toolbar.className = "admin-db-picker-toolbar";
      toolbar.addEventListener("click", (e) => e.stopPropagation());  // toolbar 클릭이 항목 토글로 새지 않게.

      const searchInput = document.createElement("input");
      searchInput.type = "text";
      searchInput.className = "admin-db-picker-search";
      searchInput.placeholder = "DB 이름 검색…";
      searchInput.value = _dbPickerQuery;
      searchInput.disabled = !canManage;
      searchInput.setAttribute("aria-label", "데이터베이스 이름 검색");
      searchInput.addEventListener("input", () => { _dbPickerQuery = searchInput.value; _applySearch(); });
      toolbar.appendChild(searchInput);

      const reRow = document.createElement("div");
      reRow.className = "admin-db-picker-regex-row";
      const reInput = document.createElement("input");
      reInput.type = "text";
      reInput.className = "admin-db-picker-regex";
      reInput.placeholder = "정규식 일괄 선택… 예: ^prod_|_log$";
      reInput.value = _dbPickerRegex;
      reInput.disabled = !canManage;
      reInput.setAttribute("aria-label", "정규식으로 데이터베이스 일괄 선택");
      reInput.addEventListener("input", () => { _dbPickerRegex = reInput.value; _applyRegexPreview(); });
      reInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); _applyRegexSelect(); } });
      regexCountEl = document.createElement("span");
      regexCountEl.className = "admin-db-picker-regex-count";
      const reBtn = document.createElement("button");
      reBtn.type = "button";
      reBtn.className = "admin-db-picker-regex-btn";
      reBtn.textContent = "일치 선택";
      reBtn.disabled = !canManage;
      reBtn.title = "정규식과 일치하는 모든 DB 를 선택에 추가(기존 선택은 유지)";
      reBtn.addEventListener("click", () => _applyRegexSelect());
      reRow.append(reInput, regexCountEl, reBtn);
      toolbar.appendChild(reRow);

      regexErrEl = document.createElement("div");
      regexErrEl.className = "admin-db-picker-regex-err hidden";
      toolbar.appendChild(regexErrEl);

      selectedCountEl = document.createElement("div");
      selectedCountEl.className = "admin-db-picker-selected-count";
      toolbar.appendChild(selectedCountEl);

      pickerDropList.appendChild(toolbar);
    }

    userSchemas.forEach((name) => {
      const item = document.createElement("label");
      item.className = "admin-db-picker-item";
      item.dataset.search = String(name).toLowerCase();   // 검색 haystack(부분일치).
      item.dataset.dbname = String(name).toLowerCase();   // 정규식 하이라이트 매칭 키.
      const cb = document.createElement("input");
      cb.type = "checkbox";
      const nameKey = String(name).toLowerCase();
      const _draftEntry = draft.find((d) => String(d.schema_name).toLowerCase() === nameKey);
      cb.checked = !!_draftEntry;
      // TASK-20260618T044318: 규칙(rule) 자동 행은 체크박스 비활성 — 수동 uncheck 가 무효(reconcile 재추가)
      //   라 혼란 방지. 제거하려면 규칙 편집/삭제로 관리.
      const _isRuleEntry = _draftEntry && String(_draftEntry.source || "manual") === "rule";
      cb.disabled = !canManage || !!_isRuleEntry;
      if (_isRuleEntry) item.title = "정규식 자동 규칙으로 추가됨 — 규칙 편집/삭제로 관리합니다.";
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
            setProductDatabasesPending(product.id, draft, _editDsKey);
            redrawChips();
            _refreshSelectedCount();
          }
        } else {
          const v = String(name).toLowerCase();
          const idx = draft.findIndex((d) => String(d.schema_name).toLowerCase() === v);
          if (idx !== -1) {
            draft.splice(idx, 1);
            setProductDatabasesPending(product.id, draft, _editDsKey);
            redrawChips();
            _refreshSelectedCount();
          }
        }
      });
      const lbl = document.createElement("span");
      lbl.className = "admin-db-picker-name";
      lbl.textContent = name;
      item.append(cb, lbl);
      // TASK-0242: 도메인 힌트 + 분석 상태(미분석/분석중/분석됨).
      item.appendChild(buildPickerInsightMeta(_pkByDb[String(name).toLowerCase()] || null, _pkWorker));
      pickerDropList.appendChild(item);
    });

    // 검색 결과 없음 안내(동적 — _applySearch 가 .hidden 토글).
    noResultEl = document.createElement("div");
    noResultEl.className = "admin-db-picker-no-result hidden";
    noResultEl.textContent = "검색 결과가 없습니다.";
    pickerDropList.appendChild(noResultEl);

    pickerDropBtn.disabled = !canManage;
    // 재렌더 후 보존된 검색/정규식 입력값을 즉시 재적용(필터·하이라이트·카운트 복원).
    _refreshSelectedCount();
    _applySearch();
    _applyRegexPreview();
  };

  const redrawChips = () => {
    chipWrap.innerHTML = "";
    // 시스템/메타데이터 고정 DB → 단일 묶음 칩(개별 이름은 hover/focus 툴팁). 분석 대상 아님.
    const sysChip = buildSystemDbChip(lockedChips);
    if (sysChip) chipWrap.appendChild(sysChip);

    // 사용자 등록 DB → "분석 진척 + 제거"를 한 행에 담은 통합 리스트(완료율 per-DB 와 1:1).
    const cov = adminState.productCoverage.get(Number(product.id));
    const covByDb = new Map();
    if (cov && Array.isArray(cov.per_db)) {
      cov.per_db.forEach((d) => {
        if (d && d.db) covByDb.set(String(d.db).toLowerCase(), d);
      });
    }
    const measuring = _isProductCoverageLoading(product.id);
    // TASK-0242: 편집 대상 datasource 의 DB insight 파악 내용(캐시) — 각 행에 한 줄 설명.
    const insKey = _dbInsightsKey(product.id, _editDsKey);
    const ins = adminState.productDbInsights.get(insKey) || null;
    const insByDb = (ins && ins.by_db) || {};
    const insLoading = adminState.productDbInsightsLoading.has(insKey) || !ins;

    const listEl = document.createElement("div");
    listEl.className = "cov-db-list";
    draft.forEach((entry, idx) => {
      const rowEl = document.createElement("div");
      rowEl.className = "cov-db-row";
      const covRow = covByDb.get(String(entry.schema_name).toLowerCase()) || null;
      if (covRow && covRow.connected === false) rowEl.classList.add("is-offline");

      const nameEl = document.createElement("span");
      nameEl.className = "cov-db-name";
      nameEl.textContent = entry.schema_name;
      nameEl.title = entry.schema_name;
      rowEl.appendChild(nameEl);

      // TASK-20260618T044318: 규칙(rule) 자동 동기화로 추가된 행은 "규칙" 배지(수동 제거 대상 아님).
      const _isRuleRow = String((entry && entry.source) || "manual") === "rule";
      if (_isRuleRow) {
        const rb = document.createElement("span");
        rb.className = "cov-db-rule-badge";
        rb.textContent = "규칙";
        rb.title = "정규식 자동 규칙으로 추가됨 — 규칙 편집/삭제로 관리합니다.";
        rowEl.appendChild(rb);
      }

      // TASK-0242: insight-worker 가 파악한 역할/도메인 한 줄(이름 다음, 진척 셀 앞).
      rowEl.appendChild(buildDbRoleCell(insByDb[String(entry.schema_name).toLowerCase()] || null, { loading: insLoading }));

      // 진척 셀(마이크로바 + 통계 + 상태칩).
      rowEl.appendChild(buildDbCoverageCells(covRow, measuring));

      // TASK-0230: insight 초기화 버튼(insight.reset 권한자만 — 파괴적, dry-run + typed-confirm).
      // 분석 데이터가 없으면 dry-run 이 "삭제할 것 없음"을 안내하므로 권한만으로 노출해도 무해.
      if (canReset) {
        const resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "cov-db-reset";
        resetBtn.textContent = "초기화";
        resetBtn.title = `'${entry.schema_name}' 의 insight 분석을 삭제합니다(다음 cycle 에 자동 재분석).`;
        resetBtn.disabled = measuring;
        resetBtn.addEventListener("click", () => resetProductDbInsight(product, entry.schema_name));
        rowEl.appendChild(resetBtn);
      } else {
        // 권한 없을 때도 grid 컬럼(초기화) 자리 유지 — 행 정렬 일관.
        const rspacer = document.createElement("span");
        rspacer.className = "cov-db-reset-spacer";
        rowEl.appendChild(rspacer);
      }

      // 제거 버튼(편집 권한 시). 규칙(rule) 행은 수동 제거 대상이 아님(규칙 편집/삭제로 관리) → spacer.
      if (canManage && !_isRuleRow) {
        const x = document.createElement("button");
        x.type = "button";
        x.className = "cov-db-remove";
        x.textContent = "×";
        x.title = "이 데이터베이스 접근 제거";
        x.setAttribute("aria-label", `${entry.schema_name} 접근 제거`);
        x.addEventListener("click", () => {
          draft.splice(idx, 1);
          setProductDatabasesPending(product.id, draft, _editDsKey);
          redrawChips();
          buildPicker();
        });
        rowEl.appendChild(x);
      } else {
        // 권한 없을 때 grid 정렬 유지용 placeholder.
        const spacer = document.createElement("span");
        spacer.className = "cov-db-remove-spacer";
        rowEl.appendChild(spacer);
      }
      listEl.appendChild(rowEl);
    });
    if (!draft.length) {
      const empty = document.createElement("div");
      empty.className = "cov-db-list-empty";
      empty.textContent = "등록된 데이터베이스가 없습니다. 아래에서 추가하세요.";
      listEl.appendChild(empty);
    }
    chipWrap.appendChild(listEl);
  };

  // 접근 DB 편집기(시스템칩 + 사용자 DB 리스트 + 추가 picker)를 담는 컨테이너.
  // accordion 의 "펼친 datasource 행" 아래로 이 컨테이너를 옮겨 단다(_renderDsAccordion).
  const dbEditorWrap = document.createElement("div");
  dbEditorWrap.className = "cov-db-editor";
  dbEditorWrap.appendChild(chipWrap);

  const pickerWrap = document.createElement("div");
  pickerWrap.className = "admin-db-picker-wrap";
  const pickerDropBtn = document.createElement("button");
  pickerDropBtn.type = "button";
  pickerDropBtn.className = "admin-db-picker-btn";
  pickerDropBtn.textContent = "+ 데이터베이스 추가";
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
  dbEditorWrap.appendChild(pickerWrap);

  redrawChips();
  buildPicker();

  // ── TASK-20260618T044318: 정규식 자동 규칙 에디터 + pending 승인 (per (product, datasource)) ──
  //  규칙을 한 번 저장하면 데이터소스 DB 변화 시 일치 DB 가 (반)자동 반영된다(cap 이하·명확=자동,
  //  초과·권한보류=pending 승인). allowlist 는 보안 경계라 안전 하이브리드(outside-voice B1).
  const ruleWrap = document.createElement("div");
  ruleWrap.className = "cov-db-rule";
  dbEditorWrap.appendChild(ruleWrap);

  const reloadProductAfterRuleChange = async () => {
    try { await loadAdminData(); } catch (e) { /* ignore */ }
    renderProductDetail();  // 갱신된 product.databases(rule 행 포함)로 상세 재렌더.
  };

  let _renderRuleEditor = () => {};
  if (canManage) {
    _renderRuleEditor = async () => {
      const dsk = String(_editDsKey || "").trim().toLowerCase();
      ruleWrap.innerHTML = "";
      if (!dsk) return;  // 미바인딩(기본 단일 MySQL)에는 규칙 미지원.
      const head = document.createElement("div");
      head.className = "cov-db-rule-head";
      head.textContent = "정규식 자동 규칙";
      const hint = document.createElement("div");
      hint.className = "cov-db-rule-hint";
      hint.textContent = "정규식과 일치하는 DB 를 데이터소스 변화 시 자동 반영합니다(한도 초과/권한 보류분은 승인 대기).";
      const incInput = document.createElement("input");
      incInput.type = "text"; incInput.className = "cov-db-rule-input cov-db-rule-include";
      incInput.placeholder = "포함 정규식… 예: ^prod_|_live$";
      const excInput = document.createElement("input");
      excInput.type = "text"; excInput.className = "cov-db-rule-input cov-db-rule-exclude";
      excInput.placeholder = "제외 정규식(선택)… 예: _bak$";
      const capInput = document.createElement("input");
      capInput.type = "number"; capInput.className = "cov-db-rule-cap";
      capInput.min = "1"; capInput.max = "100"; capInput.value = "3";
      capInput.title = "한 번에 자동 적용할 최대 신규 DB 수(초과 시 승인 대기)";
      const countEl = document.createElement("span"); countEl.className = "cov-db-rule-count";
      const saveBtn = document.createElement("button");
      saveBtn.type = "button"; saveBtn.className = "cov-db-rule-save"; saveBtn.textContent = "규칙 저장";
      const delBtn = document.createElement("button");
      delBtn.type = "button"; delBtn.className = "cov-db-rule-del hidden"; delBtn.textContent = "규칙 삭제";
      const errEl = document.createElement("div"); errEl.className = "cov-db-rule-err hidden";
      const pendWrap = document.createElement("div"); pendWrap.className = "cov-db-rule-pending";
      const row1 = document.createElement("div"); row1.className = "cov-db-rule-row"; row1.append(incInput);
      const row2 = document.createElement("div"); row2.className = "cov-db-rule-row"; row2.append(excInput);
      const row3 = document.createElement("div"); row3.className = "cov-db-rule-row";
      const capLbl = document.createElement("label"); capLbl.className = "cov-db-rule-caplbl";
      capLbl.textContent = "자동 적용 한도"; capLbl.appendChild(capInput);
      row3.append(capLbl, countEl, saveBtn, delBtn);
      ruleWrap.append(head, hint, row1, row2, row3, errEl, pendWrap);

      let data = null;
      try {
        data = await apiFetch(`/api/admin/products/${product.id}/datasources/${encodeURIComponent(dsk)}/db-rule`);
      } catch (e) { data = null; }
      if (data && data.rule) {
        incInput.value = data.rule.include_pattern || "";
        excInput.value = data.rule.exclude_pattern || "";
        capInput.value = String(data.rule.cap || 3);
        delBtn.classList.remove("hidden");
      }
      const renderPending = (pending) => {
        pendWrap.innerHTML = "";
        const list = pending || [];
        if (!list.length) return;
        const ph = document.createElement("div"); ph.className = "cov-db-rule-pending-head";
        ph.textContent = `승인 대기 ${list.length}개 — 규칙 일치(한도 초과/권한 보류)`;
        pendWrap.appendChild(ph);
        list.forEach((p) => {
          const it = document.createElement("div"); it.className = "cov-db-rule-pending-item";
          const nm = document.createElement("span"); nm.className = "cov-db-rule-pending-name"; nm.textContent = p.schema_name;
          const ap = document.createElement("button"); ap.type = "button"; ap.className = "cov-db-rule-approve"; ap.textContent = "승인";
          ap.addEventListener("click", async () => {
            ap.disabled = true;
            try {
              await apiFetch(`/api/admin/products/${product.id}/datasources/${encodeURIComponent(dsk)}/db-rule/approve-pending`,
                { method: "POST", body: JSON.stringify({ schemas: [p.schema_name] }) });
              showToast(`'${p.schema_name}' 승인 — 접근 목록에 추가됨.`);
              await reloadProductAfterRuleChange();
            } catch (e) { showToast("승인 실패: " + (e.message || "오류"), true); ap.disabled = false; }
          });
          it.append(nm, ap); pendWrap.appendChild(it);
        });
      };
      renderPending(data && data.pending);

      let _pvTimer = null;
      const _doPreview = async () => {
        const inc = incInput.value.trim();
        if (!inc) { countEl.textContent = ""; errEl.classList.add("hidden"); return; }
        try {
          const r = await apiFetch(`/api/admin/products/${product.id}/datasources/${encodeURIComponent(dsk)}/db-rule/preview`,
            { method: "POST", body: JSON.stringify({ include_pattern: inc, exclude_pattern: excInput.value.trim() }) });
          if (r && r.ok) { countEl.textContent = `${r.matched_count}개 일치 · 신규 ${r.new_count}개`; errEl.classList.add("hidden"); }
          else { countEl.textContent = ""; errEl.textContent = (r && r.error) || "정규식 오류"; errEl.classList.remove("hidden"); }
        } catch (e) { /* keep last */ }
      };
      const _schedule = () => { if (_pvTimer) clearTimeout(_pvTimer); _pvTimer = setTimeout(_doPreview, 350); };
      incInput.addEventListener("input", _schedule);
      excInput.addEventListener("input", _schedule);
      _doPreview();

      saveBtn.addEventListener("click", async () => {
        const inc = incInput.value.trim();
        if (!inc) { errEl.textContent = "포함 정규식을 입력하세요."; errEl.classList.remove("hidden"); return; }
        saveBtn.disabled = true;
        try {
          const r = await apiFetch(`/api/admin/products/${product.id}/datasources/${encodeURIComponent(dsk)}/db-rule`,
            { method: "PUT", body: JSON.stringify({ include_pattern: inc, exclude_pattern: excInput.value.trim(), cap: Number(capInput.value) || 3 }) });
          const rec = (r && r.reconcile) || {};
          const a = (rec.auto_added || []).length, pnd = (rec.pending || []).length;
          showToast(`규칙 저장 — 자동 추가 ${a}개${pnd ? `, 승인 대기 ${pnd}개` : ""}.`);
          await reloadProductAfterRuleChange();
        } catch (e) { errEl.textContent = "저장 실패: " + (e.message || "오류"); errEl.classList.remove("hidden"); saveBtn.disabled = false; }
      });
      delBtn.addEventListener("click", async () => {
        if (!confirm("이 데이터소스의 정규식 자동 규칙을 삭제할까요?")) return;
        const strip = confirm("규칙으로 추가된 DB 접근 행도 함께 삭제할까요?\n확인=행도 삭제 · 취소=규칙만 삭제(행 유지)");
        try {
          await apiFetch(`/api/admin/products/${product.id}/datasources/${encodeURIComponent(dsk)}/db-rule${strip ? "?strip=1" : ""}`,
            { method: "DELETE" });
          showToast("규칙 삭제됨.");
          await reloadProductAfterRuleChange();
        } catch (e) { showToast("삭제 실패: " + (e.message || "오류"), true); }
      });
    };
    _renderRuleEditor();
  }

  // TASK-0242: 편집 대상(펼친) datasource 의 DB insight 지연로드 — 캐시에 없으면 fetch 후 재렌더(설명/상태 채움).
  _ensureDbInsights = (opts = {}) => {
    loadProductDbInsights({
      productId: product.id,
      datasourceKey: _editDsKey,
      refresh: !!(opts && opts.refresh),
      onDone: () => { redrawChips(); buildPicker(); },
    });
  };

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
      _ensureDbInsights();   // TASK-0242: 기본(미바인딩) scope 의 DB 설명/상태 로드.
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
    _ensureDbInsights();   // TASK-0242: 이 datasource scope 의 DB 설명/상태 로드(완료 시 재렌더).
  };

  // TASK-0238: 편집 대상(펼친) datasource 전환 — 현재 draft 를 그 datasource 키로 저장 보존하고,
  // 새 datasource 의 draft 로드 + 서버 DB 목록 갱신 + accordion 재렌더(active 행 표시·편집기 이동).
  _switchEditDs = (newKey) => {
    const nk = String(newKey || "").trim().toLowerCase();
    if (nk === String(_editDsKey || "").trim().toLowerCase()) return;
    adminState.productDbDraft.set(_draftKeyFor(_editDsKey), draft.map((d) => ({ ...d })));
    _editDsKey = nk;
    _dsBodyCollapsed = false;  // 다른 datasource 로 전환 = 편집기 펼침

    _swapDraftContents(_loadDraft(nk));
    adminState.productDbDraft.set(_draftKeyFor(nk), draft);
    // TASK-0239: draft 를 즉시 다시 그려 전환 시 구 datasource 의 DB 가 남아 깜빡이는 현상 제거.
    //  (lockedChips/picker 정교화는 아래 비동기 _refreshAccessibleDbs 가 이어서 처리.)
    redrawChips();
    _renderDsAccordion();        // active 행 강조 + dbEditorWrap 을 새 행 아래로 이동
    _refreshAccessibleDbs(nk);   // 새 datasource 의 DB picker + 시스템칩 갱신
    _renderRuleEditor();         // TASK-20260618T044318: 새 datasource 의 규칙/pending 로드
  };

  // ── TASK-0238: datasource accordion (선택기 = 상태표시 = 바인딩관리 통합) ──────────────
  //  각 datasource = 펼침 가능한 행. 펼친 행(=_editDsKey) 아래로 dbEditorWrap 을 옮겨 단다.
  //  행 우측 ⋯ 메뉴 = 연결 테스트 / 기본 지정 / 바인딩 제거(액션 통일). primary 는 "기본" 배지.
  {
    const dsAccordion = document.createElement("div");
    dsAccordion.className = "ds-acc";

    // TASK-0239: 바인딩 변경(추가/제거/기본지정)은 즉시 API 가 아니라 pending(desired) 에 스테이징.
    //  "모두 적용" 으로 일괄 저장된다(다른 콘솔 편집과 동일 흐름). 여기선 로컬 재렌더만 — 전체
    //  renderProductDetail() 대신 accordion 만 다시 그려 깜빡임 없이 즉시 시각 반영.
    //  편집 대상(_editDsKey)이 제거됐으면 desired 의 primary(또는 첫째)로 전환한다.
    const _afterBindChange = (preferKey) => {
      const eff = effectiveProductDatasources(product);
      const keys = eff.map((d) => String(d.datasource_key).toLowerCase());
      const cur = String(_editDsKey || "").trim().toLowerCase();
      if (!keys.includes(cur)) {
        const prim = eff.find((d) => d.is_primary) || eff[0] || null;
        const next = prim ? String(prim.datasource_key).toLowerCase() : "";
        _editDsKey = next;
        _dsBodyCollapsed = false;  // 편집 대상이 제거되어 다른 datasource 로 옮겨감 = 펼침
        _swapDraftContents(_loadDraft(next));
        adminState.productDbDraft.set(_draftKeyFor(next), draft);
        redrawChips();
        _renderDsAccordion();
        _refreshAccessibleDbs(next);
      } else if (preferKey && String(preferKey).toLowerCase() !== cur) {
        _switchEditDs(preferKey);  // 새로 추가한 것을 펼쳐 보여줌
      } else {
        _renderDsAccordion();  // primary 배지 등 갱신
      }
    };

    // 행 우측 ⋯ 액션 메뉴(연결 테스트 / 기본 지정 / 제거). 한 datasource 의 모든 동작을 한 곳에.
    const _buildDsMenu = (b) => {
      const wrap = document.createElement("div");
      wrap.className = "ds-acc-menu-wrap";
      const btn = document.createElement("button");
      btn.type = "button"; btn.className = "ds-acc-menu-btn"; btn.textContent = "⋯";
      btn.title = "데이터소스 동작"; btn.setAttribute("aria-haspopup", "true");
      btn.setAttribute("aria-label", `'${b.datasource_key}' 데이터소스 동작 메뉴`);
      const menu = document.createElement("div");
      menu.className = "ds-acc-menu hidden"; menu.setAttribute("role", "menu");
      const addItem = (label, danger, fn) => {
        const it = document.createElement("button");
        it.type = "button"; it.className = "ds-acc-menu-item" + (danger ? " danger" : "");
        it.textContent = label; it.setAttribute("role", "menuitem");
        it.addEventListener("click", async (e) => {
          e.stopPropagation();
          menu.classList.add("hidden");
          await fn();
        });
        menu.appendChild(it);
      };
      // 연결 테스트
      addItem("연결 테스트", false, async () => {
        showToast(`'${b.datasource_key}' 연결 테스트 중…`);
        try {
          const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(b.datasource_key)}/test`, { method: "POST" });
          if (r && r.ok) showToast(`'${b.datasource_key}' 연결 성공 (${r.elapsed_ms}ms)`);
          else showToast(`'${b.datasource_key}' 연결 실패: ${(r && r.error) || "unknown"}`, true);
        } catch (e) { showToast(`'${b.datasource_key}' 연결 테스트 오류: ${e.message || "실패"}`, true); }
      });
      // 기본 지정(primary 아닐 때만) — 즉시 API 대신 desired 스테이징(일괄 적용).
      if (!b.is_primary) {
        addItem("기본으로 지정", false, () => {
          stageSetPrimaryDatasource(product, b.datasource_key);
          _afterBindChange();
          showToast(`'${b.datasource_key}' 를 기본 데이터소스로 지정(적용 대기)`);
        });
      }
      // 바인딩 제거 — desired 에서 제외(일괄 적용 시 DELETE). 접근DB 도 적용 시 함께 정리.
      addItem("바인딩 제거", true, () => {
        if (!confirm(`데이터소스 '${b.datasource_key}' 바인딩을 제거할까요?\n("모두 적용" 시 이 데이터소스의 접근 가능 DB 설정도 함께 삭제됩니다.)`)) return;
        stageRemoveDatasource(product, b.datasource_key);
        _afterBindChange();
        showToast(`'${b.datasource_key}' 바인딩 제거(적용 대기)`);
      });
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        document.querySelectorAll(".ds-acc-menu").forEach((m) => { if (m !== menu) m.classList.add("hidden"); });
        menu.classList.toggle("hidden");
      });
      document.addEventListener("click", function _closeMenu(e) { if (!wrap.contains(e.target)) menu.classList.add("hidden"); });
      wrap.append(btn, menu);
      return wrap;
    };

    // accordion 전체 재렌더: datasource 행들 + 펼친 행 아래 dbEditorWrap 이동.
    //  TASK-0239: 서버 정본이 아니라 effective(=desired 우선) 바인딩으로 그려 스테이징 변경을 즉시 반영.
    _renderDsAccordion = () => {
      dsAccordion.innerHTML = "";
      const binds = effectiveProductDatasources(product);
      const dsMeta = new Map((adminState.datasources || []).map((d) => [d.key, d]));
      if (!binds.length) {
        const none = document.createElement("div");
        none.className = "admin-detail-hint";
        none.textContent = "바인딩된 데이터소스 없음 — 기본 단일 MySQL. 아래에서 데이터소스를 선택해 추가하세요.";
        dsAccordion.appendChild(none);
        // 미바인딩: 기본 MySQL 의 접근DB 편집기를 그대로 보인다.
        dsAccordion.appendChild(dbEditorWrap);
        return;
      }
      const activeKey = String(_editDsKey || "").trim().toLowerCase();
      binds.forEach((b) => {
        // isEditTarget = 이 datasource 가 편집 대상(_editDsKey). isExpanded = 편집 대상이면서 접히지 않음.
        //  접힘(_dsBodyCollapsed)일 때는 편집 대상이라도 body 를 그리지 않고 행을 비활성처럼 보인다.
        const isEditTarget = String(b.datasource_key || "").trim().toLowerCase() === activeKey;
        const isExpanded = isEditTarget && !_dsBodyCollapsed;
        const meta = dsMeta.get(b.datasource_key) || {};
        const row = document.createElement("div");
        row.className = "ds-acc-row" + (isExpanded ? " is-active" : "");

        const head = document.createElement("button");
        head.type = "button";
        head.className = "ds-acc-head";
        head.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        head.title = isExpanded ? "클릭하면 접기" : "클릭하면 펼쳐서 DB 편집";
        head.addEventListener("click", () => {
          if (isEditTarget) {
            // 이미 편집 대상인 행 → 펼침/접힘 토글(단일 datasource 도 접어 하단 UI 접근 용이).
            _dsBodyCollapsed = !_dsBodyCollapsed;
            _renderDsAccordion();
          } else {
            // 다른 datasource 로 전환(전환 시 _switchEditDs 가 _dsBodyCollapsed 를 펼침으로 리셋).
            _switchEditDs(b.datasource_key);
          }
        });

        const caret = document.createElement("span");
        caret.className = "ds-acc-caret"; caret.textContent = isExpanded ? "▾" : "▸";
        head.appendChild(caret);

        const name = document.createElement("span");
        name.className = "ds-acc-name"; name.textContent = b.datasource_key;
        head.appendChild(name);

        // 메타: 엔진 + primary 배지(상태 = pill, 액션 아님).
        const eng = document.createElement("span");
        eng.className = "ds-acc-engine"; eng.textContent = (meta.engine || "mysql");
        head.appendChild(eng);
        if (b.is_primary) {
          const pb = document.createElement("span");
          pb.className = "ds-acc-primary"; pb.textContent = "기본";
          head.appendChild(pb);
        }
        row.appendChild(head);

        if (canDs) row.appendChild(_buildDsMenu(b));

        dsAccordion.appendChild(row);
        // 펼친 행 바로 아래에 DB 편집기 삽입(접힘 상태면 생략).
        if (isExpanded) {
          const body = document.createElement("div");
          body.className = "ds-acc-body";
          body.appendChild(dbEditorWrap);
          dsAccordion.appendChild(body);
        }
      });
    };

    dbSection.appendChild(dsAccordion);

    // ＋ 데이터소스 추가 — TASK-0240: DB picker 와 동일한 inline 체크박스 토글 드롭다운으로 통일.
    //  체크=추가 스테이징, 해제=제거 스테이징(이미 바인딩된 것도 체크 상태로 보여 토글 제거 가능).
    //  즉시 API 가 아니라 desired 스테이징 → "모두 적용" 일괄(TASK-0239).
    if (canDs) {
      const addRow = document.createElement("div");
      addRow.className = "ds-acc-add-row admin-db-picker-wrap";
      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "ds-acc-add-btn admin-db-picker-btn";
      addBtn.textContent = "+ 데이터소스 추가";
      addBtn.setAttribute("aria-haspopup", "true");
      addBtn.setAttribute("aria-expanded", "false");
      const addList = document.createElement("div");
      addList.className = "admin-db-picker-list hidden";
      addList.setAttribute("role", "group");
      addList.setAttribute("aria-label", "데이터소스 선택");

      // conn-health-monitor: 연결상태는 백엔드 백그라운드 모니터가 **미리 계산**한 값을
      //  datasources 목록 로드 시 캐시에 반영해 둔다(loadAdminData). 따라서 토글/재렌더마다
      //  per-item /test lazy probe(세마포어 대기)를 하지 않고 **캐시를 즉시 표시**한다 — 한
      //  datasource 가 불안정해도 다른 정상 datasource 배지가 그 뒤에서 대기하지 않는다.
      //  force=true(↻ 새로고침)일 때만 즉시 명시 /test 재probe(on-demand, 사용자 행동).
      const _kickDsConn = (dsk, statusEl, force) => {
        const cached = adminState.datasourceConnStatus.get(dsk);
        if (!force && cached && (cached.state === "ok" || cached.state === "fail")) {
          _paintDsConnBadge(statusEl, cached);  // 사전계산 상태 즉시 표시(정상 경로 — probe 없음).
          return;
        }
        // 캐시 miss(=unknown: 모니터 미가동/콜드 edge) 또는 force(↻) → lazy /test 폴백.
        //  정상 경로(모니터 populated)에선 도달 안 함 → 세마포어 대기 자동 폭주 없음.
        _paintDsConnBadge(statusEl, { state: "checking" });
        _probeDatasourceConn(dsk, { force }).then((res) => _paintDsConnBadge(statusEl, res));
      };

      const _rebuildDsAddList = (forceProbe = false) => {
        addList.innerHTML = "";
        const boundKeys = new Set(effectiveProductDatasources(product).map((d) => String(d.datasource_key).toLowerCase()));
        const all = (adminState.datasources || []);
        if (!all.length) {
          const empty = document.createElement("div");
          empty.className = "admin-db-picker-empty";
          empty.textContent = "(등록된 데이터소스 없음)";
          addList.appendChild(empty);
          return;
        }
        // 헤더: 연결 상태 안내 + ↻ 전체 새로고침(캐시 무효화 후 재probe).
        const header = document.createElement("div");
        header.className = "admin-ds-picker-head";
        const hLbl = document.createElement("span");
        hLbl.className = "admin-ds-picker-head-label";
        hLbl.textContent = "데이터소스 · 연결 상태";
        const refreshBtn = document.createElement("button");
        refreshBtn.type = "button";
        refreshBtn.className = "admin-ds-picker-refresh";
        refreshBtn.textContent = "↻ 새로고침";
        refreshBtn.title = "모든 데이터소스 연결 상태를 즉시 다시 확인";
        refreshBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          // 명시 새로고침(on-demand) — 캐시 비우고 '확인 중' 표시 후 각 datasource 즉시 /test
          //  재probe(force). 자동 토글 경로와 달리 사용자 명시 행동이라 즉시 probe 허용.
          // TASK-0253: 이전엔 캐시 비운 뒤 (a) _rebuildDsAddList() 가 _kickDsConn(force:false)
          //  로 cache-miss probe 를 걸고 (b) 별도 Promise.all(force:true) 로 같은 key 를 또
          //  probe 해 datasource 당 **2벌**이 동시에 떠 4-cap 세마포어를 2배로 점유, ↻ 후
          //  배지가 수 초간 "확인 중…"에 묶였다. rebuild 에 forceProbe 를 넘겨 각 항목을
          //  _kickDsConn(force:true) **한 번만** probe 하도록 단일화한다(중복 제거 + force 의미 보존).
          all.forEach((ds) => adminState.datasourceConnStatus.delete(String(ds.key).toLowerCase()));
          _rebuildDsAddList(true);
        });
        header.append(hLbl, refreshBtn);
        addList.appendChild(header);

        all.forEach((ds) => {
          const dsk = String(ds.key).toLowerCase();
          const item = document.createElement("label");
          item.className = "admin-db-picker-item admin-ds-picker-item";
          const cb = document.createElement("input");
          cb.type = "checkbox";
          cb.checked = boundKeys.has(dsk);
          cb.addEventListener("change", () => {
            if (cb.checked) {
              stageAddDatasource(product, ds.key);
              _afterBindChange(ds.key);   // 새로 켠 datasource 를 펼쳐 보여줌
              showToast(`데이터소스 '${ds.key}' 추가(적용 대기)`);
            } else {
              stageRemoveDatasource(product, ds.key);
              _afterBindChange();
              showToast(`데이터소스 '${ds.key}' 제거(적용 대기)`);
            }
            _rebuildDsAddList();  // 체크 상태 재동기화
          });
          // 이름(.admin-db-picker-name = DB picker 와 동일 클래스로 폰트/정렬 정합), 엔진 pill, 좌표(muted), 연결 상태 배지.
          const name = document.createElement("span");
          name.className = "admin-db-picker-name";
          name.textContent = ds.key;
          name.title = ds.key;
          const eng = document.createElement("span");
          eng.className = "admin-ds-picker-engine";
          eng.textContent = (ds.engine || "mysql");
          const coord = document.createElement("span");
          coord.className = "admin-ds-picker-coord";
          coord.textContent = `${ds.host || "?"}:${ds.port || ""}`;
          coord.title = `${ds.host || "?"}:${ds.port || ""}`;
          const status = document.createElement("span");
          item.append(cb, name, eng, coord, status);
          addList.appendChild(item);
          // forceProbe=true(↻ 명시 새로고침)면 캐시 무시 재probe, 평소엔 캐시 hit→즉시 / miss→'확인 중' 후 probe.
          _kickDsConn(dsk, status, forceProbe);
        });
      };

      addBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const willOpen = addList.classList.contains("hidden");
        if (willOpen) _rebuildDsAddList();
        addList.classList.toggle("hidden");
        addBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
      });
      document.addEventListener("click", function _closeDsAdd(ev) {
        if (!addRow.contains(ev.target)) { addList.classList.add("hidden"); addBtn.setAttribute("aria-expanded", "false"); }
      });
      addRow.append(addBtn, addList);
      dbSection.appendChild(addRow);
    }

    paneEl.appendChild(dbSection);
    _renderDsAccordion();
    // 초기 로드: 펼친(primary) datasource 의 DB 목록으로 접근가능DB 구성.
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
      // TASK-0248: 참조 대화가 있어도 삭제 가능 — 그 대화는 차단(진행 불가, 이력 열람·공유는 가능)으로 전환된다.
      if (!window.confirm(
        `${product.name} 제품을 삭제할까요?\n\n이 제품을 참조하는 대화가 있으면 더 이상 진행할 수 없는 ` +
        `'차단' 상태로 전환됩니다 (이력 열람·공유는 가능). 이 작업은 되돌릴 수 없습니다.`
      )) return;
      try {
        const result = await apiFetch(`/api/admin/products/${Number(product.id)}`, { method: "DELETE" });
        adminState.selectedProductId = null;
        const blockedN = Number(result?.blocked_conversations || 0);
        showToast(blockedN > 0 ? `삭제됨 (대화 ${blockedN}개 차단)` : "삭제됨");
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
  // TASK-0300: allowedCodes 가 주어지면 본인 미보유 product.access.* 카드는 숨긴다.
  const { embed = false, allowedCodes = null } = opts;
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
    // TASK-0303: 라이브 merged(pending 오버레이) 기준으로 읽는다. 렌더 시점 role.permission_codes
    //   스냅샷을 쓰면 직전 토글이 만든 pending 을 반영하지 못해 — 제품을 여러 개 켜도 매 토글이
    //   서버 스냅샷+단건으로 permission_codes 를 통째 교체 → 마지막 1개만 남는다(다중선택 무효).
    //   mergedRole 로 현재 effective codes 를 읽어 단건만 가감한다(신규 역할=draft 도 mergedRole 처리).
    const live = mergedRole(role.id);
    const base = (live && Array.isArray(live.permission_codes)) ? live.permission_codes : (role.permission_codes || []);
    const current = new Set(base.map(String));
    if (granted) current.add(code);
    else current.delete(code);
    setRolePending(role.id, { permission_codes: Array.from(current) });
    renderRoleList();
    // TASK-0303: 임베드된 product_access 그룹의 N/M 배지를 토글 즉시 갱신(상세 재렌더 없이).
    const grp = wrap.closest("details.permission-group");
    if (grp) _updateCheckboxGroupSummary(grp);
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
      if (allowedCodes && !allowedCodes.has(perm.code)) return; // TASK-0300: 본인 미보유 제품접근 권한 숨김
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
  // TASK-0300: allowedCodes 가 주어지면 본인 미보유 product.access.* 카드는 숨긴다.
  const { embed = false, allowedCodes = null } = opts;
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
    // TASK-0303: 라이브 merged(pending 오버레이) 기준으로 읽는다(역할 카드와 동일 근본). 렌더 시점
    //   account.permission_overrides 스냅샷을 쓰면 직전 카드 변경이 만든 pending 을 잃어 — 제품
    //   override 를 여러 개 바꿔도 마지막 1개만 남고, 정적 override 변경과도 서로 덮어쓴다.
    const live = mergedAccount(account.id);
    const next = { ...((live && live.permission_overrides) || account.permission_overrides || {}) };
    if (value === "inherit") {
      delete next[code];
    } else {
      next[code] = value;
    }
    setAccountPending(account.id, { permission_overrides: next });
    // TASK-0303: 임베드된 product_access 그룹의 허용/거부/상속 배지를 변경 즉시 갱신.
    const grp = wrap.closest("details.permission-group");
    if (grp) _updateOverrideGroupSummary(grp);
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
    if (allowedCodes && !allowedCodes.has(perm.code)) return; // TASK-0300: 본인 미보유 제품접근 권한 숨김
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
      opt.textContent = `(${p.product_key}) ${p.name}`;
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

  // TASK-0232/0233: 자동 생성 완료(done) 시 meta 충실도 + 잘림 경고를 metaEl 에 렌더.
  // 비스트리밍/스트리밍 done 양쪽이 공유.
  const applyAutoGenMeta = (m) => {
    m = m || {};
    if (m.grounded) {
      metaEl.textContent =
        `(자동 생성됨 — 스키마 ${m.schema_insight_count || 0}개·테이블 ${m.table_insight_count || 0}개·` +
        `대화주제 ${m.topic_count || 0}건 반영. 검토 후 저장하세요)`;
    } else {
      metaEl.textContent =
        "(자동 생성됨 — DB 인사이트가 아직 수집되지 않아 스키마-비의존 형태입니다. 검토 후 저장하세요)";
    }
    if (m.truncated) {
      metaEl.textContent +=
        " ⚠ 출력 길이 제한에 도달해 프롬프트가 중간에 잘렸을 수 있습니다. 내용을 확인하고 필요하면 다시 생성하세요.";
      metaEl.classList.add("admin-meta-warn");
    } else {
      metaEl.classList.remove("admin-meta-warn");
    }
  };

  if (autoGenerateProductId) {
    const autoBtn = document.createElement("button");
    autoBtn.type = "button";
    autoBtn.className = "btn-secondary";
    autoBtn.textContent = "자동 작성";
    // TASK-0237: SSE 토큰 스트리밍 — textarea 에 본문이 실시간으로 차오른다.
    autoBtn.addEventListener("click", async () => {
      // 재진입 방어 — 진행 중인 스트림이 있으면 중단.
      if (autoBtn._streamAbort) {
        try { autoBtn._streamAbort.abort(); } catch (_) {}
      }
      const controller = new AbortController();
      autoBtn._streamAbort = controller;

      autoBtn.disabled = true;
      autoBtn.textContent = "생성 중…";
      metaEl.classList.remove("admin-meta-warn");
      metaEl.textContent = "준비 중…";
      let streamedAny = false;

      const finish = () => {
        autoBtn.disabled = false;
        autoBtn.textContent = "자동 작성";
        autoBtn._streamAbort = null;
      };

      const handleFrame = (frame) => {
        // SSE 프레임: "event: <type>" + "data: <json>" 라인.
        let ev = null, dataStr = null;
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) ev = line.slice(6).trim();
          else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
        }
        if (!dataStr) return;
        let data;
        try { data = JSON.parse(dataStr); } catch (_) { return; }
        if (ev === "progress") {
          metaEl.textContent = data.label || "생성 중…";
        } else if (ev === "token") {
          if (!streamedAny) { textarea.value = ""; streamedAny = true; }
          // TASK-0254: stick-to-bottom — 갱신을 append 하기 *전에* 사용자가
          // 최하단 근처에 있는지 판정한다. 위로 스크롤해 상단을 읽는 중이면
          // 갱신을 따라 내려가지 않고 현재 위치를 유지한다. 최하단에 있을 때만
          // 새 토큰을 따라 자동 스크롤한다. (임계 8px = 분수 픽셀/clamp 오차 흡수)
          const atBottom =
            textarea.scrollHeight - textarea.scrollTop - textarea.clientHeight <= 8;
          textarea.value += data.text || "";
          if (atBottom) textarea.scrollTop = textarea.scrollHeight;
          metaEl.textContent = `생성 중… (${textarea.value.length}자)`;
        } else if (ev === "done") {
          // TASK-0254: 최종 본문 재할당 시에도 스크롤 위치를 보존한다.
          // 서버 done.prompt 는 .strip() 된 본문이라 스트리밍 중 append 한
          // un-stripped 누적과 길이가 다를 수 있다(흔히 선/후행 개행 trim). 동일하면
          // 재할당을 생략해 스크롤 리셋 자체를 피하고, 다를 때만 재할당 후 새
          // 높이에 맞춰 clamp 한다(최하단이었으면 새 최하단, 아니면 읽던 위치 유지).
          const atBottom =
            textarea.scrollHeight - textarea.scrollTop - textarea.clientHeight <= 8;
          const prevTop = textarea.scrollTop;
          const finalText = (data.prompt != null ? data.prompt : textarea.value);
          if (textarea.value !== finalText) textarea.value = finalText;
          const maxTop = Math.max(0, textarea.scrollHeight - textarea.clientHeight);
          textarea.scrollTop = atBottom ? maxTop : Math.min(prevTop, maxTop);
          const pid = resolveProductId();
          setSystemPromptPending({ scope, productId: pid, roleId, accountId, content: textarea.value });
          applyAutoGenMeta(data.meta);
        } else if (ev === "error") {
          metaEl.classList.add("admin-meta-warn");
          metaEl.textContent = `자동 생성 실패: ${data.error || "알 수 없는 오류"}`;
        }
      };

      try {
        const resp = await fetch(
          `/api/admin/products/${autoGenerateProductId}/prompt/generate/stream`,
          { method: "GET", credentials: "same-origin", signal: controller.signal },
        );
        if (!resp.ok) {
          // 인증/권한/제품부재 등은 JSON 으로 도착(SSE 진입 전).
          let msg = resp.statusText;
          try { const j = await resp.json(); msg = j.error || msg; } catch (_) {}
          metaEl.classList.add("admin-meta-warn");
          metaEl.textContent = `자동 생성 실패: ${msg}`;
          finish();
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const frame = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            if (frame.trim()) handleFrame(frame);
          }
        }
        // 잔여 버퍼 처리(마지막 프레임이 \n\n 없이 끝난 경우).
        if (buf.trim()) handleFrame(buf);
      } catch (error) {
        if (error && error.name === "AbortError") {
          // 사용자/재진입 abort — 조용히 무시. 부분 본문은 textarea 에 남김.
        } else {
          metaEl.classList.add("admin-meta-warn");
          metaEl.textContent = `자동 생성 중단됨(연결 오류): ${error.message || error}`;
        }
      } finally {
        finish();
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

  // TASK-0073 Phase C: audit pane filter handlers.
  attachAuditFilterHandlers();
  // TASK-0288: 모든 관리 콘솔 탭을 권한 기반으로 일괄 게이팅. 이전엔 audits/usage/archives 3개만
  // 게이팅돼 계정·역할·제품·데이터소스·설정 탭이 권한과 무관하게 항상 노출됐다(① 결함). 그룹 라벨/
  // 구분선도 전 탭 숨김 시 함께 숨기고, 활성 탭이 숨겨지면 첫 표시 탭으로 전환한다.
  applyAdminTabVisibility();
  const archiveRefreshBtn = $("archiveRefreshBtn");
  if (archiveRefreshBtn && !archiveRefreshBtn.dataset.bound) {
    archiveRefreshBtn.dataset.bound = "1";
    archiveRefreshBtn.addEventListener("click", () => loadArchivedConversations());
  }
  const archiveSearch = $("archiveSearch");
  if (archiveSearch && !archiveSearch.dataset.bound) {
    archiveSearch.dataset.bound = "1";
    archiveSearch.addEventListener("keydown", (e) => { if (e.key === "Enter") loadArchivedConversations(); });
  }
  // TASK-0276: audits 동형 — 검색 적용/초기화 버튼.
  const archiveSearchBtn = $("archiveSearchBtn");
  if (archiveSearchBtn && !archiveSearchBtn.dataset.bound) {
    archiveSearchBtn.dataset.bound = "1";
    archiveSearchBtn.addEventListener("click", () => loadArchivedConversations());
  }
  const archiveSearchClearBtn = $("archiveSearchClearBtn");
  if (archiveSearchClearBtn && !archiveSearchClearBtn.dataset.bound) {
    archiveSearchClearBtn.dataset.bound = "1";
    archiveSearchClearBtn.addEventListener("click", () => {
      const se = $("archiveSearch");
      if (se) se.value = "";
      loadArchivedConversations();
    });
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

  // Role 활성/비활성 필터 (계정 탭 data-account-filter 와 동형)
  document.querySelectorAll("[data-role-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-role-filter]").forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      adminState.roleFilter = btn.dataset.roleFilter;
      renderRoleList();
    });
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

  // Product 활성/비활성 필터 (계정 탭 data-account-filter 와 동형)
  document.querySelectorAll("[data-product-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-product-filter]").forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      adminState.productFilter = btn.dataset.productFilter;
      renderProductList();
    });
  });
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

  // TASK-0278 — Datasources select-all (현재 필터 기준)
  const datasourceSelectAllEl = $("datasourceSelectAll");
  if (datasourceSelectAllEl) {
    datasourceSelectAllEl.addEventListener("change", (ev) => {
      const visible = _dsFiltered();
      if (ev.target.checked) {
        visible.forEach((d) => adminState.datasourceSelected.add(d.key));
      } else {
        visible.forEach((d) => adminState.datasourceSelected.delete(d.key));
      }
      _dsRenderList();
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
    } else if (adminState.tab === "datasources" && adminState.datasourceSelected.size > 0) {
      adminState.datasourceSelected.clear();
      adminState.datasourceLastClickIdx = -1;
      _dsRenderList();
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
  ["accounts", "roles", "products", "datasources"].forEach((entity) => {
    try { assertBulkBarContract(entity); }
    catch (err) { console.error(err); }
  });
}

initialize().catch((error) => {
  showToast(error.message || "콘솔 로드 실패", true);
});

