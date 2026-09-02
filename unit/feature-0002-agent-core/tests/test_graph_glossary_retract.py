"""2026-09-02 — 그래프 sync 가 **삭제된 용어를 회수**한다 (AGE MERGE-only 보완).

## 이 테스트가 잠그는 사고 (라이브 실측)

AGE 는 MERGE-only 라 원본이 사라져도 정점이 남는다. 2026-09-01 소급 정리로 `kb_glossary`
105행을 지웠는데 그 용어들이 그래프에 그대로 살아 있었다:

    product.gz_qa_g | 트랜잭션      ← kb_glossary 에서 삭제됨
    product.gz_qa_g | 복합 인덱스   ← 삭제됨
    product.gz_dev  | 정규화        ← 삭제됨

누적분은 수동 회수했지만(78,362 → 68,993 정점), **sync 에 회수 단계가 없으면 다음 삭제에서
그대로 재발한다** — 청소는 원인 제거가 아니다.

## 증분 실행에서는 돌지 않는다 (핵심 안전장치)

증분(`since`)은 「그 시각 이후 변경분」만 조회한다. 그 결과에 없다는 것이 **「DB 에 없다」를
뜻하지 않는다** — 증분에서 회수를 돌리면 **멀쩡한 용어를 전부 지운다**. 전건 조회일 때만
삭제를 판단할 수 있다.
"""
from __future__ import annotations

import inspect

from modules import metadata_graph as G


def _retract_src() -> str:
    src = inspect.getsource(G.sync_graph)
    i = src.index("_step_glossary_retract")
    return src[i:src.index("_run_step(\"kb_glossary_retract\"", i)]


def test_incremental_run_skips_retraction():
    """`since` 가 있으면 **즉시 반환**한다 — 부분 조회로 삭제를 판단하면 안 된다."""
    body = _retract_src()
    assert "if since:" in body, "증분 가드가 없다 — 증분에서 회수하면 멀쩡한 용어를 지운다"
    guard = body[body.index("if since:"):body.index("if since:") + 160]
    assert "return" in guard, "증분에서 회수를 건너뛰지 않는다"
    assert "glossary_retract_skipped" in guard, "건너뛴 사실을 남기지 않는다(무음)"


def test_retraction_is_wired_into_sync():
    """헬퍼가 아니라 **sync 본문에 배선**돼 있다 — 안 부르면 아무 일도 안 일어난다."""
    src = inspect.getsource(G.sync_graph)
    assert '_run_step("kb_glossary_retract", _step_glossary_retract)' in src


def test_retraction_runs_after_projection():
    """투영 **뒤**에 회수한다. 앞이면 이번 사이클에 새로 들어온 용어를 지운다."""
    src = inspect.getsource(G.sync_graph)
    assert src.index('_run_step("kb_glossary", _step_glossary)') < \
           src.index('_run_step("kb_glossary_retract"')


def test_live_set_uses_same_key_builder_as_projection():
    """살아있는 키를 `_vkey` 로 만든다 — 투영과 다른 규칙이면 **전건이 stale 로 보인다**."""
    body = _retract_src()
    assert '_vkey(str(sc), f"term:{t}")' in body, "투영과 같은 키 생성기를 쓰지 않는다"


def test_scope_scoped_run_retracts_only_that_scope():
    """scope 를 지정한 실행은 **그 scope 안에서만** 회수한다(다른 scope 는 조회 범위 밖)."""
    body = _retract_src()
    assert "scope_filter" in body and "g.scope_key" in body


def test_deletion_uses_escaping_helper():
    """리터럴은 `_cq` 로 이스케이프한다 — 용어에 `'` 가 섞이면 손으로 이은 cypher 는 깨진다."""
    body = _retract_src()
    assert "_cq(k)" in body
    assert "DETACH DELETE g" in body


def test_counter_initialized_in_report_template():
    """`glossary_retracted` 가 **0 으로 초기화**돼야 「회수 0건」과 「단계가 안 돌았다」가 갈린다."""
    src = inspect.getsource(G.sync_graph)
    assert '"glossary_retracted": 0' in src


# ── codex 리뷰 P3 (2026-09-02) — AGE key 는 JSON 이다 ─────────────────────────
def test_key_is_json_parsed_not_stripped():
    """AGE 가 돌려준 key 를 **JSON 으로 파싱**한다. `strip('"')` 은 이스케이프를 못 되돌린다.

    실측: 용어에 `"` 나 `\\` 가 있으면 AGE 는 `\\"`·`\\\\` 로 이스케이프해 돌려준다.
    `strip('"')` 은 그것을 복원하지 못하고 `live` 집합(파이썬 raw)과 어긋나
    **멀쩡한 정점이 stale 로 판정돼 삭제된다.**

        'He said "hi"'  → strip 불일치 · json.loads 일치
        'back\\slash'   → strip 불일치 · json.loads 일치
    """
    body = _retract_src()
    assert "json.loads(raw)" in body, "AGE key 를 JSON 으로 파싱하지 않는다"
    # 주석에는 「strip 쓰지 마라」가 적혀 있으므로 **코드 줄만** 본다.
    code = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
    assert "strip(" not in code, "strip 으로 벗기면 특수문자 용어가 오판된다"


def test_unparsable_key_is_skipped_not_deleted():
    """파싱 실패한 키는 **건너뛴다** — 못 읽은 것을 지우는 쪽으로 접으면 되돌릴 수 없다."""
    body = _retract_src()
    i = body.index("except Exception")
    tail = body[i:i + 300]
    assert "continue" in tail, "파싱 실패 시 삭제 쪽으로 흐른다"
    assert "glossary_retract_unparsed" in tail, "파싱 실패를 조용히 넘긴다"


def test_unparsed_counter_initialized():
    src = inspect.getsource(G.sync_graph)
    assert '"glossary_retract_unparsed": 0' in src
