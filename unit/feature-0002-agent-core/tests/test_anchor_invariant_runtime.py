"""ANCHOR §3 invariant 시나리오 카탈로그 — agent_runtime dual-write 정합 검증.

TASK-0113 AR-M2-a: RuntimeBackend ABC + skeleton. 본 파일은 M2-b/M2-c 구현 완료
후 실제 assertion 을 채우기 위한 **시나리오 카탈로그** 선행 등록.

KB 패턴 답습 (test_anchor_invariant_postgres.py, TASK-0019 M2-a).

시나리오 카탈로그 (6종):
  RT-S1: save_conversation — upsert idempotency (중복 호출 시 1 row 보장)
  RT-S2: save_core_message — append-only (동일 conv 에 N 번 호출 → N row)
  RT-S3: save_kv — __global__ sentinel upsert (FK 없음, ADR-0027)
  RT-S4: save_memory_step — step_index 순서 보존
  RT-S5: save_memory_summary — one-row-per-conversation UPSERT
  RT-S6: dual-write mirror partial failure — PG 실패 시 MySQL caller 무영향
         (AGENT_RUNTIME_PG_REQUIRED=0)

M2-b 구현 시 각 시나리오의 실제 assertion 채움.
M2-c 구현 시 cross-DB audit SLA 시나리오 추가.
"""

from __future__ import annotations

import os
import sys

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# 시나리오 카탈로그 (M2-b/M2-c 구현 완료 후 assertion 채움)
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_CATALOG = [
    {
        "id": "RT-S1_save_conversation_upsert_idempotency",
        "name": "save_conversation — upsert 멱등성 (중복 conversation_id 호출)",
        "setup": "PgRuntimeBackend.save_conversation() 을 같은 conversation_id 로 2회 호출",
        "expected": "agent_runtime.core_conversations 에 row 1개만 존재 (ON CONFLICT DO UPDATE). "
                    "topic / owner_account_id 등 컬럼이 2차 호출 값으로 갱신.",
        "ddl_table_focus": ["core_conversations"],
    },
    {
        "id": "RT-S2_save_core_message_append_only",
        "name": "save_core_message — append-only (동일 conv N 번 호출 → N row)",
        "setup": "PgRuntimeBackend.save_core_message() 를 같은 conversation_id 로 3회 호출",
        "expected": "agent_runtime.core_messages 에 3 row. "
                    "id GENERATED ALWAYS AS IDENTITY 로 단조 증가. "
                    "role / content 각각 보존.",
        "ddl_table_focus": ["core_messages"],
    },
    {
        "id": "RT-S3_save_kv_global_sentinel",
        "name": "save_kv — __global__ sentinel (FK 없음, ADR-0027 의도적 생략)",
        "setup": "PgRuntimeBackend.save_kv() 에 conversation_id='__global__' 로 호출. "
                 "core_conversations 에 '__global__' row 없음.",
        "expected": "INSERT 성공 (FK constraint 없음). "
                    "동일 key 2차 호출 시 value UPDATE (ON CONFLICT DO UPDATE). "
                    "core_conversations 무변경.",
        "ddl_table_focus": ["kv"],
    },
    {
        "id": "RT-S4_save_memory_step_step_index_order",
        "name": "save_memory_step — step_index 순서 보존",
        "setup": "같은 (conversation_id, run_id) 로 step_index 0, 1, 2 순으로 3회 호출",
        "expected": "agent_runtime.steps 에 3 row. "
                    "ORDER BY step_index 조회 시 0→1→2 순. "
                    "ix_steps_conv_run 인덱스로 conversation_id+run_id 조회 가능.",
        "ddl_table_focus": ["steps"],
    },
    {
        "id": "RT-S5_save_memory_summary_one_row",
        "name": "save_memory_summary — one-row-per-conversation UPSERT",
        "setup": "PgRuntimeBackend.save_memory_summary() 를 같은 conversation_id 로 2회 호출 (summary 내용 다름)",
        "expected": "agent_runtime.summary 에 row 1개만 존재. "
                    "2차 호출 summary 값으로 갱신 (ON CONFLICT DO UPDATE). "
                    "updated_at 자동 갱신 (trg_summary_updated_at trigger).",
        "ddl_table_focus": ["summary"],
    },
    {
        "id": "RT-S6_dual_write_mirror_partial_failure_isolation",
        "name": "dual-write mirror 부분 실패 시 MySQL caller 무영향",
        "setup": "AGENT_RUNTIME_PG_REQUIRED=0 환경. "
                 "_dual_write_runtime_mirror('save_kv', ...) 의 PG conn_factory 가 예외 발생.",
        "expected": "예외 전파 없음 (caller 의 MySQL write 정상 완료). "
                    "logger.warning 1회 발행. "
                    "AGENT_RUNTIME_PG_REQUIRED=1 이면 예외 전파됨.",
        "ddl_table_focus": [],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 시나리오 카탈로그 등록 assertion (M2-a skeleton — 6종 존재 보장)
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_catalog_complete():
    """6 시나리오가 모두 카탈로그에 등록되어 있는지 확인."""
    ids = {s["id"] for s in SCENARIO_CATALOG}
    expected_prefixes = ["RT-S1", "RT-S2", "RT-S3", "RT-S4", "RT-S5", "RT-S6"]
    for prefix in expected_prefixes:
        matched = [i for i in ids if i.startswith(prefix)]
        assert matched, f"시나리오 {prefix} 가 카탈로그에 없음"
    assert len(SCENARIO_CATALOG) >= 6


# ─────────────────────────────────────────────────────────────────────────────
# RuntimeBackend ABC import 및 class 존재 확인 (M2-a skeleton 검증)
# ─────────────────────────────────────────────────────────────────────────────

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def test_runtime_backend_abc_importable():
    from modules.runtime_backend import RuntimeBackend
    assert RuntimeBackend is not None
    assert RuntimeBackend.backend_name == "abstract"


def test_mysql_runtime_backend_importable():
    from modules.runtime_backend import MysqlRuntimeBackend
    backend = MysqlRuntimeBackend()
    assert backend.backend_name == "mysql"


def test_pg_runtime_backend_importable():
    from modules.runtime_backend import PgRuntimeBackend
    backend = PgRuntimeBackend()
    assert backend.backend_name == "postgres"


def test_runtime_backend_has_all_6_abstract_methods():
    """ABC 가 6 method 를 모두 선언하는지 확인."""
    from modules.runtime_backend import RuntimeBackend
    import inspect
    abstract_methods = {
        name for name, _ in inspect.getmembers(RuntimeBackend, predicate=inspect.isfunction)
        if getattr(getattr(RuntimeBackend, name), "__isabstractmethod__", False)
    }
    required = {
        "save_conversation",
        "save_core_message",
        "save_kv",
        "save_memory_message",
        "save_memory_step",
        "save_memory_summary",
    }
    missing = required - abstract_methods
    assert not missing, f"ABC 에서 누락된 abstract method: {missing}"


def test_mysql_backend_all_methods_raise_not_implemented():
    from modules.runtime_backend import MysqlRuntimeBackend
    import pytest
    backend = MysqlRuntimeBackend()
    with pytest.raises(NotImplementedError):
        backend.save_conversation(None, conversation_id="test")
    with pytest.raises(NotImplementedError):
        backend.save_kv(None, conversation_id="__global__", key="k", value="v")
    with pytest.raises(NotImplementedError):
        backend.save_memory_summary(None, conversation_id="test", summary="s")


def test_pg_backend_all_methods_implemented():
    """M2-b: PgRuntimeBackend 가 6 method 를 모두 구현함 (더 이상 NotImplementedError 아님)."""
    from modules.runtime_backend import PgRuntimeBackend
    import inspect
    backend = PgRuntimeBackend()
    required = [
        "save_conversation", "save_core_message", "save_kv",
        "save_memory_message", "save_memory_step", "save_memory_summary",
    ]
    for name in required:
        method = getattr(backend, name, None)
        assert method is not None, f"PgRuntimeBackend.{name} 없음"
        assert callable(method), f"PgRuntimeBackend.{name} 는 callable 이어야 함"
        # M2-b 구현체는 NotImplementedError 를 raise 하지 않음 (conn=None 이면 AttributeError)
        assert not getattr(method, "__isabstractmethod__", False), (
            f"PgRuntimeBackend.{name} 는 abstract 이면 안 됨 (M2-b 구현 완료)"
        )


def test_dual_write_mirror_noop_when_disabled(monkeypatch):
    """AGENT_RUNTIME_DUAL_WRITE=0 (default) 시 _dual_write_runtime_mirror 은 no-op.

    M2-b: connection 은 내부 관리(_get_pg_runtime_conn). factory 인자 없음.
    """
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", False)

    called = []
    def fake_get_conn():
        called.append(1)
        return None

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", fake_get_conn)
    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")
    assert not called, "DUAL_WRITE=0 이면 _get_pg_runtime_conn 이 호출되면 안 됨"


def test_dual_write_mirror_pg_failure_nonfatal_when_not_required(monkeypatch):
    """AGENT_RUNTIME_PG_REQUIRED=0 이면 PG 예외가 caller 로 전파되지 않음.

    M2-b: _get_pg_runtime_conn 을 monkeypatch 로 대체.
    """
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", False)

    def failing_get_conn():
        raise ConnectionError("PG unreachable")

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", failing_get_conn)
    # 예외 없이 반환되어야 함
    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")


def test_dual_write_mirror_pg_failure_fatal_when_required(monkeypatch):
    """AGENT_RUNTIME_PG_REQUIRED=1 이면 PG 예외가 caller 로 전파됨.

    M2-b: _get_pg_runtime_conn 을 monkeypatch 로 대체.
    """
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", True)

    def failing_get_conn():
        raise ConnectionError("PG unreachable")

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", failing_get_conn)
    with pytest.raises(ConnectionError):
        rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")
