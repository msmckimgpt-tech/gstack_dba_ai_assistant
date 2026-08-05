"""msg-speaker-attribution — 발화자 귀속의 **보정(backfill)** 과 렌더 정합 회귀 (web 측).

배경(사용자 보고): "대화를 fork 하거나 product 를 바꿈으로써 이전에 진행했던 대화의 발화자가
실시간으로 변경되어 버리는 부정합". 원인은 발화자가 메시지에 각인되지 않고 렌더 시점의 대화
설정(현재 owner / 현재 제품 칩)에서 파생된 것. 각인 도입 **이전에 쌓인 행**은 귀속이 바뀌는
바로 그 순간(제품 전환 · fork) 에 마지막으로 알 수 있는 값으로 고정해야 한다.

검증:
  B1  `_conv_product_attribution` — pinned/auto 각인 스키마가 agent_core 각인과 동일 키.
  B2  `_conv_backfill_attribution` — **미각인 행에만** 기입, 각인된 행은 불변, inferred 표기.
  B3  `_conv_copy_messages(attribution_defaults=…)` — fork 복사 시 미각인 행만 원본 기준 고정.
  B4  fork 는 **강등 전** source 제품을 각인한다(접근권 없어 auto 로 강등된 fork 바인딩 아님).
  B5  FE renderMessages 가 assistant 발화자를 컴포저 제품 칩에서 파생하지 않는다(구조 고정).
"""
from __future__ import annotations

import json
import os
import re

import app as appmod
from routers import _conv_store


# ── fake DB ──────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows: list = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        if "WebProducts" in sql:
            self._rows = [self._conn.product_row] if self._conn.product_row else []
        elif "SELECT Id, MetaJson FROM AgentMemoryMessages" in sql:
            self._rows = [
                (mid, raw) for mid, role, raw in self._conn.messages
                if role == (params[1] if params else None)
            ]
        elif sql.strip().startswith("UPDATE AgentMemoryMessages"):
            # 낙관적 동시성 — (meta_out, id, raw_expected). raw 가 안 맞으면 rowcount 0.
            meta_out, mid, raw_expected = params
            current = next((r for r in self._conn.messages if r[0] == int(mid)), None)
            if current is not None and current[2] == raw_expected:
                self._conn.updated[int(mid)] = json.loads(meta_out)
                self.rowcount = 1
            else:
                self.rowcount = 0
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Conn:
    def __init__(self, product_row=None, messages=None):
        self.product_row = product_row
        self.messages = messages or []   # [(id, role, meta_json_str|None)]
        self.updated: dict[int, dict] = {}
        self.executed: list = []
        self.inserted: list = []

    def cursor(self, dictionary=False):
        return _Cursor(self)


class _WriterCursor:
    """_conv_copy_messages 의 MySQL 쓰기 커서(INSERT 만 사용)."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.inserted.append(params)

    def close(self):
        pass


# ── B1: 각인 스키마 ──────────────────────────────────────────────────────────

def test_product_attribution_pinned_and_auto(monkeypatch):
    conn = _Conn(product_row=("KR_LIVE", "킹스레이드 라이브"))
    pinned = _conv_store._conv_product_attribution(conn, 7, "pinned")
    assert pinned == {
        "product_mode": "pinned",
        "product_id": 7,
        "product_key": "KR_LIVE",
        "product_name": "킹스레이드 라이브",
    }
    # auto 는 제품을 만들어내지 않는다 — "제품 미고정" 그 자체가 발화자 사실.
    assert _conv_store._conv_product_attribution(conn, 7, "auto") == {"product_mode": "auto"}
    assert _conv_store._conv_product_attribution(conn, None, "pinned") == {"product_mode": "pinned"}


def test_product_attribution_matches_agent_core_schema():
    """각인 키가 갈리면 FE 가 두 생산자를 구분해야 하고 폴백이 되살아난다 — 키 집합을 고정."""
    src_path = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "feature-0002-agent-core", "src", "agent_core.py",
    )
    with open(src_path, encoding="utf-8") as fh:
        core_src = fh.read()
    body = core_src[core_src.index("def _answer_product_attribution"):]
    body = body[:body.index("\ndef ", 10)]
    for key in ("product_mode", "product_id", "product_key", "product_name"):
        assert f'"{key}"' in body, f"agent_core 각인에 {key} 없음"


# ── B2: freeze-on-change backfill ────────────────────────────────────────────

def test_backfill_only_touches_unstamped_rows(monkeypatch):
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    conn = _Conn(messages=[
        (1, "assistant", None),                                   # 미각인 → 보정 대상
        (2, "assistant", json.dumps({"duration_ms": 12})),         # 미각인(다른 키만) → 대상
        (3, "assistant", json.dumps({"product_mode": "auto"})),    # 이미 각인 → 불변
    ])
    written = _conv_store._conv_backfill_attribution(
        conn, "c1", "assistant", {"product_mode": "pinned", "product_id": 7, "product_key": "KR"},
    )
    assert written == 2
    assert set(conn.updated) == {1, 2}
    assert conn.updated[1]["product_id"] == 7
    # 추론으로 채운 행은 발화 시점 각인과 구분된다.
    assert conn.updated[1]["attribution_inferred"] is True
    # 기존 meta 키는 보존된다(추가만).
    assert conn.updated[2]["duration_ms"] == 12
    assert 3 not in conn.updated


def test_backfill_noop_on_unknown_role_or_empty_attribution(monkeypatch):
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    conn = _Conn(messages=[(1, "assistant", None)])
    assert _conv_store._conv_backfill_attribution(conn, "c1", "tool", {"product_mode": "auto"}) == 0
    assert _conv_store._conv_backfill_attribution(conn, "c1", "assistant", {}) == 0
    assert conn.updated == {}


def test_backfill_never_overwrites_existing_keys(monkeypatch):
    """부분 각인 행(probe 는 없는데 다른 귀속 키는 있는 경우) — 보정은 **없는 키만** 채운다.

    §18.8 codex P1: 종전 `meta.update(payload)` / jsonb `existing || payload` 는 payload 우선이라
    이미 있던 product_id·sender_username 을 덮었다. 보정은 추가만 해야 한다.
    """
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    conn = _Conn(messages=[
        (1, "assistant", json.dumps({"product_id": 42, "product_name": "원래 제품"})),
    ])
    assert _conv_store._conv_backfill_attribution(
        conn, "c1", "assistant",
        {"product_mode": "pinned", "product_id": 7, "product_key": "NEW", "product_name": "새 제품"},
    ) == 1
    row = conn.updated[1]
    assert row["product_id"] == 42          # 기존 값 보존
    assert row["product_name"] == "원래 제품"  # 기존 값 보존
    assert row["product_mode"] == "pinned"  # 없던 키만 채움
    assert row["product_key"] == "NEW"


def test_backfill_skips_unparseable_meta_instead_of_erasing(monkeypatch):
    """파싱 불가 meta 행은 건너뛴다 — {} 폴백 후 되쓰면 원문 meta 가 통째로 사라진다.

    §18.8 codex P1(데이터 손실). 귀속 보정이 판독 못한 데이터를 지우는 경로를 봉인한다.
    """
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    conn = _Conn(messages=[
        (1, "assistant", "{broken json"),
        (2, "assistant", json.dumps(["not", "a", "dict"])),
        (3, "assistant", None),            # 진짜 빈 meta → 보정 대상
        (4, "assistant", "   "),           # 공백 → 빈 meta 취급
    ])
    written = _conv_store._conv_backfill_attribution(
        conn, "c1", "assistant", {"product_mode": "auto"},
    )
    assert written == 2
    assert set(conn.updated) == {3, 4}     # 1·2 는 손대지 않는다


def test_backfill_mysql_update_is_guarded_by_read_value(monkeypatch):
    """SELECT~UPDATE 사이에 다른 경로가 각인하면 덮지 않는다(낙관적 동시성)."""
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    conn = _Conn(messages=[(1, "assistant", None)])

    real_cursor = conn.cursor

    def racing_cursor(dictionary=False):
        cur = real_cursor(dictionary)
        # SELECT 직후 다른 세션이 각인한 상황을 재현 — raw 값이 달라진다.
        if conn.messages[0][2] is None and conn.executed:
            conn.messages[0] = (1, "assistant", json.dumps({"product_mode": "pinned"}))
        return cur

    conn.cursor = racing_cursor  # type: ignore[assignment]
    assert _conv_store._conv_backfill_attribution(
        conn, "c1", "assistant", {"product_mode": "auto"},
    ) == 0
    assert conn.updated == {}


def test_backfill_pg_update_targets_missing_probe_key(monkeypatch):
    """PG 경로는 set-based UPDATE — probe key 부재 술어와 jsonb 병합 방향을 문자열로 고정한다.

    `meta_json || payload` 는 우측 우선이라 기존 키를 지우지 않고, `(meta_json -> probe) IS NULL`
    이 이미 각인된 행을 제외한다. 이 두 성질이 깨지면 각인이 덮이거나 미각인 행이 남는다.
    """
    src_path = os.path.join(os.path.dirname(__file__), "..", "src", "routers", "_conv_store.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def _conv_backfill_attribution"):]
    body = body[:body.index("\ndef ", 10)]
    # payload 가 **좌측** — jsonb `||` 는 우측 우선이므로 기존 meta 가 이긴다(없는 키만 채움).
    assert "%s::jsonb || COALESCE(meta_json, '{}'::jsonb)" in body
    assert "(meta_json -> %s) IS NULL" in body


# ── B3/B4: fork 복사 시 원본 기준 고정 ───────────────────────────────────────

def test_copy_messages_stamps_only_unstamped(monkeypatch):
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    monkeypatch.setattr(appmod, "_is_internal_message", lambda r, c, m: False)
    conn = _Conn()
    monkeypatch.setattr(_conv_store, "_conv_copy_messages", _conv_store._conv_copy_messages)
    conn.cursor = lambda dictionary=False: _WriterCursor(conn)  # type: ignore[assignment]

    src_rows = [
        (10, "user", "q1", "2026-08-01", None),                                   # 미각인 user
        (11, "assistant", "a1", "2026-08-01", json.dumps({"duration_ms": 5})),    # 미각인 assistant
        (12, "user", "q2", "2026-08-01", json.dumps({"sender_account_id": 99})),  # 각인됨 → 불변
        (13, "assistant", "a2", "2026-08-01", json.dumps({"product_mode": "auto"})),  # 각인됨 → 불변
    ]
    copied = _conv_store._conv_copy_messages(
        conn, "new", src_rows, "src", None,
        attribution_defaults={
            "user": {"sender_account_id": 4, "sender_username": "alice"},
            "assistant": {"product_mode": "pinned", "product_id": 7, "product_key": "KR"},
        },
    )
    assert copied == 4
    metas = [json.loads(p[4]) for p in conn.inserted]
    # 미각인 행 → 원본 기준으로 고정 + inferred 표기
    assert metas[0]["sender_account_id"] == 4 and metas[0]["sender_username"] == "alice"
    assert metas[0]["attribution_inferred"] is True
    assert metas[1]["product_id"] == 7 and metas[1]["attribution_inferred"] is True
    assert metas[1]["duration_ms"] == 5          # 기존 키 보존
    # 각인된 행 → 원본 각인이 진실이므로 덮지 않는다
    assert metas[2]["sender_account_id"] == 99 and "attribution_inferred" not in metas[2]
    assert metas[3]["product_mode"] == "auto" and "product_id" not in metas[3]
    # fork 추적 마커는 종전대로 전부 부착
    assert all(m["forked_from_conversation_id"] == "src" for m in metas)


def test_copy_messages_without_defaults_is_unchanged(monkeypatch):
    """호출자가 미지정이면 종전 동작 그대로 — 각인 없이 복사(하위호환)."""
    monkeypatch.setattr(appmod, "_runtime_backend_is_pg", lambda: False)
    monkeypatch.setattr(appmod, "_is_internal_message", lambda r, c, m: False)
    conn = _Conn()
    conn.cursor = lambda dictionary=False: _WriterCursor(conn)  # type: ignore[assignment]
    copied = _conv_store._conv_copy_messages(
        conn, "new", [(10, "user", "q", "2026-08-01", None)], "src", None,
    )
    assert copied == 1
    meta = json.loads(conn.inserted[0][4])
    assert "sender_account_id" not in meta
    assert "attribution_inferred" not in meta


def test_fork_uses_source_product_not_degraded_binding():
    """B4: fork 는 접근권 강등(auto) **전** 의 source 제품을 각인해야 한다.

    강등된 `forked_product_id`(=None) 를 쓰면 원본이 KR_LIVE 로 답한 이력이 fork 본에서 전부
    'AI'(제품 없음)로 표시된다 — 발화자 사후 변경이 형태만 바뀐 채 남는다.
    """
    src_path = os.path.join(os.path.dirname(__file__), "..", "src", "routers", "_conv_store.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def _fork_conversation_impl"):]
    body = body[:body.index("\ndef ", 10)]
    call = body[body.index("_fork_attrib[\"assistant\"]"):][:220]
    assert "_src_product_id_raw" in call and "_src_product_mode_raw" in call
    assert "forked_product_id" not in call


# ── B5: FE 렌더 구조 고정 ────────────────────────────────────────────────────

def _app_js() -> str:
    # feature-0038 Cycle 10: 메시지 콘텐츠 렌더(_assistantSpeakerFor 포함)는 app/messages.js 로
    #   분리(byte-동치 이동) — app.js 와 분리 모듈 합본으로 검사한다.
    base = os.path.join(os.path.dirname(__file__), "..", "src", "static")
    out = []
    # ITEM-P5b B2: 전송/발신자 각인(sendPrompt·_selfSenderMeta)은 app/composer.js 로 이동 — 합본에 포함.
    for rel in ("app.js", os.path.join("app", "messages.js"), os.path.join("app", "composer.js")):
        with open(os.path.join(base, rel), encoding="utf-8") as fh:
            out.append(fh.read())
    return "".join(out)


def test_assistant_avatar_resolved_per_message_not_from_composer_chip():
    """회귀의 핵심 — assistant 아바타/라벨/시드가 메시지 각인에서 나와야 한다.

    종전 구현은 renderMessages 상단에서 `state.pinnedProductId` 로 단일 값을 만들어 모든
    말풍선에 재사용했다. 그래서 제품 칩을 바꾸는 순간 과거 답변이 전부 새 제품으로 보였다.
    """
    src = _app_js()
    # B2: renderMessages 는 export 화(`export function`)되어 개행-앵커가 미매칭 — export-prefix 내성 마커
    # (합본 내 "function renderMessages(" 유일 출현 — 호출부는 "function " 접두 없음).
    render = src[src.index("function renderMessages("):]
    render = render[:render.index("\nfunction ", 10)]
    # 메시지별 해석기를 통해서만 아바타 인자를 만든다.
    assert "_assistantSpeakerFor(message.meta" in render
    assert "_assistantSpeaker.label" in render and "_assistantSpeaker.icon" in render
    # 대화 단위 단일 값을 아바타에 직접 넘기던 종전 심볼은 남아 있지 않다.
    for gone in ("_assistantLabel", "_assistantIcon", "_assistantSeed"):
        assert gone not in render, f"renderMessages 에 대화-단위 발화자 심볼 {gone} 잔존"


def test_assistant_speaker_resolver_prefers_stamp_over_live_product():
    src = _app_js()
    fn = src[src.index("function _assistantSpeakerFor("):]
    fn = fn[:fn.index("\nfunction ", 10)]
    # 각인 부재(legacy)만 폴백. 각인 있으면 스냅샷 라벨/시드 우선.
    assert '!("product_mode" in m)' in fn and "return legacyFallback" in fn
    assert re.search(r"label:\s*String\(m\.product_name \|\| m\.product_key", fn)
    assert re.search(r"seed:\s*String\(m\.product_key \|\| m\.product_name", fn)
    # auto 각인은 'AI' 배지로 확정(빈 label/seed → _msgAvatarEl 이 "AI").
    assert 'String(m.product_mode) === "auto"' in fn


def test_user_speaker_uses_sender_not_conversation_ownership():
    """fork 본은 owner 가 복제자로 바뀌므로 `isOwn` 으로 판정하면 원저자 질문이 '나' 가 된다.

    §18.8 codex P1: sender id 만 있는 타인 메시지를 `ownerLabel` 로 폴백하면, 발신자가 owner 와
    **다르다는 것을 아는** 상태에서 owner 이름을 붙이는 확정적 오귀속이 된다. id 로 구분한다.
    """
    src = _app_js()
    # B2: renderMessages 는 export 화(`export function`)되어 개행-앵커가 미매칭 — export-prefix 내성 마커
    # (합본 내 "function renderMessages(" 유일 출현 — 호출부는 "function " 접두 없음).
    render = src[src.index("function renderMessages("):]
    render = render[:render.index("\nfunction ", 10)]
    block = render[render.index('let speaker = "Assistant";'):][:1200]
    assert "else if (senderId)" in block
    assert "speaker = msgIsOwn ? selfLabel : `사용자 ${senderId}`;" in block
    # legacy(각인 전무) 행만 대화 owner 폴백을 쓴다.
    assert "speaker = isOwn ? selfLabel : ownerLabel;" in block


def test_fork_attribution_axes_are_independent():
    """user 표시명 조회 실패가 assistant 제품 귀속까지 버리면 안 된다(§18.8 codex P1)."""
    src_path = os.path.join(os.path.dirname(__file__), "..", "src", "routers", "_conv_store.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def _fork_conversation_impl"):]
    body = body[:body.index("\ndef ", 10)]
    seg = body[body.index("_fork_attrib: dict"):body.index("copied = app._conv_copy_messages")]
    # assistant 각인이 user 블록의 except 로 무효화되지 않도록 **별도 try** 여야 한다.
    assert seg.count("try:") >= 3
    assert "_fork_attrib = {}" not in seg, "한 축의 실패가 다른 축 귀속까지 버린다"


def test_product_switch_reloads_history_for_backfilled_attribution():
    """freeze-on-change 로 서버가 각인한 직후 재조회가 없으면 legacy 구간이 그 자리에서 뒤바뀐다."""
    src = _app_js()
    fn = src[src.index("async function setActiveProduct("):]
    fn = fn[:fn.index("\nasync function ", 10)]
    assert "loadHistory({ preserveScroll: true })" in fn
