"""band-visual-fit(2026-07-31): 그래프 밴드·칩의 **시각 정합** 계약 (PB-0008 육안검증 기원).

라이브 화면을 확대해 재면서 찾은 두 결함을 소스 불변식으로 고정한다. 둘 다 런타임에만 드러나고
기존 헤드리스 테스트(번들 조립 필요)로는 CI 에서 돌지 않으므로, CI 가 실제로 실행하는 pytest 로
**소스 계약**을 건다(`test_static_cache_integrity.py` 와 같은 방식).

- **F1** 싱글턴 이름-family(`nm:`) 가 밴드로 남으면, 멤버 1개짜리 상자가 헤더·테두리·접기 토글을
  갖춘 채 46-멤버 밴드와 같은 시각 무게로 서고 라벨도 `spget…` 같은 기계 어간이 된다 — 한국어
  의미 라벨(`경매 거래`) 옆에서 분류 체계가 깨진다(라이브 실측: 한 스키마에 3개, 패널에도 동일 노출).
- **F2** 루틴 칩의 `labelMaxWidth` 가 하드코딩 176 이었다. 칩 폭은 `min(190, TW + rel*40)` 이고
  rel 부스트가 없으면 **150** 이라 26px 넘친다 — 라이브에서 아이콘이 알약 왼쪽 밖으로 밀리고
  말줄임표가 오른쪽 밖에 그려졌다. 바로 위 `_metaTableStyle` 주석이 "예전 176 은 rel 부스트로
  최대 190 폭일 때 기준" 이라며 테이블만 `w - 10` 으로 고쳤고 **루틴을 빠뜨린** 자국이 남아 있었다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_GRAPH = Path(__file__).resolve().parents[1] / "src" / "static" / "graph"


def _src(name: str) -> str:
    p = _GRAPH / name
    if not p.exists():
        pytest.skip(f"{name} 부재 — 그래프 정적 자산이 이 feature 에 없다")
    return p.read_text(encoding="utf-8")


# ── F2: 칩 라벨 예산이 박스 폭을 넘지 않는다 ────────────────────────────────

def test_routine_chip_label_budget_is_derived_from_box_width():
    """루틴 칩 `labelMaxWidth` 는 상수가 아니라 **박스 폭 `w` 에서 파생**돼야 한다.

    상수로 두면 폭이 rel 에 따라 150~190 로 변하는데 예산만 고정돼, 좁은 쪽에서 반드시 넘친다."""
    s = _src("graph-roleviz.js")
    m = re.search(r"function _metaRoutineStyle\([^)]*\)\s*\{(.*?)\n\}", s, re.S)
    assert m, "_metaRoutineStyle 을 찾지 못했다"
    body = m.group(1)
    lm = re.search(r"labelMaxWidth:\s*([^,}\n]+)", body)
    assert lm, "_metaRoutineStyle 에 labelMaxWidth 가 없다"
    expr = lm.group(1).strip()
    assert not re.fullmatch(r"\d+", expr), (
        f"labelMaxWidth 가 상수 {expr} 다 — 칩 폭은 min(190, TW+rel*40) 로 변하므로 "
        "좁은 폭에서 라벨이 박스를 넘친다(라이브 실측: 아이콘·말줄임표가 알약 밖으로 렌더)")
    assert "w" in expr, f"labelMaxWidth({expr}) 가 박스 폭 w 에서 파생되지 않았다"


def test_chip_label_budgets_leave_padding_inside_box():
    """테이블·루틴 칩 모두 라벨 예산이 박스 폭보다 작아야 한다(좌우 여백 확보)."""
    s = _src("graph-roleviz.js")
    for fn in ("_metaTableStyle", "_metaRoutineStyle"):
        m = re.search(rf"function {fn}\([^)]*\)\s*\{{(.*?)\n\}}", s, re.S)
        assert m, f"{fn} 을 찾지 못했다"
        assert re.search(r"labelMaxWidth:\s*w\s*-\s*\d+", m.group(1)), (
            f"{fn} 의 labelMaxWidth 가 `w - <여백>` 형태가 아니다 — 박스 안쪽 여백이 보장되지 않는다")


# ── F1: 싱글턴은 밴드가 되지 않는다 ─────────────────────────────────────────

def test_singleton_name_family_is_absorbed_into_misc():
    """싱글턴 흡수에서 `nm:` 을 예외로 두면 안 된다.

    예외의 근거였던 "2차 attach 로 커질 수 있어" 는 이 시점에 이미 성립하지 않는다 — 2차 attach 는
    바로 위에서 끝났고, 여기 남은 `nm:` 싱글턴은 더 자랄 수 없다."""
    s = _src("graph-simgroups.js")
    # 앵커는 이 블록에만 있는 `famOf.forEach((f) => cnt.set(...))` — 파일에 동명 지역변수(cnt)를 쓰는
    #   다른 함수(_metaGenericPrefixes)가 있어 `const cnt = new Map()` 만으로는 엉뚱한 곳을 잡는다.
    m = re.search(r"famOf\.forEach\(\(f\) => cnt\.set\(.*?\);(.*?)\n\s*//", s, re.S)
    assert m, "싱글턴 흡수 블록을 찾지 못했다"
    block = m.group(1)
    assert "famOf.set(t.key, \"misc\")" in block, f"흡수 블록이 아닌 곳을 잡았다: {block[:120]}"
    assert '!f.startsWith("nm:")' not in block, (
        "싱글턴 흡수가 여전히 nm: 을 예외로 둔다 — 멤버 1개짜리 밴드가 `spget… · 1` 로 남는다")
    assert '!f.startsWith("be:")' in block, (
        "be:(백엔드 의미 클러스터) 예외는 유지돼야 한다 — 배정 시점에 이미 ≥2 를 요구하므로 "
        "싱글턴이 될 수 없고, 흡수 대상으로 훑을 이유가 없다")


def test_backend_cluster_requires_two_members_in_schema():
    """`be:` 가 싱글턴이 될 수 없다는 위 테스트의 전제를 배정부에서 직접 고정한다."""
    s = _src("graph-simgroups.js")
    assert re.search(r"beCnt\.get\(be\)\s*>=\s*2", s), (
        "be: 배정이 스키마 내 멤버 ≥2 를 요구하지 않는다 — 싱글턴 be: 밴드가 생길 수 있다")
