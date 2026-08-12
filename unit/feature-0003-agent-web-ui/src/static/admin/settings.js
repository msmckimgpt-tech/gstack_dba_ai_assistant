// feature-0038 Cycle 3 — 설정 pane (관리 콘솔 > 시스템 > 설정: 프롬프트·런타임·추론예산·
//   red-team·성능/병렬 패널). admin.js 구 L6374–7235 에서 byte-동치 이동 (본문 무수정 —
//   ITEM-P5b, unit/feature-0038-frontend-modularization). 순환 import 패턴은 graph/·admin/
//   선례와 동일: 함수는 호출 시점 참조라 TDZ-안전, 배너 주석·상태 초기화(adminState.settings=…)
//   는 admin.js 잔류. mountGuidanceRegistryPanel 은 본 모듈이 export 하고 admin.js 가
//   re-export (aiops.js 의 "../admin.js" import 계약 보존).
import {
  adminState, apiFetch, can, $,
  bindPaneSubtabs, buildSystemPromptEditor, refreshPendingUI, showGuidanceDetail,
} from "../admin.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

const SETTINGS_PANEL_MOUNTERS = {
  // feature-0021 console-subtabs(2026-07-16): 프롬프트 = 단일 패널 + 서브탭[전역/지침/스킬].
  "prompts": mountPromptsPanel,
  // feature-0018: 실행 타임아웃 / 모델별 추론 예산 — 각자 전용 UI, 레거시 admin-settings-panel 정합.
  "runtime-timeouts": mountRuntimeTimeoutsPanel,
  "model-thinking-budgets": mountModelThinkingBudgetsPanel,
  // feature-0021: 자가 적대(red-team) 리뷰 · 메모리 노트 운영 값 (runtime_settings redteam 그룹).
  "redteam-review": mountRedteamReviewPanel,
  // feature-0025: 워커 성능·병렬 처리 운영 값 (runtime_settings performance 그룹).
  "performance-parallelism": mountPerformanceParallelismPanel,
};

// feature-0021 console-subtabs: 프롬프트 패널 — 서브탭[전역 시스템 프롬프트 | 작동 지침 | 스킬].
// 각 서브탭 첫 활성 시 기존 mounter 를 lazy 호출. 전역 시스템 프롬프트는 항상 표시(편집 권한은
// 패널 내부 buildSystemPromptEditor 가 게이팅), 지침/스킬은 조회.
function mountPromptsPanel() {
  const panel = document.querySelector('.admin-settings-panel[data-settings-panel="prompts"]');
  if (!panel) return;
  bindPaneSubtabs(panel, "prompt", (key) => {
    if (key === "global") mountGlobalPromptPanel();
    else if (key === "guidance") mountGuidanceRegistryPanel("guidancePanelMount", "guidance");
    else if (key === "skills") mountGuidanceRegistryPanel("skillsPanelMount", "skill");
  });
}

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
  const qv = searchVariants(query);
  list.querySelectorAll(".admin-list-row[data-settings-tab]").forEach((row) => {
    if (!qv.length) {
      row.style.display = "";
      return;
    }
    const haystack = [
      row.getAttribute("data-settings-tab") || "",
      row.getAttribute("data-settings-group") || "",
      row.getAttribute("data-settings-keywords") || "",
      row.textContent || "",
    ].join(" ").toLowerCase();
    row.style.display = matchesAnyVariant(haystack, qv) ? "" : "none";
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
const RS_REASONING_PREFIX = "reasoning_budget:";  // reasoning_budget:{model}:{level}
const RS_AGENT_MAX_PREFIX = "agent_max_output:";  // 모델별 대화 총 출력(max_tokens)
// feature-0025: performance 그룹 키 미러(= runtime_settings._PERF_SPECS). commit-bar 의 '성능·병렬 처리'
// 서브탭 nav dot 라우팅 전용(prefix 공유 없음). 백엔드가 SSOT — 키 추가 시 함께 갱신.
const RS_PERF_KEYS = new Set([
  "AGENT_NODE_ANALYSIS_CONCURRENCY", "AGENT_NODE_ANALYSIS_BATCH_PER_TICK", "AGENT_INSIGHT_WORKER_TICK_SEC",
  "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY", "AGENT_METADATA_CLUSTER_INTERVAL_SEC",
  "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS", "AGENT_ASK_WORKER_CONCURRENCY", "AGENT_ASK_WORKER_IDLE_POLL_MS",
  "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS", "AGENT_KB_EMBEDDING_INTERVAL_SEC",
]);

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
  const r = $("redteamReviewMount");
  if (r && adminState.settings.mountedPanels.has("redteam-review")) renderRedteamReviewSettings(r);
  const p = $("performanceParallelismMount");
  if (p && adminState.settings.mountedPanels.has("performance-parallelism")) renderPerformanceParallelism(p);
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
      if (opts && typeof opts.onChange === "function") opts.onChange();
    });
    resetBtn.addEventListener("click", () => {
      const pend = adminState.pending.runtimeSettings.get(item.key);
      if (pend) {
        // 되돌리기: 예약 취소 + 서버 상태 표시 복원.
        setRuntimeSettingPending(item.key, null);
        input.value = noOverrideEmpty ? "" : String(item.effective);
        refresh();
        if (opts && typeof opts.onChange === "function") opts.onChange();
        return;
      }
      if (!item.has_override) return;  // 복원할 override 없음
      // 기본값 복원(DELETE) 예약.
      setRuntimeSettingPending(item.key, RS_RESET);
      if (emptyWhenNoOverride) { input.value = ""; input.placeholder = String(item.default); }
      else input.value = String(item.default);
      refresh();
      if (opts && typeof opts.onChange === "function") opts.onChange();
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

// feature-0025: 워커 성능·병렬 처리 패널 — runtime_settings 의 performance 그룹(그래프 노드 분석·
// cluster_label·사용자 답변·임베딩)을 실행 타임아웃 패널과 동일한 정렬 grid + 카테고리 그룹으로 렌더.
// buildRuntimeSettingRow 공용(즉시/재배포 반영 배지, pending 예약, commit-bar 적용). read/write 게이트 동일.
async function mountPerformanceParallelismPanel() {
  const mount = $("performanceParallelismMount");
  if (!mount) return;
  if (!can("system.runtime.read")) {
    rsErrorPlaceholder(mount, "런타임 설정 조회 권한이 없습니다.");
    return;
  }
  await renderPerformanceParallelism(mount);
}

async function renderPerformanceParallelism(mount) {
  rsErrorPlaceholder(mount, "불러오는 중…");
  let data;
  try {
    data = await apiFetch(RUNTIME_SETTINGS_ENDPOINT);
  } catch (err) {
    rsErrorPlaceholder(mount, `조회 실패: ${err.message || err}`);
    return;
  }
  const canWrite = can("system.runtime.write");
  const items = Array.isArray(data.performance) ? data.performance : [];
  if (!items.length) { rsErrorPlaceholder(mount, "등록된 성능·병렬 항목이 없습니다."); return; }
  mount.innerHTML = "";
  const panel = document.createElement("div");
  panel.className = "rs-panel";
  // category 순서 보존 그룹핑(그래프 노드 분석 → cluster_label → 사용자 답변 처리 → 지식베이스 임베딩).
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

// (모델, 레벨) thinking 예산을 모델 총 출력 대비 [추론 ↔ 본문] 슬라이더로 배분한다.
// 저장값은 절대 thinking budget(reasoning_budget:{model}:{level}) 하나뿐이며, 본문(content)은
// (총 − thinking) 파생 표시라 별도 저장 필드가 없다. getTotal(): 이 모델의 현재 총 출력(pending 반영).
function buildBudgetSliderRow(item, canWrite, getTotal) {
  const CONTENT_FLOOR = 1024;  // 본문 최소 확보(agent_core clamp 여유와 정합)
  const row = document.createElement("div");
  row.className = "rs-row rs-row--slider";
  row.dataset.settingKey = item.key;

  const label = document.createElement("div");
  label.className = "rs-row-label";
  const name = document.createElement("span");
  name.textContent = item.label || item.key;
  label.append(name, rsApplyBadge(item.apply_mode));

  const desc = document.createElement("div");
  desc.className = "rs-row-desc";
  desc.textContent = item.description || "";
  desc.title = desc.textContent;

  const control = document.createElement("div");
  control.className = "rs-row-control rs-slider-control";
  const slider = document.createElement("input");
  slider.type = "range";
  slider.className = "rs-slider";
  slider.min = String(item.minimum);
  slider.step = "256";
  slider.setAttribute("aria-label", `${item.label || item.key} 추론 예산`);
  const num = document.createElement("input");
  num.type = "number";
  num.className = "rs-input rs-input--compact";
  num.min = String(item.minimum);
  num.max = String(item.maximum);
  num.step = "1";
  const unit = document.createElement("span");
  unit.className = "rs-unit";
  unit.textContent = "tokens";
  if (!canWrite) { slider.disabled = true; num.disabled = true; }
  control.append(slider, num, unit);

  const split = document.createElement("div");
  split.className = "rs-split-bar";
  const segThink = document.createElement("div");
  segThink.className = "rs-split-seg rs-split-think";
  segThink.textContent = "추론";
  const segContent = document.createElement("div");
  segContent.className = "rs-split-seg rs-split-content";
  segContent.textContent = "본문";
  split.append(segThink, segContent);

  const meta = document.createElement("div");
  meta.className = "rs-row-meta";
  const status = document.createElement("span");
  status.className = "rs-status";
  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.className = "rs-reset";
  resetBtn.textContent = "기본값";
  resetBtn.title = `기본값(${item.default} tokens)으로 되돌립니다.`;
  meta.append(status, resetBtn);

  row.append(label, control, split, desc, meta);

  const pendVal = () => {
    const p = adminState.pending.runtimeSettings.get(item.key);
    return p ? p.value : null;  // number | RS_RESET | null
  };
  const sliderMax = () => Math.max(item.minimum, Math.min(item.maximum, getTotal() - CONTENT_FLOOR));
  const currentThinking = () => {
    const p = pendVal();
    if (p === RS_RESET) return item.default;
    if (typeof p === "number") return p;
    return item.effective;
  };

  function renderSplit(previewThink) {
    const total = getTotal();
    const think = Math.max(item.minimum, Math.min(previewThink == null ? currentThinking() : previewThink, sliderMax()));
    const content = Math.max(0, total - think);
    const thinkPct = total > 0 ? Math.round((think / total) * 100) : 0;
    segThink.style.flexGrow = String(Math.max(1, think));
    segContent.style.flexGrow = String(Math.max(1, content));
    segThink.title = `추론 ${think.toLocaleString()} tokens (${thinkPct}%)`;
    segContent.title = `본문 ${content.toLocaleString()} tokens (${100 - thinkPct}%)`;
  }

  function refresh() {
    num.classList.remove("is-invalid");
    const p = pendVal();
    row.classList.toggle("is-pending", p != null);
    const v = currentThinking();
    slider.max = String(sliderMax());
    slider.value = String(Math.max(item.minimum, Math.min(v, sliderMax())));
    num.value = String(v);
    renderSplit();
    if (p === RS_RESET) {
      status.textContent = "미저장 · 기본값 복원"; status.className = "rs-status is-pending";
      resetBtn.textContent = "되돌리기"; resetBtn.hidden = !canWrite;
    } else if (p != null) {
      status.textContent = "미저장 변경"; status.className = "rs-status is-pending";
      resetBtn.textContent = "되돌리기"; resetBtn.hidden = !canWrite;
    } else if (item.has_override) {
      status.textContent = `사용자 지정 · 기본 ${item.default} tokens`; status.className = "rs-status is-override";
      resetBtn.textContent = "기본값"; resetBtn.hidden = !canWrite;
    } else {
      status.textContent = `기본값 ${item.default} tokens`; status.className = "rs-status";
      resetBtn.hidden = true;
    }
  }

  function commit(v) {
    const clamped = Math.max(item.minimum, Math.min(Math.trunc(v), sliderMax()));
    if (clamped === item.effective) setRuntimeSettingPending(item.key, null);
    else setRuntimeSettingPending(item.key, clamped);
    refresh();
  }

  refresh();

  if (canWrite) {
    slider.addEventListener("input", () => {
      const v = Math.max(item.minimum, Math.min(Number(slider.value), sliderMax()));
      num.value = String(v);
      renderSplit(v);
    });
    slider.addEventListener("change", () => commit(Number(slider.value)));
    num.addEventListener("change", () => {
      const raw = num.value.trim();
      if (raw === "") { setRuntimeSettingPending(item.key, null); refresh(); return; }
      const val = Math.trunc(Number(raw));
      if (!Number.isFinite(val)) { refresh(); return; }
      // 실효 상한은 현재 총 출력 대비 sliderMax(= min(native-1024, 총-1024)) — 정적 native 상한이
      // 아니라 이 동적 상한으로 검증해 "저장 후 조용히 clamp" 되는 혼란(리뷰 NIT)을 방지.
      const hi = sliderMax();
      if (val < item.minimum || val > hi) {
        num.classList.add("is-invalid");
        status.textContent = `허용 범위 ${item.minimum}~${hi} (총 출력 ${getTotal().toLocaleString()} 대비)`;
        status.className = "rs-status is-invalid";
        return;
      }
      commit(val);
    });
    resetBtn.addEventListener("click", () => {
      const p = pendVal();
      if (p != null) { setRuntimeSettingPending(item.key, null); refresh(); return; }
      if (!item.has_override) return;
      setRuntimeSettingPending(item.key, RS_RESET);
      refresh();
    });
  } else {
    resetBtn.hidden = true;
  }

  // 총 출력이 바뀌면 슬라이더 상한/본문 파생을 다시 그린다(카드가 호출).
  row._rsRecompute = refresh;
  return row;
}

/* ── feature-0021 console-ia: 작동 지침 / 스킬 조회 패널 (설정 > 프롬프트) ─────────
 * /api/admin/reasoning/guidance?kind=guidance|skill 의 레지스트리를 progressive disclosure
 * (목록은 메타만, 클릭 시 ?key= 로 본문 lazy 로드)로 조회 전용 렌더. 권한 게이트는
 * 백엔드(system_prompt.global.read) — FE 는 조회 실패 시 안내. */
export async function mountGuidanceRegistryPanel(mountId, kind) {
  const mount = $(mountId);
  if (!mount) return;
  if (!can("system_prompt.global.read")) {
    mount.innerHTML = '<div class="admin-detail-empty">프롬프트 지침/스킬 조회 권한이 없습니다.</div>';
    return;
  }
  mount.innerHTML = '<div class="admin-detail-empty">불러오는 중…</div>';
  let data;
  try {
    data = await apiFetch("/api/admin/reasoning/guidance?kind=" + encodeURIComponent(kind));
  } catch (err) {
    mount.innerHTML = '<div class="admin-detail-empty">조회 실패: ' + String((err && err.message) || err).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])) + "</div>";
    return;
  }
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const items = Array.isArray(data && data.items) ? data.items : [];
  const rows = items.map((g) =>
    `<button type="button" class="reasoning-guidance-row" data-guidance-key="${esc(g.key)}">
      <span class="reasoning-guidance-name">${esc(g.name)}</span>
      <span class="reasoning-guidance-desc">${esc(g.description)}</span>
      <span class="reasoning-guidance-meta">${esc(g.injection || "")}${g.chars != null ? " · " + esc(g.chars) + "자" : ""}</span>
    </button>`
  ).join("");
  const detailId = mountId + "Detail";
  mount.innerHTML =
    '<div class="reasoning-guidance-list">' + (rows || '<div class="admin-detail-empty">항목이 없습니다.</div>') + "</div>" +
    '<div class="reasoning-guidance-detail" id="' + detailId + '" hidden></div>';
  mount.querySelectorAll("[data-guidance-key]").forEach((btn) => {
    btn.addEventListener("click", () => showGuidanceDetail(btn.getAttribute("data-guidance-key"), detailId));
  });
}

/* ── feature-0021: 자가 적대(red-team) 리뷰 · 메모리 노트 운영 값 패널 ─────────
 * runtime_settings 의 redteam 그룹(REDTEAM_*)을 실행 타임아웃 패널과 동일한 정렬 grid
 * 행으로 렌더 — 편집은 pending 예약, 적용은 하단 공용 commit-bar (기존 배선 재사용). */
async function mountRedteamReviewPanel() {
  const mount = $("redteamReviewMount");
  if (!mount) return;
  if (!can("system.runtime.read")) {
    rsErrorPlaceholder(mount, "런타임 설정 조회 권한이 없습니다.");
    return;
  }
  await renderRedteamReviewSettings(mount);
}

async function renderRedteamReviewSettings(mount) {
  rsErrorPlaceholder(mount, "불러오는 중…");
  let data;
  try {
    data = await apiFetch(RUNTIME_SETTINGS_ENDPOINT);
  } catch (err) {
    rsErrorPlaceholder(mount, `조회 실패: ${err.message || err}`);
    return;
  }
  const canWrite = can("system.runtime.write");
  const items = Array.isArray(data.redteam) ? data.redteam : [];
  if (!items.length) { rsErrorPlaceholder(mount, "등록된 자가 리뷰 항목이 없습니다."); return; }
  mount.innerHTML = "";
  const panel = document.createElement("div");
  panel.className = "rs-panel";
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
  const totals = Array.isArray(data.agent_max_outputs) ? data.agent_max_outputs : [];
  const models = Array.isArray(data.model_thinking_budgets) ? data.model_thinking_budgets : [];
  const levels = Array.isArray(data.reasoning_budgets) ? data.reasoning_budgets : [];
  // adaptive(Sonnet 5) 계열: budget_tokens 미적용(effort 로 제어) → 죽은 예산 슬라이더 대신 guide-note.
  const adaptiveModels = new Set(Array.isArray(data.adaptive_models) ? data.adaptive_models : []);
  if (!totals.length && !models.length && !levels.length) {
    rsErrorPlaceholder(mount, "extended thinking 을 지원하는 모델이 카탈로그에 없습니다.");
    return;
  }
  mount.innerHTML = "";
  const panel = document.createElement("div");
  panel.className = "rs-panel rs-budget-panel";

  // 모델 순서 = agent_max_outputs(카탈로그 순). 각 모델의 rows 를 모은다.
  const order = [];
  const byModel = new Map();
  const ensure = (m) => {
    if (!byModel.has(m)) { byModel.set(m, { total: null, model: [], levels: [] }); order.push(m); }
    return byModel.get(m);
  };
  for (const it of totals) ensure(it.model).total = it;
  for (const it of models) ensure(it.model).model.push(it);
  for (const it of levels) ensure(it.model).levels.push(it);

  // 이 모델의 현재 총 출력(agent_max_output; pending 반영) — 슬라이더가 참조.
  const totalRow = new Map();
  for (const it of totals) totalRow.set(it.model, it);
  const currentTotal = (m) => {
    const t = totalRow.get(m);
    if (!t) return 20000;
    const p = adminState.pending.runtimeSettings.get(RS_AGENT_MAX_PREFIX + m);
    if (p && p.value === RS_RESET) return t.default;
    if (p && typeof p.value === "number") return p.value;
    return t.effective;
  };

  const levelRank = { low: 0, high: 1, max: 2 };

  for (const m of order) {
    const bucket = byModel.get(m);
    const modelLabel = (bucket.total && bucket.total.label) || (bucket.model[0] && bucket.model[0].label) || m;

    const card = document.createElement("details");
    card.className = "permission-group rs-budget-card";
    card.open = true;
    const head = document.createElement("summary");
    head.className = "permission-group-head";
    const htitle = document.createElement("span");
    htitle.className = "permission-group-title";
    htitle.textContent = modelLabel;
    const hcount = document.createElement("span");
    hcount.className = "permission-group-counts rs-card-total";
    head.append(htitle, hcount);
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "rs-budget-card-body";

    const sliderRows = [];
    const updateHead = () => { hcount.textContent = `라운드당 ${currentTotal(m).toLocaleString()} tokens`; };

    // ① 라운드당 출력(max_tokens) — 변경 시 하위 슬라이더 상한/본문 파생 재계산.
    if (bucket.total) {
      const sub = document.createElement("div");
      sub.className = "rs-subgroup-title";
      sub.textContent = "라운드(단계)당 출력 (max_tokens · 추론+본문 · 다회차면 회차마다 적용)";
      const list = document.createElement("div");
      list.className = "rs-list";
      list.appendChild(buildRuntimeSettingRow(bucket.total, canWrite, {
        onChange: () => { updateHead(); sliderRows.forEach((r) => r._rsRecompute && r._rsRecompute()); },
      }));
      body.append(sub, list);
    }

    if (adaptiveModels.has(m)) {
      // adaptive(Sonnet 5): budget_tokens 미적용 — 죽은 ②③ 슬라이더 대신 guide-note.
      // 추론 강도는 대화 화면의 '추론 강도' 선택기가 Anthropic effort 로 직접 제어한다.
      const gsub = document.createElement("div");
      gsub.className = "rs-subgroup-title";
      gsub.textContent = "추론 강도 (adaptive thinking)";
      const gnote = document.createElement("div");
      gnote.className = "rs-readonly-note";
      gnote.textContent = "이 모델은 adaptive thinking 계열입니다 — 추론 강도는 관리자 예산(토큰)이 아니라 대화 화면의 '추론 강도' 선택이 Anthropic effort 로 직접 제어합니다 (낮음→low · 일반→모델 기본 · 높음→high · 매우 높음→max). 따라서 모델별 thinking budget(토큰) 설정은 적용되지 않아 감췄습니다. 위 '라운드당 출력'만 이 모델에 유효합니다.";
      body.append(gsub, gnote);
    } else {
      // ② 추론 강도별 (추론 ↔ 본문 배분 슬라이더) — budget 계열(Haiku 등)만.
      const explicit = bucket.levels.slice().sort((a, b) => (levelRank[a.level] ?? 9) - (levelRank[b.level] ?? 9));
      if (explicit.length) {
        const sub = document.createElement("div");
        sub.className = "rs-subgroup-title";
        sub.textContent = "추론 강도별 예산 (추론 ↔ 본문 배분)";
        const list = document.createElement("div");
        list.className = "rs-list";
        for (const it of explicit) {
          const r = buildBudgetSliderRow(it, canWrite, () => currentTotal(m));
          sliderRows.push(r);
          list.appendChild(r);
        }
        body.append(sub, list);
      }

      // ③ '일반'(모델 기본) — 선택적 override(비우면 모델 기본 thinking 유지).
      if (bucket.model.length) {
        const sub = document.createElement("div");
        sub.className = "rs-subgroup-title";
        sub.textContent = "일반(모델 기본) thinking budget — 비우면 모델 기본값 유지";
        const list = document.createElement("div");
        list.className = "rs-list";
        for (const it of bucket.model) list.appendChild(buildRuntimeSettingRow(it, canWrite, { emptyWhenNoOverride: true }));
        body.append(sub, list);
      }
    }

    updateHead();
    card.appendChild(body);
    panel.appendChild(card);
  }

  const note = document.createElement("div");
  note.className = "rs-readonly-note";
  note.textContent = canWrite
    ? "값은 추론 한 라운드(단계)당 상한입니다 — 어시스턴트는 한 요청을 다회차로 처리하므로 실제 총량은 대략 (라운드당) × 회차입니다. 라운드당 출력 안에서 추론(thinking)과 본문(content)이 나뉘며, 슬라이더로 추론 비중을 조절하면 본문 여유가 함께 표시됩니다. native 근처로 크게 잡으면 라운드마다 느려져 '에이전트/쿼리 실행 타임아웃'을 넘거나 오히려 처리 회차가 줄 수 있으니, 보수적으로 시작하고 필요 시 타임아웃도 함께 올리세요. 대화 화면의 강도 선택(낮음/높음/매우 높음)이 이 예산을 라운드 단위로 적용하며, '일반'은 모델 기본값을 유지합니다."
    : "조회 전용 — 수정 권한(system.runtime.write)이 없습니다.";
  panel.appendChild(note);
  mount.appendChild(panel);
}

export {
  mountSettingsSections, rerenderRuntimeSettingsPanels,
  rsSaveValue, rsResetValue,
  RS_RESET, RS_MODEL_PREFIX, RS_REASONING_PREFIX, RS_AGENT_MAX_PREFIX, RS_PERF_KEYS,
};
