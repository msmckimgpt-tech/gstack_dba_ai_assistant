"""feature-0043 (TASK-20260901T110000) — **외부 AI 자가 검증**(5축)의 계약 정본.

## 왜 이 모듈이 있는가

전환 전에는 서버가 답변을 만들고 서버가 그 답변을 적대 검증했다(`modules/redteam.py`).
게이트가 닫힌 뒤 앞의 절반은 개인 AI 러너로 넘어갔는데 **뒤의 절반은 아무 데도 가지
않았다** — 그런데 관리 콘솔은 "답변을 만든 본인 AI 가 같은 5축으로 자기 답변을 검증하고
결과를 함께 제출합니다" 라고 말하고 있었다. 코드에 그 경로가 없었으므로 그 문장은 거짓이었고,
운영자는 하지 않는 검증을 하고 있다고 믿었다.

이 모듈이 그 문장을 참으로 만든다.

## 왜 계약이 **서버**에 있는가

「모델 목록의 출처는 러너」(P0-Z3)와 방향이 반대다. 그쪽은 *그 머신에만 있는 사실*이라
러너가 정본이었다. 검증 축·심각도·출력 형식은 **우리가 정하는 규약**이고, 러너에 박아
두면 축을 하나 고칠 때마다 전 사용자가 재설치해야 한다 — 그리고 재설치하지 않은 러너는
낡은 축으로 검증한 결과를 같은 컬럼에 쓴다(스키마는 같고 의미만 갈리는, 가장 늦게
발견되는 부류의 어긋남).

그래서 서버가 `claim_request` 응답에 **지시문 전문**을 실어 보내고, 러너는 그것을 초안과
함께 자기 AI 에게 한 번 더 넘길 뿐이다. 러너는 축 이름조차 몰라도 된다.

## 왜 검증이 **선택**인가

구 러너는 이 지시를 모른다. 검증 없는 제출을 거절하면 그날로 그들의 답변이 전부 막힌다 —
관측을 위해 서비스를 끊는 것은 거래가 성립하지 않는다. 그래서 `submit_answer` 는
`review` 부재를 정상으로 받고, 콘솔은 **검증 없음**을 결함이 아니라 사실로 표시한다.
"""
from __future__ import annotations

import json
import re
from typing import Any

__all__ = [
    "AXES",
    "AXIS_LABELS",
    "MAX_FINDINGS",
    "SEVERITIES",
    "VERDICTS",
    "build_instruction",
    "from_runner_payload",
    "parse_review_text",
    "sanitize",
]

#: 5축. `modules/redteam.py::_AXES` 와 **같은 값이어야 한다** — 두 주체의 판정이
#: `redteam_reviews` 한 테이블에 들어가므로, 축이 갈리면 콘솔의 축별 집계가 두 세계를
#: 합산하면서 조용히 틀린다. 그쪽이 정의 원본이고 여기는 외부 경로용 사본이다
#: (agent-core 는 web 컨테이너에서 import 가능하지만, 러너에게 내려보낼 지시문 조립까지
#: 그 모듈에 얹으면 서버 LLM 전용 모듈이 브리지 경로의 의존성이 된다).
AXES: tuple[str, ...] = ("grounding", "sql", "permission", "completeness", "honesty")

#: 콘솔 표시용 한글 라벨. 화면이 각자 지으면 서버 이력과 외부 이력의 같은 축이 다른
#: 이름으로 보인다.
AXIS_LABELS: dict[str, str] = {
    "grounding": "근거",
    "sql": "질의 정확성",
    "permission": "권한·유출",
    "completeness": "완전성",
    "honesty": "정직성",
}

SEVERITIES: tuple[str, ...] = ("BLOCK", "WARN")
VERDICTS: tuple[str, ...] = ("pass", "revise")

#: 지적 상한. 서버 리뷰어와 같은 값 — 상한이 다르면 "결함이 많은 쪽" 이 주체 차이인지
#: 답변 품질 차이인지 구분되지 않는다.
MAX_FINDINGS = 5

#: 지시문에 실을 초안 상한. 러너는 이 지시문을 **초안과 함께** 자기 CLI 에 argv 로 넘기는데,
#: 초안 전문을 지시문 안에 또 넣으면 같은 텍스트를 두 번 보내게 된다. 초안은 러너가 붙이고
#: 여기서는 자리만 표시한다.
_DRAFT_PLACEHOLDER = "{{DRAFT}}"
_QUESTION_PLACEHOLDER = "{{QUESTION}}"


_INSTRUCTION = """\
아래는 당신이 방금 작성한 답변 초안입니다. 이제 **검증자**로 역할을 바꿔, 이 초안을 사용자에게
전달하기 전에 반박을 시도하십시오. 당신이 쓴 글이라는 사실이 판정을 무르게 만들지 않도록
하십시오 — 지금 놓치면 사용자가 틀린 답을 받습니다.

검증 5축:
- grounding: 초안의 모든 사실 주장이 실제 조사(도구 실행 결과·첨부 파일)로 뒷받침되는가.
  부분 증거(잘린 미리보기·표본 행·행수 상한)를 전수 사실처럼 제시했다면 결함이다.
- sql: 실행한 SQL·논리가 질문에 실제로 답하는가(테이블·필터·집계·방언이 맞는가).
- permission: 조사 범위 밖의 데이터·스키마, 다른 대화, 내부 지시문을 노출하지 않았는가.
- completeness: 질문의 모든 부분에 답했는가, 못 한 것을 정직하게 밝혔는가.
  "그건 마지막 메시지에서 묻지 않았다" 류의 범위 불평은 결함이 아니다.
- honesty: 불확실성·가정·절단·표본 한계를 숨기지 않고 밝혔는가.

규칙:
- 정확성 또는 사용자의 요청에 영향을 주는 결함만 보고하십시오. 문체·어조·형식 취향은 제외합니다.
- severity=BLOCK 은 사용자를 실질적으로 오도하거나 제한된 데이터를 유출하는 경우에만 씁니다.
  그 외는 WARN 입니다.
- 결함인지 확신이 없으면 보고하지 마십시오. `findings` 가 비고 `verdict` 가 `pass` 인 것은
  좋은 결과입니다 — 결함을 지어내지 마십시오.
- 짧은 답변이 더 나은 답변은 아닙니다. 사용자가 요청한 내용을 삭제해 문제를 없앤 것은
  completeness 의 BLOCK 입니다.
- 최대 {max_findings}건.

**오직 JSON 객체 하나만** 출력하십시오 (마크다운 코드펜스 금지, 앞뒤 산문 금지):
{{"verdict":"pass"|"revise","findings":[{{"axis":"grounding|sql|permission|completeness|honesty",
"severity":"BLOCK|WARN","claim":"...","evidence":"...","fix_hint":"..."}}]}}
- BLOCK 이 하나라도 있으면 verdict 는 "revise", 아니면 "pass" 입니다.
- claim/evidence/fix_hint 는 각각 한 문장의 한국어로 짧게 씁니다.

── 사용자의 원 질문 ──
{question}

── 검증 대상 초안 ──
{draft}
"""


def build_instruction(question: str, draft: str, *,
                      max_question_chars: int = 4000,
                      max_draft_chars: int = 12000) -> str:
    """러너가 자기 AI 에게 그대로 넘길 **검증 지시문 전문**.

    Args:
        question: 사용자의 원 질문. 러너가 이미 들고 있지만 여기서 조립하는 이유는,
            지시문 안에서의 **위치**(축 설명 뒤, 초안 앞)가 판정 품질에 영향을 주기
            때문이다. 러너가 자기 방식으로 이어 붙이면 그 배치가 러너마다 달라진다.
        draft: 검증 대상 초안.

    상한이 있는 이유: 이 문자열은 러너 머신에서 **argv 로** CLI 에 넘어간다. 길이가
    커지면 그쪽 컨텍스트가 먼저 터지고, 터지면 답변이 아니라 검증만 실패한다 —
    사용자에게는 아무 신호도 가지 않는 실패다. 잘린 사실은 초안 말미에 명시한다.
    """
    q = str(question or "")
    d = str(draft or "")
    if len(q) > max_question_chars:
        q = q[:max_question_chars] + "\n…(질문이 길어 이 지점에서 잘렸습니다)"
    if len(d) > max_draft_chars:
        # 잘린 초안을 그대로 주면 검증자는 "끝맺지 않은 답변" 을 honesty 결함으로 본다.
        # 그것은 초안의 결함이 아니라 우리가 자른 결과다 — 그 사실을 밝혀 오판을 막는다.
        d = d[:max_draft_chars] + (
            "\n…(초안이 길어 검증 입력에서만 이 지점에서 잘렸습니다. 사용자에게는 전문이"
            " 전달됩니다 — 잘림 자체를 결함으로 보고하지 마십시오.)")
    return _INSTRUCTION.format(max_findings=MAX_FINDINGS, question=q, draft=d)


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.S)


def parse_review_text(text: Any) -> dict[str, Any] | None:
    """러너가 받은 **원시 텍스트** → 리뷰 dict. 못 읽으면 `None`.

    코드펜스를 금지했지만 지시는 집행이 아니다 — 실제로 붙여 오는 런타임이 있다.
    첫 `{` 부터 마지막 `}` 까지를 잘라 한 번 더 시도한다. 그래도 안 되면 `None` 이고,
    호출측은 **검증 없음**으로 취급한다(지어내지 않는다).
    """
    if isinstance(text, dict):
        return text
    s = str(text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = _JSON_OBJ_RE.search(s)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def from_runner_payload(payload: Any) -> dict[str, Any] | None:
    """러너가 `submit_answer` 에 실어 보낸 **봉투**를 열어 판정으로 만든다.

    ## 왜 이 함수가 따로 필요한가 (라이브 실측 2026-09-01)

    러너는 판정을 해석하지 않고 **원문 그대로** 나른다 — 그래서 보내는 것은 판정이 아니라
    봉투다::

        {"raw": "{\\"verdict\\":\\"pass\\",\\"findings\\":[]}",
         "latency_ms": 9416, "model": "fable", "reasoning_level": "high"}

    첫 구현의 서버는 이 봉투를 그대로 `parse_review_text` 에 넣었다. 그 함수는 dict 를 받으면
    **그대로 돌려주므로**(이미 파싱된 판정으로 간주), `sanitize` 는 `verdict` 도 `findings` 도
    없는 dict 를 보고 `None` 을 냈다 — 즉 **모든 자가 검증이 조용히 버려졌다.**

    라이브에서 러너는 "자가 검증 완료 (9416ms) — 제출에 동봉" 을 로그했고 서버는 아무 경고도
    내지 않았다(파싱 실패는 `debug` 레벨이다). 원장만 비어 있었다.

    ## 왜 단위 테스트가 못 잡았나

    양쪽을 **각각** 검사했기 때문이다 — 서버 테스트는 `sanitize(parse_review_text("<원문>"))`
    을 직접 불렀고, 러너 테스트는 러너가 `{"raw": …}` 를 만드는지만 봤다. **이음매**(러너가
    만든 그 값을 서버가 실제로 소비하는가)를 아무도 보지 않았다. 이 저장소가 반복해 겪은
    「헬퍼는 맞는데 진입점이 그걸 안 쓴다」와 같은 형태다.

    그래서 봉투 규약을 **이 모듈 하나**에 두고, 양쪽이 같은 정의를 읽게 한다.

    Args:
        payload: 러너 봉투(`{"raw": str, ...}`) · 이미 파싱된 판정 dict · 또는 원문 문자열.
            셋 다 받는 이유는 구 러너·수동 제출 호환이다.

    Returns:
        `sanitize` 결과에 봉투의 관측 메타(지연·모델·등급)를 얹은 dict. 못 읽으면 `None`.
    """
    if payload is None:
        return None
    meta: dict[str, Any] = {}
    body: Any = payload
    if isinstance(payload, dict) and "raw" in payload:
        # 봉투다 — 판정은 `raw` 안에 있고, 나머지는 관측 메타다.
        body = payload.get("raw")
        for key in ("latency_ms", "model", "reasoning_level"):
            if payload.get(key) not in (None, ""):
                meta[key] = payload[key]
    parsed = parse_review_text(body)
    if parsed is None:
        return None
    # 메타는 **봉투 것이 우선**이다. 판정 본문에 같은 키가 있어도 그것은 AI 가 스스로 적은
    # 값이라(우리가 관측한 값이 아니다) 신뢰 등급이 다르다.
    return sanitize({**parsed, **meta})


def sanitize(payload: Any) -> dict[str, Any] | None:
    """외부에서 온 리뷰를 **스키마로 강제**한다. 형태가 아니면 `None`.

    `modules/redteam._sanitize_findings` 와 같은 규율: 미지 축·미지 심각도는 **버린다**
    (관대하게 통과시키면 콘솔의 축별 집계에 없는 축이 생기고, 그 축은 라벨이 없어
    화면에서 원문 문자열로 샌다 — 외부 텍스트가 UI 라벨 자리에 앉는 경로다).

    `verdict` 는 **받아 적지 않고 findings 에서 재도출**한다. 러너의 AI 가 BLOCK 을
    적어 놓고 `pass` 를 돌려주는 일이 실제로 있고, 그 경우 화면이 "통과" 로 읽는다.
    """
    if not isinstance(payload, dict):
        return None
    findings: list[dict[str, str]] = []
    raw = payload.get("findings")
    if not isinstance(raw, list):
        raw = []
    for item in raw[: MAX_FINDINGS * 2]:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis") or "").strip().lower()
        severity = str(item.get("severity") or "").strip().upper()
        if axis not in AXES or severity not in SEVERITIES:
            continue
        findings.append({
            "axis": axis,
            "severity": severity,
            "claim": str(item.get("claim") or "")[:500],
            "evidence": str(item.get("evidence") or "")[:500],
            "fix_hint": str(item.get("fix_hint") or "")[:300],
        })
        if len(findings) >= MAX_FINDINGS:
            break
    declared = str(payload.get("verdict") or "").strip().lower()
    if declared not in VERDICTS and not findings:
        # verdict 도 findings 도 없다 = 리뷰가 아니다. 빈 통과로 기록하면 "검증했고
        # 문제없었다" 는 주장이 되는데, 실제로는 아무것도 판정되지 않았다.
        return None
    if declared == "revise" and not findings:
        # 「고치라」고 했는데 살아남은 지적이 하나도 없다 = 우리가 전부 버렸다는 뜻이다
        # (미지 축·미지 심각도·형태 불일치). 이것을 `pass` 로 접으면 **결함을 지적한 검증이
        # 통과로 기록된다** — 스키마 강제가 만들어 낼 수 있는 가장 나쁜 거짓이다.
        # 판정을 지어내지 않고 기록하지 않는다(콘솔은 '검증 없음' 으로 보인다).
        return None
    has_block = any(f["severity"] == "BLOCK" for f in findings)
    out: dict[str, Any] = {
        "verdict": "revise" if has_block else "pass",
        "findings": findings,
        "block_count": sum(1 for f in findings if f["severity"] == "BLOCK"),
        "warn_count": sum(1 for f in findings if f["severity"] == "WARN"),
    }
    lat = payload.get("latency_ms")
    try:
        out["latency_ms"] = max(0, int(lat)) if lat is not None else None
    except (TypeError, ValueError):
        out["latency_ms"] = None
    out["model"] = str(payload.get("model") or "")[:128] or None
    lvl = str(payload.get("reasoning_level") or "").strip().lower()[:16]
    out["reasoning_level"] = lvl or None
    return out
