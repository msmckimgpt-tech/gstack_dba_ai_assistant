// feature-0003 ITEM-09 — 그래프 뷰는 graph/graph.js 로 분리(순환 import). type=module 전환.
import { _metaShowGraph, _metaGraphLoadRoots, _metaRoleLegendTips, _metaGraph } from "./graph/graph.js?v=dev";
import { loadUsage } from "./admin/usage.js?v=dev";
import { loadAiOps, loadArchiveServerActivity } from "./admin/aiops.js?v=dev";
// feature-0043 TASK-20260901T110000 — 외부AI 운영축 재편.
//   `admin/exttasks.js`(외부 AI 작업)는 `admin/tasks.js`(브리지 작업)로 흡수됐다 — 같은
//   표(`WebAiTasks`)를 두 화면이 반쪽씩 보고 있어 대화 질문의 대기 상태가 어디에도
//   나오지 않았다.
import { loadBridgeTasks } from "./admin/tasks.js?v=dev";
import { loadToolUsage } from "./admin/tools.js?v=dev";
// feature-0043 TASK-20260831T100000 — 콘솔 LLM 상태 표면화(미적용 배지·사유·조작면 게이트).
import {
  applyLlmInactiveMarks, gateLlmControl, renderLlmNotice,
  llmBlocked, delegationReady, jobDelegable,
  awaitDelegatedResult, jobPhaseLabel,
} from "./admin/llm-state.js?v=dev";
// 다른 admin/* 모듈이 "../admin.js" 로 가져다 쓰는 계약 보존 (aiops·usage 와 동형 re-export).
export { applyLlmInactiveMarks, gateLlmControl, renderLlmNotice,
         llmBlocked, delegationReady, jobDelegable,
         awaitDelegatedResult, jobPhaseLabel };
import {
  mountSettingsSections, rerenderRuntimeSettingsPanels,
  rsSaveValue, rsResetValue,
  RS_RESET, RS_MODEL_PREFIX, RS_REASONING_PREFIX, RS_AGENT_MAX_PREFIX, RS_PERF_KEYS,
  RS_EXT_TOOL_KEYS,
  mountGuidanceRegistryPanel,
} from "./admin/settings.js?v=dev";
export { mountGuidanceRegistryPanel };  // aiops.js 의 "../admin.js" import 계약 보존 (re-export)
import { loadAuditList, attachAuditFilterHandlers, loadAuditFacets, loadGrantHealth } from "./admin/audit.js?v=dev";
import { currentPageAccounts, renderAccountList, renderAccountBulkBar, renderAccountDetail } from "./admin/accounts.js?v=dev";
import { renderDatasourcesPane, _dsFiltered, _dsRenderList } from "./admin/datasources.js?v=dev";
import { filteredProducts, renderProductList, renderProductDetail, startNewProduct, loadProductInsightCoverage, _isProductCoverageLoading } from "./admin/products.js?v=dev";
import {
  initMetadataTab, loadMetadata, _metaPopulateScopeSelect, _metaPopulateProductScopeSelect,
  _metaApplySubtabPermissions, _metaSyncViews, _metaPrimeReviewBadge, _metaRefreshReviewBadge,
  _metaRenderDetail, _metaRenderReviewDetail, _metaClearReviewDetail, _metaMarkReviewActive,
  _metaReviewScopeParam, _metaLoadingSkeleton, _metaFmtDt, _metaIsMermaid, _metaDatasourceLabelOf,
} from "./admin/metadata.js?v=dev";
export { _metaPopulateScopeSelect };  // usage.js 의 "../admin.js" import 계약 보존 (re-export)
import { filteredRoles, renderRoleList, renderRoleDetail, startNewRole } from "./admin/roles.js?v=dev";
// hangul-qwerty-search: 한/영 자판 전환을 잊고 친 검색어(`ㅎㅋ` ↔ `gz`)도 찾아주는 저장소 단일
//   primitive. 작업 화면(app.js) 번들과 공유하며, 매핑표를 어느 소비처에도 복제하지 않는다.
import { matchesAnyVariant, searchVariants } from "./hangul-qwerty.js?v=dev";
const mermaid = window.mermaid;   // UMD 전역 bridge(module scope 의 bare mermaid 참조 보존).

/* =====================================================================
 * Admin console (tab + master-detail + pending changes + bulk commit)
 * ===================================================================== */

export const ACCOUNT_PAGE_SIZE = 15;

export const adminState = {
  me: null,
  // feature-0043 TASK-20260831T100000 — 콘솔 LLM 상태(`/api/admin/me` 의 `llm`).
  //   {server_llm_blocked, delegation, reason, action_url, runner, inactive_surfaces}
  // **프론트가 조합하지 않는다** — 판정은 서버 한 곳(`routers/_console_llm.py`)이고 여기는
  // 그 결과를 담는 자리다. 화면이 다시 조합하면 서버와 갈리고, 갈리는 순간 느슨한 쪽이
  // 사용자가 보는 진실이 된다(P0-R 에서 이미 겪은 형태).
  // `null` = 아직 못 받음. 빈 객체로 초기화하지 않는 이유: "못 받음" 과 "차단 아님" 은
  // 다른 사실이고, 후자로 지으면 화면이 근거 없이 낙관한다.
  llm: null,
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

export const METADATA_SCHEMAS = ["information_schema", "mysql", "sys", "performance_schema"];
export const INTERNAL_SCHEMAS = new Set(["agent_memory"]);

// ── TASK-20260618T025755: '+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택 ──────────
//  사내 서비스는 데이터소스의 DB 추가/삭제가 잦아, 후보 DB 가 많을 때 원하는 DB 를 빠르게
//  찾거나(검색) 패턴으로 한 번에 선택(정규식)할 수 있게 한다. 후보가 이 수 이상일 때만
//  toolbar 를 노출한다(소수 목록은 불필요). 자매 제품 드롭업 검색필터(PRODUCT_DROPUP_SEARCH_MIN)
//  와 동일 idiom. 아래 4개는 순수/DOM helper — admin.js 상태에 의존하지 않아 jsdom 으로 검증한다.
export const DB_PICKER_SEARCH_MIN = 6;

// 검색 부분일치(대소문자 무시 + 한/영 자판 교차). 순수 함수 — 일치하는 이름만 반환.
function dbPickerFilterNames(names, query) {
  const qv = searchVariants(query);
  if (!qv.length) return (names || []).slice();
  return (names || []).filter((n) => matchesAnyVariant(String(n).toLowerCase(), qv));
}

// 정규식 다중 매칭(대소문자 무시 'i'). 순수 함수 — { ok, matches, error }.
//  ok=false 면 정규식 컴파일 실패(error 메시지). 빈 패턴은 ok=true + 빈 matches.
export function dbPickerRegexMatches(names, pattern) {
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
export function applyDbPickerSearch(listEl, query) {
  const qv = searchVariants(query);
  let shown = 0;
  (listEl ? listEl.querySelectorAll(".admin-db-picker-item") : []).forEach((it) => {
    const hay = it.dataset.search || "";
    const hit = matchesAnyVariant(hay, qv);
    it.classList.toggle("hidden", !hit);
    if (hit) shown += 1;
  });
  return shown;
}

// 정규식 일치 항목에 .is-regex-match 하이라이트(적용 전 미리보기 = "조회 가능").
//  반환: { ok, count, error }. 빈/오류 패턴이면 하이라이트 전부 해제.
export function applyDbPickerRegexHighlight(listEl, pattern) {
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
// perm-category-hier(Critical §12.3, 사용자 승인 A안 2026-07-14): 그룹 순서를 관리 콘솔 좌측 nav
//   카테고리 순서(계정[account·role·quota] → 제품[product·datasource] → 감사 → 지식베이스 → 시스템)와
//   정합. 각 카테고리 최상위엔 '접근'(console.<cat>.access) 조회 게이트가 오고 세부 권한이 하위 종속.
// model-access-rbac(2026-07-28): model_access(모델 사용) 그룹 추가 — 운영 권한 묶음에서
//   product_access(제품 사용) 바로 뒤. 둘 다 "작업 화면에서 무엇을 쓸 수 있나" 축의 동적 권한.
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "quota", "product", "datasource", "audit", "kb", "settings", "conversation_own", "conversation_any", "product_access", "model_access", "attachment", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  // TASK-20260623T030418-quota-rbac-permission: LLM 토큰 사용 한도(역할 기본·계정 특수)의 조회/조절 권한 그룹.
  quota: "LLM 사용 한도",
  datasource: "데이터소스",
  // perm-category-hier: 메타데이터 관리·검수·그래프 뷰를 포괄하므로 "지식베이스(KB) 검수"→"지식베이스"
  //   (검수 전용이라는 오해 해소 — app.js PERMISSION_GROUP_LABELS 와 동일 유지, CONVENTIONS §10.6).
  kb: "지식베이스",
  conversation_own: "내 대화 권한",
  conversation_any: "전체 대화 권한",
  product: "제품 관리",
  product_access: "제품 사용 (작업 화면)",
  // model-access-rbac(2026-07-28): 계정/역할별 LLM 모델 선택 허용 범위(동적 model.access.<value>).
  model_access: "모델 사용 (작업 화면)",
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
  // perm-category-hier: 그룹 순서를 nav 카테고리 순서와 정합(계정 → 제품 → 감사 → 지식베이스 → 시스템).
  { id: "manage", title: "관리 권한", description: "콘솔 진입 · 계정 · 역할 · LLM 사용 한도 · 제품 관리 · 데이터소스 · 감사 · 지식베이스 · 시스템 설정", groups: ["console", "account", "role", "quota", "product", "datasource", "audit", "kb", "settings"] },
  // TASK-0094 Sprint 1 Phase 12: attachment 그룹은 운영 권한 묶음에 포함.
  // TASK-0288: 작업 화면 제품 사용(product_access)은 운영 권한 section — 관리 콘솔 제품 관리(product)와 분리.
  { id: "operate", title: "운영 권한", description: "내 대화 · 전체 대화 · 제품 사용 · 모델 사용 · 첨부", groups: ["conversation_own", "conversation_any", "product_access", "model_access", "attachment"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

// 권한 점진적 세분화 (progressive disclosure) — 종속성 선언 맵 (childCode -> 선행 parentCode).
// renderPermissionGrid 가 각 권한 row 를 "선행 권한이 충족돼야(체크 / override=허용) 표시" 하도록 접는다.
// 비파괴 원칙: 이미 명시 설정된(체크 / override=허용·거부) row 와 그 조상은 게이트 상태와 무관하게 항상 표시 →
//   부여된 권한이 조용히 숨겨지지 않는다. 각 그룹의 숨은 row 는 "세부 권한 N개 더 보기" 로 강제 노출 가능.
//
// 구조 (CONVENTIONS.md §10.6 의 group/section 정렬은 그대로 — 본 맵은 group 내부의 표시 단계만 정의):
//  · 관리 권한 section (perm-category-hier, Critical §12.3, 사용자 승인 A안 2026-07-14):
//      `console.access`(관리 콘솔 접근) 가 마스터 게이트 → 그 하위에 nav 카테고리별 최상위
//      '접근'(=카테고리 조회 게이트) 5종: console.account.access(계정) / console.product.access(제품) /
//      console.audit.access(감사) / console.kb.access(지식베이스) / console.system.access(시스템).
//      같은 카테고리의 모든 권한(탭 조회 → 추가/수정/삭제 → 승인/작동)은 그 카테고리의 접근 권한
//      하위로 탭 내부 구조를 따라 재귀 종속된다 — 예: 감사 접근 → [감사 로그 조회(own→any→내보내기/삭제),
//      보관 대화 조회, LLM 사용량 조회, AI 운영 현황 조회]. 상위 체크 시 하위가 UI 로 펼쳐진다.
//  · 운영 권한 section: 마스터 게이트 없음. 각 그룹의 "목록 조회"(list.own/list.any)가 카테고리
//      접근(=조회) 게이트 — 동작 권한(생성·요청·삭제 등)은 그 하위로 종속된다.
// 백엔드 PERMISSION_DEFINITIONS(web_context.py) 의 code 와 1:1 정합 필수 — 회귀 테스트
//   test_permission_dependency_map.py 가 모든 key/value 가 실제 권한 code 인지 검증한다.
// 탭 노출 게이트는 ADMIN_TAB_CATEGORY_ACCESS(카테고리 접근 AND 탭 권한) — 본 맵과 정합 유지.
const PERMISSION_DEPENDENCIES = {
  // ── 관리 권한 (마스터 게이트 = console.access → 카테고리 접근 5종) ──
  "console.manage": "console.access",
  "console.account.access": "console.access",
  "console.product.access": "console.access",
  "console.audit.access": "console.access",
  "console.kb.access": "console.access",
  "console.system.access": "console.access",
  // 계정 카테고리(계정·역할 탭 + 한도 섹션): account.read/role.read/quota.read 가 탭(섹션) 조회 게이트.
  "account.read": "console.account.access",
  "account.update": "account.read",
  "account.delete": "account.read",
  "account.activate": "account.read",
  "account.deactivate": "account.read",
  "account.role.assign": "account.read",
  "account.permission.override.manage": "account.read",
  "role.read": "console.account.access",
  "role.create": "role.read",
  "role.update": "role.read",
  "role.delete": "role.read",
  "role.permission.manage": "role.read",
  // TASK-20260623T030418-quota-rbac-permission: LLM 사용 한도 — 한도 UI 는 계정·역할 탭 내부 섹션이므로
  //   계정 카테고리 접근 하위. quota.manage(조절) 는 quota.read(조회) 선행. 조회 없이는 조절 불가.
  "quota.read": "console.account.access",
  "quota.manage": "quota.read",
  // 제품 카테고리(제품·데이터소스 탭): product.read/datasource.read 가 탭 조회 게이트.
  //   insight.reset 은 제품 상세의 파괴적 '작동' 권한 — 제품 조회 하위(perm-category-hier 에서
  //   console 직속에서 이동, 실행 표면 = routers/admin_products.py insight-reset).
  "product.read": "console.product.access",
  // perm-atomic-split(2026-07-15): 묶음 product.manage/datasource.manage 는 grid 숨김(LEGACY) —
  //   종속 트리는 원자 단위(생성/수정/삭제/테스트)가 조회(read) 하위로 구성된다.
  "product.create": "product.read",
  "product.update": "product.read",
  "product.delete": "product.read",
  "system_prompt.manage.role.any": "product.read",
  "insight.reset": "product.read",
  "datasource.read": "console.product.access",
  "datasource.create": "datasource.read",
  "datasource.update": "datasource.read",
  "datasource.delete": "datasource.read",
  "datasource.test": "datasource.read",
  // 감사 카테고리(감사 로그·보관 대화·LLM 사용량·AI 운영 현황 4개 탭): 각 탭의 조회 권한이
  //   감사 접근 하위로 종속(perm-category-hier — usage/aiops 는 console 직속에서, 보관 대화는
  //   conversation.list.any 하위에서 이동). 내보내기/삭제는 감사 로그 조회의 하위 작동 권한.
  "audit.read.own": "console.audit.access",
  "audit.read.any": "audit.read.own",
  "audit.export": "audit.read.own",
  "audit.purge": "audit.read.own",
  "conversation.archive.read.any": "console.audit.access",
  "console.usage.read": "console.audit.access",
  "console.aiops.read": "console.audit.access",
  // 지식베이스 카테고리(메타데이터·그래프 뷰 탭) — metadata-perm-hier 의 "묶음 게이트 → 세부" 계층을
  //   유지하되 그룹 게이트를 console.access 직속에서 카테고리 접근(console.kb.access) 하위로 이동.
  //   백엔드는 묶음이 편집 4종을 함의(_METADATA_MANUAL_IMPLIES)하므로 의미 정합. 종속 맵은 UI 표시 계층
  //   (progressive disclosure)일 뿐 authz enforcement 아님 — 개별 부여는 "세부 권한 더 보기"로 여전히 가능.
  // perm-atomic-split(2026-07-15, 사용자 승인): 사전 4종 = 조회(read)가 서브탭 게이트, 그 하위에
  //   추가/수정/삭제 원자 단위 + 검수(승급·거부 단일 단위 — 사용자 지시로 원본 사전 항목 하위 종속).
  //   레거시 묶음(kb.ingest.manual·metadata.*.manage)은 grid 숨김(LEGACY_BUNDLE_PERMISSIONS) — 트리 제외.
  "metadata.glossary.read": "console.kb.access",
  "metadata.glossary.create": "metadata.glossary.read",
  "metadata.glossary.update": "metadata.glossary.read",
  "metadata.glossary.delete": "metadata.glossary.read",
  "kb.glossary.curate": "metadata.glossary.read",
  "metadata.enum.read": "console.kb.access",
  "metadata.enum.create": "metadata.enum.read",
  "metadata.enum.update": "metadata.enum.read",
  "metadata.enum.delete": "metadata.enum.read",
  "kb.enum.curate": "metadata.enum.read",
  "metadata.table.read": "console.kb.access",
  "metadata.table.create": "metadata.table.read",
  "metadata.table.update": "metadata.table.read",
  "metadata.table.delete": "metadata.table.read",
  "metadata.column.read": "console.kb.access",
  "metadata.column.create": "metadata.column.read",
  "metadata.column.update": "metadata.column.read",
  "metadata.column.delete": "metadata.column.read",
  //   샘플 검수는 원본 사전(샘플쿼리)의 조회 단위가 없어(서브탭 자체가 검수 도메인) 카테고리 접근 직속.
  "kb.sample.curate": "console.kb.access",
  // graph-perm-split(Critical §12.3, 2026-07-13) + perm-category-hier: 그래프 뷰 조회는 '메타데이터 관리'
  //   묶음과 형제인 독립 탭 게이트 — 카테고리 접근(console.kb.access) 하위.
  "metadata.graph.read": "console.kb.access",
  // graph-analyze-perm(Critical §12.3, 2026-07-14): AI 능동 분석 실행은 조회(graph.read)의 하위 권한 —
  //   역할 편집 UI 에서 graph.read 아래 nest. 조회 없이 실행 무의미(progressive disclosure). authz 는 백엔드.
  "metadata.graph.analyze": "metadata.graph.read",
  // 시스템 카테고리(설정 탭): 전역 프롬프트/런타임 설정의 read 가 조회 게이트, write 는 read 선행.
  //   (system.runtime.* 는 기존에 종속 미선언 루트였던 것을 perm-category-hier 에서 정합.)
  "system_prompt.global.read": "console.system.access",
  "system_prompt.global.write": "system_prompt.global.read",
  "system.runtime.read": "console.system.access",
  "system.runtime.write": "system.runtime.read",
  // feature-0021: AI 추론 활동 조회(read-only) — console-ia(2026-07-16) 감사 카테고리 하위로 재배치.
  "console.reasoning.read": "console.audit.access",
  // ── 운영 권한 (TASK-0269 — own/any 그룹 분리 + "목록 조회" 게이트) ──
  //   내 대화 권한(conversation_own): "내 대화 목록 조회"(list.own) 가 카테고리 접근(조회) 게이트 —
  //     루트(항상 표시). perm-category-hier: "대화 생성"(create)도 동작 권한이므로 게이트 하위로 정합
  //     (기존 루트 → list.own 종속).
  "conversation.create": "conversation.list.own",
  "conversation.read.own": "conversation.list.own",
  "conversation.ask": "conversation.list.own",
  "conversation.file.read.own": "conversation.list.own",
  "conversation.rename.own": "conversation.list.own",
  "conversation.delete.own": "conversation.list.own",
  "conversation.cancel.own": "conversation.list.own",
  "conversation.finalize.own": "conversation.list.own",
  // feature-0030: 실행시간 연장 승인(내 대화) — 즉시답변과 같은 층(list.own 하위).
  "conversation.extend.own": "conversation.list.own",
  "conversation.duplicate.own": "conversation.list.own",
  "conversation.share.create": "conversation.list.own",
  "conversation.member.manage": "conversation.list.own",
  "conversation.attachment.upload.own": "conversation.list.own",
  "conversation.attachment.read.own": "conversation.list.own",
  // feature-0024-conversation-folders: 폴더 조회/관리(내 폴더, 엄격한 개인 — .any 폐지). manage.own 은 list.own 하위.
  "folder.list.own": "conversation.list.own",
  "folder.manage.own": "folder.list.own",
  //   전체 대화 권한(conversation_any): "전체 대화 목록 조회"(list.any) 가 게이트(루트).
  "conversation.read.any": "conversation.list.any",
  "conversation.file.read.any": "conversation.list.any",
  "conversation.rename.any": "conversation.list.any",
  "conversation.delete.any": "conversation.list.any",
  // perm-category-hier: conversation.archive.read.any(보관 대화 조회)는 감사 카테고리 탭 권한으로 이동
  //   (위 감사 블록 — console.audit.access 하위). 여기(전체 대화)에는 더 이상 두지 않는다.
  "conversation.cancel.any": "conversation.list.any",
  "conversation.finalize.any": "conversation.list.any",
  "conversation.extend.any": "conversation.list.any",
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

export function entityUnit(entity) { return BULK_ENTITY_UNIT[entity] || "개"; }
export function actionLabel(action) { return BULK_ACTION_LABEL[action] || action; }

// DESIGN.md §7 — bulk action confirm 표준
export function confirmBulkAction({ entity, action, count, danger = false }) {
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
export function runBulkActionWithPartialFail({ entity, ids, action, applyFn, canTargetRow }) {
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
export function renderCrossPageBanner({ entity, selected, visibleIds, totalCount, onClearAll, onShowCurrentOnly }) {
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
export function applyShiftRangeSelect({ selected, visibleIds, fromIdx, toIdx, addMode = true }) {
  if (fromIdx < 0 || toIdx < 0) return;
  const [lo, hi] = fromIdx <= toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
  for (let i = lo; i <= hi; i++) {
    const id = visibleIds[i];
    if (id === undefined || id === null) continue;
    if (addMode) selected.add(id); else selected.delete(id);
  }
}

/* ── Utility & DOM helpers ───────────────────────────────────────────── */

export const $ = (id) => document.getElementById(id);
const adminToastEl = $("adminToast");
let adminToastTimer = null;

export function showToast(message, isError = false) {
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

export async function apiFetch(url, options = {}) {
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

export function formatDateTime(value = "") {
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
export function applyAvatar(el, { url, seed, initials }) {
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

export function can(permission) {
  return Boolean(adminState.me?.permissions?.[permission]);
}

// perm-atomic-split(2026-07-15): 레거시 묶음 — 코드·enforcement 함의·기존 grant 는 유지하되
// 권한 grid(역할/override 편집기)에서는 숨긴다. 신규 부여는 원자 단위만. web_context.py
// LEGACY_BUNDLE_PERMISSIONS 와 정합(test_permission_dependency_map 이 parity 검증).
const LEGACY_BUNDLE_PERMISSIONS = new Set([
  "kb.ingest.manual",
  "metadata.glossary.manage", "metadata.enum.manage", "metadata.table.manage", "metadata.column.manage",
  "product.manage", "datasource.manage",
]);

export function groupedPermissions(opts = {}) {
  // TASK-0053 Phase B: dynamic 권한 (`product.access.<key>`) 은 별도 product subcatalog UI 가
  // 처리하므로 일반 권한 grid 에서는 excludeDynamic=true 로 필터링한다. 정적 권한
  // (`product.manage`, `system_prompt.manage.role.any` 등) 은 그대로 product 그룹에 남는다.
  const { excludeDynamic = false } = opts;
  const groups = new Map();
  adminState.permissions.forEach((permission) => {
    // model-access-rbac(2026-07-28): excludeDynamic 은 **product_access 전용** 이다.
    // 원래 의도는 "전용 embedded UI(buildRoleProductSubcatalog)가 따로 렌더하는 그룹을 일반 grid
    // 에서 빼기" 였는데 조건이 `is_dynamic` 전체였다. 모델 접근(`model.access.*`)도 동적 권한이지만
    // 전용 UI 가 없고 일반 권한 row 로 보여야 하므로(모델 수가 적어 subcatalog 가 과함), 그룹을
    // 명시해 좁힌다 — product 동작은 완전 동일하고 신규 동적 그룹만 정상 렌더된다.
    if (excludeDynamic && permission.is_dynamic && permission.group === "product_access") return;
    if (LEGACY_BUNDLE_PERMISSIONS.has(permission.code)) return;  // perm-atomic-split: 묶음 숨김.
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

export function statusBadge(text, className = "") {
  const badge = document.createElement("span");
  badge.className = `status-chip ${className}`.trim();
  badge.textContent = text;
  return badge;
}

/* ── Permission grid (collapsible details, from TASK-0027) ───────────── */

export function _updateCheckboxGroupSummary(section) {
  const total = section.querySelectorAll("input[type='checkbox']").length;
  const checked = section.querySelectorAll("input[type='checkbox']:checked").length;
  const badge = section.querySelector(".permission-group-counts");
  if (badge) badge.textContent = `${checked}/${total} 선택`;
}

export function _updateOverrideGroupSummary(section) {
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

export function renderPermissionGrid(containerEl, selectedCodes, disabled, mode, overrides, onChange, opts = {}) {
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

export function mergedAccount(accountId) {
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

export function mergedRole(roleKey) {
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

export function setAccountPending(accountId, patch) {
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

export function setRolePending(roleId, patch) {
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

export function setProductMetaPending(productId, patch) {
  const id = Number(productId);
  if (!id) return;
  const current = adminState.pending.productMeta.get(id) || {};
  const next = { ...current, ...patch };
  adminState.pending.productMeta.set(id, next);
  refreshPendingUI();
}

export function setProductDatabasesPending(productId, draft, dsKey) {
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
export function _ensureDbRulePending(productId, dsKey) {
  const k = _dbRuleStageKey(productId, dsKey);
  let e = adminState.pending.productDbRules.get(k);
  if (!e) {
    e = { creates: [], updates: {}, deletes: {}, approves: {} };
    adminState.pending.productDbRules.set(k, e);
  }
  return e;
}
export function _getDbRulePending(productId, dsKey) {
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
export function _settleDbRulePending(productId, dsKey) {
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
export function effectiveProductDatasources(product) {
  const e = adminState.pending.productDatasources.get(Number(product.id));
  if (e) {
    return e.desired.map((d) => ({ datasource_key: d.datasource_key, is_primary: !!d.is_primary }));
  }
  return (product.datasources || []).map((d) => ({
    datasource_key: d.datasource_key, is_primary: !!d.is_primary,
  }));
}
// 추가: desired 에 키 append(이미 있으면 no-op). 첫 바인딩이면 자동 primary.
export function stageAddDatasource(product, key) {
  const e = _ensureDatasourcePending(product.id, product.datasources);
  if (!e) return;
  const k = String(key || "").trim().toLowerCase();
  if (!k || e.desired.some((d) => d.datasource_key === k)) return;
  const firstBind = e.desired.length === 0;
  e.desired.push({ datasource_key: k, is_primary: firstBind });
  _settleDatasourcePending(product.id);
}
// 제거: desired 에서 키 제외. 제거 대상이 primary 였으면 남은 첫째를 primary 승격.
export function stageRemoveDatasource(product, key) {
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
export function stageSetPrimaryDatasource(product, key) {
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
export function _paintDsConnBadge(el, entry) {
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
export function _paintDsConnDot(el, entry) {
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
export function _probeDatasourceConn(key, { force = false } = {}) {
  const k = String(key || "").trim().toLowerCase();
  if (!k) return Promise.resolve({ state: "fail", error: "키 없음" });
  const cache = adminState.datasourceConnStatus;
  const _prev = cache.get(k);   // ds-conn-test: 429(쿨다운) 시 복원할 직전 상태 캡처(checking 덮어쓰기 전).
  if (!force) {
    // 확정된 상태(ok/unstable/down — checking 아닌 것)면 재사용.
    if (_prev && _prev.state && _prev.state !== "checking") return Promise.resolve(_prev);
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
      // ds-conn-test 쿨다운(429): 배지를 'down' 으로 떨어뜨리지 않고 직전 확정 상태 유지(없으면 확인 중).
      //  429 는 연결 실패가 아니라 재테스트 간격 제한이므로 상태 오분류를 막는다.
      if (e && e.status === 429) {
        const keep = (_prev && _prev.state && _prev.state !== "checking") ? _prev : { state: "checking" };
        cache.set(k, keep);
        return keep;
      }
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
// usage-metric-charts(2026-08-13): metric = 요약 카드로 고른 차트 지표(요청/호출/총 토큰/입력/
//   출력/캐시 읽기/캐시 쓰기/추정 비용). 기본은 종전 화면과 같은 총 토큰.
adminState.usage = { initialized: false, byAccount: [], drillRole: null, drillPage: 0, drillQuery: "", drillPageSize: 10, _renderDrill: null, selectedModels: null, metric: "total_tokens", _lastRaw: null, _lastKey: null };

// TASK-AIOPS: AI 운영 현황 패널 상태 (첫 진입 시 lazy-load, 새로고침 버튼으로 재조회).
adminState.aiOps = { initialized: false, data: null };

// TASK-20260623T014626-quota-ui-relocate: LLM 토큰 사용 한도 편집기 — 역할 상세 / 계정 상세 공용.
// (감사>LLM 사용량 화면에서 각 역할/계정 상세 속성으로 이전.)
//   opts = { scope: "role"|"account", id, daily, monthly, onSaved, inheritNote?, readOnly? }
//   값: 빈칸=상속(역할 기본은 무제한, 계정은 역할 기본 사용), 0=무제한(명시), 1 이상=한도, 1=사실상 차단.
//   TASK-20260623T030418-quota-rbac-permission: readOnly=true(quota.read 만 보유, quota.manage 없음)
//     → 입력 비활성 + 저장 버튼 제거 + "조회 전용" 안내. 섹션 자체는 quota.read 없으면 호출측이 미렌더.
export function buildQuotaEditor(opts) {
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

// feature-0038 Cycle 2: LLM 사용량 pane (loadUsage 외) 은 admin/usage.js 로 분리 (구 L1560–2238).

// TASK-0288: 관리 콘솔 탭 → 필요 권한 매핑. 값은 "하나라도 보유하면 표시"(OR) 권한 배열.
// 매핑 없는 탭(dashboard)은 항상 표시(console.access 보유 = 콘솔 진입 가능자 — overview 는 위젯별
// RBAC 스코프). 백엔드 엔드포인트 권한과 1:1 정합 — 탭은 보이는데 데이터는 403 인 괴리를 차단한다.
const ADMIN_TAB_PERMISSIONS = {
  accounts: ["account.read"],
  roles: ["role.read"],
  products: ["product.read", "product.manage"],
  datasources: ["datasource.read", "datasource.manage"],
  audits: ["audit.read.own", "audit.read.any"],
  // feature-0021 console-subtabs(2026-07-16): LLM 사용량·운영 현황·추론을 'AI 운영 현황' 단일
  //   탭(ai-console)으로 통합. **OR 게이트** — 세 조회 권한 중 하나라도 있으면 탭 노출(서브탭은
  //   initAiConsoleSubtabs 가 권한별 게이팅). **필수(fail-open 방지)** — 누락 시 전원 노출.
  "ai-console": ["console.usage.read", "console.aiops.read", "console.reasoning.read"],
  archives: ["conversation.archive.read.any"],
  // 샘플 검수(kb.sample.curate)는 메타데이터 탭 > 샘플쿼리 > 샘플 검수 큐 2차 보기로 통합(독립 탭 제거).
  // TASK-20260624-item11-metadata-glossary-enum (ROADMAP ITEM-11 MVP-1): 용어/ENUM 메타데이터 CRUD.
  // scope-key-unify: samples 서브뷰는 kb.sample.curate 권한이라, 부모 탭 게이트도 OR 로 넓혀
  // kb.sample.curate 단독 보유 큐레이터가 메타데이터 탭→samples 서브뷰에 도달 가능하게 한다
  // (서브뷰별 가시성은 _METADATA_SUBTAB_PERM 가 별도 분기).
  // graph-panel-perms(task4): 세부 권한 중 하나라도 있으면 탭 노출.
  //   kb.ingest.manual(묶음)은 함의로 아래 관리 권한을 effective 보유하므로 명시성 위해 유지.
  //   feature-0016 §45: graph.read 는 여기서 제거 — 그래프 뷰가 별도 최상위 탭(ADMIN_TAB_PERMISSIONS.graph)이 되어
  //   메타데이터 서브탭에서 빠졌으므로, graph.read 만 가진 역할이 서브탭 없는 빈 메타데이터 탭을 보지 않게 한다.
  metadata: ["metadata.glossary.read", "metadata.enum.read",
             "metadata.table.read", "metadata.column.read",
             // 검수(승급·거부) 단독 보유 큐레이터도 메타데이터 탭 → 해당 검토·검수 큐에 도달.
             "kb.sample.curate", "kb.glossary.curate", "kb.enum.curate"],
  // feature-0016 §45: 그래프 뷰 최상위 탭 — metadata.graph.read 단독 게이트.
  //   graph-perm-split(Critical §12.3, 2026-07-13): 그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리함에 따라
  //   kb.ingest.manual(묶음)은 더 이상 그래프 탭을 노출하지 않는다(백엔드 _METADATA_MANUAL_IMPLIES 에서도 제거).
  //   기존 묶음 보유자는 _backfill_graph_perm_split_v1 1회 backfill 로 metadata.graph.read 를 명시 보유해 그대로 노출.
  //   **필수(fail-open 방지)** — canSeeTab() 은 매핑 없는 탭을 fail-open 하므로 누락 = 권한 없는 사용자에게 탭 노출.
  graph: ["metadata.graph.read"],
  // perm-category-hier: 런타임 설정 pane(system.runtime.*)이 설정 탭 내부인데 탭 게이트에 누락돼
  //   있던 것을 보강 — runtime read/write 단독 보유자도 설정 탭에 도달 가능(백엔드 엔드포인트 권한과 정합).
  settings: ["system_prompt.global.read", "system_prompt.global.write",
             "system.runtime.read", "system.runtime.write"],
};

// perm-category-hier(Critical §12.3, 2026-07-14): 탭 → 소속 nav 카테고리의 최상위 '접근' 권한 매핑.
// canSeeTab = 카테고리 접근(AND) && 탭 권한(OR) — 카테고리 접근이 없으면 그 카테고리의 탭은 세부
// 권한을 보유해도 노출하지 않는다(카테고리 최상위 조회 게이트). 기존 배포 principal 은
// _backfill_console_category_access_v1(web_context.py) 1회 backfill 로 접근 권한을 자동 부여받아
// 노출 무손실. 매핑 없는 탭(dashboard/release-notes)은 카테고리 게이트 없음.
const ADMIN_TAB_CATEGORY_ACCESS = {
  accounts: "console.account.access",
  roles: "console.account.access",
  products: "console.product.access",
  datasources: "console.product.access",
  audits: "console.audit.access",
  archives: "console.audit.access",
  // feature-0021 console-subtabs: 통합 'AI 운영 현황' 탭 — 감사 카테고리(usage/ai-ops/reasoning 공통).
  "ai-console": "console.audit.access",
  metadata: "console.kb.access",
  graph: "console.kb.access",
  settings: "console.system.access",
};

function canSeeTab(tabKey) {
  // perm-category-hier: 카테고리 접근 게이트 선행(AND) — 없으면 탭 권한과 무관하게 미노출.
  const catPerm = ADMIN_TAB_CATEGORY_ACCESS[tabKey];
  if (catPerm && !can(catPerm)) return false;
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

// feature-0038 Cycle 2: AI 운영 현황 pane (loadAiOps 외) 은 admin/aiops.js 로 분리 (구 L2352–2626).

/* ── feature-0021: AI 추론 탭 (지침/스킬 레지스트리 · red-team 리뷰 활동 · 메모리 노트) ──
 * read-only 조회 — 데이터 소스: /api/admin/reasoning/{guidance,redteam,notes}.
 * 지침 목록은 progressive disclosure(메타만) — 항목 클릭 시 ?key= 단건 본문 로드. */
// console-ia(2026-07-16): '감사 > AI 추론' = red-team 리뷰 활동 + 메모리 노트만 (관측 데이터).
// 작동 지침/스킬 레지스트리는 '설정 > 프롬프트 > 작동 지침 / 스킬'로 분리(mountGuidanceRegistryPanel).
async function loadReasoning() {
  const body = $("reasoningBody");
  if (body) body.innerHTML = '<div class="admin-detail-empty">불러오는 중…</div>';
  try {
    const [redteam, notes] = await Promise.all([
      apiFetch("/api/admin/reasoning/redteam"),
      apiFetch("/api/admin/reasoning/notes"),
    ]);
    if (!adminState.reasoning) adminState.reasoning = { initialized: true, redteamCursor: null };
    adminState.reasoning.redteamCursor = redteam.next_cursor || null;
    renderReasoning(redteam, notes);
  } catch (e) {
    const msg = String((e && e.message) || e).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    if (body) body.innerHTML = '<div class="admin-detail-empty">AI 추론 정보를 불러오지 못했습니다: ' + msg + "</div>";
  }
}

// red-team 5축(redteam.py REDTEAM_REVIEW_PROMPT) 한글 라벨 + 추론 강도 라벨.
const _REASONING_AXIS_LABELS = {
  grounding: "근거", sql: "SQL", permission: "권한", completeness: "완전성", honesty: "정직성",
};
const _REASONING_LEVEL_LABELS = { low: "낮음", normal: "일반", high: "높음", max: "매우높음" };
function _reasoningAxisLabel(axis) { return _REASONING_AXIS_LABELS[axis] || axis || "기타"; }

function _reasoningVerdictBadge(esc, verdict) {
  const map = { pass: ["정상 통과", "ok"], revise: ["결함 수정", "warn"], error: ["리뷰 실패", "err"] };
  const [label, cls] = map[verdict] || [verdict || "?", ""];
  return `<span class="reasoning-verdict reasoning-verdict--${cls}">${esc(label)}</span>`;
}

// 이 리뷰가 개선한 실제 대화로의 딥링크. 예약 sentinel(__ 접두 — insight/ask worker,
// global, kb_manual 등)은 실제 대화가 아니므로 링크 대신 시스템 라벨만 (ai-ops feed 규약).
function _reasoningConvLink(esc, cid) {
  if (!cid) return "";
  const s = String(cid);
  if (s.startsWith("__")) {
    return `<span class="reasoning-conv reasoning-conv--system" title="시스템 활동 (실제 대화 아님)">시스템 · ${esc(s.slice(0, 16))}</span>`;
  }
  return `<a class="reasoning-conv" href="/?conversation=${encodeURIComponent(s)}" target="_blank" rel="noopener" title="이 개선이 일어난 대화 열기">대화 열기 ↗</a>`;
}

// 반복 수정 루프의 종료 사유(redteam.py stop_reason, 0045 컬럼) 한글 라벨.
// 결함이 남은 채 전달된 경우 "왜 더 돌지 않았는가"를 운영자가 즉시 알 수 있게 한다.
const _REASONING_STOP_REASONS = {
  resolved: "결함 해소",
  downgraded: "지적이 경고로 강등되어 종료",
  aborted: "사용자 '즉시 답변'/취소",
  review_wait_giveup: "리뷰어 응답 지연 — 대기 포기(초안 전달)",
  no_progress: "수정본이 직전과 동일 — 반복 중단",
  revise_collapsed: "수정본이 초안 대비 과도하게 축소 — 붕괴 방지로 중단",
  revise_failed: "수정 산출 실패",
  verify_error: "재검증 호출 실패",
  unverified: "재검증 미수행 설정",
  abort_check_failed: "중단 신호 확인 불가 — 보수적 종료",
  deadline: "시간 예산 도달",
  budget: "수정 상한 도달",
  backstop: "반복 안전 상한 도달",
  review_error: "리뷰 호출 실패",
};
function _reasoningStopReasonLabel(reason) {
  if (!reason) return "";
  return _REASONING_STOP_REASONS[reason] || String(reason);
}

// 진행 단계 타임라인 — ① 초안 → ② 적대 리뷰 → ③ 결함 수정 → ④ 재검증 → ⑤ 최종.
// 저장된 verdict/findings/revision_applied/rederive_*/verify_verdict 로 각 단계 상태를 재구성한다.
function _reasoningStageTimeline(esc, it) {
  const findings = Array.isArray(it.findings) ? it.findings : [];
  const err = it.verdict === "error";
  // severity 카운트는 실제 표시되는 findings 에서 일원화(손상 데이터에서 컬럼과의 내부 모순 방지, W4).
  // findings 파싱 실패(빈 배열)면 서버 집계 컬럼(block_count/warn_count)으로만 폴백.
  let nBlock = findings.filter((f) => f && f.severity === "BLOCK").length;
  let nWarn = findings.filter((f) => f && f.severity === "WARN").length;
  if (!findings.length) { nBlock = it.block_count || 0; nWarn = it.warn_count || 0; }
  // 미해결 결함(BLOCK) 여부 — 백엔드 verdict 규약(redteam.py): BLOCK 이 있으면 verdict=revise,
  // WARN-only 는 verdict=pass(자문 신호이며 수정 대상 아님). WARN-only 를 '수정 실패'로 오표기하지 않는다(B1).
  const hasBlock = it.verdict === "revise" || nBlock > 0;
  const warnOnly = !hasBlock && nWarn > 0;
  const stages = [];
  stages.push({ icon: "①", label: "초안 답변", state: "done", detail: "assistant 1차 답변 생성" });
  if (err) {
    // verdict=error 는 "리뷰어가 실패했다"만 뜻하지 않는다 — 사용자가 '즉시 답변'을 눌러
    // 중단됐거나(aborted) 우리가 대기를 포기한(review_wait_giveup) 경우도 같은 값으로 남는다
    // (redteam.py). stop_reason 을 함께 읽지 않으면 사용자 중단이 리뷰어 오류율로 집계되고,
    // 콘솔은 멀쩡한 중단을 "수행 실패"로 표시한다(§18.8 backend 패널 MAJOR).
    const stopLabel = _reasoningStopReasonLabel(it.stop_reason);
    const userStopped = it.stop_reason === "aborted" || it.stop_reason === "review_wait_giveup";
    stages.push({
      icon: "②", label: "적대 리뷰", state: userStopped ? "warn" : "err",
      detail: userStopped
        ? `리뷰 미완료 — ${stopLabel || it.stop_reason} (초안 그대로 전달)`
        : `리뷰 수행 실패 (fail-open — 초안 그대로 전달)${stopLabel ? " · " + stopLabel : ""}`,
    });
  } else if (hasBlock) {
    stages.push({ icon: "②", label: "적대 리뷰", state: "warn", detail: `결함 검출 — BLOCK ${nBlock}${nWarn ? " · WARN " + nWarn : ""}` });
  } else if (warnOnly) {
    stages.push({ icon: "②", label: "적대 리뷰", state: "done", detail: `통과 — 경고(자문) ${nWarn}건, 수정 불필요` });
  } else {
    stages.push({ icon: "②", label: "적대 리뷰", state: "done", detail: "결함 없음 — 통과" });
  }
  if (it.revision_applied) {
    let how;
    if (it.rederive_applied) {
      const ax = it.rederive_axis
        ? String(it.rederive_axis).split(",").map((a) => _reasoningAxisLabel(a.trim())).filter(Boolean).join("·") : "";
      how = `도구 재추론${ax ? " (" + ax + ")" : ""}${it.rederive_tool_rounds ? " · " + it.rederive_tool_rounds + "라운드" : ""}`;
    } else {
      how = "텍스트 재작성";
    }
    // 반복 수정 라운드 수(0045) — 결함 해소까지 몇 번 돌았는지. 1회면 표기 생략(노이즈).
    const rounds = Number(it.revision_rounds || 0);
    if (rounds > 1) how += ` · 수정 ${rounds}회 반복`;
    stages.push({ icon: "③", label: "결함 수정", state: "done", detail: how });
  } else if (err) {
    stages.push({ icon: "③", label: "결함 수정", state: "na", detail: "해당 없음" });
  } else if (hasBlock) {
    stages.push({ icon: "③", label: "결함 수정", state: "skip", detail: "미적용 (수정 실패 — 초안 유지, fail-open)" });
  } else if (warnOnly) {
    stages.push({ icon: "③", label: "결함 수정", state: "na", detail: "불필요 (경고성 자문 — 수정 대상 아님)" });
  } else {
    stages.push({ icon: "③", label: "결함 수정", state: "na", detail: "불필요 (결함 없음)" });
  }
  const unresolved = Number(it.unresolved_block_count || 0);
  if (it.verify_verdict) {
    const vpass = it.verify_verdict === "pass";
    stages.push({
      icon: "④", label: "재검증", state: vpass ? "done" : "warn",
      detail: vpass
        ? "수정본 재검증 통과 — 지적된 결함 해소"
        : `재검증에서 결함 잔존${unresolved ? " — BLOCK " + unresolved + "건 미해소" : ""}`,
    });
  } else {
    stages.push({ icon: "④", label: "재검증", state: "na", detail: "해당 없음 (강도별 skip 또는 미수행)" });
  }
  // ⑤ 최종 전달 — 결함이 남은 채 전달됐으면 '개선된 답변'으로 포장하지 않는다(정직성).
  // stop_reason(0045)이 왜 멈췄는지 알려준다: 사용자 '즉시 답변'/취소, 무진전, 수정 실패 등.
  if (unresolved > 0) {
    stages.push({
      icon: "⑤", label: "최종 전달", state: "warn",
      detail: `결함 잔존 상태로 전달 — BLOCK ${unresolved}건 미해소${
        _reasoningStopReasonLabel(it.stop_reason) ? " (" + _reasoningStopReasonLabel(it.stop_reason) + ")" : ""}`,
    });
  } else {
    stages.push({
      icon: "⑤", label: "최종 전달", state: "done",
      detail: it.revision_applied ? "결함 해소 후 개선된 답변 전달" : "답변 전달",
    });
  }
  const stageHtml = stages.map((s) =>
    `<li class="reasoning-stage reasoning-stage--${s.state}">
      <span class="reasoning-stage-icon" aria-hidden="true">${esc(s.icon)}</span>
      <span class="reasoning-stage-body"><span class="reasoning-stage-label">${esc(s.label)}</span><span class="reasoning-stage-detail">${esc(s.detail)}</span></span>
    </li>`).join("");
  return `<ol class="reasoning-timeline">${stageHtml}</ol>`;
}

// 결함별 수정 전/후 대비 — 지적(수정 전) → 수정 방향, 근거(evidence).
function _reasoningFindingHtml(esc, f) {
  const sev = (f.severity === "BLOCK") ? "block" : "warn";
  const claim = esc(f.claim || "(내용 없음)");
  const fix = f.fix_hint ? esc(f.fix_hint) : "";
  const ev = f.evidence ? esc(f.evidence) : "";
  const axisKey = f.axis || "etc";
  return `<div class="reasoning-finding reasoning-finding--${sev}">
    <div class="reasoning-finding-tags">
      <span class="reasoning-sev reasoning-sev--${sev}">${esc(f.severity || "?")}</span>
      <span class="reasoning-axis reasoning-axis--${esc(axisKey)}">${esc(_reasoningAxisLabel(f.axis))}</span>
    </div>
    <div class="reasoning-ba">
      <div class="reasoning-ba-col reasoning-ba-col--before"><span class="reasoning-ba-tag">수정 전 · 지적</span><span class="reasoning-ba-text">${claim}</span></div>
      ${fix ? `<span class="reasoning-ba-arrow" aria-hidden="true">→</span><div class="reasoning-ba-col reasoning-ba-col--after"><span class="reasoning-ba-tag">수정 방향</span><span class="reasoning-ba-text">${fix}</span></div>` : ""}
    </div>
    ${ev ? `<div class="reasoning-finding-ev"><span class="reasoning-ba-tag">근거</span> ${ev}</div>` : ""}
  </div>`;
}

// 현재 목록 리뷰들의 findings 를 5축별로 집계한 배지 요약.
function _reasoningAxisSummary(esc, reviews) {
  const counts = {};
  let total = 0;
  reviews.forEach((it) => {
    (Array.isArray(it.findings) ? it.findings : []).forEach((f) => {
      const ax = f.axis || "etc";
      counts[ax] = (counts[ax] || 0) + 1;
      total += 1;
    });
  });
  if (!total) return "";
  const order = ["grounding", "sql", "permission", "completeness", "honesty"];
  const keys = order.filter((k) => counts[k]).concat(Object.keys(counts).filter((k) => order.indexOf(k) < 0));
  const badges = keys.map((k) =>
    `<span class="reasoning-axis-badge reasoning-axis--${esc(k)}">${esc(_reasoningAxisLabel(k))} <b>${counts[k]}</b></span>`).join("");
  return `<div class="reasoning-axis-summary"><span class="reasoning-axis-summary-label">검출 축 분포 (현재 목록 ${total}건):</span>${badges}</div>`;
}

/* ── 회차 단계 원장 (0048 redteam_review_rounds) ──────────────────────────────
 * 요약 행은 '최초 리뷰 + 마지막 재검증'만 담아 중간 회차가 보이지 않았다. 원장이 있으면
 * 자가검증(0회차) → N회차 수정 → N회차 재검증 을 **진행 순서 그대로(asc)** 펼쳐 보여준다.
 * 각 회차는 <details> 라 개별 접기/펼치기 되며 기본은 접힘(스크롤 격리). */
const _REASONING_PHASE_LABELS = { review: "자가검증", revise: "결함 수정", verify: "재검증" };
const _REASONING_METHOD_LABELS = { rederive: "도구 재추론", rewrite: "텍스트 재작성" };
// 라운드-로컬 메모(redteam.py rounds_ledger note) — 그 회차가 왜 마지막인지.
const _REASONING_ROUND_NOTES = {
  revise_failed: "수정 산출 실패 — 직전 답변 유지",
  no_progress: "수정본이 직전과 동일 — 반복 중단",
  revise_collapsed: "수정본이 초안 대비 과도 축소 — 채택 취소",
  verify_error: "재검증 호출 실패 — 마지막 수정본 채택",
  unverified: "재검증 미수행 설정",
};

function _reasoningRoundLabel(r) {
  const idx = Number(r.round_index || 0);
  const phase = _REASONING_PHASE_LABELS[r.phase] || r.phase || "단계";
  return idx === 0 ? `최초 ${phase}` : `${idx}회차 ${phase}`;
}

// 회차 1단계 — summary(회차·단계·판정 요약) + 본문(지적 목록 또는 수정 방식).
// showAt=false 면 회차 시각을 렌더하지 않는다 — 원장 도입 초기 기록은 루프 종료 시
// 배치 INSERT 라 회차 시각이 전부 같다(같은 값 반복은 정보가 있는 것처럼 오도한다).
function _reasoningRoundHtml(esc, r, showAt) {
  const findings = Array.isArray(r.findings) ? r.findings : [];
  const nBlock = findings.length
    ? findings.filter((f) => f && f.severity === "BLOCK").length : Number(r.block_count || 0);
  const nWarn = findings.length
    ? findings.filter((f) => f && f.severity === "WARN").length : Number(r.warn_count || 0);
  const note = r.note ? (_REASONING_ROUND_NOTES[r.note] || String(r.note)) : "";
  const bits = [];
  let state = "done";
  let body;
  if (r.phase === "revise") {
    const method = _REASONING_METHOD_LABELS[r.revise_method] || r.revise_method || "";
    const axis = r.revise_axis
      ? String(r.revise_axis).split(",").map((a) => _reasoningAxisLabel(a.trim())).filter(Boolean).join("·") : "";
    if (method) bits.push(method + (axis ? ` (${axis})` : ""));
    if (Number(r.tool_rounds || 0) > 0) bits.push(`도구 ${r.tool_rounds}라운드`);
    if (r.answer_chars != null) bits.push(`${r.answer_chars}자`);
    if (r.note) state = "skip";
    const rows = [
      method ? `<li>수정 방식: ${esc(method)}${axis ? " · 축 " + esc(axis) : ""}</li>` : "",
      Number(r.tool_rounds || 0) > 0 ? `<li>도구 재추론 라운드: ${esc(r.tool_rounds)}</li>` : "",
      r.answer_chars != null ? `<li>수정본 길이: ${esc(r.answer_chars)}자 (본문은 감사 목적상 미저장)</li>` : "",
      note ? `<li>결과: ${esc(note)}</li>` : "<li>결과: 채택 — 재검증으로 진행</li>",
    ].filter(Boolean).join("");
    body = `<ul class="reasoning-round-facts">${rows}</ul>`;
  } else {
    if (r.verdict === "revise") {
      state = "warn";
      bits.push(`결함 검출 — BLOCK ${nBlock}${nWarn ? " · WARN " + nWarn : ""}`);
    } else if (r.verdict === "pass") {
      bits.push(nWarn ? `통과 — 경고(자문) ${nWarn}건` : "통과 — 결함 없음");
    } else if (r.note) {
      state = "skip";
    } else {
      bits.push("판정 기록 없음");
    }
    body = findings.length
      ? findings.map((f) => _reasoningFindingHtml(esc, f)).join("")
      : '<div class="reasoning-round-empty">이 단계에 기록된 지적이 없습니다.</div>';
  }
  // 폐기 사유는 **접힌 요약에도** 붙인다 — 회차가 10단계까지 늘면 목록을 훑는 것만으로
  // "왜 여기서 멈췄나" 가 보여야 한다(라이브 다회차 표본에서 실측된 가독성 결함: 사유가
  // 본문에만 있어 그 회차를 펼쳐야 알 수 있었다).
  if (note) bits.push(note);
  const at = (showAt && r.created_at) ? String(r.created_at).replace("T", " ").slice(11, 19) : "";
  return `<details class="reasoning-round reasoning-round--${state}">
    <summary class="reasoning-round-summary">
      <span class="reasoning-round-label">${esc(_reasoningRoundLabel(r))}</span>
      <span class="reasoning-round-detail">${esc(bits.filter(Boolean).join(" · "))}</span>
      ${at ? `<span class="reasoning-round-at">${esc(at)}</span>` : ""}
    </summary>
    <div class="reasoning-round-body">${body}</div>
  </details>`;
}

// 한 리뷰(run)의 회차 목록. 원장이 없는 이전 기록은 요약 타임라인만으로 폴백한다.
function _reasoningRoundsHtml(esc, it) {
  const rounds = Array.isArray(it.rounds) ? it.rounds : [];
  if (!rounds.length) {
    return '<div class="reasoning-rounds-empty">회차 원장이 없는 기록입니다 (원장 도입 이전) — 위 진행 단계 요약만 표시합니다.</div>';
  }
  const truncated = it.rounds_truncated
    ? '<div class="reasoning-rounds-empty">회차가 많아 앞부분만 표시합니다 (원장에는 전부 기록되어 있습니다).</div>'
    : "";
  // 회차 시각이 전부 동일하면(배치 기록된 초기 데이터) 시각을 숨긴다 — 서로 다른 값이
  // 하나라도 있으면 회차별 실제 종료 시각이므로 표시한다.
  const stamps = new Set(rounds.map((r) => r.created_at || ""));
  const showAt = rounds.length === 1 || stamps.size > 1;
  // 숨겼다는 사실은 **알린다** — 조용히 지우면 "시각이 원래 없다" 와 구분되지 않는다
  // (codex 리뷰 P2, 프로젝트의 '무언의 절단 금지' 규약과 동일 계열).
  const stampNote = showAt ? ""
    : '<div class="reasoning-rounds-empty">회차 시각은 이 기록이 일괄 저장돼 전부 동일합니다 — 오해를 막기 위해 표시하지 않습니다(이후 기록부터 회차별 실제 시각).</div>';
  return `<div class="reasoning-rounds">
    <div class="reasoning-rounds-title">자가검증 · 재검증 회차 (${rounds.length}단계 · 진행 순서)</div>
    ${rounds.map((r) => _reasoningRoundHtml(esc, r, showAt)).join("")}
    ${stampNote}${truncated}
  </div>`;
}

function _reasoningReviewRowHtml(esc, it) {
  const findings = Array.isArray(it.findings) ? it.findings : [];
  const rounds = Array.isArray(it.rounds) ? it.rounds : [];
  // 회차 원장이 있으면 최초 리뷰 findings 는 0회차 안에 그대로 들어 있으므로 중복 표시하지 않는다.
  const findingHtml = (!rounds.length && findings.length)
    ? findings.map((f) => _reasoningFindingHtml(esc, f)).join("") : "";
  // 재검증에서 끝내 해소되지 않은 BLOCK — 결함 잔존 답변이 무엇 때문에 잔존인지 그대로 보인다.
  // (verify_findings 는 0045 컬럼. 구 이미지/구 행에서는 비어 있으므로 최초 리뷰 findings 로
  // 폴백한다 — 폴백이 없으면 ⑤가 "BLOCK N건 미해소"라 말하면서 내용은 못 보여 준다.)
  const _vfRaw = (Array.isArray(it.verify_findings) && it.verify_findings.length)
    ? it.verify_findings : findings;
  const vf = (Array.isArray(_vfRaw) ? _vfRaw : []).filter((f) => f && f.severity === "BLOCK");
  const unresolvedHtml = (Number(it.unresolved_block_count || 0) > 0 && vf.length)
    ? `<div class="reasoning-unresolved">
        <div class="reasoning-unresolved-title">재검증에서 해소되지 않은 지적 (${vf.length}건)</div>
        ${vf.map((f) => _reasoningFindingHtml(esc, f)).join("")}
      </div>`
    : "";
  const lvl = _REASONING_LEVEL_LABELS[it.reasoning_level] || it.reasoning_level || "";
  const metaBits = [
    it.created_at ? esc(String(it.created_at).replace("T", " ").slice(0, 19)) : "",
    lvl ? esc(lvl) + " 강도" : "",
    it.is_group ? "그룹" : "1:1",
    it.latency_ms != null ? `${esc(it.latency_ms)}ms` : "",
    it.model ? esc(it.model) : "",
  ].filter(Boolean).join(" · ");
  const unresolvedN = Number(it.unresolved_block_count || 0);
  const roundsBadge = rounds.length
    ? `<span class="reasoning-review-rounds-badge">회차 ${rounds.length}단계</span>` : "";
  const unresolvedBadge = unresolvedN > 0
    ? `<span class="reasoning-review-flag">결함 잔존 ${unresolvedN}</span>` : "";
  // 리뷰(run) 단위도 접이식 — 대화 안에서 회차 묶음이 한꺼번에 펼쳐져 스크롤을 삼키지 않도록.
  return `<details class="reasoning-review-row">
    <summary class="reasoning-review-head">
      ${_reasoningVerdictBadge(esc, it.verdict)}
      <span class="reasoning-review-meta">${metaBits}</span>
      ${roundsBadge}${unresolvedBadge}
    </summary>
    <div class="reasoning-review-body">
      ${_reasoningStageTimeline(esc, it)}
      ${_reasoningRoundsHtml(esc, it)}
      ${findingHtml ? `<div class="reasoning-findings">${findingHtml}</div>` : ""}
      ${unresolvedHtml}
    </div>
  </details>`;
}

/* ── 대화 단위 격리 컨테이너 ────────────────────────────────────────────────
 * 정렬 계약(백엔드 _query_conversation_page 와 동일): 대화는 **최근 리뷰 순 desc**,
 * 대화 안의 리뷰는 **진행 순서 asc**. 서버가 이미 그 순서로 내려주므로 여기서는
 * conversation_id 로 묶기만 한다(재정렬 금지 — 계약 단일화). */
function _reasoningConvTitle(esc, cid) {
  if (!cid) return "대화 미지정 (시스템 활동)";
  const s = String(cid);
  if (s.startsWith("__")) return "시스템 · " + esc(s.slice(0, 24));
  // 대화 id 는 `YYYYMMDDHHMMSS-<hash>` — 앞 N자만 자르면 같은 분에 시작된 대화가 같은
  // 라벨로 보인다(실측). 생성 시각 + 해시 접두로 사람이 구분 가능하게 표기한다.
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})\d{2}-([0-9a-f]+)$/i.exec(s);
  if (m) return `대화 ${esc(m[2])}-${esc(m[3])} ${esc(m[4])}:${esc(m[5])} · ${esc(m[6].slice(0, 8))}`;
  return "대화 " + esc(s.slice(0, 16));
}

function _reasoningConvGroupHtml(esc, conv, items, open) {
  const cid = conv.conversation_id;
  const unresolvedTotal = items.reduce((a, it) => a + Number(it.unresolved_block_count || 0), 0);
  const roundTotal = items.reduce((a, it) => a + (Array.isArray(it.rounds) ? it.rounds.length : 0), 0);
  const lastAt = conv.last_at ? String(conv.last_at).replace("T", " ").slice(0, 19) : "";
  const capped = conv.capped
    ? `<div class="reasoning-conv-capped">이 대화의 리뷰 ${esc(conv.review_count)}건 중 최근 ${esc(items.length)}건만 표시합니다.</div>`
    : "";
  const metaBits = [
    `리뷰 ${items.length}건`,
    roundTotal ? `회차 ${roundTotal}단계` : "",
    lastAt ? `최근 ${esc(lastAt)}` : "",
  ].filter(Boolean).join(" · ");
  return `<details class="reasoning-conv-group"${open ? " open" : ""}>
    <summary class="reasoning-conv-head">
      <span class="reasoning-conv-title">${_reasoningConvTitle(esc, cid)}</span>
      <span class="reasoning-conv-meta">${metaBits}</span>
      ${unresolvedTotal ? `<span class="reasoning-conv-flag">결함 잔존 ${unresolvedTotal}</span>` : ""}
    </summary>
    <div class="reasoning-conv-body">
      <div class="reasoning-conv-actions">${_reasoningConvLink(esc, cid)}</div>
      ${capped}
      ${items.map((it) => _reasoningReviewRowHtml(esc, it)).join("")}
    </div>
  </details>`;
}

// conversations 메타 + flat items → 대화 그룹 HTML. conversations 가 없는 응답(구 서버)
// 에서도 items 의 등장 순서로 그룹을 유도해 동작한다.
function _reasoningConvGroupsHtml(esc, conversations, items, firstOpen) {
  const byConv = new Map();
  items.forEach((it) => {
    const k = it.conversation_id || "";
    if (!byConv.has(k)) byConv.set(k, []);
    byConv.get(k).push(it);
  });
  let convs = Array.isArray(conversations) ? conversations : [];
  if (!convs.length) {
    convs = Array.from(byConv.keys()).map((k) => {
      const g = byConv.get(k);
      return {
        conversation_id: k || null, review_count: g.length, returned_count: g.length,
        capped: false, last_at: g.length ? g[g.length - 1].created_at : null,
      };
    });
  }
  return convs.map((c, i) => {
    const g = byConv.get(c.conversation_id || "") || [];
    if (!g.length) return "";
    return _reasoningConvGroupHtml(esc, c, g, firstOpen && i === 0);
  }).join("");
}

function renderReasoning(redteam, notes) {
  const body = $("reasoningBody");
  if (!body) return;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // feature-0043 TASK-20260831T100000 — **빈 화면이 스스로를 설명하게** 한다.
  //
  // 서버 측 red-team 검증은 `agent_core.run_agent` 안에서 돌았고, 그 경로가 게이트에 막힌
  // 뒤로는 새 리뷰가 쌓이지 않는다. 그런데 이 화면은 종전 그대로 "0 · 0 · 0" 을 그렸다 —
  // 운영자는 그것을 "검증이 통과하고 있다" 또는 "고장" 으로 읽을 뿐, **애초에 돌지 않는다**
  // 는 사실은 어디에도 없었다. 지표의 침묵이 곧 오독이 되는 자리다.
  //
  // 지표는 지우지 않는다(과거 기록은 그때의 사실이다). 위에 범위를 한 줄로 얹는다.
  const gateNote = llmBlocked()
    ? `<p class="admin-llm-inactive-note">서버가 답변을 만들지 않으므로 <b>서버 측 자가 리뷰는`
      + ` 실행되지 않습니다</b>(고장이 아닙니다). 아래 수치는 전환 이전 기록입니다.</p>`
    : "";

  // ── 1. red-team 리뷰 활동 ──
  const st = (redteam && redteam.stats) || {};
  const statHtml = `
    <div class="reasoning-stats">
      <div class="reasoning-stat"><div class="reasoning-stat-num">${esc(st.reviews_24h ?? "–")}</div><div class="reasoning-stat-label">리뷰 (24h)</div></div>
      <div class="reasoning-stat"><div class="reasoning-stat-num">${esc(st.reviews_7d ?? "–")}</div><div class="reasoning-stat-label">리뷰 (7d)</div></div>
      <div class="reasoning-stat"><div class="reasoning-stat-num">${esc(st.revise_7d ?? "–")}</div><div class="reasoning-stat-label">결함 검출 (7d)</div></div>
      <div class="reasoning-stat"><div class="reasoning-stat-num">${esc(st.revisions_applied_7d ?? "–")}</div><div class="reasoning-stat-label">수정 적용 (7d)</div></div>
      <div class="reasoning-stat"><div class="reasoning-stat-num">${esc(st.errors_7d ?? "–")}</div><div class="reasoning-stat-label">리뷰 실패 (7d)</div></div>
      <div class="reasoning-stat${Number(st.unresolved_7d || 0) > 0 ? " reasoning-stat--warn" : ""}"><div class="reasoning-stat-num">${esc(st.unresolved_7d ?? "–")}</div><div class="reasoning-stat-label">결함 잔존 전달 (7d)</div></div>
      <div class="reasoning-stat"><div class="reasoning-stat-num">${st.avg_latency_ms_7d != null ? esc(st.avg_latency_ms_7d) + "ms" : "–"}</div><div class="reasoning-stat-label">평균 지연 (7d)</div></div>
    </div>`;
  const reviews = Array.isArray(redteam && redteam.items) ? redteam.items : [];
  // 누적 목록 추적 — "더 보기" 페이징 후 축 집계 재계산 기준(W2).
  if (adminState.reasoning) adminState.reasoning.reviewsAll = reviews.slice();
  const axisSummaryHtml = _reasoningAxisSummary(esc, reviews);
  const _reviewEmptyMsg = (redteam && redteam.pg_available === false)
    ? "저장소(PG)에 연결할 수 없습니다."
    : (redteam && redteam.table_available === false)
      ? "자가 리뷰 저장소가 아직 준비되지 않았습니다 (마이그레이션/배포 대기)."
      : "기록된 리뷰가 없습니다.";
  const conversations = Array.isArray(redteam && redteam.conversations) ? redteam.conversations : [];
  const reviewListHtml = reviews.length
    ? _reasoningConvGroupsHtml(esc, conversations, reviews, true)
    : '<div class="admin-detail-empty">' + _reviewEmptyMsg + "</div>";
  const moreBtnHtml = adminState.reasoning && adminState.reasoning.redteamCursor
    ? '<button type="button" class="btn-secondary" id="reasoningMoreBtn">대화 더 보기</button>' : "";

  // ── 2. 메모리 노트 현황 ──
  const nItems = Array.isArray(notes && notes.items) ? notes.items : [];
  const noteRows = nItems.map((n) => {
    const days = Math.floor((n.expires_in_sec || 0) / 86400);
    const hours = Math.floor(((n.expires_in_sec || 0) % 86400) / 3600);
    return `<tr><td>${esc(n.scope === "session" ? "세션" : "제품")}</td><td class="reasoning-note-ident">${esc(n.ident)}</td>
      <td>${esc(Math.round((n.size_bytes || 0) / 102.4) / 10)}KB</td><td>${esc(n.updated_at || "")}</td>
      <td>${days}일 ${hours}시간 후 만료</td></tr>`;
  }).join("");
  const notesHtml = nItems.length
    ? `<table class="admin-table reasoning-notes-table"><thead><tr><th>구분</th><th>식별자</th><th>크기</th><th>갱신</th><th>TTL</th></tr></thead><tbody>${noteRows}</tbody></table>`
    : '<div class="admin-detail-empty">축적된 노트가 없습니다.</div>';

  body.innerHTML = `
    ${gateNote}
    <div class="reasoning-section">
      <h3 class="reasoning-section-title">자가 적대 리뷰 활동</h3>
      <!-- 안내는 "이 화면이 무엇인가" 한 줄로 끝낸다. 접기/펼치기·정렬 같은 조작법과 다른
           화면 경로(설정 > …)를 여기 나열하면, 화면을 보면 아는 것을 매번 읽히는 벽이 된다
           (사용자 지적 2026-07-29). 상세 계약은 FUNCTION.md §7.5 가 정본. -->
      <p class="reasoning-section-hint">답변을 전달하기 전에 별도 모델(red-team)이 초안을 적대적으로 검증하고 결함을 고친 기록입니다.</p>
      ${statHtml}
      <div id="reasoningAxisSummaryWrap">${axisSummaryHtml}</div>
      <div class="reasoning-review-list" id="reasoningReviewList">${reviewListHtml}</div>
      <div class="reasoning-more">${moreBtnHtml}</div>
    </div>
    <div class="reasoning-section">
      <h3 class="reasoning-section-title">메모리 노트 (임시 파일)</h3>
      <p class="reasoning-section-hint">세션(대화)/제품별 자가리뷰·메모리 노트 현황입니다. TTL 만료 시 주기 정리로 자동 삭제됩니다 (경로: ${esc((notes && notes.root) || "/shared/agent-notes")}).</p>
      ${notesHtml}
    </div>`;

  const moreBtn = $("reasoningMoreBtn");
  if (moreBtn) moreBtn.addEventListener("click", loadReasoningMoreReviews);
}

async function loadReasoningMoreReviews() {
  const cursor = adminState.reasoning && adminState.reasoning.redteamCursor;
  if (!cursor) return;
  const listEl = $("reasoningReviewList");
  const moreBtn = $("reasoningMoreBtn");
  if (moreBtn) moreBtn.disabled = true;
  try {
    const data = await apiFetch(`/api/admin/reasoning/redteam?cursor=${encodeURIComponent(cursor)}`);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const newItems = data.items || [];
    // 대화 그룹 단위 append — 기존 그룹의 펼침 상태를 건드리지 않는다(innerHTML 재생성 금지).
    // 서버가 대화를 keyset 으로 페이징하므로 이미 표시된 대화가 다시 오지 않는다.
    if (listEl && newItems.length) {
      listEl.insertAdjacentHTML(
        "beforeend", _reasoningConvGroupsHtml(esc, data.conversations, newItems, false));
    }
    // 축 집계는 누적 목록 기준 재계산 — "현재 목록 N건" 라벨과 표시 행을 정합(W2).
    if (adminState.reasoning) {
      const all = (adminState.reasoning.reviewsAll || []).concat(newItems);
      adminState.reasoning.reviewsAll = all;
      const sumWrap = $("reasoningAxisSummaryWrap");
      if (sumWrap) sumWrap.innerHTML = _reasoningAxisSummary(esc, all);
    }
    adminState.reasoning.redteamCursor = data.next_cursor || null;
    if (!data.next_cursor && moreBtn) moreBtn.remove();
  } catch (e) {
    console.error("[reasoning] more reviews failed:", e);
  } finally {
    if (moreBtn) moreBtn.disabled = false;
  }
}

export async function showGuidanceDetail(key, detailId) {
  // console-ia: detailId 로 마운트 지점 지정(설정 프롬프트 패널 재사용). 미지정 시 기존 reasoning pane.
  const detail = $(detailId || "reasoningGuidanceDetail");
  if (!detail || !key) return;
  detail.hidden = false;
  detail.textContent = "불러오는 중…";
  try {
    const data = await apiFetch(`/api/admin/reasoning/guidance?key=${encodeURIComponent(key)}`);
    const item = data && data.item;
    if (!item) { detail.textContent = "본문을 불러올 수 없습니다."; return; }
    detail.innerHTML = "";
    const head = document.createElement("div");
    head.className = "reasoning-guidance-detail-head";
    const title = document.createElement("strong");
    title.textContent = item.name || item.key;
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn-secondary";
    closeBtn.textContent = "닫기";
    closeBtn.addEventListener("click", () => { detail.hidden = true; });
    head.append(title, closeBtn);
    const pre = document.createElement("pre");
    pre.className = "reasoning-guidance-pre";
    pre.textContent = item.text || "(비어 있음)";
    detail.append(head, pre);
    detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    detail.textContent = `본문 조회 실패: ${(e && e.message) || e}`;
  }
}

/* ── feature-0021 console-subtabs(2026-07-16): 재사용 pane 서브탭 헬퍼 ──────────
 * container 안의 [data-*-subtab] 버튼 ↔ [data-*-subpane] 컨텐츠를 전환한다.
 * onActivate(key) 는 각 서브탭이 처음 활성화될 때 1회 호출(lazy load). visibleKeys 로
 * 권한 게이팅(미포함 서브탭 버튼 숨김) — 첫 표시 서브탭은 보이는 것 중 첫째. */
export function bindPaneSubtabs(root, attr, onActivate, opts) {
  opts = opts || {};
  const btns = Array.from(root.querySelectorAll("[data-" + attr + "-subtab]"));
  const panes = Array.from(root.querySelectorAll("[data-" + attr + "-subpane]"));
  if (!btns.length) return;
  const visible = opts.visibleKeys || null;
  const mounted = new Set();
  const keyOf = (el, kind) => el.getAttribute("data-" + attr + "-" + kind);

  function activate(key) {
    btns.forEach((b) => {
      const on = keyOf(b, "subtab") === key;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    panes.forEach((p) => {
      const on = keyOf(p, "subpane") === key;
      p.classList.toggle("is-active", on);
      p.hidden = !on;
    });
    if (!mounted.has(key)) {
      mounted.add(key);
      try { onActivate(key); } catch (e) { console.error("[subtab] activate failed:", key, e); }
    }
  }

  // 권한 게이팅: visible 목록에 없는 서브탭 버튼·pane 숨김.
  if (visible) {
    btns.forEach((b) => { b.style.display = visible.includes(keyOf(b, "subtab")) ? "" : "none"; });
  }
  btns.forEach((b) => {
    if (b.dataset.subtabBound === "1") return;
    b.dataset.subtabBound = "1";
    b.addEventListener("click", () => activate(keyOf(b, "subtab")));
  });
  // 첫 표시: 보이는 것 중 첫째(권한 게이팅 반영).
  const firstKey = (visible ? btns.filter((b) => visible.includes(keyOf(b, "subtab"))) : btns)
    .map((b) => keyOf(b, "subtab"))[0];
  if (firstKey) {
    activate(firstKey);
  } else {
    // 방어: 보이는 서브탭이 없으면(권한 0) 정적 is-active 마크업이 미로드 상태로 남지 않도록 전부 숨김.
    panes.forEach((p) => { p.classList.remove("is-active"); p.hidden = true; });
  }
}

// feature-0043 TASK-20260901T110000 — 서브탭이 재편되면서 옛 키 두 개가 사라졌다
// (`usage`·`reasoning` → '기록' 안 섹션, `exttasks` → '브리지 작업'). 서버·대시보드 위젯이
// 보내는 옛 키를 흡수하지 않으면 그 deep-link 는 빈 pane 에 착지한다 — feature-0021 이 같은
// 이유로 이 표를 만들었고, 그때 적대검증 MAJOR#1 로 잡힌 결함이 정확히 이것이다.
//
// `switchTab`(최상위 탭 키)과 `activateAiConsoleSubtab`(서브탭 키)이 **같은 표**를 읽는다:
// 한쪽만 고치면 그쪽으로 오지 않는 호출부가 조용히 아무것도 하지 않는다.
const _AI_SUBTAB_ALIAS = {
  usage: "archive", "ai-ops": "ops", reasoning: "archive",
  // feature-0041 의 '외부 AI 작업' 은 '브리지 작업' 으로 흡수됐다.
  exttasks: "tasks",
  // 신규 키도 자기 자신으로 매핑해 둔다 — 위젯이 새 키를 보내기 시작해도 동작한다.
  ops: "ops", tasks: "tasks", tools: "tools", archive: "archive",
};

// deep-link 로 지정된 ai-console 서브탭을 활성화(보이는 서브탭일 때만). 버튼 click 으로 트리거해
// bindPaneSubtabs 의 activate(권한 게이팅·lazy load 포함)를 재사용한다.
export function activateAiConsoleSubtab(sub) {
  const pane = document.querySelector('.admin-pane[data-admin-pane="ai-console"]');
  if (!pane) return;
  // 옛 키(`usage`/`reasoning`/`exttasks`)를 여기서도 흡수한다 — `switchTab` 만 고치면
  // 그쪽으로 오지 않는 호출부(`usage.js` 의 그래프 네비게이션 등)가 조용히 아무것도 하지
  // 않는다. 별칭 판정은 **한 표**에서 나온다.
  const key = _AI_SUBTAB_ALIAS[sub] || sub;
  const btn = pane.querySelector('[data-ai-subtab="' + key + '"]');
  if (btn && btn.style.display !== "none") btn.click();
}

// 'AI 운영 현황' 통합 탭 서브탭 초기화 — 권한별 게이팅 + lazy load.
function initAiConsoleSubtabs() {
  const pane = document.querySelector('.admin-pane[data-admin-pane="ai-console"]');
  if (!pane) return;
  // feature-0043 TASK-20260901T110000 — 외부AI 운영축 4서브탭.
  //
  // 표시 게이트는 종전 권한 축을 그대로 쓴다(신규 권한을 만들지 않는다):
  //   ops·tasks·tools = `console.aiops.read`(운영 관제)
  //   archive         = `console.usage.read`(토큰·비용) **또는** `console.reasoning.read`
  //                     (서버 자가 리뷰) — 기록 탭이 두 성격을 함께 담으므로 OR 이고,
  //                     섹션별 실제 조회는 각 API 의 권한이 집행한다.
  // ⚠ `can()` 은 display-permissive 라 **판정에 쓰지 않는다** — 실제 스코프 집행은
  //   백엔드(`require_permission` · `_task_scope_clause`)가 한다.
  const visible = [];
  if (can("console.aiops.read")) visible.push("ops", "tasks", "tools");
  if (can("console.usage.read") || can("console.reasoning.read")) visible.push("archive");
  bindPaneSubtabs(pane, "ai", (key) => {
    if (key === "ops" && !adminState.aiOps.initialized) {
      adminState.aiOps.initialized = true; loadAiOps();
    } else if (key === "tasks" && !(adminState.bridgeTasks && adminState.bridgeTasks.initialized)) {
      adminState.bridgeTasks = { initialized: true }; loadBridgeTasks();
    } else if (key === "tools" && !(adminState.toolUsage && adminState.toolUsage.initialized)) {
      adminState.toolUsage = { initialized: true }; loadToolUsage();
    } else if (key === "archive") {
      bindArchiveSections();
    }
  }, { visibleKeys: visible });
}

/**
 * '기록' 탭의 세 섹션을 **펼칠 때** 조회한다 (TASK-20260901T110000).
 *
 * 진입과 동시에 셋을 다 부르면 이 탭이 콘솔에서 가장 무거워진다 — 그런데 전환 이전
 * 기록이라 자주 열리지 않는다. 비용을 실제 열람에만 붙인다.
 *
 * 각 섹션의 권한이 다르므로 **보유하지 않은 섹션은 숨긴다**(열어 봐야 403 인 자리를
 * 남기면 사용자는 그것을 고장으로 읽는다).
 */
function bindArchiveSections() {
  const sections = [
    ["archiveActivitySection", "console.usage.read", () => loadArchiveServerActivity()],
    ["archiveUsageSection", "console.usage.read", () => {
      if (adminState.usage.initialized) return;
      adminState.usage.initialized = true; loadUsage();
    }],
    ["archiveReasoningSection", "console.reasoning.read", () => {
      if (adminState.reasoning && adminState.reasoning.initialized) return;
      adminState.reasoning = { initialized: true, redteamCursor: null }; loadReasoning();
    }],
  ];
  sections.forEach(([id, perm, load]) => {
    const el = $(id);
    if (!el) return;
    if (!can(perm)) { el.style.display = "none"; return; }
    if (el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    // `toggle` 은 열림/닫힘 양쪽에 온다 — 닫을 때 재조회하지 않도록 `open` 을 본다.
    el.addEventListener("toggle", () => { if (el.open) load(); });
  });
}

export function switchTab(tabName) {
  // feature-0021 console-subtabs(2026-07-16): 레거시 최상위 탭 키(usage/ai-ops/reasoning)는
  // 'AI 운영 현황'(ai-console) 단일 탭 + 서브탭으로 통합됨. 대시보드 위젯 deep-link("열기 →")
  // 등 서버가 옛 키(tab:"usage"/"ai-ops")를 보내는 경로가 남아 있어, 여기서 통합 탭으로 매핑하고
  // 대응 서브탭을 활성화한다(빈 pane 착지 방지 — 적대검증 MAJOR#1).
  if (_AI_SUBTAB_ALIAS[tabName]) {
    const _sub = _AI_SUBTAB_ALIAS[tabName];
    tabName = "ai-console";
    // ai-console pane 활성화 후 서브탭 전환은 아래 초기화(initAiConsoleSubtabs) 뒤에 수행.
    adminState._pendingAiSubtab = _sub;
  }
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
  // feature-0021 console-subtabs(2026-07-16): LLM 사용량·운영 현황·추론을 'AI 운영 현황' 단일
  // 탭(ai-console) + 서브탭으로 통합. 첫 진입 시 서브탭 바인딩 + 권한 게이팅 + 기본 서브탭 로드.
  if (tabName === "ai-console") {
    if (!adminState.aiConsole) {
      adminState.aiConsole = { subtab: null };
      initAiConsoleSubtabs();
    }
    // deep-link 로 특정 서브탭 지정 시(대시보드 위젯) 해당 서브탭으로 전환(권한 게이팅 반영).
    if (adminState._pendingAiSubtab) {
      activateAiConsoleSubtab(adminState._pendingAiSubtab);
      adminState._pendingAiSubtab = null;
    }
  }
  // TASK-0095: 설정 tab 첫 진입 시 sub-section 마운트.
  if (tabName === "settings" && !adminState.settings.initialized) {
    adminState.settings.initialized = true;
    mountSettingsSections();
  }
  // feature-0043 TASK-20260831T100000 — 미적용 배지·사유 dropdown·최하단 집계.
  //
  // `initialized` 분기 **밖**에서 매 진입마다 부른다: 패널 본문은 지연 마운트되는 것이
  // 있어(런타임/예산/red-team) 첫 진입 시점엔 배지를 붙일 자리가 아직 없을 수 있다.
  // 함수가 멱등이므로 반복 호출이 중복을 만들지 않는다.
  if (tabName === "settings") applyLlmInactiveMarks();
  // TASK-0205: 데이터소스 관리 tab 진입 시 렌더.
  if (tabName === "datasources") {
    renderDatasourcesPane();
  }
  // TASK-0273: 보관 대화 tab 첫 진입 시 로드.
  if (tabName === "archives" && !adminState.archivesInitialized) {
    adminState.archivesInitialized = true;
    loadArchivedConversations();
  }
  // 샘플 검수는 메타데이터 > 샘플쿼리 > 샘플 검수 큐 2차 보기로 통합됨(독립 탭 제거) — 별도 진입 훅 없음.
  // TASK-20260624-item11-metadata-glossary-enum: 메타데이터 tab 첫 진입 시 scope 드롭다운+목록 초기화.
  if (tabName === "metadata") {
    if (!adminState.metadataInitialized) {
      adminState.metadataInitialized = true;
      initMetadataTab();
    } else {
      // 재진입: 제품 카탈로그가 비어 있었을 수 있으니 스코프 드롭다운 재채움(선택 보존).
      _metaPopulateProductScopeSelect();
      // 로드된 스코프와 현재 선택이 갈리면 목록 재로드(값↔목록 불일치 방지).
      if ((adminState.metadata.loadedScope || "common") !== (adminState.metadata.productScope || "common")) loadMetadata();
      _metaApplySubtabPermissions();
      _metaSyncViews();        // 재진입 시 용어사전 2차 보기 strip 가시성·active 재동기화(권한 변동 방어).
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
// 샘플 검수 큐는 메타데이터 > 샘플쿼리 > '샘플 검수 큐' 2차 보기로 통합됨(구 독립 '샘플 검수' 탭 제거).
//   loadSampleReview()/renderSampleReview() 가 #metadataList/#metadataCount 를 타깃한다.
adminState.sampleReview = { items: [], loading: false, truncated: false };

function _sfEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function _sfFmtDt(s) {
  if (!s) return "—";
  try { const d = new Date(s); return isNaN(d.getTime()) ? String(s) : d.toLocaleString(); } catch (_) { return String(s); }
}

export async function loadSampleReview() {
  const listEl = document.getElementById("metadataList");
  if (!listEl) return;
  adminState.sampleReview.loading = true;
  listEl.replaceChildren();
  listEl.appendChild(_metaLoadingSkeleton());
  try {
    const sp = _metaReviewScopeParam();   // Issue 1: 선택 datasource 로 샘플 검수 큐 필터('공용'=전체).
    const url = sp ? `/api/admin/sample-feedback?scope_key=${sp}` : "/api/admin/sample-feedback";
    const data = await apiFetch(url);
    adminState.sampleReview.items = (data && data.items) || [];
    adminState.sampleReview.truncated = Boolean(data && data.truncated);
  } catch (err) {
    adminState.sampleReview.items = [];
    listEl.replaceChildren();
    const e = document.createElement("div");
    e.className = "admin-list-empty";
    e.textContent = (err && err.message) || "샘플 피드백 조회 실패";
    listEl.appendChild(e);
    return;
  } finally {
    adminState.sampleReview.loading = false;
  }
  renderSampleReview();
}

// XSS: 모든 사용자/LLM 유래 텍스트는 createElement + textContent 로만(innerHTML 미사용). SQL 은 pre>code.textContent.
function renderSampleReview() {
  const listEl = document.getElementById("metadataList");
  const countEl = document.getElementById("metadataCount");
  if (!listEl) return;
  _metaClearReviewDetail();   // ux2 #2: 큐 (재)렌더 시 우측 상세를 empty 로 초기화(stale 선택 방지).
  const st = adminState.sampleReview;
  const items = st.items || [];
  if (countEl) countEl.textContent = `${items.length}건${st.truncated ? "+" : ""} 검수 대기`;
  const kpiEl = document.getElementById("metadataKpi");
  if (kpiEl) { kpiEl.textContent = ""; kpiEl.style.display = "none"; }   // L5: 검수 큐 보기엔 KPI 무의미 — 비우고 숨김(stale/빈 gap 방지).
  const canCurate = can("kb.sample.curate");
  listEl.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = "검수 대기 중인 샘플 피드백이 없습니다.";
    listEl.appendChild(empty);
    // 배지 반영(0건).
    adminState.metadata.reviewPending.samples = 0;
    _metaRefreshReviewBadge("samples");
    return;
  }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "admin-sf-row";
    row.dataset.sfRow = String(it.id);
    // ux2 #2: 행 클릭 → 우측 read-only 상세(승인/거부 버튼은 stopPropagation 로 행-선택 미발화).
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    const _openSf = () => {
      adminState.metadata.reviewSelected = { kind: "sample", item: it };
      _metaRenderReviewDetail("sample", it);
      _metaMarkReviewActive(listEl, row);
    };
    row.addEventListener("click", _openSf);
    row.addEventListener("keydown", (e) => {
      if (e.target !== e.currentTarget) return;   // 내부 버튼 키 입력 무시(이중 발화 방지).
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); _openSf(); }
    });
    const head = document.createElement("div");
    head.className = "admin-sf-row-head";
    const vote = document.createElement("span");
    vote.className = "sf-vote " + (it.vote === "down" ? "sf-vote-down" : "sf-vote-up");
    vote.title = it.vote === "down" ? "부정 피드백(비추천)" : "긍정 피드백(추천)";
    // L8: 이모지(👍/👎) 제거 — 텍스트 태그(추천=승급 가능 / 비추천=승급 불가)로 의미 명시.
    vote.textContent = it.vote === "down" ? "비추천" : "추천";
    head.appendChild(vote);
    const scope = document.createElement("span");
    scope.className = "admin-sf-scope";
    scope.title = "데이터소스 스코프";
    scope.textContent = _metaDatasourceLabelOf(it.scope_key);
    head.appendChild(scope);
    if (it.suggested) {
      const sug = document.createElement("span");
      sug.className = "sf-badge-suggested";
      sug.textContent = "샘플 등록 요청";
      head.appendChild(sug);
    }
    const ts = document.createElement("span");
    ts.className = "admin-sf-ts";
    // Finding 3: glossary/ENUM 큐와 동일 "등록 <시각>" 라벨·포맷(_metaFmtDt)으로 통일.
    ts.textContent = it.created_at ? `등록 ${_metaFmtDt(it.created_at)}` : "";
    head.appendChild(ts);
    row.appendChild(head);
    const q = document.createElement("div");
    q.className = "admin-sf-q";
    q.textContent = it.nl_question || "";
    row.appendChild(q);
    const sql = (it.generated_sql || "").trim();
    if (sql && _metaIsMermaid(sql)) {
      // ux2 #4: 다이어그램은 행에 원문 덤프 대신 안내(상세에서 렌더). 밀집한 mermaid 텍스트 노출 금지.
      const note = document.createElement("div");
      note.className = "admin-sf-diagram-note muted";
      note.textContent = "다이어그램 (클릭해 상세 보기)";
      row.appendChild(note);
    } else if (sql) {
      const pre = document.createElement("pre");
      pre.className = "admin-sf-sql";
      const code = document.createElement("code");
      code.textContent = sql;   // SQL preview: textContent 로만.
      pre.appendChild(code);
      row.appendChild(pre);
    } else {
      const nos = document.createElement("div");
      nos.className = "admin-sf-nosql muted";
      nos.textContent = "생성 SQL 없음";
      row.appendChild(nos);
    }
    if (canCurate) {
      const actions = document.createElement("div");
      actions.className = "admin-sf-actions";
      // 👎 는 승급 불가(코어 promote_feedback 이 down 을 거부) → 승인 버튼 미노출, 거부만.
      if (it.vote !== "down") {
        const ap = document.createElement("button");
        ap.type = "button";
        ap.className = "btn-primary sf-approve";
        ap.dataset.sfId = String(it.id);
        ap.textContent = "승인(KB 등록)";
        ap.addEventListener("click", (e) => { e.stopPropagation(); _sampleFeedbackAction(ap, "approve"); });
        actions.appendChild(ap);
      }
      const rj = document.createElement("button");
      rj.type = "button";
      rj.className = "btn-secondary sf-reject";
      rj.dataset.sfId = String(it.id);
      rj.textContent = "거부";
      rj.addEventListener("click", (e) => { e.stopPropagation(); _sampleFeedbackAction(rj, "reject"); });
      actions.appendChild(rj);
      row.appendChild(actions);
    }
    listEl.appendChild(row);
  }
  // 배지 반영.
  adminState.metadata.reviewPending.samples = items.length;
  _metaRefreshReviewBadge("samples");
}

export async function _sampleFeedbackAction(btn, action) {
  const id = btn.dataset.sfId;
  if (!id) return;
  if (action === "reject" && !window.confirm("이 피드백을 거부합니다. (sample_queries 에 반영되지 않습니다)")) return;
  const row = document.querySelector(`[data-sf-row="${id}"]`);
  if (row) row.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  try {
    await apiFetch(`/api/admin/sample-feedback/${encodeURIComponent(id)}/${action}`, { method: "POST", body: "{}" });
    // 처리된 항목 제거 + 재렌더(낙관적 제거 후 목록·배지 정합).
    adminState.sampleReview.items = adminState.sampleReview.items.filter((it) => String(it.id) !== String(id));
    renderSampleReview();
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
  // 2차 보기(IA: 메타데이터 > {용어사전|ENUM|샘플쿼리} > {목록 | 검토·검수 큐}) — 서브탭별 보기 상태(list | review).
  viewBySub: { glossary: "list", enums: "list", samples: "list" },
  reviewPending: { glossary: 0, enums: 0, samples: 0 },   // 검토 큐 pending 건수(보기 strip 배지 소스).
  // metadata-product-scope: 메타데이터 pane 의 스코프 축 = **제품**(`product.<ProductKey>`) 또는 'common'.
  //   사용자·메타데이터 관리자는 데이터소스를 인식하지 않는다(그 축은 그래프 pane 전용으로 남는다).
  productScope: "common",
  productScopes: [],    // GET /api/admin/metadata/scopes 캐시 [{scope_key,name,product_key,database_count,is_common}]
  // 그래프 pane(지식베이스 형제 탭) 전용 datasource 스코프 — 본 재구성 범위 밖(축 분리 유지).
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
  // ux2 #2: 검토·검수 큐에서 선택된 후보(우측 read-only 상세). { kind:"glossary"|"enum"|"sample", item } 또는 null.
  reviewSelected: null,
  relationsOpenId: null,   // 유사어 패널이 펼쳐진 용어 id(목록에서 1개만)
  // Phase 2 부트스트랩 상태(테이블/컬럼 서브뷰 전용).
  bootstrap: {
    open: false,
    // metadata-product-scope: 부트스트랩 대상은 제품 스코프에서 상속(물리 datasource 는 서버가 해소).
    scopeKey: "",
    schema: "",
    schemas: [],
    tables: [],         // {schema_name, table_name, columns:[{column_name, data_type}]}
    loading: false,
    saving: false,
    page: 0,            // metadata-bs-paging: 현재 페이지(0-base). 페이징은 "가시성 윈도우"라
                        //   모든 블록은 DOM 유지(저장·AI 일괄은 전체 DOM 수집) — display 토글만.
  },
};

// feature-0038 Cycle 6: 메타데이터 콘솔 (initMetadataTab/loadMetadata 외) 은 admin/metadata.js 로 분리 (구 L2742–5591).

// feature-0038 Cycle 5: 데이터소스 pane (renderDatasourcesPane 외) 은 admin/datasources.js 로 분리 (구 L5591–6368).

/* ── Settings pane (TASK-0096 v2: 계정/역할/제품 과 동일한 list-detail 패턴) ─
 * 새 항목 추가 절차:
 *   1) admin.html 의 #settingsList 에 <button class="admin-list-row admin-list-row--nav"
 *      data-settings-tab="X" data-settings-group="..." data-settings-keywords="..."> 추가
 *   2) #settingsDetail 에 <article class="admin-settings-panel" data-settings-panel="X"> 추가
 *   3) SETTINGS_PANEL_MOUNTERS 에 X 키로 마운트 함수 등록
 * 마운트 함수는 panel 이 처음 활성화될 때 1회 실행. 권한 게이트는 함수 내부에서. */

adminState.settings = {
  initialized: false,
  activeTab: "prompts",
  mountedPanels: new Set(),
};

// feature-0038 Cycle 3: 설정 pane (mountSettingsSections·런타임/예산 패널 외) 은 admin/settings.js 로 분리 (구 L6374–7235).

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

// feature-0038 Cycle 3: 감사 로그 pane (loadAuditList 외) 은 admin/audit.js 로 분리 (구 L7257–7635).

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

// feature-0038 Cycle 4: 계정 pane (renderAccountList/Detail 외) 은 admin/accounts.js 로 분리 (구 L7044–7813).

// feature-0038 Cycle 4: 역할 pane (renderRoleList/Detail 외) 은 admin/roles.js 로 분리 (구 L7815–8409).

/* ── Pending UI refresh ──────────────────────────────────────────────── */

export function refreshPendingUI() {
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
  let rsTimeoutDirty = false, rsModelDirty = false, rsPerfDirty = false, rsExtToolDirty = false;
  rsPending.forEach((_v, k) => {
    const key = String(k);
    if (key.startsWith(RS_MODEL_PREFIX) || key.startsWith(RS_REASONING_PREFIX) || key.startsWith(RS_AGENT_MAX_PREFIX)) rsModelDirty = true;
    else if (RS_PERF_KEYS.has(key)) rsPerfDirty = true;  // feature-0025: 성능·병렬 서브탭으로 라우팅
    else if (RS_EXT_TOOL_KEYS.has(key)) rsExtToolDirty = true;  // feature-0041: 외부 AI 도구 서브탭
    else rsTimeoutDirty = true;
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
  markSettingsNav("performance-parallelism", rsPerfDirty);
  markSettingsNav("ext-tool-limits", rsExtToolDirty);
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
        ? draft.filter((d) => !["rule", "ai"].includes(String((d && d.source) || "manual"))).map((d) => ({ ...d }))
        : [] };   // §59: 'ai'(승인된 AI 제안)도 rule 처럼 수동 body 에서 제외 — 백엔드가 보존/정리
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

export async function loadAdminData() {
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

// feature-0038 Cycle 5: 제품 pane (renderProductList/Detail 외) 은 admin/products.js 로 분리 (구 L7616–9660).

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

export function buildRoleProductCardList(role, disabled, opts = {}) {
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
export function buildAccountProductOverrideList(account, disabled, opts = {}) {
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

export function buildSystemPromptEditor({ scope, productId = null, roleId = null, accountId = null, title, hint, fixedProductId = null, autoGenerateProductId = null, autoGenerateRoleId = null }) {
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
    // feature-0043 TASK-20260831T100000 — 자동작성은 서버 계정 AI 를 쓰던 경로다.
    //
    // ⚠ `finish()`(스트림 종료 핸들러)가 `autoBtn.textContent = "자동 작성"` 으로 **원문을
    //   복원**하므로, 위임 문구는 그 복원과 충돌한다. 그래서 여기서는 문구를 바꾸지 않고
    //   (`delegatedText` 미지정) 활성/비활성과 툴팁만 다룬다 — 두 곳이 같은 속성을 두고
    //   싸우면 마지막에 실행된 쪽이 이기고, 그 순서는 사용자 조작에 따라 달라진다.
    gateLlmControl(autoBtn, { label: "시스템 프롬프트 자동작성",
                             jobKind: "prompt_generate" });
    renderLlmNotice(section, { label: "프롬프트 자동작성", jobKind: "prompt_generate" });
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
  // feature-0043 TASK-20260831T100000 — 콘솔 LLM 상태. 같은 응답에 실려 오므로 추가 왕복이
  // 없고, 무엇보다 **권한과 상태가 같은 순간의 사실**이 된다(따로 물으면 그 사이 러너가
  // 죽어 한 화면 안에서 서로 다른 답이 그려진다).
  adminState.llm = me.llm || null;

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
  // feature-0021: AI 추론 새로고침
  const reasoningRefreshBtn = $("reasoningRefreshBtn");
  if (reasoningRefreshBtn && !reasoningRefreshBtn.dataset.bound) {
    reasoningRefreshBtn.dataset.bound = "1";
    reasoningRefreshBtn.addEventListener("click", () => loadReasoning());
  }
  // 샘플 검수는 메타데이터 > 샘플쿼리 > 샘플 검수 큐 2차 보기로 통합됨(독립 탭·새로고침 버튼 제거).
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
      if (!can("product.create")) {
        showToast("권한 없음(product.create)", true);
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

