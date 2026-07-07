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
    runtimeSettings: new Map(),   // feature-0018 UX: key -> {key, value:정수|RS_RESET}. 편집·기본값복원 예약 → 모두 적용
    productDbRules: new Map(),    // TASK-20260619 (§10.7): "productId::dsKey" -> {creates:[{tempId,include_pattern,exclude_pattern,cap}], updates:{ruleId:{...}}, deletes:{ruleId:{strip}}, approves:{ruleId:[schema,...]}} (정규식 자동 규칙 편집 = pending → "모두 적용")
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
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "quota", "datasource", "kb", "audit", "settings", "product", "conversation_own", "conversation_any", "product_access", "attachment", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  // TASK-20260623T030418-quota-rbac-permission: LLM 토큰 사용 한도(역할 기본·계정 특수)의 조회/조절 권한 그룹.
  quota: "LLM 사용 한도",
  datasource: "데이터소스",
  // TASK-20260623T090440-sample-feedback-curation (ROADMAP ITEM-03): 피드백→샘플쿼리 KB 환류 검수.
  kb: "지식베이스(KB) 검수",
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
  // TASK-20260623T030418-quota-rbac-permission: LLM 사용 한도(quota) 그룹도 관리 권한 section.
  { id: "manage", title: "관리 권한", description: "콘솔 진입 · 계정 · 역할 · LLM 사용 한도 · 데이터소스 · KB 검수 · 제품 관리 · 감사 · 시스템 설정", groups: ["console", "account", "role", "quota", "datasource", "kb", "audit", "settings", "product"] },
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
  "console.aiops.read": "console.access",
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
  // TASK-20260623T030418-quota-rbac-permission: LLM 사용 한도 — quota.read 가 그룹 게이트(console.access
  //   하위), quota.manage(조절) 는 quota.read(조회) 선행. 조회 없이는 조절 불가.
  "quota.read": "console.access",
  "quota.manage": "quota.read",
  // TASK-0288: 데이터소스 — datasource.read 가 그룹 게이트(console.access 하위), manage 는 read 선행.
  "datasource.read": "console.access",
  "datasource.manage": "datasource.read",
  // TASK-20260623T090440-sample-feedback-curation: KB 샘플 검수/승급 — console.access 하위(콘솔 진입 필요).
  "kb.sample.curate": "console.access",
  // metadata-perm-hier: 메타데이터 그룹 종속 정합화 — 다른 관리 그룹(account.read→account.*,
  //   quota.read→quota.manage 등)이 "그룹 게이트(read) → 세부 권한" 2단 계층인데 메타데이터만 평면이었다.
  //   묶음 권한 `kb.ingest.manual`("메타데이터 관리 (전체 묶음)")을 그룹 게이트로 삼아 정합화한다:
  //   `kb.ingest.manual`→console.access(콘솔 게이트 하위, 타 그룹 base 와 동형), 세부 5개→`kb.ingest.manual`.
  //   백엔드는 이미 묶음이 5개를 함의(_METADATA_MANUAL_IMPLIES)하므로 의미 정합. 종속 맵은 UI 표시 계층
  //   (progressive disclosure)일 뿐 authz enforcement 아님 — 개별 부여는 "세부 권한 더 보기"로 여전히 가능.
  "kb.ingest.manual": "console.access",
  "metadata.glossary.manage": "kb.ingest.manual",
  "metadata.enum.manage": "kb.ingest.manual",
  "metadata.table.manage": "kb.ingest.manual",
  "metadata.column.manage": "kb.ingest.manual",
  "metadata.graph.read": "kb.ingest.manual",
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
  "conversation.member.manage": "conversation.list.own",
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
function _refreshGroupDisclosure(containerEl, showAll, recompute, mode, isGrantedForReach) {
  const collapseGroups = mode === "checkbox";
  containerEl.querySelectorAll("details.permission-group").forEach((groupEl) => {
    const rows = Array.from(groupEl.querySelectorAll("[data-perm-code]"));
    if (!rows.length) return; // 권한 row 없는 그룹(예: 제품 카드 only)은 건드리지 않음
    const groupKey = groupEl.dataset.permGroup;
    const hiddenCount = rows.filter((r) => r.hidden).length;
    const grantedCount = rows.filter((r) => isGrantedForReach(r.dataset.permCode)).length;
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
    const hiddenGranted = rows.filter((r) => r.hidden && isGrantedForReach(r.dataset.permCode)).length;
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
  // metadata-perm-hier: 그룹 도달성·"N개 부여됨" cue 판정용 — explicit(명시 설정)에 더해
  //   override(계정) 모드의 **상속(허용)** 부여(inherit + 역할이 부여)도 "부여됨" 으로 센다.
  //   메타데이터 종속을 kb.ingest.manual 게이트 하위로 옮기면서, 역할이 개별 metadata.* 를 (묶음 없이)
  //   부여한 계정을 override 편집기에서 열 때 그 row 가 게이트 미충족으로 접히는데 — isExplicit 만으로는
  //   상속-부여가 안 집계돼 "· N개 부여됨" 단서가 사라진다(도달성 회귀). 상속-부여를 포함해 단서를 복원한다.
  //   checkbox(역할) 모드는 inherited 가 비어 isExplicit 과 동일(무영향).
  const isGrantedForReach = (code) =>
    isExplicit(code) || (mode !== "checkbox" && state.get(code) === "inherit" && inherited.has(code));
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
  _refreshGroupDisclosure(containerEl, showAll, () => _applyPermissionDisclosure(containerEl, mode, showAll, inherited), mode, isGrantedForReach);
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
    productDbRuleDirtyCount() +
    adminState.pending.systemPrompts.size +
    (adminState.pending.runtimeSettings ? adminState.pending.runtimeSettings.size : 0)
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

// TASK-20260619 (§10.7): 정규식 자동 규칙(db-rule) 편집을 즉시 API 대신 pending 에 스테이징.
//  키 = `${productId}::${dsKey}`. ops: creates[{tempId,include_pattern,exclude_pattern,cap}],
//  updates{ruleId:{...}}, deletes{ruleId:{strip}}, approves{ruleId:[schema,...]}.
//  footer "모두 적용"(applyAllPending)이 일괄 확정한다. (확정된 규칙의 백그라운드 자동 동기화는 보존 = 범위 A.)
function _dbRuleStageKey(productId, dsKey) {
  return `${Number(productId) || 0}::${String(dsKey || "").trim().toLowerCase()}`;
}
function _ensureDbRulePending(productId, dsKey) {
  const k = _dbRuleStageKey(productId, dsKey);
  let e = adminState.pending.productDbRules.get(k);
  if (!e) {
    e = { creates: [], updates: {}, deletes: {}, approves: {} };
    adminState.pending.productDbRules.set(k, e);
  }
  return e;
}
function _getDbRulePending(productId, dsKey) {
  return adminState.pending.productDbRules.get(_dbRuleStageKey(productId, dsKey)) || null;
}
function _dbRulePendingEntryEmpty(e) {
  if (!e) return true;
  return (e.creates || []).length === 0
    && Object.keys(e.updates || {}).length === 0
    && Object.keys(e.deletes || {}).length === 0
    && Object.keys(e.approves || {}).length === 0;
}
// 빈 엔트리는 제거(dirty 해소). UI 갱신.
function _settleDbRulePending(productId, dsKey) {
  const k = _dbRuleStageKey(productId, dsKey);
  if (_dbRulePendingEntryEmpty(adminState.pending.productDbRules.get(k))) {
    adminState.pending.productDbRules.delete(k);
  }
  refreshPendingUI();
}
// 스테이징된 규칙 편집이 있는 (product, datasource) 수.
function productDbRuleDirtyCount() {
  let n = 0;
  adminState.pending.productDbRules.forEach((e) => { if (!_dbRulePendingEntryEmpty(e)) n += 1; });
  return n;
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

// TASK-AIOPS: AI 운영 현황 패널 상태 (첫 진입 시 lazy-load, 새로고침 버튼으로 재조회).
adminState.aiOps = { initialized: false, data: null };

// TASK-20260623T014626-quota-ui-relocate: LLM 토큰 사용 한도 편집기 — 역할 상세 / 계정 상세 공용.
// (감사>LLM 사용량 화면에서 각 역할/계정 상세 속성으로 이전.)
//   opts = { scope: "role"|"account", id, daily, monthly, onSaved, inheritNote?, readOnly? }
//   값: 빈칸=상속(역할 기본은 무제한, 계정은 역할 기본 사용), 0=무제한(명시), 1 이상=한도, 1=사실상 차단.
//   TASK-20260623T030418-quota-rbac-permission: readOnly=true(quota.read 만 보유, quota.manage 없음)
//     → 입력 비활성 + 저장 버튼 제거 + "조회 전용" 안내. 섹션 자체는 quota.read 없으면 호출측이 미렌더.
function buildQuotaEditor(opts) {
  const readOnly = Boolean(opts.readOnly);
  const fmtVal = (v) => (v === null || v === undefined ? "" : String(v));
  const wrap = document.createElement("div");
  wrap.className = "admin-quota-editor";
  const dailyPlaceholder = opts.scope === "account" ? "일일(역할 기본 상속)" : "일일(무제한)";
  const monthlyPlaceholder = opts.scope === "account" ? "월간(역할 기본 상속)" : "월간(무제한)";
  // 비신뢰 값(한도 숫자·inheritNote)은 innerHTML 보간 대신 DOM 프로퍼티(.value/.textContent)로 주입.
  //   admin.html 은 app.js 를 로드하지 않아 escapeHtml 이 admin.js 스코프에 미정의 — 보간 시 ReferenceError.
  //   placeholder/힌트는 정적 문자열(scope 파생)이라 안전, 사용자 값은 DOM 프로퍼티로 분리한다.
  wrap.innerHTML =
    '<div class="admin-quota-fields">' +
    `  <label class="admin-quota-field"><span>일일 한도</span><input type="number" min="0" class="admin-search admin-quota-daily" placeholder="${dailyPlaceholder}" /></label>` +
    `  <label class="admin-quota-field"><span>월간 한도</span><input type="number" min="0" class="admin-search admin-quota-monthly" placeholder="${monthlyPlaceholder}" /></label>` +
    '</div>' +
    `<p class="admin-quota-hint">토큰 수 기준. 빈칸=${opts.scope === "account" ? "역할 기본값 사용" : "무제한"}, 0=무제한(명시), <strong>전면 차단은 1</strong>. 초과 시 해당 사용자의 새 요청이 일시 제한됩니다.</p>` +
    (readOnly ? "" : '<button type="button" class="btn-secondary admin-quota-save">한도 저장</button>');
  const dailyInput = wrap.querySelector(".admin-quota-daily");
  const monthlyInput = wrap.querySelector(".admin-quota-monthly");
  dailyInput.value = fmtVal(opts.daily);
  monthlyInput.value = fmtVal(opts.monthly);
  const saveBtn = wrap.querySelector(".admin-quota-save");
  if (opts.inheritNote) {
    const note = document.createElement("p");
    note.className = "admin-quota-hint";
    note.textContent = opts.inheritNote;
    wrap.insertBefore(note, saveBtn || null);
  }
  if (readOnly) {
    // 조회 전용 — 입력 비활성 + 안내. 저장 버튼은 애초에 렌더하지 않음(quota.manage 미보유).
    dailyInput.disabled = true;
    monthlyInput.disabled = true;
    const ro = document.createElement("p");
    ro.className = "admin-quota-hint admin-quota-readonly";
    ro.textContent = "조회 전용입니다 — 한도를 변경하려면 ‘LLM 사용 한도 조절’ 권한이 필요합니다.";
    wrap.appendChild(ro);
    return wrap;
  }
  saveBtn.addEventListener("click", async () => {
    const d = wrap.querySelector(".admin-quota-daily").value.trim();
    const m = wrap.querySelector(".admin-quota-monthly").value.trim();
    saveBtn.disabled = true;
    try {
      await apiFetch(`/api/admin/quotas/${opts.scope}/${Number(opts.id)}`, {
        method: "PUT",
        body: JSON.stringify({ daily: d === "" ? null : Number(d), monthly: m === "" ? null : Number(m) }),
      });
      showToast("사용 한도를 저장했습니다.");
      if (typeof opts.onSaved === "function") await opts.onSaved();
    } catch (err) {
      saveBtn.disabled = false;
      showToast(`한도 저장 실패: ${err.message || err}`, true);
    }
  });
  return wrap;
}

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
  // TASK-AIOPS: AI 운영 현황 탭 — console.aiops.read 게이트. **필수(fail-open 방지)** — canSeeTab()
  //   은 매핑 없는 탭을 fail-open(전원 노출)하므로, 이 항목 누락 = 권한 없는 사용자에게 ai-ops 탭
  //   버튼 노출. cosmetic 이 아니라 enforcement 배선. key 는 data-admin-tab 과 동일한 "ai-ops"(hyphen).
  "ai-ops": ["console.aiops.read"],
  archives: ["conversation.archive.read.any"],
  // TASK-20260623T090440-sample-feedback-curation (ROADMAP ITEM-03): 피드백→샘플쿼리 KB 환류 검수 큐.
  "sample-review": ["kb.sample.curate"],
  // TASK-20260624-item11-metadata-glossary-enum (ROADMAP ITEM-11 MVP-1): 용어/ENUM 메타데이터 CRUD.
  // scope-key-unify: samples 서브뷰는 kb.sample.curate 권한이라, 부모 탭 게이트도 OR 로 넓혀
  // kb.sample.curate 단독 보유 큐레이터가 메타데이터 탭→samples 서브뷰에 도달 가능하게 한다
  // (서브뷰별 가시성은 _METADATA_SUBTAB_PERM 가 별도 분기).
  // graph-panel-perms(task4): 세부 권한 중 하나라도 있으면 탭 노출.
  //   kb.ingest.manual(묶음)은 함의로 아래 관리 권한을 effective 보유하므로 명시성 위해 유지.
  //   feature-0016 §45: graph.read 는 여기서 제거 — 그래프 뷰가 별도 최상위 탭(ADMIN_TAB_PERMISSIONS.graph)이 되어
  //   메타데이터 서브탭에서 빠졌으므로, graph.read 만 가진 역할이 서브탭 없는 빈 메타데이터 탭을 보지 않게 한다.
  metadata: ["kb.ingest.manual", "metadata.glossary.manage", "metadata.enum.manage",
             "metadata.table.manage", "metadata.column.manage",
             "kb.sample.curate", "kb.glossary.curate"],
  // feature-0016 §45: 그래프 뷰 최상위 탭 — metadata.graph.read 게이트(kb.ingest.manual 묶음이 함의).
  //   **필수(fail-open 방지)** — canSeeTab() 은 매핑 없는 탭을 fail-open 하므로 누락 = 권한 없는 사용자에게 탭 노출.
  graph: ["metadata.graph.read", "kb.ingest.manual"],
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

// ── TASK-AIOPS: AI 운영 현황 패널 (관리 콘솔 > 감사 > AI 운영 현황) ──────────────
// TASK-AIOPS-paging: 활동 row HTML(초기 렌더 + '더 보기' append 공용) — 자체 esc/포맷(모듈 스코프).
function _aiOpsEscApg(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function _aiOpsFmtNumApg(v) { return v == null ? "0" : Number(v).toLocaleString(); }
function _aiOpsFmtMsApg(v) { return v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(2) + "s" : Math.round(v) + "ms"); }
function _aiOpsFmtUsdApg(v) { return v == null ? "—" : "$" + (Number(v) < 1 ? Number(v).toFixed(4) : Number(v).toFixed(2)); }
// TASK-20260702-audit-nav-ux: 활동 행 = 클릭 요약 행 + 숨김 상세 패널(인라인 아코디언).
//   상세 구조는 참조 드릴다운(차트→대화 목록)과 동일한 "요약→상세" 흐름 — 단건 llm_usage 이므로
//   해당 호출의 전체 회계(토큰 분해·모델·지연·비용·run_id) + 연결 대화(conversation_id) 드릴다운.
//   행/상세 모두 HTML 문자열이라 페이징 '더 보기' append 와 호환(위임 토글이 append 행도 커버).
function aiOpsActivityRowsHtml(items) {
  const E = _aiOpsEscApg;
  return (items || []).map((r) => {
    // 과거 기록 페이징이라 연도까지 표시(YYYY-MM-DD HH:MM:SS) — 연도 경계 넘어가는 모호성 방지.
    const ts = String(r.created_at || "").replace("T", " ").slice(0, 19);
    const reqM = r.req_model || "";
    const srvM = r.resolved_model || r.model || "";
    const modelDetail = (reqM && srvM && reqM !== srvM) ? (E(reqM) + " → " + E(srvM)) : E(srvM || reqM || "—");
    const cid = r.conversation_id;
    // 예약 sentinel(__insight_worker__·__ask_worker__·__global__·__kb_manual__ 등, 전부 "__" 접두)은
    // 실제 사용자 대화가 아니라 시스템·자율 호출 스코프 → 열 수 없는 링크 대신 정직 안내(깨진 링크 방지).
    const isSysConv = !!cid && String(cid).slice(0, 2) === "__";
    const convHtml = (cid && !isSysConv)
      ? `<a href="/?conversation=${encodeURIComponent(cid)}" target="_blank" rel="noopener">대화 열기 ↗</a> <span style="color:#8c959f">${E(String(cid).slice(0, 8))}…</span>`
      : (isSysConv
          ? `<span style="color:#8c959f">시스템·자율 호출 (${E(cid)}) — 특정 대화에 귀속되지 않습니다.</span>`
          : `<span style="color:#8c959f">시스템·자율 호출 — 특정 대화에 귀속되지 않습니다.</span>`);
    const dl = (kk, vv) => `<span style="color:#8c959f">${E(kk)}</span><span style="min-width:0;word-break:break-word">${vv}</span>`;
    const detail =
      `<div class="aiops-act-detail" style="display:none;padding:8px 12px 10px 24px;background:#f6f8fa;border-bottom:1px solid #f0f2f4;font-size:12px">`
      + `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 14px;align-items:baseline">`
      + dl("시각", E(ts))
      + dl("작업", `<b>${E(r.label)}</b> <span style="color:#8c959f">(${E(r.task)})</span>`)
      + (r.target ? dl("대상", `<span style="font-family:monospace;word-break:break-all">${E(r.target)}</span>`) : "")  // 0032: 인사이트 분석 대상
      + dl("모델", modelDetail)
      + dl("토큰", `${_aiOpsFmtNumApg(r.prompt_tokens)} 프롬프트 · ${_aiOpsFmtNumApg(r.completion_tokens)} 완료 · <b>${_aiOpsFmtNumApg(r.total_tokens)}</b> 합계`)
      + dl("추정 비용", _aiOpsFmtUsdApg(r.cost_usd))
      + dl("왕복", _aiOpsFmtMsApg(r.latency_ms))  // 호출 전체 왕복(생성 포함). KPI '단계 간 간격' 은 라운드 사이 gap(step_gap_ms) 별도 축.
      + dl("요청 ID", r.run_id ? `<span style="font-family:monospace;font-size:11px">${E(r.run_id)}</span>` : "—")
      + dl("연결 대화", convHtml)
      + `</div></div>`;
    const row =
      `<div class="aiops-act-row" role="button" tabindex="0" aria-expanded="false" title="클릭하면 이 활동의 상세를 봅니다" style="cursor:pointer;display:flex;gap:10px;padding:3px 0;border-bottom:1px solid #f0f2f4">`
      + `<span class="aiops-act-caret" aria-hidden="true" style="width:12px;flex:none;color:#8c959f">▸</span>`
      + `<span style="color:#57606a;width:118px;flex:none">${E(ts)}</span>`
      + `<span style="flex:1;min-width:0"><b>${E(r.label)}</b>`
      // 0032: 인사이트 분석 '대상'(schema/schema.table/노드 FQN)을 라벨 옆에 인라인 표시 —
      //   '테이블 분석'·'그래프 노드 분석' 이 어떤 대상에 동작하는지 목록에서 바로 관측. 대상 없으면 생략.
      + (r.target ? ` <span class="aiops-act-target" style="color:#0a5b66;font-family:monospace;font-size:11.5px;word-break:break-all" title="분석 대상">${E(r.target)}</span>` : "")
      + ` <span style="color:#8c959f">${E(r.model || "")}</span></span>`
      + `<span style="color:#57606a;width:74px;text-align:right">${_aiOpsFmtNumApg(r.total_tokens)} tok</span>`
      + `<span style="color:#57606a;width:60px;text-align:right">${_aiOpsFmtMsApg(r.latency_ms)}</span>`
      + `</div>`;
    return `<div class="aiops-act">` + row + detail + `</div>`;
  }).join("");
}

// 활동 행 상세 토글(인라인 아코디언). 대화 링크 클릭은 토글에서 제외.
function _toggleAiOpsActRow(row) {
  const item = row.closest ? row.closest(".aiops-act") : null;
  const detail = item ? item.querySelector(".aiops-act-detail") : null;
  if (!detail) return;
  const open = !detail.style.display || detail.style.display === "none";
  detail.style.display = open ? "block" : "none";
  row.setAttribute("aria-expanded", open ? "true" : "false");
  const caret = row.querySelector(".aiops-act-caret");
  if (caret) caret.textContent = open ? "▾" : "▸";
}
// aiOpsActivityList 위임 배선(초기 렌더 + 페이징 append 공용). 요소 재생성마다 1회 바인딩.
function bindAiOpsActivityToggle(list) {
  if (!list || list._aiOpsActBound) return;
  list._aiOpsActBound = true;
  list.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("a")) return; // 대화 열기 링크는 토글 아님
    const row = e.target.closest ? e.target.closest(".aiops-act-row") : null;
    if (row && list.contains(row)) _toggleAiOpsActRow(row);
  });
  list.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    const row = e.target.closest ? e.target.closest(".aiops-act-row") : null;
    if (row && list.contains(row)) { e.preventDefault(); _toggleAiOpsActRow(row); }
  });
}

// '더 보기' — cursor(id) keyset 페이징으로 더 오래된 활동을 조회해 목록에 append.
async function loadAiOpsMoreActivity() {
  const btn = $("aiOpsActivityMore");
  const list = $("aiOpsActivityList");
  if (!btn || !list) return;
  const cursor = btn.getAttribute("data-cursor") || "";
  btn.disabled = true;
  btn.textContent = "불러오는 중…";
  try {
    const data = await apiFetch("/api/admin/ai-ops/activity?cursor=" + encodeURIComponent(cursor));
    // 계측 저장소(PG) 일시 미가용은 HTTP 200 + pg_available:false 로 오므로 '과거 끝'으로 오인 금지 —
    // 재시도 가능 상태로 복구(빈 items 를 append 하지도, 버튼을 영구 disable 하지도 않음).
    if (data.pg_available === false) {
      btn.disabled = false;
      btn.textContent = "더 보기 (재시도)";
      return;
    }
    list.insertAdjacentHTML("beforeend", aiOpsActivityRowsHtml(data.items || []));
    if (data.next_cursor != null) {
      btn.setAttribute("data-cursor", String(data.next_cursor));
      btn.disabled = false;
      btn.textContent = "더 보기";
    } else {
      btn.textContent = "과거 기록 끝";
      btn.disabled = true;   // 더 이상 없음
    }
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "더 보기 (재시도)";
  }
}

async function loadAiOps() {
  const body = $("aiOpsBody");
  if (body) body.innerHTML = '<div class="admin-detail-empty">불러오는 중…</div>';
  try {
    const data = await apiFetch("/api/admin/ai-ops");
    adminState.aiOps.data = data;
    renderAiOps(data);
  } catch (e) {
    const msg = String((e && e.message) || e).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    if (body) body.innerHTML = '<div class="admin-detail-empty">AI 운영 현황을 불러오지 못했습니다: ' + msg + "</div>";
  }
}

function renderAiOps(data) {
  const body = $("aiOpsBody");
  if (!body || !data) return;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const SC = { ok: "#1a7f37", degraded: "#9a6700", down: "#cf222e", unknown: "#57606a", na: "#8c959f" };
  const SL = { ok: "정상", degraded: "저하", down: "중단", unknown: "부분 가시", na: "해당 없음" };
  const chip = (st) => `<span style="display:inline-block;padding:1px 9px;border-radius:11px;font-weight:600;font-size:12px;color:#fff;background:${SC[st] || "#57606a"}">${esc(SL[st] || st)}</span>`;
  const fmtMs = (v) => (v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(2) + "s" : Math.round(v) + "ms"));
  const fmtUsd = (v) => (v == null ? "—" : "$" + Number(v).toFixed(Number(v) < 1 ? 4 : 2));
  const fmtNum = (v) => (v == null ? "0" : Number(v).toLocaleString());
  const b = data.banner || {}, k = data.kpis || {}, lat = k.latency || {}, a24 = k.activity_24h || {};
  const axes = data.axes || [];
  let h = "";
  // 상태 배너
  h += `<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">`
    + `<span style="font-size:15px;font-weight:700">종합 상태</span>${chip(b.state)}`
    + `<span style="color:#57606a;font-size:12px;margin-left:auto">최근 ${esc(data.window_days)}일 · ${esc(String(data.generated_at || "").replace("T", " ").slice(0, 19))}</span></div>`;
  // 상태 축
  h += `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">`
    + axes.map((a) => `<span style="border:1px solid #d0d7de;border-radius:8px;padding:6px 10px;font-size:12px"><b>${esc(a.label)}</b> ${chip(a.state)} <span style="color:#57606a">${esc(a.detail || "")}</span></span>`).join("")
    + `</div>`;
  // KPI 타일
  const kpi = (label, value, sub) => `<div style="flex:1 1 150px;border:1px solid #d0d7de;border-radius:8px;padding:10px 12px"><div style="color:#57606a;font-size:12px">${esc(label)}</div><div style="font-size:18px;font-weight:700;margin-top:2px">${value}</div>${sub ? `<div style="color:#57606a;font-size:11px;margin-top:2px">${esc(sub)}</div>` : ""}</div>`;
  h += `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px">`
    + kpi("워커 정상", `${esc(k.workers_ok)}/${esc(k.workers_total)}`, "요청·인사이트 워커")
    + kpi("24시간 활동", fmtNum(a24.calls) + "회", (a24.requests || 0) + "개 요청")
    + kpi("단계 간 간격 p50 / p95", fmtMs(lat.p50_ms) + " / " + fmtMs(lat.p95_ms), "추론 단계 사이(도구·오케스트레이션) · 다단계 요청 " + (lat.multistep_requests || 0) + "/" + (lat.agent_requests || 0) + " · 간격 " + (lat.measured_calls || 0) + "건")
    + `</div>`;
  // Attention
  const att = data.attention || [];
  if (att.length) {
    h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">주의 필요</div>`
      + att.map((x) => `<div style="display:flex;gap:8px;align-items:center;border-left:3px solid ${SC[x.level] || "#9a6700"};background:#f6f8fa;padding:6px 10px;border-radius:4px;margin-bottom:4px">${chip(x.level)}<b>${esc(x.label)}</b><span style="color:#57606a;font-size:12px">${esc(x.detail || "")}</span></div>`).join("")
      + `</div>`;
  }
  // 카테고리 드릴다운
  const cats = data.categories || [];
  h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">AI 활동 카테고리 (최근 ${esc(data.window_days)}일)</div>`;
  if (cats.length) {
    h += `<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="text-align:left;color:#57606a;border-bottom:1px solid #d0d7de"><th style="padding:4px 6px">카테고리 / 활동</th><th style="padding:4px 6px">호출</th><th style="padding:4px 6px">토큰</th><th style="padding:4px 6px">추정 비용 · 간격 p95</th></tr></thead><tbody>`;
    cats.forEach((c) => {
      h += `<tr style="border-bottom:1px solid #eaeef2"><td style="padding:4px 6px"><b>${esc(c.label)}</b></td><td style="padding:4px 6px">${fmtNum(c.calls)}</td><td style="padding:4px 6px">${fmtNum(c.total_tokens)}</td><td style="padding:4px 6px">${fmtUsd(c.cost_usd)}</td></tr>`;
      (c.tasks || []).forEach((t) => {
        const p95 = (t.p95_ms != null) ? "간격 p95 " + fmtMs(t.p95_ms) : "";
        h += `<tr style="color:#57606a"><td style="padding:2px 6px 2px 20px">· ${esc(t.label)} <span style="font-size:11px">(${esc(t.task)})</span></td><td style="padding:2px 6px">${fmtNum(t.calls)}</td><td style="padding:2px 6px">${fmtNum(t.total_tokens)}</td><td style="padding:2px 6px;font-size:11px">${esc(p95)}</td></tr>`;
      });
    });
    h += `</tbody></table>`;
  } else {
    h += `<div style="color:#57606a;font-size:13px">${data.pg_available ? "기간 내 기록된 AI 활동이 없습니다." : "계측 저장소(PG)를 조회할 수 없어 활동을 표시할 수 없습니다."}</div>`;
  }
  h += `</div>`;
  // 최근 활동 feed
  const act = data.activity || [];
  if (act.length) {
    h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">최근 활동</div>`
      + `<div style="font-size:12px" id="aiOpsActivityList">`
      + aiOpsActivityRowsHtml(act)
      + `</div>`
      + (data.activity_next_cursor != null
          ? `<div style="margin-top:8px;text-align:center"><button type="button" id="aiOpsActivityMore" class="btn-secondary" data-cursor="${esc(String(data.activity_next_cursor))}">더 보기</button></div>`
          : "")
      + `</div>`;
  }
  // 계측 커버리지 (정직 노출)
  const cov = data.coverage || {};
  h += `<div style="border-top:1px solid #d0d7de;padding-top:10px;font-size:12px;color:#57606a">`
    + `<div style="font-weight:700;color:#24292f;margin-bottom:4px">계측 커버리지</div>`
    + `<div>계측됨: ${esc((cov.instrumented || []).join(", "))}</div>`
    + `<div style="margin-top:3px">미계측: ${(cov.uninstrumented || []).map((u) => esc(u.name) + " (" + esc(u.reason) + ")").join("; ")}</div>`
    + (cov.note ? `<div style="margin-top:3px;font-style:italic">${esc(cov.note)}</div>` : "")
    + `</div>`;
  body.innerHTML = h;
  // '더 보기' 배선(innerHTML 재설정 후이므로 매 렌더마다 재바인딩).
  const _moreBtn = $("aiOpsActivityMore");
  if (_moreBtn) _moreBtn.addEventListener("click", loadAiOpsMoreActivity);
  // TASK-20260702-audit-nav-ux: 활동 행 클릭 상세 확장 위임 배선(페이징 append 행도 커버).
  const _actList = $("aiOpsActivityList");
  if (_actList) bindAiOpsActivityToggle(_actList);
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
    // TASK-20260623T014626-quota-ui-relocate: 사용 한도 설정은 역할/계정 상세 화면으로 이전(이 화면은 조회 전용).
  }
  // TASK-AIOPS: AI 운영 현황 tab 첫 진입 시 로드.
  if (tabName === "ai-ops" && !adminState.aiOps.initialized) {
    adminState.aiOps.initialized = true;
    loadAiOps();
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
  // TASK-20260623T090440-sample-feedback-curation: 샘플 검수 tab 첫 진입 시 큐 로드.
  if (tabName === "sample-review" && !adminState.sampleReviewInitialized) {
    adminState.sampleReviewInitialized = true;
    loadSampleFeedback();
  }
  // TASK-20260624-item11-metadata-glossary-enum: 메타데이터 tab 첫 진입 시 scope 드롭다운+목록 초기화.
  if (tabName === "metadata") {
    if (!adminState.metadataInitialized) {
      adminState.metadataInitialized = true;
      initMetadataTab();
    } else {
      // 재진입(REV MINOR-2): 첫 진입이 datasources 로드 전이었을 수 있으니 scope/부트스트랩 DS 드롭다운 재채움(선택 보존).
      _metaPopulateScopeSelect();
      // feature-0016 §45(적대리뷰 D1 대칭): 그래프 탭에서 데이터소스를 바꿨으면 메타데이터 목록도 그 스코프로 재로드(값↔목록 불일치 방지).
      if ((adminState.metadata.loadedScope || "common") !== (adminState.metadata.scopeKey || "common")) loadMetadata();
      _metaApplySubtabPermissions();
      _metaSyncGlossaryViews();        // 재진입 시 용어사전 2차 보기 strip 가시성·active 재동기화(권한 변동 방어).
      _metaRenderDetail();             // metadata-list-detail: 우측 상세(현재 모드)·목록 툴바·부트스트랩 가시성 재동기화.
      _metaPrimeReviewBadge();         // 검토 큐 pending 배지 best-effort 재반영(다른 화면에서 큐 변동 시 stale 방지).
    }
  }
  // feature-0016 §45: 그래프 뷰 최상위 탭 — 첫 진입 시 그래프 init + roots 로드, 재진입은 탐색 상태 보존(리사이즈만).
  if (tabName === "graph") {
    _metaPopulateScopeSelect();   // graphScopeSelect 옵션 채움/갱신(선택 보존) — datasources 로드 후 재진입 대비.
    if (!adminState.graphInitialized) {
      adminState.graphInitialized = true;
      _metaShowGraph();
    } else if (_metaGraph.graph) {
      _metaRoleLegendTips();
      // feature-0016 §45(적대리뷰 D1): 다른 탭에서 데이터소스(scopeKey)를 바꿨으면 재진입 시 그 스코프로 재로드한다.
      //   _metaPopulateScopeSelect 가 graphScopeSelect 값은 새 스코프로 동기화하지만 canvas 는 별도라, 재로드 없이는
      //   'select 는 dsB · 그래프는 dsA' 무성(silent) 불일치가 남는다. loadedScope(마지막 렌더 스코프)와 비교해 diverge 시만 재로드.
      if ((_metaGraph.loadedScope || "common") !== (adminState.metadata.scopeKey || "common")) {
        _metaGraphLoadRoots();
      } else {
        try { if (_metaGraph.graph.resize) _metaGraph.graph.resize(); } catch (_) {}
      }
    }
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

/* ── TASK-20260623T090440-sample-feedback-curation (ROADMAP dba-ai-nl2sql ITEM-03) ──────
 * "샘플 검수" 탭 — 사용자 답변 피드백(👍/👎/"샘플 등록")으로 적재된 sample_feedback(pending)
 * 큐를 검토해 KB(sample_queries)로 승급(approve)하거나 거부(reject)한다. 권한 kb.sample.curate.
 *   GET  /api/admin/sample-feedback              — 큐 목록
 *   POST /api/admin/sample-feedback/{id}/approve — 승급(promote)
 *   POST /api/admin/sample-feedback/{id}/reject  — 거부(reject)
 * 승급은 검색 정확도에 직접 영향 → 명시 검수만(자동학습 금지). generated_sql 은 적재 시점에
 * PII 마스킹돼 저장됨(표시 안전). */
adminState.sampleReview = { items: [], loading: false, truncated: false };

function _sfEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function _sfFmtDt(s) {
  if (!s) return "—";
  try { const d = new Date(s); return isNaN(d.getTime()) ? _sfEsc(s) : d.toLocaleString(); } catch (_) { return _sfEsc(s); }
}

async function loadSampleFeedback() {
  const listEl = document.getElementById("sampleReviewList");
  if (!listEl) return;
  adminState.sampleReview.loading = true;
  listEl.innerHTML = '<div class="admin-list-empty">로딩 중…</div>';
  try {
    const data = await apiFetch("/api/admin/sample-feedback");
    adminState.sampleReview.items = (data && data.items) || [];
    adminState.sampleReview.truncated = Boolean(data && data.truncated);
  } catch (err) {
    adminState.sampleReview.items = [];
    listEl.innerHTML = `<div class="admin-list-empty">${_sfEsc((err && err.message) || "샘플 피드백 조회 실패")}</div>`;
    return;
  } finally {
    adminState.sampleReview.loading = false;
  }
  renderSampleFeedbackList();
}

function renderSampleFeedbackList() {
  const listEl = document.getElementById("sampleReviewList");
  const countEl = document.getElementById("sampleReviewCount");
  if (!listEl) return;
  const items = adminState.sampleReview.items;
  if (countEl) countEl.textContent = `${items.length}건${adminState.sampleReview.truncated ? "+" : ""} 검수 대기`;
  const canCurate = can("kb.sample.curate");
  if (!items.length) {
    listEl.innerHTML = '<div class="admin-list-empty">검수 대기 중인 샘플 피드백이 없습니다.</div>';
    return;
  }
  listEl.innerHTML = items.map((it) => {
    const voteBadge = it.vote === "down"
      ? '<span class="sf-vote sf-vote-down" title="부정 피드백">👎</span>'
      : '<span class="sf-vote sf-vote-up" title="긍정 피드백">👍</span>';
    const suggestedBadge = it.suggested ? '<span class="sf-badge-suggested">샘플 등록 요청</span>' : "";
    const sql = (it.generated_sql || "").trim();
    // 👎 는 승급 불가(코어 promote_feedback 이 down 을 거부) → 승인 버튼 미노출, 거부만.
    const approveBtn = (canCurate && it.vote !== "down")
      ? `<button type="button" class="btn-primary sf-approve" data-sf-id="${it.id}">승인(KB 등록)</button>`
      : "";
    const rejectBtn = canCurate
      ? `<button type="button" class="btn-secondary sf-reject" data-sf-id="${it.id}">거부</button>`
      : "";
    return `
      <div class="admin-sf-row" data-sf-row="${it.id}">
        <div class="admin-sf-row-head">
          ${voteBadge}
          <span class="admin-sf-scope" title="데이터소스 스코프">${_sfEsc(_metaDatasourceLabelOf(it.scope_key))}</span>
          ${suggestedBadge}
          <span class="admin-sf-ts">${_sfEsc(_sfFmtDt(it.created_at))}</span>
        </div>
        <div class="admin-sf-q">${_sfEsc(it.nl_question || "")}</div>
        ${sql ? `<pre class="admin-sf-sql"><code>${_sfEsc(sql)}</code></pre>` : '<div class="admin-sf-nosql muted">생성 SQL 없음</div>'}
        <div class="admin-sf-actions">${approveBtn}${rejectBtn}</div>
      </div>`;
  }).join("");

  listEl.querySelectorAll(".sf-approve").forEach((btn) => {
    btn.addEventListener("click", () => _sampleFeedbackAction(btn, "approve"));
  });
  listEl.querySelectorAll(".sf-reject").forEach((btn) => {
    btn.addEventListener("click", () => _sampleFeedbackAction(btn, "reject"));
  });
}

async function _sampleFeedbackAction(btn, action) {
  const id = btn.dataset.sfId;
  if (!id) return;
  if (action === "reject" && !window.confirm("이 피드백을 거부합니다. (sample_queries 에 반영되지 않습니다)")) return;
  const row = document.querySelector(`[data-sf-row="${id}"]`);
  if (row) row.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  try {
    await apiFetch(`/api/admin/sample-feedback/${encodeURIComponent(id)}/${action}`, { method: "POST", body: "{}" });
    // 처리된 항목 제거 + 재렌더(낙관적 제거 후 목록 정합).
    adminState.sampleReview.items = adminState.sampleReview.items.filter((it) => String(it.id) !== String(id));
    renderSampleFeedbackList();
    if (typeof showToast === "function") {
      showToast(action === "approve" ? "샘플 쿼리(KB)로 승급했습니다." : "피드백을 거부했습니다.");
    }
  } catch (err) {
    if (row) row.querySelectorAll("button").forEach((b) => { b.disabled = false; });
    if (typeof showToast === "function") showToast((err && err.message) || "처리 실패", true);
  }
}

/* ── TASK-20260624-item11-metadata-glossary-enum (ROADMAP ITEM-11 MVP-1) ───────────────
 *    + TASK-20260624-item11-metadata-phase2 (Phase 2): 테이블/컬럼 설명·샘플쿼리·부트스트랩 추가.
 * 메타데이터 거버넌스 콘솔 — 5 서브뷰:
 *   glossary/enums/tables/columns = 권한 kb.ingest.manual,  samples = 권한 kb.sample.curate.
 *   tables/columns 는 부트스트랩 UI(스키마 골격 가져와 설명 일괄 입력) 동반.
 * scope: 데이터소스 key(소문자) 또는 'common'(공용) — adminState.datasources(기존 fetch 재사용) + common.
 *        편집/삭제는 항상 현재 선택 scope 행에만 적용(백엔드 scope 가드와 정합).
 * XSS: 모든 사용자 데이터(term/definition/label/code/description/sql/…)는 textContent/escape 로만 DOM 삽입(innerHTML 금지).
 * 백엔드: GET/POST/PUT/DELETE /api/admin/metadata/{glossary|enums|tables|columns},
 *         GET/PUT/DELETE /api/admin/metadata/samples (POST 없음 — 검수 경로가 생성 정본),
 *         GET /api/admin/metadata/bootstrap/schemas?datasource=, POST /api/admin/metadata/bootstrap. */
adminState.metadata = {
  subTab: "glossary",   // glossary | enums | tables | columns | samples
  glossaryView: "list", // 용어사전 2차 보기(IA: 메타데이터 > 용어사전 > {용어 목록 | 용어 검토 큐}). list | review
  scopeKey: "common",
  roleFilter: "",       // 용어사전 역할 필터(0021) — "" = 전체 역할, "*" = 공용만, "<role_key>" = 그 역할
  items: [],
  loading: false,
  editing: null,        // 수정 중인 항목(id 포함) 또는 null(=생성 모드)
  // metadata-list-detail: 우측 상세 컬럼 모드 + 좌측 목록 선택/검색 상태.
  detailMode: "empty",  // empty(미선택 안내) | form(생성/수정 폼) | bootstrap(스키마 골격 일괄)
  selectedId: null,     // 좌측 목록에서 선택된 행 id(.is-active 하이라이트). null=미선택.
  search: "",           // 좌측 목록 검색어(클라이언트 필터 — title/body 부분일치).
  // 대화 자율등록 검토 큐(0021) — 용어사전 하위 '용어 검토 큐' 보기 상태.
  feedback: { items: [], pendingCount: 0, status: "pending", loading: false },
  relationsOpenId: null,   // 유사어 패널이 펼쳐진 용어 id(목록에서 1개만)
  // Phase 2 부트스트랩 상태(테이블/컬럼 서브뷰 전용).
  bootstrap: {
    open: false,
    datasource: "",
    schema: "",
    schemas: [],
    tables: [],         // {schema_name, table_name, columns:[{column_name, data_type}]}
    loading: false,
    saving: false,
    page: 0,            // metadata-bs-paging: 현재 페이지(0-base). 페이징은 "가시성 윈도우"라
                        //   모든 블록은 DOM 유지(저장·AI 일괄은 전체 DOM 수집) — display 토글만.
  },
};

// 서브뷰별 권한 — 서브탭/버튼 표시 게이트(실제 거부는 서버 403). graph-panel-perms(task4): 기능별 세부 권한으로 분리.
const _METADATA_SUBTAB_PERM = {
  glossary: "metadata.glossary.manage",   // 단, 용어사전 서브탭은 OR(kb.glossary.curate) — _metaSubtabVisible 참조.
  enums: "metadata.enum.manage",
  tables: "metadata.table.manage",
  columns: "metadata.column.manage",
  samples: "kb.sample.curate",
  // feature-0016 §45: graph 서브탭 제거 — 그래프 뷰는 지식베이스 최상위 탭(ADMIN_TAB_PERMISSIONS.graph)으로 이관.
};

// 용어사전 2차 보기별 권한(IA: 메타데이터 > 용어사전 > {용어 목록 | 용어 검토 큐}).
const _GLOSSARY_VIEW_PERM = { list: "metadata.glossary.manage", review: "kb.glossary.curate" };

// 용어사전 검토 큐 보기 활성 여부.
function _metaIsGlossaryReview() {
  return adminState.metadata.subTab === "glossary" && adminState.metadata.glossaryView === "review";
}

// 서브탭 표시 게이트 — 용어사전은 목록(kb.ingest.manual) 또는 검토 큐(kb.glossary.curate) 권한 중
// 하나라도 있으면 표시(검토 큐를 용어사전 하위로 중첩했으므로 curate-only 사용자의 접근 보존).
function _metaSubtabVisible(sub) {
  if (sub === "glossary") return can("metadata.glossary.manage") || can("kb.glossary.curate");
  const perm = _METADATA_SUBTAB_PERM[sub];
  return !perm || can(perm);
}

// 생성 폼 비활성 서브뷰 — samples 는 검수 경로(ITEM-03)가 생성 정본이라 수정 전용. graph 는 읽기 전용 탐색.
const _METADATA_NO_CREATE = { samples: true };

// 서브뷰별 폼 필드 정의 — label/key/type/required/placeholder/min/max. 렌더/검증/payload 조립에 공용 사용.
// type: text | textarea | number | checkbox.
const _METADATA_FIELDS = {
  glossary: [
    // 역할 차원(0021, role-single-ui): 폼 역할 select 폐기 — 역할 선택 UI 를 툴바 하나로 일원화.
    //   role_key 는 _metaSubmitForm 에서 주입한다(생성=툴바 역할 컨텍스트, 전체→공용 '*'; 수정=기존 보존).
    { key: "term", label: "용어", required: true, type: "text", placeholder: "예: 활성 사용자" },
    { key: "definition", label: "정의", required: true, type: "textarea", placeholder: "이 용어의 의미/판정 기준" },
  ],
  enums: [
    { key: "schema_name", label: "스키마(선택)", required: false, type: "text", placeholder: "단일 스키마면 비워둠" },
    { key: "table_name", label: "테이블", required: true, type: "text", placeholder: "예: orders" },
    { key: "column_name", label: "컬럼", required: true, type: "text", placeholder: "예: status" },
    { key: "code", label: "코드", required: true, type: "text", placeholder: "예: 1" },
    { key: "label", label: "라벨(의미)", required: true, type: "text", placeholder: "예: 결제완료" },
  ],
  // 테이블 설명 — POST upsert(scope_key,schema_name,table_name). PUT 은 id+scope.
  tables: [
    { key: "schema_name", label: "스키마(선택)", required: false, type: "text", placeholder: "단일 스키마면 비워둠" },
    { key: "table_name", label: "테이블", required: true, type: "text", placeholder: "예: orders" },
    { key: "description", label: "설명", required: true, type: "textarea", placeholder: "이 테이블이 담는 데이터/용도" },
  ],
  // 컬럼 설명 — tables 동형 + column_name.
  columns: [
    { key: "schema_name", label: "스키마(선택)", required: false, type: "text", placeholder: "단일 스키마면 비워둠" },
    { key: "table_name", label: "테이블", required: true, type: "text", placeholder: "예: orders" },
    { key: "column_name", label: "컬럼", required: true, type: "text", placeholder: "예: status" },
    { key: "description", label: "설명", required: true, type: "textarea", placeholder: "이 컬럼이 담는 값/의미" },
  ],
  // 샘플쿼리 — 수정 전용(생성 폼 없음). weight 1~1000 clamp, approved 체크박스.
  samples: [
    { key: "nl_question", label: "자연어 질문", required: true, type: "textarea", placeholder: "이 SQL 이 답하는 질문" },
    { key: "sql", label: "SQL", required: true, type: "textarea", placeholder: "SELECT …" },
    { key: "domain", label: "도메인(선택)", required: false, type: "text", placeholder: "예: sales" },
    { key: "weight", label: "가중치(1~1000)", required: false, type: "number", min: 1, max: 1000, placeholder: "100" },
    { key: "approved", label: "승인됨", required: false, type: "checkbox" },
  ],
};

// XSS — 사용자 데이터는 textContent 로만. (innerHTML 절대 미사용 경로.) sample-review _sfEsc 와 동일 규약.
function _metaEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function _metaFmtDt(v) {
  if (!v) return "";
  try { return formatDateTime(v); } catch (e) { return String(v); }
}

// 탭 첫 진입 — scope 드롭다운 채우기 + 서브탭 권한 게이트 + 폼 바인딩 + 최초 목록 로드.
function initMetadataTab() {
  _metaPopulateScopeSelect();
  _metaApplySubtabPermissions();
  _metaBindControls();
  _metaBindBootstrap();
  _metaRenderDetail();   // metadata-list-detail: 초기 우측 상세 = empty-state + 목록 툴바 가시성.
  _metaPrimeReviewBadge();
  loadMetadata();
}

// 검토 큐 배지 선반영(0021) — 탭 진입 시 pending 건수만 best-effort 로 가져와 서브탭 배지 표시.
async function _metaPrimeReviewBadge() {
  if (!can("kb.glossary.curate")) return;
  try {
    const data = await apiFetch("/api/admin/metadata/glossary-feedback?status=pending");
    _updateGlossaryReviewBadge((data && data.pending_count) || 0);
  } catch (_) { /* best-effort — 배지 없음 */ }
}

// 서브탭 권한 게이트 — 미보유 서브탭 버튼 숨김. 현재 서브탭이 숨겨졌으면 첫 표시 서브탭으로 전환.
// (서버가 실제 403 으로 거부하므로 이는 표시 게이트일 뿐.)
function _metaApplySubtabPermissions() {
  const btns = Array.from(document.querySelectorAll(".admin-meta-subtab"));
  let curVisible = false;
  let firstVisible = null;
  for (const btn of btns) {
    const sub = btn.dataset.metaSubtab;
    const visible = _metaSubtabVisible(sub);
    btn.style.display = visible ? "" : "none";
    if (visible && !firstVisible) firstVisible = sub;
    if (visible && sub === adminState.metadata.subTab) curVisible = true;
  }
  if (!curVisible && firstVisible) {
    adminState.metadata.subTab = firstVisible;
    for (const b of btns) b.classList.toggle("is-active", b.dataset.metaSubtab === firstVisible);
  }
}

// 용어사전 2차 보기 탭 동기화 — 용어사전 서브탭일 때만 노출, 권한별 보기 버튼 게이트 + 현재 보기 유효성 보정.
function _metaSyncGlossaryViews() {
  const strip = document.getElementById("metadataGlossaryViews");
  if (!strip) return;
  const inGlossary = adminState.metadata.subTab === "glossary";
  strip.style.display = inGlossary ? "" : "none";
  if (!inGlossary) return;
  const btns = Array.from(strip.querySelectorAll(".admin-meta-gview"));
  let curOk = false;
  let firstOk = null;
  for (const b of btns) {
    const v = b.dataset.glossaryView;
    const perm = _GLOSSARY_VIEW_PERM[v];
    const vis = !perm || can(perm);
    b.style.display = vis ? "" : "none";
    if (vis && !firstOk) firstOk = v;
    if (vis && v === adminState.metadata.glossaryView) curOk = true;
  }
  // 현재 보기 권한 없음 → 첫 표시 보기로 전환(curate-only=검토 큐, ingest-only=용어 목록).
  if (!curOk && firstOk) adminState.metadata.glossaryView = firstOk;
  for (const b of btns) {
    const active = b.dataset.glossaryView === adminState.metadata.glossaryView;
    b.classList.toggle("is-active", active);
    b.setAttribute("aria-selected", active ? "true" : "false");
  }
}

// scope 드롭다운: '공용(common)' + 등록된 datasource key 목록(기존 adminState.datasources 재사용).
function _metaPopulateScopeSelect() {
  // feature-0016 §45: 메타데이터 pane 스코프 select 와 그래프 pane 자체 스코프 select 를 같은 옵션·선택으로 동기화한다
  //   (그래프가 최상위 pane 으로 분리되며 metadataScopeSelect 를 더 이상 공유하지 못하므로 graphScopeSelect 신설).
  const selMeta = document.getElementById("metadataScopeSelect");
  const selGraph = document.getElementById("graphScopeSelect");
  if (!selMeta && !selGraph) return;
  const opts = [{ value: "common", label: "공용 (common)" }];
  for (const ds of (adminState.datasources || [])) {
    const label = String((ds && ds.key) || "").trim().toLowerCase();
    if (!label) continue;
    // scope-key-unify(死data 수정): option value = 백엔드가 준 scope_key(= 질의 시점 read 와 동일 해소값:
    // DB-등록 ds=엔드포인트 해시, .env 레거시=라벨). 이 값으로 저장해야 ds-scoped 설명/샘플이 읽힌다.
    // 표시는 사람이 읽는 라벨(key). scope_key 가 비면(구버전 백엔드) 라벨로 폴백.
    const scope = String((ds && ds.scope_key) || label).trim().toLowerCase();
    opts.push({ value: scope, label: label });
  }
  // 현재 선택 보존(없으면 common) — 두 select 공통 해소값.
  const cur = adminState.metadata.scopeKey || "common";
  const resolved = opts.some((o) => o.value === cur) ? cur : "common";
  // textContent 기반 option 생성(XSS 안전). 존재하는 select 각각에 동일 옵션/선택 반영.
  for (const sel of [selMeta, selGraph]) {
    if (!sel) continue;
    sel.replaceChildren();
    for (const o of opts) {
      const el = document.createElement("option");
      el.value = o.value;
      el.textContent = o.label;
      sel.appendChild(el);
    }
    sel.value = resolved;
  }
  adminState.metadata.scopeKey = resolved;
}

function _metaBindControls() {
  const sel = document.getElementById("metadataScopeSelect");
  if (sel && !sel.dataset.bound) {
    sel.dataset.bound = "1";
    sel.addEventListener("change", () => {
      adminState.metadata.scopeKey = sel.value || "common";
      adminState.metadata.editing = null;
      adminState.metadata.selectedId = null;
      // scope-single-ds-ui + metadata-list-detail: 스코프가 부트스트랩 DS 를 결정하므로 bootstrap 모드면
      // 유지하며 재동기화(공용=empty-state, 구체 DS=골격 컨트롤·상속 DS·스키마 재로드). form/empty 는 선택 무효 → empty.
      if (adminState.metadata.detailMode !== "bootstrap") adminState.metadata.detailMode = "empty";
      _metaRenderDetail();
      loadMetadata();
    });
  }
  document.querySelectorAll(".admin-meta-subtab").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => {
      const sub = btn.dataset.metaSubtab;
      if (!sub || sub === adminState.metadata.subTab) return;
      adminState.metadata.subTab = sub;
      document.querySelectorAll(".admin-meta-subtab").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.metaSubtab === sub);
      });
      adminState.metadata.editing = null;
      adminState.metadata.selectedId = null;
      adminState.metadata.search = "";
      const searchEl = document.getElementById("metadataSearch");
      if (searchEl) searchEl.value = "";
      // metadata-list-detail: bootstrap 모드는 tables↔columns 간 유지(골격 결과 보존 + 새 mode 재렌더), 그 외 서브탭은 empty.
      if (!(adminState.metadata.detailMode === "bootstrap" && (sub === "tables" || sub === "columns"))) {
        adminState.metadata.detailMode = "empty";
      }
      _metaRenderDetail();
      loadMetadata();
    });
  });
  // 용어사전 2차 보기 탭(용어 목록 / 용어 검토 큐) 전환.
  document.querySelectorAll(".admin-meta-gview").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => {
      const v = btn.dataset.glossaryView;
      if (!v || v === adminState.metadata.glossaryView) return;
      adminState.metadata.glossaryView = v;
      adminState.metadata.editing = null;       // 보기 전환 시 폼 초기화
      adminState.metadata.selectedId = null;
      adminState.metadata.relationsOpenId = null;
      adminState.metadata.search = "";          // 보기 전환 시 검색 초기화(검토 큐는 검색 미적용)
      const sEl = document.getElementById("metadataSearch");
      if (sEl) sEl.value = "";
      adminState.metadata.detailMode = "empty";  // metadata-list-detail: 보기 전환 시 우측 상세 초기화
      _metaRenderDetail();
      loadMetadata();
    });
  });
  const form = document.getElementById("metadataForm");
  if (form && !form.dataset.bound) {
    form.dataset.bound = "1";
    form.addEventListener("submit", _metaSubmitForm);
  }
  const cancelBtn = document.getElementById("metadataCancelBtn");
  if (cancelBtn && !cancelBtn.dataset.bound) {
    cancelBtn.dataset.bound = "1";
    cancelBtn.addEventListener("click", () => { _metaCancelEdit(); });
  }
  const refreshBtn = document.getElementById("metadataRefreshBtn");
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", () => loadMetadata());
  }
  // metadata-list-detail: '+ 새 항목' — 우측 상세에 생성 폼(빈) 진입.
  const newBtn = document.getElementById("metadataNewBtn");
  if (newBtn && !newBtn.dataset.bound) {
    newBtn.dataset.bound = "1";
    newBtn.addEventListener("click", () => {
      adminState.metadata.editing = null;       // 생성 모드.
      adminState.metadata.selectedId = null;
      adminState.metadata.detailMode = "form";
      _metaRenderDetail();
      _metaSyncListActive();
      const first = document.querySelector("#metadataFormFields input, #metadataFormFields textarea");
      if (first && first.focus) try { first.focus(); } catch (_) {}
    });
  }
  // metadata-list-detail: '스키마 골격 가져오기'(테이블/컬럼 일괄) — 우측 상세 bootstrap 모드 토글(다시 누르면 목록 안내로 복귀).
  const bsOpenBtn = document.getElementById("metadataBootstrapOpenBtn");
  if (bsOpenBtn && !bsOpenBtn.dataset.bound) {
    bsOpenBtn.dataset.bound = "1";
    bsOpenBtn.addEventListener("click", () => {
      if (adminState.metadata.detailMode === "bootstrap") {
        adminState.metadata.detailMode = "empty";   // 다시 누르면 닫기(미선택 안내로).
      } else {
        adminState.metadata.editing = null;
        adminState.metadata.selectedId = null;
        adminState.metadata.detailMode = "bootstrap";
        adminState.metadata.bootstrap.open = true;   // 진입 시 본문 펼침.
      }
      _metaRenderDetail();
      _metaSyncListActive();
    });
  }
  // metadata-list-detail: 좌측 목록 검색(클라이언트 필터) — 입력마다 재렌더(선택 하이라이트 보존).
  const searchEl = document.getElementById("metadataSearch");
  if (searchEl && !searchEl.dataset.bound) {
    searchEl.dataset.bound = "1";
    searchEl.addEventListener("input", () => {
      adminState.metadata.search = searchEl.value || "";
      if (_metaIsGlossaryReview()) return;   // 검토 큐는 별도 렌더 경로(loadGlossaryFeedback) — 검색 미적용.
      // 설계 결정(적대 패널 MAJOR-1): 검색은 좌측 목록만 필터한다. 편집 중인 항목이 필터로 가려져도 우측 폼은
      //   유지한다(검색 키 입력으로 진행 중 편집을 폐기하지 않음 — 검색 해제 시 해당 행이 다시 강조된다).
      renderMetadataList();
    });
  }
  // 용어사전 역할 필터(0021) — 변경 시 그 역할 행만 재조회.
  const roleFilter = document.getElementById("metadataRoleFilter");
  if (roleFilter && !roleFilter.dataset.bound) {
    roleFilter.dataset.bound = "1";
    roleFilter.addEventListener("change", () => {
      adminState.metadata.roleFilter = roleFilter.value || "";
      _metaUpdateGlossaryRoleBadge();   // 생성 폼이 열려 있으면 '등록 대상 역할' 배지를 새 컨텍스트로 동기화(표시값=실제 등록값, F5)
      loadMetadata();
    });
  }
  // AI 단건 자동완성 — 식별 필드 → 설명/정의/라벨/질문 생성(검토 후 등록).
  const suggestBtn = document.getElementById("metadataSuggestBtn");
  if (suggestBtn && !suggestBtn.dataset.bound) {
    suggestBtn.dataset.bound = "1";
    suggestBtn.addEventListener("click", () => _metaSuggestFill(suggestBtn));
  }
}

// 현재 메타데이터 scope(scope_key)에 대응하는 datasource 사람-라벨(key) 반환 — tables/columns
// grounding 시 백엔드 introspection 대상 식별용. 'common' 또는 미매칭이면 빈 문자열(=ungrounded).
function _metaScopeDatasourceKey() {
  const scope = adminState.metadata.scopeKey || "common";
  if (scope === "common") return "";
  for (const ds of (adminState.datasources || [])) {
    const label = String((ds && ds.key) || "").trim().toLowerCase();
    const sk = String((ds && ds.scope_key) || label).trim().toLowerCase();
    if (sk === scope || label === scope) return label;
  }
  return "";
}

// scope_key → 사람이 지정한 datasource 라벨(key) 역매핑(표시 전용). scope_key 는 질의축 식별자로,
// DB-등록 datasource 는 엔드포인트 해시(예: mssql-06656002eda6)라 UI 에 raw 노출되면 사람이 못 읽는다.
// adminState.datasources(= GET /api/admin/datasources)의 {key=라벨, scope_key=해시} 로 해시→라벨을 되돌린다.
//   - 빈 값/'common' → '공용'
//   - 미매칭(구버전 백엔드·삭제된 ds·datasources 미로드) → 원문 유지(정보 손실보다 raw 표시가 안전).
function _metaDatasourceLabelOf(scopeKey) {
  const s = String(scopeKey == null ? "" : scopeKey).trim();
  if (!s || s.toLowerCase() === "common") return "공용";
  const low = s.toLowerCase();
  for (const ds of (adminState.datasources || [])) {
    const label = String((ds && ds.key) || "").trim();
    if (!label) continue;
    const sk = String((ds && ds.scope_key) || label).trim().toLowerCase();
    if (sk === low || label.toLowerCase() === low) return label;
  }
  return s;
}

// AI 단건 자동완성 — 폼의 식별 필드를 백엔드로 보내 설명 필드를 생성하고, 대상 입력란에 채운다.
// 생성물은 영속 안 함 — 사용자가 검토 후 '등록/수정 저장' 으로 저장. (XSS: 결과는 input.value 로만.)
async function _metaSuggestFill(btn) {
  const sub = adminState.metadata.subTab;
  const wrap = document.getElementById("metadataFormFields");
  if (!wrap) return;
  const vals = _metaFormValues();
  // 서브뷰별 최소 식별 입력 검증(백엔드와 동치) — 빈 식별자 날조 방지.
  const REQUIRES = {
    glossary: ["term"], enums: ["table_name", "column_name", "code"],
    tables: ["table_name"], columns: ["table_name", "column_name"], samples: ["sql"],
  };
  const LABELS = {
    term: "용어", table_name: "테이블", column_name: "컬럼", code: "코드", sql: "SQL",
  };
  const missing = (REQUIRES[sub] || []).filter((k) => !String(vals[k] || "").trim());
  if (missing.length) {
    if (typeof showToast === "function") {
      showToast(`먼저 ${missing.map((k) => LABELS[k] || k).join(", ")} 을(를) 입력하세요.`, true);
    }
    return;
  }
  const payload = { scope_key: adminState.metadata.scopeKey || "common" };
  for (const k of ["term", "schema_name", "table_name", "column_name", "code", "sql", "nl_question"]) {
    if (vals[k] != null && String(vals[k]).trim()) payload[k] = String(vals[k]).trim();
  }
  if (sub === "tables" || sub === "columns") {
    const dsKey = _metaScopeDatasourceKey();
    if (dsKey) payload.datasource = dsKey;
  }
  const origLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = "AI 생성 중…";
  try {
    const data = await apiFetch(`/api/admin/metadata/${encodeURIComponent(sub)}/suggest`, {
      method: "POST", body: JSON.stringify(payload),
    });
    const target = data && data.target;
    const suggestion = (data && data.suggestion) || "";
    const input = target ? wrap.querySelector(`[name="${target}"]`) : null;
    if (!input) {
      if (typeof showToast === "function") showToast("자동완성 대상 필드를 찾을 수 없습니다.", true);
      return;
    }
    if (!suggestion) {
      if (typeof showToast === "function") showToast("AI 가 생성한 내용이 비어 있습니다. 다시 시도하세요.", true);
      return;
    }
    input.value = suggestion;
    input.focus();
    try { input.setSelectionRange(input.value.length, input.value.length); } catch (_) {}
    const grounded = data && data.meta && data.meta.grounded;
    if (typeof showToast === "function") {
      showToast(grounded ? "AI 자동완성 완료(실제 스키마 반영) — 검토 후 등록하세요." : "AI 자동완성 완료 — 검토 후 등록하세요.");
    }
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "AI 자동완성 실패", true);
  } finally {
    btn.disabled = false;
    btn.textContent = origLabel;
  }
}

// 폼 필드 렌더(서브탭별). 수정 모드면 editing 값 채움. label/input 전부 DOM API(XSS 안전).
// samples 등 생성 비활성 서브뷰는 수정 모드(editing)일 때만 폼을 표시한다(생성 폼 없음).
function _metaRenderForm() {
  const wrap = document.getElementById("metadataFormFields");
  const submitBtn = document.getElementById("metadataSubmitBtn");
  const cancelBtn = document.getElementById("metadataCancelBtn");
  const form = document.getElementById("metadataForm");
  if (!wrap) return;
  const sub = adminState.metadata.subTab;
  const fields = _METADATA_FIELDS[sub] || [];
  const editing = adminState.metadata.editing;
  const noCreate = Boolean(_METADATA_NO_CREATE[sub]);
  _metaSyncGlossaryViews();   // 용어사전 보기 유효성 먼저 보정(권한 없는 보기 → 첫 표시 보기)
  // 용어 검토 큐 보기는 CRUD 폼 없음. 생성 비활성 서브뷰 + 비편집 상태도 폼 숨김(목록 '수정'으로만 진입).
  const isReview = _metaIsGlossaryReview();
  const hideForm = isReview || (noCreate && !editing);
  if (form) form.style.display = hideForm ? "none" : "";
  _metaSyncToolbarVisibility();
  if (isReview) { wrap.replaceChildren(); return; }
  wrap.replaceChildren();
  // 단일 역할 컨텍스트(glossary, role-single-ui): 등록/수정 대상 역할을 읽기전용으로 표시(선택 UI 아님 — 역할 선택은 툴바 하나).
  //   생성=현재 툴바 컨텍스트(전체 역할이면 공용 '*'), 수정=대상 용어의 기존 role_key. 배지 스타일 재사용(추가 CSS 불요).
  //   id 부여 — 툴바 역할 변경 시 폼 전체 재렌더(입력 소실) 없이 배지만 동기화하기 위함(_metaUpdateGlossaryRoleBadge).
  if (sub === "glossary") {
    const field = document.createElement("div");
    field.className = "admin-meta-field";
    field.id = "metadataRoleContextField";
    const cap = document.createElement("span");
    cap.className = "admin-meta-field-label";
    cap.textContent = "등록 대상 역할";
    const badge = document.createElement("span");
    badge.id = "metadataRoleContextBadge";
    const note = document.createElement("span");
    note.id = "metadataRoleContextNote";
    note.className = "admin-meta-row-meta";
    field.appendChild(cap);
    field.appendChild(badge);
    field.appendChild(note);
    wrap.appendChild(field);
    _metaUpdateGlossaryRoleBadge();   // 배지/노트 텍스트 채우기(생성=컨텍스트, 수정=대상 용어 역할)
  }
  for (const f of fields) {
    if (f.type === "checkbox") {
      // 체크박스는 라벨을 input 우측에 배치(가로 정렬).
      const field = document.createElement("label");
      field.className = "admin-meta-field admin-meta-field-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.className = "admin-meta-check";
      input.name = f.key;
      if (editing && (editing[f.key] === true || editing[f.key] === "true" || editing[f.key] === 1)) input.checked = true;
      const cap = document.createElement("span");
      cap.className = "admin-meta-field-label";
      cap.textContent = f.label;
      field.appendChild(input);
      field.appendChild(cap);
      wrap.appendChild(field);
      continue;
    }
    const field = document.createElement("label");
    field.className = "admin-meta-field";
    const cap = document.createElement("span");
    cap.className = "admin-meta-field-label";
    cap.textContent = f.label + (f.required ? " *" : "");
    field.appendChild(cap);
    const input = f.type === "textarea" ? document.createElement("textarea") : document.createElement("input");
    if (f.type === "number") {
      input.type = "number";
      if (f.min != null) input.min = String(f.min);
      if (f.max != null) input.max = String(f.max);
    } else if (f.type !== "textarea") {
      input.type = "text";
    }
    input.className = "admin-meta-input";
    input.name = f.key;
    input.placeholder = f.placeholder || "";
    if (editing && editing[f.key] != null) input.value = String(editing[f.key]);
    field.appendChild(input);
    wrap.appendChild(field);
  }
  if (submitBtn) submitBtn.textContent = editing ? "수정 저장" : "등록";
  if (cancelBtn) cancelBtn.style.display = editing ? "" : "none";
}

function _metaCancelEdit() {
  adminState.metadata.editing = null;
  adminState.metadata.selectedId = null;
  adminState.metadata.detailMode = "empty";
  _metaRenderDetail();
  _metaSyncListActive();
}

// metadata-list-detail: 우측 상세 컬럼 모드 코디네이터 — empty | form | bootstrap 중 하나만 노출한다.
//   다른 카테고리(계정/제품/데이터소스/감사) list-detail 과 동형: 좌측 선택 → 우측 상세 편집.
//   모드 유효성을 보정(검토 큐/생성비활성/권한)한 뒤 세 컨테이너 가시성을 일원 결정하고, form/bootstrap
//   모드는 기존 렌더러(_metaRenderForm / _metaSyncBootstrapVisibility)에 위임한다. 상단 네비(역할 필터·
//   용어 2차 보기·목록 툴바 버튼)는 모드와 무관하므로 항상 동기화한다.
function _metaRenderDetail() {
  const md = adminState.metadata;
  _metaSyncGlossaryViews();   // 용어사전 2차 보기 strip 가시성/active (모드 무관 top-nav).
  let mode = md.detailMode || "empty";
  if (mode === "form") {
    if (_metaIsGlossaryReview()) mode = "empty";                                  // 검토 큐는 CRUD 폼 없음.
    else if (_METADATA_NO_CREATE[md.subTab] && !(md.editing && md.editing.id != null)) mode = "empty";  // samples 생성 비활성.
  }
  // graph-panel-perms(task4): 스키마 골격 부트스트랩은 테이블 골격 도구 → metadata.table.manage 게이트(백엔드 동치).
  if (mode === "bootstrap" && !((md.subTab === "tables" || md.subTab === "columns") && can("metadata.table.manage"))) mode = "empty";
  md.detailMode = mode;
  const empty = document.getElementById("metadataDetailEmpty");
  const form = document.getElementById("metadataForm");
  const boot = document.getElementById("metadataBootstrap");
  if (empty) empty.style.display = mode === "empty" ? "" : "none";
  if (form) form.style.display = mode === "form" ? "" : "none";
  if (boot) boot.style.display = mode === "bootstrap" ? "" : "none";
  if (mode === "form") _metaRenderForm();                 // 폼 필드 채움(생성=빈, 수정=editing 값).
  else if (mode === "bootstrap") _metaSyncBootstrapVisibility();  // 공용=empty-state, 구체 DS=골격 컨트롤.
  _metaSyncToolbarVisibility();   // 역할 필터 가시성(glossary 목록 보기만).
  _metaSyncListToolbar();         // '+ 새 항목' / '스키마 골격 가져오기' 버튼 가시성.
}

// 좌측 목록의 선택 행(.is-active) 동기화 — selectedId 와 매칭되는 행만 강조(다른 패널 list-detail 동형).
function _metaSyncListActive() {
  const listEl = document.getElementById("metadataList");
  if (!listEl) return;
  const sel = adminState.metadata.selectedId;
  listEl.querySelectorAll(".admin-meta-row").forEach((row) => {
    row.classList.toggle("is-active", sel != null && String(row.dataset.metaId) === String(sel));
  });
}

// 좌측 목록 툴바 버튼 가시성 — '+ 새 항목'(생성 가능 서브탭만)·'스키마 골격 가져오기'(테이블/컬럼+권한만).
function _metaSyncListToolbar() {
  const md = adminState.metadata;
  const review = _metaIsGlossaryReview();
  // 검토 큐는 별도 렌더(피드백 큐) — 클라이언트 검색 미적용이라 검색 입력 숨김.
  const searchEl = document.getElementById("metadataSearch");
  if (searchEl) searchEl.style.display = review ? "none" : "";
  const bsBtn = document.getElementById("metadataBootstrapOpenBtn");
  if (bsBtn) {
    const showBs = (md.subTab === "tables" || md.subTab === "columns") && can("metadata.table.manage") && !review;
    bsBtn.style.display = showBs ? "" : "none";
    bsBtn.classList.toggle("is-active", md.detailMode === "bootstrap");   // 진입 상태 시각 표시(토글).
  }
  const newBtn = document.getElementById("metadataNewBtn");
  if (newBtn) {
    const canCreate = !_METADATA_NO_CREATE[md.subTab] && !review && can(_METADATA_SUBTAB_PERM[md.subTab] || "kb.ingest.manual");
    newBtn.style.display = canCreate ? "" : "none";
  }
}

// ── feature-0016: 메타데이터 지식그래프 뷰 (AntV G6 v5 + 투영 API) ─────────────────
//   렌더링 엔진: Cytoscape(WebGL) → AntV G6 v5(Canvas). 근거·설계·검증은
//   unit/feature-0016-metadata-graph/g6-migration/BLUEPRINT.md + DECISIONS ADR-004.
//   구버전 대비 해소: ①클릭접힘 ②위치점프 ③줌 동기화지연(HTML오버레이 제거) ④클러스터 뒤섞임
//   ⑤테두리 왜곡(WebGL 텍스처) — 전부 구조적 해소 + 점선 엣지 복원.
//   아키텍처: JS 모델(_metaGraph.nodes/edges/expanded/…) → _metaG6Build() 로 위치 포함
//   전체 G6 데이터 재구성 → graph.setData()+draw()(증분 add/translate 미사용 — 결정론·안정).
const _metaGraph = {
  graph: null,            // G6 Graph 인스턴스
  bound: false,
  lastQuery: "",
  lastDetailKey: null,
  activeRunId: null,
  _analyzePending: new Set(),  // graphux7(#4): AI 능동 분석 POST in-flight 중인 node key 집합 — 연타 동시 POST(중복 큐잉) 차단(노드별 독립).
  introspected: null,     // Set: information_schema 즉석조회한 테이블 key
  mode: "roots",          // "roots"|"search"|"neighbor" (현재는 전부 결정론 grid)
  nodes: new Map(),       // key -> {key,label,name,fqn,description,source,ordinal,score,rel,cardinality,edge_source}
  edges: new Map(),       // id  -> {id,source,target,type,status,edge_source,weight}
  expanded: new Set(),    // 컬럼 펼친 Table key
  analyzed: new Set(),    // AI 분석 완료 key(보라 마커)
  running: new Set(),     // AI 분석 중 key(주황 마커)
  roles: new Map(),       // node-role-viz: 분석 완료 Table key -> 역할 분류(_META_ROLE 키). 칩 색·아이콘 표식 소스.
  selected: null,         // 선택 강조 key
  // graph-initview: 스키마-우선 진입 상태.
  schemaExpanded: new Set(),  // 테이블을 펼친 Schema key(roots 진입은 스키마 카드만)
  schemaLoaded: new Set(),    // per-schema lazy 로드 완료(정식 schema_tables 응답+테이블>0 시만 — 재펼침 무-refetch)
  schemaLoading: new Set(),   // in-flight per-schema fetch(카드 연타 이중 fetch 차단)
  schemaTruncated: new Set(), // schema_tables 가 cap 절단을 보고한 Schema key
  firstElementId: null,       // 자연정렬 첫 요소 id(줌 클램프 시 시선 앵커, 카드는 SC:)
  renderedIds: null,          // 마지막 build 가 렌더한 요소 id 집합 — 미렌더 모델키 setElementState 차단
  schemaTotals: null,         // graph-initview: scope 별 스키마→전체 테이블 수(roots mode=schemas 에서 캐시). search 리셋에도 보존(카드 badge 전체 수 소스).
  searchMatch: null,          // 검색 필터 뷰: schemaKey -> Set(매칭 테이블 key). 카드 badge = 매칭/전체.
  searchMatchTables: null,    // 검색 매칭 테이블 key Set(펼침 시 강조).
  searchMatchNodes: null,     // feature-0016 §45: 검색 직접 매칭 노드 key Set(테이블/컬럼/용어) — 'match' 상태 soft glow 대상(너비 증가 대체).
  searchCapped: false,        // 검색 결과가 cap(_META_SEARCH_CAP) 도달 → 매칭 카운트는 부분값(badge 에 '+' 표기).
  // graph-perf-bg: 성능 인덱스·논블로킹 상태.
  colsByTable: new Map(), // Table key -> 펼쳐진 Column 개수(O(1) _metaTableHasCols 단일소스 — 매 클릭 전노드 스캔 제거).
  _opSeq: 0,              // 펼침/확장 조작 시퀀스 토큰. await(fetch·yield) 경계마다 대조해 stale 렌더 폐기.
  _stateCache: new Map(), // key -> 마지막 적용된 state signature. _metaGraphRefreshStates 가 변화분만 setElementState.
  _busyKeys: new Map(),   // graph-perf-bg fix: key -> busy 를 세운 _opSeq(소유권). refreshStates 가 busy 를 보존·복원하고, 같은 key 재트리거 시 신 op busy 를 stale op 가 지우지 않게 한다.
  tableDeps: new Map(),   // graph-drag(REQ ②): Table key -> [종속 UI 노드 id](접기 "X:" ctl + 컬럼 노드). 매 _metaG6Build 재구성. 테이블 드래그 시 함께 이동.
  _drag: null,            // graph-drag(REQ ②): 진행 중 테이블 드래그 상태 {id, offs:[{id,ox,oy}]}(종속별 테이블 대비 월드 오프셋). null=비활성.
  _dragZBoosted: new Set(),   // graph-zorder h2(리뷰 MINOR): 드래그 부스트 중 id — rebuild 의 _metaGraphZAssert 가 canonical 로 회수하지 않게 보호(dragend 복원 시 해제).
  aiPrompt: "",           // graph-funcproc(ADR-017): AI 능동 분석 hover 지침 — 세션 내 보존(상세 재렌더 시 prefill).
  // graph-freeplace: 자유 배치 persistence(ADR-004 결정론 배치가 rebuild 마다 초기화하던 것을 복원 — 사용자 후속 회귀 보고).
  //   clusterOffset: 스키마 클러스터(combo) 단위 사용자 드래그 누적 이동(dx,dy) — build 가 L.x0/L.y0 에 가산해 클러스터
  //     전체(카드·테이블·컬럼·장식)를 coherent 하게 이동시키고 rebuild(펼침/접기) 후에도 유지. combo:dragend 가 누적.
  //   nodePos: 개별 노드(주로 테이블) 사용자 드래그 최종 절대위치 — build place-loop 이 그 노드+종속을 델타 시프트해
  //     유지 + combo auto-fit 리사이즈(#3). node:dragend 가 기록. 둘 다 resetModel(스코프 전환·초기화)에서 clear.
  clusterOffset: new Map(),   // comboId(schema key) -> {dx, dy}
  nodePos: new Map(),         // nodeId -> [x, y] (사용자 확정 절대 위치)
  // group-interact(§50): sim-group(카테고리 그룹 = 유사 속성 그룹, ADR-013) 자유 배치·접기 상호작용.
  //   clusterOffset·nodePos 사이 계층(cluster → group → node)의 offset. GB 박스는 멤버 bbox 에서 파생돼
  //   그룹 이동(groupOffset)·개별 노드 이동(nodePos) 양쪽에 반응형으로 맞춰진다(#3). resetModel 에서 clear.
  groupOffset: new Map(),     // groupKey -> {dx, dy} (sim-group 단위 드래그 누적 — clusterOffset 의 그룹판)
  groupCollapsed: new Set(),  // 접힌 sim-group key(멤버 미방출·헤더만)
  groupMembers: new Map(),    // groupKey -> [멤버 테이블 id] (드래그 시 묶음 이동 — 매 build 재구성, 펼친 그룹만)
  groupOf: new Map(),         // 테이블 id -> groupKey (멤버 이동 시 GB 박스 반응형 rebuild 판정 — 매 build 재구성)
  // feature-0016 §49(요구②): 배치 순서 안정화 — 이웃확장/펼침 rebuild 시 re-seriation 으로 노드가 그리드를 점프하지
  //   않도록 직전 클러스터·테이블 순서를 보존하고 신규만 seriated 순서로 append. 드래그(nodePos/clusterOffset)와 직교.
  //   resetModel(스코프 전환·초기화)에서 clear → fresh load 는 순수 seriation.
  clusterOrder: [],           // 안정화된 클러스터(comboId) 순서
  tableOrder: new Map(),      // comboId -> 안정화된 테이블/루틴 key 순서(flat masonry 경로)
  groupOrder: new Map(),      // feature-0016 §49(R1): schemaId -> 안정화된 simgroups 그룹 순서
  groupTableOrder: new Map(), // feature-0016 §49(R1): groupKey -> 안정화된 그룹내 테이블 key 순서
  _comboDragStart: null,      // combo:dragstart 시 {id, x, y}(중심) — dragend 델타 산출용
  // graphux7(#1) + graph-navfilter(§54①): 상세 패널 방문 이력(뒤로/앞으로). datasource 컨텍스트
  //   전환(loadRoots/Products) 시 _metaGraphHistoryReset 로 초기화. _histNav=네비 중(중복 push 억제).
  detailHist: [],             // 방문 스택 — {v:"node"|"cluster"|"rel", k:key} (오래된 앞 → 최근 뒤)
  detailHistIdx: -1,          // 현재 위치 인덱스(-1=비어 있음)
  _histNav: false,            // 뒤로/앞으로 네비게이션 진행 중 플래그
  // graph-navfilter(§54②): 노드 종류 표시 필터 — "edges"|"function"|"procedure" 를 빌드 입력에서
  //   제외(스타일 숨김 아님 — masonry/simgroups/shelf-pack 이 자동 재배치). 테이블·컬럼은 항상 표시.
  //   scope-독립 preference 라 resetModel 에서 clear 하지 않는다(localStorage 영속).
  hiddenKinds: new Set(),
  // graph-navfilter(§54③): 검색이 순수 추가한 노드 key(카드·terms) — 재검색/클리어 시 사용자
  //   미접촉(pristine)만 회수해 펼침·배치·확장은 보존.
  searchAdded: new Set(),
  // §54③ 패널 MAJOR: 검색 진입 직전의 base 컨텍스트 {mode, focusName} — products/중심보기 위에서
  //   검색→클리어 시 원 화면(제품 개요/중심 보기 칩)으로 정확히 복귀·복원하기 위함.
  _searchBase: null,
  _focusName: null,           // 중심 보기 대상 이름(FocusChip 단일소스 미러 — DOM 파싱 회피)
  // graph-navfilter(§54⑤): 파라미터를 펼친 Routine key — 컬럼 펼침(expanded)의 루틴 판.
  routineExpanded: new Set(),
  // graph-category(§55 A, REQ-20260706 ①): 스키마(DB)별 제품 매핑 — 스키마 클러스터를 제품 카테고리
  //   밴드(CAT:/CATH:/CATX:)로 묶는 데이터 원천. key=스키마명 lowercase, val=[{id,name,sort}].
  //   schemaTotals 와 같은 scope 캐시 — resetModel 보존, loadRoots 가 재구축(응답 schema_products).
  schemaProducts: new Map(),
  catOrder: [],               // §49 동형: 카테고리(catKey) 순서 안정화
  catCollapsed: new Set(),    // 접힌 카테고리 catKey(멤버 클러스터 미방출·헤더 밴드만)
  catMembers: new Map(),      // catKey -> [멤버 클러스터(comboId)] — 매 build 재구성(카테고리 드래그 소비)
  catLabelOf: new Map(),      // catKey -> 표시 라벨 — 매 build 재구성(상세·헤더)
};

// ── 결정론적 배치 상수(스키마 클러스터 grid·테이블 스택·컬럼 세로열) ──
const _METtype = "rect";
const _METLAY = { COLS: 3, SW: 300, GAPX: 48, GAPY: 52, PADT: 34, PADX: 16, TROW: 34, CROW: 21, CIND: 26, TGAP: 12, TW: 150,
  CARDW: 210, CARDH: 44 };   // graph-initview: 접힌 스키마 카드 치수
const _META_MIN_READ_ZOOM = 0.55;   // graph-initview(A1): 초기 fit 이 이 배율 밑이면 판독 불가 — 클램프
// graph-zorder(§52): 캔버스 요소 의미 z-스케일 — **단일 소스**. @antv/g 는 (zIndex → 삽입순 renderOrder)로
//   페인팅·hit-test 하므로, 전 요소에 zIndex 를 명시해 setData diff 의 생성 순서·드래그 이력(내장
//   drag-element 의 frontElement 영구 승격)이 페인팅 순서를 결정하지 못하게 한다. 의미 계층:
//   클러스터 배경(COMBO) < 그룹 배경(GROUP_BG) < 관계선(EDGE) < 컬럼(COLUMN) < 칩·카드(NODE)
//   < 그룹 헤더(GROUP_HD, §50 드래그 핸들 hit-test) < 컨트롤(CTL, 항상 클릭 가능). DRAG_BOOST 는
//   드래그 중 임시 부스트 오프셋(canonical+1000) — dragend 에 canonical 복원(_metaDragZRestore).
//   흐름 내 per-table "X:" ctl 은 NODE 밴드(허위 소속 어포던스 방지, 패널 ux MINOR) — 자기 칩과 비겹침이라
//   클릭성 손실 없음. 코너 앵커 컨트롤(GX/XS)만 CTL(항상 클릭 가능).
//   EDGE 층 내부는 신뢰 강도 소수 오프셋(trusted+0.2 > candidate/교차DB+0.1)으로 tie 분해(_metaEdgeStyleFor).
// graph-category(§55 A): CAT_BG(-1) = 제품 카테고리 밴드 배경 — 클러스터 배경(COMBO 0) **아래**.
//   combo 내부 hit-test 는 combo 가 갖고, 밴드 여백·헤더(CATH, GROUP_HD 밴드)가 카테고리 상호작용 표면.
const _METZ = { CAT_BG: -1, COMBO: 0, GROUP_BG: 1, EDGE: 2, COLUMN: 3, NODE: 4, GROUP_HD: 5, CTL: 6, DRAG_BOOST: 1000 };
const _META_SEARCH_CAP = 50;        // search-badge: 백엔드 search_nodes 기본 limit(50) 미러 — 도달 시 매칭 카운트 부분값(badge '+')
const _META_TERMS_COMBO = "__terms__";   // GlossaryTerm/misc 를 담는 합성 클러스터

// node key(`scope:fqn`) → 소속 스키마 클러스터 combo id. Table/Column 은 스키마, 그 외는 terms 클러스터.
function _metaSchemaComboOf(n) {
  if (!n) return _META_TERMS_COMBO;
  if (n.label === "Schema") return n.key;
  if (n.label === "Table" || n.label === "Column" || n.label === "Routine") {
    const sc = _metaCatParent(n.key, n.fqn);
    if (sc) return sc;
  }
  return _META_TERMS_COMBO;
}
function _metaComboName(id) {
  if (id === _META_TERMS_COMBO) return "용어·기타";
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(i + 1) : id;
}
const _metaNatSort = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });

// ── node-role-viz: AI 능동 분석 완료 테이블의 역할 분류 → 시각 표식(칩 색 + 아이콘 + 범례) ──
//   분류체계는 BE(node_analysis.NODE_ROLES)와 1:1. 팔레트 = Okabe-Ito 8색(색약 안전 표준) —
//   색(범주 최강 채널) + 아이콘(중복 인코딩, 색약·흑백 대응) + 범례/상세패널 라벨 3중 인코딩.
//   dark=true 는 밝은 색이라 흰 라벨 대비가 부족한 항목 — 라벨을 어두운 글자로 전환.
const _META_ROLE = {
  // dark 배정(적대 패널 U3): 12px bold 흰 라벨 대비가 부족한 밝은/중간 색은 어두운 라벨(#161b22) —
  //   account 2.2 / log 1.9 / stats 1.1 / mapping 3.1 / transaction 3.4 (흰 라벨 대비, 전부 4.5 미달) → dark.
  // desc: 범례 hover 툴팁·클러스터 상세 접두사 툴팁의 단일 소스. BE node_analysis.NODE_ROLES 휴리스틱과 정합.
  master:      { ko: "기준·정의", icon: "📘", color: "#0072B2", dark: false, desc: "다른 테이블이 참조하는 기준·마스터·코드성 데이터 (코드표·정의·사전 등)" },
  account:     { ko: "계정·유저", icon: "👤", color: "#56B4E9", dark: true,  desc: "사용자·계정·회원 등 주체 정보 (캐릭터·플레이어 포함)" },
  transaction: { ko: "거래·행위", icon: "💳", color: "#009E73", dark: true,  desc: "결제·주문·구매·보상 등 거래·행위 이벤트 (핵심 비즈니스 팩트)" },
  log:         { ko: "로그·이력", icon: "📜", color: "#E69F00", dark: true,  desc: "시간순 로그·이력·감사 기록 (주로 append)" },
  mapping:     { ko: "매핑·연결", icon: "🔗", color: "#CC79A7", dark: true,  desc: "두 엔티티를 잇는 N:M 매핑·연결(교차 참조) 테이블" },
  config:      { ko: "설정",     icon: "⚙️", color: "#D55E00", dark: false, desc: "시스템·기능 설정·옵션·파라미터·환경값" },
  stats:       { ko: "집계·통계", icon: "📊", color: "#F0E442", dark: true,  desc: "집계·통계·랭킹·스냅샷 등 파생·요약 데이터" },
  etc:         { ko: "기타",     icon: "📦", color: "#6e7681", dark: false, desc: "위 분류에 속하지 않는 테이블" },   // ◽ 는 회색 칩 위 tofu 처럼 비가시(패널 U4) → 📦
};
// role-cluster-prefix: 역할 칩 HTML 조립(그래프 칩·상세 배지와 동일 색/아이콘). small=상세 테이블 목록 접두사(고정 폭).
function _metaRoleChipHTML(role, esc, small) {
  const rd = _META_ROLE[role]; if (!rd) return "";
  const tip = esc(`${rd.icon} ${rd.ko} — ${rd.desc}`);
  return `<span class="amgr-role-chip${small ? " amgr-role-chip-sm" : ""}" style="background:${rd.color}${rd.dark ? ";color:#161b22" : ""}" title="${tip}">${rd.icon}</span>`;
}
// role-cluster-prefix: 정적 역할 범례 <li data-role> 에 hover 툴팁(desc) 주입 — _META_ROLE 단일 소스. 그래프 뷰 진입 시 1회.
function _metaRoleLegendTips() {
  document.querySelectorAll(".admin-meta-graph-rolelegend-list li[data-role]").forEach((li) => {
    const rd = _META_ROLE[li.getAttribute("data-role")];
    if (rd) li.title = `${rd.icon} ${rd.ko} — ${rd.desc}`;
  });
}
// graphux7(#3): 그래프 범례 3-탭(노드 종류·관계·AI 상태·테이블 역할) 전환. 그래프 뷰 진입 시 1회 바인딩(멱등).
//   탭 버튼 → is-active + 대응 패널 표시(hidden 토글). ←/→ 로 탭 이동(roving tabindex 접근).
function _metaGraphBindLegendTabs() {
  const wrap = document.getElementById("metadataGraphLegendTabs");
  if (!wrap || wrap.dataset.bound === "1") return;
  wrap.dataset.bound = "1";
  const tabs = Array.prototype.slice.call(wrap.querySelectorAll(".amg-legend-tab"));
  const panels = Array.prototype.slice.call(wrap.querySelectorAll(".amg-legend-panel"));
  const activate = (name) => {
    tabs.forEach((t) => {
      const on = t.getAttribute("data-legend-tab") === name;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((p) => {
      const on = p.getAttribute("data-legend-panel") === name;
      p.classList.toggle("is-active", on);
      if (on) p.removeAttribute("hidden"); else p.setAttribute("hidden", "");
    });
  };
  tabs.forEach((t) => {
    t.addEventListener("click", () => activate(t.getAttribute("data-legend-tab")));
    t.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      const i = tabs.indexOf(t);
      const n = ev.key === "ArrowRight" ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
      const nt = tabs[n];
      if (!nt) return;
      activate(nt.getAttribute("data-legend-tab"));
      try { nt.focus(); } catch (_) {}
    });
  });
}
function _metaRoleOf(key) {
  const r = _metaGraph.roles.get(key);
  return (r && _META_ROLE[r]) ? r : null;
}

// G6 per-element inline style helpers (설정 매퍼 금지 — undefined→To() 크래시 회피, BLUEPRINT §3).
// graph-zorder(§52): 렌더 요소 id → canonical(의미) zIndex. build bake·dragend 복원의 공용 해석기.
//   장식 prefix(GB/GH/GX/X/XS/SC)가 우선하고, 그 외는 모델 label(Column/Schema)로 판정.
//   combo id == Schema 모델 key(펼침 시) — COMBO 층. 미상은 칩과 동급(NODE).
function _metaZFor(id) {
  const s = String(id);
  // graph-category(§55 A, 패널 BLOCKING fix): CAT 밴드 3종 — 누락 시 기본 NODE(4) 로 해석돼
  //   _metaGraphZAssert(매 draw 후 canonical 재-assert)가 배경을 최상층으로 승격, 밴드가 내부
  //   클러스터·노드를 반투명으로 덮고 hit-test 를 가로챈다. bake(-1/5/6)와 1:1 로 고정.
  if (s.startsWith("CATX:")) return _METZ.CTL;
  if (s.startsWith("CATH:")) return _METZ.GROUP_HD;
  if (s.startsWith("CAT:")) return _METZ.CAT_BG;
  if (s.startsWith("GB:")) return _METZ.GROUP_BG;
  if (s.startsWith("GH:")) return _METZ.GROUP_HD;
  if (s.startsWith("GX:") || s.startsWith("XS:")) return _METZ.CTL;
  if (s.startsWith("XR:")) return _METZ.NODE;   // graph-navfilter(§54⑤): 루틴 파라미터 접기 ctl — X: 와 동일 밴드(bake 1:1)
  if (s.startsWith("RP:")) return _METZ.COLUMN; // graph-navfilter(§54⑤): 루틴 파라미터 행 — 컬럼과 동일 밴드(bake 1:1)
  if (s.startsWith("X:")) return _METZ.NODE;   // 패널 ux MINOR: 흐름 내 per-table ctl 은 칩과 같은 밴드(bake 와 1:1)
  if (s.startsWith("SC:")) return _METZ.NODE;
  if (s === _META_TERMS_COMBO) return _METZ.COMBO;   // 용어·기타 클러스터 combo — 모델 노드 없음(합성 id)
  const n = _metaGraph.nodes.get(id);
  if (n && n.label === "Column") return _METZ.COLUMN;
  if (n && n.label === "Schema") return _METZ.COMBO;
  return _METZ.NODE;
}
// graph-zorder(§52): 드래그 중 대상+종속을 canonical+DRAG_BOOST 로 결정론 승격. 내장 drag-element 는
//   grabbed 만 frontElement(전역 max+1, **영구**)로 올려 종속(컬럼·ctl)과 계층이 찢어지고 드래그
//   이력이 z-order 로 굳는다 — 부스트가 그 값을 덮고(호출이 늦어 우선), dragend 가 canonical 복원.
function _metaDragZBoost(ids) { _metaDragZApply(ids, _METZ.DRAG_BOOST); }
// dragend 복원 — rebuild(_metaG6Apply)도 canonical 을 재-bake 하므로 이중 안전망(자가 치유).
function _metaDragZRestore(ids) { _metaDragZApply(ids, 0); }
function _metaDragZApply(ids, boost) {
  const g = _metaGraph.graph;
  if (!g || !ids || !ids.length) return;
  // setElementZIndex 는 미존재 id 1개로도 전체 reject — 마지막 build 의 renderedIds 로 필터
  //   (드래그 중 rebuild 로 요소가 제거된 edge case 에 나머지 복원까지 무산되지 않게).
  const r = _metaGraph.renderedIds;
  const m = {};
  let n = 0;
  ids.forEach((id) => {
    if (!r || r.has(id)) {
      m[id] = _metaZFor(id) + boost;
      n += 1;
      // h2(리뷰 MINOR): 부스트 중 id 를 기록 — 백그라운드 rebuild(_metaGraphZAssert)가 드래그 도중
      //   canonical 로 회수하지 않게 보호. 복원(boost=0) 시 해제.
      if (boost > 0) _metaGraph._dragZBoosted.add(id); else _metaGraph._dragZBoosted.delete(id);
    }
  });
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}
// graph-zorder(§52): 렌더 요소 id → 소속 클러스터(combo id). 장식 prefix 는 파싱, 그 외는 모델 기반.
function _metaComboOwnerOf(id) {
  const s = String(id);
  if (s.startsWith("SC:") || s.startsWith("XS:")) return s.slice(3);
  if (s.startsWith("GB:") || s.startsWith("GH:") || s.startsWith("GX:")) {
    const gk = s.slice(3), sep = gk.indexOf("\u0001");
    return sep >= 0 ? gk.slice(0, sep) : null;
  }
  // graph-navfilter(§54⑤): 루틴 파라미터 합성 id — 소속 루틴의 스키마 combo 로 귀속(X: 관례와 동형).
  if (s.startsWith("XR:")) {
    const n = _metaGraph.nodes.get(s.slice(3));
    return n ? _metaSchemaComboOf(n) : null;
  }
  if (s.startsWith("RP:")) {
    const n = _metaGraph.nodes.get(s.slice(3).replace(/:\d+$/, ""));
    return n ? _metaSchemaComboOf(n) : null;
  }
  if (s.startsWith("X:")) {
    const n = _metaGraph.nodes.get(s.slice(2));
    return n ? _metaSchemaComboOf(n) : null;
  }
  const n = _metaGraph.nodes.get(s);
  return n ? _metaSchemaComboOf(n) : null;
}
// graph-zorder(§52): combo(클러스터)의 렌더된 하위 요소 id 전부 — 내장 frontElement 가 combo 드래그
//   시 하위 전체를 델타 승격하므로, dragend canonical 복원 대상을 같은 범위로 재구성한다.
function _metaComboMemberIds(comboId) {
  const out = [];
  const r = _metaGraph.renderedIds;
  if (!r || !comboId) return out;
  r.forEach((id) => {
    if (String(id) === comboId) return;
    if (_metaComboOwnerOf(id) === comboId) out.push(id);
  });
  return out;
}
// graph-zorder(§52, 패널 ux BLOCKING): 엣지 datum → canonical zIndex — _metaEdgeStyleFor/_metaRoutineEdgeStyle
//   의 bake 규칙과 1:1 (EDGE + trusted 0.2 / candidate·교차DB 0.1 / 그 외 0, ROUTINE_USES·USES = EDGE).
function _metaEdgeZFor(ed) {
  const d = (ed && ed.data) || {};
  if (d.label === "ROUTINE_USES") return _METZ.EDGE;
  if (d.cross_ds) return _METZ.EDGE + 0.1;
  return _METZ.EDGE + (d.status === "trusted" ? 0.2 : (d.status === "candidate" ? 0.1 : 0));
}
// graph-zorder(§52, 패널 ux BLOCKING): 내장 frontElement 는 combo 드래그 시 **내부 엣지**도 델타 승격한다
//   (번들 실측: getRelatedEdgesData(...).internal). 노드+콤보만 복원하면 관계선이 칩(4)·헤더(5)·컨트롤(6)
//   위로 영구 잔존(반복 드래그 시 단조 증가 — 콤보 드래그는 rebuild 를 유발하지 않아 다음 rebuild 까지
//   지속) — combo 소속 끝점을 가진 엣지 전부를 canonical 로 복원한다(내장의 internal 범위 상위집합 —
//   비승격분 재-세팅은 no-op 라 무해).
function _metaComboEdgesRestore(comboId) {
  const g = _metaGraph.graph;
  if (!g || !comboId) return;
  let eds;
  try { eds = g.getEdgeData(); } catch (_) { eds = null; }
  if (!eds || !eds.length) return;
  const m = {};
  let n = 0;
  eds.forEach((ed) => {
    if (!ed || ed.id == null) return;
    if (_metaComboOwnerOf(ed.source) === comboId || _metaComboOwnerOf(ed.target) === comboId) { m[ed.id] = _metaEdgeZFor(ed); n += 1; }
  });
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}
// graph-zorder h2(§52.4, PB-0008 라이브 실측 적발): G6 v5 computeZIndex 는 setData diff 의 **update** 에서
//   datum 에 `combo` 키가 있으면(combo-자식 노드 datum 은 항상 combo: 포함 — 접힌 카드 SC:·products
//   빌드 노드는 combo 키가 없어 애초 평탄화 비대상) 제공된 style.zIndex 를 무시하고 comboZ+1(=1) 로
//   재산정한다 — add 는 명시 zIndex 존중(skip). 즉 첫 렌더는 canonical, **기존 요소가 업데이트되는
//   rebuild 마다 combo-자식 전부 z1 평탄화**(실측: 그룹 멤버 드래그 rebuild 후 칩/컬럼/ctl=1). 엣지는
//   명시 zIndex 정의 시 항상 skip 이라 무영향. setElementZIndex 경로는 datum 에 combo 키가 없어 재산정을
//   우회(sticky)하므로, 매 rebuild(draw) 직후 canonical 과 어긋난 요소만 골라 일괄 re-assert 한다.
function _metaGraphZAssert() {
  const g = _metaGraph.graph;
  if (!g || !_metaGraph.renderedIds) return;
  const m = {};
  let n = 0;
  _metaGraph.renderedIds.forEach((id) => {
    if (_metaGraph._dragZBoosted.has(id)) return;   // h2(리뷰 MINOR): 드래그 부스트 중 — 회수 금지(dragend 가 복원)
    let z; try { z = g.getElementZIndex(id); } catch (_) { return; }
    const want = _metaZFor(id);
    if (z !== want) { m[id] = want; n += 1; }
  });
  try {
    g.getEdgeData().forEach((ed) => {
      if (!ed || ed.id == null) return;
      let z; try { z = g.getElementZIndex(ed.id); } catch (_) { return; }
      const want = _metaEdgeZFor(ed);
      if (z !== want) { m[ed.id] = want; n += 1; }
    });
  } catch (_) {}
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}

function _metaTableStyle(x, y, rel, role) {
  // feature-0016 §45: 검색 매칭 표현을 '너비 증가'에서 'match 상태 soft glow'로 이관 — 노드 폭은 rel 과 무관하게 고정한다
  //   (가변 폭은 setData 재packing 을 유발하고 검색 가시성도 떨어졌다). rel 인자는 호출부 호환 위해 유지(폭 계산엔 미사용).
  const w = _METLAY.TW;
  // node-role-viz: 분석 완료 + 역할 분류가 있으면 칩 색 = 역할색(미분석은 기존 teal 유지 — 색 자체가 "분석됨+역할" 신호).
  const rd = role ? _META_ROLE[role] : null;
  return { x, y, size: [w, 24], radius: 6, fill: rd ? rd.color : _META_GRAPH_COLOR.Table, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    // feature-0016 §45: 폭이 rel 무관 고정(TW=150)이 되며 라벨이 박스를 넘치지 않도록 labelMaxWidth 를 박스 안으로 클램프(예전 176 은 rel 부스트로 최대 190 폭일 때 기준).
    labelPlacement: "center", labelFill: rd && rd.dark ? "#161b22" : "#ffffff", labelFontSize: 12, labelFontWeight: 700, labelMaxWidth: _METLAY.TW - 10, cursor: "pointer" };
}
function _metaTermStyle(x, y, rel) {
  // feature-0016 §45: 용어 노드 폭도 rel 무관 고정(검색 매칭은 match 상태 soft glow 로 표시). rel 인자는 호환 유지.
  const w = 130;
  return { x, y, size: [w, 22], radius: 11, fill: _META_GRAPH_COLOR.GlossaryTerm, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    // feature-0016 §45: 폭 고정(130)에 맞춰 라벨을 박스 안으로 클램프(예전 168 은 rel 부스트 폭 기준).
    labelPlacement: "center", labelFill: "#ffffff", labelFontSize: 11, labelFontWeight: 700, labelMaxWidth: 118, cursor: "pointer" };
}
function _metaColStyle(x, y) {
  return { x, y, size: 11, fill: _META_GRAPH_COLOR.Column, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.COLUMN,
    labelPlacement: "right", labelFill: "#161b22", labelFontSize: 10, labelOffsetX: 5, labelMaxWidth: 168, cursor: "pointer" };
}
// graph-funcproc(ADR-016): 함수·프로시저 칩 — 테이블 칩과 같은 자리(클러스터 열)에 서되 보라 + 둥근 모서리로 구분.
function _metaRoutineStyle(x, y, rel) {
  const w = Math.min(190, _METLAY.TW + (typeof rel === "number" ? Math.round(rel * 40) : 0));
  return { x, y, size: [w, 24], radius: 12, fill: _META_GRAPH_COLOR.Routine, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    labelPlacement: "center", labelFill: "#ffffff", labelFontSize: 11, labelFontWeight: 700, labelMaxWidth: 176, cursor: "pointer" };
}
function _metaCtlStyle(x, y) {
  return { x, y, size: [18, 18], radius: 4, fill: "#ffffff", stroke: "#0a5b66", lineWidth: 1.5, zIndex: _METZ.CTL,
    labelText: "−", labelPlacement: "center", labelFill: "#0a5b66", labelFontSize: 15, labelFontWeight: 700, cursor: "pointer" };
}
// graph-initview: 접힌 스키마 카드(진입 뷰 기본) — 클릭 시 그 스키마의 테이블만 lazy 펼침.
function _metaSchemaCardStyle(x, y) {
  return { x, y, size: [_METLAY.CARDW, _METLAY.CARDH], radius: 10, fill: "#eef0f8",
    stroke: _META_GRAPH_COLOR.Schema, lineWidth: 1.5, zIndex: _METZ.NODE,
    labelPlacement: "center", labelFill: "#2a3567", labelFontSize: 12, labelFontWeight: 700,
    labelMaxWidth: _METLAY.CARDW - 16, cursor: "pointer" };
}
// graph-initview: 스키마 combo 의 "−" 접기 컨트롤(카드로 복귀).
function _metaSchemaCtlStyle(x, y) {
  return { x, y, size: [18, 18], radius: 4, fill: "#ffffff", stroke: _META_GRAPH_COLOR.Schema, lineWidth: 1.5,
    labelText: "−", labelPlacement: "center", labelFill: _META_GRAPH_COLOR.Schema, labelFontSize: 15,
    labelFontWeight: 700, cursor: "pointer", zIndex: _METZ.CTL };
}
function _metaComboStyleFor(isTerms) {
  return { radius: 12, padding: [30, 16, 14, 16], labelPlacement: "top", labelFontWeight: 700, labelFontSize: 13,
    labelFill: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema,
    fill: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema,
    fillOpacity: 0.045, stroke: isTerms ? "#d3b06a" : "#aab3c5", lineWidth: 1, lineDash: [6, 4], collapsedMarker: false,
    zIndex: _METZ.COMBO };   // graph-zorder(§52): 클러스터 배경 = 최하층 — 드래그 frontElement 잔존 승격도 rebuild 재-bake 로 복원
}
function _metaEdgeStyleFor(status, crossDs) {
  // crossds-rel(ADR-019): 교차DB 관계는 상태 무관 별도 클래스 — 마젠타 점선(same-ds candidate 골드 점선과 구분).
  //   프로브 검증 불가라 항상 추정성. trusted 승격돼도 교차DB 임을 시각 유지.
  // graph-zorder(§52, 패널 design MINOR): EDGE 층 내부 tie 를 의미로 분해 — 신뢰 강도가 강한 엣지가
  //   교차점에서 위에 그려지게 소수 오프셋(trusted +0.2 > candidate/교차DB +0.1 > 기본 +0). @antv/g 는
  //   수치 정렬이라 유효. 층 상한(COLUMN=3) 미만 유지.
  if (crossDs) return { stroke: "#a855c7", lineWidth: 1.8, lineDash: [2, 4], endArrow: true, zIndex: _METZ.EDGE + 0.1 };
  const s = { stroke: status === "trusted" ? "#6b4410" : (status === "candidate" ? "#c9a24a" : "#cbd2db"),
    lineWidth: status === "trusted" ? 3 : (status === "candidate" ? 1.8 : 1.4), endArrow: true,
    zIndex: _METZ.EDGE + (status === "trusted" ? 0.2 : (status === "candidate" ? 0.1 : 0)) };
  if (status === "candidate") s.lineDash = [6, 4];   // 실선은 lineDash 키 생략(false 금지 — G6 크래시, BLUEPRINT §3)
  return s;
}
// graph-funcproc(ADR-016): 함수·프로시저 → 테이블 사용 엣지(ROUTINE_USES) — 보라 잔점선(추정 점선과 구분).
function _metaRoutineEdgeStyle() {
  return { stroke: _META_GRAPH_COLOR.Routine, lineWidth: 1.5, lineDash: [2, 3], endArrow: true, zIndex: _METZ.EDGE };
}
function _metaNodeStates(key) {
  const st = [];
  // feature-0016 §45: 검색 매칭 노드 = 'match' 상태 soft glow(예전 '너비 증가' 대체). glow 는 shadow 라
  //   뒤의 selected/analyzed stroke 와 독립적으로 공존한다(테두리색 충돌 없음).
  if (_metaGraph.mode === "search" && _metaGraph.searchMatchNodes && _metaGraph.searchMatchNodes.has(key)) st.push("match");
  if (_metaGraph.analyzed.has(key)) st.push("analyzed");
  if (_metaGraph.running.has(key)) st.push("running");
  if (_metaGraph.selected === key) st.push("selected");
  return st;
}

// ── graph-perf-bg: 논블로킹 유틸(펼침/확장이 메인스레드를 얼리지 않도록) ──
// 무거운 setData+draw 직전에 브라우저가 busy 상태를 실제로 페인트하도록 두 번의 rAF 후 넘긴다.
//   단일 rAF 는 같은 프레임에 병합될 수 있고, microtask(Promise.resolve)는 페인트를 유발하지 못하므로 둘 다 부적합.
function _metaRaf() {
  return new Promise((res) => {
    if (typeof window !== "undefined" && window.requestAnimationFrame) window.requestAnimationFrame(() => res());
    else setTimeout(res, 0);
  });
}
function _metaYieldPaint() { return _metaRaf().then(() => _metaRaf()); }

// graph-perf-bg fix: 노드에 "적용할" state = 영속 마커(_metaNodeStates) + 명령형 busy(_busyKeys).
//   busy 를 signature 에 포함시켜 _metaGraphRefreshStates(2.5s 폴)가 fetch 창 도중 busy 를 덮어써 지우지 못하게 한다.
function _metaStateSig(key) {
  const st = _metaNodeStates(key);              // 매 호출 새 배열 — push 안전
  if (_metaGraph._busyKeys.has(key)) st.push("busy");
  return st;
}
// node-role-viz: 캐시 서명 = state 서명 + 역할 suffix. 역할은 G6 state 가 아니라 **build 시 칩 색/라벨로
//   bake 되는 style** 이라 setElementState 로 반영할 수 없다 — 대신 서명에 포함시켜 refreshStates 가
//   "역할 도착"을 변화로 감지하고 rebuild(_metaG6Apply)로 승격하게 한다. setElementState 에는 넘기지 않는다.
function _metaCacheSig(key) {
  const role = _metaGraph.roles.get(key);
  return _metaStateSig(key).join("|") + (role ? "#R=" + role : "");
}
function _metaSigRole(sig) {
  const i = (sig || "").indexOf("#R=");
  return i >= 0 ? sig.slice(i + 3) : "";
}
// 요소 state 적용 단일 진입점 — 적용과 동시에 _stateCache signature 를 동기화한다.
//   불변식: _stateCache.get(key) === 요소에 마지막 적용된 state 의 signature. 명령형 writer(busy·selected)도 이 경로를 쓰면
//   refreshStates 가 "변화 없음"으로 오판해 필요한 재적용을 건너뛰는 false-negative 가 원천 차단된다.
function _metaApplyState(key) {
  const g = _metaGraph.graph;
  if (!g || !key || !_metaGraph.nodes.has(key)) return;
  const st = _metaStateSig(key);
  // graph-initview: 렌더된 요소 id 로 매핑(접힌 스키마 카드=SC:) — 카드 게이팅으로 미렌더인 모델 키에
  // setElementState 하면 async reject 가 pageerror 로 새므로 skip + promise reject 흡수.
  const el = _metaRenderedIdFor(key);
  if (el) { try { Promise.resolve(g.setElementState(el, st)).catch(() => {}); } catch (_) {} }
  _metaGraph._stateCache.set(key, _metaCacheSig(key));   // node-role-viz: 역할 suffix 포함(불변식 유지)
}

// 클릭 노드에 임시 busy 하이라이트(명령형). **_metaNodeStates 에는 넣지 않는다**(rebuild 마다 재-bake 되어 영구
//   하이라이트로 굳음) — 대신 _busyKeys 로 소유 op(seq)와 함께 추적해 rebuild(_metaG6Apply)·reset 시 일괄 소멸.
//   on=true: seq 소유권 기록. on=false: op-scoped 해제 — seq 를 주면 그 op 가 여전히 소유할 때만 해제하여, 같은 key 를
//   재트리거한 신 op 의 busy 를 뒤늦게 resolve 된 stale op 가 지우지 못하게 한다(seq 미지정이면 무조건 해제).
function _metaSetBusy(key, on, seq) {
  if (!key) return;
  if (on) {
    _metaGraph._busyKeys.set(key, seq == null ? -1 : seq);
  } else {
    if (seq != null && _metaGraph._busyKeys.get(key) !== seq) return;   // 신 op 가 이미 같은 key busy 소유 — stale op 는 건드리지 않음
    _metaGraph._busyKeys.delete(key);
  }
  _metaApplyState(key);
}

// ── graph-rel-layout: 관계(REFERENCES) 기반 배치 pre-pass — 엣지 교차 최소화 ──
//   배치 순서(스키마 seriation + 클러스터 내 테이블 군집 순서)를 관계 가중치의 순수 함수로 결정한다.
//   유사도 w = Σ 컬럼-쌍(trusted=2 · 그 외 1). 관계 0 이면 기존 자연정렬과 동일(강등 없음) — 관계가
//   쌓일수록 다음 rebuild 에서 배치가 관계 기준으로 수렴한다(사용자 요청: 관계 확보에 따른 기준 배치).
//   결정론·펼침-불변: schemaExpanded 를 읽지 않는다(ADR-004 ② 배정 불변식 유지) — 입력(nodes+edges)이
//   같으면 출력이 같고, 순서 변경은 관계 데이터가 늘어난 rebuild 시점(기존 shelf 재배치 시야고정 경로)뿐.

// REFERENCES 끝점(항상 컬럼 키, 간혹 테이블 키) → 소속 테이블 키. 미해석 시 null.
function _metaRelTableKeyOf(k) {
  const n = _metaGraph.nodes.get(k);
  if (n && n.label === "Table") return k;
  return _metaColParent(k, n && n.fqn);
}
// 테이블-레벨 무향 인접행렬: tKey -> Map(tKey -> w). 모델에 실재하는 테이블 쌍만.
function _metaRelAdjacency(tableByKey) {
  const adj = new Map();
  const bump = (a, b, w) => { let m = adj.get(a); if (!m) { m = new Map(); adj.set(a, m); } m.set(b, (m.get(b) || 0) + w); };
  _metaGraph.edges.forEach((e) => {
    if (e.type !== "REFERENCES") return;
    const a = _metaRelTableKeyOf(e.source), b = _metaRelTableKeyOf(e.target);
    if (!a || !b || a === b || !tableByKey.has(a) || !tableByKey.has(b)) return;
    const w = e.status === "trusted" ? 2 : 1;   // 신뢰 관계를 유사도에 더 크게 반영
    bump(a, b, w); bump(b, a, w);
  });
  return adj;
}
// 스키마 seriation(greedy attachment): 관계 가중치가 큰 스키마끼리 shelf 순서상 인접 → 교차 엣지가 짧아진다.
//   seed = 총 외부 가중 최대 → 이후 "이미 배치된 집합과의 가중 합" 최대를 반복 선택(다른 연결군이면 새 seed).
//   tie-break 는 자연정렬 입력 순서(ids)의 first-win — 결정론. 관계 없는 스키마는 자연정렬 그대로 후미.
function _metaRelSchemaOrder(ids, adj, schemaOf) {
  const pairW = new Map(), deg = new Map();
  adj.forEach((m, a) => m.forEach((w, b) => {
    if (a >= b) return;                                       // 무향 1회
    const sa = schemaOf(a), sb = schemaOf(b);
    if (!sa || !sb || sa === sb) return;
    const k = sa < sb ? sa + "\n" + sb : sb + "\n" + sa;
    pairW.set(k, (pairW.get(k) || 0) + w);
    deg.set(sa, (deg.get(sa) || 0) + w);
    deg.set(sb, (deg.get(sb) || 0) + w);
  }));
  if (!pairW.size) return ids;                                // 스키마 간 관계 없음 → 자연정렬 유지
  const pw = (x, y) => pairW.get(x < y ? x + "\n" + y : y + "\n" + x) || 0;
  const connected = ids.filter((s) => (deg.get(s) || 0) > 0);
  const isolated = ids.filter((s) => !((deg.get(s) || 0) > 0));
  const remaining = new Set(connected), out = [], att = new Map();   // att = 배치 집합과의 누적 가중
  while (remaining.size) {
    let best = null, bw = -1;
    for (const s of connected) {
      if (!remaining.has(s)) continue;
      const w = out.length ? (att.get(s) || 0) : (deg.get(s) || 0);
      if (w > bw) { bw = w; best = s; }
    }
    if (out.length && bw === 0) {                             // 남은 것이 전부 미연결(다른 연결군) → 새 seed
      bw = -1;
      for (const s of connected) { if (!remaining.has(s)) continue; const w = deg.get(s) || 0; if (w > bw) { bw = w; best = s; } }
    }
    out.push(best); remaining.delete(best);
    for (const s of connected) if (remaining.has(s)) att.set(s, (att.get(s) || 0) + pw(s, best));
  }
  return out.concat(isolated);
}
// 클러스터 내 테이블 순서: 스키마 내부 관계의 연결 컴포넌트를 군집으로 붙이고(BFS, 가중 내림차순),
//   내부 무관계지만 외부 관계 보유 테이블은 이웃 스키마 seriation idx 순으로, 완전 고립은 자연정렬 그대로.
//   masonry Pass1 은 균등높이 최단열(=행 우선 채움)이라 순서상 인접 = 화면상 인접 → 관계 테이블이 모인다.
function _metaRelTableOrder(items, adj, schemaIdx, schemaOf) {
  if (!adj.size || items.length < 3) return items;
  const keys = items.map((t) => t.key), inSet = new Set(keys);
  const intra = new Map(), deg = new Map(), extAnchor = new Map();
  keys.forEach((k) => {
    const m = adj.get(k);
    let d = 0, ei = 0, ew = 0;
    if (m) m.forEach((w, o) => {
      if (inSet.has(o)) { let im = intra.get(k); if (!im) { im = new Map(); intra.set(k, im); } im.set(o, w); d += w; }
      else { const oi = schemaIdx.get(schemaOf(o)); if (oi != null) { ei += oi * w; ew += w; } }
    });
    deg.set(k, d);
    if (ew > 0) extAnchor.set(k, ei / ew);
  });
  const visited = new Set(), comps = [];
  keys.forEach((k) => {                                       // 컴포넌트 수집 — 입력(자연정렬) 순 seed, 결정론
    if (visited.has(k) || !(deg.get(k) > 0)) return;
    const comp = [], q = [k]; visited.add(k);
    while (q.length) {
      const c = q.shift(); comp.push(c);
      const im = intra.get(c);
      if (im) [...im.keys()].sort(_metaNatSort).forEach((o) => { if (!visited.has(o)) { visited.add(o); q.push(o); } });
    }
    comps.push(comp);
  });
  if (!comps.length && !extAnchor.size) return items;
  const compW = (comp) => comp.reduce((a, k) => a + (deg.get(k) || 0), 0);
  comps.sort((a, b) => (compW(b) - compW(a)) || (b.length - a.length) || _metaNatSort(a[0], b[0]));
  const orderComp = (comp) => {                               // 군집 내부: 최고 가중度 seed → BFS(간선 가중 내림차순)
    const cs = new Set(comp);
    const seed = comp.slice().sort((a, b) => ((deg.get(b) || 0) - (deg.get(a) || 0)) || _metaNatSort(a, b))[0];
    const out = [], seen = new Set([seed]), q = [seed];
    while (q.length) {
      const c = q.shift(); out.push(c);
      const im = intra.get(c);
      if (im) [...im.entries()].filter(([o]) => cs.has(o) && !seen.has(o))
        .sort((x, y) => (y[1] - x[1]) || _metaNatSort(x[0], y[0]))
        .forEach(([o]) => { seen.add(o); q.push(o); });
    }
    return out;
  };
  const ordered = [];
  comps.forEach((comp) => ordered.push(...orderComp(comp)));
  const rest = keys.filter((k) => !visited.has(k));
  const ext = rest.filter((k) => extAnchor.has(k)).sort((a, b) => (extAnchor.get(a) - extAnchor.get(b)) || _metaNatSort(a, b));
  const iso = rest.filter((k) => !extAnchor.has(k));          // 입력 자연정렬 순서 보존
  const pos = new Map(); let pi = 0;
  ordered.concat(ext, iso).forEach((k) => pos.set(k, pi++));
  return items.slice().sort((a, b) => pos.get(a.key) - pos.get(b.key));
}
// 전 스키마 테이블 순서 선산정: 군집 초기순서(_metaRelTableOrder) 위에 **barycenter 4-sweep** —
//   각 테이블을 이웃(스키마 내부+외부 관계 상대)들의 전역 위치 가중평균 순으로 재정렬하는 층별
//   교차 최소화 휴리스틱. 스키마-레벨 앵커만으로는 나란한 두 클러스터 사이의 상호 교차(a↔d, b↔c)를
//   못 풀기 때문에, 이웃 "테이블" 위치 기준 정렬로 관계선이 평행에 가깝게 정돈된다.
//   이웃 없는 테이블은 자기 현재 위치가 barycenter(제자리 안정). 접힌 스키마 테이블도 순서를 계산해
//   이웃 위치 근사에 쓴다(렌더 여부는 layouts 의 카드 게이팅이 결정 — 본 pre-pass 는 펼침-비의존).
function _metaRelOrderAll(groups, ids, adj, schemaIdx, schemaOf) {
  const orderBySchema = new Map();
  ids.forEach((s) => {
    const g = groups.get(s);
    if (!g || g.isTerms) return;
    const nat = g.tables.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
    orderBySchema.set(s, adj.size ? _metaRelTableOrder(nat, adj, schemaIdx, schemaOf) : nat);
  });
  if (!adj.size) return orderBySchema;
  // SPAN=1(gpos = schemaIdx + 로컬 rank): 상대 테이블의 "클러스터 내 순위"가 barycenter 를 지배하고
  //   스키마 원근은 약한 앵커로만 작용. 합성 벤치(시드 3종 × 랜덤/허브 토폴로지 6구성, 2D 세그먼트
  //   교차)에서 SPAN∈{4096,30,10,1} 중 5/6 최선·1D 층간 역전도 유일 개선(59→51) — 원거리 스키마
  //   위치가 지배(SPAN=4096)하면 같은 스키마쌍 엣지들의 상호 정렬이 무너져 1D 역전이 되레 늘었다.
  const SPAN = 1;
  const gpos = new Map();
  ids.forEach((s) => { const arr = orderBySchema.get(s); if (arr) arr.forEach((n, i) => gpos.set(n.key, schemaIdx.get(s) * SPAN + i)); });
  for (let pass = 0; pass < 4; pass++) {   // 벤치 기준 4-pass 수렴(2-pass 는 미수렴 잔차)
    ids.forEach((s) => {
      const arr = orderBySchema.get(s);
      if (!arr || arr.length < 2) return;
      const base = schemaIdx.get(s) * SPAN;
      const bc = new Map();
      arr.forEach((n) => {
        const m = adj.get(n.key);
        let acc = 0, tw = 0;
        if (m) m.forEach((w, o) => { const p = gpos.get(o); if (p != null) { acc += p * w; tw += w; } });
        bc.set(n.key, tw > 0 ? acc / tw : gpos.get(n.key));
      });
      arr.sort((a, b) => (bc.get(a.key) - bc.get(b.key)) || (gpos.get(a.key) - gpos.get(b.key)));
      arr.forEach((n, i) => gpos.set(n.key, base + i));
    });
  }
  return orderBySchema;
}

// ── graph-simgroups: 유사 속성 그룹 — 이름 affix family + 관계 attach + 역할 폴백 ──
//   사용자 요청 "각 테이블이 서로 유사한 속성끼리 배치 + 속성 범위가 가시적으로": 스키마 클러스터 내부를
//   유사 속성 그룹 블록(배경 박스 + 헤더 칩)으로 분할해, 군집이 '순서'가 아니라 '영역'으로 보이게 한다.
//   그룹핑은 (테이블명, 관계, 역할)의 순수 함수 — 결정론·펼침-비의존(schemaExpanded 무참조).

// 테이블명 affix family: 이름의 접두/접미 토큰(4~12자) 중 지원도(공유 테이블 수) ≥2 인 것에서
//   score = 지원도×길이 최대 토큰을 family 로 채택. "view_" 접두는 정규화 시 제거(뷰는 원본 가족으로).
//   반환: Map(tableKey → token|null). 게임 DB 처럼 구분자 없는 소문자 연접 이름에서도 동작하는 유일한
//   실용 신호가 공유 affix 다(underscore/camel 분할은 이런 이름에 무력).
// graph-simgroups: 테이블명 정규화 — 소문자화 + view 접두 제거(뷰는 원본 가족으로 묶기 위해).
//   §18.8 패널 MINOR: bare "view" 를 무조건 4자 절단하면 "viewer_log"→"er_log" mangle. 구분자 있는
//   "view_" 접두만 제거하고, 그 외 "view" 로 시작하는 실명(viewer 등)은 보존한다.
function _metaViewNorm(t) {
  const s = String((t && (t.name || t.key)) || "").toLowerCase();
  return s.startsWith("view_") ? s.slice(5) : s;
}
function _metaSimFamilies(tables) {
  const norm = _metaViewNorm;
  const support = new Map();   // token -> Set(tableKey)
  const bump = (tok, k) => { let s = support.get(tok); if (!s) { s = new Set(); support.set(tok, s); } s.add(k); };
  tables.forEach((t) => {
    const nm = norm(t);
    const L = Math.min(nm.length, 16);   // 16자: battletimereward 류 긴 스템 보존(12는 중간 절단)
    for (let l = 4; l <= L; l++) { bump(nm.slice(0, l), t.key); if (l < nm.length) bump(nm.slice(nm.length - l), t.key); }
  });
  const fam = new Map();
  tables.forEach((t) => {
    const nm = norm(t);
    let best = null, bs = 0;
    const L = Math.min(nm.length, 16);
    const consider = (tok) => {
      const sup = support.get(tok) ? support.get(tok).size : 0;
      if (sup < 2) return;
      const score = sup * tok.length;
      if (score > bs || (score === bs && best != null && tok < best)) { bs = score; best = tok; }
    };
    for (let l = 4; l <= L; l++) { consider(nm.slice(0, l)); if (l < nm.length) consider(nm.slice(nm.length - l)); }
    fam.set(t.key, best);
  });
  return fam;
}

// 그룹 조립: ① 이름 family ② family 없음 → 관계 가중 최대 family 로 attach ③ 역할 family ④ 기타.
//   싱글턴 family 는 ②~④ 로 강등(1개짜리 박스 노이즈 방지). 그룹 순서 = 관계 seriation(무관계는
//   크기 desc·라벨 natural), 그룹 내 테이블 순서 = _metaRelOrderAll 재사용(컴포넌트 군집 + barycenter —
//   "그룹"을 컨테이너로 취급). 반환: { list: [{key,label,n,tables[]}], orderIds: [...] } (결정론).
function _metaSimGroups(schemaId, tables, adj) {
  const fam = _metaSimFamilies(tables);
  const roleFam = (t) => { const r = _metaRoleOf(t.key); return r ? "role:" + r : null; };
  // Phase C(ADR-013 후속, semantic-embed): 백엔드 의미 클러스터(be:) 우선. namespace 는 정확히 1회('be:'+id)
  //   부여 — 하류 nm: 재접두 대상에서 제외(verify MAJOR: 이중 namespace 방지). 이 스키마 내 be: 멤버 ≥2 일
  //   때만 그룹화하고, 싱글턴이면 affix 폴백(be: 클러스터는 datasource 전역이라 한 스키마엔 1개만 있을 수 있음).
  const beOf = new Map(), beCnt = new Map();
  tables.forEach((t) => {
    const be = (t.cluster_id != null && String(t.cluster_id) !== "") ? ("be:" + t.cluster_id) : null;
    beOf.set(t.key, be);
    if (be) beCnt.set(be, (beCnt.get(be) || 0) + 1);
  });
  // 1차 배정 + 싱글턴 판정
  const byFam = new Map();
  tables.forEach((t) => { const f = fam.get(t.key); if (f) { if (!byFam.has(f)) byFam.set(f, []); byFam.get(f).push(t); } });
  const famOf = new Map();   // tKey -> famKey (확정)
  tables.forEach((t) => {
    const be = beOf.get(t.key);
    if (be && beCnt.get(be) >= 2) { famOf.set(t.key, be); return; }   // 백엔드 클러스터 우선(namespace 1회)
    const f = fam.get(t.key);
    if (f && byFam.get(f).length >= 2) { famOf.set(t.key, "nm:" + f); return; }
    famOf.set(t.key, null);   // 싱글턴/무family — 2차에서 attach
  });
  // 2차: 관계 가중 최대 family attach — **1차 확정(nm:) family 만** 부착 대상.
  //   §18.8 패널 MAJOR: 이웃 family 를 갱신 중인 live famOf 에서 읽으면 방금 2차-배정된 이웃으로 연쇄
  //   attach 되어 입력순서 의존 그룹이 생긴다(주석의 "무연쇄" 위배). 1차 스냅샷 fam1 에서만 읽어 연쇄 차단.
  const fam1 = new Map(famOf);
  tables.forEach((t) => {
    if (famOf.get(t.key)) return;
    const m = adj.get(t.key);
    if (!m) return;
    const wByFam = new Map();
    m.forEach((w, o) => { const f = fam1.get(o); if (f) wByFam.set(f, (wByFam.get(f) || 0) + w); });
    let best = null, bw = 0;
    [...wByFam.keys()].sort(_metaNatSort).forEach((f) => { const w = wByFam.get(f); if (w > bw) { bw = w; best = f; } });
    if (best) famOf.set(t.key, best);
  });
  // 3차: 역할 family → 기타
  tables.forEach((t) => { if (!famOf.get(t.key)) famOf.set(t.key, roleFam(t) || "misc"); });
  // 역할/기타 family 도 싱글턴이면 기타로 흡수 (nm: 은 2차 attach 로 커질 수 있어 유지)
  const cnt = new Map();
  famOf.forEach((f) => cnt.set(f, (cnt.get(f) || 0) + 1));
  tables.forEach((t) => { const f = famOf.get(t.key); if (f !== "misc" && !f.startsWith("nm:") && !f.startsWith("be:") && cnt.get(f) < 2) famOf.set(t.key, "misc"); });
  // 그룹 리스트 + 라벨
  const groupsBy = new Map();
  tables.forEach((t) => { const f = famOf.get(t.key); if (!groupsBy.has(f)) groupsBy.set(f, []); groupsBy.get(f).push(t); });
  const normNm = _metaViewNorm;   // §18.8 MINOR: view_ 만 제거(viewer 등 실명 보존) — _metaSimFamilies 와 동일 규칙
  const commonAffix = (arr) => {   // 멤버 정규화 이름의 최장 공통 접두/접미 중 긴 쪽(≥4) — 자연 스템 라벨
    if (!arr.length) return null;
    const ns = arr.map(normNm);
    let p = ns[0], sfx = ns[0];
    ns.forEach((x) => {
      let i = 0; while (i < p.length && i < x.length && p[i] === x[i]) i++;
      p = p.slice(0, i);
      let j = 0; while (j < sfx.length && j < x.length && sfx[sfx.length - 1 - j] === x[x.length - 1 - j]) j++;
      sfx = sfx.slice(sfx.length - j);
    });
    const best = p.length >= sfx.length ? p : sfx;
    return best.length >= 4 ? best : null;
  };
  const labelOf = (f, members) => {
    if (f === "misc") return "기타";
    if (f.startsWith("role:")) { const r = f.slice(5); const R = _META_ROLE[r]; return R ? R.icon + " " + R.ko : r; }
    if (f.startsWith("be:")) {   // Phase C: 백엔드 의미 클러스터 — 서버 라벨 우선, 없으면 affix/멤버 폴백
      const m = (members || []).find((x) => x && x.cluster_label);
      if (m && m.cluster_label) return String(m.cluster_label);
      const ca = commonAffix(members || []);
      return ca || ("의미군 " + f.slice(3));
    }
    let tok = f.slice(3);   // nm:token
    if (members && members.length >= 2) { const ca = commonAffix(members); if (ca && ca.length > tok.length) tok = ca; }
    if (members && members.length) {   // 방향 말줄임 — "이 스템으로 시작/끝나는 테이블들" 범위 신호(정확 일치 멤버가 있으면 생략)
      const ns = members.map(normNm);
      if (!ns.some((x) => x === tok)) {
        if (ns.every((x) => x.startsWith(tok))) return tok + "…";
        if (ns.every((x) => x.endsWith(tok))) return "…" + tok;
      }
    }
    return tok;
  };
  const nsKey = (f) => schemaId + "\u0001" + f;   // 그룹 키 네임스페이스(스키마별 유일, 제어문자 구분자)
  const baseOrder = [...groupsBy.keys()].sort((a, b) => (groupsBy.get(b).length - groupsBy.get(a).length) || _metaNatSort(labelOf(a, groupsBy.get(a)), labelOf(b, groupsBy.get(b))));
  // misc 는 항상 마지막(잡동사니가 seriation 으로 가운데 끼는 것 방지)
  const miscIdx = baseOrder.indexOf("misc");
  if (miscIdx >= 0) { baseOrder.splice(miscIdx, 1); baseOrder.push("misc"); }
  const nsIds = baseOrder.map(nsKey);
  const groupOfT = new Map();
  groupsBy.forEach((arr, f) => arr.forEach((t) => groupOfT.set(t.key, nsKey(f))));
  const groupOf = (tk) => groupOfT.get(tk) || null;
  // 그룹 seriation(관계 많은 그룹끼리 인접) — misc 제외 후 재부착(항상 마지막 유지)
  let serIds = _metaRelSchemaOrder(nsIds.filter((k) => k !== nsKey("misc")), adj, groupOf);
  if (groupsBy.has("misc")) serIds.push(nsKey("misc"));
  // feature-0016 §49(요구②, 적대리뷰 R1): 그룹 순서 안정화 — 이웃확장 rebuild 시 그룹이 재-seriate 되어 형제가 점프하지
  //   않도록 직전 순서(groupOrder[schemaId])를 보존하고 신규 그룹만 append. (misc 는 위에서 이미 마지막.)
  serIds = _metaStableSeq(serIds, _metaGraph.groupOrder.get(schemaId), (x) => x);
  _metaGraph.groupOrder.set(schemaId, serIds.slice());
  const gIdx = new Map(serIds.map((k, i) => [k, i]));
  // 그룹 내 순서: 컴포넌트 군집 + 그룹-간 barycenter (컨테이너=그룹으로 _metaRelOrderAll 재사용)
  const pseudo = new Map();
  groupsBy.forEach((arr, f) => pseudo.set(nsKey(f), { isTerms: false, tables: arr, terms: [], colsByTable: new Map() }));
  const ordered = _metaRelOrderAll(pseudo, serIds, adj, gIdx, groupOf);
  // feature-0016 §49(R1): 그룹 내 테이블 순서 안정화 — 신규 테이블만 append(기존 테이블 그룹내 열/행 위치 유지).
  serIds.forEach((k) => {
    const _fr = ordered.get(k); if (!_fr) return;
    const _st = _metaStableSeq(_fr, _metaGraph.groupTableOrder.get(k), (t) => t.key);
    ordered.set(k, _st);
    _metaGraph.groupTableOrder.set(k, _st.map((t) => t.key));
  });
  const list = serIds.map((k) => {
    const f = k.slice(schemaId.length + 1);
    const arr = ordered.get(k) || groupsBy.get(f) || [];
    return { key: k, fam: f, label: labelOf(f, arr), n: arr.length, tables: arr };
  }).filter((g) => g.n > 0);
  return list;
}

// 그룹 블록 시각 팔레트(연한 틴트 8종 순환 — 칩 teal·역할색과 경쟁하지 않는 저채도 배경/테두리)
const _META_GROUP_TINTS = [
  { bg: "#eef4fb", hd: "#dbe7f7", bd: "#b9cfe8" },
  { bg: "#eff8f1", hd: "#dcefe1", bd: "#bcdcc6" },
  { bg: "#fdf6ec", hd: "#f7e8cf", bd: "#e6cfa3" },
  { bg: "#f7f0fa", hd: "#ecdcf3", bd: "#d5b9e4" },
  { bg: "#fbf0f2", hd: "#f4dbe1", bd: "#e4b9c4" },
  { bg: "#eef7f9", hd: "#d9edf2", bd: "#b3d8e2" },
  { bg: "#f4f6ee", hd: "#e7ecd7", bd: "#cdd8ab" },
  { bg: "#f3f4f7", hd: "#e3e6ec", bd: "#c6ccd8" },
];

// 모델(_metaGraph.nodes/edges) → 위치 포함 G6 데이터. 스키마 클러스터를 관계 seriation(무관계 시 자연정렬)
// grid 로, 클러스터 내부는 유사 속성 그룹 블록(배경 박스+헤더, graph-simgroups)으로, 펼친 테이블의 컬럼을
// 그 아래 세로열로 결정론 배치(무-shuffle). 그룹이 1개뿐이면 기존 평면 masonry 그대로(시각 노이즈 방지).
// feature-0016 §49(요구②): 시퀀스 안정화 — 저장된 순서(savedKeys)의 항목을 먼저(현재 존재하는 것만, 저장 순서대로),
//   신규 항목은 fresh(seriated) 순서로 뒤에 append. 이웃확장 rebuild 시 기존 항목이 masonry 슬롯을 유지하고 신규만
//   추가돼 '더블클릭 시 전체 재배치' 를 제거한다. keyOf: 항목→비교 key. 순수 함수(부수효과 없음).
function _metaStableSeq(fresh, savedKeys, keyOf) {
  const byKey = new Map();
  fresh.forEach((x) => { byKey.set(keyOf(x), x); });
  const out = [], seen = new Set();
  (savedKeys || []).forEach((k) => { if (byKey.has(k) && !seen.has(k)) { out.push(byKey.get(k)); seen.add(k); } });
  fresh.forEach((x) => { const k = keyOf(x); if (!seen.has(k)) { out.push(x); seen.add(k); } });
  return out;
}

// graph-category(§55 A, REQ-20260706 ①): 스키마 클러스터의 **제품 카테고리** 배정 + ids 재배열.
//   WebProductDatabases(제품별 접근 DB SSOT)의 스키마→제품 매핑(schemaProducts)으로 각 클러스터를
//   catKey("PC:<제품id>" | "PC:__none__" 미분류)에 배정한다 — 하위 '유사 속성 그룹'(sim-group)과 같은
//   가시적 구분(배경 밴드+헤더 칩)의 데이터 계층. 매핑이 전무하면 enabled=false(기존 배치 그대로 — 회귀 0).
//   다제품 스키마는 대표 제품(백엔드 정렬 1순위 = 제품 SortOrder)으로 배정하고 상세에서 전체 노출.
function _metaCatAssign(ids) {
  const res = { enabled: false, cats: [], inCat: new Set(), ids: null };
  const sp = _metaGraph.schemaProducts;
  const core = (ids || []).filter((k) => k !== _META_TERMS_COMBO);
  if (!sp || !sp.size || !core.length) return res;
  const byCat = new Map();
  let mapped = 0;
  // 패널 MINOR fix: 매핑은 schemaProducts 가 로드된 scope 의 클러스터에만 적용 — 크로스-DS 이웃확장으로
  //   유입된 타 scope 클러스터가 동명 DB 로 현재 제품 밴드에 오배정되지 않게(타 scope = 미분류).
  const spScope = String(_metaGraph.loadedScope || "");
  core.forEach((id) => {
    const inScope = !spScope || String(id).startsWith(spScope + ":");
    const nm = String(_metaComboName(id) || "").toLowerCase();
    const plist = inScope ? sp.get(nm) : null;
    let key = "PC:__none__", label = "미분류", sort = Number.MAX_SAFE_INTEGER;
    if (Array.isArray(plist) && plist.length) {
      const p = plist[0];
      key = "PC:" + p.id; label = p.name || ("제품#" + p.id);
      sort = (typeof p.sort === "number" ? p.sort : 100) * 100000 + (p.id || 0);
      mapped++;
    }
    let c = byCat.get(key);
    if (!c) { c = { key, label, sort, members: [] }; byCat.set(key, c); }
    c.members.push(id);
  });
  if (!mapped) return res;   // 전부 미분류 → 카테고리 계층 미방출(단일 흐름 유지)
  const cats = [...byCat.values()].sort((a, b) =>
    ((a.key === "PC:__none__") - (b.key === "PC:__none__")) || (a.sort - b.sort) || _metaNatSort(a.label, b.label));
  // §49 동형: 카테고리 순서 안정화 — rebuild 시 밴드가 자리를 점프하지 않게.
  const stable = _metaStableSeq(cats, _metaGraph.catOrder, (c) => c.key);
  _metaGraph.catOrder = stable.map((c) => c.key);
  _metaGraph.catMembers = new Map(); _metaGraph.catLabelOf = new Map();
  const pos = new Map(core.map((k, i) => [k, i]));
  const ordered = [];
  stable.forEach((c) => {
    c.memberSet = new Set(c.members);
    // 접힘: 사용자 지속 의도. 단 검색 매칭/추가 스키마를 품은 카테고리는 강제 펼침(결과 가시 — 그룹 접힘 동형).
    c.collapsed = _metaGraph.catCollapsed.has(c.key) && !c.members.some((sid) =>
      (_metaGraph.searchMatch && _metaGraph.searchMatch.has(sid)) || _metaGraph.searchAdded.has(sid));
    c.members.sort((a, b) => pos.get(a) - pos.get(b));   // 카테고리 내부는 기존(안정화된) 클러스터 순서 유지
    c.members.forEach((m) => { res.inCat.add(m); ordered.push(m); });
    _metaGraph.catMembers.set(c.key, c.members.slice());
    _metaGraph.catLabelOf.set(c.key, c.label);
  });
  res.enabled = true; res.cats = stable; res.ids = ordered;
  return res;
}

function _metaG6Build() {
  // graph-product-cat(§43): 제품 카테고리 개요는 전용 경로(Product→Datasource 2-열, combo 미사용) —
  //   기존 스키마 masonry 무간섭·저위험(ADR-014). mode 가 "products" 일 때만 발동.
  if (_metaGraph.mode === "products") return _metaG6BuildProducts();
  _metaGraph.tableDeps = new Map();   // graph-drag(REQ ②): 전체 재구성마다 종속 UI 맵 리셋(Table key -> 종속 노드 id[]).
  _metaGraph.groupMembers = new Map();   // group-interact(§50): 매 build 그룹→멤버 인덱스 재구성(펼친 그룹만 emission 에서 채움).
  _metaGraph.groupOf = new Map();        // group-interact(§50): 매 build 테이블→groupKey 역인덱스 재구성.
  const groups = new Map();   // comboId -> {isTerms, tables:[], terms:[], colsByTable:Map(tKey->[cols])}
  const ensureG = (id) => { if (!groups.has(id)) groups.set(id, { isTerms: id === _META_TERMS_COMBO, tables: [], terms: [], colsByTable: new Map() }); return groups.get(id); };
  const tableByKey = new Map();
  _metaGraph.nodes.forEach((n) => { if (n.label === "Table") tableByKey.set(n.key, n); });
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Schema") { ensureG(n.key); return; }
    if (n.label === "Table") { ensureG(_metaSchemaComboOf(n)).tables.push(n); return; }
    if (n.label === "Routine") {
      // graph-navfilter(§54②): kind 필터 — 빌드 입력에서 제외(masonry/simgroups 가 자리 자동 회수).
      //   분류식은 _metaRoutineIcon 과 동일(빈값·미상 = procedure/⚙).
      const rk = (n.routine_type === "function") ? "function" : "procedure";
      if (_metaGraph.hiddenKinds.has(rk)) return;
      // graph-funcproc(ADR-016): 함수·프로시저는 테이블과 나란히 소속 스키마 클러스터 열에 선다.
      const sc = _metaSchemaComboOf(n);
      if (sc !== _META_TERMS_COMBO) { ensureG(sc).tables.push(n); return; }
      ensureG(_META_TERMS_COMBO).terms.push(n); return;
    }
    if (n.label === "Column") {
      const tk = _metaColParent(n.key, n.fqn);
      const g = ensureG(_metaSchemaComboOf(n));
      if (tk && tableByKey.has(tk)) { if (!g.colsByTable.has(tk)) g.colsByTable.set(tk, []); g.colsByTable.get(tk).push(n); }
      return;
    }
    ensureG(_META_TERMS_COMBO).terms.push(n);   // GlossaryTerm/Datasource/Product/기타
  });
  // 클러스터 순서: 관계 seriation(graph-rel-layout, 무관계 시 자연정렬 유지), terms 클러스터는 항상 마지막.
  const relAdj = _metaRelAdjacency(tableByKey);
  const relSchemaOf = (tk) => { const n = tableByKey.get(tk); return n ? _metaSchemaComboOf(n) : null; };
  const ids = _metaRelSchemaOrder([...groups.keys()].filter((k) => k !== _META_TERMS_COMBO).sort(_metaNatSort), relAdj, relSchemaOf);
  if (groups.has(_META_TERMS_COMBO)) ids.push(_META_TERMS_COMBO);
  // feature-0016 §49(요구②): 클러스터 순서 안정화 — 이웃확장/펼침 rebuild 의 re-seriation 으로 클러스터가 그리드를
  //   점프하지 않도록 직전 순서(clusterOrder)를 보존하고 신규 클러스터만 seriated 순서로 append. terms combo 는 항상
  //   마지막. fresh load(resetModel) 시 clusterOrder=[] 라 순수 seriation(첫 배치 동일). 드래그와 직교(원점은 shelf-pack).
  {
    const _hasTerms = ids.length && ids[ids.length - 1] === _META_TERMS_COMBO;
    const _core = _metaStableSeq(_hasTerms ? ids.slice(0, -1) : ids.slice(), _metaGraph.clusterOrder, (x) => x);
    _metaGraph.clusterOrder = _core.slice();
    ids.length = 0; _core.forEach((id) => ids.push(id)); if (_hasTerms) ids.push(_META_TERMS_COMBO);
  }
  // graph-category(§55 A): 제품 카테고리 배정 + ids 를 카테고리 순으로 재배열(카테고리 내부는 위
  //   안정화 순서 유지, terms 는 항상 마지막). 매핑 전무(enabled=false)면 완전 무개입 — 기존 배치.
  const catInfo = _metaCatAssign(ids);
  if (catInfo.enabled) {
    const _hasTerms2 = ids.length && ids[ids.length - 1] === _META_TERMS_COMBO;
    ids.length = 0; catInfo.ids.forEach((id) => ids.push(id)); if (_hasTerms2) ids.push(_META_TERMS_COMBO);
  }
  const schemaIdx = new Map(ids.map((s, i) => [s, i]));   // 테이블 순서의 외부-관계 앵커(이웃 스키마 방향) 조회용
  const relOrder = _metaRelOrderAll(groups, ids, relAdj, schemaIdx, relSchemaOf);   // 스키마별 테이블 순서(군집 + barycenter 4-sweep)
  // feature-0016 §49(요구②): 클러스터 내 테이블 순서 안정화(flat masonry 경로) — 신규 테이블/루틴만 append → 기존
  //   테이블이 masonry 열/슬롯을 유지(이웃확장 시 형제 점프 제거). simgroups(구조화 스키마) 경로는 _metaSimGroups
  //   내부에서 그룹 순서·그룹내 테이블 순서를 동일 방식으로 안정화(적대리뷰 R1 반영). 잔여(R2): innerCols 임계
  //   (7/15/28) 교차 시 열 수가 바뀌어 해당 클러스터만 재열 — 반응형 레이아웃 고유 트레이드오프(비파괴, '공간 확보').
  ids.forEach((id) => {
    if (id === _META_TERMS_COMBO) return;
    const _fresh = relOrder.get(id); if (!_fresh) return;
    const _stable = _metaStableSeq(_fresh, _metaGraph.tableOrder.get(id), (t) => t.key);
    relOrder.set(id, _stable);
    _metaGraph.tableOrder.set(id, _stable.map((t) => t.key));
  });

  // ── 클러스터 내 다열 masonry(높이 균형) + 가변폭 클러스터 shelf-packing ──
  //   구버전(단일 세로열 + 고정 3열 grid)은 테이블 많은 스키마가 끝없이 길어지고 36클러스터가 세로로 쌓여
  //   fit-all 시 전부 극소로 축소됐다. 다열 masonry 로 클러스터를 넓고 낮게, shelf-pack 으로 가로 활용을 극대화한다.
  const COLW = 224;                 // 클러스터 내부 열 폭(테이블 칩 190 + 펼친 컬럼 라벨 168 여유; review MINOR: 214→224 로 최대길이 컬럼명이 인접열 칩에 겹치지 않게)
  const TXOFF = 95;                 // 열 좌측 기준 테이블 중심 x
  const CDROP = 6;                  // 테이블↔첫 컬럼 간격
  const MAXROWW = 2400;             // shelf(행) 목표 최대 폭(모델 px) — 초과 시 다음 행으로 래핑
  const innerColsFor = (n) => (n <= 6 ? 1 : n <= 14 ? 2 : n <= 27 ? 3 : 4);
  // ── churn 분리(graph-perf-bg 성능 + 사용자 체리픽): 열 "배정"과 기준 top 은 **펼침-불변** 높이로 고정하고,
  //   펼친 테이블의 실제 높이는 **자기 열 안에서만** 아래로 밀어낸다. graph-g6b 는 최단 열을 *실제* colCur(펼친
  //   컬럼 포함)로 골라, T 펼침 시 형제 테이블이 열을 옮겨다니며 x/y 동시 점프 → setData update 집합 팽창 +
  //   in-place 불안정(ADR-004 ②). 배정을 collapsed 높이로 고정하면 형제 col 이 {순서·개수·ic} 의 순수함수라
  //   펼침에 불변 → 형제 열-점프 제거. **shelf-packer 는 여전히 실제 높이 h 를 소비한다**(아래 유지). h 를
  //   collapsed 로 얼리면 콤보 카드·컬럼원이 auto-grow 로 아래 shelf 에 넘쳐 겹침(ADR-004 ②/⑤) — 절대 얼리지 말 것.
  const assignH = (g) => g.isTerms ? _METLAY.TROW : (_METLAY.TROW + _METLAY.TGAP);   // 펼침-불변(=collapsed itemH)
  const realH = (g, t) => {         // 펼친 컬럼 포함 실제 높이(자기 열 push-down + 클러스터 h 전용)
    const cols = g.colsByTable.get(t.key);
    let sub = (cols && cols.length) ? cols.length * _METLAY.CROW + CDROP : 0;
    // graph-navfilter(§54⑤): Routine 파라미터 펼침도 실높이에 반영(컬럼과 동형) — assignH(펼침-불변
    //   Pass1)는 절대 건드리지 않는다. masonry Pass2·packGroup·GB bbox·shelf-pack 이 이 클로저를 소비.
    if (!sub && t.label === "Routine" && _metaGraph.routineExpanded.has(t.key)) {
      const pn = _metaRoutineParamList(t).length;
      if (pn) sub = pn * _METLAY.CROW + CDROP;
    }
    return _METLAY.TROW + sub + _METLAY.TGAP;
  };
  // ── graph-simgroups: 그룹 블록 기하 상수 + 그룹 내부 2-pass masonry ──
  const GHH = 26;                   // 그룹 헤더 행 높이(헤더 칩 + 상단 여백)
  const GPX = 12;                   // 그룹 블록 내부 좌우 pad
  const GPB = 10;                   // 그룹 블록 하단 pad
  const GGX = 14, GGY = 16;         // 그룹 블록 간 가로/세로 간격
  const TRW = 4 * COLW + 3 * GGX;   // 클러스터 내부 그룹 행 목표 폭(≈기존 4열 masonry 폭 유지)
  const gInnerColsFor = (n) => (n <= 4 ? 1 : n <= 12 ? 2 : 3);
  // 그룹 내부 masonry(기존 철학 동일): Pass1 배정=collapsed(펼침-불변), Pass2 top=실 높이 push-down.
  const packGroup = (g, arr) => {
    const gic = gInnerColsFor(arr.length);
    const colBase = new Array(gic).fill(0);
    const assigned = arr.map((it) => {
      let c = 0; for (let k = 1; k < gic; k++) if (colBase[k] < colBase[c]) c = k;
      colBase[c] += assignH(g);
      return { it, col: c };
    });
    const colTop = new Array(gic).fill(0);
    const inner = assigned.map(({ it, col }) => {
      const top = colTop[col];
      colTop[col] += realH(g, it);
      return { it, col, top };
    });
    return { gic, inner,
      w: GPX * 2 + gic * COLW,
      h: GHH + Math.max(0, ...colTop) + GPB };   // 실 높이(펼친 컬럼 포함) — 행 y push-down 이 소비
  };
  // 각 클러스터 레이아웃 선산정(폭·높이 + 항목 절대 오프셋 배치).
  //   place 항목은 {it, lx(열 좌측 x — 클러스터 상대), top(항목 상단 y — 클러스터 상대)} 로 정규화 —
  //   평면/그룹 두 경로가 같은 렌더 루프를 공유한다.
  const layouts = ids.map((id) => {
    const g = groups.get(id);
    // graph-initview: 스키마 카드 게이팅(모드-독립 단일소스 schemaExpanded) — 접힌 스키마는 카드로만.
    //   검색/이웃 흐름은 결과 스키마를 schemaExpanded 에 자동 추가하므로 응답 노드는 항상 보인다.
    const gatedTables = (!g.isTerms && !_metaGraph.schemaExpanded.has(id)) ? [] : g.tables;
    if (!g.isTerms && !gatedTables.length && !g.terms.length) {
      return { id, g, kind: "card", w: _METLAY.CARDW, h: _METLAY.CARDH, x0: 0, y0: 0 };
    }
    // graph-simgroups: 유사 속성 그룹 분할 — 2개 이상일 때만 그룹 블록 렌더(1개면 기존 평면 masonry 유지).
    const simGroups = (!g.isTerms && gatedTables.length) ? _metaSimGroups(id, gatedTables, relAdj) : null;
    if (simGroups && simGroups.length >= 2) {
      // 그룹 블록 shelf-pack: 행 배정은 블록 폭(펼침-불변)만 소비, 행 y 는 실 높이 누적(push-down —
      //   펼친 컬럼이 자기 블록 높이를 키우면 아래 "행"만 밀리고 좌우 이웃 블록 x 는 불변).
      // group-interact(§50): 접힌 그룹은 헤더만(HDONLY) 높이로 블록 축소 → shelf-pack 자동 reflow.
      //   검색 매칭 멤버가 있는 그룹은 접힘 상태여도 강제 펼침(결과 가시 — schemaExpanded 자동추가와 동형).
      const HDONLY = GHH + GPB;
      const smt = (_metaGraph.mode === "search") ? _metaGraph.searchMatchTables : null;
      const isCollapsed = (sg) => _metaGraph.groupCollapsed.has(sg.key)
        && !(smt && sg.tables.some((t) => smt.has(t.key)));
      const blocks = simGroups.map((sg, gi) => {
        const p = packGroup(g, sg.tables);
        const collapsed = isCollapsed(sg);
        return Object.assign({ sg, gi, collapsed, hEff: collapsed ? HDONLY : p.h }, p);
      });
      const rows = [];
      { let cur = { blocks: [], w: 0 };
        blocks.forEach((b) => {
          if (cur.blocks.length && cur.w + b.w > TRW) { rows.push(cur); cur = { blocks: [], w: 0 }; }
          b.bxRel = _METLAY.PADX + cur.w; cur.blocks.push(b); cur.w += b.w + GGX;
        });
        if (cur.blocks.length) rows.push(cur); }
      let byy = _METLAY.PADT + 6, contentW = 0;
      rows.forEach((row) => {
        const rowH = Math.max(...row.blocks.map((b) => b.hEff));   // 접힌 블록은 헤더만 소비(펼친 이웃 높이에 얹힘)
        row.blocks.forEach((b) => { b.byRel = byy; });
        contentW = Math.max(contentW, row.w - GGX);
        byy += rowH + GGY;
      });
      const place = [];
      const groupsMeta = [];
      blocks.forEach((b) => {
        // group-interact(§50): sim-group 자유 배치 offset(드래그 누적) — 박스·헤더·멤버 place 공통 가산
        //   (cluster L.x0/L.y0 위, node nodePos 아래 — 3계층). GB 박스 실제 기하는 emission 이 멤버 bbox 로 파생.
        const goff = _metaGraph.groupOffset.get(b.sg.key);
        const gdx = goff ? goff.dx : 0, gdy = goff ? goff.dy : 0;
        // group-interact(§50, REV-wiring MAJOR fix): groupMembers/groupOf 는 **전체 멤버**(접힘 포함)로 채운다.
        //   emission pre-pass 는 방출된(펼친) 멤버만 알아 접힌 그룹이 인덱스에서 누락 → 접힌 그룹 드래그 시 그
        //   멤버 nodePos 시프트가 스킵돼(펼치면 nodePos 멤버만 옛 좌표에 남아 분리). 여기서 b.sg.tables 로 전량 등록.
        b.sg.tables.forEach((t) => {
          _metaGraph.groupOf.set(t.key, b.sg.key);
          let mm = _metaGraph.groupMembers.get(b.sg.key); if (!mm) { mm = []; _metaGraph.groupMembers.set(b.sg.key, mm); } mm.push(t.key);
        });
        groupsMeta.push({ key: b.sg.key, label: b.sg.label, n: b.sg.n,
          x: b.bxRel + gdx, y: b.byRel + gdy, w: b.w, h: b.collapsed ? HDONLY : b.h,
          collapsed: b.collapsed, tint: _META_GROUP_TINTS[b.gi % _META_GROUP_TINTS.length] });
        if (b.collapsed) return;   // 접힌 그룹은 멤버 미방출(헤더 칩만 — 개수로 내용 인지)
        b.inner.forEach(({ it, col, top }) => {
          place.push({ it, group: b.sg.key,
            lx: b.bxRel + gdx + GPX + col * COLW, top: b.byRel + gdy + GHH + top });
        });
      });
      const w = _METLAY.PADX * 2 + contentW;
      const h = byy - GGY + 16;   // 마지막 행 실 높이 포함(펼친 컬럼 auto-grow 겹침 방지 — collapsed 로 얼리지 말 것)
      return { id, g, place, groupsMeta, w, h, x0: 0, y0: 0 };
    }
    // ── 평면 masonry(기존 경로): terms 클러스터 · 그룹 <2 스키마 — place 를 {it,lx,top} 로 정규화 ──
    // graph-rel-layout: 테이블 순서는 _metaRelOrderAll 사전 산정분(관계-군집+barycenter, 무관계 시 자연정렬과
    //   동일)을 그대로 소비 — 여기서 재정렬하면 같은 배열의 중복 nat-sort(§18.8 패널 MINOR). terms 만 즉석 정렬.
    const items = g.isTerms
      ? g.terms.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key))
      : (relOrder.get(id) || gatedTables.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key)));
    const ic = innerColsFor(items.length);
    // Pass 1(배정): collapsed 균등 높이로 최단 열 선택 → col 은 펼침-불변(형제 열-점프 제거).
    const colBase = new Array(ic).fill(_METLAY.PADT);
    const assigned = items.map((it) => {
      let c = 0; for (let k = 1; k < ic; k++) if (colBase[k] < colBase[c]) c = k;   // 최단 열(collapsed 기준)
      colBase[c] += assignH(g);
      return { it, col: c };
    });
    // Pass 2(밀어내기): 열별 실제 누적 오프셋으로 top 확정 → 펼친 테이블은 "자기 열 아래"만 민다.
    const colTop = new Array(ic).fill(_METLAY.PADT);
    const place = assigned.map(({ it, col }) => {
      const top = colTop[col];
      colTop[col] += g.isTerms ? _METLAY.TROW : realH(g, it);
      return { it, lx: _METLAY.PADX + col * COLW, top };
    });
    const w = _METLAY.PADX * 2 + ic * COLW;
    const h = Math.max(_METLAY.PADT, ...colTop) + 16;   // 실제 높이 — shelf-packer 가 소비(겹침 방지, 절대 collapsed 로 얼리지 말 것)
    return { id, g, place, w, h, x0: 0, y0: 0 };
  });
  // shelf-packing: 가변폭 클러스터를 좌→우로 채우고, 폭 초과 시 다음 행으로.
  // graph-category(§55 A): 카테고리 활성 시 **카테고리 밴드별로** 분할 패킹 — 각 카테고리가 자기 행들을
  //   좌→우로 채우고, 밴드는 세로로 스택된다(헤더 CATHH 확보). 접힌 카테고리는 멤버를 방출하지 않고
  //   (catHidden) 헤더 밴드만 남긴다. 비활성(enabled=false)이면 기존 단일 흐름 그대로.
  const CATHH = 36;   // 카테고리 헤더 밴드 높이(칩 + 상단 여백)
  if (!catInfo.enabled) {
    let cx = 0, cyy = 0, shelfH = 0;
    layouts.forEach((L) => {
      if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; cyy += shelfH + _METLAY.GAPY; shelfH = 0; }
      L.x0 = cx; L.y0 = cyy; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
    });
  } else {
    const layById = new Map(layouts.map((L) => [L.id, L]));
    let cyy = 0;
    catInfo.cats.forEach((cat) => {
      cat.bandY = cyy;
      const catLays = cat.members.map((id) => layById.get(id)).filter(Boolean);
      if (cat.collapsed) {
        catLays.forEach((L) => { L.catHidden = true; });
        cyy += CATHH + _METLAY.GAPY;   // 헤더 밴드만 차지
        return;
      }
      let cx = 0, rowY = cyy + CATHH, shelfH = 0;
      catLays.forEach((L) => {
        if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; rowY += shelfH + _METLAY.GAPY; shelfH = 0; }
        L.x0 = cx; L.y0 = rowY; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
      });
      cyy = rowY + shelfH + _METLAY.GAPY + 22;   // 밴드 간 여유(+22 — 밴드 하단 패딩 시각 분리)
    });
    // 카테고리 무소속(terms 클러스터 등)은 마지막 밴드 아래 단일 흐름으로.
    { let cx = 0, rowY = cyy, shelfH = 0;
      layouts.forEach((L) => {
        if (catInfo.inCat.has(L.id)) return;
        if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; rowY += shelfH + _METLAY.GAPY; shelfH = 0; }
        L.x0 = cx; L.y0 = rowY; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
      }); }
  }
  // graph-freeplace: 사용자 드래그 클러스터 offset 을 packing 결과에 가산(렌더 위치만 — 폭 누적/행 배정엔 미개입).
  //   L.x0/L.y0 가 카드·테이블·컬럼·장식·combo 의 공통 기준이라, 여기서 가산하면 클러스터 전체가 coherent 하게
  //   이동하고 펼침/접기 rebuild 후에도 유지된다(자유 배치 persistence — ADR-004 결정론 배치 회귀 복원).
  layouts.forEach((L) => {
    const off = _metaGraph.clusterOffset.get(L.id);
    if (off) { L.x0 += off.dx; L.y0 += off.dy; }
  });
  const combos = [], nodes = [], edges = [];
  _metaGraph.firstElementId = null;
  // graph-category(§55 A): 카테고리 밴드(CAT: 배경 + CATH: 헤더 칩 + CATX: 접기) 방출 — 박스 기하는
  //   멤버 클러스터의 **최종 배치(clusterOffset 반영) bbox + 패딩** 파생(sim-group GB bbox 동형 —
  //   클러스터 이동에 반응형). 접힌 카테고리는 헤더 밴드만. zIndex: 배경 CAT_BG(-1, combo 아래) /
  //   헤더 GROUP_HD / 컨트롤 CTL. 헤더 드래그 = 카테고리 리지드 이동(멤버 clusterOffset 일괄 누적).
  if (catInfo.enabled) {
    const layById2 = new Map(layouts.map((L) => [L.id, L]));
    catInfo.cats.forEach((cat, ci) => {
      const vis = cat.members.map((id) => layById2.get(id)).filter((L) => L && !L.catHidden);
      let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
      vis.forEach((L) => {
        left = Math.min(left, L.x0); top = Math.min(top, L.y0);
        right = Math.max(right, L.x0 + L.w); bottom = Math.max(bottom, L.y0 + L.h);
      });
      const PADX2 = 22, PADB2 = 18;
      let bl, bt, bw, bh;
      if (vis.length && isFinite(left)) {
        bl = left - PADX2; bt = top - CATHH; bw = (right + PADX2) - bl; bh = (bottom + PADB2) - bt;
      } else {   // 접힘(또는 전 멤버 미방출) — 헤더 밴드만
        bl = -PADX2; bt = cat.bandY || 0; bw = 720; bh = CATHH;
      }
      const tint = _META_GROUP_TINTS[ci % _META_GROUP_TINTS.length];
      nodes.push({ id: "CAT:" + cat.key, type: _METtype,
        data: { kind: "cat-bg", cat: cat.key },
        style: { x: bl + bw / 2, y: bt + bh / 2, size: [bw, bh], radius: 14,
          fill: tint.bg, fillOpacity: 0.38, stroke: tint.bd, lineWidth: 1.6, lineDash: [7, 4],
          zIndex: _METZ.CAT_BG, cursor: "move" } });
      const hdText = `🗂 ${cat.label} · ${cat.members.length} DB`;
      const hdW = Math.min(Math.max(80, Math.round(hdText.length * 8.2) + 22), Math.max(120, bw - 46));
      nodes.push({ id: "CATH:" + cat.key, type: _METtype,
        data: { kind: "cat-hd", cat: cat.key, label: cat.label },
        style: { x: bl + 12 + hdW / 2, y: bt + 16, size: [hdW, 22], radius: 11,
          fill: tint.hd, stroke: tint.bd, lineWidth: 1.2, zIndex: _METZ.GROUP_HD, cursor: "move",
          labelText: hdText, labelFill: "#1d2635", labelFontSize: 12, labelFontWeight: 700,
          labelPlacement: "center" } });
      nodes.push({ id: "CATX:" + cat.key, type: _METtype,
        data: { label: cat.collapsed ? "+" : "−", kind: "cat-ctl", cat: cat.key },
        style: Object.assign(_metaCtlStyle(bl + bw - 16, bt + 16), { size: [18, 18],
          labelText: cat.collapsed ? "+" : "−", labelFontSize: 15 }) });
    });
  }
  layouts.forEach((L) => {
    const { id, g } = L;
    if (L.catHidden) return;   // graph-category(§55 A): 접힌 카테고리 멤버 — 클러스터 전체 미방출
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = (L.kind === "card") ? ("SC:" + id) : id;
    if (L.kind === "card") {
      // id 는 "SC:" 네임스페이스 — 같은 스키마 key 가 펼침 시 combo id 로 쓰이므로, 동일 id 의
      // 노드↔combo 타입 전환을 G6 setData diff 가 처리하지 못하는 문제(자식 유실)를 원천 차단.
      const cn = _metaGraph.nodes.get(id);
      const cnt = (cn && typeof cn.table_count === "number") ? cn.table_count : null;
      const nmc = _metaComboName(id);
      // graph-initview UI: 라벨은 스키마명만(전체 폭 확보) + 개수는 우상단 **badge**(작은 pill).
      //   검색 없음 → [전체 테이블 개수]. 검색 필터 → [매칭 테이블 개수 / 전체 테이블 개수](사용자 요청).
      //   badge 는 이름과 폭 경쟁 없이 개수를 노출(집계 실패 cnt=null 은 badge 없음 = 배지없는 카드 강등 정합).
      let badgeText = (cnt != null) ? String(cnt) : null;
      let badgeBg = _META_GRAPH_COLOR.Schema;
      if (_metaGraph.mode === "search" && _metaGraph.searchMatch && _metaGraph.searchMatch.has(id)) {
        const matched = _metaGraph.searchMatch.get(id).size;
        const plus = _metaGraph.searchCapped ? "+" : "";   // review MAJOR: cap 도달 시 부분 카운트 표기(≥)
        badgeText = (cnt != null) ? `${matched}${plus}/${cnt}` : `${matched}${plus}`;
        badgeBg = "#0a5b66";   // 검색 필터 badge 는 teal 강조(전체 카운트 남색과 구분)
      }
      const cardStyle = Object.assign(_metaSchemaCardStyle(L.x0 + _METLAY.CARDW / 2, L.y0 + _METLAY.CARDH / 2), {
        labelText: nmc,
        // review MINOR: offset 은 per-item 에 둬야 실제 transform 에 반영(node-level badgeOffsetX/Y 는 무시됨).
        badges: badgeText != null ? [{ text: badgeText, placement: "right-top", offsetX: -2, offsetY: 2 }] : [],
        badgeFontSize: 10, badgeFill: "#ffffff", badgeBackgroundFill: badgeBg, badgePadding: [1, 5],
      });
      nodes.push({ id: "SC:" + id, type: _METtype, states: _metaNodeStates(id),
        data: { label: nmc, kind: "schema-card", schema: id, fqn: (cn && cn.fqn) || nmc, table_count: cnt },
        style: cardStyle });
      return;
    }
    combos.push({ id, type: _METtype, data: { label: _metaComboName(id), kind: "schema" }, style: Object.assign({ labelText: _metaComboName(id) }, _metaComboStyleFor(g.isTerms)) });
    if (!g.isTerms && _metaGraph.schemaExpanded.has(id)) {
      // graph-initview: "−" 접기 컨트롤(combo 우상단) — 카드로 복귀.
      nodes.push({ id: "XS:" + id, type: _METtype, combo: id, data: { label: "−", kind: "schema-ctl", schema: id },
        style: _metaSchemaCtlStyle(L.x0 + L.w - 20, L.y0 + _METLAY.PADT - 26) });
    }
    // graph-simgroups + group-interact(§50): 그룹 배경 박스 + 헤더 칩 + 접기 컨트롤(GX).
    //   #3 반응형: 펼친 그룹의 GB 박스 기하는 **멤버(테이블+펼친 컬럼)의 최종 place bbox + 패딩**에서 파생 —
    //   개별 노드 이동(nodePos)·그룹 이동(groupOffset) 양쪽에 박스가 자동으로 맞춰진다. 접힌 그룹은 헤더 기하.
    //   pre-pass 는 방출된(펼친) 멤버 place 를 1회 훑어 groupBox(절대 경계)를 계산한다(groupMembers/groupOf 는
    //   layout 분기에서 전체 멤버로 이미 채움 — 접힌 그룹 포함, REV-wiring MAJOR fix).
    if (L.groupsMeta) {
      const grpBox = new Map();
      L.place.forEach(({ it, lx, top, group }) => {
        if (!group) return;
        let colLeftX = L.x0 + lx;
        let ty = L.y0 + top + _METLAY.TROW / 2;
        const _fp = _metaGraph.nodePos.get(it.key);   // 개별 드래그 위치(place-loop 과 동일 수학)
        if (_fp && isFinite(_fp[0]) && isFinite(_fp[1])) { colLeftX += _fp[0] - (colLeftX + TXOFF); ty = _fp[1]; }
        const topAbs = ty - _METLAY.TROW / 2, memBottom = topAbs + realH(g, it);
        let bx = grpBox.get(group);
        if (!bx) { bx = { minL: Infinity, minT: Infinity, maxR: -Infinity, maxB: -Infinity }; grpBox.set(group, bx); }
        bx.minL = Math.min(bx.minL, colLeftX); bx.maxR = Math.max(bx.maxR, colLeftX + COLW);
        bx.minT = Math.min(bx.minT, topAbs);   bx.maxB = Math.max(bx.maxB, memBottom);
      });
      L.groupsMeta.forEach((gm) => {
        // 펼침: 멤버 bbox 파생(무멤버 방어 시 패킹 폴백) · 접힘: 패킹 헤더 기하.
        const bx = (!gm.collapsed) ? grpBox.get(gm.key) : null;
        let left, top, right, bottom;
        if (bx && isFinite(bx.minL)) { left = bx.minL - GPX; top = bx.minT - GHH; right = bx.maxR + GPX; bottom = bx.maxB + GPB; }
        else { left = L.x0 + gm.x; top = L.y0 + gm.y; right = left + gm.w; bottom = top + gm.h; }
        const bw = right - left, bh = bottom - top;
        nodes.push({ id: "GB:" + gm.key, type: _METtype, combo: id,
          data: { kind: "group-bg", group: gm.key, schema: id },
          style: { x: left + bw / 2, y: top + bh / 2, size: [bw, bh], radius: 10,
            // graph-zorder(§52): GROUP_BG(1) — 예전 -2 는 combo 배경(z0) **아래**라 @antv/g hit-test 에서 combo 에
            //   삼켜져 §50 그룹 상호작용(배경 드래그=그룹 이동·클릭·우클릭)이 dead 였고, 그룹 배경을 잡으면
            //   클러스터 전체가 이동했다(의미 불일치). combo 위·엣지(2)/칩(4) 아래로 정렬해 의미·hit-test 정합.
            // 패널 ux MAJOR: GB 는 이제 그룹 드래그 핸들로 실동작 — cursor:move 로 어포던스 표시
            //   (클러스터 이동은 combo 여백·라벨·접힌 카드 경로 — 범례에 안내).
            fill: gm.tint.bg, fillOpacity: 0.75, stroke: gm.tint.bd, lineWidth: 1.2, zIndex: _METZ.GROUP_BG, cursor: "move" } });
        const hdText = `${gm.label} · ${gm.n}`;
        const hdW = Math.min(Math.max(46, Math.round(hdText.length * 7.2) + 18), bw - 36);   // GX 컨트롤 자리(우측 ~20px) 확보
        // group-interact(§50 hotfix, PB-0008) + graph-zorder(§52): GH 헤더 = GROUP_HD(5) — 칩(4) 위 드래그
        //   핸들. 음수면 combo 배경(z0) 뒤에 렌더돼 @antv/g hit-test 에서 combo 에 가려, 헤더 드래그가
        //   node:dragstart 대신 combo:dragstart(클러스터 이동)로 발화된다(라이브 실측 결함 — 헤드리스는
        //   zIndex hit-test 미모델). 헤더 스트립엔 멤버가 없어 시각 회귀 0, cursor:move 로 핸들임을 표시.
        nodes.push({ id: "GH:" + gm.key, type: _METtype, combo: id,
          data: { kind: "group-hd", group: gm.key, schema: id, label: gm.label },
          style: { x: left + 8 + hdW / 2, y: top + 13, size: [hdW, 18], radius: 9,
            fill: gm.tint.hd, stroke: gm.tint.bd, lineWidth: 1, zIndex: _METZ.GROUP_HD, cursor: "move",
            labelText: hdText, labelFill: "#273449", labelFontSize: 10.5, labelFontWeight: 600,
            labelPlacement: "center" } });
        // group-interact(§50): 접기/펼치기 토글 컨트롤(그룹 헤더 우측) — 클릭 전용(드래그 불가).
        nodes.push({ id: "GX:" + gm.key, type: _METtype, combo: id,
          data: { label: gm.collapsed ? "+" : "−", kind: "group-ctl", group: gm.key, schema: id },
          style: Object.assign(_metaCtlStyle(right - 13, top + 13), { size: [16, 16], labelText: gm.collapsed ? "+" : "−", labelFontSize: 14 }) });   // graph-zorder(§52): zIndex 는 _metaCtlStyle 의 CTL(6) — GH(5) 위, 항상 클릭 가능
      });
    }
    L.place.forEach(({ it, lx, top }) => {
      let colLeftX = L.x0 + lx;
      let tx = colLeftX + TXOFF;
      let ty = L.y0 + top + _METLAY.TROW / 2;   // 항목(테이블/용어) 중심 y
      // graph-freeplace: 개별 노드 사용자 드래그 위치 유지(테이블은 종속 컬럼·"X:" ctl 과 함께 델타 시프트,
      //   용어는 자기 위치). colLeftX/ty 를 옮기면 아래 컬럼(colLeftX 기반 x·ty 기반 cyCol)이 자동 동반된다.
      //   clusterOffset(클러스터 전체) 위에 얹히는 개별 이동 — combo 는 자식에 맞춰 auto-fit(반응형 리사이즈 #3).
      const _fp = _metaGraph.nodePos.get(it.key);
      if (_fp && isFinite(_fp[0]) && isFinite(_fp[1])) {
        const ddx = _fp[0] - tx, ddy = _fp[1] - ty;
        colLeftX += ddx; tx += ddx; ty += ddy;
      }
      if (it.label === "Routine") {
        // graph-funcproc(ADR-016): 함수(ƒ)/프로시저(⚙) 칩 — 검색 매칭 강조는 테이블과 동일 룰.
        //   §18.8 패널(NIT): isTerms 분기보다 먼저 — 스키마 세그먼트 없는 flat-scope Routine 이
        //   terms 클러스터로 강등돼도 용어 칩이 아닌 ƒ/⚙ 보라 칩으로 렌더된다.
        //   freeplace(_fp)·simgroups 배치(lx/top)는 위 공통 시프트가 이미 반영 — Routine 도 자유 배치 유지.
        const rrel = (_metaGraph.mode === "search" && _metaGraph.searchMatchTables && _metaGraph.searchMatchTables.has(it.key))
          ? Math.max(typeof it.rel === "number" ? it.rel : 0, 0.9) : it.rel;
        const rLabel = _metaRoutineIcon(it.routine_type) + " " + (it.name || it.key);
        nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaNodeStates(it.key),
          data: { label: it.name || it.key, kind: "routine", fqn: it.fqn, routine_type: it.routine_type || "" },
          style: Object.assign(_metaRoutineStyle(tx, ty, rrel), { labelText: rLabel }) });
        // graph-navfilter(§54⑤): 파라미터 수직 배치 — 컬럼(ERD ordinal)과 동형의 서브노드 방출.
        //   params 는 이미 모델에 로드돼 있어(schema_tables/이웃확장 응답) fetch 없는 동기 토글.
        //   순서는 백엔드 ORDINAL_POSITION 정렬 그대로. XR:/RP: 는 합성 id(모델 노드 아님).
        //   패널 MINOR: terms 클러스터(flat-scope 루틴)는 레이아웃 높이 진행이 TROW 고정이라 파라미터
        //   방출 시 아래 항목과 겹침 — terms 에서는 펼침 미지원(상세 패널 세로 목록으로 열람).
        const plist = (!g.isTerms && _metaGraph.routineExpanded.has(it.key)) ? _metaRoutineParamList(it) : [];
        if (plist.length) {
          // routine 칩 폭은 rel-가변(_metaRoutineStyle 과 동일식) — ctl 을 TW/2 고정으로 두면 넓은 칩과 겹침.
          const rw = Math.min(190, _METLAY.TW + (typeof rrel === "number" ? Math.round(rrel * 40) : 0));
          const depIds = ["XR:" + it.key];
          nodes.push({ id: "XR:" + it.key, type: _METtype, combo: id, data: { label: "−", kind: "rctl", routine: it.key },
            style: Object.assign(_metaCtlStyle(tx + Math.round(rw / 2) + 14, ty), { zIndex: _METZ.NODE }) });
          let cyP = ty + _METLAY.TROW / 2 + CDROP + _METLAY.CROW / 2;   // 첫 파라미터 중심 y(컬럼과 동형)
          plist.forEach((ps, i) => {
            const pid = "RP:" + it.key + ":" + i;
            nodes.push({ id: pid, type: "circle", combo: id, states: [], data: { label: ps, kind: "routine-param", routine: it.key },
              style: Object.assign(_metaColStyle(colLeftX + _METLAY.PADX + _METLAY.CIND, cyP), { labelText: ps, fill: _META_GRAPH_COLOR.Routine }) });
            depIds.push(pid);
            cyP += _METLAY.CROW;
          });
          _metaGraph.tableDeps.set(it.key, depIds);   // 드래그 리지드 이동(테이블 종속과 동일 소비처)
        }
        return;
      }
      if (g.isTerms) {
        nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaNodeStates(it.key), data: { label: it.name || it.key, kind: "term", fqn: it.fqn }, style: Object.assign(_metaTermStyle(tx, ty, it.rel), { labelText: it.name || it.key }) });
        return;
      }
      // feature-0016 §45: 검색 매칭 강조는 노드 'match' 상태 soft glow(_metaNodeStates)로 이관 — 폭 부스트(trel) 제거.
      // node-role-viz: 분석 완료 테이블 역할 표식 — 칩 색 = 역할색(Okabe-Ito) + 라벨 앞 역할 아이콘(색약·흑백 중복 인코딩).
      const role = _metaRoleOf(it.key);
      const tLabel = (role ? _META_ROLE[role].icon + " " : "") + (it.name || it.key);
      nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaNodeStates(it.key), data: { label: it.name || it.key, kind: "table", fqn: it.fqn, role: role || null }, style: Object.assign(_metaTableStyle(tx, ty, it.rel, role), { labelText: tLabel }) });
      const cols = g.colsByTable.get(it.key);
      if (cols && cols.length) {
        const depIds = ["X:" + it.key];   // graph-drag(REQ ②): 종속 UI = 접기 ctl + 컬럼 노드들
        nodes.push({ id: "X:" + it.key, type: _METtype, combo: id, data: { label: "−", kind: "ctl", table: it.key },
          // graph-zorder(§52, 패널 ux MINOR): 흐름 내 per-table ctl 은 NODE 밴드 — CTL(6) 전역 최상층이면
          //   타 칩을 그 위로 자유배치했을 때 "−" 가 뚫고 나와 허위 소속(원거리 접기)으로 오독된다.
          //   자기 칩과는 비겹침(+14px 우측) + 같은 밴드 삽입순이라 클릭성 손실 없음. GX/XS(코너 앵커)는 CTL 유지.
          style: Object.assign(_metaCtlStyle(tx + Math.round(_METLAY.TW / 2) + 14, ty), { zIndex: _METZ.NODE }) });
        let cyCol = ty + _METLAY.TROW / 2 + CDROP + _METLAY.CROW / 2;   // 첫 컬럼 중심 y
        cols.slice().sort(_metaGraphColCmp).forEach((c) => {
          nodes.push({ id: c.key, type: "circle", combo: id, states: _metaNodeStates(c.key), data: { label: c.name || c.key, kind: "column", fqn: c.fqn }, style: Object.assign(_metaColStyle(colLeftX + _METLAY.PADX + _METLAY.CIND, cyCol), { labelText: c.name || c.key }) });
          depIds.push(c.key);
          cyCol += _METLAY.CROW;
        });
        _metaGraph.tableDeps.set(it.key, depIds);   // graph-drag(REQ ②): 테이블 → 종속 노드 id 맵
      }
    });
  });
  // 엣지 조립 — HAS_TABLE/HAS_COLUMN 은 containment 라 제외.
  //   graph-reltrace ①: REFERENCES(Column→Column) 끝점을 **렌더된 id 로 해소**한다 — 컬럼이
  //   렌더돼 있으면 컬럼-레벨, 아니면 소속 테이블 노드로 승격. 두 테이블이 접힌 상태에서도 테이블
  //   간 관계 엣지가 보이도록(사용자 요청: "테이블 더블클릭 전까지 관계 미표시" 해소). 같은 두
  //   렌더 끝점으로 승격된 다수 컬럼-쌍은 하나의 집계 엣지로 dedupe 하고, 상태는 최강(trusted>
  //   candidate)을 채택하며 하위 컬럼-쌍을 pairs 로 실어 추적/툴팁에 쓴다.
  const present = new Set(nodes.map((n) => n.id));
  const renderEndpoint = (nodeKey) => {   // 컬럼 미렌더 시 소속 테이블로 승격
    if (present.has(nodeKey)) return nodeKey;
    // 컬럼 노드가 모델에 없어도(접힌 스키마 = 테이블만 로드) REFERENCES 끝점은 항상 컬럼 키이므로
    // 키 문자열에서 소속 테이블 키를 직접 도출한다(_metaColParent 는 fqn 없으면 key 로 파싱).
    const gn = _metaGraph.nodes.get(nodeKey);
    const pk = _metaColParent(nodeKey, gn && gn.fqn);
    return (pk && present.has(pk)) ? pk : null;
  };
  const aggMap = new Map();   // "src::tgt" → 집계 엣지(테이블-레벨 승격분)
  _metaGraph.edges.forEach((e) => {
    // graph-navfilter(§54②): 관계선 토글 — 방출만 차단(모델 유지: _metaRelAdjacency 가 모델을 읽어
    //   배치 순서 불변 = 엣지 토글로 테이블이 점프하지 않음. 모델 삭제 금지 — 재토글 복원·접기 관례).
    if (_metaGraph.hiddenKinds.has("edges")) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_ROUTINE") return;
    // 비-REFERENCES(DESCRIBES/RELATED_TERM/ROUTINE_USES 등)는 기존대로 양끝 직접 렌더 시에만.
    if (e.type !== "REFERENCES") {
      if (present.has(e.source) && present.has(e.target)) {
        const st = (e.type === "ROUTINE_USES") ? _metaRoutineEdgeStyle() : _metaEdgeStyleFor(e.status);
        edges.push({ id: e.id, source: e.source, target: e.target, data: { label: e.type, status: e.status }, style: st });
      }
      return;
    }
    const rs = renderEndpoint(e.source), rt = renderEndpoint(e.target);
    if (!rs || !rt || rs === rt) return;   // 미렌더 끝점 or 동일 테이블 내부(intra-table) 제외
    const colLevel = (rs === e.source && rt === e.target);
    if (colLevel) {
      // 양끝 컬럼 렌더 — 정밀 컬럼-레벨 엣지(기존 동작 유지). crossds-rel: cross_ds 면 마젠타 점선.
      edges.push({ id: e.id, source: rs, target: rt, data: { label: e.type, status: e.status, colEdge: true, cross_ds: e.cross_ds || 0 }, style: _metaEdgeStyleFor(e.status, e.cross_ds) });
      return;
    }
    // 한쪽 이상이 테이블로 승격 — 집계 엣지에 병합(dedupe + 상태 승급 + pairs 누적).
    const ak = rs + "::" + rt;
    let agg = aggMap.get(ak);
    if (!agg) { agg = { id: "agg:" + ak, source: rs, target: rt, status: e.status || "", count: 0, pairs: [], crossDs: false }; aggMap.set(ak, agg); }
    agg.count += 1;
    agg.crossDs = agg.crossDs || !!e.cross_ds;   // crossds-rel: 집계 쌍 중 하나라도 교차DB 면 교차DB 로 표식
    if (agg.pairs.length < 8) agg.pairs.push({ s: e.source, t: e.target, status: e.status });
    if (e.status === "trusted" || (e.status === "candidate" && agg.status !== "trusted")) agg.status = e.status;   // 최강 상태 채택
  });
  aggMap.forEach((agg) => {
    // 집계 엣지는 여러 컬럼-쌍을 대표하므로 살짝 굵게(count>1) — style 미지원 키는 넣지 않음(G6 안전).
    const st = _metaEdgeStyleFor(agg.status, agg.crossDs);
    if (agg.count > 1) st.lineWidth = (st.lineWidth || 1.4) + 0.8;
    edges.push({ id: agg.id, source: agg.source, target: agg.target,
      data: { label: "REFERENCES", status: agg.status, aggregated: true, count: agg.count, pairs: agg.pairs, cross_ds: agg.crossDs ? 1 : 0 },
      style: st });
  });
  // graph-initview: 렌더된 요소 id 집합(노드+combo) — setElementState/focus 가 미렌더 요소를 건드리지 않게.
  _metaGraph.renderedIds = new Set(nodes.map((n) => n.id).concat(combos.map((c) => c.id)));
  return { combos, nodes, edges };
}

// graph-product-cat(§43): 제품 카테고리 개요 전용 빌드 — Product(좌열)·Datasource(우열) rect 노드 +
//   USES 엣지. combo 미사용(결정론 2-열 배치). 여러 제품이 공유하는 datasource 는 1개 노드로 dedup(백엔드가
//   이미 dedup)하고 각 제품→datasource 엣지를 그린다. 노드 클릭: Datasource → 그 데이터소스 그래프로 drill,
//   Product → 그 제품만 focus(단일 제품 개요).
function _metaG6BuildProducts() {
  _metaGraph.tableDeps = new Map();
  _metaGraph.firstElementId = null;
  const prods = [], dss = [];
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Product") prods.push(n);
    else if (n.label === "Datasource") dss.push(n);
  });
  prods.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  dss.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const nodes = [], edges = [];
  const TOP = 40, ROWH = 66, RH = 46;
  const PW = 240, PX = 40, DW = 230, DX = 440;   // 제품 좌열 / 데이터소스 우열
  prods.forEach((p, i) => {
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = p.key;
    const cy = TOP + i * ROWH + RH / 2;
    const cnt = (typeof p.datasource_count === "number") ? p.datasource_count : null;
    nodes.push({ id: p.key, type: _METtype, states: _metaNodeStates(p.key),
      data: { label: p.name || p.key, kind: "product" },
      style: { x: PX + PW / 2, y: cy, size: [PW, RH], radius: 10, zIndex: _METZ.NODE,
        fill: "#e7f4ec", stroke: _META_GRAPH_COLOR.Product, lineWidth: 1.6,
        labelText: "🗂 " + (p.name || p.key) + (cnt != null ? "  · " + cnt : ""),
        labelPlacement: "center", labelFill: "#1c5c39", labelFontSize: 12, labelFontWeight: 700,
        labelMaxWidth: PW - 18, cursor: "pointer" } });
  });
  dss.forEach((d, i) => {
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = d.key;
    const cy = TOP + i * ROWH + RH / 2;
    nodes.push({ id: d.key, type: _METtype, states: _metaNodeStates(d.key),
      data: { label: d.name || d.key, kind: "datasource", scope: d.scope_key || "" },
      style: { x: DX + DW / 2, y: cy, size: [DW, RH], radius: 10, zIndex: _METZ.NODE,
        fill: "#eef6f1", stroke: _META_GRAPH_COLOR.Datasource, lineWidth: 1.4,
        labelText: "🔗 " + (d.name || d.key),
        labelPlacement: "center", labelFill: "#20603f", labelFontSize: 11.5, labelFontWeight: 600,
        labelMaxWidth: DW - 18, cursor: "pointer" } });
  });
  const present = new Set(nodes.map((n) => n.id));
  _metaGraph.edges.forEach((e) => {
    if (!e || e.type !== "USES") return;
    if (!present.has(e.source) || !present.has(e.target)) return;
    edges.push({ id: e.id, source: e.source, target: e.target, data: { label: "USES" },
      style: { stroke: "#8fbfa3", lineWidth: 1.5, endArrow: true, zIndex: _METZ.EDGE } });   // 실선(lineDash 생략 — G6 크래시 방지)
  });
  _metaGraph.renderedIds = new Set(nodes.map((n) => n.id));
  return { combos: [], nodes, edges };
}

// graph-initview: 모델 key → 실제 렌더된 요소 id (접힌 스키마 카드는 "SC:"+key). 미렌더면 null.
function _metaRenderedIdFor(key) {
  const r = _metaGraph.renderedIds;
  if (!r || !key) return null;
  if (r.has(key)) return key;
  if (r.has("SC:" + key)) return "SC:" + key;
  return null;
}

// 모델 → 화면 반영(전체 재구성 setData + draw). fit=true 면 전체 맞춤.
//   ⚠ 의도적 설계(BLUEPRINT §2 대비 divergence): roots/search/neighbor 전 모드가 **결정론 grid(setData+draw)**.
//   blueprint 초안의 search/neighbor=render()+d3-force 는 채택 안 함 — force 는 ④(클러스터 뒤섞임)를 재유발하고
//   POC 가 검증한 무-shuffle 보장을 깬다. 교차 스키마 이웃도 자기 스키마 combo 의 grid 셀에 배치(force 아님).
//   이 주석은 후속 리뷰어가 render()+force 로 "되돌리는" 회귀를 막기 위함(review MINOR-2).
async function _metaG6Apply(fit) {
  const g = _metaGraph.graph;
  if (!g) return;
  // graph-ctxmenu(review): 재구성으로 노드가 이동하면 열린 메뉴 좌표가 스테일 — 재적용 시 메뉴 닫기.
  if (typeof _metaGraphCtxHide === "function") _metaGraphCtxHide();
  try {
    g.setData(_metaG6Build());
    _metaGraph._busyKeys.clear();     // graph-perf-bg fix: rebuild 는 요소를 재생성 → 명령형 busy 시각 소멸, 소유권 맵도 정리(stale busy 재적용·유령 소유 방지).
    // graph-expand-perf fix(프리즈): setData 가 data.states(_metaG6Build 의 states:)로 모든 노드 상태를 이미 bake 한다.
    //   예전엔 _stateCache 를 clear 만 해서, 직후 _metaGraphRefreshStates(syncMarkers·2.5s 폴)가 cold 로 **전 노드
    //   setElementState** 를 돌렸다 — G6 v5 setElementState 는 건당 ~50ms 라 수백 노드면 수 초 메인스레드 프리즈
    //   (실측: 200노드 재적용 = 10초). 대신 캐시를 방금 bake 된 signature 로 채워 rebuild 직후 refresh 를 no-op 로
    //   만든다(진짜 변한 마커만 이후 소량 setElementState). _busyKeys clear 후라 sig=_metaNodeStates 와 일치.
    _metaGraph._stateCache.clear();
    _metaGraph.nodes.forEach((n) => { _metaGraph._stateCache.set(n.key, _metaCacheSig(n.key)); });   // node-role-viz: 역할 suffix 포함 — rebuild 가 역할 칩 색을 이미 bake 했으므로 직후 refresh 는 no-op
    await g.draw();
    _metaGraphZAssert();   // graph-zorder h2: setData update 의 combo-hierarchy z 평탄화(comboZ+1) 를 canonical 로 재-assert
    _metaGraphMinimapAnchor();   // graph-minimap-fix: 플러그인 컨테이너 inline left/top → CSS 앵커 정규화(멱등)
    if (fit) { await _metaGraphFitClamped(true); }
  } catch (err) { _metaGraphStatus("그래프 렌더 오류: " + ((err && err.message) || err)); }
}

// graph-minimap-fix(REQ ②): G6 v5 minimap 플러그인은 컨테이너 생성 시점의 캔버스 크기로 inline
//   left/top(px)을 **1회 계산해 고정**한다 — 상세 패널 드래그 리사이즈/접기/창 리사이즈로 캔버스가
//   변해도 미니맵이 옛 좌표에 남는 원인(styles.css 의 right/bottom 앵커는 inline left/top 에 진다).
//   inline 좌표를 auto 로 지워 CSS 앵커(right:10px; bottom:10px)로 전환하면 이후 모든 리사이즈를
//   레이아웃이 자동 추종한다. 멱등(재호출 무해) — 플러그인 캔버스가 lazy 생성되므로 rebuild 마다 보정.
//   §18.8 패널(MAJOR): 플러그인 컨테이너는 AFTER_DRAW 후 **128ms trailing debounce** 로 lazy 생성되므로
//   post-draw 즉시 호출은 요소를 못 찾는다 — 미발견 시 200ms 간격 재시도(기본 4회)로 생성 창을 커버.
function _metaGraphMinimapAnchor(retries) {
  let el = null;
  try { el = document.querySelector(".admin-meta-graph-canvas .g6-minimap"); } catch (_) { return; }
  if (el) {
    if (el.style.left !== "auto") { el.style.left = "auto"; el.style.top = "auto"; }
    return;
  }
  const r = (retries == null) ? 4 : retries;
  if (r > 0) setTimeout(() => _metaGraphMinimapAnchor(r - 1), 200);
}

// graph-initview(A1): 전체-fit 하되 판독 하한 밑으로는 줌아웃하지 않는다 — 콘텐츠가 크면 "판독 가능한
// 첫 페이지"를 보여주고 나머지는 팬/줌/미니맵으로 탐색. focusFirst 는 초기 로드/검색처럼 "시작점"이
// 자연스러운 경우만 true — 리사이즈/패널토글 refit 은 사용자의 현재 위치를 버리지 않게 false.
async function _metaGraphFitClamped(focusFirst) {
  const g = _metaGraph.graph;
  if (!g) return;
  try {
    await g.fitView({ padding: 30 }, false);
    const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
    if (isFinite(z) && z < _META_MIN_READ_ZOOM) {
      await g.zoomTo(_META_MIN_READ_ZOOM, false);
      if (focusFirst && _metaGraph.firstElementId) { try { await g.focusElement(_metaGraph.firstElementId, false); } catch (_) {} }
    } else if (isFinite(z) && z > 1) {
      await g.zoomTo(1, false);   // 소규모 콘텐츠(스키마 카드 몇 장)를 fit 이 과확대하지 않게 100% 상한
    }
  } catch (_) {}
}

// graph-dblclick-cam2: 더블클릭 앵커 focus 를 부드러운 팬으로. 그래프 config `animation:false`(레이아웃 셔플 방지용)가
//   **per-call 카메라 애니(focusElement/zoomTo 의 animation 인자)까지 무효화**한다(실증: false=2ms 즉시 vs true=412ms).
//   전역 animation 을 켜면 setData 레이아웃 셔플이 재발하므로, G6 애니 시스템 대신 **manual rAF tween** 으로 앵커를 뷰포트
//   중앙까지 translateBy(누적 이징) — setData 미사용이라 셔플·전역상태 무관. seq 로 연타 중단, 미렌더/ API 실패는 즉시 focus 폴백.
// graph-dblclick-latency: 앵커-중심 팬을 **적응형 follow tween** 으로. 고정-duration(Dx/Dy 1회 캡처) 대신 매 프레임
//   앵커의 **현재** 뷰포트 위치를 재조회해 뷰포트 중앙까지 잔여 delta 의 일정 비율(K)만큼 translateBy(ease-out).
//   이 구조라 (a) fetch·rebuild 완료를 기다리지 않고 **더블클릭 즉시 fire-and-forget 으로 시작**해도(앵커는 이미 렌더됨)
//   반응 텀이 사라지고, (b) 재빌드로 앵커가 이동/재생성돼도 최종 위치로 매끄럽게 수렴한다. seq 로 후속 op 시 폐기,
//   재빌드 중 element 일시 미해소는 해당 프레임만 skip(프레임카운트 조기포기 없음 — 저사양 rAF 탈동조 대비). 종료는 수렴/seq/MAXMS.
//   카메라 transform 만(노드 재렌더 없음)이라 프리즈 무관. API 부재 번들은 focusElement 즉시 폴백.
async function _metaGraphAnimateFocus(key, seq) {
  const g = _metaGraph.graph;
  if (!g || !key) return;
  // graph-rel-layout(§18.8 패널 MINOR): tween 생존 마커 — expand 가 rebuild 후 "tween 이 이미 죽었는지"를
  //   판정해 시야 보정 폴백을 결정한다(관계 재배치로 앵커가 원거리 이동 가능해져 필요해짐). seq 소유 기준.
  _metaGraph._focusLive = seq == null ? -1 : seq;
  try {
    await _metaGraphAnimateFocusRun(g, key, seq);
  } finally {
    if (_metaGraph._focusLive === (seq == null ? -1 : seq)) _metaGraph._focusLive = null;
  }
}
async function _metaGraphAnimateFocusRun(g, key, seq) {
  // API 부재 번들 폴백(getElementRenderBounds/getViewportByCanvas/translateBy 없으면 즉시 focus — 구 동작 보존).
  if (typeof g.getElementRenderBounds !== "function" || typeof g.getViewportByCanvas !== "function" || typeof g.translateBy !== "function") {
    try { const fel = _metaRenderedIdFor(key); if (fel && typeof g.focusElement === "function") await g.focusElement(fel, false); } catch (_) {}
    return;
  }
  try {   // 판독 하한 줌 clamp(즉시 — 팬보다 먼저)
    const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
    if (isFinite(z) && z < _META_MIN_READ_ZOOM) await g.zoomTo(_META_MIN_READ_ZOOM, false);
  } catch (_) {}
  const now = () => (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  const raf = () => new Promise((r) => { (typeof window !== "undefined" && window.requestAnimationFrame) ? window.requestAnimationFrame(() => r()) : setTimeout(r, 16); });
  const t0 = now(), MAXMS = 1200;   // **유일** 시간 상한 — av 미해소(재빌드 프리즈로 rAF 탈동조)여도 여기서 확정 종료.
  const K = 0.24;                    // 프레임당 잔여 delta 비율(ease-out follow — 빠른 시작·부드러운 안착)
  while (true) {
    if (seq != null && seq !== _metaGraph._opSeq) return;   // 후속 op 로 폐기
    if (now() - t0 > MAXMS) return;                          // 시간 상한(유일 안전망 — 프레임 카운트 기반 조기 포기 없음)
    let W, H;   // 매 프레임 재조회 — 팬 중 컨테이너/창 리사이즈 대응(중앙 목표 스테일 방지).
    try { const s = g.getSize(); W = s[0]; H = s[1]; } catch (_) { W = H = NaN; }
    let av = null;   // 앵커 현재 뷰포트 위치 재조회 — 재빌드로 이동·재생성돼도 최종 위치로 수렴.
    try {
      const fel = _metaRenderedIdFor(key);
      if (fel) {
        const b = g.getElementRenderBounds(fel);
        av = g.getViewportByCanvas([(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2]);
      }
    } catch (_) { av = null; }
    if (isFinite(W) && isFinite(H) && av && isFinite(av[0]) && isFinite(av[1])) {
      const rx = W / 2 - av[0], ry = H / 2 - av[1];
      if (Math.abs(rx) < 1.2 && Math.abs(ry) < 1.2) return;   // 수렴 — 종료
      try { g.translateBy([rx * K, ry * K], false); } catch (_) { return; }
    }
    // av 미해소(재빌드 중 일시)면 이 프레임 skip — MAXMS 까지 재시도(조기 포기 없음 → 저사양 프레임드롭에도 팬 미실패).
    await raf();
  }
}

// 라벨별 색 — RFC 팔레트(Table=teal, Column=slate, GlossaryTerm=amber, Schema=indigo, DS/Product=green).
const _META_GRAPH_COLOR = {
  Table: "#0f7d8c", Column: "#5c6773", GlossaryTerm: "#9c6515",
  Schema: "#3f4b8c", Datasource: "#2e7d52", Product: "#2e7d52",
  Routine: "#7b5cd6",   // graph-funcproc(ADR-016): 함수·프로시저 칩(보라 — 테이블 teal 과 구분)
};
// graphux5-progress: 라벨 한글 표기(AI 능동 분석 진행 상세 — 어떤 '항목'인지 사람이 읽게).
const _META_LABEL_KO = {
  Table: "테이블", Column: "컬럼", GlossaryTerm: "용어", Schema: "스키마",
  Datasource: "데이터소스", Product: "제품", Routine: "함수·프로시저",
};
// graph-funcproc: 함수(ƒ)/프로시저(⚙) 표기 접두 — 칩 라벨·상세 헤더 공용.
function _metaRoutineIcon(rt) { return rt === "function" ? "ƒ" : "⚙"; }
function _metaRoutineKo(rt) { return rt === "function" ? "함수" : "프로시저"; }
// graph-navfilter(§54⑤): routine params 문자열("IN a int, OUT b varchar" — routines.py 가 ", " join,
//   piece 는 DATA_TYPE 이라 내부 콤마 없음) → 파라미터 목록. 그래프 수직 배치·상세 패널 공용.
function _metaRoutineParamList(n) {
  const s = (n && n.params) || "";
  return s ? s.split(", ").map((x) => x.trim()).filter(Boolean) : [];
}

function _metaGraphStatus(msg) {
  const el = document.getElementById("metadataGraphStatus");
  if (el) el.textContent = msg || "";
}

function _metaShowGraph() {
  // feature-0016 §45: 그래프 뷰는 자체 pane(data-admin-pane="graph") 이라 메타데이터 pane DOM 을 숨길 필요가 없다
  //   (pane display 가 가시성을 관장). 여기선 그래프 init + 진입 로드만 수행한다.
  _metaInitGraph();
  _metaRoleLegendTips();   // role-cluster-prefix: 역할 범례 hover 툴팁(desc) 주입(정적 <li data-role> → _META_ROLE 단일 소스).
  _metaGraphBindLegendTabs();   // graphux7(#3): 범례 3-탭 전환 바인딩(멱등).
  // feature-0016: 그래프 뷰 진입 시 현재 선택 datasource 의 그래프(roots)를 즉시 로드 — 각 데이터소스별 그래프 출현.
  _metaGraphLoadRoots();
  const s = document.getElementById("metadataGraphSearch");
  if (s && s.focus) try { s.focus(); } catch (_) {}
}

// 모델 초기화(그래프 교체/리셋/scope 전환 시). 노드·엣지·펼침·마커 clear.
function _metaGraphResetModel() {
  _metaGraph.nodes.clear();
  _metaGraph.edges.clear();
  _metaGraph.expanded.clear();
  _metaGraph.analyzed.clear();
  _metaGraph.running.clear();
  _metaGraph.roles.clear();   // node-role-viz: 역할 표식도 모델과 함께 초기화(sync 가 재적재)
  _metaGraph.selected = null;
  _metaGraph.colsByTable.clear();   // graph-perf-bg: 펼침 인덱스 초기화(모델 교체와 정합).
  _metaGraph._stateCache.clear();   // graph-perf-bg: state 캐시 무효화(다음 refresh 가 전량 재적용).
  _metaGraph._busyKeys.clear();     // graph-perf-bg fix: 모델 교체 → 명령형 busy 정리.
  // graph-perf-bg fix(BLOCKING): 모델 교체(search/roots/scope/reset)는 in-flight 펼침·확장을 무효화한다. _opSeq 를 여기서
  //   올리지 않으면 heavy op 만 토큰을 올려, reset 후 뒤늦게 resolve 된 stale expand 가 (a) 새 모델을 덮어써 사용자가
  //   방금 요청한 검색/스코프 화면을 되돌리고(stale 렌더), (b) reset 으로 비워진 모델에 컬럼을 ingest 해 colsByTable 를
  //   포이즌(존재하지 않는 테이블의 hasCols=true → 재펼침 영구 차단)한다. 토큰을 올리면 그 op 는 다음 seq 체크에서 폐기된다.
  _metaGraph._opSeq++;
  // graph-initview: 검색 필터 뷰 상태 초기화(schemaTotals 는 scope 캐시라 보존 — loadRoots 가 재구축).
  _metaGraph.searchMatch = null;
  _metaGraph.searchMatchTables = null;
  _metaGraph.searchMatchNodes = null;   // feature-0016 §45: 검색 매칭 glow 집합 초기화.
  _metaGraph.searchCapped = false;
  _metaGraph.searchAdded.clear();       // graph-navfilter(§54③): 검색 pristine 추적도 스코프와 함께 리셋.
  _metaGraph.routineExpanded.clear();   // graph-navfilter(§54⑤): 루틴 파라미터 펼침 리셋(컬럼 펼침과 동형).
  // (주의) hiddenKinds 는 여기서 clear 하지 않는다 — scope-독립 표시 preference(§54②). 검색·중심보기가
  //   resetModel 을 경유하므로 clear 하면 검색 한 번에 필터가 풀리는 회귀가 된다.
  // graph-initview: 스키마-우선 상태 초기화.
  _metaGraph.schemaExpanded.clear();
  _metaGraph.schemaLoaded.clear();
  _metaGraph.schemaLoading.clear();
  _metaGraph.schemaTruncated.clear();
  _metaGraph.firstElementId = null;
  if (_metaGraph.introspected) _metaGraph.introspected.clear();
  // graph-freeplace: 자유 배치는 스코프 전환·초기화 시 리셋(다른 데이터소스는 다른 클러스터 — 위치 무의미).
  //   펼침/접기(rebuild)는 resetModel 을 거치지 않으므로 그 경로에선 위치가 유지된다(핵심 요구).
  _metaGraph.clusterOffset.clear();
  _metaGraph.nodePos.clear();
  _metaGraph.groupOffset.clear();      // group-interact(§50): sim-group 자유 배치·접기도 fresh load 시 리셋(다른 스코프 = 다른 그룹).
  _metaGraph.groupCollapsed.clear();
  _metaGraph.groupMembers.clear();
  _metaGraph.groupOf.clear();
  _metaGraph.clusterOrder = [];        // feature-0016 §49: 순서 안정화도 fresh load(스코프 전환·초기화) 시 리셋 → 순수 seriation.
  _metaGraph.tableOrder.clear();
  _metaGraph.groupOrder.clear();       // feature-0016 §49(R1): simgroups 순서 안정화도 fresh load 시 리셋.
  _metaGraph.groupTableOrder.clear();
  // graph-category(§55 A): 카테고리 순서·접기·인덱스 리셋(다른 스코프 = 다른 카테고리).
  //   schemaProducts 는 schemaTotals 동형의 scope 캐시라 보존 — loadRoots 가 재구축.
  _metaGraph.catOrder = [];
  _metaGraph.catCollapsed.clear();
  _metaGraph.catMembers.clear();
  _metaGraph.catLabelOf.clear();
  _metaGraph._comboDragStart = null;
}

// graph-product-cat(§43): 제품 카테고리 개요 로드 — Product→Datasource 개요(MySQL SSOT 합성).
//   scope='product:<id>' 면 단일 제품 focus, 그 외(common/__products__)는 전체 제품. 데이터소스 노드 클릭으로 drill.
async function _metaGraphLoadProducts(scope) {
  if (!_metaGraph.graph) _metaInitGraph();
  if (!_metaGraph.graph) return;
  _metaGraphHistoryReset();   // graphux7(#1): datasource/제품 컨텍스트 전환 — 방문 이력 초기화.
  _metaGraph._searchBase = null;   // §54③: fresh 컨텍스트 — 검색 base 폐기
  // §54② 패널 MINOR: kind 필터는 스키마 그래프 전용 — 제품 개요(BuildProducts 는 hiddenKinds 미참조)
  //   에서 버튼이 동작하는 척(허위 status)하지 않게 컨트롤 자체를 숨긴다.
  const _kc0 = document.querySelector(".admin-meta-graph-kindctl");
  if (_kc0) _kc0.style.display = "none";
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";
  _metaGraph.lastQuery = "";
  _metaGraph.mode = "products";                 // resetModel 은 mode 를 건드리지 않음(loadRoots 와 동형 순서)
  _metaGraph.loadedScope = scope || "common";   // feature-0016 §45 D1: 제품 개요도 마지막 렌더 스코프 기록.
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);
  _metaGraphResetModel();
  _metaGraph.mode = "products";                 // resetModel 이후 재확정(방어)
  const seq = _metaGraph._opSeq;
  _metaGraphFillJump([]);
  const s = String(scope || "");
  const pid = s.startsWith("product:") ? s.slice("product:".length) : "";
  const url = pid
    ? `/api/admin/metadata/graph?product=${encodeURIComponent(pid)}`
    : `/api/admin/metadata/graph?mode=products`;
  _metaGraphStatus("제품 카테고리 로딩…");
  let data;
  try { data = await apiFetch(url); }
  catch (err) { if (seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "제품 그래프 로드 실패"); return; }
  if (seq !== _metaGraph._opSeq) return;
  _metaGraphIngest(data.nodes || [], data.edges || []);
  await _metaG6Apply(true);
  if (seq !== _metaGraph._opSeq) return;
  const np = (data.nodes || []).filter((n) => n && n.label === "Product").length;
  const nd = (data.nodes || []).filter((n) => n && n.label === "Datasource").length;
  _metaGraphRenderDetailEmpty();
  _metaGraphStatus(np
    ? `제품 카테고리 ${np}개 · 데이터소스 ${nd}개 — 데이터소스 노드를 클릭하면 그 데이터소스의 스키마 그래프로 이동합니다.`
    : "등록된 제품이 없습니다. (관리 콘솔 > 제품 에서 등록 후 데이터소스를 바인딩하세요.)");
}

// 현재 선택 datasource(scope)의 진입 그래프(Schema→Table)를 로드. 'common'/미선택/제품 scope 는 제품 카테고리 개요.
async function _metaGraphLoadRoots() {
  if (!_metaGraph.graph) _metaInitGraph();
  if (!_metaGraph.graph) return;
  _metaGraphHistoryReset();   // graphux7(#1): datasource 컨텍스트 전환 — 방문 이력 초기화.
  const scope = adminState.metadata.scopeKey || "common";
  _metaGraph.loadedScope = scope;   // feature-0016 §45 D1: 마지막 렌더 스코프 기록(탭 재진입 시 diverge 재로드 판정).
  // graph-product-cat(§43): 데이터소스 미선택(공용) 또는 제품 scope 는 제품 카테고리 개요를 랜딩으로 보여준다.
  if (!scope || scope === "common" || scope === "__products__" || String(scope).startsWith("product:")) {
    return _metaGraphLoadProducts(scope);
  }
  _metaGraph._searchBase = null;   // §54③: fresh 컨텍스트 — 검색 base 폐기
  const _kc1 = document.querySelector(".admin-meta-graph-kindctl");
  if (_kc1) _kc1.style.display = "";   // §54②: 스키마 그래프 — kind 필터 컨트롤 표시
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";
  _metaGraph.lastQuery = "";   // 검색 컨텍스트 종료 — 상세 유사도 배지 게이트가 참조
  _metaGraph.mode = "roots";
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);   // 중심 보기 종료(전체 복귀)
  _metaGraphResetModel();
  const seq = _metaGraph._opSeq;   // graph-perf-bg fix: resetModel 직후 세대 캡처 — await 도중 다른 reset(loadRoots/search/scope 전환) 이 _opSeq 를 올리면 이 continuation 을 폐기.
  _metaGraphStatus("데이터소스 그래프 로딩…");
  let data;
  try {
    // graph-initview: 진입은 스키마 카드 경량 뷰(mode=schemas) — 테이블은 스키마 클릭 시 per-schema lazy.
    // (구 백엔드가 mode 를 모르면 scope_roots 전체 응답이 와도 카드 게이팅으로 동일 UX — 하위호환.)
    data = await apiFetch(`/api/admin/metadata/graph?scope=${encodeURIComponent(scope)}&mode=schemas`);
  } catch (err) {
    if (seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "그래프 로드 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) return;   // graph-perf-bg fix: await 사이 다른 reset 이 모델을 교체 → 이 응답은 stale. additive ingest 하면 혼합-스코프 그래프가 남으므로 폐기.
  _metaGraphIngest(data.nodes || [], data.edges || []);
  const schemaKeys = [];
  _metaGraph.nodes.forEach((sn) => { if (sn.label === "Schema") schemaKeys.push(sn.key); });
  schemaKeys.sort(_metaNatSort);
  // graph-initview: scope 별 스키마→전체 테이블 수 캐시(재구축). 검색이 모델을 리셋해도 카드 badge 의
  //   '전체 테이블 개수' 소스로 쓰이므로 여기서만 갱신하고 resetModel 에서는 보존한다.
  _metaGraph.schemaTotals = new Map();
  _metaGraph.nodes.forEach((sn) => { if (sn.label === "Schema" && typeof sn.table_count === "number") _metaGraph.schemaTotals.set(sn.key, sn.table_count); });
  // graph-category(§55 A): 스키마(DB)명 → 제품 매핑 재구축(scope 캐시 — schemaTotals 동형).
  //   key 는 lowercase(WebProductDatabases.SchemaName 과 그래프 스키마명의 대소문자 편차 방어).
  _metaGraph.schemaProducts = new Map();
  if (data.schema_products && typeof data.schema_products === "object") {
    Object.keys(data.schema_products).forEach((sch) => {
      const lst = data.schema_products[sch];
      if (Array.isArray(lst) && lst.length) _metaGraph.schemaProducts.set(String(sch).toLowerCase(), lst);
    });
  }
  _metaGraphFillJump(schemaKeys);
  let truncNote = data.truncated ? " · 스키마 표시 상한 도달(나머지는 검색)" : "";
  // 스키마 1개짜리 데이터소스는 카드 한 장이 무의미 — 즉시 펼쳐 기존 즉시성 유지(silent, 부모 seq 상속).
  if (schemaKeys.length === 1) {
    await _metaGraphExpandSchema(schemaKeys[0], { silent: true, seq });
    if (seq !== _metaGraph._opSeq) return;
    if (_metaGraph.schemaTruncated.has(schemaKeys[0])) truncNote += " · 테이블 표시 상한 도달(나머지는 검색)";
  }
  await _metaG6Apply(true);
  if (seq !== _metaGraph._opSeq) return;
  _metaGraphSyncAnalysisMarkers(scope);   // 이미 분석된/진행중 노드 마커를 클릭 없이 렌더 시점에 적용
  const n = (data.nodes || []).length;
  // graph-product-cat(§43): 이 데이터소스를 쓰는 제품(카테고리) 배너 — 어느 제품 소속인지 즉시 식별.
  const prodNames = Array.isArray(data.products) ? data.products.map((p) => p && p.name).filter(Boolean) : [];
  const prodPrefix = prodNames.length ? `제품: ${prodNames.join(", ")} · ` : "";
  _metaGraphStatus(n
    ? (schemaKeys.length > 1
        ? `${prodPrefix}${scope}: 스키마 ${schemaKeys.length}개 — 카드를 클릭하면 그 스키마의 테이블을 펼칩니다. 검색으로 바로 탐색도 가능.${truncNote}`
        : `${prodPrefix}${scope}: ${_metaGraph.nodes.size}개 노드 — 노드 클릭으로 확장, 또는 검색.${truncNote}`)
    : `${prodPrefix}${scope}: 그래프 데이터 없음(설명/인사이트 미적재).`);
}

// graph-initview(E3): 툴바 스키마 점프 select 채움 — 선택 시 해당 클러스터/카드로 focus.
function _metaGraphFillJump(schemaKeys) {
  const sel = document.getElementById("metadataGraphJump");
  if (!sel) return;
  const escA = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  const opts = ['<option value="">스키마 이동…</option>'];
  (schemaKeys || []).forEach((k) => { opts.push(`<option value="${escA(k)}">${escA(_metaComboName(k))}</option>`); });
  sel.innerHTML = opts.join("");
  sel.style.display = (schemaKeys && schemaKeys.length > 1) ? "" : "none";
}

// 노드 key(`scope:fqn`)에서 카테고리(스키마) compound parent id 도출. schema 없으면 null.
function _metaCatParent(key, fqn) {
  if (!key) return null;
  const idx = key.indexOf(":");
  if (idx < 0) return null;
  const scope = key.slice(0, idx);
  const f = fqn || key.slice(idx + 1);
  if (!f || f.indexOf(".") < 0) return null;   // 스키마 segment 없음(스키마 노드 자체 등)
  return scope + ":" + f.split(".")[0];
}

// graph-drag: 이벤트의 눌린 버튼 비트마스크(buttons)를 견고하게 추출한다.
//   G6/G 의 drag lifecycle 이벤트(node:dragstart, 전역 dragstart)는 pointermove 에서 합성돼
//   `button` 이 -1 일 수 있으므로, 현재 눌림 상태를 나타내는 `buttons`(1=좌,2=우,4=중간)를 우선한다.
//   nativeEvent fallback + button→bitmask 최종 폴백으로 번들 차이에도 안전.
function _metaEventButtons(e) {
  if (!e) return 1;
  if (typeof e.buttons === "number" && e.buttons > 0) return e.buttons;
  const ne = e.nativeEvent || e.originalEvent;
  if (ne && typeof ne.buttons === "number" && ne.buttons > 0) return ne.buttons;
  const b = (typeof e.button === "number") ? e.button
    : (ne && typeof ne.button === "number") ? ne.button : 0;
  return b === 1 ? 4 : b === 2 ? 2 : 1;   // button: 0=좌→1, 1=중간→4, 2=우→2
}
// graph-drag: 중간(휠) 버튼으로 시작한 드래그인지.
function _metaIsMiddleDrag(e) { return (_metaEventButtons(e) & 4) === 4; }
// graph-drag(REQ ①): drag-canvas 활성 판정 — 중간 버튼은 노드 위에서든 어디서든 카메라 팬으로 허용,
//   그 외(좌클릭)는 G6 기본대로 빈 캔버스에서만 팬(노드는 drag-element 가 처리).
function _metaCanvasDragEnable(e) {
  if (_metaIsMiddleDrag(e)) return true;
  return !(e && "targetType" in e) || (e && e.targetType === "canvas");
}
// graph-drag(REQ ①): drag-element 활성 판정 — 노드 이동은 좌클릭만. 중간 버튼은 카메라 팬에
//   양보해 "객체 상호작용(노드 이동)"이 아니라 카메라 드래그가 되게 한다.
function _metaElementDragEnable(e) {
  const id = e && e.target && e.target.id;
  // group-interact(§50): 그룹 접기 컨트롤(GX)만 이동 불가(클릭 전용). GB(배경)/GH(헤더)는 그룹 리지드 드래그 허용
  //   (예전 graph-simgroups 의 GB/GH 이동 차단을 해제 — 카테고리 그룹 drag&drop 위치 이동 복원).
  if (id && String(id).startsWith("GX:")) return false;
  if (id && String(id).startsWith("CATX:")) return false;   // graph-category(§55 A): 카테고리 접기 ctl = 클릭 전용
  // graph-category(§55 A, 패널 MAJOR fix): **접힌** 카테고리 밴드는 드래그 불가 — 밴드 위치가 packing
  //   (bandY) 파생이라 rebuild 로 스냅백하는데, 숨겨진 멤버 클러스터에는 clusterOffset 델타가 조용히
  //   누적돼 펼쳤을 때 멤버만 이동해 있는 모순이 생긴다(클릭 전용 = 상세/펼침 유도).
  if (id && (String(id).startsWith("CATH:") || String(id).startsWith("CAT:"))) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    if (_metaGraph.catCollapsed.has(ck)) return false;
  }
  return !_metaIsMiddleDrag(e);
}

// graph-drag(REQ ②): 테이블 노드 드래그 시 종속 UI(접기 "X:" ctl + 컬럼 노드) 동반 이동.
//   dragstart 에서 각 종속의 테이블 대비 오프셋(월드좌표)을 고정 기록하고, drag/dragend 마다
//   종속을 "테이블 현재위치 + 오프셋" 으로 절대 이동(translateElementTo)한다.
//   절대-오프셋 방식은 이벤트 실행 순서(내 핸들러 vs drag-element)에 무관하다: dragend 시점엔
//   drag-element 가 이미 테이블을 최종 위치로 옮겨 놓았으므로 재정합으로 1-frame lag 이 제거된다.
// graph-freeplace: 클러스터 offset 누적(combo 드래그 · 접힌 카드 드래그 공용). curId 의 현재 위치와
//   기록된 시작 위치의 델타를 clusterOffset[comboId] 에 누적한다(반복 드래그 정합, 미동 무시).
function _metaClusterOffsetAccumulate(comboId, startX, startY, curId) {
  const g = _metaGraph.graph;
  if (!g || !comboId) return;
  let p; try { p = g.getElementPosition(curId); } catch (_) { return; }
  if (!p || !isFinite(p[0]) || !isFinite(p[1])) return;
  const dx = p[0] - startX, dy = p[1] - startY;
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
  const prev = _metaGraph.clusterOffset.get(comboId) || { dx: 0, dy: 0 };
  _metaGraph.clusterOffset.set(comboId, { dx: prev.dx + dx, dy: prev.dy + dy });
  // graph-freeplace(리뷰 MAJOR fix): 클러스터를 통째로 옮기면, 그 클러스터에 속한 **개별 배치된 노드
  //   (nodePos, 절대좌표)** 도 같은 델타로 함께 옮긴다. 안 그러면 nodePos 가 절대값이라 clusterOffset 를
  //   덮어써(build 최종 tx=fp[0]) 그 노드만 원위치에 남아 클러스터에서 분리된다(table-then-cluster 순서).
  _metaGraph.nodePos.forEach((pos, nid) => {
    const n = _metaGraph.nodes.get(nid);
    if (n && _metaSchemaComboOf(n) === comboId) { pos[0] += dx; pos[1] += dy; }
  });
}

function _metaNodeDragStart(e) {
  _metaGraph._drag = null;
  _metaGraph._comboDragStart = null;
  if (_metaIsMiddleDrag(e)) return;             // 중간 버튼은 카메라 팬 — 노드 이동 아님
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  if (!g || !id) return;
  // graph-freeplace: 접힌 스키마 카드("SC:") 드래그 = 클러스터 위치 이동(combo 드래그와 동일 clusterOffset).
  //   L.x0/L.y0 는 카드·펼친 combo 공용 기준이라, 카드에서 옮겨도 펼쳤을 때 같은 offset 이 유지된다.
  if (String(id).startsWith("SC:")) {
    try { const p = g.getElementPosition(id); if (p) _metaGraph._comboDragStart = { comboId: id.slice(3), curId: id, x: p[0], y: p[1] }; } catch (_) {}
    _metaDragZBoost([id]);   // graph-zorder(§52): 내장 frontElement(영구 max+1) 대신 결정론 부스트 — dragend 복원
    return;
  }
  // graph-category(§55 A): 제품 카테고리 밴드(CAT: 배경 여백 / CATH: 헤더 칩) 드래그 = 카테고리 통째
  //   리지드 이동 — 멤버 클러스터(펼친 combo 는 자식 전체, 접힌 카드는 SC:) + 밴드 장식을 고정 오프셋으로
  //   묶는다(그룹 리지드 기전 재사용). dragend 에 멤버별 clusterOffset 일괄 누적(신규 offset 계층 불요).
  if (String(id).startsWith("CATH:") || String(id).startsWith("CAT:")) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    let ap; try { ap = g.getElementPosition(id); } catch (_) { return; }
    if (!ap) return;
    const rendered = _metaGraph.renderedIds;
    const clusters = _metaGraph.catMembers.get(ck) || [];
    const ids = ["CAT:" + ck, "CATH:" + ck, "CATX:" + ck];
    clusters.forEach((cid) => {
      ids.push(cid, "SC:" + cid);   // 펼친 combo / 접힌 카드 — rendered 필터가 실재만 남긴다
      _metaComboMemberIds(cid).forEach((mid) => ids.push(mid));
    });
    const offs = [];
    const seenOff = new Set();
    ids.forEach((eid) => {
      if (eid === id || seenOff.has(eid)) return;
      seenOff.add(eid);
      if (rendered && !rendered.has(eid)) return;
      let dp; try { dp = g.getElementPosition(eid); } catch (_) { return; }
      if (dp) offs.push({ id: eid, ox: dp[0] - ap[0], oy: dp[1] - ap[1] });
    });
    _metaGraph._drag = { id, offs, cat: ck, catClusters: clusters.slice(), startX: ap[0], startY: ap[1] };
    _metaDragZBoost([id].concat(offs.map((o) => o.id)));
    return;
  }
  // group-interact(§50): sim-group(GB 배경/GH 헤더) 드래그 = 카테고리 그룹 통째 리지드 이동.
  //   grabbed 요소를 anchor 로, 그룹 박스·헤더·컨트롤 + 멤버 테이블 + 그 종속(컬럼·"X:")을 고정 오프셋으로
  //   묶어 _drag.offs 에 담는다(테이블 종속 드래그와 동일 기전 재사용). dragend 에 groupOffset 누적.
  if (String(id).startsWith("GB:") || String(id).startsWith("GH:")) {
    const gk = String(id).slice(3);
    let ap; try { ap = g.getElementPosition(id); } catch (_) { return; }
    if (!ap) return;
    const rendered = _metaGraph.renderedIds;
    const ids = ["GB:" + gk, "GH:" + gk, "GX:" + gk];
    const members = _metaGraph.groupMembers.get(gk);
    if (members) members.forEach((tk) => {
      ids.push(tk);
      const deps = _metaGraph.tableDeps.get(tk);
      if (deps) deps.forEach((d) => ids.push(d));
    });
    const offs = [];
    ids.forEach((eid) => {
      if (eid === id) return;                        // grabbed 자신은 anchor(offs 제외)
      if (rendered && !rendered.has(eid)) return;
      let dp; try { dp = g.getElementPosition(eid); } catch (_) { return; }
      if (dp) offs.push({ id: eid, ox: dp[0] - ap[0], oy: dp[1] - ap[1] });
    });
    _metaGraph._drag = { id, offs, group: gk, startX: ap[0], startY: ap[1] };
    // graph-zorder(§52): 그룹 묶음(박스·헤더·컨트롤·멤버·종속) 전체를 함께 부스트 — grabbed 만 오르며
    //   계층이 찢어지던 내장 frontElement 를 덮는다(호출이 늦어 우선). dragend 에 canonical 복원.
    _metaDragZBoost([id].concat(offs.map((o) => o.id)));
    return;
  }
  const deps = _metaGraph.tableDeps.get(id);    // 테이블 key 만 등록됨(ctl/컬럼/용어/카드는 단독 이동)
  if (!deps || !deps.length) { _metaDragZBoost([id]); return; }   // graph-zorder(§52): 종속 없는 단독 노드도 부스트+복원 대칭
  let tp;
  try { tp = g.getElementPosition(id); } catch (_) { return; }
  if (!tp) return;
  const rendered = _metaGraph.renderedIds;       // 렌더된 종속 노드만(접힘 등 미렌더 제외)
  const offs = [];
  deps.forEach((d) => {
    if (rendered && !rendered.has(d)) return;
    let dp;
    try { dp = g.getElementPosition(d); } catch (_) { return; }
    if (dp) offs.push({ id: d, ox: dp[0] - tp[0], oy: dp[1] - tp[1] });
  });
  if (!offs.length) { _metaDragZBoost([id]); return; }
  _metaGraph._drag = { id, offs };
  // graph-zorder(§52): 테이블+종속(컬럼·"X:" ctl)을 함께 부스트 — 드래그 중 칩만 최상층으로 떠서
  //   자기 컬럼과 계층이 찢어지던 내장 frontElement 단독 승격을 결정론 부스트로 대체(dragend 복원).
  _metaDragZBoost([id].concat(offs.map((o) => o.id)));
}
// drag: 종속을 "테이블 현재위치 + 고정 오프셋" 으로 절대 이동(누적 drift·zoom 수학 비의존).
function _metaNodeDrag() {
  const st = _metaGraph._drag;
  const g = _metaGraph.graph;
  if (!st || !g) return;
  let tp;
  try { tp = g.getElementPosition(st.id); } catch (_) { return; }
  if (!tp) return;
  const to = {};
  st.offs.forEach((o) => { to[o.id] = [tp[0] + o.ox, tp[1] + o.oy]; });
  try { g.translateElementTo(to, false); } catch (_) {}
}
// dragend: 최종 위치 재정합(내 핸들러가 drag-element 보다 먼저 실행돼도 마지막 프레임 lag 제거) + 상태 해제.
function _metaNodeDragEnd(e) {
  _metaNodeDrag();
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  // graph-zorder(§52): 드래그 임시 부스트(+내장 frontElement 잔존) canonical 복원 — 이후 분기(그룹
  //   커밋·nodePos 기록·rebuild)와 직교. 드래그 이력이 z-order 로 굳지 않는 것이 본 cycle 의 핵심 불변식.
  {
    const dz = _metaGraph._drag;
    const rids = [];
    if (id) rids.push(id);
    if (dz && dz.id && dz.id !== id) rids.push(dz.id);
    if (dz && dz.offs) dz.offs.forEach((o) => rids.push(o.id));
    _metaDragZRestore(rids);
  }
  // group-interact(§50): sim-group 리지드 드래그 종료 → grabbed 델타를 groupOffset 에 누적 + 소속 멤버
  //   nodePos(절대좌표)도 같은 델타로 시프트(freeplace clusterOffset MAJOR fix 동형 — 개별 배치 노드가
  //   그룹 이동에서 분리되지 않게). 시각 위치는 이미 drag-element+리지드 핸들러가 최종화 — 즉시 rebuild 불요.
  const gd = _metaGraph._drag;
  // graph-category(§55 A): 카테고리 밴드 리지드 드래그 종료 → 델타를 **멤버 클러스터별 clusterOffset 에
  //   일괄 누적**(신규 offset 계층 없이 기존 ① 계층 재사용) + 소속 nodePos 동반 시프트(freeplace MAJOR
  //   fix 동형) → rebuild 로 CAT 박스 재파생(반응형).
  if (gd && gd.cat) {
    _metaGraph._drag = null;
    let p; try { p = g && g.getElementPosition(gd.id); } catch (_) { p = null; }
    if (p && isFinite(p[0]) && isFinite(p[1])) {
      const dx = p[0] - gd.startX, dy = p[1] - gd.startY;
      if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) {
        const cset = new Set(gd.catClusters || []);
        cset.forEach((cid) => {
          const prev = _metaGraph.clusterOffset.get(cid) || { dx: 0, dy: 0 };
          _metaGraph.clusterOffset.set(cid, { dx: prev.dx + dx, dy: prev.dy + dy });
        });
        _metaGraph.nodePos.forEach((pos, nid) => {
          const n = _metaGraph.nodes.get(nid);
          if (n && cset.has(_metaSchemaComboOf(n))) { pos[0] += dx; pos[1] += dy; }
        });
        _metaG6Apply(false);
      }
    }
    return;
  }
  if (gd && gd.group) {
    _metaGraph._drag = null;
    let p; try { p = g && g.getElementPosition(gd.id); } catch (_) { p = null; }
    if (p && isFinite(p[0]) && isFinite(p[1])) {
      const dx = p[0] - gd.startX, dy = p[1] - gd.startY;
      if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) {
        const prev = _metaGraph.groupOffset.get(gd.group) || { dx: 0, dy: 0 };
        _metaGraph.groupOffset.set(gd.group, { dx: prev.dx + dx, dy: prev.dy + dy });
        const members = _metaGraph.groupMembers.get(gd.group);
        if (members) members.forEach((tk) => { const pos = _metaGraph.nodePos.get(tk); if (pos) { pos[0] += dx; pos[1] += dy; } });
      }
    }
    return;
  }
  // graph-freeplace: 접힌 스키마 카드("SC:") 드래그 = 클러스터 이동 → clusterOffset(combo 드래그와 통합).
  if (id && String(id).startsWith("SC:")) { _metaClusterDragCommit(); _metaGraph._drag = null; return; }
  // 그 외 이동 가능 노드(테이블·컬럼·용어)의 최종 절대위치를 nodePos 에 기록 → rebuild 후에도 유지.
  //   컨트롤/장식(X:/XS:/GB:/GH:/GX:)은 제외. 테이블은 위치만 기록하고, 종속(컬럼·"X:")은 build 가 테이블 델타로 시프트.
  if (g && id && !/^(X:|XS:|XR:|RP:|GB:|GH:|GX:|CAT:|CATH:|CATX:)/.test(String(id))) {   // §54⑤·§55: 장식/밴드 — nodePos 오염 방지
    // 컬럼은 소속 테이블에서 재파생(build)되므로 개별 위치를 기록하지 않는다(dead 엔트리·재빌드 snap-back 방지, 리뷰 NIT).
    const _n = _metaGraph.nodes.get(id);
    if (!_n || _n.label !== "Column") {
      try { const p = g.getElementPosition(id); if (p && isFinite(p[0]) && isFinite(p[1])) _metaGraph.nodePos.set(id, [p[0], p[1]]); } catch (_) {}
    }
    // group-interact(§50, #3 반응형): 그룹 소속 테이블을 옮기면 GB 박스가 새 경계를 감싸도록 rebuild(박스=멤버 bbox 파생).
    //   비-그룹(평면 masonry) 테이블은 기존대로 combo auto-fit 만 — rebuild 없음(회귀 0).
    if (_metaGraph.groupOf.get(id)) { _metaGraph._drag = null; _metaG6Apply(false); return; }
  }
  _metaGraph._drag = null;
}

// graph-freeplace: 스키마 클러스터(combo) 드래그 — 전체 클러스터 위치 이동("분류 drag&drop 위치 이동").
//   dragstart 에서 중심을 기록하고 dragend 에서 델타를 clusterOffset 에 누적 → build 가 L.x0/L.y0 에 가산해
//   카드·테이블·컬럼·장식을 coherent 하게 이동시키고 rebuild(펼침/접기) 후에도 유지한다.
function _metaComboDragStart(e) {
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  _metaGraph._comboDragStart = null;
  if (!g || !id) return;
  try { const p = g.getElementPosition(id); if (p) _metaGraph._comboDragStart = { comboId: id, curId: id, x: p[0], y: p[1] }; } catch (_) {}
}
function _metaComboDragEnd(e) {
  const id = e && e.target && e.target.id;
  _metaClusterDragCommit();
  // graph-zorder(§52): 내장 drag-element frontElement 는 combo 드래그 시 combo+**하위 전체(내부 엣지
  //   포함)**를 델타 승격(영구 잔존·반복 시 단조 증가 — 드래그 이력이 클러스터 간 z-order 로 굳음).
  //   드래그 중에는 그 coherent 승격을 그대로 쓰고(시각적으로 자연), 종료 시 같은 범위를 canonical 로
  //   복원한다 — 노드+콤보(_metaComboMemberIds) + 엣지(_metaComboEdgesRestore, 패널 ux BLOCKING).
  if (id) { _metaDragZRestore([id].concat(_metaComboMemberIds(id))); _metaComboEdgesRestore(id); }
}
// combo:dragend · 접힌 카드 dragend 공용 커밋: _comboDragStart 의 델타를 clusterOffset 에 누적 후 클리어.
function _metaClusterDragCommit() {
  const st = _metaGraph._comboDragStart;
  _metaGraph._comboDragStart = null;
  if (!st || !st.comboId) return;
  _metaClusterOffsetAccumulate(st.comboId, st.x, st.y, st.curId);
}

// G6 v5 그래프 초기화(1회). 이후 상태변경은 _metaG6Apply(setData+draw). Canvas 렌더러(선명·벡터).
function _metaInitGraph() {
  const container = document.getElementById("metadataGraphCanvas");
  if (!container) return;
  if (!window.G6 || typeof window.G6.Graph !== "function") {
    _metaGraphStatus("그래프 라이브러리(G6)를 불러오지 못했습니다.");
    return;
  }
  if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} return; }
  if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
  const baseCfg = {
    container,
    autoResize: true,
    // graph-initview(A2): 과도 줌아웃/과확대 하드 클램프(Cytoscape 시절 minZoom/maxZoom 의 G6 이식).
    zoomRange: [0.05, 4],
    // 상태 스타일만 config 로(기본 스타일은 per-element 인라인 — 매퍼 undefined→To() 크래시 회피).
    node: { state: {
      // feature-0016 §45: 검색 매칭 soft glow — 예전 '너비 증가' 대신 부드러운 앰버 글로우(shadow)로 매칭 강조.
      //   shadow 계열이라 selected/analyzed 의 stroke 와 독립적으로 공존(테두리색 충돌 없음). animation:false 라
      //   전환은 즉시지만 넓은 blur 가 시각적으로 '부드러운' 하이라이트로 읽힌다.
      match: { stroke: "#e8a400", lineWidth: 2, shadowColor: "#f4b400", shadowBlur: 18 },
      analyzed: { stroke: "#7b2fbe", lineWidth: 3 },
      // node-role-viz(적대 패널 U2): 역할색 fill(특히 log #E69F00) 위에서 주황 점선이 위장되지 않게
      //   진행 중엔 fill 을 desaturate — 어느 역할색 위에서도 "분석 중" 이 읽힌다(재분석 경로 실재).
      running: { stroke: "#e08a1e", lineWidth: 2, lineDash: [4, 3], fillOpacity: 0.45 },
      // node-role-viz(적대 패널 U1): 선택 테두리 #9c6515(앰버)는 log/config 역할색과 동계열이라 위장 —
      //   전 역할색·teal 위에서 성립하는 어두운 무채색으로 교체(흰 캔버스 경계 대비 확보).
      selected: { stroke: "#161b22", lineWidth: 3 },
      busy: { stroke: "#0a5b66", lineWidth: 3, lineDash: [2, 2] },   // graph-perf-bg: 펼침/확장 조회 중 임시 표시(teal 점선)
    } },
    // graph-drag: 중간 버튼 드래그 = 카메라 팬(어디서든), 좌클릭 = 기존대로(빈 캔버스 팬 / 노드 이동).
    behaviors: [
      { type: "drag-canvas", key: "drag-canvas", enable: _metaCanvasDragEnable },
      "zoom-canvas",
      { type: "drag-element", key: "drag-element", enable: _metaElementDragEnable },
    ],
    animation: false,
  };
  // graph-initview(E1): 미니맵 — 초기 화면이 "부분"이 될 수 있으므로 전체 지도+뷰포트 표시로 보완.
  // 플러그인 미지원 번들이면 그래프 자체는 살린다(minimap 없이 재생성 — 번들 교체 시 POC 재검증 전제).
  let graph = null;
  try {
    graph = new window.G6.Graph(Object.assign({}, baseCfg, { plugins: [{ type: "minimap", size: [168, 112], position: "right-bottom" }] }));
  } catch (_) { graph = null; }
  if (!graph) {
    try { graph = new window.G6.Graph(baseCfg); } catch (_) { graph = null; }
  }
  if (!graph) { _metaGraphStatus("그래프 초기화 실패(G6)."); return; }
  _metaGraph.graph = graph;
  // feature-0016 §45: 그래프 pane 자체 데이터소스 스코프 select — 변경 시 그 데이터소스 그래프(roots) 재로드.
  //   메타데이터 pane 의 metadataScopeSelect 와 상태(scopeKey)를 공유하되 양쪽 select 값을 동기화한다. 1회 바인딩.
  const _gsc = document.getElementById("graphScopeSelect");
  if (_gsc && !_gsc.dataset.bound) {
    _gsc.dataset.bound = "1";
    _gsc.addEventListener("change", () => {
      adminState.metadata.scopeKey = _gsc.value || "common";
      const ms = document.getElementById("metadataScopeSelect");
      if (ms) ms.value = _gsc.value || "common";
      _metaGraphLoadRoots();
    });
  }
  graph.on("node:click", (e) => _metaGraphOnNodeClick(e));
  graph.on("combo:click", (e) => { const id = e && e.target && e.target.id; if (id) _metaGraphShowClusterDetailById(id); });
  // graph-ctxmenu: 우클릭 상호작용 메뉴(REQ-20260702T113000). 좌표는 container capture 리스너가
  //   선캡처(_metaCtx.x/y — capture 단계가 G6 캔버스 target 핸들러보다 먼저 실행됨). G6 이벤트에
  //   client 좌표가 실리면 그것을 우선 사용. "X:" 접기 컨트롤 우클릭은 소속 테이블 메뉴로 귀속.
  graph.on("node:contextmenu", (e) => {
    let id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    // graph-initview: 스키마 카드("SC:")·펼친 스키마 접기 ctl("XS:") 우클릭 → 스키마 전용 메뉴로 귀속.
    //   이 prefix 를 안 벗기면 _metaGraphCtxForNode 가 모델(SC: 없는 순수 key)에서 노드를 못 찾아 무반응.
    // graph-category(§55 A): 카테고리 밴드 요소 우클릭 — 노드 메뉴 부적합(합성 밴드) → 메뉴 숨김(무반응 방지 후속 여지).
    if (/^CAT(H|X)?:/.test(String(id))) { _metaGraphCtxHide(); return; }
    if (String(id).startsWith("GB:") || String(id).startsWith("GH:") || String(id).startsWith("GX:")) {   // graph-simgroups(§18.8 MAJOR): 그룹 박스/헤더/컨트롤(GX 포함, group-interact §50 REV) 우클릭 = 소속 스키마 메뉴(combo 배경 대체 — 데드존 방지)
      const gk = String(id).slice(3), sep = gk.indexOf("\u0001");
      if (sep >= 0) _metaGraphCtxForSchema(gk.slice(0, sep), p.x, p.y); else _metaGraphCtxHide();
      return;
    }
    if (String(id).startsWith("SC:")) { _metaGraphCtxForSchema(id.slice(3), p.x, p.y); return; }
    if (String(id).startsWith("XS:")) { _metaGraphCtxForSchema(id.slice(3), p.x, p.y); return; }
    if (String(id).startsWith("XR:")) id = String(id).slice(3);   // §54⑤: 루틴 파라미터 ctl → 소속 루틴 메뉴
    else if (String(id).startsWith("RP:")) id = String(id).slice(3).replace(/:\d+$/, "");   // §54⑤: 파라미터 행 → 소속 루틴
    else if (String(id).startsWith("X:")) id = String(id).slice(2);   // 테이블 접기 ctl → 소속 테이블 메뉴
    _metaGraphCtxForNode(id, p.x, p.y);
  });
  graph.on("combo:contextmenu", (e) => {
    const id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    _metaGraphCtxForCombo(id, p.x, p.y);
  });
  graph.on("edge:contextmenu", (e) => {
    // review MAJOR-2: 관계선 자체도 우클릭 대상 — 신뢰도·근거 + 양끝 노드 이동.
    const id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    _metaGraphCtxForEdge(id, p.x, p.y);
  });
  graph.on("canvas:contextmenu", (e) => {
    const p = _metaCtxPoint(e);
    _metaGraphCtxForCanvas(p.x, p.y);
  });
  // capture 단계: 캔버스 전역 브라우저 기본 메뉴 차단 + 클라이언트 좌표 캡처.
  container.addEventListener("contextmenu", (ev) => {
    ev.preventDefault();
    _metaCtx.x = ev.clientX; _metaCtx.y = ev.clientY;
  }, true);
  // graph-drag(REQ ①): 중간(휠) 버튼 mousedown 의 브라우저 기본 동작(자동 스크롤 = 팬 커서)을
  //   억제해 G6 카메라 팬만 남긴다. pointer 이벤트 흐름은 유지되므로 drag-canvas 는 정상 작동.
  container.addEventListener("mousedown", (ev) => {
    if (ev.button === 1) ev.preventDefault();
  }, true);
  // graph-drag(REQ ②): 테이블 노드를 드래그하면 그 하위 종속 UI(접기 "X:" 컨트롤 + 컬럼 노드)도
  //   함께 이동한다. dragstart 에서 각 종속의 테이블 대비 월드 오프셋을 고정 기록하고, node:drag/
  //   dragend 마다 종속을 "테이블 현재 월드좌표 + 오프셋" 으로 translateElementTo 절대이동한다
  //   — 절대-오프셋이라 핸들러 실행 순서·누적 delta·줌 배율에 무관(월드좌표 기준).
  graph.on("node:dragstart", (e) => _metaNodeDragStart(e));
  graph.on("node:drag", (e) => _metaNodeDrag(e));
  graph.on("node:dragend", (e) => _metaNodeDragEnd(e));
  // graph-freeplace: 클러스터(combo) 드래그 = 분류 위치 이동(clusterOffset 누적 → rebuild 유지).
  graph.on("combo:dragstart", (e) => _metaComboDragStart(e));
  graph.on("combo:dragend", (e) => _metaComboDragEnd(e));
  if (!_metaGraph.bound) {
    _metaGraph.bound = true;
    const s = document.getElementById("metadataGraphSearch");
    if (s) {
      let t = null;
      s.addEventListener("input", () => { if (t) clearTimeout(t); t = setTimeout(() => _metaGraphSearch(s.value.trim()), 300); });
    }
    const reset = document.getElementById("metadataGraphResetBtn");
    if (reset) reset.addEventListener("click", () => { _metaGraphLoadRoots(); });
    // graph-product-cat(§43): 제품 카테고리 개요 진입 — scope 를 제품 개요로 전환(공유 scope select 는 datasource 전용 유지).
    const prodBtn = document.getElementById("metadataGraphProductsBtn");
    if (prodBtn) prodBtn.addEventListener("click", () => { adminState.metadata.scopeKey = "__products__"; _metaGraphLoadProducts("__products__"); });
    // graph-initview(E2): 줌 툴바 — +/− 단계 줌, 전체(클램프 없는 조망), 100%.
    const zin = document.getElementById("metaGraphZoomIn");
    if (zin) zin.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomBy(1.25, false); } catch (_) {} } });
    const zout = document.getElementById("metaGraphZoomOut");
    if (zout) zout.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomBy(0.8, false); } catch (_) {} } });
    const zfit = document.getElementById("metaGraphZoomFit");
    if (zfit) zfit.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.fitView({ padding: 30 }, false); } catch (_) {} } });
    const z100 = document.getElementById("metaGraphZoom100");
    if (z100) z100.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomTo(1, false); } catch (_) {} } });
    // graph-initview(E3): 스키마 점프 — 판독 줌 보장 후 해당 클러스터/카드로 focus.
    const jump = document.getElementById("metadataGraphJump");
    if (jump) jump.addEventListener("change", async () => {
      const g = _metaGraph.graph;
      const key = jump.value;
      if (!g || !key) return;
      try {
        const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
        if (isFinite(z) && z < _META_MIN_READ_ZOOM) await g.zoomTo(_META_MIN_READ_ZOOM, false);
        const el = _metaRenderedIdFor(key);   // 접힌 스키마는 카드(SC:) 로 렌더됨
        if (el) await g.focusElement(el, false);
      } catch (_) {}
      jump.value = "";
    });
    const tgl = document.getElementById("metadataGraphDetailToggle");
    if (tgl) tgl.addEventListener("click", () => {
      const body = document.getElementById("metadataGraphView");
      if (body) body.classList.toggle("detail-collapsed");
      setTimeout(() => { if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} _metaGraphFitClamped(false); } }, 60);
    });
    const depthSel = document.getElementById("metadataGraphDepth");
    if (depthSel) depthSel.addEventListener("change", () => {
      const key = _metaGraph.selected || _metaGraph.lastDetailKey || null;
      if (key) { _metaGraphExpand(key); }
      else { _metaGraphStatus(`이웃 깊이 ${depthSel.value}-hop 적용 — 노드를 선택/더블클릭하면 이 깊이로 확장됩니다.`); }
    });
    // graphux7(#1): 상세 패널 방문 이력 뒤로/앞으로.
    const dnBack = document.getElementById("metaGraphDetailBack");
    if (dnBack) dnBack.addEventListener("click", () => _metaGraphHistoryGo(-1));
    const dnFwd = document.getElementById("metaGraphDetailFwd");
    if (dnFwd) dnFwd.addEventListener("click", () => _metaGraphHistoryGo(1));
    // graph-navfilter(§54②): 노드 종류 표시 필터 토글 — Set 갱신 → 버튼 시각 → 전체 rebuild(제자리).
    //   localStorage 영속(metaGraphHiddenKinds, metaGraphDetailW 관례) — scope-독립 preference.
    const _kindLabelKo = { edges: "관계선", function: "ƒ 함수", procedure: "⚙ 프로시저" };
    const _kindBtns = ["metaGraphKindEdges", "metaGraphKindFn", "metaGraphKindProc"]
      .map((bid) => document.getElementById(bid)).filter(Boolean);
    try {
      const saved = JSON.parse(localStorage.getItem("metaGraphHiddenKinds") || "[]");
      if (Array.isArray(saved)) saved.forEach((k) => { if (Object.prototype.hasOwnProperty.call(_kindLabelKo, k)) _metaGraph.hiddenKinds.add(k); });
    } catch (_) {}
    _kindBtns.forEach((b) => {
      const k = b.getAttribute("data-kind");
      const shown = !_metaGraph.hiddenKinds.has(k);
      b.classList.toggle("is-active", shown);
      b.setAttribute("aria-pressed", String(shown));
      b.addEventListener("click", () => {
        const hide = !_metaGraph.hiddenKinds.has(k);
        if (hide) _metaGraph.hiddenKinds.add(k); else _metaGraph.hiddenKinds.delete(k);
        b.classList.toggle("is-active", !hide);
        b.setAttribute("aria-pressed", String(!hide));
        try { localStorage.setItem("metaGraphHiddenKinds", JSON.stringify(Array.from(_metaGraph.hiddenKinds))); } catch (_) {}
        _metaG6Apply(false);   // 카메라 유지 rebuild — masonry/simgroups 가 자리 자동 회수(GX 토글 동형)
        _metaGraphStatus(hide ? `${_kindLabelKo[k]} 숨김 — 그래프에서 제외하고 재배치했습니다.`
                              : `${_kindLabelKo[k]} 표시 — 그래프에 복원했습니다.`);
      });
    });
    _metaGraphInitResizer();
  }
}

// 노드 클릭 라우팅: "−" ctl=접기 · 단일=상세(+테이블은 펼침 전용) · 더블(320ms)=이웃 확장.
//   버그① 해소: 펼쳐진 테이블 body 클릭은 접지 않는다(접기는 "−" 컨트롤만).
function _metaGraphOnNodeClick(e) {
  const id = e && e.target && e.target.id;
  if (!id) return;
  // graph-category(§55 A): 카테고리 밴드 접기/펼치기(CATX) + 밴드/헤더 클릭 = 카테고리 상세.
  if (String(id).startsWith("CATX:")) {
    const ck = String(id).slice(5);
    if (_metaGraph.catCollapsed.has(ck)) _metaGraph.catCollapsed.delete(ck);
    else _metaGraph.catCollapsed.add(ck);
    _metaG6Apply(false);
    return;
  }
  if (String(id).startsWith("CATH:") || String(id).startsWith("CAT:")) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    _metaGraphShowCategoryDetail(ck);
    return;
  }
  // group-interact(§50): 카테고리 그룹 접기/펼치기 토글(GX 컨트롤 — GB/GH 보다 먼저 판정). groupCollapsed 는
  //   사용자 지속 의도로 보존하고, 검색 시 매칭 그룹만 build 가 강제 펼침(결과 가시).
  if (String(id).startsWith("GX:")) {
    const gk = String(id).slice(3);
    if (_metaGraph.groupCollapsed.has(gk)) _metaGraph.groupCollapsed.delete(gk);
    else _metaGraph.groupCollapsed.add(gk);
    _metaG6Apply(false);
    return;
  }
  // graph-simgroups(§18.8 패널 MAJOR): 그룹 배경/헤더의 **클릭(무이동)** 은 소속 스키마 클러스터 상세로 위임
  //   (데드존 방지). group-interact(§50): GB/GH 는 이제 드래그 가능 — G6 이동 임계값으로 click/drag 를 구분하므로
  //   무이동 클릭만 여기 도달(드래그는 node:dragstart/end 리지드 경로).
  if (String(id).startsWith("GB:") || String(id).startsWith("GH:")) {
    const gk = String(id).slice(3), sep = gk.indexOf("\u0001"), sc = sep >= 0 ? gk.slice(0, sep) : null;
    if (sc) _metaGraphShowClusterDetailById(sc);
    return;
  }
  if (String(id).startsWith("XS:")) { _metaGraphCollapseSchema(id.slice(3)); return; }   // graph-initview: 스키마 접기
  // graph-navfilter(§54⑤): 루틴 파라미터 접기 ctl — 모델 삭제 없이 Set 토글(합성 노드라 rebuild 로 소멸).
  //   "XR:" 은 콜론 위치상 startsWith("X:") 에 안 걸리지만 XS: 관례대로 X: 보다 먼저 명시 판정.
  if (String(id).startsWith("XR:")) { _metaGraph.routineExpanded.delete(id.slice(3)); _metaG6Apply(false); return; }
  if (String(id).startsWith("X:")) { _metaGraphCollapse(id.slice(2)); return; }
  // graph-navfilter(§54⑤): 파라미터 행 클릭 → 소속 루틴 상세(RP: 는 합성 id — bogus API fetch 차단).
  //   routine key 자체에 ':' 가 있으므로 꼬리 인덱스(:N)만 strip.
  if (String(id).startsWith("RP:")) { _metaGraphShowDetail(String(id).slice(3).replace(/:\d+$/, "")); return; }
  if (String(id).startsWith("SC:")) {
    // graph-initview: 스키마 카드 클릭 = 그 스키마 테이블 lazy 펼침 + 클러스터 상세(더블클릭 구분 불필요 —
    // 스키마의 이웃확장은 곧 테이블 펼침). 상세는 펼침 성공 시에만 모델 로컬 렌더(실패/빈/stale 시 오도 패널 방지).
    const sk = id.slice(3);
    _metaGraphExpandSchema(sk).then((st) => {
      if (st === "expanded" || st === "already") _metaGraphShowClusterDetailLocal(sk);
    }).catch(() => {});
    return;
  }
  // graph-product-cat(§43): 제품 개요 노드 — Datasource 클릭 → 그 데이터소스 스키마 그래프로 drill(scope 전환),
  //   Product 클릭 → 단일 제품 focus(그 제품의 데이터소스만).
  if (String(id).startsWith("ds:")) {
    const sc = id.slice(3);
    adminState.metadata.scopeKey = sc;
    const selEl = document.getElementById("metadataScopeSelect");
    if (selEl) { try { selEl.value = sc; } catch (_) {} }   // 드롭다운 동기화(datasource 옵션 존재 시)
    _metaGraphLoadRoots();
    return;
  }
  if (String(id).startsWith("product:")) {
    adminState.metadata.scopeKey = id;
    _metaGraphLoadProducts(id);
    return;
  }
  const now = (window.performance && performance.now) ? performance.now() : Date.now();
  const isDbl = (_metaGraph._lastClickId === id && (now - (_metaGraph._lastClickAt || 0)) < 320);
  _metaGraph._lastClickId = id; _metaGraph._lastClickAt = now;
  if (isDbl) {
    _metaGraph._lastClickId = null;
    if (_metaGraph._clickTimer) { clearTimeout(_metaGraph._clickTimer); _metaGraph._clickTimer = null; }
    _metaGraphExpand(id);
    return;
  }
  const n = _metaGraph.nodes.get(id);
  _metaGraphShowDetail(id);
  if (n && n.label === "Table") {
    if (_metaGraph._clickTimer) clearTimeout(_metaGraph._clickTimer);
    _metaGraph._clickTimer = setTimeout(() => {
      _metaGraph._clickTimer = null;
      if (!_metaTableHasCols(id)) _metaGraphToggleColumns(id);   // 접힌 테이블만 펼침(펼쳐졌으면 no-op) — hasCols 단일소스
    }, 340);   // 더블클릭 창(320ms) 초과로 설정 — 빠른 더블클릭이 컬럼펼침+이웃확장 동시발동하는 것 방지(review MINOR-1)
  }
  // graph-navfilter(§54⑤): 루틴 단일클릭 = 파라미터 수직 펼침(테이블 컬럼 펼침과 동형 340ms 타이머).
  //   params 는 모델에 이미 있어 fetch 없는 동기 토글 — 더블클릭(이웃확장)은 기존 경로 그대로.
  //   terms 클러스터(flat-scope)는 방출 게이트와 짝 맞춰 미지원(무효 토글 방지).
  if (n && n.label === "Routine" && _metaSchemaComboOf(n) !== _META_TERMS_COMBO) {
    if (_metaGraph._clickTimer) clearTimeout(_metaGraph._clickTimer);
    _metaGraph._clickTimer = setTimeout(() => {
      _metaGraph._clickTimer = null;
      if (!_metaGraph.routineExpanded.has(id) && _metaRoutineParamList(n).length) {
        _metaGraph.routineExpanded.add(id);
        _metaG6Apply(false);
      }
    }, 340);
  }
}

// ── graph-ctxmenu: 노드 우클릭 상세 상호작용 (REQ-20260702T113000) ──────────────────
//   스키마를 모르는 사용자가 선택 노드의 연관 관계를 파악하는 진입점. 메뉴는 **HTML 오버레이**
//   (G6 요소 아님) — _metaG6Apply 의 setData 전체 재구성과 무간섭(BLUEPRINT §3 함정 회피).
//   전 항목이 읽기성 탐색 + 기존 AI 분석 트리거 재사용 — mutation 0 (CONVENTIONS §10.7 대상 아님).
const _metaCtx = { el: null, x: 0, y: 0, bound: false };

// G6 이벤트 → 메뉴 표시용 client 좌표. e.client 우선, 없으면 capture 리스너가 담은 좌표.
function _metaCtxPoint(e) {
  if (e && e.client && typeof e.client.x === "number" && typeof e.client.y === "number") {
    return { x: e.client.x, y: e.client.y };
  }
  return { x: _metaCtx.x || 0, y: _metaCtx.y || 0 };
}

function _metaGraphCtxHide() {
  if (!_metaCtx.el) return;
  // 접근성(review): 포커스가 메뉴 안에 있을 때만 이전 지점으로 복원 — 외부클릭 dismiss 의 포커스는 뺏지 않음.
  const pf = _metaCtx.prevFocus;
  const restore = pf && pf.focus && _metaCtx.el.contains(document.activeElement) && document.contains(pf);
  try { _metaCtx.el.remove(); } catch (_) {}
  _metaCtx.el = null;
  _metaCtx.prevFocus = null;
  if (restore) { try { pf.focus({ preventScroll: true }); } catch (_) {} }
}

// 메뉴 렌더. items: {head,badge,badgeColor,label} 헤더 · {sep} 구분선 · {label,icon,hint,onClick} 항목 ·
//   {label,icon,chips:[{label,onClick}]} 한 행 소형버튼(hop 선택). 전부 DOM 생성(innerHTML 미사용 — XSS 0).
//   뷰포트 clamp + Esc/외부클릭/스크롤/리사이즈 dismiss + ↑/↓/Enter 키보드 접근.
function _metaGraphCtxShow(items, x, y) {
  const prevFocus = document.activeElement;   // hide 전에 캡처(Hide 가 prevFocus 를 소거하므로)
  _metaGraphCtxHide();
  _metaCtx.prevFocus = prevFocus;
  const menu = document.createElement("div");
  menu.className = "admin-meta-graph-ctxmenu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "그래프 상호작용 메뉴");
  (items || []).forEach((it) => {
    if (!it) return;
    if (it.sep) {
      const s = document.createElement("div");
      s.className = "amgc-sep";
      menu.appendChild(s);
      return;
    }
    if (it.head) {
      const h = document.createElement("div");
      h.className = "amgc-head";
      if (it.badge) {
        const b = document.createElement("span");
        // 상세/관계 패널의 배지 스타일을 재사용(디자인 리뷰 — 동일 개념 배지 시각 통일). 라벨만 한글.
        b.className = "admin-meta-graph-badge amgc-badge";
        b.style.background = it.badgeColor || "#5c6773";
        b.textContent = it.badge;
        h.appendChild(b);
      }
      const t = document.createElement("strong");
      t.textContent = it.label || "";
      h.appendChild(t);
      menu.appendChild(h);
      return;
    }
    if (it.chips) {
      const row = document.createElement("div");
      row.className = "amgc-item amgc-chip-row";
      const lbl = document.createElement("span");
      lbl.className = "amgc-label";
      lbl.textContent = (it.icon ? it.icon + " " : "") + (it.label || "");
      row.appendChild(lbl);
      it.chips.forEach((c) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "amgc-chip";
        b.setAttribute("role", "menuitem");
        b.textContent = c.label;
        b.addEventListener("click", (ev) => { ev.stopPropagation(); _metaGraphCtxHide(); if (c.onClick) c.onClick(); });
        row.appendChild(b);
      });
      menu.appendChild(row);
      return;
    }
    const el = document.createElement("button");
    el.type = "button";
    el.className = "amgc-item";
    el.setAttribute("role", "menuitem");
    if (it.disabled) el.disabled = true;
    const lbl = document.createElement("span");
    lbl.className = "amgc-label";
    lbl.textContent = (it.icon ? it.icon + " " : "") + (it.label || "");
    el.appendChild(lbl);
    if (it.hint) {
      const h = document.createElement("span");
      h.className = "amgc-hint";
      h.textContent = it.hint;
      el.appendChild(h);
    }
    if (!it.disabled) el.addEventListener("click", () => { _metaGraphCtxHide(); if (it.onClick) it.onClick(); });
    menu.appendChild(el);
  });
  document.body.appendChild(menu);
  // 뷰포트 clamp — 우/하단 넘침 시 화면 안쪽으로 이동.
  const r = menu.getBoundingClientRect();
  let px = x, py = y;
  if (px + r.width > window.innerWidth - 8) px = Math.max(8, window.innerWidth - r.width - 8);
  if (py + r.height > window.innerHeight - 8) py = Math.max(8, window.innerHeight - r.height - 8);
  menu.style.left = px + "px";
  menu.style.top = py + "px";
  _metaCtx.el = menu;
  const first = menu.querySelector("button.amgc-item:not(:disabled)");
  if (first) { try { first.focus({ preventScroll: true }); } catch (_) {} }
  if (!_metaCtx.bound) {
    _metaCtx.bound = true;
    // 외부 클릭(모든 버튼) dismiss — 메뉴 내부 pointerdown 은 유지(click 에서 액션 후 hide).
    document.addEventListener("pointerdown", (ev) => {
      if (_metaCtx.el && !_metaCtx.el.contains(ev.target)) _metaGraphCtxHide();
    }, true);
    document.addEventListener("keydown", (ev) => {
      if (!_metaCtx.el) return;
      if (ev.key === "Escape" || ev.key === "Tab") { _metaGraphCtxHide(); return; }   // Tab=닫기(포커스 트랩 대신 복원)
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      const btns = Array.prototype.slice.call(
        _metaCtx.el.querySelectorAll("button.amgc-item:not(:disabled), button.amgc-chip"));
      if (!btns.length) return;
      ev.preventDefault();
      const i = btns.indexOf(document.activeElement);
      const next = btns[(i + (ev.key === "ArrowDown" ? 1 : -1) + btns.length) % btns.length];
      try { next.focus({ preventScroll: true }); } catch (_) {}
    }, true);
    window.addEventListener("resize", _metaGraphCtxHide);
    document.addEventListener("scroll", _metaGraphCtxHide, true);
    // review: 휠 줌(zoom-canvas)은 scroll 이벤트가 없어 메뉴가 옛 좌표에 부유 — wheel 도 dismiss.
    document.addEventListener("wheel", _metaGraphCtxHide, { capture: true, passive: true });
  }
}

// 클립보드 복사(FQN/이름) — navigator.clipboard 우선, 거부/미지원 시 textarea 폴백(review: 침묵 실패 방지).
function _metaGraphCopyText(txt) {
  if (!txt) return;
  const done = () => { if (typeof showToast === "function") showToast(`복사했습니다: ${txt}`); };
  const fallback = () => {
    try {
      const ta = document.createElement("textarea");
      ta.value = txt;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      if (ok) done();
      else if (typeof showToast === "function") showToast("복사에 실패했습니다.", true);
    } catch (_) {
      if (typeof showToast === "function") showToast("복사에 실패했습니다.", true);
    }
  };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done, fallback);
      return;
    }
  } catch (_) {}
  fallback();
}

// 노드(Table/Column/Term) kind 별 우클릭 메뉴 구성.
function _metaGraphCtxForNode(key, x, y) {
  const n = _metaGraph.nodes.get(key);
  if (!n) return;
  const scope = key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common");
  const hopChips = {
    icon: "🕸", label: "관계 확장",
    // review: 1회성 확장 — 툴바 '이웃 깊이' select 를 조용히 바꾸지 않고 depth 를 직접 넘긴다.
    chips: ["1", "2", "3"].map((d) => ({ label: `${d}-hop`, onClick: () => _metaGraphExpand(key, d) })),
  };
  const items = [
    { head: true, badge: _META_LABEL_KO[n.label] || n.label || "노드", badgeColor: _META_GRAPH_COLOR[n.label] || "#5c6773", label: n.name || key },
    { icon: "📋", label: "상세 보기", hint: "설명·컬럼·용어", onClick: () => _metaGraphShowDetail(key) },
    { icon: "🔗", label: "관계 상세", hint: "방향·신뢰도·근거", onClick: () => _metaGraphShowRelations(key) },
    hopChips,   // review: 더블클릭 확장과 파리티 — Column 포함 전 kind 노출
  ];
  items.push({ icon: "🎯", label: "이 노드 중심으로 보기", hint: "주변만 남김", onClick: () => _metaGraphFocus(key) });
  if (n.label === "Table") {
    items.push(_metaTableHasCols(key)
      ? { icon: "▦", label: "컬럼 접기", onClick: () => _metaGraphCollapse(key) }
      : { icon: "▦", label: "컬럼 펼치기", onClick: () => _metaGraphToggleColumns(key) });
  }
  // graph-navfilter(§54⑤): 루틴 파라미터 접기/펼치기 — 테이블 컬럼 항목의 루틴 판(동기 Set 토글).
  //   terms 클러스터는 방출 게이트와 짝 맞춰 항목 미노출.
  if (n.label === "Routine" && _metaSchemaComboOf(n) !== _META_TERMS_COMBO && _metaRoutineParamList(n).length) {
    const rOpen = _metaGraph.routineExpanded.has(key);
    items.push({ icon: "▦", label: rOpen ? "파라미터 접기" : "파라미터 펼치기",
      onClick: () => { if (rOpen) _metaGraph.routineExpanded.delete(key); else _metaGraph.routineExpanded.add(key); _metaG6Apply(false); } });
  }
  if (n.label === "Column") {
    const pk = _metaColParent(key, n.fqn);
    if (pk) items.push({ icon: "📄", label: "소속 테이블 상세", onClick: () => _metaGraphShowDetail(pk) });
  }
  items.push({ sep: true });
  items.push({
    // graph-funcproc(REQ ④): '재분석' 라벨 제거 — 능동 분석 재실행이 곧 재분석(UX 중복 정리).
    icon: "✨", label: "AI 능동 분석", hint: "관련 노드 자동 분석 · 상세 패널 버튼 hover 로 지침 입력",
    // 상세 카드를 먼저 열어 AI box 에 진행이 보이게 한 뒤 트리거(ShowDetail 은 내부 catch 라 항상 resolve).
    // §18.8 패널(MINOR): ctxmenu 경로는 지침 미전송 — 이전 노드의 stale 지침이 화면 표시 없이 암묵
    // 적용되는 것을 차단. 지침은 popover(입력이 눈에 보이는 경로)로만 전송한다.
    onClick: () => { _metaGraphShowDetail(key).then(() => _metaGraphAnalyze(key, scope)); },
  });
  items.push({
    icon: "📑", label: n.label === "GlossaryTerm" ? "이름 복사" : "FQN 복사",
    onClick: () => _metaGraphCopyText(n.fqn || n.name || key),
  });
  _metaGraphCtxShow(items, x, y);
}

// graph-initview: 스키마(접힌 카드 "SC:" 또는 펼친 스키마의 접기 ctl "XS:") 우클릭 메뉴.
//   좌클릭(펼치기/접기)과 파리티 — 접힌 카드도 우클릭이 동작해 펼치기·상세·복사에 도달한다.
function _metaGraphCtxForSchema(schemaKey, x, y) {
  if (!schemaKey) return;
  const n = _metaGraph.nodes.get(schemaKey);
  const name = _metaComboName(schemaKey);
  const expanded = _metaGraph.schemaExpanded.has(schemaKey);
  const cnt = (n && typeof n.table_count === "number") ? n.table_count : null;
  const items = [
    { head: true, badge: "스키마", badgeColor: _META_GRAPH_COLOR.Schema, label: cnt != null ? `${name} · 테이블 ${cnt}` : name },
  ];
  items.push(expanded
    ? { icon: "▦", label: "접기 (카드로)", onClick: () => _metaGraphCollapseSchema(schemaKey) }
    : { icon: "▦", label: "펼치기 (테이블 표시)", hint: cnt != null ? `${cnt}개` : "", onClick: () => {
        // 좌클릭 SC: 경로와 동일 — 펼침 성공/기존 상태에서만 로컬 클러스터 상세 렌더(실패·빈·stale 오도 방지).
        //   ("already" 는 SC 경로에선 도달 불가 — expanded 면 위 접기 항목이 대신 붙음 — 이나 좌클릭과 대칭 유지.)
        _metaGraphExpandSchema(schemaKey).then((st) => { if (st === "expanded" || st === "already") _metaGraphShowClusterDetailLocal(schemaKey); }).catch(() => {});
      } });
  // 클러스터 상세는 그래프를 펼치지 않고 API 로 테이블 목록을 조회(접힌 카드에서 "펼치지 않고 훑어보기").
  items.push({ icon: "📋", label: "클러스터 상세", hint: "테이블 목록(펼치지 않음)", onClick: () => _metaGraphShowClusterDetailById(schemaKey) });
  // routine-dbanalysis(§53): DB(스키마) 단위 AI 능동 분석 — 미분석 테이블 일괄 시드(confirm 에 대상 수 표시).
  items.push({ icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(schemaKey) });
  items.push({ icon: "📑", label: "스키마명 복사", onClick: () => _metaGraphCopyText(name) });
  _metaGraphCtxShow(items, x, y);
}

// 스키마 클러스터(펼친 combo) 우클릭 메뉴 — combo 배경/테두리 우클릭. 접힌 카드는 _metaGraphCtxForSchema.
function _metaGraphCtxForCombo(comboId, x, y) {
  const name = _metaComboName(comboId);
  const isTerms = comboId === _META_TERMS_COMBO;
  _metaGraphCtxShow([
    { head: true, badge: isTerms ? "묶음" : "스키마", badgeColor: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema, label: name },
    { icon: "📋", label: "클러스터 상세", hint: "테이블 목록", onClick: () => _metaGraphShowClusterDetailById(comboId) },
    // graph-initview 파리티: 펼친 스키마 combo 우클릭도 카드로 접기 도달(기존엔 "−" ctl 클릭만).
    (isTerms || !_metaGraph.schemaExpanded.has(comboId)) ? null
      : { icon: "▦", label: "접기 (카드로)", onClick: () => _metaGraphCollapseSchema(comboId) },
    // routine-dbanalysis(§53): DB 단위 능동 분석 — 용어 묶음(합성)은 제외.
    isTerms ? null : { icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(comboId) },
    isTerms ? null : { icon: "📑", label: "스키마명 복사", onClick: () => _metaGraphCopyText(name) },
  ], x, y);
}

// 엣지(관계선) 우클릭 메뉴 (review MAJOR-2) — 관계 자체의 신뢰도·근거·cardinality + 양끝 노드 이동.
function _metaGraphCtxForEdge(edgeId, x, y) {
  const e = _metaGraph.edges.get(edgeId);
  if (!e) { _metaGraphCtxForCanvas(x, y); return; }
  const sn = _metaGraph.nodes.get(e.source) || { name: e.source };
  const tn = _metaGraph.nodes.get(e.target) || { name: e.target };
  const w = (e.weight != null && e.weight !== "" && !isNaN(Number(e.weight))) ? Number(e.weight).toFixed(2) : "";
  const statusKo = e.status === "trusted" ? "신뢰" : (e.status === "candidate" ? "추정" : (e.edge_source === "fk_introspect" ? "FK" : ""));
  const srcKo = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "";
  const info = [
    _META_EDGE_TYPE_KO[e.type] || e.type,
    statusKo ? `${statusKo}${w ? ` w=${w}` : ""}` : "",
    e.cardinality ? `[${e.cardinality}]` : "",
    srcKo ? `근거: ${srcKo}` : "",
  ].filter(Boolean).join(" · ");
  // 관계 상세의 앵커: 컬럼 단위 엣지면 소속 테이블 관점으로 (테이블 행에 조인 컬럼이 함께 표기됨).
  const anchor = (sn.label === "Column" && _metaColParent(e.source, sn.fqn)) || e.source;
  _metaGraphCtxShow([
    { head: true, badge: "관계", badgeColor: "#6b4410", label: `${sn.name || e.source} → ${tn.name || e.target}` },
    { icon: "ℹ️", label: info, disabled: true },
    { icon: "📋", label: `출발 노드 상세 — ${sn.name || e.source}`, onClick: () => _metaGraphShowDetail(e.source) },
    { icon: "📋", label: `도착 노드 상세 — ${tn.name || e.target}`, onClick: () => _metaGraphShowDetail(e.target) },
    { icon: "🔗", label: "관계 상세 (출발 기준)", hint: "방향·신뢰도·근거", onClick: () => _metaGraphShowRelations(anchor) },
  ], x, y);
}

// 빈 캔버스 우클릭 메뉴.
function _metaGraphCtxForCanvas(x, y) {
  _metaGraphCtxShow([
    { icon: "⛶", label: "전체 맞춤", onClick: () => { const g = _metaGraph.graph; if (g) { try { g.fitView({ padding: 30 }, false); } catch (_) {} } } },
    { icon: "↺", label: "그래프 초기화", hint: "데이터소스 진입 뷰", onClick: () => _metaGraphLoadRoots() },
  ], x, y);
}

// graph-panel-resize: 상세 패널 폭을 드래그(및 ←/→ 키)로 조절 — CSS var(--meta-graph-detail-w) 갱신 + localStorage 영속.
//   핸들은 캔버스 오른쪽·패널 왼쪽 사이의 세로 바(#metadataGraphResizer)라, 왼쪽으로 끌면 패널이 넓어진다.
//   1fr 캔버스가 줄면 ResizeObserver(위)가 cy.resize()+fit 을 debounce 호출하므로 별도 라이브 리사이즈 불필요(놓을 때만 보강).
function _metaGraphInitResizer() {
  const handle = document.getElementById("metadataGraphResizer");
  const body = document.querySelector(".admin-meta-graph-body");
  const root = document.getElementById("metadataGraphView");
  if (!handle || !body || !root || handle._bound) return;
  handle._bound = true;
  const MIN = 240, CANVAS_MIN = 360;   // 패널 최소폭 / 캔버스 보존 최소폭
  const clampW = (w) => {
    const total = body.clientWidth || 0;
    const max = total > 0 ? Math.max(MIN, total - CANVAS_MIN - 16) : Math.max(MIN, w);
    return Math.round(Math.min(Math.max(w, MIN), max));
  };
  const applyW = (w) => { root.style.setProperty("--meta-graph-detail-w", clampW(w) + "px"); };
  const curW = () => {
    const v = getComputedStyle(root).getPropertyValue("--meta-graph-detail-w").trim();
    const n = parseInt(v, 10);
    if (isFinite(n) && n > 0) return n;
    const d = document.getElementById("metadataGraphDetail");
    return (d && d.clientWidth) ? d.clientWidth : 340;
  };
  const persist = () => { try { localStorage.setItem("metaGraphDetailW", String(curW())); } catch (_) {} };
  const refit = () => { if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} _metaGraphFitClamped(false); } };   // graph-initview: 클램프 fit(무-focus — 현재 위치 보존)
  // 저장된 폭 복원(있으면).
  try { const saved = parseInt(localStorage.getItem("metaGraphDetailW") || "", 10); if (isFinite(saved) && saved > 0) applyW(saved); } catch (_) {}
  // 리뷰 fix(MEDIUM-2): 창 크기 변화 시 현재 폭을 새 body 폭 기준으로 재-clamp — 넓은 화면에서 저장한 폭이
  //   좁은 화면에서 캔버스를 near-0 로 짓누르지 않게 한다(ResizeObserver 는 cy.resize 만 하고 폭 재적용 안 함).
  let _rwT = null;
  window.addEventListener("resize", () => {
    if (_rwT) clearTimeout(_rwT);
    _rwT = setTimeout(() => { applyW(curW()); }, 150);
  });
  let startX = 0, startW = 0;
  const onMove = (e) => { applyW(startW + (startX - e.clientX)); };   // 왼쪽으로 끌면 패널 넓어짐
  const endDrag = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", endDrag);
    document.removeEventListener("pointercancel", endDrag);   // 리뷰 fix(MEDIUM-1): 터치 중단·제스처 취소 시에도 정리
    handle.classList.remove("is-dragging");
    document.body.style.userSelect = "";
    persist(); refit();
  };
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    startX = e.clientX; startW = curW();
    handle.classList.add("is-dragging");
    document.body.style.userSelect = "none";
    try { handle.setPointerCapture(e.pointerId); } catch (_) {}   // 리뷰 fix(MEDIUM-1): 캡처로 out-of-window 이동·취소 확실 정리
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", endDrag);
    document.addEventListener("pointercancel", endDrag);
  });
  // 키보드 접근(WAI-ARIA separator): ← 넓게 / → 좁게, 24px 단위.
  handle.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    applyW(curW() + (e.key === "ArrowLeft" ? 24 : -24));
    persist(); refit();
  });
}

// 검색어 관련도 점수(0~1): exact name > prefix > name contains > fqn contains.
function _metaRelevance(name, fqn, ql) {
  name = (name || "").toLowerCase(); fqn = (fqn || "").toLowerCase();
  if (name === ql) return 1.0;
  if (name.startsWith(ql)) return 0.85;
  if (name.indexOf(ql) >= 0) return 0.65;
  if (fqn.indexOf(ql) >= 0) return 0.45;
  return 0.3;
}

// graph-navfilter(§54③): 검색이 순수 추가한 노드 중 사용자 미접촉(pristine)만 모델에서 회수 —
//   펼침(schemaExpanded/Loaded)·드래그(clusterOffset/nodePos)·확장(엣지 참조·컬럼 보유)된 것은 보존.
//   재검색 키스트로크마다 호출해 비매칭 카드의 누적을 막고, 클리어 시엔 검색 잔재만 걷어낸다.
function _metaSearchPrunePristine() {
  if (!_metaGraph.searchAdded.size) return;
  const referenced = new Set();
  _metaGraph.edges.forEach((e) => { referenced.add(e.source); referenced.add(e.target); });
  _metaGraph.searchAdded.forEach((k) => {
    const n = _metaGraph.nodes.get(k);
    if (!n) return;
    // 재검증 MINOR: Column 은 회수 제외 — colsByTable 불변식(Ingest 증가·Collapse 감소·Reset 초기화
    //   3경로 전용)을 prune 이 4번째 삭제 경로로 우회하면 flat-scope 에서 hasCols 가 영구 true 로 고착.
    if (n.label === "Column") return;
    if (n.label === "Schema") {
      // schemaLoaded 포함 — 펼쳤다 접은 카드는 모델 테이블이 남아(렌더 게이팅만) 카드 회수 시 고아가 된다.
      if (_metaGraph.schemaExpanded.has(k) || _metaGraph.schemaLoaded.has(k) || _metaGraph.clusterOffset.has(k)) return;
    } else {
      if (_metaGraph.nodePos.has(k) || referenced.has(k) || _metaGraph.expanded.has(k)
          || _metaGraph.routineExpanded.has(k) || _metaTableHasCols(k)) return;   // §54⑤ 패널: 파라미터 펼침도 사용자 접촉
    }
    _metaGraph.nodes.delete(k);
    _metaGraph.routineExpanded.delete(k);   // stale 키 정리(회수된 노드의 펼침 상태 잔존 방지)
  });
  _metaGraph.searchAdded.clear();
}

async function _metaGraphSearch(q) {
  if (!_metaGraph.graph) return;
  _metaGraph.lastQuery = q;
  if (!q) {
    // graph-navfilter(§54③): 검색어 클리어는 그래프 구성(펼침·배치·확장)을 보존한다 — 검색 잔재
    //   (pristine 카드·glow)만 걷어내고 제자리 rebuild. 초기 화면 복귀는 '그래프 초기화' 버튼 전용.
    //   §54③ 패널 MAJOR: 검색이 products 개요를 리셋하고 들어온 경우(base.mode=products)는 보존할
    //   사용자 구성이 없다 — 원 화면(제품 개요)으로 복귀. 중심 보기 base 는 칩 복원.
    if (_metaGraph.mode !== "search" && !_metaGraph.searchMatchNodes) return;   // 지울 검색 상태 없음 — no-op(base 소비 전, 재검증 MINOR)
    const base = _metaGraph._searchBase; _metaGraph._searchBase = null;
    const scopeNow = adminState.metadata.scopeKey || "common";
    const preserve = _metaGraph.mode !== "products" && !(base && base.mode === "products")
      && (_metaGraph.loadedScope || "common") === scopeNow && _metaGraph.nodes.size > 0;
    if (!preserve) { _metaGraphLoadRoots(); return; }
    _metaSearchPrunePristine();
    _metaGraph.searchMatch = null; _metaGraph.searchMatchTables = null;
    _metaGraph.searchMatchNodes = null; _metaGraph.searchCapped = false;
    if (_metaGraph.nodes.size === 0) { _metaGraphLoadRoots(); return; }   // 패널 MAJOR: 잔재 회수 후 빈 모델 — 허위 '유지' 방지
    _metaGraph.mode = (base && base.mode && base.mode !== "search") ? base.mode : "roots";   // 원 모드(neighbor 등) 복원
    _metaGraph.nodes.forEach((n) => { delete n.rel; });
    const seq0 = _metaGraph._opSeq;            // bump 없음 — in-flight 펼침·확장은 여전히 유효(additive 병존)
    await _metaG6Apply(false);                 // 카메라·배치 유지(fit 금지)
    if (seq0 !== _metaGraph._opSeq) return;
    if (base && base.focusName) {
      _metaGraphFocusChip(base.focusName);     // 패널 MAJOR: 중심 보기 부분 그래프가 '전체'로 위장하지 않게 칩 복원
      _metaGraphStatus("검색 해제 — 중심 보기 서브그래프 유지(전체는 칩의 '전체 보기' 또는 '초기화').");
    } else {
      _metaGraphStatus("검색 해제 — 그래프 구성(펼침·배치·확장)은 유지됩니다. 초기 화면은 '초기화' 버튼.");
    }
    return;
  }
  _metaGraphStatus("검색 중…");
  const scope = adminState.metadata.scopeKey || "common";
  const scopeParam = (scope && scope !== "common") ? `&scope=${encodeURIComponent(scope)}` : "";
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?q=${encodeURIComponent(q)}${scopeParam}`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "그래프 검색 실패");
    return;
  }
  if (q !== _metaGraph.lastQuery) return;
  // graph-navfilter(§54③): 같은 scope 의 기존 그래프가 있으면 리셋하지 않고 **additive overlay** —
  //   사용자 구성(펼침·드래그·확장) 위에 검색 하이라이트만 얹는다. mode 대입 전에 판정(아래서 "search" 로 바뀜).
  const preserve = _metaGraph.mode !== "products"
    && (_metaGraph.loadedScope || "common") === scope && _metaGraph.nodes.size > 0;
  // §54③ 패널 MAJOR: 검색 진입 직전 base 컨텍스트 기록(최초 키스트로크만) — 클리어 시 products 복귀·
  //   중심 보기 칩 복원의 근거. mode 가 이미 "search" 면 이전 키스트로크의 base 를 유지.
  if (_metaGraph.mode !== "search") {
    _metaGraph._searchBase = { mode: _metaGraph.mode, focusName: _metaGraph._focusName || null };
  }
  _metaGraph.mode = "search";
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);   // 검색 컨텍스트로 전환 — 중심 보기 칩 해제
  if (preserve) _metaSearchPrunePristine();   // 직전 키스트로크의 pristine 추가분 회수(누적 방지)
  else _metaGraphResetModel();
  const seq = _metaGraph._opSeq;   // review LOW-CONF: 세대 캡처 — await 사이 scope 전환 시 tail(status) 폐기.
  // graph-initview 검색 = **스키마 카드 필터 뷰**(사용자 요청): 매칭 테이블을 스키마별로 집계해 카드를
  //   유지하고 badge 를 "매칭/전체" 로 표기(펼치지 않음). 카드 클릭 시 그 스키마를 펼쳐 매칭 테이블을 강조.
  //   (이전엔 매칭 스키마를 combo 로 auto-expand 해 카드·badge 가 사라졌음.)
  const matchBySchema = new Map();   // schemaKey -> Set(매칭 테이블 key)
  const matchTables = new Set();     // 매칭 테이블 key(펼침 시 크기 강조)
  const terms = [];                  // 매칭 GlossaryTerm/기타 + 스키마 미도출 Table/Column(카드 아닌 노드 — terms 클러스터로 표시)
  const addMatch = (sc, tk) => { if (!matchBySchema.has(sc)) matchBySchema.set(sc, new Set()); if (tk) { matchBySchema.get(sc).add(tk); matchTables.add(tk); } };
  (data.nodes || []).forEach((nd) => {
    if (!nd || !nd.key) return;
    if (nd.label === "Table") {
      const sc = _metaSchemaComboOf(nd);
      if (sc && sc !== _META_TERMS_COMBO) addMatch(sc, nd.key);
      else terms.push(nd);   // review MINOR: 스키마 세그먼트 없는 flat scope 테이블 — 소실 방지(terms 로 표시)
    } else if (nd.label === "Column") {
      const tk = _metaColParent(nd.key, nd.fqn);
      const sc = tk ? _metaCatParent(tk, tk.slice(tk.indexOf(":") + 1)) : null;
      if (sc && sc !== _META_TERMS_COMBO) addMatch(sc, tk);
      else terms.push(nd);
    } else if (nd.label === "Routine") {
      // graph-funcproc: 함수·프로시저 매칭 — 소속 스키마 카드는 표시하되 badge **카운트에는 미가산**
      // (§18.8 패널 MINOR: badge 분모 table_count 는 테이블 총계라 Routine 가산 시 N>M 모순).
      // 강조는 searchMatchTables 로 유지 — 카드 펼침 시 schema_tables 가 Routine 을 로드하고 ƒ/⚙ 칩이 커진다.
      const sc = _metaCatParent(nd.key, nd.fqn);
      if (sc && sc !== _META_TERMS_COMBO) { addMatch(sc, null); matchTables.add(nd.key); }
      else terms.push(nd);
    } else if (nd.label === "Schema") { addMatch(nd.key, null); }   // 스키마명 매칭 → 0 매칭이라도 카드 표시(0/전체)
    else terms.push(nd);
  });
  _metaGraph.searchMatch = matchBySchema;
  _metaGraph.searchMatchTables = matchTables;
  // feature-0016 §45: 직접 매칭 노드(테이블/컬럼/용어) key 집합 — 렌더 시 'match' 상태 soft glow 대상(너비 증가 대체).
  const matchNodes = new Set();
  (data.nodes || []).forEach((nd) => { if (nd && nd.key) matchNodes.add(nd.key); });
  _metaGraph.searchMatchNodes = matchNodes;
  // review MAJOR: search_nodes 는 cap(_META_SEARCH_CAP) 로 평면 절단하고 truncated 플래그가 없다 →
  //   응답이 cap 도달이면 스키마별 매칭 카운트는 부분값이므로 badge 에 '+'(≥) 로 표기해 오인 방지.
  const nRaw = (data.nodes || []).length;
  _metaGraph.searchCapped = nRaw >= _META_SEARCH_CAP;
  // 매칭 스키마를 카드로 ingest(전체 총계는 roots 캐시 schemaTotals). auto-expand 하지 않음(카드 유지).
  //   §54③: 신규 추가 key 를 searchAdded 로 추적 — 다음 검색/클리어 때 pristine 만 회수.
  matchBySchema.forEach((set, sc) => {
    const total = _metaGraph.schemaTotals ? _metaGraph.schemaTotals.get(sc) : null;
    const added = _metaGraphIngest([{ label: "Schema", key: sc, name: _metaComboName(sc), fqn: _metaComboName(sc), table_count: (typeof total === "number" ? total : null) }], []);
    (added || []).forEach((k) => _metaGraph.searchAdded.add(k));
  });
  if (terms.length) {
    const added = _metaGraphIngest(terms, []);
    (added || []).forEach((k) => _metaGraph.searchAdded.add(k));
  }
  // 유사도(rel) → 용어 칩 크기 가산. 백엔드 pg_trgm score 우선, 없으면 클라 휴리스틱.
  //   §54③: preserve 모델에는 기존 노드 수천 개가 있으므로 **매칭 노드에만** rel 부여(전역 부여 시
  //   비매칭 칩 폭 왜곡·상세 유사도 배지 오표시). 비-preserve(리셋) 모델은 카드+terms 뿐이라 동치.
  const ql = q.toLowerCase();
  _metaGraph.nodes.forEach((n) => {
    if (matchNodes.has(n.key)) n.rel = (typeof n.score === "number") ? n.score : _metaRelevance(n.name, n.fqn, ql);
    else delete n.rel;
  });
  await _metaG6Apply(preserve ? false : true);   // §54③: preserve 시 카메라·배치 유지
  if (seq !== _metaGraph._opSeq) return;   // await 사이 scope/roots 전환 — 이 검색의 tail(status) 폐기
  if (q !== _metaGraph.lastQuery) return;  // §54③ 패널 MINOR: 클리어는 _opSeq 무-bump — stale 검색 tail 은 lastQuery 로 폐기
  _metaGraphSyncAnalysisMarkers(scope);
  // §54③: preserve 시 첫 매칭 렌더 노드로 부드러운 팬(fit 없이) — 하이라이트 가시화.
  if (preserve && matchNodes.size) {
    const first = Array.from(matchNodes).find((k) => _metaRenderedIdFor(k));
    if (first) _metaGraphAnimateFocus(first, seq);
  }
  const nSchemas = matchBySchema.size;
  const capNote = _metaGraph.searchCapped ? " · 결과 상한(부분 카운트, 검색어를 좁혀 정확도↑)" : "";
  // §54② 패널 MINOR: 매칭에 Routine 이 있는데 ƒ/⚙ 표시 필터가 꺼져 있으면 비가시 원인 안내.
  const anyHiddenRoutineMatch = (data.nodes || []).some((nd) => nd && nd.label === "Routine"
    && _metaGraph.hiddenKinds.has((nd.routine_type === "function") ? "function" : "procedure"));   // 재검증 NIT: kind 별 대조(과잉 발화 방지)
  const hiddenNote = anyHiddenRoutineMatch
    ? " ※ 매칭된 함수/프로시저 일부는 표시 필터로 숨김 상태 — 툴바 ƒ/⚙ 토글을 켜세요." : "";
  if (!nRaw) _metaGraphStatus("검색 결과 없음.");
  else if (nSchemas === 0) _metaGraphStatus(`'${q}' — 용어·기타 ${terms.length}개 매칭(해당 스키마 테이블 없음).${capNote}${hiddenNote}`);
  else _metaGraphStatus(`'${q}' — 스키마 ${nSchemas}개 매칭. 카드 badge = 매칭/전체 테이블. 카드 클릭으로 펼쳐 매칭 테이블(앰버 글로우)을 확인.${capNote}${hiddenNote}`);
}

// 선택 강조: 모델 selected 갱신 + 이전/현재 노드 state 만 갱신(전체 rebuild 없이 가벼움).
function _metaGraphSetSelected(key) {
  const g = _metaGraph.graph;
  const prev = _metaGraph.selected;
  _metaGraph.selected = key || null;
  if (!g) return;
  // graph-perf-bg fix: _metaApplyState 경유 — busy 보존 + _stateCache signature 동기화(명령형 writer 가 캐시를 stale 로 남기지 않음).
  if (prev && prev !== key && _metaGraph.nodes.has(prev)) _metaApplyState(prev);
  if (key && _metaGraph.nodes.has(key)) _metaApplyState(key);
}

// 테이블 key 에 (모델상) 컬럼 노드가 있으면 true — 펼침 상태의 단일 소스.
//   graph-perf-bg: 전 노드 O(N) 선형 스캔(매 Table 클릭·토글마다 호출) → colsByTable 인덱스 O(1) 조회.
//   인덱스는 _metaGraphIngest(추가)·_metaGraphCollapse(제거)·_metaGraphResetModel(초기화) 세 경로에서만 갱신.
function _metaTableHasCols(key) {
  return (_metaGraph.colsByTable.get(key) || 0) > 0;
}

// 단일 클릭: 그래프 구조는 그대로 두고 상세 카드만 갱신(1-hop 으로 컬럼·직접관계·용어).
// graphux7(#1) + graph-navfilter(§54①): 상세 패널 방문 이력(뒤로/앞으로) — view-typed 엔트리
//   {v:"node"|"cluster"|"rel", k:key} 로 노드 상세뿐 아니라 클러스터 상세·관계 상세도 되짚는다.
const _META_HIST_CAP = 50;
function _metaGraphHistoryRecord(key, view) {
  if (!key || _metaGraph._histNav) return;              // 뒤로/앞으로 네비 중 재기록 금지
  const v = view || "node";
  const h = _metaGraph.detailHist;
  const cur = h[_metaGraph.detailHistIdx];
  if (cur && cur.k === key && cur.v === v) return;      // 같은 화면 연속 재선택 — 중복 억제
  h.splice(_metaGraph.detailHistIdx + 1);               // 앞으로 분기 절단(새 방문이 forward 이력을 덮음)
  h.push({ v, k: key });
  if (h.length > _META_HIST_CAP) h.shift();             // 상한 초과 시 오래된 앞부분 제거
  _metaGraph.detailHistIdx = h.length - 1;
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryGo(dir) {
  const ni = _metaGraph.detailHistIdx + dir;
  if (ni < 0 || ni >= _metaGraph.detailHist.length) return;
  _metaGraph.detailHistIdx = ni;
  const ent = _metaGraph.detailHist[ni];
  _metaGraph._histNav = true;                           // 각 진입 함수의 Record(첫 await 이전 동기 구간)가 재기록하지 않게
  try {
    // 클러스터 복원은 반드시 ById — Local 은 모델-로컬이라 중심보기(resetModel) 후 빈 목록을 렌더.
    if (ent.v === "cluster") _metaGraphShowClusterDetailById(ent.k);
    else if (ent.v === "rel") _metaGraphShowRelations(ent.k);
    else _metaGraphShowDetail(ent.k);
  } finally { _metaGraph._histNav = false; }
  // 카메라 재현(fire-and-forget) — 미렌더(접힘/모델 제거)면 skip, 패널은 API 재조회로 복원됨.
  if (_metaRenderedIdFor(ent.k)) {
    const seq = _metaGraph._opSeq;
    _metaGraphAnimateFocus(ent.k, seq);
  }
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryReset() {
  _metaGraph.detailHist = [];
  _metaGraph.detailHistIdx = -1;
  _metaGraph._histNav = false;
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryUpdateUI() {
  const nav = document.getElementById("metadataGraphDetailNav");
  if (!nav) return;
  const h = _metaGraph.detailHist, i = _metaGraph.detailHistIdx;
  if (h.length <= 1) { nav.hidden = true; return; }     // 0~1개면 네비 의미 없음 — 숨김
  nav.hidden = false;
  const back = document.getElementById("metaGraphDetailBack");
  const fwd = document.getElementById("metaGraphDetailFwd");
  const label = document.getElementById("metaGraphDetailNavLabel");
  if (back) back.disabled = i <= 0;
  if (fwd) fwd.disabled = i >= h.length - 1;
  if (label) label.textContent = `${i + 1}/${h.length}`;
}

async function _metaGraphShowDetail(key) {
  if (!_metaGraph.graph || !key) return;
  _metaGraph.lastDetailKey = key;
  _metaGraphHistoryRecord(key);   // graphux7(#1): 방문 이력 기록(뒤로/앞으로 네비 중이면 no-op).
  _metaGraphStatus("상세 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "상세 조회 실패");
    return;
  }
  _metaGraphSetSelected(key);
  const self = (data.nodes || []).find((x) => x.key === key) || { key, name: key };
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  const nb = Math.max(0, (data.nodes || []).length - 1);
  _metaGraphStatus(`상세: ${self.name || key} · 이웃 ${nb}개 (더블클릭 = 관계 확장 · 우클릭 = 상호작용 메뉴)`);
}

// graph-reltrace ②③: 관계 클릭 → **대상 테이블·컬럼으로 그래프 추적**.
//   상세 패널/관계 상세/AI 능동 분석 결과의 관계 행이 공통으로 호출한다. 대상 테이블을 이웃과 함께
//   화면에 가져오고(스키마 펼침·관계 엣지 로드), 컬럼을 전개해 **대상 컬럼을 강조+카메라 focus** 한다.
//   기존 "상대 노드 상세만 교체"(showDetail)와 달리 사용자가 연결을 실제 화면에서 따라가게 한다.
async function _metaGraphTraceRelation(targetKey) {
  if (!_metaGraph.graph || !targetKey) return;
  // review MINOR: 대상이 컬럼/테이블이 아닌 노드(용어 GlossaryTerm 등)면 추적(테이블·컬럼 강조)이
  //   의미 없으므로 상세 보기로 라우팅. "관계 상세" 의 연관 용어 행이 trace 로 넘어오던 오라우팅 해소.
  const tgtNode = _metaGraph.nodes.get(targetKey);
  if (tgtNode && tgtNode.label && tgtNode.label !== "Table" && tgtNode.label !== "Column") {
    return _metaGraphShowDetail(targetKey);
  }
  // review MINOR: 컬럼 판정은 **node label 우선**(세그먼트≥3 은 3-part fqn 테이블에서 오판 가능) —
  //   모델에 label 이 있으면 그것으로, 없으면(집계 대상 미로드) 세그먼트 수 휴리스틱 폴백.
  const idx = String(targetKey).indexOf(":");
  const segs = idx >= 0 ? String(targetKey).slice(idx + 1).split(".") : [];
  const looksColumn = tgtNode ? (tgtNode.label === "Column") : (segs.length >= 3);
  const tableKey = looksColumn ? (_metaColParent(targetKey, tgtNode && tgtNode.fqn) || targetKey) : targetKey;
  // 1) 대상 테이블을 이웃과 함께 화면에 가져오고 스키마 펼침 + 카메라 이동 (REFERENCES 엣지도 로드).
  await _metaGraphExpand(tableKey);
  // 2) 대상 테이블 컬럼 전개(펼침 전용) — 컬럼까지 추적 가능하게(이웃 응답에 컬럼이 이미 오면 no-op).
  if (!_metaTableHasCols(tableKey)) { try { await _metaGraphToggleColumns(tableKey); } catch (_) { /* graceful */ } }
  // 3) 대상 컬럼 강조 + 카메라 focus (렌더된 경우). 미렌더(컬럼 introspect 불가 등)면 테이블 강조 유지.
  const focusKey = (looksColumn && _metaRenderedIdFor(targetKey)) ? targetKey : tableKey;
  _metaGraphSetSelected(focusKey);
  const seq = _metaGraph._opSeq;
  try { await _metaGraphAnimateFocus(focusKey, seq); } catch (_) { /* graceful */ }
  const nm = (_metaGraph.nodes.get(focusKey) || {}).name || focusKey;
  _metaGraphStatus(`관계 추적 → ${nm} (대상 테이블·컬럼 강조).`);
}

// graphux7(#2): 관계 행 단일 클릭 = 카메라 이동만(상세 패널 유지). 대상이 렌더돼 있으면 그 노드로,
//   접힌 스키마면 그 스키마 카드로 카메라를 팬(+렌더된 경우 선택 강조). 상세 패널은 바꾸지 않는다 — 전환은 더블클릭.
function _metaGraphPanToRelation(targetKey) {
  if (!_metaGraph.graph || !targetKey) return;
  const el = _metaRenderedIdFor(targetKey);   // 렌더 노드, 접힌 스키마면 카드(SC:)
  if (!el) { _metaGraphStatus("대상 노드가 현재 화면에 없습니다 — 더블클릭하면 펼쳐 상세로 전환합니다."); return; }
  if (_metaGraph.renderedIds && _metaGraph.renderedIds.has(targetKey)) _metaGraphSetSelected(targetKey);
  const seq = _metaGraph._opSeq;
  _metaGraphAnimateFocus(targetKey, seq);   // key→렌더 요소(노드/카드) 내부 해소 후 카메라 팬
  const nm = (_metaGraph.nodes.get(targetKey) || {}).name || targetKey;
  _metaGraphStatus(`→ ${nm} 로 카메라 이동 (더블클릭 = 상세 패널 전환).`);
}
// graphux7(#2): 관계 행 클릭 라우팅 — 단일=카메라 이동만, 더블=상세 전환(+대상을 화면에 가져오기).
//   짧은 타이머(260ms)로 단일/더블 구분: 더블클릭이면 예약된 단일(카메라) 취소 후 전환만 실행.
//   키보드(Enter/Space)=상세 전환(commit — 키보드는 '더블' 표현이 어려워 실질 네비게이션을 기본으로).
function _metaGraphBindRelRow(r, key) {
  if (!r || !key) return;
  let timer = null;
  r.addEventListener("click", (ev) => {
    if (ev) ev.stopPropagation();
    if (timer) { clearTimeout(timer); timer = null; }
    timer = setTimeout(() => { timer = null; _metaGraphPanToRelation(key); }, 260);
  });
  r.addEventListener("dblclick", (ev) => {
    if (ev) ev.stopPropagation();
    if (timer) { clearTimeout(timer); timer = null; }
    _metaGraphTraceRelation(key);
  });
  r.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); _metaGraphTraceRelation(key); }
  });
}
// graph-reltrace ②③: 컨테이너 내 `.amgr-trace[data-trace]` 행에 클릭/키보드 바인딩(공용, graphux7#2 단일/더블 라우팅).
function _metaGraphBindTraceRows(el) {
  if (!el) return;
  el.querySelectorAll(".amgr-trace[data-trace]").forEach((r) => {
    _metaGraphBindRelRow(r, r.getAttribute("data-trace"));
  });
}

// graph-reltrace ②③: 노드(테이블이면 자기 컬럼 포함)에 닿는 REFERENCES 관계를 추적 행 HTML 로.
//   edges 미지정 시 모델(_metaGraph.edges)에서 수집(AI 박스용). broken 제외. 반환: {html, count}.
function _metaGraphRelTraceRowsHTML(nodeKey, edges) {
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const nmOf = (k) => { const n = _metaGraph.nodes.get(k); return (n && (n.fqn || n.name)) || String(k).split(".").pop(); };
  const isSelf = (k) => k === nodeKey || _metaColParent(k, (_metaGraph.nodes.get(k) || {}).fqn) === nodeKey;
  const src = edges || Array.from(_metaGraph.edges.values());
  const seen = new Set();
  const rows = [];
  src.forEach((e) => {
    if (!e || e.type !== "REFERENCES" || e.status === "broken") return;
    const sSelf = isSelf(e.source), tSelf = isSelf(e.target);
    if (!sSelf && !tSelf) return;      // self 무관 엣지 제외
    const other = sSelf ? e.target : e.source;
    if (!other || seen.has(other)) return;
    seen.add(other);
    const arrow = sSelf ? "→" : "←";
    rows.push(
      `<li class="amgr-row amgr-trace" data-trace="${esc(other)}" role="button" tabindex="0" ` +
      `title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환(대상 테이블·컬럼 추적)">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span> <code>${esc(nmOf(other))}</code>` +
      `${_metaEdgeTrustBadge(e)} <span class="amgr-tracehint">🔎 추적</span></div></li>`
    );
  });
  return { html: rows.join(""), count: rows.length };
}

// 테이블 단일 클릭 = **자신의 컬럼 인라인 펼침(펼침 전용)**. 이미 펼쳐졌으면 no-op(버그① — 클릭으론 안 접힘).
//   접힘: "−" 컨트롤(_metaGraphCollapse). 그래프 컬럼(HAS_COLUMN) 없으면 information_schema 즉석조회(introspect).
async function _metaGraphToggleColumns(key) {
  if (!_metaGraph.graph || !key) return;
  const node = _metaGraph.nodes.get(key);
  if (!node || node.label !== "Table") return;
  if (_metaTableHasCols(key)) return;   // 이미 펼침 — 클릭으로 접지 않음(접기는 "−" 컨트롤). O(1) 인덱스.
  // graph-perf-bg: 논블로킹 — busy 상태를 먼저 페인트(과거 dead-frozen 구간 제거)한 뒤 무거운 fetch·재구성.
  //   seq 토큰을 await(fetch·yield) 경계마다 대조해 그 사이 다른 조작이 시작됐으면 폐기(stale 렌더 방지).
  const seq = ++_metaGraph._opSeq;
  const nm = node.name || key;
  _metaGraphStatus("컬럼 조회 중…");
  _metaSetBusy(key, true, seq);
  await _metaYieldPaint();
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }   // 폐기 — busy 소유 op 일 때만 해제(후속 op 가 rebuild 없이 끝나도 busy 잔류 방지)
  try {
    let data;
    try { data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`); }
    catch (_) { data = { nodes: [], edges: [] }; }
    if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
    const respHasCols = (data.edges || []).some((e) => e && e.type === "HAS_COLUMN" && e.source === key);
    if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
    let note = "";
    if (!respHasCols && !_metaGraph.introspected.has(key)) {
      try {
        const col = await apiFetch(`/api/admin/metadata/graph/columns?node=${encodeURIComponent(key)}`);
        if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
        if (col && col.introspected && (col.nodes || []).length) {
          _metaGraph.introspected.add(key);
          data.nodes = (data.nodes || []).concat(col.nodes);
          data.edges = (data.edges || []).concat(col.edges || []);
        } else if (col && !col.introspected && col.reason) {
          note = ` (${col.reason})`;
        }
      } catch (_) { /* graceful */ }
    }
    // 이 테이블 소속 컬럼만(이웃 테이블 컬럼 제외).
    const colNodes = (data.nodes || []).filter((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
    _metaGraphIngest(colNodes, []);
    if (colNodes.length > 0) {
      _metaGraph.expanded.add(key);
      await _metaG6Apply(false);   // fit=false — 제자리 펼침(버그② — 카메라 점프·재확산 없음). busy 는 rebuild 로 소멸.
      _metaGraphStatus(`${nm} 컬럼 ${colNodes.length}개 펼침 — "−" 버튼으로 접기`);
    } else {
      _metaSetBusy(key, false, seq);   // rebuild 없는 경로 — busy 직접 해제(소유 op)
      _metaGraphStatus(`${nm} — 펼칠 컬럼 없음${note}`);
    }
  } catch (err) {
    _metaSetBusy(key, false, seq);
    _metaGraphStatus("컬럼 펼침 오류: " + ((err && err.message) || err));
  }
}

// graph-initview: 스키마 카드 → combo 펼침(per-schema lazy 로드). 반환 상태로 후속(클러스터 상세) 게이팅.
//   "expanded"(펼침 완료) | "already"(이미 펼침) | "empty"(테이블 0) | "failed"(로드 실패) | "stale"(세대 폐기) | "blocked".
//   opts.seq: 부모 op(LoadRoots silent) 세대 상속 — 자체 bump 없이 그 세대로 stale 판정.
//   사용자 클릭 경로는 새 op 세대(++_opSeq)로 시작해 in-flight 이전 조작을 폐기(graph-perf-bg 패턴).
async function _metaGraphExpandSchema(key, opts) {
  if (!_metaGraph.graph || !key) return "blocked";
  const silent = !!(opts && opts.silent);
  // 2차 검증 fix(V-B): scope 전환 fetch 대기 중 화면에 남은 이전 scope 카드 클릭 차단 — 현재 scope 소속만 진행.
  const cidx = key.indexOf(":");
  const kscope = cidx >= 0 ? key.slice(0, cidx) : "";
  if (!kscope || kscope !== (adminState.metadata.scopeKey || "")) return "blocked";
  let sn = _metaGraph.nodes.get(key);
  // 1차 리뷰 fix(MAJOR-1): 검색/이웃 자동펼침 combo 는 Schema 노드 없이 만들어질 수 있다(응답이 테이블만
  // 반환) — 접은 뒤 카드 재클릭이 죽지 않게 Schema 노드를 합성 삽입(위 scope 가드 통과 시에만).
  if (!sn) {
    sn = { key, label: "Schema", name: _metaComboName(key), fqn: _metaComboName(key) };
    _metaGraph.nodes.set(key, sn);
  }
  if (sn.label !== "Schema") return "blocked";
  if (_metaGraph.schemaExpanded.has(key)) return "already";   // 클릭으로 접지 않음(접기는 "−")
  if (_metaGraph.schemaLoading.has(key)) return "blocked";    // 1차 리뷰 fix(MINOR-4): 카드 연타 이중 fetch 차단
  const seq = (opts && opts.seq != null) ? opts.seq : ++_metaGraph._opSeq;
  const nm = _metaComboName(key);
  let note = "";
  let freshResp = false;
  if (!_metaGraph.schemaLoaded.has(key)) {
    _metaGraph.schemaLoading.add(key);
    if (!silent) {
      _metaGraphStatus(`${nm}: 테이블 로딩…`);
      _metaSetBusy(key, true, seq);   // 카드(SC:)에 busy 표시 — _metaApplyState 가 렌더드 id 로 매핑
      await _metaYieldPaint();
      if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); _metaGraph.schemaLoading.delete(key); return "stale"; }
    }
    let data;
    try {
      data = await apiFetch(`/api/admin/metadata/graph?scope=${encodeURIComponent(kscope)}&schema=${encodeURIComponent(key)}`);
    } catch (err) {
      _metaGraph.schemaLoading.delete(key);
      _metaSetBusy(key, false, seq);
      if (!silent && seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "스키마 테이블 로드 실패");
      return "failed";
    }
    _metaGraph.schemaLoading.delete(key);
    // 2차 검증 fix(V-A): await 사이 다른 reset/조작이 세대를 올렸으면 이 응답은 stale — ingest 없이 폐기
    // (이전 scope 응답이 새 모델에 병합되는 교차 스코프 오염을 원천 차단).
    if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return "stale"; }
    _metaGraphIngest(data.nodes || [], data.edges || []);
    if (data.truncated) { _metaGraph.schemaTruncated.add(key); note = " · 표시 상한 도달 — 나머지는 검색으로 탐색"; }
    // 1차 리뷰 fix(MINOR-3, 혼합버전): 구 백엔드는 ?schema= 를 몰라 scope_roots(mode!=schema_tables)로 응답 —
    // 이때 loaded 마킹하면 cap 밖 스키마가 영구 펼침 불능. 정식 응답에만 마킹(아래 cnt>0 조건과 결합).
    freshResp = (data.mode === "schema_tables");
  }
  let cnt = 0;
  // graph-funcproc(§18.8 패널 MAJOR): Routine 도 콘텐츠 — 함수·프로시저만 있는 스키마(테이블 0)가
  // '빈 스키마' 로 오판돼 영구 펼침 불능(Routine 도달 불가)이 되지 않게 카운트에 포함.
  _metaGraph.nodes.forEach((x) => { if ((x.label === "Table" || x.label === "Routine") && _metaCatParent(x.key, x.fqn) === key) cnt += 1; });
  // 2차 검증 fix(V-F): 테이블 확보 시에만 loaded 굳힘 — 빈 스키마는 re-sync 후 재클릭이 다시 조회.
  if (freshResp && cnt > 0) _metaGraph.schemaLoaded.add(key);
  if (cnt === 0) {
    _metaSetBusy(key, false, seq);
    if (!silent && seq === _metaGraph._opSeq) _metaGraphStatus(`${nm}: 빈 스키마(표시할 테이블·함수 없음)${note}`);
    return "empty";
  }
  _metaGraph.schemaExpanded.add(key);
  if (silent) return "expanded";   // 호출측(LoadRoots)이 apply+fit — 이중 렌더 방지
  await _metaG6Apply(false);       // 제자리 원칙(ADR-004 ②) — 전체 fit 없이. busy 는 rebuild 로 소멸.
  try { await _metaGraph.graph.focusElement(key, false); } catch (_) {}   // shelf 재배치 대비 시야 고정(무애니)
  _metaGraphStatus(`${nm}: 테이블·함수 ${cnt}개 펼침 — "−" 로 접기, 테이블 클릭=컬럼${note}`);
  return "expanded";
}

// graph-initview: 스키마 combo "−" 접기 — 카드로 복귀(모델 유지, 렌더 게이팅만 해제 → 재펼침 무-refetch).
function _metaGraphCollapseSchema(key) {
  if (!_metaGraph.graph || !key) return;
  if (!_metaGraph.schemaExpanded.has(key)) return;
  _metaGraph.schemaExpanded.delete(key);
  _metaG6Apply(false);
  _metaGraphStatus(`'${_metaComboName(key)}' 스키마를 접었습니다 — 카드를 클릭하면 다시 펼쳐집니다.`);
}

// graph-initview: 카드 클릭 경로용 클러스터 상세 — 방금 lazy 로드된 모델 데이터로 로컬 렌더(추가 fetch 0,
// 상태줄 미접촉 — 펼침 완료 메시지 보존). combo:click 은 기존 API 기반 상세 유지. 2차 검증 fix(V-G):
// cap 절단 스키마는 카드 배지의 실 카운트(table_count)를 총계로 표기해 배지↔패널 모순 제거.
function _metaGraphShowClusterDetailLocal(comboId) {
  if (!comboId) return;
  _metaGraph.lastDetailKey = comboId;
  _metaGraphHistoryRecord(comboId, "cluster");   // §54①: 복원은 Go 가 ById(API+모델 폴백)로 수행.
  const nm = _metaComboName(comboId);
  const tables = [];
  let childCols = 0;
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n);
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  tables.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const snode = _metaGraph.nodes.get(comboId);
  const total = (snode && typeof snode.table_count === "number" && snode.table_count > tables.length)
    ? snode.table_count : null;
  const truncated = _metaGraph.schemaTruncated.has(comboId);
  _metaGraphRenderClusterDetail(nm, nm, tables, tables.length, childCols, total, truncated, comboId);
}

// "−" 컨트롤 접기 — 이 테이블의 컬럼 노드(+containment 엣지) 모델에서 제거 + 재조회 재허용.
//   graph-rel-layout(§18.8 패널 MAJOR): **REFERENCES 는 보존** — 관계 데이터는 배치 순서(_metaRelAdjacency)와
//   접힌 테이블 간 관계 표시(graph-reltrace renderEndpoint 승격)의 입력이라, 접기 제스처가 지우면 (a) 전면
//   재셔플(펼침-불변 계약 위반) (b) 관계선 소실이 재펼침(ToggleColumns 는 엣지 미재조회)으로도 복원 불가.
function _metaGraphCollapse(key) {
  if (!_metaGraph.graph || !key) return;
  const node = _metaGraph.nodes.get(key);
  const nm = (node && node.name) || key;
  const toDel = [];
  _metaGraph.nodes.forEach((n) => { if (n.label === "Column" && _metaColParent(n.key, n.fqn) === key) toDel.push(n.key); });
  if (!toDel.length) return;
  const delSet = new Set(toDel);
  toDel.forEach((k) => _metaGraph.nodes.delete(k));
  _metaGraph.edges.forEach((e, id) => { if (e.type !== "REFERENCES" && (delSet.has(e.source) || delSet.has(e.target))) _metaGraph.edges.delete(id); });
  _metaGraph.expanded.delete(key);
  _metaGraph.colsByTable.delete(key);   // graph-perf-bg: 컬럼 전부 제거 → 인덱스 카운트 해제(O(1) hasCols 정합).
  if (_metaGraph.introspected) _metaGraph.introspected.delete(key);
  _metaG6Apply(false);
  _metaGraphStatus(`'${nm}' 테이블 컬럼을 접었습니다 — 테이블을 클릭하면 다시 펼쳐집니다.`);
}

// 더블 클릭: 이웃(관계) 그래프로 확장. depth=N-hop 이웃을 모델에 병합.
//   depthOverride: 컨텍스트 메뉴 hop chip 의 1회성 깊이 — 툴바 select 는 건드리지 않는다(review).
async function _metaGraphExpand(key, depthOverride) {
  if (!_metaGraph.graph || !key) return;
  _metaGraph.lastDetailKey = key;
  const depthSel = document.getElementById("metadataGraphDepth");
  const depth = depthOverride || (depthSel ? depthSel.value : "2");
  // graph-perf-bg: 논블로킹 — busy 페인트 후 무거운 이웃 조회·재구성. seq 토큰으로 stale 폐기.
  const seq = ++_metaGraph._opSeq;
  _metaGraphStatus("이웃 조회 중…");
  _metaSetBusy(key, true, seq);
  // graph-dblclick-latency: 앵커는 이미 렌더돼 있으므로 카메라 팬을 fetch·rebuild 를 기다리지 않고 **즉시** 시작(fire-and-forget).
  //   적응형 follow 라 재빌드로 앵커가 이동해도 최종 위치로 수렴 — 더블클릭↔팬 시작 사이의 ~350ms 텀 제거. seq 로 폐기.
  _metaGraphAnimateFocus(key, seq);
  await _metaYieldPaint();
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=${encodeURIComponent(depth)}`);
  } catch (err) {
    _metaSetBusy(key, false, seq);
    _metaGraphStatus((err && err.message) || "이웃 조회 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
  // 미분석 테이블은 그래프에 컬럼(HAS_COLUMN)이 없어 즉석조회(introspect) 병합.
  let introspectNote = "";
  const selfNode = (data.nodes || []).find((x) => x.key === key);
  const respHasCols = (data.edges || []).some((e) => e && e.type === "HAS_COLUMN" && e.source === key);
  if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
  const anchorHasCols = _metaTableHasCols(key);
  if (selfNode && selfNode.label === "Table" && !respHasCols && !anchorHasCols && !_metaGraph.introspected.has(key)) {
    try {
      const col = await apiFetch(`/api/admin/metadata/graph/columns?node=${encodeURIComponent(key)}`);
      if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
      if (col && col.introspected && (col.nodes || []).length) {
        _metaGraph.introspected.add(key);
        data.nodes = (data.nodes || []).concat(col.nodes);
        data.edges = (data.edges || []).concat(col.edges || []);
        introspectNote = ` · 컬럼 ${col.nodes.length}개 즉석조회(introspect)`;
      } else if (col && !col.introspected && col.reason) {
        introspectNote = ` · 컬럼 없음: ${col.reason}`;
      }
    } catch (_) { /* graceful */ }
  }
  _metaGraph.mode = "neighbor";
  _metaGraph.lastQuery = "";
  _metaGraph.nodes.forEach((n) => { delete n.rel; });   // 이웃 탐색 진입 — 검색 유사도 크기 해제
  _metaGraphIngest(data.nodes || [], data.edges || []);
  // graph-initview: 이웃 응답 테이블/컬럼/함수의 스키마 자동 펼침(카드 게이팅에서 이웃이 숨지 않게) + 앵커 스키마.
  //   graph-funcproc(§18.8 패널 MINOR): Routine 포함 — 접힌 타 스키마의 Routine 이웃·ROUTINE_USES 엣지 비가시 방지.
  (data.nodes || []).forEach((nd) => {
    if (nd && (nd.label === "Table" || nd.label === "Column" || nd.label === "Routine")) {
      const sc = _metaCatParent(nd.key, nd.fqn);
      if (sc) _metaGraph.schemaExpanded.add(sc);
    }
  });
  {
    const an = _metaGraph.nodes.get(key);
    if (an) {
      const sc = _metaSchemaComboOf(an);
      if (sc && sc !== _META_TERMS_COMBO) _metaGraph.schemaExpanded.add(sc);
    }
  }
  const anchorCols = (data.nodes || []).some((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
  if (anchorCols) _metaGraph.expanded.add(key);
  // graph-initview(A3): 이웃 확장은 전체-fit 대신 앵커 중심 focus. graph-dblclick-cam2: manual rAF tween 으로 부드럽게.
  //   graph-dblclick-latency: 그 tween 을 위(busy 직후)에서 이미 fire-and-forget 으로 시작함 — 적응형 follow 라 이 rebuild 로
  //   앵커가 이동해도 자동 수렴. 여기서 재호출 불필요(중복 tween 방지).
  await _metaG6Apply(false);   // busy 는 rebuild 로 소멸 (진행 중인 follow tween 이 새 위치로 이어서 수렴)
  // graph-rel-layout(§18.8 패널 MINOR): fetch(이웃+introspect) 합계가 tween MAXMS(1.2s)를 넘으면 follow tween 이
  //   앵커 '구 위치'에 수렴·종료한 뒤 rebuild 가 일어난다 — 관계 재배치로 앵커가 다른 shelf 행으로 원거리 이동
  //   가능하므로, tween 이 이미 죽었으면 무애니 focusElement 1회로 시야 보정(살아 있으면 adaptive follow 가 수렴).
  if (_metaGraph._focusLive !== seq) {
    try { const fel = _metaRenderedIdFor(key); if (fel) await _metaGraph.graph.focusElement(fel, false); } catch (_) {}
  }
  _metaGraphSyncAnalysisMarkers(key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  _metaGraphSetSelected(key);
  const self = selfNode || { key, name: key };
  _metaGraphHistoryRecord(key, "node");   // §54①: seq 가드 뒤 성공-기반 기록(실패/스테일 확장 미기록).
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  _metaGraphStatus(`노드 ${(data.nodes || []).length} · 관계 ${(data.edges || []).length}${introspectNote}`);
}

// graph-ctxmenu: "이 노드 중심으로 보기" — 모델을 리셋하고 앵커의 N-hop 이웃만 남긴다.
//   expand(기존 화면에 병합·누적)와 달리 화면을 앵커 중심 서브그래프로 정리해, 스키마를 모르는
//   사용자가 관심 노드의 연관 관계만 집중해 보게 한다. 분석 마커는 서버 상태에서 재적용.
async function _metaGraphFocus(key) {
  _metaGraph._searchBase = null;   // §54③ 재검증 MINOR: 중심 보기 = 새 컨텍스트 — stale 검색 base 폐기
  if (!_metaGraph.graph || !key) return;
  const depthSel = document.getElementById("metadataGraphDepth");
  const depth = depthSel ? depthSel.value : "2";
  _metaGraph.mode = "neighbor";
  _metaGraph.lastQuery = "";
  _metaGraph.lastDetailKey = key;
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";   // review: 검색어 잔존 시 focus 서브그래프와 상태 불일치
  // graph-perf-bg 규약 정합: reset 경로는 resetModel(_opSeq 증가) 직후 세대 캡처 → await 후 대조.
  //   fetch 를 reset 앞에 두면 fetch 동안 발생한 다른 reset 화면을 이 continuation 이 되돌린다(stale-render).
  _metaGraphResetModel();
  const seq = _metaGraph._opSeq;
  _metaGraphStatus("중심 보기 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=${encodeURIComponent(depth)}`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "중심 보기 조회 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) return;   // await 사이 다른 reset(loadRoots/search/scope) — stale 폐기
  _metaGraphIngest(data.nodes || [], data.edges || []);
  const anchorCols = (data.nodes || []).some((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
  if (anchorCols) _metaGraph.expanded.add(key);
  await _metaG6Apply(true);
  _metaGraphSyncAnalysisMarkers(key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  _metaGraphSetSelected(key);
  const self = (data.nodes || []).find((x) => x.key === key) || { key, name: key };
  _metaGraphHistoryRecord(key, "node");   // §54①: seq 가드 뒤 성공-기반 기록(중심보기).
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  const nm = (_metaGraph.nodes.get(key) || {}).name || key;
  _metaGraphFocusChip(nm);   // review MAJOR-3: 부분 그래프임을 지속 표시 + '전체 보기' 복귀
  _metaGraphStatus(`${nm} 중심 ${depth}-hop — 노드 ${(data.nodes || []).length} · 관계 ${(data.edges || []).length} ('전체 보기'로 복귀)`);
}

// review MAJOR-3: 중심 보기 지속 표시 칩 — 캔버스 좌상단에 "🎯 중심 보기: <노드>" + "✕ 전체 보기"(roots 복귀).
//   name=null 이면 제거. roots 로드·검색 진입 시 자동 해제(전체/검색 컨텍스트로 전환됨).
function _metaGraphFocusChip(name) {
  _metaGraph._focusName = name || null;   // §54③ 패널: 중심 보기 상태 미러(검색→클리어 시 칩 복원용)
  const canvas = document.getElementById("metadataGraphCanvas");
  if (!canvas) return;
  let chip = document.getElementById("metaGraphFocusChip");
  if (!name) { if (chip) chip.remove(); return; }
  if (!chip) {
    chip = document.createElement("div");
    chip.id = "metaGraphFocusChip";
    chip.className = "amgr-focus-chip";
    canvas.appendChild(chip);
  }
  chip.replaceChildren();
  const t = document.createElement("span");
  t.textContent = `🎯 중심 보기: ${name}`;
  chip.appendChild(t);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "✕ 전체 보기";
  btn.title = "중심 보기를 끝내고 데이터소스 전체 그래프로 복귀합니다";
  btn.addEventListener("click", () => _metaGraphLoadRoots());
  chip.appendChild(btn);
}

// feature-0016 ERD-card: Column 의 소속 Table (scope:...fqn 에서 마지막 세그먼트 제거). 미상 시 null.
function _metaColParent(key, fqn) {
  if (!key) return null;
  const idx = key.indexOf(":");
  if (idx < 0) return null;
  const scope = key.slice(0, idx);
  const f = fqn || key.slice(idx + 1);
  if (!f) return null;
  const parts = f.split(".");
  if (parts.length < 2) return null;      // 최소 table.column
  return scope + ":" + parts.slice(0, -1).join(".");   // 마지막(컬럼) 세그먼트 제거 → 테이블 fqn
}

// reltrace-tabledetail(review): 모델에 없는 관계 끝점(컬럼)의 표시용 노드 파생 — scope 접두 제거한 fqn +
//   leaf 명. schema_tables 는 REFERENCES 끝점 Column 노드를 nodes 에 싣지 않아, 모델-병합 관계행이
//   raw scoped key(`scope:db.t.c`)로 뜨던 UX 저하를 해소(테이블-레벨/컬럼-레벨 읽기 쉬운 이름).
function _metaKeyDisplayNode(key) {
  const s = String(key || "");
  const idx = s.indexOf(":");
  const fqn = idx >= 0 ? s.slice(idx + 1) : s;
  const segs = fqn.split(".");
  const label = segs.length >= 3 ? "Column" : (segs.length === 2 ? "Table" : "Schema");
  return { key, label, fqn, name: segs[segs.length - 1] || fqn };
}

// API nodes/edges → 모델(_metaGraph.nodes/edges Map) 병합. 반환: 새로 추가된 노드 key 배열.
//   HAS_TABLE/HAS_COLUMN 은 containment(컬럼 fqn 으로 부모 도출)라 엣지로 저장하지 않는다.
function _metaGraphIngest(nodes, edges) {
  const added = [];
  (nodes || []).forEach((n) => {
    if (!n || !n.key) return;
    if (n.label === "Schema") {
      const ex = _metaGraph.nodes.get(n.key);
      if (!ex) {
        _metaGraph.nodes.set(n.key, { key: n.key, label: "Schema", name: n.name || n.fqn || n.key, fqn: n.fqn || "",
          table_count: (typeof n.table_count === "number") ? n.table_count : null });
        added.push(n.key);   // §54③ 패널 MAJOR: 카드 미반환 시 searchAdded 가 항상 비어 pristine 회수가 dead code
      } else if (typeof n.table_count === "number") { ex.table_count = n.table_count; }   // graph-initview: 카드 배지
      return;
    }
    const ord = (typeof n.ordinal === "number" && isFinite(n.ordinal)) ? n.ordinal : null;
    const existing = _metaGraph.nodes.get(n.key);
    const rec = existing || { key: n.key };
    rec.label = n.label || rec.label || "Node";
    rec.name = n.name || n.fqn || rec.name || n.key;
    rec.fqn = n.fqn || rec.fqn || "";
    rec.description = (n.description != null) ? n.description : (rec.description || "");
    rec.source = n.source || rec.source || "";
    if (ord != null) rec.ordinal = ord;
    if (typeof n.score === "number") rec.score = n.score;
    // graph-funcproc(ADR-016): 함수·프로시저 속성 보존(칩 접두 ƒ/⚙ + 상세 파라미터 표시).
    if (n.routine_type) rec.routine_type = n.routine_type;
    if (n.params != null && n.params !== "") rec.params = n.params;
    // graph-product-cat(§43): Product/Datasource 부가 필드 보존(제품 라벨 개수 · datasource scope drill).
    if (n.scope_key != null) rec.scope_key = n.scope_key;
    if (typeof n.datasource_count === "number") rec.datasource_count = n.datasource_count;
    // Phase C(semantic-embed): 의미 클러스터 id/라벨 보존 → _metaSimGroups 가 be: 그룹으로 소비(affix 폴백).
    if (n.cluster_id != null) rec.cluster_id = n.cluster_id;
    if (n.cluster_label != null) rec.cluster_label = n.cluster_label;
    if (!existing) {
      _metaGraph.nodes.set(n.key, rec); added.push(n.key);
      // graph-perf-bg: 새 Column 노드면 소속 테이블의 colsByTable 카운트 증가(_metaTableHasCols O(1) 단일소스).
      if (rec.label === "Column") {
        const tk = _metaColParent(rec.key, rec.fqn);
        if (tk) _metaGraph.colsByTable.set(tk, (_metaGraph.colsByTable.get(tk) || 0) + 1);
      }
    }
  });
  (edges || []).forEach((e) => {
    if (!e || !e.source || !e.target) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_ROUTINE") return;   // containment
    const id = `${e.source}|${e.type}|${e.target}`;
    if (_metaGraph.edges.has(id)) return;
    _metaGraph.edges.set(id, { id, source: e.source, target: e.target, type: e.type || "",
      status: e.status || "", edge_source: e.edge_source || "",
      cardinality: e.cardinality || "",   // reltrace-tabledetail(review): 모델-병합 관계행의 [cardinality] 배지 보존
      relation_type: e.relation_type || "",   // graph-funcproc: ROUTINE_USES read/write(+유사어 관계형)
      cross_ds: (e.cross_ds != null && e.cross_ds !== "") ? 1 : 0,   // crossds-rel: 교차DB 엣지 표식(빌드 스타일/배지)
      weight: (e.weight != null && e.weight !== "") ? Number(e.weight) : "" });
  });
  return added;
}

// 컬럼 정렬 비교자(모델 객체): ordinal 숫자 우선(미상=MAX), 동률 name.
function _metaGraphColCmp(a, b) {
  const na = (typeof a.ordinal === "number" && isFinite(a.ordinal)) ? a.ordinal : Number.MAX_SAFE_INTEGER;
  const nb = (typeof b.ordinal === "number" && isFinite(b.ordinal)) ? b.ordinal : Number.MAX_SAFE_INTEGER;
  if (na !== nb) return na - nb;
  return String(a.name || "").localeCompare(String(b.name || ""));
}

function _metaGraphRenderDetailEmpty() {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  el.innerHTML = '<div class="admin-detail-empty"><p>검색 후 노드를 클릭하면 해당 항목의 <strong>설명·컬럼·관계·연관 용어</strong>를 한 곳에서 봅니다.</p><p class="admin-meta-detail-note">노드를 <strong>우클릭</strong>하면 상세 보기·관계 상세·관계 확장(1~3-hop)·중심 보기 등 상호작용 메뉴가 열립니다.</p></div>';
}

// feature-0016: 관계 엣지의 신뢰 상태 배지 — FK 는 무표시, 추정(candidate)/신뢰(trusted) 구분.
// "이 연결이 정말 올바른지" 를 사람이 한눈에 판단하도록 weight 를 함께 노출.
function _metaEdgeTrustBadge(e) {
  if (!e || e.edge_source === "fk_introspect") return "";
  const w = (e.weight != null && e.weight !== "") ? Number(e.weight) : null;
  const ws = (w != null && !isNaN(w)) ? " w=" + w.toFixed(2) : "";
  if (e.status === "candidate") {
    return ` <span class="admin-meta-graph-trust admin-meta-graph-trust-candidate" title="검증 전 추정 관계 — 사용/프로브로 강화·감쇠">추정${ws}</span>`;
  }
  if (e.status === "trusted") {
    return ` <span class="admin-meta-graph-trust admin-meta-graph-trust-trusted" title="검증된 신뢰 관계">신뢰${ws}</span>`;
  }
  return "";
}

// reldetail-colexpand ④: 관계 hover 툴팁용 **의미 분석** 텍스트(즉시 조합 — LLM 지연 없음).
//   방향(참조함/참조받음)·연결 컬럼·근거(대화학습/FK/추정)·신뢰도를 해석해 "이 관계가 무엇을
//   뜻하는지" 를 문장으로 설명한다. dir: "out"(self 가 상대를 참조) | "in"(상대가 self 를 참조).
//   selfEndFqn/otherFqn 은 표시용 fqn(scope 접두 제거). native title 속성값으로 쓰여 다중 줄로 표시.
function _metaRelSemanticTip(e, dir, selfEndFqn, otherFqn) {
  const src = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "미상";
  const w = (e.weight != null && e.weight !== "") ? Number(e.weight) : null;
  const wPct = (w != null && !isNaN(w)) ? Math.round(w * 100) + "%" : null;
  const trust = e.status === "trusted"
    ? "검증된 신뢰 관계"
    : (e.status === "candidate"
        ? ("추정 관계" + (wPct ? " (신뢰도 " + wPct + " — 실사용·프로브로 강화·감쇠)" : ""))
        : (e.edge_source === "fk_introspect" ? "FK 스키마 선언 관계" : "관계"));
  // 방향 문장: 물리적 참조 방향을 자연어로.
  const arrowSent = dir === "out"
    ? (selfEndFqn + " 이(가) " + otherFqn + " 을(를) 참조합니다.")
    : (otherFqn + " 이(가) " + selfEndFqn + " 을(를) 참조합니다.");
  // 근거별 의미 해석.
  const meaningBy = {
    fk_introspect: "데이터베이스에 선언된 외래키(FK)로, 두 테이블 행이 이 컬럼으로 확정 연결됩니다.",
    conversation: "사용자 대화의 실제 JOIN 질의에서 학습된 연결 — 실무에서 함께 조회되는 관계입니다.",
    inferred: "컬럼 명명 규칙으로 추론된 암묵 관계 — 실데이터 겹침 프로브로 신뢰도가 조정됩니다.",
    llm_insight: "AI 인사이트가 제안한 연관 관계입니다.",
    manual: "관리자가 수동 등록한 관계입니다.",
  };
  const meaning = meaningBy[e.edge_source] || "두 컬럼이 연관됩니다.";
  const card = e.cardinality ? ("\n관계 형태(cardinality): " + e.cardinality) : "";
  return "관계 의미 분석\n" + arrowSent + "\n근거: " + src + " · " + trust + card + "\n" + meaning;
}

// 통합 엔티티 카드 — 클릭 노드의 이웃을 카테고리(컬럼·관계·용어)로 묶어 표시.
function _metaGraphRenderDetail(self, nodes, edges) {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  // 항목1: 이 노드가 검색 결과라 그래프에 rel(유사도)이 실려 있으면 상세 헤더에 % 명시.
  const selfScopeKey = (self.key && self.key.indexOf(":") >= 0)
    ? self.key.slice(0, self.key.indexOf(":")) : (adminState.metadata.scopeKey || "common");
  let relPct = null;
  try {
    const gn = _metaGraph.nodes.get(self.key);
    // 검색 컨텍스트(lastQuery 활성)일 때만 유사도 배지 — 확장/리셋 후 stale 배지 방지.
    if (_metaGraph.lastQuery && gn && typeof gn.rel === "number") relPct = Math.round(gn.rel * 100);
  } catch (_) {}
  const byKey = {};
  (nodes || []).forEach((n) => { if (n && n.key) byKey[n.key] = n; });
  // counter 노드명: fetch(byKey) → 모델(_metaGraph.nodes) → key 파생(scope 접두 제거 fqn) 순 폴백.
  //   raw scoped key 노출 방지(review LOW) — 모델에 없는 병합 끝점도 읽기 쉬운 fqn 으로 표시.
  const nm = (k) => (byKey[k] && (byKey[k].fqn || byKey[k].name)) || ((_metaGraph.nodes.get(k) || {}).fqn) || ((_metaGraph.nodes.get(k) || {}).name) || _metaKeyDisplayNode(k).fqn || k;
  const selfKey = self.key;
  // 컬럼(HAS_COLUMN out), 관계(REFERENCES), 용어(GlossaryTerm), 부모 스키마(HAS_TABLE in)
  const columns = [], refs = [], terms = [], routineUses = [];
  const refSeen = new Set();
  (edges || []).forEach((e) => {
    if (!e) return;
    if (e.type === "HAS_COLUMN" && e.source === selfKey && byKey[e.target]) columns.push(byKey[e.target]);
    if (e.type === "REFERENCES") { refs.push(e); refSeen.add((e.source || "") + "|" + (e.target || "")); }
    if (e.type === "DESCRIBES" && byKey[e.source] && byKey[e.source].label === "GlossaryTerm") terms.push(byKey[e.source]);
    // graph-funcproc(ADR-016): 함수·프로시저 ↔ 테이블 사용 관계 — Routine self=사용 테이블 / Table self=사용 루틴.
    if (e.type === "ROUTINE_USES" && (e.source === selfKey || e.target === selfKey)) routineUses.push(e);
  });
  (nodes || []).forEach((n) => { if (n && n.label === "GlossaryTerm" && n.key !== selfKey && !terms.includes(n)) terms.push(n); });
  // graph-reltrace(tabledetail): 테이블 단일클릭 상세는 depth=1 이라 컬럼의 REFERENCES(테이블 기준
  //   2-hop)가 fetch 에 없어 "관계" 섹션이 비었다. 관계는 스키마 펼침 시 이미 모델(_metaGraph.edges)에
  //   로드돼 있으므로, self(테이블이면 자기 컬럼 포함)에 닿는 REFERENCES 를 모델에서 병합한다(dedup).
  //   컬럼 단일클릭(depth=1 에 REFERENCES 있음)은 fetch 로 이미 채워지고 여기서 dedup 로 중복 방지.
  {
    const isSelfEnd = (k) => k === selfKey || _metaColParent(k, (byKey[k] || {}).fqn || (_metaGraph.nodes.get(k) || {}).fqn) === selfKey;
    _metaGraph.edges.forEach((e) => {
      if (!e || e.type !== "REFERENCES" || e.status === "broken") return;
      if (!isSelfEnd(e.source) && !isSelfEnd(e.target)) return;
      const id = (e.source || "") + "|" + (e.target || "");
      if (refSeen.has(id)) return;
      refSeen.add(id); refs.push(e);
    });
  }

  // graph-reltrace(review MAJOR): 관계 행 data-trace 속성값(노드 키)에 쓰이므로 따옴표까지 이스케이프
  //   (DB 식별자에 인용부호 가능 — 속성 탈출 방어. sibling _metaGraphRelTraceRowsHTML 와 parity).
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || self.key)}</strong>${relPct != null ? ` <span class="admin-meta-graph-relbadge" title="검색어 유사도(pg_trgm)">유사도 ${relPct}%</span>` : ""} <button type="button" class="amgr-link" id="metaGraphRelBtn" title="이 노드의 관계를 방향·신뢰도·근거별로 자세히 봅니다 (노드 우클릭 메뉴에서도 열림)">🔗 관계 상세</button></div>`);
  if (self.fqn) parts.push(`<div class="admin-meta-graph-fqn">${esc(self.fqn)}</div>`);
  if (self.description) parts.push(`<p class="admin-meta-graph-desc">${esc(self.description)}</p>`);
  else parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">(설명 없음 — 해당 서브탭에서 추가)</p>`);
  // graph-funcproc(ADR-016): 함수·프로시저 상세 — 유형 + introspect 된 파라미터 시그니처.
  //   graph-navfilter(§54⑤): 파라미터를 수평 한 줄 대신 **수직 목록**으로(컬럼 리스트 amgr-collist 관례 재사용).
  if (self.label === "Routine") {
    const mn = _metaGraph.nodes.get(selfKey) || {};
    const rt = self.routine_type || mn.routine_type || "";
    const rparams = self.params || mn.params || "";
    const plist = _metaRoutineParamList({ params: rparams });
    parts.push(`<div class="admin-meta-graph-sec"><h4>${_metaRoutineIcon(rt)} ${esc(_metaRoutineKo(rt))} · 파라미터 (${plist.length})</h4>` +
      (plist.length
        ? `<ul class="amgr-collist">${plist.map((p) => `<li class="amgr-col amgr-col-plain"><code>${esc(p)}</code></li>`).join("")}</ul>`
        : `<p class="admin-meta-graph-desc admin-meta-graph-muted">파라미터 없음</p>`) + `</div>`);
  }
  // reldetail-colexpand ①②③: 관계를 **소속 컬럼별**로 그룹화하고, 각 컬럼 안에서 참조함(→)/참조받음(←)
  //   을 분리·개수 표기. 관계 있는 컬럼은 아코디언(클릭 시 펼침)으로 관계 행을 노출한다.
  //   self 측 끝점(테이블이면 자기 컬럼, 컬럼이면 자신)을 기준으로 방향을 정한다.
  const selfIsColumn = (self.label === "Column");
  const selfColKey = (k) => {   // 엣지 끝점 k 가 self 소속이면 그 self측 컬럼 키, 아니면 null
    if (selfIsColumn) return (k === selfKey) ? selfKey : null;
    // 테이블 self: 끝점이 self 테이블의 컬럼이면 그 컬럼 키.
    if (k === selfKey) return null;   // 테이블 자신은 컬럼 아님(REFERENCES 끝점은 항상 컬럼)
    return (_metaColParent(k, (byKey[k] || {}).fqn || (_metaGraph.nodes.get(k) || {}).fqn) === selfKey) ? k : null;
  };
  // colKey -> { out:[{e,other}], in:[{e,other}] }
  const colRel = new Map();
  let totOut = 0, totIn = 0;
  const addRel = (colKey, dir, e, other) => {
    if (!colRel.has(colKey)) colRel.set(colKey, { out: [], in: [] });
    colRel.get(colKey)[dir].push({ e, other });
    if (dir === "out") totOut += 1; else totIn += 1;
  };
  refs.forEach((e) => {
    const sc = selfColKey(e.source), tc = selfColKey(e.target);
    // review MAJOR: intra-table self-FK(양끝이 모두 self 컬럼, 예: employees.manager_id→employees.id)는
    //   source 컬럼의 참조함(→)과 target 컬럼의 참조받음(←)을 **둘 다** 기록해야 방향별 개수가 정확하다
    //   (else-if 로 out 만 잡으면 참조받음이 누락·totIn 저계상). sc===tc(컬럼 자기참조)면 out 만(중복 방지).
    if (sc) addRel(sc, "out", e, e.target);        // self 컬럼이 source → 참조함
    if (tc && tc !== sc) addRel(tc, "in", e, e.source);   // self 컬럼이 target → 참조받음
    // sc·tc 모두 falsy = self 무관(모델 병합 방어) → 무시.
  });

  const relRow = (item, dir) => {   // 추적 가능 관계 행(툴팁 = 의미 분석)
    const { e, other } = item;
    const arrow = dir === "out" ? "→" : "←";
    const selfEndFqn = dir === "out" ? nm(e.source) : nm(e.target);
    const otherFqn = nm(other);
    const tip = _metaRelSemanticTip(e, dir, selfEndFqn, otherFqn);
    return `<li class="amgr-row amgr-trace" data-trace="${esc(other)}" role="button" tabindex="0" ` +
      `title="${esc(tip)}">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span> <code>${esc(otherFqn)}</code>` +
      `${e.cardinality ? " [" + esc(e.cardinality) + "]" : ""}` +
      `${e.edge_source && e.edge_source !== "fk_introspect" ? " <span class=\"admin-meta-graph-muted\">(" + esc(_META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source) + ")</span>" : ""}` +
      `${_metaEdgeTrustBadge(e)} <span class="amgr-tracehint">🔎 추적</span></div></li>`;
  };
  const dirGroup = (list, dir) => {   // 방향 그룹(참조함/참조받음) + 개수
    if (!list.length) return "";
    const label = dir === "out" ? "참조함" : "참조받음";
    const arrow = dir === "out" ? "→" : "←";
    return `<div class="amgr-dir"><div class="amgr-dir-head"><span class="amgr-arrow">${arrow}</span> ${label} (${list.length})</div>` +
      `<ul class="amgr-list">${list.map((it) => relRow(it, dir)).join("")}</ul></div>`;
  };

  if (columns.length || selfIsColumn) {
    // 전체 관계 요약(방향별 개수).
    const relSummary = (totOut + totIn) > 0
      ? ` <span class="admin-meta-graph-relbadge" title="이 노드의 관계 방향별 개수">관계 ${totOut + totIn} · 참조함 ${totOut} · 참조받음 ${totIn}</span>`
      : "";
    if (selfIsColumn) {
      // 컬럼 상세: 컬럼 자신의 관계를 방향별로 바로 표시(아코디언 불필요).
      const cr = colRel.get(selfKey) || { out: [], in: [] };
      parts.push(`<div class="admin-meta-graph-sec"><h4>관계${relSummary}</h4>`);
      if (cr.out.length || cr.in.length) {
        parts.push(`<p class="admin-meta-detail-note">행 hover 시 관계 의미, 클릭 시 대상 추적.</p>`);
        parts.push(dirGroup(cr.out, "out"));
        parts.push(dirGroup(cr.in, "in"));
      } else {
        parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다.</p>`);
      }
      parts.push(`</div>`);
    } else {
      // 테이블 상세: 컬럼 목록 — 관계 있는 컬럼은 아코디언(클릭 펼침).
      parts.push(`<div class="admin-meta-graph-sec"><h4>컬럼 (${columns.length})${relSummary}</h4>`);
      parts.push(`<p class="admin-meta-detail-note">관계가 있는 컬럼(🔗)을 클릭하면 참조함/참조받음 관계가 펼쳐집니다. 관계 hover=의미, 클릭=대상 추적.</p><ul class="amgr-collist">`);
      columns.slice(0, 80).forEach((c) => {
        const cr = colRel.get(c.key);
        const nOut = cr ? cr.out.length : 0, nIn = cr ? cr.in.length : 0;
        if (!cr || (nOut + nIn) === 0) {
          parts.push(`<li class="amgr-col amgr-col-plain"><code>${esc(c.name)}</code>${c.description ? " <span class=\"admin-meta-graph-muted\">— " + esc(c.description) + "</span>" : ""}</li>`);
          return;
        }
        parts.push(
          `<li class="amgr-col amgr-col-rel">` +
          `<button type="button" class="amgr-col-toggle" aria-expanded="false" data-colrel="${esc(c.key)}">` +
          `<span class="amgr-caret">▸</span> 🔗 <code>${esc(c.name)}</code>` +
          `<span class="amgr-col-relcount" title="참조함 ${nOut} · 참조받음 ${nIn}">→${nOut} ←${nIn}</span></button>` +
          `<div class="amgr-col-body" data-colbody="${esc(c.key)}" hidden>${dirGroup(cr.out, "out")}${dirGroup(cr.in, "in")}</div>` +
          `</li>`
        );
      });
      parts.push(`</ul></div>`);
    }
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul>`);
    terms.slice(0, 30).forEach((t) => parts.push(`<li><strong>${esc(t.name)}</strong>${t.description ? " — " + esc(t.description) : ""}</li>`));
    parts.push(`</ul></div>`);
  }
  // graph-funcproc(ADR-016): ROUTINE_USES — Routine 상세엔 "사용 테이블", Table 상세엔 "사용하는 함수·프로시저".
  if (routineUses.length) {
    const isRoutineSelf = self.label === "Routine";
    parts.push(`<div class="admin-meta-graph-sec"><h4>${isRoutineSelf ? "사용 테이블" : "사용하는 함수·프로시저"} (${routineUses.length})</h4><ul class="amgr-list">`);
    routineUses.slice(0, 30).forEach((e) => {
      const other = e.source === selfKey ? e.target : e.source;
      const on = byKey[other] || _metaGraph.nodes.get(other) || {};
      const disp = on.label === "Routine"
        ? `${_metaRoutineIcon(on.routine_type)} ${on.name || nm(other)}` : nm(other);
      const kindKo = (e.relation_type === "write") ? "쓰기" : "읽기";
      parts.push(`<li><button type="button" class="amgr-link" data-rtuse="${esc(other)}" title="상세 보기">${esc(disp)}</button> <span class="admin-meta-graph-muted">${kindKo}</span></li>`);
    });
    parts.push(`</ul></div>`);
  }
  // 항목2: AI 능동 분석 섹션 — 버튼으로 트리거(백그라운드 재귀), box 에 진행/결과 렌더.
  //   graph-funcproc(ADR-017, REQ ⑤): 버튼 hover 시 지침 입력 popover(툴팁형) — 입력하면 LLM 이
  //   자율 판단해 분석에 반영. 입력 없이 클릭하면 기존과 동일(지침 없는 분석).
  parts.push(`<div class="admin-meta-graph-sec admin-meta-graph-ai" id="metaGraphAiSec">`);
  parts.push(`<div class="admin-meta-graph-ai-head"><h4>AI 능동 분석</h4><button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiBtn" title="hover: 분석 지침 입력">✨ 능동 분석</button></div>`);
  parts.push(`<div class="admin-meta-ai-pop" id="metaGraphAiPop" hidden>` +
    `<label for="metaGraphAiPrompt">분석 지침 (선택, ≤400자)</label>` +
    `<textarea id="metaGraphAiPrompt" rows="2" maxlength="400" placeholder="예: 결제 흐름 관점에서 연관 테이블 위주로 분석"></textarea>` +
    `<div class="admin-meta-ai-pop-foot"><span class="admin-meta-graph-muted">지침은 AI가 자율 판단해 분석 내용·탐색 방향에 반영합니다.</span>` +
    `<button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiPopGo">✨ 분석 시작</button></div></div>`);
  parts.push(`<div class="admin-meta-graph-ai-box" id="metaGraphAiBox"><span class="admin-meta-graph-muted">이 노드에서 시작해 관련 노드를 AI가 재귀적으로 분석합니다(백그라운드).</span></div>`);
  parts.push(`</div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // 버튼 바인딩(+hover 지침 popover) + 기존 분석 결과가 있으면 즉시 로드.
  _metaGraphBindAiPopover(self.key, selfScopeKey);
  const relBtn = document.getElementById("metaGraphRelBtn");
  if (relBtn) relBtn.addEventListener("click", () => _metaGraphShowRelations(self.key));
  // graph-funcproc: 사용 테이블/사용 루틴 행 클릭 → 대상 상세로 이동.
  el.querySelectorAll("[data-rtuse]").forEach((btn) => {
    btn.addEventListener("click", () => { const k = btn.getAttribute("data-rtuse"); if (k) _metaGraphShowDetail(k); });
  });
  _metaGraphBindTraceRows(el);   // graph-reltrace ②: 관계 행 클릭 → 대상 추적
  // reldetail-colexpand ①: 컬럼 아코디언 토글 — 클릭 시 그 컬럼의 관계 펼침/접힘.
  //   body 는 버튼의 형제(같은 li 내 .amgr-col-body)로 찾는다(키의 CSS 특수문자 셀렉터 이스케이프 회피).
  el.querySelectorAll(".amgr-col-toggle[data-colrel]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const li = btn.closest(".amgr-col-rel");
      const body = li ? li.querySelector(".amgr-col-body") : null;
      const open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      const caret = btn.querySelector(".amgr-caret");
      if (caret) caret.textContent = open ? "▸" : "▾";
      if (body) body.hidden = open;
    });
  });
  _metaGraphLoadNodeAnalysis(self.key);
}

// graph-ctxmenu: 관계 근거(edge_source)·타입 한글 라벨 — 스키마 미숙지 사용자용 신뢰 판단 보조.
const _META_EDGE_SOURCE_KO = {
  fk_introspect: "FK 스키마 선언", inferred: "명명 규칙 추정",
  conversation: "대화 JOIN 학습", llm_insight: "AI 인사이트", manual: "수동 등록",
};
const _META_EDGE_TYPE_KO = {
  REFERENCES: "참조", DESCRIBES: "용어 설명", RELATED_TERM: "유사어",
  USES: "사용", HAS_SCHEMA: "소속", HAS_TABLE: "소속", HAS_COLUMN: "소속",
  HAS_ROUTINE: "소속", ROUTINE_USES: "테이블 사용",   // graph-funcproc(ADR-016)
};

// graph-ctxmenu: 관계 상세 패널 — 선택 노드의 1-hop 관계를 **방향별**(참조함→/참조받음←/연관 용어/
//   주변 관계)로 그룹해 신뢰도(추정/신뢰 + weight)·근거(edge_source)·상대 노드 설명과 함께 나열한다.
//   행 클릭 = 상대 노드 상세로 이동. self 판정은 노드 자신 + (테이블 관점) 자기 컬럼 포함 —
//   컬럼 단위 FK 도 테이블 관계로 묶여 보인다.
async function _metaGraphShowRelations(key) {
  if (!key) return;
  _metaGraph.lastDetailKey = key;
  _metaGraphHistoryRecord(key, "rel");   // §54①: 첫 await 이전(동기 구간) — Go 재기록은 _histNav 가 차단.
  _metaGraphStatus("관계 상세 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "관계 상세 조회 실패");
    return;
  }
  _metaGraphSetSelected(key);
  // graph-reltrace(tabledetail): 테이블 depth=1 은 컬럼 REFERENCES(2-hop) 미포함 → 모델에서 self
  //   (자기 컬럼 포함)에 닿는 REFERENCES 를 병합해 "관계 상세" 도 테이블 관계를 표시(dedup).
  const mNodes = (data.nodes || []).slice();
  const mEdges = (data.edges || []).slice();
  {
    const seen = new Set(mEdges.map((e) => (e.source || "") + "|" + (e.type || "") + "|" + (e.target || "")));
    const nodeKeys = new Set(mNodes.map((n) => n && n.key));
    const isSelfEnd = (k) => k === key || _metaColParent(k, (_metaGraph.nodes.get(k) || {}).fqn) === key;
    _metaGraph.edges.forEach((e) => {
      if (!e || e.type !== "REFERENCES" || e.status === "broken") return;
      if (!isSelfEnd(e.source) && !isSelfEnd(e.target)) return;
      const id = (e.source || "") + "|REFERENCES|" + (e.target || "");
      if (seen.has(id)) return;
      seen.add(id); mEdges.push(e);
      // 병합 엣지의 상대 노드 보강: 모델에 있으면 모델 노드, 없으면(schema_tables 는 REFERENCES 끝점
      //   Column 노드를 안 실음) key 파생 노드로 — raw scoped key 표시·조인컬럼 주석 소실 방지(review LOW).
      [e.source, e.target].forEach((k) => {
        if (!k || nodeKeys.has(k)) return;
        nodeKeys.add(k);
        mNodes.push(_metaGraph.nodes.has(k) ? _metaGraph.nodes.get(k) : _metaKeyDisplayNode(k));
      });
    });
  }
  _metaGraphRenderRelations(key, mNodes, mEdges);
}

function _metaGraphRenderRelations(key, nodes, edges) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const byKey = {};
  (nodes || []).forEach((n) => { if (n && n.key) byKey[n.key] = n; });
  const self = byKey[key] || _metaGraph.nodes.get(key) || { key, name: key, label: "" };
  const nm = (k) => (byKey[k] && (byKey[k].fqn || byKey[k].name)) || k;
  // self 측 판정: 자신 또는 (테이블이면) 자기 소속 컬럼.
  const isSelf = (k) => {
    if (!k) return false;
    if (k === key) return true;
    const nd = byKey[k];
    return _metaColParent(k, nd && nd.fqn) === key;
  };
  const out = [], inn = [], around = [], terms = [];
  const termSeen = new Set();
  (edges || []).forEach((e) => {
    if (!e || !e.type) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_SCHEMA" || e.type === "HAS_ROUTINE") return;   // containment 제외(graph-funcproc: 소속 스키마도)
    const sSelf = isSelf(e.source), tSelf = isSelf(e.target);
    if (!sSelf && !tSelf) { around.push(e); return; }   // review: self 무관(이웃-이웃)은 term 이라도 주변 관계
    const other = sSelf ? e.target : e.source;
    const on = byKey[other];
    if ((e.type === "DESCRIBES" || e.type === "RELATED_TERM") && on && on.label === "GlossaryTerm") {
      if (!termSeen.has(other)) { termSeen.add(other); terms.push({ e, node: on }); }
      return;
    }
    if (sSelf) { out.push(e); return; }
    inn.push(e);
  });
  // review MAJOR-1: 앵커 측 조인 컬럼 표기 — 컬럼 단위 FK 에서 "어느 컬럼으로 JOIN 되는가"를 행에 노출.
  //   out: `colname → 상대` · in: `상대 → colname`. 같은 대상으로 가는 FK 2개도 로컬 컬럼으로 구분된다.
  // graph-category(§55 B): 관계 큐레이션 버튼 — REFERENCES 행에 신뢰 승격(✓)·파단(✕). 권한
  //   metadata.table.manage(kb.ingest.manual 묶음 함의) 보유자만. 크로스-DS candidate 는 프로브 검증이
  //   불가해 이 승격이 유일한 신뢰 경로(ADR-019) — trusted 는 승격 버튼 생략(파단만).
  const canCurate = (typeof can === "function") && (can("metadata.table.manage") || can("kb.ingest.manual"));
  const curateBtns = (e) => {
    if (!canCurate || e.type !== "REFERENCES" || !e.source || !e.target) return "";
    const b = [];
    if (e.status !== "trusted") b.push(`<button type="button" class="amgr-cur amgr-cur-trust" data-cur="trust" data-src="${esc(e.source)}" data-tgt="${esc(e.target)}" title="이 관계를 신뢰(trusted)로 승격 — AI 답변 컨텍스트에 주입됩니다">✓ 신뢰</button>`);
    b.push(`<button type="button" class="amgr-cur amgr-cur-break" data-cur="break" data-src="${esc(e.source)}" data-tgt="${esc(e.target)}" title="이 관계를 파단(broken) 처리 — 그래프·AI 컨텍스트에서 제거됩니다">✕ 파단</button>`);
    return `<span class="amgr-curate">${b.join("")}</span>`;
  };
  const row = (e, otherKey, selfEndKey, arrow) => {
    const on = byKey[otherKey] || {};
    const selfEnd = (selfEndKey && selfEndKey !== key) ? (byKey[selfEndKey] || null) : null;
    const localName = selfEnd ? (selfEnd.name || String(selfEndKey).split(".").pop()) : "";
    const srcKo = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "";
    const typeKo = _META_EDGE_TYPE_KO[e.type] || e.type || "";
    const counter = `<code>${esc(on.fqn || on.name || otherKey)}</code>`;
    const main = arrow === "→"
      ? `${localName ? `<code>${esc(localName)}</code> <span class="amgr-arrow">→</span> ` : ""}${counter}`
      : `${counter}${localName ? ` <span class="amgr-arrow">→</span> <code>${esc(localName)}</code>` : ""}`;
    return `<li class="amgr-row" data-key="${esc(otherKey)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span>${main}` +
      `${e.cardinality ? ` <span class="admin-meta-graph-muted">[${esc(e.cardinality)}]</span>` : ""}${_metaEdgeTrustBadge(e)}${curateBtns(e)}</div>` +
      `<div class="amgr-sub admin-meta-graph-muted">${esc(typeKo)}${srcKo ? " · 근거: " + esc(srcKo) : ""}${on.description ? " — " + esc(on.description) : ""}</div></li>`;
  };
  // review: 60/30건 절단 시 "… 외 N건" 명시(헤더 카운트와 행 수의 침묵 불일치 방지).
  const moreRow = (n) => `<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${n}건 (그래프에 펼치기로 확인)</div></li>`;
  // review: REFERENCES 외 타입이 섞이면 "참조" 대신 중립 라벨.
  const dirLabel = (list, refLabel, neutral) => (list.every((e) => e.type === "REFERENCES") ? refLabel : neutral);
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || key)}</strong> <span class="admin-meta-graph-relbadge">관계 상세</span></div>`);
  if (self.fqn) parts.push(`<div class="admin-meta-graph-fqn">${esc(self.fqn)}</div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">이 노드가 맺은 관계를 방향별로 봅니다 — 참조함 ${out.length} · 참조받음 ${inn.length} · 연관 용어 ${terms.length}${around.length ? ` · 주변 관계 ${around.length}` : ""}. 행을 클릭하면 상대 노드 상세로 이동합니다.</p>`);
  if (out.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>→ ${dirLabel(out, "참조함", "나가는 관계")} (${out.length})</h4><ul class="amgr-list">`);
    out.slice(0, 60).forEach((e) => parts.push(row(e, e.target, e.source, "→")));
    if (out.length > 60) parts.push(moreRow(out.length - 60));
    parts.push(`</ul></div>`);
  }
  if (inn.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>← ${dirLabel(inn, "참조받음", "들어오는 관계")} (${inn.length})</h4><ul class="amgr-list">`);
    inn.slice(0, 60).forEach((e) => parts.push(row(e, e.source, e.target, "←")));
    if (inn.length > 60) parts.push(moreRow(inn.length - 60));
    parts.push(`</ul></div>`);
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul class="amgr-list">`);
    terms.slice(0, 30).forEach(({ e, node }) => {
      parts.push(`<li class="amgr-row" data-key="${esc(node.key)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
        `<div class="amgr-main"><span class="amgr-arrow">◈</span><strong>${esc(node.name || node.key)}</strong></div>` +
        `<div class="amgr-sub admin-meta-graph-muted">${esc(_META_EDGE_TYPE_KO[e.type] || e.type)}${node.description ? " — " + esc(node.description) : ""}</div></li>`);
    });
    if (terms.length > 30) parts.push(moreRow(terms.length - 30));
    parts.push(`</ul></div>`);
  }
  if (around.length) {
    // 앵커에 직접 닿지 않는 이웃-이웃 관계 — 맥락 참고용으로만 접어서 나열(비클릭).
    parts.push(`<div class="admin-meta-graph-sec"><h4>주변 관계 (${around.length})</h4><ul class="amgr-list">`);
    around.slice(0, 20).forEach((e) => parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted"><code>${esc(nm(e.source))}</code> → <code>${esc(nm(e.target))}</code>${_metaEdgeTrustBadge(e)}</div></li>`));
    if (around.length > 20) parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${around.length - 20}건 (관계 확장으로 그래프에서 확인)</div></li>`);
    parts.push(`</ul></div>`);
  }
  if (!out.length && !inn.length && !terms.length) {
    parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다 — FK 미선언 스키마일 수 있습니다. AI 능동 분석·대화 사용이 쌓이면 추정(점선) 관계가 나타납니다.</p>`);
  }
  parts.push(`<div class="amgr-actions"><button type="button" class="btn-secondary" id="amgrExpandBtn" title="이 노드의 이웃을 그래프 화면에 펼칩니다">🕸 그래프에 펼치기</button><button type="button" class="btn-secondary" id="amgrDetailBtn">📋 상세 보기</button></div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  el.querySelectorAll(".amgr-row[data-key]").forEach((r) => {
    // graphux7(#2): 단일=카메라 이동만(상세 유지), 더블=상세 전환(+대상 테이블·컬럼 강조).
    _metaGraphBindRelRow(r, r.getAttribute("data-key"));
  });
  // graph-category(§55 B): 큐레이션 버튼 — 행 클릭(카메라 이동)과 분리(stopPropagation).
  el.querySelectorAll("button.amgr-cur").forEach((b) => {
    b.addEventListener("click", (ev) => {
      ev.stopPropagation(); ev.preventDefault();
      _metaGraphCurateRelation(b.getAttribute("data-cur"), b.getAttribute("data-src"), b.getAttribute("data-tgt"), key);
    });
  });
  const eb = document.getElementById("amgrExpandBtn");
  if (eb) eb.addEventListener("click", () => _metaGraphExpand(key));
  const db = document.getElementById("amgrDetailBtn");
  if (db) db.addEventListener("click", () => _metaGraphShowDetail(key));
  _metaGraphStatus(`관계 상세: ${self.name || key} — 참조함 ${out.length} · 참조받음 ${inn.length} · 용어 ${terms.length}`);
}

// graph-category(§55 A): 카테고리(제품) 밴드 상세 — 제품 정보 + 멤버 스키마(DB) 목록. 행 클릭 = 그 스키마
//   클러스터 상세로 이동. 다제품 스키마는 전 제품을 뱃지로 노출(배정은 대표 제품 — 헤더와 정합).
function _metaGraphShowCategoryDetail(catKey) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el || !catKey) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const label = _metaGraph.catLabelOf.get(catKey) || (catKey === "PC:__none__" ? "미분류" : catKey);
  const members = _metaGraph.catMembers.get(catKey) || [];
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:#8a5a1f">카테고리</span><strong>🗂 ${esc(label)}</strong> <span class="admin-meta-graph-relbadge">제품 카테고리</span></div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">${catKey === "PC:__none__"
    ? "어느 제품의 접근 DB 로도 등록되지 않은 스키마(DB) 묶음입니다. 관리 콘솔 > 제품 > 접근 DB 에 등록하면 해당 제품 카테고리로 배치됩니다."
    : "이 제품의 접근 DB 로 등록된 스키마(DB) 묶음입니다. 헤더 칩 드래그로 밴드 전체 이동, − / + 로 접기/펼치기."}</p>`);
  parts.push(`<div class="admin-meta-graph-sec"><h4>스키마(DB) ${members.length}개</h4><ul class="amgr-list">`);
  members.forEach((cid) => {
    const nm = _metaComboName(cid);
    const plist = _metaGraph.schemaProducts.get(String(nm).toLowerCase()) || [];
    const extras = plist.length > 1 ? ` <span class="admin-meta-graph-muted">(제품 ${plist.map((p) => esc(p.name)).join(", ")})</span>` : "";
    const cnt = _metaGraph.schemaTotals.get(cid);
    parts.push(`<li class="amgr-row" data-cid="${esc(cid)}" role="button" tabindex="0" title="클릭 = 이 스키마 클러스터 상세">` +
      `<div class="amgr-main"><span class="amgr-arrow">▦</span><strong>${esc(nm)}</strong>${typeof cnt === "number" ? ` <span class="admin-meta-graph-muted">· 테이블 ${cnt}</span>` : ""}${extras}</div></li>`);
  });
  parts.push(`</ul></div></div>`);
  el.innerHTML = parts.join("");
  el.querySelectorAll(".amgr-row[data-cid]").forEach((r) => {
    r.addEventListener("click", () => _metaGraphShowClusterDetailById(r.getAttribute("data-cid")));
  });
  _metaGraphStatus(`카테고리: ${label} — 스키마 ${members.length}개`);
}

// graph-category(§55 B): 관계 사람 큐레이션 — 신뢰 승격(trust) / 파단(break). 관계 상세 패널의 행 버튼이
//   호출한다. 성공 시 모델 로컬 반영(trust=status 승급 · break=엣지 제거) + 재렌더. 크로스-DS 후보는
//   프로브 검증 불가라 이 승격이 유일한 신뢰 경로(→ AI 컨텍스트 주입 대상 전환).
async function _metaGraphCurateRelation(action, src, tgt, anchorKey) {
  if (!src || !tgt || (action !== "trust" && action !== "break")) return;
  const label = action === "trust" ? "신뢰 승격" : "파단";
  const nmOf = (k) => { const n = _metaGraph.nodes.get(k); return (n && (n.fqn || n.name)) || k; };
  if (!window.confirm(`이 관계를 ${label} 처리할까요?\n\n${nmOf(src)}\n→ ${nmOf(tgt)}\n\n${action === "trust"
    ? "신뢰(trusted)로 승격되어 AI 답변 컨텍스트에 주입됩니다."
    : "파단(broken) 처리되어 그래프와 AI 컨텍스트에서 제거됩니다."}`)) return;
  _metaGraphStatus(`관계 ${label} 처리 중…`);
  try {
    await apiFetch(`/api/admin/metadata/graph/relationship/curate`, {
      method: "POST", body: JSON.stringify({ action, src, tgt }) });
  } catch (err) {
    _metaGraphStatus((err && err.message) || `관계 ${label} 실패`);
    return;
  }
  // 모델 로컬 반영(다음 로드/이웃확장과도 멱등 — 서버 SSOT 가 정본).
  const toDelete = [];
  _metaGraph.edges.forEach((e, eid) => {
    if (!e || e.type !== "REFERENCES") return;
    const fwd = (e.source === src && e.target === tgt), rev = (e.source === tgt && e.target === src);
    if (!fwd && !rev) return;
    if (action === "trust") { e.status = "trusted"; e.weight = 1.0; }
    else toDelete.push(eid);
  });
  toDelete.forEach((eid) => _metaGraph.edges.delete(eid));
  await _metaG6Apply(false);
  _metaGraphStatus(`관계 ${label} 완료`);
  if (anchorKey) _metaGraphShowRelations(anchorKey);   // 패널 재렌더(뱃지/버튼 갱신)
}

// graph-funcproc(ADR-017, REQ ⑤): 'AI 능동 분석' hover 지침 popover — 툴팁형 입력창.
//   버튼/섹션 hover(or 버튼 focus) 시 표시, 섹션 이탈 250ms 후 숨김(입력 중이면 유지), Esc 로 닫기.
//   '분석 시작'(또는 지침 입력 후 메인 버튼) → 지침과 함께 분석 트리거. 지침은 세션 내 보존(재열람 prefill).
function _metaGraphBindAiPopover(key, scope) {
  const sec = document.getElementById("metaGraphAiSec");
  const btn = document.getElementById("metaGraphAiBtn");
  const pop = document.getElementById("metaGraphAiPop");
  const ta = document.getElementById("metaGraphAiPrompt");
  const go = document.getElementById("metaGraphAiPopGo");
  if (!btn) return;
  const promptVal = () => (ta && typeof ta.value === "string" ? ta.value.trim().slice(0, 400) : "");
  const start = () => {
    const p = promptVal();
    _metaGraph.aiPrompt = p;
    if (pop) pop.hidden = true;
    _metaGraphAnalyze(key, scope, p);
  };
  btn.addEventListener("click", start);
  if (!pop || !ta || !go) return;   // popover 마크업 부재(비정상) — 버튼 단독 동작 보존
  if (_metaGraph.aiPrompt) ta.value = _metaGraph.aiPrompt;
  let hideT = null;
  // funcproc-esc-hotfix(PB-0008 라이브 적발): Esc 가 pop 을 닫고 btn.focus() 로 포커스를 돌려주는데,
  // btn 의 focus-show 가 즉시 재열고 show() 가 blur 경로의 hide 타이머까지 취소해 **popover 고착**.
  // Esc 직후 짧은 창(300ms) 동안 show 를 억제해 닫힘을 확정한다(focus 복귀는 유지 — a11y).
  let escClosing = false;
  const show = () => {
    if (escClosing) return;
    if (hideT) { clearTimeout(hideT); hideT = null; }
    pop.hidden = false;
  };
  const hideSoon = () => {
    if (hideT) clearTimeout(hideT);
    hideT = setTimeout(() => { if (document.activeElement !== ta) pop.hidden = true; }, 250);
  };
  btn.addEventListener("mouseenter", show);
  btn.addEventListener("focus", show);
  if (sec) { sec.addEventListener("mouseleave", hideSoon); sec.addEventListener("mouseenter", show); }
  ta.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      escClosing = true;
      pop.hidden = true;
      try { btn.focus(); } catch (_) {}
      setTimeout(() => { escClosing = false; }, 300);
    }
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); start(); }
  });
  ta.addEventListener("blur", hideSoon);
  go.addEventListener("click", start);
}

// 항목2: 선택 노드에 대한 AI 능동 분석 트리거(POST → run 생성) + 진행 폴링 시작.
//   prompt(ADR-017): hover popover 로 입력한 사용자 지침(선택) — run 에 저장돼 LLM 이 자율 반영.
async function _metaGraphAnalyze(key, scope, prompt) {
  if (!key) return;
  const box = document.getElementById("metaGraphAiBox");
  const sc = scope || (key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  // graphux7(#4): 중복 큐잉 방어(프론트 1차) — 같은 노드 POST 가 이미 in-flight 면 재요청 안 함(연타 동시 POST
  //   경합 차단; 백엔드 lease-dedup 이 방금 만든 run 을 아직 못 보는 창을 프론트에서 먼저 막는다). 상호작용은 유지.
  if (_metaGraph._analyzePending.has(key)) {
    if (box) box.innerHTML = '<span class="admin-meta-graph-muted">이미 요청을 처리 중입니다 — 중복 요청을 방지합니다. 잠시만 기다려 주세요.</span>';
    return;
  }
  _metaGraph._analyzePending.add(key);
  if (box) box.innerHTML = '<span class="admin-meta-graph-muted">AI 능동 분석 요청 중…</span>';
  const body = { node_key: key, scope_key: sc };
  const p = (typeof prompt === "string") ? prompt.trim().slice(0, 400) : "";
  if (p) body.prompt = p;
  let res;
  try {
    res = await apiFetch(`/api/admin/metadata/graph/analyze`, {
      method: "POST", body: JSON.stringify(body),
    });
  } catch (err) {
    if (box) box.innerHTML = `<span class="admin-meta-graph-muted">시작 실패: ${(err && err.message) || "오류"}</span>`;
    return;
  } finally {
    _metaGraph._analyzePending.delete(key);   // 이 노드 POST 완료(성공/실패) — in-flight 해제. 이후 중복 차단은 백엔드 lease-dedup(reused).
  }
  if (res && res.run_id) {
    // graphux7(#4): 백엔드가 검증한 결과(reused) 로 사용자 메시지를 분기 — 새 큐잉 vs 이미 진행 중을 명확히 구분.
    const reused = !!res.reused;
    // graphux5-progress: 진행 패널을 즉시 표시(닫힘 상태 해제) — 이후 폴링이 상세를 라이브 갱신.
    const panel = document.getElementById("metadataGraphProgress");
    if (panel) {
      delete panel.dataset.dismissed; panel.style.display = "";
      panel.innerHTML = reused
        ? '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">이미 진행 중 — 새로 큐잉하지 않고 기존 분석 현황을 표시합니다.</span></div>'
        : '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">시작 중… 관련 노드를 재귀 탐색합니다.</span></div>';
    }
    if (box) {
      if (reused) {
        const pr = res.progress || {};
        const prTxt = (typeof pr.done === "number" && typeof pr.enqueued === "number") ? ` (진행 ${pr.done}/${pr.enqueued})` : "";
        box.innerHTML = `<span class="admin-meta-graph-muted">이미 이 노드의 AI 능동 분석이 진행 중입니다${prTxt} — 중복 큐잉하지 않고 진행 현황을 위 패널에서 갱신합니다.</span>`;
      } else {
        box.innerHTML = '<span class="admin-meta-graph-muted">분석 중(백그라운드)… 진행 현황은 위 진행 패널에서 확인하세요.</span>';
      }
    }
    _metaGraphPollRun(res.run_id, key);
  }
}

// routine-dbanalysis(§53): DB(스키마) 단위 AI 능동 분석 — dry_run 집계 → confirm(비용 가시화) →
//   실행 → 기존 run 진행 패널(_metaGraphPollRun) 연동. 시드는 미분석 테이블만(only_missing, cap 은
//   백엔드 AGENT_NODE_ANALYSIS_SCHEMA_CAP). reused/noop 은 노드 분석과 동일 parity 안내.
async function _metaGraphAnalyzeSchema(schemaKey) {
  if (!schemaKey) return;
  const nm = _metaComboName(schemaKey);
  if (_metaGraph._analyzePending.has(schemaKey)) {   // 연타 동시 POST 차단(노드 분석과 동일 가드)
    // §18.8 MINOR: 대형 스키마 dry_run 지연 중 재클릭이 무반응이면 기능이 죽은 것처럼 보임 — 노드 경로 parity 피드백.
    _metaGraphStatus(`${nm}: 이미 요청을 처리 중입니다 — 중복 요청을 방지합니다. 잠시만 기다려 주세요.`);
    return;
  }
  _metaGraph._analyzePending.add(schemaKey);
  // §18.8 MAJOR: 사용자가 진행 패널을 ✕ 로 닫은 뒤(dataset.dismissed) 같은 run 을 재트리거하면 안내는
  //   "진행 패널에서 갱신" 을 약속하는데 _metaGraphRenderProgress 가 dismissed run 을 조기 반환해 패널이
  //   영원히 안 뜸 — 노드 분석 경로(delete panel.dataset.dismissed) parity 로 폴 시작 직전 해제.
  //   즉시 head 를 렌더해 첫 폴 tick 전까지 직전 run 의 stale 내용이 보이는 창도 봉인(노드 경로 parity).
  const revealProgress = (reused) => {
    const panel = document.getElementById("metadataGraphProgress");
    if (!panel) return;
    delete panel.dataset.dismissed; panel.style.display = "";
    panel.innerHTML = reused
      ? '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">이미 진행 중 — 새로 큐잉하지 않고 기존 분석 현황을 표시합니다.</span></div>'
      : '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">시작 중… 스키마 시드 항목(테이블·함수·프로시저)을 분석합니다(추가 확장 없음).</span></div>';
  };
  try {
    let dry;
    try {
      dry = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
        method: "POST", body: JSON.stringify({ schema_key: schemaKey, dry_run: true }),
      });
    } catch (err) {
      _metaGraphStatus(`${nm}: DB 단위 분석 대상 조회 실패 — ${(err && err.message) || "오류"}`);
      return;
    }
    if (dry && dry.reused && dry.run_id) {
      // §18.8 MINOR: 이미 진행 중이면 confirm 을 띄우지 않는다 — "이번 실행 N개" 승인 후 실제 POST 가
      //   reused(신규 큐잉 0)로 끝나는 허위 승인 차단(백엔드 dry_run 이 running run 을 먼저 감지).
      const pr = dry.progress || {};
      _metaGraphStatus(`${nm}: 이미 DB 단위 분석 진행 중 (진행 ${pr.done || 0}/${pr.enqueued || 0}) — 중복 큐잉하지 않고 진행 패널에서 갱신합니다.`);
      revealProgress(true);
      _metaGraphPollRun(dry.run_id, null);
      return;
    }
    if (!dry || !dry.planned) {
      _metaGraphStatus(`${nm}: 분석 대상 없음 — 테이블 ${dry ? (dry.total_tables || 0) : 0}개 · 함수/프로시저 ${dry ? (dry.total_routines || 0) : 0}개 전부 분석 완료(또는 대상 없음)`);
      return;
    }
    const cappedTxt = dry.capped ? `\n※ 상한 적용: 미분석 ${dry.missing}개 중 이번 실행 ${dry.planned}개 — 완료 후 재실행하면 이어서 분석합니다.` : "";
    if (!window.confirm(`'${nm}' DB 전체 AI 능동 분석을 시작합니다.\n\n테이블 ${dry.total_tables}개 · 함수/프로시저 ${dry.total_routines || 0}개 · 미분석 ${dry.missing}개 · 이번 실행 ${dry.planned}개${cappedTxt}\n\n이번 실행 대상 ${dry.planned}개 항목(테이블·함수·프로시저)마다 LLM 분석이 수행됩니다(백그라운드). 진행할까요?`)) return;
    let res;
    try {
      res = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
        method: "POST", body: JSON.stringify({ schema_key: schemaKey }),
      });
    } catch (err) {
      _metaGraphStatus(`${nm}: DB 단위 분석 시작 실패 — ${(err && err.message) || "오류"}`);
      return;
    }
    if (!res) return;
    if (res.reused) {
      const pr = res.progress || {};
      _metaGraphStatus(`${nm}: 이미 DB 단위 분석 진행 중 (진행 ${pr.done || 0}/${pr.enqueued || 0}) — 중복 큐잉하지 않고 진행 패널에서 갱신합니다.`);
      if (res.run_id) { revealProgress(true); _metaGraphPollRun(res.run_id, null); }
      return;
    }
    if (res.status === "noop" || !res.run_id) {
      _metaGraphStatus(`${nm}: 분석 대상 없음(이미 전부 분석 완료).`);
      return;
    }
    _metaGraphStatus(`${nm}: DB 전체 AI 능동 분석 시작 — 테이블 ${res.planned}개 (백그라운드, 진행은 우측 패널)`);
    revealProgress();
    _metaGraphPollRun(res.run_id, null);
  } finally {
    _metaGraph._analyzePending.delete(schemaKey);
  }
}

// run 진행률을 폴링하며 완료 노드에 그래프 마커 표시 + 초점 노드 분석 완료 시 결과 로드.
function _metaGraphPollRun(runId, focusKey) {
  if (!runId) return;
  _metaGraph.activeRunId = runId;   // fix(low): 최신 run 만 유효 — 재분석 시 이전 폴 루프 무효화(중복 방지)
  let tries = 0;
  const tick = async () => {
    if (_metaGraph.activeRunId !== runId) return;   // 다른 run 이 시작됨 → 이 루프 종료
    tries += 1;
    let st;
    try { st = await apiFetch(`/api/admin/metadata/graph/analyze?run_id=${encodeURIComponent(runId)}`); }
    catch (_) {
      // fix(medium): 일시 오류/네트워크/일시 5xx 로 폴이 영구 중단되지 않게 재시도(bounded).
      if (tries < 240 && _metaGraph.activeRunId === runId) setTimeout(tick, 2500);
      else _metaGraphMarkRunning([], []);   // review fix: 재시도 소진 시 주황 마커 정리(무한 '분석중' 방지)
      return;
    }
    if (!st) {
      if (tries < 240 && _metaGraph.activeRunId === runId) setTimeout(tick, 2500);
      else _metaGraphMarkRunning([], []);
      return;
    }
    // graphux5-progress: 그래프 마커(완료/분석중) + 진행 패널은 노드 선택과 무관하게 항상 갱신(화면 라이브).
    _metaGraphMarkAnalyzed(st.done_keys || [], st.roles || null);   // node-role-viz: 완료 즉시 역할 칩 색 라이브 반영
    _metaGraphMarkRunning(st.running_keys || [], st.done_keys || []);
    _metaGraphRenderProgress(st);
    const done = st.done || 0, total = st.enqueued || 0, failed = st.failed || 0;
    const onFocus = (_metaGraph.lastDetailKey === focusKey);
    // 초점 노드가 완료되면 상세 패널의 분석문도 로드(노드 상세는 여전히 개별 표시).
    if (onFocus && (st.done_keys || []).indexOf(focusKey) >= 0) _metaGraphLoadNodeAnalysis(focusKey);
    _metaGraphStatus(`AI 능동 분석: ${done}/${total} 완료${failed ? " · 실패 " + failed : ""} (${st.status})`);
    if (st.status === "running") {
      if (tries < 240) { setTimeout(tick, 2500); }
      else {
        // review fix: 캡 도달(여전히 running) — 폴 중단 시 주황 마커 잔존 방지 + 안내(백그라운드는 계속).
        _metaGraphMarkRunning([], st.done_keys || []);
        _metaGraphStatus(`AI 능동 분석: ${done}/${total} — 폴링 시간초과(백그라운드 계속). 노드 재클릭으로 최신 확인.`);
        _metaGraph.activeRunId = null;
      }
    } else {
      _metaGraphMarkRunning([], st.done_keys || []);   // 종료(done/failed) 시 주황 '분석중' 마커 정리
      if (onFocus) _metaGraphLoadNodeAnalysis(focusKey);
    }
  };
  setTimeout(tick, 1500);
}

// 현재 렌더된 노드에 마커/선택 state 재적용(전체 rebuild 없이 — 위치 불변).
// graph-perf-bg: 변화분만 적용(마지막 적용 signature 와 대조) — 폴(2.5s) 마다 전 노드 개별 setElementState 하던 stutter 제거.
// graph-expand-perf fix(프리즈): G6 v5 setElementState 는 건당 ~50ms(실측). 변화 노드가 많으면 per-node 루프가 수 초
//   메인스레드 프리즈를 낸다(200노드=10s). 그래서 변화 노드가 THRESHOLD 초과면 per-node 대신 **단일 setData rebuild**
//   (_metaG6Apply 가 data.states 로 전 상태를 한 번에 bake, ~80–200ms 상수)로 폴백한다. rebuild 는 캐시를 새 sig 로
//   채우므로(위 _metaG6Apply) 재귀·재적용 없음. 소수 변화는 per-node 유지(rebuild flicker 회피).
//   graph-expand-perf fix(폴 tick 이중 refresh): 한 폴 tick 이 _metaGraphMarkAnalyzed + _metaGraphMarkRunning 로 refresh 를
//   연속 2회 부르고 syncMarkers 등과도 겹친다 → 각기 rebuild 를 던지면 tick 당 2× rebuild + in-flight setData/draw 재진입.
//   rAF 로 coalesce: 같은 프레임의 다중 호출을 1회 실행으로 병합(양쪽 set 갱신 후 한 번만 반영). 폴 간격(2.5s) ≫ rebuild(~200ms)라 프레임 간 중첩 없음.
function _metaGraphRefreshStates() {
  if (_metaGraph._refreshScheduled) return;
  _metaGraph._refreshScheduled = true;
  const run = () => { _metaGraph._refreshScheduled = false; _metaGraphRefreshStatesNow(); };
  if (typeof window !== "undefined" && window.requestAnimationFrame) window.requestAnimationFrame(run);
  else setTimeout(run, 0);
}
function _metaGraphRefreshStatesNow() {
  const g = _metaGraph.graph;
  if (!g) return;
  const cache = _metaGraph._stateCache;
  const changed = [];
  let roleChanged = false;   // node-role-viz: 역할 도착/변경은 칩 색·라벨(bake 스타일)이라 setElementState 불가 → rebuild 강제
  _metaGraph.nodes.forEach((n) => {
    const st = _metaStateSig(n.key);   // busy 포함 signature — 폴 tick 이 fetch 창 도중 busy 를 지우지 않도록 보존
    const sig = _metaCacheSig(n.key);  // node-role-viz: 역할 suffix 포함 비교
    const prev = cache.get(n.key);
    if (prev !== sig) {
      changed.push({ key: n.key, st, sig });
      if (_metaSigRole(prev) !== _metaSigRole(sig)) roleChanged = true;
    }
  });
  if (!changed.length) return;   // 변화 없음 — 즉시 반환(폴 tick 의 대다수, rebuild 직후 no-op)
  const REBUILD_THRESHOLD = 4;   // per-node ~50ms/개 → 4개 초과면 rebuild(~200ms)가 저렴 + 프리즈 상한
  if (roleChanged || changed.length > REBUILD_THRESHOLD) {
    // node-role-viz(적대 패널 F2): 펼침/확장 fetch 창(busy) 중엔 rebuild 를 유예 — rebuild 는 _busyKeys 를
    //   소멸시켜 진행 피드백을 지운다. 캐시를 갱신하지 않고 반환하므로 다음 tick(≤2.5s)이 재감지해 수행.
    if (_metaGraph._busyKeys.size) return;
    _metaG6Apply(false);   // setData 가 전 노드 상태 bake + _stateCache populate(카메라 유지, fit=false). fire-and-forget.
    return;
  }
  const apply = () => {
    // graph-expand-perf(freeze) + graph-initview 병합: 변화분(changed)만 순회하되, graph-initview 의
    //   _metaRenderedIdFor(카드 매핑·미렌더 skip) + Promise-wrap setElementState(async reject 무해화)를 유지.
    changed.forEach(({ key, st, sig }) => {
      cache.set(key, sig);
      const el = _metaRenderedIdFor(key);   // graph-initview: 카드 매핑 + 미렌더 skip
      if (!el) return;
      try { Promise.resolve(g.setElementState(el, st)).catch(() => {}); } catch (_) {}
    });
  };
  try {
    if (typeof g.startBatch === "function") { g.startBatch(); try { apply(); } finally { g.endBatch(); } }
    else apply();
  } catch (_) { try { apply(); } catch (_2) {} }
}

// AI 분석 중(running) 노드 주황 점선 마커. done 은 제외.
function _metaGraphMarkRunning(runningKeys, doneKeys) {
  const done = new Set(doneKeys || []);
  _metaGraph.running = new Set((runningKeys || []).filter((k) => !done.has(k)));
  _metaGraphRefreshStates();
}

// graphux5-progress: AI 능동 분석 진행 현황을 상단 패널에 라이브 렌더. 노드 선택과 무관하게 항상 갱신하고,
//   단순 %가 아니라 **어떤 항목(테이블/컬럼/스키마/용어)이 어느 상태(분석중/완료/대기)인지 상세**를 보여준다.
function _metaGraphRenderProgress(st) {
  const panel = document.getElementById("metadataGraphProgress");
  if (!panel || !st) return;
  if (panel.dataset.dismissed && panel.dataset.dismissed === st.run_id) return;   // 사용자가 이 run 패널을 닫음
  panel.style.display = "";   // fix(세션 독립): 재개 폴 경로(버튼 미경유)에서도 패널을 표시 — 초기 display:none 해제
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const jobs = st.jobs || [];
  const done = st.done || 0, enq = st.enqueued || 0, failed = st.failed || 0;
  const running = jobs.filter((j) => j.status === "running");
  const pending = Math.max(0, enq - done - failed - running.length);
  const pct = enq ? Math.round((done / enq) * 100) : 0;
  const ko = (l) => _META_LABEL_KO[l] || l || "노드";
  const statusKo = st.status === "running" ? "진행 중" : st.status === "done" ? "완료" : st.status === "failed" ? "실패" : (st.status || "");
  const stCls = { running: "ampg-st-running", done: "ampg-st-done", failed: "ampg-st-failed" }[st.status] || "";   // review fix: 값을 class 속성에 직접 보간하지 않음
  // node-role-viz: 완료 항목에 AI 분류 역할(아이콘+라벨) 병기 — 진행 패널에서도 역할이 즉시 읽히게.
  const roleTag = (j) => (j.role && _META_ROLE[j.role]) ? ` <span class="admin-meta-graph-muted">${_META_ROLE[j.role].icon} ${esc(_META_ROLE[j.role].ko)}</span>` : "";
  const item = (j, cls, ic) => `<li class="ampg-item ${cls}">${ic} <span class="ampg-lbl">${esc(ko(j.node_label))}</span> <span class="ampg-nm">${esc(j.node_name || j.node_key || "")}</span>${roleTag(j)}<span class="admin-meta-graph-muted"> · 깊이 ${j.depth}</span></li>`;
  const rows = [];
  running.forEach((j) => rows.push(item(j, "ampg-running", "⏳")));
  jobs.filter((j) => j.status === "done").slice(0, 12).forEach((j) => rows.push(item(j, "ampg-done", "✅")));
  jobs.filter((j) => j.status === "failed").slice(0, 4).forEach((j) => rows.push(item(j, "ampg-fail", "⚠️")));
  // routine-dbanalysis(§53 MINOR): 스키마 run 은 고정 시드·재귀 0 이 비용 계약 — "재귀 탐색 중" 카피가
  //   confirm("이번 실행 N개") 직후 무한 fan-out 오해를 부르므로 root_label 로 분기.
  //   (root_label=Schema 재귀 run 은 UI 비도달 — Schema 루트는 analyze-schema 경로만 생성한다.)
  if (pending > 0) rows.push(`<li class="ampg-item admin-meta-graph-muted">⋯ 대기 ${pending}개 (${st.root_label === "Schema" ? "시드 항목 대기 — 추가 확장 없음" : "관련 노드 재귀 탐색 중"})</li>`);
  const parts = [];
  parts.push(`<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">${esc(st.root_name || st.root_key || "")}</span> <span class="ampg-status ${stCls}">${statusKo}</span><button type="button" class="ampg-close" id="metaGraphProgClose" title="닫기" aria-label="진행 패널 닫기">✕</button></div>`);
  parts.push(`<div class="ampg-bar" title="${done}/${enq}"><div class="ampg-bar-fill" style="width:${pct}%"></div></div>`);
  parts.push(`<div class="ampg-counts">완료 <b>${done}</b> · 분석중 <b>${running.length}</b> · 대기 <b>${pending}</b>${failed ? ` · 실패 <b>${failed}</b>` : ""} <span class="admin-meta-graph-muted">/ 예약 ${enq}${st.node_budget ? ` (상한 ${st.node_budget})` : ""}</span></div>`);
  parts.push(`<ul class="ampg-list">${rows.join("") || '<li class="admin-meta-graph-muted">준비 중…</li>'}</ul>`);
  panel.innerHTML = parts.join("");
  const cb = document.getElementById("metaGraphProgClose");
  if (cb) cb.addEventListener("click", () => { panel.style.display = "none"; panel.dataset.dismissed = st.run_id || "1"; });
}

// 완료 노드 키에 분석 마커(보라). 세션 set 에 기억(rebuild 시 유지).
// node-role-viz: roles({key:role})가 오면 역할 표식도 병합 — refreshStates 가 역할 변화를 감지해 rebuild 로 칩 색/아이콘 반영.
function _metaGraphMarkAnalyzed(keys, roles) {
  (keys || []).forEach((k) => _metaGraph.analyzed.add(k));
  if (roles) Object.keys(roles).forEach((k) => { if (roles[k] && _META_ROLE[roles[k]]) _metaGraph.roles.set(k, roles[k]); });
  _metaGraphRefreshStates();
}

// 항목1: 스코프 내 이미 분석된/진행중 노드 마커를 그래프 로드/검색/확장 직후 **일괄** 적용 —
//   노드를 개별 클릭하지 않아도 렌더 시점에 '분석됨'(보라)·'분석중'(주황) 표식이 나타나게 한다.
//   기존엔 세션 로컬 set(_metaGraph.analyzed/running)이 현재 세션 폴 run 에서만 채워져, 새로고침/재진입 시
//   DB 에 저장된 분석 상태가 클릭 전까지 반영되지 않던 근본 원인 수정. 활성 폴의 running set 은 덮어쓰지
//   않도록 additive 로만 적용(clear 안 함).
async function _metaGraphSyncAnalysisMarkers(scope) {
  if (!_metaGraph.graph) return;
  const sc = scope || adminState.metadata.scopeKey || "common";
  if (!sc || sc === "common") return;
  let res;
  try { res = await apiFetch(`/api/admin/metadata/graph/analyze/status?scope=${encodeURIComponent(sc)}`); }
  catch (_) { return; }
  if (!res) return;
  (res.done_keys || []).forEach((k) => _metaGraph.analyzed.add(k));
  const doneSet = new Set(res.done_keys || []);
  (res.running_keys || []).forEach((k) => { if (!doneSet.has(k)) _metaGraph.running.add(k); });
  // node-role-viz: DB 에 저장된 역할 분류를 렌더 시점에 일괄 적용(새로고침/재진입에도 칩 색·아이콘 복원).
  const roles = res.roles || {};
  Object.keys(roles).forEach((k) => { if (roles[k] && _META_ROLE[roles[k]]) _metaGraph.roles.set(k, roles[k]); });
  _metaGraphRefreshStates();
}

// 스키마 클러스터(combo) 상세 — 스키마명·포함 테이블 목록·개수. combo:click 진입.
async function _metaGraphShowClusterDetailById(comboId) {
  if (!_metaGraph.graph || !comboId) return;
  if (comboId === _META_TERMS_COMBO) { _metaGraphStatus("용어·기타 클러스터"); return; }
  _metaGraph.lastDetailKey = comboId;
  _metaGraphHistoryRecord(comboId, "cluster");   // §54①: terms 가드 뒤·첫 await 이전(동기 구간).
  const schemaName = _metaComboName(comboId);
  _metaGraphStatus("클러스터 상세 조회 중…");
  let data = null;
  try { data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(comboId)}&depth=1`); }
  catch (_) { data = null; }
  let tables = [];
  if (data) {
    const byKey = {};
    (data.nodes || []).forEach((nd) => { if (nd && nd.key) byKey[nd.key] = nd; });
    (data.edges || []).forEach((e) => { if (e && e.type === "HAS_TABLE" && e.source === comboId && byKey[e.target]) tables.push(byKey[e.target]); });
    if (!tables.length) (data.nodes || []).forEach((nd) => { if (nd && nd.label === "Table" && nd.key !== comboId) tables.push(nd); });
  }
  // API 가 비면 모델에 로드된 이 스키마 테이블로 폴백.
  let childTables = 0, childCols = 0;
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) childTables += 1;
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  if (!tables.length) _metaGraph.nodes.forEach((n) => { if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n); });
  _metaGraphRenderClusterDetail(schemaName, schemaName, tables, childTables, childCols, null, false, comboId);
  _metaGraphStatus(`클러스터: ${schemaName} · 테이블 ${tables.length || childTables}개`);
}

// 항목2: 클러스터 상세 카드 렌더(우측 상세 패널 body). 노드 상세(_metaGraphRenderDetail)와 동일 컨테이너를 교체.
function _metaGraphRenderClusterDetail(name, fqn, tables, childTables, childCols, totalOverride, truncated, comboId) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // graph-initview(V-G): cap 절단 시 실 총계(table_count) 우선 — 카드 배지와 패널 수치 모순 방지.
  const nTables = (totalOverride != null) ? totalOverride : ((tables && tables.length) || childTables || 0);
  const truncNote = (truncated || (totalOverride != null && tables && totalOverride > tables.length))
    ? ` (그래프에는 ${tables && tables.length ? tables.length : 0}개만 표시 — 상한)` : "";
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  // graphux7(#7): 펼쳐진 스키마면 상세 패널(항상 화면 내 aside)에 전용 '접기' 버튼 — 캔버스 combo 우상단
  //   "−" 컨트롤은 큰 스키마에서 뷰포트 밖으로 벗어나 접근 불가하던 문제 해소. 패널 body 클릭으로 접히지 않게
  //   접기는 이 버튼(및 기존 "−"/우클릭 메뉴)로만 트리거.
  const _canCollapse = comboId && _metaGraph.schemaExpanded && _metaGraph.schemaExpanded.has(comboId);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR.Schema}">스키마 클러스터</span><strong>${esc(name)}</strong>${_canCollapse ? ` <button type="button" class="amgr-link" id="metaGraphClusterCollapseBtn" title="이 스키마를 카드로 접습니다(그래프에서 축소)">▦ 접기</button>` : ""}${comboId && comboId !== _META_TERMS_COMBO ? ` <button type="button" class="amgr-link" id="metaGraphClusterAnalyzeBtn" title="이 DB(스키마)의 미분석 항목(테이블·함수·프로시저) 전체를 AI 능동 분석합니다 — 실행 전 대상 수를 확인합니다">✨ DB 전체 AI 능동 분석</button>` : ""}</div>`);
  if (fqn && fqn !== name) parts.push(`<div class="admin-meta-graph-fqn">${esc(fqn)}</div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">이 스키마 클러스터에 속한 테이블 ${nTables}개${truncNote}${childCols ? ` · 표시된 컬럼 ${childCols}개` : ""}. 테이블 노드를 클릭하면 컬럼·관계·용어 상세를 봅니다.</p>`);
  if (tables && tables.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>테이블 (${tables.length})</h4><ul class="amgr-cluster-tables">`);
    // role-cluster-prefix: AI 능동 분석 완료 테이블은 역할 칩을 접두사로, 미분석은 동일 폭 빈 슬롯(라벨 좌측 정렬 유지 — 뒤틀림 방지).
    const rowHTML = (t) => {
      const role = _metaRoleOf(t.key);
      const prefix = role ? _metaRoleChipHTML(role, esc, true) : `<span class="amgr-role-chip amgr-role-chip-sm amgr-role-none" aria-hidden="true"></span>`;
      return `<li><button type="button" class="amgr-ct-row" data-node-key="${esc(t.key)}" title="클릭하면 이 테이블 노드를 선택합니다">${prefix}<code>${esc(t.name || t.fqn || "")}</code>${t.description ? `<span class="amgr-ct-desc"> — ${esc(t.description)}</span>` : ""}</button></li>`;
    };
    // graph-simgroups: 캔버스와 동일한 유사 속성 그룹으로 목록도 구획(헤딩 행) — 2그룹 이상일 때만. 실패 시 평면 폴백.
    let sgs = null;
    try {
      const tbk = new Map(tables.map((t) => [t.key, t]));
      sgs = _metaSimGroups("panel:" + String(name), tables, _metaRelAdjacency(tbk));
    } catch (_) { sgs = null; }
    if (sgs && sgs.length >= 2) {
      // §18.8 패널: 그룹 헤딩은 목록의 실제 구획 의미(장식 아님) → aria-hidden 금지. role="group"+aria-label
      //   로 보조기기에 "그룹명·개수"를 노출. 80행 캡은 그룹 경계에서만 끊고 절단 표식을 남긴다(개수 모순 방지).
      let emitted = 0;
      sgs.forEach((sg) => {
        if (emitted >= 80) return;
        const shown = Math.min(sg.tables.length, 80 - emitted);
        const trunc = shown < sg.tables.length ? ` <span class="amgr-ct-group-trunc">(${shown}/${sg.n})</span>` : "";
        parts.push(`<li class="amgr-ct-group" role="group" aria-label="${esc(sg.label)} 그룹 · 테이블 ${sg.n}개"><span class="amgr-ct-group-label">${esc(sg.label)}</span><span class="amgr-ct-group-n">${sg.n}</span>${trunc}</li>`);
        sg.tables.slice(0, shown).forEach((t) => { parts.push(rowHTML(t)); emitted++; });
      });
    } else {
      tables.slice(0, 80).forEach((t) => parts.push(rowHTML(t)));
    }
    parts.push(`</ul></div>`);
  }
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // graphux7(#7): 전용 접기 버튼 바인딩 — 이 스키마를 카드로 축소(항상 화면 내 상세 패널에서 접근).
  const _collapseBtn = document.getElementById("metaGraphClusterCollapseBtn");
  if (_collapseBtn && comboId) _collapseBtn.addEventListener("click", () => _metaGraphCollapseSchema(comboId));
  // routine-dbanalysis(§53): DB 단위 능동 분석 버튼 — 컨텍스트 메뉴와 동일 핸들러(확인창에 대상 수 표시).
  const _schemaAiBtn = document.getElementById("metaGraphClusterAnalyzeBtn");
  if (_schemaAiBtn && comboId) _schemaAiBtn.addEventListener("click", () => _metaGraphAnalyzeSchema(comboId));
  // role-cluster-prefix: 테이블 행 클릭 → 해당 노드 선택(_metaGraphShowDetail = 하이라이트 setSelected + 상세 렌더) + 렌더돼 있으면 카메라 focus.
  el.querySelectorAll(".amgr-ct-row[data-node-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.getAttribute("data-node-key");
      if (!k) return;
      _metaGraphShowDetail(k);
      const g = _metaGraph.graph, rel = _metaRenderedIdFor(k);
      if (g && rel && typeof g.focusElement === "function") { try { Promise.resolve(g.focusElement(rel, false)).catch(() => {}); } catch (_) {} }
    });
  });
}

// 노드의 최신 분석 상태/결과를 조회해 AI box 에 렌더(상세 패널 진입 시 + 폴링 완료 시).
async function _metaGraphLoadNodeAnalysis(key) {
  const box = document.getElementById("metaGraphAiBox");
  if (!box || !key) return;
  let res;
  try { res = await apiFetch(`/api/admin/metadata/graph/analyze/node?node=${encodeURIComponent(key)}`); }
  catch (_) { return; }
  if (!res) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (res.status === "done" && res.analysis) {
    const roleObj = (res.role && _META_ROLE[res.role]) ? _META_ROLE[res.role] : null;
    _metaGraphMarkAnalyzed([key], roleObj ? { [key]: res.role } : null);
    const a = res.analysis;
    const rows = [];
    // node-role-viz: AI 분류 역할 칩 — 그래프 칩 색과 동일 색/아이콘으로 상세 패널에서도 역할을 명시.
    if (roleObj) rows.push(`<p><span class="admin-meta-graph-badge" style="background:${roleObj.color}${roleObj.dark ? ";color:#161b22" : ""}">${roleObj.icon} ${esc(roleObj.ko)}</span> <span class="admin-meta-graph-muted">AI 분류 테이블 역할</span></p>`);
    if (a.summary) rows.push(`<p class="admin-meta-graph-ai-summary">${esc(a.summary)}</p>`);
    if (a.relationships) rows.push(`<p><strong>관계</strong> — ${esc(a.relationships)}</p>`);
    if (a.usage) rows.push(`<p><strong>활용</strong> — ${esc(a.usage)}</p>`);
    if (a.caveats) rows.push(`<p class="admin-meta-graph-muted"><strong>주의</strong> — ${esc(a.caveats)}</p>`);
    // graph-reltrace ③: AI 능동 분석은 REFERENCES 를 따라 이웃을 재귀 분석한다(백엔드 node_analysis).
    //   그 분석이 따라간 **구조화된 관계**를 추적 가능한 행으로 노출 — LLM prose(위)는 서술이라
    //   클릭 대상이 없으므로, 분석 결과에서도 대상 테이블·컬럼을 직접 추적하게 한다(사용자 요청 ③).
    const trace = _metaGraphRelTraceRowsHTML(key, null);
    if (trace.count) {
      rows.push(`<div class="admin-meta-graph-ai-rels"><strong>연결 관계 추적 (${trace.count})</strong>` +
        `<ul class="amgr-list">${trace.html}</ul></div>`);
    }
    // graph-funcproc(REQ ④): '↻ 재분석' 버튼 제거 — 섹션 헤더의 '✨ 능동 분석' 재실행으로 충분(UX 중복).
    box.innerHTML = rows.join("") || '<span class="admin-meta-graph-muted">분석 결과 없음.</span>';
    _metaGraphBindTraceRows(box);   // graph-reltrace ③: AI 결과의 관계 행도 추적
  } else if (res.status === "pending" || res.status === "running") {
    box.innerHTML = '<span class="admin-meta-graph-muted">분석 진행 중(백그라운드)… 진행 현황은 위 진행 패널에서 확인하세요.</span>';
    // graphux5 fix(세션 독립): 이 노드가 (다른 탭/세션·새로고침으로) 활성 폴이 없는 진행 중 run 에 속하면
    //   그 run 을 폴링 재개해 **어느 화면에서도** 진행 패널·주황 마커·진행률이 나타나게 한다. 이미 그 run 을
    //   폴링 중이면 재개하지 않음(중복 방지). run 이 done/failed 로 끝나면 폴이 자연 종료.
    if (res.run_id && _metaGraph.activeRunId !== res.run_id) {
      const panel = document.getElementById("metadataGraphProgress");
      if (panel) delete panel.dataset.dismissed;
      _metaGraphPollRun(res.run_id, key);
    }
  } else if (res.status === "failed") {
    box.innerHTML = '<span class="admin-meta-graph-muted">이 노드 분석 실패. 재시도하려면 능동 분석을 다시 눌러 주세요.</span>';
  }
  // status === 'none' → 기본 안내 유지(버튼으로 시작).
}

// 폼 값 수집 — 체크박스는 boolean, 그 외는 trim 된 문자열. (number 변환은 _metaSubmitForm 에서.)
function _metaFormValues() {
  const wrap = document.getElementById("metadataFormFields");
  const out = {};
  if (!wrap) return out;
  wrap.querySelectorAll("input, textarea, select").forEach((el) => {
    if (el.type === "checkbox") out[el.name] = el.checked;
    else out[el.name] = (el.value || "").trim();
  });
  return out;
}

async function loadMetadata() {
  const listEl = document.getElementById("metadataList");
  if (!listEl) return;
  const sub = adminState.metadata.subTab;
  // 용어 검토 큐 보기는 별도 적재/렌더 경로(폼/CRUD 아님).
  if (_metaIsGlossaryReview()) {
    await loadGlossaryFeedback();
    return;
  }
  const scope = adminState.metadata.scopeKey || "common";
  adminState.metadata.loadedScope = scope;   // feature-0016 §45 D1: 메타데이터 목록이 로드된 스코프 기록(탭 재진입 diverge 재로드 판정).
  adminState.metadata.loading = true;
  listEl.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "admin-list-empty";
  loading.textContent = "로딩 중…";
  listEl.appendChild(loading);
  try {
    let url = `/api/admin/metadata/${sub}?scope_key=${encodeURIComponent(scope)}`;
    // 용어사전 역할 필터(0021) — 선택된 역할이 있으면 그 역할 행만(공용 '*' 포함 안 함).
    if (sub === "glossary" && adminState.metadata.roleFilter) {
      url += `&role_key=${encodeURIComponent(adminState.metadata.roleFilter)}`;
    }
    const data = await apiFetch(url);
    adminState.metadata.items = (data && data.items) || [];
  } catch (err) {
    adminState.metadata.items = [];
    listEl.replaceChildren();
    const e = document.createElement("div");
    e.className = "admin-list-empty";
    e.textContent = (err && err.message) || "메타데이터 조회 실패";
    listEl.appendChild(e);
    return;
  } finally {
    adminState.metadata.loading = false;
  }
  renderMetadataList();
  // metadata-bs-prefill: 부트스트랩 모드에서 items 가 갱신되면(스코프/서브탭 전환·저장 후) 골격 입력란을
  // 갱신된 기존 설명으로 재prefill 한다. 전체 재렌더(filterBar·페이지·펼침 리셋) 대신 in-place 갱신으로
  // 검색어·페이지·펼침 등 작업 위치를 보존한다(골격 구조는 fetch·서브탭 sync 렌더가 담당).
  const _bs = adminState.metadata.bootstrap;
  if (adminState.metadata.detailMode === "bootstrap" && _bs && Array.isArray(_bs.tables) && _bs.tables.length) {
    _metaBootstrapRefreshPrefill();
  }
}

// 서브뷰별 빈 상태 안내 문구.
const _METADATA_EMPTY_MSG = {
  glossary: "등록된 용어가 없습니다.",
  enums: "등록된 ENUM 항목이 없습니다.",
  tables: "등록된 테이블 설명이 없습니다.",
  columns: "등록된 컬럼 설명이 없습니다.",
  samples: "등록된 샘플쿼리가 없습니다. (피드백 검수 경로로 생성됩니다)",
};

// metadata-list-detail: 좌측 목록 클라이언트 검색 — 서브뷰별 표시 필드 부분일치(소문자).
function _metaItemMatchesSearch(it, sub, q) {
  if (!q) return true;
  let hay = "";
  if (sub === "glossary") hay = `${it.term || ""} ${it.definition || ""}`;
  else if (sub === "enums") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.column_name || ""} ${it.code || ""} ${it.label || ""}`;
  else if (sub === "tables") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.description || ""}`;
  else if (sub === "columns") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.column_name || ""} ${it.description || ""}`;
  else if (sub === "samples") hay = `${it.nl_question || ""} ${it.sql || ""} ${it.domain || ""}`;
  return hay.toLowerCase().includes(q);
}

function renderMetadataList() {
  const listEl = document.getElementById("metadataList");
  const countEl = document.getElementById("metadataCount");
  if (!listEl) return;
  const allItems = adminState.metadata.items;
  const sub = adminState.metadata.subTab;
  // metadata-list-detail: 좌측 목록 검색(title/body 부분일치). 카운트는 검색 시 필터/전체 표기.
  const q = (adminState.metadata.search || "").trim().toLowerCase();
  const items = q ? allItems.filter((it) => _metaItemMatchesSearch(it, sub, q)) : allItems;
  // 서브뷰별 편집 권한 — samples 는 kb.sample.curate, 나머지는 kb.ingest.manual.
  const canEdit = can(_METADATA_SUBTAB_PERM[sub] || "kb.ingest.manual");
  if (countEl) countEl.textContent = q ? `${items.length}/${allItems.length}건` : `${items.length}건`;
  listEl.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = q ? "검색 결과가 없습니다." : (_METADATA_EMPTY_MSG[sub] || "등록된 항목이 없습니다.");
    listEl.appendChild(empty);
    return;
  }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "admin-meta-row";
    if (it.id != null) row.dataset.metaId = String(it.id);
    if (adminState.metadata.selectedId != null && String(it.id) === String(adminState.metadata.selectedId)) row.classList.add("is-active");
    // metadata-list-detail: 행 클릭 = 선택 → 우측 상세 편집('수정' 버튼·폼 점프 스크롤 폐기). 키보드 접근(Enter/Space).
    if (canEdit) {
      row.setAttribute("role", "button");
      row.setAttribute("tabindex", "0");
      row.addEventListener("click", () => _metaStartEdit(it));
      row.addEventListener("keydown", (e) => {
        if (e.target !== e.currentTarget) return;   // 행 내부 버튼(삭제/유사어) 키 입력은 무시 — 이중 발화 방지(적대 패널 MAJOR-2).
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); _metaStartEdit(it); }
      });
    }
    const main = document.createElement("div");
    main.className = "admin-meta-row-main";
    const title = document.createElement("div");
    title.className = "admin-meta-row-title";
    const body = document.createElement("div");
    body.className = "admin-meta-row-body";
    if (sub === "glossary") {
      title.textContent = it.term || "";
      body.textContent = it.definition || "";
    } else if (sub === "enums") {
      const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
      title.textContent = `${loc}  ·  ${it.code || ""}`;
      body.textContent = it.label || "";
    } else if (sub === "tables") {
      const loc = [it.schema_name, it.table_name].filter(Boolean).join(".");
      title.textContent = loc || (it.table_name || "");
      body.textContent = it.description || "";
    } else if (sub === "columns") {
      const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
      title.textContent = loc || (it.column_name || "");
      body.textContent = it.description || "";
    } else if (sub === "samples") {
      title.textContent = it.nl_question || "";
      body.textContent = it.sql || "";
      // SQL 은 monospace 로 표시(가독성).
      body.classList.add("admin-meta-row-code");
    }
    main.appendChild(title);
    main.appendChild(body);
    // glossary 전용 — 역할/출처 배지(0021). 역할별 비중복·자동등록 출처를 한눈에.
    if (sub === "glossary") {
      const tags = document.createElement("div");
      tags.className = "admin-meta-row-tags";
      const mkTag = (text, cls) => {
        const t = document.createElement("span");
        t.className = "admin-meta-tag" + (cls ? " " + cls : "");
        t.textContent = text;
        return t;
      };
      const rk = String(it.role_key || "*");
      tags.appendChild(mkTag(rk === "*" ? "공용" : `역할: ${_metaRoleLabel(rk)}`,
        rk === "*" ? "" : "admin-meta-tag-role"));
      const src = String(it.source || "manual");
      if (src === "auto") tags.appendChild(mkTag("자동등록", "admin-meta-tag-warn"));
      else if (src === "auto_promoted") tags.appendChild(mkTag("자동승급", "admin-meta-tag-warn"));
      main.appendChild(tags);
    }
    // samples 전용 — 가중치/도메인/승인/status 배지.
    if (sub === "samples") {
      const tags = document.createElement("div");
      tags.className = "admin-meta-row-tags";
      const mkTag = (text, cls) => {
        const t = document.createElement("span");
        t.className = "admin-meta-tag" + (cls ? " " + cls : "");
        t.textContent = text;
        return t;
      };
      if (it.domain) tags.appendChild(mkTag(`도메인: ${it.domain}`));
      if (it.weight != null) tags.appendChild(mkTag(`가중치 ${it.weight}`));
      tags.appendChild(mkTag(it.approved ? "승인됨" : "미승인", it.approved ? "admin-meta-tag-ok" : "admin-meta-tag-warn"));
      if (String(it.status || "").toLowerCase() === "stale") {
        tags.appendChild(mkTag("stale", "admin-meta-tag-stale"));
      } else if (it.status) {
        tags.appendChild(mkTag(String(it.status)));
      }
      main.appendChild(tags);
    }
    const meta = document.createElement("div");
    meta.className = "admin-meta-row-meta";
    meta.textContent = it.updated_at ? `수정 ${_metaFmtDt(it.updated_at)}` : "";
    main.appendChild(meta);
    row.appendChild(main);
    if (canEdit) {
      const actions = document.createElement("div");
      actions.className = "admin-meta-row-actions";
      // metadata-list-detail: '수정'은 행 클릭으로 대체. 유사어/삭제만 인라인 — 클릭 전파 차단(행 선택과 분리).
      // glossary 전용 — 유사어/참조 패널 토글(0021).
      if (sub === "glossary") {
        const relBtn = document.createElement("button");
        relBtn.type = "button";
        relBtn.className = "btn-secondary admin-meta-rel";
        relBtn.textContent = "유사어";
        relBtn.addEventListener("click", (e) => { e.stopPropagation(); _metaToggleRelations(it); });
        actions.appendChild(relBtn);
      }
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-secondary admin-meta-del";
      delBtn.textContent = "삭제";
      delBtn.addEventListener("click", (e) => { e.stopPropagation(); _metaDelete(it); });
      actions.appendChild(delBtn);
      row.appendChild(actions);
    }
    listEl.appendChild(row);
    // 유사어 패널 — 이 용어가 펼쳐진 상태면 행 아래에 패널 삽입(0021).
    if (sub === "glossary" && String(adminState.metadata.relationsOpenId) === String(it.id)) {
      listEl.appendChild(_metaBuildRelationsPanel(it));
    }
  }
}

function _metaStartEdit(it) {
  // metadata-list-detail: 좌측 행 선택 → 우측 상세에 수정 폼. 선택 하이라이트 동기화(폼 점프 스크롤 제거 — 상세가 상시 우측에 존재).
  adminState.metadata.editing = { ...it };
  adminState.metadata.selectedId = (it && it.id != null) ? it.id : null;
  adminState.metadata.detailMode = "form";
  _metaRenderDetail();
  _metaSyncListActive();
}

async function _metaSubmitForm(e) {
  if (e && e.preventDefault) e.preventDefault();
  const sub = adminState.metadata.subTab;
  const scope = adminState.metadata.scopeKey || "common";
  const fields = _METADATA_FIELDS[sub] || [];
  const vals = _metaFormValues();
  const editing = adminState.metadata.editing;
  // 생성 비활성 서브뷰(samples)는 PUT(수정)만 허용 — POST 경로 차단(검수 경로가 생성 정본).
  if (_METADATA_NO_CREATE[sub] && !(editing && editing.id != null)) {
    if (typeof showToast === "function") showToast("이 항목은 검수 경로로만 생성됩니다.", true);
    return;
  }
  // 클라 필수 검증(백엔드도 검증 — 이중 안전). checkbox 는 필수 검증 제외.
  for (const f of fields) {
    if (f.type === "checkbox") continue;
    if (f.required && !vals[f.key]) {
      if (typeof showToast === "function") showToast(`${f.label} 는 필수입니다.`, true);
      return;
    }
  }
  // 타입별 payload 조립 — number clamp, checkbox boolean, 빈 선택 필드는 생략.
  const payload = { scope_key: scope };
  for (const f of fields) {
    const raw = vals[f.key];
    if (f.type === "checkbox") {
      payload[f.key] = Boolean(raw);
    } else if (f.type === "number") {
      if (raw === "" || raw == null) continue;            // 빈 number → 미전송(백엔드 default)
      let n = parseInt(raw, 10);
      if (Number.isNaN(n)) continue;
      if (f.min != null) n = Math.max(f.min, n);
      if (f.max != null) n = Math.min(f.max, n);          // weight 1~1000 clamp
      payload[f.key] = n;
    } else {
      if (!f.required && (raw === "" || raw == null)) continue;  // 빈 선택 텍스트 생략(schema_name/domain)
      payload[f.key] = raw;
    }
  }
  // 단일 역할 컨텍스트(glossary, role-single-ui) — 폼 role select 폐기. role_key 를 _metaGlossaryTargetRole 로 주입
  //   (배지·노트와 동일 진실원). 생성=툴바 컨텍스트, 수정=대상 용어 기존 role_key 보존. 백엔드 role_key 검증은 그대로.
  if (sub === "glossary") {
    payload.role_key = _metaGlossaryTargetRole(editing);
  }
  const submitBtn = document.getElementById("metadataSubmitBtn");
  if (submitBtn) submitBtn.disabled = true;
  try {
    if (editing && editing.id != null) {
      await apiFetch(`/api/admin/metadata/${sub}/${encodeURIComponent(editing.id)}`, {
        method: "PUT", body: JSON.stringify(payload),
      });
    } else {
      await apiFetch(`/api/admin/metadata/${sub}`, { method: "POST", body: JSON.stringify(payload) });
    }
    adminState.metadata.editing = null;
    adminState.metadata.selectedId = null;
    adminState.metadata.detailMode = "empty";   // metadata-list-detail: 저장 후 미선택 안내로 복귀(목록 갱신).
    // 폼 초기화(생성 모드면 입력 비움).
    _metaResetInputs();
    _metaRenderDetail();
    await loadMetadata();
    if (typeof showToast === "function") {
      // glossary 는 역할별 비중복 namespace — mis-scope 방지를 위해 등록/수정된 대상 역할을 토스트에 명시(F2).
      if (sub === "glossary") {
        const rk = payload.role_key;
        const rkLabel = (!rk || rk === "*") ? "공용" : `역할: ${_metaRoleLabel(rk)}`;
        showToast(`${editing ? "수정" : "등록"}했습니다 (${rkLabel}).`);
      } else {
        showToast(editing ? "수정했습니다." : "등록했습니다.");
      }
    }
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "저장 실패", true);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function _metaResetInputs() {
  const wrap = document.getElementById("metadataFormFields");
  if (!wrap) return;
  wrap.querySelectorAll("input, textarea").forEach((el) => {
    if (el.type === "checkbox") el.checked = false;
    else el.value = "";
  });
}

// 서브뷰별 삭제 confirm 라벨.
function _metaDeleteLabel(sub, it) {
  if (sub === "glossary") return it.term || "이 용어";
  if (sub === "enums") return `${it.table_name || ""}.${it.column_name || ""}=${it.code || ""}`;
  if (sub === "tables") return [it.schema_name, it.table_name].filter(Boolean).join(".") || "이 테이블 설명";
  if (sub === "columns") return [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".") || "이 컬럼 설명";
  if (sub === "samples") return it.nl_question || "이 샘플쿼리";
  return "이 항목";
}

async function _metaDelete(it) {
  const sub = adminState.metadata.subTab;
  const scope = adminState.metadata.scopeKey || "common";
  const label = _metaDeleteLabel(sub, it);
  if (!window.confirm(`삭제하시겠습니까?\n\n${label}\n\n등록 내용이 답변 프롬프트에서 제외됩니다.`)) return;
  try {
    await apiFetch(`/api/admin/metadata/${sub}/${encodeURIComponent(it.id)}?scope_key=${encodeURIComponent(scope)}`, {
      method: "DELETE",
    });
    adminState.metadata.items = adminState.metadata.items.filter((x) => String(x.id) !== String(it.id));
    // metadata-list-detail: 삭제한 항목이 우측에서 편집/선택 중이면 상세를 empty 로 리셋(stale 폼 방지).
    const ed = adminState.metadata.editing;
    if (String(adminState.metadata.selectedId) === String(it.id) || (ed && String(ed.id) === String(it.id))) {
      adminState.metadata.editing = null;
      adminState.metadata.selectedId = null;
      adminState.metadata.detailMode = "empty";
      _metaRenderDetail();
    }
    renderMetadataList();
    if (typeof showToast === "function") showToast("삭제했습니다.");
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "삭제 실패", true);
  }
}

/* ── 용어사전 대화 자율등록: 역할 차원 + 검토 큐 + 유사어 참조 (0021) ───────────────────
 * 역할(role) 차원: 용어사전을 역할별 비중복 namespace 로 운영. 역할 선택 UI 는 **툴바 하나로 일원화**
 *   (role-single-ui): 툴바 역할 컨텍스트 = 목록 필터(GET …/glossary?role_key=) + 신규 용어 등록 대상.
 *   폼엔 역할 select 없음 — 대상 역할은 읽기전용 배지로만 표시. 목록 역할 배지는 유지. 공용 = '*'.
 * 검토 큐(용어사전 > 용어 검토 큐 보기, 권한 kb.glossary.curate): 대화에서 자동 제안된 용어 후보를 검토.
 *   하이브리드 — pending(검토 대기) / auto_promoted(자동 등록, 되돌리기 가능). promote(승급)/reject(거부).
 * 유사어/참조: 용어별 glossary_relations 패널(목록/추가/삭제, 역할 경계 횡단 허용).
 * XSS: 모든 사용자 데이터 textContent/value 로만 삽입. */

// (role-single-ui) _metaRoleOptions 폐기 — 폼 역할 select 제거로 미사용. 역할 옵션은 툴바 _metaPopulateRoleFilter 하나만 채운다.

// 단일 역할 컨텍스트(role-single-ui) — 등록/수정 대상 role_key 의 단일 진실원(배지·payload·토스트 공용).
//   생성 = 현재 툴바 역할 컨텍스트(전체 역할 "" → 공용 '*'). 수정 = 대상 용어의 기존 role_key 보존(legacy null/빈값 → '*').
function _metaGlossaryTargetRole(editing) {
  if (editing && editing.id != null) {
    return String((editing.role_key != null && String(editing.role_key).trim() !== "") ? editing.role_key : "*");
  }
  const ctx = adminState.metadata.roleFilter || "";
  return ctx === "" ? "*" : ctx;
}

// '등록 대상 역할' 배지/노트 동기화 — 폼 전체 재렌더(입력 소실) 없이 배지만 갱신(툴바 역할 변경·렌더 시 호출).
//   수정 모드면 대상 용어 역할(고정), 생성 모드면 현재 컨텍스트. '전체 역할' 보기 생성 시 공용 귀속을 노트로 명시(혼동 방지, F1).
function _metaUpdateGlossaryRoleBadge() {
  const badge = document.getElementById("metadataRoleContextBadge");
  if (!badge) return;   // 폼 미표시(다른 서브탭/검토 큐)면 대상 없음
  const editing = adminState.metadata.editing;
  const isEdit = Boolean(editing && editing.id != null);
  const rk = _metaGlossaryTargetRole(editing);
  badge.className = "admin-meta-tag" + (rk === "*" ? "" : " admin-meta-tag-role");
  badge.textContent = rk === "*" ? "공용 (모든 역할)" : `역할: ${_metaRoleLabel(rk)}`;
  badge.title = "역할은 위 툴바의 '역할' 선택으로 정합니다.";
  const note = document.getElementById("metadataRoleContextNote");
  if (note) {
    note.textContent = (!isEdit && (adminState.metadata.roleFilter || "") === "")
      ? "‘전체 역할’ 보기 — 신규 용어는 공용으로 등록됩니다."
      : "";
  }
}

// role_key → 사람이 읽는 라벨(역할명). 미매칭이면 key 그대로.
function _metaRoleLabel(rk) {
  const key = String(rk || "").trim().toLowerCase();
  if (!key || key === "*") return "공용";
  // role 객체(/api/admin/roles 정본 직렬화)는 key/name 필드를 쓴다 — role_key/role_name 은 미존재(역할 라벨 미표시 fix).
  const r = (adminState.roles || []).find((x) => String((x && x.key) || "").toLowerCase() === key);
  return (r && r.name) ? String(r.name) : key;
}

// 역할 필터 드롭다운: 전체("") + 공용('*') + 역할들. glossary 서브뷰 툴바 노출.
function _metaPopulateRoleFilter() {
  const sel = document.getElementById("metadataRoleFilter");
  if (!sel) return;
  const opts = [{ value: "", label: "전체 역할" }, { value: "*", label: "공용만" }];
  for (const r of (adminState.roles || [])) {
    // role 객체는 key/name(정본 /api/admin/roles 직렬화) — role_key/role_name 은 미존재 필드라 전 역할이 스킵돼 드롭다운이 비던 버그 fix.
    const rk = String((r && r.key) || "").trim().toLowerCase();
    if (!rk) continue;
    opts.push({ value: rk, label: (r && r.name) ? String(r.name) : rk });
  }
  sel.replaceChildren();
  for (const o of opts) {
    const el = document.createElement("option");
    el.value = o.value;
    el.textContent = o.label;
    sel.appendChild(el);
  }
  const cur = adminState.metadata.roleFilter || "";
  sel.value = opts.some((o) => o.value === cur) ? cur : "";
  adminState.metadata.roleFilter = sel.value;
}

// 툴바 가시성 — 역할 필터는 용어사전 '용어 목록' 보기에서만(검토 큐 보기엔 무의미). scope select 는 유지.
function _metaSyncToolbarVisibility() {
  const showRole = (adminState.metadata.subTab === "glossary" && adminState.metadata.glossaryView === "list");
  const label = document.getElementById("metadataRoleFilterLabel");
  const sel = document.getElementById("metadataRoleFilter");
  if (label) label.style.display = showRole ? "" : "none";
  if (sel) {
    sel.style.display = showRole ? "" : "none";
    if (showRole) _metaPopulateRoleFilter();
  }
}

// ── 검토 큐(용어사전 > 용어 검토 큐 보기) ─────────────────────────────────────
async function loadGlossaryFeedback() {
  const listEl = document.getElementById("metadataList");
  if (!listEl) return;
  adminState.metadata.feedback.loading = true;
  listEl.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "admin-list-empty";
  loading.textContent = "로딩 중…";
  listEl.appendChild(loading);
  const status = adminState.metadata.feedback.status || "pending";
  try {
    const url = `/api/admin/metadata/glossary-feedback?status=${encodeURIComponent(status)}`;
    const data = await apiFetch(url);
    adminState.metadata.feedback.items = (data && data.items) || [];
    adminState.metadata.feedback.pendingCount = (data && data.pending_count) || 0;
    _updateGlossaryReviewBadge(adminState.metadata.feedback.pendingCount);
  } catch (err) {
    adminState.metadata.feedback.items = [];
    listEl.replaceChildren();
    const e = document.createElement("div");
    e.className = "admin-list-empty";
    e.textContent = (err && err.message) || "검토 큐 조회 실패";
    listEl.appendChild(e);
    return;
  } finally {
    adminState.metadata.feedback.loading = false;
  }
  renderGlossaryFeedback();
}

function _updateGlossaryReviewBadge(count) {
  const badge = document.getElementById("glossaryReviewBadge");
  if (!badge) return;
  const n = Number(count) || 0;
  if (n > 0) { badge.textContent = String(n); badge.hidden = false; }
  else { badge.textContent = ""; badge.hidden = true; }
}

function renderGlossaryFeedback() {
  const listEl = document.getElementById("metadataList");
  const countEl = document.getElementById("metadataCount");
  if (!listEl) return;
  const items = adminState.metadata.feedback.items || [];
  const canCurate = can("kb.glossary.curate");
  if (countEl) countEl.textContent = `${items.length}건`;
  listEl.replaceChildren();

  // 상태 필터 툴바(pending / auto_promoted / rejected / 전체).
  const bar = document.createElement("div");
  bar.className = "admin-meta-review-bar";
  const sel = document.createElement("select");
  sel.className = "admin-meta-scope-select";
  sel.setAttribute("aria-label", "검토 큐 상태 필터");
  for (const o of [
    { value: "pending", label: "검토 대기(pending)" },
    { value: "auto_promoted", label: "자동 등록(auto)" },
    { value: "promoted", label: "승급됨" },
    { value: "rejected", label: "거부됨" },
    { value: "all", label: "전체" },
  ]) {
    const opt = document.createElement("option");
    opt.value = o.value; opt.textContent = o.label;
    if (o.value === (adminState.metadata.feedback.status || "pending")) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => {
    adminState.metadata.feedback.status = sel.value || "pending";
    loadGlossaryFeedback();
  });
  bar.appendChild(sel);
  const note = document.createElement("span");
  note.className = "admin-archive-detail-note";
  note.textContent = "대화에서 자동 제안된 용어 후보입니다. 승급하면 용어사전에 반영되고, 거부하면 제외(자동 등록분은 회수)됩니다.";
  bar.appendChild(note);
  listEl.appendChild(bar);

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = "검토할 용어 후보가 없습니다.";
    listEl.appendChild(empty);
    return;
  }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "admin-meta-row";
    const main = document.createElement("div");
    main.className = "admin-meta-row-main";
    const title = document.createElement("div");
    title.className = "admin-meta-row-title";
    title.textContent = it.term || "";
    const body = document.createElement("div");
    body.className = "admin-meta-row-body";
    body.textContent = it.suggested_definition || "";
    main.appendChild(title);
    main.appendChild(body);
    // 배지: 역할 / scope / confidence / status.
    const tags = document.createElement("div");
    tags.className = "admin-meta-row-tags";
    const mkTag = (text, cls) => {
      const t = document.createElement("span");
      t.className = "admin-meta-tag" + (cls ? " " + cls : "");
      t.textContent = text;
      return t;
    };
    const rk = String(it.role_key || "*");
    tags.appendChild(mkTag(rk === "*" ? "공용" : `역할: ${_metaRoleLabel(rk)}`, rk === "*" ? "" : "admin-meta-tag-role"));
    if (it.scope_key) tags.appendChild(mkTag(`scope: ${_metaDatasourceLabelOf(it.scope_key)}`));
    if (it.confidence != null) tags.appendChild(mkTag(`신뢰도 ${Number(it.confidence).toFixed(2)}`));
    const st = String(it.status || "");
    const stLabel = { pending: "검토 대기", auto_promoted: "자동 등록됨", promoted: "승급됨", rejected: "거부됨" }[st] || st;
    tags.appendChild(mkTag(stLabel, st === "auto_promoted" ? "admin-meta-tag-warn" : (st === "promoted" ? "admin-meta-tag-ok" : "")));
    main.appendChild(tags);
    row.appendChild(main);

    if (canCurate) {
      const actions = document.createElement("div");
      actions.className = "admin-meta-row-actions";
      if (st === "pending") {
        const promoteBtn = document.createElement("button");
        promoteBtn.type = "button";
        promoteBtn.className = "btn-primary admin-meta-edit";
        promoteBtn.textContent = "승급";
        promoteBtn.addEventListener("click", () => _glossaryFeedbackAction(it.id, "promote", promoteBtn));
        actions.appendChild(promoteBtn);
      }
      if (st === "pending" || st === "auto_promoted") {
        const rejectBtn = document.createElement("button");
        rejectBtn.type = "button";
        rejectBtn.className = "btn-secondary admin-meta-del";
        rejectBtn.textContent = (st === "auto_promoted") ? "되돌리기" : "거부";
        rejectBtn.addEventListener("click", () => _glossaryFeedbackAction(it.id, "reject", rejectBtn));
        actions.appendChild(rejectBtn);
      }
      if (actions.childNodes.length) row.appendChild(actions);
    }
    listEl.appendChild(row);
  }
}

async function _glossaryFeedbackAction(feedbackId, action, btn) {
  if (action === "reject" && !window.confirm("이 용어 후보를 거부하시겠습니까?\n자동 등록된 용어라면 용어사전에서 회수됩니다.")) return;
  if (btn) btn.disabled = true;
  try {
    await apiFetch(`/api/admin/metadata/glossary-feedback/${encodeURIComponent(feedbackId)}/${action}`, { method: "POST" });
    if (typeof showToast === "function") showToast(action === "promote" ? "용어사전에 승급했습니다." : "거부 처리했습니다.");
    await loadGlossaryFeedback();
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "처리 실패", true);
    if (btn) btn.disabled = false;
  }
}

// ── 유사어/참조 패널 (glossary_relations) ─────────────────────────────────────
function _metaToggleRelations(it) {
  const open = String(adminState.metadata.relationsOpenId) === String(it.id);
  adminState.metadata.relationsOpenId = open ? null : it.id;
  renderMetadataList();
}

function _metaBuildRelationsPanel(it) {
  const panel = document.createElement("div");
  panel.className = "admin-meta-rel-panel";
  const head = document.createElement("div");
  head.className = "admin-meta-rel-head";
  head.textContent = `"${it.term}" 의 유사어/참조`;
  panel.appendChild(head);
  const listWrap = document.createElement("div");
  listWrap.className = "admin-meta-rel-list";
  listWrap.textContent = "로딩 중…";
  panel.appendChild(listWrap);

  // 추가 컨트롤 — 다른 용어 선택 + 관계 유형 + 추가.
  const addWrap = document.createElement("div");
  addWrap.className = "admin-meta-rel-add";
  const otherSel = document.createElement("select");
  otherSel.className = "admin-meta-scope-select";
  otherSel.setAttribute("aria-label", "연결할 용어");
  const others = (adminState.metadata.items || []).filter((x) => String(x.id) !== String(it.id));
  if (!others.length) {
    const opt = document.createElement("option");
    opt.value = ""; opt.textContent = "(연결할 다른 용어 없음)";
    otherSel.appendChild(opt);
  } else {
    for (const o of others) {
      const opt = document.createElement("option");
      opt.value = String(o.id);
      const rk = String(o.role_key || "*");
      opt.textContent = `${o.term}${rk === "*" ? "" : " (" + _metaRoleLabel(rk) + ")"}`;
      otherSel.appendChild(opt);
    }
  }
  const typeSel = document.createElement("select");
  typeSel.className = "admin-meta-scope-select";
  typeSel.setAttribute("aria-label", "관계 유형");
  for (const o of [
    { value: "similar", label: "유사어" },
    { value: "synonym", label: "동의어" },
    { value: "see_also", label: "참고" },
  ]) {
    const opt = document.createElement("option");
    opt.value = o.value; opt.textContent = o.label;
    typeSel.appendChild(opt);
  }
  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "btn-secondary";
  addBtn.textContent = "연결 추가";
  addBtn.addEventListener("click", () => {
    const toId = otherSel.value;
    if (!toId) { if (typeof showToast === "function") showToast("연결할 용어를 선택하세요.", true); return; }
    _metaAddRelation(it.id, toId, typeSel.value, listWrap);
  });
  addWrap.appendChild(otherSel);
  addWrap.appendChild(typeSel);
  addWrap.appendChild(addBtn);
  panel.appendChild(addWrap);

  _metaLoadRelations(it.id, listWrap);
  return panel;
}

const _META_REL_TYPE_LABEL = { similar: "유사어", synonym: "동의어", see_also: "참고" };

async function _metaLoadRelations(termId, listWrap) {
  listWrap.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "admin-list-empty";
  loading.textContent = "로딩 중…";
  listWrap.appendChild(loading);
  let items = [];
  try {
    const data = await apiFetch(`/api/admin/metadata/glossary/${encodeURIComponent(termId)}/relations`);
    items = (data && data.items) || [];
  } catch (err) {
    listWrap.replaceChildren();
    const e = document.createElement("div");
    e.className = "admin-list-empty";
    e.textContent = (err && err.message) || "유사어 조회 실패";
    listWrap.appendChild(e);
    return;
  }
  listWrap.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = "연결된 유사어가 없습니다.";
    listWrap.appendChild(empty);
    return;
  }
  for (const rel of items) {
    const chip = document.createElement("div");
    chip.className = "admin-meta-rel-item";
    const label = document.createElement("span");
    const rk = String(rel.other_role_key || "*");
    label.textContent = `[${_META_REL_TYPE_LABEL[rel.relation_type] || rel.relation_type}] ${rel.other_term}${rk === "*" ? "" : " (" + _metaRoleLabel(rk) + ")"}`;
    chip.appendChild(label);
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "btn-secondary admin-meta-del";
    rm.textContent = "✕";
    rm.addEventListener("click", () => _metaRemoveRelation(rel.relation_id, termId, listWrap));
    chip.appendChild(rm);
    listWrap.appendChild(chip);
  }
}

async function _metaAddRelation(termId, toId, relType, listWrap) {
  try {
    await apiFetch(`/api/admin/metadata/glossary/${encodeURIComponent(termId)}/relations`, {
      method: "POST",
      body: JSON.stringify({ to_id: Number(toId), relation_type: relType }),
    });
    if (typeof showToast === "function") showToast("유사어를 연결했습니다.");
    _metaLoadRelations(termId, listWrap);
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "연결 추가 실패", true);
  }
}

async function _metaRemoveRelation(relationId, termId, listWrap) {
  try {
    await apiFetch(`/api/admin/metadata/glossary/relations/${encodeURIComponent(relationId)}`, { method: "DELETE" });
    if (typeof showToast === "function") showToast("연결을 삭제했습니다.");
    _metaLoadRelations(termId, listWrap);
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "연결 삭제 실패", true);
  }
}

/* ── TASK-20260624-item11-metadata-phase2: 부트스트랩 UI (테이블/컬럼 서브뷰 전용) ───────
 * 흐름: [datasource 선택] → [schema 선택(GET …/bootstrap/schemas?datasource=)] → "골격 가져오기"
 *       (POST …/bootstrap {datasource,schema}) → 응답 골격을 트리/목록으로 표시(설명 빈칸 입력란) →
 *       사람이 description 입력 → 저장 시 tables/columns POST(각 행). 골격은 미영속 — 저장 전까지 DB 무반영.
 * 권한 게이트: kb.ingest.manual(서브뷰가 이미 게이트됨). XSS: 모든 식별자 textContent/value 로만 삽입. */

// metadata-bs-paging: 페이지당 테이블 블록 수. 대규모 스키마(수백 테이블)에서 접힌 한 줄
//   헤더라도 전부 렌더하면 pane(overflow-y:auto) 세로가 무한 확장된다. 페이징으로 가시 블록을
//   한 페이지로 제한해 스크롤 길이를 고정한다(필터와 동일한 display 토글 — DOM 은 전체 보존).
const META_BS_PAGE_SIZE = 30;

// 현재 서브탭(tables/columns) + metadata.table.manage 일 때만 부트스트랩 패널을 노출한다(graph-panel-perms task4).
// scope-single-ds-ui: 부트스트랩 데이터소스는 상단 스코프(metadataScopeSelect)를 상속한다.
//   - 공용(common)/미매칭 스코프 → 실제 스키마 없음 → empty-state(#metadataBootstrapEmpty)만 노출.
//   - 구체 데이터소스 스코프 → 골격 컨트롤(토글+본문) 노출 + 스코프 DS 상속·스키마 목록 로드.
function _metaSyncBootstrapVisibility() {
  const panel = document.getElementById("metadataBootstrap");
  if (!panel) return;
  const sub = adminState.metadata.subTab;
  const applicable = (sub === "tables" || sub === "columns") && can("metadata.table.manage");
  panel.style.display = applicable ? "" : "none";
  if (!applicable) return;
  const scopeDs = _metaScopeDatasourceKey();  // 공용/미매칭이면 빈 문자열.
  const head = document.getElementById("metadataBootstrapHead");
  const body = document.getElementById("metadataBootstrapBody");
  const empty = document.getElementById("metadataBootstrapEmpty");
  if (!scopeDs) {
    // 공용(common) 스코프 — 골격 불가. empty-state 만 노출(토글/본문 숨김).
    if (empty) empty.style.display = "";
    if (head) head.style.display = "none";
    if (body) body.style.display = "none";
    return;
  }
  // 구체 데이터소스 스코프 — 골격 컨트롤 노출. 본문은 접힘 상태(bootstrap.open)를 따른다.
  if (empty) empty.style.display = "none";
  if (head) head.style.display = "";
  if (body) body.style.display = adminState.metadata.bootstrap.open ? "" : "none";
  // metadata-list-detail: 토글 텍스트/aria 를 open 상태와 동기화(우측 상세 진입 시 펼친 상태 정합).
  const toggle = document.getElementById("metadataBootstrapToggle");
  if (toggle) {
    const open = adminState.metadata.bootstrap.open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.textContent = open ? "스키마 골격 가져오기 ▴" : "스키마 골격 가져오기 ▾";
  }
  _metaBootstrapSyncToScopeDs(scopeDs);
  // metadata-bs-inline-desc: tables↔columns 서브탭 전환 시 골격 결과를 현재 mode 로 재렌더한다.
  // 서브탭 전환 핸들러는 이 함수만 부르고 _metaBootstrapRenderResult 를 호출하지 않으므로, 이미
  // 가져온 골격(bs.tables)이 있으면 여기서 새 mode 입력 UI 로 교체해야 한다 — 안 그러면 두 mode 의
  // 행 구조(평면 vs 접힘)·expand-all 가시성이 엇갈린 채 stale 하게 남는다(적대 패널 H4 적발).
  if (adminState.metadata.bootstrap.tables.length) _metaBootstrapRenderResult();
}

// 부트스트랩 컨트롤 바인딩(idempotent).
function _metaBindBootstrap() {
  const toggle = document.getElementById("metadataBootstrapToggle");
  if (toggle && !toggle.dataset.bound) {
    toggle.dataset.bound = "1";
    toggle.addEventListener("click", () => {
      const body = document.getElementById("metadataBootstrapBody");
      adminState.metadata.bootstrap.open = !adminState.metadata.bootstrap.open;
      const open = adminState.metadata.bootstrap.open;
      if (body) body.style.display = open ? "" : "none";
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? "스키마 골격 가져오기 ▴" : "스키마 골격 가져오기 ▾";
    });
  }
  // scope-single-ds-ui: 부트스트랩 전용 데이터소스 selector 폐기 — 데이터소스는 상단 스코프를
  // 상속한다(_metaBootstrapSyncToScopeDs). 스코프 변경 핸들러(_metaBindControls)와 서브탭/패널
  // 가시성 동기화(_metaSyncBootstrapVisibility)가 DS 상속·스키마 로드를 담당한다.
  const schemaSel = document.getElementById("metadataBootstrapSchema");
  if (schemaSel && !schemaSel.dataset.bound) {
    schemaSel.dataset.bound = "1";
    schemaSel.addEventListener("change", () => {
      adminState.metadata.bootstrap.schema = schemaSel.value || "";
      const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
      if (fetchBtn) fetchBtn.disabled = !adminState.metadata.bootstrap.schema;
    });
  }
  const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
  if (fetchBtn && !fetchBtn.dataset.bound) {
    fetchBtn.dataset.bound = "1";
    fetchBtn.addEventListener("click", () => _metaBootstrapFetch());
  }
  const saveBtn = document.getElementById("metadataBootstrapSaveBtn");
  if (saveBtn && !saveBtn.dataset.bound) {
    saveBtn.dataset.bound = "1";
    saveBtn.addEventListener("click", () => _metaBootstrapSave());
  }
  // AI 일괄 자동완성 — 골격의 빈 설명 입력란을 AI 가 채움(검토 후 저장).
  const aiBtn = document.getElementById("metadataBootstrapAiBtn");
  if (aiBtn && !aiBtn.dataset.bound) {
    aiBtn.dataset.bound = "1";
    aiBtn.addEventListener("click", () => _metaBootstrapAiFill(aiBtn));
  }
  // metadata-bs-collapse: 테이블명 검색 필터. 검색어 변경은 결과 부분집합을 바꾸므로
  //   metadata-bs-paging: 페이지를 1쪽으로 리셋한 뒤 뷰 재계산.
  const search = document.getElementById("metadataBootstrapSearch");
  if (search && !search.dataset.bound) {
    search.dataset.bound = "1";
    search.addEventListener("input", () => {
      adminState.metadata.bootstrap.page = 0;
      _metaBootstrapApplyFilter();
    });
  }
  // metadata-bs-collapse: 모두 펼치기/접기.
  const expandAll = document.getElementById("metadataBootstrapExpandAll");
  if (expandAll && !expandAll.dataset.bound) {
    expandAll.dataset.bound = "1";
    expandAll.addEventListener("click", () => _metaBootstrapToggleAll());
  }
  // metadata-bs-paging: 이전/다음 페이지. 페이지 변경 후 뷰 재계산 + 결과 상단으로 스크롤.
  const pagePrev = document.getElementById("metadataBootstrapPagePrev");
  if (pagePrev && !pagePrev.dataset.bound) {
    pagePrev.dataset.bound = "1";
    pagePrev.addEventListener("click", () => _metaBootstrapGoPage(-1));
  }
  const pageNext = document.getElementById("metadataBootstrapPageNext");
  if (pageNext && !pageNext.dataset.bound) {
    pageNext.dataset.bound = "1";
    pageNext.addEventListener("click", () => _metaBootstrapGoPage(1));
  }
}

// scope-single-ds-ui: 부트스트랩 데이터소스를 상단 스코프(metadataScopeSelect)에서 상속한다.
// 별도 DS selector 가 없으므로, 노트의 데이터소스명(읽기 전용 컨텍스트)을 갱신하고, 스코프 DS 가
// 바뀐 경우에만 이전 골격/스키마 선택을 리셋한 뒤 새 DS 의 스키마 목록을 로드한다.
// (구체 데이터소스 스코프에서만 호출됨 — 공용/미매칭은 _metaSyncBootstrapVisibility 가 먼저 차단.)
function _metaBootstrapSyncToScopeDs(scopeDs) {
  const ds = String(scopeDs || "").trim().toLowerCase();
  const dsName = document.getElementById("metadataBootstrapDsName");
  if (dsName) dsName.textContent = ds || "—";
  if (ds === (adminState.metadata.bootstrap.datasource || "")) return;  // 변동 없음 — 기존 골격 보존.
  // 스코프 DS 변경 — 이전 DS 의 골격/스키마는 무효(다른 데이터소스 스키마).
  adminState.metadata.bootstrap.datasource = ds;
  adminState.metadata.bootstrap.schema = "";
  adminState.metadata.bootstrap.tables = [];
  const schemaSel = document.getElementById("metadataBootstrapSchema");
  if (schemaSel) { schemaSel.disabled = true; schemaSel.replaceChildren(); }
  const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
  if (fetchBtn) fetchBtn.disabled = true;
  _metaBootstrapRenderResult();
  _metaBootstrapLoadSchemas();
}

function _metaBootstrapStatus(text, isError) {
  const el = document.getElementById("metadataBootstrapStatus");
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("is-error", Boolean(isError));
}

// 부트스트랩 unit 라벨 갱신(엔진별) — MySQL='스키마', MSSQL='데이터베이스'(server>db>schema 4계층).
// metadata-table-desc-fix: MSSQL 은 unit=database 라 라벨/플레이스홀더를 분기해야 사용자 혼동이 없다.
function _metaBootstrapUnitWord() {
  return adminState.metadata.bootstrap.unitKind === "database" ? "데이터베이스" : "스키마";
}
function _metaBootstrapSetUnitLabel() {
  const word = _metaBootstrapUnitWord();
  const lbl = document.getElementById("metadataBootstrapSchemaLabel");
  if (lbl) lbl.textContent = `${word} *`;
  const sel = document.getElementById("metadataBootstrapSchema");
  if (sel) sel.setAttribute("aria-label", `부트스트랩 ${word}`);
}

// 선택 DS 의 unit(MySQL=schema / MSSQL=database) 목록 로드 → 드롭다운 채움.
async function _metaBootstrapLoadSchemas() {
  const ds = adminState.metadata.bootstrap.datasource;
  const schemaSel = document.getElementById("metadataBootstrapSchema");
  const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
  if (schemaSel) { schemaSel.replaceChildren(); schemaSel.disabled = true; }
  if (fetchBtn) fetchBtn.disabled = true;
  if (!ds) { adminState.metadata.bootstrap.unitKind = ""; _metaBootstrapSetUnitLabel(); _metaBootstrapStatus(""); return; }
  _metaBootstrapStatus("목록 로딩 중…");
  try {
    const data = await apiFetch(`/api/admin/metadata/bootstrap/schemas?datasource=${encodeURIComponent(ds)}`);
    // scope-single-ds-ui: 스코프가 부트스트랩 DS 를 결정하므로 스코프 빠른 전환 시 본 함수가 연속 발화한다.
    // await 사이에 DS 가 바뀌었으면 이 응답은 stale — 폐기해 늦게 온 응답이 다른 DS 드롭다운을 덮지 않게 한다.
    if (adminState.metadata.bootstrap.datasource !== ds) return;
    const schemas = (data && Array.isArray(data.schemas)) ? data.schemas : [];
    // engine/unit_kind 로 라벨 분기(MSSQL=database). 구버전 백엔드 응답(필드 없음)은 'schema' 로 폴백.
    adminState.metadata.bootstrap.unitKind = (data && data.unit_kind) || "schema";
    adminState.metadata.bootstrap.schemas = schemas;
    _metaBootstrapSetUnitLabel();
    const word = _metaBootstrapUnitWord();
    if (schemaSel) {
      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent = schemas.length ? `${word} 선택…` : `${word} 없음`;
      schemaSel.appendChild(ph);
      for (const s of schemas) {
        const el = document.createElement("option");
        el.value = String(s);
        el.textContent = String(s);
        schemaSel.appendChild(el);
      }
      schemaSel.disabled = !schemas.length;
    }
    _metaBootstrapStatus(schemas.length ? `${schemas.length}개 ${word}` : `${word}가 없습니다.`);
  } catch (err) {
    adminState.metadata.bootstrap.schemas = [];
    _metaBootstrapStatus((err && err.message) || "목록 조회 실패", true);
  }
}

// 골격 가져오기 — POST /bootstrap {datasource,schema}. 응답 tables 를 입력 트리로 렌더.
async function _metaBootstrapFetch() {
  const bs = adminState.metadata.bootstrap;
  if (!bs.datasource || !bs.schema) {
    _metaBootstrapStatus(`데이터소스와 ${_metaBootstrapUnitWord()}를 선택하세요.`, true);
    return;
  }
  const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
  if (fetchBtn) fetchBtn.disabled = true;
  bs.loading = true;
  bs.tables = [];
  _metaBootstrapRenderResult();
  _metaBootstrapStatus("골격 가져오는 중… (큰 스키마는 시간이 걸릴 수 있습니다)");
  try {
    const data = await apiFetch("/api/admin/metadata/bootstrap", {
      method: "POST",
      body: JSON.stringify({ datasource: bs.datasource, schema: bs.schema }),
    });
    bs.tables = (data && Array.isArray(data.tables)) ? data.tables : [];
    const tcount = bs.tables.length;
    const ccount = bs.tables.reduce((a, t) => a + ((t.columns && t.columns.length) || 0), 0);
    _metaBootstrapStatus(tcount ? `${tcount}개 테이블 · ${ccount}개 컬럼` : "테이블이 없습니다.");
  } catch (err) {
    bs.tables = [];
    _metaBootstrapStatus((err && err.message) || "골격 조회 실패", true);
  } finally {
    bs.loading = false;
    if (fetchBtn) fetchBtn.disabled = !bs.schema;
    _metaBootstrapRenderResult();
  }
}

// metadata-bs-prefill: 기존 저장된 설명을 골격 입력란에 prefill 하기 위한 색인 + 조회 헬퍼.
// loadMetadata 가 현재 (scope, 서브탭) 기준으로 적재한 adminState.metadata.items 를 색인한다.
// read 경로(kb_metadata.load_column_descriptions_for_table)와 동일 정규화 — schema 는 대소문자 무관
// (LOWER) + 빈 schema('') 폴백 — 으로 키잉해, 수동 폼 입력(케이스 임의)·MSSQL 저장 schema_name=DB명
// (원본 케이스) 비대칭에서도 기존 설명이 매칭된다. table/column 명은 정확매치(read 경로 동일).
function _metaBootstrapBuildDescIndex(mode) {
  const idx = new Map();
  for (const it of (adminState.metadata.items || [])) {
    const desc = (it && it.description) || "";
    if (!desc) continue;
    const sn = String(it.schema_name || "").toLowerCase();
    const tn = it.table_name || "";
    const key = mode === "columns" ? JSON.stringify([sn, tn, it.column_name || ""]) : JSON.stringify([sn, tn]);
    // 정확-schema 항목이 빈-schema 폴백을 이기도록, 동일 키 충돌 시 비어있지 않은 schema 를 우선.
    if (!idx.has(key) || sn) idx.set(key, desc);
  }
  return idx;
}
// 골격 행(schemaName/tableName[/colName])에 대응하는 기존 설명을 조회 — 정확 schema 우선, 빈 schema 폴백.
function _metaBootstrapDescLookup(idx, schemaName, tableName, colName) {
  const ls = String(schemaName || "").toLowerCase();
  const exact = colName !== undefined
    ? idx.get(JSON.stringify([ls, tableName, colName]))
    : idx.get(JSON.stringify([ls, tableName]));
  if (exact !== undefined) return exact;
  const fb = colName !== undefined
    ? idx.get(JSON.stringify(["", tableName, colName]))
    : idx.get(JSON.stringify(["", tableName]));
  return fb !== undefined ? fb : "";
}
// metadata-bs-prefill: 골격 DOM 을 다시 그리지 않고(검색어·페이지·펼침 상태 보존) 입력란의 value·
// dataset.original 만 최신 items 로 갱신한다. loadMetadata(스코프/서브탭 전환·저장 후) 가 호출 —
// 전체 재렌더(_metaBootstrapRenderResult)는 filterBar 를 리셋해 작업 위치를 잃으므로 in-place 갱신.
function _metaBootstrapRefreshPrefill() {
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap) return;
  const mode = adminState.metadata.subTab === "columns" ? "columns" : "tables";
  const idx = _metaBootstrapBuildDescIndex(mode);
  wrap.querySelectorAll(".admin-meta-bs-table").forEach((block) => {
    const schemaName = block.dataset.schema || "";
    const tableName = block.dataset.table || "";
    if (mode === "tables") {
      const inp = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
      if (inp) { const v = _metaBootstrapDescLookup(idx, schemaName, tableName); inp.value = v; inp.dataset.original = v; }
    } else {
      block.querySelectorAll(".admin-meta-bs-col").forEach((colRow) => {
        const inp = colRow.querySelector(".admin-meta-bs-desc[data-kind='column']");
        if (inp) { const v = _metaBootstrapDescLookup(idx, schemaName, tableName, colRow.dataset.column || ""); inp.value = v; inp.dataset.original = v; }
      });
    }
  });
  _metaBootstrapRefreshAllHints(mode);  // 프로그램적 value 변경 후 힌트(입력상태/채움 수) 동기화
}

// 골격 결과 렌더 — 현재 서브탭(tables vs columns)에 따라 입력란 형태가 다르다.
//   tables: 테이블별 설명 1줄.  columns: 테이블 트리 아래 컬럼별 설명.
// 모든 식별자/타입은 textContent, 입력값은 value(=신규 입력)로만 다룸(XSS 안전).
// metadata-bs-collapse: 대규모 스키마(수백 테이블·수천 컬럼) 가독성 — 각 테이블을 기본 접힘
// 한 줄 헤더로 렌더(여백 최소화), 클릭 시 펼쳐 설명/컬럼 입력. 검색 필터·모두 펼치기/접기 동반.
// 접기·필터는 모두 "시각" 토글(display/class)로만 동작 — 입력값은 DOM 에 보존되어 저장(_metaBootstrapSave)
// ·AI 일괄생성(_metaBootstrapApplyDescriptions)·apply 로직은 변경 없이 그대로 전체를 수집한다.
function _metaBootstrapRenderResult() {
  const wrap = document.getElementById("metadataBootstrapResult");
  const saveActions = document.getElementById("metadataBootstrapSaveActions");
  const filterBar = document.getElementById("metadataBootstrapFilterBar");
  const pager = document.getElementById("metadataBootstrapPager");  // metadata-bs-paging
  if (!wrap) return;
  wrap.replaceChildren();
  const bs = adminState.metadata.bootstrap;
  const sub = adminState.metadata.subTab;
  const mode = sub === "columns" ? "columns" : "tables";  // 부트스트랩은 tables/columns 서브뷰에서만 노출
  // metadata-bs-prefill: 기존 저장된 설명 색인(현재 mode 기준). 입력란 생성 시 prefill 에 사용.
  const _descIndex = _metaBootstrapBuildDescIndex(mode);
  if (bs.loading) {
    if (saveActions) saveActions.style.display = "none";
    if (filterBar) filterBar.style.display = "none";
    if (pager) pager.style.display = "none";
    const l = document.createElement("div");
    l.className = "admin-list-empty";
    l.textContent = "로딩 중…";
    wrap.appendChild(l);
    return;
  }
  if (!bs.tables.length) {
    if (saveActions) saveActions.style.display = "none";
    if (filterBar) filterBar.style.display = "none";
    if (pager) pager.style.display = "none";
    return;
  }
  for (const t of bs.tables) {
    const schemaName = t.schema_name || bs.schema || "";
    const tableName = t.table_name || "";
    const fullName = [schemaName, tableName].filter(Boolean).join(".");
    const block = document.createElement("div");
    block.className = "admin-meta-bs-table";
    block.dataset.schema = schemaName;
    block.dataset.table = tableName;
    if (mode === "tables") {
      // metadata-bs-inline-desc: 테이블 설명은 테이블당 1줄뿐이라 접기/펼치기가 불필요하다.
      // 행을 평면(flat)으로 두고, 이름↔상태 사이 빈 중앙 여백을 설명 입력란으로 채운다 —
      // 펼치지 않고 바로 입력(클릭 절감 + 여백 효용화). 입력은 항상 DOM 에 존재(저장·AI fill 전체 수집).
      block.classList.add("is-flat");
      const row = document.createElement("div");
      row.className = "admin-meta-bs-row";
      const name = document.createElement("span");
      name.className = "admin-meta-bs-table-name";
      name.textContent = fullName;
      name.title = fullName;  // ellipsis 시 전체명 hover 노출
      const inp = document.createElement("input");
      inp.type = "text";
      inp.className = "admin-meta-input admin-meta-bs-desc admin-meta-bs-desc-inline";
      inp.placeholder = "테이블 설명 입력…";
      inp.dataset.kind = "table";
      // metadata-bs-prefill: 기존 저장된 테이블 설명을 표시. dataset.original 로 원본을 기억해
      // 저장 시 변경된 행만 POST(미변경 prefill 재저장 안 함 → source provenance 보존).
      {
        const _existing = _metaBootstrapDescLookup(_descIndex, schemaName, tableName);
        inp.value = _existing;
        inp.dataset.original = _existing;
      }
      inp.setAttribute("aria-label", `${fullName} 설명`);
      inp.addEventListener("input", () => _metaBootstrapUpdateHint(block, mode));
      const hint = document.createElement("span");
      hint.className = "admin-meta-bs-hint";
      row.appendChild(name);
      row.appendChild(inp);
      row.appendChild(hint);
      block.appendChild(row);
    } else {
      // columns — 테이블당 컬럼이 여러 개라 접힘 헤더(클릭 토글) + 본문(컬럼별 입력 트리)을 유지.
      block.classList.add("is-collapsed");  // 기본 접힘
      const head = document.createElement("button");
      head.type = "button";
      head.className = "admin-meta-bs-table-head";
      head.setAttribute("aria-expanded", "false");
      const caret = document.createElement("span");
      caret.className = "admin-meta-bs-caret";
      caret.setAttribute("aria-hidden", "true");
      caret.textContent = "▸";
      const name = document.createElement("span");
      name.className = "admin-meta-bs-table-name";
      name.textContent = fullName;
      const hint = document.createElement("span");
      hint.className = "admin-meta-bs-hint";
      head.appendChild(caret);
      head.appendChild(name);
      head.appendChild(hint);
      head.addEventListener("click", () => _metaBootstrapToggleTable(block));
      block.appendChild(head);
      // 본문 — 접힘 시 CSS(.is-collapsed)로 숨김. 입력 요소는 항상 생성(저장·AI fill 이 전체 수집).
      const body = document.createElement("div");
      body.className = "admin-meta-bs-body";
      const cols = Array.isArray(t.columns) ? t.columns : [];
      if (!cols.length) {
        const none = document.createElement("div");
        none.className = "admin-meta-bs-col-none";
        none.textContent = "컬럼 없음";
        body.appendChild(none);
      }
      for (const c of cols) {
        const colName = c.column_name || "";
        const colRow = document.createElement("div");
        colRow.className = "admin-meta-bs-col";
        colRow.dataset.column = colName;
        const cn = document.createElement("span");
        cn.className = "admin-meta-bs-col-name";
        cn.textContent = colName;
        const dt = document.createElement("span");
        dt.className = "admin-meta-bs-col-type";
        dt.textContent = c.data_type ? `(${c.data_type})` : "";
        const inp = document.createElement("input");
        inp.type = "text";
        inp.className = "admin-meta-input admin-meta-bs-desc";
        inp.placeholder = "컬럼 설명 입력…";
        inp.dataset.kind = "column";
        // metadata-bs-prefill: 기존 저장된 컬럼 설명을 표시(원본 기억 → 변경분만 저장).
        {
          const _existing = _metaBootstrapDescLookup(_descIndex, schemaName, tableName, colName);
          inp.value = _existing;
          inp.dataset.original = _existing;
        }
        inp.addEventListener("input", () => _metaBootstrapUpdateHint(block, mode));
        colRow.appendChild(cn);
        colRow.appendChild(dt);
        colRow.appendChild(inp);
        body.appendChild(colRow);
      }
      block.appendChild(body);
    }
    wrap.appendChild(block);
    _metaBootstrapUpdateHint(block, mode);
  }
  // 검색/펼치기 바 초기화(매 fetch 마다 검색어·펼침상태·페이지 리셋).
  if (filterBar) {
    filterBar.style.display = "";
    const search = document.getElementById("metadataBootstrapSearch");
    if (search) search.value = "";
    bs.page = 0;  // metadata-bs-paging: 새 골격은 항상 1쪽부터.
    // metadata-bs-inline-desc: tables 모드는 평면 행(펼침 없음)이라 "모두 펼치기/접기" 숨김(columns 전용).
    const expandAll = document.getElementById("metadataBootstrapExpandAll");
    if (expandAll) expandAll.style.display = mode === "columns" ? "" : "none";
    _metaBootstrapSyncExpandAllLabel();  // columns: 전부 접힌 상태 → "모두 펼치기"
    _metaBootstrapApplyFilter();
  }
  if (saveActions) saveActions.style.display = "";
  const info = document.getElementById("metadataBootstrapSaveInfo");
  if (info) info.textContent = mode === "columns"
    ? "기존 설명은 채워져 표시됩니다. 변경·추가한 행만 저장됩니다. (접힌 테이블·다른 페이지의 변경도 저장됩니다)"
    : "기존 설명은 채워져 표시됩니다. 변경·추가한 행만 저장됩니다. (다른 페이지의 변경도 저장됩니다)";
}

// 단일 테이블 블록 접기/펼치기 토글.
function _metaBootstrapToggleTable(block) {
  if (!block) return;
  const collapsed = block.classList.toggle("is-collapsed");
  const head = block.querySelector(".admin-meta-bs-table-head");
  const caret = block.querySelector(".admin-meta-bs-caret");
  if (head) head.setAttribute("aria-expanded", collapsed ? "false" : "true");
  if (caret) caret.textContent = collapsed ? "▸" : "▾";
  _metaBootstrapSyncExpandAllLabel();  // 개별 토글 후 모두펼치기/접기 라벨 DOM 기준 재동기화
}

// "모두 펼치기/접기" 버튼 라벨을 DOM 상태로 동기화 — 하나라도 접혀 있으면 "모두 펼치기"(다음 클릭=전체 펼침).
function _metaBootstrapSyncExpandAllLabel() {
  const wrap = document.getElementById("metadataBootstrapResult");
  const btn = document.getElementById("metadataBootstrapExpandAll");
  if (!wrap || !btn) return;
  const anyCollapsed = !!wrap.querySelector(".admin-meta-bs-table.is-collapsed");
  btn.textContent = anyCollapsed ? "모두 펼치기" : "모두 접기";
}

// 입력상태 힌트 갱신 — tables: 설명 유무, columns: 채운/전체 컬럼 수.
function _metaBootstrapUpdateHint(block, mode) {
  const hint = block && block.querySelector(".admin-meta-bs-hint");
  if (!hint) return;
  if (mode === "tables") {
    const inp = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
    const has = !!(inp && (inp.value || "").trim());
    hint.textContent = has ? "● 설명 입력됨" : "○ 비어있음";
    hint.classList.toggle("is-filled", has);
  } else {
    const total = block.querySelectorAll(".admin-meta-bs-col").length;
    let filled = 0;
    block.querySelectorAll(".admin-meta-bs-desc[data-kind='column']").forEach((i) => {
      if ((i.value || "").trim()) filled += 1;
    });
    hint.textContent = total ? `컬럼 ${filled}/${total}` : "컬럼 없음";
    hint.classList.toggle("is-filled", filled > 0);
  }
}

// 모든 블록 힌트 일괄 갱신(AI 일괄생성 등 프로그램적 value 설정 후 호출 — input 이벤트 미발생).
function _metaBootstrapRefreshAllHints(mode) {
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap) return;
  wrap.querySelectorAll(".admin-meta-bs-table").forEach((b) => _metaBootstrapUpdateHint(b, mode));
}

// 검색 필터 + 페이징(metadata-bs-paging) — 이름 부분일치(대소문자 무시)로 매칭 블록을 추리고,
// 그중 현재 페이지 윈도우(META_BS_PAGE_SIZE개)만 노출한다. 숨겨도 DOM 보존(저장·AI 일괄은
// 전체 DOM 수집 — 가시성은 순수 display 토글). 대규모 스키마에서 세로 스크롤을 1페이지로 고정.
function _metaBootstrapApplyFilter() {
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap) return;
  const search = document.getElementById("metadataBootstrapSearch");
  const count = document.getElementById("metadataBootstrapFilterCount");
  const q = (search ? search.value : "").trim().toLowerCase();
  const blocks = wrap.querySelectorAll(".admin-meta-bs-table");
  const bs = adminState.metadata.bootstrap;
  // 1) 필터 매칭 — 검색어 부분일치한 블록만 페이징 대상. 비매칭은 즉시 숨김.
  const matched = [];
  blocks.forEach((b) => {
    const nm = [(b.dataset.schema || ""), (b.dataset.table || "")].filter(Boolean).join(".").toLowerCase();
    if (!q || nm.includes(q)) matched.push(b);
    else b.style.display = "none";
  });
  // 2) 페이지 클램프 — 매칭 수 기준(검색으로 결과가 줄면 현재 페이지가 범위 밖일 수 있음).
  const total = matched.length;
  const pageCount = Math.max(1, Math.ceil(total / META_BS_PAGE_SIZE));
  bs.page = Math.min(Math.max(0, bs.page || 0), pageCount - 1);
  const start = bs.page * META_BS_PAGE_SIZE;
  const end = start + META_BS_PAGE_SIZE;
  // 3) 가시성 — 매칭 블록 중 현재 페이지 윈도우만 노출(display 토글만 — DOM/입력값 보존).
  matched.forEach((b, i) => { b.style.display = (i >= start && i < end) ? "" : "none"; });
  // 4) 카운트 라벨 — 페이지 범위 + 전체. 검색 시 매칭/전체 함께 표기.
  const from = total === 0 ? 0 : start + 1;
  const to = Math.min(end, total);
  if (count) {
    count.textContent = q
      ? `표시 ${from}–${to} / 검색 ${total}건 (전체 ${blocks.length})`
      : `표시 ${from}–${to} / 전체 ${total}`;
  }
  // 5) 페이저 갱신(페이지 1쪽뿐이면 숨김).
  _metaBootstrapRenderPager(pageCount);
}

// metadata-bs-paging: 페이지 이동(delta = -1/+1). 클램프·가시성·페이저 갱신은 ApplyFilter 가 수행.
function _metaBootstrapGoPage(delta) {
  const bs = adminState.metadata.bootstrap;
  bs.page = (bs.page || 0) + delta;
  _metaBootstrapApplyFilter();
  // 페이지 전환 시 결과 영역 상단으로 — 긴 목록에서 위치 감 유지.
  const wrap = document.getElementById("metadataBootstrapResult");
  if (wrap && typeof wrap.scrollIntoView === "function") wrap.scrollIntoView({ block: "nearest" });
}

// metadata-bs-paging: 페이저 컨트롤 갱신 — 라벨/이전·다음 disabled. 1페이지뿐이면 바 자체 숨김.
function _metaBootstrapRenderPager(pageCount) {
  const bar = document.getElementById("metadataBootstrapPager");
  if (!bar) return;
  const bs = adminState.metadata.bootstrap;
  if (!pageCount || pageCount <= 1) { bar.style.display = "none"; return; }
  bar.style.display = "";
  const label = document.getElementById("metadataBootstrapPageLabel");
  if (label) label.textContent = `페이지 ${bs.page + 1} / ${pageCount}`;
  const prev = document.getElementById("metadataBootstrapPagePrev");
  const next = document.getElementById("metadataBootstrapPageNext");
  if (prev) prev.disabled = bs.page <= 0;
  if (next) next.disabled = bs.page >= pageCount - 1;
}

// 모두 펼치기 ↔ 모두 접기 토글.
function _metaBootstrapToggleAll() {
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap) return;
  // 하나라도 접혀 있으면 모두 펼침, 전부 펼쳐져 있으면 모두 접음(DOM 기준 — 상태 desync 없음).
  const expand = !!wrap.querySelector(".admin-meta-bs-table.is-collapsed");
  wrap.querySelectorAll(".admin-meta-bs-table").forEach((block) => {
    block.classList.toggle("is-collapsed", !expand);
    const head = block.querySelector(".admin-meta-bs-table-head");
    const caret = block.querySelector(".admin-meta-bs-caret");
    if (head) head.setAttribute("aria-expanded", expand ? "true" : "false");
    if (caret) caret.textContent = expand ? "▾" : "▸";
  });
  _metaBootstrapSyncExpandAllLabel();
}

// 부트스트랩 저장 — 설명이 입력된 행만 tables/columns POST(각 행). scope = 현재 메타데이터 scope.
async function _metaBootstrapSave() {
  const bs = adminState.metadata.bootstrap;
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap) return;
  const sub = adminState.metadata.subTab;
  const mode = sub === "columns" ? "columns" : "tables";
  const scope = adminState.metadata.scopeKey || "common";
  // 입력된 행 수집(DOM 순회 — 입력값은 value, 식별자는 dataset).
  const rows = [];
  wrap.querySelectorAll(".admin-meta-bs-table").forEach((block) => {
    const schemaName = block.dataset.schema || "";
    const tableName = block.dataset.table || "";
    if (mode === "tables") {
      const inp = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
      const desc = inp ? (inp.value || "").trim() : "";
      // metadata-bs-prefill: 변경된(또는 새로 입력한) 행만 저장 — prefill 된 기존 설명을
      // 손대지 않았으면 재저장하지 않아 source(manual 등) provenance 를 보존한다.
      const orig = inp ? (inp.dataset.original || "") : "";
      if (desc && desc !== orig) rows.push({ schema_name: schemaName, table_name: tableName, description: desc });
    } else {
      // feature-0016 graphux5: 골격 컬럼 DOM 순서 = describe_columns(ORDINAL_POSITION) 순 = 실제 DDL 순.
      //   행 인덱스(1-based)를 ordinal 로 전송 → 그래프 뷰가 컬럼을 테이블 아래 실제 순서로 세로 배치한다.
      block.querySelectorAll(".admin-meta-bs-col").forEach((colRow, idx) => {
        const inp = colRow.querySelector(".admin-meta-bs-desc[data-kind='column']");
        const desc = inp ? (inp.value || "").trim() : "";
        const orig = inp ? (inp.dataset.original || "") : "";
        if (desc && desc !== orig) {
          rows.push({
            schema_name: schemaName, table_name: tableName,
            column_name: colRow.dataset.column || "", description: desc,
            ordinal: idx + 1,
          });
        }
      });
    }
  });
  if (!rows.length) {
    if (typeof showToast === "function") showToast("저장할 변경(새 입력 또는 수정)이 없습니다.", true);
    return;
  }
  const saveBtn = document.getElementById("metadataBootstrapSaveBtn");
  if (saveBtn) saveBtn.disabled = true;
  bs.saving = true;
  _metaBootstrapStatus(`저장 중… (0/${rows.length})`);
  let ok = 0; let fail = 0;
  for (let i = 0; i < rows.length; i++) {
    const payload = { scope_key: scope, source: "bootstrap" };
    payload.schema_name = rows[i].schema_name;
    payload.table_name = rows[i].table_name;
    if (mode === "columns") {
      payload.column_name = rows[i].column_name;
      if (rows[i].ordinal != null) payload.ordinal = rows[i].ordinal;   // graphux5: 실제 컬럼 순서
    }
    payload.description = rows[i].description;
    try {
      await apiFetch(`/api/admin/metadata/${mode}`, { method: "POST", body: JSON.stringify(payload) });
      ok += 1;
    } catch (err) {
      fail += 1;
    }
    _metaBootstrapStatus(`저장 중… (${i + 1}/${rows.length})`);
  }
  bs.saving = false;
  if (saveBtn) saveBtn.disabled = false;
  _metaBootstrapStatus(`저장 완료 — 성공 ${ok}건${fail ? `, 실패 ${fail}건` : ""}`, fail > 0);
  if (typeof showToast === "function") {
    showToast(fail ? `저장 ${ok}건 성공, ${fail}건 실패` : `${ok}건 저장했습니다.`, fail > 0);
  }
  // metadata-bs-prefill: 저장 후 목록 + items 갱신 → (부트스트랩 모드면) loadMetadata 가 골격 입력란을
  // 갱신된 설명으로 재prefill 한다(방금 저장분 포함, dataset.original 도 최신값으로 재설정 → 중복 저장 방지).
  if (ok > 0) {
    await loadMetadata();
  }
}

// 부트스트랩 AI 일괄 자동완성 — 골격을 청크 단위로 백엔드에 보내 설명을 생성하고,
// 비어 있는 설명 입력란에만 채운다(사용자 수동 입력 보존). 생성물은 영속 안 함 — 기존
// '설명 입력분 저장' 으로만 저장된다. 청크 분할로 진행률 표면화 + 단일 호출 지연/부하 분산.
async function _metaBootstrapAiFill(btn) {
  const bs = adminState.metadata.bootstrap;
  const wrap = document.getElementById("metadataBootstrapResult");
  if (!wrap || !bs.tables || !bs.tables.length) {
    if (typeof showToast === "function") showToast("먼저 스키마 골격을 가져오세요.", true);
    return;
  }
  const mode = adminState.metadata.subTab === "columns" ? "columns" : "tables";
  const CHUNK = mode === "columns" ? 6 : 12;  // columns 는 출력량↑ → 청크 작게.
  const tables = bs.tables.map((t) => ({
    schema_name: t.schema_name || bs.schema || "",
    table_name: t.table_name || "",
    columns: Array.isArray(t.columns)
      ? t.columns.map((c) => (mode === "columns"
          ? { column_name: c.column_name, data_type: c.data_type }
          : { column_name: c.column_name }))
      : [],
  })).filter((t) => t.table_name);
  if (!tables.length) {
    if (typeof showToast === "function") showToast("처리할 테이블이 없습니다.", true);
    return;
  }
  const chunks = [];
  for (let i = 0; i < tables.length; i += CHUNK) chunks.push(tables.slice(i, i + CHUNK));

  const saveBtn = document.getElementById("metadataBootstrapSaveBtn");
  const origLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = "AI 생성 중…";
  if (saveBtn) saveBtn.disabled = true;
  bs.saving = true;
  let filled = 0;
  let done = 0;
  let failedTables = 0;
  try {
    for (const chunk of chunks) {
      _metaBootstrapStatus(`AI 생성 중… (${done}/${tables.length} 테이블, ${filled}건 채움)`);
      try {
        const data = await apiFetch("/api/admin/metadata/bootstrap/describe", {
          method: "POST",
          body: JSON.stringify({ mode, schema: bs.schema, tables: chunk }),
        });
        const results = (data && Array.isArray(data.results)) ? data.results : [];
        filled += _metaBootstrapApplyDescriptions(wrap, mode, results);
      } catch (err) {
        failedTables += chunk.length;
      }
      done += chunk.length;
    }
    if (failedTables) {
      _metaBootstrapStatus(
        `AI 자동완성: ${filled}건 채움 · 테이블 ${failedTables}개 실패. 빈 칸만 채웠습니다.`,
        failedTables >= tables.length,
      );
    } else {
      _metaBootstrapStatus(`AI 자동완성 완료: ${filled}건 채움. 검토 후 '설명 입력분 저장' 을 누르세요.`);
    }
    if (typeof showToast === "function" && filled) {
      showToast(`AI 가 ${filled}건의 설명을 채웠습니다 — 검토 후 저장하세요.`);
    } else if (typeof showToast === "function" && !filled) {
      showToast("채울 빈 칸이 없거나 생성 결과가 비었습니다.", true);
    }
  } finally {
    bs.saving = false;
    btn.disabled = false;
    btn.textContent = origLabel;
    if (saveBtn) saveBtn.disabled = false;
    // metadata-bs-collapse: 프로그램적 value 설정 후 접힌 헤더 힌트(설명 유무/채움 수) 갱신.
    _metaBootstrapRefreshAllHints(mode);
  }
}

// AI 결과를 비어 있는 설명 입력란에만 채운다(수동 입력 보존). 반환=채운 건수. (XSS: input.value 로만.)
function _metaBootstrapApplyDescriptions(wrap, mode, results) {
  let n = 0;
  const blocks = Array.from(wrap.querySelectorAll(".admin-meta-bs-table"));
  for (const r of results) {
    if (!r || !r.description) continue;
    const block = blocks.find((b) =>
      (b.dataset.table || "") === (r.table_name || "") &&
      (!r.schema_name || !b.dataset.schema || b.dataset.schema === r.schema_name));
    if (!block) continue;
    if (mode === "tables") {
      const inp = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
      if (inp && !(inp.value || "").trim()) { inp.value = String(r.description); n += 1; }
    } else {
      const rows = Array.from(block.querySelectorAll(".admin-meta-bs-col"));
      const row = rows.find((rw) => (rw.dataset.column || "") === (r.column_name || ""));
      const inp = row ? row.querySelector(".admin-meta-bs-desc[data-kind='column']") : null;
      if (inp && !(inp.value || "").trim()) { inp.value = String(r.description); n += 1; }
    }
  }
  return n;
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

// conn-health 3단계 status → 사람-친화 한글 라벨(상세 패널 "연결 상태" 행). 배지 텍스트("연결 정상/
// 불안정/끊김", admin.js ~1290)와 어휘 정합. background 모니터 사전계산값(snapshot)을 그대로 반영.
function _dsConnStatusLabel(status) {
  switch (String(status || "").toLowerCase()) {
    case "healthy":  return "정상 (연결 성공)";
    case "unstable": return "불안정 (느리거나 간헐적)";
    case "down":     return "끊김 (도달 불가)";
    default:         return "확인 중";
  }
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

  // 연결 상태 · 응답 시간 — background conn_health 모니터가 미리 계산한 값(추가 probe·연결테스트 불필요).
  //   핵심: "연결 응답 시간(평균)" = 최근 sample_count(≤AGENT_CONN_AVG_WINDOW)회 성공 DB probe elapsed 의
  //   산술평균(ms). 순간값(최근 응답 시간)보다 대표성이 높아 데이터소스별 상시 연결 품질을 나타낸다.
  //   표본이 아직 없으면(신규·연속 실패) "측정 중". conn_status 는 API(admin_datasources)가 첨부.
  const cs = ds.conn_status || null;
  const sec3 = document.createElement("div"); sec3.className = "admin-detail-section";
  const t3 = document.createElement("div"); t3.className = "admin-detail-section-title"; t3.textContent = "연결 상태"; sec3.appendChild(t3);
  const dl3 = document.createElement("dl"); dl3.className = "admin-kv";
  _dsKvRow(dl3, "상태", _dsConnStatusLabel(cs && cs.status));
  if (cs && cs.avg_elapsed_ms != null) {
    const n = Number(cs.sample_count || 0);
    _dsKvRow(dl3, "연결 응답 시간(평균)", n > 1 ? `${cs.avg_elapsed_ms} ms · 최근 ${n}회 평균` : `${cs.avg_elapsed_ms} ms`);
  } else {
    _dsKvRow(dl3, "연결 응답 시간(평균)", "측정 중 (연결 성공 시 집계)");
  }
  // 참고값: 마지막 1회 응답 시간(순간값) + 마지막 확인 시각(epoch 초 → ms 변환).
  //   `> 0` 가드(평균 행과 동일): foreground 성공 피드백은 elapsed 미측정(0.0-coerce)이라 "0 ms" 로
  //   표시되면 평균값(예: 45ms)과 모순돼 보인다 → 0/음수 순간값은 표시 생략(background probe 값만 노출).
  if (cs && cs.elapsed_ms != null && cs.elapsed_ms > 0) _dsKvRow(dl3, "최근 응답 시간", `${cs.elapsed_ms} ms`);
  if (cs && cs.checked_at) _dsKvRow(dl3, "마지막 확인", formatDateTime(Number(cs.checked_at) * 1000));
  sec3.appendChild(dl3);
  detailEl.appendChild(sec3);

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
  // feature-0018: 실행 타임아웃 / 모델별 추론 예산 — 각자 전용 UI, 레거시 admin-settings-panel 정합.
  "runtime-timeouts": mountRuntimeTimeoutsPanel,
  "model-thinking-budgets": mountModelThinkingBudgetsPanel,
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

/* ── feature-0018: 런타임 설정 (실행 타임아웃 · 모델별 추론 예산) ────────────
 * 백엔드: GET/PUT/DELETE /api/admin/settings/runtime (shared.runtime_settings 레지스트리).
 * 값은 서버에서 스펙 [min,max] 범위로 검증되며, 저장 시 즉시(live)/재배포(restart) 반영된다.
 * 두 패널 모두 read 게이트 system.runtime.read, write 게이트 system.runtime.write. */

const RUNTIME_SETTINGS_ENDPOINT = "/api/admin/settings/runtime";
const RS_RESET = "__reset__";  // pending sentinel — 기본값 복원(DELETE) 예약
const RS_MODEL_PREFIX = "model_thinking_budget:";

function rsApplyBadge(applyMode) {
  const span = document.createElement("span");
  if (applyMode === "live") {
    span.className = "admin-badge rs-badge";
    span.textContent = "즉시 반영";
    span.title = "저장 즉시 실행 경로에 반영됩니다(최대 수십 초 캐시).";
  } else {
    span.className = "admin-badge admin-badge--warn rs-badge";
    span.textContent = "재배포 반영";
    span.title = "저장은 즉시 되지만, 실제 적용은 다음 배포/재시작 시점입니다(저수준 값 안전).";
  }
  return span;
}

function rsUnitSuffix(unit) {
  if (unit === "초") return "초";
  if (unit === "밀리초") return "ms";
  if (unit === "tokens") return "tokens";
  return unit || "";
}

async function rsSaveValue(key, value) {
  return apiFetch(RUNTIME_SETTINGS_ENDPOINT, {
    method: "PUT",
    body: JSON.stringify({ key, value }),
  });
}

async function rsResetValue(key) {
  return apiFetch(`${RUNTIME_SETTINGS_ENDPOINT}?key=${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

// 값 편집·기본값복원을 commit-bar("모두 적용")로 예약한다 — 즉시 API 호출 없음(계정·시스템
// 프롬프트와 동일한 콘솔 네이티브 패턴). value: 정수(PUT) | RS_RESET(DELETE) | null(예약 취소).
function setRuntimeSettingPending(key, value) {
  if (!adminState.pending.runtimeSettings) adminState.pending.runtimeSettings = new Map();
  if (value === null) adminState.pending.runtimeSettings.delete(key);
  else adminState.pending.runtimeSettings.set(key, { key, value });
  refreshPendingUI();
}

// 현재 mount 된 런타임 설정 패널을 재렌더(모두 적용/취소 후 서버 상태 재반영).
function rerenderRuntimeSettingsPanels() {
  const t = $("runtimeTimeoutsMount");
  if (t && adminState.settings.mountedPanels.has("runtime-timeouts")) renderRuntimeTimeouts(t);
  const m = $("modelThinkingBudgetsMount");
  if (m && adminState.settings.mountedPanels.has("model-thinking-budgets")) renderModelThinkingBudgets(m);
}

// 정렬 grid 행(라벨+배지 / 설명 / 입력+단위 / 상태·기본값). timeouts·models 공용.
// 저장/초기화 버튼 없음 — 편집은 pending 예약, 적용은 하단 commit-bar.
function buildRuntimeSettingRow(item, canWrite, opts) {
  // emptyWhenNoOverride: 모델 예산 전용 — override 없으면 런타임이 값을 주입하지 않으므로(effective=
  // 표시 기준일 뿐 실제 적용값 아님) input 을 비우고 placeholder 로 기본값 표시(무변경 예약 트랩 방지).
  const emptyWhenNoOverride = !!(opts && opts.emptyWhenNoOverride);
  const unknownBaseline = emptyWhenNoOverride && item.default_known === false;
  const baseLabel = unknownBaseline ? "모델 기본값" : `${item.default}${rsUnitSuffix(item.unit)}`;
  const noOverrideEmpty = emptyWhenNoOverride && !item.has_override;

  const row = document.createElement("div");
  row.className = "rs-row";
  row.dataset.settingKey = item.key;

  const label = document.createElement("div");
  label.className = "rs-row-label";
  const name = document.createElement("span");
  name.textContent = item.label || item.model || item.key;
  label.append(name, rsApplyBadge(item.apply_mode));

  const desc = document.createElement("div");
  desc.className = "rs-row-desc";
  desc.textContent = (emptyWhenNoOverride && !item.default_known)
    ? "미설정 시 모델 config 의 기본 thinking 을 그대로 사용합니다."
    : (item.description || "");
  desc.title = desc.textContent;

  const control = document.createElement("div");
  control.className = "rs-row-control";
  const input = document.createElement("input");
  input.type = "number";
  input.className = "rs-input";
  input.min = String(item.minimum);
  input.max = String(item.maximum);
  input.step = "1";
  input.setAttribute("aria-label", `${item.label || item.model || item.key} 값`);
  if (noOverrideEmpty) { input.value = ""; input.placeholder = String(item.default); }
  else input.value = String(item.effective);
  if (!canWrite) input.disabled = true;
  const unit = document.createElement("span");
  unit.className = "rs-unit";
  unit.textContent = rsUnitSuffix(item.unit);
  control.append(input, unit);

  const meta = document.createElement("div");
  meta.className = "rs-row-meta";
  const status = document.createElement("span");
  status.className = "rs-status";
  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.className = "rs-reset";
  resetBtn.textContent = "기본값";
  resetBtn.title = `${baseLabel}(으)로 되돌립니다.`;
  meta.append(status, resetBtn);

  row.append(label, control, desc, meta);

  function refresh() {
    input.classList.remove("is-invalid");
    const pend = adminState.pending.runtimeSettings.get(item.key);
    row.classList.toggle("is-pending", !!pend);
    if (pend && pend.value === RS_RESET) {
      status.textContent = "미저장 · 기본값 복원"; status.className = "rs-status is-pending";
      resetBtn.textContent = "되돌리기"; resetBtn.hidden = !canWrite;
    } else if (pend) {
      status.textContent = "미저장 변경"; status.className = "rs-status is-pending";
      resetBtn.textContent = "되돌리기"; resetBtn.hidden = !canWrite;
    } else if (item.has_override) {
      status.textContent = `사용자 지정 · 기본 ${baseLabel}`; status.className = "rs-status is-override";
      resetBtn.textContent = "기본값"; resetBtn.hidden = !canWrite;
    } else {
      status.textContent = `기본값 ${baseLabel}`; status.className = "rs-status";
      resetBtn.hidden = true;
    }
  }
  refresh();

  if (canWrite) {
    input.addEventListener("change", () => {
      const raw = input.value.trim();
      if (raw === "") {
        // 빈 값 → 예약 취소(원상). 모델 no-override 는 빈 값이 정상 상태.
        setRuntimeSettingPending(item.key, null);
        input.value = noOverrideEmpty ? "" : String(item.effective);
        refresh();
        return;
      }
      const val = Math.trunc(Number(raw));
      if (!Number.isFinite(val)) {
        setRuntimeSettingPending(item.key, null);
        input.value = noOverrideEmpty ? "" : String(item.effective);
        refresh();
        return;
      }
      if (val < item.minimum || val > item.maximum) {
        // 범위 밖: 예약하지 않고 인라인 경고(서버 검증 실패 예방).
        setRuntimeSettingPending(item.key, null);
        input.classList.add("is-invalid");
        status.textContent = `허용 범위 ${item.minimum}~${item.maximum}`;
        status.className = "rs-status is-invalid";
        row.classList.remove("is-pending");
        // pending 이 해제됐으므로 reset 버튼 라벨을 no-pending 상태(기본값)로 되돌린다(라벨/동작 불일치 방지).
        resetBtn.textContent = "기본값";
        resetBtn.hidden = !(canWrite && item.has_override);
        return;
      }
      // 입력값이 서버 현재상태(effective)와 같으면 예약 불필요 — has_override 무관.
      // no-override 도 effective==기본값이므로 재-핀(override==default) 트랩을 함께 방지.
      if (val === item.effective) {
        setRuntimeSettingPending(item.key, null);
      } else {
        setRuntimeSettingPending(item.key, val);
      }
      refresh();
    });
    resetBtn.addEventListener("click", () => {
      const pend = adminState.pending.runtimeSettings.get(item.key);
      if (pend) {
        // 되돌리기: 예약 취소 + 서버 상태 표시 복원.
        setRuntimeSettingPending(item.key, null);
        input.value = noOverrideEmpty ? "" : String(item.effective);
        refresh();
        return;
      }
      if (!item.has_override) return;  // 복원할 override 없음
      // 기본값 복원(DELETE) 예약.
      setRuntimeSettingPending(item.key, RS_RESET);
      if (emptyWhenNoOverride) { input.value = ""; input.placeholder = String(item.default); }
      else input.value = String(item.default);
      refresh();
    });
  } else {
    resetBtn.hidden = true;
  }
  return row;
}

function rsErrorPlaceholder(mount, msg) {
  mount.innerHTML = "";
  const div = document.createElement("div");
  div.className = "admin-detail-empty";
  div.textContent = msg;
  mount.appendChild(div);
}

async function mountRuntimeTimeoutsPanel() {
  const mount = $("runtimeTimeoutsMount");
  if (!mount) return;
  if (!can("system.runtime.read")) {
    rsErrorPlaceholder(mount, "런타임 설정 조회 권한이 없습니다.");
    return;
  }
  await renderRuntimeTimeouts(mount);
}

async function renderRuntimeTimeouts(mount) {
  rsErrorPlaceholder(mount, "불러오는 중…");
  let data;
  try {
    data = await apiFetch(RUNTIME_SETTINGS_ENDPOINT);
  } catch (err) {
    rsErrorPlaceholder(mount, `조회 실패: ${err.message || err}`);
    return;
  }
  const canWrite = can("system.runtime.write");
  const items = Array.isArray(data.timeouts) ? data.timeouts : [];
  if (!items.length) { rsErrorPlaceholder(mount, "등록된 타임아웃 항목이 없습니다."); return; }
  mount.innerHTML = "";
  const panel = document.createElement("div");
  panel.className = "rs-panel";
  // category 순서 보존 그룹핑.
  const order = [];
  const byCat = new Map();
  for (const it of items) {
    const cat = it.category || "기타";
    if (!byCat.has(cat)) { byCat.set(cat, []); order.push(cat); }
    byCat.get(cat).push(it);
  }
  for (const cat of order) {
    const group = document.createElement("div");
    group.className = "rs-group";
    const gtitle = document.createElement("div");
    gtitle.className = "rs-group-title";
    gtitle.textContent = cat;
    const list = document.createElement("div");
    list.className = "rs-list";
    for (const it of byCat.get(cat)) list.appendChild(buildRuntimeSettingRow(it, canWrite));
    group.append(gtitle, list);
    panel.appendChild(group);
  }
  if (!canWrite) {
    const note = document.createElement("div");
    note.className = "rs-readonly-note";
    note.textContent = "조회 전용 — 수정 권한(system.runtime.write)이 없습니다.";
    panel.appendChild(note);
  }
  mount.appendChild(panel);
}

async function mountModelThinkingBudgetsPanel() {
  const mount = $("modelThinkingBudgetsMount");
  if (!mount) return;
  if (!can("system.runtime.read")) {
    rsErrorPlaceholder(mount, "런타임 설정 조회 권한이 없습니다.");
    return;
  }
  await renderModelThinkingBudgets(mount);
}

async function renderModelThinkingBudgets(mount) {
  rsErrorPlaceholder(mount, "불러오는 중…");
  let data;
  try {
    data = await apiFetch(RUNTIME_SETTINGS_ENDPOINT);
  } catch (err) {
    rsErrorPlaceholder(mount, `조회 실패: ${err.message || err}`);
    return;
  }
  const canWrite = can("system.runtime.write");
  const items = Array.isArray(data.model_thinking_budgets) ? data.model_thinking_budgets : [];
  if (!items.length) { rsErrorPlaceholder(mount, "extended thinking 을 지원하는 모델이 카탈로그에 없습니다."); return; }
  mount.innerHTML = "";
  const panel = document.createElement("div");
  panel.className = "rs-panel";
  const group = document.createElement("div");
  group.className = "rs-group";
  const gtitle = document.createElement("div");
  gtitle.className = "rs-group-title";
  gtitle.textContent = "모델별 thinking budget (tokens)";
  const list = document.createElement("div");
  list.className = "rs-list";
  for (const it of items) list.appendChild(buildRuntimeSettingRow(it, canWrite, { emptyWhenNoOverride: true }));
  group.append(gtitle, list);
  panel.appendChild(group);
  const note = document.createElement("div");
  note.className = "rs-readonly-note";
  note.textContent = canWrite
    ? "비워두거나 '기본값'으로 두면 해당 모델은 서버 기본 thinking 을 사용합니다(대화별 추론 강도 선택이 우선)."
    : "조회 전용 — 수정 권한(system.runtime.write)이 없습니다.";
  panel.appendChild(note);
  mount.appendChild(panel);
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
  // TASK-20260619T023922-audit-tamper-evidence (보안 ③): 무결성 검증 버튼 (audit.read.any 권한자만).
  const verifyBtn = $("auditVerifyBtn");
  if (verifyBtn) {
    verifyBtn.style.display = Boolean(adminState.me?.permissions?.["audit.read.any"]) ? "" : "none";
    if (!verifyBtn._wired) {
      verifyBtn._wired = true;
      verifyBtn.addEventListener("click", () => triggerAuditChainVerify());
    }
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

// TASK-20260619T023922-audit-tamper-evidence (보안 ③): 감사 해시 체인 무결성 검증.
async function triggerAuditChainVerify() {
  const btn = $("auditVerifyBtn");
  const out = $("auditVerifyResult");
  if (out) { out.style.display = ""; out.className = "admin-audit-verify-result"; out.textContent = "검증 중…"; }
  if (btn) btn.disabled = true;
  let res;
  try {
    res = await apiFetch("/api/admin/audits/verify");
  } catch (error) {
    if (out) { out.className = "admin-audit-verify-result is-error"; out.textContent = `검증 실패: ${error.message || error}`; }
    if (btn) btn.disabled = false;
    return;
  }
  if (btn) btn.disabled = false;
  if (!out) return;
  if (res && res.ok) {
    out.className = "admin-audit-verify-result is-ok";
    out.textContent = `✓ 무결성 정상 (${Number(res.verified_count) || 0}건 검증)`;
  } else {
    const br = (res && res.first_break) || {};
    const reasonMap = { unsealed: "미봉인", prev_hash_mismatch: "체인 링크 불일치", content_modified: "내용 변조" };
    out.className = "admin-audit-verify-result is-error";
    out.textContent = `⚠ 무결성 위반 — 이벤트 #${br.id || "?"} (${reasonMap[br.reason] || br.reason || "알 수 없음"})`;
  }
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
  adminState.pending.productDbRules.forEach((e, k) => {
    if (_dbRulePendingEntryEmpty(e)) return;
    const _ps = String(k).split("::");
    const id = Number(_ps[0]);
    const dk = (_ps.length > 1 ? _ps[1] : "");
    const base = adminState.products.find((p) => Number(p.id) === Number(id));
    const parts = [];
    if ((e.creates || []).length) parts.push(`추가 ${e.creates.length}`);
    const nu = Object.keys(e.updates || {}).length; if (nu) parts.push(`수정 ${nu}`);
    const nd = Object.keys(e.deletes || {}).length; if (nd) parts.push(`삭제 ${nd}`);
    const na = Object.values(e.approves || {}).reduce((s, a) => s + (a ? a.length : 0), 0); if (na) parts.push(`승인 ${na}`);
    addRow(`제품 규칙 · ${base ? base.name : `#${id}`}${dk ? ` · [${dk}]` : ""} · ${parts.join(" · ")}`);
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
  // TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 상태 배지.
  if (base.is_locked) badges.appendChild(statusBadge("잠김", "is-locked"));
  // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 사용 배지.
  if (base.totp_enabled) badges.appendChild(statusBadge("2FA", "is-2fa"));
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

    // TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 해제 버튼 (잠긴 계정에만 노출).
    // 비밀번호 변경 없이 잠금만 해제 — 표적 DoS 회복 경로.
    if (base.is_locked) {
      const unlockBtn = document.createElement("button");
      unlockBtn.type = "button";
      unlockBtn.id = "adminUnlockBtn";
      unlockBtn.className = "btn-secondary";
      unlockBtn.textContent = "잠금 해제";
      unlockBtn.title = "로그인 실패로 잠긴 계정의 잠금을 즉시 해제합니다 (비밀번호 변경 없음).";
      unlockBtn.addEventListener("click", () => triggerAccountUnlockFlow(base));
      actions.appendChild(unlockBtn);
    }

    // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 강제 해제 버튼 (2FA 사용 계정에만).
    // 분실 디바이스 복구 — 비밀번호 변경 없이 2FA 만 제거.
    if (base.totp_enabled) {
      const totpBtn = document.createElement("button");
      totpBtn.type = "button";
      totpBtn.id = "adminTotpDisableBtn";
      totpBtn.className = "btn-secondary";
      totpBtn.textContent = "2FA 해제";
      totpBtn.title = "기기 분실 등으로 2단계 인증을 풀어줍니다 (비밀번호 변경 없음). 사용자가 재설정해야 합니다.";
      totpBtn.addEventListener("click", () => triggerAccountTotpDisableFlow(base));
      actions.appendChild(totpBtn);
    }
  }

  // TASK-20260623T014626-quota-ui-relocate: 계정 특수 LLM 사용 한도 (감사>LLM 사용량에서 이전).
  // TASK-20260623T030418-quota-rbac-permission: 표시=quota.read, 편집=quota.manage(없으면 readOnly).
  //   조회 권한 없으면 섹션 자체 미렌더(account.update 종속 제거 — 한도는 독립 권한).
  if (!base.deleted_at && !merged._isNew && can("quota.read")) {
    const roleObj = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
    const roleName = roleObj ? (roleObj.name || roleObj.key) : "역할";
    const fmtInherit = (v) => (v === null || v === undefined ? "무제한" : `${Number(v).toLocaleString()} 토큰`);
    const inheritNote = roleObj
      ? `비워 두면 ‘${roleName}’ 역할 기본값을 따릅니다 (현재 역할 기본 — 일일 ${fmtInherit(roleObj.quota_daily)} · 월간 ${fmtInherit(roleObj.quota_monthly)}).`
      : "비워 두면 역할 기본값을 따릅니다.";
    const qSection = document.createElement("div");
    qSection.className = "admin-detail-section";
    const qTitle = document.createElement("div");
    qTitle.className = "admin-detail-section-title";
    qTitle.textContent = "LLM 사용 한도 (계정 개별 지정)";
    qSection.appendChild(qTitle);
    qSection.appendChild(buildQuotaEditor({
      scope: "account",
      id: base.id,
      daily: base.quota_daily,
      monthly: base.quota_monthly,
      inheritNote: inheritNote,
      readOnly: !can("quota.manage"),
      onSaved: async () => { await loadAdminData(); renderAccountDetail(); },
    }));
    paneEl.appendChild(qSection);
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 관리자 2FA 강제 해제 flow.
async function triggerAccountTotpDisableFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(`${account.username} 계정의 2단계 인증을 해제하시겠습니까?\n사용자는 비밀번호로 로그인 후 다시 설정해야 합니다.`)) return;
  try {
    await apiFetch(`/api/admin/accounts/${Number(account.id)}/totp/disable`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`2FA 해제 실패: ${error.message || error}`, true);
    return;
  }
  showToast(`${account.username} 계정의 2단계 인증을 해제했습니다.`);
  await loadAdminData();
  renderAccountDetail();
}

// TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 즉시 해제 flow.
async function triggerAccountUnlockFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(`${account.username} 계정의 로그인 잠금을 해제하시겠습니까?`)) return;
  try {
    await apiFetch(`/api/admin/accounts/${Number(account.id)}/unlock`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`잠금 해제 실패: ${error.message || error}`, true);
    return;
  }
  showToast(`${account.username} 계정의 잠금을 해제했습니다.`);
  await loadAdminData();
  renderAccountDetail();
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

  // TASK-20260623T014626-quota-ui-relocate: 역할 기본 LLM 사용 한도 (감사>LLM 사용량에서 이전).
  // TASK-20260623T030418-quota-rbac-permission: 표시=quota.read, 편집=quota.manage(없으면 readOnly).
  if (!merged._isNew && !merged._delete && can("quota.read")) {
    const qSection = document.createElement("div");
    qSection.className = "admin-detail-section";
    const qTitle = document.createElement("div");
    qTitle.className = "admin-detail-section-title";
    qTitle.textContent = "LLM 사용 한도 (역할 기본)";
    qSection.appendChild(qTitle);
    const qHint = document.createElement("p");
    qHint.className = "admin-detail-section-hint";
    qHint.textContent = "이 역할에 속한 계정들의 기본 토큰 한도입니다. 계정별로 다르게 지정하려면 ‘계정’ 상세에서 개별 한도를 설정하세요.";
    qSection.appendChild(qHint);
    qSection.appendChild(buildQuotaEditor({
      scope: "role",
      id: merged.id,
      daily: merged.quota_daily,
      monthly: merged.quota_monthly,
      readOnly: !can("quota.manage"),
      onSaved: async () => { await loadAdminData(); renderRoleDetail(); },
    }));
    paneEl.appendChild(qSection);
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
  const ruleDirty = productDbRuleDirtyCount();
  if (ruleDirty) detail.push(`제품 규칙 ${ruleDirty}`);
  if (adminState.pending.systemPrompts.size) detail.push(`프롬프트 ${adminState.pending.systemPrompts.size}`);
  // feature-0018 UX: 런타임 설정 pending 요약 + 설정 pane 좌측 nav row dirty 표시.
  const rsPending = adminState.pending.runtimeSettings || new Map();
  if (rsPending.size) detail.push(`설정 ${rsPending.size}`);
  let rsTimeoutDirty = false, rsModelDirty = false;
  rsPending.forEach((_v, k) => {
    if (String(k).startsWith(RS_MODEL_PREFIX)) rsModelDirty = true; else rsTimeoutDirty = true;
  });
  // 설정 nav row: `.has-pending` 테두리 + `.admin-pending-dot`(계정·역할 row 와 일관 — 색 외 신호).
  const markSettingsNav = (tab, dirty) => {
    const btn = document.querySelector(`#settingsList [data-settings-tab="${tab}"]`);
    if (!btn) return;
    btn.classList.toggle("has-pending", dirty);
    const nameEl = btn.querySelector(".admin-list-row-name");
    if (!nameEl) return;
    let dot = nameEl.parentElement.querySelector(".admin-pending-dot");
    if (!dot) {
      dot = document.createElement("span");
      dot.className = "admin-pending-dot";
      dot.title = "미저장 변경 있음";
      nameEl.after(dot);
    }
    dot.textContent = dirty ? "•" : "";
  };
  markSettingsNav("runtime-timeouts", rsTimeoutDirty);
  markSettingsNav("model-thinking-budgets", rsModelDirty);
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
  const runtimeSettingEntries = Array.from((adminState.pending.runtimeSettings || new Map()).entries());
  // TASK-0239: datasource 바인딩 — desired≠baseline 인 제품만(실제 변경).
  const datasourceEntries = Array.from(adminState.pending.productDatasources.entries())
    .filter(([, e]) => e && !_dsBindEqual(e.baseline, e.desired));
  // TASK-20260619 (§10.7): 정규식 자동 규칙 편집 — 비어있지 않은 (product, datasource) 만.
  const dbRuleEntries = Array.from(adminState.pending.productDbRules.entries())
    .filter(([, e]) => !_dbRulePendingEntryEmpty(e));

  if (
    !accountEntries.length
    && !roleEntries.length
    && !newRoleEntries.length
    && !productMetaEntries.length
    && !productDbEntries.length
    && !datasourceEntries.length
    && !dbRuleEntries.length
    && !systemPromptEntries.length
    && !runtimeSettingEntries.length
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

  // TASK-20260619 (§10.7): 정규식 자동 규칙 편집(추가/수정/승인/삭제)을 일괄 확정.
  //  순서: ① 추가(POST) → ② 수정(PUT) → ③ 승인(approve-pending) → ④ 삭제(DELETE, 마지막 — 다른
  //  op 의 rule_id 참조 보존). 각 엔드포인트는 확정 시점에 reconcile 하므로 여기가 allowlist 적용 지점.
  for (const [k, e] of dbRuleEntries) {
    const _ps = String(k).split("::");
    const pid = Number(_ps[0]);
    const dsk = _ps.length > 1 ? _ps[1] : "";
    const ruleBase = `/api/admin/products/${pid}/datasources/${encodeURIComponent(dsk)}/db-rules`;
    let entryFailed = false;
    for (const c of (e.creates || [])) {
      try {
        await apiFetch(ruleBase, { method: "POST", body: JSON.stringify({
          include_pattern: c.include_pattern, exclude_pattern: c.exclude_pattern || "", cap: Number(c.cap) || 3 }) });
        ok += 1;
      } catch (error) { entryFailed = true; failures.push({ kind: "product_db_rule", id: pid, error }); }
    }
    for (const [ruleId, patch] of Object.entries(e.updates || {})) {
      try {
        await apiFetch(`${ruleBase}/${Number(ruleId)}`, { method: "PUT", body: JSON.stringify({
          include_pattern: patch.include_pattern, exclude_pattern: patch.exclude_pattern || "", cap: Number(patch.cap) || 3 }) });
        ok += 1;
      } catch (error) { entryFailed = true; failures.push({ kind: "product_db_rule", id: pid, error }); }
    }
    for (const [ruleId, schemas] of Object.entries(e.approves || {})) {
      if (!schemas || !schemas.length) continue;
      try {
        await apiFetch(`${ruleBase}/${Number(ruleId)}/approve-pending`, { method: "POST", body: JSON.stringify({ schemas }) });
        ok += 1;
      } catch (error) { entryFailed = true; failures.push({ kind: "product_db_rule", id: pid, error }); }
    }
    for (const [ruleId, meta] of Object.entries(e.deletes || {})) {
      try {
        const q = (meta && meta.strip) ? "?strip=1" : "";
        await apiFetch(`${ruleBase}/${Number(ruleId)}${q}`, { method: "DELETE" });
        ok += 1;
      } catch (error) { entryFailed = true; failures.push({ kind: "product_db_rule", id: pid, error }); }
    }
    if (!entryFailed) adminState.pending.productDbRules.delete(k);
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

  // feature-0018 UX: 런타임 설정(실행 타임아웃·모델 추론 예산) — 값 PUT / 기본값복원 DELETE.
  for (const [key, entry] of runtimeSettingEntries) {
    try {
      if (entry.value === RS_RESET) await rsResetValue(key);
      else await rsSaveValue(key, entry.value);
      adminState.pending.runtimeSettings.delete(key);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "runtime_setting", id: key, error });
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
  // feature-0018 UX: 설정 패널은 lazy-mount 라 loadAdminData 로 갱신되지 않는다 — 런타임 설정이
  // 실제 적용됐을 때만 명시 재렌더(불필요한 재-fetch 방지).
  if (runtimeSettingEntries.length && typeof rerenderRuntimeSettingsPanels === "function") {
    rerenderRuntimeSettingsPanels();
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
  adminState.pending.productDbRules.clear();
  adminState.pending.systemPrompts.clear();
  const hadRuntimePending = !!(adminState.pending.runtimeSettings && adminState.pending.runtimeSettings.size);
  if (adminState.pending.runtimeSettings) adminState.pending.runtimeSettings.clear();
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
  // feature-0018 UX: 런타임 설정 예약이 있었을 때만 패널 원상 복원(불필요한 재-fetch 방지).
  if (hadRuntimePending && typeof rerenderRuntimeSettingsPanels === "function") rerenderRuntimeSettingsPanels();
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
  // TASK-20260619: 삭제된 제품의 정규식 자동 규칙 pending GC(키 `productId::dsKey`).
  Array.from(adminState.pending.productDbRules.keys()).forEach((k) => {
    if (!productIds.has(Number(String(k).split("::")[0]))) adminState.pending.productDbRules.delete(k);
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
      // TASK-20260618T061703: 규칙(rule) 행은 이 메인 목록이 아니라 각 규칙 카드에 종속 표시 → 여기선 제외.
      //   (manual 수동 추가 DB 만 이 목록에 남긴다.)
      // feature-0003-rule-db-coverage: 단, 규칙 카드(_renderRuleEditor)는 canManage 일 때만 렌더된다.
      //   read-only 뷰어(product.read 만, product.manage 없음)는 규칙 카드를 못 보므로, 그 경우엔
      //   규칙 DB 도 이 메인 목록에 남겨 분석 여부·완료율이 어디서든 노출되게 한다(요청 불변식).
      const _isRuleRow = String((entry && entry.source) || "manual") === "rule";
      if (_isRuleRow && canManage) return;
      const rowEl = document.createElement("div");
      rowEl.className = "cov-db-row";
      const covRow = covByDb.get(String(entry.schema_name).toLowerCase()) || null;
      if (covRow && covRow.connected === false) rowEl.classList.add("is-offline");

      const nameEl = document.createElement("span");
      nameEl.className = "cov-db-name";
      nameEl.textContent = entry.schema_name;
      nameEl.title = entry.schema_name;
      rowEl.appendChild(nameEl);

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

  // ── TASK-20260618T044318 / TASK-20260619: 정규식 자동 규칙 에디터 ──
  //  규칙을 한 번 확정하면 데이터소스 DB 변화 시 일치 DB 가 (반)자동 반영된다(cap 이하·명확=자동,
  //  초과·권한보류=pending 승인). allowlist 는 보안 경계.
  //  TASK-20260619 (§10.7): 규칙 추가/수정/삭제/승인은 즉시 서버 반영하지 않고 adminState.pending
  //  .productDbRules 에 스테이징한다. footer "모두 적용"(applyAllPending)이 일괄 확정한다. 읽기성
  //  preview 만 즉시 호출. (확정된 규칙의 백그라운드 자동 동기화는 보존 = 범위 A.)
  const ruleWrap = document.createElement("div");
  ruleWrap.className = "cov-db-rule";
  dbEditorWrap.appendChild(ruleWrap);

  // TASK-20260618T061703: 다중 규칙 — (product, datasource) 당 여러 규칙. 각 규칙 카드에 그 규칙이
  //  추가한 DB 를 중첩 표시(DB 가 규칙에 종속돼 보이게). manual DB 는 위 cov-db-list 에 그대로.
  let _renderRuleEditor = () => {};
  if (canManage) {
    let _ruleTempSeq = 1;  // staged create 임시 id 시퀀스(이 카드의 추가-대기 식별).
    const _ruleBase = () => `/api/admin/products/${product.id}/datasources/${encodeURIComponent(String(_editDsKey || "").trim().toLowerCase())}/db-rules`;
    // 정규식 입력 폼(추가/수정 공용). onSubmit(payload) 반환 시 호출. existing=수정 대상 규칙(없으면 추가).
    const _buildRuleForm = (existing, onSubmit, submitLabel) => {
      const form = document.createElement("div"); form.className = "cov-db-rule-form";
      const incInput = document.createElement("input");
      incInput.type = "text"; incInput.className = "cov-db-rule-input cov-db-rule-include";
      incInput.placeholder = "포함 정규식… 예: ^prod_|_live$"; incInput.value = (existing && existing.include_pattern) || "";
      const excInput = document.createElement("input");
      excInput.type = "text"; excInput.className = "cov-db-rule-input cov-db-rule-exclude";
      excInput.placeholder = "제외 정규식(선택)… 예: _bak$"; excInput.value = (existing && existing.exclude_pattern) || "";
      const capInput = document.createElement("input");
      capInput.type = "number"; capInput.className = "cov-db-rule-cap"; capInput.min = "1"; capInput.max = "100";
      capInput.value = String((existing && existing.cap) || 3);
      capInput.title = "한 번에 자동 적용할 최대 신규 DB 수(초과 시 승인 대기)";
      const countEl = document.createElement("span"); countEl.className = "cov-db-rule-count";
      const okBtn = document.createElement("button"); okBtn.type = "button"; okBtn.className = "cov-db-rule-save"; okBtn.textContent = submitLabel;
      const errEl = document.createElement("div"); errEl.className = "cov-db-rule-err hidden";
      const row1 = document.createElement("div"); row1.className = "cov-db-rule-row"; row1.append(incInput);
      const row2 = document.createElement("div"); row2.className = "cov-db-rule-row"; row2.append(excInput);
      const row3 = document.createElement("div"); row3.className = "cov-db-rule-row";
      const capLbl = document.createElement("label"); capLbl.className = "cov-db-rule-caplbl"; capLbl.textContent = "자동 적용 한도"; capLbl.appendChild(capInput);
      row3.append(capLbl, countEl, okBtn);
      form.append(row1, row2, row3, errEl);
      let _pvTimer = null;
      const _doPreview = async () => {
        const inc = incInput.value.trim();
        if (!inc) { countEl.textContent = ""; errEl.classList.add("hidden"); return; }
        try {
          const r = await apiFetch(`${_ruleBase()}/preview`,
            { method: "POST", body: JSON.stringify({ include_pattern: inc, exclude_pattern: excInput.value.trim() }) });
          if (r && r.ok) { countEl.textContent = `${r.matched_count}개 일치 · 신규 ${r.new_count}개`; errEl.classList.add("hidden"); }
          else { countEl.textContent = ""; errEl.textContent = (r && r.error) || "정규식 오류"; errEl.classList.remove("hidden"); }
        } catch (e) { /* keep */ }
      };
      const _sch = () => { if (_pvTimer) clearTimeout(_pvTimer); _pvTimer = setTimeout(_doPreview, 350); };
      incInput.addEventListener("input", _sch); excInput.addEventListener("input", _sch);
      _doPreview();
      okBtn.addEventListener("click", async () => {
        const inc = incInput.value.trim();
        if (!inc) { errEl.textContent = "포함 정규식을 입력하세요."; errEl.classList.remove("hidden"); return; }
        okBtn.disabled = true;
        try {
          await onSubmit({ include_pattern: inc, exclude_pattern: excInput.value.trim(), cap: Number(capInput.value) || 3 });
        } catch (e) { errEl.textContent = "실패: " + (e.message || "오류"); errEl.classList.remove("hidden"); okBtn.disabled = false; }
      });
      return form;
    };
    // 한 규칙 카드: 요약/수정 토글 + 그 규칙이 추가한 DB(중첩) + 그 규칙의 pending.
    //  TASK-20260619: 스테이징 오버레이 — 수정 대기는 새 패턴/한도를, 삭제 대기는 dim + 취소 버튼을,
    //  pending 승인은 승인 대기/취소 토글을 반영. 실제 반영은 "모두 적용".
    const _buildRuleCard = (rule, idx) => {
      const dsk = String(_editDsKey || "").trim().toLowerCase();
      const e = _getDbRulePending(product.id, _editDsKey);
      const upd = e && e.updates[String(rule.id)];      // 수정 대기 패치(있으면 화면에 반영).
      const del = !!(e && e.deletes[String(rule.id)]);  // 삭제 대기 여부.
      const view = upd || rule;                         // 표시 패턴/한도 = 스테이징 우선.
      const card = document.createElement("div");
      card.className = "cov-db-rule-card" + (del ? " is-staged-delete" : (upd ? " is-staged-update" : ""));
      // 헤더(요약 + 수정/삭제 또는 취소 + 대기 배지).
      const hd = document.createElement("div"); hd.className = "cov-db-rule-card-head";
      const title = document.createElement("span"); title.className = "cov-db-rule-card-title";
      title.textContent = `규칙 ${idx + 1}`;
      const pat = document.createElement("code"); pat.className = "cov-db-rule-card-pat";
      pat.textContent = view.include_pattern + (view.exclude_pattern ? `  (제외: ${view.exclude_pattern})` : "");
      const capPill = document.createElement("span"); capPill.className = "cov-db-rule-card-cap"; capPill.textContent = `한도 ${view.cap}`;
      hd.append(title, pat, capPill);
      if (del || upd) {
        const badge = document.createElement("span");
        badge.className = "cov-db-rule-card-badge " + (del ? "is-delete" : "is-update");
        badge.textContent = del ? "삭제 대기" : "수정 대기";
        hd.appendChild(badge);
      }
      const editHost = document.createElement("div"); editHost.className = "cov-db-rule-edit-host hidden";
      if (del) {
        const undo = document.createElement("button"); undo.type = "button"; undo.className = "cov-db-rule-edit"; undo.textContent = "삭제 취소";
        undo.addEventListener("click", () => {
          const ee = _ensureDbRulePending(product.id, _editDsKey);
          delete ee.deletes[String(rule.id)];
          _settleDbRulePending(product.id, _editDsKey);
          _renderRuleEditor();
        });
        hd.appendChild(undo);
      } else {
        const editBtn = document.createElement("button"); editBtn.type = "button"; editBtn.className = "cov-db-rule-edit"; editBtn.textContent = "수정";
        const delBtn = document.createElement("button"); delBtn.type = "button"; delBtn.className = "cov-db-rule-del"; delBtn.textContent = "삭제";
        hd.append(editBtn, delBtn);
        if (upd) {
          const undo = document.createElement("button"); undo.type = "button"; undo.className = "cov-db-rule-edit"; undo.textContent = "수정 취소";
          undo.addEventListener("click", () => {
            const ee = _ensureDbRulePending(product.id, _editDsKey);
            delete ee.updates[String(rule.id)];
            _settleDbRulePending(product.id, _editDsKey);
            _renderRuleEditor();
          });
          hd.appendChild(undo);
        }
        editBtn.addEventListener("click", () => {
          if (!editHost.classList.contains("hidden")) { editHost.classList.add("hidden"); editHost.innerHTML = ""; return; }
          editHost.innerHTML = "";
          editHost.appendChild(_buildRuleForm(view, (payload) => {
            const ee = _ensureDbRulePending(product.id, _editDsKey);
            ee.updates[String(rule.id)] = { ...payload };
            _settleDbRulePending(product.id, _editDsKey);
            showToast("규칙 수정 대기 — '모두 적용' 시 반영됩니다.");
            _renderRuleEditor();
          }, "수정 대기"));
          editHost.classList.remove("hidden");
        });
        delBtn.addEventListener("click", () => {
          if (!confirm(`'규칙 ${idx + 1}' (${rule.include_pattern}) 을 삭제 대기에 담을까요?`)) return;
          const strip = confirm("이 규칙이 추가한 DB 접근 행도 함께 삭제할까요?\n확인=행도 삭제 · 취소=규칙만 삭제(행 유지)\n('모두 적용' 시 실제 반영)");
          const ee = _ensureDbRulePending(product.id, _editDsKey);
          delete ee.updates[String(rule.id)];   // 수정 대기와 상충 — 삭제가 우선.
          delete ee.approves[String(rule.id)];  // 승인 대기도 정리 — 삭제될 규칙의 pending 승인은 무의미(리뷰 minor#1).
          ee.deletes[String(rule.id)] = { strip: !!strip };
          _settleDbRulePending(product.id, _editDsKey);
          showToast("규칙 삭제 대기 — '모두 적용' 시 반영됩니다.");
          _renderRuleEditor();
        });
      }
      card.appendChild(hd);
      card.appendChild(editHost);
      if (del) return card;  // 삭제 대기 카드는 종속 DB/pending 영역 생략(곧 사라질 규칙).
      // 이 규칙이 추가한 DB(종속 중첩 표시).
      const dbWrap = document.createElement("div"); dbWrap.className = "cov-db-rule-dblist";
      const ruleDbs = (product.databases || []).filter((d) =>
        String(d.datasource_key || "").trim().toLowerCase() === dsk && Number(d.rule_id) === Number(rule.id));
      const dbHead = document.createElement("div"); dbHead.className = "cov-db-rule-dblist-head";
      dbHead.textContent = `이 규칙으로 추가된 DB ${ruleDbs.length}개`;
      dbWrap.appendChild(dbHead);
      if (ruleDbs.length) {
        // feature-0003-rule-db-coverage: 규칙으로 추가된 DB 도 수동 등록 DB(메인 목록)와 동일하게
        //   insight 분석 여부(DB✓/✗)·완료율(테이블 ta/tt 마이크로바)을 표시한다. 백엔드
        //   per_db[] 는 Source(manual/rule) 무관 전체 접근 DB 의 coverage 를 담으므로
        //   (app.py _compute_product_insight_coverage), 여기서 db명으로 1:1 매칭만 하면 된다.
        const _ruleCov = adminState.productCoverage.get(Number(product.id));
        const _ruleCovByDb = new Map();
        if (_ruleCov && Array.isArray(_ruleCov.per_db)) {
          _ruleCov.per_db.forEach((c) => { if (c && c.db) _ruleCovByDb.set(String(c.db).toLowerCase(), c); });
        }
        const _ruleMeasuring = _isProductCoverageLoading(product.id);
        ruleDbs.forEach((d) => {
          const it = document.createElement("div"); it.className = "cov-db-rule-dbitem";
          const dot = document.createElement("span"); dot.className = "cov-db-rule-dbdot"; dot.textContent = "└";
          const nm = document.createElement("span"); nm.className = "cov-db-rule-dbname"; nm.textContent = d.schema_name; nm.title = d.schema_name;
          const covRow = _ruleCovByDb.get(String(d.schema_name).toLowerCase()) || null;
          if (covRow && covRow.connected === false) it.classList.add("is-offline");
          it.append(dot, nm);
          // 진척 셀(마이크로바 + 통계 + 상태칩) — 메인 목록 행과 동일 helper 재사용.
          it.appendChild(buildDbCoverageCells(covRow, _ruleMeasuring));
          dbWrap.appendChild(it);
        });
      } else {
        const em = document.createElement("div"); em.className = "cov-db-rule-dbempty"; em.textContent = "(아직 없음 — 데이터소스에 일치 DB 가 생기면 자동 추가)";
        dbWrap.appendChild(em);
      }
      card.appendChild(dbWrap);
      // 이 규칙의 pending(승인 대기) — 승인은 즉시 반영 아니라 "승인 대기" 스테이징(토글).
      const pend = (rule.pending || []);
      if (pend.length) {
        const pw = document.createElement("div"); pw.className = "cov-db-rule-pending";
        const ph = document.createElement("div"); ph.className = "cov-db-rule-pending-head";
        ph.textContent = `승인 대기 ${pend.length}개 (한도 초과/권한 보류)`;
        pw.appendChild(ph);
        const appr = (e && e.approves && e.approves[String(rule.id)]) || [];
        pend.forEach((p) => {
          const it = document.createElement("div"); it.className = "cov-db-rule-pending-item";
          const nm = document.createElement("span"); nm.className = "cov-db-rule-pending-name"; nm.textContent = p.schema_name;
          const staged = appr.includes(p.schema_name);
          const ap = document.createElement("button"); ap.type = "button";
          ap.className = "cov-db-rule-approve" + (staged ? " is-staged" : "");
          ap.textContent = staged ? "승인 취소" : "승인";
          ap.addEventListener("click", () => {
            const ee = _ensureDbRulePending(product.id, _editDsKey);
            ee.approves[String(rule.id)] = ee.approves[String(rule.id)] || [];
            const arr = ee.approves[String(rule.id)];
            const i = arr.indexOf(p.schema_name);
            if (i >= 0) { arr.splice(i, 1); if (!arr.length) delete ee.approves[String(rule.id)]; }
            else { arr.push(p.schema_name); }
            _settleDbRulePending(product.id, _editDsKey);
            _renderRuleEditor();
          });
          if (staged) {
            const tag = document.createElement("span"); tag.className = "cov-db-rule-pending-tag"; tag.textContent = "승인 대기";
            it.append(nm, tag, ap);
          } else {
            it.append(nm, ap);
          }
          pw.appendChild(it);
        });
        card.appendChild(pw);
      }
      return card;
    };

    // 추가 대기(staged create) 카드 — 아직 서버에 없는 규칙.
    const _buildStagedCreateCard = (create, ord) => {
      const card = document.createElement("div"); card.className = "cov-db-rule-card is-staged-create";
      const hd = document.createElement("div"); hd.className = "cov-db-rule-card-head";
      const title = document.createElement("span"); title.className = "cov-db-rule-card-title"; title.textContent = `규칙 (신규 ${ord})`;
      const pat = document.createElement("code"); pat.className = "cov-db-rule-card-pat";
      pat.textContent = create.include_pattern + (create.exclude_pattern ? `  (제외: ${create.exclude_pattern})` : "");
      const capPill = document.createElement("span"); capPill.className = "cov-db-rule-card-cap"; capPill.textContent = `한도 ${create.cap}`;
      const badge = document.createElement("span"); badge.className = "cov-db-rule-card-badge is-create"; badge.textContent = "추가 대기";
      const undo = document.createElement("button"); undo.type = "button"; undo.className = "cov-db-rule-edit"; undo.textContent = "추가 취소";
      undo.addEventListener("click", () => {
        const ee = _ensureDbRulePending(product.id, _editDsKey);
        ee.creates = (ee.creates || []).filter((c) => c.tempId !== create.tempId);
        _settleDbRulePending(product.id, _editDsKey);
        _renderRuleEditor();
      });
      hd.append(title, pat, capPill, badge, undo);
      card.appendChild(hd);
      return card;
    };

    _renderRuleEditor = async () => {
      const dsk = String(_editDsKey || "").trim().toLowerCase();
      ruleWrap.innerHTML = "";
      if (!dsk) return;  // 미바인딩(기본 단일 MySQL)에는 규칙 미지원.
      const head = document.createElement("div"); head.className = "cov-db-rule-head"; head.textContent = "정규식 자동 규칙";
      const hint = document.createElement("div"); hint.className = "cov-db-rule-hint";
      hint.textContent = "여러 규칙을 둘 수 있습니다. 규칙 추가/수정/삭제/승인은 즉시 반영되지 않고 하단 '모두 적용' 시 일괄 반영됩니다. 확정된 규칙은 데이터소스 변화 시 일치 DB 를 자동 동기화하며(한도 초과/권한 보류분은 승인 대기), 그 규칙에 종속돼 아래에 묶여 표시됩니다.";
      const cardsWrap = document.createElement("div"); cardsWrap.className = "cov-db-rule-cards";
      const addBtn = document.createElement("button"); addBtn.type = "button"; addBtn.className = "cov-db-rule-addbtn"; addBtn.textContent = "+ 규칙 추가";
      const addHost = document.createElement("div"); addHost.className = "cov-db-rule-add-host hidden";
      addBtn.addEventListener("click", () => {
        if (!addHost.classList.contains("hidden")) { addHost.classList.add("hidden"); addHost.innerHTML = ""; return; }
        addHost.innerHTML = "";
        addHost.appendChild(_buildRuleForm(null, (payload) => {
          const ee = _ensureDbRulePending(product.id, _editDsKey);
          ee.creates.push({ tempId: `new:${_ruleTempSeq++}`, ...payload });
          _settleDbRulePending(product.id, _editDsKey);
          addHost.classList.add("hidden"); addHost.innerHTML = "";
          showToast("규칙 추가 대기 — '모두 적용' 시 반영됩니다.");
          _renderRuleEditor();
        }, "추가 대기"));
        addHost.classList.remove("hidden");
      });
      ruleWrap.append(head, hint, cardsWrap, addBtn, addHost);

      let data = null;
      try { data = await apiFetch(`${_ruleBase()}`); } catch (e) { data = null; }
      const rules = (data && data.rules) || [];
      const e = _getDbRulePending(product.id, dsk);
      const creates = (e && e.creates) || [];
      if (!rules.length && !creates.length) {
        const em = document.createElement("div"); em.className = "cov-db-rule-empty";
        em.textContent = "설정된 규칙이 없습니다. '+ 규칙 추가' 로 첫 규칙을 만드세요.";
        cardsWrap.appendChild(em);
      } else {
        rules.forEach((rule, i) => cardsWrap.appendChild(_buildRuleCard(rule, i)));
        creates.forEach((c, i) => cardsWrap.appendChild(_buildStagedCreateCard(c, i + 1)));
      }
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

  // ds-conn-bg-decouple: 연결 불안정/끊김으로 DB 목록 로드를 보류했을 때, picker 위에 상태
  // 배너 + '새로고침'(force) 버튼을 노출/제거한다. 동기 연결확인이 UI 를 막지 않고, 사용자가
  // 원할 때만 명시적으로 live connect 를 재시도(?force=1)하게 한다.
  const _setAccessDbDegraded = (info) => {
    const host = pickerWrap && pickerWrap.parentNode;
    if (!host) return;
    const prev = host.querySelector(".admin-db-degraded-note");
    if (prev) prev.remove();
    if (!info) return;
    const note = document.createElement("div");
    note.className = "admin-db-degraded-note";
    note.setAttribute("role", "status");   // degraded 상태를 보조기술에 알림(서버 degraded 경로는 toast 없음).
    const label = info.connStatus === "down" ? "연결 끊김" : "연결 불안정";
    const span = document.createElement("span");
    span.textContent = `데이터소스 ${label} — DB 목록 로드를 보류했습니다(연결 상태는 백그라운드에서 점검 중).`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "admin-db-degraded-refresh";
    btn.textContent = "새로고침";
    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = "확인 중…";
      _refreshAccessibleDbs(info.key, { force: true });
    });
    note.append(span, btn);
    host.insertBefore(note, pickerWrap);
  };

  // TASK-0206: 선택 datasource 의 DB 목록으로 접근가능 DB(고정 시스템칩 + 사용자 picker)을 갱신.
  // 등록 datasource 면 /databases(classified) 사용; 미바인딩이면 데이터 MySQL 기본값으로 환원.
  // ds-conn-bg-decouple: 기본 호출은 백그라운드 conn_health 캐시 게이트를 통과한 응답(불안정/끊김이면
  // degraded=true 로 즉시 반환 — live connect 안 함)을 받고, opts.force 시에만 ?force=1 로 실제 열거.
  _refreshAccessibleDbs = async (key, opts = {}) => {
    const force = !!(opts && opts.force);
    const ds = (adminState.datasources || []).find((d) => d.key === key);
    if (!key || !ds) {
      // 미바인딩(또는 미등록) → 데이터 MySQL 기본값.
      lockedChips = _defaultLocked.slice();
      availableUserDbs = (adminState.availableDatabases.user_schemas || []).slice();
      dsCaseInsensitive = false;
      redrawChips();
      buildPicker();
      _setAccessDbDegraded(null);
      _ensureDbInsights();   // TASK-0242: 기본(미바인딩) scope 의 DB 설명/상태 로드.
      return;
    }
    const isMssql = String(ds.engine || "mysql").toLowerCase() === "mssql";
    dsCaseInsensitive = isMssql;
    let degraded = false, connStatus = null;
    try {
      const qs = force ? "?force=1" : "";
      const r = await apiFetch(`/api/admin/datasources/${encodeURIComponent(key)}/databases${qs}`);
      if (r && r.degraded) {
        // 백그라운드 모니터가 불안정/끊김으로 판정 → 동기 열거 생략(다른 UI 갱신 비차단). 캐시 상태만.
        degraded = true;
        connStatus = r.conn_status || null;
        lockedChips = isMssql ? [] : _defaultLocked.slice();
        availableUserDbs = [];
      } else {
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
      }
    } catch (e) {
      lockedChips = isMssql ? [] : _defaultLocked.slice();
      availableUserDbs = [];
      degraded = true;   // 연결/권한 실패 — 재시도 affordance 유지.
      showToast("데이터소스 DB 목록 조회 실패 — 연결/권한 확인.", true);
    }
    redrawChips();
    buildPicker();
    _setAccessDbDegraded(degraded ? { key, connStatus } : null);
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

        // 메타: 엔진 배지(상태 = pill, 액션 아님).
        // TASK-0308: 기본(primary) 표시는 별도 '기본' 텍스트 배지 대신 **엔진 배지 색상**으로 한다.
        //  조건부 '기본' 배지가 뒤따르는 인사이트 아이콘의 x-위치를 행마다 어긋나게 하던 문제를 제거
        //  (engine 배지는 항상 존재 → 아이콘 위치 일관). 색 단독 의존을 피해 primary 는 title 로도 명시.
        const eng = document.createElement("span");
        eng.className = "ds-acc-engine" + (b.is_primary ? " is-primary" : "");
        eng.textContent = (meta.engine || "mysql");
        if (b.is_primary) eng.title = "기본(primary) 데이터소스";
        head.appendChild(eng);
        // TASK-0308: 인사이트 탐색(InsightEnabled) 상태 표시 — 제품 탭에서 이 데이터소스가
        //  insight-worker 에 의해 스캔되는지 한눈에. OFF(스캔 안 함)는 amber 로 두드러지게 표기해
        //  '제품·접근DB 만 보고 탐색 토글을 놓치는' 실수를 방지(상태 표시 전용 — 토글은 데이터소스
        //  관리 탭). insight_enabled 는 meta(=adminState.datasources)에서 온다(bool, 기본 true).
        const _insOn = meta.insight_enabled !== false;
        const ins = document.createElement("span");
        ins.className = "ds-acc-insight " + (_insOn ? "is-on" : "is-off");
        ins.setAttribute("role", "img");
        const _insLabel = _insOn
          ? "인사이트 탐색 켜짐 — 이 데이터소스의 스키마·테이블이 자동 탐색됩니다"
          : "인사이트 탐색 꺼짐 — 이 데이터소스는 탐색/분석되지 않습니다 (데이터소스 관리 탭에서 켤 수 있습니다)";
        ins.title = _insLabel;
        ins.setAttribute("aria-label", _insLabel);
        ins.innerHTML = _insOn
          ? '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M1.4 8S3.7 3.6 8 3.6 14.6 8 14.6 8 12.3 12.4 8 12.4 1.4 8 1.4 8Z"/><circle cx="8" cy="8" r="2.1"/></svg>'
          : '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9.9 9.9A2.1 2.1 0 0 1 6.1 6.1M6.5 3.9A6.6 6.6 0 0 1 8 3.6C12.3 3.6 14.6 8 14.6 8a11.6 11.6 0 0 1-1.8 2.3M3.5 5.2A11.4 11.4 0 0 0 1.4 8S3.7 12.4 8 12.4a6.6 6.6 0 0 0 2.3-.4"/><line x1="2.4" y1="2.4" x2="13.6" y2="13.6"/></svg>';
        head.appendChild(ins);
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
      hint: "모든 제품에 적용됩니다. '자동 작성'은 역할 성격과 소속 사용자 대화 패턴을 반영합니다.",
      fixedProductId: 0, // 0 = product 무관 (Phase 1B catalog 의 NULL 매칭)
      autoGenerateRoleId: Number(role.id), // TASK-20260625: 역할 전체 제품 프롬프트 자동작성
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

function buildSystemPromptEditor({ scope, productId = null, roleId = null, accountId = null, title, hint, fixedProductId = null, autoGenerateProductId = null, autoGenerateRoleId = null }) {
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
    if (scope === "role") {
      // 역할 '전체 제품 프롬프트' — schema/table 이 아닌 소속 사용자·대화주제 기준 메타.
      metaEl.textContent = m.grounded
        ? `(자동 생성됨 — 소속 사용자 ${m.member_count || 0}명·대화주제 ${m.topic_count || 0}건 반영. 검토 후 저장하세요)`
        : "(자동 생성됨 — 이 역할의 대화 이력이 아직 적어 권한·정의 기반 형태입니다. 검토 후 저장하세요)";
    } else if (m.grounded) {
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

  if (autoGenerateProductId || autoGenerateRoleId) {
    // 자동작성 스트림 URL — 역할 scope 면 roles/{id}, 그 외(제품)면 products/{id}.
    const autoStreamUrl = autoGenerateRoleId
      ? `/api/admin/roles/${autoGenerateRoleId}/prompt/generate/stream`
      : `/api/admin/products/${autoGenerateProductId}/prompt/generate/stream`;
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
        // 재진입 가드: 이 호출이 소유한 controller 일 때만 복원 — 빠른 더블클릭 시 앞선 호출의
        // finally 가 뒤 호출의 진행 중 스트림 버튼을 재활성/abort 핸들 제거하지 않도록.
        if (autoBtn._streamAbort !== controller) return;
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
          autoStreamUrl,
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
  // TASK-AIOPS: AI 운영 현황 새로고침.
  const aiOpsRefreshBtn = $("aiOpsRefreshBtn");
  if (aiOpsRefreshBtn && !aiOpsRefreshBtn.dataset.bound) {
    aiOpsRefreshBtn.dataset.bound = "1";
    aiOpsRefreshBtn.addEventListener("click", () => loadAiOps());
  }
  // TASK-20260623T090440-sample-feedback-curation: 샘플 검수 새로고침.
  const sampleReviewRefreshBtn = $("sampleReviewRefreshBtn");
  if (sampleReviewRefreshBtn && !sampleReviewRefreshBtn.dataset.bound) {
    sampleReviewRefreshBtn.dataset.bound = "1";
    sampleReviewRefreshBtn.addEventListener("click", () => loadSampleFeedback());
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

