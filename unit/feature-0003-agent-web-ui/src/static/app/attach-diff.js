// attach-diff — 첨부 **본문 보기** 모달 2종: 버전 비교(REQ-20260806-attach-version-diff)와
// 원문 보기(REQ-20260807T-attach-source-view).
//
// 첨부 사이드 패널의 "버전 N개 ▾" 이력 박스는 각 버전의 존재와 다운로드만 보여줬다.
// 이 모듈은 그 체인에서 **임의의 두 버전**(v1↔v3 처럼 여러 단계 떨어진 쌍 포함)을 골라
// 본문 차이를 보는 전용 모달을 담당한다. 비교 계산은 서버
// (`GET /api/attachments/{id}/diff`)가 하고, 여기서는 선택·렌더·토글만 한다.
//
// **원문 보기가 같은 모듈에 있는 이유**(2026-08-07): 두 화면은 같은 렌더 primitive
// (`_renderSource`·`_appendColgroup`·`_paintCell`·스크롤 앵커)를 쓴다. 별 모듈로 나누면 그
// primitive 를 복제하거나 순환 import 를 만들게 되고, 이 저장소는 "복제가 곧 결함 기전"
// (modal-dismiss.js)을 이미 한 번 치렀다. 서버도 `_build_source_view` 가 diff `rows` 와
// **호환 shape** 을 내보내 렌더러 분기가 0 이다.
//
// 설계 메모
//  - **저장된 diff 를 쓰지 않는다**: `MetaJson.version_diff` 는 업로드 시점의 직전↔신규
//    1쌍뿐이라 다단계 비교에 답이 없다. 서버가 매번 두 원본을 읽어 대칭적으로 계산한다.
//  - **2열/단일열은 같은 응답의 두 표현**: 서버가 한 번의 opcode 패스로 `rows`(좌우 정렬)와
//    `unified_diff`(문자열)를 함께 만들므로 토글이 서로 다른 비교 결과를 보일 수 없다.
//  - **절단은 전부 표면화**: 원본 cap 초과(from/to)·행 상한 초과를 각각 배너로 알린다.
//    조용히 잘린 diff 를 "전체" 로 오인하면 사용자가 존재하는 변경을 놓친다.
//  - 배경 dismiss 는 저장소 단일 primitive `bindBackdropDismiss` 를 쓴다(복제 금지 —
//    modal-dismiss.js 주석의 결함 기전 참조).
//  - **구문 하이라이트도 단일 primitive**(`code-highlight.js`): 파일명 확장자로 언어를 한 번
//    판정하고 각 code 셀을 토큰 span 으로 칠한다. 미지원 확장자는 판정이 `null` → 평문 경로
//    그대로(무색). 모르는 파일에 색을 칠하면 없는 구조를 있는 것처럼 보이게 만든다.
//  - **줄 안 변경은 서버 세그먼트를 덧그린다**(`_markSegments`): 줄 배경은 "이 줄이 바뀌었다"
//    까지만 말하므로 긴 줄에서는 사용자가 두 줄을 눈으로 대조해야 했다. 구간 계산은 서버가
//    한 번만 하고(2열·단일열 동일), 프론트는 이미 칠해진 텍스트 노드를 문자 오프셋으로 쪼개
//    감싼다 — 구문 색과 변경 마크가 서로를 지우지 않는 독립 레이어가 된다.
import { apiFetch, bindBackdropDismiss, escapeHtml, showToast, detectCodeLanguage, paintCodeInto, codeLanguageLabel, markdownToHtml } from "../app.js?v=dev";

const VIEW_MODE_KEY = "attachDiffViewMode";   // "split" | "unified"
const CONTEXT_KEY = "attachDiffContextFull";  // "1" 이면 전체 맥락
const HIGHLIGHT_KEY = "attachDiffHighlight";  // "0" 이면 구문 하이라이트 끔 (기본 켬)
const SPLIT_RATIO_KEY = "attachDiffSplitRatio";  // 2열 중앙선 위치 (좌측 비율 0.15~0.85)
const SPLIT_RATIO_DEFAULT = 0.5;
const SPLIT_RATIO_MIN = 0.15;
const SPLIT_RATIO_MAX = 0.85;

function _readSplitRatio() {
  try {
    const v = parseFloat(localStorage.getItem(SPLIT_RATIO_KEY) || "");
    if (!Number.isFinite(v)) return SPLIT_RATIO_DEFAULT;
    return Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, v));
  } catch (e) { return SPLIT_RATIO_DEFAULT; }
}
function _writeSplitRatio(r) {
  try { localStorage.setItem(SPLIT_RATIO_KEY, String(r)); } catch (e) { /* private mode */ }
}

// 줄번호 열 폭은 **자릿수에서 산출**한다 — 고정 48px 는 3자리 파일에서 여백만 넓고(사용자
// 지적 2026-08-07) 5자리 파일에서는 잘린다. 등폭 폰트라 `ch`(문자 '0' 폭)로 정확히 잡힌다.
function _linenoCh(rows) {
  let max = 1;
  for (const r of rows || []) {
    if (r.left_no) max = Math.max(max, r.left_no);
    if (r.right_no) max = Math.max(max, r.right_no);
    if (r.left_to) max = Math.max(max, r.left_to);
    if (r.right_to) max = Math.max(max, r.right_to);
  }
  return String(max).length;
}

function _readViewMode() {
  try {
    const v = localStorage.getItem(VIEW_MODE_KEY);
    return v === "unified" ? "unified" : "split";
  } catch (e) { return "split"; }
}
function _writeViewMode(mode) {
  try { localStorage.setItem(VIEW_MODE_KEY, mode === "unified" ? "unified" : "split"); } catch (e) { /* private mode */ }
}
function _readContextFull() {
  try { return localStorage.getItem(CONTEXT_KEY) === "1"; } catch (e) { return false; }
}
function _writeContextFull(on) {
  try { localStorage.setItem(CONTEXT_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
}
// 하이라이트는 **기본 켬**이며 끈 상태만 저장한다(부재 = 켬) — 새 기능이 기본 off 면 사용자
// 대다수에게 없는 기능과 같다. 끄기 수단을 두는 이유는 확장자 판정이 틀릴 수 있고(예: `.config`
// 가 XML 이 아닌 경우) 그때 색이 오히려 방해가 되기 때문이다.
function _readHighlightOn() {
  try { return localStorage.getItem(HIGHLIGHT_KEY) !== "0"; } catch (e) { return true; }
}
function _writeHighlightOn(on) {
  try { localStorage.setItem(HIGHLIGHT_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
}

// ── 마크다운 렌더 (사용자 요청 2026-08-12) ───────────────────────────────────
// `.md` 첨부를 **문서로** 보여 준다. 선행 cycle 은 같은 요청을 구문 색으로 처리했는데,
// 사용자가 원한 것은 "실제 마크다운 구성으로 출력" — 제목이 제목으로, 표가 표로, 목록이
// 목록으로 보이는 것이었다. 원문(줄번호+평문)은 토글로 남긴다.
//
// **렌더 파이프라인은 새로 만들지 않는다**: 답변 말풍선과 같은 `markdownToHtml`
// (`marked.parse` → enhance(diff/sql/attachment-edit/mermaid) → `DOMPurify.sanitize`)을 그대로
// 쓴다. 같은 `.md` 가 대화 본문에 인용될 때와 첨부로 열릴 때 다르게 보이면 그 자체가 결함이고,
// 파이프라인을 두 벌 두면 한쪽만 갱신되는 것이 이 모듈이 반복해 기록한 결함 기전이다.
const MD_RENDER_KEY = "attachSourceMarkdown";   // "0" 이면 원문 보기 (기본: 렌더)
function _readMdRenderOn() {
  try { return localStorage.getItem(MD_RENDER_KEY) !== "0"; } catch (e) { return true; }
}
function _writeMdRenderOn(on) {
  try { localStorage.setItem(MD_RENDER_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
}

/** 이 첨부가 마크다운으로 렌더할 대상인가 — 판정은 `code-highlight.js` 레지스트리 단일 정본. */
function _isMarkdownFile(filename) {
  return detectCodeLanguage(filename) === "md";
}

/** 원문 행 배열 → 원본 텍스트. `gap` 행은 본문이 아니므로 제외한다. */
function _sourceText(data) {
  const rows = Array.isArray(data && data.rows) ? data.rows : [];
  const out = [];
  for (const r of rows) {
    if (!r || r.type === "gap") continue;
    out.push(r.right ?? r.left ?? "");
  }
  return out.join("\n");
}

// 첨부 본문은 **사용자가 올린 임의 바이트**다. 답변 말풍선(LLM 산출물)과 같은 sanitize 를
// 거치지만, 그것만으로는 닫히지 않는 축이 하나 있다: **원격 리소스 fetch**.
// `![](https://attacker/track.gif)` 한 줄이면 그 문서를 여는 모든 멤버의 IP·열람 시각이
// 업로더가 고른 서버로 새어 나간다(스크립트 실행이 아니라 로드 자체가 신호라 DOMPurify 는
// 막지 않는다). 그룹 대화에서 첨부는 멤버 전원이 열람하므로 이 경로는 실재한다.
// 응답 헤더의 CSP 는 현재 **report-only** 라 차단이 아니라 보고만 한다 — 즉 브라우저가 막아
// 주리라 기대할 수 없다. 그래서 sanitize 이후 DOM 에서 **교차 출처 리소스를 직접 중립화**하고,
// 사용자에게는 URL 을 텍스트로 보여 준다(숨기지 않는다 — 무엇이 있었는지는 알아야 한다).
// **첨부 전용 sanitize 프로필** — 말풍선(LLM 산출물)용 기본 프로필보다 좁다. 기본 프로필은
// `style`·`form`·`input`·`action` 을 통과시키는데, 임의 업로드 본문에서는 그것들이 각각
// ① `<div style="background:url(https://evil/x)">` CSS 비콘 ② 인증된 앱 위에 뜨는 외부 form
// (`position:fixed` 오버레이 + `action=https://evil`) 피싱이 된다(codex 적대 리뷰 [P1]).
// 미디어 태그도 전부 막고, **`img` 만 남겨** 아래에서 URL 을 보여 주는 칩으로 바꾼다
// (무엇이 있었는지는 사용자가 알아야 하므로 통째로 지우지 않는다).
// `svg`/`math` 는 네임스페이스 혼동 + `<image href>` 우회 경로라 문서 렌더에서 제외한다
// (```mermaid 다이어그램은 sanitize 이후 `mermaid.render` 가 만들므로 영향 없다).
// 렌더러(marked + enhance*)가 스스로 붙이는 클래스만 통과시키는 allowlist. 사용자 HTML 이
// 들고 온 클래스는 앱 CSS 를 빌려 UI 를 위장할 수 있으므로 여기 없으면 제거한다(6R [P1]).
const _RENDERER_CLASS_RE = /^(?:language-[\w+#.-]+|sql-block|sql-tok-[\w-]+|diff-(?:block|line|add|del|hunk|meta|ctx|lineno)|mermaid-(?:block|pending|rendered|error)|attachment-edit-note)$/;
const _ATTACH_SANITIZE = {
  FORBID_TAGS: [
    "style", "form", "input", "button", "textarea", "select",
    "iframe", "object", "embed", "link", "meta", "base",
    "svg", "math", "video", "audio", "source", "track", "picture", "map", "area",
  ],
  FORBID_ATTR: [
    "style", "srcset", "poster", "ping", "background",
    "formaction", "action", "usemap", "longdesc", "lowsrc", "dynsrc",
    // `id`/`name` 은 앱의 기존 요소와 충돌하거나 DOM clobbering 표면이 된다 — 문서에 필요 없다.
    "id", "name",
  ],
};
// sanitize 이후에도 URL 을 실어 나를 수 있는 요소 — 위 프로필이 대부분을 막지만, 방어를 한 곳에만
// 걸지 않는다(프로필이 완화되면 여기서 잡힌다).
const _MEDIA_SEL = "img,video,audio,source,track,embed,object,iframe,image";

function _resolveUrl(raw) {
  const s = String(raw || "").trim();
  if (!s) return null;
  try { return new URL(s, document.baseURI); } catch (e) { return null; }
}
/** `data:image/…` — 인라인이라 네트워크 요청이 없다. */
function _isInlineImage(raw) { return /^data:image\//i.test(String(raw || "").trim()); }
/**
 * 같은 출처의 http(s) 인가. **프로토콜 상대 URL(`//host/x`)도 정확히 판정**한다 —
 * 초판은 `^https?:` 문자열 검사라 `//evil/x` 가 "상대 경로" 로 통과했다(codex [P1]).
 * 판정은 문자열이 아니라 `new URL(raw, baseURI)` 의 실 origin 으로 한다.
 */
function _isSameOrigin(raw) {
  const u = _resolveUrl(raw);
  if (!u) return false;
  if (u.protocol !== "http:" && u.protocol !== "https:") return false;
  return u.origin === window.location.origin;
}
/**
 * 이 미디어 URL 을 **실제로 로드해도 되는가**. 답은 `data:image/` 뿐이다.
 *
 * 초판은 "같은 출처면 안전" 으로 봤는데 **틀렸다**(codex 적대 리뷰 4R [P1]). 이 앱에는 GET 만으로
 * 상태가 움직이는 인증 엔드포인트가 있고(예: `routers/oauth_as.py` 의 authorize),
 * `![x](/api/ai/oauth/authorize?…redirect_uri=https://attacker/…)` 한 줄이면 **열람자의 세션으로**
 * 인가 코드가 발급돼 공격자에게 리다이렉트된다 — 즉 같은 출처가 오히려 위험한 방향이다
 * (교차 출처 비콘은 정보 유출, 같은 출처는 **권한 행사**).
 *
 * 잃는 것은 거의 없다: 첨부 `.md` 가 참조하는 이미지는 우리 서버에 호스팅되지 않아
 * 상대 경로든 절대 경로든 어차피 404 다. `data:` 인라인 이미지는 네트워크 요청이 없어 남긴다.
 * 나머지는 URL 을 텍스트 칩으로 보여 주므로 **무엇이 있었는지는 사라지지 않는다**.
 */
function _mediaLoadAllowed(url) {
  return _isInlineImage(url);
}
// 링크 판정에서만 쓰인다(요청이 아니라 **클릭 이동**의 외부 여부) — 미디어에는 쓰지 않는다.
function _isSameOriginOrInline(url) {
  return _isInlineImage(url) || _isSameOrigin(url);
}

/**
 * 렌더된 DOM 에 첨부 전용 하드닝을 적용한다 (sanitize **이후**).
 *  - 교차 출처 미디어 → 로드하지 않고 URL 을 텍스트 칩으로 대체(비콘 차단)
 *  - 외부 링크 → `target=_blank` + `rel="noopener noreferrer nofollow"`
 * @returns {{blockedMedia: number, deadLinks: number}} 중립화 건수 (호출자가 배너로 표면화)
 */
function _hardenRenderedMarkdown(root) {
  let blockedMedia = 0;
  // URL 을 실어 나르는 속성은 `src` 하나가 아니다 — `srcset`·`poster`·`href`/`xlink:href`·`data`
  // 가 모두 요청을 만든다(codex 적대 리뷰 [P1]: `<img src="/safe" srcset="https://evil 2x">`).
  // 프로필이 대부분을 이미 막지만, **하나라도 남으면 비콘**이므로 여기서 전부 확인한다.
  const URL_ATTRS = ["src", "srcset", "poster", "data", "href", "xlink:href"];
  const anyRemote = (el) => URL_ATTRS.some((a) => {
    const v = el.getAttribute(a);
    if (!v) return false;
    // ⚠️ 콤마 분할은 **`srcset` 에만** 적용한다(`url 1x, url 2x` 목록). 다른 속성에 적용하면
    // `data:image/png;base64,AAAA` 의 콤마에서 쪼개져 인라인 이미지가 통째로 차단된다
    // (하네스가 적발 — 과잉 차단도 결함이다).
    const candidates = a === "srcset"
      ? String(v).split(",").map((part) => part.trim().split(/\s+/)[0])
      : [String(v).trim()];
    return candidates.some((u) => u && !_mediaLoadAllowed(u));
  });
  root.querySelectorAll(_MEDIA_SEL).forEach((el) => {
    const src = el.getAttribute("src") || el.getAttribute("data")
      || el.getAttribute("srcset") || el.getAttribute("href") || "";
    const tag = el.tagName.toLowerCase();
    // iframe·object·embed 는 출처와 무관하게 문서 안에 둘 이유가 없다(첨부는 문서다).
    if (tag === "iframe" || tag === "object" || tag === "embed" || anyRemote(el)) {
      const chip = document.createElement("span");
      chip.className = "attach-source-md-blocked";
      const alt = el.getAttribute("alt") || "";
      // 텍스트로만 넣는다 — 여기서 문자열을 조립하면 하드닝이 새 XSS 경로가 된다.
      chip.textContent = `🚫 외부 ${tag} 차단${alt ? ` · ${alt}` : ""}${src ? ` · ${src}` : ""}`;
      chip.title = "외부 서버로 열람 사실이 새지 않도록 로드하지 않았습니다. 필요하면 원문 보기에서 URL 을 확인하세요.";
      el.replaceWith(chip);
      blockedMedia += 1;
    }
  });
  // 링크는 미디어와 **위험 방향이 반대**다.
  //  - 교차 출처 링크: 우리 세션 쿠키가 가지 않는다 → 클릭 가능하게 두되 `rel`/`target` 강제.
  //  - **같은 출처 링크: 열람자의 세션으로 우리 엔드포인트를 부른다** → 그것이 위험한 쪽이다.
  //    `[정상 문서](/api/ai/oauth/authorize?client_id=…&redirect_uri=https://evil/cb)` 처럼
  //    라벨로 가려 두면 한 번의 클릭으로 열람자 권한의 인가 코드가 공격자에게 간다
  //    (codex 적대 리뷰 5R [P1] — 이미지 자동 GET 을 닫은 뒤에도 남아 있던 "권한 사용" 경로).
  //    첨부 문서가 이 앱의 엔드포인트로 딥링크할 정당한 이유는 없으므로 **비활성화**하고 URL 을
  //    텍스트로 보여 준다(숨기지 않는다 — 필요하면 사용자가 직접 복사해 연다).
  //  - 문서 내 앵커(`#section`)는 스크롤일 뿐이라 남긴다 — 긴 문서의 목차가 동작해야 한다.
  //  - `mailto:`/`tel:` 등 비-HTTP 스킴은 우리 세션과 무관하다.
  let deadLinks = 0;
  root.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) return;                       // 문서 내 앵커
    const u = _resolveUrl(href);
    if (!u || (u.protocol !== "http:" && u.protocol !== "https:")) return;
    if (u.origin !== window.location.origin) {
      // 문자열이 아니라 **resolve 된 origin** 으로 판정한다 — `//evil/x`(프로토콜 상대)가
      // `^https?:` 검사를 빠져나가던 구멍을 닫는다(codex [P1]).
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer nofollow");
      return;
    }
    const chip = document.createElement("span");
    chip.className = "attach-source-md-blocked";
    chip.textContent = `🚫 앱 내부 링크 비활성 · ${a.textContent || ""} · ${href}`;
    chip.title = "첨부 문서가 이 앱의 주소를 여는 것을 막았습니다 — 클릭 한 번으로 내 권한이 쓰일 수 있습니다. 필요하면 주소를 직접 복사해 여세요.";
    a.replaceWith(chip);
    deadLinks += 1;
  });
  // ```mermaid 블록을 **코드블록으로 되돌린다** (첨부 경로에서는 다이어그램을 렌더하지 않는다).
  //
  // 왜 렌더하지 않는가(codex 적대 리뷰 [P1]): `renderMermaidDiagrams` 는 sanitize·하드닝이 끝난
  // **뒤에** 라이브 DOM 으로 SVG 를 넣는다. mermaid 의 `%%{init: {"themeCSS": "…url(https://evil/x)"}}%%`
  // 지시자는 그 SVG 안 `<style>` 에 **외부 `url()` 을 그대로 만들어** 첨부 전용 sanitize 프로필과
  // 위 URL 중립화를 **둘 다 우회한** 열람 비콘이 된다(vendored mermaid 10.9.3 에서 재현됨).
  // 말풍선에서는 입력이 LLM 산출물이라 그 위험을 감수하지만, **첨부는 임의 업로드**다 — 같은
  // 파이프라인을 쓰되 이 후처리 한 단계만 끊는 것이 비용 대비 정확한 조치다.
  // 대안(생성된 SVG 를 inert DOM 에서 재정화)은 mermaid API 가 직접 삽입하는 구조라 우회면이
  // 다시 넓어지고, 다이어그램은 markdown 표준도 아니다 — 원문은 코드블록으로 그대로 읽힌다.
  root.querySelectorAll(".mermaid-block").forEach((el) => {
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.className = "language-mermaid";
    code.textContent = el.textContent || "";   // 텍스트로만 — 재주입 경로를 만들지 않는다
    pre.appendChild(code);
    el.replaceWith(pre);
  });

  // 넓은 표는 **표만** 가로 스크롤한다 — 감싸지 않으면 표 하나가 문서 전체에 가로 스크롤바를
  // 만들어 본문 읽기가 어긋난다(모달 폭은 고정이라 이 조건이 흔하다).
  root.querySelectorAll("table").forEach((t) => {
    if (t.parentElement && t.parentElement.classList.contains("attach-source-md-tablewrap")) return;
    const w = document.createElement("div");
    w.className = "attach-source-md-tablewrap";
    t.replaceWith(w);
    w.appendChild(t);
  });
  return { blockedMedia, deadLinks };
}

/**
 * 마크다운 본문을 컨테이너에 렌더한다.
 * @returns {{ok: boolean, blockedMedia: number}} `ok:false` 면 호출자가 원문 표로 폴백한다.
 */
function _renderMarkdownInto(container, text) {
  const src = String(text || "");
  // 렌더 라이브러리 미로드(파일 결합 실패·구버전 캐시)면 **조용히 빈 화면을 주지 않는다** —
  // 호출자가 원문 표로 폴백하고 사유를 배너로 알린다. `markdownToHtml` 은 그 경우
  // `<pre>` 폴백을 돌려주므로, 라이브러리 유무를 여기서 직접 판정한다.
  if (!window.marked || !window.DOMPurify) return { ok: false, blockedMedia: 0, deadLinks: 0 };
  let html = "";
  try { html = markdownToHtml(src); } catch (e) { return { ok: false, blockedMedia: 0, deadLinks: 0 }; }
  if (!html) return { ok: false, blockedMedia: 0, deadLinks: 0 };
  // 2차 sanitize — 첨부 전용 좁은 프로필(위 `_ATTACH_SANITIZE`). 문자열 입출력이라 DOMPurify
  // 내부 파싱은 inert 문서에서 일어난다(요청 없음).
  // ⚠️ **strict sanitize 전에** GFM 작업 목록의 체크박스를 글리프로 바꾼다.
  // `_ATTACH_SANITIZE` 는 `input` 을 막는데(피싱 표면), marked 가 `- [x]`/`- [ ]` 를 정확히
  // `<input type=checkbox disabled>` 로 내므로 그대로 두면 **체크 상태가 조용히 사라져**
  // `- [x] 완료` 와 `- [ ] 대기` 가 같은 목록으로 보인다(codex 적대 리뷰 3R [P1] — 요청한
  // 기능 자체의 회귀). 상태는 살리고 상호작용 요소는 없애기 위해 **비대화형 글리프**로 치환한다.
  // 이 변환도 `<template>`(inert)에서 수행하며 텍스트는 `textContent` 로만 넣는다.
  try {
    const tplTask = document.createElement("template");
    tplTask.innerHTML = html;
    // **사용자 HTML 의 `class` 를 걸러낸다.** 이것을 두면 `<div class="share-mgr-backdrop">` 한 줄로
    // 앱의 모달 배경 스타일(`position:fixed; z-index:9999`)을 그대로 얻어, 첨부 문서가 **앱 UI 를
    // 위장**할 수 있다(codex 적대 리뷰 6R [P1] — UI redress). `style` 을 막아도 클래스로 같은 일이
    // 된다. 렌더러가 만든 클래스(코드블록 언어·SQL 토큰·diff·mermaid)만 통과시킨다 — 그것들이
    // 없으면 코드블록 구문색·mermaid 강등이 함께 죽으므로 전부 지우지는 않는다.
    tplTask.content.querySelectorAll("[class]").forEach((el) => {
      const kept = String(el.getAttribute("class") || "").split(/\s+/)
        .filter((c) => c && _RENDERER_CLASS_RE.test(c));
      if (kept.length) el.setAttribute("class", kept.join(" "));
      else el.removeAttribute("class");
    });
    tplTask.content.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      const span = document.createElement("span");
      const checked = cb.hasAttribute("checked") || cb.checked === true;
      span.className = `attach-source-md-task${checked ? " is-checked" : ""}`;
      span.textContent = checked ? "☑" : "☐";
      span.setAttribute("aria-label", checked ? "완료" : "미완료");
      cb.replaceWith(span);
    });
    html = tplTask.innerHTML;
  } catch (e) { /* 변환 실패는 치명적이지 않다 — 아래 sanitize 가 체크박스를 지울 뿐 */ }

  let safe = "";
  try { safe = window.DOMPurify.sanitize(html, _ATTACH_SANITIZE); }
  catch (e) { return { ok: false, blockedMedia: 0, deadLinks: 0 }; }
  if (!safe) return { ok: false, blockedMedia: 0, deadLinks: 0 };

  // ⚠️ **inert 파싱이 이 함수의 핵심**이다. 초판은 살아 있는 노드에 sanitize 결과를 그대로 먹여 파싱한 뒤
  // 원격 미디어를 제거했는데, 브라우저는 **파싱 시점에 이미 요청을 시작**한다 — 최종 DOM 에서
  // 지워도 비콘은 이미 나간 뒤다(codex 적대 리뷰 [P1], 이 기능의 목적 자체를 무효화하던 결함).
  // `<template>` 의 content 는 browsing context 가 없는 별도 문서라 **리소스를 가져오지 않는다**
  // (같은 이유로 `enhanceMermaidBlocks`·`enhanceDiffBlocks` 도 template 을 쓴다). 여기서 URL 을
  // 중립화한 **뒤에** 라이브 DOM 으로 옮기므로, 교차 출처 요청은 한 번도 발생하지 않는다.
  const tpl = document.createElement("template");
  tpl.innerHTML = safe;
  const { blockedMedia, deadLinks } = _hardenRenderedMarkdown(tpl.content);

  const host = document.createElement("div");
  // `message-content` 를 함께 붙여 답변 말풍선과 **같은 타이포·코드블록 스타일**을 상속한다
  // (같은 파이프라인의 산출물이 화면마다 다르게 보이지 않게). 첨부 전용 조정은
  // `.attach-source-md` 쪽에만 둔다.
  host.className = "attach-source-md message-content";
  host.appendChild(tpl.content);              // 이 시점엔 교차 출처 URL 이 남아 있지 않다
  container.appendChild(host);
  // ⚠️ **여기서 `renderMermaidDiagrams` 를 호출하지 않는다** — 그것은 sanitize·하드닝 이후에
  // 라이브 DOM 으로 SVG 를 넣는 유일한 경로이고, mermaid `themeCSS` 지시자로 외부 `url()` 을
  // 심을 수 있어 두 방어선을 모두 우회한다(위 `_hardenRenderedMarkdown` 의 mermaid 주석 참조).
  // ```mermaid 는 코드블록으로 표시되며, 그 변환은 하드닝 단계가 **inert** 상태에서 끝냈다.
  return { ok: true, blockedMedia, deadLinks };
}

function _versionLabel(v) {
  const n = Number(v.version_number || 1);
  const role = v.is_assistant_generated || v.created_by_role === "assistant" ? "AI 수정" : "사용자";
  const latest = (v.superseded === false || v.is_latest === true) ? " · 최신" : "";
  return `v${n} · ${role}${latest}`;
}

function _fmtBytes(b) {
  const n = Number(b || 0);
  if (n > 1048576) return `${(n / 1048576).toFixed(1)}MB`;
  if (n > 1024) return `${(n / 1024).toFixed(0)}KB`;
  return `${n}B`;
}

// 열 폭은 **반드시 `<colgroup>` 으로 선언**한다 — `td` 의 width 규칙으로는 안 된다.
//
// `table-layout: fixed` 는 열 폭을 **첫 행의 셀**에서 가져온다. 그런데 맥락 축약 뷰의 첫 행은
// 흔히 `gap`(`colspan=4|3`) 이고, 그러면 개별 열 폭이 정의되지 않아 브라우저가 표를 **균등
// 분할**한다 — `.attach-diff-lineno{width:48px}` 과 `.attach-diff-code{width:calc(50% - 48px)}`
// 가 통째로 무시된다. 라이브 실측(PB-0008, 2026-08-06): 표 1136px 에서 네 열이 전부 284px 로
// 잡혀 본문이 가운데로 몰리고 양옆에 큰 여백이 생겼다. jsdom·정적 검사로는 보이지 않는
// 픽셀-클래스 결함이다(§16.6). `<colgroup>` 은 행 순서와 무관하게 열 폭을 확정한다.
function _appendColgroup(table, kind, opts) {
  const cg = document.createElement("colgroup");
  const cols = kind === "unified"
    ? ["attach-diff-col-no", "attach-diff-col-sign", "attach-diff-col-code"]
    : kind === "source"
      ? ["attach-diff-col-no", "attach-diff-col-code"]
      : ["attach-diff-col-no", "attach-diff-col-code", "attach-diff-col-no", "attach-diff-col-code"];
  for (const cls of cols) {
    const col = document.createElement("col");
    col.className = cls;
    cg.appendChild(col);
  }
  // ⚠️ `table-layout: fixed` 의 `col` 폭에서 **퍼센트를 포함한 `calc()` 는 Chrome 이 무시**하고
  // 그 열을 auto 로 떨어뜨려 균등 분배한다(실측 2026-08-07: `calc(0.3*(100% - 4ch - 24px))` ·
  // `calc(30% - 12px)` 모두 무시 → 468/468. `30%`·`300px`·퍼센트 없는 `calc(2ch + 12px)` 는 honor).
  // 따라서 줄번호(절대 calc)는 여기서 정하고, **좌우 code 폭은 렌더 후 `_applySplitRatio` 가
  // 실측 기반 plain % 로 설정**한다. 초기값은 지정하지 않는다(auto = 균등 → rAF 에서 보정).
  const noCh = Math.max(1, Number((opts && opts.linenoCh) || 3));
  const noW = `calc(${noCh}ch + 12px)`;
  const list = Array.from(cg.children);
  list[0].style.width = noW;
  if (kind === "unified") {
    // 부호 열은 CSS(18px), code 열은 auto — 남는 폭을 전부 먹는다.
    list[2].style.width = "";
  } else if (kind === "source") {
    // 원문 뷰는 줄번호 + 본문 2열뿐 — 본문이 남는 폭을 전부 먹는다(auto).
    list[1].style.width = "";
  } else {
    list[2].style.width = noW;
  }
  table.appendChild(cg);
  return cg;
}

// 좌우 code 열 폭을 비율대로 설정한다. 퍼센트는 표 폭 기준이라 **줄번호 열의 실측 폭**을
// 빼고 나눠야 정확하다(줄번호는 자릿수 기반 절대폭이라 표가 커져도 거의 불변).
function _applySplitRatio(table, cols, ratio) {
  const row = table.querySelector("tr.attach-diff-row:not(.is-gap)");
  const cells = row ? row.querySelectorAll("td") : null;
  if (!cells || cells.length !== 4 || cols.length !== 4) return;
  const tableW = table.getBoundingClientRect().width;
  const noW = cells[0].getBoundingClientRect().width + cells[2].getBoundingClientRect().width;
  const avail = tableW - noW;
  if (tableW <= 0 || avail <= 0) return;
  const r = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, ratio));
  cols[1].style.width = `${(avail * r / tableW * 100).toFixed(4)}%`;
  cols[3].style.width = `${(avail * (1 - r) / tableW * 100).toFixed(4)}%`;
}

// ── 문단(블록) 단위 하이라이트 ───────────────────────────────────────────────
// 사용자 요청(2026-08-07): "line 단위 하이라이트 뿐만 아니라, 문단 단위 하이라이트도".
// 줄마다 배경만 칠하면 5줄이 한 덩어리로 바뀐 변경과 1줄씩 5곳이 바뀐 변경이 **같아 보인다**.
// 연속된 비-equal 행을 한 **블록**으로 묶어 시작/끝 경계와 좌측 accent 를 준다.
//
// 계산은 **한 곳**에서만 한다 — 2열·단일열이 같은 블록 경계를 봐야 한다(두 뷰가 같은 응답의
// 두 표현이라는 불변식의 연장). gap 은 블록을 끊는다(생략 구간을 건너 이어붙이면 거짓 연속).
function _assignBlocks(rows) {
  const list = rows || [];
  let blockId = 0;
  let i = 0;
  while (i < list.length) {
    const r = list[i];
    if (!r || r.type === "equal" || r.type === "gap") { i += 1; continue; }
    let j = i;
    while (j < list.length && list[j] && list[j].type !== "equal" && list[j].type !== "gap") j += 1;
    blockId += 1;
    for (let k = i; k < j; k++) {
      list[k]._block = blockId;
      list[k]._blockFirst = (k === i);
      list[k]._blockLast = (k === j - 1);
      list[k]._blockSize = j - i;
    }
    i = j;
  }
  return blockId;
}

// 행에 블록 클래스·앵커 데이터를 붙인다. 두 렌더러가 공유한다.
//   `data-lno` — 스크롤 앵커용 줄번호(우측 우선, 없으면 좌측). gap 은 없음.
function _decorateRow(tr, r, opts) {
  if (r._block) {
    tr.classList.add("in-block");
    if (r._blockFirst) tr.classList.add("is-block-start");
    if (r._blockLast) tr.classList.add("is-block-end");
    if (Number(r._blockSize) > 1) tr.classList.add("is-block-multi");
    tr.dataset.block = String(r._block);
  }
  const lno = (opts && opts.lnoSide === "left")
    ? (r.left_no ?? r.right_no)
    : (r.right_no ?? r.left_no);
  if (lno != null) tr.dataset.lno = String(lno);
}

// ── 스크롤 위치 보존 ────────────────────────────────────────────────────────
// 사용자 보고(2026-08-07): "상호작용을 할 때(펼치기, 동일한 줄도 모두 보기, 좌우 2열/단일열
// 교체 등) 스크롤이 최상단으로 이동".
//
// 원인: `_renderBody` 가 `bodyEl.innerHTML = ""` 로 본문을 비우고 **scroller 를 새로 만든다** —
// 스크롤은 그 요소의 상태이므로 요소와 함께 사라진다. scrollTop 을 그냥 복원하면 안 되는 이유:
//   ① 전개·토글로 **행 수가 바뀌면** 같은 픽셀 위치가 다른 줄을 가리킨다.
//   ② 2열↔단일열은 `replace` 가 1행↔2행이라 높이가 근본적으로 다르다.
// 그래서 **줄번호로 앵커**한다 — 화면 최상단에 보이던 줄을 찾아 그 줄을 다시 최상단에 둔다.
// 픽셀이 아니라 "사용자가 보고 있던 내용" 을 보존한다.
//
// 검증 정본은 **실 브라우저**다 — innerHTML 교체 직후 scrollHeight 가 작으면 브라우저가
// scrollTop 을 0으로 clamp 하는데, jsdom 은 clamp 를 하지 않아 그 결함을 통과시킨다
// (auto-memory `project-frontend-scroll-restore-jsdom-gotcha`).
function _captureScrollAnchor(scroller) {
  if (!scroller) return null;
  const top = scroller.scrollTop;
  if (top <= 0) return null;   // 최상단이면 보존할 것이 없다
  const rows = scroller.querySelectorAll("tr[data-lno]");
  const scRect = scroller.getBoundingClientRect();
  for (const tr of rows) {
    const r = tr.getBoundingClientRect();
    if (r.bottom > scRect.top + 1) {   // 첫 '보이는' 행
      return { lno: Number(tr.dataset.lno), offset: Math.round(r.top - scRect.top), left: scroller.scrollLeft };
    }
  }
  return { lno: null, offset: 0, left: scroller.scrollLeft, ratio: top / Math.max(1, scroller.scrollHeight) };
}

function _restoreScrollAnchor(scroller, anchor) {
  if (!scroller || !anchor) return;
  const apply = () => {
    if (anchor.left) scroller.scrollLeft = anchor.left;
    if (anchor.lno == null) {
      if (anchor.ratio) scroller.scrollTop = anchor.ratio * scroller.scrollHeight;
      return;
    }
    // 같은 줄번호가 없으면(뷰 전환으로 그 줄이 다른 쪽에만 존재) **가장 가까운 이하 줄**로.
    let best = null;
    for (const tr of scroller.querySelectorAll("tr[data-lno]")) {
      const n = Number(tr.dataset.lno);
      if (n === anchor.lno) { best = tr; break; }
      if (n < anchor.lno && (!best || n > Number(best.dataset.lno))) best = tr;
    }
    if (!best) return;
    scroller.scrollTop = best.offsetTop - anchor.offset;
  };
  // rAF 2회 후 적용 — **방어적 조치이며 현재 호출 지점에서는 필수가 아니다**(정직 표기).
  // `_renderBody` 는 `_attachSplitHandle`(→ `_applySplitRatio`)을 동기로 끝낸 뒤 여기 오고,
  // `apply()` 가 읽는 `offsetTop` 이 동기 레이아웃을 강제하므로 즉시 실행도 동작한다 —
  // 헤드리스 하네스는 rAF 제거를 **구별하지 못한다**(뮤테이션 실측: S1~S6 전부 생존).
  // 그래도 남겨 두는 이유: 호출 지점이 늘어 레이아웃이 강제되지 않는 경로가 생기면 그때는
  // clamp 가 되살아나고, 그 실패는 조용하다. 비용이 프레임 2개뿐이라 방어를 유지한다.
  requestAnimationFrame(() => requestAnimationFrame(apply));
}

// gap 행을 만든다. `onExpand` 가 주어지면 **누를 수 있는 버튼**이 되어 그 구간만 국소 전개한다
// (사용자 요청 2026-08-07 — "동일한 줄도 모두 보기" 가 꺼진 상태에서 부분만 펼치는 수요).
function _gapRow(r, colSpan, onExpand) {
  const tr = document.createElement("tr");
  tr.className = "attach-diff-row is-gap";
  const td = document.createElement("td");
  td.colSpan = colSpan;
  td.className = "attach-diff-gap";
  const n = Number(r.skipped || 0);
  if (onExpand) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "attach-diff-gap-btn";
    btn.textContent = `⋯ 동일한 ${n}줄 생략 — 펼치기`;
    btn.title = `숨은 ${n}줄을 이 자리에만 표시합니다`;
    btn.addEventListener("click", () => onExpand(r, btn));
    td.appendChild(btn);
  } else {
    td.textContent = `⋯ 동일한 ${n}줄 생략`;
  }
  tr.appendChild(td);
  return tr;
}

// ── 파일 유형별 구문 하이라이트 ──────────────────────────────────────────────
// 사용자 요청(2026-08-06): "파일 유형에 따른 확장 하이라이트(SQL 예약어 등)".
//
// 왜 필요한가: diff 배경색은 "이 줄이 바뀌었다" 까지만 말한다. 바뀐 것이 테이블명인지 값인지
// 주석인지는 토큰 색이 있어야 한 눈에 갈린다 — 특히 SQL·설정 파일에서 예약어와 식별자가
// 같은 색이면 `SET status = status` 류의 줄에서 변경 지점을 눈으로 찾지 못한다.
//
// 두 렌더러가 **같은 함수**로 칠한다(2열·단일열이 같은 응답의 두 표현이라는 불변식의 연장 —
// 한쪽만 칠하면 토글이 서로 다른 화면이 된다). 토큰화 자체는 `code-highlight.js` 정본이고
// 여기서는 셀에 적용하는 얇은 어댑터만 둔다.
//
// `opts.lang` 이 없으면(미지원 확장자·판정 실패) 종전과 **완전히 같은** 평문 경로다.
// 렌더-측 마크 예산 — 서버 예산은 **계산**을 막을 뿐 **렌더된 span 수**는 막지 않는다.
// 실측(§18.8 frontend 패널 P2, jsdom): 10필드 CSV 6,000행에 행마다 5필드 변경이면 서버 예산
// (361/행 × 6,000 = 2.17M ≤ 3M)을 통과해 **전 행이 마크**되고, chunk span 60,000개 · 노드
// 222,007개가 된다(구문 하이라이트까지 켜면 438,007). 표는 가상화가 없고 `_renderBody` 가
// 상호작용마다 통째로 다시 만들므로 그 비용을 매번 치른다. 예산을 넘으면 남은 행은 **줄 단위
// 강조 그대로** 두고 배너로 알린다 — 조용히 절반만 칠하는 것이 가장 나쁜 결과다.
const MARK_RENDER_BUDGET = 12000;
// 계약 위반 경고는 렌더당 1회만 — 6,000행에서 매 행 경고하면 콘솔이 무용지물이 된다.
let _markContractWarned = false;

function _paintCell(td, text, opts, segs) {
  const lang = opts && opts.lang;
  if (!lang) td.textContent = text == null ? "" : text;
  else paintCodeInto(td, text == null ? "" : text, lang);
  if (!segs) return;
  const budget = opts && opts.markBudget;
  if (budget && budget.left <= 0) { budget.exhausted = true; return; }
  const made = _markSegments(td, segs);
  if (budget) budget.left -= made;
}

// ── 줄 안(intra-line) 변경 구간 마킹 ────────────────────────────────────────
// 사용자 요청(2026-08-07): "여전히 line 단위 차이만 나타나고 각 글자 단위의 차이점은 출력되지
// 않는다". 줄 배경은 "이 줄이 바뀌었다" 까지만 말한다 — 200자 CSV 행에서 한 칸이 바뀐 경우
// 사용자가 두 줄을 눈으로 대조해야 했다.
//
// **구간은 서버가 정한다**(`left_segs`/`right_segs`). 프론트가 각자 계산하면 2열과 단일열이
// 같은 줄에 다른 강조를 그릴 수 있다 — "두 뷰는 같은 응답의 두 표현" 불변식의 연장이다.
//
// **덧그리기이지 다시 그리기가 아니다**: 구문 하이라이트가 이미 셀을 토큰 span 으로 나눠 놓았고,
// 변경 경계는 토큰 경계와 일치하지 않는다(`user_id` 가 한 토큰인데 `id` 만 바뀔 수 있다).
// 그래서 텍스트를 다시 만들지 않고 **이미 있는 텍스트 노드를 문자 오프셋으로 쪼개** 감싼다.
// 두 강조가 독립 레이어라 어느 쪽도 상대를 지우지 않는다.
function _markSegments(td, segs) {
  if (!td || !Array.isArray(segs) || segs.length === 0) return 0;
  // 재적용 방지 — 두 번 씌우면 chunk 가 중첩된다. 현재 호출부는 매번 새 `td` 를 만들어
  // 도달하지 않지만, `_markSegments` 가 하네스 2곳이 쓰는 이름 있는 seam 이 된 이상
  // 잠재 함정으로 남는다(§18.8 frontend 패널 P3 — 재현 확인됨).
  if (td.querySelector(".attach-diff-chunk")) return 0;
  const ranges = [];
  const parts = [];
  let pos = 0;
  for (const s of segs) {
    const v = String((s && s.v) || "");
    parts.push(v);
    if (s && s.t === "ch" && v.length > 0) ranges.push([pos, pos + v.length]);
    pos += v.length;
  }
  if (ranges.length === 0) return 0;
  // 세그먼트를 이으면 원문과 동치라는 것이 서버 계약이다. 어긋나면(계약 드리프트·부분 응답)
  // **아무것도 하지 않는다** — 어긋난 위치에 마크를 그리는 것은 마크가 없는 것보다 나쁘다.
  // 안 그리면 종전의 줄 단위 강조가 그대로 남지만, 잘못 그리면 없는 변경을 지목한다.
  //
  // 길이만 비교하면 **같은 길이의 다른 내용**이 통과해 엉뚱한 위치를 칠한다(§18.8 frontend
  // 패널 P3 재현: `[eq "SELECT ", ch "uid", eq " FROM user"]` 가 `id ` 를 칠했다). 서버에서
  // 도달 가능한 경로는 확인되지 않았지만, 이미 모든 조각을 손에 쥐고 있어 문자열 비교가 같은
  // O(n) 이다 — 더 약한 검사를 고를 이유가 없다.
  if (parts.join("") !== (td.textContent || "")) {
    // fail-closed 는 맞지만 **조용하면 안 된다** — 계약이 드리프트하면 표 전체에서 마크가
    // 사라지는데 사용자도 개발자도 "원래 변경이 없었다" 와 구별하지 못한다(§18.8 frontend
    // 패널 P3 · docs/CODE_REVIEW.md §2.1 "삼켜진 예외"). 렌더당 1회만 알린다.
    if (!_markContractWarned) {
      _markContractWarned = true;
      console.warn("[attach-diff] 줄 안 세그먼트가 셀 원문과 일치하지 않아 마킹을 건너뜁니다.");
    }
    return 0;
  }

  const doc = td.ownerDocument;
  const walker = doc.createTreeWalker(td, 4 /* NodeFilter.SHOW_TEXT */);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);

  let off = 0;
  let made = 0;
  for (const node of nodes) {
    const text = node.nodeValue || "";
    const start = off;
    const end = off + text.length;
    off = end;
    const local = [];
    for (const [rs, re] of ranges) {
      const a = Math.max(rs, start);
      const b = Math.min(re, end);
      if (b > a) local.push([a - start, b - start]);
    }
    if (local.length === 0) continue;
    const frag = doc.createDocumentFragment();
    let cur = 0;
    for (const [a, b] of local) {
      if (a > cur) frag.appendChild(doc.createTextNode(text.slice(cur, a)));
      const span = doc.createElement("span");
      span.className = "attach-diff-chunk";
      span.textContent = text.slice(a, b);
      frag.appendChild(span);
      made += 1;
      cur = b;
    }
    if (cur < text.length) frag.appendChild(doc.createTextNode(text.slice(cur)));
    node.parentNode.replaceChild(frag, node);
  }
  return made;   // 만든 span 수 — 호출자가 렌더 예산에서 차감한다
}

// 2열 렌더 — 서버 rows(좌우 정렬 + gap)를 그대로 표로 펼친다.
function _renderSplit(container, data, opts) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-split";
  _assignBlocks(data.rows);
  _appendColgroup(table, "split", {
    linenoCh: _linenoCh(data.rows), ratio: (opts && opts.ratio) });
  const tbody = document.createElement("tbody");
  for (const r of data.rows || []) {
    const tr = document.createElement("tr");
    if (r.type === "gap") {
      tbody.appendChild(_gapRow(r, 4, opts && opts.onExpandGap));
      continue;
    }
    tr.className = `attach-diff-row is-${r.type}`;
    const lNo = document.createElement("td");
    lNo.className = "attach-diff-lineno";
    lNo.textContent = r.left_no == null ? "" : String(r.left_no);
    const lTxt = document.createElement("td");
    lTxt.className = "attach-diff-code side-left";
    _paintCell(lTxt, r.left, opts, r.left_segs);
    const rNo = document.createElement("td");
    rNo.className = "attach-diff-lineno";
    rNo.textContent = r.right_no == null ? "" : String(r.right_no);
    const rTxt = document.createElement("td");
    rTxt.className = "attach-diff-code side-right";
    _paintCell(rTxt, r.right, opts, r.right_segs);
    // 좌/우 강조는 **내용이 있는 쪽**에만 — 빈 셀에 색을 얹으면 없는 변경을 가리킨다.
    // (`has-content` 는 줄 배경, `has-block` 은 문단 accent. 둘이 같은 규칙을 따라야 한다.)
    if (r.left != null) lTxt.classList.add("has-content");
    if (r.right != null) rTxt.classList.add("has-content");
    if (r._block) {
      if (r.left != null) lTxt.classList.add("has-block");
      if (r.right != null) rTxt.classList.add("has-block");
    }
    _decorateRow(tr, r, {});
    tr.append(lNo, lTxt, rNo, rTxt);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

// 단일열 렌더 — 같은 rows 를 삭제→추가 순으로 한 줄씩 펼친다. 서버 `unified_diff`
// 문자열을 그대로 뿌리지 않는 이유: 줄번호 표시·gap 표기를 2열과 동일한 규칙으로
// 유지해야 토글이 "같은 데이터의 두 표현" 이 되기 때문(하나는 표, 하나는 텍스트면
// 사용자가 두 화면을 별개 결과로 읽는다).
function _renderUnified(container, data, opts) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-unified";
  _assignBlocks(data.rows);
  _appendColgroup(table, "unified", { linenoCh: _linenoCh(data.rows) });
  const tbody = document.createElement("tbody");
  // `src` = 이 표시 행이 파생된 원본 row (블록 경계·앵커 산출용). `replace` 는 두 행으로
  // 펼쳐지므로 경계 플래그를 **펼친 결과 기준**으로 보정한다(첫 행만 start, 끝 행만 end).
  // `segs` = 이 표시 행이 쓸 intra-line 세그먼트. `replace` 는 두 행으로 펼쳐지므로 삭제 행에는
  // 좌측(`left_segs`), 추가 행에는 우측(`right_segs`) 을 넘긴다 — 2열과 같은 구간을 보게 된다.
  const push = (type, no, sign, text, src, edge, segs) => {
    const tr = document.createElement("tr");
    tr.className = `attach-diff-row is-${type}`;
    if (src) {
      const view = {
        ...src,
        _blockFirst: src._blockFirst && (edge !== "tail"),
        _blockLast: src._blockLast && (edge !== "head"),
      };
      _decorateRow(tr, view, { lnoSide: type === "delete" ? "left" : "right" });
    }
    const tdNo = document.createElement("td");
    tdNo.className = "attach-diff-lineno";
    tdNo.textContent = no == null ? "" : String(no);
    const tdSign = document.createElement("td");
    tdSign.className = "attach-diff-sign";
    tdSign.textContent = sign;
    const tdTxt = document.createElement("td");
    tdTxt.className = "attach-diff-code";
    if (src && src._block) tdTxt.classList.add("has-block");
    // `has-content` 는 **줄 배경**(danger/ok)의 게이트다 — `has-block`(문단 accent) 과 짝이며
    // 둘 다 붙여야 한다. 직전 cycle 이 배경 규칙을 `.has-content` 로 좁힐 때 2열 렌더러에만
    // 클래스를 부여해, 단일열의 추가/삭제 줄이 색을 잃고 오히려 **"대응 내용 없음" 을 뜻하는
    // 중립 filler** 를 받았다(라이브 실측: 내용 있는 'B2' 가 rgb(240,239,234)). 색이 사라진
    // 것보다 나쁘게 **의미가 반대로 뒤집혔다**. 두 렌더러가 같은 규칙을 따르는지 B9/B9b 가 고정.
    if (text != null) tdTxt.classList.add("has-content");
    _paintCell(tdTxt, text, opts, segs);
    tr.append(tdNo, tdSign, tdTxt);
    tbody.appendChild(tr);
  };
  for (const r of data.rows || []) {
    if (r.type === "gap") {
      tbody.appendChild(_gapRow(r, 3, opts && opts.onExpandGap));
    } else if (r.type === "equal") {
      push("equal", r.right_no, " ", r.right, r);
    } else if (r.type === "delete") {
      // 두 렌더러가 **같은 규칙**으로 세그먼트를 전달한다. 오늘은 서버가 `replace` 에만
      // 세그먼트를 실어 실동작이 같지만, 여기서 조건이 갈라져 있으면 서버가 범위를 넓히는
      // 순간 2열에만 마크가 뜨고 단일열에는 안 뜬다 — 조용히 두 뷰가 달라진다
      // (§18.8 frontend 패널 P3).
      push("delete", r.left_no, "-", r.left, r, undefined, r.left_segs);
    } else if (r.type === "insert") {
      push("insert", r.right_no, "+", r.right, r, undefined, r.right_segs);
    } else {  // replace — 삭제 줄과 추가 줄을 연달아
      push("delete", r.left_no, "-", r.left, r, "head", r.left_segs);
      push("insert", r.right_no, "+", r.right, r, "tail", r.right_segs);
    }
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

// identical 응답의 **단정 강도**를 정하는 두 플래그. 렌더(배너)와 요약 배지가 같은 판정을
// 써야 한 화면에서 서로 반박하지 않는다(§18.8 패널 공통 지적 — "차이가 많아" ↔ "차이 없음").
//  - `clipped`: 원본 바이트 cap 또는 행 상한에 걸렸다 ⇒ **본 범위 안에서만** 동일하다.
//    이때 "원문" 이라는 말을 쓰면 안 된다 — 보지 않은 뒷부분을 봤다고 주장하는 셈이다.
//  - `shaDiff`: 줄 비교는 같은데 파일 해시가 다르다. 서버 비교는 `splitlines()` 기반이라
//    CRLF↔LF·마지막 줄 개행 유무가 **판정에서 흡수**된다. 그 차이는 사용자에게 실재하고
//    (크기·해시가 다르다), 판별 근거(sha256)는 이미 응답에 실려 있다.
function _identicalFlags(data) {
  const tr = (data && data.truncated) || {};
  const clipped = Boolean(tr.rows || tr.from_source || tr.to_source);
  const a = String(data?.from?.sha256 || "");
  const b = String(data?.to?.sha256 || "");
  return { clipped, shaDiff: Boolean(a) && Boolean(b) && a !== b };
}

/**
 * 한 화면의 **본문 상태**를 판정하는 단일 면 — 이 모듈의 컨트롤 노출·비활성은 전부 여기서 갈린다.
 *
 * 판정을 함수 하나로 모은 이유: 컨트롤마다 자기 조건을 따로 쓰면 같은 화면에서 어떤 토글은
 * 사라지고 어떤 토글은 남는 "규칙 없는 컨트롤 바" 가 된다(§18.8 패널이 실제로 지적한 결함).
 * 이제 두 모달이 같은 화면에서 같은 답을 얻는다 — 원문 보기 모달도 비교를 수행하게 되면서
 * (REQ-20260813-attach-source-compare) 판정 사본이 세 벌이 될 자리였다.
 *
 * @param {object|null} data  `/source` 또는 `/diff` 응답
 * @param {"source"|"diff"} kind  응답 스키마 — 본문 유무 키가 다르다(`viewable` vs `comparable`)
 * @returns {{rows:number, hasBody:boolean, sourceView:boolean, hasDiff:boolean}}
 *   - `hasBody`: 칠할 본문 줄이 화면에 있다(구문 색 토글의 전제).
 *   - `sourceView`: 그 본문이 **원문**이다 — 원문 응답은 항상 그렇고, diff 응답은 내용이
 *     동일할 때만 그렇다(줄 대조 diff 를 마크다운으로 렌더하면 대조가 사라진다).
 *   - `hasDiff`: diff 표가 실제로 그려진다(보기 방식·맥락 토글의 전제).
 */
function _bodyState(data, kind) {
  const isDiff = kind === "diff";
  const rows = Array.isArray(data?.rows) ? data.rows.length : 0;
  const hasBody = Boolean(data) && rows > 0
    && (isDiff ? data.comparable !== false : data.viewable !== false);
  const sourceView = hasBody && (isDiff ? Boolean(data.identical) : true);
  const hasDiff = Boolean(isDiff && hasBody && !data.identical);
  return { rows, hasBody, sourceView, hasDiff };
}

// `/source` 응답의 절단 여부. 절단·해시와 같은 계열의 판정이다 — **"원문" 은 전량을 봤을 때만
// 쓸 수 있는 말**이므로(`_identicalFlags` 와 같은 원칙) 절단이면 제목·통계·배너가 함께 강도를
// 낮춘다. 두 모달이 같은 함수를 쓴다(원문 보기 · 비교의 같은-버전 화면).
function _sourceClipped(data) {
  return Boolean(data && (
    (data.truncated && (data.truncated.source || data.truncated.rows))
    || data.stats?.lines_partial));
}

/** `/source` 응답 한 벌의 요약 배지 문구 — 절단이면 "앞 N행" 으로 말한다. */
function _sourceStatsText(data) {
  if (!data || data.viewable === false) return "";
  const shown = Array.isArray(data.rows) ? data.rows.length : 0;
  const size = _fmtBytes(data.version?.size);
  return _sourceClipped(data)
    ? `앞 ${shown}행 표시 · 전체 ${size}`
    : `${Number(data.stats?.lines || 0)}줄 · ${size}`;
}

/** `/diff` 응답 한 벌의 요약 배지 문구. 배너(`_renderBody`)와 **같은 판정**(`_identicalFlags`)을
 *  쓴다 — 한 화면의 두 요약이 서로 반박하면 사용자는 어느 쪽을 믿을지 판단할 수 없다. */
function _diffStatsText(data) {
  if (!data || data.comparable === false) return "";
  const st = data.stats || {};
  if (!data.identical) return `+${Number(st.added || 0)} / -${Number(st.removed || 0)}`;
  const flags = _identicalFlags(data);
  if (flags.clipped) return "차이 없음(부분 비교)";
  if (flags.shaDiff) return "줄 차이 없음 · 파일은 다름";
  return "차이 없음 — 원문 표시";
}

// 마크다운 렌더의 두 배너. 문구를 한 곳에 두는 이유는 이 모듈의 다른 복제 사례와 같다 —
// 두 화면(원문 보기 · 비교의 identical 화면)이 같은 사실을 다른 말로 알리면, 한쪽만 고쳐지는
// 방식으로 갈라진다.
function _mdBlockedNotice({ blockedMedia, deadLinks }) {
  if (!blockedMedia && !deadLinks) return null;
  const el = document.createElement("div");
  el.className = "attach-diff-notice is-warn";
  const parts = [];
  if (blockedMedia) parts.push(`이미지·미디어 ${blockedMedia}건`);
  if (deadLinks) parts.push(`앱 내부 링크 ${deadLinks}건`);
  el.textContent =
    `${parts.join(" · ")}을 차단했습니다 — 문서를 여는 것만으로 열람 사실이 외부로 새거나 `
    + "클릭 한 번으로 내 권한이 쓰이지 않도록 막았습니다. 원래 주소는 본문에 표시됩니다.";
  return el;
}

function _mdFallbackNotice() {
  const el = document.createElement("div");
  el.className = "attach-diff-notice is-warn";
  el.textContent =
    "마크다운으로 렌더하지 못해 원문으로 표시합니다 (렌더 라이브러리 미로드일 수 있습니다).";
  return el;
}

// 원문 렌더 — **두 버전의 내용이 동일할 때** 쓰는 제3의 표현(사용자 요청 2026-08-07:
// "파일 내용이 동일하다면 문서 원문을 출력").
//
// 왜 별 렌더러인가: 2열은 같은 글을 좌우에 두 번 그려 폭을 절반씩 낭비하고(비교할 것이
// 없는데 비교 표 모양을 유지하면 "어딘가 다른가?" 하고 찾게 만든다), 단일열은 부호 열이
// 전부 공백이라 의미 없는 열이 남는다. 원문은 줄번호 + 본문 2열이면 충분하다.
//
// 줄번호는 **우측(to) 기준**이다 — 두 내용이 같으므로 좌우 번호가 같지만, 없을 때만
// 좌측으로 떨어뜨려(빈 파일·구버전 응답 방어) 번호 칸이 비지 않게 한다.
// gap 행은 여기 오지 않는 것이 정상이다(서버가 identical 이면 축약하지 않는다). 그래도
// 오면 "생략" 문구로 그린다 — 조용히 버리면 사용자가 잘린 원문을 전체로 오인한다.
function _renderSource(container, data, opts) {
  // 마크다운 렌더 경로 — `.md` 첨부를 문서로 출력한다(사용자 요청 2026-08-12).
  // 실패(라이브러리 미로드·빈 결과) 시 **조용히 비우지 않고** 아래 원문 표로 떨어진다.
  if (opts && opts.md) {
    const res = _renderMarkdownInto(container, _sourceText(data));
    if (res.ok) {
      if (typeof opts.onMdRendered === "function") opts.onMdRendered(res);
      return;
    }
    if (typeof opts.onMdFallback === "function") opts.onMdFallback();
  }

  const table = document.createElement("table");
  // `is-source` 는 **표 계층** modifier 다(`is-split`·`is-unified` 와 같은 축). 행 계층은
  // `is-equal`/`is-insert`… 어휘라 같은 토큰을 두 계층에 얹지 않는다 — 후속 CSS 규칙이 두 곳에
  // 걸려 의도치 않게 번진다(§18.8 design 지적). 원문 행은 diff 타입이 없으므로 `is-plain`.
  table.className = "attach-diff-table is-source";
  table.setAttribute("aria-label", `문서 원문 ${(data.rows || []).length}행`);
  _appendColgroup(table, "source", { linenoCh: _linenoCh(data.rows) });
  const tbody = document.createElement("tbody");
  for (const r of data.rows || []) {
    if (r.type === "gap") {
      tbody.appendChild(_gapRow(r, 2, null));
      continue;
    }
    const tr = document.createElement("tr");
    tr.className = "attach-diff-row is-plain";
    const no = r.right_no ?? r.left_no;
    if (no != null) tr.dataset.lno = String(no);
    const tdNo = document.createElement("td");
    tdNo.className = "attach-diff-lineno";
    // 원문 뷰는 성격이 **문서**다 — 줄번호를 매 행 낭독하면 읽기가 불가능해진다. diff 표는
    // 좌/우 대조라는 표 성격이 있어 낭독이 정당하지만 여기서는 시각 보조에 불과하다.
    tdNo.setAttribute("aria-hidden", "true");
    tdNo.textContent = no == null ? "" : String(no);
    const tdTxt = document.createElement("td");
    tdTxt.className = "attach-diff-code";
    _paintCell(tdTxt, r.right ?? r.left, opts);
    tr.append(tdNo, tdTxt);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

/**
 * `/source` 응답 한 벌을 **원문 화면**으로 그린다 — 강등(바이너리)·절단 배너·빈 문서·원문 표.
 *
 * 두 모달이 공유한다: 원문 보기 모달의 기본 화면이자, 비교 모달에서 **같은 버전 두 개를 고른**
 * 화면(REQ-20260813-attach-source-compare — 사용자 요청 "같은 버전이나 버전 간 변경사항이 없는
 * 경우에는 문서 원문을 그대로 출력"). 종전 비교 모달은 그 선택에 "서로 다른 두 버전을
 * 선택하세요" 안내만 두어 **본문이 없는 화면**이었다.
 *
 * `_renderBody` 의 identical 경로와 역할이 겹치지 않는다 — 그쪽은 `/diff` 스키마(`from`/`to`·
 * `comparable`·`truncated.from_source`)를 읽고, 이쪽은 `/source` 스키마(`version`·`viewable`·
 * `truncated.source`)를 읽는다. 표를 그리는 렌더러는 양쪽 모두 `_renderSource` 하나다.
 */
function _renderSourceBody(bodyEl, data, opts) {
  const o = opts || {};
  const anchor = o.keepScroll
    ? _captureScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"))
    : null;
  bodyEl.innerHTML = "";
  if (!data) return;

  // 호출부가 준 상태 안내를 본문보다 **먼저** 싣는다 — 비교 모달에서 같은 버전을 골라 원문이
  // 나온 화면은, 그 사실을 말하지 않으면 "비교가 고장 났다" 로 읽힌다(제목은 여전히 "버전
  // 비교" 다). 강등·절단 분기보다 앞에 두는 이유: 바이너리라도 "같은 버전을 골랐다" 는 사실은
  // 그대로 유효하다.
  if (o.preface) {
    const el = document.createElement("div");
    el.className = `attach-diff-notice ${o.prefaceTone || "is-same"}`;
    el.textContent = String(o.preface);
    bodyEl.appendChild(el);
  }

  // 볼 수 없는 형식(스프레드시트·PDF·이미지 등) — 메타로 강등해 답한다. 조용히 빈 화면을
  // 주면 사용자는 기능이 고장 났다고 읽는다.
  // (`source_unavailable` 은 서버가 **503** 으로 답하므로 `apiFetch` 가 throw 하고 호출부의
  //  catch 경로로 간다 — 여기서 그 사유를 분기하면 도달 불가 코드가 된다.)
  if (data.viewable === false) {
    const msg = document.createElement("div");
    msg.className = "attach-diff-notice";
    msg.textContent =
      "이 형식(스프레드시트·PDF·이미지 등)은 원문 보기를 지원하지 않습니다. 내려받아 확인하세요.";
    bodyEl.appendChild(msg);
    const v = data.version || {};
    const meta = document.createElement("table");
    meta.className = "attach-diff-meta";
    const rowOf = (label, val) =>
      `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(val)}</td></tr>`;
    meta.innerHTML = "<tbody>" +
      rowOf("작성 주체", v.created_by_role === "assistant" ? "AI 수정" : "사용자") +
      rowOf("크기", _fmtBytes(v.size)) +
      rowOf("등록 시각", v.created_at || "-") +
      rowOf("sha256", (v.sha256 || "").slice(0, 16) + "…") +
      "</tbody>";
    bodyEl.appendChild(meta);
    return;
  }

  // 절단 배너 — 무음 절단 금지(`/diff` 화면과 같은 계약).
  const tr = data.truncated || {};
  if (tr.source) {
    const capMB = ((data.caps?.source_bytes || 0) / 1048576).toFixed(0);
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-warn";
    el.textContent = `원본이 ${capMB}MB 를 넘어 앞부분만 표시했습니다 — 이후 내용은 보이지 않습니다.`;
    bodyEl.appendChild(el);
  }
  if (tr.rows) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-warn";
    el.textContent = `문서가 길어 앞쪽 ${Number(data.caps?.rows || 0)}행만 표시했습니다.`;
    bodyEl.appendChild(el);
  }

  const rows = Array.isArray(data.rows) ? data.rows : [];
  if (rows.length === 0) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice";
    el.textContent = "문서가 비어 있습니다.";
    bodyEl.appendChild(el);
    return;
  }
  const wrap = document.createElement("div");
  wrap.className = "attach-diff-splitwrap";
  const scroller = document.createElement("div");
  scroller.className = "attach-diff-scroller";
  // 렌더 결과에 따라 배너를 **뒤에 만들어 본문 앞에 끼운다** — 차단 건수·폴백 사유는
  // 렌더가 끝나야 알 수 있고, 사용자는 그 사실을 본문보다 먼저 봐야 한다.
  let mdNotice = null;
  _renderSource(scroller, data, {
    ...o,
    onMdRendered: (res) => { mdNotice = _mdBlockedNotice(res); },
    onMdFallback: () => {
      mdNotice = _mdFallbackNotice();
      // 컨트롤을 **화면과 일치**시킨다 — 체크는 켜져 있는데 원문 표가 보이면 사용자는 토글이
      // 고장 났다고 읽는다(codex 적대 리뷰 [P2]). 저장값은 건드리지 않는다: 이 전환은 사용자의
      // 선택이 아니라 실패로 인한 강등이므로 다음 열람에서 다시 시도한다.
      if (typeof o.onMdFallbackSync === "function") o.onMdFallbackSync();
    },
  });
  wrap.appendChild(scroller);
  if (mdNotice) bodyEl.appendChild(mdNotice);
  bodyEl.appendChild(wrap);
  _restoreScrollAnchor(scroller, anchor);
}

function _renderBody(bodyEl, data, mode, opts) {
  // 교체 **전** 현재 scroller 에서 앵커를 뜬다(요소가 사라지면 스크롤도 사라진다).
  const anchor = (opts && opts.keepScroll)
    ? _captureScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"))
    : null;
  bodyEl.innerHTML = "";
  _markContractWarned = false;   // 렌더마다 1회 경고

  // 비교 불가(바이너리) — 메타 비교로 강등해 답한다.
  if (data.comparable === false) {
    const msg = document.createElement("div");
    msg.className = "attach-diff-notice";
    msg.textContent = data.reason === "source_unavailable"
      ? "원본 파일을 읽을 수 없어 내용을 비교하지 못했습니다."
      : "이 형식(스프레드시트·PDF·이미지 등)은 줄 단위 비교를 지원하지 않습니다. 아래 메타 정보로 비교하세요.";
    bodyEl.appendChild(msg);
    const meta = document.createElement("table");
    meta.className = "attach-diff-meta";
    const rowOf = (label, a, b) =>
      `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(a)}</td><td>${escapeHtml(b)}</td></tr>`;
    meta.innerHTML =
      `<thead><tr><th></th><th>v${Number(data.from.version_number)}</th>` +
      `<th>v${Number(data.to.version_number)}</th></tr></thead><tbody>` +
      rowOf("작성 주체", data.from.created_by_role === "assistant" ? "AI 수정" : "사용자",
        data.to.created_by_role === "assistant" ? "AI 수정" : "사용자") +
      rowOf("크기", _fmtBytes(data.from.size), _fmtBytes(data.to.size)) +
      rowOf("등록 시각", data.from.created_at || "-", data.to.created_at || "-") +
      rowOf("sha256", (data.from.sha256 || "").slice(0, 16) + "…",
        (data.to.sha256 || "").slice(0, 16) + "…") +
      `</tbody>`;
    bodyEl.appendChild(meta);
    if (data.identical) {
      const same = document.createElement("div");
      same.className = "attach-diff-notice is-same";
      same.textContent = "두 버전의 내용 해시가 동일합니다.";
      bodyEl.appendChild(same);
    }
    return;
  }

  // 절단 배너 — 무음 절단 금지.
  const tr = data.truncated || {};
  const warnings = [];
  if (tr.from_source || tr.to_source) {
    const capMB = ((data.caps?.source_bytes || 0) / 1048576).toFixed(0);
    warnings.push(`원본이 ${capMB}MB 를 넘어 앞부분만 비교했습니다 — 이후 변경은 표시되지 않습니다.`);
  }
  if (tr.rows) {
    // 같은 절단인데 사유가 다르다 — identical 화면에서 "차이가 많아" 는 바로 아래 "차이 없음"
    // 배지와 정면으로 모순한다(§18.8 패널 2인 공통 지적). 행이 많은 이유를 상태에 맞게 말한다.
    warnings.push(data.identical
      ? `문서가 길어 앞쪽 ${Number(data.caps?.rows || 0)}행만 표시했습니다.`
      : `차이가 많아 앞쪽 ${Number(data.caps?.rows || 0)}행만 표시했습니다.`);
  }
  for (const w of warnings) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-warn";
    el.textContent = w;
    bodyEl.appendChild(el);
  }
  // 위 둘은 **내용** 절단이지만 이건 **정밀도** 절단이다 — 줄 단위 차이는 전부 나와 있고
  // 글자 단위 마크만 생략됐다. 무음으로 두면 마크 없는 줄을 "통째로 바뀐 줄" 로 오독하지만,
  // 같은 amber `is-warn` 으로 두면 "내용이 잘렸다" 와 같은 경보 강도로 읽힌다(§18.8 ux 패널
  // P2) — 별도 톤(`is-note`)으로 낮춘다. 사유도 "길어서" 가 아니다: 길이 컷·표시 분량 상한·
  // 조각화 판단이 섞여 있고, 같은 길이의 윗줄은 마크되는데 아랫줄만 안 되는 경우가 있어
  // 길이를 사유로 말하면 사용자가 화면과 어긋난 설명을 읽는다.
  if (tr.intraline) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-note";
    el.textContent = "일부 줄은 글자 단위 표시를 생략했습니다 — 줄 단위 차이는 모두 표시됩니다.";
    bodyEl.appendChild(el);
  }

  // 내용이 같으면 **원문을 출력**한다(사용자 요청 2026-08-07). 종전에는 "동일합니다" 한 줄만
  // 두고 return 했는데, 그 화면에는 본문이 없어 사용자가 "무엇이 같은지" 를 확인할 수단이
  // 없었다(서버 축약이 파일 전체를 gap 한 줄로 접기 때문 — `_build_version_diff_view` 참조).
  if (data.identical) {
    const same = document.createElement("div");
    const lines = Number(data.stats?.right_lines ?? data.stats?.left_lines ?? 0);
    const shown = Array.isArray(data.rows) ? data.rows.length : 0;
    const { clipped, shaDiff } = _identicalFlags(data);
    // 단정의 강도를 근거에 맞춘다 — "원문" 은 **전량을 봤을 때만** 쓸 수 있는 말이다.
    same.className = `attach-diff-notice ${clipped || shaDiff ? "is-warn" : "is-same"}`;
    same.textContent = lines <= 0
      ? "두 버전의 내용이 동일합니다 — 문서가 비어 있습니다."
      : clipped
        ? `비교한 범위에서 두 버전의 내용이 동일합니다 — 아래는 문서 앞부분 ${shown}줄입니다(전체는 더 길 수 있습니다).`
        : shaDiff
          ? `줄 내용은 같지만 두 파일이 완전히 동일하지는 않습니다(줄바꿈 방식·마지막 줄 개행 등). 아래는 v${Number(data.to?.version_number || 0)} 원문(${lines}줄)입니다.`
          : `두 버전의 내용이 동일합니다 — 아래는 문서 원문(${lines}줄)입니다.`;
    bodyEl.appendChild(same);
    if (!Array.isArray(data.rows) || data.rows.length === 0) return;
    const srcWrap = document.createElement("div");
    srcWrap.className = "attach-diff-splitwrap";
    const srcScroller = document.createElement("div");
    srcScroller.className = "attach-diff-scroller";
    // 배너는 렌더 결과를 알아야 만들 수 있으므로 **뒤에 만들어 본문 앞에 끼운다**
    // (원문 보기 모달과 같은 계약 — 차단 사실은 본문보다 먼저 읽혀야 한다).
    let mdNotice = null;
    _renderSource(srcScroller, data, {
      ...(opts || {}),
      // 배너 문구는 원문 보기 화면과 **같은 헬퍼**에서 온다 — 같은 사실을 두 화면이 다른 말로
      // 알리면 한쪽만 고쳐지는 방식으로 갈라진다.
      onMdRendered: (res) => { mdNotice = _mdBlockedNotice(res); },
      onMdFallback: () => {
        mdNotice = _mdFallbackNotice();
        // 원문 보기 모달과 같은 이유로 컨트롤을 화면과 일치시킨다(codex [P2]) — 저장값은 불변.
        if (typeof opts.onMdFallbackSync === "function") opts.onMdFallbackSync();
      },
    });
    if (mdNotice) bodyEl.appendChild(mdNotice);
    srcWrap.appendChild(srcScroller);
    bodyEl.appendChild(srcWrap);
    _restoreScrollAnchor(srcScroller, anchor);
    return;
  }

  // 2열은 중앙선 드래그 핸들을 얹기 위해 relative wrap 안에 둔다(핸들은 absolute).
  const wrap = document.createElement("div");
  wrap.className = "attach-diff-splitwrap";
  const scroller = document.createElement("div");
  scroller.className = "attach-diff-scroller";
  // 렌더-측 마크 예산(위 `MARK_RENDER_BUDGET` 주석 참조). 소진 여부는 렌더가 끝나야 알 수
  // 있으므로 배너를 **뒤에 만들어 표 앞에 끼운다** — 순서를 위 절단 배너들과 맞춘다.
  const markBudget = { left: MARK_RENDER_BUDGET, exhausted: false };
  const renderOptsWithBudget = { ...(opts || {}), markBudget };
  if (mode === "unified") _renderUnified(scroller, data, renderOptsWithBudget);
  else _renderSplit(scroller, data, renderOptsWithBudget);
  if (markBudget.exhausted && !tr.intraline) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-note";
    el.textContent = "변경 지점이 많아 아래쪽 일부 줄은 글자 단위 표시를 생략했습니다 — 줄 단위 차이는 모두 표시됩니다.";
    bodyEl.appendChild(el);
  }
  wrap.appendChild(scroller);
  bodyEl.appendChild(wrap);
  if (mode !== "unified" && opts && opts.onRatioChange) {
    _attachSplitHandle(wrap, scroller, opts);
  }
  _restoreScrollAnchor(scroller, anchor);
}

// 2열 중앙선 드래그 (사용자 요청 2026-08-07). 표는 `table-layout: fixed` + colgroup 이라
// 좌우 code `col` 의 width 를 비율로 다시 쓰면 즉시 반영된다 — 재요청·재렌더 없음.
// 핸들은 표 위에 absolute 로 띄우되 위치를 **경계의 실측 좌표**에서 얻는다(계산 추정 금지).
function _attachSplitHandle(wrap, scroller, opts) {
  const table = scroller.querySelector("table.attach-diff-table.is-split");
  if (!table) return;
  const cols = Array.from(table.querySelectorAll("col"));
  if (cols.length !== 4) return;
  const handle = document.createElement("div");
  handle.className = "attach-diff-splitter";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("aria-label", "좌우 비교 폭 조절");
  handle.tabIndex = 0;
  wrap.appendChild(handle);

  let ratio = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN,
    Number(opts.ratio) || SPLIT_RATIO_DEFAULT));

  const place = () => {
    // 경계 x = (우측 줄번호 셀의 좌변). 실측이라 ch·calc 해석과 무관하게 정확하다.
    const anyRow = table.querySelector("tr.attach-diff-row:not(.is-gap)");
    const cells = anyRow ? anyRow.querySelectorAll("td") : null;
    if (!cells || cells.length !== 4) { handle.style.display = "none"; return; }
    handle.style.display = "";
    const boundary = cells[2].getBoundingClientRect().left;
    const box = wrap.getBoundingClientRect();
    handle.style.left = `${Math.round(boundary - box.left)}px`;
  };

  const applyRatio = (r) => {
    ratio = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, r));
    _applySplitRatio(table, cols, ratio);
    place();
  };
  applyRatio(ratio);   // 저장된 비율을 첫 렌더에 반영(초기 col 폭은 auto)

  let dragging = false;
  const onMove = (clientX) => {
    const anyRow = table.querySelector("tr.attach-diff-row:not(.is-gap)");
    const cells = anyRow ? anyRow.querySelectorAll("td") : null;
    if (!cells || cells.length !== 4) return;
    const leftCodeStart = cells[1].getBoundingClientRect().left;
    const rightCodeEnd = cells[3].getBoundingClientRect().right;
    const span = rightCodeEnd - leftCodeStart;
    if (span <= 0) return;
    applyRatio((clientX - leftCodeStart) / span);
  };
  // 이동·종료 리스너는 **document 레벨**에 둔다(`setupAttachSidePanelResize` 와 동형).
  // 핸들에만 바인딩하면 포인터가 11px 핸들을 벗어나는 순간 이벤트가 끊겨 드래그가 죽는다 —
  // 헤드리스 기하 하네스 T10 이 이 결함을 초판에서 잡았다(핸들 위 pointerdown 은 성립했으나
  // 첫 이동(32px)에 이미 핸들 밖이라 비율이 그대로였다).
  const moveHandler = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchHandler = (e) => {
    if (dragging && e.touches && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); }
  };
  const end = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("is-dragging");
    document.removeEventListener("mousemove", moveHandler);
    document.removeEventListener("mouseup", end);
    document.removeEventListener("touchmove", touchHandler);
    document.removeEventListener("touchend", end);
    _writeSplitRatio(ratio);
    if (opts.onRatioChange) opts.onRatioChange(ratio);
  };
  const start = (e) => {
    dragging = true;
    handle.classList.add("is-dragging");
    document.addEventListener("mousemove", moveHandler);
    document.addEventListener("mouseup", end);
    document.addEventListener("touchmove", touchHandler, { passive: false });
    document.addEventListener("touchend", end);
    e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => { if (e.button === 0) start(e); });
  handle.addEventListener("touchstart", start, { passive: false });
  // 키보드 경로 — 포인터 없이도 조절 가능해야 한다(핸들이 focusable 인 이유).
  handle.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 0.1 : 0.02;
    if (e.key === "ArrowLeft") { applyRatio(ratio - step); }
    else if (e.key === "ArrowRight") { applyRatio(ratio + step); }
    else if (e.key === "Home") { applyRatio(SPLIT_RATIO_DEFAULT); }
    else { return; }
    e.preventDefault();
    _writeSplitRatio(ratio);
    if (opts.onRatioChange) opts.onRatioChange(ratio);
  });
  // 가로 스크롤·창 크기 변화에 핸들 위치를 따라붙인다.
  scroller.addEventListener("scroll", place);
  window.addEventListener("resize", () => applyRatio(ratio));
  requestAnimationFrame(() => applyRatio(ratio));
}

/**
 * 첨부 버전 비교 모달을 연다.
 *
 * @param {number|string} attachmentId 체인 내 아무 버전의 첨부 id (권한 기준 첨부)
 * @param {Array<object>} versions     `/api/attachments/{id}/versions` 응답의 versions (ASC)
 * @param {object} [preselect]         {from, to} 초기 선택 VersionNumber
 */
/**
 * @param {Array<object>} lineages  `/versions` 응답의 `lineages`(같은 파일명의 계보 head, 시간순).
 *   REQ-20260814-attach-version-tree-ui: 작성 주체별로 계보가 갈린 뒤로 "최신" 이 두 뜻이 됐다 —
 *   **계보 내 최신**(이 체인의 최고 버전)과 **시간순 최신**(같은 파일의 모든 계보 중 가장 나중).
 *   계보가 둘 이상이면 비교 기준을 고르는 토글을 띄운다. 하나뿐이면 종전과 동일한 화면이다.
 */
export function openAttachmentDiffModal(attachmentId, versions, preselect, lineages) {
  const list = Array.isArray(versions) ? [...versions] : [];
  // 계보 목록은 head 가 2개 이상일 때만 뜻이 있다(하나면 '시간순' 이 곧 '계보 내' 다).
  const lins = (Array.isArray(lineages) ? lineages : [])
    .filter((l) => Number(l?.head_attachment_id || 0) > 0);
  const hasLineageAxis = lins.length > 1;
  if (list.length < 2 && !hasLineageAxis) {
    showToast("비교할 버전이 2개 이상 필요합니다.", true);
    return;
  }
  list.sort((a, b) => Number(a.version_number || 1) - Number(b.version_number || 1));
  // §18.8 적대 리뷰 [P2]: 계보가 2개면 `list` 가 비어도 진입한다 — 마지막 원소를 무조건
  // 역참조하면 그 경로에서 예외로 죽는다. 계보 head 를 폴백으로 쓴다.
  const filename = String(
    list[list.length - 1]?.original_filename
    || lins[0]?.original_filename
    || "파일");

  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop attach-diff-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.setAttribute("aria-label", "첨부 버전 비교");
  backdrop.innerHTML =
    '<div class="share-mgr-panel attach-diff-panel">' +
    '  <div class="share-mgr-head">' +
    `    <h3 class="share-mgr-title"><span class="attach-diff-titleword">버전 비교</span> — <span class="attach-diff-fname"></span></h3>` +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="attach-diff-controls">' +
    // REQ-20260814-attach-version-tree-ui: 비교 축 토글. 계보가 하나뿐이면 숨긴다 —
    // 선택지가 하나인 토글은 화면만 복잡하게 하고 사용자에게 "뭔가 더 있나" 를 묻게 만든다.
    (hasLineageAxis
      ? '    <div class="attach-diff-axistoggle" role="group" aria-label="비교 기준">' +
        '      <button type="button" class="attach-diff-axis" data-axis="lineage">이 계보 안</button>' +
        '      <button type="button" class="attach-diff-axis" data-axis="time">계보 간(시간순)</button>' +
        '    </div>'
      : '') +
    '    <label class="attach-diff-ctl"><span>기준</span><select class="attach-diff-from"></select></label>' +
    '    <button type="button" class="attach-diff-swap" title="기준과 비교 대상 맞바꾸기" aria-label="기준과 비교 대상 맞바꾸기">⇄</button>' +
    '    <label class="attach-diff-ctl"><span>비교</span><select class="attach-diff-to"></select></label>' +
    '    <span class="attach-diff-stats" role="status" aria-live="polite"></span>' +
    '    <div class="attach-diff-viewtoggle" role="group" aria-label="보기 방식">' +
    '      <button type="button" class="attach-diff-mode" data-mode="split">좌우 2열</button>' +
    '      <button type="button" class="attach-diff-mode" data-mode="unified">단일열</button>' +
    '    </div>' +
    '    <label class="attach-diff-ctxtoggle"><input type="checkbox" class="attach-diff-ctxfull"><span>동일한 줄도 모두 보기</span></label>' +
    // 마크다운 렌더 토글 — 이 모달에서는 **내용이 동일해 원문을 출력하는 화면**에서만 뜻이 있다
    // (줄 대조 diff 는 렌더하면 대조 자체가 성립하지 않는다). 원문 보기 모달과 같은 저장 키를
    // 써서 한쪽에서 고른 보기 방식이 다른 쪽에도 적용된다 — 같은 파일이 두 화면에서 다르게
    // 보이지 않는다는 이 모듈의 계약.
    '    <label class="attach-source-mdtoggle" hidden><input type="checkbox" class="attach-source-md-cb">' +
    '<span>마크다운으로 보기</span></label>' +
    // 구문 하이라이트 토글 — **색이 실제로 칠해질 수 있을 때만** 표시한다(아래 `syncHlToggle`).
    // 옆의 맥락 토글과 같은 체크박스 관용구를 쓴다(같은 성격의 on/off 를 다른 위젯으로 두지 않는다).
    '    <label class="attach-diff-hltoggle" hidden><input type="checkbox" class="attach-diff-hl">' +
    '<span class="attach-diff-hl-label"></span></label>' +
    '  </div>' +
    '  <div class="attach-diff-body"></div>' +
    '</div>';
  backdrop.querySelector(".attach-diff-fname").textContent = filename;

  const close = () => {
    if (backdrop.parentNode) document.body.removeChild(backdrop);
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);

  const fromSel = backdrop.querySelector(".attach-diff-from");
  const toSel = backdrop.querySelector(".attach-diff-to");
  const statsEl = backdrop.querySelector(".attach-diff-stats");
  const bodyEl = backdrop.querySelector(".attach-diff-body");
  const ctxCb = backdrop.querySelector(".attach-diff-ctxfull");
  const modeBtns = Array.from(backdrop.querySelectorAll(".attach-diff-mode"));

  // 비교 축: 'lineage' = 이 체인의 버전 번호 / 'time' = 같은 파일명 계보 head 들(시간순).
  // 축에 따라 **`<select>` 값의 의미가 달라진다** — 전자는 version_number, 후자는 attachment_id.
  // 요청 파라미터도 그에 맞춰 갈리므로(`from_version` vs `from_attachment_id`) 값 해석은
  // `_diffParams` 한 곳으로 모은다(세 갈래로 흩으면 축을 바꿀 때 한 곳이 조용히 남는다).
  let axis = "lineage";

  const _lineageLabel = (l) => {
    const who = l.is_assistant_generated ? "AI 수정본" : "사용자 업로드";
    const v = Number(l.version_number || 1);
    const mine = l.is_current_lineage ? " · 현재" : "";
    return `${who} v${v}${mine}`;
  };

  const _fillSelects = () => {
    for (const sel of [fromSel, toSel]) sel.innerHTML = "";
    if (axis === "time") {
      // 시간순: 오래된 것 → 최신 순으로 놓아 좌(기준)·우(비교) 가 자연스럽게 과거→현재가 된다.
      // 서버는 최신 우선으로 주므로 뒤집는다.
      for (const l of [...lins].reverse()) {
        for (const sel of [fromSel, toSel]) {
          const opt = document.createElement("option");
          opt.value = String(l.head_attachment_id);
          opt.textContent = _lineageLabel(l);
          sel.appendChild(opt);
        }
      }
      const ids = [...lins].reverse().map((l) => String(l.head_attachment_id));
      fromSel.value = ids[ids.length - 2] ?? ids[0];
      toSel.value = ids[ids.length - 1];
      return;
    }
    for (const v of list) {
      const n = Number(v.version_number || 1);
      for (const sel of [fromSel, toSel]) {
        const opt = document.createElement("option");
        opt.value = String(n);
        opt.textContent = _versionLabel(v);
        sel.appendChild(opt);
      }
    }
    // 기본 선택 = 직전 ↔ 최신 (사용자가 가장 자주 보는 쌍). preselect 로 덮어쓸 수 있다.
    const defFrom = Number(preselect?.from ?? list[list.length - 2]?.version_number ?? 1);
    const defTo = Number(preselect?.to ?? list[list.length - 1]?.version_number ?? 1);
    fromSel.value = String(defFrom);
    toSel.value = String(defTo);
  };

  /** 현재 축에 맞는 diff 쿼리 파라미터. 축이 바뀌어도 요청 형식이 한 곳에서만 결정된다. */
  const _diffParams = (fromVal, toVal) => (axis === "time"
    ? { from_attachment_id: String(fromVal), to_attachment_id: String(toVal) }
    : { from_version: String(fromVal), to_version: String(toVal) });

  // 계보가 하나뿐이면 축 자체가 없으므로 `list` 가 2개 미만일 수 없다(위 guard).
  if (hasLineageAxis && list.length < 2) axis = "time";
  _fillSelects();

  let mode = _readViewMode();
  ctxCb.checked = _readContextFull();
  const syncModeButtons = () => {
    for (const b of modeBtns) b.classList.toggle("is-active", b.dataset.mode === mode);
  };
  syncModeButtons();

  // 언어 판정은 **파일명 한 번**으로 끝난다 — 버전 체인은 같은 파일의 이력이므로 유형이 바뀔 수
  // 없다(파일명·sha256 대조로 체인을 잇는 구조). 행마다 재판정하면 6,000행 표에서 낭비다.
  const detectedLang = detectCodeLanguage(filename);
  const hlWrap = backdrop.querySelector(".attach-diff-hltoggle");
  const hlCb = backdrop.querySelector(".attach-diff-hl");
  const hlLabel = backdrop.querySelector(".attach-diff-hl-label");
  let hlOn = _readHighlightOn();
  hlCb.checked = hlOn;
  // 노출 판정은 **파일명이 아니라 렌더 결과**에 걸린다. 파일명만 보면 `logo.svg`·`rows.tsv` 처럼
  // 서버가 줄 비교를 거부한(`comparable: false`) 첨부, 내용이 동일한 쌍, 조회 실패, 같은 버전 두 개
  // 선택 — 즉 **칠할 본문이 아예 없는 화면**에서도 "TSV 구문 색" 이 켜진 채 떠 있었다(§18.8 ux P1
  // 실측 6종). 누르면 아무 일도 일어나지 않으니 사용자는 토글이 고장 났다고 읽는다. 이 모듈이
  // 스스로 금지한 거짓 어포던스와 같은 결함이 다른 축(파일명은 지원인데 본문이 없음)에서 난 것.
  // (내용 동일 = 원문 뷰도 **칠할 본문이 있는 화면**이다 — 원문 출력이 생긴 뒤로는
  //  `identical` 을 제외하지 않는다. 제외한 채 두면 원문만 무색으로 남아, 같은 파일이
  //  diff 화면에서는 색이 있고 원문 화면에서는 없는 비일관이 된다.)
  const mdWrap = backdrop.querySelector(".attach-source-mdtoggle");
  const mdCb = backdrop.querySelector(".attach-source-md-cb");
  let mdOn = _readMdRenderOn();
  mdCb.checked = mdOn;
  // 이 모달의 마크다운 렌더는 **identical(원문 출력) 화면 한정**이다 — 줄 대조 diff 를 렌더하면
  // 어느 줄이 바뀌었는지가 사라진다. 그래서 노출 판정에 `identical` 이 들어간다(하이라이트
  // 토글이 `identical` 을 제외하지 **않는** 것과 정반대이며, 이 비대칭은 의도다).
  // 판정면은 모듈 공용 `_bodyState` 다 — 같은 화면을 두 모달이 다르게 판정하지 않도록
  // (원문 보기 모달이 비교를 수행하게 되면서 사본이 세 벌이 될 자리였다).
  const mdRenderable = (data, kind) =>
    _isMarkdownFile(filename) && _bodyState(data, kind || "diff").sourceView;
  const syncHlToggle = (data, kind) => {
    const md = mdRenderable(data, kind);
    mdWrap.hidden = !md;
    if (md) mdCb.checked = mdOn;
    // 렌더된 문서에는 칠할 원문 줄이 없다 → `md && mdOn` 이면 구문 색 토글을 숨긴다.
    const paintable = Boolean(detectedLang) && _bodyState(data, kind || "diff").hasBody
      && !(md && mdOn);
    hlWrap.hidden = !paintable;
    if (!paintable) return;
    hlLabel.textContent = `${codeLanguageLabel(detectedLang)} 구문 색`;
    hlCb.checked = hlOn;
  };
  syncHlToggle(null);   // 응답 도착 전에는 숨김 — 칠할 수 있는지 아직 모른다

  // 보기 방식(2열/단일열)·맥락 토글은 **diff 표가 실제로 그려질 때만** 뜻이 있다.
  //
  // 판정면은 `syncHlToggle` 과 **동일**하다 — 초판은 `identical` 하나만 봤는데, 그러면 바로 옆
  // 하이라이트 토글은 사라지는데 이 둘은 남는 화면(바이너리 메타 비교·같은 버전 두 개 선택·
  // 조회 실패)이 생겨 사용자에게는 규칙 없는 컨트롤 바가 된다(§18.8 패널 2인 공통 지적).
  // 같은 인자(`null`)가 두 함수에서 반대 뜻을 갖던 것도 사고였다.
  //
  // 숨김이 아니라 **비활성**인 이유: 이 컨트롤들은 모달 안에서 위치를 외우는 primary 컨트롤이고,
  // `.attach-diff-stats{margin-left:auto}` 때문에 사라지면 컨트롤 바가 통째로 흔들린다(버전 쌍을
  // 오가며 훑을 때 누르려던 버튼이 응답 도착 순간 이동). 비활성은 레이아웃을 고정하면서
  // "지금은 쓸 수 없다" 는 사실까지 전달한다 — 거짓 어포던스를 없애는 목적에도 부합한다.
  // (반면 하이라이트 토글은 라벨 자체가 `<유형> 구문 색` 이라 유형 판정 없이는 문구가 성립하지
  //  않는다. 그쪽이 숨김인 것은 그 이유이며, 이 비대칭은 의도다.)
  const viewToggleEl = backdrop.querySelector(".attach-diff-viewtoggle");
  const ctxToggleEl = backdrop.querySelector(".attach-diff-ctxtoggle");
  const syncDiffOnlyControls = (data, kind) => {
    const { hasDiff } = _bodyState(data, kind || "diff");
    const why = hasDiff ? "" : "비교할 차이가 없는 화면이라 표시 방식을 바꿀 대상이 없습니다.";
    for (const b of modeBtns) { b.disabled = !hasDiff; b.title = why; }
    ctxCb.disabled = !hasDiff;
    ctxToggleEl.title = why;
    viewToggleEl.classList.toggle("is-disabled", !hasDiff);
    ctxToggleEl.classList.toggle("is-disabled", !hasDiff);
  };
  syncDiffOnlyControls(null);   // 응답 전에는 비활성 — `syncHlToggle(null)` 과 같은 뜻

  let lastData = null;
  // 같은 버전 두 개를 고른 화면의 `/source` 응답. diff 응답과 **스키마가 달라** 한 변수에
  // 섞지 않는다(`viewable` vs `comparable` · `version` vs `from`/`to` · `truncated.source` vs
  // `truncated.from_source`). 판정·렌더가 어느 스키마를 읽는지는 `viewKind` 가 정한다.
  let srcData = null;
  let viewKind = "diff";   // "diff" | "source"
  const curData = () => (viewKind === "source" ? srcData : lastData);
  let reqSeq = 0;
  let ratio = _readSplitRatio();
  // gap 국소 전개용 전체 맥락 캐시 — 현재 선택 쌍에 대해 1회만 받아 재사용한다.
  let fullRowsCache = null;
  let fullRowsKey = "";

  // 축을 키에 넣는다 — 계보 안 v1↔v2 와 시간순 id1↔id2 가 우연히 같은 문자열이 될 수 있고,
  // 그러면 축을 바꿔도 이전 축의 전체-펼침 캐시를 그대로 쓴다(§18.8 적대 리뷰 [P2]).
  const pairKey = () => `${axis}:${fromSel.value}:${toSel.value}`;

  // 렌더 옵션 — rows 는 매 렌더 시점의 표시 행(전개 결과 포함).
  const renderOpts = () => ({
    ratio,
    rows: (curData() && curData().rows) || [],
    // 하이라이트가 꺼져 있으면 lang 을 아예 넘기지 않는다 — 렌더러가 종전 평문 경로를 타므로
    // "끔" 이 곧 이전 동작과 동일함이 구조로 보장된다(끈 상태에 잔여 span 이 남지 않는다).
    lang: hlOn ? detectedLang : null,
    // identical 원문 화면(또는 같은-버전 원문 화면)에서만 참 — `_renderBody` 의 diff 경로는
    // 이 값을 읽지 않는다.
    md: mdOn && mdRenderable(curData(), viewKind),
    onMdFallbackSync: () => {
      mdCb.checked = false;
      hlWrap.hidden = !detectedLang;
      if (detectedLang) {
        hlLabel.textContent = `${codeLanguageLabel(detectedLang)} 구문 색`;
        hlCb.checked = hlOn;
      }
    },
    onRatioChange: (r) => { ratio = r; },
    // "동일한 줄도 모두 보기" 가 켜져 있으면 이미 전부 보이므로 전개 버튼을 달지 않는다.
    onExpandGap: ctxCb.checked ? null : expandGap,
    // 같은-버전 원문 화면임을 알리는 배너. 재렌더(토글 조작)에도 유지되어야 하므로 렌더
    // 옵션에 담는다 — 한 번만 append 하면 다음 재렌더에서 조용히 사라진다.
    preface: viewKind === "source"
      ? `같은 버전을 선택했습니다 — v${Number(fromSel.value)} 원문입니다.`
      : null,
  });

  // 재렌더는 **기본적으로 스크롤을 보존**한다. 새 비교(버전 쌍 변경)만 최상단으로 돌아간다 —
  // 그건 다른 내용이므로 위치 보존이 오히려 혼란이다.
  const rerender = (keepScroll = true) => {
    if (viewKind === "source") {
      // 같은 버전 두 개를 고른 화면 — 원문 보기 모달과 **같은 렌더러**를 쓴다.
      if (srcData) _renderSourceBody(bodyEl, srcData, { ...renderOpts(), keepScroll });
      return;
    }
    if (lastData) _renderBody(bodyEl, lastData, mode, { ...renderOpts(), keepScroll });
  };

  // gap 한 칸만 국소 전개. 서버가 gap 에 실어 준 줄번호 범위로 전체 맥락 응답에서 해당
  // `equal` 행들을 골라 그 자리에 끼워 넣는다 — 축약 로직을 프론트에 재구현하지 않는다
  // (그러면 서버·클라이언트 두 구현이 갈라져 같은 쌍에 다른 화면이 나온다).
  async function expandGap(gapRow, btn) {
    const key = pairKey();
    if (btn) { btn.disabled = true; btn.textContent = "펼치는 중…"; }
    try {
      if (fullRowsCache === null || fullRowsKey !== key) {
        const axisAtRequest = axis;
        const qs = new URLSearchParams({
          ..._diffParams(fromSel.value, toSel.value), context: "full" });
        const full = await apiFetch(
          `/api/attachments/${encodeURIComponent(attachmentId)}/diff?${qs.toString()}`);
        // §18.8 적대 리뷰 [P2]: 이 요청에는 `reqSeq` 가 없다. 축을 바꾸고 나서 이전 축의 응답이
        // 도착하면 **다른 쌍의 본문**으로 캐시를 채운다. 응답 시점에 축·선택이 그대로인지 다시 본다.
        if (axisAtRequest !== axis || key !== `${axis}:${fromSel.value}:${toSel.value}`) return;
        fullRowsCache = Array.isArray(full?.rows) ? full.rows : [];
        fullRowsKey = key;
      }
      const lf = Number(gapRow.left_from), lt = Number(gapRow.left_to);
      const rf = Number(gapRow.right_from), rt = Number(gapRow.right_to);
      const hidden = fullRowsCache.filter((r) => {
        if (r.type === "gap") return false;
        if (Number.isFinite(lf) && r.left_no != null) return r.left_no >= lf && r.left_no <= lt;
        if (Number.isFinite(rf) && r.right_no != null) return r.right_no >= rf && r.right_no <= rt;
        return false;
      });
      const idx = (lastData.rows || []).indexOf(gapRow);
      if (idx < 0 || hidden.length === 0) {
        if (btn) { btn.disabled = false; btn.textContent = "펼칠 내용을 찾지 못했습니다"; }
        return;
      }
      lastData.rows.splice(idx, 1, ...hidden);
      rerender();
    } catch (e) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = `⋯ 펼치기 실패 — 다시 시도 (${Number(gapRow.skipped || 0)}줄)`;
      }
    }
  }

  const load = async (loadOpts) => {
    const keepScroll = Boolean(loadOpts && loadOpts.keepScroll);
    // 재요청 전에 앵커를 떠 둔다 — 응답이 오면 본문이 통째로 교체된다.
    const pendingAnchor = keepScroll
      ? _captureScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"))
      : null;
    const from = Number(fromSel.value);
    const to = Number(toSel.value);
    fullRowsCache = null;   // 쌍이 바뀌면 전개 캐시 무효
    if (from === to) {
      // 같은 버전 두 개 = 비교할 것이 없는 선택. 종전에는 "서로 다른 두 버전을 선택하세요"
      // 안내만 두어 **본문이 0 인 화면**이었다 — 사용자가 확인하려던 내용이 아무것도 없다.
      // 그 버전의 **원문을 그대로 출력**한다(사용자 요청 2026-08-13: "같은 버전이나 / 버전 간
      // 변경사항이 없는 경우에는 문서 원문을 그대로 출력"). 내용이 동일한 쌍(`identical`)이
      // 이미 원문을 출력하므로, 같은 버전만 빈 화면으로 남는 비대칭이었다.
      //
      // `/diff` 에 `from==to` 를 허용하지 **않는다** — 그 400 은 존재 여부 oracle 방지 계약의
      // 일부다. 각 버전이 자기 id 를 가지므로 그 id 의 `/source` 를 부르면 된다(원문 보기
      // 모달이 쓰는 것과 같은 엔드포인트·같은 게이트).
      viewKind = "source";
      lastData = null;
      // §18.8 적대 리뷰 [P2]: 축에 따라 `from` 의 **의미가 다르다**. 시간순 축에서는 그 값이 이미
      // attachment_id 이므로 version_number 로 체인을 뒤지면 못 찾고 "원문을 찾지 못했습니다" 가
      // 뜬다(값은 멀쩡한데 화면만 실패하는 종류).
      const vid = axis === "time"
        ? Number(from || 0)
        : Number(list.find((v) => Number(v.version_number || 1) === from)?.id || 0);
      const seqSrc = ++reqSeq;
      if (!vid) {
        // 체인 payload 에 id 가 없는 경우(구버전 응답 형식) — 조용히 빈 화면을 주지 않는다.
        srcData = null;
        statsEl.textContent = "";
        bodyEl.innerHTML =
          '<div class="attach-diff-notice is-warn">이 버전의 원문을 찾지 못했습니다.</div>';
        syncHlToggle(null, "source");
        syncDiffOnlyControls(null, "source");
        return;
      }
      statsEl.textContent = "불러오는 중…";
      if (!keepScroll) bodyEl.innerHTML = '<div class="attach-diff-notice">불러오는 중…</div>';
      try {
        const data = await apiFetch(`/api/attachments/${encodeURIComponent(vid)}/source`);
        if (seqSrc !== reqSeq) return;   // 늦게 도착한 응답이 최신 선택을 덮지 않게
        srcData = data;
        syncHlToggle(data, "source");
        syncDiffOnlyControls(data, "source");
        statsEl.textContent = _sourceStatsText(data);
        if (keepScroll && pendingAnchor) {
          _renderSourceBody(bodyEl, data, { ...renderOpts(), keepScroll: false });
          _restoreScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"), pendingAnchor);
        } else {
          rerender(false);
        }
      } catch (e) {
        if (seqSrc !== reqSeq) return;
        srcData = null;
        syncHlToggle(null, "source");
        syncDiffOnlyControls(null, "source");
        statsEl.textContent = "";
        bodyEl.innerHTML = `<div class="attach-diff-notice is-warn">${escapeHtml(e?.message || "원문을 불러오지 못했습니다.")}</div>`;
      }
      return;
    }
    viewKind = "diff";
    srcData = null;
    const seq = ++reqSeq;
    statsEl.textContent = "비교 중…";
    // 보존 요청이면 기존 표를 남겨 둔다 — 지우면 '불러오는 중' 사이에 화면이 튄다.
    if (!keepScroll) bodyEl.innerHTML = '<div class="attach-diff-notice">불러오는 중…</div>';
    const qs = new URLSearchParams(_diffParams(from, to));
    if (ctxCb.checked) qs.set("context", "full");
    try {
      const data = await apiFetch(`/api/attachments/${encodeURIComponent(attachmentId)}/diff?${qs.toString()}`);
      if (seq !== reqSeq) return;   // 늦게 도착한 응답이 최신 선택을 덮지 않게
      lastData = data;
      syncHlToggle(data);   // 칠할 본문이 실제로 왔을 때만 토글이 보인다
      syncDiffOnlyControls(data);
      // 배지도 배너와 **같은 판정**(`_identicalFlags`)을 쓴다 — 한 화면의 두 요약이 서로
      // 반박하면 사용자는 어느 쪽을 믿을지 판단할 수 없다. 문구 정본은 `_diffStatsText`
      // (원문 보기 모달이 비교를 수행하게 되면서 두 모달이 같은 배지를 쓴다).
      statsEl.textContent = _diffStatsText(data);
      if (keepScroll && pendingAnchor) {
        _renderBody(bodyEl, data, mode, { ...renderOpts(), keepScroll: false });
        _restoreScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"), pendingAnchor);
      } else {
        rerender(false);
      }
    } catch (e) {
      if (seq !== reqSeq) return;
      lastData = null;
      syncHlToggle(null);
      syncDiffOnlyControls(null);
      statsEl.textContent = "";
      bodyEl.innerHTML = `<div class="attach-diff-notice is-warn">${escapeHtml(e?.message || "비교에 실패했습니다.")}</div>`;
    }
  };

  fromSel.addEventListener("change", load);
  toSel.addEventListener("change", load);

  // REQ-20260814-attach-version-tree-ui: 축 전환. 옵션 세트와 요청 파라미터가 함께 바뀌므로
  // 전환 시 **캐시를 버린다** — 이전 축의 전체-펼침 결과를 재사용하면 다른 쌍의 본문이 뜬다.
  const axisBtns = Array.from(backdrop.querySelectorAll(".attach-diff-axis"));
  // REQ-20260828-attach-lineage-ui: 제목이 **지금 무엇을 견주는지** 말한다.
  //
  // 종전에는 축과 무관하게 "버전 비교" 로 고정이었다. 계보 간 비교에서 그 문구는 틀린다 —
  // 견주는 대상이 한 줄기의 버전이 아니라 **다른 계보**다. 사용자가 계보를 못 보는 것이
  // 이번 제보의 본질이고, 제목이 계보를 감추면 같은 결함이 모달에서 반복된다.
  const titleWordEl = backdrop.querySelector(".attach-diff-titleword");
  const syncAxisButtons = () => {
    for (const b of axisBtns) b.classList.toggle("is-active", b.dataset.axis === axis);
    const _word = axis === "time" ? "계보 비교" : "버전 비교";
    if (titleWordEl) titleWordEl.textContent = _word;
    // 접근성 이름도 함께 바꾼다(codex P2) — 눈에 보이는 제목만 고치면 스크린리더에는 계속
    // "첨부 버전 비교" 가 읽혀, 계보 축에서 **틀린 제목**이 그쪽에만 남는다.
    backdrop.setAttribute("aria-label", `첨부 ${_word}`);
  };
  syncAxisButtons();
  for (const b of axisBtns) {
    b.addEventListener("click", () => {
      const next = b.dataset.axis === "time" ? "time" : "lineage";
      if (next === axis) return;
      axis = next;
      syncAxisButtons();
      _fillSelects();
      fullRowsCache = null;
      fullRowsKey = "";
      load();
    });
  }
  ctxCb.addEventListener("change", () => {
    _writeContextFull(ctxCb.checked);
    load({ keepScroll: true });   // 같은 비교의 표시 범위만 바뀐다 — 보던 위치를 유지
  });
  backdrop.querySelector(".attach-diff-swap").addEventListener("click", () => {
    const a = fromSel.value;
    fromSel.value = toSel.value;
    toSel.value = a;
    load();
  });
  for (const b of modeBtns) {
    b.addEventListener("click", () => {
      mode = b.dataset.mode === "unified" ? "unified" : "split";
      _writeViewMode(mode);
      syncModeButtons();
      // 렌더만 다시 — 같은 응답의 다른 표현이므로 재요청하지 않는다.
      rerender();
    });
  }
  // 하이라이트 on/off — 같은 응답의 표시 방식만 바뀌므로 재요청 없이 재렌더하고,
  // 보고 있던 줄을 유지한다(스크롤 보존 계약은 다른 토글들과 동일해야 한다).
  hlCb.addEventListener("change", () => {
    hlOn = hlCb.checked;
    _writeHighlightOn(hlOn);
    rerender();
  });

  // 마크다운 ↔ 원문 전환(identical 화면 한정). 원문 보기 모달과 **같은 저장 키**라 한쪽에서
  // 고른 방식이 다른 쪽에도 적용된다.
  mdCb.addEventListener("change", () => {
    mdOn = mdCb.checked;
    _writeMdRenderOn(mdOn);
    syncHlToggle(curData(), viewKind);   // 구문 색 토글 노출이 md 상태에 종속된다
    rerender();
  });

  load();
}

/**
 * 첨부 **원문 보기** 모달을 연다 — 그리고 그 화면에서 **버전 간 비교까지** 수행한다
 * (REQ-20260807T-attach-source-view + REQ-20260813-attach-source-compare).
 *
 * 사용자 요청(2026-08-07): "별도로 추가된 버전이 없는 첨부파일 또한, 클릭했을 때 문서 원문이
 * 출력되도록 구성해주세요."
 * 사용자 요청(2026-08-13): "첨부파일의 '문서 원문' 화면에서도 버전 간 비교를 수행할 수 있도록
 * 구성해주세요. 추가로, 같은 버전이나 / 버전 간 변경사항이 없는 경우에는 문서 원문을 그대로
 * 출력하도록 구성해주세요."
 *
 * 화면은 두 상태를 갖는다. 기본은 **이 버전의 원문**이고, 컨트롤 바의 `비교 기준` 선택기로
 * **같은 모달 안에서** 비교로 전환한다 — 다른 창을 띄우지 않는다. 원문을 읽다가 "이게 직전
 * 버전과 무엇이 다른가" 로 넘어가는 것은 하나의 흐름이고, 그 사이에 모달이 갈리면 보던 위치와
 * 켜 둔 토글이 리셋된다.
 *
 * **되돌아오는 조건 두 가지**(사용자 요청 2026-08-13 후단):
 *   - 기준으로 **이 버전 자신**을 고르면 → 요청 없이 이미 받아 둔 원문을 다시 그린다.
 *   - 고른 쌍의 **내용이 같으면**(`identical`) → `_renderBody` 가 원문을 그린다(선행 계약).
 * 두 경우 모두 "비교할 것이 없다" 는 같은 사실이므로 같은 화면(원문)으로 수렴한다.
 *
 * **버전 목록은 `/source` 응답이 함께 준다**(`versions`) — `/versions` 를 따로 부르지 않는
 * 이유는 서버 docstring 에 있다(왕복 1회 유지 + presign 비용 0). 체인이 1개면 선택기를
 * **숨긴다**: 고를 것이 하나뿐인 select 는 조작할 수 없는 컨트롤이고, 이 모듈이 금지한 거짓
 * 어포던스다.
 *
 * 유지되는 종전 계약: `?version=` 쿼리는 없다(각 버전이 자기 id 를 가지므로 식별 경로를 둘로
 * 만들지 않는다). 비교는 **버전 번호**로 `/diff` 에 넘기고, 방향은 항상 **오래된 → 새로운**
 * 으로 정규화한다(문서 이력은 시간 순으로 읽는다 — 기준으로 더 새 버전을 골랐다고 화면의
 * 좌우가 뒤집히면 같은 쌍이 두 방향으로 보인다).
 *
 * @param {number|string} attachmentId  첨부(=버전) id — 권한·대상 기준
 * @param {object} [opts]
 * @param {string} [opts.filename]      제목·언어 판정용 파일명(미지정 시 응답에서 취함)
 */
export function openAttachmentSourceModal(attachmentId, opts) {
  const o = opts || {};

  // 열기 전 포커스를 기억한다 — 이 모달은 **키보드로도 열린다**(목록의 파일명 버튼). 닫을 때
  // 돌려주지 않으면 사용자가 문서 맨 앞으로 튕긴다(첨부 관리 모달 `_openAttachDeleteModal` 과 동형).
  const opener = document.activeElement;
  const uid = `attach-source-${Math.random().toString(36).slice(2, 9)}`;

  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop attach-diff-backdrop attach-source-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  // 정적 `aria-label` 대신 **제목을 이름으로** 쓴다 — 파일명·절단 여부가 이름에 실린다.
  backdrop.setAttribute("aria-labelledby", `${uid}-title`);
  backdrop.innerHTML =
    '<div class="share-mgr-panel attach-diff-panel">' +
    '  <div class="share-mgr-head">' +
    `    <h3 class="share-mgr-title" id="${uid}-title"><span class="attach-source-titleword">문서 원문</span>` +
    ' — <span class="attach-diff-fname"></span><span class="attach-source-vertag"></span></h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="attach-diff-controls">' +
    // 비교 기준 선택기 — 체인에 다른 버전이 있을 때만 보인다(`fillCompareSelect`). 관용구·클래스는
    // 비교 모달의 `기준`/`비교` select 와 같다(`.attach-diff-ctl`) — 같은 성격의 컨트롤을 두
    // 화면에서 다른 모양으로 두지 않는다.
    '    <label class="attach-source-cmpctl attach-diff-ctl" hidden><span>비교 기준</span>' +
    '<select class="attach-source-cmp"></select></label>' +
    '    <span class="attach-diff-stats" role="status" aria-live="polite"></span>' +
    // 보기 방식·맥락 토글은 **비교 상태에서만** 나타난다. 비교 모달은 이 둘을 상시 노출하고
    // 비활성으로 두는데(그 모달에서는 diff 가 기본 화면이라 위치를 외운다), 이 모달의 기본
    // 화면은 원문이므로 상시 노출하면 대부분의 시간에 쓸 수 없는 컨트롤이 떠 있게 된다.
    '    <div class="attach-diff-viewtoggle" role="group" aria-label="보기 방식" hidden>' +
    '      <button type="button" class="attach-diff-mode" data-mode="split">좌우 2열</button>' +
    '      <button type="button" class="attach-diff-mode" data-mode="unified">단일열</button>' +
    '    </div>' +
    '    <label class="attach-diff-ctxtoggle" hidden><input type="checkbox" class="attach-diff-ctxfull">' +
    '<span>동일한 줄도 모두 보기</span></label>' +
    // 마크다운 렌더 토글 — `.md` 첨부에서만 보인다(사용자 요청 2026-08-12). 기본 켬이며
    // 끄면 종전의 줄번호+원문 표로 돌아간다. 구문 색 토글과 **동시에 보이지 않는다**:
    // 렌더된 문서에는 칠할 원문 줄이 없어 그 토글이 아무 일도 하지 않는 거짓 어포던스가 된다.
    '    <label class="attach-source-mdtoggle" hidden><input type="checkbox" class="attach-source-md-cb">' +
    '<span>마크다운으로 보기</span></label>' +
    // 구문 색 토글은 비교 모달과 **같은 관용구·같은 저장 키**다 — 한쪽에서 끈 사용자가 다른
    // 쪽에서 다시 켜야 한다면 그건 두 기능이 아니라 한 기능의 일관성 결함이다.
    '    <label class="attach-diff-hltoggle" hidden><input type="checkbox" class="attach-diff-hl">' +
    '<span class="attach-diff-hl-label"></span></label>' +
    '  </div>' +
    '  <div class="attach-diff-body"></div>' +
    '</div>';

  const close = () => {
    if (backdrop.parentNode) document.body.removeChild(backdrop);
    document.removeEventListener("keydown", onKey);
    // 열어 준 요소로 포커스 복귀(사라졌으면 조용히 포기 — 목록이 재렌더됐을 수 있다).
    try { if (opener && document.contains(opener)) opener.focus(); } catch (e) { /* detached */ }
  };
  const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  try { backdrop.querySelector(".share-mgr-close").focus(); } catch (e) { /* jsdom */ }

  const titleWordEl = backdrop.querySelector(".attach-source-titleword");
  const verTagEl = backdrop.querySelector(".attach-source-vertag");
  const controlsEl = backdrop.querySelector(".attach-diff-controls");
  const fnameEl = backdrop.querySelector(".attach-diff-fname");
  const statsEl = backdrop.querySelector(".attach-diff-stats");
  const bodyEl = backdrop.querySelector(".attach-diff-body");
  const hlWrap = backdrop.querySelector(".attach-diff-hltoggle");
  const hlCb = backdrop.querySelector(".attach-diff-hl");
  const hlLabel = backdrop.querySelector(".attach-diff-hl-label");
  const mdWrap = backdrop.querySelector(".attach-source-mdtoggle");
  const mdCb = backdrop.querySelector(".attach-source-md-cb");
  const cmpWrap = backdrop.querySelector(".attach-source-cmpctl");
  const cmpSel = backdrop.querySelector(".attach-source-cmp");
  const viewToggleEl = backdrop.querySelector(".attach-diff-viewtoggle");
  const ctxToggleEl = backdrop.querySelector(".attach-diff-ctxtoggle");
  const ctxCb = backdrop.querySelector(".attach-diff-ctxfull");
  const modeBtns = Array.from(backdrop.querySelectorAll(".attach-diff-mode"));

  fnameEl.textContent = String(o.filename || "파일");
  let detectedLang = detectCodeLanguage(fnameEl.textContent);
  let hlOn = _readHighlightOn();
  hlCb.checked = hlOn;
  let mdOn = _readMdRenderOn();
  mdCb.checked = mdOn;
  // 보기 방식·맥락·중앙선 비율은 비교 모달과 **같은 저장 키**를 쓴다 — 한 화면에서 고른 표시
  // 방식이 다른 화면에서 리셋되면 두 기능처럼 보인다.
  let mode = _readViewMode();
  let ratio = _readSplitRatio();
  ctxCb.checked = _readContextFull();
  const syncModeButtons = () => {
    for (const b of modeBtns) b.classList.toggle("is-active", b.dataset.mode === mode);
  };
  syncModeButtons();

  // 두 화면의 응답을 **각자의 변수**에 둔다 — 스키마가 다르므로(`viewable` vs `comparable`,
  // `version` vs `from`/`to`) 한 변수에 섞으면 판정이 어느 스키마를 보는지 알 수 없게 된다.
  let srcData = null;     // `/source` — 이 버전의 원문(정본, 재요청 없이 재사용)
  let diffData = null;    // `/diff` — 선택한 기준과의 비교
  let viewKind = "source";
  let thisVersion = 0;    // 이 모달이 가리키는 버전 번호(선택기 기본값 · 비교의 한쪽)
  let reqSeq = 0;
  const curData = () => (viewKind === "diff" ? diffData : srcData);

  /** 이 화면에 마크다운으로 렌더할 본문이 실제로 있는가 (파일명만으로 판정하지 않는다). */
  const mdRenderable = (data, kind) =>
    _isMarkdownFile(fnameEl.textContent) && _bodyState(data, kind || viewKind).sourceView;

  const syncToggles = (data, kind) => {
    const k = kind || viewKind;
    // 노출 판정은 비교 모달의 `syncHlToggle` 과 **같은 함수**(`_bodyState`)를 쓴다 —
    // 렌더할 본문이 실제로 왔을 때만 보인다.
    const md = mdRenderable(data, k);
    mdWrap.hidden = !md;
    if (md) mdCb.checked = mdOn;
    // 마크다운으로 보는 동안 구문 색 토글은 숨긴다(칠할 원문 줄이 화면에 없다 — 거짓 어포던스).
    const state = _bodyState(data, k);
    const paintable = Boolean(detectedLang) && state.hasBody && !(md && mdOn);
    hlWrap.hidden = !paintable;
    if (paintable) {
      hlLabel.textContent = `${codeLanguageLabel(detectedLang)} 구문 색`;
      hlCb.checked = hlOn;
    }
    // diff 전용 컨트롤 — 비교 상태에서만 나타나고, 그릴 diff 표가 있을 때만 활성이다
    // (내용이 같은 쌍은 원문 화면이므로 표시 방식을 바꿀 대상이 없다 — 비교 모달과 같은 사유).
    const inDiff = k === "diff";
    viewToggleEl.hidden = !inDiff;
    ctxToggleEl.hidden = !inDiff;
    if (inDiff) {
      const why = state.hasDiff ? "" : "비교할 차이가 없는 화면이라 표시 방식을 바꿀 대상이 없습니다.";
      for (const b of modeBtns) { b.disabled = !state.hasDiff; b.title = why; }
      ctxCb.disabled = !state.hasDiff;
      ctxToggleEl.title = why;
      viewToggleEl.classList.toggle("is-disabled", !state.hasDiff);
      ctxToggleEl.classList.toggle("is-disabled", !state.hasDiff);
    }
  };
  const syncHlToggle = syncToggles;   // 기존 호출부 이름 보존(같은 함수 — 판정면이 하나여야 한다)
  syncToggles(null, "source");

  // 컨트롤이 하나도 없으면 컨트롤 바를 통째로 숨긴다 — 바이너리 화면에서 통계도 토글도 없이
  // padding + border-bottom 만 남아 제목 아래에 정체불명의 빈 띠가 그어졌다(§18.8 design 지적).
  const syncControlsBar = () => {
    controlsEl.hidden = !statsEl.textContent && hlWrap.hidden && mdWrap.hidden
      && cmpWrap.hidden && viewToggleEl.hidden;
  };
  syncControlsBar();

  // 제목·버전 태그·통계는 **상태에 따라 다르게 말한다** — 한 모달이 두 화면을 갖게 됐으므로,
  // 지금 보고 있는 것이 원문인지 비교인지가 제목에서 먼저 읽혀야 한다.
  const syncHead = () => {
    if (viewKind === "diff") {
      // ⚠ 이 모달(`openAttachmentSourceModal`)에는 **계보 축이 없다** — 자기 체인의 버전만
      //   견준다. 그래서 여기서는 "버전 비교" 가 정확하다. 계보 축을 가진 것은 전용 diff
      //   모달(`openAttachmentDiffModal`)이고, 그쪽 제목은 그 함수가 따로 갱신한다.
      titleWordEl.textContent = "버전 비교";
      const f = Number(diffData?.from?.version_number || 0);
      const t = Number(diffData?.to?.version_number || 0);
      verTagEl.textContent = f && t ? ` (v${f} → v${t})` : "";
      statsEl.textContent = _diffStatsText(diffData);
      return;
    }
    const clipped = _sourceClipped(srcData);
    titleWordEl.textContent = clipped ? "문서 앞부분" : "문서 원문";
    // 어느 버전의 원문인지 화면에 남긴다 — 체인의 모든 버전이 같은 파일명을 쓰므로
    // 번호가 없으면 구별 단서가 0 이다(§18.8 ux 지적).
    const vn = Number(srcData?.version?.version_number || 0);
    verTagEl.textContent = vn > 1 || srcData?.version?.is_latest === false
      ? ` (v${vn}${srcData?.version?.is_latest === false ? "" : " · 최신"})`
      : "";
    statsEl.textContent = _sourceStatsText(srcData);
  };

  const renderOpts = () => ({
    ratio,
    rows: (curData() && curData().rows) || [],
    lang: hlOn ? detectedLang : null,
    md: mdOn && mdRenderable(curData(), viewKind),
    onRatioChange: (r) => { ratio = r; },
    // gap 국소 전개는 이 모달에 두지 않는다 — 전개는 "전체 맥락" 재요청 + 쌍별 캐시가 필요한
    // 비교 전용 흐름이고, 여기서 더 보려면 "동일한 줄도 모두 보기" 라는 대안 경로가 이미 있다.
    // (버튼을 만들지 않으므로 눌러서 실패하는 경로도 없다.)
    onExpandGap: null,
    onMdFallbackSync: () => {
      mdCb.checked = false;
      hlWrap.hidden = !detectedLang;
      if (detectedLang) {
        hlLabel.textContent = `${codeLanguageLabel(detectedLang)} 구문 색`;
        hlCb.checked = hlOn;
      }
      syncControlsBar();
    },
  });

  // 재렌더는 **스크롤을 보존**한다 — `bodyEl.innerHTML = ""` 가 scroller 요소를 통째로 갈아치우고
  // 스크롤은 그 요소의 상태이므로 함께 사라진다. 원문 뷰는 축약이 없어 항상 전량(최대 6,000행)을
  // 그리므로 diff 보다 잃는 거리가 크다(§18.8 ux 지적 — 비교 모달 AC-AVD-15 와 같은 계약).
  //
  // 두 화면 모두 **비교 모달과 같은 렌더러**를 쓴다: 원문은 `_renderSourceBody`, 비교는
  // `_renderBody`. 이 모달이 자기 렌더러를 따로 갖지 않는 것이 "같은 파일이 두 화면에서 다르게
  // 보이지 않는다" 는 계약의 실행면이다.
  const render = (renderCfg) => {
    const keepScroll = Boolean(renderCfg && renderCfg.keepScroll);
    if (viewKind === "diff") {
      if (diffData) _renderBody(bodyEl, diffData, mode, { ...renderOpts(), keepScroll });
      return;
    }
    _renderSourceBody(bodyEl, srcData, { ...renderOpts(), keepScroll });
  };

  /** 원문 화면으로 (되)돌아간다 — 이미 받아 둔 `/source` 응답을 다시 그린다(재요청 0). */
  const showSource = (renderCfg) => {
    viewKind = "source";
    diffData = null;
    syncToggles(srcData, "source");
    syncHead();
    syncControlsBar();
    render(renderCfg);
  };

  // 비교 기준 선택기 — `/source` 가 준 체인으로 채운다. **이 버전이 기본 선택**이고 그 선택은
  // 곧 원문 보기다. 체인이 1개면 숨긴다 — 고를 것이 하나뿐인 select 는 조작할 수 없는 컨트롤이고
  // (이 모듈이 금지한 거짓 어포던스), 버전이 하나인 첨부가 이 모달의 원래 대상이다.
  const fillCompareSelect = (data) => {
    const chain = (Array.isArray(data?.versions) ? [...data.versions] : [])
      .sort((a, b) => Number(a.version_number || 1) - Number(b.version_number || 1));
    cmpSel.innerHTML = "";
    if (chain.length < 2) { cmpWrap.hidden = true; return; }
    for (const v of chain) {
      const n = Number(v.version_number || 1);
      const opt = document.createElement("option");
      opt.value = String(n);
      // 자기 자신도 목록에 둔다 — 비교 상태에서 원문으로 되돌아오는 **명시적 경로**가 되고,
      // "같은 버전을 고르면 원문" 이라는 계약이 화면에서 조작 가능해진다(사용자 요청 후단).
      opt.textContent = n === thisVersion ? `${_versionLabel(v)} · 이 버전` : _versionLabel(v);
      cmpSel.appendChild(opt);
    }
    cmpSel.value = String(thisVersion);
    cmpWrap.hidden = false;
  };

  const loadDiff = async (basisVersionRaw, loadOpts) => {
    const basis = Number(basisVersionRaw);
    // 같은 버전 = 비교할 것이 없다 → 원문을 그대로 출력한다(요청 없이 정본 재사용).
    if (!basis || basis === thisVersion) { showSource({ keepScroll: false }); return; }
    const keepScroll = Boolean(loadOpts && loadOpts.keepScroll);
    const pendingAnchor = keepScroll
      ? _captureScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"))
      : null;
    // 방향은 **오래된 → 새로운** 으로 정규화한다(docstring 참조) — 기준으로 더 새 버전을
    // 골랐다고 좌우가 뒤집히면 같은 쌍이 두 방향으로 보인다.
    const from = Math.min(basis, thisVersion);
    const to = Math.max(basis, thisVersion);
    const seq = ++reqSeq;
    viewKind = "diff";
    statsEl.textContent = "비교 중…";
    // 보존 요청이면 기존 표를 남겨 둔다 — 지우면 '불러오는 중' 사이에 화면이 튄다.
    if (!keepScroll) bodyEl.innerHTML = '<div class="attach-diff-notice">불러오는 중…</div>';
    const qs = new URLSearchParams({ from_version: String(from), to_version: String(to) });
    if (ctxCb.checked) qs.set("context", "full");
    try {
      const data = await apiFetch(
        `/api/attachments/${encodeURIComponent(attachmentId)}/diff?${qs.toString()}`);
      if (seq !== reqSeq) return;   // 늦게 도착한 응답이 최신 선택을 덮지 않게
      diffData = data;
      syncToggles(data, "diff");
      syncHead();
      syncControlsBar();
      render({ keepScroll: false });
      if (keepScroll && pendingAnchor) {
        _restoreScrollAnchor(bodyEl.querySelector(".attach-diff-scroller"), pendingAnchor);
      }
    } catch (e) {
      if (seq !== reqSeq) return;
      diffData = null;
      syncToggles(null, "diff");
      syncHead();   // 제목은 "버전 비교" 로 두고 태그·통계는 비운다(diffData 부재)
      syncControlsBar();
      bodyEl.innerHTML =
        `<div class="attach-diff-notice is-warn">${escapeHtml(e?.message || "비교에 실패했습니다.")}</div>`;
    }
  };

  const load = async () => {
    const seq = ++reqSeq;
    viewKind = "source";
    statsEl.textContent = "불러오는 중…";
    bodyEl.innerHTML = '<div class="attach-diff-notice">불러오는 중…</div>';
    try {
      const data = await apiFetch(
        `/api/attachments/${encodeURIComponent(attachmentId)}/source`);
      if (seq !== reqSeq) return;   // 늦게 도착한 응답이 최신 선택을 덮지 않게
      srcData = data;
      // 파일명은 서버가 정본이다 — 호출부가 이름을 안 넘겼을 때(말풍선 칩 등) 제목·언어
      // 판정이 어긋나지 않게 응답으로 다시 맞춘다.
      if (data.filename && data.filename !== fnameEl.textContent) {
        fnameEl.textContent = String(data.filename);
        detectedLang = detectCodeLanguage(fnameEl.textContent);
      }
      thisVersion = Number(data.version?.version_number || 1);
      fillCompareSelect(data);
      syncToggles(data, "source");
      syncHead();
      syncControlsBar();
      render();
    } catch (e) {
      if (seq !== reqSeq) return;
      srcData = null;
      diffData = null;
      viewKind = "source";
      cmpWrap.hidden = true;
      syncToggles(null, "source");
      statsEl.textContent = "";
      titleWordEl.textContent = "문서 원문";
      verTagEl.textContent = "";
      syncControlsBar();
      bodyEl.innerHTML =
        `<div class="attach-diff-notice is-warn">${escapeHtml(e?.message || "원문을 불러오지 못했습니다.")}</div>`;
    }
  };

  // 비교 기준 변경 — 같은 버전이면 원문으로 되돌아오고(요청 0), 다른 버전이면 그 쌍을 비교한다.
  cmpSel.addEventListener("change", () => { loadDiff(cmpSel.value); });

  // 보기 방식(2열/단일열) — 같은 응답의 다른 표현이므로 재요청하지 않는다.
  for (const b of modeBtns) {
    b.addEventListener("click", () => {
      mode = b.dataset.mode === "unified" ? "unified" : "split";
      _writeViewMode(mode);
      syncModeButtons();
      render({ keepScroll: true });
    });
  }

  // 맥락 범위는 **서버가 축약을 계산**하므로 재요청이 필요하다(프론트에 축약 로직을 재구현하면
  // 같은 쌍에 두 화면이 나온다 — 비교 모달과 같은 사유). 보던 위치는 유지한다.
  ctxCb.addEventListener("change", () => {
    _writeContextFull(ctxCb.checked);
    if (viewKind === "diff") loadDiff(cmpSel.value, { keepScroll: true });
  });

  // 같은 응답의 표시 방식만 바뀌므로 재요청 없이 재렌더하고, **보고 있던 줄을 유지**한다
  // (비교 모달과 동일 계약 — 계약의 절반만 옮기면 스크롤이 최상단으로 튄다).
  hlCb.addEventListener("change", () => {
    hlOn = hlCb.checked;
    _writeHighlightOn(hlOn);
    render({ keepScroll: true });
  });

  // 마크다운 ↔ 원문 전환. 스크롤은 **보존하지 않는다** — 두 뷰는 좌표계가 다르다(렌더된 문서의
  // 스크롤 위치를 줄 표에 그대로 얹으면 엉뚱한 곳으로 튄다). 전환은 사용자가 의도한 뷰 변경이라
  // 맨 위에서 시작하는 편이 예측 가능하다.
  mdCb.addEventListener("change", () => {
    mdOn = mdCb.checked;
    _writeMdRenderOn(mdOn);
    syncToggles(curData(), viewKind);   // 구문 색 토글 노출이 md 상태에 종속된다
    syncControlsBar();
    render({ keepScroll: false });
  });

  load();
}
