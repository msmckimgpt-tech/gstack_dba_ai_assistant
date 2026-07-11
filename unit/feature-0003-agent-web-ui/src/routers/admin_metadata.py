"""feature-0012 P5b Final — admin/metadata 도메인 APIRouter (메타데이터 거버넌스: 용어사전/ENUM/테이블·컬럼 설명/샘플/그래프/부트스트랩/AI 자동완성).

DI 전환 33 핸들러(require_permission RP: kb.ingest.manual / kb.glossary.curate / kb.sample.curate)
+ 이연 1(admin_metadata_suggest — 동적 perm + pre-auth 404 gate, inline auth 유지). uniform
`import app`+`app.X` 동적참조(_metadata_* 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging
import asyncio
import json
import time

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 120  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p2: _metadata_* 헬퍼 20종 app.py 에서 이동(도메인 소유 정상화 — 판정표 §4).
# app 전역은 app.X 동적 참조(패치-단일점). _metadata_llm_complete 호출부는 app.X 유지(테스트 setattr 패치 관통).
def _metadata_resolve_account(request: Request):
    """RBAC(kb.ingest.manual) 게이트. (account, None) 또는 (None, JSONResponse[401/403/500])."""
    try:
        conn = app._connect_memory()
    except Exception:
        return None, app._json_error("db connection failed", 500)
    try:
        account, error = app._require_permission(request, conn, "kb.ingest.manual")
        if error:
            return None, error
        return account, None
    finally:
        conn.close()

def _metadata_valid_scope_keys() -> set[str]:
    """허용 scope_key 집합 — 등록된 datasource 의 **질의 시점 read 와 동일한 scope 해소값** ∪ {'common'}.

    scope-key-unify(死data 수정): 메타데이터/샘플 admin write 의 scope_key 축을 **질의 시점 read 와
    똑같은 식**으로 통일한다. read 는 `agent_core` 가 `cfg.set_active_datasource(_ds.get('scope_key') or
    _ds.get('key'))` 로 활성 scope 를 잡고(= **scope_key 필드 우선, 없으면 라벨**), tools/insight 도 동일
    규약(`ds.get('scope_key') or ds.get('key')`)이다. 즉 DB-등록 ds 는 `scope_key` 필드(compute_scope_key
    해시), .env 레거시 ds 는 그 필드가 없어 **라벨**로 해소된다.

    ⚠️ 주의(BLOCKER 회피): write 를 `_dsr.scope_key(ds)` 로 잡으면 안 된다 — 그 헬퍼는 .env ds(host 필수)에서
    해시를 *계산*하지만 read 는 필드 부재 시 라벨로 떨어지므로, .env ds 에서 write(해시)≠read(라벨) 死data 가
    역으로 재발한다. 그래서 read 와 **동일한 식** `ds.get('scope_key') or ds.get('key')` 를 그대로 쓴다.
    과거엔 admin write 가 datasource **라벨**(all_datasources dict 키)만 저장해 DB-등록 ds 에서 라벨 ≠ 해시
    死data 였다. 'common' 은 항상 허용(공용 사전). 조회 실패 시 'common' 만 허용(보수적).
    """
    keys = {"common"}
    conn = None
    try:
        from shared import datasources as _dsr
        try:
            conn = app._connect_memory()
        except Exception:
            conn = None
        for k, ds in (_dsr.all_datasources(conn) or {}).items():
            # read(agent_core.set_active_datasource)와 동일 해소: scope_key 필드(DB ds=해시) 우선, 없으면 라벨.
            sk = str((ds.get("scope_key") or ds.get("key") or k) or "").strip().lower()
            if sk:
                keys.add(sk)
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    # 폴백: 활성 datasource(ContextVar) 도 허용에 포함(요청 컨텍스트 한정).
    try:
        from shared import config as _cfg
        active = str(_cfg.get_active_datasource() or "").strip().lower()
        if active:
            keys.add(active)
    except Exception:
        pass
    return keys

def _metadata_check_scope(scope_key: str):
    """scope_key 검증 → (normalized, None) 또는 (None, JSONResponse[400]). 빈값/미허용 거부."""
    sk = str(scope_key or "").strip().lower()
    if not sk:
        return None, app._json_error("scope_key 는 필수입니다.", 400)
    if len(sk) > app._METADATA_FIELD_CAPS["scope_key"]:
        return None, app._json_error("scope_key 가 너무 깁니다.", 400)
    allowed = _metadata_valid_scope_keys()
    if sk not in allowed:
        return None, app._json_error("허용되지 않은 scope_key 입니다 (등록된 datasource 또는 'common').", 400)
    return sk, None

def _metadata_valid_role_keys() -> set[str]:
    """허용 role_key 집합 — 등록된 WebRoles.RoleKey ∪ {'*'(공용)}. 조회 실패 시 {'*'}만(보수적).

    용어사전 역할 차원(0021): role_key 는 WebRoles.RoleKey(admin/operator/sales/…) 또는 '*'(공용).
    역할별 비중복 namespace 를 위해 write 시 검증한다(임의 문자열 저장 방지).
    """
    keys = {app._GLOSSARY_COMMON_ROLE}
    conn = None
    try:
        conn = app._connect_memory()
        cur = conn.cursor()
        try:
            cur.execute("SELECT RoleKey FROM WebRoles")
            for row in (cur.fetchall() or []):
                rk = str((row[0] if not isinstance(row, dict) else row.get("RoleKey")) or "").strip().lower()
                if rk:
                    keys.add(rk)
        finally:
            cur.close()
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return keys

def _metadata_check_role_key(role_key, *, default=app._GLOSSARY_COMMON_ROLE):
    """role_key 검증 → (normalized, None) 또는 (None, JSONResponse[400]). 빈값 → default('*')."""
    rk = str(role_key or "").strip().lower()
    if not rk:
        rk = default
    if len(rk) > app._METADATA_FIELD_CAPS["role_key"]:
        return None, app._json_error("role_key 가 너무 깁니다.", 400)
    if rk not in _metadata_valid_role_keys():
        return None, app._json_error("허용되지 않은 role_key 입니다 (등록된 역할 또는 '*' 공용).", 400)
    return rk, None

def _metadata_str_field(data: dict, key: str, *, required: bool = True):
    """문자열 필드 추출+trim+cap 검증 → (value, None) 또는 (None, JSONResponse[400])."""
    val = str((data or {}).get(key) or "").strip()
    if required and not val:
        return None, app._json_error(f"{key} 는 필수입니다.", 400)
    cap = app._METADATA_FIELD_CAPS.get(key)
    if cap is not None and len(val) > cap:
        return None, app._json_error(f"{key} 가 너무 깁니다 (최대 {cap}자).", 400)
    return val, None

async def _metadata_read_json(request: Request) -> dict:
    try:
        body_raw = await request.body()
        data = (await request.json()) if body_raw else {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}

def _metadata_audit(request, account, *, action, resource_id, change_json):
    """audit(memory conn, 별도) — CRUD 는 PG, audit 은 MySQL(cross-DB 분리). best-effort."""
    try:
        mconn = app._connect_memory()
        try:
            app.record_audit_event(
                mconn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action=action,
                resource_type="kb_metadata",
                resource_id=(str(resource_id) if resource_id is not None else None),
                change_json=change_json,
            )
            mconn.commit()
        finally:
            mconn.close()
    except Exception:
        logging.getLogger(__name__).warning("metadata audit 실패 action=%s id=%s", action, resource_id, exc_info=True)

def _metadata_iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)

def _metadata_enum_fields(data: dict):
    """ENUM 공통 필드 추출/검증 → (dict, None) 또는 (None, JSONResponse[400]).

    schema_name 은 선택(빈 문자열 허용 — 단일 스키마 DB), 나머지는 필수.
    """
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return None, e
    column_name, e = _metadata_str_field(data, "column_name")
    if e:
        return None, e
    code, e = _metadata_str_field(data, "code")
    if e:
        return None, e
    label, e = _metadata_str_field(data, "label")
    if e:
        return None, e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return None, e
    return {"table_name": table_name, "column_name": column_name, "code": code,
            "label": label, "schema_name": schema_name}, None

def _metadata_resolve_account_perm(request: Request, perm: str):
    """서브뷰별 RBAC 게이트 — (account, None) 또는 (None, JSONResponse[401/403/500]).
    _metadata_resolve_account(kb.ingest.manual 고정)의 perm 가변 버전(samples=kb.sample.curate)."""
    try:
        conn = app._connect_memory()
    except Exception:
        return None, app._json_error("db connection failed", 500)
    try:
        account, error = app._require_permission(request, conn, perm)
        if error:
            return None, error
        return account, None
    finally:
        conn.close()

def _metadata_qualname(schema_name, table_name) -> str:
    return ".".join([p for p in [str(schema_name or "").strip(), str(table_name or "").strip()] if p])

def _metadata_introspect_table(datasource_key: str, schema_name: str, table_name: str):
    """tables/columns 자동완성 grounding — 대상 테이블의 실제 컬럼 목록을 best-effort 조회.

    부트스트랩 introspection 경로 재사용(RO 유저·dialect-aware·schema allowlist). datasource 미지정
    /'common'/schema 미지정/조회 실패 시 None(=ungrounded — 일반 설명으로 진행). 식별자는
    _safe_ident + load_known_schemas 멤버십으로만 통과(부트스트랩 SQLi 방어와 동일).
    """
    key = str(datasource_key or "").strip().lower()
    schema_name = str(schema_name or "").strip()
    table_name = str(table_name or "").strip()
    if not key or key == "common" or not table_name or not schema_name:
        return None
    ds, scope_key, derr = app._bootstrap_resolve_datasource(key)
    if derr or not ds:
        return None
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    from modules.tools import _safe_ident as _safe_ident_fn
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        safe_table = _safe_ident_fn(table_name)
        cols: list = []
        if engine == "mssql":
            # metadata-table-desc-fix: MSSQL 은 schema_name 이 **database**(부트스트랩 저장 규약과 동일).
            # 시스템 DB 제외 allowlist 로 검증 → 해당 DB 로 연결 → 비시스템 SQL 스키마에서 테이블 컬럼 탐색.
            dialect0 = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect0.system_databases()}
            # §58(적대 리뷰 MAJOR): 저장 라벨이 lower 계약(normalize_db_label)으로 바뀌었으므로
            #   allowlist 를 lower→원본 매핑으로 case-insensitive 매치하고 **연결은 원본 케이스**로
            #   한다(kb_metadata 의 LOWER 매칭 계약과 동형). 케이스-정확 set 이면 lower 라벨의
            #   membership 이 항상 실패해 grounding 이 무음 파괴된다(CS collation 서버 안전 겸비).
            db_map = {str(n).strip().lower(): str(n) for n in (_db.list_server_databases(ds) or [])
                      if str(n).strip().lower() not in sys_db}
            safe_db = _safe_ident_fn(schema_name)
            real_db = db_map.get(str(safe_db).strip().lower())
            if not real_db:
                return None
            conn = _db.connect(datasource=ds, database=real_db, autocommit=True)
            dialect = _dialects.active()
            sys_schema = {str(n).strip().lower() for n in dialect.system_schemas()}
            real_schemas = [s for s in (_schema.load_known_schemas(conn) or [])
                            if str(s).strip().lower() not in sys_schema]
            for sql_schema in real_schemas:
                ss = _safe_ident_fn(sql_schema)
                cur = conn.cursor()
                try:
                    cur.execute(dialect.describe_columns(ss, safe_table))
                    for crow in (cur.fetchall() or []):
                        if crow and crow[0]:
                            cols.append({"column_name": str(crow[0]), "data_type": str(crow[1] or "").lower()})
                        if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                            break
                except Exception:
                    cols = []
                finally:
                    cur.close()
                if cols:
                    break  # 테이블을 담은 첫 SQL 스키마에서 종료(DB명 평탄화와 정합)
        else:
            conn = _db.connect(datasource=ds, autocommit=True)
            known = set(_schema.load_known_schemas(conn) or [])
            safe_schema = _safe_ident_fn(schema_name)
            if safe_schema not in known:
                return None
            dialect = _dialects.active()
            cur = conn.cursor()
            try:
                cur.execute(dialect.describe_columns(safe_schema, safe_table))
                for crow in (cur.fetchall() or []):
                    if crow and crow[0]:
                        cols.append({"column_name": str(crow[0]), "data_type": str(crow[1] or "").lower()})
                    if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                        break
            finally:
                cur.close()
        return {"schema_name": schema_name, "table_name": table_name, "columns": cols} if cols else None
    except Exception:
        logging.getLogger(__name__).warning(
            "metadata suggest introspection 실패 ds=%s schema=%s table=%s", key, schema_name, table_name, exc_info=True
        )
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass

def _metadata_grounding_cols_line(grounding) -> str:
    if not grounding or not grounding.get("columns"):
        return ""
    cols = grounding["columns"][:60]
    names = ", ".join(
        (f"{c['column_name']}({c['data_type']})" if c.get("data_type") else c["column_name"]) for c in cols
    )
    return f"이 테이블의 실제 컬럼: {names}\n"

def _metadata_grounding_coltype(grounding, column_name) -> str:
    if not grounding or not column_name:
        return ""
    target = str(column_name).strip().lower()
    for c in (grounding.get("columns") or []):
        if str(c.get("column_name") or "").strip().lower() == target:
            return c.get("data_type") or ""
    return ""

def _metadata_suggest_messages(sub: str, fields: dict, grounding) -> list:
    """서브뷰별 자동완성 프롬프트 — 식별 필드 → 설명/정의/라벨/질문 1건. 본문만 출력하도록 지시."""
    f = fields
    if sub == "glossary":
        body = (
            "당신은 사내 데이터 분석 용어사전을 작성하는 전문가입니다.\n"
            f"다음 도메인 용어의 '정의'를 한국어 1~3문장으로 간결하게 작성하세요.\n"
            f"용어: {f.get('term', '')}\n"
            "판정 기준·계산 방식이 있으면 한 줄로 포함하세요. 정의 본문만 출력하고 따옴표·머리말을 붙이지 마세요."
        )
    elif sub == "enums":
        body = (
            "당신은 데이터베이스 코드값의 의미 라벨을 다는 전문가입니다.\n"
            f"테이블 {f.get('table_name', '')}, 컬럼 {f.get('column_name', '')} 의 코드 값 "
            f"'{f.get('code', '')}' 가 의미하는 한국어 라벨(짧은 명사구)을 출력하세요.\n"
            "라벨 텍스트만 출력하고 설명·따옴표·머리말을 붙이지 마세요."
        )
    elif sub == "tables":
        cols_line = _metadata_grounding_cols_line(grounding)
        body = (
            "당신은 데이터베이스 테이블 카탈로그를 작성하는 전문가입니다.\n"
            f"테이블 {_metadata_qualname(f.get('schema_name'), f.get('table_name'))} 가 담는 데이터와 용도를 "
            "한국어 1~3문장으로 설명하세요.\n"
            f"{cols_line}"
            "설명 본문만 출력하고 머리말·따옴표를 붙이지 마세요. 실제 컬럼이 주어졌으면 그에 근거하고, "
            "없으면 일반적이되 단정적이지 않게 작성하세요."
        )
    elif sub == "columns":
        dtype = _metadata_grounding_coltype(grounding, f.get("column_name"))
        body = (
            "당신은 데이터베이스 컬럼 사전을 작성하는 전문가입니다.\n"
            f"컬럼 {_metadata_qualname(f.get('schema_name'), f.get('table_name'))}.{f.get('column_name', '')}"
            f"{(' (' + dtype + ')') if dtype else ''} 이 담는 값과 의미를 한국어 1~2문장으로 설명하세요.\n"
            "설명 본문만 출력하고 머리말·따옴표를 붙이지 마세요."
        )
    else:  # samples
        body = (
            "당신은 SQL 의 의도를 자연어 질문으로 옮기는 전문가입니다.\n"
            "다음 SQL 이 답하는 자연어 질문을 한국어 1문장으로 작성하세요.\n"
            f"SQL:\n{f.get('sql', '')}\n"
            "질문 문장만 출력하고 머리말·따옴표·SQL 재출력을 하지 마세요."
        )
    return [{"role": "user", "content": body}]

def _metadata_bulk_describe_messages(mode: str, tables: list) -> list:
    """골격 일괄 자동완성 프롬프트 — JSON 객체로만 응답하도록 강하게 지시."""
    lines = []
    for t in tables:
        q = _metadata_qualname(t.get("schema_name"), t.get("table_name"))
        if mode == "columns":
            cols = ", ".join(
                (f"{c['column_name']}({c['data_type']})" if c.get("data_type") else c["column_name"])
                for c in (t.get("columns") or [])
            )
            lines.append(f"- {q}: {cols or '(컬럼 정보 없음)'}")
        else:
            cols = ", ".join(c["column_name"] for c in (t.get("columns") or [])[:40])
            lines.append(f"- {q} (컬럼: {cols or '없음'})")
    skeleton = "\n".join(lines)
    if mode == "tables":
        instruction = (
            "각 테이블이 담는 데이터/용도를 한국어 1~2문장으로 설명하세요.\n"
            "반드시 아래 JSON 객체로만 출력하세요(키=테이블 이름, 값=설명 문자열). 코드펜스·다른 텍스트 금지:\n"
            '{"테이블이름": "설명", ...}'
        )
    else:
        instruction = (
            "각 컬럼이 담는 값/의미를 한국어 1문장으로 설명하세요.\n"
            "반드시 아래 중첩 JSON 객체로만 출력하세요(키=테이블 이름, 값={컬럼 이름: 설명}). 코드펜스·다른 텍스트 금지:\n"
            '{"테이블이름": {"컬럼이름": "설명", ...}, ...}'
        )
    body = (
        "당신은 데이터베이스 카탈로그를 작성하는 전문가입니다. 아래 스키마 골격에 설명을 작성합니다.\n\n"
        f"=== 골격 ===\n{skeleton}\n\n{instruction}"
    )
    return [{"role": "user", "content": body}]

def _metadata_parse_json_object(text):
    """LLM 출력에서 JSON 객체 추출 — 코드펜스/전후 텍스트 허용. 실패 시 None."""
    if not text:
        return None
    s = str(text).strip()
    if s.startswith("```"):
        # ```json ... ``` 또는 ``` ... ``` 펜스 제거.
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip()[:4].lower() == "json":
                s = s.lstrip()[4:]
    s = s.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    try:
        i = s.index("{")
        j = s.rindex("}")
        obj = json.loads(s[i:j + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

def _metadata_bulk_shape_results(mode: str, tables: list, parsed: dict) -> list:
    """LLM JSON 응답을 프론트가 입력란에 매칭할 수 있는 리스트로 정형(대소문자/공백 무시 매칭)."""
    out: list = []
    pidx = {str(k).strip().lower(): v for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    cap = app._METADATA_FIELD_CAPS["description"]
    for t in tables:
        tname = t["table_name"]
        pv = pidx.get(tname.strip().lower())
        if mode == "tables":
            if isinstance(pv, str) and pv.strip():
                out.append({"schema_name": t.get("schema_name", ""), "table_name": tname,
                            "description": pv.strip()[:cap]})
        else:
            if isinstance(pv, dict):
                cidx = {str(k).strip().lower(): v for k, v in pv.items()}
                for c in (t.get("columns") or []):
                    cv = cidx.get(c["column_name"].strip().lower())
                    if isinstance(cv, str) and cv.strip():
                        out.append({"schema_name": t.get("schema_name", ""), "table_name": tname,
                                    "column_name": c["column_name"], "description": cv.strip()[:cap]})
    return out

async def _metadata_llm_complete(messages: list, *, task: str = "summary", temperature: float = 0.3):
    """메타데이터 AI 자동완성 공용 LLM 호출(비스트리밍). (text, meta, None) 또는 (None, None, JSONResponse).

    admin_generate_product_prompt 비스트리밍 경로와 동일 패턴 — 단일 uvicorn 루프를 막지 않도록
    run_in_executor 로 동기 호출을 오프로드. task = max_tokens cap 키('summary'=단건, 'prompt_gen'=일괄).
    """
    from modules.llm import _get_llm_client
    llm_model = app._resolve_session_default_model()
    client = _get_llm_client(model=llm_model)
    if client is None:
        return None, None, app._json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503)
    create_kwargs: dict = {"model": llm_model, "messages": messages, "timeout": 60}
    mt = app.max_tokens_for_model(llm_model, task)
    if mt is not None:
        create_kwargs["max_tokens"] = mt
    if app.model_supports_temperature(llm_model):
        create_kwargs["temperature"] = temperature

    def _aiops_create_and_record():
        # AI 운영 관제 계측(TASK-AIOPS): create + 회계를 executor 스레드에서 함께 실행(이벤트 루프 무영향).
        # task 는 reasoning 'summary' 와 구분되게 metadata_ 접두(taxonomy: ai.metadata.autocomplete).
        _t0 = time.perf_counter_ns()
        r = client.chat.completions.create(**create_kwargs)
        try:
            from modules.llm import _record_llm_usage
            _record_llm_usage(
                str(llm_model or ""), f"metadata_{task}", r, conversation_id=None,
                latency_ms=int((time.perf_counter_ns() - _t0) // 1_000_000),
            )
        except Exception:
            pass
        return r

    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, _aiops_create_and_record)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        truncated = getattr(choice, "finish_reason", None) == "length"
    except Exception as exc:  # noqa: BLE001 — 어떤 LLM 오류든 502 로 변환
        return None, None, app._json_error(f"LLM 생성 실패: {exc}", 502)
    return text, {"model": llm_model, "truncated": truncated}, None


# ── graph-perf-bg: /graph/columns introspection TTL 캐시 ──────────────────────────
#   /api/admin/metadata/graph/columns 는 그래프 투영에 Column 노드가 없는 테이블을 (더블)클릭할 때마다
#   데이터소스 information_schema 를 **라이브 조회**했다 — 요청 스레드를 1~5초 블로킹하고 무캐시라, 펼침
#   임계경로(그래프 fetch + columns fetch 2왕복)의 두 번째 왕복이 매번 재수행됐다. 성공한 introspection 을
#   (scope_key, fqn) 키로 짧은 TTL(기본 300s) 동안 프로세스 내 캐시해 반복 펼침·다중 사용자·재진입 왕복을
#   제거한다. **실패/빈 결과는 캐시하지 않는다**(일시 오류 재시도 보장). DDL 변경은 TTL 만료 후 자동 반영.
#   프로세스별 캐시라 마이그레이션 불필요(alembic 병렬 충돌 회피). TTL<=0 이면 캐시 비활성(테스트/디버그).
import os as _os
import time as _time
import threading as _threading

_COLUMNS_CACHE = {}                        # (scope_key, fqn) -> (expires_at_monotonic, payload_dict)
_COLUMNS_CACHE_LOCK = _threading.Lock()
_COLUMNS_CACHE_MAX = 512                    # 무한 성장 방지 상한


def _graph_columns_cache_ttl() -> float:
    try:
        return float(_os.environ.get("METADATA_GRAPH_COLUMNS_CACHE_TTL", "300") or 300)
    except (TypeError, ValueError):
        return 300.0


def _graph_columns_cache_get(scope_key: str, fqn: str):
    """유효 캐시 payload 반환(없거나 만료면 None). 만료 항목은 조회 시 청소."""
    if _graph_columns_cache_ttl() <= 0:
        return None
    now = _time.monotonic()
    with _COLUMNS_CACHE_LOCK:
        item = _COLUMNS_CACHE.get((scope_key, fqn))
        if not item:
            return None
        exp, payload = item
        if exp <= now:
            _COLUMNS_CACHE.pop((scope_key, fqn), None)
            return None
        return payload


def _graph_columns_cache_put(scope_key: str, fqn: str, payload) -> None:
    """성공 introspection payload 를 TTL 캐시. 상한 초과 시 만료 항목 청소 후 최소-만료 항목 축출."""
    ttl = _graph_columns_cache_ttl()
    if ttl <= 0:
        return
    now = _time.monotonic()
    with _COLUMNS_CACHE_LOCK:
        if len(_COLUMNS_CACHE) >= _COLUMNS_CACHE_MAX:
            for k in [k for k, (e, _p) in _COLUMNS_CACHE.items() if e <= now]:
                _COLUMNS_CACHE.pop(k, None)
            while len(_COLUMNS_CACHE) >= _COLUMNS_CACHE_MAX:
                _COLUMNS_CACHE.pop(min(_COLUMNS_CACHE, key=lambda k: _COLUMNS_CACHE[k][0]), None)
        _COLUMNS_CACHE[(scope_key, fqn)] = (now + ttl, payload)


@router.get("/api/admin/metadata/glossary")
def admin_list_glossary(request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """용어 목록 — 단일 scope(역할 차원 포함). 권한 kb.ingest.manual.

    ?scope_key= (기본 'common'). ?role_key= 지정 시 그 역할 행만(공용 '*' 미포함) 필터 — 역할별
    조회. 미지정이면 scope 의 모든 역할 행(role_key 필드로 구분 표시).
    """
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    role_filter = None
    rk_param = request.query_params.get("role_key")
    if rk_param is not None and str(rk_param).strip() != "":
        role_filter, rerr = _metadata_check_role_key(rk_param)
        if rerr:
            return rerr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_admin(pg, scope_key, role_key=role_filter)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary 조회 실패", exc_info=True)
        return app._json_error("용어 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, role_key, term, definition, source, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
        "term": str(r[3] or ""), "definition": str(r[4] or ""), "source": str(r[5] or "manual"),
        "created_at": _metadata_iso(r[6]), "updated_at": _metadata_iso(r[7]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "role_key": role_filter})

@router.post("/api/admin/metadata/glossary")
async def admin_create_glossary(request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """용어 생성(upsert). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    role_key, rerr = _metadata_check_role_key(data.get("role_key"))
    if rerr:
        return rerr
    term, terr = _metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = _metadata_str_field(data, "definition")
    if derr:
        return derr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_glossary_term(pg, scope_key, term, definition, role_key=role_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_glossary 실패", exc_info=True)
        return app._json_error("용어 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.term.create",
                    resource_id=f"{scope_key}:{role_key}:{term}",
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term})
    return JSONResponse({"ok": True, "scope_key": scope_key, "role_key": role_key, "term": term})

@router.put("/api/admin/metadata/glossary/{term_id}")
async def admin_update_glossary(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """용어 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    # role_key 는 선택 — 본문에 있으면 역할 귀속까지 변경(공용↔역할 이동), 없으면 기존 유지.
    role_key = None
    if "role_key" in (data or {}) and str(data.get("role_key") or "").strip() != "":
        role_key, rerr = _metadata_check_role_key(data.get("role_key"))
        if rerr:
            return rerr
    term, terr = _metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = _metadata_str_field(data, "definition")
    if derr:
        return derr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_glossary_term(pg, int(term_id), scope_key, term, definition,
                                            role_key=role_key)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 용어를 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,role,term) 충돌 → 409 (같은 역할에 동일 용어 존재).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("같은 역할에 동일 용어가 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.term.update",
                    resource_id=int(term_id),
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term})
    return JSONResponse({"ok": True, "id": int(term_id)})

@router.delete("/api/admin/metadata/glossary/{term_id}")
def admin_delete_glossary(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """용어 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_term(pg, int(term_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # 멱등 — affected=0(이미 없음)도 성공. audit 은 실제 삭제(affected>0)만 기록.
    if affected > 0:
        _metadata_audit(request, account, action="glossary.term.delete",
                        resource_id=int(term_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(term_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/glossary-feedback")
def admin_list_glossary_feedback(request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 목록. 권한 kb.glossary.curate. ?status=(기본 pending, 'all'=전체) &scope_key= &role_key=."""
    status = str(request.query_params.get("status") or "pending").strip().lower()
    if status in ("all", ""):
        status = None
    elif status not in ("pending", "auto_promoted", "promoted", "rejected"):
        return app._json_error("허용되지 않은 status 입니다.", 400)
    scope_filter = None
    sk_param = request.query_params.get("scope_key")
    if sk_param is not None and str(sk_param).strip() != "":
        scope_filter, serr = _metadata_check_scope(sk_param)
        if serr:
            return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_feedback(pg, status=status, scope_key=scope_filter)
        pending_count = _kg.count_glossary_feedback(pg, status="pending")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_feedback 조회 실패", exc_info=True)
        return app._json_error("검토 큐 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, role_key, term, suggested_definition, confidence, status,
    #       source_run_id, conversation_id, promoted_glossary_id, approved_by, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
        "term": str(r[3] or ""), "suggested_definition": str(r[4] or ""),
        "confidence": float(r[5]) if r[5] is not None else None, "status": str(r[6] or ""),
        "source_run_id": (str(r[7]) if r[7] is not None else None),
        "conversation_id": (str(r[8]) if r[8] is not None else None),
        "promoted_glossary_id": (int(r[9]) if r[9] is not None else None),
        "approved_by": (str(r[10]) if r[10] is not None else None),
        "created_at": app._glossary_feedback_iso(r[11]), "updated_at": app._glossary_feedback_iso(r[12]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items),
                         "pending_count": int(pending_count), "status": status})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/promote")
def admin_promote_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐(pending) → 용어사전 승급. 권한 kb.glossary.curate."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        gid = _kg.promote_glossary_feedback(
            pg, int(feedback_id), approved_by=str((account or {}).get("username") or "") or None)
        if gid is None:
            pg.rollback()
            return app._json_error("해당 후보를 찾을 수 없거나 이미 처리되었습니다.", 404)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_promote_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.feedback.promote",
                    resource_id=int(feedback_id),
                    change_json={"feedback_id": int(feedback_id), "glossary_id": int(gid)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "glossary_id": int(gid)})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/reject")
def admin_reject_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 거부(pending) 또는 자동등록 되돌리기(auto_promoted → source='auto' 행 회수).
    권한 kb.glossary.curate. 멱등."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.reject_glossary_feedback(pg, int(feedback_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 후보 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="glossary.feedback.reject",
                        resource_id=int(feedback_id), change_json={"feedback_id": int(feedback_id)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "rejected": int(affected)})

@router.get("/api/admin/metadata/glossary/{term_id}/relations")
def admin_list_glossary_relations(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """해당 용어의 인접 참조(유사어/동의어/see_also) 목록. 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_relations(pg, int(term_id))
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_relations 실패 id=%s", term_id, exc_info=True)
        return app._json_error("유사어 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (relation_id, relation_type, from_id, to_id, other_id, other_scope, other_role, other_term, other_def)
    items = [{
        "relation_id": int(r[0]), "relation_type": str(r[1] or ""),
        "from_id": int(r[2]), "to_id": int(r[3]),
        "other_id": int(r[4]), "other_scope_key": str(r[5] or ""), "other_role_key": str(r[6] or "*"),
        "other_term": str(r[7] or ""), "other_definition": str(r[8] or ""),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "term_id": int(term_id)})

@router.post("/api/admin/metadata/glossary/{term_id}/relations")
async def admin_add_glossary_relation(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """유사어 참조 추가. 권한 kb.ingest.manual. body: to_id(필수), relation_type(synonym|similar|see_also)."""
    data = await _metadata_read_json(request)
    try:
        to_id = int(data.get("to_id"))
    except (TypeError, ValueError):
        return app._json_error("to_id 는 필수(정수)입니다.", 400)
    if int(to_id) == int(term_id):
        return app._json_error("자기 자신은 참조로 연결할 수 없습니다.", 400)
    relation_type = str(data.get("relation_type") or "similar").strip().lower()
    if relation_type not in ("synonym", "similar", "see_also"):
        return app._json_error("relation_type 은 synonym|similar|see_also 중 하나여야 합니다.", 400)
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        # 두 용어 존재 확인(FK 위반 전 명시 404).
        if _kg.get_glossary_term(pg, int(term_id)) is None or _kg.get_glossary_term(pg, int(to_id)) is None:
            pg.rollback()
            return app._json_error("연결 대상 용어를 찾을 수 없습니다.", 404)
        _kg.add_glossary_relation(pg, int(term_id), int(to_id), relation_type,
                                  created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_add_glossary_relation 실패 from=%s to=%s", term_id, to_id, exc_info=True)
        return app._json_error("유사어 추가 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.relation.create",
                    resource_id=int(term_id),
                    change_json={"from_id": int(term_id), "to_id": int(to_id), "relation_type": relation_type})
    return JSONResponse({"ok": True, "from_id": int(term_id), "to_id": int(to_id),
                         "relation_type": relation_type})

@router.delete("/api/admin/metadata/glossary/relations/{relation_id}")
def admin_delete_glossary_relation(relation_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.manage'))) -> JSONResponse:
    """유사어 참조 삭제(by relation id, 멱등). 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_relation(pg, int(relation_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary_relation 실패 id=%s", relation_id, exc_info=True)
        return app._json_error("유사어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="glossary.relation.delete",
                        resource_id=int(relation_id), change_json={"relation_id": int(relation_id)})
    return JSONResponse({"ok": True, "id": int(relation_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/enums")
def admin_list_enums(request: Request, account=Depends(app.require_permission('metadata.enum.manage'))) -> JSONResponse:
    """ENUM 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_enum_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_enums 조회 실패", exc_info=True)
        return app._json_error("ENUM 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, code, label, source, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
        "code": str(r[5] or ""), "label": str(r[6] or ""), "source": str(r[7] or "manual"),
        "created_at": _metadata_iso(r[8]), "updated_at": _metadata_iso(r[9]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/enums")
async def admin_create_enum(request: Request, account=Depends(app.require_permission('metadata.enum.manage'))) -> JSONResponse:
    """ENUM 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, code, label, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = _metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_enum_entry(pg, scope_key, fields["table_name"], fields["column_name"],
                              fields["code"], fields["label"], schema_name=fields["schema_name"])
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_enum 실패", exc_info=True)
        return app._json_error("ENUM 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.entry.create",
                    resource_id=f"{scope_key}:{fields['table_name']}.{fields['column_name']}={fields['code']}",
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "scope_key": scope_key})

@router.put("/api/admin/metadata/enums/{entry_id}")
async def admin_update_enum(entry_id: int, request: Request, account=Depends(app.require_permission('metadata.enum.manage'))) -> JSONResponse:
    """ENUM 수정(by id, scope 가드). 권한 kb.ingest.manual. body 동일."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = _metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_enum_entry(
            pg, int(entry_id), scope_key, fields["table_name"], fields["column_name"],
            fields["code"], fields["label"], schema_name=fields["schema_name"])
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 ENUM 항목을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,schema,table,column,code) 충돌 → 409 (다른 행과 key 중복).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 key(스키마/테이블/컬럼/코드)의 ENUM 항목이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.entry.update",
                    resource_id=int(entry_id),
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "id": int(entry_id)})

@router.delete("/api/admin/metadata/enums/{entry_id}")
def admin_delete_enum(entry_id: int, request: Request, account=Depends(app.require_permission('metadata.enum.manage'))) -> JSONResponse:
    """ENUM 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_enum_entry(pg, int(entry_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="enum.entry.delete",
                        resource_id=int(entry_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(entry_id), "deleted": int(affected)})

# ── ENUM 코드사전 대화 자율수집 검토 큐(0039) — 용어사전 glossary-feedback 대칭 ────────────
@router.get("/api/admin/metadata/enum-feedback")
def admin_list_enum_feedback(request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐 목록. 권한 kb.enum.curate. ?status=(기본 pending, 'all'=전체) &scope_key=."""
    status = str(request.query_params.get("status") or "pending").strip().lower()
    if status in ("all", ""):
        status = None
    elif status not in ("pending", "auto_promoted", "promoted", "rejected"):
        return app._json_error("허용되지 않은 status 입니다.", 400)
    scope_filter = None
    sk_param = request.query_params.get("scope_key")
    if sk_param is not None and str(sk_param).strip() != "":
        scope_filter, serr = _metadata_check_scope(sk_param)
        if serr:
            return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_enum_feedback(pg, status=status, scope_key=scope_filter)
        pending_count = _kg.count_enum_feedback(pg, status="pending")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_enum_feedback 조회 실패", exc_info=True)
        return app._json_error("검토 큐 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, code, suggested_label,
    #       confidence, status, source_run_id, conversation_id, promoted_enum_id, approved_by,
    #       created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""), "code": str(r[5] or ""),
        "suggested_label": str(r[6] or ""),
        "confidence": float(r[7]) if r[7] is not None else None, "status": str(r[8] or ""),
        "source_run_id": (str(r[9]) if r[9] is not None else None),
        "conversation_id": (str(r[10]) if r[10] is not None else None),
        "promoted_enum_id": (int(r[11]) if r[11] is not None else None),
        "approved_by": (str(r[12]) if r[12] is not None else None),
        "created_at": _metadata_iso(r[13]), "updated_at": _metadata_iso(r[14]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items),
                         "pending_count": int(pending_count), "status": status})

@router.post("/api/admin/metadata/enum-feedback/{feedback_id}/promote")
def admin_promote_enum_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐(pending) → ENUM 코드사전 승급. 권한 kb.enum.curate."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        eid = _kg.promote_enum_feedback(
            pg, int(feedback_id), approved_by=str((account or {}).get("username") or "") or None)
        if eid is None:
            pg.rollback()
            return app._json_error("해당 후보를 찾을 수 없거나 이미 처리되었습니다.", 404)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_promote_enum_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("ENUM 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.feedback.promote",
                    resource_id=int(feedback_id),
                    change_json={"feedback_id": int(feedback_id), "enum_id": int(eid)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "enum_id": int(eid)})

@router.post("/api/admin/metadata/enum-feedback/{feedback_id}/reject")
def admin_reject_enum_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐 거부(pending) 또는 자동등록 되돌리기(auto_promoted → source='auto' 행 회수).
    권한 kb.enum.curate. 멱등."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.reject_enum_feedback(pg, int(feedback_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_enum_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("ENUM 후보 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="enum.feedback.reject",
                        resource_id=int(feedback_id), change_json={"feedback_id": int(feedback_id)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "rejected": int(affected)})

@router.get("/api/admin/metadata/tables")
def admin_list_table_desc(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """테이블 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _km.list_table_desc_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_table_desc 조회 실패", exc_info=True)
        return app._json_error("테이블 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, description, source, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "description": str(r[4] or ""), "source": str(r[5] or ""),
        "created_at": _metadata_iso(r[6]), "updated_at": _metadata_iso(r[7]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/tables")
async def admin_create_table_desc(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """테이블 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, description, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return e
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_table_desc(pg, scope_key, table_name, description,
                              schema_name=schema_name, source=source,
                              created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_table_desc 실패", exc_info=True)
        return app._json_error("테이블 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="table_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name})

@router.put("/api/admin/metadata/tables/{desc_id}")
async def admin_update_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """테이블 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?, table_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    # key 컬럼(schema/table)은 선택 — 둘 다 주어질 때만 key 수정(부분 제공 거부).
    has_schema = "schema_name" in data
    has_table = "table_name" in data
    schema_name = table_name = None
    if has_table:
        table_name, e = _metadata_str_field(data, "table_name")
        if e:
            return e
        schema_name, e = _metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    elif has_schema:
        return app._json_error("table_name 없이 schema_name 만 수정할 수 없습니다.", 400)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_table_desc(pg, int(desc_id), scope_key, description,
                                         schema_name=schema_name, table_name=table_name)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 테이블 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="table_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/tables/{desc_id}")
def admin_delete_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """테이블 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_table_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="table_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/columns")
def admin_list_column_desc(request: Request, account=Depends(app.require_permission('metadata.column.manage'))) -> JSONResponse:
    """컬럼 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _km.list_column_desc_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_column_desc 조회 실패", exc_info=True)
        return app._json_error("컬럼 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, description, source, created_at, updated_at, ordinal)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
        "description": str(r[5] or ""), "source": str(r[6] or ""),
        "created_at": _metadata_iso(r[7]), "updated_at": _metadata_iso(r[8]),
        "ordinal": (int(r[9]) if len(r) > 9 and r[9] is not None else None),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.post("/api/admin/metadata/columns")
async def admin_create_column_desc(request: Request, account=Depends(app.require_permission('metadata.column.manage'))) -> JSONResponse:
    """컬럼 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, description, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return e
    column_name, e = _metadata_str_field(data, "column_name")
    if e:
        return e
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    # feature-0016 graphux5: 실제 스키마 컬럼 순서(1-based). 부트스트랩 저장이 골격(DDL) 순서를 전송.
    ordinal = data.get("ordinal")
    try:
        ordinal = int(ordinal) if ordinal is not None and str(ordinal).strip() != "" else None
    except (TypeError, ValueError):
        ordinal = None
    if ordinal is not None and not (0 < ordinal <= 100000):
        ordinal = None   # 비정상 범위(PG int 초과·음수·0)는 미지정 처리(500 회피)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_column_desc(pg, scope_key, table_name, column_name, description,
                               schema_name=schema_name, source=source,
                               created_by=str((account or {}).get("username") or "") or None,
                               ordinal=ordinal)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_column_desc 실패", exc_info=True)
        return app._json_error("컬럼 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="column_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}.{column_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "column_name": column_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name, "column_name": column_name})

@router.put("/api/admin/metadata/columns/{desc_id}")
async def admin_update_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.column.manage'))) -> JSONResponse:
    """컬럼 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?/table_name?/column_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    has_table = "table_name" in data
    has_column = "column_name" in data
    schema_name = table_name = column_name = None
    if has_table or has_column:
        # key 수정 시 table+column 둘 다 필수(부분 제공 거부).
        table_name, e = _metadata_str_field(data, "table_name")
        if e:
            return e
        column_name, e = _metadata_str_field(data, "column_name")
        if e:
            return e
        schema_name, e = _metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    # feature-0016 graphux5: ordinal(실제 스키마 컬럼 순서) 선택 수정. 미제공 → 미변경.
    ordinal = data.get("ordinal")
    if ordinal is not None and str(ordinal).strip() != "":
        try:
            ordinal = int(ordinal)
        except (TypeError, ValueError):
            ordinal = None
        if ordinal is not None and not (0 < ordinal <= 100000):
            ordinal = None   # 비정상 범위는 미지정 처리(500 회피)
    else:
        ordinal = None
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_column_desc(pg, int(desc_id), scope_key, description,
                                          schema_name=schema_name, table_name=table_name,
                                          column_name=column_name, ordinal=ordinal)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 컬럼 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블/컬럼)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="column_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/columns/{desc_id}")
def admin_delete_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.column.manage'))) -> JSONResponse:
    """컬럼 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_column_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="column_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})


# ── graph-product-cat (feature-0016 §43): 제품(Products) 단위 카테고리 투영 ──────────────
#   그래프(AGE)는 Postgres `agent_kb` 에 있고 Product↔Datasource SSOT 는 MySQL(`WebProducts`·
#   `WebProductDatasources`)에 있다. AGE 에 Product/Datasource 노드를 물리 저장하는 대신, 투영 API 가
#   **질의시점에 MySQL SSOT 로부터 합성**한다("projection" 원칙 정합 — 마이그레이션·이중 정합 회피).
#   브리지: product → _list_product_datasources → datasource_key → shared.datasources.resolve → scope_key
#   (= 그래프 scope). scope_key 는 그대로 datasource-scoped 그래프(scope_roots/schemas)의 진입 키.
def _product_overview_graph(conn, product_id=None) -> dict:
    """활성 제품(product_id 지정 시 단일) + 바인딩 Datasource 노드 + USES 엣지 합성.

    노드: Product(key=`product:<id>`) · Datasource(key=`ds:<scope_key>`, scope_key 로 drill).
    여러 제품이 같은 datasource 를 공유할 수 있어 Datasource 노드는 dedup(엣지는 각 제품마다)."""
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        products = []
    if product_id is not None:
        products = [p for p in products if int(p.get("id") or 0) == int(product_id)]
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ds: set[str] = set()
    for p in products:
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        pkey = "product:%d" % pid
        ds_list = p.get("datasources") or []
        nodes.append({
            "label": "Product", "key": pkey,
            "name": p.get("name") or p.get("product_key") or ("제품#%d" % pid),
            "fqn": p.get("product_key") or "", "scope_key": "",
            "product_key": p.get("product_key") or "", "datasource_count": len(ds_list),
        })
        for d in ds_list:
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            # read-axis 정렬(§43 리뷰 MAJOR): 그래프 scope 는 admin_datasources 가 노출하는 read 축
            #   `scope_key or key`(DB-등록=엔드포인트 해시, .env 레거시=라벨)여야 drill-down 이 실 그래프와 일치한다.
            #   `_dsr.scope_key(ds)` 는 .env 도 해시로 계산해 read 축(라벨)과 어긋나 빈 그래프를 부른다 — 금지.
            sk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if not sk:
                continue
            dnode = "ds:%s" % sk
            if dnode not in seen_ds:
                seen_ds.add(dnode)
                nodes.append({
                    "label": "Datasource", "key": dnode,
                    "name": (ds.get("name") if ds else None) or dsk,
                    "fqn": sk, "scope_key": sk, "datasource_key": str(dsk).strip().lower(),
                })
            edges.append({
                "id": "uses:%d:%s" % (pid, sk), "type": "USES",
                "source": pkey, "target": dnode, "status": "",
                "data": {"is_primary": bool(d.get("is_primary"))},
            })
    return {"nodes": nodes, "edges": edges}


def _products_for_scope(conn, scope_key) -> list[dict]:
    """그래프 scope(=datasource scope_key)를 사용하는 제품 목록(배너용). common/미지정은 []."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return []
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        return []
    out: list[dict] = []
    for p in products:
        for d in (p.get("datasources") or []):
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            # read-axis 정렬(§43 리뷰 MAJOR): _product_overview_graph 와 동일 규약 — scope_key or 라벨.
            rk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if rk == sk:
                out.append({"id": int(p.get("id") or 0), "name": p.get("name") or "",
                            "product_key": p.get("product_key") or ""})
                break
    return out


def _schema_products_for_scope(conn, scope_key) -> dict:
    """§55 A(REQ-20260706 ①): scope 의 스키마(DB)명 → 그 DB 를 접근DB 로 선언한 제품 목록 매핑.

    그래프 뷰 스키마 클러스터의 **제품 카테고리** 데이터 원천. 브리지: scope → (read-axis 규약,
    _products_for_scope 동형) 그 scope 를 쓰는 (product, datasource_key) 쌍 → `WebProductDatabases`
    (ProductId, DatasourceKey, SchemaName — 제품별 접근DB SSOT) → {SchemaName: [{id,name,sort}]}.
    SchemaName 은 effective schema(=MSSQL/MySQL DB명) 규약이라 그래프 Schema 노드 name 과 조인 가능.
    AGE 미저장 — 질의시점 합성(ADR-014 원칙 계승). 실패·미매핑은 {}(프론트 '미분류' 폴백)."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return {}
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        return {}
    prod_ds: list[tuple[dict, str]] = []
    for p in products:
        for d in (p.get("datasources") or []):
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            rk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if rk == sk:
                prod_ds.append((p, str(dsk)))
    if not prod_ds:
        return {}
    out: dict[str, list[dict]] = {}
    try:
        cur = conn.cursor()
        try:
            for p, dsk in prod_ds:
                pid = int(p.get("id") or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "SELECT SchemaName FROM WebProductDatabases "
                    "WHERE ProductId=%s AND DatasourceKey=%s ORDER BY SortOrder, SchemaName",
                    (pid, dsk))
                psort = p.get("sort_order")
                ent = {"id": pid, "name": p.get("name") or p.get("product_key") or ("제품#%d" % pid),
                       "sort": int(psort) if isinstance(psort, (int, float)) else 100}
                for row in cur.fetchall():
                    sch = str(row[0] or "").strip()
                    if not sch:
                        continue
                    lst = out.setdefault(sch, [])
                    if not any(e.get("id") == pid for e in lst):
                        lst.append(dict(ent))
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("_schema_products_for_scope 실패", exc_info=True)
        return {}
    return out


@router.get("/api/admin/metadata/graph")
def admin_metadata_graph(request: Request, account=Depends(app.require_permission('metadata.graph.read')), conn=Depends(app.get_conn)) -> JSONResponse:
    """메타데이터 지식그래프 투영(Apache AGE metadata_kb) — UI(Cytoscape)·검색 공급.

    권한 kb.ingest.manual. 8K 노드 규모라 **전체 덤프 금지** — 모드:
      - 제품:    ?mode=products / ?product=<id> → 제품(카테고리)→Datasource 개요 (MySQL SSOT 합성, graph-product-cat)
      - 이웃:    ?node=<key>&depth=1..3      → 해당 노드 k-hop (cap 적용)
      - 검색:    ?q=<부분일치>[&scope=<ds>]  → 이름/FQN CONTAINS (scope 지정 시 그 datasource 만)
      - 스키마:  ?scope=<ds>&mode=schemas    → Schema 카드 + table_count (graph-initview 경량 진입)
      - 단일스키마: ?scope=<ds>&schema=<key> → 그 스키마의 Table 만 (per-schema lazy, truncated 플래그)
      - 진입:    ?scope=<ds>                 → 그 datasource 의 Schema→Table 서브그래프(하위호환 유지)
    셋 다 없으면 빈 그래프. AGE cutover 전(확장 부재)엔 모듈이 graceful no-op → 빈 결과.
    scope 는 datasource scope_key(예: mssql-06656002eda6) — 각 데이터소스별 그래프 분리.
    """
    q = (request.query_params.get("q") or "").strip()
    node = (request.query_params.get("node") or "").strip()
    scope = (request.query_params.get("scope") or "").strip() or None
    schema = (request.query_params.get("schema") or "").strip()
    mode_param = (request.query_params.get("mode") or "").strip()
    product = (request.query_params.get("product") or "").strip()
    try:
        depth = int(request.query_params.get("depth") or "1")
    except (TypeError, ValueError):
        depth = 1
    depth = max(1, min(depth, 3))
    try:
        limit = int(request.query_params.get("limit") or "50")
    except (TypeError, ValueError):
        limit = 50

    # graph-product-cat (§43): 제품 카테고리 개요 — MySQL SSOT 합성(PG 불필요, early-return).
    #   product 는 숫자일 때만 단일 제품 트리거(비숫자는 통과 → 일반 dispatch; 리뷰 NIT 방어).
    if mode_param == "products" or product.isdigit():
        pid = int(product) if product.isdigit() else None
        try:
            pdata = _product_overview_graph(conn, product_id=pid)
        except Exception:
            logging.getLogger(__name__).warning("admin_metadata_graph products 조회 실패", exc_info=True)
            return app._json_error("제품 그래프 조회 실패", 503)
        return JSONResponse({
            "nodes": pdata.get("nodes", []), "edges": pdata.get("edges", []),
            "mode": "products", "q": "", "node": "", "scope": product or "", "depth": 1,
            "truncated": False, "products": [],
            "node_count": len(pdata.get("nodes", [])), "edge_count": len(pdata.get("edges", [])),
        })

    from modules import metadata_graph as _mg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("그래프 저장소(PG) 연결 실패", 503)
    try:
        if node:
            data = _mg.neighborhood(node, depth=depth, conn=pg)
            mode = "neighborhood"
        elif q:
            data = {"nodes": _mg.search_nodes(q, limit=limit, scope=scope, conn=pg), "edges": []}
            mode = "search"
        elif scope and schema:
            data = _mg.schema_tables(scope, schema, conn=pg)
            mode = "schema_tables"
        elif scope and mode_param == "schemas":
            data = _mg.scope_schemas(scope, conn=pg)
            mode = "scope_schemas"
        elif scope:
            data = _mg.scope_roots(scope, conn=pg)
            mode = "scope_roots"
        else:
            data = {"nodes": [], "edges": []}
            mode = "empty"
    except Exception:
        logging.getLogger(__name__).warning("admin_metadata_graph 조회 실패", exc_info=True)
        return app._json_error("그래프 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # graph-product-cat (§43): 진입 모드(scope_roots/schemas)에서만 이 datasource 를 쓰는 제품 목록 첨부(배너용).
    #   neighborhood/search/schema_tables 등 임계경로 모드는 skip(MySQL 왕복 절감).
    scope_products = []
    schema_products = {}
    if scope and mode in ("scope_roots", "scope_schemas"):
        try:
            scope_products = _products_for_scope(conn, scope)
        except Exception:
            scope_products = []
        # §55 A: 스키마(DB)별 제품 매핑 — 프론트 카테고리 그룹(CAT 계층)의 데이터 원천. 실패는 {}(미분류 폴백).
        try:
            schema_products = _schema_products_for_scope(conn, scope)
        except Exception:
            schema_products = {}
    return JSONResponse({
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "mode": mode,
        "q": q, "node": node, "scope": scope or "", "depth": depth,
        "truncated": bool(data.get("truncated", False)),
        "products": scope_products,
        "schema_products": schema_products,
        "node_count": len(data.get("nodes", [])), "edge_count": len(data.get("edges", [])),
    })

@router.post("/api/admin/metadata/graph/analyze")
async def admin_metadata_graph_analyze(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """그래프 노드 AI 능동 분석 트리거(항목2). 권한 metadata.graph.read(우산 kb.ingest.manual 함의).

    body: {node_key, scope_key?, depth?, node_budget?, prompt?}. run 을 만들고 즉시 202 반환 — 실제
    분석은 insight-worker 백그라운드가 선택 노드에서 관련 노드를 재귀 탐색하며 노드별 수행(부하 분산).
    prompt(ADR-017, 선택 ≤400자): hover 툴팁으로 입력한 사용자 분석 지침 — run 에 저장돼 앵커 토큰
    합류 + LLM user_intent 로 자율 반영된다.
    진행은 GET .../graph/analyze?run_id= 로 폴링, 노드 결과는 GET .../graph/analyze/node?node= 로 조회.
    """
    data = await _metadata_read_json(request)
    node_key = str(data.get("node_key") or data.get("node") or "").strip()
    if not node_key or ":" not in node_key:
        return app._json_error("node_key(그래프 노드 키)는 필수입니다.", 400)
    scope_key = str(data.get("scope_key") or node_key.split(":", 1)[0] or "common").strip().lower()
    depth = data.get("depth")
    node_budget = data.get("node_budget")
    user_prompt = str(data.get("prompt") or "").strip()[:400] or None
    from modules import node_analysis as _na
    res = _na.enqueue_analysis(scope_key, node_key, depth_budget=depth, node_budget=node_budget,
                               requested_by=str((account or {}).get("username") or "") or None,
                               user_prompt=user_prompt)
    if not res.get("ok"):
        reason = res.get("reason") or "분석 시작 실패"
        # fix: 서버측 실패(PG 미가용/disabled/enqueue 실패)는 5xx. 클라 입력 오류만 400(라우트가 이미
        #   node_key 를 검증하므로 'node_key 필수'는 사실상 발생 안 함).
        code = 400 if reason == "node_key 필수" else 503
        return app._json_error(f"AI 능동 분석 시작 실패: {reason}", code)
    _metadata_audit(request, account, action="node_analysis.enqueue", resource_id=node_key,
                    change_json={"scope_key": scope_key, "run_id": res.get("run_id"),
                                 "depth": depth, "node_budget": node_budget,
                                 "reused": res.get("reused", False),
                                 "prompt_len": len(user_prompt or ""),
                                 "prompt_preview": (user_prompt or "")[:120] or None})
    return JSONResponse({"ok": True, "run_id": res.get("run_id"), "status": res.get("status"),
                         "reused": res.get("reused", False), "progress": res.get("progress")},
                        status_code=202)

@router.post("/api/admin/metadata/graph/analyze-schema")
async def admin_metadata_graph_analyze_schema(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """DB(스키마) 단위 AI 능동 분석(§53·§55). 권한 metadata.graph.read(노드 분석과 동일 우산).

    body: {schema_key, scope_key?, prompt?, only_missing?=true, dry_run?}. 스키마 소속 Table·Routine 을
    depth=0 시드로 일괄 enqueue — §55(REQ-20260706 ③): 시드별 직계 컬럼 + per-seed 앵커 게이팅 재귀
    전개(depth=AGENT_NODE_ANALYSIS_SCHEMA_DEPTH, 총예산 min(SCHEMA_RUN_BUDGET_MAX, planned×EXPAND_FACTOR)).
    비용 가드 = only_missing 기본 + AGENT_NODE_ANALYSIS_SCHEMA_CAP(기본 200) + 예산 캡 + 빈약 노드만
    back-refine(REFINE_MAX). dry_run=true 는 run 미생성 — 대상 집계만 반환(프론트 confirm 용).
    진행 폴링은 기존 GET .../graph/analyze?run_id= 재사용(enqueued 는 재귀 전개로 실행 중 증가)."""
    data = await _metadata_read_json(request)
    schema_key = str(data.get("schema_key") or data.get("schema") or "").strip()
    if not schema_key or ":" not in schema_key:
        return app._json_error("schema_key(스키마 노드 키)는 필수입니다.", 400)
    scope_key = str(data.get("scope_key") or schema_key.split(":", 1)[0] or "common").strip().lower()
    user_prompt = str(data.get("prompt") or "").strip()[:400] or None
    only_missing = bool(data.get("only_missing", True))
    dry_run = bool(data.get("dry_run", False))
    from modules import node_analysis as _na
    res = _na.enqueue_schema_analysis(scope_key, schema_key,
                                      requested_by=str((account or {}).get("username") or "") or None,
                                      user_prompt=user_prompt, only_missing=only_missing,
                                      dry_run=dry_run)
    if not res.get("ok"):
        reason = res.get("reason") or "분석 시작 실패"
        code = 400 if reason == "schema_key 필수" else 503
        return app._json_error(f"DB 단위 AI 능동 분석 시작 실패: {reason}", code)
    if not dry_run and res.get("status") in ("running",):
        _metadata_audit(request, account, action="node_analysis.enqueue_schema", resource_id=schema_key,
                        change_json={"scope_key": scope_key, "run_id": res.get("run_id"),
                                     "planned": res.get("planned"), "total_tables": res.get("total_tables"),
                                     "total_routines": res.get("total_routines"),
                                     "missing": res.get("missing"), "capped": res.get("capped", False),
                                     "only_missing": only_missing, "reused": res.get("reused", False),
                                     "prompt_len": len(user_prompt or ""),
                                     "prompt_preview": (user_prompt or "")[:120] or None})
    return JSONResponse({"ok": True, "run_id": res.get("run_id"), "status": res.get("status"),
                         "total_tables": res.get("total_tables"),
                         "total_routines": res.get("total_routines"), "missing": res.get("missing"),
                         "planned": res.get("planned"), "capped": res.get("capped", False),
                         "reused": res.get("reused", False), "progress": res.get("progress"),
                         "reason": res.get("reason")},
                        status_code=200 if dry_run or res.get("status") == "noop" else 202)


def _parse_graph_column_key(raw) -> dict | None:
    """그래프 Column 노드 key `<scope>:<schema>.<table>.<column>` 파싱(§55 B curate). 실패 None."""
    k = str(raw or "").strip()
    if ":" not in k:
        return None
    scope, fqn = k.split(":", 1)
    parts = [p for p in fqn.split(".") if p != ""]
    if len(parts) < 2 or not scope:
        return None
    column, table = parts[-1], parts[-2]
    schema = ".".join(parts[:-2])
    return {"scope": scope.strip().lower(), "schema": schema, "table": table, "column": column,
            "table_fqn": (f"{schema}.{table}" if schema else table)}


@router.post("/api/admin/metadata/graph/relationship/curate")
async def admin_metadata_graph_relationship_curate(request: Request,
                                                   account=Depends(app.require_permission('metadata.table.manage')),
                                                   conn=Depends(app.get_conn)) -> JSONResponse:
    """§55 B(REQ-20260706 ②): 관계 사람 큐레이션 — trust(신뢰 승격) / break(파단).

    크로스-데이터소스 후보는 프로브 검증이 불가해 source='manual' 승격이 **유일한 신뢰 경로**인데
    (ADR-019), 그 호출자가 미배선이라 영구 candidate(AI 컨텍스트 미주입)로 남던 dead-end 를 해소한다.
    intra-DS 관계에도 동작(운영자 확정/오탐 즉시 파단). 권한 metadata.table.manage(메타데이터 큐레이션 축).

    body: {action: 'trust'|'break', src: <Column key>, tgt: <Column key>} — key 는 그래프 Column 노드
    key(`<scope>:<schema>.<table>.<column>`). trust=upsert(source='manual'→trusted, weight 1.0) + 그래프
    엣지 즉시 투영. break=status 'broken'·weight 0 + 그래프 엣지 즉시 회수. 관계형 SSOT(PG)와 그래프
    (AGE) 동시 정합 — 다음 sync_graph 주기와도 멱등."""
    data = await _metadata_read_json(request)
    action = str(data.get("action") or "").strip().lower()
    if action not in ("trust", "break"):
        return app._json_error("action 은 'trust' 또는 'break' 여야 합니다.", 400)
    src = _parse_graph_column_key(data.get("src"))
    tgt = _parse_graph_column_key(data.get("tgt"))
    if not src or not tgt:
        return app._json_error("src/tgt(그래프 Column 노드 키)는 필수입니다.", 400)
    from modules import metadata_graph as _mg
    from modules import relationships as _rel
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=True)
    except Exception:
        return app._json_error("그래프 저장소(PG) 연결 실패", 503)
    updated = 0
    try:
        cur = pg.cursor()
        try:
            # §55 패널 fix: ds-키 매칭에 ''(레거시 — scope 배선 이전 행, 라이브 실측 scope_key='common'
            # +ds '' 797행) 허용. 정확 매칭만 쓰면 레거시 행에서 UPDATE 0건인데 AGE 엣지만 삭제/승격돼
            # 다음 sync_graph 가 원상복구(부활/강등 flap)한다 — SSOT·그래프 동시 정합이 목적.
            if action == "trust":
                # 기존 행 우선 UPDATE(방향 그대로) — upsert 를 먼저 쓰면 기존 행의 UNIQUE 키(레거시 ''-ds)와
                # 어긋날 때 **중복 행**이 생기고, 원 candidate 가 계속 프로브·파단되며 같은 그래프 엣지를
                # 삭제/신뢰로 뒤집는 flap 이 남는다(패널 MAJOR). 매칭 0건일 때만 신규 manual 행 upsert.
                cur.execute(
                    "UPDATE table_relationships SET status='trusted', weight=1.0, source='manual', "
                    "       confidence=1.0, negative_signals=0, updated_at=now() "
                    "WHERE source_table_fqn=%s AND source_column=%s "
                    "  AND target_table_fqn=%s AND target_column=%s "
                    "  AND (source_datasource_key=%s OR source_datasource_key='') "
                    "  AND (target_datasource_key=%s OR target_datasource_key='')",
                    (src["table_fqn"], src["column"], tgt["table_fqn"], tgt["column"],
                     src["scope"], tgt["scope"]))
                updated = int(cur.rowcount or 0)
                if not updated:
                    ok = _rel.upsert_relationship(
                        pg, src["scope"],
                        src_schema=src["schema"], src_table=src["table"], src_column=src["column"],
                        tgt_schema=tgt["schema"], tgt_table=tgt["table"], tgt_column=tgt["column"],
                        source="manual", datasource_key=src["scope"],
                        source_datasource_key=src["scope"], target_datasource_key=tgt["scope"])
                    if not ok:
                        return app._json_error("관계 승격 실패(관계 저장소)", 503)
                    updated = 1
                _mg.sync_relationship(cur, src["scope"], src["table_fqn"], src["column"],
                                      tgt["table_fqn"], tgt["column"], source="manual",
                                      confidence=1.0, weight=1.0, status="trusted",
                                      tgt_scope=tgt["scope"])
            else:
                # break: 방향 그대로 + 역방향 행 모두 파단(추론기가 어느 방향으로 저장했든 오탐 회수).
                cur.execute(
                    "UPDATE table_relationships SET status='broken', weight=0.0, updated_at=now() "
                    "WHERE (source_table_fqn=%s AND source_column=%s "
                    "       AND target_table_fqn=%s AND target_column=%s "
                    "       AND (source_datasource_key=%s OR source_datasource_key='') "
                    "       AND (target_datasource_key=%s OR target_datasource_key='')) "
                    "   OR (source_table_fqn=%s AND source_column=%s "
                    "       AND target_table_fqn=%s AND target_column=%s "
                    "       AND (source_datasource_key=%s OR source_datasource_key='') "
                    "       AND (target_datasource_key=%s OR target_datasource_key=''))",
                    (src["table_fqn"], src["column"], tgt["table_fqn"], tgt["column"],
                     src["scope"], tgt["scope"],
                     tgt["table_fqn"], tgt["column"], src["table_fqn"], src["column"],
                     tgt["scope"], src["scope"]))
                updated = int(cur.rowcount or 0)
                _mg.delete_relationship(cur, src["scope"], src["table_fqn"], src["column"],
                                        tgt["table_fqn"], tgt["column"], tgt_scope=tgt["scope"])
                _mg.delete_relationship(cur, tgt["scope"], tgt["table_fqn"], tgt["column"],
                                        src["table_fqn"], src["column"], tgt_scope=src["scope"])
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("relationship_curate 실패", exc_info=True)
        return app._json_error("관계 큐레이션 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="graph.relationship.curate",
                    resource_id=f"{data.get('src')}->{data.get('tgt')}",
                    change_json={"action": action, "updated": updated,
                                 "cross_ds": src["scope"] != tgt["scope"]})
    return JSONResponse({"ok": True, "action": action, "updated": updated,
                         "cross_ds": src["scope"] != tgt["scope"]})

@router.get("/api/admin/metadata/graph/analyze")
def admin_metadata_graph_analyze_status(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """분석 run 진행률 폴링(항목2). 권한 kb.ingest.manual. ?run_id=<hex>.
    반환 {status, enqueued, done, failed, done_keys[...]} — 프론트가 done_keys 로 분석 마커 표시."""
    run_id = (request.query_params.get("run_id") or "").strip()
    if not run_id:
        return app._json_error("run_id 는 필수입니다.", 400)
    from modules import node_analysis as _na
    st = _na.get_run_status(run_id)
    if st is None:
        return app._json_error("run 을 찾을 수 없습니다.", 404)
    return JSONResponse(st)

@router.get("/api/admin/metadata/graph/analyze/node")
def admin_metadata_graph_analyze_node(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """노드의 최신 분석 상태/결과(상세 패널, 항목2). 권한 kb.ingest.manual. ?node=<key>[&scope=<ds>].
    반환 {status:'none'|'pending'|'running'|'done'|'failed', analysis:{summary,relationships,usage,caveats}}."""
    node = (request.query_params.get("node") or "").strip()
    if not node:
        return app._json_error("node 는 필수입니다.", 400)
    scope = (request.query_params.get("scope") or "").strip() \
        or (node.split(":", 1)[0] if ":" in node else "common")
    from modules import node_analysis as _na
    res = _na.get_node_analysis(scope, node)
    if res is None:
        return app._json_error("조회 실패", 503)
    return JSONResponse(res)

@router.get("/api/admin/metadata/graph/analyze/status")
def admin_metadata_graph_analyze_status_bulk(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """스코프 내 노드들의 분석 상태 **일괄** 집계(그래프 초기 렌더 마커용, 항목1). 권한 kb.ingest.manual.
    ?scope=<ds> — 그 datasource 스코프의 완료/진행중 node_key 집합을 반환한다. 프론트는 그래프 로드/검색/확장
    직후 이 결과로 마커(보라 '분석됨'·주황 '분석중')와 역할 표식(node-role-viz)을 **노드 클릭 없이** 즉시 적용한다.
    반환 {done_keys:[...], running_keys:[...], roles:{node_key:role}}. PG 미가용 시 빈 집합(마커 없음 — 그래프는 정상)."""
    scope = (request.query_params.get("scope") or "").strip() or "common"
    from modules import node_analysis as _na
    res = _na.get_scope_analysis_status(scope)
    if res is None:
        # PG 미가용/예외 — 그래프 자체는 렌더되어야 하므로 빈 집합으로 graceful(마커만 생략).
        return JSONResponse({"done_keys": [], "running_keys": [], "roles": {}, "unavailable": True})
    return JSONResponse({"done_keys": res.get("done_keys", []), "running_keys": res.get("running_keys", []),
                         "roles": res.get("roles", {})})

@router.get("/api/admin/metadata/graph/columns")
def admin_metadata_graph_columns(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """더블클릭 컬럼 즉석 introspection(항목3). 권한 kb.ingest.manual. ?node=<table key `scope:schema.table`>.

    그래프 투영(SSOT=column_descriptions)에 Column 노드가 없어(큐레이션/분석 미진행) 더블클릭해도
    컬럼이 안 펼쳐지던 문제를 해소한다. 그래프에 컬럼이 없으면 **데이터소스 information_schema 를 즉석
    조회**해 Column 노드 + HAS_COLUMN 엣지로 반환한다(read-only, 그래프 미저장). 실패 시 introspected=False
    + reason 으로 명확 피드백(silent no-op 금지)."""
    node = (request.query_params.get("node") or "").strip()
    if not node or ":" not in node:
        return app._json_error("node(테이블 키 `scope:schema.table`)는 필수입니다.", 400)
    scope_key = node.split(":", 1)[0]
    fqn = node.split(":", 1)[1]
    parts = [p for p in fqn.split(".") if p]
    if len(parts) < 2:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "테이블 노드가 아니거나 스키마.테이블 형식이 아닙니다."})
    schema = parts[0]
    table = parts[-1]
    import re as _re
    _ident = r"^[A-Za-z0-9_$\- ]+$"
    if not _re.match(_ident, schema) or not _re.match(_ident, table):
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "식별자에 허용되지 않는 문자가 있어 조회를 건너뜁니다."})
    # graph-perf-bg: 성공 introspection 캐시 히트면 ds 해석·라이브 DB 연결·information_schema 조회 전량 우회.
    _cached = _graph_columns_cache_get(scope_key, fqn)
    if _cached is not None:
        return JSONResponse(_cached)
    ds, derr = app._graph_resolve_ds_by_scope(scope_key)
    if derr:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node, "reason": derr})
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    conn = None
    engine = ""
    rows = []
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: fqn 첫 세그먼트가 DB(카탈로그) — 그 DB 에 연결 후 테이블명으로 컬럼 조회(스키마 무관).
            conn = _db.connect(datasource=ds, database=schema, autocommit=True)
            cur = conn.cursor()
            cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        f"WHERE TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")
            rows = cur.fetchall()
            cur.close()
        else:
            # MySQL: schema == database. information_schema 는 서버 전역 → 무-database 연결 + WHERE 필터.
            conn = _db.connect(datasource=ds, autocommit=True)
            dialect = _dialects.active()
            cur = conn.cursor()
            cur.execute(dialect.describe_columns(schema, table))  # SELECT COLUMN_NAME, COLUMN_TYPE, ...
            rows = cur.fetchall()
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("graph columns introspect 실패 node=%s", node, exc_info=True)
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "데이터소스 컬럼 조회 실패(권한/연결 확인, 또는 AI 능동 분석 사용)."})
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    nodes, edges = [], []
    ord_i = 0
    for r in rows[:500]:
        cname = str(r[0]) if r and r[0] is not None else ""
        if not cname:
            continue
        ctype = str(r[1]) if len(r) > 1 and r[1] is not None else ""
        ckey = f"{scope_key}:{fqn}.{cname}"
        ord_i += 1   # describe_columns 는 ORDINAL_POSITION 순 → 인덱스가 실제 스키마 컬럼 순서(ERD 카드 정렬키)
        nodes.append({"label": "Column", "key": ckey, "name": cname,
                      "fqn": f"{fqn}.{cname}", "description": ctype, "source": "introspect", "ordinal": ord_i})
        edges.append({"source": node, "target": ckey, "type": "HAS_COLUMN",
                      "cardinality": None, "edge_source": "introspect"})
    payload = {"nodes": nodes, "edges": edges, "introspected": True,
               "count": len(nodes), "engine": engine, "node": node}
    if nodes:   # graph-perf-bg: 컬럼이 실제 조회된 성공만 캐시(빈/실패 결과는 재시도 보장 위해 미캐시)
        _graph_columns_cache_put(scope_key, fqn, payload)
    return JSONResponse(payload)

@router.get("/api/admin/metadata/samples")
def admin_list_samples(request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 목록 — 단일 scope. 권한 kb.sample.curate. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        rows = _sq.list_samples_admin(pg, scope_key)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_samples 조회 실패", exc_info=True)
        return app._json_error("샘플 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, nl_question, sql, domain, weight, approved, status, source_type, created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "nl_question": str(r[2] or ""),
        "sql": str(r[3] or ""), "domain": str(r[4] or ""), "weight": int(r[5] or 0),
        "approved": bool(r[6]), "status": str(r[7] or ""), "source_type": str(r[8] or ""),
        "created_at": _metadata_iso(r[9]), "updated_at": _metadata_iso(r[10]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key})

@router.put("/api/admin/metadata/samples/{sample_id}")
async def admin_update_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 수정(by id, scope 가드). 권한 kb.sample.curate. body: scope_key, nl_question?, sql?, domain?, weight?, approved?.

    하이브리드 C 임베딩: nl_question 변경 시에만 kb_retrieval._embed_query_vector 동기 시도 →
    성공이면 embedding 갱신(status='active'), 실패면 embedding 무효화(status='stale', 재임베딩 대기).
    nl 미변경 시 embedding touch 안 함. weight 1~1000 clamp. nl 중복(UNIQUE) → 409.
    """
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr

    # 부분 수정 — 본문에 키가 있을 때만 해당 필드 변경. 전부 미제공이면 400(no-op 거부).
    kwargs: dict = {}
    if "nl_question" in data:
        nlq, e = _metadata_str_field(data, "nl_question")
        if e:
            return e
        kwargs["nl_question"] = nlq
    if "sql" in data:
        sql_v = str(data.get("sql") or "").strip()
        if not sql_v:
            return app._json_error("sql 은 비울 수 없습니다.", 400)
        if len(sql_v) > 8000:  # 샘플 SQL 길이 cap(프롬프트 예시 전용 — 비대 방지)
            return app._json_error("sql 이 너무 깁니다 (최대 8000자).", 400)
        kwargs["sql"] = sql_v
    if "domain" in data:
        kwargs["domain"] = str(data.get("domain") or "").strip()
    if "weight" in data:
        try:
            w = int(data.get("weight"))
        except Exception:
            return app._json_error("weight 는 정수여야 합니다.", 400)
        kwargs["weight"] = max(app._SAMPLE_WEIGHT_MIN, min(app._SAMPLE_WEIGHT_MAX, w))  # 1~1000 clamp
    if "approved" in data:
        kwargs["approved"] = bool(data.get("approved"))
    if not kwargs:
        return app._json_error("수정할 필드가 없습니다.", 400)

    # 하이브리드 C: nl_question 변경 시에만 임베딩 동기 시도. 실패→None(코어가 status='stale').
    embed_changed = "nl_question" in kwargs
    embed_status = None  # 응답 진단용: 'active' | 'stale' | None(미변경)
    if embed_changed:
        vec = None
        try:
            from modules.kb_retrieval import _embed_query_vector
            vec = _embed_query_vector(kwargs["nl_question"])  # dim=1024(titan-embed v2)
        except Exception:
            vec = None
        kwargs["embedding"] = vec if vec else None
        embed_status = "active" if vec else "stale"

    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.update_sample(pg, int(sample_id), scope_key, **kwargs)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 샘플을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 질문(nl_question)의 샘플이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="sample.update",
                    resource_id=int(sample_id),
                    change_json={"scope_key": scope_key, "fields": sorted(k for k in kwargs if k != "embedding"),
                                 "embedding": embed_status})
    return JSONResponse({"ok": True, "id": int(sample_id), "embedding_status": embed_status})

@router.delete("/api/admin/metadata/samples/{sample_id}")
def admin_delete_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 삭제(by id, scope 가드, 멱등). 권한 kb.sample.curate. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.delete_sample(pg, int(sample_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="sample.delete",
                        resource_id=int(sample_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(sample_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/bootstrap/schemas")
def admin_bootstrap_schemas(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """선택 datasource 의 골격 단위(unit) 목록. 권한 kb.ingest.manual. ?datasource=<key>.

    엔진별 unit 차이(metadata-table-desc-fix):
      - **MySQL**: schema == database. information_schema/mysql/performance_schema/sys 시스템
        스키마 + __invalid_default_db__ 센티넬을 제외한 schema 목록.
      - **MSSQL**: server > database > schema 4계층. unit = **database**(list_server_databases,
        master/model/msdb/tempdb 제외). 과거엔 database 미선택 시 중립 tempdb 에 연결되어 임시테이블
        (#A0A50030 …)이 골격으로 잡혀 "테이블 명칭이 모두 올바르지 않은 값"으로 보였다.
    응답: {schemas:[...], datasource, engine, unit_kind:"database"|"schema"} — 프론트가 unit_kind 로 라벨 분기.
    """
    ds, scope_key, derr = app._bootstrap_resolve_datasource(request.query_params.get("datasource") or "")
    if derr:
        return derr
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL unit = database. 시스템 DB(master/model/msdb/tempdb) 제외.
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            units = [str(n) for n in (_db.list_server_databases(ds) or [])
                     if str(n).strip().lower() not in sys_db]
            unit_kind = "database"
        else:
            conn = _db.connect(datasource=ds, autocommit=True)  # RO 유저(데이터소스 좌표는 least-priv)
            raw = _schema.load_known_schemas(conn) or []  # dialect-aware(schema.py:788)
            units = [str(n) for n in raw
                     if str(n).strip().lower() not in app._BOOTSTRAP_MYSQL_SYS_SCHEMAS]
            unit_kind = "schema"
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap_schemas 실패 ds=%s", scope_key, exc_info=True)
        return app._json_error("스키마 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)  # 요청 컨텍스트 dialect 리셋
        except Exception:
            pass
    return JSONResponse({"schemas": units, "datasource": scope_key, "engine": engine, "unit_kind": unit_kind})

@router.post("/api/admin/metadata/bootstrap")
async def admin_bootstrap(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """선택 datasource+schema 의 테이블/컬럼 골격(미영속). 권한 kb.ingest.manual. body: datasource, schema.

    골격은 저장하지 않는다 — UI 가 설명 빈칸을 prefill, 사람이 채워 tables/columns POST(source='bootstrap')
    로 저장한다. dialect-aware: MSSQL 은 set_active_datasource(engine=) 로 활성화 후 dialect.describe_columns
    경유(MySQL 백틱 하드코딩 load_schema_metadata 우회). 자동 1행 샘플/list_indexes 호출 안 함(부하/PII).
    """
    data = await _metadata_read_json(request)
    ds, scope_key, derr = app._bootstrap_resolve_datasource(data.get("datasource") or "")
    if derr:
        return derr
    schema_name = str(data.get("schema") or "").strip()
    if not schema_name:
        return app._json_error("schema 는 필수입니다.", 400)
    if len(schema_name) > app._METADATA_FIELD_CAPS["schema_name"]:
        return app._json_error("schema 가 너무 깁니다.", 400)

    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    from modules.tools import _safe_ident as _safe_ident_fn
    # REV B1(BLOCKER) — SQLi 차단: dialect.describe_schema_tables 는 schema 를 f-string 으로 SQL 에
    # 삽입(dialects.py `WHERE … = '{schema}'`)하므로, 구조화 도구(tools.py)와 동일하게
    # ① _safe_ident 로 인용 구분자 제거 + ② allowlist 멤버십으로만 통과시킨다.
    safe_schema = _safe_ident_fn(schema_name)
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: schema 파라미터는 **database**. 시스템 DB 제외 allowlist 로 검증 후 해당 DB 로
            # 직접 연결(database 미지정 시 중립 tempdb 폴백 → 임시테이블 회귀)하고, 그 DB 안의 비시스템
            # SQL 스키마 테이블을 평탄 수집한다(저장 schema_name = database).
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            db_units = {str(n) for n in (_db.list_server_databases(ds) or [])
                        if str(n).strip().lower() not in sys_db}
            if safe_schema not in db_units:
                return app._json_error("알 수 없는 database 이거나 접근할 수 없습니다.", 404)
            conn = _db.connect(datasource=ds, database=safe_schema, autocommit=True)
            tables = app._bootstrap_collect_skeleton_mssql(conn, _dialects, safe_schema)
        else:
            conn = _db.connect(datasource=ds, autocommit=True)
            known_schemas = set(_schema.load_known_schemas(conn) or [])
            if safe_schema not in known_schemas:
                return app._json_error("알 수 없는 schema 이거나 접근할 수 없습니다.", 404)
            tables = app._bootstrap_collect_skeleton(conn, _dialects, safe_schema)
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap 실패 ds=%s schema=%s", scope_key, schema_name, exc_info=True)
        return app._json_error("스키마 골격 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    return JSONResponse({"tables": tables, "datasource": scope_key, "schema": schema_name})

@router.post("/api/admin/metadata/{sub}/suggest")
async def admin_metadata_suggest(sub: str, request: Request) -> JSONResponse:
    """메타데이터 단건 AI 자동완성 — 식별 필드 → 설명/정의/라벨/질문 1건(영속 안 함).

    RBAC 는 서브뷰별(glossary/enums/tables/columns=kb.ingest.manual, samples=kb.sample.curate).
    tables/columns 는 datasource 지정 시 실제 스키마(컬럼)에 best-effort grounding.
    """
    sub = str(sub or "").strip().lower()
    target = app._METADATA_SUGGEST_TARGET.get(sub)
    if not target:
        return app._json_error("알 수 없는 메타데이터 서브뷰입니다.", 404)
    perm = app._METADATA_SUBTAB_PERM_SERVER.get(sub, "kb.ingest.manual")
    account, error = _metadata_resolve_account_perm(request, perm)
    if error:
        return error
    # per-account rate-limit(429) — LLM dispatch 비용 DoS 방어(fix-with-ai 와 동일 패턴). RBAC 통과 후 검사.
    if not app._search_rate_limit_check(int(account.get("id") or 0), max_per_min=app._METADATA_AI_RATE_PER_MIN):
        return app._json_error("자동완성 요청이 너무 잦습니다. 잠시 후 다시 시도하세요.", 429)
    data = await _metadata_read_json(request)
    fields: dict = {}
    for k in ("term", "schema_name", "table_name", "column_name", "code", "sql", "nl_question"):
        if k in data:
            v, ferr = _metadata_str_field(data, k, required=False)
            if ferr:
                return ferr
            fields[k] = v
    for req_k in app._METADATA_SUGGEST_REQUIRES.get(sub, []):
        if not fields.get(req_k):
            return app._json_error(f"자동완성하려면 먼저 '{req_k}' 를 입력하세요.", 400)
    grounding = None
    if sub in ("tables", "columns"):
        grounding = _metadata_introspect_table(
            str(data.get("datasource") or ""), fields.get("schema_name") or "", fields.get("table_name") or ""
        )
    messages = _metadata_suggest_messages(sub, fields, grounding)
    text, meta, lerr = await app._metadata_llm_complete(messages, task="summary")
    if lerr:
        return lerr
    cap = app._METADATA_FIELD_CAPS.get(target)
    suggestion = text or ""
    if cap and len(suggestion) > cap:
        suggestion = suggestion[:cap].rstrip()
    return JSONResponse({
        "target": target,
        "suggestion": suggestion,
        "meta": {**(meta or {}), "grounded": bool(grounding and grounding.get("columns"))},
    })

@router.post("/api/admin/metadata/bootstrap/describe")
async def admin_metadata_bootstrap_describe(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """부트스트랩 일괄 AI 자동완성 — 골격(테이블/컬럼)의 설명을 1 LLM 호출로 생성(영속 안 함).

    프론트가 청크 단위(≤_METADATA_BULK_MAX_TABLES)로 호출해 진행률을 표면화한다. RBAC kb.ingest.manual.
    골격 식별자는 프롬프트 텍스트로만 사용(SQL 미사용)하므로 클라 제공 골격을 cap 후 신뢰한다.
    반환 results 는 {schema_name, table_name[, column_name], description} 리스트 — 프론트가 입력란에 채움.
    """
    # per-account rate-limit(429) — 청크 일괄 LLM dispatch 비용 DoS 방어. RBAC 통과 후 검사.
    if not app._search_rate_limit_check(int(account.get("id") or 0), max_per_min=app._METADATA_AI_RATE_PER_MIN):
        return app._json_error("일괄 자동완성 요청이 너무 잦습니다. 잠시 후 다시 시도하세요.", 429)
    data = await _metadata_read_json(request)
    mode = str(data.get("mode") or "tables").strip().lower()
    if mode not in ("tables", "columns"):
        return app._json_error("mode 는 tables/columns 중 하나여야 합니다.", 400)
    raw_tables = data.get("tables")
    if not isinstance(raw_tables, list) or not raw_tables:
        return app._json_error("tables 골격이 필요합니다.", 400)
    if len(raw_tables) > app._METADATA_BULK_MAX_TABLES:
        return app._json_error(f"1회 호출은 테이블 {app._METADATA_BULK_MAX_TABLES}개 이하만 처리합니다.", 400)
    tables: list = []
    for t in raw_tables:
        if not isinstance(t, dict):
            continue
        tname = str(t.get("table_name") or "").strip()[:128]
        if not tname:
            continue
        sname = str(t.get("schema_name") or "").strip()[:128]
        cols: list = []
        for c in (t.get("columns") or [])[:app._BOOTSTRAP_MAX_COLS_PER_TABLE]:
            if not isinstance(c, dict):
                continue
            cn = str(c.get("column_name") or "").strip()[:128]
            if cn:
                cols.append({"column_name": cn, "data_type": str(c.get("data_type") or "").strip()[:64]})
        tables.append({"schema_name": sname, "table_name": tname, "columns": cols})
    if not tables:
        return app._json_error("유효한 테이블이 없습니다.", 400)
    messages = _metadata_bulk_describe_messages(mode, tables)
    text, meta, lerr = await app._metadata_llm_complete(messages, task="prompt_gen", temperature=0.2)
    if lerr:
        return lerr
    parsed = _metadata_parse_json_object(text)
    if parsed is None:
        return app._json_error("AI 응답을 해석할 수 없습니다. 다시 시도하세요.", 502)
    results = _metadata_bulk_shape_results(mode, tables, parsed)
    return JSONResponse({"mode": mode, "results": results, "meta": {**(meta or {}), "count": len(results)}})
