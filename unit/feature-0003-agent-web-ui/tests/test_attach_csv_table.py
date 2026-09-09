"""attach-csv-table: 첨부 `.csv`/`.tsv` 의 **표 렌더** 계약 구조 가드.

사용자 요청(2026-09-09): "DQA클라이언트 첨부파일 중, csv 확장자가 표 형태로 출력될 수 있도록
구성해주세요." 종전에는 CSV 첨부를 열면 쉼표가 섞인 평문 줄 표가 나왔다(구문 색이 구분자만
강조). `.md` 를 문서로 렌더하는 선행 경로와 같은 성격의 요청이며, 같은 관용구
(원문은 토글로 남기고 기본은 렌더)로 구현했다.

**층위 분담** — 이 파일은 *구조*를, `tests/verify_attach_source_table.mjs` 는 jsdom 위에서
*행위*(실제 격자 생성·파서 계약·XSS·상한·토글 배타)를 잠근다. 본 프로젝트의 `make test` 는
agent 이미지에 node·node-jsdom 을 설치하므로 **S7 이 실제로 그 하네스를 돌린다** — 다만
node/jsdom 이 없는 환경(호스트 직접 실행 등)에서는 조용히 skip 되지 않고 «gap 이 문서에
기록됐는가» 로 강등해 판정한다 (`test_side_panel_exclusive.py` 와 같은 계약).

픽셀은 어느 쪽도 보지 못한다 — 정렬·머리글 고정·행 높이는 `tests/pb0009_attach_csv_table.py`
가 실제 DQA Shell(WebView2)에서 잰다 (§16.6, PB-0009).

검증 (`make test` agent 이미지, DB 불요 — 순수 소스 검사):

  S1  파서·렌더러·구분자 판정이 실재하고, 파서는 **테스트가 직접 부를 수 있게 export** 된다.
  S2  서버가 이 화면에 `.csv` 를 실제로 **도달시킨다** — `Kind` 지도의 `csv` 와
      `_VERSION_DIFF_TEXT_KINDS` 가 맞물려야 표 토글이 뜰 본문이 온다. 프론트만 고치고
      서버 kind 가 막고 있으면 기능은 0% 인데 프론트 테스트는 전부 green 이다.
  S3  구분자 판정의 정본이 `code-highlight.js` 레지스트리 하나다 — 확장자 목록을 프론트에
      두 벌 두면 한쪽만 갱신되는 방식으로 갈린다(이 모듈이 반복 기록한 결함 기전).
  S4  셀 값이 **`textContent` 로만** 들어간다 — 표 렌더 경로에 `innerHTML` 이 없다.
      첨부 본문은 사용자가 올린 임의 바이트다.
  S5  **양쪽 모달**이 표 토글을 갖는다 — 같은 파일이 두 화면에서 다르게 보이지 않는다는
      이 모듈의 계약. 한쪽만 배선하면 비교 모달의 identical 화면에서 CSV 가 평문으로 남는다.
  S6  CSS 계약 — sticky 머리글, `[hidden]` 강제, 표 wrap 이 자체 스크롤 컨테이너가 아님.
      (`[hidden]` 강제가 빠지면 "그릴 본문이 없으면 숨김" 이 CSS 층에서만 조용히 무력화되고,
       jsdom 은 `.hidden` 속성만 보므로 행위 하네스도 못 잡는다 — 이 파일이 유일한 backstop.)
  S7  행위 하네스가 실행되거나, 그 CI 미배선 gap 이 문서에 기록돼 있다.

  음성 대조군 (§16.7 G11-b — 검사 자체가 무엇을 검사하는지 증명):
  N1  `innerHTML` 주입을 넣은 사본을 **같은 파이프라인**에 태우면 S4 판정이 False 다.
  N2  주석/문자열 안의 `innerHTML` 은 오탐을 만들지 않는다(주석 제거가 실제로 동작함).
  N3  토글 마크업이 한쪽 모달에만 있으면 S5 판정이 누락을 보고한다.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_STATIC = _ROOT / "src" / "static"
_TESTS = pathlib.Path(__file__).resolve().parent
_FEATURE_DOCS = _ROOT / "docs"

_ATTACH_DIFF = _STATIC / "app" / "attach-diff.js"
_CODE_HL = _STATIC / "code-highlight.js"
_CHAT_CSS = _STATIC / "css" / "chat.css"
_CONVERSATIONS = _ROOT / "src" / "routers" / "conversations.py"
_CONV_STORE = _ROOT / "src" / "routers" / "_conv_store.py"
_HARNESS = _TESTS / "verify_attach_source_table.mjs"

_CI_GAP_MARKER = "attach-csv-table: 행위 하네스 CI 미배선"


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments_and_strings(src: str) -> str:
    """`//`·`/* */` 주석과 문자열 리터럴을 지운다 — «코드로 존재하는가» 만 남긴다.

    주석에 적어 둔 예시가 계약 충족으로 읽히면 검사가 스스로 무의미해진다 (§16.7 G11-a).
    정규식 리터럴은 건드리지 않는다(이 파일의 판정 대상이 아니다).
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ── S1: 구성요소 실재 ───────────────────────────────────────────────────────
def test_s1_parser_and_renderer_exist_and_parser_is_exported():
    src = _read(_ATTACH_DIFF)
    assert re.search(r"^export function parseDelimitedText\(", src, re.M), (
        "파서가 export 되지 않으면 행위 하네스가 정본 대신 자기 사본을 시험하게 된다"
    )
    assert re.search(r"^function _renderDelimitedInto\(", src, re.M)
    assert re.search(r"^function _tableDelimiter\(", src, re.M)
    # 상한은 «숫자» 여야 한다 — 없으면 넓은 CSV 한 건이 창을 멎게 한다.
    assert re.search(r"const TABLE_COL_CAP = \d+;", src)
    assert re.search(r"const TABLE_CELL_CAP = \d+;", src)


# ── S2: 서버 도달성 (프론트만 고치면 기능 0%) ────────────────────────────────
def test_s2_server_actually_delivers_csv_body_to_this_screen():
    """`.csv` 가 `/source` 의 본문 응답까지 도달하는지 — 프론트 계약의 **전제**다.

    `code-highlight.js` 가 스스로 적어 둔 주의: "도달성은 서버가 결정한다". 확장자를 프론트
    레지스트리에 등록해도 서버 `Kind` 가 텍스트 계열이 아니면 `viewable:false` 로 강등되어
    이 화면에 본문이 오지 않는다 — 그러면 표 토글은 영영 뜨지 않는데 프론트 단위 검증은
    전부 통과한다.
    """
    conv = _read(_CONVERSATIONS)
    store = _read(_CONV_STORE)
    assert re.search(r'"csv":\s*"csv"', conv), "확장자 → Kind 지도에 csv 가 없다"
    kinds = re.search(r"_VERSION_DIFF_TEXT_KINDS\s*=\s*\(([^)]*)\)", store)
    assert kinds, "_VERSION_DIFF_TEXT_KINDS 정의를 찾지 못했다"
    assert '"csv"' in kinds.group(1), (
        "csv 가 본문 조회 kind 집합에 없다 — 표 토글이 뜰 본문 자체가 오지 않는다"
    )


# ── S3: 구분자 판정 정본 단일화 ─────────────────────────────────────────────
def test_s3_delimiter_decision_has_one_source_of_truth():
    src = _read(_ATTACH_DIFF)
    body = _strip_comments_and_strings(src)
    fn = re.search(r"function _tableDelimiter\(filename\) \{(.*?)\n\}", src, re.S)
    assert fn, "_tableDelimiter 본문을 찾지 못했다"
    assert "detectCodeLanguage(filename)" in fn.group(1), (
        "확장자 판정이 레지스트리를 거치지 않는다 — 목록이 두 벌이 되면 한쪽만 갱신된다"
    )
    # 레지스트리 쪽에 csv/tsv 가 실재해야 위 판정이 값을 낸다.
    hl = _read(_CODE_HL)
    assert re.search(r'csv:\s*\{[^}]*exts:\s*\["csv"\]', hl)
    assert re.search(r'tsv:\s*\{[^}]*exts:\s*\["tsv"', hl)
    # 확장자 문자열을 파일 어딘가에 하드코딩해 두 벌로 만들지 않았는지 (코드 기준).
    assert '.csv' not in body, "확장자 판정이 코드에 하드코딩돼 있다(레지스트리 이중화)"


# ── S4: 셀 값은 값으로만 ────────────────────────────────────────────────────
def _table_render_block(src: str) -> str:
    m = re.search(r"function _renderDelimitedInto\(.*?\n\}\n", src, re.S)
    assert m, "_renderDelimitedInto 본문을 찾지 못했다"
    return m.group(0)


def test_s4_table_cells_never_use_innerhtml():
    block = _strip_comments_and_strings(_table_render_block(_read(_ATTACH_DIFF)))
    assert "innerHTML" not in block, (
        "표 렌더 경로에 innerHTML 이 있다 — 첨부 본문은 사용자가 올린 임의 바이트다"
    )
    # 값은 셀 래퍼 div 의 textContent 로만 들어간다(래퍼 도입 후에도 «값은 값» 계약은 같다).
    assert "d.textContent = v" in block and "cellDiv(" in block


# ── S5: 두 모달 모두 배선 ───────────────────────────────────────────────────
def test_s5_both_modals_expose_the_table_toggle():
    src = _read(_ATTACH_DIFF)
    assert src.count('class="attach-source-tabletoggle"') == 2, (
        "표 토글 마크업이 두 모달(원문 보기·버전 비교)에 각각 있어야 한다 — 한쪽만 배선하면 "
        "같은 CSV 가 화면에 따라 표로도 평문으로도 보인다"
    )
    assert src.count('querySelector(".attach-source-table-cb")') == 2
    # 두 모달 모두 «원문을 출력하는 화면» 에서만 켠다(줄 대조 diff 를 격자로 바꾸지 않는다).
    assert src.count("tableRenderable") >= 6
    assert len(re.findall(r"tableRenderable = \(data, kind\) =>\n?\s*Boolean\(tableDelim\) && _bodyState\([^)]*\)\.sourceView", src)) == 2, (
        "표 렌더 가능 판정이 sourceView(원문 출력 화면)에 걸려 있지 않다"
    )


# ── S6: CSS 계약 (jsdom 이 못 보는 축) ──────────────────────────────────────
def test_s6_css_contract():
    css = _read(_CHAT_CSS)
    assert re.search(r"\.attach-source-table thead th\s*\{[^}]*position:\s*sticky", css), (
        "머리글 sticky 부재 — 긴 표에서 스크롤하면 열 이름이 사라진다"
    )
    assert re.search(r"\.attach-source-table\s*\{[^}]*border-collapse:\s*separate", css), (
        "sticky 머리글에 collapse 를 쓰면 테두리가 함께 스크롤된다"
    )
    assert re.search(
        r"\.attach-source-tabletoggle\[hidden\]\s*\{[^}]*display:\s*none", css
    ) or re.search(
        r"\.attach-source-mdtoggle\[hidden\],\s*\.attach-source-tabletoggle\[hidden\]\s*\{[^}]*display:\s*none",
        css,
    ), "[hidden] 강제 부재 — 토글 숨김 계약이 CSS 층에서 무력화될 수 있다"
    assert not re.search(r"\.attach-source-tablewrap\s*\{[^}]*overflow", css), (
        "표 wrap 이 자체 스크롤 컨테이너가 되면 sticky 머리글의 기준이 그쪽으로 옮겨간다"
    )
    assert re.search(r"\.attach-source-table-cell\s*\{[^}]*white-space:\s*pre-wrap", css), (
        "셀의 줄바꿈·연속 공백 보존 규칙 부재 — 인용 필드는 여러 줄일 수 있다"
    )
    # 실측 캡처에서 적발: `td` 에 `max-width`/`white-space` 를 두면 각각 열 계산이 무시하고
    # (긴 값 한 칸이 표를 늘린다) 행 번호 열까지 덮어쓴다(두 자리 번호가 세로로 쪼개진다).
    assert re.search(r"\.attach-source-table-cell\s*\{[^}]*max-width:", css)
    assert not re.search(
        r"\.attach-source-table th,\s*\n?\.attach-source-table td\s*\{[^}]*(max-width|white-space):", css
    ), "값 상한·줄바꿈 규칙이 td 에 있으면 열 계산·행 번호 열이 그것을 무시하거나 덮어쓴다"
    assert re.search(r"\.attach-source-table-no\s*\{[^}]*white-space:\s*nowrap", css)


# ── S7: 행위 하네스 배선 또는 gap 기록 ──────────────────────────────────────
def test_s7_behaviour_harness_runs_or_ci_gap_is_documented():
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
        if proc.returncode != 2:      # 2 = jsdom 미설치 → 아래 gap 경로로 강등
            assert proc.returncode == 0, (
                f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
            )
            return
    recorded = any(
        _CI_GAP_MARKER in _read(p)
        for p in [_FEATURE_DOCS / "REVIEW.md", *sorted((_FEATURE_DOCS / "test-runs.d").glob("*.md"))]
        if p.exists()
    )
    assert recorded, (
        "행위 하네스를 실행할 수 없는데(node/jsdom 부재) 그 gap 이 문서에 없다. "
        f'REVIEW.md 또는 test-runs.d fragment 에 "{_CI_GAP_MARKER}" 를 기록하라 — '
        "조용한 skip 은 «검증했다» 로 오인된다"
    )


# ── N: 음성 대조군 (§16.7 G11-b) ────────────────────────────────────────────
def test_n1_innerhtml_injection_is_rejected_by_same_pipeline():
    fixture = 'function _renderDelimitedInto(a, b, c) {\n  td.innerHTML = v;\n  th.textContent = h;\n}\n'
    block = _strip_comments_and_strings(_table_render_block(fixture))
    assert "innerHTML" in block, "S4 검사가 실제 주입을 잡지 못한다 — 검사 자체가 무의미"


def test_n2_innerhtml_in_comment_or_string_is_not_a_false_positive():
    fixture = (
        'function _renderDelimitedInto(a, b, c) {\n'
        '  // innerHTML 은 쓰지 않는다\n'
        '  const why = "innerHTML 금지";\n'
        '  td.textContent = v;\n  th.textContent = h;\n}\n'
    )
    block = _strip_comments_and_strings(_table_render_block(fixture))
    assert "innerHTML" not in block, "주석/문자열이 오탐을 만든다"


def test_n3_single_modal_wiring_is_reported():
    one_only = 'const a = 1; class="attach-source-tabletoggle"'
    assert one_only.count('class="attach-source-tabletoggle"') != 2, (
        "S5 의 개수 판정이 한쪽만 배선된 상태를 통과시키면 안 된다"
    )
