"""node_analysis 테이블 역할 분류 순수함수 단위 테스트 (feature-0016 node-role-viz).

DB/AGE/LLM 불요 — 분류체계 검증·휴리스틱 분류·role 해석은 전부 순수 함수다. 검증 핵심(요청 2026-07-02):
  - NODE_ROLES 8종 고정 분류체계가 FE(_META_ROLE)·LLM 계약과 정합 유지.
  - LLM "role" 값이 유효하면 우선, 무효/누락이면 휴리스틱 폴백.
  - 휴리스틱: 이름 신호 우선(1-pass) → 분석문 본문(2-pass) → 'etc'. 우선순위 순서(log 가
    transaction 보다 먼저 — PurchaseLog 류가 log 로) 보존.
  - Table 이외 라벨(Column/Schema/GlossaryTerm)은 role 저장 안 함(None).

실행: conftest.py 가 src 를 path 에 넣어 `from modules import node_analysis` 가능.
"""
from modules import node_analysis as na


# ── 분류체계 계약 ─────────────────────────────────────────────────────────────
def test_node_roles_fixed_taxonomy():
    assert na.NODE_ROLES == ("master", "account", "transaction", "log", "mapping",
                             "config", "stats", "etc")
    # 규칙 표의 role 은 전부 분류체계 원소여야 한다(etc 는 폴백이라 규칙 없음).
    rule_roles = {r for r, _n, _t in na._ROLE_RULES}
    assert rule_roles <= set(na.NODE_ROLES)
    assert "etc" not in rule_roles


def test_role_valid():
    assert na._role_valid("log") == "log"
    assert na._role_valid(" Master ") == "master"      # 공백·대소문자 정규화
    assert na._role_valid("unknown") is None
    assert na._role_valid("") is None
    assert na._role_valid(None) is None


# ── 휴리스틱: 이름 신호(1-pass) ───────────────────────────────────────────────
def test_heuristic_name_signals():
    assert na.classify_role_heuristic("PurchaseLog", "dbo.PurchaseLog") == "log"       # log 가 transaction 보다 우선
    assert na.classify_role_heuristic("GachaHistory", "dbo.GachaHistory") == "log"     # hist 토큰
    assert na.classify_role_heuristic("RankWeekly", "dbo.RankWeekly") == "stats"
    assert na.classify_role_heuristic("GameConfig", "dbo.GameConfig") == "config"      # config 가 mapping 보다 우선
    assert na.classify_role_heuristic("ItemUserMapping", "dbo.ItemUserMapping") == "mapping"
    assert na.classify_role_heuristic("CharacterSlot", "dbo.CharacterSlot") == "account"
    assert na.classify_role_heuristic("PaymentReceipt", "dbo.PaymentReceipt") == "transaction"
    assert na.classify_role_heuristic("ItemDefine", "dbo.ItemDefine") == "master"


def test_heuristic_name_uses_fqn_last_segment():
    # name 이 비어도 fqn 마지막 세그먼트로 분류.
    assert na.classify_role_heuristic("", "dbo.UserAccount") == "account"


# ── 휴리스틱: 본문 신호(2-pass) + etc 폴백 ────────────────────────────────────
def test_heuristic_text_fallback():
    analysis = {"summary": "확률형 아이템 결제·지급 내역을 담는 테이블", "usage": "", "relationships": ""}
    assert na.classify_role_heuristic("TBL_A", "dbo.TBL_A", analysis) == "transaction"


def test_heuristic_name_beats_text():
    # 이름 신호(log)가 본문 신호(결제=transaction)보다 우선.
    analysis = {"summary": "결제 이벤트 기록", "usage": "", "relationships": ""}
    assert na.classify_role_heuristic("BuyLog", "dbo.BuyLog", analysis) == "log"


def test_heuristic_etc_when_no_signal():
    assert na.classify_role_heuristic("Achievement", "dbo.Achievement") == "etc"
    assert na.classify_role_heuristic("Achievement", "dbo.Achievement", {"summary": "업적 진행"}) == "etc"
    # 문자열 analysis(비-dict, json 파싱 실패 잔재)도 크래시 없이 처리.
    assert na.classify_role_heuristic("TBL_B", "dbo.TBL_B", "결제 지급 기록") == "transaction"


# ── _resolve_role: LLM 우선 + 폴백 + Table 한정 ──────────────────────────────
def test_resolve_role_llm_valid_wins():
    obj = {"summary": "구매 로그", "role": "master"}   # LLM 이 명시한 유효 role 이 휴리스틱(log)보다 우선
    assert na._resolve_role("Table", obj, "PurchaseLog", "dbo.PurchaseLog") == "master"


def test_resolve_role_invalid_falls_back_to_heuristic():
    obj = {"summary": "구매 로그", "role": "banana"}
    assert na._resolve_role("Table", obj, "PurchaseLog", "dbo.PurchaseLog") == "log"
    obj2 = {"summary": "확률형 아이템 결제 지급 내역"}   # role 누락 → 본문 휴리스틱
    assert na._resolve_role("Table", obj2, "TBL_A", "dbo.TBL_A") == "transaction"


def test_resolve_role_non_table_is_none():
    obj = {"summary": "컬럼 설명", "role": "master"}
    assert na._resolve_role("Column", obj, "UserId", "dbo.T.UserId") is None
    assert na._resolve_role("GlossaryTerm", obj, "용어", "") is None
    assert na._resolve_role("Schema", obj, "dbo", "dbo") is None
    assert na._resolve_role("", obj, "X", "") is None
