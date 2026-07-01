"""feature-0016 순수 함수 단위 테스트 (AGE·DB 불요).

metadata_graph 의 값 직렬화·화이트리스트·주입방어 순수 함수를 DB 없이 검증한다.
graphux5(ordinal) 회귀 커버 핵심: `_props_set` 이 ordinal 을 정수 리터럴(따옴표 없음)로 SET 하고,
`_node_dict`/`_node_from_props` 가 ordinal 을 int 로 반환하며, 비정수·None 은 안전히 제외되는지.

실행 (AGE 미필요):
    PYTHONPATH=unit/feature-0002-agent-core/src/modules \
      python3 unit/feature-0016-metadata-graph/tests/test_metadata_graph_units.py
"""
import os
import sys

# metadata_graph 는 shared.db 를 지연 import(연결 헬퍼 내부)하므로 모듈 import 자체엔 DB 불요.
_MODULES = os.environ.get("MG_MODULES_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "..", "feature-0002-agent-core", "src", "modules")
sys.path.insert(0, os.path.abspath(_MODULES))

import metadata_graph as mg  # noqa: E402


def test_props_set_ordinal_int_literal():
    # ordinal 은 정수 리터럴(따옴표 없음) 로 SET — Cypher 숫자.
    out = mg._props_set("n", {"key": "k1", "name": "col", "ordinal": 3})
    assert "n.ordinal = 3" in out, out
    assert "n.ordinal = '3'" not in out, out           # 문자열 리터럴이면 정렬/타입 오류
    assert "n.name = 'col'" in out, out                # 문자열은 그대로 인용


def test_props_set_ordinal_string_coerced():
    out = mg._props_set("n", {"key": "k", "ordinal": "5"})
    assert "n.ordinal = 5" in out, out                 # 문자열 "5" → 정수 5


def test_props_set_ordinal_none_omitted():
    out = mg._props_set("n", {"key": "k", "ordinal": None})
    assert "ordinal" not in out, out                   # None → SET 생략(기존값 보존)


def test_props_set_ordinal_nonint_omitted_injection_safe():
    # 정수화 불가 값은 제외 — 주입 시도가 그대로 통과하지 않음(int() 검증).
    out = mg._props_set("n", {"key": "k", "ordinal": "1); DROP GRAPH"})
    assert "ordinal" not in out, out
    assert "DROP" not in out, out


def test_ordinal_not_in_prop_keys_whitelist_bypass():
    # 화이트리스트 밖 키는 무시(주입 차단).
    out = mg._props_set("n", {"key": "k", "evil": "x", "ordinal": 2})
    assert "evil" not in out, out
    assert "n.ordinal = 2" in out, out


def test_as_int():
    assert mg._as_int(3) == 3
    assert mg._as_int("7") == 7
    assert mg._as_int(None) is None
    assert mg._as_int("abc") is None
    assert mg._as_int("") is None


def test_node_dict_includes_ordinal():
    # search_nodes RETURN 행: (label,key,name,fqn,description,source,ordinal) — agtype 는 문자열로 옴.
    row = ('"Column"', '"ds:db.t.c"', '"c"', '"db.t.c"', '"desc"', '"manual"', "4")
    d = mg._node_dict(row)
    assert d["label"] == "Column" and d["ordinal"] == 4, d
    # ordinal 없는(null) 경우
    row2 = ('"Table"', '"ds:db.t"', '"t"', '"db.t"', "null", "null", "null")
    d2 = mg._node_dict(row2)
    assert d2["ordinal"] is None, d2


def test_node_from_props_includes_ordinal():
    d = mg._node_from_props("Column", {"key": "k", "name": "c", "ordinal": 6})
    assert d["ordinal"] == 6, d
    d2 = mg._node_from_props("Table", {"key": "k", "name": "t"})   # ordinal 부재
    assert d2["ordinal"] is None, d2


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"METADATA_GRAPH UNITS: PASS ({len(fns)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
