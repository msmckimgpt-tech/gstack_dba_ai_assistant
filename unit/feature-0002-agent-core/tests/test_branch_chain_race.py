"""feature-0019 branch-chain-race 회귀 테스트.

버그: 재답변(reanswer) 브랜치 대화에서 새 메시지 parent 를 대화-공유 active_leaf 를 매 write
마다 재-read 해 결정 → 동시 재답변 setup/overlap 으로 active_leaf 가 분기점(M.parent)으로
리셋되면 **답변이 user 메시지의 형제로 붙어**(자식이 아님) active-path 걷기에서 user 가 누락 →
화면에서 사라지고 assistant 답변만 쌓임(라이브 대화 20260722015229-79da15cb 실측).

수정: run-scoped thread-local 커서(runtime_backend.branch_run_*)로 이 run 의 직전 write id 에
이어붙인다 — active_leaf 리셋과 무관하게 `user → 답변` 체인 무결.

본 테스트는 표시 store 쓰기 choke-point `memory.save_memory_message` 를 mock 백엔드로 격리해,
run 도중 active_leaf 가 분기점으로 리셋돼도 답변이 user 에 체인되는지 검증한다(순수 로직·DB 불요).
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src")))

import modules.runtime_backend as rb
import modules.memory as memory


class _FakeBackend:
    """parent 링크 + active_display_leaf 를 in-memory 로 추적하는 mock display backend."""

    def __init__(self, branch_point_id):
        self._next = branch_point_id + 1
        self.active_leaf = branch_point_id      # 초기 = 분기점(M.parent), reanswer setup 이 세팅한 값
        self.parents = {}                       # id -> parent_message_id

    def load_display_branch_state(self, conn, *, conversation_id):
        return {"has_branches": True, "active_leaf_id": self.active_leaf}

    def save_memory_message(self, conn, *, conversation_id, role, content, meta_json,
                            parent_message_id, edit_root_message_id, edit_version, core_message_id):
        mid = self._next
        self._next += 1
        self.parents[mid] = parent_message_id
        return mid

    def set_active_display_leaf(self, conn, *, conversation_id, leaf_id):
        self.active_leaf = leaf_id


class _FakeConn:
    def close(self):
        pass


def _patch(monkeypatch, fake):
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _FakeConn())
    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: fake)


def test_reanswer_answer_chains_to_user_even_if_active_leaf_reset(monkeypatch):
    """핵심 회귀: run 도중 active_leaf 가 분기점으로 리셋돼도 답변은 user(직전 write)에 체인된다."""
    BRANCH_POINT = 1270  # M.parent (분기점) — 라이브 결함 재현값
    fake = _FakeBackend(BRANCH_POINT)
    _patch(monkeypatch, fake)

    rb.branch_run_begin(True)   # 이 대화 has_branches=true
    try:
        # 1) user 메시지 write — 분기점에 체인 + leaf 전진, 커서=user_id
        user_id = memory.save_memory_message(_FakeConn(), "cid", "user", "로그 흐름만 따로 답변해주세요.",
                                             {"internal": False})
        assert fake.parents[user_id] == BRANCH_POINT, "user 는 분기점에 체인돼야"
        assert fake.active_leaf == user_id
        assert rb.branch_chain_get("disp") == user_id

        # 2) *** 경합 시뮬레이션 ***: 동시 재답변 setup 이 active_leaf 를 분기점으로 리셋
        fake.active_leaf = BRANCH_POINT

        # 3) 답변 write — 수정 전이면 리셋된 active_leaf(분기점)에 붙어 user 형제가 됐다.
        #    수정 후엔 run 커서(user_id)에 붙어야 한다.
        answer_id = memory.save_memory_message(_FakeConn(), "cid", "assistant", "완벽합니다! 이제 아이템 로그 흐름을…",
                                               {"internal": False})
        assert fake.parents[answer_id] == user_id, (
            f"답변은 user({user_id})의 자식이어야 하는데 parent={fake.parents[answer_id]} "
            f"(분기점 {BRANCH_POINT} 이면 user 가 active-path 에서 사라지는 결함)"
        )
        assert fake.parents[answer_id] != BRANCH_POINT
        assert fake.active_leaf == answer_id
    finally:
        rb.branch_run_end()


def test_multi_step_answer_chains_within_run(monkeypatch):
    """tool 스텝이 끼어도(user→step→step→답변) 답변은 자기 run 의 마지막 write 에 체인."""
    BRANCH_POINT = 5091
    fake = _FakeBackend(BRANCH_POINT)
    _patch(monkeypatch, fake)
    rb.branch_run_begin(True)
    try:
        uid = memory.save_memory_message(_FakeConn(), "cid", "user", "u", {"internal": False})
        # 중간에 active_leaf 가 여러 번 리셋돼도 커서 체인은 단조 증가
        fake.active_leaf = BRANCH_POINT
        s1 = memory.save_memory_message(_FakeConn(), "cid", "assistant", "step1", {"internal": False})
        fake.active_leaf = BRANCH_POINT
        s2 = memory.save_memory_message(_FakeConn(), "cid", "assistant", "step2", {"internal": False})
        fake.active_leaf = BRANCH_POINT
        ans = memory.save_memory_message(_FakeConn(), "cid", "assistant", "final", {"internal": False})
        assert fake.parents[uid] == BRANCH_POINT
        assert fake.parents[s1] == uid
        assert fake.parents[s2] == s1
        assert fake.parents[ans] == s2, "답변은 직전 write(s2)에 체인 — 분기점/과거 turn 이 아님"
    finally:
        rb.branch_run_end()


def test_non_branched_conversation_unaffected(monkeypatch):
    """비분기 대화(active=False): 커서 경로 미진입 → 기존 auto append(has_branches=false → parent None)."""
    class _NoBranch(_FakeBackend):
        def load_display_branch_state(self, conn, *, conversation_id):
            return {"has_branches": False, "active_leaf_id": None}

    fake = _NoBranch(0)
    _patch(monkeypatch, fake)
    rb.branch_run_begin(False)   # 비분기
    try:
        mid = memory.save_memory_message(_FakeConn(), "cid", "user", "u", {"internal": False})
        assert fake.parents[mid] is None, "비분기 대화는 parent 미설정(기존 linear append, INV-1)"
        assert fake.active_leaf == 0, "비분기 대화는 leaf 전진 안 함"
    finally:
        rb.branch_run_end()


def test_branch_run_end_clears_cursor(monkeypatch):
    """teardown 후 커서/active 플래그 해제 — 스레드 재사용 시 stale leak 방지."""
    rb.branch_run_begin(True)
    rb.branch_chain_set("disp", 999)
    rb.branch_chain_set("core", 888)
    assert rb.branch_run_active() is True
    rb.branch_run_end()
    assert rb.branch_run_active() is False
    assert rb.branch_chain_get("disp") is None
    assert rb.branch_chain_get("core") is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))


# ── §18.8 리뷰 권고 추가 커버리지: core store(_save_message) + leak 봉인 ──

class _FakeCoreBackend:
    """core_messages parent 링크 + active_leaf 추적 mock."""
    def __init__(self, branch_point_id):
        self._next = branch_point_id + 1
        self.active_leaf = branch_point_id
        self.parents = {}

    def load_branch_state(self, conn, *, conversation_id):
        return {"has_branches": True, "active_leaf_id": self.active_leaf}

    def save_core_message(self, conn, *, conversation_id, role, content, tool_calls,
                          tool_call_id, name, sender_account_id, recall_floor_created_at,
                          parent_message_id):
        mid = self._next
        self._next += 1
        self.parents[mid] = parent_message_id
        return mid

    def set_active_leaf(self, conn, *, conversation_id, leaf_id):
        self.active_leaf = leaf_id


def test_core_store_answer_chains_to_tool_tail_within_run(monkeypatch):
    """core store: run 도중 active_leaf 리셋돼도 최종 답변이 자기 run 의 직전 write(tool tail)에 체인."""
    import agent_core
    BRANCH = 5091
    fake = _FakeCoreBackend(BRANCH)
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _FakeConn())
    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: fake)

    rb.branch_run_begin(True)
    try:
        uid = None  # _save_message 는 None/ id 반환; 실제 chain 은 fake.parents 로 검증
        agent_core._save_message(_FakeConn(), "cid", "user", content="q")   # 5092, parent 5091
        fake.active_leaf = BRANCH                                            # 리셋 시뮬
        agent_core._save_message(_FakeConn(), "cid", "assistant", content="{tool_calls}")  # 5093 -> 5092
        fake.active_leaf = BRANCH
        agent_core._save_message(_FakeConn(), "cid", "tool", content="result")             # 5094 -> 5093
        fake.active_leaf = BRANCH
        agent_core._save_message(_FakeConn(), "cid", "assistant", content="final answer")  # 5095 -> 5094
        # 체인: 5092(u,5091) 5093(5092) 5094(5093) 5095(5094) — 각 직전 write, 분기점 아님
        ids = sorted(fake.parents)
        assert fake.parents[ids[0]] == BRANCH, "user 는 분기점"
        assert fake.parents[ids[1]] == ids[0]
        assert fake.parents[ids[2]] == ids[1]
        assert fake.parents[ids[3]] == ids[2], "최종 답변은 직전 tool(자기 run) — 분기점/타 turn 아님"
        assert BRANCH not in [fake.parents[i] for i in ids[1:]]
    finally:
        rb.branch_run_end()


def test_leaked_cursor_does_not_contaminate_next_nonbranch_write(monkeypatch):
    """§18.8 리뷰 [1]: 이전 run 이 예외로 teardown skip → active=True+stale 커서 잔존 상태에서도,
    다음 run 진입 시 무조건 리셋(_run_agent_core 가 begin 전 branch_run_end 호출) + 비분기면 커서 미사용."""
    # 1) leak 시뮬: 활성 + stale 커서
    rb.branch_run_begin(True)
    rb.branch_chain_set("disp", 99999)
    rb.branch_chain_set("core", 88888)
    assert rb.branch_run_active() is True

    # 2) 다음 run 진입 = 무조건 리셋(_run_agent_core entry 의 _branch_run_end0()) → 비분기(_hb=False)면 활성 안 함
    rb.branch_run_end()   # entry unconditional reset
    # (has_branches=False 이므로 branch_run_begin(True) 미호출 = 비활성 유지)
    assert rb.branch_run_active() is False

    # 3) 비분기 write: stale 커서를 쓰지 않고 기존 auto append(has_branches=false → parent None)
    class _NoBranch(_FakeBackend):
        def load_display_branch_state(self, conn, *, conversation_id):
            return {"has_branches": False, "active_leaf_id": None}
    fake = _NoBranch(0)
    _patch(monkeypatch, fake)
    mid = memory.save_memory_message(_FakeConn(), "cid2", "user", "u", {"internal": False})
    assert fake.parents[mid] is None, "leak 후에도 비분기 write 는 stale 커서(88888/99999) 미사용"
