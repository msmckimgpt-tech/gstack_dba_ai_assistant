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

# feature-0043: 브리지 task 의 점유·취소 술어 **단일 정본**. 지역 별칭(`_CLAIMABLE_SQL` 등)은
# 아래 "브리지 상태 술어" 절에서 붙인다 — 정의가 아니라 참조다.
from shared.bridge_tasks import (
    BRIDGE_CLAIM_LEASE_MIN as _BRIDGE_CLAIM_LEASE_MIN,
    CLAIMABLE_SQL as _CLAIMABLE_SQL,
    DEFERRED_MAX_AGE_HOURS as _DEFERRED_MAX_AGE_HOURS,
    STATUS_CANCELED as _STATUS_CANCELED,
    STATUS_DEFERRED as _STATUS_DEFERRED,
    STATUS_EXPIRED as _STATUS_EXPIRED,
    claim_is_live as _claim_is_live,
    promote_latest_deferred as _promote_latest_deferred,
)

import app

INCLUDE_ORDER = 9_450  # oauth_as(9_400) 다음, ai_discovery(9_500) 앞
router = APIRouter()

# feature-0041 서버측 모듈은 **이 디렉터리**(= 컨테이너 `/app/web`)에 있다.
# 초기 구현은 feature-local `unit/feature-0041-.../src` 에 두고 sys.path 를 주입했는데,
# agent 이미지가 그 경로를 COPY 하지 않아 라이브 기동이 ModuleNotFoundError 로 죽었다
# (Dockerfile 은 feature-0002/0003/shared 만 복사). 소비자가 feature-0003 라우터뿐이므로
# 코드 거주지를 소비처로 옮기는 것이 이 저장소 관례에도 맞다.
import bridge_drain as _drain       # noqa: E402  feature-0045: 배포 연속성(대기 계상·드레인)
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

    _ctx_work, _ctx_reason = _bridge_step_narration(body, {})
    _record_bridge_step(
        conn, task, "get_task_context",
        {k: v for k, v in (("focus", str(body.get("focus") or "").strip()),) if v},
        payload, work=_ctx_work, reason=_ctx_reason,
        elapsed_ms=(time.perf_counter() - t0) * 1000)

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

    # feature-0043(2026-08-28): 사용자가 **취소했거나 새 질문으로 갈아탄** 요청이다.
    #
    # 여기서 막지 않으면 취소 UX 가 거짓이 된다 — 화면은 "취소했습니다" 라고 말했는데 잠시 뒤
    # 답변이 대화에 붙는다. 러너는 `wait_for_request` 의 `canceled_task_ids` 로 **제출 전에**
    # 하차하지만, 그 신호를 읽지 않는 등록형 AI 도 있으므로 서버가 마지막에 집행한다.
    # 인지(러너)와 집행(서버)은 층이 다르며, 두 겹이지 이중 정의가 아니다.
    #
    # 저장도 하지 않는다: 취소된 요청의 답변은 어디에도 표시되지 않으므로 보존할 소비처가 없고,
    # 외부 텍스트를 이유 없이 붙들고 있지 않는다.
    # ⚠ 이 조기 반환은 **빠른 길일 뿐 집행이 아니다.** `_load_task` 가 읽은 상태는 이미 과거이고,
    # 아래 인젝션 판정·형제 조회 사이(여러 DB 왕복)에 사용자가 취소하면 이 검사를 그냥 지나친다.
    # 실제 집행은 확정 UPDATE 의 `Status <> 'canceled'` 조건이 한다(같은 문장 안 = TOCTOU 없음).
    if str(task.get("status") or "") == _STATUS_CANCELED:
        _safe_record(account, ctx, tool="submit_answer", outcome="denied",
                     detail="task_canceled", task_id=task_id)
        return _json_err(409, _CANCELED_SUBMIT_MSG)

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
            # feature-0043(2026-08-28): **취소 집행은 여기서** 한다.
            #
            # 위쪽 `_load_task` 기반 조기 반환만으로는 못 막는다 — 그 값은 인젝션 판정·형제
            # 조회(여러 DB 왕복) 전의 과거 상태다. 그 사이 사용자가 중단하거나 새 질문으로
            # 갈아타면 조기 검사를 지나쳐 **취소된 답변이 대화에 새 말풍선으로 붙는다**
            # (취소 말풍선은 `placeholder=false` 라 덮어쓰기 대상에서도 빠져 append 로 떨어진다).
            # 조건을 같은 UPDATE 안에 두면 그 창이 사라진다 — 바로 위 `SubmittedAt IS NULL`
            # 가드가 같은 이유로 SQL 안에 있다.
            "WHERE TaskId = %s AND SubmittedAt IS NULL AND Status <> %s "
            "AND (Origin <> 'web' OR (ClaimedBy = %s "
            "     AND (ClaimedClient IS NULL OR ClaimedClient = %s)))",
            (stored, len(answer.encode("utf-8")), answer_verdict["verdict"], truncated,
             ",".join(str(d) for d in declared)[:4000], task_id, _STATUS_CANCELED,
             int(account.get("id") or 0), ctx.get("client_id")))
        affected = cur.rowcount
        conn.commit()
        if not affected:
            # 세 사유가 같은 rowcount 0 으로 오므로 구분해서 안내한다 — 러너의 다음 행동이
            # 다르다(취소=버리기 / 이미 제출=건너뛰기 / 미점유=claim_request 먼저).
            cur.execute(
                "SELECT SubmittedAt, Origin, ClaimedBy, Status FROM WebAiTasks WHERE TaskId=%s",
                (task_id,))
            _r = cur.fetchone()
            if _r is not None and str(_r[3] or "") == _STATUS_CANCELED:
                _safe_record(account, ctx, tool="submit_answer", outcome="denied",
                             task_id=task_id, detail="task_canceled_race")
                return _json_err(409, _CANCELED_SUBMIT_MSG)
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
    delivered = _deliver_web_bridge_answer(conn, task_id, account, answer,
                                           title=str(body.get("title") or ""))

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


#: 브리지에만 있는 도구의 (무엇을, 왜). 내부 경로에는 대응 도구가 없어 `_derive_step_*` 이
#: 모르는 이름들이다 — 여기서 채우지 않으면 사용자에게 "단계를 수행한다" 로만 보인다.
_BRIDGE_ONLY_NARRATION: dict[str, tuple[str, str]] = {
    "get_task_context": ("이 질문의 도메인 맥락 번들을 확인한다",
                         "질문이 어느 업무 영역인지 먼저 파악해 조사 범위를 좁히기 위해"),
    "read_task_attachment": ("첨부 파일의 내용을 읽는다",
                             "질문에 딸린 첨부의 실제 내용을 확인하기 위해"),
}


def _promote_deferred_for(conn, account_id: int) -> str:
    """연결이 성립한 이 계정의 **보류 질문 1건을 대기열에 올린다**. 반환 = 승격된 task_id.

    호출 지점이 `list_open_requests` · `wait_for_request` 인 이유: 개인 AI 가 "가져갈 질문
    있나" 를 묻는 그 순간이 **연결이 실제로 성립했다는 유일한 증거**다. 토큰 발급 시점에
    올리면, 발급만 받고 한 번도 오지 않는 클라이언트 때문에 질문이 대기열에서 늙는다.

    밀린 것을 한꺼번에 처리하지 않는다 — 정본(`promote_latest_deferred`)이 최근 1건만 올리고
    나머지는 만료시킨다. 만료된 질문의 대기 말풍선은 여기서 '처리되지 않음' 으로 정정한다:
    상태만 바꾸고 화면을 그대로 두면 "연결하면 이 질문부터 처리합니다" 가 영원히 박제된다.
    """
    promoted, expired = _promote_latest_deferred(conn, account_id=int(account_id or 0))
    # 방금 만료시킨 것 + **이미 만료됐지만 말풍선이 아직 안 고쳐진 것**을 함께 정정한다.
    #
    # 상태(MySQL)와 말풍선(PG)은 다른 저장소라 한 번에 확정할 수 없다. 정정이 한 번 실패하면
    # 그 task 는 두 번 다시 조회되지 않아, 화면에 "연결하면 이 질문부터 처리합니다" 가 영구히
    # 남는다(codex REV-20260828T070000 P1). 정정은 idempotent 하므로(placeholder=true 인 것만
    # 바꾼다) 매 연결마다 다시 시도해도 안전하다 — 일시 장애는 다음 연결에서 자동 복구된다.
    _settle_expired_deferred(conn, expired + _recent_unsettled_expired(conn, account_id, expired))
    return promoted


def _recent_unsettled_expired(conn, account_id: int, exclude: list[str]) -> list[str]:
    """최근 만료된 보류 질문 중 **아직 정정되지 않았을 수 있는** task id.

    범위를 최근으로 좁히는 이유: 정정은 idempotent 라 여러 번 시도해도 무해하지만, 계정의
    만료 이력 전체를 매 연결마다 훑으면 오래된 행이 영원히 조회 대상으로 남는다. 보류의 유효
    기간과 같은 창(`DEFERRED_MAX_AGE_HOURS`)이면 "이번 작업 흐름" 을 덮는다.
    """
    if not account_id:
        return []
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT TaskId FROM WebAiTasks "
                "WHERE AccountId = %s AND Origin = 'web' AND Status = %s "
                f"  AND CreatedAt > DATE_SUB(NOW(), INTERVAL {_DEFERRED_MAX_AGE_HOURS} HOUR) "
                "ORDER BY CreatedAt DESC LIMIT 20",
                (int(account_id), _STATUS_EXPIRED))
            seen = set(exclude or [])
            return [str(r[0]) for r in (cur.fetchall() or []) if str(r[0]) not in seen]
        finally:
            cur.close()
    except Exception:
        return []


def _settle_expired_deferred(conn, task_ids: list[str]) -> None:
    """만료된 보류 질문의 대기 말풍선을 '처리되지 않음' 안내로 바꾼다.

    말풍선 정정 SQL 은 웹 쪽 정본(`conversations._mark_bridge_placeholders_canceled`)을 그대로
    쓴다 — 취소와 만료는 "종결된 안내로 바꾸고 덮어쓰기 대상에서 뺀다" 는 같은 처리이고,
    여기서 SQL 을 다시 쓰면 두 벌이 되어 언젠가 갈린다(이 feature 가 반복해 겪은 결함).
    """
    if not task_ids:
        return
    log = logging.getLogger(__name__)
    try:
        # 지연 import — 라우터 로드 시점 순환 회피(다른 핸들러의 `import agent_core` 와 동형).
        import routers.conversations as _convs

        cur = conn.cursor()
        try:
            marks = ",".join(["%s"] * len(task_ids))
            cur.execute(
                f"SELECT TaskId, ConversationId FROM WebAiTasks WHERE TaskId IN ({marks})",
                tuple(task_ids))
            rows = cur.fetchall() or []
        finally:
            cur.close()
        by_conv: dict[str, list[str]] = {}
        for tid, cid in rows:
            if cid:
                by_conv.setdefault(str(cid), []).append(str(tid))
        for cid, tids in by_conv.items():
            _convs._mark_bridge_placeholders_canceled(
                conn, cid, tids, _convs._BRIDGE_NOTICE_DEFERRED_EXPIRED)
    except Exception as exc:
        # 말풍선 정정 실패가 승격 자체를 무르지 않는다 — 승격된 질문은 이미 대기열에 있다.
        log.warning("[bridge] 만료 보류 질문 말풍선 정정 실패 (%d건): %r", len(task_ids), exc)


def _bridge_derived_narration(tool_name: str, args: dict[str, Any] | None) -> tuple[str, str]:
    """도구·인자에서 (무엇을, 왜) 를 파생한다 — 내부 경로와 **같은 헬퍼**를 쓴다.

    `agent_core._derive_step_work` / `_derive_step_reason` 은 서버 LLM 경로가 narration 을
    받지 못했을 때 쓰던 fallback 이다. 브리지에서 문구를 새로 지으면 같은 도구가 경로에 따라
    다르게 표현되고, 그때부터 둘 중 하나는 반드시 낡는다. 브리지 전용 도구(내부에 대응이 없는
    이름)만 위 표로 보완한다.
    """
    payload = args if isinstance(args, dict) else {}
    tool = str(tool_name or "").strip().lower()
    if tool in _BRIDGE_ONLY_NARRATION:
        work, reason = _BRIDGE_ONLY_NARRATION[tool]
        name = str(payload.get("filename") or "").strip()
        if tool == "read_task_attachment" and name:
            work = f'첨부 파일 "{name}" 의 내용을 읽는다'
        return work, reason
    try:
        import agent_core as _core

        work = str(_core._derive_step_work(tool, payload) or "").strip()
        reason = str(_core._derive_step_reason(tool, payload) or "").strip()
        # 내부 헬퍼가 모르는 도구는 "단계를 수행한다" 로 떨어진다 — 도구 이름이라도 남긴다.
        if tool and work in ("", "단계를 수행한다"):
            work = f"`{tool}` 도구를 실행한다"
        return work, reason
    except Exception:
        # 파생 실패가 단계 기록 자체를 막지는 않는다(빈 문구로라도 단계는 남는다).
        return (f"`{tool}` 도구를 실행한다" if tool else ""), ""


def _bridge_step_narration(body: dict[str, Any], arguments: dict[str, Any]) -> tuple[str, str]:
    """개인 AI 가 함께 보낸 단계 narration `(work, reason)` 을 꺼내고 **인자에서 제거**한다.

    내부 경로(`agent_core`)는 LLM 이 도구 호출 인자에 실어 보낸 `work`/`reason` 을 pop 해서
    쓴다(TASK-0178). 브리지도 같은 계약을 쓴다 — 다만 MCP 어댑터가 최상위로 보낼 수도,
    클라이언트가 `arguments` 안에 넣을 수도 있어 양쪽을 모두 받는다.

    **제거가 핵심이다.** 남겨두면 `execute_tool` 이 알 수 없는 인자를 받는다(도구에 따라
    거절되거나 조용히 무시되는데, 어느 쪽이든 narration 때문에 조사가 실패하면 안 된다).
    """
    out: list[str] = []
    for key in ("work", "reason"):
        inline = arguments.pop(key, None)
        raw = body.get(key)
        picked = raw if raw not in (None, "") else inline
        out.append(str(picked or "").strip()[:500])
    return out[0], out[1]


def _insert_bridge_step(conversation_id: str, run_id: str, entry: dict[str, Any]) -> int:
    """단계 1건을 **번호 채번과 같은 트랜잭션에서** 적재한다. 반환 = 부여된 step_index(실패 0).

    번호를 따로 조회한 뒤 다른 연결로 INSERT 하면 경합에 안전하지 않다(codex
    REV-20260828T040000 P1): 개인 AI 가 도구 두 개를 동시에 부르면 둘 다 `MAX=0` 을 읽어
    같은 번호로 저장되고, 증분 폴링(`step_index > after_step`)이 뒤늦게 커밋된 행을 **영구히**
    건너뛴다. advisory lock 을 잡고 `INSERT ... SELECT MAX+1` 을 한 문장으로 실행해 run 단위로
    직렬화한다(락은 커밋과 함께 풀린다 — 채번과 적재가 갈리지 않는다).

    저장 형태는 내부 경로와 같다: payload 는 `agent_core._build_step_payload` 가 만든 것을
    그대로 펼친다(컬럼이 갈리면 표시층이 두 벌을 다루게 된다).
    """
    pg = _pg()
    if pg is None:
        return 0
    try:
        args_json = json.dumps(entry.get("args") or {}, ensure_ascii=False)
        summary = entry.get("result_summary")
        summary_json = json.dumps(summary, ensure_ascii=False) if summary is not None else None
        with pg.cursor() as cur:
            # run 단위 직렬화. 트랜잭션 락이라 아래 INSERT 커밋 시점에 자동 해제된다.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (f"{conversation_id}|{run_id}",))
            cur.execute(
                "INSERT INTO agent_runtime.steps "
                "(conversation_id, run_id, step_index, action, tool, intent, "
                " work_text, work_source, reason_text, reason_source, args_json, sql_text, "
                " result_summary_json, error_text) "
                "SELECT %s, %s, COALESCE(MAX(s.step_index), 0) + 1, %s, %s, %s, "
                "       %s, %s, %s, %s, %s, %s, %s, %s "
                "FROM agent_runtime.steps s "
                "WHERE s.conversation_id = %s AND s.run_id = %s "
                "RETURNING step_index",
                (conversation_id, run_id,
                 str(entry.get("action") or "step"), str(entry.get("tool") or ""),
                 str(entry.get("intent") or "")[:255],
                 str(entry.get("work") or "") or None, str(entry.get("work_source") or "") or None,
                 str(entry.get("reason") or "") or None,
                 str(entry.get("reason_source") or "") or None,
                 args_json, str(entry.get("sql") or "") or None,
                 summary_json, str(entry.get("error") or "") or None,
                 conversation_id, run_id))
            row = cur.fetchone()
        pg.commit()
        return int(row[0]) if row else 0
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning(
            "[bridge] 단계 적재 실패 conv=%s run=%s: %r", conversation_id, run_id, exc)
        return 0
    finally:
        try:
            pg.close()
        except Exception:
            pass


def _record_bridge_step(conn, task: dict[str, Any], tool_name: str, args: dict[str, Any],
                        tool_result: str, *, work: str = "", reason: str = "",
                        elapsed_ms: float | None = None, error: str = "") -> None:
    """도구 호출 **그 시점에** 실행 단계를 남긴다 — 「어떤 이유로 → 어떤 작업」 구조 그대로.

    원장 이관(`_materialize_bridge_steps`)만 있던 때는 사유 칸이 비고 작업 문구도 인자가 없어
    `SQL을 실행한다` 로 뭉뚱그려졌다(사용자 제보 2026-08-27). 여기서 기록하면 **인자와 사유를
    둘 다 갖고 있는 유일한 시점**이라 내부 경로와 같은 밀도의 단계가 남는다.

    부수 효과가 하나 더 있다: 답변을 기다리는 동안 단계가 실시간으로 쌓인다(내부 경로의 진행
    표시와 같은 모양). 이관은 제출 시점이라 그때까지 화면이 비어 있었다.

    payload 는 내부 경로와 **같은 빌더**(`agent_core._build_step_payload`)로 만든다 — 결과 요약·
    미리보기·소요 형태가 한 벌로 유지된다. 적재만 브리지 전용(`_insert_bridge_step`)인데,
    번호 채번과 INSERT 를 한 트랜잭션으로 묶어야 하기 때문이다. 실패는 흡수한다: 단계 기록이
    조사 결과 반환을 막지 않는다.
    """
    conversation_id = str(task.get("conversation_id") or "")
    task_id = str(task.get("task_id") or "")
    if not conversation_id or not task_id:
        return  # 외부 AI 가 스스로 연 task(웹 대화 없음) — 그릴 화면이 없다.
    try:
        import agent_core as _core

        derived_work, derived_reason = _bridge_derived_narration(tool_name, args)
        work_text = work or derived_work
        reason_text = reason or derived_reason
        # intent 는 도구 기반으로 고정한다. 내부 경로는 첫 단계에 원 질문을 쓰지만, 여기서는
        # 번호가 INSERT 시점에 정해져 "내가 첫 단계인가" 를 미리 알 수 없다(그걸 알려고 미리
        # 조회하면 방금 없앤 경합이 되돌아온다). 질문은 이미 말풍선에 있다.
        intent = f"{tool_name}: {work_text or tool_name}"
        entry = _core._build_step_payload(
            run_id=task_id, step_index=0, tool_name=tool_name, intent=intent,
            args=args, tool_result=tool_result,
            work_text=work_text, work_source=("external-ai" if work else "derived"),
            reason_text=reason_text, reason_source=("external-ai" if reason else "derived"),
            error=error, elapsed_ms=elapsed_ms)
        _insert_bridge_step(conversation_id, task_id, entry)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[bridge] 실행 단계 기록 실패 task=%s tool=%s: %r", task_id, tool_name, exc)


def _materialize_bridge_steps(conversation_id: str, task_id: str) -> int:
    """개인 AI 가 **우리 도구를 호출한 내역**을 실행 단계로 옮긴다. 반환 = 기록한 단계 수.

    ## 왜 이게 가능한가

    브리지 답변에는 서버 run 이 없다. 그래서 처음엔 'AI 추론' 탭이 비었고, 나는 그것을
    "없는 것을 있는 것처럼 그리지 않는다" 며 그대로 뒀다. 그러나 그건 절반만 맞았다 —
    **답을 만든 추론은 우리 밖에 있지만, 그 AI 가 무엇을 조사했는지는 우리 안에 있다.**
    도구 호출은 전부 원장(`tool_call_usage`)에 남는다.

    그래서 여기서 옮기는 것은 추측이 아니라 **우리가 실제로 관측한 사실**이다: 어떤 도구를
    어떤 스키마에 대해 언제 불렀고, 몇 행이 나갔고, 얼마나 걸렸는지.

    ## 이제는 **fallback** 이다 (2026-08-27, 사용자 제보)

    원장에는 인자가 남지 않는다(`datasource_key`·`schema_name` 뿐). 그래서 여기서 만든 단계는
    표시층 fallback 을 타 `SQL을 실행한다`·`테이블 구조를 확인한다` 처럼 **어느 테이블을 왜**
    가 빠진 문구가 됐고, 사유 칸은 통째로 비었다 — "어떤 이유로 어떤 작업을 했다" 라는 구조가
    사라진 것이다.

    지금은 도구 호출 **그 시점에** `_record_bridge_step` 이 인자·사유까지 담아 기록한다. 이
    함수는 그 경로가 하나도 남기지 못했을 때만 돈다(구 task, 단계 기록 실패). 이미 단계가 있으면
    **아무것도 하지 않는다** — 같은 조사가 두 벌로 보이면 그것대로 못 믿을 화면이 된다.

    실패는 흡수한다. 단계 기록은 답변 전달의 조건이 아니다(없으면 탭이 빌 뿐이다).
    """
    if not conversation_id or not task_id:
        return 0
    pg = _pg()
    if pg is None:
        return 0
    try:
        with pg.cursor() as cur:
            # 호출 시점 기록이 이미 있으면 이관하지 않는다(중복 방지).
            cur.execute(
                "SELECT 1 FROM agent_runtime.steps "
                "WHERE conversation_id = %s AND run_id = %s LIMIT 1",
                (conversation_id, task_id))
            if cur.fetchone():
                return 0
            cur.execute(
                "SELECT tool, datasource_key, schema_name, rows_returned, bytes_out, "
                "       latency_ms, outcome, detail, created_at "
                "FROM agent_runtime.tool_call_usage "
                "WHERE task_id = %s ORDER BY id ASC", (task_id,))
            rows = cur.fetchall() or []
            # 브리지 자체의 진행 도구는 조사 내역이 아니다 — 사용자에게는 소음이다.
            # 집합은 `_BRIDGE_PROGRESS_TOOLS` 정본을 쓴다: 진행 중 표시(`_bridge_live_steps`)와
            # 갈리면 제출 순간 단계 목록이 바뀌어 사용자가 "단계가 사라졌다" 고 본다.
            n = 0
            for r in rows:
                tool = str(r[0] or "")
                if tool in _BRIDGE_PROGRESS_TOOLS:
                    continue
                n += 1
                summary = {"rows_returned": int(r[3] or 0), "bytes_out": int(r[4] or 0),
                           "outcome": str(r[6] or "")}
                args = {k: v for k, v in (("datasource", r[1]), ("schema_name", r[2])) if v}
                # 원장에는 인자가 거의 없어 문구가 뭉뚱그려지지만, **사유 칸까지 비우지는
                # 않는다** — 도구의 목적에서 파생한 근거라도 있어야 "왜 이 단계가 있었나" 가
                # 읽힌다. 출처를 'derived' 로 남겨 LLM 이 말한 사유와 구분된다.
                #
                # ⚠ `work_source` 는 **`'bridge-ledger'` 여야 한다**(문자열 그대로).
                #   `_conv_store._BRIDGE_LEDGER_WORK_SOURCE` 가 이 값을 "끝난 답변의 사후
                #   기록" 표식으로 소비해, 진행 중 run 추론에서 제외한다. 여기를 다른 값으로
                #   바꾸면 제외가 조용히 무효가 되어 **끝난 답변이 '진행 중' 으로 보인다**.
                #   (호출 시점 기록은 external-ai/derived 라 그 추론에 정상 포함된다.)
                work_text, reason_text = _bridge_derived_narration(tool, args)
                cur.execute(
                    "INSERT INTO agent_runtime.steps "
                    "(conversation_id, run_id, step_index, action, tool, intent, "
                    " work_text, work_source, reason_text, reason_source, args_json, "
                    " result_summary_json, error_text, created_at) "
                    "VALUES (%s,%s,%s,'tool',%s,%s,%s,'bridge-ledger',%s,'derived',%s,%s,%s,%s)",
                    (conversation_id, task_id, n, tool,
                     f"{tool}: {work_text or tool}"[:255], work_text or None, reason_text or None,
                     json.dumps(args, ensure_ascii=False),
                     json.dumps(summary, ensure_ascii=False),
                     (str(r[7] or "") if str(r[6] or "") not in ("ok", "") else None), r[8]))
        pg.commit()
        return n
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[bridge] 실행 단계 기록 실패 task=%s: %r", task_id, exc)
        return 0
    finally:
        try:
            pg.close()
        except Exception:
            pass


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


def _deliver_web_bridge_answer(conn, task_id: str, account: dict[str, Any], answer: str,
                               *, title: str = "") -> bool:
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
                "SELECT ConversationId, Origin, ProductId, ProductMode, Question "
                "FROM WebAiTasks WHERE TaskId=%s", (task_id,))
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return False
        conversation_id, origin = row[0], str(row[1] or "")
        if origin != "web" or not conversation_id:
            return False
        question = row[4]

        # 지연 import — 라우터 import 시점 순환 회피(다른 핸들러의 `import agent_core` 와 동형).
        from modules.memory import save_memory_message as _save_msg

        # 답변 말풍선의 **제품 귀속 각인**(msg-speaker-attribution). 기존 경로가 답변마다 굳히는
        # 값이고, 빠지면 FE 가 컴포저의 *현재* 제품 칩으로 폴백해 그린다 — 사용자가 제품을 바꾸는
        # 순간 과거 답변의 발화자까지 소급 변경된다. 각인은 답변 시점에 확정되는 사실이다.
        # 조회 실패는 fail-open(각인만 생략) — 각인이 답변 저장을 막게 두지 않는다.
        # `run_id` 를 task_id 로 잡는다 — 프런트가 `meta.run_id` 로 단계를 조회하므로,
        # 이 키가 없으면 단계를 기록해도 화면에서 찾지 못한다.
        _meta: dict[str, Any] = {"bridge": {"task_id": task_id, "origin": "web"},
                                 "run_id": task_id}
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

        # 개인 AI 가 맥락 제목을 제안했으면 승급시킨다(대화 제목 2단 중 두 번째 축).
        #
        # **답변이 실제로 화면에 앉은 뒤에** 한다(codex REV-20260828T040000 P2): 앞에 두면
        # 저장이 실패했을 때 대기 말풍선은 그대로인데 사이드바 제목만 바뀌어, 답변이 도착한
        # 것처럼 보이는 부분 상태가 굳는다(재제출은 409 라 스스로 풀리지도 않는다).
        #
        # `supersedes` 에 원 질문을 넘겨 **우리가 붙인 질문 기반 제목**만 갱신 대상이 되게 한다 —
        # 사용자가 손으로 바꾼 제목은 답변이 도착해도 그대로 둔다.
        if str(title or "").strip():
            try:
                applied = app._conv_apply_auto_topic(
                    conn, str(conversation_id), title, max_len=256, supersedes=question)
                if applied:
                    logging.getLogger(__name__).info(
                        "[bridge] 대화 제목 갱신 task=%s conv=%s title=%r",
                        task_id, conversation_id, applied)
            except Exception as exc:
                # 제목은 부가 정보다 — 실패가 답변 전달을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "[bridge] 대화 제목 갱신 실패 task=%s: %r", task_id, exc)

        # 개인 AI 의 조사 내역을 'AI 추론' 탭에 보이도록 단계로 옮긴다(사용자 제보 2026-08-27).
        _steps = _materialize_bridge_steps(str(conversation_id), task_id)
        if _steps:
            logging.getLogger(__name__).info(
                "[bridge] 실행 단계 %d건 기록 task=%s", _steps, task_id)

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

    # 연결이 끊겼던 동안 보관된 질문을 지금 대기열에 올린다(최근 1건).
    _promote_deferred_for(conn, account_id)

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
    canceled: list[str] = []
    drained = False
    # 대기에 들어가기 **전에** 보류 질문을 올린다(최근 1건). 루프 안에 두면 매 0.5초마다
    # 같은 판정을 반복하고, 승격은 연결 성립 시점에 한 번이면 충분하다 — 대기 중 새로
    # 생기는 질문은 이미 연결된 상태이므로 처음부터 `open` 으로 들어온다.
    _promote_deferred_for(conn, account_id)
    # feature-0045: 이 대기를 **관측 가능**하게 만든다. 종전엔 무중단 스파인의 pre-drain
    # 게이트가 이 대기를 전혀 보지 못해, 개인 AI 가 붙어 있는 replica 를 "조용하다"고 읽고
    # 그대로 내렸다. 다만 대기는 **기다릴 대상이 아니라 비울 대상**이다(아래 드레인 분기).
    with _drain.waiting():
        while True:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT TaskId, Question, CreatedAt FROM WebAiTasks "
                    "WHERE AccountId=%s AND Origin='web' AND Status='open' AND " + _CLAIMABLE_SQL +
                    " ORDER BY CreatedAt ASC LIMIT 20", (account_id,))
                found = list(cur.fetchall() or [])
                # **내가 점유 중인데 취소된 작업** — 사용자가 중단을 눌렀거나 새 질문으로 갈아탔다.
                #
                # 왜 여기서 보는가(2026-08-28): 취소를 알릴 별도 도구를 만들면 러너가 채널을 하나 더
                # 돌봐야 하고, 그 주기가 사람마다 달라 **환경 차이**가 된다(P0-J 가 폴링을 버린 이유와
                # 같다). 이 루프는 이미 0.5초마다 재조회하므로, 취소를 그 **두 번째 조건**으로 넣으면
                # 새 질문과 똑같이 즉시 인지된다 — 도구 개수도 늘지 않는다.
                #
                # 점유자 스코프(`ClaimedBy=%s`)로 좁힌다: 남이 집은 작업의 취소는 내 하차 사유가 아니다.
                cur.execute(
                    "SELECT TaskId FROM WebAiTasks "
                    "WHERE AccountId=%s AND Origin='web' AND Status=%s AND ClaimedBy=%s "
                    "ORDER BY CreatedAt ASC LIMIT 20",
                    (account_id, _STATUS_CANCELED, account_id))
                canceled = [str(r[0]) for r in (cur.fetchall() or [])]
                if canceled:
                    # **한 번만 알린다** — 알린 뒤 점유를 놓는다(2026-08-28 라이브 실측 P1).
                    #
                    # 놓지 않으면 이 SELECT 가 같은 행을 **영원히** 다시 집는다. 그러면
                    # `timed_out = not canceled` 가 항상 False → 대기가 즉시 반환 → 호출측이
                    # 간격 없이 다시 부른다. 그것이 정확히 P0-J 가 없애려던 tight loop 이고,
                    # 이번엔 **우리 서버를 향한** 것이다.
                    #
                    # 실측(라이브): 취소 1건이 남은 상태에서 러너가 초당 수십 회 재호출 →
                    # 20라운드 만에 spin 가드로 사망 → **그 사이 처리 중이던 다른 질문의 답변이
                    # 통째로 유실**됐다. 조용한 낭비가 아니라 사용자 대면 손실이었다.
                    #
                    # `Status='canceled'` 는 **그대로 둔다** — `submit_answer` 409 집행과
                    # 화면의 `canceled` 국면이 그 값에 걸려 있다. 놓는 것은 점유뿐이다.
                    marks = ",".join(["%s"] * len(canceled))
                    cur.execute(
                        f"UPDATE WebAiTasks SET ClaimedBy=NULL, ClaimedClient=NULL "
                        f"WHERE AccountId=%s AND Status=%s AND TaskId IN ({marks})",
                        (account_id, _STATUS_CANCELED, *canceled))
            finally:
                cur.close()
            # ⚠ 커밋(또는 롤백)이 없으면 이 커넥션의 트랜잭션 스냅샷이 고정돼 **새로 들어온 행이
            #   영원히 안 보인다**(REPEATABLE READ). 대기 루프에서 가장 빠지기 쉬운 함정이다.
            try:
                conn.commit()
            except Exception:
                pass
            if found or canceled or time.perf_counter() >= deadline:
                break
            # feature-0045: 이 replica 가 곧 교체된다(드레인). 여기서 계속 붙들고 있으면 그
            # 연결이 recreate 로 **끊기고**, 클라이언트에겐 오류로 보인다. 대신 지금 정상
            # 반환하면 호출측이 곧바로 다시 부르고, 그 호출은 엣지가 살아 있는 replica 로
            # 보낸다 — 사용자 관점에서 아무 일도 일어나지 않은 것과 같다.
            if _drain.is_draining():
                drained = True
                break
            if await request.is_disconnected():
                # 이미 끊긴 클라이언트를 위해 계속 두드리지 않는다.
                return JSONResponse({"count": 0, "task_ids": [], "requests": "",
                                     "canceled_task_ids": [],
                                     "timed_out": False, "disconnected": True})
            await asyncio.sleep(_WAIT_TICK_SEC)

    waited_ms = int((time.perf_counter() - t0) * 1000)
    if not found:
        # 빈 대기도 원장에 남긴다 — 남기지 않으면 "AI 가 붙어 있었는가" 를 사후에 알 수 없다.
        _safe_record(account, ctx, tool="wait_for_request", outcome="ok",
                     latency_ms=waited_ms, rows_returned=0)
        # 새 질문은 없지만 **취소는 있을 수 있다** — 그 경우 `timed_out` 이 아니다(기다림이
        # 끝난 이유가 시간이 아니라 사건이다). 러너는 이 목록을 보고 해당 작업을 하차시킨다.
        body = {"count": 0, "task_ids": [], "requests": "",
                "canceled_task_ids": canceled,
                "timed_out": not canceled, "waited_ms": waited_ms,
                "next": ("취소된 작업을 중단하세요(제출해도 409 로 거절됩니다)."
                         if canceled else
                         "곧바로 다시 wait_for_request 를 호출하면 된다(간격 불필요).")}
        if drained and not canceled:
            # feature-0045: **오류가 아니다.** 배포로 이 replica 가 교대하는 중이라는 사실을
            # 그대로 알린다 — 호출측이 이것을 실패로 읽으면 백오프에 들어가 그만큼 인지가
            # 늦어진다. 취소가 함께 있으면 그쪽이 더 급한 신호이므로 문구를 덮지 않는다.
            body["draining"] = True
            body["timed_out"] = True
            body["next"] = ("이 서버 인스턴스가 배포 교대 중이라 대기를 정상 종료했습니다. "
                            "곧바로 다시 호출하면 다른 인스턴스가 이어받습니다(간격 불필요).")
        return JSONResponse(body)

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
        # 새 질문과 취소가 같은 tick 에 걸릴 수 있다(사용자가 갈아탔을 때가 정확히 그렇다).
        # 둘 다 실어야 러너가 "옛 것을 버리고 새 것을 집는" 한 번의 동작으로 처리한다.
        "canceled_task_ids": canceled,
        "timed_out": False, "waited_ms": waited_ms,
        "next": "claim_request 로 점유한 뒤 처리하세요."
                + (" 취소된 작업은 중단하세요." if canceled else ""),
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

        # `RequestedModel`·`ReasoningLevel` 은 **읽지 않는다** (P0-T, 사용자 결정 2026-08-28) —
        # 웹에서 그 값을 고를 수 없게 됐고, 과거 행에 남은 값을 지금 전달하면 사용자가 이번에
        # 고르지도 않은 요구가 답변에 반영된 척하게 된다. 컬럼은 이력으로 남긴다.
        cur.execute(
            "SELECT Question, ConversationId, ProductId, CreatedAt, AttachmentIds, "
            "RoleId, ProductMode "
            "FROM WebAiTasks WHERE TaskId=%s AND AccountId=%s", (task_id, account_id))
        row = cur.fetchone() or ("", None, None, None, None, None, None)
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

    # 운영자가 설정한 5단계 시스템 프롬프트 + 이 요청이 바라보는 제품·데이터소스.
    # 둘 다 빠져 있어서, 브리지 답변만 다른 규칙으로·어디를 보는지 모른 채 만들어졌다.
    system_prompt = _bridge_system_prompt(
        conn, product_id=row[2], role_id=row[5], account_id=account_id,
        product_mode=str(row[6] or "pinned"), conversation_id=conversation_id)
    scope = _bridge_product_scope(conn, row[2])
    # 사용자에게 "지금 처리 중" 을 보인다(제보 2026-08-27 — 상황을 알 방법이 없었다).
    _mark_bridge_working(conn, task_id, conversation_id)
    return JSONResponse({
        "task_id": task_id,
        "question": marked,
        "conversation_context": marked_history,
        "product_id": int(row[2]) if row[2] is not None else None,
        "asked_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3] or ""),
        "attachments": attachments,
        # AI 가 이 지침을 **답변 생성의 시스템 프롬프트로** 써야 한다(단순 참고가 아니다).
        "system_prompt": system_prompt,
        "scope": scope,
        "next": ("조사 후 submit_answer 로 제출하세요. source_tasks 에 근거로 쓴 task_id 를 "
                 "선언합니다." + (
                     f" 이 질문에는 첨부 {len(attachments)}건이 있습니다 — "
                     f"read_task_attachment(task_id, attachment_id) 로 본문을 읽고 나서 답하세요."
                     if attachments else "")),
    })


# (P0-T, 2026-08-28) `_REASONING_INTENT` 와 `_requested_quality()` 는 제거됐다.
# 웹에서 모델·추론 강도를 고를 수 없게 됐으므로 전달할 요구 자체가 없다 — 남겨 두면 "언젠가
# 쓰이는 것처럼" 보이는 죽은 계약이 되고, 다음 사람이 그것을 근거로 조작면을 되살린다.
# 되돌리는 방법은 git 이력이지 주석 처리된 코드가 아니다.


def _mark_bridge_working(conn, task_id: str, conversation_id) -> bool:
    """대기 말풍선을 **'처리 중'** 으로 바꾼다. 점유 직후 1회.

    사용자 제보(2026-08-27): "AI 가 연결이 완수되었는지, 답변을 진행중인건지 알 방법이 없다."
    맞다 — 전송 직후의 안내는 "가져가면 표시됩니다" 에서 멈춰 있었고, 실제로 누가 가져갔는지는
    화면에 아무 흔적이 없었다.

    토스트가 아니라 **말풍선 본문을 바꾼다**: 토스트는 몇 초 뒤 사라지고 새로고침하면 없다.
    사용자가 알고 싶은 것은 "지금 어떤 상태인가" 이고, 그건 화면에 남아 있어야 한다.

    실패는 흡수한다 — 진행 표시는 편의이지 점유의 조건이 아니다.
    """
    if not conversation_id or not task_id:
        return False
    try:
        if not app._runtime_backend_is_pg():
            return False
        from shared.db import _pg_connect

        pg = _pg_connect()
        try:
            with pg.cursor() as cur:
                cur.execute(
                    "UPDATE agent_runtime.messages "
                    "SET content = %s "
                    "WHERE conversation_id = %s AND role = 'assistant' "
                    "  AND (meta_json -> 'bridge' ->> 'task_id') = %s "
                    "  AND (meta_json -> 'bridge' ->> 'placeholder') = 'true' "
                    "RETURNING id",
                    ("연결된 AI 가 이 질문을 가져갔습니다. 조사·작성 중입니다.\n\n"
                     "완료되면 이 자리에 답변이 표시됩니다.",
                     str(conversation_id), str(task_id)))
                hit = cur.fetchone() is not None
            pg.commit()
            return hit
        finally:
            pg.close()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[bridge] 진행 표시 갱신 실패 task=%s: %r", task_id, exc)
        return False


#: 대기 중으로 볼 수 있는 최근성. 서버 보류 상한(55초)의 두 배 남짓 — 한 번의 보류가 끝나고
#: 다시 들어가는 사이의 공백을 '멈춤' 으로 오판하지 않을 만큼만 넉넉하게.
_LISTENING_WINDOW_SEC = 150


def account_is_listening(account_id: int) -> bool:
    """이 계정의 AI 가 **지금 실제로 대기 중인가**.

    ## 왜 토큰만으로는 부족한가

    토큰은 DB 에 있고 러너는 프로세스다. 머신을 재시작하면 **러너만 사라진다** — 토큰은 그대로라
    화면은 계속 "연결됨" 이라 말하고, 사용자는 아무도 듣지 않는 곳에 질문을 보낸다
    (사용자 지적 2026-08-27: "머신이 재실행하여 첫 환경에서 다시 사용되었을 경우").

    `wait_for_request` 는 호출마다 원장에 남는다. 그 최근성이 곧 **살아 있는 귀**의 증거다 —
    추측이 아니라 관측이다.

    조회 실패는 False. 여기서 True 로 넘기면 "대기 중" 이라 말해 놓고 답이 오지 않는다 —
    연결 판정(fail-open)과 방향이 **반대**인 이유: 저쪽은 과잉 경고를, 이쪽은 헛된 기다림을 막는다.
    """
    if not account_id:
        return False
    try:
        pg = _pg()
        if pg is None:
            return False
        with pg.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM agent_runtime.tool_call_usage "
                "WHERE account_id = %s AND tool = 'wait_for_request' "
                f"  AND created_at > now() - interval '{_LISTENING_WINDOW_SEC} seconds' "
                "LIMIT 1", (int(account_id),))
            return cur.fetchone() is not None
    except Exception as exc:
        logging.getLogger(__name__).warning("[bridge] 대기 여부 조회 실패 account=%s: %r",
                                            account_id, exc)
        return False


def _bridge_system_prompt(conn, *, product_id, role_id, account_id,
                          product_mode: str, conversation_id) -> str:
    """이 요청에 적용될 **5단계 시스템 프롬프트**(전역·제품·역할·계정·개인).

    브리지는 `agent_core` 를 타지 않으므로 이 프롬프트가 통째로 빠져 있었다 — 운영자가 제품별·
    역할별로 설정한 지침이 브리지 답변에서만 사라졌고, 같은 질문이 경로에 따라 다른 규칙으로
    답해졌다(사용자 제보 2026-08-27).

    **서버가 조립해서 넘긴다.** 개인 AI 가 우리 프롬프트 체계를 알 리 없고, 안다 해도 DB 를 읽을
    수 없다. 그리고 조립 로직을 여기서 다시 쓰면 두 벌이 되어 갈린다 — 내부 경로와 **같은 함수**
    (`agent_core.compose_system_prompt`)를 부른다.

    실패는 빈 문자열. 프롬프트를 못 만들었다고 답변 자체를 막지는 않는다(막으면 운영자 설정
    하나가 서비스 전체를 세운다). 다만 로그로 남겨 조용히 사라지지 않게 한다.
    """
    try:
        import agent_core as _core

        return str(_core.compose_system_prompt(
            conn,
            product_id=int(product_id) if product_id else None,
            role_id=int(role_id) if role_id else None,
            account_id=int(account_id) if account_id else None,
            product_mode=str(product_mode or "pinned"),
            conversation_id=str(conversation_id or "") or None,
        ) or "")
    except Exception as exc:
        logging.getLogger(__name__).error(
            "[bridge] 시스템 프롬프트 조립 실패 conv=%s product=%s role=%s: %r",
            conversation_id, product_id, role_id, exc)
        return ""


def _bridge_product_scope(conn, product_id) -> dict[str, Any]:
    """이 요청이 바라보는 **제품과 데이터소스**. AI 가 무엇을 조사하는지 알아야 한다.

    도구 호출은 이미 `scoped_execution` 이 제품 경계로 묶는다(그건 집행). 여기서 주는 것은
    **인지**다 — 어떤 제품·어떤 DB 를 보고 있는지 모르면 AI 는 엉뚱한 스키마를 찾아 헤맨다.
    """
    out: dict[str, Any] = {"product_id": None, "product_key": None,
                           "product_name": None, "datasources": []}
    if not product_id:
        return out
    pid = int(product_id)
    out["product_id"] = pid
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT ProductKey, Name FROM WebProducts WHERE Id=%s LIMIT 1", (pid,))
            row = cur.fetchone()
        finally:
            cur.close()
        if row:
            out["product_key"] = str(row[0] or "") or None
            out["product_name"] = str(row[1] or "") or None
    except Exception as exc:
        logging.getLogger(__name__).warning("[bridge] 제품 조회 실패 id=%s: %r", pid, exc)
    try:
        # `_core` 는 모듈 전역이 아니다(순환 회피로 함수 지역 import 규약) — 여기서도 지역으로.
        import agent_core as _core

        out["datasources"] = list(_authz.allowed_datasource_labels(_core, conn, pid) or [])
    except Exception as exc:
        logging.getLogger(__name__).warning("[bridge] 데이터소스 조회 실패 id=%s: %r", pid, exc)
    return out


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
    """점유 lease 가 아직 유효한가 — `shared.bridge_tasks.claim_is_live` 로 위임.

    판정을 여기서 다시 쓰지 않는다: `_CLAIMABLE_SQL`(SQL 축)과 이 함수(파이썬 축)가 다른 값을
    보면 "목록에는 다시 뜨는데 읽기는 계속 되는" 어긋난 창이 생기고, 취소 정본까지 세 벌이 된다.

    호출측(`read_task_attachment`)은 이 시점에 `claimed_by` 를 이미 자기 계정과 대조했으므로
    여기서는 점유 시각만 넘긴다 — `claimed_by=1` 은 "점유자가 있다" 는 뜻의 자리표시다.
    """
    return _claim_is_live(1, claimed_at)


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
        # 실패한 시도도 단계로 남긴다 — 감추면 "첨부를 봤는가" 가 화면에서 판정 불가가 된다.
        _fw, _fr = _bridge_step_narration(body, {})
        _record_bridge_step(
            conn, {"conversation_id": conversation_id, "task_id": task_id},
            "read_task_attachment",
            {k: v for k, v in (("filename", filename), ("attachment_id", attachment_id)) if v},
            "", work=_fw, reason=_fr, error=str(exc)[:500],
            elapsed_ms=(time.perf_counter() - t0) * 1000)
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

    _att_work, _att_reason = _bridge_step_narration(body, {})
    _record_bridge_step(
        conn, {"conversation_id": conversation_id, "task_id": task_id},
        "read_task_attachment",
        {k: v for k, v in (("filename", str(res.get("filename") or "")),
                           ("attachment_id", int(res.get("attachment_id") or 0))) if v},
        str(res.get("text") or ""), work=_att_work, reason=_att_reason,
        elapsed_ms=(time.perf_counter() - t0) * 1000)

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

#: 취소된 요청의 제출을 거절할 때의 문구. 조기 반환과 확정 UPDATE 실패 **양쪽**이 같은 말을
#: 해야 한다 — 러너 입장에서 두 경로는 구분할 수 없는 같은 사건(사용자가 취소했다)이다.
_CANCELED_SUBMIT_MSG = (
    "사용자가 취소한 요청입니다. 이 답변은 저장·전달되지 않습니다. "
    "wait_for_request 의 canceled_task_ids 로 취소를 먼저 확인하면 "
    "불필요한 작업을 줄일 수 있습니다."
)


# ── 브리지 상태 술어 ─────────────────────────────────────────────────────────
#
# `_BRIDGE_CLAIM_LEASE_MIN`(30분 lease) · `_CLAIMABLE_SQL`(미점유 or lease 만료) ·
# `_STATUS_CANCELED` 는 파일 상단에서 `shared/bridge_tasks.py` 로부터 import 한다.
#
# 왜 여기서 정의하지 않는가(2026-08-28): 같은 술어를 `routers/conversations.py` 의 취소·
# supersede 경로도 판정해야 한다. 두 라우터가 각자 조립하면 "목록엔 없는데 취소는 안 되는"
# 류의 어긋남이 생기고, **갈리는 순간 느슨한 쪽이 사용자가 보는 진실**이 된다(P0-R 재발 방지).
# 지역 별칭은 기존 호출부·계약 테스트가 참조하는 이름이며 값은 shared 정본과 동일하다.


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
    # 단계 narration(무엇을·왜)은 조사 인자가 아니다 — 실행 전에 걷어낸다(내부 경로와 동형).
    narr_work, narr_reason = _bridge_step_narration(body, arguments)
    # `execute_tool` 이 `arguments` 에서 `datasource` 를 pop 한다 — 실행 뒤에 읽으면 항상 빈 값이
    # 되어 추출 원장의 datasource 추적이 통째로 죽는다(codex P2). 실행 전에 붙잡는다.
    requested_ds = str(arguments.get("datasource") or "") or None
    # 단계에 남길 인자 사본. 실행이 `datasource` 를 pop 하고 내부 out-param(`_stats_out`)을
    # 심으므로, **실행 전 사용자 인자**를 그대로 굳혀야 화면 문구가 조사 대상과 일치한다.
    step_args = dict(arguments)
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
        # 실패한 조사도 단계다 — 감추면 "왜 답이 늦었나/왜 이 결론인가" 가 화면에서 사라진다.
        _record_bridge_step(conn, task, tool_name, step_args, "", work=narr_work,
                            reason=narr_reason, error=str(exc)[:500],
                            elapsed_ms=(time.perf_counter() - t0) * 1000)
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
            _record_bridge_step(
                conn, task, tool_name, step_args, "", work=narr_work, reason=narr_reason,
                error=f"반환 행수 {got:,}행이 건당 상한 {cap:,}행을 넘어 결과를 돌려주지 않았습니다.",
                elapsed_ms=(time.perf_counter() - t0) * 1000)
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

    # 웹 대화에서 온 질문이면 이 조사를 '실행 단계' 로 남긴다(화면의 「AI 추론」 탭).
    # 각인본(`marked`)이 아니라 `rendered` 를 넘긴다 — 단계 미리보기는 사람이 읽는 자리다.
    _record_bridge_step(conn, task, tool_name, step_args, rendered, work=narr_work,
                        reason=narr_reason, elapsed_ms=(time.perf_counter() - t0) * 1000)

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


def _bridge_phase(status: str, claimed_by: Any, submitted: bool, connected: bool,
                  listening: bool = True) -> str:
    """국면을 **한 단어**로 — 서버가 정한다(프런트가 조합하면 화면마다 갈린다).

    | phase | 뜻 |
    |---|---|
    | `canceled` | 사용자가 중단했거나 새 질문으로 갈아탔다. **답변은 오지 않는다** |
    | `expired` | 연결 후 최근 1건만 승격돼 이 질문은 밀렸다. **답변은 오지 않는다** |
    | `done` | 제출됨 |
    | `working` | 누군가 가져가 처리 중 |
    | `deferred` | 아직 연결이 없어 보관 중 — 연결하면 이 질문부터 올라간다 |
    | `waiting` | 연결도 있고 러너도 붙어 있다 — 곧 집힌다 |
    | `not_listening` | 토큰은 살아 있는데 **대기 중인 러너가 없다**(재부팅 등) |
    | `not_connected` | 연결된 AI 자체가 없다 — 기다리게 두지 않고 알린다 |

    `connected` 와 `listening` 은 **다른 사실**이다(TASK-20260828T060000 형제 cycle) — 토큰은
    DB 에 있고 러너는 프로세스에 있다. 머신을 재부팅하면 러너만 사라지는데, 그때 "대기 중" 이라
    말하면 사용자는 영원히 오지 않을 답을 기다린다.

    `canceled` 를 **맨 앞에** 둔다: 취소된 뒤에도 `ClaimedBy` 는 남아 있으므로 순서가 뒤면
    같은 행이 계속 `working` 으로 읽혀 화면이 "처리 중" 을 영원히 보여준다.

    `listening` 의 기본값이 True 인 이유: 관측하지 못했을 때 "러너가 없다" 고 단정하면 멀쩡히
    붙어 있는 사용자에게 매번 틀린 경고를 띄운다(연결 판정의 fail-open 과 같은 방향).
    """
    if str(status or "") == _STATUS_CANCELED:
        return "canceled"
    # 만료도 **종결**이다 — 답변은 오지 않는다. 여기서 안 걸러내면 토큰·러너가 살아 있다는
    # 이유로 `waiting` 이 반환되어, DB 는 끝났다는데 화면은 영원히 "대기 중" 을 그린다
    # (codex REV-20260828T070000 P2).
    if str(status or "") == _STATUS_EXPIRED:
        return "expired"
    if submitted or str(status or "") == "submitted":
        return "done"
    if claimed_by is not None:
        return "working"
    # 보류는 "연결이 없다" 와 같은 뜻이되, 질문이 **보관돼 있다**는 사실이 더 있다.
    if str(status or "") == _STATUS_DEFERRED:
        return "deferred"
    if not connected:
        return "not_connected"
    return "waiting" if listening else "not_listening"


#: 브리지 **진행** 도구 — 조사 내역이 아니므로 단계 표시에서 걸러낸다.
#:
#: `_materialize_bridge_steps`(제출 시 이관)와 `_bridge_live_steps`(진행 중 표시)가 **같은
#: 집합**을 써야 한다. 갈리면 제출 전후로 단계 목록이 달라져 사용자가 "단계가 사라졌다" 고 본다.
_BRIDGE_PROGRESS_TOOLS = frozenset({
    "wait_for_request", "list_open_requests", "claim_request", "submit_answer",
})

#: 진행 중 노출할 조사 단계 상한. 긴 조사에서 매 프레임 수백 행을 실어 나르지 않는다.
_BRIDGE_LIVE_STEPS_MAX = 40


def _bridge_live_steps(task_id: str) -> list[dict[str, Any]]:
    """개인 AI 가 **지금까지 호출한 도구**를 요약해 돌려준다(진행 중에도).

    종전에는 `_materialize_bridge_steps` 가 제출 시점에 일괄 이관해, 답변이 오기 전까지
    'AI 추론' 탭이 비어 있었다 — 사용자에게는 30분 동안 아무 일도 일어나지 않는 화면이었다.
    그런데 **그 AI 가 무엇을 조사했는지는 우리 안에 있다**(`tool_call_usage` 원장에 호출 즉시
    남는다). 이미 관측한 사실을 늦게 보여줄 이유가 없다.

    옮기는 것은 관측 사실뿐이다 — 어떤 도구를 · 어떤 스키마에 · 몇 행 · 얼마나 걸려.
    LLM 사고 과정은 없다(우리 밖에서 일어났다). **지어내면 그 순간 이 패널 전체가 못 믿을
    것이 된다** — `_materialize_bridge_steps` 가 그은 선을 여기서도 지킨다.

    브리지 자체의 진행 도구(wait·claim·submit)는 조사 내역이 아니므로 걸러낸다.
    실패는 흡수한다 — 단계 조회 실패가 상태 조회를 막지 않는다(없으면 빈 목록일 뿐이다).
    """
    if not task_id:
        return []
    try:
        pg = _pg()
        if pg is None:
            return []
        with pg.cursor() as cur:
            cur.execute(
                "SELECT tool, datasource_key, schema_name, rows_returned, latency_ms, "
                "       outcome, created_at "
                "FROM agent_runtime.tool_call_usage "
                "WHERE task_id = %s ORDER BY id ASC LIMIT %s",
                (task_id, _BRIDGE_LIVE_STEPS_MAX + len(_BRIDGE_PROGRESS_TOOLS)))
            rows = cur.fetchall() or []
        out: list[dict[str, Any]] = []
        for r in rows:
            tool = str(r[0] or "")
            if tool in _BRIDGE_PROGRESS_TOOLS:
                continue
            out.append({
                "tool": tool,
                "datasource": str(r[1] or ""),
                "schema": str(r[2] or ""),
                "rows": int(r[3] or 0),
                "latency_ms": int(r[4] or 0),
                "outcome": str(r[5] or ""),
                "at": r[6].isoformat() if hasattr(r[6], "isoformat") else "",
            })
        return out[:_BRIDGE_LIVE_STEPS_MAX]
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "[bridge] 진행 단계 조회 실패 task=%s: %r", task_id, exc)
        return []


#: SSE 를 붙들어 두는 **서버 고정** 상한(초).
#:
#: `_WAIT_MAX_HOLD_SEC`(55) 와 같은 값이지만 이유가 다르다. 저쪽은 프록시 타임아웃(60s)이고,
#: 여기는 **배포**다: `bin/deploy-web.sh` 의 pre-drain 이 `/livez` 의 `active_streams` 가 0 이
#: 되기를 최대 `DEPLOY_WEB_PREDRAIN_TIMEOUT`(기본 90s) 기다린 뒤 남은 스트림을 **끊는다**.
#: 브리지 대기는 최대 30분이라, 그동안 스트림을 붙들면 배포마다 replica 당 90초를 버리고
#: 그러고도 절단된다(fetch/getReader 는 자동 재접속이 없다). 55초로 끊고 프런트가 다시 붙으면
#: 배포 대기가 그 안에 들어가고 절단도 사라진다.
_BRIDGE_STREAM_MAX_HOLD_SEC = 55.0

#: 서버 **내부** 확인 간격. 클라이언트에 노출되지 않으므로 환경 차이를 만들지 않는다.
#: `_WAIT_TICK_SEC`(0.5) 보다 느슨하다 — 여기서 재는 것은 "질문 도착" 이 아니라 국면 전환이라
#: 0.5초 해상도가 필요 없고, 대화당 여러 스트림이 열릴 수 있어 DB 부하를 아낀다.
_BRIDGE_STREAM_TICK_SEC = 1.0


@router.get("/api/ai/bridge_stream")
async def bridge_stream(request: Request):
    """feature-0043(2026-08-28) — 브리지 진행 상황 **SSE**.

    ## 왜 폴링을 대체하는가

    종전 `bridge_status` 5초 폴링은 (a) 국면 전환이 최대 5초 늦고, (b) 진행 중 조사 내역이
    답변 전에는 보이지 않아 사용자에게는 "멈춘 화면" 이었다.

    새 스트리밍 스택을 만들지 않는다 — `app._sse_pack` · `app._counted_stream` ·
    `X-Accel-Buffering: no` 는 프롬프트 자동작성에서 이미 프로덕션 검증된 조합이다.
    `_counted_stream` 을 반드시 통과시킨다: 그것이 feature-0014 무중단 배포의 pre-drain
    게이트가 세는 카운터다. 빼먹으면 배포가 이 스트림을 **못 보고** 그냥 끊는다.

    ## 계약

    - **변한 것만** 보낸다(`phase` 전환 · 새 단계). 매 tick 전량을 보내면 클라이언트가
      스크롤을 흔들고 대역만 먹는다.
    - `_BRIDGE_STREAM_MAX_HOLD_SEC` 에 도달하면 `event: reconnect` 후 **정상 종료**한다 —
      오류가 아니다. 프런트는 곧바로 다시 붙는다(그 사이 도착한 변화는 첫 프레임이 담는다).
    - 종결 국면(`done` · `canceled`)에 도달하면 그 프레임을 보내고 닫는다.
    - 클라이언트가 끊으면 즉시 그만둔다(끊긴 응답을 위해 DB 를 두드리지 않는다).

    **웹 세션 인증**이다(외부 OAuth 토큰이 아니라) — 자기 계정이 연 web task 만 보인다.
    답변 **본문은 싣지 않는다**: 도착 사실만 알리고 화면은 대화를 다시 읽어 렌더한다.
    본문을 여기로 흘리면 각인 블록이 두 경로로 새어 규약이 갈린다(`bridge_status` 와 동일).
    """
    task_id = str(request.query_params.get("task_id") or "").strip()
    if not task_id:
        return app._json_error("task_id 가 필요합니다.", 400)

    # 인증·소유 확인은 **스트림을 열기 전에** 끝낸다. 제너레이터 안에서 하면 이미 200 +
    # SSE 헤더가 나간 뒤라 401/403 을 제대로 돌려줄 수 없다.
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        account_id = int(account.get("id") or 0)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT ConversationId FROM WebAiTasks "
                "WHERE TaskId=%s AND AccountId=%s AND Origin='web'",
                (task_id, account_id))
            row = cur.fetchone()
        finally:
            cur.close()
        if row is None:
            return app._json_error("task 를 찾을 수 없습니다.", 404)
        conversation_id = str(row[0] or "")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    async def event_stream():
        # 커넥션은 **스트림당 하나**를 유지하고 tick 마다 커밋해 스냅샷을 갱신한다.
        #
        # tick 마다 열고 닫으면 55초 스트림 하나가 커넥션을 55번 만든다 — 연결 비용이 조회
        # 비용보다 크고, 동시 대화가 늘수록 그 비용이 선형으로 붙는다. 하나를 들고 있는 편이
        # 총 부하가 낮다.
        #
        # ⚠ 대신 **커밋을 빠뜨리면 안 된다**: 커넥션을 오래 들고 있으면 트랜잭션 스냅샷이 고정돼
        #   상태 변화가 영영 안 보인다(REPEATABLE READ). `wait_for_request` 루프가 같은 이유로
        #   매 확인마다 커밋한다.
        last_phase = ""
        last_step_count = -1
        deadline = time.perf_counter() + _BRIDGE_STREAM_MAX_HOLD_SEC
        try:
            sconn = app._connect_memory()
        except Exception:
            # 커넥션을 못 열어도 스트림은 연다 — 다음 tick 에 다시 시도한다. 여기서 죽으면
            # 프런트는 SSE 불가로 판단해 폴링으로 내려가는데, 원인은 일시 장애일 뿐이다.
            sconn = None
        try:
            while True:
                if await request.is_disconnected():
                    return
                if sconn is None:
                    try:
                        sconn = app._connect_memory()
                    except Exception:
                        sconn = None
                snap = _bridge_stream_snapshot(sconn, task_id, account_id)
                if snap is None:
                    # task 가 사라졌다 = 미점유 상태로 취소되어 삭제됐다(취소 정본의 DELETE 갈래).
                    # 종결로 알리고 닫는다 — 없는 행을 계속 물으면 404 만 쌓인다.
                    yield app._sse_pack("phase", {"task_id": task_id, "phase": "canceled",
                                                  "conversation_id": conversation_id,
                                                  "answered": False, "delivered": False})
                    yield app._sse_pack("end", {"reason": "canceled"})
                    return

                if snap["phase"] != last_phase:
                    last_phase = snap["phase"]
                    yield app._sse_pack("phase", {**snap, "task_id": task_id,
                                                  "conversation_id": conversation_id})
                steps = snap["steps"]
                if len(steps) != last_step_count:
                    last_step_count = len(steps)
                    yield app._sse_pack("steps", {"task_id": task_id, "steps": steps})

                if snap["phase"] in ("done", "canceled"):
                    yield app._sse_pack("end", {"reason": snap["phase"]})
                    return
                if time.perf_counter() >= deadline:
                    # 오류가 아니다 — 배포 pre-drain 이 기다릴 수 있는 길이로 끊고, 프런트가 다시 붙는다.
                    yield app._sse_pack("reconnect", {"after_ms": 0})
                    return
                await asyncio.sleep(_BRIDGE_STREAM_TICK_SEC)
        finally:
            if sconn is not None:
                try:
                    sconn.close()
                except Exception:
                    pass

    return app.StreamingResponse(
        app._counted_stream(event_stream()),  # feature-0014: 무중단 배포 pre-drain 용 스트림 카운트
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _bridge_stream_snapshot(conn, task_id: str, account_id: int) -> dict[str, Any] | None:
    """SSE 한 tick 분의 상태. task 가 없으면 `None`(취소로 삭제된 것).

    `bridge_status` 와 **같은 필드**를 만든다 — 두 경로가 다른 모양을 주면 프런트가 전송 방식에
    따라 다르게 그리게 되고, 폴백(SSE 실패 → 폴링)이 화면을 바꿔 버린다.

    커넥션은 호출측(스트림)이 들고 있는 것을 받는다. 여기서 열면 tick 마다 연결이 생긴다.
    """
    if conn is None:
        # 일시 DB 장애로 스트림을 죽이지 않는다 — 다음 tick 에 다시 시도한다.
        # ⚠ `None` 은 "task 없음(=취소 삭제)" 이라는 뜻이므로 여기서 돌려주면 안 된다.
        #   돌려주면 DB 가 잠깐 흔들릴 때마다 사용자 화면이 "취소됨" 으로 확정된다.
        return {"phase": "waiting", "answered": False, "delivered": False,
                "connected": True, "listening": True, "steps": []}
    try:
        # 오래 들고 있는 커넥션의 트랜잭션 스냅샷을 푼다(없으면 새 상태가 영영 안 보인다).
        try:
            conn.commit()
        except Exception:
            pass
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT Status, ClaimedBy, SubmittedAt, Delivered FROM WebAiTasks "
                "WHERE TaskId=%s AND AccountId=%s AND Origin='web'",
                (task_id, account_id))
            row = cur.fetchone()
        finally:
            cur.close()
        if row is None:
            return None
        status = str(row[0] or "")
        submitted = bool(row[2]) or status == "submitted"
        claimed_by = row[1]
        # 연결·러너 여부는 **아직 안 집힌 국면에서만** 의미가 있다(그 판정만
        # `not_connected`/`not_listening` 으로 갈린다). 이미 누가 집었거나 끝난 뒤에는 물어볼
        # 이유가 없다 — tick 마다 도는 조회라 값이 싸지 않다.
        connected, listening = True, True
        if not submitted and claimed_by is None and status != _STATUS_CANCELED:
            try:
                c2 = conn.cursor()
                try:
                    connected = _store.account_has_live_token(c2, account_id)
                finally:
                    c2.close()
            except Exception:
                connected = True   # 판정 실패는 '연결됨' 으로(틀렸을 때 덜 성가신 방향)
            try:
                # 러너 기동 여부(형제 cycle TASK-20260828T060000). `bridge_status` 와 **같은
                # 함수**를 써야 폴링과 스트리밍이 같은 국면을 말한다.
                listening = account_is_listening(account_id)
            except Exception:
                listening = True
        return {
            "phase": _bridge_phase(status, claimed_by, bool(row[2]), connected, listening),
            "answered": submitted,
            "delivered": bool(row[3]),
            "connected": connected,
            "listening": listening,
            # 아직 아무도 안 집었으면 조사 내역이 있을 수 없다 — 매 tick 원장을 뒤지지 않는다.
            "steps": _bridge_live_steps(task_id) if claimed_by is not None else [],
        }
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "[bridge] 스트림 스냅샷 실패 task=%s: %r", task_id, exc)
        return {"phase": "waiting", "answered": False, "delivered": False,
                "connected": True, "listening": True, "steps": []}



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
                "SELECT Status, ClaimedBy, SubmittedAt, ConversationId, Delivered, ClaimedAt "
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
        # 연결된 AI 가 **있는가** — 없으면 사용자는 영원히 오지 않을 답을 기다린다.
        connected = False
        try:
            c2 = conn.cursor()
            try:
                connected = _store.account_has_live_token(c2, int(account.get("id") or 0))
            finally:
                c2.close()
        except Exception:
            connected = True   # 판정 실패는 '연결됨' 으로(틀렸을 때 덜 성가신 방향)
        listening = account_is_listening(int(account.get("id") or 0))
        return JSONResponse({
            "task_id": task_id,
            "status": status,
            "claimed": row[1] is not None,
            "claimed_at": row[5].isoformat() if hasattr(row[5], "isoformat") else None,
            "connected": connected,
            # 'connected' 와 'listening' 은 다른 사실이다 — 토큰은 DB 에, 러너는 프로세스에 있다.
            # 재부팅하면 러너만 사라지고, 그때 "대기 중" 이라 말하면 헛되이 기다리게 된다.
            "listening": listening,
            # 화면이 한 단어로 말할 수 있게 서버가 국면을 정한다(프런트가 조합하면 갈린다).
            # 판정은 `_bridge_phase` 한 곳 — 폴링(여기)과 스트리밍(`_bridge_stream_snapshot`)이
            # 각자 조합하면 전송 방식에 따라 화면이 달라져 폴백이 곧 UX 회귀가 된다.
            "phase": _bridge_phase(status, row[1], bool(row[2]), connected, listening),
            # `answered` 는 **제출됐다** 는 뜻이고, `delivered` 는 **대화에 실렸다** 는 뜻이다.
            # 둘을 합치면 저장 실패 시 화면엔 아무것도 없는데 "답변 도착" 이라 말하게 된다
            # (codex 재리뷰 P1). 프런트는 delivered=false 면 그 사실을 사용자에게 알린다.
            "answered": submitted,
            "delivered": delivered,
            "conversation_id": str(row[3] or ""),
            # 진행 중인 조사 내역(2026-08-28). 답변 전에도 "무엇을 보고 있는지" 를 말한다.
            "steps": _bridge_live_steps(task_id),
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
