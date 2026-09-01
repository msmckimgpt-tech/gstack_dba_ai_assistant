"""`Makefile` `test` 와 `.github/workflows/ci.yml` 의 pytest 경로 집합이 같은지 잠근다.

## 왜 구조 테스트인가 (§16.7 G10)

같은 결함 클래스가 **네 번** 재발했다:

| 시점 | 누락 | 발견 경위 |
|---|---|---|
| ~2026-08-14 | feature-0014 · 0020 | "무중단 불변식을 잠그는 테스트가 CI 에서 한 번도 돈 적 없음" |
| 〃 | feature-0023 | Makefile 에는 있고 CI 에는 없었다 |
| 2026-09-01 | feature-0041 · **0043** · 0008 | 0043 에 회귀 18건을 추가하고 나서야 "그게 CI 에서 도는가" 를 확인 |

세 번째까지의 대응은 매번 **그 경로를 목록에 추가**하는 것이었고, ci.yml 에는 이미
「이 함정을 조심하라」는 주석까지 있었다. 주석이 있는 채로 세 번 더 반복됐다 — 재발 관측이
쌓였으므로 §16.7 G10 에 따라 점수정이 아니라 **클래스를 잠그는 구조 테스트**로 승격한다.

## 왜 이 클래스가 조용한가

`pytest.ini` 의 `testpaths` 는 **인자를 명시하면 무시된다.** 두 진입점(Makefile·ci.yml)이 각자
경로를 나열하므로, 한쪽에만 추가하면 «로컬은 green 인데 CI 는 그 축을 보지 않는» 상태가 된다.
그 상태는 **아무 신호도 내지 않는다** — CI 는 초록이고, 누락된 스위트는 그냥 실행되지 않는다.

## 이 파일이 feature-0043 에 사는 이유

CI 설정을 소유한 feature 는 없다. 발견이 여기서 났고, 무엇보다 **이 디렉토리가 방금 CI 에
등재되어 실제로 도는 곳**이기 때문이다 — 돌지 않는 곳에 둔 가드는 가드가 아니다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_MAKEFILE = _REPO / "Makefile"
_CI_YML = _REPO / ".github" / "workflows" / "ci.yml"

#: `unit/<feature>/tests` 형태의 pytest 경로.
_TESTPATH = re.compile(r"unit/[A-Za-z0-9._-]+/tests\b")


def _strip_comments(text: str, marker: str = "#") -> str:
    """`#` 로 시작하는 줄을 지운다 — Makefile·YAML 모두 줄 주석이 `#` 다.

    ⚠ **존재가 아니라 «집합» 을 비교하므로 주석 제거가 필수다** (§16.7 G11-a). 두 파일의
    주석에는 이 클래스를 설명하며 feature 이름·경로가 등장한다. 주석을 남겨 두면 «목록에는
    없는데 주석에 있어서» 집합이 같아 보이는 거짓 PASS 가 난다.

    줄 단위 판정으로 충분한 이유: 두 파일 모두 `#` 가 문자열 리터럴 안에 오는 문법이 없고
    (Makefile 의 레시피·YAML 의 블록 스칼라), 여기서 뽑는 것은 경로 토큰뿐이다.
    """
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith(marker)
    )


def _makefile_paths() -> set[str]:
    src = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^test:.*?(?=^\w[\w-]*:)", src, re.M | re.S)
    assert m, "Makefile 에서 `test:` 타깃 블록을 찾지 못했다 — 파서를 갱신하라"
    return set(_TESTPATH.findall(_strip_comments(m.group(0))))


def _ci_paths() -> set[str]:
    src = _CI_YML.read_text(encoding="utf-8")
    m = re.search(r"- name: Unit tests \(pytest\).*?(?=\n      - name: |\Z)", src, re.S)
    assert m, "ci.yml 에서 'Unit tests (pytest)' 스텝을 찾지 못했다 — 파서를 갱신하라"
    return set(_TESTPATH.findall(_strip_comments(m.group(0))))


def test_parsers_find_something():
    """파서가 0개를 뽑으면 아래 집합 비교가 `set() == set()` 로 **항진 통과**한다.

    G11 의 요점 — 게이트로 쓰는 검사가 무엇도 검사하지 않는 상태를 먼저 배제한다.
    """
    mk, ci = _makefile_paths(), _ci_paths()
    assert len(mk) >= 5, f"Makefile 에서 뽑은 경로가 너무 적다({len(mk)}) — 파서가 깨졌다"
    assert len(ci) >= 5, f"ci.yml 에서 뽑은 경로가 너무 적다({len(ci)}) — 파서가 깨졌다"


def test_makefile_and_ci_run_the_same_test_paths():
    """두 진입점이 **같은 집합**을 돌린다.

    한쪽에만 있는 경로는 곧 «그 스위트가 한쪽에서 안 도는» 상태다. 로컬만 도는 것은 CI 사각,
    CI 만 도는 것은 개발 중 미검출 — 어느 방향이든 결함이다.
    """
    mk, ci = _makefile_paths(), _ci_paths()
    only_mk = sorted(mk - ci)
    only_ci = sorted(ci - mk)
    assert not only_mk, (
        f"Makefile `test` 에만 있고 CI 에는 없는 테스트 경로: {only_mk} — "
        "그 스위트는 CI 에서 한 번도 돌지 않는다(pytest.ini testpaths 는 인자 명시 시 무시됨). "
        ".github/workflows/ci.yml 의 'Unit tests (pytest)' 스텝에 추가하라."
    )
    assert not only_ci, (
        f"CI 에만 있고 Makefile `test` 에는 없는 테스트 경로: {only_ci} — "
        "개발자가 로컬 `make test` 로는 그 축을 보지 못한다. Makefile `test` 타깃에 추가하라."
    )


@pytest.mark.parametrize("d", [
    "unit/feature-0041-external-ai-tool-surface/tests",
    "unit/feature-0043-external-llm-bridge/tests",
    "unit/feature-0008-windows-browser-testing/tests",
])
def test_the_three_newly_registered_dirs_are_in_ci(d):
    """2026-09-01 에 등재한 3개가 CI 목록에 실제로 있는지 — 되돌림 방지.

    위 집합 비교는 «양쪽이 똑같이 빠지면» 통과한다(둘 다에서 지우는 회귀). 이 단언이 그 구멍을
    메운다 — 이 셋은 등재된 채로 남아야 한다.
    """
    assert d in _ci_paths(), f"{d} 가 CI pytest 목록에서 빠졌다"
