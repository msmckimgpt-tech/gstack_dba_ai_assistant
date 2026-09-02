"""AI CLI 허용목록 3자리 ↔ 러너 정본(`_RUNTIME_SPECS`) 동기화 잠금.

## 무엇을 막는가 (ROADMAP ITEM-05 · RESEARCH §1.1, 실측 2026-09-02)

`ollama` 가 러너에서 제거됐는데(P0-Z6.1, 사용자 결정 2026-09-01) **설치 스크립트와 서버 안내에는
남아 있었다.** 결과: `BRIDGE_PROBED_AI='ollama'` 를 채운 사용자는 **설치 단계를 통과하고
런타임에서 실패**한다 — 러너의 `_CLI_ADAPTERS` 는 `_RUNTIME_SPECS` 파생이라 그 이름을 모른다.

`oauth_as.py` 의 종전 주석은 *"설치 스크립트의 `_KNOWN_AI_CLIS` 와 같은 목록이어야 한다"* 였고
그 계약은 **지켜지고 있었다.** 그런데 세 자리가 서로 일치한 채 **셋 다 러너와 갈렸다.** 서로를
대조하는 계약은 **정본을 지목하지 않으면 «함께 틀린» 상태를 잡지 못한다** — 이 테스트가 그
정본을 `_RUNTIME_SPECS` 로 못박는다.

## 왜 파싱인가 (import 가 아니라)

세 자리가 sh · PowerShell · Python 으로 **언어가 다르고**, 러너 정본은 `agent/runtimes.py`(패키지
소스)인데 기존 테스트들이 쓰는 `src/bridge_agent.py` 는 **빌드 생성물**(`.gitignore` 등재)이라
clean checkout 에 없을 수 있다. 그래서 정본은 `ast` 로, 소비처 셋은 텍스트로 읽는다 — 어느 것도
빌드·실행 환경에 의존하지 않는다.

## 커버리지 경계 (정직한 한계)

이 테스트는 **이름 목록의 집합 일치**만 본다. 「그 CLI 가 실제로 동작하는가」는 보지 않는다
(그건 라이브 왕복의 몫). 그리고 **열거 지점을 새로 만들면 이 테스트는 그것을 모른다** — 그래서
`test_no_new_hardcoded_runtime_lists` 가 «하드코딩된 런타임 이름 나열» 자체를 전 파일에서 훑는다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_BRIDGE = _UNIT / "feature-0043-external-llm-bridge" / "src"
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"

_RUNTIMES_PY = _BRIDGE / "agent" / "runtimes.py"
_SETUP_SH = _BRIDGE / "bridge_setup.sh"
_SETUP_PS1 = _BRIDGE / "bridge_setup.ps1"
_OAUTH_AS = _WEB / "routers" / "oauth_as.py"

#: 러너가 더 이상 지원하지 않는 런타임. 소비처 어디에도 남으면 안 된다.
#: (P0-Z6.1 이 지운 것 — 이 상수는 «지워진 것이 되살아나지 않게» 하는 회귀 앵커다.)
_REMOVED_RUNTIMES = ("ollama",)


def _canon_runtimes() -> set[str]:
    """정본 = `agent/runtimes.py` 의 `_RUNTIME_SPECS` 최상위 키.

    `ast` 로 읽는다 — import 하면 그 모듈의 의존성·부수효과를 함께 끌고 오고, 이 테스트가
    검사하려는 것은 «값» 이 아니라 «표에 적힌 이름» 이다.
    """
    tree = ast.parse(_RUNTIMES_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == "_RUNTIME_SPECS" for t in targets):
            continue
        value = node.value
        assert isinstance(value, ast.Dict), "_RUNTIME_SPECS 가 dict 리터럴이 아니다"
        keys = set()
        for k in value.keys:
            assert isinstance(k, ast.Constant) and isinstance(k.value, str), (
                "_RUNTIME_SPECS 키가 문자열 리터럴이 아니다 — 이 테스트의 파싱 전제가 깨졌다")
            keys.add(k.value)
        assert keys, "_RUNTIME_SPECS 가 비었다"
        return keys
    pytest.fail(f"{_RUNTIMES_PY} 에서 `_RUNTIME_SPECS` 대입을 찾지 못했다")


# ── 정본 선언 라인의 패턴 ────────────────────────────────────────────────────
#
# ⚠ **표기 변형에 대한 태도 (codex 적대 리뷰 P2-2, 2026-09-02)**: 아래 패턴은 따옴표 종류와
# `readonly`·타입 주석 정도의 변형까지 받는다. 그래도 재작성 방식에 따라 못 찾을 수 있는데,
# 그 때는 `assert m` 이 **큰 소리로 실패**한다 — fail-open 이 아니다. 이 테스트가 잡으려는
# 결함(목록이 조용히 갈리는 것)에 비해 «정규식이 못 읽어서 실패» 는 즉시 눈에 띄고 고치기 쉽다.
# 두 오류의 값이 다르므로 fail-loud 쪽으로 기운다.
_SH_DECL = re.compile(r'^\s*(?:readonly\s+)?_KNOWN_AI_CLIS=(["\'])(.*?)\1', re.M)
_PS1_DECL = re.compile(r"^\s*\$KnownAiClis\s*=\s*@\(([^)]*)\)", re.M)
_PY_DECL = re.compile(r"^_PROBED_AI_ALLOWLIST(?:\s*:[^=]+)?\s*=\s*[\(\[]([^)\]]*)[\)\]]", re.M)


def _sh_allowlist() -> set[str]:
    m = _SH_DECL.search(_SETUP_SH.read_text(encoding="utf-8"))
    assert m, "bridge_setup.sh 에서 `_KNOWN_AI_CLIS=\"...\"` 를 찾지 못했다"
    return set(m.group(2).split())


def _ps1_allowlist() -> set[str]:
    m = _PS1_DECL.search(_SETUP_PS1.read_text(encoding="utf-8"))
    assert m, "bridge_setup.ps1 에서 `$KnownAiClis = @(...)` 를 찾지 못했다"
    return set(re.findall(r"""['"]([^'"]+)['"]""", m.group(1)))


def _server_allowlist() -> set[str]:
    """`oauth_as.py` 의 `_PROBED_AI_ALLOWLIST` — feature-0003 은 import 할 수 없다(conftest 규약)."""
    m = _PY_DECL.search(_OAUTH_AS.read_text(encoding="utf-8"))
    assert m, "oauth_as.py 에서 `_PROBED_AI_ALLOWLIST = (...)` 를 찾지 못했다"
    return set(re.findall(r"""['"]([^'"]+)['"]""", m.group(1)))


def _code_lines(path: Path):
    """주석을 제외한 (lineno, line) — sh·ps1 은 `#`, py 는 `#`.

    문자열 리터럴 안의 `#` 은 구분하지 않는다(휴리스틱). 검사 대상이 «이름이 적혀 있는가» 라
    과탐이 나면 그 자리를 파생으로 바꾸면 되므로, 미탐보다 과탐 쪽으로 둔다.
    """
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield lineno, line


_CONSUMERS = (
    ("bridge_setup.sh `_KNOWN_AI_CLIS`", _sh_allowlist),
    ("bridge_setup.ps1 `$KnownAiClis`", _ps1_allowlist),
    ("oauth_as.py `_PROBED_AI_ALLOWLIST`", _server_allowlist),
)


@pytest.mark.parametrize("label,getter", _CONSUMERS, ids=[c[0] for c in _CONSUMERS])
def test_consumer_allowlist_equals_runner_canon(label, getter):
    """소비처 목록 == 러너 정본. **집합 일치**를 요구한다(부분집합이 아니라).

    - 소비처가 **넓으면**: 설치는 통과하고 런타임에서 실패한다(원 결함).
    - 소비처가 **좁으면**: 러너가 지원하는 런타임을 사용자가 지목할 수 없다(조용한 기능 상실).

    두 방향 모두 사용자에게 «되는 줄 알았는데 안 되는» 상태이므로 한쪽만 막지 않는다.
    """
    canon = _canon_runtimes()
    actual = getter()
    assert actual == canon, (
        f"{label} 이 러너 정본(`_RUNTIME_SPECS`)과 다르다.\n"
        f"  정본에만: {sorted(canon - actual)}\n"
        f"  {label} 에만: {sorted(actual - canon)}\n"
        f"  정본 = {_RUNTIMES_PY}")


@pytest.mark.parametrize("label,getter", _CONSUMERS, ids=[c[0] for c in _CONSUMERS])
def test_removed_runtimes_do_not_come_back(label, getter):
    """P0-Z6.1 이 지운 런타임이 소비처 **허용목록**에 되살아나지 않는다.

    위 집합 일치 테스트가 이미 덮지만, 이쪽은 **왜 없어야 하는지**를 이름으로 남긴다 —
    집합이 우연히 맞아도 `ollama` 가 돌아오면 여기서 먼저 이름을 대고 실패한다.
    """
    actual = getter()
    for name in _REMOVED_RUNTIMES:
        assert name not in actual, (
            f"{label} 에 `{name}` 이 되살아났다 — P0-Z6.1(2026-09-01)에서 러너가 제거한 런타임이다. "
            f"설치는 통과하고 런타임에서 실패한다.")


@pytest.mark.parametrize("path", (_SETUP_SH, _SETUP_PS1, _OAUTH_AS), ids=lambda p: p.name)
def test_removed_runtimes_absent_from_whole_file(path):
    """제거된 런타임 이름이 **파일 어디에도** 코드로 남지 않는다 (허용목록 밖 포함).

    ⚠ **codex 적대 리뷰 P2-1 (2026-09-02) 이 연 구멍을 닫는다.** 초판은 이 전수 스캔을 설치
    스크립트 **둘에만** 걸었다. 그래서 `oauth_as.py` 의 안내 문구에 `claude·ollama` 처럼 써도
    ① 허용목록 파싱은 정상(목록 자체엔 없음) ② 하드코딩 census 는 정본 이름만 세므로 hit 1개로
    통과 — **아무 테스트도 잡지 못했다.** 원 결함이 정확히 「사용자 대면 문구에 남은 이름」이었다.

    설치 경로 후보(`%LOCALAPPDATA%\\Programs\\Ollama`)도 이 스캔이 함께 덮는다 — 목록만 지우고
    경로를 남기면 「없앴다는데 아직 찾아다닌다」가 된다(러너 `agent/discovery.py` 의 같은 자리
    주석 참조). **주석은 남아도 된다** — 왜 지웠는지를 남기는 자리다.
    """
    for lineno, line in _code_lines(path):
        for name in _REMOVED_RUNTIMES:
            assert name not in line.lower(), (
                f"{path.name}:{lineno} 에 제거된 런타임 `{name}` 이 코드로 남아 있다: {line.strip()}")


def test_user_facing_handoff_derives_names_from_the_allowlist():
    """외부 AI 가 읽는 지시문이 런타임 이름을 **하드코딩하지 않는다**.

    이 줄이 원래 `claude·codex·gemini·ollama` 를 손으로 적고 있었다 — 즉 목록을 지목하는 자리가
    넷이었고, 그래서 넷이 따로 틀렸다. 파생시키면 자리가 하나로 줄어든다(§16.7 G10 — 재발 관측된
    결함 클래스는 구조로 잠근다).
    """
    src = _OAUTH_AS.read_text(encoding="utf-8")
    assert "_PROBED_AI_ALLOWLIST)}를 자동으로 찾아 쓴다" in src or \
           "'·'.join(_PROBED_AI_ALLOWLIST)" in src, (
        "핸드오프 지시문이 `_PROBED_AI_ALLOWLIST` 에서 파생되지 않는다 — 이름을 손으로 적으면 "
        "그 자리가 다시 독립적으로 낡는다")
    # 하드코딩된 나열이 남아 있지 않은지 직접 확인 (파생 도입이 «추가» 였고 옛 줄이 남는 경우).
    for lineno, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        assert "claude·codex·gemini" not in line, (
            f"oauth_as.py:{lineno} 에 런타임 이름이 하드코딩돼 있다 — "
            f"`_PROBED_AI_ALLOWLIST` 에서 파생시켜라: {line.strip()}")


def test_no_new_hardcoded_runtime_lists():
    """열거 지점이 **새로 생기는 것**을 막는다 (모수 = 소비처 파일 전체).

    위 테스트들은 «내가 아는 3자리» 만 본다. 네 번째 자리가 생기면 그것들은 침묵한다 —
    실제로 이번에 발견된 5건 중 2건(ps1 설치 경로 · 핸드오프 문장)이 정확히 그 사각지대였다.
    그래서 「런타임 이름을 2개 이상 나란히 적은 코드 라인」 자체를 훑는다.

    **한계**: 휴리스틱이다. 이름을 변수로 쪼개 적으면 통과한다. 이 테스트가 잡는 것은
    «무심코 또 나열하는» 흔한 형태이고, 의도적 우회를 막는 장치가 아니다.
    """
    canon = sorted(_canon_runtimes())
    offenders: list[str] = []
    for path, decl in ((_SETUP_SH, _SH_DECL), (_SETUP_PS1, _PS1_DECL), (_OAUTH_AS, _PY_DECL)):
        for lineno, line in _code_lines(path):
            # ⚠ **면제는 «정본 선언 라인» 에만 준다** (codex 적대 리뷰 P2-3, 2026-09-02).
            #   초판은 `"ALLOWLIST" not in line` 이라, `OTHER_ALLOWLIST = "claude codex gemini"`
            #   같은 **새 열거**가 그 문자열을 포함한다는 이유만으로 통째로 면제됐다 —
            #   막으려던 것이 면제 조건이 되는 형태였다.
            if decl.match(line) or decl.search(line):
                continue
            hits = [n for n in canon if re.search(rf"\b{re.escape(n)}\b", line)]
            if len(hits) >= 2:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "런타임 이름이 나열된 새 자리가 생겼다 — 허용목록에서 파생시켜라:\n  "
        + "\n  ".join(offenders))
