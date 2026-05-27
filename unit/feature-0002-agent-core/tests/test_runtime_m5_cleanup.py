"""AR-M5 (TASK-0119) — runtime cleanup script 단위 검증.

실 mysqldump / DROP 호출 없이 검증:
- bin/runtime-cleanup-mysql.sh syntax + dry-run 출력
- 사전 조건 gate (read_backend / dual-write / 14-day window)
- mode 중복 / arg 누락 거부
- ADR-0028 문서화 확인
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Script 기본 검증
# ─────────────────────────────────────────────────────────────────────────────


def test_cleanup_script_exists_and_executable():
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    assert script.exists(), f"cleanup script 부재: {script}"
    assert script.stat().st_mode & 0o111, "executable bit 부재"


def test_cleanup_script_syntax_valid():
    """bash -n 으로 syntax 검증."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True,
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


def test_cleanup_script_dry_run_outputs_drop_sql():
    """dry-run mode 가 6 테이블 DROP TABLE SQL 출력."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--dry-run"], capture_output=True, text=True,
    )
    assert result.returncode == 0, f"dry-run 실패: {result.stderr}"
    out = result.stdout
    assert "DROP TABLE IF EXISTS" in out
    assert "AgentCoreMessages" in out
    assert "AgentMemoryMessages" in out
    assert "AgentMemorySteps" in out
    assert "AgentMemorySummary" in out
    assert "AgentMemoryKv" in out
    assert "AgentCoreConversations" in out
    # confirm string 가이드 포함 확인
    assert "I_UNDERSTAND_DATA_LOSS" in out


def test_cleanup_script_drop_order():
    """AgentCoreMessages 가 AgentCoreConversations 보다 먼저 DROP (parent 마지막 convention)."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--dry-run"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    # DROP TABLE 라인만 순서 추출 (헤더/주석 제외).
    drop_lines = [l for l in result.stdout.splitlines() if "DROP TABLE IF EXISTS" in l]
    names = [l.split(".")[-1].rstrip(";").strip() for l in drop_lines]
    assert "AgentCoreMessages" in names and "AgentCoreConversations" in names
    pos_child = names.index("AgentCoreMessages")
    pos_parent = names.index("AgentCoreConversations")
    assert pos_child < pos_parent, (
        f"AgentCoreMessages ({pos_child}) 가 AgentCoreConversations ({pos_parent}) 보다 먼저 DROP 돼야 함"
    )


# ─────────────────────────────────────────────────────────────────────────────
# confirm string 검증
# ─────────────────────────────────────────────────────────────────────────────


def test_cleanup_script_rejects_wrong_confirm_string():
    """--confirm 의 정확한 string 외 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--confirm", "yes"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"잘못된 confirm 인데 진행됨: rc={result.returncode}"
    assert "I_UNDERSTAND_DATA_LOSS" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# mode 중복 / arg 누락 거부
# ─────────────────────────────────────────────────────────────────────────────


def test_dry_run_confirm_combination_rejected():
    """--dry-run + --confirm 혼합 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--dry-run", "--confirm", "I_UNDERSTAND_DATA_LOSS"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "mode 중복" in result.stderr or "중복" in result.stderr


def test_backup_only_confirm_combination_rejected():
    """--backup-only + --confirm 혼합 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--backup-only", "--confirm", "I_UNDERSTAND_DATA_LOSS"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_confirm_missing_arg_rejected():
    """--confirm 다음 string 누락 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--confirm"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_cutover_date_missing_arg_rejected():
    """--cutover-date 다음 string 누락 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    result = subprocess.run(
        ["bash", str(script), "--cutover-date"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


# ─────────────────────────────────────────────────────────────────────────────
# 사전 조건 gate — read_backend / dual-write / 14-day window
# ─────────────────────────────────────────────────────────────────────────────

_BASE_ENV = {"PATH": "/usr/bin:/bin"}


def test_confirm_requires_postgres_read_backend():
    """AGENT_RUNTIME_READ_BACKEND!=postgres 일 때 --confirm 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    env = {**_BASE_ENV, "AGENT_RUNTIME_READ_BACKEND": "mysql", "AGENT_RUNTIME_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS", "--cutover-date", "2026-01-01"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "AGENT_RUNTIME_READ_BACKEND" in result.stderr or "postgres" in result.stderr


def test_confirm_requires_dual_write_off():
    """AGENT_RUNTIME_DUAL_WRITE=1 일 때 --confirm 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    env = {**_BASE_ENV, "AGENT_RUNTIME_READ_BACKEND": "postgres", "AGENT_RUNTIME_DUAL_WRITE": "1"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS", "--cutover-date", "2026-01-01"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "AGENT_RUNTIME_DUAL_WRITE" in result.stderr or "dual-write" in result.stderr.lower() or "M5-impl" in result.stderr


def test_confirm_requires_cutover_date():
    """--cutover-date 누락 시 --confirm 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    env = {**_BASE_ENV, "AGENT_RUNTIME_READ_BACKEND": "postgres", "AGENT_RUNTIME_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "cutover-date" in result.stderr or "14-day" in result.stderr


def test_confirm_rejects_recent_cutover_date():
    """14-day window 미달 시 --confirm 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    recent = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    env = {**_BASE_ENV, "AGENT_RUNTIME_READ_BACKEND": "postgres", "AGENT_RUNTIME_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS", "--cutover-date", recent],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "14-day" in result.stderr or "경과" in result.stderr


def test_confirm_rejects_invalid_cutover_date_format():
    """잘못된 날짜 형식 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    env = {**_BASE_ENV, "AGENT_RUNTIME_READ_BACKEND": "postgres", "AGENT_RUNTIME_DUAL_WRITE": "0"}
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS", "--cutover-date", "20260101"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert "형식" in result.stderr or "YYYY-MM-DD" in result.stderr


def test_confirm_non_tty_requires_env_var():
    """non-TTY 환경에서 RUNTIME_M5_RUN_FROM_HUMAN_SHELL 없으면 거부."""
    script = REPO_ROOT / "bin" / "runtime-cleanup-mysql.sh"
    # 14일 이전 날짜 (충분히 오래됨)
    old_date = "2026-01-01"
    env = {
        **_BASE_ENV,
        "AGENT_RUNTIME_READ_BACKEND": "postgres",
        "AGENT_RUNTIME_DUAL_WRITE": "0",
        # RUNTIME_M5_RUN_FROM_HUMAN_SHELL 미설정
    }
    result = subprocess.run(
        ["bash", str(script), "--confirm", "I_UNDERSTAND_DATA_LOSS", "--cutover-date", old_date],
        capture_output=True, text=True, env=env,
        stdin=subprocess.DEVNULL,  # non-TTY
    )
    assert result.returncode == 2
    assert "non-TTY" in result.stderr or "RUNTIME_M5_RUN_FROM_HUMAN_SHELL" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# ADR-0028 문서화 확인
# ─────────────────────────────────────────────────────────────────────────────


def test_adr_0028_documented():
    adr_path = REPO_ROOT / "docs" / "DECISIONS.md"
    text = adr_path.read_text(encoding="utf-8")
    assert "## ADR-0028" in text, "ADR-0028 entry 부재"
    # Stage A/B/C 정의
    assert "Stage A" in text and "Stage B" in text and "Stage C" in text
    # 14-day window
    assert "14" in text
    # confirm string
    assert "I_UNDERSTAND_DATA_LOSS" in text
    # 6 테이블 목록
    assert "AgentCoreConversations" in text
    assert "AgentCoreMessages" in text
