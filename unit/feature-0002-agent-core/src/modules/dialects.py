"""SQL dialect 어댑터 (멀티 datasource Stage 2 P5).

MySQL / MSSQL 의 introspection·sampling SQL 을 엔진별로 산출한다. tools.py 의 스키마탐색·
샘플 SQL 이 본 모듈을 통해 dialect-aware 가 된다.

**골든 회귀 0**: `MySQLDialect` 는 P5 이전 tools.py 의 SQL 을 *글자 그대로* 산출한다(MySQL 동작
0 변경). `MSSQLDialect` 는 동일 **컬럼 순서**의 T-SQL 을 산출해 tools.py 의 결과 파싱(row[i])이
엔진 무관하게 유지된다.

**보안 주의 (P6 이월)**: 본 모듈은 *SQL 생성*만 담당한다. 식별자 인용은 dialect 별로 하지만,
allowlist(스키마 격리)·sql_guard(AST) 등 **보안 게이트의 dialect 화는 P6** 다. P5 단계에서
MSSQL datasource 를 실제 활성화하면 보안 게이트가 아직 MySQL 방언이라 위험하므로, flag OFF +
미바인딩 상태(shadow)에서만 의미를 갖는다.
"""
from __future__ import annotations

import re

from shared import config as cfg


# ── 사전 부하추정 파서 (엔진별 결과 → 예상 처리 행수) ──────────────────────────
def _parse_explain_rows_product(result_sets) -> int | None:
    """MySQL EXPLAIN 결과 → 테이블별 (rows × filtered/100) 곱 = join 후 예상 카디널리티.

    `filtered`(옵티마이저 선택률 %)를 반영해 잘 인덱싱된 조인의 과대추정(false-positive 게이팅)을
    줄인다. **골든**: 이전 tools.py `_estimate_explain_rows` 의 산식 그대로 — MySQL 동작 0 변경.
    """
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).lower() for c in columns]
        try:
            ridx = lcols.index("rows")
        except ValueError:
            continue
        fidx = lcols.index("filtered") if "filtered" in lcols else None
        product = 1
        seen = False
        for r in rows:
            try:
                v = int(r[ridx])
            except (ValueError, TypeError, IndexError):
                continue
            eff = float(v)
            if fidx is not None:
                try:
                    filt = float(r[fidx])
                    if 0.0 <= filt <= 100.0:
                        eff = v * (filt / 100.0)
                except (ValueError, TypeError, IndexError):
                    pass
            product *= max(1, int(round(eff)))
            seen = True
        if seen:
            return product
    return None


def _parse_showplan_estimate(result_sets) -> int | None:
    """MSSQL `SET SHOWPLAN_ALL` 결과 → 예상 처리 행수.

    추정 실행계획의 각 operator 행에서 `EstimateRows × EstimateExecutions`(중첩루프 inner side
    재실행 반영)를 구해 **최대값**을 "예상 처리 행수"로 산출. MySQL 의 rows×filtered 곱(join 후
    카디널리티)과 산식은 다르나 동일 임계값(AGENT_QUERY_EXPLAIN_ROWS_WARN)으로 무거운 쿼리를
    판정한다(=가장 무거운 단일 operator 가 처리하는 추정 행수). `EstimateRows` 컬럼 부재/전부
    파싱불가 시 None(추정 실패 → caller 가 엔진별 fail-open/closed 결정).

    **알려진 한계 (REV-20260617-0310 M1)**: `EstimateRows` 는 operator 의 *출력* 추정행수이지
    *스캔* 행수가 아니다 → 잔여 술어가 선택적인 비인덱스 풀스캔(많이 읽고 적게 출력)은 과소추정될
    수 있다(무거운 쿼리를 light 로 오판). 이 스캔-부하 공백은 게이트와 무관하게 항상 적용되는 런타임
    시간 cap(tools.py `_apply_query_cap`, `AGENT_QUERY_MAX_EXECUTION_MS`)이 2차 방어로 보완한다.
    더 정확한 비용 기반 게이트(`TotalSubtreeCost` 보조 임계)는 후속 cycle 이월.
    """
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).strip().lower() for c in columns]  # m2: 컬럼명 패딩 견고화
        if "estimaterows" not in lcols:
            continue
        ridx = lcols.index("estimaterows")
        eidx = lcols.index("estimateexecutions") if "estimateexecutions" in lcols else None
        best: int | None = None
        for r in rows:
            try:
                er = float(r[ridx])
            except (ValueError, TypeError, IndexError):
                continue
            ex = 1.0
            if eidx is not None:
                try:
                    ex = float(r[eidx])
                except (ValueError, TypeError, IndexError):
                    ex = 1.0
            if ex < 1.0:
                ex = 1.0
            eff = int(round(er * ex))
            if best is None or eff > best:
                best = eff
        if best is not None:
            return max(0, best)
    return None


# ── 실행계획 사실 추출 + LIMIT 상한 보정 (conv-audit FR-loadgate-blind-coaching) ──
# 배경(라이브 실측 2026-07-31): 부하게이트가 차단할 때 EXPLAIN 이 이미 알고 있는 "왜 무거운가"
# (접근형태·미사용 인덱스·스캔 파티션 수)를 **버리고** 정적 일반론만 돌려줘, 모델이 이미 시도한
# 조언을 다시 받고 같은 형태를 재제출 → 한 대화에서 6연속 차단. 아래 두 함수가 그 정보를 살린다.
def _parse_explain_plan_facts(result_sets) -> dict:
    """MySQL EXPLAIN 결과 → 차단 코칭용 실행계획 사실.

    반환 dict: `{"plan_rows": [ {table,select_type,type,key,possible_keys,parts,extra,rows,filtered} ],
    "worst": <rows 최대 항목|None>}`. 파싱 불가/컬럼 부재는 빈 dict — caller 는 facts 가 비면
    기존(정적) 문구로 폴백한다(추정치 자체는 `_parse_explain_rows_product` 가 독립 산출).
    """
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).strip().lower() for c in columns]
        if "rows" not in lcols:
            continue

        def _get(r, key):
            return r[lcols.index(key)] if key in lcols else None

        plan_rows: list[dict] = []
        for r in rows:
            try:
                nrows = int(_get(r, "rows"))
            except (ValueError, TypeError, IndexError):
                nrows = None
            parts = _get(r, "partitions")
            plan_rows.append({
                "table": _get(r, "table"),
                "select_type": _get(r, "select_type"),
                "type": _get(r, "type"),
                "key": _get(r, "key"),
                "possible_keys": _get(r, "possible_keys"),
                # 스캔 대상 파티션 수(프루닝 정도의 대리 지표). 비파티션 테이블은 None.
                "parts": len([p for p in str(parts).split(",") if p.strip()]) if parts else None,
                "extra": _get(r, "extra"),
                "rows": nrows,
                "filtered": _get(r, "filtered"),
            })
        if not plan_rows:
            return {}
        # 코칭 대상은 **실효 행수**(rows × filtered/100)가 가장 큰 항목이다 — raw `rows` 로 고르면
        # "rows 1,000만 · filtered 0.01%(인덱스 range)" 가 "rows 90만 · filtered 100%(풀스캔)" 을
        # 이겨, 실제 병목 테이블의 인덱스 부재를 숨기고 엉뚱한 대상을 안내한다(codex P2).
        worst = max(plan_rows, key=_effective_rows)
        return {"plan_rows": plan_rows, "worst": worst}
    return {}


def _effective_rows(pr: dict) -> float:
    """plan row 의 실효 처리 행수(rows × filtered/100). filtered 미상이면 rows 그대로."""
    r = float(pr.get("rows") or 0)
    try:
        f = float(pr.get("filtered"))
    except (TypeError, ValueError):
        return r
    return r * (f / 100.0) if 0.0 <= f <= 100.0 else r


# 조기 종료(LIMIT 상한)를 깨는 SQL 요소. 하나라도 보이면 보정하지 않는다(= 차단 유지).
# 오탐(있는데 못 봄)만 위험하므로 **넓게** 잡는다 — 미검출 쪽이 안전한 방향이 아니다.
# `sql_calc_found_rows` 는 LIMIT 이 있어도 **전체 결과 행수를 계산**하므로 조기 종료가 없다.
# `distinctrow`·`straight_join` 은 `_` 가 word char 라 `\bdistinct\b`/`\bjoin\b` 에 안 걸려 별도 명시
# (둘 다 codex P1/P1-동류 지적).
_LIMIT_CAP_BLOCKERS = re.compile(
    r"\b(where|group\s+by|having|distinct|distinctrow|union|intersect|except|order\s+by|join|"
    r"straight_join|over|window|for\s+update|lock\s+in\s+share|into|procedure|"
    r"sql_calc_found_rows|sql_big_result|sql_small_result|sql_buffer_result|sql_no_cache|"
    r"high_priority)\b",
    re.IGNORECASE,
)
# MySQL 주석: `-- …`(줄 끝) · `# …`(줄 끝) · `/* … */`. 주석 안의 `LIMIT 5` 를 실제 상한으로
# 오인하면 **LIMIT 없는 전체 스캔이 게이트를 통과**한다(codex P1, 재현 확인).
_SQL_COMMENT = re.compile(r"--[^\n]*|#[^\n]*|/\*.*?\*/", re.DOTALL)
_AGGREGATE_CALL = re.compile(
    r"\b(count|sum|avg|min|max|group_concat|std|stddev|stddev_pop|stddev_samp|"
    r"var_pop|var_samp|variance|bit_and|bit_or|bit_xor|json_arrayagg|json_objectagg)\s*\(",
    re.IGNORECASE,
)
# LIMIT 은 **문 끝**에서만 인정한다 — 문자열 리터럴 안의 'LIMIT 1'(예 `SELECT 'LIMIT 1' FROM t`)이
# 상한으로 오인되지 않게. `LIMIT n` / `LIMIT off, n` / `LIMIT n OFFSET off` 세 형태.
_TAIL_LIMIT = re.compile(r"\blimit\s+(\d+)\s*(?:,\s*(\d+)\s*)?;?\s*\Z", re.IGNORECASE)
_TAIL_LIMIT_OFFSET = re.compile(r"\blimit\s+(\d+)\s+offset\s+(\d+)\s*;?\s*\Z", re.IGNORECASE)


def _limit_scan_cap(sql: str, facts: dict) -> int | None:
    """순수 `LIMIT n` 조회의 **실제 처리 행수 상한**(=n+offset). 해당 없으면 None.

    MySQL `EXPLAIN.rows` 는 **LIMIT 을 반영하지 않는 스캔 상한**이다 — `SELECT * FROM t LIMIT 5`
    도 rows=테이블 전체로 보고된다(라이브 실측: 13,903,018). 그 값을 "예상 처리 행수"로 그대로
    쓰면 실제로 5행만 읽는 쿼리가 heavy 로 오판·차단된다.

    보정은 **조기 종료가 보장되는 형태로만** 좁힌다(부하 회귀 방지 — 아래를 모두 충족):
      1) 단일 plan row + `select_type=SIMPLE`  (조인·서브쿼리·derived·UNION 배제)
      2) SELECT 1개 + 집계호출/`_LIMIT_CAP_BLOCKERS` 부재 (WHERE·ORDER BY·GROUP BY 등 전부 배제)
      3) `Extra` 에 filesort/temporary 부재 (정렬·임시테이블은 전체를 읽어야 함)
      4) 문 끝 LIMIT 파싱 성공 — **주석 제거본 기준**
    하나라도 어긋나면 None → 기존 추정치 유지(차단). 즉 이 보정은 **오판 구간만** 되돌린다.

    **주석 처리(codex P1)**: `SELECT * FROM t -- LIMIT 5` 는 MySQL 에 LIMIT 없는 전체 스캔으로
    가는데 raw 문자열 끝에는 `LIMIT 5` 가 보인다 → 상한을 **주석 제거본에서만** 인정한다. 반대로
    주석 제거가 문자열 리터럴을 잘라 blocker(WHERE 등)를 지워버리는 반대 방향 위험이 있으므로,
    **blocker·SELECT 개수는 원본과 제거본 양쪽에서** 검사한다(둘 중 하나라도 걸리면 미적용).
    """
    raw = (sql or "").strip()
    if not raw:
        return None
    stripped = _SQL_COMMENT.sub(" ", raw)
    plan_rows = facts.get("plan_rows") or []
    if len(plan_rows) != 1:
        return None
    only = plan_rows[0]
    st = str(only.get("select_type") or "").strip().upper()
    if st and st != "SIMPLE":
        return None
    extra = str(only.get("extra") or "").lower()
    if "filesort" in extra or "temporary" in extra:
        return None
    for variant in (raw, stripped):
        # 서브쿼리/CTE 는 select 가 2회 이상 등장한다(정규식 blocker 로 못 잡는 형태 방어).
        if len(re.findall(r"\bselect\b", variant, re.IGNORECASE)) != 1:
            return None
        if re.search(r"\bwith\b", variant, re.IGNORECASE):
            return None
        if _LIMIT_CAP_BLOCKERS.search(variant) or _AGGREGATE_CALL.search(variant):
            return None
    m = _TAIL_LIMIT_OFFSET.search(stripped)
    if m:
        n, off = int(m.group(1)), int(m.group(2))
    else:
        m = _TAIL_LIMIT.search(stripped)
        if not m:
            return None
        # `LIMIT a, b` = offset a, count b / `LIMIT a` = count a
        if m.group(2) is not None:
            off, n = int(m.group(1)), int(m.group(2))
        else:
            n, off = int(m.group(1)), 0
    # `LIMIT 0` 은 offset 과 무관하게 즉시 빈 결과 — 처리 행수 0(codex P3).
    return 0 if n == 0 else n + off


# ── 역할 기반 DB 객체 조회 공통 상수·헬퍼 (feature-0040 db-object-explorer) ──────
# 열거 상한은 `search_routines` 의 51(=50+1 초과 감지) 과 같은 계열이다. **상한 도달 자체를
# 도구가 감지해 "더 있음" 을 고지**해야 하므로 표시 상한보다 1 크게 뽑는다 — 조용한 절단은
# 곧 허위 부재다(AGENTS.md §16.7 G9-b 무음 절단 금지).
_OBJ_ROWS_LIMIT = 201
# 표시 상한(도구가 잘라 보여주는 수). _OBJ_ROWS_LIMIT 보다 작아야 초과 감지가 성립한다.
OBJECT_ROWS_SHOWN = 200


def _mysql_snippet(col: str, keyword: str) -> str:
    """본문 매칭 지점의 앞뒤 문맥 조각 (MySQL) — `search_routines` 의 MATCH_SNIPPET 과 동형.

    keyword 가 비면(전체 열거) `LOCATE('', x)` 가 1 을 돌려 무의미한 머리말이 붙으므로 상수 ''.
    """
    if not keyword:
        return "'' AS MATCH_SNIPPET"
    return (
        f"CASE WHEN LOCATE('{keyword}', COALESCE({col}, '')) > 0\n"
        f"                 THEN SUBSTRING({col}, GREATEST(LOCATE('{keyword}', {col}) - 40, 1), 140)\n"
        f"                 ELSE '' END AS MATCH_SNIPPET"
    )


def _mssql_snippet(col: str, keyword: str) -> str:
    """본문 매칭 지점의 앞뒤 문맥 조각 (T-SQL). CHARINDEX 는 미발견 시 0 → CASE 로 가드."""
    if not keyword:
        return "CAST('' AS NVARCHAR(200)) AS MATCH_SNIPPET"
    return (
        f"CASE WHEN CHARINDEX('{keyword}', ISNULL({col}, '')) > 0\n"
        f"                 THEN CAST(SUBSTRING({col},\n"
        f"                      CASE WHEN CHARINDEX('{keyword}', {col}) - 40 < 1 THEN 1\n"
        f"                           ELSE CHARINDEX('{keyword}', {col}) - 40 END, 140) AS NVARCHAR(200))\n"
        f"                 ELSE CAST('' AS NVARCHAR(200)) END AS MATCH_SNIPPET"
    )


def _sql_str_list(values) -> str:
    """`'a','b'` 형태의 SQL 문자열 리터럴 목록. 빈 입력이면 매칭 불가 리터럴을 돌려준다.

    **fail-closed**: 허용 DB 목록이 비었는데 빈 `IN ()` 을 만들면 구문 오류이거나(엔진에 따라)
    필터가 사라져 전 서버 범위가 열린다. 빈 목록은 `IN ('')` 로 남겨 **아무것도 매칭되지 않게**
    한다 — 경계가 불명확할 때 넓게 여는 대신 닫는다.
    caller 가 `_safe_ident` 로 정제한 값만 넘긴다(SQLi 경계). 방어적으로 작은따옴표를 이중화한다.
    """
    out = [str(v).replace("'", "''") for v in (values or ()) if str(v or "").strip()]
    return ", ".join(f"'{v}'" for v in out) if out else "''"


class Dialect:
    name = "mysql"
    sqlglot = "mysql"
    # 사전 부하추정 지원 여부. False 엔진은 gate 모드에서 무조건 fail-closed (M-4).
    supports_load_estimate = True
    # gate 모드에서 추정 실패(None) 시 동작. False=fail-open(허용 — MySQL 골든: EXPLAIN 실패는
    # 드물고 정상 작업을 막지 않음). True=fail-closed(차단 — MSSQL: SHOWPLAN 미권한/연결 실패 시
    # 무거운 쿼리 무방어를 막는 보수적 차단, M-4).
    gate_fail_closed_on_estimate_error = False

    # ── 보안: 시스템 스키마 소유권 (P6, DESIGN §3.4 m3 / §4 "차단 스키마 정합") ──
    def system_schemas(self) -> frozenset:
        """사용자 스키마 열거에서 **제외**할 엔진 시스템 스키마 (case-insensitive, lowercase).

        `_is_user_schema`·`search_tables` 의 sys_exclude 가 사용. 누락 시 시스템 카탈로그가
        사용자 스키마로 노출된다.
        """
        raise NotImplementedError

    def metadata_schemas(self) -> frozenset:
        """Product allowlist 와 무관하게 **항상 허용**하는 카탈로그 스키마 (lowercase).

        에이전트가 구조 탐색에 필요한 카탈로그(`information_schema`/`sys` 등) 만. DB 계정 GRANT 가
        2 차 방어. `system_schemas()` 의 부분집합이어야 한다(시스템이면서 카탈로그 조회용).
        """
        raise NotImplementedError

    def system_databases(self) -> frozenset:
        """**DB 단위** 접근모델(TASK-0206)에서 시스템 데이터베이스(catalog) 집합 (lowercase).

        DB allowlist 와 무관하게 항상 catalog 로 허용(완결성). MySQL=메타DB(=system_schemas, schema==database),
        MSSQL=master/model/msdb/tempdb. **주의(M1 보존)**: 시스템 DB 가 catalog 로 허용돼도 `sys`/`guest`/`db_*`
        **스키마**는 `system_schemas()` 로 계속 차단된다 → `master.sys.sql_logins` 는 여전히 거부.
        """
        raise NotImplementedError

    # ── insight 핑거프린트: 컬럼 메타데이터 projection (P7) ──
    def fingerprint_column_projection(self) -> str:
        """insight.py 의 컬럼 핑거프린트용 SELECT projection (information_schema.COLUMNS 기준).

        FROM/WHERE(`information_schema.COLUMNS`·`TABLE_SCHEMA`·`ORDINAL_POSITION`)는 ANSI 표준이라
        MySQL·MSSQL 공통 → insight.py 가 공유하고, **엔진 고유 컬럼만 본 projection 으로 분기**한다
        (MySQL `COLUMN_TYPE`/`COLUMN_KEY` 는 SQL Server INFORMATION_SCHEMA 에 없어 `Invalid column name`).
        반환 컬럼 수는 엔진 무관 5개(코드 대칭, 첫 컬럼=COLUMN_NAME). 핑거프린트는 datasource 별 스코프라
        엔진 간 값 비교를 안 함 — 엔진 내 안정성·변경검출만 필요.
        """
        raise NotImplementedError

    # ── 식별자 인용 ──
    def quote_qualified(self, schema: str, table: str) -> str:
        raise NotImplementedError

    # ── introspection / sampling SQL ──
    # `db`(catalog) 파라미터는 MSSQL cross-DB 발견 전용 — MySQL 은 information_schema 가 인스턴스-전역이라
    # 무시(schema 인자가 곧 DB). 호출부가 dialect 무관하게 db= 를 넘길 수 있도록 시그니처만 공유한다.
    def list_schemas_with_counts(self, db: str = "") -> str:
        raise NotImplementedError

    def list_schema_names(self, db: str = "") -> str:
        raise NotImplementedError

    def describe_schema_tables(self, schema: str, db: str = "") -> str:
        raise NotImplementedError

    def describe_columns(self, schema: str, table: str, db: str = "") -> str:
        raise NotImplementedError

    def list_indexes(self, schema: str, table: str, db: str = "") -> str:
        raise NotImplementedError

    def sample(self, schema: str, table: str, limit: int, db: str = "") -> str:
        raise NotImplementedError

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str, db: str = "") -> str:
        raise NotImplementedError

    def search_routines(self, keyword: str, schema: str = "", sys_exclude_schemas: "frozenset|set|tuple" = (), db: str = "") -> str:
        """저장 루틴(PROCEDURE/FUNCTION) **열거·검색** SQL (FR-false-absence-zero-row-catalog-scope).

        `schema` 는 **원시 스키마명**(빈값=전체)이고 각 dialect 가 자기 컬럼식으로 조립한다 —
        문자열 조각(`AND t.TABLE_SCHEMA = …`)을 받아 치환하던 초기안은 caller 와의 문서화되지 않은
        결합이라 MSSQL dialect + 비활성 datasource 조합에서 잘못된 컬럼을 주입했다(§18.8 패널).
        `sys_exclude_schemas` 는 열거에서 제외할 시스템/내부 스키마(공백이면 제외 없음).
        `keyword` 가 빈 문자열이면 **필터 없이 전체 열거**(개수 파악용).

        컬럼 계약(엔진 무관, 위치 파싱): ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_TYPE, MATCH_SNIPPET.
        이름·정의 본문에 keyword 가 포함된 루틴을 찾는다(본문 검색이라 "문서 조회 프로시저" 처럼
        **이름만으로는 못 찾는** 탐색 의도를 충족). read-only 카탈로그 조회.

        `MATCH_SNIPPET`(conversation_audit 2026-07-30): 본문 매칭이 일어난 지점의 앞뒤 문맥
        조각. 종전에는 목록만 돌려줘 "왜 이 루틴이 걸렸는지" 를 알려면 매 후보마다
        `describe_routine` 을 다시 호출해야 했다 — 후보가 여러 개면 그 왕복이 탐색을 접게 만든다.
        이름만 매칭됐거나 keyword 가 없으면(전체 열거) 빈 문자열. caller 는 `len(row) > 3` 로
        방어적으로 읽는다(3-컬럼 dialect·fake row 하위호환).
        """
        raise NotImplementedError

    def safe_sys_views(self) -> frozenset:
        """freeform 에서 **읽기 허용**하는 시스템 스키마 카탈로그 뷰 (lowercase view 명).

        기본은 빈 집합(=시스템 스키마 전면 차단, 종전 동작). 엔진이 DB(catalog) 스코프임이 보장된
        구조 카탈로그 뷰만 열거해 overblock 을 푼다 — 서버 스코프 뷰(`databases`/`dm_*`/로그인·
        주체 뷰)는 **절대 포함하지 않는다**(제품 DB allowlist 를 우회하는 정보 노출 경로).
        """
        return frozenset()

    # ── 사전 부하추정 / 실행계획 (P6 부하게이트 — dialect 별 처리) ──
    def estimate_load_rows(self, run, sql: str) -> int | None:
        """사전 부하추정: 본 쿼리를 **실행하지 않고** 예상 처리 행수를 산출.

        `run(sql_str) -> result_sets` 는 caller(tools.py)가 주입하는 실행 콜백이다(dialects 가
        db/tools 를 import 하지 않도록 — 계층 보존). 추정 불가/실패 시 None → caller 가 엔진별
        fail-open/closed(`gate_fail_closed_on_estimate_error`)를 결정한다.
        """
        raise NotImplementedError

    def estimate_load(self, run, sql: str) -> "tuple[int | None, dict]":
        """`estimate_load_rows` + **차단 코칭용 실행계획 사실**을 한 번의 계획 취득으로 함께 반환.

        기본 구현은 추정치만 주고 facts 는 빈 dict(엔진이 계획 사실 파싱을 구현하지 않은 경우) —
        caller 는 facts 가 비면 기존 정적 문구로 폴백한다. 계획을 두 번 뜨지 않도록(오버헤드 0 유지)
        엔진별 override 가 EXPLAIN/SHOWPLAN 결과를 재사용한다.
        """
        return self.estimate_load_rows(run, sql), {}

    def explain_plan(self, run, sql: str):
        """explain_query 도구용 실행계획 result_sets(본 쿼리 미실행). None=미지원/실패."""
        raise NotImplementedError

    # ── get_table_indexes / get_foreign_keys 전용 SQL (P6: 두 도구 dialect 화) ──
    def table_indexes(self, schema: str, table: str, db: str = "") -> str:
        raise NotImplementedError

    def foreign_keys_outgoing(self, schema: str, table: str, db: str = "") -> str:
        raise NotImplementedError

    def foreign_keys_incoming(self, schema: str, table: str, db: str = "") -> str:
        raise NotImplementedError

    # ── describe_routine 전용 SQL (저장 프로시저/함수 정의·파라미터 introspection) ──
    # FR-show-create-routine-blocked: LLM 이 자연스럽게 쓰는 `SHOW CREATE PROCEDURE` 는 sql_guard 의
    # SELECT/CTE-only 불변식에 (의도대로) 막힌다. 정의 조회는 이미 항상-허용인 카탈로그(information_schema/
    # sys)에서 **읽기 전용**으로 얻으므로, 신뢰경계 확장 없이 전용 구조화 도구로 노출한다(RO GRANT 가 backstop).
    def routine_definition(self, schema: str, name: str, db: str = "") -> str:
        """저장 루틴(PROCEDURE/FUNCTION) 정의 조회 SQL.

        컬럼 계약(엔진 무관, 위치 파싱 호환): ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE(함수 반환타입/'')，
        ROUTINE_COMMENT, ROUTINE_DEFINITION(본문). read-only 카탈로그 조회.
        """
        raise NotImplementedError

    def routine_parameters(self, schema: str, name: str, db: str = "") -> str:
        """저장 루틴 파라미터 조회 SQL.

        컬럼 계약: ORDINAL_POSITION, PARAMETER_NAME, PARAMETER_MODE, DATA_TYPE. (position 0 = 함수 반환)
        """
        raise NotImplementedError

    # ══════════════════════════════════════════════════════════════════
    #  역할 기반 DB 객체 (feature-0040 db-object-explorer)
    # ══════════════════════════════════════════════════════════════════
    # `modules/db_object_roles.py` 의 역할 taxonomy(view/trigger/schedule/alias/generator)를
    # 각 엔진의 구체 객체로 매핑하는 계층. **신규 DBMS 를 붙일 때 손대는 유일한 곳**이며,
    # 역할 축 자체는 DBMS 수와 무관하게 고정된다.
    #
    # 컬럼 계약(엔진 무관, 위치 파싱 — 기존 도구들과 동일 관례):
    #   list_objects      → SCHEMA_NAME, OBJECT_NAME, OBJECT_TYPE, OWNER_OBJECT,
    #                       ATTR_A, ATTR_B, ATTR_C, MATCH_SNIPPET
    #   object_definition → OBJECT_NAME, OBJECT_TYPE, OWNER_OBJECT,
    #                       ATTR_A, ATTR_B, ATTR_C, PART_LABEL, DEFINITION
    # ATTR_A/B/C 의 **의미는 역할마다 다르며** `object_attr_labels(role)` 이 표제를 준다
    # (예: trigger → 시점 / 이벤트 / 활성). 위치 계약을 고정하고 표제만 역할별로 두면,
    # 도구·수집기·그래프가 역할이 늘어도 파싱 코드를 고치지 않는다.
    #
    # PART_LABEL 은 **한 객체가 여러 본문 조각으로 구성되는 역할**을 위한 것이다
    # (SQL Server Agent 작업 = 단계 N개). 조각이 없으면 ''.

    def object_support(self, role: str) -> str:
        """이 엔진에서 `role` 의 지원 상태 — SUPPORTED | UNSUPPORTED | PRIVILEGED | DELEGATED.

        **UNSUPPORTED 를 0행으로 뭉개지 않는 것이 본 API 의 존재 이유다.** MySQL 에 별칭을
        물으면 0행이 나오지만 그것은 "없다" 가 아니라 "MySQL 에 시노님 개념이 없다" 이며,
        둘을 구분하지 않으면 모델이 허위 부재를 서술한다
        (`db_object_roles` 모듈 docstring · FR-false-absence-zero-row-catalog-scope).

        `OWNED_ELSEWHERE`(현재 `routine`) 는 **여기서 일괄 DELEGATED 로 확정**한다 — 엔진별
        하위클래스에 맡기면 하나가 표에서 빠지는 순간 "이 DBMS 는 프로시저를 지원하지 않는다"
        는 거짓이 나온다. 실제로 초판이 그렇게 동작했다(하위클래스 dict 에 routine 부재 →
        기본값 UNSUPPORTED 로 낙하). 엔진이 재정의할 수 없는 자리에 두어 구조적으로 막는다.
        """
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        if r in _r.OWNED_ELSEWHERE:
            return _r.DELEGATED
        return self._object_support(r)

    def _object_support(self, role: str) -> str:
        """엔진별 지원 상태 — 하위클래스가 재정의한다(`OWNED_ELSEWHERE` 는 위에서 이미 처리)."""
        from . import db_object_roles as _r
        return _r.UNSUPPORTED

    def object_privilege_note(self, role: str) -> str:
        """PRIVILEGED 역할에 덧붙일 엔진별 구체 사유(어느 권한이 있어야 보이는가). 없으면 ''."""
        return ""

    def object_attr_labels(self, role: str) -> tuple:
        """역할별 ATTR_A/B/C 표제 3-tuple. 미사용 슬롯은 ''.

        기본값은 역할 축 공통이며, 엔진이 다른 표제를 쓰면 오버라이드한다.
        """
        from . import db_object_roles as _r
        return {
            _r.ROLE_VIEW: ("갱신가능", "CHECK 옵션", "컬럼 수"),
            _r.ROLE_TRIGGER: ("시점", "이벤트", "활성"),
            _r.ROLE_SCHEDULE: ("상태", "주기", "최근 실행"),
            _r.ROLE_ALIAS: ("대상 객체", "대상 위치", ""),
            _r.ROLE_GENERATOR: ("시작값", "증가값", "현재값"),
        }.get(_r.normalize_role(role), ("", "", ""))

    def list_objects(self, role: str, keyword: str = "", schema: str = "",
                     db: str = "", allow_dbs: "tuple|list" = (),
                     sys_exclude_schemas: "frozenset|set|tuple" = ()) -> "str|None":
        """역할별 객체 **열거·검색** SQL. 지원하지 않으면 None.

        `keyword` 는 빈 문자열이면 필터 없이 전량 열거한다(`search_routines` 와 동일 규약 —
        원 마찰의 질문이 "몇 개나 있나" 라는 열거였고, 필수로 두면 모델이 와일드카드로 우회한다).
        `allow_dbs` 는 **서버 스코프 객체**(SQL Server Agent 작업)의 제품 경계 필터용 —
        caller 가 `_safe_ident` + allowlist 검증을 마친 값만 넘긴다(SQLi/무단 catalog 차단).
        `sys_exclude_schemas` 는 **schema 미지정 전량 열거**의 시스템·내부 스키마 차단용이며
        `search_routines` 와 동일하게 **필수**다 — 누락하면 allowlist 무관 영구차단 대상인
        `agent_memory` 의 뷰·트리거까지 열거된다(search_routines 의 §18.8 BLOCKER 와 동형).
        """
        return None

    def object_definition(self, role: str, name: str, schema: str = "",
                          db: str = "", allow_dbs: "tuple|list" = ()) -> "str|None":
        """역할별 객체 **정의 본문·속성** 조회 SQL. 지원하지 않으면 None.

        한 객체가 여러 행으로 나올 수 있다(Agent 작업의 단계). 그 경우 PART_LABEL 로 구분한다.
        """
        return None


class MySQLDialect(Dialect):
    name = "mysql"
    sqlglot = "mysql"

    # 골든: tools.py `_METADATA_SCHEMAS` 와 동일 집합(시스템=메타데이터). MySQL 동작 0 변경.
    _SYS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

    def system_schemas(self) -> frozenset:
        return self._SYS

    def metadata_schemas(self) -> frozenset:
        return self._SYS

    def system_databases(self) -> frozenset:
        # MySQL: schema==database → 시스템 DB = 시스템 스키마.
        return self._SYS

    def fingerprint_column_projection(self) -> str:
        # 골든: insight.py 의 기존 컬럼 목록 그대로(COLUMN_TYPE/COLUMN_KEY 포함).
        return "COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY"

    def quote_qualified(self, schema: str, table: str) -> str:
        return f"`{schema}`.`{table}`"

    def list_schemas_with_counts(self, db: str = "") -> str:
        return """
        SELECT
            s.SCHEMA_NAME,
            COUNT(t.TABLE_NAME) AS table_count,
            COALESCE(SUM(t.TABLE_ROWS), 0) AS approx_total_rows
        FROM information_schema.SCHEMATA s
        LEFT JOIN information_schema.TABLES t
            ON s.SCHEMA_NAME = t.TABLE_SCHEMA
        GROUP BY s.SCHEMA_NAME
        ORDER BY s.SCHEMA_NAME
    """

    def list_schema_names(self, db: str = "") -> str:
        return "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"

    def describe_schema_tables(self, schema: str, db: str = "") -> str:
        return f"""
        SELECT
            TABLE_NAME,
            TABLE_ROWS AS approx_rows,
            ENGINE,
            TABLE_COMMENT,
            CREATE_TIME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = '{schema}'
        ORDER BY TABLE_NAME
    """

    def describe_columns(self, schema: str, table: str, db: str = "") -> str:
        return f"""
        SELECT
            COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
            COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION
    """

    def list_indexes(self, schema: str, table: str, db: str = "") -> str:
        return f"SHOW INDEX FROM `{schema}`.`{table}`"

    def sample(self, schema: str, table: str, limit: int, db: str = "") -> str:
        return f"SELECT * FROM `{schema}`.`{table}` LIMIT {limit}"

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str, db: str = "") -> str:
        return f"""
        SELECT DISTINCT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_ROWS AS approx_rows,
            t.TABLE_COMMENT
        FROM information_schema.TABLES t
        LEFT JOIN information_schema.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE ({sys_exclude})
            {where_schema}
            AND (
                t.TABLE_NAME LIKE '%{keyword}%'
                OR c.COLUMN_NAME LIKE '%{keyword}%'
                OR t.TABLE_COMMENT LIKE '%{keyword}%'
            )
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        LIMIT 50
    """

    def search_routines(self, keyword: str, schema: str = "", sys_exclude_schemas=(), db: str = "") -> str:
        # MySQL 의 information_schema 는 **인스턴스 전역**이라 catalog 접두가 불필요(db 인자 무시).
        # ROUTINE_DEFINITION(본문)까지 LIKE 검색 — 이름에 안 드러나는 조회 대상을 찾기 위함.
        # 시스템·내부 스키마 제외는 `search_tables` 와 대칭으로 **필수**(§18.8 BLOCKER: 누락 시
        # allowlist 무관 영구차단 대상인 agent_memory 루틴까지 열거·본문매칭됐다).
        where = ""
        if schema:
            where += f"\n            AND ROUTINE_SCHEMA = '{schema}'"
        for s in sorted(sys_exclude_schemas or ()):
            where += f"\n            AND ROUTINE_SCHEMA != '{s}'"
        if keyword:
            where += (
                f"\n            AND (\n"
                f"                ROUTINE_NAME LIKE '%{keyword}%'\n"
                f"                OR COALESCE(ROUTINE_DEFINITION, '') LIKE '%{keyword}%'\n"
                f"                OR COALESCE(ROUTINE_COMMENT, '') LIKE '%{keyword}%'\n"
                f"            )"
            )
        # MATCH_SNIPPET: 본문 매칭 지점의 앞뒤 문맥(앞 40자 ~ 총 140자). keyword 가 비면(전체 열거)
        # LOCATE('', x) 가 1 을 돌려 무의미한 머리말이 붙으므로 상수 ''.
        snippet = "'' AS MATCH_SNIPPET"
        if keyword:
            snippet = (
                f"CASE WHEN LOCATE('{keyword}', COALESCE(ROUTINE_DEFINITION, '')) > 0\n"
                f"                 THEN SUBSTRING(ROUTINE_DEFINITION,\n"
                f"                      GREATEST(LOCATE('{keyword}', ROUTINE_DEFINITION) - 40, 1), 140)\n"
                f"                 ELSE '' END AS MATCH_SNIPPET"
            )
        return f"""
        SELECT
            ROUTINE_SCHEMA,
            ROUTINE_NAME,
            ROUTINE_TYPE,
            {snippet}
        FROM information_schema.ROUTINES
        WHERE 1=1{where}
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
        LIMIT 51
    """

    def estimate_load_rows(self, run, sql: str) -> int | None:
        # 골든: EXPLAIN 실행 후 (rows × filtered/100) 곱. 실패(구문/권한/플랜불가)는 None(fail-open).
        return self.estimate_load(run, sql)[0]

    def estimate_load(self, run, sql: str) -> "tuple[int | None, dict]":
        """EXPLAIN 1회로 추정치 + 계획 사실을 함께 산출(+ 순수 LIMIT 조회 상한 보정).

        골든 대비 변경은 **오판 구간 한정 하향**뿐이다 — `_limit_scan_cap` 이 조기 종료 보장 형태로
        판정한 쿼리만 `min(est, n+offset)` 로 낮춘다(그 외 산식·값 무변경).
        """
        try:
            result_sets = run(f"EXPLAIN {sql}")
        except Exception:
            return None, {}
        est = _parse_explain_rows_product(result_sets)
        facts = _parse_explain_plan_facts(result_sets)
        if est is not None:
            cap = _limit_scan_cap(sql, facts)
            if cap is not None and cap < est:
                facts["limit_capped_from"] = est
                est = cap
        return est, facts

    def explain_plan(self, run, sql: str):
        try:
            return run(f"EXPLAIN {sql}")
        except Exception:
            return None

    def table_indexes(self, schema: str, table: str, db: str = "") -> str:
        # 골든: _tool_get_table_indexes 의 기존 SQL 그대로.
        return f"""
        SELECT
            INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX,
            CARDINALITY, INDEX_TYPE, NULLABLE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """

    def foreign_keys_outgoing(self, schema: str, table: str, db: str = "") -> str:
        return f"""
        SELECT
            CONSTRAINT_NAME, COLUMN_NAME,
            REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{table}'
            AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
    """

    def foreign_keys_incoming(self, schema: str, table: str, db: str = "") -> str:
        return f"""
        SELECT
            CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA = '{schema}'
            AND REFERENCED_TABLE_NAME = '{table}'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """

    def routine_definition(self, schema: str, name: str, db: str = "") -> str:
        # information_schema.ROUTINES — ROUTINE_DEFINITION 은 본문(BEGIN…END). DTD_IDENTIFIER 는 함수
        # 반환 타입 전체 선언(프로시저는 NULL→''). 정의 열람 권한 없으면 ROUTINE_DEFINITION NULL(도구가 안내).
        return f"""
        SELECT
            ROUTINE_NAME,
            ROUTINE_TYPE,
            COALESCE(DTD_IDENTIFIER, '') AS DATA_TYPE,
            COALESCE(ROUTINE_COMMENT, '') AS ROUTINE_COMMENT,
            COALESCE(ROUTINE_DEFINITION, '') AS ROUTINE_DEFINITION
        FROM information_schema.ROUTINES
        WHERE ROUTINE_SCHEMA = '{schema}' AND ROUTINE_NAME = '{name}'
        ORDER BY ROUTINE_TYPE
    """

    def routine_parameters(self, schema: str, name: str, db: str = "") -> str:
        # ORDINAL_POSITION=0 = 함수 반환값(PARAMETER_NAME NULL). DTD_IDENTIFIER 로 전체 타입 선언.
        # ROUTINE_TYPE(pr[4]) 은 MySQL 동명 PROCEDURE+FUNCTION 공존 시 caller 가 타입별로 파라미터를
        # 분리하기 위한 판별 컬럼(교차오염 방지). information_schema.PARAMETERS 가 제공.
        return f"""
        SELECT
            ORDINAL_POSITION,
            COALESCE(PARAMETER_NAME, '(RETURN)') AS PARAMETER_NAME,
            COALESCE(PARAMETER_MODE, '') AS PARAMETER_MODE,
            COALESCE(DTD_IDENTIFIER, '') AS DATA_TYPE,
            ROUTINE_TYPE
        FROM information_schema.PARAMETERS
        WHERE SPECIFIC_SCHEMA = '{schema}' AND SPECIFIC_NAME = '{name}'
        ORDER BY ROUTINE_TYPE, ORDINAL_POSITION
    """

    # ── 역할 기반 DB 객체 (feature-0040) ────────────────────────────────────
    # MySQL 매핑:  view→VIEW · trigger→TRIGGER · schedule→EVENT · alias/generator→없음
    #
    # **PRIVILEGED 판정 근거 (MySQL 매뉴얼)**: `information_schema.TRIGGERS` 는 그 트리거가 붙은
    # 테이블에 대한 TRIGGER 권한이, `information_schema.EVENTS` 는 그 스키마에 대한 EVENT 권한이
    # 있어야 행이 보인다. 최소권한 RO 계정(SELECT-only)에는 **오류 없이 빈 목록**이 돌아오므로,
    # 결과만으로는 "없음" 과 "안 보임" 이 구분되지 않는다 → 반드시 모호성을 고지한다(§16.7 G7-c).
    # `information_schema.VIEWS` 는 행 자체는 SELECT 권한으로 보이고 **VIEW_DEFINITION 만**
    # SHOW VIEW 권한을 요구하므로, 열거는 SUPPORTED 이고 본문 부재는 도구가 graceful 안내한다.
    def _object_support(self, role: str) -> str:
        from . import db_object_roles as _r
        return {
            _r.ROLE_VIEW: _r.SUPPORTED,
            _r.ROLE_TRIGGER: _r.PRIVILEGED,
            _r.ROLE_SCHEDULE: _r.PRIVILEGED,
            _r.ROLE_ALIAS: _r.UNSUPPORTED,       # MySQL 에 SYNONYM 없음
            _r.ROLE_GENERATOR: _r.UNSUPPORTED,   # AUTO_INCREMENT 는 컬럼 속성이지 독립 객체가 아님
        }.get(_r.normalize_role(role), _r.UNSUPPORTED)

    def object_privilege_note(self, role: str) -> str:
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        if r == _r.ROLE_TRIGGER:
            return "MySQL 은 대상 테이블의 TRIGGER 권한이 있어야 트리거가 카탈로그에 보입니다."
        if r == _r.ROLE_SCHEDULE:
            return "MySQL 은 해당 스키마의 EVENT 권한이 있어야 이벤트가 카탈로그에 보입니다."
        return ""

    def list_objects(self, role: str, keyword: str = "", schema: str = "",
                     db: str = "", allow_dbs=(), sys_exclude_schemas=()) -> "str|None":
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        # MySQL 의 information_schema 는 **인스턴스 전역**이라 catalog 접두가 불필요(db 인자 무시).
        # 스키마 절은 컬럼명이 카탈로그 뷰마다 다르므로 역할별로 조립한다. `str.format` 을 쓰지 않는
        # 이유: `_safe_ident` 는 중괄호를 제거하지 않아, 스키마명에 `{`/`}` 가 섞이면 format 이
        # KeyError/IndexError 로 죽거나 엉뚱한 치환을 한다(구조화 도구는 예외로 죽으면 안 된다).
        def sch(col: str) -> str:
            if schema:
                return f"\n            AND {col} = '{schema}'"
            # schema 미지정 = 인스턴스 전량 열거 → 시스템·내부 스키마를 **여기서** 잘라낸다.
            out = ""
            for x in sorted(sys_exclude_schemas or ()):
                out += f"\n            AND {col} != '{str(x).replace(chr(39), chr(39) * 2)}'"
            return out

        if r == _r.ROLE_VIEW:
            where = sch("TABLE_SCHEMA")
            if keyword:
                where += (f"\n            AND (TABLE_NAME LIKE '%{keyword}%'"
                          f" OR COALESCE(VIEW_DEFINITION, '') LIKE '%{keyword}%')")
            snip = _mysql_snippet("VIEW_DEFINITION", keyword)
            return f"""
        SELECT
            TABLE_SCHEMA, TABLE_NAME, 'VIEW' AS OBJECT_TYPE, '' AS OWNER_OBJECT,
            COALESCE(IS_UPDATABLE, '') AS ATTR_A,
            COALESCE(CHECK_OPTION, '') AS ATTR_B,
            '' AS ATTR_C,
            {snip}
        FROM information_schema.VIEWS
        WHERE 1=1{where}
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        LIMIT {_OBJ_ROWS_LIMIT}
    """
        if r == _r.ROLE_TRIGGER:
            where = sch("TRIGGER_SCHEMA")
            if keyword:
                where += (f"\n            AND (TRIGGER_NAME LIKE '%{keyword}%'"
                          f" OR EVENT_OBJECT_TABLE LIKE '%{keyword}%'"
                          f" OR COALESCE(ACTION_STATEMENT, '') LIKE '%{keyword}%')")
            snip = _mysql_snippet("ACTION_STATEMENT", keyword)
            # MySQL 트리거는 항상 활성(DISABLE 구문이 없다) → ATTR_C 는 상수 '활성'.
            return f"""
        SELECT
            TRIGGER_SCHEMA, TRIGGER_NAME, 'TRIGGER' AS OBJECT_TYPE,
            EVENT_OBJECT_TABLE AS OWNER_OBJECT,
            ACTION_TIMING AS ATTR_A,
            EVENT_MANIPULATION AS ATTR_B,
            '활성' AS ATTR_C,
            {snip}
        FROM information_schema.TRIGGERS
        WHERE 1=1{where}
        ORDER BY TRIGGER_SCHEMA, EVENT_OBJECT_TABLE, TRIGGER_NAME
        LIMIT {_OBJ_ROWS_LIMIT}
    """
        if r == _r.ROLE_SCHEDULE:
            where = sch("EVENT_SCHEMA")
            if keyword:
                where += (f"\n            AND (EVENT_NAME LIKE '%{keyword}%'"
                          f" OR COALESCE(EVENT_DEFINITION, '') LIKE '%{keyword}%')")
            snip = _mysql_snippet("EVENT_DEFINITION", keyword)
            # 주기(ATTR_B): RECURRING 은 `EVERY <n> <unit>`, ONE TIME 은 실행 시각.
            return f"""
        SELECT
            EVENT_SCHEMA, EVENT_NAME, 'EVENT' AS OBJECT_TYPE, '' AS OWNER_OBJECT,
            COALESCE(STATUS, '') AS ATTR_A,
            CASE WHEN EVENT_TYPE = 'RECURRING'
                 THEN CONCAT('EVERY ', COALESCE(INTERVAL_VALUE, '?'), ' ',
                             COALESCE(INTERVAL_FIELD, ''))
                 ELSE CONCAT('ONE TIME @ ', COALESCE(CAST(EXECUTE_AT AS CHAR), '?')) END AS ATTR_B,
            COALESCE(CAST(LAST_EXECUTED AS CHAR), '') AS ATTR_C,
            {snip}
        FROM information_schema.EVENTS
        WHERE 1=1{where}
        ORDER BY EVENT_SCHEMA, EVENT_NAME
        LIMIT {_OBJ_ROWS_LIMIT}
    """
        return None

    def object_definition(self, role: str, name: str, schema: str = "",
                          db: str = "", allow_dbs=()) -> "str|None":
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        # `str.format` 미사용 사유는 list_objects 의 sch() 주석 참조(중괄호 포함 스키마명 방어).
        def sch(col: str) -> str:
            return f" AND {col} = '{schema}'" if schema else ""

        if r == _r.ROLE_VIEW:
            return f"""
        SELECT
            TABLE_NAME, 'VIEW' AS OBJECT_TYPE, '' AS OWNER_OBJECT,
            COALESCE(IS_UPDATABLE, '') AS ATTR_A,
            COALESCE(CHECK_OPTION, '') AS ATTR_B,
            '' AS ATTR_C,
            '' AS PART_LABEL,
            COALESCE(VIEW_DEFINITION, '') AS DEFINITION
        FROM information_schema.VIEWS
        WHERE TABLE_NAME = '{name}'{sch('TABLE_SCHEMA')}
        ORDER BY TABLE_SCHEMA
    """
        if r == _r.ROLE_TRIGGER:
            return f"""
        SELECT
            TRIGGER_NAME, 'TRIGGER' AS OBJECT_TYPE, EVENT_OBJECT_TABLE AS OWNER_OBJECT,
            ACTION_TIMING AS ATTR_A, EVENT_MANIPULATION AS ATTR_B, '활성' AS ATTR_C,
            '' AS PART_LABEL,
            COALESCE(ACTION_STATEMENT, '') AS DEFINITION
        FROM information_schema.TRIGGERS
        WHERE TRIGGER_NAME = '{name}'{sch('TRIGGER_SCHEMA')}
        ORDER BY TRIGGER_SCHEMA
    """
        if r == _r.ROLE_SCHEDULE:
            return f"""
        SELECT
            EVENT_NAME, 'EVENT' AS OBJECT_TYPE, '' AS OWNER_OBJECT,
            COALESCE(STATUS, '') AS ATTR_A,
            CASE WHEN EVENT_TYPE = 'RECURRING'
                 THEN CONCAT('EVERY ', COALESCE(INTERVAL_VALUE, '?'), ' ',
                             COALESCE(INTERVAL_FIELD, ''))
                 ELSE CONCAT('ONE TIME @ ', COALESCE(CAST(EXECUTE_AT AS CHAR), '?')) END AS ATTR_B,
            COALESCE(CAST(LAST_EXECUTED AS CHAR), '') AS ATTR_C,
            '' AS PART_LABEL,
            COALESCE(EVENT_DEFINITION, '') AS DEFINITION
        FROM information_schema.EVENTS
        WHERE EVENT_NAME = '{name}'{sch('EVENT_SCHEMA')}
        ORDER BY EVENT_SCHEMA
    """
        return None

    def probe_relationship_overlap(self, src_schema, src_table, src_col,
                                   tgt_schema, tgt_table, tgt_col, sample, timeout_ms=0):
        """암묵 관계 검증(feature-0016): src 컬럼 표본이 tgt 컬럼에 존재하는 비율.

        반환 SQL 결과 = (sampled, matched) 1행. read-only. 식별자는 백틱 이스케이프(DB-sourced).
        timeout_ms>0 이면 `MAX_EXECUTION_TIME` 옵티마이저 힌트로 statement 시간 상한(운영 DB 폭주 차단).
        """
        def q(x):
            return "`" + str(x).replace("`", "``") + "`"
        n = max(1, min(int(sample), 200))
        src = f"{q(src_schema)}.{q(src_table)}" if src_schema else q(src_table)
        tgt = f"{q(tgt_schema)}.{q(tgt_table)}" if tgt_schema else q(tgt_table)
        hint = f"/*+ MAX_EXECUTION_TIME({int(timeout_ms)}) */ " if int(timeout_ms or 0) > 0 else ""
        return (
            f"SELECT {hint}COUNT(*) AS sampled, "
            f"SUM(CASE WHEN EXISTS (SELECT 1 FROM {tgt} t WHERE t.{q(tgt_col)} = s.v) "
            f"THEN 1 ELSE 0 END) AS matched "
            f"FROM (SELECT {q(src_col)} AS v FROM {src} "
            f"WHERE {q(src_col)} IS NOT NULL LIMIT {n}) s"
        )


class MSSQLDialect(Dialect):
    """MSSQL(T-SQL). 동일 컬럼 순서로 tools.py 결과 파싱(row[i]) 호환.

    식별자 인용 `[schema].[table]`. INFORMATION_SCHEMA 는 SQL Server 도 제공하나 일부 컬럼
    의미가 달라 컬럼 별칭/순서를 MySQL 산출과 동일하게 맞춘다. 행수 추정은 **sys.partitions.rows**
    (P6: 최소권한 RO 가 metadata-visibility 로 접근 — sys.dm_db_partition_stats DMV 는 VIEW DATABASE
    STATE 권한이 필요해 db_datareader 금지/스키마 GRANT-only RO 에서 거부됨).

    **사전 부하추정 (TASK-0299)**: EXPLAIN 구문은 없으나 `SET SHOWPLAN_ALL ON` 으로 본 쿼리를
    실행하지 않고 추정 실행계획을 받아 예상 처리 행수를 산출한다(MySQL EXPLAIN 등가). RO role 에
    `GRANT SHOWPLAN` 필요(데이터 읽기 권한 아님 — 최소권한과 양립; bin/datasource-mssql-ro-bootstrap*.sql).
    SHOWPLAN 미권한/연결 실패 시 추정 불가 → gate 모드 fail-closed(`gate_fail_closed_on_estimate_error`).
    """
    name = "mssql"
    sqlglot = "tsql"
    # SET SHOWPLAN_ALL 로 사전 부하추정 지원(TASK-0299). 추정 실패 시 gate 모드 fail-closed.
    supports_load_estimate = True
    gate_fail_closed_on_estimate_error = True

    # 사용자 스키마 열거에서 제외: sys/INFORMATION_SCHEMA(카탈로그) + guest + 고정 db_* 역할 스키마.
    # **dbo 는 제외하지 않는다** — MSSQL 의 기본 사용자 스키마(대부분의 사용자 테이블 거처)라
    # 제외하면 정상 테이블이 통째로 차단된다.
    _SYS = frozenset({
        "sys", "information_schema", "guest",
        "db_owner", "db_accessadmin", "db_securityadmin", "db_ddladmin",
        "db_backupoperator", "db_datareader", "db_datawriter",
        "db_denydatareader", "db_denydatawriter",
    })
    # 항상 허용(LLM freeform execute_sql 의 카탈로그 조회)은 **INFORMATION_SCHEMA 만**.
    # **`sys` 는 항상-허용에서 제외** (REV-0201 M1): MSSQL `sys` 카탈로그 뷰는 metadata-visibility 라
    # GRANT 로 막히지 않아, 최소권한 RO 도 `sys.sql_logins`(로그인 enumeration)·`sys.server_principals`·
    # `sys.database_principals`·`sys.tables`(allowlist 밖 스키마 인벤토리) 를 freeform 으로 읽을 수 있다
    # (라이브 실증 — 설계가 믿은 "GRANT backstop" 이 sys 영역엔 부재). 구조 탐색은 list_schemas/
    # describe_* 구조화 도구(내부적으로 sys.* 를 쓰되 결과를 allowlist 로 필터)가 담당하므로, freeform
    # 의 sys.* 직접 조회는 차단해도 기능 손실이 없다. db_* 역할 스키마도 metadata 아님.
    _META = frozenset({"information_schema"})

    # RC-B: freeform 읽기 허용 `sys` 카탈로그 뷰 — **DB(catalog) 스코프 구조 뷰만**.
    # 서버 스코프(databases/dm_*/로그인·주체/구성) 는 의도적 제외(safe_sys_views docstring 참조).
    _SAFE_SYS_VIEWS = frozenset({
        "objects", "procedures", "tables", "views", "columns", "schemas",
        "sql_modules", "parameters", "types", "indexes", "index_columns",
        "foreign_keys", "foreign_key_columns", "key_constraints",
        "check_constraints", "default_constraints", "triggers",
        # `synonyms` 의도적 제외(§18.8 MINOR): base_object_name 이 allowlist 밖 DB·linked server 명을
        # 그대로 노출해 "DB 스코프만 기술" 안전 논거의 반례이고, RC-A 에 불필요(최소범위 원칙).
        "sequences", "identity_columns", "computed_columns", "extended_properties",
        # 행수 관용구(`SUM(p.rows) FROM sys.partitions p WHERE p.index_id < 2`)·의존성 분석은
        # "몇 건인가" 라는 원 질문 유형의 정본 경로다. 넷 다 현재 DB 범위만 기술(§18.8 2R MINOR).
        "partitions", "allocation_units", "stats", "sql_expression_dependencies",
    })

    # MSSQL 시스템 데이터베이스(catalog 차원). DB allowlist 무관 항상 catalog 허용(완결성). 단 그 안의
    # `sys`/`guest`/`db_*` 스키마는 `_SYS`(system_schemas)로 계속 차단 → master.sys.sql_logins 거부(M1 보존).
    _SYS_DB = frozenset({"master", "model", "msdb", "tempdb"})

    def system_schemas(self) -> frozenset:
        return self._SYS

    def metadata_schemas(self) -> frozenset:
        return self._META

    def system_databases(self) -> frozenset:
        return self._SYS_DB

    def fingerprint_column_projection(self) -> str:
        # MSSQL INFORMATION_SCHEMA.COLUMNS 에는 COLUMN_TYPE/COLUMN_KEY 가 없다 → DATA_TYPE +
        # CHARACTER_MAXIMUM_LENGTH 로 타입 상세를 대체하고, KEY 자리는 상수(핑거프린트는 컬럼 추가/삭제/
        # 타입변경 검출이 주목적이라 PK 표식 생략 무해). 컬럼 수 5개로 MySQL 과 대칭(insight 가 위치로 읽음).
        return (
            "COLUMN_NAME, DATA_TYPE, "
            "CAST(ISNULL(CHARACTER_MAXIMUM_LENGTH, -1) AS NVARCHAR(20)) AS COLUMN_TYPE, "
            "IS_NULLABLE, CAST('' AS NVARCHAR(1)) AS COLUMN_KEY"
        )

    def quote_qualified(self, schema: str, table: str) -> str:
        return f"[{schema}].[{table}]"

    @staticmethod
    def _cat(db: str) -> str:
        """catalog(DB) 3-part 접두 `[db].` — 빈값이면 현재 연결(pin) DB(접두 없음).

        **cross-DB 발견(FR-mssql-crossdb-structured-discovery)**: SQL Server 의 INFORMATION_SCHEMA/
        sys 카탈로그 뷰는 **DB(catalog)별**이라(MySQL 의 인스턴스-전역 information_schema 와 비대칭),
        구조화 발견 도구가 pin 된 primary DB 하나만 봤다 → 다른 허용 DB 의 객체를 "없음"으로 오판.
        `[db].` 접두로 같은 연결에서 다른 허용 DB 의 카탈로그를 읽는다(freeform 3-part 가 이미 도달하는
        범위와 동일 — 보안 경계 불변, RO GRANT 가 backstop). ADR/probe_relationship_overlap 의
        `[db].[dbo].[table]` cross-DB 규약과 정합. `db` 는 **caller 가 _safe_ident + allowlist 검증한 값만**
        전달(SQLi/무단 catalog 차단 — `[{db}]` 삽입 전 신뢰경계 필수)."""
        d = str(db or "").strip()
        return f"[{d}]." if d else ""

    def list_schemas_with_counts(self, db: str = "") -> str:
        # 컬럼 순서: schema_name, table_count, approx_total_rows (MySQL 과 동일)
        c = self._cat(db)
        return f"""
        SELECT
            s.name AS SCHEMA_NAME,
            COUNT(t.object_id) AS table_count,
            COALESCE(SUM(CAST(p.rows AS BIGINT)), 0) AS approx_total_rows
        FROM {c}sys.schemas s
        LEFT JOIN {c}sys.tables t ON t.schema_id = s.schema_id
        LEFT JOIN {c}sys.partitions p
            ON p.object_id = t.object_id AND p.index_id IN (0, 1)
        GROUP BY s.name
        ORDER BY s.name
    """

    def list_schema_names(self, db: str = "") -> str:
        return f"SELECT name AS SCHEMA_NAME FROM {self._cat(db)}sys.schemas ORDER BY name"

    def describe_schema_tables(self, schema: str, db: str = "") -> str:
        # 컬럼: table_name, approx_rows, engine, comment, create_time (MySQL 순서)
        # schema 가 비면(catalog 전체 나열 — cross-DB DB 단위 describe) 시스템 스키마만 제외하고 전체 사용자
        # 테이블을 반환한다. schema 지정 시 그 스키마로 한정(기존 동작).
        c = self._cat(db)
        if str(schema or "").strip():
            _where = f"s.name = '{schema}'"
        else:
            _sys = ", ".join(f"'{s}'" for s in sorted(self._SYS))
            _where = f"s.name NOT IN ({_sys})"
        return f"""
        SELECT
            t.name AS TABLE_NAME,
            COALESCE(SUM(CAST(p.rows AS BIGINT)), 0) AS approx_rows,
            'mssql' AS ENGINE,
            CAST(ep.value AS NVARCHAR(200)) AS TABLE_COMMENT,
            t.create_date AS CREATE_TIME
        FROM {c}sys.tables t
        JOIN {c}sys.schemas s ON s.schema_id = t.schema_id
        LEFT JOIN {c}sys.partitions p
            ON p.object_id = t.object_id AND p.index_id IN (0, 1)
        LEFT JOIN {c}sys.extended_properties ep
            ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
        WHERE {_where}
        GROUP BY t.name, t.create_date, CAST(ep.value AS NVARCHAR(200))
        ORDER BY t.name
    """

    def describe_columns(self, schema: str, table: str, db: str = "") -> str:
        # 컬럼: COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        # MSSQL 에 COLUMN_KEY/EXTRA/COMMENT 직접 동치 없음 → 가용 정보만, 나머지 빈 문자열(순서 유지).
        # schema 가 비면(catalog 타깃·실 스키마 미상) 테이블명만으로 조회(DB 내 어느 사용자 스키마든 매칭).
        c = self._cat(db)
        _schema_clause = f"c.TABLE_SCHEMA = '{schema}' AND " if str(schema or "").strip() else ""
        return f"""
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE + COALESCE('(' + CAST(c.CHARACTER_MAXIMUM_LENGTH AS NVARCHAR(20)) + ')', '') AS COLUMN_TYPE,
            c.IS_NULLABLE,
            '' AS COLUMN_KEY,
            CAST(c.COLUMN_DEFAULT AS NVARCHAR(200)) AS COLUMN_DEFAULT,
            '' AS EXTRA,
            '' AS COLUMN_COMMENT
        FROM {c}INFORMATION_SCHEMA.COLUMNS c
        WHERE {_schema_clause}c.TABLE_NAME = '{table}'
        ORDER BY c.ORDINAL_POSITION
    """

    def list_indexes(self, schema: str, table: str, db: str = "") -> str:
        # SHOW INDEX 가 소비하는 위치(row[1]=non_unique, [2]=key_name, [3]=seq, [4]=column, [6]=cardinality)
        # 에 맞춰 7 컬럼을 정렬: (NULL, non_unique, index_name, seq, column, NULL, NULL).
        c = self._cat(db)
        return f"""
        SELECT
            NULL AS Table_,
            CASE WHEN i.is_unique = 1 THEN 0 ELSE 1 END AS Non_unique,
            i.name AS Key_name,
            ic.key_ordinal AS Seq_in_index,
            col.name AS Column_name,
            NULL AS Collation,
            NULL AS Cardinality
        FROM {c}sys.indexes i
        JOIN {c}sys.tables t ON t.object_id = i.object_id
        JOIN {c}sys.schemas s ON s.schema_id = t.schema_id
        JOIN {c}sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN {c}sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
        WHERE s.name = '{schema}' AND t.name = '{table}' AND i.type > 0
        ORDER BY i.name, ic.key_ordinal
    """

    def sample(self, schema: str, table: str, limit: int, db: str = "") -> str:
        # catalog(db) 지정 시 3-part `[db].[schema].[table]`(cross-DB 표본). db 미지정=현재 연결 DB.
        d = str(db or "").strip()
        qual = f"[{d}].[{schema}].[{table}]" if d else f"[{schema}].[{table}]"
        return f"SELECT TOP {int(limit)} * FROM {qual}"

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str, db: str = "") -> str:
        # sys_exclude/where_schema 는 MySQL 의 `t.TABLE_SCHEMA` 별칭 기준 문자열이라 그대로 호환
        # (INFORMATION_SCHEMA.TABLES 의 TABLE_SCHEMA 컬럼 동일). TOP 50 으로 LIMIT 대체.
        # db 지정 시 그 catalog(DB)의 INFORMATION_SCHEMA 를 3-part 로 조회(cross-DB 발견). tools.py 가
        # catalog 별로 호출해 결과를 병합(DB-qualified). db 미지정=현재 연결 DB(기존 동작).
        c = self._cat(db)
        return f"""
        SELECT DISTINCT TOP 50
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            CAST(NULL AS BIGINT) AS approx_rows,
            CAST('' AS NVARCHAR(200)) AS TABLE_COMMENT
        FROM {c}INFORMATION_SCHEMA.TABLES t
        LEFT JOIN {c}INFORMATION_SCHEMA.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE ({sys_exclude})
            {where_schema}
            AND (
                t.TABLE_NAME LIKE '%{keyword}%'
                OR c.COLUMN_NAME LIKE '%{keyword}%'
            )
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
    """

    def search_routines(self, keyword: str, schema: str = "", sys_exclude_schemas=(), db: str = "") -> str:
        # SQL Server 의 카탈로그는 **DB(catalog)별** — `[db].` 접두로 다른 허용 DB 를 훑는다
        # (search_tables 와 동일 패턴, FR-mssql-crossdb-structured-discovery 계보).
        # 본문은 INFORMATION_SCHEMA.ROUTINE_DEFINITION(4000자 절단) 대신 **sys.sql_modules.definition**
        # (nvarchar(max))로 검색해야 4000자 뒤에 있는 참조 테이블도 잡힌다.
        # 타입 필터(§18.8 패널 MAJOR): P/FN/IF/TF 만 보면 CLR(PC/FS/FT/AF)·확장(X)·복제필터(RF)
        # 루틴이 통째로 빠져 **부재 방지 도구 안에 새 허위 부재**가 생긴다(그 루틴들은
        # INFORMATION_SCHEMA.ROUTINES·describe_routine 으로는 보인다). CASE 도 함께 넓혀 오분류 방지.
        # TOP 51 = 상한 50 + **포화 감지용 1건**(caller 가 절단을 명시 고지).
        c = self._cat(db)
        where = ""
        if schema:
            where += f"\n            AND SCHEMA_NAME(o.schema_id) = '{schema}'"
        for s_ in sorted(sys_exclude_schemas or ()):
            where += f"\n            AND SCHEMA_NAME(o.schema_id) != '{s_}'"
        if keyword:
            where += (
                f"\n            AND (\n"
                f"                o.name LIKE '%{keyword}%'\n"
                f"                OR COALESCE(m.definition, '') LIKE '%{keyword}%'\n"
                f"            )"
            )
        # MATCH_SNIPPET: MySQL 판과 동일 계약 — 본문 매칭 지점의 앞뒤 문맥(앞 40자 ~ 총 140자).
        # keyword 가 비면(전체 열거) CHARINDEX('', x) 가 1 이라 무의미하므로 상수 ''.
        snippet = "'' AS MATCH_SNIPPET"
        if keyword:
            _ci = f"CHARINDEX('{keyword}', COALESCE(m.definition, ''))"
            snippet = (
                f"CASE WHEN {_ci} > 0\n"
                f"                 THEN SUBSTRING(m.definition,\n"
                f"                      CASE WHEN {_ci} > 40 THEN {_ci} - 40 ELSE 1 END, 140)\n"
                f"                 ELSE '' END AS MATCH_SNIPPET"
            )
        return f"""
        SELECT TOP 51
            SCHEMA_NAME(o.schema_id) AS ROUTINE_SCHEMA,
            o.name AS ROUTINE_NAME,
            CASE WHEN o.type IN ('P', 'PC', 'X', 'RF') THEN 'PROCEDURE' ELSE 'FUNCTION' END AS ROUTINE_TYPE,
            {snippet}
        FROM {c}sys.objects o
        LEFT JOIN {c}sys.sql_modules m ON m.object_id = o.object_id
        WHERE o.type IN ('P', 'PC', 'X', 'RF', 'FN', 'IF', 'TF', 'FS', 'FT', 'AF'){where}
        ORDER BY SCHEMA_NAME(o.schema_id), o.name
    """

    def safe_sys_views(self) -> frozenset:
        """freeform 에서 읽기 허용하는 **DB 스코프** `sys` 카탈로그 뷰.

        RC-B(FR-false-absence-zero-row-catalog-scope): `sys` 스키마 전면 차단이 SQL Server 의 정본
        구조 탐색 경로를 닫아, 모델을 "2-part INFORMATION_SCHEMA + 다른 카탈로그 필터"(구조적 항상
        0행)로 몰았다. 여기 열거된 뷰는 **현재 DB 범위만 기술**하므로, 이미 선행하는 catalog(DB)
        allowlist 검사와 결합하면 제품 경계를 넘지 않는다.

        **의도적 제외(서버 스코프 = allowlist 우회 노출)**: `databases`·`master_files`·`dm_*`(DMV)·
        `server_principals`·`sql_logins`·`syslogins`·`credentials`·`configurations`·`endpoints`·
        `availability_*` 등. 화이트리스트 방식이라 신규 서버 스코프 뷰가 생겨도 자동 차단된다.
        **메타데이터 함수는 계속 차단**(`OBJECT_ID`/`OBJECT_DEFINITION`/`DB_NAME` …) — 인자가 문자열
        리터럴이라 AST catalog 게이트가 볼 수 없어 `OBJECT_DEFINITION(OBJECT_ID('master.dbo.x'))`
        같은 우회가 성립한다.
        """
        return self._SAFE_SYS_VIEWS

    def _showplan(self, run, sql: str):
        """`SET SHOWPLAN_ALL ON` → sql(미실행, 추정 실행계획 반환) → `OFF`. result_sets | None.

        **단일 result-set 의존 (REV-20260617-0310 m1)**: SHOWPLAN_ALL 은 본 SELECT 에 대해 operator
        당 1행을 가진 *단일* result set 을 반환하므로, `nextset()` 미호출(db.execute_sql)인 현 수집기와
        호환된다. 다른 result-set 형태가 오면 estimaterows 컬럼 부재로 None(추정 실패 → MSSQL gate
        fail-closed=안전 방향). sql_guard 가 단일 SELECT/CTE 만 허용해 다중 result-set SQL 은 도달 불가.

        **세션 poison 방지 (Codex-7, DESIGN §"pool 세션누출")**: conn 은 run 전체 공유라 SHOWPLAN_ALL
        이 켜진 채 남으면 *이후 실쿼리가 데이터 대신 plan 을 반환하는 조용한 오염*이 된다. ON 이 성공한
        경우 OFF 를 `finally` 로 항상 보장한다(조회가 예외로 끝나도 복구). OFF 자체가 실패하면 conn 이
        끊긴 것 — 이후 실쿼리도 loud 하게 실패하므로 silent plan-as-data 는 발생하지 않는다.
        ON 실패(SHOWPLAN 미권한 등)·조회 실패 시 None(추정 불가).
        """
        showplan_on = False
        try:
            run("SET SHOWPLAN_ALL ON")
            showplan_on = True
            return run(sql)
        except Exception:
            return None
        finally:
            if showplan_on:
                try:
                    run("SET SHOWPLAN_ALL OFF")
                except Exception:
                    # conn 세션 복구 실패(끊긴 conn 추정). 이후 실쿼리가 loud 실패 → silent 오염 없음.
                    pass

    def estimate_load_rows(self, run, sql: str) -> int | None:
        result_sets = self._showplan(run, sql)
        if result_sets is None:
            return None
        return _parse_showplan_estimate(result_sets)

    def explain_plan(self, run, sql: str):
        return self._showplan(run, sql)

    def table_indexes(self, schema: str, table: str, db: str = "") -> str:
        # 컬럼 순서/이름을 MySQL 산출과 동일하게(INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX,
        # CARDINALITY, INDEX_TYPE, NULLABLE). CARDINALITY 직접 동치 없음 → NULL.
        c = self._cat(db)
        return f"""
        SELECT
            i.name AS INDEX_NAME,
            CASE WHEN i.is_unique = 1 THEN 0 ELSE 1 END AS NON_UNIQUE,
            col.name AS COLUMN_NAME,
            ic.key_ordinal AS SEQ_IN_INDEX,
            CAST(NULL AS BIGINT) AS CARDINALITY,
            i.type_desc AS INDEX_TYPE,
            CASE WHEN col.is_nullable = 1 THEN 'YES' ELSE 'NO' END AS NULLABLE
        FROM {c}sys.indexes i
        JOIN {c}sys.tables t ON t.object_id = i.object_id
        JOIN {c}sys.schemas s ON s.schema_id = t.schema_id
        JOIN {c}sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN {c}sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
        WHERE s.name = '{schema}' AND t.name = '{table}' AND i.type > 0
        ORDER BY i.name, ic.key_ordinal
    """

    def foreign_keys_outgoing(self, schema: str, table: str, db: str = "") -> str:
        # 컬럼: CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        c = self._cat(db)
        return f"""
        SELECT
            fk.name AS CONSTRAINT_NAME,
            pc.name AS COLUMN_NAME,
            rs.name AS REFERENCED_TABLE_SCHEMA,
            rt.name AS REFERENCED_TABLE_NAME,
            rc.name AS REFERENCED_COLUMN_NAME
        FROM {c}sys.foreign_keys fk
        JOIN {c}sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN {c}sys.tables pt ON pt.object_id = fk.parent_object_id
        JOIN {c}sys.schemas ps ON ps.schema_id = pt.schema_id
        JOIN {c}sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        JOIN {c}sys.tables rt ON rt.object_id = fk.referenced_object_id
        JOIN {c}sys.schemas rs ON rs.schema_id = rt.schema_id
        JOIN {c}sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        WHERE ps.name = '{schema}' AND pt.name = '{table}'
        ORDER BY fk.name, fkc.constraint_column_id
    """

    def foreign_keys_incoming(self, schema: str, table: str, db: str = "") -> str:
        # 컬럼: CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, REFERENCED_COLUMN_NAME
        c = self._cat(db)
        return f"""
        SELECT
            fk.name AS CONSTRAINT_NAME,
            ps.name AS TABLE_SCHEMA,
            pt.name AS TABLE_NAME,
            pc.name AS COLUMN_NAME,
            rc.name AS REFERENCED_COLUMN_NAME
        FROM {c}sys.foreign_keys fk
        JOIN {c}sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN {c}sys.tables pt ON pt.object_id = fk.parent_object_id
        JOIN {c}sys.schemas ps ON ps.schema_id = pt.schema_id
        JOIN {c}sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        JOIN {c}sys.tables rt ON rt.object_id = fk.referenced_object_id
        JOIN {c}sys.schemas rs ON rs.schema_id = rt.schema_id
        JOIN {c}sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        WHERE rs.name = '{schema}' AND rt.name = '{table}'
        ORDER BY ps.name, pt.name
    """

    def routine_definition(self, schema: str, name: str, db: str = "") -> str:
        # 컬럼 순서를 MySQL 산출과 동일하게(ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE, ROUTINE_COMMENT,
        # ROUTINE_DEFINITION). MSSQL INFORMATION_SCHEMA.ROUTINES.ROUTINE_DEFINITION 은 4000자 절단이라
        # 전체 정의(nvarchar(max))를 우선 사용, 폴백으로 ROUTINE_DEFINITION. COMMENT 동치 없음→''.
        # 정의 소스(REV 패널 backend MAJOR): `OBJECT_DEFINITION(id)` 은 db_id 인자가 없어 **current(pin) DB
        # 컨텍스트**에서 평가된다 → cross-DB 에서 3-part OBJECT_ID 가 대상 DB 의 object_id 를 줘도 정의는
        # pin DB 에서 해소돼 NULL(→ 4000자 절단 폴백) 또는 오답이 된다. 따라서 **`[db].sys.sql_modules`**
        # (object_id 도 같은 [db] 공간에서 해소)에서 definition 을 읽어 cross-DB 정확성을 확보한다.
        # schema 가 비면(catalog 타깃·실스키마 미상) ROUTINE_SCHEMA 필터를 생략(이름으로 매칭).
        c = self._cat(db)
        d = str(db or "").strip()
        if d:
            # cross-DB: 대상 DB 의 sys.sql_modules(object_id 도 [db] 공간) 로 전체 정의 조회.
            _def_expr = (
                f"(SELECT sm.definition FROM {c}sys.sql_modules sm "
                f"WHERE sm.object_id = OBJECT_ID('[{d}].' + QUOTENAME(r.ROUTINE_SCHEMA) + '.' + QUOTENAME(r.ROUTINE_NAME)))"
            )
        else:
            # primary(현재 DB): 기존 골든 — OBJECT_DEFINITION(전체 nvarchar(max)).
            _def_expr = "OBJECT_DEFINITION(OBJECT_ID(QUOTENAME(r.ROUTINE_SCHEMA) + '.' + QUOTENAME(r.ROUTINE_NAME)))"
        _schema_clause = f"r.ROUTINE_SCHEMA = '{schema}' AND " if str(schema or "").strip() else ""
        return f"""
        SELECT
            r.ROUTINE_NAME,
            r.ROUTINE_TYPE,
            COALESCE(r.DATA_TYPE, '') AS DATA_TYPE,
            '' AS ROUTINE_COMMENT,
            COALESCE(
                {_def_expr},
                CAST(r.ROUTINE_DEFINITION AS NVARCHAR(MAX)),
                ''
            ) AS ROUTINE_DEFINITION
        FROM {c}INFORMATION_SCHEMA.ROUTINES r
        WHERE {_schema_clause}r.ROUTINE_NAME = '{name}'
        ORDER BY r.ROUTINE_TYPE
    """

    def routine_parameters(self, schema: str, name: str, db: str = "") -> str:
        # 컬럼: ORDINAL_POSITION, PARAMETER_NAME, PARAMETER_MODE, DATA_TYPE, ROUTINE_TYPE (MySQL 순서).
        # MSSQL 은 스키마 내 객체명이 유일해 동명 proc+func 공존이 없다(교차오염 무관) → ROUTINE_TYPE(pr[4])
        # 슬롯은 컬럼 계약 대칭을 위해 NULL 상수로 채운다(caller 는 def_rows 다중일 때만 이 컬럼으로 필터).
        c = self._cat(db)
        _schema_clause = f"SPECIFIC_SCHEMA = '{schema}' AND " if str(schema or "").strip() else ""
        return f"""
        SELECT
            ORDINAL_POSITION,
            COALESCE(PARAMETER_NAME, '(RETURN)') AS PARAMETER_NAME,
            COALESCE(PARAMETER_MODE, '') AS PARAMETER_MODE,
            COALESCE(DATA_TYPE, '') AS DATA_TYPE,
            CAST(NULL AS NVARCHAR(20)) AS ROUTINE_TYPE
        FROM {c}INFORMATION_SCHEMA.PARAMETERS
        WHERE {_schema_clause}SPECIFIC_NAME = '{name}'
        ORDER BY ORDINAL_POSITION
    """

    # ── 역할 기반 DB 객체 (feature-0040) ────────────────────────────────────
    # SQL Server 매핑:
    #   view→VIEW · trigger→DML/DDL TRIGGER · schedule→**SQL Server Agent 작업**
    #   alias→SYNONYM · generator→SEQUENCE
    #
    # **schedule(Agent 작업)의 두 가지 비대칭** — 다른 역할과 달리 특별 취급이 필요하다:
    #  (1) **저장 위치가 DB 밖**: 작업은 `msdb` 에 있고 서버 스코프다. 그런데 `msdb` 는
    #      `system_databases()` 소속이라 freeform 에서 하드 차단된 DB 다. 본 경로는 **코드가
    #      고정한 컬럼 투영 + 허용 DB 필터**로만 msdb 를 읽는다(구조화 도구 전용 — freeform 의
    #      msdb 차단은 그대로다). 임의 msdb 조회로 확장될 여지를 남기지 않기 위해, 여기서
    #      생성되는 SQL 은 `sysjobs`/`sysjobsteps`/`sysjobschedules`/`sysschedules` 4개 뷰의
    #      **고정 조인**이며 사용자 입력은 `name`/`keyword`/`allow_dbs` 뿐이다(전부 caller 가
    #      `_safe_ident` 정제).
    #  (2) **제품 경계 귀속**: 작업 자체엔 소속 DB 가 없고 **단계(step)의 `database_name`** 이
    #      대상 DB 다. 따라서 허용 DB 를 대상으로 하는 단계가 하나라도 있는 작업만 노출하고,
    #      SCHEMA_NAME 슬롯에 그 DB 명을 넣는다(MSSQL store-slot=DB명 규약 ADR-007 과 정합).
    #      `database_name` 이 빈 단계(CmdExec/PowerShell 등 OS 레벨)는 어느 허용 DB 와도
    #      매칭되지 않아 **자동 제외**된다 — fail-closed 이며, 그 사실을 도구가 caveat 으로 고지한다.
    #
    # **PRIVILEGED 판정 근거**: `msdb.dbo.sysjobs` 는 sysadmin 이 아니면 **자기가 소유한 작업만**
    # 반환한다(SQLAgentUserRole). RO 계정의 빈 결과는 "작업 없음" 을 뜻하지 않는다 → 모호성 고지.
    def _object_support(self, role: str) -> str:
        from . import db_object_roles as _r
        return {
            _r.ROLE_VIEW: _r.SUPPORTED,
            _r.ROLE_TRIGGER: _r.SUPPORTED,
            _r.ROLE_SCHEDULE: _r.PRIVILEGED,
            _r.ROLE_ALIAS: _r.SUPPORTED,
            _r.ROLE_GENERATOR: _r.SUPPORTED,
        }.get(_r.normalize_role(role), _r.UNSUPPORTED)

    def object_privilege_note(self, role: str) -> str:
        from . import db_object_roles as _r
        if _r.normalize_role(role) == _r.ROLE_SCHEDULE:
            return ("SQL Server Agent 작업은 sysadmin 이 아니면 **자기가 소유한 작업만** 보입니다"
                    "(SQLAgentUserRole). 또한 대상 DB 가 지정되지 않은 단계(CmdExec/PowerShell 등 "
                    "OS 레벨 작업)는 제품 경계 밖이라 목록에서 제외됩니다.")
        return ""

    def object_attr_labels(self, role: str) -> tuple:
        from . import db_object_roles as _r
        if _r.normalize_role(role) == _r.ROLE_GENERATOR:
            # MSSQL SEQUENCE 는 현재값 대신 last_used_value(아직 미사용이면 NULL)를 제공한다 —
            # '현재값' 이라 부르면 NULL 을 0 으로 오독하므로 표제를 정확히 둔다(§16.7 G7).
            return ("시작값", "증가값", "마지막 사용값")
        return super().object_attr_labels(role)

    def list_objects(self, role: str, keyword: str = "", schema: str = "",
                     db: str = "", allow_dbs=(), sys_exclude_schemas=()) -> "str|None":
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        c = self._cat(db)
        sch = f"\n            AND s.name = '{schema}'" if schema else ""
        if r == _r.ROLE_VIEW:
            kw = ""
            if keyword:
                kw = (f"\n            AND (v.name LIKE '%{keyword}%'"
                      f" OR ISNULL(m.definition, '') LIKE '%{keyword}%')")
            snip = _mssql_snippet("m.definition", keyword)
            return f"""
        SELECT TOP {_OBJ_ROWS_LIMIT}
            s.name AS SCHEMA_NAME, v.name AS OBJECT_NAME,
            CAST('VIEW' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST('' AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(CASE WHEN v.is_date_correlation_view = 1 THEN 'NO' ELSE 'YES' END AS NVARCHAR(8)) AS ATTR_A,
            CAST(CASE WHEN v.with_check_option = 1 THEN 'CHECK' ELSE '' END AS NVARCHAR(16)) AS ATTR_B,
            CAST((SELECT COUNT(*) FROM {c}sys.columns cc WHERE cc.object_id = v.object_id) AS NVARCHAR(16)) AS ATTR_C,
            {snip}
        FROM {c}sys.views v
        JOIN {c}sys.schemas s ON s.schema_id = v.schema_id
        LEFT JOIN {c}sys.sql_modules m ON m.object_id = v.object_id
        WHERE v.is_ms_shipped = 0{sch}{kw}
        ORDER BY s.name, v.name
    """
        if r == _r.ROLE_TRIGGER:
            kw = ""
            if keyword:
                kw = (f"\n            AND (tr.name LIKE '%{keyword}%'"
                      f" OR ISNULL(OBJECT_NAME(tr.parent_id), '') LIKE '%{keyword}%'"
                      f" OR ISNULL(m.definition, '') LIKE '%{keyword}%')")
            snip = _mssql_snippet("m.definition", keyword)
            # DML 트리거만(parent_class=1). DDL/LOGON 트리거는 DB·서버 스코프라 소유 테이블이 없어
            # 별도 행으로 뽑는다(아래 UNION) — 그래프에서 테이블에 붙일 수 없으므로 OWNER_OBJECT=''.
            return f"""
        SELECT TOP {_OBJ_ROWS_LIMIT} * FROM (
        SELECT
            s.name AS SCHEMA_NAME, tr.name AS OBJECT_NAME,
            CAST('DML_TRIGGER' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST(OBJECT_NAME(tr.parent_id) AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(CASE WHEN tr.is_instead_of_trigger = 1 THEN 'INSTEAD OF' ELSE 'AFTER' END AS NVARCHAR(16)) AS ATTR_A,
            CAST(STUFF(
                CASE WHEN EXISTS (SELECT 1 FROM {c}sys.trigger_events te
                     WHERE te.object_id = tr.object_id AND te.type_desc = 'INSERT') THEN ',INSERT' ELSE '' END +
                CASE WHEN EXISTS (SELECT 1 FROM {c}sys.trigger_events te
                     WHERE te.object_id = tr.object_id AND te.type_desc = 'UPDATE') THEN ',UPDATE' ELSE '' END +
                CASE WHEN EXISTS (SELECT 1 FROM {c}sys.trigger_events te
                     WHERE te.object_id = tr.object_id AND te.type_desc = 'DELETE') THEN ',DELETE' ELSE '' END,
                1, 1, '') AS NVARCHAR(64)) AS ATTR_B,
            CAST(CASE WHEN tr.is_disabled = 1 THEN '비활성' ELSE '활성' END AS NVARCHAR(16)) AS ATTR_C,
            {snip}
        FROM {c}sys.triggers tr
        JOIN {c}sys.objects po ON po.object_id = tr.parent_id
        JOIN {c}sys.schemas s ON s.schema_id = po.schema_id
        LEFT JOIN {c}sys.sql_modules m ON m.object_id = tr.object_id
        WHERE tr.is_ms_shipped = 0 AND tr.parent_class = 1{sch}{kw}
        UNION ALL
        SELECT
            CAST('' AS NVARCHAR(128)) AS SCHEMA_NAME, tr.name AS OBJECT_NAME,
            CAST('DDL_TRIGGER' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST('' AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST('DDL' AS NVARCHAR(16)) AS ATTR_A,
            CAST(ISNULL((SELECT TOP 1 te.type_desc FROM {c}sys.trigger_events te
                         WHERE te.object_id = tr.object_id), '') AS NVARCHAR(64)) AS ATTR_B,
            CAST(CASE WHEN tr.is_disabled = 1 THEN '비활성' ELSE '활성' END AS NVARCHAR(16)) AS ATTR_C,
            {snip}
        FROM {c}sys.triggers tr
        LEFT JOIN {c}sys.sql_modules m ON m.object_id = tr.object_id
        WHERE tr.is_ms_shipped = 0 AND tr.parent_class = 0{kw}
        ) q
        ORDER BY q.SCHEMA_NAME, q.OWNER_OBJECT, q.OBJECT_NAME
    """
        if r == _r.ROLE_ALIAS:
            kw = f"\n            AND sy.name LIKE '%{keyword}%'" if keyword else ""
            # base_object_name 은 `[db].[schema].[object]` 또는 linked-server 4-part 를 그대로 담는다.
            # 그 값이 **허용 DB 밖**을 가리키면 이름을 노출하지 않는다 — 시노님이 freeform
            # `_SAFE_SYS_VIEWS` 에서 의도적으로 제외됐던 바로 그 사유(allowlist 밖 DB·linked server
            # 명 노출)를 구조화 경로에서도 지킨다. 존재는 알리되 대상 이름은 가린다.
            allow = _sql_str_list(allow_dbs)
            _base_db = ("PARSENAME(sy.base_object_name, 3)")
            return f"""
        SELECT TOP {_OBJ_ROWS_LIMIT}
            s.name AS SCHEMA_NAME, sy.name AS OBJECT_NAME,
            CAST('SYNONYM' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST(CASE WHEN PARSENAME(sy.base_object_name, 4) IS NOT NULL THEN ''
                      WHEN {_base_db} IS NULL OR LOWER({_base_db}) IN ({allow})
                      THEN ISNULL(sy.base_object_name, '') ELSE '' END AS NVARCHAR(512)) AS OWNER_OBJECT,
            CAST(CASE WHEN PARSENAME(sy.base_object_name, 4) IS NOT NULL THEN ''
                      WHEN {_base_db} IS NULL OR LOWER({_base_db}) IN ({allow})
                      THEN ISNULL(sy.base_object_name, '') ELSE '' END AS NVARCHAR(512)) AS ATTR_A,
            CAST(CASE WHEN PARSENAME(sy.base_object_name, 4) IS NOT NULL THEN '(원격 서버 — 범위 밖)'
                      WHEN {_base_db} IS NULL THEN '(현재 DB)'
                      WHEN LOWER({_base_db}) IN ({allow}) THEN {_base_db}
                      ELSE '(허용 범위 밖 DB)' END AS NVARCHAR(128)) AS ATTR_B,
            CAST('' AS NVARCHAR(16)) AS ATTR_C,
            CAST('' AS NVARCHAR(200)) AS MATCH_SNIPPET
        FROM {c}sys.synonyms sy
        JOIN {c}sys.schemas s ON s.schema_id = sy.schema_id
        WHERE 1=1{sch}{kw}
        ORDER BY s.name, sy.name
    """
        if r == _r.ROLE_GENERATOR:
            kw = f"\n            AND sq.name LIKE '%{keyword}%'" if keyword else ""
            return f"""
        SELECT TOP {_OBJ_ROWS_LIMIT}
            s.name AS SCHEMA_NAME, sq.name AS OBJECT_NAME,
            CAST('SEQUENCE' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST('' AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.start_value), '') AS NVARCHAR(64)) AS ATTR_A,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.increment), '') AS NVARCHAR(64)) AS ATTR_B,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.last_used_value), '(미사용)') AS NVARCHAR(64)) AS ATTR_C,
            CAST('' AS NVARCHAR(200)) AS MATCH_SNIPPET
        FROM {c}sys.sequences sq
        JOIN {c}sys.schemas s ON s.schema_id = sq.schema_id
        WHERE 1=1{sch}{kw}
        ORDER BY s.name, sq.name
    """
        if r == _r.ROLE_SCHEDULE:
            return self._agent_jobs_sql(keyword=keyword, name="", allow_dbs=allow_dbs,
                                        schema=schema)
        return None

    def object_definition(self, role: str, name: str, schema: str = "",
                          db: str = "", allow_dbs=()) -> "str|None":
        from . import db_object_roles as _r
        r = _r.normalize_role(role)
        c = self._cat(db)
        d = str(db or "").strip()
        sch = f" AND s.name = '{schema}'" if schema else ""
        # cross-DB 정의: routine_definition 과 동일 사유 — OBJECT_DEFINITION() 은 pin DB 컨텍스트에서
        # 평가되므로 [db].sys.sql_modules 를 직접 읽는다(object_id 가 같은 [db] 공간에서 해소).
        if r in (_r.ROLE_VIEW, _r.ROLE_TRIGGER):
            is_view = r == _r.ROLE_VIEW
            src = "sys.views" if is_view else "sys.triggers"
            otype = "VIEW" if is_view else "TRIGGER"
            if is_view:
                owner = "CAST('' AS NVARCHAR(256))"
                join_schema = f"JOIN {c}sys.schemas s ON s.schema_id = o.schema_id"
                attr_a = "CAST(CASE WHEN o.is_date_correlation_view = 1 THEN 'NO' ELSE 'YES' END AS NVARCHAR(8))"
                attr_b = "CAST(CASE WHEN o.with_check_option = 1 THEN 'CHECK' ELSE '' END AS NVARCHAR(16))"
                attr_c = f"CAST((SELECT COUNT(*) FROM {c}sys.columns cc WHERE cc.object_id = o.object_id) AS NVARCHAR(16))"
                where_extra = "o.is_ms_shipped = 0"
            else:
                owner = "CAST(ISNULL(OBJECT_NAME(o.parent_id), '') AS NVARCHAR(256))"
                # DDL/LOGON 트리거(parent_class=0)는 소유 테이블이 없어 스키마 조인이 성립하지 않는다
                # → LEFT JOIN 으로 두고 스키마 필터가 있으면 DML 트리거만 남는다.
                join_schema = (f"LEFT JOIN {c}sys.objects po ON po.object_id = o.parent_id "
                               f"LEFT JOIN {c}sys.schemas s ON s.schema_id = po.schema_id")
                attr_a = "CAST(CASE WHEN o.is_instead_of_trigger = 1 THEN 'INSTEAD OF' WHEN o.parent_class = 0 THEN 'DDL' ELSE 'AFTER' END AS NVARCHAR(16))"
                attr_b = (f"CAST(ISNULL(STUFF((SELECT ',' + te.type_desc FROM {c}sys.trigger_events te "
                          f"WHERE te.object_id = o.object_id FOR XML PATH('')), 1, 1, ''), '') AS NVARCHAR(200))")
                attr_c = "CAST(CASE WHEN o.is_disabled = 1 THEN '비활성' ELSE '활성' END AS NVARCHAR(16))"
                where_extra = "o.is_ms_shipped = 0"
            if d:
                def_expr = (f"(SELECT sm.definition FROM {c}sys.sql_modules sm "
                            f"WHERE sm.object_id = o.object_id)")
            else:
                def_expr = "OBJECT_DEFINITION(o.object_id)"
            return f"""
        SELECT
            o.name AS OBJECT_NAME, CAST('{otype}' AS NVARCHAR(32)) AS OBJECT_TYPE,
            {owner} AS OWNER_OBJECT,
            {attr_a} AS ATTR_A, {attr_b} AS ATTR_B, {attr_c} AS ATTR_C,
            CAST('' AS NVARCHAR(128)) AS PART_LABEL,
            CAST(ISNULL({def_expr}, '') AS NVARCHAR(MAX)) AS DEFINITION
        FROM {c}{src} o
        {join_schema}
        WHERE {where_extra} AND o.name = '{name}'{sch}
    """
        if r == _r.ROLE_ALIAS:
            allow = _sql_str_list(allow_dbs)
            _base_db = "PARSENAME(sy.base_object_name, 3)"
            # 대상이 허용 범위 밖이면 DEFINITION 도 가린다(위 list_objects 와 동일 사유).
            _safe_base = (f"CASE WHEN PARSENAME(sy.base_object_name, 4) IS NOT NULL THEN '(원격 서버 대상 — 이름 비공개)'"
                          f" WHEN {_base_db} IS NULL OR LOWER({_base_db}) IN ({allow})"
                          f" THEN ISNULL(sy.base_object_name, '') ELSE '(허용 범위 밖 DB 대상 — 이름 비공개)' END")
            return f"""
        SELECT
            sy.name AS OBJECT_NAME, CAST('SYNONYM' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST({_safe_base} AS NVARCHAR(512)) AS OWNER_OBJECT,
            CAST({_safe_base} AS NVARCHAR(512)) AS ATTR_A,
            CAST(CASE WHEN PARSENAME(sy.base_object_name, 4) IS NOT NULL THEN '(원격 서버 — 범위 밖)'
                      WHEN {_base_db} IS NULL THEN '(현재 DB)'
                      WHEN LOWER({_base_db}) IN ({allow}) THEN {_base_db}
                      ELSE '(허용 범위 밖 DB)' END AS NVARCHAR(128)) AS ATTR_B,
            CAST('' AS NVARCHAR(16)) AS ATTR_C,
            CAST('' AS NVARCHAR(128)) AS PART_LABEL,
            CAST({_safe_base} AS NVARCHAR(MAX)) AS DEFINITION
        FROM {c}sys.synonyms sy
        JOIN {c}sys.schemas s ON s.schema_id = sy.schema_id
        WHERE sy.name = '{name}'{sch}
    """
        if r == _r.ROLE_GENERATOR:
            return f"""
        SELECT
            sq.name AS OBJECT_NAME, CAST('SEQUENCE' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST(TYPE_NAME(sq.user_type_id) AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.start_value), '') AS NVARCHAR(64)) AS ATTR_A,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.increment), '') AS NVARCHAR(64)) AS ATTR_B,
            CAST(ISNULL(CONVERT(NVARCHAR(64), sq.last_used_value), '(미사용)') AS NVARCHAR(64)) AS ATTR_C,
            CAST('' AS NVARCHAR(128)) AS PART_LABEL,
            CAST(CONCAT('MINVALUE ', ISNULL(CONVERT(NVARCHAR(64), sq.minimum_value), '?'),
                        ' MAXVALUE ', ISNULL(CONVERT(NVARCHAR(64), sq.maximum_value), '?'),
                        CASE WHEN sq.is_cycling = 1 THEN ' CYCLE' ELSE ' NO CYCLE' END,
                        CASE WHEN sq.is_cached = 1 THEN ' CACHE' ELSE ' NO CACHE' END) AS NVARCHAR(MAX)) AS DEFINITION
        FROM {c}sys.sequences sq
        JOIN {c}sys.schemas s ON s.schema_id = sq.schema_id
        WHERE sq.name = '{name}'{sch}
    """
        if r == _r.ROLE_SCHEDULE:
            return self._agent_jobs_sql(keyword="", name=name, allow_dbs=allow_dbs, schema=schema)
        return None

    def _agent_jobs_sql(self, keyword: str, name: str, allow_dbs, schema: str = "") -> str:
        """SQL Server Agent 작업 조회 — 열거(name='')와 정의(name!='')를 한 골격으로.

        **msdb 접근의 유일한 지점**이다. 컬럼 투영·조인·필터가 전부 여기서 고정되며,
        외부에서 오는 값은 `keyword`/`name`/`allow_dbs`/`schema` 뿐이다 — freeform 의 msdb
        하드 차단은 불변이고, 이 경로가 새 우회로가 되지 않도록 임의 SQL 조립을 허용하지 않는다.

        **정제 계약(수정됨)**: `schema` 는 식별자라 caller 가 `_safe_ident` 로 정제한다. 그러나
        `name`/`keyword` 는 **작업명 — 식별자가 아니라 리터럴 값**이다. 식별자 정제기를 태우면
        `[DK] Ranking Update` 의 대괄호가 지워져 영구 미매칭이 되므로(관측 서버 83개 중 73개가
        `[` 접두), caller 는 문자를 보존하는 `_safe_literal_value`(역슬래시·제어문자만 제거)로
        넘기고 **리터럴 이스케이프(작은따옴표 이중화)는 이 함수가 진다** — 삽입 지점이 이중화를
        책임지는 `_sql_str_list` 와 같은 계약이다. 그래야 인용 탈출 경계가 한 곳에 남는다.

        열거 모드: 작업당 1행(대상 DB 별로 분해 — 한 작업이 여러 허용 DB 를 건드리면 각 DB 슬롯에
        나타난다). 정의 모드: **단계당 1행**(PART_LABEL='N. 단계명', DEFINITION=단계 명령).
        `sysjobsteps.database_name` 이 허용 DB 인 단계만 통과한다(제품 경계 — 위 (2) 참조).
        """
        # 리터럴 이스케이프는 삽입 지점 책임(위 계약). caller 정제와 이중으로 걸리지 않도록
        # 여기서만 한 번 이중화한다.
        name = str(name or "").replace("'", "''")
        keyword = str(keyword or "").replace("'", "''")
        schema = str(schema or "").replace("'", "''")
        allow = _sql_str_list(allow_dbs)
        def database_filter(alias: str) -> str:
            clause = f"LOWER({alias}.database_name) IN ({allow})"
            if schema:
                clause += f" AND LOWER({alias}.database_name) = LOWER('{schema}')"
            return clause
        db_filter = database_filter("st")
        # 주기 표현: sysschedules 는 freq_type 코드라 사람이 읽을 문자열로 환원한다.
        freq = """CASE sc.freq_type
                    WHEN 1 THEN '1회'
                    WHEN 4 THEN CONCAT('매일(', sc.freq_interval, '일 간격)')
                    WHEN 8 THEN '매주'
                    WHEN 16 THEN '매월'
                    WHEN 32 THEN '매월(상대)'
                    WHEN 64 THEN 'SQL Agent 시작 시'
                    WHEN 128 THEN 'CPU 유휴 시'
                    ELSE '' END"""
        if name:
            return f"""
        SELECT
            j.name AS OBJECT_NAME, CAST('AGENT_JOB' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST(ISNULL(st.database_name, '') AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(CASE WHEN j.enabled = 1 THEN '활성' ELSE '비활성' END AS NVARCHAR(16)) AS ATTR_A,
            CAST(ISNULL((SELECT TOP 1 {freq} FROM msdb.dbo.sysjobschedules js
                         JOIN msdb.dbo.sysschedules sc ON sc.schedule_id = js.schedule_id
                         WHERE js.job_id = j.job_id), '(스케줄 없음)') AS NVARCHAR(64)) AS ATTR_B,
            CAST(ISNULL(CONVERT(NVARCHAR(32), j.date_modified, 120), '') AS NVARCHAR(32)) AS ATTR_C,
            CAST(CONCAT(st.step_id, '. ', st.step_name, ' [', ISNULL(st.subsystem, ''), ' @ ',
                        ISNULL(st.database_name, ''), ']') AS NVARCHAR(128)) AS PART_LABEL,
            CAST(ISNULL(st.command, '') AS NVARCHAR(MAX)) AS DEFINITION
        FROM msdb.dbo.sysjobs j
        JOIN msdb.dbo.sysjobsteps st ON st.job_id = j.job_id
        WHERE j.name = '{name}' AND {db_filter}
        ORDER BY st.step_id
    """
        kw = ""
        keyword_db_filter = database_filter("k")
        if keyword:
            kw = (f" AND (j.name LIKE '%{keyword}%'"
                  f" OR ISNULL(j.description, '') LIKE '%{keyword}%'"
                  f" OR EXISTS (SELECT 1 FROM msdb.dbo.sysjobsteps k"
                  f"            WHERE k.job_id = j.job_id AND {keyword_db_filter} AND ISNULL(k.command, '') LIKE '%{keyword}%'))")
        return f"""
        SELECT TOP {_OBJ_ROWS_LIMIT}
            CAST(st.database_name AS NVARCHAR(128)) AS SCHEMA_NAME,
            j.name AS OBJECT_NAME,
            CAST('AGENT_JOB' AS NVARCHAR(32)) AS OBJECT_TYPE,
            CAST('' AS NVARCHAR(256)) AS OWNER_OBJECT,
            CAST(CASE WHEN j.enabled = 1 THEN '활성' ELSE '비활성' END AS NVARCHAR(16)) AS ATTR_A,
            CAST(ISNULL((SELECT TOP 1 {freq} FROM msdb.dbo.sysjobschedules js
                         JOIN msdb.dbo.sysschedules sc ON sc.schedule_id = js.schedule_id
                         WHERE js.job_id = j.job_id), '(스케줄 없음)') AS NVARCHAR(64)) AS ATTR_B,
            CAST(ISNULL(CONVERT(NVARCHAR(32), j.date_modified, 120), '') AS NVARCHAR(32)) AS ATTR_C,
            CAST(ISNULL(j.description, '') AS NVARCHAR(200)) AS MATCH_SNIPPET
        FROM msdb.dbo.sysjobs j
        JOIN msdb.dbo.sysjobsteps st ON st.job_id = j.job_id
        WHERE {db_filter}{kw}
        GROUP BY st.database_name, j.name, j.enabled, j.job_id, j.date_modified, j.description
        ORDER BY st.database_name, j.name
    """

    def probe_relationship_overlap(self, src_schema, src_table, src_col,
                                   tgt_schema, tgt_table, tgt_col, sample, timeout_ms=0):
        """암묵 관계 검증(feature-0016): src 컬럼 표본이 tgt 컬럼에 존재하는 비율.

        반환 SQL 결과 = (sampled, matched) 1행. read-only. 식별자는 대괄호 이스케이프(']' 이중화).
        timeout_ms>0 이면 `SET LOCK_TIMEOUT` 로 락 대기 상한(운영 DB blocking hang 차단 — MSSQL 은
        per-statement CPU timeout 구문이 없어 락 대기를 상한. 표본 상한 TOP {n} 이 CPU 폭주를 2차 제한).

        §55(REQ-20260706 ②) 스키마-slot 해석: 본 플랫폼의 MSSQL 관계 row 스키마-slot 은 **DB(catalog)명**
        (ADR-007 규약 — effective schema=DB명, 실제 스키마는 dbo 가정). 따라서 qualifier 는 3-part
        `[db].[dbo].[table]` 로 조립해 **같은 서버의 다른 DB 간(cross-DB) 프로브**를 한 연결에서 실행
        가능하게 한다(기존 2-part `[db].[table]` 은 db 를 스키마로 오해석 — probe_and_reinforce 가
        qualifier 를 벗겨 회피하던 제약의 근본 해소). slot 비면 연결 DB 기본 스키마 해석(불변).
        예외: slot 이 'dbo'(레거시 대화학습 행 — 2-part `dbo.T` 파싱 유래)면 실 스키마로 보고 2-part
        유지 — `[dbo].[dbo].[T]` 오조립이 "Database 'dbo'" missing-object → 실관계 오파단을 막는다.
        한계: dbo 외 실스키마 테이블은 관계 파이프라인 전반이 미추적(플랫폼 가정)."""
        def q(x):
            return "[" + str(x).replace("]", "]]") + "]"
        def qual(sch, tbl):
            s = str(sch or "").strip()
            if not s:
                return q(tbl)
            if s.lower() == "dbo":
                return f"{q(s)}.{q(tbl)}"          # 실 스키마(레거시 slot) — 2-part 유지
            return f"{q(s)}.[dbo].{q(tbl)}"        # 스키마-slot=DB명(ADR-007) — 3-part cross-DB
        n = max(1, min(int(sample), 200))
        src = qual(src_schema, src_table)
        tgt = qual(tgt_schema, tgt_table)
        prefix = f"SET LOCK_TIMEOUT {int(timeout_ms)}; " if int(timeout_ms or 0) > 0 else ""
        # rel-selfheal 라이브 후속(probe-mssqlfix): MSSQL 은 집계식이 서브쿼리를 포함할 수 없다
        # (오류 130 "Cannot perform an aggregate function on an expression containing an
        # aggregate or a subquery") — SUM(CASE WHEN EXISTS ...) 가 라이브에서 전면 실패했다
        # (파이프라인 정지 동안 미노출이던 잠복 결함). CASE/EXISTS 를 파생 테이블 안으로
        # 내리고 바깥에서 SUM(단순 컬럼) 집계로 재작성 — 의미(표본 n 중 겹침 수) 동일.
        return (
            f"{prefix}SELECT COUNT(*) AS sampled, SUM(s.m) AS matched FROM ("
            f"SELECT TOP {n} CASE WHEN EXISTS "
            f"(SELECT 1 FROM {tgt} t WHERE t.{q(tgt_col)} = s0.{q(src_col)}) "
            f"THEN 1 ELSE 0 END AS m "
            f"FROM {src} s0 WHERE s0.{q(src_col)} IS NOT NULL) s"
        )


_MYSQL = MySQLDialect()
_MSSQL = MSSQLDialect()


def get(engine: str | None) -> Dialect:
    return _MSSQL if str(engine or "mysql").strip().lower() == "mssql" else _MYSQL


def active() -> Dialect:
    """현재 컨텍스트의 활성 datasource 엔진에 맞는 dialect (기본 mysql)."""
    return get(cfg.get_active_datasource_engine())
