"""TASK-0168 (F2, Minor §12.3) — 공유뷰 redaction/internal-filter 회귀 가드 (PG dict-meta 경로).

배경: TASK-0167 cutover 수정으로 `_share_load_messages` 가 MySQL dict-cursor 대신
`_conv_load_messages_raw` (PG `agent_runtime.messages`) 의 **tuple 행 + jsonb→dict meta_json**
을 처리하도록 바뀌었다. REV-20260609-0001 (outside-voice) 가 "public-exposure 면이므로
redaction/internal-filter 불변식을 자동 가드하라" 권고(F2).

본 테스트는 `_pg_connect` 를 mock 해 PG dict-meta 경로를 결정적으로 재현하고, 익명 공유뷰의
보안 불변식을 단언한다 (라이브 DB 불요):
  1. attachment_derived 메시지(stale-policy token) 본문이 SHARE_POLICY_REDACT_TEXT 로 redact 된다.
  2. 내부(internal) assistant 메시지가 공유뷰에서 제외된다.
  3. 정상 메시지 본문은 보존된다.
  4. 정책 version gate: token version == CURRENT 면 redact 안 함 / None·stale 면 redact.

실행 (web 컨테이너 내 — web.app import 필요):
  docker exec -w /app repo-web-1 python web/tests/test_share_redaction_invariant.py
  또는 make test (컨테이너 pytest 수집).
"""
from __future__ import annotations

import datetime
import os
import sys


def _imports():
    try:
        import web.app as A  # type: ignore
        import shared.db as DB  # type: ignore
    except ModuleNotFoundError:
        # 컨테이너 실행 경로 보정 (uvicorn web.app:app 의 working_dir 와 동일).
        sys.path.insert(0, "/app")
        import web.app as A  # type: ignore
        import shared.db as DB  # type: ignore
    return A, DB


class _FakePgCursor:
    """psycopg cursor context-manager 흉내 — `with pg.cursor() as cur:` 패턴 대응."""

    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class _FakePgConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakePgCursor(self._rows)

    def close(self):
        return None


# jsonb → dict 로 반환되는 PG read 를 모사한 행: (id, role, content, created_at, meta_json[dict|None])
def _sample_rows():
    dt = datetime.datetime(2026, 6, 9, 3, 0, 0)
    return [
        (1, "user", "정상 사용자 질문", dt, None),
        (2, "assistant", "원본 첨부 분석 결과: 민감 CSV 본문 row1,row2 ...", dt, {"attachment_derived": True}),
        (3, "assistant", "내부 시스템 노트", dt, {"internal": True}),
        (4, "assistant", "정상 어시스턴트 답변", dt, {}),
    ]


def _run_share_load(policy_version):
    """_pg_connect 를 mock + PG 백엔드 플래그 set 후 _share_load_messages 실행, id→msg map 반환."""
    A, DB = _imports()
    prev_flag = os.environ.get("AGENT_RUNTIME_READ_BACKEND")
    os.environ["AGENT_RUNTIME_READ_BACKEND"] = "postgres"
    orig_pg = DB._pg_connect
    DB._pg_connect = lambda *a, **k: _FakePgConn(_sample_rows())
    try:
        out = A._share_load_messages(None, "conv-x", None, share_token_policy_version=policy_version)
    finally:
        DB._pg_connect = orig_pg
        if prev_flag is None:
            os.environ.pop("AGENT_RUNTIME_READ_BACKEND", None)
        else:
            os.environ["AGENT_RUNTIME_READ_BACKEND"] = prev_flag
    return A, {m["id"]: m for m in out}, out


def test_stale_token_redacts_attachment_and_filters_internal():
    """stale-policy token(version=1 < CURRENT) → attachment_derived redact + internal 제외."""
    A, by_id, out = _run_share_load(policy_version=1)
    # internal assistant 메시지(id=3)는 공유뷰에서 제외.
    assert 3 not in by_id, "internal 메시지가 공유뷰에 노출됨 (필터 회귀)"
    # attachment_derived 메시지(id=2) 본문은 redact.
    assert by_id[2]["content"] == A.SHARE_POLICY_REDACT_TEXT, "attachment_derived 본문 redact 회귀"
    # 정상 메시지 본문 보존.
    assert by_id[1]["content"] == "정상 사용자 질문"
    assert by_id[4]["content"] == "정상 어시스턴트 답변"
    # 4행 중 internal 1개 제외 = 3개.
    assert len(out) == 3, f"기대 3개, 실제 {len(out)}"


def test_null_policy_token_redacts():
    """legacy token(version=NULL) 도 현 정책으로 redact 적용."""
    A, by_id, _ = _run_share_load(policy_version=None)
    assert 3 not in by_id
    assert by_id[2]["content"] == A.SHARE_POLICY_REDACT_TEXT


def test_current_policy_token_no_auto_redact():
    """token version == CURRENT → R-F7 자동 redact 비활성(원본 노출) — version gate 정합 확인."""
    A0, _DB = _imports()
    A, by_id, _ = _run_share_load(policy_version=A0.SHARE_POLICY_VERSION_CURRENT)
    # 정책 version gate: redact_active = (version is None or version < CURRENT). CURRENT 면 False.
    assert by_id[2]["content"].startswith("원본 첨부 분석 결과"), "current-policy token 인데 redact 됨 (gate 회귀)"
    # internal 필터는 정책 version 과 무관하게 항상 적용.
    assert 3 not in by_id


def test_attachment_redact_strips_steps_sql_and_results():
    """share-query-navigator: share.js 가 meta.steps 의 execute_sql 단계(sql + result_summary)를
    렌더하므로, attachment_derived 메시지 redact 시 steps 도 제거돼 raw 첨부 파생 쿼리/결과가
    익명 공유뷰에 새지 않아야 한다 (보안 정합).
    """
    A, _DB = _imports()
    meta = {
        "attachment_derived": True,
        "final_sql": "SELECT * FROM secret.t",
        "result_rows": [{"col": "민감값"}],
        "steps": [
            {
                "tool": "execute_sql",
                "sql": "SELECT secret_col FROM attached.csv_table",
                "result_summary": {"preview_table": {"columns": ["secret_col"], "rows": [["민감"]]}},
            }
        ],
    }
    content, was_redacted, meta_clean = A._share_redact_message_content("원본 첨부 분석 본문", meta)
    assert was_redacted is True
    assert content == A.SHARE_POLICY_REDACT_TEXT
    # 민감 키 전부 제거.
    assert "steps" not in meta_clean, "attachment_derived redact 후 meta.steps 잔존 (쿼리/결과 누출)"
    assert "final_sql" not in meta_clean
    assert "result_rows" not in meta_clean
    # categorical 플래그는 유지.
    assert meta_clean["attachment_derived"] is True
    assert meta_clean["redacted_by_share_policy"] is True


def test_non_attachment_message_preserves_steps():
    """attachment_derived 가 아닌 정상 메시지는 meta.steps(쿼리 navigator 데이터)를 보존한다."""
    A, _DB = _imports()
    meta = {
        "steps": [
            {"tool": "execute_sql", "sql": "SELECT 1", "result_summary": {"preview_table": {"columns": ["x"], "rows": [["1"]]}}},
            {"tool": "execute_sql", "sql": "SELECT 2", "result_summary": {"preview_table": {"columns": ["y"], "rows": [["2"]]}}},
        ],
    }
    content, was_redacted, meta_out = A._share_redact_message_content("정상 답변", meta)
    assert was_redacted is False
    assert content == "정상 답변"
    # 정상 메시지의 steps 는 그대로 — share.js navigator 가 쿼리 전환에 사용.
    assert meta_out is meta
    assert len(meta_out["steps"]) == 2


def test_share_sanitize_step_strips_server_paths_and_raw_payload():
    """share-query-navigator(보안): share 익명 노출용 step sanitize 가 csv_paths(서버 경로)·
    preview(결과 전문)·args(원본 tool 인자)·error(원본 오류)를 제거하고, share.js 가 실제 렌더하는
    {tool, sql, reason, result_summary.preview_table} 만 통과시키는지 단언.

    agent_runtime.steps.result_summary_json 은 라이브에서 {preview, csv_paths, preview_table} 를
    담고 csv_paths 에 /shared/... 서버 경로가 들어간다. 익명 공유 API 페이로드로 새면 안 된다.
    """
    A, _DB = _imports()
    raw_step = {
        "tool": "execute_sql",
        "sql": "SELECT * FROM sales.orders",
        "reason": "주문 조회",
        "intent": "조회",
        "work": "쿼리 실행",
        "args": {"database": "sales", "raw": "민감 tool 인자"},
        "error": "원본 오류 본문 (raw payload 단편 포함 가능)",
        "result_summary": {
            "preview_table": {"columns": ["id"], "rows": [["1"]], "truncated": False},
            "csv_paths": ["/shared/out/run-123/result_0.csv"],
            "preview": "원본 결과 전문 텍스트 (100자 잘림 전)...",
        },
    }
    clean = A._share_sanitize_step(raw_step)
    # 통과돼야 할 것
    assert clean["tool"] == "execute_sql"
    assert clean["sql"] == "SELECT * FROM sales.orders"
    assert clean["reason"] == "주문 조회"
    assert clean["result_summary"]["preview_table"]["columns"] == ["id"]
    # 제거돼야 할 것 (익명 노출 차단)
    assert "args" not in clean, "step.args(원본 tool 인자) 누출"
    assert "error" not in clean, "step.error(원본 오류 본문) 누출"
    assert "csv_paths" not in clean["result_summary"], "result_summary.csv_paths(서버 경로) 누출"
    assert "preview" not in clean["result_summary"], "result_summary.preview(결과 전문) 누출"
    # 직렬화 후 서버 경로 문자열이 전혀 없어야 함
    import json as _json
    blob = _json.dumps(clean, ensure_ascii=False)
    assert "/shared/" not in blob, "직렬화 결과에 /shared/ 서버 경로 잔존"
    assert "원본 결과 전문" not in blob and "민감 tool 인자" not in blob, "raw payload 잔존"


def test_share_sanitize_step_handles_malformed():
    """sanitize 가 비정상 입력(비-dict result_summary, None, 빈 dict)에 안전한지."""
    A, _DB = _imports()
    assert A._share_sanitize_step(None) == {}
    assert A._share_sanitize_step("not a dict") == {}
    # result_summary 가 dict 아님 → 통째 제거
    clean = A._share_sanitize_step({"tool": "execute_sql", "sql": "SELECT 1", "result_summary": "raw string"})
    assert "result_summary" not in clean
    assert clean["sql"] == "SELECT 1"
    # preview_table 없는 result_summary → result_summary 자체 제거
    clean2 = A._share_sanitize_step({"tool": "execute_sql", "sql": "SELECT 1", "result_summary": {"csv_paths": ["/shared/x.csv"]}})
    assert "result_summary" not in clean2


def main() -> int:
    tests = [
        test_stale_token_redacts_attachment_and_filters_internal,
        test_null_policy_token_redacts,
        test_current_policy_token_no_auto_redact,
        test_attachment_redact_strips_steps_sql_and_results,
        test_non_attachment_message_preserves_steps,
        test_share_sanitize_step_strips_server_paths_and_raw_payload,
        test_share_sanitize_step_handles_malformed,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"[FAIL] {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n=== {passed}/{len(tests)} passed ===")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
