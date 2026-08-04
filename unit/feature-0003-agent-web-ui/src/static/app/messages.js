// feature-0038 Cycle 10 — 메시지 콘텐츠 렌더 (markdown/SQL 코드블록·파일 미리보기·CSV
//   다운로드/인라인 테이블·SQL 스텝 패널/네비게이터·실행단계 블록·메시지 상세·첨부 칩·
//   발화자/아바타). app.js 구 L3118–4068 에서 byte-동치 이동 (본문 무수정 — ITEM-P5b).
import {
  state, showToast, identiconSvg, markdownToHtml, messageLogEl, _downloadAttachmentById,
} from "../app.js?v=dev";

function collapseSqlCodeBlocksInContent(target) {
  // marked 렌더 결과의 ```sql 블록은 쿼리 문자열이므로 항상 표시.
  // (결과셋은 buildSqlStepPanel/buildStepDetailEl 에서 별도 토글로 관리)
}

function renderMessageContent(target, content = "", role = "assistant") {
  target.className = "message-content";
  if (role === "assistant") {
    target.innerHTML = markdownToHtml(content);
    collapseSqlCodeBlocksInContent(target);
    enhanceFilePreviewLinks(target);
    enhanceCsvBlockDownloads(target);
    // feature-0013: ```mermaid → SVG (sanitize 이후 라이브 DOM). mermaid-render.js 미로드 시 가드(no-op).
    if (typeof renderMermaidDiagrams === "function") renderMermaidDiagrams(target);
    return;
  }
  target.innerHTML = markdownToHtml(content || "");
}

// 값 기반 식별 토큰 추출 (TASK-0174) — backend _distinctive_tokens 의 JS 판.
// 천단위 콤마 제거 후 길이 ≥3 숫자열(ID·집계값) + 숫자 없는 라벨(길이 ≥2).
function distinctiveValueTokens(cells) {
  const tokens = new Set();
  for (const cell of cells) {
    const s = String(cell == null ? "" : cell).trim();
    if (!s) continue;
    const nums = s.replace(/,/g, "").match(/\d{3,}/g);
    if (nums) for (const n of nums) tokens.add(n);
    if (!/\d/.test(s) && s.length >= 2) tokens.add(s);
  }
  return tokens;
}

// 메시지 본문의 "📎 전체 N행 미리보기" 링크(에이전트가 생성한 /api/file?path=... 마크다운)를
// 인터랙티브 표 로더로 전환한다 (#120). 에이전트 마크다운에는 conversation_id 가 없어
// 그대로 클릭하면 /api/file 이 422 를 내고, 표가 아닌 문자열 링크로만 보였다.
function enhanceFilePreviewLinks(target) {
  const anchors = target.querySelectorAll('a[href*="/api/file?"]');
  anchors.forEach((anchor) => {
    let csvPath = "";
    try {
      csvPath = new URL(anchor.getAttribute("href"), window.location.origin)
        .searchParams.get("path") || "";
    } catch (_) {
      return;
    }
    if (!csvPath) return;
    anchor.classList.add("file-preview-link");
    anchor.addEventListener("click", (evt) => {
      evt.preventDefault();
      loadCsvAsInlineTable(csvPath, anchor);
    });
  });
}

function _csvDownloadFilename() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const ts = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(
    d.getHours()
  )}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  return `result_${ts}.csv`;
}

// conv-audit (csv-inline-no-download): assistant 가 결과를 인라인 ```csv 코드블록으로 제시하고
// "다운로드하실 수 있습니다" 라고 안내하지만, 그 블록에는 클릭할 다운로드 대상이 없어 사용자가
// 실제로 파일을 받지 못하던 마찰을 닫는다. 서버측 CSV 파일(/api/file)이 있으면 그 경로는
// enhanceFilePreviewLinks 가 이미 처리하고, 서버 파일이 없더라도(소형 결과·직접 붙여넣은 CSV)
// 화면에 렌더된 CSV 텍스트를 그대로 클라이언트 Blob 으로 저장해 항상 다운로드를 보장한다.
// enhanceDiffBlocks/enhanceFilePreviewLinks 와 동일하게 sanitize 이후 라이브 DOM 에서 동작한다.
function enhanceCsvBlockDownloads(target) {
  if (typeof document === "undefined" || !target) return;
  const blocks = target.querySelectorAll("pre > code.language-csv");
  blocks.forEach((codeEl) => {
    const pre = codeEl.closest("pre");
    if (!pre || pre.dataset.csvDownloadReady === "1") return;
    const csvText = (codeEl.textContent || "").replace(/\s+$/, "");
    if (!csvText.trim()) return;
    // 백엔드 _collapse_large_csv_blocks 가 이미 대형 블록을 미리보기로 접고 전체 파일
    // /api/file 링크를 바로 뒤에 주입한 경우, 절단된 미리보기에 다운로드 버튼을 붙이면
    // 일부 행만 받는 오해를 준다 → 그 경우 버튼 생략(전체 파일 링크가 canonical 다운로드).
    const nextEl = pre.nextElementSibling;
    if (nextEl && nextEl.querySelector && nextEl.querySelector('a[href*="/api/file?"]')) {
      pre.dataset.csvDownloadReady = "1";
      return;
    }
    pre.dataset.csvDownloadReady = "1";
    pre.classList.add("csv-block");
    const bar = document.createElement("div");
    bar.className = "csv-block-actions";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tool-btn csv-download-btn";
    btn.textContent = "📥 CSV 다운로드";
    btn.title = "위 CSV 데이터를 파일로 저장합니다";
    btn.addEventListener("click", () => {
      try {
        // UTF-8 BOM(U+FEFF) 부여 — Excel 에서 한글 CSV 가 깨지지 않게 한다.
        const blob = new Blob(["\uFEFF" + csvText + "\n"], {
          type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = _csvDownloadFilename();
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1500);
      } catch (_) {
        // best-effort — 다운로드 실패가 대화 렌더를 막지 않는다.
      }
    });
    bar.appendChild(btn);
    pre.parentNode.insertBefore(bar, pre.nextSibling);
  });
}

async function loadCsvAsInlineTable(csvPath, anchorEl) {
  const block = anchorEl.closest("p") || anchorEl;
  if (block.dataset.fullTableExpanded === "1") return; // 이미 펼침
  const originalText = anchorEl.textContent;
  anchorEl.textContent = "불러오는 중...";
  anchorEl.style.pointerEvents = "none";
  try {
    // conversation_id 는 항상 현재 활성 대화 기준으로 주입 (에이전트 링크엔 없음 → 422 원인).
    const url = `/api/file?path=${encodeURIComponent(csvPath)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`CSV 요청 실패 (${response.status})`);
    }
    const text = await response.text();
    const rows = parseCsv(text).filter((r) => r.length && !(r.length === 1 && r[0] === ""));
    if (!rows.length) {
      throw new Error("CSV에 표시할 데이터가 없습니다.");
    }
    const body = rows.slice(1);

    // 방어 가드 (#118 인라인 경로, TASK-0174): 로드한 CSV 의 값 토큰이 인접
    // 미리보기 표와 전혀 겹치지 않으면 다른 쿼리 결과(과거 링크 오정렬 등)이므로
    // 인라인 렌더를 거부한다. 헤더명이 아닌 값으로 비교(LLM 헤더 리네이밍 오탐 방지).
    const previewTableEl =
      block.previousElementSibling && block.previousElementSibling.tagName === "TABLE"
        ? block.previousElementSibling
        : null;
    if (previewTableEl) {
      const previewTokens = distinctiveValueTokens(
        Array.from(previewTableEl.querySelectorAll("td")).map((td) => td.textContent)
      );
      const csvCells = [];
      for (const r of body) for (const c of r) csvCells.push(c);
      const csvTokens = distinctiveValueTokens(csvCells);
      // previewTokens 가 2개 이상일 때만 강제 거부 — 단일 토큰 우연 불일치로
      // 정상 데이터를 막는 오탐을 줄인다 (재포맷·반올림 내성).
      if (previewTokens.size >= 2 && csvTokens.size) {
        let overlaps = false;
        for (const t of previewTokens) {
          if (csvTokens.has(t)) { overlaps = true; break; }
        }
        if (!overlaps) {
          throw new Error("결과 파일이 미리보기와 일치하지 않아 전체 데이터를 표시할 수 없습니다.");
        }
      }
    }

    const tableWrap = buildResultTable({ columns: rows[0], rows: body, truncated: false });
    if (!tableWrap) {
      throw new Error("표를 생성할 수 없습니다.");
    }
    tableWrap.classList.add("is-full-data");

    // 펼친 표를 헤더바(행수 + 접기)와 함께 감싸 메시지를 영구 점유하지 않게 한다 (#122).
    const container = document.createElement("div");
    container.className = "inline-full-table";
    const bar = document.createElement("div");
    bar.className = "inline-full-table-bar";
    const count = document.createElement("span");
    count.className = "inline-full-table-count";
    count.textContent = `전체 ${body.length}행`;
    const collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.className = "tool-btn";
    collapseBtn.textContent = "접기";
    bar.append(count, collapseBtn);
    container.append(bar, tableWrap);

    // 직전 markdown 미리보기 표(있으면)와 링크 단락을 숨기고 그 자리에 펼친 표 삽입.
    const previewTable =
      block.previousElementSibling && block.previousElementSibling.tagName === "TABLE"
        ? block.previousElementSibling
        : null;
    block.after(container);
    block.style.display = "none";
    if (previewTable) previewTable.style.display = "none";
    block.dataset.fullTableExpanded = "1";
    anchorEl.textContent = originalText;
    anchorEl.style.pointerEvents = "";

    // 접기 — 펼친 표 제거 후 미리보기/링크 복원 (토글).
    collapseBtn.addEventListener("click", () => {
      container.remove();
      block.style.display = "";
      if (previewTable) previewTable.style.display = "";
      delete block.dataset.fullTableExpanded;
    });
  } catch (error) {
    anchorEl.textContent = originalText;
    anchorEl.style.pointerEvents = "";
    showToast(error.message || "전체 데이터를 불러오지 못했습니다.", true);
  }
}

function appendDetailBlock(parentEl, title, contentNode) {
  const block = document.createElement("div");
  block.className = "message-detail-block";
  if (title) {
    const strong = document.createElement("strong");
    strong.textContent = title;
    block.appendChild(strong);
  }
  block.appendChild(contentNode);
  parentEl.appendChild(block);
}

function extractFirstTableRef(sql = "") {
  const match = String(sql || "").match(
    /(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?/i,
  );
  return match ? `${match[1]}.${match[2]}` : "";
}

// 단순 CSV 파서 — 따옴표, 이스케이프된 따옴표(""), CR/LF 처리.
function parseCsv(text = "") {
  const rows = [];
  let row = [];
  let current = "";
  let inQuotes = false;
  const src = String(text || "");
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (inQuotes) {
      if (ch === '"' && src[i + 1] === '"') {
        current += '"';
        i++;
        continue;
      }
      if (ch === '"') {
        inQuotes = false;
        continue;
      }
      current += ch;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(current);
      current = "";
      continue;
    }
    if (ch === "\r") continue;
    if (ch === "\n") {
      row.push(current);
      rows.push(row);
      row = [];
      current = "";
      continue;
    }
    current += ch;
  }
  if (current.length || row.length) {
    row.push(current);
    rows.push(row);
  }
  return rows;
}

function appendRowNumCell(tr, tag, value) {
  const cell = document.createElement(tag);
  cell.className = "col-rownum";
  cell.textContent = String(value);
  tr.appendChild(cell);
  return cell;
}

// markdown 표 문자열(| a | b |\n|---|---|\n| 1 | 2 |)을 {columns, rows} 로 파싱.
// execute_sql 외 도구(get_sample_rows/describe_table 등)의 결과 preview 는 구조화
// preview_table 없이 markdown 표 문자열만 있어, 이를 파싱해 buildResultTable 로 표 렌더.
// 표가 아니면(헤더/구분선 패턴 불일치) null → 호출부가 raw <pre> 로 폴백.
function parseMarkdownTablePreview(text) {
  const raw = String(text || "");
  if (!raw.includes("|")) return null;
  const lines = raw.split("\n");
  const tableLines = [];
  for (const ln of lines) {
    const t = ln.trim();
    if (t.startsWith("|") && t.endsWith("|") && t.length > 1) {
      tableLines.push(t);
    } else if (tableLines.length) {
      break; // 표 블록(연속된 | 라인) 종료 — 이후 "(N 행)"/"CSV 저장" 등은 무시
    }
  }
  if (tableLines.length < 2) return null;
  const splitRow = (ln) => ln.slice(1, -1).split("|").map((c) => c.trim());
  const columns = splitRow(tableLines[0]);
  if (!columns.length) return null;
  // 2번째 줄이 구분선(---, :--:)이어야 표로 인정
  const sepCells = splitRow(tableLines[1]);
  const isSeparator = sepCells.length > 0 && sepCells.every((c) => /^:?-{1,}:?$/.test(c.replace(/\s/g, "")));
  if (!isSeparator) return null;
  const rows = tableLines.slice(2).map(splitRow);
  return { columns, rows, truncated: false };
}

function buildResultTable(previewTable) {
  const { columns = [], rows = [], truncated = false } = previewTable;
  if (!columns.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "result-table-wrap";

  const tableEl = document.createElement("table");
  tableEl.className = "result-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  appendRowNumCell(headRow, "th", "#");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = String(col);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, ri) => {
    const tr = document.createElement("tr");
    appendRowNumCell(tr, "td", ri + 1);
    columns.forEach((_, ci) => {
      const td = document.createElement("td");
      td.textContent = row[ci] != null ? String(row[ci]) : "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tableEl.appendChild(tbody);
  wrap.appendChild(tableEl);

  const meta = document.createElement("div");
  meta.className = "result-table-meta";
  const shown = rows.length;
  const colCount = columns.length;
  meta.textContent = truncated
    ? `${shown}행 표시 중 (더 있음) · ${colCount}열`
    : `${shown}행 · ${colCount}열`;
  wrap.appendChild(meta);

  // 테이블 래퍼에 참조용 핸들 노출 — 전체 데이터 로드 시 tbody 교체에 사용
  wrap._tableEl = tableEl;
  wrap._metaEl = meta;
  wrap._colCount = colCount;
  // 전체 데이터 로드 시 CSV 헤더 검증용 — 미리보기 컬럼 보관 (#118)
  wrap._previewColumns = columns.map((c) => String(c));
  return wrap;
}

async function loadFullCsvIntoTable(csvPath, tableWrap, buttonEl) {
  if (!tableWrap || !tableWrap._tableEl) return;
  const originalText = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "불러오는 중...";
  try {
    const url = `/api/file?path=${encodeURIComponent(csvPath)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`CSV 요청 실패 (${response.status})`);
    }
    const text = await response.text();
    const rows = parseCsv(text).filter((r) => r.length && !(r.length === 1 && r[0] === ""));
    if (!rows.length) {
      throw new Error("CSV에 표시할 데이터가 없습니다.");
    }
    const header = rows[0];
    const body = rows.slice(1);
    // 방어 가드 (#118): 불러온 CSV 헤더가 미리보기 컬럼과 불일치하면 잘못된
    // 결과 파일(과거 save_csv 파일명 충돌로 덮어써진 케이스 등)이므로 표 교체를
    // 거부한다. 다른 쿼리 데이터를 조용히 "전체"로 표시하던 오염을 차단한다.
    const expectedCols = tableWrap._previewColumns;
    if (Array.isArray(expectedCols) && expectedCols.length) {
      const norm = (s) => String(s == null ? "" : s).trim();
      const mismatch =
        header.length !== expectedCols.length ||
        header.some((h, i) => norm(h) !== norm(expectedCols[i]));
      if (mismatch) {
        throw new Error("결과 파일이 미리보기와 일치하지 않아 전체 데이터를 표시할 수 없습니다.");
      }
    }
    const tableEl = tableWrap._tableEl;
    // 헤더 재구성 (RowCount 가상 컬럼 유지)
    const thead = tableEl.querySelector("thead");
    thead.innerHTML = "";
    const headRow = document.createElement("tr");
    appendRowNumCell(headRow, "th", "#");
    header.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    // 본문 재구성 (각 tr 에 행 번호 prepend)
    const tbody = tableEl.querySelector("tbody");
    tbody.innerHTML = "";
    body.forEach((row, ri) => {
      const tr = document.createElement("tr");
      appendRowNumCell(tr, "td", ri + 1);
      header.forEach((_, ci) => {
        const td = document.createElement("td");
        td.textContent = row[ci] != null ? row[ci] : "";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tableWrap.classList.add("is-full-data");
    tableWrap._metaEl.textContent = `${body.length}행 · ${header.length}열 (전체)`;
    buttonEl.textContent = "전체 데이터 로드됨";
    buttonEl.setAttribute("aria-disabled", "true");
  } catch (error) {
    buttonEl.disabled = false;
    buttonEl.textContent = originalText;
    showToast(error.message || "전체 데이터를 불러오지 못했습니다.", true);
  }
}

const SQL_FORMAT_KEYWORDS = [
  "LEFT OUTER JOIN",
  "RIGHT OUTER JOIN",
  "FULL OUTER JOIN",
  "LEFT JOIN",
  "RIGHT JOIN",
  "INNER JOIN",
  "OUTER JOIN",
  "FULL JOIN",
  "CROSS JOIN",
  "UNION ALL",
  "GROUP BY",
  "ORDER BY",
  "INSERT INTO",
  "DELETE FROM",
  "SELECT",
  "FROM",
  "WHERE",
  "HAVING",
  "LIMIT",
  "OFFSET",
  "UNION",
  "UPDATE",
  "SET",
  "VALUES",
];

function formatSqlForDisplay(raw = "") {
  const src = String(raw || "").trim();
  if (!src) return "";
  if (/\n/.test(src)) return src;

  const literals = [];
  const literalRe = /('([^'\\]|\\.|'')*'|"([^"\\]|\\.|"")*"|`[^`]*`)/g;
  const masked = src.replace(literalRe, (m) => {
    literals.push(m);
    return `\u0001${literals.length - 1}\u0001`;
  });

  const keywordAlt = SQL_FORMAT_KEYWORDS
    .map((k) => k.replace(/ /g, "\\s+"))
    .join("|");
  const pattern = new RegExp(`\\s+(?=\\b(?:${keywordAlt})\\b)`, "gi");
  let formatted = masked.replace(pattern, "\n");

  formatted = formatted.replace(/\u0001(\d+)\u0001/g, (_, i) => literals[Number(i)]);
  return formatted;
}

function buildSqlStepPanel(step) {
  const panel = document.createElement("div");
  panel.className = "sql-result-group";

  // 근거 — execute_sql 단계도 수행 이유를 표 위에 명시(side panel 과 일관).
  const reason = String((step && step.reason) || "").trim();
  if (reason) {
    const reasonEl = document.createElement("div");
    reasonEl.className = "step-reason";
    const reasonLabel = document.createElement("span");
    reasonLabel.className = "step-reason-label";
    reasonLabel.textContent = "근거";
    reasonEl.appendChild(reasonLabel);
    const reasonText = document.createElement("span");
    reasonText.className = "step-reason-text";
    reasonText.textContent = reason;
    reasonEl.appendChild(reasonText);
    panel.appendChild(reasonEl);
  }

  // SQL 블록 — 쿼리 문자열은 항상 표시
  if (step.sql) {
    const sqlWrap = document.createElement("div");
    sqlWrap.className = "sql-toggle-wrap";
    const pre = document.createElement("pre");
    pre.className = "sql-block";
    pre.textContent = formatSqlForDisplay(step.sql);
    sqlWrap.append(pre);
    panel.appendChild(sqlWrap);
  }

  // 결과셋 — 기본 숨김, "결과 보기" 버튼 클릭 시 토글
  const rs = step.result_summary;
  let tableWrap = null;
  let firstCsvPath = "";
  let truncated = false;
  let csvPaths = [];
  if (rs && typeof rs === "object") {
    const pt = rs.preview_table;
    if (pt && pt.columns?.length) {
      tableWrap = buildResultTable(pt);
      truncated = Boolean(pt.truncated);
    }
    csvPaths = Array.isArray(rs.csv_paths) ? rs.csv_paths : [];
    if (csvPaths.length) firstCsvPath = csvPaths[0];

    if (tableWrap || csvPaths.length) {
      const resultToggleWrap = document.createElement("div");
      resultToggleWrap.className = "sql-result-toggle-wrap";

      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "tool-btn sql-toggle-btn";
      toggleBtn.textContent = "결과 보기";
      toggleBtn.setAttribute("aria-expanded", "false");

      const resultBody = document.createElement("div");
      resultBody.className = "sql-result-body";
      resultBody.hidden = true;

      if (tableWrap) resultBody.appendChild(tableWrap);

      if (csvPaths.length || (tableWrap && truncated)) {
        const actions = document.createElement("div");
        actions.className = "sql-result-actions";

        if (tableWrap && truncated && firstCsvPath) {
          const loadBtn = document.createElement("button");
          loadBtn.type = "button";
          loadBtn.className = "tool-btn";
          loadBtn.textContent = "전체 데이터 보기";
          loadBtn.title = "CSV에서 전체 행을 이 화면 표에 불러옵니다";
          loadBtn.addEventListener("click", (evt) => {
            evt.preventDefault();
            loadFullCsvIntoTable(firstCsvPath, tableWrap, loadBtn);
          });
          actions.appendChild(loadBtn);
        }

        csvPaths.forEach((path, i) => {
          const link = document.createElement("a");
          link.className = "message-link";
          link.href = `/api/file?path=${encodeURIComponent(path)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = `CSV 다운로드${csvPaths.length > 1 ? ` ${i + 1}` : ""}`;
          link.title = "새 탭에서 원본 CSV 파일을 연다";
          actions.appendChild(link);
        });

        resultBody.appendChild(actions);
      }

      toggleBtn.addEventListener("click", () => {
        const willShow = resultBody.hidden;
        resultBody.hidden = !willShow;
        toggleBtn.textContent = willShow ? "결과 닫기" : "결과 보기";
        toggleBtn.setAttribute("aria-expanded", String(willShow));
      });

      resultToggleWrap.append(toggleBtn, resultBody);
      panel.appendChild(resultToggleWrap);
    }
  }

  return panel;
}

function buildSqlNavigator(sqlSteps) {
  const root = document.createElement("div");
  root.className = "sql-navigator";
  root.setAttribute("tabindex", "0");
  root.setAttribute("role", "group");
  root.setAttribute("aria-label", "SQL 쿼리 결과 탐색");

  const header = document.createElement("div");
  header.className = "sql-nav-header";

  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "sql-nav-btn";
  prevBtn.innerHTML = "&#9664;";
  prevBtn.setAttribute("aria-label", "이전 쿼리");
  prevBtn.title = "이전 쿼리 (←)";

  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "sql-nav-btn";
  nextBtn.innerHTML = "&#9654;";
  nextBtn.setAttribute("aria-label", "다음 쿼리");
  nextBtn.title = "다음 쿼리 (→)";

  const indicator = document.createElement("span");
  indicator.className = "sql-nav-indicator";
  indicator.setAttribute("aria-live", "polite");

  const context = document.createElement("span");
  context.className = "sql-nav-context";

  header.append(prevBtn, indicator, nextBtn, context);
  root.appendChild(header);

  const panels = document.createElement("div");
  panels.className = "sql-nav-panels";
  root.appendChild(panels);

  const panelEls = sqlSteps.map((step) => {
    const p = buildSqlStepPanel(step);
    p.className += " sql-nav-panel";
    panels.appendChild(p);
    return p;
  });

  let activeIdx = 0;
  // 결과셋마다 높이가 달라 ◀▶ 전환 시 panels 컨테이너가 줄었다 늘었다 하며
  // 아래 콘텐츠가 점프한다. 지금까지 본 최대 패널 높이를 floor 로 박아
  // 짧은 결과셋으로 전환해도 컨테이너가 줄지 않게 한다(확장 높이 보존).
  let maxPanelHeight = 0;
  function preserveHeight() {
    const h = panels.scrollHeight;
    if (h > maxPanelHeight) {
      maxPanelHeight = h;
      panels.style.minHeight = maxPanelHeight + "px";
    }
  }
  function update() {
    // 전환 직전, 현재 보이는(나가는) 패널 높이를 먼저 기록한다.
    // 초기 update() 는 아직 DOM 에 붙기 전이라 scrollHeight=0 → floor 무변(무해).
    preserveHeight();
    panelEls.forEach((el, i) => {
      el.classList.toggle("is-active", i === activeIdx);
    });
    indicator.textContent = `쿼리 ${activeIdx + 1}/${sqlSteps.length}`;
    const step = sqlSteps[activeIdx] || {};
    const ref = extractFirstTableRef(step.sql);
    context.textContent = ref ? `대상: ${ref}` : "";
    prevBtn.disabled = activeIdx <= 0;
    nextBtn.disabled = activeIdx >= sqlSteps.length - 1;
    // 들어오는 패널이 더 크면 floor 를 키운다(축소만 방지, 확장은 허용).
    preserveHeight();
  }
  function go(delta) {
    const next = Math.min(Math.max(activeIdx + delta, 0), sqlSteps.length - 1);
    if (next !== activeIdx) {
      activeIdx = next;
      update();
    }
  }
  function goTo(idx) {
    const next = Math.min(Math.max(idx, 0), sqlSteps.length - 1);
    if (next !== activeIdx) {
      activeIdx = next;
      update();
    }
  }

  prevBtn.addEventListener("click", (evt) => {
    evt.preventDefault();
    go(-1);
    root.focus();
  });
  nextBtn.addEventListener("click", (evt) => {
    evt.preventDefault();
    go(1);
    root.focus();
  });
  root.addEventListener("keydown", (evt) => {
    // 내부 input/textarea에 포커스가 있으면 무시
    const target = evt.target;
    if (target && target !== root && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
      return;
    }
    if (evt.key === "ArrowLeft") {
      evt.preventDefault();
      go(-1);
    } else if (evt.key === "ArrowRight") {
      evt.preventDefault();
      go(1);
    } else if (evt.key === "Home") {
      evt.preventDefault();
      goTo(0);
    } else if (evt.key === "End") {
      evt.preventDefault();
      goTo(sqlSteps.length - 1);
    }
  });

  update();
  return root;
}

function buildStepBlocks(steps, containerEl) {
  // execute_sql 단계는 SQL + 결과 테이블 + CSV 링크로 묶어 표시
  // 나머지 단계는 요약 목록으로 표시. 2개 이상이면 Navigator로 압축.
  const nonSqlSteps = steps.filter((s) => String(s.tool || "") !== "execute_sql");
  const sqlSteps = steps.filter((s) => String(s.tool || "") === "execute_sql");

  if (nonSqlSteps.length) {
    const list = document.createElement("ul");
    nonSqlSteps.forEach((step) => {
      const item = document.createElement("li");
      const work = String(step.work || step.intent || step.tool || "단계").trim();
      const reason = String(step.reason || "").trim();
      item.textContent = reason ? `${work} — ${reason}` : work;
      list.appendChild(item);
    });
    appendDetailBlock(containerEl, "단계", list);
  }

  if (!sqlSteps.length) return;
  if (sqlSteps.length === 1) {
    const label = document.createElement("div");
    label.className = "sql-result-label";
    label.textContent = "SQL 쿼리";
    containerEl.appendChild(label);
    containerEl.appendChild(buildSqlStepPanel(sqlSteps[0]));
    return;
  }
  containerEl.appendChild(buildSqlNavigator(sqlSteps));
}

function renderMessageDetails(meta = {}) {
  const steps = Array.isArray(meta?.steps) ? meta.steps : [];
  const hasSql = steps.some((s) => String(s.tool || "") === "execute_sql" && s.sql);
  const hasDetails = hasSql || meta?.rationale || steps.length || Array.isArray(meta?.csv_paths) && meta.csv_paths.length;
  if (!hasDetails) return null;

  const detailsEl = document.createElement("details");
  detailsEl.className = "message-details";
  // SQL 결과가 있으면 테이블이 기본 노출되도록 자동 펼침
  if (hasSql) detailsEl.open = true;
  const summary = document.createElement("summary");
  summary.textContent = hasSql ? "쿼리 결과" : "실행 단계";
  detailsEl.appendChild(summary);

  // 스크롤 앵커: 펼침/접힘 시 summary 라인이 뷰포트 내 동일 위치에 유지되도록 보정.
  summary.addEventListener("click", () => {
    if (!messageLogEl) return;
    const logRect = messageLogEl.getBoundingClientRect();
    const prevOffset = summary.getBoundingClientRect().top - logRect.top;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const newOffset = summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top;
        const delta = newOffset - prevOffset;
        if (delta !== 0) {
          messageLogEl.scrollTop += delta;
        }
      });
    });
  });

  const body = document.createElement("div");
  body.className = "message-details-body";

  if (steps.length) {
    buildStepBlocks(steps, body);
  } else {
    // steps가 없는 구형 메시지 — 기존 필드로 폴백 (쿼리 문자열은 항상 표시)
    if (meta.sql) {
      const sqlWrap = document.createElement("div");
      sqlWrap.className = "sql-toggle-wrap";
      const pre = document.createElement("pre");
      pre.className = "sql-block";
      pre.textContent = String(meta.sql);
      sqlWrap.append(pre);
      appendDetailBlock(body, "실행 SQL", sqlWrap);
    }
    if (Array.isArray(meta.csv_paths) && meta.csv_paths.length) {
      const wrap = document.createElement("div");
      wrap.className = "message-link-list";
      meta.csv_paths.forEach((path, index) => {
        const link = document.createElement("a");
        link.className = "message-link";
        link.href = `/api/file?path=${encodeURIComponent(path)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `CSV ${index + 1}`;
        wrap.appendChild(link);
      });
      appendDetailBlock(body, "결과 파일", wrap);
    }
  }

  detailsEl.appendChild(body);
  return detailsEl;
}

// ③ TASK-0285: 메시지 말풍선 첨부 칩 빌더(user/assistant 공통). att 는 user snapshot
// ({name,size,id,signed_url}) 또는 백엔드 직렬화({original_filename,size,id,version_number,
// is_assistant_generated}) 형식 모두 허용한다. 다운로드는 id 가 있으면 web 프록시 경로
// (/api/attachments/{id}/download, 외부 머신 호환·same-origin 쿠키 인증), 없으면 signed_url.
function _buildMessageAttachChip(att) {
  const chip = document.createElement("span");
  chip.className = "message-bubble-attach-chip";
  const attName = att.name || att.original_filename || "파일";
  const downloadable = Boolean(att.id || att.signed_url);
  if (downloadable) {
    chip.classList.add("has-download");
    chip.title = "클릭하여 다운로드";
    chip.addEventListener("click", () => {
      // ★ TASK-0287: 목록 다운로드(_downloadAttachmentById)와 동일한 fetch+blob 방식으로 통일.
      // 기존 <a href download> navigation 은 octet-stream 프록시(/api/attachments/{id}/download,
      // TASK-0284)에서 다운로드가 실패했다 — 목록은 TASK-0284 에서 fetch+blob 으로 전환했으나
      // 말풍선 칩(TASK-0285)은 navigation 으로 남아 있었다. id 가 있으면 프록시 fetch, 없고
      // signed_url 만 있으면(드문 폴백) 기존 navigation 유지.
      if (att.id) {
        _downloadAttachmentById(att.id, attName, null);
      } else if (att.signed_url) {
        const a = document.createElement("a");
        a.href = att.signed_url;
        a.download = attName;
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    });
  }
  const nameEl = document.createElement("span");
  nameEl.className = "attach-chip-name";
  nameEl.textContent = attName;
  const sizeEl = document.createElement("span");
  sizeEl.className = "attach-chip-size";
  const sizeKb = Math.max(1, Math.round((Number(att.size) || 0) / 1024));
  sizeEl.textContent = `${sizeKb} KB`;
  const parts = [nameEl, sizeEl];
  // 버전 배지 — AI 수정본 또는 version>1 표시(첨부 목록 패널 배지와 일관).
  const verNum = Number(att.version_number || 1);
  const isAi = Boolean(att.is_assistant_generated);
  if (isAi || verNum > 1) {
    const verEl = document.createElement("span");
    verEl.className = "attach-chip-ver" + (isAi ? " ai-edited" : "");
    verEl.textContent = isAi ? `v${verNum} · AI 수정` : `v${verNum}`;
    parts.push(verEl);
  }
  if (downloadable) {
    const dlIcon = document.createElement("span");
    dlIcon.className = "attach-chip-dl";
    dlIcon.textContent = "↓";
    parts.push(dlIcon);
  }
  chip.append(...parts);
  return chip;
}

// feature-0009: 텍스트가 주어진 (소문자) username 을 @멘션하는지 — canonical mentions.js 사용.
function _mentionsUser(text, myNameLower) {
  if (!text || !myNameLower || !window.Mentions) return false;
  try {
    const names = window.Mentions.parseMentions(text).mentionedUsernames || [];
    return names.some((n) => String(n).toLowerCase() === myNameLower);
  } catch (_e) {
    return false;
  }
}

// msg-speaker-attribution: assistant 말풍선의 발화자(제품) 표시값을 **그 메시지에 각인된 귀속**
// 에서 해석한다. 각인 키(product_mode/product_id/product_key/product_name)는 답변 저장 시점에
// agent_core 가, 각인 이전 메시지는 제품 전환·fork 시점에 web 이 기입한다. 각인이 전혀 없는
// legacy 메시지만 legacyFallback(대화 바인딩 기준 — 종전 동작)으로 떨어진다.
//
// 라벨·Identicon 시드는 **각인 스냅샷 우선**이다. 제품이 개명·삭제되거나 열람자에게 접근권이
// 없어도 그 대화에서 누가 말했는지가 보존돼야 하고, 무엇보다 이후 어떤 변경으로도 과거 발화자가
// 다시 바뀌지 않는다(이 함수가 존재하는 이유). 아이콘 이미지만 현재 제품 설정을 따른다.
function _assistantSpeakerFor(meta, products, legacyFallback) {
  const m = meta || {};
  if (!("product_mode" in m)) return legacyFallback;   // 각인 이전 메시지 — 종전 폴백 유지.
  if (String(m.product_mode) === "auto" || !m.product_id) {
    return { icon: "", label: "", seed: "" };          // 제품 미고정 답변 → 'AI' 배지로 영구 확정.
  }
  const live = (Array.isArray(products) ? products : [])
    .find((p) => Number(p.id) === Number(m.product_id));
  const liveName = live ? (live.name || live.product_key || "") : "";
  const liveKey = live ? (live.product_key || live.name || "") : "";
  return {
    icon: (live && live.icon_url) ? live.icon_url : "",
    label: String(m.product_name || m.product_key || liveName || ""),
    seed: String(m.product_key || m.product_name || liveKey || ""),
  };
}

// feature-0009: 메시지 발신자 프로필 아이콘. user=계정 실제 아바타(/api/avatars/{id}), 없으면 username Identicon.
// assistant=그 답변을 낸 제품(Product) 아이콘, 없으면 제품 Identicon(제품 칩과 동일 시드), 제품 자체가 없으면(auto) 'AI' 배지.
// 헤더/프로필의 applyAvatar()/identiconSvg() 와 동일한 Identicon 폴백을 써서, 아바타 미업로드 시에도 "맨 글자"가 아니라
// 실제 프로필과 정합하는 컬러 아이콘으로 표시한다 (gc-avatar-identicon).
function _msgAvatarEl(senderId, label, role, assistantIcon, seed) {
  const av = document.createElement("span");
  av.className = "msg-avatar" + (role === "assistant" ? " msg-avatar-assistant" : "");
  av.title = label || (role === "assistant" ? "Assistant" : "");
  const idSeed = String(seed || label || "");
  if (role === "assistant") {
    if (assistantIcon) {
      _fillMsgAvatar(av, assistantIcon, idSeed, "AI");        // 제품 아이콘 → 실패 시 제품 Identicon → "AI"
    } else if (idSeed) {
      _fillMsgIdenticon(av, idSeed);                          // 제품은 있으나 아이콘 미설정 → 제품 Identicon
    } else {
      av.textContent = "AI";                                  // 제품 없음(auto) → 'AI' 배지
    }
    return av;
  }
  if (senderId) {
    _fillMsgAvatar(av, `/api/avatars/${encodeURIComponent(senderId)}`, idSeed, "");  // 실제 아바타 → 실패 시 Identicon
  } else {
    _fillMsgIdenticon(av, idSeed);                            // senderId 없음 → username Identicon
  }
  return av;
}
// <img> 로드 시도 → 성공 시 표시, 실패(404 등) 시 Identicon(seed) 또는 텍스트로 폴백. applyAvatar() 와 동형.
function _fillMsgAvatar(av, url, seed, textFallback) {
  const img = document.createElement("img");
  img.src = url;
  img.alt = "";
  img.loading = "lazy";
  img.addEventListener("load", () => av.classList.add("has-img"));
  img.addEventListener("error", () => {
    try { img.remove(); } catch (_e) {}
    if (seed) _fillMsgIdenticon(av, seed);
    else if (textFallback) av.textContent = textFallback;
  });
  av.appendChild(img);
}
// Identicon SVG 로 채운다 (headers/profile 의 identiconSvg 와 동일 시드 해시 → 같은 사용자/제품은 같은 아이콘).
function _fillMsgIdenticon(av, seed) {
  av.classList.add("has-img");
  av.innerHTML = identiconSvg(seed, 100);
}

export { renderMessageContent, renderMessageDetails, buildResultTable, parseMarkdownTablePreview, _buildMessageAttachChip, _msgAvatarEl, _mentionsUser, _assistantSpeakerFor };
