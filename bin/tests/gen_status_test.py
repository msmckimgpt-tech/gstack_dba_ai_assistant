#!/usr/bin/env python3
"""Exercise the generated status index without touching the real checkout."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "gen-status.sh"


class StatusIndex(unittest.TestCase):
    def test_long_notes_preserve_sources_and_generate_bounded_idempotent_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "bin").mkdir()
            (root / "docs").mkdir()
            shutil.copyfile(SCRIPT, root / "bin/gen-status.sh")
            note = "**진행** [관련 문서](./FUNCTION.md) · 입력 | 결과 " + "상세 작업 기록 " * 2000
            task = root / "unit/feature-0001-current/docs/TASK.md"
            task.parent.mkdir(parents=True)
            original = (
                "---\nfeature_status: review\nfeature_status_date: 2026-09-08\n"
                f"feature_status_note: {note}\n---\n실제 작업 기록\n"
            )
            task.write_text(original)
            legacy = root / "unit/feature-0002-legacy/docs/TASK.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("기존 형식\n")
            short = root / "unit/feature-0003-short/docs/TASK.md"
            short.parent.mkdir(parents=True)
            short.write_text(
                "---\nfeature_status: review\nfeature_status_date: 2026-09-08\n"
                "feature_status_note: `MAX_RETRY_COUNT` 조건 `value < 10 && elapsed > 0` 유지\n---\n"
            )
            status = root / "docs/STATUS.md"
            status.write_text(
                "보존할 앞문단\n<!-- AI-EDITABLE:STATUS-TABLE:START -->\n"
                "| 기능 ID | 상태 | 최종 갱신 | 정본(상세) | 최근 작업 요지 |\n"
                "|---|---|---|---|---|\n"
                "| feature-0002-legacy | blocked | 2026-08-01 | [TASK](../unit/feature-0002-legacy/docs/TASK.md) | "
                + "예전 기록 | 다른 결과 " * 2000
                + " |\n<!-- AI-EDITABLE:STATUS-TABLE:END -->\n보존할 차단사항\n"
            )

            def run(*args):
                return subprocess.run(
                    ["bash", str(root / "bin/gen-status.sh"), *args],
                    capture_output=True, text=True, check=False,
                )

            self.assertEqual(1, run("--check").returncode)
            first = run()
            self.assertEqual(0, first.returncode, first.stderr)
            rendered = status.read_text()
            self.assertEqual(original, task.read_text())
            self.assertTrue(rendered.startswith("보존할 앞문단\n"))
            self.assertTrue(rendered.endswith("보존할 차단사항\n"))
            self.assertIn("| review | 2026-09-08 |", rendered)
            self.assertIn("| blocked | 2026-08-01 |", rendered)
            rows = [line for line in rendered.splitlines() if line.startswith("| feature-")]
            self.assertEqual(3, len(rows))
            self.assertIn("MAX_RETRY_COUNT 조건 value < 10 && elapsed > 0 유지", rendered)
            for row in rows:
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                self.assertEqual(5, len(cells), row)
                self.assertLessEqual(len(cells[4]), 180)
                if cells[0] != "feature-0003-short":
                    self.assertIn("상세는 TASK", cells[4])
                self.assertTrue((root / "docs" / cells[3].split("(", 1)[1][:-1]).is_file())
            self.assertEqual(0, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(rendered, status.read_text())


if __name__ == "__main__":
    unittest.main()
