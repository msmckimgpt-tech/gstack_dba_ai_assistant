"""ITEM-01 eval metrics.

generation: **execution accuracy**(표준 NL→SQL — Spider/BIRD execution match). 생성SQL
            결과셋과 정답(expected_sql) 결과셋을 정규화 후 행-순서 무관 set 비교. LLM 무관·
            결정적. + execution_success(생성SQL 이 오류 없이 실행).
retrieval:  RAGAS-style precision/recall — 검색된 KB id 대비 ground-truth(relevant_kb_ids).
            ground-truth 없으면 None(=N/A). KB 자산(ITEM-02/05/10) 후 의미를 갖는다.
judge:      (선택) LLM-as-Judge SQL 동치 — execution mismatch 진단용. 비용 cap.
"""
from __future__ import annotations

import datetime
import os
from decimal import Decimal


def _norm_cell(v):
    """셀 값을 비교 가능한 정규형으로. 숫자(int/float/Decimal/숫자문자열)는 ('num', round).

    한계(합성 fixture 전제): 숫자형 문자열을 float 로 강제하므로 '01'==1, '1e3'==1000 같은
    coercion 이 가능하고(zero-pad 코드/과학표기 문자열에서 오탐 위험), bigint>2^53 은 정밀도
    손실. 본 fixture 는 그런 컬럼이 없어 안전하나, 타 datasource 재사용 시 typed 비교로 강화 필요.
    actual 은 agent CSV(문자열), expected 는 typed DB 행이라 비교를 위해 coercion 이 필요하다.
    """
    if v is None:
        return ("null",)
    if isinstance(v, bool):
        return ("num", float(int(v)))
    if isinstance(v, (int, float, Decimal)):
        return ("num", round(float(v), 6))
    if isinstance(v, (datetime.date, datetime.datetime)):
        return ("str", v.isoformat())
    s = str(v).strip()
    try:
        return ("num", round(float(s), 6))
    except (ValueError, TypeError):
        return ("str", s)


def normalize_resultset(rows) -> list:
    """rows(list[tuple|list]) → 행-순서 무관 정규화 정렬 리스트(set 동치 비교용)."""
    norm = [tuple(_norm_cell(c) for c in row) for row in (rows or [])]
    return sorted(norm, key=repr)


def result_equiv(expected_rows, actual_rows) -> bool:
    """expected 와 actual 결과셋이 set-동치인가(execution accuracy)."""
    return normalize_resultset(expected_rows) == normalize_resultset(actual_rows)


def retrieval_precision_recall(retrieved_ids, relevant_ids):
    """RAGAS-style P/R. relevant 없으면 None(N/A)."""
    rel = {str(x) for x in (relevant_ids or [])}
    if not rel:
        return None
    ret = {str(x) for x in (retrieved_ids or [])}
    tp = len(ret & rel)
    precision = (tp / len(ret)) if ret else 0.0
    recall = tp / len(rel)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


# ── LLM-as-Judge (선택, 비용 cap) ──────────────────────────────────────────
_JUDGE_PROMPT = (
    "다음 두 SQL 이 주어진 질문에 대해 의미적으로 동치(같은 결과를 의도)인지 판정하라.\n"
    "질문: {q}\n정답 SQL: {gold}\n생성 SQL: {gen}\n"
    "동치면 정확히 'YES', 아니면 'NO' 한 단어로만 답하라."
)


def llm_sql_judge(nl_question: str, expected_sql: str, generated_sql: str) -> "bool | None":
    """LLM 으로 SQL 동치 판정(temp 0). 실패/미가용 시 None. 호출측이 cap 관리."""
    try:
        from modules.llm import _get_llm_client
        from modules.config import OPENAI_MODEL
    except Exception:
        return None
    client = _get_llm_client()
    if client is None:
        return None
    prompt = _JUDGE_PROMPT.format(q=nl_question, gold=expected_sql, gen=generated_sql)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4,
        )
        ans = (resp.choices[0].message.content or "").strip().upper()
        return ans.startswith("YES")
    except Exception:
        return None


def judge_cap() -> int:
    """LLM-as-Judge 호출 상한(env). 기본 25(비용 cap, 폐쇄망 가드)."""
    try:
        return max(0, int(os.getenv("EVAL_MAX_JUDGE_CALLS", "25")))
    except ValueError:
        return 25
