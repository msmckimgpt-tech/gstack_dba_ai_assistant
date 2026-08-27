"""feature-0012 ITEM-10 p8 — 웹 테이블/시드 부트스트랩 오케스트레이터 (비-라우트 모듈).

app.py 에서 이동. startup 기계(_bootstrap_memory_runtime 계열, app 잔류·KEEP)가 호출하는
스키마 보증/시드 계층 — `_` 접두라 register_all 제외. app 전역은 `app.X` 동적 참조,
`global _WEB_TABLES_READY` 쓰기는 `app._WEB_TABLES_READY = ...` 속성 대입으로 등가 변환
(모듈 전역 대입과 동일 — app 잔류 독자가 같은 플래그를 본다).
"""

import logging
import os

import app  # noqa: F401 — app.X 동적 참조(꼬리 rebind 시점 import — 순환 안전)


def _ensure_web_product_datasources_schema(conn) -> None:
    """TASK-0228 (멀티 datasource 1:N): 제품 ↔ 여러 datasource 바인딩 join 테이블 + 접근DB 의
    datasource 차원화. 멱등 CREATE/ALTER + 레거시(`WebProducts.DatasourceKey` 단일 바인딩) 이전.

    **하위호환 전략 (blast-radius 0)**: `WebProducts.DatasourceKey` 는 **primary datasource** 포인터로
    그대로 유지된다(기존 `_resolve_product_datasource`·`_product_has_datasource`·insight `WHERE
    p.DatasourceKey=` 경로 무수정 동작). `WebProductDatasources` 는 primary 를 포함한 **전체 바인딩**을
    담는다(primary 는 IsPrimary=1). 둘은 동기화된다 — 단일 바인딩 제품은 기존과 100% 동일하게 동작하고,
    1:N 은 join 테이블을 읽는 신규 경로만 사용한다.

    **접근 DB 차원화**: `WebProductDatabases` 에 `DatasourceKey` 를 추가해 접근가능 DB 목록을
    (product, datasource) 단위로 분리한다 — datasource A 의 스키마가 datasource B 컨텍스트로 새지
    않도록(보안 경계). 레거시 행(DatasourceKey='')은 제품의 primary datasource 로 backfill 한다.
    PK 를 `(ProductId, SchemaName)` → `(ProductId, DatasourceKey, SchemaName)` 로 이전해 같은 스키마명이
    서로 다른 datasource 에 공존할 수 있게 한다(MSSQL DB명 충돌 대비).
    """
    cur = conn.cursor()
    try:
        # 1) 제품 ↔ datasource 다대다 바인딩 (primary 포함, IsPrimary=1).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatasources (
                ProductId BIGINT NOT NULL,
                DatasourceKey VARCHAR(64) NOT NULL,
                SortOrder INT NOT NULL DEFAULT 100,
                IsPrimary TINYINT(1) NOT NULL DEFAULT 0,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ProductId, DatasourceKey),
                INDEX IX_WebProductDatasources_Ds (DatasourceKey)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # 2) 레거시 단일 바인딩(WebProducts.DatasourceKey)을 join 테이블로 1회 이전(primary 로 마킹).
        #    멱등: INSERT IGNORE — 이미 있는 (product, ds) 는 skip.
        try:
            cur.execute(
                """
                INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary)
                SELECT Id, LOWER(DatasourceKey), 0, 1 FROM WebProducts
                WHERE DatasourceKey IS NOT NULL AND TRIM(DatasourceKey) <> ''
                """
            )
        except Exception:
            pass
        # 3) WebProductDatabases 에 DatasourceKey 차원 추가(접근DB 를 datasource 별로 격리).
        #    REV-0228 MAJOR-1: 컬럼 존재를 먼저 확인해 멱등 보장 + 추가 실패를 가시화(silent pass 금지).
        #    이 컬럼은 멀티 datasource 격리의 핵심 — 부재 시 런타임이 fail-closed(접근 0) 하므로
        #    누출은 없으나, 운영자가 마이그레이션 비정상을 알 수 있어야 한다.
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='DatasourceKey'"
        )
        _has_dsk_col = int((cur.fetchone() or [0])[0]) > 0
        if not _has_dsk_col:
            try:
                cur.execute(
                    "ALTER TABLE WebProductDatabases ADD COLUMN DatasourceKey VARCHAR(64) NOT NULL DEFAULT ''"
                )
                _has_dsk_col = True
            except Exception as _alter_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases.DatasourceKey 컬럼 추가 실패 — 멀티 datasource 격리 "
                    "비활성(런타임 fail-closed). 운영자 수동 ALTER 필요: %r", _alter_exc,
                )
        # 4) 레거시 접근DB 행(DatasourceKey='')을 제품의 primary datasource 키로 backfill.
        #    제품이 datasource 미바인딩(NULL)이면 ''(레거시 단일 MySQL) 유지 — 그 행은 primary=None 매칭.
        #    컬럼이 존재할 때만(REV-0228 MAJOR-1: 컬럼 추가 실패 시 backfill/PK 이전 모두 skip).
        if _has_dsk_col:
            try:
                cur.execute(
                    """
                    UPDATE WebProductDatabases pd
                    JOIN WebProducts p ON p.Id = pd.ProductId
                    SET pd.DatasourceKey = LOWER(p.DatasourceKey)
                    WHERE pd.DatasourceKey = ''
                      AND p.DatasourceKey IS NOT NULL AND TRIM(p.DatasourceKey) <> ''
                    """
                )
            except Exception as _bf_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases.DatasourceKey backfill 실패: %r", _bf_exc,
                )
            # 5) PK 이전: (ProductId, SchemaName) → (ProductId, DatasourceKey, SchemaName). 멱등 가드 —
            #    information_schema 로 현재 PK 컬럼 수를 확인해 미이전 시에만 DROP/ADD(재실행 방지).
            #    DROP+ADD 는 단일 ALTER 라 InnoDB 에서 atomic — 부분 적용 없음. 실패는 loud 로깅(silent 금지).
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'WebProductDatabases'
                      AND INDEX_NAME = 'PRIMARY'
                    """
                )
                _pk_cols = int((cur.fetchone() or [0])[0])
                if _pk_cols < 3:
                    cur.execute(
                        "ALTER TABLE WebProductDatabases DROP PRIMARY KEY, "
                        "ADD PRIMARY KEY (ProductId, DatasourceKey, SchemaName)"
                    )
            except Exception as _pk_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases PK 이전 실패 — 같은 스키마명이 다른 datasource 에 "
                    "공존 불가(중복 PK). 운영자 확인 필요: %r", _pk_exc,
                )
        # 6) TASK-0277 (라벨/키 분리): 제품 바인딩의 canonical 식별자를 renameable 라벨(DatasourceKey)에서
        #    **stable surrogate `WebDatasources.Id`** 로 이전한다. 라벨 rename 시에도 Id 는 불변이라 바인딩이
        #    고아되지 않는다(근본수정). 추가형(PK 무변경) — `DatasourceId` 컬럼을 3 테이블에 멱등 추가 + 현재
        #    DatasourceKey 로 1회 backfill + 인덱스. 기존 키 컬럼은 denormalized 라벨 캐시로 잔존(rename 시
        #    Id 구동 cascade 로 신선도 유지 — admin_update_datasource). 컬럼 drop·PK 이전은 멀티이미지 배포
        #    안전 확인 후 차기 cycle (TASK.md 이월).
        _dsid_targets = [
            # (table, key_col_expr_for_join, extra_where)
            ("WebProducts", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
            ("WebProductDatasources", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
            ("WebProductDatabases", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
        ]
        for _tbl, _keyexpr, _extra in _dsid_targets:
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND COLUMN_NAME='DatasourceId'",
                    (_tbl,),
                )
                _has_id = int((cur.fetchone() or [0])[0]) > 0
                if not _has_id:
                    cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN DatasourceId BIGINT NULL")
                # backfill: 현재 라벨로 매칭되는 WebDatasources.Id 를 1회 채운다(이미 채워진 행은 건드리지 않음).
                cur.execute(
                    f"UPDATE {_tbl} t JOIN WebDatasources d ON LOWER(d.DatasourceKey) = {_keyexpr} "
                    f"SET t.DatasourceId = d.Id WHERE t.DatasourceId IS NULL AND ({_extra})"
                )
                # 인덱스(멱등 — 존재 확인 후 생성). 조회/cascade 가 Id 로 매칭.
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND INDEX_NAME=%s",
                    (_tbl, f"IX_{_tbl}_DsId"),
                )
                if int((cur.fetchone() or [0])[0]) == 0:
                    cur.execute(f"CREATE INDEX IX_{_tbl}_DsId ON {_tbl} (DatasourceId)")
            except Exception as _dsid_exc:
                logging.getLogger(__name__).error(
                    "[ds-id] %s.DatasourceId 추가/backfill/인덱스 실패 — 라벨 rename 안정성 저하 가능 "
                    "(런타임은 키 캐시 cascade 로 폴백). 운영자 확인 필요: %r", _tbl, _dsid_exc,
                )
        conn.commit()
    finally:
        cur.close()

def _seed_main_mysql_datasource(conn) -> None:
    """TASK-0206: 데이터 MySQL(.env AGENT_DATA_DB_*) 을 편집가능 데이터소스로 1회 시드.

    이제 제품 접근 데이터는 데이터소스에 종속된다. 기존엔 `WebProducts.DatasourceKey` NULL =
    데이터 MySQL 암묵 접근이었으나, 이를 명시 데이터소스로 승격하고 NULL 바인딩 제품을 일괄
    해시 키 datasource 로 바인딩(기존 접근 보존; DESIGN §3.1·§5). 멱등 — KEK 미설정/자격부재/이미존재 시 skip.

    레거시 `main_mysql` 키 마이그레이션: 이미 `main_mysql` 로 등록된 항목이 있으면 해시 키로 rename 하고
    `WebProducts.DatasourceKey` 참조도 일괄 업데이트한다(운영 연속성 보장).
    """
    try:
        from modules import cred_crypto as _cc
        from shared import datasources as _dsr
    except Exception:
        return
    if not _cc.enc_available():
        return  # KEK 미설정 — 암호화 불가, 시드 보류(운영자가 KEK 설정 후 재부팅 시 시드)
    user = os.getenv("AGENT_DATA_DB_USER", "").strip()
    password = os.getenv("AGENT_DATA_DB_PASSWORD", "")
    if not user:
        return  # 데이터 MySQL 자격 미구성 — 시드 대상 아님
    # 키를 엔진+호스트+포트 해시로 결정한다.
    key = app._generate_datasource_key("mysql", app.DB_HOST, int(app.DB_PORT))
    legacy_key = "main_mysql"
    cur = conn.cursor()
    try:
        # 레거시 `main_mysql` 키가 존재하면 해시 키로 rename (운영 연속성 보장).
        cur.execute(
            "SELECT PasswordEnc, EncryptionVersion FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
            (legacy_key,),
        )
        legacy_row = cur.fetchone()
        if legacy_row:
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,))
            if not cur.fetchone():
                # 해시 키 미존재 → rename.
                # PasswordEnc는 AAD=DatasourceKey로 암호화되어 있어 키 rename 시 재암호화 필요.
                new_pw_enc = legacy_row[0]
                new_enc_ver = legacy_row[1]
                got = _dsr.ensure_dek(conn)
                if got is not None:
                    ver, dek = got
                    try:
                        old_plain = _cc.decrypt_password(dek, legacy_row[0], legacy_key) if legacy_row[0] else None
                        if old_plain is not None:
                            new_pw_enc = _cc.encrypt_password(dek, old_plain, key)
                            new_enc_ver = int(ver)
                    except Exception:
                        pass  # 복호 실패 시 기존 암호문 유지(연결 테스트 실패로 드러남)
                cur.execute(
                    "UPDATE WebDatasources SET DatasourceKey=%s, PasswordEnc=%s, EncryptionVersion=%s"
                    " WHERE DatasourceKey=%s",
                    (key, new_pw_enc, new_enc_ver, legacy_key),
                )
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s WHERE DatasourceKey=%s",
                    (key, legacy_key),
                )
                # TASK-0277: 바인딩 join/접근DB 의 레거시 main_mysql 키도 cascade(완전 cascade — 고아 방지).
                for _bt in ("WebProductDatasources", "WebProductDatabases"):
                    try:
                        cur.execute(f"UPDATE {_bt} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s", (key, legacy_key))
                    except Exception:
                        pass
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] main_mysql → %s 키 마이그레이션 완료 (패스워드 재암호화)", key,
                    )
                except Exception:
                    pass
            else:
                # 해시 키가 이미 존재(수동 생성 등) → 레거시 제품 바인딩만 업데이트
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s WHERE DatasourceKey=%s",
                    (key, legacy_key),
                )
                # TASK-0277: 바인딩 join/접근DB 의 레거시 키도 cascade(완전 cascade — 고아 방지).
                for _bt in ("WebProductDatasources", "WebProductDatabases"):
                    try:
                        cur.execute(f"UPDATE {_bt} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s", (key, legacy_key))
                    except Exception:
                        pass
                cur.execute("DELETE FROM WebDatasources WHERE DatasourceKey=%s", (legacy_key,))
        else:
            # main_mysql 없음 → 해시 키가 이미 rename됐을 수 있음.
            # PasswordEnc AAD 가 구 키 이름으로 암호화됐을 경우 복호 실패가 발생하므로 검증 후 재암호화.
            cur.execute(
                "SELECT PasswordEnc, EncryptionVersion FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
                (key,),
            )
            hash_row = cur.fetchone()
            if hash_row and hash_row[0]:
                got = _dsr.ensure_dek(conn)
                if got is not None:
                    ver, dek = got
                    try:
                        _cc.decrypt_password(dek, hash_row[0], key)
                        # 복호 성공 → AAD 정합, 재암호화 불필요.
                    except Exception:
                        # 복호 실패 → 구 AAD(main_mysql)로 재시도 후 새 키 AAD로 재암호화.
                        try:
                            plain = _cc.decrypt_password(dek, hash_row[0], legacy_key)
                            new_pw_enc = _cc.encrypt_password(dek, plain, key)
                            cur.execute(
                                "UPDATE WebDatasources SET PasswordEnc=%s, EncryptionVersion=%s"
                                " WHERE DatasourceKey=%s",
                                (new_pw_enc, int(ver), key),
                            )
                            try:
                                logging.getLogger(__name__).info(
                                    "[ds-seed] %s PasswordEnc AAD 재정렬 완료 (main_mysql → %s)", key, key,
                                )
                            except Exception:
                                pass
                        except Exception:
                            pass  # 복호 실패 — 패스워드를 모르므로 수동 재입력 필요

        # TASK-0222/0224: DatasourceKey 는 admin rename 가능한 단순 라벨(TASK-0216/0219) — 해시 키 부재가
        # "미시드"를 뜻하지 않는다. 운영자가 데이터 MySQL datasource 를 다른 라벨(mysql_local)로 rename 하면
        # 해시 라벨은 없지만 같은 엔드포인트(engine=mysql, host=app.DB_HOST, port=app.DB_PORT)의 활성 datasource 가
        # 이미 존재한다. 이때 해시 라벨로 INSERT 하면 같은 엔드포인트에 고아 중복 행이 재생성된다(rename 무력화).
        # 정책(엔드포인트=신원):
        #   - 같은 엔드포인트의 **다른 라벨** datasource 가 존재하면 그것을 canonical 로 채택(중복 INSERT 방지).
        #   - 추가로, 해시 라벨이 **시드 자동생성 고아**(UpdatedByAccountId IS NULL = 시드가 만든 것 + 제품 바인딩 0)
        #     로 존재하면 **능동 정리**(self-heal, TASK-0224) — 동시세션의 구버전/스테일 배포가 재생성한 잔재를
        #     fix 보유 web 부팅 시 제거. **운영자가 콘솔로 미리 세팅한 datasource(UpdatedByAccountId 有)는
        #     제품 미연결이어도 절대 삭제하지 않는다**(시드 INSERT 는 UpdatedByAccountId=NULL, admin_create 는 actor.id).
        #   - 해시 라벨에 제품이 바인딩됐거나(bound>0) 운영자 생성이면 보존(삭제·채택 안 함).
        cur.execute(
            "SELECT DatasourceKey FROM WebDatasources "
            "WHERE Engine='mysql' AND LOWER(Host)=LOWER(%s) AND Port=%s AND IsActive=1 AND DatasourceKey<>%s "
            "ORDER BY Id LIMIT 1",
            (app.DB_HOST, int(app.DB_PORT), key),
        )
        _ep_row = cur.fetchone()
        if _ep_row and _ep_row[0]:
            _other_label = str(_ep_row[0]).strip()
            cur.execute(
                "SELECT UpdatedByAccountId FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,)
            )
            _hr = cur.fetchone()
            _hash_present = _hr is not None
            _seed_created = _hash_present and (_hr[0] is None)  # 시드 자동생성(UpdatedByAccountId IS NULL)
            _bound = 0
            if _hash_present:
                cur.execute("SELECT COUNT(*) FROM WebProducts WHERE DatasourceKey=%s", (key,))
                _bc = cur.fetchone()
                _bound = int(_bc[0]) if _bc and _bc[0] is not None else 0
            # self-heal: **시드 자동생성 + 제품 0** 인 고아 해시키만 정리(운영자 생성/바인딩 datasource 절대 미삭제).
            if _seed_created and _bound == 0:
                cur.execute(
                    "DELETE FROM WebDatasources WHERE DatasourceKey=%s AND UpdatedByAccountId IS NULL", (key,)
                )
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] 시드-고아 해시키 '%s' 정리(UpdatedByAccountId NULL·제품 0, 라벨 '%s' 존재) — self-heal TASK-0224",
                        key, _other_label,
                    )
                except Exception:
                    pass
            # 라벨 채택(중복 INSERT 방지): 해시키가 제품 바인딩됐거나 운영자 생성이면 그대로 두고(보존), 그 외엔 라벨 채택.
            if not (_hash_present and (_bound > 0 or not _seed_created)):
                key = _other_label
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] 동일 엔드포인트(%s:%s) 데이터소스 '%s' 채택 — 해시키 신규 시드 skip(라벨 보존, TASK-0222)",
                        app.DB_HOST, app.DB_PORT, key,
                    )
                except Exception:
                    pass

        cur.execute(
            "SELECT Host, DbUser, IsActive, Engine, Port FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
            (key,),
        )
        row = cur.fetchone()
        exists = row is not None
        seeded_now = False
        if not exists:
            got = _dsr.ensure_dek(conn)
            if got is None:
                return
            ver, dek = got
            try:
                pw_enc = _cc.encrypt_password(dek, password, key) if password else None
            except Exception:
                return
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,'mysql',%s,%s,%s,%s,NULL,%s,1,NULL)",
                (key, app.DB_HOST, int(app.DB_PORT), user, pw_enc, int(ver)),
            )
            seeded_now = True
            try:
                logging.getLogger(__name__).info("[ds-seed] 데이터소스 시드 완료 key=%s (host=%s)", key, app.DB_HOST)
            except Exception:
                pass
        # re-gate MAJOR7: NULL/빈 바인딩 제품 → main_mysql 일괄 마이그레이션은 **main_mysql 이 실제 데이터
        # MySQL(.env 좌표)을 가리킬 때만** 수행. 운영자가 main_mysql 을 다른 호스트로 재설정했으면 일괄 바인딩이
        # 의도치 않게 접근을 부여/박탈하므로 skip. (방금 시드한 경우는 좌표가 .env 와 일치하므로 항상 안전.)
        migrate_ok = seeded_now
        if exists and row is not None:
            r_host = (str(row[0]).strip().lower() if row[0] else "")
            r_user = (str(row[1]).strip() if len(row) > 1 and row[1] else "")
            r_active = (int(row[2]) if len(row) > 2 and row[2] is not None else 1)
            r_engine = (str(row[3]).strip().lower() if len(row) > 3 and row[3] else "mysql")
            r_port = (int(row[4]) if len(row) > 4 and row[4] is not None else int(app.DB_PORT))
            # re-gate MAJOR7(2차): host/user 뿐 아니라 engine='mysql'·port 도 일치해야 동일 데이터 MySQL 로 간주
            # (동일 host/user 의 다른 포트·MSSQL datasource 에 NULL 제품 오바인딩 차단).
            migrate_ok = (
                r_host == str(app.DB_HOST).strip().lower()
                and r_user == user
                and r_active == 1
                and r_engine == "mysql"
                and r_port == int(app.DB_PORT)
            )
            if not migrate_ok:
                logging.getLogger(__name__).warning(
                    "[ds-seed] main_mysql 이 데이터 MySQL(.env)과 불일치(host=%s user=%s engine=%s port=%s active=%s) — "
                    "NULL 제품 일괄 바인딩 skip(운영자 관리 데이터소스로 간주)",
                    r_host, r_user, r_engine, r_port, r_active,
                )
        if migrate_ok:
            try:
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s "
                    "WHERE DatasourceKey IS NULL OR DatasourceKey=''",
                    (key,),
                )
            except Exception:
                pass
    except Exception:
        # 시드 실패는 부팅을 막지 않는다(레지스트리는 .env fallback 보유)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_tables():
    """Create auth/account tables and normalize conversation ownership."""
    if app._WEB_TABLES_READY:
        return
    conn = app._open_memory_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAccounts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(64) NOT NULL UNIQUE,
                Role VARCHAR(32) NOT NULL DEFAULT '',
                PasswordHash VARCHAR(255) NOT NULL,
                CanSendRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanCancelRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanFinalizeRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanDeleteConversation TINYINT(1) NOT NULL DEFAULT 0,
                CanClearConversations TINYINT(1) NOT NULL DEFAULT 0,
                RoleId BIGINT NULL,
                LastConversationId VARCHAR(128) NULL,
                ApprovedByAccountId BIGINT NULL,
                ApprovedAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastLoginAt DATETIME NULL,
                IsActive TINYINT(1) DEFAULT 1,
                DeletedAt DATETIME NULL,
                DeletedByAccountId BIGINT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN RoleId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN DeletedAt DATETIME NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN DeletedByAccountId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IX_WebAccounts_RoleId ON WebAccounts (RoleId)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IX_WebAccounts_DeletedAt ON WebAccounts (DeletedAt)")
        except Exception:
            pass
        # TASK-0047: 사용자별 직전 Product 선호 (재로그인 시 복원에 사용).
        # ProductPrefMode: 'auto' | 'pinned' | NULL(미설정 — 서버 default 적용).
        # ProductPrefPinnedId: pinned 일 때만 의미 있고, auto/NULL 일 때는 무시한다.
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN ProductPrefMode VARCHAR(8) NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN ProductPrefPinnedId BIGINT NULL")
        except Exception:
            pass
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0092): 관리자 비밀번호 reset 후 다음 로그인 시
        # 강제 변경 플래그. 기본 0 (false). idempotent ALTER.
        try:
            cur.execute(
                "ALTER TABLE WebAccounts ADD COLUMN MustChangePassword TINYINT(1) NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        # TASK-0268: 프로필 아바타 이미지 — MinIO object key (NULL=미설정 → 프론트 Identicon 폴백).
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN AvatarObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebPermissions (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Code VARCHAR(128) NOT NULL UNIQUE,
                Label VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                GroupName VARCHAR(32) NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # TASK-0052 Phase 1B: WebPermissions 의 IsDynamic / ProductId 컬럼을 helper 로 보장 (slow path).
        # 같은 helper 가 _ensure_seed_catchup (fast path) 에서도 호출되어 기존 배포에 ALTER 적용.
        app._ensure_dynamic_permissions_schema(conn)
        # TASK-0205: DB 기반 datasource 레지스트리 테이블 (slow path).
        app._ensure_web_datasources_schema(conn)
        # TASK-0206: 데이터 MySQL 데이터소스 시드 + NULL 바인딩 마이그레이션 (slow path).
        _seed_main_mysql_datasource(conn)
        # TASK-0206: 구 MSSQL 제품(참조 DB)을 DB-단위 접근목록으로 일회성 이전 (slow path).
        app._migrate_mssql_products_to_db_level(conn)
        # TASK-0211: .env 분석 데이터소스(DS_*)를 DB 레지스트리로 이전 (slow path).
        app._migrate_env_datasources_to_db(conn)
        # TASK-0228 (멀티 datasource 1:N): 제품 ↔ 여러 datasource join 테이블 + 접근DB 차원화 (slow path).
        # WebProducts/WebProductDatabases 가 위에서 보장된 뒤 실행돼야 한다(ALTER/INSERT 의존).
        _ensure_web_product_datasources_schema(conn)
        # TASK-20260618T044318: 제품 DB allowlist 정규식 규칙 + pending + Source/RuleId (slow path).
        #   WebProductDatabases(DatasourceKey 포함)·WebProducts 가 보장된 뒤 실행돼야 한다.
        app._ensure_web_product_db_rules_schema(conn)
        # REQ-20260514-0001: 공유 링크 테이블 보장 (slow path).
        app._ensure_web_conversation_shares_schema(conn)
        # TASK-0094 Sprint 1 Phase 2 (R-F7): share-policy version column (slow path).
        app._ensure_web_share_links_policy_version_column(conn)
        # TASK-20260619T012028-share-link-expiry (SECURITY.md §7.2): 공유 링크 만료 column (slow path).
        app._ensure_web_share_links_expiry_column(conn)
        app._ensure_web_share_links_joinable_column(conn)  # feature-0009: 공유 링크 참여 허용 컬럼
        app._ensure_web_share_links_floor_column(conn)  # share-visibility-window: 하단 경계("여기부터 공유")
        # TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 컬럼 (slow path).
        app._ensure_login_lockout_schema(conn)
        # TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 사용량 한도 테이블 (slow path).
        app._ensure_llm_quota_schema(conn)
        # TASK-20260619T034522-oauth-google-foundation (REQ-20260619-0328): Google OAuth 신원 매핑 컬럼 (slow path).
        app._ensure_oauth_identity_schema(conn)
        # TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA TOTP 테이블 (slow path).
        app._ensure_web_account_totp_schema(conn)
        # feature-0023 (REQ-20260722-conversation-api-access): Bearer API 토큰 테이블 (slow path).
        app._ensure_web_api_tokens_schema(conn)
        # feature-0041 (REQ-20260812-external-ai-tool-surface): OAuth AS 저장 계약 3종 (slow path).
        app._ensure_oauth_client_schema(conn)
        # TASK-20260623T190000-gdrive-foundation (feature-0010): 계정별 Google Drive 토큰 테이블 (slow path).
        app._ensure_web_gdrive_tokens_schema(conn)
        # TASK-0094 Sprint 1 Phase 2: 첨부 metadata + sandbox mapping +
        # derived join + provider files lifecycle 4 신규 테이블 (slow path).
        app._ensure_web_conversation_attachments_schema(conn)
        app._ensure_web_conversation_attachments_sandbox_schemas_schema(conn)
        app._ensure_web_attachment_derived_messages_schema(conn)
        app._ensure_web_conversation_attachment_provider_files_schema(conn)
        # TASK-0274: 첨부 버전 관리 컬럼 보장 (slow path — 기존 배포 첨부 테이블에 컬럼 backfill).
        app._ensure_attachment_version_schema(conn)
        # REQ-20260519-0001 (TASK-0073, Phase A0): 전체 행위 audit log 테이블 보장 (slow path).
        app._ensure_web_audit_events_schema(conn)
        # TASK-20260619T023922-audit-tamper-evidence (보안 ③): 감사 해시 체인 컬럼/체크포인트 (slow path).
        app._ensure_web_audit_chain_schema(conn)
        # REQ-20260520-0001 (TASK-0086): migration helper 는 rollback window 동안 보존 (slow path).
        # WebAccountActivity 부재 시 SHOW TABLES check 로 silent skip.
        try:
            app._migrate_web_account_activity_to_audit(conn)
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebRoles (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                RoleKey VARCHAR(64) NOT NULL UNIQUE,
                Name VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                IsDefaultSignup TINYINT(1) NOT NULL DEFAULT 0,
                IconObjectKey VARCHAR(512) NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebRolePermissions (
                RoleId BIGINT NOT NULL,
                PermissionId BIGINT NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (RoleId, PermissionId),
                INDEX IX_WebRolePermissions_Permission (PermissionId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAccountPermissionOverrides (
                AccountId BIGINT NOT NULL,
                PermissionId BIGINT NOT NULL,
                OverrideValue VARCHAR(16) NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (AccountId, PermissionId),
                INDEX IX_WebAccountPermissionOverrides_Permission (PermissionId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAuthSessions (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AccountId BIGINT NOT NULL,
                SessionTokenHash CHAR(64) NOT NULL UNIQUE,
                RemoteAddr VARCHAR(64) NULL,
                UserAgent VARCHAR(255) NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastSeenAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                ExpiresAt DATETIME NOT NULL,
                IsRevoked TINYINT(1) NOT NULL DEFAULT 0,
                INDEX IX_WebAuthSessions_Account (AccountId),
                INDEX IX_WebAuthSessions_Expires (ExpiresAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") != "postgres":
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS AgentCoreConversations (
                conversation_id VARCHAR(128) PRIMARY KEY,
                topic VARCHAR(256) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            )
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN owner_account_id BIGINT NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN owner_assigned_at DATETIME NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "CREATE INDEX IX_AgentCoreConversations_Owner ON AgentCoreConversations (owner_account_id)"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN product_id BIGINT NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "CREATE INDEX IX_AgentCoreConversations_Product ON AgentCoreConversations (product_id)"
                )
            except Exception:
                pass
            # TASK-0047: 대화별 product_mode ('pinned'|'auto') — auto 는 일반 대화 모드.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations "
                    "ADD COLUMN product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'"
                )
            except Exception:
                pass
            # TASK-0248: 참조 제품 삭제 시 대화 차단. blocked_at 이 NULL 이 아니면 차단
            # (이력 열람 가능, 진행 불가). PG 정본(agent_runtime.core_conversations)의
            # MySQL 폴백 등가 — production 은 PG 라 보통 미경유하나 parity 유지.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN blocked_at DATETIME NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN blocked_reason VARCHAR(256) NULL"
                )
            except Exception:
                pass
            # TASK-0273: "삭제"→soft-archive. archived_at 이 NULL 이 아니면 보관(목록 숨김+진행
            # 차단, 데이터 보존). PG 정본(alembic 0007)의 MySQL 폴백 parity.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN archived_at DATETIME NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN archived_by_account_id BIGINT NULL"
                )
            except Exception:
                pass
            # feature-0009 gc-group-authz-flag: 그룹 대화 영구 플래그. PG 정본(alembic 0016)의
            # MySQL 폴백 parity (production 은 PG 라 보통 미경유). 공유 생성/join 시 1 로 set.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN is_group TINYINT(1) NOT NULL DEFAULT 0"
                )
            except Exception:
                pass
            # feature-0009-group-conversation (TASK-20260619T023140): 그룹 대화 — MySQL parity.
            # core_messages/멤버십 정본은 PG(agent_runtime). 본 블록은 READ_BACKEND != postgres
            # 레거시 경로 parity 유지(try/except 멱등). production(PG)에서는 본 가드가 skip 된다.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreMessages ADD COLUMN sender_account_id BIGINT NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreMessages ADD COLUMN thread_root_message_id BIGINT NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS AgentCoreConversationMembers ("
                    " conversation_id VARCHAR(128) NOT NULL,"
                    " account_id BIGINT NOT NULL,"
                    " role VARCHAR(16) NOT NULL DEFAULT 'member',"
                    " joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    " invited_by_account_id BIGINT NULL,"
                    " PRIMARY KEY (conversation_id, account_id),"
                    " INDEX IX_AgentCoreConversationMembers_Account (account_id)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
            except Exception:
                pass
            # feature-0009 gc-unread-badge: 멤버별 안 읽은 메세지 커서. PG 정본(alembic 0019)의
            # MySQL 폴백 parity (production 은 PG 라 보통 미경유).
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversationMembers ADD COLUMN last_read_message_id BIGINT NULL"
                )
            except Exception:
                pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProducts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ProductKey VARCHAR(32) NOT NULL UNIQUE,
                Name VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                IsDefault TINYINT(1) NOT NULL DEFAULT 0,
                SortOrder INT NOT NULL DEFAULT 100,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatabases (
                ProductId BIGINT NOT NULL,
                SchemaName VARCHAR(64) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                SortOrder INT NOT NULL DEFAULT 100,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ProductId, SchemaName),
                INDEX IX_WebProductDatabases_Schema (SchemaName)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebSystemPrompts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Scope VARCHAR(16) NOT NULL,
                ProductId BIGINT NULL,
                RoleId BIGINT NULL,
                AccountId BIGINT NULL,
                Content MEDIUMTEXT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UpdatedByAccountId BIGINT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX IX_WebSystemPrompts_Product (ProductId),
                INDEX IX_WebSystemPrompts_Role (RoleId),
                INDEX IX_WebSystemPrompts_Account (AccountId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # MySQL 의 unique index 로 NULL 구분 (복합키에 NULL 이 있으면 UNIQUE 에서 제외됨)
        # → application-level 로 upsert 시 중복 방지 (별도 체크)
        try:
            cur.execute(
                "CREATE UNIQUE INDEX UX_WebSystemPrompts_Scope ON WebSystemPrompts (Scope, ProductId, RoleId, AccountId)"
            )
        except Exception:
            pass
        # TASK-0210 (Major §12.3): per-account 관리 콘솔 대시보드 커스터마이즈 영속.
        # 각 관리자(AccountId)별 위젯 표시/순서/옵션을 JSON 본문으로 저장(self-service,
        # 신규 RBAC 권한 없음). Content 는 WebSystemPrompts 와 동일하게 MEDIUMTEXT 에
        # JSON 텍스트로 보관(부트스트랩 MySQL 버전 무관 호환). AccountId 1행/계정.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDashboardPreferences (
                AccountId BIGINT NOT NULL PRIMARY KEY,
                Content MEDIUMTEXT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # feature-0018 (REQ runtime-settings): assistant 운영 값(실행 타임아웃·모델별 thinking
        # budget) 관리 콘솔 override 를 KV(SettingKey 1행/키)로 영속. shared.runtime_settings 의
        # 스펙 [min,max] 범위에서만 저장되며, 유효값은 스냅샷 파일(/shared)로 전 프로세스에 전파된다
        # (본 테이블 = source of truth + audit, 스냅샷 = 런타임 소비 캐시). SettingValue 는 정수의
        # 문자열 표현. WebDashboardPreferences 와 동일하게 in-code DDL(부트스트랩 MySQL 버전 무관).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebRuntimeSettings (
                SettingKey VARCHAR(128) NOT NULL PRIMARY KEY,
                SettingValue VARCHAR(64) NOT NULL,
                UpdatedByAccountId BIGINT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # graph-perm-split(Critical §12.3, 2026-07-13): 웹 권한 DB 의 1회성 데이터 마이그레이션/backfill
        # 적용 여부 마커. 웹 권한 스키마는 alembic 없이 부트스트랩 `_ensure_*` 로 관리되므로, "정확히 1회만"
        # 실행해야 하는 backfill(예: _backfill_graph_perm_split_v1)의 재실행 방지 guard 저장소로 사용한다.
        # (WebRuntimeSettings 는 런타임 설정 KV 이자 snapshot 대상이라 마이그레이션 마커와 용도를 분리.)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebSchemaMigrations (
                MigrationKey VARCHAR(191) NOT NULL PRIMARY KEY,
                AppliedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.close()
        app._ensure_permission_catalog(conn)
        app._ensure_seed_roles(conn)
        app._ensure_seed_products(conn)
        app._ensure_seed_role_system_prompts(conn)
        # TASK-0095 (Major §12.3): GLOBAL scope system prompt 1행 idempotent seed.
        app._ensure_seed_global_system_prompt(conn)
        # TASK-0052 Phase 1B: WebProducts 와 1:1 동적 권한 row 보장 + D2-A 호환성 backfill (모든 role grant).
        # 호출 순서 정합성: products 가 먼저 만들어진 후, 권한 row 가 보장되어야 admin/account 의 effective
        # permission 계산이 일관됨. app._migrate_legacy_accounts_to_rbac 보다 먼저 두는 이유는 RBAC 마이그레이션
        # 시점에 effective permission 이 이미 정합 상태이도록 하기 위함.
        _migration_added = app._ensure_product_access_permissions(conn)
        if _migration_added > 0:
            try:
                # 운영 transparency: backfill 결과를 stderr 에 1 회 기록 (Codex Claim 5 권고).
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0052 Phase 1B] product access backfill: {_migration_added} permission/role-permission rows added (compatibility-first, NOT secure-by-default — 권한 회수가 필요한 (role x product) 조합은 admin 콘솔 deny override 로 적용)\n"
                )
            except Exception:
                pass
        # model-access-rbac(2026-07-28): 카탈로그 모델별 `model.access.<value>` 동적 권한 보장.
        # 제품 권한과 같은 시점(RBAC 마이그레이션 前)에 둬 effective permission 계산 정합을 맞춘다.
        # model-access-seed-fix(2026-07-28): **격리 필수** — 이 seeder 가 던지면 뒤따르는
        # _migrate_legacy_accounts_to_rbac · _ensure_bootstrap_admin · _seed_legacy_conversations 가
        # 전부 skip 된다. 권한 seed 실패는 게이트 미설치(fail-open)로 흡수되는 국소 사건이어야 하고
        # 부트스트랩 전체를 끌고 내려가선 안 된다. 실패는 stderr 로 loud 하게 남긴다(조용한 skip 금지).
        try:
            _model_perm_added = app._ensure_model_access_permissions(conn)
        except Exception as _mp_exc:
            _model_perm_added = 0
            try:
                import sys as _sys
                _sys.stderr.write(f"[model-access-rbac] seed FAILED (부트스트랩 계속): {_mp_exc!r}\n")
            except Exception:
                pass
        if _model_perm_added > 0:
            try:
                import sys as _sys
                _sys.stderr.write(
                    f"[model-access-rbac] model access backfill: {_model_perm_added} permission/role-permission rows added "
                    "(신규 권한 row 는 전 역할 grant = 무회귀. 기존 row 는 grant 미변경 — 관리자 해제 보존)\n"
                )
            except Exception:
                pass
        app._migrate_legacy_accounts_to_rbac(conn)
        bootstrap_admin_id = app._ensure_bootstrap_admin(conn)
        app._seed_legacy_conversations(conn, bootstrap_admin_id)
        # feature-0018: DB 의 런타임 설정 override 를 공유 볼륨 스냅샷으로 reconcile — 스냅샷이
        # 유실/부재(예: /shared 재생성)여도 web 기동 시 DB 진실원본으로 복구한다. 실패는 비치명적
        # (best-effort) — 스냅샷 부재 시 각 소비처는 기본값으로 fail-open 한다.
        app._reconcile_runtime_settings_snapshot(conn)
        app._mark_memory_runtime_ready()
    finally:
        conn.close()


# ── ITEM-10 p10: 스키마/마이그레이션/시드 잔여 일괄(런타임 성격 5종 제외) ──

def _ensure_seed_role_system_prompts(conn) -> None:
    """사업팀 등 seed role 의 기본 role-scope system prompt 를 1회만 upsert 한다.

    이미 같은 scope/role/product 조합으로 prompt 가 존재하면 덮어쓰지 않는다(관리 콘솔 수정 존중).
    """
    role_map = app._role_id_map(conn)
    for seed in app.SEED_ROLE_SYSTEM_PROMPTS:
        role_id = int(role_map.get(str(seed.get("role_key") or "")) or 0)
        if role_id <= 0:
            continue
        existing = app._load_system_prompt(
            conn,
            scope="role",
            product_id=seed.get("product_id"),
            role_id=role_id,
            account_id=None,
        )
        if existing:
            continue
        app._upsert_system_prompt(
            conn,
            scope="role",
            content=str(seed.get("content") or ""),
            product_id=seed.get("product_id"),
            role_id=role_id,
            account_id=None,
            updated_by_account_id=None,
        )

def _ensure_seed_global_system_prompt(conn) -> None:
    """TASK-0095 (Major §12.3): GLOBAL scope system prompt 1행 idempotent seed.

    `agent_core.SYSTEM_PROMPT` 상수 본문을 `WebSystemPrompts(scope='global', Product/Role/Account NULL)`
    로 1회만 INSERT. 이미 row 가 있으면 건드리지 않는다 (관리 콘솔 수정 존중).
    agent_core import 가 실패하면 silent skip — bootstrap-time 의존성 약화는
    `compose_system_prompt()` 의 fallback 로직이 흡수.
    """
    existing = app._load_system_prompt(
        conn,
        scope="global",
        product_id=None,
        role_id=None,
        account_id=None,
    )
    if existing:
        return
    try:
        from agent_core import SYSTEM_PROMPT as _AGENT_SYSTEM_PROMPT  # type: ignore
        seed_content = str(_AGENT_SYSTEM_PROMPT or "").strip()
    except Exception:
        seed_content = ""
    if not seed_content:
        return
    app._upsert_system_prompt(
        conn,
        scope="global",
        content=seed_content,
        product_id=None,
        role_id=None,
        account_id=None,
        updated_by_account_id=None,
    )

def _ensure_product_access_permissions(conn) -> int:
    """TASK-0052 Phase 1B: 각 WebProducts 에 대응하는 동적 권한 row + role grant 를 idempotent backfill.

    동작:
    1. 모든 WebProducts row 에 대해 `product.access.<key>` 권한이 WebPermissions 에 없으면 INSERT.
       IsDynamic=1, ProductId=<product_id>, GroupName='product_access' (TASK-0288).
    2. D2-A backfill: 신규 추가된 권한을 모든 WebRoles row 에 INSERT IGNORE WebRolePermissions.
       기존 운영 호환성 유지 (briefing §4 Phase 1B 단계).
    Returns: backfill 로 인해 추가된 (permission row + role-permission row) 합계 — 운영 transparency 용 카운트.
    """
    added_total = 0
    # TASK-0288: 기존 배포의 동적 제품 접근 권한을 'product'(제품 관리) → 'product_access'(제품 사용)
    # 그룹으로 멱등 이전. enforce 무관(group=UI 메타) — 권한 편집기에서 작업 화면 사용 vs 관리 콘솔
    # 구성 권한을 분리 표시하기 위함. IsDynamic=1 로 정적 product.read/manage 와 구분.
    _mig_cur = conn.cursor()
    _mig_cur.execute(
        "UPDATE WebPermissions SET GroupName = 'product_access' "
        "WHERE IsDynamic = 1 AND Code LIKE 'product.access.%' AND GroupName <> 'product_access'"
    )
    _mig_cur.close()
    cur = conn.cursor(dictionary=True)
    # TASK-0053: product 자체가 DefaultRoleAccess 정책의 주체. 1=모든 role 자동 grant, 0=명시 grant 만.
    cur.execute("SELECT Id, ProductKey, Name, DefaultRoleAccess FROM WebProducts ORDER BY Id")
    products = cur.fetchall() or []
    cur.close()
    if not products:
        return 0
    for product in products:
        product_id = int(product.get("Id") or 0)
        product_key = str(product.get("ProductKey") or "")
        product_name = str(product.get("Name") or product_key)
        default_role_access = bool(product.get("DefaultRoleAccess", True))
        if not product_id or not product_key:
            continue
        code = app._product_permission_code(product_key)
        # 1. 권한 row 보장
        cur = conn.cursor()
        cur.execute(
            """
INSERT IGNORE INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                code,
                f"제품 접근 — {product_name}",
                f"이 계정은 {product_key} 제품에 접근할 수 있습니다 (대화 생성·pin·system prompt 읽기).",
                # TASK-0288: 작업 화면 제품 사용 권한은 별도 그룹(product_access)으로 분리.
                # 관리 콘솔 제품 구성 권한(product.read/manage, group='product')과 구분.
                "product_access",
                1,
                product_id,
            ),
        )
        if int(cur.rowcount or 0) > 0:
            added_total += 1
        cur.close()
        # 2. 권한 id 조회 (INSERT IGNORE 했으니 fetch)
        cur = conn.cursor()
        cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (code,))
        row = cur.fetchone()
        cur.close()
        if not row:
            continue
        permission_id = int(row[0] or 0)
        if permission_id <= 0:
            continue
        # 3. product.DefaultRoleAccess=1 일 때만 모든 role 에 grant backfill (TASK-0053 정책 — product 주체).
        # DEFAULT 1 이라 기존 운영 데이터는 D2-A 와 동일 동작 유지.
        if default_role_access:
            cur = conn.cursor()
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT r.Id, %s FROM WebRoles r
                """,
                (permission_id,),
            )
            added_total += int(cur.rowcount or 0)
            cur.close()
    return added_total

def _ensure_model_access_permissions(conn) -> int:
    """model-access-rbac(2026-07-28): 카탈로그의 각 사용자 선택 모델에 대응하는 동적 접근 권한을 보장.

    `product.access.<key>`(_ensure_product_access_permissions) 와 동일 패턴 —
    `WebPermissions` 에 IsDynamic=1 / GroupName='model_access' row 를 넣어 역할 편집기·계정
    override 그리드·감사·pending→'모두 적용' UI 를 전부 재사용한다(신규 UI·신규 테이블 0).

    ⚠️ **grant 는 권한 row 가 "새로 생성된 순간"에만** 전 역할에 부여한다(사용자 결정 2026-07-28:
    "전부 기본 부여" = 배포 시 무회귀). 제품 쪽 `_ensure_product_access_permissions` 는
    `DefaultRoleAccess=1` 이면 **매 부트스트랩마다** 무조건 re-grant 하는데, 그 방식을 그대로
    쓰면 관리자가 콘솔에서 어떤 역할의 opus 를 해제해도 다음 배포/재기동이 조용히 되살린다
    (관리 행위가 무효화 — 본 기능의 목적 자체가 무력화). 그래서 여기서는 **INSERT IGNORE 의
    rowcount>0(=이 부트스트랩이 row 를 처음 만들었다)** 를 one-time 마커로 삼는다:
      · 최초 배포        → row 신규 → 전 역할 grant (현행과 byte-동치 동작)
      · 이후 재기동      → row 기존 → grant skip → 관리자의 해제가 보존된다
      · 나중에 모델 추가 → 그 모델 row 만 신규 → 전 역할 grant (같은 정책 일관 적용)

    카탈로그에서 사라진 모델의 권한 row 는 **삭제하지 않는다**(prune 없음) — 선택 불가 모델의
    잔존 row 는 무해하고, 삭제하면 역할별 grant 이력이 사라져 모델 재도입 시 설정이 리셋된다.

    Returns: 추가된 (permission row + role-permission row) 합계 — 운영 transparency 용.
    """
    from shared.model_catalog import (
        MODEL_ACCESS_PERMISSION_GROUP,
        PUBLIC_API_MODEL_OPTIONS,
        model_permission_code,
    )

    added_total = 0
    for item in PUBLIC_API_MODEL_OPTIONS:
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        code = model_permission_code(value)
        if not code:
            continue
        label = str(item.get("label") or value)
        # model-access-seed-fix(2026-07-28): 컬럼 길이 방어 클립 — Label VARCHAR(128) /
        # Description VARCHAR(255). 초과하면 INSERT 가 1406(Data too long)으로 던지고 이 함수를
        # 감싸는 부트스트랩 단계가 통째로 skip 된다(`_ensure_permission_catalog` 가 같은 fragility 를
        # graph-perm-split 배포에서 실측하고 남긴 경고와 동일 축). 모델 label 이 길어져도 안전하게.
        perm_label = f"모델 사용 — {label}"[:128]
        perm_desc = (
            f"작업 화면 대화에서 `{label}` 모델을 선택해 요청할 수 있습니다. "
            f"해제하면 모델 선택기에서 숨겨지고 서버가 요청을 거부합니다 (내부 alias: {value})."
        )[:255]
        cur = conn.cursor()
        # ⚠️ placeholder 개수 = 파라미터 개수. IsDynamic 은 **반드시 바인딩**한다 — 이전 버전은
        # placeholder 5개에 파라미터 4개를 넘겨 `ProgrammingError: Not enough parameters` 로
        # 부트스트랩 seed 단계가 skip 됐다(라이브 실측 `[web.startup] seed catchup skipped`).
        # 게이트가 fail-open('권한 row 미등록'=미설치)으로 설계돼 서비스 영향은 없었으나, 권한 row 가
        # 생성되지 않아 기능 자체가 조용히 미적용됐다. 테스트 더블이 arity 를 검증하지 않아 단위
        # 테스트를 통과한 것이 근본 gap → `_SeedCur` 가 이제 arity 를 단정한다.
        cur.execute(
            """
INSERT IGNORE INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
VALUES (%s, %s, %s, %s, %s, NULL)
            """,
            (
                code,
                perm_label,
                perm_desc,
                MODEL_ACCESS_PERMISSION_GROUP,
                1,  # IsDynamic — 동적 권한(제품 접근과 동일 규약)
            ),
        )
        newly_created = int(cur.rowcount or 0) > 0
        cur.close()
        if not newly_created:
            # 이미 등록된 모델 — 역할별 grant/해제는 관리자 소관이므로 손대지 않는다(위 ⚠️).
            continue
        added_total += 1
        cur = conn.cursor()
        cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (code,))
        row = cur.fetchone()
        cur.close()
        if not row:
            continue
        permission_id = int(row[0] or 0)
        if permission_id <= 0:
            continue
        # 최초 생성 시에만: 전 역할 grant (무회귀 — 배포 직후 동작이 현행과 동일).
        cur = conn.cursor()
        cur.execute(
            """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT r.Id, %s FROM WebRoles r
            """,
            (permission_id,),
        )
        added_total += int(cur.rowcount or 0)
        cur.close()
    return added_total


def _migrate_legacy_accounts_to_rbac(conn) -> None:
    role_map = app._role_id_map(conn)
    rows = app._fetch_account_rows(conn, "a.RoleId IS NULL", include_password=False, include_legacy=True)
    if not rows:
        return
    permission_map = app._permission_id_map(conn)
    cur = conn.cursor()
    for row in rows:
        account_id = int(row.get("id") or 0)
        if account_id <= 0:
            continue
        legacy_role = str(row.get("legacy_role") or "").strip().lower() or "pending"
        if legacy_role not in role_map:
            seed = app._seed_role_definition(legacy_role)
            role_map[legacy_role] = app._create_role_with_permissions(
                conn,
                legacy_role,
                name=str(seed["name"] if seed else legacy_role.title()),
                description=str(seed["description"] if seed else ""),
                is_active=True,
                is_default_signup=bool(seed["is_default_signup"]) if seed else False,
                permission_codes=app._seed_role_codes(legacy_role),
            )
        role_id = int(role_map[legacy_role])
        desired_codes = app._legacy_permission_codes_from_row(row)
        seed_codes = app._seed_role_codes(legacy_role)
        cur.execute(
            """
UPDATE WebAccounts
SET RoleId = %s
WHERE Id = %s
            """,
            (role_id, account_id),
        )
        cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (account_id,))
        for code in app.PERMISSION_CODES:
            if (code in desired_codes) == (code in seed_codes):
                continue
            permission_id = int(permission_map.get(code) or 0)
            if permission_id <= 0:
                continue
            cur.execute(
                """
INSERT INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
VALUES (%s, %s, %s)
                """,
                (
                    account_id,
                    permission_id,
                    app.OVERRIDE_ALLOW if code in desired_codes else app.OVERRIDE_DENY,
                ),
            )
        if not row.get("approved_at") and (
            "conversation.ask" in desired_codes or "console.access" in desired_codes
        ):
            cur.execute(
                "UPDATE WebAccounts SET ApprovedAt = CURRENT_TIMESTAMP WHERE Id = %s AND ApprovedAt IS NULL",
                (account_id,),
            )
    cur.close()
    app._ensure_default_signup_role(conn)

def _ensure_bootstrap_admin(conn) -> int:
    managers = app._management_accounts(conn)
    if managers:
        return int(managers[0]["id"])

    username = app._sanitize_username(app.BOOTSTRAP_ADMIN_USERNAME)
    password = app.BOOTSTRAP_ADMIN_PASSWORD
    if not app._is_valid_username(username) or not app._is_valid_password(password):
        raise RuntimeError(
            "관리 가능 계정이 없습니다. WEB_BOOTSTRAP_ADMIN_USERNAME 및 "
            "WEB_BOOTSTRAP_ADMIN_PASSWORD를 설정해야 합니다."
        )

    role_map = app._role_id_map(conn)
    admin_role_id = int(role_map.get("admin") or 0)
    if admin_role_id <= 0:
        admin_role_id = app._create_role_with_permissions(
            conn,
            "admin",
            name="Admin",
            description="관리 콘솔과 전체 대화 관리 권한을 가진 계정",
            is_active=True,
            is_default_signup=False,
            permission_codes=set(app.PERMISSION_CODES),
        )
    password_hash = app._hash_password(password)
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebAccounts WHERE Username = %s LIMIT 1", (username,))
    existing = cur.fetchone()
    if existing:
        admin_id = int(existing[0] or 0)
        cur.execute(
            """
UPDATE WebAccounts
SET PasswordHash = %s,
    RoleId = %s,
    IsActive = 1,
    DeletedAt = NULL,
    DeletedByAccountId = NULL,
    ApprovedAt = COALESCE(ApprovedAt, CURRENT_TIMESTAMP)
WHERE Id = %s
            """,
            (password_hash, admin_role_id, admin_id),
        )
        cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (admin_id,))
        cur.close()
        return admin_id

    cur.execute(
        """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    RoleId,
    ApprovedAt,
    IsActive
) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 1)
        """,
        (username, password_hash, admin_role_id),
    )
    admin_id = int(cur.lastrowid or 0)
    cur.close()
    return admin_id

def _seed_legacy_conversations(conn, bootstrap_admin_id: int) -> None:
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        return
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT ConversationId COLLATE utf8mb4_unicode_ci AS conversation_id FROM AgentMemoryKv
UNION
SELECT ConversationId COLLATE utf8mb4_unicode_ci FROM AgentMemoryMessages
UNION
SELECT conversation_id COLLATE utf8mb4_unicode_ci FROM AgentCoreConversations
            """
        )
        rows = cur.fetchall() or []
        for (conversation_id_raw,) in rows:
            conversation_id = str(conversation_id_raw or "").strip()
            if not conversation_id:
                continue
            cur.execute(
                "INSERT IGNORE INTO AgentCoreConversations (conversation_id, topic) VALUES (%s, '')",
                (conversation_id,),
            )
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE owner_account_id IS NULL
            """,
            (int(bootstrap_admin_id),),
        )
    finally:
        cur.close()

def _ensure_dynamic_permissions_schema(conn) -> None:
    """TASK-0052 Phase 1B + TASK-0053: WebPermissions/WebProducts 의 동적 권한·정책 컬럼을 idempotent ALTER.

    - WebPermissions.IsDynamic / ProductId : 동적 권한 row 식별 (TASK-0052).
    - WebProducts.DefaultRoleAccess : product 생성 시 모든 role 자동 grant 여부 정책 (TASK-0053).
      DEFAULT 1 = 기존 D2-A 호환 (모든 신규 product 가 모든 role 에 자동 grant). 운영자가 product
      생성 시 0 으로 설정하면 그 product 는 명시적 grant 가 있어야만 role 이 접근 가능.
      정책의 주체는 product 자체 — role 은 어떤 product 든 자기 grant 만으로 결정 (role-side default
      toggle 은 별도로 두지 않음, 본 cycle 에서 사용자 의도 반영).

    `WebRoles.DefaultProductAccess` (이전 설계) 는 **deprecated** — 컬럼 자체는 destructive DROP
    회피 차원에서 남기되 어떤 SQL 도 참조하지 않음. 다음 cleanup cycle 에서 DROP COLUMN.

    _ensure_web_tables (slow path) 와 _ensure_seed_catchup (fast path) 양쪽에서 호출되어
    기존 배포 (table 이미 존재) 에서도 신규 컬럼이 추가되도록 한다. 컬럼이 이미 있으면
    `try/except pass` 로 graceful no-op.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute("ALTER TABLE WebPermissions ADD COLUMN IsDynamic TINYINT(1) NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebPermissions ADD COLUMN ProductId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebPermissions ADD INDEX IX_WebPermissions_ProductId (ProductId)")
        except Exception:
            pass
        # TASK-0053: WebProducts 에 DefaultRoleAccess 컬럼 — product 가 자체 정책의 주체.
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1")
        except Exception:
            pass
        # 멀티 datasource (P1, DESIGN Stage 1): product → datasource 바인딩.
        # NULL = 기본 단일 MySQL(DB_HOST). 값 = config.DATASOURCES 의 키 (agent_core 가 해석).
        # 좌표/비밀번호는 DB 에 저장하지 않는다 — .env named credential 만 (security-first).
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DatasourceKey VARCHAR(64) NULL")
        except Exception:
            pass
        # TASK-0205 §2.4: 제품별 MSSQL 참조 DB(같은 서버 데이터소스의 어느 DB 를 볼지). NULL=데이터소스 기본.
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DatasourceDatabase VARCHAR(128) NULL")
        except Exception:
            pass
        # TASK-0268: 제품 아이콘 이미지 — MinIO object key (NULL=미설정 → 프론트 Identicon 폴백).
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN IconObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        # TASK-0309: 제품 프롬프트 무인 자동완성 1회성 마커. insight 분석률이 임계(기본 95%)에
        # 도달해 자동완성·저장이 1회 수행된 시각을 기록한다(NULL=미수행). insight 초기화
        # (admin_product_insight_reset)는 PG insight 만 삭제하고 본 MySQL 컬럼은 보존하므로,
        # reset 으로 분석률이 내려갔다 재상승해도 본 마커가 있으면 재실행하지 않는다(1회성 보장).
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN AutoPromptGeneratedAt DATETIME NULL")
        except Exception:
            pass
        # WebRoles.DefaultProductAccess (deprecated, 이전 설계 잔재) 의 ALTER 는 더 이상 추가하지 않는다.
        # 기존 deploy 에 컬럼이 이미 있다면 그대로 보존 (다음 cleanup cycle 의 DROP 대상).
    finally:
        cur.close()

def _ensure_web_datasources_schema(conn) -> None:
    """TASK-0205: DB 기반 datasource 레지스트리 테이블 (자격증명 암호화 저장). 멱등 CREATE.

    - WebDatasourceKeys: envelope DEK(KEK 로 wrap 해 저장 — 마스터키의 DB 암호화 저장).
    - WebDatasources: datasource 좌표 + 암호화 password. password 만 암호화(host/user 는 노출 경계 밖).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDatasourceKeys (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                KeyVersion INT NOT NULL UNIQUE,
                DekWrapped TEXT NOT NULL,
                KekVersion INT NOT NULL,
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDatasources (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                DatasourceKey VARCHAR(64) NOT NULL UNIQUE,
                Engine VARCHAR(16) NOT NULL DEFAULT 'mysql',
                Host VARCHAR(255) NOT NULL,
                Port INT NOT NULL,
                DbUser VARCHAR(128) NOT NULL,
                PasswordEnc TEXT NULL,
                DefaultDb VARCHAR(128) NULL,
                EncryptionVersion INT NOT NULL DEFAULT 1,
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                InsightEnabled TINYINT(1) NOT NULL DEFAULT 1,
                Description TEXT NULL,
                DomainTags VARCHAR(512) NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UpdatedByAccountId BIGINT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # TASK-0215: insight-worker 가 이 데이터소스를 탐색할지 토글(기존 deploy idempotent ALTER, default 1=탐색).
        try:
            cur.execute("ALTER TABLE WebDatasources ADD COLUMN InsightEnabled TINYINT(1) NOT NULL DEFAULT 1")
        except Exception:
            pass
        # ITEM-04: datasource 비즈니스 컨텍스트(멀티DS 그라운딩·DS picker 주입용). plaintext(비밀 아님).
        # 멱등 ALTER — feature-0002 datasources._db_datasource 가 이 컬럼을 읽어 _row_to_ds 로 전달.
        for _ddl in (
            "ALTER TABLE WebDatasources ADD COLUMN Description TEXT NULL",
            "ALTER TABLE WebDatasources ADD COLUMN DomainTags VARCHAR(512) NULL",
        ):
            try:
                cur.execute(_ddl)
            except Exception:
                pass
    finally:
        cur.close()

def _migrate_mssql_products_to_db_level(conn) -> None:
    """TASK-0206 일회성 마이그레이션: 구 MSSQL 제품을 DB-단위 접근목록(`WebProductDatabases`)으로 이전.

    배경: 구 모델(TASK-0205, schema-allowlist)에서 MSSQL 제품의 WebProductDatabases 는 **스키마명**(dbo 등)이고,
    실제 접근 DB 는 (a) `WebProducts.DatasourceDatabase`(per-product 참조 DB) 또는 (b) 그게 없으면 **데이터소스의
    default_db**(연결 기본 DB)였다. DB-단위 모델에선 WebProductDatabases 가 **DB명(catalog)** 을 의미하므로 구
    schema-name 항목은 DB명으로 오해석돼 제품이 접근 불가가 된다.

    이전 규칙: MSSQL 제품의 **유효 DB**(= DatasourceDatabase 또는 데이터소스 default_db)가 현재 접근목록에
    없으면(=구 schema-name 구성) 접근목록을 유효 DB 단일 항목으로 치환하고 DatasourceDatabase 를 비운다.
    유효 DB 가 이미 접근목록에 있으면(=신규 UI 구성) 건드리지 않는다(멱등 + 운영자 구성 보존).
    """
    try:
        from shared import config as _cfg2
        _env_ds = getattr(_cfg2, "DATASOURCES", {}) or {}
    except Exception:
        _env_ds = {}
    cur = conn.cursor()
    try:
        # WebDatasources(엔진·default_db) 매핑.
        db_ds: dict[str, tuple[str, str]] = {}
        try:
            cur.execute("SELECT DatasourceKey, Engine, DefaultDb FROM WebDatasources")
            for r in (cur.fetchall() or []):
                if r and r[0]:
                    db_ds[str(r[0]).strip().lower()] = (
                        (str(r[1]).strip().lower() if len(r) > 1 and r[1] else "mysql"),
                        (str(r[2]).strip() if len(r) > 2 and r[2] else ""),
                    )
        except Exception:
            db_ds = {}
        cur.execute(
            "SELECT Id, DatasourceKey, DatasourceDatabase FROM WebProducts "
            "WHERE DatasourceKey IS NOT NULL AND DatasourceKey <> ''"
        )
        prows = cur.fetchall() or []
        migrated = 0
        for r in prows:
            pid = r[0]
            dskey = (str(r[1]).strip().lower() if len(r) > 1 and r[1] else "")
            pdb = (str(r[2]).strip() if len(r) > 2 and r[2] else "")
            if not pid or not dskey:
                continue
            # 데이터소스 엔진 + default_db 해석 (WebDatasources 우선, .env 폴백).
            engine, ds_default = db_ds.get(dskey, ("", ""))
            if not engine:
                _ed = _env_ds.get(dskey) or {}
                engine = str(_ed.get("engine") or "mysql").strip().lower()
                ds_default = str(_ed.get("default_db") or "").strip()
            if engine != "mssql":
                continue  # MySQL 제품은 schema==DB 라 무변경
            effective_db = pdb or ds_default
            if not effective_db:
                continue  # 유효 DB 불명 — 운영자 수동 구성 필요
            # 현재 접근목록 조회.
            cur.execute("SELECT SchemaName FROM WebProductDatabases WHERE ProductId=%s", (int(pid),))
            cur_names = {str(x[0]).strip().lower() for x in (cur.fetchall() or []) if x and x[0]}
            if effective_db.lower() in cur_names:
                continue  # 이미 DB-단위 구성(신규 UI) — 멱등, 보존
            # 구 schema-name 구성 → 유효 DB 단일 항목으로 치환.
            cur.execute("DELETE FROM WebProductDatabases WHERE ProductId=%s", (int(pid),))
            cur.execute(
                "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder) "
                "VALUES (%s, %s, %s, 10)",
                (int(pid), effective_db, "TASK-0206 마이그레이션(참조 DB→접근 가능 DB)"),
            )
            cur.execute("UPDATE WebProducts SET DatasourceDatabase=NULL WHERE Id=%s", (int(pid),))
            migrated += 1
        if migrated:
            try:
                logging.getLogger(__name__).info(
                    "[ds-migrate] MSSQL 제품 %d개를 DB-단위 접근목록으로 이전(유효 DB→접근 DB)", migrated,
                )
            except Exception:
                pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()

def _migrate_env_datasources_to_db(conn) -> None:
    """TASK-0211: `.env`(config.DATASOURCES, `DS_<KEY>_*`) 분석 데이터소스를 **DB 레지스트리**(WebDatasources,
    암호화)로 이전. 이제 데이터소스는 **관리 콘솔(DB)에서 일원 관리**한다 — `.env` 는 앱 인프라('Database Query
    Assistant' = 데이터 MySQL `AGENT_DATA_DB_*`(.env.mysql) / `agent_memory` / KEK(.env.secret))만 둔다.

    멱등: 이미 DB 에 동일 키가 있으면 skip(운영자가 콘솔에서 편집한 값을 .env 가 덮어쓰지 않는다). KEK
    미설정/불완전 좌표 시 skip. 이전 후 운영자가 `.env` 의 `DS_*` 를 제거하면 DB 사본이 단일 소스가 된다.
    """
    try:
        from modules import cred_crypto as _cc
        from shared import datasources as _dsr
        from shared import config as _cfg2
    except Exception:
        return
    if not _cc.enc_available():
        return  # KEK 미설정 — 암호화 불가, 보류
    env_ds = getattr(_cfg2, "DATASOURCES", {}) or {}
    if not env_ds:
        return
    cur = conn.cursor()
    try:
        for key, ds in env_ds.items():
            k = str(key).strip().lower()
            if not k:
                continue
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (k,))
            if cur.fetchone():
                continue  # 이미 DB 관리 — 멱등 skip(콘솔 편집값 보존)
            engine = str(ds.get("engine") or "mysql").strip().lower()
            host = str(ds.get("host") or "").strip()
            try:
                port = int(ds.get("port") or (1433 if engine == "mssql" else 3306))
            except Exception:
                port = 1433 if engine == "mssql" else 3306
            duser = str(ds.get("user") or "").strip()
            password = ds.get("password") or ""
            default_db = (str(ds.get("default_db")).strip() or None) if ds.get("default_db") else None
            if not host or not duser:
                continue  # 불완전 좌표 — skip
            got = _dsr.ensure_dek(conn)
            if got is None:
                continue
            ver, dek = got
            try:
                pw_enc = _cc.encrypt_password(dek, password, k) if password else None
            except Exception:
                continue
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,NULL)",
                (k, engine, host, port, duser, pw_enc, default_db, int(ver)),
            )
            try:
                logging.getLogger(__name__).info(
                    "[ds-migrate] .env 데이터소스 '%s'(%s @ %s:%s) → DB 레지스트리 이전(암호화)", k, engine, host, port,
                )
            except Exception:
                pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_product_db_rules_schema(conn) -> None:
    """TASK-20260618T044318 (REQ-20260618-0321): 제품×데이터소스 DB allowlist 정규식 규칙 + pending +
    WebProductDatabases.Source/RuleId 차원. 모두 멱등 CREATE/ALTER — 기존 행은 Source='manual' 로 backfill
    (B4: manual 우선 불변식). 비파괴: 신규 컬럼/테이블만 추가, 기존 동작 불변.
    """
    cur = conn.cursor()
    try:
        # 1) 규칙 테이블: (product, datasource) 당 정규식 규칙 **여러 개**(TASK-20260618T061703).
        #    신규 설치는 UNIQUE 없이 생성. 기존(단일 규칙 시절 UNIQUE) 테이블은 아래 마이그레이션이 DROP.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatasourceDbRules (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ProductId BIGINT NOT NULL,
                DatasourceKey VARCHAR(64) NOT NULL,
                IncludePattern VARCHAR(255) NOT NULL,
                ExcludePattern VARCHAR(255) NULL,
                Cap INT NOT NULL DEFAULT 3,
                IsEnabled TINYINT(1) NOT NULL DEFAULT 1,
                SortOrder INT NOT NULL DEFAULT 100,
                CreatedByAccountId BIGINT NULL,
                LastSyncAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX IX_WebProductDsDbRule_PD (ProductId, DatasourceKey),
                INDEX IX_WebProductDsDbRule_Ds (DatasourceKey)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # 1b) 다중 규칙 마이그레이션: 단일 규칙 시절의 UNIQUE(ProductId,DatasourceKey) 제거 + SortOrder 추가.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebProductDatasourceDbRules' AND INDEX_NAME='UQ_WebProductDsDbRule'")
            if int((cur.fetchone() or [0])[0]) > 0:
                cur.execute("ALTER TABLE WebProductDatasourceDbRules DROP INDEX UQ_WebProductDsDbRule")
                # UNIQUE 자리에 비-UNIQUE 조회 인덱스 보강(부재 시).
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME='WebProductDatasourceDbRules' AND INDEX_NAME='IX_WebProductDsDbRule_PD'")
                if int((cur.fetchone() or [0])[0]) == 0:
                    cur.execute("ALTER TABLE WebProductDatasourceDbRules ADD INDEX IX_WebProductDsDbRule_PD (ProductId, DatasourceKey)")
        except Exception as _exc:
            logging.getLogger(__name__).error("[db-rule] 다중규칙 UNIQUE 제거 실패: %r", _exc)
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebProductDatasourceDbRules' AND COLUMN_NAME='SortOrder'")
            if int((cur.fetchone() or [0])[0]) == 0:
                cur.execute("ALTER TABLE WebProductDatasourceDbRules ADD COLUMN SortOrder INT NOT NULL DEFAULT 100")
        except Exception as _exc:
            logging.getLogger(__name__).error("[db-rule] SortOrder 추가 실패: %r", _exc)
        # 2) pending: 자동적용 보류분(Cap 초과/모호 — 승인 대기). B1.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatabasePending (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ProductId BIGINT NOT NULL,
                DatasourceKey VARCHAR(64) NOT NULL,
                SchemaName VARCHAR(128) NOT NULL,
                RuleId BIGINT NULL,
                Reason VARCHAR(64) NOT NULL DEFAULT '',
                DetectedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY UQ_WebProductDbPending (ProductId, DatasourceKey, SchemaName),
                INDEX IX_WebProductDbPending_Product (ProductId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # 3) WebProductDatabases.Source — manual/rule 구분(B4). 기존 행은 manual default.
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='Source'"
        )
        if int((cur.fetchone() or [0])[0]) == 0:
            try:
                cur.execute(
                    "ALTER TABLE WebProductDatabases ADD COLUMN Source VARCHAR(8) NOT NULL DEFAULT 'manual'"
                )
            except Exception as _exc:
                logging.getLogger(__name__).error(
                    "[db-rule] WebProductDatabases.Source 컬럼 추가 실패 — rule/manual 구분 비활성: %r", _exc)
        # 4) WebProductDatabases.RuleId — 어느 규칙이 추가했는지 추적(감사·strip).
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='RuleId'"
        )
        if int((cur.fetchone() or [0])[0]) == 0:
            try:
                cur.execute("ALTER TABLE WebProductDatabases ADD COLUMN RuleId BIGINT NULL")
            except Exception as _exc:
                logging.getLogger(__name__).error(
                    "[db-rule] WebProductDatabases.RuleId 컬럼 추가 실패: %r", _exc)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_conversation_shares_schema(conn) -> None:
    """REQ-20260514-0001: WebConversationShares 테이블을 idempotent CREATE.

    대화 공유 링크 (anonymous 접근 가능) 저장소. 한 ConversationId 에 여러 share 발급 가능
    (ScopeMode='full' 또는 'anchored' + AnchorMessageId 조합으로 구분).

    AnchorMessageId 는 `AgentMemoryMessages.Id` 와 동일 식별자를 사용한다
    (`fork_conversation` 의 `from_message_id` 와 정합). 의미: inclusive — 해당 메시지
    까지 (`Id <= AnchorMessageId`) 공유 view 에 노출.

    Token 은 `secrets.token_urlsafe(32)` (256-bit entropy) 가 생성하며 UNIQUE.
    RevokedAt NULL = 활성, NOT NULL = revoked → public GET 은 410 Gone 반환.

    `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서
    호출되어 기존 배포에도 자동 적용된다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationShares (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL,
                Token VARCHAR(64) NOT NULL UNIQUE,
                ScopeMode VARCHAR(16) NOT NULL DEFAULT 'full',
                AnchorMessageId BIGINT NULL,
                FloorMessageId BIGINT NULL,
                CreatedBy BIGINT NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                RevokedAt DATETIME NULL,
                RevokedBy BIGINT NULL,
                ViewCount BIGINT NOT NULL DEFAULT 0,
                LastViewedAt DATETIME NULL,
                INDEX IX_WCS_Conversation (ConversationId),
                INDEX IX_WCS_Token (Token),
                INDEX IX_WCS_CreatedBy (CreatedBy),
                INDEX IX_WCS_RevokedAt (RevokedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_share_links_policy_version_column(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (R-F7): WebConversationShares 에 PolicyVersion column 추가.

    BRIEFING Revision 2 D9 갱신 — 기존 share token 의 backward-compat 문제 해소를
    위해 share 발급 시점의 share-policy version 을 row 에 기록한다. 배포된 정책 변경
    (예: attachment_derived redact 강화) 시 PolicyVersion < 현재 정책 version 의 token
    이 자동 redact 대상이 되며, audit `share.policy.redact_applied` 이벤트가 기록된다.

    Phase 2 본 단계는 column ALTER 만 추가 — 실제 PolicyVersion 값 채움 / redact 로직 /
    audit 이벤트 dispatch 는 Phase 8 (share redact) 에서 ship. 기존 row 에는 NULL 또는
    DEFAULT 1 ('initial-pre-attachment' 의미) 적용.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebConversationShares ADD COLUMN PolicyVersion INT NOT NULL DEFAULT 1"
            )
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_share_links_expiry_column(conn) -> None:
    """TASK-20260619T012028-share-link-expiry (REQ-20260619-0324, SECURITY.md §7.2):
    WebConversationShares 에 `ExpiresAt DATETIME NULL` column 추가.

    시간 기반 공유 링크 만료. 기본 NULL = 무기한 (기존 share 동작 무회귀 — 명시 revoke
    그대로). 생성 시 `expires_in_seconds` 옵션 → `DATE_ADD(NOW(), INTERVAL ... SECOND)`.
    public GET / fork 시 `ExpiresAt IS NOT NULL AND ExpiresAt <= NOW()` → 410 Gone
    (revoke 의 410 과 구분된 만료 메시지). 만료 판정은 **DB 시계 기준** (Python clock
    skew 차단) — view 의 ViewCount UPDATE predicate 와 `_share_row_expired` 헬퍼 모두 DB
    NOW() 사용.

    `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서
    호출되어 기존 배포에도 자동 적용된다 (PolicyVersion 헬퍼 idiom 동형).
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebConversationShares ADD COLUMN ExpiresAt DATETIME NULL"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE INDEX IX_WCS_ExpiresAt ON WebConversationShares (ExpiresAt)"
            )
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_share_links_joinable_column(conn) -> None:
    """feature-0009-group-conversation: WebConversationShares 에 `Joinable TINYINT(1)` column 추가.

    공유 링크를 통한 그룹 대화 **참여(join)** 허용 여부. 기본 1(ON, 사용자 결정) — 링크를 가진
    로그인 사용자가 '참여' 로 해당 대화의 멤버가 될 수 있다(열람 ≠ 발화, AR-1: 멤버는 대화 전체를
    열람). owner 가 링크별로 OFF 가능. 기존 share row 는 DEFAULT 1 로 채워져 참여 가능해진다.

    PolicyVersion/ExpiresAt 헬퍼 idiom 동형 — fast/slow path 양쪽에서 호출되어 기존 배포 자동 적용.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebConversationShares ADD COLUMN Joinable TINYINT(1) NOT NULL DEFAULT 1"
            )
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_share_links_floor_column(conn) -> None:
    """share-visibility-window: WebConversationShares 에 `FloorMessageId BIGINT NULL` column 추가.

    "여기부터 공유"(하단 경계)를 저장한다. AnchorMessageId(상단, "여기까지 공유", inclusive
    `Id <= AnchorMessageId`)와 짝을 이뤄 windowed share 는 [FloorMessageId, AnchorMessageId]
    구간만 노출한다(inclusive `Id >= FloorMessageId`). 둘 다 DISPLAY id-space
    (AgentMemoryMessages.Id / agent_runtime.messages.id), AnchorMessageId 계약과 동일.

    기본 NULL = 하단 무제한 = 첫 메세지부터(기존 'full'/'anchored' share 무회귀). 익명 공유 뷰·
    join stamp·fork 가 이 값을 읽어 가려진 pre-floor 구간을 뷰·멤버십·fork·LLM recall 전부에서 배제한다.

    PolicyVersion/ExpiresAt/Joinable 헬퍼 idiom 동형 — fast/slow path 양쪽에서 호출되어 기존 배포 자동 적용.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebConversationShares ADD COLUMN FloorMessageId BIGINT NULL"
            )
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_web_conversation_attachments_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2: WebConversationAttachments 테이블 idempotent CREATE.

    BRIEFING §5.1 정본 — 첨부 객체의 metadata source-of-truth. MinIO ObjectKey (D1) +
    HMAC filename (D12) + size bucket (D12) + Kind/UploadStatus enum (D17 7 값) +
    DeletePending/DeleteReason taxonomy (D6 4 종) + MetaJson kind-별 부가 (sheet
    names, page count, degraded_reason, ingest_summary).

    BRIEFING Revision 2 R-Claim6 흡수 — ConversationId 는 nullable 로 두지 않고 NOT
    NULL 유지하되, conversation hard-delete 시 application-level tombstone 처리
    (DELETE 가 아닌 DeletePending=1 + DeleteReason='conv_soft'). reconciliation worker
    (Phase 9) 가 SLA 따라 hard-delete.

    R-F11 흡수 — derived message 목록은 본 row 의 AttachmentDerivedMessages JSON 이
    아닌 별도 join table (`WebAttachmentDerivedMessages`) 가 source-of-truth. 본 column
    은 deprecated 로 두며 Phase 8 (share redact) 에서 join table 로 마이그레이션.

    _ensure_web_tables (slow path) 와 _ensure_seed_catchup (fast path) 양쪽에서 호출.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachments (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL,
                AccountId BIGINT NOT NULL,
                ObjectKey VARCHAR(512) NOT NULL,
                OriginalFilename VARCHAR(255) NOT NULL,
                FilenameHmac CHAR(64) NOT NULL,
                MimeType VARCHAR(128) NOT NULL,
                SizeBytes BIGINT NOT NULL,
                SizeBucket VARCHAR(16) NOT NULL,
                Sha256 CHAR(64) NOT NULL,
                Kind VARCHAR(16) NOT NULL,
                UploadStatus VARCHAR(24) NOT NULL DEFAULT 'uploaded',
                AttachmentDerivedMessages JSON NULL,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DeletedAt DATETIME(6) NULL,
                DeletePending TINYINT NOT NULL DEFAULT 0,
                DeleteReason VARCHAR(16) NULL,
                MetaJson JSON NULL,
                RootAttachmentId BIGINT NULL,
                VersionNumber INT NOT NULL DEFAULT 1,
                CreatedByRole VARCHAR(16) NOT NULL DEFAULT 'user',
                SupersededAt DATETIME(6) NULL,
                INDEX IX_WCA_Conversation (ConversationId, DeletedAt),
                INDEX IX_WCA_Account (AccountId, CreatedAt),
                INDEX IX_WCA_Status (UploadStatus, DeletePending),
                -- TASK-0274: 버전 체인 내 (root, version) 유일성 강제(동시 materialize race 방지).
                -- RootAttachmentId NULL(=원본, 버전체인 미생성)은 MySQL UNIQUE 에서 중복 허용되어
                -- 기존 단일 첨부(NULL,1 다수)와 충돌하지 않는다.
                UNIQUE KEY UQ_WCA_VersionChain (RootAttachmentId, VersionNumber)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_conversation_attachments_sandbox_schemas_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D2/D15/R-F4): sandbox schema mapping table.

    BRIEFING §5.1 — 1 conversation = 1 sandbox schema 의 mapping. schema name 은
    `agent_attachment_<sha256(conversation_id)[:32]>` 로 D15 R-Claim4 maintenance path
    가 결정. 본 table 은 lifecycle 추적 (CreatedAt / DroppedAt / DeletePending) + R-F4
    drift detection 의 expected grants source.

    Phase 2 는 schema CREATE 만 — 실제 schema 생성 path (D15 maintenance) + grant 부여
    + drift detection worker 는 Phase 10 (sandbox + MySQL users) 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachmentsSandboxSchemas (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL UNIQUE,
                SchemaName VARCHAR(64) NOT NULL UNIQUE,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DroppedAt DATETIME(6) NULL,
                DeletePending TINYINT NOT NULL DEFAULT 0,
                INDEX IX_WCASS_DeletePending (DeletePending, DroppedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_attachment_derived_messages_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D19, R-F11): derived message join table.

    BRIEFING Revision 2 D19 신규 — many-to-many 정규화. 한 assistant message 가 여러
    attachment 에서 파생될 수 있고, 한 attachment 가 여러 message 에 파생 데이터를
    제공할 수 있다. DerivationType enum:
      - csv_sample            : CSV/XLSX의 sample row 출력
      - csv_query_result      : sandbox SQL 실행 결과
      - vision_analysis       : Cycle 2 vision 분석 결과
      - pdf_excerpt           : Cycle 4 PDF excerpt 인용
      - rag_citation          : Cycle 4 RAG retrieval citation

    Share redact (D9) / audit (D12) / fork 시 derivation 보존 / message hard-delete
    cascade 가 모두 본 join 기준. 본 row 자체에는 PII 가 없어야 함 — 실제 derived
    content 는 message body 에 있고, 본 join 은 관계만 보존.

    Phase 2 는 schema 만 — 실제 INSERT 는 Phase 5 (upload API + audit) / Phase 8 (share
    redact) / Phase 11 (ingest pipeline) / Phase 12 (SQL guard) 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAttachmentDerivedMessages (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AttachmentId BIGINT NOT NULL,
                MessageId BIGINT NOT NULL,
                DerivationType VARCHAR(24) NOT NULL,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                INDEX IX_WADM_Attachment (AttachmentId),
                INDEX IX_WADM_Message (MessageId),
                INDEX IX_WADM_Type (DerivationType, CreatedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_conversation_attachment_provider_files_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D13, R-F13): provider Files API lifecycle table.

    BRIEFING Revision 2 R-F13 흡수 — OpenAI Files API / Anthropic Files API 를 사용
    하여 inference 시 attachment bytes 를 provider 에 업로드할 때, provider 측에
    잔존하는 file object 의 lifecycle 추적. inference 직후 delete API 호출 + 실패 시
    `reconcile_provider_files` worker 의 TTL 기반 재시도.

    DeletedAt NULL = provider 측에 잔존, NOT NULL = 삭제 확인. Phase 2 는 schema 만 —
    실제 INSERT + delete 호출 + worker 는 Phase 5 (upload API base) / Phase 4 (storage
    wrapper) + 후속 cycle 의 provider integration 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachmentProviderFiles (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AttachmentId BIGINT NOT NULL,
                Provider VARCHAR(32) NOT NULL,
                ProviderFileId VARCHAR(255) NOT NULL,
                UploadedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DeletedAt DATETIME(6) NULL,
                LastDeleteAttemptAt DATETIME(6) NULL,
                DeleteAttemptCount INT NOT NULL DEFAULT 0,
                LastError VARCHAR(512) NULL,
                INDEX IX_WCAPF_Attachment (AttachmentId),
                INDEX IX_WCAPF_Provider (Provider, ProviderFileId),
                INDEX IX_WCAPF_Pending (DeletedAt, LastDeleteAttemptAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_audit_events_schema(conn) -> None:
    """REQ-20260519-0001 (TASK-0073, Critical §12.3): 전체 계정 행위 audit log.

    Approach B (admin 13 endpoint + user 4 endpoint = `/api/ask` / share create
    / share revoke / public share view) 의 모든 mutation 을 기록한다. CEO review
    9 decision + Codex outside voice 14 findings + Eng review 9 lock-in (E1-E9)
    의 최종 schema 다.

    핵심 column:
    - ActorAccountId (NULL = anonymous), ActorRoleId (snapshot),
      ActorType (`account` / `anonymous` / `system`)  -- E4 결정
    - TargetAccountId (NULL = no target) -- E1 self filter 의 OR 분기
    - ActionCode (`admin.account.update` / `conversation.ask` / `share.public.view` 등)
    - ChangeJson (allowlist builder 산출), MaskedFields (sensitive field 목록)
    - RemoteAddr, UserAgent, RequestId, SessionId

    Hook 정책 (Eng review E5):
    - admin endpoint 13 = direct dispatcher Same tx (fail-safe, audit 실패 = rollback)
    - user endpoint 4 = best-effort delegate (fail-open, TASK-0072 `_log_search_activity` 패턴)

    Index 정책 (E2 hybrid schema):
    - (ActorAccountId, OccurredAt) — admin `.any` filter + actor 검색
    - (TargetAccountId, OccurredAt) — E1 self OR branch
    - (ActionCode, OccurredAt) — action 별 filter
    - (ResourceType, ResourceId) — resource 별 추적
    - (ActorType, OccurredAt) — anonymous / system 분리 조회 (E4)

    `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서
    호출되어 idempotent 보장. (TASK-0086 에서 WebAccountActivity schema helper 는
    legacy table DROP 과 함께 제거됨 — 본 함수의 idempotent 호출 패턴은 동일.)
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAuditEvents (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ActorAccountId BIGINT NULL,
                ActorRoleId BIGINT NULL,
                ActorType VARCHAR(16) NOT NULL DEFAULT 'account',
                TargetAccountId BIGINT NULL,
                SessionId VARCHAR(64) NULL,
                ActionCode VARCHAR(64) NOT NULL,
                ResourceType VARCHAR(32) NOT NULL,
                ResourceId VARCHAR(64) NULL,
                ChangeJson JSON NULL,
                MaskedFields JSON NULL,
                RemoteAddr VARCHAR(64) NULL,
                UserAgent VARCHAR(255) NULL,
                RequestId VARCHAR(64) NULL,
                OccurredAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                INDEX IX_WAE_Actor (ActorAccountId, OccurredAt),
                INDEX IX_WAE_Target (TargetAccountId, OccurredAt),
                INDEX IX_WAE_Action (ActionCode, OccurredAt),
                INDEX IX_WAE_Resource (ResourceType, ResourceId),
                INDEX IX_WAE_ActorType (ActorType, OccurredAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()

def _ensure_web_audit_chain_schema(conn) -> None:
    """TASK-20260619T023922-audit-tamper-evidence (보안 ③, Critical §12.3): 감사 로그 변조방지 해시 체인.

    `WebAuditEvents` 에 `EventHash`/`PrevHash CHAR(64)` 멱등 ALTER + `WebAuditChainCheckpoint`
    (purge 경계 재앵커) 신설. `EventHash = SHA256(PrevHash | 정규화행)` 해시 체인.

    **위협모델(정직)**: 본 체인은 *tamper-EVIDENCE* 다 — 체인을 인지하지 못한 수정/삭제/삽입
    (SQL injection 버그·잘못된 마이그레이션·우발적 손상·내용 컬럼만 쓸 수 있는 부분권한 공격자)
    을 검증에서 탐지한다. 그러나 `WebAuditEvents` 전체 write 권한을 가진 공격자는 행을 고치고
    EventHash/PrevHash 를 재계산해 후속 행까지 re-chain 하거나(2a), tail 을 truncate 하거나(2b),
    checkpoint 를 위조해(5) 검증을 통과시킬 수 있다 — in-DB 체인 단독의 본질적 한계.
    이를 보완하려고 백그라운드 sealer 가 체인 head 해시를 **app 로그로 앵커**(off-DB)하며,
    로그를 외부 WORM/SIEM 으로 선적하면 외부 대조로 위 공격을 탐지할 수 있다. 강한 보장이
    필요하면 별 cycle 에서 head 해시의 주기적 외부 notarization(object-lock 버킷 등)을 추가한다
    (SECURITY.md §13).

    봉인(seal)은 `_seal_audit_chain` 이 GET_LOCK 직렬화 하에 미봉인 커밋행을 Id 순 일괄 처리
    (fork 방지, `EventHash IS NULL` 가드). 기존 행 NULL=미봉인(다음 seal 이 backfill).
    fast(`_ensure_seed_catchup`)+slow(`_ensure_web_tables`) 양 경로 — 기존 배포 자동 적용.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            "ALTER TABLE WebAuditEvents ADD COLUMN EventHash CHAR(64) NULL",
            "ALTER TABLE WebAuditEvents ADD COLUMN PrevHash CHAR(64) NULL",
            "CREATE INDEX IX_WAE_EventHash ON WebAuditEvents (EventHash)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS WebAuditChainCheckpoint (
                    Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    ThroughEventId BIGINT NOT NULL,
                    CheckpointHash CHAR(64) NOT NULL,
                    Reason VARCHAR(32) NOT NULL DEFAULT 'purge',
                    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                    INDEX IX_WACC_Through (ThroughEventId)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        except Exception:
            pass
    finally:
        cur.close()

def _migrate_web_account_activity_to_audit(conn) -> int:
    """REQ-20260519-0001 (TASK-0073 Phase A2): WebAccountActivity 기존 row 흡수.

    TASK-0072 의 cross-account body search audit row 를 신규 `WebAuditEvents` 로
    transform 한다. idempotent — `RequestId = CONCAT('account-activity:', waa.Id)`
    marker 로 두 번째 호출 시 NOT EXISTS subquery 가 skip.

    ChangeJson 에 `_migrated_from='WebAccountActivity'` + `_original_id=<id>` +
    `query_hash` + `matched_count` 보존. RemoteAddr / UserAgent NULL (TASK-0072
    schema 에는 부재). OccurredAt = waa.CreatedAt (시간 정합).

    **TASK-0086 (2026-05-20)**: WebAccountActivity 테이블 DROP 완료. 본 helper 는
    rollback 1~2 cycle window 동안 보존 (Codex outside voice C5 — code revert +
    DB restore 시나리오) — line 2813 의 `SHOW TABLES LIKE 'WebAccountActivity'`
    check 가 table-absent 시 silent return 0. rollback window 종료 후 별 cycle
    에서 helper 제거.

    `_ensure_seed_catchup` (fast path) 와 `_ensure_web_tables` (slow path) 양쪽
    호출 → 신규 / 기존 배포 모두 자동 흡수. 실패는 stderr only (main flow 차단 X).

    Returns: 새로 INSERT 된 row 수 (기존 marker 있는 row 는 skip, 또는 table
    부재 시 0).
    """
    cur = conn.cursor()
    try:
        # Pre-check: legacy table 존재 여부 (신규 배포에 부재해도 graceful skip).
        cur.execute("SHOW TABLES LIKE 'WebAccountActivity'")
        if not cur.fetchone():
            return 0
    except Exception:
        return 0
    finally:
        cur.close()

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO WebAuditEvents
              (ActorAccountId, ActorRoleId, ActorType, TargetAccountId, SessionId,
               ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields,
               RemoteAddr, UserAgent, RequestId, OccurredAt)
            SELECT
              waa.AccountId,
              NULL,
              'account',
              waa.TargetOwnerId,
              NULL,
              waa.Action,
              'conversation',
              CASE WHEN waa.TargetOwnerId IS NULL THEN NULL
                   ELSE CAST(waa.TargetOwnerId AS CHAR) END,
              JSON_OBJECT(
                'query_hash', waa.QueryHash,
                'matched_count', waa.MatchedCount,
                '_migrated_from', 'WebAccountActivity',
                '_original_id', waa.Id
              ),
              NULL,
              NULL,
              NULL,
              CONCAT('account-activity:', waa.Id),
              waa.CreatedAt
            FROM WebAccountActivity waa
            WHERE NOT EXISTS (
              SELECT 1 FROM WebAuditEvents wae
              WHERE wae.RequestId = CONCAT('account-activity:', waa.Id)
            )
            """
        )
        inserted = cur.rowcount or 0
        try:
            conn.commit()
        except Exception:
            pass
        if inserted > 0:
            try:
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0073 Phase A2] migrated {inserted} WebAccountActivity row(s) → WebAuditEvents\n"
                )
            except Exception:
                pass
        return int(inserted)
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0073 Phase A2] migration failed (legacy table preserved): {exc}\n"
            )
        except Exception:
            pass
        return 0
    finally:
        cur.close()

def _ensure_must_change_password_schema(conn) -> None:
    """TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0092): fast-path 재기동에서도
    MustChangePassword 컬럼이 존재하도록 idempotent ALTER. _ensure_web_tables 와 동일 SQL."""
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebAccounts ADD COLUMN MustChangePassword TINYINT(1) NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_login_lockout_schema(conn) -> None:
    """TASK-20260619T021356-login-attempt-limit (보안 ②): WebAccounts 에 로그인 실패 제한 컬럼 (멱등 ALTER).

    `FailedLoginAttempts`(연속 실패 누적, 성공/잠금 시 0 리셋)·`LockedUntilAt`(잠금 자동 해제
    시각, NULL=미잠금)·`LastFailedLoginAt`(관측용). 기존 행은 DEFAULT 0/NULL → 무회귀.
    fast-path(`_ensure_seed_catchup`)+slow-path(`_ensure_web_tables`) 양쪽 호출
    (`_ensure_must_change_password_schema` idiom 동형) — 기존 배포 자동 적용.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            "ALTER TABLE WebAccounts ADD COLUMN FailedLoginAttempts INT NOT NULL DEFAULT 0",
            "ALTER TABLE WebAccounts ADD COLUMN LockedUntilAt DATETIME NULL",
            "ALTER TABLE WebAccounts ADD COLUMN LastFailedLoginAt DATETIME NULL",
            "CREATE INDEX IX_WebAccounts_LockedUntil ON WebAccounts (LockedUntilAt)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
    finally:
        cur.close()

def _ensure_llm_quota_schema(conn) -> None:
    """TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 토큰 사용량 한도 테이블 (멱등 CREATE).

    `WebRoleTokenQuotas`(역할별 기본)·`WebAccountTokenQuotas`(계정별 특수/override). QuotaType=
    'daily'|'monthly', TokenLimit BIGINT(0=무제한 명시). 미존재 행=상속(계정→역할→무제한).
    RBAC override 패턴(WebRolePermissions+WebAccountPermissionOverrides) 미러. fast+slow 양 경로.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            """
            CREATE TABLE IF NOT EXISTS WebRoleTokenQuotas (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                RoleId BIGINT NOT NULL,
                QuotaType VARCHAR(16) NOT NULL,
                TokenLimit BIGINT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY UQ_WRTQ (RoleId, QuotaType)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            """
            CREATE TABLE IF NOT EXISTS WebAccountTokenQuotas (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AccountId BIGINT NOT NULL,
                QuotaType VARCHAR(16) NOT NULL,
                TokenLimit BIGINT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY UQ_WATQ (AccountId, QuotaType)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
    finally:
        cur.close()

def _ensure_oauth_identity_schema(conn) -> None:
    """TASK-20260619T034522-oauth-google-foundation (REQ-20260619-0328, SECURITY.md §15):
    WebAccounts 에 외부 IdP(Google OAuth) 신원 매핑 컬럼 idempotent ALTER.

    - `Email VARCHAR(320) NULL`: OAuth 신원 또는 향후 이메일 식별용. 기존 행 NULL = 무회귀.
      (RFC 5321 local 64 + @ + domain 255 = 320.)
    - `AuthProvider VARCHAR(32) NULL`: 'google' 등. NULL = 로컬(비번) 계정.
    - `OAuthSubject VARCHAR(255) NULL`: IdP 의 안정적 사용자 식별자(Google `sub`).
    - UNIQUE (AuthProvider, OAuthSubject): 동일 IdP 신원 중복 계정 차단(부분 NULL 은 MySQL
      에서 UNIQUE 제약 면제 → 로컬 계정 다수 공존 가능).
    - UNIQUE (Email): 이메일 기준 계정 link 일관성(NULL 다수 허용).

    기본 비활성 토대 — 컬럼만 추가하고 런타임 인증 경로는 OAUTH_GOOGLE_ENABLED OFF 면 무영향.
    `_ensure_login_lockout_schema` idiom 동형 — fast-path(_ensure_seed_catchup) +
    slow-path(_ensure_web_tables) 양쪽 호출로 기존 배포 자동 적용.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            "ALTER TABLE WebAccounts ADD COLUMN Email VARCHAR(320) NULL",
            "ALTER TABLE WebAccounts ADD COLUMN AuthProvider VARCHAR(32) NULL",
            "ALTER TABLE WebAccounts ADD COLUMN OAuthSubject VARCHAR(255) NULL",
            "CREATE UNIQUE INDEX UX_WebAccounts_OAuth ON WebAccounts (AuthProvider, OAuthSubject)",
            "CREATE UNIQUE INDEX UX_WebAccounts_Email ON WebAccounts (Email)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
    finally:
        cur.close()

def _ensure_web_account_totp_schema(conn) -> None:
    """TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA TOTP 저장 테이블 (멱등 CREATE).

    `WebAccountTotp`: AccountId PK·SecretEnc(cred_crypto AESGCM 암호문)·EncryptionVersion(DEK 버전)·
    Enabled(0=등록 미확인, 1=활성)·BackupCodesJson(백업코드 sha256 해시 1회용)·ConfirmedAt.
    미존재 행 = 2FA 미사용(무회귀). fast+slow 양 경로.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAccountTotp (
                AccountId BIGINT PRIMARY KEY,
                SecretEnc TEXT NOT NULL,
                EncryptionVersion INT NOT NULL,
                Enabled TINYINT(1) NOT NULL DEFAULT 0,
                BackupCodesJson TEXT NULL,
                ConfirmedAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    except Exception:
        pass
    finally:
        cur.close()

def _ensure_web_api_tokens_schema(conn) -> None:
    """feature-0023 (REQ-20260722-conversation-api-access): 외부 AI 프로그래매틱 접근용
    Bearer API 토큰 테이블 (멱등 CREATE).

    세션 쿠키(WebAuthSessions)와 별개로, 저권한 서비스 계정에 귀속된 장수명 토큰을
    보관한다. **토큰 원문은 저장하지 않고 SHA-256 해시(`TokenHash`)만 저장** — 세션
    토큰(SessionTokenHash)·share 토큰(token_prefix) 패턴 답습. 인증 경로
    (`web_context._get_authenticated_account`)가 쿠키 부재 시 `Authorization: Bearer`
    를 이 테이블로 조회한다.

    컬럼:
      - AccountId          : 토큰이 귀속되는 WebAccounts.Id (그 계정의 RBAC 적용).
      - TokenHash CHAR(64) : SHA-256 hex. UNIQUE (조회 키).
      - TokenPrefix        : 원문 앞 12자(식별/로그용, 민감도 낮음 — full token 아님).
      - Label              : 사람이 읽는 용도 라벨("n8n integration" 등).
      - Scopes             : 콤마구분 권한 접두 allowlist(예: "conversation."). NULL =
                             서비스 계정 권한 전체(권장 안 함 — 항상 scope 지정).
      - ExpiresAt          : 만료 시각(DB 시계 기준). NULL = 무기한.
      - LastUsedAt         : 마지막 사용 시각(관측/미사용 토큰 식별).
      - RevokedAt          : 폐기 시각. NOT NULL = 인증 거부.
      - CreatedByAccountId : 발급자(운영자) 계정. CLI 발급 시 서비스 계정/운영자.

    fast-path(_ensure_seed_catchup)·slow-path(_ensure_web_tables) 양쪽 호출
    (_ensure_llm_quota_schema idiom 동형) — 기존 배포 자동 적용. additive·비파괴.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebApiTokens (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AccountId BIGINT NOT NULL,
                TokenHash CHAR(64) NOT NULL,
                TokenPrefix VARCHAR(16) NOT NULL,
                Label VARCHAR(128) NULL,
                Scopes VARCHAR(512) NULL,
                ExpiresAt DATETIME NULL,
                LastUsedAt DATETIME NULL,
                CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CreatedByAccountId BIGINT NULL,
                RevokedAt DATETIME NULL,
                UNIQUE KEY UQ_WebApiTokens_Hash (TokenHash),
                KEY IX_WebApiTokens_Account (AccountId),
                KEY IX_WebApiTokens_Active (RevokedAt, ExpiresAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    except Exception:
        pass
    finally:
        cur.close()


def _ensure_oauth_client_schema(conn) -> None:
    """feature-0041 (REQ-20260812-external-ai-tool-surface): 외부 AI 도구 표면의 OAuth
    authorization-server 저장 계약 (멱등 CREATE — `_ensure_web_api_tokens_schema` idiom 동형).

    feature-0023 의 Bearer 토큰은 **운영자가 CLI 로 발급**하는 장수명 자격증명이라 "사용자별
    신원" 도 "세션 실재" 도 담지 못한다. 본 feature 는 신원을 **우리 로그인 세션**으로 못박으므로
    (사람이 브라우저에서 로그인·동의) authorization-code 흐름과 그 저장 계약이 필요하다.

    **codex REV-20260812-0001 P1 반영 — 저장 계약이 곧 보안 경계다:**
      · 인가 코드는 **1회용**(`ConsumedAt` NOT NULL 이면 거절) + 단TTL + 발급 시
        `(ClientId, RedirectUri, CodeChallenge)` 에 결합 — 셋 중 하나라도 교환 시점에 다르면 거절.
      · access/refresh 는 **해시만 저장**(평문 컬럼 없음). `WebApiTokens.TokenHash` 규약 재사용.
      · refresh 는 **rotation** 하며, 이미 교체된 refresh 가 다시 오면(**reuse**) 그 `FamilyId`
        계열 전체를 폐기한다 — 토큰 탈취를 탐지하는 사실상 유일한 신호다.
      · `SessionId` 로 웹 세션에 결합 — 사용자가 브라우저에서 로그아웃하면 그 세션에서 파생된
        토큰이 함께 죽는다(= "세션 실재" 요구의 집행면).

    **DCR redirect 정책(codex P1)**: `RedirectUris` 는 등록 시 검증된 값만 담고, 인가 시
    **정확 일치**로만 매칭한다(prefix·와일드카드 금지). HTTPS 고정 + loopback 예외는 애플리케이션
    (`routers/oauth_as.py::_validate_redirect_uri`)이 강제하며, 본 스키마는 그 결과를 보관만 한다.

    fast-path(`_ensure_seed_catchup`)·slow-path(`_ensure_web_tables`) 양쪽 호출 — 기존 배포
    자동 적용. additive·비파괴.

    ⚠ **`conn.cursor()` 까지 try 안에 둔다 (LRN 반복 결함 + catchup abort)**: 본 함수는
    `_ensure_seed_catchup` (운영 재기동 fast path) 의 **중간**에서 호출되고, 그 함수는 항목마다
    try 로 감싸지 않는다 — 여기서 예외가 새면 **뒤따르는 catchup 항목이 전부 조용히 skip** 된다
    (gdrive 토큰 · 아바타 컬럼 · 첨부 버전 · DB allowlist 규칙 · **audit events** · **audit chain**).
    `docs/LEARNINGS.md` 의 seed-catchup abort 사례와 동일 기전이므로, 커서 획득 실패도 이 함수
    안에서 흡수한다. 신규 테이블 부재는 이 feature 의 엔드포인트만 실패시키지만(fail-closed),
    catchup 중단은 무관한 서브시스템을 조용히 망가뜨린다 — 후자가 훨씬 나쁘다.
    """
    cur = None
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS WebOAuthClients (
                    Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    ClientId VARCHAR(64) NOT NULL,
                    ClientName VARCHAR(128) NULL,
                    RedirectUris TEXT NOT NULL,
                    RegisteredIp VARCHAR(64) NULL,
                    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    LastUsedAt DATETIME NULL,
                    RevokedAt DATETIME NULL,
                    UNIQUE KEY UQ_WebOAuthClients_ClientId (ClientId),
                    KEY IX_WebOAuthClients_Created (CreatedAt),
                    KEY IX_WebOAuthClients_Ip (RegisteredIp, CreatedAt)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS WebOAuthGrants (
                    Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    CodeHash CHAR(64) NOT NULL,
                    ClientId VARCHAR(64) NOT NULL,
                    AccountId BIGINT NOT NULL,
                    SessionId BIGINT NULL,
                    RedirectUri VARCHAR(512) NOT NULL,
                    CodeChallenge VARCHAR(128) NOT NULL,
                    CodeChallengeMethod VARCHAR(8) NOT NULL DEFAULT 'S256',
                    Scopes VARCHAR(512) NULL,
                    ExpiresAt DATETIME NOT NULL,
                    ConsumedAt DATETIME NULL,
                    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY UQ_WebOAuthGrants_Code (CodeHash),
                    KEY IX_WebOAuthGrants_Expires (ExpiresAt)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS WebOAuthTokens (
                    Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    TokenHash CHAR(64) NOT NULL,
                    TokenType VARCHAR(8) NOT NULL,
                    FamilyId CHAR(32) NOT NULL,
                    ClientId VARCHAR(64) NOT NULL,
                    AccountId BIGINT NOT NULL,
                    SessionId BIGINT NULL,
                    Scopes VARCHAR(512) NULL,
                    ExpiresAt DATETIME NOT NULL,
                    ReplacedAt DATETIME NULL,
                    RevokedAt DATETIME NULL,
                    LastUsedAt DATETIME NULL,
                    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY UQ_WebOAuthTokens_Hash (TokenHash),
                    KEY IX_WebOAuthTokens_Family (FamilyId),
                    KEY IX_WebOAuthTokens_Account (AccountId),
                    KEY IX_WebOAuthTokens_Session (SessionId),
                    KEY IX_WebOAuthTokens_Active (RevokedAt, ExpiresAt)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        except Exception:
            pass
        try:
            # task 세션 계약(feature-0041): 외부 AI 의 한 작업 단위. 모든 도구 호출이 여기 묶이고,
            # 원 질문(open)·최종 답변(submit)이 서비스 측 대화로 흘러가는 근거가 된다.
            # `SubmittedAt IS NULL` 로 남은 task 가 곧 **미제출률** — 자발적 제출을 강제할 수는
            # 없으므로(구조적 한계) 측정해서 소프트 강제하는 것이 유일한 수단이다.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS WebAiTasks (
                    Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    TaskId VARCHAR(64) NOT NULL,
                    AccountId BIGINT NOT NULL,
                    ClientId VARCHAR(64) NULL,
                    ConversationId VARCHAR(255) NULL,
                    ProductId BIGINT NULL,
                    Question TEXT NULL,
                    Status VARCHAR(16) NOT NULL DEFAULT 'open',
                    InjectionVerdict VARCHAR(16) NULL,
                    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    SubmittedAt DATETIME NULL,
                    -- feature-0043: 웹 브리지 축. 신규 설치는 여기서 만들어지므로 아래 멱등
                    -- ALTER 루프가 돌지 않는다(ALTER 는 기존 설치의 1회성 마이그레이션 전용).
                    Origin VARCHAR(16) NOT NULL DEFAULT 'external',
                    ClaimedBy BIGINT NULL,
                    ClaimedAt DATETIME NULL,
                    -- 점유한 **세션**(OAuth client). 계정만으로는 같은 계정의 다른 세션이
                    -- claim 없이 제출하는 것을 막지 못한다.
                    ClaimedClient VARCHAR(64) NULL,
                    -- 답변이 원 대화에 실제로 실렸는가. `Status='submitted'` 와 분리해야
                    -- "제출은 됐는데 화면엔 없다" 를 구분해 재전달할 수 있다.
                    Delivered TINYINT(1) NOT NULL DEFAULT 0,
                    UNIQUE KEY UQ_WebAiTasks_TaskId (TaskId),
                    KEY IX_WebAiTasks_Account (AccountId, CreatedAt),
                    KEY IX_WebAiTasks_Client (ClientId, CreatedAt),
                    KEY IX_WebAiTasks_Open (Status, CreatedAt),
                    -- 브리지 폴링 전용. `(AccountId, CreatedAt)` 만으로는 그 계정의 과거
                    -- external·submitted task 까지 전부 훑어, 상주 러너의 주기 조회가 대화가
                    -- 쌓일수록 무거워진다(codex 리뷰 P2-3).
                    KEY IX_WebAiTasks_Bridge (AccountId, Origin, Status, ClaimedBy, CreatedAt)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        except Exception:
            pass
        # AC-7(대화 적재) — 답변 보존 컬럼. 2026-08-14 까지 `submit_answer` 는 Status 만 갱신했고
        # 답변 본문은 어디에도 남지 않았다(원장에 bytes_out 수치로만). 사용자 요구
        # ("외부 AI 세션의 대화 기록 또한 우리 쪽에 남겨야 합니다", 2026-08-12)의 답변 축이다.
        #
        # 멱등 추가 — `WebProductDatabases.DatasourceKey` idiom 복제. 실패를 **삼키지 않고**
        # logging.error 로 올린다: 컬럼이 없으면 저장 경로가 fail-closed 로 꺼지므로 누출은
        # 없지만, 운영자가 "보존되고 있다" 고 오해하면 안 된다(이 feature 의 반복 결함).
        # ⚠ 모든 ALTER 에 `ALGORITHM=INPLACE, LOCK=NONE` 필수 (CONVENTIONS §13.1 ·
        # `bin/mysql-ddl-lint.sh` 가 diff-mode 로 강제). agent_memory 는 replica 없는 단일
        # 인스턴스라 silent COPY 로 떨어지면 그 테이블 DML 이 락에 걸려 체감 중단이 된다.
        # LOCK=NONE 의 의도는 online 불가 시 **에러로 표면화**하는 것이다(조용한 락 금지).
        # (lint 는 텍스트 스캐너다 — 상수 결합으로 빼면 따라오지 못하므로 절을 리터럴로 둔다.)
        for _col, _ddl in (
            # 각인(datamark)된 답변 본문. TEXT(64KB) 는 실측 6~8KB 답변에 여유가 없어 MEDIUMTEXT.
            ("Answer", "ALTER TABLE WebAiTasks ADD COLUMN Answer MEDIUMTEXT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # **원문** 바이트 수(각인 래퍼 제외). 원장 bytes_out 과 대조 가능해야 한다.
            ("AnswerBytes", "ALTER TABLE WebAiTasks ADD COLUMN AnswerBytes INT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # 답변에 대한 인젝션 3단 판정. 질문의 InjectionVerdict 와 같은 축.
            ("AnswerVerdict", "ALTER TABLE WebAiTasks ADD COLUMN AnswerVerdict VARCHAR(16) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # 상한 초과로 절단됐는지. 조용한 절단을 금지하기 위한 가시 플래그.
            ("AnswerTruncated", "ALTER TABLE WebAiTasks ADD COLUMN AnswerTruncated TINYINT(1) NOT NULL DEFAULT 0, ALGORITHM=INPLACE, LOCK=NONE"),
            # 외부 AI 가 선언한 근거 task 목록(교차오염 대조 입력). 판정과 함께 남겨야 사후에
            # "무엇을 근거로 썼다고 주장했는가" 를 재구성할 수 있다.
            ("SourceTasks", "ALTER TABLE WebAiTasks ADD COLUMN SourceTasks TEXT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # ADR-003 관찰: 어느 datasource 를 본 답변인지 기록 자체에 남으면, 이후 제품
            # 바인딩이 교체돼도 "이 답변은 그때 그 DB 를 본 것" 이 자명해진다. 2026-08-14 의
            # `dbauth` 혼동이 정확히 이 정보의 부재에서 왔다.
            ("DatasourceKey", "ALTER TABLE WebAiTasks ADD COLUMN DatasourceKey VARCHAR(128) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # ── feature-0043 (external-llm-bridge, 2026-08-26) — 웹 대화 pull 브리지 ──
            # 웹 대화창의 질문이 서버 LLM 대신 이 테이블의 **대기 작업**이 되고, 사용자의 개인 머신
            # AI 가 MCP/REST 로 가져가 답한다. 기존 외부 AI 개설 task(`Origin='external'`)와 같은
            # 테이블을 쓰되 출처로 구분한다 — 별도 테이블을 만들면 원장·각인·판정 경로가 두 벌이 된다.
            #
            # `ConversationId` 는 이미 위 CREATE TABLE 에 있다(외부 task 는 NULL). 웹 브리지 task 는
            # 이 값으로 대화창에 답변을 되돌려 붙인다.
            ("Origin", "ALTER TABLE WebAiTasks ADD COLUMN Origin VARCHAR(16) NOT NULL DEFAULT 'external', ALGORITHM=INPLACE, LOCK=NONE"),
            # 점유자(계정). NULL = 아직 아무도 집지 않음. 점유는 SQL `WHERE ClaimedBy IS NULL` 안에서
            # 원자적으로 일어나야 한다(애플리케이션 층 선조회 후 UPDATE 는 TOCTOU).
            ("ClaimedBy", "ALTER TABLE WebAiTasks ADD COLUMN ClaimedBy BIGINT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            ("ClaimedAt", "ALTER TABLE WebAiTasks ADD COLUMN ClaimedAt DATETIME NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # 점유 세션(OAuth client). 계정 단위 조건만으로는 같은 계정의 다른 세션이
            # claim 을 건너뛰고 제출할 수 있어 원자적 점유가 소유권으로 집행되지 않는다.
            ("ClaimedClient", "ALTER TABLE WebAiTasks ADD COLUMN ClaimedClient VARCHAR(64) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # 대화 전달 성공 여부. `Status='submitted'` 만으로 "답변이 화면에 있다" 를 단정하면
            # 저장 실패 시 사용자에게는 답이 없는데 시스템은 완료로 보는 상태가 굳는다.
            ("Delivered", "ALTER TABLE WebAiTasks ADD COLUMN Delivered TINYINT(1) NOT NULL DEFAULT 0, ALGORITHM=INPLACE, LOCK=NONE"),
            # ── 사용감 패리티(2026-08-27) — 브리지 답변이 기존 답변과 **같은 각인**을 갖게 하는 값들.
            #
            # `ProductMode`: 'auto' | 'pinned'. 답변 말풍선의 제품 귀속(msg-speaker-attribution)은
            # `_answer_product_attribution(product_id, product_mode)` 로 각인되는데, mode 없이
            # ProductId 만으로는 "제품 미고정 답변(auto)" 과 "고정 답변" 을 구분할 수 없다. 구분에
            # 실패하면 각인이 빠지고, FE 는 컴포저의 **현재** 제품 칩으로 폴백해 그린다 — 제품을
            # 바꾸는 순간 과거 답변의 발화자까지 소급 변경된다(기존 경로가 이미 고친 결함).
            ("ProductMode", "ALTER TABLE WebAiTasks ADD COLUMN ProductMode VARCHAR(16) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # `SenderUsername`: 그룹 대화 발신자 귀속(gc-ask-sender-attrib). 그룹에서는 여러 명이
            # 같은 대화에 @assistant 를 부르므로, 질문 말풍선이 **누구 것인지** 각인돼야 한다
            # (`app.js` 가 `meta.sender_username` 을 읽어 표시한다). 각인이 없으면 그룹 대화의
            # 모든 질문이 발신자 없는 말풍선이 된다.
            ("SenderUsername", "ALTER TABLE WebAiTasks ADD COLUMN SenderUsername VARCHAR(128) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # `AttachmentIds`: 이 질문에 딸린 첨부 id 목록(CSV). 브리지 AI 가 "무엇이 첨부됐는지"
            # 조차 모르면 첨부 기반 질문에 엉뚱하게 답한다 — 목록을 실어 최소한 인지시킨다.
            ("AttachmentIds", "ALTER TABLE WebAiTasks ADD COLUMN AttachmentIds TEXT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # ── 요청 품질 설정(2026-08-27 사용자 제보) ───────────────────────────────
            #
            # 웹 컴포저의 **모델**·**추론 강도** 선택은 기존 경로에서 그 요청의 LLM 호출을
            # 지배한다. 브리지는 그 둘을 통째로 버려, 사용자가 무엇을 고르든 답변이 달라지지
            # 않았다 — 화면은 선택지를 주는데 실제로는 아무 효과가 없는 **거짓 조작면**이다.
            #
            # 답은 개인 AI 가 만들므로 서버가 강제할 수는 없다. 대신 **요청 시점의 의도를
            # 굳혀** AI 에게 전달한다(각인과 같은 이유 — 나중에 대화 설정을 바꿔도 이 요청에
            # 대해 무엇이 요구됐는지가 변하지 않는다).
            ("RequestedModel", "ALTER TABLE WebAiTasks ADD COLUMN RequestedModel VARCHAR(64) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            ("ReasoningLevel", "ALTER TABLE WebAiTasks ADD COLUMN ReasoningLevel VARCHAR(16) NULL, ALGORITHM=INPLACE, LOCK=NONE"),
            # `RoleId`: 시스템 프롬프트 5단계(전역·제품·역할·계정·개인) 조립에 필요하다.
            # 브리지는 `agent_core.compose_system_prompt` 를 타지 않으므로, 그 프롬프트를 서버가
            # 대신 조립해 AI 에게 넘겨야 한다 — 그러려면 요청 시점의 역할이 남아 있어야 한다.
            # 없으면 운영자가 설정한 역할별 지침이 브리지 답변에서만 통째로 사라진다.
            ("RoleId", "ALTER TABLE WebAiTasks ADD COLUMN RoleId BIGINT NULL, ALGORITHM=INPLACE, LOCK=NONE"),
        ):
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME='WebAiTasks' AND COLUMN_NAME=%s", (_col,))
                if int((cur.fetchone() or [0])[0]) > 0:
                    continue
                cur.execute(_ddl)
            except Exception as _alter_exc:
                logging.getLogger(__name__).error(
                    "[ai-task] WebAiTasks.%s 컬럼 추가 실패 — 외부 AI 답변 보존이 비활성화된다"
                    "(런타임 fail-closed: submit_answer 가 5xx). 운영자 수동 ALTER 필요: %r",
                    _col, _alter_exc,
                )

        # feature-0043 (codex 리뷰 P2-3) — 브리지 폴링 전용 복합 인덱스.
        # 상주 러너가 주기적으로 `WHERE AccountId=? AND Origin='web' AND Status='open'
        # AND ClaimedBy IS NULL ORDER BY CreatedAt` 를 돈다. 기존 `(AccountId, CreatedAt)` 로는
        # 그 계정의 과거 external·submitted task 까지 전부 훑어, 대화가 쌓일수록 폴링이 무거워진다.
        # 신규 설치는 위 CREATE TABLE 이 이미 만들었으므로 여기서는 skip 된다.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebAiTasks' AND INDEX_NAME='IX_WebAiTasks_Bridge'")
            if int((cur.fetchone() or [0])[0]) == 0:
                cur.execute(
                    "ALTER TABLE WebAiTasks ADD INDEX IX_WebAiTasks_Bridge "
                    "(AccountId, Origin, Status, ClaimedBy, CreatedAt), "
                    "ALGORITHM=INPLACE, LOCK=NONE")
        except Exception as _idx_exc:
            # 인덱스 부재는 기능을 막지 않는다(느려질 뿐) — fail-closed 대상이 아니다.
            # 다만 조용히 넘기면 "왜 폴링이 무겁지" 를 추적할 단서가 사라진다.
            logging.getLogger(__name__).error(
                "[ai-task] WebAiTasks 브리지 인덱스 추가 실패 — 폴링이 full scan 으로 "
                "떨어진다(기능은 유지). 운영자 수동 ALTER 권장: %r", _idx_exc)
    except Exception:
        # 커서 획득 실패 등 — 여기서 흡수한다(catchup 체인 보호, 위 docstring 참조).
        pass
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass


def _ensure_avatar_icon_schema(conn) -> None:
    """TASK-0268/0293: fast-path 재기동에서도 WebAccounts.AvatarObjectKey / WebProducts.IconObjectKey
    / WebRoles.IconObjectKey 컬럼이 존재하도록 idempotent ALTER. _ensure_web_tables 의 CREATE 와 동일
    의미 — 운영 재기동은 slow path (_ensure_web_tables) 를 안 타고 _ensure_seed_catchup 만 타므로, 계정
    SELECT(a.AvatarObjectKey)·제품 SELECT(IconObjectKey)·역할 SELECT(r.IconObjectKey) 가
    'Unknown column' 으로 깨지지 않게 양쪽 경로에 ALTER 를 둔다."""
    cur = conn.cursor()
    try:
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN AvatarObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN IconObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        # TASK-0293: 역할 아이콘 이미지 — MinIO object key (NULL=미설정 → 프론트 Identicon 폴백).
        try:
            cur.execute("ALTER TABLE WebRoles ADD COLUMN IconObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
    finally:
        cur.close()

def _ensure_attachment_version_schema(conn) -> None:
    """TASK-0274: WebConversationAttachments 의 버전 관리 컬럼 idempotent ALTER.

    assistant 가 전달받은 첨부를 수정해 새 버전으로 materialize 하는 기능(Task⑥)의
    스키마 토대. 첨부는 MySQL(agent_memory) 전용 테이블이라 PG/alembic 무관 — avatar
    선례(_ensure_avatar_icon_schema)와 동형으로 fast-path(_ensure_seed_catchup)·
    slow-path(_ensure_web_tables) 양쪽에서 호출해 'Unknown column' 회귀를 막는다.

    컬럼:
      - RootAttachmentId  : 버전 체인 루트(원본) 첨부 Id. NULL = 자기 자신이 루트.
      - VersionNumber     : 1부터 증가. 같은 RootAttachmentId 내 단조 증가.
      - CreatedByRole      : 'user'(사용자 업로드) | 'assistant'(LLM materialize).
      - SupersededAt       : 이 버전이 더 새로운 버전으로 대체된 시각. NULL = 최신.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            "ALTER TABLE WebConversationAttachments ADD COLUMN RootAttachmentId BIGINT NULL",
            "ALTER TABLE WebConversationAttachments ADD COLUMN VersionNumber INT NOT NULL DEFAULT 1",
            "ALTER TABLE WebConversationAttachments ADD COLUMN CreatedByRole VARCHAR(16) NOT NULL DEFAULT 'user'",
            "ALTER TABLE WebConversationAttachments ADD COLUMN SupersededAt DATETIME(6) NULL",
            # 버전 체인 (root, version) 유일성. NULL root(원본)는 중복 허용 — 기존 데이터 무충돌.
            "ALTER TABLE WebConversationAttachments ADD UNIQUE KEY UQ_WCA_VersionChain (RootAttachmentId, VersionNumber)",
            # REQ-20260814-attach-createdat-utc: CreatedAt 을 **UTC** 로 기록한다.
            #   종전 DEFAULT `CURRENT_TIMESTAMP(6)` 는 서버 세션 TZ(이 배포는 `time_zone=SYSTEM` =
            #   KST)를 따라 **로컬 시각**을 넣었다. 반면 같은 테이블의 SupersededAt/DeletedAt 은
            #   코드가 `UTC_TIMESTAMP(6)` 로 넣고, 메시지 저장도 UTC 다 — 한 테이블 안에서 축이
            #   갈려 "생성이 삭제보다 나중" 인 모순 행이 실제로 쌓였다(라이브 실측 234건).
            #   INSERT 경로가 CreatedAt 을 명시하지 않으므로 DEFAULT 를 바꾸면 전 경로가 정합해지고
            #   앞으로 추가될 경로도 자동으로 안전하다. `ALTER COLUMN ... SET DEFAULT` 는 메타데이터
            #   전용이라 테이블 rebuild 가 없고 반복 실행에도 멱등이다(MySQL 8.0.13+ 표현식 DEFAULT).
            "ALTER TABLE WebConversationAttachments ALTER COLUMN CreatedAt SET DEFAULT (UTC_TIMESTAMP(6))",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
    finally:
        cur.close()

def _ensure_seed_catchup(conn) -> None:
    """기존 배포에 신규 seed role/prompt 가 있으면 상태를 맞춘다.

    `_schedule_memory_runtime_bootstrap` 의 fast path 에서 호출한다. 모든 seed
    ensure 함수는 존재 여부를 먼저 확인해 건드리지 않으므로 매 재기동마다 호출
    해도 안전하다. TASK-0044 에서 sales role + role-scope system prompt 를 기존
    배포에 합류시키기 위해 도입.
    """
    # REQ-20260518-0001: catalog hydrate 를 seed_roles 앞으로 옮긴다.
    # app._ensure_seed_roles 의 admin/operator/sales catchup 이 _permission_id_map(conn) 으로
    # PermissionId 를 lookup 하므로, 신규 권한이 catalog 에 먼저 INSERT 되어 있어야
    # 기존 배포에 grant 가 보정된다 (Codex review risk 3 변형).
    app._ensure_permission_catalog(conn)
    app._ensure_seed_roles(conn)
    app._ensure_seed_products(conn)
    _ensure_seed_role_system_prompts(conn)
    # TASK-0095: 기존 배포는 fast-path 만 타기 때문에 GLOBAL scope row 가 부재한 채로 남는다.
    # idempotent — row 가 이미 있으면 건드리지 않으며, agent_core import 실패 시 silent skip 한다.
    _ensure_seed_global_system_prompt(conn)
    # TASK-0052 Phase 1B: fast-path 재기동에서도 신규 dynamic permission 컬럼 + product 권한 backfill 실행.
    _ensure_dynamic_permissions_schema(conn)
    # TASK-0205: DB 기반 datasource 레지스트리 테이블 fast-path 보정.
    _ensure_web_datasources_schema(conn)
    # TASK-0206: 데이터 MySQL 데이터소스 시드 + NULL 바인딩 마이그레이션 (fast-path).
    app._seed_main_mysql_datasource(conn)
    # TASK-0206: 구 MSSQL 제품(참조 DB)을 DB-단위 접근목록으로 일회성 이전 (fast-path).
    _migrate_mssql_products_to_db_level(conn)
    # TASK-0211: .env 분석 데이터소스(DS_*)를 DB 레지스트리로 이전 (fast-path).
    _migrate_env_datasources_to_db(conn)
    # REQ-20260514-0001: 공유 링크 테이블 fast-path 보정.
    _ensure_web_conversation_shares_schema(conn)
    # TASK-0094 Sprint 1 Phase 2 (R-F7): share-policy version column ALTER.
    _ensure_web_share_links_policy_version_column(conn)
    # TASK-20260619T012028-share-link-expiry (SECURITY.md §7.2): 공유 링크 만료 column ALTER.
    _ensure_web_share_links_expiry_column(conn)
    _ensure_web_share_links_joinable_column(conn)  # feature-0009: 공유 링크 참여 허용 컬럼
    _ensure_web_share_links_floor_column(conn)  # share-visibility-window: 하단 경계("여기부터 공유")
    # TASK-0094 Sprint 1 Phase 2: 첨부 metadata + sandbox mapping +
    # derived join + provider files lifecycle 4 신규 테이블 fast-path 보정.
    _ensure_web_conversation_attachments_schema(conn)
    _ensure_web_conversation_attachments_sandbox_schemas_schema(conn)
    _ensure_web_attachment_derived_messages_schema(conn)
    _ensure_web_conversation_attachment_provider_files_schema(conn)
    # TASK-0061 Phase 6: 기존 배포에 MustChangePassword 컬럼 backfill.
    _ensure_must_change_password_schema(conn)
    # TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 컬럼 fast-path 보정.
    _ensure_login_lockout_schema(conn)
    # TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 사용량 한도 테이블 (fast path).
    _ensure_llm_quota_schema(conn)
    # TASK-20260619T034522-oauth-google-foundation (REQ-20260619-0328): Google OAuth 신원 매핑 컬럼 fast-path 보정.
    _ensure_oauth_identity_schema(conn)
    # TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA TOTP 테이블 (fast path).
    _ensure_web_account_totp_schema(conn)
    # feature-0023 (REQ-20260722-conversation-api-access): Bearer API 토큰 테이블 (fast path).
    _ensure_web_api_tokens_schema(conn)
    # feature-0041 (REQ-20260812-external-ai-tool-surface): OAuth AS 저장 계약 3종 (fast path).
    _ensure_oauth_client_schema(conn)
    # TASK-20260623T190000-gdrive-foundation (feature-0010): 계정별 Google Drive 토큰 테이블 (fast path).
    _ensure_web_gdrive_tokens_schema(conn)
    # TASK-0268: 아바타/아이콘 object key 컬럼 fast-path 보정(slow path _ensure_web_tables 미경유 재기동 대비).
    _ensure_avatar_icon_schema(conn)
    # TASK-0274: 첨부 버전 관리 컬럼(RootAttachmentId/VersionNumber/CreatedByRole/SupersededAt) fast-path 보정.
    _ensure_attachment_version_schema(conn)
    # TASK-20260618T044318/061703: DB allowlist 규칙 테이블 + Source/RuleId + 다중규칙(UNIQUE 제거·SortOrder)
    #   fast-path 보정 — slow path 안 타는 재기동에서도 다중규칙 마이그레이션이 반영되도록(MAJOR#2 재리뷰).
    _ensure_web_product_db_rules_schema(conn)
    # REQ-20260519-0001 (TASK-0073, Phase A0): 전체 행위 audit log 테이블 fast-path 보정.
    _ensure_web_audit_events_schema(conn)
    # TASK-20260619T023922-audit-tamper-evidence (보안 ③): 감사 해시 체인 컬럼/체크포인트 (fast path).
    _ensure_web_audit_chain_schema(conn)
    # REQ-20260520-0001 (TASK-0086): WebAccountActivity DROP 완료. migration helper 는
    # rollback 1~2 cycle window 동안 보존 — table 부재 시 SHOW TABLES check 로 silent skip.
    try:
        _migrate_web_account_activity_to_audit(conn)
    except Exception:
        pass
    _migration_added = _ensure_product_access_permissions(conn)
    if _migration_added > 0:
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0052 Phase 1B catchup] product access backfill: {_migration_added} permission/role-permission rows added\n"
            )
        except Exception:
            pass
    # model-access-rbac(2026-07-28): slow path(catchup)에서도 모델 접근 권한 보장 — 기존 배포가
    # fast path 를 타지 않는 경로로 올라와도 권한 row 가 누락되지 않게(제품 권한과 동형 2지점 호출).
    # model-access-seed-fix(2026-07-28): 위와 동일 격리. 본 호출은 _ensure_seed_catchup 말미지만,
    # 예외가 밖으로 나가면 caller 가 "seed catchup skipped" 로 함수 전체를 실패로 기록해 다음 재기동
    # 까지 진단이 이 한 줄에 묶인다(라이브 실측). 국소 실패로 가둔다.
    try:
        _model_perm_added = _ensure_model_access_permissions(conn)
    except Exception as _mp_exc:
        _model_perm_added = 0
        try:
            import sys as _sys
            _sys.stderr.write(f"[model-access-rbac catchup] seed FAILED (catchup 계속): {_mp_exc!r}\n")
        except Exception:
            pass
    if _model_perm_added > 0:
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[model-access-rbac catchup] model access backfill: {_model_perm_added} permission/role-permission rows added\n"
            )
        except Exception:
            pass

def _ensure_web_gdrive_tokens_schema(conn) -> None:
    """feature-0010 (TASK-20260623T190000-gdrive-foundation): 계정별 Google Drive OAuth 토큰
    저장 테이블 (멱등 CREATE). fast+slow 양 경로 호출(_ensure_web_account_totp_schema 동형).

    `WebGoogleDriveTokens`: 계정별 암호화된 access/refresh 토큰 + 만료/scope/연결상태.
    AccessTokenEnc/RefreshTokenEnc 는 cred_crypto AESGCM 암호문(AAD=gdrive:{AccountId}).
    UNIQUE(AccountId, Provider) — 계정×provider 1행(향후 다른 provider 확장 여지). 미존재 행 =
    미연동(무회귀). 평문 토큰은 어떤 컬럼에도 저장하지 않는다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebGoogleDriveTokens (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AccountId BIGINT NOT NULL,
                Provider VARCHAR(32) NOT NULL DEFAULT 'google_drive',
                AccessTokenEnc TEXT NULL,
                RefreshTokenEnc TEXT NULL,
                TokenExpiresAt DATETIME NULL,
                GrantedScopes VARCHAR(1024) NULL,
                EncryptionVersion INT NOT NULL,
                IsConnected TINYINT(1) NOT NULL DEFAULT 0,
                FirstConnectedAt DATETIME NULL,
                RevokedAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY UX_WebGoogleDriveTokens_Account_Provider (AccountId, Provider),
                INDEX IX_WebGoogleDriveTokens_Expires (TokenExpiresAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    except Exception:
        pass
    finally:
        cur.close()


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _mark_memory_runtime_ready() -> None:
    app._MEMORY_SCHEMA_READY = True
    app._WEB_TABLES_READY = True


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (6종). app 전역은 app.X 동적 참조. ====

def _management_accounts(conn) -> list[dict[str, app.Any]]:
    rows = app._list_active_accounts(conn)
    return [
        row
        for row in rows
        if app._account_has_permission(row, "console.manage")
        and app._account_has_permission(row, "account.role.assign")
        and app._account_has_permission(row, "role.permission.manage")
    ]

def _generate_datasource_key(engine: str, host: str, port: int) -> str:
    """엔진 + 호스트 + 포트 의 SHA-256 해시 앞 12자를 키로 반환.

    형식: `{engine}-{hash12}` (예: mysql-3f2a1b9c7e41).
    fact-key `:ds:` 구분자와 충돌 없고, `ds` 로 시작하지 않으며(기존 `_ds_valid_key` 제약 통과),
    엔드포인트 좌표가 바뀌어도 목적지 변경을 즉시 키에 반영한다.
    """
    import hashlib as _hl
    raw = f"{(engine or 'mysql').strip().lower()}:{(host or '').strip().lower()}:{int(port or 0)}"
    digest = _hl.sha256(raw.encode()).hexdigest()[:12]
    eng_tag = (engine or "mysql").strip().lower()[:10]  # 최대 10자로 잘라 가독성 보존
    return f"{eng_tag}-{digest}"

def _runtime_tables_available() -> bool:
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            conn = app._open_memory_connection()
        except app.mysql.connector.Error as exc:
            if int(getattr(exc, "errno", 0) or 0) == 1049:
                return False
            raise
        try:
            cur = conn.cursor()
            try:
                for table_name in ("WebAccounts", "WebRoles", "WebAuthSessions",
                                   "WebProducts", "WebProductDatabases", "WebSystemPrompts",
                                   "WebDashboardPreferences"):
                    cur.execute(f"SELECT 1 FROM `{table_name}` LIMIT 1")
                    cur.fetchall()
                for column_check in (
                    "SELECT `ProductPrefMode` FROM `WebAccounts` LIMIT 1",
                    "SELECT `ProductPrefPinnedId` FROM `WebAccounts` LIMIT 1",
                    # TASK-0277: 제품 바인딩 stable surrogate(DatasourceId) 컬럼 — 누락 시 1054 → full 마이그레이션.
                    "SELECT `DatasourceId` FROM `WebProducts` LIMIT 1",
                    "SELECT `DatasourceId` FROM `WebProductDatasources` LIMIT 1",
                    "SELECT `DatasourceId` FROM `WebProductDatabases` LIMIT 1",
                    # TASK-20260618T044318: DB allowlist rule/manual 구분 컬럼 — 누락 시 1054 → full 마이그레이션
                    #   (rule 테이블/pending 도 같은 slow path 에서 생성됨).
                    "SELECT `Source` FROM `WebProductDatabases` LIMIT 1",
                    # TASK-20260618T061703: 다중 규칙 — SortOrder 누락 시 1054 → slow path 가 UNIQUE 제거 + SortOrder 추가.
                    "SELECT `SortOrder` FROM `WebProductDatasourceDbRules` LIMIT 1",
                ):
                    cur.execute(column_check)
                    cur.fetchall()
            finally:
                cur.close()
        except app.mysql.connector.Error as exc:
            if int(getattr(exc, "errno", 0) or 0) in (1146, 1054):
                return False
            raise
        finally:
            conn.close()
        return True
    try:
        conn = app._open_memory_connection()
    except app.mysql.connector.Error as exc:
        if int(getattr(exc, "errno", 0) or 0) == 1049:
            return False
        raise
    try:
        cur = conn.cursor()
        try:
            for table_name in (
                "AgentMemoryKv",
                "AgentMemoryMessages",
                "AgentMemorySteps",
                "WebAccounts",
                "WebRoles",
                "WebAuthSessions",
                "AgentCoreConversations",
                "WebProducts",
                "WebProductDatabases",
                "WebSystemPrompts",
                "WebDashboardPreferences",
            ):
                cur.execute(f"SELECT 1 FROM `{table_name}` LIMIT 1")
                cur.fetchall()
            # TASK-0047: 신규 컬럼 존재까지 검증해 신규 배포가 fast-path 를 우회하고
            # `_ensure_web_tables` 의 idempotent ALTER 들을 한 번 더 실행하도록 한다.
            # 컬럼 누락 시 errno 1054(Unknown column)가 발생 → False 반환 → full 마이그레이션 트리거.
            for column_check in (
                "SELECT `product_mode` FROM `AgentCoreConversations` LIMIT 1",
                "SELECT `ProductPrefMode` FROM `WebAccounts` LIMIT 1",
                "SELECT `ProductPrefPinnedId` FROM `WebAccounts` LIMIT 1",
                # TASK-0277: 제품 바인딩 stable surrogate(DatasourceId) 컬럼 — 누락 시 1054 → full 마이그레이션 트리거.
                "SELECT `DatasourceId` FROM `WebProducts` LIMIT 1",
                "SELECT `DatasourceId` FROM `WebProductDatasources` LIMIT 1",
                "SELECT `DatasourceId` FROM `WebProductDatabases` LIMIT 1",
            ):
                cur.execute(column_check)
                cur.fetchall()
        finally:
            cur.close()
    except app.mysql.connector.Error as exc:
        # 1146=Unknown table, 1054=Unknown column — 둘 다 신규 마이그레이션이 필요함을 의미.
        if int(getattr(exc, "errno", 0) or 0) in (1146, 1054):
            return False
        raise
    finally:
        conn.close()
    return True

def _backfill_group_conversation_members_once() -> None:
    """feature-0009: 기존 단일소유 대화 → owner member backfill (멱등, 프로세스당 1회, best-effort).

    멤버십 정본은 PG `agent_runtime.conversation_members`. READ_BACKEND != postgres 또는 PG
    미가용 시 skip(레거시/테스트 환경). ON CONFLICT DO NOTHING 이라 재실행 안전(이미 멤버는 skip).
    실패는 startup 흐름을 막지 않는다(다음 startup 에 재시도).
    """
    if app._GROUP_MEMBERS_BACKFILL_DONE:
        return
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") != "postgres":
        app._GROUP_MEMBERS_BACKFILL_DONE = True
        return
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            inserted = group_members.backfill_conversation_members(pg)
            print(f"[web.startup] group_members backfill: inserted={inserted}")
        finally:
            pg.close()
        app._GROUP_MEMBERS_BACKFILL_DONE = True
    except Exception as exc:
        print(f"[web.startup] group_members backfill skipped: {exc}")

def _schedule_memory_runtime_bootstrap() -> None:
    if app._MEMORY_SCHEMA_READY:
        return
    try:
        if app._runtime_tables_available():
            try:
                catchup_conn = app._open_memory_connection()
                try:
                    app._ensure_seed_catchup(catchup_conn)
                finally:
                    catchup_conn.close()
            except Exception as exc:
                print(f"[web.startup] seed catchup skipped: {exc}")
            app._backfill_group_conversation_members_once()
            app._mark_memory_runtime_ready()
            return
    except Exception as exc:
        print(f"[web.startup] memory probe failed: {exc}")
        return
    with app._MEMORY_SCHEMA_INIT_LOCK:
        if app._MEMORY_SCHEMA_READY or app._MEMORY_BOOTSTRAP_RUNNING:
            return
        app._MEMORY_BOOTSTRAP_RUNNING = True

    def _run_bootstrap() -> None:
        try:
            app._ensure_memory_runtime_ready()
            app._backfill_group_conversation_members_once()
        except Exception as exc:
            print(f"[web.startup] memory bootstrap failed: {exc}")
        finally:
            with app._MEMORY_SCHEMA_INIT_LOCK:
                app._MEMORY_BOOTSTRAP_RUNNING = False

    app.threading.Thread(
        target=_run_bootstrap,
        name="web-memory-bootstrap",
        daemon=True,
    ).start()

def _ensure_memory_runtime_ready() -> None:
    if app._MEMORY_SCHEMA_READY:
        return
    with app._MEMORY_SCHEMA_INIT_LOCK:
        if app._MEMORY_SCHEMA_READY:
            return
        app.ensure_memory_schema()
        app._ensure_web_tables()
        app._mark_memory_runtime_ready()


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (1종). ====

SEED_ROLE_SYSTEM_PROMPTS = (
    {
        "role_key": "sales",
        "product_id": None,
        "content": (
            "당신은 게임 사업팀을 지원하는 DBA 어시스턴트다.\n"
            "- 질의가 단순 조회 (특정 아이템의 유무, NPC ID, 몬스터 스킬 모듈 등) 이면 문장으로 답하라.\n"
            "- 질의가 집계/통계 요청이면 결과셋 표로 답하라.\n"
            "- 심층 ad-hoc 분석, 데이터 의미 해석, 성능 튜닝 요청은 "
            "\"DBA 팀으로 요청 이관이 필요합니다\" 안내 후 대화 종료.\n"
            "- DB 쓰기 쿼리 (INSERT/UPDATE/DELETE/DDL) 는 항상 거부."
        ),
    },
)
