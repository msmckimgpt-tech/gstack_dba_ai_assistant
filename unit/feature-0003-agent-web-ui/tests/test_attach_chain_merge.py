"""attach-chain-merge — 분열 체인 병합 스크립트의 판정·계획 로직 회귀 가드.

본 스크립트는 **라이브 첨부 메타데이터를 다시 쓰는 파괴적 도구**라, 계획 산출이 틀리면
사용자 대화의 첨부 목록이 잘못 합쳐진다. 아래는 그 계획 단계를 잠근다:

  C1  base_name — `_v<n>` 접미만 제거하고 확장자·내부 `_v` 는 보존.
  C2  단일 체인·단일 이름 그룹은 계획에 오르지 않는다(무의미 write 0).
  C3  이름이 갈린 assistant 편집본이 원본 체인으로 흡수된다(시각순 v1..vN · root 통일).
  C4  재업로드로 새 root 가 생긴 분열이 하나의 체인으로 합쳐진다.
  C5  SupersededAt — 마지막 1건만 NULL, 나머지는 **다음 버전의 CreatedAt**.
  C6  사용자가 직접 `_v<n>` 이름으로 올린 것만 있는 그룹은 **제외**(분열이 아님).
  C7  `--days` 범위 밖 그룹은 계획에서 빠진다.
  C8  대화·계정 스코프를 넘어 합쳐지지 않는다(IDOR·오병합 차단).
  C9  UNIQUE(root, version) 충돌 회피 — apply 가 2단계(오프셋 → 최종)로 UPDATE 한다.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "attach_chain_merge.py"


def _load_module():
    """스크립트를 import 한다 — 상단 `import app` 은 최소 스텁으로 대체.

    스크립트는 컨테이너 경로(`/app/web`)를 전제로 `app` 을 import 하므로, 테스트에서는
    `_hmac_filename` 만 가진 가짜 모듈을 sys.modules 에 미리 꽂는다. 계획 산출 로직은
    app 의 다른 기능에 의존하지 않는다(의존이 늘면 이 테스트가 먼저 깨져 알려준다).
    """
    fake = types.ModuleType("app")
    fake._hmac_filename = lambda name: "hmac:" + str(name)  # noqa: SLF001
    saved = sys.modules.get("app")
    sys.modules["app"] = fake
    try:
        spec = importlib.util.spec_from_file_location("_attach_chain_merge", _SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if saved is not None:
            sys.modules["app"] = saved
        else:
            sys.modules.pop("app", None)


M = _load_module()

T0 = _dt.datetime(2026, 8, 1, 10, 0, 0)


def _row(id_, name, *, conv="c1", acct=1, ver=1, root=None, superseded=None,
         role="user", created=None, meta=None):
    return {
        "Id": id_, "ConversationId": conv, "AccountId": acct,
        "OriginalFilename": name, "FilenameHmac": "old",
        "VersionNumber": ver, "RootAttachmentId": root, "SupersededAt": superseded,
        "CreatedByRole": role, "CreatedAt": created or T0,
        "MetaJson": json.dumps(meta) if meta else None,
    }


# ── C1: base_name ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("x.sql", "x.sql"),
    ("x_v2.sql", "x.sql"),
    ("x_v10.sql", "x.sql"),
    ("report_v3", "report"),
    ("v2_report.sql", "v2_report.sql"),      # 접미가 아닌 내부 `v2` 는 보존
    ("a_v2_b.sql", "a_v2_b.sql"),            # 끝이 아니면 보존
    ("", ""),
])
def test_c1_base_name(raw, expected):
    assert M.base_name(raw) == expected


# ── C2: 정합한 그룹은 계획 0 ─────────────────────────────────────────────────
def test_c2_clean_chain_produces_no_plan():
    rows = [
        _row(1, "x.sql", ver=1, root=None, superseded=T0, created=T0),
        _row(2, "x.sql", ver=2, root=1, created=T0 + _dt.timedelta(hours=1)),
    ]
    plan, skipped = M.build_plan(rows, None)
    assert plan == [], f"이미 단일 체인·단일 이름인데 write 를 계획했다: {plan}"
    assert skipped == []


# ── C3: assistant 편집본(이름만 다름) 흡수 ───────────────────────────────────
def test_c3_assistant_edit_absorbed_into_origin_chain():
    rows = [
        _row(10, "q.sql", ver=1, root=None, superseded=T0, created=T0),
        _row(11, "q_v2.sql", ver=2, root=10, role="assistant",
             created=T0 + _dt.timedelta(hours=1), meta={"assistant_edit_of": 10}),
    ]
    plan, _ = M.build_plan(rows, None)
    by_id = {p["id"]: p for p in plan}
    assert 11 in by_id, "편집본 파일명이 원본으로 통일돼야 한다"
    assert by_id[11]["after"]["OriginalFilename"] == "q.sql"
    assert by_id[11]["after"]["RootAttachmentId"] == 10
    assert by_id[11]["after"]["VersionNumber"] == 2
    assert by_id[11]["after"]["SupersededAt"] is None, "최신 1건은 live 여야 한다"
    assert by_id[11]["after"]["FilenameHmac"] == "hmac:q.sql", "파일명 변경 시 HMAC 재계산"


# ── C4: 재업로드로 갈라진 새 root 재결합 ─────────────────────────────────────
def test_c4_split_roots_merge_into_one_chain():
    t1, t2, t3 = T0, T0 + _dt.timedelta(hours=1), T0 + _dt.timedelta(hours=2)
    rows = [
        _row(20, "s.sql", ver=1, root=None, superseded=t2, created=t1),
        _row(21, "s_v2.sql", ver=2, root=20, role="assistant", created=t2,
             meta={"assistant_edit_of": 20}),
        _row(22, "s.sql", ver=1, root=None, created=t3),   # 분열: 새 root
    ]
    plan, _ = M.build_plan(rows, None)
    after = {p["id"]: p["after"] for p in plan}
    assert after[21]["RootAttachmentId"] == 20 and after[21]["VersionNumber"] == 2
    assert after[22]["RootAttachmentId"] == 20, "새 root 가 원 체인으로 흡수돼야 한다"
    assert after[22]["VersionNumber"] == 3
    assert {p["after"]["OriginalFilename"] for p in plan} == {"s.sql"}
    # 첫 row 는 root 유지(NULL) — 계획에 오르더라도 root 를 바꾸지 않는다.
    assert after.get(20, {"RootAttachmentId": None})["RootAttachmentId"] is None


# ── C5: SupersededAt = 다음 버전 생성 시각 · 최신만 NULL ─────────────────────
def test_c5_superseded_stamps_follow_next_version():
    t1, t2, t3 = T0, T0 + _dt.timedelta(hours=1), T0 + _dt.timedelta(hours=2)
    rows = [
        _row(30, "m.sql", ver=1, root=None, created=t1),
        _row(31, "m.sql", ver=1, root=None, created=t2),
        _row(32, "m_v2.sql", ver=2, root=30, role="assistant", created=t3,
             meta={"assistant_edit_of": 30}),
    ]
    plan, _ = M.build_plan(rows, None)
    after = {p["id"]: p["after"] for p in plan}
    assert after[30]["SupersededAt"] == t2
    assert after[31]["SupersededAt"] == t3
    assert after[32]["SupersededAt"] is None
    lives = [i for i, a in after.items() if a["SupersededAt"] is None]
    assert lives == [32], f"체인의 live 는 정확히 1건이어야 한다: {lives}"


# ── C6: 사용자가 직접 `_v<n>` 이름으로 올린 것만 있으면 제외 ─────────────────
def test_c6_user_named_version_suffix_is_skipped():
    rows = [
        _row(40, "draft_v1.sql", ver=1, root=None, created=T0),
        _row(41, "draft_v2.sql", ver=1, root=None, created=T0 + _dt.timedelta(hours=1)),
    ]
    plan, skipped = M.build_plan(rows, None)
    assert plan == [], "사용자가 고른 이름을 임의로 합치면 안 된다"
    assert len(skipped) == 1 and skipped[0]["ids"] == [40, 41]


def test_c6b_user_named_but_base_present_is_merged():
    """base 이름 row 가 함께 있으면 분열로 보고 합친다(제외 규칙이 과하지 않은지)."""
    rows = [
        _row(45, "draft.sql", ver=1, root=None, created=T0),
        _row(46, "draft_v2.sql", ver=1, root=None, created=T0 + _dt.timedelta(hours=1)),
    ]
    plan, skipped = M.build_plan(rows, None)
    assert skipped == []
    assert {p["id"] for p in plan} >= {46}
    assert all(p["after"]["OriginalFilename"] == "draft.sql" for p in plan)


# ── C7: --days 범위 ──────────────────────────────────────────────────────────
def test_c7_days_window_excludes_old_groups():
    old = _dt.datetime.now() - _dt.timedelta(days=40)
    rows = [
        _row(50, "o.sql", ver=1, root=None, created=old),
        _row(51, "o_v2.sql", ver=2, root=50, role="assistant", created=old,
             meta={"assistant_edit_of": 50}),
    ]
    assert M.build_plan(rows, 7)[0] == [], "범위 밖 그룹이 계획에 올랐다"
    assert M.build_plan(rows, None)[0] != [], "범위 미지정이면 대상이어야 한다"


# ── C8: 대화·계정 경계 ───────────────────────────────────────────────────────
def test_c8_never_merges_across_conversation_or_account():
    rows = [
        _row(60, "x.sql", conv="c1", acct=1, created=T0),
        _row(61, "x_v2.sql", conv="c2", acct=1, role="assistant", created=T0,
             meta={"assistant_edit_of": 60}),
        _row(62, "x_v2.sql", conv="c1", acct=2, role="assistant", created=T0,
             meta={"assistant_edit_of": 60}),
    ]
    plan, _ = M.build_plan(rows, None)
    assert plan == [], "대화/계정이 다르면 각자 단일 그룹이라 합칠 것이 없다"


# ── C9: apply 2단계 UPDATE (UNIQUE 충돌 회피) ────────────────────────────────
class _FakeCursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append((" ".join(sql.split()), params))

    def fetchone(self):
        return (5,)

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.log = []
        self.committed = False
        self.rolled_back = False

    def cursor(self, dictionary=False):
        return _FakeCursor(self.log)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_c9_apply_uses_two_phase_version_update():
    plan = [
        {"id": 70, "after": {"OriginalFilename": "x.sql", "FilenameHmac": "h",
                             "RootAttachmentId": None, "VersionNumber": 1, "SupersededAt": None}},
        {"id": 71, "after": {"OriginalFilename": "x.sql", "FilenameHmac": "h",
                             "RootAttachmentId": 70, "VersionNumber": 2, "SupersededAt": None}},
    ]
    conn = _FakeConn()
    assert M.apply_plan(conn, plan) == 2
    assert conn.committed and not conn.rolled_back
    stmts = [s for s, _ in conn.log]
    # 1단계: VersionNumber 만 바꾸는 UPDATE 가 대상 row 수만큼 선행.
    phase1 = [i for i, s in enumerate(stmts) if s.startswith("UPDATE WebConversationAttachments SET VersionNumber = %s")]
    phase2 = [i for i, s in enumerate(stmts) if "SET OriginalFilename" in s]
    assert len(phase1) == 2 and len(phase2) == 2
    assert max(phase1) < min(phase2), "오프셋 단계가 최종 UPDATE 보다 먼저여야 UNIQUE 충돌을 피한다"
    # 오프셋은 기존 MAX(VersionNumber)=5 보다 충분히 커야 하고 row 마다 달라야 한다.
    offsets = [p[0] for s, p in conn.log if s.startswith("UPDATE WebConversationAttachments SET VersionNumber = %s")]
    assert all(o > 1000 for o in offsets) and len(set(offsets)) == len(offsets)


def test_c9b_apply_rolls_back_on_failure():
    class _Boom(_FakeConn):
        def cursor(self, dictionary=False):
            class C(_FakeCursor):
                def execute(self, sql, params=None):
                    if "SET OriginalFilename" in sql:
                        raise RuntimeError("boom")
                    super().execute(sql, params)
            return C(self.log)

    conn = _Boom()
    plan = [{"id": 80, "after": {"OriginalFilename": "x.sql", "FilenameHmac": "h",
                                 "RootAttachmentId": None, "VersionNumber": 1, "SupersededAt": None}}]
    with pytest.raises(RuntimeError):
        M.apply_plan(conn, plan)
    assert conn.rolled_back and not conn.committed, "실패 시 부분 적용이 남으면 안 된다"
