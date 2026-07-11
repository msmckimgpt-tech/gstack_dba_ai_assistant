"""feature-0012 P5b Final — admin_datasources 도메인 APIRouter (데이터소스 CRUD/테스트/DB 목록).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 190  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p1: app.py 에서 이동(도메인 소유 정상화 — 판정표 §4 routers 경로).
async def _ds_write_common(request, require_manage=True):
    """CRUD 공통: conn + actor + 권한 + body. 반환 (conn, actor, data, None) 또는 (None,None,None, error)."""
    try:
        conn = app._connect_memory()
    except Exception:
        return None, None, None, app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return None, None, None, error
    # TASK-0288: datasource CRUD 는 datasource.manage 전용 권한. 기존 console.access+console.manage
    # 게이트에 datasource.manage 를 추가(require_manage 경로). 미보유 시 403.
    need = ["console.access"] + (["console.manage", "datasource.manage"] if require_manage else [])
    if not all(app._account_has_permission(actor, p) for p in need):
        conn.close()
        return None, None, None, app._json_error("데이터소스 관리 권한(datasource.manage)이 필요합니다.", 403)
    try:
        body_raw = await request.body()
        data = (await request.json()) if body_raw else {}
    except Exception:
        conn.close()
        return None, None, None, app._json_error("invalid json", 400)
    if not isinstance(data, dict):
        conn.close()
        return None, None, None, app._json_error("invalid body", 400)
    return conn, actor, data, None



@router.get("/api/admin/datasources")
async def admin_list_datasources(request: Request, actor=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """등록된 datasource 키 목록 + product 바인딩 현황 (멀티 datasource P1, DESIGN Stage 1).

    좌표/비밀번호는 절대 반환하지 않는다 (datasource_public 마스킹). 관리 콘솔 접근 권한 필요.
    """
    from shared.config import AGENT_MULTI_DATASOURCE_ENABLED, DATASOURCES
    from shared import datasources as _dsr
    if not app._account_has_permission(actor, "console.access"):
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 데이터소스 조회 전용 권한 게이트 (read 또는 manage). 기존엔 console.access 만
    # 검사해 콘솔 진입권만 있으면 datasource 목록(좌표·바인딩 현황)이 무조건 노출됐다.
    if not app._account_has_any_permission(actor, "datasource.read", "datasource.manage"):
        return app._json_error("데이터소스 조회 권한이 필요합니다.", 403)
    # B3: host/port/engine/default_db 만 노출. **user/password 절대 비노출**(enumeration·누출 회피).
    # has_password=bool 만(평문/복호값 echo 금지). source=db/env(DB 우선 override 가시화, N1).
    merged = _dsr.all_datasources(conn)
    # conn-health-monitor: 백그라운드 모니터가 미리 계산한 per-datasource 연결 상태를
    # 첨부 → admin.js 가 per-item /test lazy probe(세마포어 대기) 없이 즉시 표시.
    try:
        from shared import conn_health as _ch
        _health = _ch.snapshot()
    except Exception:
        _health = {}
    # TASK-0255 R2: insight-worker 가 PG 에 영속한 스캔 관점 health(연결 불안정 vs 권한 실패 구분).
    _insight_health = app._read_insight_datasource_health()
    datasources = []
    for v in merged.values():
        _sk = _dsr.scope_key(v)
        _h = _health.get(_sk) if _sk else None
        datasources.append({
            "key": v["key"], "engine": v["engine"], "host": v.get("host"),
            "port": v.get("port"), "default_db": v.get("default_db"),
            "has_password": bool(v.get("password")),
            "source": ("db" if v.get("_source") == "db" else "env"),
            "editable": (v.get("_source") == "db"),  # .env datasource 는 UI 수정 불가(운영자 .env 편집)
            # TASK-0215: insight-worker 탐색 토글(.env 데이터소스는 컬럼 부재 → True 기본).
            "insight_enabled": bool(v.get("insight_enabled", True)),
            # conn-health: 사전 계산된 연결 상태(좌표 비노출 — status/elapsed/avg/checked_at 만).
            #   avg_elapsed_ms: 최근 sample_count(≤AGENT_CONN_AVG_WINDOW)회 성공 DB probe 응답시간 평균(ms).
            #   상세 패널의 "연결 응답 시간(평균)" 표시용 — background 모니터 사전계산값 재사용(추가 probe 없음).
            "conn_status": ({
                "status": _h.get("status"),
                "elapsed_ms": _h.get("last_elapsed_ms"),
                "avg_elapsed_ms": _h.get("avg_elapsed_ms"),
                "sample_count": _h.get("sample_count"),
                "checked_at": _h.get("checked_at"),
            } if _h else {"status": "unknown", "elapsed_ms": None, "avg_elapsed_ms": None,
                          "sample_count": 0, "checked_at": None}),
            # TASK-0255 R2: insight-worker 스캔 관점(PG 정본) — 미커버 사유 구분(연결 불안정/권한). None=insight 미기록.
            "insight_health": (_insight_health.get(_sk) if _sk else None),
            # scope-key-unify: 메타데이터 admin scope 드롭다운이 쓸 scope 식별자 — **질의 시점 read 와
            # 동일 해소값**(`scope_key 필드 or 라벨`: DB-등록 ds=해시, .env 레거시=라벨). 위 health 용
            # `_sk`(=_dsr.scope_key, .env 도 해시 계산)와 달리 read 축을 그대로 노출해야 write==read 가 된다
            # (라벨 ≠ 해시 死data 및 .env 역방향 死data 동시 회피). host/port 는 이미 노출 → 파생값 신규 누출 없음.
            "scope_key": (v.get("scope_key") or v.get("key")),
        })
    datasources.sort(key=lambda d: d["key"])
    cur = conn.cursor()
    try:
        try:
            cur.execute("SELECT Id, ProductKey, Name, DatasourceKey, DatasourceDatabase FROM WebProducts ORDER BY Id")
            rows = cur.fetchall() or []
            products = [
                {"id": int(r[0]), "product_key": str(r[1] or ""), "name": str(r[2] or ""),
                 "datasource_key": (str(r[3]).lower() if r[3] else None),
                 "datasource_database": (str(r[4]) if len(r) > 4 and r[4] else None)}
                for r in rows
            ]
        except Exception:
            cur.execute("SELECT Id, ProductKey, Name, DatasourceKey FROM WebProducts ORDER BY Id")
            products = [
                {"id": int(r[0]), "product_key": str(r[1] or ""), "name": str(r[2] or ""),
                 "datasource_key": (str(r[3]).lower() if r[3] else None), "datasource_database": None}
                for r in (cur.fetchall() or [])
            ]
    finally:
        cur.close()
    # TASK-0228 (1:N): 각 product 에 전체 datasource 바인딩 목록 부착(primary 포함, 단일 바인딩=1건).
    for _p in products:
        _p["datasources"] = app._list_product_datasources(conn, int(_p["id"]))
    from modules import cred_crypto as _cc
    return JSONResponse({
        "enabled": bool(AGENT_MULTI_DATASOURCE_ENABLED),
        "encryption_ready": bool(_cc.enc_available()),  # KEK 설정 여부(미설정 시 UI 가 CRUD 비활성)
        # TASK-0228: 사설/링크로컬 SSRF 경계 활성 여부 — UI 안내 문구 정합용(메타데이터 차단은 토글 무관 상시).
        "ssrf_private_guard_enabled": bool(app._ssrf_private_guard_enabled()),
        "datasources": datasources,
        "products": products,
    })

@router.post("/api/admin/datasources/{key}/test")
async def admin_test_datasource(key: str, request: Request, actor=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """datasource 연결 테스트 (멀티 datasource P2) — 좌표로 직접 SELECT 1.

    flag 활성화 *전* 운영자가 자격증명·연결성을 검증. 관리 콘솔 접근 권한 필요. password/host
    는 응답에 비노출(errno 만). flag 무관(명시 테스트).
    """
    from shared import datasources as _dsr
    from shared import db as _db
    if not app._account_has_permission(actor, "console.access"):
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 연결 테스트는 datasource 관리 동작(자격증명 검증·서버 probe) — manage 권한.
    if not app._account_has_permission(actor, "datasource.manage"):
        return app._json_error("데이터소스 관리 권한이 필요합니다.", 403)
    ds = _dsr.resolve(conn, str(key).strip().lower())
    if not ds:
        return app._json_error(f"미등록(또는 복호 불가) datasource 라벨: {key}", 404)
    okssrf, ssrf_reason, _pin = app._ssrf_check_host(ds.get("host"))
    if not okssrf:
        return JSONResponse({"key": str(key).strip().lower(), "ok": False, "elapsed_ms": 0.0,
                             "error": f"ssrf_blocked: {ssrf_reason}"})
    # MAJOR-2: 검증된 IP 로 고정 연결(DNS rebinding 차단 — host 재해석 금지).
    # TASK-0253: probe_datasource 는 도달 불가 datasource 에서 connection_timeout(기본 8s)까지
    #  동기 점유한다. async 핸들러 안에서 직접 호출하면 그동안 **이벤트 루프 전체가 블로킹**되어
    #  동시에 들어온 다른 datasource /test 요청(관리 콘솔 ↻ 일괄 새로고침 = N개 동시)이 직렬화돼
    #  배지가 "확인 중…"에 수 초 묶인다. asyncio.to_thread 로 스레드풀에 넘겨 루프를 비우면
    #  N개 probe 가 동시 진행 → 전체 소요가 sum→max(가장 느린 1개 ≤ timeout)로 떨어진다.
    #  (프로젝트 기존 패턴: /api/ask 의 asyncio.to_thread(run_agent, …) 와 동일.)
    ok, elapsed_ms, err = await asyncio.to_thread(
        _db.probe_datasource, {**ds, "host": _pin}
    )  # probe 는 errno 만 반환
    # conn-tristate: 3단계 분류(healthy 정상 / unstable 불안정-느림 / down 끊김)를 응답에 첨부.
    #  즉석 단발 테스트라 fails 이력이 없으므로 실패는 즉시 down(관리자 명시 테스트의 1회 도달
    #  실패 = 끊김), 성공+느림(elapsed≥SLOW)은 unstable. background snapshot 의 누적 fails 분류와
    #  의미가 일치하도록 conn_health.classify 를 공용으로 재사용한다.
    try:
        from shared import conn_health as _ch
        _status = _ch.classify(bool(ok), elapsed_ms, fails=10 ** 6)
    except Exception:
        _status = "healthy" if ok else "down"
    return JSONResponse({"key": str(key).strip().lower(), "ok": bool(ok),
                         "elapsed_ms": round(elapsed_ms, 1), "error": err, "status": _status})

@router.post("/api/admin/datasources")
async def admin_create_datasource(request: Request) -> JSONResponse:
    """datasource 생성 (자격증명 DB 암호화 저장, TASK-0205). console.manage. password 는 응답 비노출."""
    from modules import cred_crypto as _cc
    from shared import datasources as _dsr
    conn, actor, data, error = await _ds_write_common(request)
    if error:
        return error
    try:
        if not _cc.enc_available():
            return app._json_error("암호화 키(AGENT_DATASOURCE_KEK_V1) 미설정 — datasource 자격증명 저장 불가.", 400)
        engine = str(data.get("engine") or "mysql").strip().lower()
        if engine not in ("mysql", "mssql"):
            return app._json_error("engine 은 mysql|mssql.", 400)
        host = str(data.get("host") or "").strip()
        okssrf, reason, _ = app._ssrf_check_host(host)
        if not okssrf:
            return app._json_error(f"호스트 차단(SSRF): {reason}", 400)
        try:
            port = int(data.get("port") or (1433 if engine == "mssql" else 3306))
        except Exception:
            return app._json_error("port 정수 오류.", 400)
        user = str(data.get("user") or "").strip()
        password = str(data.get("password") or "")
        # TASK-0213: '기본 참조 DB'(default_db) 폐지 — 데이터소스에 기본 DB 를 두지 않는다(NULL). 접근 DB 는
        # 제품의 '접근 가능 데이터베이스'(allowlist)로 관리, MSSQL 연결은 그 중 첫 DB 자동(없으면 tempdb).
        if not host or not user:
            return app._json_error("host·user 는 필수.", 400)
        # 키를 엔진+호스트+포트 해시로 자동 생성한다. 동일 엔드포인트면 항상 동일 키 → 중복 등록 방지.
        # 용도 변경 시(host/port 변경)는 새 키가 발급되어 이전 키와 명확히 구분된다.
        key = app._generate_datasource_key(engine, host, port)
        got = _dsr.ensure_dek(conn)
        if got is None:
            return app._json_error("DEK 생성 실패(KEK 확인).", 500)
        ver, dek = got
        pw_enc = _cc.encrypt_password(dek, password, key) if password else None
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,))
            if cur.fetchone():
                return app._json_error(f"이미 존재하는 키: {key} (동일 엔드포인트가 이미 등록되어 있습니다)", 409)
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,1,%s)",
                (key, engine, host, port, user, pw_enc, int(ver),
                 int(actor.get("id")) if isinstance(actor, dict) and actor.get("id") else None),
            )
        finally:
            cur.close()
        app.record_audit_event(conn, actor=app._build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.create", resource_type="datasource", resource_id=key,
                           change_json=app._ds_audit_fields({**data, "key": key}))
        conn.commit()
        return JSONResponse({"key": key, "engine": engine, "host": host, "port": port,
                             "default_db": None, "has_password": bool(pw_enc), "source": "db"})
    finally:
        conn.close()

@router.patch("/api/admin/datasources/{key}")
async def admin_update_datasource(key: str, request: Request) -> JSONResponse:
    """datasource 수정 (TASK-0205). password 미입력 시 미변경. console.manage. 응답 password 비노출."""
    from modules import cred_crypto as _cc
    from shared import datasources as _dsr
    conn, actor, data, error = await _ds_write_common(request)
    if error:
        return error
    # TASK-0277 (REV BLOCKER2): _connect_memory 는 autocommit=True 라 다단계 rename+cascade 가 비원자적이었다.
    # 명시 트랜잭션으로 묶어 부분 적용(라벨만 바뀌고 일부 바인딩 cascade 누락)을 방지 — 실패 시 전체 rollback.
    try:
        conn.autocommit = False
        k = app._ds_valid_key(key)
        if not k:
            return app._json_error("라벨 형식 오류.", 400)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion FROM WebDatasources"
                " WHERE DatasourceKey=%s LIMIT 1",
                (k,),
            )
            existing = cur.fetchone()
            if not existing:
                return app._json_error("datasource not found (DB 등록분만 수정 가능, .env 는 운영자 편집).", 404)
            cur_engine, cur_host, cur_port, cur_pw_enc, cur_enc_ver = existing

            sets, params = [], []
            new_engine = cur_engine
            if "engine" in data:
                eng = str(data.get("engine") or "").strip().lower()
                if eng not in ("mysql", "mssql"):
                    return app._json_error("engine 은 mysql|mssql.", 400)
                sets.append("Engine=%s"); params.append(eng)
                new_engine = eng
            # TASK-0212: 수정 폼이 모든 필드를 항상 전송하므로(빈값 포함), **필수/구성 필드는 빈값일 때
            # 갱신하지 않고 기존값을 보존**한다(write-only-when-provided). 특히 GET 은 보안상 user 를
            # 마스킹(B3)해 폼이 pre-fill 못 하므로, 빈 user 를 그대로 쓰면 DbUser 가 wipe 돼 연결 테스트가
            # 실패한다(회귀). host/user 는 필수, default_db 는 구성값 — 빈값=유지(실수 wipe 방지).
            new_host = cur_host
            if "host" in data:
                host = str(data.get("host") or "").strip()
                if host:  # 빈 host 무시(필수 — 기존 유지)
                    okssrf, reason, _ = app._ssrf_check_host(host)
                    if not okssrf:
                        return app._json_error(f"호스트 차단(SSRF): {reason}", 400)
                    sets.append("Host=%s"); params.append(host)
                    new_host = host
            new_port = cur_port
            if "port" in data and str(data.get("port") or "").strip():
                try:
                    p = int(data.get("port"))
                    sets.append("Port=%s"); params.append(p)
                    new_port = p
                except Exception:
                    return app._json_error("port 정수 오류.", 400)
            if "user" in data and str(data.get("user") or "").strip():
                sets.append("DbUser=%s"); params.append(str(data.get("user")).strip())
            # TASK-0213: '기본 참조 DB'(default_db) 폐지 — PATCH 에서 갱신하지 않는다(데이터소스 레벨 기본 DB 미관리).
            if "is_active" in data:
                sets.append("IsActive=%s"); params.append(1 if data.get("is_active") else 0)
            # TASK-0215: insight-worker 탐색 토글.
            if "insight_enabled" in data:
                sets.append("InsightEnabled=%s"); params.append(1 if data.get("insight_enabled") else 0)

            # 키 결정 (TASK-0234 근본수정): 라벨(DatasourceKey)은 **사용자가 명시적으로 rename 할 때만** 변경한다.
            # 과거엔 키 미지정 편집 시 엔드포인트 해시로 재계산(`... else hash_new_k`)해, host/port 뿐 아니라
            # insight 토글·password 등 **다른 필드만 바꿔도 친화 라벨이 매 편집마다 엔드포인트 해시로 되돌아가는**
            # 회귀가 있었다(admin.js 는 라벨 변경 시에만 key 전송 → 일반 편집은 data.key 부재 → 해시 default 적용).
            # 라벨은 이제 admin rename 가능한 단순 식별자이고(TASK-0216/0219), 엔드포인트 신원은 라벨이 아닌
            # `compute_scope_key`(런타임 insight/RAG 스코핑)로 추적하므로 라벨을 엔드포인트에 종속시키면 안 된다.
            # → explicit rename(body.key) 시에만 변경, 그 외(host/port 변경 포함) 현재 라벨(k) 유지.
            # PasswordEnc AAD=DatasourceKey 이므로 키가 실제로 바뀔 때만(explicit rename) 재암호화.
            explicit_new_key = app._ds_valid_key(data.get("key") or "") if data.get("key") else None
            new_k = explicit_new_key if (explicit_new_key and explicit_new_key != k) else k
            key_changed = (new_k != k)

            if data.get("password"):  # 비어있지 않을 때만 재암호화(write-only)
                if not _cc.enc_available():
                    return app._json_error("암호화 키 미설정 — password 변경 불가.", 400)
                got = _dsr.ensure_dek(conn)
                if got is None:
                    return app._json_error("DEK 확인 실패.", 500)
                ver, dek = got
                sets.append("PasswordEnc=%s"); params.append(_cc.encrypt_password(dek, str(data.get("password")), new_k))
                sets.append("EncryptionVersion=%s"); params.append(int(ver))
            elif key_changed and cur_pw_enc:
                # 키가 바뀌었고 패스워드 신규 입력이 없으면 기존 패스워드를 새 AAD 로 재암호화.
                if not _cc.enc_available():
                    return app._json_error("암호화 키 미설정 — 키/호스트/포트 변경 시 패스워드 재암호화 불가.", 400)
                got = _dsr.ensure_dek(conn)
                if got is None:
                    return app._json_error("DEK 확인 실패.", 500)
                ver, dek = got
                try:
                    plain = _cc.decrypt_password(dek, cur_pw_enc, k)
                    sets.append("PasswordEnc=%s"); params.append(_cc.encrypt_password(dek, plain, new_k))
                    sets.append("EncryptionVersion=%s"); params.append(int(ver))
                except Exception:
                    return app._json_error("기존 패스워드 재암호화 실패 — 키/호스트/포트 변경 시 패스워드를 직접 입력해 주세요.", 500)

            if key_changed:
                cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (new_k,))
                if cur.fetchone():
                    return app._json_error(f"이미 존재하는 키: {new_k}", 409)
                sets.append("DatasourceKey=%s"); params.append(new_k)

            if isinstance(actor, dict) and actor.get("id"):
                sets.append("UpdatedByAccountId=%s"); params.append(int(actor.get("id")))
            if not sets:
                return app._json_error("변경할 필드 없음.", 400)
            params.append(k)
            cur.execute(f"UPDATE WebDatasources SET {', '.join(sets)} WHERE DatasourceKey=%s", tuple(params))

            if key_changed:
                # TASK-0277 (라벨/키 분리 근본수정): 제품 바인딩은 stable surrogate `WebDatasources.Id` 로 anchor
                # 되므로 라벨이 바뀌어도 고아되지 않는다. 바인딩 테이블의 denormalized 라벨 캐시(DatasourceKey
                # — 기존 PK·읽기 경로 호환)는 신선도 유지를 위해 **완전 cascade** 한다 — 과거 버그처럼 WebProducts
                # 만 갱신하고 WebProductDatasources/WebProductDatabases 를 누락하지 않는다.
                #  - **컬럼 부재(마이그레이션 지연) 시에도 키 기준으로 cascade** → 일부 테이블 누락 없음(REV BLOCKER1).
                #    DatasourceId 가 있으면 추가로 Id 기준 매칭(stale 키 캐시 행도 포착).
                #  - new_k 는 위 409 가드로 미존재 datasource → 바인딩 테이블에 new_k 행이 있으면 고아(이전 삭제
                #    잔재). PK(ProductId,DatasourceKey[,SchemaName]) 충돌 방지 위해 cascade 전 제거(REV BLOCKER3).
                #  - 실패는 swallow 하지 않고 상위 트랜잭션 rollback 으로 전파(부분 적용 방지 — fail-loud, REV BLOCKER2).
                cur.execute("SELECT Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (new_k,))
                _dsrow = cur.fetchone()
                _ds_id = int(_dsrow[0]) if _dsrow and _dsrow[0] is not None else None
                for _tbl in ("WebProductDatasources", "WebProductDatabases"):
                    cur.execute(f"DELETE FROM {_tbl} WHERE LOWER(DatasourceKey)=%s", (new_k,))
                for _tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
                    cur.execute(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                        "AND TABLE_NAME=%s AND COLUMN_NAME='DatasourceId'", (_tbl,))
                    _has_id = int((cur.fetchone() or [0])[0]) > 0
                    if _has_id and _ds_id is not None:
                        cur.execute(
                            f"UPDATE {_tbl} SET DatasourceKey=%s WHERE DatasourceId=%s OR LOWER(DatasourceKey)=%s",
                            (new_k, _ds_id, k))
                    else:
                        cur.execute(
                            f"UPDATE {_tbl} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s",
                            (new_k, k))
        finally:
            cur.close()
        effective_key = new_k if key_changed else k
        app.record_audit_event(conn, actor=app._build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.update", resource_type="datasource", resource_id=effective_key,
                           change_json=app._ds_audit_fields(data))
        conn.commit()
        return JSONResponse({"key": effective_key, "updated": True, "password_changed": bool(data.get("password")),
                             "key_changed": key_changed})
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

@router.delete("/api/admin/datasources/{key}")
async def admin_delete_datasource(key: str, request: Request) -> JSONResponse:
    """datasource 삭제 (TASK-0205). 바인딩된 product 있으면 거부(?force=1 로 강제). console.manage."""
    conn, actor, _data, error = await _ds_write_common(request)
    if error:
        return error
    try:
        k = app._ds_valid_key(key)
        if not k:
            return app._json_error("라벨 형식 오류.", 400)
        force = str(request.query_params.get("force", "")).strip().lower() in ("1", "true", "yes")
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (k,))
            _del_row = cur.fetchone()
            if not _del_row:
                return app._json_error("datasource not found.", 404)
            _del_id = int(_del_row[0]) if _del_row and _del_row[0] is not None else None  # TASK-0277 dangling anchor 해제용
            # TASK-0228 (1:N): primary 포인터(WebProducts.DatasourceKey) + join 테이블 양쪽에서 바인딩 탐색.
            cur.execute("SELECT Id, ProductKey FROM WebProducts WHERE LOWER(DatasourceKey)=%s", (k,))
            bound_map = {int(r[0]): str(r[1] or "") for r in (cur.fetchall() or [])}
            try:
                cur.execute(
                    "SELECT p.Id, p.ProductKey FROM WebProductDatasources pds "
                    "JOIN WebProducts p ON p.Id = pds.ProductId WHERE LOWER(pds.DatasourceKey)=%s", (k,))
                for r in (cur.fetchall() or []):
                    bound_map[int(r[0])] = str(r[1] or "")
            except Exception:
                pass
            bound = [{"id": pid, "product_key": pk} for pid, pk in sorted(bound_map.items())]
            if bound and not force:
                return JSONResponse({"deleted": False, "reason": "bound_products",
                                     "bound_products": bound}, status_code=409)
            if bound and force:
                # primary 포인터 해제 + join 바인딩 제거 + 그 datasource 의 접근DB 행 정리(고아 차단).
                cur.execute("UPDATE WebProducts SET DatasourceKey=NULL WHERE LOWER(DatasourceKey)=%s", (k,))
                # TASK-0277: 삭제 datasource 를 가리키던 DatasourceId 도 해제(dangling anchor 차단). 컬럼 부재 graceful.
                if _del_id is not None:
                    try:
                        cur.execute("UPDATE WebProducts SET DatasourceId=NULL WHERE DatasourceId=%s", (_del_id,))
                    except Exception:
                        pass
                try:
                    cur.execute("DELETE FROM WebProductDatasources WHERE LOWER(DatasourceKey)=%s", (k,))
                    cur.execute("DELETE FROM WebProductDatabases WHERE LOWER(DatasourceKey)=%s", (k,))
                    # primary 가 비워진 제품은 남은 join 바인딩 중 첫째를 새 primary 로 승격.
                    for pid in bound_map:
                        cur.execute(
                            "SELECT LOWER(DatasourceKey) FROM WebProductDatasources WHERE ProductId=%s "
                            "ORDER BY SortOrder ASC, DatasourceKey ASC LIMIT 1", (int(pid),))
                        nr = cur.fetchone()
                        if nr and nr[0]:
                            _np = str(nr[0]).strip().lower()
                            cur.execute("UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                        (int(pid), _np))
                            cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (_np, int(pid)))
                            # TASK-0277: 승격된 primary 의 DatasourceId 도 동기화. 컬럼 부재 graceful.
                            try:
                                cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (_np,))
                                _npr = cur.fetchone()
                                cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s",
                                            (int(_npr[0]) if _npr and _npr[0] is not None else None, int(pid)))
                            except Exception:
                                pass
                except Exception:
                    pass
            cur.execute("DELETE FROM WebDatasources WHERE DatasourceKey=%s", (k,))
        finally:
            cur.close()
        app.record_audit_event(conn, actor=app._build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.delete", resource_type="datasource", resource_id=k,
                           change_json={"force": force, "unbound_products": bound})
        conn.commit()
        return JSONResponse({"deleted": True, "key": k, "unbound_products": bound})
    finally:
        conn.close()

@router.get("/api/admin/datasources/{key}/databases")
async def admin_datasource_databases(key: str, request: Request, actor=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """datasource 서버의 DB 목록(제품별 참조 DB 선택용, TASK-0205 §2.4). datasource.read. SSRF 차단."""
    from shared import datasources as _dsr
    from shared import db as _db
    from shared import conn_health as _ch
    # TASK-0288: datasource 의 DB 목록 조회 — datasource.read(또는 manage). 기존 console.manage 대체.
    if not (app._account_has_permission(actor, "console.access")
            and app._account_has_any_permission(actor, "datasource.read", "datasource.manage")):
        return app._json_error("데이터소스 조회 권한이 필요합니다.", 403)
    ds = _dsr.resolve(conn, str(key).strip().lower())
    if not ds:
        return app._json_error("미등록(또는 복호 불가) datasource.", 404)
    okssrf, reason, _pin = app._ssrf_check_host(ds.get("host"))
    if not okssrf:
        return app._json_error(f"호스트 차단(SSRF): {reason}", 400)
    # ds-conn-bg-decouple: 연결 확인을 동기 render 경로에서 분리한다. 백그라운드 conn_health
    # 모니터가 미리 계산해 둔 상태를 먼저 읽어, unstable/down 이면 live connect(최대 8s 이벤트
    # 루프 블록)를 시도하지 않고 캐시 상태만 즉시 반환한다 — 제품 항목 진입 시 다른 UI 갱신이
    # 멈추지 않는다. 명시적 새로고침(?force=1)일 때만 실제 열거를 강제한다.
    force = str(request.query_params.get("force") or "").strip().lower() in ("1", "true", "yes")
    cached = _ch.status_for(ds) or {}
    conn_status = cached.get("status") or _ch.UNKNOWN
    if not force and conn_status in (_ch.UNSTABLE, _ch.DOWN):
        return JSONResponse({
            "key": str(key).strip().lower(),
            "engine": ds.get("engine"),
            "databases": [],
            "databases_classified": [],
            "conn_status": conn_status,
            "degraded": True,
        })
    try:
        # TASK-0206 §3.4: 시스템/사용자 DB 구분(`[{name, system}]`). UI 가 시스템 DB 는 고정칩으로.
        # 실제 DB 열거는 살아있는 연결이 필요 → 이벤트 루프 블로킹 방지 위해 to_thread 로 오프로드.
        classified = await asyncio.to_thread(
            _db.list_server_databases_classified, {**ds, "host": _pin})  # MAJOR-2: pinned IP
    except Exception:
        # 실패를 conn_health 에 피드백 — 다음 요청이 즉시 캐시 상태로 fast-path(8s 재낭비 차단).
        try:
            _ch.record_foreground_result(ds, False, None, "list_databases_failed")
        except Exception:
            pass
        return app._json_error("DB 목록 조회 실패(연결/권한 확인).", 502)
    # 하위호환: 기존 `databases`(사용자 DB 이름 배열) 유지 + 신규 `databases_classified`.
    user_names = [d["name"] for d in classified if not d.get("system")]
    return JSONResponse({
        "key": str(key).strip().lower(),
        "engine": ds.get("engine"),
        "databases": user_names,
        "databases_classified": classified,
        "conn_status": conn_status,
        "degraded": False,
    })
