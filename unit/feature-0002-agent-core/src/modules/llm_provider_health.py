"""LLM provider 외부요인 제한(특히 자격증명/키 만료) 분류 + health 상태 영속.

TASK-20260619T014034 — Bedrock 등 외부 provider 장애로 LLM 응답이 막힐 때 서비스
사용자가 **명시적으로** 확인할 수 있도록:
  (1) provider 예외를 사용자 친화 restriction 으로 분류(classify_llm_provider_error),
  (2) provider별 health 상태를 PG(agent_runtime.llm_provider_health)에 영속한다.
ask-worker(agent_core, passive 신호)와 web(app.py probe/read)이 공유한다.

**자격증명 비영속**: 저장 컬럼은 provider/state/kind/message/error_tag/source/since/
updated_at 만 — api key·AWS secret·토큰은 절대 저장하지 않는다(datasource_health 동형
원칙, TASK-0255 R2). error_tag 도 예외 *클래스명*(ExpiredToken 등)만 추출, 본문/비밀 미포함.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

_log = logging.getLogger("llm_provider_health")

# ── state / kind 상수 ──────────────────────────────────────────────────
STATE_OK = "ok"
STATE_RESTRICTED = "restricted"
STATE_UNKNOWN = "unknown"

KIND_CREDENTIAL_EXPIRED = "credential_expired"
KIND_AUTH_INVALID = "auth_invalid"
KIND_THROTTLED = "throttled"
KIND_UNAVAILABLE = "unavailable"
KIND_NOT_CONFIGURED = "not_configured"
# TASK-20260714-attach-grounding: 요청-레벨 400 오류(provider 장애 아님).
#   bad_model    — 라우팅/설정으로 잘못된 모델명이 API 로 전달(예: model=auto/core/edge 미해소).
#   context_length — 프롬프트(첨부+히스토리)가 모델 컨텍스트 초과. raw 덤프 대신 친절 메시지 +
#   글로벌 provider health 미오염(persist_health=False).
KIND_BAD_MODEL = "bad_model"
KIND_CONTEXT_LENGTH = "context_length"
KIND_UNKNOWN = "unknown"

# 요청-레벨 오류 kind — provider 장애가 아니므로 글로벌 health 상태에 영속하지 않는다.
_REQUEST_LEVEL_KINDS = frozenset({KIND_BAD_MODEL, KIND_CONTEXT_LENGTH})

_PROVIDER_LABEL = {"bedrock": "AWS Bedrock", "local": "로컬 LLM", "openai": "LLM 제공자"}


def _provider_label(provider: str | None) -> str:
    return _PROVIDER_LABEL.get(str(provider or "").lower(), "LLM 제공자")


def current_provider() -> str:
    """런타임 활성 provider 판정(config env 기반). bedrock | local | openai."""
    try:
        from shared import config as cfg
        if getattr(cfg, "BEDROCK_GATEWAY_URL", None) and getattr(cfg, "BEDROCK_GATEWAY_API_KEY", None):
            return "bedrock"
        if getattr(cfg, "LOCAL_LLM_API_BASE", None) and getattr(cfg, "LOCAL_LLM_API_KEY", None):
            return "local"
    except Exception:
        pass
    return "openai"


# ── 예외 → (status, text) 추출 ─────────────────────────────────────────
def _extract_status_and_text(exc: Exception) -> "tuple[int | None, str]":
    status: "int | None" = None
    for attr in ("status_code", "status"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            status = v
            break
    parts = [type(exc).__name__, str(exc) or ""]
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            parts.append(str(getattr(resp, "text", "") or "")[:600])
        except Exception:
            pass
        if status is None:
            sc = getattr(resp, "status_code", None)
            if isinstance(sc, int):
                status = sc
    body = getattr(exc, "body", None)
    if body is not None:
        try:
            parts.append(str(body)[:600])
        except Exception:
            pass
    return status, " ".join(p for p in parts if p)


# 패턴 → kind (대소문자 무시). credential_expired 를 가장 먼저(가장 구체적) 판정.
_CRED_EXPIRED_PAT = re.compile(
    r"expiredtoken|the security token included in the request is expired"
    r"|security token.*expired|expired.*credential|token.*has expired"
    r"|credential.*expired",
    re.I,
)
_AUTH_INVALID_PAT = re.compile(
    r"unrecognizedclient|invalidsignatureexception|invalidclienttokenid"
    r"|signaturedoesnotmatch|the security token included in the request is invalid"
    r"|accessdenied|not authorized|unauthorized|invalid api key|incorrect api key"
    r"|authenticationerror|permissiondenied|forbidden|missing credentials"
    r"|no credentials|nocredentials|unable to locate credentials",
    re.I,
)
_THROTTLE_PAT = re.compile(
    r"throttl|too many requests|rate ?limit|slow down", re.I,
)
_UNAVAIL_PAT = re.compile(
    r"serviceunavailable|service is unavailable|modelnotready|model.*not.*available"
    r"|internalserver|bad gateway|gateway timeout|connection.*(refused|reset)"
    r"|temporarily unavailable"
    # conv-audit FR-llm-transient-failure-kills-run (2026-08-12): OpenAI SDK 의 **전송층** 예외
    # 두 종은 위 어휘 중 무엇에도 걸리지 않아 분류가 None 으로 떨어졌고, 그 결과 사용자 화면에
    # 원문 영어(`오류: LLM 호출 오류: Connection error.` / `... Request timed out.`)가 그대로
    # 노출됐다 — 무엇이 일어났는지도, 다시 시도하면 되는지도 알려주지 않는 표면이었다(라이브
    # 90일 18 대화). `_extract_status_and_text` 가 예외 **클래스명**을 텍스트에 넣어주므로
    # 클래스명과 기본 메시지 양쪽을 잡는다.
    #   · APIConnectionError("Connection error.") — 요청이 도달조차 못 함(게이트웨이 순단 등)
    #   · APITimeoutError("Request timed out.")   — per-attempt 상한 초과
    # **`_TAG_PAT` 에는 넣지 않는다**: 그러면 confirmed=True 가 되어 단발 순단이 전 사용자에게
    # 보이는 sticky 글로벌 배너를 켠다. 여기 매칭은 confirmed=False 로 남아 per-run 메시지로만
    # 노출되고 글로벌 health 는 건드리지 않는다(record_provider_restricted 의 confirmed 게이트).
    r"|apiconnectionerror|apitimeouterror|connection error|request timed out"
    r"|server disconnected|connection aborted|remote end closed",
    re.I,
)
# TASK-20260714-attach-grounding: 요청-레벨 400 패턴.
#   bad_model — litellm "Invalid model name passed in model=..." / OpenAI "model_not_found" 등.
_BAD_MODEL_PAT = re.compile(
    r"invalid model name|model_not_found|the model .* does not exist"
    r"|unknown model|model=\w+\.?\s*call `?/v1/models`?|no such model"
    r"|invalid.*model.*passed",
    re.I,
)
#   context_length — 프롬프트가 컨텍스트 초과(Anthropic/Bedrock/OpenAI 표현 통합).
_CONTEXT_LEN_PAT = re.compile(
    r"context length|context window|maximum context|context_length_exceeded"
    r"|input is too long|input length and max_tokens|too many (?:input )?tokens"
    r"|prompt is too long|reduce the length of the messages"
    r"|exceeds?.*(?:context|token limit)|max_tokens.*exceed.*context",
    re.I,
)
_TAG_PAT = re.compile(
    r"(ExpiredToken(?:Exception)?|UnrecognizedClientException|InvalidSignatureException"
    r"|AccessDenied(?:Exception)?|ThrottlingException|ServiceUnavailable(?:Exception)?"
    r"|SignatureDoesNotMatch|InvalidClientTokenId|AuthenticationError|RateLimitError"
    r"|PermissionDeniedError)",
    re.I,
)


def _short_tag(kind: str, status: "int | None", text: str) -> str:
    """자격증명 비포함 short tag — 예외 클래스명/코드 키워드만(비밀 미포함)."""
    m = _TAG_PAT.search(text)
    code = m.group(1) if m else kind
    return (f"{code}:{status}" if status else str(code))[:120]


def _build_restriction(
    kind: str, provider: str, *, status: "int | None" = None, text: str = "",
    confirmed: "bool | None" = None,
) -> "dict[str, Any]":
    # M3(리뷰): confirmed=특정 provider 오류 *클래스명* 매칭(고신뢰). status code/generic
    # 키워드만 매칭(예: bare 403, connection reset)이면 False=일시·모호 → 글로벌 banner 미영속.
    if confirmed is None:
        confirmed = bool(_TAG_PAT.search(text))
    plabel = _provider_label(provider)
    if kind == KIND_CREDENTIAL_EXPIRED:
        msg = f"{plabel} 자격증명이 만료되어 현재 AI 응답을 생성할 수 없습니다. 관리자가 키를 갱신하면 자동으로 복구됩니다."
        retryable = False
    elif kind == KIND_AUTH_INVALID:
        msg = f"{plabel} 인증에 실패해 현재 AI 응답을 생성할 수 없습니다. 관리자에게 자격증명 확인을 요청하세요."
        retryable = False
    elif kind == KIND_THROTTLED:
        # 요청량 한도(throttle)는 "서비스 자체" 한도임을 명시 — 계정 당 사용 한도
        # (app.py _check_account_token_quota)와 주체를 구분한다. provider 이름
        # (AWS Bedrock 등)은 노출하지 않는다(서비스 한도임이 핵심, 내부 backend 비노출).
        msg = "서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."
        retryable = True
    elif kind == KIND_UNAVAILABLE:
        msg = f"{plabel} 서비스가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해 주세요."
        retryable = True
    elif kind == KIND_NOT_CONFIGURED:
        msg = "AI 제공자 자격증명이 설정되지 않아 응답을 생성할 수 없습니다. 관리자에게 문의하세요."
        retryable = False
    elif kind == KIND_BAD_MODEL:
        # 요청-레벨: 라우팅/설정 오류로 잘못된 모델명이 전달됨. 사용자가 재시도해도 무의미 → 관리자 안내.
        msg = "요청한 AI 모델을 현재 사용할 수 없습니다(모델 설정 오류). 관리자에게 모델 라우팅 설정 확인을 요청해 주세요."
        retryable = False
    elif kind == KIND_CONTEXT_LENGTH:
        # 요청-레벨: 첨부/대화가 컨텍스트 초과. 분량을 줄이면 사용자 스스로 복구 가능 → 행동 가능한 안내.
        msg = "첨부 파일과 대화 내용이 한 번에 처리할 수 있는 분량을 초과했습니다. 첨부 파일을 나눠서 올리거나 일부만 남기고 다시 시도해 주세요."
        retryable = False
    else:
        msg = f"{plabel} 사용에 외부 요인으로 인한 제한이 발생했습니다. 잠시 후 다시 시도해 주세요."
        retryable = True
    return {
        "kind": kind,
        "provider": provider,
        "message": msg,
        "retryable": retryable,
        "error_tag": _short_tag(kind, status, text),
        "confirmed": bool(confirmed),
        # 요청-레벨 오류(bad_model/context_length)는 provider 장애가 아님 → 글로벌 health 미영속.
        "persist_health": kind not in _REQUEST_LEVEL_KINDS,
    }


def classify_llm_provider_error(exc: "Exception | None", provider: "str | None" = None) -> "dict[str, Any] | None":
    """provider 예외를 사용자 친화 restriction dict 로 분류.

    인식 가능한 외부요인 제한(자격증명 만료/인증실패/쓰로틀/서비스불가)이면
    {kind, provider, message, retryable, error_tag} 반환. 인식 불가(일반 코드 오류,
    네트워크 타임아웃 등)면 None — caller 는 기존 일반 에러 폴백.
    """
    if exc is None:
        return None
    provider = provider or current_provider()
    status, text = _extract_status_and_text(exc)
    low = text.lower()
    # 자격증명 만료가 가장 구체적 → 최우선. 이어서 요청-레벨(bad_model/context_length)을 auth/throttle/
    # unavail 앞에서 판정하되, **request-level status(400/404/413)일 때만** 매칭한다.
    # REV-20260714T210000(security Concern 3): text-only 매칭이 status 를 무시하면, 실제 429 throttle
    # ("Too many tokens submitted, slow down") 이나 403 auth("unknown model tier") 가 context_length/
    # bad_model 로 오분류돼 persist_health=False 로 **실제 provider health 배너를 억제**한다. status 로
    # 확정 outage/auth/throttle 를 요청-레벨 버킷이 훔치지 못하게 게이트한다.
    # 400/413=요청 형식/크기 오류, 404=모델 미존재(OpenAI model_not_found) — 모두 요청-레벨(client)이고
    # 위험한 401/403/429/5xx 와 겹치지 않는다.
    # REV-20260714T221500(적대 패널 MINOR-1): status 미상(None) fallback 도 제거한다 — 래핑/네트워크
    # 예외로 status 를 잃은 throttle/auth 가 토큰/모델 어휘("too many tokens"/"unknown model")를 담으면
    # 요청-레벨로 훔쳐가 배너를 억제할 수 있었다. 실 SDK 오류는 status_code 를 항상 실어(429/401/403)
    # 게이트가 정확하므로, status 없는 요청-레벨 매칭을 포기하는 편(→ 보수적으로 auth/throttle/generic 폴백)이
    # provider-health 신호 억제 위험보다 안전. context_length/bad_model 은 status 확정(400/404/413) 시에만.
    _req_ok = status in (400, 404, 413)
    if _CRED_EXPIRED_PAT.search(low):
        kind = KIND_CREDENTIAL_EXPIRED
    elif _req_ok and _BAD_MODEL_PAT.search(low):
        kind = KIND_BAD_MODEL
    elif _req_ok and _CONTEXT_LEN_PAT.search(low):
        kind = KIND_CONTEXT_LENGTH
    elif _AUTH_INVALID_PAT.search(low) or status in (401, 403):
        kind = KIND_AUTH_INVALID
    elif _THROTTLE_PAT.search(low) or status == 429:
        kind = KIND_THROTTLED
    elif _UNAVAIL_PAT.search(low) or (status is not None and 500 <= status < 600):
        kind = KIND_UNAVAILABLE
    else:
        return None
    return _build_restriction(kind, provider, status=status, text=text)


def not_configured_restriction(provider: "str | None" = None) -> "dict[str, Any]":
    # 자격증명 미설정은 확정 상태(transient 아님) → confirmed=True.
    return _build_restriction(KIND_NOT_CONFIGURED, provider or current_provider(), confirmed=True)


# ── PG 영속(agent_runtime.llm_provider_health) ────────────────────────
_UPSERT_SQL = """
INSERT INTO agent_runtime.llm_provider_health
    (provider, state, kind, message, error_tag, source, since, updated_at)
VALUES (%(provider)s, %(state)s, %(kind)s, %(message)s, %(error_tag)s, %(source)s, now(), now())
ON CONFLICT (provider) DO UPDATE SET
    state      = EXCLUDED.state,
    kind       = EXCLUDED.kind,
    message    = EXCLUDED.message,
    error_tag  = EXCLUDED.error_tag,
    source     = EXCLUDED.source,
    since      = CASE WHEN agent_runtime.llm_provider_health.state <> EXCLUDED.state
                      THEN now() ELSE agent_runtime.llm_provider_health.since END,
    updated_at = now();
"""


def _pg():
    from shared.db import _pg_available, _pg_connect
    try:
        if not _pg_available():
            return None
    except Exception:
        return None
    return _pg_connect(autocommit=True)


def record_provider_state(
    state: str,
    *,
    provider: "str | None" = None,
    kind: "str | None" = None,
    message: "str | None" = None,
    error_tag: "str | None" = None,
    source: str = "ask",
) -> None:
    """provider health upsert. soft telemetry — PG 미가용/실패는 무시(요청에 무영향)."""
    provider = provider or current_provider()
    conn = None
    try:
        conn = _pg()
        if conn is None:
            return
        cur = conn.cursor()
        try:
            cur.execute(_UPSERT_SQL, {
                "provider": str(provider)[:32],
                "state": str(state)[:16],
                "kind": (str(kind)[:32] if kind else None),
                "message": (str(message)[:512] if message else None),
                "error_tag": (str(error_tag)[:120] if error_tag else None),
                "source": str(source)[:16],
            })
        finally:
            cur.close()
    except Exception as exc:
        _log.warning("llm_provider_health_persist_failed err=%s — soft telemetry", type(exc).__name__)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def record_provider_restricted(restriction: "dict[str, Any]", *, source: str = "ask") -> None:
    if not restriction:
        return
    # M3(리뷰): 확정 신호만 sticky 글로벌 banner 로 영속. 모호/일시(단순 status·connection
    # reset·bare forbidden)는 per-run 에러 메시지로만 노출하고 글로벌 health 미변경(오탐 banner
    # 방지 — datasource_health tri-state 선례). 확정=특정 provider 오류 클래스명 매칭 or not_configured.
    if not restriction.get("confirmed"):
        return
    record_provider_state(
        STATE_RESTRICTED,
        provider=restriction.get("provider"),
        kind=restriction.get("kind"),
        message=restriction.get("message"),
        error_tag=restriction.get("error_tag"),
        source=source,
    )


def record_provider_ok(*, provider: "str | None" = None, source: str = "ask") -> None:
    """제한 해소(성공) 기록. caller 가 run 당 1회만 호출(폭주 방지)."""
    record_provider_state(STATE_OK, provider=provider, kind=None, message=None, error_tag=None, source=source)


def read_provider_health(provider: "str | None" = None) -> "dict[str, Any]":
    """web 표면용 health 읽기. 기록 없음 → state=ok(문제 신호 없음). 실패 → state=unknown."""
    provider = provider or current_provider()
    conn = None
    try:
        conn = _pg()
        if conn is None:
            return {"state": STATE_UNKNOWN, "provider": provider}
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT provider, state, kind, message, error_tag, source, "
                "  EXTRACT(EPOCH FROM since)::bigint, EXTRACT(EPOCH FROM updated_at)::bigint "
                "FROM agent_runtime.llm_provider_health WHERE provider = %s LIMIT 1",
                (provider,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return {"state": STATE_OK, "provider": provider}
        return {
            "provider": row[0],
            "state": row[1] or STATE_UNKNOWN,
            "kind": row[2],
            "message": row[3],
            "error_tag": row[4],
            "source": row[5],
            "since_epoch": row[6],
            "updated_epoch": row[7],
        }
    except Exception:
        return {"state": STATE_UNKNOWN, "provider": provider}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ── active probe(hybrid) ──────────────────────────────────────────────
_PROBE_STATE: "dict[str, Any]" = {"ts": 0.0, "running": False}

# 요청 단위 probe thinking budget(Anthropic 하한 1024). thinking 을 강제하는 alias
# (litellm config 가 budget_tokens 고정)에 max_tokens=1 을 보내면 Anthropic 제약
# (max_tokens > thinking.budget_tokens)을 위반해 항상 400 → classify None → OK/restricted
# 어느 것도 기록 못 해 stale restricted 배너를 영영 해소 못 한다(자동 복구 무력화 —
# llm-routing-interactive-split "thinking budget > max_tokens 오진" 함정). probe 는 요청
# 단위 override 로 최소 budget 을 넣고 max_tokens 를 그 위로 잡아 valid·저비용 ping 을 만든다.
_PROBE_THINKING_BUDGET = 1024


def _probe_enabled() -> bool:
    return os.getenv("LLM_HEALTH_PROBE_ENABLED", "1").strip().lower() not in ("0", "false", "off", "no")


def _probe_ttl() -> int:
    try:
        return max(10, int(os.getenv("LLM_HEALTH_PROBE_TTL_SEC", "60")))
    except Exception:
        return 60


def probe_provider(*, timeout_sec: int = 8, force: bool = False) -> "dict[str, Any]":
    """active probe — 최소 LLM 호출로 provider 자격증명 상태를 선제 확인 + 기록.

    TTL(LLM_HEALTH_PROBE_TTL_SEC, 기본 60s) 내 재호출은 skip(throttle) — 비용 최소화.
    분류 불가 예외는 health 를 바꾸지 않는다(일시 네트워크 등 오탐 방지). web 에서만 호출.

    실제 claude 호출(valid-ping)은 **restricted 상태(복구 감지 필요) 또는 force 일 때만** 발생한다 —
    ok/unknown 이면 cached 상태만 반환해 idle 폴링이 5h rolling 윈도우를 재고정하지 않는다.

    thinking 을 강제하는 alias(claude-*)면 요청 단위 thinking override(최소 budget) + max_tokens>
    budget 로 valid ping 을 만든다 — 그래야 성공 시 record_provider_ok 가 stale restricted 배너를
    실제로 해소한다(max_tokens=1 고정은 Anthropic 400 → 어느 상태도 기록 못 함). 비-thinking 모델
    (로컬 gemma 등)은 max_tokens=1(최저 비용) 유지.
    """
    provider = current_provider()
    if not _probe_enabled():
        return read_provider_health(provider)
    now = time.monotonic()
    # M1(리뷰): running 가드는 force 와 무관하게 항상(동시 force 스탬피드 차단). force 도 최소 5s 플로어
    # (per-request 비용 증폭 차단) — TTL 만 우회.
    if _PROBE_STATE["running"]:
        return read_provider_health(provider)
    min_gap = 5.0 if force else float(_probe_ttl())
    # probe-throttle-monotonic-flake: ts 는 time.monotonic()(부팅 이후 절대초)로만 스탬프되고 초기값은
    #   0.0(미-probe 센티넬)이다. `now - ts < min_gap` 만으로 판정하면, monotonic() 이 아직 min_gap 미만인
    #   갓-부팅 워커/러너에서 **첫 probe 가 spurious throttle** 된다(= restricted 복구 ping 누락 + 러너
    #   uptime 에 따라 갈리는 테스트 flake). last_ts>0 일 때만(=실제로 1회 이상 스탬프된 뒤에만) throttle.
    last_ts = float(_PROBE_STATE["ts"])
    if last_ts > 0.0 and now - last_ts < min_gap:
        return read_provider_health(provider)
    # M2(리뷰): 클러스터 전역 throttle — 다른 web 워커의 최근 probe(updated_at)가 TTL 내면 skip.
    # per-process _PROBE_STATE 만으로는 N 워커 stampede 방지 불가 → PG updated_at 비교로 보강.
    if not force:
        existing = read_provider_health(provider)
        try:
            if existing.get("source") == "probe" and existing.get("updated_epoch") \
               and (time.time() - float(existing["updated_epoch"])) < float(_probe_ttl()):
                return existing
        except Exception:
            pass
        # 능동 valid-ping(실제 claude 호출)은 **복구 감지가 필요한 restricted 상태일 때만** 한다.
        # ok/unknown 이면 실제 호출 없이 cached 상태만 반환 — idle 폴링이 claude-corp 5h rolling
        # 윈도우를 재고정하지 않게(refresh-claude-oauth-token.sh 가 cron probe 를 없앤 것과 동일 원칙).
        # 정상 상태에서 새로 발생하는 제한은 실제 답변 실패 경로(agent_core record_provider_restricted,
        # reactive)가 권위적으로 잡는다. force(사용자 명시 재시도)는 이 gate 를 우회해 즉시 실제 ping.
        if str(existing.get("state") or "") != STATE_RESTRICTED:
            return existing
    _PROBE_STATE["running"] = True
    _PROBE_STATE["ts"] = now
    try:
        from shared import config as cfg
        from shared.model_catalog import model_thinking_style
        from .llm import _get_llm_client
        model = getattr(cfg, "OPENAI_MODEL", None) or "claude-sonnet-4"
        client = _get_llm_client(timeout_sec=timeout_sec, model=model)
        if client is None:
            record_provider_restricted(not_configured_restriction(provider), source="probe")
            return read_provider_health(provider)
        # cc-identity-inject(2026-07-24): OAuth frontier(Sonnet 5)는 system 첫 블록에 Claude Code identity
        # 요구(없으면 429). probe 도 adaptive 계열이면 CC system 을 먼저 넣어야 valid ping 이 된다.
        # cc-identity-chokepoint(2026-08-25): 수동 주입을 관문으로 통일 — 주입 규칙의 정본은
        # prepare_provider_messages 하나다(호출측 개별 주입이 2회 재발의 구조적 원인이었다).
        from modules.llm import prepare_provider_messages
        _messages: "list[dict[str, Any]]" = prepare_provider_messages(
            [{"role": "user", "content": "ping"}], model)
        create_kwargs: "dict[str, Any]" = {
            "model": model,
            "messages": _messages,
            "timeout": timeout_sec,
        }
        # sonnet5-upgrade(2026-07-24): probe 도 모델별 thinking 스타일을 따라야 한다.
        _style = model_thinking_style(model)
        if _style == "budget":
            # budget 강제 alias(Haiku 등) — Anthropic 제약(max_tokens > budget_tokens) 충족하도록
            # 최소 budget override + max_tokens 를 그 위로. valid 성공 → OK 기록 → 배너 자동 해소.
            create_kwargs["max_tokens"] = _PROBE_THINKING_BUDGET + 64
            create_kwargs["extra_body"] = {
                "thinking": {"type": "enabled", "budget_tokens": _PROBE_THINKING_BUDGET}
            }
        elif _style == "adaptive":
            # Sonnet 5: budget_tokens 는 400. adaptive thinking + output_config.effort=low 로 저비용 valid ping.
            # (adaptive 는 budget<max_tokens 제약이 없어 max_tokens=1 도 400 은 아니나 응답이 잘려 무의미 →
            #  최소 여유(1088)를 준다.)
            create_kwargs["max_tokens"] = _PROBE_THINKING_BUDGET + 64
            create_kwargs["extra_body"] = {"output_config": {"effort": "low"}}
        else:
            create_kwargs["max_tokens"] = 1
        try:
            client.chat.completions.create(**create_kwargs)
            record_provider_ok(provider=provider, source="probe")
        except Exception as exc:
            restriction = classify_llm_provider_error(exc, provider)
            if restriction is not None:
                record_provider_restricted(restriction, source="probe")
        return read_provider_health(provider)
    except Exception:
        return read_provider_health(provider)
    finally:
        _PROBE_STATE["running"] = False
