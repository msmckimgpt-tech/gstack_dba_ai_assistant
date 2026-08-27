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

import asyncio
import json
import logging
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

# P1 (2026-08-14): 자유 SELECT. 구조만으로는 **관계 주장을 데이터로 검증할 수 없다**는 실사용
# 제보로 열었다(FK 0건 스키마에서 뷰 정의·실제 행수·고아행 확인이 전부 막혀 있었다).
#
# 방어는 새로 만들지 않고 내부 경로의 것을 그대로 쓴다 — sqlglot AST 가드(단일 SELECT/CTE ·
# write verb·다중문·lock·INTO·금지스키마 거부) · 제품 스키마 allowlist · 무거운 쿼리 사전 게이트 ·
# per-query 시간 cap. 외부 표면이 **추가로** 지는 것은 둘이다:
#   ① 서버 CSV 경로를 응답에서 제거한다(경로 유출 + 외부 호출자에겐 없는 다운로드 약속).
#   ② 원장에 **실제 행수**를 기록한다(렌더 문자열의 줄 수로 세면 시간당 행 상한이 장식이 된다).
P1_TOOLS = frozenset({"execute_sql"})
EXPOSED_TOOLS = P0_TOOLS | P1_TOOLS

# 운영자 스위치. 데이터 추출 축이라 구조 조회와 별개로 끌 수 있어야 한다.
_SQL_ENABLED_KEY = "AGENT_EXT_TOOL_SQL_ENABLED"
_SQL_MAX_ROWS_KEY = "AGENT_EXT_TOOL_SQL_MAX_ROWS"

# AC-7 — 보존하는 답변 본문의 문자 상한. `MEDIUMTEXT`(16MB)에 한참 못 미치는 값으로 잡는다:
# 상한의 목적은 저장 용량이 아니라 **한 task 가 원장을 지배하지 못하게** 하는 것이다.
# 실측 답변은 6~8KB 라 여유가 크다. 초과분은 조용히 잘리지 않고 `AnswerTruncated` 로 남는다.
_ANSWER_MAX_CHARS = 262_144


def _sql_max_rows() -> int:
    """건당 반환 행수 상한. 0 이하 = 무제한.

    시간당 상한은 **실행 전 누적 확인**이라 원자적이지 않다 — 상한 직전의 대형 쿼리 한 번,
    또는 같은 잔여량을 본 동시 요청들이 모두 통과한다(codex P1). 이 값이 그 초과분을
    유계로 만든다. hard cap 이라고 부르지 않는다 — **초과분이 유계**라고 부른다.
    """
    try:
        from shared import runtime_settings as _rs
        return int(_rs.get_int(_SQL_MAX_ROWS_KEY))
    except Exception:
        return 10000


def _sql_enabled() -> bool:
    """★ `get_int(key)` 는 **인자를 하나만** 받는다. 기본값까지 넘기면 TypeError 가 나고
    except 가 True 를 돌려줘 **스위치가 항상 켜진 상태**가 된다(codex 가 실제 호출로 재현).
    문자열 존재만 보던 테스트는 이걸 통과시켰다 — 이제 실제로 호출해 본다."""
    try:
        from shared import runtime_settings as _rs
        return int(_rs.get_int(_SQL_ENABLED_KEY)) > 0
    except Exception:
        # 설정을 못 읽는 상태에서 데이터 추출을 여는 것보다 닫는 편이 안전하다(fail-closed).
        return False


def _sanitize_sql_output(text: str, csv_paths: list[str]) -> str:
    """서버 파일 경로와 '다운로드 버튼' 안내를 걷어낸다.

    내부 경로는 결과 CSV 를 저장하고 web UI 가 다운로드로 준다. 외부 호출자에겐 그 UI 도,
    그 파일을 읽을 방법도 없다 — 경로만 새고 지키지 못할 약속이 남는다.
    """
    out = str(text or "")
    for path in csv_paths or []:
        out = out.replace(f"CSV 저장: {path}\n", "").replace(f"CSV 저장: {path}", "")
    marker = "(저장된 CSV 는 사용자에게 다운로드 버튼으로 자동 제공됩니다"
    idx = out.find(marker)
    if idx >= 0:
        end = out.find(")", idx)
        out = (out[:idx] + out[end + 1:]) if end >= 0 else out[:idx]
    out = out.replace("CSV 는 사용자 다운로드 전용이라 당신은 읽을 수 없습니다.",
                      "이 표면에는 CSV 다운로드가 없습니다 — 필요한 범위를 SQL 로 좁혀 다시 조회하세요.")
    return out.strip()


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

    # ADR-003 — 이 task 가 어느 datasource 를 보는지 **여는 시점에** 새긴다. 제품의 바인딩은
    # 교체될 수 있고 실제로 2026-08-14 에 교체됐다(메모리 DB MySQL → MSSQL). 그때 이전 답변이
    # 어느 DB 를 본 것인지 알 방법이 기록 밖 문맥밖에 없어 혼동이 생겼다. 해석 실패는 NULL 로
    # 두고 task 개설 자체를 막지 않는다 — 이 값은 감사 보조지 접근 통제가 아니다(통제는 authz).
    datasource_key = None
    try:
        import agent_core as _core
        _labels = _authz.allowed_datasource_labels(_core, conn, int(product.get("id") or 0))
        if _labels:
            datasource_key = ",".join(_labels)[:128]
    except Exception:
        datasource_key = None

    task_id = "t_" + secrets.token_urlsafe(12)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebAiTasks (TaskId, AccountId, ClientId, ProductId, Question, "
            "Status, InjectionVerdict, DatasourceKey) VALUES (%s,%s,%s,%s,%s,'open',%s,%s)",
            (task_id, int(account.get("id") or 0), ctx.get("client_id"),
             int(product.get("id") or 0), question[:4000], verdict["verdict"], datasource_key))
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
    notes: list[str] = []
    # ⚠ 이 블록은 두 가지 이유로 **항상 비어 있었다**(라이브 제보 — "(관련 요약 없음)" 만 반환).
    #   ① `load_cluster_summary_context` 는 **조립된 문자열**을 돌려주는데 rows 로 착각해
    #      `_cc.render(...)` 를 다시 불렀다 → 예외 → 아래 bare except 가 삼켰다.
    #   ② scope 를 안 넘기면 `get_active_datasource()` 로 도출하는데, API 요청 컨텍스트에는
    #      활성 datasource 가 없어 후보가 **빈 목록**이 된다 → 즉시 "" 반환.
    #   그래서 task 의 제품에 바인딩된 datasource 라벨을 **명시적으로** 넘긴다.
    scopes: list[str] = []
    try:
        import agent_core as _core   # 지연 import — 라우터 import 시점 순환 회피(다른 핸들러와 동형)
        scopes = _authz.datasource_scope_keys(_core, conn, int(task.get("product_id") or 0))
    except Exception:
        scopes = []
    try:
        from modules import cluster_context as _cc
        if _cc.enabled():
            # ⚠ 이 층은 **질문에 테이블 이름이 등장할 때만** 매칭된다(내부 대화 경로는 매 턴
            #   호출하므로 자연히 이름이 섞인다). 외부 AI 는 탐색 *전에* 한 번 부르므로 그
            #   질문엔 이름이 없다 — 그래서 `focus` 로 **탐색 후 다시** 부를 수 있게 한다.
            focus = str(body.get("focus") or "").strip()
            question = focus or (task.get("question") or "")
            for scope in (scopes or [None]):
                rendered = _cc.load_cluster_summary_context(question, scope_key=scope, conn=None)
                if rendered:
                    sections.append(rendered)
                    break
    except Exception as exc:   # grounding 부재는 degrade — 도구 자체를 막지 않는다
        # 다만 **왜** 비었는지는 남긴다. 조용히 삼키는 바람에 이 결함이 오래 보이지 않았다.
        notes.append(f"grounding 로드 실패: {type(exc).__name__}")
    if not sections and not notes:
        notes.append(
            "질문에 테이블 이름이 없어 매칭된 묶음이 없습니다 — 구조 조회로 테이블을 찾은 뒤 "
            "`focus` 에 그 이름들을 넣어 다시 부르면 해당 묶음의 요약을 받습니다"
            if scopes else "이 task 의 제품에 바인딩된 datasource 를 찾지 못했습니다")

    payload = "\n\n".join(s for s in sections if s)
    if not payload:
        # 빈 번들을 "(관련 요약 없음)" 한 줄로만 돌려주면 호출자는 **이게 정상인지 고장인지**
        # 구분할 수 없다(라이브에서 실제로 그 상태였다). 사유와 다음 행동을 함께 준다.
        payload = ("(grounding 번들 없음 — " + " / ".join(notes) + ")\n"
                   "구조 조회 도구(list_schemas → describe_schema → describe_table)로 "
                   "직접 탐색하세요. 이 경우 도메인 맥락 없이 구조만 보게 되므로, 답변에 "
                   "그 한계를 밝히세요.")
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

    # AC-7 — 답변 본문을 **저장 시점에 각인해서** 보존한다. 2026-08-14 까지 이 자리는 Status 만
    # 갱신했고 답변은 원장에 바이트 수로만 남았다(요구 미충족을 정본이 `[x]` 로 주장했다).
    #
    # 각인 방향 주의: 나가는 도구 결과는 `wrap_tool_output` 이지만 여기는 **들어오는** 외부
    # 텍스트라 `wrap_external_answer` 다. 저장본은 이후 우리 컨텍스트로 되돌아올 수 있다.
    answer_verdict = _guard.classify_injection(answer)
    if answer_verdict["verdict"] == "reject":
        # codex REV-0026 P2 — 고신뢰 인젝션은 `open_task` 와 **같은 계약**으로 거절한다(AC-8).
        # 처음엔 판정만 컬럼에 남기고 그대로 저장했는데, 그러면 (a) 400 거절 계약이 답변 축에서만
        # 조용히 깨지고 (b) 운영자가 읽는 영속 기록에 공격 페이로드가 '정상 답변' 으로 앉는다.
        #
        # 단 **판정은 task 행에 남긴다**(codex 2차 P2): 원장에만 남기면 그 원장이 다른 저장소라
        # 콘솔에서 task 를 볼 때 "거절된 제출 시도가 있었다" 는 사실이 보이지 않는다. 페이로드는
        # 보존하지 않고 판정만 남기는 것이 AC-7(보존)과 AC-8(거절)을 동시에 만족하는 배치다.
        _mark_answer_verdict(conn, task_id, "reject")
        _safe_record(account, ctx, tool="submit_answer", outcome="denied", task_id=task_id,
                     detail=f"injection:{','.join(answer_verdict['matched'])[:180]}")
        return _json_err(400, "답변에 지시 전복 시도로 판정된 문구가 있어 거절했습니다. "
                              "해당 문구를 제거하고 다시 제출하세요.")
    stored_body = answer_verdict["text"]
    truncated = 0
    if len(stored_body) > _ANSWER_MAX_CHARS:
        # 조용히 자르지 않는다 — 잘렸다는 사실 자체가 기록의 일부다.
        stored_body = stored_body[:_ANSWER_MAX_CHARS]
        truncated = 1
    stored = _guard.wrap_external_answer(
        stored_body, account=str(account.get("username") or ""), task_id=task_id,
        datasource_key=task.get("datasource_key"))

    # 대화 접근 권한 **재검증** — 아래에서 이 대화에 assistant 메시지를 **쓴다**. 질문 시점의
    # 권한으로 지금의 대화에 글을 남기지 않도록, 쓰기 직전에 다시 확인한다(codex 재리뷰 P1).
    denied = _conversation_access_denied(conn, account, task.get("conversation_id"))
    if denied is not None:
        _safe_record(account, ctx, tool="submit_answer", outcome="denied",
                     detail="conversation_access_revoked", task_id=task_id)
        return denied

    cur = conn.cursor()
    try:
        # `SubmittedAt IS NULL` 가드 (codex 2차 P2) — 무조건 UPDATE 면 타임아웃 후 재시도나
        # 동시 제출이 **이미 보존된 답변·판정·근거선언을 덮어쓴다.** 최종 답변은 감사 기록이므로
        # 한 번 확정되면 파괴할 수 없어야 한다. 조건을 SQL 에 둬야 TOCTOU 없이 원자적이다
        # (`_load_task` 로 미리 읽고 분기하면 두 요청이 같은 'open' 을 보고 둘 다 통과한다).
        #
        # feature-0043 (codex 리뷰 P2-1): 웹 브리지 task 는 **점유자만** 제출할 수 있다.
        # 이 조건이 없으면 같은 계정의 다른 세션이 `claim_request` 를 건너뛰고 먼저 제출할 수
        # 있어, 원자적 claim 이 "처리 소유권" 으로 집행되지 않는다(점유는 목록에서만 사라지고
        # 실제로는 아무 것도 막지 못하는 장식이 된다). 외부 AI 가 스스로 연 task
        # (`Origin='external'`)에는 claim 개념이 없으므로 종전대로 통과시킨다.
        cur.execute(
            "UPDATE WebAiTasks SET Status = 'submitted', SubmittedAt = NOW(), Answer = %s, "
            "AnswerBytes = %s, AnswerVerdict = %s, AnswerTruncated = %s, SourceTasks = %s "
            # `ClaimedClient` 까지 비교하는 이유(codex 재리뷰 P2): 계정 조건만으로는 같은
            # 계정의 **다른 세션**이 claim 을 건너뛰고 제출할 수 있다. 컬럼 추가 이전에
            # 점유된 행은 NULL 이므로 호환을 위해 통과시킨다.
            "WHERE TaskId = %s AND SubmittedAt IS NULL "
            "AND (Origin <> 'web' OR (ClaimedBy = %s "
            "     AND (ClaimedClient IS NULL OR ClaimedClient = %s)))",
            (stored, len(answer.encode("utf-8")), answer_verdict["verdict"], truncated,
             ",".join(str(d) for d in declared)[:4000], task_id,
             int(account.get("id") or 0), ctx.get("client_id")))
        affected = cur.rowcount
        conn.commit()
        if not affected:
            # 두 사유가 같은 rowcount 0 으로 오므로 구분해서 안내한다 — 러너의 다음 행동이
            # 다르다(이미 제출=건너뛰기 / 미점유=claim_request 먼저).
            cur.execute(
                "SELECT SubmittedAt, Origin, ClaimedBy FROM WebAiTasks WHERE TaskId=%s",
                (task_id,))
            _r = cur.fetchone()
            if _r is not None and _r[0] is None and str(_r[1] or "") == "web":
                _safe_record(account, ctx, tool="submit_answer", outcome="denied",
                             task_id=task_id, detail="not_claimed")
                return _json_err(409, "이 질문을 먼저 claim_request 로 가져와야 제출할 수 "
                                      "있습니다(점유자만 답변을 확정합니다).")
            # 이미 제출된 task. 원 기록을 보존한 채 거절한다.
            _safe_record(account, ctx, tool="submit_answer", outcome="denied", task_id=task_id,
                         detail="already_submitted")
            return _json_err(409, "이미 답변이 제출된 task 입니다. 최종 답변은 한 번만 "
                                  "확정되며 덮어쓸 수 없습니다.")
    except Exception as exc:
        # fail-closed — 원장의 `기록 실패 = 거절` 과 동형. 저장이 안 됐는데 recorded:true 를
        # 돌려주면 "보존되고 있다" 는 주장과 실제가 갈린다(이 feature 의 반복 결함).
        # 컬럼 미추가(부트스트랩 ALTER 실패)도 여기로 떨어진다.
        try:
            conn.rollback()
        except Exception:
            pass
        return _json_err(503, f"답변을 보존할 수 없어 제출을 중단했습니다: {exc}")
    finally:
        cur.close()

    # feature-0043 — 웹 대화에서 온 질문이면 답변을 그 대화에 되돌려 붙인다.
    # 이게 없으면 답변은 `WebAiTasks` 에만 남고 사용자가 물어본 화면에는 영원히 나타나지 않는다.
    #
    # **원장보다 먼저** 하는 이유(codex 재리뷰 P1): task 는 이미 `submitted` 로 확정됐고
    # 재제출은 409 다. 원장 실패로 여기서 503 을 내면 답변은 확정됐는데 화면엔 없고 자동
    # 복구 경로도 없는 상태가 굳는다. 전달을 앞에 두면 원장 장애가 사용자 대면 결과를
    # 훼손하지 않는다(원장은 그 뒤에도 여전히 fail-closed 로 집행된다).
    delivered = _deliver_web_bridge_answer(conn, task_id, account, answer)

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
                         "delivered_to_conversation": delivered,
                         "cross_session_findings": findings})


def _replace_bridge_placeholder(conn, conversation_id: str, task_id: str,
                                answer: str, meta: dict[str, Any]) -> int:
    """대기 안내 말풍선을 **답변으로 덮어쓴다**. 성공 시 message id, 없으면 0.

    왜 append 가 아니라 덮어쓰기인가: 기존 경로의 UX 는 "대기 말풍선 하나가 답변으로 바뀌는"
    모양이다. 새로 붙이면 안내와 답변이 **둘 다** 남아, 대화를 다시 열 때마다 "처리 중입니다"
    가 답변 위에 영구히 붙어 있다.

    placeholder 를 못 찾으면 0 을 돌려 호출측이 append 로 폴백한다 — 이 기능 이전에 적재된
    task(안내 말풍선이 없는 task)도 답변을 받아야 한다.
    """
    if not conversation_id or not task_id:
        return 0
    try:
        if not app._runtime_backend_is_pg():
            return 0
        from shared.db import _pg_connect

        pg = _pg_connect()
        try:
            with pg.cursor() as cur:
                cur.execute(
                    # 이 task 의 placeholder 만 고른다 — 같은 대화의 다른 질문·과거 답변을
                    # 건드리면 남의 말풍선을 덮어쓴다.
                    "UPDATE agent_runtime.messages "
                    "SET content = %s, meta_json = %s::jsonb "
                    "WHERE conversation_id = %s AND role = 'assistant' "
                    "  AND (meta_json -> 'bridge' ->> 'task_id') = %s "
                    "  AND (meta_json -> 'bridge' ->> 'placeholder') = 'true' "
                    "RETURNING id",
                    (answer, json.dumps(meta, ensure_ascii=False), str(conversation_id),
                     str(task_id)))
                row = cur.fetchone()
            pg.commit()
            return int(row[0]) if row else 0
        finally:
            pg.close()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[bridge] 대기 말풍선 덮어쓰기 실패 task=%s — append 로 폴백: %r", task_id, exc)
        return 0


def _deliver_web_bridge_answer(conn, task_id: str, account: dict[str, Any], answer: str) -> bool:
    """`Origin='web'` task 의 답변을 원 대화에 assistant 메시지로 저장한다.

    **각인된 본문이 아니라 원문을 저장한다.** `WebAiTasks.Answer` 에는 각인본이 남아 지연
    인젝션 방어가 유지되고(우리 LLM 컨텍스트로 되돌아올 수 있는 경로), 화면에는 사람이 읽을
    본문이 필요하다 — 두 소비처의 요구가 달라 저장본을 나눈다.

    실패는 **삼키지 않고 로그로 올리되 제출 자체는 성공으로 둔다**: 답변은 이미 `WebAiTasks`
    에 확정 저장됐고(그 단계는 fail-closed), 여기서 5xx 를 돌려주면 러너가 재제출을 시도해
    409 에 부딪힌다 — 이미 보존된 답변을 잃지 않으면서 전달 실패만 드러내는 쪽을 택한다.
    """
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT ConversationId, Origin, ProductId, ProductMode "
                "FROM WebAiTasks WHERE TaskId=%s", (task_id,))
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return False
        conversation_id, origin = row[0], str(row[1] or "")
        if origin != "web" or not conversation_id:
            return False

        # 지연 import — 라우터 import 시점 순환 회피(다른 핸들러의 `import agent_core` 와 동형).
        from modules.memory import save_memory_message as _save_msg

        # 답변 말풍선의 **제품 귀속 각인**(msg-speaker-attribution). 기존 경로가 답변마다 굳히는
        # 값이고, 빠지면 FE 가 컴포저의 *현재* 제품 칩으로 폴백해 그린다 — 사용자가 제품을 바꾸는
        # 순간 과거 답변의 발화자까지 소급 변경된다. 각인은 답변 시점에 확정되는 사실이다.
        # 조회 실패는 fail-open(각인만 생략) — 각인이 답변 저장을 막게 두지 않는다.
        _meta: dict[str, Any] = {"bridge": {"task_id": task_id, "origin": "web"}}
        try:
            import agent_core as _core

            _meta.update(_core._answer_product_attribution(
                conn, row[2], str(row[3] or "pinned")))
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "[bridge] 제품 귀속 각인 실패 task=%s — 각인 없이 저장한다: %r", task_id, exc)

        # placeholder 각인은 지운다 — 남겨두면 이 답변이 다음 전달의 덮어쓰기 대상이 된다.
        _meta["bridge"]["placeholder"] = False
        # 대기 안내 자리에 덮어쓴다. 없으면(구 task) 종전대로 새 말풍선으로 붙인다.
        message_id = _replace_bridge_placeholder(
            conn, str(conversation_id), task_id, answer, _meta)
        if not message_id:
            message_id = _save_msg(conn, str(conversation_id), "assistant", answer, meta=_meta)
        conn.commit()
        # ⚠ `save_memory_message` 는 PG 쓰기 실패를 내부에서 삼키고 **0 을 반환**한다
        #   (codex 재리뷰 P1). 반환값을 안 보면 저장이 실패해도 `delivered=true` 를 돌려주고,
        #   상태 API 는 "답변 도착" 이라 말하는데 화면엔 아무것도 없는 상태가 굳는다.
        if not message_id:
            logging.getLogger(__name__).error(
                "[bridge] 대화 저장이 0 을 반환했다 task=%s conv=%s — 전달 실패로 기록한다",
                task_id, conversation_id)
            return False

        # 회수 store(`agent_runtime.core_messages`)에도 답변을 남긴다 — 표시 store 만 쓰면 대화
        # 복제·분기본에서 브리지 답변만 사라진다. 실패는 흡수(표시본은 이미 확정).
        try:
            import agent_core as _core

            _core._save_message(conn, str(conversation_id), "assistant", content=answer)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "[bridge] core store 답변 기록 실패 task=%s conv=%s — 표시본만 남는다: %r",
                task_id, conversation_id, exc)

        # 전달 성공을 task 에 새긴다. `Status='submitted'` 와 분리해야 "제출됐지만 화면에는
        # 없다" 를 구분해 재전달·진단할 수 있다.
        cur = conn.cursor()
        try:
            cur.execute("UPDATE WebAiTasks SET Delivered=1 WHERE TaskId=%s", (task_id,))
            conn.commit()
        finally:
            cur.close()
        return True
    except Exception as exc:
        logging.getLogger(__name__).error(
            "[bridge] 답변을 대화에 전달하지 못했다 task=%s — 답변은 WebAiTasks 에 보존됨: %r",
            task_id, exc)
        return False


# ── 구조 조회 6종 ─────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# feature-0043 (external-llm-bridge) — 웹 대화 pull 브리지
#
# 서버가 보유 계정으로 답변을 만들지 않게 되면서(shared/llm_gate), 웹 대화창의 질문은
# `WebAiTasks` 의 **대기 작업**(`Origin='web'`)이 된다. 사용자의 개인 머신 AI 런타임이
# 아래 두 도구로 그것을 가져가 자기 계정 LLM 으로 답한 뒤 기존 `submit_answer` 로 제출한다.
#
# **왜 push(MCP sampling)가 아니라 pull 인가**: `sampling/createMessage` 는 프로토콜
# 2026-07-28 에서 폐기됐고(SEP-2577 — "New implementations SHOULD NOT adopt it"),
# Claude Code 가 미지원이다(anthropics/claude-code#1785). 표준 tools 로 당겨오면
# 클라이언트 호환성 문제도, 폐기 기능 의존도 없다.
#
# **격리**: 웹 질문은 그것을 **연 계정 본인**만 가져갈 수 있다(사용자 결정 2026-08-26).
# 아래 쿼리의 `AccountId=%s` 는 편의가 아니라 경계다 — 빼면 남의 질문과 그 답변이
# 대리자 AI 의 컨텍스트로 들어간다.
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/api/ai/tools/list_open_requests")
async def list_open_requests(request: Request, ctx=Depends(require_ai_token),
                             conn=Depends(app.get_conn)) -> JSONResponse:
    """내 계정의 **웹 대화 대기 질문** 목록 (아직 아무도 집지 않은 것).

    아직 점유되지 않은 것만 돌려준다 — 이미 집힌 작업을 목록에 남기면 러너가 매 주기
    같은 것을 다시 집으려다 409 를 받는다.
    """
    body = await _json(request)
    account = ctx["account"]
    account_id = int(account.get("id") or 0)
    try:
        limit = int(body.get("limit") or 20)
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(50, limit))

    t0 = time.perf_counter()
    try:
        _ledger.check_limits(_pg(), account_id=account_id, client_id=ctx.get("client_id"))
    except _ledger.RateLimited as exc:
        _safe_record(account, ctx, tool="list_open_requests", outcome="gated", detail=exc.limit)
        return JSONResponse({"error": exc.message}, status_code=429,
                            headers={"Retry-After": str(exc.retry_after)})
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"상한을 확인할 수 없어 요청을 중단했습니다: {exc}")

    rows: list[dict[str, Any]] = []
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TaskId, Question, CreatedAt FROM WebAiTasks "
            "WHERE AccountId=%s AND Origin='web' AND Status='open' AND " + _CLAIMABLE_SQL +
            " ORDER BY CreatedAt ASC LIMIT %s",
            (account_id, limit))
        for r in cur.fetchall() or []:
            rows.append({
                "task_id": str(r[0]),
                "question": str(r[1] or ""),
                "asked_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2] or ""),
            })
    finally:
        cur.close()

    # 질문 본문은 우리 사용자가 쓴 텍스트지만 **외부 AI 의 컨텍스트로 나가는 데이터**이므로
    # 나가는 다른 도구 결과와 같은 규약으로 각인한다(L2). 각인을 여기서만 빼면 그 구획이
    # 뚫리는 자리가 된다.
    listing = "\n\n".join(
        f"[{i + 1}] task_id={r['task_id']}\n{r['question']}" for i, r in enumerate(rows)
    ) or "(대기 중인 웹 질문 없음)"
    marked = _guard.wrap_tool_output(
        listing,
        account=str(account.get("username") or account.get("id")),
        conversation_id=None, task_id=None, source="open_requests")

    try:
        # ⚠ 인자명은 `rows_returned` 다(`rows` 아님). 잘못 쓰면 조회가 끝난 **뒤** 원장 기록
        # 단계에서 TypeError 가 나 항상 500 이 된다 — 대기 질문이 있든 없든 100% 실패한다.
        # 그리고 `claim_request` 는 이 도구가 주는 task_id 를 요구하므로, **웹 브리지 축 전체**가
        # 끊긴다(라이브 제보 2026-08-27). 도구가 등록됐는지만 보는 테스트로는 잡히지 않았다.
        _ledger.record(_pg(), account_id=account_id, tool="list_open_requests",
                       client_id=ctx.get("client_id"), rows_returned=len(rows),
                       bytes_out=len(marked.encode("utf-8")),
                       latency_ms=int((time.perf_counter() - t0) * 1000), outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    return JSONResponse({
        "count": len(rows),
        "task_ids": [r["task_id"] for r in rows],
        "requests": marked,
    })


#: 대기 응답을 붙들어 두는 **서버 고정** 상한(초).
#:
#: 클라이언트가 정하지 않는다 — 간격이 knob 이 되는 순간 사람마다 다른 지연이 생기고, 그게
#: 곧 "환경 차이" 다(사용자 요구 2026-08-27: 주기적 폴링 금지 · 환경 차이 금지).
#: 55초로 잡은 이유: 흔한 프록시·클라이언트 기본 타임아웃(60s)보다 작아야 우리가 먼저 끝내고
#: 정상 응답을 돌려줄 수 있다. 더 길면 중간 단이 먼저 끊어 "오류" 로 보인다.
_WAIT_MAX_HOLD_SEC = 55.0

#: 서버 **내부** 확인 간격. 클라이언트에 노출되지 않으므로 환경 차이를 만들지 않는다.
#: (PG LISTEN/NOTIFY 로 바꾸면 이 값 자체가 사라진다 — 지금은 의존성을 늘리지 않는 쪽을 택했다.)
_WAIT_TICK_SEC = 0.5


@router.post("/api/ai/tools/wait_for_request")
async def wait_for_request(request: Request, ctx=Depends(require_ai_token),
                           conn=Depends(app.get_conn)) -> JSONResponse:
    """대기 질문이 **생길 때까지 응답을 보류**한다. 생기면 그 즉시 돌려준다.

    ## 왜 이 도구인가

    MCP 는 클라이언트→서버 단방향이라 서버가 AI 를 깨울 수 없다(`sampling` 은 폐기됐고
    Claude Code 미지원). 그렇다고 AI 가 N 초마다 묻게 하면 두 가지가 나빠진다 — 사용자가
    보낸 질문이 최대 N 초 늦게 인지되고, 그 N 이 사람마다 달라 **환경 차이**가 된다.

    블로킹 대기는 둘 다 없앤다: 호출은 **한 번**이고, 응답은 **질문이 들어온 그 순간** 온다.
    상한은 서버가 정하므로 모든 클라이언트가 동일하게 동작한다.

    ## 계약

    - 이미 대기 질문이 있으면 **즉시** 반환한다(기다리지 않는다).
    - 없으면 최대 `_WAIT_MAX_HOLD_SEC` 까지 보류한다. 그동안 생기면 즉시 반환.
    - 시간이 다 되면 `timed_out: true` 로 정상(200) 반환한다 — **오류가 아니다.**
      호출측은 곧바로 다시 대기에 들어가면 된다(그것이 폴링이 아닌 이유: 간격이 없다).
    - 클라이언트가 연결을 끊으면 즉시 그만둔다(끊긴 응답을 위해 DB 를 두드리지 않는다).

    반환은 `list_open_requests` 와 **같은 모양**이다 — 호출측이 분기 없이 이어서 처리한다.
    """
    account = ctx["account"]
    account_id = int(account.get("id") or 0)

    # 상한은 **대기 시작 전에 한 번만** 본다. 보류 중 매 tick 마다 검사하면 상한 조회가
    # 초당 두 번씩 원장을 두드린다 — 대기는 그 자체로 비용이 아니어야 한다.
    try:
        _ledger.check_limits(_pg(), account_id=account_id, client_id=ctx.get("client_id"))
    except _ledger.RateLimited as exc:
        _safe_record(account, ctx, tool="wait_for_request", outcome="gated", detail=exc.limit)
        return JSONResponse({"error": exc.message}, status_code=429,
                            headers={"Retry-After": str(exc.retry_after)})
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"상한을 확인할 수 없어 요청을 중단했습니다: {exc}")

    t0 = time.perf_counter()
    deadline = t0 + _WAIT_MAX_HOLD_SEC
    found: list[tuple] = []
    while True:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT TaskId, Question, CreatedAt FROM WebAiTasks "
                "WHERE AccountId=%s AND Origin='web' AND Status='open' AND " + _CLAIMABLE_SQL +
                " ORDER BY CreatedAt ASC LIMIT 20", (account_id,))
            found = list(cur.fetchall() or [])
        finally:
            cur.close()
        # ⚠ 커밋(또는 롤백)이 없으면 이 커넥션의 트랜잭션 스냅샷이 고정돼 **새로 들어온 행이
        #   영원히 안 보인다**(REPEATABLE READ). 대기 루프에서 가장 빠지기 쉬운 함정이다.
        try:
            conn.commit()
        except Exception:
            pass
        if found or time.perf_counter() >= deadline:
            break
        if await request.is_disconnected():
            # 이미 끊긴 클라이언트를 위해 계속 두드리지 않는다.
            return JSONResponse({"count": 0, "task_ids": [], "requests": "",
                                 "timed_out": False, "disconnected": True})
        await asyncio.sleep(_WAIT_TICK_SEC)

    waited_ms = int((time.perf_counter() - t0) * 1000)
    if not found:
        # 빈 대기도 원장에 남긴다 — 남기지 않으면 "AI 가 붙어 있었는가" 를 사후에 알 수 없다.
        _safe_record(account, ctx, tool="wait_for_request", outcome="ok",
                     latency_ms=waited_ms, rows_returned=0)
        return JSONResponse({"count": 0, "task_ids": [], "requests": "",
                             "timed_out": True, "waited_ms": waited_ms,
                             "next": "곧바로 다시 wait_for_request 를 호출하면 된다(간격 불필요)."})

    lines = [f"- task_id={r[0]}  ({r[2]})\n  {str(r[1] or '')[:500]}" for r in found]
    marked = _guard.wrap_tool_output(
        "\n".join(lines),
        account=str(account.get("username") or account.get("id")),
        conversation_id=None, task_id=None, source="open_requests")
    try:
        _ledger.record(_pg(), account_id=account_id, tool="wait_for_request",
                       client_id=ctx.get("client_id"), rows_returned=len(found),
                       bytes_out=len(marked.encode("utf-8")),
                       latency_ms=waited_ms, outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    return JSONResponse({
        "count": len(found), "task_ids": [r[0] for r in found], "requests": marked,
        "timed_out": False, "waited_ms": waited_ms,
        "next": "claim_request 로 점유한 뒤 처리하세요.",
    })


@router.post("/api/ai/tools/claim_request")
async def claim_request(request: Request, ctx=Depends(require_ai_token),
                        conn=Depends(app.get_conn)) -> JSONResponse:
    """대기 질문 1건을 **원자적으로 점유**하고 전문을 받는다.

    점유는 `UPDATE ... WHERE ClaimedBy IS NULL` 한 문장 안에서 일어난다 — 선조회 후 UPDATE 는
    두 러너가 같은 작업을 동시에 집는 TOCTOU 창을 만든다(0041 의 `submit_answer` 확정 불변과 동형).
    """
    body = await _json(request)
    account = ctx["account"]
    account_id = int(account.get("id") or 0)
    task_id = str(body.get("task_id") or "").strip()
    if not task_id:
        return _json_err(400, "task_id 가 필요합니다.")

    t0 = time.perf_counter()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE WebAiTasks SET ClaimedBy=%s, ClaimedAt=NOW(), ClaimedClient=%s "
            "WHERE TaskId=%s AND AccountId=%s AND Origin='web' AND Status='open' "
            "AND " + _CLAIMABLE_SQL,
            (account_id, ctx.get("client_id"), task_id, account_id))
        claimed = int(cur.rowcount or 0)
        conn.commit()
        if claimed != 1:
            # 왜 실패했는지 구분한다 — 남의 것/없는 것(404)과 이미 집힌 것(409)은 러너의
            # 다음 행동이 다르다(전자는 목록 재조회, 후자는 그냥 건너뛰기).
            cur.execute(
                "SELECT ClaimedBy FROM WebAiTasks WHERE TaskId=%s AND AccountId=%s",
                (task_id, account_id))
            row = cur.fetchone()
            if row is None:
                _safe_record(account, ctx, tool="claim_request", outcome="denied",
                             detail="not_found_or_foreign", task_id=task_id)
                return _json_err(404, "대기 중인 질문을 찾을 수 없습니다.")
            _safe_record(account, ctx, tool="claim_request", outcome="denied",
                         detail="already_claimed", task_id=task_id)
            return _json_err(409, f"이미 다른 세션이 가져간 질문입니다"
                                  f"(점유는 {_BRIDGE_CLAIM_LEASE_MIN}분 뒤 자동 해제됩니다).")

        cur.execute(
            "SELECT Question, ConversationId, ProductId, CreatedAt, AttachmentIds "
            "FROM WebAiTasks WHERE TaskId=%s AND AccountId=%s", (task_id, account_id))
        row = cur.fetchone() or ("", None, None, None, None)
    finally:
        cur.close()

    question = str(row[0] or "")
    conversation_id = row[1]

    # 권한 **재검증** — 질문을 던진 시점과 지금 사이에 그룹 퇴출·권한 회수가 있었을 수 있다.
    # 아래에서 이 대화의 **최신** 문맥을 읽으므로, 검증 없이 진행하면 질문 당시의 권한으로
    # 지금의 대화를 읽는 창이 열린다(codex 재리뷰 P1). 점유는 되돌린다 — 못 읽을 작업을
    # 붙들고 있으면 lease 만료까지 대기열에서도 사라진다.
    denied = _conversation_access_denied(conn, account, conversation_id)
    if denied is not None:
        _release_claim(conn, task_id, account_id)
        _safe_record(account, ctx, tool="claim_request", outcome="denied",
                     detail="conversation_access_revoked", task_id=task_id)
        return denied

    marked = _guard.wrap_tool_output(
        f"{_guard.session_canary(task_id)}\n{question}",
        account=str(account.get("username") or account.get("id")),
        conversation_id=conversation_id, task_id=task_id, source="web_request")

    # 이전 대화 문맥 — 후속 질문("그럼 그건?")은 앞 turn 없이는 해석 불가다(codex 리뷰 P1-4).
    # 방금 저장한 사용자 질문 자신은 제외한다(중복).
    history = _recent_conversation_context(conn, conversation_id, exclude_text=question)
    marked_history = ""
    if history:
        marked_history = _guard.wrap_tool_output(
            history,
            account=str(account.get("username") or account.get("id")),
            conversation_id=conversation_id, task_id=task_id, source="conversation_history")

    try:
        _ledger.record(_pg(), account_id=account_id, tool="claim_request",
                       client_id=ctx.get("client_id"), task_id=task_id,
                       bytes_out=len((marked + marked_history).encode("utf-8")),
                       latency_ms=int((time.perf_counter() - t0) * 1000), outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        # 점유는 이미 커밋됐다. 여기서 그냥 503 을 돌려주면 `ClaimedBy` 가 박힌 채 목록에서
        # 사라져 **일시적인 원장 장애 한 번이 질문을 영구 고착**시킨다(codex 리뷰 P1-5).
        # 점유를 되돌려 다음 폴링에서 다시 보이게 한다.
        _release_claim(conn, task_id, account_id)
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다(점유 해제됨): {exc}")

    # 첨부 목록 — **있다는 사실 자체**를 알려야 한다. 종전에는 첨부가 딸린 질문도 본문만
    # 전달돼, 개인 머신 AI 가 "첨부가 없다" 고 전제하고 답했다(웹 대화 사용감과 어긋남).
    attachments = _task_attachment_list(conn, row[4], conversation_id)
    return JSONResponse({
        "task_id": task_id,
        "question": marked,
        "conversation_context": marked_history,
        "product_id": int(row[2]) if row[2] is not None else None,
        "asked_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3] or ""),
        "attachments": attachments,
        "next": ("조사 후 submit_answer 로 제출하세요. source_tasks 에 근거로 쓴 task_id 를 "
                 "선언합니다." + (
                     f" 이 질문에는 첨부 {len(attachments)}건이 있습니다 — "
                     f"read_task_attachment(task_id, attachment_id) 로 본문을 읽고 나서 답하세요."
                     if attachments else "")),
    })


def _task_attachment_ids(raw: Any) -> list[int]:
    """`WebAiTasks.AttachmentIds`(CSV) → id 목록. 값이 이 task 의 **권한 경계**다."""
    out: list[int] = []
    for tok in str(raw or "").split(","):
        tok = tok.strip()
        if not tok.isdigit():
            continue
        val = int(tok)
        if val > 0 and val not in out:
            out.append(val)
    return out


def _task_attachment_list(conn, raw_ids: Any, conversation_id: Any) -> list[dict[str, Any]]:
    """이 task 에 딸린 첨부의 목록(본문 아님 — 존재·이름·종류만).

    `ConversationId` 를 술어에 함께 건다: 저장된 id 가 어떤 이유로 오염돼도 **다른 대화의
    첨부는 나오지 않는다**(내부 `_load_scoped_attachment_rows` 와 같은 다층 방어).
    조회 실패는 빈 목록 — 첨부 조회 실패가 질문 점유 자체를 막게 두지 않는다.
    """
    ids = _task_attachment_ids(raw_ids)
    if not ids or not conversation_id:
        return []
    try:
        cur = conn.cursor()
        try:
            placeholders = ", ".join(["%s"] * len(ids))
            cur.execute(
                "SELECT Id, OriginalFilename, Kind, SizeBytes FROM WebConversationAttachments "
                f"WHERE Id IN ({placeholders}) AND ConversationId=%s "
                "AND DeletedAt IS NULL AND DeletePending=0 ORDER BY Id ASC",
                tuple(ids) + (str(conversation_id),))
            rows = cur.fetchall() or []
        finally:
            cur.close()
    except Exception as exc:
        logging.getLogger(__name__).warning("[bridge] 첨부 목록 조회 실패: %r", exc)
        return []
    return [{"attachment_id": int(r[0] or 0), "filename": str(r[1] or ""),
             "kind": str(r[2] or ""), "size_bytes": int(r[3] or 0) if r[3] is not None else None}
            for r in rows]


def _claim_lease_valid(claimed_at) -> bool:
    """점유 lease 가 아직 유효한가. `_CLAIMABLE_SQL` 의 파이썬 쪽 대응.

    같은 상수(`_BRIDGE_CLAIM_LEASE_MIN`)를 쓴다 — SQL 술어와 파이썬 판정이 다른 값을 보면
    "목록에는 다시 뜨는데 읽기는 계속 되는" 어긋난 창이 생긴다.
    `ClaimedAt` 이 NULL 이면 만료로 본다(점유 시각을 모르면 유효하다고 우길 근거가 없다).
    """
    if claimed_at is None:
        return False
    try:
        from datetime import datetime, timedelta

        if not isinstance(claimed_at, datetime):
            return False
        # DB 는 서버 로컬 NOW() 로 기록한다 — 같은 기준(naive local)으로 비교한다.
        return (datetime.now() - claimed_at) < timedelta(minutes=_BRIDGE_CLAIM_LEASE_MIN)
    except Exception:
        return False


@router.post("/api/ai/tools/read_task_attachment")
async def read_task_attachment(request: Request, ctx=Depends(require_ai_token),
                               conn=Depends(app.get_conn)) -> JSONResponse:
    """점유한 웹 질문에 딸린 **첨부 본문**을 줄 범위로 읽는다.

    웹 대화창에서는 첨부를 올리고 "이 파일 분석해줘" 라고 묻는 것이 일상 사용이다. 브리지가
    본문을 못 읽으면 그 사용법만 조용히 죽는다 — 그래서 내부 에이전트가 쓰는
    `read_attachment_content` 를 **task 범위로 못박아** 같은 경로로 연다.

    경계는 넓히지 않는다. 읽을 수 있는 것은 다음을 **모두** 만족하는 첨부뿐이다:
      1. 호출자 계정이 연 `Origin='web'` task 의 것 (남의 질문 불가)
      2. 그 task 를 **호출자가 점유** 중 (집지 않고 훔쳐보기 불가)
      3. 그 대화에 대한 접근 권한이 **지금도** 유효 (점유 후 그룹 퇴출 반영)
      4. 적재 시점에 `_resolve_conversation_attachment_scope` 가 허용한 id 목록 안
    """
    body = await _json(request)
    account = ctx["account"]
    account_id = int(account.get("id") or 0)
    task_id = str(body.get("task_id") or "").strip()
    if not task_id:
        return _json_err(400, "task_id 가 필요합니다.")
    attachment_id = body.get("attachment_id")
    filename = str(body.get("filename") or "").strip()
    if not attachment_id and not filename:
        return _json_err(400, "attachment_id 또는 filename 중 하나가 필요합니다.")

    t0 = time.perf_counter()
    # 원장 상한을 **호출 전에** 건다(codex 리뷰 P2). 사후 record 만 하면 이 도구 하나만 상한
    # 밖에 놓여, 첨부 본문(가장 큰 payload)으로 시간당 bytes 상한을 우회할 수 있다.
    try:
        _ledger.check_limits(_pg(), account_id=account_id, client_id=ctx.get("client_id"))
    except _ledger.RateLimited as exc:
        _safe_record(account, ctx, tool="read_task_attachment", outcome="gated",
                     detail=exc.limit, task_id=task_id)
        return JSONResponse({"error": exc.message}, status_code=429,
                            headers={"Retry-After": str(getattr(exc, "retry_after", 60) or 60)})

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ConversationId, AttachmentIds, ClaimedBy, ClaimedClient, ClaimedAt, "
            "SubmittedAt, Status FROM WebAiTasks "
            "WHERE TaskId=%s AND AccountId=%s AND Origin='web'", (task_id, account_id))
        row = cur.fetchone()
    finally:
        cur.close()
    if row is None:
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="not_found_or_foreign", task_id=task_id)
        return _json_err(404, "대기 중인 질문을 찾을 수 없습니다.")
    conversation_id, raw_ids = row[0], row[1]
    claimed_by, claimed_client, claimed_at, submitted_at, status = row[2], row[3], row[4], row[5], row[6]

    # 점유 경계는 `submit_answer` 와 **같은 모양**이어야 한다(codex 리뷰 P2). 한쪽만 느슨하면
    # 그 쪽이 실질 경계가 된다 — 읽기가 느슨하면 제출을 막아도 내용은 이미 새어 나간 뒤다.
    #
    #  · 점유자 계정 일치      — claim 없이 읽기 차단
    #  · 점유 세션(client) 일치 — 같은 계정의 **다른 세션**이 남의 점유를 타고 읽는 것 차단
    #                            (컬럼 추가 이전 점유 행은 NULL → 호환 통과, submit 과 동일 규약)
    #  · lease 유효            — 만료된 점유는 남의 것이 될 수 있다(재claim 대상)
    #  · 미제출 상태           — 끝난 task 를 계속 읽을 이유가 없다
    if int(claimed_by or 0) != account_id:
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="not_claimed", task_id=task_id)
        return _json_err(409, "먼저 claim_request 로 이 질문을 점유해야 첨부를 읽을 수 있습니다.")
    if claimed_client is not None and str(claimed_client) != str(ctx.get("client_id") or ""):
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="foreign_client", task_id=task_id)
        return _json_err(409, "이 질문은 다른 세션이 점유 중입니다. 해당 세션에서 처리하세요.")
    if submitted_at is not None or str(status or "") != "open":
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="already_submitted", task_id=task_id)
        return _json_err(409, "이미 답변이 제출된 질문입니다.")
    if not _claim_lease_valid(claimed_at):
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="lease_expired", task_id=task_id)
        return _json_err(409, f"점유가 만료됐습니다({_BRIDGE_CLAIM_LEASE_MIN}분). "
                              "claim_request 로 다시 점유하세요.")

    # claim 때와 같은 재검증 — 점유 이후 권한이 회수됐을 수 있다.
    denied = _conversation_access_denied(conn, account, conversation_id)
    if denied is not None:
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="conversation_access_revoked", task_id=task_id)
        return denied

    ids = _task_attachment_ids(raw_ids)
    if not ids:
        return _json_err(404, "이 질문에는 읽을 수 있는 첨부가 없습니다.")

    try:
        import agent_core as _core
        import shared.config as _cfg
    except Exception as exc:
        logging.getLogger(__name__).error("[bridge] 첨부 읽기 모듈 로드 실패: %r", exc)
        return _json_err(503, "첨부를 읽을 수 없습니다(내부 모듈 로드 실패).")

    # 스코프는 **이 요청 동안만** 세운다. 되돌리지 않으면 같은 워커 스레드의 다음 요청이
    # 남의 대화 스코프를 물려받는다 — 그래서 token 으로 반드시 복원한다.
    # ⚠ 되돌려야 하는 것은 스코프 id 하나가 아니다(codex 리뷰 P2). `read_attachment_content` 는
    # provenance 판정 결과(`_UNTRUSTED_ATTACH_BODY_CTX` 등)도 **쓴다** — 복원하지 않으면 같은
    # Context 를 재사용하는 다음 호출이 남의 판정 결과를 물려받는다. 그리고 계정을 세우지 않으면
    # 판정 자체가 실행되지 않아 "타 멤버 파일" 표시가 조용히 사라진다. 둘 다 세우고 둘 다 되돌린다.
    _ctx_tokens: list = [_core._ATTACHMENT_IDS_CTX.set(",".join(str(i) for i in ids))]
    for _name, _val in (("_ACTIVE_ACCOUNT_ID_CTX", account_id),
                        ("_UNTRUSTED_ATTACH_BODY_CTX", False),
                        ("_UNTRUSTED_ATTACH_BODY_REASON_CTX", "")):
        _var = getattr(_core, _name, None)
        if _var is not None:
            try:
                _ctx_tokens.append(_var.set(_val))
            except Exception:
                pass
    prev_conv = None
    try:
        prev_conv = _cfg.get_active_conversation_id()
    except Exception:
        prev_conv = None
    try:
        _cfg.set_active_conversation_id(str(conversation_id or ""))
        res = _core.read_attachment_content(
            filename=filename or None,
            attachment_id=int(attachment_id) if attachment_id else None,
            start_line=int(body.get("start_line") or 1),
            max_lines=(int(body["max_lines"]) if body.get("max_lines") else None),
        )
    except Exception as exc:
        logging.getLogger(__name__).error(
            "[bridge] 첨부 읽기 실패 task=%s: %r", task_id, exc)
        return _json_err(500, "첨부를 읽는 중 오류가 발생했습니다.")
    finally:
        # 역순 복원 — set 순서와 반대로 되돌려야 중첩 Context 가 어긋나지 않는다.
        for _tok in reversed(_ctx_tokens):
            try:
                _tok.var.reset(_tok)
            except Exception:
                pass
        try:
            _cfg.set_active_conversation_id(prev_conv)
        except Exception:
            pass

    if not res.get("ok"):
        _safe_record(account, ctx, tool="read_task_attachment", outcome="denied",
                     detail="out_of_scope", task_id=task_id)
        return _json_err(404, str(res.get("error") or "첨부를 읽을 수 없습니다."))

    # 첨부 본문은 **사용자가 올린 텍스트** — 지연 인젝션 방어 각인을 씌운다(질문 본문과 동형).
    marked = _guard.wrap_tool_output(
        str(res.get("text") or ""),
        account=str(account.get("username") or account.get("id")),
        conversation_id=conversation_id, task_id=task_id, source="attachment")
    try:
        _ledger.record(_pg(), account_id=account_id, tool="read_task_attachment",
                       client_id=ctx.get("client_id"), task_id=task_id,
                       bytes_out=len(marked.encode("utf-8")),
                       latency_ms=int((time.perf_counter() - t0) * 1000), outcome="ok")
    except _ledger.LedgerUnavailable as exc:
        return _json_err(503, f"원장을 기록할 수 없어 요청을 중단했습니다: {exc}")

    return JSONResponse({
        "task_id": task_id,
        "attachment_id": int(res.get("attachment_id") or 0),
        "filename": str(res.get("filename") or ""),
        "kind": str(res.get("kind") or ""),
        "text": marked,
        "start_line": int(res.get("start_line") or 1),
        "end_line": int(res.get("end_line") or 0),
        "total_lines": int(res.get("total_lines") or 0),
        "truncated": bool(res.get("truncated")),
    })


def _release_claim(conn, task_id: str, account_id: int) -> None:
    """점유 해제 — 실패 경로에서 작업을 대기열로 되돌린다.

    `Status='open'` 인 것만 되돌린다: 이미 제출된(`submitted`) 작업을 되살리면 확정 불변이 깨진다.
    """
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE WebAiTasks SET ClaimedBy=NULL, ClaimedAt=NULL "
                "WHERE TaskId=%s AND AccountId=%s AND Status='open'",
                (task_id, account_id))
            conn.commit()
        finally:
            cur.close()
    except Exception as exc:
        logging.getLogger(__name__).error(
            "[bridge] 점유 해제 실패 task=%s — 이 작업은 수동 개입 없이는 다시 잡히지 않는다: %r",
            task_id, exc)


#: `claim_request` 가 함께 넘기는 이전 대화 turn 수. 크게 잡으면 외부 AI 컨텍스트를 잠식하고
#: 작게 잡으면 후속 질문이 해석되지 않는다. 대화형 후속질문 대부분이 직전 2~3 turn 안에서 닫힌다.
_BRIDGE_HISTORY_TURNS = 6
_BRIDGE_HISTORY_CHARS = 4000

#: 점유 lease. 이 시간이 지나도록 제출되지 않은 작업은 **다시 대기열에 나타난다**.
#:
#: 왜 필요한가: 점유는 커밋되는데 그 뒤 어떤 이유로든(러너 강제 종료·머신 절전·`--exec` 타임아웃·
#: 빈 답변으로 건너뜀·프로세스 크래시) 제출이 오지 않으면, lease 가 없는 한 그 질문은 목록에서
#: 영원히 사라진다 — 사용자는 "AI 가 가져갔는데 답이 없다" 는 상태에 갇힌다(codex 재리뷰 P1).
#: 원장 실패 한 경로만 롤백하는 것으로는 부족하다는 것이 그 지적의 요지다.
#:
#: 30분: 개인 머신 AI 가 어려운 질문을 붙들 수 있는 현실적 상한이면서, 사용자가 "잊혔나" 하고
#: 다시 물어보기 전에 회수되는 길이.
_BRIDGE_CLAIM_LEASE_MIN = 30

#: 점유 가능 조건 — 미점유이거나 lease 가 만료된 것. `list_open_requests` 와 `claim_request` 가
#: **같은 술어**를 써야 한다(목록에 보이는데 집으면 409 나는 불일치를 만들지 않는다).
_CLAIMABLE_SQL = (
    "(ClaimedBy IS NULL OR ClaimedAt IS NULL "
    f"OR ClaimedAt < DATE_SUB(NOW(), INTERVAL {_BRIDGE_CLAIM_LEASE_MIN} MINUTE))"
)


def _conversation_access_denied(conn, account: dict[str, Any], conversation_id) -> JSONResponse | None:
    """대화 접근 권한 **재검증**. 통과면 None, 아니면 403 응답.

    task 를 연 계정이라는 사실만으로는 부족하다(codex 재리뷰 P1): 질문을 던진 뒤 그룹에서
    퇴출되거나 권한이 회수될 수 있고, 그 사이 `claim_request` 는 **최신** 대화 문맥을 읽고
    `submit_answer` 는 그 대화에 글을 쓴다. 두 시점 사이의 권한 변화를 반영하지 않으면
    "질문 당시의 권한" 으로 지금의 대화를 읽고 쓰는 창이 열린다.

    대화가 없는 task(외부 AI 가 스스로 연 것)는 검증 대상이 아니다 — 붙을 대화가 없다.
    """
    if not conversation_id:
        return None
    try:
        allowed = app._account_can_access_conversation(
            conn, account, str(conversation_id),
            "conversation.read.own", "conversation.read.any")
    except Exception as exc:
        # 판정 불가는 거부한다(fail-closed) — 권한 확인이 안 되는 상태에서 대화를 열지 않는다.
        logging.getLogger(__name__).error(
            "[bridge] 대화 권한 판정 실패 conv=%s: %r", conversation_id, exc)
        allowed = False
    if allowed:
        return None
    return _json_err(403, "이 대화에 접근할 권한이 없습니다(권한이 변경되었을 수 있습니다).")


def _recent_conversation_context(conn, conversation_id, exclude_text: str = "") -> str:
    """대화의 최근 turn 을 렌더한 문자열. 조회 실패는 빈 문자열(도구를 막지 않는다)."""
    if not conversation_id:
        return ""
    try:
        rows = app._conv_load_messages_raw(conn, str(conversation_id), upto_id=None) or []
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[bridge] 대화 문맥 로드 실패 conv=%s: %r", conversation_id, exc)
        return ""

    parts: list[str] = []
    for _id, role, content, _created, _meta in rows[-_BRIDGE_HISTORY_TURNS:]:
        text = str(content or "").strip()
        if not text or text == exclude_text:
            continue
        speaker = "사용자" if str(role) == "user" else "assistant"
        parts.append(f"[{speaker}] {text}")
    if not parts:
        return ""
    rendered = "\n\n".join(parts)
    if len(rendered) > _BRIDGE_HISTORY_CHARS:
        # 조용히 자르지 않는다 — 잘렸다는 사실을 호출자가 알아야 "문맥이 다 왔다" 고 오해하지 않는다.
        rendered = rendered[-_BRIDGE_HISTORY_CHARS:]
        rendered = "(앞부분 생략 — 전체 기록은 웹 대화 화면 참조)\n\n" + rendered
    return rendered


@router.post("/api/ai/tools/{tool_name}")
async def run_structure_tool(tool_name: str, request: Request, ctx=Depends(require_ai_token),
                             conn=Depends(app.get_conn)) -> JSONResponse:
    """P0 구조 조회. 내부 에이전트와 **같은** `tools.execute_tool` 을 탄다 — SQL 신뢰경계·
    부하 게이트·allowlist 를 재구현하지 않는다(재구현은 곧 두 벌 관리이고, 갈리는 순간 약한
    쪽이 실질 경계가 된다)."""
    if tool_name not in EXPOSED_TOOLS:
        return _json_err(404, f"'{tool_name}' 는 이 표면에 노출된 도구가 아닙니다.")
    if tool_name in P1_TOOLS and not _sql_enabled():
        return _json_err(403, f"'{tool_name}' 는 현재 비활성화되어 있습니다(운영 설정).")

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

    # 밑줄 시작 키는 **예약**이다(`_stats_out` 등 내부 out-param). 호출자가 심어 보내는 것을
    # 그대로 넘기면 내부 규약과 충돌한다 — 입구에서 걷어낸다.
    arguments = {k: v for k, v in dict(body.get("arguments") or {}).items()
                 if not str(k).startswith("_")}
    # `execute_tool` 이 `arguments` 에서 `datasource` 를 pop 한다 — 실행 뒤에 읽으면 항상 빈 값이
    # 되어 추출 원장의 datasource 추적이 통째로 죽는다(codex P2). 실행 전에 붙잡는다.
    requested_ds = str(arguments.get("datasource") or "") or None
    sql_stats: dict[str, Any] = {}
    if tool_name in P1_TOOLS:
        arguments["_stats_out"] = sql_stats
        arguments["_suppress_csv"] = True   # 외부 표면엔 다운로드가 없다 — 파일 자체를 안 만든다
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
        # ⚠ yield 값이 **도구에 넘길 연결**이다. 예전엔 라우터를 받아 `None if _router else conn`
        #   으로 넘겼는데, 단일 바인딩 제품(대부분)에서 그 `conn` 이 **메모리 DB** 라
        #   구조 조회가 내부 서버를 향했다(다른 대화의 첨부 샌드박스까지 노출).
        with _authz.scoped_execution(_core, _tools, conn, product_id, app_mod=app) as _ds_conn:
            out = _tools.execute_tool(_ds_conn, tool_name, arguments)
    except _authz.ScopeDenied as exc:
        # 바인딩 없음 등 — 스코프를 세울 수 없으면 실행하지 않는다(fail-closed).
        _safe_record(account, ctx, tool=tool_name, outcome="denied", detail=exc.code,
                     task_id=task_id)
        return _json_err(403, exc.message)
    except Exception as exc:  # noqa: BLE001
        _safe_record(account, ctx, tool=tool_name, outcome="error", detail=str(exc)[:200],
                     task_id=task_id)
        return _json_err(500, f"도구 실행 오류: {exc}")

    rendered = str(out or "")
    if tool_name in P1_TOOLS:
        rendered = _sanitize_sql_output(rendered, sql_stats.get("csv_paths") or [])
        cap = _sql_max_rows()
        got = int(sql_stats.get("total_rows") or 0)
        if cap > 0 and got > cap:
            # 부하는 이미 발생했으므로 **원장에는 기록하고** 결과만 돌려주지 않는다.
            _safe_record(account, ctx, tool=tool_name, outcome="gated",
                         detail=f"rows>{cap}", task_id=task_id, rows_returned=got)
            return JSONResponse(
                {"error": f"이 쿼리는 {got:,}행을 반환합니다(건당 상한 {cap:,}행). "
                          f"결과를 돌려주지 않았습니다 — 집계(COUNT/GROUP BY)·기간·WHERE 로 "
                          f"범위를 좁혀 다시 물어보세요. 이 호출의 부하는 원장에 기록됐습니다.",
                 "rows": got, "limit": cap},
                status_code=413)
    marked = _guard.wrap_tool_output(
        rendered, account=str(account.get("username") or account.get("id")),
        conversation_id=task.get("conversation_id"), task_id=task_id, source=tool_name)

    try:
        _ledger.record(_pg(), account_id=int(account.get("id") or 0), tool=tool_name,
                       client_id=ctx.get("client_id"), task_id=task_id,
                       datasource_key=requested_ds,
                       schema_name=str(arguments.get("schema_name") or "") or None,
                       # execute_sql 은 백엔드가 알려준 **실제 행수**를 쓴다. 렌더 줄 수로 세면
                       # 미리보기 50행만 잡혀 시간당 행 상한이 사실상 걸리지 않는다.
                       rows_returned=(int(sql_stats["total_rows"])
                                      if "total_rows" in sql_stats
                                      else rendered.count("\n")),
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
        cur.execute("SELECT TaskId, ConversationId, ProductId, Question, Status, DatasourceKey "
                    "FROM WebAiTasks WHERE TaskId = %s AND AccountId = %s LIMIT 1",
                    (task_id, int(account.get("id") or 0)))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return None
    return {"task_id": row[0], "conversation_id": row[1], "product_id": row[2],
            "question": row[3], "status": row[4], "datasource_key": row[5]}


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


# ── AC-7 열람 (웹 세션 전용) ──────────────────────────────────────────────────
#
# ⚠ **외부 access token 으로는 도달하지 않는다.** 이 라우트들은 `require_ai_token` 이 아니라
# `app._require_account`(웹 로그인 세션)를 쓴다. 외부 AI 에게 "자기 기록 열람" 을 주면 그
# 엔드포인트가 곧 task 열거면이 되고, 같은 `client_id` 를 공유하는 무관한 사용자들(DCR 은 앱
# 식별자를 누구에게나 준다 — L4 의 codex P1 과 같은 구조)에게 타 계정 task 의 존재가 드러날
# 여지가 생긴다. 보존의 수혜자는 **사람 운영자**이지 외부 런타임이 아니다.

_TASKS_PAGE_MAX = 100

# 열람 권한. 콘솔 서브탭의 표시 게이트와 **같은 키**를 쓴다 — 표시와 집행이 갈리면 화면에
# 없는 것을 REST 로 읽거나 그 반대가 된다.
#
# ⚠ codex REV-0026 P2: 처음에는 `admin.console.access` 를 썼는데 **그런 권한 키가 없다**.
# `_account_has_permission` 은 미정의 키에 항상 False 를 돌려주므로, 관리자도 전역 조회를
# 받지 못한 채 조용히 자기 것만 보게 된다 — "존재하지 않는 방어" 의 거울상(존재하지 않는
# 권한으로 게이트한 탓에 기능이 조용히 죽는 형태)이다. 실재 키로 바로잡는다.
_TASKS_READ_PERM = "console.aiops.read"
# 전역(타 계정 포함) 조회. 감사 축의 기존 키를 그대로 쓴다.
_TASKS_READ_ANY_PERM = "audit.read.any"


def _require_task_reader(account: dict[str, Any]):
    """열람 자격. 미보유면 403 — 로그인만으로는 이 원장에 닿지 않는다.

    보존의 수혜자는 **사람 운영자**다. 로그인 계정 전체에 열어 두면 이 엔드포인트가 곧
    외부 AI 활동 열거면이 된다.
    """
    if not app._account_has_permission(account, _TASKS_READ_PERM):
        return _json_err(403, "외부 AI 작업 원장을 조회할 권한이 없습니다.")
    return None


def _task_scope_clause(account: dict[str, Any]) -> tuple[str, list[Any]]:
    """조회 범위. 전역 권한이 있을 때만 타 계정 task 까지 본다.

    프론트 게이트가 아니라 **여기가 집행면**이다(프론트 `can()` 은 표시-관대라 판정에 쓰지
    않는다 — 이 저장소의 기존 회귀 사례).
    """
    if app._account_has_permission(account, _TASKS_READ_ANY_PERM):
        return "", []
    return " AND AccountId = %s", [int(account.get("id") or 0)]


@router.get("/api/ai/bridge_status")
def bridge_status(request: Request) -> JSONResponse:
    """feature-0043 — 웹 대화창이 폴링하는 브리지 진행 상태.

    **웹 세션 인증**이다(외부 OAuth 토큰이 아니라). 자기 계정이 연 web task 만 보이며,
    답변 **본문은 싣지 않는다** — 도착 사실만 알리고 화면은 대화를 다시 읽어 렌더한다.
    본문을 여기로 흘리면 각인 블록이 두 경로(대화 저장본·상태 API)로 새어 규약이 갈린다.

    `_require_task_reader` 같은 관리 권한을 요구하지 않는 이유: 이건 **자기가 방금 던진 질문의
    진행 상태**이므로 대화 소유자면 충분하다. 스코프는 `AccountId` 로 닫는다.
    """
    task_id = str(request.query_params.get("task_id") or "").strip()
    if not task_id:
        return app._json_error("task_id 가 필요합니다.", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT Status, ClaimedBy, SubmittedAt, ConversationId, Delivered "
                "FROM WebAiTasks WHERE TaskId=%s AND AccountId=%s AND Origin='web'",
                (task_id, int(account.get("id") or 0)))
            row = cur.fetchone()
        finally:
            cur.close()
        if row is None:
            return app._json_error("task 를 찾을 수 없습니다.", 404)
        status = str(row[0] or "")
        submitted = bool(row[2]) or status == "submitted"
        delivered = bool(row[4])
        return JSONResponse({
            "task_id": task_id,
            "status": status,
            "claimed": row[1] is not None,
            # `answered` 는 **제출됐다** 는 뜻이고, `delivered` 는 **대화에 실렸다** 는 뜻이다.
            # 둘을 합치면 저장 실패 시 화면엔 아무것도 없는데 "답변 도착" 이라 말하게 된다
            # (codex 재리뷰 P1). 프런트는 delivered=false 면 그 사실을 사용자에게 알린다.
            "answered": submitted,
            "delivered": delivered,
            "conversation_id": str(row[3] or ""),
        })
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.get("/api/ai/tasks")
def list_ai_tasks(request: Request) -> JSONResponse:
    """외부 AI task 목록. 답변 **본문은 싣지 않는다**(목록에서 각인 블록을 흘리지 않는다)."""
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        denied = _require_task_reader(account)
        if denied:
            return denied
        try:
            limit = max(1, min(_TASKS_PAGE_MAX, int(request.query_params.get("limit") or 50)))
            offset = max(0, int(request.query_params.get("offset") or 0))
        except (TypeError, ValueError):
            return _json_err(400, "limit/offset 이 올바르지 않습니다.")

        where, params = _task_scope_clause(account)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT TaskId, AccountId, ClientId, ProductId, Question, Status, "
                "InjectionVerdict, AnswerVerdict, AnswerBytes, AnswerTruncated, DatasourceKey, "
                "CreatedAt, SubmittedAt, (Answer IS NOT NULL) AS HasAnswer "
                f"FROM WebAiTasks WHERE 1=1{where} ORDER BY Id DESC LIMIT %s OFFSET %s",
                (*params, limit, offset))
            rows = cur.fetchall() or []
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    items = [{
        "task_id": r[0], "account_id": r[1], "client_id": r[2], "product_id": r[3],
        "question": r[4], "status": r[5], "injection_verdict": r[6],
        "answer_verdict": r[7], "answer_bytes": r[8], "answer_truncated": bool(r[9]),
        "datasource_key": r[10],
        "created_at": str(r[11]) if r[11] else None,
        "submitted_at": str(r[12]) if r[12] else None,
        "has_answer": bool(r[13]),
    } for r in rows]
    return JSONResponse({"items": items, "limit": limit, "offset": offset})


@router.get("/api/ai/tasks/{task_id}")
def get_ai_task(task_id: str, request: Request) -> JSONResponse:
    """task 상세 — 보존된 답변 본문 포함.

    본문은 저장 시점에 각인된 형태 그대로 돌려준다. 각인을 벗겨서 주면 이 블록이 다시 어떤
    LLM 컨텍스트로 들어갔을 때 "외부가 쓴 텍스트" 라는 사실이 사라진다(AC-7 의 목적).
    """
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        denied = _require_task_reader(account)
        if denied:
            return denied
        where, params = _task_scope_clause(account)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT TaskId, AccountId, ClientId, ProductId, Question, Status, "
                "InjectionVerdict, Answer, AnswerVerdict, AnswerBytes, AnswerTruncated, "
                "SourceTasks, DatasourceKey, CreatedAt, SubmittedAt "
                f"FROM WebAiTasks WHERE TaskId = %s{where} LIMIT 1",
                (task_id, *params))
            row = cur.fetchone()
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        # 존재 여부를 권한으로 갈라 알려주지 않는다 — 스코프 밖은 '없음' 과 구분 불가해야 한다.
        return _json_err(404, "task 를 찾을 수 없습니다.")
    return JSONResponse({
        "task_id": row[0], "account_id": row[1], "client_id": row[2], "product_id": row[3],
        "question": row[4], "status": row[5], "injection_verdict": row[6],
        "answer": row[7], "answer_verdict": row[8], "answer_bytes": row[9],
        "answer_truncated": bool(row[10]),
        "source_tasks": [s for s in str(row[11] or "").split(",") if s],
        "datasource_key": row[12],
        "created_at": str(row[13]) if row[13] else None,
        "submitted_at": str(row[14]) if row[14] else None,
        "tool_calls": _task_tool_calls(str(row[0])),
    })


def _mark_answer_verdict(conn, task_id: str, verdict: str) -> None:
    """거절된 제출 시도의 **판정만** task 행에 남긴다 (페이로드는 저장하지 않는다).

    원장에만 남기면 저장소가 달라(task=MySQL · 원장=PG) 콘솔에서 task 를 볼 때 "거절된 제출
    시도가 있었다" 는 사실이 보이지 않는다. 이미 확정된 답변은 건드리지 않는다
    (`SubmittedAt IS NULL` 가드 — 확정 뒤의 거절 시도가 기존 판정을 덮지 않게).

    여기서 실패해도 거절 자체는 유지한다 — 이 기록은 감사 보조이지 거절의 근거가 아니다.
    """
    try:
        cur = conn.cursor()
        try:
            cur.execute("UPDATE WebAiTasks SET AnswerVerdict = %s "
                        "WHERE TaskId = %s AND SubmittedAt IS NULL", (verdict, task_id))
            conn.commit()
        finally:
            cur.close()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _task_tool_calls(task_id: str) -> list[dict[str, Any]]:
    """이 task 가 실제로 돌린 도구 이력(원장).

    질문·답변만 보여 주면 "무엇을 근거로 그 답이 나왔는가" 를 감사할 수 없다 — 답변은 외부
    런타임의 **주장**이고, 그 주장을 검증할 사실은 어느 도구로 어느 datasource 를 얼마나 읽었나
    이다. 두 원장이 저장소가 다르므로(task=MySQL · 도구=PG) 여기서 합류시킨다.

    원장 조회 실패는 상세 전체를 죽이지 않는다 — 보존된 질문·답변을 보여 주는 것이 1차 목적이고,
    이 목록은 보강이다(fail-soft. 저장 경로의 fail-closed 와 목적이 다르다).
    """
    try:
        pg = _pg()
        if pg is None:
            return []
        with pg.cursor() as cur:
            cur.execute(
                "SELECT tool, datasource_key, schema_name, rows_returned, bytes_out, "
                "       est_scanned_rows, latency_ms, outcome, detail, created_at "
                "FROM agent_runtime.tool_call_usage WHERE task_id = %s "
                "ORDER BY created_at ASC LIMIT 500", (task_id,))
            rows = cur.fetchall() or []
    except Exception:
        return []
    return [{"tool": r[0], "datasource_key": r[1], "schema_name": r[2],
             "rows_returned": r[3], "bytes_out": r[4], "est_scanned_rows": r[5],
             "latency_ms": r[6], "outcome": r[7], "detail": r[8],
             "created_at": str(r[9]) if r[9] else None} for r in rows]
