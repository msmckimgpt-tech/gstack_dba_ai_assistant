"""feature-0012 P5b Final — admin_usage 도메인 APIRouter (LLM 사용량/비용 집계 + 사용량 대화목록).

MIXED 도메인: admin_llm_usage(RP require_permission console.usage.read) + admin_usage_conversations
(AO get_current_account + 본문 _account_has_permission 2-perm 검사). 동반 테스트
(test_usage_conversations.py)가 핸들러 직접호출(account/conn 명시) + app.<helper> monkeypatch
(_query_usage_conversations·_usage_account_ids_for_role)를 쓰므로, 본 라우터는 **uniform
`import app`+호출시 `app.X` 동적 속성 접근**으로 작성한다(import-time 복사 아님 → monkeypatch 보존).
DI seam(require_permission/get_conn/get_current_account)도 `Depends(app.X)` — app 정본과 동일 객체라
dependency_overrides(객체키) 정합. _pg_connect 는 본문 내 shared.db import 유지(app 아님).
순환 안전: app 정의 후 맨 끝 include_router. 경로/메서드/응답·SQL·403 메시지 byte-동치.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app
from shared.model_catalog import (
    canonical_usage_model,
    canonical_usage_model_sql,
    taxonomy_for,
    usage_nav_path_label,
    usage_task_nav,
)

INCLUDE_ORDER = 30  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p11 이동분.
def _query_usage_conversations(pg, *, days: int, model: "str | None", account_ids: "list[int] | None",
                               day_label: "str | None", gran: str, owner_account_id: "int | None",
                               owner_is_null_ok: bool) -> "tuple[list[dict], bool]":
    """llm_usage ⋈ core_conversations 로 차원 필터된 대화 목록 + 대화별 기간내 usage 집계.

    필터(모두 AND, None=무시):
      - model: COALESCE(u.resolved_model, u.model) = model (차트 by_model 규칙과 동일)
      - account_ids: c.owner_account_id IN (...) — 역할 클릭은 그 역할 계정 집합을 호출측이 산출해 전달.
      - day_label: to_char(date_trunc(gran, u.created_at), fmt) = day_label (by_day 규칙과 동일)
      - owner_account_id: 본인 범위 강제(profile) — c.owner_account_id = owner_account_id.
    owner_is_null_ok=False 면 owner NULL(시스템) 대화 제외(profile·계정 클릭). True 면 "(시스템)" 역할
    클릭처럼 owner NULL 도 포함(account_ids 가 [None] 신호일 때 호출측이 별도 처리).

    반환: (items[{conversation_id, topic, owner_account_id, created_at, updated_at, blocked_at,
                  calls, total_tokens, prompt_tokens, completion_tokens, cost_usd, models[]}], truncated)
    conversation_id NOT NULL 강제(INNER JOIN) — insight/시스템 비대화 usage 제외.
    """
    # PG 는 `interval $1`(파라미터) 문법을 불허 → `%s::interval` 캐스트로 days 를 바인드한다
    # (admin_llm_usage 는 int 보간 `interval '{days} days'`; 여기선 캐스트로 파라미터화 유지).
    win = "now() - %s::interval"
    where = ["u.conversation_id IS NOT NULL", "u.created_at >= " + win]
    params: list = [f"{int(days)} days"]
    # 모델 필터는 canonical family 기준 — 도넛/차트 라벨(canonical_usage_model_sql)과 동일 규칙이라
    # 'claude-haiku-4' 클릭이 -interactive/-chat/실ID 변형 대화까지 모두 매칭(차트 수치 ↔ 대화목록 정합).
    if model:
        where.append(canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)") + " = %s")
        params.append(model)
    if account_ids is not None:
        # 빈 집합이면 결과 0 (역할에 계정이 없음).
        if not account_ids:
            return ([], False)
        ph = ",".join(["%s"] * len(account_ids))
        where.append(f"c.owner_account_id IN ({ph})")
        params.extend([int(a) for a in account_ids])
    if owner_account_id is not None:
        where.append("c.owner_account_id = %s")
        params.append(int(owner_account_id))
    elif not owner_is_null_ok:
        where.append("c.owner_account_id IS NOT NULL")
    if day_label:
        bucket_expr, _fmt = app._usage_bucket_match_sql(gran)
        where.append(f"{bucket_expr} = %s")
        params.append(day_label)
    where_sql = " AND ".join(where)
    # 대화별 × 모델 분해(모델 stacked·비용용) → Python fold. LIMIT 은 대화 수 기준(+1 로 truncated 감지).
    # 모델 분해 키도 canonical family — 대화 모달의 models[] 가 도넛과 동일 표기로 표시(라우팅 변형 미분점).
    _canon_m = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")

    # usage-metric-charts: 캐시 인지 비용 — 차트 막대와 이 모달의 비용이 같은 식이어야 정합.
    #   컬럼 부재(0056 미적용)는 _usage_cache_exec 가 리터럴 0 판으로 재실행해 흡수(컬럼 자리 동일).
    def _sql(cr: str, cw: str) -> str:
        return (
            "SELECT u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, "
            f"c.blocked_at, {_canon_m} AS m, count(*) AS calls, "
            "sum(u.total_tokens) AS tok, sum(u.prompt_tokens) AS pt, sum(u.completion_tokens) AS ct, "
            f"max(u.created_at) AS last_used, sum({cr}) AS cr, sum({cw}) AS cw "
            "FROM agent_runtime.llm_usage u "
            "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
            f"WHERE {where_sql} "
            "GROUP BY u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, c.blocked_at, "
            f"{_canon_m}"
        )
    fold: dict = {}
    with pg.cursor() as cur:
        _usage_cache_exec(cur, pg, _sql, tuple(params), alias="u")
        for r in (cur.fetchall() or []):
            cid = r[0]
            e = fold.get(cid)
            if e is None:
                e = {
                    "conversation_id": cid, "topic": (r[1] or ""),
                    "owner_account_id": (int(r[2]) if r[2] is not None else None),
                    "created_at": (r[3].isoformat() if r[3] else None),
                    "updated_at": (r[4].isoformat() if r[4] else None),
                    "blocked": bool(r[5] is not None),
                    "calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "_models": {}, "_last_used": r[11],
                }
                fold[cid] = e
            mk, calls_r = r[6], int(r[7] or 0)
            tok_r, pt_r, ct_r = int(r[8] or 0), int(r[9] or 0), int(r[10] or 0)
            cr_r, cw_r = (int(r[12] or 0), int(r[13] or 0)) if len(r) > 13 else (0, 0)
            e["calls"] += calls_r
            e["total_tokens"] += tok_r
            e["prompt_tokens"] += pt_r
            e["completion_tokens"] += ct_r
            mc = app._estimate_llm_cost_usd(mk, pt_r, ct_r, cr_r, cw_r)
            e["cost_usd"] += mc
            mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += tok_r
            mm["cost_usd"] += mc
            if r[11] and (e["_last_used"] is None or r[11] > e["_last_used"]):
                e["_last_used"] = r[11]
    items = list(fold.values())
    # 기간내 사용량(토큰) 큰 순 → 같은 집계에 가장 많이 기여한 대화 먼저.
    items.sort(key=lambda x: x["total_tokens"], reverse=True)
    truncated = len(items) > app._USAGE_CONV_LIMIT
    items = items[:app._USAGE_CONV_LIMIT]
    for e in items:
        e["cost_usd"] = round(e["cost_usd"], 4)
        e["models"] = sorted(e.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in e["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        e["last_used_at"] = (e.pop("_last_used").isoformat() if e.get("_last_used") else None)
    return (items, truncated)


# ==== usage-records-system(2026-07-28) — 시스템·자율 사용 기록 (대화 비귀속분) ==========
#
# 배경: 차트 클릭 드릴다운은 `_query_usage_conversations`(INNER JOIN core_conversations +
#   owner NOT NULL)만 보여줬다. 라이브 실측(최근 30일) 기준 그 필터를 통과하는 건 883 호출·
#   37.4M 토큰뿐이고, **14,474 호출·36.4M 토큰(전체의 약 49%)** 은 대화에 귀속되지 않아
#   목록에서 통째로 사라졌다(insight 워커의 노드/테이블 분석, 콘텐츠 그룹 라벨, ask 워커의
#   용어/ENUM 후보 등). "(시스템)" 역할 막대를 클릭하면 빈 목록만 떴다.
#
# 보완 정의(집합 정합): 시스템 기록 = 대화 기록의 **정확한 여집합**
#   대화 기록 = joinable(core_conversations) AND owner_account_id IS NOT NULL
#   시스템 기록 = NOT(joinable AND owner NOT NULL)
#            = (매칭 대화 없음) OR (매칭되나 owner NULL — 예약 sentinel `__ask_worker__` 행)
#   → 두 목록의 합 = 그 차트 슬라이스의 전체 usage. 누락도 중복 계상도 없다.
#
# 그룹 단위: (task, target, 실행 주체 conversation_id). 대화 기록이 '대화 1건 = 1행'인 것과
#   대칭으로, 시스템은 '작업 × 대상 = 1행' 이라 사용자가 "어떤 작업이 어떤 객체에서 돌았는지"
#   를 바로 읽는다. run 단위 원장이 필요하면 'AI 운영 현황 > 운영 현황'의 최근 활동 피드가 정본.

_USAGE_SYS_LIMIT = 200  # 시스템 사용 기록 상한(대화 목록 _USAGE_CONV_LIMIT 과 동일 규모).


def _usage_cache_exprs(alias: str = "") -> "tuple[str, str]":
    """(cache_read, cache_write) 집계 표현식 — 0056 적용 DB 용."""
    p = f"{alias}." if alias else ""
    return (f"COALESCE({p}cache_read_tokens, 0)", f"COALESCE({p}cache_write_tokens, 0)")


# 캐시 컬럼(0056) 부재 시 같은 자리에 채우는 리터럴. **컬럼 개수·순서가 두 경로에서 동일**해야
# 호출측의 위치 인덱스가 흔들리지 않는다(0032/0047 사다리와 같은 규약).
_USAGE_CACHE_OFF = ("0", "0")


def _usage_cache_exec(cur, pg, build_sql, params=None, alias: str = "") -> bool:
    """캐시 컬럼 포함 SQL 을 실행하고, 컬럼이 없으면 리터럴 0 판으로 **재실행**한다.

    0056 이 `cache_read_tokens` / `cache_write_tokens` 를 추가하기 전 DB(마이그 지연·개발 DB·구
    이미지)에서 컬럼을 그대로 참조하면 사용량 화면이 통째로 500 이 된다. 저장소의 기존 자가치유
    관례(0032 target / 0047 target_scope 폴백 재조회)와 **같은 방식**으로 흡수한다 — 정상 경로에서
    추가 왕복이 없고(information_schema probe 불요), 실패 경로만 rollback 후 한 번 더 조회한다.

    build_sql(cache_read_expr, cache_write_expr) → SQL 문자열.
    반환: 캐시 컬럼이 실재해 값이 실집계됐으면 True, 리터럴 0 폴백이면 False.
    """
    on = _usage_cache_exprs(alias)
    try:
        cur.execute(build_sql(*on), params) if params is not None else cur.execute(build_sql(*on))
        return True
    except Exception:
        # 원인을 단정하지 않는다 — 재실행이 **성공했을 때만** 캐시 컬럼 부재로 판정할 수 있다.
        # 캐시 표현식 외에는 두 판이 동일하므로, 리터럴 0 판도 실패하면 다른 결함(문법·alias 등)이며
        # 그 예외는 삼키지 않고 그대로 올려 보낸다(무음 0 으로 위장한 성공 금지).
        try:
            pg.rollback()  # 실패 트랜잭션은 abort 상태라 재쿼리 전 rollback 필수
        except Exception:
            pass
        cur.execute(build_sql(*_USAGE_CACHE_OFF), params) if params is not None else cur.execute(build_sql(*_USAGE_CACHE_OFF))
        logging.getLogger(__name__).warning(
            "usage: 캐시 컬럼 없이 재조회 성공 — 0056 미적용으로 판단해 캐시 축 0 표시", exc_info=True)
        return False

# target 해소 소스 — 어느 것도 정본 단독이 아니라 union 한다(각자 커버가 다르다):
#   table_descriptions(콘솔 테이블 설명 SSOT, scope_key) · routine_objects(프로시저/함수,
#   datasource_key) · rag_objects(인사이트 적재 객체, datasource_key).
# 셋 다 소규모(각 ~2.3만 행 이하)라 스키마 IN 제한만으로 충분히 싸다.
_USAGE_TARGET_SCOPE_SQL = (
    "SELECT schema_name, table_name, scope_key AS ds FROM public.table_descriptions "
    "  WHERE scope_key <> 'common' AND schema_name IN ({ph}) "
    "UNION "
    "SELECT schema_name, routine_name, datasource_key FROM public.routine_objects "
    "  WHERE datasource_key <> '' AND schema_name IN ({ph}) "
    "UNION "
    "SELECT schema_name, table_name, datasource_key FROM public.rag_objects "
    "  WHERE datasource_key IS NOT NULL AND datasource_key <> '' AND schema_name IN ({ph})"
)


def _usage_target_parts(target: "str | None") -> "tuple[str | None, str | None]":
    """llm_usage.target → (schema, object) 파싱.

    관측된 형식(0032 기록 규약):
      'log_v2'                              → ('log_v2', None)           스키마 분석
      'gunzgame.account'                    → ('gunzgame', 'account')    테이블 분석
      'log_v2.tf_log_08.RoomID'             → ('log_v2', 'tf_log_08')    컬럼 노드 분석(테이블까지만 사용)
      'dbGame.usp_mod_player_currency()'    → ('dbGame', 'usp_mod_player_currency')  루틴 노드 분석
    데이터소스 라벨(cluster_label/product_classify)은 호출측이 target_kind='datasource' 로
    분기하므로 여기 오지 않는다. 파싱 불가/빈 값은 (None, None).
    """
    s = str(target or "").strip()
    if not s:
        return (None, None)
    if s.endswith("()"):
        s = s[:-2]
    parts = [p.strip() for p in s.split(".")]
    sch = parts[0] or None
    obj = (parts[1] if len(parts) >= 2 else "") or None
    return (sch, obj)


def _resolve_usage_target_scopes(pg, records: "list[dict]") -> None:
    """시스템 사용 기록의 target(스키마/객체) → 데이터소스 scope_key 해소 (in-place, best-effort).

    각 record 에 다음을 채운다:
      scope_key       해소된 데이터소스 scope_key(콘솔 스코프 select 의 option value 와 동일 값) 또는 None
      scope_ambiguous 후보 데이터소스가 2개 이상이라 특정 불가 (dev/qa 동일 스키마 복제 등)

    해소 실패(0건)·모호(2건 이상)는 **에러가 아니다** — 프론트가 데이터소스 스코프 없이 화면까지만
    이동하고 검색어를 채운다(정직한 저하). llm_usage.target 에 데이터소스 차원이 없기 때문에
    생기는 구조적 한계라, 여기서 추측으로 하나를 고르면 엉뚱한 데이터소스로 착지시킨다.
    """
    want = [r for r in records if r.get("_resolve_schema")]
    if not want:
        return
    # 스키마 IN 목록 — MSSQL 라벨 정규화(소문자 저장) 이력이 있어 원형·소문자 양쪽을 넣고,
    # 폴딩은 소문자 키로 통일한다(케이스 변형에 의한 false-miss 차단).
    schemas: list[str] = []
    seen: set[str] = set()
    for r in want:
        for cand in (r["_resolve_schema"], r["_resolve_schema"].lower()):
            if cand and cand not in seen:
                seen.add(cand)
                schemas.append(cand)
    if not schemas:
        return
    ph = ",".join(["%s"] * len(schemas))
    sql = _USAGE_TARGET_SCOPE_SQL.format(ph=ph)
    by_schema: dict[str, set] = {}
    by_object: dict[tuple, set] = {}
    try:
        with pg.cursor() as cur:
            cur.execute(sql, tuple(schemas) * 3)
            for row in (cur.fetchall() or []):
                sch = str(row[0] or "").strip().lower()
                obj = str(row[1] or "").strip().lower()
                ds = str(row[2] or "").strip()
                if not sch or not ds:
                    continue
                by_schema.setdefault(sch, set()).add(ds)
                if obj:
                    by_object.setdefault((sch, obj), set()).add(ds)
    except Exception:
        # 해소 실패는 목록 자체를 깨뜨리지 않는다(표시·이동 보조 정보일 뿐). 트랜잭션 abort 정리 후 포기.
        logging.getLogger(__name__).warning("usage system records: target scope resolve failed", exc_info=True)
        try:
            pg.rollback()
        except Exception:
            pass
        return
    for r in want:
        sch = str(r.pop("_resolve_schema", "") or "").lower()
        obj = str(r.pop("_resolve_object", "") or "").lower()
        cands = by_object.get((sch, obj)) if obj else None
        if not cands:
            cands = by_schema.get(sch)
        if not cands:
            continue
        if len(cands) == 1:
            r["scope_key"] = next(iter(cands))
        else:
            r["scope_ambiguous"] = True


def _usage_system_nav(record: dict) -> dict:
    """시스템 사용 기록 1건 → 관리 콘솔 내비게이션 서술자.

    shared/model_catalog.USAGE_TASK_NAV 가 task→화면 SSOT. 여기서는 해소된 데이터소스와
    검색어(대상 문자열)를 얹어 프론트가 그대로 적용할 수 있는 형태로 만든다.
      screen/subtab  admin.html 의 data-admin-tab / data-meta-subtab 키
      scope_key      PG 해소 결과(데이터소스 scope select 값). 없으면 프론트가 스코프 미변경.
      scope_ambiguous 후보 데이터소스가 여럿이라 특정 불가 — 프론트가 "화면까지만 이동" 을
                     행에 명시한다. **record 최상위에도 같은 값이 있지만 nav 에 실어야 한다**:
                     프론트의 이동 UI 는 nav 서술자만 읽으므로, 여기 누락되면 모호 안내가
                     조용히 사라져 사용자가 '엉뚱한 데이터소스에 착지했다'고 오인한다.
      scope_hint     target 자체가 데이터소스인 경우(cluster_label/product_classify)의 원문 —
                     라벨↔scope_key 매핑은 MySQL 레지스트리라 PG 에서 못 푼다. 프론트가
                     adminState.datasources 의 key/scope_key 양쪽과 대조해 해소한다.
      search         목록 검색창에 채울 대상 문자열(객체명). 없으면 None.
      path_label     '메타데이터 > 테이블 설명' 사람이 읽는 경로(hover 안내용).
    """
    nav = usage_task_nav(record.get("task"))
    kind = nav.pop("target_kind", "none")
    target = str(record.get("target") or "").strip()
    nav["scope_key"] = record.get("scope_key")
    nav["scope_ambiguous"] = bool(record.get("scope_ambiguous"))
    nav["scope_hint"] = target if (kind == "datasource" and target) else None
    # 검색어: 객체형은 파싱된 객체명(없으면 스키마), 스키마형은 스키마명. 데이터소스형/대상없음은 없음.
    search = None
    if kind in ("object", "schema") and target:
        sch, obj = _usage_target_parts(target)
        search = obj or sch
    nav["search"] = search
    nav["path_label"] = usage_nav_path_label(nav.get("screen"), nav.get("subtab"))
    return nav


def _query_usage_system_records(pg, *, days: int, model: "str | None",
                                day_label: "str | None", gran: str) -> "tuple[list[dict], bool]":
    """대화에 귀속되지 않는 시스템·자율 LLM 사용분을 (작업 × 대상 × 실행주체) 로 집계.

    필터는 대화 목록과 동일 규칙(model=canonical family, day_label=차트 버킷)이라 같은 막대를
    클릭했을 때 두 목록의 합이 그 막대 수치와 정합한다. 계정/역할 필터는 여기 오지 않는다 —
    시스템 사용분은 계정에 귀속되지 않으므로 호출측이 애초에 이 질의를 건너뛴다.

    반환: (items[{task, task_label, category, target, actor, calls, total_tokens, prompt_tokens,
                  completion_tokens, cost_usd, models[], last_used_at, scope_key, scope_ambiguous,
                  nav{...}}], truncated)
    """
    win = "now() - %s::interval"
    where = [
        # 여집합 정의 — 대화 목록(INNER JOIN + owner NOT NULL)이 포함하지 않는 전부.
        "(c.conversation_id IS NULL OR c.owner_account_id IS NULL)",
        "u.created_at >= " + win,
    ]
    params: list = [f"{int(days)} days"]
    _canon_m = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")
    if model:
        where.append(_canon_m + " = %s")
        params.append(model)
    if day_label:
        bucket_expr, _fmt = app._usage_bucket_match_sql(gran)
        where.append(f"{bucket_expr} = %s")
        params.append(day_label)
    where_sql = " AND ".join(where)
    # conv_exists: 실행 주체 id 로 실제 core_conversations 행이 있는지. 소유 계정만 없는 대화(링크
    #   가능)와 아예 삭제·미기록된 대화 id(링크 불가)를 구분하려면 필요하다 — 구분 없이 링크를 걸면
    #   삭제된 대화로 가는 깨진 링크가 생긴다(ai-ops feed 의 'sentinel 은 링크 안 함' 규약과 동형).
    # 0047 target_scope: 기록 시점에 확정된 데이터소스 scope_key. 있으면 역해소보다 **항상 우선**한다
    #   (역해소는 dev/qa 동명 스키마에서 구조적으로 모호 — CHG-20260728T113819 참조).
    #   컬럼 부재(마이그 미적용 / 구 이미지)는 SELECT 실패 → rollback 후 컬럼 제외 재조회로 자가치유
    #   (ai_ops `_query_activity` 의 has_target 폴백과 동형). 그 경우 legacy 경로(역해소)만 작동.
    #   GROUP BY 에 포함하는 이유: 같은 `schema.table` 이라도 데이터소스가 다르면 **다른 행**이어야
    #   한다(그게 이 컬럼을 만든 이유). NULL(legacy·비-DS 활동)끼리는 종전처럼 하나로 묶인다.
    # usage-metric-charts: 캐시 인지 비용(차트·대화목록과 동일 식). 0056 미적용이면 리터럴 0.
    def _build_sql(with_scope: bool, cr: str = "0", cw: str = "0") -> str:
        scope_sel = "COALESCE(u.target_scope, '') AS tscope, " if with_scope else "'' AS tscope, "
        scope_grp = ", COALESCE(u.target_scope, '')" if with_scope else ""
        return (
            "SELECT u.task, COALESCE(u.target, '') AS tgt, COALESCE(u.conversation_id, '') AS actor, "
            f"{_canon_m} AS m, count(*) AS calls, "
            "sum(u.total_tokens) AS tok, sum(u.prompt_tokens) AS pt, sum(u.completion_tokens) AS ct, "
            "max(u.created_at) AS last_used, "
            "bool_or(c.conversation_id IS NOT NULL) AS conv_exists, "
            # 폴백 변형도 리터럴 '' / 0 으로 같은 자리를 채워 **컬럼 인덱스가 모든 경로에서 동일**하다
            # (tscope=r[10], cr=r[11], cw=r[12]).
            f"{scope_sel[:-2]}, "
            f"sum({cr}) AS cr, sum({cw}) AS cw "
            "FROM agent_runtime.llm_usage u "
            "LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
            f"WHERE {where_sql} "
            f"GROUP BY u.task, tgt, actor, {_canon_m}{scope_grp}"
        )

    fold: dict = {}
    with pg.cursor() as cur:
        # 컬럼 사다리 — 두 마이그가 독립적으로 빠질 수 있어 조합을 위에서부터 시도한다:
        #   ① scope(0047) + cache(0056)  ② scope 만(0056 미적용 — 배포 순서상 실재하는 상태)
        #   ③ 둘 다 없음(구 이미지)
        #   "scope 없는데 cache 있는" 조합은 0047 < 0056 이라 실재하지 않으므로 시도하지 않는다.
        #   어느 단계든 SELECT 컬럼 **개수·순서는 동일**하다(부재분은 리터럴 '' / 0).
        _on = _usage_cache_exprs("u")
        _ladder = ((True, _on[0], _on[1]), (True, "0", "0"), (False, "0", "0"))
        for _i, (_scope, _cr, _cw) in enumerate(_ladder):
            try:
                cur.execute(_build_sql(_scope, _cr, _cw), tuple(params))
                break
            except Exception:
                logging.getLogger(__name__).warning(
                    "usage system records: 컬럼 사다리 %d단 실패 — 다음 단계로 폴백", _i + 1, exc_info=True)
                try:
                    pg.rollback()  # 실패 트랜잭션 abort 정리
                except Exception:
                    pass
                if _i == len(_ladder) - 1:
                    raise
        for r in (cur.fetchall() or []):
            task, tgt, actor = (r[0] or ""), (r[1] or ""), (r[2] or "")
            # 0047: 기록된 데이터소스 scope_key(없으면 ""). 같은 target 이라도 데이터소스가 다르면
            #   별 행 — fold 키에 포함해야 두 데이터소스의 사용량이 한 줄로 뭉개지지 않는다.
            rec_scope = (r[10] or "") if len(r) > 10 else ""
            key = (task, tgt, actor, rec_scope)
            e = fold.get(key)
            if e is None:
                tx = taxonomy_for(task)
                e = {
                    "task": task, "task_label": tx["label"], "category": tx["category"],
                    "target": tgt or None, "actor": actor or None,
                    # 대화 링크는 **실재하는 비-sentinel 대화**에만 준다:
                    #   · sentinel(`__insight_worker__` 등) → 대화가 아님
                    #   · 삭제·미기록 id(conv_exists=False) → 열면 404 (깨진 링크)
                    # 둘 다 링크 없이 주체 라벨만 보여준다(ai-ops feed 의 정직 안내 규약과 동형).
                    "conversation_id": (actor if (actor and not actor.startswith("__") and bool(r[9])) else None),
                    "calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "_models": {}, "_last_used": r[8],
                    # 0047 이 채운 값이 있으면 그대로 확정(역해소 불필요·모호 없음).
                    "scope_key": (rec_scope or None), "scope_ambiguous": False,
                    "scope_source": ("recorded" if rec_scope else None),
                }
                fold[key] = e
            mk, calls_r = r[3], int(r[4] or 0)
            tok_r, pt_r, ct_r = int(r[5] or 0), int(r[6] or 0), int(r[7] or 0)
            cr_r, cw_r = (int(r[11] or 0), int(r[12] or 0)) if len(r) > 12 else (0, 0)
            e["calls"] += calls_r
            e["total_tokens"] += tok_r
            e["prompt_tokens"] += pt_r
            e["completion_tokens"] += ct_r
            mc = app._estimate_llm_cost_usd(mk, pt_r, ct_r, cr_r, cw_r)
            e["cost_usd"] += mc
            mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += tok_r
            mm["cost_usd"] += mc
            if r[8] and (e["_last_used"] is None or r[8] > e["_last_used"]):
                e["_last_used"] = r[8]
    items = list(fold.values())
    items.sort(key=lambda x: x["total_tokens"], reverse=True)
    truncated = len(items) > _USAGE_SYS_LIMIT
    items = items[:_USAGE_SYS_LIMIT]
    for e in items:
        e["cost_usd"] = round(e["cost_usd"], 4)
        e["models"] = sorted(e.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in e["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        e["last_used_at"] = (e.pop("_last_used").isoformat() if e.get("_last_used") else None)
        # 데이터소스 해소 대상 표시 — 객체/스키마형 target 만(데이터소스형은 프론트가 hint 로 해소).
        #   0047 로 **기록된 scope 가 이미 있으면 역해소를 건너뛴다**(정확한 값을 추정으로 덮지 않음).
        kind = usage_task_nav(e["task"]).get("target_kind")
        if e.get("scope_key"):
            continue
        if kind in ("object", "schema") and e.get("target"):
            sch, obj = _usage_target_parts(e["target"])
            if sch:
                e["_resolve_schema"] = sch
                e["_resolve_object"] = obj or ""
    # 상한 적용 **후** 해소 — IN 목록이 표시분으로 제한돼 질의 비용이 유계.
    _resolve_usage_target_scopes(pg, items)
    for e in items:
        e.pop("_resolve_schema", None)
        e.pop("_resolve_object", None)
        e["nav"] = _usage_system_nav(e)
    return (items, truncated)


@router.get("/api/admin/usage")
def admin_llm_usage(request: Request, account=Depends(app.require_permission("console.usage.read", message="LLM 사용량 조회 권한이 필요합니다 (운영자 전용).")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0136 (#11): LLM 토큰 사용량/비용 집계 — admin 한정(console.usage.read).

    감사 #11/cost gap: ~128 step frontier 호출에 비용 가시성이 전무했다. 모든 LLM 호출이
    agent_runtime.llm_usage 에 기록되며 본 endpoint 가 기간(days)별 총합 + 모델별 + 계정별
    (conversation→owner join) + 일별 집계를 반환. 운영·비용 민감 정보이므로 일반 사용자에게
    노출하지 않는다(권한 console.usage.read = admin 전용).

    Query: days (기본 30, 1~365). Response: {window_days, totals, by_model, by_account, by_day}.
    """
    try:
        days = int(request.query_params.get("days", "30"))
    except Exception:
        days = 30
    days = max(1, min(365, days))
    # TASK-0166: granularity (시/일/주/월). date_trunc 단위는 화이트리스트로만 SQL 삽입.
    gran = request.query_params.get("gran", "day").lower()
    if gran not in app._USAGE_GRAN:
        gran = "day"
    gran_cfg = app._USAGE_GRAN[gran]
    bucket_expr = f"to_char(date_trunc('{gran}', created_at), '{gran_cfg['fmt']}')"
    bucket_limit = gran_cfg["limit"]
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception as exc:
        logging.getLogger(__name__).warning("admin_usage: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        win = f"now() - interval '{days} days'"
        # usage-metric-charts: 캐시 축(0056). 첫 질의에서 컬럼 실재를 판정하고 그 결과를 이 요청의
        #   나머지 질의가 공유한다 — 질의마다 폴백을 반복하지 않으면서도 미적용 DB 에서 화면이 죽지 않는다.
        _CACHE_R, _CACHE_W = _usage_cache_exprs()
        _CACHE_R_U, _CACHE_W_U = _usage_cache_exprs("u")
        with pg.cursor() as cur:
            # TASK-0181: requests = 작업 화면에서 보낸 요청 수(distinct run_id; NULL=insight 등 제외).
            # usage-metric-charts: 캐시 읽기/쓰기 합도 함께 — 요약 카드 지표이자 비용식 입력.
            if not _usage_cache_exec(cur, pg, lambda cr, cw: (
                f"SELECT COALESCE(count(*),0), COALESCE(sum(prompt_tokens),0), "
                f"COALESCE(sum(completion_tokens),0), COALESCE(sum(total_tokens),0), "
                f"COALESCE(count(distinct run_id),0), "
                f"COALESCE(sum({cr}),0), COALESCE(sum({cw}),0) "
                f"FROM agent_runtime.llm_usage WHERE created_at >= {win}"
            )):
                # 컬럼 부재 확정 — 이 요청의 나머지 질의도 리터럴 0 으로 간다(재실패 방지).
                _CACHE_R, _CACHE_W = _USAGE_CACHE_OFF
                _CACHE_R_U, _CACHE_W_U = _USAGE_CACHE_OFF
            t = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0)
            totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                      "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                      "requests": int(t[4]),
                      "cache_read_tokens": int(t[5] or 0), "cache_write_tokens": int(t[6] or 0)}
            # usage-model-canonical: 실제 서빙 모델(COALESCE(resolved_model, model))을 canonical
            # family 로 접어 집계 → 라우팅 변형 alias(-interactive/-chat/-root)·실 모델 ID·gemma 폴백이
            # 한 논리 모델로 합쳐진다('모델별 비중' 도넛 중복 분점 해소). run_id distinct 도 canonical
            # 그룹 단위로 dedup 되어 요청 수 과대계상이 없다. model==resolved_model==canonical 로 채워
            # 프론트 modelKeyOf/도넛 라벨/색맵/드릴다운 필터가 동일 키로 정합(admin.js 무변경).
            _canon = canonical_usage_model_sql("COALESCE(resolved_model, model)")
            cur.execute(
                f"SELECT {_canon} AS m, count(*), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens), count(distinct run_id), "
                f"sum({_CACHE_R}), sum({_CACHE_W}) "
                f"FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY {_canon} "
                f"ORDER BY 3 DESC NULLS LAST LIMIT 50"
            )
            by_model = []
            for r in (cur.fetchall() or []):
                m = r[0]
                pt_m, ct_m = int(r[3] or 0), int(r[4] or 0)
                cr_m, cw_m = int(r[6] or 0), int(r[7] or 0)
                by_model.append({"model": m, "resolved_model": m, "calls": int(r[1]),
                                 "requests": int(r[5] or 0),
                                 "total_tokens": int(r[2] or 0), "prompt_tokens": pt_m,
                                 "completion_tokens": ct_m,
                                 "cache_read_tokens": cr_m, "cache_write_tokens": cw_m,
                                 "cost_usd": app._estimate_llm_cost_usd(m, pt_m, ct_m, cr_m, cw_m)})
            # TASK-0176: 계정 × 모델 분해 → 계정별 추정 비용 산출(비용은 모델별 단가라
            # 모델 분해 필수). Python 으로 계정별 fold(calls/tokens/cost). 역할별 비용은
            # _aggregate_usage_by_role 가 enrich 된 by_account 의 cost_usd 를 재합산.
            _canon_u = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")
            cur.execute(
                f"SELECT c.owner_account_id, {_canon_u}, count(*), "
                f"sum(u.total_tokens), sum(u.prompt_tokens), sum(u.completion_tokens), "
                f"sum({_CACHE_R_U}), sum({_CACHE_W_U}) "
                f"FROM agent_runtime.llm_usage u "
                f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} GROUP BY c.owner_account_id, {_canon_u}"
            )
            _acct_fold: dict = {}
            for r in (cur.fetchall() or []):
                aid = int(r[0]) if r[0] is not None else None
                mk, calls_r, tok_r, pt_r, ct_r = r[1], int(r[2]), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                cr_r, cw_r = int(r[6] or 0), int(r[7] or 0)
                e = _acct_fold.setdefault(aid, {"account_id": aid, "calls": 0, "total_tokens": 0,
                                                "prompt_tokens": 0, "completion_tokens": 0,
                                                "cache_read_tokens": 0, "cache_write_tokens": 0,
                                                "cost_usd": 0.0, "_models": {}})
                e["calls"] += calls_r
                e["total_tokens"] += tok_r
                # usage-metric-charts: 지표 전환(입력/출력/캐시)이 계정·역할 축에서도 성립하도록
                #   엔티티 레벨과 모델 분해 양쪽에 같은 축을 보존한다.
                e["prompt_tokens"] += pt_r
                e["completion_tokens"] += ct_r
                e["cache_read_tokens"] += cr_r
                e["cache_write_tokens"] += cw_r
                mc = app._estimate_llm_cost_usd(mk, pt_r, ct_r, cr_r, cw_r)
                e["cost_usd"] += mc
                # TASK-0181: 계정 × 모델 분해 보존(stacked 막대용).
                mm = e["_models"].setdefault(mk, {"model": mk, "calls": 0, "total_tokens": 0,
                                                  "prompt_tokens": 0, "completion_tokens": 0,
                                                  "cache_read_tokens": 0, "cache_write_tokens": 0,
                                                  "cost_usd": 0.0})
                mm["calls"] += calls_r
                mm["total_tokens"] += tok_r
                mm["prompt_tokens"] += pt_r
                mm["completion_tokens"] += ct_r
                mm["cache_read_tokens"] += cr_r
                mm["cache_write_tokens"] += cw_r
                mm["cost_usd"] += mc
            # TASK-0181: 계정별 요청 수(distinct run_id; run 은 conversation=계정 단위, NULL 제외).
            cur.execute(
                f"SELECT c.owner_account_id, count(distinct u.run_id) "
                f"FROM agent_runtime.llm_usage u "
                f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} AND u.run_id IS NOT NULL GROUP BY 1"
            )
            _acct_req = {(int(r[0]) if r[0] is not None else None): int(r[1]) for r in (cur.fetchall() or [])}
            by_account = sorted(_acct_fold.values(), key=lambda x: x["total_tokens"], reverse=True)[:100]
            for a in by_account:
                a["cost_usd"] = round(a["cost_usd"], 4)
                a["requests"] = _acct_req.get(a["account_id"], 0)
                a["models"] = sorted(a.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
                for m in a["models"]:
                    m["cost_usd"] = round(m["cost_usd"], 4)
            # TASK-0166: granularity bucket(시/일/주/월) 시계열 — 호출/토큰/prompt/completion.
            # usage-metric-charts: requests(distinct run_id)·캐시 축 추가. requests 는 모델 가산이
            #   성립하지 않아(한 run 이 여러 모델 횡단) by_day_model 로 분해할 수 없다 — 그래서
            #   버킷 총계를 여기서 따로 실어 보내고, 프론트가 그 지표에서만 단일 막대로 그린다.
            cur.execute(
                f"SELECT {bucket_expr} AS b, count(*), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens), count(distinct run_id), "
                f"sum({_CACHE_R}), sum({_CACHE_W}) FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}"
            )
            by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0),
                       "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0),
                       "requests": int(r[5] or 0),
                       "cache_read_tokens": int(r[6] or 0), "cache_write_tokens": int(r[7] or 0)}
                      for r in (cur.fetchall() or [])]
            # TASK-0164/0166: bucket × 모델 분해 (stacked bar). 최근 bucket_limit 버킷만
            # (서브쿼리로 by_day 와 동일 버킷 집합 보장 → 차트 정합).
            # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(cost_usd) 산출 → hover 표시.
            cur.execute(
                f"SELECT {bucket_expr} AS b, {_canon} , sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens), count(*), "
                f"sum({_CACHE_R}), sum({_CACHE_W}) "
                f"FROM agent_runtime.llm_usage WHERE created_at >= {win} "
                f"AND {bucket_expr} IN (SELECT {bucket_expr} FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) "
                f"GROUP BY 1, 2 ORDER BY 1"
            )
            # usage-metric-charts: 지표 전환용 축을 버킷×모델 단위로 전량 보존(프론트가 재계산 없이 선택).
            by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                             "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0),
                             "calls": int(r[5] or 0),
                             "cache_read_tokens": int(r[6] or 0), "cache_write_tokens": int(r[7] or 0),
                             "cost_usd": app._estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0),
                                                                    int(r[6] or 0), int(r[7] or 0))}
                            for r in (cur.fetchall() or [])]
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # TASK-0163: 계정 ID → 사용자명·역할 매핑(MySQL, cross-DB) + 역할별 집계.
    # usage 는 PG·계정/역할은 MySQL 이라 SQL join 불가 → Python 으로 enrich/fold.
    acct_ids = [row["account_id"] for row in by_account if row["account_id"] is not None]
    acct_meta: dict[int, dict] = {}
    if acct_ids:
        try:
            placeholders = ",".join(["%s"] * len(acct_ids))
            mcur = conn.cursor(dictionary=True)
            try:
                mcur.execute(
                    f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                    f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId "
                    f"WHERE a.Id IN ({placeholders})",
                    tuple(acct_ids),
                )
                for m in (mcur.fetchall() or []):
                    acct_meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
            finally:
                mcur.close()
        except Exception:
            logging.getLogger(__name__).warning("admin_usage: role enrichment failed", exc_info=True)
    for row in by_account:
        meta = acct_meta.get(row["account_id"]) if row["account_id"] is not None else None
        row["username"] = (meta or {}).get("username")
        row["role"] = (meta or {}).get("role")
    by_role = app._aggregate_usage_by_role(by_account)
    # TASK-0166: 총 추정 비용 = 모델별 추정 비용 합(단가 미상 로컬은 0).
    totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
    return JSONResponse({
        "window_days": days,
        "granularity": gran,
        "totals": totals,
        "by_model": by_model,
        "by_account": by_account,
        "by_role": by_role,
        "by_day": by_day,
        "by_day_model": by_day_model,
    })


@router.get("/api/admin/usage/conversations")
def admin_usage_conversations(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0263: 사용량 차트 클릭 → 집계 기여 '사용 기록'(admin 콘솔 모달).

    권한: console.usage.read(사용량 조회) + conversation.list.any(타 계정 대화목록 열람).
    둘 다 필요 — 사용량은 admin 인데 대화목록 열람 권한이 없는 운영자에게 타 계정 대화
    제목을 노출하지 않기 위함(기존 RBAC 재사용, 신규 권한 0). 대화 메타(제목/일시/소유자/
    기간내 usage)만 반환 — 메시지 본문 미포함.

    usage-records-system(2026-07-28): 응답에 `system_items`(대화 비귀속 = 시스템·자율 사용분)를
    **additive** 로 추가한다. `items`(대화) 는 형태·규칙 무변경이라 기존 소비자 회귀 0.
      · 모델/일자 클릭      → items + system_items (둘의 합 = 그 막대 수치)
      · "(시스템)" 역할 클릭 → items=[] + system_items (종전엔 빈 목록만 떴다)
      · 계정/일반 역할 클릭  → items + system_items=[] (시스템 사용분은 계정 귀속이 아니므로
                              그 계정 몫으로 섞어 보여주면 귀속 오도 — 의도적 제외)
    엔드포인트 URL 은 기존 경로를 유지한다(프론트 배포 순서 무관 호환 — 구 프론트는 새 필드를
    무시하고, 신 프론트는 구 백엔드에서 system_items 부재를 빈 배열로 폴백한다).
    """
    if not app._account_has_permission(account, "console.usage.read"):
        return app._json_error("LLM 사용량 조회 권한이 필요합니다 (운영자 전용).", 403)
    if not app._account_has_permission(account, "conversation.list.any"):
        return app._json_error("전체 대화목록 열람 권한이 필요합니다 (conversation.list.any).", 403)
    p = app._parse_usage_conv_params(request)
    # 역할 클릭 → 계정 집합 역매핑(MySQL). 모델/일자 클릭은 account 필터 없음.
    account_ids = None
    system_only = False
    if p["account_id"] is not None:
        account_ids = [p["account_id"]]
    elif p["role"] is not None:
        account_ids = app._usage_account_ids_for_role(conn, p["role"])
        if account_ids is None:
            # "(시스템)" 역할 — owner 없는 비대화 usage. 대화 목록은 비고, 시스템 기록만 채운다.
            system_only = True
    # 계정/역할로 좁힌 클릭은 시스템 기록 비대상(위 docstring 귀속 규칙).
    want_system = system_only or (account_ids is None)
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("admin_usage_conversations: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    items: list = []
    truncated = False
    system_items: list = []
    system_truncated = False
    try:
        if not system_only:
            items, truncated = app._query_usage_conversations(
                pg, days=p["days"], model=p["model"], account_ids=account_ids,
                day_label=p["day_label"], gran=p["gran"], owner_account_id=None,
                owner_is_null_ok=False,
            )
        if want_system:
            try:
                system_items, system_truncated = app._query_usage_system_records(
                    pg, days=p["days"], model=p["model"],
                    day_label=p["day_label"], gran=p["gran"],
                )
            except Exception:
                # 시스템 기록 질의 실패가 대화 목록(기존 기능)을 깨뜨리지 않게 격리 — 부분 저하로 응답.
                logging.getLogger(__name__).warning(
                    "admin_usage_conversations: system records query failed", exc_info=True)
                system_items, system_truncated = [], False
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # 계정 메타(사용자명/역할) enrich — 모달 표시용(cross-DB, MySQL).
    app._enrich_usage_conv_owner_meta(conn, items)
    return JSONResponse({"items": items, "truncated": truncated,
                         "system_items": system_items, "system_truncated": system_truncated,
                         "filter": p, "scope": "admin"})


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (4종). app 전역은 app.X 동적 참조. ====

def _estimate_llm_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int,
                           cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float:
    """TASK-0166: 모델 토큰 → 추정 비용(USD). 단가 미상(로컬/edge 등)은 0.

    usage-model-canonical: 단가 조회 키를 canonical family 로 접는다. 단가표
    (_LLM_PRICE_USD_PER_1M)는 base alias(claude-haiku-4/claude-sonnet-4)만 등록돼, 라우팅 변형
    (claude-haiku-4-chat/-interactive)이나 실 모델 ID(claude-haiku-4-5-20251001)가 그대로 들어오면
    미매칭으로 비용 $0 로 오표시되던 gap 이 있었다. canonical 화로 변형/실ID 도 올바른 단가로 계상되고,
    gemma 폴백(edge)은 canonical 'edge' → 단가 미등록 → 0(로컬 무료) 로 정직하게 남는다.

    usage-metric-charts(2026-08-13) — **캐시 인지 단가**: `prompt_tokens` 는 캐시 토큰을 포함한
    값이다(게이트웨이 실측: 5039 = 순수입력 37 + 캐시쓰기 5002). 프롬프트 캐싱을 켠 뒤 이 함수가
    종전처럼 prompt 전량을 정가로 계산하면 캐시 적중분을 **10배 과대 계상**한다. 그래서 입력을
    세 구간으로 분해한다:
        순수 입력 = prompt - cache_read - cache_write   →  정가
        캐시 쓰기                                        →  정가 × 1.25 (기록 오버헤드)
        캐시 읽기                                        →  정가 × 0.10 (적중 할인)
    계수는 Anthropic 5분 ephemeral 캐시의 공시 배수다(정확 단가는 시점별 변동 — 운영자 참고용 "추정").

    무회귀: 캐시 인자 미전달(기본 0) 또는 캐시 0 인 레거시 행이면 순수 입력 = prompt 라 종전 식과
    **완전히 동일한 값**이 나온다. 캐시 값이 prompt 보다 큰 이상 데이터는 순수 입력을 0 으로 clamp 한다.
    """
    key = canonical_usage_model(model)
    p = app._LLM_PRICE_USD_PER_1M.get(key)
    if not p:
        return 0.0
    pt = int(prompt_tokens or 0)
    cr = max(0, int(cache_read_tokens or 0))
    cw = max(0, int(cache_write_tokens or 0))
    plain = max(0, pt - cr - cw)
    in_rate = p["in"] / 1e6
    return round(
        plain * in_rate
        + cw * in_rate * app._LLM_CACHE_WRITE_MULT
        + cr * in_rate * app._LLM_CACHE_READ_MULT
        + (completion_tokens or 0) / 1e6 * p["out"],
        4,
    )

def _aggregate_usage_by_role(by_account: list[dict]) -> list[dict]:
    """TASK-0163: 계정별 LLM usage 를 역할별로 폴딩.

    account_id 가 None(insight 워커 등 owner 없는 시스템 호출) → "(시스템)" 버킷,
    계정은 있으나 역할 미지정(role NULL) → "(역할 없음)" 버킷. total_tokens desc 정렬.
    PG(usage)·MySQL(역할) cross-DB 라 SQL join 불가 → enrich 된 by_account 를 Python 집계.
    """
    buckets: dict[str, dict] = {}
    for row in by_account:
        if row.get("account_id") is None:
            key = "(시스템)"
        else:
            key = row.get("role") or "(역할 없음)"
        b = buckets.setdefault(key, {"role": key, "calls": 0, "requests": 0,
                                     "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                     "cache_read_tokens": 0, "cache_write_tokens": 0,
                                     "cost_usd": 0.0, "_models": {}})
        b["calls"] += int(row.get("calls") or 0)
        b["requests"] += int(row.get("requests") or 0)  # TASK-0181: 요청 수(distinct run_id) 합산
        b["total_tokens"] += int(row.get("total_tokens") or 0)
        # usage-metric-charts: 지표 전환 축(입력/출력/캐시)도 역할로 합산.
        for _k in ("prompt_tokens", "completion_tokens", "cache_read_tokens", "cache_write_tokens"):
            b[_k] += int(row.get(_k) or 0)
        b["cost_usd"] += float(row.get("cost_usd") or 0)  # TASK-0176: 역할별 추정 비용 합산
        # TASK-0181: 역할별 모델 분해(stacked 막대용) — 계정의 models[] 를 역할로 합산.
        for m in (row.get("models") or []):
            mm = b["_models"].setdefault(m["model"], {"model": m["model"], "calls": 0, "total_tokens": 0,
                                                      "prompt_tokens": 0, "completion_tokens": 0,
                                                      "cache_read_tokens": 0, "cache_write_tokens": 0,
                                                      "cost_usd": 0.0})
            mm["total_tokens"] += int(m.get("total_tokens") or 0)
            for _k in ("calls", "prompt_tokens", "completion_tokens", "cache_read_tokens", "cache_write_tokens"):
                mm[_k] += int(m.get(_k) or 0)
            mm["cost_usd"] += float(m.get("cost_usd") or 0)
    out = []
    for b in buckets.values():
        b["cost_usd"] = round(b["cost_usd"], 4)
        b["models"] = sorted(b.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in b["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        out.append(b)
    return sorted(out, key=lambda x: x["total_tokens"], reverse=True)

def _usage_bucket_match_sql(gran: str) -> "tuple[str, str]":
    """day 필터용 bucket 표현식 + 화이트리스트 검증된 to_char 포맷.

    admin_llm_usage 의 _USAGE_GRAN[gran]['fmt'] 와 동일 — 클릭한 일자 라벨(차트의 by_day[].day)이
    그 포맷 문자열이므로, 동일 to_char(date_trunc(...)) 로 매칭하면 차트 막대 ↔ 대화 정합.
    반환: (bucket_expr, fmt). gran 미허용 시 day 폴백.
    """
    g = gran if gran in app._USAGE_GRAN else "day"
    fmt = app._USAGE_GRAN[g]["fmt"]
    return (f"to_char(date_trunc('{g}', u.created_at), '{fmt}')", fmt)

def _enrich_usage_conv_owner_meta(conn, items: list[dict]) -> None:
    """대화 owner_account_id → 사용자명/역할 enrich(MySQL, 모달 표시용). in-place."""
    ids = sorted({e["owner_account_id"] for e in items if e.get("owner_account_id") is not None})
    if not ids:
        return
    meta: dict[int, dict] = {}
    try:
        ph = ",".join(["%s"] * len(ids))
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE a.Id IN ({ph})",
                tuple(ids),
            )
            for m in (cur.fetchall() or []):
                meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("usage_conversations: owner meta enrich failed", exc_info=True)
        return
    for e in items:
        mm = meta.get(e.get("owner_account_id")) if e.get("owner_account_id") is not None else None
        e["owner_username"] = (mm or {}).get("username")
        e["owner_role"] = (mm or {}).get("role")


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _usage_account_ids_for_role(conn, role_key: str) -> "list[int] | None":
    """역할 클릭(by_role 의 role 키) → 그 역할에 속한 account_id 집합(MySQL).

    by_role 규칙(_aggregate_usage_by_role)과 동일:
      "(시스템)"   → None (owner NULL 대화 = 비대화 usage. 대화목록에선 빈 집합 — 시스템 호출엔 대화 없음)
      "(역할 없음)" → RoleId NULL(또는 역할 매핑 실패) 계정들
      그 외        → WebRoles.Name == role_key 인 계정들
    반환: account_id 리스트(빈 리스트 가능) 또는 None(시스템 — 대화 없음).
    """
    if role_key == "(시스템)":
        return None
    cur = conn.cursor()
    try:
        if role_key == "(역할 없음)":
            cur.execute("SELECT a.Id FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name IS NULL")
        else:
            cur.execute("SELECT a.Id FROM WebAccounts a JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name = %s", (role_key,))
        return [int(row[0]) for row in (cur.fetchall() or [])]
    finally:
        cur.close()


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (2종). ====

# date_trunc granularity 화이트리스트 + 표시 포맷 + bucket 개수 상한(차트 막대 과밀 방지).
_USAGE_GRAN = {
    "hour":  {"fmt": "YYYY-MM-DD HH24:00", "limit": 168},
    "day":   {"fmt": "YYYY-MM-DD",          "limit": 90},
    "week":  {"fmt": "YYYY-MM-DD",          "limit": 53},
    "month": {"fmt": "YYYY-MM",             "limit": 36},
}

# TASK-0166: LLM 비용 추정 단가 (USD per 1M tokens). 로컬 LLM(edge/core/auto/code)=0.
# Bedrock claude 공시가 근사 — 정확 단가는 시점/리전별 변동하므로 운영자 참고용 "추정"이다.
# 별칭(model) 기준 매핑(LiteLLM 이 resolved_model 에도 별칭을 반환하는 경우가 많음).
# usage-metric-charts(2026-08-13): 프롬프트 캐시 단가 배수(Anthropic 5분 ephemeral 공시 기준).
#   캐시 쓰기는 정가의 1.25배, 캐시 읽기는 0.1배. 입력 단가에만 곱한다(출력은 캐시 개념 없음).
_LLM_CACHE_WRITE_MULT = 1.25
_LLM_CACHE_READ_MULT = 0.10

_LLM_PRICE_USD_PER_1M = {
    "claude-haiku-4": {"in": 1.0, "out": 5.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    # opus5-model(2026-07-27): Opus 5 공시가 $5 / $25 per MTok. canonical family 키(claude-opus-5)와
    # 동일해 -chat/-chat-root 라우팅 변형·실 모델 ID 도 이 단가로 계상된다(단가 $0 오표시 gap 차단).
    "claude-opus-5": {"in": 5.0, "out": 25.0},
}
