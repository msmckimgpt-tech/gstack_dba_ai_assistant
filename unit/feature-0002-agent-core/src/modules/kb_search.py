"""외부 AI용 KB 문자 검색. 인가된 datasource·DB의 공개 스키마 인사이트만 후보로 제공한다."""
from __future__ import annotations

import json
import re

from shared.config import ds_fact_key


def _excerpt(text: str, query: str, cap: int = 1200) -> tuple[str, int]:
    if len(text) <= cap:
        return text, 0
    lower = text.lower()
    terms = [query.lower()] + sorted(set(re.findall(r"\w{2,}", query.lower())), key=len, reverse=True)
    match = next((lower.find(term) for term in terms if term and term in lower), 0)
    start = min(max(0, match - cap // 4), len(text) - cap)
    return text[start:start + cap], start


def search_schema_knowledge(conn, question: str, targets: list[dict], limit: int = 8) -> list[dict]:
    """벡터/LLM 호출 없이 검색한다. targets는 서버가 해석한 접근 범위여야 한다."""
    query = " ".join(str(question or "").split())[:2000]
    allowed = []
    for target in targets:
        scope = str(target.get("scope_key") or "")
        # engine를 포함한 정본 endpoint hash만 인정한다. MSSQL의 과거 무catalog 키는 제외한다.
        if target.get("engine") != "mysql" or not re.fullmatch(r"mysql-[0-9a-f]{12}", scope):
            continue
        databases = [str(db) for db in target.get("allowed_databases") or [] if db]
        if databases:
            allowed.append({
                "schema_prefix": ds_fact_key("schema_insight", "", ds_key=scope),
                "table_prefix": ds_fact_key("table_insight", "", ds_key=scope),
                "databases": databases,
            })
    if not query or not allowed:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            "WITH allowed AS (SELECT * FROM jsonb_to_recordset(%(targets)s::jsonb) "
            "AS a(schema_prefix text, table_prefix text, databases text[])) "
            "SELECT fact_key, content, score FROM ("
            "SELECT d.id, d.fact_key, t.text_content AS content, "
            "GREATEST(word_similarity(%(query)s, d.fact_key), "
            "word_similarity(%(query)s, t.text_content)) AS score "
            "FROM rag_documents d JOIN texts t ON t.text_hash = d.text_hash "
            "WHERE d.conversation_id = '__global__' AND d.scope_key = 'common' "
            "AND d.source_type IN ('schema_insight', 'insight') "
            "AND EXISTS (SELECT 1 FROM allowed a WHERE "
            "(starts_with(d.fact_key, a.schema_prefix) AND "
            "substring(d.fact_key FROM length(a.schema_prefix) + 1) = ANY(a.databases) "
            "AND position(':' IN substring(d.fact_key FROM length(a.schema_prefix) + 1)) = 0) OR "
            "(starts_with(d.fact_key, a.table_prefix) AND EXISTS ("
            "SELECT 1 FROM (SELECT substring(d.fact_key FROM length(a.table_prefix) + 1) AS suffix) s "
            "WHERE position('.' IN s.suffix) > 1 AND right(s.suffix, 1) <> '.' "
            "AND position(':' IN s.suffix) = 0 "
            # DB와 테이블 모두 점을 포함할 수 있으므로 가능한 DB 해석을 전부 인가한다.
            "AND NOT EXISTS (SELECT 1 FROM (SELECT string_to_array(s.suffix, '.') AS parts) p, "
            "generate_series(1, cardinality(p.parts) - 1) AS split(pos) "
            "WHERE NOT array_to_string(p.parts[1:split.pos], '.') = ANY(a.databases)))))) AS candidates "
            "WHERE score >= %(floor)s ORDER BY score DESC, fact_key, id DESC LIMIT %(limit)s",
            {"query": query, "targets": json.dumps(allowed),
             "floor": 0.2, "limit": max(0, min(int(limit), 20))},
        )
        out = []
        for key, content, score in (cur.fetchall() or []):
            content = str(content or "")
            excerpt, start = _excerpt(content, query)
            out.append({"key": str(key), "text": excerpt, "score": float(score),
                        "total_chars": len(content), "excerpt_start": start})
        return out
    finally:
        cur.close()


def load_schema_knowledge_context(question: str, targets: list[dict], conn=None) -> str:
    from shared.db import _pg_conn_pair_ro

    if not targets or not str(question or "").strip():
        return ""
    ro, owned = _pg_conn_pair_ro(conn)
    if ro is None:
        raise RuntimeError("KB read connection unavailable")
    try:
        with ro.transaction():
            ro.execute("SET LOCAL statement_timeout = '5s'")
            rows = search_schema_knowledge(ro, question, targets)
    finally:
        if owned:
            ro.close()
    if not rows:
        return ""
    parts = []
    for row in rows:
        note = ""
        if row["total_chars"] > len(row["text"]):
            start = row["excerpt_start"]
            note = (f" [발췌 {start + 1}–{start + len(row['text'])}/{row['total_chars']}자; "
                    "다른 구간은 focus에 구체 용어를 넣어 재검색]")
        parts.append(f"- {row['key']} (문자 유사도 {row['score']:.3f}){note}\n{row['text']}")
    return "\n\n".join(parts)
