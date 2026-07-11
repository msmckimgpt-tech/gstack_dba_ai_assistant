"""feature-0012 ITEM-10 p3 — 프롬프트 컨텍스트 조립 공용 헬퍼 (비-라우트 모듈).

app.py 에서 이동. 소비처가 4개 도메인 라우터(admin_roles/admin_products/auth/conversations)에
분산된 공용 조립 계층이라 특정 도메인 파일이 아닌 본 모듈에 둔다. 모듈명이 `_` 로 시작해
routers/__init__.register_all 의 자동 등록에서 제외된다(라우트 없음).

패치-단일점 규약(판정표 §4): app 전역·패치 대상(setattr 4종)의 호출은 전부 `app.X` 동적 참조 —
테스트의 app-패치가 본 모듈 경유 경로에서도 관통한다. app.py 꼬리 rebind 가 기존
`app._collect_*`/`app._assemble_*` 참조(라우터·테스트·app 내부)를 보존한다.
"""

import asyncio
import logging
import time
from typing import Any

from fastapi import Request

import app  # noqa: F401 — app.X 동적 참조(순환: app 이 본 모듈을 꼬리에서 import — register_all 이후라 안전)


def _collect_matched_excerpts(conn, conv_ids: list[str], q: str) -> dict[str, str]:
    """REQ-20260519-0005 (TASK-0077) + REQ-20260519-0008 (TASK-0080):
    for each matched conversation, return the most-recent matching message body
    excerpt as a line-based clip. Empty dict if no body-search active or no rows.
    Skips on error (snippet is best-effort UX, not a security boundary).

    REQ-20260519-0008 (TASK-0080): scope expanded from AgentMemoryMessages-only
    to UNION (AgentMemoryMessages + AgentCoreMessages). TASK-0072 의
    `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하나,
    TASK-0077 의 excerpt 는 AgentMemoryMessages 한정이라 core-only conv 의
    snippet 이 비어 있던 회귀 차단. UNION 내 ROW_NUMBER OVER (PARTITION BY cid
    ORDER BY created_at DESC) 로 conv 별 더 최근 매칭 1건 선택. (TASK-0200: 두
    table 의 id 가 독립 IDENTITY 시퀀스라 cross-table msg_id 비교가 시간순과
    어긋날 수 있어, 두 table 공통 created_at 기준으로 교정.) ConversationId 의
    (MySQL) collation mismatch 회피 위해 `COLLATE utf8mb4_unicode_ci` 통일.
    """
    if not conv_ids or not q:
        return {}
    escaped = app._escape_like_for_search(q)
    pattern = f"%{escaped}%"
    placeholders = ",".join(["%s"] * len(conv_ids))
    rows: list[Any] = []
    params = (
        *[str(c) for c in conv_ids],
        pattern,
        *[str(c) for c in conv_ids],
        pattern,
    )
    # AR-M5 cutover: AgentMemoryMessages/AgentCoreMessages MySQL 테이블이 DROP 됨 →
    # PG agent_runtime.messages/core_messages 로 라우팅(미라우팅 시 except→{} 로 검색
    # 발췌 스니펫이 항상 빈칸). 후처리(발췌 클리핑)는 DB 무관 — rows(cid, content)만 동일.
    # PG 는 case-insensitive 매칭을 위해 ILIKE 사용(MySQL utf8mb4_unicode_ci 패리티).
    if app._runtime_backend_is_pg():
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    # TASK-0200 MINOR: conv 별 "가장 최근 매칭" 선택을 두 테이블 공통
                    # created_at(timestamptz) 기준으로 정렬. 이전 msg_id 기준은
                    # messages.id 와 core_messages.id 가 독립 IDENTITY 시퀀스라
                    # cross-table 비교가 시간순과 어긋날 수 있었다(발췌 스니펫만 영향).
                    pgcur.execute(
                        f"""
SELECT t.cid, t.content
FROM (
  SELECT cid, content,
         ROW_NUMBER() OVER (PARTITION BY cid ORDER BY created_at DESC) AS rn
  FROM (
    SELECT m.conversation_id AS cid, m.content AS content, m.created_at AS created_at
    FROM agent_runtime.messages m
    WHERE m.conversation_id IN ({placeholders})
      AND m.content ILIKE %s ESCAPE '!'
    UNION ALL
    SELECT cm.conversation_id AS cid, cm.content AS content, cm.created_at AS created_at
    FROM agent_runtime.core_messages cm
    WHERE cm.conversation_id IN ({placeholders})
      AND cm.content ILIKE %s ESCAPE '!'
  ) AS u
) AS t
WHERE t.rn = 1
                        """,
                        params,
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        except Exception:
            return {}
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT t.cid, t.content
FROM (
  SELECT cid, content,
         ROW_NUMBER() OVER (PARTITION BY cid ORDER BY created_at DESC) AS rn
  FROM (
    SELECT m.ConversationId COLLATE utf8mb4_unicode_ci AS cid,
           m.Content AS content,
           m.CreatedAt AS created_at
    FROM AgentMemoryMessages m
    WHERE m.ConversationId IN ({placeholders})
      AND m.Content LIKE %s ESCAPE '!'
    UNION ALL
    SELECT cm.conversation_id COLLATE utf8mb4_unicode_ci AS cid,
           cm.content AS content,
           cm.created_at AS created_at
    FROM AgentCoreMessages cm
    WHERE cm.conversation_id IN ({placeholders})
      AND cm.content LIKE %s ESCAPE '!'
  ) AS u
) AS t
WHERE t.rn = 1
                """,
                params,
            )
            rows = cur.fetchall() or []
        except Exception:
            return {}
        finally:
            cur.close()
    # REQ-20260519-0006 (TASK-0078): excerpt 를 line-based 로 변환. 매칭 위치가 속한
    # line 전체 (이전 \n 직후 ~ 다음 \n 직전) 를 반환해 사용자가 의미 있는 문장 단위로
    # 발췌를 보게 한다. 그 line 이 매우 길 경우 매칭 위치 ±60 char clip + "…".
    result: dict[str, str] = {}
    q_lower = q.lower()
    LINE_MAX = 220  # 한 line 의 최대 길이 — 초과 시 매칭 위치 기준 ±60 char clip
    HALF_WINDOW = 60
    for cid, content in rows:
        text = str(content or "")
        if not text:
            continue
        idx = text.lower().find(q_lower)
        if idx < 0:
            # LIKE 매칭이나 case-insensitive find 실패 (escape edge) — 첫 line 사용.
            first_line = text.split("\n", 1)[0]
            excerpt = first_line if len(first_line) <= LINE_MAX else (first_line[:LINE_MAX] + "…")
        else:
            # 매칭 위치가 속한 line 의 경계 찾기.
            line_start = text.rfind("\n", 0, idx)
            line_start = 0 if line_start == -1 else line_start + 1
            line_end = text.find("\n", idx)
            line_end = len(text) if line_end == -1 else line_end
            line = text[line_start:line_end]
            if len(line) <= LINE_MAX:
                excerpt = line
            else:
                rel = idx - line_start
                start = max(0, rel - HALF_WINDOW)
                end = min(len(line), rel + len(q) + HALF_WINDOW)
                excerpt = line[start:end]
                if start > 0:
                    excerpt = "…" + excerpt
                if end < len(line):
                    excerpt = excerpt + "…"
        result[str(cid)] = excerpt
    return result

def _assemble_product_prompt_llm_request(product_id: int):
    """TASK-0309: 제품 프롬프트 LLM 요청 조립 (request-less, 인증 비포함).

    TASK-0237 의 수집·조립을 인증에서 분리한 코어. 인증 게이트 경로
    (`_collect_product_prompt_context`) 와 무인 자동완성 sweep
    (`_autonomous_generate_product_prompt`) 양쪽이 동일한 ①MySQL 제품/스키마 조회 →
    ②PG 인사이트 수집 → ③knowledge_block 구성 → ④messages/create_kwargs 조립을 공유한다.

    반환: (error_response, context)
      - 제품부재(404)/LLM 클라이언트 부재(503) 시 (JSONResponse, None).
      - 성공 시 (None, dict) — keys: openai_client, create_kwargs, llm_model, max_tokens, meta_base.
        meta_base 는 truncated 를 제외한 meta 전부(LLM 호출 후 truncated 만 덧붙임).
    """
    conn = app._connect_memory()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, ProductKey, Name, Description, DatasourceKey FROM WebProducts WHERE Id = %s",
            (product_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return app._json_error("제품을 찾을 수 없습니다.", 404), None

    prod_id, prod_key, prod_name, prod_desc, prod_ds_key = row

    conn2 = app._connect_memory()
    try:
        cur2 = conn2.cursor()
        cur2.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s",
            (product_id,),
        )
        db_rows = cur2.fetchall()
        # TASK-0228 (1:N): 제품에 바인딩된 **모든** datasource 의 ds 식별자 집합을 모은다 — fact_key
        # 교차노출 차단(아래 매칭). 마이그레이션 진행 중 PG 에 라벨·scope_key 혼재 → 양쪽 다 허용.
        # 단일 바인딩(레거시)이면 primary 1건만(app._list_product_datasources 폴백).
        _bound = app._list_product_datasources(conn2, int(product_id))
        _bound_keys = [b["datasource_key"] for b in _bound if b.get("datasource_key")]
        if not _bound_keys and prod_ds_key:
            _bound_keys = [str(prod_ds_key).strip().lower()]
        ds_keys_allowed: list[str] = []
        for _bk in _bound_keys:
            ds_keys_allowed.append(str(_bk).strip().lower())
            try:
                cur2.execute(
                    "SELECT Engine, Host, Port FROM WebDatasources WHERE DatasourceKey = %s",
                    (_bk,),
                )
                ds_row = cur2.fetchone()
                if ds_row:
                    _eng, _host, _port = ds_row
                    scope_key = app._generate_datasource_key(_eng or "mysql", _host or "", int(_port or 0))
                    if scope_key:
                        ds_keys_allowed.append(scope_key.strip().lower())
            except Exception:
                pass
        # dedup(순서 보존)
        _seen_dsk: set[str] = set()
        ds_keys_allowed = [k for k in ds_keys_allowed if k and not (k in _seen_dsk or _seen_dsk.add(k))]
    finally:
        conn2.close()

    schema_names = [r[0] for r in db_rows]

    # PG 인사이트 수집.
    #
    # fact_key 형식 두 가지 (TASK-0218 datasource-스코프 마이그레이션 진행 중 혼재):
    #   - 구형식:  `{source}:{schema[.table]}`              (예: `table_insight:dbgame.item`)
    #   - 신형식:  `{source}:ds:{ds_key}:{schema[.table]}`  (예: `table_insight:ds:main_mysql:dbgame.item`)
    # `_infer_rag_object_from_fact`(utils.py) 와 동형으로, ds 접두를 제거해 정규화한 뒤
    # 제품이 실제 접근 가능한 스키마명으로 **정확히** 매칭한다. (과거 버그: `source_type` 컬럼은
    # 전부 'schema_insight' 로 들어가 신뢰 불가하고, `scope_key` 는 전부 'common' 이라 ILIKE
    # 매칭이 0건 → 인사이트가 통째로 누락된 채 LLM 이 테이블/컬럼을 날조했음.)
    #
    # source_type 은 fact_key 접두(`schema_insight:` / `table_insight:`)로 판별한다.
    schema_insights: dict[str, str] = {}          # schema -> 스키마 수준 요약 (최고 weight 1건)
    table_insights: dict[str, list[str]] = {}     # schema -> ["table: 설명", ...]
    topic_lines: list[str] = []                   # 대화 topic (최신 50개)
    summary_lines: list[str] = []                 # 대화 summary 샘플 (최신 5개)
    try:
        from shared.db import _pg_connect
        pg_conn = _pg_connect()
        pg_cur = pg_conn.cursor()

        if schema_names:
            # 정규화 키 = ds 접두 제거. `regexp_replace` 로 `{src}:ds:{key}:` → `{src}:`.
            # 매칭은 정규화 키가 `{schema}` 또는 `{schema}.` 로 시작하는지로 판정 (substring ILIKE
            # 가 아니라 boundary 매칭 — `dbgame` 가 `dbgamelog` 를 오탐하지 않게).
            schema_lc = [s.lower() for s in schema_names if s]
            # datasource 교차노출 차단: 제품에 datasource 가 지정돼 있으면 그 datasource 의 ds 세그먼트
            # (라벨 또는 scope_key) 이거나 무접두(레거시 단일 MySQL) fact 만 매칭. 미지정 제품은 종전대로
            # 전체 매칭(하위호환). fact_key 의 ds 세그먼트 = `:ds:{key}:` 의 key, 없으면 빈 문자열.
            pg_cur.execute(
                """
                WITH norm AS (
                    SELECT
                        fe.fact_key,
                        fe.weight,
                        fe.updated_at,
                        t.text_content,
                        split_part(fe.fact_key, ':', 1) AS src_prefix,
                        CASE
                            WHEN fe.fact_key ~ '^(schema_insight|table_insight):ds:'
                            THEN split_part(fe.fact_key, ':', 3)
                            ELSE ''
                        END AS ds_seg,
                        regexp_replace(
                            fe.fact_key,
                            '^(schema_insight|table_insight):ds:[^:]+:',
                            '\\1:'
                        ) AS norm_key
                    FROM public.fact_entries fe
                    JOIN public.texts t ON fe.text_hash = t.text_hash
                ),
                parsed AS (
                    SELECT
                        src_prefix,
                        weight,
                        updated_at,
                        text_content,
                        ds_seg,
                        -- norm_key = `{src}:{schema[.table]}` → 접두 제거 후 object 부분만
                        regexp_replace(norm_key, '^(schema_insight|table_insight):', '') AS obj,
                        norm_key
                    FROM norm
                    WHERE src_prefix IN ('schema_insight', 'table_insight')
                )
                SELECT
                    src_prefix,
                    obj,
                    text_content,
                    weight
                FROM parsed
                WHERE lower(split_part(obj, '.', 1)) = ANY(%s)
                  AND (
                    %s = 0                       -- 제품 datasource 미지정 → 전체 매칭(하위호환)
                    OR ds_seg = ''               -- 무접두 레거시(단일 MySQL) 허용
                    OR lower(ds_seg) = ANY(%s)   -- 제품 datasource 의 ds 세그먼트만
                  )
                ORDER BY weight DESC, updated_at DESC
                """,
                (schema_lc, len(ds_keys_allowed), ds_keys_allowed),
            )
            for src_prefix, obj, text_content, _weight in pg_cur.fetchall():
                if not text_content:
                    continue
                # obj 의 계층 분해 — 제품 접근 단위(WebProductDatabases.SchemaName)는 항상 최상위 segment.
                #   - MySQL(2계층): `{schema}.{table}`        → group=schema, table=table
                #   - MSSQL(3계층): `{database}.{schema}.{table}` → group=database, table=`{schema}.{table}`
                # group(obj_top)이 제품 접근 단위와 매칭된 값이므로 그대로 그룹 키로 쓴다.
                parts = obj.split(".")
                # 그룹 키는 소문자로 통일 — fact_key segment 는 소문자 저장이지만(MSSQL),
                # MySQL schema 명은 대소문자 보존될 수 있어 렌더 lookup(sch.lower())과 정합되게 강제.
                obj_top = parts[0].lower()
                if len(parts) >= 3:
                    table_label = ".".join(parts[1:])  # `dbo.QuestInfo` (스키마.테이블)
                elif len(parts) == 2:
                    table_label = parts[1]
                else:
                    table_label = obj
                if src_prefix == "schema_insight":
                    # 스키마/DB 수준: 최고 weight 1건만 (ORDER BY weight DESC → 첫 등장 보존)
                    if obj_top not in schema_insights:
                        schema_insights[obj_top] = text_content.strip()
                elif src_prefix == "table_insight":
                    # 테이블 수준: 접근 단위별로 묶어 누적 (단위당 상한은 아래 렌더에서 적용)
                    table_insights.setdefault(obj_top, [])
                    if len(table_insights[obj_top]) < 60:
                        table_insights[obj_top].append(
                            f"- `{table_label}`: {text_content.strip()[:300]}"
                        )

        # topic 집계: 이 제품의 대화 제목 최신 50개
        pg_cur.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) AS t
            FROM agent_runtime.core_conversations c
            LEFT JOIN agent_runtime.kv kv
              ON kv.conversation_id = c.conversation_id AND kv.key = 'topic'
            WHERE c.product_id = %s
              AND COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) IS NOT NULL
            ORDER BY c.updated_at DESC
            LIMIT 50
            """,
            (product_id,),
        )
        for (t,) in pg_cur.fetchall():
            if t:
                topic_lines.append(t)

        # summary 샘플: 이 제품의 대화 요약 최신 5개
        pg_cur.execute(
            """
            SELECT s.summary
            FROM agent_runtime.summary s
            JOIN agent_runtime.core_conversations c
              ON c.conversation_id = s.conversation_id
            WHERE c.product_id = %s
              AND s.summary IS NOT NULL AND TRIM(s.summary) <> ''
            ORDER BY s.updated_at DESC
            LIMIT 5
            """,
            (product_id,),
        )
        for (sm,) in pg_cur.fetchall():
            if sm:
                summary_lines.append(sm[:600])

        pg_conn.close()
    except Exception as pg_exc:
        logging.getLogger(__name__).warning("admin_generate_product_prompt PG error: %s", pg_exc)

    # 지식 블록 구성 — 스키마별로 schema_insight + table_insight 를 묶어 구조화.
    sections: list[str] = []
    sections.append(f"제품명: {prod_name}")
    if prod_desc:
        sections.append(f"제품 설명: {prod_desc}")
    # TASK-0228 (1:N): 여러 datasource 에 바인딩됐으면 datasource 별로 접근 가능 DB 를 그룹핑해
    # 보여준다 — 생성될 시스템 프롬프트가 "어느 데이터소스에 어떤 DB 가 있는지" 인지하도록.
    _conn_dsg = app._connect_memory()
    try:
        _ds_groups: list[str] = []
        if len(_bound_keys) >= 2:
            for _bk in _bound_keys:
                _dbs = app._product_allowed_schemas_for_datasource(_conn_dsg, int(product_id), _bk)
                if _dbs:
                    _ds_groups.append(f"- 데이터소스 `{_bk}`: " + ", ".join(_dbs))
                else:
                    _ds_groups.append(f"- 데이터소스 `{_bk}`: (접근 가능 DB 미설정)")
    except Exception:
        _ds_groups = []
    finally:
        _conn_dsg.close()
    if _ds_groups:
        sections.append(
            "이 제품은 **여러 데이터소스**에 연결돼 있습니다. 각 데이터소스의 접근 가능 데이터베이스:\n"
            + "\n".join(_ds_groups)
            + "\n어시스턴트는 질문에 따라 적절한 데이터소스를 선택해 조회하며, 한 질문이 여러 데이터소스를 "
            "참조하면 각각 조회 후 결과를 합쳐 분석합니다. 데이터소스 간 직접 JOIN 은 불가합니다."
        )
    elif schema_names:
        sections.append("접근 가능 데이터베이스(스키마): " + ", ".join(schema_names))

    # 실제 인사이트 데이터 유무 — 지시문 분기 + 응답 메타에 사용.
    total_tables = sum(len(v) for v in table_insights.values())
    has_insights = bool(schema_insights or table_insights)

    if has_insights:
        db_sections: list[str] = []
        for sch in schema_names:
            # fact_key 의 DB/스키마 segment 는 소문자로 저장되므로(set_active_database 가 소문자화),
            # 수집 dict 는 소문자 키. 표시는 제품 등록 원본 대소문자(sch), lookup 은 소문자로.
            sch_lc = str(sch or "").strip().lower()
            sch_block: list[str] = [f"### 스키마 `{sch}`"]
            sch_summary = schema_insights.get(sch_lc)
            if sch_summary:
                sch_block.append(sch_summary)
            tbls = table_insights.get(sch_lc, [])
            if tbls:
                sch_block.append(f"\n**주요 테이블 ({len(tbls)}개):**")
                sch_block.extend(tbls)
            if sch_summary or tbls:
                db_sections.append("\n".join(sch_block))
        if db_sections:
            sections.append(
                "\n## 데이터베이스 구조 (insight-worker 가 실제 스키마를 분석해 축적한 정본)\n\n"
                + "\n\n".join(db_sections)
            )

    if topic_lines:
        sections.append(
            "\n## 사용자가 실제로 요청한 분석 주제 (최근 대화 기준)\n"
            + "\n".join(f"- {t}" for t in topic_lines[:40])
        )

    if summary_lines:
        sections.append(
            "\n## 실제 분석 사례 요약 (과거 대화 결과)\n"
            + "\n\n---\n".join(summary_lines)
        )

    knowledge_block = "\n\n".join(sections)

    # LLM 지시문 — 제공된 실제 인사이트에만 근거하도록 강하게 제약(테이블/컬럼명 날조 금지).
    if has_insights:
        grounding_rule = (
            "절대 규칙:\n"
            "1. 테이블명·컬럼명·스키마명은 아래 '데이터베이스 구조' 섹션에 명시된 것만 사용하세요. "
            "거기 없는 테이블/컬럼을 추측하거나 예시로 지어내지 마세요.\n"
            "2. '데이터베이스 구조'에 없는 정보가 필요하면, 어시스턴트가 런타임에 "
            "`SHOW TABLES` / `DESCRIBE` / `information_schema` 조회로 확인하도록 지시하는 문장을 넣으세요 "
            "(가짜 스키마를 적지 마세요).\n"
            "3. '사용자가 실제로 요청한 분석 주제'를 반영해, 그 유형의 질문에 어떻게 대응할지 "
            "구체적 가이드를 포함하세요.\n"
            "4. 실제 컬럼명이 제공된 테이블은 그 컬럼을 인용해 분석 예시를 들어도 됩니다."
        )
    else:
        # 인사이트가 비었을 때(insight-worker 미실행/마이그레이션 중) — 날조 방지가 더 중요.
        grounding_rule = (
            "주의: 이 제품의 데이터베이스 구조 인사이트가 아직 수집되지 않았습니다. "
            "따라서 구체적인 테이블명·컬럼명을 지어내지 마세요. "
            "대신 어시스턴트가 분석 전 반드시 `SHOW TABLES` / `DESCRIBE` / `information_schema` 로 "
            "실제 스키마를 먼저 탐색하도록 지시하는, 스키마-비의존적인 시스템 프롬프트를 작성하세요."
        )

    llm_model = app._resolve_session_default_model()
    messages = [
        {
            "role": "user",
            "content": (
                "당신은 사내 DB 분석 AI 어시스턴트의 '시스템 프롬프트'를 작성하는 전문가입니다.\n"
                "아래 제품 정보를 바탕으로, 이 제품 전용 어시스턴트가 따라야 할 한국어 시스템 프롬프트를 작성하세요.\n\n"
                "시스템 프롬프트에는 다음을 포함하세요:\n"
                "- 어시스턴트의 역할과 분석 대상 (이 제품의 데이터베이스)\n"
                "- 접근 가능한 각 스키마의 용도와 실제 주요 테이블 설명\n"
                "- 사용자가 자주 요청하는 분석 유형과 대응 방법\n"
                "- SQL 작성·결과 제시 시 주의사항\n\n"
                f"{grounding_rule}\n\n"
                "실무에서 바로 적용 가능한, 구체적이고 완성된 시스템 프롬프트를 작성하세요. "
                "메타 설명 없이 시스템 프롬프트 본문만 출력하세요.\n\n"
                f"=== 제품 정보 ===\n{knowledge_block}"
            ),
        }
    ]

    from modules.llm import _get_llm_client
    openai_client = _get_llm_client(model=llm_model)
    if openai_client is None:
        return app._json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503), None

    # TASK-0232: 자동작성은 "완성된 시스템 프롬프트 본문" 을 생성하므로 짧은 요약용
    # "summary" cap(Claude 7000 / 로컬 512) 으로는 본문이 중간에 잘렸다. 긴 본문 전용
    # "prompt_gen" cap(Claude 20000 / 로컬 3072) 을 사용한다.
    _mt = app.max_tokens_for_model(llm_model, "prompt_gen")
    create_kwargs: dict = {
        "model": llm_model,
        "messages": messages,
        "timeout": 90,
    }
    if _mt is not None:
        create_kwargs["max_tokens"] = _mt
    if app.model_supports_temperature(llm_model):
        create_kwargs["temperature"] = 0.3

    meta_base = {
        "schema_count": len(schema_names),
        "schema_insight_count": len(schema_insights),
        "table_insight_count": total_tables,
        "topic_count": len(topic_lines),
        "summary_count": len(summary_lines),
        "grounded": has_insights,
    }
    return None, {
        "openai_client": openai_client,
        "create_kwargs": create_kwargs,
        "llm_model": llm_model,
        "max_tokens": _mt,
        "meta_base": meta_base,
    }

def _collect_conversation_signals_pg(
    *,
    product_id: "int | None" = None,
    account_ids: "list[int] | None" = None,
    topic_limit: int = 40,
    summary_limit: int = 5,
):
    """대화 패턴 집계 — topic(제목) 목록 + summary(요약) 샘플.

    `_assemble_product_prompt_llm_request` 가 product_id 로 인라인 수집하던 것과 동형이되
    역할/계정 scope 를 위해 필터를 일반화한다:
      - product_id: 그 제품의 대화만 (None = 제품 무관).
      - account_ids: 그 계정들이 **소유**(owner_account_id)한 대화만.
    둘 다 주면 AND. account_ids 가 **빈 list** 면 (대상 계정 없음) 빈 결과를 반환한다 —
    전체 대화로 fallback 하지 않는다(cross-scope 누출 방지). account_ids 가 None 이면
    계정 필터 없음(제품 scope 처럼 전체).

    원문 메시지가 아닌 집계 메타(제목·요약)만 반환한다 — 제품 경로와 동일 privacy 경계.
    반환: (topic_lines, summary_lines).
    """
    topic_lines: list[str] = []
    summary_lines: list[str] = []
    # account_ids 가 명시(빈 list)됐는데 대상이 없으면 — 조회 자체를 생략(전체 누출 방지).
    if account_ids is not None and len(account_ids) == 0:
        return topic_lines, summary_lines

    filters: list[str] = []
    params: list[Any] = []
    if product_id:
        filters.append("c.product_id = %s")
        params.append(int(product_id))
    if account_ids:
        placeholders = ",".join(["%s"] * len(account_ids))
        filters.append(f"c.owner_account_id IN ({placeholders})")
        params.extend(int(a) for a in account_ids)
    filter_sql = "".join(f" AND {f}" for f in filters)

    try:
        from shared.db import _pg_connect
        pg_conn = _pg_connect()
        pg_cur = pg_conn.cursor()
        # topic 집계: 대화 제목 최신순.
        pg_cur.execute(
            f"""
            SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) AS t
            FROM agent_runtime.core_conversations c
            LEFT JOIN agent_runtime.kv kv
              ON kv.conversation_id = c.conversation_id AND kv.key = 'topic'
            WHERE COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) IS NOT NULL
              {filter_sql}
            ORDER BY c.updated_at DESC
            LIMIT %s
            """,
            (*params, int(topic_limit)),
        )
        for (t,) in pg_cur.fetchall():
            if t:
                topic_lines.append(t)
        # summary 샘플: 대화 요약 최신순.
        pg_cur.execute(
            f"""
            SELECT s.summary
            FROM agent_runtime.summary s
            JOIN agent_runtime.core_conversations c
              ON c.conversation_id = s.conversation_id
            WHERE s.summary IS NOT NULL AND TRIM(s.summary) <> ''
              {filter_sql}
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (*params, int(summary_limit)),
        )
        for (sm,) in pg_cur.fetchall():
            if sm:
                summary_lines.append(sm[:600])
        pg_conn.close()
    except Exception as pg_exc:
        logging.getLogger(__name__).warning("_collect_conversation_signals_pg PG error: %s", pg_exc)
    return topic_lines, summary_lines

def _assemble_role_prompt_llm_request(role_id: int):
    """역할 '전체 제품 프롬프트'(role scope, ProductId NULL) LLM 요청 조립 (request-less).

    제품 프롬프트 자동작성과 동형 계약((error, ctx) 반환). 컨텍스트는 **역할 성격**
    (정의·설명·권한 특성) + **그 역할 소속 사용자들의 실제 대화 패턴**(집계 topic·summary).
    생성물은 모든 제품에 공통 누적되는 role-scope 가이드 프롬프트 본문.
    """
    conn = app._connect_memory()
    try:
        role = app._load_role_by_id(conn, int(role_id))
        if not role:
            return app._json_error("역할을 찾을 수 없습니다.", 404), None
        cur = conn.cursor()
        cur.execute(
            "SELECT Id FROM WebAccounts WHERE RoleId = %s AND DeletedAt IS NULL",
            (int(role_id),),
        )
        account_ids = [int(r[0]) for r in (cur.fetchall() or [])]
        cur.close()
        # 이 역할이 접근 가능한 제품(product.access.<key> 권한 보유분) — "전체 제품" 맥락.
        role_codes = set(role.get("permission_codes") or [])
        accessible_products: list[str] = []
        for prod in app._list_products(conn):
            code = app._product_permission_code(str(prod.get("product_key") or ""))
            if code in role_codes:
                accessible_products.append(f"({prod.get('product_key')}) {prod.get('name')}")
    finally:
        conn.close()

    member_count = len(account_ids)
    topic_lines, summary_lines = app._collect_conversation_signals_pg(account_ids=account_ids)

    sections: list[str] = []
    sections.append(f"역할 키: {role.get('key')}")
    sections.append(f"역할 이름: {role.get('name')}")
    role_character = app._describe_role_character(role)
    if role_character:
        sections.append(role_character)
    sections.append(f"이 역할에 속한 사용자 수: {member_count}명")
    if accessible_products:
        sections.append("이 역할이 접근 가능한 제품: " + ", ".join(accessible_products))
    if topic_lines:
        sections.append(
            "\n## 이 역할 사용자가 실제로 요청한 주제 (최근 대화 기준)\n"
            + "\n".join(f"- {t}" for t in topic_lines)
        )
    if summary_lines:
        sections.append(
            "\n## 이 역할 사용자의 실제 분석 사례 요약 (과거 대화 결과)\n"
            + "\n\n---\n".join(summary_lines)
        )
    knowledge_block = "\n\n".join(sections)

    has_signals = bool(topic_lines or summary_lines)
    if has_signals:
        grounding_rule = (
            "절대 규칙:\n"
            "1. 위 '실제로 요청한 주제'·'분석 사례 요약'에 드러난 이 역할 사용자의 실제 사용 패턴을 "
            "반영해, 그 유형의 요청에 어떻게 응대할지 구체적 가이드를 포함하세요.\n"
            "2. 특정 제품의 테이블/컬럼명을 지어내지 마세요 — 이 프롬프트는 모든 제품에 공통 적용되므로 "
            "제품 비의존적이어야 합니다(스키마 세부는 제품별 프롬프트가 담당).\n"
            "3. 역할 권한 특성(조회 전용/질의 가능/관리 등)에 어긋나는 동작을 지시하지 마세요."
        )
    else:
        grounding_rule = (
            "주의: 이 역할의 대화 이력이 아직 충분하지 않습니다. 역할 정의와 권한 특성에 근거해 이 역할 "
            "사용자에게 적용할 공통 응대 원칙을 작성하되, 특정 제품의 테이블/컬럼명이나 구체 데이터를 "
            "지어내지 마세요."
        )

    llm_model = app._resolve_session_default_model()
    messages = [
        {
            "role": "user",
            "content": (
                "당신은 사내 DB 분석 AI 어시스턴트의 '역할(role) 공통 시스템 프롬프트'를 작성하는 전문가입니다.\n"
                "아래 역할 정보와 이 역할 사용자들의 실제 대화 패턴을 바탕으로, 이 역할에 속한 모든 사용자에게 "
                "(제품과 무관하게) 공통 적용할 한국어 시스템 프롬프트를 작성하세요.\n\n"
                "시스템 프롬프트에는 다음을 포함하세요:\n"
                "- 이 역할 사용자의 성격과 어시스턴트가 취할 기본 응대 태도\n"
                "- 이 역할에서 자주 나오는 요청 유형과 그에 대한 응대 방침\n"
                "- 역할 권한 특성에 맞는 경계(예: 조회 전용 역할이면 쓰기/심층분석 이관 안내 방침)\n"
                "- 답변 형식·톤·주의사항\n\n"
                f"{grounding_rule}\n\n"
                "실무에서 바로 적용 가능한, 구체적이고 완성된 시스템 프롬프트를 작성하세요. "
                "메타 설명 없이 시스템 프롬프트 본문만 출력하세요.\n\n"
                f"=== 역할 정보 ===\n{knowledge_block}"
            ),
        }
    ]

    from modules.llm import _get_llm_client
    openai_client = _get_llm_client(model=llm_model)
    if openai_client is None:
        return app._json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503), None

    _mt = app.max_tokens_for_model(llm_model, "prompt_gen")
    create_kwargs: dict = {"model": llm_model, "messages": messages, "timeout": 90}
    if _mt is not None:
        create_kwargs["max_tokens"] = _mt
    if app.model_supports_temperature(llm_model):
        create_kwargs["temperature"] = 0.3

    meta_base = {
        "member_count": member_count,
        "product_count": len(accessible_products),
        "topic_count": len(topic_lines),
        "summary_count": len(summary_lines),
        "grounded": has_signals,
    }
    return None, {
        "openai_client": openai_client,
        "create_kwargs": create_kwargs,
        "llm_model": llm_model,
        "max_tokens": _mt,
        "meta_base": meta_base,
    }

def _assemble_account_prompt_llm_request(account_id: int, role_id: int, product_id: "int | None"):
    """프로필 '제품별 개인 프롬프트'(account scope) LLM 요청 조립 (request-less).

    계정의 역할 성격 + (선택 제품의 이름·용도) + **본인의 실제 대화 패턴**(집계 topic·summary,
    제품 지정 시 그 제품으로 필터) → 이 사용자가 이 제품을 쓸 때 적용할 개인 프롬프트.
    개인 프롬프트는 제품/역할 프롬프트 위에 얹히는 **개인 선호·스타일 레이어**이므로 제품 스키마
    세부를 중복 서술하지 않는다(그건 제품 프롬프트 담당). 동형 계약((error, ctx) 반환).
    """
    conn = app._connect_memory()
    try:
        role = app._load_role_by_id(conn, int(role_id)) if role_id else None
        prod_key = prod_name = prod_desc = None
        if product_id:
            cur = conn.cursor()
            cur.execute(
                "SELECT ProductKey, Name, Description FROM WebProducts WHERE Id = %s",
                (int(product_id),),
            )
            prow = cur.fetchone()
            cur.close()
            if prow:
                prod_key, prod_name, prod_desc = prow
    finally:
        conn.close()

    topic_lines, summary_lines = app._collect_conversation_signals_pg(
        account_ids=[int(account_id)],
        product_id=int(product_id) if product_id else None,
    )

    sections: list[str] = []
    if role:
        sections.append(f"사용자 역할: ({role.get('key')}) {role.get('name')}")
        role_character = app._describe_role_character(role)
        if role_character:
            sections.append(role_character)
    if product_id and prod_name:
        line = f"대상 제품: ({prod_key}) {prod_name}"
        if prod_desc:
            line += f" — {prod_desc}"
        sections.append(line)
    else:
        sections.append("대상 제품: 제품 무관 — 모든 제품에 공통 적용되는 개인 프롬프트")
    if topic_lines:
        sections.append(
            "\n## 내가 실제로 자주 요청한 주제 (최근 대화 기준)\n"
            + "\n".join(f"- {t}" for t in topic_lines)
        )
    if summary_lines:
        sections.append(
            "\n## 내 과거 분석 사례 요약\n"
            + "\n\n---\n".join(summary_lines)
        )
    knowledge_block = "\n\n".join(sections)

    has_signals = bool(topic_lines or summary_lines)
    grounding_rule = (
        "절대 규칙:\n"
        "1. 이것은 제품/역할 프롬프트 위에 얹히는 **개인 선호 레이어**입니다. 제품의 테이블/컬럼 "
        "구조나 분석 방법론을 중복 서술하지 마세요 — 그건 제품 프롬프트가 담당합니다.\n"
        "2. 위 '내가 자주 요청한 주제'에 드러난 이 사용자의 관심사·반복 패턴을 반영해, 답변 형식·"
        "기본 가정·자주 보는 지표 등 개인화된 선호를 간결히 기술하세요.\n"
        "3. 대화 이력이 부족하면 역할 성격에 맞는 일반적 개인 선호(형식·톤·단위 등)만 제안하세요."
    )

    llm_model = app._resolve_session_default_model()
    messages = [
        {
            "role": "user",
            "content": (
                "당신은 사내 DB 분석 AI 어시스턴트 사용자의 '개인 프롬프트'를 작성하는 전문가입니다.\n"
                "개인 프롬프트는 그 사용자의 답변 선호·스타일·기본 가정을 어시스턴트에게 알려주는, "
                "제품/역할 프롬프트 위에 누적되는 개인 레이어입니다.\n"
                "아래 사용자 정보와 실제 대화 패턴을 바탕으로, 이 사용자에게 맞는 한국어 개인 프롬프트를 작성하세요.\n\n"
                "개인 프롬프트에는 다음을 포함하세요:\n"
                "- 이 사용자가 자주 다루는 주제·관심 지표\n"
                "- 선호하는 답변 형식·톤·상세도(예: 표/요약/단위 표기)\n"
                "- 반복적으로 전제하면 좋은 기본 가정\n\n"
                f"{grounding_rule}\n\n"
                "간결하고 바로 적용 가능한 개인 프롬프트 본문만 출력하세요. 메타 설명은 넣지 마세요.\n\n"
                f"=== 사용자 정보 ===\n{knowledge_block}"
            ),
        }
    ]

    from modules.llm import _get_llm_client
    openai_client = _get_llm_client(model=llm_model)
    if openai_client is None:
        return app._json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503), None

    _mt = app.max_tokens_for_model(llm_model, "prompt_gen")
    create_kwargs: dict = {"model": llm_model, "messages": messages, "timeout": 90}
    if _mt is not None:
        create_kwargs["max_tokens"] = _mt
    if app.model_supports_temperature(llm_model):
        create_kwargs["temperature"] = 0.3

    meta_base = {
        "topic_count": len(topic_lines),
        "summary_count": len(summary_lines),
        "product_scoped": bool(product_id),
        "grounded": has_signals,
    }
    return None, {
        "openai_client": openai_client,
        "create_kwargs": create_kwargs,
        "llm_model": llm_model,
        "max_tokens": _mt,
        "meta_base": meta_base,
    }

async def _collect_product_prompt_context(product_id: int, request: Request):
    """TASK-0237: 제품 프롬프트 자동작성 수집·조립의 **인증 게이트** 래퍼.

    인증/`product.manage` 권한을 확인한 뒤 request-less 코어
    (`_assemble_product_prompt_llm_request`) 에 위임한다. 비스트리밍
    (POST /prompt/generate)·스트리밍(GET /prompt/generate/stream) 엔드포인트가
    본 함수를 await 한다(시그니처·반환계약 불변).

    반환: (error_response, context) — 인증/권한 실패 시 (JSONResponse, None),
    그 외는 코어 반환을 그대로 전달.
    """
    conn = app._connect_memory()
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error, None
        if not app._account_has_permission(account, "product.manage"):
            return app._json_error("제품 관리 권한이 필요합니다.", 403), None
    finally:
        conn.close()
    return app._assemble_product_prompt_llm_request(product_id)

async def _collect_role_prompt_context(role_id: int, request: Request):
    """역할 프롬프트 자동작성의 **인증 게이트** 래퍼 — `system_prompt.manage.role.any` 확인 후
    request-less 코어(`_assemble_role_prompt_llm_request`)에 위임. 반환: (error, ctx)."""
    conn = app._connect_memory()
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error, None
        if not app._account_has_permission(account, "system_prompt.manage.role.any"):
            return app._json_error("역할 시스템 프롬프트 관리 권한이 필요합니다.", 403), None
    finally:
        conn.close()
    return app._assemble_role_prompt_llm_request(int(role_id))

async def _collect_account_prompt_context(product_id: "int | None", request: Request):
    """프로필 개인 프롬프트 자동작성의 **인증 게이트** 래퍼 — 본인 인증 + (제품 지정 시) 제품
    접근 권한 확인 + LLM 토큰 quota 게이트 후 request-less 코어
    (`_assemble_account_prompt_llm_request`)에 위임."""
    conn = app._connect_memory()
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error, None
        if product_id is not None and int(product_id) > 0:
            if not app._account_has_product_access(account, int(product_id), conn=conn):
                return app._json_error("요청을 수행할 수 없습니다.", 403), None
        # 자동작성은 LLM 토큰을 직접 소비(에이전트 경로 우회)하므로, self-service 남용 방지를 위해
        # /api/ask 와 동일한 계정 토큰 quota 게이트를 적용한다(REV 적대리뷰 MAJOR 흡수).
        _q_ok, _q_msg = app._check_account_token_quota(conn, account)
        if not _q_ok:
            return app._json_error(_q_msg, 429), None
        acc_id = int(account["id"])
        role_id = int(account.get("role_id") or 0)
    finally:
        conn.close()
    return app._assemble_account_prompt_llm_request(acc_id, role_id, int(product_id) if product_id else None)


# ── ITEM-10 p11 ──

def _prompt_generate_stream_response(ctx: dict, *, log_label: str, log_ctx: str):
    """자동작성 LLM 토큰 스트리밍(SSE) 코어 — product/role/account 엔드포인트 공유.

    LLM stream(동기 generator)은 단일 uvicorn 이벤트 루프를 막지 않도록 **별 스레드 +
    asyncio.Queue 브릿지**로 소비한다. 인증·수집은 호출부에서 이 함수 진입 **전**에 완료
    (실패 시 JSON 403/404/503, SSE 미진입).

    SSE event: progress(stage/label) → token(text 증분, 다수) → done(prompt+meta) | error.
    """
    openai_client = ctx["openai_client"]
    create_kwargs = ctx["create_kwargs"]
    meta_base = ctx["meta_base"]
    llm_model = ctx["llm_model"]
    _mt = ctx["max_tokens"]

    async def event_stream():
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()
        SENTINEL = object()

        def produce():
            # 별 스레드: 동기 LLM stream 을 iterate 하며 call_soon_threadsafe 로 큐 적재.
            # loop 가 닫혔거나 client 가 끊긴 경우 call_soon_threadsafe 가 예외 → 무시(누수 방지).
            def _emit(item):
                try:
                    loop.call_soon_threadsafe(q.put_nowait, item)
                except Exception:
                    pass
            # AI 운영 관제 계측(TASK-AIOPS): usage 는 choices=[] 인 마지막 청크로 오므로
            # include_usage 로 요청하고 choices 가드 앞에서 선포착 → 스트림 완료 후 1회 기록.
            # produce() 는 executor 스레드에서 도므로 회계 PG I/O 가 이벤트 루프를 막지 않는다.
            _aiops_t0 = time.perf_counter_ns()
            _aiops_usage = None
            _aiops_served = None
            try:
                try:
                    stream = openai_client.chat.completions.create(
                        **create_kwargs, stream=True, stream_options={"include_usage": True}
                    )
                except Exception:
                    # AI 운영 관제 계측: stream_options(include_usage)를 거부하는 SDK/게이트웨이
                    # (TypeError 또는 400)로부터 프롬프트 자동작성 스트리밍 기능을 보전 — 계측만 포기하고
                    # stream_options 없이 재시도. 재시도도 실패하면 외곽 except 가 SSE error 로 전달.
                    stream = openai_client.chat.completions.create(**create_kwargs, stream=True)
                for chunk in stream:
                    u = getattr(chunk, "usage", None)
                    if u is not None:
                        _aiops_usage = u
                        _rm = getattr(chunk, "model", None)
                        if _rm:
                            _aiops_served = _rm
                    if not getattr(chunk, "choices", None):
                        continue
                    ch = chunk.choices[0]
                    delta = getattr(getattr(ch, "delta", None), "content", None)
                    if delta:
                        _emit(("token", delta))
                    fr = getattr(ch, "finish_reason", None)
                    if fr is not None:
                        _emit(("finish", fr))
            except Exception as e:  # noqa: BLE001 — 어떤 LLM 오류든 SSE error 로 전달
                _emit(("error", str(e)))
            finally:
                # include_usage 미지원 provider 는 _aiops_usage=None → 기록 스킵(정직 폴백).
                if _aiops_usage is not None:
                    try:
                        from modules.llm import _record_llm_usage
                        from types import SimpleNamespace
                        _shim = SimpleNamespace(
                            usage=_aiops_usage,
                            model=_aiops_served or str(llm_model or ""),
                        )
                        _record_llm_usage(
                            str(llm_model or ""), "prompt_gen", _shim, conversation_id=None,
                            latency_ms=int((time.perf_counter_ns() - _aiops_t0) // 1_000_000),
                        )
                    except Exception:
                        pass
                _emit(("__end__", SENTINEL))

        # 진행 단계 표면화(수집은 이미 끝났으므로 즉시 generating 으로). 사용자에게 "멈춤 아님" 신호.
        yield app._sse_pack("progress", {"stage": "generating", "label": "AI가 프롬프트 작성 중…"})

        loop.run_in_executor(None, produce)

        accumulated: list[str] = []
        truncated = False
        error_msg = None
        while True:
            kind, val = await q.get()
            if kind == "token":
                accumulated.append(val)
                yield app._sse_pack("token", {"text": val})
            elif kind == "finish":
                truncated = (val == "length")
            elif kind == "error":
                error_msg = val
            elif val is SENTINEL:
                break

        if error_msg is not None:
            yield app._sse_pack("error", {"error": f"LLM 생성 실패: {error_msg}"})
            return

        if truncated:
            logging.getLogger(__name__).warning(
                "%s truncated (finish_reason=length, model=%s, max_tokens=%s, %s)",
                log_label, llm_model, _mt, log_ctx,
            )
        yield app._sse_pack("done", {
            "prompt": "".join(accumulated).strip(),
            "meta": {**meta_base, "truncated": truncated},
        })

    return app.StreamingResponse(
        app._counted_stream(event_stream()),  # feature-0014: 무중단 배포 pre-drain 용 스트림 카운트
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ==== feature-0012 ITEM-10 p13 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _load_system_prompt(
    conn,
    *,
    scope: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
) -> dict[str, Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT Id AS id, Scope AS scope, ProductId AS product_id, RoleId AS role_id, AccountId AS account_id,
       Content AS content, UpdatedAt AS updated_at, UpdatedByAccountId AS updated_by_account_id
FROM WebSystemPrompts
WHERE Scope = %s
  AND ((ProductId IS NULL AND %s IS NULL) OR ProductId = %s)
  AND ((RoleId IS NULL AND %s IS NULL) OR RoleId = %s)
  AND ((AccountId IS NULL AND %s IS NULL) OR AccountId = %s)
LIMIT 1
        """,
        (
            scope,
            product_id, product_id,
            role_id, role_id,
            account_id, account_id,
        ),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "id": int(row.get("id") or 0),
        "scope": str(row.get("scope") or ""),
        "product_id": int(row.get("product_id") or 0) or None,
        "role_id": int(row.get("role_id") or 0) or None,
        "account_id": int(row.get("account_id") or 0) or None,
        "content": str(row.get("content") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "updated_by_account_id": int(row.get("updated_by_account_id") or 0) or None,
    }


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _auto_prompt_eligible_product_ids(conn) -> list[int]:
    """자동완성 후보 = 1회성 마커 미설정(AutoPromptGeneratedAt IS NULL) 제품 id.

    프롬프트 입력 여부·분석률은 라이브 조회라 무거우므로 호출부(sweep)가 제품별로 추가 검사한다.
    이미 자동완성된 제품(마커 보유)은 본 단계에서 영구 제외 — insight reset 후 분석률이 재상승해도
    재실행되지 않는 1회성의 핵심 게이트.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT Id FROM WebProducts WHERE AutoPromptGeneratedAt IS NULL ORDER BY Id"
            )
        except Exception:
            # 컬럼 부재(부트스트랩 직전) — _ensure_web_tables 의 멱등 ALTER 이후엔 항상 존재.
            return []
        return [int(r[0]) for r in (cur.fetchall() or [])]
    finally:
        cur.close()

def _auto_prompt_sweep_once() -> dict:
    """후보 제품을 1회 sweep — 프롬프트 미입력 + 분석률>=임계 + 마커 미설정 → 자동완성.

    반환: {scanned, generated, skipped, errors}. 라이브 DB/LLM 조회라 호출부(루프)가 간격을 둔다.
    프롬프트 미입력 검사를 분석률(라이브 카탈로그 조회, 무거움)보다 **먼저** 수행해, 이미
    프롬프트가 있는 제품의 불필요한 coverage 계산을 피한다.
    """
    log = logging.getLogger(__name__)
    stats = {"scanned": 0, "generated": 0, "skipped": 0, "errors": 0}
    try:
        conn = app._connect_memory()
    except Exception as exc:  # noqa: BLE001
        log.warning("auto_prompt sweep: memory 연결 실패 — skip cycle: %r", exc)
        return stats
    try:
        try:
            candidate_ids = app._auto_prompt_eligible_product_ids(conn)
        except Exception as exc:  # noqa: BLE001
            log.warning("auto_prompt sweep: 후보 조회 실패: %r", exc)
            return stats
        if not candidate_ids:
            return stats
        import time as _t
        now = _t.monotonic()
        generated_this_cycle = 0
        products = {int(p["id"]): p for p in app._list_products(conn, include_inactive=True)}
        for pid in candidate_ids:
            product = products.get(pid)
            if not product:
                continue
            stats["scanned"] += 1
            # 1) 프롬프트 미입력만 대상 (이미 있으면 자동완성 안 함).
            if app._product_prompt_present(conn, pid):
                stats["skipped"] += 1
                continue
            # 2) 실패 backoff — 직전 실패 제품은 backoff 창 동안 LLM 재호출 안 함(M1 비용 누수 차단).
            with app._AUTO_PROMPT_FAIL_LOCK:
                fail_until = app._AUTO_PROMPT_FAIL_UNTIL.get(pid, 0.0)
            if fail_until > now:
                stats["skipped"] += 1
                continue
            # 3) 분석률 — coverage API 와 동일 캐시(있으면 재사용, TTL 만료/부재 시 계산).
            cache_key = (pid, product.get("datasource_key") or "")
            cov = app._insight_cov_cache_get(cache_key)
            if cov is None:
                cov = app._compute_product_insight_coverage(conn, product)
                app._insight_cov_cache_put(cache_key, cov)
            pct = cov.get("pct")
            if pct is None or float(pct) < app._AUTO_PROMPT_COVERAGE_THRESHOLD:
                stats["skipped"] += 1
                continue
            # 4) cycle 당 생성 상한 — 비용 버스트 분산(M2). 남은 적격 제품은 다음 cycle 처리.
            if app._AUTO_PROMPT_MAX_PER_CYCLE > 0 and generated_this_cycle >= app._AUTO_PROMPT_MAX_PER_CYCLE:
                break
            # 5) 자동완성·저장·마커.
            res = app._autonomous_generate_product_prompt(pid)
            status = res.get("status")
            if status == "ok":
                stats["generated"] += 1
                generated_this_cycle += 1
                with app._AUTO_PROMPT_FAIL_LOCK:
                    app._AUTO_PROMPT_FAIL_UNTIL.pop(pid, None)
            elif status in ("skip_present", "skip_marked"):
                stats["skipped"] += 1
                with app._AUTO_PROMPT_FAIL_LOCK:
                    app._AUTO_PROMPT_FAIL_UNTIL.pop(pid, None)
            else:  # no_llm / no_body / error — 매 cycle 재호출 방지 backoff (M1).
                stats["errors"] += 1
                with app._AUTO_PROMPT_FAIL_LOCK:
                    app._AUTO_PROMPT_FAIL_UNTIL[pid] = now + app._AUTO_PROMPT_FAIL_BACKOFF_SEC
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if stats["generated"] or stats["errors"]:
        log.info("auto_prompt sweep 완료: %s", stats)
    return stats


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (5종). app 전역은 app.X 동적 참조. ====

async def _counted_stream(agen):
    """async generator 를 감싸 진행 중 스트림 수를 카운트한다(SSE event_stream 용)."""
    with app._ACTIVE_STREAMS_LOCK:
        app._ACTIVE_STREAMS += 1
    try:
        async for chunk in agen:
            yield chunk
    finally:
        with app._ACTIVE_STREAMS_LOCK:
            app._ACTIVE_STREAMS = max(0, app._ACTIVE_STREAMS - 1)

def _product_allowed_schemas_for_datasource(conn, product_id: int, datasource_key: str | None) -> list[str]:
    """TASK-0228 (1:N): 특정 (product, datasource) 의 접근가능 스키마(DB) 목록 — datasource 차원 격리.

    datasource_key=None/'' 은 레거시(단일 MySQL/미차원화) 행 — DatasourceKey='' 으로 저장된 backfill
    이전 행 또는 미바인딩 제품. 매칭은 소문자 비교."""
    if product_id <= 0:
        return []
    dsk = (str(datasource_key).strip().lower() if datasource_key else "")
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
                "ORDER BY SortOrder, SchemaName",
                (int(product_id), dsk),
            )
            return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
        except Exception:
            # DatasourceKey 컬럼 부재(미이전) → 차원 없는 레거시 조회로 폴백.
            cur.execute(
                "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder, SchemaName",
                (int(product_id),),
            )
            return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
    finally:
        cur.close()

def _product_prompt_present(conn, product_id: int) -> bool:
    """제품 시스템 프롬프트(Scope='product')가 비어있지 않게 입력돼 있는지."""
    sp = app._load_system_prompt(conn, scope="product", product_id=int(product_id))
    return bool(sp and str(sp.get("content") or "").strip())

def _describe_role_character(role: "dict[str, Any]") -> str:
    """역할 dict(`_load_role_by_id` 산출)의 권한 특성을 LLM 이 이해할 성격 서술로 변환."""
    codes = set(role.get("permission_codes") or [])
    traits = [phrase for code, phrase in app._ROLE_CAPABILITY_HINTS if code in codes]
    if "conversation.ask" not in codes:
        traits.insert(0, "질의 권한 없음 — 조회 전용 성격")
    lines: list[str] = []
    if role.get("description"):
        lines.append(f"역할 설명: {role['description']}")
    if traits:
        lines.append("주요 권한 특성: " + ", ".join(traits))
    return "\n".join(lines)

def _sse_pack(event: str, payload: dict) -> str:
    """SSE 프레임 직렬화 — `event: <type>\\ndata: <json>\\n\\n`. 한국어 위해 ensure_ascii=False."""
    return f"event: {event}\ndata: {app.json.dumps(payload, ensure_ascii=False)}\n\n"


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _upsert_system_prompt(
    conn,
    *,
    scope: str,
    content: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    updated_by_account_id: int | None = None,
) -> int:
    existing = app._load_system_prompt(
        conn,
        scope=scope,
        product_id=product_id,
        role_id=role_id,
        account_id=account_id,
    )
    cur = conn.cursor()
    content = (content or "").strip()
    if existing:
        if not content:
            cur.execute("DELETE FROM WebSystemPrompts WHERE Id = %s", (int(existing["id"]),))
            cur.close()
            return 0
        cur.execute(
            """
UPDATE WebSystemPrompts
SET Content = %s, UpdatedByAccountId = %s
WHERE Id = %s
            """,
            (content, updated_by_account_id, int(existing["id"])),
        )
        cur.close()
        return int(existing["id"])
    if not content:
        cur.close()
        return 0
    cur.execute(
        """
INSERT INTO WebSystemPrompts (Scope, ProductId, RoleId, AccountId, Content, UpdatedByAccountId)
VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (scope, product_id, role_id, account_id, content, updated_by_account_id),
    )
    new_id = int(cur.lastrowid or 0)
    cur.close()
    return new_id

def _resolve_session_default_model() -> str:
    """env 의 OPENAI_MODEL 이 catalog 안 alias 일 때만 그 값을 사용. 그 외 (미설정 /
    invalid / Local LLM gateway 미가용 시의 'auto' / 폐기된 GPT alias) 는 catalog
    의 API_DEFAULT_MODEL fallback. feature-0007 P1 보강 (CHG-20260522-0002) — 운영
    .env 잔존 'auto' 또는 legacy GPT 값에서 frontend 가 invalid model 을 /api/ask
    에 첨부 후 400 차단되던 회귀 차단. Local LLM gateway 가 실제로 가용한 경우
    (`_is_local_llm_available()` True) 에만 `auto` 가 catalog 에 포함되어 통과 —
    그 외 시점은 API_DEFAULT_MODEL fallback."""
    # TASK-0237: 새 이름 LLM_MODEL 우선, 구이름 OPENAI_MODEL fallback(운영 .env 무중단).
    raw = (app.os.getenv("LLM_MODEL") or app.os.getenv("OPENAI_MODEL") or "").strip()
    if raw and app.is_allowed_api_model(raw):
        # 로컬 LLM 모델(auto/edge/core/code)은 웹 UI 기본값으로 노출하지 않음 —
        # insight-worker 전용. 웹 세션은 항상 Bedrock Claude 계열 기본값 사용.
        if app.is_local_llm_model(raw):
            return app.API_DEFAULT_MODEL
        return raw
    return app.API_DEFAULT_MODEL

def _is_allowed_api_model(value: str) -> bool:
    # 웹 UI /api/ask 에서는 로컬 LLM 모델(auto/edge/core/code) 거부 —
    # insight-worker 전용 모델을 사용자가 직접 지정해 호출하는 경로 차단.
    if app.is_local_llm_model(value):
        return False
    return app.is_allowed_api_model(value)


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (1종). ====

# 역할 성격 서술용 — 시스템 프롬프트 작성에 유의미한 권한 코드만 사람이 읽는 특성 문장으로
# 매핑한다(전체 권한 코드 나열 회피). 순서대로 평가해 보유분만 노출.
_ROLE_CAPABILITY_HINTS: "list[tuple[str, str]]" = [
    ("conversation.ask", "어시스턴트에게 질의·분석 요청 가능"),
    ("conversation.create", "새 대화 생성 가능"),
    ("conversation.read.any", "전체 사용자 대화 열람(관리 범위)"),
    ("conversation.share.create", "대화 공유 가능"),
    ("conversation.attachment.upload.own", "파일 첨부 업로드 가능"),
    ("product.manage", "제품 구성 관리(관리자)"),
    ("console.access", "관리 콘솔 접근(관리자)"),
    ("system_prompt.manage.role.any", "역할/시스템 프롬프트 거버넌스(관리자)"),
]
