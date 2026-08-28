"""feature-0043 P0-AD — codex 적대 리뷰가 실행해서 보여 준 것들 (REV-20260828T193000).

## 왜 파일이 따로 있나

앞 스위트(`test_ai_assisted_setup.py`)가 **62건 green 인 상태에서** codex 가 아래 값들을
그대로 통과시켰다:

    BRIDGE_PROBED_AI=rm
    BRIDGE_PROBED_ARGS='--workers .'
    BRIDGE_PROBED_ARGS='--workers 1..2'
    BRIDGE_PROBED_ARGS='--workers 999999999'

테스트가 있다는 것과 그 테스트가 결함을 잡는다는 것은 다르다. 앞 스위트는 「내가 막으려고
생각한 것」을 검사했고, 이 파일은 「막았다고 **믿었는데** 안 막힌 것」을 검사한다. 섞지 않고
분리해 두는 이유는 그 출처를 잃지 않기 위해서다 — 다음에 같은 형태의 자기확신이 생겼을 때,
이 파일이 「내 뮤턴트만으로는 부족했다」는 증거로 남는다.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_ai_assisted_setup import (  # noqa: E402  — 같은 디렉터리의 헬퍼 재사용
    _INDEX_HTML,
    _AIC_HTML,
    _OAUTH_AS,
    _SETUP_PS1,
    _SETUP_SH,
    _load_launch_ns,
    _run_probe,
    _slice_probe_section,
)


def _instruction() -> str:
    return _load_launch_ns()["compose_probe_setup_instruction"](posix="P", windows="W")


# ── P1: 실존 검사는 「무엇인지」를 확인하지 않는다 ───────────────────────────


@pytest.mark.parametrize("val", ["rm", "sh", "curl", "bash", "python3", "git"])
def test_probed_ai_rejects_arbitrary_executables_on_path(val):
    """PATH 에 있다는 것만으로 통과시키지 않는다 (codex 실측: `BRIDGE_PROBED_AI=rm` 통과).

    통과하면 `--ai rm` 이 되고, 러너는 그것을 **AI CLI 로 실행**한다. 실존 검사는 「없는
    것을 거르는」 장치이지 「무엇인지 확인하는」 장치가 아니었다.
    """
    args, err = _run_probe({"BRIDGE_PROBED_AI": val})
    assert "--ai" not in args, f"{val!r} 이 AI 런타임으로 통과했다"
    assert "알려진 AI CLI 가 아닙니다" in err


def test_known_ai_list_matches_between_installer_and_instruction():
    """설치기가 받는 목록 = 지시문이 안내하는 목록 = ps1 목록.

    한쪽이 넓으면 AI 가 그 이름을 채우고 다른 쪽이 버려서, 사용자는 "왜 반영이 안 되지" 를
    겪는다(버린 사실은 stderr 경고로만 보인다).
    """
    sh_known = set(re.search(r'_KNOWN_AI_CLIS="([^"]+)"',
                             _SETUP_SH.read_text(encoding="utf-8")).group(1).split())
    ps_known = set(re.findall(r"'([a-z]+)'",
                              re.search(r"\$KnownAiClis = @\(([^)]+)\)",
                                        _SETUP_PS1.read_text(encoding="utf-8")).group(1)))
    advertised = set(re.search(r"_PROBED_AI_ALLOWLIST = \(([^)]+)\)",
                               _OAUTH_AS.read_text(encoding="utf-8"))
                     .group(1).replace('"', " ").replace(",", " ").split())
    assert sh_known == ps_known == advertised, f"sh={sh_known} ps1={ps_known} 안내={advertised}"


# ── P2: 수치 축은 타입과 범위로 봐야 한다 ───────────────────────────────────


@pytest.mark.parametrize("raw", [
    "--workers .",            # codex 실측: 통과했다
    "--workers 1..2",         # codex 실측: 통과했다
    "--workers 999999999",    # codex 실측: 통과했다 — 조사 결과가 아니라 사고다
    "--max-workers 999999999",
    "--workers 0",
    "--workers 1.5",          # 러너 쪽이 int — 통과시키면 러너가 argparse 로 죽는다
    "--ai-timeout .",
    "--ai-timeout 0",
    "--ai-timeout 99999999",
    "--worker-idle-sec 1..2",
])
def test_numeric_axes_are_typed_and_bounded(raw):
    """`*[!0-9.]*` 하나로 뭉뚱그리면 `.` 과 `1..2` 가 통과한다.

    그 값은 러너의 argparse 에서 죽고, 사용자는 설치가 끝난 줄 알았다가 "러너가 바로
    종료됐다" 만 본다 — 설치기가 green 인데 러너가 못 뜨는, 가장 진단하기 어려운 형태다.
    """
    args, err = _run_probe({"BRIDGE_PROBED_ARGS": raw})
    assert args == "", f"버려지지 않았다: {raw!r} -> {args!r}"
    assert "⚠" in err


@pytest.mark.parametrize("raw", [
    "--workers 1", "--workers 64", "--max-workers 8",
    "--ai-timeout 1", "--ai-timeout 86400", "--worker-idle-sec 90",
    "--worker-idle-sec 0.5" if False else "--ai-timeout 300.5",
])
def test_bounds_still_allow_reasonable_values(raw):
    """경계를 좁히다가 정상값까지 죽이지 않는다 — 그러면 이 기능이 있으나 마나가 된다."""
    args, _err = _run_probe({"BRIDGE_PROBED_ARGS": raw})
    assert args.split() == raw.split(), f"정상값이 버려졌다: {raw}"


def test_native_handler_mode_is_not_advertised():
    """구현이 `auto` 와 같은 선택지를 공개하지 않는다 (codex P2-8).

    사용자는 판단값을 준 줄 알지만 동작은 바뀌지 않는다 — 그 괴리는 어디에도 드러나지 않는다.
    """
    _args, err = _run_probe({"BRIDGE_PROBED_HANDLER": "native"})
    assert "auto|none" in err, "native 가 여전히 유효한 값이다"
    assert "native" not in _instruction(), "지시문이 없는 모드를 안내한다"


def test_python_search_order_is_the_same_everywhere():
    """탐색 순서가 sh · ps1 · 지시문에서 같다 (codex P2-6).

    같은 머신에서 OS 판마다 다른 인터프리터가 뽑히면, 그것이 곧 이 기능이 없애려는
    "환경마다 다른 결과" 다.
    """
    assert "for cand in python3 python; do" in _SETUP_SH.read_text(encoding="utf-8")
    assert "@('python3','python','py')" in _SETUP_PS1.read_text(encoding="utf-8"), \
        "ps1 이 python 을 먼저 찾는다"
    assert "`python3` → `python`" in _instruction()


# ── P1: 검증되지 않는 동일성 주장 ───────────────────────────────────────────


@pytest.mark.parametrize("html", [_INDEX_HTML, _AIC_HTML])
def test_ui_does_not_claim_identical_results(html):
    """화면이 "결과가 같다" 고 단정하지 않는다.

    같은 머신에서도 AI 마다 다른 값을 고를 수 있다 — 핸들러 등록 여부·실행 AI·워커 수가
    갈린다. **스크립트가 같다**는 것과 **결과가 같다**는 것은 다른 주장이고, 후자는 우리가
    보장할 수 없다.
    """
    src = html.read_text(encoding="utf-8")
    assert "결과는 ①과 같습니다" not in src and "결과는 1단계와 같습니다" not in src, (
        f"{html.name}: 검증되지 않는 동일성 주장이 남아 있다")
    assert "AI마다 다를 수 있습니다" in src, f"{html.name}: 비결정성 고지가 없다"


def test_instruction_draws_the_line_at_the_unvalidated_human_slot():
    """`BRIDGE_ARGS` 를 채우지 말라고 명시한다 (provenance gap 완화).

    스크립트는 **누가 채웠는지 알 수 없다** — 사람 칸은 무검증이므로 AI 가 그쪽에 넣으면
    allowlist 를 통째로 우회한다. 강제할 수단이 없으니 지시로 선을 긋는 것이 할 수 있는
    전부이고, 그 한계 자체는 REVIEW 에 적었다.
    """
    probe = _instruction()
    assert "BRIDGE_ARGS" in probe and "검증을 거치지 않는다" in probe


# ── P2-9: 문자열이 아니라 실제 argv 로 확인한다 ─────────────────────────────


def _expand_runner_args(env_extra: dict) -> list[str]:
    """검증을 통과한 값이 **실제 argv 로** 어떻게 전개되는지 본다.

    문자열 포함 여부만 보면 따옴표·글로빙으로 깨진 argv 를 정상으로 판정한다(codex P2-7 이
    지적한 형태). `set --` 로 실제 전개해 토큰 경계를 확인한다.
    """
    marker = "__ARGV__"
    script = (_slice_probe_section()
              + "\nset -- $RUNNER_ARGS\n"
              + f'printf "{marker}"\n'
              + 'for a in "$@"; do printf "[%s]" "$a"; done\n')
    env = {"BRIDGE_BASE": "https://h.example", "BRIDGE_TOKEN": "mat_x",
           "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}
    env.update(env_extra)
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          env=env, timeout=60, cwd="/tmp")
    assert proc.returncode == 0, proc.stderr
    tail = proc.stdout.split(marker, 1)[1]
    return re.findall(r"\[([^\]]*)\]", tail)


def test_real_argv_is_built_not_just_a_string():
    """검증을 통과한 값이 의도한 **토큰 경계**로 전개된다."""
    assert _expand_runner_args({"BRIDGE_PROBED_ARGS": "--workers 4 --refresh-caps"}) == \
        ["--workers", "4", "--refresh-caps"]


def test_quoted_group_in_human_slot_is_documented_as_not_preserved():
    """사람 칸의 따옴표 그룹이 보존되지 않는다는 **사실과 문서가 맞는가**.

    이건 이 변경이 만든 결함이 아니라 원래 동작이다(비인용 전개). 그러나 "기존 호환" 이라고
    쓰면서 한계를 숨기면 주장이 코드보다 넓어진다 — 이 feature 에서 반복된 실패 형태다.
    그래서 문서에 적고, **그 문서가 사실인지도** 여기서 확인한다.
    """
    assert "따옴표 그룹은 보존되지 않는다" in _SETUP_SH.read_text(encoding="utf-8")
    argv = _expand_runner_args({"BRIDGE_ARGS": "--cmd 'my-ai -p {prompt}'"})
    assert argv == ["--cmd", "'my-ai", "-p", "{prompt}'"], (
        f"문서는 '보존되지 않는다' 인데 실제는 다르다: {argv}")


def test_glob_in_human_slot_does_not_expand_into_cwd_files():
    """비인용 전개는 글로빙도 탄다 — 그 사실이 실제로 어떤 모양인지 고정한다.

    `/tmp` 에서 돌리면 그 디렉터리의 파일 이름이 인자로 들어올 수 있다. 이것도 원래 동작이고,
    여기서는 **모른 채로 두지 않는 것**이 목적이다.
    """
    argv = _expand_runner_args({"BRIDGE_ARGS": "--workers 4"})
    assert argv == ["--workers", "4"], f"평범한 값이 글로빙으로 바뀌었다: {argv}"
