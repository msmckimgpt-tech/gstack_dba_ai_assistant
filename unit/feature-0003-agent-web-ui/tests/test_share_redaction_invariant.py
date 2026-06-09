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
        import modules.db as DB  # type: ignore
    except ModuleNotFoundError:
        # 컨테이너 실행 경로 보정 (uvicorn web.app:app 의 working_dir 와 동일).
        sys.path.insert(0, "/app")
        import web.app as A  # type: ignore
        import modules.db as DB  # type: ignore
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


def main() -> int:
    tests = [
        test_stale_token_redacts_attachment_and_filters_internal,
        test_null_policy_token_redacts,
        test_current_policy_token_no_auto_redact,
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
