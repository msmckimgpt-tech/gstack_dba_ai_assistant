"""TASK-0285: 첨부 버전 현황 표면화 — 3개 보완(②③④) 회귀 테스트.

사용자 요청(TASK-0275 후속 보완):
  ② `'+' > 첨부파일 목록` 의 각 파일에 버전 현황(버전 배지 + 체인 길이) 표시.
  ③ assistant 말풍선 안에 첨부파일을 명시적으로 칩 표시(사용자 말풍선처럼) + 새로고침 영속.
  ④ assistant 가 첨부를 수정하면 진행 단계(step)에 명시적으로 출력.

검증(`make test` agent 이미지, DB 없이 fake conn):
  A1  _attach_assistant_attachments — assistant 메시지에만 _attachments 주입, user 무시.
  A2  _attach_assistant_attachments — 매칭 message_id 없으면 무주입(빈 by_message graceful).
  L1  _load_assistant_attachments_by_message — MetaJson(dict/str) message_id 별 그룹핑.
  L2  _load_assistant_attachments_by_message — message_id 누락/0 인 첨부는 제외.
  L3  _load_assistant_attachments_by_message — 조회 예외 시 빈 dict(fail-soft, history 비차단).
  V1  list_conversation_attachments — 버전 체인 집계 SQL(GROUP BY COALESCE) + version_count 키.
  V2  _serialize_attachment_for_api — 버전 필드가 그대로 직렬화(목록 배지 데이터 소스).
  S1  ask materialize step — 소스에 materialize_attachment step + save_memory_step 기록 존재.
  S2  _resolve_step_display — 저장된 work/reason 이 그대로 표시(materialize step 표시 경로).
"""
from __future__ import annotations

import json

import app


# ── fake DB (dictionary cursor) ─────────────────────────────────────────────
class _DictCursor:
    def __init__(self, rows, *, raise_on_execute=False):
        self._rows = rows
        self._raise = raise_on_execute
        self.last = None

    def execute(self, sql, params=None):
        if self._raise:
            raise RuntimeError("boom")
        self.last = (" ".join(str(sql).split()).lower(), params)

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _DictConn:
    def __init__(self, rows, *, raise_on_execute=False):
        self._rows = rows
        self._raise = raise_on_execute

    def cursor(self, dictionary=False):
        return _DictCursor(self._rows, raise_on_execute=self._raise)


def _att_row(att_id, message_id, *, role="assistant", version=2, filename="q.sql", root=5, meta_as_str=False):
    meta = {"assistant_edit_of": root, "message_id": message_id}
    return {
        "Id": att_id,
        "ConversationId": "conv-1",
        "AccountId": 7,
        "ObjectKey": f"k/{att_id}",
        "OriginalFilename": filename,
        "MimeType": "text/plain; charset=utf-8",
        "SizeBytes": 1234,
        "SizeBucket": "small",
        "Sha256": "deadbeef",
        "Kind": "text",
        "UploadStatus": "uploaded",
        "CreatedAt": None,
        "DeletedAt": None,
        "DeletePending": 0,
        "DeleteReason": None,
        "MetaJson": (json.dumps(meta) if meta_as_str else meta),
        "RootAttachmentId": root,
        "VersionNumber": version,
        "CreatedByRole": role,
        "SupersededAt": None,
    }


# ── A: _attach_assistant_attachments ────────────────────────────────────────
def test_a1_attach_only_assistant_messages():
    messages = [
        {"id": 100, "role": "assistant"},
        {"id": 101, "role": "user"},
        {"id": 102, "role": "assistant"},
    ]
    by_message = {100: [{"id": 10}], 102: [{"id": 12}], 101: [{"id": 99}]}
    app._attach_assistant_attachments(messages, by_message)
    assert messages[0]["_attachments"] == [{"id": 10}]
    # user 메시지는 by_message 에 키가 있어도 주입하지 않는다.
    assert "_attachments" not in messages[1]
    assert messages[2]["_attachments"] == [{"id": 12}]


def test_a2_attach_no_match_is_noop():
    messages = [{"id": 100, "role": "assistant"}]
    app._attach_assistant_attachments(messages, {})  # 빈 by_message
    assert "_attachments" not in messages[0]
    app._attach_assistant_attachments(messages, {999: [{"id": 1}]})  # 매칭 없음
    assert "_attachments" not in messages[0]


# ── L: _load_assistant_attachments_by_message ───────────────────────────────
def test_l1_group_by_message_id_dict_and_str_meta():
    rows = [
        _att_row(10, 100, version=2, filename="q.sql"),
        _att_row(11, 100, version=3, filename="q.sql", meta_as_str=True),  # str MetaJson
        _att_row(12, 200, version=2, filename="r.sql"),
    ]
    out = app._load_assistant_attachments_by_message(_DictConn(rows), "conv-1")
    assert set(out.keys()) == {100, 200}
    assert {a["id"] for a in out[100]} == {10, 11}
    assert [a["id"] for a in out[200]] == [12]
    # 직렬화 필드가 칩 렌더용으로 포함되는지.
    assert out[100][0]["is_assistant_generated"] is True
    assert out[100][0]["version_number"] in (2, 3)


def test_l2_skip_missing_or_zero_message_id():
    rows = [
        _att_row(10, 0),                       # message_id=0 → skip
        {**_att_row(11, 100), "MetaJson": {}},  # message_id 키 없음 → skip
        _att_row(12, 100),                      # 정상
    ]
    out = app._load_assistant_attachments_by_message(_DictConn(rows), "conv-1")
    assert list(out.keys()) == [100]
    assert [a["id"] for a in out[100]] == [12]


def test_l3_query_exception_returns_empty():
    out = app._load_assistant_attachments_by_message(_DictConn([], raise_on_execute=True), "conv-1")
    assert out == {}
    # 빈 conversation_id 도 빈 dict.
    assert app._load_assistant_attachments_by_message(_DictConn([]), "") == {}


# ── V: ② version_count 집계 + 직렬화 ────────────────────────────────────────
def test_v1_list_endpoint_has_version_count_aggregate():
    import inspect

    src = inspect.getsource(app.list_conversation_attachments)
    # 체인 길이 집계 SQL(루트 기준 GROUP BY) + 응답 키.
    assert "GROUP BY COALESCE(RootAttachmentId, Id)" in src
    assert '"version_count"' in src or "version_count" in src
    assert "ai_version_count" in src


def test_v2_serialize_keeps_version_fields():
    row = _att_row(10, 100, version=2, filename="q.sql", root=5)
    ser = app._serialize_attachment_for_api(dict(row))
    assert ser["version_number"] == 2
    assert ser["root_attachment_id"] == 5
    assert ser["created_by_role"] == "assistant"
    assert ser["is_assistant_generated"] is True


# ── S: ④ materialize step ───────────────────────────────────────────────────
def test_s1_ask_records_materialize_step():
    import inspect

    src = inspect.getsource(app.ask) if hasattr(app, "ask") else ""
    if not src:
        # ask 가 다른 이름이면 모듈 소스에서 확인.
        src = inspect.getsource(app)
    assert '"materialize_attachment"' in src
    assert "save_memory_step" in src
    assert '"attachment_edit"' in src


def test_s2_resolve_step_display_keeps_stored_work_reason():
    step = {
        "tool": "materialize_attachment",
        "work": "첨부 'q.sql'(v2)을(를) 새 버전으로 저장했습니다.",
        "reason": "수정한 첨부를 사용자에게 새 버전으로 제공합니다.",
    }
    out = app._resolve_step_display(step)
    assert out["work"] == step["work"]
    assert out["reason"] == step["reason"]
    assert out["work_source"] == "llm"
    assert out["reason_source"] == "llm"
