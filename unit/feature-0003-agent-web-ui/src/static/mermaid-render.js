/* mermaid-render.js — feature-0013 mermaid 렌더 헬퍼 (공용)
 *
 * 메인 UI(index.html/app.js)와 공유 대화 뷰(share.html/share.js)가 **동일** 렌더 경로를
 * 쓰도록 app.js 에서 추출한 단일 소스. 특히 `securityLevel:'strict'` 초기화를 한 곳에만 두어
 * 두 뷰의 mermaid XSS 표면(라벨 escape / click·script 디렉티브 비활성)이 갈라지지 않게 한다
 * (§18.8 security 패널이 검증한 strict-mode SVG sanitize 불변식 — 공유 뷰는 anonymous 노출면).
 *
 * 로드 순서: vendor/mermaid.min.js (window.mermaid) → 본 파일 → app.js / share.js.
 * top-level function 선언이라 전역(window) 으로 노출된다.
 */

function enhanceMermaidBlocks(html) {
  // marked 가 만든 ```mermaid 코드블록(<pre><code class="language-mermaid">)을
  // <div class="mermaid-block mermaid-pending"> (다이어그램 source 텍스트만) 으로 치환한다.
  // 실제 SVG 렌더는 DOMPurify sanitize 이후 renderMermaidDiagrams() 가 라이브 DOM 에서
  // mermaid.render(securityLevel:'strict') 로 수행 — SVG 를 sanitize 표면에 태우지 않으므로
  // DOMPurify 전역 ALLOWED_TAGS 완화가 불필요하다(XSS 표면 최소화, ANCHOR §2 Alt-C 불채택).
  if (typeof document === "undefined") return html;
  if (!html || html.indexOf("language-mermaid") === -1) return html;
  try {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    const blocks = tpl.content.querySelectorAll("pre > code.language-mermaid");
    if (!blocks.length) return html;
    blocks.forEach((codeEl) => {
      const src = (codeEl.textContent || "").replace(/\n$/, "");
      const div = document.createElement("div");
      div.className = "mermaid-block mermaid-pending";
      div.textContent = src; // source 만 — SVG 아님. render 단계가 textContent 를 읽는다.
      const pre = codeEl.closest("pre");
      (pre || codeEl).replaceWith(div);
    });
    return tpl.innerHTML;
  } catch (_) {
    return html;
  }
}

let _mermaidInited = false;
function ensureMermaidInit() {
  // mermaid 1회 초기화. startOnLoad:false 라 자동 스캔 없음 — 명시적 render 만 수행.
  // securityLevel:'strict' 가 라벨 HTML escape + click/script 디렉티브를 비활성화해
  // 사용자 DB 유래 라벨로 인한 XSS 를 mermaid 내부에서 차단한다.
  if (_mermaidInited) return true;
  if (!window.mermaid) return false;
  try {
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "default",
      flowchart: { useMaxWidth: true, htmlLabels: false },
      er: { useMaxWidth: true },
      sequence: { useMaxWidth: true },
    });
    _mermaidInited = true;
  } catch (_) {}
  return _mermaidInited;
}

let _mermaidSeq = 0;
function renderMermaidDiagrams(target) {
  // innerHTML(=DOMPurify 통과본) 설정 "이후" 호출.
  // 라이브 DOM 의 .mermaid-pending(다이어그램 source) 을 SVG 로 렌더한다.
  if (!target || typeof target.querySelectorAll !== "function") return;
  const nodes = Array.from(target.querySelectorAll(".mermaid-pending"));
  if (!nodes.length) return;
  if (!ensureMermaidInit()) {
    nodes.forEach((node) => mermaidFallback(node, node.textContent || ""));
    return;
  }
  nodes.forEach((node) => {
    const src = node.textContent || "";
    const id = "mmd-" + (++_mermaidSeq);
    Promise.resolve()
      .then(() => window.mermaid.render(id, src))
      .then((out) => {
        node.classList.remove("mermaid-pending");
        node.classList.add("mermaid-rendered");
        node.innerHTML = (out && out.svg) || ""; // strict-mode 에서 mermaid 가 자체 sanitize 한 SVG
      })
      .catch(() => mermaidFallback(node, src));
  });
}

function mermaidFallback(node, src) {
  // 렌더 실패/미로딩 시 원본 다이어그램 소스를 코드블록으로 노출(비차단 graceful fallback).
  try {
    node.className = "mermaid-error";
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = src;
    pre.appendChild(code);
    node.innerHTML = "";
    node.appendChild(pre);
  } catch (_) {}
}
