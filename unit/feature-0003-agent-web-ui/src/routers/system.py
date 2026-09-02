"""feature-0012 P5b Final — system 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

from shared.model_catalog import API_DEFAULT_MODEL
from shared.model_catalog import PUBLIC_API_MODEL_OPTIONS
from shared.llm_gate import server_llm_enabled
import logging
import os
from typing import Any

import app
import bridge_drain as _drain  # feature-0045: 브리지 in-flight + lame-duck drain
import oauth_store as _store   # feature-0043 P0-Z3: 러너 능력 신고(모델 선택기 카탈로그)

INCLUDE_ORDER = 60  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


def _anonymous_provider_status() -> "dict[str, Any]":
    """미인증 요청에 돌려줄 **축소된** LLM provider 상태.

    api-exposure-hardening (2026-08-11): 인증 없이 `/api/llm/health` 를 부르면 `provider`(bedrock)·
    `source`·`since_epoch`·`updated_epoch` 가 그대로 나갔다 — LLM 공급자 스택과 **장애 발생/복구
    시각**을 익명에게 알려주는 정찰 표면이다(외부 AI 감사가 적발, 라이브 실측 재현). 상태점 UI 가
    실제로 필요로 하는 것은 `state` 하나뿐이므로 그 키만 남긴다.

    인증된 요청의 응답은 불변 — 축소는 미인증 경로에만 적용한다.
    """
    status = app._read_llm_provider_status()
    state = "unknown"
    if isinstance(status, dict):
        state = str(status.get("state") or "unknown")
    return {"state": state}


@router.get("/api/llm/health")
def get_llm_health(request: Request, force: int = 0, conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-20260619T014034: LLM provider health(외부요인 제한) 조회 + hybrid active probe.

    프론트가 로드 시 + 주기적으로 폴링. probe 는 TTL(LLM_HEALTH_PROBE_TTL_SEC, 기본 60s) 내
    재호출이면 skip(비용 최소화) — 단 `force=1`(배너 '다시 확인')은 TTL 무시. 인증 필요(외부
    노출 최소화) — 미인증은 cheap read 만 반환.

    [P5b DI seam Phase 1 파일럿] conn 공급을 app.get_conn DI 로 위임(behavior-neutral). 인증 해석은
    legacy 와 동일하게 app._get_authenticated_account 를 **직접** 호출한다 — app.get_optional_account 로
    위임하면 인증 쿼리 예외를 삼켜(except→None) legacy 의 'conn-open + 인증쿼리 raise → 500 전파'
    를 200 cheap-read 로 바꾸므로(적대 패널 REV HIGH-1) 의도적으로 inline 유지. 동치 경로:
    conn 획득 실패(app.get_conn None)·미인증 → cheap read 200, 인증 쿼리 예외 → 전파(→500), 인증 성공 → probe.
    (conn 은 app.get_conn 계약상 요청 teardown 까지 보유 — 관측 응답은 불변, §1.1 sanction 한 design tradeoff.)
    """
    if conn is None:
        # conn 획득 실패: probe 트리거 없이 마지막 알려진 상태만 (legacy `except → cheap read` 동치).
        return JSONResponse(_anonymous_provider_status())
    account = app._get_authenticated_account(conn, request)
    if not account:
        # 미인증: probe 트리거 없이 마지막 알려진 상태만.
        return JSONResponse(_anonymous_provider_status())
    try:
        from modules.llm_provider_health import probe_provider
        status = probe_provider(force=bool(force))
    except Exception:
        status = app._read_llm_provider_status()
    return JSONResponse(status)


@router.get("/api/file")
def get_file(request: Request, path: str, conversation_id: str, max_bytes: int = 0, account=Depends(app.get_current_account), conn=Depends(app.get_conn)):
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return app._json_error("conversation_id is required", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.file.read.own",
        "conversation.file.read.any",
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    safe = app._safe_shared_path(path)
    if not safe or not safe.exists():
        return JSONResponse({"error": "file not found"}, status_code=404)
    if max_bytes and max_bytes > 0:
        try:
            with open(safe, "rb") as f:
                data = f.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return JSONResponse({"error": "read failed"}, status_code=500)
        return PlainTextResponse(text)
    return FileResponse(safe)


@router.get("/livez")
def livez() -> JSONResponse:
    """feature-0014: DB-무관 liveness probe. 프로세스가 떠서 HTTP 를 처리하면 항상 200.

    Caddy 의 active health_uri 가 본 endpoint 를 쓴다 — /healthz(mysql+pg ping)로 하면 DB 가
    잠깐 느릴 때(예: migrate 중) 양 replica 가 동시에 unhealthy 로 빠져 502 가 날 수 있으므로,
    LB liveness 는 DB 와 분리한다. active_streams 는 deploy-web.sh pre-drain 게이트가 폴링한다.

    feature-0045: **드레인 중이면 503** 이다. Caddy 의 active health(`health_interval 2s` ·
    `health_fails 1`)가 그 신호로 2초 안에 이 replica 를 LB 후보에서 빼므로, recreate 하기
    전에 신규 유입이 먼저 멈춘다 — replica 를 죽이면서 트래픽을 끊는 것이 아니라, 트래픽을
    먼저 옮기고 조용해진 뒤에 죽인다. 본문은 200 일 때와 **같은 모양**을 유지한다(진단 시
    상태 코드만 보고 카운터를 못 읽는 일이 없게).
    """
    body = {
        "status": "ok",
        "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
        "active_streams": app._active_stream_count(),
    }
    body.update(_drain.snapshot())
    if body.get("draining"):
        body["status"] = "draining"
        return JSONResponse(body, status_code=503)
    return JSONResponse(body, status_code=200)

@router.get("/readyz")
def readyz() -> JSONResponse:
    """feature-0014: 배포 게이트용 readiness probe. mysql+pg 도달 가능해야 200, 아니면 503.

    deploy-web.sh 가 새 replica 를 띄운 뒤 본 endpoint 가 200 + git_commit==<배포 대상 SHA>
    가 될 때까지 기다린 후에만 다음 replica 로 넘어간다(또는 OLD 를 제거한다). /livez 와 달리
    DB 연결을 확인하므로, DB 미준비 상태의 replica 로 트래픽이 가는 것을 막는다."""
    git_commit = os.environ.get("GIT_COMMIT", "unknown")
    mysql_ok = False
    pg_ok = False
    try:
        conn = app._connect_memory()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            mysql_ok = True
        finally:
            conn.close()
    except Exception:
        logging.getLogger(__name__).warning("readyz: mysql check failed", exc_info=True)
    try:
        from shared.db import _pg_available

        pg_ok = bool(_pg_available())
    except Exception:
        logging.getLogger(__name__).warning("readyz: pg check failed", exc_info=True)

    ready = mysql_ok and pg_ok
    body = {
        "status": "ready" if ready else "not-ready",
        "git_commit": git_commit,
        "mysql_ok": mysql_ok,
        "pg_ok": pg_ok,
        "active_streams": app._active_stream_count(),
    }
    # feature-0045: 브리지 카운터를 함께 싣되 **상태 코드는 바꾸지 않는다**. /readyz 는
    # "이 replica 가 서빙 가능한가" 를 답하는 자리이고, 드레인은 서빙 능력의 문제가 아니라
    # 배포 절차의 국면이다. 여기서 503 을 내면 스파인의 recreate 후 대기(`wait_ready`)가
    # 자기가 건 드레인 때문에 영원히 못 끝나는 자기참조가 생긴다.
    body.update(_drain.snapshot())
    return JSONResponse(body, status_code=200 if ready else 503)


@router.post("/internal/bridge-drain")
def internal_bridge_drain(request: Request) -> JSONResponse:
    """이 replica 를 lame-duck 으로 만들고(또는 되돌리고) 현재 in-flight 를 돌려준다.

    feature-0045 — 무중단 롤링의 pre-drain 게이트가 replica 를 내리기 **직전에** 부른다.
    멱등이며, 스파인은 `bridge_inflight` 가 0 이 될 때까지 이 호출을 반복한다.

    | 파라미터 | 뜻 |
    |---|---|
    | (없음) | 드레인 시작 — 신규 유입 차단 + 대기 롱폴 즉시 반환 |
    | `?release=1` | 드레인 해제 — **배포가 replica 를 못 내리고 중단했을 때** 되돌린다 |

    해제 경로가 없으면, 게이트에서 중단된 배포가 replica 를 문 닫힌 채로 남긴다. 그 상태에서
    상대까지 교체하려 들면 두 replica 모두 LB 후보 밖 — 정확히 전면 다운이다.

    ## 접근 경계

    **loopback 전용**(`_loopback_only`). 엣지에서도 `/internal/*` 을 404 로 막지만, 앱이 스스로
    판정하는 쪽이 정본이다 — 엣지 설정이 바뀌어도 이 경계는 남아야 한다.
    """
    denied = _loopback_only(request)
    if denied is not None:
        return denied
    release = str(request.query_params.get("release") or "").strip().lower() in ("1", "true", "yes")
    if release:
        _drain.end_drain()
    else:
        _drain.begin_drain()
    body: dict[str, Any] = {"git_commit": os.environ.get("GIT_COMMIT", "unknown"),
                            "active_streams": app._active_stream_count()}
    body.update(_drain.snapshot())
    return JSONResponse(body, status_code=200)


def _loopback_only(request: Request) -> JSONResponse | None:
    """`/internal/*` 접근 경계. 통과면 None.

    Caddy 를 통해 들어온 요청의 `client.host` 는 엣지 컨테이너 IP 라 거부된다. 엣지에서도
    `/internal/*` 을 404 로 막지만(2겹), **앱이 스스로 판정하는 쪽이 정본**이다 — 엣지 설정이
    바뀌어도 이 경계는 남아야 한다.

    `::ffff:127.0.0.1` 은 bind 가 `::` 로 바뀌면 나타나는 IPv4-mapped 표기다. 지금 구성에서는
    안 나오지만, 나올 때 조용히 403 이 되면 배포가 원인 불명으로 멈춘다.
    """
    client = getattr(request, "client", None)
    host = (getattr(client, "host", "") or "") if client else ""
    if host not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return JSONResponse({"error": "loopback 전용 엔드포인트입니다."}, status_code=403)
    return None


def _bridge_lease_minutes() -> int:
    """점유 lease(분). 정본은 `routers/ai_tools._BRIDGE_CLAIM_LEASE_MIN` 이다.

    여기서 숫자를 다시 쓰면 상수를 바꿨을 때 **게이트만 조용히 옛 경계를 본다** — lease 를
    줄이면 이미 재점유되어 처리 중인 작업을 두 번 세고, 늘리면 진짜 진행 중인 작업을 놓친다.
    import 는 지연시킨다(모듈 로드 순서 의존을 만들지 않는다).
    """
    try:
        from routers.ai_tools import _BRIDGE_CLAIM_LEASE_MIN
        return int(_BRIDGE_CLAIM_LEASE_MIN)
    except Exception:  # pragma: no cover — 방어적(정본이 사라지면 보수적으로 길게 본다)
        return 30


@router.get("/internal/bridge-activity")
def internal_bridge_activity(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """지금 **개인 AI 가 처리 중인** 브리지 작업 수(클러스터 전역).

    feature-0045 — quiesce 게이트(`bin/lib/quiesce.sh`)가 쓴다.

    그 게이트는 진행 중 사용자 run 을 `ask_jobs.status='running'` 과 web 의 `active_streams`
    두 신호로 판정한다. **브리지 전환(feature-0043) 이후 그 둘은 사용자 작업을 대변하지
    않는다** — 서버 LLM 이 차단돼 `ask_jobs` 행이 만들어지지 않고, 개인 AI 의 왕복은
    `active_streams` 에 세지 않는다. 즉 게이트는 사용자가 답을 기다리는 중에도 "조용함" 으로
    통과한다(vacuous pass — 있으나 마나가 아니라, 무중단이라고 **믿게 만들기 때문에** 더 나쁘다).

    ## fresh 와 stale 을 나눠 준다 (적대 리뷰 P2)

    `ask_jobs` 축이 heartbeat 로 살아 있는 run 과 좀비를 나누는 것과 같은 이유다. 개인 머신
    AI 는 **노트북을 닫는 것이 정상적인 실패 양상**이라, 점유만 보고 "진행 중" 으로 세면 유령
    점유 하나가 배포를 lease 만료(30분)까지 막는다 — quiesce 상한이 15분이므로 그 대기는
    구조적으로 성공할 수 없다. `fresh`(최근에 점유)만 게이트를 막고, `stale` 은 분리 계상해
    로그로 보이게 한다(제외가 아니라 구분 — 판단 근거를 지운다는 뜻이 아니다).
    """
    denied = _loopback_only(request)
    if denied is not None:
        return denied
    if conn is None:
        # `app.get_conn` 은 연결 실패를 흡수해 **None 을 yield 한다**(raise 하지 않는다).
        # 확인하지 않으면 `conn.cursor()` 가 AttributeError 로 터져 generic 500 이 나가고,
        # "조회 실패는 503 으로 말한다" 는 아래 계약이 그 경로에서 실행되지 않는다.
        return JSONResponse({"error": "db connection unavailable"}, status_code=503)
    lease_min = _bridge_lease_minutes()
    fresh_min = max(1, min(lease_min, 5))   # 최근 점유 = "지금 붙어 있다" 로 볼 수 있는 창
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT "
            "  SUM(ClaimedBy IS NOT NULL AND ClaimedAt IS NOT NULL "
            "      AND ClaimedAt > DATE_SUB(NOW(), INTERVAL %s MINUTE)), "
            "  SUM(ClaimedBy IS NOT NULL AND ClaimedAt IS NOT NULL "
            "      AND ClaimedAt <= DATE_SUB(NOW(), INTERVAL %s MINUTE) "
            "      AND ClaimedAt > DATE_SUB(NOW(), INTERVAL %s MINUTE)), "
            "  SUM(ClaimedBy IS NULL OR ClaimedAt IS NULL "
            "      OR ClaimedAt <= DATE_SUB(NOW(), INTERVAL %s MINUTE)) "
            "FROM WebAiTasks WHERE Origin='web' AND Status='open' AND SubmittedAt IS NULL",
            (fresh_min, fresh_min, lease_min, lease_min))
        row = cur.fetchone() or (0, 0, 0)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        # 조회 실패를 0 으로 돌려주지 않는다 — 그것이 곧 게이트의 vacuous pass 다.
        # 호출측이 "관측 불가" 로 구분해 보수적으로 판단하도록 503 으로 말한다.
        logging.getLogger(__name__).warning("bridge-activity 실패: %s", exc, exc_info=True)
        return JSONResponse({"error": str(exc)}, status_code=503)
    finally:
        if cur is not None:
            cur.close()
    return JSONResponse({"claimed": int(row[0] or 0), "stale": int(row[1] or 0),
                         "pending": int(row[2] or 0), "fresh_minutes": fresh_min,
                         "lease_minutes": lease_min}, status_code=200)


@router.post("/internal/bridge-reclaim")
def internal_bridge_reclaim(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """배포가 **강행**으로 끊었을 가능성이 있는 브리지 점유를 대기열로 되돌린다.

    feature-0045 — pre-drain 이 상한 안에 조용해지지 못해 진행 중인 왕복을 끊고 간 배포에서만
    호출된다(`bin/deploy-web.sh`). 평상시에는 호출되지 않는다.

    ## 되돌리는 방식 — `ClaimedBy` 를 지우지 않는다

    점유 시각(`ClaimedAt`)만 과거로 밀어 **lease 만 만료**시킨다. 그 결과:

    | 누가 | 무슨 일이 되나 |
    |---|---|
    | 원래 가져간 AI 가 살아 있었다 | `submit_answer` 는 `ClaimedBy` 만 보므로 **그대로 제출된다** |
    | 원래 가져간 AI 가 죽었다 | lease 가 만료됐으므로 다음 연결이 **다시 가져간다** |

    `ClaimedBy` 까지 지우면 살아남은 원 소유자의 제출이 "점유하지 않았다" 로 409 거절된다 —
    끊기지도 않은 작업을 배포가 버리는 셈이다. 먼저 끝내는 쪽이 이기게 두는 것이 손실이 없다.

    `grace_sec` (기본 60): **그 시간 안에 점유된 것은 건드리지 않는다.** 배포 직후 새 replica
    에서 막 시작된 정상 작업까지 재노출하면, 하나뿐인 연결이 자기가 처리 중인 질문을 다시
    가져가는 중복이 생긴다.

    ## 범위에 **하한**이 있다 (적대 리뷰 P1)

    초판은 상한만 두어 "60초보다 오래된 **모든** 점유" 를 만료시켰다. 배포와 무관하게 15분째
    조사 중이던 작업까지 대기열에 되돌려, 다른 세션이 재점유하면 원 소유자의 제출이
    `ClaimedClient` 불일치로 409 가 됐다 — 끊기지도 않은 작업을 배포가 버리는 셈이다.

    `since_epoch` 로 **배포 창의 시작**을 받아, 그 이후에 점유된 것만 대상으로 한다(= 이번
    배포가 실제로 끊었을 수 있는 것). 미지정이면 보수적으로 최근 `window_sec`(기본 1800초)
    안으로 제한한다 — 무제한 전역 sweep 은 하지 않는다.
    """
    denied = _loopback_only(request)
    if denied is not None:
        return denied
    if conn is None:
        return JSONResponse({"error": "db connection unavailable", "released": 0},
                            status_code=503)

    def _int_param(name: str, default: int, lo: int, hi: int) -> int:
        try:
            return max(lo, min(int(str(request.query_params.get(name) or default).strip()), hi))
        except ValueError:
            return default

    grace = _int_param("grace_sec", 60, 0, 3600)
    window = _int_param("window_sec", 1800, 60, 86400)
    since_raw = str(request.query_params.get("since_epoch") or "").strip()
    cur = None
    try:
        cur = conn.cursor()
        # 24시간 전으로 민다 — 어떤 lease 값이든 만료로 판정되므로 상수를 여기서 알 필요가 없다.
        sql = ("UPDATE WebAiTasks SET ClaimedAt = DATE_SUB(NOW(), INTERVAL 24 HOUR) "
               "WHERE Origin='web' AND Status='open' AND SubmittedAt IS NULL "
               "  AND ClaimedBy IS NOT NULL AND ClaimedAt IS NOT NULL "
               "  AND ClaimedAt <= DATE_SUB(NOW(), INTERVAL %s SECOND) ")
        if since_raw:
            sql += "  AND ClaimedAt >= FROM_UNIXTIME(%s)"
            params: tuple = (grace, int(float(since_raw)))
        else:
            sql += "  AND ClaimedAt >= DATE_SUB(NOW(), INTERVAL %s SECOND)"
            params = (grace, window)
        cur.execute(sql, params)
        released = int(cur.rowcount or 0)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("bridge-reclaim 실패: %s", exc, exc_info=True)
        return JSONResponse({"error": str(exc), "released": 0}, status_code=503)
    finally:
        if cur is not None:
            cur.close()
    if released:
        logging.getLogger(__name__).warning(
            "bridge-reclaim: 배포 강행으로 끊겼을 수 있는 점유 %d건의 lease 를 만료시켰다"
            "(원 소유자가 살아 있으면 그대로 제출된다).", released)
    return JSONResponse({"released": released, "grace_sec": grace,
                         "scoped_by": "since_epoch" if since_raw else f"window_sec={window}"},
                        status_code=200)

@router.get("/api/session")
def get_session(request: Request) -> JSONResponse:
    # api-exposure-hardening (2026-08-11): 미인증 응답은 `authenticated` 판정 하나로 좁힌다.
    # 종전에는 로그인 전에도 `local_llm_enabled`(로컬 LLM 운용 여부)와 `default_model`(기본 모델)을
    # 익명에게 노출했다 — 로그인 오버레이가 화면을 덮는 시점이라 UI 가 쓰지 않는 값이고, 프론트의
    # 모델 라벨은 `state.session?.default_model || state.modelCatalog?.default_model || ...` fallback
    # 체인이라 부재에 graceful 하다. 로그인 후 initializeWorkspace() 가 인증 상태로 재조회한다.
    local_llm_enabled = app._is_local_llm_available()
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"authenticated": False})
    account = app._get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse({"authenticated": False})
    # TASK-0048 후속 fix: /api/session 응답 조립 시 자동으로 빈 대화를 만들지 않는다 (lazy 정책).
    conversation_id = app._repair_current_conversation(
        conn,
        account,
        create_if_missing=False,
    )
    try:
        products = app._list_products(conn, include_inactive=False)
        # TASK-0295: 작업 화면 제품 목록을 계정의 product.access.<key> 권한으로 게이트.
        # 역할에 접근 권한 없는 제품은 picker 에서 제외 (mutation 경로의 403 enforcement 와 정합).
        products = app._filter_products_for_account_access(account, products)
        default_pid = app._coerce_default_product_id(app._get_default_product_id(conn), products)
    except Exception:
        products = []
        default_pid = 0
    # TASK-0261: 제품 목록에 datasource 연결(네트워크) 상태 첨부 — 드롭업 배지 색.
    try:
        app._attach_product_conn_status(conn, products)
    except Exception:
        pass
    # TASK-0047: 사용자 ProductPref 복원 + 현재 대화의 product_mode/product_id 동봉.
    product_pref = app._load_account_product_pref(conn, int(account.get("id") or 0), products)
    conversation_product = app._load_conversation_product(conn, conversation_id) if conversation_id else None
    # feature-0009 gc-participant-product-select: 공유 대화 참가자가 현재 대화의 고정 제품에
    # 접근권이 없으면 그 제품을 '생성자 제품 — 열람 전용'으로 분리 표시(드롭업 하단 회색 그룹).
    try:
        conversation_view_only_products = app._conversation_view_only_products_for(
            conn, conversation_id, account
        )
    except Exception:
        conversation_view_only_products = []
    payload = {
        "authenticated": True,
        "user": app._serialize_account(account),
        "conversation_id": conversation_id,
        "local_llm_enabled": local_llm_enabled,
        "default_model": app._resolve_session_default_model(),
        "public_url": app.WEB_PUBLIC_URL,
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
        "product_pref": product_pref,
        "conversation_product": conversation_product,
        "conversation_view_only_products": conversation_view_only_products,
        # TASK-20260619T014034: LLM provider 외부요인 제한 상태(컴포저 배너·상태점 초기값).
        "llm_provider_status": app._read_llm_provider_status(),
    }
    conn.close()
    return JSONResponse(payload)

@router.get("/api/api-vault/options")
def get_api_vault_options(request: Request) -> JSONResponse:
    """작업 화면 모델 선택기의 카탈로그 source.

    model-access-rbac(2026-07-28): 인증된 계정이면 `model.access.<value>` 권한으로 모델 목록을
    필터한다(`_filter_products_for_account_access` 가 제품 목록에 하는 것과 동형) — 선택기에 안
    보이는 모델을 서버가 거부하고, 서버가 거부할 모델이 선택기에 안 보이게 표시·집행을 함께 닫는다.

    api-exposure-hardening (2026-08-11): 비인증 요청은 **빈 카탈로그**를 받는다. 종전에는 필터 전
    전체 목록에 더해 `public_host`(내부 호스트명)·`public_url`·`provider`(bedrock-gateway)까지
    익명에게 나갔고, 외부 AI 감사가 이를 "인증 없이 공개되는 인프라 정보"로 적발했다(라이브 재현).
    "비인증은 `/api/ask` 가 401 이라 노출로 얻을 것이 없다" 는 종전 판단은 *데이터* 접근만 본 것이고,
    LLM 스택·모델 구성·내부 호스트명은 그 자체가 정찰 표면이다.

    회귀 없음의 근거: 미인증 프론트 경로는 auth overlay 가 화면을 덮은 상태에서 loadVaultOptions()
    를 부르고, 그 실패/공백을 이미 graceful 처리한다(`catch → state.modelCatalog = null`). 로그인
    직후 initializeWorkspace() 가 인증 상태로 재호출해 선택기를 채운다.

    인증 요청의 응답은 불변 — `model.access.<value>` 권한 필터도 그대로다. 권한 판정 실패(DB 미가용
    등)는 필터 전 목록으로 graceful — 집행은 ask() 게이트가 담당한다(display-permissive ·
    backend-enforced).

    bridge-model-selector (feature-0043, 2026-08-28): **서버 계정 LLM 이 차단된 동안 이 카탈로그는
    서버가 부를 수 없는 모델들의 목록**이다. 답변은 사용자의 개인 AI 가 만들고, 그 런타임이
    claude 일지 codex·gemini·ollama 일지 서버는 알 방법이 없다(MCP 어댑터가 별도 컨테이너라
    `clientInfo` 가 여기까지 오지 않는다). 그러므로 이 상태의 모델 선택기는 **무엇을 골라도
    답변이 달라지지 않는 조작면**이고, 고른 값(`claude-haiku-4` 같은 내부 alias)은 개인 AI 의
    CLI 가 알지 못해 실패 후 기본 모델로 폴백한다.

    사용자 결정(2026-08-28): 제어할 수 없으면 **보여주지 않는다**. `model_selector: "hidden"` 을
    실어 프론트가 항목 자체를 숨기게 하고, 목록은 비운다(빈 목록만으로는 "로딩 중" 과 구분되지
    않는다 — 그래서 상태를 값으로 말한다). 게이트를 되돌리면(`AGENT_SERVER_LLM_ENABLED=1`)
    같은 코드가 원래 카탈로그를 그대로 반환한다.

    runtime-model-selector (P0-Z3, 사용자 결정 2026-08-28 — 위 P0-T 를 **대체**): 위 문단의
    "서버는 알 방법이 없다" 는 전제를 러너가 직접 말해서 깬다. 상주 러너가 하트비트에
    자기가 쓸 수 있는 런타임·모델·추론등급을 실어 보내고(`WebOAuthTokens.RunnerCapabilities`),
    이 카탈로그는 **그 신고를 그대로** 목록으로 쓴다. 그래서 화면에 보이는 이름이 곧 그
    러너의 CLI 가 아는 이름이 되고, 고른 값이 실제로 반영된다.

    | 상태 | 응답 |
    |---|---|
    | 서버 LLM 차단 + 러너 신고 있음 | 신고 목록 + `model_selector: "visible"` (그룹 = 런타임) |
    | 서버 LLM 차단 + 러너 없음 | 빈 목록 + `"hidden"` + 「연결된 러너가 없어…」 |
    | 서버 LLM 차단 + 러너는 듣는데 고를 것 없음 | 빈 목록 + `"hidden"` + **다음 행동 + 받을 곳** |
    | 서버 LLM 활성 | 원래 서버 카탈로그 (게이트 되돌리기 경로, 불변) |

    "신고 없음" 이 곧 숨김인 것이 이 설계의 안전판이다 — 러너가 없거나(고를 주체가 없다),
    구 러너이거나(신고를 모른다), `--cmd` 로 명령을 직접 준 사용자(고른 값이 무시된다)일 때
    선택기가 나타나지 않는다. **반영되지 않을 조작면은 어느 경로로도 생기지 않는다.**

    caps-trust-gate (사용자 제보 2026-09-01, 4차 재발 · 같은 날 재설계): 폴백을 제거한 러너를
    배포해도 **사용자 머신의 러너를 우리가 갱신할 수는 없어서**, 낡은 빌드가 자기 소스의 내장
    표(`gpt-5.1-codex`)를 계속 신고했고 이 카탈로그가 그것을 그대로 그렸다.

    막는 지점은 **수신 시점**이다 — `ai_tools._sanitize_runtimes` 가 출처(`source`)가 라이브
    답이 아닌 런타임을 저장 전에 떨어뜨린다. 그래서 구 러너의 신고는 **첫 하트비트에** 빈
    목록이 되고, 이 함수는 그 결과를 그대로 읽기만 하면 된다.

    ⚠ 한때 여기 읽기 시점 전역 게이트(러너가 계약을 선언했는가 + 다중 러너 fail-closed)를
    더 뒀다가 **철회**했다(적대 패널 3인 확인 라운드). 수신 시점 게이트가 이미 짐을 다 지는데,
    전역 게이트가 더한 고유 효과는 「살아 있는 러너 하나라도 미선언이면 감춘다」뿐이었고 그
    대가가 **제품 안에서 풀 수 없는 무기한 잠금**이었다 — 다른 머신에 잊고 켜 둔 러너 하나가
    선택기를 무기한 감추는데 화면은 그 러너를 지목하지도, 끊지도 못한다.

    **빈 목록만 내리지 않고 사유를 함께 내리는 것**은 유지한다 — 사유 없이 감추면 선택기가
    이유 없이 사라진 것으로 보이고, 사용자는 다음 행동을 어디서도 듣지 못한다.

    이 분기는 **인증 확인 뒤**에 둔다 — 미인증 응답은 종전대로 빈 카탈로그이고, 게이트 상태라는
    운영 사실조차 익명에게 싣지 않는다(위 api-exposure-hardening 과 같은 방향).
    """
    models: list = []
    authenticated = False
    runner_caps: list = []
    # 러너는 듣고 있는데 능력 신고 자격이 없다(구 빌드) — "고를 것이 없다" 와 구분해야
    # 화면이 다음 행동을 말할 수 있다. 기본 False: 러너가 아예 없을 때와 섞지 않는다.
    # 러너가 **듣고 있는데 고를 모델이 없는가**. 이 한 축이 안내 문구와 링크를 가른다 —
    # 종전에 이 자리에 있던 `caps_contract_declared`·`mixed_runners` 두 축은 철회했다
    # (2026-09-01 재설계: 수신 시점 provenance 가 짐을 다 지고, 읽기 시점 전역 게이트는
    # 제품 안에서 풀 수 없는 잠금만 남겼다 — 적대 패널 3인 확인 라운드).
    runner_listening = False
    account_bridge_model = ""
    account_bridge_effort = ""
    conn = None
    try:
        conn = app._connect_memory()
        account = app._get_authenticated_account(conn, request)
        if account:
            authenticated = True
            models = app._filter_models_for_account_access(
                account, list(PUBLIC_API_MODEL_OPTIONS), conn=conn
            )
            # 브리지 모드에서 쓸 목록 (P0-Z3). 같은 conn 안에서 읽는다 — 별도 연결을 열면
            # 인증과 능력이 서로 다른 순간의 사실이 되고, 로그아웃 직후의 창이 벌어진다.
            if not server_llm_enabled():
                cur = conn.cursor()
                try:
                    # 능력과 **자격**을 한 행에서 함께 읽는다 (caps-trust-gate). 목록만 받아
                    # 오면 "비었다" 의 이유(러너 없음 / 고를 것 없음 / 자격 없음)를 잃는다.
                    _profile = _store.account_runner_profile(
                        cur, int(account.get("id") or 0))
                    runner_caps = list(_profile.get("capabilities") or [])
                    runner_listening = bool(_profile.get("listening"))
                    # 계정 기본값도 **같은 커넥션에서** 읽는다 — 별개 연결을 열면 목록과
                    # 기본값이 서로 다른 순간의 사실이 되고, 그 틈에서 "목록에 없는 기본값"
                    # 이 나온다.
                    #
                    # ⚠ 실패를 **여기서** 삼킨다. 바깥 except 로 흘리면 그쪽이 `runner_caps`
                    #   를 비워 선택기가 통째로 사라진다 — 시작점을 정해 주는 편의 기능 하나가
                    #   목록 전체를 지우는 형태다(회귀 테스트로 잠금).
                    try:
                        account_bridge_model, account_bridge_effort = \
                            _store.account_bridge_defaults(cur, int(account.get("id") or 0))
                    except Exception:
                        account_bridge_model, account_bridge_effort = "", ""
                finally:
                    cur.close()
    except Exception:
        # 카탈로그 조회는 화면 부트스트랩 경로 — 권한 필터 실패로 선택기를 비우지 않는다(fail-soft).
        # 단 인증 여부를 확정하지 못한 요청에까지 전체 목록을 주지는 않는다(fail-soft ≠ fail-open).
        if authenticated:
            models = list(PUBLIC_API_MODEL_OPTIONS)
        # ⚠ 능력 조회 실패는 fail-soft 로 **채우지 않는다** — 여기서 추측한 목록은 그 러너에
        #   없는 모델일 수 있고, 그것을 고른 요청은 반영되지 않는다(P0-T 가 지운 상태의 재발).
        #   빈 목록은 선택기가 숨겨질 뿐이고, 답변 경로는 그대로 동작한다.
        runner_caps = []
        # 조회가 실패했으면 러너가 듣고 있는지도 **모르는** 것이다 — 모르는 것을 근거로
        # 갱신 안내를 띄우면, 일시적 DB 오류가 멀쩡한 사용자에게 틀린 지시를 준다.
        runner_listening = False
        # 기본값도 같이 버린다 — 목록 없이 남은 기본값은 대조할 곳이 없어 그대로 쓰이거나
        # (없는 값이 선택돼 보이거나) 어차피 아래 `visible=False` 로 무시된다. 두 사실을
        # 함께 버려 "목록은 실패했는데 기본값만 살아 있는" 중간 상태를 만들지 않는다.
        account_bridge_model = ""
        account_bridge_effort = ""
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if not authenticated:
        return JSONResponse({"default_model": None, "models": []})
    if not server_llm_enabled():
        # 브리지 모드 — 목록의 출처는 **연결된 러너의 신고**다(위 docstring 의 표).
        bridge_models: list = []
        reasoning_by_runtime: dict = {}
        for rt in runner_caps:
            name = str(rt.get("runtime") or "")
            label = str(rt.get("label") or name)
            for m in (rt.get("models") or []):
                bridge_models.append({
                    # 값에 런타임을 접두한다 — 한 머신에 claude·codex 가 함께 있으면 모델
                    # 이름만으로는 어느 CLI 의 것인지 정해지지 않는다(`sonnet` 이 두 곳에
                    # 있을 수도 있다). 화면이 고른 항목이 어느 그룹에서 왔는지를 값 자체가
                    # 지니게 해, 전송·적재·전달 어디서도 그 짝이 풀리지 않는다.
                    "value": f"{name}:{m.get('value')}",
                    "label": str(m.get("label") or m.get("value") or ""),
                    "group": label,
                })
            # 추론등급은 런타임마다 다르다(gemini 는 아예 없다). 화면이 고른 모델의 런타임을
            # 보고 해당 목록을 그리도록 런타임별로 내려준다.
            reasoning_by_runtime[name] = list(rt.get("efforts") or [])
        visible = bool(bridge_models)
        # 계정 기본값 — **지금 신고된 목록 안에 있을 때만** 쓴다 (2026-08-31, 사용자 결정).
        #
        # 러너를 바꿨거나(claude 머신 → codex 머신) 그 모델이 사라졌으면 저장값은 여기서
        # 탈락하고 첫 항목으로 떨어진다. 대조 없이 내려보내면 화면은 "고를 수 없는 것이
        # 선택돼 있는" 상태가 되고, 그 값으로 보낸 질문은 러너가 버린다.
        _default_model = bridge_models[0]["value"] if visible else None
        _default_effort = ""
        if visible:
            _offered_values = {m["value"] for m in bridge_models}
            if account_bridge_model and account_bridge_model in _offered_values:
                _default_model = account_bridge_model
            # 등급은 **고른 모델의 런타임** 목록으로 대조한다 — claude 의 `xhigh` 는 codex 에
            # 없다. 모델이 바뀌면 등급도 함께 무효가 되는 것이 이 축의 성질이다.
            _rt = str(_default_model or "").split(":", 1)[0]
            if account_bridge_effort and any(
                    str(e.get("value")) == account_bridge_effort
                    for e in (reasoning_by_runtime.get(_rt) or [])):
                _default_effort = account_bridge_effort
        return JSONResponse({
            # ⚠ `None` 으로 두면 프론트가 **서버 기본값(haiku)** 으로 폴백한다
            # (codex REV-20260828T170000 P1-2): 사용자가 선택기를 건드리지 않고 보낸 첫 질문에
            # 그 alias 가 실려 굳고, 러너는 자기 목록에 없으니 버린다 — "고른 적 없는 값이
            # 저장되고 반영은 안 되는" 상태가 신규 대화마다 재현된다.
            # 신고 목록의 **첫 항목**을 기본값으로 명시해 그 폴백 경로를 끊는다.
            # 계정 기본값이 지금도 유효하면 그것이 첫 항목을 대신한다(위 대조 참조).
            "default_model": _default_model,
            # 사용자가 마지막으로 고른 추론등급 — 새 대화가 이 값으로 시작한다. 빈 문자열은
            # "저장된 값이 없거나 지금 런타임에서 무효" 이고, 그때 프론트는 목록 첫 항목을 쓴다.
            "default_reasoning_level": _default_effort,
            "models": bridge_models,
            "server_llm_enabled": False,
            # 프론트 계약: "hidden" 이면 모델·추론 강도 조작면을 DOM 에서 감춘다.
            "model_selector": "visible" if visible else "hidden",
            "model_selector_source": "runner" if visible else "",
            "reasoning_levels_by_runtime": reasoning_by_runtime,
            # 숨김의 **이유**를 값으로 말한다 (§16.8 예산: 1문장). 구 러너는 다음 행동이
            # 있으므로 그것을 적고, 그 밖의 숨김은 종전 문구를 유지한다.
            # 숨김의 **이유**를 값으로 말한다 (§16.8 예산: 1문장). 두 상태뿐이다 —
            # 러너가 없거나(고를 주체 없음), 듣고 있는데 고를 모델이 없거나.
            # 후자는 「러너가 오래됐거나 AI 에게 물어보지 못했다」가 둘 다 참일 수 있으므로
            # 원인을 단정하지 않고 **다음 행동**만 말한다(§16.7 G7-c: 미확보는 단정하지 않는다).
            "model_selector_reason": (
                "연결된 본인 AI 가 쓸 수 있는 모델입니다."
                if visible else
                "연결된 러너가 알려준 모델이 없습니다 — 최신 실행 파일로 다시 실행해 보세요."
                if runner_listening else
                "답변은 연결된 본인 AI 가 생성합니다 — 연결된 러너가 없어"
                " 이 화면에서는 모델을 지정할 수 없습니다."
            ),
            # 프론트가 사유 문구를 파싱하지 않게 상태를 **별도 값**으로 준다.
            "runner_listening": runner_listening,
            # 프런트가 안내 안 **링크로 그린다**(소비처 0 이던 것을 배선 — 적대리뷰 C2).
            # 링크는 러너가 듣고 있을 때만 의미가 있다: 러너가 아예 없으면 받을 파일이
            # 아니라 연결 흐름이 먼저다.
            "runner_download_url": "/static/agent/bridge_agent.py",
        })
    return JSONResponse(
        {
            "default_model": API_DEFAULT_MODEL,
            "models": models,
            "server_llm_enabled": True,
            "model_selector": "visible",
            "public_host": app.WEB_PUBLIC_HOST,
            "public_url": app.WEB_PUBLIC_URL,
            "provider": "bedrock-gateway",
        }
    )


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _active_stream_count() -> int:
    with app._ACTIVE_STREAMS_LOCK:
        return app._ACTIVE_STREAMS

def _is_local_llm_available() -> bool:
    base_url = str(os.getenv("LOCAL_LLM_API_BASE", "") or "").strip()
    if not base_url:
        return False
    now = app.time.time()
    if now - float(app._LOCAL_LLM_STATUS.get("checked_at") or 0.0) < 30:
        return bool(app._LOCAL_LLM_STATUS.get("value"))
    parsed = app.urlparse(base_url)
    host = str(parsed.hostname or "").strip()
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    available = False
    if host:
        try:
            with app.socket.create_connection((host, port), timeout=1.5):
                available = True
        except OSError:
            available = False
    app._LOCAL_LLM_STATUS["checked_at"] = now
    app._LOCAL_LLM_STATUS["value"] = available
    return available

def _safe_shared_path(path: str) -> app.Path | None:
    if not path:
        return None
    try:
        resolved = app.Path(path).expanduser().resolve()
    except Exception:
        return None
    if resolved == app.SHARED_ROOT or app.SHARED_ROOT in resolved.parents:
        return resolved
    return None


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _read_llm_provider_status_admin() -> "dict[str, Any]":
    """**관리자 관제 전용** provider 상태 — feature-0043 차단 마스킹을 통과하지 않은 원본.

    대화 UI 용 `_read_llm_provider_status()` 는 차단 중 상태를 non-restricted 로 덮는다(전송에
    영향이 없고, 복구 ping 이 불가능해 배너가 영구 고착되므로). 그 마스킹이 관제까지 오면
    운영자는 "정상" 만 보고, 게이트를 되돌리는 순간 숨어 있던 제한이 되살아난다.

    `server_llm_blocked` 를 함께 실어 "왜 이 값을 그대로 믿으면 안 되는지" 를 남긴다.
    """
    try:
        from modules.llm_provider_health import _read_provider_health_raw
        from shared.llm_gate import server_llm_enabled

        out = dict(_read_provider_health_raw() or {})
        out["server_llm_blocked"] = not server_llm_enabled()
        return out
    except Exception:
        return {"state": "unknown", "server_llm_blocked": False}


def _read_llm_provider_status() -> "dict[str, Any]":
    """TASK-20260619T014034: LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health)
    를 읽어 web 표면(컴포저 배너·상태점·툴팁·실행단계 패널)에 싣는다. probe 없이 cheap PG read 만
    (probe 는 /api/llm/health 전용). 실패/미가용은 graceful {state:'unknown'}."""
    try:
        from modules.llm_provider_health import read_provider_health
        return read_provider_health()
    except Exception:
        return {"state": "unknown"}
