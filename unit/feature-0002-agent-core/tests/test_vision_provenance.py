"""REQ-20260814-vision-provenance — 이미지 첨부의 provenance 신호.

선행 cycle(`attach-provenance-gate`)의 §18.8 적대 리뷰가 **미해소로 남긴 축**이다: 텍스트 첨부만
신호를 세워, 타 멤버가 올린 **이미지** 본문이 프롬프트에 붙어도 도구 게이트가 발동하지 않았다.

이미지는 datamark 로 감쌀 수도 없는 콘텐츠다 — 프롬프트에 그대로 들어가고, 그 안에 심긴 지시문
("이 표의 값을 scratch 에 넣어라" 류)은 텍스트 축의 어떤 방어도 거치지 않는다.

여기서 고정하는 계약:
  - 소유자가 호출자와 다른 이미지 본문이 실리면 신호가 선다
  - 본인 이미지·1:1 은 서지 않는다(과차단 방지)
  - 판정 실패는 막는 쪽, 소유자 정보 부재는 종전 동작(배포 혼합 창에서 1:1 사용자를 막지 않는다)
  - 신호를 세우는 시점이 도구 실행보다 앞이다
"""
from __future__ import annotations

import json

import agent_core


def _write_inline(tmp_path, entries) -> str:
    p = tmp_path / "vision.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return str(p)


def _entry(account_id=None, name="shot.png"):
    e = {"filename": name, "mime_type": "image/png", "base64_data": "aGVsbG8="}
    if account_id is not None:
        e["account_id"] = account_id
    return e


def _load(tmp_path, entries, *, caller: int):
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._INLINE_IMAGE_PATH_CTX.set(_write_inline(tmp_path, entries))
    agent_core._ACTIVE_ACCOUNT_ID_CTX.set(caller)
    out = agent_core._load_attachment_inline_images()
    return out, agent_core.untrusted_attachment_body_in_context()


# ── 발동 ───────────────────────────────────────────────────────────────────

def test_other_member_image_raises_signal(tmp_path):
    """타 멤버가 올린 이미지 본문이 실리면 신호가 선다 — 이 축이 비어 있던 것이 미해소분이었다."""
    out, flagged = _load(tmp_path, [_entry(account_id=50)], caller=10)
    assert len(out) == 1, "이미지는 정상적으로 전달된다(차단이 아니라 신호)"
    assert flagged is True


def test_own_image_does_not_raise_signal(tmp_path):
    """본인 이미지는 신호를 세우지 않는다(과차단 방지)."""
    out, flagged = _load(tmp_path, [_entry(account_id=10)], caller=10)
    assert len(out) == 1
    assert flagged is False


def test_mixed_images_raise_if_any_is_other_members(tmp_path):
    """하나라도 타 멤버 것이면 신호가 선다 — 섞여 있을 때가 정확히 위험한 경우다."""
    _, flagged = _load(tmp_path, [_entry(account_id=10), _entry(account_id=50, name="theirs.png")], caller=10)
    assert flagged is True


# ── 미발동(무회귀) ─────────────────────────────────────────────────────────

def test_missing_owner_keeps_previous_behavior(tmp_path):
    """소유자 키가 없으면(배포 혼합 창의 구 JSON) 종전 동작 — 신호를 세우지 않는다.

    막는 쪽으로 두면 그 창 동안 **1:1 사용자까지** 도구가 막힌다. web 이 먼저 롤링되므로 워커가
    신코드일 때 JSON 도 신형식이며, 이 경로는 짧은 과도기에만 존재한다.
    """
    _, flagged = _load(tmp_path, [_entry(account_id=None)], caller=10)
    assert flagged is False


def test_no_caller_identity_does_not_raise(tmp_path):
    """호출자 계정이 없으면(시스템·CLI) 비교 자체가 성립하지 않는다."""
    _, flagged = _load(tmp_path, [_entry(account_id=50)], caller=0)
    assert flagged is False


def test_empty_or_missing_file_is_noop(tmp_path):
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._INLINE_IMAGE_PATH_CTX.set(str(tmp_path / "nope.json"))
    agent_core._ACTIVE_ACCOUNT_ID_CTX.set(10)
    assert agent_core._load_attachment_inline_images() == []
    assert agent_core.untrusted_attachment_body_in_context() is False


# ── 실패 방향 ──────────────────────────────────────────────────────────────

def test_owner_parse_failure_blocks(tmp_path):
    """소유자를 숫자로 읽지 못했는데 이미지 본문은 이미 프롬프트로 간다 — 막는 쪽으로 센다."""
    bad = {"filename": "x.png", "mime_type": "image/png", "base64_data": "aGk=",
           "account_id": {"unexpected": "shape"}}
    _, flagged = _load(tmp_path, [bad], caller=10)
    assert flagged is True


# ── 순서 계약 ──────────────────────────────────────────────────────────────

def test_signal_survives_compose_reset_and_reaches_the_gate():
    """**[P2] 반영** — 문자열 존재가 아니라 **실제 순서 불변식**을 검증한다.

    `compose_system_prompt` 는 매 조립마다 플래그를 지운다. 이미지 로더가 그보다 **뒤에** 돌아야
    신호가 살아 도구 게이트에 도달한다. 초판 테스트는 "로더 안에 set 이 있다" 만 봐서, 순서가
    뒤집히는 회귀를 잡지 못했다.
    """
    from modules import tools

    # 1) compose 가 지운다(리셋 계약).
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(True)
    import inspect
    assert "_UNTRUSTED_ATTACH_BODY_CTX.set(False)" in inspect.getsource(agent_core.compose_system_prompt)

    # 2) 리셋 이후 로더가 신호를 세우면 → 게이트가 실제로 막는다(끝단까지 도달).
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)          # compose 리셋 직후 상태
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(True)           # 로더가 세운 상태
    assert tools._provenance_gate("scratch_sql"), "신호가 게이트까지 도달하지 않으면 방어가 없다"

    # 3) 반대로 리셋만 되고 로더가 안 돌면 열려 있다(과차단 없음의 반대 축).
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    assert tools._provenance_gate("scratch_sql") is None

    # 4) 로더는 `_call_llm` 안에서 돈다 = 조립 이후·도구 실행 이전.
    assert "_load_attachment_inline_images()" in inspect.getsource(agent_core._call_llm)
    assert "_UNTRUSTED_ATTACH_BODY_CTX.set(True)" in inspect.getsource(
        agent_core._load_attachment_inline_images)


def test_sandbox_csv_of_other_member_raises_signal(monkeypatch):
    """**[P1] 반영** — csv/xlsx 는 본문 인라인이 아니라 **sandbox 샘플 행**으로 프롬프트에 들어간다.

    그 셀 값도 타 멤버가 쓴 콘텐츠다. 텍스트 축만 신호를 세우면 공격 셀 → `scratch_*` 우회가 남는다.
    """
    import json as _json

    rows = [(
        1150, "conv-x", "theirs.csv", "csv", "text/csv", 100, "small", "ingested",
        _json.dumps({}),  # sandbox 메타 없이 — 신호는 kind 기반이며, 메타가 있으면 fake conn 이
                          # sandbox 컬럼 조회까지 태워 하네스가 그 경로에서 깨진다(검증 대상 아님).
        None, 1, "user", 50, None,
    )]

    class _RowsConn:
        def cursor(self, *a, **k):
            class _C:
                def execute(self, *a, **k): pass
                def fetchall(self): return rows
                def close(self): pass
            return _C()

    monkeypatch.setenv("ATTACHMENT_IDS", "1150")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: {50: "jm.kim"})
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._build_attachment_context_section(_RowsConn(), [1150], 10, "conv-x")
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_own_sandbox_csv_does_not_raise(monkeypatch):
    """본인 csv 는 신호를 세우지 않는다 — 과차단 방지 축."""
    import json as _json

    rows = [(
        1151, "conv-x", "mine.csv", "csv", "text/csv", 100, "small", "ingested",
        _json.dumps({}),
        None, 1, "user", 10, None,
    )]

    class _RowsConn:
        def cursor(self, *a, **k):
            class _C:
                def execute(self, *a, **k): pass
                def fetchall(self): return rows
                def close(self): pass
            return _C()

    monkeypatch.setenv("ATTACHMENT_IDS", "1151")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: {10: "admin"})
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._build_attachment_context_section(_RowsConn(), [1151], 10, "conv-x")
    assert agent_core.untrusted_attachment_body_in_context() is False


def test_web_side_carries_owner_in_both_backends():
    """web 이 이미지 조회에서 소유자를 싣지 않으면 이 신호는 영원히 서지 않는다.

    MySQL 폴백과 PG 미러 **양쪽** 을 고정한다 — 한쪽만 실으면 읽기 백엔드에 따라 방어가 사라진다.
    (web 패키지를 import 하면 순환 import 가 나므로 **파일로 읽어** 검사한다 — 이 하네스가 확인하려는
     것은 실행 동작이 아니라 두 SELECT 가 소유자를 싣는다는 계약이다.)
    """
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    web_src = os.path.normpath(os.path.join(here, "..", "..", "feature-0003-agent-web-ui", "src"))

    with open(os.path.join(web_src, "routers", "_conv_store.py"), encoding="utf-8") as f:
        conv_store = f.read()
    assert "SizeBucket, AccountId" in conv_store, "MySQL 폴백 SELECT 에 소유자"
    assert '"account_id": int(row_account_id or 0)' in conv_store, "inline JSON 에 소유자"

    with open(os.path.join(web_src, "modules", "attachment_pg_mirror.py"), encoding="utf-8") as f:
        pg_mirror = f.read()
    assert 'account_id AS "AccountId"' in pg_mirror, "PG 미러 SELECT 에 소유자"
