"""TASK-0277 — 첨부 메타 MySQL→PG agent_runtime dual-write + read cutover 회귀 테스트.

라이브 PG 라운드트립이 별도 게이트(interval cast·jsonb·datetime 정합은 라이브로만 최종 확인)이고,
본 테스트는 fake-cursor 단위로 잡히는 면 — **타입 정합 계약·게이트 라우팅·SQL 불변식·마이그레이션 구조** —
를 회귀 차단한다.

  A  attachment_pg_mirror 순수함수: 타입 정규화(datetime→UTC ISO, JSON→str, NULL) + SQL 계약(::text/
     AT TIME ZONE 'UTC' 정합, ON CONFLICT) + 플래그.
  B  app.py read-gate 라우팅: ATTACHMENTS_READ_BACKEND=postgres 면 PG 헬퍼 호출, 아니면 MySQL.
  C  dual-write 게이트: ATTACHMENTS_DUAL_WRITE off 면 PG 미접촉(no-op).
  D  attachment_backfill 매핑/SQL 계약(id 보존·ON CONFLICT DO NOTHING).
  E  alembic 0008 마이그레이션 구조(revision 체인·id 비-IDENTITY·GRANT·version-chain UNIQUE).
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import os
import sys
import types
from pathlib import Path

import app


_SRC = Path(__file__).resolve().parent.parent / "src"
_REPO = Path(__file__).resolve().parents[3]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 실제 mirror 모듈을 파일 경로로 직접 로드(테스트 env 엔 web 패키지 없음).
apm = _load(_SRC / "modules" / "attachment_pg_mirror.py", "_t0277_apm")


def _install_fake_apm(monkeypatch, **overrides):
    """app.py 의 `from web.modules import attachment_pg_mirror` 가 잡도록 fake 체인 등록."""
    fake = types.ModuleType("web.modules.attachment_pg_mirror")
    # 기본은 실제 모듈의 플래그 함수 + no-op, override 로 개별 교체.
    fake.dual_write_enabled = apm.dual_write_enabled
    fake.read_pg_enabled = apm.read_pg_enabled
    fake.mirror_attachments = lambda *a, **k: None
    fake.mirror_conversation_attachments = lambda *a, **k: None
    fake.mirror_derived_messages = lambda *a, **k: None
    for k, v in overrides.items():
        setattr(fake, k, v)
    web_pkg = sys.modules.get("web") or types.ModuleType("web")
    web_mods = sys.modules.get("web.modules") or types.ModuleType("web.modules")
    setattr(web_mods, "attachment_pg_mirror", fake)
    setattr(web_pkg, "modules", web_mods)
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.modules", web_mods)
    monkeypatch.setitem(sys.modules, "web.modules.attachment_pg_mirror", fake)
    return fake


# ── A: mirror 순수함수 ────────────────────────────────────────────────────────
def test_a1_dt_to_pg_naive_utc_isoformat():
    naive = _dt.datetime(2026, 6, 15, 12, 34, 56, 123456)
    out = apm._dt_to_pg(naive)
    assert out == "2026-06-15T12:34:56.123456+00:00"  # UTC 명시(naive→aware)
    assert apm._dt_to_pg(None) is None
    aware = _dt.datetime(2026, 6, 15, 12, 0, 0, tzinfo=_dt.timezone.utc)
    assert apm._dt_to_pg(aware) == "2026-06-15T12:00:00+00:00"


def test_a2_json_to_pg_str_and_dict_and_null():
    assert apm._json_to_pg(None) is None
    # dict → JSON 문자열
    assert apm._json_to_pg({"k": "v"}) == '{"k": "v"}'
    # 이미 문자열이면 그대로(공백 trim)
    assert apm._json_to_pg('{"a":1}') == '{"a":1}'
    # 빈 문자열 → None(빈 jsonb 회피)
    assert apm._json_to_pg("   ") is None
    # bytes → 디코드
    assert apm._json_to_pg(b'{"b":2}') == '{"b":2}'


def test_a3_attach_row_to_params_full_mapping():
    row = {
        "Id": 42, "ConversationId": "conv-1", "AccountId": 7, "ObjectKey": "k/o",
        "OriginalFilename": "f.csv", "FilenameHmac": "h" * 64, "MimeType": "text/csv",
        "SizeBytes": 1234, "SizeBucket": "<1MB", "Sha256": "s" * 64, "Kind": "csv",
        "UploadStatus": "ingested", "AttachmentDerivedMessages": None,
        "CreatedAt": _dt.datetime(2026, 6, 15, 1, 2, 3), "DeletedAt": None,
        "DeletePending": 0, "DeleteReason": None,
        "MetaJson": {"sandbox_schema_name": "agent_attachment_x"},
        "RootAttachmentId": None, "VersionNumber": 1, "CreatedByRole": "user",
        "SupersededAt": None,
    }
    p = apm._attach_row_to_params(row)
    assert p["id"] == 42 and isinstance(p["id"], int)
    assert p["root_attachment_id"] is None          # NULL root 보존(version-chain NULLS DISTINCT)
    assert p["deleted_at"] is None and p["superseded_at"] is None
    assert p["created_at"] == "2026-06-15T01:02:03+00:00"
    assert p["meta_json"] == '{"sandbox_schema_name": "agent_attachment_x"}'  # dict→str
    assert p["delete_pending"] == 0 and p["version_number"] == 1
    # root_attachment_id 가 있으면 int 보존
    row2 = dict(row, RootAttachmentId=42, VersionNumber=2)
    assert apm._attach_row_to_params(row2)["root_attachment_id"] == 42


def test_a4_sql_type_parity_contract():
    sel = apm._PG_ATTACH_SELECT
    # jsonb 컬럼은 ::text 로(=MySQL connector 의 JSON 문자열 반환 정합)
    assert 'meta_json::text AS "MetaJson"' in sel
    assert 'attachment_derived_messages::text AS "AttachmentDerivedMessages"' in sel
    # timestamptz 는 naive UTC 로(=MySQL DATETIME naive 정합)
    assert "(created_at AT TIME ZONE 'UTC') AS \"CreatedAt\"" in sel
    assert "(deleted_at AT TIME ZONE 'UTC') AS \"DeletedAt\"" in sel
    assert "(superseded_at AT TIME ZONE 'UTC') AS \"SupersededAt\"" in sel
    # upsert: id 충돌 시 UPDATE 하되 created_at 은 갱신하지 않음(최초 생성시각 보존)
    up = apm._PG_UPSERT_ATTACH
    assert "ON CONFLICT (id) DO UPDATE SET" in up
    assert "created_at = EXCLUDED.created_at" not in up
    # 바인딩 캐스트
    assert "%(meta_json)s::jsonb" in up and "%(created_at)s::timestamptz" in up


def test_a5_flag_helpers(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE", raising=False)
    monkeypatch.delenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", raising=False)
    assert apm.dual_write_enabled() is False
    assert apm.read_pg_enabled() is False
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE", "1")
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "postgres")
    assert apm.dual_write_enabled() is True
    assert apm.read_pg_enabled() is True
    # 임의 값은 mysql(기본) 유지
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "mysql")
    assert apm.read_pg_enabled() is False


# ── B: app.py read-gate 라우팅 ───────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows=None):
        self.cursors = []
        self._rows = rows or []

    def cursor(self, dictionary=False):
        c = _FakeCursor(self._rows)
        self.cursors.append(c)
        return c


def test_b1_load_attachment_row_routes_to_pg(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "postgres")
    called = {}

    def fake_pg_load(aid):
        called["id"] = aid
        return {"Id": aid, "ConversationId": "c", "Kind": "csv"}

    _install_fake_apm(monkeypatch, pg_load_attachment_row=fake_pg_load)
    conn = _FakeConn()
    row = app._load_attachment_row(conn, 99)
    assert called["id"] == 99
    assert row["Id"] == 99
    # PG 경로면 MySQL 커서를 만들지 않는다.
    assert conn.cursors == []


def test_b1_load_attachment_row_mysql_when_disabled(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "mysql")
    _install_fake_apm(monkeypatch, pg_load_attachment_row=lambda aid: {"Id": -1})
    conn = _FakeConn(rows=[{"Id": 5, "ConversationId": "c"}])
    row = app._load_attachment_row(conn, 5)
    assert row["Id"] == 5            # MySQL fake cursor 결과
    assert len(conn.cursors) == 1    # MySQL 커서 사용


def test_b2_size_caps_max_of_mysql_and_pg(monkeypatch):
    # REV-20260615-0279 MAJOR-1: quota 무결성 — MySQL(권위) 계산 후 PG 와 max() 를 취한다.
    # PG 가 더 크면 PG 값으로 cap 이 enforce 되어야 한다(미러 누락분 과소계상 → cap 우회 방지).
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "postgres")
    monkeypatch.setattr(app, "_attachment_size_caps", lambda: (1000, 100, 10000))
    seen = []

    def fake_sum(*, conversation_id=None, account_id=None):
        seen.append((conversation_id, account_id))
        return 95 if conversation_id is not None else 0  # conv=95(PG), account=0

    _install_fake_apm(monkeypatch, pg_sum_size_bytes=fake_sum)
    conn = _FakeConn(rows=[(0,)])  # MySQL 누적 0
    ok, reason = app._check_attachment_size_caps(
        conn, account_id=7, conversation_id="conv-1", new_size_bytes=10)
    # MySQL 만이면 0+10=10 ≤ 100 통과지만, PG conv=95 → max=95, 95+10=105 > 100 → 거부.
    assert ok is False and "대화당" in reason
    assert ("conv-1", None) in seen and (None, 7) in seen   # 양 scope PG 조회
    assert len(conn.cursors) >= 1                            # MySQL(권위)도 계산


# ── C: dual-write 게이트 ──────────────────────────────────────────────────────
def test_c1_mirror_noop_when_dual_write_off(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE", raising=False)

    class _Guard:
        def cursor(self, *a, **k):
            raise AssertionError("dual-write off 인데 MySQL 재조회가 일어남")

    # off 면 즉시 return — mysql_conn 미접촉.
    apm.mirror_attachments(_Guard(), [1, 2, 3])
    apm.mirror_derived_messages(_Guard(), [1])
    apm.mirror_conversation_attachments(_Guard(), "conv-1")


def test_c2_mirror_calls_pg_upsert_when_on(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE", "1")
    row = {
        "Id": 11, "ConversationId": "c", "AccountId": 1, "ObjectKey": "k",
        "OriginalFilename": "f", "FilenameHmac": "h", "MimeType": "text/csv",
        "SizeBytes": 1, "SizeBucket": "<1MB", "Sha256": "s", "Kind": "csv",
        "UploadStatus": "uploaded", "AttachmentDerivedMessages": None,
        "CreatedAt": _dt.datetime(2026, 6, 15), "DeletedAt": None, "DeletePending": 0,
        "DeleteReason": None, "MetaJson": None, "RootAttachmentId": None,
        "VersionNumber": 1, "CreatedByRole": "user", "SupersededAt": None,
    }

    class _MyCur:
        def __init__(self): self.q = None
        def execute(self, sql, params=None): self.q = sql
        def fetchall(self): return [row]
        def close(self): pass

    class _MyConn:
        def cursor(self, dictionary=False): return _MyCur()

    pg_exec = []

    class _PgCur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): pg_exec.append((sql, params))

    class _PgConn:
        def cursor(self): return _PgCur()
        def commit(self): pass
        def close(self): pass

    monkeypatch.setattr(apm, "_pg", lambda: _PgConn())
    apm.mirror_attachments(_MyConn(), [11])
    assert len(pg_exec) == 1
    assert "INSERT INTO agent_runtime.core_attachments" in pg_exec[0][0]
    assert pg_exec[0][1]["id"] == 11


# ── D: backfill 매핑/SQL ─────────────────────────────────────────────────────
bf = _load(
    _REPO / "unit" / "feature-0002-agent-core" / "src" / "scripts" / "attachment_backfill.py",
    "_t0277_backfill",
)


def test_d1_backfill_param_mapping_and_id_preserved():
    row = {
        "Id": 7, "ConversationId": "c", "AccountId": 2, "ObjectKey": "k",
        "OriginalFilename": "f", "FilenameHmac": "h", "MimeType": "text/csv",
        "SizeBytes": 9, "SizeBucket": "<1MB", "Sha256": "s", "Kind": "csv",
        "UploadStatus": "uploaded", "AttachmentDerivedMessages": None,
        "CreatedAt": _dt.datetime(2026, 6, 15), "DeletedAt": None, "DeletePending": 0,
        "DeleteReason": None, "MetaJson": None, "RootAttachmentId": None,
        "VersionNumber": 1, "CreatedByRole": "user", "SupersededAt": None,
    }
    p = bf._attach_params(row)
    assert p["id"] == 7  # MySQL Id 보존(GENERATED ALWAYS 미사용)


def test_d2_backfill_idempotent_do_nothing():
    """backfill 은 dual-write 가 이미 넣은 행을 덮지 않는다.

    REQ-20260908-attach-folder-tree (§18.8 backend [P1]): `core_attachments` 만 **한 컬럼**
    예외를 갖는다 — `relative_path` 가 비어 있을 때만 채운다. 그 컬럼이 생기기 전에 들어온
    행은 순수 DO NOTHING 이면 재실행으로도 영영 NULL 로 남고, read backend 를 PG 로 돌리는
    순간 cutover 이전 폴더가 통째로 평면 목록이 된다. `COALESCE` 라 이미 값이 있는 행은
    건드리지 않으므로 「덮지 않는다」는 성질 자체는 유지된다.
    """
    # 다른 컬럼은 여전히 보존 — UPDATE 절이 relative_path **하나만** 건드린다.
    assert "ON CONFLICT (id) DO UPDATE SET" in bf._PG_UPSERT_ATTACH
    _set_clause = bf._PG_UPSERT_ATTACH.split("DO UPDATE SET", 1)[1]
    assert _set_clause.count("=") == 1, f"경로 외 컬럼도 덮어쓴다: {_set_clause}"
    assert "relative_path = COALESCE(" in _set_clause
    # 부속 테이블은 종전 그대로 순수 DO NOTHING.
    assert "ON CONFLICT (id) DO NOTHING" in bf._PG_UPSERT_DERIVED
    assert set(bf._TABLE_ORDER[:1]) == {"core_attachments"}  # FK 의존성: 첨부 선행


# ── E: alembic 마이그레이션 구조 ─────────────────────────────────────────────
# 마이그레이션 모듈은 `from alembic import op`(런타임 전용)를 import 하므로 텍스트로 정적 검증한다.
_MIG_TEXT = (
    _REPO / "unit" / "feature-0002-agent-core" / "alembic" / "versions"
    / "20260615_0008_core_attachments.py"
).read_text(encoding="utf-8")


def test_e1_revision_chain():
    assert 'revision: str = "0008_core_attachments"' in _MIG_TEXT
    assert 'down_revision: Union[str, None] = "0007_core_conv_archived"' in _MIG_TEXT


def test_e2_schema_invariants():
    # docstring(설명) 말고 UPGRADE_SQL 본문만 검증(docstring 에 "GENERATED ALWAYS 금지" 설명이 있음).
    up = _MIG_TEXT.split('UPGRADE_SQL = r"""', 1)[1].split('"""', 1)[0]
    # 4 테이블 CREATE
    for t in ("core_attachments", "core_attachment_sandbox_schemas",
              "core_attachment_derived_messages", "core_attachment_provider_files"):
        assert f"CREATE TABLE IF NOT EXISTS agent_runtime.{t}" in up
    # id 는 IDENTITY 가 아니라 MySQL Id 보존용 plain bigint PRIMARY KEY
    assert "id                          bigint        PRIMARY KEY" in up
    assert "GENERATED ALWAYS AS IDENTITY" not in up
    # version-chain UNIQUE (NULLS DISTINCT 기본 = MySQL NULL 중복허용 정합)
    assert "uq_core_attachments_version_chain" in up
    assert "UNIQUE (root_attachment_id, version_number)" in up
    # 신규 테이블 명시 GRANT(superuser 적용 trap — ALL TABLES 스냅샷 미커버)
    assert up.count("TO agent_kb_rw;") >= 4
    assert "TO agent_kb_ro;" in up
    # derived.message_id 는 FK 아님(PG messages id-space 불일치)
    assert "fk_core_att_derived_att" in up           # attachment FK 는 존재
    assert "REFERENCES agent_runtime.messages" not in up  # message_id FK 부재


# ── E3/E4: 0009 conversation FK 제거(라이브 backfill orphan 대응) ─────────────
_MIG09_TEXT = (
    _REPO / "unit" / "feature-0002-agent-core" / "alembic" / "versions"
    / "20260615_0009_drop_attach_conv_fk.py"
).read_text(encoding="utf-8")
_BOOT_TEXT = (
    _REPO / "unit" / "feature-0002-agent-core" / "src" / "scripts" / "agent_runtime_schema.sql"
).read_text(encoding="utf-8")


def test_e3_drop_conv_fk_migration():
    # 0009 가 core_attachments / sandbox_schemas 의 conversation FK 를 제거(orphan 첨부 이전 허용)
    assert 'revision: str = "0009_drop_attach_conv_fk"' in _MIG09_TEXT
    assert 'down_revision: Union[str, None] = "0008_core_attachments"' in _MIG09_TEXT
    up = _MIG09_TEXT.split('UPGRADE_SQL = r"""', 1)[1].split('"""', 1)[0]
    assert "DROP CONSTRAINT IF EXISTS fk_core_attachments_conv" in up
    assert "DROP CONSTRAINT IF EXISTS fk_core_att_sandbox_conv" in up


def test_e4_bootstrap_drops_conv_fk_keeps_subtable_fk():
    # fresh deploy(bootstrap) 도 conversation FK 미설정 — orphan 정합
    assert "CONSTRAINT fk_core_attachments_conv" not in _BOOT_TEXT
    assert "CONSTRAINT fk_core_att_sandbox_conv" not in _BOOT_TEXT
    # 단, 서브테이블 attachment_id FK(id 보존으로 안정)는 유지
    assert "fk_core_att_derived_att" in _BOOT_TEXT
    assert "fk_core_att_provider_att" in _BOOT_TEXT
    # conversation_id 컬럼·인덱스는 유지(JOIN)
    assert "ix_core_attachments_conv" in _BOOT_TEXT
