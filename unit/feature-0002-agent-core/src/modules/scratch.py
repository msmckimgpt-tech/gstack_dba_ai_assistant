"""feature-0022: agent PG scratch workspace.

assistant 가 적절한 답변을 위해 PostgreSQL 안에 **자기 전용 낙서장 DB**(`agent_scratch`)를
자율적으로 다루는 기능. 다른 데이터소스/DB 의 데이터를 이 낙서장 테이블로 반입(materialize)한
뒤 PG 안에서 cross-source JOIN 을 수행하고, 설정된 TTL 주기(기본 24h)마다 임시데이터를 비운다.

경계 (ADR-SCRATCH-0001):
- **완전 자율 within sandbox**: agent_scratch_rw role 은 이 DB 안에서 스키마/테이블 CREATE·
  DROP·CRUD 자유. 밖으로의 도달 차단은 (a) non-superuser (b) 코드가 항상 agent_scratch 로만
  연결(`_pg_connect_scratch` dbname 고정) (c) PG 단일세션 cross-DB 불가 (d) 다른 DB 에 무-grant
  의 조합. `--harden-kb-isolation` 으로 sibling DB 의 PUBLIC CONNECT 회수 시 role 레벨까지 봉인.
- **대화별 격리**: 반입/생성 데이터는 대화별 스키마 `s_<hash(conversation_id)>` 아래 — 대화 A 가
  대화 B 의 데이터를 못 본다(datasource 가시성/window RBAC 격리를 materialization 후에도 보존).
  ⚠ 모든 s_* 는 동일 role 소유라 **PG 레벨 대화 격리는 없다** — 격리는 scratch_guard(allowlist)
  + search_path pin 에 의존한다(feature-0021 적대 리뷰 반영). 향후 대화별 전용 role 로 PG 레벨
  격리 승격 여지(REPORT 잔여).
- **governed 반입**: 반입 SELECT 는 execute_sql 과 **동일한** sql_guard + 제품 allowlist 게이트를
  통과한 데이터만 대상 (tools.py 핸들러가 게이트 후 본 모듈의 materialize() 를 호출) — 새 데이터
  유출 표면 0.
- **TTL cleanup**: `_scratch_admin.schema_registry` 의 last_used_at 기준으로 ask-worker 주기
  reaper 가 TTL 초과 대화 스키마를 DROP SCHEMA CASCADE.

본 모듈은 datasource guard 에 의존하지 않는다(순환 import 회피) — 반입 게이트는 tools.py 책임.
"""

from __future__ import annotations

import hashlib
import re
import sys
import time
from typing import Any

import shared.config as _cfg
import shared.db as _db
import shared.runtime_settings as _rts

# ── 런타임 설정 기본값 (runtime_settings 미등록/스냅샷 부재 시 폴백) ──────────────
_DEFAULTS = {
    "AGENT_SCRATCH_ENABLED": 0,             # 런타임 ON/OFF (기본 OFF — bootstrap 후 명시 활성화)
    "AGENT_SCRATCH_TTL_HOURS": 24,          # 대화 스키마 TTL (마지막 사용 후)
    "AGENT_SCRATCH_MAX_IMPORT_ROWS": 100000,  # 1회 반입 최대 행수
    "AGENT_SCRATCH_MAX_TABLES_PER_CONV": 50,  # 대화당 최대 테이블 수
    "AGENT_SCRATCH_MAX_SCHEMAS": 500,         # 전역 최대 대화 스키마 수 (disk 폭주 방지)
    "AGENT_SCRATCH_STMT_TIMEOUT_MS": 30000,   # scratch_sql 문당 statement_timeout
    "AGENT_SCRATCH_QUERY_PREVIEW_ROWS": 200,  # scratch_sql SELECT 미리보기 행수
}

_ADMIN_SCHEMA = "_scratch_admin"
_REGISTRY = f"{_ADMIN_SCHEMA}.schema_registry"
_SCHEMA_RE = re.compile(r"^s_[0-9a-f]{24}$")
_IDENT_SUB = re.compile(r"[^a-z0-9_]")


def _rt(key: str) -> int:
    """runtime setting 정수값 — 미등록 시 _DEFAULTS 폴백 (fail-open)."""
    try:
        spec = _rts.spec_for(key)
        if spec is not None:
            return _rts.get_int(key)
    except Exception:
        pass
    return int(_DEFAULTS.get(key, 0))


def enabled() -> bool:
    """런타임 스위치 ON + 인프라(psycopg + AGENT_SCRATCH_PG_*) 준비 완료."""
    try:
        if _rt("AGENT_SCRATCH_ENABLED") != 1:
            return False
        return _db._scratch_pg_available()
    except Exception:
        return False


# ── 식별자 / 스키마명 ────────────────────────────────────────────────────────
def schema_for(conversation_id: Any) -> str | None:
    """대화 id → 결정론적·안전한 PG 스키마명 `s_<sha1[:24]>`. 빈 값이면 None."""
    text = str(conversation_id or "").strip()
    if not text:
        return None
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]
    return f"s_{h}"


def _safe_ident(name: Any, fallback: str) -> str:
    """임의 문자열 → 유효한 PG 식별자(소문자, [a-z0-9_], 63자 cap, 선두 문자/밑줄)."""
    raw = str(name or "").strip().lower()
    cleaned = _IDENT_SUB.sub("_", raw)[:63]
    if not cleaned or not re.match(r"^[a-z_]", cleaned):
        cleaned = (fallback + ("_" + cleaned if cleaned else ""))[:63]
    return cleaned or fallback


def _dedupe_idents(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for n in names:
        if n in seen:
            seen[n] += 1
            cand = f"{n[:60]}_{seen[n]}"
        else:
            seen[n] = 0
            cand = n
        out.append(cand)
    return out


# ── 타입 추론 ────────────────────────────────────────────────────────────────
def infer_pg_type(values: list[Any]) -> str:
    """컬럼 값 표본 → PG 타입. 혼합/불명은 text (JOIN·저장 안전 우선)."""
    import datetime as _dt
    from decimal import Decimal

    seen = False
    all_bool = all_int = all_num = all_dt = True
    for v in values:
        if v is None:
            continue
        seen = True
        if isinstance(v, bool):
            all_int = all_num = all_dt = False
        else:
            all_bool = False
            if isinstance(v, int):
                pass  # int 은 bigint·double 후보 유지
            elif isinstance(v, (float, Decimal)):
                all_int = False
            else:
                all_int = all_num = False
            if not isinstance(v, _dt.datetime):
                all_dt = False
    if not seen:
        return "text"
    if all_bool:
        return "boolean"
    if all_int:
        return "bigint"
    if all_num:
        return "double precision"
    if all_dt:
        return "timestamptz"
    return "text"


# ── 연결 / 스키마 lifecycle ──────────────────────────────────────────────────
def _connect():
    return _db._pg_connect_scratch(autocommit=True)


def ensure_schema(conn, conversation_id: Any) -> str:
    """대화 스키마 생성(멱등) + 레지스트리 upsert. 스키마명 반환. 전역 스키마 캡 강제."""
    schema = schema_for(conversation_id)
    if not schema:
        raise ValueError("conversation_id 가 비어 있어 scratch 스키마를 결정할 수 없습니다.")
    from psycopg import sql as _sql
    with conn.cursor() as cur:
        # 전역 스키마 캡 — 신규 스키마 생성 전 체크(기존 스키마 재사용은 통과).
        cur.execute(f"SELECT 1 FROM {_REGISTRY} WHERE schema_name = %s", (schema,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(f"SELECT count(*) FROM {_REGISTRY}")
            total = int((cur.fetchone() or [0])[0])
            cap = _rt("AGENT_SCRATCH_MAX_SCHEMAS")
            if total >= cap:
                # 캡 도달 시 만료분 우선 정리 후 재확인(자기치유).
                sweep_expired_schemas()
                cur.execute(f"SELECT count(*) FROM {_REGISTRY}")
                total = int((cur.fetchone() or [0])[0])
                if total >= cap:
                    raise RuntimeError(
                        f"scratch 스키마 전역 한도({cap}) 도달 — 잠시 후 다시 시도하세요."
                    )
        cur.execute(_sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(_sql.Identifier(schema)))
        cur.execute(
            f"""INSERT INTO {_REGISTRY} (schema_name, conversation_id, created_at, last_used_at)
                VALUES (%s, %s, now(), now())
                ON CONFLICT (schema_name)
                DO UPDATE SET last_used_at = now()""",
            (schema, str(conversation_id)),
        )
    return schema


def _touch(conn, schema: str) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {_REGISTRY}
                    SET last_used_at = now(),
                        table_count = (SELECT count(*) FROM information_schema.tables
                                       WHERE table_schema = %s)
                    WHERE schema_name = %s""",
                (schema, schema),
            )
    except Exception:
        pass


def _table_count(conn, schema: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
            (schema,),
        )
        return int((cur.fetchone() or [0])[0])


# ── 반입(materialize) ────────────────────────────────────────────────────────
def materialize(conversation_id: Any, dest_table: Any,
                columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    """governed read 로 얻은 (columns, rows) 를 대화 스키마의 테이블로 적재.

    tools.py 의 scratch_import 핸들러가 datasource guard 통과 후 호출한다.
    테이블이 있으면 DROP 후 재생성(replace semantics — 반입은 스냅샷). 행수 캡 적용.
    반환: {ok, schema, table, columns, row_count, truncated} 또는 {ok:False, error}.
    """
    if not enabled():
        return {"ok": False, "error": "scratch workspace 가 비활성 상태입니다."}
    from psycopg import sql as _sql

    tbl = _safe_ident(dest_table, "t_imported")
    # scratch_guard 가 pg_ 접두 테이블 참조를 차단하므로, 반입 테이블이 조회 불가해지지 않도록
    # pg_ 로 시작하면 접두를 붙인다(시스템 카탈로그명 오인 방지).
    if tbl.startswith("pg_"):
        tbl = "t_" + tbl
    if not columns:
        return {"ok": False, "error": "반입할 컬럼이 없습니다(빈 결과)."}

    cap = _rt("AGENT_SCRATCH_MAX_IMPORT_ROWS")
    truncated = len(rows) > cap
    rows = rows[:cap]

    col_idents = _dedupe_idents([_safe_ident(c, f"col_{i}") for i, c in enumerate(columns)])
    col_types = [
        infer_pg_type([r[i] if i < len(r) else None for r in rows])
        for i in range(len(col_idents))
    ]
    text_cols = {i for i, t in enumerate(col_types) if t == "text"}

    conn = None
    try:
        conn = _connect()
        schema = ensure_schema(conn, conversation_id)

        # 대화당 테이블 캡 — 신규 테이블일 때만 체크.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
                (schema, tbl),
            )
            is_new = cur.fetchone() is None
        if is_new:
            tcap = _rt("AGENT_SCRATCH_MAX_TABLES_PER_CONV")
            if _table_count(conn, schema) >= tcap:
                return {"ok": False, "error": f"대화당 테이블 한도({tcap}) 도달 — scratch_reset 로 정리하세요."}

        col_defs = _sql.SQL(", ").join(
            _sql.SQL("{} {}").format(_sql.Identifier(c), _sql.SQL(t))
            for c, t in zip(col_idents, col_types)
        )
        qtable = _sql.SQL("{}.{}").format(_sql.Identifier(schema), _sql.Identifier(tbl))
        with conn.cursor() as cur:
            cur.execute(_sql.SQL("DROP TABLE IF EXISTS {}").format(qtable))
            cur.execute(_sql.SQL("CREATE TABLE {} ({})").format(qtable, col_defs))

            if rows:
                placeholders = _sql.SQL(", ").join(_sql.Placeholder() * len(col_idents))
                ins = _sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    qtable,
                    _sql.SQL(", ").join(_sql.Identifier(c) for c in col_idents),
                    placeholders,
                )
                norm: list[list[Any]] = []
                ncols = len(col_idents)
                for r in rows:
                    row = list(r)[:ncols] + [None] * (ncols - len(r))
                    for i in text_cols:
                        if row[i] is not None:
                            row[i] = str(row[i])
                    norm.append(row)
                cur.executemany(ins, norm)
        _touch(conn, schema)
        return {
            "ok": True,
            "schema": schema,
            "table": tbl,
            "columns": [{"name": c, "type": t} for c, t in zip(col_idents, col_types)],
            "row_count": len(rows),
            "truncated": truncated,
        }
    except Exception as exc:
        return {"ok": False, "error": f"materialize 실패: {exc}"}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ── scratch SQL guard (역-태세: DDL/DML 허용, 대화 스키마 밖 접근 차단) ─────────
_FORBIDDEN_SCRATCH_FUNCS = frozenset({
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_get", "lo_put",
    "dblink", "dblink_connect", "dblink_exec", "dblink_open",
    "pg_sleep", "pg_sleep_for", "pg_terminate_backend", "pg_cancel_backend",
    "pg_reload_conf", "pg_read_server_files", "set_config",
    "query_to_xml", "current_setting",
})


def scratch_guard(sql: str, conv_schema: str) -> tuple[bool, str]:
    """scratch_sql 검증 — **allowlist 방식**. (ok, reason) 반환. 파싱 실패=deny(fail-closed).

    보안 근거(feature-0021 적대 리뷰 BLOCK 대응): 대화별 스키마는 모두 동일 role 이 소유하므로
    PG 레벨 격리가 없다 → 격리는 이 guard + search_path pin 에만 의존한다. 따라서 **허용 구문을
    명시 열거**하고 그 외는 전부 거부한다(denylist 반전). 특히:
      - CREATE FUNCTION/PROCEDURE/VIEW/TRIGGER 등은 **본문이 문자열 리터럴**이라 sqlglot 이
        내부 table/func 참조를 못 보고 통과시킨다(cross-대화 read/write 은닉 벡터) → 전면 거부.
        허용 CREATE 는 kind ∈ {TABLE, INDEX} 뿐(본문이 AST 로 노출돼 참조 검사가 유효).
      - pg_catalog 관계(`pg_class`/`pg_namespace`/...)는 무자격으로 써도 항상 해석돼 타 대화
        스키마/컬럼을 열거할 수 있다 → 테이블명 `pg_` 접두 전면 거부.
    """
    raw = (sql or "").strip()
    if not raw:
        return (False, "empty SQL")
    try:
        import sqlglot
        from sqlglot import exp
    except Exception:
        return (False, "sqlglot 미설치 — scratch_sql 비활성")
    try:
        parsed = sqlglot.parse(raw, dialect="postgres")
    except Exception as exc:
        return (False, f"파싱 실패: {exc}")
    parsed = [s for s in parsed if s is not None]
    if len(parsed) != 1:
        return (False, "단일 statement 만 허용됩니다(세미콜론 분리 다중문 금지).")
    root = parsed[0]
    cls = type(root).__name__

    # ── allowlist: 허용 root 구문만 통과 ──────────────────────────────────
    _READ_ROOTS = {"Select", "With", "Subquery", "Union", "Intersect", "Except", "SetOperation", "Values"}
    _DML_ROOTS = {"Insert", "Update", "Delete", "TruncateTable"}
    if cls in _READ_ROOTS or cls in _DML_ROOTS:
        pass
    elif cls in ("Create", "Drop"):
        # DDL 은 테이블/인덱스만 — FUNCTION/PROCEDURE/VIEW/TRIGGER/SCHEMA/EXTENSION/ROLE 등 거부.
        kind = str(getattr(root, "kind", "") or "").strip().upper()
        if kind not in ("TABLE", "INDEX"):
            return (False, f"허용되지 않는 {cls} 종류: {kind or '(unknown)'} (테이블/인덱스만 가능)")
    else:
        # Command(DO/CALL/CREATE EXTENSION/VACUUM/GRANT/...), Copy, Set, Alter 등 전면 거부.
        return (False, f"허용되지 않는 구문: {cls}")

    # ── 모든 table 참조 검사(모든 분기·서브쿼리·CTAS 본문 포함) ──────────────
    for t in root.find_all(exp.Table):
        cat = (t.catalog or "").strip().lower()
        db = (t.db or "").strip().lower()
        name = (t.name or "").strip().lower()
        if cat:
            return (False, f"교차-DB 참조 금지: {cat}")
        if db and db != conv_schema.lower():
            return (False, f"대화 스키마({conv_schema}) 밖 참조 금지: {db}")
        # pg_catalog 관계(무자격이어도 항상 해석) — 타 대화 메타데이터 열거 차단(HIGH).
        if name.startswith("pg_"):
            return (False, f"시스템 카탈로그 참조 금지: {name}")

    # ── 위험 함수 차단 ─────────────────────────────────────────────────────
    for fn in root.find_all(exp.Func):
        if isinstance(fn, exp.Anonymous):
            name = str(getattr(fn, "name", "") or "").lower()
        else:
            try:
                name = fn.sql_name().lower()
            except Exception:
                name = type(fn).__name__.lower()
        if name in _FORBIDDEN_SCRATCH_FUNCS or name.startswith("pg_"):
            return (False, f"금지 함수: {name}()")

    return (True, "")


def run_sql(conversation_id: Any, sql: str) -> dict[str, Any]:
    """대화 스키마 안에서 자율 SQL(DDL/DML/JOIN) 실행. guard + search_path pin + timeout.

    반환: SELECT 계열이면 {ok, columns, rows(preview), row_count, truncated};
    그 외(DDL/DML)면 {ok, rowcount, message}. 오류면 {ok:False, error}.
    """
    if not enabled():
        return {"ok": False, "error": "scratch workspace 가 비활성 상태입니다."}
    schema = schema_for(conversation_id)
    if not schema:
        return {"ok": False, "error": "conversation_id 미지정 — scratch_sql 불가."}
    ok, reason = scratch_guard(sql, schema)
    if not ok:
        return {"ok": False, "error": f"scratch 정책 차단: {reason}"}

    from psycopg import sql as _sql
    conn = None
    try:
        conn = _connect()
        ensure_schema(conn, conversation_id)
        with conn.cursor() as cur:
            # 대화 스키마로 search_path 고정(무자격 이름은 여기서만 해석) + 문당 timeout.
            cur.execute(_sql.SQL("SET search_path TO {}").format(_sql.Identifier(schema)))
            cur.execute("SET statement_timeout = %s", (int(_rt("AGENT_SCRATCH_STMT_TIMEOUT_MS")),))
            cur.execute(sql)
            if cur.description is not None:
                colnames = [d.name for d in cur.description]
                preview_cap = _rt("AGENT_SCRATCH_QUERY_PREVIEW_ROWS")
                fetched = cur.fetchmany(preview_cap + 1)
                truncated = len(fetched) > preview_cap
                data = [list(r) for r in fetched[:preview_cap]]
                _touch(conn, schema)
                return {
                    "ok": True, "columns": colnames, "rows": data,
                    "row_count": len(data), "truncated": truncated,
                }
            rc = cur.rowcount
        _touch(conn, schema)
        return {"ok": True, "rowcount": rc, "message": "실행 완료"}
    except Exception as exc:
        return {"ok": False, "error": f"scratch_sql 실행 오류: {exc}"}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def list_workspace(conversation_id: Any) -> dict[str, Any]:
    """대화 스키마의 테이블·행수 요약."""
    if not enabled():
        return {"ok": False, "error": "scratch workspace 가 비활성 상태입니다."}
    schema = schema_for(conversation_id)
    if not schema:
        return {"ok": False, "error": "conversation_id 미지정."}
    conn = None
    try:
        conn = _connect()
        tables: list[dict[str, Any]] = []
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.relname, coalesce(c.reltuples::bigint, 0)
                   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = %s AND c.relkind = 'r' ORDER BY c.relname""",
                (schema,),
            )
            for name, approx in cur.fetchall():
                tables.append({"table": name, "approx_rows": int(approx)})
        return {"ok": True, "schema": schema, "tables": tables}
    except Exception as exc:
        return {"ok": False, "error": f"list 실패: {exc}"}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def reset(conversation_id: Any) -> dict[str, Any]:
    """대화 스키마 전체 삭제(DROP SCHEMA CASCADE) + 재생성 + 레지스트리 갱신."""
    if not enabled():
        return {"ok": False, "error": "scratch workspace 가 비활성 상태입니다."}
    schema = schema_for(conversation_id)
    if not schema:
        return {"ok": False, "error": "conversation_id 미지정."}
    from psycopg import sql as _sql
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(_sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(_sql.Identifier(schema)))
            cur.execute(f"DELETE FROM {_REGISTRY} WHERE schema_name = %s", (schema,))
        ensure_schema(conn, conversation_id)
        return {"ok": True, "schema": schema, "message": "작업공간을 비웠습니다."}
    except Exception as exc:
        return {"ok": False, "error": f"reset 실패: {exc}"}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ── TTL reaper (ask-worker 주기 호출) ────────────────────────────────────────
def sweep_expired_schemas(now: float | None = None) -> int:
    """마지막 사용 후 TTL(기본 24h) 초과 대화 스키마를 DROP. 삭제 수 반환.

    인프라 미설정/비활성이어도 안전(no-op). ask-worker reaper 가 주기 호출.
    """
    try:
        if not _db._scratch_pg_available():
            return 0
    except Exception:
        return 0
    ttl_hours = max(1, _rt("AGENT_SCRATCH_TTL_HOURS"))
    from psycopg import sql as _sql
    removed = 0
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT schema_name FROM {_REGISTRY}
                    WHERE last_used_at < now() - make_interval(hours => %s)""",
                (ttl_hours,),
            )
            expired = [row[0] for row in cur.fetchall()]
        for schema in expired:
            if not _SCHEMA_RE.match(str(schema or "")):
                continue  # 안전: 레지스트리 오염 시 s_* 형식만 DROP.
            try:
                with conn.cursor() as cur:
                    cur.execute(_sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(_sql.Identifier(schema)))
                    cur.execute(f"DELETE FROM {_REGISTRY} WHERE schema_name = %s", (schema,))
                removed += 1
            except Exception:
                continue
    except Exception as exc:
        print(f"[scratch] sweep skipped: {exc}", file=sys.stderr)
        return removed
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    if removed:
        print(f"[scratch] expired schemas removed: {removed}", file=sys.stderr)
    return removed
