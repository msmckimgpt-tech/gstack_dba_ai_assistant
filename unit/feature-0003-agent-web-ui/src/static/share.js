// REQ-20260514-0001: 대화 공유 페이지 (anonymous accessible) 의 vanilla JS.
// /share/{token} 페이지에서 로드되어 /api/public/share/{token} 을 호출하고
// 메시지·SQL·결과셋을 read-only 렌더링한다. 로그인 + conversation.create 권한이
// 있는 viewer 에게는 "내 계정에서 fork" 버튼을 노출한다.

(function () {
  "use strict";

  // 메인 UI(app.js)와 동일한 SQL 가독성 줄바꿈 키워드 — formatSqlForDisplay 가 사용.
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

  const path = window.location.pathname.split("/").filter(Boolean);
  const token = path.length > 0 ? decodeURIComponent(path[path.length - 1]) : "";

  if (!token) {
    showError("공유 토큰이 URL 에 없습니다.");
    return;
  }

  setupCopyLink();

  fetchShare(token)
    .then((data) => render(data, token))
    .catch((err) => showError(err && err.message ? err.message : "공유 데이터를 불러오지 못했습니다."));

  // 수신자가 현재 공유 링크를 손쉽게 재전달할 수 있도록 "링크 복사" 버튼을 연결한다.
  function setupCopyLink() {
    const btn = document.getElementById("shareCopyLinkBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const url = window.location.href;
      const original = btn.textContent;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(url);
        } else {
          const ta = document.createElement("textarea");
          ta.value = url;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
        }
        btn.textContent = "복사됨 ✓";
        btn.classList.add("is-copied");
      } catch (e) {
        btn.textContent = "복사 실패";
      }
      window.setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove("is-copied");
      }, 1600);
    });
  }

  async function fetchShare(tok) {
    const res = await fetch(`/api/public/share/${encodeURIComponent(tok)}`, {
      credentials: "same-origin",
    });
    if (res.status === 404) throw new Error("공유 링크를 찾을 수 없습니다.");
    if (res.status === 410) {
      // TASK-20260619T012028-share-link-expiry: 서버 메시지로 만료/취소 구분.
      const body = await res.json().catch(() => ({}));
      throw new Error(body && body.error ? body.error : "이 공유 링크는 더 이상 사용할 수 없습니다.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body && body.error ? body.error : `서버 오류 (${res.status})`);
    }
    return res.json();
  }

  function render(data, tok) {
    const conv = (data && data.conversation) || {};
    const share = (data && data.share) || {};
    const viewer = (data && data.viewer) || {};
    const messages = Array.isArray(data && data.messages) ? data.messages : [];

    const topicEl = document.getElementById("shareTopic");
    if (topicEl) topicEl.textContent = conv.topic || "공유된 대화";

    const ownerEl = document.getElementById("shareOwner");
    if (ownerEl) ownerEl.textContent = conv.owner_username ? `소유자 ${conv.owner_username}` : "";

    const scopeEl = document.getElementById("shareScope");
    if (scopeEl) {
      if (share.scope_mode === "anchored" && share.anchor_message_id != null) {
        scopeEl.textContent = `범위: 여기까지 공유 (메시지 #${share.anchor_message_id})`;
      } else {
        scopeEl.textContent = "범위: 대화 전체";
      }
    }

    const productEl = document.getElementById("shareProduct");
    if (productEl) {
      const productLabel = conv.product_name || conv.product_key || "";
      productEl.textContent = productLabel ? `제품 ${productLabel}` : "";
    }

    // TASK-20260619T012028-share-link-expiry: 만료일 표시 (무기한이면 숨김).
    const expiryEl = document.getElementById("shareExpiry");
    if (expiryEl) {
      expiryEl.textContent = share.expires_at ? `만료 ${formatDateTime(share.expires_at)}` : "";
    }

    const viewCountEl = document.getElementById("shareViewCount");
    if (viewCountEl) viewCountEl.textContent = `조회 ${share.view_count || 0}회`;

    const messagesEl = document.getElementById("shareMessages");
    if (messagesEl) {
      messagesEl.innerHTML = "";
      if (messages.length === 0) {
        const empty = document.createElement("div");
        empty.className = "share-empty";
        empty.textContent = "공유된 메시지가 없습니다.";
        messagesEl.appendChild(empty);
      } else {
        messages.forEach((msg) => messagesEl.appendChild(renderMessage(msg)));
      }
    }

    const joinBtn = document.getElementById("shareJoinBtn");
    const forkBtn = document.getElementById("shareForkBtn");
    const loginLink = document.getElementById("shareLoginLink");
    // feature-0009: 참여(join) — 링크 Joinable + 로그인 + 아직 멤버 아님일 때.
    if (joinBtn && viewer.is_authenticated && viewer.can_join) {
      joinBtn.classList.remove("hidden");
      joinBtn.addEventListener("click", () => doJoin(tok, joinBtn));
    }
    if (forkBtn && viewer.is_authenticated && viewer.can_fork) {
      forkBtn.classList.remove("hidden");
      forkBtn.addEventListener("click", () => doFork(tok, forkBtn));
    }
    if (loginLink && !viewer.is_authenticated) {
      loginLink.classList.remove("hidden");
    }
  }

  function renderMessage(msg) {
    const row = document.createElement("article");
    const role = msg && msg.role === "user" ? "user" : "assistant";
    row.className = `share-message share-message-${role}`;

    const meta = document.createElement("div");
    meta.className = "share-message-meta";
    const badge = document.createElement("span");
    badge.className = `share-role-badge share-role-${role}`;
    badge.textContent = roleLabel(msg.role);
    const time = document.createElement("span");
    time.className = "share-message-time";
    time.textContent = formatDateTime(msg.created_at);
    meta.append(badge, time);
    row.appendChild(meta);

    const content = document.createElement("div");
    content.className = "share-message-content";
    renderMarkdownContent(content, msg.content || "");
    row.appendChild(content);

    if (msg.role === "assistant" && msg.meta) {
      const details = renderAssistantDetails(msg.meta);
      if (details) row.appendChild(details);
    }

    return row;
  }

  // 메시지 본문을 markdown → HTML 로 렌더한다. 메인 UI(app.js markdownToHtml)와
  // 동일 파이프라인(marked.parse → DOMPurify.sanitize)을 사용해 표·코드블록·리스트·
  // 제목·강조·링크가 그대로 가시화되도록 한다. 라이브러리 부재 시 평문으로 폴백.
  //
  // 본문 내 ```sql 코드블록은 메인 UI 와 동일하게 항상 펼쳐 표시한다.
  // (이전의 "쿼리 보기/닫기" 열고닫기 토글은 의도된 기능이 아니었음 — 실행된
  //  쿼리 사이의 전환은 renderAssistantDetails 의 SQL navigator 가 담당한다.)
  // TASK-0256: ```diff 코드 블록을 라인별 +/- span 으로 재구성 (app.js 와 동일 파이프라인).
  function diffLineClass(line) {
    // +++/--- 는 뒤에 공백+경로(git 파일 헤더)일 때만 meta — 내용이 "---" 인
    // 삭제 라인 회색 오분류 방지(REV-0256 MINOR).
    if (/^(diff |index |new file|deleted file|rename )/.test(line)) return "diff-meta";
    if (/^(\+\+\+|---)\s/.test(line)) return "diff-meta";
    if (line.startsWith("@@")) return "diff-hunk";
    if (line.startsWith("+")) return "diff-add";
    if (line.startsWith("-")) return "diff-del";
    return "diff-ctx";
  }

  // @@ -a,b +c,d @@ 헌크 헤더에서 old/new 시작 줄번호 추출. 없으면 null.
  function parseDiffHunkHeader(line) {
    const m = /^@@\s*-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s*@@/.exec(line);
    return m ? { oldStart: parseInt(m[1], 10), newStart: parseInt(m[2], 10) } : null;
  }

  // 맨 앞 마커(+/-/공백) 1글자 + 뒤따르는 공백 1개 제거 — 복사 시 순수 코드만 남김.
  function stripDiffMarker(line) {
    let s = line;
    if (s[0] === "+" || s[0] === "-" || s[0] === " ") s = s.slice(1);
    if (s[0] === " ") s = s.slice(1);
    return s;
  }

  // 각 줄을 {cls, mark, code, oldNo, newNo} 로 분해 — GitHub 식 양쪽 줄번호.
  function buildDiffRows(lines) {
    let oldNo = 1;
    let newNo = 1;
    return lines.map((line) => {
      const cls = diffLineClass(line);
      if (cls === "diff-hunk") {
        const h = parseDiffHunkHeader(line);
        if (h) { oldNo = h.oldStart; newNo = h.newStart; }
        return { cls, mark: "", code: line, oldNo: "", newNo: "" };
      }
      if (cls === "diff-meta") {
        return { cls, mark: "", code: line, oldNo: "", newNo: "" };
      }
      if (cls === "diff-add") {
        return { cls, mark: "+", code: stripDiffMarker(line), oldNo: "", newNo: newNo++ };
      }
      if (cls === "diff-del") {
        return { cls, mark: "-", code: stripDiffMarker(line), oldNo: oldNo++, newNo: "" };
      }
      return { cls, mark: " ", code: stripDiffMarker(line), oldNo: oldNo++, newNo: newNo++ };
    });
  }

  function enhanceDiffBlocks(html) {
    // 줄번호 + +/- 마커는 data-gutter → CSS ::before content 로만 렌더(의사요소라 복사 비포함).
    // 코드는 마커 제거 후 textContent 로만 넣어 복사 시 순수 코드만 잡힘(XSS 무첨가, DOMPurify 최종).
    if (typeof document === "undefined") return html;
    try {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      const blocks = tpl.content.querySelectorAll("pre > code.language-diff");
      if (!blocks.length) return html;
      const NB = "\u00a0"; // NBSP — gutter 정렬용
      blocks.forEach((codeEl) => {
        const raw = (codeEl.textContent || "").replace(/\n$/, "");
        const rows = buildDiffRows(raw.split("\n"));
        let maxNo = 1;
        rows.forEach((r) => {
          if (r.oldNo) maxNo = Math.max(maxNo, r.oldNo);
          if (r.newNo) maxNo = Math.max(maxNo, r.newNo);
        });
        const w = String(maxNo).length;
        const padNo = (v) => {
          const s = v === "" || v == null ? "" : String(v);
          return NB.repeat(Math.max(0, w - s.length)) + s;
        };
        codeEl.textContent = "";
        rows.forEach((r) => {
          const span = document.createElement("span");
          span.className = "diff-line " + r.cls;
          span.setAttribute(
            "data-gutter",
            padNo(r.oldNo) + NB + padNo(r.newNo) + NB + (r.mark || NB)
          );
          span.textContent = r.code.length ? r.code : " ";
          codeEl.appendChild(span);
        });
        const pre = codeEl.closest("pre");
        if (pre) {
          pre.classList.add("diff-block");
          pre.style.setProperty("--diff-gutter-ch", String(2 * w + 3));
        }
      });
      return tpl.innerHTML;
    } catch (_) {
      return html;
    }
  }

  function enhanceAttachmentEditBlocks(html) {
    // ★ TASK-0286: ```attachment-edit 코드 블록(전체 수정본 본문)을 "📎 수정된 첨부 파일" 안내로
    // 치환 — 공유 화면에서도 전체 본문 텍스트를 노출하지 않는다(app.js 와 동형 안전망).
    if (typeof document === "undefined") return html;
    if (!html || html.indexOf("language-attachment-edit") === -1) return html;
    try {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      const blocks = tpl.content.querySelectorAll("pre > code.language-attachment-edit");
      if (!blocks.length) return html;
      blocks.forEach((codeEl) => {
        const raw = codeEl.textContent || "";
        let fname = "";
        const firstLine = (raw.split("\n", 1)[0] || "").trim();
        try { fname = String((JSON.parse(firstLine) || {}).filename || ""); } catch (_) {}
        const note = document.createElement("div");
        note.className = "attachment-edit-note";
        note.textContent = "📎 수정된 첨부 파일" + (fname ? ` (${fname})` : "");
        const pre = codeEl.closest("pre");
        (pre || codeEl).replaceWith(note);
      });
      return tpl.innerHTML;
    } catch (_) {
      return html;
    }
  }

  function renderMarkdownContent(target, text) {
    const source = String(text || "").trim();
    if (!source) {
      target.textContent = "";
      return;
    }
    if (window.marked && window.DOMPurify) {
      // feature-0013 후속: 공유 대화도 메인 UI 와 동일하게 ```mermaid 를 다이어그램으로 렌더.
      // mermaid-render.js(공용) 의 enhanceMermaidBlocks 로 sanitize 이전 텍스트 치환 → DOMPurify →
      // innerHTML 이후 라이브 DOM 에서 strict-mode SVG 렌더. mermaid-render.js 미로드 시 안전 폴백(원문 유지).
      const enhanceMmd =
        typeof window.enhanceMermaidBlocks === "function" ? window.enhanceMermaidBlocks : (h) => h;
      target.innerHTML = window.DOMPurify.sanitize(
        enhanceMmd(enhanceAttachmentEditBlocks(enhanceDiffBlocks(window.marked.parse(source))))
      );
      markExternalLinks(target);
      if (typeof window.renderMermaidDiagrams === "function") window.renderMermaidDiagrams(target);
    } else {
      // 폴백: 라이브러리 로드 실패 시 줄바꿈 보존 평문 (share.css .share-content-plain).
      target.classList.add("share-content-plain");
      target.textContent = source;
    }
  }

  // 본문 내 외부 링크는 새 탭 + noopener 로 — 익명 공유 페이지의 안전한 이동.
  function markExternalLinks(target) {
    target.querySelectorAll("a[href]").forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer nofollow");
    });
  }

  function renderAssistantDetails(meta) {
    if (!meta || typeof meta !== "object") return null;
    const container = document.createElement("div");
    container.className = "share-message-details";

    // 1순위: meta.steps 의 execute_sql 단계 — 메인 UI 와 동일하게 "실행된 쿼리"
    // 단위로 묶어 표시한다. 한 답변에 여러 쿼리가 실행됐다면 결과셋에 따라 쿼리를
    // 전환하는 navigator(◀ ▶)로 보여준다 (열고닫기 토글이 아님 — 사용자 의도).
    const steps = Array.isArray(meta.steps) ? meta.steps : [];
    const sqlSteps = steps.filter(
      (s) => s && String(s.tool || "") === "execute_sql" && s.sql,
    );
    if (sqlSteps.length > 0) {
      if (sqlSteps.length === 1) {
        container.appendChild(buildSqlStepPanel(sqlSteps[0]));
      } else {
        container.appendChild(buildSqlNavigator(sqlSteps));
      }
      return container;
    }

    // 폴백: steps 가 없는 구형 메시지 — 기존 final_sql / result_rows 단일 필드.
    let hasAny = false;

    const finalSql = meta.final_sql || meta.sql || "";
    if (finalSql) {
      const pre = document.createElement("pre");
      pre.className = "share-sql";
      pre.textContent = String(finalSql);
      container.appendChild(pre);
      hasAny = true;
    }

    const rows = Array.isArray(meta.result_rows) ? meta.result_rows : null;
    if (rows && rows.length > 0) {
      const table = renderResultTable(rows);
      if (table) {
        container.appendChild(table);
        const dlBtn = document.createElement("button");
        dlBtn.type = "button";
        dlBtn.className = "share-csv-download-btn";
        dlBtn.textContent = "CSV 다운로드";
        dlBtn.addEventListener("click", () => downloadRowsAsCsv(rows, "result.csv"));
        container.appendChild(dlBtn);
        hasAny = true;
      }
    }

    return hasAny ? container : null;
  }

  // 단일 execute_sql 단계를 SQL 블록 + (있으면) 결과 미리보기 표로 렌더.
  // 메인 UI(app.js buildSqlStepPanel)의 share 전용 read-only 이식판이다.
  function buildSqlStepPanel(step) {
    const panel = document.createElement("div");
    panel.className = "share-sql-group";

    // 근거 — 메인 UI 와 일관되게 쿼리 위에 수행 이유를 명시(있을 때만).
    const reason = String((step && step.reason) || "").trim();
    if (reason) {
      const reasonEl = document.createElement("div");
      reasonEl.className = "share-step-reason";
      const reasonLabel = document.createElement("span");
      reasonLabel.className = "share-step-reason-label";
      reasonLabel.textContent = "근거";
      const reasonText = document.createElement("span");
      reasonText.className = "share-step-reason-text";
      reasonText.textContent = reason;
      reasonEl.append(reasonLabel, reasonText);
      panel.appendChild(reasonEl);
    }

    // SQL 문 — 항상 펼쳐 표시.
    if (step.sql) {
      const pre = document.createElement("pre");
      pre.className = "share-sql";
      pre.textContent = formatSqlForDisplay(step.sql);
      panel.appendChild(pre);
    }

    // 결과 미리보기 표 — result_summary.preview_table 가 있을 때만.
    const rs = step.result_summary;
    if (rs && typeof rs === "object") {
      const pt = rs.preview_table;
      if (pt && Array.isArray(pt.columns) && pt.columns.length) {
        const table = buildPreviewTable(pt);
        if (table) panel.appendChild(table);
      }
    }

    return panel;
  }

  // 여러 execute_sql 단계를 ◀ ▶ 로 전환하는 navigator. 결과셋(쿼리)별 패널을
  // 모두 만들어 두고 활성 인덱스만 노출한다 (메인 UI buildSqlNavigator 이식).
  function buildSqlNavigator(sqlSteps) {
    const root = document.createElement("div");
    root.className = "share-sql-navigator";
    root.setAttribute("tabindex", "0");
    root.setAttribute("role", "group");
    root.setAttribute("aria-label", "SQL 쿼리 결과 탐색");

    const header = document.createElement("div");
    header.className = "share-sql-nav-header";

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "share-sql-nav-btn";
    prevBtn.innerHTML = "&#9664;";
    prevBtn.setAttribute("aria-label", "이전 쿼리");
    prevBtn.title = "이전 쿼리 (←)";

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "share-sql-nav-btn";
    nextBtn.innerHTML = "&#9654;";
    nextBtn.setAttribute("aria-label", "다음 쿼리");
    nextBtn.title = "다음 쿼리 (→)";

    const indicator = document.createElement("span");
    indicator.className = "share-sql-nav-indicator";
    indicator.setAttribute("aria-live", "polite");

    const context = document.createElement("span");
    context.className = "share-sql-nav-context";

    header.append(prevBtn, indicator, nextBtn, context);
    root.appendChild(header);

    const panels = document.createElement("div");
    panels.className = "share-sql-nav-panels";
    root.appendChild(panels);

    const panelEls = sqlSteps.map((step) => {
      const p = buildSqlStepPanel(step);
      p.className += " share-sql-nav-panel";
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

  // result_summary.preview_table({columns, rows[][], truncated}) → read-only 표.
  // 메인 UI buildResultTable 과 동일한 컬럼/행 모델(배열의 배열)을 받는다.
  function buildPreviewTable(previewTable) {
    const columns = Array.isArray(previewTable.columns) ? previewTable.columns : [];
    const rows = Array.isArray(previewTable.rows) ? previewTable.rows : [];
    const truncated = Boolean(previewTable.truncated);
    if (!columns.length) return null;

    const wrap = document.createElement("div");
    wrap.className = "share-result-table-wrap";

    const table = document.createElement("table");
    table.className = "share-result-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = String(col);
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((_, ci) => {
        const td = document.createElement("td");
        const val = Array.isArray(row) ? row[ci] : undefined;
        td.textContent = val == null ? "" : String(val);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);

    const meta = document.createElement("div");
    meta.className = "share-result-table-meta";
    const shown = rows.length;
    meta.textContent = truncated
      ? `${shown}행 표시 중 (더 있음) · ${columns.length}열`
      : `${shown}행 · ${columns.length}열`;
    wrap.appendChild(meta);

    return wrap;
  }

  // 한 줄 SQL 을 주요 키워드 앞에서 줄바꿈해 가독성을 높인다(메인 UI 이식).
  // 문자열/식별자 리터럴 내부는 보존한다.
  function formatSqlForDisplay(raw) {
    const src = String(raw || "").trim();
    if (!src) return "";
    if (/\n/.test(src)) return src;

    const literals = [];
    const literalRe = /('([^'\\]|\\.|'')*'|"([^"\\]|\\.|"")*"|`[^`]*`)/g;
    const masked = src.replace(literalRe, (m) => {
      literals.push(m);
      return `${literals.length - 1}`;
    });

    const keywordAlt = SQL_FORMAT_KEYWORDS.map((k) => k.replace(/ /g, "\\s+")).join("|");
    const pattern = new RegExp(`\\s+(?=\\b(?:${keywordAlt})\\b)`, "gi");
    let formatted = masked.replace(pattern, "\n");

    formatted = formatted.replace(/(\d+)/g, (_, i) => literals[Number(i)]);
    return formatted;
  }

  // 첫 테이블 참조(schema.table)를 추출해 navigator context 라벨에 쓴다.
  function extractFirstTableRef(sql) {
    const match = String(sql || "").match(
      /(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?/i,
    );
    return match ? `${match[1]}.${match[2]}` : "";
  }

  function renderResultTable(rows) {
    if (!rows.length) return null;
    const first = rows[0];
    if (!first || typeof first !== "object") return null;
    const headers = Object.keys(first);
    if (headers.length === 0) return null;

    const table = document.createElement("table");
    table.className = "share-result-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headers.forEach((h) => {
      const th = document.createElement("th");
      th.textContent = h;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      headers.forEach((h) => {
        const td = document.createElement("td");
        const val = row[h];
        td.textContent = val == null ? "" : String(val);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    return table;
  }

  function downloadRowsAsCsv(rows, filename) {
    if (!rows || !rows.length) return;
    const headers = Object.keys(rows[0] || {});
    const escape = (v) => {
      const s = v == null ? "" : String(v);
      return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [headers.map(escape).join(",")];
    rows.forEach((row) => lines.push(headers.map((h) => escape(row[h])).join(",")));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "result.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function doJoin(tok, btn) {
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.textContent = "참여 중...";
    try {
      const res = await fetch(`/api/share/${encodeURIComponent(tok)}/join`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const errMsg = body && body.error ? body.error : `참여 실패 (${res.status})`;
        window.alert(errMsg);
        btn.disabled = false;
        btn.textContent = originalLabel;
        return;
      }
      const body = await res.json();
      const cid = body && body.conversation_id ? body.conversation_id : "";
      window.location.href = cid ? `/?conversation=${encodeURIComponent(cid)}` : "/";
    } catch (e) {
      window.alert(`참여 실패: ${e && e.message ? e.message : e}`);
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  }

  async function doFork(tok, btn) {
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.textContent = "fork 중...";
    try {
      const res = await fetch(`/api/public/share/${encodeURIComponent(tok)}/fork`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const errMsg = body && body.error ? body.error : `fork 실패 (${res.status})`;
        window.alert(errMsg);
        btn.disabled = false;
        btn.textContent = originalLabel;
        return;
      }
      const body = await res.json();
      window.alert(`내 계정에 fork 됐습니다. (${body.copied}개 메시지 복제) 메인 페이지로 이동합니다.`);
      window.location.href = "/";
    } catch (e) {
      window.alert(`fork 실패: ${e && e.message ? e.message : e}`);
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  }

  function roleLabel(role) {
    if (role === "user") return "사용자";
    if (role === "assistant") return "어시스턴트";
    return role || "메시지";
  }

  function formatDateTime(ts) {
    if (!ts) return "";
    try {
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return String(ts);
      return d.toLocaleString("ko-KR");
    } catch (e) {
      return String(ts);
    }
  }

  function showError(msg) {
    const main = document.getElementById("shareMessages");
    if (main) {
      main.innerHTML = "";
      const div = document.createElement("div");
      div.className = "share-error";
      div.textContent = msg;
      main.appendChild(div);
    }
  }
})();
