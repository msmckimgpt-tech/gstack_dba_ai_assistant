"""FR-attach-change-signal-client-only — 첨부 변경-인지 신호의 서버 권위 봉인 회귀 테스트.

관측(conversation_audit 2026-08-14, 대화 …f72f26ef): 사용자가 파일 3개를 v2 로 재업로드하고
74초 뒤 "다시 리뷰" 를 요청했는데, 그 턴의 `ask_jobs.payload.new_attachment_ids` 가 **빈 배열**
이었다. 그 값 하나에 변경-인지 경로 4종이 전부 걸려 있어 한꺼번에 꺼진다:
  ① `★신규` 라벨 → 갱신 파일이 오히려 `◆세션`(이전 세션에서 첨부)으로 **오라벨**
  ② `## FILE UPDATES` v(n-1)→v(n) unified diff 섹션 생략 — 서버가 **이미 계산해 저장한** diff 인데도
  ③ `## ATTACHMENT SET` 코드-권위 사실 블록 침묵 (FR-attachment-change-false-absence 봉인 미도달)
  ④ red-team 리뷰어 digest 의 version_diff 부재 → 모순을 검출할 근거 없음

근본: `new_attachment_ids` 는 브라우저 in-memory pill 상태(`source:"new"`)에서 나오는 **클라이언트
신호**다. 대화 전환·첨부 패널 조작·새로고침이면 목록이 서버에서 재수화되며 전부 `source:"session"`
으로 덮이고(composer.js `_loadConversationAttachments`), 비-브라우저 호출은 애초에 비어 있다.
60일 실측: 이번-턴 업로드가 있는데 신호가 빈 job **14건 / 14 대화**(버전 갱신 축 5/37 = 13.5%).

봉인: 서버가 **직전 턴 전달 스코프**를 기준선으로 "이번 턴에 새로 도착한 첨부" 를 스스로 파생하고
클라이언트 신호와 **합집합**한다. 판정은 첨부 id 단조성으로 하며 저장 **시각**을 쓰지 않는다
(FR-attachment-created-at-tz-skew-9h 류 시간축 왜곡 비의존).

불변식(이 파일이 잠그는 것):
  - 빈 신호를 "첨부 없음" 으로 단정하지 않는다 — 양쪽 다 비면 종전대로 **침묵**한다.
  - 스코프를 넓히지 않는다 — 파생은 이미 게이트를 통과한 행의 **부분집합**에만 라벨을 붙인다.
  - 첫 턴(fork 포함)에서는 파생하지 않는다 — 기준선이 없으면 복사된 첨부까지 신규라 말하게 된다.
"""
from __future__ import annotations

import json

import agent_core
import shared.config as cfg
from modules import runtime_backend

_DIFF = {"from_version": 1, "to_version": 2, "truncated": False,
         "unified_diff": "--- a (v1)\n+++ a (v2)\n@@ -1 +1 @@\n-old\n+new"}


# ── fixtures ──────────────────────────────────────────────────────────────


def _scoped(aid, fname, *, version=1, role="user", meta=None, kind="text"):
    """`_load_scoped_attachment_rows()` 가 돌려주는 dict 형태."""
    return {
        "id": aid, "filename": fname, "kind": kind, "object_key": f"k/{aid}",
        "status": "uploaded", "meta_json": json.dumps(meta if meta is not None else {}),
        "created_by_role": role, "version_number": version, "account_id": 10,
    }


def _arm(monkeypatch, *, prev_ids, scoped_rows, job_id=685, client_signal="", account_id=10):
    """서버 파생의 두 입력(직전 턴 스코프 · 현재 스코프)과 클라이언트 신호를 고정한다."""
    monkeypatch.setenv("NEW_ATTACHMENT_IDS", client_signal)
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: list(scoped_rows))
    monkeypatch.setattr(
        runtime_backend, "_read_ask_queue_pg",
        lambda method, **kw: prev_ids if method == "load_prev_turn_attachment_ids" else None,
    )
    agent_core._SERVER_NEW_ATTACHMENT_IDS_CTX.set(None)
    agent_core._ASK_JOB_ID_CTX.set(job_id)
    agent_core._ACTIVE_ACCOUNT_ID_CTX.set(account_id)
    cfg._ACTIVE_CONVERSATION_ID.set("conv-x")


# ── 직전 턴 기준선 로더: None 과 [] 는 다른 뜻이다 ────────────────────────


class _OneRowConn:
    def __init__(self, row):
        self._row = row

    def cursor(self, *a, **k):
        row = self._row

        class _Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def execute(self_inner, sql, params=None):
                pass

            def fetchone(self_inner):
                return row

        return _Cur()


def test_prev_turn_loader_distinguishes_absent_from_empty():
    """`None`(기준선 없음) 과 `[]`(직전 턴에 첨부 0건) 를 합치면 첫 턴에서 과표시가 난다."""
    backend = runtime_backend.PgRuntimeBackend()
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(None), conversation_id="c", job_id=685, account_id=10) is None
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(([],)), conversation_id="c", job_id=685, account_id=10) == []
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(([1179, 1180],)), conversation_id="c", job_id=685, account_id=10) == [1179, 1180]
    # 현재 job id 를 모르면 기준선을 특정할 수 없다(web inproc·CLI).
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(([1],)), conversation_id="c", job_id=0, account_id=10) is None


def test_prev_turn_loader_treats_missing_scope_key_as_unknown():
    """§18.8 codex [P2]: legacy/부분 payload 의 **부재**를 `[]`(=직전 턴 첨부 0건)로 뭉개면
    그 다음 턴의 사용자 첨부가 전부 신규로 라벨된다(stale 사실 주입)."""
    backend = runtime_backend.PgRuntimeBackend()
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn((None,)), conversation_id="c", job_id=685, account_id=10) is None


def test_prev_turn_loader_does_not_depend_on_current_job_row_visibility():
    """§18.8 codex [P1]: 현재 job 을 `run_id` 로 되찾으면 RO(비동기 replica) 경로에서 자기 행이
    아직 안 보일 때 기준선을 잃어 **봉인이 조용히 꺼진다**. 조회는 호출자가 준 id 범위만 쓴다."""
    assert "run_id" not in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS
    assert "%(job_id)s" in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS
    assert "COALESCE" not in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS


def test_prev_turn_baseline_is_scoped_to_the_same_sender():
    """§18.8 codex [P1]: 첨부 스코프는 **계정별로** 해소된다(공유창 + 발신자 게이트).

    그룹에서 직전 job 이 다른 멤버의 것이면 그 `attachment_ids` 는 *그 멤버의* 스코프라 내
    스코프와 비교 가능한 축이 아니다. 내가 오래전 올린 파일 id 가 그 멤버의 최대 id 보다 크기만
    하면(내 5000 vs 그 멤버 4000) 내가 아무것도 올리지 않은 턴에도 그 파일이 '이번 턴 신규' 가
    되어 낡은 diff 와 ★신규 사실이 **턴마다** 재주입된다. 기준선은 같은 account 로 좁힌다.
    """
    assert "%(account_id)s" in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS, (
        "기준선이 발신자로 좁혀지지 않는다 — 그룹에서 비교 불가능한 스코프끼리 대조하게 된다"
    )
    assert "account_id =" in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS
    backend = runtime_backend.PgRuntimeBackend()
    # 계정을 모르면 비교 가능한 기준선을 특정할 수 없다 → 파생 안 함(종전 동작).
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(([1],)), conversation_id="c", job_id=685, account_id=0) is None


def test_prev_turn_baseline_only_counts_delivered_turns():
    """§18.8 codex round4 [P2]: `error`/진행중 job 의 payload 는 '그 첨부가 전달됐다' 는 증거가
    아니다. 기준선으로 삼으면 그 id 들이 `prev_max` 이하가 되어 다음 턴에서 제외되고, 프론트
    표식까지 강등됐으면 ★신규·FILE UPDATES 가 다시 통째로 빠진다(봉인 대상 마찰 재현)."""
    assert "status = 'done'" in runtime_backend._PG_LOAD_PREV_TURN_ATTACHMENTS, (
        "전달이 완료되지 않은 턴이 기준선이 될 수 있다"
    )


def test_baseline_read_is_independent_of_history_read_backend_toggle():
    """§18.8 codex round6 [P1]: ask 큐는 PG 에만 있다(MySQL 대응물 없음). 큐 조회를
    `AGENT_RUNTIME_READ_BACKEND`(히스토리 읽기 스위치)에 매달면 그 설정을 mysql 로 돌리는 순간
    첨부 변경-인지 봉인이 **조용히 꺼진다** — 이 cycle 의 R1 교정과 같은 원칙."""
    import ast
    import inspect
    # **docstring 을 제거하고** 실행 코드만 본다 — 설명문에 등장하는 이름이 단언을 vacuous 하게
    # 통과/실패시키면 안 된다(이 저장소의 주석-오통과 함정과 같은 축).
    fn = ast.parse(inspect.getsource(runtime_backend._read_ask_queue_pg)).body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]
    body_src = ast.unparse(fn)
    assert "AGENT_RUNTIME_READ_BACKEND" not in body_src, (
        "큐 읽기가 히스토리 읽기 백엔드 토글에 묶여 있다 — 설정 하나로 봉인이 꺼진다"
    )
    assert "_read_ask_queue_pg" in inspect.getsource(agent_core._derive_server_new_attachment_ids)


def test_unknown_account_does_not_derive(monkeypatch):
    """요청 계정을 모르면(비-워커 경로) 서버 파생을 건너뛴다 — fail-soft."""
    _arm(monkeypatch, prev_ids=[1179], scoped_rows=[_scoped(1187, "a.sql")], account_id=0)
    assert agent_core._derive_server_new_attachment_ids() == frozenset()


def test_prev_turn_loader_parses_json_string_payload():
    """jsonb auto-parse 가 없는 드라이버에서도 기준선을 잃지 않는다."""
    backend = runtime_backend.PgRuntimeBackend()
    assert backend.load_prev_turn_attachment_ids(
        _OneRowConn(("[1179, 1180]",)), conversation_id="c", job_id=685, account_id=10) == [1179, 1180]


# ── 서버 파생 판정식 ──────────────────────────────────────────────────────


def test_derives_this_turn_uploads_from_previous_scope(monkeypatch):
    """관측 대화 재현: 직전 턴 4건 → 이번 턴 v2 3건 신규. 클라이언트 신호는 비어 있다."""
    _arm(
        monkeypatch,
        prev_ids=[1179, 1180, 1181, 1182],
        scoped_rows=[
            _scoped(1181, "01_CharacterRank_Prev.sql"),                       # 이월(v1 그대로)
            _scoped(1187, "02_login.sql", version=2, meta={"version_diff": _DIFF}),
            _scoped(1188, "03_replication.sql", version=2, meta={"version_diff": _DIFF}),
            _scoped(1189, "01_LeagueRank_Prev.sql", version=2, meta={"version_diff": _DIFF}),
        ],
    )
    assert agent_core._derive_server_new_attachment_ids() == frozenset({1187, 1188, 1189})


def test_first_turn_does_not_derive(monkeypatch):
    """기준선이 없으면(첫 턴·fork 첫 턴·job 행 부재) 파생하지 않는다 — 복사된 첨부 과표시 방지."""
    _arm(monkeypatch, prev_ids=None, scoped_rows=[_scoped(1187, "a.sql", version=2)])
    assert agent_core._derive_server_new_attachment_ids() == frozenset()


def test_no_job_id_does_not_derive(monkeypatch):
    """web inproc·CLI·테스트 경로(현재 job id 부재)는 종전 동작 유지."""
    _arm(monkeypatch, prev_ids=[1], scoped_rows=[_scoped(1187, "a.sql")], job_id=0)
    assert agent_core._derive_server_new_attachment_ids() == frozenset()


def test_assistant_authored_attachment_is_not_a_user_upload(monkeypatch):
    """AI 수정본은 '사용자가 이번 턴에 올린 것' 이 아니다 — 🔄 표식이 그 축을 따로 말한다."""
    _arm(
        monkeypatch,
        prev_ids=[1179],
        scoped_rows=[_scoped(1190, "ai_fix.sql", version=2, role="assistant")],
    )
    assert agent_core._derive_server_new_attachment_ids() == frozenset()


def test_widened_share_window_does_not_mark_old_files_as_new(monkeypatch):
    """그룹 공유창이 넓어져 **예전** 파일이 이제 보이게 된 것은 '이번 턴에 올라왔다' 가 아니다.

    id 단조성으로 판정하므로 직전 턴 최대 id 이하의 파일은 스코프에 새로 나타나도 제외된다.
    (이 대칭이 깨지면 멤버가 합류하는 순간 남의 옛 파일이 전부 ★신규 로 실린다.)
    """
    _arm(
        monkeypatch,
        prev_ids=[1179, 1180],
        scoped_rows=[
            _scoped(1100, "other_member_old.sql"),   # 창이 열려 이제 보이는 옛 파일
            _scoped(1181, "just_uploaded.sql"),      # 이번 턴 실제 업로드
        ],
    )
    assert agent_core._derive_server_new_attachment_ids() == frozenset({1181})


def test_previous_turn_with_zero_attachments_marks_all_current(monkeypatch):
    """`[]` 는 양성 정보다 — 직전 턴엔 첨부가 없었으니 지금 스코프의 사용자 첨부는 전부 신규."""
    _arm(monkeypatch, prev_ids=[], scoped_rows=[_scoped(5, "a.sql"), _scoped(6, "b.sql")])
    assert agent_core._derive_server_new_attachment_ids() == frozenset({5, 6})


# ── 합집합 · run 단위 캐시 ────────────────────────────────────────────────


def test_union_of_client_signal_and_server_derivation(monkeypatch):
    """한쪽이 비어도 다른 쪽이 사실을 지킨다."""
    _arm(
        monkeypatch,
        prev_ids=[1179],
        scoped_rows=[_scoped(1187, "a.sql", version=2)],
        client_signal="1181",
    )
    assert agent_core._load_new_attachment_ids() == {1181, 1187}


def test_server_derivation_computed_once_per_run(monkeypatch):
    """소비자 3곳이 각자 DB 를 다시 읽으면 부분 실패 시 서로 다른 집합을 말한다(단일 사실 붕괴)."""
    calls = {"n": 0}

    def _counting(method, **kw):
        if method == "load_prev_turn_attachment_ids":
            calls["n"] += 1
            return [1179]
        return None

    _arm(monkeypatch, prev_ids=[1179], scoped_rows=[_scoped(1187, "a.sql")])
    monkeypatch.setattr(runtime_backend, "_read_ask_queue_pg", _counting)
    agent_core._SERVER_NEW_ATTACHMENT_IDS_CTX.set(None)

    first = agent_core._load_new_attachment_ids()
    second = agent_core._load_new_attachment_ids()
    assert first == second == {1187}
    assert calls["n"] == 1, f"run 당 1회여야 하는데 {calls['n']}회 조회"


def test_derivation_failure_is_fail_soft(monkeypatch):
    """기준선 조회가 던져도 턴을 죽이지 않는다 — 종전(클라이언트 신호 단독)으로 내려간다."""
    def _boom(method, **kw):
        raise RuntimeError("pg down")

    _arm(monkeypatch, prev_ids=[1], scoped_rows=[_scoped(1187, "a.sql")], client_signal="1181")
    monkeypatch.setattr(runtime_backend, "_read_ask_queue_pg", _boom)
    agent_core._SERVER_NEW_ATTACHMENT_IDS_CTX.set(None)
    assert agent_core._load_new_attachment_ids() == {1181}


# ── 배선 seam: 파생이 실제로 프롬프트/사실 블록에 도달하는가 ──────────────
#
# 형제 봉인(FR-attachment-change-false-absence)의 §18.8 패널이 남긴 교훈 — builder 를 직접
# 호출하는 테스트만 있으면 "합집합을 지운다" 는 뮤테이션이 전부 통과한다. 아래는 클라이언트
# 신호가 **빈 상태**에서 관측된 마찰(◆세션 오라벨 + diff 소실 + 사실 침묵)이 사라지는지를 잠근다.


class _RowsConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *a, **k):
        rows = self._rows

        class _Cur:
            def execute(self, sql, params=None):
                pass

            def fetchall(self):
                return rows

            def close(self):
                pass

        return _Cur()


def _mysql_row(aid, fname, *, version=1, root=None, role="user", meta=None, kind="text"):
    """`_build_attachment_context_section` 이 읽는 MySQL SELECT 컬럼 순서."""
    return (
        aid, "conv-x", fname, kind, "text/plain", 100, "small", "uploaded",
        json.dumps(meta if meta is not None else {}), root, version, role,
    )


def test_empty_client_signal_still_renders_new_label_and_diff(monkeypatch):
    """마찰 그 자체: 신호가 비어도 갱신 파일이 ★신규 로 라벨되고 diff 가 프롬프트에 실린다."""
    rows = [
        _mysql_row(1187, "02_login.sql", version=2, root=1179, meta={"version_diff": _DIFF}),
        _mysql_row(1181, "01_char.sql", version=1),
    ]
    _arm(
        monkeypatch,
        prev_ids=[1179, 1180, 1181, 1182],
        scoped_rows=[_scoped(1187, "02_login.sql", version=2, meta={"version_diff": _DIFF}),
                     _scoped(1181, "01_char.sql")],
        client_signal="",
    )
    monkeypatch.setenv("ATTACHMENT_IDS", "1187,1181")
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)

    out = agent_core._build_attachment_context_section(
        _RowsConn(rows), [1187, 1181], conversation_id="conv-x")

    assert "★신규" in out, "갱신 파일이 여전히 ◆세션 으로만 라벨된다"
    assert "## FILE UPDATES" in out, "서버가 이미 가진 v1→v2 diff 가 프롬프트에서 빠졌다"
    facts = agent_core._attachment_turn_facts()
    assert facts is not None and len(facts["updated"]) == 1, facts
    assert "02_login.sql" in facts["updated"][0]
    # 권위 블록도 살아난다(형제 봉인 A 축 도달).
    assert "ATTACHMENT SET" in agent_core._build_attachment_authority_directive(facts)


def test_silence_preserved_when_nothing_new(monkeypatch):
    """빈 값을 '첨부 없음' 으로 단정하지 않는 계약은 그대로 — 부정 진술을 만들지 않는다."""
    rows = [_mysql_row(1181, "01_char.sql", version=1)]
    _arm(
        monkeypatch,
        prev_ids=[1181],
        scoped_rows=[_scoped(1181, "01_char.sql")],
        client_signal="",
    )
    monkeypatch.setenv("ATTACHMENT_IDS", "1181")
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)

    out = agent_core._build_attachment_context_section(
        _RowsConn(rows), [1181], conversation_id="conv-x")
    assert "★신규" not in out
    assert "## FILE UPDATES" not in out
    facts = agent_core._attachment_turn_facts()
    assert agent_core._build_attachment_authority_directive(facts) == ""
