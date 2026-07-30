"""T0b — AI 운영 현황의 워커 공유 자원 섹션(`ai_ops._worker_resources`) 단위 테스트.

DB/LLM 불요. 검증 핵심:
  - 카운터는 **워커 프로세스 메모리**에 있고 web 은 다른 프로세스다 → 공유 볼륨의 파일을 읽는다.
    PG 테이블·마이그레이션 없이 성립하는지(파일 파싱 계약).
  - **fail-open**: 파일 부재·손상·거대·권한 오류가 콘솔 응답을 깨지 않고 degrade 로 강등된다
    (§20 ai-ops 부분 degrade 규약 답습).
  - stale 판정(워커가 flush 를 멈춘 경우)과 손상 파일 격리(하나가 깨져도 나머지는 보인다).
"""
from __future__ import annotations

import json
import os
import time

import pytest

from routers import ai_ops


@pytest.fixture
def res_dir(tmp_path, monkeypatch):
    """스냅샷 디렉토리를 tmp 로 격리."""
    monkeypatch.setattr(ai_ops, "_WORKER_RES_DIR", str(tmp_path))
    return tmp_path


def _write(path, *, role="insight-worker", rejected=0, limit=16, peak=0,
           background=True, flushed_at="2026-07-30T05:00:00Z", conns=None):
    payload = {
        "resources": {"llm": {"limit": limit, "in_use": 0, "peak": peak, "acquired": 3,
                              "rejected": rejected, "wait_ms_total": 0.0,
                              "held_ms_total": 12.5,
                              "reject_ratio": (rejected / (3 + rejected)) if rejected else 0.0}},
        "conns": conns if conns is not None else {"pg_conns": 5, "pg_ro_conns": 0, "ds_conns": 2},
        "background_enabled": background,
        "flushed_at": flushed_at,
        "role": role,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_absent_dir_degrades_not_raises(monkeypatch):
    monkeypatch.setattr(ai_ops, "_WORKER_RES_DIR", "/nonexistent-dir-for-test")
    out = ai_ops._worker_resources()
    assert out["available"] is False
    assert out["workers"] == []
    assert out.get("reason")


def test_empty_dir_reports_reason(res_dir):
    out = ai_ops._worker_resources()
    assert out["available"] is False
    assert "flush" in out["reason"] or "스냅샷" in out["reason"]


def test_valid_snapshot_is_parsed(res_dir):
    _write(res_dir / "worker-resources-insight.json")
    out = ai_ops._worker_resources()
    assert out["available"] is True
    assert len(out["workers"]) == 1
    w = out["workers"][0]
    assert w["role"] == "insight-worker"
    assert w["background_enabled"] is True
    assert w["resources"]["llm"]["limit"] == 16
    assert w["resources"]["llm"]["rejected"] == 0
    assert w["conns"]["ds_conns"] == 2
    assert w["stale"] is False


def test_corrupt_file_is_isolated(res_dir):
    """파일 하나가 깨져도 나머지 워커는 보인다(격리)."""
    (res_dir / "worker-resources-broken.json").write_text("{not json", encoding="utf-8")
    _write(res_dir / "worker-resources-ok.json", role="ask-worker")
    out = ai_ops._worker_resources()
    assert out["available"] is True
    assert [w["role"] for w in out["workers"]] == ["ask-worker"]


def test_oversized_file_skipped(res_dir):
    big = res_dir / "worker-resources-big.json"
    big.write_text("x" * (ai_ops._WORKER_RES_MAX_BYTES + 1), encoding="utf-8")
    out = ai_ops._worker_resources()
    assert out["available"] is False


def test_stale_snapshot_flagged(res_dir):
    """워커가 flush 를 멈추면 stale — 값이 최신처럼 보이지 않게 표식한다."""
    path = res_dir / "worker-resources-stale.json"
    _write(path)
    old = time.time() - (ai_ops._WORKER_RES_STALE_SEC + 60)
    os.utime(path, (old, old))
    out = ai_ops._worker_resources()
    assert out["workers"][0]["stale"] is True
    assert out["workers"][0]["age_sec"] > ai_ops._WORKER_RES_STALE_SEC


def test_non_dict_payload_skipped(res_dir):
    (res_dir / "worker-resources-list.json").write_text("[1,2,3]", encoding="utf-8")
    out = ai_ops._worker_resources()
    assert out["available"] is False


def test_file_count_capped(res_dir):
    for i in range(ai_ops._WORKER_RES_MAX_FILES + 3):
        _write(res_dir / f"worker-resources-{i:02d}.json", role=f"w{i}")
    out = ai_ops._worker_resources()
    assert len(out["workers"]) == ai_ops._WORKER_RES_MAX_FILES


def test_malformed_resource_values_do_not_break_parse(res_dir):
    """숫자 자리에 문자열이 와도(손상) 해당 항목만 빠지고 파싱은 계속된다."""
    path = res_dir / "worker-resources-odd.json"
    path.write_text(json.dumps({
        "resources": {"llm": "not-a-dict", "ds": {"limit": 8, "rejected": 1, "reject_ratio": 0.25}},
        "conns": {"pg_conns": "nope", "ds_conns": 3},
        "background_enabled": True, "role": "w",
    }), encoding="utf-8")
    out = ai_ops._worker_resources()
    assert out["available"] is True
    w = out["workers"][0]
    assert "llm" not in w["resources"]          # dict 아닌 값은 제외
    assert w["resources"]["ds"]["rejected"] == 1
    assert "pg_conns" not in w["conns"]          # int 변환 실패는 제외
    assert w["conns"]["ds_conns"] == 3

# ── codex P1/P2 회귀 ─────────────────────────────────────────────────────────

def test_nan_and_infinity_do_not_break_json(res_dir):
    """NaN/Infinity 는 표준 JSON 이 아니라 `JSONResponse` 직렬화를 500 으로 만든다(fail-open 위반).

    손상된 스냅샷이 그 값을 담을 수 있으므로 경계에서 0 으로 접는다(codex P1, REV-20260730T1430).
    """
    path = res_dir / "worker-resources-nan.json"
    # json.dump 는 기본적으로 NaN/Infinity 를 그대로 쓴다(비표준 JSON) — 실제 손상 파일 재현.
    path.write_text(json.dumps({
        "resources": {"llm": {"limit": float("inf"), "peak": float("nan"), "in_use": 0,
                              "acquired": 1, "rejected": float("nan"),
                              "reject_ratio": float("nan")}},
        "conns": {"pg_conns": float("inf")},
        "background_enabled": True, "role": "w",
    }), encoding="utf-8")
    out = ai_ops._worker_resources()
    llm = out["workers"][0]["resources"]["llm"]
    assert llm["limit"] == 0 and llm["peak"] == 0
    assert llm["rejected"] == 0 and llm["reject_ratio"] == 0.0
    # 표준 JSON 으로 직렬화 가능해야 한다(allow_nan=False 가 곧 JSONResponse 계약).
    json.dumps(out, allow_nan=False)


def test_symlink_is_skipped(res_dir, tmp_path):
    """공유 볼륨은 다른 컨테이너도 쓴다 — symlink 를 따라 임의 JSON 을 읽지 않는다(codex P2)."""
    outside = tmp_path.parent / "outside-secret.json"
    outside.write_text(json.dumps({"resources": {}, "conns": {}, "role": "evil"}), encoding="utf-8")
    link = res_dir / "worker-resources-link.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink 미지원 환경")
    out = ai_ops._worker_resources()
    assert out["available"] is False, "symlink 를 따라 읽었다"
    assert not any(w.get("role") == "evil" for w in out["workers"])


def test_bool_values_are_not_counted_as_numbers(res_dir):
    """`True` 는 파이썬에서 int 지만 카운터 값으로는 손상이다 — 제외한다."""
    path = res_dir / "worker-resources-bool.json"
    path.write_text(json.dumps({
        "resources": {"llm": {"limit": 8, "peak": True, "rejected": 0, "reject_ratio": 0.0}},
        "conns": {"pg_conns": True, "ds_conns": 4},
        "background_enabled": True, "role": "w",
    }), encoding="utf-8")
    out = ai_ops._worker_resources()
    w = out["workers"][0]
    assert w["resources"]["llm"]["peak"] == 0      # bool → 0
    assert "pg_conns" not in w["conns"]            # bool 은 카운터 아님
    assert w["conns"]["ds_conns"] == 4

def test_newest_snapshots_win_when_capped(res_dir):
    """★회귀: 표시 상한에 도달해도 **최신 워커가 남는다**(mtime DESC).

    파일명 사전순이면 어느 것이 잘릴지 예측 불가라, 유령 스냅샷이 살아 있는 워커를 밀어낼 수 있다
    (T0c — 라이브에서 스냅샷이 실제로 누적됐다).
    """
    import os
    import time
    now = time.time()
    # 사전순으로는 앞서지만 오래된 파일들 + 사전순 뒤이지만 최신인 파일 1개
    for i in range(ai_ops._WORKER_RES_MAX_FILES + 2):
        p = res_dir / f"worker-resources-aa{i:02d}.json"
        _write(p, role=f"old{i}")
        os.utime(p, (now - 9000 - i, now - 9000 - i))
    newest = res_dir / "worker-resources-zz-current.json"
    _write(newest, role="current")
    os.utime(newest, (now, now))
    out = ai_ops._worker_resources()
    roles = [w["role"] for w in out["workers"]]
    assert "current" in roles, "최신 스냅샷이 상한에 밀려 잘렸다"
    assert len(roles) == ai_ops._WORKER_RES_MAX_FILES

def test_equal_mtime_ordering_is_deterministic(res_dir):
    """mtime 동률이면 경로 오름차순 — tie-break 가 없으면 상한 밖 파일이 실행마다 달라진다(codex P2)."""
    import os
    import time
    now = time.time()
    for name in ("cc", "aa", "bb"):
        p = res_dir / f"worker-resources-{name}.json"
        _write(p, role=name)
        os.utime(p, (now, now))
    first = [w["role"] for w in ai_ops._worker_resources()["workers"]]
    second = [w["role"] for w in ai_ops._worker_resources()["workers"]]
    assert first == second == ["aa", "bb", "cc"], "동률 정렬이 비결정적이다"
