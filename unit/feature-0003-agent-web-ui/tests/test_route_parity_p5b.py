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


def _walk_routes(routes, ordered):
    """app.routes 를 in-order 평탄화. P5b Final: include_router(Starlette 1.x)는 라우트를
    app.routes 에 flatten 하지 않고 path=None 의 컨테이너(_IncludedRouter)로 nest 하므로,
    컨테이너(path 없음 + .routes 보유)는 등록 위치에서 그 하위 라우트로 재귀 전개한다.
    이로써 router 추출 후에도 동일 경로/메서드/순서가 평탄 골든과 1:1 대조된다(StaticFiles 등
    path 보유 Mount 는 단일 leaf 로 기록 — 재귀 안 함)."""
    for r in routes:
        methods = sorted(
            m for m in (getattr(r, "methods", None) or []) if m not in ("HEAD", "OPTIONS")
        )
        path = getattr(r, "path", None)
        # included router 컨테이너의 하위 라우트 접근: Starlette 1.x 의 _IncludedRouter 는
        # .routes 가 아니라 .original_router.routes 에 보관한다. 둘 다 시도.
        sub = getattr(r, "routes", None)
        if sub is None:
            orig = getattr(r, "original_router", None)
            sub = getattr(orig, "routes", None) if orig is not None else None
        if path is None and not methods and sub:
            _walk_routes(sub, ordered)  # included router 컨테이너 → 등록 위치에서 전개
        else:
            ordered.append({"path": path, "methods": methods, "type": type(r).__name__})


def _build_table():
    ordered = []
    _walk_routes(appmod.app.routes, ordered)
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
