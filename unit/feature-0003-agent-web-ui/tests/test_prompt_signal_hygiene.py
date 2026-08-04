"""FR-prompt-autogen-wiring — 시스템 프롬프트 자동작성의 접지 신호 위생 + 실패 관측 회귀 가드.

배경(라이브 실측 2026-08-04): 개인(account)·역할(role) 스코프 자동작성은 요약 축이 배선 단절로
비어 있어(FR-summary-writer-disconnected) **대화 topic 이 유일한 접지원**이다. 그런데 topic 원본은
잡음이 크다 — 계정 4 기준 40건 중 placeholder `새 대화` 3 · 동일 제목 중복 3 · 인사말 3 ·
첫 메시지 raw 절단(개행 포함) 2 = 11건(27.5%). 이 상태로 "사용자가 실제로 요청한 주제" 라며
LLM 에 주면 생성 프롬프트가 잡음을 관심사로 오인한다.

검증:
  T1  `_normalize_signal_topics`: placeholder(`새 대화`/`(미설정)`) 제거.
  T2  인사·의례 제목 제거 — 단, **완전일치만**(실제 요청을 삼키면 안 된다).
  T3  중복 제거(대소문자·끝 구두점 무시) + 최신순 보존.
  T4  raw 절단본의 개행/연속공백 정규화 + 표시 상한 적용.
  T5  limit 준수 / 빈 입력 안전.
  T6  `_collect_conversation_signals_pg` 가 정제기를 통과시킨다 + 원본은 limit 의 3배 창을 읽는다.
  T7  자동작성 JSON 경로의 LLM 실패가 서버 로그에 남는다(종전엔 클라이언트에만 전달).

`make test`(agent 이미지, --no-deps)에서 DB·LLM 없이 fake/monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import logging

import app


# ── T1~T5 _normalize_signal_topics ──────────────────────────────────────────────

def test_normalize_drops_placeholders():
    out = app._normalize_signal_topics(
        ["새 대화", "(미설정)", "미설정", "접속 로그 집계", "New Chat"], limit=10,
    )
    assert out == ["접속 로그 집계"]


def test_normalize_drops_greetings_exact_match_only():
    out = app._normalize_signal_topics(
        ["안녕하세요", "반갑습니다", "안녕?", "테스트", "안녕하세요, 접속 로그 좀 봐주세요"],
        limit=10,
    )
    # 의례적 인사 단독은 제거, 실제 요청이 붙은 문장은 보존(부분일치로 넓히지 않는다).
    assert out == ["안녕하세요, 접속 로그 좀 봐주세요"]


def test_normalize_dedupes_case_and_trailing_punct():
    out = app._normalize_signal_topics(
        [
            "당신의 역할을 알려주세요.",
            "당신의 역할을 알려주세요",
            "당신의 역할을 알려주세요!",
            "아이템 매출 집계",
        ],
        limit=10,
    )
    assert out == ["당신의 역할을 알려주세요.", "아이템 매출 집계"]  # 최신순(입력 순서) 보존


def test_normalize_collapses_raw_message_slice():
    raw = "쿼리 리뷰를 진행해주세요.  \n- 기존 DB에 해당 쿼리를 적"
    out = app._normalize_signal_topics([raw], limit=5)
    assert out == ["쿼리 리뷰를 진행해주세요. - 기존 DB에 해당 쿼리를 적"]
    assert "\n" not in out[0]


def test_normalize_caps_display_length():
    long_topic = "가" * 300
    out = app._normalize_signal_topics([long_topic], limit=5)
    assert len(out) == 1
    assert len(out[0]) == app._SIGNAL_TOPIC_MAX_LEN + 1  # 상한 + 말줄임표
    assert out[0].endswith("…")


def test_normalize_limit_and_empty():
    out = app._normalize_signal_topics(["주제A", "주제B", "주제C"], limit=2)
    assert out == ["주제A", "주제B"]
    assert app._normalize_signal_topics([], limit=5) == []
    assert app._normalize_signal_topics(None, limit=5) == []
    assert app._normalize_signal_topics(["", "   ", None], limit=5) == []
    # 상한 0 = "신호 없음". append-후-검사 루프라 가드가 없으면 1건이 새어 나간다.
    assert app._normalize_signal_topics(["주제A", "주제B"], limit=0) == []


def test_normalize_dedupes_on_truncated_display():
    """중복 판정은 **출력될 문자열** 기준 (codex P2).

    원문 전체로 판정하면 앞 120자가 같은 긴 제목들이 서로 다른 키를 받아 통과한 뒤,
    화면·프롬프트에는 똑같은 절단 문자열로 N번 나타나 limit 을 잠식한다.
    """
    prefix = "게임 로그 데이터에서 스테이지별 성공률과 이탈 지점을 집계해 주세요 " * 5
    assert len(prefix) > app._SIGNAL_TOPIC_MAX_LEN  # 분기점이 절단선 뒤에 오도록
    a, b = prefix + "그리고 A 도", prefix + "그리고 B 도"
    assert a != b
    out = app._normalize_signal_topics([a, b, "다른 주제"], limit=10)
    assert len(out) == 2, f"절단 후 동일한 두 제목은 1건으로 합쳐져야 한다: {out}"
    assert out[1] == "다른 주제"


def test_normalize_keeps_short_korean_topics():
    """길이 게이트가 짧지만 유효한 한국어 제목을 삼키지 않는다(backstop 일 뿐).

    임계를 넉넉히 잡았다가 "매출"·"접속 로그" 같은 실제 관심사가 통째로 사라진 회귀를 고정.
    """
    out = app._normalize_signal_topics(["매출", "접속 로그", "가", " "], limit=10)
    assert out == ["매출", "접속 로그"]


# ── T6 _collect_conversation_signals_pg 가 정제기를 통과시킨다 ─────────────────

class _NoisyPgCursor:
    def __init__(self, rec):
        self._rec = rec
        self._q = 0

    def execute(self, sql, params=None):
        self._rec.append((" ".join(sql.split()), list(params or ())))
        self._q += 1

    def fetchall(self):
        if self._q == 1:
            return [("새 대화",), ("접속 로그 집계",), ("접속 로그 집계",), ("안녕하세요",), ("매출 추이",)]
        return [("요약1",)]

    def close(self):
        return None


class _NoisyPgConn:
    def __init__(self, rec):
        self._rec = rec

    def cursor(self):
        return _NoisyPgCursor(self._rec)

    def close(self):
        return None


def test_collect_signals_applies_topic_hygiene(monkeypatch):
    rec: list = []
    monkeypatch.setattr("shared.db._pg_connect", lambda: _NoisyPgConn(rec))
    topics, summaries = app._collect_conversation_signals_pg(account_ids=[1], topic_limit=10)
    assert topics == ["접속 로그 집계", "매출 추이"]   # placeholder·인사·중복 제거
    assert summaries == ["요약1"]
    # 정제로 줄어들 몫을 감안해 원본은 limit 의 3배 창에서 읽는다.
    _, topic_params = rec[0]
    assert topic_params[-1] == 30


# ── T7 자동작성 실패 서버 로깅 ─────────────────────────────────────────────────

class _BoomClient:
    class _Completions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("gateway 503")

    class _Chat:
        completions = None

    def __init__(self):
        self.chat = _BoomClient._Chat()
        self.chat.completions = _BoomClient._Completions()


def test_prompt_generate_json_logs_llm_failure(monkeypatch, caplog):
    ctx = {
        "openai_client": _BoomClient(),
        "create_kwargs": {"model": "m", "messages": []},
        "llm_model": "m",
        "max_tokens": 100,
        "meta_base": {},
    }
    monkeypatch.setattr(app, "_json_error", lambda msg, code: {"error": msg, "code": code})
    with caplog.at_level(logging.WARNING):
        out = asyncio.run(
            app._prompt_generate_json_response(ctx, log_label="test_gen", log_ctx="role_id=3")
        )
    assert out["code"] == 502
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "test_gen" in joined and "LLM 생성 실패" in joined and "role_id=3" in joined


# ── T8 역할 삭제 시 role-scope 프롬프트 동반 정리 ───────────────────────────────

class _SqlRecordingCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        self._store.setdefault("sql", []).append((" ".join(sql.split()), list(params or ())))

    def fetchone(self):
        return (self._store.get("in_use", 0),)

    def close(self):
        return None


class _SqlRecordingConn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        return _SqlRecordingCursor(self._store)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def test_role_delete_cleans_role_scope_prompts(client, as_account, monkeypatch):
    """역할 삭제가 그 역할의 시스템 프롬프트를 함께 지운다 — 고아행 재발 방지.

    제품 삭제 경로는 이미 `DELETE FROM WebSystemPrompts WHERE ProductId = %s` 를 수행하는데
    역할 경로에만 이 정리가 빠져 있었다(라이브 실측 고아 2건: RoleId 16·30). 관리 콘솔에서
    보이지 않는 행이라 사후 회수 수단도 없었다.
    """
    store: dict = {"in_use": 0}

    def _gen():
        yield _SqlRecordingConn(store)

    app.app.dependency_overrides[app.get_conn] = _gen
    as_account(perms={"console.access": True, "console.manage": True, "role.delete": True})
    monkeypatch.setattr(app, "_load_role_by_id", lambda *a, **k: {"is_default_signup": False})
    monkeypatch.setattr(app, "_audit_admin_mutation", lambda *a, **k: None)

    r = client.delete("/api/admin/roles/7")
    assert r.status_code == 200

    statements = [s for s, _ in store.get("sql", [])]
    assert any(
        "DELETE FROM WebSystemPrompts WHERE RoleId" in s for s in statements
    ), f"역할 삭제가 role-scope 프롬프트를 정리해야 한다: {statements}"
    # 프롬프트 정리는 역할 행 삭제보다 **먼저** — 순서가 뒤집혀도 결과는 같지만, 같은 트랜잭션
    # 안에서 참조 정리를 앞세우는 기존 관례(WebRolePermissions)와 정합을 유지한다.
    idx_prompt = next(i for i, s in enumerate(statements) if "WebSystemPrompts" in s)
    idx_role = next(i for i, s in enumerate(statements) if "DELETE FROM WebRoles" in s)
    assert idx_prompt < idx_role
