"""다중 SQL 첨부의 전달 수와 실제 저장 바이트 경계를 검사한다."""
import app
import pytest
from test_attachment_new import _Conn, _install_fake_storage, _new_block, _new_row
from test_attachment_versioning import _src_row


@pytest.fixture
def storage(monkeypatch):
    recorder = _install_fake_storage(monkeypatch)
    monkeypatch.setattr(app, "_check_attachment_size_caps", lambda *a, **k: (True, ""))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row() if i == 100 else _new_row())
    monkeypatch.setattr(app, "_update_assistant_message_content", lambda *a: True)
    return recorder


def apply(answer, **kwargs):
    return app._apply_assistant_attachment_blocks(
        _Conn({"new_id": 7001}), account={"id": 1}, conversation_id="conv-1",
        message_id=7, answer=answer, **kwargs)


def edit(body):
    return '```attachment-edit\n{"source_attachment_id":100}\n' + body + '\n```'


@pytest.mark.parametrize("count", [13, 23, 32])
def test_many_small_sql_files_are_all_delivered(storage, count):
    answer = "검토했습니다.\n" + "\n".join(_new_block(f"query{i}.sql", f"SELECT {i};") for i in range(count))
    result = apply(answer)
    assert len(result["created"]) == len(storage.calls) == count
    assert result["undelivered"] == 0
    assert "첨부 전달 실패" not in result["answer"]
    assert "SELECT" not in result["answer"]
    assert "검토했습니다." in result["answer"]


def test_count_limit_reports_each_missing_file(storage):
    result = apply("\n".join(_new_block(f"q{i}.sql") for i in range(33)))
    assert len(storage.calls) == 32 and result["undelivered"] == 1
    assert "신규 첨부 33" in result["answer"] and "32개" in result["answer"]
    assert "사유 미상" not in result["answer"]


def test_edit_and_new_share_exact_byte_limit(storage, monkeypatch):
    monkeypatch.setattr(app, "_ASSISTANT_ATTACHMENT_TOTAL_SIZE_CAP_BYTES", 10)
    # UTF-8 실제 본문 바이트: edit 6 + new 4 = 10.
    result = apply(edit("가나") + "\n" + _new_block("one.sql", "1234") + "\n" + _new_block("two.sql", "x"))
    assert len(storage.calls) == 2
    assert sum(len(call[1]) for call in storage.calls) == 10
    assert result["undelivered"] == 1 and "합계 용량" in result["answer"]


def test_real_five_mib_boundary(storage):
    content = "x" * (1024 * 1024)
    result = apply("\n".join(_new_block(f"q{i}.sql", content) for i in range(5)) + "\n" + _new_block("extra.sql", "x"))
    assert sum(len(call[1]) for call in storage.calls) == 5 * 1024 * 1024
    assert len(storage.calls) == 5 and result["undelivered"] == 1
    assert "합계 용량" in result["answer"]


def test_storage_failure_does_not_refund_budget(storage, monkeypatch):
    monkeypatch.setattr(app, "_ASSISTANT_ATTACHMENT_TOTAL_SIZE_CAP_BYTES", 4)
    storage.fail_put = True
    result = apply(_new_block("a.sql", "1234") + "\n" + _new_block("b.sql", "x"))
    assert len(storage.calls) == 0 and result["undelivered"] == 2
    assert "저장소 쓰기" in result["answer"] and "합계 용량" in result["answer"]


def test_insert_failure_does_not_refund_budget(storage, monkeypatch):
    monkeypatch.setattr(app, "_ASSISTANT_ATTACHMENT_TOTAL_SIZE_CAP_BYTES", 4)
    result = app._apply_assistant_attachment_blocks(
        _Conn({"new_id": 0}), account={"id": 1}, conversation_id="conv-1", message_id=7,
        answer=_new_block("a.sql", "1234") + "\n" + _new_block("b.sql", "x"))
    assert len(storage.calls) == 1 and result["undelivered"] == 2
    assert "첨부 기록" in result["answer"] and "합계 용량" in result["answer"]


def test_upload_permission_guard_precedes_storage(storage, monkeypatch):
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: False)
    result = apply(_new_block("q.sql"))
    assert not storage.calls and result["undelivered"] == 1
    assert "업로드 권한" in result["answer"]


def test_foreign_source_is_not_written(storage, monkeypatch):
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: _src_row(aid=2))
    result = apply(edit("SELECT 1;"))
    assert not storage.calls and result["undelivered"] == 1
    assert "당신이 갱신할 수 있는 첨부가 아닙니다" in result["answer"]


def test_failed_response_never_writes(storage):
    result = apply(_new_block("q.sql"), failed=True)
    assert not storage.calls and "SELECT" not in result["answer"]


def test_rejected_sources_still_consume_attempt_cap(storage, monkeypatch):
    reads = []
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: reads.append(i))
    result = apply("\n".join(edit("SELECT 1;") for _ in range(1000)))
    assert len(reads) == 32 and not storage.calls
    assert result["undelivered"] == 1000
    assert "사유 미상" not in result["answer"]


def test_failed_edits_and_new_share_attempt_count(storage, monkeypatch):
    monkeypatch.setattr(app, "_ASSISTANT_EDIT_COUNT_CAP", 2)
    monkeypatch.setattr(app, "_load_attachment_row", lambda c, i: None)
    result = apply(edit("a") + "\n" + edit("b") + "\n" + _new_block("c.sql"))
    assert not storage.calls and result["undelivered"] == 3
    assert "2개" in result["answer"]


@pytest.mark.parametrize("count", [13, 23])
def test_many_existing_sql_edits_are_all_delivered(storage, count):
    result = apply("검토했습니다.\n" + "\n".join(edit(f"SELECT {i};") for i in range(count)))
    assert len(result["edited"]) == len(storage.calls) == count
    assert result["undelivered"] == 0
    assert "SELECT" not in result["answer"] and "첨부 전달 실패" not in result["answer"]


@pytest.mark.parametrize("failed", [False, True])
def test_missing_message_id_never_writes_or_exposes_file_body(storage, monkeypatch, failed):
    writes = []
    monkeypatch.setattr(app, "_update_assistant_message_content", lambda *a: writes.append(a))
    result = app._apply_assistant_attachment_blocks(
        _Conn({"new_id": 7001}), account={"id": 1}, conversation_id="conv-1", message_id=0,
        answer="실행 결과\n" + _new_block("q.sql", "SELECT SECRET_FILE_BODY;"), failed=failed)
    assert not storage.calls and not writes
    assert "SECRET_FILE_BODY" not in result["answer"]
    assert "```attachment" not in result["answer"]
    assert result["answer_persisted"] is False
    assert ("답변 저장을 확인하지 못해" in result["answer"]) is (not failed)
