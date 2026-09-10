"""ITEM-03 (DQA-03 · DQA-09 설명 길이, Critical §12.3) — 비공개 Product 원자 생성 · 초기 접근
권한 · Description 길이 검증의 불변식 고정.

근거: `docs/improvements/dqa-field-audit-20260910/EVIDENCE.md` E-03a~e · E-09b.
설계: 같은 초기의 `DESIGN.md` `### ITEM-03` (사용자 승인 2026-09-10).

무엇을 잠그는가 (AC-03-1~5):

  A1  비공개(`default_role_access=false`) 생성이 **생성자 계정에 allow override 1행**을 같은
      트랜잭션에서 넣는다. 역할 backfill 은 돌지 않는다.
  A2  그 결과 생성자의 effective 권한에 `product.access.<key>` 가 서고 작업 화면 제품 목록에
      그 제품이 포함된다 (AC-03-1 의 관측 대체 — 단건 GET 엔드포인트가 없다).
  A3  grant INSERT 를 강제 실패시키면 **commit 0 · rollback 1** — 제품·권한·감사행이 남지
      않는다. 생성자의 기존 override 는 손대지 않는다(DELETE 0건).
  A4  `_grant_product_access_to_account` 는 **INSERT 1행만** 한다 — `_set_account_overrides`
      의 «DELETE … WHERE AccountId 후 재삽입» 을 상속하지 않는다(상속하면 생성자의 기존
      override 가 전멸한다).
  A5  감사행이 **생성과 같은 commit** 안에 있다 (E-03d: 종전 2 commit 회귀 방지).
  A6  공개(`default_role_access=true`) 생성은 역할 backfill 만 — 계정 override INSERT 0.
  A7  `product.create` 무권한은 403 유지, self-scope 가드 2곳은 **무변경**(관리자 우회 없음).
  A8  Description/Name 길이: 경계 양측(255/256 한글) · 이모지 · 따옴표·`--`·`;` 특수문자.
      응답 본문에 `Data too long` 및 SQL 조각 **0건**.
  A9  PATCH 도 같은 상한·같은 응답 형식. `WebProductDatabases.Description` 도 동일.
  A10 길이 상수 ↔ DDL ↔ 프론트 3자 동치 (수기 표류 차단).
  A11 복구 스크립트: dry-run 은 쓰기 0 · 자동 계정 선택 없음 · deny override 를 뒤집지 않음 ·
      복구 후 재진단 0건.

실행:
    python3 -m pytest unit/feature-0003-agent-web-ui/tests/test_product_create_atomic.py -q
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import app
from routers import admin_products

_SRC = Path(__file__).resolve().parents[1] / "src"
_STATIC = _SRC / "static"
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_REPAIR_SCRIPT = _SCRIPTS / "product_access_repair.py"

NEW_PRODUCT_ID = 501
NEW_PERMISSION_ID = 901
ACTOR_ID = 7


# ── 테스트 더블 ───────────────────────────────────────────────────────────────
_WRITE_PREFIXES = ("insert", "update", "delete", "replace")


class _Cursor:
    """SQL 접두로 응답을 분기하는 stub. `store['executed']` 에 정규화 SQL 을 적재한다.

    ⭐ **autocommit 감시**: 쓰기 문장이 `conn.autocommit is True` 인 채로 실행되면 raise 한다.
    이게 없으면 stub 은 「`.commit()` 을 몇 번 불렀나」만 세므로, 정본에서
    `conn.autocommit = False` 한 줄을 지워도 **전건 통과**한다 — 실제 MySQL 이라면 각 INSERT 가
    즉시 확정되고 이후 `.rollback()` 이 무효라 ITEM-03 이 없애려던 고립(E-03b)이 그대로
    재현되는데도. 적대 검증(qa P1)이 결손 주입으로 그 맹점을 실증해 여기서 닫는다.
    `dictionary=True` 커서도 지원한다 — 미지원 상태로 두면 `is_default` 경로를 덮으려는 다음
    사람이 test-double 인공물(TypeError)에 걸린다(같은 지적).
    """

    def __init__(self, store, conn=None, dictionary=False):
        self._store = store
        self._conn = conn
        self._dictionary = bool(dictionary)
        self._rows: list = []
        self.lastrowid = 0
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        sl = s.lower()
        if (
            sl.split(" ", 1)[0] in _WRITE_PREFIXES
            and self._conn is not None
            and getattr(self._conn, "autocommit", True)
        ):
            raise RuntimeError(
                "autocommit=True 상태에서 쓰기 문장이 실행됐다 — 트랜잭션이 없으므로 "
                f"rollback 이 무효다: {s[:80]}"
            )
        self._store["executed"].append(s)
        self._store["params"].append(params)
        self._rows = []
        self.lastrowid = 0
        self.rowcount = 0
        for fragment, exc in self._store.get("fail_on", ()):
            if fragment in sl:
                raise exc
        if sl.startswith("select count(*) from webproducts where productkey"):
            self._rows = [(int(self._store.get("existing_key_count", 0)),)]
        elif sl.startswith("insert into webproducts"):
            self.lastrowid = int(self._store.get("product_lastrowid", NEW_PRODUCT_ID))
            self.rowcount = 1
        elif sl.startswith("insert into webpermissions"):
            self.lastrowid = int(self._store.get("new_permission_id", NEW_PERMISSION_ID))
            self.rowcount = 1
        elif sl.startswith("insert ignore into webrolepermissions"):
            self.rowcount = int(self._store.get("role_grant_rows", 3))
        elif sl.startswith("insert into webaccountpermissionoverrides"):
            self.rowcount = int(self._store.get("override_insert_rows", 1))
        elif sl.startswith("update webproducts"):
            self.rowcount = 1
        elif sl.startswith("select"):
            self._rows = list(self._store.get("select_rows", []))

    def _shape(self, row):
        if not self._dictionary or isinstance(row, dict):
            return row
        # dictionary=True 소비처는 컬럼명으로 읽는다. store 가 dict 를 주지 않았다면
        # 위치 기반 튜플을 그대로 주는 대신 명시적으로 알려 준다(조용한 TypeError 금지).
        raise RuntimeError(
            "dictionary=True 커서인데 store 가 dict row 를 주지 않았다 — "
            "`select_rows` 에 dict 를 넣어라"
        )

    def fetchone(self):
        return self._shape(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [self._shape(r) for r in self._rows]

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True
        self.closed = False

    def cursor(self, *a, **kw):
        return _Cursor(self._store, conn=self, dictionary=bool(kw.get("dictionary")))

    def commit(self):
        self._store["executed"].append("COMMIT")

    def rollback(self):
        self._store["executed"].append("ROLLBACK")

    def close(self):
        self.closed = True


class _Req:
    def __init__(self, body=None):
        self._body = body or {}

    async def json(self):
        return self._body


def _actor(permissions=None):
    return {
        "id": ACTOR_ID,
        "username": "opsuser",
        "role_id": 2,
        "permissions": permissions if permissions is not None else {"product.create": True},
    }


def _store(**overrides):
    base = {"executed": [], "params": [], "fail_on": ()}
    base.update(overrides)
    return base


def _patch(monkeypatch, conn, *, actor=None, has_permission=True):
    the_actor = actor if actor is not None else _actor()
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: (the_actor, None))
    # has_permission 은 bool 또는 (actor, perm) -> bool 콜러블. 콜러블이면 권한 축을
    # 개별로 흉내낼 수 있다(두 축 독립 검증용).
    _hp = has_permission if callable(has_permission) else (lambda a, perm: has_permission)
    monkeypatch.setattr(app, "_account_has_permission", _hp)
    monkeypatch.setattr(app, "invalidate_permission_catalog_cache", lambda: None)
    monkeypatch.setattr(
        app, "_build_actor_from_request",
        lambda req, acct, actor_type="account": {"actor_type": actor_type, "account_id": ACTOR_ID},
    )
    # 감사 dispatcher 만 대체한다 — `build_audit_change_json` 은 실제로 돌려서 action code
    # (`admin.product.create`) 가 builder 화이트리스트에 있는지도 함께 검증한다.
    audit_calls = []

    def _record(conn_, *, actor, action, resource_type, resource_id, change_json,
                masked_fields=None, target_account_id=None):
        conn_.cursor().execute(
            "INSERT INTO WebAuditEvents (ActionCode, ResourceType, ResourceId) VALUES (%s,%s,%s)",
            (action, resource_type, resource_id),
        )
        audit_calls.append({"action": action, "resource_id": resource_id, "change": change_json})

    monkeypatch.setattr(app, "record_audit_event", _record)
    return audit_calls


def _create(body):
    return asyncio.run(admin_products.admin_create_product(_Req(body)))


def _payload(response):
    return json.loads(bytes(response.body).decode("utf-8"))


def _sql_of(store, fragment):
    return [s for s in store["executed"] if fragment in s.lower()]


# ── A1 · A5 · A6: 원자 생성 + 초기 grant ─────────────────────────────────────
def test_a1_private_create_grants_creator_in_same_transaction(monkeypatch):
    store = _store()
    conn = _Conn(store)
    audit = _patch(monkeypatch, conn)

    resp = _create({"product_key": "PRIV1", "name": "비공개 제품",
                    "description": "사내 전용", "default_role_access": False})

    assert resp.status_code == 200, _payload(resp)
    body = _payload(resp)
    assert body["ok"] is True and body["product_id"] == NEW_PRODUCT_ID
    assert body["initial_access_account_id"] == ACTOR_ID

    # 계정 override allow 1행 — 대상 계정·권한·값 모두 고정.
    grants = [
        p for s, p in zip(store["executed"], store["params"])
        if s.lower().startswith("insert into webaccountpermissionoverrides")
    ]
    assert len(grants) == 1, store["executed"]
    assert grants[0] == (ACTOR_ID, NEW_PERMISSION_ID, app.OVERRIDE_ALLOW)

    # 비공개는 역할 backfill 을 돌리지 않는다(그게 「비공개」의 정의다).
    assert _sql_of(store, "insert ignore into webrolepermissions") == []

    # A5: 제품·권한·grant·감사가 **한 번의 commit** 안에 있다 (E-03d 2-commit 회귀 방지).
    assert store["executed"].count("COMMIT") == 1
    assert "ROLLBACK" not in store["executed"]
    order = store["executed"]
    assert order.index("COMMIT") == len(order) - 1, order
    assert len(_sql_of(store, "insert into webauditevents")) == 1
    assert [c["action"] for c in audit] == ["admin.product.create"]
    assert audit[0]["change"]["created_product"]["default_role_access"] is False


def test_a6_public_create_backfills_roles_without_account_override(monkeypatch):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)

    resp = _create({"product_key": "PUB1", "name": "공개 제품", "default_role_access": True})

    assert resp.status_code == 200
    assert "initial_access_account_id" not in _payload(resp)
    assert len(_sql_of(store, "insert ignore into webrolepermissions")) == 1
    # 공개 제품에 계정 override 를 덧붙이면 이후 «역할 단위 회수» 가 무력화된다(최소 권한).
    assert _sql_of(store, "insert into webaccountpermissionoverrides") == []
    assert store["executed"].count("COMMIT") == 1


@pytest.mark.parametrize("raw", ["false", "False", "0", 0, 1, "true", None, [], {}])
def test_a6b_non_boolean_default_role_access_is_rejected(monkeypatch, raw):
    """⭐ 이 boolean 하나가 「전 역할 공개」와 「생성자 1인」을 가른다.

    느슨한 `bool()` 은 `"false"` 를 참으로 읽어 **비공개 의도를 전 역할 공개로 뒤집는다**.
    ITEM-03 이 이 값의 위험도를 올렸으므로 non-boolean 은 400 으로 거부한다(쓰기 0).
    """
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "DRA1", "name": "범위", "default_role_access": raw})
    assert resp.status_code == 400, _payload(resp)
    body = _payload(resp)
    assert body["field"] == "default_role_access"
    assert store["executed"] == [], "거부 응답인데 쓰기가 발행됐다"


@pytest.mark.parametrize("raw,expect_role_backfill", [(True, True), (False, False)])
def test_a6c_boolean_default_role_access_accepted(monkeypatch, raw, expect_role_backfill):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "DRA2", "name": "범위", "default_role_access": raw})
    assert resp.status_code == 200, _payload(resp)
    got = bool(_sql_of(store, "insert ignore into webrolepermissions"))
    assert got is expect_role_backfill


def test_a6d_absent_default_role_access_stays_public(monkeypatch):
    """키가 없으면 종전 호환대로 공개(True) — 기존 클라이언트가 깨지지 않는다."""
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "DRA3", "name": "범위"})
    assert resp.status_code == 200
    assert len(_sql_of(store, "insert ignore into webrolepermissions")) == 1
    assert _sql_of(store, "insert into webaccountpermissionoverrides") == []


# ── A2: 생성 직후 생성자가 그 제품을 본다 (AC-03-1) ────────────────────────────
def test_a2_creator_effective_permission_and_workspace_visibility():
    code = app._product_permission_code("PRIV1")
    # 역할 grant 0 + 계정 override allow 1 → effective True (런타임 판정 정본 경로).
    permissions = app._apply_permission_overrides(
        set(), {code: app.OVERRIDE_ALLOW}, catalog_codes=[code],
    )
    assert permissions[code] is True

    account = {"id": ACTOR_ID, "permissions": permissions}
    products = [
        {"id": NEW_PRODUCT_ID, "product_key": "PRIV1", "name": "비공개 제품", "is_active": True},
        {"id": 502, "product_key": "OTHER", "name": "타 제품", "is_active": True},
    ]
    visible = app._filter_products_for_account_access(account, products)
    assert [p["product_key"] for p in visible] == ["PRIV1"]

    # 무권한 계정에는 여전히 보이지 않는다(격리 유지).
    outsider = {"id": 99, "permissions": app._apply_permission_overrides(set(), {}, catalog_codes=[code])}
    assert app._filter_products_for_account_access(outsider, products) == []


def test_a2b_creator_can_patch_the_product_they_created(monkeypatch):
    """AC-03-1 의 「PATCH 가능」 절 — 종전에는 어떤 테스트도 이 절을 구속하지 않았다(적대 검증).

    `admin_update_product` 의 게이트는 `product.update` 축이고 이 ITEM 이 준 것은
    `product.access.<key>` 축이라 서로 독립이다 — 그 사실 자체를 여기서 고정한다.
    """
    code = app._product_permission_code("PRIV1")
    creator = {
        "id": ACTOR_ID, "username": "opsuser", "role_id": 2,
        "permissions": {code: True, "product.update": True},
    }
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn, actor=creator,
           has_permission=lambda a, perm: bool((a or {}).get("permissions", {}).get(perm)))
    monkeypatch.setattr(
        app, "_audit_product_snapshot",
        lambda c, pid: {"id": int(pid), "product_key": "PRIV1", "name": "n", "description": "d"},
    )
    resp = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"description": "수정된 설명"})))
    assert resp.status_code == 200, _payload(resp)
    assert store["executed"].count("COMMIT") == 1

    # `product.update` 가 없으면 접근 권한을 가져도 403 (두 축 독립 — 표시-집행 분리).
    access_only = dict(creator, permissions={code: True})
    store2 = _store()
    conn2 = _Conn(store2)
    _patch(monkeypatch, conn2, actor=access_only,
           has_permission=lambda a, perm: bool((a or {}).get("permissions", {}).get(perm)))
    denied = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"description": "x"})))
    assert denied.status_code == 403
    assert store2["executed"] == []


def test_a2c_non_numeric_sort_order_is_400_not_traceback(monkeypatch):
    """`int("abc")` 는 트랜잭션 블록 밖에서 터져 처리되지 않은 500 이 됐다(적대 검증 §3)."""
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "SORT1", "name": "정렬", "sort_order": "abc"})
    assert resp.status_code == 400
    assert _payload(resp)["field"] == "sort_order"
    assert store["executed"] == []
    # 정상 정수·빈 값은 그대로 통과.
    for value in (0, 5, "7", None):
        st = _store()
        cn = _Conn(st)
        _patch(monkeypatch, cn)
        assert _create({"product_key": "SORT2", "name": "정렬",
                        "sort_order": value}).status_code == 200


# ── A3: grant 실패 시 전체 rollback ──────────────────────────────────────────
def test_a3_grant_failure_rolls_back_everything(monkeypatch):
    store = _store(fail_on=(("insert into webaccountpermissionoverrides",
                             RuntimeError("injected grant failure")),))
    conn = _Conn(store)
    audit = _patch(monkeypatch, conn)

    resp = _create({"product_key": "PRIV2", "name": "비공개2", "default_role_access": False})

    assert resp.status_code == 500
    body = _payload(resp)
    assert body["error"] == "제품 저장 실패"
    # 예외 원문·주입 문구가 사용자 응답에 새지 않는다.
    assert "injected" not in json.dumps(body, ensure_ascii=False)

    assert "COMMIT" not in store["executed"], store["executed"]
    assert store["executed"].count("ROLLBACK") == 1
    # 감사행도 남지 않는다(같은 tx 이므로).
    assert audit == []
    assert _sql_of(store, "insert into webauditevents") == []
    # 생성자의 **기존** override 를 건드리지 않았다 — DELETE 0건.
    assert _sql_of(store, "delete from webaccountpermissionoverrides") == []


@pytest.mark.parametrize("rowcount", [0, -1])
def test_a3b_grant_zero_affected_rows_rolls_back(monkeypatch, rowcount):
    """영향 행 0 도 실패다 — 「예외 없음」을 성공으로 읽으면 고립이 다시 commit 된다.

    `-1` 도 함께 시험한다: mysql-connector 는 정보 없음을 `-1` 로 주는데, `or 0` 로 감싸면
    `-1` 이 살아남으므로 `< 1` 판정이 여전히 실패로 읽어야 한다(적대 검증 §3 stub 충실도 지적).
    """
    store = _store(override_insert_rows=rowcount)
    conn = _Conn(store)
    _patch(monkeypatch, conn)

    resp = _create({"product_key": "PRIV3", "name": "비공개3", "default_role_access": False})

    assert resp.status_code == 500
    assert "COMMIT" not in store["executed"]
    assert store["executed"].count("ROLLBACK") == 1


def test_a3d_zero_product_lastrowid_rolls_back(monkeypatch):
    """제품 행의 `lastrowid` 가 0 이면 rollback — 그대로 진행하면 `WHERE Id <> 0` 이
    **모든 제품의 IsDefault 를 0 으로 지우고** `ProductId=0` 고아 권한 행이 남는다."""
    store = _store(product_lastrowid=0)
    conn = _Conn(store)
    _patch(monkeypatch, conn)

    resp = _create({"product_key": "ZERO1", "name": "영행", "is_default": True,
                    "default_role_access": False})

    assert resp.status_code == 500
    assert "COMMIT" not in store["executed"]
    assert store["executed"].count("ROLLBACK") == 1
    # 파괴적 side effect 가 발행되지 않았다.
    assert _sql_of(store, "update webproducts set isdefault") == []
    assert _sql_of(store, "insert into webpermissions") == []


def test_a3c_audit_failure_rolls_back_product(monkeypatch):
    """E-03d: 감사행이 같은 tx 이므로 감사 실패도 제품을 되돌린다."""
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    monkeypatch.setattr(
        app, "record_audit_event",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("audit down")),
    )

    resp = _create({"product_key": "PRIV4", "name": "비공개4", "default_role_access": False})

    assert resp.status_code == 500
    assert _payload(resp)["error"] == "제품 저장 실패"
    assert "COMMIT" not in store["executed"]
    assert store["executed"].count("ROLLBACK") == 1


# ── A4: grant 헬퍼는 INSERT 1행만 ────────────────────────────────────────────
def test_a4_grant_helper_inserts_single_row_only():
    store = _store()
    conn = _Conn(store)
    conn.autocommit = False        # 이 헬퍼는 호출자의 트랜잭션 안에서만 쓰인다
    admin_products._grant_product_access_to_account(conn, ACTOR_ID, NEW_PERMISSION_ID)
    inserts = [s for s in store["executed"] if s.lower().startswith("insert into")]
    assert len(inserts) == 1
    joined = " ".join(store["executed"]).lower()
    assert "delete" not in joined, "이 헬퍼가 DELETE 를 하면 생성자의 기존 override 가 전멸한다"
    assert "select" not in joined


def test_a4b_grant_helper_rejects_invalid_targets():
    conn = _Conn(_store())
    conn.autocommit = False
    with pytest.raises(RuntimeError):
        admin_products._grant_product_access_to_account(conn, 0, NEW_PERMISSION_ID)
    with pytest.raises(RuntimeError):
        admin_products._grant_product_access_to_account(conn, ACTOR_ID, 0)


def test_a4c_grant_helper_source_does_not_inherit_set_account_overrides():
    """구조 가드 — `_set_account_overrides` 의 delete-all-then-insert 를 상속하지 않는다.

    AST 로 함수를 떼어 **docstring 노드만** 제거한 뒤 본다 — 정규식으로 삼중 인용을 전부
    지우면 SQL 리터럴까지 사라져 검사가 항진명제(항상 통과)가 된다(직접 실측).
    """
    import ast

    tree = ast.parse((_SRC / "routers" / "admin_products.py").read_text(encoding="utf-8"))
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "_grant_product_access_to_account"),
        None,
    )
    assert fn is not None, "_grant_product_access_to_account 정의를 찾지 못했다"
    if ast.get_docstring(fn) is not None:
        fn.body = fn.body[1:]
    code = ast.unparse(fn)
    upper = code.upper()
    assert "DELETE" not in upper, "이 헬퍼가 DELETE 를 하면 생성자의 기존 override 가 전멸한다"
    assert "UPDATE" not in upper
    assert upper.count("INSERT INTO WEBACCOUNTPERMISSIONOVERRIDES") == 1
    assert "_set_account_overrides" not in code
    assert "SELECT" not in upper, "기존 override 를 읽지도 않는다(교체 로직의 전조)"


# ── A7: 인가 게이트 · self-scope 가드 무변경 ──────────────────────────────────
def test_a7_create_requires_product_create_permission(monkeypatch):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn, has_permission=False)

    resp = _create({"product_key": "NOPE", "name": "무권한", "default_role_access": False})

    assert resp.status_code == 403
    assert _payload(resp)["error"] == "제품 관리 권한이 필요합니다."
    # 어떤 쓰기도 하지 않는다.
    assert store["executed"] == []


@pytest.mark.parametrize("path,func,message", [
    ("routers/admin_accounts.py", "_enforce_override_self_scope",
     "본인이 보유하지 않은 권한은 설정할 수 없습니다"),
    ("routers/admin_roles.py", "_enforce_role_permission_self_scope",
     "본인이 보유하지 않은 권한은 역할에 부여할 수 없습니다"),
])
def test_a7b_self_scope_guards_unchanged(path, func, message):
    """ITEM-03 의 명시 guard: 두 가드를 손대지 않는다 — 관리자 이름·역할 우회를 넣지 않는다.

    생성 시점 grant 가 가드를 완화할 필요를 없애는 것이 이 ITEM 의 설계다
    (`docs/SECURITY.md` §28.6 · 새 ADR). 우회가 들어오면 여기서 먼저 깨진다.
    """
    src = (_SRC / path).read_text(encoding="utf-8")
    m = re.search(rf"def {func}\(.*?\n(?=\ndef |\n@|\n# ====)", src, re.S)
    assert m, f"{func} 정의를 찾지 못했다"
    body = m.group(0)
    assert message in body
    assert "raise ValueError" in body
    lowered = body.lower()
    for bypass in ('== "admin"', "== 'admin'", "is_admin", "superuser", "bypass"):
        assert bypass not in lowered, f"{func} 에 관리자 우회로 보이는 표현: {bypass}"


# ── A8 · A9: 길이 경계 (경계 양측 · 한글 · 이모지 · 특수문자) ──────────────────
_KO = "가"
_MAX = 255


@pytest.mark.parametrize("length,expect_status", [
    (0, 200), (1, 200), (_MAX - 1, 200), (_MAX, 200), (_MAX + 1, 400), (_MAX + 100, 400),
])
def test_a8_description_length_boundary_both_sides(monkeypatch, length, expect_status):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "LEN1", "name": "길이", "description": _KO * length})
    assert resp.status_code == expect_status, (length, _payload(resp))
    if expect_status == 400:
        body = _payload(resp)
        assert body["field"] == "description"
        assert body["max"] == _MAX
        assert body["error"] == f"설명은 {_MAX}자 이내여야 합니다 (현재 {length}자)"
        # 400 이면 아무 것도 쓰지 않는다.
        assert store["executed"] == []


def test_a8b_name_length_boundary(monkeypatch):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    assert _create({"product_key": "LEN2", "name": _KO * 128}).status_code == 200
    resp = _create({"product_key": "LEN2", "name": _KO * 129})
    assert resp.status_code == 400
    body = _payload(resp)
    assert (body["field"], body["max"]) == ("name", 128)


@pytest.mark.parametrize("description", [
    "🙂" * 255,                     # 이모지 255자 = 경계 통과 (문자 수 기준)
    "따옴표 '단일' \"이중\" 포함",
    "주석 -- 처럼 보이는 문자열",
    "세미콜론; 포함",
    "역슬래시 \\ 와 백틱 ` 포함",
    "혼합 한글abc123 🙂 -- ; ' \"",
])
def test_a8c_special_characters_are_stored_not_rejected(monkeypatch, description):
    """특수문자는 **파라미터 바인딩**으로 저장된다 — 거부하거나 이스케이프하지 않는다."""
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "SPEC1", "name": "특수문자", "description": description})
    assert resp.status_code == 200, _payload(resp)
    inserts = [
        p for s, p in zip(store["executed"], store["params"])
        if s.lower().startswith("insert into webproducts")
    ]
    assert inserts and inserts[0][2] == description.strip()


def test_a8c2_measured_value_equals_stored_value(monkeypatch):
    """길이를 **재는 값**과 **저장하는 값**이 같아야 한다 (`.strip()` 타이밍 계약).

    공백 포함 256자는 strip 후 255자이므로 통과하고, **저장되는 것도 그 255자**다.
    두 값이 갈리면 「검사는 통과했는데 DB 가 1406」 또는 그 반대가 생긴다.
    """
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    raw = " " + _KO * 255 + " "          # 원문 257자, strip 후 255자
    resp = _create({"product_key": "STRIP1", "name": "공백", "description": raw})
    assert resp.status_code == 200, _payload(resp)
    stored = [
        p for s2, p in zip(store["executed"], store["params"])
        if s2.lower().startswith("insert into webproducts")
    ][0][2]
    assert stored == raw.strip()
    assert len(stored) == 255

    # strip 후에도 상한을 넘으면 거부하고, 오류 문안의 N 은 **strip 후 길이**다.
    store2 = _store()
    conn2 = _Conn(store2)
    _patch(monkeypatch, conn2)
    resp2 = _create({"product_key": "STRIP2", "name": "공백",
                     "description": "  " + _KO * 256 + "  "})
    assert resp2.status_code == 400
    assert _payload(resp2)["error"] == f"설명은 {_MAX}자 이내여야 합니다 (현재 256자)"
    assert store2["executed"] == []


def test_a8d_emoji_over_boundary_rejected(monkeypatch):
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = _create({"product_key": "SPEC2", "name": "이모지", "description": "🙂" * 256})
    assert resp.status_code == 400
    assert _payload(resp)["error"] == f"설명은 {_MAX}자 이내여야 합니다 (현재 256자)"


def test_a8b2_max_length_name_fits_every_derived_column(monkeypatch):
    """⭐ 이름은 **두 컬럼**에 쓰인다 — `WebProducts.Name`(128) 과 `WebPermissions.Label`(128).

    Label 은 `f"제품 접근 — {name}"` 이라 접두 8자가 붙으므로, 상한 128자짜리 **정당한**
    이름이 Name 검사를 통과하고도 Label 에서 1406 으로 죽었다(적대 검증 P1 실측: 121~128자).
    stub cursor 는 컬럼 폭을 강제하지 않으므로 경계 테스트만으로는 통과했다 — 그래서 여기서
    **실제로 바인딩되는 파생 문자열의 길이**를 직접 재서 DDL 상한과 대조한다.
    """
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    long_name = _KO * app.PRODUCT_NAME_MAX          # 상한 정확히 채운 정당한 이름
    resp = _create({"product_key": "LBL1", "name": long_name})
    assert resp.status_code == 200, _payload(resp)

    perm_params = [
        p for s2, p in zip(store["executed"], store["params"])
        if s2.lower().startswith("insert into webpermissions")
    ]
    assert len(perm_params) == 1
    label, description = perm_params[0][1], perm_params[0][2]
    assert len(label) <= app.PERMISSION_LABEL_MAX, (
        f"Label {len(label)}자 > {app.PERMISSION_LABEL_MAX} — 실 MySQL 에서 1406"
    )
    assert len(description) <= app.PERMISSION_DESCRIPTION_MAX
    # clip 했더라도 사람이 읽을 수 있는 접두는 남는다.
    assert label.startswith("제품 접근 — ")


def test_a8b3_permission_constants_match_ddl():
    """`WebPermissions` 파생 컬럼 상한도 DDL 과 동치여야 한다(수기 표류 차단)."""
    ddl = (_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS WebPermissions \((.*?)\n\s*\) ENGINE", ddl, re.S)
    assert m, "WebPermissions DDL 을 찾지 못했다"
    block = m.group(1)
    assert f"Label VARCHAR({app.PERMISSION_LABEL_MAX})" in block
    assert f"Description VARCHAR({app.PERMISSION_DESCRIPTION_MAX})" in block
    # 접두가 길어지면 clip 이 이름을 더 많이 먹는다 — 여유를 명시적으로 계측해 둔다.
    prefix_len = len("제품 접근 — ")
    assert prefix_len + app.PRODUCT_NAME_MAX > app.PERMISSION_LABEL_MAX, (
        "이 단언이 깨지면 clip 이 더는 필요 없다 — 그때 clip 을 지워도 된다(의도 기록)"
    )


def test_a8e2_unmapped_length_error_column_is_not_faked_as_400():
    """사용자 입력에 매핑되지 않는 컬럼의 길이 오류를 **틀린 필드 안내**로 위장하지 않는다.

    종전 분류기는 `Label` 을 어느 분기에도 못 걸어 「입력은 255자 이내」(field 없음)를 냈고,
    `SchemaName`·`GroupName` 은 부분문자열 `"Name"` 에 걸려 「표시 이름 128자」로 오분류했다.
    """
    class _MySqlError(Exception):
        errno = 1406

    for column in ("Label", "SchemaName", "GroupName", "Code"):
        resp = admin_products._product_save_error(
            _MySqlError(f"1406 (22001): Data too long for column '{column}' at row 1"))
        assert resp.status_code == 500, column
        body = _payload(resp)
        assert body == {"error": "제품 저장 실패"}, (column, body)
        assert column not in json.dumps(body, ensure_ascii=False)

    # 매핑되는 컬럼은 그대로 400 + 정확한 field.
    for column, field, mx in (("Description", "description", 255), ("Name", "name", 128)):
        resp = admin_products._product_save_error(
            _MySqlError(f"1406 (22001): Data too long for column '{column}' at row 1"))
        assert resp.status_code == 400
        body = _payload(resp)
        assert (body["field"], body["max"]) == (field, mx)


def test_a9d_schema_name_gate_matches_ddl(monkeypatch):
    """접근DB 스키마명 상한이 DDL(`VARCHAR(64)`)과 같아야 한다.

    게이트가 128 이던 동안 65~128자는 앱을 통과하고 DELETE 후 INSERT 루프에서 1406 으로
    죽어 **부분 쓰기**(삭제만 반영)를 남겼다(적대 검증 P2).
    """
    ddl = (_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS WebProductDatabases \((.*?)\n\s*\) ENGINE", ddl, re.S)
    assert m and f"SchemaName VARCHAR({admin_products._SCHEMA_NAME_MAX})" in m.group(1)

    store = _store(select_rows=[(NEW_PRODUCT_ID, "mainmysql")])
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = asyncio.run(admin_products.admin_update_product_databases(
        NEW_PRODUCT_ID,
        _Req({"databases": [{"schema_name": "s" * 65}]}),
        account=_actor(), conn=conn,
    ))
    assert resp.status_code == 400
    assert "invalid schema_name" in _payload(resp)["error"]
    # 거부됐으니 DELETE 가 발행되지 않았다(부분 쓰기 0).
    assert _sql_of(store, "delete from webproductdatabases") == []


def test_a8e_driver_length_error_is_classified_not_echoed():
    """E-09b 정면: `Data too long for column 'Description'` 이 응답에 **절대** 나오지 않는다."""
    class _MySqlError(Exception):
        errno = 1406

    resp = admin_products._product_save_error(
        _MySqlError("1406 (22001): Data too long for column 'Description' at row 1"))
    assert resp.status_code == 400
    body = _payload(resp)
    assert body == {"error": f"설명은 {_MAX}자 이내여야 합니다.", "max": _MAX, "field": "description"}
    raw = json.dumps(body, ensure_ascii=False)
    for leak in ("Data too long", "22001", "at row", "column"):
        assert leak not in raw


def test_a8f_duplicate_key_error_is_409():
    class _MySqlError(Exception):
        errno = 1062

    resp = admin_products._product_save_error(
        _MySqlError("1062 (23000): Duplicate entry 'KR' for key 'WebProducts.ProductKey'"))
    assert resp.status_code == 409
    assert _payload(resp)["error"] == "이미 존재하는 product_key 입니다."


def test_a8g_unknown_error_is_generic_500_without_sql():
    resp = admin_products._product_save_error(
        RuntimeError("INSERT INTO WebProducts (ProductKey, ...) VALUES (...) failed: deadlock"))
    assert resp.status_code == 500
    body = _payload(resp)
    assert body == {"error": "제품 저장 실패"}
    for leak in ("INSERT", "WebProducts", "deadlock"):
        assert leak not in json.dumps(body, ensure_ascii=False)


def test_a8h_product_mutation_500s_do_not_echo_exception_text():
    """제품 CRUD 3핸들러(create·update·delete)의 500 은 **모두** 분류기를 거친다.

    그리고 이 라우터에 남은 «예외 문자열을 응답에 싣는» 지점의 **모수를 고정**한다 —
    ITEM-03 승인 범위는 제품 저장 경로였고 나머지(`audit write failed: {exc}` 계열 ·
    LLM 502)는 다른 family 의 선재 부채다. 여기서 개수를 못박아 두면 그 클래스가 조용히
    **늘어나지는** 못한다(§16.7 G10 — 재발 클래스의 구조 가드).
    """
    import ast

    src = (_SRC / "routers" / "admin_products.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    handlers = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in ("admin_create_product", "admin_update_product", "admin_delete_product"):
        body = ast.unparse(handlers[name])
        assert "_product_save_error(" in body, f"{name} 이 예외 분류기를 쓰지 않는다"
        # 그 핸들러 안에서 예외 객체를 응답 문자열에 보간하지 않는다.
        assert "{exc}" not in body, f"{name} 이 예외 문자열을 응답에 싣는다"

    # 라우터 전체에 남은 잔여 모수(승인 범위 밖 family) — 늘어나면 여기서 걸린다.
    residual = re.findall(r'_json_error\(f"[^"]*\{(?:audit_exc|llm_exc|exc)\}', src)
    assert len(residual) == 9, (
        f"예외 문자열을 응답에 싣는 지점이 {len(residual)}곳 — 기준선 9곳에서 변했다. "
        "늘었다면 새 경로가 드라이버 메시지를 노출한다(E-09b 클래스 재발). "
        "줄였다면 이 기준선을 함께 낮춰라."
    )


def test_a9_patch_applies_same_length_rule(monkeypatch):
    store = _store(select_rows=[])
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    monkeypatch.setattr(
        app, "_audit_product_snapshot",
        lambda c, pid: {"id": int(pid), "product_key": "LEN3", "name": "n", "description": "d"},
    )

    resp = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"description": _KO * 256})))
    assert resp.status_code == 400
    body = _payload(resp)
    assert (body["field"], body["max"]) == ("description", _MAX)
    assert body["error"] == f"설명은 {_MAX}자 이내여야 합니다 (현재 256자)"
    assert "COMMIT" not in store["executed"]
    assert _sql_of(store, "update webproducts set") == []

    store2 = _store()
    conn2 = _Conn(store2)
    _patch(monkeypatch, conn2)
    ok = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"description": _KO * 255})))
    assert ok.status_code == 200
    assert store2["executed"].count("COMMIT") == 1


def test_a9c_patch_rejects_non_boolean_default_role_access(monkeypatch):
    """PATCH 도 create 와 같은 엄격 파싱 — 비대칭이 남으면 그쪽으로 정책을 뒤집을 수 있다."""
    store = _store()
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    monkeypatch.setattr(
        app, "_audit_product_snapshot",
        lambda c, pid: {"id": int(pid), "product_key": "DRA4", "name": "n", "description": "d"},
    )
    resp = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"default_role_access": "false"})))
    assert resp.status_code == 400
    assert _payload(resp)["field"] == "default_role_access"
    assert "COMMIT" not in store["executed"]
    assert _sql_of(store, "update webproducts set") == []

    store2 = _store()
    conn2 = _Conn(store2)
    _patch(monkeypatch, conn2)
    ok = asyncio.run(admin_products.admin_update_product(
        NEW_PRODUCT_ID, _Req({"default_role_access": False})))
    assert ok.status_code == 200
    assert store2["executed"].count("COMMIT") == 1


def test_a9b_product_databases_description_uses_same_limit(monkeypatch):
    """`WebProductDatabases.Description` 도 VARCHAR(255) — 다른 표면으로 1406 이 돌아오지 않게."""
    store = _store(select_rows=[(NEW_PRODUCT_ID, "mainmysql")])
    conn = _Conn(store)
    _patch(monkeypatch, conn)

    resp = asyncio.run(admin_products.admin_update_product_databases(
        NEW_PRODUCT_ID,
        _Req({"databases": [{"schema_name": "shop", "description": _KO * 256}]}),
        account=_actor(), conn=conn,
    ))
    assert resp.status_code == 400
    body = _payload(resp)
    assert (body["field"], body["max"]) == ("description", _MAX)


def test_a9b2_product_databases_accepts_boundary_description_and_pins_nonatomic_write(monkeypatch):
    """경계의 **통과 측**을 고정하고, 그 뒤 쓰기 경로가 **비원자적**이라는 선재 사실을 못박는다.

    경계 거부만 시험하면 상한을 0 으로 줄여도 통과한다 → 255자가 길이 검증을 **통과해서
    쓰기 경로에 도달**함을 확인해야 한다. 그런데 그 쓰기 경로(`DELETE` → `INSERT` 루프)는
    `autocommit=False` 를 걸지 않는다 — autocommit 감시 stub 이 첫 `DELETE` 에서 raise 하는
    것이 그 증거다(적대 검증 backend P2). ITEM-03 은 그 루프에 **도달하는 과길이 입력**을
    상한 정합(64/255)으로 막았을 뿐 루프의 원자화는 하지 않았다(승인 범위 밖 · REPORT 후속).
    이 테스트는 그 사실을 **보이게** 유지한다 — 원자화되면 여기서 먼저 깨져 갱신을 요구한다.
    """
    store = _store(select_rows=[(NEW_PRODUCT_ID, "mainmysql")])
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    desc = _KO * _MAX
    with pytest.raises(RuntimeError, match="autocommit=True"):
        asyncio.run(admin_products.admin_update_product_databases(
            NEW_PRODUCT_ID,
            _Req({"databases": [{"schema_name": "shop", "description": desc}]}),
            account=_actor(), conn=conn,
        ))
    # 길이 검증을 통과했다 = description 400 이 발행되지 않고 쓰기 경로까지 갔다.
    assert _sql_of(store, "delete from webproductdatabases") == [], (
        "감시 stub 이 첫 쓰기에서 막았으므로 executed 에는 기록되지 않는다"
    )
    # 그 쓰기가 트랜잭션 밖이었다는 사실 자체가 위 raise 로 증명된다.


# ── A10: 상수 ↔ DDL ↔ 프론트 3자 동치 ────────────────────────────────────────
def test_a10_constants_match_ddl():
    ddl = (_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    assert app.PRODUCT_DESCRIPTION_MAX == 255
    assert app.PRODUCT_NAME_MAX == 128

    def _block(table):
        m = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\s*\) ENGINE", ddl, re.S)
        assert m, f"{table} DDL 을 찾지 못했다"
        return m.group(1)

    products = _block("WebProducts")
    assert f"Description VARCHAR({app.PRODUCT_DESCRIPTION_MAX})" in products
    assert f"Name VARCHAR({app.PRODUCT_NAME_MAX})" in products
    product_dbs = _block("WebProductDatabases")
    assert f"Description VARCHAR({app.PRODUCT_DESCRIPTION_MAX})" in product_dbs


def test_a10b_frontend_constants_match_backend():
    src = (_STATIC / "admin" / "products.js").read_text(encoding="utf-8")
    assert f"const PRODUCT_DESCRIPTION_MAX = {app.PRODUCT_DESCRIPTION_MAX};" in src
    assert f"const PRODUCT_NAME_MAX = {app.PRODUCT_NAME_MAX};" in src


def test_a10c2_counter_css_rule_beats_field_caption_rule():
    """⭐ CSS 규칙이 **파일에 있어도 적용되지 않는** 클래스를 잠근다.

    카운터는 `<label class="field ...">` 의 직속 span 이라 `base.css` 의
    `.field > span`(0-1-1: bold + --text-2)이 함께 매칭된다. 단일 클래스 셀렉터(0-1-0)면
    특이도에서 밀려 **필드 캡션과 똑같이 굵게** 렌더된다(실 Chromium 실측: pre-fix
    `rgb(90,88,82)`/600 → post-fix `rgb(128,125,114)`/400). 선언 순서로는 해결되지 않는다.
    """
    css = (_STATIC / "css" / "admin.css").read_text(encoding="utf-8")
    base = (_STATIC / "css" / "base.css").read_text(encoding="utf-8")
    assert ".field > span {" in base, "경쟁 규칙이 사라졌다면 이 가드의 전제를 재확인하라"
    assert "label.field > .admin-char-counter {" in css, (
        "단일 클래스 셀렉터는 `.field > span` 에 밀린다 — `label.field >` 를 유지하라"
    )
    assert "label.field > .admin-char-counter.is-limit {" in css
    # 상한 도달은 오류가 아니다(maxlength 가 초과를 이미 막는다) → danger 아님.
    limit_block = css.split("label.field > .admin-char-counter.is-limit {", 1)[1].split("}", 1)[0]
    assert "--warning" in limit_block, "정상 값에 error 색을 쓰지 않는다"
    assert "--danger" not in limit_block
    # 정의되지 않은 토큰(`--muted`)에 조용히 fallback 하지 않는다.
    rest_block = css.split("label.field > .admin-char-counter {", 1)[1].split("}", 1)[0]
    assert "--text-muted" in rest_block
    assert "--muted," not in rest_block


def test_a10c_frontend_wires_maxlength_and_counter():
    src = (_STATIC / "admin" / "products.js").read_text(encoding="utf-8")
    assert "descInput.maxLength = PRODUCT_DESCRIPTION_MAX;" in src
    assert "nameInput.maxLength = PRODUCT_NAME_MAX;" in src
    assert src.count("_attachCharCounter(") >= 3  # 정의 1 + 이름/설명 배선 2
    assert 'counter.className = "admin-char-counter"' in src
    # 감싸는 label 의 접근가능 이름을 오염시키지 않는다(타이핑마다 바뀌는 숫자).
    assert 'counter.setAttribute("aria-hidden", "true")' in src
    css = (_STATIC / "css" / "admin.css").read_text(encoding="utf-8")
    # 규칙이 파일에 있는 것과 «적용되는 것» 은 다르다 — 최소한 미닫힌 @media 안에 들지
    # 않았음을 중괄호 균형으로 확인한다(선행 결함 클래스: CSS 규칙이 있어도 미적용).
    assert ".admin-char-counter {" in css
    head = css.split(".admin-char-counter {")[0]
    assert head.count("{") == head.count("}"), "카운터 규칙이 미닫힌 블록 안에 있다"


def test_a10d_create_flow_collects_description_and_scope():
    src = (_STATIC / "admin" / "products.js").read_text(encoding="utf-8")
    m = re.search(r"function startNewProduct\(\) \{(.*?)\n\}", src, re.S)
    assert m, "startNewProduct 를 찾지 못했다"
    body = m.group(1)
    assert "default_role_access: defaultRoleAccess" in body
    assert "description," in body
    # 인식하지 못한 접근 범위 답을 임의 해석하지 않고 다시 묻는다(조용한 오독 금지).
    assert "비공개|private" in body
    assert "공개|public" in body


def test_a10d2_create_flow_preserves_draft_and_confirms_irreversible_scope():
    """취소가 작성분을 버리지 않고, 되돌릴 수 없는 선택 앞에 요약 confirm 이 있다."""
    src = (_STATIC / "admin" / "products.js").read_text(encoding="utf-8")
    assert "_newProductDraft" in src, "취소 시 입력을 보존하는 초안 캐시가 없다"
    m = re.search(r"function startNewProduct\(\) \{(.*?)\n\}", src, re.S)
    body = m.group(1)
    assert "window.confirm(" in body, "되돌릴 수 없는 접근 범위 선택에 확정 단계가 없다"
    assert "되돌릴 수 없습니다" in body
    # 성공 시에만 초안을 비운다(실패·취소 후 재시도에 남아 있어야 한다).
    assert "_newProductDraft = { key: \"\", name: \"\", description: \"\" };" in src


def test_a10e_bulk_failure_toast_shows_first_reason():
    src = (_STATIC / "admin.js").read_text(encoding="utf-8")
    m = re.search(r"if \(failures\.length\) \{(.*?)\n  \} else \{", src, re.S)
    assert m, "일괄 적용 실패 분기를 찾지 못했다"
    body = m.group(1)
    assert "first?.error?.message" in body
    assert "reason" in body and "showToast(" in body
    # 사유가 갈리는 혼합 배치에서 첫 사유가 전체 이유로 읽히지 않게 알린다.
    assert "f.kind !== first.kind" in body
    assert "다른 사유" in body


# ── A11: 복구 스크립트 ───────────────────────────────────────────────────────
def _load_repair():
    spec = importlib.util.spec_from_file_location("_product_access_repair", _REPAIR_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    saved = sys.modules.get("_product_access_repair")
    sys.modules["_product_access_repair"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        if saved is not None:
            sys.modules["_product_access_repair"] = saved
        else:
            sys.modules.pop("_product_access_repair", None)
    return mod


class _RepairCursor:
    """진단·복구 SQL 을 상태 dict 로 응답하는 stub."""

    def __init__(self, state):
        self._state = state
        self._rows: list = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        sl = s.lower()
        self._state["executed"].append(s)
        self._rows = []
        self.rowcount = 0
        if "from webproducts p" in sl:
            self._rows = list(self._state["products"])
        elif sl.startswith("select count(*) from webaccounts a"):
            pid = int((params or (0,))[0])
            self._rows = [(int(self._state["grantees"].get(pid, 0)),)]
        elif "from webauditevents ev" in sl:
            self._rows = list(self._state.get("create_actor", []))
        elif sl.startswith("select id from webproducts where id"):
            wanted = int((params or (0,))[0])
            self._rows = [(wanted,)] if any(int(r[0]) == wanted for r in self._state["products"]) else []
        elif sl.startswith("select id, username, isactive, deletedat from webaccounts"):
            wanted = int((params or (0,))[0])
            self._rows = [r for r in self._state.get("account", []) if int(r[0]) == wanted]
        elif sl.startswith("select overridevalue from webaccountpermissionoverrides"):
            existing = self._state.get("existing_override")
            self._rows = [(existing,)] if existing is not None else []
        elif sl.startswith("insert into webaccountpermissionoverrides"):
            self.rowcount = 1
            self._state["written"].append(params)
            # 부여 성공을 진단에 반영 — 재진단이 0건이어야 한다.
            self._state["grantees"][int((params or (0, 0))[1])] = 1

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _RepairConn:
    def __init__(self, state):
        self._state = state
        self.autocommit = True

    def cursor(self, *a, **kw):
        return _RepairCursor(self._state)

    def commit(self):
        self._state["executed"].append("COMMIT")

    def rollback(self):
        self._state["executed"].append("ROLLBACK")

    def close(self):
        pass


def _repair_state(**over):
    state = {
        "executed": [], "written": [], "existing_override": None,
        # (Id, ProductKey, Name, IsActive, DefaultRoleAccess, PermissionId, Code)
        "products": [
            (990002, "PRIV", "비공개 제품", 1, 0, NEW_PERMISSION_ID, "product.access.priv"),
            (91, "DK", "DK", 1, 1, 902, "product.access.dk"),
        ],
        "grantees": {902: 4},          # DK 는 정상, PRIV 는 0
        "create_actor": [(ACTOR_ID, "2026-09-09 06:32:17", "mckim")],
        "account": [(ACTOR_ID, "opsuser", 1, None)],
    }
    state.update(over)
    return state


def test_a11_dry_run_lists_orphans_and_writes_nothing():
    mod = _load_repair()
    state = _repair_state()
    orphans = mod.diagnose(_RepairConn(state))
    assert [o["product_id"] for o in orphans] == [990002]
    assert orphans[0]["reason"] == "no_grantee"
    assert orphans[0]["create_actor"]["account_id"] == ACTOR_ID
    # 진단은 **읽기 전용** — 실행한 문장이 모두 SELECT 로 시작해야 한다(컬럼명에 섞인
    # 'DeletedAt' 같은 문자열이 아니라 «문장의 종류» 로 판정한다).
    kinds = {s.split(None, 1)[0].upper() for s in state["executed"] if s.strip()}
    assert kinds == {"SELECT"}, state["executed"]
    assert state["written"] == []
    assert "COMMIT" not in state["executed"]


def test_a11b_missing_permission_row_is_reported_separately():
    mod = _load_repair()
    state = _repair_state(products=[(990003, "NOPERM", "권한행 없음", 1, 0, None, None)],
                          grantees={})
    orphans = mod.diagnose(_RepairConn(state))
    assert orphans[0]["reason"] == "missing_permission"


def test_a11c_inactive_orphans_are_reported_by_default():
    """⭐ 기본값이 **활성만** 이면 안 된다 — 라이브 dry-run(2026-09-10)에서 요구서가 지목한
    고립 제품 990002 가 **비활성**이라 「고립 Product 없음」이 출력됐다(도구가 자기 존재
    이유인 데이터를 숨김). 기본은 전부, 좁히는 것만 명시 flag.
    """
    mod = _load_repair()
    state = _repair_state(products=[(990002, "PRIV", "비활성", 0, 0, NEW_PERMISSION_ID, "c")],
                          grantees={})
    assert len(mod.diagnose(_RepairConn(state))) == 1, "비활성 고립이 기본 진단에서 빠졌다"
    assert mod.diagnose(_RepairConn(state), active_only=True) == []


def test_a11d_apply_grants_one_row_and_rediagnose_is_zero():
    mod = _load_repair()
    state = _repair_state()
    conn = _RepairConn(state)
    result = mod.repair(conn, 990002, ACTOR_ID, operator_id=ACTOR_ID)
    assert result["status"] == "ok"
    assert state["written"] == [(ACTOR_ID, NEW_PERMISSION_ID, "allow")]
    assert state["executed"].count("COMMIT") == 1
    assert "delete from webaccountpermissionoverrides" not in " ".join(state["executed"]).lower()
    # 사후 대조 — 같은 진단을 다시 돌리면 0건.
    assert mod.diagnose(conn) == []


def test_a11e_apply_refuses_when_account_not_specified():
    mod = _load_repair()
    state = _repair_state()
    calls = {"n": 0}

    def _connect():
        calls["n"] += 1
        return _RepairConn(state)

    saved = app._connect_memory
    app._connect_memory = _connect
    try:
        rc = mod.main(["--apply", "--product", "990002"])
    finally:
        app._connect_memory = saved
    assert rc == 1
    assert state["written"] == []


def test_a11f_apply_does_not_flip_explicit_deny():
    mod = _load_repair()
    state = _repair_state(existing_override="deny")
    result = mod.repair(_RepairConn(state), 990002, ACTOR_ID, operator_id=ACTOR_ID)
    assert result["status"] == "deny_override_present"
    assert state["written"] == []
    assert "COMMIT" not in state["executed"]


def test_a11g_apply_is_idempotent_when_already_allowed():
    mod = _load_repair()
    state = _repair_state(existing_override="allow", grantees={902: 4})
    result = mod.repair(_RepairConn(state), 990002, ACTOR_ID, operator_id=ACTOR_ID)
    assert result["status"] == "already_allowed"
    assert state["written"] == []


def test_a11h_apply_rejects_inactive_or_unknown_grant_account():
    """부여 **대상** 계정의 상태 검사 — 수행자(operator)는 별개의 활성 계정으로 고정한다."""
    OPER = 3
    oper_row = (OPER, "operator", 1, None)

    mod = _load_repair()
    # 대상 계정 비활성
    state = _repair_state(account=[oper_row, (ACTOR_ID, "opsuser", 0, None)])
    assert mod.repair(_RepairConn(state), 990002, ACTOR_ID,
                      operator_id=OPER)["status"] == "account_inactive"
    assert state["written"] == []
    # 대상 계정 미존재
    state2 = _repair_state(account=[oper_row])
    assert mod.repair(_RepairConn(state2), 990002, ACTOR_ID,
                      operator_id=OPER)["status"] == "account_not_found"
    assert state2["written"] == []
    # 고립이 아닌 제품
    state3 = _repair_state(account=[oper_row, (ACTOR_ID, "opsuser", 1, None)])
    assert mod.repair(_RepairConn(state3), 91, ACTOR_ID,
                      operator_id=OPER)["status"] == "not_orphan"
    assert state3["written"] == []


def test_a11h2_repair_finds_inactive_orphan_without_extra_flag():
    """복구 경로도 같은 기본값을 쓴다 — 비활성 고립을 `--active-only` 없이 고칠 수 있어야 한다."""
    mod = _load_repair()
    state = _repair_state(products=[(990002, "PRIV", "비활성", 0, 0, NEW_PERMISSION_ID, "c")],
                          grantees={})
    assert mod.repair(_RepairConn(state), 990002, ACTOR_ID, operator_id=ACTOR_ID)["status"] == "ok"
    assert state["written"] == [(ACTOR_ID, NEW_PERMISSION_ID, "allow")]


def test_a11j_apply_records_human_operator_as_audit_actor():
    """인가 데이터 부여의 감사행 actor 는 **사람 계정**이어야 한다 (패널 security P2).

    `actor_type='system'` 만 남기면 `ActorAccountId` 가 NULL 이라 「누가 부여했는가」를
    감사 시스템 안에서 답할 수 없다 — docker exec 권한자 누구든 흔적 없이 부여 가능해진다.
    """
    mod = _load_repair()
    state = _repair_state()
    captured = {}

    def _rec(conn_, *, actor, action, resource_type, resource_id, change_json,
             masked_fields=None, target_account_id=None):
        captured.update({"actor": actor, "action": action, "change": change_json,
                         "target": target_account_id})

    saved = app.record_audit_event
    app.record_audit_event = _rec
    try:
        result = mod.repair(_RepairConn(state), 990002, ACTOR_ID, operator_id=ACTOR_ID)
    finally:
        app.record_audit_event = saved

    assert result["status"] == "ok"
    assert captured["actor"]["actor_type"] == "account"
    assert captured["actor"]["account_id"] == ACTOR_ID
    assert captured["actor"]["username"] == "opsuser"
    assert captured["action"] == "admin.product.access.repair"
    assert captured["target"] == ACTOR_ID
    assert captured["change"]["operator_account_id"] == ACTOR_ID
    assert "host_os_user" in captured["change"]


def test_a11k_apply_rejects_unknown_or_inactive_operator():
    mod = _load_repair()
    state = _repair_state()
    assert mod.repair(_RepairConn(state), 990002, ACTOR_ID,
                      operator_id=999)["status"] == "operator_not_found"
    assert state["written"] == []

    state2 = _repair_state(account=[(ACTOR_ID, "opsuser", 0, None)])
    assert mod.repair(_RepairConn(state2), 990002, ACTOR_ID,
                      operator_id=ACTOR_ID)["status"] == "operator_inactive"
    assert state2["written"] == []


def test_a11l_cli_requires_operator_with_apply():
    """`--apply` 는 `--operator` 없이는 거부한다 — 쓰기 0."""
    mod = _load_repair()
    state = _repair_state()
    saved = app._connect_memory
    app._connect_memory = lambda: _RepairConn(state)
    try:
        rc = mod.main(["--apply", "--product", "990002", "--grant-account", str(ACTOR_ID)])
    finally:
        app._connect_memory = saved
    assert rc == 1
    assert state["written"] == []


def test_a11i_wrapper_defaults_to_dry_run_and_never_auto_selects():
    sh = (Path(__file__).resolve().parents[3] / "bin" / "product-access-repair.sh")
    src = sh.read_text(encoding="utf-8")
    assert "--grant-account" in src
    assert "자동 선택하지 않는다" in src
    # 래퍼 사용 예시가 「기본이 전부 진단」을 반영해야 한다(비활성 숨김 재발 방지).
    assert "--active-only" in src
    assert "--operator" in src
    # 래퍼가 스스로 --apply 를 붙이지 않는다(사용 예시 주석은 제외).
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "--apply" not in body


# ── A12: 행위 하네스(jsdom) 실행 또는 gap 기록 ────────────────────────────────
_HARNESS = Path(__file__).resolve().parent / "verify_product_create_flow.mjs"
_CI_GAP_MARKER = "product-atomic-create: 행위 하네스 CI 미배선"


def test_a12_behaviour_harness_runs_or_gap_is_documented():
    """프론트 **행위**는 소스 대조가 아니라 하네스가 본다 — 돌리거나, 못 돌리면 «기록» 한다.

    조용한 `skip` 은 「검증했다」로 오인된다(선례: `test_attach_csv_table.py::test_s7` 와 동일 계약).
    본 프로젝트의 `make test` 는 agent 이미지에 node·node-jsdom 을 설치하므로 여기서 실제로 돈다.
    """
    import os
    import shutil
    import subprocess

    assert _HARNESS.exists(), "행위 하네스 파일 부재"
    node = shutil.which("node")
    if node:
        proc = subprocess.run(
            [node, str(_HARNESS)], cwd=str(_HARNESS.parent),
            capture_output=True, text=True, timeout=600,
            env={**os.environ, "NODE_OPTIONS": ""},
        )
        if proc.returncode != 2:      # 2 = jsdom 미설치 → 아래 gap 경로로 강등
            assert proc.returncode == 0, (
                f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
            )
            return
    docs = Path(__file__).resolve().parents[1] / "docs"
    recorded = any(
        _CI_GAP_MARKER in p.read_text(encoding="utf-8")
        for p in [docs / "REVIEW.md", *sorted((docs / "test-runs.d").glob("*.md"))]
        if p.exists()
    )
    assert recorded, (
        "행위 하네스를 실행할 수 없는데(node/jsdom 부재) 그 gap 이 문서에 없다. "
        f'REVIEW.md 또는 test-runs.d fragment 에 "{_CI_GAP_MARKER}" 를 기록하라'
    )
