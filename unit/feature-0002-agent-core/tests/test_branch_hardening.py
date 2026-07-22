"""feature-0019 message-editing — branch-hardening 회귀 테스트.

두 잠재 결함(footgun)에 대한 방어를 DB 없이 가드한다:

  footgun A (fail-closed 대화 바인딩): 웹/ask 경로(account_id 지정)에서 conversation_id 가
    비어 있으면, agent_core._get_conversation_id 의 프로세스 전역 env·호스트 공유 파일 폴백을
    쓰지 않고 즉시 실패한다(cross-conversation 누출 표면 봉인). CLI/eval(account_id=None)은
    파일 폴백을 유지한다(정당 — 단일 사용자 로컬).

  footgun B (run-scoped active-leaf): 브랜치 대화(has_branches=true)의 한 run 이 여러 메시지를
    순차 append 할 때, 생성 중 브랜치 페이징 전환이 DB active_leaf 를 바꿔도 실행 중 답변의
    부모 체인이 산란하지 않는다(run-local last-leaf 로 격리). 비분기 대화는 무영향(INV-1).

`make test`(agent 이미지)에서 DB 없이 실행된다.
"""
from __future__ import annotations

import agent_core
from modules import memory
from modules import runtime_backend as rb
from shared import config as cfg


# ─────────────────────────────────────────────────────────────────────────────
# footgun A — fail-closed 대화 바인딩 (전역/공유 폴백 차단)
# ─────────────────────────────────────────────────────────────────────────────

def test_footgun_a_web_path_empty_conversation_id_fails_closed(monkeypatch):
    """account_id 지정(웹/ask) + conversation_id 비어있음 → fail-closed, 전역 폴백 미호출."""
    called = {"get_conv": False}

    def _spy(*a, **k):
        called["get_conv"] = True
        return "LEAKED-SHARED-CID"  # 전역 env/공유 파일에 있을 법한 값

    monkeypatch.setattr(agent_core, "_get_conversation_id", _spy)
    res = agent_core.run_agent(
        "hi", conversation_id=None, account_id=7,
        model="claude-haiku-4-5-20251001",
    )
    assert res.get("error")                       # fail-closed 에러
    assert res.get("conversation_id") in ("", None)  # 어떤 대화에도 바인딩 안 함
    assert called["get_conv"] is False            # 전역/공유 대화 폴백 미사용(핵심)


def test_footgun_a_web_path_empty_string_conversation_id_fails_closed(monkeypatch):
    """conversation_id='' (빈 문자열) 도 falsy → fail-closed."""
    called = {"get_conv": False}
    monkeypatch.setattr(
        agent_core, "_get_conversation_id",
        lambda *a, **k: called.__setitem__("get_conv", True) or "X",
    )
    res = agent_core.run_agent(
        "hi", conversation_id="", account_id=3, model="claude-haiku-4-5-20251001",
    )
    assert res.get("error")
    assert called["get_conv"] is False


def test_footgun_a_cli_path_does_not_trigger_failclosed():
    """account_id=None(CLI/eval)은 footgun A fail-closed 를 발동시키지 않는다(파일 폴백 정당).

    테스트 환경엔 LLM 자격증명이 없어 run 은 다른 사유로 조기 종료될 수 있으나(그건 무방),
    반환 에러가 fail-closed '대화 컨텍스트' 에러여선 안 된다 — account_id=None 은 가드 대상 아님."""
    res = agent_core.run_agent(
        "hi", conversation_id=None, account_id=None,
        model="claude-haiku-4-5-20251001",
    )
    err = res.get("error") or ""
    assert "conversation_id 미지정" not in err
    assert "대화 컨텍스트를 확인할 수 없습니다" not in err


# ─────────────────────────────────────────────────────────────────────────────
# footgun B — run-scoped active-leaf (생성 중 브랜치 전환 산란 방지)
# ─────────────────────────────────────────────────────────────────────────────

class _FakeCoreBackend:
    """core_messages 쓰기 백엔드 mock. load_branch_state 는 호출마다 시퀀스의 다음 active_leaf 를
    돌려줘 '생성 중 브랜치 전환'(active_leaf 동시 변경)을 시뮬레이션한다."""

    def __init__(self, active_leaf_sequence, has_branches=True):
        self._seq = list(active_leaf_sequence)
        self._i = 0
        self._has = has_branches
        self._next_id = 200
        self.saved_parents: list = []
        self.set_leaf_calls: list = []

    def load_branch_state(self, conn, *, conversation_id):
        al = self._seq[self._i] if self._i < len(self._seq) else self._seq[-1]
        self._i += 1
        return {"has_branches": self._has, "active_leaf_id": al}

    def save_core_message(self, conn, *, conversation_id, role, content, tool_calls=None,
                          tool_call_id=None, name=None, sender_account_id=None,
                          recall_floor_created_at=None, parent_message_id=None):
        self.saved_parents.append(parent_message_id)
        self._next_id += 1
        return self._next_id

    def set_active_leaf(self, conn, *, conversation_id, leaf_id):
        self.set_leaf_calls.append(leaf_id)


class _FakeDisplayBackend:
    def __init__(self, active_leaf_sequence, has_branches=True):
        self._seq = list(active_leaf_sequence)
        self._i = 0
        self._has = has_branches
        self._next_id = 300
        self.saved_parents: list = []
        self.set_leaf_calls: list = []

    def load_display_branch_state(self, conn, *, conversation_id):
        al = self._seq[self._i] if self._i < len(self._seq) else self._seq[-1]
        self._i += 1
        return {"has_branches": self._has, "active_leaf_id": al}

    def save_memory_message(self, conn, *, conversation_id, role, content, meta_json=None,
                            parent_message_id=None, edit_root_message_id=None,
                            edit_version=1, core_message_id=None):
        self.saved_parents.append(parent_message_id)
        self._next_id += 1
        return self._next_id

    def set_active_display_leaf(self, conn, *, conversation_id, leaf_id):
        self.set_leaf_calls.append(leaf_id)


class _FakeConn:
    def close(self):
        pass


def _patch_core(monkeypatch, backend):
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _FakeConn())
    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: backend)


def test_footgun_b_core_run_local_leaf_isolates_from_concurrent_switch(monkeypatch):
    """run 첫 append 만 DB active_leaf(100), 이후는 run-local(직전 new_id) — 동시 브랜치 전환
    (load 가 999·888 반환)이 부모 체인을 산란시키지 못한다."""
    fake = _FakeCoreBackend(active_leaf_sequence=[100, 999, 888])  # 2·3회차 = 동시 전환
    _patch_core(monkeypatch, fake)
    cfg.reset_run_active_leaf()

    agent_core._save_message(None, "c1", "user", content="q")       # parent=100, id=201
    agent_core._save_message(None, "c1", "assistant", content="a1")  # parent=201(run-local)
    agent_core._save_message(None, "c1", "assistant", content="a2")  # parent=202(run-local)

    assert fake.saved_parents == [100, 201, 202]   # run-local 체인
    assert fake.saved_parents != [100, 999, 888]   # 수정 전(산란) 이 아님
    assert fake.set_leaf_calls == [201, 202, 203]  # DB active_leaf 도 정본 전진


def test_footgun_b_reset_clears_run_local_leaf_between_runs(monkeypatch):
    """reset_run_active_leaf() 후의 새 run 은 DB active_leaf 를 다시 부모로 쓴다(이전 run leaf 누출 없음)."""
    fake = _FakeCoreBackend(active_leaf_sequence=[100, 500])
    _patch_core(monkeypatch, fake)

    cfg.reset_run_active_leaf()                 # run 1
    agent_core._save_message(None, "c1", "user", content="q")   # load seq[0]=100 → parent=100, run-local=201
    assert fake.saved_parents[-1] == 100

    cfg.reset_run_active_leaf()                 # run 2 시작 — run-local 초기화
    agent_core._save_message(None, "c1", "user", content="q2")  # load seq[1]=500 → parent=500(DB), NOT 201
    assert fake.saved_parents[-1] == 500        # 이전 run 의 leaf(201) 누출 안 됨(reset 동작)


def test_footgun_b_nonbranch_conversation_unaffected_inv1(monkeypatch):
    """비분기 대화(has_branches=false)는 chaining 미진입 — parent 항상 None, active_leaf 미전진(INV-1)."""
    fake = _FakeCoreBackend(active_leaf_sequence=[100], has_branches=False)
    _patch_core(monkeypatch, fake)
    cfg.reset_run_active_leaf()

    agent_core._save_message(None, "c1", "user", content="q")
    agent_core._save_message(None, "c1", "assistant", content="a")

    assert fake.saved_parents == [None, None]   # 브랜치 체이닝 미적용
    assert fake.set_leaf_calls == []            # active_leaf 미전진


def test_footgun_b_explicit_parent_bypasses_run_local(monkeypatch):
    """엔드포인트가 parent_message_id 를 명시하면(sibling 생성) 그 값을 그대로 쓴다(run-local 무시)."""
    fake = _FakeCoreBackend(active_leaf_sequence=[100])
    _patch_core(monkeypatch, fake)
    cfg.reset_run_active_leaf()
    agent_core._save_message(None, "c1", "user", content="edited", parent_message_id=42)
    assert fake.saved_parents == [42]
    assert fake.set_leaf_calls == []            # 명시 parent 경로는 run-local 전진 안 함


def test_footgun_b_display_run_local_leaf_isolates_from_concurrent_switch(monkeypatch):
    """표시 store(save_memory_message) 도 core 와 동일하게 run-local 로 격리."""
    fake = _FakeDisplayBackend(active_leaf_sequence=[300, 777, 666])
    _patch_core(monkeypatch, fake)
    cfg.reset_run_active_leaf()

    memory.save_memory_message(None, "c1", "user", "q")
    memory.save_memory_message(None, "c1", "user", "a1")
    memory.save_memory_message(None, "c1", "user", "a2")

    assert fake.saved_parents == [300, 301, 302]   # run-local 체인
    assert fake.saved_parents != [300, 777, 666]


def test_footgun_b_core_and_display_leaves_independent(monkeypatch):
    """core/display run-local leaf 는 별도 id 공간 — 서로 오염하지 않는다."""
    core = _FakeCoreBackend(active_leaf_sequence=[100, 900])
    _patch_core(monkeypatch, core)
    cfg.reset_run_active_leaf()
    agent_core._save_message(None, "c1", "user", content="q")   # core run-local=201
    # display 를 같은 run 에서 저장 — core 의 201 이 display 부모로 새면 안 됨
    disp = _FakeDisplayBackend(active_leaf_sequence=[300, 900])
    _patch_core(monkeypatch, disp)
    memory.save_memory_message(None, "c1", "user", "d1")        # display 첫 append → DB 300
    assert disp.saved_parents == [300]                          # core leaf(201) 누출 없음
