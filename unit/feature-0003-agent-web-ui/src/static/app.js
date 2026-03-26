const promptBox = document.getElementById("prompt");
const sessionIdEl = document.getElementById("sessionId");
const convIdEl = document.getElementById("conversationId");
const lastDurationEl = document.getElementById("lastDuration");
const conversationCountEl = document.getElementById("conversationCount");
const conversationStatsEl = document.getElementById("conversationStats");
const jumpTimeEl = document.getElementById("jumpTime");
const jumpBtn = document.getElementById("jumpBtn");
const jumpLatestBtn = document.getElementById("jumpLatest");
const scrollLatestBtn = document.getElementById("scrollLatestBtn");
const jumpCalBtn = document.getElementById("jumpCalBtn");
const jumpCalPanel = document.getElementById("jumpCalPanel");
const jumpCalGrid = document.getElementById("jumpCalGrid");
const jumpCalTitle = document.getElementById("jumpCalTitle");
const jumpCalPrev = document.getElementById("jumpCalPrev");
const jumpCalNext = document.getElementById("jumpCalNext");
const jumpCalTimes = document.getElementById("jumpCalTimes");
const jumpCalTimesList = document.getElementById("jumpCalTimesList");
const conversationListEl = document.getElementById("conversationList");
const chatLogEl = document.getElementById("chatLog");
const timelineEl = document.getElementById("chatTimeline");
const runHudEl = document.getElementById("runHud");
const layoutEl = document.querySelector(".layout");
const sideEl = document.querySelector(".side");
const sideToggleEl = document.getElementById("sideToggle");
const toolsToggleEl = document.getElementById("toolsToggle");
const domainBadgeEl = document.getElementById("domainBadge");
const strategyBadgeEl = document.getElementById("strategyBadge");
const toolsDrawerEl = document.getElementById("toolsDrawer");
const toolsCloseEl = document.getElementById("toolsClose");
const apiPanelEl = document.getElementById("apiPanel");
const apiToggleEl = document.getElementById("apiToggle");
const csvPagerDockEl = document.getElementById("csvPagerDock");
const csvPagerPanelEl = document.getElementById("csvPagerPanel");
const apiKeyEncEl = document.getElementById("apiKeyEnc");
const apiKeyPassEl = document.getElementById("apiKeyPass");
const apiModelEl = document.getElementById("apiModel");
const apiModelHintEl = document.getElementById("apiModelHint");
const apiStatusEl = document.getElementById("apiStatus");
const apiKeyPlainEl = document.getElementById("apiKeyPlain");
const apiValidationEl = document.getElementById("apiValidation");
const apiHistoryEl = document.getElementById("apiHistory");
const apiSaveBtn = document.getElementById("apiSave");
const apiClearBtn = document.getElementById("apiClear");
const apiEncryptBtn = document.getElementById("apiEncrypt");
const apiSecureHintEl = document.getElementById("apiSecureHint");
/* 제거된 UI: followup 의도/제약, 전송문 미리보기 — null로 유지하여 기존 가드 호환 */
const followupIntentEl = null;
const followupConstraintsEl = null;
const followupClearEl = null;
const followupApplyOnceEl = null;
const followupLiveEl = null;
const followupAutoInjectEl = null;
const sendPreviewBoxEl = null;
const sendPreviewMetaEl = null;
const sendPreviewTextEl = null;
const dangerModalEl = document.getElementById("dangerModal");
const dangerModalTitleEl = document.getElementById("dangerModalTitle");
const dangerModalTextEl = document.getElementById("dangerModalText");
const dangerModalLabelEl = document.getElementById("dangerModalLabel");
const dangerModalInputEl = document.getElementById("dangerModalInput");
const dangerModalConfirmEl = document.getElementById("dangerModalConfirm");
const dangerModalCancelEl = document.getElementById("dangerModalCancel");
const dangerModalCloseEl = document.getElementById("dangerModalClose");
const restoreModePanelEl = document.getElementById("restoreModePanel");
const restoreModeFileEl = document.getElementById("restoreModeFile");
const restoreContinueBtnEl = document.getElementById("restoreContinueBtn");
const restoreModeClearBtnEl = document.getElementById("restoreModeClearBtn");
const domainDriftPanelEl = document.getElementById("domainDriftPanel");
const domainDriftTextEl = document.getElementById("domainDriftText");
const domainDriftRevertBtnEl = document.getElementById("domainDriftRevert");
const domainDriftCloseBtnEl = document.getElementById("domainDriftClose");
/* 제거된 UI: 지연 Top3 단계 패널 */
const timingPanelEl = null;
const timingMetaEl = null;
const timingListEl = null;
const HISTORY_PAGE_SIZE = 10;
const STATUS_POLL_MS = 2000;
const CHAT_POLL_MS = 3000;
const CONV_POLL_MS = 5000;
const HUD_TICK_MS = 1000;
const TOAST_DURATION_MS = 1800;
let historyLoading = false;
let historyExhausted = false;
let historyOldestId = null;
let historyMoreAvailable = false;
let activeConversationId = "";
let lastRenderedMessageId = null;
let lastRenderedSignature = null;
let activeChatPoller = null;
let activeHudTicker = null;
let currentHistoryMessages = [];
let conversationTotalCount = 0;
const conversationState = new Map();
const conversationPollers = new Map();
const conversationPollCounts = new Map();
const cancelOverrideUntil = new Map();
let modalCopyText = "";
let toastTimer = null;
let dangerModalResolver = null;
let dangerModalReturnFocusEl = null;
let followupManualEdit = false;
let followupApplyArmed = false;
let followupContextConversationId = "";
let currentDomainHint = "";
let currentStrategyHint = "";
let pinnedDomainHint = "";
let pinnedStrategyHint = "";
let localLlmEnabled = false;
let localLlmDefaultModel = "auto";
const recentDurationsMs = [];
const SUGGESTION_CACHE_KEY = "mysql_ai_suggestions_v1";
const SUGGESTION_CACHE_TTL_MS = 1000 * 60 * 60 * 6;
const API_KEY_CACHE_KEY = "mysql_ai_api_key_v3";
const API_KEY_CACHE_LEGACY_KEYS = ["mysql_ai_api_key_v2", "mysql_ai_api_key_v1"];
const API_KEY_HISTORY_KEY = "mysql_ai_api_key_history_v1";
const API_KEY_HISTORY_MAX = 5;
const PINNED_CONTEXT_KEY = "mysql_ai_pinned_context_v1";
const CANCEL_OVERRIDE_MS = 12000;
const TIMING_LOG_PATH = "/shared/logs/timing.log";
const TIMING_LOG_MAX_BYTES = 262144;
const TIMING_PANEL_REFRESH_MS = 7000;
const RECOVERY_FLOW_STEPS = ["오류 감지", "후보 탐색", "검증", "재실행", "결론"];
const FALLBACK_API_VAULT_OPTIONS = {
  default_model: "gpt-5.4-nano",
  public_host: "localhost",
  public_url: "https://localhost",
  requires_secure_context: true,
  models: [
    {
      value: "gpt-5.4",
      label: "gpt-5.4",
      group: "GPT-5",
      description: "최신 GPT-5 base 모델",
    },
    {
      value: "gpt-5-mini",
      label: "gpt-5-mini",
      group: "GPT-5",
      description: "최신 가용 mini alias",
    },
    {
      value: "gpt-5-nano",
      label: "gpt-5-nano",
      group: "GPT-5",
      description: "최신 가용 nano alias",
    },
    {
      value: "gpt-5.3-codex",
      label: "gpt-5.3-codex",
      group: "GPT-5",
      description: "최신 numbered codex 모델",
    },
    {
      value: "gpt-5.3-chat-latest",
      label: "gpt-5.3-chat-latest",
      group: "GPT-5",
      description: "최신 numbered chat-latest 모델",
    },
  ],
};
let apiVaultOptions = FALLBACK_API_VAULT_OPTIONS;
const csvPreviewState = {
  paths: [],
  index: 0,
  loading: false,
  steps: [],
  scrollTop: 0,
  rowLimit: 50,
  sortIndex: null,
  sortDir: 1,
  rawRows: null,
};
const sqlResultModalState = {
  open: false,
  sql: "",
  returnTarget: null,
};
const MISSING_CSV_TOAST = "저장된 CSV 파일이 없습니다.";
const ASSISTANT_PLAIN_TEXT_HINT_RE = /(오류|error|실패|not\s+found|unknown|mcp|syntax|중단|자동\s*복구|취소)/i;
let markdownRenderer = null;
const restoreModeState = {
  active: false,
  file_path: "",
  conversation_id: "",
};
let domainDriftDismissedKey = "";
let timingPanelLastFetchAt = 0;
let timingPanelLastKey = "";

function hasMarkdownRuntime() {
  return Boolean(window.marked && window.DOMPurify);
}

function getMarkdownRenderer() {
  if (markdownRenderer || !window.marked || !window.marked.Renderer) {
    return markdownRenderer;
  }
  markdownRenderer = new window.marked.Renderer();
  markdownRenderer.html = () => "";
  return markdownRenderer;
}

function extractPlainTextFromHtml(html = "") {
  const wrap = document.createElement("div");
  wrap.innerHTML = String(html || "");
  return String(wrap.innerText || wrap.textContent || "")
    .replace(/\u00a0/g, " ")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function sanitizeRawMarkdownSource(source = "") {
  const raw = String(source || "").replace(/\\n/g, "\n").replace(/\\t/g, "\t");
  if (!raw) return "";
  return raw
    .split(/(```[\s\S]*?```)/g)
    .map((part) => {
      if (part.startsWith("```")) return part;
      return part
        .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
        .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
        .replace(/<\/?[A-Za-z][^>]*>/g, (match) =>
          match.replace(/</g, "&lt;").replace(/>/g, "&gt;")
        );
    })
    .join("");
}

function renderMarkdownSource(source = "") {
  const raw = String(source || "").trim();
  if (!raw || !hasMarkdownRuntime()) {
    return { html: "", text: raw };
  }
  const normalized = sanitizeRawMarkdownSource(raw);
  let html = "";
  try {
    html = window.marked.parse(normalized, {
      gfm: true,
      breaks: true,
      renderer: getMarkdownRenderer(),
      headerIds: false,
      mangle: false,
    });
  } catch (err) {
    return { html: "", text: raw };
  }
  const sanitized = window.DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["data-csv-path", "data-csv-label"],
  });
  const wrap = document.createElement("div");
  wrap.innerHTML = sanitized;
  wrap.querySelectorAll("a").forEach((anchor) => {
    const href = String(anchor.getAttribute("href") || "").trim();
    if (!href || /^javascript:/i.test(href)) {
      anchor.removeAttribute("href");
      return;
    }
    // CSV 파일 링크에 data 속성 마킹 (DOM 삽입 후 이벤트 바인딩)
    const csvMatch = href.match(/\/api\/file\?path=(.+\.csv)/i);
    if (csvMatch) {
      anchor.setAttribute("data-csv-path", decodeURIComponent(csvMatch[1]));
      anchor.setAttribute("data-csv-label", anchor.textContent || "CSV 미리보기");
      anchor.removeAttribute("target");
      anchor.removeAttribute("rel");
      return;
    }
    anchor.setAttribute("target", "_blank");
    anchor.setAttribute("rel", "noopener noreferrer");
  });
  const safeHtml = wrap.innerHTML;
  return {
    html: safeHtml,
    text: extractPlainTextFromHtml(safeHtml) || raw,
  };
}

function shouldRenderAssistantMarkdown(role, text = "") {
  if (role !== "assistant") return false;
  const raw = String(text || "").trim();
  if (!raw) return false;
  if (isInternalAssistantContent(raw)) return false;
  if (ASSISTANT_PLAIN_TEXT_HINT_RE.test(raw.slice(0, 120))) return false;
  if (raw.length <= 180 && isQuestionContent(raw)) return false;
  return hasMarkdownRuntime();
}

function hasStructuredMarkdownSource(text = "") {
  const raw = String(text || "");
  if (!raw) return false;
  return /(^|\n)(#{1,6}\s|[-*+]\s|\d+\.\s|\|.+\||```|> )/.test(raw);
}

function createPlainOutputNode(text = "") {
  const content = document.createElement("pre");
  content.className = "output";
  const cleaned = String(text || "").replace(/\\n/g, "\n").replace(/\\t/g, "\t");
  content.textContent = cleaned;
  if (!/[\u2500-\u257f\u2580-\u259f]/.test(text || "")) {
    content.classList.add("wrap");
  }
  return content;
}

function createMarkdownOutputNode(html = "", steps = []) {
  const content = document.createElement("div");
  content.className = "answer-markdown";
  content.innerHTML = String(html || "");
  // CSV 링크(data-csv-path)를 미리보기 모달 버튼으로 변환
  // fallback: data 속성이 없는 경우 href 패턴으로 직접 탐색
  if (!content.querySelectorAll("a[data-csv-path]").length) {
    content.querySelectorAll("a").forEach((anchor) => {
      const href = String(anchor.getAttribute("href") || "");
      const m = href.match(/\/api\/file\?path=(.+\.csv)/i);
      if (m) {
        anchor.setAttribute("data-csv-path", decodeURIComponent(m[1]));
        anchor.setAttribute("data-csv-label", anchor.textContent || "CSV 미리보기");
      }
    });
  }
  const safeSteps = Array.isArray(steps) ? steps : [];
  content.querySelectorAll("a[data-csv-path]").forEach((anchor) => {
    const csvPath = anchor.getAttribute("data-csv-path");
    const labelText = anchor.getAttribute("data-csv-label") || "CSV 미리보기";
    const btnWrap = document.createElement("div");
    btnWrap.className = "csv-inline-link";
    const previewBtn = document.createElement("button");
    previewBtn.type = "button";
    previewBtn.className = "mini csv-preview-inline-btn";
    previewBtn.textContent = labelText;
    previewBtn.addEventListener("click", () => {
      openCsvPreviewModal([csvPath], 0, safeSteps);
    });
    btnWrap.appendChild(previewBtn);
    anchor.replaceWith(btnWrap);
  });
  return content;
}

function syncAnswerExpandedState(messageEl, detailEl) {
  if (!messageEl || !detailEl) return;
  if (!detailEl.open) {
    messageEl.classList.remove("msg--answer-expanded");
    return;
  }
  const bubble = messageEl.querySelector(".bubble");
  const messageRect = messageEl.getBoundingClientRect();
  const bubbleRect = bubble ? bubble.getBoundingClientRect() : null;
  const widthRatio =
    bubbleRect && messageRect
      ? Math.max(0, bubbleRect.width / Math.max(messageRect.width, 1))
      : 1;
  messageEl.classList.toggle("msg--answer-expanded", widthRatio <= 0.82);
}

function formatSql(sql) {
  const raw = String(sql || "").trim();
  if (!raw) return "";
  if (raw.includes("\n")) return raw;
  const segments = [];
  let buf = "";
  let quote = "";
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (quote) {
      buf += ch;
      if (ch === quote) {
        if (quote === "'" && raw[i + 1] === "'") {
          buf += raw[i + 1];
          i += 1;
          continue;
        }
        if (raw[i - 1] !== "\\") {
          segments.push({ text: buf, quoted: true });
          buf = "";
          quote = "";
        }
      }
      continue;
    }
    if (ch === "'" || ch === "\"" || ch === "`") {
      if (buf) segments.push({ text: buf, quoted: false });
      buf = ch;
      quote = ch;
      continue;
    }
    buf += ch;
  }
  if (buf) {
    segments.push({ text: buf, quoted: Boolean(quote) });
  }

  const formatSegment = (text) => {
    let s = text.replace(/\s+/g, " ");
    s = s.replace(/\bUNION\s+ALL\b/gi, "__UNION_ALL__");
    s = s.replace(/\bLEFT\s+JOIN\b/gi, "__LEFT_JOIN__");
    s = s.replace(/\bRIGHT\s+JOIN\b/gi, "__RIGHT_JOIN__");
    s = s.replace(/\bINNER\s+JOIN\b/gi, "__INNER_JOIN__");
    s = s.replace(/\bOUTER\s+JOIN\b/gi, "__OUTER_JOIN__");
    s = s.replace(/\bCROSS\s+JOIN\b/gi, "__CROSS_JOIN__");
    s = s.replace(/\bGROUP\s+BY\b/gi, "__GROUP_BY__");
    s = s.replace(/\bORDER\s+BY\b/gi, "__ORDER_BY__");
    s = s.replace(/\bDELETE\s+FROM\b/gi, "__DELETE_FROM__");
    s = s.replace(/\bINSERT\s+INTO\b/gi, "__INSERT_INTO__");

    const rules = [
      [/\bSELECT\b/gi, "\nSELECT"],
      [/\bFROM\b/gi, "\nFROM"],
      [/\bWHERE\b/gi, "\nWHERE"],
      [/\bHAVING\b/gi, "\nHAVING"],
      [/\bLIMIT\b/gi, "\nLIMIT"],
      [/\bOFFSET\b/gi, "\nOFFSET"],
      [/\bUNION\b/gi, "\nUNION"],
      [/\bJOIN\b/gi, "\nJOIN"],
      [/\bON\b/gi, "\n  ON"],
      [/\bAND\b/gi, "\n  AND"],
      [/\bOR\b/gi, "\n  OR"],
      [/\bVALUES\b/gi, "\nVALUES"],
      [/\bSET\b/gi, "\nSET"],
      [/\bUPDATE\b/gi, "\nUPDATE"],
    ];
    rules.forEach(([re, rep]) => {
      s = s.replace(re, rep);
    });

    s = s.replace(/__UNION_ALL__/g, "\nUNION ALL");
    s = s.replace(/__LEFT_JOIN__/g, "\nLEFT JOIN");
    s = s.replace(/__RIGHT_JOIN__/g, "\nRIGHT JOIN");
    s = s.replace(/__INNER_JOIN__/g, "\nINNER JOIN");
    s = s.replace(/__OUTER_JOIN__/g, "\nOUTER JOIN");
    s = s.replace(/__CROSS_JOIN__/g, "\nCROSS JOIN");
    s = s.replace(/__GROUP_BY__/g, "\nGROUP BY");
    s = s.replace(/__ORDER_BY__/g, "\nORDER BY");
    s = s.replace(/__DELETE_FROM__/g, "\nDELETE FROM");
    s = s.replace(/__INSERT_INTO__/g, "\nINSERT INTO");
    s = s.replace(/\n\s*\n+/g, "\n");
    return s;
  };

  let output = "";
  segments.forEach((seg) => {
    output += seg.quoted ? seg.text : formatSegment(seg.text);
  });
  output = output.replace(/^\s*\n/, "");
  return output.trim();
}

function buildSqlLinesHtml(sql) {
  const raw = String(sql || "");
  const lines = raw.split(/\r?\n/);
  const items = lines
    .map((line) => `<li><span class="sql-line-code">${highlightSqlLine(line)}</span></li>`)
    .join("");
  return `<ol class="sql-lines">${items}</ol>`;
}

function highlightSqlLine(line) {
  const source = String(line || "");
  if (!source) return "";
  const stashed = [];
  const makeToken = () => `__SQLTOKEN_${"x".repeat(stashed.length + 1)}__`;
  const stash = (text, kind) => {
    const key = makeToken();
    stashed.push({ key, text, kind });
    return key;
  };

  let work = source;
  work = work.replace(/(--.*$|#.*$)/g, (m) => stash(m, "comment"));
  work = work.replace(/'([^'\\]|\\.|'')*'|\"([^\"\\]|\\.)*\"|`[^`]*`/g, (m) => stash(m, "str"));

  let html = escapeHtml(work);
  html = html.replace(
    /\b(COUNT|SUM|AVG|MIN|MAX|DATE_FORMAT|COALESCE|IFNULL|ROUND|CAST|CONCAT|SUBSTRING|NOW|DATEDIFF|TIMESTAMPDIFF)\b(?=\s*\()/gi,
    (m) => `<span class="sql-token sql-fn">${m.toUpperCase()}</span>`
  );
  html = html.replace(
    /\b(LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|OUTER\s+JOIN|CROSS\s+JOIN|GROUP\s+BY|ORDER\s+BY|UNION\s+ALL|INSERT\s+INTO|DELETE\s+FROM|SELECT|FROM|WHERE|HAVING|LIMIT|OFFSET|UNION|JOIN|ON|AND|OR|AS|IN|EXISTS|NOT|NULL|IS|LIKE|DISTINCT|CASE|WHEN|THEN|ELSE|END|UPDATE|SET|DELETE|INSERT|INTO|VALUES|CREATE|ALTER|DROP|TABLE|DATABASE|SHOW|DESCRIBE|EXPLAIN|WITH|BY|ASC|DESC)\b/gi,
    (m) => `<span class="sql-token sql-kw">${m.toUpperCase()}</span>`
  );
  html = html.replace(/\b\d+(?:\.\d+)?\b/g, (m) => `<span class="sql-token sql-num">${m}</span>`);

  for (let i = stashed.length - 1; i >= 0; i -= 1) {
    const item = stashed[i];
    const cls = item.kind === "comment" ? "sql-comment" : "sql-str";
    const tokenHtml = `<span class="sql-token ${cls}">${escapeHtml(item.text)}</span>`;
    html = html.replace(item.key, tokenHtml);
  }
  return html;
}

function bufferToBase64(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
}

function base64ToBuffer(base64) {
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  } catch (err) {
    return new Uint8Array();
  }
}

async function deriveAesKey(passphrase, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

async function encryptApiKey(plain, passphrase) {
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveAesKey(passphrase, salt);
  const cipherBuf = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(plain));
  return `v1:${bufferToBase64(salt)}:${bufferToBase64(iv)}:${bufferToBase64(cipherBuf)}`;
}

async function decryptApiKey(cipher, passphrase) {
  if (!cipher || !cipher.startsWith("v1:")) {
    throw new Error("invalid cipher");
  }
  const parts = cipher.split(":");
  if (parts.length !== 4) {
    throw new Error("invalid cipher");
  }
  const salt = base64ToBuffer(parts[1]);
  const iv = base64ToBuffer(parts[2]);
  const data = base64ToBuffer(parts[3]);
  if (!salt.length || !iv.length || !data.length) {
    throw new Error("invalid cipher");
  }
  const key = await deriveAesKey(passphrase, salt);
  const plainBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, data);
  const dec = new TextDecoder();
  return dec.decode(plainBuf);
}

function maskApiKey(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.length <= 8) return `${text[0]}***${text[text.length - 1]}`;
  return `${text.slice(0, 4)}****${text.slice(-4)}`;
}

const CONTROL_RE = /[\x00-\x08\x0b-\x1f\x7f]/;

function isSafePassphrase(value) {
  const text = String(value || "").trim();
  if (!text) return false;
  if (text.length < 8 || text.length > 128) return false;
  if (CONTROL_RE.test(text)) return false;
  return true;
}

function isCipherFormat(value) {
  const text = String(value || "").trim();
  if (!text || !text.startsWith("v1:")) return false;
  const parts = text.split(":");
  if (parts.length !== 4) return false;
  return parts.slice(1).every((p) => p && !CONTROL_RE.test(p));
}

function shortPath(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const parts = raw.split("/");
  return parts[parts.length - 1] || raw;
}

function normalizeApiVaultOptions(payload) {
  const fallback = FALLBACK_API_VAULT_OPTIONS;
  const models = Array.isArray(payload && payload.models)
    ? payload.models.filter((item) => item && typeof item.value === "string" && typeof item.label === "string")
    : fallback.models;
  const safeModels = models.length ? models : fallback.models;
  const defaultModel =
    typeof payload?.default_model === "string" && safeModels.some((item) => item.value === payload.default_model)
      ? payload.default_model
      : fallback.default_model;
  const publicHost = typeof payload?.public_host === "string" && payload.public_host.trim()
    ? payload.public_host.trim()
    : fallback.public_host;
  let publicUrl = typeof payload?.public_url === "string" && payload.public_url.trim()
    ? payload.public_url.trim()
    : fallback.public_url;
  try {
    const parsedUrl = new URL(publicUrl);
    if (parsedUrl.protocol !== "https:") {
      publicUrl = fallback.public_url;
    } else {
      publicUrl = parsedUrl.toString().replace(/\/$/, "");
    }
  } catch (err) {
    publicUrl = fallback.public_url;
  }
  return {
    default_model: defaultModel,
    models: safeModels,
    public_host: publicHost,
    public_url: publicUrl,
    requires_secure_context: payload?.requires_secure_context !== false,
  };
}

async function loadApiVaultOptions() {
  try {
    const data = await apiFetch("/api/api-vault/options");
    apiVaultOptions = normalizeApiVaultOptions(data);
  } catch (err) {
    apiVaultOptions = FALLBACK_API_VAULT_OPTIONS;
  }
  renderApiModelOptions();
  renderApiSecureContextState();
}

function getApiVaultModels() {
  return Array.isArray(apiVaultOptions.models) ? apiVaultOptions.models : [];
}

function getApiVaultDefaultModel() {
  const fallback = FALLBACK_API_VAULT_OPTIONS.default_model;
  const candidate = String(apiVaultOptions.default_model || fallback).trim();
  return getApiVaultModels().some((item) => item.value === candidate) ? candidate : fallback;
}

function getApiVaultPublicUrl() {
  const fallback = FALLBACK_API_VAULT_OPTIONS.public_url;
  const candidate = String(apiVaultOptions.public_url || fallback).trim();
  if (!candidate) return fallback;
  try {
    const parsedUrl = new URL(candidate);
    if (parsedUrl.protocol !== "https:") return fallback;
    return parsedUrl.toString().replace(/\/$/, "");
  } catch (err) {
    return fallback;
  }
}

function isApiVaultSecureRuntime() {
  return Boolean(window.isSecureContext && window.crypto && window.crypto.subtle);
}

function getApiVaultDisableReason() {
  // HTTPS 또는 localhost(secure context)이면 crypto.subtle 사용 가능 → vault 허용
  if (isApiVaultSecureRuntime()) {
    return "";
  }
  // crypto.subtle 없지만 localhost 계열이면 허용 (개발 환경)
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1" || host.endsWith(".localhost")) {
    return "";
  }
  const publicUrl = getApiVaultPublicUrl();
  return `API 키 입력은 HTTPS(${publicUrl}) 또는 localhost 에서만 지원됩니다. 현재 접속은 secure context가 아닙니다.`;
}

function renderApiSecureContextState() {
  const disableReason = getApiVaultDisableReason();
  const shouldDisable = Boolean(disableReason);
  [apiKeyEncEl, apiKeyPassEl, apiModelEl, apiKeyPlainEl, apiSaveBtn, apiEncryptBtn].forEach((el) => {
    if (!el) return;
    el.disabled = shouldDisable;
  });
  if (!apiSecureHintEl) return;
  if (!shouldDisable) {
    apiSecureHintEl.classList.add("hidden");
    apiSecureHintEl.innerHTML = "";
    return;
  }
  const publicUrl = getApiVaultPublicUrl();
  const showLink = publicUrl && window.location.origin !== publicUrl;
  const linkHtml = showLink
    ? `<a class="btn ghost tiny api-secure-link" href="${escapeHtml(publicUrl)}">HTTPS 도메인으로 이동</a>`
    : "";
  apiSecureHintEl.innerHTML = `<span>${escapeHtml(disableReason)}</span>${linkHtml}`;
  apiSecureHintEl.classList.remove("hidden");
}

function getApiModelMeta(model) {
  const target = String(model || "").trim();
  return getApiVaultModels().find((item) => item.value === target) || null;
}

function isAllowedApiModel(model) {
  return Boolean(getApiModelMeta(model));
}

function normalizeApiCache(cache) {
  if (!cache || !cache.cipher) return null;
  const model = isAllowedApiModel(cache.model) ? cache.model : getApiVaultDefaultModel();
  return {
    cipher: String(cache.cipher || "").trim(),
    passphrase: String(cache.passphrase || ""),
    model,
    mask: String(cache.mask || ""),
    updated_at: Number.isFinite(Number(cache.updated_at)) ? Number(cache.updated_at) : Date.now(),
  };
}

function renderApiModelOptions(selectedModel) {
  if (!apiModelEl) return;
  const models = getApiVaultModels();
  if (!models.length) return;
  const groups = new Map();
  models.forEach((item) => {
    const group = item.group || "기타";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(item);
  });
  const currentModel = isAllowedApiModel(selectedModel) ? selectedModel : apiModelEl.value || getApiVaultDefaultModel();
  const fragments = [];
  groups.forEach((items, group) => {
    const options = items
      .map((item) => '<option value="' + escapeHtml(item.value) + '">' + escapeHtml(item.label) + '</option>')
      .join("");
    fragments.push('<optgroup label="' + escapeHtml(group) + '">' + options + '</optgroup>');
  });
  apiModelEl.innerHTML = fragments.join("");
  apiModelEl.value = isAllowedApiModel(currentModel) ? currentModel : getApiVaultDefaultModel();
}

function renderApiModelHint() {
  const model = apiModelEl ? apiModelEl.value : getApiVaultDefaultModel();
  const meta = getApiModelMeta(model);
  if (apiModelHintEl) {
    apiModelHintEl.textContent = meta ? meta.description : "";
  }
}

function loadApiKeyCache() {
  try {
    const keys = [API_KEY_CACHE_KEY, ...API_KEY_CACHE_LEGACY_KEYS];
    for (const key of keys) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      const normalized = normalizeApiCache(parsed);
      if (normalized) {
        saveApiKeyCache(normalized);
        return normalized;
      }
    }
    return null;
  } catch (err) {
    return null;
  }
}

function saveApiKeyCache(cache) {
  try {
    const normalized = normalizeApiCache(cache);
    if (!normalized) return;
    localStorage.setItem(API_KEY_CACHE_KEY, JSON.stringify(normalized));
  } catch (err) {
    // ignore
  }
}

function clearApiKeyCache() {
  try {
    localStorage.removeItem(API_KEY_CACHE_KEY);
    API_KEY_CACHE_LEGACY_KEYS.forEach((key) => localStorage.removeItem(key));
  } catch (err) {
    // ignore
  }
}

function loadApiKeyHistory() {
  try {
    const raw = localStorage.getItem(API_KEY_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    return [];
  }
}

function saveApiKeyHistory(items) {
  try {
    localStorage.setItem(API_KEY_HISTORY_KEY, JSON.stringify(items));
  } catch (err) {
    // ignore
  }
}

function renderApiHistory() {
  if (!apiHistoryEl) return;
  const items = loadApiKeyHistory();
  if (!items.length) {
    apiHistoryEl.innerHTML = "<div class=\"api-history-empty\">최근 변경 이력이 없습니다.</div>";
    return;
  }
  apiHistoryEl.innerHTML = items
    .map((entry) => {
      const mask = escapeHtml(entry.mask || "-");
      const model = escapeHtml(entry.model || "-");
      const ts = new Date(entry.updated_at || 0).toLocaleString();
      return `<div class="api-history-item"><span>${mask}</span><span>${model}</span><span class="api-history-time">${ts}</span></div>`;
    })
    .join("");
}

function recordApiKeyHistory(entry) {
  if (!entry) return;
  const normalized = {
    mask: entry.mask || "",
    model: entry.model || "",
    updated_at: entry.updated_at || Date.now(),
  };
  const items = loadApiKeyHistory();
  if (items.length && items[0].mask === normalized.mask && items[0].model === normalized.model) {
    items[0] = normalized;
  } else {
    items.unshift(normalized);
  }
  saveApiKeyHistory(items.slice(0, API_KEY_HISTORY_MAX));
  renderApiHistory();
}

async function updateApiStatusDisplay() {
  if (!apiStatusEl) return;
  const disableReason = getApiVaultDisableReason();
  const cached = loadApiKeyCache();
  if (!cached || !cached.cipher) {
    if (localLlmEnabled) {
      apiStatusEl.textContent = `로컬 LLM / ${localLlmDefaultModel}`;
      apiStatusEl.title = "서버 로컬 LLM 게이트웨이 사용 중 — API 키 불필요";
      renderApiHistory();
      return;
    }
    apiStatusEl.textContent = disableReason ? "보안 연결 필요" : "미설정";
    apiStatusEl.title = disableReason || "";
    renderApiHistory();
    return;
  }
  const model = cached.model || "-";
  const mask = cached.mask ? ` / ${cached.mask}` : "";
  apiStatusEl.textContent = `설정됨 / ${model}${mask}`;
  apiStatusEl.title = disableReason
    ? `키는 브라우저에만 저장됩니다. ${disableReason}`
    : "키는 브라우저에만 저장됩니다.";
  renderApiHistory();
}

function getApiKeyConfig() {
  const cached = loadApiKeyCache();
  if (cached && cached.cipher && cached.passphrase && cached.model) return cached;
  if (localLlmEnabled) {
    return { cipher: "", passphrase: "", model: localLlmDefaultModel };
  }
  return null;
}

function escapeHtml(value) {
  const text = String(value ?? "");
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function parseCsv(text) {
  const rows = [];
  const raw = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  let field = "";
  let row = [];
  let inQuotes = false;
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (inQuotes) {
      if (ch === "\"") {
        const next = raw[i + 1];
        if (next === "\"") {
          field += "\"";
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
      continue;
    }
    if (ch === "\"") {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(field);
      field = "";
      continue;
    }
    if (ch === "\n") {
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
      continue;
    }
    field += ch;
  }
  row.push(field);
  if (row.length > 1 || row[0] !== "") {
    rows.push(row);
  }
  return rows;
}

function stringifyValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (err) {
    return String(value);
  }
}

function formatResultSummary(summary) {
  if (!summary) return "";
  if (typeof summary !== "object") return String(summary);
  const parts = [];
  if (summary.rows !== undefined && summary.rows !== null) {
    parts.push(`rows=${summary.rows}`);
  }
  if (summary.cols !== undefined && summary.cols !== null) {
    parts.push(`cols=${summary.cols}`);
  }
  if (Array.isArray(summary.col_names) && summary.col_names.length) {
    const head = summary.col_names.slice(0, 6).join(", ");
    const tail = summary.col_names.length > 6 ? ` 외 ${summary.col_names.length - 6}` : "";
    parts.push(`col=${head}${tail}`);
  }
  if (Array.isArray(summary.samples) && summary.samples.length) {
    const sample = summary.samples[0];
    if (Array.isArray(sample) && sample.length) {
      parts.push(`sample=${sample.slice(0, 4).join(", ")}${sample.length > 4 ? "..." : ""}`);
    }
  }
  if (!parts.length && summary.preview_table && typeof summary.preview_table === "object") {
    const columns = Array.isArray(summary.preview_table.columns) ? summary.preview_table.columns : [];
    const rows = Array.isArray(summary.preview_table.rows) ? summary.preview_table.rows : [];
    if (columns.length) {
      parts.push(`preview=${rows.length}행, ${columns.length}열`);
    }
  }
  if (!parts.length && summary.preview) {
    parts.push("저장된 결과 미리보기");
  }
  return parts.join(" · ");
}

function buildCsvTable(rows, rowLimit = 50) {
  if (!rows.length) return "";
  const header = rows[0];
  const bodyRows = rows.slice(1, rowLimit > 0 ? rowLimit + 1 : undefined);
  const headHtml = header.map((cell) => `<th>${escapeHtml(cell)}</th>`).join("");
  const bodyHtml = bodyRows
    .map(
      (r) =>
        `<tr>${r.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`
    )
    .join("");
  return `<table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

function getStepCsvPaths(step = {}) {
  const summary = step && typeof step.result_summary === "object" ? step.result_summary : null;
  const csvPaths = summary && Array.isArray(summary.csv_paths) ? summary.csv_paths : [];
  return csvPaths.filter(Boolean);
}

function createCsvPreviewButton(paths = [], steps = []) {
  const csvPaths = [...new Set((Array.isArray(paths) ? paths : []).filter(Boolean))];
  const button = document.createElement("button");
  button.type = "button";
  button.className = "mini";
  button.textContent = csvPaths.length > 1 ? `CSV 미리보기 (${csvPaths.length})` : "CSV 미리보기";
  if (csvPaths.length) {
    button.addEventListener("click", () => {
      openCsvPreviewModal(csvPaths, csvPaths.length - 1, steps).catch(() => showToast("CSV 미리보기 실패"));
    });
    return button;
  }
  button.classList.add("is-disabled");
  button.setAttribute("aria-disabled", "true");
  button.title = MISSING_CSV_TOAST;
  button.addEventListener("click", (event) => {
    event.preventDefault();
    showToast(MISSING_CSV_TOAST);
  });
  return button;
}

function normalizeSqlForCompare(sql) {
  return String(sql || "")
    .replace(/\s+/g, " ")
    .replace(/;+\s*$/, "")
    .trim()
    .toLowerCase();
}

function findCsvPathsForSql(sql, paths = [], steps = []) {
  const target = normalizeSqlForCompare(sql);
  if (!target || !Array.isArray(paths) || !paths.length) return [];
  return paths.filter((path) => normalizeSqlForCompare(findSqlForCsvPath(path, steps)) === target);
}

function resetSqlResultModalState() {
  sqlResultModalState.open = false;
  sqlResultModalState.sql = "";
  sqlResultModalState.returnTarget = null;
}

function getStepWorkText(step = {}) {
  return String((step && (step.work || step.intent || step.action)) || "").trim();
}

function getStepReasonText(step = {}) {
  return String((step && step.reason) || "").trim();
}

function buildStepsDropdown(steps = [], label = "") {
  if (!Array.isArray(steps) || !steps.length) return null;
  const details = document.createElement("details");
  details.className = "msg-steps";
  const summary = document.createElement("summary");
  summary.textContent = label || `작업 상세 (${steps.length})`;
  details.appendChild(summary);
  const list = document.createElement("div");
  list.className = "steps-list";

  steps.forEach((step, idx) => {
    const item = document.createElement("div");
    item.className = "step-item";
    const head = document.createElement("div");
    head.className = "step-head";
    const title = getStepWorkText(step) || "단계";
    const stepIndex = step.step_index || idx + 1;
    head.textContent = `#${stepIndex} · ${title}`;
    item.appendChild(head);

    const meta = document.createElement("div");
    meta.className = "step-meta";
    meta.textContent = `도구: ${step.tool || "-"}`;
    item.appendChild(meta);

    const reasonText = getStepReasonText(step);
    if (reasonText) {
      const reasonEl = document.createElement("div");
      reasonEl.className = "step-reason";
      reasonEl.textContent = `이유: ${reasonText}`;
      item.appendChild(reasonEl);
    }

    const summaryText = formatResultSummary(step.result_summary || "");
    if (summaryText) {
      const summaryEl = document.createElement("div");
      summaryEl.className = "step-summary";
      summaryEl.textContent = summaryText;
      item.appendChild(summaryEl);
    }

    if (step.error) {
      const errorEl = document.createElement("div");
      errorEl.className = "step-error";
      errorEl.textContent = step.error;
      item.appendChild(errorEl);
    }

    if (step.sql) {
      const actions = document.createElement("div");
      actions.className = "step-actions";
      const stepCsvPaths = getStepCsvPaths(step);
      const sqlBtn = document.createElement("button");
      sqlBtn.className = "mini ghost";
      sqlBtn.textContent = "SQL 보기";
      sqlBtn.addEventListener("click", () =>
        openSqlResultModal({
          sql: step.sql,
        }).catch(() => showToast("SQL 보기 실패"))
      );
      actions.appendChild(sqlBtn);
      actions.appendChild(createCsvPreviewButton(stepCsvPaths, [step]));
      item.appendChild(actions);
    }

    list.appendChild(item);
  });

  details.appendChild(list);
  return details;
}

function findSqlForCsvPath(path, steps = []) {
  if (!path || !Array.isArray(steps)) return "";
  for (const step of steps) {
    if (!step || !step.result_summary) continue;
    const summary = step.result_summary || {};
    const csvPaths = Array.isArray(summary.csv_paths) ? summary.csv_paths : [];
    if (csvPaths.includes(path) && step.sql) {
      return step.sql;
    }
  }
  return "";
}

function isInternalAssistantContent(text) {
  const value = String(text || "").trim();
  if (!value) return true;
  if (
    value.startsWith("실행 완료:") ||
    value.startsWith("자동 탐색 완료:") ||
    value.startsWith("파일 탐색 완료:") ||
    value.startsWith("대화 검색 완료:") ||
    value.startsWith("파일 읽기 완료:")
  ) return true;
  // tool_notes JSON (LLM 도구 호출 시 생성) 필터링
  if (value.startsWith("{") && value.endsWith("}")) {
    try {
      const parsed = JSON.parse(value);
      if (parsed && typeof parsed === "object" && "tool_notes" in parsed) return true;
    } catch (_) { /* not JSON */ }
  }
  return false;
}

function isQuestionContent(text) {
  const value = String(text || "").trim();
  if (!value) return false;
  if (value.includes("?")) return true;
  return /알려주세요|하시겠습니까|될까요|가능할까요|확인해|선택/.test(value);
}

function dedupeSteps(steps = []) {
  const map = new Map();
  steps.forEach((step) => {
    if (!step) return;
    const key = `${step.run_id || ""}#${step.step_index || ""}#${step.tool || ""}#${getStepWorkText(step)}`;
    if (!map.has(key)) map.set(key, step);
  });
  return Array.from(map.values()).sort((a, b) => (a.step_index || 0) - (b.step_index || 0));
}

function mergeMeta(base = {}, next = {}) {
  const merged = { ...base };
  if (next.sql && !merged.sql) merged.sql = next.sql;
  if (next.run_id && !merged.run_id) merged.run_id = next.run_id;
  if (next.rationale) merged.rationale = next.rationale;
  const baseCsv = Array.isArray(merged.csv_paths) ? merged.csv_paths : [];
  const nextCsv = Array.isArray(next.csv_paths)
    ? next.csv_paths
    : Array.isArray(next.csvPaths)
      ? next.csvPaths
      : next.csvPath
        ? [next.csvPath]
        : [];
  const csvSet = new Set([...baseCsv, ...nextCsv].filter(Boolean));
  if (csvSet.size) merged.csv_paths = Array.from(csvSet);
  const baseSteps = Array.isArray(merged.steps) ? merged.steps : [];
  const nextSteps = Array.isArray(next.steps) ? next.steps : [];
  merged.steps = dedupeSteps([...baseSteps, ...nextSteps]);
  return merged;
}

function buildSummaryFromMeta(meta = {}) {
  const steps = Array.isArray(meta.steps) ? meta.steps : [];
  const lastStep = steps.length ? steps[steps.length - 1] : null;
  const work = lastStep ? getStepWorkText(lastStep) : "";
  const summary = lastStep && lastStep.result_summary ? lastStep.result_summary : null;
  const rows = summary && typeof summary === "object" ? summary.rows : null;
  const cols = summary && typeof summary === "object" ? summary.cols : null;
  const csvCount = Array.isArray(meta.csv_paths) ? meta.csv_paths.length : 0;
  const lines = [];
  if (work) lines.push(`실행 완료: ${work}`);
  if (rows !== null && rows !== undefined) {
    lines.push(cols !== null && cols !== undefined ? `결과: ${rows}행, ${cols}열` : `결과: ${rows}행`);
  }
  if (csvCount) lines.push(`결과셋: ${csvCount}개 (CSV 미리보기에서 확인)`);
  return lines.join("\n") || "요청 처리 완료";
}

function groupConversationMessages(messages = []) {
  const grouped = [];
  let pendingAssistant = null;
  let pendingRunId = "";

  const flushAssistant = () => {
    if (pendingAssistant) {
      if (isInternalAssistantContent(pendingAssistant.content) || !pendingAssistant.content) {
        pendingAssistant.content = buildSummaryFromMeta(pendingAssistant.meta || {});
      }
      grouped.push(pendingAssistant);
      pendingAssistant = null;
      pendingRunId = "";
    }
  };

  messages.forEach((msg) => {
    if (!msg) return;
    if (msg.role === "user") {
      flushAssistant();
      grouped.push(msg);
      return;
    }
    if (msg.role === "assistant") {
      const content = String(msg.content || "");
      const runId = msg.meta && msg.meta.run_id ? String(msg.meta.run_id) : "";
      if (pendingAssistant && runId && pendingRunId && runId !== pendingRunId) {
        flushAssistant();
      }
      if (!pendingAssistant) {
        pendingAssistant = { ...msg };
        pendingAssistant.meta = mergeMeta({}, msg.meta || {});
        pendingRunId = runId;
        return;
      }
      pendingAssistant.meta = mergeMeta(pendingAssistant.meta || {}, msg.meta || {});
      if (isQuestionContent(content)) {
        pendingAssistant.content = content;
        pendingAssistant.created_at = msg.created_at;
      } else if (!isInternalAssistantContent(content)) {
        pendingAssistant.content = content;
        pendingAssistant.created_at = msg.created_at;
      }
      return;
    }
    grouped.push(msg);
  });

  flushAssistant();
  return grouped;
}

function renderCsvPager(paths, index) {
  if (!csvPagerDockEl || !csvPagerPanelEl) return;
  csvPagerPanelEl.innerHTML = "";
  const rerender = async () => renderCsvPreviewPage();
  const pager = document.createElement("div");
  pager.className = "csv-pager";
  const left = document.createElement("div");
  left.className = "csv-pager-left";
  const prevBtn = document.createElement("button");
  prevBtn.className = "mini ghost";
  prevBtn.textContent = "이전";
  prevBtn.disabled = index <= 0;
  prevBtn.addEventListener("click", async () => {
    if (csvPreviewState.loading) return;
    csvPreviewState.index = Math.max(0, csvPreviewState.index - 1);
    await rerender();
  });
  const label = document.createElement("div");
  label.className = "csv-pager-label";
  label.textContent = `결과셋 ${index + 1} / ${paths.length}`;
  const nextBtn = document.createElement("button");
  nextBtn.className = "mini ghost";
  nextBtn.textContent = "다음";
  nextBtn.disabled = index >= paths.length - 1;
  nextBtn.addEventListener("click", async () => {
    if (csvPreviewState.loading) return;
    csvPreviewState.index = Math.min(paths.length - 1, csvPreviewState.index + 1);
    await rerender();
  });
  left.appendChild(prevBtn);
  left.appendChild(label);
  left.appendChild(nextBtn);
  pager.appendChild(left);
  csvPagerPanelEl.appendChild(pager);
  csvPagerDockEl.classList.remove("hidden");
  csvPagerDockEl.setAttribute("aria-hidden", "false");
}

function hideCsvPagerDock() {
  if (!csvPagerDockEl || !csvPagerPanelEl) return;
  csvPagerPanelEl.innerHTML = "";
  csvPagerDockEl.classList.add("hidden");
  csvPagerDockEl.setAttribute("aria-hidden", "true");
}

function prepareModalShell(title, bodyClasses = []) {
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modalTitle");
  const modalBody = document.getElementById("modalBody");
  const modalDownload = document.getElementById("modalDownload");
  const modalCopy = document.getElementById("modalCopy");
  hideCsvPagerDock();
  modalTitle.textContent = title;
  modalBody.textContent = "";
  modalBody.classList.remove("modal-sql");
  modalBody.classList.remove("modal-csv");
  modalBody.classList.remove("modal-sql-result");
  modalBody.innerHTML = "";
  bodyClasses.forEach((className) => {
    if (className) modalBody.classList.add(className);
  });
  return { modal, modalTitle, modalBody, modalDownload, modalCopy };
}

function syncCsvPreviewState(paths, startIndex = 0, steps = [], resetView = false) {
  const nextPaths = Array.isArray(paths) ? paths.filter(Boolean) : [];
  const nextIndex =
    Number.isFinite(Number(startIndex)) && Number(startIndex) >= 0
      ? Math.min(nextPaths.length - 1, Math.max(0, Number(startIndex)))
      : Math.max(0, nextPaths.length - 1);
  const prevPath = Array.isArray(csvPreviewState.paths) ? csvPreviewState.paths[csvPreviewState.index] || "" : "";
  const nextPath = nextPaths[nextIndex] || "";
  csvPreviewState.paths = [...nextPaths];
  csvPreviewState.index = nextIndex;
  csvPreviewState.steps = Array.isArray(steps) ? steps : [];
  if (resetView || prevPath !== nextPath) {
    csvPreviewState.scrollTop = 0;
    csvPreviewState.sortIndex = null;
    csvPreviewState.sortDir = 1;
    csvPreviewState.rawRows = null;
  }
}

async function buildCsvPreviewContent({
  path,
  titleText,
  sqlText = "",
  sqlButtonLabel = "SQL 보기",
  onSqlButtonClick = null,
} = {}) {
  const currentPath = String(path || "").trim();
  if (!currentPath) {
    return {
      bodyEl: document.createElement("div"),
      copyText: "",
      copyLabel: "복사",
      downloadUrl: "",
    };
  }

  const scrollWrap = document.createElement("div");
  scrollWrap.className = "csv-preview-scroll";
  scrollWrap.addEventListener("scroll", () => {
    csvPreviewState.scrollTop = scrollWrap.scrollTop;
  });

  const toolbar = document.createElement("div");
  toolbar.className = "csv-preview-toolbar";
  const toolbarTitle = document.createElement("div");
  toolbarTitle.className = "csv-preview-title";
  toolbarTitle.textContent = titleText || shortPath(currentPath) || "CSV 결과";
  toolbar.appendChild(toolbarTitle);

  const limitWrap = document.createElement("div");
  limitWrap.className = "csv-preview-limit";
  const limitLabel = document.createElement("span");
  limitLabel.className = "csv-preview-limit-label";
  limitLabel.textContent = `행: ${csvPreviewState.rowLimit}`;
  const limitInput = document.createElement("input");
  limitInput.type = "range";
  limitInput.min = "5";
  limitInput.max = "200";
  limitInput.step = "5";
  limitInput.value = String(csvPreviewState.rowLimit);
  limitInput.addEventListener("input", () => {
    csvPreviewState.rowLimit = parseInt(limitInput.value, 10) || 50;
    limitLabel.textContent = `행: ${csvPreviewState.rowLimit}`;
    if (csvPreviewState.rawRows && csvPreviewState.rawRows.length) {
      const sorted = applyCsvSort(csvPreviewState.rawRows);
      tableWrap.innerHTML = buildCsvTable(sorted, csvPreviewState.rowLimit);
      if (note) {
        note.textContent = `미리보기는 상위 ${csvPreviewState.rowLimit}행까지 표시됩니다. 복사는 TSV로 제공됩니다.`;
      }
      attachCsvSortHandlers(tableWrap);
    }
  });
  limitWrap.appendChild(limitLabel);
  limitWrap.appendChild(limitInput);
  toolbar.appendChild(limitWrap);

  if (sqlText && typeof onSqlButtonClick === "function") {
    const sqlToggleBtn = document.createElement("button");
    sqlToggleBtn.className = "mini ghost";
    sqlToggleBtn.textContent = sqlButtonLabel;
    sqlToggleBtn.addEventListener("click", onSqlButtonClick);
    toolbar.appendChild(sqlToggleBtn);
  }
  scrollWrap.appendChild(toolbar);

  const tableWrap = document.createElement("div");
  tableWrap.className = "csv-preview-table";
  csvPreviewState.loading = true;
  const preview = await fetchCsvPreview(currentPath);
  csvPreviewState.loading = false;
  let note = null;
  let rows = [];
  if (!preview || preview.includes("CSV 미리보기 실패")) {
    tableWrap.textContent = preview || "CSV 미리보기 실패";
    modalCopyText = preview || "";
    scrollWrap.appendChild(tableWrap);
  } else {
    rows = parseCsv(preview);
    if (!rows.length) {
      tableWrap.textContent = preview;
      modalCopyText = preview;
      scrollWrap.appendChild(tableWrap);
    } else {
      csvPreviewState.rawRows = rows;
      const sortedRows = applyCsvSort(rows);
      tableWrap.innerHTML = buildCsvTable(sortedRows, csvPreviewState.rowLimit);
      attachCsvSortHandlers(tableWrap);
      modalCopyText = buildTsv(rows);
      scrollWrap.appendChild(tableWrap);
      note = document.createElement("div");
      note.className = "csv-preview-note";
      note.textContent = `미리보기는 상위 ${csvPreviewState.rowLimit}행까지 표시됩니다. 복사는 TSV로 제공됩니다.`;
    }
  }
  if (note) scrollWrap.appendChild(note);

  return {
    bodyEl: scrollWrap,
    copyText: modalCopyText,
    copyLabel: Array.isArray(rows) && rows.length ? "복사(TSV)" : "복사",
    downloadUrl: `/api/file?path=${encodeURIComponent(currentPath)}`,
  };
}

async function renderCsvPreviewPage() {
  const paths = csvPreviewState.paths || [];
  const steps = Array.isArray(csvPreviewState.steps) ? csvPreviewState.steps : [];
  if (!paths.length) return;
  const index = Math.min(Math.max(csvPreviewState.index, 0), paths.length - 1);
  const currentPath = paths[index];
  const sqlForPath = findSqlForCsvPath(currentPath, steps);
  const { modal, modalBody, modalDownload, modalCopy } = prepareModalShell("CSV 미리보기", ["modal-csv"]);
  const fileLabel = shortPath(currentPath);
  const titleText = fileLabel ? `${index + 1}/${paths.length} · ${fileLabel}` : `${index + 1}/${paths.length}`;
  const content = await buildCsvPreviewContent({
    path: currentPath,
    titleText,
    sqlText: sqlForPath,
    sqlButtonLabel: "SQL 보기",
    onSqlButtonClick:
      sqlForPath
        ? () =>
            openSqlResultModal({
              sql: sqlForPath,
              returnTarget: {
                type: "csv",
                paths: [...paths],
                index,
                steps: [...steps],
              },
            })
        : null,
  });
  modalBody.appendChild(content.bodyEl);
  if (csvPreviewState.scrollTop) {
    content.bodyEl.scrollTop = csvPreviewState.scrollTop;
  }
  modalCopyText = content.copyText || "";
  if (modalCopy) modalCopy.textContent = content.copyLabel || "복사";
  if (modalDownload) {
    modalDownload.href = content.downloadUrl || "#";
    modalDownload.classList.toggle("hidden", !content.downloadUrl);
  }
  renderCsvPager(paths, index);
  modal.classList.add("show");
}

async function renderSqlResultModal() {
  if (!sqlResultModalState.open) return;
  const sqlText = formatSql(sqlResultModalState.sql);
  const { modal, modalBody, modalDownload, modalCopy } = prepareModalShell("실행 SQL", ["modal-sql", "modal-sql-result"]);
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "sql-result-scroll";
  const toolbar = document.createElement("div");
  toolbar.className = "sql-result-toolbar";
  const toolbarTitle = document.createElement("div");
  toolbarTitle.className = "sql-result-title";
  toolbarTitle.textContent = "실행 SQL";
  toolbar.appendChild(toolbarTitle);
  scrollWrap.appendChild(toolbar);
  const sqlPanel = document.createElement("div");
  sqlPanel.className = "sql-result-panel";
  sqlPanel.innerHTML = buildSqlLinesHtml(sqlText);
  scrollWrap.appendChild(sqlPanel);
  modalBody.appendChild(scrollWrap);
  modalCopyText = sqlText;
  if (modalCopy) modalCopy.textContent = "복사";
  if (modalDownload) modalDownload.classList.add("hidden");
  hideCsvPagerDock();
  modal.classList.add("show");
}

async function openSqlResultModal({
  sql,
  returnTarget = null,
} = {}) {
  const formattedSql = formatSql(sql);
  if (!formattedSql) return;
  sqlResultModalState.open = true;
  sqlResultModalState.sql = formattedSql;
  sqlResultModalState.returnTarget = returnTarget;
  await renderSqlResultModal();
}

async function openCsvPreviewModal(paths, startIndex = 0, steps = []) {
  if (!Array.isArray(paths) || !paths.length) return;
  resetSqlResultModalState();
  syncCsvPreviewState(paths, startIndex, steps, true);
  await renderCsvPreviewPage();
}

function buildTsv(rows) {
  return rows
    .map((row) =>
      row.map((cell) => String(cell ?? "").replace(/\r?\n/g, " ")).join("\t")
    )
    .join("\n");
}

function compareCsvValues(a, b) {
  const ax = String(a ?? "").trim();
  const bx = String(b ?? "").trim();
  const na = Number(ax.replace(/,/g, ""));
  const nb = Number(bx.replace(/,/g, ""));
  const isNum = !Number.isNaN(na) && !Number.isNaN(nb) && ax !== "" && bx !== "";
  if (isNum) return na - nb;
  return ax.localeCompare(bx, "ko");
}

function applyCsvSort(rows) {
  if (!rows || rows.length < 2) return rows;
  if (csvPreviewState.sortIndex === null || csvPreviewState.sortIndex === undefined) {
    return rows;
  }
  const header = rows[0];
  const body = rows.slice(1);
  const idx = csvPreviewState.sortIndex;
  const dir = csvPreviewState.sortDir || 1;
  const sorted = [...body].sort((a, b) => compareCsvValues(a[idx], b[idx]) * dir);
  return [header, ...sorted];
}

function attachCsvSortHandlers(tableWrap) {
  if (!tableWrap) return;
  const headers = tableWrap.querySelectorAll("th");
  if (!headers.length) return;
  headers.forEach((th, idx) => {
    th.classList.toggle("sorted", csvPreviewState.sortIndex === idx);
    th.classList.toggle("asc", csvPreviewState.sortIndex === idx && csvPreviewState.sortDir === 1);
    th.classList.toggle("desc", csvPreviewState.sortIndex === idx && csvPreviewState.sortDir === -1);
    th.addEventListener("click", () => {
      if (csvPreviewState.sortIndex === idx) {
        csvPreviewState.sortDir = csvPreviewState.sortDir === 1 ? -1 : 1;
      } else {
        csvPreviewState.sortIndex = idx;
        csvPreviewState.sortDir = 1;
      }
      if (csvPreviewState.rawRows && csvPreviewState.rawRows.length) {
        const sorted = applyCsvSort(csvPreviewState.rawRows);
        tableWrap.innerHTML = buildCsvTable(sorted, csvPreviewState.rowLimit);
        attachCsvSortHandlers(tableWrap);
      }
    });
  });
}

function extractDateKey(createdAt) {
  if (createdAt) {
    const match = String(createdAt).match(/\d{4}-\d{2}-\d{2}/);
    if (match) return match[0];
  }
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function sanitizeTopic(value) {
  const raw = String(value || "").trim();
  if (!raw) return "(미설정)";
  const convIdPattern = /\b\d{14}-[0-9a-f]{8}\b/i;
  if (convIdPattern.test(raw)) {
    const cleaned = raw.replace(convIdPattern, "").replace(/\s+/g, " ").trim();
    if (cleaned && cleaned !== "대화") {
      return cleaned;
    }
    return "대화";
  }
  return raw;
}

function formatAbsoluteTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const y = parsed.getFullYear();
  const m = String(parsed.getMonth() + 1).padStart(2, "0");
  const d = String(parsed.getDate()).padStart(2, "0");
  const hh = String(parsed.getHours()).padStart(2, "0");
  const mm = String(parsed.getMinutes()).padStart(2, "0");
  const ss = String(parsed.getSeconds()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}

function formatDateLabel(dateKey) {
  return dateKey;
}

function formatRelativeTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const diffMs = Date.now() - parsed.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));
  if (diffSec < 60) return `${diffSec}초 전`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간 전`;
  const y = parsed.getFullYear();
  const m = String(parsed.getMonth() + 1).padStart(2, "0");
  const d = String(parsed.getDate()).padStart(2, "0");
  const hh = String(parsed.getHours()).padStart(2, "0");
  const mm = String(parsed.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

function normalizeSingleLine(value, maxLen = 140) {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  if (raw.length <= maxLen) return raw;
  return `${raw.slice(0, maxLen - 1)}…`;
}

function normalizeForCompare(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function sanitizeContextTag(value, maxLen = 48) {
  const cleaned = sanitizeFollowupText(value, maxLen)
    .replace(/[`"'()[\]{}]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned || cleaned === "-" || cleaned === "none") return "";
  return normalizeSingleLine(cleaned, maxLen);
}

function loadPinnedContext() {
  try {
    const raw = localStorage.getItem(PINNED_CONTEXT_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    pinnedDomainHint = sanitizeContextTag(parsed.domain || "", 56);
    pinnedStrategyHint = sanitizeContextTag(parsed.strategy || "", 72);
  } catch (err) {
    pinnedDomainHint = "";
    pinnedStrategyHint = "";
  }
}

function savePinnedContext() {
  try {
    localStorage.setItem(
      PINNED_CONTEXT_KEY,
      JSON.stringify({
        domain: pinnedDomainHint || "",
        strategy: pinnedStrategyHint || "",
        updated_at: Date.now(),
      })
    );
  } catch (err) {
    // ignore
  }
}

function renderContextBadges() {
  const domainValue = pinnedDomainHint || currentDomainHint || "-";
  const strategyValue = pinnedStrategyHint || currentStrategyHint || "-";
  if (domainBadgeEl) {
    domainBadgeEl.textContent = `Domain: ${domainValue}`;
    domainBadgeEl.classList.toggle("is-empty", domainValue === "-");
    domainBadgeEl.classList.toggle("is-pinned", Boolean(pinnedDomainHint));
    domainBadgeEl.title = pinnedDomainHint
      ? "고정 해제: 현재 도메인 고정 상태"
      : "고정: 현재 도메인을 다음 요청에도 유지";
  }
  if (strategyBadgeEl) {
    strategyBadgeEl.textContent = `Strategy: ${strategyValue}`;
    strategyBadgeEl.classList.toggle("is-empty", strategyValue === "-");
    strategyBadgeEl.classList.toggle("is-pinned", Boolean(pinnedStrategyHint));
    strategyBadgeEl.title = pinnedStrategyHint
      ? "고정 해제: 현재 전략 고정 상태"
      : "고정: 현재 전략을 다음 요청에도 유지";
  }
}

function renderFollowupLiveStatus() {
  if (!followupLiveEl) return;
  updateFollowupApplyButton();
  renderFollowupAutoInject();
  const intent = followupIntentEl ? sanitizeFollowupText(followupIntentEl.value || "", 64) : "";
  const constraints = followupConstraintsEl ? sanitizeFollowupText(followupConstraintsEl.value || "", 84) : "";
  const parts = [];
  if (intent) parts.push(`의도 ${intent}`);
  if (constraints) parts.push(`제약 ${constraints}`);
  if (pinnedDomainHint) parts.push(`Domain ${pinnedDomainHint} 고정`);
  if (pinnedStrategyHint) parts.push(`Strategy ${pinnedStrategyHint} 고정`);
  if (isRestoreModeActive()) parts.push("복원 모드 고정");
  const hasContext = parts.length > 0;
  if (!hasContext) {
    followupLiveEl.textContent = followupApplyArmed ? "현재 이어받기 없음 (전송 반영만 켜짐)" : "현재 이어받기 없음";
    followupLiveEl.classList.add("empty");
    return;
  }
  parts.push(followupApplyArmed || isRestoreModeActive() ? "전송 반영 켜짐" : "전송 반영 꺼짐");
  followupLiveEl.textContent = `현재 이어받기: ${parts.join(" · ")}`;
  followupLiveEl.classList.remove("empty");
}

function updateFollowupApplyButton() {
  if (!followupApplyOnceEl) return;
  const active = followupApplyArmed || isRestoreModeActive();
  followupApplyOnceEl.classList.toggle("is-active", active);
  followupApplyOnceEl.textContent = active ? "다음 요청 반영: 켜짐" : "다음 요청 반영: 꺼짐";
  if (isRestoreModeActive()) {
    followupApplyOnceEl.title = "복원 모드에서는 항상 반영됩니다.";
  } else {
    followupApplyOnceEl.title = "필요할 때만 켜고, 전송 후 자동으로 꺼집니다.";
  }
}

function getPendingInjectParts() {
  const parts = [];
  const useDraft = Boolean(followupManualEdit && followupContextConversationId === activeConversationId);
  const draftIntent = useDraft && followupIntentEl ? sanitizeFollowupText(followupIntentEl.value || "", 56) : "";
  const draftConstraints = useDraft && followupConstraintsEl ? sanitizeFollowupText(followupConstraintsEl.value || "", 72) : "";
  if (draftIntent) parts.push(`의도 ${draftIntent}`);
  if (draftConstraints) parts.push(`제약 ${draftConstraints}`);
  const pin = getPinnedContextPayload();
  if (pin.domain) parts.push(`고정 도메인 ${pin.domain}`);
  if (pin.strategy) parts.push(`고정 전략 ${pin.strategy}`);
  if (isRestoreModeActive()) {
    parts.push(`복원 모드 ${shortPath(restoreModeState.file_path)}`);
  }
  return parts;
}

function getActiveInjectParts() {
  if (!followupApplyArmed && !isRestoreModeActive()) return [];
  return getPendingInjectParts();
}

function mergeConstraintLine(base, line, maxLen = 220) {
  const target = sanitizeFollowupText(line || "", 120);
  if (!target) return sanitizeFollowupText(base || "", maxLen);
  const parts = String(base || "")
    .split(/\s*[;·]\s*/g)
    .map((item) => sanitizeFollowupText(item || "", 120))
    .filter(Boolean);
  const exists = parts.some((item) => normalizeForCompare(item) === normalizeForCompare(target));
  if (!exists) parts.push(target);
  return sanitizeFollowupText(parts.join("; "), maxLen);
}

function getPinnedContextPayload() {
  return {
    domain: sanitizeContextTag(pinnedDomainHint || "", 56),
    strategy: sanitizeContextTag(pinnedStrategyHint || "", 72),
  };
}

function renderFollowupAutoInject() {
  if (!followupAutoInjectEl) return;
  const pending = getPendingInjectParts();
  const parts = getActiveInjectParts();
  if (!pending.length) {
    followupAutoInjectEl.textContent = "자동 추가 제약 없음";
    followupAutoInjectEl.classList.add("empty");
    return;
  }
  if (!parts.length) {
    followupAutoInjectEl.textContent = `자동 추가 대기: ${pending.join(" · ")} (반영 버튼 필요)`;
    followupAutoInjectEl.classList.remove("empty");
    return;
  }
  followupAutoInjectEl.textContent = `다음 요청에 자동 추가: ${parts.join(" · ")}`;
  followupAutoInjectEl.classList.remove("empty");
}

function buildSendPreviewPayload(rawInput = "") {
  const raw = String(rawInput || "").trim();
  if (!raw) {
    return { original: "", outbound: "", changed: false };
  }
  const parsed = parseFollowupEnvelope(raw);
  const original = parsed.userRequest || raw;
  const outbound = composeMessageWithFollowup(original);
  const changed = normalizeForCompare(outbound) !== normalizeForCompare(original);
  return { original, outbound, changed };
}

function renderSendPreview() {
  if (!sendPreviewBoxEl || !sendPreviewMetaEl || !sendPreviewTextEl || !promptBox) return;
  let rawInput = String(promptBox.value || "");
  const draftParsed = parseFollowupEnvelope(rawInput);
  // Keep the prompt box clean: when follow-up auto-apply is off, unwrap stale context text.
  if (draftParsed.wrapped && !followupApplyArmed && !isRestoreModeActive()) {
    const cleanedRequest = String(draftParsed.userRequest || "").trim();
    if (cleanedRequest && cleanedRequest !== String(promptBox.value || "").trim()) {
      promptBox.value = cleanedRequest;
      rawInput = cleanedRequest;
    }
  }
  const raw = String(rawInput || "").trim();
  const autoParts = getActiveInjectParts();
  const pendingParts = getPendingInjectParts();
  if (!raw) {
    sendPreviewMetaEl.textContent = autoParts.length
      ? `입력 전입니다. 자동 추가 예정: ${autoParts.join(" · ")}`
      : pendingParts.length
        ? `입력 전입니다. 자동 추가 대기: ${pendingParts.join(" · ")}`
      : "입력 전입니다. 원문 그대로 전송됩니다.";
    sendPreviewTextEl.textContent = "(요청을 입력하면 실제 전송문이 표시됩니다.)";
    sendPreviewBoxEl.classList.remove("changed");
    return;
  }
  const payload = buildSendPreviewPayload(raw);
  const originalLabel = normalizeSingleLine(payload.original, 92);
  sendPreviewTextEl.textContent = payload.outbound || payload.original;
  if (payload.changed) {
    sendPreviewMetaEl.textContent = autoParts.length
      ? `원문: ${originalLabel} / 전송문은 아래 내용 + 자동 추가(${autoParts.join(" · ")})`
      : `원문: ${originalLabel} / 전송문은 아래 내용(이어받기 컨텍스트 포함)`;
    sendPreviewBoxEl.classList.add("changed");
  } else {
    sendPreviewMetaEl.textContent = autoParts.length
      ? `원문 그대로 전송 + 자동 추가: ${autoParts.join(" · ")}`
      : pendingParts.length
        ? `원문 그대로 전송됩니다. (자동 추가 대기: ${pendingParts.join(" · ")})`
      : "원문 그대로 전송됩니다.";
    sendPreviewBoxEl.classList.remove("changed");
  }
}

function isLikelySqlText(value) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  const head = /^(select|with|insert|update|delete|create|alter|drop|show|describe|explain)\b/i.test(raw);
  const body = /\b(from|where|group\s+by|order\s+by|limit|join|having|count\(|sum\(|avg\(|min\(|max\(|left\(|right\(|inner\s+join)\b/i.test(raw);
  return head && body;
}

function stripFollowupTokens(value) {
  let text = String(value || "");
  if (!text) return "";
  text = text
    .replace(/\[이어받기 컨텍스트\]/gi, " ")
    .replace(/\[사용자 요청\]/gi, " ")
    .replace(/\b의도\s*:/gi, " ")
    .replace(/\b제약\s*:/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
  return text;
}

function sanitizeFollowupText(value, maxLen = 140) {
  const cleaned = stripFollowupTokens(value);
  if (!cleaned) return "";
  return normalizeSingleLine(cleaned, maxLen);
}

function parseFollowupEnvelope(value) {
  const maxUnwrap = 4;
  let current = String(value || "").trim();
  if (!current) {
    return { wrapped: false, intent: "", constraints: "", userRequest: "" };
  }
  let wrapped = false;
  let intent = "";
  let constraints = "";
  for (let i = 0; i < maxUnwrap; i += 1) {
    if (!current.includes("[이어받기 컨텍스트]")) break;
    if (!current.startsWith("[이어받기 컨텍스트]")) {
      const markerPos = current.indexOf("[이어받기 컨텍스트]");
      current = current.slice(markerPos).trim();
    }
    wrapped = true;
    const normalizedCurrent = current
      .replace(/^\[이어받기 컨텍스트\]\s*/i, "[이어받기 컨텍스트]\n")
      .replace(/\s+(의도\s*:)/gi, "\n$1")
      .replace(/\s+(제약\s*:)/gi, "\n$1")
      .replace(/\s+(\[사용자 요청\])/gi, "\n$1");
    const lines = normalizedCurrent
      .split(/\r?\n/)
      .map((line) => String(line || "").trim())
      .filter(Boolean);
    let nextRequest = "";
    lines.forEach((line) => {
      if (/^의도\s*:/i.test(line)) {
        intent = sanitizeFollowupText(line.replace(/^의도\s*:/i, "").trim(), 180);
        return;
      }
      if (/^제약\s*:/i.test(line)) {
        constraints = sanitizeFollowupText(line.replace(/^제약\s*:/i, "").trim(), 220);
        return;
      }
      if (line.startsWith("[사용자 요청]")) {
        nextRequest = line.replace("[사용자 요청]", "").trim();
      }
    });
    if (!nextRequest) {
      const fallback = lines
        .filter(
          (line) =>
            line &&
            line !== "[이어받기 컨텍스트]" &&
            !/^의도\s*:/i.test(line) &&
            !/^제약\s*:/i.test(line) &&
            !line.startsWith("[사용자 요청]")
        )
        .pop();
      nextRequest = String(fallback || "").trim();
    }
    if (!nextRequest) break;
    current = nextRequest;
  }
  return {
    wrapped,
    intent: sanitizeFollowupText(intent, 180),
    constraints: sanitizeFollowupText(constraints, 220),
    userRequest: String(current || "").trim(),
  };
}

function extractConclusionLines(text, maxLines = 3) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const sentenceLines = lines.length > 1
    ? lines
    : raw
      .split(/(?<=[.!?])\s+|(?<=다\.)\s+/)
      .map((line) => line.trim())
      .filter(Boolean);
  const picked = sentenceLines
    .filter((line) => !/^실행 완료[:：]?$/i.test(line))
    .slice(0, maxLines)
    .map((line) => normalizeSingleLine(line, 180));
  return picked;
}

function buildConclusionText(text, maxLines = 3) {
  const lines = extractConclusionLines(text, maxLines);
  return lines.join("\n").trim();
}

function isRedundantAssistantBody(text, conclusionText) {
  const raw = String(text || "").trim();
  const conclusion = String(conclusionText || "").trim();
  if (!raw || !conclusion) return false;
  const normRaw = normalizeForCompare(raw);
  const normConclusion = normalizeForCompare(conclusion);
  if (normRaw === normConclusion) return true;
  if (raw.length <= 260 && normConclusion && normRaw.includes(normConclusion)) return true;
  const rawLines = raw
    .split(/\r?\n/)
    .map((line) => normalizeForCompare(line))
    .filter(Boolean);
  const conclusionLines = conclusion
    .split(/\r?\n/)
    .map((line) => normalizeForCompare(line))
    .filter(Boolean);
  if (rawLines.length <= 4 && conclusionLines.length >= 2) {
    const matched = conclusionLines.filter((line) => rawLines.some((rawLine) => rawLine.includes(line) || line.includes(rawLine)));
    if (matched.length / conclusionLines.length >= 0.75) return true;
  }
  return false;
}

function shouldCollapseAssistantOutput(text, meta = {}) {
  const raw = String(text || "");
  if (!raw) return false;
  const lineCount = raw.split(/\r?\n/).filter(Boolean).length;
  const csvCount = Array.isArray(meta.csv_paths) ? meta.csv_paths.length : 0;
  const stepCount = Array.isArray(meta.steps) ? meta.steps.length : 0;
  return raw.length >= 320 || lineCount >= 8 || stepCount >= 6 || csvCount >= 2;
}

function isMaxStepReachedText(text) {
  const raw = String(text || "").trim();
  return raw.includes("최대 단계 수에 도달");
}

function formatElapsedShort(seconds) {
  const sec = Math.max(0, Math.floor(Number(seconds) || 0));
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatDurationMsLabel(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value < 1000) return `${Math.round(value)}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

function estimateDurationMs() {
  if (!recentDurationsMs.length) return null;
  const sorted = [...recentDurationsMs].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)] || null;
}

function getLatestStepInfoFromGrouped(grouped = []) {
  if (!Array.isArray(grouped) || !grouped.length) return { stepCount: 0, intent: "" };
  for (let i = grouped.length - 1; i >= 0; i -= 1) {
    const item = grouped[i];
    if (!item || item.role !== "assistant") continue;
    const meta = item.meta || {};
    const steps = Array.isArray(meta.steps) ? meta.steps : [];
    if (!steps.length) continue;
    let stepCount = 0;
    let intent = "";
    steps.forEach((step) => {
      const idx = Number(step && step.step_index);
      if (Number.isFinite(idx) && idx > stepCount) stepCount = idx;
      const work = getStepWorkText(step);
      if (work) intent = work;
    });
    return { stepCount, intent: normalizeSingleLine(intent, 96) };
  }
  return { stepCount: 0, intent: "" };
}

function collectAssistantSteps(grouped = []) {
  const items = Array.isArray(grouped) ? grouped : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item || item.role !== "assistant") continue;
    const meta = item.meta || {};
    if (Array.isArray(meta.steps) && meta.steps.length) {
      return dedupeSteps(meta.steps);
    }
  }
  return [];
}

function extractSchemaFromSql(sqlText = "") {
  const sql = String(sqlText || "");
  const schemaCounts = new Map();
  const patterns = [
    /(?:from|join|update|into)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?\s*\.\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?/gi,
    /`([a-zA-Z_][a-zA-Z0-9_]*)`\.`([a-zA-Z_][a-zA-Z0-9_]*)`/g,
  ];
  patterns.forEach((re) => {
    let match;
    while ((match = re.exec(sql))) {
      const schema = String(match[1] || "").toLowerCase();
      if (!schema) continue;
      if (["information_schema", "performance_schema", "mysql", "sys"].includes(schema)) continue;
      schemaCounts.set(schema, (schemaCounts.get(schema) || 0) + 1);
    }
  });
  let best = "";
  let bestCount = 0;
  schemaCounts.forEach((count, schema) => {
    if (count > bestCount) {
      bestCount = count;
      best = schema;
    }
  });
  return best;
}

function inferDomainFromGrouped(grouped = []) {
  const steps = collectAssistantSteps(grouped);
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    const schema = extractSchemaFromSql(steps[i] && steps[i].sql ? steps[i].sql : "");
    if (schema) return sanitizeContextTag(schema, 42);
  }
  const items = Array.isArray(grouped) ? grouped : [];
  const schemaRef = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*[a-zA-Z_][a-zA-Z0-9_]*\b/g;
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item || !item.content) continue;
    let match;
    while ((match = schemaRef.exec(String(item.content || "")))) {
      const schema = String(match[1] || "").toLowerCase();
      if (!schema || ["information_schema", "performance_schema", "mysql", "sys"].includes(schema)) continue;
      return sanitizeContextTag(schema, 42);
    }
  }
  return "";
}

function inferStrategyFromGrouped(grouped = []) {
  const items = Array.isArray(grouped) ? grouped : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item || item.role !== "assistant") continue;
    const meta = item.meta || {};
    const steps = Array.isArray(meta.steps) ? meta.steps : [];
    if (!steps.length) continue;
    const toolSet = new Set(
      steps
        .map((step) => String((step && step.tool) || "").toLowerCase())
        .filter(Boolean)
    );
    const hasSearch = toolSet.has("search_objects");
    const hasSql = toolSet.has("execute_sql");
    const hasCsv = Array.isArray(meta.csv_paths) && meta.csv_paths.length > 0;
    if (hasSearch && hasSql) return hasCsv ? "탐색 + SQL 집계 + CSV" : "탐색 + SQL 집계";
    if (hasSql) return hasCsv ? "SQL 집계 + CSV" : "SQL 집계";
    if (hasSearch) return "메타 탐색";
    if (hasCsv) return "CSV 분석";
    return "단계 실행";
  }
  return "";
}

function detectRepeatExploration(grouped = []) {
  const steps = collectAssistantSteps(grouped);
  if (steps.length < 4) return false;
  const counts = new Map();
  steps.forEach((step) => {
    const intent = normalizeForCompare(getStepWorkText(step));
    if (!intent) return;
    const key = intent
      .replace(/[0-9]+/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!key) return;
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  let maxCount = 0;
  counts.forEach((count) => {
    if (count > maxCount) maxCount = count;
  });
  if (maxCount >= 3) return true;
  const loopHints = steps.filter((step) =>
    /(메타\s*탐색|후보|스키마\s*검색|재검색|탐색\s*축소)/i.test(getStepWorkText(step))
  );
  return loopHints.length >= 3;
}

function inferRecoveryProgressFromGrouped(grouped = []) {
  const items = (Array.isArray(grouped) ? grouped : []).filter((item) => item && item.role === "assistant");
  if (!items.length) {
    return { active: false, stage: 0 };
  }
  const recent = items.slice(-6);
  const corpus = recent.map((item) => String(item.content || "")).join("\n");
  const hasErrorHint = /(오류|error|실패|not\s+found|unknown\s+(table|column|database)|syntax|권한|접근\s+거부|mcp)/i.test(corpus);
  if (!hasErrorHint) {
    return { active: false, stage: 0 };
  }
  let stage = 1;
  if (/(후보|탐색|search|schema|대체\s*경로|fallback)/i.test(corpus)) stage = Math.max(stage, 2);
  if (/(검증|validate|검토|확인)/i.test(corpus)) stage = Math.max(stage, 3);
  if (/(재실행|재시도|retry|다시\s*실행|재요청)/i.test(corpus)) stage = Math.max(stage, 4);
  if (/(결론|요약|핵심\s*결론|최종)/i.test(corpus)) stage = Math.max(stage, 5);
  return { active: true, stage };
}

function normalizeDomainKey(value = "") {
  return sanitizeContextTag(value || "", 42).toLowerCase();
}

function findLatestRestoreFileFromGrouped(grouped = []) {
  const items = Array.isArray(grouped) ? grouped : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item) continue;
    const paths = extractSharedFilePaths(item.content || "");
    const restorable = paths.filter((path) => isSqlRestoreFile(path));
    if (restorable.length) {
      return restorable[0];
    }
  }
  return "";
}

function isRestoreModeActive(conversationId = activeConversationId) {
  return Boolean(
    restoreModeState.active &&
      restoreModeState.file_path &&
      restoreModeState.conversation_id &&
      conversationId &&
      restoreModeState.conversation_id === conversationId
  );
}

function setRestoreModeState(active, filePath = "", conversationId = activeConversationId) {
  const normalizedPath = String(filePath || "").trim();
  const nextActive = Boolean(active && normalizedPath && conversationId);
  restoreModeState.active = nextActive;
  restoreModeState.file_path = nextActive ? normalizedPath : "";
  restoreModeState.conversation_id = nextActive ? String(conversationId || "") : "";
  renderRestoreModePanel();
  updatePromptPlaceholder();
  renderFollowupLiveStatus();
  renderSendPreview();
}

function clearRestoreModeState(conversationId = activeConversationId, force = false) {
  if (!force && restoreModeState.conversation_id && conversationId && restoreModeState.conversation_id !== conversationId) {
    return;
  }
  restoreModeState.active = false;
  restoreModeState.file_path = "";
  restoreModeState.conversation_id = "";
  renderRestoreModePanel();
  updatePromptPlaceholder();
  renderFollowupLiveStatus();
  renderSendPreview();
}

function buildRestoreContinuePrompt() {
  if (!restoreModeState.file_path) return "";
  return `복원 모드 계속 진행: ${restoreModeState.file_path} 파일을 우선 실행하고, 실패 시 이유와 다음 대안 1개만 제시해줘.`;
}

function syncRestoreModeFromGrouped(grouped = []) {
  const latestRestoreFile = findLatestRestoreFileFromGrouped(grouped);
  if (latestRestoreFile && activeConversationId) {
    setRestoreModeState(true, latestRestoreFile, activeConversationId);
    return;
  }
  if (restoreModeState.active && restoreModeState.conversation_id && restoreModeState.conversation_id !== activeConversationId) {
    clearRestoreModeState(activeConversationId, true);
  } else {
    renderRestoreModePanel();
  }
}

function renderRestoreModePanel() {
  if (!restoreModePanelEl) return;
  const active = isRestoreModeActive();
  restoreModePanelEl.classList.toggle("hidden", !active);
  document.body.classList.toggle("restore-mode-active", active);
  if (!active) {
    if (restoreModeFileEl) restoreModeFileEl.textContent = "선택 파일 없음";
    return;
  }
  if (restoreModeFileEl) {
    restoreModeFileEl.textContent = restoreModeState.file_path;
    restoreModeFileEl.title = restoreModeState.file_path;
  }
}

function buildRecoveryFlowHtml(stage = 1) {
  const current = Math.max(1, Math.min(RECOVERY_FLOW_STEPS.length, Number(stage) || 1));
  const chunks = [];
  RECOVERY_FLOW_STEPS.forEach((label, idx) => {
    const n = idx + 1;
    const cls = n < current ? "done" : n === current ? "current" : "pending";
    chunks.push(`<span class="recovery-step ${cls}">${escapeHtml(label)}</span>`);
    if (idx < RECOVERY_FLOW_STEPS.length - 1) {
      chunks.push('<span class="recovery-sep">›</span>');
    }
  });
  return `<div class="recovery-flow">${chunks.join("")}</div>`;
}

function renderDomainDriftPanel() {
  if (!domainDriftPanelEl || !domainDriftTextEl) return;
  const expected = normalizeDomainKey(pinnedDomainHint || "");
  const state = getConversationState(activeConversationId);
  const actual = normalizeDomainKey(currentDomainHint || state.current_domain || "");
  if (!expected || !actual || expected === actual) {
    domainDriftPanelEl.classList.add("hidden");
    if (domainDriftPanelEl.dataset) {
      delete domainDriftPanelEl.dataset.driftKey;
    }
    domainDriftDismissedKey = "";
    return;
  }
  const driftKey = `${activeConversationId}:${expected}:${actual}`;
  if (domainDriftDismissedKey === driftKey) {
    domainDriftPanelEl.classList.add("hidden");
    return;
  }
  domainDriftPanelEl.dataset.driftKey = driftKey;
  domainDriftTextEl.textContent = `도메인 드리프트 감지: 고정 ${expected} 대비 최근 실행 ${actual}.`;
  domainDriftPanelEl.classList.remove("hidden");
}

function toUserFriendlyAssistantText(text = "") {
  const raw = String(text || "");
  if (!raw) return "";
  if (!/(오류|error|실패|not\s+found|unknown|mcp|syntax|중단)/i.test(raw)) {
    return raw;
  }
  let next = raw;
  next = next.replace(/요청\s*처리를?\s*중단(?:했습니다)?\./gi, "자동 복구 시도 중입니다.");
  next = next.replace(/실행을\s*중단(?:했습니다)?\./gi, "자동 복구 시도 중입니다.");
  next = next.replace(/중단(?:했습니다)?\./g, "자동 복구 시도 중입니다.");
  return next;
}

function formatTimingEntryLabel(entry) {
  const event = String(entry.event || "");
  const tool = String(entry.tool || "");
  const action = String(entry.action || "");
  const step = Number(entry.step_index || 0);
  if (event === "mcp_tool" && tool) return `도구:${tool} (step ${step || "-"})`;
  if (event === "plan") return `플랜:${action || "step"} (step ${step || "-"})`;
  if (event === "step_validation") return `검증 (step ${step || "-"})`;
  if (event === "summary_refresh") return `요약 갱신 (step ${step || "-"})`;
  if (event === "schema_meta") return `스키마 메타 (step ${step || "-"})`;
  return `${event || "unknown"} (step ${step || "-"})`;
}

async function refreshTimingPanel(force = false) {
  if (!timingPanelEl || !timingMetaEl || !timingListEl) return;
  const state = getConversationState(activeConversationId);
  if (!activeConversationId || state.status === "processing" || state.status === "idle") {
    timingPanelEl.classList.add("hidden");
    timingListEl.innerHTML = "";
    return;
  }
  timingPanelEl.classList.remove("hidden");
  const key = `${activeConversationId}:${state.status}:${state.duration_ms || ""}`;
  const now = Date.now();
  if (!force && key === timingPanelLastKey && now - timingPanelLastFetchAt < TIMING_PANEL_REFRESH_MS) {
    return;
  }
  timingPanelLastKey = key;
  timingPanelLastFetchAt = now;
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(TIMING_LOG_PATH)}&max_bytes=${TIMING_LOG_MAX_BYTES}`);
    if (!res.ok) {
      timingMetaEl.textContent = "타이밍 로그를 읽지 못했습니다.";
      timingListEl.innerHTML = "";
      return;
    }
    const text = await res.text();
    const lines = String(text || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(-1200);
    const entries = [];
    lines.forEach((line) => {
      try {
        const parsed = JSON.parse(line);
        const ms = Number(parsed && parsed.ms);
        if (!parsed || parsed.conversation_id !== activeConversationId || !Number.isFinite(ms) || ms <= 0) return;
        entries.push({ ...parsed, ms });
      } catch (err) {
        // ignore non-json lines
      }
    });
    if (!entries.length) {
      timingMetaEl.textContent = "현재 대화의 지연 데이터가 아직 없습니다.";
      timingListEl.innerHTML = "";
      return;
    }
    const agg = new Map();
    entries.forEach((entry) => {
      const label = formatTimingEntryLabel(entry);
      const current = agg.get(label) || { label, total: 0, count: 0 };
      current.total += Number(entry.ms || 0);
      current.count += 1;
      agg.set(label, current);
    });
    const top = [...agg.values()]
      .sort((a, b) => b.total - a.total)
      .slice(0, 3);
    timingMetaEl.textContent = `최근 실행 기준 상위 ${top.length}개 단계`;
    timingListEl.innerHTML = top
      .map((item) => `<li><strong>${escapeHtml(item.label)}</strong> · ${formatDurationMsLabel(item.total)} · ${item.count}회</li>`)
      .join("");
  } catch (err) {
    timingMetaEl.textContent = "타이밍 패널 갱신 실패";
    timingListEl.innerHTML = "";
  }
}

function deriveFollowupContextFromGrouped(grouped = []) {
  const items = Array.isArray(grouped) ? grouped : [];
  let latestUserRaw = "";
  let latestAssistantQuestion = "";
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item) continue;
    if (!latestUserRaw && item.role === "user") {
      latestUserRaw = String(item.content || "").trim();
    }
    if (!latestAssistantQuestion && item.role === "assistant" && isQuestionContent(item.content || "")) {
      latestAssistantQuestion = String(item.content || "").trim();
    }
    if (latestUserRaw && latestAssistantQuestion) break;
  }
  const parsedUser = parseFollowupEnvelope(latestUserRaw);
  const latestUser = parsedUser.userRequest || latestUserRaw;
  const latestParsedIntent = parsedUser.intent || "";
  const latestParsedConstraints = parsedUser.constraints || "";
  const intentBase = sanitizeFollowupText(latestUser, 120) || sanitizeFollowupText(latestParsedIntent, 120);
  const intent = !isLikelySqlText(intentBase) ? normalizeSingleLine(intentBase || "", 120) : "";
  let constraints = "";
  if (latestParsedConstraints && !isLikelySqlText(latestParsedConstraints)) {
    constraints = sanitizeFollowupText(latestParsedConstraints, 140);
  } else if (
    latestUser &&
    !isLikelySqlText(latestUser) &&
    /(제외|포함|이상|이하|상위|하위|최근|limit|only|조건|필터)/i.test(latestUser)
  ) {
    constraints = sanitizeFollowupText(latestUser, 140);
  } else if (latestAssistantQuestion && !isLikelySqlText(latestAssistantQuestion)) {
    constraints = sanitizeFollowupText(latestAssistantQuestion, 140);
  }
  return { intent, constraints };
}

function setFollowupContextFields(intent = "", constraints = "", force = false) {
  if (!followupIntentEl || !followupConstraintsEl) return;
  if (!force && followupManualEdit && followupContextConversationId === activeConversationId) return;
  followupIntentEl.value = String(intent || "");
  followupConstraintsEl.value = String(constraints || "");
  renderFollowupLiveStatus();
  renderSendPreview();
}

function getFollowupContextPayload() {
  const intent = followupIntentEl ? String(followupIntentEl.value || "").trim() : "";
  const constraints = followupConstraintsEl ? String(followupConstraintsEl.value || "").trim() : "";
  return { intent, constraints };
}

function composeMessageWithFollowup(message) {
  const raw = String(message || "").trim();
  if (!raw) return "";
  const parsed = parseFollowupEnvelope(raw);
  const userRequest = parsed.userRequest || raw;
  const applyContext = followupApplyArmed || isRestoreModeActive();
  if (!applyContext) {
    return userRequest;
  }
  const ctx = getFollowupContextPayload();
  const pin = getPinnedContextPayload();
  const useDraft = Boolean(followupManualEdit && followupContextConversationId === activeConversationId);
  const intent = sanitizeFollowupText(useDraft ? (ctx.intent || parsed.intent) : parsed.intent, 180);
  let constraints = sanitizeFollowupText(useDraft ? (ctx.constraints || parsed.constraints) : parsed.constraints, 220);
  if (pin.domain) {
    constraints = mergeConstraintLine(constraints, `고정 도메인 ${pin.domain}`, 220);
  }
  if (pin.strategy) {
    constraints = mergeConstraintLine(constraints, `고정 전략 ${pin.strategy}`, 220);
  }
  if (isRestoreModeActive() && restoreModeState.file_path) {
    constraints = mergeConstraintLine(constraints, `복원 모드 ${restoreModeState.file_path} 우선 실행`, 220);
  }
  if (!intent && !constraints) return userRequest;
  const lines = ["[이어받기 컨텍스트]"];
  if (intent) lines.push(`의도: ${intent}`);
  if (constraints) lines.push(`제약: ${constraints}`);
  lines.push(`[사용자 요청] ${userRequest}`);
  return lines.join("\n");
}

function normalizePromptDraftFromFollowup() {
  if (!promptBox) return;
  const raw = String(promptBox.value || "").trim();
  if (!raw) return;
  const parsed = parseFollowupEnvelope(raw);
  if (!parsed.wrapped) return;
  const userRequest = parsed.userRequest || "";
  if (!followupManualEdit) {
    if (parsed.intent && !isLikelySqlText(parsed.intent) && followupIntentEl && !followupIntentEl.value.trim()) {
      followupIntentEl.value = sanitizeFollowupText(parsed.intent, 120);
    }
    if (
      parsed.constraints &&
      !isLikelySqlText(parsed.constraints) &&
      followupConstraintsEl &&
      !followupConstraintsEl.value.trim()
    ) {
      followupConstraintsEl.value = sanitizeFollowupText(parsed.constraints, 140);
    }
  }
  promptBox.value = userRequest;
  renderFollowupLiveStatus();
  renderSendPreview();
}

function renderRunHud() {
  // 상단 HUD 비활성화 — 모든 진행 상황은 대화 로그 내 progress 버블에 표시
  if (!runHudEl) return;
  runHudEl.classList.add("hidden");
  runHudEl.innerHTML = "";
}

function createDateSeparator(dateKey) {
  const sep = document.createElement("div");
  sep.className = "date-separator";
  sep.dataset.dateKey = dateKey;
  const label = document.createElement("span");
  label.className = "date-sep-label";
  label.textContent = formatDateLabel(dateKey);
  label.title = "\uD074\uB9AD\uD558\uC5EC \uD574\uB2F9 \uB0A0\uC9DC \uCE98\uB9B0\uB354 \uC5F4\uAE30";
  label.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("openCalDate", { detail: dateKey }));
  });
  sep.appendChild(label);
  return sep;
}

function ensureHistoryIndicator() {
  let el = document.getElementById("historyLoading");
  if (el) return el;
  el = document.createElement("div");
  el.id = "historyLoading";
  el.className = "history-loading";
  el.textContent = "이전 대화 로딩 중...";
  return el;
}

function ensureHistoryMoreButton() {
  let el = document.getElementById("historyMore");
  if (el) return el;
  el = document.createElement("button");
  el.id = "historyMore";
  el.type = "button";
  el.className = "history-more";
  el.textContent = "이전 대화 더보기";
  el.addEventListener("click", () => loadOlderHistory());
  return el;
}

function ensureHistoryTopElements() {
  const indicator = ensureHistoryIndicator();
  const moreBtn = ensureHistoryMoreButton();
  if (!indicator.parentElement || !moreBtn.parentElement) {
    chatLogEl.replaceChildren(indicator, moreBtn);
    return;
  }
  if (chatLogEl.firstChild !== indicator) {
    chatLogEl.insertBefore(indicator, chatLogEl.firstChild);
  }
  if (indicator.nextSibling !== moreBtn) {
    chatLogEl.insertBefore(moreBtn, indicator.nextSibling);
  }
}

function setHistoryLoading(show) {
  const indicator = ensureHistoryIndicator();
  if (show) {
    indicator.classList.add("show");
  } else {
    indicator.classList.remove("show");
  }
}

function setHistoryMoreVisible(show) {
  historyMoreAvailable = Boolean(show);
  updateHistoryMoreButtonVisibility();
}

function updateHistoryMoreButtonVisibility() {
  const moreBtn = ensureHistoryMoreButton();
  const nearTop = chatLogEl ? chatLogEl.scrollTop <= 100 : false;
  if (historyMoreAvailable && nearTop) {
    moreBtn.classList.add("show");
  } else {
    moreBtn.classList.remove("show");
  }
}

function extractSharedFilePaths(text = "") {
  const raw = String(text || "");
  const matches = raw.match(/(?:\/shared\/[^\s"'`)\]}]+|shared\/[^\s"'`)\]}]+)/g) || [];
  const unique = [];
  const seen = new Set();
  matches.forEach((item) => {
    const normalized = String(item || "").replace(/^[.\/]*/, "/").replace(/\/+/g, "/").trim();
    if (!normalized) return;
    if (!normalized.startsWith("/shared/")) return;
    if (seen.has(normalized)) return;
    seen.add(normalized);
    unique.push(normalized);
  });
  return unique;
}

function isSqlRestoreFile(path = "") {
  const lower = String(path || "").toLowerCase();
  return [".sql", ".dump"].some((ext) => lower.endsWith(ext));
}

function createMessageElement(role, text, meta = {}, createdAt = "") {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.dataset.dateKey = extractDateKey(createdAt);
  if (createdAt) msg.dataset.createdAt = String(createdAt);
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const rawText = String(text || "");
  const mergedMeta = mergeMeta({}, meta || {});
  const steps = Array.isArray(mergedMeta.steps) ? mergedMeta.steps : [];
  const fallbackSqlText = (() => {
    const sqlSteps = steps.filter((step) => step && step.sql);
    return sqlSteps.length ? sqlSteps[sqlSteps.length - 1].sql : "";
  })();
  const fallbackCsvPaths = (() => {
    const values = [];
    steps.forEach((step) => {
      getStepCsvPaths(step).forEach((path) => values.push(path));
    });
    return [...new Set(values.filter(Boolean))];
  })();
  const sqlText =
    mergedMeta.sql ||
    (Array.isArray(mergedMeta.sqls) && mergedMeta.sqls.length ? mergedMeta.sqls[mergedMeta.sqls.length - 1] : "") ||
    fallbackSqlText;
  const csvPaths = Array.isArray(mergedMeta.csv_paths) && mergedMeta.csv_paths.length
    ? mergedMeta.csv_paths
    : Array.isArray(mergedMeta.csvPaths) && mergedMeta.csvPaths.length
      ? mergedMeta.csvPaths
      : mergedMeta.csvPath
        ? [mergedMeta.csvPath]
        : fallbackCsvPaths;
  const stepsLabel = steps.length ? `작업 상세 (${steps.length})` : "";
  const rationale = mergedMeta.rationale || mergedMeta.reason || "";
  const isAssistant = role === "assistant";
  const displayText = isAssistant ? toUserFriendlyAssistantText(rawText) : rawText;
  const markdownPayload =
    isAssistant && shouldRenderAssistantMarkdown(role, displayText)
      ? renderMarkdownSource(displayText)
      : { html: "", text: displayText };
  const renderedDisplayText = markdownPayload.text || displayText;
  const keepsMarkdownBody =
    isAssistant && markdownPayload.html && hasStructuredMarkdownSource(displayText);
  const sharedFiles = isAssistant ? extractSharedFilePaths(rawText) : [];
  const sqlRestoreFiles = sharedFiles.filter((path) => isSqlRestoreFile(path));
  const conclusionText = isAssistant ? buildConclusionText(renderedDisplayText, 3) : "";
  const isBodyRedundant =
    isAssistant && conclusionText && !keepsMarkdownBody
      ? isRedundantAssistantBody(renderedDisplayText, conclusionText)
      : false;
  if (isAssistant && conclusionText) {
    const conclusionCard = document.createElement("div");
    conclusionCard.className = "answer-conclusion";
    const title = document.createElement("div");
    title.className = "answer-conclusion-title";
    title.textContent = "핵심 결론";
    const body = document.createElement("pre");
    body.className = "answer-conclusion-text";
    body.textContent = conclusionText;
    conclusionCard.appendChild(title);
    conclusionCard.appendChild(body);
    bubble.appendChild(conclusionCard);
  }

  if (!isBodyRedundant) {
    const content =
      isAssistant && markdownPayload.html
        ? createMarkdownOutputNode(markdownPayload.html, steps)
        : createPlainOutputNode(displayText);
    if (isAssistant && shouldCollapseAssistantOutput(renderedDisplayText, mergedMeta)) {
      const detail = document.createElement("details");
      detail.className = "answer-detail";
      const summary = document.createElement("summary");
      summary.textContent = "상세 답변 보기";
      detail.appendChild(summary);
      detail.appendChild(content);
      detail.addEventListener("toggle", () => {
        if (detail.open) {
          requestAnimationFrame(() => syncAnswerExpandedState(msg, detail));
          return;
        }
        syncAnswerExpandedState(msg, detail);
      });
      syncAnswerExpandedState(msg, detail);
      bubble.appendChild(detail);
    } else {
      bubble.appendChild(content);
    }
  }

  if (isAssistant && isMaxStepReachedText(displayText) && !isRestoreModeActive()) {
    const actionWrap = document.createElement("div");
    actionWrap.className = "maxstep-actions";
    const ctaList = [
      { label: "결론만 보기", prompt: "방금 작업의 결론만 핵심 3줄로 요약해줘." },
      { label: "다른 경로 재시도", prompt: "같은 목표를 다른 경로로 재시도해줘. 탐색 범위를 더 좁혀줘." },
      { label: "질문 최소화 모드", prompt: "질문을 최소화하고 바로 실행 가능한 가정으로 진행해줘." },
    ];
    ctaList.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "mini ghost";
      btn.textContent = item.label;
      btn.addEventListener("click", () => sendMessage(item.prompt));
      actionWrap.appendChild(btn);
    });
    bubble.appendChild(actionWrap);
  }

  const sqlResultPaths = sqlText ? findCsvPathsForSql(sqlText, csvPaths, steps) : [];
  if (role === "assistant" || sqlText || csvPaths.length) {
    const footer = document.createElement("div");
    footer.className = "msg-footer";
    let extraTools = null;
    let extraToolsBody = null;
    const ensureExtraTools = () => {
      if (extraTools) return;
      extraTools = document.createElement("details");
      extraTools.className = "msg-tools";
      const summary = document.createElement("summary");
      summary.textContent = "추가 도구";
      extraToolsBody = document.createElement("div");
      extraToolsBody.className = "msg-tools-body";
      extraTools.appendChild(summary);
      extraTools.appendChild(extraToolsBody);
    };
    const addExtraTool = (label, onClick) => {
      ensureExtraTools();
      const btn = document.createElement("button");
      btn.className = "mini ghost";
      btn.textContent = label;
      btn.addEventListener("click", onClick);
      extraToolsBody.appendChild(btn);
    };

    if (sqlText) {
      const sqlBtn = document.createElement("button");
      sqlBtn.className = "mini ghost";
      sqlBtn.textContent = "SQL 보기";
      sqlBtn.addEventListener("click", () =>
        openSqlResultModal({
          sql: sqlText,
        }).catch(() => showToast("SQL 보기 실패"))
      );
      footer.appendChild(sqlBtn);
      footer.appendChild(createCsvPreviewButton(sqlResultPaths, steps));
    }
    if (!sqlText && csvPaths.length) {
      footer.appendChild(createCsvPreviewButton(csvPaths, steps));
    }
    if (isAssistant && sharedFiles.length) {
      const restoreBtn = document.createElement("button");
      restoreBtn.className = "mini ghost restore-cta-btn";
      if (sqlRestoreFiles.length) {
        restoreBtn.textContent =
          sqlRestoreFiles.length > 1 ? `복원 실행 (${sqlRestoreFiles.length})` : "복원 실행";
        const targetPath = sqlRestoreFiles[0];
        restoreBtn.title = `SQL 파일 실행: ${targetPath}`;
        restoreBtn.addEventListener("click", () => {
          if (activeConversationId) {
            setRestoreModeState(true, targetPath, activeConversationId);
          }
          sendMessage(`다음 SQL 복원 파일을 실행해줘: ${targetPath}`);
        });
      } else {
        restoreBtn.textContent = "복원 실행 불가";
        restoreBtn.disabled = true;
        restoreBtn.title = "복원 실행은 .sql 또는 .dump 파일에서만 가능합니다.";
      }
      footer.appendChild(restoreBtn);
    }
    if (role === "assistant") {
      addExtraTool("원문 보기", () => {
        showModal("응답 원문", rawText || "");
      });

      if (rationale) {
        addExtraTool("근거 보기", () => {
          showModal("실행 근거", stringifyValue(rationale));
        });
      }
      addExtraTool("출력 복사", () => {
        navigator.clipboard
          .writeText(rawText || displayText || "")
          .then(() => showToast("복사 완료"))
          .catch(() => showToast("복사 실패"));
      });
      if (isAssistant && conclusionText) {
        addExtraTool("결론 보기", () => {
          showModal("핵심 결론", conclusionText);
        });
      }
    }
    // duration_ms 뱃지 (답변 소요 시간)
    if (isAssistant && mergedMeta.duration_ms != null) {
      const durBadge = document.createElement("span");
      durBadge.className = "msg-duration-badge";
      durBadge.textContent = formatDurationMsLabel(mergedMeta.duration_ms);
      durBadge.title = `소요 시간: ${Number(mergedMeta.duration_ms).toLocaleString()}ms`;
      footer.appendChild(durBadge);
    }
    if (extraTools) {
      footer.appendChild(extraTools);
    }
    bubble.appendChild(footer);
  }

  if (role === "assistant" && steps.length) {
    const dropdown = buildStepsDropdown(steps, stepsLabel);
    if (dropdown) bubble.appendChild(dropdown);
  }

  msg.appendChild(bubble);
  return msg;
}

function getConversationState(conversationId) {
  if (!conversationId) {
    return {
      status: "idle",
      duration_ms: null,
      updated_at: null,
      step_count: 0,
      current_intent: "",
      current_domain: "",
      current_strategy: "",
      repeat_explore: false,
      recovery_active: false,
      recovery_stage: 0,
    };
  }
  if (!conversationState.has(conversationId)) {
    conversationState.set(conversationId, {
      status: "idle",
      duration_ms: null,
      updated_at: null,
      step_count: 0,
      current_intent: "",
      current_domain: "",
      current_strategy: "",
      repeat_explore: false,
      recovery_active: false,
      recovery_stage: 0,
    });
  }
  return conversationState.get(conversationId);
}

function markCancelOverride(conversationId, ttlMs = CANCEL_OVERRIDE_MS) {
  if (!conversationId) return;
  cancelOverrideUntil.set(conversationId, Date.now() + Math.max(0, Number(ttlMs) || 0));
}

function clearCancelOverride(conversationId) {
  if (!conversationId) return;
  cancelOverrideUntil.delete(conversationId);
}

function isCancelOverrideActive(conversationId) {
  if (!conversationId) return false;
  const expireAt = Number(cancelOverrideUntil.get(conversationId) || 0);
  if (!Number.isFinite(expireAt) || expireAt <= 0) return false;
  if (Date.now() >= expireAt) {
    cancelOverrideUntil.delete(conversationId);
    return false;
  }
  return true;
}

function setConversationState(conversationId, patch) {
  if (!conversationId) return;
  const current = getConversationState(conversationId);
  const next = {
    ...current,
    ...patch,
    updated_at: new Date().toISOString(),
  };
  const hasStatusPatch = Boolean(patch && Object.prototype.hasOwnProperty.call(patch, "status"));
  if (hasStatusPatch) {
    const incomingStatus = String(patch.status || "").toLowerCase();
    if (incomingStatus === "processing" && isCancelOverrideActive(conversationId)) {
      next.status = "canceled";
      if (current.started_at) {
        next.started_at = current.started_at;
      }
    } else if (incomingStatus === "done" || incomingStatus === "error" || incomingStatus === "idle") {
      clearCancelOverride(conversationId);
    }
  }
  if (next.status === "done") {
    const ms = Number(next.duration_ms);
    if (Number.isFinite(ms) && ms > 0) {
      recentDurationsMs.push(ms);
      if (recentDurationsMs.length > 20) {
        recentDurationsMs.splice(0, recentDurationsMs.length - 20);
      }
    }
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, "current_domain")) {
    next.current_domain = sanitizeContextTag(patch.current_domain || "", 42);
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, "current_strategy")) {
    next.current_strategy = sanitizeContextTag(patch.current_strategy || "", 72);
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, "repeat_explore")) {
    next.repeat_explore = Boolean(patch.repeat_explore);
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, "recovery_active")) {
    next.recovery_active = Boolean(patch.recovery_active);
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, "recovery_stage")) {
    const stage = Number(patch.recovery_stage);
    next.recovery_stage = Number.isFinite(stage) ? Math.max(0, Math.min(RECOVERY_FLOW_STEPS.length, Math.floor(stage))) : 0;
  }
  conversationState.set(conversationId, next);
}

function startConversationPoll(conversationId) {
  if (!conversationId) return;
  const nextCount = (conversationPollCounts.get(conversationId) || 0) + 1;
  conversationPollCounts.set(conversationId, nextCount);
  if (conversationPollers.has(conversationId)) {
    return;
  }
  const handle = setInterval(() => {
    refreshConversations().catch(() => {});
    if (conversationId === activeConversationId) {
      refreshActiveConversation(false);
    }
  }, STATUS_POLL_MS);
  conversationPollers.set(conversationId, handle);
}

function stopConversationPoll(conversationId) {
  const current = conversationPollCounts.get(conversationId) || 0;
  const next = current - 1;
  if (next > 0) {
    conversationPollCounts.set(conversationId, next);
    return;
  }
  conversationPollCounts.delete(conversationId);
  const handle = conversationPollers.get(conversationId);
  if (handle) {
    clearInterval(handle);
    conversationPollers.delete(conversationId);
  }
}

function renderHeaderStatus() {
  if (!lastDurationEl) return;
  const state = getConversationState(activeConversationId);
  if (!activeConversationId) {
    lastDurationEl.textContent = "대기 중";
    currentDomainHint = "";
    currentStrategyHint = "";
    renderContextBadges();
    renderFollowupLiveStatus();
    renderSendPreview();
    renderDomainDriftPanel();
    renderRestoreModePanel();
    updateComposerActions();
    renderRunHud();
    refreshTimingPanel().catch(() => {});
    return;
  }
  if (!currentDomainHint || !currentStrategyHint) {
    currentDomainHint = sanitizeContextTag(state.current_domain || "", 42) || currentDomainHint;
    currentStrategyHint = sanitizeContextTag(state.current_strategy || "", 72) || currentStrategyHint;
  }
  renderContextBadges();
  renderFollowupLiveStatus();
  renderSendPreview();
  renderDomainDriftPanel();
  renderRestoreModePanel();
  if (state.status === "processing") {
    lastDurationEl.textContent = "처리 중";
    updateComposerActions();
    renderRunHud();
    refreshTimingPanel().catch(() => {});
    return;
  }
  if (state.status === "error") {
    lastDurationEl.textContent = state.recovery_active ? "자동 복구 시도 중" : "오류 발생";
    updateComposerActions();
    renderRunHud();
    refreshTimingPanel().catch(() => {});
    return;
  }
  if (state.status === "canceled") {
    lastDurationEl.textContent = "요청 취소됨";
    updateComposerActions();
    renderRunHud();
    refreshTimingPanel().catch(() => {});
    return;
  }
  if (state.status === "done" && state.duration_ms !== null && state.duration_ms !== undefined) {
    lastDurationEl.textContent = `최근 처리: ${state.duration_ms} ms`;
    updateComposerActions();
    renderRunHud();
    refreshTimingPanel().catch(() => {});
    return;
  }
  lastDurationEl.textContent = "대기 중";
  updateComposerActions();
  renderRunHud();
  refreshTimingPanel().catch(() => {});
}

function updateComposerActions() {
  const sendBtn = document.getElementById("btnSend");
  const cancelBtn = document.getElementById("btnCancel");
  if (!sendBtn || !cancelBtn) return;
  const state = getConversationState(activeConversationId);
  const processing = state.status === "processing";
  sendBtn.classList.toggle("hidden", processing);
  cancelBtn.classList.toggle("hidden", !processing);
  promptBox.disabled = processing;
}

function isNearBottom() {
  const threshold = 80;
  return chatLogEl.scrollHeight - chatLogEl.scrollTop - chatLogEl.clientHeight < threshold;
}

function ensureDateSeparatorForAppend(dateKey) {
  const nodes = Array.from(chatLogEl.children).filter((node) => node.id !== "historyLoading");
  let lastDateKey = null;
  for (let i = nodes.length - 1; i >= 0; i -= 1) {
    const node = nodes[i];
    if (node.classList.contains("date-separator")) {
      lastDateKey = node.dataset.dateKey || null;
      break;
    }
    if (node.classList.contains("msg")) {
      lastDateKey = node.dataset.dateKey || null;
      break;
    }
  }
  if (!lastDateKey || lastDateKey !== dateKey) {
    chatLogEl.appendChild(createDateSeparator(dateKey));
  }
}

function appendMessage(role, text, meta = {}, options = {}) {
  const dateKey = extractDateKey();
  const shouldStickBottom = isNearBottom();
  ensureDateSeparatorForAppend(dateKey);
  const msg = createMessageElement(role, text, meta, dateKey);
  chatLogEl.appendChild(msg);
  if (options.forceScroll || role === "user" || shouldStickBottom) {
    scrollToBottom();
  }
}

function prependMessages(items) {
  if (!items.length) return;
  ensureHistoryTopElements();
  const existingNodes = Array.from(chatLogEl.children).filter(
    (node) => node.id !== "historyLoading" && node.id !== "historyMore"
  );
  const firstNode = existingNodes[0] || null;
  let firstDateKey = null;
  if (firstNode) {
    if (firstNode.classList.contains("date-separator")) {
      firstDateKey = firstNode.dataset.dateKey || null;
    } else if (firstNode.classList.contains("msg")) {
      firstDateKey = firstNode.dataset.dateKey || null;
    }
  }
  const anchor = (() => {
    const containerTop = chatLogEl.scrollTop;
    for (const node of existingNodes) {
      const nodeTop = node.offsetTop;
      const nodeBottom = nodeTop + node.offsetHeight;
      if (nodeBottom >= containerTop) {
        return { node, offset: nodeTop - containerTop };
      }
    }
    return null;
  })();
  const prevHeight = chatLogEl.scrollHeight;
  const nodes = [];
  let lastDate = null;
  const groupedItems = groupConversationMessages(items);
  groupedItems.forEach((item) => {
    const dateKey = extractDateKey(item.created_at);
    if (dateKey !== lastDate) {
      nodes.push(createDateSeparator(dateKey));
      lastDate = dateKey;
    }
    const msg = createMessageElement(item.role, item.content, item.meta || {}, item.created_at);
    if (item.id) {
      msg.id = `msg-${item.id}`;
      msg.dataset.msgId = String(item.id);
    }
    nodes.push(msg);
  });
  if (nodes.length) {
    const lastNode = nodes[nodes.length - 1];
    if (lastNode.classList.contains("date-separator") && lastNode.dataset.dateKey === firstDateKey) {
      nodes.pop();
    }
  }
  let insertBefore = null;
  for (const child of chatLogEl.children) {
    if (child.id === "historyLoading" || child.id === "historyMore") continue;
    insertBefore = child;
    break;
  }
  nodes.forEach((node) => {
    if (insertBefore) {
      chatLogEl.insertBefore(node, insertBefore);
    } else {
      chatLogEl.appendChild(node);
    }
  });
  const newHeight = chatLogEl.scrollHeight;
  if (anchor && anchor.node && anchor.node.isConnected) {
    const newTop = anchor.node.offsetTop;
    chatLogEl.scrollTop = newTop - anchor.offset;
  } else {
    chatLogEl.scrollTop += newHeight - prevHeight;
  }
}

function buildRenderSignature(groupedItems = []) {
  if (!Array.isArray(groupedItems) || !groupedItems.length) return "";
  const last = groupedItems[groupedItems.length - 1];
  const meta = last && last.meta ? last.meta : {};
  const steps = Array.isArray(meta.steps) ? meta.steps.length : 0;
  const csvCount = Array.isArray(meta.csv_paths) ? meta.csv_paths.length : 0;
  const contentLen = (last && last.content ? String(last.content).length : 0) || 0;
  return `${last && last.id ? last.id : ""}:${steps}:${csvCount}:${contentLen}`;
}

function updateConversationStats(payload = {}) {
  if (!conversationStatsEl) return;
  const total = payload.total_messages ?? payload.total ?? null;
  const userTotal = payload.total_user_messages ?? payload.user_total ?? null;
  if (total === null || total === undefined) {
    conversationStatsEl.textContent = conversationTotalCount
      ? `대화 ${conversationTotalCount} · 메시지 0`
      : "메시지 0";
    return;
  }
  if (userTotal !== null && userTotal !== undefined) {
    conversationStatsEl.textContent = conversationTotalCount
      ? `대화 ${conversationTotalCount} · 메시지 ${total} · 사용자 ${userTotal}`
      : `메시지 ${total} · 사용자 ${userTotal}`;
  } else {
    conversationStatsEl.textContent = conversationTotalCount
      ? `대화 ${conversationTotalCount} · 메시지 ${total}`
      : `메시지 ${total}`;
  }
}

function formatTooltipText(message) {
  const text = String(message || "").trim().replace(/\s+/g, " ");
  if (!text) return "내용 없음";
  return text.length > 60 ? `${text.slice(0, 60)}...` : text;
}

function renderTimelineMarkers(groupedItems = []) {
  if (!timelineEl) return;
  timelineEl.innerHTML = "";
  if (!Array.isArray(groupedItems) || !groupedItems.length) {
    return;
  }
  const userItems = groupedItems.filter((item) => item && item.role === "user" && item.id);
  if (!userItems.length) return;
  userItems.forEach((item) => {
    const marker = document.createElement("div");
    marker.className = "timeline-marker";
    marker.dataset.targetId = `msg-${item.id}`;
    const tooltip = document.createElement("div");
    tooltip.className = "timeline-tooltip";
    const timeLabel = item.created_at ? String(item.created_at).replace("T", " ") : "";
    tooltip.textContent = `${timeLabel}\n${formatTooltipText(item.content)}`;
    marker.appendChild(tooltip);
    marker.addEventListener("click", () => {
      const target = document.getElementById(`msg-${item.id}`);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    });
    timelineEl.appendChild(marker);
  });
  updateTimelinePositions();
}

function updateTimelinePositions() {
  if (!timelineEl || !chatLogEl) return;
  const height = chatLogEl.scrollHeight || 1;
  const timelineHeight = timelineEl.clientHeight || 1;
  const markers = Array.from(timelineEl.querySelectorAll(".timeline-marker"));
  markers.forEach((marker) => {
    const targetId = marker.dataset.targetId;
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    const ratio = Math.min(Math.max(target.offsetTop / height, 0), 1);
    const markerHalf = (marker.offsetHeight || 10) / 2;
    const topPx = Math.min(
      Math.max(ratio * timelineHeight, markerHalf),
      Math.max(timelineHeight - markerHalf, markerHalf)
    );
    marker.style.top = `${topPx}px`;
  });
}

function replaceMessages(items, groupedItems = null) {
  ensureHistoryTopElements();
  // progress 버블 보존: replaceChildren 전에 떼어두고 마지막에 다시 붙임
  const progressBubble = chatLogEl.querySelector(".msg-progress-live");
  if (progressBubble) progressBubble.remove();
  chatLogEl.replaceChildren(ensureHistoryIndicator(), ensureHistoryMoreButton());
  const grouped = groupedItems || groupConversationMessages(items);
  if (!grouped.length) {
    const msg = createMessageElement("assistant", "대화 기록이 없습니다.");
    chatLogEl.appendChild(msg);
    lastRenderedSignature = "";
    renderTimelineMarkers([]);
    return;
  }
  let lastDate = null;
  grouped.forEach((item) => {
    const dateKey = extractDateKey(item.created_at);
    if (dateKey !== lastDate) {
      chatLogEl.appendChild(createDateSeparator(dateKey));
      lastDate = dateKey;
    }
    const msg = createMessageElement(item.role, item.content, item.meta || {}, item.created_at);
    if (item.id) {
      msg.id = `msg-${item.id}`;
      msg.dataset.msgId = String(item.id);
    }
    chatLogEl.appendChild(msg);
  });
  const last = grouped[grouped.length - 1];
  lastRenderedMessageId = last && last.id ? last.id : lastRenderedMessageId;
  lastRenderedSignature = buildRenderSignature(grouped);
  renderTimelineMarkers(grouped);
  // progress 버블 복원
  if (progressBubble) chatLogEl.appendChild(progressBubble);
}

function syncActiveConversationMetaFromGrouped(grouped = []) {
  if (!activeConversationId) return;
  const stepInfo = getLatestStepInfoFromGrouped(grouped);
  const domain = inferDomainFromGrouped(grouped);
  const strategy = inferStrategyFromGrouped(grouped);
  const repeatExplore = detectRepeatExploration(grouped);
  const recovery = inferRecoveryProgressFromGrouped(grouped);
  if (stepInfo.stepCount || stepInfo.intent) {
    setConversationState(activeConversationId, {
      step_count: stepInfo.stepCount || 0,
      current_intent: stepInfo.intent || "",
      current_domain: domain || "",
      current_strategy: strategy || "",
      repeat_explore: repeatExplore,
      recovery_active: recovery.active,
      recovery_stage: recovery.stage,
    });
  } else {
    setConversationState(activeConversationId, {
      current_domain: domain || "",
      current_strategy: strategy || "",
      repeat_explore: repeatExplore,
      recovery_active: recovery.active,
      recovery_stage: recovery.stage,
    });
  }
  currentDomainHint = domain || "";
  currentStrategyHint = strategy || "";
  renderContextBadges();
  if (followupContextConversationId !== activeConversationId) {
    followupManualEdit = false;
  }
  const ctx = deriveFollowupContextFromGrouped(grouped);
  setFollowupContextFields(ctx.intent, ctx.constraints, followupContextConversationId !== activeConversationId);
  followupContextConversationId = activeConversationId;
  renderFollowupLiveStatus();
  syncRestoreModeFromGrouped(grouped);
  renderDomainDriftPanel();
}

function scrollToBottom() {
  chatLogEl.scrollTop = chatLogEl.scrollHeight;
}

function showModal(title, content, downloadUrl = "") {
  resetSqlResultModalState();
  const bodyClasses = String(title || "").includes("SQL") ? ["modal-sql"] : [];
  const { modal, modalBody, modalDownload, modalCopy } = prepareModalShell(title, bodyClasses);
  if (content && content.html) {
    modalBody.innerHTML = content.html;
    modalCopyText = content.copyText || modalBody.innerText || "";
    if (modalCopy) modalCopy.textContent = content.isSql ? "복사" : "복사(TSV)";
  } else {
    const text = String(content || "(내용 없음)");
    const pre = document.createElement("pre");
    pre.textContent = text;
    modalBody.appendChild(pre);
    modalCopyText = text;
    if (modalCopy) modalCopy.textContent = "복사";
  }
  if (downloadUrl) {
    modalDownload.href = downloadUrl;
    modalDownload.classList.remove("hidden");
  } else {
    modalDownload.classList.add("hidden");
  }
  modal.classList.add("show");
}

function hideModal() {
  const modal = document.getElementById("modal");
  const returnTarget = sqlResultModalState.open ? sqlResultModalState.returnTarget : null;
  resetSqlResultModalState();
  if (returnTarget && returnTarget.type === "csv" && Array.isArray(returnTarget.paths) && returnTarget.paths.length) {
    openCsvPreviewModal(returnTarget.paths, returnTarget.index || 0, returnTarget.steps || []).catch(() => {
      modal.classList.remove("show");
      hideCsvPagerDock();
    });
    return;
  }
  modal.classList.remove("show");
  hideCsvPagerDock();
  const modalBody = document.getElementById("modalBody");
  if (modalBody) {
    modalBody.classList.remove("modal-csv");
    modalBody.classList.remove("modal-sql-result");
  }
}

async function fetchCsvPreview(path) {
  const res = await fetch(`/api/file?path=${encodeURIComponent(path)}&max_bytes=65536`);
  if (!res.ok) {
    return "CSV 미리보기 실패";
  }
  return await res.text();
}

async function apiFetch(path, body = null) {
  const options = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "요청 실패");
  }
  return data;
}

function loadSuggestionCache() {
  try {
    const raw = localStorage.getItem(SUGGESTION_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) return null;
    return parsed;
  } catch (err) {
    return null;
  }
}

function saveSuggestionCache(items) {
  try {
    localStorage.setItem(
      SUGGESTION_CACHE_KEY,
      JSON.stringify({ items, updated_at: Date.now() })
    );
  } catch (err) {
    // ignore
  }
}

function pickRandomSuggestion(items = []) {
  if (!items.length) return "";
  const idx = Math.floor(Math.random() * items.length);
  return items[idx];
}

function normalizeSuggestionText(value) {
  const parsed = parseFollowupEnvelope(value);
  const base = parsed.userRequest || String(value || "");
  return sanitizeFollowupText(base, 180);
}

async function refreshSuggestionCache() {
  try {
    const data = await apiFetch("/api/suggestions");
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length) {
      saveSuggestionCache(items);
      return items;
    }
  } catch (err) {
    // ignore
  }
  return [];
}

async function updatePromptPlaceholder() {
  if (!promptBox) return;
  if (isRestoreModeActive() && restoreModeState.file_path) {
    promptBox.placeholder = `복원 모드: ${shortPath(restoreModeState.file_path)} 계속 진행`;
    return;
  }
  let cached = loadSuggestionCache();
  const now = Date.now();
  let items = cached && Array.isArray(cached.items) ? cached.items : [];
  if (!items.length || !cached || now - (cached.updated_at || 0) > SUGGESTION_CACHE_TTL_MS) {
    items = await refreshSuggestionCache();
  }
  const suggestion = normalizeSuggestionText(pickRandomSuggestion(items));
  if (suggestion) {
    promptBox.placeholder = suggestion;
  }
}

function loadApiKeyIntoInputs() {
  const cached = loadApiKeyCache();
  const model = cached && isAllowedApiModel(cached.model) ? cached.model : getApiVaultDefaultModel();
  renderApiModelOptions(model);
  if (apiKeyEncEl) apiKeyEncEl.value = cached ? cached.cipher || "" : "";
  if (apiKeyPassEl) apiKeyPassEl.value = cached ? cached.passphrase || "" : "";
  if (apiModelEl) apiModelEl.value = model;
  renderApiModelHint();
  renderApiSecureContextState();
}

function setInputValidity(el, ok) {
  if (!el) return;
  el.classList.toggle("invalid", !ok);
}

function validateApiInputs() {
  const disableReason = getApiVaultDisableReason();
  const cipherRaw = apiKeyEncEl ? apiKeyEncEl.value : "";
  const cipher = cipherRaw.trim().replace(/\s+/g, "");
  const passphrase = apiKeyPassEl ? apiKeyPassEl.value.trim() : "";
  const model = apiModelEl ? apiModelEl.value.trim() : "";
  const cipherOk = !cipher || isCipherFormat(cipher);
  const passOk = !passphrase || isSafePassphrase(passphrase);
  const modelOk = !model || isAllowedApiModel(model);
  setInputValidity(apiKeyEncEl, cipherOk);
  setInputValidity(apiKeyPassEl, passOk);
  setInputValidity(apiModelEl, modelOk);
  const errors = [];
  if (cipher && !cipherOk) errors.push("암호화된 키 형식이 올바르지 않습니다.");
  if (passphrase && !passOk) errors.push("암호화 키 형식이 올바르지 않습니다.");
  if (model && !modelOk) errors.push("허용된 모델만 선택할 수 있습니다.");
  const ready = Boolean(cipher && passphrase && model && cipherOk && passOk && modelOk);
  renderApiSecureContextState();
  if (apiSaveBtn) apiSaveBtn.disabled = Boolean(disableReason) || !ready;
  if (apiValidationEl) {
    if (disableReason) {
      apiValidationEl.textContent = disableReason;
    } else if (!cipher && !passphrase && localLlmEnabled) {
      apiValidationEl.textContent = "로컬 LLM 사용 중 — API 키 없이 전송 가능";
    } else if (!cipher && !passphrase) {
      apiValidationEl.textContent = "";
    } else if (errors.length) {
      apiValidationEl.textContent = errors[0];
    } else if (!ready) {
      apiValidationEl.textContent = "암호화된 키, 암호화 키, 모델을 입력해주세요.";
    } else {
      apiValidationEl.textContent = "입력값이 유효합니다.";
    }
  }
}

async function saveApiKeyFromInputs() {
  const disableReason = getApiVaultDisableReason();
  if (disableReason) {
    throw new Error(disableReason);
  }
  const cipherRaw = apiKeyEncEl ? apiKeyEncEl.value : "";
  const cipher = cipherRaw.trim().replace(/\s+/g, "");
  const passphrase = apiKeyPassEl ? apiKeyPassEl.value.trim() : "";
  const model = apiModelEl ? apiModelEl.value.trim() : "";
  if (!cipher || !passphrase || !model) {
    throw new Error("암호화된 키, 암호화 키, 모델을 모두 입력해주세요.");
  }
  if (apiKeyEncEl) apiKeyEncEl.value = cipher;
  if (!isCipherFormat(cipher)) {
    throw new Error("암호화된 키 형식이 올바르지 않습니다.");
  }
  if (!isSafePassphrase(passphrase)) {
    throw new Error("암호화 키 형식이 올바르지 않습니다.");
  }
  if (!isAllowedApiModel(model)) {
    throw new Error("허용된 모델만 선택할 수 있습니다.");
  }
  let mask = "";
  try {
    const plain = await decryptApiKey(cipher, passphrase);
    mask = maskApiKey(plain);
  } catch (err) {
    throw new Error("암호화 키 검증에 실패했습니다.");
  }
  saveApiKeyCache({
    cipher,
    passphrase,
    model,
    mask,
    updated_at: Date.now(),
  });
  recordApiKeyHistory({
    mask,
    model,
    updated_at: Date.now(),
  });
  await updateApiStatusDisplay();
}

function clearApiKeyInputs() {
  if (apiKeyEncEl) apiKeyEncEl.value = "";
  if (apiKeyPassEl) apiKeyPassEl.value = "";
  if (apiKeyPlainEl) apiKeyPlainEl.value = "";
  renderApiModelOptions(getApiVaultDefaultModel());
  if (apiModelEl) apiModelEl.value = getApiVaultDefaultModel();
  renderApiModelHint();
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
    toastTimer = null;
  }, TOAST_DURATION_MS);
}

function resetConversationRenderState() {
  currentHistoryMessages = [];
  lastRenderedMessageId = null;
  lastRenderedSignature = null;
  resetHistoryState();
  setHistoryLoading(false);
  setHistoryMoreVisible(false);
  replaceMessages([], []);
  updateConversationStats({ total_messages: 0, total_user_messages: 0 });
}

function setActiveConversation(conversationId, options = {}) {
  const nextId = String(conversationId || "").trim();
  // 대화 전환 시 기존 progress 버블/polling 정리
  if (nextId !== _progressActiveConvId && _progressActiveConvId) {
    _stopProgressPoll();
    _progressActiveConvId = "";
    const oldBubble = chatLogEl.querySelector(".msg-progress-live");
    if (oldBubble) oldBubble.remove();
  }
  activeConversationId = nextId;
  if (convIdEl) {
    convIdEl.textContent = `CONV: ${nextId || "-"}`;
  }
  if (options.resetView) {
    resetConversationRenderState();
  }
  if (nextId) {
    getConversationState(nextId);
  }
  renderHeaderStatus();
}

function pruneConversationClientState(items = []) {
  const visibleIds = new Set(
    (Array.isArray(items) ? items : [])
      .map((item) => String(item && item.id ? item.id : "").trim())
      .filter(Boolean)
  );
  Array.from(conversationPollers.keys()).forEach((conversationId) => {
    if (!visibleIds.has(conversationId)) {
      stopConversationPoll(conversationId);
    }
  });
  Array.from(conversationState.keys()).forEach((conversationId) => {
    if (!visibleIds.has(conversationId)) {
      conversationState.delete(conversationId);
    }
  });
  Array.from(cancelOverrideUntil.keys()).forEach((conversationId) => {
    if (!visibleIds.has(conversationId)) {
      cancelOverrideUntil.delete(conversationId);
    }
  });
}

function resolveDangerModal(result) {
  const resolver = dangerModalResolver;
  dangerModalResolver = null;
  if (resolver) {
    resolver(result);
  }
}

function getFocusableElement(candidate) {
  if (!(candidate instanceof HTMLElement)) return null;
  if (!document.body.contains(candidate)) return null;
  if (candidate.hasAttribute("disabled")) return null;
  if (candidate.closest(".hidden")) return null;
  return candidate;
}

function setAppModalState(open) {
  document.body.classList.toggle("modal-open", Boolean(open));
  if (!toolsDrawerEl) return;
  if (open) {
    toolsDrawerEl.setAttribute("inert", "");
    return;
  }
  if (toolsDrawerEl.classList.contains("show")) {
    toolsDrawerEl.removeAttribute("inert");
  } else {
    toolsDrawerEl.setAttribute("inert", "");
  }
}

function setToolsDrawerOpen(open, options = {}) {
  if (!toolsDrawerEl) return;
  const nextOpen = Boolean(open);
  toolsDrawerEl.classList.toggle("show", nextOpen);
  toolsDrawerEl.classList.toggle("hidden", !nextOpen);
  toolsDrawerEl.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  if (toolsToggleEl) {
    toolsToggleEl.setAttribute("aria-expanded", nextOpen ? "true" : "false");
  }
  if (nextOpen) {
    if (!document.body.classList.contains("modal-open")) {
      toolsDrawerEl.removeAttribute("inert");
    }
    return;
  }
  toolsDrawerEl.setAttribute("inert", "");
  if (options.restoreFocus === false) return;
  const activeEl = document.activeElement;
  if (activeEl instanceof HTMLElement && toolsDrawerEl.contains(activeEl)) {
    const focusTarget = getFocusableElement(toolsToggleEl) || getFocusableElement(promptBox);
    if (focusTarget) {
      requestAnimationFrame(() => focusTarget.focus());
    }
  }
}

function waitForNextPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(resolve);
    });
  });
}

function hideDangerConfirmModal(result = { confirmed: false, value: "" }, options = {}) {
  if (!dangerModalEl) return;
  dangerModalEl.classList.remove("show");
  dangerModalEl.setAttribute("aria-hidden", "true");
  if (dangerModalInputEl) {
    dangerModalInputEl.value = "";
    dangerModalInputEl.placeholder = "";
  }
  if (dangerModalConfirmEl) {
    dangerModalConfirmEl.disabled = true;
  }
  if (dangerModalEl.dataset) {
    dangerModalEl.dataset.expectedText = "";
  }
  setAppModalState(false);
  const focusTarget =
    options.restoreFocus === false
      ? null
      : getFocusableElement(dangerModalReturnFocusEl) ||
        getFocusableElement(toolsToggleEl) ||
        getFocusableElement(promptBox);
  dangerModalReturnFocusEl = null;
  if (focusTarget) {
    requestAnimationFrame(() => {
      focusTarget.focus();
    });
  }
  resolveDangerModal(result);
}

function syncDangerConfirmButton() {
  if (!dangerModalEl || !dangerModalConfirmEl || !dangerModalInputEl) return;
  const expectedText = String(dangerModalEl.dataset.expectedText || "");
  dangerModalConfirmEl.disabled = dangerModalInputEl.value.trim() !== expectedText;
}

async function requestDangerConfirmation(options = {}) {
  const title = String(options.title || "삭제 확인");
  const message = String(options.message || "");
  const label = String(options.label || "확인 입력");
  const expectedText = String(options.expectedText || "").trim();
  const confirmLabel = String(options.confirmLabel || "삭제");
  const closeToolsDrawerBeforeOpen = Boolean(options.closeToolsDrawerBeforeOpen);
  const explicitReturnFocusEl = getFocusableElement(options.returnFocusEl);
  if (!dangerModalEl || !dangerModalInputEl || !dangerModalConfirmEl) {
    return Promise.resolve({ confirmed: false, value: "" });
  }
  if (dangerModalResolver) {
    hideDangerConfirmModal({ confirmed: false, value: "" }, { restoreFocus: false });
  }
  dangerModalReturnFocusEl =
    explicitReturnFocusEl ||
    getFocusableElement(document.activeElement) ||
    getFocusableElement(toolsToggleEl) ||
    getFocusableElement(promptBox);
  if (closeToolsDrawerBeforeOpen && toolsDrawerEl && toolsDrawerEl.classList.contains("show")) {
    setToolsDrawerOpen(false, { restoreFocus: false });
    await waitForNextPaint();
  }
  if (dangerModalTitleEl) dangerModalTitleEl.textContent = title;
  if (dangerModalTextEl) dangerModalTextEl.textContent = message;
  if (dangerModalLabelEl) dangerModalLabelEl.textContent = label;
  dangerModalInputEl.value = "";
  dangerModalInputEl.placeholder = expectedText;
  dangerModalEl.dataset.expectedText = expectedText;
  dangerModalConfirmEl.textContent = confirmLabel;
  dangerModalConfirmEl.disabled = true;
  setAppModalState(true);
  dangerModalEl.classList.add("show");
  dangerModalEl.setAttribute("aria-hidden", "false");
  return new Promise((resolve) => {
    dangerModalResolver = resolve;
    requestAnimationFrame(() => {
      dangerModalInputEl.focus();
      dangerModalInputEl.select();
    });
  });
}

async function syncConversationAfterMutation(currentConversationId) {
  const nextCurrentId = String(currentConversationId || "").trim();
  if (nextCurrentId !== activeConversationId) {
    setActiveConversation(nextCurrentId, { resetView: true });
  }
  const data = await refreshConversations({ syncHistoryOnCurrentChange: false });
  const resolvedCurrentId = String((data && data.current) || nextCurrentId || "").trim();
  if (!resolvedCurrentId) {
    setActiveConversation("", { resetView: true });
    return;
  }
  if (resolvedCurrentId !== activeConversationId) {
    setActiveConversation(resolvedCurrentId, { resetView: true });
  }
  await loadRecentHistory(resolvedCurrentId);
}

async function deleteConversationWithConfirmation(item) {
  if (!item || !item.id) return;
  const conversationId = String(item.id).trim();
  if (!conversationId) return;
  const state = getConversationState(conversationId);
  const processing = state.status === "processing";
  if (!processing) {
    if (!confirm("이 대화를 삭제할까요?")) return;
  } else {
    const decision = await requestDangerConfirmation({
      title: "처리 중 대화 강제 삭제",
      message:
        "이 대화는 현재 처리 중입니다.\n`삭제`를 입력하면 실행을 중단시키고 이 대화를 강제로 삭제합니다.",
      label: "정말 삭제하려면 아래에 `삭제`를 입력하세요.",
      expectedText: "삭제",
      confirmLabel: "강제 삭제",
    });
    if (!decision.confirmed) return;
  }
  try {
    const payload = processing
      ? { conversation_id: conversationId, force: true, confirm_text: "삭제" }
      : { conversation_id: conversationId };
    const data = await apiFetch("/api/delete_conversation", payload);
    await syncConversationAfterMutation(data.current || "");
    showToast(data.deleted_pending ? "처리 중 대화 삭제를 요청했습니다." : "대화를 삭제했습니다.");
  } catch (err) {
    showToast(`대화 삭제 실패: ${err.message}`);
  }
}

async function clearAllConversationsWithConfirmation() {
  const decision = await requestDangerConfirmation({
    title: "모든 대화 삭제",
    message:
      "비처리중 대화가 모두 삭제됩니다.\n처리 중 대화는 보호되어 유지됩니다.\n계속하려면 `YES`를 입력하세요.",
    label: "전체 삭제를 진행하려면 아래에 `YES`를 입력하세요.",
    expectedText: "YES",
    confirmLabel: "모든 대화 삭제",
    closeToolsDrawerBeforeOpen: true,
    returnFocusEl: toolsToggleEl,
  });
  if (!decision.confirmed) return;
  try {
    const data = await apiFetch("/api/clear_memory", { confirm_text: "YES" });
    conversationState.clear();
    Array.from(conversationPollers.keys()).forEach((conversationId) => stopConversationPoll(conversationId));
    cancelOverrideUntil.clear();
    await syncConversationAfterMutation(data.current || "");
    const preserved = Number(data.preserved_processing_count || 0);
    showToast(
      preserved > 0
        ? `모든 대화 삭제 완료 · 처리 중 대화 ${preserved}건 유지`
        : "모든 대화 삭제 완료"
    );
  } catch (err) {
    showToast(`모든 대화 삭제 실패: ${err.message}`);
  }
}

async function refreshSession() {
  try {
    const data = await apiFetch("/api/session");
    const sessionLabel = data.client_ip ? `SESSION: ${data.client_ip}` : `SESSION: ${data.session_id || "-"}`;
    sessionIdEl.textContent = sessionLabel;
    convIdEl.textContent = `CONV: ${data.conversation_id || "-"}`;
    if (data.conversation_id) {
      activeConversationId = data.conversation_id;
      getConversationState(activeConversationId);
    }
    localLlmEnabled = Boolean(data.local_llm_enabled);
    if (data.default_model) localLlmDefaultModel = data.default_model;
    renderHeaderStatus();
    return data;
  } catch (err) {
    sessionIdEl.textContent = "SESSION: -";
    convIdEl.textContent = "CONV: -";
    renderHeaderStatus();
    return null;
  }
}

function resetHistoryState() {
  historyLoading = false;
  historyExhausted = false;
  historyOldestId = null;
}

async function loadRecentHistory(conversationId) {
  if (!conversationId) return;
  if (followupContextConversationId && followupContextConversationId !== conversationId) {
    followupApplyArmed = false;
  }
  resetHistoryState();
  historyLoading = true;
  setHistoryLoading(true);
  try {
    const data = await apiFetch(`/api/history?conversation_id=${encodeURIComponent(conversationId)}&limit=${HISTORY_PAGE_SIZE}`);
    const messages = data.messages || [];
    currentHistoryMessages = messages;
    const grouped = groupConversationMessages(messages);
    replaceMessages(messages, grouped);
    syncActiveConversationMetaFromGrouped(grouped);
    updateConversationStats(data);
    historyOldestId = data.next_before_id || null;
    historyExhausted = !data.has_more;
    setHistoryMoreVisible(!historyExhausted);
    scrollToBottom();
    updateHistoryMoreButtonVisibility();
    await ensureHistoryFilled();
    normalizePromptDraftFromFollowup();
    requestAnimationFrame(_syncJumpTimeFromScroll);
    // 서버에서 processing 상태이면 클라이언트 상태를 갱신하여 progress bubble 복원
    if (data.last_status === "processing") {
      setConversationState(conversationId, {
        status: "processing",
        run_id: data.last_run_id || "",
      });
      _restoreProgressBubbleIfNeeded();
    }
  } catch (err) {
    appendMessage("assistant", `대화 기록 로드 실패: ${err.message}`);
  } finally {
    historyLoading = false;
    setHistoryLoading(false);
  }
}

async function refreshActiveConversation(force = false) {
  if (!activeConversationId || historyLoading) return;
  try {
    const data = await apiFetch(
      `/api/history?conversation_id=${encodeURIComponent(activeConversationId)}&limit=${HISTORY_PAGE_SIZE}`
    );
    const messages = data.messages || [];
    currentHistoryMessages = messages;
    const grouped = groupConversationMessages(messages);
    const signature = buildRenderSignature(grouped);
    // 서버에서 processing 상태이면 클라이언트 상태 갱신
    if (data.last_status === "processing") {
      setConversationState(activeConversationId, {
        status: "processing",
        run_id: data.last_run_id || "",
      });
    }
    if (!force && signature && signature === lastRenderedSignature) {
      // signature가 같아도 processing 상태 복원은 항상 시도
      _restoreProgressBubbleIfNeeded();
      return;
    }
    const stayBottom = force || isNearBottom();
    const prevHeight = chatLogEl.scrollHeight;
    const prevTop = chatLogEl.scrollTop;
    replaceMessages(messages, grouped);
    syncActiveConversationMetaFromGrouped(grouped);
    updateConversationStats(data);
    if (stayBottom) {
      scrollToBottom();
    } else {
      const newHeight = chatLogEl.scrollHeight;
      chatLogEl.scrollTop = prevTop + (newHeight - prevHeight);
    }
    updateHistoryMoreButtonVisibility();
    normalizePromptDraftFromFollowup();
    lastRenderedSignature = signature || lastRenderedSignature;
    // processing 중인 대화라면 progress 버블 복원
    _restoreProgressBubbleIfNeeded();
  } catch (err) {
    // ignore polling errors
  }
}

async function loadOlderHistory() {
  if (historyLoading || historyExhausted || !activeConversationId || !historyOldestId) return;
  historyLoading = true;
  setHistoryLoading(true);
  try {
    const data = await apiFetch(
      `/api/history?conversation_id=${encodeURIComponent(activeConversationId)}&before_id=${historyOldestId}&limit=${HISTORY_PAGE_SIZE}`
    );
    const messages = data.messages || [];
    if (!messages.length) {
      historyExhausted = true;
      setHistoryMoreVisible(false);
      return;
    }
    currentHistoryMessages = [...messages, ...currentHistoryMessages];
    historyOldestId = data.next_before_id || historyOldestId;
    historyExhausted = !data.has_more;
    setHistoryMoreVisible(!historyExhausted);
    prependMessages(messages);
    updateHistoryMoreButtonVisibility();
    updateConversationStats(data);
    const grouped = groupConversationMessages(currentHistoryMessages);
    renderTimelineMarkers(grouped);
    syncActiveConversationMetaFromGrouped(grouped);
  } catch (err) {
    historyLoading = false;
  } finally {
    historyLoading = false;
    setHistoryLoading(false);
  }
}

async function ensureHistoryFilled() {
  if (historyExhausted) return;
  let attempts = 0;
  while (!historyExhausted && chatLogEl.scrollHeight <= chatLogEl.clientHeight && attempts < 5) {
    await loadOlderHistory();
    attempts += 1;
  }
}

async function jumpToTime() {
  if (!activeConversationId) {
    showToast("대화를 선택해주세요.");
    return;
  }
  const raw = jumpTimeEl ? jumpTimeEl.value.trim() : "";
  if (!raw) {
    showToast("이동할 시각을 선택해주세요.");
    return;
  }
  const normalized = raw.replace("T", " ");
  const at = normalized.length === 16 ? `${normalized}:00` : normalized;
  try {
    const data = await apiFetch(
      `/api/history_anchor?conversation_id=${encodeURIComponent(activeConversationId)}&at=${encodeURIComponent(at)}`
    );
    const targetId = data.message_id;
    if (!targetId) {
      showToast("해당 시각의 대화가 없습니다.");
      return;
    }
    /* 이미 DOM에 있으면 스크롤만 */
    const existing = document.getElementById(`msg-${targetId}`);
    if (existing) {
      existing.scrollIntoView({ block: "center" });
      _highlightJumpTarget(existing);
      return;
    }
    /* DOM에 없으면 전체 메시지 로드 후 스크롤 */
    resetHistoryState();
    historyLoading = true;
    setHistoryLoading(true);
    const history = await apiFetch(
      `/api/history?conversation_id=${encodeURIComponent(activeConversationId)}&limit=9999`
    );
    const messages = history.messages || [];
    currentHistoryMessages = messages;
    const grouped = groupConversationMessages(messages);
    replaceMessages(messages, grouped);
    syncActiveConversationMetaFromGrouped(grouped);
    updateConversationStats(history);
    historyOldestId = history.next_before_id || null;
    historyExhausted = !history.has_more;
    setHistoryMoreVisible(!historyExhausted);
    updateHistoryMoreButtonVisibility();
    requestAnimationFrame(() => {
      const target = document.getElementById(`msg-${targetId}`);
      if (target) {
        target.scrollIntoView({ block: "center" });
        _highlightJumpTarget(target);
      }
    });
  } catch (err) {
    showToast("시각 이동 실패");
  } finally {
    historyLoading = false;
    setHistoryLoading(false);
  }
}

/** 시각 이동 대상 메시지를 잠깐 강조 */
function _highlightJumpTarget(el) {
  el.classList.add("jump-highlight");
  setTimeout(() => el.classList.remove("jump-highlight"), 1800);
}

async function jumpToLatest() {
  if (!activeConversationId) return;
  await loadRecentHistory(activeConversationId);
}

/** 스크롤 위치에 따라 jumpTimeEl을 현재 보이는 메시지 시각으로 갱신 */
function _syncJumpTimeFromScroll() {
  if (!jumpTimeEl || !chatLogEl) return;
  const rect = chatLogEl.getBoundingClientRect();
  const midY = rect.top + rect.height * 0.3;
  const msgs = chatLogEl.querySelectorAll(".msg[data-created-at]");
  let closest = null;
  let closestDist = Infinity;
  for (const m of msgs) {
    const r = m.getBoundingClientRect();
    const dist = Math.abs(r.top - midY);
    if (dist < closestDist) { closestDist = dist; closest = m; }
  }
  if (closest && closest.dataset.createdAt) {
    const dt = closest.dataset.createdAt.replace(" ", "T").substring(0, 16);
    jumpTimeEl.value = dt;
  }
}

let _jumpTimeSyncTimer = 0;
function _updateScrollLatestVisibility() {
  if (!scrollLatestBtn || !chatLogEl) return;
  const gap = chatLogEl.scrollHeight - chatLogEl.scrollTop - chatLogEl.clientHeight;
  scrollLatestBtn.classList.toggle("hidden", gap < 200);
}
if (chatLogEl) {
  chatLogEl.addEventListener("scroll", () => {
    clearTimeout(_jumpTimeSyncTimer);
    _jumpTimeSyncTimer = setTimeout(() => {
      _syncJumpTimeFromScroll();
      _updateScrollLatestVisibility();
    }, 300);
  }, { passive: true });
}
if (scrollLatestBtn) {
  scrollLatestBtn.addEventListener("click", () => {
    if (chatLogEl) chatLogEl.scrollTo({ top: chatLogEl.scrollHeight, behavior: "smooth" });
  });
}

function renderConversations(items = [], currentId = "") {
  if (!conversationListEl) return;
  conversationTotalCount = Array.isArray(items) ? items.length : 0;
  let activeTopic = "";
  if (conversationCountEl) {
    conversationCountEl.textContent = String(conversationTotalCount || 0);
  }
  updateConversationStats({ total_messages: currentHistoryMessages.length, total_user_messages: null });
  items.forEach((item) => {
    if (item && item.id && item.status) {
      const duration = item.duration_ms !== undefined && item.duration_ms !== null
        ? Number(item.duration_ms)
        : null;
      const patch = { status: item.status, duration_ms: duration };
      if (item.status_at) {
        patch.status_at = item.status_at;
        if (item.status === "processing") {
          patch.started_at = item.status_at;
        }
      }
      setConversationState(item.id, patch);
    }
  });
  conversationListEl.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "대화가 없습니다.";
    conversationListEl.appendChild(empty);
    const loadBtn = document.createElement("button");
    loadBtn.type = "button";
    loadBtn.className = "btn ghost tiny";
    loadBtn.textContent = "이전 대화 불러오기";
    loadBtn.addEventListener("click", refreshConversations);
    conversationListEl.appendChild(loadBtn);
    return;
  }
  items.forEach((item) => {
    const state = getConversationState(item.id);
    const isActive = item.id === currentId || item.is_current;
    if (isActive) {
      activeTopic = sanitizeTopic(item.topic);
    }
    const card = document.createElement("div");
    card.className = `conv-item ${isActive ? "active" : ""}`;
    card.setAttribute("role", "button");
    card.tabIndex = 0;
    card.dataset.conversationId = item.id || "";
    const topic = document.createElement("div");
    topic.className = "conv-topic";
    topic.textContent = sanitizeTopic(item.topic);
    const meta = document.createElement("div");
    meta.className = "conv-meta";
    meta.textContent = formatRelativeTime(item.last_activity_at || item.created_at || "");
    meta.title = formatAbsoluteTime(item.last_activity_at || item.created_at || "");
    const countEl = document.createElement("div");
    countEl.className = "conv-count";
    if (item.message_count !== undefined && item.message_count !== null) {
      countEl.textContent = `메시지 ${item.message_count}`;
      countEl.title = `전체 메시지: ${item.message_count}\n사용자 메시지: ${item.user_message_count ?? 0}`;
    } else {
      countEl.textContent = "";
    }
    const liveEl = document.createElement("div");
    liveEl.className = "conv-live";
    if (state.status === "processing") {
      const startTs = state.started_at ? new Date(state.started_at).getTime() : Date.now();
      const elapsed = Math.max(0, Math.floor((Date.now() - startTs) / 1000));
      const stepText = Number(state.step_count || 0) > 0 ? ` · 단계 ${state.step_count}` : "";
      liveEl.textContent = `진행 ${formatElapsedShort(elapsed)}${stepText}`;
    } else if (state.status === "error" && state.recovery_active) {
      liveEl.textContent = "자동 복구 시도 중";
    } else if (state.status === "done" && state.duration_ms) {
      liveEl.textContent = `최근 ${formatDurationMsLabel(state.duration_ms)}`;
    } else {
      liveEl.textContent = "";
    }
    const statusLabel = document.createElement("span");
    const statusVisual = state.status === "error" && state.recovery_active ? "recovery" : (state.status || "idle");
    statusLabel.className = `conv-status conv-status--${statusVisual}`;
    statusLabel.textContent =
      state.status === "processing"
        ? "처리중"
        : state.status === "error" && state.recovery_active
          ? "복구중"
        : state.status === "canceled"
          ? "취소됨"
          : state.status === "error"
            ? "오류"
          : state.status === "done"
            ? "완료"
            : "대기";
    const foot = document.createElement("div");
    foot.className = "conv-foot";
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "conv-delete";
    deleteBtn.textContent = "삭제";
    deleteBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteConversationWithConfirmation(item);
    });
    foot.appendChild(statusLabel);
    foot.appendChild(deleteBtn);
    card.appendChild(topic);
    card.appendChild(meta);
    card.appendChild(countEl);
    if (liveEl.textContent) {
      card.appendChild(liveEl);
    }
    card.appendChild(foot);

    const activateConversation = async () => {
      try {
        await apiFetch("/api/use_conversation", { conversation_id: item.id });
        setActiveConversation(item.id);
        lastRenderedMessageId = null;
        await loadRecentHistory(item.id);
        await refreshConversations();
        _restoreProgressBubbleIfNeeded();
      } catch (err) {
        appendMessage("assistant", `대화 전환 실패: ${err.message}`);
      }
    };
    card.addEventListener("click", (event) => {
      const target = event.target;
      if (target && typeof target.closest === "function" && target.closest(".conv-delete")) {
        return;
      }
      activateConversation();
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateConversation();
      }
    });
    conversationListEl.appendChild(card);
  });
  if (activeTopic && !currentHistoryMessages.length) {
    setFollowupContextFields(normalizeSingleLine(activeTopic, 120), "", followupContextConversationId !== activeConversationId);
    followupContextConversationId = activeConversationId || followupContextConversationId;
  }
}

async function refreshConversations(options = {}) {
  const syncHistoryOnCurrentChange = options.syncHistoryOnCurrentChange !== false;
  try {
    const data = await apiFetch("/api/conversations");
    const items = Array.isArray(data.items) ? data.items : [];
    const currentId = String(data.current || "").trim();
    const currentChanged = currentId !== activeConversationId;
    pruneConversationClientState(items);
    if (currentChanged) {
      setActiveConversation(currentId, { resetView: true });
    }
    renderConversations(items, currentId);
    renderHeaderStatus();
    if (currentChanged && syncHistoryOnCurrentChange) {
      if (currentId) {
        await loadRecentHistory(currentId);
        _restoreProgressBubbleIfNeeded();
      } else {
        resetConversationRenderState();
      }
    }
    return data;
  } catch (err) {
    pruneConversationClientState([]);
    renderConversations([], "");
    renderHeaderStatus();
    return { items: [], current: "" };
  }
}

// ── 실시간 progress polling ──
let _progressPoller = null;
let _progressTimerHandle = null;
let _progressLastStep = 0;
let _progressStartTime = 0;
let _progressActiveConvId = "";  // 현재 progress 버블이 연결된 대화 ID

/**
 * processing 중인 대화의 progress 버블을 복원한다.
 * 대화 전환, 페이지 새로고침 시 호출.
 */
function _restoreProgressBubbleIfNeeded() {
  const cid = activeConversationId;
  if (!cid) return;
  const state = getConversationState(cid);
  const isProcessing = state.status === "processing" || (state.status === "error" && state.recovery_active);
  // 이미 progress 버블이 있으면 무시
  if (chatLogEl.querySelector(".msg-progress-live")) {
    if (!isProcessing) {
      // 더 이상 processing이 아니면 버블 제거
      _stopProgressPoll();
      const old = chatLogEl.querySelector(".msg-progress-live");
      if (old) old.remove();
    }
    return;
  }
  if (!isProcessing) return;
  // processing 중인데 버블이 없으면 복원
  const progressUI = _createProgressBubble();
  // 기존 시작 시간 복원
  if (state.started_at) {
    _progressStartTime = new Date(state.started_at).getTime();
    if (progressUI.timerEl) {
      const sec = Math.floor((Date.now() - _progressStartTime) / 1000);
      progressUI.timerEl.textContent = `${sec}s`;
    }
  }
  _progressActiveConvId = cid;
  _startProgressPoll(cid, progressUI.stepsContainer, progressUI.spinner, progressUI.timerEl, progressUI.intentEl, _progressStartTime || undefined);
  scrollToBottom();
}

function _createProgressBubble() {
  const dateKey = extractDateKey();
  const shouldStick = isNearBottom();
  ensureDateSeparatorForAppend(dateKey);
  const wrapper = document.createElement("div");
  wrapper.className = "msg assistant msg-progress-live";
  wrapper.dataset.dateKey = dateKey;
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  // 상단 상태바: 스피너 + 의도 + 경과 시간 + 취소 버튼
  const statusBar = document.createElement("div");
  statusBar.className = "progress-status-bar";
  const spinner = document.createElement("div");
  spinner.className = "progress-spinner";
  spinner.textContent = "처리 중...";
  statusBar.appendChild(spinner);
  const intentEl = document.createElement("span");
  intentEl.className = "progress-intent";
  intentEl.textContent = "";
  statusBar.appendChild(intentEl);
  const timerEl = document.createElement("span");
  timerEl.className = "progress-timer";
  timerEl.textContent = "0s";
  statusBar.appendChild(timerEl);
  const finalizeBtn = document.createElement("button");
  finalizeBtn.className = "progress-finalize-btn";
  finalizeBtn.textContent = "즉시 답변";
  finalizeBtn.title = "지금까지 수집한 정보로 즉시 답변 생성";
  finalizeBtn.addEventListener("click", () => { finalizeRequest(); });
  statusBar.appendChild(finalizeBtn);
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "progress-cancel-btn";
  cancelBtn.textContent = "취소";
  cancelBtn.title = "현재 요청 취소";
  cancelBtn.addEventListener("click", () => { cancelRequest(); });
  statusBar.appendChild(cancelBtn);
  bubble.appendChild(statusBar);

  // step 리스트 영역
  const stepsContainer = document.createElement("div");
  stepsContainer.className = "progress-steps-live";
  bubble.appendChild(stepsContainer);
  wrapper.appendChild(bubble);
  chatLogEl.appendChild(wrapper);
  if (shouldStick) scrollToBottom();
  return { wrapper, stepsContainer, spinner, timerEl, intentEl };
}

function _renderProgressStep(container, step) {
  const item = document.createElement("div");
  item.className = "step-item step-item--live";

  // 헤더: step 번호 + 작업 설명
  const head = document.createElement("div");
  head.className = "step-head";
  const title = getStepWorkText(step) || "단계";
  const stepIndex = step.step_index || 0;
  head.textContent = `#${stepIndex} · ${title}`;
  item.appendChild(head);

  // 메타: 도구명
  const meta = document.createElement("div");
  meta.className = "step-meta";
  meta.textContent = `도구: ${step.tool || "-"}`;
  item.appendChild(meta);

  // 근거/이유
  const reasonText = getStepReasonText(step);
  if (reasonText) {
    const reasonEl = document.createElement("div");
    reasonEl.className = "step-reason";
    reasonEl.textContent = `근거: ${reasonText}`;
    item.appendChild(reasonEl);
  }

  // 결과 요약
  const summaryText = formatResultSummary(step.result_summary || "");
  if (summaryText) {
    const summaryEl = document.createElement("div");
    summaryEl.className = "step-summary";
    summaryEl.textContent = summaryText;
    item.appendChild(summaryEl);
  }

  // SQL 전문 (접이식)
  if (step.sql) {
    const sqlText = String(step.sql || "");
    const sqlDetails = document.createElement("details");
    sqlDetails.className = "step-sql-details";
    const sqlSummary = document.createElement("summary");
    sqlSummary.className = "step-sql-summary";
    sqlSummary.textContent = sqlText.length > 60 ? `SQL: ${sqlText.slice(0, 60)}…` : `SQL: ${sqlText}`;
    sqlDetails.appendChild(sqlSummary);

    const sqlBody = document.createElement("div");
    sqlBody.className = "step-sql-body";
    const sqlPre = document.createElement("pre");
    sqlPre.className = "step-sql-full";
    sqlPre.textContent = sqlText;
    sqlBody.appendChild(sqlPre);

    // 액션 버튼: 복사 + SQL 보기
    const sqlActions = document.createElement("div");
    sqlActions.className = "step-sql-actions";
    const copyBtn = document.createElement("button");
    copyBtn.className = "mini ghost";
    copyBtn.textContent = "SQL 복사";
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(sqlText)
        .then(() => { copyBtn.textContent = "복사 완료"; setTimeout(() => { copyBtn.textContent = "SQL 복사"; }, 1200); })
        .catch(() => showToast("복사 실패"));
    });
    sqlActions.appendChild(copyBtn);
    if (typeof openSqlResultModal === "function") {
      const viewBtn = document.createElement("button");
      viewBtn.className = "mini ghost";
      viewBtn.textContent = "SQL 보기";
      viewBtn.addEventListener("click", () =>
        openSqlResultModal({ sql: step.sql }).catch(() => showToast("SQL 보기 실패"))
      );
      sqlActions.appendChild(viewBtn);
    }
    sqlBody.appendChild(sqlActions);
    sqlDetails.appendChild(sqlBody);
    item.appendChild(sqlDetails);
  }

  // 오류
  if (step.error) {
    const errorEl = document.createElement("div");
    errorEl.className = "step-error";
    errorEl.textContent = step.error;
    item.appendChild(errorEl);
  }

  container.appendChild(item);
}

function _startProgressPoll(conversationId, stepsContainer, spinner, timerEl, intentEl, restoreStartTime) {
  _progressLastStep = 0;
  // restoreStartTime이 주어지면 서버측 시작 시각을 사용 (타이머 복원)
  _progressStartTime = restoreStartTime || Date.now();
  if (_progressPoller) clearInterval(_progressPoller);
  if (_progressTimerHandle) clearInterval(_progressTimerHandle);

  // 경과 시간 타이머 (1초마다)
  _progressTimerHandle = setInterval(() => {
    if (timerEl) {
      const sec = Math.floor((Date.now() - _progressStartTime) / 1000);
      timerEl.textContent = `${sec}s`;
    }
  }, 1000);

  // step polling (1.5초마다)
  let _pollConvId = conversationId;
  _progressPoller = setInterval(async () => {
    try {
      // 첫 대화에서 conversation_id가 아직 없으면 activeConversationId 사용
      const effectiveId = _pollConvId || activeConversationId || "";
      const url = `/api/progress?conversation_id=${encodeURIComponent(effectiveId)}&after_step=${_progressLastStep}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      // 서버에서 run_id를 받으면 정상 연결된 것
      if (!_pollConvId && effectiveId) _pollConvId = effectiveId;
      // 서버측 시작 시각으로 타이머 보정 (최초 1회)
      if (data.status_at && _progressStartTime && data.status === "processing") {
        const serverStart = new Date(data.status_at).getTime();
        if (serverStart > 0 && Math.abs(_progressStartTime - serverStart) > 3000) {
          _progressStartTime = serverStart;
          // conversationState에도 반영
          const cState = getConversationState(effectiveId);
          if (cState) cState.started_at = data.status_at;
        }
      }
      const newSteps = Array.isArray(data.steps) ? data.steps : [];
      if (newSteps.length > 0) {
        const wasNearBottom = isNearBottom();
        newSteps.forEach((step) => {
          _renderProgressStep(stepsContainer, step);
          const idx = step.step_index || 0;
          if (idx > _progressLastStep) _progressLastStep = idx;
        });
        if (spinner) {
          spinner.textContent = `처리 중... (${data.step_count || _progressLastStep}단계)`;
        }
        if (wasNearBottom) scrollToBottom();
      }
      // 완료 감지: processing이 아니면 progress 버블 제거 + 대화 새로고침
      if (data.status && data.status !== "processing") {
        _stopProgressPoll();
        _progressActiveConvId = "";
        const liveBubble = document.querySelector(".msg-progress-live");
        if (liveBubble) liveBubble.remove();
        if (effectiveId) {
          setConversationState(effectiveId, { status: data.status });
        }
        refreshActiveConversation(true);
        refreshConversations();
        renderHeaderStatus();
        return;
      }
      // 의도 정보 업데이트 (상태 또는 step 기반)
      if (intentEl) {
        const cState = getConversationState(effectiveId);
        const intentText = normalizeSingleLine(cState.current_intent || "", 88) || "";
        if (intentText) {
          intentEl.textContent = intentText;
        } else if (newSteps.length > 0) {
          // step에서 직접 의도 추출
          const lastStep = newSteps[newSteps.length - 1];
          const stepDesc = lastStep.work || lastStep.tool || "";
          if (stepDesc) intentEl.textContent = stepDesc;
        }
      }
    } catch (_e) {
      // polling 실패는 무시
    }
  }, 1500);
}

function _stopProgressPoll() {
  if (_progressPoller) {
    clearInterval(_progressPoller);
    _progressPoller = null;
  }
  if (_progressTimerHandle) {
    clearInterval(_progressTimerHandle);
    _progressTimerHandle = null;
  }
  _progressLastStep = 0;
  _progressStartTime = 0;
}

async function sendMessage(message) {
  if (!message) return;
  const previewPayload = buildSendPreviewPayload(message);
  const cleanMessage = previewPayload.original || String(message || "").trim();
  const outboundMessage = previewPayload.outbound || cleanMessage;
  const keyConfig = getApiKeyConfig();
  if (!keyConfig) {
    showToast("API 설정이 필요합니다.");
    appendMessage("assistant", "API 설정이 필요합니다. 좌측의 API 설정에서 키와 모델을 등록해주세요.");
    return;
  }
  const consumeFollowupApply = followupApplyArmed && !isRestoreModeActive();
  if (consumeFollowupApply) {
    followupApplyArmed = false;
    renderFollowupLiveStatus();
    renderSendPreview();
  }
  const requestConversationId = activeConversationId;
  appendMessage("user", cleanMessage);
  promptBox.value = "";
  renderSendPreview();
  if (requestConversationId) {
    clearCancelOverride(requestConversationId);
    setConversationState(requestConversationId, {
      status: "processing",
      started_at: new Date().toISOString(),
      step_count: 0,
      recovery_active: false,
      recovery_stage: 0,
    });
    startConversationPoll(requestConversationId);
  }
  renderHeaderStatus();
  refreshConversations();
  refreshActiveConversation(true);

  // ── 실시간 progress 버블 생성 ──
  const progressUI = _createProgressBubble();
  _progressActiveConvId = requestConversationId || "";
  // conversation_id가 없어도(첫 대화) polling 시작 — 서버가 세션 기반으로 자동 탐지
  _startProgressPoll(requestConversationId || "", progressUI.stepsContainer, progressUI.spinner, progressUI.timerEl, progressUI.intentEl);

  try {
    const data = await apiFetch("/api/ask", {
      message: outboundMessage,
      api_key_cipher: keyConfig.cipher,
      api_key_passphrase: keyConfig.passphrase,
      model: keyConfig.model,
      conversation_id: requestConversationId || "",
    });

    // ── progress 버블 제거 ──
    _stopProgressPoll();
    _progressActiveConvId = "";
    if (progressUI.wrapper && progressUI.wrapper.parentNode) {
      progressUI.wrapper.parentNode.removeChild(progressUI.wrapper);
    }

    const responseConversationId = data.conversation_id || requestConversationId;
    const responseError = String(data.error || "").trim();
    const canceledResponse =
      Boolean(responseConversationId) &&
      isCancelOverrideActive(responseConversationId) &&
      /취소/.test(responseError);
    if (!activeConversationId && responseConversationId) {
      setActiveConversation(responseConversationId);
    }
    if (responseConversationId) {
      setConversationState(responseConversationId, {
        status: canceledResponse ? "canceled" : responseError ? "error" : "done",
        duration_ms: data.duration_ms,
      });
      if (canceledResponse) {
        clearCancelOverride(responseConversationId);
      }
    }
    if (responseConversationId === activeConversationId) {
      if (canceledResponse) {
        showToast("요청이 취소되었습니다.");
      } else if (responseError) {
        appendMessage("assistant", `오류: ${responseError}`);
      } else {
        appendMessage("assistant", data.output || "(출력 없음)", {
          sql: data.executed_sql,
          csvPaths: data.result_csv_paths || (data.result_csv_path ? [data.result_csv_path] : []),
          steps: data.steps || [],
          rationale: data.rationale || "",
        });
      }
      if (data.conversation_id) {
        convIdEl.textContent = `CONV: ${data.conversation_id}`;
        activeConversationId = data.conversation_id;
      }
      renderHeaderStatus();
    } else {
      renderHeaderStatus();
    }
    refreshConversations();
    refreshActiveConversation(true);
  } catch (err) {
    _stopProgressPoll();
    _progressActiveConvId = "";
    if (progressUI.wrapper && progressUI.wrapper.parentNode) {
      progressUI.wrapper.parentNode.removeChild(progressUI.wrapper);
    }
    if (requestConversationId) {
      setConversationState(requestConversationId, { status: "error" });
    }
    if (!requestConversationId || requestConversationId === activeConversationId) {
      appendMessage("assistant", `오류: ${err.message}`);
    }
    renderHeaderStatus();
    refreshConversations();
  } finally {
    if (requestConversationId) {
      stopConversationPoll(requestConversationId);
    }
  }
}

async function cancelRequest() {
  if (!activeConversationId) {
    showToast("취소할 대화가 없습니다.");
    return;
  }
  const targetConversationId = activeConversationId;
  markCancelOverride(targetConversationId);
  setConversationState(targetConversationId, { status: "canceled" });
  renderHeaderStatus();
  renderRunHud();
  refreshConversations();
  if (targetConversationId === activeConversationId) {
    refreshActiveConversation(false);
  }
  showToast("요청 취소 요청 중...");
  try {
    const data = await apiFetch("/api/cancel", { conversation_id: targetConversationId });
    setConversationState(targetConversationId, { status: "canceled" });
    renderHeaderStatus();
    renderRunHud();
    showToast("요청 취소 요청 완료");
    if (data && data.output) {
      appendMessage("assistant", data.output);
    }
  } catch (err) {
    clearCancelOverride(targetConversationId);
    setConversationState(targetConversationId, { status: "processing" });
    renderHeaderStatus();
    renderRunHud();
    showToast("요청 취소 실패");
  }
}

async function finalizeRequest() {
  if (!activeConversationId) {
    showToast("즉시 답변할 대화가 없습니다.");
    return;
  }
  const state = getConversationState(activeConversationId);
  if (state.status !== "processing") {
    showToast("처리 중인 대화만 즉시 답변을 요청할 수 있습니다.");
    return;
  }
  showToast("즉시 답변 요청 중...");
  try {
    await apiFetch("/api/finalize", { conversation_id: activeConversationId });
    showToast("즉시 답변을 요청했습니다. 잠시 후 답변이 생성됩니다.");
  } catch (err) {
    showToast("즉시 답변 요청 실패");
  }
}

function bindActions() {
  if (domainBadgeEl) {
    domainBadgeEl.addEventListener("click", () => {
      if (pinnedDomainHint) {
        pinnedDomainHint = "";
        savePinnedContext();
        renderContextBadges();
        renderFollowupLiveStatus();
        renderSendPreview();
        showToast("도메인 고정을 해제했습니다.");
        return;
      }
      const candidate = sanitizeContextTag(currentDomainHint || "", 56);
      if (!candidate) {
        showToast("고정할 도메인 정보가 아직 없습니다.");
        return;
      }
      pinnedDomainHint = candidate;
      savePinnedContext();
      renderContextBadges();
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast(`도메인 고정: ${candidate}`);
    });
  }

  if (strategyBadgeEl) {
    strategyBadgeEl.addEventListener("click", () => {
      if (pinnedStrategyHint) {
        pinnedStrategyHint = "";
        savePinnedContext();
        renderContextBadges();
        renderFollowupLiveStatus();
        renderSendPreview();
        showToast("전략 고정을 해제했습니다.");
        return;
      }
      const candidate = sanitizeContextTag(currentStrategyHint || "", 72);
      if (!candidate) {
        showToast("고정할 전략 정보가 아직 없습니다.");
        return;
      }
      pinnedStrategyHint = candidate;
      savePinnedContext();
      renderContextBadges();
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast(`전략 고정: ${candidate}`);
    });
  }

  if (restoreContinueBtnEl) {
    restoreContinueBtnEl.addEventListener("click", () => {
      if (!isRestoreModeActive()) {
        showToast("복원 모드가 아닙니다.");
        return;
      }
      const prompt = buildRestoreContinuePrompt();
      if (!prompt) {
        showToast("복원 파일이 선택되지 않았습니다.");
        return;
      }
      sendMessage(prompt);
    });
  }

  if (restoreModeClearBtnEl) {
    restoreModeClearBtnEl.addEventListener("click", () => {
      clearRestoreModeState(activeConversationId, true);
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast("복원 모드를 해제했습니다.");
    });
  }

  if (domainDriftRevertBtnEl) {
    domainDriftRevertBtnEl.addEventListener("click", () => {
      const targetDomain = sanitizeContextTag(pinnedDomainHint || "", 42);
      if (!targetDomain || !activeConversationId) {
        showToast("원복할 고정 도메인이 없습니다.");
        return;
      }
      currentDomainHint = targetDomain;
      setConversationState(activeConversationId, { current_domain: targetDomain });
      domainDriftDismissedKey = "";
      renderContextBadges();
      renderDomainDriftPanel();
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast(`고정 도메인으로 원복: ${targetDomain}`);
    });
  }

  if (domainDriftCloseBtnEl) {
    domainDriftCloseBtnEl.addEventListener("click", () => {
      const key = domainDriftPanelEl && domainDriftPanelEl.dataset ? domainDriftPanelEl.dataset.driftKey : "";
      domainDriftDismissedKey = key || domainDriftDismissedKey;
      if (domainDriftPanelEl) domainDriftPanelEl.classList.add("hidden");
    });
  }

  if (sideToggleEl && sideEl) {
    sideToggleEl.addEventListener("click", () => {
      if (layoutEl) {
        layoutEl.classList.toggle("side-collapsed");
      } else {
        sideEl.classList.toggle("collapsed");
      }
      const collapsed = layoutEl ? layoutEl.classList.contains("side-collapsed") : sideEl.classList.contains("collapsed");
      const expanded = !collapsed;
      sideToggleEl.setAttribute("aria-expanded", expanded ? "true" : "false");
      if (expanded) {
        showToast("사이드 메뉴 확장");
      } else {
        showToast("사이드 메뉴 축소");
      }
    });
  }

  if (toolsToggleEl && toolsDrawerEl) {
    toolsToggleEl.addEventListener("click", () => {
      if (document.body.classList.contains("modal-open")) return;
      const open = !toolsDrawerEl.classList.contains("show");
      setToolsDrawerOpen(open);
    });
  }

  if (toolsCloseEl && toolsDrawerEl) {
    toolsCloseEl.addEventListener("click", () => {
      setToolsDrawerOpen(false);
    });
  }

  if (toolsDrawerEl) {
    toolsDrawerEl.addEventListener("click", (event) => {
      if (event.target === toolsDrawerEl) {
        setToolsDrawerOpen(false);
      }
    });
  }

  if (apiToggleEl && apiPanelEl) {
    apiToggleEl.textContent = apiPanelEl.classList.contains("hidden") ? "설정 열기" : "설정 닫기";
    apiToggleEl.addEventListener("click", () => {
      apiPanelEl.classList.toggle("hidden");
      apiToggleEl.textContent = apiPanelEl.classList.contains("hidden") ? "설정 열기" : "설정 닫기";
    });
  }

  document.getElementById("btnSend").addEventListener("click", () => {
    sendMessage(promptBox.value.trim());
  });

  promptBox.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(promptBox.value.trim());
    }
  });
  promptBox.addEventListener("input", () => {
    renderSendPreview();
  });

  [followupIntentEl, followupConstraintsEl].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", () => {
      followupManualEdit = true;
      followupContextConversationId = activeConversationId || followupContextConversationId;
      renderFollowupLiveStatus();
      renderSendPreview();
    });
  });
  if (followupApplyOnceEl) {
    followupApplyOnceEl.addEventListener("click", () => {
      if (isRestoreModeActive()) {
        showToast("복원 모드에서는 반영이 항상 켜져 있습니다.");
        renderFollowupLiveStatus();
        renderSendPreview();
        return;
      }
      const pending = getPendingInjectParts();
      if (!pending.length && !followupApplyArmed) {
        showToast("반영할 의도/제약 또는 고정값이 없습니다.");
        return;
      }
      followupApplyArmed = !followupApplyArmed;
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast(followupApplyArmed ? "다음 요청 반영을 켰습니다." : "다음 요청 반영을 껐습니다.");
    });
  }
  if (followupClearEl) {
    followupClearEl.addEventListener("click", () => {
      if (followupIntentEl) followupIntentEl.value = "";
      if (followupConstraintsEl) followupConstraintsEl.value = "";
      followupManualEdit = false;
      followupApplyArmed = false;
      followupContextConversationId = activeConversationId || "";
      renderFollowupLiveStatus();
      renderSendPreview();
      showToast("이어받기 컨텍스트를 초기화했습니다.");
    });
  }

  document.getElementById("btnNew").addEventListener("click", async () => {
    appendMessage("assistant", "새 대화를 생성합니다...");
    try {
      const data = await apiFetch("/api/new_conversation", {});
      appendMessage("assistant", data.output || "(출력 없음)");
      if (data.conversation_id) {
        setActiveConversation(data.conversation_id);
        followupApplyArmed = false;
        await loadRecentHistory(data.conversation_id);
        await refreshConversations();
        refreshActiveConversation(true);
      }
      refreshConversations();
    } catch (err) {
      appendMessage("assistant", `오류: ${err.message}`);
    }
  });

  document.getElementById("btnClear").addEventListener("click", async () => {
    await clearAllConversationsWithConfirmation();
  });
  const cancelBtn = document.getElementById("btnCancel");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      cancelRequest();
    });
  }
  const quickDbBtn = document.getElementById("btnQuickDb");
  if (quickDbBtn) {
    quickDbBtn.addEventListener("click", () => {
      sendMessage("현재 DB 목록 보여줘");
    });
  }
  if (jumpBtn) {
    jumpBtn.addEventListener("click", () => {
      jumpToTime();
    });
  }
  if (jumpLatestBtn) {
    jumpLatestBtn.addEventListener("click", () => {
      jumpToLatest();
    });
  }
  if (jumpTimeEl) {
    jumpTimeEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        jumpToTime();
      }
    });
  }

  /* ── 캘린더 시각 이동 ── */
  let _calDatesCache = {};
  let _calMonth = new Date();
  let _calSelectedDate = "";

  function _toggleCalPanel() {
    if (!jumpCalPanel) return;
    const show = jumpCalPanel.classList.contains("hidden");
    jumpCalPanel.classList.toggle("hidden", !show);
    if (show && activeConversationId) _loadCalDates();
  }

  async function _loadCalDates() {
    try {
      const data = await apiFetch(`/api/history_dates?conversation_id=${encodeURIComponent(activeConversationId)}`);
      _calDatesCache = data.dates || {};
      if (data.last) {
        const parts = data.last.split("-");
        _calMonth = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
      }
      _renderCalendar();
    } catch (e) { /* ignore */ }
  }

  function _renderCalendar() {
    if (!jumpCalGrid || !jumpCalTitle) return;
    const year = _calMonth.getFullYear();
    const month = _calMonth.getMonth();
    jumpCalTitle.textContent = `${year}년 ${month + 1}월`;

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const prevDays = new Date(year, month, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;

    jumpCalGrid.innerHTML = "";
    // prev month fill
    for (let i = firstDay - 1; i >= 0; i--) {
      const d = document.createElement("div");
      d.className = "jump-cal-day other-month";
      d.textContent = prevDays - i;
      jumpCalGrid.appendChild(d);
    }
    // current month
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
      const d = document.createElement("div");
      d.className = "jump-cal-day";
      d.textContent = day;
      if (dateStr === todayStr) d.classList.add("today");
      if (_calDatesCache[dateStr]) {
        d.classList.add("has-messages");
        d.addEventListener("click", () => _selectCalDate(dateStr, d));
      }
      if (dateStr === _calSelectedDate) d.classList.add("selected");
      jumpCalGrid.appendChild(d);
    }
    // next month fill
    const totalCells = jumpCalGrid.children.length;
    const remaining = (7 - (totalCells % 7)) % 7;
    for (let i = 1; i <= remaining; i++) {
      const d = document.createElement("div");
      d.className = "jump-cal-day other-month";
      d.textContent = i;
      jumpCalGrid.appendChild(d);
    }
  }

  function _selectCalDate(dateStr, el) {
    _calSelectedDate = dateStr;
    jumpCalGrid.querySelectorAll(".selected").forEach(s => s.classList.remove("selected"));
    if (el) el.classList.add("selected");
    const times = _calDatesCache[dateStr] || [];
    if (jumpCalTimes) jumpCalTimes.classList.toggle("hidden", !times.length);
    if (jumpCalTimesList) {
      jumpCalTimesList.innerHTML = "";
      const unique = [...new Set(times)].sort();
      unique.forEach(t => {
        const btn = document.createElement("button");
        btn.className = "jump-cal-time";
        btn.textContent = t;
        btn.addEventListener("click", () => {
          if (jumpTimeEl) jumpTimeEl.value = `${dateStr}T${t}`;
          jumpToTime();
          jumpCalPanel.classList.add("hidden");
        });
        jumpCalTimesList.appendChild(btn);
      });
    }
  }

  if (jumpCalBtn) jumpCalBtn.addEventListener("click", _toggleCalPanel);
  if (jumpCalPrev) jumpCalPrev.addEventListener("click", () => {
    _calMonth.setMonth(_calMonth.getMonth() - 1);
    _renderCalendar();
  });
  if (jumpCalNext) jumpCalNext.addEventListener("click", () => {
    _calMonth.setMonth(_calMonth.getMonth() + 1);
    _renderCalendar();
  });

  // 패널 외부 클릭 시 닫기
  document.addEventListener("click", (e) => {
    if (jumpCalPanel && !jumpCalPanel.classList.contains("hidden")) {
      if (!jumpCalPanel.contains(e.target) && !e.target.classList.contains("date-sep-label")) {
        jumpCalPanel.classList.add("hidden");
      }
    }
  });

  // 날짜 경계선 라벨 클릭 → 캘린더 열기
  document.addEventListener("openCalDate", (e) => {
    const dateKey = e.detail;
    if (!jumpCalPanel) return;
    const parts = dateKey.split("-");
    if (parts.length === 3) {
      _calMonth = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
    }
    jumpCalPanel.classList.remove("hidden");
    if (activeConversationId) {
      _loadCalDates().then(() => {
        _selectCalDate(dateKey, jumpCalGrid && jumpCalGrid.querySelector(".jump-cal-day.selected"));
      });
    } else {
      _renderCalendar();
    }
  });

  if (apiSaveBtn) {
    apiSaveBtn.addEventListener("click", async () => {
      try {
        await saveApiKeyFromInputs();
        showToast("API 설정 저장 완료");
        validateApiInputs();
      } catch (err) {
        showToast(err.message || "API 설정 저장 실패");
      }
    });
  }

  if (apiClearBtn) {
    apiClearBtn.addEventListener("click", async () => {
      clearApiKeyCache();
      clearApiKeyInputs();
      await updateApiStatusDisplay();
      validateApiInputs();
      showToast("API 설정 삭제 완료");
    });
  }

  if (apiEncryptBtn) {
    apiEncryptBtn.addEventListener("click", async () => {
      const disableReason = getApiVaultDisableReason();
      if (disableReason) {
        showToast(disableReason);
        return;
      }
      const plain = apiKeyPlainEl ? apiKeyPlainEl.value.trim() : "";
      const passphrase = apiKeyPassEl ? apiKeyPassEl.value.trim() : "";
      if (!plain || !passphrase) {
        showToast("평문 키와 암호화 키를 입력해주세요.");
        return;
      }
      try {
        const cipher = await encryptApiKey(plain, passphrase);
        if (apiKeyEncEl) apiKeyEncEl.value = cipher;
        const mask = maskApiKey(plain);
        const model = apiModelEl ? apiModelEl.value.trim() || getApiVaultDefaultModel() : getApiVaultDefaultModel();
        if (!isAllowedApiModel(model)) {
          showToast("허용된 모델만 선택할 수 있습니다.");
          return;
        }
        saveApiKeyCache({
          cipher,
          passphrase,
          model,
          mask,
          updated_at: Date.now(),
        });
        recordApiKeyHistory({
          mask,
          model,
          updated_at: Date.now(),
        });
        await updateApiStatusDisplay();
        validateApiInputs();
        showToast("암호화 완료");
      } catch (err) {
        showToast(err.message || "암호화 실패");
      }
    });
  }
  [apiKeyEncEl, apiKeyPassEl, apiModelEl].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", () => {
      if (el === apiModelEl) {
        renderApiModelHint();
      }
      validateApiInputs();
    });
  });
  if (apiModelEl) {
    apiModelEl.addEventListener("change", () => {
      renderApiModelHint();
      validateApiInputs();
    });
  }
  document.getElementById("modalClose").addEventListener("click", hideModal);
  document.getElementById("modalCopy").addEventListener("click", () => {
    const modalBody = document.getElementById("modalBody");
    const text = modalCopyText || modalBody.innerText || "";
    navigator.clipboard
      .writeText(text)
      .then(() => showToast("복사 완료"))
      .catch(() => showToast("복사 실패"));
  });
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") hideModal();
  });
  if (dangerModalInputEl) {
    dangerModalInputEl.addEventListener("input", () => {
      syncDangerConfirmButton();
    });
    dangerModalInputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && dangerModalConfirmEl && !dangerModalConfirmEl.disabled) {
        e.preventDefault();
        hideDangerConfirmModal({ confirmed: true, value: dangerModalInputEl.value.trim() });
      }
    });
  }
  if (dangerModalCancelEl) {
    dangerModalCancelEl.addEventListener("click", () => {
      hideDangerConfirmModal({ confirmed: false, value: "" });
    });
  }
  if (dangerModalCloseEl) {
    dangerModalCloseEl.addEventListener("click", () => {
      hideDangerConfirmModal({ confirmed: false, value: "" });
    });
  }
  if (dangerModalConfirmEl) {
    dangerModalConfirmEl.addEventListener("click", () => {
      if (dangerModalConfirmEl.disabled) return;
      hideDangerConfirmModal({ confirmed: true, value: dangerModalInputEl ? dangerModalInputEl.value.trim() : "" });
    });
  }
  if (dangerModalEl) {
    dangerModalEl.addEventListener("click", (e) => {
      if (e.target === dangerModalEl) {
        hideDangerConfirmModal({ confirmed: false, value: "" });
      }
    });
  }
  document.addEventListener("keydown", (e) => {
    if (dangerModalEl && dangerModalEl.classList.contains("show")) {
      if (e.key === "Escape") {
        e.preventDefault();
        hideDangerConfirmModal({ confirmed: false, value: "" });
      }
      return;
    }
    const modal = document.getElementById("modal");
    if (!modal || !modal.classList.contains("show")) return;
    if (e.key === "Escape") {
      e.preventDefault();
      hideModal();
    }
  });
  if (toolsDrawerEl && !toolsDrawerEl.classList.contains("show")) {
    toolsDrawerEl.setAttribute("inert", "");
  }

  if (chatLogEl) {
    chatLogEl.addEventListener("scroll", () => {
      updateHistoryMoreButtonVisibility();
      updateTimelinePositions();
    });
  }
}

async function init() {
  loadPinnedContext();
  renderContextBadges();
  await loadApiVaultOptions();
  await refreshSession();
  await refreshConversations();
  if (activeConversationId) {
    await loadRecentHistory(activeConversationId);
    _restoreProgressBubbleIfNeeded();
  }
  bindActions();
  renderHeaderStatus();
  loadApiKeyIntoInputs();
  updateApiStatusDisplay();
  validateApiInputs();
  updatePromptPlaceholder();
  normalizePromptDraftFromFollowup();
  renderFollowupLiveStatus();
  renderContextBadges();
  renderSendPreview();
  window.addEventListener("resize", () => {
    updateTimelinePositions();
  });
  if (activeChatPoller) {
    clearInterval(activeChatPoller);
  }
  activeChatPoller = setInterval(() => {
    refreshConversations();
    refreshActiveConversation(false);
    updatePromptPlaceholder();
  }, CONV_POLL_MS);
  if (activeHudTicker) {
    clearInterval(activeHudTicker);
  }
  activeHudTicker = setInterval(() => {
    renderHeaderStatus();
    renderRunHud();
  }, HUD_TICK_MS);
}

init();
