"""llm_budget — 백그라운드 LLM 토큰 예산 (feature-0032-llm-token-budget).

**왜 필요한가.** `TODOS.md` 의 LLM 비용 항목은 *"라이브 100% edge(로컬 Ollama) → per-token 과금
없음 → 일일 cap 가치 0"* 을 근거로 종결돼 있었다. 그 전제는 2026-07-30 실측에서 반전됐다:

    최근 7일  Anthropic(claude)  8,654 콜 / 55,567,176 토큰
              edge/기타             25 콜 /      30,404 토큰   → 과금 lane 99.7%

그중 사람 confirm 없이 나가는 **백그라운드** 소비가 약 2,600만 토큰/7일(일 평균 ≈371만)이다.
즉 지금은 자동 지출에 상한이 없다. 본 모듈이 그 상한을 만든다.

**설계 결정**

1. **rolling 24시간**으로 센다(자정 리셋 아님). 타임존 논쟁이 없고, 자정 직후 폭주가 재개되지
   않으며, 구현이 단순하다. knob 이름도 그대로 `..._TOKEN_CAP_24H` 다.
2. **사용자 요청 경로는 세지도 막지도 않는다.** 대화 답변(`agent`)·답변 자가검증(`redteam`)·
   대화 제목(`topic`)·원본 전환 분류(`classify`) 는 사람이 기다리는 호출이다. 예산으로 사용자를
   막으면 그건 비용 통제가 아니라 서비스 장애다.
3. **분류는 블랙리스트**다 — 사용자 경로 task 만 열거하고 나머지 전부를 백그라운드로 센다.
   화이트리스트면 새 백그라운드 작업이 조용히 예산 밖으로 새지만, 블랙리스트면 새 작업이 자동으로
   예산 안에 들어온다(보수적인 방향으로 틀린다).
4. **원천은 `agent_runtime.llm_usage`** — 이미 모든 호출이 기록되는 테이블이라 새 계측이 필요
   없다. 60초 TTL 캐시를 둬서 게이트가 매번 PG 를 때리지 않는다.
5. **fail-open** — 예산을 조회할 수 없으면 허용한다. 계량 실패가 백그라운드 정지로 번지면
   관측 장애가 기능 장애가 된다. 상한은 안전망이지 필수 경로가 아니다.

**게이트 커버리지 (정직하게)**: LLM 호출에 단일 choke-point 가 없어(`chat.completions.create`
가 15곳에서 직접 호출된다) 게이트는 백그라운드 **진입점**에 건다 — 노드 분석 tick · 클러스터
유지보수 pass · 제품 분류 pass. 이 셋이 백그라운드 소비의 약 96%(node_analysis + cluster_label)를
차지한다. 나머지(table/account/schema insight)는 **계량되지만 차단되지는 않는다**. 예산 표시가
"전체 소비"이고 차단이 "일부 경로"임을 콘솔 설명과 로그가 그대로 말한다.
"""
from __future__ import annotations

import logging
import threading
import time

_log = logging.getLogger("llm_budget")

#: 사람이 기다리는 호출 — 예산에서 제외하고 절대 차단하지 않는다.
#: (`llm.py` 의 `_record_llm_usage(model, task, ...)` 인자와 1:1 정합해야 한다.)
USER_FACING_TASKS = frozenset({"agent", "redteam", "topic", "classify", "prompt_gen"})

_WINDOW_SEC = 24 * 3600
_CACHE_TTL_SEC = 60.0
_DEFAULT_CAP = 20_000_000   # 실측 일 평균(≈371만)의 5배 남짓 — 정상 운영 무영향, 폭주만 잡는다

_LOCK = threading.Lock()
#: 조회는 한 번에 하나만 나간다(single-flight). 없으면 느린 조회가 나중에 끝나면서 더 최신인
#: 결과를 **과거 값으로 덮어써** 최대 TTL 동안 예산 초과를 허용한다(codex P1). 병렬 워커에서
#: 같은 순간 여러 tick 이 예산을 묻는 것이 정상 경로라 실제로 발생할 수 있는 race 다.
_INFLIGHT = threading.Lock()
_CACHE = {"at": 0.0, "spent": 0}


def cap() -> int:
    """예산 상한(토큰). 0 이하면 무제한(비활성)."""
    try:
        from shared import runtime_settings as _rts
        return max(0, int(_rts.get_int("AGENT_BACKGROUND_LLM_TOKEN_CAP_24H")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return max(0, int(getattr(_cfg, "AGENT_BACKGROUND_LLM_TOKEN_CAP_24H", _DEFAULT_CAP)))
    except Exception:
        return _DEFAULT_CAP


def _query_spent(conn=None) -> int:
    """rolling 24시간 백그라운드 토큰 소비. 조회 불가면 `-1`(=판정 불가)."""
    own = False
    c = conn
    try:
        if c is None:
            from shared import db as _db
            c = _db._pg_connect_ro()
            own = c is not None
        if c is None:
            return -1
        cur = c.cursor()
        try:
            cur.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) FROM agent_runtime.llm_usage "
                "WHERE created_at > now() - make_interval(secs => %s) "
                "  AND COALESCE(task, '') <> ALL(%s)",
                (_WINDOW_SEC, list(USER_FACING_TASKS)))
            row = cur.fetchone()
            return int((row or [0])[0] or 0)
        finally:
            try:
                cur.close()
            except Exception:
                pass
    except Exception as exc:
        _log.debug("llm_budget_query_failed err=%r", exc)
        return -1
    finally:
        if own and c is not None:
            try:
                c.close()
            except Exception:
                pass


def spent(conn=None, *, refresh: bool = False) -> int:
    """캐시된 rolling 24h 백그라운드 소비(토큰). 판정 불가면 `-1`.

    동시 호출은 single-flight 로 직렬화한다 — 조회가 진행 중이면 기다리지 않고 직전 캐시를
    쓴다(캐시가 없으면 `-1` = fail-open). 이렇게 하면 (a) 느린 조회가 최신 결과를 덮어쓰는
    race 가 구조적으로 불가능하고, (b) 병렬 워커가 같은 순간 예산을 물어도 PG 조회는 하나다.
    """
    now = time.monotonic()
    with _LOCK:
        has_cache = bool(_CACHE["at"])
        cached = int(_CACHE["spent"])
        fresh = has_cache and (now - _CACHE["at"]) < _CACHE_TTL_SEC
    if not refresh and fresh:
        return cached
    # 이미 다른 스레드가 조회 중이면 그 결과를 기다리지 않는다 — 게이트는 tick 마다 불리므로
    # 블로킹하면 워커가 서로를 붙잡는다. 살짝 낡은 값으로 판정하고 다음 tick 에 정확해진다.
    if not _INFLIGHT.acquire(blocking=False):
        return cached if has_cache else -1
    try:
        value = _query_spent(conn)
        if value < 0:
            return -1
        with _LOCK:
            _CACHE["at"] = time.monotonic()
            _CACHE["spent"] = value
        return value
    finally:
        _INFLIGHT.release()


def allowed(conn=None) -> bool:
    """백그라운드 LLM 작업을 시작해도 되는지.

    fail-open: 상한이 0(무제한)이거나 소비를 조회할 수 없으면 True. 상한은 안전망이지
    필수 경로가 아니다 — 계량 장애가 기능 정지로 번지지 않게 한다."""
    limit = cap()
    if limit <= 0:
        return True
    used = spent(conn)
    if used < 0:
        return True
    return used < limit


def snapshot(conn=None) -> dict:
    """콘솔·로그용 현황. `spent` 가 음수면 판정 불가(계량 실패).

    상한이 0(무제한)이면 소비를 조회하지 않는다 — `allowed()` 와 같은 계약이다. 관리 API 가
    상한 비활성 상태에서도 PG 를 때리면 PG 장애가 콘솔 지연으로 번진다(codex P2)."""
    limit = cap()
    if limit <= 0:
        return {"window_sec": _WINDOW_SEC, "cap": 0, "spent": 0,
                "enabled": False, "measurable": True, "exhausted": False}
    used = spent(conn)
    out = {
        "window_sec": _WINDOW_SEC,
        "cap": limit,
        "spent": used,
        "enabled": limit > 0,
        "measurable": used >= 0,
    }
    if limit > 0 and used >= 0:
        out["remaining"] = max(0, limit - used)
        out["used_ratio"] = round(used / limit, 4)
        out["exhausted"] = used >= limit
    else:
        out["exhausted"] = False
    return out


def invalidate() -> None:
    """캐시 무효화 — 상한 변경 직후 즉시 반영이 필요한 경로용."""
    with _LOCK:
        _CACHE["at"] = 0.0
        _CACHE["spent"] = 0
