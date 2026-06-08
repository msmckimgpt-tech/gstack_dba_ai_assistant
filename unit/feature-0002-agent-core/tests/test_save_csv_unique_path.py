"""Regression: #118 — save_csv 파일명 초단위 충돌.

동일 초에 저장된 서로 다른 result set 이 `{ts}_{prefix}.csv` 를 공유해 나중
결과가 앞 결과 파일을 덮어썼다 (open 'w'). 그 결과 "전체 데이터 보기" 버튼이
다른 쿼리의 CSV 를 "전체"로 로드하던 데이터 오염 버그가 발생.

Found by gstack /qa on 2026-06-08 (TASK-0154).
Report: .gstack/qa-reports/qa-report-localhost-2026-06-08.md

라이브 DB 비의존 — 순수 함수 + monkeypatch(시계 고정) 검증.
"""
import os
from datetime import datetime

from modules import render


class _FrozenClock:
    """datetime.now() 를 고정해 '동일 초 저장' 을 강제한다."""

    @staticmethod
    def now(tz=None):
        return datetime(2026, 5, 29, 10, 4, 26)


def test_save_csv_unique_path_within_same_second(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    monkeypatch.setattr(render, "datetime", _FrozenClock)

    # 같은 초·같은 prefix 로 저장되는 서로 다른 두 쿼리 결과.
    p1 = render.save_csv(
        "resultset1", ["TABLE_SCHEMA", "TABLE_NAME"], [["gunzgame", "_currencytype"]]
    )
    p2 = render.save_csv(
        "resultset1", ["COLUMN_NAME", "COLUMN_TYPE"], [["Date", "datetime"]]
    )

    # 경로가 달라야 한다 — 충돌 0.
    assert p1 != p2
    # 두 파일 모두 존재 — 앞 파일이 덮어써지지 않았다.
    assert os.path.exists(p1)
    assert os.path.exists(p2)
    # 각 파일은 자신의 헤더/데이터를 보존한다 (서로 섞이지 않음).
    assert "TABLE_SCHEMA" in open(p1, encoding="utf-8").read()
    assert "COLUMN_NAME" in open(p2, encoding="utf-8").read()


def test_save_csv_keeps_readable_ts_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    monkeypatch.setattr(render, "datetime", _FrozenClock)

    path = render.save_csv("resultset2", ["A"], [["1"]])
    name = os.path.basename(path)
    # 사람이 읽을 수 있는 `{ts}_{prefix}_` 접두 + .csv 확장자는 유지.
    assert name.startswith("20260529_100426_resultset2_")
    assert name.endswith(".csv")
