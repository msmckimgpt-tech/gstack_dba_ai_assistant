"""cluster_context — L2 클러스터 요약을 대화 답변 grounding 에 주입 (feature-0034, ITEM-09).

**왜 필요한가.** 라이브에 노드 분석문이 1만여 건, 클러스터 요약이 쌓이고 있는데 **대화 답변
경로가 그것을 읽지 않았다**(`kb_retrieval`/`knowledge` 에서 `node_analysis`·`cluster_summaries`
참조 0). 분석의 가치가 관리 콘솔 열람에만 갇혀 있었다 — 진단에서 RI-5 로 잡힌 공백이다.

**무엇을 주입하나.** 질문이 언급한 테이블이 속한 클러스터의 요약 1~2건. 개별 테이블 설명
(`TABLE & COLUMN DESCRIPTIONS`)이 "이 테이블이 무엇인가"라면, 이것은 **"이 테이블이 속한 묶음이
함께 무엇을 하는가"** 다. 조인 상대를 고르거나 도메인 맥락을 잡을 때 필요한 층이다.

**설계 결정**

1. **사전 계산분만 주입한다.** 런타임 합성은 하지 않는다 — feature-0027 이 확보한 체감 지연
   개선을 잠식하면 안 된다. 요약이 없으면 섹션 자체를 생략한다.
2. **매칭은 라벨 조인**이다. `cluster_summaries` 는 `member_set_hash` 로 키가 잡혀 있고
   `rag_objects` 는 `semantic_cluster_id` 만 갖는데, 그 id 는 pass 마다 재부여되어 churn 한다.
   반면 `semantic_cluster_label` 은 `_disambiguate_labels` 로 스키마 내 유일하게 만들어지고
   양쪽 저장소에 모두 있다 — 그래서 라벨이 안정적인 조인 키다.
3. **근거 수를 함께 싣는다.** `analyzed_count/member_count` 를 요약 옆에 붙인다. 라이브 실측상
   요약의 85%가 상세분석 근거 0으로 생성됐다(이름 규칙 기반). 그 사실을 숨기면 LLM 이 요약을
   실측 결론으로 오독한다.
4. **fail-soft.** 조회 실패·테이블 부재·타임아웃은 빈 문자열(섹션 생략). 답변 경로에 있는
   코드라 어떤 실패도 답변을 막아서는 안 된다.
"""
from __future__ import annotations

import logging

_log = logging.getLogger("cluster_context")

#: 주입할 요약 수 상한. 답변 프롬프트에서 이 섹션이 다른 grounding 을 밀어내지 않게.
_DEFAULT_LIMIT = 2

#: 매칭에 쓸 테이블명 최소 길이 — 짧은 이름("id", "log")이 질문 아무 데나 걸려 오탐하는 것을 막는다.
_MIN_TABLE_NAME_LEN = 4

#: 요약 본문 절단(문자). 2~4문장 계약이라 넉넉하다.
_SUMMARY_CLIP = 700

#: 조회 상한 — 답변 경로이므로 느려지면 주입을 포기하는 편이 낫다.
_STATEMENT_TIMEOUT_MS = 1500

#: 1단계(테이블 매칭)에서 끌어올 행 상한. 질문에 테이블명이 수십 개 등장하는 일은 없고,
#: 상한이 없으면 짧은 이름이 광범위 매칭될 때 2단계 IN 절이 비대해진다.
_MATCH_ROW_CAP = 200


def _ro_conn(conn):
    """(conn, owned). 읽기 전용 연결 — 실패하면 (None, False)."""
    if conn is not None:
        return conn, False
    try:
        from shared import db as _db
        c = _db._pg_connect_ro()
        return c, (c is not None)
    except Exception as exc:
        _log.debug("cluster_context_conn_failed err=%r", exc)
        return None, False


def _scope_candidates(scope_key):
    """활성 datasource 후보. 미지정이면 설정에서 도출(`relationships` 와 동형)."""
    if scope_key:
        return [str(scope_key)]
    try:
        from shared import config as _cfg
        active = _cfg.get_active_datasource()
        return [str(active)] if active else []
    except Exception:
        return []


def effective_schema(datasource_key, object_key, schema_name) -> str:
    """`cluster_summaries.schema_name` 이 쓰는 **effective schema** 를 유도한다.

    MSSQL 은 `rag_objects.schema_name` 이 리터럴 'dbo' 라 DB 차원이 소실되고, 클러스터링은
    object_key 의 DB명을 스키마로 쓴다. 즉 `rag_objects.schema_name` 을 그대로 조인하면
    MSSQL 에서 **한 건도 매칭되지 않는다**.

    ⚠ `semantic_cluster._effective_schema` 와 **동형이어야 한다**(테스트가 두 구현의 일치를
    단정한다). 여기에 복제해 둔 이유는 답변 경로에서 무거운 클러스터링 모듈을 import 하지
    않기 위해서다.
    """
    ok = object_key or ""
    pref = f"{datasource_key or ''}:"
    if ok.startswith(pref):
        ok = ok[len(pref):]
    parts = [p for p in ok.split(".") if p] if ok else []
    if len(parts) >= 2:
        return parts[0]
    return schema_name or ""


def _matched_clusters(cur, user_message: str, scopes) -> list:
    """질문이 언급한 테이블의 `(scope, effective_schema, label)` 조합. 중복 제거·정렬(결정적).

    매칭은 **질문 문자열 안에 테이블명이 등장하는가**로 본다(`load_relationship_context` 와 동형).
    `strpos` 를 쓰는 이유: ILIKE 는 테이블명의 `_`(예 `backup_log_trade`)를 "임의의 1문자"
    와일드카드로 해석해 `backup-log-trade` 같은 문자열에도 걸린다.
    """
    cur.execute(
        "SELECT DISTINCT o.datasource_key, o.schema_name, o.object_key, o.semantic_cluster_label "
        "FROM rag_objects o "
        "WHERE o.datasource_key = ANY(%s) "
        "  AND o.semantic_cluster_label IS NOT NULL "
        "  AND o.semantic_cluster_label <> '' "
        "  AND length(o.table_name) >= %s "
        "  AND strpos(lower(%s), lower(o.table_name)) > 0 "
        # ⚠ 정렬 없는 LIMIT 은 **어느 200행이 오는지 비결정적**이다. 테이블명 하나가 24개
        #   eff-schema(DB 사본군 cc_data_main/cc_data_test/cc_dbrestore_*/cc_obt …)에 걸리는
        #   라이브에서는 상한에 실제로 닿고, 그때 같은 질문이 매번 다른 근거를 받는다.
        "ORDER BY o.datasource_key, o.object_key, o.semantic_cluster_label "
        "LIMIT %s",
        (list(scopes), _MIN_TABLE_NAME_LEN, user_message, _MATCH_ROW_CAP))
    seen = set()
    for ds, schema, object_key, label in cur.fetchall() or ():
        eff = effective_schema(ds, object_key, schema)
        if eff and label:
            seen.add((str(ds), str(eff), str(label)))
    return sorted(seen)


def fetch_summaries(conn, user_message: str, scopes, limit: int) -> list:
    """질문이 언급한 테이블의 클러스터 요약 rows. 조회 실패는 빈 목록.

    2단계로 나눈 이유: `cluster_summaries` 의 식별자는 `(scope_key, schema_name, …)` 이고 그
    `schema_name` 은 **effective schema** 다. SQL 한 방으로 조인하려면 그 유도 규칙을 SQL 로
    재현해야 하는데, 파이썬에서 계산하는 편이 정확하고 읽기 쉽다. 두 쿼리 모두 가볍다.
    """
    if not scopes or not user_message:
        return []
    # ⚠ `cursor()` 도 try **안**에서 얻는다 — 밖에 두면 커넥션이 죽었을 때 예외가 답변 경로로
    #   그대로 전파된다(feature-0031 의 connect 배치와 같은 계열). 이 함수는 사용자가 기다리는
    #   경로에 있으므로 어떤 실패도 답변을 막아서는 안 된다.
    cur = None
    timeout_set = False
    try:
        cur = conn.cursor()
        # ⚠ `SET LOCAL` 은 트랜잭션 안에서만 유효하고 RO 연결은 autocommit 이라 무효다(codex P1).
        #   세션 레벨 `SET` 을 걸고 finally 에서 되돌린다 — 호출측이 준 커넥션이면 설정이
        #   누출되면 안 되므로 RESET 이 짝을 이룬다.
        try:
            cur.execute("SET statement_timeout = %s", (_STATEMENT_TIMEOUT_MS,))
            timeout_set = True
        except Exception:
            timeout_set = False
        keys = _matched_clusters(cur, user_message, scopes)
        if not keys:
            return []
        cur.execute(
            # schema_name 을 함께 읽는다 — 라벨은 datasource 안에서 유일하지 않다(라이브: `메일
            #   시스템` 9개 스키마 · `길드 관리` 8개). 스키마를 빼고 렌더하면 서로 다른 DB 의
            #   같은 이름 클러스터 요약이 구분 없이 나란히 실려, 모델이 한 DB 의 사실로 읽는다.
            "SELECT label, summary, member_count, analyzed_count, schema_name "
            "FROM cluster_summaries "
            "WHERE (scope_key, schema_name, label) IN "
            "      (SELECT * FROM unnest(%s::text[], %s::text[], %s::text[])) "
            # member_set_hash 를 최종 tie-breaker 로 — (label, member_count, analyzed_count) 가
            #   완전 동률인 그룹이 라이브에 실재해(`일일 경험치 · dayexp` mc79/ac0 ×2) 그것 없이는
            #   같은 질문이 매번 다른 행을 받는다.
            "ORDER BY analyzed_count DESC, member_count DESC, label, member_set_hash "
            "LIMIT %s",
            ([k[0] for k in keys], [k[1] for k in keys], [k[2] for k in keys],
             max(1, int(limit))))
        return cur.fetchall() or []
    except Exception as exc:
        _log.debug("cluster_summary_fetch_failed err=%r", exc)
        return []
    finally:
        if cur is not None:
            if timeout_set:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    pass
            try:
                cur.close()
            except Exception:
                pass


def _domain_line(cur, scope_key, eff_schemas) -> str:
    """feature-0037(L3): 매칭된 스키마의 **도메인 요약** 한 줄. 없으면 요청만 남기고 빈 문자열.

    ⚠ 여기서 합성하지 않는다 — 답변 경로에 LLM 을 부르면 체감 지연을 잠식한다(ADR-0034-07).
    요청만 기록하면 insight tick 이 다음 주기에 만들고, 그 다음 질문부터 실린다. 아무도 찾지
    않은 스키마는 영원히 만들어지지 않는다(사전 전량 생성 회피).
    """
    try:
        from . import domain_synthesis as _ds
    except Exception:
        return ""
    for eff in list(eff_schemas)[:2]:
        try:
            got = _ds.load(cur, scope_key, eff)
        except Exception:
            got = {}
        if got.get("summary"):
            basis = (f"그룹 {got.get('cluster_count', 0)}개 · 멤버 {got.get('member_count', 0)}개 중 "
                     f"{got.get('analyzed_count', 0)}개 상세분석 근거")
            return f"- [{eff} 전체] ({basis}) {got['summary']}"
        _record_request(scope_key, eff)
    return ""


def _record_request(scope_key, eff_schema) -> None:
    """도메인 요약 요청을 남긴다 — **요약이 없을 때만** 불린다.

    ⚠ 조회에 쓰는 커넥션은 읽기 전용(`agent_kb_ro` = SELECT only)이라 여기서 쓸 수 없다.
    요청 기록은 작은 UPSERT 1회이고, 요약이 이미 있으면 아예 오지 않으므로 정상 경로에서는
    쓰기가 발생하지 않는다. 실패는 조용히 무시한다 — 요청을 못 남기면 다음 질문이 다시 남긴다.
    """
    try:
        from . import domain_synthesis as _ds
        from shared import db as _db
    except Exception:
        return
    conn = None
    try:
        conn = _db._pg_connect()
        if conn is None:
            return
        cur = conn.cursor()
        try:
            _ds.request(cur, scope_key, eff_schema)
        finally:
            try:
                cur.close()
            except Exception:
                pass
    except Exception as exc:
        _log.debug("domain_request_skipped %s.%s err=%r", scope_key, eff_schema, exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def load_cluster_summary_context(user_message, scope_key=None, conn=None,
                                 limit: int = _DEFAULT_LIMIT) -> str:
    """질문에 매칭되는 클러스터 요약을 프롬프트 본문으로 조립. 매칭 0건이면 빈 문자열.

    헤더·datamark 는 호출측(`_build_knowledge_context`)이 부여한다(다른 grounding 로더와 동형).
    """
    if not enabled():
        return ""
    msg = str(user_message or "").strip()
    if not msg:
        return ""
    scopes = _scope_candidates(scope_key)
    if not scopes:
        return ""
    c, owned = _ro_conn(conn)
    if c is None:
        return ""
    domain_line = ""
    try:
        rows = fetch_summaries(c, msg, scopes, limit)
        # feature-0037: 매칭된 스키마의 도메인(L3) 요약도 함께 — 그룹 요약이 "이 묶음"이라면
        #   이것은 "이 DB 전체"다. 없으면 요청만 남긴다(합성은 백그라운드).
        try:
            cur = c.cursor()
            try:
                effs = _matched_effective_schemas(cur, msg, scopes)
                if effs:
                    domain_line = _domain_line(cur, scopes[0], effs)
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
        except Exception:
            domain_line = ""
    finally:
        if owned:
            try:
                c.close()
            except Exception:
                pass
    body = render(rows, limit)
    if domain_line:
        return f"{domain_line}\n{body}" if body else domain_line
    return body


def _matched_effective_schemas(cur, user_message, scopes) -> list:
    """질문이 언급한 테이블이 속한 effective schema 목록(결정적 정렬)."""
    try:
        return sorted({k[1] for k in _matched_clusters(cur, user_message, scopes)})
    except Exception:
        return []


def render(rows, limit: int = _DEFAULT_LIMIT) -> str:
    """rows → 프롬프트 조각. 근거 수를 반드시 함께 적는다.

    라이브 실측상 요약의 85%가 상세분석 근거 0(이름 규칙 기반)이다. 근거 수를 숨기면 LLM 이
    요약을 실측 결론으로 오독하고, 그 오독이 사용자 답변에 그대로 실린다.
    """
    out = []
    for r in (rows or [])[:max(1, int(limit))]:
        try:
            label = str(r[0] or "").strip()
            summary = " ".join(str(r[1] or "").split())[:_SUMMARY_CLIP]
            member_count = int(r[2] or 0)
            analyzed_count = int(r[3] or 0)
        except (IndexError, TypeError, ValueError):
            continue
        # 5번째 원소(schema_name)는 선택 — 없으면 기존 형태로 렌더한다(하위호환).
        try:
            schema = str(r[4] or "").strip()
        except (IndexError, TypeError):
            schema = ""
        if not label or not summary:
            continue
        if analyzed_count > 0:
            basis = f"멤버 {member_count}개 중 {analyzed_count}개 상세분석 근거"
        else:
            basis = f"멤버 {member_count}개 · 상세분석 근거 없음(이름·구조 기반 추정)"
        # 스키마를 앞에 **따로** 붙인다 — 라벨 자체가 `_disambiguate_labels` 로 `" · "` 를 품기
        #   때문에(`일일 경험치 · dayexp`) 같은 구분자로 이으면 스키마 경계가 소실된다.
        #   5번째 원소가 없으면 기존 형태(하위호환).
        head = f"[{schema}] {label}" if schema else f"[{label}]"
        out.append(f"- {head} ({basis}) {summary}")
    return "\n".join(out)


def enabled() -> bool:
    """주입 스위치 — 콘솔 live override 우선. 조회 실패는 config 기본값."""
    try:
        from shared import runtime_settings as _rts
        return bool(int(_rts.get_int("AGENT_CLUSTER_SUMMARY_GROUNDING")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return bool(int(getattr(_cfg, "AGENT_CLUSTER_SUMMARY_GROUNDING", 1) or 0))
    except Exception:
        return False
