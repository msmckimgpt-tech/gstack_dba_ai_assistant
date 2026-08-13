"""feature-0041 (REQ-20260812-external-ai-tool-surface) — 외부 AI 원시 도구 표면 (P0).

feature-0023 의 `ask` 는 외부 AI 를 *질문하는 사람* 으로 두고 **우리 LLM 이 추론**한다. 여기서는
그 관계가 뒤집힌다 — 우리는 도구·컨텍스트만 주고 추론 루프는 호출자 런타임에서 돈다. 그래서
LLM 비용이 호출자에게 귀속되고, 우리 계정 쿼터 소진이 이 표면을 멈추지 않는다.

## 요청 1건이 지나는 관문 (순서 고정)

    ① OAuth access token → 계정·client·세션 (세션 죽으면 401)
    ② 부하 상한 조회      → 초과 429 / 조회 불가 5xx  (tool_ledger, fail-closed)
    ③ 스코프 해석·교차검증 → product/datasource 가 계정 권한 밖이면 403 (tool_authz)
    ④ 도구 실행           → tools.execute_tool (내부 에이전트와 **같은** 가드·SQL 신뢰경계)
    ⑤ 세션 각인           → datamark + [SCOPE] (session_guard)
    ⑥ 원장 커밋           → **결과 반환 전** · 실패 시 5xx (codex P1)

②·⑥ 이 같은 원장을 쓰는 것이 요점이다: 누적 상한의 원천이 원장이므로 기록이 실패하면 상한을
집행할 수 없고, 그때 결과를 주면 상한이 우회된다.

## P0 도구 9종

세션 계약 3종(`open_task`/`get_task_context`/`submit_answer`) + 구조 조회 6종.
`execute_sql` 은 **P1** — 행수 예산·rate limit·추출 원장이 선행 조건이라 여기 없다.
쓰기·첨부·scratch 계열은 영구 제외(세션 간 서버측 공유 상태를 만들지 않는다).
"""
from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 9_450  # oauth_as(9_400) 다음, ai_discovery(9_500) 앞
router = APIRouter()

# feature-0041 서버측 모듈은 **이 디렉터리**(= 컨테이너 `/app/web`)에 있다.
# 초기 구현은 feature-local `unit/feature-0041-.../src` 에 두고 sys.path 를 주입했는데,
# agent 이미지가 그 경로를 COPY 하지 않아 라이브 기동이 ModuleNotFoundError 로 죽었다
# (Dockerfile 은 feature-0002/0003/shared 만 복사). 소비자가 feature-0003 라우터뿐이므로
# 코드 거주지를 소비처로 옮기는 것이 이 저장소 관례에도 맞다.
import oauth_store as _store        # noqa: E402
import session_guard as _guard      # noqa: E402
import tool_authz as _authz         # noqa: E402
import tool_ledger as _ledger       # noqa: E402

# 구조 조회 도구 allowlist. **여기 없는 이름은 도달 불가** — tools.py 에 무엇이 있든
# 이 표면에 열리는 것은 이 집합뿐이다(도구가 늘어도 자동으로 새어나가지 않는다).
P0_TOOLS = frozenset({
    "list_schemas", "describe_schema", "describe_table",
    "search_tables", "get_foreign_keys", "get_table_indexes",
})


# ── 인증 ──────────────────────────────────────────────────────────────────────

def _bearer(request: Request) -> str:
    raw = str(request.headers.get("authorization", "") or "")
    return raw[7:].strip() if raw[:7].lower() == "bearer " else ""


_REQUIRED_SCOPE = "data.read"


def _challenge(request: Request) -> dict[str, str]:
    """RFC 9728 — 401 이 **인증 방법의 위치**를 알려준다.

    이게 없으면 MCP 클라이언트는 "인증이 필요하다"는 것만 알고 *어디서* 받는지 모른다.
    그래서 사람이 등록·PKCE·코드 교환을 손으로 대신해야 했다(셸 스크립트가 필요했던 이유).
    """
    origin = str(request.base_url).rstrip("/")
    return {"WWW-Authenticate":
            f'Bearer resource_metadata="{origin}/.well-known/oauth-protected-resource"'}


# 엣지(Caddy)가 **무토큰 `/api/ai/mcp*` 요청만** 여기로 넘긴다. 목적은 두 가지다.
#   ① 익명 요청이 `ext-tool-mcp` 에 닿아 MCP 세션/스트림을 열지 못하게 한다(원래 차단 목적).
#   ② 그러면서 401 의 `resource_metadata` **호스트가 접속에 쓴 호스트와 같아야** 한다 —
#      이 배포는 사내 이름·공인 IP·loopback 여러 이름으로 도달하고, 엣지에 이름을 박아 두면
#      IP 로 붙은 외부 클라이언트가 해석 안 되는 이름을 따라가다 discovery 가 끊긴다(실측).
# 여기서 만들면 `request.base_url` 이 접속 호스트를 따르고, TrustedHost 가 그 호스트를 이미
# 검증한다(엣지에서 `{host}` 를 되비추면 검증 없는 반사가 된다).
@router.api_route("/api/ai/mcp", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
@router.api_route("/api/ai/mcp/{rest:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
def mcp_unauthenticated(request: Request, rest: str = "") -> JSONResponse:
    raise app._AuthError("Bearer access token 이 필요합니다.", 401, _challenge(request))


def require_ai_token(request: Request, conn=Depends(app.get_conn)) -> dict[str, Any]:
    """access token → 계정 컨텍스트. 세션이 죽었으면 401(= '세션 실재' 집행면)."""
    token = _bearer(request)
    if not token:
        raise app._AuthError("Bearer access token 이 필요합니다.", 401, _challenge(request))
    if conn is None:
        # `app.get_conn` 은 memory DB 실패를 흡수해 None 을 준다. 분기하지 않으면 AttributeError
        # 로 500 이 나고, 그 500 은 클라이언트에 "토큰이 잘못됐다" 로 읽힌다(재인증 루프).
        raise app._AuthError("일시적으로 처리할 수 없습니다. 잠시 후 다시 시도하세요.", 503)
    cur = conn.cursor()
    try:
        resolved = _store.resolve_access_token(cur, token)
    finally:
        cur.close()
    if not resolved:
        raise app._AuthError("유효하지 않거나 만료된 토큰입니다.", 401, _challenge(request))
    account = app._load_account_by_id(conn, int(resolved["account_id"])) \
        if hasattr(app, "_load_account_by_id") else None
    if account is None:
        rows = app._fetch_account_rows(conn, "a.Id = %s AND a.IsActive = 1 AND a.DeletedAt IS NULL",
                                       (int(resolved["account_id"]),), include_password=False,
                                       limit_sql="LIMIT 1")
        rows = app._decorate_account_rows(conn, rows)
        account = rows[0] if rows else None
    if not account:
        raise app._AuthError("계정을 찾을 수 없습니다.", 401)
    # codex P1 — 저장된 scope 를 아무도 읽지 않으면 동의 화면이 표시한 범위가 **장식**이 된다.
    # 도구 표면은 전부 읽기이므로 요구 scope 는 하나뿐이지만, 집행 지점이 존재해야 나중에
    # 쓰기 도구를 추가할 때 "그때 붙이자" 가 되지 않는다.
    granted = {t for t in str(resolved.get("scopes") or "").replace(",", " ").split() if t}
    if _REQUIRED_SCOPE not in granted:
        raise app._AuthError(f"이 토큰에는 {_REQUIRED_SCOPE} 권한이 없습니다.", 403)
    return {"account": account, "client_id": resolved.get("client_id"),
            "session_id": resolved.get("session_id"), "scopes": resolved.get("scopes")}


def _pg():
    """원장용 RW 연결. 없으면 None — 호출측이 fail-closed 로 처리한다."""
    try:
        from modules.runtime_backend import _get_pg_runtime_conn
        return _get_pg_runtime_conn()
    except Exception:
        return None


# ── task 세션 계약 ────────────────────────────────────────────────────────────

@router.post("/api/ai/tools/open_task")
async def open_task(request: Request, ctx=Depends(require_ai_token),
                    conn=Depends(app.get_conn)) -> JSONResponse:
    """작업 단위를 열고 **원 질문을 서비스 측에 기록**한다.

    대화 기록 보존 요구의 시작점이다. 이후 모든 도구 호출은 이 `task_id` 를 요구하므로,
    "무엇을 물었고 무엇을 조회했는가" 는 우리가 확실히 갖는다(최종 답변만 자발 제출에 의존).
    """
    body = await _json(request)
    account = ctx["account"]
    question_raw = str(body.get("question") or "").strip()
    if not question_raw:
        return _json_err(400, "question 이 필요합니다.")

    # codex P1 — 상한이 구조 조회에만 걸려 있어 `open_task` 는 무제한이었다. task 생성도
    #   DB 쓰기라 같은 축으로 세고, 미제출 누적 상한도 여기서만 집행된다.
    try:
        _ledger.check_limits(_pg(), account_id=int(account.get("id") or 0),
                             client_id=ctx.get("client_id"))
        _ledger.check_open_tasks(conn, account_id=int(account.get("id") or 0))
    except _ledger.RateLimited as exc:
        _safe_record(account, ctx, tool="open_task", outcome="gated", detail=exc.limit)
        return JSONResponse({"error": exc.message}, status_code=429,
                            headers={"Retry-After": str(exc.retry_after)})
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"상한을 확인할 수 없어 요청을 중단했습니다: {exc}")

    verdict = _guard.classify_injection(question_raw)
    if verdict["verdict"] == "reject":
        _safe_record(account, ctx, tool="open_task", outcome="denied",
                     detail=f"injection:{','.join(verdict['matched'])[:180]}")
        return _json_err(400, "요청에 지시 전복 시도로 판정된 문구가 있어 거절했습니다.")
    question = verdict["text"]

    try:
        product = _authz.resolve_product(app, account, conn, body.get("product_id"))
    except _authz.ScopeDenied as exc:
        _safe_record(account, ctx, tool="open_task", outcome="denied", detail=exc.code)
        return _json_err(403, exc.message)

    task_id = "t_" + secrets.token_urlsafe(12)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebAiTasks (TaskId, AccountId, ClientId, ProductId, Question, "
            "Status, InjectionVerdict) VALUES (%s,%s,%s,%s,%s,'open',%s)",
            (task_id, int(account.get("id") or 0), ctx.get("client_id"),
             int(product.get("id") or 0), question[:4000], verdict["verdict"]))
        conn.commit()
    finally:
        cur.close()

    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0), tool="open_task",
                       client_id=ctx.get("client_id"), task_id=task_id, outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    # L4 — 같은 client 에 권한 격차가 큰 세션이 동시 활성인지. **원장 전용**(응답 미포함).
    #
    # ⚠ codex P1: 응답에 실으면 **교차 테넌트 정보 노출**이다. OAuth `client_id` 는 DCR 로
    #   누구나 받는 **앱 식별자**이지 설치·사용자 식별자가 아니라, 서로 무관한 사용자들이 같은
    #   client_id 를 공유할 수 있다. 그 상태에서 상대 계정 id·권한 겹침을 돌려주면 호출자가
    #   자기와 무관한 사용자의 존재와 권한 윤곽을 알게 된다. L4 의 목적은 **운영자 관측**이지
    #   호출자 통보가 아니므로 원장에만 남긴다.
    asym = _permission_asymmetry(conn, ctx, account)
    if asym:
        _safe_record(account, ctx, tool="open_task", outcome="ok", task_id=task_id,
                     detail=f"asymmetry:jaccard={asym['jaccard']}:n={asym['n_accounts']}")

    return JSONResponse({
        "task_id": task_id,
        "product": {"id": int(product.get("id") or 0), "name": product.get("name")},
        "canary": _guard.session_canary(task_id),
        "session_notice": _session_notice(account),
        "next": "get_task_context 로 근거를 받은 뒤 구조 조회 도구를 쓰고, "
                "끝나면 submit_answer 로 최종 답변을 제출하세요.",
    })


@router.post("/api/ai/tools/get_task_context")
async def get_task_context(request: Request, ctx=Depends(require_ai_token),
                           conn=Depends(app.get_conn)) -> JSONResponse:
    """grounding 번들. **우리 LLM 을 호출하지 않는다**(조회·렌더만 — AC-4).

    내부 대화 경로가 프롬프트에 주입하던 층(L2 클러스터 요약·L3 도메인 개요)을 그대로
    조회해서 넘긴다. 이게 없으면 외부 AI 는 "스키마만 아는 상태" 로 SQL 을 쓰게 되고,
    그동안 쌓은 정합 층이 통째로 우회된다.
    """
    body = await _json(request)
    account, task = ctx["account"], None
    task_id = str(body.get("task_id") or "")
    task = _load_task(conn, task_id, account)
    if task is None:
        return _json_err(404, "task 를 찾을 수 없습니다.")

    t0 = time.perf_counter()
    sections: list[str] = []
    try:
        from modules import cluster_context as _cc
        if _cc.enabled():
            rows = _cc.load_cluster_summary_context(task.get("question") or "", conn=None)
            rendered = _cc.render(rows) if rows else ""
            if rendered:
                sections.append(rendered)
    except Exception:
        pass   # grounding 부재는 degrade — 도구 자체를 막지 않는다

    payload = "\n\n".join(s for s in sections if s) or "(관련 요약 없음 — 구조 조회 도구로 탐색하세요)"
    marked = _guard.wrap_tool_output(
        f"{_guard.session_canary(task_id)}\n{payload}",
        account=str(account.get("username") or account.get("id")),
        conversation_id=task.get("conversation_id"), task_id=task_id, source="task_context")

    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0), tool="get_task_context",
                       client_id=ctx.get("client_id"), task_id=task_id,
                       bytes_out=len(marked.encode("utf-8")),
                       latency_ms=int((time.perf_counter() - t0) * 1000), outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    return JSONResponse({"task_id": task_id, "context": marked})


@router.post("/api/ai/tools/submit_answer")
async def submit_answer(request: Request, ctx=Depends(require_ai_token),
                        conn=Depends(app.get_conn)) -> JSONResponse:
    """최종 답변 제출 + **교차오염 대조**.

    `source_tasks` 선언을 필수로 받는다 — 선언하려면 외부 AI 가 "이 데이터가 어느 세션 것인가" 를
    실제로 판단해야 하고(인지 강화), 선언과 원장이 어긋나면 우리가 잡는다(대조). 다만 값이
    요약·환산되면 못 잡는다(AC-5 미탐 허용).
    """
    body = await _json(request)
    account = ctx["account"]
    task_id = str(body.get("task_id") or "")
    answer = str(body.get("answer") or "").strip()
    declared = body.get("source_tasks")
    if not answer:
        return _json_err(400, "answer 가 필요합니다.")
    if not isinstance(declared, list):
        return _json_err(400, "source_tasks 선언이 필요합니다(근거로 쓴 task id 목록).")

    task = _load_task(conn, task_id, account)
    if task is None:
        return _json_err(404, "task 를 찾을 수 없습니다.")

    foreign = _sibling_tasks(conn, account, ctx.get("client_id"), exclude=task_id)
    findings = _guard.detect_cross_session(
        answer, task_id=task_id, declared_tasks=[str(d) for d in declared],
        foreign_tasks=[f["task_id"] for f in foreign],
        foreign_accounts=[str(account.get("username") or "")])

    cur = conn.cursor()
    try:
        cur.execute("UPDATE WebAiTasks SET Status = 'submitted', SubmittedAt = NOW() "
                    "WHERE TaskId = %s", (task_id,))
        conn.commit()
    finally:
        cur.close()

    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0), tool="submit_answer",
                       client_id=ctx.get("client_id"), task_id=task_id,
                       bytes_out=len(answer.encode("utf-8")),
                       outcome="denied" if findings else "ok",
                       detail=("cross_session:" + ",".join(f["kind"] for f in findings))[:255]
                       if findings else None)
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    return JSONResponse({"task_id": task_id, "recorded": True,
                         "cross_session_findings": findings})


# ── 구조 조회 6종 ─────────────────────────────────────────────────────────────

@router.post("/api/ai/tools/{tool_name}")
async def run_structure_tool(tool_name: str, request: Request, ctx=Depends(require_ai_token),
                             conn=Depends(app.get_conn)) -> JSONResponse:
    """P0 구조 조회. 내부 에이전트와 **같은** `tools.execute_tool` 을 탄다 — SQL 신뢰경계·
    부하 게이트·allowlist 를 재구현하지 않는다(재구현은 곧 두 벌 관리이고, 갈리는 순간 약한
    쪽이 실질 경계가 된다)."""
    if tool_name not in P0_TOOLS:
        return _json_err(404, f"'{tool_name}' 는 이 표면에 노출된 도구가 아닙니다.")

    body = await _json(request)
    account = ctx["account"]
    task_id = str(body.get("task_id") or "")
    task = _load_task(conn, task_id, account)
    if task is None:
        return _json_err(400, "task_id 가 필요합니다(open_task 로 먼저 여세요).")

    try:
        _ledger.check_limits(_pg(), account_id=int(account.get("id") or 0),
                             client_id=ctx.get("client_id"))
    except _ledger.RateLimited as exc:
        _safe_record(account, ctx, tool=tool_name, outcome="gated", detail=exc.limit,
                     task_id=task_id)
        return JSONResponse({"error": exc.message}, status_code=429,
                            headers={"Retry-After": str(exc.retry_after)})
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"상한을 확인할 수 없어 요청을 중단했습니다: {exc}")

    arguments = dict(body.get("arguments") or {})
    product_id = int(task.get("product_id") or 0)

    import agent_core as _core
    import modules.tools as _tools

    try:
        labels = _authz.allowed_datasource_labels(_core, conn, product_id)
        _authz.assert_datasource_allowed(arguments.get("datasource"), labels)
    except _authz.ScopeDenied as exc:
        _safe_record(account, ctx, tool=tool_name, outcome="denied", detail=exc.code,
                     task_id=task_id)
        return _json_err(403, exc.message)

    t0 = time.perf_counter()
    try:
        with _authz.scoped_execution(_core, _tools, conn, product_id) as _router:
            out = _tools.execute_tool(None if _router else conn, tool_name, arguments)
    except Exception as exc:  # noqa: BLE001
        _safe_record(account, ctx, tool=tool_name, outcome="error", detail=str(exc)[:200],
                     task_id=task_id)
        return _json_err(500, f"도구 실행 오류: {exc}")

    marked = _guard.wrap_tool_output(
        str(out or ""), account=str(account.get("username") or account.get("id")),
        conversation_id=task.get("conversation_id"), task_id=task_id, source=tool_name)

    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0), tool=tool_name,
                       client_id=ctx.get("client_id"), task_id=task_id,
                       datasource_key=str(arguments.get("datasource") or "") or None,
                       schema_name=str(arguments.get("schema_name") or "") or None,
                       rows_returned=str(out or "").count("\n"),
                       bytes_out=len(marked.encode("utf-8")),
                       latency_ms=int((time.perf_counter() - t0) * 1000), outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        # ★ 결과를 반환하지 않는다 — 기록 없는 호출은 상한 우회다(codex P1).
        return _json_err(503, f"원장을 기록할 수 없어 결과를 반환하지 않습니다: {exc}")

    return JSONResponse({"task_id": task_id, "tool": tool_name, "result": marked})


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

async def _json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


def _json_err(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _load_task(conn, task_id: str, account: dict[str, Any]) -> dict[str, Any] | None:
    """task 조회 — **소유 계정 스코프**. 남의 task 로는 어떤 도구도 못 돈다."""
    if not task_id:
        return None
    cur = conn.cursor()
    try:
        cur.execute("SELECT TaskId, ConversationId, ProductId, Question, Status "
                    "FROM WebAiTasks WHERE TaskId = %s AND AccountId = %s LIMIT 1",
                    (task_id, int(account.get("id") or 0)))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return None
    return {"task_id": row[0], "conversation_id": row[1], "product_id": row[2],
            "question": row[3], "status": row[4]}


def _sibling_tasks(conn, account: dict[str, Any], client_id: str | None,
                   *, exclude: str) -> list[dict[str, Any]]:
    """같은 client(=같은 머신 AI 런타임) 의 **다른 계정** task — 교차오염 대조 대상.

    같은 계정의 다른 task 는 대조 대상이 아니다(같은 권한이라 섞여도 유출이 아니다).
    실제 위험은 A·B·C 세션을 한 런타임이 동시에 다룰 때의 계정 간 혼입이다."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT TaskId FROM WebAiTasks WHERE AccountId <> %s AND ClientId = %s "
                    "AND TaskId <> %s ORDER BY CreatedAt DESC LIMIT 20",
                    (int(account.get("id") or 0), client_id or "", exclude))
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()
    return [{"task_id": r[0]} for r in rows]


# L4 판정에서 훑는 계정 수 상한(codex P2 — DB 증폭 방어).
_ASYMMETRY_MAX_ACCOUNTS = 8


def _permission_asymmetry(conn, ctx: dict[str, Any],
                          account: dict[str, Any]) -> dict[str, Any] | None:
    """같은 client 의 **최근 활성 세션들**을 모아 L4 판정에 넘긴다.

    "활성" 은 최근 1시간 내 open 된 task 를 가진 계정으로 근사한다 — 세션 테이블을 따로 두지
    않고도 "지금 이 런타임이 몇 계정을 다루고 있나" 를 충분히 잡는다(정확한 동시성보다
    **권한 격차** 가 판정의 본질이라 근사로 족하다).
    """
    client_id = ctx.get("client_id")
    if not client_id:
        return None
    cur = conn.cursor()
    try:
        # codex P2: 상한 없는 fan-out 은 인증된 요청 1건으로 DB 증폭을 만든다
        # (공유 client 에 계정이 많을수록 심해진다). 상한 안에서만 본다 —
        # 판정의 본질은 "권한 격차가 있는가" 라 표본으로 족하다.
        cur.execute(
            "SELECT DISTINCT AccountId FROM WebAiTasks "
            "WHERE ClientId = %s AND CreatedAt > (NOW() - INTERVAL 1 HOUR) "
            "ORDER BY AccountId LIMIT %s",
            (client_id, _ASYMMETRY_MAX_ACCOUNTS))
        account_ids = [int(r[0]) for r in (cur.fetchall() or [])]
    except Exception:
        return None
    finally:
        cur.close()

    account_ids = sorted(set(account_ids) | {int(account.get("id") or 0)})
    if len(account_ids) < 2:
        return None

    sessions = []
    for aid in account_ids:
        try:
            if aid == int(account.get("id") or 0):
                acct = account
            else:
                rows = app._fetch_account_rows(
                    conn, "a.Id = %s AND a.IsActive = 1 AND a.DeletedAt IS NULL",
                    (aid,), include_password=False, limit_sql="LIMIT 1")
                rows = app._decorate_account_rows(conn, rows)
                acct = rows[0] if rows else None
            if not acct:
                continue
            products = _authz.allowed_products(app, acct, conn)
        except Exception:
            continue
        sessions.append({"account_id": aid,
                         "products": [int(p.get("id") or 0) for p in products]})
    try:
        return _authz.permission_asymmetry(sessions)
    except Exception:
        return None


def _session_notice(account: dict[str, Any]) -> str:
    """세션 규범 — MCP 서버 `instructions` 와 같은 문구를 REST 소비자에게도 준다."""
    who = str(account.get("username") or account.get("id"))
    return (f"This session is bound to account={who}. Data returned here belongs to that "
            f"account only; never use it when answering for another account, and never merge "
            f"results across accounts. 이 세션은 계정 {who} 전용입니다.")


def _safe_record(account: dict[str, Any], ctx: dict[str, Any], **kwargs) -> None:
    """거절·게이트 경로의 원장 기록. 여기서까지 5xx 로 바꾸면 거절이 오류로 뒤집히므로
    삼킨다 — 단 **성공 경로는 절대 삼키지 않는다**(위 record 호출들)."""
    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0),
                       client_id=ctx.get("client_id"), **kwargs)
    except Exception:
        pass
