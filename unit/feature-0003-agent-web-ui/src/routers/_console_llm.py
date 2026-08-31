"""feature-0043 (TASK-20260831T100000) — 관리 콘솔의 **LLM 상태 판정 단일 정본**.

## 왜 이 모듈이 있는가

feature-0043 이 서버 계정 LLM 을 fail-closed 로 차단하고 대화 답변을 개인 AI 브리지로
뒤집었는데, **그 전환이 대화 화면만 따라갔다.** 관리 콘솔은 게이트의 존재를 몰랐다 —
`static/admin/*.js` 전체에 차단 사실을 읽는 코드가 한 줄도 없었고, 그래서:

- 버튼은 그대로 있고 **눌러야** 503 을 알았다 (메타 자동완성 · 프롬프트 자동작성 · 능동 분석)
- 저장은 되는데 집행되지 않는 설정이 "설정됨" 으로 보였다 (모델 권한 · 추론 예산 · 자가 리뷰)
- `LLM 사용량` 이 0 으로 수렴해 "아무도 AI 를 안 쓴다" 로 읽혔다

## 왜 판정을 여기 하나로 두는가

이 feature 는 **같은 질문에 두 개의 답이 있으면 갈린다** 는 것을 이미 두 번 겪었다 —
P0-R(연결 판정이 화면과 인증에서 두 벌이라 로그아웃 후에도 "연결됨") 과 P0-Z3(목록의
출처가 서버와 러너로 갈려 "고를 수 있는데 반영은 안 되는" 상태).

관리 콘솔은 이 판정을 **여섯 곳**에서 쓴다(조작면 게이트 · 설정 배지 · 최하단 집계 ·
사용량 배너 · 운영 현황 축 · 위임 적재 전 검사). 각자 조립하면 그중 하나는 반드시 낡고,
낡는 순간 느슨한 쪽이 사용자가 보는 진실이 된다.

## 판정의 두 축은 **독립**이다

| 축 | 묻는 것 | 출처 |
|---|---|---|
| `server_llm_blocked` | 서버 계정으로 LLM 을 부를 수 있는가 | `shared.llm_gate` (env) |
| `delegation` | 이 계정의 개인 AI 가 콘솔 작업을 대신할 수 있는가 | 러너 신고 |

둘을 한 값으로 접지 않는다. 차단됐지만 위임 가능(정상 운영) · 차단됐고 위임 불가(안내
필요) · 차단 해제(종전 직접 경로) 는 화면이 **서로 다르게** 말해야 하는 세 상태다.
"""
from __future__ import annotations

import logging
from typing import Any

from shared.bridge_tasks import (
    RUNNER_FEATURE_BATCH_JOBS,
    RUNNER_FEATURE_CONSOLE_JOBS,
    RUNNER_MIN_AGENT_VERSION,
)
from shared.llm_gate import SERVER_LLM_ENABLED_ENV, server_llm_enabled

__all__ = [
    "DELEGATION_DIRECT",
    "DELEGATION_READY",
    "DELEGATION_NO_CONNECTION",
    "DELEGATION_RUNNER_IDLE",
    "DELEGATION_UNSUPPORTED",
    "DELEGATION_OUTDATED",
    "INACTIVE_SURFACES",
    "console_llm_state",
    "delegable_job_kinds",
    "delegation_available",
    "inactive_surfaces",
    "version_at_least",
]

_log = logging.getLogger(__name__)

#: 되돌리기 안내에 쓰는 env 이름 — 게이트 정본에서 가져온다(문자열을 여기 다시 적으면
#: 게이트가 knob 을 바꾸는 날 이 안내만 낡아 운영자를 없는 스위치로 보낸다).
_GATE_ENV = SERVER_LLM_ENABLED_ENV

#: 게이트가 열려 있다 — 종전 직접 경로. 위임은 애초에 필요 없다.
DELEGATION_DIRECT = "direct"
#: 위임 가능 — 연결된 러너가 콘솔 작업을 신고했다.
DELEGATION_READY = "ready"
#: 연결된 AI 자체가 없다(토큰 없음). 조치 = `/ai/connect`.
DELEGATION_NO_CONNECTION = "no_connection"
#: 토큰은 살아 있는데 **듣고 있는 프로세스가 없다**(러너 종료·재부팅). 조치 = 러너 기동.
#:
#: `no_connection` 과 나누는 이유: 조치가 다르다. 전자는 연결 설정이고 후자는 프로세스 기동인데,
#: 하나로 합치면 이미 연결한 사용자에게 매번 "연결하세요" 라고 말하게 된다(P0-G 가 대화 축에서
#: 고친 것과 같은 형태 — 안내가 하나면 둘 중 한쪽에게는 반드시 틀린 말이 된다).
DELEGATION_RUNNER_IDLE = "runner_idle"
#: 러너는 듣고 있는데 콘솔 작업 기능을 신고하지 않았다(구 러너 또는 `--cmd` 사용자).
DELEGATION_UNSUPPORTED = "unsupported"
#: 기능은 신고했는데 버전이 하한 미만 — 갱신 유도(사용자 결정 2026-08-31).
DELEGATION_OUTDATED = "outdated"

#: 조치까지 함께 말한다. 상태만 주면 화면이 문구를 각자 지어 여섯 곳이 갈린다.
#: **"고장" 어휘를 쓰지 않는다** — 이것은 운영 결정이고, 장애로 읽히면 사용자는 무한히
#: 재시도하며 원인을 찾는다(`llm_gate.feature_blocked_message` 와 같은 원칙).
_REASON: dict[str, str] = {
    DELEGATION_DIRECT: "",
    DELEGATION_READY: "연결된 본인 AI 가 이 작업을 처리합니다.",
    DELEGATION_NO_CONNECTION:
        "이 서비스는 서버 계정 AI 를 쓰지 않습니다. 본인 AI 를 연결하면 이 작업을 맡길 수 있습니다.",
    DELEGATION_RUNNER_IDLE:
        "연결은 되어 있는데 지금 듣고 있는 AI 가 없습니다. 본인 머신에서 AI 를 실행해 주세요.",
    DELEGATION_UNSUPPORTED:
        "연결된 AI 가 관리 콘솔 작업을 아직 다루지 못합니다. 연결 안내에서 최신 실행 파일을 받아 다시 실행해 주세요.",
    DELEGATION_OUTDATED:
        "연결된 AI 가 구버전입니다. 연결 안내에서 최신 실행 파일을 받아 다시 실행하면 이 작업을 맡길 수 있습니다.",
}

#: 조치 경로가 있는 상태만 링크를 준다 — "연결 안 됨" 만 보이고 방법이 없으면 소용없다(P0-T).
_ACTION_URL: dict[str, str] = {
    DELEGATION_NO_CONNECTION: "/ai/connect",
    DELEGATION_RUNNER_IDLE: "/ai/connect",
    DELEGATION_UNSUPPORTED: "/ai/connect",
    DELEGATION_OUTDATED: "/ai/connect",
}


# ── 미적용 표면 레지스트리 (A3) ─────────────────────────────────────────────────────
#
# 화면은 이 목록을 **세 곳**에서 쓴다: 각 패널 헤더의 `미적용` 배지 · 패널 내부의 사유
# dropdown · 설정 탭 최하단의 집계 섹션 (사용자 결정 2026-08-31). 세 곳이 각자 문구를
# 가지면 한 곳을 고칠 때 나머지가 낡는다 — 그래서 서버가 한 벌만 내려보낸다.
#
# 각 항목:
#   key      : 프론트가 DOM 을 찾는 안정 키. 문구가 바뀌어도 이 값은 안 바꾼다.
#   panel    : `data-settings-panel` 값 또는 논리 위치. 배지를 붙일 자리.
#   label    : 사람이 읽는 이름.
#   why      : **왜** 집행되지 않는가 (한 문장, 내부 용어 없이).
#   instead  : 대신 무엇이 작동하는가. 빈 값이면 대체가 없다는 뜻이고 화면이 그렇게 말한다.
#   restore  : 되돌리는 방법. 운영자용이므로 여기서는 env 이름을 써도 된다.
#
# ⚠ `delegated: True` 인 항목은 **위임으로 되살아난다** — 차단 중이어도 미적용이 아니다.
#   위임 가능 여부에 따라 표시가 갈리므로 `inactive_surfaces()` 가 그때 걸러 낸다.
INACTIVE_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "key": "model-thinking-budgets",
        "panel": "model-thinking-budgets",
        "label": "모델별 추론 예산",
        "why": "서버 계정 모델의 라운드당 출력 예산이라, 답변을 본인 AI 가 만드는 지금은 적용될 곳이 없습니다.",
        "instead": "추론 강도는 대화 화면의 선택기에서 연결된 AI 가 알려준 등급으로 고릅니다.",
        "restore": f"{_GATE_ENV}=1 로 서버 계정 LLM 을 되돌리면 다시 적용됩니다.",
        "delegated": False,
    },
    {
        "key": "redteam-review",
        "panel": "redteam-review",
        "label": "AI 자가 리뷰(적대 검증)",
        "why": "서버가 답변을 만들지 않으므로 서버 측 검증 단계가 실행되지 않습니다.",
        # red-team 은 위임으로 되살아나지만 **다른 주체**가 한다 — 그 사실을 여기서 말한다.
        # 되살아난 뒤에도 이 설정(축·강도)이 서버 검증을 지배하지는 않기 때문이다.
        "instead": "답변을 만든 본인 AI 가 같은 5축으로 자기 답변을 검증하고 결과를 함께 제출합니다.",
        "restore": f"{_GATE_ENV}=1 로 되돌리면 서버 측 검증이 다시 실행됩니다.",
        "delegated": False,
    },
    {
        "key": "model-access-rbac",
        "panel": "roles-accounts",
        "label": "모델별 접근 권한",
        "why": "대화에서 고를 수 있는 모델이 서버 카탈로그가 아니라 각자 연결한 AI 가 알려준 목록이라, 이 권한으로 걸러지지 않습니다.",
        "instead": "어떤 모델을 쓸지는 각 사용자가 자기 머신에서 실행한 AI 가 정합니다.",
        "restore": f"{_GATE_ENV}=1 로 되돌리면 카탈로그 기반 권한 필터가 다시 집행됩니다.",
        "delegated": False,
    },
    {
        "key": "runtime-timeouts-llm",
        "panel": "runtime-timeouts",
        "label": "실행 타임아웃 중 LLM 응답 상한",
        "why": "서버가 LLM 을 호출하지 않으므로 그 호출에 걸던 상한이 쓰이지 않습니다.",
        "instead": "본인 AI 의 처리 시간은 점유 유효기간(30분)과 러너 자체 설정이 정합니다.",
        "restore": f"{_GATE_ENV}=1 로 되돌리면 다시 적용됩니다.",
        "delegated": False,
    },
)


def inactive_surfaces(state: dict | None) -> list[dict[str, Any]]:
    """지금 실제로 **미적용인** 표면만. 게이트가 열려 있으면 빈 목록.

    `delegated` 항목은 위임이 성립한 상태에서 제외한다 — 되살아난 기능을 "미적용" 이라
    표시하면 그 표시 자체가 다음 거짓말이 된다. (현재 레지스트리에는 해당 항목이 없지만,
    위임 범위가 넓어질 때 이 필터가 그 확장을 자동으로 따라간다.)
    """
    if not state or not state.get("server_llm_blocked"):
        return []
    ready = state.get("delegation") == DELEGATION_READY
    return [dict(item) for item in INACTIVE_SURFACES
            if not (item.get("delegated") and ready)]


def version_at_least(actual: Any, minimum: str) -> bool:
    """`actual >= minimum` 을 점(.) 구분 정수 튜플로 비교한다.

    **판정 불가는 False**(=구버전 취급)로 본다. 버전을 모르는 러너에 콘솔 작업을 주면
    프레이밍이 어긋나 산출물이 조용히 망가지는데, 그 실패는 사용자에게 "AI 가 이상한 답을
    했다" 로만 보인다. 모르는 채로 "충족한다" 고 우길 근거가 없다.

    자릿수가 다르면 짧은 쪽을 0 으로 채운다(`2026.9` vs `2026.9.1`).
    """
    def _parts(v: Any) -> list[int] | None:
        s = str(v or "").strip()
        if not s:
            return None
        out: list[int] = []
        for chunk in s.split("."):
            chunk = chunk.strip()
            if not chunk.isdigit():
                return None
            out.append(int(chunk))
        return out or None

    got, want = _parts(actual), _parts(minimum)
    if got is None or want is None:
        return False
    width = max(len(got), len(want))
    got += [0] * (width - len(got))
    want += [0] * (width - len(want))
    return got >= want


def _classify(profile: dict, has_token: bool, *, need_batch: bool = False) -> str:
    """러너 신고 → 위임 상태. **순서가 의미다** — 가장 바깥 원인부터 판정한다.

    연결이 없는 사람에게 "러너를 갱신하세요" 라고 말하면 그는 갱신할 러너가 없다.
    """
    if not has_token:
        return DELEGATION_NO_CONNECTION
    if not profile.get("listening"):
        return DELEGATION_RUNNER_IDLE
    features = profile.get("features") or []
    if RUNNER_FEATURE_CONSOLE_JOBS not in features:
        return DELEGATION_UNSUPPORTED
    if not version_at_least(profile.get("agent_version"), RUNNER_MIN_AGENT_VERSION):
        return DELEGATION_OUTDATED
    if need_batch and RUNNER_FEATURE_BATCH_JOBS not in features:
        return DELEGATION_UNSUPPORTED
    return DELEGATION_READY


def delegation_available(state: dict | None) -> bool:
    """이 상태에서 콘솔 작업을 **적재해도 되는가**.

    게이트가 열려 있으면(`direct`) 위임 자체가 불필요하므로 False — 호출측은 종전 직접
    경로를 탄다. 적재 가능은 오직 `ready` 뿐이다.

    ⚠ "차단됐으니 위임" 이 아니라 "위임할 곳이 있으니 위임" 이다. 아무도 못 집는 작업을
    쌓지 않는다(P0-S 와 같은 규율).
    """
    return bool(state) and state.get("delegation") == DELEGATION_READY


def console_llm_state(conn, account: Any, *, need_batch: bool = False) -> dict:
    """관리 콘솔이 읽는 LLM 상태 — **이 판정의 유일한 출처**.

    Args:
        conn: 호출측이 이미 들고 있는 커넥션. 여기서 새로 열지 않는다 — 같은 요청 안에서
            두 트랜잭션이 생기면 방금 쓴 행을 못 보는 창이 열린다(`bridge_tasks` 와 동일 규율).
        account: 인증된 계정 dict. 없으면 위임 판정 불가 → 연결 없음으로 본다.
        need_batch: 배경 배치 자격까지 요구하는가(`batch_jobs` 동의 필요).

    Returns:
        `{"server_llm_blocked", "delegation", "reason", "action_url",
          "runner": {"listening", "agent_version", "features"}}`

    **조회 실패는 위임 불가로 본다**(fail-closed). 대화 축의 연결 판정은 fail-open 이지만
    (확신 없이 "연결이 없습니다" 라고 단정하면 이미 연결한 사용자에게 매번 설정하라고
    떠든다), 여기서는 방향이 반대다 — 낙관하면 **적재까지 해 버리고** 아무도 못 집는 작업이
    쌓인다. 표시의 오류는 한 줄이고 적재의 오류는 유령 작업이다.
    """
    blocked = not server_llm_enabled()
    runner = {"listening": False, "agent_version": "", "features": []}
    if not blocked:
        # 게이트가 열려 있으면 러너를 조회하지 않는다 — 쓰이지 않을 사실을 위해 매 요청
        # 토큰 테이블을 두드릴 이유가 없다.
        return {
            "server_llm_blocked": False,
            "delegation": DELEGATION_DIRECT,
            "reason": _REASON[DELEGATION_DIRECT],
            "action_url": "",
            "runner": runner,
        }

    account_id = 0
    try:
        account_id = int((account or {}).get("id") or 0)
    except (TypeError, ValueError, AttributeError):
        account_id = 0

    has_token = False
    if account_id and conn is not None:
        try:
            import oauth_store as _store

            cur = conn.cursor()
            try:
                has_token = bool(_store.account_has_live_token(cur, account_id))
                if has_token:
                    runner = _store.account_runner_profile(cur, account_id)
            finally:
                cur.close()
        except Exception as exc:  # noqa: BLE001
            # 조용히 낙관하지 않는다 — 사유를 남기고 위임 불가로 간다(위 docstring).
            _log.warning("[console-llm] 러너 상태 조회 실패 account=%s: %r", account_id, exc)
            has_token = False
            runner = {"listening": False, "agent_version": "", "features": []}

    state = _classify(runner, has_token, need_batch=need_batch)
    return {
        "server_llm_blocked": True,
        "delegation": state,
        "reason": _REASON.get(state, ""),
        "action_url": _ACTION_URL.get(state, ""),
        "runner": runner,
        # ── 위임은 **작업 종류 단위**로 참이다 (TASK-20260831T100000) ──────────────
        #
        # 러너가 콘솔 작업을 신고했다는 것과 *이* 기능의 전 구간(적재 호출부·프롬프트
        # 조립·산출물 반영)이 서 있다는 것은 다른 사실이다. 앞의 것만 보고 조작면을 열면
        # 사용자는 "눌렀는데 아무 일도 없는" 버튼을 만난다 — P0-M·P0-T 가 두 번 지운
        # 바로 그 상태다.
        #
        # 그래서 화면이 종류별로 판정할 수 있게 **배선이 선 종류의 목록**을 함께 내린다.
        # 러너 자격이 없으면 목록은 비어 있다(둘 다 필요하므로 여기서 미리 접는다).
        "delegable_jobs": (delegable_job_kinds() if state == DELEGATION_READY else []),
    }


def delegable_job_kinds() -> list[str]:
    """전 구간 배선이 선 작업 종류. 레지스트리의 `wired` 가 유일한 출처다.

    화면이 자기 목록을 갖지 않게 서버가 내려보낸다 — 프론트에 종류 이름을 적어 두면
    배선을 끄는 날 그 목록만 낡아, 없는 경로를 여는 버튼이 남는다.
    """
    from shared.bridge_tasks import JOB_SPECS

    return [k for k, v in JOB_SPECS.items() if v.get("wired")]
