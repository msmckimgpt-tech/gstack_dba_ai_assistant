"""TASK-20260714-attach-grounding: 첨부 리뷰 섹션 ↔ 전역 grounding 규칙 모순 제거 검증.

관측된 마찰(대화 20260714 자기정정 "첨부 파일과 실제 DB를 비교하니 심각한 환각이 있었습니다"):
전역 SYSTEM_PROMPT 는 이미 "COMPARING an attachment against the live DB: fetch BOTH sides ...
Never narrate the current-DB side from assumption or memory" 규칙을 갖는다(FR-partial-evidence,
병합 PR #793). 그러나 첨부 섹션 INSTRUCTION 은 "do NOT run execute_sql ... unless the user explicitly
asks" 로 그 규칙과 **직접 모순**해 실 DB 미검증 단언(환각)을 유발했다.

본 테스트는 `_build_attachment_context_section` 이 주입하는 지시문이:
  (1) 모순되던 무조건 억제 문구를 제거했고,
  (2) 순수 코드 리뷰(내부 품질)는 DB 불필요를 유지하며,
  (3) 실 DB 상태 주장은 전역 규칙에 위임(검증 선행)하도록
규율함을 소스 수준에서 검증한다(DB 없이 실행 — test_attachment_line_numbers 하네스 동형).
"""
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

_SRC = (SRC_ROOT / "agent_core.py").read_text(encoding="utf-8")


def test_contradictory_suppression_removed():
    # 전역 grounding 규칙과 모순되던 무조건 억제 문구가 제거되어야 한다(환각 유발 지시 제거).
    # (동적 _build_attachment_context_section INSTRUCTION)
    assert (
        "answer about it directly and do NOT "
        "run execute_sql against your own database unless the user explicitly asks"
    ) not in _SRC


def test_static_attached_files_suppression_removed():
    # REV-20260714T221500 (적대 패널 MAJOR): 정적 SYSTEM_PROMPT `## ATTACHED FILES` 섹션에
    # 남아 있던 동일 억제 + "takes precedence" 도 제거돼야 grounding 회귀가 완전히 닫힌다.
    # (동적본만 고치고 이 정적본을 남기면 "takes precedence" 가 verify 지시를 이긴다.)
    assert (
        "Do NOT run execute_sql against your own database unless the user explicitly "
        "asks you to run or validate the query there"
    ) not in _SRC
    assert 'take precedence over the general "query the database" guidance' not in _SRC


def test_static_attached_files_section_delegates_to_grounding():
    # 정적 ATTACHED FILES 섹션도 실 DB 관계 주장은 전역 grounding 규칙에 위임해야 한다(동적본과 동형).
    assert "Focusing on the attached files does NOT override that grounding rule" in _SRC
    assert "does not by itself require execute_sql" in _SRC  # 순수 리뷰 보존(과차단 회귀 방지)


def test_live_db_claim_defers_to_global_rule():
    # 실 DB 상태 주장은 검증 선행 + 전역 규칙("COMPARING an attachment against the live DB")에 위임.
    # (_SRC 는 소스 텍스트 — 인접 문자열 리터럴이 개행/들여쓰기로 분할되므로 토큰 단위로 검증.)
    assert "MUST verify it" in _SRC
    assert "against the live DB first" in _SRC
    assert "COMPARING an attachment against the live DB" in _SRC  # 전역 규칙 참조 + 규칙 자체 존속


def test_no_ungrounded_db_claims_from_memory():
    # 기억에 근거한 실 DB 관계 단언 금지.
    assert "from memory" in _SRC
    assert "do NOT infer or assert" in _SRC


def test_pure_review_still_no_db_required():
    # 파일 내부 품질 리뷰는 여전히 DB 불필요 — 순수 리뷰 경로 보존(과차단 회귀 방지).
    assert "Reviewing the file's INTERNAL quality" in _SRC
    assert "not by itself require execute_sql" in _SRC


def test_global_grounding_rule_still_present():
    # 위임 대상인 전역 규칙(FR-partial-evidence, 병합됨)이 base 에 존속해야 위임이 유효하다.
    assert "fetch BOTH sides before comparing" in _SRC
    assert "Never narrate the current-DB side from assumption or memory" in _SRC


# --- CHG-20260714T221500-attach-case-insensitive-grounding (라이브 실측 잔존 false-missing 봉인) ---
# 라이브 실측(배포본 244e6bec 직접 재현)에서 gunzlog 절단 목록의 유일한 CamelCase 테이블
# `LoginEventLog`(첨부 162행 활성 TRUNCATE 실재)가 "초기화 쿼리에 없는 누락"으로 오판됨 —
# 실 DB 가 lower_case_table_names=1 로 `logineventlog`(소문자) 반환 → 모델의 대소문자 구분
# 비교가 case-only 차이를 absence 로 귀결. grounding 계약에 식별자 case-fold 비교 규칙 추가.


def test_identifier_case_insensitive_rule_present():
    # 식별자 대소문자 정규화 비교 규칙이 grounding 계약에 존재해야 한다: case-only 차이는 absence 근거 아님.
    assert "A name that differs ONLY in case is NOT by itself evidence of absence" in _SRC


def test_case_rule_conditions_equating_on_server_casefold():
    # REV-20260714T221500 (적대 패널 NIT): 무조건 case-insensitive 동일시는 lcase=0 서버에서
    # 반대방향 오류(거짓 동일시)를 유발 → lower_case_table_names 실측에 조건화(L105 SERVER OPTIONS 정합).
    assert "lower_case_table_names=1" in _SRC
    assert "on a case-sensitive server, confirm before equating" in _SRC
    assert "LoginEventLog" in _SRC and "logineventlog" in _SRC  # 구체 예시(CamelCase↔소문자)


def test_case_rule_requires_casefold_search_before_absence():
    # absence 단정 전 case-fold 검색/probe 를 요구(정확-표기 스캔만으로 absence 결론 금지).
    assert "search the attachment case-insensitively (case-fold) or run a targeted probe" in _SRC
    assert "never conclude absence from an exact-case scan" in _SRC
