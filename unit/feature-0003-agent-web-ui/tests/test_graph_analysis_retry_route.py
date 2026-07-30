"""analysis-retry-resilience — 실패 잡 회수 엔드포인트 계약(feature-0016, 2026-07-30).

`POST /api/admin/metadata/graph/analyze/retry` 는 LLM 재호출을 유발하는 특권 동작이라:
  · 권한은 실행 권한 `metadata.graph.analyze` 재사용(조회 권한 `metadata.graph.read` 로는 불가)
  · `run_id` 또는 `scope_key` 중 최소 하나 필수 — 무제한 전역 회수는 비용이 예측 불가
  · dry_run 은 감사 기록을 남기지 않고(변경 0), 실제 회수만 감사에 남는다
  · 모듈 실패(PG 미가용·마이그레이션 미적용)는 503 으로 표면화(조용한 200 금지)

라우터 계약만 검증한다 — 회수 SQL 자체는 feature-0002 `test_node_analysis_retry.py` 가 담당.

**격리 주의(전 스위트 실행에서 실패했던 두 지점)**:
  ① 모듈 스텁을 `sys.modules` 에 넣지 않는다 — 핸들러가 `from modules import node_analysis` 로
     받는 값은 이미 import 된 `modules` 패키지의 **속성**이라, 다른 테스트가 먼저 import 한
     뒤에는 sys.modules 치환이 무시된다. 실제 모듈의 함수만 monkeypatch 한다.
  ② `asyncio.get_event_loop()` 를 쓰지 않는다 — 앞선 테스트가 루프를 닫아두면 재사용에 실패한다.
     매 호출 `asyncio.run()` 으로 새 루프를 쓴다.
"""
import asyncio
import json

from modules import node_analysis as na
from routers import admin_metadata as am


class _Req:
    """핸들러가 body 를 `_metadata_read_json` 으로만 읽으므로 최소 스텁."""


async def _async(v):
    return v


def _invoke(monkeypatch, body, *, retry_result=None, audit_sink=None):
    calls = []

    def _fake_retry(run_id=None, scope_key=None, limit=500, dry_run=False):
        calls.append({"run_id": run_id, "scope_key": scope_key, "limit": limit, "dry_run": dry_run})
        if retry_result is not None:
            return retry_result
        return {"ok": True, "dry_run": dry_run, "retried": 43, "runs": 1, "run_ids": ["r1"]}

    monkeypatch.setattr(am, "_metadata_read_json", lambda request: _async(body))
    monkeypatch.setattr(am, "_metadata_audit",
                        lambda *a, **k: (audit_sink.append(k) if audit_sink is not None else None))
    monkeypatch.setattr(na, "retry_failed_jobs", _fake_retry)
    resp = asyncio.run(am.admin_metadata_graph_analyze_retry(_Req(), account={"username": "op"}))
    return resp, calls


def _body_of(resp):
    return json.loads(bytes(resp.body).decode("utf-8"))


def test_requires_run_id_or_scope(monkeypatch):
    """무제한 전역 회수 차단 — 대상 미지정은 400이며 회수 함수를 호출하지 않는다."""
    resp, calls = _invoke(monkeypatch, {})
    assert resp.status_code == 400
    assert "run_id" in str(_body_of(resp))
    assert calls == []


def test_passes_run_id_and_limit(monkeypatch):
    resp, calls = _invoke(monkeypatch, {"run_id": "abc", "limit": 200})
    assert resp.status_code == 200
    assert calls == [{"run_id": "abc", "scope_key": None, "limit": 200, "dry_run": False}]
    assert _body_of(resp)["retried"] == 43


def test_scope_is_lowercased(monkeypatch):
    _resp, calls = _invoke(monkeypatch, {"scope_key": "MySQL-Prod"})
    assert calls[0]["scope_key"] == "mysql-prod"


def test_invalid_limit_falls_back(monkeypatch):
    """limit 이 숫자가 아니어도 500(기본)으로 진행 — 입력 오류가 회수를 막지 않는다."""
    _resp, calls = _invoke(monkeypatch, {"run_id": "abc", "limit": "많이"})
    assert calls[0]["limit"] == 500


def test_dry_run_does_not_audit(monkeypatch):
    sink = []
    resp, calls = _invoke(monkeypatch, {"run_id": "abc", "dry_run": True}, audit_sink=sink)
    assert calls[0]["dry_run"] is True
    assert _body_of(resp)["dry_run"] is True
    assert sink == [], "dry_run 은 아무것도 바꾸지 않으므로 감사 기록 대상이 아니다"


def test_actual_retry_is_audited(monkeypatch):
    sink = []
    _resp, _calls = _invoke(monkeypatch, {"run_id": "abc"}, audit_sink=sink)
    assert sink and sink[0].get("action") == "node_analysis.retry_failed"
    assert sink[0]["change_json"]["retried"] == 43


def test_zero_retried_is_not_audited(monkeypatch):
    """회수 0건은 상태 변화가 없으므로 감사 노이즈를 만들지 않는다."""
    sink = []
    resp, _calls = _invoke(monkeypatch, {"scope_key": "ds"},
                           retry_result={"ok": True, "dry_run": False, "retried": 0, "runs": 0},
                           audit_sink=sink)
    assert resp.status_code == 200 and _body_of(resp)["retried"] == 0
    assert sink == []


def test_module_failure_is_503(monkeypatch):
    resp, _calls = _invoke(
        monkeypatch, {"run_id": "abc"},
        retry_result={"ok": False, "reason": "재시도 계정(alembic 0049) 미적용 — 배포 후 다시 시도"})
    assert resp.status_code == 503
    assert "0049" in str(_body_of(resp))


def test_route_uses_execute_permission():
    """조회 권한으로 LLM 재호출을 열지 않는다(권한 승격 회귀 가드)."""
    import inspect
    src = inspect.getsource(am.admin_metadata_graph_analyze_retry)
    assert "metadata.graph.analyze" in src
    assert "metadata.graph.read" not in src
