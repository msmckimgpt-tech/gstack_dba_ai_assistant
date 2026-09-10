"""한 건 처리 (`handle_one`).

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import hashlib
from contextlib import ExitStack

from .sessions import conversation_session

from .cancel import CancelRegistry

import time

from .api import Api
from .discovery import _which_ai
from .events import _EV_TASK_CANCEL, _EV_TASK_DISPATCH, _EV_TASK_REVIEW, _EV_TASK_SUBMIT_FAIL, _EV_TASK_SUBMIT_OK, _EV_TASK_SUBMIT_REJECT, _EV_TASK_SUBMIT_RETRY, _EV_TASK_UNMET
from .invoke import CANCELED, ask_local_ai, offered_options, system_channel_fits, system_channel_supported
from .logs import log_event
from .prompt import annotate_approval_request, compose_prompt, split_glossary, split_title
from .review import run_self_review
from .runtimes import _RUNTIME_SPECS, _STRICT_MCP_FLAG, runtime_option_flag
from .timing import _RECONNECT_BACKOFF_START

# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, claimed: dict, kind: str, argv: list[str],
               custom: str | None, cancels: "CancelRegistry | None" = None,
               runtimes: list | None = None, caps: dict | None = None,
               self_review: bool = True) -> bool:
    """이미 **점유된** task 하나를 처리한다.

    점유(`claim_request`)를 여기서 하지 않고 호출측(대기 루프)이 하는 이유: 점유가 늦으면 그
    task 가 `wait_for_request` 결과에 계속 남아, 워커가 다 찼을 때 같은 것을 반복해서 받게 된다
    (그리고 그 반복이 곧 서버를 두드리는 tight loop 다). 점유는 값싸고 즉시 끝나므로 대기
    루프에서 처리하고, 오래 걸리는 AI 호출만 워커로 넘긴다.
    """
    with ExitStack() as session_stack:
        _canceled = (lambda: cancels.is_canceled(task_id)) if cancels else (lambda: False)

        # 웹에서 고른 (런타임·모델·추론등급). 유효성은 **이 러너의 신고**로 판정한다 (P0-Z3) —
        # 서버가 준 값을 그대로 믿지 않는다. 지정이 없으면 이 머신의 AI 설정이 정한다.
        want = claimed.get("requested") or {}
        want_runtime = str(want.get("runtime") or "").strip()
        want_model = str(want.get("model") or "").strip() or None
        want_effort = str(want.get("reasoning_level") or "").strip() or None
        run_kind, run_argv = kind, argv
        unmet: list[str] = []

        if want_runtime and want_runtime != run_kind:
            # 사용자가 이 머신의 **다른** 런타임을 골랐다. 신고에 있고(= 우리가 고를 수 있다고
            # 말했고) 지금도 실재할 때만 그쪽으로 보낸다. `--ai` 로 제한한 사용자의 의도를
            # 서버 응답이 넘어서지 않게, 정적 표가 아니라 신고를 본다(codex P1-5).
            _offered = any(str(rt.get("runtime") or "") == want_runtime for rt in (runtimes or []))
            _known = (_RUNTIME_SPECS.get(want_runtime) or {}).get("argv")
            _learned = ((caps or {}).get(want_runtime) or {}).get("argv")
            if _offered and (_known or _learned) and _which_ai(want_runtime):
                run_kind = want_runtime
                run_argv = list(_known or _learned)
            else:
                unmet.append(f"런타임 {want_runtime}")

        # 반영하지 못하는 지정을 **조용히 버리지 않는다**(codex P1-4). 같은 계정에 러너가 여럿이면
        # 목록을 신고한 러너와 질문을 가져간 러너가 다를 수 있고, 그때 사용자는 자기가 고른 것이
        # 적용됐다고 믿는다. 무엇이 반영되지 않았는지는 답변에 적어 사용자가 알게 한다.
        _models, _efforts = offered_options(runtimes, run_kind)
        # ⚠ 목록에 있는 것만으로는 부족하다 — **그 값을 넘길 플래그가 있어야** 인자가 된다
        #   (codex P1-5). 표 밖 CLI 가 모델 목록만 신고하고 `model_flag` 를 못 주면 `build_cmd`
        #   는 모델 인자를 붙이지 않는데, 목록 대조만 보면 `unmet` 이 비어 "반영됐다" 고 말하게
        #   된다. 그 고지는 거짓이고, 사용자는 고르지 않은 기본 모델의 답을 자기가 고른 모델의
        #   답으로 읽는다. 플래그 출처는 `build_cmd` 와 같은 어댑터를 사용한다.
        _local = (caps or {}).get(run_kind) or {}
        _model_flag = runtime_option_flag(run_kind, "model", _local)
        _effort_flag = runtime_option_flag(run_kind, "effort", _local)
        _model_ok = bool(want_model) and bool(_model_flag) and any(
            str(o.get("value")) == want_model for o in _models)
        _effort_ok = bool(want_effort) and bool(_effort_flag) and any(
            str(o.get("value")) == want_effort for o in _efforts)
        if want_model and not _model_ok:
            unmet.append(f"모델 {want_model}")
        if want_effort and not _effort_ok:
            unmet.append(f"추론등급 {want_effort}")

        # 운영자 지침을 실제 시스템 채널로 보낼 수 있는가 (TASK-20260901T140000).
        # **한 번만 판정해 두 곳에 쓴다** — 프롬프트 조립과 명령 조립이 각자 판정하면 지침이
        # 두 벌이 되거나(본문 + 플래그) 한 벌도 없는 상태가 된다.
        # 콘솔 작업(`kind='job'`)은 서버가 완성된 지시문을 보내므로 운영자 지침 자체가 없다.
        _sysp = str(claimed.get("system_prompt") or "")
        # 두 축을 **따로** 묻는다 (TASK-20260902T140000): ① 그 CLI 가 이 플래그를 아는가
        # ② 이 운영체제가 이 길이를 인자로 받아 주는가. ②가 거짓이면 지침을 본문으로 접는다 —
        # 인젝션 오판 방지를 잃지만, 접지 않으면 Windows 에서 **답이 아예 오지 않는다**
        # (라이브 2026-09-02: 지침 34,962자 → `[WinError 206]` 로 전 질문 사망).
        _sys_supported = bool(_sysp) and system_channel_supported(run_kind, custom)
        _use_sys_channel = _sys_supported and system_channel_fits(run_kind, _sysp)
        if _sys_supported and not _use_sys_channel:
            log_event("task.system_channel.folded",
                      "운영자 지침이 이 운영체제의 명령줄 상한을 넘어 본문으로 전달합니다.",
                      level="WARN", task=task_id, runtime=run_kind, system_chars=len(_sysp))
        prompt = compose_prompt(api, {**claimed, "task_id": task_id},
                                system_channel=_use_sys_channel)
        # 이 질문 한 건의 **일생**을 같은 키(`task`)로 묶는다 (TASK-20260901T163000). 동시 처리에서
        # 줄이 인터리브되어도 `task=` 로 걸러내면 한 건의 흐름이 그대로 복원되고, 그 키는 서버
        # DB(`BridgeTasks.TaskId`)·웹 화면과도 같은 값이라 3자 대조가 된다.
        _t_task = time.monotonic()
        log_event(_EV_TASK_DISPATCH, "내 AI 에게 전달", task=task_id, runtime=run_kind,
                  model=want_model, effort=want_effort,
                  kind=str(claimed.get("kind") or "conversation"),
                  conv=str(claimed.get("conversation_id") or "") or None,
                  prompt_chars=len(prompt), sys_channel=_use_sys_channel,
                  system_delivery=("system" if _use_sys_channel else "user_body") if _sysp else "none",
                  system_chars=len(_sysp),
                  system_sha256=hashlib.sha256(_sysp.encode("utf-8")).hexdigest() if _sysp else None)
        if unmet:
            # 「고른 값이 반영되지 않았다」는 **답변에도 적히지만 로그에도 남겨야** 한다 — 답변은
            # 사용자가 지우면 사라지고, 같은 계정에 러너가 여럿일 때의 재현 조사는 로그로 한다.
            log_event(_EV_TASK_UNMET, "요청한 지정을 반영하지 못했다", level="WARN",
                      task=task_id, runtime=run_kind, unmet=list(unmet))
        selection_unavailable = bool(
            (want_runtime and want_runtime != run_kind)
            or (want_model and not _model_ok)
            or (custom and (want_runtime or want_model))
        )
        binding = None
        if selection_unavailable:
            ok, answer = False, "선택한 AI 또는 모델을 현재 연결에서 사용할 수 없습니다. AI 연결과 모델 선택을 확인한 뒤 다시 보내 주세요."
        else:
            binding = session_stack.enter_context(conversation_session(api, claimed, run_kind, custom))
            ok, answer = ask_local_ai(run_kind, run_argv, prompt, custom, _canceled,
                                      model=want_model, effort=want_effort, runtimes=runtimes,
                                      caps=caps,
                                      system=(_sysp if _use_sys_channel else None),
                                      token=api.token, api_base=api.base, api_ca=api.ca,
                                      session=(binding.result if binding else None))
        if answer == CANCELED:
            # 사용자가 취소했다. **제출하지 않는다** — 서버도 409 로 거절하지만, 여기서 멈추는 것이
            # 토큰과 왕복을 아끼는 지점이다.
            log_event(_EV_TASK_CANCEL, "사용자가 취소했다 — 제출하지 않는다", level="WARN",
                      task=task_id, runtime=run_kind, at="during_ai",
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            return False
        generated_answer = ok and bool(answer.strip())
        if not generated_answer:
            # 「AI 가 실패했다」와 「AI 가 빈 답을 냈다」는 사용자에게는 같아 보이지만 원인이 다르다
            # (전자는 exit≠0 · 후자는 exit=0 에 출력 0바이트 — 프롬프트 거절이 대표적이다).
            log_event("task.answer.degraded", "실패·빈 응답을 안내문으로 대체해 제출한다",
                      level="WARN", task=task_id, runtime=run_kind,
                      reason=("ai_failed" if not ok else "empty_answer"),
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
            # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
            answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
                "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

        # 답을 만드는 동안 취소됐을 수 있다 — 제출 **직전**에 한 번 더 본다.
        # 제목 분리보다 **앞**에 둔다: 어차피 버릴 답이면 가공할 이유가 없다.
        if _canceled():
            log_event(_EV_TASK_CANCEL, "답변 완료 직전에 취소됨 — 제출하지 않는다", level="WARN",
                      task=task_id, runtime=run_kind, at="before_submit",
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            return False

        # 제목·용어 줄은 답변에서 떼어 별도 필드로 보낸다 — 본문에 남기면 사용자가 규약 문자열을 본다.
        #
        # 순서: title → glossary → title 한 번 더. 지시는 「용어 줄, 그 다음 제목 줄」 하나로 주지만,
        # 두 줄을 뒤바꿔 내는 런타임이 있으면 첫 `split_title` 이 실패하고 그 줄이 본문에 남는다.
        # 두 번째 호출은 그 경우를 흡수한다(마커가 없으면 no-op 이라 정상 경로에는 무영향).
        answer, title = split_title(answer)
        answer, glossary_terms = split_glossary(answer)
        if not title:
            answer, title = split_title(answer)

        # 반영하지 못한 지정을 **밝힌다**(codex REV-20260828T170000 P1-4). 조용히 기본값으로
        # 답하면 사용자는 자기가 고른 모델로 답이 나온 줄 안다 — 그 오해는 화면 어디에도 드러나지
        # 않는다. 같은 계정에 러너가 여럿일 때(목록을 신고한 러너 ≠ 질문을 가져간 러너) 실제로
        # 발생한다. 제목 분리 **뒤**에 붙인다: 앞에 붙이면 이 줄이 제목 규약 위치를 밀어낸다.
        #
        # ⚠ **반영된 지정은 답변 본문에 쓰지 않는다** (사용자 결정 2026-08-31).
        #
        #   잠깐 넣었다가 뺐다. 넣은 이유는 "무엇으로 답했는지 확인할 수 없다" 였는데, 그 확인
        #   수단은 **선택기 라벨**이면 충분하다 — 그리고 그쪽이 답변을 읽기 전에, 다음 질문을
        #   보내기 전에 보인다. 답변마다 붙는 한 줄은 정상 경로에서 아무것도 더하지 않으면서
        #   본문을 밀어낸다. (라벨이 러너 어휘를 표시하지 못하던 결함은 같은 cycle 에서 고쳤다.)
        #
        #   **미반영 고지는 남긴다** — 그건 다른 사실이다. "고른 값이 반영되지 않았다" 는 화면
        #   어디에도 드러나지 않으므로 답변이 유일한 통로다.
        if unmet:
            answer = (answer or "") + (
                f"\n\n> 참고: 요청하신 {' · '.join(unmet)} 은(는) 이 AI 에서 쓸 수 없어"
                + (" 기본 설정으로 답했습니다." if generated_answer
                   else " 적용되지 않았습니다.")
            )

        # 프롬프트 계약은 지시이지 집행이 아니다 — 따르지 않은 답이 그대로 화면에 가는 것을 여기서
        # 막는다 (codex P1-4). 답을 지우지 않고 「할 일이 없다」를 덧붙인다. 제목 분리 **뒤**다.
        answer, _asked_approval = annotate_approval_request(answer)
        if _asked_approval:
            log_event("task.answer.approval_request",
                      "답변이 사용자에게 도구 승인을 요구했다 — 안내를 덧붙였다. "
                      "(연결된 AI 가 도구 호출 실패를 권한 문제로 오해한 신호. "
                      f"claude 라면 {_STRICT_MCP_FLAG} 적용 여부와 토큰 유효성을 확인하라)",
                      level="WARN", task=task_id, runtime=run_kind)

        # 자가 검증 — 제출 **직전**, 취소 검사 뒤. 여기 두는 이유: 취소된 답을 검증하는 것은
        # 남의 계정 토큰을 이유 없이 태우는 일이고, 제출 뒤에 두면 검증 결과를 실을 자리가 없다.
        #
        # ⚠ 검증은 답변을 **바꾸지 않는다.** 서버 시절에는 BLOCK 결함이면 초안을 고쳐 다시
        #   물었지만(`REDTEAM_MAX_REVISIONS`), 그 반복은 개인 머신 AI 호출을 몇 배로 늘린다 —
        #   남의 자원이라 우리가 임의로 결정할 축이 아니다. 지금은 **판정을 기록**하고 그
        #   판정을 콘솔이 보이게 하는 데까지다(수정 반복은 별도 결정 사항).
        review = None
        if self_review and generated_answer:
            review = run_self_review(claimed.get("self_review") or {}, answer, run_kind, run_argv,
                                     custom, _canceled, model=want_model, effort=want_effort,
                                     runtimes=runtimes, caps=caps)
            if review:
                log_event(_EV_TASK_REVIEW, "자가 검증 완료 — 제출에 동봉", task=task_id,
                          dur_ms=review["latency_ms"], model=review.get("model"),
                          effort=review.get("reasoning_level"))

        payload = {"task_id": task_id, "answer": answer, "source_tasks": [task_id]}
        if title:
            payload["title"] = title
        if glossary_terms:
            # 빈 목록은 싣지 않는다 — 서버가 `None` 과 `[]` 를 구분해 「규약을 모르는 러너」와
            # 「담을 것이 없던 턴」을 로그에서 가를 수 있게 한다.
            payload["glossary_terms"] = glossary_terms
        if review:
            # 서버 계약: `review.raw` 는 검증자가 낸 원문이다(우리가 뜯지 않는다).
            payload["review"] = {
                "raw": review["raw"], "latency_ms": review["latency_ms"],
                "model": review["model"], "reasoning_level": review["reasoning_level"],
            }
        res = api.call("submit_answer", payload, timeout=120.0)
        if res.get("_http") == 409:
            # 취소 신호를 못 본 채 여기까지 왔다(서버가 마지막 관문). 정상 흐름이다.
            log_event(_EV_TASK_SUBMIT_REJECT, "서버가 제출을 거절했다(취소된 요청) — 버린다",
                      level="WARN", task=task_id, http=409,
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            return False
        if res.get("_failed"):
            # ⚠ 연결 실패는 `_http == 0` 이라 아래 진위 검사에 걸리지 않는다 (codex P2-2).
            #   그대로 두면 **저장 여부를 모르는데 "제출 완료" 라고 기록**한다. 답변은 이미 만들어
            #   놓았으므로 한 번 더 시도할 값어치가 있다 — 서버의 `SubmittedAt IS NULL` 가드가
            #   중복 제출을 409 로 막으므로 재시도는 안전하다(멱등).
            log_event(_EV_TASK_SUBMIT_RETRY, "제출 중 연결 실패 — 한 번 더 시도한다",
                      level="WARN", task=task_id, attempt=1, http=0,
                      detail=str(res.get("error") or ""))
            time.sleep(_RECONNECT_BACKOFF_START)
            res = api.call("submit_answer", payload, timeout=120.0)
            if res.get("_failed") or res.get("_http"):
                log_event(_EV_TASK_SUBMIT_FAIL,
                          "이 답변은 전달되지 않았다 — lease 만료 뒤 다시 제안된다",
                          level="ERROR", task=task_id, attempt=2,
                          http=res.get("_http"), detail=str(res.get("error") or ""),
                          answer_chars=len(answer or ""),
                          dur_ms=int((time.monotonic() - _t_task) * 1000))
                return False
        if res.get("_http"):
            log_event(_EV_TASK_SUBMIT_FAIL, "제출 실패", level="ERROR", task=task_id,
                      attempt=1, http=res.get("_http"), detail=str(res.get("error") or ""),
                      answer_chars=len(answer or ""),
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            return False
        _gl = res.get("glossary") or {}
        # 한 건의 **종결**. `dur_ms` 는 전달→제출 완료 전체이고, 그 안의 AI 호출 몫은 `ai.ok`
        # 줄이 따로 갖고 있다 — 두 값의 차가 곧 러너·서버가 쓴 시간이다.
        log_event(_EV_TASK_SUBMIT_OK, "제출 완료", task=task_id, runtime=run_kind,
                  delivered=bool(res.get("delivered_to_conversation")),
                  answer_chars=len(answer or ""), has_title=bool(title),
                  glossary=(_gl or None),
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        if binding and ok and res.get("delivered_to_conversation"):
            try:
                binding.commit(res.get("conversation_session"))
            except OSError:
                log_event("task.session.save_failed", "답변은 전달됐지만 세션 저장에 실패했습니다.", level="WARN", task=task_id)
        return True
