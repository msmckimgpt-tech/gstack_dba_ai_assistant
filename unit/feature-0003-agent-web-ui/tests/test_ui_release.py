"""A public reload signal requires a completed deployment matching this replica."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import app
import ui_release


STAMP = "123456abcdef"
REVISION = "abcdef12"
COMPLETE = {"status": "complete", "release": REVISION,
            "asset_stamp": STAMP, "generation": 1234}
PENDING = {"status": "pending"}


@pytest.fixture
def release_files(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / ".asset-stamp").write_text(STAMP + "\n")
    path = tmp_path / "current.json"
    path.write_text(json.dumps(COMPLETE))
    return path, static


def test_completed_release_exposes_only_public_identity(release_files):
    path, static = release_files
    path.write_text(json.dumps({**COMPLETE, "internal_path": "/private/deploy",
                                "operator_note": "do not expose"}))
    assert ui_release.read_release(path, static, REVISION) == COMPLETE


@pytest.mark.parametrize("body", [b"", b"{", b"\xff", b"null", b"[]", b"true", b'"complete"',
                                  b"{}", b'{"status":"pending"}', b" " * 4097])
def test_missing_or_malformed_completion_is_pending(release_files, body):
    path, static = release_files
    path.write_bytes(body)
    assert ui_release.read_release(path, static, REVISION) == PENDING


def test_oversized_otherwise_valid_manifest_is_not_accepted(release_files):
    path, static = release_files
    path.write_text(json.dumps({**COMPLETE, "padding": "x" * 5000}))
    assert ui_release.read_release(path, static, REVISION) == PENDING


@pytest.mark.parametrize("field,value", [
    ("status", "pending"), ("status", "failed"), ("status", True),
    ("asset_stamp", None), ("asset_stamp", "dev"), ("asset_stamp", "ABCDEF123456"),
    ("asset_stamp", "123456abcdef0"), ("asset_stamp", [STAMP]),
    ("release", None), ("release", "unknown"), ("release", "abc123"),
    ("release", "a" * 41), ("release", "ABCDEF12"),
    ("generation", None), ("generation", 0), ("generation", -1),
    ("generation", True), ("generation", 1.0), ("generation", "1234"),
    ("generation", 2**53),
])
def test_invalid_manifest_fields_never_authorize_reload(release_files, field, value):
    path, static = release_files
    path.write_text(json.dumps({**COMPLETE, field: value}))
    assert ui_release.read_release(path, static, REVISION) == PENDING


@pytest.mark.parametrize("field", COMPLETE)
def test_incomplete_manifest_is_pending(release_files, field):
    path, static = release_files
    value = dict(COMPLETE)
    del value[field]
    path.write_text(json.dumps(value))
    assert ui_release.read_release(path, static, REVISION) == PENDING


@pytest.mark.parametrize("stamp,commit", [("000000000000", REVISION), (STAMP, "00000000"),
                                           (STAMP, "unknown"), ("dev", REVISION)])
def test_mixed_replica_identity_cannot_emit_completed_release(release_files, stamp, commit):
    path, static = release_files
    (static / ".asset-stamp").write_text(stamp)
    assert ui_release.read_release(path, static, commit) == PENDING


@pytest.mark.parametrize("missing", ["manifest", "stamp"])
def test_missing_files_are_pending(release_files, missing):
    path, static = release_files
    (path if missing == "manifest" else static / ".asset-stamp").unlink()
    assert ui_release.read_release(path, static, REVISION) == PENDING


def test_manifest_read_error_is_pending(release_files, monkeypatch):
    path, static = release_files
    original = Path.open

    def deny(self, *args, **kwargs):
        if self == path:
            raise PermissionError("private deployment path")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny)
    assert ui_release.read_release(path, static, REVISION) == PENDING


@pytest.mark.parametrize("status", ["complete", "pending"])
@pytest.mark.parametrize("cookie", [False, True])
def test_public_endpoint_is_uncached_and_never_accesses_auth_or_db(
        release_files, monkeypatch, client, status, cookie):
    path, static = release_files
    path.write_text(json.dumps({**COMPLETE, "status": status}))
    monkeypatch.setattr(ui_release, "RELEASE_PATH", path)
    monkeypatch.setattr(app, "STATIC_DIR", static)
    monkeypatch.setenv("GIT_COMMIT", REVISION)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Public deployment metadata must not touch auth or DB")

    monkeypatch.setattr(app, "_connect_memory", forbidden)
    for dependency in (app.get_conn, app.get_current_account, app.get_optional_account):
        app.app.dependency_overrides[dependency] = forbidden
    if cookie:
        client.cookies.set("mysql_ai_session", "test-cookie-not-a-session")
    response = client.get("/api/ui-release")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == (COMPLETE if status == "complete" else PENDING)
    assert calls == []
