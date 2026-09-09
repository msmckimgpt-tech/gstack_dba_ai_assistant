"""feature-0043 (TASK-20260831T100000) — 콘솔 작업의 **프롬프트 조립**과 **산출물 반영**.

## 이 모듈의 두 책임

| 방향 | 하는 일 |
|---|---|
| 나갈 때 | 각 작업 종류의 프롬프트를 조립한다 — **기존 헬퍼를 불러서** |
| 들어올 때 | 개인 AI 가 낸 답을 **기존 저장 경로**로 흘려보낸다 |

## 왜 "기존 것을 부른다" 가 핵심 제약인가

이 feature 는 같은 함정을 두 번 밟았다. P0-P 에서는 브리지가 `compose_system_prompt` 를
부르지 않아 **같은 질문이 경로에 따라 다른 규칙으로** 답해졌고, P0-U 에서는 헬퍼가 멀쩡한데
브리지가 그것을 **부르지 않아** 대화 제목과 단계 사유가 통째로 사라졌다.

둘 다 계산이 틀린 것이 아니라 **연결이 없던** 것이다 — 그래서 헬퍼 단위 테스트로는 전부
통과했다. 여기서 프롬프트를 새로 쓰거나 저장을 새로 구현하면 세 번째가 된다.

## 반영은 "제출" 과 다른 사실이다

`submit_answer` 가 성공해도 산출물이 저장소에 도달하지 못할 수 있다(형식 불일치·대상 소실·
권한). 그 둘을 한 상태로 접으면 화면은 "완료" 라 말하는데 값은 어디에도 없다. 그래서
`JobAppliedAt`/`JobApplyError` 를 따로 둔다 — `Delivered` 를 `Status` 와 나눈 것과 같은 규율.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.bridge_tasks import (
    FORMAT_NOTE as _bt_format_note,
    job_label, job_spec, load_console_job, mark_console_job_applied,
    messages_to_prompt as _bt_messages_to_prompt,
    store_console_job_result,
)

__all__ = [
    "apply_console_job_result",
    "build_job_status_payload",
    "console_job_body",
    "console_job_payload",
    "extract_json_object",
    "maybe_delegate",
    "messages_to_prompt",
    "poll_url_for",
]

_log = logging.getLogger(__name__)

#: 응답에서 JSON 을 찾을 때 벗겨 낼 코드펜스. 개인 AI 는 형식을 정확히 요구해도 코드펜스나
#: 머리말을 붙이는 일이 흔하다 — 러너(`_extract_json`)가 같은 관대함을 이미 갖고 있고,
#: 여기서도 같은 태도를 취한다(P0-Z4 "요구는 정확히, 수용은 관대하게").
_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*|\s*```\s*$")


def extract_json_object(text: Any) -> Any:
    """텍스트에서 **첫 완전한 JSON 객체/배열**을 꺼낸다. 못 찾으면 `None`.

    중괄호(대괄호) 균형으로 찾는다 — 정규식으로 잡으면 값 안의 `}` 에서 끊긴다.
    문자열 리터럴 안의 괄호와 이스케이프를 건너뛰므로 `{"a": "}"}` 도 온전히 잡는다.

    **관대함은 포장에 대한 것이지 내용에 대한 것이 아니다.** 코드펜스·머리말·맺음말은
    벗겨 내되, 내용이 JSON 이 아니면 추측하지 않고 `None` 을 돌려준다 — 추측하면 엉뚱한
    값이 저장소에 기입되고, 그 기입은 되돌릴 근거가 없다.
    """
    s = _FENCE_RE.sub("", str(text or "").strip())
    if not s:
        return None
    try:
        return json.loads(s)          # 통째로 JSON 이면 그대로(가장 흔한 정상 경로).
    except (TypeError, ValueError):
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = s.find(opener)
        if start < 0:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except (TypeError, ValueError):
                        break        # 균형은 맞는데 JSON 이 아니다 — 다음 여는 문자로.
    return None


def apply_console_job_result(conn, task_id: str, answer: str) -> tuple[bool, str]:
    """제출된 답을 그 작업의 **원래 저장 경로**로 흘려보낸다.

    Returns:
        `(applied, error)` — `applied=False` 면 `error` 에 사람이 읽을 사유가 담긴다.
        예외를 밖으로 올리지 않는다: 제출 자체는 이미 확정됐고(`Status='submitted'`), 여기서
        5xx 를 내면 러너가 재제출을 시도해 409 에 부딪힌다. 실패는 **상태로 남겨** 화면이
        "제출됐지만 반영 실패" 를 사유와 함께 말하게 한다.
    """
    job = load_console_job(conn, task_id)
    if job is None:
        return False, "작업 기록을 찾을 수 없습니다."
    kind = job["job_kind"]
    spec = job_spec(kind)
    if spec is None:
        # 적재 시점에 거른 값이라 정상 경로에서는 오지 않는다. 여기 오면 레지스트리가
        # 배포 사이에 바뀐 것이므로, 조용히 성공으로 두지 않는다.
        return False, f"등록되지 않은 작업 종류입니다: {kind}"

    payload = None
    if job.get("payload"):
        try:
            payload = json.loads(job["payload"])
        except (TypeError, ValueError):
            payload = None

    # 형식 검증은 **저장 전에** 한다. 형식이 어긋난 답을 그대로 넣으면 되돌릴 근거가 없다.
    if spec["response"] == "json":
        parsed = extract_json_object(answer)
        if parsed is None:
            return _fail(conn, task_id, kind,
                         "AI 답변에서 요청한 형식(JSON)을 찾지 못했습니다.")
        result: Any = parsed
    else:
        result = str(answer or "").strip()
        if not result:
            return _fail(conn, task_id, kind, "AI 답변이 비어 있습니다.")

    # 화면이 읽을 **원문**을 보존한다 (2026-08-31 라이브 제보).
    #
    # `WebAiTasks.Answer` 는 각인본이다 — 감사 보존과 지연 인젝션 방어를 위해 저장 시점에
    # `⟦UNTRUSTED-DATA⟧ … ⟦/UNTRUSTED-DATA⟧` 로 구획된다. 그것을 폼에 그대로 채우면 사용자
    # 눈에 래퍼가 통째로 들어간다(실제 제보). 대화 경로는 이 문제를 원문을 따로 저장해
    # 해결했고("두 소비처의 요구가 달라 저장본을 나눈다"), 콘솔 경로도 같은 규율을 쓴다.
    #
    # 실패해도 반영을 막지 않는다 — 보존은 화면 편의이지 반영의 조건이 아니다.
    try:
        store_console_job_result(conn, task_id, str(answer or "").strip())
    except Exception as exc:  # noqa: BLE001
        _log.warning("[console-job] 원문 보존 실패 task=%s: %r", task_id, exc)

    # 검토형은 여기서 저장하지 않는다 — 사람이 화면에서 확인하고 기존 '저장' 버튼으로 넣는다.
    # 위임이 그 단계를 건너뛰면 **기존 경로의 쓰기 의미가 바뀐다**(사용감 회귀).
    if spec["apply"] == "review":
        mark_console_job_applied(conn, task_id, "")
        return True, ""

    try:
        _store_result(conn, kind, result, payload)
    except Exception as exc:  # noqa: BLE001
        _log.error("[console-job] 산출물 반영 실패 task=%s kind=%s: %r", task_id, kind, exc)
        return _fail(conn, task_id, kind, f"저장 중 오류: {exc}")
    mark_console_job_applied(conn, task_id, "")
    _log.info("[console-job] 산출물 반영 task=%s kind=%s", task_id, kind)
    return True, ""


def _fail(conn, task_id: str, kind: str, message: str) -> tuple[bool, str]:
    """실패 사유를 **작업 행에 남기고** 돌려준다. 로그만 남기면 화면이 못 읽는다."""
    _log.warning("[console-job] %s — task=%s kind=%s", message, task_id, kind)
    try:
        mark_console_job_applied(conn, task_id, message)
    except Exception as exc:  # noqa: BLE001
        _log.error("[console-job] 실패 사유 기록 실패 task=%s: %r", task_id, exc)
    return False, message


#: 자동기입 경로 — `job_kind` → `(모듈, 함수명)`. **선언만 여기 두고 구현은 그 모듈에** 둔다.
#:
#: 저장 규칙(정규화·중복 처리·감사 기록)을 이 모듈에 다시 쓰지 않는 것이 요점이다. 두 벌이
#: 되는 순간 한쪽이 낡고, 그때부터 같은 값이 경로에 따라 다르게 저장된다 — P0-P 가 시스템
#: 프롬프트 축에서, P0-U 가 제목·단계 축에서 이미 겪은 형태.
#:
#: ⚠ 여기 이름이 있다고 배선이 끝난 것은 아니다. **적재 자격은 `JOB_SPECS[...]["wired"]`** 가
#:   정하고, 그것이 False 인 종류는 애초에 대기열에 들어오지 못한다. 이 표는 wired 종류가
#:   도달할 곳을 적은 것이고, 미구현 모듈은 아래 ImportError 경로로 **사유와 함께** 실패한다.
_STORE_ROUTES: dict[str, tuple[str, str]] = {
    "node_analysis": ("modules.node_analysis", "apply_external_node_analysis"),
    "insight_summary": ("modules.insight", "apply_external_insight_summary"),
    "cluster_label": ("modules.semantic_cluster", "apply_external_cluster_labels"),
}


def _store_result(conn, kind: str, result: Any, payload: Any) -> None:
    """자동기입형 작업의 산출물을 **기존 저장 함수**로 넘긴다.

    이 함수가 하는 일은 "값을 꺼내 기존 함수에 넘기는 것" 뿐이다. 대상 함수가 아직 없으면
    `ImportError`/`AttributeError` 가 나고, 호출측이 그것을 **사유와 함께** 작업 행에 남긴다
    (조용한 성공으로 접지 않는다).
    """
    route = _STORE_ROUTES.get(kind)
    if route is None:
        raise RuntimeError(f"자동기입 경로가 정의되지 않은 작업 종류입니다: {job_label(kind)}")
    module_name, func_name = route
    module = __import__(module_name, fromlist=[func_name])
    func = getattr(module, func_name, None)
    if func is None:
        raise RuntimeError(
            f"{job_label(kind)} 의 반영 함수({module_name}.{func_name})가 아직 없습니다.")
    func(conn, payload or {}, result)


# ── 나가는 방향: 기존 `messages` 를 그대로 위임 프롬프트로 ────────────────────────────
#
# 관리 콘솔의 네 기능은 전부 **OpenAI 스타일 `messages` 를 조립한 뒤** LLM 을 부른다. 그
# 조립부가 이 feature 의 자산이다(스키마 grounding · 제품 바인딩 · 필드 제약이 전부 거기 있다).
#
# 그래서 위임은 조립 **뒤**, 호출 **앞** 한 지점에만 끼운다. 프롬프트를 여기서 새로 쓰면
# 같은 기능이 경로에 따라 다른 규칙으로 산출되고, 그때부터 한쪽은 반드시 낡는다
# (P0-P 가 시스템 프롬프트 축에서, P0-U 가 제목·단계 축에서 이미 겪은 형태).

#: 출력 형식 지시 · `messages` → 단일 프롬프트 편성. **정본은 `shared.bridge_tasks`** 다
#: (TASK-20260901T190000). 옮긴 이유: 그래프 능동 분석·인사이트 배치를 **워커**가 위임하게
#: 됐고, 그쪽은 다른 컨테이너라 이 모듈을 import 하지 못한다. 여기 남겨 두고 워커가 자기
#: 편성을 새로 쓰면 같은 작업이 경로에 따라 다른 프롬프트로 나가고, 그때부터 한쪽은 낡는다.
_FORMAT_NOTE = _bt_format_note
messages_to_prompt = _bt_messages_to_prompt


def maybe_delegate(request, account, *, job_kind: str, messages: Any,
                   payload: Any = None, product_id: Any = None,
                   datasource_key: str | None = None):
    """이 요청을 개인 AI 에게 넘길 수 있으면 **넘기고 대기 응답**을 돌려준다.

    Returns:
        `JSONResponse` — 위임 적재 성공(대기). 호출측은 **그대로 반환**한다.
        `None` — 위임 대상이 아니다(게이트 열림 / 러너 자격 없음 / 미배선 종류).
                 호출측은 종전 경로를 그대로 탄다 — 게이트가 닫혀 있으면 그 경로가
                 `feature_blocked_message` 로 안내하므로 **여기서 그 문구를 다시 쓰지 않는다.**

    적재 실패(`ConsoleJobRejected`)도 `None` 을 돌려준다 — 사유는 로그에 남기고, 사용자에게는
    종전 경로의 안내가 나간다. 위임은 개선이지 새로운 실패 지점이 되어선 안 된다.
    """
    from fastapi.responses import JSONResponse

    from shared.bridge_tasks import ConsoleJobRejected, enqueue_console_job, job_label, job_spec
    from routers._console_llm import console_llm_state, delegation_available

    spec = job_spec(job_kind)
    if spec is None or not spec.get("wired"):
        return None
    conn = None
    try:
        import app as _app

        conn = _app._connect_memory()
        # `job_kind` 를 넘겨 **그 항목에 고른 모델**까지 자격에 넣는다 (TASK-20260902T110000).
        # 넘기지 않으면 화면은 "맡겼습니다" 라고 말하고 claim 이 거절해, 사용자는 결과를
        # 영영 기다린다 — 표시와 집행이 갈리는 그 형태가 이 feature 가 반복해 고쳐 온 결함이다.
        state = console_llm_state(conn, account, job_kind=job_kind)
        if not delegation_available(state):
            return None
        prompt = messages_to_prompt(messages, spec.get("response") or "text")
        task_id = enqueue_console_job(
            conn, account_id=int((account or {}).get("id") or 0), job_kind=job_kind,
            prompt=prompt, payload=payload, product_id=product_id,
            datasource_key=datasource_key)
    except ConsoleJobRejected as exc:
        _log.info("[console-job] 위임 미적재 kind=%s: %s", job_kind, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        _log.warning("[console-job] 위임 적재 실패 kind=%s: %r", job_kind, exc)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return JSONResponse({
        # 프런트 계약: 이 키가 있으면 **결과가 아직 없다** — 폴링으로 전환한다.
        "bridge_pending": True,
        "task_id": task_id,
        "job_kind": job_kind,
        "poll_url": poll_url_for(task_id),
        "message": f"{job_label(job_kind)}을(를) 연결된 본인 AI 에 맡겼습니다. 완료되면 여기에 채워집니다.",
    })


# ── 진행/결과 조회 응답의 단일 조립 (TASK-20260909T000000-prompt-autogen-delivery) ──────
#
# 폴링 경로가 둘이다: 관리 콘솔용 `/api/admin/ai-jobs/{task_id}`(종전, `console.access`)와
# 프로필용 `/api/profile/ai-jobs/{task_id}`(신설, 로그인만). **응답 계약은 하나여야 한다** —
# 두 벌로 두면 한쪽만 고쳐지고, 화면은 어느 경로로 물었는지에 따라 다른 사실을 듣는다.
# 권한은 각 라우트가 정하고, 무엇을 말하는지는 여기가 정한다.

def poll_url_for(task_id: str) -> str:
    """위임 응답에 실을 폴링 주소.

    **프로필 경로**를 준다 — 위임을 여는 세 진입점 중 개인 프롬프트 자동작성은 `console.access`
    를 요구하지 않는다(`JOB_SPECS['prompt_generate']['perms']` 가 비어 있는 것과 같은 사실).
    관리 권한이 필요한 주소를 주면 그 사용자는 작업이 정상 적재·완료돼도 결과를 영영 못 받는다.
    관리자에게도 이 경로가 맞다 — 스코프가 «자기 계정이 연 작업» 이라 admin 경로와 같은 것만
    본다. 종전 admin 경로는 호환을 위해 남아 있다.
    """
    from urllib.parse import quote

    return f"/api/profile/ai-jobs/{quote(str(task_id), safe='')}"


def console_job_body(job) -> str:
    """화면에 줄 **원문**. `JobResult`(정본) → 없으면 각인본을 벗겨 폴백.

    폴백이 있는 이유: 원문 컬럼이 생기기 **이전에** 제출된 작업은 그 칸이 비어 있다. 그 행들을
    버리면 사용자는 이미 AI 가 답한 작업을 다시 시켜야 한다.

    새 코드가 폴백에 의존하지 않게 순서를 이렇게 둔다 — 정본이 있으면 파싱하지 않는다.
    """
    raw = job.get("result")
    if raw:
        return str(raw)
    from session_guard import unwrap_external_answer

    return unwrap_external_answer(job.get("answer") or "")


def console_job_payload(raw):
    """저장된 JSON payload → dict. 깨졌으면 `None`(화면은 그때 폼 컨텍스트로 폴백한다)."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def build_job_status_payload(job) -> dict:
    """위임 작업 1건의 진행/결과 응답 본문.

    ## 국면은 **서버가 한 단어로** 정한다

    프런트가 `submitted && !error` 같은 조합을 다시 만들면 화면마다 갈리고, 갈리는 순간 느슨한
    쪽이 사용자가 보는 진실이 된다(대화 축과 같은 규율).

    ## `degraded` — 「제출됐다」와 「AI 가 해냈다」를 가른다

    러너는 자기 AI 가 실패하면 사유를 **답변 본문에 적어** 제출한다(침묵보다 낫다는 대화 축의
    옳은 결정). 그 답이 콘솔 작업 축에 오면 «결과물» 이 되어 폼을 덮으므로, 여기서 그 사실을
    표시해 화면이 본문을 덮지 않게 한다. 판정 정본은 `shared.bridge_tasks.runner_degraded_reason`.
    상태 자체는 `submitted`(러너는 제 할 일을 했다) 그대로 두고, **해석만** 덧붙인다.
    """
    from shared.bridge_tasks import job_label, runner_degraded_reason

    status = str(job.get("status") or "")
    submitted = status == "submitted"
    applied = job.get("applied_at") is not None
    error = str(job.get("apply_error") or "")
    if status in ("canceled", "expired"):
        phase = "canceled"
    elif not submitted:
        phase = "working" if job.get("claimed_by") is not None else "waiting"
    elif error:
        # 「제출됐지만 반영 실패」는 성공이 아니다 — 합치면 화면이 완료라 말하는데 값이 없다.
        phase = "apply_failed"
    else:
        phase = "done"

    # 본문은 **완료됐을 때만** 싣는다. 진행 중에 부분 결과를 흘리면 화면이 그것을 최종으로
    # 읽고 폼에 채운 뒤, 잠시 뒤 다른 값으로 덮인다.
    #
    # ⚠ **각인본(`Answer`)을 주지 않는다** (2026-08-31 라이브 제보). 그것은 감사 보존·지연
    #   인젝션 방어용이고, 화면에 그대로 주면 `⟦UNTRUSTED-DATA⟧ …` 래퍼가 통째로 폼
    #   입력란에 들어간다. 원문은 제출 시점에 `JobResult` 로 따로 보존한다.
    body = console_job_body(job) if submitted else None
    degraded_reason = runner_degraded_reason(body) if body else None

    return {
        "task_id": job["task_id"],
        "job_kind": job["job_kind"],
        "label": job_label(job["job_kind"]),
        "phase": phase,
        "status": status,
        "claimed": job.get("claimed_by") is not None,
        "applied": applied,
        "apply_error": error,
        "result": body,
        # 러너가 실패를 안내문으로 대체 제출했는가. 화면은 이 표시를 보고 본문을 덮지 않는다.
        "degraded": degraded_reason is not None,
        "degraded_reason": degraded_reason or "",
        # 적재 시점에 굳힌 입력. 화면이 **서버 봉투를 재구성**하는 데 쓴다 — 직접 경로는
        # `{target, suggestion}` 같은 봉투를 서버가 만들지만, 위임 결과는 AI 가 낸 본문뿐이라
        # "이 답이 무엇에 대한 것인가" 를 화면이 알아야 폼의 어느 칸에 넣을지 정한다.
        "payload": console_job_payload(job.get("payload")),
    }
