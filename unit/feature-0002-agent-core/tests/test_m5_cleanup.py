"""M5 (TASK-0025) — cleanup script + deprecation note 단위 검증.

실 mysqldump / DROP 호출 없이 검증:
- bin/kb-cleanup-mysql.sh syntax + dry-run 출력
- _DualWriteMirror class 의 deprecation notice docstring
- ADR-0025 의 사전 조건 (M4 cutover gate PASS) 의 명시
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup script — dry-run 출력 + confirm string 검증
# ─────────────────────────────────────────────────────────────────────────────


def test_cleanup_script_exists_and_executable():
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    assert script.exists(), f"cleanup script 부재: {script}"
    assert script.stat().st_mode & 0o111, "executable bit 부재"


def test_cleanup_script_syntax_valid():
    """bash -n 으로 syntax 검증."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True,
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


def test_cleanup_script_dry_run_outputs_drop_sql():
    """dry-run mode 가 5 DROP SQL 출력 (VIEW + 4 base table)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--dry-run"], capture_output=True, text=True,
    )
    assert result.returncode == 0, f"dry-run 실패: {result.stderr}"
    out = result.stdout
    # 5 entries 모두 출력
    assert "DROP VIEW IF EXISTS" in out
    assert "AgentMemoryFacts" in out
    assert "AgentMemoryRagObjects" in out
    assert "AgentMemoryRagDocuments" in out
    assert "AgentMemoryFactEntries" in out
    assert "AgentMemoryTexts" in out
    # confirm string 가이드
    assert "I_UNDERSTAND_DATA_LOSS" in out


def test_cleanup_script_rejects_wrong_confirm_string():
    """--confirm 의 정확한 string 외 거부 — typo 방지."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--confirm", "yes"],
        capture_output=True, text=True,
    )
    # mode 진입 — confirm 검증 후 거부 (rc=2)
    assert result.returncode == 2, f"잘못된 confirm 인데 진행됨: rc={result.returncode}"
    assert "I_UNDERSTAND_DATA_LOSS" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# REV-20260522-0013 B5 흡수: mode 중복 / arg 누락 검증
# ─────────────────────────────────────────────────────────────────────────────


def test_dry_run_confirm_combination_rejected():
    """--dry-run + --confirm 혼합 거부 (B5 — silent promotion 차단)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--dry-run", "--confirm", "I_UNDERSTAND_DATA_LOSS"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"mode 중복 인데 진행됨: rc={result.returncode}"
    assert "mode 중복" in result.stderr or "중복" in result.stderr


def test_confirm_missing_arg_rejected():
    """--confirm 다음 string 누락 거부 (B5)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--confirm"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"--confirm arg 없는데 진행됨: rc={result.returncode}"


# ─────────────────────────────────────────────────────────────────────────────
# REV-20260522-0013 B3 + B4 흡수: dual-write sentinel + 14-day window
# ─────────────────────────────────────────────────────────────────────────────


def test_confirm_requires_dual_write_off(monkeypatch, tmp_path):
    """AGENT_KB_DUAL_WRITE=1 일 때 --confirm 거부 (B3)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    # 운영 환경 시뮬레이션 — AGENT_KB_READ_BACKEND=postgres + DUAL_WRITE=1
    env = {"AGENT_KB_READ_BACKEND": "postgres", "AGENT_KB_DUAL_WRITE": "1"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS",
         "--cutover-date", "2026-01-01"],
        capture_output=True, text=True, env={**env, "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "AGENT_KB_DUAL_WRITE" in result.stderr or "M5-implementation" in result.stderr


def test_confirm_requires_cutover_date(monkeypatch):
    """--cutover-date 누락 시 --confirm 거부 (B4)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    env = {"AGENT_KB_READ_BACKEND": "postgres", "AGENT_KB_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS"],
        capture_output=True, text=True, env={**env, "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "cutover-date" in result.stderr or "14-day" in result.stderr


def test_confirm_rejects_recent_cutover_date(monkeypatch):
    """14-day window 미달 시 --confirm 거부 (B4)."""
    script = REPO_ROOT / "bin" / "kb-cleanup-mysql.sh"
    import datetime
    recent = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    env = {"AGENT_KB_READ_BACKEND": "postgres", "AGENT_KB_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS",
         "--cutover-date", recent],
        capture_output=True, text=True, env={**env, "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "14-day" in result.stderr or "경과" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# _DualWriteMirror deprecation notice
# ─────────────────────────────────────────────────────────────────────────────


def test_dual_write_mirror_has_deprecation_notice():
    """M5 cleanup 후 module 제거 예정 명시."""
    sys.path.insert(0, str(REPO_ROOT / "unit/feature-0002-agent-core/src"))
    from modules import kb_backend  # type: ignore

    doc = kb_backend._DualWriteMirror.__doc__ or ""
    assert "DEPRECATION NOTICE" in doc, "_DualWriteMirror 의 DEPRECATION NOTICE 누락"
    assert "M5" in doc, "M5 cycle 언급 누락"
    assert "ADR-0025" in doc, "ADR-0025 참조 누락"


# ─────────────────────────────────────────────────────────────────────────────
# ADR-0025 정합 — 사전 조건 + 14-day window + 4 metric 명시
# ─────────────────────────────────────────────────────────────────────────────


def test_adr_0025_documented():
    adr_path = REPO_ROOT / "docs" / "DECISIONS.md"
    text = adr_path.read_text(encoding="utf-8")
    assert "## ADR-0025" in text, "ADR-0025 entry 부재"
    # 14-day monitoring window
    assert "14" in text
    # 4 metric 명시 (ask 5종 / p99 latency / error rate / KB write SLA)
    assert "ask 5종" in text or "S1~S5" in text
    assert "p99 latency" in text or "p99" in text.lower()
    # Stage A/B/C 정의
    assert "Stage A" in text and "Stage B" in text and "Stage C" in text
    # confirm string 정확 명시
    assert "I_UNDERSTAND_DATA_LOSS" in text
