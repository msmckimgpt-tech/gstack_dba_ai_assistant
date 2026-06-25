"""gc-unread-read-500-fix: 읽음 API(POST /api/conversations/{cid}/read) 핸들러가
PG 연결을 존재하지 않는 `modules.db` 가 아니라 `shared.db._pg_connect` 로 import 하는지 보장.

배경: `mark_conversation_read` 가 `from modules.db import _pg_connect` 를 쓰던 탓에,
web 컨테이너(feature-0002 modules 를 baked — 거기에 `db.py` 가 없음)에서 매 호출
`ModuleNotFoundError` → 핸들러의 `except Exception: return _json_error(..., 500)` 로 500.
frontend `markConversationRead` 가 best-effort try/catch 로 500 을 삼켜 화면엔 배지가 0 으로
보이지만 서버 `conversation_members.last_read_message_id` 커서는 전진하지 않아, 새로고침하면
사이드바 unread 배지가 다시 복원되던 버그. 읽음 API 신설(gc-unread-badge) 이래 존재했고
baseline backfill·읽음커서 FE 보정(gc-unread-read-fix) 등 후속 수정이 전부 frontend/DB 만
건드려 이 서버 import 버그를 놓쳐 두 차례 재보고까지 살아남았다. 그 원인이 핸들러 테스트
공백이므로, 본 테스트가 회귀를 정적+런타임 양면으로 가드한다.

`make test`(agent 이미지, --no-deps) 에서 DB 없이 실행된다.
"""
from __future__ import annotations

from pathlib import Path

import app  # noqa: E402


def test_app_source_has_no_modules_db_import():
    """web app.py 는 PG 연결을 `shared.db` 에서만 import 해야 한다.

    `modules.db` 는 web 컨테이너 레이아웃에 존재하지 않아(ModuleNotFoundError) silent 500 을
    유발한다 — 같은 파일의 다른 PG 연결 지점들과 동일하게 `shared.db._pg_connect` 를 써야 한다.
    """
    src = Path(app.__file__).read_text(encoding="utf-8")
    assert "from modules.db import" not in src, (
        "web app.py 가 존재하지 않는 modules.db 를 import 함 — shared.db 를 써야 한다 "
        "(POST /api/conversations/{cid}/read silent 500 회귀)"
    )
    assert "import modules.db" not in src, (
        "web app.py 가 modules.db 를 import 함 — web 레이아웃엔 부재(silent 500 회귀)"
    )


def test_read_handler_pg_connect_import_is_resolvable():
    """읽음 핸들러가 쓰는 정확한 import 경로가 web 레이아웃에서 resolvable 해야 한다.

    이 import 가 깨지면 읽음 커서가 영영 전진하지 못해(매 호출 500) unread 배지가 새로고침마다
    복원된다. import 자체의 가용성을 런타임으로 가드한다.
    """
    from shared.db import _pg_connect  # noqa: F401

    assert callable(_pg_connect)


def test_read_handler_ignores_client_id_uses_core_messages_max():
    """gc-unread-read-idspace-fix: 읽음 핸들러는 client 가 보낸 last_read_message_id 를
    커서로 신뢰하지 않고, 항상 그 대화 agent_runtime.core_messages 의 MAX(id) 로 전진해야 한다.

    근본 원인 회귀 가드: 읽음 커서·unread 집계는 core_messages.id 공간인데, FE 가 보내던
    last_read_message_id 는 /api/history 가 채운 표시 store(agent_runtime.messages) 의 id 라
    두 id 공간이 분리(disjoint)되어 있었다. FE 값을 커서로 쓰면 set_last_read 의 GREATEST 가
    항상 전진을 거부(영구 no-op) → 읽어도 unread 배지가 안 줄고 대화 전환 시 회귀했다. 누군가
    `target_id = requested`(client 값 신뢰)로 되돌리면 이 테스트가 잡는다.
    """
    import inspect

    src = inspect.getsource(app.mark_conversation_read)
    # (1) client 가 보낸 값(requested/last_read_message_id)을 커서 target 으로 신뢰하면 안 된다.
    assert "target_id = requested" not in src, (
        "읽음 핸들러가 client last_read_message_id 를 커서로 신뢰함 — "
        "표시 store(messages) id 라 core_messages 커서 공간과 분리되어 GREATEST no-op 회귀"
    )
    assert 'data.get("last_read_message_id")' not in src, (
        "읽음 핸들러가 body 의 last_read_message_id 를 파싱·사용함 — id-space 불일치 회귀"
    )
    # (2) 항상 core_messages 의 MAX(id) 를 커서로 쓴다(조건부가 아니라 무조건).
    assert "MAX(id)" in src and "agent_runtime.core_messages" in src, (
        "읽음 핸들러가 core_messages MAX(id) 로 커서를 산출하지 않음"
    )
    assert "set_last_read" in src
