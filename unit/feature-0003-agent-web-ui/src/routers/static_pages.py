"""feature-0012 P5b Final — static_pages 도메인 APIRouter (무인증 정적 페이지 + 헬스 프로브).

NS-BOUND=0 도메인: 인증 0(`/`·`/admin`·`/share/{token}` 는 정적 HTML serve, `/healthz` 는 인증
불필요 readiness probe). app.* monkeypatch 의존 pytest 0(검증 완료) — web_context 선행 불요.

순환 안전: `import app` 은 app 이 모든 정의를 마친 뒤 맨 끝 include_router 시점에 실행되므로
이미 sys.modules 에 완성된 모듈을 바인딩한다. 또한 _connect_memory/load_memory_kv 같은
heavily-monkeypatched 헬퍼는 import-time 복사(`from app import`)가 아닌 **호출 시 `app.X`
속성 접근**으로 참조해 테스트 monkeypatch 호환을 보존한다(STATIC_DIR/_HTML_NO_CACHE 도 동일
규약으로 통일). 경로/메서드/응답 byte-동치(원본 app.py 핸들러와 동일 로직·헤더·status).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

import app

INCLUDE_ORDER = 10  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# FileResponse 는 app.FileResponse 속성으로 호출한다(test_html_no_cache 가
# monkeypatch.setattr(app,"FileResponse",...) 로 가로채는 계약 보존 — 원본도 app
# 모듈 전역 FileResponse 를 사용했다). 반환 타입 주석은 정적 심볼(import 한 FileResponse) 사용.
@router.get("/")
def index() -> FileResponse:
    return app.FileResponse(app.STATIC_DIR / "index.html", headers=app._HTML_NO_CACHE)


@router.get("/admin")
def admin_index() -> FileResponse:
    return app.FileResponse(app.STATIC_DIR / "admin.html", headers=app._HTML_NO_CACHE)


# REQ-20260514-0001: 공유 링크 페이지 (anonymous accessible). 실제 token 검증은
# 클라이언트 JS 가 `/api/public/share/{token}` 호출로 수행한다. 본 route 는
# 정적 share.html serve 만 담당. AGENTS.md / SECURITY.md 에 명시된 유이한
# anonymous-allowed 페이지 경로.
@router.get("/share/{token}")
def share_page(token: str) -> FileResponse:
    return app.FileResponse(app.STATIC_DIR / "share.html", headers=app._HTML_NO_CACHE)


@router.get("/healthz")
def healthz() -> JSONResponse:
    """TASK-0126 (#5 split-brain / #4 워커 가시성): 배포 provenance + readiness probe.
    인증 불필요, 최소 정보만 노출한다. git_commit 으로 web·insight-worker 가 동일 빌드인지
    검증하고, insight_heartbeat_age_sec 로 워커 생존을 확인한다. Docker HEALTHCHECK 가
    본 endpoint 를 사용한다 (mysql·pg 둘 다 정상이면 200, 아니면 503)."""
    git_commit = os.environ.get("GIT_COMMIT", "unknown")
    mysql_ok = False
    pg_ok = False
    heartbeat_age_sec: int | None = None

    conn = None
    try:
        conn = app._connect_memory()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        mysql_ok = True
    except Exception:
        logging.getLogger(__name__).warning("healthz: mysql check failed", exc_info=True)

    if conn is not None:
        try:
            from shared.config import GLOBAL_CONVERSATION_ID

            raw = app.load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
            if raw:
                ts = str(raw).strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                heartbeat_age_sec = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        except Exception:
            logging.getLogger(__name__).warning("healthz: insight heartbeat read failed", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass

    try:
        from shared.db import _pg_available

        pg_ok = bool(_pg_available())
    except Exception:
        logging.getLogger(__name__).warning("healthz: pg check failed", exc_info=True)

    ok = mysql_ok and pg_ok
    return JSONResponse(
        {
            "status": "ok" if ok else "degraded",
            "git_commit": git_commit,
            "mysql_ok": mysql_ok,
            "pg_ok": pg_ok,
            "insight_heartbeat_age_sec": heartbeat_age_sec,
        },
        status_code=200 if ok else 503,
    )
