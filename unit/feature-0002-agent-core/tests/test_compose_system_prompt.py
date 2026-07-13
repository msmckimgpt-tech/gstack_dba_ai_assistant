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

    def test_system_prompt_prefers_attachment_edit_on_update_request(self):
        # FR-attachment-update-pasted-not-versioned (A1): 코드 상수 SYSTEM_PROMPT 가 명시적
        # 갱신요청 시 attachment-edit 새 버전 전달을 지시하고, filename 은 생략(시스템 자동 버전명명)
        # 하도록 유도해야 한다 (라이브 global row 의 seed/fallback).
        prompt = agent_core.SYSTEM_PROMPT
        self.assertIn("attachment-edit", prompt)
        # "brand-new SQL" 예외가 편집을 삼키지 않음을 명시.
        self.assertRegex(prompt, r"(?i)EDIT of that file|never .*brand-new SQL")
        # filename 생략 유도 (수동 report_v2.csv 지정 유도 제거).
        self.assertRegex(prompt, r"(?i)do NOT set `?filename`?|OMIT")

    def test_attachment_delivery_directive_always_injected(self):
        # A2: compose 결과에 코드-권위 첨부 전달 지시가 항상 포함(global row 무관).
        prompt = agent_core.compose_system_prompt(
            FakeConnection(),
            product_id=1,
            role_id=16,
            account_id=7,
            product_mode="pinned",
        )
        self.assertIn("FILE UPDATE REQUESTS", prompt)
        self.assertIn("source_attachment_id", prompt)
        # injection guard 처럼 base 뒤 상위에 위치(제품/역할/계정 커스터마이즈보다 앞).
        self.assertLess(prompt.index("FILE UPDATE REQUESTS"), prompt.index("## PRODUCT CONTEXT"))

    def test_attachment_directive_survives_operator_global_override(self):
        # A2 drift 봉인 핵심: 운영자 WebSystemPrompts global row 가 코드 상수 base 를 통째
        # 대체해도(첨부 지침이 빠진 커스텀 프롬프트라도) 코드-권위 지시는 여전히 주입된다.
        class FakeCursorGlobalOverride(FakeCursor):
            def execute(self, sql, params=None):
                if "Scope='global'" in sql:
                    self._row = ("운영자 커스텀 BASE — 첨부 관련 지침 전혀 없음",)
                    return
                super().execute(sql, params)

        class FakeConnectionGlobalOverride:
            def cursor(self):
                return FakeCursorGlobalOverride()

        prompt = agent_core.compose_system_prompt(
            FakeConnectionGlobalOverride(),
            product_id=1,
            role_id=16,
            account_id=None,
            product_mode="pinned",
        )
        # global override 내용이 base 로 쓰였는지 확인.
        self.assertIn("운영자 커스텀 BASE", prompt)
        # 그럼에도 코드-권위 첨부 전달 지시는 존속(프로덕션 도달).
        self.assertIn("FILE UPDATE REQUESTS", prompt)
        self.assertIn("attachment-edit", prompt)


if __name__ == "__main__":
    unittest.main()
