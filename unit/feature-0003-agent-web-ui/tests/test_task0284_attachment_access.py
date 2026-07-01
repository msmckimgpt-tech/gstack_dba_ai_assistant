"""TASK-0284 — 첨부 접근/다운로드 회귀 테스트.

이슈1: LLM 컨텍스트 주입 스코프를 AccountId → ConversationId 로 통일(대화 접근권은 ask 핸들러가
       게이트). 목록 조회·다운로드가 이미 대화 단위인데 주입만 계정 단위라, fork·이어받기 등
       cross-account 시 목록엔 보이나 LLM 주입이 0행이던 불일치를 해소.
이슈2: 외부 머신 다운로드 — MinIO presigned(내부 호스트) 대신 web 프록시 라우트
       /api/attachments/{id}/download.
이슈3(파일명 우선)은 agent_core 측 — feature-0002 test_attachment_idor.py 에서 검증.

라이브 PG 라운드트립이 별도 게이트이며, 본 테스트는 fake-cursor/정적 검증으로 잡히는 면
(스코프 SQL 불변식·시그니처 계약·라우트 보안 속성)을 회귀 차단한다.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import app

_SRC = Path(__file__).resolve().parent.parent / "src"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


apm = _load(_SRC / "modules" / "attachment_pg_mirror.py", "_t0284_apm")


# ── 이슈1: pg_mirror 주입 스코프 (conversation 우선, account 폴백) ──


def test_attach_scope_clause_prefers_conversation():
    assert apm._attach_scope_clause("conv-1", 7) == ("conversation_id = %s", "conv-1")
    assert apm._attach_scope_clause(None, 7) == ("account_id = %s", 7)
    assert apm._attach_scope_clause("", 7) == ("account_id = %s", 7)   # 빈 conv → account 폴백
    assert apm._attach_scope_clause(None, None) is None               # 둘 다 없음 → None(fail-closed)
    assert apm._attach_scope_clause("", 0) is None


def _capture_pg(monkeypatch):
    captured: dict = {}

    class _Cur:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Pg:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    monkeypatch.setattr(apm, "_pg", lambda: _Pg())
    monkeypatch.setattr(apm, "_dict_cursor", lambda pg: _Cur())
    return captured


def test_pg_select_text_inline_conversation_scope(monkeypatch):
    captured = _capture_pg(monkeypatch)
    apm.pg_select_text_inline("conv-1", 7, [10, 20], 5)
    assert "conversation_id = %s" in captured["sql"], "ConversationId 스코프 누락"
    assert "account_id = %s" not in captured["sql"], "conversation 스코프 시 account 필터가 남으면 cross-account 차단됨"
    assert "conv-1" in tuple(captured["params"])


def test_pg_select_vision_images_conversation_scope(monkeypatch):
    captured = _capture_pg(monkeypatch)
    apm.pg_select_vision_images("conv-2", 7, [10], 4)
    assert "conversation_id = %s" in captured["sql"] and "conv-2" in tuple(captured["params"])
    assert "account_id = %s" not in captured["sql"]


def test_pg_select_ingested_meta_conversation_scope(monkeypatch):
    captured = _capture_pg(monkeypatch)
    apm.pg_select_ingested_meta("conv-3", 7, [10])
    assert "conversation_id = %s" in captured["sql"] and "conv-3" in tuple(captured["params"])
    assert "account_id = %s" not in captured["sql"]


def test_pg_select_account_fallback_without_conversation(monkeypatch):
    """conversation_id 미전달 시 account_id 폴백(하위호환)."""
    captured = _capture_pg(monkeypatch)
    apm.pg_select_text_inline(None, 7, [10], 5)
    assert "account_id = %s" in captured["sql"] and 7 in tuple(captured["params"])


# ── 이슈2: web 프록시 다운로드 라우트 ──


def test_download_route_registered():
    """프록시 다운로드 라우트가 FastAPI 앱에 등록되어 있다."""
    # feature-0012 P5b: include_router 로 중첩된 라우트까지 재귀 수집(Starlette _IncludedRouter).
    def _paths(routes):
        out = set()
        for r in routes:
            p = getattr(r, "path", None)
            sub = getattr(r, "routes", None) or getattr(getattr(r, "original_router", None), "routes", None)
            if p is None and sub:
                out |= _paths(sub)
            elif p is not None:
                out.add(p)
        return out
    paths = _paths(app.app.routes)
    assert "/api/attachments/{attachment_id}/download" in paths


def test_download_route_security_contract():
    """라우트 본문이 권한 게이트 + pending 차단 + octet-stream + attachment disposition + nosniff 를 갖춘다."""
    # feature-0012 P5b: download_attachment 은 routers/attachments.py 로 추출됨(@router 데코레이터).
    src = (_SRC / "routers" / "attachments.py").read_text(encoding="utf-8")
    m = re.search(r"def download_attachment\(.*?\n(.*?)\n@router\.", src, re.S)
    assert m, "download_attachment 함수 추출 실패"
    body = m.group(1)
    assert "_account_can_access_attachment" in body, "권한 게이트 누락 (IDOR)"
    assert "_account_is_pending" in body, "pending 계정 차단 누락 (D21)"
    assert "application/octet-stream" in body, "octet-stream 강제 누락 (inline 렌더/XSS 방지)"
    assert "attachment;" in body, "Content-Disposition attachment 누락"
    assert "nosniff" in body, "X-Content-Type-Options nosniff 누락"
