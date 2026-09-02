"""feature-0012 P5b Final — profile 도메인 APIRouter (프로필 사용량/감사 조회).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any

import app
from shared.model_catalog import canonical_usage_model_sql

INCLUDE_ORDER = 130  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


def _visible_console_job_kinds(account) -> tuple[str, ...]:
    """이 계정에 노출할 콘솔 작업 종류 (TASK-20260902T160000).

    판정 규칙의 정본은 `shared.bridge_tasks` 다 — 워커도 같은 레지스트리를 읽으므로 목록·권한
    선언이 두 벌이 되면 반드시 갈린다. 여기서는 **권한 판정 함수만** 넘긴다(RBAC 헬퍼는 웹
    전용이라 워커가 import 하지 못한다).

    GET 과 PUT 이 **같은 함수**를 부르는 것이 요점이다. 한쪽만 필터하면 화면에서 사라진 항목이
    저장에서 되살아나거나(PUT 미필터), 보이는 항목을 저장하지 못한다(GET 만 필터).
    """
    from shared import bridge_tasks as _bt

    return _bt.visible_console_job_kinds(
        lambda code: app._account_has_permission(account, code))


@router.get("/api/profile/console-jobs")
def get_profile_console_jobs(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-20260902T110000: 콘솔·배경 작업 항목별 **모델·추론등급** 설정 조회.

    로그인만 필요하고 **본인 계정으로 스코프가 강제**된다(신규 권한 코드 0) — 읽는 것도 쓰는
    것도 `account["id"]` 뿐이라 계정 파라미터가 없다. 이 설정이 남의 것을 건드릴 표면 자체를
    만들지 않는다.

    ## 항목은 «이 계정이 실제로 열 수 있는 것» 만 (TASK-20260902T160000)

    목록은 `JOB_SPECS` 전량이 아니라 `visible_console_job_kinds` 가 추린 것이다 — 그 기능의
    집행 게이트를 통과할 수 없는 계정에게 설정칸을 보여 주면, 사용자는 모델을 고르고 저장까지
    한 뒤에도 그 작업이 영영 오지 않는 이유를 알 수 없다(화면은 「설정됨」이라고 말하는데
    기능 자체가 403 이다). 여기서 걸러 두는 편이 정직하다.

    필터는 **표시 축**이고 집행이 아니다 — 각 기능의 서버 게이트는 종전 그대로다. 이 필터가
    무엇을 통과시키든 권한 없는 계정이 그 기능을 부를 수는 없다.

    Returns:
        - `jobs`: **이 계정에 노출되는** 항목 목록(`JOB_SPECS` 순서, kind·label·origin·wired)
          + 저장된 model/effort + `available`(지금 연결된 러너가 그 모델을 주는가).
        - `runtimes`: 지금 러너가 신고한 `[{runtime, label, models[], efforts[]}]`. **화면의
          선택지는 이것뿐이다** — 우리가 아는 이름이 아니라 그 러너가 고를 수 있다고 말한
          이름만 고르게 해야, 없는 모델을 골라 실행이 실패하는 경로(P0-T)가 생기지 않는다.
        - `listening`: 러너가 지금 듣고 있는가. False 면 `runtimes` 가 비고, 화면은 저장된
          값을 **지우지 않고** 그대로 보여준다(연결이 끊겼다고 설정이 사라지면 안 된다).
    """
    from shared import bridge_tasks as _bt

    aid = int((account or {}).get("id") or 0)
    if aid <= 0:
        return app._json_error("계정 식별 실패", 403)
    prefs, profile = {}, {"capabilities": [], "listening": False}
    try:
        import oauth_store as _store

        cur = conn.cursor()
        try:
            prefs = _store.account_console_job_prefs(cur, aid)
            profile = _store.account_runner_profile(cur, aid)
        finally:
            cur.close()
    except Exception:
        # 설정 조회 실패는 화면을 막지 않는다 — 빈 설정으로 그린다(저장은 여전히 가능).
        logging.getLogger(__name__).warning("console-jobs prefs load failed", exc_info=True)
    caps = profile.get("capabilities") or []
    visible = _visible_console_job_kinds(account)
    jobs = []
    for kind in visible:
        spec = _bt.JOB_SPECS[kind]
        entry = prefs.get(kind) or {}
        resolved = _bt.resolve_console_job_request(kind, prefs, caps)
        jobs.append({
            "kind": kind,
            "label": spec.get("label") or kind,
            "origin": spec.get("origin") or "",
            "wired": bool(spec.get("wired")),
            "model": str(entry.get("model") or ""),
            "effort": str(entry.get("effort") or ""),
            # 「고른 모델을 지금 러너가 주는가」 — False 면 그 항목은 위임되지 않는다
            #  (사용자 결정 2026-09-02). 화면이 그 사실을 그 자리에서 말해야, 저장해 두고
            #  왜 분석이 안 도는지 모르는 상태가 만들어지지 않는다.
            "available": not resolved.get("blocked"),
            "effective_model": (f"{resolved.get('runtime')}:{resolved.get('model')}"
                                if resolved.get("model") and not resolved.get("blocked") else ""),
            "source": str(resolved.get("source") or ""),
        })
    runtimes = []
    for item in (caps if isinstance(caps, list) else []):
        if not isinstance(item, dict):
            continue
        rt = str(item.get("runtime") or "").strip()
        if not rt:
            continue
        def _opts(field: str) -> list[dict[str, str]]:
            out = []
            for opt in (item.get(field) or []):
                value = str((opt or {}).get("value") or "") if isinstance(opt, dict) else str(opt or "")
                label = str((opt or {}).get("label") or value) if isinstance(opt, dict) else value
                if value:
                    out.append({"value": value, "label": label})
            return out
        runtimes.append({"runtime": rt, "label": str(item.get("label") or rt),
                         "models": _opts("models"), "efforts": _opts("efforts")})
    return JSONResponse({"jobs": jobs, "runtimes": runtimes,
                         "listening": bool(profile.get("listening"))})


@router.put("/api/profile/console-jobs")
async def put_profile_console_jobs(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-20260902T110000: 콘솔·배경 작업 항목별 모델·추론등급 저장(본인 계정 전용).

    본문: `{"jobs": {"<job_kind>": {"model": "runtime:model", "effort": "medium"}, ...}}`.
    **보이는 항목은 통째 교체**다(부분 갱신 아님) — 화면이 그 항목 전체를 그리므로, 화면에
    없는 값이 서버에만 남으면 사용자가 그것을 지울 방법이 없다.

    ## 「보이는 항목」의 경계 (TASK-20260902T160000)

    교체 범위는 **이 계정에 노출되는 종류**뿐이다(`_visible_console_job_kinds` — GET 과 같은
    함수). 두 가지를 동시에 막는다:

    - **권한 없는 종류로 들어온 값은 버린다.** 화면이 그리지 않는 항목을 본문에 실어 보내도
      저장되지 않는다(표시만 감추고 저장은 열어 두면 게이트가 표시 장식이 된다).
    - **숨겨진 종류의 기존 설정은 지우지 않는다.** 「통째 교체」를 전체 집합에 적용하면, 권한이
      빠진 계정이 저장 버튼을 한 번 누르는 것만으로 예전에 고른 값이 조용히 증발한다 — 권한은
      되돌아올 수 있고 그때 설정은 돌아오지 않는다. 화면은 자기가 그린 것만 소유한다.

    저장 값은 **검증하지 않고 정규화만** 한다. 「지금 러너가 그 모델을 주는가」는 저장 시점이
    아니라 배급 시점의 질문이고(러너는 껐다 켜며 목록이 바뀐다), 저장 시점에 걸면 러너를 끈
    채로는 설정을 못 하게 된다.
    """
    from shared import bridge_tasks as _bt

    aid = int((account or {}).get("id") or 0)
    if aid <= 0:
        return app._json_error("계정 식별 실패", 403)
    try:
        body = await request.json()
    except Exception:
        body = None
    # ⚠ **깨진 본문을 「전부 비웠다」로 읽지 않는다.** 이 엔드포인트는 교체 의미라 빈 `jobs`
    #   가 정당한 입력이다([모두 기본값] 후 저장이 정확히 그것을 보낸다). 그래서 파싱 실패나
    #   `jobs` 키 부재를 `{}` 로 흘려보내면, **의도한 초기화와 사고를 서버가 구분할 수 없고**
    #   그 사고는 200 을 받고 조용히 설정을 지운다. 둘을 여기서 가른다:
    #   dict 본문 + dict `jobs` = 의도 / 그 외 = 거절.
    if not isinstance(body, dict) or not isinstance(body.get("jobs"), dict):
        return app._json_error("jobs 는 객체여야 합니다. (항목을 모두 비우려면 빈 객체 {} 를 보냅니다)", 400)
    payload = body["jobs"]
    visible = set(_visible_console_job_kinds(account))
    try:
        import oauth_store as _store

        cur = conn.cursor()
        try:
            # ⚠ baseline 은 **엄격판**으로 읽는다. lenient 판(`account_console_job_prefs`)은
            #   조회 실패를 `{}` 로 돌려주는데, 그것을 쓰기의 baseline 으로 삼으면 「보존할 것이
            #   없다」로 오인해 **숨겨진 항목을 지운 문서**를 쓰고 200 을 돌려준다 — 잃은 값이
            #   화면에 없던 것이라 사용자는 알아채지도 못한다. 모르는 상태 위에 쓰지 않는다.
            stored = _bt.read_console_job_prefs_strict(cur, aid)
            # 병합 규칙의 정본은 `shared.bridge_tasks` 다 — 정규화 → 가시성 필터 순서가
            # 그 안에 있다(순서가 뒤집히면 표기 변형이 숨긴 항목을 덮어쓴다).
            merged = _bt.merge_visible_console_job_prefs(stored, payload, visible)
            saved = _store.set_account_console_job_prefs(cur, aid, merged)
            conn.commit()
        finally:
            cur.close()
    except ValueError as exc:
        return app._json_error(str(exc), 400)
    except Exception:
        logging.getLogger(__name__).warning("console-jobs prefs save failed", exc_info=True)
        return app._json_error("설정을 저장하지 못했습니다.", 500)
    # 응답도 보이는 항목만 — 숨긴 종류의 이름·값을 되돌려주면 화면에서 감춘 것이 응답으로
    # 새고, 프런트가 그것을 다음 저장에 실어 보낼 수도 있다.
    return JSONResponse({"saved": True,
                         "jobs": {k: v for k, v in saved.items() if k in visible}})


@router.get("/api/profile/usage/conversations")
def profile_usage_conversations(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0263: 본인 사용량 차트 클릭 → 본인 대화목록(작업 화면 프로필 모달).

    로그인만 필요(profile_llm_usage 와 동일 — 본인 소유 대화로 범위 강제, 신규 RBAC 0).
    owner_account_id = 로그인 계정으로 INNER 필터 → 타인 대화 노출 불가.
    """
    aid = int(account.get("id") or 0)
    if aid <= 0:
        return app._json_error("계정 식별 실패", 403)
    p = app._parse_usage_conv_params(request)
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("profile_usage_conversations: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        # 본인 범위 강제 — role/account_id 파라미터 무시(권한 상승 차단), model/day 만 적용.
        items, truncated = app._query_usage_conversations(
            pg, days=p["days"], model=p["model"], account_ids=None,
            day_label=p["day_label"], gran=p["gran"], owner_account_id=aid,
            owner_is_null_ok=False,
        )
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return JSONResponse({"items": items, "truncated": truncated,
                         "filter": {"days": p["days"], "gran": p["gran"], "model": p["model"], "day_label": p["day_label"]},
                         "scope": "self"})

@router.get("/api/profile/usage")
def profile_llm_usage(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0184: 본인 LLM 사용량 — 로그인 사용자 자신의 토큰/모델/요청 집계(간소판).

    admin_llm_usage(console.usage.read, admin 전용) 의 본인-범위 축소판. owner_account_id =
    로그인 계정으로 강제하고, 계정/역할 enrich·추정 비용은 제외한다(일반 사용자 화면에 단가
    비노출). 별도 RBAC 권한 없이 로그인만 요구 — 본인 소유 대화의 usage 로만 한정되므로
    권한 카탈로그 변경이 없다. 프로필 '사용 내역' 탭에서 사용.
    """
    aid = int(account["id"])
    try:
        days = int(request.query_params.get("days", "30"))
    except Exception:
        days = 30
    days = max(1, min(365, days))
    gran = request.query_params.get("gran", "day").lower()
    if gran not in app._USAGE_GRAN:
        gran = "day"
    gran_cfg = app._USAGE_GRAN[gran]
    bucket_expr = f"to_char(date_trunc('{gran}', u.created_at), '{gran_cfg['fmt']}')"
    bucket_limit = gran_cfg["limit"]
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("profile_usage: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        win = f"now() - interval '{days} days'"
        # 본인 소유 대화로 한정 (INNER JOIN: owner 매칭 안 되는 insight/시스템 호출은 제외).
        base = (
            "FROM agent_runtime.llm_usage u "
            "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
            f"WHERE u.created_at >= {win} AND c.owner_account_id = %s"
        )
        # usage-metric-charts: 캐시 축(0056). 첫 질의에서 컬럼 실재를 판정해 나머지 질의가 공유한다
        #   — 관리 화면(admin_usage)과 같은 규약이라 두 화면의 지표 구성이 어긋나지 않는다.
        _cr, _cw = app._usage_cache_exprs("u")
        with pg.cursor() as cur:
            if not app._usage_cache_exec(cur, pg, lambda cr, cw: (
                "SELECT COALESCE(count(*),0), COALESCE(sum(u.prompt_tokens),0), "
                "COALESCE(sum(u.completion_tokens),0), COALESCE(sum(u.total_tokens),0), "
                f"COALESCE(count(distinct u.run_id),0), "
                f"COALESCE(sum({cr}),0), COALESCE(sum({cw}),0) {base}"
            ), (aid,), alias="u"):
                _cr, _cw = "0", "0"
            t = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0)
            totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                      "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                      "requests": int(t[4]),
                      "cache_read_tokens": int(t[5] or 0), "cache_write_tokens": int(t[6] or 0)}
            # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(hover 표시). 본인 범위라 owner enrich 불요.
            # usage-model-canonical: 실 서빙 모델을 canonical family 로 접어 개인 사용량 도넛의 중복 분점
            # 해소 + admin 과 동일 규칙. model==resolved_model==canonical 로 채워 드릴다운 필터
            # (_query_usage_conversations, canonical)와 클릭 키가 정합(프론트 무변경).
            _canon_u = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")
            # usage-metric-charts(2026-08-13): 캐시 인지 비용 — 관리 화면과 **같은 식**이어야 개인
            #   사용량과 전체 집계가 어긋나지 않는다. 0056 미적용 DB 는 리터럴 0 표현식으로 폴백.
            _cr, _cw = app._usage_cache_exprs("u")
            cur.execute(
                f"SELECT {_canon_u} AS m, count(*), "
                f"sum(u.total_tokens), count(distinct u.run_id), sum(u.prompt_tokens), sum(u.completion_tokens), "
                f"sum({_cr}), sum({_cw}) {base} "
                f"GROUP BY {_canon_u} "
                "ORDER BY 3 DESC NULLS LAST LIMIT 50",
                (aid,),
            )
            by_model = [{"model": r[0], "resolved_model": r[0], "calls": int(r[1]),
                         "total_tokens": int(r[2] or 0), "requests": int(r[3] or 0),
                         "cache_read_tokens": int(r[6] or 0), "cache_write_tokens": int(r[7] or 0),
                         "cost_usd": app._estimate_llm_cost_usd(r[0], int(r[4] or 0), int(r[5] or 0),
                                                                int(r[6] or 0), int(r[7] or 0))}
                        for r in (cur.fetchall() or [])]
            cur.execute(
                f"SELECT {bucket_expr} AS b, count(*), sum(u.total_tokens), "
                f"sum(u.prompt_tokens), sum(u.completion_tokens), count(distinct u.run_id), "
                f"sum({_cr}), sum({_cw}) {base} "
                f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}",
                (aid,),
            )
            # usage-metric-charts: requests 는 모델로 나눌 수 없어(한 요청이 모델 횡단) 버킷 총계를
            #   따로 싣는다 — 프론트가 그 지표에서만 단일 막대로 그린다(관리 화면과 동일 규약).
            by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0),
                       "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0),
                       "requests": int(r[5] or 0),
                       "cache_read_tokens": int(r[6] or 0), "cache_write_tokens": int(r[7] or 0)}
                      for r in (cur.fetchall() or [])]
            cur.execute(
                f"SELECT {bucket_expr} AS b, {_canon_u}, sum(u.total_tokens), "
                f"sum(u.prompt_tokens), sum(u.completion_tokens), sum({_cr}), sum({_cw}), count(*) "
                f"{base} AND {bucket_expr} IN (SELECT {bucket_expr} {base} "
                f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) GROUP BY 1, 2 ORDER BY 1",
                (aid, aid),
            )
            by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                             "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0),
                             "cache_read_tokens": int(r[5] or 0), "cache_write_tokens": int(r[6] or 0),
                             "calls": int(r[7] or 0),
                             "cost_usd": app._estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0),
                                                                    int(r[5] or 0), int(r[6] or 0))}
                            for r in (cur.fetchall() or [])]
            # TASK-0263: 본인 총 추정 비용(모델별 합).
            totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return JSONResponse({
        "window_days": days,
        "granularity": gran,
        "totals": totals,
        "by_model": by_model,
        "by_day": by_day,
        "by_day_model": by_day_model,
    })

@router.get("/api/profile/audits")
def list_profile_audit_events(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): 작업 화면 profile drawer 의 본인 audit row 조회.

    권한: `audit.read.own` 또는 `audit.read.any`. **backend 가 scope="own" 강제** —
    `.any` 보유자도 본인 row 만 조회 (admin 콘솔 `GET /api/admin/audits` 와 분리).
    Codex outside voice C2 — `.any` 가 drawer 에서 전체 audit 보이는 위험 차단.

    Query params: action_code / from_at / to_at / q / cursor / limit (admin endpoint 와 동일 schema,
    actor_account_id / actor_type 는 본인 한정이라 무시).

    Response: `{items: [...], next_cursor: <id>|None, scope: 'own'}`.
    """
    if not (
        app._account_has_permission(account, "audit.read.own")
        or app._account_has_permission(account, "audit.read.any")
    ):
        return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
    params = app._audit_parse_filter_params(request)
    cursor_id = app._audit_parse_cursor(params["cursor"])
    limit = app._audit_clamped_limit(params["limit"])
    # TASK-0089 (Codex C2): scope="own" 강제 — .any 보유자도 본인 row 만.
    where_clause, args = app._audit_compose_where(
        scope="own",
        account_id=int(account["id"]),
        params=params,
        cursor_id=cursor_id,
    )
    sql = (
        "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
        "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
        "RemoteAddr, UserAgent, RequestId, OccurredAt "
        f"FROM WebAuditEvents{where_clause} "
        "ORDER BY Id DESC LIMIT %s"
    )
    args.append(int(limit) + 1)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, tuple(args))
        rows = cur.fetchall() or []
    finally:
        cur.close()
    has_more = len(rows) > limit
    items = [app._audit_row_to_dict(r) for r in rows[:limit]]
    next_cursor = str(items[-1]["id"]) if has_more and items else None
    return JSONResponse({"items": items, "next_cursor": next_cursor, "scope": "own"})

@router.get("/api/profile/audits/{event_id}")
def get_profile_audit_event(event_id: int, request: Request) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): profile drawer audit detail.

    `.own` 강제 (Actor = self — TASK-0293 Actor-only) — profile drawer 는 본인이 수행한
    행위만. 권한 부족 시 무조건 404 (byte-equal, metadata leak 차단).
    """
    if event_id <= 0:
        return app._json_error("invalid event_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not (
            app._account_has_permission(account, "audit.read.own")
            or app._account_has_permission(account, "audit.read.any")
        ):
            return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
        # TASK-0089: .own 강제 (admin endpoint 의 scope dependency 제거).
        cond, scope_args = app._audit_build_self_filter_sql(int(account["id"]))
        where_clause = f" WHERE Id = %s AND {cond}"
        args: list[Any] = [int(event_id)]
        args.extend(scope_args)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId, OccurredAt "
                f"FROM WebAuditEvents{where_clause} LIMIT 1",
                tuple(args),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return app._json_error("audit event not found", 404)
        return JSONResponse({"item": app._audit_row_to_dict(row), "scope": "own"})
    finally:
        conn.close()
