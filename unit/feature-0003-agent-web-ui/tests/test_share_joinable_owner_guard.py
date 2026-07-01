"""feature-0009-share-joinable-guard (Critical §12.3 — 인가/권한) —
공유 링크 '참여 허용(joinable)' 토글은 대화 생성자(owner)만 설정 가능.

요청: `대화 탭 > ··· > 설정 > 공유` 의 "이 링크로 대화 참여 허용" 체크박스를
대화를 생성한 사용자만 수정할 수 있게 하고, 비소유자에겐 비활성(disabled) 으로
표시한다. 비소유자가 브라우저 조작으로 joinable=true 를 전송해도 백엔드에서 403 으로
차단한다(클라이언트 disable 은 UX, 백엔드 게이트가 권위).

결정(AskUserQuestion):
  D1 = 비소유자 joinable=true → 403 거부 (조용한 강등 아님).
  D2 = 소유자만 엄격 (admin/conversation.read.any 예외 없음).

검증(`make test` agent 이미지, DB 없이 — inspect.getsource 함수 단위 + static read):
  B1 create 엔드포인트: joinable + 비소유자 → 403 게이트(_conversation_owned_by_account).
  B2 게이트가 INSERT 보다 먼저 — 비소유자의 joinable 행이 절대 기록되지 않음.
  B3 owner 헬퍼 존재 + owner_account_id 동등 비교(admin 우회 분기 없음).
  F1 openShareDialog: isOwnConversation 게이트 + 비소유자 disabled + 강제 false.
  F2 promptShareExpiry(앵커 경로): canToggleJoinable + 비소유자 disabled + 강제 false.
  F3 createConversationShare 가 owner 여부를 promptShareExpiry 로 전달.
"""
from __future__ import annotations

import inspect
import os
import sys


def _import_app():
    try:
        import app  # type: ignore
        return app
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        try:
            import app  # type: ignore
            return app
        except ModuleNotFoundError:
            import web.app as app  # type: ignore
            return app


app = _import_app()
from routers import conversations  # feature-0012 P5b


def _static_path(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    return os.path.join(base, "static", name)


def _read_static(name: str) -> str:
    with open(_static_path(name), "r", encoding="utf-8") as fh:
        return fh.read()


# ── B: backend ──────────────────────────────────────────────────────────────
def test_b1_create_endpoint_rejects_nonowner_joinable():
    src = inspect.getsource(conversations.create_conversation_share)
    # joinable 이 truthy 인데 owner 가 아니면 차단.
    assert "_conversation_owned_by_account(conn, cid, int(account[\"id\"]))" in src
    assert "joinable and not app._conversation_owned_by_account" in src
    # 403 + 명시 메시지(요청의 '차단' 직역, D1).
    assert "참여 허용 링크는 대화 생성자만 만들 수 있습니다" in src
    assert ", 403)" in src


def test_b2_owner_gate_runs_before_insert():
    src = inspect.getsource(conversations.create_conversation_share)
    gate_idx = src.find("joinable and not app._conversation_owned_by_account")
    insert_idx = src.find("INSERT INTO WebConversationShares")
    assert gate_idx != -1 and insert_idx != -1
    # 게이트가 INSERT 보다 먼저 — 비소유자의 joinable 링크는 DB 에 절대 기록되지 않는다.
    assert gate_idx < insert_idx


def test_b3_owner_helper_strict_no_admin_bypass():
    assert callable(app._conversation_owned_by_account)
    src = inspect.getsource(app._conversation_owned_by_account)
    # owner_account_id 동등 비교 — admin/superuser 우회 분기 없음(D2: 소유자만 엄격).
    assert "owner_account_id" in src
    assert "== int(account_id)" in src
    # 게이트 자체가 read.any/admin 예외를 두지 않는다.
    gate_src = inspect.getsource(conversations.create_conversation_share)
    gate_line = next(
        (ln for ln in gate_src.splitlines() if "joinable and not app._conversation_owned_by_account" in ln),
        "",
    )
    assert "read.any" not in gate_line
    assert "is_admin" not in gate_line


# ── F: frontend ─────────────────────────────────────────────────────────────
def test_f1_open_share_dialog_owner_gate():
    js = _read_static("app.js")
    # 대화 객체 조회 + 소유자 판정.
    assert "const isOwner = isOwnConversation(_shareConv);" in js
    # 비소유자: disabled 체크박스 + 안내 문구.
    assert 'id="shareDialogJoinableChk" disabled' in js
    assert "대화 생성자만 변경할 수 있습니다" in js
    # 발급 시 비소유자 joinable 강제 false (share-joinable-confirm 리팩터 후 변수명 intended → 최종 joinable).
    # 의도(체크박스) 단계: 비소유자는 항상 false.
    assert "const intended = isOwner && chk ? chk.checked !== false : false;" in js
    # 확인 모달 통과 후 최종 joinable: 비소유자는 owner 분기 자체가 false 라 강제 false 보존.
    assert "const joinable = isOwner ? confirmRes.joinable !== false : false;" in js


def test_f2_prompt_share_expiry_can_toggle_param():
    js = _read_static("app.js")
    # share-joinable-persist 리팩터 후 cid 파라미터 추가 — canToggleJoinable 기본값 유지.
    assert "function promptShareExpiry({ cid = null, canToggleJoinable = true } = {})" in js
    # 비소유자: shareJoinableChk disabled.
    assert 'id="shareJoinableChk" disabled' in js
    # 강제 false resolve.
    assert "const joinable = canToggleJoinable && chk ? chk.checked : false;" in js


def test_f3_create_share_passes_owner_flag():
    js = _read_static("app.js")
    # createConversationShare 가 owner 여부를 promptShareExpiry 로 전달(cid 동반 — persist).
    assert "await promptShareExpiry({ cid, canToggleJoinable: isOwner });" in js
