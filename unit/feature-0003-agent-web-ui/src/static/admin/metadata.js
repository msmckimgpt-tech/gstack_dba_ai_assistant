// feature-0038 Cycle 6 — 메타데이터 거버넌스 콘솔 (관리 콘솔 > 지식베이스 > 메타데이터:
//   용어사전/ENUM/테이블/컬럼/샘플쿼리 5서브뷰 + 검토·검수 큐 + 유사어 관계 + 부트스트랩 UI).
//   admin.js 구 L2742–5591 에서 byte-동치 이동 (본문 무수정 — ITEM-P5b, 최대 단일 블록).
//   배너 주석·상태 초기화(adminState.metadata=…)와 소형 sampleReview 블록(초기화 동반)은
//   admin.js 잔류 (§2.1 착수 시 심볼 재실측 조항). _metaPopulateScopeSelect 는 본 모듈이
//   export 하고 admin.js 가 re-export (usage.js 의 "../admin.js" import 계약 보존).
import {
  adminState, apiFetch, can, showToast, $, formatDateTime,
  loadSampleReview, _sampleFeedbackAction,
  gateLlmControl, renderLlmNotice,
} from "../admin.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

// 서브뷰별 권한 — 서브탭/버튼 표시 게이트(실제 거부는 서버 403). graph-panel-perms(task4): 기능별 세부 권한으로 분리.
const _METADATA_SUBTAB_PERM = {
  // perm-atomic-split(2026-07-15): 서브탭 진입(가시성) 게이트 = 조회(read) 원자 단위 —
  //   레거시 묶음(manage)은 함의+backfill 로 read 를 보유하므로 무손실. samples 는 검수 단일 단위.
  glossary: "metadata.glossary.read",
  enums: "metadata.enum.read",
  tables: "metadata.table.read",
  columns: "metadata.column.read",
  samples: "kb.sample.curate",
};

// perm-atomic-split: 서브탭별 추가/수정/삭제 원자 게이트 — 백엔드 엔드포인트 enforcement 와 1:1.
const _METADATA_SUBTAB_CREATE_PERM = {
  glossary: "metadata.glossary.create",
  enums: "metadata.enum.create",
  tables: "metadata.table.create",
  columns: "metadata.column.create",
  samples: "kb.sample.curate",
};
const _METADATA_SUBTAB_UPDATE_PERM = {
  glossary: "metadata.glossary.update",
  enums: "metadata.enum.update",
  tables: "metadata.table.update",
  columns: "metadata.column.update",
  samples: "kb.sample.curate",
};
const _METADATA_SUBTAB_DELETE_PERM = {
  glossary: "metadata.glossary.delete",
  enums: "metadata.enum.delete",
  tables: "metadata.table.delete",
  columns: "metadata.column.delete",
  samples: "kb.sample.curate",
};

// 2차 보기(목록 | 검토·검수 큐)를 갖는 서브탭 설정 — 서브탭 파라미터화(용어사전에 하드코딩됐던 것을 일반화).
//   IA: 메타데이터 > {용어사전|ENUM|샘플쿼리} > {목록 보기 | 검토·검수 큐 보기}.
//   listPerm=목록 CRUD 권한, reviewPerm=검토 큐 큐레이션 권한, kind=검토 큐 렌더/엔드포인트 분기 키,
//   endpoint=검토 큐 REST 베이스. 이 객체의 key 인 서브탭만 "검토 보기"를 갖는다(_metaHasReview).
const _METADATA_REVIEW = {
  glossary: { listLabel: "용어 목록",    listPerm: "metadata.glossary.manage", reviewLabel: "용어 검토 큐", reviewPerm: "kb.glossary.curate", kind: "glossary", endpoint: "/api/admin/metadata/glossary-feedback" },
  enums:    { listLabel: "ENUM 목록",    listPerm: "metadata.enum.manage",     reviewLabel: "ENUM 검토 큐", reviewPerm: "kb.enum.curate",     kind: "enum",     endpoint: "/api/admin/metadata/enum-feedback" },
  samples:  { listLabel: "샘플쿼리 목록", listPerm: "kb.sample.curate",          reviewLabel: "샘플 검수 큐", reviewPerm: "kb.sample.curate",   kind: "sample",   endpoint: "/api/admin/sample-feedback" },
};

// 현재 서브탭의 2차 보기(없으면 list). viewBySub 는 review 서브탭만 key 를 가지므로 || "list" 로 폴백.
function _metaCurrentView() {
  return adminState.metadata.viewBySub[adminState.metadata.subTab] || "list";
}
// 서브탭이 2차 검토 보기를 갖는가(= _METADATA_REVIEW 의 key 인가).
function _metaHasReview(sub) {
  return Object.prototype.hasOwnProperty.call(_METADATA_REVIEW, sub);
}
// 검토·검수 큐 보기 활성 여부(모든 review 서브탭 공통 — 용어사전 전용 판정을 일반화).
function _metaIsReview() {
  return _metaHasReview(adminState.metadata.subTab) && _metaCurrentView() === "review";
}

// 서브탭 표시 게이트 — 검토 보기를 갖는 서브탭은 목록 권한 또는 검토 권한 중 하나라도 있으면 표시
// (검토 큐를 서브탭 하위로 중첩했으므로 curate-only 사용자의 접근 보존). 나머지는 서브탭 권한 그대로.
function _metaSubtabVisible(sub) {
  if (_metaHasReview(sub)) {
    const cfg = _METADATA_REVIEW[sub];
    return can(cfg.listPerm) || can(cfg.reviewPerm);
  }
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

// XSS — 사용자 데이터는 textContent 로만. (innerHTML 절대 미사용 경로.) 샘플 검수 _sfEsc 와 동일 규약.
function _metaEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function _metaFmtDt(v) {
  if (!v) return "";
  try { return formatDateTime(v); } catch (e) { return String(v); }
}

// B2: 로딩 스켈레톤(회색 3바) — 밋밋한 "로딩 중…" 대체. DOM 전용.
function _metaLoadingSkeleton() {
  const box = document.createElement("div");
  box.className = "admin-meta-skeleton";
  box.setAttribute("aria-label", "로딩 중");
  for (let i = 0; i < 3; i++) {
    const bar = document.createElement("div");
    bar.className = "admin-meta-skel-bar";
    box.appendChild(bar);
  }
  return box;
}

// B2: 리치 빈 상태 — 강한 안내(strong) + 옵션 힌트(muted). 모두 textContent(XSS 안전).
function _metaEmptyState(strongMsg, hintMsg) {
  const box = document.createElement("div");
  box.className = "admin-list-empty admin-meta-empty";
  const s = document.createElement("strong");
  s.className = "admin-meta-empty-title";
  s.textContent = strongMsg || "";
  box.appendChild(s);
  if (hintMsg) {
    const h = document.createElement("span");
    h.className = "admin-meta-empty-hint";
    h.textContent = hintMsg;
    box.appendChild(h);
  }
  return box;
}

// B5: table.column 경로 + code 를 별도 span + CSS 구분자(.admin-meta-sep)로 append(하드코딩 middot 제거).
function _metaAppendPathCode(el, loc, code) {
  const a = document.createElement("span");
  a.className = "admin-meta-path";
  a.textContent = loc || "";
  el.appendChild(a);
  if (code != null && String(code) !== "") {
    const sep = document.createElement("span");
    sep.className = "admin-meta-sep";
    sep.setAttribute("aria-hidden", "true");
    el.appendChild(sep);
    const c = document.createElement("span");
    c.className = "admin-meta-code";
    c.textContent = String(code);
    el.appendChild(c);
  }
}

// ── ux2 #4: 샘플 검수 generated_sql — mermaid 다이어그램 vs SQL 분기 렌더 ─────────────
// mermaid 판정: 선두 키워드 매치 OR 첫 비어있지 않은 라인이 ```mermaid 펜스.
function _metaIsMermaid(text) {
  const t = String(text == null ? "" : text).trim();
  if (!t) return false;
  const firstLine = (t.split(/\r?\n/).find((l) => l.trim() !== "") || "").trim();
  if (/^```mermaid/i.test(firstLine)) return true;
  return /^\s*(mermaid\b|erDiagram|graph\s|flowchart\s|sequenceDiagram|classDiagram|stateDiagram|gantt|pie\b|journey)/i.test(t);
}

// container 에 generated_sql 을 렌더한다. mermaid 면 다이어그램(공용 sanitized 헬퍼 mermaid-render.js),
// 아니면 SQL 코드블록. 빈 값이면 "생성 SQL 없음". 모든 소스 텍스트는 textContent 로만 주입(XSS 안전) —
// mermaid SVG 는 헬퍼가 securityLevel:'strict' 로 자체 sanitize 한다(exception #4).
function _metaRenderSqlOrDiagram(container, text) {
  if (!container) return;
  const trimmed = String(text == null ? "" : text).trim();
  if (!trimmed) {
    const nos = document.createElement("div");
    nos.className = "admin-sf-nosql muted";
    nos.textContent = "생성 SQL 없음";
    container.appendChild(nos);
    return;
  }
  if (_metaIsMermaid(trimmed)) {
    // 다이어그램 소스 추출: 선두 ```mermaid 펜스 및/또는 bare 'mermaid' 라인 제거.
    let src = trimmed;
    if (/^```mermaid/i.test(src)) {
      src = src.replace(/^```mermaid[^\n]*\n?/i, "").replace(/\n?```\s*$/i, "");
    } else if (/^\s*mermaid\b/i.test(src)) {
      // bare leading 'mermaid' 라인만 제거(erDiagram/graph 등 실 키워드는 보존).
      src = src.replace(/^\s*mermaid[^\S\r\n]*\r?\n?/i, "");
    }
    src = src.trim();
    // 공용 렌더 헬퍼가 소비하는 형식(.mermaid-pending) 으로 삽입 — 헬퍼는 render 실패/미로딩 시에도
    // 자체 graceful fallback(원본 코드블록) 을 수행한다. 헬퍼 함수 자체가 없으면 라벨 붙인 코드블록으로 폴백.
    if (typeof renderMermaidDiagrams === "function") {
      const div = document.createElement("div");
      div.className = "mermaid-block mermaid-pending";
      div.textContent = src;   // 소스 텍스트만(SVG 아님).
      container.appendChild(div);
      if (typeof ensureMermaidInit === "function") { try { ensureMermaidInit(); } catch (_) {} }
      try { renderMermaidDiagrams(container); } catch (_) {}
    } else {
      const lbl = document.createElement("div");
      lbl.className = "drawer-label";
      lbl.textContent = "다이어그램";
      const pre = document.createElement("pre");
      pre.className = "admin-sf-sql";
      const code = document.createElement("code");
      code.className = "language-mermaid";
      code.textContent = src;
      pre.appendChild(code);
      container.appendChild(lbl);
      container.appendChild(pre);
    }
    return;
  }
  // SQL 코드블록.
  const pre = document.createElement("pre");
  pre.className = "admin-sf-sql";
  const code = document.createElement("code");
  code.textContent = trimmed;   // SQL: textContent 로만.
  pre.appendChild(code);
  container.appendChild(pre);
}

// ── ux2 #2: 검토·검수 큐 후보 read-only 상세(우측 #metadataDetail) ───────────────────
// kind: "glossary" | "enum" | "sample". 폼/부트스트랩/empty 안내를 숨기고 #metadataReviewDetail 만 노출.
// 액션(승급/거부/승인)은 목록 행 액션과 동일 핸들러를 호출 → 처리 후 큐 리로드가 상세를 empty 로 되돌린다.
// 모든 사용자/LLM 데이터는 textContent / 렌더 헬퍼로만 주입(XSS 안전).
function _metaRenderReviewDetail(kind, it) {
  const box = document.getElementById("metadataReviewDetail");
  if (!box || !it) return;
  const empty = document.getElementById("metadataDetailEmpty");
  const form = document.getElementById("metadataForm");
  const boot = document.getElementById("metadataBootstrap");
  if (empty) empty.style.display = "none";
  if (form) form.style.display = "none";
  if (boot) boot.style.display = "none";
  box.style.display = "";
  box.replaceChildren();

  const mkTag = (t, cls) => {
    const s = document.createElement("span");
    s.className = "admin-meta-tag" + (cls ? " " + cls : "");
    s.textContent = t;
    return s;
  };

  // 제목.
  const title = document.createElement("h3");
  title.className = "admin-meta-review-title";
  if (kind === "enum") {
    const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
    _metaAppendPathCode(title, loc, it.code);
  } else if (kind === "sample") {
    title.textContent = it.nl_question || "(질문 없음)";
  } else {
    title.textContent = it.term || "(용어 없음)";
  }
  box.appendChild(title);

  // 배지 행.
  const tags = document.createElement("div");
  tags.className = "admin-meta-review-tags";
  if (kind === "sample") {
    const vote = document.createElement("span");
    vote.className = "sf-vote " + (it.vote === "down" ? "sf-vote-down" : "sf-vote-up");
    vote.textContent = it.vote === "down" ? "비추천" : "추천";
    tags.appendChild(vote);
    if (it.scope_key != null) tags.appendChild(mkTag(`scope: ${_metaDatasourceLabelOf(it.scope_key)}`, "admin-meta-tag-neutral"));
    if (it.suggested) tags.appendChild(mkTag("샘플 등록 요청", "admin-meta-tag-info"));
    if (it.created_at) tags.appendChild(mkTag(`등록 ${_metaFmtDt(it.created_at)}`, "admin-meta-tag-neutral"));
  } else {
    if (it.confidence != null) tags.appendChild(mkTag(`신뢰도 ${Number(it.confidence).toFixed(2)}`, "admin-meta-tag-conf"));
    if (kind === "glossary") {
      const rk = String(it.role_key || "*");
      tags.appendChild(mkTag(rk === "*" ? "공용" : `역할: ${_metaRoleLabel(rk)}`, rk === "*" ? "admin-meta-tag-neutral" : "admin-meta-tag-role"));
    }
    if (it.scope_key) tags.appendChild(mkTag(`scope: ${_metaDatasourceLabelOf(it.scope_key)}`, "admin-meta-tag-neutral"));
    const st = String(it.status || "");
    const stLabel = { pending: "검토 대기", auto_promoted: "자동 등록됨", promoted: "승급됨", rejected: "거부됨" }[st] || st;
    if (stLabel) {
      const stCls = st === "promoted" ? "admin-meta-tag-ok" : st === "rejected" ? "admin-meta-tag-danger" : "admin-meta-tag-neutral";
      tags.appendChild(mkTag(stLabel, stCls));
    }
    // Issue 3: 등록 시각(created_at) — glossary/ENUM 후보 상세에도 언제 수집됐는지 표기(sample 은 위 분기에 이미 존재).
    if (it.created_at) tags.appendChild(mkTag(`등록 ${_metaFmtDt(it.created_at)}`, "admin-meta-tag-neutral"));
  }
  if (tags.childNodes.length) box.appendChild(tags);

  // 본문 섹션.
  const section = document.createElement("div");
  section.className = "admin-meta-review-section";
  const lbl = document.createElement("div");
  lbl.className = "drawer-label";
  lbl.textContent = kind === "enum" ? "라벨" : kind === "sample" ? "생성 SQL / 다이어그램" : "정의";
  section.appendChild(lbl);
  if (kind === "sample") {
    const body = document.createElement("div");
    body.className = "admin-meta-review-body admin-meta-review-sql";
    _metaRenderSqlOrDiagram(body, it.generated_sql);
    section.appendChild(body);
  } else {
    const body = document.createElement("div");
    body.className = "admin-meta-review-body";
    body.textContent = (kind === "enum" ? it.suggested_label : it.suggested_definition) || "";
    section.appendChild(body);
  }
  box.appendChild(section);

  // 액션 행 — 목록 행 액션 미러(같은 핸들러 → 성공 시 큐 리로드가 상세 초기화).
  const actions = document.createElement("div");
  actions.className = "admin-meta-review-actions";
  if (kind === "sample") {
    if (can("kb.sample.curate")) {
      if (it.vote !== "down") {
        const ap = document.createElement("button");
        ap.type = "button"; ap.className = "btn-primary"; ap.dataset.sfId = String(it.id);
        ap.textContent = "승인(KB 등록)";
        ap.addEventListener("click", (e) => { e.stopPropagation(); _sampleFeedbackAction(ap, "approve"); });
        actions.appendChild(ap);
      }
      const rj = document.createElement("button");
      rj.type = "button"; rj.className = "btn-secondary"; rj.dataset.sfId = String(it.id);
      rj.textContent = "거부";
      rj.addEventListener("click", (e) => { e.stopPropagation(); _sampleFeedbackAction(rj, "reject"); });
      actions.appendChild(rj);
    }
  } else {
    const reviewPerm = kind === "enum" ? "kb.enum.curate" : "kb.glossary.curate";
    const st = String(it.status || "");
    if (can(reviewPerm)) {
      if (st === "pending") {
        const pb = document.createElement("button");
        pb.type = "button"; pb.className = "btn-primary";
        pb.textContent = "승급";
        pb.addEventListener("click", () => _feedbackQueueAction(kind, it.id, "promote", pb));
        actions.appendChild(pb);
      }
      if (st === "pending" || st === "auto_promoted") {
        const rb = document.createElement("button");
        rb.type = "button"; rb.className = "btn-secondary";
        rb.textContent = st === "auto_promoted" ? "되돌리기" : "거부";
        rb.addEventListener("click", () => _feedbackQueueAction(kind, it.id, "reject", rb));
        actions.appendChild(rb);
      }
    }
  }
  if (actions.childNodes.length) box.appendChild(actions);
}

// 검토·검수 큐 우측 상세 초기화 — 선택 해제 + 상세 숨김 + (검토 보기면) empty 안내 복원. 큐 리로드/재렌더 시 호출.
function _metaClearReviewDetail() {
  adminState.metadata.reviewSelected = null;
  const box = document.getElementById("metadataReviewDetail");
  if (box) { box.style.display = "none"; box.replaceChildren(); }
  const empty = document.getElementById("metadataDetailEmpty");
  if (empty && _metaIsReview()) empty.style.display = "";
}

// 좌측 검토·검수 큐 행 선택 상태 표시 — 한 행만 .is-active(다른 행 해제).
function _metaMarkReviewActive(listEl, row) {
  if (!listEl) return;
  listEl.querySelectorAll(".admin-meta-row.is-active, .admin-sf-row.is-active").forEach((r) => r.classList.remove("is-active"));
  if (row) row.classList.add("is-active");
}

// B6: 인라인 필드 검증 — 필수 미입력 필드에 red border + 필드 하단 메시지. key 는 고정 필드키(사용자 데이터 아님).
function _metaSetFieldError(key, msg) {
  const wrap = document.getElementById("metadataFormFields");
  if (!wrap) return;
  const input = wrap.querySelector(`[name="${key}"]`);
  if (!input) return;
  const field = input.closest(".admin-meta-field");
  if (!field) return;
  field.classList.add("is-error");
  let em = field.querySelector(".admin-meta-field-error");
  if (!em) {
    em = document.createElement("span");
    em.className = "admin-meta-field-error";
    field.appendChild(em);
  }
  em.textContent = msg;
}
function _metaClearFieldErrors() {
  const wrap = document.getElementById("metadataFormFields");
  if (!wrap) return;
  wrap.querySelectorAll(".admin-meta-field.is-error").forEach((f) => f.classList.remove("is-error"));
  wrap.querySelectorAll(".admin-meta-field-error").forEach((e) => e.remove());
}

// 탭 첫 진입 — 제품 스코프 드롭다운 채우기 + 서브탭 권한 게이트 + 폼 바인딩 + 최초 목록 로드.
// metadata-product-scope: 목록/부트스트랩이 제품 축이므로 카탈로그 로드를 선행하고, 그 뒤 목록을 읽는다
// (카탈로그보다 목록이 먼저 나가면 첫 화면이 잘못된 스코프로 로드된다).
async function initMetadataTab() {
  _metaApplySubtabPermissions();
  _metaBindControls();
  _metaBindBootstrap();
  await _metaLoadProductScopes();
  _metaRenderDetail();   // metadata-list-detail: 초기 우측 상세 = empty-state + 목록 툴바 가시성.
  _metaPrimeReviewBadge();
  loadMetadata();
}

// 검토 큐 배지 선반영 — 탭 진입/재진입 시 큐레이션 권한이 있는 모든 review 서브탭의 pending 건수를
//   best-effort 로 가져와 reviewPending 에 저장하고, 그 서브탭이 현재면 보기 strip 배지를 갱신한다.
//   glossary/enum 은 ?status=pending + data.pending_count, sample 은 GET 목록 응답의 count/items 길이.
async function _metaPrimeReviewBadge() {
  const md = adminState.metadata;
  for (const sub of Object.keys(_METADATA_REVIEW)) {
    const cfg = _METADATA_REVIEW[sub];
    if (!can(cfg.reviewPerm)) continue;
    try {
      const sp = _metaReviewScopeParam();   // Finding 1: 배지도 선택 datasource 로 한정('공용'=전체) — 큐 리스트 카운트와 정합.
      if (cfg.kind === "sample") {
        const data = await apiFetch(sp ? `${cfg.endpoint}?scope_key=${sp}` : cfg.endpoint);
        md.reviewPending[sub] = (data && data.count != null) ? Number(data.count) : ((data && data.items) ? data.items.length : 0);
      } else {
        let u = `${cfg.endpoint}?status=pending`;
        if (sp) u += `&scope_key=${sp}`;
        const data = await apiFetch(u);
        md.reviewPending[sub] = (data && data.pending_count) || 0;
      }
      _metaRefreshReviewBadge(sub);
    } catch (_) { /* best-effort — 배지 없음 */ }
  }
}

// 검토 큐 pending 배지 갱신 — 대상 서브탭이 현재면 보기 strip 을 재동기화(배지 반영). 동적 strip 이라 재빌드.
function _metaRefreshReviewBadge(sub) {
  if (sub === adminState.metadata.subTab) _metaSyncViews();
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

// 2차 보기 strip 동기화(일반화) — review 서브탭에서만 노출. 보기 버튼(list/review)을 동적 생성하고
//   권한별로 게이트, review 버튼엔 pending 배지, 현재 보기가 권한 없으면 첫 표시 보기로 폴백한다.
//   버튼은 XSS 안전하게 createElement + textContent 로만 만든다(데이터 없음이지만 규약 일관).
function _metaSyncViews() {
  const strip = document.getElementById("metadataViews");
  if (!strip) return;
  const md = adminState.metadata;
  const sub = md.subTab;
  if (!_metaHasReview(sub)) {
    strip.style.display = "none";
    strip.replaceChildren();
    md.viewBySub[sub] = "list";   // 검토 보기 없는 서브탭은 항상 목록.
    return;
  }
  strip.style.display = "";
  const cfg = _METADATA_REVIEW[sub];
  const views = [
    { v: "list", label: cfg.listLabel, perm: cfg.listPerm },
    { v: "review", label: cfg.reviewLabel, perm: cfg.reviewPerm },
  ];
  const permitted = views.filter((x) => !x.perm || can(x.perm));
  let cur = md.viewBySub[sub] || "list";
  // 현재 보기 권한 없음 → 첫 표시 보기로 폴백(curate-only=검토 큐, list-only=목록).
  if (!permitted.some((x) => x.v === cur)) {
    cur = permitted.length ? permitted[0].v : "list";
    md.viewBySub[sub] = cur;
  }
  strip.replaceChildren();
  for (const x of views) {
    if (x.perm && !can(x.perm)) continue;
    const active = x.v === cur;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "admin-meta-view" + (active ? " is-active" : "");
    btn.dataset.metaView = x.v;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", active ? "true" : "false");
    const lbl = document.createElement("span");
    lbl.textContent = x.label;
    btn.appendChild(lbl);
    if (x.v === "review") {
      const n = Number(md.reviewPending[sub]) || 0;
      const badge = document.createElement("span");
      badge.className = "admin-meta-view-badge";
      if (n > 0) badge.textContent = String(n);
      else badge.hidden = true;
      btn.appendChild(badge);
    }
    btn.addEventListener("click", () => {
      const v = btn.dataset.metaView;
      if (!v || v === (md.viewBySub[sub] || "list")) return;
      md.viewBySub[sub] = v;
      md.editing = null;
      md.selectedId = null;
      md.reviewSelected = null;   // ux2 #2: 보기 전환 시 검토 상세 선택 해제.
      md.relationsOpenId = null;
      md.search = "";
      const sEl = document.getElementById("metadataSearch");
      if (sEl) sEl.value = "";
      md.detailMode = "empty";
      _metaRenderDetail();
      loadMetadata();
    });
    strip.appendChild(btn);
  }
}

// 그래프 pane 스코프 드롭다운: '공용(common)' + 등록된 datasource key 목록(adminState.datasources 재사용).
// metadata-product-scope: 메타데이터 pane 은 더 이상 이 축을 쓰지 않는다 — 제품 축(_metaPopulateProductScopeSelect).
// 그래프 뷰(지식베이스 형제 탭)는 물리 스키마 투영이라 datasource 축을 그대로 유지한다.
export function _metaPopulateScopeSelect() {
  const selGraph = document.getElementById("graphScopeSelect");
  if (!selGraph) return;
  const opts = [{ value: "common", label: "공용 (common)" }];
  for (const ds of (adminState.datasources || [])) {
    const label = String((ds && ds.key) || "").trim().toLowerCase();
    if (!label) continue;
    // scope-key-unify: option value = 백엔드가 준 scope_key(질의 시점 read 와 동일 해소값:
    // DB-등록 ds=엔드포인트 해시, .env 레거시=라벨). 표시는 사람이 읽는 라벨(key).
    const scope = String((ds && ds.scope_key) || label).trim().toLowerCase();
    opts.push({ value: scope, label: label });
  }
  const cur = adminState.metadata.scopeKey || "common";
  const resolved = opts.some((o) => o.value === cur) ? cur : "common";
  selGraph.replaceChildren();
  for (const o of opts) {
    const el = document.createElement("option");
    el.value = o.value;
    el.textContent = o.label;
    selGraph.appendChild(el);
  }
  selGraph.value = resolved;
  adminState.metadata.scopeKey = resolved;
}

// metadata-product-scope: 메타데이터 pane 스코프 드롭다운 = **제품** 목록 + 공용.
// 옵션 원천은 GET /api/admin/metadata/scopes (제품 SSOT). 실패 시 '공용' 단독으로 degrade —
// 데이터소스 목록으로 폴백하지 않는다(축이 섞이면 사용자가 다시 데이터소스를 마주하게 된다).
function _metaPopulateProductScopeSelect() {
  const sel = document.getElementById("metadataScopeSelect");
  if (!sel) return;
  const scopes = adminState.metadata.productScopes || [];
  const opts = scopes.length
    ? scopes.map((s) => ({ value: String(s.scope_key || ""), label: String(s.name || s.product_key || s.scope_key || "") }))
    : [{ value: "common", label: "공용 (모든 제품)" }];
  const cur = adminState.metadata.productScope || "common";
  const resolved = opts.some((o) => o.value === cur) ? cur : (opts[0] ? opts[0].value : "common");
  sel.replaceChildren();
  for (const o of opts) {
    const el = document.createElement("option");
    el.value = o.value;
    el.textContent = o.label;   // textContent 기반(XSS 안전)
    sel.appendChild(el);
  }
  sel.value = resolved;
  adminState.metadata.productScope = resolved;
}

// 제품 스코프 카탈로그 로드(1회 캐시). 목록/등록/부트스트랩이 모두 이 축을 쓰므로 탭 진입 시 선행한다.
async function _metaLoadProductScopes() {
  try {
    const data = await apiFetch("/api/admin/metadata/scopes");
    adminState.metadata.productScopes = (data && Array.isArray(data.scopes)) ? data.scopes : [];
  } catch (_) {
    adminState.metadata.productScopes = [];
  }
  _metaPopulateProductScopeSelect();
}

// 현재 선택된 제품 스코프의 카탈로그 엔트리(없으면 null — 'common' 포함).
function _metaCurrentProductEntry() {
  const cur = adminState.metadata.productScope || "common";
  if (cur === "common") return null;
  for (const s of (adminState.metadata.productScopes || [])) {
    if (String(s.scope_key || "") === cur) return s;
  }
  return null;
}

function _metaBindControls() {
  const sel = document.getElementById("metadataScopeSelect");
  if (sel && !sel.dataset.bound) {
    sel.dataset.bound = "1";
    sel.addEventListener("change", () => {
      adminState.metadata.productScope = sel.value || "common";   // metadata-product-scope: 제품 축
      adminState.metadata.editing = null;
      adminState.metadata.selectedId = null;
      adminState.metadata.reviewSelected = null;   // ux2 #2: 스코프 변경(큐 재조회) 시 검토 상세 선택 해제.
      // scope-single-ds-ui + metadata-list-detail: 스코프가 부트스트랩 DS 를 결정하므로 bootstrap 모드면
      // 유지하며 재동기화(공용=empty-state, 구체 DS=골격 컨트롤·상속 DS·스키마 재로드). form/empty 는 선택 무효 → empty.
      if (adminState.metadata.detailMode !== "bootstrap") adminState.metadata.detailMode = "empty";
      _metaRenderDetail();
      loadMetadata();
      _metaPrimeReviewBadge();   // Finding 2: 제품 변경 시 검토 배지도 새 scope 로 재산정(전 review 서브탭·list 보기 포함).
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
      adminState.metadata.reviewSelected = null;   // ux2 #2: 서브탭 전환 시 검토 상세 선택 해제.
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
  // 2차 보기 버튼(목록 / 검토·검수 큐)은 _metaSyncViews 가 동적 생성하며 click 을 그 안에서 바인딩한다.
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
      if (_metaIsReview()) return;   // 검토·검수 큐는 별도 렌더 경로(loadFeedbackQueue/loadSampleReview) — 검색 미적용.
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
  // feature-0043 TASK-20260831T100000 — **누르기 전에** 상태를 말한다.
  //
  // 종전에는 서버 계정 AI 가 차단된 뒤에도 버튼이 멀쩡히 보였고, 누르면 503 토스트가 떴다가
  // 몇 초 뒤 사라졌다 — 사용자에게 남는 것은 "왜 안 되지" 뿐이고, 그것을 고장으로 읽으면
  // 계속 재시도한다. 게이트는 `bound` 분기 **밖**에 둔다: 바인딩은 1회지만 상태 표시는
  // 폼이 다시 그려질 때마다 최신이어야 한다.
  gateLlmControl(suggestBtn, {
    label: "메타데이터 AI 자동완성",
    delegatedText: "AI 자동완성 (내 AI)",
    jobKind: "metadata_suggest",
  });
}

// metadata-product-scope: 프론트는 물리 datasource 를 다루지 않는다. tables/columns 골격·AI grounding
// 대상 연결은 서버가 (제품 스코프, 접근DB) 바인딩으로 해소한다(_scope_datasource_for_schema).
// 본 헬퍼는 "골격을 가져올 수 있는 스코프인가"(= 공용이 아닌 제품)만 판정한다.
function _metaScopeIsProduct() {
  const scope = adminState.metadata.productScope || "common";
  return scope !== "common";
}

// scope_key → 사람이 읽는 스코프 라벨(표시 전용). metadata-product-scope 이후 KB row 의 scope_key 는
// `product.<ProductKey>` 이므로 제품명으로 되돌린다.
//   - 빈 값/'common' → '공용'
//   - 제품 스코프 → 제품명(카탈로그 매칭)
//   - 미매칭(레거시 datasource 스코프 잔여 행·카탈로그 미로드) → 원문 유지(정보 손실보다 raw 표시가 안전).
function _metaDatasourceLabelOf(scopeKey) {
  const s = String(scopeKey == null ? "" : scopeKey).trim();
  if (!s || s.toLowerCase() === "common") return "공용";
  const low = s.toLowerCase();
  for (const sc of (adminState.metadata.productScopes || [])) {
    if (String(sc.scope_key || "").toLowerCase() === low) return String(sc.name || sc.product_key || s);
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
  // metadata-product-scope: scope_key = 제품 스코프. tables/columns grounding 의 물리 datasource 는
  // 서버가 scope_key + schema_name 으로 해소하므로 프론트가 datasource 를 실어보내지 않는다.
  const payload = { scope_key: adminState.metadata.productScope || "common" };
  for (const k of ["term", "schema_name", "table_name", "column_name", "code", "sql", "nl_question"]) {
    if (vals[k] != null && String(vals[k]).trim()) payload[k] = String(vals[k]).trim();
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
  _metaSyncViews();   // 용어사전 보기 유효성 먼저 보정(권한 없는 보기 → 첫 표시 보기)
  // 용어 검토 큐 보기는 CRUD 폼 없음. 생성 비활성 서브뷰 + 비편집 상태도 폼 숨김(목록 '수정'으로만 진입).
  const isReview = _metaIsReview();
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
    field.className = "admin-meta-field admin-meta-field-wide";   // B6: 역할 컨텍스트는 전폭.
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
    // B6: 긴 필드(textarea: 정의/설명/질문/SQL)는 전폭, 짧은 식별 필드는 2열 grid 셀.
    field.className = "admin-meta-field" + (f.type === "textarea" ? " admin-meta-field-wide" : "");
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
  if (submitBtn) {
    submitBtn.textContent = editing ? "수정 저장" : "등록";
    // perm-atomic-split: 저장 버튼은 액션별 원자 권한 보유 시에만 노출(서버 enforcement 와 정합).
    const _saveSub = adminState.metadata.subTab;
    const _savePerm = editing ? (_METADATA_SUBTAB_UPDATE_PERM[_saveSub] || "metadata.table.update")
                              : (_METADATA_SUBTAB_CREATE_PERM[_saveSub] || "metadata.table.create");
    submitBtn.style.display = can(_savePerm) ? "" : "none";
  }
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
  _metaSyncViews();   // 용어사전 2차 보기 strip 가시성/active (모드 무관 top-nav).
  let mode = md.detailMode || "empty";
  if (mode === "form") {
    if (_metaIsReview()) mode = "empty";                                  // 검토 큐는 CRUD 폼 없음.
    else if (_METADATA_NO_CREATE[md.subTab] && !(md.editing && md.editing.id != null)) mode = "empty";  // samples 생성 비활성.
  }
  // graph-panel-perms(task4): 스키마 골격 부트스트랩은 테이블 골격 도구 → metadata.table.manage 게이트(백엔드 동치).
  if (mode === "bootstrap" && !((md.subTab === "tables" || md.subTab === "columns") && can("metadata.table.create") && can("metadata.table.update"))) mode = "empty";
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
  // ux2 #2: 검토·검수 큐 보기 — 선택된 후보가 있으면 우측 read-only 상세(empty/폼 위로 override), 없으면 상세 숨김.
  const reviewBox = document.getElementById("metadataReviewDetail");
  if (reviewBox) {
    if (_metaIsReview() && md.reviewSelected && md.reviewSelected.item) {
      _metaRenderReviewDetail(md.reviewSelected.kind, md.reviewSelected.item);
    } else {
      reviewBox.style.display = "none";
      reviewBox.replaceChildren();
    }
  }
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
  const review = _metaIsReview();
  // 검토 큐는 별도 렌더(피드백 큐) — 클라이언트 검색 미적용이라 검색 입력 숨김.
  const searchEl = document.getElementById("metadataSearch");
  if (searchEl) searchEl.style.display = review ? "none" : "";
  const bsBtn = document.getElementById("metadataBootstrapOpenBtn");
  if (bsBtn) {
    const showBs = (md.subTab === "tables" || md.subTab === "columns") && can("metadata.table.create") && can("metadata.table.update") && !review;
    bsBtn.style.display = showBs ? "" : "none";
    bsBtn.classList.toggle("is-active", md.detailMode === "bootstrap");   // 진입 상태 시각 표시(토글).
  }
  const newBtn = document.getElementById("metadataNewBtn");
  if (newBtn) {
    const canCreate = !_METADATA_NO_CREATE[md.subTab] && !review && can(_METADATA_SUBTAB_CREATE_PERM[md.subTab] || "metadata.table.create");
    newBtn.style.display = canCreate ? "" : "none";
  }
}

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
  // 검토·검수 큐 보기는 별도 적재/렌더 경로(폼/CRUD 아님) — kind 별 로더로 분기.
  if (_metaIsReview()) {
    if (sub === "glossary") await loadFeedbackQueue("glossary");
    else if (sub === "enums") await loadFeedbackQueue("enum");
    else if (sub === "samples") await loadSampleReview();
    return;
  }
  const scope = adminState.metadata.productScope || "common";
  adminState.metadata.loadedScope = scope;   // 메타데이터 목록이 로드된 제품 스코프 기록(탭 재진입 diverge 재로드 판정).
  adminState.metadata.loading = true;
  listEl.replaceChildren();
  listEl.appendChild(_metaLoadingSkeleton());   // B2: 스켈레톤(회색 3바) 로딩 상태.
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
//   hangul-qwerty-search: `qv` 는 원문 + 반대 자판 변환본 후보 배열(호출부가 1회 생성).
function _metaItemMatchesSearch(it, sub, qv) {
  if (!qv || !qv.length) return true;
  let hay = "";
  if (sub === "glossary") hay = `${it.term || ""} ${it.definition || ""}`;
  else if (sub === "enums") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.column_name || ""} ${it.code || ""} ${it.label || ""}`;
  else if (sub === "tables") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.description || ""}`;
  else if (sub === "columns") hay = `${it.schema_name || ""} ${it.table_name || ""} ${it.column_name || ""} ${it.description || ""}`;
  else if (sub === "samples") hay = `${it.nl_question || ""} ${it.sql || ""} ${it.domain || ""}`;
  return matchesAnyVariant(hay.toLowerCase(), qv);
}

// L5: KPI 는 distinctive signal 만 표기 — bare total("총 N건")은 #metadataCount 와 중복이므로 금지.
//   tables/columns → 미기재 M(M>0 일 때만). enums(그룹 카드가 테이블별 개수 표기)·glossary·samples → 신호 없음 → 숨김.
function _metaUpdateKpi(items, sub) {
  const kpiEl = document.getElementById("metadataKpi");
  if (!kpiEl) return;
  let text = "";
  if (sub === "tables" || sub === "columns") {
    const missing = items.filter((it) => !String(it.description || "").trim()).length;
    if (missing > 0) text = `미기재 ${missing}`;
  }
  kpiEl.textContent = text;
  kpiEl.style.display = text ? "" : "none";   // 비어 있으면 요소 자체 숨김(빈 gap 방지).
}

// 한 항목 → .admin-meta-row 엘리먼트. grouped=true 면(enums/columns 그룹 카드 내부) 경로 반복 제거를 위해
//   제목을 code/컬럼명만 축약 표시한다. 행 클릭→편집, 삭제/유사어 인라인 액션은 flat/grouped 공통.
function _metaListRow(it, sub, canEdit, grouped) {
  const md = adminState.metadata;
  const row = document.createElement("div");
  row.className = "admin-meta-row";
  if (it.id != null) row.dataset.metaId = String(it.id);
  if (md.selectedId != null && String(it.id) === String(md.selectedId)) row.classList.add("is-active");
  if (canEdit) {
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    row.addEventListener("click", () => _metaStartEdit(it));
    row.addEventListener("keydown", (e) => {
      if (e.target !== e.currentTarget) return;   // 행 내부 버튼 키 입력 무시(이중 발화 방지).
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
    if (grouped) {
      title.textContent = it.code || "";   // 경로는 그룹 헤더에 있음 — 행은 code 만.
    } else {
      const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
      _metaAppendPathCode(title, loc, it.code);   // B5: table.column · code(구분자 span).
    }
    body.textContent = it.label || "";
  } else if (sub === "tables") {
    const loc = [it.schema_name, it.table_name].filter(Boolean).join(".");
    title.textContent = loc || (it.table_name || "");
    body.textContent = it.description || "";
  } else if (sub === "columns") {
    if (grouped) {
      title.textContent = it.column_name || "";   // 경로는 그룹 헤더에.
    } else {
      const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
      title.textContent = loc || (it.column_name || "");
    }
    body.textContent = it.description || "";
  } else if (sub === "samples") {
    title.textContent = it.nl_question || "";
    // B7: SQL 은 1~2줄 truncated preview 만(전체 SQL 은 우측 상세 폼). 행 내부 스크롤 박스 제거.
    body.textContent = it.sql || "";
    body.classList.add("admin-meta-sql-preview");
  }
  main.appendChild(title);
  main.appendChild(body);
  const mkTag = (text, cls) => {
    const t = document.createElement("span");
    t.className = "admin-meta-tag" + (cls ? " " + cls : "");
    t.textContent = text;
    return t;
  };
  // glossary 전용 — 역할/출처 배지. L7: 역할=blue(info 톤), provenance(자동등록/자동승급)=중립 회색
  //   (role 파랑·attention warn/danger 와 시각적으로 구분 — 경고로 오인 금지).
  if (sub === "glossary") {
    const tags = document.createElement("div");
    tags.className = "admin-meta-row-tags";
    const rk = String(it.role_key || "*");
    tags.appendChild(mkTag(rk === "*" ? "공용" : `역할: ${_metaRoleLabel(rk)}`,
      rk === "*" ? "admin-meta-tag-neutral" : "admin-meta-tag-role"));
    const src = String(it.source || "manual");
    if (src === "auto") tags.appendChild(mkTag("자동등록", "admin-meta-tag-neutral"));
    else if (src === "auto_promoted") tags.appendChild(mkTag("자동승급", "admin-meta-tag-neutral"));
    main.appendChild(tags);
  }
  // samples 전용 — 가중치/도메인/승인/status 배지. B9: 미승인=warn(주의), stale=danger, status 기타=neutral.
  if (sub === "samples") {
    const tags = document.createElement("div");
    tags.className = "admin-meta-row-tags";
    if (it.domain) tags.appendChild(mkTag(`도메인: ${it.domain}`, "admin-meta-tag-neutral"));
    if (it.weight != null) tags.appendChild(mkTag(`가중치 ${it.weight}`, "admin-meta-tag-neutral"));
    tags.appendChild(mkTag(it.approved ? "승인됨" : "미승인", it.approved ? "admin-meta-tag-ok" : "admin-meta-tag-warn"));
    if (String(it.status || "").toLowerCase() === "stale") {
      tags.appendChild(mkTag("stale", "admin-meta-tag-stale"));
    } else if (it.status) {
      tags.appendChild(mkTag(String(it.status), "admin-meta-tag-neutral"));
    }
    main.appendChild(tags);
  }
  const meta = document.createElement("div");
  meta.className = "admin-meta-row-meta";
  // Issue 3: 등록 시각(created_at) 표기 — 수정 시각과 다르면 병기(언제 등록됐는지 항상 노출).
  const _cAt = it.created_at ? _metaFmtDt(it.created_at) : "";
  const _uAt = it.updated_at ? _metaFmtDt(it.updated_at) : "";
  meta.textContent = (_cAt && _uAt && _cAt !== _uAt) ? `등록 ${_cAt} · 수정 ${_uAt}`
    : _cAt ? `등록 ${_cAt}` : _uAt ? `수정 ${_uAt}` : "";
  main.appendChild(meta);
  row.appendChild(main);
  if (canEdit) {
    const actions = document.createElement("div");
    actions.className = "admin-meta-row-actions";
    if (sub === "glossary") {
      const relBtn = document.createElement("button");
      relBtn.type = "button";
      relBtn.className = "btn-secondary admin-meta-rel";
      relBtn.textContent = "유사어";
      relBtn.addEventListener("click", (e) => { e.stopPropagation(); _metaToggleRelations(it); });
      actions.appendChild(relBtn);
    }
    if (can(_METADATA_SUBTAB_DELETE_PERM[sub] || "metadata.table.delete")) {
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-secondary admin-meta-del";
      delBtn.textContent = "삭제";
      delBtn.addEventListener("click", (e) => { e.stopPropagation(); _metaDelete(it); });
      actions.appendChild(delBtn);
    }
    row.appendChild(actions);
  }
  return row;
}

// enums/columns 를 그룹핑 — 각 그룹을 .dashboard-widget 카드(헤더 + 내부 행)로 렌더. 행 클릭→편집·삭제 보존.
//   M1: enums 는 schema.table.column 로 그룹(컬럼별 코드 묶음) → 헤더에 table.column(컬럼 표시)으로 두 컬럼 동일 코드 모호성 제거.
//        행 = code(제목)/label(본문). columns 는 schema.table 로(컬럼이 leaf, 손실 없음) → 행 = column_name/description.
//   M4: 항목 1건 그룹은 카드 chrome(eyebrow+title+count"1") 없이 flat .admin-meta-row 로 — density 폭발·노이즈 "1" 제거.
//        (flat 행은 grouped=false 로 렌더해 경로 컨텍스트를 행 제목에 그대로 보존.)
function _metaRenderGroupedList(listEl, items, sub, canEdit) {
  const byColumn = (sub === "enums");   // enums 만 컬럼까지 내려 그룹.
  const order = [];
  const groups = new Map();   // key -> { schema, table, column, headTitle, items }
  for (const it of items) {
    const schema = String(it.schema_name || "");
    const table = String(it.table_name || "");
    const column = String(it.column_name || "");
    const key = byColumn
      ? ([schema, table, column].filter(Boolean).join(".") || "(미지정)")
      : ([schema, table].filter(Boolean).join(".") || table || "(미지정)");
    // 카드 헤더 제목 — enums: table.column(컬럼 표시), columns: table.
    const headTitle = byColumn
      ? ([table, column].filter(Boolean).join(".") || key)
      : (table || key);
    if (!groups.has(key)) { groups.set(key, { schema, table, column, headTitle, items: [] }); order.push(key); }
    groups.get(key).items.push(it);
  }
  for (const key of order) {
    const g = groups.get(key);
    // M4: 단일 항목 그룹 → 카드 없이 flat 행(경로 포함 grouped=false).
    if (g.items.length < 2) {
      const flat = _metaListRow(g.items[0], sub, canEdit, false);
      // ux2 #3: enums 단일 코드 그룹도 같은 컬럼에 '코드 추가' 진입점(행 아래 footer 버튼).
      if (sub === "enums" && canEdit) {
        const wrap = document.createElement("div");
        wrap.className = "admin-meta-enum-singleton";
        wrap.appendChild(flat);
        wrap.appendChild(_metaMakeEnumAddCodeBtn(g.items[0]));
        listEl.appendChild(wrap);
      } else {
        listEl.appendChild(flat);
      }
      continue;
    }
    const card = document.createElement("div");
    card.className = "dashboard-widget admin-meta-group";
    const head = document.createElement("div");
    head.className = "admin-meta-group-head";
    const eyebrow = document.createElement("div");
    eyebrow.className = "drawer-label admin-meta-group-eyebrow";
    eyebrow.textContent = g.schema || (sub === "enums" ? "ENUM 코드" : "컬럼");
    const h = document.createElement("div");
    h.className = "admin-meta-group-title";
    h.textContent = g.headTitle || key;
    const cnt = document.createElement("span");
    cnt.className = "admin-meta-group-count";
    cnt.textContent = `${g.items.length}`;   // M4: 개수 배지는 ≥2 그룹에서만 렌더.
    head.appendChild(eyebrow);
    head.appendChild(h);
    head.appendChild(cnt);
    // ux2 #3: enums 그룹 head 에 '코드 추가' — 이 컬럼(schema.table.column)으로 prefill 된 생성 폼.
    if (sub === "enums" && canEdit) head.appendChild(_metaMakeEnumAddCodeBtn(g));
    card.appendChild(head);
    const rows = document.createElement("div");
    rows.className = "admin-meta-group-rows";
    for (const it of g.items) rows.appendChild(_metaListRow(it, sub, canEdit, true));
    card.appendChild(rows);
    listEl.appendChild(card);
  }
}

function renderMetadataList() {
  const listEl = document.getElementById("metadataList");
  const countEl = document.getElementById("metadataCount");
  if (!listEl) return;
  const allItems = adminState.metadata.items;
  const sub = adminState.metadata.subTab;
  // metadata-list-detail: 좌측 목록 검색(title/body 부분일치). 카운트는 검색 시 필터/전체 표기.
  const q = (adminState.metadata.search || "").trim().toLowerCase();
  const qv = searchVariants(adminState.metadata.search);   // hangul-qwerty-search: 원문 + 반대 자판 후보
  const items = qv.length ? allItems.filter((it) => _metaItemMatchesSearch(it, sub, qv)) : allItems;
  // perm-atomic-split: 행 편집 affordance = 수정(update) 원자 게이트(samples=검수 단일).
  const canEdit = can(_METADATA_SUBTAB_UPDATE_PERM[sub] || "metadata.table.update");
  if (countEl) countEl.textContent = q ? `${items.length}/${allItems.length}건` : `${items.length}건`;
  _metaUpdateKpi(allItems, sub);   // B10: KPI 는 전체 로드분 기준.
  listEl.replaceChildren();
  if (!items.length) {
    if (q) {
      listEl.appendChild(_metaEmptyState("검색 결과가 없습니다.", "다른 검색어를 시도하세요."));
    } else {
      const creatable = !_METADATA_NO_CREATE[sub] && can(_METADATA_SUBTAB_CREATE_PERM[sub] || "metadata.table.create");
      listEl.appendChild(_metaEmptyState(_METADATA_EMPTY_MSG[sub] || "등록된 항목이 없습니다.",
        creatable ? "+ 새 항목으로 시작하세요." : ""));
    }
    return;
  }
  // B3: enums/columns 는 그룹 카드로, 나머지(glossary/tables/samples)는 flat.
  if (sub === "enums" || sub === "columns") {
    _metaRenderGroupedList(listEl, items, sub, canEdit);
    return;
  }
  for (const it of items) {
    listEl.appendChild(_metaListRow(it, sub, canEdit, false));
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

// ux2 #3: ENUM 컬럼 그룹의 '+ 코드 추가' 버튼. source 는 그룹({schema,table,column}) 또는 항목({schema_name,…}).
function _metaMakeEnumAddCodeBtn(source) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-secondary admin-meta-enum-add";
  btn.textContent = "+ 코드 추가";
  btn.title = "이 컬럼에 새 코드↔라벨 추가";
  btn.addEventListener("click", (e) => {
    e.stopPropagation();   // 그룹 head/행 클릭 전파 차단.
    _metaStartCreatePrefilled({
      schema_name: (source && (source.schema_name != null ? source.schema_name : source.schema)) || "",
      table_name: (source && (source.table_name != null ? source.table_name : source.table)) || "",
      column_name: (source && (source.column_name != null ? source.column_name : source.column)) || "",
    });
  });
  return btn;
}

// ux2 #3: 지정된 식별 필드(schema/table/column)로 prefill 된 생성 폼 진입 — 기존 create 흐름 재사용(검증/pending 그대로).
//   code/label 은 비워두고 code 에 포커스. 값은 input.value 로만 주입(XSS 안전).
function _metaStartCreatePrefilled(prefill) {
  const md = adminState.metadata;
  md.editing = null;        // 생성 모드.
  md.selectedId = null;
  md.detailMode = "form";
  _metaRenderDetail();       // 빈 생성 폼 렌더.
  _metaSyncListActive();
  const wrap = document.getElementById("metadataFormFields");
  if (wrap && prefill) {
    for (const key of ["schema_name", "table_name", "column_name"]) {
      if (prefill[key] == null) continue;
      const input = wrap.querySelector(`[name="${key}"]`);
      if (input) input.value = String(prefill[key]);
    }
  }
  const codeInput = wrap ? wrap.querySelector('[name="code"]') : null;
  if (codeInput && codeInput.focus) { try { codeInput.focus(); } catch (_) {} }
}

export async function _metaSubmitForm(e) {
  if (e && e.preventDefault) e.preventDefault();
  const sub = adminState.metadata.subTab;
  const scope = adminState.metadata.productScope || "common";
  const fields = _METADATA_FIELDS[sub] || [];
  const vals = _metaFormValues();
  const editing = adminState.metadata.editing;
  // 생성 비활성 서브뷰(samples)는 PUT(수정)만 허용 — POST 경로 차단(검수 경로가 생성 정본).
  if (_METADATA_NO_CREATE[sub] && !(editing && editing.id != null)) {
    if (typeof showToast === "function") showToast("이 항목은 검수 경로로만 생성됩니다.", true);
    return;
  }
  // 클라 필수 검증(백엔드도 검증 — 이중 안전). checkbox 는 필수 검증 제외.
  //   B6: 누락 필드에 인라인 오류(red border + 필드 메시지) + 토스트 병행. 첫 누락 필드로 포커스.
  _metaClearFieldErrors();
  const missing = fields.filter((f) => f.type !== "checkbox" && f.required && !vals[f.key]);
  if (missing.length) {
    for (const f of missing) _metaSetFieldError(f.key, `${f.label}은(는) 필수입니다.`);
    const wrap = document.getElementById("metadataFormFields");
    const firstInput = wrap ? wrap.querySelector(`[name="${missing[0].key}"]`) : null;
    if (firstInput && firstInput.focus) { try { firstInput.focus(); } catch (_) {} }
    if (typeof showToast === "function") showToast(`${missing.map((f) => f.label).join(", ")}은(는) 필수입니다.`, true);
    return;
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
  _metaClearFieldErrors();   // B6: 폼 초기화 시 인라인 오류 제거.
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
  const scope = adminState.metadata.productScope || "common";
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
  const showRole = (adminState.metadata.subTab === "glossary" && _metaCurrentView() === "list");
  const label = document.getElementById("metadataRoleFilterLabel");
  const sel = document.getElementById("metadataRoleFilter");
  if (label) label.style.display = showRole ? "" : "none";
  if (sel) {
    sel.style.display = showRole ? "" : "none";
    if (showRole) _metaPopulateRoleFilter();
  }
}

// ── 검토 큐(용어사전/ENUM 공용, 파라미터화) ─────────────────────────────────────
//   glossary + enum 은 promote/reject + status 필터 흐름이 동일하고 필드/엔드포인트만 다르다.
//   kind: "glossary" | "enum". 서브탭 매핑: glossary→glossary, enum→enums(_METADATA_REVIEW key).
function _metaReviewCfgOf(kind) {
  const sub = kind === "glossary" ? "glossary" : "enums";
  return { sub, cfg: _METADATA_REVIEW[sub] };
}

// 검토·검수 큐 제품 필터(Issue 1 / metadata-product-scope) — 상단 제품 셀렉터를 목록과 동일 축으로 적용.
//   특정 제품 선택 시 그 제품 스코프로 후보를 한정한다. '공용' 은 전체 제품 triage 로 표시한다
//   (자율수집 후보는 대화의 제품에 귀속되므로 common 을 문자 그대로 필터하면 큐가 영구히 비고 pending
//   배지와 불일치 — Option A 유지). 반환: URL-encoded scope_key 또는 ""(전체).
function _metaReviewScopeParam() {
  const scope = String(adminState.metadata.productScope || "common");
  return (scope && scope !== "common") ? encodeURIComponent(scope) : "";
}

async function loadFeedbackQueue(kind) {
  const { sub, cfg } = _metaReviewCfgOf(kind);
  const listEl = document.getElementById("metadataList");
  if (!listEl) return;
  adminState.metadata.feedback.loading = true;
  listEl.replaceChildren();
  listEl.appendChild(_metaLoadingSkeleton());
  const status = adminState.metadata.feedback.status || "pending";
  try {
    let url = `${cfg.endpoint}?status=${encodeURIComponent(status)}`;
    const sp = _metaReviewScopeParam();   // Issue 1: 선택 datasource 로 검토 큐 필터('공용'=전체).
    if (sp) url += `&scope_key=${sp}`;
    const data = await apiFetch(url);
    adminState.metadata.feedback.items = (data && data.items) || [];
    adminState.metadata.feedback.pendingCount = (data && data.pending_count) || 0;
    adminState.metadata.reviewPending[sub] = adminState.metadata.feedback.pendingCount;
    _metaRefreshReviewBadge(sub);
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
  renderFeedbackQueue(kind);
}

function renderFeedbackQueue(kind) {
  const { cfg } = _metaReviewCfgOf(kind);
  const listEl = document.getElementById("metadataList");
  const countEl = document.getElementById("metadataCount");
  if (!listEl) return;
  _metaClearReviewDetail();   // ux2 #2: 큐 (재)렌더 시 우측 상세 초기화(stale 선택 방지).
  const items = adminState.metadata.feedback.items || [];
  const canCurate = can(cfg.reviewPerm);
  if (countEl) countEl.textContent = `${items.length}건`;
  const kpiEl = document.getElementById("metadataKpi");
  if (kpiEl) { kpiEl.textContent = ""; kpiEl.style.display = "none"; }   // L5: 검토 큐 보기엔 KPI 무의미 — 비우고 숨김(stale/빈 gap 방지).
  listEl.replaceChildren();

  // 상태 필터 툴바(pending / auto_promoted / promoted / rejected / 전체).
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
    loadFeedbackQueue(kind);
  });
  bar.appendChild(sel);
  const note = document.createElement("span");
  note.className = "admin-archive-detail-note";
  note.textContent = kind === "enum"
    ? "대화에서 자동 수집된 ENUM 코드↔라벨 후보입니다. 컬럼(구조 묶음)별로 묶어 표시합니다. 묶음 안에서 전체 승인 또는 일부 해제 후 '등록'하면 선택한 코드만 코드사전에 반영되고, 해제한 코드는 검토 큐에 그대로 남습니다."
    : "대화에서 자동 제안된 용어 후보입니다. 승급하면 용어사전에 반영되고, 거부하면 제외(자동 등록분은 회수)됩니다.";
  bar.appendChild(note);
  listEl.appendChild(bar);

  // ENUM 검토 큐는 구조 묶음(scope · schema.table.column) 단위 승인 체크리스트 + 일괄 등록으로 렌더.
  if (kind === "enum") {
    _metaRenderEnumBundles(listEl, items, canCurate);
    return;
  }

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = kind === "enum" ? "검토할 ENUM 후보가 없습니다." : "검토할 용어 후보가 없습니다.";
    listEl.appendChild(empty);
    return;
  }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "admin-meta-row";
    // ux2 #2: 후보 행 클릭 → 우측 read-only 상세(승급/거부 버튼은 stopPropagation 로 행-선택 미발화).
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    const _openFb = () => {
      adminState.metadata.reviewSelected = { kind, item: it };
      _metaRenderReviewDetail(kind, it);
      _metaMarkReviewActive(listEl, row);
    };
    row.addEventListener("click", _openFb);
    row.addEventListener("keydown", (e) => {
      if (e.target !== e.currentTarget) return;   // 내부 버튼 키 입력 무시(이중 발화 방지).
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); _openFb(); }
    });
    const main = document.createElement("div");
    main.className = "admin-meta-row-main";
    const title = document.createElement("div");
    title.className = "admin-meta-row-title";
    const body = document.createElement("div");
    body.className = "admin-meta-row-body";
    if (kind === "enum") {
      // 제목 = table.column · code(CSS 구분자 span). 본문 = 제안 라벨.
      const loc = [it.schema_name, it.table_name, it.column_name].filter(Boolean).join(".");
      _metaAppendPathCode(title, loc, it.code);
      body.textContent = it.suggested_label || "";
    } else {
      title.textContent = it.term || "";
      body.textContent = it.suggested_definition || "";
    }
    main.appendChild(title);
    main.appendChild(body);
    // 배지: (glossary)역할 / scope / confidence / status.
    const tags = document.createElement("div");
    tags.className = "admin-meta-row-tags";
    const mkTag = (text, cls) => {
      const t = document.createElement("span");
      t.className = "admin-meta-tag" + (cls ? " " + cls : "");
      t.textContent = text;
      return t;
    };
    if (kind === "glossary") {
      const rk = String(it.role_key || "*");
      tags.appendChild(mkTag(rk === "*" ? "공용" : `역할: ${_metaRoleLabel(rk)}`, rk === "*" ? "admin-meta-tag-neutral" : "admin-meta-tag-role"));
    }
    if (it.scope_key) tags.appendChild(mkTag(`scope: ${_metaDatasourceLabelOf(it.scope_key)}`, "admin-meta-tag-neutral"));
    if (it.confidence != null) tags.appendChild(mkTag(`신뢰도 ${Number(it.confidence).toFixed(2)}`, "admin-meta-tag-conf"));  /* 폴리시 #5: 신뢰도 accent. */
    const st = String(it.status || "");
    const stLabel = { pending: "검토 대기", auto_promoted: "자동 등록됨", promoted: "승급됨", rejected: "거부됨" }[st] || st;
    // L7: 자동 등록(auto_promoted=provenance)=neutral 회색(경고 아님), 승급=ok, 거부=danger, 검토 대기=neutral.
    const stCls = st === "promoted" ? "admin-meta-tag-ok"
      : st === "rejected" ? "admin-meta-tag-danger"
      : "admin-meta-tag-neutral";
    tags.appendChild(mkTag(stLabel, stCls));
    main.appendChild(tags);
    // Issue 3: 등록 시각(created_at) — 후보가 언제 수집·제안됐는지 표기.
    if (it.created_at) {
      const cMeta = document.createElement("div");
      cMeta.className = "admin-meta-row-meta";
      cMeta.textContent = `등록 ${_metaFmtDt(it.created_at)}`;
      main.appendChild(cMeta);
    }
    row.appendChild(main);

    if (canCurate) {
      const actions = document.createElement("div");
      actions.className = "admin-meta-row-actions";
      if (st === "pending") {
        const promoteBtn = document.createElement("button");
        promoteBtn.type = "button";
        promoteBtn.className = "btn-primary admin-meta-edit";
        promoteBtn.textContent = "승급";
        promoteBtn.addEventListener("click", (e) => { e.stopPropagation(); _feedbackQueueAction(kind, it.id, "promote", promoteBtn); });
        actions.appendChild(promoteBtn);
      }
      if (st === "pending" || st === "auto_promoted") {
        const rejectBtn = document.createElement("button");
        rejectBtn.type = "button";
        rejectBtn.className = "btn-secondary admin-meta-del";
        rejectBtn.textContent = (st === "auto_promoted") ? "되돌리기" : "거부";
        rejectBtn.addEventListener("click", (e) => { e.stopPropagation(); _feedbackQueueAction(kind, it.id, "reject", rejectBtn); });
        actions.appendChild(rejectBtn);
      }
      if (actions.childNodes.length) row.appendChild(actions);
    }
    listEl.appendChild(row);
  }
}

// ── ENUM 검토 큐 — 구조 묶음(scope · schema.table.column) 단위 승인 체크리스트 + 일괄 등록 ──────
// enum_feedback UNIQUE 키 = (scope,schema,table,column,code) → 한 컬럼 = 한 '구조 묶음'. 묶음별로
// pending 후보를 체크리스트로 묶어 '전체 승인' 마스터 체크 + 개별 해제('일부만 승인 해제') 후 '등록'
// (bulk-promote) 한다. 미선택(해제)은 pending 유지(비파괴). promoted/rejected/auto 행은 읽기전용 표시.
function _enumBundleKey(it) {
  return [it.scope_key || "", it.schema_name || "", it.table_name || "", it.column_name || ""].join("");
}

function _metaRenderEnumBundles(listEl, items, canCurate) {
  const countEl = document.getElementById("metadataCount");
  // 묶음 그룹핑 — 입력 순서 보존(백엔드가 status/created_at DESC 정렬). Map 은 삽입 순서 유지.
  const bundles = new Map();
  for (const it of (items || [])) {
    const key = _enumBundleKey(it);
    let b = bundles.get(key);
    if (!b) {
      b = { scope_key: it.scope_key || "", schema_name: it.schema_name || "",
            table_name: it.table_name || "", column_name: it.column_name || "", items: [] };
      bundles.set(key, b);
    }
    b.items.push(it);
  }
  if (countEl) countEl.textContent = bundles.size ? `${(items || []).length}건 · ${bundles.size}개 묶음` : "0건";
  if (!bundles.size) {
    const empty = document.createElement("div");
    empty.className = "admin-list-empty";
    empty.textContent = "검토할 ENUM 후보가 없습니다.";
    listEl.appendChild(empty);
    return;
  }
  for (const b of bundles.values()) {
    listEl.appendChild(_metaBuildEnumBundle(b, canCurate));
  }
}

function _metaBuildEnumBundle(b, canCurate) {
  const card = document.createElement("div");
  card.className = "admin-meta-bundle";

  const pendingItems = b.items.filter((it) => String(it.status || "") === "pending");
  const hasPending = pendingItems.length > 0;
  const showChecklist = canCurate && hasPending;   // 체크리스트/등록은 pending 후보가 있고 큐레이트 권한일 때만.

  // ── 헤더: [전체 승인 마스터]  scope · schema.table.column  [코드 N개 · 대기 M]
  const head = document.createElement("div");
  head.className = "admin-meta-bundle-head";
  let master = null;
  if (showChecklist) {
    const ml = document.createElement("label");
    ml.className = "admin-meta-bundle-master";
    master = document.createElement("input");
    master.type = "checkbox";
    master.checked = true;
    ml.appendChild(master);
    const mt = document.createElement("span");
    mt.textContent = "전체 승인";
    ml.appendChild(mt);
    head.appendChild(ml);
  }
  const titleWrap = document.createElement("div");
  titleWrap.className = "admin-meta-bundle-title";
  const scopeTag = document.createElement("span");
  scopeTag.className = "admin-meta-tag admin-meta-tag-neutral";
  scopeTag.textContent = `scope: ${_metaDatasourceLabelOf(b.scope_key)}`;
  titleWrap.appendChild(scopeTag);
  const loc = [b.schema_name, b.table_name, b.column_name].filter(Boolean).join(".");
  const locEl = document.createElement("span");
  locEl.className = "admin-meta-bundle-loc";
  locEl.textContent = loc;
  titleWrap.appendChild(locEl);
  head.appendChild(titleWrap);
  const cnt = document.createElement("span");
  cnt.className = "admin-meta-bundle-count";
  cnt.textContent = hasPending ? `코드 ${b.items.length}개 · 대기 ${pendingItems.length}` : `코드 ${b.items.length}개`;
  head.appendChild(cnt);
  card.appendChild(head);

  // ── 코드 체크리스트
  const list = document.createElement("div");
  list.className = "admin-meta-bundle-list";
  const checkboxes = [];
  for (const it of b.items) {
    const isPending = String(it.status || "") === "pending";
    const row = document.createElement("div");
    row.className = "admin-meta-bundle-row";
    if (showChecklist && isPending) {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      cb.className = "admin-meta-bundle-check";
      cb.dataset.fid = String(it.id);
      cb.setAttribute("aria-label", `${it.code} 승인`);
      checkboxes.push(cb);
      row.appendChild(cb);
    } else {
      const sp = document.createElement("span");
      sp.className = "admin-meta-bundle-check-sp";
      sp.setAttribute("aria-hidden", "true");
      row.appendChild(sp);
    }
    const codeWrap = document.createElement("div");
    codeWrap.className = "admin-meta-bundle-codewrap";
    const codeEl = document.createElement("span");
    codeEl.className = "admin-meta-code";
    codeEl.textContent = String(it.code || "");
    codeWrap.appendChild(codeEl);
    const arrow = document.createElement("span");
    arrow.className = "admin-meta-bundle-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    codeWrap.appendChild(arrow);
    const labelEl = document.createElement("span");
    labelEl.className = "admin-meta-bundle-label";
    labelEl.textContent = it.suggested_label || "";
    codeWrap.appendChild(labelEl);
    row.appendChild(codeWrap);
    const tags = document.createElement("div");
    tags.className = "admin-meta-bundle-tags";
    if (it.confidence != null) {
      const t = document.createElement("span");
      t.className = "admin-meta-tag admin-meta-tag-conf";
      t.textContent = `신뢰도 ${Number(it.confidence).toFixed(2)}`;
      tags.appendChild(t);
    }
    if (it.created_at) {   // Issue 3: 등록 시각 — 묶음 내 각 코드 후보의 수집 시점.
      const ct = document.createElement("span");
      ct.className = "admin-meta-tag admin-meta-tag-neutral";
      ct.textContent = `등록 ${_metaFmtDt(it.created_at)}`;
      tags.appendChild(ct);
    }
    const st = String(it.status || "");
    if (st !== "pending") {
      const stLabel = { auto_promoted: "자동 등록됨", promoted: "승급됨", rejected: "거부됨" }[st] || st;
      const stCls = st === "promoted" ? "admin-meta-tag-ok" : st === "rejected" ? "admin-meta-tag-danger" : "admin-meta-tag-neutral";
      const t = document.createElement("span");
      t.className = "admin-meta-tag " + stCls;
      t.textContent = stLabel;
      tags.appendChild(t);
    }
    row.appendChild(tags);
    list.appendChild(row);
  }
  card.appendChild(list);

  // ── 푸터: 등록 버튼 + 선택 상태 힌트(전체 승인 / 일부 해제) — 마스터·개별 체크박스와 연동.
  if (showChecklist) {
    const foot = document.createElement("div");
    foot.className = "admin-meta-bundle-foot";
    const hint = document.createElement("span");
    hint.className = "admin-meta-bundle-hint";
    foot.appendChild(hint);
    const reg = document.createElement("button");
    reg.type = "button";
    reg.className = "btn-primary admin-meta-bundle-register";
    foot.appendChild(reg);
    const syncState = () => {
      const checkedN = checkboxes.filter((c) => c.checked).length;
      reg.textContent = `등록 (${checkedN})`;
      reg.disabled = checkedN === 0;
      hint.textContent = checkedN === checkboxes.length ? "전체 승인"
        : checkedN === 0 ? "선택된 코드 없음"
        : `일부 해제 (${checkboxes.length - checkedN}개 제외)`;
      if (master) {
        master.checked = checkedN === checkboxes.length;
        master.indeterminate = checkedN > 0 && checkedN < checkboxes.length;
      }
    };
    for (const c of checkboxes) c.addEventListener("change", syncState);
    if (master) {
      master.addEventListener("change", () => {
        for (const c of checkboxes) c.checked = master.checked;
        syncState();
      });
    }
    reg.addEventListener("click", () => {
      const ids = checkboxes.filter((c) => c.checked).map((c) => Number(c.dataset.fid));
      _enumBundleRegister(ids, reg);
    });
    syncState();
    card.appendChild(foot);
  }
  return card;
}

async function _enumBundleRegister(feedbackIds, btn) {
  if (!feedbackIds || !feedbackIds.length) return;
  if (!window.confirm(`선택한 ${feedbackIds.length}개 코드를 ENUM 코드사전에 등록(승급)합니다.\n해제한 코드는 검토 큐에 그대로 남습니다.`)) return;
  if (btn) btn.disabled = true;
  try {
    const data = await apiFetch("/api/admin/metadata/enum-feedback/bulk-promote", {
      method: "POST",
      body: JSON.stringify({ feedback_ids: feedbackIds }),
    });
    const n = (data && data.promoted_count) || 0;
    const skipped = (data && data.skipped_ids && data.skipped_ids.length) || 0;
    if (typeof showToast === "function") {
      showToast(skipped ? `${n}개 코드를 등록했습니다. (${skipped}개는 이미 처리됨)` : `${n}개 코드를 코드사전에 등록했습니다.`);
    }
    await loadFeedbackQueue("enum");
  } catch (err) {
    if (typeof showToast === "function") showToast((err && err.message) || "등록 실패", true);
    if (btn) btn.disabled = false;
  }
}

async function _feedbackQueueAction(kind, feedbackId, action, btn) {
  const { cfg } = _metaReviewCfgOf(kind);
  const confirmMsg = kind === "enum"
    ? "이 ENUM 후보를 거부하시겠습니까?\n자동 등록된 코드라면 코드사전에서 회수됩니다."
    : "이 용어 후보를 거부하시겠습니까?\n자동 등록된 용어라면 용어사전에서 회수됩니다.";
  if (action === "reject" && !window.confirm(confirmMsg)) return;
  if (btn) btn.disabled = true;
  try {
    await apiFetch(`${cfg.endpoint}/${encodeURIComponent(feedbackId)}/${action}`, { method: "POST" });
    if (typeof showToast === "function") {
      const promoted = kind === "enum" ? "코드사전에 승급했습니다." : "용어사전에 승급했습니다.";
      showToast(action === "promote" ? promoted : "거부 처리했습니다.");
    }
    await loadFeedbackQueue(kind);
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
// metadata-product-scope: 부트스트랩 대상은 상단 **제품** 스코프를 상속한다.
//   - 공용(common) → 특정 제품의 접근DB 가 없음 → empty-state(#metadataBootstrapEmpty)만 노출.
//   - 구체 제품 스코프 → 골격 컨트롤(토글+본문) 노출 + 그 제품의 접근DB 목록 로드.
function _metaSyncBootstrapVisibility() {
  const panel = document.getElementById("metadataBootstrap");
  if (!panel) return;
  const sub = adminState.metadata.subTab;
  const applicable = (sub === "tables" || sub === "columns") && can("metadata.table.create") && can("metadata.table.update");
  panel.style.display = applicable ? "" : "none";
  if (!applicable) return;
  const isProduct = _metaScopeIsProduct();  // 공용이면 false.
  const head = document.getElementById("metadataBootstrapHead");
  const body = document.getElementById("metadataBootstrapBody");
  const empty = document.getElementById("metadataBootstrapEmpty");
  if (!isProduct) {
    // 공용(common) 스코프 — 골격 불가. empty-state 만 노출(토글/본문 숨김).
    if (empty) empty.style.display = "";
    if (head) head.style.display = "none";
    if (body) body.style.display = "none";
    return;
  }
  // 구체 제품 스코프 — 골격 컨트롤 노출. 본문은 접힘 상태(bootstrap.open)를 따른다.
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
  _metaBootstrapSyncToScope(adminState.metadata.productScope || "common");
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
  // 상속한다(_metaBootstrapSyncToScope). 스코프 변경 핸들러(_metaBindControls)와 서브탭/패널
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
  // feature-0043 TASK-20260831T100000 — 일괄 자동완성도 같은 게이트.
  // 여기는 안내 줄까지 붙인다: 일괄은 사용자가 골격을 다 만들어 둔 **뒤에** 누르는 버튼이라,
  // 그 시점에 막히면 이미 들인 수고가 헛되었다고 느낀다 — 먼저 알려야 한다.
  gateLlmControl(aiBtn, {
    label: "메타데이터 AI 일괄 자동완성",
    delegatedText: "AI 일괄 자동완성 (내 AI)",
    jobKind: "metadata_bulk",
  });
  renderLlmNotice(aiBtn && aiBtn.closest(".admin-settings-panel-body, .admin-subpane, .admin-detail-col"),
                  { label: "AI 일괄 자동완성", jobKind: "metadata_bulk" });
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

// metadata-product-scope: 부트스트랩 대상을 상단 **제품** 스코프에서 상속한다.
// 노트의 제품명(읽기 전용 컨텍스트)을 갱신하고, 제품이 바뀐 경우에만 이전 골격/DB 선택을 리셋한 뒤
// 새 제품의 접근DB 목록을 로드한다.
// (구체 제품 스코프에서만 호출됨 — 공용은 _metaSyncBootstrapVisibility 가 먼저 차단.)
function _metaBootstrapSyncToScope(scopeKey) {
  const sk = String(scopeKey || "").trim().toLowerCase();
  const entry = _metaCurrentProductEntry();
  const dsName = document.getElementById("metadataBootstrapDsName");
  if (dsName) dsName.textContent = (entry && (entry.name || entry.product_key)) || "—";
  if (sk === (adminState.metadata.bootstrap.scopeKey || "")) return;  // 변동 없음 — 기존 골격 보존.
  // 제품 변경 — 이전 제품의 골격/접근DB 선택은 무효.
  adminState.metadata.bootstrap.scopeKey = sk;
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
  const sk = adminState.metadata.bootstrap.scopeKey;
  const schemaSel = document.getElementById("metadataBootstrapSchema");
  const fetchBtn = document.getElementById("metadataBootstrapFetchBtn");
  if (schemaSel) { schemaSel.replaceChildren(); schemaSel.disabled = true; }
  if (fetchBtn) fetchBtn.disabled = true;
  if (!sk || sk === "common") { adminState.metadata.bootstrap.unitKind = ""; _metaBootstrapSetUnitLabel(); _metaBootstrapStatus(""); return; }
  _metaBootstrapStatus("목록 로딩 중…");
  try {
    const data = await apiFetch(`/api/admin/metadata/bootstrap/schemas?scope_key=${encodeURIComponent(sk)}`);
    // 제품 스코프가 부트스트랩 대상을 결정하므로 제품 빠른 전환 시 본 함수가 연속 발화한다.
    // await 사이에 제품이 바뀌었으면 이 응답은 stale — 폐기해 늦게 온 응답이 다른 제품 목록을 덮지 않게 한다.
    if (adminState.metadata.bootstrap.scopeKey !== sk) return;
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

// 골격 가져오기 — POST /bootstrap {scope_key,schema}. 응답 tables 를 입력 트리로 렌더.
// metadata-product-scope: 가드는 제품 스코프(bs.scopeKey)를 본다 — 폐기된 bs.datasource 를 계속
// 검사하면 항상 검증 실패로 떨어져 골격 가져오기가 통째로 죽는다(codex review P1).
async function _metaBootstrapFetch() {
  const bs = adminState.metadata.bootstrap;
  if (!bs.scopeKey || bs.scopeKey === "common" || !bs.schema) {
    _metaBootstrapStatus(`제품과 ${_metaBootstrapUnitWord()}를 선택하세요.`, true);
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
      body: JSON.stringify({ scope_key: bs.scopeKey, schema: bs.schema }),
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
  // metadata-pane-refresh: 통합 표 sticky 열 헤더. 가시성은 `hidden` 속성 단일 채널
  // (CSS `[hidden]` 규칙 + 인접 형제 규칙이 결과 컨테이너의 상단 변 소유를 넘겨받는다).
  const gridHead = document.getElementById("metadataBootstrapGridHead");
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
    if (gridHead) gridHead.hidden = true;
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
    if (gridHead) gridHead.hidden = true;
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
        // metadata-pane-refresh: 이름 칸이 고정 폭(입력란 시작 x 정렬 조건)이라 긴 컬럼명은
        // ellipsis 로 잘린다 → 전체 이름을 hover 로 회수 가능하게(tables 모드 테이블명과 동일 규약).
        cn.title = colName;
        const dt = document.createElement("span");
        dt.className = "admin-meta-bs-col-type";
        dt.textContent = c.data_type ? `(${c.data_type})` : "";
        // metadata-pane-refresh: 타입 칸이 고정 폭(입력란 시작 x 정렬을 위해)이라 긴 타입
        // (`decimal(18,4)` 등)은 ellipsis 로 잘린다 → 전체 값을 hover 로 보존.
        if (c.data_type) dt.title = String(c.data_type);
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
  // metadata-pane-refresh: 통합 표 열 헤더는 **tables 모드 전용**이다 — columns 모드의 행은
  // 접힘 헤더(caret + 이름 + 상태)라 "설명" 열이 존재하지 않고, 입력란은 펼친 본문 안에 있다.
  // 없는 열의 라벨을 띄우면 헤더가 행과 어긋난 거짓 정보가 된다.
  if (gridHead) gridHead.hidden = mode !== "tables";
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
// metadata-pane-refresh(20260812T1739): raw `●`/`○` 글리프를 텍스트에서 제거했다 — 상태 dot 은
// CSS(`.admin-meta-bs-hint::before`)가 그리고 색은 `--tag-*` 시맨틱 토큰에서 나온다. 라벨 문구
// (`비어있음` / `설명 입력됨` / `컬럼 N/M`)는 그대로다(사용자 문구·기존 하네스 계약 보존).
// `is-complete` 는 "전량 입력 완료" 3단 상태 — 미입력 / 진행 / 완료를 색으로 스캔하게 한다.
function _metaBootstrapUpdateHint(block, mode) {
  const hint = block && block.querySelector(".admin-meta-bs-hint");
  if (!hint) return;
  if (mode === "tables") {
    const inp = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
    const has = !!(inp && (inp.value || "").trim());
    hint.textContent = has ? "설명 입력됨" : "비어있음";
    hint.classList.toggle("is-filled", has);
    // tables 는 테이블당 설명 1줄뿐이라 "입력됨" 이 곧 완료다.
    hint.classList.toggle("is-complete", has);
  } else {
    const total = block.querySelectorAll(".admin-meta-bs-col").length;
    let filled = 0;
    block.querySelectorAll(".admin-meta-bs-desc[data-kind='column']").forEach((i) => {
      if ((i.value || "").trim()) filled += 1;
    });
    hint.textContent = total ? `컬럼 ${filled}/${total}` : "컬럼 없음";
    hint.classList.toggle("is-filled", filled > 0);
    hint.classList.toggle("is-complete", total > 0 && filled === total);
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
  const qv = searchVariants(search ? search.value : "");   // hangul-qwerty-search: 원문 + 반대 자판 후보
  const blocks = wrap.querySelectorAll(".admin-meta-bs-table");
  const bs = adminState.metadata.bootstrap;
  // 1) 필터 매칭 — 검색어 부분일치한 블록만 페이징 대상. 비매칭은 즉시 숨김.
  const matched = [];
  blocks.forEach((b) => {
    const nm = [(b.dataset.schema || ""), (b.dataset.table || "")].filter(Boolean).join(".").toLowerCase();
    if (matchesAnyVariant(nm, qv)) matched.push(b);
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
  const scope = adminState.metadata.productScope || "common";
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

export {
  initMetadataTab, loadMetadata, _metaPopulateProductScopeSelect,
  _metaApplySubtabPermissions, _metaSyncViews, _metaPrimeReviewBadge, _metaRefreshReviewBadge,
  _metaRenderDetail, _metaRenderReviewDetail, _metaClearReviewDetail, _metaMarkReviewActive,
  _metaReviewScopeParam, _metaLoadingSkeleton, _metaFmtDt, _metaIsMermaid, _metaDatasourceLabelOf,
};
