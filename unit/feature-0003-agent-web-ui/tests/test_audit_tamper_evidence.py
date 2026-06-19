"""TASK-20260619T023922-audit-tamper-evidence (Critical §12.3) — 감사 로그 변조방지(해시 체인) 회귀 테스트.

요청(보안 보강 6종 중 ③): 감사 기록 변조방지. 기존 WebAuditEvents 는 append-only 의도였으나
변조(수정/삭제/삽입/재정렬) 탐지 수단이 없었음. EventHash=SHA256(PrevHash|정규화행) 해시 체인 도입.

검증(`make test` agent 이미지, DB 없이 — 해시/정규화는 순수 함수 실 동작, 나머지 inspect.getsource):
  B1  _audit_compute_hash/_canonical: 결정성 + 내용변조 탐지 + prev 민감(재정렬/삽입/삭제 탐지).
  B2  체인 일관성 + 변조 시 재계산 불일치(walk 검증 모사).
  B3  schema 헬퍼: EventHash/PrevHash ALTER + Checkpoint 테이블 + 양 경로 호출.
  B4  _seal_audit_chain: GET_LOCK 직렬 + Id ASC 일괄 + 멱등(EventHash IS NULL).
  B5  record_audit_event: INSERT 후 동기 _seal_audit_chain 훅.
  B6  verify 엔드포인트: audit.read.any + 재계산 + first_break + checkpoint 재앵커.
  B7  purge: 삭제 전 seal + 경계 EventHash 를 Checkpoint INSERT.
  B8  백그라운드 sealer 루프(AGENT_AUDIT_SEAL_SEC).
  F1  admin.js: 무결성 검증 버튼 + triggerAuditChainVerify + admin.html 버튼.
"""
from __future__ import annotations

import inspect
import os
import sys


def _import_app():
    try:
        import app  # type: ignore
        return app
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        try:
            import app  # type: ignore
            return app
        except ModuleNotFoundError:
            import web.app as app  # type: ignore
            return app


app = _import_app()


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


def _row(rid: int, action: str = "admin.account.update", change: str = '{"role_id": 2}') -> dict:
    return {
        "Id": rid, "ActorAccountId": 5, "ActorRoleId": 1, "ActorType": "account",
        "TargetAccountId": 9, "SessionId": "sess", "ActionCode": action,
        "ResourceType": "account", "ResourceId": str(rid), "ChangeJson": change,
        "MaskedFields": None, "RemoteAddr": "10.0.0.1", "UserAgent": "ua", "RequestId": "req",
        "OccurredAt": None,
    }


# ── B: hash core (pure, real behavior) ──────────────────────────────────────
def test_b1_hash_determinism_and_tamper_detection():
    r = _row(1)
    c = app._audit_canonical_string(r)
    h = app._audit_compute_hash("", c)
    assert isinstance(h, str) and len(h) == 64
    # 결정성
    assert app._audit_compute_hash("", c) == h
    # 내용 변조 탐지: 한 필드만 바꿔도 해시 변화
    r2 = _row(1, action="admin.account.delete")
    assert app._audit_compute_hash("", app._audit_canonical_string(r2)) != h
    # ChangeJson 변조 탐지
    r3 = _row(1, change='{"role_id": 99}')
    assert app._audit_compute_hash("", app._audit_canonical_string(r3)) != h
    # prev 민감(재정렬/삽입/삭제 탐지): 같은 내용도 prev 가 다르면 해시 다름
    assert app._audit_compute_hash(h, c) != app._audit_compute_hash("", c)


def test_b2_chain_consistency_and_break_detection():
    rows = [_row(i, action=f"act{i}") for i in (1, 2, 3)]
    prev = ""
    chain = []
    for r in rows:
        eh = app._audit_compute_hash(prev, app._audit_canonical_string(r))
        chain.append((r, prev, eh))
        prev = eh
    # 정상 walk: 각 행 PrevHash==직전 EventHash + 재계산 일치
    p = ""
    for (r, sp, eh) in chain:
        assert sp == p
        assert app._audit_compute_hash(sp, app._audit_canonical_string(r)) == eh
        p = eh
    # 중간 행(2) 내용 변조 → 재계산이 저장 해시와 불일치(탐지)
    tampered = _row(2, action="tampered")
    assert app._audit_compute_hash(chain[1][1], app._audit_canonical_string(tampered)) != chain[1][2]


def test_b2b_canonical_field_ordering_and_none():
    r = _row(1)
    c = app._audit_canonical_string(r)
    # 필드 구분자(unit separator) 사용 + None→빈문자열
    assert "\x1f" in c
    r_none = dict(r); r_none["SessionId"] = None
    assert app._audit_canonical_string(r_none) != c  # None 처리가 값과 구분됨


# ── B: backend source ───────────────────────────────────────────────────────
def test_b3_schema_helper():
    src = inspect.getsource(app._ensure_web_audit_chain_schema)
    assert "ADD COLUMN EventHash CHAR(64)" in src
    assert "ADD COLUMN PrevHash CHAR(64)" in src
    assert "WebAuditChainCheckpoint" in src
    assert "except Exception" in src  # 멱등
    seed = inspect.getsource(app._ensure_seed_catchup)
    assert "_ensure_web_audit_chain_schema(conn)" in seed


def test_b4_seal_function():
    src = inspect.getsource(app._seal_audit_chain)
    assert "GET_LOCK" in src and "RELEASE_LOCK" in src      # 직렬화
    assert "EventHash IS NULL" in src                        # 미봉인만
    assert "ORDER BY Id ASC" in src                          # Id 순(fork 방지)
    assert "UPDATE WebAuditEvents SET EventHash" in src


def test_b5_record_event_seal_hook():
    src = inspect.getsource(app.record_audit_event)
    # INSERT 후 동기 봉인 — outside-voice MAJOR-1 흡수: caller conn 이 아닌 fresh autocommit 연결.
    assert "_seal_audit_chain(_seal_conn)" in src
    assert "_connect_memory()" in src


def test_b5b_seal_update_guard_and_drain():
    # MAJOR-1: UPDATE 가 EventHash IS NULL 가드(double-seal/fork 차단).
    seal_src = inspect.getsource(app._seal_audit_chain)
    assert "WHERE Id = %s AND EventHash IS NULL" in seal_src
    # MAJOR-4: verify/purge 는 batch bound drain 사용(거대 batch=1000000 제거).
    assert hasattr(app, "_seal_audit_chain_drain")
    vsrc = inspect.getsource(app.verify_audit_chain)
    assert "_seal_audit_chain_drain(conn)" in vsrc
    assert "batch=1000000" not in vsrc


def test_b6_verify_endpoint():
    assert hasattr(app, "verify_audit_chain")
    src = inspect.getsource(app.verify_audit_chain)
    assert "audit.read.any" in src                           # 권한
    assert "_seal_audit_chain" in src                        # 검증 전 catch-up
    assert "_audit_compute_hash" in src                      # 재계산
    assert "first_break" in src
    assert "WebAuditChainCheckpoint" in src                  # purge 재앵커
    assert "prev_hash_mismatch" in src and "content_modified" in src


def test_b7_purge_checkpoint():
    src = inspect.getsource(app.purge_audit_events)
    assert "_seal_audit_chain" in src                        # 삭제 전 봉인
    assert "INSERT INTO WebAuditChainCheckpoint" in src      # 경계 재앵커
    assert "OccurredAt < %s AND EventHash IS NOT NULL" in src


def test_b8_background_sealer():
    src = inspect.getsource(app._start_audit_seal_loop)
    assert "AGENT_AUDIT_SEAL_SEC" in src
    assert "_seal_audit_chain" in src


# ── F: frontend ─────────────────────────────────────────────────────────────
def test_f1_admin_verify_ui():
    js = _read_static("admin.js")
    assert "triggerAuditChainVerify" in js
    assert "/api/admin/audits/verify" in js
    assert "auditVerifyBtn" in js
    assert 'permissions?.["audit.read.any"]' in js
    html = _read_static("admin.html")
    assert 'id="auditVerifyBtn"' in html
