"""feature-0012 P5b Final — system 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

import app

router = APIRouter()


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
        return JSONResponse(app._read_llm_provider_status())
    account = app._get_authenticated_account(conn, request)
    if not account:
        # 미인증: probe 트리거 없이 마지막 알려진 상태만.
        return JSONResponse(app._read_llm_provider_status())
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
