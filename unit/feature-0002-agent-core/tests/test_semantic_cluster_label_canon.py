"""label-canon(2026-07-31): 스키마 간 라벨 어휘 통일 계약.

사용자 리포트("동일한 의미가 다른 이름으로 구성 — 메일 시스템 ↔ 우편 시스템")의 잔여분이다.
같은 스키마 안의 유의어는 `_merge_clusters_by_label` 이 **병합**으로 해소하지만, 스키마가 다르면
두 밴드는 각자 자기 DB 의 객체를 가리키므로 병합하면 안 되고 **라벨 텍스트만** 맞춰야 한다.

라이브 실측(mssql-06656002eda6 · 밴드 2,083 · 스키마 115)에서 같은 게임 DB 의 사본 스키마들이
`거래 시스템`↔`거래 처리`(centroid 0.9998), `아이템 관리`↔`아이템 획득`(0.9998) 처럼 갈렸다.
"""
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

np = pytest.importorskip("numpy")

from modules.semantic_cluster import (  # noqa: E402
    _canonicalize_labels_across_schemas,
    _ws_key,
)


def _unit(*vals):
    v = np.asarray(vals, dtype=np.float64)
    return v / (np.linalg.norm(v) or 1.0)


def _near(base, eps):
    """base 에서 아주 조금 틀어진 단위벡터 — 코사인 유사도 ≈ 1 - eps²/2."""
    v = np.asarray(base, dtype=np.float64).copy()
    v[1] += eps
    return v / (np.linalg.norm(v) or 1.0)


def _row(eff, cid, label, centroid, size):
    return {"eff": eff, "cid": cid, "label": label, "centroid": centroid, "size": size}


# ── 핵심 계약 ────────────────────────────────────────────────────────────────

def test_cross_schema_near_identical_unifies_to_larger_cluster_label():
    """다른 스키마 · 유사도 임계 이상 · 라벨 다름 → 큰 쪽 라벨로 통일."""
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "우편 시스템", base, 4),
        _row("db_b", 0, "메일 시스템", _near(base, 0.01), 9),
    ]
    out = _canonicalize_labels_across_schemas(rows, sim=0.97)
    assert out == {("db_a", 0): "메일 시스템"}, "작은 쪽이 큰 쪽 어휘를 따라야 한다"


def test_same_schema_pair_is_never_touched():
    """같은 스키마의 유의어는 병합(_merge_clusters_by_label)의 관할 — 여기서 손대지 않는다."""
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "경매 기록", base, 3),
        _row("db_a", 1, "경매 시스템", _near(base, 0.005), 7),
    ]
    assert _canonicalize_labels_across_schemas(rows, sim=0.97) == {}


def test_below_threshold_keeps_distinct_vocabulary():
    """임계 미만이면 서로 다른 개념이므로 라벨을 건드리지 않는다."""
    rows = [
        _row("db_a", 0, "우편 시스템", _unit(1.0, 0.0, 0.0), 4),
        _row("db_b", 0, "길드 관리", _unit(0.0, 1.0, 0.0), 9),
    ]
    assert _canonicalize_labels_across_schemas(rows, sim=0.97) == {}


def test_whitespace_variant_unifies_without_similarity():
    """`메일 시스템` 과 `메일시스템` 은 유사도와 무관하게 같은 어휘로 본다(공백만 다름)."""
    rows = [
        _row("db_a", 0, "메일시스템", _unit(1.0, 0.0, 0.0), 3),
        _row("db_b", 0, "메일 시스템", _unit(0.0, 1.0, 0.0), 8),
    ]
    out = _canonicalize_labels_across_schemas(rows, sim=0.97)
    assert out == {("db_a", 0): "메일 시스템"}


def test_ws_key_ignores_spacing_and_case():
    assert _ws_key(" 메일 시스템 ") == _ws_key("메일시스템")
    assert _ws_key("Mail System") == _ws_key("mailsystem")
    assert _ws_key(None) == ""


# ── 안전 장치 ────────────────────────────────────────────────────────────────

def test_same_schema_collision_is_reverted():
    """통일 결과가 한 스키마 안에서 같은 라벨 둘을 만들면, 작은 쪽을 원래 라벨로 되돌린다.

    스키마-내 동일 라벨은 병합·구별(_disambiguate_labels)의 관할이다. 여기서 새로 만들면
    "왜 같은 이름이 둘인가" 가 다시 생긴다."""
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "거래 처리", base, 5),
        _row("db_a", 1, "거래 기록", _near(base, 0.004), 3),
        _row("db_b", 0, "거래 시스템", _near(base, 0.002), 20),
    ]
    out = _canonicalize_labels_across_schemas(rows, sim=0.97)
    # db_a 의 두 밴드가 모두 "거래 시스템" 이 되면 충돌 → 큰 쪽(cid=0)만 유지
    assert out.get(("db_a", 0)) == "거래 시스템"
    assert ("db_a", 1) not in out, "충돌하는 작은 쪽은 원래 라벨을 지켜야 한다"


def test_no_transitive_chaining():
    """A~B, B~C 지만 A~C 가 멀면 A 와 C 를 억지로 한 어휘로 묶지 않는다(1-hop 결정론).

    union-find 를 쓰면 임계를 아슬아슬하게 넘는 연쇄가 서로 무관한 어휘까지 뭉갠다 —
    centroid 병합에서 완전연결을 쓴 것과 같은 이유다."""
    a = _unit(1.0, 0.0, 0.0)
    b = _near(a, 0.22)          # A~B ≈ 0.976
    cvec = np.asarray(b, dtype=np.float64).copy()
    cvec[1] += 0.22
    cvec = cvec / np.linalg.norm(cvec)   # B~C ≈ 0.976, A~C ≈ 0.906
    rows = [
        _row("db_a", 0, "A라벨", a, 10),
        _row("db_b", 0, "B라벨", b, 5),
        _row("db_c", 0, "C라벨", cvec, 3),
    ]
    out = _canonicalize_labels_across_schemas(rows, sim=0.97)
    # B 는 자기 이웃 중 최대인 A 를 따르고, C 는 자기 이웃 중 최대인 B 를 따른다.
    # A 와 C 는 직접 이웃이 아니므로 C 가 A 라벨로 끌려가지 않는다.
    assert out.get(("db_b", 0)) == "A라벨"
    assert out.get(("db_c", 0)) == "B라벨"


def test_tie_on_size_is_deterministic_by_label():
    """멤버 수 동률이면 사전순 최소 — pass 마다 흔들리면 라벨 캐시가 전패한다."""
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "나라벨", base, 5),
        _row("db_b", 0, "가라벨", _near(base, 0.01), 5),
    ]
    out1 = _canonicalize_labels_across_schemas(rows, sim=0.97)
    out2 = _canonicalize_labels_across_schemas(list(reversed(rows)), sim=0.97)
    assert out1 == {("db_a", 0): "가라벨"}
    assert out2 == {("db_a", 0): "가라벨"}, "입력 순서가 결과를 바꾸면 안 된다"


def test_disabled_and_oversized_are_no_ops():
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "우편 시스템", base, 4),
        _row("db_b", 0, "메일 시스템", _near(base, 0.01), 9),
    ]
    assert _canonicalize_labels_across_schemas(rows, sim=0.0) == {}, "임계 0 이하 = 비활성"
    assert _canonicalize_labels_across_schemas(rows, sim=0.97, max_n=1) == {}, "과대 입력은 건너뛴다"


def test_missing_centroid_or_empty_label_is_ignored():
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "우편 시스템", None, 4),        # centroid 없음
        _row("db_b", 0, "", _near(base, 0.01), 9),      # 라벨 없음
        _row("db_c", 0, "메일 시스템", base, 7),
    ]
    assert _canonicalize_labels_across_schemas(rows, sim=0.97) == {}


# ── 임계값 계약 ──────────────────────────────────────────────────────────────

def test_threshold_sits_above_measured_different_label_tail():
    """기본 임계는 실측 '다른 라벨' 쌍 분포의 꼬리보다 위여야 한다.

    라이브 실측(mssql-06656002eda6, 교차-스키마 213만 쌍): 다른 라벨 쌍은 중앙 0.672 · p95 0.788 ·
    **p99 0.848**. 임계가 이 아래로 내려가면 서로 다른 개념의 어휘까지 뭉개진다."""
    from shared import config as _c
    measured_diff_label_p99 = 0.848
    assert _c.AGENT_METADATA_CLUSTER_LABEL_CANON_SIM >= measured_diff_label_p99 + 0.10, (
        "실측 다른-라벨 p99(0.848) 대비 여유가 부족하다 — 어휘가 과통합될 수 있다")
    assert _c.AGENT_METADATA_CLUSTER_LABEL_CANON_SIM <= 1.0
    assert _c.AGENT_METADATA_CLUSTER_LABEL_CANON_MAX_N >= 2083, (
        "라이브 최대 scope(밴드 2,083)를 못 담으면 정작 필요한 곳에서 통일이 꺼진다")


# ── 생성 순서 계약(AST) ──────────────────────────────────────────────────────

def test_summaries_are_generated_after_label_canonicalization():
    """합성 요약은 **어휘 통일 이후**에 생성돼야 한다 — 순서가 뒤집히면 조용히 부정합이 고착된다.

    요약 프롬프트는 `label` 을 입력으로 받는데, 스키마 간 어휘 통일은 모든 스키마를 본 뒤에야
    확정된다. 통일 전에 요약을 만들면 밴드는 `거래 시스템` 인데 요약문은 `거래 처리` 를 말하고,
    요약 캐시 키(멤버셋+L1 지문+L0 지문)에 **라벨이 없어서** 그 불일치가 영구히 남는다.

    런타임에서만 드러나는 순서 결함이라 일반 단위 테스트로는 안 잡힌다 — 소스 구조로 잠근다."""
    import ast

    src_path = _SRC / "modules" / "semantic_cluster.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "run_semantic_cluster_pass"), None)
    assert fn is not None, "run_semantic_cluster_pass 를 찾지 못했다"

    def call_lines(name):
        return [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name]

    canon = call_lines("_canonicalize_labels_across_schemas")
    summ = call_lines("_llm_cluster_summaries")
    assert canon, "어휘 통일 호출이 pass 에서 사라졌다"
    assert summ, "요약 생성 호출이 pass 에서 사라졌다"
    assert max(canon) < min(summ), (
        f"요약 생성(line {min(summ)})이 어휘 통일(line {max(canon)})보다 앞선다 — "
        "통일 전 라벨로 요약이 만들어져 영구 부정합이 된다")


def test_collision_guard_holds_when_incumbent_band_is_smaller():
    """그 라벨을 **이미 갖고 있던** 밴드가 더 작아도 충돌이 생기면 안 된다.

    회귀: 크기만으로 정렬하면 되돌림 대상이 '통일로 바뀐 쪽'이 아니라 '원래 그 라벨이던 쪽'이
    되어 pop 이 no-op 이 되고, 한 스키마 안에 같은 라벨 둘이 그대로 남는다."""
    base = _unit(1.0, 0.0, 0.0)
    rows = [
        _row("db_a", 0, "거래 시스템", _near(base, 0.30), 2),   # 원래부터 이 라벨(작음)
        _row("db_a", 1, "거래 기록", _near(base, 0.004), 9),    # 통일 대상(큼)
        _row("db_b", 0, "거래 시스템", _near(base, 0.002), 20),
    ]
    out = _canonicalize_labels_across_schemas(rows, sim=0.97)
    assert ("db_a", 1) not in out, "이미 같은 라벨을 쓰는 밴드가 있으면 통일하지 않는다"
    final = {("db_a", 0): "거래 시스템", ("db_a", 1): out.get(("db_a", 1), "거래 기록")}
    assert len(set(_ws_key(v) for v in final.values())) == 2, "한 스키마에 같은 라벨 둘이 남으면 안 된다"
