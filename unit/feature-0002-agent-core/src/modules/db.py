__all__ = [
    "DatasourceCircuitOpen",
    "_collect_cursor_result",
    "_pg_available",
    "_pg_connect",
    "_pg_connect_ro",
    "_pg_mark_kb_invalidation",
    "_pg_check_kb_invalidation",
    "_should_retry_db_error",
    "connect",
    "connect_with_retry",
    "execute_sql",
    "list_server_databases",
    "probe_datasource",
    "records_to_columns_rows",
    "summarize_mcp_result",
]


"""Database connection management and SQL execution."""
from .config import *
import logging
import threading
import time
from typing import Any
import mysql.connector
import mysql.connector.pooling  # MySQLConnectionPool (TASK-0144)
from mysql.connector.errors import PoolError  # 풀 소진 시그널 (TASK-0144)

# ─────────────────────────────────────────────────────────────────────────────
# TASK-0144: opt-in MySQL 커넥션 풀 (기본 OFF, 폴백 안전).
#
# 안전 계약:
#   - AGENT_DB_POOL_ENABLED 기본 False → connect() 가 기존 connect-per-request
#     경로 그대로 (mysql.connector.connect(**params)) → 동작 0 변경.
#   - True(canary 로만) 일 때만 (host,user,database) 시그니처별 풀에서 대여.
#   - 풀 소진(PoolError) / 풀 생성 실패 시 direct connect 로 폴백 (절대 raise 로
#     요청을 실패시키지 않음) + logger.warning. 즉 풀은 best-effort 최적화.
#   - 풀에서 꺼낸 커넥션은 호출측이 .close() 하면 mysql.connector 기본 동작으로
#     풀에 반환된다 (추가 반환 API 불필요). direct connect 폴백 커넥션도 .close()
#     로 정상 종료되므로 호출측 수명주기 코드는 풀/비풀 구분 없이 동일하다.
#
# 풀 키 설계: (host, port, user, database) 4-tuple 을 풀 이름으로 직렬화.
#   - mysql.connector 풀은 생성 시 user/password/database 가 고정되므로, connect()
#     의 3분기 라우팅(replica / RO data-plane(agent_ro) / memory primary(root)) 이
#     고른 (host,user) 조합과, database 값까지 키에 포함해야 cross-contamination 이
#     없다. database=None(서버 default) 와 특정 database 는 서로 다른 풀.
# ─────────────────────────────────────────────────────────────────────────────
_db_logger = logging.getLogger("agent_core.db")
_POOL_REGISTRY: dict[str, "mysql.connector.pooling.MySQLConnectionPool"] = {}
_POOL_LOCK = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# 데이터플레인 연결 격리 (TASK: ds-connect-isolation → conn-health-monitor)
#
# 문제: 한 datasource 의 연결 불안정이 단일 직렬 ask-worker 를 점유해 정상 datasource 제품
#   요청까지 지연시킨다(connection timeout 이 쿼리 예산을 재사용해 1회 시도가 길게 블록).
#
# 격리 2단:
#   1) bounded connect timeout — _dataplane_connect_timeout() (AGENT_DB_CONNECT_TIMEOUT_SEC).
#      실제 데이터 연결 수립 상한을 쿼리 예산(AGENT_TIMEOUT_SEC)에서 분리(기본 10s).
#      control-plane(datasource=None)은 미적용.
#   2) connection health 게이트 — modules/conn_health.py 가 백그라운드 TCP liveness probe 로
#      per-datasource 상태를 미리 유지(적응형 timeout 100ms→×2→10s). connect_with_retry 는
#      실제 연결 전 conn_health.should_fast_fail(scope_key) 로 unstable 이면 즉시 fail-fast
#      (DatasourceCircuitOpen) → worker 무점유. 복구는 background 모니터가 담당(foreground
#      half-open trial 불요 — thundering-herd 함정 원천 제거). 실제 연결 결과는
#      conn_health.record_foreground_result 로 피드백(모니터 없이도 반응).
#
# 과거(TASK-0247) foreground in-process breaker 는 conn_health 로 흡수됐다. db.py 는 scope_key
#   키 산출(_breaker_key) + connect-stage 실패 분류(_is_connect_breaker_failure) + bounded
#   connect timeout 만 보유하고, 상태/게이트/복구는 conn_health 가 단일 소유한다.
# ─────────────────────────────────────────────────────────────────────────────
class DatasourceCircuitOpen(Exception):
    """datasource 연결 health unstable — 연결 시도 없이 즉시 fail-fast(격리).

    connect_with_retry 는 게이트 단계에서 raise 하므로 재시도하지 않는다. tool 경로
    (execute_tool)는 per-datasource 에러 문자열로 surface 한다. 좌표/비밀번호 비노출."""

    def __init__(self, scope_key: str, retry_after: float):
        self.scope_key = scope_key
        self.retry_after = max(0.0, float(retry_after))
        super().__init__(
            f"데이터소스 연결이 일시적으로 불안정하여 차단되었습니다 "
            f"(약 {int(self.retry_after) + 1}초 후 자동 재시도)."
        )


def _dataplane_connect_timeout() -> int:
    """data-plane 연결 수립 상한(초). AGENT_DB_CONNECT_TIMEOUT_SEC>0 이면 그 값, 아니면
    AGENT_TIMEOUT_SEC 폴백(기존 동작). 쿼리 timeout(AGENT_TIMEOUT_SEC)과 분리된 값."""
    t = int(AGENT_DB_CONNECT_TIMEOUT_SEC or 0)
    return t if t > 0 else int(AGENT_TIMEOUT_SEC)


def _controlplane_connect_timeout() -> int:
    """control-plane(datasource=None: MEMORY_DB/DB_CONNECT_DB/replica/data-RO) + KB Postgres
    연결 *수립* 상한(초). TASK-0255: 과거 connection_timeout=AGENT_TIMEOUT_SEC(운영 300s)라
    control-plane 불안정이 cycle 을 최대 300s×retry 블록했다. 로컬·신뢰 호스트이므로 bounded(기본 10s).
    **data-plane 과 달리 0/미설정 폴백은 10s** (AGENT_TIMEOUT_SEC 300s 회귀 방지). 쿼리 timeout 과 분리.
    control-plane breaker 는 적용하지 않는다(timeout 만) — MEMORY_DB fast-fail=전체 마비 방지."""
    t = int(AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC or 0)
    return t if t > 0 else 10


def _breaker_key(datasource: "dict | None") -> "str | None":
    """datasource scope_key(엔진+host+port 안정 해시). None=control-plane(미적용).

    엔드포인트(host:port) 단위 — 연결 *수립* 실패는 그 서버 공통 신호이므로 user/db 를 키에서
    제외한다. 인증 실패(계정별)는 _is_connect_breaker_failure 가 제외하므로 한 계정의 잘못된
    비밀번호가 같은 서버 다른 계정의 게이트를 열지 않는다. conn_health._scope_key_of 와 동형."""
    if not datasource:
        return None
    try:
        from . import datasources as _ds
        k = _ds.scope_key(datasource)
        if k:
            return str(k)
    except Exception:
        pass
    host = datasource.get("host")
    if not host:
        return None
    engine = (datasource.get("engine") or "mysql").strip().lower()
    try:
        port = int(datasource.get("port") or 0)
    except Exception:
        port = 0
    return f"{engine}:{str(host).strip().lower()}:{port}"


def _is_connect_breaker_failure(err: Exception) -> bool:
    """health unstable 로 피드백할 대상 = **연결 수립** 실패만(쿼리시점 에러 제외).

    DatasourceCircuitOpen(이미 게이트 신호)과 1205(deadlock — 쿼리시점 락, 연결과 무관)은 제외.
    인증(1045 등)도 errno set 비포함으로 제외 — 한 계정 자격오류가 datasource 를 unstable 로
    오판하지 않게(인증 실패는 fast-fail 이라 starvation 무관)."""
    if isinstance(err, DatasourceCircuitOpen):
        return False
    code = getattr(err, "errno", None)
    if code == 1205:  # deadlock — 쿼리시점, 연결 수립과 무관
        return False
    if code in (2002, 2003, 2005, 2006, 2013):  # socket/can't-connect/unknown-host/gone/lost
        return True
    msg = str(err).lower()
    for pat in (
        "can't connect", "unable to connect", "connection refused", "connection failed",
        "timed out", "timeout", "name or service not known", "no route to host",
        "login timeout", "host is unreachable",
    ):
        if pat in msg:
            return True
    return False


def _pool_key(params: dict[str, Any]) -> str:
    """풀 레지스트리 키 — (host, port, user, database) 시그니처를 직렬화.

    password 는 (host,user) 에 종속이므로 키에서 제외. database=None 은 빈 문자열로
    구분(서버 default DB 전용 풀). user 라우팅(root vs agent_ro) 과 replica host 분기는
    자연히 다른 키가 된다.
    """
    return "|".join(
        str(params.get(k, ""))
        for k in ("host", "port", "user", "database")
    )


def _get_or_create_pool(params: dict[str, Any]):
    """시그니처별 풀을 lazy 생성 후 반환. thread-safe.

    풀 생성 실패 시 None 을 반환하여 connect() 가 direct connect 로 폴백하게 한다
    (raise 하지 않음 — 풀은 best-effort).
    """
    key = _pool_key(params)
    pool = _POOL_REGISTRY.get(key)
    if pool is not None:
        return pool
    with _POOL_LOCK:
        # double-checked locking — 다른 스레드가 먼저 생성했을 수 있음.
        pool = _POOL_REGISTRY.get(key)
        if pool is not None:
            return pool
        try:
            pool_params = dict(params)
            pool_params["pool_name"] = f"agent_pool_{abs(hash(key)) & 0xFFFFFFFF:x}"
            pool_params["pool_size"] = AGENT_DB_POOL_SIZE
            pool_params["pool_reset_session"] = bool(AGENT_DB_POOL_RESET_SESSION)
            pool = mysql.connector.pooling.MySQLConnectionPool(**pool_params)
            _POOL_REGISTRY[key] = pool
            return pool
        except Exception as exc:
            _db_logger.warning(
                "db_pool_create_failed key=%s err=%r — direct connect 로 폴백", key, exc
            )
            return None


# TASK-0015 §2.1.3 M0: psycopg3 import 는 optional. requirements.txt 에는 포함되어
# 있으나 M0~M1 단계에서는 코드가 호출되지 않을 수도 (postgres 컨테이너 미가동 환경).
# import 실패 시 _pg_connect() 가 fail-loud 하고, _pg_available() 가 False 를 반환.
try:
    import psycopg as _psycopg  # type: ignore[import-not-found]
    _PSYCOPG_IMPORT_ERR: Exception | None = None
except Exception as _e:  # pragma: no cover — env without psycopg
    _psycopg = None  # type: ignore[assignment]
    _PSYCOPG_IMPORT_ERR = _e

# 멀티 datasource Stage 2 (P4): MSSQL(pymssql) optional import. engine='mssql' datasource
# 분석에만 쓰인다. 미설치 환경(기본)에서는 None — mssql datasource 연결 시 fail-loud.
try:
    import pymssql as _pymssql  # type: ignore[import-not-found]
    _PYMSSQL_IMPORT_ERR: Exception | None = None
except Exception as _e:  # pragma: no cover — env without pymssql
    _pymssql = None  # type: ignore[assignment]
    _PYMSSQL_IMPORT_ERR = _e


def _connect_mssql(datasource: dict, database: str | None, autocommit: bool):
    """MSSQL(SQL Server) datasource 연결 (Stage 2 P4, pymssql).

    **DB 컨텍스트 고정 (P6, M-1 엔진별 정합)**: MSSQL 은 `database > schema > table` 3계층이라
    schema 격리(allowlist=dbo/sales)는 **특정 DATABASE 안에서** 의미를 가진다. 따라서 연결은
    datasource 의 `default_db` 로 고정하고(없으면 caller 명시값), 쿼리는 2-part `schema.table` 로
    한다. MySQL 의 M-1("database=None — 미접두 쿼리가 default_db 를 우회조회")과 달리 MSSQL 에서는
    **무자격 table-ref 를 P6 가 fail-closed 로 거부**(tools._freeform_sql_access_error)하고 3-part
    catalog(DB) cross-DB 참조도 차단하므로, DB 고정이 오히려 안전하다. (로그인 GRANT 도 해당 DB 의
    허용 스키마로 한정 — bin/datasource-mssql-ro-bootstrap.sql.) default_db 미설정 MSSQL datasource 는
    로그인 기본 DB(보통 master)로 붙어 2-part 쿼리가 깨지므로 DS_<KEY>_DEFAULT_DB 설정이 사실상 필수.
    포트 미설정 시 MSSQL 기본 1433.
    """
    if _pymssql is None:
        raise RuntimeError(
            f"pymssql 미설치 — mssql datasource 연결 불가. requirements.txt 의 pymssql 확인. "
            f"original error: {_PYMSSQL_IMPORT_ERR!r}"
        )
    port = int(datasource.get("port") or 1433)
    # TASK-0213: DB 컨텍스트는 caller 명시값 > 제품 auto-pin(default_db, 첫 접근가능 DB) 순. 둘 다 없으면
    # (예: 접근가능 DB 미설정 제품) **로그인 기본 DB(보통 master, 업무·시스템 DB)로 붙지 않고 중립 `tempdb`**
    # 로 고정한다(사용자 결정). tempdb 는 업무데이터가 없어 2-part 무자격 참조가 새지 않고, 업무 쿼리는
    # 3-part `DB.스키마.테이블`(allowlist 검사) 로만 동작한다. '기본 참조 DB' 데이터소스 필드는 폐지(TASK-0213).
    db_name = database or datasource.get("default_db") or "tempdb"
    conn = _pymssql.connect(
        server=datasource.get("host") or DB_HOST,
        port=str(port),
        user=datasource.get("user") or DB_USER,
        password=datasource.get("password", ""),
        database=db_name,  # MSSQL DB 컨텍스트(auto-pin 또는 중립 tempdb 폴백)
        # ds-connect-isolation: 연결 수립(login_timeout)은 짧은 상한으로 분리해 불안정
        # datasource 가 worker 를 점유하지 못하게 한다. 쿼리 실행(timeout)은 정상 장기 쿼리를
        # 위해 쿼리 예산(AGENT_TIMEOUT_SEC) 유지.
        login_timeout=_dataplane_connect_timeout(),
        timeout=int(AGENT_TIMEOUT_SEC),
        autocommit=bool(autocommit),
        charset="UTF-8",
    )
    return conn


def connect(database: str | None = None, autocommit: bool = True, datasource: dict | None = None):
    # ── 멀티 datasource (P1, DESIGN Stage 1): 명시 datasource 좌표 우선 ──────────
    # datasource(dict: host/port/user/password/default_db) 가 주어지고 flag 가 켜져 있으면
    # 문자열 휴리스틱(MEMORY_DB/replica/AGENT_DATA_DB) 라우팅을 **건너뛰고** 그 좌표로 연결한다.
    # data-plane(분석 대상) 전용 경로 — 호출측(agent_core/insight)이 conversation 의 product 에
    # 바인딩된 datasource 를 해석해 넘긴다. flag OFF 또는 datasource=None 이면 아래 기존 라우팅이
    # 100% 그대로 — 기존 단일 MySQL 동작 0 변경(M-3: plane 은 호출측이 명시).
    if datasource and AGENT_MULTI_DATASOURCE_ENABLED:
        # ds-connect-isolation: data-plane 연결 수립 timeout 을 쿼리 예산과 분리(bounded).
        # breaker 게이트/기록은 connect_with_retry 경계에서 요청당 1회 수행한다(여기 connect()
        # 안이 아님 — 내부 retry 가 1요청을 threshold 까지 밀어올리는 false-open 증폭 차단).
        # Stage 2 (P4): engine 디스패치 — mssql 은 pymssql, 그 외(mysql)는 mysql.connector.
        if (datasource.get("engine") or "mysql").strip().lower() == "mssql":
            return _connect_mssql(datasource, database, autocommit)
        host = datasource.get("host") or DB_HOST
        port = int(datasource.get("port") or DB_PORT)
        user = datasource.get("user") or DB_USER
        password = datasource.get("password", "")
        # REV-20260610-0187 M-1: datasource 의 default_db 를 연결의 암묵 기본 스키마로 적용하지
        # 않는다. 적용하면 미접두 쿼리(`SELECT * FROM t`)가 schema-ref 0개로 allowlist 를 우회해
        # default_db 를 조회하게 된다. database 는 caller 가 명시한 값만 사용(agent_core 는 datasource
        # 경로에서 None 전달) → schema-prefixed 쿼리만 가능 → allowlist 가 유일 게이트.
        # connection_timeout: 쿼리 예산(AGENT_TIMEOUT_SEC)과 분리된 연결 수립 상한(ds-connect-isolation).
        params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "autocommit": autocommit,
            "connection_timeout": _dataplane_connect_timeout(),
            "charset": "utf8mb4",
            "use_unicode": True,
        }
        if database:
            params["database"] = database
        if not AGENT_DB_POOL_ENABLED:
            return mysql.connector.connect(**params)
        return _pooled_connect(params)

    # 복제 DB (TASK-0044): REPLICA_DB_HOST 가 설정되어 있고 요청된 database 가
    # memory DB(agent_memory) 가 아닌 경우(= data-plane 쿼리) 복제 인스턴스로 라우팅.
    # memory DB 연결은 항상 primary 로 유지된다 (대화·세션·권한 정본은 primary).
    #
    # TASK-0107: sandbox schema (agent_attachment_<sha256[:32]>) 도 primary 유지.
    # sandbox 는 사용자 첨부 ingest 로 primary 에 동적 생성되며 replica 복제 latency
    # 또는 미복제 환경에서도 즉시 SELECT 가능해야 한다. memory DB 와 같은 DB user
    # 로 접근하므로 별 grant 추가 불필요 (단일-user MVP).
    db_str = str(database) if database is not None else ""
    is_sandbox = db_str.startswith("agent_attachment_")
    use_replica = (
        bool(REPLICA_DB_ENABLED)
        and (database is not None)
        and db_str != str(MEMORY_DB)
        and not is_sandbox
    )
    if use_replica:
        host, port, user, password = REPLICA_DB_HOST, REPLICA_DB_PORT, REPLICA_DB_USER, REPLICA_DB_PASSWORD
    elif db_str != str(MEMORY_DB) and AGENT_DATA_DB_USER:
        # TASK-0128 (#2): data-plane(고객 데이터/sandbox 분석) 연결은 최소권한 RO 유저로 라우팅.
        # MEMORY_DB(제어) 연결은 root 유지. AGENT_DATA_DB_USER 미설정 시 아래 else(root) 로 폴백.
        host, port, user, password = DB_HOST, DB_PORT, AGENT_DATA_DB_USER, AGENT_DATA_DB_PASSWORD
    else:
        host, port, user, password = DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
    params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "autocommit": autocommit,
        # TASK-0255: control-plane(datasource=None) 연결 수립 상한을 쿼리 예산(AGENT_TIMEOUT_SEC=300s)에서
        # 분리(bounded, 기본 10s). 과거 300s 라 control-plane 불안정이 cycle 을 최대 300s×retry 블록했다.
        # 쿼리 실행 timeout 은 별개(연결 후 SQL 은 server 측·driver 별 제어). breaker 는 미적용(여기는 datasource=None).
        "connection_timeout": _controlplane_connect_timeout(),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if database:
        params["database"] = database

    # TASK-0144: 기본 OFF — 풀 비활성 시 기존 connect-per-request 경로 그대로
    # (동작 0 변경). opt-in(canary) True 일 때만 풀 경로 + 폴백.
    if not AGENT_DB_POOL_ENABLED:
        return mysql.connector.connect(**params)
    return _pooled_connect(params)


def _pooled_connect(params: dict[str, Any]):
    """풀에서 커넥션 대여 — 풀 소진/생성 실패 시 direct connect 로 폴백 (TASK-0144).

    절대 raise 로 요청을 실패시키지 않는다. 풀이 없거나(생성 실패) 소진(PoolError)
    되면 logger.warning 후 mysql.connector.connect(**params) 로 direct connect 한다.
    direct connect 자체가 실패(DB down 등) 하면 그 예외는 평소처럼 전파(폴백 대상 아님).
    """
    pool = _get_or_create_pool(params)
    if pool is None:
        # 풀 생성 실패 — 이미 warning 로깅됨. direct connect 로 폴백.
        return mysql.connector.connect(**params)
    try:
        return pool.get_connection()
    except PoolError as exc:
        # 풀 소진 — overflow 허용(기본) 여부와 무관히 안전하게 direct connect 폴백.
        _db_logger.warning(
            "db_pool_exhausted key=%s overflow_allowed=%s err=%r — direct connect 로 폴백",
            _pool_key(params), bool(AGENT_DB_POOL_MAX_OVERFLOW), exc,
        )
        return mysql.connector.connect(**params)
    except Exception as exc:
        # 예기치 못한 풀 오류도 요청 실패로 번지지 않게 폴백.
        _db_logger.warning(
            "db_pool_get_failed key=%s err=%r — direct connect 로 폴백",
            _pool_key(params), exc,
        )
        return mysql.connector.connect(**params)


def _should_retry_db_error(err: Exception) -> bool:
    # ds-connect-isolation: breaker open 은 의도된 즉시 fail-fast → 재시도 금지(블로킹 회피).
    if isinstance(err, DatasourceCircuitOpen):
        return False
    code = getattr(err, "errno", None)
    if code in (2003, 2006, 2013, 1205):
        return True
    msg = str(err).lower()
    if "can't connect" in msg or "lost connection" in msg or "timeout" in msg:
        return True
    return False


def connect_with_retry(
    database: str | None = None, autocommit: bool = True, attempts: int | None = None,
    datasource: dict | None = None,
):
    # conn-health-monitor: connection health 게이트의 **단일 경계**. 모든 런타임 datasource
    # 연결이 이 함수를 경유하므로(라우터 conn_for·agent_core·insight) 실제 연결 전 1회 게이트
    # (conn_health.should_fast_fail)를 적용하고, 결과를 1회 피드백한다. datasource=None(control-
    # plane: memory DB)이면 게이트/피드백 미적용(기존 동작 0 변경). 복구는 background 모니터.
    attempts = attempts if attempts is not None else AGENT_DB_CONNECT_RETRIES
    attempts = max(1, int(attempts))
    _bkey = _breaker_key(datasource)
    if datasource and _bkey:
        try:
            from . import conn_health as _ch
        except Exception:
            _ch = None
        # health unstable → 시도 없이 즉시 fail-fast(worker 무점유). 복구는 background 모니터.
        if _ch is not None and _ch.should_fast_fail(_bkey):
            raise DatasourceCircuitOpen(_bkey, float(AGENT_CONN_UNSTABLE_RECHECK_SEC))
    else:
        _ch = None
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            conn = connect(database=database, autocommit=autocommit, datasource=datasource)
            if _ch is not None:
                _record_health(_ch, datasource, ok=True)  # 성공 → healthy 피드백(예외 격리)
            return conn
        except Exception as exc:
            last_exc = exc
            if not _should_retry_db_error(exc):
                break
            if attempt < attempts:
                time.sleep(AGENT_DB_CONNECT_BACKOFF_SEC * attempt)
                continue
    # 모든 시도 소진 → 연결 수립 실패만 unstable 피드백(인증/deadlock 등은 제외).
    if _ch is not None and _is_connect_breaker_failure(last_exc):
        _record_health(_ch, datasource, ok=False, err=last_exc)
    if last_exc:
        raise last_exc
    raise RuntimeError("DB 연결 실패")


def _record_health(ch, datasource, ok: bool, err: "Exception | None" = None) -> None:
    """conn_health 피드백 — 그 내부 예외가 connect 결과/원본 예외를 절대 삼키지 않게 격리."""
    try:
        errtag = ""
        if err is not None:
            errtag = str(getattr(err, "errno", None) or type(err).__name__)
        ch.record_foreground_result(datasource, ok=ok, err=errtag)
    except Exception as _e:  # pragma: no cover — 방어
        _db_logger.warning("conn_health_feedback_failed err=%r", _e)


def probe_datasource(datasource: dict, *, timeout: int | None = None) -> tuple[bool, float, str]:
    """datasource 좌표로 직접 연결 + `SELECT 1` (관리자 명시 연결테스트, P2).

    **flag(AGENT_MULTI_DATASOURCE_ENABLED) 무관**으로 좌표에 연결한다 — 운영자가 flag 활성화
    *전*에 자격증명·연결성을 검증하는 용도. authz 는 호출측(web admin 권한)이 담당한다.
    database(default_db) 는 설정하지 않는다 — host/port/user/password 연결성만 검증(에이전트가
    schema-prefixed 로 동작하므로 특정 DB 기본 선택 불요, M-1 정합).

    password 유출 방지: 예외 전문(host/user 포함 가능)을 반환하지 않고 errno/예외타입만 반환한다.
    Returns: (ok, elapsed_ms, error_message).
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    start = time.time()
    conn = None
    try:
        if engine == "mssql":
            # Stage 2 (P4): MSSQL probe (pymssql, flag 무관 명시 테스트).
            if _pymssql is None:
                return False, 0.0, "pymssql_not_installed"
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8),
                timeout=int(timeout or 8),
            )
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8),
                charset="utf8mb4",
                use_unicode=True,
            )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchall()
        cur.close()
        return True, (time.time() - start) * 1000.0, ""
    except Exception as exc:
        errno = getattr(exc, "errno", None)
        # errno/예외타입만 노출 (host/user/pw 비유출).
        msg = f"errno={errno}" if errno else type(exc).__name__
        return False, (time.time() - start) * 1000.0, msg
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_server_databases(datasource: dict, *, timeout: int | None = None) -> "list[str]":
    """datasource 서버의 DB 목록 (TASK-0205 §2.4 제품별 참조 DB 선택용). flag 무관 직결.

    MSSQL=`sys.databases`(시스템 DB 1-4 제외), MySQL=`SHOW DATABASES`(시스템 스키마 제외).
    예외는 그대로 raise(호출 endpoint 가 generic 메시지로 일반화 — host/pw 비유출). SSRF 검사는
    호출측(_ssrf_check_host)이 선행한다.
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    conn = None
    try:
        if engine == "mssql":
            if _pymssql is None:
                raise RuntimeError("pymssql_not_installed")
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8), timeout=int(timeout or 8),
            )
            cur = conn.cursor()
            cur.execute("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name")
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8), charset="utf8mb4", use_unicode=True,
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
        _sys = {"information_schema", "mysql", "performance_schema", "sys", "agent_memory"}
        out = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] and str(r[0]).lower() not in _sys]
        cur.close()
        return out
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_server_databases_classified(datasource: dict, *, timeout: int | None = None) -> "list[dict]":
    """TASK-0206 §3.4: DB 목록을 시스템/사용자 구분해 반환(`[{name, system}]`).

    DB-단위 접근 모델에서 UI 는 시스템 DB(MSSQL master/model/msdb/tempdb)를 고정칩(메타,
    항상 접근)으로, 사용자 DB 를 다중선택 allowlist 로 렌더한다. MSSQL 만 시스템 DB 를 포함
    (catalog 차원 — `sys`/`guest` 스키마는 dialect 가 차단). MySQL 은 DB==스키마라 시스템 스키마
    (information_schema/mysql/...) 는 메타데이터 경계로 계속 숨김(기존 동작 유지).
    예외는 그대로 raise(endpoint 가 일반화). SSRF 검사는 호출측 선행.
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    conn = None
    try:
        if engine == "mssql":
            if _pymssql is None:
                raise RuntimeError("pymssql_not_installed")
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8), timeout=int(timeout or 8),
            )
            cur = conn.cursor()
            # database_id 1-4 = master/tempdb/model/msdb (시스템). 그 외 = 사용자 DB.
            cur.execute(
                "SELECT name, CASE WHEN database_id <= 4 THEN 1 ELSE 0 END AS is_sys "
                "FROM sys.databases ORDER BY is_sys DESC, name"
            )
            out = []
            for r in (cur.fetchall() or []):
                if not r or not r[0]:
                    continue
                # tempdb 은 휘발성 — allowlist 의미 없음, 숨김.
                if str(r[0]).lower() == "tempdb":
                    continue
                out.append({"name": str(r[0]), "system": bool(int(r[1] or 0))})
            cur.close()
            return out
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8), charset="utf8mb4", use_unicode=True,
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
            _sys = {"information_schema", "mysql", "performance_schema", "sys", "agent_memory"}
            out = [
                {"name": str(r[0]), "system": False}
                for r in (cur.fetchall() or [])
                if r and r[0] and str(r[0]).lower() not in _sys
            ]
            cur.close()
            return out
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# MSSQL 시스템 스키마(분석 대상 아님) — insight-worker 의 dialect.system_schemas() 와 정합되게
# information_schema 열거에서 제외(db_* 고정 역할 + sys/guest/INFORMATION_SCHEMA).
_MSSQL_SYSTEM_SCHEMAS = frozenset({
    "sys", "guest", "information_schema",
    "db_owner", "db_accessadmin", "db_securityadmin", "db_ddladmin",
    "db_backupoperator", "db_datareader", "db_datawriter",
    "db_denydatareader", "db_denydatawriter",
})


def list_information_schema_tables(
    datasource: dict,
    *,
    schemas: "list[str] | None" = None,
    database: str | None = None,
    timeout: int | None = None,
    cap: int = 20000,
) -> "list[tuple[str, str]]":
    """datasource 의 information_schema 에서 (schema, table) 객체 목록을 **직결**로 열거.

    TASK-0223: 제품별 insight 분석 완료율의 분모(전체 객체 모수) 산출용. flag(AGENT_MULTI_DATASOURCE_ENABLED)
    **무관** 직결 — `list_server_databases_classified`/`probe_datasource` 와 동일 패턴(connect() 의 flag-gated
    datasource 경로를 우회). SSRF 검사는 호출측(_ssrf_check_host) 선행.

    - MySQL: 한 연결이 모든 DB 를 보므로 `schemas`(DB명들) 로 `TABLE_SCHEMA IN (...)` 필터. VIEW 포함
      (insight-worker 의 무필터 열거와 정합). 시스템 스키마는 호출측이 accessible DB 만 넘기므로 자연 배제.
    - MSSQL: DB==database 1개 컨텍스트라 `database`(1개) 로 연결해 그 DB 의 전체 user 스키마 table/view 열거.
      `INFORMATION_SCHEMA.TABLES` 는 현재 DB 한정이고 시스템 스키마(sys/db_*/guest)는 `_MSSQL_SYSTEM_SCHEMAS`
      로 제외(dialect.system_schemas() 정합).

    반환: `[(schema_name, table_name), ...]` (cap 개 제한). 예외는 그대로 raise(호출측이 graceful 처리).
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    conn = None
    try:
        if engine == "mssql":
            if _pymssql is None:
                raise RuntimeError("pymssql_not_installed")
            db_name = database or datasource.get("default_db") or "tempdb"
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                database=db_name,
                login_timeout=int(timeout or 8), timeout=int(timeout or 8),
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
            out: list[tuple[str, str]] = []
            for r in (cur.fetchall() or []):
                if not r or not r[0] or not r[1]:
                    continue
                if str(r[0]).strip().lower() in _MSSQL_SYSTEM_SCHEMAS:
                    continue
                out.append((str(r[0]), str(r[1])))
                if len(out) >= cap:
                    break
            cur.close()
            return out
        else:
            wanted = [str(s).strip() for s in (schemas or []) if s and str(s).strip()]
            if not wanted:
                return []
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8), charset="utf8mb4", use_unicode=True,
            )
            cur = conn.cursor()
            placeholders = ", ".join(["%s"] * len(wanted))
            # TASK-0249: 대소문자 무시 매칭. Linux MySQL(lower_case_table_names=0)은 DB명이 대소문자
            # 구분이라 등록 DB명(소문자 'dbcommon')이 실제 DB명('dbCommon')과 어긋나면 `TABLE_SCHEMA
            # IN (...)`이 0행을 반환해 완료율이 0/0으로 잘못 표기됐다. `LOWER(TABLE_SCHEMA)`로 비교해
            # 등록 케이스와 무관하게 매칭한다(반환값은 실제 케이스 유지 → 호출측이 소문자로 grouping).
            cur.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES "
                f"WHERE LOWER(TABLE_SCHEMA) IN ({placeholders}) "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                [w.lower() for w in wanted],
            )
            out = []
            for r in (cur.fetchall() or []):
                if not r or not r[0] or not r[1]:
                    continue
                out.append((str(r[0]), str(r[1])))
                if len(out) >= cap:
                    break
            cur.close()
            return out
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _collect_cursor_result(cur) -> list[tuple[str, Any, Any]]:
    # Stage 2 (P4): 크로스엔진 결과 수집. mysql.connector 전용 `cur.with_rows` 대신 DBAPI 표준
    # `cur.description`(result set 있으면 not None)으로 판정 → mysql.connector·pymssql 공통.
    # mysql.connector 도 SELECT 후 description 이 set 되고 비-row 문에서 None 이라 등가(회귀 0).
    result_sets = []
    has_rows = getattr(cur, "description", None) is not None
    if has_rows:
        rows = cur.fetchall()
        columns = [d[0] for d in (cur.description or [])]
        result_sets.append(("rows", columns, rows))
    else:
        rc = getattr(cur, "rowcount", None)
        if rc is not None and rc != -1:
            result_sets.append(("rowcount", rc, None))
    return result_sets


def execute_sql(conn, sql: str) -> tuple[list[tuple[str, Any, Any]], float]:
    cur = conn.cursor()
    start = time.time()
    results: list[tuple[str, Any, Any]] = []
    try:
        try:
            # TASK-0128 (#2): multi=False — 다중문 실행 차단(SQL injection 방어 심층).
            # LLM freeform SQL 은 sql_guard 가 이미 다중문 reject 하고, 구조화 도구는
            # 단일 statement 만 생성하므로 multi 비활성이 안전하다.
            iterator = cur.execute(sql, multi=False)
            if iterator is not None:
                for item in iterator:
                    results.extend(_collect_cursor_result(item))
            else:
                results.extend(_collect_cursor_result(cur))
        except TypeError:
            cur.execute(sql)
            results.extend(_collect_cursor_result(cur))
    finally:
        cur.close()
    return results, time.time() - start


def records_to_columns_rows(records: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    if not records:
        return [], []
    first = records[0]
    columns = [str(c) for c in first.keys()]
    rows = []
    for record in records:
        rows.append([record.get(c) for c in columns])
    return columns, rows


def summarize_mcp_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        if isinstance(result.get("data"), dict):
            data = result["data"]
            if isinstance(data.get("rows"), list):
                rows = data["rows"]
                return {"rows": len(rows), "sample": rows[:3]}
            if isinstance(data.get("results"), list):
                rows = data["results"]
                return {"rows": len(rows), "sample": rows[:3]}
            if isinstance(data.get("count"), int):
                return {"count": data["count"]}
        if "records" in result and isinstance(result["records"], list):
            records = result["records"]
            return {"records": len(records), "sample": records[:3]}
        if "results" in result and isinstance(result["results"], list):
            return {"result_sets": len(result["results"])}
        if "rowcount" in result:
            return {"rowcount": result["rowcount"]}
        if "status" in result:
            return {"status": result["status"]}
    return {"result": result}


# ─────────────────────────────────────────────────────────────────────────────
# TASK-0015 §2.1.3 M0: KB Postgres pgvector connection helper.
#
# M0 단계의 진입점. mysql.connector 와 공존하며 기존 코드 경로는 무영향.
# M2 dual-write phase 부터 `_pg_connect()` 가 write path 에 호출되고, M4 cutover
# 시점에 read path 도 본 helper 를 사용한다. M1 cycle 에서 `agent_kb_rw` /
# `agent_kb_ro` role 분리 + ADR-0021 작성 후 본 함수의 user/password 가 rw role 로
# 전환된다 (config.AGENT_KB_PG_USER 환경변수 갱신만으로 적용).
# ─────────────────────────────────────────────────────────────────────────────

def _pg_available() -> bool:
    """psycopg import + AGENT_KB_PG_* 환경변수 둘 다 갖춰져 있으면 True.

    M0 단계의 standalone 운영에서 호출자가 postgres backend 호출 가능 여부를
    싸게 확인하기 위한 helper. 본 함수는 connection 시도 안 함 (network 부담 0).
    """
    return (_psycopg is not None) and AGENT_KB_PG_ENABLED


def _pg_connect(database: str | None = None, autocommit: bool = True):
    """KB Postgres (pgvector/pgvector:pg16) 에 connection 을 연다.

    M0 단계: 호출자가 standalone 테스트 또는 `bin/kb-pg-healthcheck.sh` 에서 사용.
    실 KB read/write 는 M2+ phase 에서 본 함수를 통해 routing.

    Args:
        database: 대상 database. None 이면 AGENT_KB_PG_DB (default `agent_kb`) 사용.
        autocommit: psycopg3 default 는 autocommit=False. 본 helper 는 mysql.connector
                    의 default 동작 (autocommit=True) 과 일치시키기 위해 명시.

    Raises:
        RuntimeError: psycopg import 실패 또는 AGENT_KB_PG_* 환경변수 미설정 시.
                      M0 의 standalone 운영에서 본 RuntimeError 는 caller 가
                      mysql.connector path 로 fallback 하도록 신호. M4 cutover
                      이후 본 RuntimeError 는 KB 접근 차단을 의미하므로 healthcheck
                      에서 fail-loud.
        psycopg.OperationalError: connection 실패 (host unreachable, auth 실패 등).
    """
    if _psycopg is None:
        raise RuntimeError(
            f"psycopg not importable (M0 prerequisite missing). "
            f"requirements.txt 에 psycopg[binary] 가 설치되었는지 확인. "
            f"original error: {_PSYCOPG_IMPORT_ERR!r}"
        )
    if not AGENT_KB_PG_ENABLED:
        raise RuntimeError(
            "AGENT_KB_PG_HOST / AGENT_KB_PG_USER 미설정 (M0 prerequisite missing). "
            ".env 의 AGENT_KB_PG_* 변수가 채워졌는지 확인."
        )
    target_db = (database or AGENT_KB_PG_DB or "agent_kb")
    conninfo_parts = [
        f"host={AGENT_KB_PG_HOST}",
        f"port={AGENT_KB_PG_PORT}",
        f"dbname={target_db}",
        f"user={AGENT_KB_PG_USER}",
        f"password={AGENT_KB_PG_PASSWORD}",
        f"sslmode={AGENT_KB_PG_SSLMODE}",
        # TASK-0255: PG 도 control-plane — 연결 수립 상한을 bounded(기본 10s)로. 과거 300s.
        f"connect_timeout={_controlplane_connect_timeout()}",
        "application_name=agent_core_kb",
    ]
    conninfo = " ".join(conninfo_parts)
    conn = _psycopg.connect(conninfo)
    if autocommit:
        conn.autocommit = True
    return conn


def _pg_connect_ro(database: str | None = None, autocommit: bool = True):
    """REV-20260522-0012 B3 흡수 (M4 TASK-0024): read path least-privilege connection.

    `agent_kb_ro` role 로 connection 을 연다. ADR-0021 의 2-layer hybrid RBAC 정합 —
    read 는 read-only role 로, write 는 rw role 로 분리.

    AGENT_KB_PG_USER_RO / AGENT_KB_PG_PASSWORD_RO 가 미설정 시 RW 로 fallback (warning
    log) — backward-compat 보장 + 운영 환경에서 RO role 미배포 시 cutover 진행 가능.

    Raises:
        RuntimeError: AGENT_KB_PG_ENABLED 가 False 또는 psycopg 미설치.
    """
    if _psycopg is None:
        raise RuntimeError(
            f"psycopg not importable. original error: {_PSYCOPG_IMPORT_ERR!r}"
        )
    if not AGENT_KB_PG_ENABLED:
        raise RuntimeError("AGENT_KB_PG_HOST / AGENT_KB_PG_USER 미설정")

    ro_user = AGENT_KB_PG_USER_RO or AGENT_KB_PG_USER
    ro_pw = AGENT_KB_PG_PASSWORD_RO or AGENT_KB_PG_PASSWORD
    if not AGENT_KB_PG_USER_RO:
        import logging
        logging.getLogger("agent_core.db").warning(
            "kb_pg_ro_fallback_to_rw — AGENT_KB_PG_USER_RO 미설정, RW role 로 read path 진행. "
            "운영 환경에서는 .env 의 AGENT_KB_PG_USER_RO/AGENT_KB_PG_PASSWORD_RO 설정 권장 (ADR-0021)."
        )
    # T5-14: AGENT_KB_PG_HOST_RO 설정 시 replica 로 라우팅 (미설정=primary fallback).
    ro_host = AGENT_KB_PG_HOST_RO or AGENT_KB_PG_HOST
    ro_port = AGENT_KB_PG_PORT_RO or AGENT_KB_PG_PORT
    target_db = (database or AGENT_KB_PG_DB or "agent_kb")
    conninfo_parts = [
        f"host={ro_host}",
        f"port={ro_port}",
        f"dbname={target_db}",
        f"user={ro_user}",
        f"password={ro_pw}",
        f"sslmode={AGENT_KB_PG_SSLMODE}",
        # TASK-0255: PG read path 도 control-plane — bounded connect timeout(기본 10s). 과거 300s.
        f"connect_timeout={_controlplane_connect_timeout()}",
        "application_name=agent_core_kb_ro",
    ]
    conninfo = " ".join(conninfo_parts)
    conn = _psycopg.connect(conninfo)
    if autocommit:
        conn.autocommit = True
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# T4-12: KB 무효화 플래그 — LISTEN/NOTIFY 대용 공유 시계.
#
# 에이전트가 per-call 방식으로 connection 을 열어 LISTEN 을 유지할 수 없는 구조이므로,
# `kb_invalidations` 테이블에 channel 별 최신 write 시각을 기록한다.
#   - 쓰기 완료 시: _pg_mark_kb_invalidation(conn, "kb_global") 호출.
#   - 캐시 유효성 판단 시: _pg_check_kb_invalidation(channel) 으로 last epoch 반환.
# _is_refresh_due 에서 TTL 판단에 추가로 이 시각을 활용한다.
# ─────────────────────────────────────────────────────────────────────────────


def _pg_mark_kb_invalidation(conn, channel: str = "kb_global") -> None:
    """fact 쓰기 완료 후 kb_invalidations 에 invalidated_at 갱신."""
    channel = str(channel or "kb_global").strip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
INSERT INTO kb_invalidations (channel, invalidated_at)
VALUES (%s, now())
ON CONFLICT (channel) DO UPDATE SET invalidated_at = now()
                """,
                (channel,),
            )
        # NOTIFY 도 함께 발행 — 미래 persistent-listener 구현을 위한 groundwork.
        with conn.cursor() as cur:
            cur.execute("SELECT pg_notify(%s, %s)", (channel, "write"))
    except Exception:
        pass


def _pg_check_kb_invalidation(channel: str = "kb_global") -> float | None:
    """kb_invalidations 에서 해당 channel 의 invalidated_at (Unix timestamp) 반환.

    Returns: float epoch or None (table absent / channel not found / PG unavailable).
    """
    if not _pg_available():
        return None
    channel = str(channel or "kb_global").strip()
    conn = None
    try:
        conn = _pg_connect_ro()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXTRACT(EPOCH FROM invalidated_at) FROM kb_invalidations WHERE channel = %s",
                (channel,),
            )
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception:
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
