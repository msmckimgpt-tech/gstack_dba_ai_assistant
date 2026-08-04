"""msg-speaker-attribution — 발화자 귀속의 **저장 시점 각인** 회귀 (agent-core 측).

배경(사용자 보고): 대화내역의 발화자(사용자 = 질문 발신자, assistant = 답한 제품)가 어디에도
각인되지 않아 FE 가 "대화의 현재 owner / 컴포저의 현재 제품 칩" 에서 파생했다. 그 결과
**제품을 바꾸거나 대화를 fork 하면 이미 지나간 대화의 발화자가 실시간으로 바뀌었다.**

여기서는 각인 생산자(agent_core)를 고정한다:
  A1  pinned 답변에 product_mode/product_id/product_key/product_name 이 각인된다.
  A2  auto 답변은 product_mode='auto' 만 각인 — 제품 id 를 발명하지 않는다("AI" 배지 확정).
  A3  제품 조회 실패는 fail-open — id/mode 는 남고 예외가 답변 저장을 막지 않는다.
  A4  1:1 사용자 메시지도 발신자를 각인한다(종전엔 그룹만) — 단 `group_chat` 마커는 붙지 않는다.
  A5  각인 부재(계정 미상)면 종전대로 meta 없이 저장 — 값 발명 금지.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_core  # noqa: E402


class _Cursor:
    """WebProducts / WebAccounts 단건 조회만 흉내내는 최소 커서."""

    def __init__(self, product_row=None, account_row=None, raise_on_execute=False):
        self._product_row = product_row
        self._account_row = account_row
        self._raise = raise_on_execute
        self._row = None

    def execute(self, sql, params=None):
        if self._raise:
            raise RuntimeError("db down")
        self._row = self._product_row if "WebProducts" in sql else self._account_row

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _Conn:
    def __init__(self, **kw):
        self._kw = kw

    def cursor(self):
        return _Cursor(**self._kw)


class AnswerProductAttributionTest(unittest.TestCase):
    def test_pinned_stamps_id_mode_key_and_name(self):
        """A1: pinned 답변은 제품 정체성 4키를 모두 각인한다."""
        attrib = agent_core._answer_product_attribution(
            _Conn(product_row=("KR_LIVE", "킹스레이드 라이브")), 7, "pinned"
        )
        self.assertEqual(attrib["product_mode"], "pinned")
        self.assertEqual(attrib["product_id"], 7)
        self.assertEqual(attrib["product_key"], "KR_LIVE")
        self.assertEqual(attrib["product_name"], "킹스레이드 라이브")

    def test_auto_stamps_mode_only(self):
        """A2: auto 는 제품이 없는 상태 그 자체가 사실 — product_id 를 만들어내지 않는다."""
        attrib = agent_core._answer_product_attribution(
            _Conn(product_row=("KR_LIVE", "킹스레이드")), 7, "auto"
        )
        self.assertEqual(attrib, {"product_mode": "auto"})
        self.assertNotIn("product_id", attrib)

    def test_no_product_id_stamps_mode_only(self):
        attrib = agent_core._answer_product_attribution(_Conn(), None, "pinned")
        self.assertEqual(attrib, {"product_mode": "pinned"})

    def test_lookup_failure_is_fail_open(self):
        """A3: 조회 실패해도 id/mode 는 남는다(FE 가 현재 제품 목록으로 라벨 해소 가능)."""
        attrib = agent_core._answer_product_attribution(
            _Conn(raise_on_execute=True), 7, "pinned"
        )
        self.assertEqual(attrib, {"product_mode": "pinned", "product_id": 7})

    def test_missing_product_row_keeps_id(self):
        attrib = agent_core._answer_product_attribution(_Conn(product_row=None), 7, "pinned")
        self.assertEqual(attrib, {"product_mode": "pinned", "product_id": 7})


class LookupAccountUsernameTest(unittest.TestCase):
    def test_resolves_username(self):
        self.assertEqual(
            agent_core._lookup_account_username(_Conn(account_row=("alice",)), 4), "alice"
        )

    def test_absent_or_failed_returns_none(self):
        """값 발명 금지 — 실패 시 None 이면 FE 가 종전 폴백으로 표시한다."""
        self.assertIsNone(agent_core._lookup_account_username(_Conn(account_row=None), 4))
        self.assertIsNone(agent_core._lookup_account_username(_Conn(raise_on_execute=True), 4))
        self.assertIsNone(agent_core._lookup_account_username(_Conn(), 0))
        self.assertIsNone(agent_core._lookup_account_username(_Conn(), None))


class UserMirrorMetaSourceContractTest(unittest.TestCase):
    """A4/A5 — 사용자 메시지 각인 계약을 소스 수준으로 고정.

    `_run_agent_core` 는 DB·LLM·컨텍스트 전반을 요구해 단위 호출이 불가하므로, 회귀가 실제로
    발생했던 **분기 구조**를 고정한다: (a) 1:1 도 sender 를 각인하고, (b) `group_chat` 마커는
    주입된 sender_username(그룹 게이트 proxy)에만 붙는다. 종전 구현은 두 가지를 하나의 조건에
    묶어 1:1 을 통째로 미각인으로 남겼다.
    """

    def _source(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "agent_core.py")
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_one_to_one_user_message_is_attributed(self):
        src = self._source()
        head = src.index("_user_mirror_meta: dict[str, Any] | None = None")
        block = src[head:head + 1200]
        # 각인은 account_id 만으로 성립한다(그룹 여부와 무관).
        self.assertIn('_user_mirror_meta = {"sender_account_id": int(account_id)}', block)
        # 1:1 은 username 을 조회해 채운다 — 없으면 FE 가 대화 owner 폴백으로 되돌아간다.
        self.assertIn("_lookup_account_username(mem_conn, account_id)", block)

    def test_group_chat_marker_still_gated_on_injected_sender_username(self):
        src = self._source()
        head = src.index("_user_mirror_meta: dict[str, Any] | None = None")
        block = src[head:head + 1200]
        marker = block.index('"group_chat"')
        gate = block.index("if sender_username:")
        # group_chat 마커는 주입된 sender_username 게이트 **안쪽**에만 존재해야 한다.
        self.assertLess(gate, marker)
        self.assertEqual(block.count('"group_chat"'), 1)


class AnswerPathsAttributionCoverageTest(unittest.TestCase):
    """§16.7 G2 — assistant 표시 메시지를 남기는 **모든** 경로가 각인된다.

    정상 답변만 각인하면 max_steps 초과·중단 보존·오류 말풍선이 미각인으로 남아 FE 폴백
    (대화 바인딩)으로 되돌아가고, 그 말풍선들만 제품 전환 때 다시 사후 변경된다.
    """

    # meta= 인자 표현식 — 다음 키워드 인자(recall_tag) 또는 호출 종료까지.
    _META_ARG = re.compile(r"meta=(.+?)(?:,\s*recall_tag=|\)\s*$)", re.S | re.M)

    def test_every_assistant_mirror_carries_product_meta(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "agent_core.py")
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        src = "".join(lines)
        calls = [
            i for i, ln in enumerate(lines)
            if "_mirror_message(" in ln and '"assistant"' in ln
        ]
        self.assertGreaterEqual(len(calls), 4, "assistant mirror 호출을 찾지 못함")
        for idx in calls:
            lineno = idx + 1
            window = "".join(lines[idx:idx + 3])   # 호출부는 최대 3줄로 래핑됨
            m = self._META_ARG.search(window)
            self.assertIsNotNone(
                m, f"agent_core.py:{lineno} assistant mirror 에 meta= 인자가 없다(각인 누락)",
            )
            arg = m.group(1).strip()
            if "_answer_product_meta" in arg:
                continue                      # 인라인으로 각인을 펼친 경우.
            # 변수 전달 — 그 변수가 이 run 의 각인으로 갱신돼야 한다.
            self.assertRegex(
                arg, r"^[A-Za-z_][A-Za-z0-9_]*$",
                f"agent_core.py:{lineno} meta 인자 `{arg}` 를 판독할 수 없다",
            )
            self.assertIn(
                f"{arg}.update(_answer_product_meta)", src,
                f"agent_core.py:{lineno} meta 변수 `{arg}` 가 제품 귀속으로 갱신되지 않는다",
            )


if __name__ == "__main__":
    unittest.main()
