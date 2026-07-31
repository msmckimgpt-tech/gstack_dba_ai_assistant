"""analysis_planner — 분석 대상의 결정적 우선순위 선정 (feature-0035, ITEM-11).

**왜 필요한가.** 지금까지 분석 대상은 "사용자가 그래프 뷰에서 클릭한 노드 + 그 이웃"으로만
정해졌다. 그래서 커버리지가 중요도와 무관하게 편향된다 — 라이브 실측(2026-07-31):

    분석 완료 테이블  2,040 / 17,192  = **11.9%**

그 편향이 위층 전체의 품질 상한이 된다. 클러스터 요약(L2)의 85%가 "상세분석 근거 0"으로
생성되는 것도, 대화 grounding 에 주입되는 요약 대부분이 추정인 것도 같은 원인이다.
**아래 층의 커버리지를 중요도 순으로 채우면 위 세 층이 함께 올라간다.**

**왜 LLM 플래너가 아닌가.** 무엇을 분석할지 고르는 일에 LLM 은 필요 없다 — 신호가 이미 구조적
데이터로 있다(관계 차수, 대화에서 실제 조인된 이력). 결정적 규칙이 재현 가능하고, 비용이 0이며,
왜 그 테이블이 뽑혔는지 설명할 수 있다. LLM 이 값어치를 내는 자리는 계획이 아니라 분석과 합성이다.

**우선순위 신호** (둘 다 이미 있는 데이터 — AGE 실시간 중심성은 쓰지 않는다. multi-hop 이
라이브 최악 82초라 tick 안에서 감당할 수 없다):

1. **대화 조인 이력** (`table_relationships.source='conversation'`) — 사람이 실제 질문에서 이
   테이블을 조인해 썼다는 직접 증거. 가장 강한 신호라 가중치를 크게 둔다.
2. **관계 차수(degree)** — 선언된 FK + 학습된 관계에서 이 테이블이 등장하는 edge 수. 허브일수록
   먼저 이해해 두는 편이 이웃 분석의 맥락이 된다.

**이 모듈이 하지 않는 것**: 큐잉하지 않는다. 선정만 하고, 실제 시드는 검증된 경로
(`node_analysis.enqueue_change_analysis` — 자격·그래프 실재·cap·쿨다운·busy 가드가 이미 있다)에
맡긴다. 자동 LLM 지출의 안전장치를 두 번 구현하지 않는다.
"""
from __future__ import annotations

import logging
import re

_log = logging.getLogger("analysis_planner")

#: 대화 조인 이력 1건의 가중치. 관계 차수보다 훨씬 강한 신호다 — 사람이 실제로 그 테이블을
#: 질문에 썼다는 뜻이라, 분석해 두면 다음 질문에서 바로 값을 한다.
_W_CONVERSATION = 50

#: 관계 차수 1건의 가중치.
_W_DEGREE = 1

#: 후보 조회 상한 — 스키마 하나에 테이블이 수천 개인 경우 정렬 비용을 묶어둔다.
_CANDIDATE_CAP = 2000


def _rows(cur, sql, params):
    cur.execute(sql, params)
    return cur.fetchall() or []


def unanalyzed_tables(cur, datasource_key: str, eff_schema: str) -> list:
    """해당 스키마에서 **아직 분석되지 않은** 테이블명. 조회 실패는 빈 목록.

    ⚠ `rag_objects.schema_name` 으로 필터하지 않는다 — MSSQL 은 그 값이 리터럴 `dbo` 라 DB
    차원이 소실되고, 그래프 노드 키는 effective schema(=DB명)를 쓴다. 두 엔진 모두
    `object_key` 가 `<ds>:<db>.…` 로 시작하므로 그 prefix 로 맞추면 정확하다.

    ⚠ prefix 검사에 `LIKE` 를 쓰지 않는다 — datasource_key·스키마명에 `_` 가 흔한데(예
    `dk_data_release`) LIKE 는 그것을 "임의의 1문자" 와일드카드로 해석해 **다른 스키마의
    테이블이 섞인다**. `strpos(…) = 1` 은 순수 prefix 검사라 이스케이프가 필요 없다.
    """
    prefix = f"{datasource_key}:{eff_schema}."
    # ⚠ DISTINCT 필수(codex P1): `rag_objects` 유니크 키에 conversation_id 가 포함돼 같은
    #   테이블이 여러 행으로 존재할 수 있다. 중복을 그대로 두면 상한 3이 "Orders, Orders,
    #   Orders" 가 되어 **실제로는 한 테이블만** 시드된다(커버리지·우선순위 왜곡).
    return [str(r[0]) for r in _rows(
        cur,
        "SELECT DISTINCT o.table_name FROM rag_objects o "
        "WHERE o.datasource_key = %s AND o.object_type = 'table' "
        "  AND strpos(o.object_key, %s) = 1 "
        "  AND NOT EXISTS ("
        "        SELECT 1 FROM node_analysis_jobs j "
        "        WHERE j.node_key = %s || o.table_name AND j.status = 'done') "
        "LIMIT %s",
        (datasource_key, prefix, prefix, _CANDIDATE_CAP)) if r and r[0]]


def relationship_signals(cur, datasource_key: str) -> dict:
    """{table_name.casefold(): (edges, conversation_edges)}. 조회 실패는 빈 맵.

    양방향으로 센다 — 참조하는 쪽도 참조당하는 쪽도 그만큼 맥락에 얽혀 있다.

    ⚠ 스키마로 좁히지 않고 **datasource 단위**로 집계한다. `table_relationships` 의 schema 는
    원본이라 effective schema 와 어긋나고(MSSQL), 우선순위는 순위만 정하면 되는 근사 신호라
    같은 datasource 안의 동명 테이블이 합산되는 오차를 감수하는 편이 낫다 — 스키마를 잘못
    맞춰 **신호가 통째로 0이 되는 것**보다 훨씬 안전한 실패 방향이다.
    """
    out: dict = {}
    rows = _rows(
        cur,
        "SELECT tbl, COUNT(*) AS edges, "
        "       COUNT(*) FILTER (WHERE src = 'conversation') AS conv_edges FROM ("
        "   SELECT lower(source_table) AS tbl, source AS src FROM table_relationships "
        "    WHERE datasource_key = %s AND source_table IS NOT NULL "
        "   UNION ALL "
        "   SELECT lower(target_table), source FROM table_relationships "
        "    WHERE datasource_key = %s AND target_table IS NOT NULL "
        ") x GROUP BY tbl",
        (datasource_key, datasource_key))
    for tbl, edges, conv in rows:
        if tbl:
            out[str(tbl)] = (int(edges or 0), int(conv or 0))
    return out


#: 파티션·샤드 접미 감지 — 4자리 이상 연속 숫자(날짜 `20240425`, 연월 `202404`, 일련번호)만
#: 파티션으로 본다. 3자리 이하(`item2`, `log_01`)는 정당한 이름일 수 있어 건드리지 않는다.
_PARTITION_SUFFIX_RE = re.compile(r"^(?P<base>.+?)[_-]?\d{4,}$")


def partition_base(table_name: str) -> str:
    """파티션 계열의 베이스 이름. 접미 숫자를 **한 번만** 제거한다.

    `daily_league_ranking_20240425`   → `daily_league_ranking`
    `daily_league_ranking_1_20240425` → `daily_league_ranking_1`  (샤드 `_1` 은 보존)
    `tf_log_05_item`                  → 그대로(접미가 아니라 중간)

    ⚠ 반복 제거를 하지 않는다(codex P1): `foo_2024_2025` 를 `foo` 까지 깎으면 `foo_2024` 와
    `foo_2025` 가 **독립 테이블이어도 한 계열로 합쳐진다**. 잘못 합치면 실제 테이블이 영영
    분석되지 않으므로, 덜 깎아 계열이 조금 잘게 나뉘는 쪽이 안전한 실패 방향이다.
    """
    name = str(table_name or "")
    m = _PARTITION_SUFFIX_RE.match(name)
    if not m:
        return name
    base = m.group("base").rstrip("_-")
    return base or name


def collapse_partitions(tables, signals=None) -> list:
    """같은 파티션 계열은 **대표 1개**만 남긴다. 대표는 계열 내 **최고 점수**(동점은 이름 순).

    ⚠ load-bearing(라이브 실측): 어떤 datasource 는 테이블 1,464개 중 **1,364개(93%)가 날짜
    접미 파티션**이다. 관계 신호가 없는 스키마에서는 점수가 전부 0이라 선정이 이름 순으로
    퇴화하는데, 그때 축약이 없으면 **같은 구조의 파티션 수백 개를 반복 분석**하게 된다.
    커버리지 숫자만 오르고 실제 이해는 늘지 않으면서 토큰만 태우는 최악의 조합이다.

    ⚠ 대표를 이름 순으로 고르면 안 된다(codex P1): 계열 안에 대화 조인 이력이 있는 파티션이
    있어도 사전순 첫 번째에 밀려 **그 신호가 통째로 버려진다**. 축약은 하되 계열이 가진 가장
    강한 신호는 보존해야 한다.

    한 계열을 대표 하나로 분석해 두면 나머지는 그 분석문이 그대로 설명한다.
    """
    sig = signals or {}
    groups: dict = {}
    for t in sorted(str(x) for x in (tables or []) if x):
        groups.setdefault(partition_base(t), []).append(t)
    out = []
    for members in groups.values():
        if len(members) == 1:
            out.append(members[0])
            continue
        # members 는 이름 오름차순이므로 max 의 첫 최대값 반환이 곧 이름 순 tie-break 다.
        out.append(max(members, key=lambda m: score(m, sig)))
    return out


def score(table_name: str, signals: dict) -> int:
    """우선순위 점수. 신호가 없으면 0(= 이름 순 tie-break 로 밀린다)."""
    edges, conv = signals.get(str(table_name).casefold(), (0, 0))
    return conv * _W_CONVERSATION + edges * _W_DEGREE


def rank_targets(tables, signals: dict, limit: int) -> list:
    """(table_name, score) 상위 N. **결정적** — 동점은 이름 오름차순으로 가른다.

    동점 tie-break 가 없으면 tick 마다 다른 테이블이 뽑혀, 어떤 테이블은 영영 분석되지 않고
    어떤 테이블은 반복 시드된다.
    """
    scored = [(str(t), score(t, signals)) for t in (tables or []) if t]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:max(0, int(limit))]


def select_priority_targets(cur, datasource_key: str, eff_schema: str, limit: int) -> list:
    """중요도 상위 **미분석** 테이블의 node_key 목록. 어떤 실패도 빈 목록(fail-soft).

    반환 형식은 `node_analysis.enqueue_change_analysis` 가 받는 시드 키와 동일한
    `<datasource>:<eff_schema>.<table>` 이다.
    """
    if limit <= 0 or not datasource_key or not eff_schema:
        return []
    try:
        tables = unanalyzed_tables(cur, datasource_key, eff_schema)
        if not tables:
            return []
        signals = relationship_signals(cur, datasource_key)
    except Exception as exc:
        _log.debug("priority_select_failed ds=%s schema=%s err=%r",
                   datasource_key, eff_schema, exc)
        return []
    collapsed = collapse_partitions(tables, signals)
    ranked = rank_targets(collapsed, signals, limit)
    if not ranked:
        return []
    _log.info("분석 우선순위 선정 ds=%s schema=%s 미분석=%s 계열=%s 선정=%s 최고점=%s",
              datasource_key, eff_schema, len(tables), len(collapsed), len(ranked), ranked[0][1])
    return [f"{datasource_key}:{eff_schema}.{t}" for t, _s in ranked]


def enabled() -> bool:
    """자동 커버리지 확대 스위치 — 콘솔 live override 우선."""
    try:
        from shared import runtime_settings as _rts
        return bool(int(_rts.get_int("AGENT_ANALYSIS_COVERAGE_SEEDS")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return bool(int(getattr(_cfg, "AGENT_ANALYSIS_COVERAGE_SEEDS", 0) or 0))
    except Exception:
        return False


def cycle_limit() -> int:
    """**한 점검 사이클 전체**에 시드할 테이블 수 상한.

    ⚠ load-bearing(codex): 시드는 effective-schema 루프 안에서 일어나고 큐잉 경로의
    cap·쿨다운·busy 가드는 **스키마 단위**다. 사이클 상한이 없으면 스키마 수만큼 곱해져
    라이브(수백 스키마)에서 자동 지출이 폭주한다 — feature-0033 에서 같은 계열의 결함을
    지적받았고, 그때는 "검증된 경로를 쓰니 괜찮다"고 넘겼다가 여기서 다시 만났다.
    """
    try:
        from shared import runtime_settings as _rts
        return max(0, int(_rts.get_int("AGENT_ANALYSIS_COVERAGE_CYCLE_CAP")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return max(0, int(getattr(_cfg, "AGENT_ANALYSIS_COVERAGE_CYCLE_CAP", 0) or 0))
    except Exception:
        return 0


def seed_limit() -> int:
    """한 스키마에서 한 번에 시드할 테이블 수. 0 이면 비활성과 같다."""
    try:
        from shared import runtime_settings as _rts
        return max(0, int(_rts.get_int("AGENT_ANALYSIS_COVERAGE_SEED_CAP")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return max(0, int(getattr(_cfg, "AGENT_ANALYSIS_COVERAGE_SEED_CAP", 0) or 0))
    except Exception:
        return 0
