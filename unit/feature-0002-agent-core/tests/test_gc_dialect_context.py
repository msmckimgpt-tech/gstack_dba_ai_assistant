"""gc-assistant-dialect-context 회귀 테스트 (RC-1 dialect 교정 + RC-2 그룹 발신자 라벨).

근본 원인(라이브 group conv 20260625063340-4220125d 관측):
  RC-1 — MySQL datasource 인데 LLM 이 T-SQL(TOP/UNION/[brackets]/CONVERT/2-arg ISNULL)을 생성→
         sql_guard 거부 thrashing. 수정: 엔진별 dialect 지침 권위 주입 + 거부 메시지 교정 힌트.
  RC-2 — 그룹대화 히스토리에 발신자 라벨이 없어 LLM 이 사람-사람 맥락을 못 따라감. 수정: user
         메시지에 `[발신자]: ` 라벨 부착(병합 전 → 병합 후에도 보존), 그룹일 때만(비그룹 무회귀).

라이브 DB 비의존 — 순수 함수 + cfg ContextVar 만 사용.
"""
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402
from modules import tools  # noqa: E402
from shared import config as cfg  # noqa: E402


# ── RC-2: 발신자 라벨 부착 (그룹) + 병합 보존 ──────────────────────────────
def _rows():
    return [
        {"role": "user", "content": "안녕하세요", "sender_account_id": 4},
        {"role": "user", "content": "네네", "sender_account_id": 10},
        {"role": "user", "content": "@assistant 가능한가요?", "sender_account_id": 10},
        {"role": "assistant", "content": "네, 가능합니다"},
        {"role": "user", "content": "프로덕트 바꿔서", "sender_account_id": 4},
    ]


def test_group_sender_labels_attached_and_preserved_through_merge():
    labels = {4: "mckim", 10: "admin"}
    out = agent_core._merge_consecutive_user_messages(
        agent_core._format_core_messages(_rows(), labels)
    )
    # 연속 user 3건이 1개 user 턴으로 병합되되 각 발화의 발신자 라벨이 보존된다.
    assert out[0]["role"] == "user"
    assert out[0]["content"].startswith("[mckim]: 안녕하세요")
    assert "[admin]: 네네" in out[0]["content"]
    assert "[admin]: @assistant 가능한가요?" in out[0]["content"]
    # assistant 턴 뒤의 user 도 라벨.
    assert out[-1]["content"] == "[mckim]: 프로덕트 바꿔서"
    # assistant 메시지는 라벨 대상 아님.
    assert out[1]["role"] == "assistant" and out[1]["content"] == "네, 가능합니다"


def test_non_group_none_no_labels_regression():
    # sender_labels=None(1:1·미백필) → 라벨 미부착, 기존 동작과 동일.
    out = agent_core._merge_consecutive_user_messages(
        agent_core._format_core_messages(_rows(), None)
    )
    assert out[0]["content"].startswith("안녕하세요")
    assert "[" not in out[0]["content"]
    assert out[-1]["content"] == "프로덕트 바꿔서"


def test_label_skipped_for_unknown_sender():
    # 라벨 사전에 없는 발신자(예: 추방된 멤버)는 라벨 없이 원문 유지.
    labels = {4: "mckim"}
    rows = [{"role": "user", "content": "hi", "sender_account_id": 999}]
    out = agent_core._format_core_messages(rows, labels)
    assert out[0]["content"] == "hi"


# ── RC-1: 엔진 인지형 dialect 교정 힌트 ──────────────────────────────────
def test_dialect_hint_mysql_corrects_tsql():
    cfg.set_active_datasource("mysql-x", engine="mysql")
    h = tools._dialect_correction_hint(
        "SELECT TOP 100 * FROM [t] WHERE d=CONVERT(DATE, x) UNION ALL SELECT ISNULL(a,b)"
    )
    assert "MySQL" in h
    assert "TOP" in h and "LIMIT" in h
    assert "UNION" in h
    assert "IFNULL" in h or "COALESCE" in h
    assert "백틱" in h  # [bracket] → backtick 교정


def test_dialect_hint_mssql_corrects_mysql():
    cfg.set_active_datasource("mssql-x", engine="mssql")
    h = tools._dialect_correction_hint("SELECT * FROM `db`.`t` LIMIT 10")
    assert ("SQL Server" in h) or ("T-SQL" in h)
    assert "TOP" in h


def test_dialect_hint_clean_query_head_only():
    # 방언 오용 마커가 없으면 엔진 헤더만(거짓 교정 없음).
    cfg.set_active_datasource("mysql-x", engine="mysql")
    h = tools._dialect_correction_hint("SELECT a FROM db.t LIMIT 5")
    assert "MySQL" in h
    assert "TOP" not in h and "UNION" not in h


# ── conv-audit FR-nl2sql-schema-discovery-giveup: 능동 해석 지침을 modality 무관으로 일반화 ──
# 라이브 1:1 conv 20260626034832 에서 assistant 가 스키마(dbGame)를 dbgame 으로 소문자화→1049→
# 8 tool 후 give-up·대량 재질문. 기존 능동해석 지침이 그룹에만 주입돼 1:1 은 무방비였다.
import inspect  # noqa: E402


def test_active_interpretation_guidance_is_modality_agnostic():
    g = agent_core._ACTIVE_INTERPRETATION_GUIDANCE
    # 핵심 anti-friction 지침 포함(과도 재질문 억제 / 추측 말고 발견 / casing 보존 / 데이터소스 일관성).
    assert "과도하게 되묻지" in g
    assert "추측하지 말고 발견" in g
    assert "소문자화하지" in g  # casing 보존(dbGame≠dbgame)
    assert "데이터소스/주제 일관성" in g
    assert "통째로 미루지" in g  # give-up 금지
    # modality 무관 — 그룹 전용 마커(여러 명/발신자 라벨/@assistant)는 이 블록에 없어야 한다.
    assert "여러 명의 사람" not in g
    assert "발신자이름" not in g


def test_group_guidance_keeps_only_multiparty_specifics():
    g = agent_core._GROUP_CONVERSATION_GUIDANCE
    # 다자-특화(발신자 라벨·여러 사람)만 유지.
    assert "여러 명의 사람" in g
    assert "발신자이름" in g
    # 능동 해석 일반 본문은 분리됐다(중복 제거) — general 안티마찰 문구가 group 블록에 재등장하지 않아야
    # split 불변식이 잠긴다(§18.8 QA 리뷰 follow-up: 1개만 단언하면 미래 재중복을 못 잡음).
    for _p in ("과도하게 되묻", "추측하지 말고", "소문자화", "통째로 미루지", "데이터소스/주제 일관성", "스키마/테이블을 모르면"):
        assert _p not in g, f"general 문구 '{_p}' 가 group 블록에 재등장 — split de-dup 위반"


def test_active_interpretation_injected_unconditionally_for_1to1():
    # _run_agent_core 에서 능동해석 주입이 그룹 조건(if _group_sender_labels) 밖(무조건)이어야 1:1 도 받는다.
    src = inspect.getsource(agent_core._run_agent_core)
    lines = src.splitlines()
    active = [l for l in lines if "system_content += _ACTIVE_INTERPRETATION_GUIDANCE" in l]
    assert active, "능동해석 주입 라인이 _run_agent_core 에 있어야 한다"
    # 함수 본문 레벨 들여쓰기(8 spaces: def 안 4 + 1단계)여야 하고, 16(if-블록 내부)이면 그룹-한정 회귀.
    indent = len(active[0]) - len(active[0].lstrip())
    grp = [l for l in lines if "system_content += _GROUP_CONVERSATION_GUIDANCE" in l]
    assert grp, "그룹 지침 주입 라인 존재"
    grp_indent = len(grp[0]) - len(grp[0].lstrip())
    # 능동해석은 그룹 주입보다 얕은(또는 같지 않은 if-내부가 아닌) 들여쓰기 — 그룹은 if 안이라 더 깊다.
    assert indent < grp_indent, (
        f"능동해석(indent={indent})이 그룹 if-블록(indent={grp_indent}) 밖이어야 1:1 도 주입됨"
    )
