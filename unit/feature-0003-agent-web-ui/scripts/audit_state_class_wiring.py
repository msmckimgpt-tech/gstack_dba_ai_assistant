"""상태 modifier 클래스(`is-*` / `has-*`)의 CSS 배선 감사 — 재현 가능한 단일 구현.

**배선** = 「코드가 부여하는 상태 클래스」와 「그 상태에 시각을 주는 CSS 규칙」의 짝.
한쪽만 있으면 끊긴 것이다:

  · 코드만 있고 CSS 가 없다  → 상태가 계산되는데 화면에 드러나지 않는다 (사용자가 신고하는 쪽)
  · CSS 만 있고 코드가 없다  → 죽은 규칙. 대개 어휘 drift 의 흔적이라 옆에서 진짜 결함이 난다

conv-status-dot-wiring cycle 이 이 모듈을 만든 계기: 사이드바 대화 상태 dot 이 `is-${status}`
로 조립되는데 CSS 는 `.conv-dot.is-completed`(아무도 만들지 않는 값)를 갖고 있었고, 정작
서버가 쓰는 `done`·`error`·`canceled` 는 규칙이 없었다. 눈으로는 「처리 중만 색이 보인다」로
나타났고, 클래스는 붙어 있으니 코드 리뷰로는 정상처럼 읽혔다.

`tests/test_conv_status_dot_wiring.py` 가 이 모듈을 import 해 CI 게이트로 쓴다.
사람이 직접 훑고 싶으면:  python3 scripts/audit_state_class_wiring.py [static_dir]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

#: 상태 modifier 로 인정하는 이름 꼴. 이 저장소의 규약은 `is-` / `has-` 다.
#: (`in-block` 류의 `in-` 은 vendor 번들의 easing 이름과 충돌해 대상에서 뺀다.)
STATE_RE = re.compile(r"^(?:is|has)-[a-z0-9][-\w]*$")

#: 감사 대상에서 제외 — 서드파티 번들은 우리 CSS 와 짝을 이루지 않는다.
SKIP_PARTS = ("vendor/",)

#: 코드가 클래스를 **부여**하는 자리만 본다. `querySelector(".is-gap")` 처럼 읽기만 하는
#: 자리는 배선의 한쪽 끝이 아니므로 세지 않는다.
ASSIGN_RE = re.compile(
    r"""(?:\.className\s*=\s*|classList\.(?:add|toggle)\(|\.push\(|\bclass\s*=\s*)"""
    r"""(["'`])(.*?)\1""",
    re.S,
)
HTML_CLASS_RE = re.compile(r"""class=(["'])(.*?)\1""", re.S)

#: `${...}` 로 값이 주입되는 자리. 문자열만 봐서는 어휘를 못 읽으므로 별도로 보고한다.
DYNAMIC_RE = re.compile(r"(?:is|has)-\$\{[^}]*\}")


def _iter_files(root: Path, suffixes: tuple[str, ...]):
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in rel for part in SKIP_PARTS):
            continue
        yield path, rel


def _strip_css_comments(text: str) -> str:
    # 주석 속 예시 셀렉터가 "규칙이 있다" 로 오탐되면 게이트가 조용히 무력해진다.
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def collect_css_state_classes(root: Path) -> dict[str, list[str]]:
    """CSS 셀렉터에 등장하는 상태 modifier → 등장 위치."""
    found: dict[str, list[str]] = defaultdict(list)
    for path, rel in _iter_files(root, (".css",)):
        text = _strip_css_comments(path.read_text(encoding="utf-8", errors="replace"))
        for lineno, line in enumerate(text.splitlines(), 1):
            # 셀렉터 줄만 — 선언 블록의 값(`background: ...`)은 클래스가 아니다.
            if "{" not in line and not line.rstrip().endswith(","):
                continue
            selector = line.split("{", 1)[0]
            for match in re.finditer(r"\.([A-Za-z_][-\w]*)", selector):
                name = match.group(1)
                if STATE_RE.match(name):
                    found[name].append(f"{rel}:{lineno}")
    return dict(found)


def collect_css_rules_for(root: Path, base: str) -> dict[str, list[str]]:
    """`.<base>.<modifier>` 형태로 정의된 modifier → 위치. (예: base="conv-dot")

    줄 단위가 아니라 파일 전체를 훑는다 — 콤마로 이어진 셀렉터가 여러 줄에 걸쳐 있어도
    놓치지 않기 위해서다.
    """
    found: dict[str, list[str]] = defaultdict(list)
    pattern = re.compile(rf"\.{re.escape(base)}\.((?:is|has)-[a-z0-9][-\w]*)")
    for path, rel in _iter_files(root, (".css",)):
        text = _strip_css_comments(path.read_text(encoding="utf-8", errors="replace"))
        for match in pattern.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            found[match.group(1)].append(f"{rel}:{lineno}")
    return dict(found)


def collect_css_declarations_for(root: Path, base: str) -> dict[str, list[str]]:
    """`.<base>.<modifier>` 규칙의 **선언 본문**을 모은다 → {modifier: [declaration, ...]}.

    셀렉터 이름의 존재만 보면 `.conv-dot.is-done {}` 이나 `color` 만 바꾸는 규칙도 "규칙 있음"
    으로 읽힌다 — 그런데 이번 결함의 관측값은 **배경색**이었다. 무엇을 선언했는지까지 봐야
    "상태가 화면에 도달한다" 를 말할 수 있다(§18.8 codex [P2]).
    """
    found: dict[str, list[str]] = defaultdict(list)
    sel_pattern = re.compile(rf"\.{re.escape(base)}\.((?:is|has)-[a-z0-9][-\w]*)")
    for path, rel in _iter_files(root, (".css",)):
        text = _strip_css_comments(path.read_text(encoding="utf-8", errors="replace"))
        # `<셀렉터 그룹> { <선언> }` 블록 단위 — 콤마로 묶인 그룹의 각 modifier 에 같은 본문을 준다.
        for block in re.finditer(r"([^{}]*)\{([^{}]*)\}", text):
            selector, body = block.group(1), block.group(2)
            for match in sel_pattern.finditer(selector):
                found[match.group(1)].append(body.strip())
    return dict(found)


def _resolve_interpolation(text: str) -> str:
    """`${...}` 를 **그 안의 문자열 리터럴**로 치환한다 (통째로 지우지 않는다).

    `${checked ? " is-checked" : ""}` 처럼 조건식 안에서만 부여되는 상태 클래스가 실재한다
    (`app/attach-diff.js`). 보간부를 통째로 비우면 그 클래스가 「부여됨」 집합에서 사라지고,
    그러면 해당 CSS 규칙을 지워도 게이트가 조용히 통과한다 — 감사가 스스로 만든 사각지대다
    (§18.8 codex [P2]). 리터럴이 없는 진짜 동적 조립(`is-${status}`)은 그대로 비워져
    `collect_dynamic_sites` 가 따로 보고한다.
    """
    def _keep_literals(match: re.Match) -> str:
        inner = match.group(0)[2:-1]
        return " " + " ".join(re.findall(r"[\"'`]([^\"'`]*)[\"'`]", inner)) + " "
    return re.sub(r"\$\{[^}]*\}", _keep_literals, text)


def collect_assigned_state_classes(root: Path) -> dict[str, list[str]]:
    """코드(JS/HTML)가 **부여**하는 상태 modifier → 부여 위치."""
    found: dict[str, list[str]] = defaultdict(list)
    for path, rel in _iter_files(root, (".js", ".html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for regex, group in ((ASSIGN_RE, 2), (HTML_CLASS_RE, 2)):
            for match in regex.finditer(text):
                body = _resolve_interpolation(match.group(group))
                lineno = text.count("\n", 0, match.start()) + 1
                for token in re.split(r"[^\w-]+", body):
                    if STATE_RE.match(token or "") and not token.endswith("-"):
                        found[token].append(f"{rel}:{lineno}")
    return dict(found)


def collect_dynamic_sites(root: Path) -> list[tuple[str, int, str]]:
    """`is-${...}` 처럼 어휘를 정적으로 못 읽는 조립 지점 (수동 대조가 필요한 자리)."""
    sites: list[tuple[str, int, str]] = []
    for path, rel in _iter_files(root, (".js", ".html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for match in DYNAMIC_RE.finditer(line):
                sites.append((rel, lineno, match.group(0)))
    return sites


#: 「CSS 규칙이 없어도 배선이 끊긴 것이 아니다」로 판정한 상태 modifier 와 그 근거.
#:
#: 여기에 넣는 것은 면제가 아니라 **판정 기록**이다. 근거 없이 추가하지 않는다 — 근거를
#: 적을 수 없다면 그건 대개 진짜 결함이다.
ALLOWED_UNSTYLED: dict[str, str] = {
    "is-gap": (
        "diff 표의 접힌 구간 행. 시각은 행 내부 요소(`_gapRow` 가 만드는 확장 버튼)가 담당하고, "
        "이 클래스는 `tr.attach-diff-row:not(.is-gap)` 셀렉터용 JS hook 이다."
    ),
    "is-plain": (
        "diff 가 아닌 원문 보기 행. 추가/삭제 배경을 **주지 않는 것**이 곧 이 상태의 표현이라 "
        "규칙이 없는 것이 정상이다(있으면 원문에 diff 색이 번진다)."
    ),
    "is-source": "첨부 원문 보기 표의 기본 형태. 특수 배치가 필요한 쪽은 `.is-split` 뿐이다.",
    "is-unified": "단일 열 diff 표의 기본 형태. 2열 배치가 필요한 `.is-split` 만 규칙을 갖는다.",
    "is-chain": (
        "「전체 버전 복구」 버튼. 단일 복구(↩)와 글리프(⇤)·title·aria-label 로 이미 구분되며 "
        "색·형태 차이를 더하면 같은 줄의 액션 두 개가 서로 경쟁한다."
    ),
    "is-group": (
        "그룹 대화 행 표식. 시각은 `.conv-item-group-badge`(사람 아이콘 + 멤버 수)가 전담하고 "
        "이 클래스는 현재 CSS·JS 어디서도 읽히지 않는다 — 제거 후보로 REPORT §8 에 이월."
    ),
    "is-enabled": (
        "프로필 화면의 권한 pill. 렌더되는 pill 은 **전부** 이 값이라 상태 변별력이 없다. "
        "이 화면의 실제 문제는 base 클래스(`permission-pill`·`perm-*`) 자체의 무스타일이며 "
        "상태 배선 축이 아니라 별도 항목으로 REPORT §8 에 이월."
    ),
}


def report(root: Path) -> int:
    css = collect_css_state_classes(root)
    assigned = collect_assigned_state_classes(root)

    unstyled = {k: v for k, v in assigned.items() if k not in css and k not in ALLOWED_UNSTYLED}
    print(f"### 배선 끊김 — 코드가 부여하지만 CSS 규칙 없음 ({len(unstyled)}건)")
    for name in sorted(unstyled):
        print(f"  {name:26s} <- {unstyled[name][0]}")

    allowed = {k: v for k, v in assigned.items() if k in ALLOWED_UNSTYLED}
    print(f"\n### 판정 완료 — 무스타일이 정상 ({len(allowed)}건)")
    for name in sorted(allowed):
        print(f"  {name:26s} {ALLOWED_UNSTYLED[name][:80]}…")

    print(f"\n### 동적 조립 지점 — 어휘 수동 대조 필요 ({len(collect_dynamic_sites(root))}건)")
    for rel, lineno, token in collect_dynamic_sites(root):
        print(f"  {rel}:{lineno}  {token}")

    return 1 if unstyled else 0


if __name__ == "__main__":  # pragma: no cover - 사람이 직접 훑을 때만
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "src" / "static"
    raise SystemExit(report(target.resolve()))
