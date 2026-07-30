"""metadata_stats — 노드 분석 접지용 통계 증거층 (feature-0031-analysis-grounding, L0).

그래프 뷰 'AI 능동 분석'의 LLM 입력에는 지금까지 **데이터 실측이 전혀 없었다** — 이름·설명·이웃
관계만 주고, 프롬프트가 "이름 규칙에서 가장 그럴듯한 의미를 추론하라"고 지시한다. 본 모듈은 운영
DB 에서 **통계만** 수집해 `metadata_table_stats` / `metadata_column_stats`(alembic 0050) 에 적재하고,
분석 payload 의 `evidence` 블록으로 되돌려준다. LLM 호출 수는 늘지 않는다 — 같은 콜에 더 나은 입력.

설계 불변식 (전부 load-bearing):

1. **원시 샘플값 미저장·미주입.** 컬럼 값 자체는 어떤 형태로도 저장하지 않는다. 문자열 컬럼의
   min/max 값도 저장하지 않는다 — 문자열 극단값은 사실상 원시 샘플 1건이며 이름·이메일 컬럼에서는
   곧 PII 다. 대신 길이 분포와 패턴 클래스(`value_pattern`)를 남긴다. 표본 행은 프로세스 안에서
   집계 즉시 폐기되고, 로그·예외 메시지에도 값이 실리지 않는다(식별자만 기록).
2. **보수적 시작 → 점진 승격.** 첫 수집은 Stage 0(카탈로그만 — 사용자 테이블 read 0). 이후
   하루에 최대 1단계씩만 올라가고, 주간에는 시간창 상한에 막힌다. Stage 3(정밀)은 운영자가
   상한 knob 을 명시적으로 올려야만 도달한다. AIMD 류 자동 증감은 쓰지 않는다 — 우리가 운영 DB 의
   지배적 부하원이 아니고 신호 지연이 커서 발진 위험이 있다.
3. **fail-soft.** 수집 실패·예산 거절은 분석을 막지 않는다. 증거 없이 분석하던 종전 동작으로
   그대로 진행하고 다음 주기에 재시도한다.
4. **`ds` 자원 예산 게이트 위에서만 운영 DB 에 붙는다**(feature-0025 T0b). 전역 kill-switch
   `AGENT_BACKGROUND_ANALYSIS_ENABLED` 하위.
5. **`COUNT(*)` 전수 스캔 금지.** 행 수는 카탈로그 추정치를 쓴다.

이 통계는 `semantic_cluster` 의 RC4 시그니처에 넣지 않는다 — 넣으면 통계가 갱신될 때마다 전량
재임베딩·재클러스터가 유발된다. 증거 변경은 L2 요약 캐시 키로만 전파한다.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re

from shared import config as _cfg

_log = logging.getLogger("metadata_stats")


# ── 설정 ────────────────────────────────────────────────────────────────────
#: Stage 정의 — 0=카탈로그만 · 1=표본 100 · 2=표본 1,000 · 3=정밀(운영자 승격)
STAGE_SAMPLE_ROWS = {0: 0, 1: 100, 2: 1000, 3: 10000}
MAX_STAGE = 3

#: 표본 SELECT 가 읽는 컬럼 상한 — 폭 넓은 테이블에서 전송량 방어.
_SAMPLE_COLUMN_CAP = 60

#: 한 번 수집한 테이블을 다시 보기까지의 최소 간격(시간). 승격 판정도 이 간격 이후에만 일어난다.
_DEFAULT_REFRESH_HOURS = 24

#: 주간(업무시간)에 허용하는 최대 Stage — 야간에만 더 깊이 판다.
_DEFAULT_DAY_MAX_STAGE = 1
_NIGHT_START_HOUR = 22   # 로컬 22:00 ~
_NIGHT_END_HOUR = 8      # ~ 08:00 을 야간으로 본다


def _knob_int(name: str, fallback: int) -> int:
    """runtime_settings live override → shared.config → fallback 순으로 정수 knob 을 읽는다."""
    try:
        from shared import runtime_settings as _rts
        return int(_rts.get_int(name))
    except Exception:
        pass
    try:
        return int(getattr(_cfg, name, fallback))
    except (TypeError, ValueError):
        return fallback


def enabled() -> bool:
    """증거 수집 활성 여부. 전역 kill-switch 하위이며, 설정 조회 실패는 비활성(보수)으로 본다."""
    if not _knob_int("AGENT_METADATA_STATS_ENABLED", 1):
        return False
    try:
        from shared import resource_budget as _rb
        return bool(_rb.background_enabled())
    except Exception:
        return True   # 예산 모듈 부재 환경(테스트·경량 배포)에서는 자체 knob 만 본다


def _is_night(now: _dt.datetime | None = None) -> bool:
    """야간 시간창 판정(서버 로컬 시각). 22:00~08:00 을 야간으로 본다."""
    h = (now or _dt.datetime.now()).hour
    return h >= _NIGHT_START_HOUR or h < _NIGHT_END_HOUR


def stage_ceiling(now: _dt.datetime | None = None) -> int:
    """지금 이 순간 허용되는 최대 Stage — 운영자 상한과 시간창 상한 중 낮은 쪽."""
    ceiling = max(0, min(MAX_STAGE, _knob_int("AGENT_METADATA_STATS_MAX_STAGE", 2)))
    if not _is_night(now):
        ceiling = min(ceiling, max(0, _knob_int("AGENT_METADATA_STATS_DAY_MAX_STAGE",
                                                _DEFAULT_DAY_MAX_STAGE)))
    return ceiling


def plan_stage(prev_stage, collected_at, *, now=None, ceiling=None) -> int | None:
    """다음 수집이 어느 Stage 로 갈지 판정. `None` 이면 이번엔 수집하지 않는다.

    - 미수집 테이블 → Stage 0(카탈로그만). 첫 접촉에서 사용자 테이블을 읽지 않는다.
    - 마지막 수집이 refresh 간격 이내 → None(수집 안 함).
    - 간격이 지났으면 **한 단계만** 승격(상한 초과 금지). 상한에 이미 도달했으면 같은 Stage 로
      재수집(통계 신선도 유지)한다.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    # ⚠ 시간창(주/야) 판정은 **서버 로컬 시각** 기준이다. `now` 는 경과 시간 계산용 UTC 값이라
    #   그대로 넘기면 UTC 의 hour 로 주·야를 가르게 되고, 서버 TZ 가 UTC 가 아니면(우리는
    #   Asia/Tokyo) 야간 창이 통째로 어긋난다. 그래서 인자 없이 호출한다.
    ceil_ = stage_ceiling() if ceiling is None else max(0, min(MAX_STAGE, int(ceiling)))
    if prev_stage is None or collected_at is None:
        return 0
    refresh_h = max(1, _knob_int("AGENT_METADATA_STATS_REFRESH_HOURS", _DEFAULT_REFRESH_HOURS))
    try:
        age = now - collected_at
    except TypeError:
        # naive/aware 혼합 — 비교 불가면 보수적으로 "아직 이르다"로 본다(과수집 방지).
        return None
    if age < _dt.timedelta(hours=refresh_h):
        return None
    return max(0, min(int(prev_stage) + 1, ceil_))


# ── 값 패턴 분류 (값이 아니라 형태) ──────────────────────────────────────────
_RE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RE_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_RE_DIGITS = re.compile(r"[+-]?[0-9]+")
_RE_HEX = re.compile(r"(0[xX])?[0-9a-fA-F]{4,}")

#: DB CHECK 제약(ck_metadata_column_stats_pattern)과 1:1 정합해야 하는 열거.
VALUE_PATTERNS = ("digits", "hex", "uuid", "email_like", "mixed", "empty")


def classify_pattern(values) -> str:
    """문자열 표본의 **형태**를 분류한다 — 반환값은 언제나 `VALUE_PATTERNS` 의 원소다.

    입력 값 자체는 반환되지 않는다(원시값 유출 차단). 서로 다른 형태가 섞이면 'mixed'.
    """
    kinds = set()
    for v in values or ():
        if v is None:
            kinds.add("empty")
            continue
        s = str(v).strip()
        if not s:
            kinds.add("empty")
            continue
        if _RE_UUID.fullmatch(s):
            kinds.add("uuid")
        elif _RE_EMAIL.fullmatch(s):
            kinds.add("email_like")
        elif _RE_DIGITS.fullmatch(s):
            kinds.add("digits")
        elif _RE_HEX.fullmatch(s):
            kinds.add("hex")
        else:
            kinds.add("mixed")
    non_empty = kinds - {"empty"}
    if not non_empty:
        return "empty"
    if len(non_empty) == 1:
        return next(iter(non_empty))
    return "mixed"


# ── 식별자 인용 ─────────────────────────────────────────────────────────────
#: 표본 SELECT 는 식별자를 SQL 에 직접 넣는다. 화이트리스트 통과분만 인용해 조립한다.
_IDENT_OK = re.compile(r"^[A-Za-z0-9_$#@ .\-]{1,128}$")


def _quote_ident(name: str, engine: str) -> str | None:
    """식별자를 엔진 관례로 인용. 화이트리스트를 벗어나면 None(해당 대상 수집 포기)."""
    s = str(name or "").strip()
    if not s or not _IDENT_OK.match(s):
        return None
    if engine == "mssql":
        return "[" + s.replace("]", "]]") + "]"
    return "`" + s.replace("`", "``") + "`"


# ── 카탈로그 수집 (Stage 0) ─────────────────────────────────────────────────
def _fetch_catalog(cur, engine: str, schema: str, table: str) -> dict:
    """카탈로그(information_schema / sys)에서 구조 정보를 읽는다 — 사용자 테이블 read 0."""
    out = {"columns": [], "row_count_est": None, "pk_columns": [], "index_columns": [],
           "fk_out": None, "fk_in": None}
    if engine == "mssql":
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
            (table,))
    else:
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH "
            "FROM information_schema.columns WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION", (schema, table))
    for r in cur.fetchall() or ():
        name = str(r[0] or "").strip()
        if not name:
            continue
        try:
            cmax = int(r[3]) if r[3] is not None else None
        except (TypeError, ValueError):
            cmax = None
        out["columns"].append({
            "name": name,
            "data_type": str(r[1] or "")[:64].lower(),
            "is_nullable": str(r[2] or "").strip().upper() == "YES",
            "char_max_len": cmax,
        })

    def _try(fn):
        """카탈로그 보조 조회는 권한·버전 차이로 실패할 수 있다 — 개별 실패를 흡수한다."""
        try:
            fn()
        except Exception as exc:
            _log.debug("catalog_part_failed schema=%s table=%s err=%r", schema, table, exc)

    if engine == "mssql":
        # ⚠ MSSQL 규약: 여기서 `schema` 는 스키마가 아니라 **effective DB(catalog)** 이고,
        #   호출측이 이미 그 DB 로 접속했다(`_introspect_table_columns` 동형). 따라서
        #   OBJECT_ID 에 "<schema>.<table>" 을 넘기면 MSSQL 이 그것을 schema.object 로
        #   해석해 매칭에 실패하고 row count·FK·인덱스가 통째로 NULL 이 된다 — 테이블명만 넘긴다.
        def _rows():
            cur.execute("SELECT SUM(row_count) FROM sys.dm_db_partition_stats "
                        "WHERE object_id = OBJECT_ID(%s) AND index_id IN (0, 1)", (table,))
            row = cur.fetchone()
            out["row_count_est"] = int(row[0]) if row and row[0] is not None else None

        def _pk():
            cur.execute(
                "SELECT kcu.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
                "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
                "WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
                "ORDER BY kcu.ORDINAL_POSITION", (table,))
            out["pk_columns"] = [str(r[0]) for r in cur.fetchall() or () if r and r[0]]

        def _fk():
            cur.execute("SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(%s)",
                        (table,))
            out["fk_out"] = int((cur.fetchone() or [0])[0] or 0)
            cur.execute("SELECT COUNT(*) FROM sys.foreign_keys "
                        "WHERE referenced_object_id = OBJECT_ID(%s)", (table,))
            out["fk_in"] = int((cur.fetchone() or [0])[0] or 0)

        def _idx():
            cur.execute(
                "SELECT DISTINCT c.name FROM sys.index_columns ic "
                "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
                "WHERE ic.object_id = OBJECT_ID(%s)", (table,))
            out["index_columns"] = [str(r[0]) for r in cur.fetchall() or () if r and r[0]]
    else:
        def _rows():
            cur.execute("SELECT TABLE_ROWS FROM information_schema.tables "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (schema, table))
            row = cur.fetchone()
            out["row_count_est"] = int(row[0]) if row and row[0] is not None else None

        def _pk():
            cur.execute("SELECT COLUMN_NAME FROM information_schema.statistics "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = 'PRIMARY' "
                        "ORDER BY SEQ_IN_INDEX", (schema, table))
            out["pk_columns"] = [str(r[0]) for r in cur.fetchall() or () if r and r[0]]

        def _fk():
            cur.execute("SELECT COUNT(*) FROM information_schema.key_column_usage "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "AND REFERENCED_TABLE_NAME IS NOT NULL", (schema, table))
            out["fk_out"] = int((cur.fetchone() or [0])[0] or 0)
            cur.execute("SELECT COUNT(*) FROM information_schema.key_column_usage "
                        "WHERE REFERENCED_TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME = %s",
                        (schema, table))
            out["fk_in"] = int((cur.fetchone() or [0])[0] or 0)

        def _idx():
            cur.execute("SELECT DISTINCT COLUMN_NAME FROM information_schema.statistics "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (schema, table))
            out["index_columns"] = [str(r[0]) for r in cur.fetchall() or () if r and r[0]]

    _try(_rows)
    _try(_pk)
    _try(_fk)
    _try(_idx)
    return out


# ── 표본 통계 (Stage ≥ 1) ───────────────────────────────────────────────────
_NUMERIC_TYPES = {"int", "integer", "bigint", "smallint", "tinyint", "mediumint", "decimal",
                  "numeric", "float", "double", "real", "money", "smallmoney", "bit"}
_TEMPORAL_TYPES = {"date", "datetime", "datetime2", "smalldatetime", "timestamp", "time",
                   "datetimeoffset", "year"}


def _sample_rows(cur, engine: str, schema: str, table: str, columns: list, limit: int):
    """표본 행을 읽어 (컬럼명 리스트, 행 리스트) 반환. 실패 시 (None, None).

    ⚠ 반환된 행은 호출측이 **집계 직후 폐기**한다 — 저장·로깅 금지.
    """
    names = [c["name"] for c in columns[:_SAMPLE_COLUMN_CAP]]
    quoted = [_quote_ident(n, engine) for n in names]
    pairs = [(n, q) for n, q in zip(names, quoted) if q]
    if not pairs:
        return None, None
    names = [n for n, _ in pairs]
    col_sql = ", ".join(q for _, q in pairs)
    qtable = _quote_ident(table, engine)
    qschema = _quote_ident(schema, engine) if schema else None
    if not qtable:
        return None, None
    if engine == "mssql":
        # MSSQL 은 INFORMATION_SCHEMA 가 DB(catalog)별이라 이미 해당 DB 로 접속돼 있다 —
        # 스키마 한정 없이 테이블명으로 조회한다(dialects.describe_columns 의 빈-스키마 관례와 동형).
        sql = "SELECT TOP %d %s FROM %s" % (int(limit), col_sql, qtable)
    else:
        target = "%s.%s" % (qschema, qtable) if qschema else qtable
        sql = "SELECT %s FROM %s LIMIT %d" % (col_sql, target, int(limit))
    cur.execute(sql)
    return names, (cur.fetchall() or [])


def _aggregate_sample(columns: list, names: list, rows) -> dict:
    """표본 행 → 컬럼별 집계. **원시값은 반환하지 않는다**(숫자·시각 min/max 만 값이다)."""
    by_name = {c["name"]: c for c in columns}
    stats = {}
    for idx, name in enumerate(names):
        meta = by_name.get(name) or {}
        dtype = str(meta.get("data_type") or "").lower()
        seen, nulls, total = set(), 0, 0
        num_min = num_max = None
        ts_min = ts_max = None
        len_min = len_max = None
        len_sum = len_cnt = 0
        text_values = []
        for r in rows:
            total += 1
            try:
                v = r[idx]
            except (IndexError, TypeError):
                continue
            if v is None:
                nulls += 1
                continue
            try:
                seen.add(v if isinstance(v, (int, float, str, bytes, bool)) else str(v))
            except TypeError:
                pass
            if dtype in _NUMERIC_TYPES and isinstance(v, (int, float)) and not isinstance(v, bool):
                num_min = v if num_min is None or v < num_min else num_min
                num_max = v if num_max is None or v > num_max else num_max
            elif dtype in _TEMPORAL_TYPES and isinstance(v, (_dt.datetime, _dt.date)):
                dv = v if isinstance(v, _dt.datetime) else _dt.datetime.combine(v, _dt.time.min)
                ts_min = dv if ts_min is None or dv < ts_min else ts_min
                ts_max = dv if ts_max is None or dv > ts_max else ts_max
            else:
                s = v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
                ln = len(s)
                len_min = ln if len_min is None or ln < len_min else len_min
                len_max = ln if len_max is None or ln > len_max else len_max
                len_sum += ln
                len_cnt += 1
                if len(text_values) < 200:
                    text_values.append(s)
        if not total:
            continue
        non_null = total - nulls
        entry = {
            "distinct_est": len(seen),
            "null_ratio": round(nulls / total, 4),
            "unique_in_sample": bool(non_null) and len(seen) == non_null,
        }
        if num_min is not None:
            entry["num_min"], entry["num_max"] = num_min, num_max
        if ts_min is not None:
            entry["ts_min"], entry["ts_max"] = ts_min, ts_max
        if len_cnt:
            entry["len_min"], entry["len_max"] = len_min, len_max
            entry["len_avg"] = round(len_sum / len_cnt, 2)
            entry["value_pattern"] = classify_pattern(text_values)
        stats[name] = entry
        # 표본 원시값은 여기서 수명이 끝난다 — 다음 컬럼으로 넘어가기 전에 참조를 끊는다.
        text_values = []
    return stats


# ── 적재 ────────────────────────────────────────────────────────────────────
def _savepoint(c):
    """호출측 트랜잭션을 오염시키지 않기 위한 savepoint.

    ⚠ load-bearing: 이 모듈은 노드 분석과 **같은 PG 커넥션**을 쓴다. 신규 테이블이 아직 없는
    배포 창(코드 선행·마이그레이션 후행)에서 SELECT 가 실패하면 psycopg 는 트랜잭션 전체를
    abort 시키고, 그러면 뒤따르는 노드 분석 쿼리가 전부 깨진다 — 증거 수집 실패가 분석을 막지
    않는다는 계약이 무너진다. savepoint 를 못 여는 환경(스텁 커넥션 등)에서는 no-op 으로 둔다."""
    import contextlib
    try:
        return c.transaction()
    except Exception:
        return contextlib.nullcontext()


def _mark_error(c, scope: str, schema: str, table: str, stage: int, error: str) -> None:
    """수집 실패를 기록한다 — **기존 통계는 덮어쓰지 않는다**.

    실패 시 전체 행을 재작성하면 직전까지 유효했던 row_count_est·PK·인덱스가 NULL 로 지워져
    evidence 가 통째로 사라진다. 실패는 실패대로 남기고, 이미 모은 사실은 보존한다."""
    with _savepoint(c):
        cur = c.cursor()
        try:
            cur.execute(
                "INSERT INTO metadata_table_stats "
                "(scope_key, schema_name, table_name, stage, collected_at, error) "
                "VALUES (%s,%s,%s,%s,now(),%s) "
                "ON CONFLICT (scope_key, schema_name, table_name) DO UPDATE SET "
                " collected_at=EXCLUDED.collected_at, error=EXCLUDED.error",
                (scope, schema, table, int(stage), str(error)[:500]))
        finally:
            try:
                cur.close()
            except Exception:
                pass


def _upsert(c, scope: str, schema: str, table: str, catalog: dict, col_stats: dict,
            stage: int, sampled_rows: int, error=None) -> None:
    """수집 결과를 upsert. 컬럼 통계는 이번에 본 컬럼만 갱신한다(사라진 컬럼 행은 그대로 남는다 —
    다음 카탈로그 수집이 정리 대상을 판단할 때까지 오래된 행이 evidence 에 섞이지 않도록
    `collected_at` 으로 신선도를 함께 노출한다)."""
    cur = c.cursor()
    try:
        cols = catalog.get("columns") or []
        cur.execute(
            "INSERT INTO metadata_table_stats "
            "(scope_key, schema_name, table_name, row_count_est, column_count, pk_columns, "
            " index_columns, fk_out, fk_in, stage, sampled_rows, collected_at, error) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s) "
            "ON CONFLICT (scope_key, schema_name, table_name) DO UPDATE SET "
            " row_count_est=EXCLUDED.row_count_est, column_count=EXCLUDED.column_count, "
            " pk_columns=EXCLUDED.pk_columns, index_columns=EXCLUDED.index_columns, "
            " fk_out=EXCLUDED.fk_out, fk_in=EXCLUDED.fk_in, stage=EXCLUDED.stage, "
            " sampled_rows=EXCLUDED.sampled_rows, collected_at=EXCLUDED.collected_at, "
            " error=EXCLUDED.error",
            (scope, schema, table, catalog.get("row_count_est"), len(cols),
             catalog.get("pk_columns") or [], catalog.get("index_columns") or [],
             catalog.get("fk_out"), catalog.get("fk_in"), int(stage), int(sampled_rows),
             (str(error)[:500] if error else None)))
        for col in cols:
            st = col_stats.get(col["name"]) or {}
            cur.execute(
                "INSERT INTO metadata_column_stats "
                "(scope_key, schema_name, table_name, column_name, data_type, is_nullable, "
                " char_max_len, distinct_est, null_ratio, num_min, num_max, ts_min, ts_max, "
                " len_min, len_max, len_avg, value_pattern, unique_in_sample, stage, "
                " sampled_rows, collected_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) "
                "ON CONFLICT (scope_key, schema_name, table_name, column_name) DO UPDATE SET "
                " data_type=EXCLUDED.data_type, is_nullable=EXCLUDED.is_nullable, "
                " char_max_len=EXCLUDED.char_max_len, distinct_est=EXCLUDED.distinct_est, "
                " null_ratio=EXCLUDED.null_ratio, num_min=EXCLUDED.num_min, num_max=EXCLUDED.num_max, "
                " ts_min=EXCLUDED.ts_min, ts_max=EXCLUDED.ts_max, len_min=EXCLUDED.len_min, "
                " len_max=EXCLUDED.len_max, len_avg=EXCLUDED.len_avg, "
                " value_pattern=EXCLUDED.value_pattern, unique_in_sample=EXCLUDED.unique_in_sample, "
                " stage=EXCLUDED.stage, sampled_rows=EXCLUDED.sampled_rows, "
                " collected_at=EXCLUDED.collected_at",
                (scope, schema, table, col["name"], col.get("data_type"), col.get("is_nullable"),
                 col.get("char_max_len"), st.get("distinct_est"), st.get("null_ratio"),
                 st.get("num_min"), st.get("num_max"), st.get("ts_min"), st.get("ts_max"),
                 st.get("len_min"), st.get("len_max"), st.get("len_avg"),
                 st.get("value_pattern"), st.get("unique_in_sample"), int(stage),
                 int(sampled_rows)))
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _prev_state(c, scope: str, schema: str, table: str):
    """(stage, collected_at) — 미수집이면 (None, None)."""
    with _savepoint(c):
        cur = c.cursor()
        try:
            cur.execute("SELECT stage, collected_at FROM metadata_table_stats "
                        "WHERE scope_key=%s AND schema_name=%s AND table_name=%s",
                        (scope, schema, table))
            row = cur.fetchone()
            return (row[0], row[1]) if row else (None, None)
        finally:
            try:
                cur.close()
            except Exception:
                pass


# ── 공개 진입점 ─────────────────────────────────────────────────────────────
def collect_table(ds: dict, c, scope: str, schema: str, table: str, stage: int) -> bool:
    """한 테이블의 증거를 Stage 깊이로 수집·적재. 반환 True=적재됨.

    `ds` 자원 예산을 획득하지 못하면 아무것도 하지 않고 False(다음 주기 이월).

    게이트는 래퍼(여기)에서 `with` 로만 잡고 본체는 `_collect_table_inner` 에 둔다(ADR-0025-07) —
    수동 `__enter__`/`__exit__` 는 획득 직후 예외가 나면 반납이 빠질 수 있고, 슬롯 누수는 조용한
    전역 고장이 된다.
    """
    try:
        from shared import resource_budget as _rb
    except Exception:
        _rb = None
    if _rb is None:
        return _collect_table_inner(ds, c, scope, schema, table, stage)
    with _rb.acquire("ds") as ok:
        if not ok:
            _log.info("증거 수집 보류 — 소스 DB 연결 예산 여유 없음 (%s.%s, 다음 주기 재시도)",
                      schema, table)
            return False
        return _collect_table_inner(ds, c, scope, schema, table, stage)


def _collect_table_inner(ds: dict, c, scope: str, schema: str, table: str, stage: int) -> bool:
    """`collect_table` 본체 — 호출 시점에 `ds` 예산이 이미 확보돼 있다."""
    from shared import db as _db
    engine = str((ds or {}).get("engine") or "mysql").strip().lower()
    # ⚠ connect() 는 try 안에서 호출한다 — 연결 수립이 예외를 내도 finally 가 close 를 처리하게.
    conn = None
    try:
        conn = _db.connect(database=(schema if engine == "mssql" else None), datasource=ds)
        cur = conn.cursor()
        try:
            catalog = _fetch_catalog(cur, engine, schema, table)
            col_stats, sampled = {}, 0
            limit = STAGE_SAMPLE_ROWS.get(int(stage), 0)
            if limit > 0 and catalog.get("columns"):
                names, rows = _sample_rows(cur, engine, schema, table, catalog["columns"], limit)
                if names is not None and rows is not None:
                    sampled = len(rows)
                    col_stats = _aggregate_sample(catalog["columns"], names, rows)
                    rows = None   # 원시 표본 즉시 폐기
        finally:
            try:
                cur.close()
            except Exception:
                pass
        with _savepoint(c):
            _upsert(c, scope, schema, table, catalog, col_stats, stage, sampled)
        _log.info("증거 수집 완료 scope=%s %s.%s stage=%s cols=%s sampled=%s",
                  scope, schema, table, stage, len(catalog.get("columns") or []), sampled)
        return True
    except Exception as exc:
        # 실패해도 분석은 계속된다. **예외 문자열은 남기지 않는다** — 드라이버 오류 메시지에
        # 조회한 값이 실려 오는 경우가 있어(제약 위반·타입 변환 실패) 원시값 유출 경로가 된다.
        kind = type(exc).__name__
        _log.warning("증거 수집 실패 scope=%s %s.%s stage=%s err=%s", scope, schema, table, stage, kind)
        try:
            _mark_error(c, scope, schema, table, int(stage), kind)
        except Exception:
            pass
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def ensure_stats(ds: dict, c, scope: str, schema: str, table: str) -> None:
    """분석 직전 호출 — 필요하면(그리고 허용되면) 증거를 수집한다. 어떤 실패도 삼킨다.

    수집 대상 선정은 별도 스케줄러를 두지 않는다: **분석되는 테이블만** 본다. 노드 분석 자체가
    이미 페이싱돼 있으므로 수집 부하도 그 페이스를 그대로 물려받고, 쓰이지 않을 통계를 미리
    모으는 낭비가 없다.
    """
    if not enabled() or not scope or not schema or not table:
        return
    try:
        prev_stage, collected_at = _prev_state(c, scope, schema, table)
        stage = plan_stage(prev_stage, collected_at)
        if stage is None:
            return
        collect_table(ds, c, scope, schema, table, stage)
    except Exception as exc:
        _log.debug("ensure_stats_failed %s.%s err=%r", schema, table, exc)


def load_evidence(c, scope: str, schema: str, table: str, *, column_cap: int = 40) -> dict | None:
    """분석 payload 에 실을 `evidence` 블록을 조립한다. 증거가 없으면 None.

    비어 있는 값은 키 자체를 넣지 않는다(토큰 절약 + LLM 이 "없음"을 사실로 오독하지 않게).
    """
    if not scope or not schema or not table:
        return None
    try:
        # savepoint — 조회 실패(마이그레이션 전 배포 창 등)가 노드 분석의 트랜잭션을 죽이지 않게.
        with _savepoint(c):
            cur = c.cursor()
            try:
                cur.execute(
                    "SELECT row_count_est, column_count, pk_columns, index_columns, fk_out, fk_in, "
                    "       stage, sampled_rows, collected_at "
                    "FROM metadata_table_stats "
                    "WHERE scope_key=%s AND schema_name=%s AND table_name=%s",
                    (scope, schema, table))
                trow = cur.fetchone()
                if not trow:
                    return None
                cur.execute(
                    "SELECT column_name, data_type, is_nullable, distinct_est, null_ratio, "
                    "       num_min, num_max, ts_min, ts_max, len_min, len_max, len_avg, "
                    "       value_pattern, unique_in_sample "
                    "FROM metadata_column_stats "
                    "WHERE scope_key=%s AND schema_name=%s AND table_name=%s "
                    "ORDER BY column_name LIMIT %s",
                    (scope, schema, table, max(1, int(column_cap))))
                crows = cur.fetchall() or []
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
    except Exception as exc:
        _log.debug("load_evidence_failed %s.%s err=%r", schema, table, exc)
        return None

    ev = {"stage": int(trow[6] or 0), "sampled_rows": int(trow[7] or 0)}
    if trow[8] is not None:
        ev["collected_at"] = trow[8].strftime("%Y-%m-%d")
    if trow[0] is not None:
        ev["row_count_est"] = int(trow[0])
    if trow[1]:
        ev["column_count"] = int(trow[1])
    if trow[2]:
        ev["pk_columns"] = [str(x) for x in trow[2]][:16]
    if trow[3]:
        ev["indexed_columns"] = [str(x) for x in trow[3]][:24]
    if trow[4] is not None:
        ev["fk_out"] = int(trow[4])
    if trow[5] is not None:
        ev["fk_in"] = int(trow[5])

    cols = []
    for r in crows:
        item = {"name": str(r[0])}
        if r[1]:
            item["type"] = str(r[1])
        if r[2] is not None:
            item["nullable"] = bool(r[2])
        if r[3] is not None:
            item["distinct_est"] = int(r[3])
        if r[4] is not None:
            item["null_ratio"] = float(r[4])
        if r[5] is not None:
            item["min"] = float(r[5])
        if r[6] is not None:
            item["max"] = float(r[6])
        if r[7] is not None:
            item["min"] = r[7].strftime("%Y-%m-%d")
        if r[8] is not None:
            item["max"] = r[8].strftime("%Y-%m-%d")
        if r[11] is not None:
            item["len_avg"] = float(r[11])
        if r[12]:
            item["pattern"] = str(r[12])
        if r[13]:
            item["unique_in_sample"] = True
        cols.append(item)
    if cols:
        ev["columns"] = cols
    return ev
