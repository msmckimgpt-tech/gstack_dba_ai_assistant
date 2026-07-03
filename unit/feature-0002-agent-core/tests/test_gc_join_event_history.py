"""feature-0009 gc-join-notice — 참여 알림 이벤트가 LLM 대화 히스토리에서 배제되는지 회귀.

배경(§18.8 적대 패널 BLOCKING #1):
  공유 링크로 새 멤버가 참여하면 `_save_group_join_event_pg` 가 "X님이 대화에 참여했습니다."
  를 core_messages 에 role='user' 로 기록한다(사이드바 unread 배지 집계가 role IN
  ('user','assistant') 를 요구하기 때문). 그런데 core_messages 는 그대로 LLM 대화 히스토리의
  소스라, 필터가 없으면 이 이벤트가 발신자 라벨이 붙은 user 턴("[Alice]: Alice님이 대화에
  참여했습니다.")으로 LLM 에 주입돼 assistant 가 오응답(환영 인사 등)하거나 맥락이 오염된다.

수정: 이런 이벤트 core_message 에 `name = EVENT_MESSAGE_NAME` sentinel 을 부여하고,
  `_normalize_history_rows` 최상단에서 그 name 을 보고 완전히 배제한다(윈도우·kept_users·
  발신자 라벨·연속 user 병합 어디에도 들어가지 않음). unread 집계(app.py SQL)는 name 을
  참조하지 않으므로 role='user' 로 그대로 집계된다.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 순수 함수로 실행된다.
"""
from __future__ import annotations

import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402
from modules.runtime_backend import EVENT_MESSAGE_NAME  # noqa: E402

_JOIN_TEXT = "Alice님이 대화에 참여했습니다."


def _rows_with_event():
    """가입자(id=10)의 참여 이벤트가 두 실제 user 턴 사이에 낀 그룹 히스토리."""
    return [
        {"role": "user", "content": "안녕하세요", "sender_account_id": 4},
        {"role": "user", "content": _JOIN_TEXT, "sender_account_id": 10,
         "name": EVENT_MESSAGE_NAME},
        {"role": "user", "content": "@assistant 최근 에러율?", "sender_account_id": 4},
        {"role": "assistant", "content": "네, 조회할게요"},
    ]


def test_event_row_dropped_by_normalize():
    # _normalize_history_rows 가 name sentinel 행을 통째로 배제한다.
    out = agent_core._normalize_history_rows(_rows_with_event())
    assert all(str(r.get("name") or "") != EVENT_MESSAGE_NAME for r in out)
    assert all(_JOIN_TEXT not in str(r.get("content") or "") for r in out)
    # 실제 user/assistant 턴은 보존.
    assert any(r.get("content") == "안녕하세요" for r in out)
    assert any(r.get("content") == "@assistant 최근 에러율?" for r in out)
    assert any(r.get("role") == "assistant" for r in out)


def test_event_not_injected_into_assembled_llm_messages_group():
    # 그룹(sender_labels 有) 전체 파이프라인에서도 이벤트 문장이 LLM 메시지에 없어야 한다.
    labels = {4: "mckim", 10: "alice"}
    msgs = agent_core._assemble_core_messages(_rows_with_event(), max_messages=50,
                                              sender_labels=labels)
    joined = "\n".join(str(m.get("content") or "") for m in msgs)
    assert _JOIN_TEXT not in joined
    # 발신자 라벨이 이벤트에 붙지 않았는지(오염된 형태) 이중 확인.
    assert "alice님이 대화에 참여" not in joined and "[alice]:" not in joined
    # 실제 발화는 라벨과 함께 보존.
    assert "[mckim]: 안녕하세요" in joined
    assert "[mckim]: @assistant 최근 에러율?" in joined


def test_identical_content_without_sentinel_is_kept():
    # name sentinel 이 없으면(사용자가 우연히 같은 문장을 실제로 입력) 배제하지 않는다 —
    # content 매칭이 아니라 name sentinel 매칭임을 보장(무고한 발화 억제 방지).
    rows = [
        {"role": "user", "content": _JOIN_TEXT, "sender_account_id": 4},
    ]
    out = agent_core._normalize_history_rows(rows)
    assert len(out) == 1 and out[0]["content"] == _JOIN_TEXT


def test_event_row_does_not_consume_kept_user_window_slot():
    # 이벤트가 normalize 단계에서 빠지므로 윈도우/kept_users 슬롯을 잠식하지 않는다.
    # max_messages=1 로 강제 절단해도 실제 앞선 user 의도가 kept_users 로 보존된다.
    rows = [
        {"role": "user", "content": "제약: 최근 1시간만", "sender_account_id": 4},
        {"role": "user", "content": _JOIN_TEXT, "sender_account_id": 10,
         "name": EVENT_MESSAGE_NAME},
        {"role": "assistant", "content": "확인"},
        {"role": "user", "content": "@assistant 진행", "sender_account_id": 4},
    ]
    msgs = agent_core._assemble_core_messages(rows, max_messages=1, sender_labels=None)
    joined = "\n".join(str(m.get("content") or "") for m in msgs)
    assert _JOIN_TEXT not in joined
    assert "제약: 최근 1시간만" in joined  # 이벤트가 슬롯을 훔치지 않아 실제 제약 보존
