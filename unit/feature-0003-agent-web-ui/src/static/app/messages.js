// feature-0038 Cycle 10 — 메시지 콘텐츠 렌더 (markdown/SQL 코드블록·파일 미리보기·CSV
//   다운로드/인라인 테이블·첨부 칩·발화자/아바타). app.js 구 L3118–4068 에서 byte-동치
//   이동 (본문 무수정 — ITEM-P5b).
//
// 말풍선 안 「▼ 쿼리 결과 / 실행 단계」 여닫이(`renderMessageDetails` 와 그 하위 조립 —
// SQL 스텝 패널·결과 네비게이터·단계 블록)는 2026-09-01 사용자 결정으로 **제거**했다.
// 같은 단계·SQL·결과를 「단계 보기」 사이드 패널(`buildStepDetailEl`)이 더 정확하게
// 보여주고 있어 말풍선 쪽은 중복 표시면이었다. 되살릴 일이 있으면 그 패널을 정본으로
// 두고 판단한다 — 표시면을 두 벌로 되돌리는 것이 이 자리의 원래 결함이었다.
import {
  state, showToast, identiconSvg, markdownToHtml, _downloadAttachmentById,
  apiFetch,
} from "../app.js?v=dev";
// attach-diff-bubble-chip: 말풍선 칩의 비교·원문 진입점도 **저장소 단일 모달**을 쓴다.
// 첨부 사이드 패널(composer.js)이 쓰는 것과 같은 모듈이며, 렌더러를 복제하지 않는다
// (복제가 곧 결함 기전 — modal-dismiss.js·attach-diff.js 주석의 같은 근거).
import { openAttachmentDiffModal, openAttachmentSourceModal } from "./attach-diff.js?v=dev";

function collapseSqlCodeBlocksInContent(target) {
  // marked 렌더 결과의 ```sql 블록은 쿼리 문자열이므로 항상 표시.
  // (결과셋은 「단계 보기」 패널의 buildStepDetailEl 에서 별도 토글로 관리)
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
  // attach-diff-bubble-chip: 수정본 칩에서 **그 수정 내용**으로 바로 들어가는 버튼.
  // 사용자 요청(2026-08-11): "assistant 가 답변을 전달할 때, 첨부파일의 수정이 나타났다면
  // 해당 수정에 따라 diff 패널이 출력될 수 있도록 버튼을 구성해주세요."
  //
  // 종전에 이 칩에서 할 수 있는 일은 다운로드뿐이었다. 방금 받은 답변이 만든 변경을 보려면
  // 첨부 사이드 패널을 열고 → 그 파일을 찾고 → "버전 N개 ▾" 를 펼치고 → `⇄` 를 눌러야 했다.
  // 변경을 만든 화면에서 그 변경으로 가는 길이 없었던 셈이다.
  //
  // 조건은 **`version_number > 1` + id 보유** — 즉 "비교할 짝이 존재하는가" 다. v1(신규 생성)은
  // 직전 버전이 없어 diff 자체가 성립하지 않으므로 버튼을 두지 않는다(거짓 어포던스 금지 —
  // attach-diff.js 의 하이라이트 토글 노출 판정과 같은 원칙). AI 수정본으로 좁히지 않는 이유:
  // 같은 화면에서 사용자 재업로드 v2 칩에는 버튼이 없는 비대칭이 되고, 칩의 버전 배지는 이미
  // 두 경우 모두에 붙는다(위 `attach-chip-ver`).
  // REQ-20260814-attach-version-tree-ui(§18.8 적대 리뷰 [P1]): **AI 수정본은 v1 이어도 비교 대상이
  // 반드시 있다** — 정의상 사람 계보에서 분기해 나온 것이기 때문이다. `verNum > 1` 만 보면 계보가
  // 갈린 뒤의 핵심 시나리오(사용자 v1 ↔ AI v1)에서 진입점이 아예 사라진다.
  const _isAiEdit = !!(att.is_assistant_generated || att.created_by_role === "assistant");
  if (att.id && (verNum > 1 || _isAiEdit)) {
    const cmpBtn = document.createElement("button");
    cmpBtn.type = "button";
    cmpBtn.className = "attach-chip-cmp";
    cmpBtn.textContent = "⇄";
    cmpBtn.title = `v${verNum} 수정 내용 보기 (직전 버전과 비교)`;
    cmpBtn.setAttribute("aria-label", `${attName} 버전 ${verNum} 의 수정 내용 비교`);
    cmpBtn.addEventListener("click", (evt) => {
      // 칩 자체의 click 은 다운로드다 — 비교를 누르려다 파일이 함께 내려가면 안 된다
      // (첨부 목록 행이 원문 보기를 얻을 때 지킨 것과 같은 계약).
      evt.stopPropagation();
      evt.preventDefault();
      _openBubbleAttachDiff(att, attName, verNum, cmpBtn);
    });
    parts.push(cmpBtn);
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

// attach-diff-bubble-chip: 칩의 `⇄` 실행부. 칩 payload 에는 버전 **체인**이 없으므로
// (`_serialize_attachment_for_api` 는 그 한 행만 싣는다) 누를 때 lazy 로 체인을 불러
// 비교 모달에 넘긴다 — 말풍선마다 선행 조회를 깔면 첨부 N개짜리 대화를 열 때마다 N회
// 왕복이 생기고, 그 대부분은 아무도 누르지 않는다.
async function _openBubbleAttachDiff(att, attName, thisVer, btn) {
  // 재진입 가드. `disabled` **하나만으로는 부족하다** — 그 속성은 trusted 클릭을 막지만
  // 프로그램 dispatch 와 (브라우저 구현에 따라) 아주 빠른 연속 입력에서는 리스너가 그대로
  // 실행돼 같은 왕복이 여러 번 뜨고 모달이 겹쳐 쌓인다(codex P2 가 지적한 축을 테스트로
  // 재현: dispatch 3회 → 왕복 3회). 상태 플래그로 왕복 자체를 1회로 봉인한다.
  if (btn && btn.dataset.diffBusy === "1") return;
  if (btn) { btn.dataset.diffBusy = "1"; btn.disabled = true; }
  try {
    const resp = await apiFetch(`/api/attachments/${encodeURIComponent(att.id)}/versions`);
    const versions = Array.isArray(resp?.versions) ? resp.versions : [];
    // REQ-20260814-attach-version-tree-ui: 계보가 둘 이상이면 이 체인의 버전이 하나뿐이어도
    // 비교할 짝이 있다(다른 계보의 head). 그 경우까지 원문 모달로 빠지면 사용자는 "AI 수정본과
    // 내 파일을 비교" 하는 경로를 잃는다.
    const lineages = Array.isArray(resp?.lineages) ? resp.lineages : [];
    if (versions.length < 2 && lineages.length < 2) {
      // 구버전이 삭제된 체인(attach-manage soft-delete)에는 비교할 짝이 없다. 눌렀는데 아무
      // 일도 일어나지 않는 대신 그 버전의 **원문**을 열고 사유를 알린다 — 이 경로도 정본
      // 모달(`openAttachmentSourceModal`)이며, 사용자가 하려던 "내용 확인" 은 충족된다.
      showToast("비교할 이전 버전이 남아 있지 않아 원문을 표시합니다.", false);
      openAttachmentSourceModal(att.id, { filename: attName });
      return;
    }
    // `to` = 이 칩이 가리키는 버전(= 이 답변이 만든 결과), `from` = 체인에 **실제로 남아 있는**
    // 직전 버전. `thisVer - 1` 을 그대로 preselect 하면 중간 버전이 삭제된 체인에서 없는 번호를
    // 지정해 `<select>` 가 조용히 첫 옵션(가장 오래된 버전)으로 떨어진다 — 엉뚱한 쌍이 "이
    // 수정" 으로 보이는 무음 오표시다.
    const nums = versions
      .map((v) => Number(v.version_number || 1))
      .filter((n) => Number.isFinite(n))
      .sort((a, b) => a - b);
    const newest = nums[nums.length - 1];
    const anchor = nums.includes(thisVer) ? thisVer : newest;
    const older = nums.filter((n) => n < anchor);
    // anchor 가 체인의 최소 번호면 앞이 없다 — 그때만 뒤(더 새 버전) 방향으로 비교한다.
    let preselect = older.length
      ? { from: older[older.length - 1], to: anchor }
      : { from: anchor, to: newest };
    // 같은 번호 두 개를 고르는 preselect 는 서버가 400 으로 막는 쌍이다(존재 oracle 방지 계약).
    // 그런 값을 넘기지 않고 모달 기본값(직전↔최신)에 맡긴다.
    if (preselect.from === preselect.to) preselect = undefined;
    openAttachmentDiffModal(att.id, versions, preselect, lineages);
  } catch (e) {
    // apiFetch 는 non-2xx 를 throw 한다. 실패를 조용히 삼키지 않는다 — 버튼을 눌렀는데 아무
    // 반응이 없으면 고장으로 읽힌다. 단 **403 은 apiFetch 가 이미 공통 토스트를 냈으므로**
    // 여기서 다시 띄우지 않는다(같은 사유가 두 번 뜨고 두 번째가 첫 번째의 표시 시간을
    // 리셋한다 — 저장소 공통 403 처리와 중복, codex P2).
    if (!(e && e.status === 403)) {
      showToast(`버전 이력을 불러오지 못했습니다: ${(e && e.message) || e}`, true);
    }
  } finally {
    if (btn) { btn.disabled = false; delete btn.dataset.diffBusy; }
  }
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

export { renderMessageContent, buildResultTable, parseMarkdownTablePreview, _buildMessageAttachChip, _msgAvatarEl, _mentionsUser, _assistantSpeakerFor };
