import pathlib
import sys
import unittest


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402


class FakeCursor:
    def __init__(self):
        self._row = None

    def execute(self, sql, params=None):
        params = params or ()
        if "FROM WebProducts" in sql:
            self._row = ("KR",)
            return
        if "FROM WebRoles" in sql:
            self._row = ("sales",)
            return
        if "Scope='product'" in sql:
            self._row = ("product guidance",)
            return
        if "FROM WebSystemPrompts" in sql and "RoleId=%s" in sql:
            product_param = params[-1] if params else None
            if "ProductId=%s" in sql and product_param == 1:
                self._row = ("product-specific role guidance",)
                return
            if "ProductId IS NULL" in sql:
                self._row = ("common role guidance",)
                return
        if "FROM WebSystemPrompts" in sql and "AccountId=%s" in sql:
            product_param = params[-1] if params else None
            if "ProductId=%s" in sql and product_param == 1:
                self._row = ("product-specific account preference",)
                return
            if "ProductId IS NULL" in sql:
                self._row = ("common account preference",)
                return
            self._row = None
            return
        self._row = None

    def fetchone(self):
        return self._row

    def close(self):
        pass


class FakeConnection:
    def cursor(self):
        return FakeCursor()


class ComposeSystemPromptTest(unittest.TestCase):
    def test_role_common_prompt_accumulates_with_product_specific_prompt(self):
        prompt = agent_core.compose_system_prompt(
            FakeConnection(),
            product_id=1,
            role_id=16,
            account_id=None,
            product_mode="pinned",
        )

        self.assertIn("### 전 Product 공통\ncommon role guidance", prompt)
        self.assertIn("### ProductId=1\nproduct-specific role guidance", prompt)
        self.assertLess(prompt.index("common role guidance"), prompt.index("product-specific role guidance"))

    def test_product_role_account_order_accumulates_before_user_request(self):
        system_prompt = agent_core.compose_system_prompt(
            FakeConnection(),
            product_id=1,
            role_id=16,
            account_id=7,
            product_mode="pinned",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "current user request"},
        ]

        self.assertLess(system_prompt.index("## PRODUCT CONTEXT"), system_prompt.index("## ROLE GUIDANCE"))
        self.assertLess(system_prompt.index("## ROLE GUIDANCE"), system_prompt.index("## ACCOUNT PREFERENCES"))
        self.assertIn("### 전 Product 공통\ncommon account preference", system_prompt)
        self.assertIn("### ProductId=1\nproduct-specific account preference", system_prompt)
        self.assertEqual(messages[-1], {"role": "user", "content": "current user request"})

    def test_auto_mode_uses_only_role_common_prompt(self):
        prompt = agent_core.compose_system_prompt(
            FakeConnection(),
            product_id=1,
            role_id=16,
            account_id=7,
            product_mode="auto",
        )

        self.assertIn("### 전 Product 공통\ncommon role guidance", prompt)
        self.assertNotIn("product-specific role guidance", prompt)
        self.assertIn("### 전 Product 공통\ncommon account preference", prompt)
        self.assertNotIn("product-specific account preference", prompt)

    def test_system_prompt_instructs_diff_block_for_reviews(self):
        # TASK-0256: 첨부파일/쿼리 리뷰 시 변경 제안을 markdown diff 블록으로 제시하도록
        # base SYSTEM_PROMPT 가 지시해야 한다 (라이브 global row 의 seed/fallback).
        prompt = agent_core.SYSTEM_PROMPT
        self.assertIn("```diff", prompt)
        self.assertIn("DIFF BLOCK", prompt.upper())
        # 리뷰/편집 맥락에서의 지시임이 드러나야 한다 (신규 SQL 작성과 구분).
        self.assertRegex(prompt, r"(?i)review|edit")
        # diff 가이드는 OUTPUT 섹션 이후에 위치 (최종 답변 포맷 지침의 일부).
        self.assertIn("## OUTPUT", prompt)
        self.assertLess(prompt.index("## OUTPUT"), prompt.index("```diff"))


if __name__ == "__main__":
    unittest.main()
