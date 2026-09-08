"""All test entrypoints inherit the suite list from pyproject.toml.

Comparing only Makefile and CI missed feature-0046 because both omitted it.
Explicit pytest paths override testpaths, so shared configuration must remain
in control of collection rather than keeping three synchronized copies.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
# Frozen pre-consolidation coverage: future suites are added only to testpaths.
_EXISTING_SUITES = frozenset({
    "unit/feature-0002-agent-core/tests",
    "unit/feature-0003-agent-web-ui/tests",
    "unit/feature-0023-conversation-api-access/tests",
    "unit/feature-0014-zero-downtime-deploy/tests",
    "unit/feature-0020-zd-deploy-all/tests",
    "unit/feature-0041-external-ai-tool-surface/tests",
    "unit/feature-0043-external-llm-bridge/tests",
    "unit/feature-0008-windows-browser-testing/tests",
    "unit/feature-0006-lan-proxy-access/tests",
})


def _assert_existing_coverage(paths) -> None:
    missing = _EXISTING_SUITES - set(paths)
    assert not missing, f"Previously active regression suites omitted: {sorted(missing)}"


def _pytest_args(source: str, block_pattern: str) -> list[str]:
    block = re.search(block_pattern, source, re.M | re.S)
    assert block, "Could not find the test entrypoint"
    text = "\n".join(
        line for line in block.group(0).splitlines()
        if not line.lstrip().startswith("#")
    ).replace("\\\n", " ")
    commands = re.findall(
        r"(?:^|[;\n])[ \t]*(?:(?:python|python3)\s+-m\s+)?pytest\b([^\n;]*)", text, re.M
    )
    assert len(commands) == 1, "Expected one pytest invocation per entrypoint"
    return shlex.split(commands[0])


def _assert_unfiltered_collection(args: list[str]) -> None:
    assert set(args) <= {"-q", "--quiet"}, (
        f"Test entrypoint overrides pytest configuration: {args}. "
        "Maintain suite membership in pyproject.toml testpaths."
    )


@pytest.mark.parametrize(("relative", "pattern"), [
    ("Makefile", r"^test:.*?(?=^\w[\w-]*:|\Z)"),
    (".github/workflows/ci.yml", r"- name: Unit tests \(pytest\).*?(?=\n      - name: |\Z)"),
])
def test_entrypoints_use_configured_unfiltered_collection(relative, pattern):
    _assert_unfiltered_collection(
        _pytest_args((_REPO / relative).read_text(encoding="utf-8"), pattern)
    )


def test_configured_testpaths_exist_and_include_native_client(pytestconfig):
    paths = pytestconfig.getini("testpaths")
    assert paths and len(paths) == len(set(paths)), "Empty or duplicate testpaths"
    assert all((_REPO / path).is_dir() for path in paths), paths
    _assert_existing_coverage(paths)
    assert "unit/feature-0046-native-client/tests" in paths, (
        "Native-client regression suite was omitted by both former entrypoints"
    )
    assert str(Path(__file__).parent.relative_to(_REPO)) in paths


@pytest.mark.parametrize("omitted", sorted(_EXISTING_SUITES))
def test_removing_any_previously_active_suite_is_detected(omitted):
    with pytest.raises(AssertionError, match="Previously active regression suites omitted"):
        _assert_existing_coverage(_EXISTING_SUITES - {omitted})


@pytest.mark.parametrize("command", [
    "pytest -q unit/feature-0002-agent-core/tests",
    "pytest -q .",
    "pytest -q -k smoke",
    "pytest -q --ignore unit/feature-0046-native-client/tests",
    "pytest -q -c other.ini",
])
def test_explicit_path_or_filter_cannot_silently_reduce_the_shared_suite(command):
    source = f"test:\n\t{command}\nnext:\n"
    with pytest.raises(AssertionError, match="overrides pytest configuration"):
        _assert_unfiltered_collection(_pytest_args(source, r"^test:.*?(?=^next:)"))


def test_missing_pytest_invocation_does_not_vacuously_pass():
    with pytest.raises(AssertionError, match="Expected one pytest invocation"):
        _pytest_args("test:\n\techo pytest removed\nnext:\n", r"^test:.*?(?=^next:)")
