"""domain_synthesis — 스키마(도메인) 단위 합성 요약, lazy 생성 (feature-0037, ITEM-08 / L3).

클러스터 요약(L2)은 "이 묶음이 함께 무엇을 하는가"에 답한다. 그 위에 "이 DB 전체가 어떤
도메인이고 그 안에 어떤 축들이 있는가"를 답하는 층이 L3 다.

**요청과 생성을 분리한다** — 이 모듈의 설계 전부가 여기서 나온다.

    grounding 이 조회 → 없으면 `request()` 만 남긴다 (LLM 0, 지연 0)
    insight tick 이 요청된 것만 `run_synthesis_pass()` 로 합성 → 다음 질문부터 주입

두 제약이 얼핏 모순이기 때문이다:
  - **사전 전량 생성 금지**(LazyGraphRAG): 120개 스키마를 미리 다 만들면 대부분 아무도 안 읽는다.
  - **답변 경로 런타임 합성 금지**(ADR-0034-07): 질문이 들어온 순간 LLM 을 부르면 체감 지연을
    잠식한다.

해법은 "누가 실제로 찾았는가"를 생성 신호로 쓰는 것이다. 첫 질문은 요약 없이 답하지만, 그 대가로
120번의 헛된 합성을 치르지 않는다. 자주 찾히는 도메인이 먼저 채워진다(`request_count` 우선순위).

입력은 그 스키마의 **클러스터 요약들**이지 개별 테이블이 아니다 — 이미 한 번 접힌 것을 다시 접는다.
"""
from __future__ import annotations

import hashlib
import logging

_log = logging.getLogger("domain_synthesis")

#: 한 pass 에 합성할 스키마 수. L3 는 입력이 크므로(클러스터 요약 다수) 작게 유지한다.
_DEFAULT_MAX_PER_PASS = 3

#: payload 에 싣는 클러스터 요약 수 — 스키마 하나에 수십 개가 있을 수 있다.
_GROUP_CAP = 25

#: 재생성 판정(해시)에 쓰는 조회 상한. payload cap 보다 크게 둔다 — cap 으로 자른 뒤 해시하면
#: **26번째 이후 클러스터의 변화를 영영 놓친다**(codex).
_HASH_SCAN_CAP = 300

#: 각 클러스터 요약 절단.
_GROUP_SUMMARY_CLIP = 300

#: 도메인 요약 저장 절단.
_SUMMARY_CLIP = 1500


def enabled() -> bool:
    """L3 합성 스위치 — 콘솔 live override 우선. 조회 실패는 비활성(모르면 지출하지 않는다)."""
    try:
        from shared import runtime_settings as _rts
        return bool(int(_rts.get_int("AGENT_DOMAIN_SUMMARY_ENABLED")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return bool(int(getattr(_cfg, "AGENT_DOMAIN_SUMMARY_ENABLED", 0) or 0))
    except Exception:
        return False


def max_per_pass() -> int:
    try:
        from shared import runtime_settings as _rts
        return max(0, int(_rts.get_int("AGENT_DOMAIN_SUMMARY_MAX_PER_PASS")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return max(0, int(getattr(_cfg, "AGENT_DOMAIN_SUMMARY_MAX_PER_PASS",
                                  _DEFAULT_MAX_PER_PASS) or 0))
    except Exception:
        return 0


def _savepoint(cur):
    """조회·적재 실패가 호출측 트랜잭션을 오염시키지 않게 한다(0031·0033·0036 과 동형)."""
    import contextlib

    @contextlib.contextmanager
    def _sp():
        name = "sp_domain_synthesis"
        opened = False
        try:
            cur.execute(f"SAVEPOINT {name}")
            opened = True
        except Exception:
            opened = False
        try:
            yield
        except Exception:
            if opened:
                try:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
                except Exception:
                    pass
            raise
        else:
            if opened:
                try:
                    cur.execute(f"RELEASE SAVEPOINT {name}")
                except Exception:
                    pass

    return _sp()


def cluster_set_hash(rows) -> str:
    """그 스키마의 클러스터 요약 집합 지문. **정렬 후** 해시한다(순서 무관).

    라벨·요약뿐 아니라 **멤버 수·근거 수도 넣는다**(codex): 커버리지가 늘어 근거가 두터워지면
    같은 라벨·같은 요약이어도 도메인 그림의 신뢰도가 달라진다. 그것을 반영하지 않으면 요약이
    영원히 옛 커버리지 기준으로 남는다.

    ⚠ 이 함수는 payload cap 으로 자르기 **전** 전체 집합에 대해 불려야 한다 — 잘린 뒤 해시하면
    상한 밖 클러스터의 변화를 영영 놓친다.
    """
    parts = []
    for r in rows or ():
        label = str((r[0] if len(r) > 0 else "") or "")
        summary = str((r[1] if len(r) > 1 else "") or "")
        mc = int((r[2] if len(r) > 2 else 0) or 0)
        ac = int((r[3] if len(r) > 3 else 0) or 0)
        digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()[:12]
        parts.append(f"{len(label)}:{label}|{digest}|{mc}|{ac}")
    if not parts:
        return ""
    joined = "".join(sorted(parts))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def request(cur, scope_key: str, schema_name: str) -> bool:
    """도메인 요약 요청 기록. **LLM 을 부르지 않는다** — 지연 0.

    grounding 이 요약을 찾다가 없을 때 호출한다. 이미 생성된 스키마면 아무것도 하지 않는다.
    반환 True=요청이 기록됨.
    """
    if not scope_key or not schema_name:
        return False
    try:
        with _savepoint(cur):
            cur.execute(
                "INSERT INTO domain_summaries "
                "(scope_key, schema_name, requested_at, request_count) "
                "VALUES (%s, %s, now(), 1) "
                "ON CONFLICT (scope_key, schema_name) DO UPDATE SET "
                " requested_at = COALESCE(domain_summaries.requested_at, now()), "
                " request_count = domain_summaries.request_count + 1",
                (scope_key, schema_name))
        return True
    except Exception as exc:
        _log.debug("domain_request_failed %s.%s err=%r", scope_key, schema_name, exc)
        return False


def load(cur, scope_key: str, schema_name: str) -> dict:
    """생성된 도메인 요약. 없으면 빈 dict(호출측이 `request()` 를 남긴다)."""
    if not scope_key or not schema_name:
        return {}
    try:
        with _savepoint(cur):
            cur.execute(
                "SELECT summary, cluster_count, member_count, analyzed_count "
                "FROM domain_summaries "
                "WHERE scope_key=%s AND schema_name=%s AND generated_at IS NOT NULL "
                "  AND summary IS NOT NULL AND summary <> ''",
                (scope_key, schema_name))
            row = cur.fetchone()
    except Exception as exc:
        _log.debug("domain_load_failed %s.%s err=%r", scope_key, schema_name, exc)
        return {}
    if not row:
        return {}
    return {"summary": str(row[0]), "cluster_count": int(row[1] or 0),
            "member_count": int(row[2] or 0), "analyzed_count": int(row[3] or 0)}


def pending_schemas(cur, limit: int) -> list:
    """합성 대기(요청됐고 미생성 또는 입력이 바뀐) 스키마. 요청이 많은 것부터.

    조회 실패는 빈 목록.
    """
    if limit <= 0:
        return []
    try:
        with _savepoint(cur):
            # ⚠ **미생성분을 먼저** 별도 쿼리로 가져온다(codex P2): 한 쿼리로 합치면
            #   `WHERE requested_at IS NOT NULL` 뿐이라 partial index
            #   (`generated_at IS NULL AND requested_at IS NOT NULL`)가 받지 못하고,
            #   생성된 행이 쌓일수록 요청 이력 전체 스캔에 가까워진다.
            cur.execute(
                "SELECT scope_key, schema_name, cluster_set_hash "
                "FROM domain_summaries "
                "WHERE generated_at IS NULL AND requested_at IS NOT NULL "
                "ORDER BY request_count DESC, requested_at "
                "LIMIT %s",
                (int(limit),))
            fresh = cur.fetchall() or []
            room = max(0, int(limit) - len(fresh))
            if room <= 0:
                return fresh
            # 남는 여유만큼 **이미 생성된 것 중 입력이 바뀌었을 수 있는 것**을 재검사한다.
            cur.execute(
                "SELECT scope_key, schema_name, cluster_set_hash "
                "FROM domain_summaries "
                "WHERE generated_at IS NOT NULL AND requested_at IS NOT NULL "
                "ORDER BY request_count DESC, generated_at "
                "LIMIT %s",
                (room * 2,))
            return fresh + (cur.fetchall() or [])
    except Exception as exc:
        _log.debug("domain_pending_unavailable err=%r", exc)
        return []


def live_cluster_labels(cur, scope_key: str, schema_name: str):
    """그 스키마에 **현재 존재하는** 클러스터 라벨 집합. 조회 실패는 `None`.

    `cluster_summaries` 의 PK 는 (scope, schema, member_set_hash) 라 클러스터가 재구성되면 옛 행이
    지워지지 않고 남는다. 그것을 L3 입력으로 쓰면 도메인 요약이 **이미 없어진 클러스터를 재료로**
    만들어지고, `cluster_count`/`member_count` 가 부풀려진 채 `_domain_line` 을 통해 사용자 답변
    프롬프트에 그대로 실린다("그룹 90개 · 멤버 887개 중 …개 상세분석 근거").

    라이브 실측(2026-08-06): `atum2_db_1` 은 요약 90행(멤버 887) 중 현재 유효한 것이 **17행
    (멤버 196)** — 81%가 죽은 클러스터였다. `gunzgame` 은 45행(329) → 25행(147).

    현재 유효성의 정본은 클러스터링이 매 pass 역기록하는 라벨이고, 그 저장처가 **멤버 종류에 따라
    갈린다**: 테이블은 `rag_objects`, 루틴(프로시저·함수)은 `routine_objects`. 둘을 합쳐야 한다 —
    `rag_objects` 만 보면 **루틴으로만 이뤄진 클러스터가 통째로 죽은 것으로 판정된다**. 라이브 실측
    (2026-08-06): rag 만 보면 사망 933행이지만 루틴을 합치면 **63행(3.4%)** 이다. 버려질 뻔한 933행
    중 870행이 살아있는 루틴 클러스터였고, MSSQL 은 루틴이 압도적이다(`atum2_db_1` 라벨 달린 루틴
    865 vs 테이블 115). 이 축을 빼먹으면 그 DB 의 프로시저 표면을 통째로 못 본 요약이 나간다.

    ⚠ `rag_objects` 쪽 조인 키는 `effective_schema` 를 거쳐야 한다 — MSSQL 은 `schema_name` 이
    리터럴 'dbo' 라 DB 차원이 소실돼, 그대로 비교하면 한 건도 매칭되지 않는다. SQL 로 후보를 좁히고
    (object_key 접두) 파이썬에서 정확히 판정한다. `routine_objects.schema_name` 은 이미
    eff-schema 라 변환이 필요 없다.
    """
    out = set()
    try:
        with _savepoint(cur):
            cur.execute(
                "SELECT object_key, schema_name, semantic_cluster_label FROM rag_objects "
                "WHERE datasource_key=%s AND semantic_cluster_label IS NOT NULL "
                "  AND semantic_cluster_label <> '' "
                "  AND (schema_name=%s OR object_key LIKE %s)",
                (scope_key, schema_name, f"{scope_key}:{schema_name}.%"))
            rag_rows = cur.fetchall() or []
        with _savepoint(cur):
            cur.execute(
                "SELECT semantic_cluster_label FROM routine_objects "
                "WHERE datasource_key=%s AND schema_name=%s "
                "  AND semantic_cluster_label IS NOT NULL AND semantic_cluster_label <> ''",
                (scope_key, schema_name))
            routine_rows = cur.fetchall() or []
    except Exception as exc:
        _log.debug("live_labels_unavailable %s.%s err=%r", scope_key, schema_name, exc)
        return None
    try:
        from .cluster_context import effective_schema
    except Exception as exc:
        _log.debug("effective_schema_unavailable err=%r", exc)
        return None
    for object_key, sch, label in rag_rows:
        if effective_schema(scope_key, object_key, sch) == schema_name and label:
            out.add(str(label))
    for (label,) in routine_rows:
        if label:
            out.add(str(label))
    return out


def cluster_inputs(cur, scope_key: str, schema_name: str) -> list:
    """그 스키마의 **현재 살아있는** 클러스터 요약들. **결정적 정렬**(근거 많은 순 → 라벨).

    조회 실패는 빈 목록(= 합성 대상에서 제외). 현재 라벨 집합을 못 읽어도 마찬가지다 —
    **부풀려진 재료로 만든 요약을 내보내느니 이번 pass 를 건너뛴다**(요청은 남아 있으므로 다음
    pass 가 재시도한다). 판정 실패를 침묵으로 처리하는 feature-0036 의 계약과 같은 방향이다.
    """
    live = live_cluster_labels(cur, scope_key, schema_name)
    if live is None:
        return []
    if not live:
        # 요약은 있는데 현재 라벨이 하나도 없다 = 클러스터링이 아직 역기록하지 않았거나 스키마가
        #   비었다. 조용히 건너뛰면 그 스키마가 pass cap 을 계속 물어 **뒤의 요청까지 굶는다**
        #   (head-of-line). 로그로 남겨 스톨을 식별 가능하게 한다.
        _log.info("도메인 합성 건너뜀 — 현재 클러스터 라벨 없음 %s.%s(클러스터링 역기록 대기)",
                  scope_key, schema_name)
        return []
    try:
        with _savepoint(cur):
            cur.execute(
                "SELECT label, summary, member_count, analyzed_count "
                "FROM cluster_summaries "
                "WHERE scope_key=%s AND schema_name=%s AND summary IS NOT NULL AND summary <> '' "
                "ORDER BY analyzed_count DESC, member_count DESC, label "
                "LIMIT %s",
                (scope_key, schema_name, _HASH_SCAN_CAP))
            rows = cur.fetchall() or []
    except Exception as exc:
        _log.debug("domain_inputs_unavailable %s.%s err=%r", scope_key, schema_name, exc)
        return []
    return [r for r in rows if r and str(r[0] or "") in live]


def build_payload(datasource_label: str, schema_name: str, rows) -> dict:
    """합성 payload. 커버리지 카운트를 함께 실어 판정자가 확신 수위를 조절하게 한다."""
    groups = []
    members = analyzed = 0
    # 커버리지 합계는 **전체** 클러스터 기준으로 센다 — payload 에 싣는 것만 세면 "그룹 8개 중
    # 3개 근거" 같은 표기가 실제보다 작아 보인다.
    for r in rows:
        label = str(r[0] or "")
        summary = " ".join(str(r[1] or "").split())[:_GROUP_SUMMARY_CLIP]
        mc, ac = int(r[2] or 0), int(r[3] or 0)
        members += mc
        analyzed += ac
        if label and summary and len(groups) < _GROUP_CAP:
            groups.append({"label": label, "member_count": mc,
                           "analyzed_count": ac, "summary": summary})
    total_clusters = sum(1 for r in rows if str(r[0] or "") and str(r[1] or ""))
    return {"task": "domain_summary", "datasource": datasource_label, "schema": schema_name,
            "cluster_count": total_clusters, "member_count": members,
            "analyzed_count": analyzed, "groups": groups}


def store(cur, scope_key, schema_name, summary, payload, c_hash, model) -> bool:
    """합성 결과 적재. 반환 True=저장됨."""
    try:
        with _savepoint(cur):
            cur.execute(
                "UPDATE domain_summaries SET "
                " summary=%s, cluster_count=%s, member_count=%s, analyzed_count=%s, "
                " cluster_set_hash=%s, model=%s, generated_at=now() "
                "WHERE scope_key=%s AND schema_name=%s",
                (str(summary)[:_SUMMARY_CLIP], payload["cluster_count"],
                 payload["member_count"], payload["analyzed_count"], c_hash,
                 str(model or "")[:64], scope_key, schema_name))
        return True
    except Exception as exc:
        _log.debug("domain_store_failed %s.%s err=%r", scope_key, schema_name, exc)
        return False


def run_synthesis_pass(conn=None, limit=None) -> dict:
    """요청된 스키마만 합성한다. 반환 telemetry.

    `conn` 이 없으면 자체 agent_kb 연결을 연다(insight tick 스코프에는 그 커넥션이 없다 —
    feature-0036 에서 같은 실수를 했다).
    """
    # `attempted` = 실제로 태운 LLM 콜 수. `synthesized`(저장 성공)만 세면 **콜만 태우고 산출이
    #   0인 pass 가 통째로 무음**이 된다 — 빈약한 응답(30자 미만)·저장 실패가 그 경로다.
    #   feature-0036 이 같은 결함을 라이브에서 겪었고(판정 실패가 예산을 먹는데 계기판은 조용),
    #   여기서도 둘의 격차가 곧 "재료는 있는데 못 만들고 있다"는 신호다.
    rep = {"synthesized": 0, "attempted": 0, "skipped": None}
    if not enabled():
        rep["skipped"] = "disabled"
        return rep
    configured = max_per_pass()
    cap = configured if limit is None else min(configured, max(0, int(limit)))
    if cap <= 0:
        rep["skipped"] = "cap_zero"
        return rep
    try:
        from shared import llm_budget as _lb
        from shared import resource_budget as _rb
    except Exception:
        rep["skipped"] = "budget_unavailable"
        return rep
    if not _lb.allowed(conn):
        rep["skipped"] = "llm_token_budget"
        return rep
    try:
        from . import llm as _llm
    except Exception:
        rep["skipped"] = "llm_unavailable"
        return rep

    owned = False
    if conn is None:
        try:
            from shared import db as _db
            conn = _db._pg_connect()
            owned = conn is not None
        except Exception as exc:
            _log.debug("domain_conn_failed err=%r", exc)
            conn = None
    if conn is None:
        rep["skipped"] = "pg_unavailable"
        return rep

    cur = None
    try:
        cur = conn.cursor()
        pend = pending_schemas(cur, cap)
        if not pend:
            rep["skipped"] = "no_requests"
            return rep
        try:
            from shared import config as _cfg
            model = str(getattr(_cfg, "AGENT_NODE_ANALYSIS_MODEL", "") or "")
        except Exception:
            model = ""
        for (scope_key, schema_name, prev_hash) in pend:
            if rep["synthesized"] >= cap:
                break
            if not _lb.allowed(conn):
                _log.info("도메인 합성 중단 — 백그라운드 LLM 토큰 예산 소진(다음 pass 재시도)")
                break
            rows = cluster_inputs(cur, scope_key, schema_name)
            if not rows:
                continue     # 클러스터 요약이 아직 없다 — 합성할 재료가 없다
            c_hash = cluster_set_hash(rows)
            if prev_hash and c_hash and str(prev_hash) == c_hash:
                continue     # 입력이 그대로면 다시 만들 이유가 없다
            payload = build_payload(scope_key, schema_name, rows)
            if not payload["groups"]:
                continue
            with _rb.acquire("llm") as _ok:
                if not _ok:
                    _log.info("도메인 합성 보류 — 공유 LLM 예산 여유 없음(다음 pass 재시도)")
                    break
                res = _synth_call(_llm, payload, scope_key)
            rep["attempted"] += 1
            summary = ""
            if isinstance(res, dict):
                summary = " ".join(str(res.get("summary") or "").split())
            if len(summary) < 30:
                continue     # 빈약한 응답은 저장하지 않는다(다음 pass 재시도)
            if store(cur, scope_key, schema_name, summary, payload, c_hash, model):
                rep["synthesized"] += 1
                _log.info("도메인 합성 완료 %s.%s (그룹 %s · 멤버 %s · 근거 %s)",
                          scope_key, schema_name, payload["cluster_count"],
                          payload["member_count"], payload["analyzed_count"])
    except Exception as exc:
        _log.warning("domain_synthesis pass 실패(다음 pass 재시도): %r", exc)
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if owned and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return rep


def _synth_call(_llm, payload, scope_key):
    """합성 LLM 1회. 예외는 None(다음 pass 재시도)."""
    try:
        return _llm.llm_domain_summary(payload, scope_key=scope_key)
    except Exception as exc:
        _log.warning("llm_domain_summary 실패(다음 pass 재시도): %r", exc)
        return None
