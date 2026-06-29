"""feature-0012 P5b — route-parity 안전망 (web app router 점진 분할 회귀 게이트).

app.py(feature-0003)를 도메인별 APIRouter 로 점진 분할(P5b)할 때, router 추출/`include_router`
가 등록 경로·메서드·**순서**를 바꾸면(누락·중복·재정렬) 이 테스트가 실패해 "동작 불변
(behavior-neutral)" 위반을 기계적으로 적발한다.

plan-eng-review(Critical) T1: feature-0003 의 60개 테스트 중 HTTP-route 레벨 검증이 거의 없어
`make test` 가 router 분할의 실제 실패모드(경로 등록·순서·배선)를 못 잡는다. 본 스냅샷이 그 격차를 메운다.
TestClient 대신 `app.routes` 정적 열람(startup 훅·DB 불요)이라 `--no-deps` 에서도 동작.

골든 갱신(의도적 route 변경 시): `_build_table()` 출력을 `route_snapshot_p5b.json` 에 덮어쓴다.
"""
import json
from pathlib import Path

import app as appmod  # feature-0003 src on PYTHONPATH (make test)

_GOLDEN = Path(__file__).parent / "route_snapshot_p5b.json"


def _build_table():
    ordered = []
    for r in appmod.app.routes:
        methods = sorted(
            m for m in (getattr(r, "methods", None) or []) if m not in ("HEAD", "OPTIONS")
        )
        ordered.append(
            {"path": getattr(r, "path", None), "methods": methods, "type": type(r).__name__}
        )
    api = [r for r in ordered if r["methods"]]
    return {"total_routes": len(ordered), "api_routes": len(api), "ordered": ordered}


def _pairs(tbl):
    return {(r["path"], m) for r in tbl["ordered"] for m in (r["methods"] or ["<none>"])}


def test_route_table_matches_golden_snapshot():
    current = _build_table()
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))

    # 1) count guard (빠른 신호)
    assert current["total_routes"] == golden["total_routes"], (
        f"route 수 drift: {golden['total_routes']} -> {current['total_routes']} "
        "(P5b router 추출이 경로 누락/중복? 의도적이면 골든 갱신)"
    )
    assert current["api_routes"] == golden["api_routes"]

    # 2) set drift (추가/삭제된 path+method)
    cur_p, gold_p = _pairs(current), _pairs(golden)
    added, removed = sorted(cur_p - gold_p), sorted(gold_p - cur_p)
    assert not added and not removed, (
        f"route set drift — added={added} removed={removed} "
        "(behavior-neutral 위반; 의도적이면 골든 스냅샷 갱신)"
    )

    # 3) order drift (FastAPI 는 등록 순서로 매칭 — {var} vs 구체경로 충돌 존재, plan-eng-review A2)
    cur_ord = [(r["path"], tuple(r["methods"])) for r in current["ordered"]]
    gold_ord = [(r["path"], tuple(r["methods"])) for r in golden["ordered"]]
    if cur_ord != gold_ord:
        for i, (c, g) in enumerate(zip(cur_ord, gold_ord)):
            if c != g:
                raise AssertionError(
                    f"route 등록 순서 drift @index {i}: golden={g} current={c} "
                    "(라우팅 매칭 영향 가능 — 검토 후 골든 갱신)"
                )
        raise AssertionError(f"route 순서 길이 drift: {len(gold_ord)} -> {len(cur_ord)}")
