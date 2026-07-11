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
