"""feature-0016 graphux5: 그래프 노드 AI 능동 분석 — 재귀 탐색 + 백그라운드 처리.

관리콘솔 그래프뷰 상세 패널의 "AI 능동 분석" 버튼이 `enqueue_analysis()` 로 run 을 만들고 루트 노드를
pending 잡으로 넣는다. insight-worker 틱이 `process_pending()` 으로 pending 잡을 소량씩 소비하며(부하
분산), 노드마다 이웃 컨텍스트를 모아 LLM 분석문을 생성·저장하고, 방문하지 않은 이웃을 (예산 내)
pending 으로 재큐한다 — 이렇게 **선택 노드에서 시작해 관련 노드를 재귀적으로 탐색**한다.

설계 원칙 (metadata_graph.py 동형):
  - 저장소 = agent_kb PG 의 node_analysis_runs / node_analysis_jobs (alembic 0028, relevance 0029).
  - 연결은 shared.db._pg_connect(RW). PG 미가용·예외 시 no-op — 코어 흐름 절대 비차단.
  - **비용 경계(사용자 결정 2026-07-01)**: run 마다 depth_budget/node_budget 로 재귀를 캡하고,
    UNIQUE(run_id,node_key) 로 dedupe 한다. "관련된 모든 노드"의 무한 확장(LLM 비용 폭증) 방지.
  - 그래프 컨텍스트/이웃은 metadata_graph.neighborhood(depth=1) 재사용.
  - **앵커-상대 관련도(node-analysis-anchor, 2026-07-01)**: 재귀는 방문 노드의 인접성이 아니라
    **원래 분석 대상(루트=anchor)** 과의 관련도로 이웃을 게이트·우선순위화한다. 허브(일반 컬럼 UniqueID·
    부모 Schema)를 새 중심으로 무관 노드까지 fan-out 하던 문제를 차단한다. 루트 직속 컬럼은 기본 분석
    (게이트 면제), 그 외는 관련도 임계 이상만 재귀(깊을수록 임계 상향), relevance 로 우선순위 정렬.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid

from shared import config as _cfg

_log = logging.getLogger("node_analysis")


# ── 테이블 역할 분류 (feature-0016 node-role-viz, 2026-07-02) ─────────────────
# 그래프 뷰에서 "AI 능동 분석 완료" 테이블 노드에 역할을 시각 표식(역할색·아이콘·범례)으로 명시하기
# 위한 고정 분류체계. 고전 DB 테이블 분류(master/reference/transaction/history)를 게임 운영 DB 에
# 맞게 8종으로 조정 — FE(_META_ROLE, admin.js)·LLM 계약(NODE_ANALYSIS_PROMPT "role")과 1:1 정합.
NODE_ROLES = ("master", "account", "transaction", "log", "mapping", "config", "stats", "etc")

# 휴리스틱 분류 규칙 — (role, 이름 토큰, 본문(요약·활용) 키워드). **순서 = 우선순위**:
#   log 를 transaction 보다 먼저 봐야 PurchaseLog 류가 log 로 잡힌다. 이름 신호가 본문 신호보다
#   우선(2-pass) — 이름이 도메인 관례(…Log, …Config)를 가장 신뢰도 높게 드러낸다.
_ROLE_RULES = (
    ("log", ("log", "logs", "hist", "history", "audit", "trace"),
     ("로그", "이력", "감사")),
    ("stats", ("stat", "stats", "rank", "ranking", "agg", "summary", "daily", "weekly", "monthly"),
     ("통계", "집계", "랭킹", "순위", "스냅샷")),
    ("config", ("config", "conf", "setting", "settings", "option", "options", "env", "param", "params"),
     ("설정", "옵션", "파라미터", "환경값")),
    ("mapping", ("map", "mapping", "link", "bridge", "xref", "junction"),
     ("매핑", "다대다", "n:m", "교차 참조", "연결 테이블")),
    ("account", ("user", "users", "member", "account", "char", "character", "player", "avatar"),
     ("계정", "유저", "사용자", "회원", "캐릭터", "플레이어")),
    ("transaction", ("order", "pay", "payment", "purchase", "buy", "sell", "trade", "reward",
                     "billing", "cash", "gacha", "txn", "transaction"),
     ("결제", "구매", "지급", "거래", "주문", "보상", "판매", "청구")),
    ("master", ("master", "code", "codes", "define", "def", "dict", "meta", "item", "items", "release"),
     ("정의", "기준정보", "마스터", "사전", "코드표", "기준 테이블")),
)


def _role_valid(role) -> str | None:
    r = str(role or "").strip().lower()
    return r if r in NODE_ROLES else None


def classify_role_heuristic(name, fqn, analysis=None) -> str:
    """테이블명·분석문 키워드 기반 역할 추정 — LLM role 누락 폴백 + 기존 done 행 백필용(LLM 재호출 없음).

    1-pass: 이름(name + fqn 마지막 세그먼트) 토큰을 _ROLE_RULES 우선순위대로 매칭.
    2-pass: 이름 무매칭 시 분석문(summary/usage/relationships) 본문 키워드 매칭. 둘 다 없으면 'etc'.
    """
    name_tokens = set(_split_tokens(name)) | set(_split_tokens((fqn or "").rsplit(".", 1)[-1]))
    for role, name_keys, _text_keys in _ROLE_RULES:
        if name_tokens & set(name_keys):
            return role
    text = ""
    if isinstance(analysis, dict):
        text = " ".join(str(analysis.get(k) or "") for k in ("summary", "usage", "relationships"))
    elif analysis:
        text = str(analysis)
    if text:
        low = text.lower()
        for role, _name_keys, text_keys in _ROLE_RULES:
            if any(k in low for k in text_keys):
                return role
    return "etc"


def _resolve_role(node_label: str, llm_obj, node_name, node_fqn) -> str | None:
    """저장할 role 결정 — Table 노드만 분류(그 외 NULL). LLM 값 우선, 무효/누락은 휴리스틱 폴백."""
    if (node_label or "") != "Table":
        return None
    role = _role_valid(llm_obj.get("role") if isinstance(llm_obj, dict) else None)
    if role:
        return role
    return classify_role_heuristic(node_name, node_fqn, llm_obj if isinstance(llm_obj, dict) else None)


# 마이그레이션 창 방어(적대 패널 B1): role 컬럼(alembic 0031) 미적용 DB + 신 코드 조합(롤링 순서 실수·
# 롤백에서 downgrade 를 코드 revert 보다 먼저 실행)에서 role 참조 쿼리가 UndefinedColumn 으로 죽으면 —
# (a) 분석 파이프라인이 LLM 비용 소진 후 전건 terminal-failed, (b) run 폴링이 404 로 오표시된다.
# 각 쿼리 지점이 실패 시 role 미포함 legacy 쿼리로 1회 폴백해 창 안에서도 기능을 보존한다(role 만 생략).
# 경고는 프로세스당 1회(로그 홍수 방지). autocommit 연결(기본)에서 실패 statement 는 트랜잭션을 오염시키지
# 않으므로 폴백 재실행이 안전하다(비-autocommit 주입 conn 은 폴백도 실패 → 기존 예외 경로와 동일 강도).
_ROLE_COL_WARNED = {"done": False}


def _warn_role_column_once(where: str, exc) -> None:
    if not _ROLE_COL_WARNED["done"]:
        _ROLE_COL_WARNED["done"] = True
        _log.warning("node_analysis role 컬럼 접근 실패(%s) — alembic 0031 미적용 창으로 보고 legacy 폴백. err=%r",
                     where, exc)


# user_prompt(alembic 0034, ADR-017) 마이그레이션 창 방어 — role 컬럼(B1)과 동형 legacy 폴백.
_UPROMPT_COL_WARNED = {"done": False}


# anchor_key/pass_no(alembic 0038, §55 refine) 마이그레이션 창 방어 — 컬럼 가용성을 프로세스당 1회
# probe 해 캐시한다. _enqueue_neighbors 는 명시 트랜잭션 안에서 INSERT 하므로(실패 statement 가
# 트랜잭션을 오염) per-statement try/except 폴백이 불가 — 트랜잭션 진입 **전** probe 로 SQL 을 선택한다.
_REFINE_COLS = {"ok": None, "warned": False}


def _refine_cols_ok(cur) -> bool:
    if _REFINE_COLS["ok"] is None:
        try:
            cur.execute("SELECT anchor_key, pass_no FROM node_analysis_jobs LIMIT 0")
            cur.fetchall()
            _REFINE_COLS["ok"] = True
        except Exception as exc:
            msg = f"{exc.__class__.__name__} {exc}".lower()
            # §55 패널 fix: **컬럼 부재(0038 미적용 창)일 때만** False 를 캐시한다 — transient(연결 끊김·
            # 타임아웃 등) 오류를 영구 캐시하면 프로세스 수명 내내 §55 기능이 silent 비활성으로 남는다.
            # transient 는 캐시 없이 이번 호출만 legacy(다음 호출 재-probe).
            permanent = ("undefinedcolumn" in msg) or ("column" in msg and (
                "does not exist" in msg or "존재하지 않" in msg))
            if not _REFINE_COLS["warned"]:
                _REFINE_COLS["warned"] = True
                _log.warning("node_analysis anchor_key/pass_no probe 실패(%s) — %s. err=%r",
                             "영구: 0038 미적용 창" if permanent else "일시: 다음 tick 재시도",
                             "legacy 동작(단일 앵커·refine 비활성) 폴백", exc)
            if permanent:
                _REFINE_COLS["ok"] = False
            else:
                return False   # 미캐시 — 다음 호출 재-probe
    return bool(_REFINE_COLS["ok"])


def _warn_uprompt_column_once(where: str, exc) -> None:
    if not _UPROMPT_COL_WARNED["done"]:
        _UPROMPT_COL_WARNED["done"] = True
        _log.warning("node_analysis user_prompt 컬럼 접근 실패(%s) — alembic 0034 미적용 창으로 보고 legacy 폴백. err=%r",
                     where, exc)


# ── 일시 실패 재시도 (analysis-retry-resilience, 사용자 리포트 2026-07-30) ─────
# attempts/next_attempt_at/error_kind(alembic 0049) 가용성을 프로세스당 1회 probe 해 캐시한다.
# _refine_cols_ok 와 동형 — **컬럼 부재(0049 미적용 창)일 때만 False 를 캐시**하고 transient 오류는
# 캐시하지 않는다(캐시하면 프로세스 수명 내내 재시도 기능이 silent 비활성으로 남는다).
_RETRY_COLS = {"ok": None, "warned": False, "checked_at": 0.0}
# codex P2-1: **False 를 영구 캐시하지 않는다.** 배포 스파인에서 워커가 0049 적용 *전에* 기동되면
#   여기서 False 가 잡히는데, 영구 캐시면 마이그레이션이 끝난 뒤에도 프로세스 수명 내내 재시도가
#   silent 비활성으로 남아(= 이 cycle 이 고친 결함이 그대로 재발) 다음 재배포까지 회복되지 않는다.
#   그래서 부재 판정은 아래 간격 뒤 재-probe 한다(성공 True 는 영구 — 컬럼이 사라지는 일은 없다).
_RETRY_COLS_RECHECK_SEC = 600

#: T0 공유 LLM 예산 거절 시 재예약 간격(초). transient backoff(60s 지수)보다 짧다 — 예산 거절은
#: 장애가 아니라 순번 대기이므로 다음 여유가 생기면 곧 처리되어야 한다.
_BUDGET_DEFER_SEC = 30


def _retry_cols_ok(cur) -> bool:
    if _RETRY_COLS["ok"] is False:
        if (time.time() - float(_RETRY_COLS.get("checked_at") or 0.0)) < _RETRY_COLS_RECHECK_SEC:
            return False
        _RETRY_COLS["ok"] = None       # 재-probe 대상으로 되돌림(마이그레이션 완료 흡수)
    if _RETRY_COLS["ok"] is None:
        _RETRY_COLS["checked_at"] = time.time()
        try:
            cur.execute("SELECT attempts, next_attempt_at, error_kind FROM node_analysis_jobs LIMIT 0")
            cur.fetchall()
            _RETRY_COLS["ok"] = True
        except Exception as exc:
            msg = f"{exc.__class__.__name__} {exc}".lower()
            permanent = ("undefinedcolumn" in msg) or ("column" in msg and (
                "does not exist" in msg or "존재하지 않" in msg))
            if not _RETRY_COLS["warned"]:
                _RETRY_COLS["warned"] = True
                _log.warning("node_analysis attempts/next_attempt_at probe 실패(%s) — %s. err=%r",
                             "영구: 0049 미적용 창" if permanent else "일시: 다음 tick 재시도",
                             "legacy 동작(일시 실패도 즉시 terminal) 폴백", exc)
            if permanent:
                _RETRY_COLS["ok"] = False
            else:
                return False   # 미캐시 — 다음 호출 재-probe
    return bool(_RETRY_COLS["ok"])


def _retry_cfg() -> dict:
    """재시도·회로차단 knob 해석(런타임 설정 override 없음 — env/config 정본)."""
    return {
        "max_attempts": max(1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_MAX_ATTEMPTS", 4) or 1)),
        "base_sec": max(1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_RETRY_BASE_SEC", 60) or 1)),
        "max_sec": max(1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_RETRY_MAX_SEC", 600) or 1)),
        "circuit_fails": max(0, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_CIRCUIT_FAILS", 3) or 0)),
    }


# 회로차단(B): 연속 일시 실패 카운터. **프로세스 로컬** — 워커 재시작 시 리셋되지만, 그때는 다음
# 실패가 즉시 다시 채우므로 안전 방향으로만 틀린다(과도 차단 없음). PG 영속을 피한 이유는 이
# 신호가 "지금 이 워커에서 LLM 왕복이 되는가" 라는 프로세스-국소 사실이기 때문.
_CIRCUIT = {"fails": 0}


def _circuit_open(cfg: dict) -> bool:
    """연속 일시 실패가 임계에 도달했거나 provider health 가 restricted 면 True(=canary 로 축소)."""
    th = int(cfg.get("circuit_fails") or 0)
    if th and int(_CIRCUIT["fails"]) >= th:
        return True
    # 보조 신호: 다른 경로(대화 답변 등)가 이미 provider 제한을 관측했으면 그것도 존중한다.
    #   health 모듈/PG 미가용은 무시(자체 카운터만으로 동작 — 신호 부재가 차단을 만들지 않음).
    try:
        from modules import llm_provider_health as _health
        st = _health.read_provider_health() or {}
        if str(st.get("state") or "") == _health.STATE_RESTRICTED:
            return True
    except Exception:
        pass
    return False


# ── 앵커-상대 관련도 (feature-0016 node-analysis-anchor) ──────────────────────
# 일반어(도메인 식별력 없는 토큰) — 이름이 이것만 겹치는 이웃은 "단순히 컬럼 명칭이 같은" 경우라
# 관련도로 인정하지 않는다(사용자 요구). id/uniqueid/seq/regdate 등 관용 컬럼명·구조어 위주.
_GENERIC_TOKENS = frozenset({
    "id", "uid", "uuid", "guid", "seq", "seqno", "no", "num", "idx", "index",
    "key", "pk", "fk", "ref", "code", "type", "kind", "status", "state", "flag",
    "yn", "use", "used", "enable", "enabled", "active", "value", "val", "data",
    "info", "count", "cnt", "sum", "total", "amount", "qty", "date", "datetime",
    "time", "timestamp", "ts", "created", "updated", "modified", "deleted",
    "createdat", "updatedat", "createddate", "regdate", "reg", "mod", "del",
    "insert", "update", "order", "ordinal", "sort", "unique", "uniqueid", "row",
    "rownum", "version", "ver", "rev", "desc", "description", "comment", "memo",
    "note", "table", "column", "schema", "db", "database", "common", "dbo",
    "tbl", "col", "name", "title", "label", "text", "str", "int", "bigint",
    # camelCase 접속·전치사 조각(CreatedAt/UpdatedBy/BasedOn 등) — 도메인 식별력 없음.
    "at", "by", "on", "of", "to", "in", "for", "and", "or", "with", "from", "per", "is", "as",
    # 한글 일반어·구조어(이 Korean-first 스키마의 설명·명칭에 흔한 boilerplate) — 라틴 목록과 동형.
    #  이것을 빼지 않으면 설명 겹침 booster 가 "게임/정의/테이블" 같은 일반어만으로 content 를 조작(M1 재발).
    "테이블", "컬럼", "정의", "정보", "코드", "상태", "이름", "데이터", "목록", "관리",
    "사용", "여부", "순서", "번호", "유형", "종류", "생성", "수정", "삭제", "일시",
    "게임", "기본", "설정", "내용", "대상", "처리", "결과", "항목", "구분", "시간",
    "날짜", "등록", "요청", "응답", "시스템", "서버", "사용자", "유저", "기록", "로그",
    "값", "필드", "속성", "관련", "전체", "해당", "각각",
})

_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z가-힣]+")
_CAMEL_SPLIT = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])"          # camelCase (rewardItem)
    r"|(?<=[A-Z])(?=[A-Z][a-z])"       # ACRONYM+Word (HTTPServer)
    r"|(?<=[가-힣])(?=[A-Za-z0-9])"     # 한글→라틴/숫자 (업적Achievement)
    r"|(?<=[A-Za-z0-9])(?=[가-힣])"     # 라틴/숫자→한글 (Achievement업적)
)
_HANGUL = re.compile(r"[가-힣]")


def _has_hangul(s) -> bool:
    return bool(_HANGUL.search(s or ""))


def _split_tokens(text) -> list:
    """텍스트를 snake/camel/한글↔라틴/구분자 기준으로 분해 + 끝자리 숫자 제거한 소문자 토큰 리스트."""
    out = []
    for part in _TOKEN_SPLIT.split(str(text or "")):
        if not part:
            continue
        for sub in _CAMEL_SPLIT.split(part):
            s = sub.strip().lower()
            if not s:
                continue
            out.append(s)
            s2 = s.rstrip("0123456789")   # col1 → col
            if s2 and s2 != s:
                out.append(s2)
    return out


def _meaningful_tokens(*texts) -> set:
    """일반어·1글자 토큰을 뺀 '식별력 있는' 토큰 집합. 도메인 연관성 비교용."""
    toks = set()
    for text in texts:
        for t in _split_tokens(text):
            if len(t) < 2 or t in _GENERIC_TOKENS:
                continue
            toks.add(t)
    return toks


def _hangul_partial_overlap(a_tokens: set, n_tokens: set) -> bool:
    """한글 합성어 부분 연관(형태소 분석 부재 보정): 업적 ⊂ 업적보상 처럼 어근이 **접두/접미** 일치.

    라틴 부분일치(log ⊂ login)는 오연관이 잦아 한글에만 적용하되, 한글도 **임의 부분문자열은 금지**하고
    접두/접미 경계만 인정한다 — 그렇지 않으면 회원 ⊂ 비회원구매(반대 의미)·업적 ⊂ 기업적자(무관) 같은
    중간삽입 오매칭이 발생(재검증 지적). 한글 합성어는 어근이 보통 접두/접미이므로 이 경계로 정밀도 확보."""
    ah = [t for t in a_tokens if len(t) >= 2 and _has_hangul(t)]
    nh = [t for t in n_tokens if len(t) >= 2 and _has_hangul(t)]
    for at in ah:
        for nt in nh:
            if at == nt:
                continue
            short, long = (at, nt) if len(at) <= len(nt) else (nt, at)
            if long.startswith(short) or long.endswith(short):
                return True
    return False


def _scope_of(key: str) -> str:
    return (key or "").split(":", 1)[0]


def _table_fqn(label: str, fqn: str) -> str:
    """노드의 소속 테이블 fqn. Column 이면 마지막 세그먼트(컬럼명) 제거, Table 이면 그대로."""
    fqn = fqn or ""
    if label == "Column":
        return fqn.rsplit(".", 1)[0] if "." in fqn else ""
    if label == "Table":
        return fqn
    return ""


def _build_anchor(root_key: str, root_label: str, root_name: str, root_desc: str = "") -> dict:
    """원래 분석 대상(루트) 서술자 — 이웃 관련도 채점의 기준. 그래프 미발견 시에도 run 행 값으로 구성."""
    fqn = root_key.split(":", 1)[1] if ":" in root_key else root_key
    tbl = _table_fqn(root_label, fqn)
    last_seg = fqn.rsplit(".", 1)[-1] if fqn else ""
    return {
        "key": root_key,
        "scope": _scope_of(root_key),
        "label": root_label or "",
        "table_fqn": tbl,
        "tokens": _meaningful_tokens(root_name, last_seg, tbl),
        "desc_tokens": _meaningful_tokens(root_desc),
    }


def _relevance(node: dict, meta: dict, anchor: dict) -> float:
    """후보 이웃 node 의 '원래 루트(anchor)' 와의 관련도(0~1). 인접성이 아니라 **루트 기준** 채점.

    핵심 원칙(사용자 요구): **내용(도메인) 연관이 전혀 없으면 재귀 대상 아님.** 같은 제품(scope)·신뢰
    REFERENCES 같은 구조 신호만으로는 통과하지 못한다 — 반드시 아래 content 신호(테이블 서브트리·이름/
    설명 토큰·용어) 중 하나가 있어야 하고, 구조 신호는 그 위에 **부스터**로만 작용한다.
    """
    meta = meta or {}
    label = node.get("label") or ""
    # Schema 는 형제 테이블 전량 fan-out 허브 → 확장 대상에서 제외(옵션으로만 허용).
    if label == "Schema" and not getattr(_cfg, "AGENT_NODE_ANALYSIS_EXPAND_SCHEMA", False):
        return 0.0
    # 파단(broken) 엣지로만 닿는 이웃은 신뢰할 수 없는 관계 → 제외.
    #   (belt-and-suspenders: neighborhood() 가 이미 broken 엣지를 투영 제외하지만 방어적으로 유지.)
    if meta.get("status") == "broken":
        return 0.0

    # ── content(도메인 연관) 신호 — 0 이면 '단순 명칭·구조 링크' 로 보고 제외 ──────────────
    content = 0.0
    # 1) 루트 테이블 서브트리(같은 테이블 소속) — 가장 강한 "대상 엔티티" 연관.
    n_table = _table_fqn(label, node.get("fqn") or "")
    if anchor["table_fqn"] and n_table and n_table == anchor["table_fqn"]:
        content += 0.6
    # 2) 이름 토큰 겹침(일반어 제외) — "Achievement" 등 도메인 명칭 연관 + 한글 합성어 부분 연관.
    n_tokens = _meaningful_tokens(node.get("name"), node.get("fqn"))
    a_tokens = anchor.get("tokens") or set()
    if a_tokens and n_tokens:
        overlap = len(n_tokens & a_tokens)
        if overlap:
            content += min(0.45, 0.30 * overlap)
        elif _hangul_partial_overlap(a_tokens, n_tokens):
            content += 0.22
    # 3) 설명 내용 겹침 — 상위 객체 속성/컨텐츠 연관.
    if anchor.get("desc_tokens") and node.get("description"):
        inter = len(_meaningful_tokens(node.get("description")) & anchor["desc_tokens"])
        if inter:
            content += min(0.25, 0.06 * inter)
    # 4) 관련 용어(GlossaryTerm) 는 그 자체가 도메인 개념 앵커 — content 로 인정.
    if label == "GlossaryTerm":
        content += 0.18
    # 4b) 함수·프로시저 사용 관계(ROUTINE_USES, graph-funcproc ADR-016) — 현재 노드의 테이블을
    #     실제로 읽고 쓰는 코드 객체(또는 그 역방향)는 도메인 연관 신호. 깊을수록 임계 상향이
    #     자연 억제하므로 중간 강도(0.35)로 인정.
    if (meta.get("kind") == "routine_use") and label in ("Routine", "Table"):
        content += 0.35

    if content <= 0.0:
        return 0.0   # 내용 연관 전무 → 신뢰/제품만으론 재귀 제외(M1: 단순 명칭·구조 링크 배제)

    score = content
    # 5) REFERENCES 신뢰도(ADR-002 weight/status) — **부스터**: 이미 연관 있는 노드를 강화만.
    w = meta.get("weight")
    if meta.get("status") == "trusted" or (isinstance(w, (int, float)) and w >= 0.85):
        score += 0.15

    # 제품 경계: 같은 제품이면 소폭 가산, 다른 제품이면 강한 감쇠(교차-제품 확장 억제).
    if _scope_of(node.get("key") or "") == anchor["scope"]:
        score += 0.08
    else:
        # crossds-rel(ADR-019): **의도적 교차DB REFERENCES** 엣지로 도달한 이웃은 감쇠 완화(기본 1.0=무감쇠) —
        #   Phase B 가 만든 크로스-ds 관계는 우연 교차가 아니라 의도된 연결. 그 외 우연 교차-scope 는 0.25 유지.
        if meta.get("cross_ds"):
            score *= max(0.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_XDS_REFERENCES_FACTOR", 1.0)))
        else:
            score *= max(0.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_CROSS_SCOPE_FACTOR", 0.25)))

    return max(0.0, min(1.0, score))


# ── 연결 헬퍼 ────────────────────────────────────────────────────────────────
def _rw_conn(conn):
    from shared.db import _pg_conn_pair_rw
    return _pg_conn_pair_rw(conn)


def _clamp(v, lo, hi, default):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def _new_run_id() -> str:
    return uuid.uuid4().hex


# ── 그래프 컨텍스트 수집 (neighborhood 재사용) ────────────────────────────────
def _fetch_context(node_key: str, conn):
    """node_key 중심 1-hop {root, neighbors[], columns[], references[], related_terms[]}.

    root 미발견(그래프에 없는 노드) 시 root=None. worker/enqueue 공용.
    """
    from modules import metadata_graph as _mg
    data = _mg.neighborhood(node_key, depth=1, conn=conn) or {"nodes": [], "edges": []}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    root = None
    for n in nodes:
        if n.get("key") == node_key:
            root = n
            break
    by_key = {n.get("key"): n for n in nodes if n.get("key")}
    columns, references, related_terms, other = [], [], [], []
    # graph-funcproc(node-analysis-routine-touch): 현재 노드가 Routine 일 때, 이 루틴이
    #   읽고/쓰는 테이블을 read/write 구분과 함께 구조화해 payload 의 `touches` 로 투영한다
    #   (그간 참조 테이블이 무구분 `other` 로만 흘러 프롬프트의 "the tables it touches" 가 약하게만
    #    뒷받침되던 gap — routine 분석 caveats 가 "참조 테이블 미상"으로 흐르던 원인 중 하나).
    routine_touches: list = []
    # 이웃별 엣지 메타(관련도 채점용): {key: {kind, weight, status, child}}.
    #   child=True → node_key(현재 노드)의 직속 HAS_COLUMN 자식(=하위 컬럼). 우선순위: 신뢰 REFERENCES > child > 그 외.
    neighbor_meta: dict = {}

    def _record(k, kind, weight=None, status=None, child=False, parent=False, cross_ds=None):
        if not k or k == node_key:
            return
        cur = neighbor_meta.get(k)
        if cur is None:
            neighbor_meta[k] = {"kind": kind, "weight": weight, "status": status,
                                "child": child, "parent": parent, "cross_ds": cross_ds}
            return
        cur["child"] = cur["child"] or child
        cur["parent"] = cur.get("parent") or parent
        if weight is not None and cur.get("weight") is None:
            cur["weight"] = weight
        if status and not cur.get("status"):
            cur["status"] = status
        if cross_ds and not cur.get("cross_ds"):
            cur["cross_ds"] = cross_ds   # crossds-rel: 교차DB 의도적 REFERENCES 표식(_relevance/pagerank 완화)

    for e in edges:
        et = e.get("type")
        src, tgt = e.get("source"), e.get("target")
        if et == "HAS_COLUMN" and src == node_key:
            t = by_key.get(tgt)
            if t:
                columns.append(t)
            _record(tgt, "column", child=True)
        elif et == "HAS_COLUMN" and tgt == node_key:
            # graph-funcproc(ADR-017): 현재 노드가 Column 일 때 그 **소속(부모) 테이블** — 재귀로
            # 참조 컬럼이 분석되면 소속 테이블까지 분석되도록 _score_candidates 가 승격한다.
            _record(src, "parent_table", parent=True)
        elif et == "ROUTINE_USES":
            # graph-funcproc(ADR-016): 함수·프로시저 ↔ 테이블 사용 관계 — 도메인 연관 신호로 채점.
            _record(tgt if src == node_key else src, "routine_use")
            # 현재 노드가 이 루틴(src==node_key)이면 target 테이블을 read/write 와 함께 touches 로 수집.
            if src == node_key:
                routine_touches.append({"key": tgt, "access": (e.get("relation_type") or "read")})
        elif et == "REFERENCES":
            references.append({"from": src, "to": tgt, "cardinality": e.get("cardinality"),
                               "weight": e.get("weight"), "status": e.get("status"),
                               "cross_ds": e.get("cross_ds")})
            other_key = tgt if src == node_key else (src if tgt == node_key else None)
            if other_key:
                _record(other_key, "reference", weight=e.get("weight"), status=e.get("status"),
                        cross_ds=e.get("cross_ds"))
        elif et in ("RELATED_TERM", "DESCRIBES"):
            _record(tgt if src == node_key else src, "term")
        else:  # HAS_TABLE, HAS_SCHEMA, USES 등 구조 엣지
            _record(tgt if src == node_key else src, "structural")
    for n in nodes:
        k = n.get("key")
        if k == node_key:
            continue
        if n.get("label") == "GlossaryTerm":
            related_terms.append(n)
            _record(k, "term")
        elif n not in columns:
            other.append(n)
            neighbor_meta.setdefault(k, {"kind": "other", "weight": None, "status": None, "child": False})
    # Routine 이면 touches 에 테이블명(그래프 노드에서 해소) + returns(routine_objects) 보강.
    routine_returns = ""
    if (root or {}).get("label") == "Routine":
        for t in routine_touches:
            tn = by_key.get(t.get("key")) or {}
            t["table"] = tn.get("name") or (t.get("key") or "").rsplit(".", 1)[-1] or t.get("key")
        routine_returns = _fetch_routine_returns(node_key, (root or {}).get("fqn") or "", conn)
    return {"root": root, "neighbors": [n for n in nodes if n.get("key") != node_key],
            "columns": columns, "references": references, "related_terms": related_terms,
            "other": other, "neighbor_meta": neighbor_meta,
            "routine_touches": routine_touches, "routine_returns": routine_returns}


def _fetch_routine_returns(node_key: str, fqn: str, conn) -> str:
    """Routine 의 선언 반환형(routine_objects.returns) — payload `returns` 보강용.

    그래프 Routine 노드는 returns 를 싣지 않으므로(sync_routine 미투영) SSOT 인 routine_objects 에서
    1회 조회한다. 실패·부재·conn 없음 시 빈 문자열(비차단 — returns 는 부가정보). fqn = `schema.name()`.
    """
    if conn is None:
        return ""
    base = fqn[:-2] if fqn.endswith("()") else fqn
    if "." not in base:
        return ""
    schema, name = base.rsplit(".", 1)
    scope = (node_key or "").split(":", 1)[0] or "common"
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT returns FROM routine_objects "
                        "WHERE scope_key=%s AND schema_name=%s AND routine_name=%s LIMIT 1",
                        (scope[:96], schema[:256], name[:256]))
            r = cur.fetchone()
        finally:
            cur.close()
        return (str(r[0]).strip()[:200] if r and r[0] else "")
    except Exception as exc:
        _log.debug("fetch_routine_returns_failed key=%s err=%r", node_key, exc)
        return ""


# ── 컬럼 인벤토리 lazy introspection (node-analysis-completeness, 2026-07-23) ──
#  §55 "직계 컬럼 게이트 면제 편입"·payload 컬럼 컨텍스트는 그래프 HAS_COLUMN 이웃에 의존하는데,
#  Column 정점은 큐레이션(column_descriptions)·관계 끝점만 투영된다. 부트스트랩을 거치지 않은
#  datasource(사용자 리포트: mysql-local/log_v2 — 컬럼 잡 10/전체, 테이블당 0~2개)는 그래프에
#  컬럼이 없어 "DB 전체 AI 능동 분석"이 컬럼을 사실상 건너뛰었다. Table 잡 처리 직전 1회,
#  datasource 라이브 INFORMATION_SCHEMA 로 컬럼 목록(+ordinal·native comment)을
#  column_descriptions 스켈레톤 upsert(관계형 SSOT — 그래프 재생성 생존) + Column 정점 targeted
#  MERGE 한다. 실패는 전부 삼킴(fail-soft — 종전 동작으로 저하), 프로세스 내 dedup.
_COLS_ENSURED: set = set()          # node_key — 프로세스 수명 dedup(잡 재시도·refine 재진입 무비용)
_DS_CACHE: dict = {"at": 0.0, "map": {}}   # scope_key(해시) → datasource dict (TTL 캐시)
_DS_CACHE_TTL_SEC = 300


def _resolve_datasource_by_scope(scope: str) -> dict | None:
    """scope_key(엔드포인트 해시, node_key 접두) → datasource 좌표 dict. 제어면 MySQL 1회 조회 + TTL 캐시.

    §18.8 B1: 레지스트리 정본 = MEMORY_DB 의 WebDatasources — DB 미지정 connect() 는 default DB
    미선택 연결이 되어 _all_db_datasources 가 조용히 {} 를 반환(routine_backfill 동일 규약).
    scope 키는 `_datasources.scope_key(coords)` 로 계산(.env 레거시 dict 는 scope_key 필드 미보유)."""
    import time as _time
    now = _time.monotonic()
    if _DS_CACHE["map"] and (now - _DS_CACHE["at"]) < _DS_CACHE_TTL_SEC:
        return _DS_CACHE["map"].get(scope)
    try:
        from shared import datasources as _datasources
        from shared import db as _db
        mem = _db.connect(database=_cfg.MEMORY_DB)
        try:
            m = {}
            for _k, _v in (_datasources.all_datasources(mem) or {}).items():
                if not _v:
                    continue
                sk = _datasources.scope_key(_v) or _k
                if sk:
                    m[str(sk)] = _v
            _DS_CACHE["map"] = m
            _DS_CACHE["at"] = now
        finally:
            try:
                mem.close()
            except Exception:
                pass
    except Exception as exc:
        _log.debug("resolve_datasource_failed scope=%s err=%r", scope, exc)
        return _DS_CACHE["map"].get(scope) if _DS_CACHE["map"] else None
    return _DS_CACHE["map"].get(scope)


def _introspect_table_columns(ds: dict, schema: str, table: str, cap: int) -> list:
    """datasource 라이브 INFORMATION_SCHEMA 컬럼 조회 → [(name, ordinal, comment)] (ordinal 순, cap 절단).

    MySQL: information_schema 가 인스턴스 전역 — TABLE_SCHEMA=<schema>(DB) 필터.
    MSSQL: INFORMATION_SCHEMA 가 DB(catalog)별 — <schema>=effective DB 로 재연결, 테이블명만 매칭
    (기본 dbo 외 사용자 스키마도 포섭 — dialects.describe_columns 의 빈-스키마 관례와 동형)."""
    from shared import db as _db
    engine = str((ds or {}).get("engine") or "mysql").strip().lower()
    # T0b: 소스 DB 동시 연결 예산. 거절되면 이번엔 introspect 를 건너뛴다(컬럼 인벤토리는
    #   fail-soft — 다음 tick 에 재시도하며 payload 는 기존 컬럼만으로 구성된다).
    try:
        from shared import resource_budget as _rb_ds
    except Exception:
        _rb_ds = None
    _ds_cm = _rb_ds.acquire("ds") if _rb_ds is not None else None
    if _ds_cm is not None:
        _ds_ok = _ds_cm.__enter__()
        if not _ds_ok:
            _ds_cm.__exit__(None, None, None)
            _log.info("컬럼 introspect 보류 — 소스 DB 연결 예산 여유 없음(다음 tick 재시도)")
            return []
    # ⚠ connect() 는 **try 안**에서 호출한다 — 예산 획득 후 연결 수립이 예외를 내면 try/finally
    #   진입 전이라 반납이 보장되지 않아 슬롯이 영구 누수된다(codex P1, REV-20260730T1430).
    conn = None
    try:
        conn = _db.connect(database=(schema if engine == "mssql" else None), datasource=ds)
        cur = conn.cursor()
        try:
            if engine == "mssql":
                cur.execute(
                    "SELECT COLUMN_NAME, ORDINAL_POSITION, '' FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = %s ORDER BY ORDINAL_POSITION", (table,))
            else:
                cur.execute(
                    "SELECT COLUMN_NAME, ORDINAL_POSITION, COALESCE(COLUMN_COMMENT, '') "
                    "FROM information_schema.columns "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                    (schema, table))
            rows = cur.fetchall() or []
        finally:
            try:
                cur.close()
            except Exception:
                pass
        out = []
        for r in rows[:max(0, cap)]:
            name = str(r[0] or "").strip()
            if not name:
                continue
            try:
                ordn = int(r[1])
            except (TypeError, ValueError):
                ordn = None
            out.append((name, ordn, str(r[2] or "").strip()[:400]))
        return out
    except Exception:
        # 연결 수립·조회 실패는 fail-soft(컬럼 인벤토리는 다음 tick 재시도) — 호출측 계약 유지.
        _log.debug("introspect_table_columns_failed schema=%s table=%s", schema, table)
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        # T0b: 소스 DB 연결 예산 반납 — 연결 close 와 같은 finally 에서 해제해 점유 수명이
        #   연결 수명과 정확히 일치한다(누수 없음). connect 실패 경로도 여기를 지난다.
        if _ds_cm is not None:
            try:
                _ds_cm.__exit__(None, None, None)
            except Exception:
                pass


def _ensure_table_columns(c, node_key: str) -> int:
    """Table 잡 처리 직전 컬럼 인벤토리 보강 — **신규 insert(누락분만)** 수 반환(0=완비/비활성/실패).

    c = node_analysis 의 PG RW conn(같은 세션에서 column_descriptions insert + AGE MERGE).
    §18.8 M1·M2·m4 반영: 행-존재 게이트 대신 **누락분-only insert**(ON CONFLICT DO NOTHING) —
    부분 큐레이션 테이블(수동 1~2컬럼)도 나머지가 채워지고, 부분 쓰기(중단)는 다음 프로세스
    재시도가 잔여만 멱등 삽입하며, 큐레이션 설명은 어떤 race 에서도 덮어쓰지 않는다.
    그래프 MERGE 는 이번에 insert 된 행만(기존 행의 정점 투영은 30분 sync 정본 경로 소관 —
    큐레이션 layering 보존). §18.8 m2: 멀티 datasource 비활성 환경은 전체 skip(레거시 DB_HOST
    로 붙어 엉뚱한 서버 컬럼을 기록하는 오염 차단)."""
    cap = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP", 200) or 0)
    if cap <= 0 or not node_key or ":" not in node_key:
        return 0
    if not bool(getattr(_cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False)):
        return 0
    if node_key in _COLS_ENSURED:
        return 0
    _COLS_ENSURED.add(node_key)   # 프로세스 수명 dedup(실패 포함 — 재기동/다음 워커가 재시도)
    scope, _, rest = node_key.partition(":")
    schema, _, table = rest.rpartition(".")
    if not scope or not schema or not table:
        return 0
    try:
        ds = _resolve_datasource_by_scope(scope)
        if not ds:
            return 0
        cols = _introspect_table_columns(ds, schema, table, cap)
        if not cols:
            return 0
        # 누락분 산정 — 기존 행(큐레이션·부트스트랩·선행 introspection)은 절대 불변.
        cur = c.cursor()
        try:
            cur.execute("SELECT column_name FROM column_descriptions "
                        "WHERE scope_key=%s AND schema_name=%s AND table_name=%s",
                        (scope, schema, table))
            existing = {str(r[0]).casefold() for r in cur.fetchall() if r and r[0]}
        finally:
            cur.close()
        missing = [(n, o, cm) for (n, o, cm) in cols if n.casefold() not in existing]
        if not missing:
            return 0
        from modules import metadata_graph as _mg
        inserted = []
        cur = c.cursor()
        try:
            for (name, ordn, comment) in missing:
                cur.execute(
                    "INSERT INTO column_descriptions "
                    "(scope_key, schema_name, table_name, column_name, description, source, ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,'introspect',%s) "
                    "ON CONFLICT (scope_key, schema_name, table_name, column_name) DO NOTHING",
                    (scope, schema, table, name, comment, ordn))
                if int(cur.rowcount or 0) > 0:
                    inserted.append((name, ordn, comment))
        finally:
            cur.close()
        if inserted:
            gcur = c.cursor()
            try:
                _mg._set_age_path(gcur)
                for (name, ordn, comment) in inserted:
                    _mg.sync_column(gcur, scope, schema, table, name,
                                    description=comment, source="introspect", ordinal=ordn)
            finally:
                try:
                    gcur.close()
                except Exception:
                    pass
        _log.info("node_analysis ensure_columns node=%s introspected=%s inserted=%s (cap=%s)",
                  node_key, len(cols), len(inserted), cap)
        return len(inserted)
    except Exception as exc:
        _log.warning("ensure_table_columns_failed node=%s err=%r", node_key, exc)
        return 0


# ── 통계 증거 접지 (feature-0031-analysis-grounding, L0/L1) ──────────────────
def _split_table_key(node_key: str):
    """`scope:schema.table` → (scope, schema, table). 형식이 아니면 (None, None, None)."""
    if not node_key or ":" not in node_key:
        return None, None, None
    scope, _, rest = node_key.partition(":")
    schema, _, table = rest.rpartition(".")
    if not scope or not schema or not table:
        return None, None, None
    return scope, schema, table


def _ensure_table_stats(c, node_key: str) -> None:
    """Table 잡 처리 직전 통계 증거 보강 — 필요하고 허용될 때만 수집한다(fail-soft, 반환 없음).

    수집 깊이·주기·시간창은 `metadata_stats` 가 판정하고, 운영 DB 연결은 `ds` 자원 예산 게이트
    위에서만 열린다. 어떤 실패도 분석 흐름을 막지 않는다 — 증거 없이 분석하던 종전 동작으로 진행."""
    if not bool(getattr(_cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False)):
        return   # 멀티 datasource 비활성 환경은 전체 skip(_ensure_table_columns 와 동형)
    scope, schema, table = _split_table_key(node_key)
    if not scope:
        return
    try:
        from modules import metadata_stats as _ms
        ds = _resolve_datasource_by_scope(scope)
        if ds:
            _ms.ensure_stats(ds, c, scope, schema, table)
    except Exception as exc:
        _log.debug("ensure_table_stats_failed node=%s err=%r", node_key, exc)


def _table_evidence(c, node_key: str):
    """payload 에 실을 `evidence` 블록(없으면 None). 수집 여부와 무관하게 안전하다."""
    scope, schema, table = _split_table_key(node_key)
    if not scope:
        return None
    try:
        from modules import metadata_stats as _ms
        cap = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_EVIDENCE_COLUMN_CAP", 40) or 40)
        return _ms.load_evidence(c, scope, schema, table, column_cap=cap)
    except Exception as exc:
        _log.debug("table_evidence_failed node=%s err=%r", node_key, exc)
        return None


def _build_payload(node: dict, ctx: dict) -> dict:
    """LLM 입력 payload (NODE_ANALYSIS_PROMPT 계약). 이웃 리스트는 cap 으로 토큰 보호."""
    def _names(items, n):
        out = []
        for it in items[:n]:
            nm = it.get("name") or it.get("fqn") or it.get("key")
            desc = (it.get("description") or "").strip()
            out.append({"name": nm, "description": desc[:200]} if desc else {"name": nm})
        return out
    payload = {
        "label": node.get("label") or "",
        "name": node.get("name") or node.get("fqn") or node.get("key") or "",
        "fqn": node.get("fqn") or "",
        "description": (node.get("description") or "")[:1000],
        "scope_key": (node.get("key") or "").split(":", 1)[0] if node.get("key") else "",
        "neighbors": {
            "columns": _names(ctx.get("columns") or [], 40),
            "references": (ctx.get("references") or [])[:30],
            "related_terms": _names(ctx.get("related_terms") or [], 20),
            "other": _names(ctx.get("other") or [], 20),
        },
    }
    # graph-navfilter-routine(§54): Routine 은 프롬프트가 약속한 "name, parameters and the tables
    # it touches" 계약 충족을 위해 유형·파라미터를 함께 투영(그간 name·이웃만으로 분석되던 gap).
    if (node.get("label") or "") == "Routine":
        if node.get("routine_type"):
            payload["routine_type"] = str(node.get("routine_type"))[:32]
        if node.get("params"):
            payload["params"] = str(node.get("params"))[:500]
        # node-analysis-routine-touch: 반환형 + 읽고/쓰는 테이블(read/write) 구조화 투영.
        #   프롬프트의 "the tables it touches" 를 실제로 뒷받침 — 루틴 분석이 이름만으로 굶주려
        #   caveats 를 "참조 테이블 미상"으로 채우던 원인 완화.
        rr = (ctx.get("routine_returns") or "").strip()
        if rr:
            payload["returns"] = rr[:200]
        touches = []
        seen_t = set()
        for t in (ctx.get("routine_touches") or [])[:40]:
            tbl = (t.get("table") or "").strip()
            if not tbl or tbl in seen_t:
                continue
            seen_t.add(tbl)
            touches.append({"table": tbl, "access": t.get("access") or "read"})
        if touches:
            payload["touches"] = touches
    return payload


# ── enqueue (웹 트리거) ──────────────────────────────────────────────────────
def enqueue_analysis(scope_key: str, node_key: str, depth_budget=None, node_budget=None,
                     requested_by=None, user_prompt=None, conn=None) -> dict:
    """루트 노드로 분석 run 생성 + 루트 pending 잡 삽입. 반환 {ok, run_id, status, reason?}.

    같은 (scope_key, root_key) 로 진행 중(status='running') run 이 있으면 그 run_id 를 재사용(중복 방지 —
    이 경우 새 user_prompt 는 무시된다: 진행 중 run 의 지침을 중간에 바꾸면 앞뒤 분석문의 관점이 갈린다).

    user_prompt(ADR-017): 그래프 뷰 'AI 능동 분석' hover 툴팁으로 입력한 사용자 지침(≤400자) —
    run 에 저장되어 (a) 앵커 토큰에 합류(관련도 채점이 지침 어휘를 따라가게), (b) LLM payload 의
    `user_intent` 로 주입돼 분석문에 자율 반영된다.
    """
    if not _cfg_enabled():
        return {"ok": False, "reason": "disabled"}
    if not node_key:
        return {"ok": False, "reason": "node_key 필수"}
    depth_budget = _clamp(depth_budget if depth_budget is not None else _cfg.AGENT_NODE_ANALYSIS_DEFAULT_DEPTH,
                          1, _cfg.AGENT_NODE_ANALYSIS_MAX_DEPTH, _cfg.AGENT_NODE_ANALYSIS_DEFAULT_DEPTH)
    node_budget = _clamp(node_budget if node_budget is not None else _cfg.AGENT_NODE_ANALYSIS_DEFAULT_BUDGET,
                         1, _cfg.AGENT_NODE_ANALYSIS_MAX_BUDGET, _cfg.AGENT_NODE_ANALYSIS_DEFAULT_BUDGET)
    sk = (scope_key or "common")[:96]   # fix(low): scope_key 길이 초과 insert 오류 방지
    lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
    c, owned = _rw_conn(conn)
    if c is None:
        return {"ok": False, "reason": "PG 미가용"}
    try:
        cur = c.cursor()
        # 진행 중 run 재사용 (중복 트리거 방지). fix(high): updated_at 이 lease 이내인 run 만 재사용 —
        #   워커 크래시로 갇힌(stale) run 을 영구 재사용해 재트리거 불가에 빠지지 않게 한다(reaper 와 함께).
        cur.execute("SELECT run_id, enqueued, done, failed FROM node_analysis_runs "
                    "WHERE scope_key=%s AND root_key=%s AND status='running' "
                    "AND updated_at > now() - make_interval(secs => %s) "
                    "ORDER BY created_at DESC LIMIT 1", (sk, node_key, lease))
        row = cur.fetchone()
        if row:
            cur.close()
            # graphux7(#4): 이미 진행 중 — 재큐잉하지 않고 기존 run 재사용(중복 큐잉 방어). 진행 카운트를
            #   함께 반환해 프론트가 사용자에게 "이미 분석 중(진행률)" 을 즉시 안내한다.
            return {"ok": True, "run_id": row[0], "status": "running", "reused": True,
                    "progress": {"enqueued": row[1], "done": row[2], "failed": row[3]}}
        # 루트 노드 props 확보 (그래프에서)
        ctx = _fetch_context(node_key, c)
        root = ctx.get("root") or {"label": "", "name": node_key, "fqn": ""}
        run_id = _new_run_id()
        up = (str(user_prompt).strip()[:400] or None) if user_prompt else None
        base_cols = (run_id, sk, node_key, (root.get("label") or "")[:32],
                     (root.get("name") or node_key)[:512], depth_budget, node_budget,
                     (requested_by or None))
        try:
            cur.execute(
                "INSERT INTO node_analysis_runs "
                "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
                " status, enqueued, done, failed, requested_by, user_prompt) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',1,0,0,%s,%s)",
                base_cols + (up,))
        except Exception as up_exc:
            # 마이그레이션 창(user_prompt 컬럼 부재, alembic 0034) — 지침만 생략하고 run 은 생성(B1 동형).
            _warn_uprompt_column_once("enqueue_analysis", up_exc)
            cur.execute(
                "INSERT INTO node_analysis_runs "
                "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
                " status, enqueued, done, failed, requested_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',1,0,0,%s)",
                base_cols)
        cur.execute(
            "INSERT INTO node_analysis_jobs "
            "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,0,1.0,'pending') "
            "ON CONFLICT (run_id, node_key) DO NOTHING",
            (run_id, sk, node_key, (root.get("label") or "")[:32],
             (root.get("name") or node_key)[:512], (root.get("fqn") or "")))
        cur.close()
        _log.info("node_analysis enqueue run=%s root=%s depth=%s budget=%s",
                  run_id, node_key, depth_budget, node_budget)
        return {"ok": True, "run_id": run_id, "status": "running"}
    except Exception as exc:
        _log.warning("enqueue_analysis_failed err=%r", exc)
        return {"ok": False, "reason": "enqueue 실패"}
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def enqueue_schema_analysis(scope_key: str, schema_key: str, *, requested_by=None,
                            user_prompt=None, only_missing=True, table_cap=None,
                            dry_run=False, conn=None) -> dict:
    """DB(스키마) 단위 능동 분석(§53·§54·§55) — run(root=Schema) + 소속 Table 과 Routine(함수·프로시저,
    §54)을 **depth=0 시드**로 일괄 pre-seed(테이블 우선, cap 절단 시 루틴 후순위).
    반환 {ok, run_id?, status, total_tables, total_routines, missing, planned, capped, reused?}.

    §55(REQ-20260706 ③): 시드는 depth=0 + anchor_key=자기 자신(per-seed 앵커) — 각 시드의 직계 컬럼이
    게이트 면제로 편입되고, 관련 노드는 그 시드(Schema 아님) 기준 앵커 게이팅으로 재귀 전개된다
    ("DB 하위 전 노드 분석 + 관련 노드 재귀"). 비용 경계: only_missing(기본) + SCHEMA_CAP(시드 상한)
    + depth_budget=AGENT_NODE_ANALYSIS_SCHEMA_DEPTH + node_budget=min(SCHEMA_RUN_BUDGET_MAX,
    planned×SCHEMA_EXPAND_FACTOR). alembic 0038 미적용 창은 legacy(depth=1 시드·node_budget=planned=
    재귀 0)로 자동 폴백.
    dry_run: run 미생성 — 집계만 반환(UI confirm 용). 단 진행 중 run 이 있으면 dry_run 도
    reused 를 반환해 프론트가 confirm(허위 승인)을 건너뛰게 한다(§18.8 MINOR).
    진행 중 run(root=schema_key) 존재 시 재사용(reused) — 노드 분석과 동일 dedup 규약."""
    if not _cfg_enabled():
        return {"ok": False, "reason": "disabled"}
    if not schema_key or ":" not in str(schema_key):
        return {"ok": False, "reason": "schema_key 필수"}
    sk = (scope_key or str(schema_key).split(":", 1)[0] or "common")[:96]
    cap_def = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_CAP", 200) or 200)
    cap_max = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_MAX", 500) or 500)
    cap = _clamp(table_cap if table_cap is not None else cap_def, 1, cap_max, cap_def)
    from modules import metadata_graph as _mg
    # limit 5000(클램프 상한) — 기본 2000 이면 초과 스키마의 total/missing 이 절단돼 confirm 수치가
    # 과소보고된다(§18.8 NIT; 시드는 어차피 cap 으로 제한). 5000 초과 스키마는 여전히 절단(수용).
    tables = _mg.schema_table_keys(sk, schema_key, limit=5000) or []
    total = len(tables)
    # graph-navfilter-routine(§54): 함수·프로시저(Routine)도 스키마 시드에 포함 — 열거 실패/
    # HAS_ROUTINE 라벨 부재(0034 미적용)는 [] 저하(테이블-only 로 계속, schema_table_keys 관례).
    routines = _mg.schema_routine_keys(sk, schema_key, limit=5000) or []   # 테이블과 대칭(confirm 과소보고 방지)
    total_routines = len(routines)
    done = set()
    if only_missing and (tables or routines):
        st = get_scope_analysis_status(sk)
        if st is None:
            # silent 저하 방지(§18.8 MINOR): 집계 실패를 done=∅ 로 계속하면 이미 분석 완료된
            # 테이블까지 cap 이내 전량 재시드(중복 LLM 비용) — fail-loud 로 중단.
            return {"ok": False, "reason": "분석 상태 집계 실패(PG) — 잠시 후 다시 시도해 주세요."}
        done = set(st.get("done_keys") or [])
    # 순서 = 테이블 먼저, 루틴 뒤 — cap 절단 시 테이블 우선(기존 동작 보존, 결정적).
    targets = ([dict(t, label="Table") for t in tables
                if t.get("key") and (not only_missing or t["key"] not in done)]
               + [dict(r, label="Routine") for r in routines
                  if r.get("key") and (not only_missing or r["key"] not in done)])
    missing = len(targets)
    capped = missing > cap
    targets = targets[:cap]
    base = {"total_tables": total, "total_routines": total_routines,
            "missing": missing, "planned": len(targets), "capped": capped}
    lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
    c, owned = _rw_conn(conn)
    if c is None:
        return {"ok": False, "reason": "PG 미가용"}
    try:
        cur = c.cursor()
        # 진행 중 run 재사용 — enqueue_analysis 와 동일 규약(lease 이내 running 만).
        # dry_run 보다 먼저(§18.8 MINOR): 진행 중인데 dry_run 이 집계만 돌려주면 confirm 이
        # "이번 실행 N개" 를 약속하고 실제 POST 는 reused(신규 큐잉 0)가 되는 허위 승인 유도.
        cur.execute("SELECT run_id, enqueued, done, failed FROM node_analysis_runs "
                    "WHERE scope_key=%s AND root_key=%s AND status='running' "
                    "AND updated_at > now() - make_interval(secs => %s) "
                    "ORDER BY created_at DESC LIMIT 1", (sk, schema_key, lease))
        row = cur.fetchone()
        if row:
            cur.close()
            return dict(base, ok=True, run_id=row[0], status="running", reused=True,
                        progress={"enqueued": row[1], "done": row[2], "failed": row[3]})
        if dry_run:
            cur.close()
            return dict(base, ok=True, status="dry_run")
        if not targets:
            cur.close()
            return dict(base, ok=True, status="noop",
                        reason="분석 대상 없음(테이블 없음 또는 전부 분석 완료)")
        run_id = _new_run_id()
        up = (str(user_prompt).strip()[:400] or None) if user_prompt else None
        schema_name = schema_key.split(":", 1)[1] if ":" in schema_key else schema_key
        # §55: 재귀 전개 예산 — 0038 적용 시 depth=SCHEMA_DEPTH·budget=planned×factor(cap), 미적용 창은
        # legacy(depth 1·budget=planned=재귀 0). planned 보다 작아지지 않게 하한 고정(시드 전량 보장).
        refine_ok = _refine_cols_ok(cur)
        if refine_ok:
            sdepth = _clamp(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_DEPTH", 2),
                            1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_MAX_DEPTH", 5)), 2)
            factor = max(1.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_EXPAND_FACTOR", 12) or 12))
            run_max = max(1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_RUN_BUDGET_MAX", 2500) or 2500))
            node_budget = max(len(targets), min(run_max, int(len(targets) * factor)))
        else:
            sdepth, node_budget = 1, len(targets)
        base_cols = (run_id, sk, schema_key, "Schema", schema_name[:512],
                     sdepth, node_budget, (requested_by or None))
        try:
            cur.execute(
                "INSERT INTO node_analysis_runs "
                "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
                " status, enqueued, done, failed, requested_by, user_prompt) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',%s,0,0,%s,%s)",
                base_cols[:7] + (len(targets),) + base_cols[7:] + (up,))
        except Exception as up_exc:
            _warn_uprompt_column_once("enqueue_schema_analysis", up_exc)
            cur.execute(
                "INSERT INTO node_analysis_runs "
                "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
                " status, enqueued, done, failed, requested_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',%s,0,0,%s)",
                base_cols[:7] + (len(targets),) + base_cols[7:])
        for t in targets:
            fqn = t.get("fqn") or ""
            if refine_ok:
                # §55: depth=0(직계 컬럼 게이트 면제 편입) + anchor_key=자기 자신(per-seed 앵커 게이팅).
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status, anchor_key) "
                    "VALUES (%s,%s,%s,%s,%s,%s,0,1.0,'pending',%s) "
                    "ON CONFLICT (run_id, node_key) DO NOTHING",
                    (run_id, sk, t["key"], t.get("label") or "Table",
                     (t.get("name") or t["key"])[:512], fqn, t["key"]))
            else:
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,1,1.0,'pending') "
                    "ON CONFLICT (run_id, node_key) DO NOTHING",
                    (run_id, sk, t["key"], t.get("label") or "Table",
                     (t.get("name") or t["key"])[:512], fqn))
        cur.close()
        _log.info("node_analysis enqueue_schema run=%s schema=%s planned=%s/%s(+routines %s) capped=%s "
                  "depth=%s budget=%s refine_cols=%s",
                  run_id, schema_key, len(targets), total, total_routines, capped,
                  sdepth, node_budget, refine_ok)
        return dict(base, ok=True, run_id=run_id, status="running")
    except Exception as exc:
        _log.warning("enqueue_schema_analysis_failed err=%r", exc)
        return {"ok": False, "reason": "enqueue 실패"}
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


# ── 구조 변동 자동 재분석 (change-reanalysis, 사용자 결정 2026-07-27) ────────────
#: 자동 run 의 root_key 접미 — 사용자의 수동 'DB 전체 분석' run(root_key=<schema_key>)과 **분리**한다.
#  같은 root_key 를 쓰면 enqueue_schema_analysis 의 진행-중 dedup 이 자동 run 을 잡아, 사용자가 전체
#  분석을 눌렀을 때 "이미 분석 중"(실은 변경 노드 몇 개짜리 run)으로 흡수돼 planned 수치가 허위가 된다.
_AUTO_ROOT_SUFFIX = "#auto"
#: 자동 run 의 root_label — 사용자 run('Schema')과 구분해 조회·감사에서 식별 가능하게 한다.
_AUTO_ROOT_LABEL = "SchemaAuto"


def auto_root_key(schema_key: str) -> str:
    """스키마 key → 자동 재분석 run 의 root_key."""
    return f"{schema_key}{_AUTO_ROOT_SUFFIX}"


#: `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP` 의 3-state 규약 — 관리 콘솔 숫자 하나로 라이브 전환한다.
#    >0  = 발동(그 값이 1회 시드 상한)
#     0  = 완전 정지(신규 트리거 차단 + 이미 큐잉된 SchemaAuto 잡도 drain 보류 — process_pending 게이트)
#    -1  = shadow(후보 산출·계측만, enqueue 0 · 비용 0)
#  단일 int knob 으로 둔 이유: 안전 모드 전환에 **재배포가 필요하면 사고 시 무용**이기 때문이다
#  (적대 리뷰 C3 — env-only shadow 는 전환·복귀 모두 재배포). runtime_settings 는 int 스펙이라
#  문자열 3-state 대신 음수 sentinel 을 쓴다. env `AUTO_ON_CHANGE=shadow` 도 계속 유효(하위호환).
AUTO_CAP_SHADOW = -1


def auto_cap_value() -> int:
    """현재 유효 cap(라이브 override 우선). 3-state 규약은 `AUTO_CAP_SHADOW` 참조."""
    return auto_setting_int("AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", 50)


def auto_shadow_mode() -> bool:
    """shadow(계측만) 여부 — cap==-1(라이브) 또는 env 3-state 문자열."""
    if auto_cap_value() == AUTO_CAP_SHADOW:
        return True
    return str(getattr(_cfg, "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE", "1")).strip().lower() == "shadow"


def _auto_enabled() -> bool:
    """자동 재분석 경로가 살아 있는지. cap==0(라이브 kill switch)만 완전 비활성 —
    shadow(-1)는 후보 산출까지는 살아 있어야 규모를 계측할 수 있으므로 여기서 막지 않는다."""
    return bool(_cfg_enabled()
                and getattr(_cfg, "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", True)
                and auto_cap_value() != 0)


def auto_setting_int(key: str, fallback: int) -> int:
    """자동 재분석 노브 조회 — 관리 콘솔 live override(runtime_settings) 우선, 실패 시 config env.

    사람 confirm 게이트가 없는 자동 LLM 지출 경로라 **라이브 정지 스위치**가 필요하다(적대 리뷰 C1):
    `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP` 을 0 으로 내리면 재배포 없이 즉시 비활성. import 시점
    상수(star-import 복사본)로 읽으면 이 조절이 반영되지 않으므로 **호출 시점 조회**한다."""
    try:
        from shared import runtime_settings as _rs
        v = _rs.get_int(key)
        if v is not None:
            return int(v)
    except Exception:
        pass
    try:
        return int(getattr(_cfg, key))
    except Exception:
        return fallback


def schema_analysis_completed(scope_key: str, schema_key: str, conn=None) -> bool:
    """해당 스키마(DB)에 **'DB 전체 AI 능동 분석' 완료 이력**이 있는지 (자동 재분석 자격 판정).

    사용자 요청(2026-07-27): 자동 재분석은 "'DB 전체 AI 능동 분석'이 이루어진 DB" 에만 발동한다.
    판정 = 그 스키마를 루트로 한 **사용자 run(root_label='Schema')** 중 `status='done'` 이면서
    **성공이 과반**(`done*2 >= enqueued`)인 run 1건 이상.

    - 자동 run(root_label='SchemaAuto')은 자격 판정에서 제외 — 자기 자신이 자격을 만드는 순환 차단.
    - **과반 조건(적대 리뷰 B3)**: `process_pending` 의 run 마감은 `done > 0` 이면 'done' 이라,
      500 노드 중 1개만 성공한 run 도 'done' 이 된다. 그런 run 을 '전체 분석 완료'로 인정하면
      사실상 분석되지 않은 DB 가 영구 자동 지출 대상이 된다.
    - **scope·root_key 대소문자(적대 리뷰 C6 + 재검증 Q3b)**: 수동 run 기록 경로는 scope_key 를
      소문자화해 저장하는데 `.env` 레거시 datasource 는 라벨 원형(예 `KR_LIVE`)을 쓴다. **root_key 는
      그 scope 문자열을 그대로 품은 파생**(`<scope>:<schema>`)이라 같은 방어가 없으면 한 글자 차이로
      기능이 100% 침묵 사망한다(남는 신호가 정상 상태와 동일한 `ineligible` 뿐이라 관측도 안 된다)
      → 두 축 모두 원형·소문자 매칭(`IN` 이라 인덱스 ix_node_analysis_runs_scope_root 유지).

    PG 미가용·예외 → **False (fail-closed)**. 자동 LLM 비용을 유발하는 경로이므로, 모르면 발동하지
    않는 쪽이 안전하다."""
    if not schema_key:
        return False
    c, owned = _rw_conn(conn)
    if c is None:
        return False
    try:
        sk = (scope_key or "common")[:96]
        rk = str(schema_key)
        cur = c.cursor()
        cur.execute("SELECT 1 FROM node_analysis_runs "
                    "WHERE scope_key IN (%s, %s) AND root_key IN (%s, %s) AND root_label='Schema' "
                    "AND status='done' AND done > 0 AND done * 2 >= enqueued "
                    "LIMIT 1", (sk, sk.lower(), rk, rk.lower()))
        row = cur.fetchone()
        cur.close()
        return bool(row)
    except Exception as exc:
        _log.debug("schema_analysis_completed_failed schema=%s err=%r", schema_key, exc)
        return False
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def enqueue_change_analysis(scope_key: str, schema_key: str, node_keys, *,
                            reason: str = "structure_changed",
                            requested_by: str = "auto:insight-change",
                            cap=None, conn=None) -> dict:
    """구조 변동 감지 노드를 시드로 하는 **자동** 재귀 분석 run 생성 (change-reanalysis).

    insight-worker 가 스키마/테이블 지문·루틴 정의 해시로 구조 변동(테이블 신규, 컬럼 구성 변경,
    루틴 신규·정의 변경)을 감지하면 이 함수를 호출한다. 시드는 `enqueue_schema_analysis` 와 동일한
    §55 규약(depth=0 + anchor_key=자기 자신 = per-seed 앵커)이라, 변경 노드에서 출발해 **관련 노드까지
    재귀 전개**되고 기존 분석문은 refine-not-override 로 갱신된다.

    비용 가드(사용자 결정 2026-07-27 — 자동 발동은 사람 confirm 게이트가 없다):
      - 자격: `schema_analysis_completed` (사람이 한 번 전체 분석했고 그 run 이 과반 성공한 DB 에만).
      - 그래프 실재: AGE 그래프에 아직 투영되지 않은 노드는 시드에서 제외(반환 `seeded_keys` 로 호출자가
        스냅샷을 선택 갱신 → 투영 후 다음 사이클에 자연 재시도).
      - 시드 상한: `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP`(라이브 조절, **0=완전 비활성**).
      - 쿨다운: 직전 자동 run 이 `AUTO_CHANGE_COOLDOWN_SEC` 이내면 skip(status='cooldown').
      - **진행 중 자동 run 이 있으면 아무것도 하지 않는다(status='busy')** — 적대 리뷰 B2: 진행 중 run 에
        시드를 append 하면 run 이 영구 'running' 이라 쿨다운이 한 번도 발동하지 못하고(사이클마다 cap 만큼
        유입) node_budget 까지 ratchet 된다. 변경 누락은 호출자의 스냅샷 미갱신으로 이미 보장되므로
        (다음 사이클 재시도) append 는 순이익 없이 무제한 증식 통로만 연다.

    반환 {ok, status, run_id?, seeded, seeded_keys, skipped_missing, capped, reason?}.
      status: running | busy | cooldown | ineligible | noop | disabled."""
    base = {"seeded": 0, "seeded_keys": [], "skipped_missing": 0, "capped": False}
    if not _auto_enabled():
        return dict(base, ok=False, status="disabled", reason="자동 재분석 정지(cap 0)")
    if not schema_key or ":" not in str(schema_key):
        return dict(base, ok=False, status="noop", reason="schema_key 필수")
    # scope 정규화 — 수동 라우터가 `.strip().lower()` 로 적재하므로 자동 경로도 같은 축을 써야
    # `get_scope_analysis_status`/`only_missing` 중복 제거가 성립한다(적대 리뷰 재검증 C1:
    # 축이 갈리면 사용자가 방금 비용을 낸 노드를 자동 경로가 통째로 재시드한다).
    sk = (scope_key or str(schema_key).split(":", 1)[0] or "common").strip().lower()[:96]
    keys, seen = [], set()
    for k in (node_keys or []):
        k = str(k or "").strip()
        if k and k not in seen:
            seen.add(k)
            keys.append(k)
    if not keys:
        return dict(base, ok=True, status="noop", reason="변경 노드 없음")

    cap_cfg = auto_cap_value()
    # shadow — **여기서** 판정한다(적대 리뷰 재검증 C3: 호출자 규율에만 의존하면 다른 진입점이
    # 안전 모드를 우회한다). 후보 수는 호출자가 이미 계측했고, seeded 가 비므로 호출자의 스냅샷
    # 전진 로직은 변경 없이 그대로 "미전진 = 다음 사이클 재시도" 가 된다.
    if auto_shadow_mode():
        return dict(base, ok=True, status="shadow", reason="shadow 모드(후보 계측만, enqueue 없음)")
    cap_req = cap if cap is not None else cap_cfg
    if int(cap_req or 0) <= 0:
        return dict(base, ok=False, status="disabled", reason="시드 상한 0(자동 재분석 정지)")
    cap_v = _clamp(cap_req, 1,
                   int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_MAX", 2000) or 2000), cap_cfg)
    lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
    cooldown = max(0, auto_setting_int("AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC", 1800))
    root_key = auto_root_key(schema_key)
    schema_name = schema_key.split(":", 1)[1] if ":" in schema_key else schema_key
    c, owned = _rw_conn(conn)
    if c is None:
        return dict(base, ok=False, status="noop", reason="PG 미가용")
    try:
        cur = c.cursor()
        # ① 자격 — 사람이 한 번 이상 'DB 전체 분석'을 마친 스키마에만 자동 발동(사용자 요청 범위).
        #    AGE 그래프 조회(④)보다 **먼저** 판정해, 미자격 스키마의 구조 변동이 매 tick 그래프를
        #    긁는 낭비를 막는다(인덱스 1행 조회로 종결).
        if not schema_analysis_completed(sk, schema_key, conn=c):
            cur.close()
            return dict(base, ok=True, status="ineligible", reason="DB 전체 분석 이력 없음")
        # ② 진행 중 run 이 있으면 **아무것도 하지 않는다**(적대 리뷰 B2). append 하면 run 이 계속
        #    'running' 이라 쿨다운이 영구 미발동 + 사이클마다 cap 만큼 시드가 유입되고 node_budget 까지
        #    ratchet 된다. 변경 누락은 호출자가 스냅샷을 갱신하지 않아 다음 사이클에 재시도되므로 0.
        #    **수동 run 도 대상**(재검증 C2): 사용자가 방금 승인해 도는 '전체 분석' 위에 승인 없는
        #    두 번째 분석을 겹치면 같은 노드가 두 run 에서 동시 분석돼 LLM 비용이 이중 지출되고
        #    refine 세대(pass_no)가 경합한다. 자동은 그 run 이 끝난 뒤 이어받는 게 맞다.
        cur.execute("SELECT run_id, root_label FROM node_analysis_runs "
                    "WHERE scope_key=%s AND root_key IN (%s, %s) AND status='running' "
                    "AND updated_at > now() - make_interval(secs => %s) "
                    "ORDER BY created_at DESC LIMIT 1", (sk, root_key, schema_key, lease))
        row = cur.fetchone()
        if row:
            cur.close()
            manual = str(row[1] or "") != _AUTO_ROOT_LABEL
            return dict(base, ok=True, status="busy", run_id=row[0],
                        reason=("사용자 전체 분석 run 진행 중(완료 후 재시도)" if manual
                                else "자동 재분석 run 진행 중(다음 사이클 재시도)"))
        # ③ 쿨다운 — 직전 자동 run 이 최근이면 보류. 스냅샷 미갱신이라 쿨다운 만료 후 재시도된다.
        if cooldown:
            cur.execute("SELECT 1 FROM node_analysis_runs "
                        "WHERE scope_key=%s AND root_key=%s "
                        "AND created_at > now() - make_interval(secs => %s) LIMIT 1",
                        (sk, root_key, cooldown))
            if cur.fetchone():
                cur.close()
                return dict(base, ok=True, status="cooldown", reason="자동 재분석 쿨다운")
        # ④ 그래프 실재 검증 — 신규 테이블·루틴은 AGE 투영(30분 cron)이 아직 안 됐을 수 있다. 미투영
        #    노드를 시드하면 컨텍스트 없는 빈 분석이 되므로 제외한다. 호출자가 그 노드의 마커를 남기지
        #    않으므로 투영 후 다음 사이클에 자연 재시도된다. (RO 라우팅 — 별도 커넥션)
        from modules import metadata_graph as _mg
        meta = {}
        for row, label in ([(r, "Table") for r in (_mg.schema_table_keys(sk, schema_key,
                                                                         limit=5000) or [])]
                           + [(r, "Routine") for r in (_mg.schema_routine_keys(sk, schema_key,
                                                                               limit=5000) or [])]):
            if row.get("key"):
                meta[row["key"]] = dict(row, label=label)
        present = [k for k in keys if k in meta]
        skipped_missing = len(keys) - len(present)
        if not present:
            cur.close()
            return dict(base, ok=True, status="noop", skipped_missing=skipped_missing,
                        reason="그래프 미투영(다음 sync 이후 재시도)")
        capped = len(present) > cap_v
        targets = present[:cap_v]
        refine_ok = _refine_cols_ok(cur)
        # ⑤ 신규 자동 run — enqueued 는 INSERT 시점에 확정값으로 넣는다(적대 리뷰 B7/C4). autocommit
        #    이라 run INSERT 직후 시드가 claim 가능해지는데, 'enqueued=0 커밋 → 나중에 절대값 SET' 순서면
        #    그 사이 `_enqueue_neighbors` 의 `enqueued = enqueued + n` 증분이 덮어써져 예산 회계가 깨진다
        #    (수동 경로 enqueue_schema_analysis 는 애초에 INSERT 에 확정값을 넣어 이 창이 없다).
        run_id = _new_run_id()
        if refine_ok:
            sdepth = _clamp(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_DEPTH", 2),
                            1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_MAX_DEPTH", 5)), 2)
            factor = max(1.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_AUTO_EXPAND_FACTOR", 4) or 4))
            run_max = max(1, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SCHEMA_RUN_BUDGET_MAX", 4000) or 4000))
            node_budget = max(len(targets), min(run_max, int(len(targets) * factor)))
        else:
            sdepth, node_budget = 1, len(targets)
        cur.execute(
            "INSERT INTO node_analysis_runs "
            "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
            " status, enqueued, done, failed, requested_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',%s,0,0,%s)",
            (run_id, sk, root_key, _AUTO_ROOT_LABEL, f"{schema_name} (자동 재분석)"[:512],
             sdepth, node_budget, len(targets), (requested_by or None)))
        added, added_keys = _insert_seed_jobs(cur, run_id, sk, targets, meta, refine_ok)
        if not added:
            # 시드가 하나도 안 들어간 run 은 영구 'running' 으로 남아 이후 자동 트리거를 막는다(그리고
            # lease 동안 busy·cooldown 을 점유) — 즉시 정리(jobs 는 FK ON DELETE CASCADE).
            cur.execute("DELETE FROM node_analysis_runs WHERE run_id=%s", (run_id,))
            cur.close()
            return dict(base, ok=True, status="noop", skipped_missing=skipped_missing,
                        reason="시드 삽입 0")
        if added != len(targets):
            # 일부 시드가 예외/충돌로 빠졌으면 회계를 실제 삽입분으로 보정(증분식이라 race-safe).
            cur.execute("UPDATE node_analysis_runs SET enqueued = enqueued - %s WHERE run_id=%s",
                        (len(targets) - added, run_id))
        cur.close()
        _log.info("node_analysis auto enqueue run=%s schema=%s seeded=%s/%s missing=%s capped=%s "
                  "depth=%s budget=%s reason=%s",
                  run_id, schema_key, added, len(keys), skipped_missing, capped,
                  sdepth, node_budget, reason)
        return dict(base, ok=True, status="running", run_id=run_id, seeded=added,
                    seeded_keys=added_keys, skipped_missing=skipped_missing, capped=capped)
    except Exception as exc:
        _log.warning("enqueue_change_analysis_failed schema=%s err=%r", schema_key, exc)
        return dict(base, ok=False, status="noop", reason="enqueue 실패")
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def _insert_seed_jobs(cur, run_id: str, scope_key: str, keys, meta: dict, refine_ok: bool):
    """시드 잡 삽입 — §55 규약(depth=0 + anchor_key=자기 자신). 반환 (삽입 수, 삽입된 key 목록).

    ON CONFLICT (run_id,node_key) DO NOTHING 이라 같은 run 에 재삽입해도 중복되지 않는다.
    **행 단위 try/except**(적대 리뷰 B7): 한 행의 INSERT 예외가 배치 전체를 중단시켜 시드 0 인
    'running' run 이 남지 않도록 한다 — 실패 행은 건너뛰고 회계는 실제 삽입분으로 보정된다."""
    added, added_keys = 0, []
    for k in keys:
        info = (meta or {}).get(k) or {}
        label = info.get("label") or ("Routine" if str(k).endswith("()") else "Table")
        fqn = info.get("fqn") or (str(k).split(":", 1)[1] if ":" in str(k) else "")
        name = info.get("name") or (fqn.rsplit(".", 1)[-1] if fqn else k)
        try:
            if refine_ok:
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, "
                    " status, anchor_key) "
                    "VALUES (%s,%s,%s,%s,%s,%s,0,1.0,'pending',%s) "
                    "ON CONFLICT (run_id, node_key) DO NOTHING",
                    (run_id, scope_key, k, label, str(name)[:512], fqn, k))
            else:
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,1,1.0,'pending') "
                    "ON CONFLICT (run_id, node_key) DO NOTHING",
                    (run_id, scope_key, k, label, str(name)[:512], fqn))
        except Exception as exc:
            _log.debug("auto_seed_insert_failed run=%s node=%s err=%r", run_id, k, exc)
            continue
        if (cur.rowcount or 0) > 0:
            added += 1
            added_keys.append(k)
    return added, added_keys


def _cfg_enabled() -> bool:
    return bool(getattr(_cfg, "AGENT_NODE_ANALYSIS_ENABLED", True))


# ── worker step (insight-worker 틱) ──────────────────────────────────────────
def _empty_rep() -> dict:
    """처리 0건 telemetry (진입 게이트에서 조기 반환할 때 사용 — 키 집합을 한 곳에 고정)."""
    return {"claimed": 0, "done": 0, "failed": 0, "retry_pending": 0, "enqueued": 0,
            "links": 0, "refined": 0, "budget_deferred": 0}


def process_pending(max_nodes=None, conn=None) -> dict:
    """pending 잡 처리 — **동시 작업 예산 게이트 래퍼**. 본체는 `_process_pending_inner`.

    T0b: 진입 게이트를 `with` 로 감싸기 위해 본체를 분리했다. 본체에는 중간 early return 이
    여러 개 있어(예산 여유 0·PG 미가용) 수동 enter/exit 로는 반납 누락 경로가 생긴다.
    예산 모듈 부재(배포 skew)면 게이트 없이 본체를 그대로 실행한다.
    """
    try:
        from shared import resource_budget as _rb0
    except Exception:
        return _process_pending_inner(max_nodes=max_nodes, conn=conn)
    with _rb0.acquire("task") as _ok:
        if not _ok:
            _log.info("node_analysis tick 보류 — 동시 진행 백그라운드 작업 예산 여유 없음")
            return _empty_rep()
        return _process_pending_inner(max_nodes=max_nodes, conn=conn)


def _process_pending_inner(max_nodes=None, conn=None) -> dict:
    """pending 잡을 FIFO 로 최대 max_nodes 개 처리(claim→분석→저장→이웃 재큐). 반환 telemetry.

    각 잡은 독립 try/except — 1개 실패가 배치를 중단하지 않는다. run 의 pending/running 이 모두
    소진되면 run.status 를 done(1개 이상 성공) 또는 failed(전부 실패) 로 마감."""
    # retry_pending(analysis-retry-resilience): 이번 틱에서 **terminal 로 종결하지 않고** backoff 재시도로
    #   되돌린 잡 수. failed(terminal) 와 분리해 세어야 "단절 창에 실패가 몰렸다"와 "영구 실패가 늘었다"를
    #   운영이 구분할 수 있다(insight cycle summary 의 node_analysis_* 계열).
    # budget_deferred(worker-resource-isolation T0): 공유 LLM 예산이 없어 **이번 tick 에 미룬**
    #   잡 수. failed(terminal)·retry_pending(일시 실패 backoff) 와 별개 축 — "실패가 늘었다"와
    #   "자원이 조여 뒤로 밀렸다"를 운영이 구분해야 상한을 올릴지 판단할 수 있다.
    rep = _empty_rep()
    if not _cfg_enabled():
        return rep
    # T0 전역 kill-switch — **claim 단계에서도** 게이트한다. 신규 트리거만 막고 이미 적재된
    #   잡을 계속 처리하면 "즉시 정지" 라는 운영 기대와 어긋난다(change-reanalysis cap==0 이
    #   적재분을 계속 소진했던 결함 C2 의 반복 금지). 설정 조회 실패는 활성 취급(fail-open).
    try:
        from shared import resource_budget as _rb
    except Exception:
        _rb = None            # 부트스트랩 창(모듈 부재) — 게이트 없이 종전 동작
    if _rb is not None and not _rb.background_enabled():
        return rep
    if max_nodes is None:
        # feature-0025: tick 당 처리량을 관리 콘솔에서 live 조절(override 없으면 config 기본 10 = byte-동치).
        try:
            from shared import runtime_settings as _rts_bt
            max_nodes = _rts_bt.get_int("AGENT_NODE_ANALYSIS_BATCH_PER_TICK")
        except Exception:
            max_nodes = _cfg.AGENT_NODE_ANALYSIS_BATCH_PER_TICK
    max_nodes = _clamp(max_nodes, 1, 64, 4)
    # T0: 공유 LLM 예산 여유만큼만 claim — 잡을 집어온 뒤 예산에서 거절하면 그 잡이 실패·재시도
    #   상태를 오가므로(attempts 소모), **집어오는 수를 미리 조인다**. 여유 0 이면 이번 tick 은
    #   claim 하지 않고 종료(다음 tick 재시도). 경합으로 실제 획득 시점 여유가 달라질 수 있어
    #   _run_llm 의 acquire 가 최종 게이트다. 기본 상한(16) 은 현행 최대 동시성 이상이라
    #   이 clamp 는 발동하지 않는다(byte-동치).
    if _rb is not None:
        try:
            _llm_room = int(_rb.available("llm"))
        except Exception:
            _llm_room = max_nodes
        if _llm_room <= 0:
            _log.info("node_analysis LLM 예산 여유 없음 — 이번 tick claim 생략(다음 tick 재시도)")
            return rep
        max_nodes = min(max_nodes, _llm_room)
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    from modules import llm as _llm
    try:
        cur = c.cursor()
        # fix(high): stale 'running' reclaim — 워커 크래시/SIGTERM 으로 running 에 갇힌 잡을 lease 초과 시
        #   pending 으로 되돌린다. 없으면 run 이 finalize(SELECT COUNT status IN pending/running = 0) 되지
        #   못해 영구 'running' + enqueue dedup 이 그 run 을 계속 재사용 → 재트리거 영구 불가.
        lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
        retry_ok = _retry_cols_ok(cur)
        rcfg = _retry_cfg()
        try:
            # analysis-retry-resilience: reclaim 은 즉시 재처리 의도이므로 backoff 예약(next_attempt_at)을
            #   함께 비운다 — 남겨두면 되살린 잡이 due 게이트에 다시 막혀 lease 회수가 무력해진다.
            if retry_ok:
                cur.execute("UPDATE node_analysis_jobs SET status='pending', next_attempt_at=NULL "
                            "WHERE status='running' AND updated_at < now() - make_interval(secs => %s)",
                            (lease,))
            else:
                cur.execute("UPDATE node_analysis_jobs SET status='pending' "
                            "WHERE status='running' AND updated_at < now() - make_interval(secs => %s)",
                            (lease,))
        except Exception:
            pass
        # analysis-retry-resilience(load-bearing): 처리 대기 잡을 가진 running run 의 liveness 를 갱신한다.
        #   enqueue_analysis/enqueue_schema_analysis 의 dedup 은 "updated_at 이 lease 이내인 running run"
        #   만 재사용하는데, 재시도 backoff 대기나 회로차단 대기 중에는 카운터 UPDATE 가 없어 그 run 의
        #   updated_at 이 정지한다 → lease 초과 시 stale 로 오판돼 사용자 재트리거가 **중복 run** 을 만든다.
        #   워커가 죽으면 이 갱신도 멈추므로 stale 판정 자체는 그대로 유효하다.
        try:
            cur.execute("UPDATE node_analysis_runs r SET updated_at = now() "
                        "WHERE r.status='running' AND EXISTS ("
                        "  SELECT 1 FROM node_analysis_jobs j WHERE j.run_id = r.run_id "
                        "    AND j.status IN ('pending','running'))")
        except Exception:
            pass
        # 회로차단(B): LLM 도달 불가가 확정된 동안에는 배치를 canary 1건으로 줄인다 — 종전에는 틱마다
        #   BATCH_PER_TICK(10)건을 claim 해 즉시 실패시키며 큐를 태웠다(단절이 길수록 소실 확대).
        #   canary 가 성공하면 _CIRCUIT 이 리셋돼 다음 틱부터 정상 배치로 복귀한다.
        if retry_ok and max_nodes > 1 and _circuit_open(rcfg):
            _log.info("node_analysis 회로차단 — 연속 일시 실패 %d회, 이번 틱 canary 1건만 처리",
                      int(_CIRCUIT["fails"]))
            max_nodes = 1
        # claim (원자적 단일 statement — autocommit 안전).
        #   fairness fix: **depth ASC 우선** 정렬 — 모든 run 의 root(depth 0)/얕은 노드를 먼저 처리한다.
        #   과거 created_at-only FIFO 는 대형 run(예: 124노드)의 깊은 recursion 잡이 앞줄을 독점해, 이후
        #   트리거된 단일노드 run 의 root 조차 처리 못 하고 사용자 화면이 오래 0% 에 머물렀다(starvation).
        #   depth 우선이면 새 run 의 root 가 즉시 처리돼 done>0(진행 표시)로 빠르게 전환된다.
        #   anchor(node-analysis-anchor): 같은 depth 안에서는 **relevance DESC** — 원래 대상과 관련 높은
        #   노드부터 예산을 소비한다(사용자 "낮은 우선순위로 판단" 요구의 영속 구현, ix_..._claim_priority).
        #   공정성 주의(M2): root 는 전부 depth 0·relevance 1.0 이라 tie→created_at ASC(FIFO) — **root
        #   starvation 무회귀**. 단 depth>=1 은 run 간에도 relevance 우선(FIFO 아님)이라, 관련도 높은 잡이
        #   많은 대형 run 이 신규 run 의 저관련 깊은 잡보다 먼저 소비될 수 있다(예산 캡·BATCH 로 지연만,
        #   영구 기아 아님. root 는 즉시 진행 표시). 엄격 per-run 공정성 필요 시 round-robin 후속.
        refine_ok = _refine_cols_ok(cur)
        # change-reanalysis 라이브 정지(적대 리뷰 재검증 C2): cap==0 은 **신규 트리거만** 막을 뿐,
        # 이미 적재된 SchemaAuto 잡은 계속 claim 돼 최대 node_budget(4000)까지 LLM 을 소진했다 —
        # "폭주 시 즉시 정지" 라는 운영 기대와 어긋난다(중단 수단이 재배포/수동 SQL 뿐). cap==0 인
        # 동안에는 자동 run 의 pending 잡을 **보류**(삭제 아님 — cap 을 되돌리면 그대로 재개)한다.
        # 정상(cap>0)에서는 조건절이 붙지 않아 기존 claim 과 byte-동치.
        auto_paused = auto_cap_value() == 0
        pause_sql = ("  AND run_id NOT IN (SELECT run_id FROM node_analysis_runs "
                     "                     WHERE root_label = '" + _AUTO_ROOT_LABEL + "') "
                     if auto_paused else "")
        # analysis-retry-resilience: backoff 예약이 아직 도달하지 않은 잡은 이번 틱에서 건너뛴다.
        #   (0049 미적용 창에서는 조건절이 붙지 않아 기존 claim 과 byte-동치.)
        due_sql = "  AND (next_attempt_at IS NULL OR next_attempt_at <= now()) " if retry_ok else ""
        pause_sql = pause_sql + due_sql
        if refine_ok:
            # §55: anchor_key(per-seed 앵커)·pass_no(refine 세대)·analysis(재-pending 행의 직전 분석문 =
            # refine payload 의 previous_analysis) 를 함께 claim.
            cur.execute(
                "UPDATE node_analysis_jobs SET status='running' WHERE id IN ("
                "  SELECT id FROM node_analysis_jobs WHERE status='pending' " + pause_sql +
                "  ORDER BY depth ASC, relevance DESC, created_at ASC LIMIT %s FOR UPDATE SKIP LOCKED) "
                "RETURNING id, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, "
                "          anchor_key, pass_no, analysis",
                (max_nodes,))
            claimed = cur.fetchall()
        else:
            cur.execute(
                "UPDATE node_analysis_jobs SET status='running' WHERE id IN ("
                "  SELECT id FROM node_analysis_jobs WHERE status='pending' " + pause_sql +
                "  ORDER BY depth ASC, relevance DESC, created_at ASC LIMIT %s FOR UPDATE SKIP LOCKED) "
                "RETURNING id, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth",
                (max_nodes,))
            claimed = [tuple(row) + ("", 0, None) for row in cur.fetchall()]
        rep["claimed"] = len(claimed)
        touched_runs = set()
        anchors: dict = {}   # run_id[|anchor_key] -> anchor 서술자(틱 내 캐시, 앵커당 1회 그래프 조회)
        # feature-0025 병렬 처리: LLM 호출(느린 부분)만 스레드 병렬화하고, 노드 분석의 DB I/O(claim/
        #   UPDATE/enqueue/backrefine)와 공유 상태(anchors·cur·c·rep)는 전부 단일 스레드 유지한다 — psycopg
        #   커넥션은 스레드 비안전이므로 공유 conn 을 병렬 접근하지 않기 위함. (주의: LLM 단계 내부의
        #   usage 회계(_record_llm_usage)는 호출당 단명 PG 연결을 열어 최대 concurrency 개가 병렬 생성될
        #   수 있으나, autocommit·transaction-pooling 이라 서버측 점유가 짧다. §82 는 장기 lock-wait 풀
        #   소진이 원인이었고, 여기선 그런 장기 점유를 만들지 않는다.) 아래
        #   _gather/_persist 는 기존 per-job 본체를 두 단계로 분해한 것이며, concurrency==1(및 1건)은
        #   gather→llm→persist 를 노드마다 인터리브해 **기존 동작 byte-동치**, >1 은 gather 전부 →
        #   LLM 병렬(ThreadPoolExecutor) → persist 전부(claim 순서 유지)로 처리한다.
        def _gather(job_row):
            (jid, run_id, scope_key, node_key, node_label, node_name, node_fqn,
             depth, anchor_key, pass_no, prev_text) = job_row
            touched_runs.add(run_id)
            w = {"jid": jid, "run_id": run_id, "scope_key": scope_key, "node_key": node_key,
                 "node_label": node_label, "node_name": node_name, "node_fqn": node_fqn,
                 "depth": depth, "anchor_key": anchor_key, "pass_no": pass_no,
                 "ctx": None, "root": None, "anchor": None, "payload": None, "err": None,
                 # analysis-retry-resilience: LLM 실패 분류({kind,tag,detail}) — _run_llm 이 채우고
                 #   _persist 가 읽어 backoff 재시도 / terminal 종결을 가른다.
                 "fail": None}
            try:
                # node-analysis-completeness: Table 은 컨텍스트 수집 전에 컬럼 인벤토리 보강 —
                #   같은 틱의 _fetch_context 가 HAS_COLUMN 자식을 보고 (a) payload 컬럼 컨텍스트
                #   (b) §55 직계 컬럼 게이트 면제 편입이 함께 살아난다. fail-soft(0 = 종전 동작).
                if (node_label or "") == "Table":
                    _ensure_table_columns(c, node_key)
                    # feature-0031 접지(L0): 같은 자리에서 통계 증거도 보강한다 — 분석되는
                    #   테이블만 보므로 쓰이지 않을 통계를 미리 모으는 낭비가 없다. fail-soft.
                    _ensure_table_stats(c, node_key)
                ctx = _fetch_context(node_key, c)
                root = ctx.get("root") or {"label": node_label, "name": node_name,
                                           "fqn": node_fqn, "key": node_key}
                # per-seed 앵커(§55): 시드 잡(anchor_key==node_key)은 방금 조회한 자기 노드를 재사용(중복 조회 0).
                anchor = _load_anchor(c, cur, run_id, anchors, anchor_key,
                                      self_node=(ctx.get("root") if (anchor_key and anchor_key == node_key) else None))
                payload = _build_payload(root, ctx)
                # feature-0031 접지(L1): 수집된 통계를 payload 의 `evidence` 로 주입한다. 증거가
                #   없으면 키 자체를 넣지 않아 종전 payload 와 동형이다(LLM 콜 수는 불변 — 같은
                #   호출에 더 나은 입력을 준다).
                if (node_label or "") == "Table":
                    ev = _table_evidence(c, node_key)
                    if ev:
                        payload["evidence"] = ev
                # ADR-017: hover 프롬프트 지침을 run 전 노드 분석에 주입 — LLM 이 자율 판단해 반영.
                if anchor and anchor.get("prompt"):
                    payload["user_intent"] = anchor["prompt"]
                # §55 refine-not-override: 이전 분석문을 payload 에 동봉 — LLM 이 비교·융합(override 금지 계약).
                #   재-pending refine 행은 자기 행의 직전 분석문, 그 외는 최신 done 행(타 run 포함)에서.
                prev_obj = _parse_analysis(prev_text)
                if prev_obj is None:
                    prev_obj = _latest_done_analysis(cur, scope_key, node_key, exclude_id=jid)
                if prev_obj:
                    payload["previous_analysis"] = prev_obj
                # §55 back-refine: refine 세대 잡은 같은 run 에서 분석 완료된 인접 노드의 발견을 동봉 —
                #   "후속 재귀 탐색 중 추가로 분석된 내용" 으로 빈약 분석을 보충한다.
                if refine_ok and int(pass_no or 0) > 0:
                    rf = _related_findings(cur, run_id, ctx, exclude_key=node_key)
                    if rf:
                        payload["related_findings"] = rf
                w["ctx"], w["root"], w["anchor"], w["payload"] = ctx, root, anchor, payload
            except Exception as exc:
                w["err"] = exc
            return w

        def _run_llm(w):
            """LLM 노드 분석 1회. **DB 미접근 — 스레드 병렬 안전**. 예외는 Exception 객체로 반환(직렬 persist 가 처리).

            analysis-retry-resilience: 실패 분류를 `w["fail"]` 에 싣는다. 각 스레드는 **자기 work item
            만** 쓰므로(공유 dict 아님) 병렬에서도 안전하다."""
            if w["err"] is not None or w["payload"] is None:
                return None
            # T0: 공유 LLM 예산 최종 게이트. claim 단계에서 여유만큼만 집어왔지만 다른 워커
            #   (cluster_label·분류 제안)와 예산을 공유하므로 실행 시점에 여유가 사라질 수 있다.
            #   비차단 — 거절되면 kind='budget' 으로 표시해 **attempts 를 소모하지 않고** 짧게
            #   재예약한다(_record_failure 의 budget 분기).
            # retry_ok=False(0049 미적용 창)에서는 예산 게이트를 걸지 않는다 — budget 분기가
            #   attempts 컬럼에 의존하므로, 그 창에서 거절되면 terminal failed 로 굳어 버린다.
            if _rb is None or not retry_ok:
                return _run_llm_inner(w)
            with _rb.acquire("llm") as _ok:
                if not _ok:
                    w["fail"] = {"kind": "budget", "tag": "llm_budget"}
                    return None
                return _run_llm_inner(w)

        def _run_llm_inner(w):
            """예산 획득 후의 실제 LLM 호출 본체 (분리 이유: 예산 게이트와 호출 로직 분리)."""
            sink: dict = {}
            try:
                # 0047: 병렬 스레드라 active-datasource ContextVar 가 전파되지 않는다 →
                #   사용 기록의 데이터소스 귀속을 위해 work item 의 scope_key 를 명시 전달.
                obj = _llm.llm_node_analysis(w["payload"], scope_key=w.get("scope_key"), error_sink=sink)
            except Exception as exc:
                w["fail"] = _llm.classify_node_analysis_failure(exc)
                return exc
            if obj is None:
                # sink 가 비어 있으면(계약 밖 경로) 보수적으로 transient — 재시도 상한이 비용을 막는다.
                w["fail"] = dict(sink) if sink else _llm.classify_node_analysis_failure(empty=True)
            return obj

        def _record_failure(jid, run_id, message, fail_info) -> None:
            """실패 1건 기록 (analysis-retry-resilience). **단일 스레드에서만 호출**(cur/rep/_CIRCUIT).

            일시 실패(network·timeout·429·5xx·빈 응답)는 terminal 로 굳히지 않고 `attempts+1` 과 함께
            pending 으로 되돌려 지수 backoff 후 재시도한다 — 네트워크가 복구되면 **사람 개입 없이** 그
            잡이 다시 claim 된다(본 cycle 의 핵심). `MAX_ATTEMPTS` 도달 또는 영구 실패(bad_model 등)는
            종전과 동일하게 terminal `failed` + `runs.failed+1`. 0049 미적용 창(retry_ok=False)은
            전부 종전 경로.
            """
            kind = str((fail_info or {}).get("kind") or "")
            tag = str((fail_info or {}).get("tag") or "")
            # T0 예산 거절: **실패가 아니다** — 자원이 조여 뒤로 밀린 것이다. attempts 를 소모하지
            #   않고(영구 실패로 굳지 않게) 짧게 재예약한다. 예산 상한 최소값이 1 이라 여유가
            #   영구 0 일 수 없고, 전역 정지는 kill-switch 가 담당하므로 무한 루프가 되지 않는다.
            if retry_ok and kind == "budget":
                # **연속** budget 거절이면 attempts 를 증가시킨다(codex P2): 첫 거절은 무료(일시
                #   경합)지만, 지속 contention 에서 attempts 를 영원히 올리지 않으면 그 잡이 무기한
                #   pending 으로 남아 run 이 영구 running → enqueue dedup 이 사용자 재트리거를 막는다.
                #   상한 도달 시 terminal 종결해 표면화한다(운영자가 상한을 올리고 재트리거).
                cur.execute(
                    "UPDATE node_analysis_jobs SET "
                    "  attempts = attempts + CASE WHEN error_kind = 'budget' THEN 1 ELSE 0 END, "
                    "  status = CASE WHEN error_kind = 'budget' AND attempts + 1 >= %s "
                    "                THEN 'failed' ELSE 'pending' END, "
                    "  next_attempt_at = CASE WHEN error_kind = 'budget' AND attempts + 1 >= %s "
                    "                THEN NULL ELSE now() + make_interval(secs => %s) END, "
                    "  error_kind = CASE WHEN error_kind = 'budget' AND attempts + 1 >= %s "
                    "                THEN 'budget_exhausted' ELSE 'budget' END, "
                    "  error = %s "
                    "WHERE id=%s RETURNING status",
                    (rcfg["max_attempts"], rcfg["max_attempts"], _BUDGET_DEFER_SEC,
                     rcfg["max_attempts"], "공유 LLM 예산 여유 없음 — 자동 재시도 대기", jid))
                _brow = cur.fetchone() or (None,)
                if str(_brow[0] or "") == "pending":
                    rep["budget_deferred"] += 1
                    return            # terminal 아님 · runs.failed 미증가
                # 상한 도달 = terminal. **여기서 완결하고 반환한다** — 아래 generic 실패 분기로
                #   흐르면 attempts 가 두 번 증가하고 error_kind='budget_exhausted' 가 'budget' 로
                #   덮어써진다(codex 재검증 P2-b). 종결 카운터는 이 분기가 직접 올린다.
                _log.warning("node_analysis job=%s 공유 LLM 예산 대기 상한(%d회) 도달 — terminal 종결",
                             jid, rcfg["max_attempts"])
                cur.execute("UPDATE node_analysis_runs SET failed = failed + 1 WHERE run_id=%s", (run_id,))
                rep["failed"] += 1
                return
            if retry_ok and kind == _llm.FAILURE_TRANSIENT:
                # 단일 statement 로 attempts 증가 + 상한 판정 + backoff 예약을 원자 처리(autocommit 안전).
                #   backoff = BASE × 2^attempts(증가 전 값 = 0-based) → 60s, 120s, 240s … MAX 캡.
                cur.execute(
                    "UPDATE node_analysis_jobs SET attempts = attempts + 1, "
                    "  status = CASE WHEN attempts + 1 >= %s THEN 'failed' ELSE 'pending' END, "
                    "  next_attempt_at = CASE WHEN attempts + 1 >= %s THEN NULL "
                    "    ELSE now() + make_interval(secs => LEAST((%s * power(2, attempts))::int, %s)) END, "
                    "  error_kind = CASE WHEN attempts + 1 >= %s THEN 'transient_exhausted' ELSE 'transient' END, "
                    "  error = %s "
                    "WHERE id=%s RETURNING status, attempts, next_attempt_at",
                    (rcfg["max_attempts"], rcfg["max_attempts"], rcfg["base_sec"], rcfg["max_sec"],
                     rcfg["max_attempts"], str(message)[:500], jid))
                row = cur.fetchone() or (None, None, None)
                # 회로차단 신호: 연속 일시 실패를 센다(성공 시 0 으로 리셋).
                _CIRCUIT["fails"] = int(_CIRCUIT["fails"]) + 1
                if str(row[0] or "") == "pending":
                    rep["retry_pending"] += 1
                    _log.info("node_analysis job=%s 일시 실패(%s) — 시도 %s회, %s 이후 자동 재시도",
                              jid, tag or "transient", row[1], row[2])
                    return   # terminal 아님 — runs.failed 를 올리지 않는다(run 은 running 유지).
                _log.warning("node_analysis job=%s 일시 실패 상한(%d회) 도달 — terminal 종결(%s)",
                             jid, rcfg["max_attempts"], tag or "transient")
            elif retry_ok:
                cur.execute("UPDATE node_analysis_jobs SET attempts = attempts + 1, status='failed', "
                            "next_attempt_at=NULL, error_kind=%s, error=%s WHERE id=%s",
                            ((kind or "permanent")[:32], str(message)[:500], jid))
            else:
                cur.execute("UPDATE node_analysis_jobs SET status='failed', error=%s WHERE id=%s",
                            (str(message)[:500], jid))
            cur.execute("UPDATE node_analysis_runs SET failed = failed + 1 WHERE run_id=%s", (run_id,))
            rep["failed"] += 1

        def _persist(w, obj):
            """LLM 결과 반영(UPDATE·suggested_links·backrefine·enqueue). **단일 스레드에서만 호출**(cur/c/rep)."""
            jid = w["jid"]; run_id = w["run_id"]; scope_key = w["scope_key"]
            node_label = w["node_label"]; node_name = w["node_name"]; node_fqn = w["node_fqn"]
            ctx = w["ctx"]; root = w["root"]; anchor = w["anchor"]
            anchor_key = w["anchor_key"]; pass_no = w["pass_no"]; depth = w["depth"]
            try:
                # gather 또는 LLM 단계 예외는 기존 per-job try 와 동일하게 아래 except 로 흘려보낸다.
                if w["err"] is not None:
                    raise w["err"]
                if isinstance(obj, Exception):
                    raise obj
                if isinstance(obj, dict):
                    analysis_text = json.dumps({
                        "summary": str(obj.get("summary") or "").strip(),
                        "relationships": str(obj.get("relationships") or "").strip(),
                        "usage": str(obj.get("usage") or "").strip(),
                        "caveats": str(obj.get("caveats") or "").strip(),
                    }, ensure_ascii=False)
                    # 저장·표시용 모델 라벨은 llm_node_analysis 의 실제 라우팅과 동일 순서로 해석
                    # (전용 AGENT_NODE_ANALYSIS_MODEL 우선) — 상세 패널이 실제 사용 모델(claude-haiku)을
                    # 표시하도록. 이 순서가 어긋나면 UI 에 gemma(edge)로 오표시된다.
                    model = (getattr(_cfg, "AGENT_NODE_ANALYSIS_MODEL", None)
                             or getattr(_cfg, "AGENT_INSIGHT_MODEL", None)
                             or getattr(_cfg, "OPENAI_MODEL", None))
                    # node-role-viz: Table 노드 역할 분류(LLM "role" 우선, 무효/누락 휴리스틱 폴백) —
                    #   그래프 뷰 시각 표식(역할색·아이콘)의 데이터 원천. 그 외 라벨은 NULL.
                    role = _resolve_role((root.get("label") or node_label), obj, node_name, node_fqn)
                    try:
                        cur.execute("UPDATE node_analysis_jobs SET status='done', analysis=%s, model=%s, role=%s, "
                                    "error=NULL WHERE id=%s",
                                    (analysis_text, (str(model)[:128] if model else None), role, jid))
                    except Exception as role_exc:
                        # 마이그레이션 창(role 컬럼 부재) — LLM 결과를 버리지 않게 role 제외 UPDATE 폴백(B1).
                        _warn_role_column_once("process_pending", role_exc)
                        cur.execute("UPDATE node_analysis_jobs SET status='done', analysis=%s, model=%s, "
                                    "error=NULL WHERE id=%s",
                                    (analysis_text, (str(model)[:128] if model else None), jid))
                    cur.execute("UPDATE node_analysis_runs SET done = done + 1 WHERE run_id=%s", (run_id,))
                    rep["done"] += 1
                    # analysis-retry-resilience: 성공했으므로 재시도 흔적을 정리하고(과거 backoff 예약·분류가
                    #   남아 진행 패널의 '재시도 대기' 집계를 흐리지 않게) 회로차단 카운터를 닫는다.
                    if retry_ok:
                        try:
                            cur.execute("UPDATE node_analysis_jobs SET error_kind=NULL, next_attempt_at=NULL "
                                        "WHERE id=%s", (jid,))
                        except Exception:
                            pass
                    _CIRCUIT["fails"] = 0
                    # §55: LLM 이 컨텍스트 안에서 확신한 조인 후보(suggested_links)를 관계 저장소에
                    # candidate 로 적재 — 끝점 실재 검증 통과분만. 이후 프로브·자기교정이 판정한다.
                    try:
                        rep["links"] += _ingest_suggested_links(c, scope_key, root, ctx, obj)
                    except Exception as link_exc:
                        _log.debug("suggested_links_ingest_failed job=%s err=%r", jid, link_exc)
                    # §55 back-refine: 같은 run 의 선행 done 인접 노드 중 빈약(thin) 분석을 재-pending
                    # (pass_no+1) — 지금 분석된 새 맥락(related_findings)으로 보충된다. run 당 REFINE_MAX 캡.
                    if refine_ok:
                        try:
                            rep["refined"] += _backrefine_neighbors(c, cur, run_id, jid, ctx)
                        except Exception as br_exc:
                            _log.debug("backrefine_failed job=%s err=%r", jid, br_exc)
                elif refine_ok and int(pass_no or 0) > 0:
                    # §55 패널 fix: **refine 실패는 원 분석(done)을 강등하지 않는다** — 재-pending 전의
                    # 분석문이 행에 그대로 있으므로 상태만 done 으로 복원(refine-not-override 계약 —
                    # 보충 실패가 기존 유효 분석·마커·집계(done_keys)를 지우면 안 된다). 카운터: done 은
                    # 최초 완료에 이미 1회 계상 — 재계상 없음(enqueued 만 재-pend 시 +1, 단조 유지).
                    cur.execute("UPDATE node_analysis_jobs SET status='done', error=%s WHERE id=%s",
                                ("refine 실패(빈 응답) — 원 분석 유지", jid))
                else:
                    # analysis-retry-resilience: 종전엔 여기서 곧바로 terminal 'failed' 였다 — 네트워크
                    #   단절 창의 잡이 통째로 굳어 복구 후에도 되살아나지 않은 근본 지점.
                    _record_failure(jid, run_id, "LLM 분석 실패(빈 응답/파싱)", w.get("fail"))
                # 이웃 재큐 (예산 내) — 성공/실패 무관(그래프 구조는 분석 성공과 독립).
                #   anchor(잡의 앵커 — 단일 노드 run 은 루트, 스키마 run 은 시드) 관련도로 게이트·우선순위화.
                rep["enqueued"] += _enqueue_neighbors(c, cur, run_id, scope_key, ctx, depth, anchor,
                                                      anchor_key=(anchor_key or ""))
            except Exception as exc:
                _log.warning("node_analysis job=%s 처리 실패 err=%r", jid, exc)
                try:
                    if refine_ok and int(pass_no or 0) > 0:
                        # §55 패널 fix(위와 동형): refine 예외도 원 분석 보존 — done 복원.
                        cur.execute("UPDATE node_analysis_jobs SET status='done', error=%s WHERE id=%s",
                                    (("refine 실패: " + str(exc))[:500], jid))
                    else:
                        # analysis-retry-resilience: 예외도 분류해 일시 실패면 backoff 재시도로 되돌린다.
                        #   (gather 단계 예외 — PG/그래프 조회 실패 — 도 여기로 오며, 그 경로는 LLM 을
                        #    호출하지 않으므로 재시도가 외부 비용을 만들지 않는다. 상한은 동일 적용.)
                        _record_failure(jid, run_id, str(exc),
                                        w.get("fail") or _llm.classify_node_analysis_failure(exc))
                except Exception:
                    pass

        _na_conc = 1
        try:
            from shared import runtime_settings as _rts_na
            _na_conc = max(1, min(8, int(_rts_na.node_analysis_concurrency())))
        except Exception:
            _na_conc = 1
        if _na_conc <= 1 or len(claimed) <= 1:
            # 직렬(기존 byte-동치): 노드마다 gather→llm→persist 인터리브.
            for job_row in claimed:
                w = _gather(job_row)
                _persist(w, _run_llm(w))
        else:
            # 병렬: gather 전부(단일 스레드, anchors 캐시 안전) → LLM 병렬 → persist 전부(claim 순서, 단일 스레드).
            works = [_gather(job_row) for job_row in claimed]
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=_na_conc) as _ex:
                objs = list(_ex.map(_run_llm, works))
            for w, obj in zip(works, objs):
                _persist(w, obj)
        # run 마감 판정
        for run_id in touched_runs:
            try:
                cur.execute("SELECT COUNT(*) FROM node_analysis_jobs "
                            "WHERE run_id=%s AND status IN ('pending','running')", (run_id,))
                remaining = int((cur.fetchone() or [0])[0])
                if remaining == 0:
                    cur.execute("SELECT done, failed FROM node_analysis_runs WHERE run_id=%s", (run_id,))
                    r = cur.fetchone() or (0, 0)
                    final = "done" if int(r[0]) > 0 else "failed"
                    cur.execute("UPDATE node_analysis_runs SET status=%s WHERE run_id=%s AND status='running'",
                                (final, run_id))
            except Exception:
                pass
        cur.close()
    except Exception as exc:
        _log.warning("process_pending_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


# ── 굳은 일시 실패 회수 (analysis-retry-resilience, 2026-07-30) ────────────────
# 0049 이전에 terminal 로 굳은 실패(라이브 실측: 'LLM 분석 실패(빈 응답/파싱)' 130건이 07-27·07-29
# 두 장애 창에 뭉쳐 있음)와, 상한을 소진한 transient_exhausted 를 다시 큐에 올린다.
#
# **회수 대상 판정** — 사람이 만든 인위적 실패는 건드리지 않는다:
#   · `error_kind LIKE 'transient%'`  = 본 cycle 이후의 일시 실패(상한 소진분 포함)
#   · `error_kind IS NULL AND error LIKE 'LLM %'` = 0049 이전 레거시 LLM 실패
#   → 'verification-cleanup(취소)'(라이브 580건, 검증 잔재)·permanent 는 **제외**된다.
# LIKE 패턴은 **반드시 파라미터로** 넘긴다 — SQL 리터럴 'transient%' 를 params 와 함께 execute 하면
# psycopg 가 그 `%` 를 포맷 지시자로 읽어 "not enough arguments for format string" 으로 죽는다.
_RETRYABLE_FAILED_SQL = "(error_kind LIKE %s OR (error_kind IS NULL AND error LIKE %s))"
_RETRYABLE_FAILED_ARGS = ("transient%", "LLM %")


def retry_failed_jobs(run_id: str | None = None, scope_key: str | None = None, *,
                      limit: int = 500, dry_run: bool = False, conn=None) -> dict:
    """굳은 일시 실패 잡을 pending 으로 회수한다. 반환 {ok, retried, runs, dry_run, reason?}.

    사람이 명시적으로 요청하는 경로(진행 패널 '재시도' 버튼 · 1회성 CLI)라 **attempts 를 0 으로
    리셋**해 새 예산을 준다(자동 backoff 재시도와 구분 — 자동 경로는 attempts 를 누적해 상한에서 멈춘다).

    run 카운터 정합도 함께 복원한다: 되살린 수만큼 `runs.failed` 를 차감하고 `status='running'` 으로
    되돌린다(이미 done/failed 로 마감된 run 도 다시 진행 상태가 된다). 이 복원이 없으면 진행 패널의
    완료율이 영구히 어긋나고, finalize 판정이 그 run 을 두 번 마감한다.
    """
    if not _cfg_enabled():
        return {"ok": False, "reason": "disabled"}
    lim = _clamp(limit, 1, 5000, 500)
    c, owned = _rw_conn(conn)
    if c is None:
        return {"ok": False, "reason": "PG 미가용"}
    try:
        cur = c.cursor()
        if not _retry_cols_ok(cur):
            cur.close()
            return {"ok": False, "reason": "재시도 계정(alembic 0049) 미적용 — 배포 후 다시 시도"}
        where = ["status='failed'", _RETRYABLE_FAILED_SQL]
        params: list = list(_RETRYABLE_FAILED_ARGS)
        if run_id:
            where.append("run_id=%s")
            params.append(str(run_id))
        if scope_key:
            where.append("scope_key=%s")
            params.append(str(scope_key)[:96])
        pred = " AND ".join(where)
        if dry_run:
            cur.execute(f"SELECT count(*), count(DISTINCT run_id) FROM node_analysis_jobs WHERE {pred}",
                        tuple(params))
            row = cur.fetchone() or (0, 0)
            cur.close()
            # codex P2-2: 실제 실행은 LIMIT 으로 잘리므로 dry-run 도 **이번 실행량**을 보고해야 한다 —
            #   전체 대상 수만 보여주면 운영자가 1회 LLM 비용 규모를 과대 판단한다(eligible 은 별도 표기).
            eligible = int(row[0] or 0)
            return {"ok": True, "dry_run": True, "retried": min(eligible, lim), "eligible": eligible,
                    "capped": eligible > lim, "runs": int(row[1] or 0)}
        # 단일 statement(CTE) — 잡 회수와 run 카운터 복원을 한 번에 처리해 중간 상태를 노출하지 않는다.
        cur.execute(
            "WITH tgt AS ("
            f"  SELECT id FROM node_analysis_jobs WHERE {pred} ORDER BY id LIMIT %s"
            "), upd AS ("
            "  UPDATE node_analysis_jobs j SET status='pending', attempts=0, next_attempt_at=NULL, "
            "         error=NULL, error_kind=NULL "
            "    FROM tgt WHERE j.id = tgt.id "
            "  RETURNING j.run_id"
            "), agg AS (SELECT run_id, count(*) AS n FROM upd GROUP BY run_id) "
            "UPDATE node_analysis_runs r "
            "   SET failed = GREATEST(0, r.failed - agg.n), status='running', updated_at=now() "
            "  FROM agg WHERE r.run_id = agg.run_id "
            "RETURNING r.run_id, agg.n",
            tuple(params) + (lim,))
        rows = cur.fetchall() or []
        cur.close()
        retried = sum(int(r[1] or 0) for r in rows)
        if retried:
            _log.info("node_analysis 일시 실패 회수: %d건 / run %d개 (run_id=%s scope=%s)",
                      retried, len(rows), run_id or "*", scope_key or "*")
        return {"ok": True, "dry_run": False, "retried": retried, "runs": len(rows),
                "run_ids": [r[0] for r in rows][:50]}
    except Exception as exc:
        _log.warning("retry_failed_jobs_failed err=%r", exc)
        return {"ok": False, "reason": "회수 실패"}
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def backfill_roles(limit=200, conn=None) -> int:
    """role 도입(alembic 0031) 이전의 done Table 잡에 역할을 휴리스틱으로 1회 백필(LLM 재호출 없음).

    insight-worker 틱마다 소량(limit) 처리 — 잔여 0 이면 SELECT 만 하고 즉시 반환(자기 종결).
    휴리스틱 결과가 'etc' 여도 저장하므로 같은 행을 재선택하지 않는다(멱등·수렴 보장). 반환: 갱신 수."""
    if not _cfg_enabled():
        return 0
    c, owned = _rw_conn(conn)
    if c is None:
        return 0
    updated = 0
    try:
        cur = c.cursor()
        cur.execute("SELECT id, node_name, node_fqn, analysis FROM node_analysis_jobs "
                    "WHERE status='done' AND role IS NULL AND node_label='Table' "
                    "ORDER BY id LIMIT %s", (max(1, int(limit)),))
        rows = cur.fetchall()
        for jid, node_name, node_fqn, analysis_text in rows:
            analysis = None
            if analysis_text:
                try:
                    analysis = json.loads(analysis_text)
                except Exception:
                    analysis = str(analysis_text)
            role = classify_role_heuristic(node_name, node_fqn, analysis)
            cur.execute("UPDATE node_analysis_jobs SET role=%s WHERE id=%s", (role, jid))
            updated += 1
        cur.close()
        if updated:
            _log.info("node_analysis role backfill: %d행 (휴리스틱)", updated)
    except Exception as exc:
        # B2: 신규 쓰기 경로 — 마이그레이션 누락 등 반복 실패가 프로덕션 로그레벨에서 무신호가 되지 않게 warning.
        _log.warning("backfill_roles_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return updated


def _load_anchor(c, cur, run_id: str, cache: dict, anchor_key: str = "", self_node=None) -> dict:
    """잡의 관련도 채점 기준(anchor) 서술자를 로드·캐시. 실패 시에도 최소 서술자 반환.

    anchor_key(alembic 0038, §55)가 비면 run 의 root(기존 동작). 스키마(DB) 단위 run 은 시드마다
    자기 자신이 앵커(per-seed) — Schema 명칭이 아니라 각 테이블/루틴 기준으로 재귀가 게이트된다.
    user_prompt 는 run 전역 지침이라 per-seed 앵커에도 합류한다. self_node: 호출측이 이미 조회한
    앵커 노드(시드 자신) — 중복 그래프 조회 회피."""
    ak = str(anchor_key or "").strip()
    base = _load_run_anchor(c, cur, run_id, cache)
    if not ak or (base and ak == base.get("key")):
        return base
    ck = f"{run_id}|{ak}"
    if ck in cache:
        return cache[ck]
    anchor = base
    try:
        node = self_node if isinstance(self_node, dict) else ((_fetch_context(ak, c).get("root")) or {})
        anchor = _build_anchor(ak, node.get("label") or "", node.get("name")
                               or (ak.split(":", 1)[-1].rsplit(".", 1)[-1]), node.get("description") or "")
        if base and base.get("prompt"):
            anchor["prompt"] = base["prompt"]
            anchor["tokens"] = (anchor.get("tokens") or set()) | _meaningful_tokens(base["prompt"])
    except Exception as exc:
        _log.debug("load_seed_anchor_failed err=%r", exc)
    cache[ck] = anchor
    return anchor


def _load_run_anchor(c, cur, run_id: str, cache: dict) -> dict:
    """run 의 원래 루트 서술자(anchor)를 로드·캐시. 관련도 채점 기준. 실패 시에도 최소 서술자 반환.

    루트 설명은 그래프에서 run 당 1회만 조회(틱 캐시)해 비용을 제한한다. 그래프 미발견 시 run 행 값만으로 구성."""
    if run_id in cache:
        return cache[run_id]
    anchor = None
    try:
        try:
            cur.execute("SELECT root_key, root_label, root_name, user_prompt "
                        "FROM node_analysis_runs WHERE run_id=%s", (run_id,))
            r = cur.fetchone()
        except Exception as up_exc:
            # 마이그레이션 창(user_prompt 컬럼 부재) — 지침 없이 legacy 조회(B1 동형).
            _warn_uprompt_column_once("load_anchor", up_exc)
            cur.execute("SELECT root_key, root_label, root_name, NULL "
                        "FROM node_analysis_runs WHERE run_id=%s", (run_id,))
            r = cur.fetchone()
        if r:
            root_key, root_label, root_name = r[0], (r[1] or ""), (r[2] or "")
            user_prompt = (str(r[3]).strip() if r[3] else "")
            root_desc = ""
            try:
                rnode = (_fetch_context(root_key, c).get("root")) or {}
                root_desc = rnode.get("description") or ""
            except Exception:
                pass
            anchor = _build_anchor(root_key, root_label, root_name, root_desc)
            if user_prompt:
                # ADR-017: 사용자 지침 어휘를 앵커 토큰에 합류 — 관련도 채점(재귀 방향)이 지침을 따른다.
                anchor["prompt"] = user_prompt
                anchor["tokens"] = (anchor.get("tokens") or set()) | _meaningful_tokens(user_prompt)
    except Exception as exc:
        _log.debug("load_anchor_failed err=%r", exc)
    cache[run_id] = anchor
    return anchor


def _score_candidates(ctx: dict, cur_depth: int, anchor: dict) -> list:
    """이웃 후보를 (relevance, node) 로 채점·게이트·정렬(내림차순)한다.

    - cur_depth==0 의 직속 컬럼(=원래 대상의 하위 컬럼)은 relevance=1.0 으로 **무조건 통과**(기본 분석).
    - 그 외는 앵커(원래 루트) 상대 관련도로 채점, 이웃 깊이가 깊을수록 임계 상향 → 허브 재탐색 억제.
    - 임계 미달·Schema 허브·파단 엣지는 제외(재귀 낮은 우선순위 = 탈락).
    """
    if not anchor:   # 앵커 로드 실패(드묾) → 보수적 게이팅(하위 컬럼만 통과, fan-out 억제).
        anchor = {"key": "", "scope": "", "label": "", "table_fqn": "",
                  "tokens": set(), "desc_tokens": set()}
    meta_map = ctx.get("neighbor_meta") or {}
    neighbor_depth = cur_depth + 1
    # 임계: 이웃 depth 가 깊을수록 상향(허브 재탐색 억제). depth 1 은 MIN, depth>=2 는 _DEEP 에서
    #   깊이당 추가 가산(MAX_DEPTH=5 등 깊은 예산에서도 "깊을수록 상향" 유지, M3). 상한 0.7.
    min_val = float(getattr(_cfg, "AGENT_NODE_ANALYSIS_RELEVANCE_MIN", 0.18))
    deep_val = float(getattr(_cfg, "AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP", 0.34))
    if neighbor_depth <= 1:
        min_rel = min_val
    else:
        min_rel = min(0.7, deep_val + 0.06 * (neighbor_depth - 2))
    kept = []   # (rel, node, same_depth) — same_depth=True 는 depth 를 늘리지 않는 승격(부모 테이블)
    for n in (ctx.get("neighbors") or []):
        k = n.get("key")
        if not k:
            continue
        meta = meta_map.get(k) or {}
        if cur_depth == 0 and meta.get("child"):
            kept.append((1.0, n, False))   # 원래 대상의 직속 하위 컬럼 → 기본 분석
            continue
        if meta.get("parent") and (n.get("label") or "") == "Table":
            # graph-funcproc(ADR-017): 재귀로 분석된 **참조 컬럼의 소속(부모) 테이블**은 임계와
            # 무관하게 분석 대상으로 승격(사용자 요구 "테이블까진 분석"). 고정 승격값(교차 제품은
            # 감쇠)이라 그 테이블의 *다음* 확장은 여전히 앵커 게이팅이 막는다 — 재귀 심화 억제.
            # depth 는 컬럼과 같은 층(same_depth) — "컬럼의 소속" 은 추가 hop 이 아니다(예산 정합).
            # §18.8 패널(BLOCKING→수정): 단 **cur_depth==0(루트가 Column)** 일 땐 same-depth 금지 —
            # 부모가 depth 0 으로 들어가면 위의 depth-0 '하위 컬럼 무조건 통과' 규칙이 그 테이블에
            # 재발화해 전 sibling 컬럼이 rel=1.0 으로 flood(예산 붕괴). depth 1 승격이면 부모는
            # 분석되되 그 컬럼들은 앵커 게이팅을 받는다(depth-0 자동통과는 실제 루트 전용으로 보존).
            pr = float(getattr(_cfg, "AGENT_NODE_ANALYSIS_PARENT_TABLE_REL", 0.5))
            if _scope_of(k) != (anchor.get("scope") or ""):
                # crossds-rel: 의도적 교차DB REFERENCES 로 도달한 부모 테이블은 완화(기본 1.0), 우연 교차는 0.25.
                if meta.get("cross_ds"):
                    pr *= max(0.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_XDS_REFERENCES_FACTOR", 1.0)))
                else:
                    pr *= max(0.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_CROSS_SCOPE_FACTOR", 0.25)))
            kept.append((max(_relevance(n, meta, anchor), pr), n, cur_depth > 0))
            continue
        rel = _relevance(n, meta, anchor)
        if rel < min_rel:
            continue                 # 관련도 미달 → 재귀 제외
        kept.append((rel, n, False))
    # 관련도 높은 순 — 예산 우선 소비. 동점(특히 하위 컬럼 1.0)은 ordinal→name 으로 **결정적** 정렬:
    #   예산 절단 시 어느 컬럼이 분석되는지 재현 가능 + 컬럼은 ordinal 순 우선(M5).
    def _tiebreak(node):
        ordv = node.get("ordinal")
        ordv = ordv if isinstance(ordv, int) else 10_000
        # key 를 마지막 성분으로 — 동명(다른 스키마/제품) 노드도 전순서 결정(DB row order 비의존).
        return (ordv, str(node.get("name") or ""), str(node.get("key") or ""))
    kept.sort(key=lambda t: (-t[0], _tiebreak(t[1])))
    return kept


def _enqueue_neighbors(c, cur, run_id: str, scope_key: str, ctx: dict, cur_depth: int,
                       anchor: dict, anchor_key: str = "") -> int:
    """cur_depth 노드의 이웃을 **앵커 관련도로 게이트·우선순위화**해 pending 재큐(dedupe + 예산 캡).

    반환: 실제 삽입 수. anchor(원래 루트 서술자) 기준으로 채점해, 방문 노드가 허브여도 무관 노드로
    fan-out 하지 않고 원래 대상과 연관 높은 이웃만 관련도 순으로 재큐한다.

    fix(medium): 예산 read-modify-write 를 run 행 `FOR UPDATE` 로 원자화한다 — 다중 워커/replica 가 같은
    run 을 동시 처리해도 node_budget 을 초과 enqueue(LLM 비용 초과)하지 않도록 직렬화. LLM 호출은 이
    트랜잭션 밖(호출측)이라 락 보유 시간은 짧다. autocommit 연결에서도 c.transaction() 이 블록 트랜잭션을 연다."""
    sk = (scope_key or "common")[:96]
    inserted = 0
    candidates = _score_candidates(ctx, cur_depth, anchor)
    if not candidates:
        return 0
    # §55: 이웃은 현재 잡의 anchor_key 를 **상속** — 시드에서 뻗은 재귀 전체가 같은 앵커로 게이트된다.
    #   컬럼 probe 는 트랜잭션 진입 전(실패 statement 가 블록 트랜잭션을 오염시키지 않게).
    refine_ok = _refine_cols_ok(cur)
    try:
        with c.transaction():
            cur.execute("SELECT depth_budget, node_budget, enqueued FROM node_analysis_runs "
                        "WHERE run_id=%s FOR UPDATE", (run_id,))
            row = cur.fetchone()
            if not row:
                return 0
            depth_budget, node_budget, enqueued = int(row[0]), int(row[1]), int(row[2])
            remaining = node_budget - enqueued
            if remaining <= 0:
                return 0
            for rel, n, same_depth in candidates:
                # ADR-017: 부모 테이블 승격(same_depth)은 depth 를 늘리지 않는다 — depth_budget
                # 마지막 층의 컬럼도 소속 테이블까지는 분석된다. 그 외는 기존 +1 규칙.
                d = cur_depth if same_depth else cur_depth + 1
                if d > depth_budget:
                    continue
                if remaining <= 0:
                    break
                k = n.get("key")
                # crossds-rel: 이웃 job 은 **이웃 자신의 scope**(_scope_of(k))로 기록 — 크로스-ds 엣지로 도달한
                #   이웃을 run 의 단일 sk 로 넣으면 그 이웃의 재분석이 잘못된 scope 에서 이웃을 찾는다. prefix 없으면 sk 폴백.
                nsk = (_scope_of(k) or sk)[:96]
                if refine_ok:
                    cur.execute(
                        "INSERT INTO node_analysis_jobs "
                        "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status, anchor_key) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s) "
                        "ON CONFLICT (run_id, node_key) DO NOTHING RETURNING id",
                        (run_id, nsk, k, (n.get("label") or "")[:32],
                         (n.get("name") or k)[:512], (n.get("fqn") or ""), d,
                         round(float(rel), 4), (anchor_key or "")))
                else:
                    cur.execute(
                        "INSERT INTO node_analysis_jobs "
                        "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending') "
                        "ON CONFLICT (run_id, node_key) DO NOTHING RETURNING id",
                        (run_id, nsk, k, (n.get("label") or "")[:32],
                         (n.get("name") or k)[:512], (n.get("fqn") or ""), d,
                         round(float(rel), 4)))
                if cur.fetchone():
                    inserted += 1
                    remaining -= 1
            if inserted:
                cur.execute("UPDATE node_analysis_runs SET enqueued = enqueued + %s WHERE run_id=%s",
                            (inserted, run_id))
    except Exception as exc:
        _log.debug("enqueue_neighbors_failed err=%r", exc)
        return 0
    return inserted


# ── §55 refine-not-override + back-refine + suggested_links 헬퍼 ─────────────
def _parse_analysis(text):
    """jobs.analysis JSON → dict(필드 트림) 또는 None. refine payload 용."""
    if not text:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return {k: str(obj.get(k) or "").strip()[:700]
            for k in ("summary", "relationships", "usage", "caveats") if obj.get(k)}


#: 실질 내용이 아닌 상투 무응답 — 채워져 있어도 "충족"으로 세지 않는다.
#  ⚠ 정확 일치만 보면 안 된다: 기존 1만여 건의 분석문에는 "연결 정보 없음." · "연결 정보가 없습니다"
#  같은 변형이 섞여 있어, 정확 일치 판정은 그것들을 "충족"으로 세고 thin 판정을 통과시킨다
#  (= 보충돼야 할 분석이 보충되지 않는다). 어미·구두점 변형을 함께 흡수한다.
_EMPTY_RE = re.compile(
    r"^(?:n/?a"
    r"|연결\s*정보(?:가)?\s*(?:없음|없습니다|없다|없어요)"
    r"|(?:관련|참조)?\s*정보(?:가)?\s*(?:없음|없습니다|없다)"
    r"|해당\s*(?:사항)?(?:이)?\s*없(?:음|습니다|다)"
    r"|없(?:음|습니다|다)"
    r"|[-–—.])[\s.!]*$",
    re.IGNORECASE)

#: 충족으로 인정할 최소 항목 수(summary·relationships·usage·role 중).
_THIN_MIN_FILLED = 2


def _is_filled(value) -> bool:
    """분석 항목이 실질 내용인지 — 공란·상투 무응답은 미충족."""
    s = str(value or "").strip()
    if len(s) < 4:
        return False
    return not _EMPTY_RE.match(s)


def _analysis_is_thin(text, thin_chars: int, label: str = "") -> bool:
    """빈약(thin) 분석 판정 — **항목 충족도** 기준(feature-0031 재정의).

    종전에는 summary 길이(기본 120자) 단독 판정이었는데, 프롬프트 계약이 "한국어 1~2문장"
    (≈50~100자)이라 **정상 분석 대부분이 thin 으로 잡혔다** — `REFINE_MAX` 캡이 폭주를 막고
    있었을 뿐, 캡을 올리면 대량 재분석이 터지는 구조였다. 이제 "무엇이 채워졌는가"로 본다:
    summary·relationships·usage(Table 노드는 role 도) 중 실질 항목이 `_THIN_MIN_FILLED` 개
    미만이면 thin. summary 하한(`thin_chars`)은 한 문장도 안 되는 응답을 거르는 역할로 남는다.

    파싱 불가 텍스트는 판단 불가 → thin 아님(보수 — 무한 재분석 방지). 빈 분석문은 thin."""
    if not text:
        return True
    try:
        obj = json.loads(text)
    except Exception:
        return False
    if not isinstance(obj, dict):
        return False
    summary = str(obj.get("summary") or "").strip()
    # §56 RC3: LLM 계약의 무관계 문구("연결 정보 없음")는 공란과 동치 — 관계 substrate(루틴/크로스-DB)가
    # 뒤늦게 채워지는 환경(fhgame1 류)에서 이런 노드가 back-refine 대상으로 잡혀 보충되게 한다.
    filled = sum(1 for k in ("summary", "relationships", "usage") if _is_filled(obj.get(k)))
    if (label or "") == "Table" and _role_valid(obj.get("role")):
        filled += 1
    if len(summary) < max(1, thin_chars):
        return True
    return filled < _THIN_MIN_FILLED


def _latest_done_analysis(cur, scope_key, node_key, exclude_id=None):
    """노드의 최신 done 분석문(타 run 포함) — refine-not-override 의 previous_analysis 원천."""
    try:
        cur.execute("SELECT analysis FROM node_analysis_jobs "
                    "WHERE scope_key=%s AND node_key=%s AND status='done' AND id <> COALESCE(%s, -1) "
                    "ORDER BY id DESC LIMIT 1", ((scope_key or "common")[:96], node_key, exclude_id))
        row = cur.fetchone()
        return _parse_analysis(row[0]) if row else None
    except Exception as exc:
        _log.debug("latest_done_analysis_failed err=%r", exc)
        return None


def _related_findings(cur, run_id, ctx, exclude_key=None, limit=6):
    """같은 run 에서 분석 완료된 인접 노드의 발견 요약 — refine 잡 payload 의 보충 맥락."""
    keys = [k for k in (ctx.get("neighbor_meta") or {}).keys() if k and k != exclude_key][:60]
    if not keys:
        return []
    out = []
    try:
        cur.execute("SELECT node_name, node_label, analysis FROM node_analysis_jobs "
                    "WHERE run_id=%s AND status='done' AND node_key = ANY(%s) "
                    "ORDER BY relevance DESC, id DESC LIMIT %s", (run_id, keys, max(1, int(limit))))
        for name, label, atext in cur.fetchall():
            obj = _parse_analysis(atext)
            if not obj:
                continue
            item = {"name": str(name or ""), "label": str(label or ""),
                    "summary": (obj.get("summary") or "")[:300]}
            if obj.get("relationships"):
                item["relationships"] = obj["relationships"][:200]
            out.append(item)
    except Exception as exc:
        _log.debug("related_findings_failed err=%r", exc)
    return out


def _backrefine_neighbors(c, cur, run_id: str, cur_jid, ctx: dict) -> int:
    """방금 분석된 노드의 인접 중, 같은 run 에서 먼저 분석됐지만 빈약(thin)한 done 잡을 재-pending
    (pass_no+1) — 후속 재귀가 만든 새 맥락(related_findings)으로 보충(refine)된다.

    UNIQUE(run_id,node_key) 불변 설계: 새 행이 아니라 기존 행의 상태 전이라 mixed-version 안전.
    counters: enqueued += n (재작업 단위 — done 은 완료 시 재증가 → done ≤ enqueued 단조 유지).
    run 당 pass_no>0 잡 수 ≤ AGENT_NODE_ANALYSIS_REFINE_MAX. 반환: 재-pending 수."""
    refine_max = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_REFINE_MAX", 30) or 0)
    if refine_max <= 0:
        return 0
    keys = [k for k in (ctx.get("neighbor_meta") or {}).keys() if k][:60]
    if not keys:
        return 0
    thin_chars = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_THIN_CHARS", 120) or 120)
    updated = 0
    with c.transaction():
        cur.execute("SELECT COUNT(*) FROM node_analysis_jobs WHERE run_id=%s AND pass_no > 0", (run_id,))
        room = refine_max - int((cur.fetchone() or [0])[0])
        if room <= 0:
            return 0
        cur.execute("SELECT id, analysis, node_label FROM node_analysis_jobs "
                    "WHERE run_id=%s AND status='done' AND pass_no=0 AND id <> %s AND node_key = ANY(%s) "
                    "ORDER BY id LIMIT 20", (run_id, cur_jid, keys))
        rows = cur.fetchall()
        for rid, atext, nlabel in rows:
            if updated >= room:
                break
            # label 은 thin 판정의 항목 충족도에 쓰인다 — Table 노드는 role 도 충족 항목이다.
            if not _analysis_is_thin(atext, thin_chars, str(nlabel or "")):
                continue
            cur.execute("UPDATE node_analysis_jobs SET status='pending', pass_no = pass_no + 1, error=NULL "
                        "WHERE id=%s AND status='done' AND pass_no=0", (rid,))
            if cur.rowcount:
                updated += 1
        if updated:
            cur.execute("UPDATE node_analysis_runs SET enqueued = enqueued + %s WHERE run_id=%s",
                        (updated, run_id))
    return updated


_IDENT_RE = re.compile(r"^[A-Za-z0-9_\-\. ]{1,128}$")


def _ingest_suggested_links(c, scope_key, root, ctx, obj) -> int:
    """LLM 분석의 suggested_links(컨텍스트 내 조인 후보)를 table_relationships 에 candidate 적재.

    가드(환각 차단): (a) 양끝 테이블이 payload 컨텍스트의 **그래프 노드**와 매칭돼야 하고(임의 문자열
    금지 — 노드 fqn/scope 를 신뢰), (b) 한쪽 끝은 반드시 현재 분석 노드(root)의 테이블이어야 하며,
    (c) root 쪽 컬럼은 ctx.columns 실재 확인, 반대쪽 컬럼은 식별자 형식 검사(실데이터 검증은 기존
    프로브 파이프라인 몫 — source='llm_insight' 는 fetch_probe_candidates 대상). 잡당 SUGGEST_LINKS_MAX."""
    cap = int(getattr(_cfg, "AGENT_NODE_ANALYSIS_SUGGEST_LINKS_MAX", 4) or 0)
    if cap <= 0 or not isinstance(obj, dict):
        return 0
    links = obj.get("suggested_links")
    if not isinstance(links, list) or not links:
        return 0
    root_label = (root.get("label") or "") if isinstance(root, dict) else ""
    # 링크는 Table/Routine 분석에서만 의미 — Column/용어 잡은 skip(부모 테이블 잡이 담당).
    if root_label not in ("Table",):
        return 0

    def _tbl_id(node):
        key = str(node.get("key") or "")
        scope = key.split(":", 1)[0] if ":" in key else (scope_key or "")
        fqn = str(node.get("fqn") or (key.split(":", 1)[1] if ":" in key else ""))
        schema = fqn.rsplit(".", 1)[0] if "." in fqn else ""
        table = fqn.rsplit(".", 1)[-1]
        return {"scope": scope, "schema": schema, "table": table}

    allowed = {}

    def _add_tbl(n):
        if isinstance(n, dict) and (n.get("label") or "") == "Table":
            info = _tbl_id(n)
            for alias in (str(n.get("name") or ""), str(n.get("fqn") or ""), info["table"]):
                a = alias.strip().lower()
                if not a:
                    continue
                cur_info = allowed.get(a)
                if a not in allowed:
                    allowed[a] = info
                elif cur_info is not None and (cur_info["scope"], cur_info["schema"], cur_info["table"]) \
                        != (info["scope"], info["schema"], info["table"]):
                    # §55 패널 fix: 동명 alias 가 서로 다른 테이블(타 DB/scope)을 가리키면 **모호 — 비활성**
                    # (first-wins 오귀속으로 잘못된 쌍이 candidate 적재되는 것 방지. fqn 정확 표기는 계속 유효).
                    allowed[a] = None

    _add_tbl(root)
    for n in (ctx.get("neighbors") or []):
        _add_tbl(n)
    root_info = _tbl_id(root)
    root_cols = {str(col.get("name") or "").strip().lower()
                 for col in (ctx.get("columns") or []) if col.get("name")}
    ingested = 0
    try:
        from modules import relationships as _rel
    except Exception:
        return 0
    for item in links[: cap * 3]:
        if ingested >= cap:
            break
        if not isinstance(item, dict):
            continue
        ft = str(item.get("from_table") or "").strip().lower()
        tt = str(item.get("to_table") or "").strip().lower()
        fc = str(item.get("from_column") or "").strip()
        tc = str(item.get("to_column") or "").strip()
        if not (ft and tt and fc and tc) or ft == tt:
            continue
        if not (_IDENT_RE.match(fc) and _IDENT_RE.match(tc)):
            continue
        src, tgt = allowed.get(ft), allowed.get(tt)
        if not src or not tgt:
            continue   # 컨텍스트 밖 테이블(환각) 배제
        # root 연루 강제 + root 쪽 컬럼 실재 확인.
        if src["table"].lower() == root_info["table"].lower() and src["schema"] == root_info["schema"]:
            if root_cols and fc.lower() not in root_cols:
                continue
        elif tgt["table"].lower() == root_info["table"].lower() and tgt["schema"] == root_info["schema"]:
            if root_cols and tc.lower() not in root_cols:
                continue
        else:
            continue
        try:
            ok = _rel.upsert_relationship(
                c, src["scope"] or (scope_key or "common"),
                src_schema=src["schema"], src_table=src["table"], src_column=fc,
                tgt_schema=tgt["schema"], tgt_table=tgt["table"], tgt_column=tc,
                source="llm_insight", datasource_key=src["scope"] or "",
                source_datasource_key=src["scope"] or "", target_datasource_key=tgt["scope"] or "")
            if ok:
                ingested += 1
        except Exception as exc:
            _log.debug("suggested_link_upsert_failed err=%r", exc)
    if ingested:
        _log.info("node_analysis suggested_links: %d건 candidate 적재 (root=%s)", ingested, root.get("key"))
    return ingested


# ── 조회 API (웹 폴링/상세 패널) ─────────────────────────────────────────────
def get_run_status(run_id: str, conn=None) -> dict | None:
    if not run_id:
        return None
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        cur.execute("SELECT run_id, scope_key, root_key, root_name, depth_budget, node_budget, "
                    "status, enqueued, done, failed, root_label "
                    "FROM node_analysis_runs WHERE run_id=%s", (run_id,))
        r = cur.fetchone()
        if not r:
            cur.close()
            return None
        # 그래프 마커용 완료/진행 키는 **전량(cap 없이)** 조회 — node_budget 최대 1000 이라도 마커 누락 방지.
        #   키만 가져와 페이로드 작음(review fix: LIMIT 400 이 done_keys/running_keys 를 절단해 tail 노드 미표시).
        #   node-role-viz: done 키의 role 도 함께 — 폴 중 완료되는 노드에 역할 표식을 라이브 적용.
        done_keys, running_keys, roles = [], [], {}
        try:
            cur.execute("SELECT node_key, status, role FROM node_analysis_jobs "
                        "WHERE run_id=%s AND status IN ('done','running')", (run_id,))
            rows = cur.fetchall()
        except Exception as role_exc:
            # 마이그레이션 창(role 컬럼 부재) — 폴링 404 회귀 방지: role 없이 legacy 조회(B1).
            _warn_role_column_once("get_run_status", role_exc)
            cur.execute("SELECT node_key, status, NULL FROM node_analysis_jobs "
                        "WHERE run_id=%s AND status IN ('done','running')", (run_id,))
            rows = cur.fetchall()
        for k, s, role in rows:
            if s == "done":
                done_keys.append(k)
                if role:
                    roles[k] = role
            else:
                running_keys.append(k)
        # 항목별 상세 리스트(진행 패널 표시분) — 분석중→완료→깊이·관련도 순, UI 표시분만 cap(패널은 running+최근 done 만 노출).
        #   relevance 도 함께 노출 — UI 가 "원래 대상과의 관련도" 로 우선순위를 표시할 수 있게(node-analysis-anchor).
        _JOBS_SQL = ("SELECT node_key, node_label, node_name, node_fqn, status, depth, relevance{role_col} "
                     "FROM node_analysis_jobs WHERE run_id=%s "
                     "ORDER BY (status='running') DESC, (status='done') DESC, depth ASC, relevance DESC, node_name ASC "
                     "LIMIT 80")
        try:
            cur.execute(_JOBS_SQL.format(role_col=", role"), (run_id,))
            job_rows = cur.fetchall()
        except Exception as role_exc:
            _warn_role_column_once("get_run_status.jobs", role_exc)
            cur.execute(_JOBS_SQL.format(role_col=", NULL"), (run_id,))
            job_rows = cur.fetchall()
        jobs = [{"node_key": row[0], "node_label": row[1], "node_name": row[2],
                 "node_fqn": row[3], "status": row[4], "depth": row[5],
                 "relevance": round(float(row[6]), 4) if row[6] is not None else None,
                 "role": row[7]}
                for row in job_rows]
        # analysis-retry-resilience: 진행 패널이 "멈춘 것"과 "재시도를 기다리는 것"을 구분해 보여줄 수
        #   있도록 재시도 대기 수·가장 이른 재시도 시각·회수 가능한 실패 수를 함께 싣는다.
        #   0049 미적용 창에서는 조회가 실패하므로 0/None(프론트가 해당 표기를 생략) — 폴링 404 회귀 없음.
        retry_waiting, next_attempt_at, retryable_failed = 0, None, 0
        try:
            cur.execute(
                "SELECT count(*) FILTER (WHERE status='pending' AND next_attempt_at > now()), "
                "       min(next_attempt_at) FILTER (WHERE status='pending' AND next_attempt_at > now()), "
                "       count(*) FILTER (WHERE status='failed' AND " + _RETRYABLE_FAILED_SQL + ") "
                "  FROM node_analysis_jobs WHERE run_id=%s",
                _RETRYABLE_FAILED_ARGS + (run_id,))
            rr = cur.fetchone() or (0, None, 0)
            retry_waiting = int(rr[0] or 0)
            next_attempt_at = rr[1].isoformat() if rr[1] else None
            retryable_failed = int(rr[2] or 0)
        except Exception as retry_exc:
            _log.debug("get_run_status retry 집계 생략(0049 미적용?) err=%r", retry_exc)
        cur.close()
        return {"run_id": r[0], "scope_key": r[1], "root_key": r[2], "root_name": r[3],
                "depth_budget": r[4], "node_budget": r[5], "status": r[6],
                "enqueued": r[7], "done": r[8], "failed": r[9], "root_label": r[10] or "",
                "done_keys": done_keys, "running_keys": running_keys, "roles": roles, "jobs": jobs,
                "retry_waiting": retry_waiting, "next_attempt_at": next_attempt_at,
                "retryable_failed": retryable_failed}
    except Exception as exc:
        _log.debug("get_run_status_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def get_node_analysis(scope_key: str, node_key: str, conn=None) -> dict | None:
    """노드의 최신 분석 상태/결과 (상세 패널). done 이 있으면 그 analysis, 없으면 최신 상태만."""
    if not node_key:
        return None
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        # node-role-viz(적대 패널 Q1): "최신 done" 선택은 updated_at 이 아니라 **id(삽입 순 = 최신 run)**.
        #   backfill_roles 의 UPDATE 가 updated_at 트리거를 발화시켜 과거 run 행이 재분석 행보다 "최신"으로
        #   역전되던 결함 차단(get_scope_analysis_status 의 집계 정렬도 동일 기준).
        _SEL_SQL = ("SELECT status, analysis, model, updated_at, run_id{role_col} FROM node_analysis_jobs "
                    "WHERE scope_key=%s AND node_key=%s "
                    "ORDER BY (status='done') DESC, id DESC LIMIT 1")
        try:
            cur.execute(_SEL_SQL.format(role_col=", role"), (scope_key or "common", node_key))
            r = cur.fetchone()
        except Exception as role_exc:
            # 마이그레이션 창(role 컬럼 부재) — 상세 패널 503 회귀 방지: role 없이 legacy 조회(B1).
            _warn_role_column_once("get_node_analysis", role_exc)
            cur.execute(_SEL_SQL.format(role_col=", NULL"), (scope_key or "common", node_key))
            r = cur.fetchone()
        cur.close()
        if not r:
            return {"status": "none", "analysis": None}
        analysis = None
        if r[1]:
            try:
                analysis = json.loads(r[1])
            except Exception:
                analysis = {"summary": str(r[1])}
        return {"status": r[0], "analysis": analysis, "model": r[2],
                "updated_at": r[3].isoformat() if r[3] else None, "run_id": r[4],
                "role": r[5]}
    except Exception as exc:
        _log.debug("get_node_analysis_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def get_scope_analysis_status(scope_key: str, node_keys=None, conn=None) -> dict | None:
    """스코프 내 노드들의 최신 분석 상태를 **일괄** 집계 — 그래프 초기 렌더/검색/확장 시
    마커(보라 '분석됨'·주황 '분석중')를 노드 클릭 없이 즉시 적용하기 위함.

    반환 {done_keys:[...], running_keys:[...], roles:{node_key:role}}:
      - done_keys    = 완료(done) 잡이 하나라도 있는 node_key
      - running_keys = done 은 없고 pending/running 잡이 있는 node_key
      - roles        = done node_key 의 최신 역할 분류(node-role-viz — Table 만, NULL 제외)
    node_keys 지정 시 그 부분집합만 조회(대형 그래프 payload 축소). PG 미가용/예외 → None(코어 비차단)."""
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        params = [scope_key or "common"]
        where = "scope_key=%s"
        keys = [k for k in (node_keys or []) if k]
        if keys:
            where += " AND node_key = ANY(%s)"
            params.append(keys)
        # role = 노드의 최신 done 잡(id DESC — Q1: backfill 의 updated_at bump 로 과거 run 역전 차단).
        _AGG_SQL = ("SELECT node_key, "
                    "bool_or(status='done') AS has_done, "
                    "bool_or(status IN ('pending','running')) AS has_active{role_col} "
                    "FROM node_analysis_jobs WHERE " + where + " GROUP BY node_key")
        _ROLE_AGG = (", (array_agg(role ORDER BY id DESC) "
                     " FILTER (WHERE status='done' AND role IS NOT NULL))[1] AS role")
        try:
            cur.execute(_AGG_SQL.format(role_col=_ROLE_AGG), tuple(params))
            rows = cur.fetchall()
        except Exception as role_exc:
            # 마이그레이션 창(role 컬럼 부재) — 마커 회귀 방지: role 없이 legacy 집계(B1).
            _warn_role_column_once("get_scope_analysis_status", role_exc)
            cur.execute(_AGG_SQL.format(role_col=", NULL AS role"), tuple(params))
            rows = cur.fetchall()
        done_keys, running_keys, roles = [], [], {}
        for k, has_done, has_active, role in rows:
            if has_done:
                done_keys.append(k)
                if role:
                    roles[k] = role
            elif has_active:
                running_keys.append(k)
        cur.close()
        return {"done_keys": done_keys, "running_keys": running_keys, "roles": roles}
    except Exception as exc:
        _log.debug("get_scope_analysis_status_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
