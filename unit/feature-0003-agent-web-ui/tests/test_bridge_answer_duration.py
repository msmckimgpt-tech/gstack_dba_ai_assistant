"""브리지 답변에도 **총 수행시간이 각인된다** (사용자 제보 2026-09-02).

## 이 테스트가 잠그는 사고

답변 말풍선의 수행시간은 프런트가 `meta.duration_ms` 로만 그린다(`app.js` renderMessages —
`durationMs > 0` 게이트). 서버 LLM 경로는 답변마다 그 값을 굳혔지만(`agent_core` 의
`mirror_meta`), 브리지 경로(`_deliver_web_bridge_answer`)는 각인하지 않았다. feature-0043 이
브리지를 주 경로로 승격한 뒤 **표시가 통째로 사라졌다** — 라이브 실측:

    is_bridge | has_duration | count |   first    |    last
    ----------+--------------+-------+------------+------------
    f         | t            |   326 | 2026-07-24 | 2026-08-26
    t         | f            |   104 | 2026-08-27 | 2026-09-02   ← 전량 미각인

계산이 아니라 **연결**이 없어서 생긴 결함이다(이 feature 가 반복해서 겪은 형태). 그래서 헬퍼
단위 검사만 두지 않고, `_deliver_web_bridge_answer` 를 가짜 DB 로 **실제 구동**해 저장 경로에
넘어가는 meta 를 본다 — 각인 한 줄을 지우면 여기서 FAIL 한다.

## 지키는 두 설계 결정

**① 기준은 end-to-end 다.** `CreatedAt`(요청 적재) → `SubmittedAt`(답변 제출). 「러너가 실행한
시간」(`ClaimedAt` 기준)만 각인하면 대기 구간이 빠져, 대기 중 사용자가 보던 경과 타이머보다
**작은 숫자로 줄어든다**. 서버 LLM 경로가 TASK-0289 에서 같은 이유로 `run_start` 기준을 버렸다.

**② 각인 실패가 답변을 잃게 하지 않는다.** `ClaimedAt`/`SubmittedAt` 은 부트스트랩 ALTER 로
추가되는 컬럼이고 그 ALTER 가 실패한 환경이 실제로 상정돼 있다(`submit_answer` 의 503 분기).
수행시간은 관측이고 답변은 사용자 대면 산출물이다 — 관측을 못 얻는 대가로 답변을 잃지 않는다.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import types

import pytest

import routers.ai_tools as ai_tools


AI_TOOLS_PY = pathlib.Path(ai_tools.__file__)


# ── 헬퍼 값 계약 ─────────────────────────────────────────────────────────────

def test_duration_meta_splits_wait_and_run():
    """정상 경로 — 총량 + 두 구간. 키 이름은 서버 LLM 경로와 **같아야** 한다."""
    got = ai_tools._bridge_answer_duration_meta(192_000.0, 8_200.0)
    assert got["duration_ms"] == 192_000.0
    assert got["duration_breakdown"] == {
        "total_ms": 192_000.0, "queued_ms": 8_200.0, "inference_ms": 183_800.0}


def test_breakdown_keys_match_frontend_reader():
    """프런트 `formatDurationBreakdown` 이 읽는 키만 쓴다.

    그 함수는 `queued_ms`·`init_ms`·`inference_ms` 세 축만 본다. 새 라벨(예: `runner_ms`)을
    만들면 값은 저장되는데 **툴팁·보조문에는 아무것도 안 나온다** — 각인했다고 믿는 상태로
    표시가 비는 형태다.
    """
    bd = ai_tools._bridge_answer_duration_meta(5_000.0, 1_000.0)["duration_breakdown"]
    assert set(bd) <= {"total_ms", "queued_ms", "init_ms", "inference_ms"}, (
        f"프런트가 읽지 않는 키가 있다: {sorted(set(bd) - {'total_ms', 'queued_ms', 'init_ms', 'inference_ms'})}")
    # 브리지에는 서버측 준비 구간이 없다 — 재지 않은 계측을 0 으로 실어 있다고 말하지 않는다.
    assert "init_ms" not in bd


def test_unclaimed_task_reports_total_without_a_fake_split():
    """점유 시각이 없으면(구 task·외부 origin) 분해를 **아예 싣지 않는다**.

    총량 하나만 남는다. 「실행 = 총량」 분해를 실으면 화면에 같은 숫자가 괄호로 한 번 더
    나올 뿐이다(라이브 관측 2026-09-02 — 대기 0 인 답변이 `36초 (추론 36초)` 로 보였다).
    """
    got = ai_tools._bridge_answer_duration_meta(4_500.0, None)
    assert got == {"duration_ms": 4_500.0}


@pytest.mark.parametrize("queued", [
    -1.0,        # ClaimedAt < CreatedAt (시계 역행)
    9_999.0,     # ClaimedAt > SubmittedAt (총량과 모순)
    "abc",       # 드라이버가 준 비수치
    0.0,         # 즉시 점유 — 가를 것이 없다 (라이브 실측: 초 해상도라 흔하다)
    100.0,       # 프런트 표시 임계(250ms) 미만 — 그려지지 않을 분해는 각인하지 않는다
])
def test_wait_that_cannot_be_shown_yields_total_only(queued):
    """대기 축을 못 쓰거나 보여줄 수 없으면 **총량만** 남긴다 — 표시가 사라지면 안 된다."""
    got = ai_tools._bridge_answer_duration_meta(5_000.0, queued)
    assert got == {"duration_ms": 5_000.0}


def test_segment_threshold_matches_the_frontend():
    """서버의 구간 임계가 프런트 표시 임계와 **같은 숫자**여야 한다.

    갈리면 두 방향으로 조용히 틀린다 — 서버가 더 관대하면 화면에 아무것도 못 그리는 분해를
    각인하고(툴팁이 비어 보인다), 서버가 더 엄하면 프런트가 그릴 수 있는 구간을 미리 버린다.
    """
    js = (pathlib.Path(ai_tools.__file__).resolve().parents[1]
          / "static" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"if \(Number\(ms \|\| 0\) >= (\d+)\) parts\.push", js)
    assert m, "프런트 formatDurationBreakdown 의 표시 임계를 찾지 못했다(구현이 바뀌었나?)"
    assert float(m.group(1)) == ai_tools._BRIDGE_SEGMENT_MIN_MS, (
        f"프런트 임계 {m.group(1)}ms ≠ 서버 임계 {ai_tools._BRIDGE_SEGMENT_MIN_MS}ms")


def test_showable_wait_still_produces_a_breakdown():
    """보여줄 수 있는 대기(임계 이상)는 그대로 분해된다 — 위 게이트가 과잉이 아님을 잠근다."""
    got = ai_tools._bridge_answer_duration_meta(5_000.0, 250.0)
    assert got["duration_breakdown"] == {
        "total_ms": 5_000.0, "queued_ms": 250.0, "inference_ms": 4_750.0}


@pytest.mark.parametrize("total", [None, 0, 0.0, -12.0, "", "nan-ish"])
def test_unusable_total_emits_nothing(total):
    """총량을 못 구하면 **아무것도 각인하지 않는다**.

    거짓 `0초` 를 그리는 것보다 안 그리는 쪽이 정직하고, 종전(미각인) 동작과 같아 회귀가 없다.
    프런트 게이트가 `duration_ms > 0` 이라 0 을 실어도 그려지지 않고 원장만 오염된다.
    """
    assert ai_tools._bridge_answer_duration_meta(total, 100.0) == {}


def test_numeric_strings_from_the_driver_are_accepted():
    """`TIMESTAMPDIFF(...)/1000.0` 는 드라이버에 따라 Decimal·문자열로 온다 — 값이 죽지 않는다."""
    got = ai_tools._bridge_answer_duration_meta("3000.5", "500.25")
    assert got["duration_ms"] == 3000.5
    assert got["duration_breakdown"]["queued_ms"] == 500.25


# ── 측정 기준 (SQL) ──────────────────────────────────────────────────────────

def _func_source(name: str) -> str:
    text = AI_TOOLS_PY.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(text, node) or ""
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                lo = body[0].lineno - node.lineno
                hi = (body[0].end_lineno or body[0].lineno) - node.lineno
                lines = seg.splitlines()
                seg = "\n".join(lines[:lo] + lines[hi + 1:])
            return seg
    raise AssertionError(f"ai_tools.py: 함수 {name} 를 찾지 못했다(이름이 바뀌었나?)")


def test_total_is_measured_from_task_creation():
    """총량의 시작점은 `CreatedAt` 이다 — 이 기준이 바뀌면 표시 숫자가 조용히 줄어든다.

    `ClaimedAt → SubmittedAt` 으로 재면 대기 구간이 총량에서 빠진다. 그 값은 사용자가 대기
    중 보던 경과 타이머보다 **작아서**, 답변이 도착하는 순간 숫자가 거꾸로 가는 것처럼 보인다.
    """
    body = _func_source("_bridge_task_duration_meta")
    assert "TIMESTAMPDIFF(MICROSECOND, CreatedAt, COALESCE(SubmittedAt, NOW()))" in body, (
        "총 수행시간 기준(CreatedAt → SubmittedAt)이 바뀌었다")
    assert "TIMESTAMPDIFF(MICROSECOND, CreatedAt, ClaimedAt)" in body, (
        "대기 구간 기준(CreatedAt → ClaimedAt)이 바뀌었다")


def test_duration_lookup_is_a_separate_query():
    """소요 조회를 **답변 전달의 주 SELECT 에 얹지 않는다**.

    한 쿼리로 묶으면 `ClaimedAt`/`SubmittedAt` 컬럼 부재(부트스트랩 ALTER 실패)가 답변 전달
    자체를 실패시킨다 — 관측 때문에 사용자 대면 산출물을 잃는 형태다.
    """
    deliver = _func_source("_deliver_web_bridge_answer")
    assert "TIMESTAMPDIFF" not in deliver, "소요 계산이 전달 경로의 주 SELECT 로 합쳐졌다"
    assert "_bridge_task_duration_meta(conn, task_id)" in deliver


# ── 진입점 배선 (_deliver_web_bridge_answer 실제 구동) ───────────────────────

_CONV_ID = 7
_TASK_ID = "t_dur"


class _FakeCursor:
    def __init__(self, owner):
        self._owner = owner
        self._row = None
        self.rowcount = 1

    def execute(self, sql, params=None):
        self._owner.sql.append(sql)
        if "TIMESTAMPDIFF" in sql:
            if self._owner.duration_raises:
                # 컬럼 부재(부트스트랩 ALTER 실패) 환경의 재현.
                raise RuntimeError("Unknown column 'ClaimedAt' in 'field list'")
            self._row = self._owner.duration_row
        elif "SELECT ConversationId" in sql:
            self._row = (_CONV_ID, "web", None, "pinned", "어제 신규 가입자?")
        else:
            self._row = None

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _FakeConn:
    def __init__(self, duration_row=(192_000.0, 8_200.0), duration_raises=False):
        self.sql: list[str] = []
        self.duration_row = duration_row
        self.duration_raises = duration_raises

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass


def _run_deliver(monkeypatch, conn) -> dict:
    """`_deliver_web_bridge_answer` 를 구동하고 저장 경로에 넘어간 meta 를 돌려준다."""
    seen: dict = {}

    # 배포본 path 에만 있는 모듈들(feature-0002) — 테스트 환경에서는 스텁.
    mem = types.ModuleType("modules.memory")
    mem.save_memory_message = lambda *a, **k: 0  # placeholder 경로가 잡으므로 미사용
    monkeypatch.setitem(sys.modules, "modules.memory", mem)
    core = types.ModuleType("agent_core")
    core._answer_product_attribution = lambda *a, **k: {"product_key": "WEB_QA"}
    core._save_message = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "agent_core", core)

    def _replace(conn_, conversation_id, task_id, answer, meta):
        seen["meta"] = meta
        seen["answer"] = answer
        return 4242

    monkeypatch.setattr(ai_tools, "_replace_bridge_placeholder", _replace)
    monkeypatch.setattr(ai_tools, "_materialize_bridge_attachments",
                        lambda *a, **k: ("", [], []))
    monkeypatch.setattr(ai_tools, "_materialize_bridge_steps", lambda *a, **k: 0)

    seen["delivered"] = ai_tools._deliver_web_bridge_answer(
        conn, _TASK_ID, {"id": 1, "username": "admin"}, "인덱스가 없습니다.")
    return seen


def test_delivered_answer_carries_the_duration(monkeypatch):
    """저장되는 meta 에 수행시간이 실린다 — **이 각인이 없으면 화면에서 숫자가 사라진다**."""
    seen = _run_deliver(monkeypatch, _FakeConn())
    assert seen["delivered"] is True
    meta = seen["meta"]
    assert meta["duration_ms"] == 192_000.0, "총 수행시간 각인이 없다"
    assert meta["duration_breakdown"]["queued_ms"] == 8_200.0
    assert meta["duration_breakdown"]["inference_ms"] == 183_800.0
    # 기존 각인(제품 귀속·run_id·placeholder 해제)을 덮지 않는다.
    assert meta["run_id"] == _TASK_ID
    assert meta["product_key"] == "WEB_QA"
    assert meta["bridge"]["placeholder"] is False


def test_unclaimed_delivery_still_carries_a_total(monkeypatch):
    """점유 시각이 없는 task 도 총량은 각인된다(구 task 도 수행시간을 본다) — 분해는 없다."""
    seen = _run_deliver(monkeypatch, _FakeConn(duration_row=(4_500.0, None)))
    assert seen["meta"]["duration_ms"] == 4_500.0
    assert "duration_breakdown" not in seen["meta"]


def test_duration_failure_does_not_cost_the_answer(monkeypatch):
    """소요 조회가 깨져도 **답변은 그대로 전달된다** (fail-open).

    컬럼 부재 환경에서 각인 때문에 답변 전달이 실패하면, 사용자는 수행시간이 아니라 **답변
    자체**를 잃는다 — 관측을 위해 산출물을 버리는 교환은 하지 않는다.
    """
    seen = _run_deliver(monkeypatch, _FakeConn(duration_raises=True))
    assert seen["delivered"] is True, "각인 실패가 답변 전달을 막았다"
    assert "duration_ms" not in seen["meta"]
    assert seen["meta"]["run_id"] == _TASK_ID, "다른 각인까지 잃었다"
