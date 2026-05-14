// REQ-20260514-0001: 대화 공유 페이지 (anonymous accessible) 의 vanilla JS.
// /share/{token} 페이지에서 로드되어 /api/public/share/{token} 을 호출하고
// 메시지·SQL·결과셋을 read-only 렌더링한다. 로그인 + conversation.create 권한이
// 있는 viewer 에게는 "내 계정에서 fork" 버튼을 노출한다.

(function () {
  "use strict";

  const path = window.location.pathname.split("/").filter(Boolean);
  const token = path.length > 0 ? decodeURIComponent(path[path.length - 1]) : "";

  if (!token) {
    showError("공유 토큰이 URL 에 없습니다.");
    return;
  }

  fetchShare(token)
    .then((data) => render(data, token))
    .catch((err) => showError(err && err.message ? err.message : "공유 데이터를 불러오지 못했습니다."));

  async function fetchShare(tok) {
    const res = await fetch(`/api/public/share/${encodeURIComponent(tok)}`, {
      credentials: "same-origin",
    });
    if (res.status === 404) throw new Error("공유 링크를 찾을 수 없습니다.");
    if (res.status === 410) throw new Error("이 공유 링크는 취소되었습니다.");
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

    const forkBtn = document.getElementById("shareForkBtn");
    const loginLink = document.getElementById("shareLoginLink");
    if (forkBtn && viewer.is_authenticated && viewer.can_fork) {
      forkBtn.classList.remove("hidden");
      forkBtn.addEventListener("click", () => doFork(tok, forkBtn));
    } else if (loginLink && !viewer.is_authenticated) {
      loginLink.classList.remove("hidden");
    }
  }

  function renderMessage(msg) {
    const row = document.createElement("article");
    const roleClass = msg && msg.role === "user" ? "share-message-user" : "share-message-assistant";
    row.className = `share-message ${roleClass}`;

    const meta = document.createElement("div");
    meta.className = "share-message-meta";
    meta.textContent = `${roleLabel(msg.role)} · ${formatDateTime(msg.created_at)}`;
    row.appendChild(meta);

    const content = document.createElement("div");
    content.className = "share-message-content";
    content.textContent = msg.content || "";
    row.appendChild(content);

    if (msg.role === "assistant" && msg.meta) {
      const details = renderAssistantDetails(msg.meta);
      if (details) row.appendChild(details);
    }

    return row;
  }

  function renderAssistantDetails(meta) {
    if (!meta || typeof meta !== "object") return null;
    const container = document.createElement("div");
    container.className = "share-message-details";
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
        hasAny = true;
      }
    }

    return hasAny ? container : null;
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
