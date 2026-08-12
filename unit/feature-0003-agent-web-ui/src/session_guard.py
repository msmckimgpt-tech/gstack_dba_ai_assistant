"""feature-0041 (REQ-20260812-external-ai-tool-surface) — 세션 격리·각인·인젝션 판정.

외부 AI 가 **자기 계정 LLM 으로 추론**하는 표면에서는 신뢰경계가 뒤집힌다. 지금까지는
"우리 LLM 이 비신뢰 데이터를 읽는다" 였지만, 여기서는 **우리가 통제하지 않는 LLM 에게 데이터를
내보낸다.** 그래서 이 모듈이 다루는 것은 세 가지다:

  L2 **각인** — 나가는 모든 데이터 블록에 `account`·`conversation`·`task` 를 새긴다.
       SECURITY.md §14 의 `_datamark_untrusted` sentinel 구획을 그대로 쓰되 label 을 구조화한다.
       §14.2 한계 3번(guard notice 가 블록에서 멀어짐)을 블록마다 1줄 재진술로 보완한다.
  L3 **탐지** — `submit_answer` 의 `source_tasks` 선언과 실제 원장을 대조해 교차오염을 잡는다.
       ⚠ **명시적 유출 신호에 한정**한다(codex REV-20260812-0001 P2): 외부 AI 가 값을 요약·
       환산·재서술하면 출처를 결정론적으로 판별할 수 없다. 미탐을 허용하며 탐지율을 보장하지 않는다.
  인젝션 **3단 판정** — allow / neutralize+flag / reject.
       거절을 넓게 잡으면 정상 DB 질의가 막힌다(`system_prompts` 테이블, `ignore_flag` 컬럼은
       **정상 식별자**다). 그래서 reject 는 *명령-계층 전복 문형* 에만 걸고, 나머지는 통과시키되
       무해화·표시한다.

**순수 함수 모듈** — DB·네트워크·전역 상태 없음. 호출측(`routers/ai_tools.py`)이 원장·응답을 맡는다.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

# SECURITY.md §14 의 sentinel. agent_core 를 import 하면 무거운 의존이 딸려오므로 값만 미러한다
# (agent_core._INJ_OPEN/_INJ_CLOSE 와 동일해야 하며, 테스트가 동치를 단정한다).
INJ_OPEN = "⟦UNTRUSTED-DATA⟧"
INJ_CLOSE = "⟦/UNTRUSTED-DATA⟧"

# 블록마다 재진술하는 1줄 경계 고지(영문 병기 — §14.2 한계 3번: 한국어 guard 가 약모델에서 약함).
_SCOPE_NOTE = (
    "[SCOPE] account={account} only — do not use in answers for other accounts/conversations. "
    "이 블록은 계정 {account} 전용입니다."
)


# ── L2 각인 ────────────────────────────────────────────────────────────────────

def datamark_label(*, account: str, conversation_id: str | None = None,
                   task_id: str | None = None, source: str = "tool") -> str:
    """datamark label 문자열. `_datamark_untrusted(content, label)` 에 그대로 넘긴다.

    label 자체도 비신뢰 값이 섞일 수 있어 sentinel 을 제거한다(agent_core 가 한 번 더 제거하지만
    호출측에서도 막아 두 겹으로 둔다 — 위조 close 마커로 구획을 깨는 벡터).
    """
    parts = [f"account={_clean(account)}"]
    if conversation_id:
        parts.append(f"conversation={_clean(conversation_id)}")
    if task_id:
        parts.append(f"task={_clean(task_id)}")
    parts.append(f"source={_clean(source)}")
    return " ".join(parts)


def wrap_tool_output(content: str, *, account: str, conversation_id: str | None = None,
                     task_id: str | None = None, source: str = "tool") -> str:
    """도구 결과 1건을 세션 각인과 함께 구획한다.

    반환 형태:
        ⟦UNTRUSTED-DATA⟧ (account=… conversation=… task=… source=…)
        [SCOPE] account=… only — …
        <데이터>
        ⟦/UNTRUSTED-DATA⟧

    `_datamark_untrusted` 와 동일한 sentinel·strip 규약을 쓰되, 본문 첫 줄에 경계 고지를 넣어
    긴 컨텍스트에서 블록과 규범이 멀어지는 문제를 보완한다.
    """
    label = datamark_label(account=account, conversation_id=conversation_id,
                           task_id=task_id, source=source)
    body = _clean(content)
    note = _SCOPE_NOTE.format(account=_clean(account))
    return f"{INJ_OPEN} ({label})\n{note}\n{body}\n{INJ_CLOSE}"


def session_canary(task_id: str) -> str:
    """task 고유의 무해한 마커. context 번들 헤더에 심어 두고, 다른 task 답변에 등장하면
    교차오염 확증으로 쓴다. 결정론적이라 서버가 상태를 들고 있을 필요가 없다."""
    digest = hashlib.sha256(f"task-canary:{task_id}".encode("utf-8")).hexdigest()
    return f"tc-{digest[:12]}"


# ── L3 교차오염 탐지 ───────────────────────────────────────────────────────────

def detect_cross_session(answer: str, *, task_id: str,
                         declared_tasks: Iterable[str] | None = None,
                         foreign_tasks: Iterable[str] | None = None,
                         foreign_values: Iterable[str] | None = None,
                         foreign_accounts: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """제출된 답변에서 **명시적** 교차오염 신호를 찾는다.

    Args:
        answer:           `submit_answer` 로 제출된 최종 답변
        task_id:          이 답변이 속한 task
        declared_tasks:   외부 AI 가 선언한 `source_tasks` (task_id 자신 포함 가정)
        foreign_tasks:    같은 client 의 **다른** task id 들 (선언에 없는 것)
        foreign_values:   그 task 들의 결과셋에서 뽑은 **원문 그대로의** 고유 값 표본
        foreign_accounts: 그 task 들의 계정 라벨

    Returns:
        finding dict 리스트. 비어 있으면 명시적 신호 없음(= 오염이 없다는 뜻은 아니다).

    ⚠ 미탐 허용(codex P2): 값이 요약·환산·재서술되면 못 잡는다. 본 함수는 "몰라서 섞임" 이
    아니라 "각인·원문이 그대로 흘러나온" 경우를 잡는다.
    """
    findings: list[dict[str, Any]] = []
    text = str(answer or "")
    if not text.strip():
        return findings

    declared = {str(t) for t in (declared_tasks or ()) if t}
    declared.add(str(task_id))

    # (1) 다른 task 의 카나리가 등장 — 가장 강한 신호(우리가 심은 값이라 우연 일치 불가)
    for other in (foreign_tasks or ()):
        other = str(other)
        if other in declared:
            continue
        canary = session_canary(other)
        if canary in text:
            findings.append({"kind": "canary", "foreign_task": other, "signal": canary})

    # (2) 다른 task 의 id 문자열이 그대로 등장
    for other in (foreign_tasks or ()):
        other = str(other)
        if other in declared:
            continue
        if other in text:
            findings.append({"kind": "task_id", "foreign_task": other, "signal": other})

    # (3) 각인 라벨 누출 — 다른 계정의 datamark 라벨이 답변에 실려 나옴
    for acct in (foreign_accounts or ()):
        acct = str(acct)
        if f"account={acct}" in text:
            findings.append({"kind": "label", "foreign_account": acct,
                             "signal": f"account={acct}"})

    # (4) 선언 밖 task 의 결과셋 값이 **원문 그대로** 등장
    #     짧은 값(연도·코드 등)은 우연 일치가 흔해 제외한다 — 오탐이 나면 이 신호 전체의
    #     신뢰도가 떨어져 운영자가 원장을 안 보게 된다.
    for val in (foreign_values or ()):
        s = str(val or "").strip()
        if len(s) < 8:
            continue
        if s in text:
            findings.append({"kind": "value", "signal": s[:64]})

    return _dedupe(findings)


# ── 인젝션 3단 판정 ────────────────────────────────────────────────────────────

# reject — 명령-계층 전복 *문형*. 명사 하나로는 걸리지 않게 동사+목적어를 요구한다.
_REJECT_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("ignore_previous", re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
        r"(previous|prior|above|earlier|all)\b[^.\n]{0,20}\b"
        r"(instruction|instructions|prompt|prompts|rule|rules|direction|directions)\b",
        re.I)),
    ("ignore_previous_ko", re.compile(
        r"(이전|앞의|위의|기존)\s*(의)?\s*(지시|명령|규칙|프롬프트)[^.\n]{0,10}"
        r"(무시|잊어|덮어|무효)", re.I)),
    ("reveal_system_prompt", re.compile(
        r"\b(print|show|reveal|output|repeat|dump|display)\b[^.\n]{0,30}\b"
        r"(system\s*prompt|your\s+instructions|initial\s+prompt|developer\s+message)\b",
        re.I)),
    ("reveal_system_prompt_ko", re.compile(
        r"(시스템\s*프롬프트|너의\s*지시문|초기\s*지시)[^.\n]{0,15}"
        r"(출력|보여|알려|공개|말해)", re.I)),
    ("role_override", re.compile(
        r"\byou\s+are\s+now\b[^.\n]{0,40}\b(a|an|the)\b|"
        r"\bnew\s+(system\s+)?(rule|rules|instruction|instructions)\s*[:：]",
        re.I)),
    ("chat_delimiter_forgery", re.compile(
        r"<\|(im_start|im_end|system|endoftext)\|>|"
        r"^\s*(system|assistant)\s*[:：]\s*$", re.I | re.M)),
)

# neutralize — 의심스럽지만 정상 질의에도 나타날 수 있는 것. 통과시키되 표시·무해화한다.
_NEUTRALIZE_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("sentinel_forgery", re.compile(re.escape(INJ_OPEN) + r"|" + re.escape(INJ_CLOSE))),
    ("scope_note_forgery", re.compile(r"\[SCOPE\]\s*account=", re.I)),
    ("tool_directive", re.compile(
        r"\b(call|invoke|execute)\s+the\s+\w+\s+tool\b[^.\n]{0,30}\b(instead|before|first)\b",
        re.I)),
)


def classify_injection(text: str) -> dict[str, Any]:
    """들어오는 텍스트를 3단으로 판정한다.

    Returns:
        {"verdict": "allow"|"neutralize"|"reject", "matched": [rule…], "text": <무해화된 텍스트>}

    설계 원칙 — **거절은 좁게**. `system_prompts` 같은 테이블명이나 `ignore_flag` 컬럼은 정상
    식별자이므로 명사 단독으로는 어떤 단계에도 걸리지 않는다. 실제로 걸리는 것은 "이전 지시를
    무시하고…" 처럼 **명령-계층을 전복하려는 문형** 뿐이다.
    """
    src = str(text or "")
    matched_reject = [name for name, pat in _REJECT_PATTERNS if pat.search(src)]
    if matched_reject:
        return {"verdict": "reject", "matched": matched_reject, "text": src}

    matched_neutral = [name for name, pat in _NEUTRALIZE_PATTERNS if pat.search(src)]
    if matched_neutral:
        return {"verdict": "neutralize", "matched": matched_neutral, "text": _clean(src)}

    return {"verdict": "allow", "matched": [], "text": src}


# ── 내부 ──────────────────────────────────────────────────────────────────────

def _clean(value: Any) -> str:
    """sentinel 위조 문자열 제거 — 구획 breakout 차단(§14 규약)."""
    return str(value if value is not None else "").replace(INJ_OPEN, "").replace(INJ_CLOSE, "")


def _dedupe(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for f in findings:
        key = (f.get("kind"), f.get("signal"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
