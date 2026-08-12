// feature-0038 Cycle 5 — 데이터소스 pane (관리 콘솔 > 제품 > 데이터소스: CRUD·bulk·
//   연결상태/insight health·엔진 카탈로그·폼). admin.js 구 L5591–6368 에서 byte-동치 이동
//   (본문 무수정 — ITEM-P5b).
import {
  adminState, apiFetch, can, showToast, $, formatDateTime,
  loadAdminData, entityUnit, applyShiftRangeSelect, confirmBulkAction,
  renderCrossPageBanner, actionLabel,
  _probeDatasourceConn, _paintDsConnDot,
} from "../admin.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

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
  // perm-atomic-split: '+ 새 데이터소스' 노출 = 생성(create) 원자 게이트.
  const canManage = can("datasource.create");
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
  const qv = searchVariants(adminState._dsSearch);
  return qv.length
    ? dsList.filter((ds) => matchesAnyVariant((ds.key || "").toLowerCase(), qv)
                         || matchesAnyVariant((ds.host || "").toLowerCase(), qv))
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

  // perm-atomic-split: bulk 액션별 원자 게이트 — 인사이트 토글=수정(update), 삭제=삭제(delete).
  if (can("datasource.update")) {
    bar.appendChild(makeBtn("인사이트 탐색 켜기", () => bulkDatasourceSetInsight(true)));
    bar.appendChild(makeBtn("인사이트 탐색 끄기", () => bulkDatasourceSetInsight(false)));
  }
  if (can("datasource.delete")) {
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
  // perm-atomic-split: 상세 패널 액션별 원자 게이트 — 수정/인사이트 토글=update, 삭제=delete, 연결 테스트=test.
  const canManage = can("datasource.update");
  const canDsDelete = can("datasource.delete");
  const canDsTest = can("datasource.test");
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
    } catch (e) {
      // ds-conn-test: 429(쿨다운)는 실패가 아니라 재테스트 간격 제한 — 중립 토스트.
      if (e && e.status === 429) showToast(e.message || "잠시 후 다시 시도해 주세요.", false);
      else showToast(e.message || "테스트 실패", true);
    }
    finally { testBtn.disabled = false; testBtn.textContent = prev; }
  });
  if (canDsTest) actions.appendChild(testBtn);

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
    actions.append(editBtn);
    if (canDsDelete) {
      const delBtn = document.createElement("button");
      delBtn.className = "btn-danger"; delBtn.textContent = "삭제";
      delBtn.addEventListener("click", () => _dsDelete(ds.key));
      actions.append(delBtn);
    }
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

export { renderDatasourcesPane, _dsFiltered, _dsRenderList };
