"""DB 기반 datasource 레지스트리 (TASK-0205, DESIGN-datasource-registry §2.3/§6/§7).

`.env`(legacy) + DB(`WebDatasources`) 병합 레지스트리. 소비처(agent_core.resolve, insight 순회,
admin API)가 **mem_conn 을 주입**해 호출(per-resolve — 멀티프로세스 정합·평문 password 무캐시, M2).
`db.connect` 는 이미 resolved dict 를 받으므로 변경 없음.

보안 계약:
- **password 평문 무캐시**(M2): 복호는 resolve 시점, 반환 dict 의 `password` 만(캐시는 DEK=키만).
- **`.env` 격리**(M5): DB datasource 복호 실패(KEK 부재 등)는 그 키만 skip — `.env` datasource 정상.
- **DB 우선 + fail-loud**(N1): 같은 키가 DB·env 양쪽이면 DB 우선 + 1회 warning 로그.
- 테이블 부재(워커 선기동 등)는 graceful — DB datasource 0개 취급, `.env` 폴백.
"""
from __future__ import annotations

import logging

from . import config as cfg
from . import cred_crypto

_log = logging.getLogger("datasources")

# DEK 캐시: KEK 로 unwrap 된 DEK(=키, password 아님)만 프로세스 메모리에. 평문 password 는 캐시 안 함.
_DEK_CACHE: "dict[int, bytes]" = {}
_CONFLICT_WARNED: "set[str]" = set()


# ── DEK 관리 (WebDatasourceKeys) ─────────────────────────────────────────────
def _fetch_dek_row(mem_conn, version: "int | None"):
    """version=None 이면 활성(IsActive=1) 최신, 아니면 해당 버전. (KeyVersion, DekWrapped, KekVersion)."""
    cur = mem_conn.cursor()
    try:
        if version is None:
            cur.execute(
                "SELECT KeyVersion, DekWrapped, KekVersion FROM WebDatasourceKeys "
                "WHERE IsActive=1 ORDER BY KeyVersion DESC LIMIT 1"
            )
        else:
            cur.execute(
                "SELECT KeyVersion, DekWrapped, KekVersion FROM WebDatasourceKeys WHERE KeyVersion=%s",
                (int(version),),
            )
        return cur.fetchone()
    finally:
        cur.close()


def get_dek(mem_conn, version: "int | None" = None) -> "tuple[int, bytes] | None":
    """활성(또는 지정) DEK 를 unwrap 해 (version, dek) 반환. 캐시(DEK 만). 실패 시 None."""
    row = None
    try:
        row = _fetch_dek_row(mem_conn, version)
    except Exception:
        return None  # 테이블 부재 등 graceful
    if not row:
        return None
    ver = int(row[0])
    if ver in _DEK_CACHE:
        return (ver, _DEK_CACHE[ver])
    try:
        dek = cred_crypto.unwrap_dek(str(row[1]), int(row[2]))
    except cred_crypto.CredCryptoError as exc:
        _log.error("dek_unwrap_failed version=%s err=%s — datasource 복호 불가(KEK 확인)", ver, exc)
        return None
    _DEK_CACHE[ver] = dek
    return (ver, dek)


def ensure_dek(mem_conn) -> "tuple[int, bytes] | None":
    """활성 DEK 보장 — 없으면 생성·wrap·저장. enc 불가(KEK 부재)면 None(신규 암호화 차단, fail-closed)."""
    existing = get_dek(mem_conn, None)
    if existing is not None:
        return existing
    kek_ver = cred_crypto.current_kek_version()
    if not cred_crypto.enc_available() or kek_ver is None:
        return None
    dek = cred_crypto.generate_dek()
    try:
        wrapped = cred_crypto.wrap_dek(dek, kek_ver)
    except cred_crypto.CredCryptoError:
        return None
    cur = mem_conn.cursor()
    try:
        # KeyVersion 은 단조 증가(다음 max+1). 동시생성 경합은 UNIQUE 로 1개만 성공 → 재조회.
        cur.execute("SELECT COALESCE(MAX(KeyVersion),0)+1 FROM WebDatasourceKeys")
        next_ver = int(cur.fetchone()[0])
        try:
            cur.execute(
                "INSERT INTO WebDatasourceKeys (KeyVersion, DekWrapped, KekVersion, IsActive) "
                "VALUES (%s,%s,%s,1)",
                (next_ver, wrapped, int(kek_ver)),
            )
            mem_conn.commit()
        except Exception:
            mem_conn.rollback()  # 경합 — 다른 프로세스가 먼저 생성, 재조회
        return get_dek(mem_conn, None)
    finally:
        cur.close()


# ── 레지스트리 (DB + .env 병합) ───────────────────────────────────────────────
def _row_to_ds(mem_conn, row) -> "dict | None":
    """WebDatasources row → datasource dict(password 복호 포함). 복호 실패 시 None(그 키만 skip)."""
    # row: (DatasourceKey, Engine, Host, Port, DbUser, PasswordEnc, DefaultDb, EncryptionVersion[, InsightEnabled])
    key = str(row[0]).strip().lower()
    password = ""
    enc = row[5]
    if enc:
        got = get_dek(mem_conn, int(row[7]) if row[7] else None)
        if got is None:
            _log.warning("datasource_decrypt_skipped key=%s — DEK 부재(KEK 확인). 이 키만 skip", key)
            return None
        try:
            password = cred_crypto.decrypt_password(got[1], str(enc), key)
        except cred_crypto.CredCryptoError as exc:
            _log.warning("datasource_decrypt_failed key=%s err=%s — 이 키만 skip", key, exc)
            return None
    return {
        "key": key,
        "engine": (str(row[1] or "mysql").strip().lower() or "mysql"),
        "host": str(row[2] or ""),
        "port": int(row[3] or cfg.DB_PORT),
        "user": str(row[4] or ""),
        "password": password,
        "default_db": (str(row[6]).strip() if row[6] else None),
        # TASK-0215: insight-worker 탐색 토글(컬럼 부재 구 스키마는 True 로 간주 — 기존 동작 보존).
        "insight_enabled": (bool(int(row[8])) if len(row) > 8 and row[8] is not None else True),
        "_source": "db",
    }


def _db_datasource(mem_conn, key: str) -> "dict | None":
    cur = mem_conn.cursor()
    try:
        cur.execute(
            "SELECT DatasourceKey, Engine, Host, Port, DbUser, PasswordEnc, DefaultDb, EncryptionVersion, InsightEnabled "
            "FROM WebDatasources WHERE DatasourceKey=%s AND IsActive=1 LIMIT 1",
            (str(key).strip().lower(),),
        )
        row = cur.fetchone()
    except Exception:
        return None  # 테이블 부재 graceful
    finally:
        cur.close()
    # row 가 8 컬럼(정상 WebDatasources) 아니면 None → .env 폴백(테이블 부재·stub conn 방어).
    if not row or len(row) < 8:
        return None
    return _row_to_ds(mem_conn, row)


def _all_db_datasources(mem_conn) -> "dict[str, dict]":
    cur = mem_conn.cursor()
    try:
        cur.execute(
            "SELECT DatasourceKey, Engine, Host, Port, DbUser, PasswordEnc, DefaultDb, EncryptionVersion, InsightEnabled "
            "FROM WebDatasources WHERE IsActive=1"
        )
        rows = cur.fetchall() or []
    except Exception:
        return {}  # 테이블 부재 graceful
    finally:
        cur.close()
    out: dict[str, dict] = {}
    for row in rows:
        ds = _row_to_ds(mem_conn, row)
        if ds:
            out[ds["key"]] = ds
    return out


def _warn_conflict(key: str) -> None:
    if key not in _CONFLICT_WARNED:
        _CONFLICT_WARNED.add(key)
        _log.warning("datasource_key_conflict key=%s — DB 레코드가 .env 를 override 합니다(DB 우선)", key)


def resolve(mem_conn, key: str) -> "dict | None":
    """단일 datasource 해석(DB 우선, .env 폴백). password 복호 포함. 미등록/복호실패 시 None.

    mem_conn 없으면(None) .env 만(레거시 경로 호환).
    """
    k = str(key or "").strip().lower()
    if not k:
        return None
    if mem_conn is not None:
        db_ds = _db_datasource(mem_conn, k)
        if db_ds is not None:
            if k in (cfg.DATASOURCES or {}):
                _warn_conflict(k)
            return db_ds
    return (cfg.DATASOURCES or {}).get(k)  # .env 레거시 폴백(M5: DB 실패해도 여기 도달)


def all_datasources(mem_conn) -> "dict[str, dict]":
    """DB(활성) + .env 병합. DB 우선. insight 순회·admin 용. password 포함(노출 시 datasource_public)."""
    merged: dict[str, dict] = dict(cfg.DATASOURCES or {})  # .env 먼저
    if mem_conn is not None:
        for k, ds in _all_db_datasources(mem_conn).items():
            if k in merged:
                _warn_conflict(k)
            merged[k] = ds  # DB 우선
    return merged
