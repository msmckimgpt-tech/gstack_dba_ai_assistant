"""TASK-0256e: 첨부 텍스트 본문 줄번호 prefix(`<N>→`) 검증.

모델이 첨부 파일의 실제 줄을 인용/diff 헌크 헤더에 쓸 수 있도록 `_build_attachment_context_section`
이 본문을 줄번호와 함께 주입한다. 본 테스트는 줄번호 부여 헬퍼(`_number_file_lines`)의 포맷·정렬·
본문 보존을 검증한다. `make test`(agent 이미지) 에서 DB 없이 실행.
"""
import pathlib
import sys
import unittest


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402


class NumberFileLinesTest(unittest.TestCase):
    def test_basic_numbering(self):
        out = agent_core._number_file_lines("SELECT\n  AID\n  , UserID")
        self.assertEqual(out, "1→SELECT\n2→  AID\n3→  , UserID")

    def test_right_aligned_width(self):
        content = "\n".join(f"line{i}" for i in range(1, 13))  # 12줄 → 폭 2
        rows = agent_core._number_file_lines(content).split("\n")
        self.assertEqual(rows[0], " 1→line1")   # 우측 정렬(폭 2)
        self.assertEqual(rows[9], "10→line10")
        self.assertEqual(rows[11], "12→line12")

    def test_empty_content(self):
        self.assertEqual(agent_core._number_file_lines(""), "")

    def test_preserves_code_after_prefix(self):
        # prefix 뒤 본문은 원본 그대로(들여쓰기 포함) — 모델이 순수 코드를 복원 가능.
        content = "  , YEAR( EndHackingBlockTime) AS HackBlockYear"
        out = agent_core._number_file_lines(content)
        self.assertEqual(out, "1→" + content)
        self.assertEqual(out.split("→", 1)[1], content)

    def test_instruction_mentions_hunk_header(self):
        # 줄번호 안내 + 실제 줄번호 기반 diff 헌크 헤더 지시가 코드에 존재해야 한다.
        src = (SRC_ROOT / "agent_core.py").read_text(encoding="utf-8")
        self.assertIn("LINE NUMBERS & DIFFS", src)
        self.assertIn("@@ -<oldStart>,<oldCount> +<newStart>,<newCount> @@", src)
        self.assertIn("_number_file_lines(content)", src)


if __name__ == "__main__":
    unittest.main()
