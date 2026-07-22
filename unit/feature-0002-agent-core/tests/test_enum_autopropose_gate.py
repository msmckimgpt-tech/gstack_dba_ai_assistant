"""_enum_autopropose 의 schema-grounding 게이트 wiring 통합 테스트.

순수 판정(is_enum_grounded)은 test_kb_enum_grounding.py 가 커버한다. 본 파일은 그 판정이 실제로
등록 파이프라인에 **배선**되어, 환각 (schema,table) 제안이 auto_promote_or_queue_enum 까지 도달하지
못하게 막는지를 잠근다(적대 패널 QA 공백: `not is_enum_grounded: continue` 분기·flag·fail-open 미검증
→ 조건을 뒤집어도 순수-함수 테스트는 green 이던 문제).
"""
import agent_core
import shared.config as _cfg
import shared.db as _db
from modules import kb_glossary as _kg


# scope=mysql-kr-an1-auth 재현: 카탈로그는 dbAuth 계열만, 제안은 정상 1 + 환각 2.
_SUGGESTIONS = [
    {"schema_name": "dbAuth", "table_name": "AccountBasicInfo", "column_name": "CountryCode",
     "code": "CN", "label": "중국", "confidence": 0.9},                       # grounded
    {"schema_name": "dbLog", "table_name": "Currency", "column_name": "CurrencyType",
     "code": "1", "label": "골드", "confidence": 0.95},                       # 환각 DB
    {"schema_name": "", "table_name": "Currency", "column_name": "CurrencyType",
     "code": "2", "label": "젬", "confidence": 0.95},                         # 환각 table(db無)
]


class _FakePg:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _wire(monkeypatch, *, idx, grounding_on=True, suggestions=None):
    """게이트 주변을 실 PG·LLM 없이 배선하고, auto_promote 로 도달한 (schema,table) 캡처 리스트 반환."""
    reached: list = []
    monkeypatch.setattr(_cfg, "AGENT_ENUM_AUTOPROPOSE", True, raising=False)
    monkeypatch.setattr(_cfg, "AGENT_ENUM_SCHEMA_GROUNDING", grounding_on, raising=False)
    monkeypatch.setattr(_kg, "infer_enum_suggestions",
                        lambda *a, **k: list(suggestions if suggestions is not None else _SUGGESTIONS))
    monkeypatch.setattr(_db, "_pg_available", lambda: True)
    monkeypatch.setattr(_db, "_pg_connect", lambda *a, **k: _FakePg())
    monkeypatch.setattr(agent_core, "_enum_known_table_index", lambda: idx)
    # is_enum_grounded 는 실물 유지(fake idx 로 판정). auto_promote 만 캡처.
    monkeypatch.setattr(_kg, "auto_promote_or_queue_enum",
                        lambda conn, sk, sn, tb, col, cd, lb, **k: reached.append((sn, tb, cd)))
    return reached


def test_gate_blocks_ungrounded_suggestions(monkeypatch):
    idx = _kg.build_known_table_index(["dbAuth.AccountBasicInfo"])
    reached = _wire(monkeypatch, idx=idx)
    agent_core._enum_autopropose("cid", "재화 종류 알려줘", "answer body long enough", "run-1")
    # 정상 dbAuth 만 등록 파이프라인에 도달, 환각 dbLog.Currency·bare Currency 는 차단
    assert reached == [("dbAuth", "AccountBasicInfo", "CN")]


def test_gate_off_lets_all_through(monkeypatch):
    # AGENT_ENUM_SCHEMA_GROUNDING=0 → 게이트 비활성(기존 동작 보존): 3건 전부 도달
    idx = _kg.build_known_table_index(["dbAuth.AccountBasicInfo"])
    reached = _wire(monkeypatch, idx=idx, grounding_on=False)
    agent_core._enum_autopropose("cid", "msg", "answer body long enough", "run-2")
    assert [r[2] for r in reached] == ["CN", "1", "2"]


def test_gate_failopen_when_catalog_unavailable(monkeypatch):
    # 카탈로그 미가용(known_idx=None) → fail-open: 전건 통과(false-reject 방지)
    reached = _wire(monkeypatch, idx=None, grounding_on=True)
    agent_core._enum_autopropose("cid", "msg", "answer body long enough", "run-3")
    assert [r[2] for r in reached] == ["CN", "1", "2"]
