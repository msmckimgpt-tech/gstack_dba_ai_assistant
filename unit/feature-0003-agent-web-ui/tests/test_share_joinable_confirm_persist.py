"""feature-0009 share-joinable-confirm-persist (Critical 인접 §12.3 — 인가/프라이버시 UX) —
공유 '링크 생성' 직후 참여 허용 여부 확인 + '참여 허용' 체크박스 상태 대화별 영속.

요청:
  (1) '대화 공유' 의 '링크 생성' 버튼을 누른 후, 해당 대화에 참여 허용 여부를 먼저
      확인하는 구조를 구성한다 (Q1=항상 확인 모달).
  (2) '공유' 화면에서 '이 링크로 대화 참여 허용' 체크박스를 조절한 후 다시 '공유'
      화면으로 진입했을 때 상태가 회귀하던 버그를 수정한다 (Q2=대화별 localStorage 영속).

불변식(절대 약화 금지): joinable 의 authoritative 게이트는 여전히 백엔드 owner-only 403.
본 확인/영속은 프론트 UX 편의일 뿐이며, 비소유자는 확인 모달에서도 '허용' 선택지를 못 본다.

검증(`make test` agent 이미지, DB 없이 — static read of app.js / styles.css):
  P1 영속 헬퍼 존재 + 기본 ON(미설정 키는 true).
  P2 openShareDialog 체크박스 초기값을 영속값에서 복원 + change 시 저장.
  P3 promptShareExpiry(앵커 경로)도 cid 영속값 복원 + change/확정 시 저장.
  C1 confirmShareJoinable 모달 존재.
  C2 openShareDialog '링크 생성' 이 발급 전 confirmShareJoinable 게이트를 통과 + 취소 시 중단.
  C3 비소유자(canAllow=false)는 '허용' 버튼(data-act="allow") 자체가 없음 — joinable 강제 false.
  C4 확인 모달 CSS 클래스 존재.
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


def _static_path(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    return os.path.join(base, "static", name)


def _read_static(name: str) -> str:
    with open(_static_path(name), "r", encoding="utf-8") as fh:
        return fh.read()


# ── P: persistence (회귀 수정) ───────────────────────────────────────────────
def test_p1_persist_helpers_exist_and_default_on():
    js = _read_static("app.js")
    assert 'SHARE_JOINABLE_PREFS_LS_KEY = "mad.shareJoinablePrefs.v1"' in js
    assert "function _loadShareJoinablePrefs()" in js
    assert "function getShareJoinablePref(cid)" in js
    assert "function setShareJoinablePref(cid, joinable)" in js
    # 미설정(키 부재) 대화는 기존 기본값 ON 유지 — 명시 false 일 때만 OFF.
    assert "_loadShareJoinablePrefs()[String(cid)] !== false" in js
    # 저장 시 명시 false 만 OFF 로 정규화.
    assert "prefs[String(cid)] = joinable !== false;" in js


def test_p2_open_share_dialog_restores_and_persists():
    js = _read_static("app.js")
    # 초기값을 영속값에서 복원(회귀 방지) — 하드코딩 checked 가 아니어야 한다.
    assert "const joinableInit = isOwner && getShareJoinablePref(cid);" in js
    assert "(joinableInit ? ' checked' : '')" in js
    # 토글 즉시 영속(생성 안 하고 닫아도 복원).
    assert 'joinableChk.addEventListener("change", () => setShareJoinablePref(cid, joinableChk.checked));' in js


def test_p3_prompt_share_expiry_restores_and_persists():
    js = _read_static("app.js")
    assert "const joinableInit = canToggleJoinable && getShareJoinablePref(cid);" in js
    # 토글 즉시 영속.
    assert 'chkInit.addEventListener("change", () => setShareJoinablePref(cid, chkInit.checked));' in js
    # 만료 프리셋 확정 시에도 최종 joinable 영속.
    assert "if (canToggleJoinable) setShareJoinablePref(cid, joinable);" in js


# ── C: confirm gate (요청 1) ─────────────────────────────────────────────────
def test_c1_confirm_modal_exists():
    js = _read_static("app.js")
    assert "function confirmShareJoinable({ initial = true, canAllow = true } = {})" in js
    assert "참여 허용 확인" in js


def test_c2_create_gated_by_confirm_before_issue():
    js = _read_static("app.js")
    confirm_idx = js.find("await confirmShareJoinable({ initial: intended, canAllow: isOwner });")
    abort_idx = js.find("if (!confirmRes || confirmRes.cancelled) return;")
    issue_idx = js.find('await _issueConversationShare({ cid, scopeMode: "full", joinable, seconds: preset.seconds });')
    assert confirm_idx != -1 and abort_idx != -1 and issue_idx != -1
    # 확인 모달 → 취소 중단 → (통과 시) 발급. 순서가 보장되어야 무심코 누른 생성으로 공개되지 않는다.
    assert confirm_idx < abort_idx < issue_idx


def test_c3_nonowner_cannot_allow_in_confirm():
    js = _read_static("app.js")
    confirm_src = js[js.find("function confirmShareJoinable("):]
    confirm_src = confirm_src[: confirm_src.find("\nfunction ")]
    # '허용' 선택지(data-act="allow")는 canAllow 분기 안에서만 렌더된다.
    allow_idx = confirm_src.find('data-act="allow"')
    deny_only_idx = confirm_src.find("canAllow")
    assert allow_idx != -1 and deny_only_idx != -1
    # canAllow 평가가 allow 버튼보다 먼저(조건부 렌더) — 비소유자는 allow 버튼 미생성.
    assert deny_only_idx < allow_idx
    # 호출부: openShareDialog 는 canAllow 를 isOwner 로 묶고, 최종 joinable 은 비소유자 강제 false.
    assert "confirmShareJoinable({ initial: intended, canAllow: isOwner })" in js
    assert "const joinable = isOwner ? confirmRes.joinable !== false : false;" in js


def test_c4_confirm_css_present():
    css = _read_static("styles.css")
    assert ".share-confirm-panel" in css
    assert ".share-confirm-actions" in css
