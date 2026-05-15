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
            self._row = None
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

    def test_auto_mode_uses_only_role_common_prompt(self):
        prompt = agent_core.compose_system_prompt(
            FakeConnection(),
            product_id=1,
            role_id=16,
            account_id=None,
            product_mode="auto",
        )

        self.assertIn("### 전 Product 공통\ncommon role guidance", prompt)
        self.assertNotIn("product-specific role guidance", prompt)


if __name__ == "__main__":
    unittest.main()
