"""사이드바 대화 상태 dot 의 **배선 계약** — 상태값이 화면 색으로 도달하는지 소스로 대조한다.

## 왜 이 테스트가 있는가

사용자 신고(2026-09-01): "assistant 에게 요청을 보냈을 때 좌측 사이드바 대화 뱃지 색상이
상태값에 따라 변경되지 않는다."

원인은 단일 버그가 아니라 **어휘가 세 갈래로 갈린 배선**이었다:

  · 코드는 `is-${status}` 를 세 곳에서 각각 조립했다(사이드바 일반 행 · 인라인 이름변경 행 ·
    폴링 중 DOM 직접 갱신). 어느 곳도 CSS 를 참조하지 않는다.
  · CSS 에는 `.conv-dot.is-completed` 가 있었지만 서버가 쓰는 완료 리터럴은 `done` 이라
    **아무도 만들지 않는 죽은 규칙**이었고, `done`·`error`·`canceled` 는 규칙이 없었다.
  · `stale_error` 는 CSS 가 하이픈(`is-stale-error`), 코드가 언더스코어라 어긋나 있었다 —
    같은 줄에서 부여하는 `title` 툴팁만 떠서 "글씨는 뜨는데 색은 안 변한다" 로 보였다.

세 결함 모두 **개별 파일만 보면 정상으로 읽힌다.** 클래스는 붙고, CSS 는 문법이 맞고,
서버는 상태를 정확히 쓴다. 끊긴 것은 그 사이의 짝이다. 그래서 이 파일은 함수 하나의
정확성이 아니라 **파일 경계를 가로지르는 짝**을 검사한다.

## 왜 JS 가 아니라 pytest 인가

이 저장소의 CI 는 pytest 만 실행한다(JS 러너 없음). JS 로 계약을 써도 게이트에서 돌지
않으므로, 파이썬이 JS·CSS·백엔드 소스를 **읽어서** 대조한다. 실행되지 않는 검사는
검사가 아니다.

## 축

  T1  서버가 KV 에 쓰는 상태 리터럴 + 파생 stale_error ⊆ 프런트 어휘   (누락된 상태 = 무색)
  T2  프런트 어휘의 모든 클래스가 CSS 에서 **배경색을 실제로 선언**     (규칙 이름만으론 부족)
  T3  dot 클래스를 배정하는 곳은 정본 모듈 하나뿐 + 진입점이 실제로 그걸 호출
  T4  코드가 부여하는 모든 상태 modifier 가 CSS 규칙 또는 근거 있는 판정을 가진다
  T5  툴팁 소유권(`data-title-status`) 이음매의 세 계약이 코드에 남아 있다

## 게이트를 게이트로 잡은 이력 (§18.8 codex 리뷰, 2026-09-02)

초판은 위 축을 **주장**했지만 실제로는 다섯 갈래로 새고 있었다. 전부 「테스트는 통과하는데
결함은 살아 있다」 형태였고, 그대로 뒀다면 이 파일이 지키지 않는 것을 REPORT 가 지킨다고
말하는 상태가 됐다:

  · T1 이 상태 writer 파일을 **하드코딩 목록**으로 들고 있어 `routers/conversations.py` 의
    실제 writer 를 못 봤고, 3번째 인자가 변수인 호출(`modules/ask.py` 의 `_status`)을 조용히 건너뛰었다.
  · T2 가 **셀렉터 이름의 존재**만 봐서 `.conv-dot.is-done {}` 빈 규칙도 통과했다 — 정작
    이번 결함의 관측값은 배경색이었다.
  · T3 의 직접-조립 탐지가 **줄 단위**라 줄바꿈된 배정을 놓쳤고, T3b 최소치가 실제 호출 수보다
    낮아 한 경로를 되돌려도 통과했다.
  · T4 가 의존하는 감사가 `${...}` 를 통째로 비워, 조건식 안에서만 부여되는 클래스
    (`${checked ? " is-checked" : ""}`)가 양쪽 집합에서 동시에 사라졌다.
  · 툴팁 이음매(`data-title-status`)를 **아무 테스트도 건드리지 않아**, 그 분기를 지워도 green 이었다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

FEATURE_ROOT = Path(__file__).resolve().parents[1]
STATIC = FEATURE_ROOT / "src" / "static"
CONV_STATUS_JS = STATIC / "app" / "conv-status.js"
REPO_ROOT = FEATURE_ROOT.parents[1]

sys.path.insert(0, str(FEATURE_ROOT / "scripts"))
from audit_state_class_wiring import (  # noqa: E402
    ALLOWED_UNSTYLED,
    collect_assigned_state_classes,
    collect_css_declarations_for,
    collect_css_rules_for,
    collect_css_state_classes,
)

#: 상태 writer 를 **탐색**할 뿌리. 파일을 하드코딩하면 목록 밖에 생긴 writer 를 영영 못 본다
#: (초판이 `routers/conversations.py` 의 `set_run_status(..., "canceled", ...)` 를 놓친 이유).
BACKEND_SEARCH_ROOT = REPO_ROOT / "unit"

#: 3번째 인자를 리터럴로 해석하지 못한 호출 — 왜 안전한지 근거와 함께 등재한다.
#: 비어 있는 것이 정상이고, 채워야 한다면 그건 대개 해석기를 고칠 신호다.
ALLOWED_UNRESOLVED_STATUS_ARGS: dict[str, str] = {}

#: `_compute_display_status` / `_display_status_from_step_at` 이 파생시키는 상태.
DERIVED_STATUS_SOURCE = REPO_ROOT / "unit" / "feature-0003-agent-web-ui" / "src" / "routers" / "_conv_store.py"


# ── 소스 파싱 도우미 ────────────────────────────────────────────────────────────

def _strip_js_comments(text: str) -> str:
    """`//` 와 `/* */` 를 지운다.

    이 파일의 검사 대상 중 몇몇은 **주석에서 옛 코드 모양을 인용**한다(왜 고쳤는지 남기려고).
    주석을 지우지 않으면 그 인용이 "아직 옛 조립이 남아 있다" 로 읽혀 거짓 실패가 난다.
    문자열 안의 `//` 를 지우지 않도록 인용부호를 먼저 소비한다.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            quote, j = ch, i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _split_top_level_args(call_body: str) -> list[str]:
    """괄호·대괄호·중괄호 깊이 0 의 콤마로만 인자를 쪼갠다."""
    args, depth, current = [], 0, []
    for ch in call_body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        args.append("".join(current))
    return args


def _call_bodies(text: str, func: str) -> list[tuple[str, int]]:
    """`func(` 부터 균형 잡힌 닫는 괄호까지의 (인자 본문, 호출 시작 offset)."""
    bodies: list[tuple[str, int]] = []
    for match in re.finditer(rf"\b{re.escape(func)}\s*\(", text):
        i, depth = match.end(), 1
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        bodies.append((text[match.end():i - 1], match.start()))
    return bodies


def _resolve_status_literals(arg: str, text: str, call_start: int) -> list[str] | None:
    """status 인자에서 가능한 리터럴 값을 뽑는다. 해석 불가면 None.

    인자가 리터럴이거나 조건식(`"error" if _err else "done"`)이면 그대로 읽힌다. 바깥에서
    정해진 **변수**(`_status`)면 같은 함수 위쪽에서 그 이름에 대입된 문자열 리터럴을 찾는다 —
    `modules/ask.py` 가 실제로 그 형태이고, 초판은 이런 호출을 그냥 건너뛰어 **새 상태가 그
    경로로만 추가되면 게이트가 조용히 통과**했다.
    """
    literals = re.findall(r"[\"']([a-z_]+)[\"']", arg)
    if literals:
        return literals
    name = arg.strip()
    if not re.fullmatch(r"[A-Za-z_]\w*", name):
        return None
    window = text[max(0, call_start - 4000):call_start]
    assigned = re.findall(rf"\b{re.escape(name)}\s*=\s*[\"']([a-z_]+)[\"']", window)
    return assigned or None


def _frontend_status_map() -> dict[str, str]:
    """`app/conv-status.js` 의 CONV_DOT_STATUS 를 상태 → 클래스로 읽는다."""
    text = CONV_STATUS_JS.read_text(encoding="utf-8")
    block = re.search(r"CONV_DOT_STATUS\s*=\s*Object\.freeze\(\{(.*?)\}\);", text, re.S)
    assert block, "CONV_DOT_STATUS 정의를 찾지 못했다 — 어휘 정본의 형태가 바뀌었으면 이 테스트도 함께 고친다."
    entries = re.findall(r"(\w+)\s*:\s*Object\.freeze\(\{\s*cls:\s*\"([^\"]+)\"", block.group(1))
    assert entries, "CONV_DOT_STATUS 항목을 하나도 읽지 못했다."
    return dict(entries)


# ── T1: 서버 어휘 ⊆ 프런트 어휘 ────────────────────────────────────────────────

def _discover_status_writes() -> tuple[set[str], list[str]]:
    """저장소 전체에서 `set_run_status(...)` 를 찾아 (관측된 상태, 해석 실패 호출)."""
    observed: set[str] = set()
    unresolved: list[str] = []
    for path in sorted(BACKEND_SEARCH_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if "/tests/" in rel:
            continue  # 테스트가 만든 가짜 호출은 서버 어휘가 아니다
        text = path.read_text(encoding="utf-8", errors="replace")
        if "set_run_status" not in text:
            continue
        for body, start in _call_bodies(text, "set_run_status"):
            if text[max(0, start - 4):start] == "def ":
                continue  # 정의부 — 여기 `status: str` 는 값이 아니라 시그니처다
            args = _split_top_level_args(body)
            if len(args) < 3:
                continue  # status 인자가 없는 호출 형태
            resolved = _resolve_status_literals(args[2], text, start)
            if resolved is None:
                unresolved.append(f"{rel}:{text.count(chr(10), 0, start) + 1} → {args[2].strip()[:40]}")
            else:
                observed.update(resolved)
    return observed, unresolved


def test_t1_backend_status_vocabulary_is_covered_by_frontend():
    """서버가 실제로 기록하는 상태가 프런트 어휘에 전부 있어야 한다.

    빠진 상태는 조용히 **무색**이 된다 — 이번 결함에서 `done`·`error`·`canceled` 가 정확히
    그랬다. 파일 목록이 아니라 저장소를 **탐색**하므로, 새 writer 가 어디에 생겨도 걸린다.
    """
    observed, unresolved = _discover_status_writes()

    assert observed, "서버 상태 리터럴을 하나도 못 읽었다 — 파서가 소스 형태를 못 따라간 것이니 파서를 고친다."
    assert "done" in observed and "error" in observed, (
        f"기본 종료 상태(done/error)를 못 읽었다 — 탐색이 writer 를 놓치고 있다. 관측: {sorted(observed)}"
    )

    leftover = [u for u in unresolved if u.split(" → ", 1)[-1] not in ALLOWED_UNRESOLVED_STATUS_ARGS]
    assert not leftover, (
        "status 인자를 리터럴로 해석하지 못한 set_run_status 호출:\n  " + "\n  ".join(leftover)
        + "\n해석기를 고치거나, 안전한 이유를 ALLOWED_UNRESOLVED_STATUS_ARGS 에 적는다. "
        "해석 못 한 호출을 조용히 건너뛰면 새 상태가 그 경로로 들어와 무색이 된다."
    )

    derived = set(re.findall(r"return\s+\"(stale_error)\"", DERIVED_STATUS_SOURCE.read_text(encoding="utf-8")))
    assert "stale_error" in derived, "파생 상태 stale_error 를 못 읽었다 — 판정 로직이 옮겨갔는지 확인한다."
    observed |= derived

    missing = sorted(observed - set(_frontend_status_map()))
    assert not missing, (
        f"서버가 기록하는 상태 {missing} 이 app/conv-status.js 의 CONV_DOT_STATUS 에 없다. "
        "어휘에 없는 상태는 dot 이 기본 회색으로 떨어져 사용자에게 아무 신호도 주지 않는다."
    )


# ── T2: 프런트 어휘 ⊆ CSS 규칙 ─────────────────────────────────────────────────

def test_t2_every_frontend_status_class_actually_paints_a_background():
    """어휘의 모든 클래스가 `.conv-dot.<cls>` 규칙에서 **배경색을 실제로 선언**해야 한다.

    셀렉터 이름만 보면 `.conv-dot.is-done {}` 이나 `color` 만 바꾸는 규칙도 "규칙 있음" 으로
    읽힌다 — 그런데 base `.conv-dot` 의 회색 배경이 그대로 남아 화면은 결함 그대로다.
    이번 결함의 관측값이 배경색이었으므로 검사도 거기까지 내려간다 (§18.8 codex [P2]).
    """
    declarations = collect_css_declarations_for(STATIC, "conv-dot")
    unpainted = []
    for cls in sorted(set(_frontend_status_map().values())):
        bodies = declarations.get(cls) or []
        if not bodies:
            unpainted.append(f"{cls} — 규칙 없음")
        elif not any(re.search(r"\bbackground(-color)?\s*:", b) for b in bodies):
            unpainted.append(f"{cls} — 규칙은 있으나 background 미선언: {bodies[0][:60]!r}")
    assert not unpainted, (
        "상태가 배경색으로 도달하지 않는다:\n  " + "\n  ".join(unpainted)
        + "\n`src/static/css/shell.css` 의 `.conv-dot` 블록을 고친다."
    )


def test_t2b_no_dead_conv_dot_rule():
    """반대 방향 — CSS 에만 있고 어휘에 없는 `.conv-dot.is-*` 규칙은 죽은 규칙이다.

    `.conv-dot.is-completed` 가 정확히 그것이었다: 서버 어휘는 `done` 인데 CSS 는
    `completed` 를 칠하고 있어, 규칙이 존재한다는 사실이 오히려 "완료 색은 있다" 는
    오독을 만들었다.
    """
    dead = sorted(set(collect_css_rules_for(STATIC, "conv-dot")) - set(_frontend_status_map().values()))
    assert not dead, (
        f"어떤 상태도 만들지 않는 `.conv-dot` 규칙: {dead}. "
        "어휘에 등재하거나 규칙을 지운다 — 죽은 규칙은 다음 사람이 '색은 있다' 고 오독한다."
    )


# ── T3: 조립 지점이 정본을 실제로 쓰는가 ────────────────────────────────────────

def test_t3_conv_dot_class_is_assembled_only_in_the_single_source():
    """`conv-dot` 클래스 문자열을 배정하는 곳은 `app/conv-status.js` 하나뿐이어야 한다.

    헬퍼의 정확성만 검사하면 「진입점이 그 헬퍼를 실제로 쓰는가」를 못 본다. 종전 결함이
    바로 그 형태였다 — 헬퍼 없이 각 지점이 제 어휘로 조립했다.
    """
    # 줄 단위로 보면 줄바꿈된 배정(`dot.className =\n  \`conv-dot ...\``)이 빠져나간다.
    # 파일 전체를 DOTALL 로 훑되, `;` 를 만나기 전까지로 범위를 묶어 오탐을 막는다.
    direct_assembly = re.compile(
        r"(?:\.className\s*=|classList\.(?:add|toggle)\()[^;]{0,300}?conv-dot", re.S
    )
    offenders: list[str] = []
    for path in sorted(STATIC.rglob("*.js")):
        rel = path.relative_to(STATIC).as_posix()
        if "vendor/" in rel or rel == "app/conv-status.js":
            continue
        code = _strip_js_comments(path.read_text(encoding="utf-8", errors="replace"))
        for match in direct_assembly.finditer(code):
            lineno = code.count("\n", 0, match.start()) + 1
            offenders.append(f"{rel}:{lineno}: {' '.join(match.group(0).split())[:120]}")
    assert not offenders, (
        "conv-dot 클래스를 정본 밖에서 조립한다 — 어휘가 다시 갈라진다:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "rel, expected",
    [
        # 일반 행 · 인라인 이름변경 행 · in-flight 항목 · 무상태 placeholder
        ("app/sidebar.js", 4),
        ("app.js", 1),           # 폴링 중 DOM 직접 갱신
    ],
)
def test_t3b_entry_points_call_the_helper(rel: str, expected: int):
    """dot 을 만드는 진입점이 정본 헬퍼를 **실제로, 빠짐없이** 호출하는지.

    최소치(`>=`)로 두면 한 경로를 직접 조립으로 되돌려도 나머지가 최소치를 채워 통과한다
    (§18.8 codex [P2]). 정확한 수로 묶어, 배선이 하나라도 빠지거나 늘면 계약을 갱신하게 만든다.
    """
    code = _strip_js_comments((STATIC / rel).read_text(encoding="utf-8"))
    assert 'from "./conv-status.js' in code or 'from "./app/conv-status.js' in code, (
        f"{rel} 이 상태 어휘 정본을 import 하지 않는다."
    )
    calls = len(re.findall(r"\bconversationDotClass\s*\(", code))
    assert calls == expected, (
        f"{rel} 의 conversationDotClass 호출 {calls}회 ≠ 계약 {expected}회. "
        "배선이 빠졌거나 dot 생성 지점이 늘었다 — 어느 쪽이든 이 계약을 함께 갱신해야 한다."
    )


def test_t3c_no_underscore_status_class_is_produced():
    """`is-stale_error` 처럼 **언더스코어가 섞인** 클래스를 만들지 않는다.

    CSS 클래스 어휘는 하이픈이다. 상태값(`stale_error`)을 그대로 클래스에 이어붙이던 것이
    이번 구분자 불일치의 원인이었고, 툴팁만 뜨고 색은 안 변하는 비대칭을 만들었다.
    """
    bad = [cls for cls in _frontend_status_map().values() if "_" in cls]
    assert not bad, f"클래스 이름에 언더스코어: {bad} — CSS 어휘는 하이픈이다."


# ── T4: 상태 modifier 전반의 배선 게이트 ───────────────────────────────────────

def test_t4_every_assigned_state_modifier_is_styled_or_adjudicated():
    """코드가 부여하는 모든 `is-*`/`has-*` 가 CSS 규칙을 갖거나 근거와 함께 판정돼 있어야 한다.

    이 축이 사용자 요청의 "이와 같이 배선이 끊긴 기능들" 을 재발까지 포함해 닫는다.
    새 상태 클래스를 CSS 없이 추가하면 여기서 적색이 나고, 스타일이 필요 없다면
    `ALLOWED_UNSTYLED` 에 **왜 필요 없는지**를 적어야 통과한다 — 근거를 못 적으면
    대개 진짜 결함이다.
    """
    css = collect_css_state_classes(STATIC)
    assigned = collect_assigned_state_classes(STATIC)
    unstyled = {name: locs for name, locs in assigned.items() if name not in css and name not in ALLOWED_UNSTYLED}
    assert not unstyled, (
        "CSS 규칙도 판정 근거도 없는 상태 modifier:\n  "
        + "\n  ".join(f"{name} <- {locs[0]}" for name, locs in sorted(unstyled.items()))
        + "\n스타일을 주거나, scripts/audit_state_class_wiring.py 의 ALLOWED_UNSTYLED 에 근거를 적는다."
    )


def test_t5_tooltip_ownership_seam_is_intact():
    """툴팁 소유권(`data-title-status`) 이음매의 세 계약이 코드에 남아 있어야 한다.

    라이브 구동이 잡은 두 결함을 이 이음매가 함께 막는다 — ① `stale_error` 의 구체 문구
    ("마지막 활동: <시각>")를 폴링이 일반 라벨로 덮는 퇴화, ② 모르는 상태로 바뀔 때 직전
    상태의 툴팁이 거짓으로 남는 것. 초판은 **아무 테스트도 이 분기를 건드리지 않아** 통째로
    지워도 green 이었다 (§18.8 codex [P2]).

    ⚠ 이 검사는 **소스 형태** 검사다 — CI 가 pytest 전용이라 브라우저 실행을 여기서 돌릴 수
    없기 때문이다. 실제 동작은 PB-0008 실측이 확인했고
    (`docs/test-runs.d/TASK-20260901T1900-conv-status-dot-wiring.md` §4), 이 테스트는 그
    구조가 조용히 사라지는 것을 막는 역할이다. 둘을 같은 강도로 읽지 않는다.
    """
    poll = _strip_js_comments((STATIC / "app.js").read_text(encoding="utf-8"))
    sidebar = _strip_js_comments((STATIC / "app" / "sidebar.js").read_text(encoding="utf-8"))

    updater = re.search(r"export function _updateConversationStatusDot\b.*?\n}", poll, re.S)
    assert updater, "_updateConversationStatusDot 를 찾지 못했다 — 폴링 갱신 진입점이 옮겨갔는지 확인한다."
    body = updater.group(0)

    assert "dataset.titleStatus" in body, (
        "폴링 갱신이 툴팁 소유자(data-title-status)를 읽지 않는다 — 이 분기가 없으면 "
        "사이드바가 넣은 stale 구체 문구를 매 tick 일반 라벨로 덮는다."
    )
    assert "stale_error" in body, (
        "폴링 갱신에 stale_error 예외가 없다 — 구체 문구 보존 조건이 사라졌다."
    )
    assert 'removeAttribute("title")' in body, (
        "라벨 없는(모르는) 상태에서 title 을 지우지 않는다 — 직전 상태의 툴팁이 거짓으로 남는다."
    )
    assert "dot.dataset.titleStatus =" in sidebar, (
        "사이드바 렌더가 툴팁 소유자를 기록하지 않는다 — 폴링이 구체 문구를 구별할 근거가 사라진다."
    )


def test_t4b_allowlist_entries_are_still_in_use():
    """판정 목록이 낡지 않게 — 더 이상 쓰이지 않는 항목은 지운다.

    근거만 쌓이고 대상은 사라진 목록은 다음 사람이 "판정이 끝났다" 로 오독하는 카고컬트가 된다.
    """
    assigned = set(collect_assigned_state_classes(STATIC))
    stale = sorted(set(ALLOWED_UNSTYLED) - assigned)
    assert not stale, f"코드에서 사라진 판정 항목: {stale} — ALLOWED_UNSTYLED 에서 제거한다."
