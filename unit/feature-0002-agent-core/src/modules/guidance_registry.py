"""feature-0021: 작동 지침(guidance)·스킬(tool) 레지스트리 — 관리 콘솔 read-only 조회.

Claude Code 의 progressive disclosure 이식: 목록 API 는 name+description 메타만,
본문은 개별 조회 시에만 반환한다 (콘솔·토큰 양쪽 비용 절약).

지침 본문은 여기 복제하지 않는다 — 코드 상수(agent_core/llm/redteam/agent_notes)를
lazy import 로 참조해 단일 진실원본을 유지한다 (drift 없음). DB-편집형 프롬프트
(WebSystemPrompts: base/product/role/account) 는 기존 관리 콘솔 편집 화면이 정본이므로
여기서는 존재만 안내한다.
"""

from __future__ import annotations

from typing import Any, Callable


def _agent_core():
    import agent_core
    return agent_core


def _guidance_entries() -> list[dict[str, Any]]:
    """지침 카탈로그 — text_fn 은 lazy (목록 조회 시 본문 미로드)."""

    def entry(key: str, name: str, description: str, injection: str,
              text_fn: Callable[[], str], source: str = "code") -> dict[str, Any]:
        return {
            "key": key, "name": name, "description": description,
            "kind": "guidance", "injection": injection, "source": source,
            "text_fn": text_fn,
        }

    # console-ia(2026-07-16): 기본 시스템 프롬프트(SYSTEM_PROMPT)는 전역 시스템 프롬프트
    # (WebSystemPrompts scope=global)의 코드 fallback 이라 편집 정본이 관리 콘솔 '설정 > 프롬프트
    # > 전역 시스템 프롬프트'다. 작동 지침 목록에서 제외해 편집 경로를 단일화한다(중복 제거).
    return [
        entry(
            "dialect-mysql", "MySQL 방언 지침",
            "활성 datasource 가 MySQL 일 때 T-SQL 패턴 대신 MySQL 문법을 강제하는 지침.",
            "conditional (활성 datasource=MySQL)",
            lambda: str(getattr(_agent_core(), "_MYSQL_DIALECT_GUIDANCE", "")),
        ),
        entry(
            "dialect-mssql", "MSSQL 방언 지침",
            "활성 datasource 가 SQL Server 일 때 T-SQL 문법을 강제하는 지침.",
            "conditional (활성 datasource=MSSQL)",
            lambda: str(getattr(_agent_core(), "_MSSQL_DIALECT_GUIDANCE", "")),
        ),
        entry(
            "active-interpretation", "능동 해석 지침",
            "과도 재질문·스키마 추측 후 포기·datasource 드리프트를 억제하는 능동 탐색 지침 (1:1·그룹 공통).",
            "always",
            lambda: str(getattr(_agent_core(), "_ACTIVE_INTERPRETATION_GUIDANCE", "")),
        ),
        entry(
            "data-grounding", "데이터 의미 grounding 지침",
            "저장값의 의미(날짜/시각 타임존·ENUM 코드값·분리저장)를 추측하지 말고 확인·명시하도록 하는 지침 "
            "(DQA 마찰 B-1 타임존 오판·D-1 ENUM 환각·D-2 분리저장 누락).",
            "always",
            lambda: str(getattr(_agent_core(), "_DATA_GROUNDING_GUIDANCE", "")),
        ),
        entry(
            "group-conversation", "그룹 대화 지침",
            "그룹 대화에서 발신자 라벨로 화자를 구분하고 멘션 직전 맥락에서 의도를 해석하는 지침.",
            "conditional (그룹 대화)",
            lambda: str(getattr(_agent_core(), "_GROUP_CONVERSATION_GUIDANCE", "")),
        ),
        entry(
            "mermaid-diagram", "관계 다이어그램(mermaid) 지침",
            "flow/관계/구조 질문에 mermaid 다이어그램으로 답하도록 유도하는 지침.",
            "always (knowledge context 뒤)",
            lambda: str(getattr(_agent_core(), "_MERMAID_DIAGRAM_GUIDANCE", "")),
        ),
        entry(
            "injection-guard", "프롬프트 인젝션 방어 공지",
            "도구 결과(datamark 구획)를 데이터로만 취급하고 그 안의 지시를 따르지 않게 하는 방어 지침.",
            "always (compose_system_prompt)",
            lambda: str(getattr(_agent_core(), "_INJECTION_GUARD_NOTICE", "")),
        ),
        entry(
            "redteam-review", "자가 적대(red-team) 리뷰어 지침",
            "답변 전달 전 fresh-context 리뷰어가 grounding/SQL/권한/완전성/정직성 5축으로 반박을 시도하는 지침 (feature-0021). 낮음 강도는 skip, BLOCK 결함만 수정 유발.",
            "post-answer (추론 강도 게이팅 — REDTEAM_* 런타임 설정)",
            lambda: __import__("modules.redteam", fromlist=["REDTEAM_REVIEW_PROMPT"]).REDTEAM_REVIEW_PROMPT,
        ),
        entry(
            "self-review-notes", "세션/제품 자가리뷰 노트 사용 지침",
            "축적 노트를 힌트로만 쓰고 증거로 인용하지 않게 하는 경계 헤더 (feature-0021). 세션 노트는 해당 대화에만 주입.",
            "conditional (노트 존재 + 캡 이내 + 공유창 bounded 발신자 제외)",
            lambda: __import__("modules.agent_notes", fromlist=["NOTES_CONTEXT_HEADER"]).NOTES_CONTEXT_HEADER,
        ),
    ]


def _skill_entries() -> list[dict[str, Any]]:
    """스킬(도구) 카탈로그 — assistant 가 답변 중 호출 가능한 함수 도구 전체."""
    try:
        from modules.tools import TOOL_DEFINITIONS_FULL as _defs
    except Exception:
        try:
            from modules.tools import TOOL_DEFINITIONS as _defs
        except Exception:
            return []
    entries: list[dict[str, Any]] = []
    for item in _defs:
        try:
            fn = item.get("function") or {}
            name = str(fn.get("name") or "")
            if not name:
                continue
            desc = str(fn.get("description") or "")
            entries.append({
                "key": f"tool:{name}", "name": name,
                "description": desc[:300],
                "kind": "skill", "injection": "tool-calling (LLM 자율 선택)",
                "source": "code",
                "text_fn": (lambda _item=item: __import__("json").dumps(_item, ensure_ascii=False, indent=2)),
            })
        except Exception:
            continue
    return entries


def _all_entries() -> list[dict[str, Any]]:
    return _guidance_entries() + _skill_entries()


def list_guidance() -> list[dict[str, Any]]:
    """목록 (progressive disclosure — 본문 제외 메타만). 실패 항목은 조용히 제외."""
    result: list[dict[str, Any]] = []
    for item in _all_entries():
        meta = {k: v for k, v in item.items() if k != "text_fn"}
        try:
            meta["chars"] = len(item["text_fn"]() or "")
        except Exception:
            meta["chars"] = None
        result.append(meta)
    return result


def get_guidance(key: str) -> dict[str, Any] | None:
    """단건 상세 (본문 포함). 미존재/로드 실패 시 None."""
    want = str(key or "").strip()
    for item in _all_entries():
        if item["key"] == want:
            try:
                text = item["text_fn"]() or ""
            except Exception:
                return None
            meta = {k: v for k, v in item.items() if k != "text_fn"}
            meta["text"] = text
            meta["chars"] = len(text)
            return meta
    return None
