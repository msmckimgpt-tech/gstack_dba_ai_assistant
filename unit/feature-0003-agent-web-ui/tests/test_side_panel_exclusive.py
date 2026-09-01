"""side-panel-exclusive: 우측 오버레이 사이드 패널의 **단독 열림** 계약 구조 가드.

사용자 요청: "사이드바는 하나만 열릴 수 있도록 구성해주세요. (실행 단계, 첨부파일, 유저
프로필 등)". 세 패널(`#attachSidePanel` 첨부 · `#stepSidePanel` 실행 단계 · `#profileDrawer`
유저 프로필)은 모두 `position: fixed; right: 0` 로 같은 자리에 겹치는데 서로를 모른 채 각자
`hidden` 만 벗겨, 둘 이상이 동시에 "열린" 상태가 될 수 있었다. 화면에는 z-index 가 높은
하나만 보이고 아래 패널은 **열린 채 가려진다**(닫기 버튼·리사이즈 핸들까지 가려짐).

해소: `src/static/app/side-panels.js` 를 단일 등록부(choke point)로 두고, 각 소유 모듈이
자기 close 를 등록(`registerSidePanel`)한 뒤 **모든 열기가 `openSidePanel(key, openFn)` 을
통과**한다. 배타를 opener 가 «기억해서» 호출하는 구조였다면 그 규율을 정적 검사로만 지켜야
하지만, 열기를 문 하나로 모으면 «호출 누락» 이라는 실패 모드 자체가 없어진다.

**층위 분담** — 이 파일은 *구조*를, `tests/verify_side_panel_exclusive.mjs` 는 jsdom 위에서
*행위*(실제로 하나만 열리는지 · 접근성 동기화 · 사후 단언)를 잠근다. `make test` 의 agent
이미지에 node 가 없어 행위 하네스는 CI 에 배선되지 않는다 — 그 **gap 자체를 S6 이 단언**해
조용한 skip 이 되지 않게 한다.

검증 (`make test` agent 이미지, DB 불요 — 순수 소스 검사):

  S1  등록부가 존재하고 계약 3종을 export 하며, **leaf(의존성 0)** 다.
      leaf 가 깨지면 등록(top-level 부수효과)이 순환 import 의 TDZ·미평가 모듈에 걸린다.
  S2  세 opener 가 모두 `openSidePanel("<자기 key>", …)` 를 **코드로** 호출한다
      (주석·문자열 안의 등장은 인정하지 않는다 — AGENTS.md §16.7 G11-a).
  S3  index.html 의 `data-side-panel` 오버레이 전수가 등록부에 등록돼 있고, 그 반대도 참이다.
      선언적 표식이라 `<aside>`/`<div>` 같은 태그 선택에 좌우되지 않는다 (§16.7 G6 동형).
  S4  등록의 **형태**가 옳다 — `close`/`elementId` 키가 정확히 있고, 등록문이 **줄머리**에
      있다(= 모듈 top-level 부수효과). `colse:` 오타 하나면 그 패널이 배타에서 통째로
      이탈하는데 증상은 «수정 전 겹침» 과 같다.
  S5  세 패널 DOM 에 소유 모듈 밖에서 닿지 않는다 — `getElementById` 뿐 아니라
      `querySelector` 와 **모듈 스코프 핸들 import**(`profileDrawerEl`)까지 본다.
      소유 모듈 면제는 **자기 패널에 한정**한다 (§16.7 G8-a 적용면 전수감사).
  S6  행위 하네스가 실행되거나(node 가 있으면), 그 **CI 미배선 gap 이 문서에 기록**돼 있다.

  음성 대조군 (§16.7 G11-b — 검사 자체가 무엇을 검사하는지 증명):
  N1  계약 호출이 없는 opener 를 **같은 파이프라인**에 태우면 S2 판정이 False 다.
  N2  계약 호출이 주석/문자열에만 있는 opener 도 False 다 (주석 제거가 실제로 동작함).
  N3  등록되지 않은 오버레이 표식이 있으면 S3 판정이 누락을 보고한다.
  N4  `colse:` 오타 등록을 S4 가 잡는다.
  N5  `querySelector("#…")` · 핸들 import 우회를 S5 가 잡는다.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"
_TESTS = pathlib.Path(__file__).resolve().parent
_FEATURE_DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"

_REGISTRY = _STATIC / "app" / "side-panels.js"
_INDEX_HTML = _STATIC / "index.html"
_HARNESS = _TESTS / "verify_side_panel_exclusive.mjs"

# (소유 모듈, opener 함수명, 패널 key, 패널 DOM id)
_OWNERS = [
    (_STATIC / "app.js", "openStepSidePanel", "step", "stepSidePanel"),
    (_STATIC / "app" / "profile.js", "openProfile", "profile", "profileDrawer"),
    (_STATIC / "app" / "composer.js", "openAttachSidePanel", "attach", "attachSidePanel"),
]

# 감시 대상 DOM id — 등록된 3종 + 프로필 backdrop(드로어와 한 몸이라 단독 노출도 결함).
_WATCHED_IDS = ["attachSidePanel", "stepSidePanel", "profileDrawer", "profileBackdrop"]

# 파일별 «직접 닿아도 되는» 패널 id. 소유 모듈이라고 통째로 면제하지 않는다 —
# composer.js 가 남의 패널(#stepSidePanel)을 직접 여는 것도 우회다.
# app.js 가 profileDrawer/profileBackdrop 을 집는 것은 **핸들 획득**(export)이 그 자리이기 때문.
_PANEL_DOM_ALLOWLIST = {
    "app.js": {"stepSidePanel"},
    "app/profile.js": {"profileDrawer", "profileBackdrop"},
    "app/composer.js": {"attachSidePanel"},
    "app/side-panels.js": set(),      # 등록부는 elementId 로 동적 조회만 한다
}
# app.js 가 프로필 드로어/backdrop 을 집는 것은 **핸들 획득 선언 2줄**에서만 정당하다 —
# 그 사유가 정당화하는 것은 그 줄이지 파일 8천 줄 전체가 아니다.
# 줄바꿈·`let`·여분 공백 같은 **정당한 포맷 차이**로 거짓 FAIL 을 내지 않게 관대하게 쓴다 —
# 실측: 74자 줄을 포맷터가 감싸면 "누가 우회를 넣었다" 로 오진됐다(라운드 2 C6 과 같은 형태).
_HANDLE_DECL = re.compile(
    r'^export\s+(?:const|let)\s+profile(?:Drawer|Backdrop)El\s*=\s*'
    r'document\.getElementById\(\s*["\']profile(?:Drawer|Backdrop)["\']\s*\)\s*;',
    re.M | re.S)

# 모듈 스코프 패널 핸들 — 이것을 import 하면 `getElementById` 없이 패널을 여닫을 수 있다.
_HANDLE_SYMBOLS = ["profileDrawerEl", "profileBackdropEl"]
_HANDLE_IMPORT_ALLOWLIST = {"app/profile.js"}

# S6 이 «CI 미배선 gap 이 기록돼 있는가» 를 확인할 때 찾는 마커.
_CI_GAP_MARKER = "side-panel-exclusive: 행위 하네스 CI 미배선"


# ── 소스 검사 파이프라인 (프로덕션 파일과 음성 대조군이 **동일 함수**를 통과한다) ─────

# 정규식 리터럴은 이 문자들 **또는** 아래 키워드 뒤에서 시작할 수 있다.
# `/` 앞이 이 문자면 정규식 리터럴이 시작될 수 있다. `}` 는 **뺀다** — `function f(){}/2`
# 처럼 나눗셈이 더 흔하고, 블록 뒤 정규식은 실무에서 거의 없다(오판 시 거짓 FAIL).
_REGEX_PREV_CHARS = set("(,=:[!&|?{;+-*%<>~^")
# 증감 연산자 뒤의 `/` 는 언제나 나눗셈이다 (`i++ / n`) — 그런데 마지막 문자가 `+`/`-` 라
# 위 집합만 보면 정규식으로 오판해 그 뒤 파일 전체를 삼킨다(실측: 정상 산술 한 줄이
# 계약 테스트 4건을 붉게 만들었다).
_INCDEC_TAIL = ("++", "--")
_REGEX_PREV_WORDS = {
    "return", "typeof", "case", "in", "of", "do", "else", "instanceof",
    "new", "delete", "void", "throw", "yield", "await",
}
_TRAILING_WORD = re.compile(r"([A-Za-z_$][\w$]*)\s*$")


class JsScanError(RuntimeError):
    """스캐너가 소스를 해석하지 못했다 — 조용히 틀린 결과를 내지 않고 실패한다."""


def scan_js(src: str) -> tuple[str, list[bool]]:
    """JS 소스를 훑어 (주석 제거 소스, 리터럴 마스크) 를 낸다.

    - **주석은 제거**한다 (행 번호는 개행 보존으로 유지).
    - **문자열·템플릿·정규식 리터럴은 보존**하되, 그 구간을 마스크(True)로 표시한다.
      템플릿 리터럴의 `${...}` **보간은 코드**다 — 중첩 템플릿(`` `${x ? `a` : ""}` ``)이
      실제로 이 저장소에 있어(composer.js 첨부 목록 렌더), 템플릿을 평평한 문자열로 읽으면
      안쪽 백틱이 바깥을 닫아 **그 뒤 파일 전체가 오독**된다. 그래서 모드 스택으로 센다.

    마스크의 용도는 **«X 가 있다» 존재 단언 전용**이다 — 그 축에서는 자기 주석·자기 문자열이
    자기 단언을 통과시키는 것을 막아야 한다 (AGENTS.md §16.7 G11-a). 반대로 **«X 가 없다»
    축(S5 우회 스캔)에서는 마스크를 쓰지 않는다** — 리터럴을 건너뛰면 결함 라인만 골라
    지나치는 구조적 거짓 PASS 가 된다(같은 §의 경고).

    행 단위 휴리스틱이 아니라 문자 스캐너다. 정규식 리터럴 판정은 "직전 코드 토큰"
    휴리스틱이며, 오판이 조용히 넘어가지 않도록 **미종료 리터럴을 만나면 예외를 던진다**
    (오판의 전형적 귀결이 «따옴표가 파일 끝까지 열린 채» 이기 때문).
    """
    out: list[str] = []
    mask: list[bool] = []

    # 최근 emit 된 꼬리 32자만 들고 다닌다 — 매 `/` 마다 전체를 join 하면 O(n^2) 이라
    # 8천 줄 파일에서 스캐너가 사실상 멈춘다(실측).
    tail = [""]

    def emit(text: str, literal: bool) -> None:
        out.append(text)
        mask.extend([literal] * len(text))
        tail[0] = (tail[0] + text)[-32:]

    def regex_can_start() -> bool:
        stripped = tail[0].rstrip()
        if not stripped:
            return True
        if stripped.endswith(_INCDEC_TAIL):
            return False
        if stripped[-1] in _REGEX_PREV_CHARS:
            return True
        m = _TRAILING_WORD.search(stripped)
        return bool(m and m.group(1) in _REGEX_PREV_WORDS)

    # 모드 스택: ("code", brace_depth) | ("tmpl", 0). 템플릿 보간은 code 프레임으로 push.
    stack: list[list] = [["code", 0]]
    i, n = 0, len(src)
    while i < n:
        mode, depth = stack[-1]
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        if mode == "tmpl":
            if c == "\\":
                emit(src[i:i + 2], True)
                i += 2
                continue
            if c == "`":
                emit(c, True)
                stack.pop()
                i += 1
                continue
            if c == "$" and nxt == "{":
                emit("${", False)
                stack.append(["code", 0])
                i += 2
                continue
            emit(c, True)
            i += 1
            continue

        # ── code 모드 ──
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            i += 2
            closed = False
            while i < n:
                if src[i] == "*" and i + 1 < n and src[i + 1] == "/":
                    closed = True
                    break
                if src[i] == "\n":
                    emit("\n", False)  # 행 번호 보존
                i += 1
            if not closed:
                raise JsScanError("블록 주석이 닫히지 않았습니다 — 스캐너 오판 가능")
            i += 2
            continue
        if c == "`":
            emit(c, True)
            stack.append(["tmpl", 0])
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            emit(c, True)
            i += 1
            closed = False
            while i < n:
                if src[i] == "\\":
                    emit(src[i:i + 2], True)
                    i += 2
                    continue
                emit(src[i], True)
                if src[i] == quote:
                    i += 1
                    closed = True
                    break
                if src[i] == "\n":
                    break  # 개행을 넘는 따옴표 = 오판
                i += 1
            if not closed:
                raise JsScanError(f"문자열 리터럴({quote})이 닫히지 않았습니다 — 스캐너 오판 가능")
            continue
        if c == "/" and regex_can_start():
            emit(c, True)
            i += 1
            in_class = False
            closed = False
            while i < n:
                if src[i] == "\\":
                    emit(src[i:i + 2], True)
                    i += 2
                    continue
                if src[i] == "[":
                    in_class = True
                elif src[i] == "]":
                    in_class = False
                elif src[i] == "/" and not in_class:
                    emit(src[i], True)
                    i += 1
                    closed = True
                    break
                elif src[i] == "\n":
                    break
                emit(src[i], True)
                i += 1
            if not closed:
                raise JsScanError("정규식 리터럴이 닫히지 않았습니다 — 스캐너 오판 가능")
            continue
        if c == "{":
            stack[-1][1] = depth + 1
        elif c == "}":
            if depth == 0 and len(stack) > 1:
                # 템플릿 보간의 끝 — 바깥 템플릿으로 돌아간다.
                emit(c, False)
                stack.pop()
                i += 1
                continue
            stack[-1][1] = max(0, depth - 1)
        emit(c, False)
        i += 1

    if len(stack) != 1 or stack[0][0] != "code":
        raise JsScanError("템플릿 리터럴이 닫히지 않았습니다 — 스캐너 오판 가능")
    return "".join(out), mask


def strip_comments_only(src: str, path: pathlib.Path | None = None) -> str:
    """주석만 제거하고 **리터럴은 그대로** 둔다 — «X 가 없다» 축 전용.

    항상 **주어진 `src`** 를 스캔한다(테스트 fixture 의 상대경로가 실 파일과 겹쳐도
    엉뚱한 파일을 읽지 않게). `path` 는 스캔 실패 시 예외에 **파일 경로**를 싣는 용도다.
    """
    try:
        return scan_js(src)[0]
    except JsScanError as e:
        raise JsScanError(f"{path}: {e}" if path is not None else str(e)) from e


def extract_fn_span(src: str, name: str) -> tuple[int, int] | None:
    """함수 선언 하나의 [start, end) 구간 (verify_side_panel_exclusive.mjs 와 동일 규약)."""
    start = -1
    for cand in (f"export function {name}(", f"export async function {name}(",
                 f"async function {name}(", f"function {name}("):
        start = src.find(cand)
        if start >= 0:
            break
    if start < 0:
        return None
    depth, sig_end = 0, -1
    j = src.index("(", start)
    while j < len(src):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                sig_end = j
                break
        j += 1
    depth, end = 0, -1
    i = src.index("{", sig_end)
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    return (start, end) if end > 0 else None


def opener_honors_contract(src: str, fn_name: str, key: str) -> bool:
    """`fn_name` 의 **코드**가 `openSidePanel("<key>", …)` 로 연다."""
    code, mask = scan_js(src)
    span = extract_fn_span(code, fn_name)
    if not span:
        return False
    start, end = span
    pat = re.compile(rf'openSidePanel\(\s*["\']{re.escape(key)}["\']\s*,')
    for m in pat.finditer(code, start, end):
        if not mask[m.start()]:
            return True
    return False


def _top_level_props(body: str) -> set[str]:
    """옵션 객체의 **최상위** 속성명만 뽑는다 (`key: value` 와 ES6 축약형 `key` 둘 다).

    `close: () => closeAttachSidePanel({ auto: true })` 처럼 값이 중첩 객체를 담으면
    평평하게 훑는 정규식이 안쪽 `auto:` 까지 세어 오탐한다 — 깊이를 센다. 그리고 `:` 를
    이미 본 항목의 **값** 토큰(`closeProfile`)을 축약 속성으로 오인하지 않도록 항목마다
    `saw_colon` 을 추적한다.
    """
    props: set[str] = set()
    depth = 0
    token = ""
    saw_colon = False

    def flush() -> None:
        nonlocal token, saw_colon
        if not saw_colon:
            name = token.strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                props.add(name)
        token = ""
        saw_colon = False

    i = 0
    while i < len(body):
        c = body[i]
        if c in "{[(":
            depth += 1
            token = ""
        elif c in "}])":
            depth = max(0, depth - 1)
            token = ""
        elif c == ":" and depth == 0:
            name = token.strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                props.add(name)
            token = ""
            saw_colon = True
        elif c == "," and depth == 0:
            flush()
        elif c in "'\"`":
            quote = c
            i += 1
            while i < len(body) and body[i] != quote:
                i += 2 if body[i] == "\\" else 1
            token = ""
        else:
            token += c
        i += 1
    flush()
    return props


_REG_CALL = re.compile(r"^registerSidePanel\((.*?)\);[ \t]*$", re.M | re.S)


def parse_registrations(src: str, path: pathlib.Path | None = None) -> list[dict]:
    """줄머리(top-level) `registerSidePanel(...)` 호출을 파싱한다.

    줄머리 앵커라 (a) 주석 안의 언급 (b) 함수 안에 갇혀 **실행되지 않는** 등록이 걸러진다.
    반환: `{key, keys(전달한 속성명 집합), elementId, close_expr}`.
    """
    try:
        code, mask = scan_js(src)
    except JsScanError as e:
        raise JsScanError(f"{path}: {e}" if path is not None else str(e)) from e
    out = []
    for m in _REG_CALL.finditer(code):
        if mask[m.start()]:
            continue
        args = m.group(1)
        key_m = re.match(r'\s*["\']([A-Za-z0-9_-]+)["\']\s*,', args)
        obj_m = re.search(r"\{(.*)\}", args, re.S)
        props = _top_level_props(obj_m.group(1)) if obj_m else set()
        el_m = re.search(r'elementId:\s*["\']([A-Za-z0-9_-]+)["\']', args)
        out.append({
            "key": key_m.group(1) if key_m else "",
            "keys": props,
            "elementId": el_m.group(1) if el_m else "",
            "raw": m.group(0),
        })
    return out


def all_registrations() -> list[dict]:
    """static 트리 **전수**에서 등록을 모은다 (소유 3파일 하드코딩에 묶이지 않게)."""
    found = []
    for js in _first_party_js():
        for reg in parse_registrations(js.read_text(encoding="utf-8"), path=js):
            reg["file"] = str(js.relative_to(_STATIC))
            found.append(reg)
    return found




# body 직속 오버레이 «후보» — `<aside>` 전부 + `class` 토큰이 정확히 `drawer` 인 `<div>`.
# `drawer-bg`(프로필 backdrop)는 독립 패널이 아니라 드로어의 부속이므로 제외한다 —
# 부분 문자열이 아니라 **클래스 토큰**으로 가른다.
# 오버레이 «후보» 판정 — 태그 화이트리스트가 아니라 **class 토큰**으로 가른다.
#   `x-side-panel` · `notif-side-panel` · `drawer` · `side-drawer` … 를 모두 잡고,
#   좌측 in-flow 컬럼(`class="sidebar"`)은 잡지 않는다(배타 대상이 아니다).
# 속성은 `HTMLParser` 가 파싱한 값을 쓰므로 **따옴표 종류에 의존하지 않고**, 중첩된
# 오버레이(app-shell 안)도 후보에 들어간다.
_OVERLAY_CLASS_TOKEN = re.compile(r"^(?:[\w-]+-)?side-panel$|^drawer$|^(?:[\w-]+-)?drawer$")


def _is_overlay_candidate(tag: str, attrs: dict, body_child: bool) -> bool:
    tokens = (attrs.get("class") or "").split()
    if any(_OVERLAY_CLASS_TOKEN.match(t) for t in tokens):
        return True
    return tag == "aside" and body_child


class _OverlayCandidateCollector(HTMLParser):
    """오버레이 후보의 (id, 표식) 를 모은다 — 중첩 포함, 따옴표 무관."""

    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self.candidates: list[tuple[str, str]] = []   # (id, data-side-panel)

    def handle_startendtag(self, tag, attrs):
        self._consider(tag, attrs)

    def handle_starttag(self, tag, attrs):
        if tag in self._VOID:
            self._consider(tag, attrs)
            return
        self._consider(tag, attrs)
        self._stack.append(tag)

    def _consider(self, tag, attrs):
        d = dict(attrs)
        body_child = (self._stack[-1] if self._stack else "") == "body"
        if _is_overlay_candidate(tag, d, body_child):
            self.candidates.append((d.get("id") or "", d.get("data-side-panel") or ""))

    def handle_endtag(self, tag):
        for idx in range(len(self._stack) - 1, -1, -1):
            if self._stack[idx] == tag:
                del self._stack[idx:]
                return


def unmarked_overlays(html: str) -> list[str]:
    """오버레이 후보 중 `data-side-panel` 표식이 **없는** 것.

    census 를 선언적 표식으로 옮기면 태그 의존은 사라지지만 «작성자가 표식을 잊으면 검출
    0» 이라는 성질이 생긴다 — 그런데 이 census 가 존재하는 이유가 정확히 «서로를 모르는
    패널이 각자 만들어졌다» 는 사건이다. 그래서 표식 **강제** 축을 함께 둔다.

    ⚠ **한계**: 후보 판정이 class 토큰에 걸려 있다. 위 패턴에 맞지 않는 이름
    (`class="rail"` 같은)으로 만든 새 오버레이는 이 축 밖이며, 그때는 S3 census 도 비고
    런타임 사후 단언도 (표식이 없으므로) 그 패널을 보지 못한다.
    """
    parser = _OverlayCandidateCollector()
    parser.feed(html)
    return [(cid or "(id 없음)") for cid, marker in parser.candidates if not marker]


def declared_overlays(html: str) -> dict[str, str]:
    """`data-side-panel="<key>"` 표식이 붙은 요소의 {key: id}.

    **S8 과 같은 `HTMLParser` 경로**를 쓴다 — 한쪽만 파서를 쓰고 다른 쪽이 정규식을 쓰면
    따옴표 종류에서 규약이 갈려, 단일따옴표 마크업의 «표식은 붙었는데 등록은 잊은» 패널이
    **두 축 모두 조용히 통과**한다(실측). 반대 방향으로는 거짓 FAIL 도 난다.
    """
    parser = _OverlayCandidateCollector()
    parser.feed(html)
    return {marker: cid for cid, marker in parser.candidates if marker}
# 패널을 손에 넣는 **관용구 축** — id 문자열 한 형태만 보면 저장소가 실제로 쓰는 형태
# (핸들 import · 클래스 선택자 · 이번 변경이 만든 `[data-side-panel]`)가 전부 샌다.
_PANEL_CLASS_LITERALS = ["attach-side-panel", "step-side-panel", "drawer-bg"]


def panel_dom_offenders(sources: dict[str, str]) -> list[str]:
    """소유 허용 범위 밖에서 패널 DOM 에 닿는 지점 (**«없다» 축 — 리터럴 마스크 미사용**)."""
    offenders: list[str] = []
    for rel, src in sources.items():
        code = strip_comments_only(src, _STATIC / rel if (_STATIC / rel).exists() else None)
        allowed = _PANEL_DOM_ALLOWLIST.get(rel, set())
        # app.js 의 프로필 핸들 획득 2줄만 면제 — 그 줄을 지운 사본으로 나머지를 검사한다.
        scan_target = _HANDLE_DECL.sub("", code) if rel == "app.js" else code
        for pid in _WATCHED_IDS:
            if pid in allowed:
                continue
            hit = (
                re.search(rf'getElementById\(\s*["\']{pid}["\']\s*\)', scan_target)
                or re.search(rf'querySelector(?:All)?\(\s*["\'][^"\']*#{pid}\b', scan_target)
            )
            if hit:
                offenders.append(f"{rel} → #{pid}")
        if rel not in _HANDLE_IMPORT_ALLOWLIST:
            for sym in _HANDLE_SYMBOLS:
                if re.search(rf'^\s*{sym}\s*,?\s*$|[{{,]\s*{sym}\s*[,}}]', code, re.M):
                    offenders.append(f"{rel} → import {sym}")
        if rel not in _PANEL_DOM_ALLOWLIST:      # 소유 3모듈 + 등록부 외
            if re.search(r'querySelector(?:All)?\(\s*["\'][^"\']*\[data-side-panel', code):
                offenders.append(f"{rel} → [data-side-panel] 선택자")
            for cls in _PANEL_CLASS_LITERALS:
                if re.search(rf'(?:querySelector(?:All)?\(\s*["\'][^"\']*\.{cls}\b'
                             rf'|getElementsByClassName\(\s*["\']{cls}["\'])', code):
                    offenders.append(f"{rel} → .{cls} 선택자")
    return offenders



def _call_spans(code: str, callee: str) -> list[tuple[int, int]]:
    """`callee(` 호출의 [시작, 닫는 괄호+1) 구간 전수."""
    spans = []
    for m in re.finditer(rf"\b{re.escape(callee)}\s*\(", code):
        depth, i = 0, m.end() - 1
        while i < len(code):
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i + 1))
                    break
            i += 1
    return spans


# 패널을 «손에 넣는» 토큰 — 어떤 API 를 썼든 이 중 하나는 근처에 있어야 그 패널을 집을 수 있다.
_PANEL_TOKENS = _WATCHED_IDS + _HANDLE_SYMBOLS + _PANEL_CLASS_LITERALS + ["data-side-panel"]
_UNHIDE = re.compile(r'classList\s*\.\s*(?:remove|toggle)\(\s*["\']hidden["\']')


def _fn_body_spans(code: str) -> list[tuple[int, int]]:
    """`function …(…) { … }` 와 `(…) => { … }` 의 **[선언 시작, 본문 끝)** 스팬 전수.

    ⚠ `function` 뒤 **첫 `{` 를 본문으로 잡으면 안 된다** — `function f(a, { b = 1 } = {})`
    처럼 구조분해·기본값 파라미터가 있으면 그 `{` 는 **시그니처의 중괄호**다. 그러면 경계
    파싱이 실패해 파일 전체로 폴백하고, 8천 줄 안의 동명 지역변수가 무관한 커밋을 붉게
    만든다(실측). `extract_fn_span` 과 같은 규약으로 **시그니처 괄호를 균형 매칭으로 넘긴
    뒤** 본문 `{` 를 잡는다.
    """
    spans: list[tuple[int, int]] = []

    def body_from(open_brace: int) -> int:
        depth, i = 0, open_brace
        while i < len(code):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def sig_end(paren: int) -> int:
        depth, i = 0, paren
        while i < len(code):
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    for m in re.finditer(r"\bfunction\b", code):
        paren = code.find("(", m.end())
        if paren < 0:
            continue
        se = sig_end(paren)
        if se < 0:
            continue
        brace = code.find("{", se)
        if brace < 0:
            continue
        end = body_from(brace)
        if end > 0:
            spans.append((m.start(), end))
    # 화살표 함수 — `(…) => {` / `x => {`. 경계를 못 잡으면 «보류» 가 늘어나므로 함께 센다.
    for m in re.finditer(r"=>\s*\{", code):
        end = body_from(code.index("{", m.start()))
        if end < 0:
            continue
        # 선언 시작은 화살표 앞의 파라미터 목록 시작(근사) — 대입문 탐색 범위로만 쓴다.
        head = code[:m.start()].rstrip()
        st = m.start()
        if head.endswith(")"):
            depth, i = 0, len(head) - 1
            while i >= 0:
                if head[i] == ")":
                    depth += 1
                elif head[i] == "(":
                    depth -= 1
                    if depth == 0:
                        break
                i -= 1
            st = max(0, i)
        spans.append((st, end))
    return spans


def _enclosing_fn_span(code: str, pos: int, spans: list[tuple[int, int]]) -> tuple[int, int] | None:
    """`pos` 를 품는 **가장 안쪽** 함수 스팬. 못 찾으면 `None`(= 경계 미상)."""
    best = None
    for a, b in spans:
        if a <= pos < b and (best is None or (b - a) < (best[1] - best[0])):
            best = (a, b)
    return best


# «이 표현식이 감시 대상 **패널 자체**를 집는가» — 하위 요소(`#attachSidePanelNote` 등)와
# 구분하려면 부분 문자열이 아니라 **완결된 조회 형태**를 봐야 한다.
_PANEL_LOOKUP = re.compile(
    r'getElementById\(\s*["\'](?:' + "|".join(_WATCHED_IDS) + r')["\']\s*\)'
    r'|querySelector(?:All)?\(\s*["\'][^"\']*(?:#(?:' + "|".join(_WATCHED_IDS) + r')\b'
    r'|\[data-side-panel|\.(?:attach-side-panel|step-side-panel|drawer-bg)\b)'
    r'|getElementsByClassName\(\s*["\'](?:attach-side-panel|step-side-panel|drawer-bg)["\']'
    r'|\b(?:' + "|".join(_HANDLE_SYMBOLS) + r')\b'
)
_UNHIDE_RECEIVER = re.compile(r'([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*|\))\s*$')


def _receiver_of(code: str, at: int) -> str:
    """`code[at]` 에 있는 `classList` 의 **수신 표현식** 텍스트(근사)."""
    head = code[:at].rstrip()
    if head.endswith("."):
        head = head[:-1].rstrip()   # `p.` 의 점을 떼고 수신자만 남긴다
    while head.endswith("]"):       # `getElementsByClassName("x")[0]` 의 인덱싱을 건너뛴다
        depth, i = 0, len(head) - 1
        while i >= 0:
            if head[i] == "]":
                depth += 1
            elif head[i] == "[":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        head = head[:i].rstrip()
    if head.endswith(")"):
        # `document.getElementById("x")` 같은 호출 — 균형 괄호로 되짚는다.
        i = len(head) - 1
        depth = 0
        while i >= 0:
            if head[i] == ")":
                depth += 1
            elif head[i] == "(":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        j = i
        while j > 0 and (head[j - 1].isalnum() or head[j - 1] in "_$."):
            j -= 1
        return head[j:]
    m = _UNHIDE_RECEIVER.search(head)
    return m.group(1) if m else ""


def unhide_outside_gate(sources: dict[str, str]) -> list[str]:
    """감시 대상 패널의 `hidden` **해제**가 `openSidePanel(` 밖에서 일어나는 지점.

    `getElementById` 든 `querySelector` 든 클래스든 핸들이든, «연다» 는 행위 자체를 본다 —
    수신 표현식이 패널을 집는 형태이거나, 지역 변수라면 **같은 함수 안의 그 대입문**이
    패널을 집으면 대상으로 센다.

    ⚠ **한계 (정직 표기)**: 완전히 형태-무관하지는 않다. 패널을 집는 형태의 열거
    (`_PANEL_LOOKUP`)에 없는 새 관용구, 함수 밖에서 얻어 넘긴 핸들, 동적 id 조립은 놓친다.
    그 표면은 S5(우회 축)와 런타임 사후 단언이 **부분적으로만** 덮는다 — 후자는 등록부의
    문을 탄 열기에서만 돌기 때문이다.
    """
    offenders: list[str] = []
    deferred: list[str] = []
    for rel, src in sources.items():
        code = strip_comments_only(src, _STATIC / rel if (_STATIC / rel).exists() else None)
        gates = _call_spans(code, "openSidePanel")
        spans = _fn_body_spans(code)
        for m in _UNHIDE.finditer(code):
            recv = _receiver_of(code, m.start())
            if not recv:
                continue
            targets_panel = bool(_PANEL_LOOKUP.search(recv))
            if not targets_panel and re.fullmatch(r"[A-Za-z_$][\w$]*", recv.strip()):
                span = _enclosing_fn_span(code, m.start(), spans)
                if span is None:
                    # 경계 미상 — **판정을 보류**한다(파일 전수로 넓히면 8천 줄 안의 동명
                    # 지역변수가 무관한 커밋을 붉게 만든다). 미탐지 방향은 런타임 사후 단언이
                    # 결과 축에서 한 번 더 본다.
                    deferred.append(f"{rel}:{code[:m.start()].count(chr(10)) + 1}")
                    continue
                a, b = span
                assign = re.search(rf'\b(?:const|let|var)\s+{re.escape(recv.strip())}\s*=([^;]*);', code[a:b])
                targets_panel = bool(assign and _PANEL_LOOKUP.search(assign.group(1)))
            if not targets_panel:
                continue
            if any(ga <= m.start() < gb for ga, gb in gates):
                continue                      # 문 안에서 열린다 — 정상
            line = code[:m.start()].count("\n") + 1
            offenders.append(f"{rel}:{line}")
    unhide_outside_gate.deferred = deferred      # 진단용 — 「보류」 건수를 밖에서 볼 수 있게
    return offenders


def _first_party_js() -> list[pathlib.Path]:
    """스캔 대상 — `vendor/` 는 제외한다.

    서드파티 minified 번들(9MB+)은 우리가 고칠 수 없고, 그 안의 `i++ / n` 같은 정상 산술이
    손수 만든 렉서를 넘어뜨리면 **사이드 패널 계약 테스트가 무관한 이유로 붉어진다**.
    등록도 우회도 `vendor/` 안에서 일어날 일이 아니다(배포 스탬프 스크립트도 같은 예외를
    쓴다 — 선례 정합).
    """
    return [js for js in sorted(_STATIC.rglob("*.js")) if "vendor" not in js.parts]


def _static_js_sources(skip: set[str] = frozenset()) -> dict[str, str]:
    out = {}
    for js in _first_party_js():
        rel = str(js.relative_to(_STATIC))
        if rel in skip:
            continue
        out[rel] = js.read_text(encoding="utf-8")
    return out


# ── S: 프로덕션 계약 ──────────────────────────────────────────────────────

def test_s1_registry_module_exports_contract_and_is_leaf():
    assert _REGISTRY.exists(), "등록부 모듈(app/side-panels.js) 부재"
    raw = _REGISTRY.read_text(encoding="utf-8")
    code = strip_comments_only(raw)
    for fn in ("registerSidePanel", "closeOtherSidePanels", "openSidePanel"):
        assert re.search(rf"^export function {fn}\(", code, re.M), f"{fn} export 누락"
    # leaf 불변식 — 등록부가 순환에 편입되면 top-level 등록이 TDZ·미평가 모듈에 걸린다.
    assert not re.search(r"^\s*import\s", code, re.M), (
        "등록부는 leaf 여야 한다 — 여기서 다른 모듈을 import 하면 app.js ↔ app/*.js 순환에 "
        "편입되어 top-level 등록(부수효과)이 누락될 수 있다"
    )


@pytest.mark.parametrize("path,fn_name,key,_elem", _OWNERS)
def test_s2_each_opener_goes_through_the_gate(path, fn_name, key, _elem):
    src = path.read_text(encoding="utf-8")
    assert opener_honors_contract(src, fn_name, key), (
        f'{path.name}:{fn_name}() 가 openSidePanel("{key}", …) 를 통과하지 않는다 — '
        "다른 사이드 패널이 열린 채 겹친다"
    )


def test_s3_overlay_census_matches_registry():
    dom = declared_overlays(_INDEX_HTML.read_text(encoding="utf-8"))
    regs = {r["key"]: r["elementId"] for r in all_registrations()}
    missing = sorted(set(dom) - set(regs))
    assert not missing, (
        f"오버레이 패널이 등록부에 없다: {missing} — registerSidePanel(...) 로 등록해야 "
        "다른 패널을 열 때 함께 닫힌다"
    )
    orphan = sorted(set(regs) - set(dom))
    assert not orphan, f'DOM 에 data-side-panel 표식이 없는 등록: {orphan}'
    mismatched = sorted(k for k in dom if dom[k] != regs[k])
    assert not mismatched, f"key 는 같은데 elementId 가 다르다: {[(k, dom[k], regs[k]) for k in mismatched]}"


def test_s4_registration_shape_is_valid():
    regs = all_registrations()
    assert len(regs) == len(_OWNERS), f"top-level 등록 수 불일치: {[r['file'] for r in regs]}"
    for r in regs:
        assert r["keys"] == {"close", "elementId"}, (
            f'{r["file"]} 의 등록 속성이 {sorted(r["keys"])} — `close`/`elementId` 여야 한다. '
            "오타 한 글자면 그 패널이 배타에서 통째로 이탈하고 증상은 «수정 전 겹침» 과 같다"
        )
        assert r["key"] and r["elementId"], f'{r["file"]} 의 등록에 key/elementId 누락'


def test_s5_panel_dom_is_touched_only_by_owner_modules():
    offenders = panel_dom_offenders(_static_js_sources())
    assert not offenders, (
        "소유 허용 범위 밖에서 사이드 패널 DOM 에 닿는다 — 등록부를 우회해 여닫으면 "
        f"단독 열림 계약이 무력화된다: {offenders}"
    )


def test_s7_unhide_happens_only_inside_the_gate():
    offenders = unhide_outside_gate(_static_js_sources())
    assert not offenders, (
        "감시 대상 패널의 `hidden` 해제가 `openSidePanel(` 밖에서 일어난다 — 어떤 선택자를 "
        f"썼든 그 지점은 배타를 거치지 않는다: {offenders}"
    )


def test_s8_body_level_overlays_carry_the_marker():
    unmarked = unmarked_overlays(_INDEX_HTML.read_text(encoding="utf-8"))
    assert not unmarked, (
        f"오버레이 후보에 `data-side-panel` 표식이 없다: {unmarked} — 표식이 없으면 "
        "census(S3) 밖이라 등록 누락이 검출되지 않는다"
    )


def test_s9_hidden_panels_are_css_unfocusable():
    """`inert` 미지원 엔진의 폴백 — CSS 가 실제로 포커스를 끊는지."""
    css = (_STATIC / "css" / "chat.css").read_text(encoding="utf-8")
    for sel in (".attach-side-panel.hidden", ".step-side-panel.hidden"):
        m = re.search(rf"{re.escape(sel)}\s*\{{(.*?)\}}", css, re.S)
        assert m, f"{sel} 규칙 부재"
        body = m.group(1)
        assert "visibility: hidden" in body, (
            f"{sel} 에 `visibility: hidden` 이 없다 — 이 패널의 `.hidden` 은 "
            "`display:flex !important` 라 화면 밖에 있어도 Tab 대상이다"
        )
        assert "pointer-events: none" in body, f"{sel} 에 `pointer-events: none` 이 없다"


def test_s10_restore_tail_is_wired():
    """복원 꼬리가 **실제로 호출되는가** — 함수가 옳아도 아무도 부르지 않으면 사용자에게는
    수정 전과 같은 화면이 남는다(helper-wiring vs helper-correctness).
    """
    code = strip_comments_only(
        (_STATIC / "app" / "composer.js").read_text(encoding="utf-8"),
        _STATIC / "app" / "composer.js",
    )
    assert re.search(r"function\s+_applyAttachRestoreAfterLoad\s*\(", code), "복원 꼬리 함수 부재"
    # 정의 스팬 밖에서 **호출**되는 지점이 있어야 한다.
    span = extract_fn_span(code, "_applyAttachRestoreAfterLoad")
    assert span, "복원 꼬리 함수 스팬을 찾지 못했다"
    calls = [m.start() for m in re.finditer(r"_applyAttachRestoreAfterLoad\s*\(", code)]
    outside = [c for c in calls if not (span[0] <= c < span[1])]
    assert outside, (
        "복원 꼬리가 배선되지 않았다 — 정의만 있고 호출이 없다. 사용자에게는 «단계 보기 후 "
        "첨부 패널을 다시 열면 보던 화면이 안 돌아온다» 로 나타난다"
    )


def test_s6_behaviour_harness_runs_or_ci_gap_is_documented():
    """행위 하네스를 돌리거나, 돌릴 수 없으면 그 **gap 이 문서에 기록**돼 있어야 한다.

    조용한 `skip` 은 운영에서만 통과하는 형태다 — 여기서는 skip 대신 «기록» 을 강제한다.
    """
    assert _HARNESS.exists(), "행위 하네스 파일 부재"
    node = shutil.which("node")
    if node:
        proc = subprocess.run(
            [node, str(_HARNESS)], cwd=str(_TESTS),
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "NODE_OPTIONS": ""},
        )
        if proc.returncode == 2:      # jsdom 미설치 — 아래 gap 경로로 강등
            pass
        else:
            assert proc.returncode == 0, f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
            return
    # node(또는 jsdom) 부재 — gap 이 저장소에 기록돼 있는지 확인한다.
    recorded = any(
        _CI_GAP_MARKER in p.read_text(encoding="utf-8")
        for p in [_FEATURE_DOCS / "REVIEW.md", *sorted((_FEATURE_DOCS / "test-runs.d").glob("*.md"))]
        if p.exists()
    )
    assert recorded, (
        "행위 하네스를 실행할 수 없는데(node/jsdom 부재) 그 gap 이 문서에 없다. "
        f'REVIEW.md 또는 test-runs.d fragment 에 "{_CI_GAP_MARKER}" 를 기록하라 — '
        "조용한 skip 은 «검증했다» 로 오인된다"
    )


# ── N: 음성 대조군 (§16.7 G11-b) ──────────────────────────────────────────

def test_n1_opener_without_gate_is_rejected():
    fixture = """
function openAttachSidePanel() {
  const panel = document.getElementById("attachSidePanel");
  if (!panel) return null;
  panel.classList.remove("hidden");
  return null;
}
"""
    assert opener_honors_contract(fixture, "openAttachSidePanel", "attach") is False


def test_n2_gate_only_in_comment_or_string_is_rejected():
    fixture = """
function openAttachSidePanel() {
  // openSidePanel("attach", () => {});
  /* openSidePanel("attach", () => {}); */
  const note = 'openSidePanel("attach",';
  document.getElementById("attachSidePanel").classList.remove("hidden");
  return note;
}
"""
    assert opener_honors_contract(fixture, "openAttachSidePanel", "attach") is False


def test_n2b_real_call_next_to_decoy_is_accepted():
    # 주석 제거가 과하게 잘라 **진짜 호출까지** 지우지 않는지(거짓 FAIL 방향) 함께 잠근다.
    # `return /…/` 은 정규식 리터럴이다 — 나눗셈으로 오판하면 그 뒤 파일 전체가 문자열로
    # 먹혀 스캐너가 조용히 틀린다(그 오판은 이제 JsScanError 로 드러난다).
    fixture = """
function openAttachSidePanel() {
  // side-panel-exclusive 설명 주석
  const re = /https:\\/\\/example/;
  openSidePanel("attach", () => {});
  return re;
}
function q(s) { return /['"]/.test(s); }
"""
    assert opener_honors_contract(fixture, "openAttachSidePanel", "attach") is True


def test_n2c_unterminated_literal_raises_instead_of_silently_masking():
    # 스캐너가 오판하면 «조용히 틀린 결과» 대신 예외를 낸다 — «없다» 축의 거짓 PASS 차단.
    with pytest.raises(JsScanError):
        scan_js('const s = "열린 채 끝나는 문자열\n')


def test_n3_unregistered_overlay_is_detected():
    html = """<!DOCTYPE html><html><body>
      <div class="app-shell"><aside class="sidebar" id="innerNav"></aside></div>
      <aside class="attach-side-panel hidden" id="attachSidePanel" data-side-panel="attach"></aside>
      <div class="new-side-panel hidden" id="brandNewPanel" data-side-panel="brandnew"></div>
    </body></html>"""
    dom = declared_overlays(html)
    # 표식 없는 좌측 사이드바는 census 밖 — 태그가 아니라 표식이 판정축이다.
    assert dom == {"attach": "attachSidePanel", "brandnew": "brandNewPanel"}, dom
    regs = {r["key"]: r["elementId"] for r in parse_registrations(
        'registerSidePanel("attach", { close: closeAttachSidePanel, elementId: "attachSidePanel" });'
    )}
    assert sorted(set(dom) - set(regs)) == ["brandnew"]


def test_n4_typo_registration_is_detected():
    regs = parse_registrations(
        'registerSidePanel("profile", { colse: closeProfile, elementId: "profileDrawer" });'
    )
    assert len(regs) == 1
    assert regs[0]["keys"] != {"close", "elementId"}


def test_n4b_registration_inside_function_is_not_counted():
    # 실행되지 않는 함수 안으로 옮긴 등록은 top-level 부수효과가 아니다 — 세지 않는다.
    src = (
        "function _neverCalled() {\n"
        '  registerSidePanel("profile", { close: closeProfile, elementId: "profileDrawer" });\n'
        "}\n"
    )
    assert parse_registrations(src) == []


def test_n5_bypass_forms_are_detected():
    # 저장소가 실제로 쓰는 세 우회 관용구를 전부 잡는지 — id 문자열 한 형태만 보면 샌다.
    cases = {
        "app/messages.js": 'document.querySelector("#stepSidePanel").classList.remove("hidden");',
        "app/sidebar.js": 'import { profileDrawerEl } from "../app.js?v=dev";',
        # 소유 모듈이라도 **남의 패널**을 직접 집으면 우회다.
        "app/composer.js": 'document.getElementById("stepSidePanel").classList.remove("hidden");',
    }
    for rel, src in cases.items():
        assert panel_dom_offenders({rel: src}), f"{rel} 우회를 잡지 못했다"
    # 리터럴 안에 숨겨도 «없다» 축은 마스크를 쓰지 않으므로 그대로 걸린다.
    assert panel_dom_offenders({"app/messages.js": """const s = 'getElementById("stepSidePanel")';"""})



def test_n5b_scan_failure_names_the_file():
    """스캐너 실패 메시지에 **파일 경로**가 실린다.

    파일명 없는 렉서 오류는 «어느 파일이 스캐너를 넘어뜨렸는가» 를 알 수 없어 원인 귀속에
    시간이 든다(라운드 3 B-2 축). 경로 귀속은 `strip_comments_only(path=…)` 한 곳이 맡는다.
    """
    broken = 'const s = "닫히지 않은 문자열\n'
    with pytest.raises(JsScanError) as ei:
        strip_comments_only(broken, pathlib.Path("app/somewhere.js"))
    assert "app/somewhere.js" in str(ei.value)


def test_n6_unhide_outside_gate_is_detected():
    # 형태를 바꿔도(핸들·클래스·표식 선택자) «연다» 는 행위 자체가 걸린다.
    cases = {
        "rogue-marker.js": ('function open2(){ const p = document.querySelector("[data-side-panel]");'
                            ' p.classList.remove("hidden"); }'),
        "rogue-handle.js": 'profileDrawerEl.classList.remove("hidden");',
        "rogue-class.js": 'document.getElementsByClassName("step-side-panel")[0].classList.remove("hidden");',
        # 라운드 3 실측: 핸들 획득과 해제가 **12줄 떨어진** 형태(고정 400자 창이 놓치던 것).
        "rogue-far.js": ('function f(){ const p = document.getElementById("attachSidePanel");\n'
                         + "".join(f"  const v{i} = {i};\n" for i in range(12))
                         + '  p.classList.remove("hidden");\n}'),
    }
    for rel, src in cases.items():
        assert unhide_outside_gate({rel: src}), f"{rel} 의 게이트 밖 해제를 잡지 못했다"
    # 하위 요소(`#attachSidePanelNote`)의 hidden 토글은 대상이 아니다 — 거짓 FAIL 방향.
    assert unhide_outside_gate(
        {"sub.js": 'document.getElementById("attachSidePanelNote").classList.remove("hidden");'}) == []
    # 함수 경계를 특정하지 못하면 **offender 로 올리지 않고 «보류»** 로 센다 — 파일 전수로
    # 넓히면 8천 줄 안의 동명 지역변수가 무관한 커밋을 붉게 만든다(라운드 4 B4-1).
    top_level = {"toplevel.js": 'const p = document.getElementById("stepSidePanel");\np.classList.remove("hidden");'}
    assert unhide_outside_gate(top_level) == []
    assert unhide_outside_gate.deferred, "경계 미상은 조용히 사라지지 않고 «보류» 로 관측된다"
    # 구조분해 파라미터가 있어도 경계를 정확히 잡는다(라운드 4 B4-1 회귀).
    destructured_ok = {"d.js": 'function f(a, { b = 1 } = {}){ const panel = document.getElementById("someModal");'
                               ' panel.classList.remove("hidden"); }\n'
                               'function g(){ const panel = document.getElementById("stepSidePanel"); }'}
    assert unhide_outside_gate(destructured_ok) == [], "구조분해 파라미터에서 거짓 FAIL"
    destructured_bad = {"e.js": 'function f(a, { b = 1 } = {}){ const p = document.getElementById("stepSidePanel");'
                                ' const x = 1; p.classList.remove("hidden"); }'}
    assert unhide_outside_gate(destructured_bad), "구조분해 함수 안의 우회를 놓쳤다"
    # 문 안에서 여는 형태는 정상 — 거짓 FAIL 방향도 함께 잠근다.
    good = 'openSidePanel("step", () => { document.getElementById("stepSidePanel").classList.remove("hidden"); });'
    assert unhide_outside_gate({"app.js": good}) == []


def test_n7_unmarked_overlay_is_detected():
    # 라운드 3 실측으로 드러난 사각 전부 — 태그·따옴표·중첩에 의존하지 않는지 잠근다.
    html = """<!DOCTYPE html><html><body>
      <aside class="attach-side-panel hidden" id="attachSidePanel" data-side-panel="attach"></aside>
      <aside class="notif-side-panel hidden" id="notifSidePanel"></aside>
      <div class='drawer hidden' id='quoteDrawer'></div>
      <section class="notif-side-panel" id="sectionPanel"></section>
      <nav class="side-drawer" id="navDrawer"></nav>
      <div class="app-shell">
        <aside class="sidebar" id="leftNav"></aside>
        <div class="x-side-panel" id="nestedPanel"></div>
      </div>
      <div class="chat-toast" id="toast"></div>
    </body></html>"""
    assert sorted(unmarked_overlays(html)) == [
        "navDrawer", "nestedPanel", "notifSidePanel", "quoteDrawer", "sectionPanel",
    ]
    # 좌측 in-flow 컬럼(`class="sidebar"`)은 후보가 아니다 — 배타 대상이 아니기 때문.
    assert "leftNav" not in unmarked_overlays(html)
