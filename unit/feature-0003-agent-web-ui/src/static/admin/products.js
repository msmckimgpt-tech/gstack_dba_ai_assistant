// feature-0038 Cycle 5 — 제품 pane (관리 콘솔 > 제품: 목록·bulk·상세[접근 DB allowlist·
//   DB 규칙·인사이트 커버리지·시스템 프롬프트]·생성). admin.js 구 L7616–9660 에서 byte-동치
//   이동 (본문 무수정 — ITEM-P5b). Product subcatalog(역할/계정 상세용 카드)는 accounts/roles
//   가 공유하는 코어라 admin.js 잔류.
import {
  adminState, apiFetch, can, showToast, $, formatDateTime,
  loadAdminData, entityUnit, applyShiftRangeSelect, confirmBulkAction,
  runBulkActionWithPartialFail, renderCrossPageBanner, applyAvatar,
  buildSystemPromptEditor,
  setProductMetaPending, setProductDatabasesPending, effectiveProductDatasources,
  stageAddDatasource, stageRemoveDatasource, stageSetPrimaryDatasource,
  _ensureDbRulePending, _getDbRulePending, _settleDbRulePending,
  applyDbPickerRegexHighlight, applyDbPickerSearch, dbPickerRegexMatches,
  _probeDatasourceConn, _paintDsConnBadge,
  DB_PICKER_SEARCH_MIN, INTERNAL_SCHEMAS, METADATA_SCHEMAS,
} from "../admin.js?v=dev";
// hangul-qwerty-search: 한/영 자판을 잘못 둔 채 친 검색어도 찾아준다(`ㅎㅋ`→`gz`).
//   저장소 단일 primitive — 매핑표를 여기 복제하지 않는다.
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

/* ── Products pane ───────────────────────────────────────────────────── */

// ITEM-03 (DQA-09 설명 길이): 서버 DDL 상한과 **같은 값**이어야 한다 —
// 백엔드 정본은 `routers/_bootstrap_schema.py` 의 `PRODUCT_DESCRIPTION_MAX` /
// `PRODUCT_NAME_MAX` (= `WebProducts.Description VARCHAR(255)` / `Name VARCHAR(128)`).
// 이 상수는 «서버 왕복 전에 알려주기» 용 표시축이고 집행은 서버 400 이다(display-permissive ·
// backend-enforced). BE↔FE 값 일치는 `tests/test_product_create_atomic.py` 가 강제한다.
const PRODUCT_DESCRIPTION_MAX = 255;
const PRODUCT_NAME_MAX = 128;

// 입력 옆에 «N/최대» 카운터를 붙이고 입력마다 갱신한다. 반환값은 카운터 요소(호출부가 append).
function _attachCharCounter(inputEl, maxLen) {
  const counter = document.createElement("span");
  counter.className = "admin-char-counter";
  // 이 요소는 감싸는 `<label>` 안에 있다 — 래핑 label 의 접근가능 이름은 자손 텍스트를
  // 이어붙이므로, 그냥 두면 입력의 이름이 «설명 3/255» 처럼 **타이핑마다 바뀌는 숫자**를
  // 포함하게 된다(적대 검증 지적). 시각 표시 전용으로 감춘다 — 상한 자체는 `maxlength` 를
  // 통해 보조기술이 이미 알린다.
  counter.setAttribute("aria-hidden", "true");
  const paint = () => {
    const used = String(inputEl.value || "").length;
    counter.textContent = `${used}/${maxLen}`;
    counter.classList.toggle("is-limit", used >= maxLen);
  };
  inputEl.addEventListener("input", paint);
  paint();
  return counter;
}

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
  // hangul-qwerty-search: 원문 + 반대 자판 변환본을 함께 부분일치(항목마다 재생성하지 않게 밖에서 1회).
  const qv = searchVariants(adminState.productSearch);
  return adminState.products.filter((p) => {
    // 계정 탭 filteredAccounts() 와 동형: 상태 필터 먼저, 그다음 검색어 매칭.
    if (adminState.productFilter === "active" && !p.is_active) return false;
    if (adminState.productFilter === "inactive" && p.is_active) return false;
    if (!qv.length) return true;
    return (
      matchesAnyVariant((p.product_key || "").toLowerCase(), qv)
      || matchesAnyVariant((p.name || "").toLowerCase(), qv)
      || matchesAnyVariant((p.description || "").toLowerCase(), qv)
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

  // perm-atomic-split: bulk 액션별 원자 게이트 — 활성/비활성=수정(update), 삭제=삭제(delete).
  if (can("product.update")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkProductSetActive(true)));
    bar.appendChild(makeBtn("비활성화 pending", () => bulkProductSetActive(false)));
  }
  if (can("product.delete")) {
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
  // perm-atomic-split: 상세 편집 affordance = 수정(update) 원자 게이트(입력 disable·구성 액션).
  const canManage = can("product.update");
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
  // ITEM-03: DDL 상한(`Name VARCHAR(128)`) 을 입력 단계에서 고정 — 넘겨 붙여넣을 수 없다.
  nameInput.maxLength = PRODUCT_NAME_MAX;
  nameInput.addEventListener("input", () => {
    setProductMetaPending(product.id, { name: nameInput.value.trim() });
  });
  nameField.append(nameLabel, nameInput, _attachCharCounter(nameInput, PRODUCT_NAME_MAX));
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
  // ITEM-03 / E-09b: 종전엔 maxlength 가 없어 256자 이상이 그대로 전송되고 서버가
  // `Data too long for column 'Description'` 을 500 으로 돌려줬다.
  descInput.maxLength = PRODUCT_DESCRIPTION_MAX;
  descInput.addEventListener("input", () => {
    setProductMetaPending(product.id, { description: descInput.value.trim() });
  });
  descField.append(descLabel, descInput, _attachCharCounter(descInput, PRODUCT_DESCRIPTION_MAX));
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
    // dbpicker-layout-stability: 재구성(정규식 일괄 선택·× 제거·insight 도착)마다 innerHTML 을
    //  비우므로 드롭다운 **내부** 스크롤이 맨 위로 튄다 — 방금 보던 항목을 다시 찾아 내려야
    //  했다. 바깥 밀림(위 순서 수정)과 같은 부류의 "위치 상실" 이라 함께 봉인한다.
    const _keepScrollTop = pickerDropList.scrollTop;
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

    // dbpicker-layout-stability: 등록 목록이 picker **아래**로 내려가면서, "방금 체크가 반영됐나"
    //  를 알려주는 표면이 드롭다운 안에 상시 필요해졌다. 종전엔 선택 카운트가 검색 toolbar
    //  (후보 6개 이상일 때만 노출)에 얹혀 있어 후보가 적은 datasource 에선 아무 피드백이 없었다.
    //  toolbar 자체는 항상 만들고, 검색·정규식 행만 임계 이상에서 채운다(노출 임계 계약 보존).
    const toolbar = document.createElement("div");
    toolbar.className = "admin-db-picker-toolbar";
    toolbar.addEventListener("click", (e) => e.stopPropagation());  // toolbar 클릭이 항목 토글로 새지 않게.

    if (userSchemas.length >= DB_PICKER_SEARCH_MIN) {
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
    }

    selectedCountEl = document.createElement("div");
    selectedCountEl.className = "admin-db-picker-selected-count";
    selectedCountEl.setAttribute("role", "status");   // 체크 결과를 보조기술에도 알림.
    toolbar.appendChild(selectedCountEl);

    pickerDropList.appendChild(toolbar);

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
      const _srcVal = _draftEntry && String(_draftEntry.source || "manual");
      const _isRuleEntry = _srcVal === "rule" || _srcVal === "ai";   // §59: ai 승인 행도 자동 관리 특례
      cb.disabled = !canManage || !!_isRuleEntry;
      if (_srcVal === "rule") item.title = "정규식 자동 규칙으로 추가됨 — 규칙 편집/삭제로 관리합니다.";
      else if (_srcVal === "ai") item.title = "AI 분류 제안 승인으로 추가됨 — 접근DB 목록에서 삭제로 관리합니다.";
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
    // 필터 적용까지 끝난 뒤 복원 — .hidden 토글이 scrollHeight 를 바꾸므로 순서가 중요하다
    // (브라우저가 새 scrollHeight 로 clamp 한다).
    pickerDropList.scrollTop = _keepScrollTop;
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
      // dbpicker-layout-stability: picker 가 이 목록 **위**로 올라갔다(방향 지시어 정합).
      empty.textContent = "등록된 데이터베이스가 없습니다. 위 '+ 데이터베이스 추가' 에서 선택하세요.";
      listEl.appendChild(empty);
    }
    chipWrap.appendChild(listEl);
  };

  // 접근 DB 편집기(추가 picker + 시스템칩 + 사용자 DB 리스트)를 담는 컨테이너.
  // accordion 의 "펼친 datasource 행" 아래로 이 컨테이너를 옮겨 단다(_renderDsAccordion).
  const dbEditorWrap = document.createElement("div");
  dbEditorWrap.className = "cov-db-editor";

  const pickerWrap = document.createElement("div");
  pickerWrap.className = "admin-db-picker-wrap";
  const pickerDropBtn = document.createElement("button");
  pickerDropBtn.type = "button";
  pickerDropBtn.className = "admin-db-picker-btn";
  pickerDropBtn.textContent = "+ 데이터베이스 추가";
  pickerDropBtn.disabled = !canManage;
  pickerDropBtn.setAttribute("aria-haspopup", "true");
  pickerDropBtn.setAttribute("aria-expanded", "false");
  const pickerDropList = document.createElement("div");
  pickerDropList.className = "admin-db-picker-list hidden";
  pickerDropList.setAttribute("role", "group");
  pickerDropList.setAttribute("aria-label", "추가할 데이터베이스 선택");
  pickerDropBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const opened = pickerDropList.classList.toggle("hidden") === false;
    pickerDropBtn.setAttribute("aria-expanded", opened ? "true" : "false");
  });
  // 패널 바깥 클릭 시 닫기.
  document.addEventListener("click", function _closePicker(e) {
    if (!pickerWrap.contains(e.target)) {
      pickerDropList.classList.add("hidden");
      pickerDropBtn.setAttribute("aria-expanded", "false");
    }
  });
  pickerWrap.append(pickerDropBtn, pickerDropList);

  // dbpicker-layout-stability(2026-08-12, 사용자 보고): **picker 를 등록 목록보다 앞에 붙인다.**
  //  종전 순서([목록] → [picker])에서는 체크박스 하나를 켤 때마다 redrawChips() 가 위쪽 목록에
  //  행을 더해, 그 높이(실측 ~38px = 한 행보다 크다)만큼 열려 있는 드롭다운이 통째로 아래로
  //  밀렸다. 커서는 그대로인데 항목만 내려가므로 연속 체크가 **다른 DB 를 누르는** 오클릭이
  //  된다(해제는 반대로 위로 당김). 재구성 대상을 picker 뒤에 두면 흐름상 picker 위쪽이 변하지
  //  않아 밀림이 구조적으로 0 이다 — 스크롤 보정 같은 사후 계산이 필요 없고, 스크롤 위치가
  //  0 이라 아래로 당길 여지가 없는 경우(보정이 원리적으로 실패하는 구간)에도 성립한다.
  //  회귀 잠금: tests/headless/verify_dbpicker_layout_stability.py (L1~L4·L6a).
  dbEditorWrap.appendChild(pickerWrap);
  dbEditorWrap.appendChild(chipWrap);

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
      // §59(ADR-025): AI 분류 제안 — 규칙 미귀속 pending(RuleId NULL·reason 'ai_suggest:<conf>').
      //   즉시 승인/거부(스테이징 아님 — 서버 product.manage 게이트 + 감사 기록). 승인 시 Source='ai'.
      const aiPend = ((data && data.orphan_pending) || []).filter((p) => String(p.reason || "").startsWith("ai_suggest"));
      if (aiPend.length) {
        const aiWrap = document.createElement("div"); aiWrap.className = "cov-db-rule-card cov-ai-suggest";
        const aiHead = document.createElement("div"); aiHead.className = "cov-db-rule-summary";
        aiHead.textContent = `✨ AI 분류 제안 · ${aiPend.length}건 (분석 기반 — 승인 시 접근DB 반영)`;
        aiWrap.appendChild(aiHead);
        const aiBase = `/api/admin/products/${product.id}/datasources/${encodeURIComponent(String(_editDsKey || "").trim().toLowerCase())}/ai-suggestions`;
        aiPend.forEach((p) => {
          const row = document.createElement("div"); row.className = "cov-db-rule-pending-row";
          const nm = document.createElement("span"); nm.className = "cov-db-rule-pending-name";
          const m = /^ai_suggest:([0-9.]+)(?:\|(.*))?$/.exec(String(p.reason || ""));
          const conf = m ? Number(m[1]) : NaN;
          nm.textContent = p.schema_name + (Number.isFinite(conf) ? ` (신뢰도 ${Math.round(conf * 100)}%)` : "");
          if (m && m[2]) nm.title = `분류 근거: ${m[2]}`;   // 패널 NIT: LLM 근거를 승인자에게 노출
          const ap = document.createElement("button"); ap.type = "button"; ap.className = "cov-db-rule-save"; ap.textContent = "승인";
          const rj = document.createElement("button"); rj.type = "button"; rj.className = "cov-db-rule-del"; rj.textContent = "거부";
          const act = async (path) => {
            ap.disabled = rj.disabled = true;
            try { await apiFetch(`${aiBase}/${path}`, { method: "POST", body: JSON.stringify({ schemas: [p.schema_name] }) }); }
            catch (e) { try { showToast(`AI 제안 ${path === "approve" ? "승인" : "거부"} 실패: ` + (e.message || "오류"), "error"); } catch (_) {} }
            _renderRuleEditor();
          };
          ap.addEventListener("click", () => act("approve"));
          rj.addEventListener("click", () => act("reject"));
          row.append(nm, ap, rj);
          aiWrap.appendChild(row);
        });
        cardsWrap.appendChild(aiWrap);
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
    // dbpicker-layout-stability: 배너를 picker **아래**(등록 목록 바로 위)에 단다. picker 위에
    //  달면 연결 상태가 비동기로 바뀔 때마다 picker 가 밀려 같은 결함이 다른 경로로 되살아난다.
    //  의미상으로도 이 배너는 "DB 목록이 왜 비었나" 를 설명하므로 목록 바로 위가 제자리다.
    host.insertBefore(note, chipWrap);
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
        } catch (e) {
          // ds-conn-test: 429(쿨다운)는 실패가 아니라 재테스트 간격 제한 — 중립 토스트.
          if (e && e.status === 429) showToast(e.message || "잠시 후 다시 시도해 주세요.", false);
          else showToast(`'${b.datasource_key}' 연결 테스트 오류: ${e.message || "실패"}`, true);
        }
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
        // dbpicker-layout-stability: picker 가 accordion **위**로 올라갔다 — 방향 지시어 정합
        //  (빈 상태에서 유일한 진입점이 위에 있는데 "아래에서" 라고 가리키면 길을 잘못 안내한다).
        none.textContent = "바인딩된 데이터소스 없음 — 기본 단일 MySQL. 위 '+ 데이터소스 추가' 에서 선택하세요.";
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
        // dbpicker-layout-stability: 체크 재동기화·↻ 새로고침마다 통째로 다시 그리므로 드롭다운
        //  내부 스크롤이 맨 위로 튄다(DB picker 와 동일 규약으로 보존).
        const _keepScrollTop = addList.scrollTop;
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
        addList.scrollTop = _keepScrollTop;   // 재구성 전 위치 복원(브라우저가 새 scrollHeight 로 clamp).
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
      // dbpicker-layout-stability: DB picker 와 **같은 결함 클래스** — 체크 시 _afterBindChange
      //  → _renderDsAccordion() 이 위쪽 accordion 을 재구성해(행 추가/제거 + 편집기 이동) 아래의
      //  이 목록이 밀렸다(실측 42px). 재구성 대상(accordion) 앞에 두어 밀림을 0 으로 만든다.
      //  복제된 결함은 한 곳만 고치면 다른 표면에서 되살아나므로 두 picker 를 같은 규약으로 묶는다.
      //  회귀 잠금: tests/headless/verify_dbpicker_layout_stability.py (L5·L6b).
      dbSection.insertBefore(addRow, dsAccordion);
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

// 생성 흐름의 미완성 입력. 어느 단계에서 취소해도 **다음 호출에 되살린다** — 4단계째에서
// 취소 한 번에 이미 작성한 설명(최대 255자)까지 사라지던 문제(적대 검증 P1). 이 캐시는
// pending 스토어가 아니다: 서버에 아무것도 만들지 않으며 새로고침하면 사라진다.
let _newProductDraft = { key: "", name: "", description: "" };

function startNewProduct() {
  const draft = _newProductDraft;
  const keyRaw = window.prompt("Product Key (A-Z0-9_, 32자 이내)", draft.key || "");
  if (keyRaw === null) return;                       // 취소 — 초안은 보존
  const key = String(keyRaw).trim().toUpperCase();
  if (!key) return;
  draft.key = key;
  if (!/^[A-Z][A-Z0-9_]{0,31}$/.test(key)) {
    showToast("Key 형식 오류 — A-Z/0-9/_ 만, 영문 대문자로 시작", true);
    return;
  }
  const nameRaw = window.prompt(`표시 이름 (${PRODUCT_NAME_MAX}자 이내)`, draft.name || key);
  if (nameRaw === null) return;
  const name = String(nameRaw).trim();
  if (!name) return;
  draft.name = name;
  if (name.length > PRODUCT_NAME_MAX) {
    showToast(`표시 이름은 ${PRODUCT_NAME_MAX}자 이내여야 합니다 (현재 ${name.length}자)`, true);
    return;
  }
  // ITEM-03 / E-09b: 설명 입력을 생성 흐름에 넣는다(종전엔 항상 빈 문자열로 전송돼 생성
  //   직후 상세에서 다시 입력해야 했다). 상한 초과분은 **자동으로 자르지 않고** 입력값을
  //   보존한 채 다시 묻는다 — 무엇이 잘렸는지 알 수 없는 무음 절단을 만들지 않는다.
  let description = draft.description || "";
  for (;;) {
    const raw = window.prompt(`설명 (선택 · ${PRODUCT_DESCRIPTION_MAX}자 이내)`, description);
    if (raw === null) return;  // 취소 = 생성 중단 (초안은 보존 — 다시 열면 그대로 채워진다)
    description = String(raw).trim();
    draft.description = description;
    if (description.length <= PRODUCT_DESCRIPTION_MAX) break;
    showToast(`설명은 ${PRODUCT_DESCRIPTION_MAX}자 이내여야 합니다 (현재 ${description.length}자)`, true);
  }
  // ITEM-03 (DQA-03): 「비공개」 = `DefaultRoleAccess=0` — 어떤 역할에도 접근이 자동
  //   부여되지 않고, 서버가 같은 트랜잭션에서 **생성자 계정에만** 접근 권한을 넣는다.
  //   인가 경계 입력이므로 인식 못한 답을 임의 해석하지 않고 다시 묻는다(조용한 오독 금지).
  //   ⚠️ 되돌릴 수 없는 선택이다 — 공개로 만들면 전 역할에 grant 가 이미 나가므로 나중에
  //   토글을 꺼도 그 grant 는 사라지지 않는다. 그래서 (a) 인식 못한 답을 임의 해석하지 않고
  //   다시 묻고, (b) 확정 직전에 무엇이 만들어지는지 한 번 더 보여 준다.
  let defaultRoleAccess = true;
  for (;;) {
    const raw = window.prompt(
      "접근 범위 — '공개' 또는 '비공개' 입력\n\n공개: 모든 역할이 접근\n비공개: 나만 접근 (뒤에 개별 부여)",
      "공개",
    );
    if (raw === null) return;
    const answer = String(raw).trim();
    if (/^(공개|public|pub|o)$/i.test(answer)) { defaultRoleAccess = true; break; }
    if (/^(비공개|private|priv|p|x)$/i.test(answer)) { defaultRoleAccess = false; break; }
    showToast("'공개' 또는 '비공개' 로 입력해 주세요.", true);
  }
  if (!window.confirm(
    `${key} 를 ${defaultRoleAccess ? "공개(모든 역할 접근)" : "비공개(나만 접근)"} 로 만듭니다.\n\n` +
    "접근 범위는 생성 후 되돌릴 수 없습니다. 계속할까요?"
  )) return;
  apiFetch("/api/admin/products", {
    method: "POST",
    body: JSON.stringify({
      product_key: key,
      name,
      description,
      default_role_access: defaultRoleAccess,
    }),
  })
    .then(async (payload) => {
      adminState.selectedProductId = Number(payload.product_id);
      _newProductDraft = { key: "", name: "", description: "" };   // 성공 — 초안 비움
      showToast(defaultRoleAccess
        ? "제품을 생성했습니다."
        : "비공개 제품을 생성했습니다 — 지금은 나만 접근할 수 있습니다.");
      await loadAdminData();
    })
    .catch((error) => {
      showToast(error.message || "생성 실패", true);
    });
}

export { filteredProducts, renderProductList, renderProductDetail, startNewProduct, loadProductInsightCoverage, _isProductCoverageLoading };
