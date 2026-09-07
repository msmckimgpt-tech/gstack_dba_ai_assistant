"""클라이언트 업데이트 채널 — 계약 잠금 (feature-0046 client-update-channel, 2026-09-07).

## 이 스위트가 지키는 것

1. **버전 판정** — 문자열 비교가 아니다(`1.10.0 > 1.9.0`). 같으면 갱신하지 않는다(무한 재설치
   차단). 모양이 아닌 값은 **거짓**이다(오염된 매니페스트가 설치를 유발하지 못하게).
2. **출처 고정** — 매니페스트가 실어 보낸 어떤 URL 도 쓰지 않는다. 앵커는 `pinned_server`
   (실제로 연결에 성공한 곳)와 사내 CA 뿐이고, `remembered_base`(수락한 딥링크 주소)는
   **쓰지 않는다** — 창을 여는 근거와 실행 파일을 받는 근거는 세기가 다르다.
3. **무결성 4축** — 크기·sha256·PE 서명·상한. 하나만 남으면 그 하나가 방어선 전체가 된다.
4. **세 곳의 이름 규약이 같다** — 클라이언트·서버·퍼블리시가 같은 파일명을 통과·거절해야
   한다. 갈리면 한 곳이 통과시킨 릴리스를 다른 곳이 거절해 **아무도 받지 못한다**.
5. **버전 정본 1개** — `version.py` ↔ `.iss` 폴백 ↔ 빌드 주입. 갈리면 설치기 파일명과
   프로그램이 말하는 버전이 달라지고, 업데이트 판정이 두 방향 중 하나로 고장난다.
6. **확인 없이 설치하지 않는다** — `update_apply` 는 `DANGEROUS` 이고 자동 적용은 기본 꺼짐.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from client import bridge as bridge_mod  # noqa: E402
from client import core, updater, version  # noqa: E402

_ISS = _SRC / "installer" / "DQAConnect.iss"
_BUILD = _SRC / "scripts" / "build_client.py"
_PUBLISH = _SRC / "scripts" / "publish_release.py"
_WEB_SRC = (Path(__file__).resolve().parents[2]
            / "feature-0003-agent-web-ui" / "src")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def release_mod():
    """서버 라우터를 **파일에서** 적재한다 — 웹 패키지 전체를 세우지 않는다."""
    if str(_WEB_SRC) not in sys.path:
        sys.path.insert(0, str(_WEB_SRC))
    return _load("client_release_under_test", _WEB_SRC / "routers" / "client_release.py")


def _setup_bytes(size: int = updater.MIN_SETUP_BYTES) -> bytes:
    """PE 처럼 보이는 더미. **실제 실행 파일이 아니다** — 검사만 통과한다."""
    return b"MZ" + b"\0" * (size - 2)


def _manifest(**over) -> bytes:
    payload = _setup_bytes()
    doc = {
        "version": "9.9.9",
        "filename": "DQAConnect-Setup-9.9.9.exe",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "notes": "테스트",
    }
    doc.update(over)
    return json.dumps(doc).encode("utf-8")


# ── 1. 버전 판정 ────────────────────────────────────────────────────────────────

def test_version_compares_numerically_not_as_text():
    # 문자열 비교면 "1.10.0" < "1.9.0" 이라 열 번째 릴리스가 낡은 것으로 읽힌다.
    assert version.is_newer("1.10.0", "1.9.0")
    assert not version.is_newer("1.9.0", "1.10.0")


def test_same_version_is_not_newer():
    """같은 버전을 새것으로 읽으면 **매번 자기를 다시 설치**한다."""
    assert not version.is_newer("1.1.0", "1.1.0")
    # 자릿수만 다른 같은 버전도 마찬가지다.
    assert not version.is_newer("1.1", "1.1.0")
    assert not version.is_newer("1.1.0", "1.1")


@pytest.mark.parametrize("bad", ["", "abc", "1.2.3-rc1", "../1.2.3", "1.2.3.4.5",
                                 "1.2.3\n9.9.9"])
def test_malformed_version_never_triggers_update(bad):
    """모르는 값을 「새것」으로 읽으면 아무 문자열이 설치를 유발한다."""
    assert not version.is_newer(bad, "1.0.0")


# ── 2. 매니페스트 검증 (순수 함수 — 모든 거절 경로를 돈다) ──────────────────────

def test_manifest_happy_path():
    got = updater.parse_manifest(_manifest(), current="1.0.0")
    assert got is not None
    assert got.version == "9.9.9"
    assert got.filename == "DQAConnect-Setup-9.9.9.exe"


def test_manifest_rejects_when_not_newer():
    assert updater.parse_manifest(_manifest(), current="9.9.9") is None
    assert updater.parse_manifest(_manifest(), current="10.0.0") is None


@pytest.mark.parametrize("name", [
    "../../etc/passwd",
    "DQAConnect-Setup-9.9.9.exe/../evil.exe",
    "evil.exe",
    "DQAConnect-Setup-9.9.9.exe.bat",
    "-DQAConnect-Setup-9.9.9.exe",
    "sub/DQAConnect-Setup-9.9.9.exe",
])
def test_manifest_rejects_dangerous_filenames(name):
    """파일명이 곧 **받을 경로**다. 이름 하나로 다른 파일을 받게 두지 않는다."""
    assert updater.parse_manifest(_manifest(filename=name), current="1.0.0") is None


def test_manifest_rejects_when_filename_and_version_disagree():
    """어느 쪽을 믿을지 고르는 순간 나머지 하나는 검증이 아니라 장식이 된다."""
    bad = _manifest(filename="DQAConnect-Setup-9.9.8.exe")
    assert updater.parse_manifest(bad, current="1.0.0") is None


@pytest.mark.parametrize("digest", ["", "deadbeef", "Z" * 64, "0" * 63])
def test_manifest_rejects_non_digest(digest):
    assert updater.parse_manifest(_manifest(sha256=digest), current="1.0.0") is None


@pytest.mark.parametrize("size", [0, -1, updater.MIN_SETUP_BYTES - 1,
                                  updater.MAX_SETUP_BYTES + 1, "많이"])
def test_manifest_rejects_impossible_size(size):
    assert updater.parse_manifest(_manifest(size=size), current="1.0.0") is None


def test_manifest_rejects_non_json():
    assert updater.parse_manifest(b"<html>login</html>", current="1.0.0") is None
    assert updater.parse_manifest(b"[]", current="1.0.0") is None


def test_manifest_ignores_any_url_it_carries():
    """서버가 URL 을 실어 보내도 `Update` 에 남지 않는다 — 규율 1 의 기계적 표현."""
    got = updater.parse_manifest(
        _manifest(url="https://evil.example/x.exe", path="/evil/x.exe"), current="1.0.0")
    assert got is not None
    assert not [f for f in got.__dataclass_fields__ if "url" in f]


# ── 3. 무결성 4축 ───────────────────────────────────────────────────────────────

def _update_of(payload: bytes) -> updater.Update:
    return updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                          sha256=hashlib.sha256(payload).hexdigest(),
                          size=len(payload))


def test_verify_accepts_exactly_what_the_manifest_described():
    payload = _setup_bytes()
    assert updater.verify(payload, _update_of(payload))


def test_verify_rejects_size_mismatch():
    payload = _setup_bytes()
    upd = _update_of(payload)
    assert not updater.verify(payload + b"\0", upd)


def test_verify_rejects_non_executable():
    """HTML 오류 본문·리다이렉트 페이지가 그대로 실행되지 않게 한다."""
    payload = b"<!" + b"\0" * (updater.MIN_SETUP_BYTES - 2)
    assert not updater.verify(payload, _update_of(payload))


def test_verify_rejects_digest_mismatch():
    payload = _setup_bytes()
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=len(payload))
    assert not updater.verify(payload, upd)


# ── 4. 신뢰 앵커 ────────────────────────────────────────────────────────────────

def test_update_base_uses_the_pinned_server(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.pin_server(home, "https://real.example")
    assert updater.update_base(home) == "https://real.example"


def test_update_base_ignores_a_merely_remembered_link(tmp_path, monkeypatch):
    """딥링크를 한 번 수락한 것만으로 그 서버가 **실행 파일의 출처**가 되지 않는다."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.remember_base(home, "https://attacker.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: None)
    assert updater.update_base(home) == ""


def test_update_base_refuses_plaintext(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "pinned_server", lambda _h: "http://plain.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: None)
    assert updater.update_base(home) == ""


def test_check_is_a_noop_without_ca(tmp_path, monkeypatch):
    """CA 가 없으면 **묻지도 않는다** — 전역 신뢰로 폴백하지 않는다."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.pin_server(home, "https://real.example")
    called = []
    monkeypatch.setattr(updater, "_open",
                        lambda *a, **k: called.append(a) or (_ for _ in ()).throw(AssertionError))
    assert updater.check(home) is None
    assert not called


def test_download_refuses_a_hand_made_update_with_a_bad_name(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.pin_server(home, "https://real.example")
    (home / "rootCA.crt").write_text("x", encoding="utf-8")
    evil = updater.Update(version="9.9.9", filename="../evil.exe",
                          sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    assert updater.download(home, evil) is None


# ── 5. 설정·주기 ────────────────────────────────────────────────────────────────

def test_auto_apply_defaults_to_off(tmp_path):
    """서명되지 않은 설치기를 사용자 모르게 돌리지 않는다 (사용자 결정 2026-09-07)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    assert updater.auto_apply(home) is False
    updater.set_auto_apply(home, True)
    assert updater.auto_apply(home) is True


def test_due_is_true_before_any_check_and_false_right_after(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    assert updater.due(home)
    updater.mark_checked(home)
    assert not updater.due(home)


def test_due_recovers_when_the_clock_went_backwards(tmp_path):
    """재부팅·NTP 보정으로 시계가 뒤로 가면 「아직 멀었다」로 **영원히 굳는다**."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    updater.mark_checked(home, now=2_000_000_000.0)
    assert updater.due(home, now=1_000_000_000.0)


# ── 6. 적용 ─────────────────────────────────────────────────────────────────────

def test_apply_refuses_a_missing_file(tmp_path):
    assert updater.apply(tmp_path / "nope.exe") is False


def test_silent_args_relaunch_the_app():
    """무음 설치는 `[Run]` 의 `skipifsilent` 를 타지 않는다 — 우리가 다시 띄워야 한다."""
    assert "/RELAUNCH" in updater.SILENT_ARGS
    assert "/SILENT" in updater.SILENT_ARGS


def _iss_code_only(text: str) -> str:
    """`.iss` 에서 **주석을 걷어낸** 본문.

    ⚠ 이 필터가 없으면 이 파일의 설명 주석이 아래 단언을 스스로 통과·실패시킨다 —
    AGENTS.md §16.7 G11-a 가 「자기 문구가 자기 단언을 통과시킨다」로 기록한 그 형태이며,
    실제로 이 스위트를 처음 돌렸을 때 그렇게 **거짓 FAIL** 이 났다. Inno 의 주석은 두
    가지뿐이라(`;` 로 시작하는 줄 · `{ … }` 블록) 여기서는 이 정도로 충분하고, 이보다
    복잡해지면 G11-a 가 요구하는 언어 인지 도구로 올린다.
    """
    without_blocks = re.sub(r"\{[^{}]*\}", " ", text, flags=re.S)
    return "\n".join(l for l in without_blocks.splitlines()
                     if not l.lstrip().startswith(";"))


def test_installer_relaunches_only_for_our_flag():
    """MDM·스크립트 무음 배포에서 남의 세션에 창이 뜨면 안 된다."""
    code = _iss_code_only(_ISS.read_text(encoding="utf-8", errors="replace"))
    assert "RelaunchAfterSilentUpdate" in code
    assert "WizardSilent" in code
    # 부분 문자열 매칭(`Pos`)으로 판정하면 다른 인자의 **값 안에** 들어 있어도 참이 된다.
    assert "Pos('/RELAUNCH'" not in code
    assert "ParamStr(I)" in code


def test_confirm_text_says_what_is_lost():
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    text = updater.confirm_text(upd, connected=True)
    assert "9.9.9" in text and version.CLIENT_VERSION in text
    assert "끊" in text          # 연결이 끊긴다는 사실을 말한다
    assert "다시 시작" in text     # 그리고 돌아온다는 것도


# ── 7. 세 곳의 이름 규약이 같다 ─────────────────────────────────────────────────

@pytest.mark.parametrize("name,ok", [
    ("DQAConnect-Setup-1.1.0.exe", True),
    ("DQAConnect-Setup-10.20.30.exe", True),
    ("DQAConnect-Setup-1.1.0-rc1.exe", False),
    ("../DQAConnect-Setup-1.1.0.exe", False),
    ("DQAConnect.exe", False),
])
def test_setup_name_rule_is_identical_in_three_places(name, ok, release_mod):
    """클라이언트·서버·퍼블리시가 **같은 이름을** 통과·거절해야 한다.

    갈리면 한 곳이 통과시킨 릴리스를 다른 곳이 거절해 그 버전은 아무도 받지 못하고,
    원인은 세 파일을 나란히 놓고 봐야만 보인다.
    """
    publish = _load("publish_release_under_test", _PUBLISH)
    assert bool(updater.SETUP_NAME_RE.match(name)) is ok
    assert bool(release_mod.SETUP_NAME_RE.match(name)) is ok
    assert bool(publish.SETUP_NAME_RE.match(name)) is ok


def test_client_and_server_agree_on_the_download_prefix(release_mod):
    """접두가 갈리면 매니페스트는 뜨는데 파일만 404 가 된다."""
    assert updater.DOWNLOAD_PREFIX == release_mod.DOWNLOAD_PREFIX


# ── 8. 버전 정본 1개 ────────────────────────────────────────────────────────────

def test_the_canon_version_satisfies_its_own_rule():
    """정본이 `VERSION_RE` 를 만족하지 않으면 **아무도 업데이트되지 않는다** (적대 리뷰 C4).

    `1.2.3.4.5` 같은 값이면 `parse(current)` 가 `None` 이라 `is_newer` 가 항상 거짓이 되고,
    클라이언트는 어떤 매니페스트에도 반응하지 않는다 — `.iss` 주석이 스스로 명명한 두 파괴
    모드 중 「영원히 최신」이 정본 한 글자로 발생하는데 그것을 잡는 게이트가 없었다.
    """
    assert version.VERSION_RE.fullmatch(version.CLIENT_VERSION)
    assert version.parse(version.CLIENT_VERSION) is not None


def test_the_build_and_the_iss_use_the_same_version_shape():
    """빌드·테스트의 정규식이 정본보다 느슨하면 그 느슨함이 곧 위 실패 모드의 입구다(C4)."""
    build = _BUILD.read_text(encoding="utf-8", errors="replace")
    # 정본 `VERSION_RE` 의 상한(`{0,3}`)이 빌드 쪽에도 있어야 한다 — `[0-9.]*` 류는
    # `1.2.3.4.5` 를 통과시키고, 그 값이면 클라이언트가 어떤 매니페스트에도 반응하지 않는다.
    m = re.search(r"CLIENT_VERSION\\s\*=\\s\*\\\"\(\[0-9\]\+\(\?:", build)
    assert m or "{0,3}" in build, "빌드의 버전 정규식이 정본과 같은 모양이 아니다"


def test_iss_version_matches_the_canon():
    iss = _ISS.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'#define\s+AppVersion\s+"([0-9]+(?:\.[0-9]+){0,3})"', iss)
    assert m, ".iss 에 AppVersion 폴백이 없다"
    assert m.group(1) == version.CLIENT_VERSION


def test_build_injects_the_canon_version_into_the_installer():
    """폴백을 그대로 쓰면 소스에서 버전을 올려도 설치기 파일명이 그대로다."""
    src = _BUILD.read_text(encoding="utf-8", errors="replace")
    assert "/DAppVersion=" in src
    assert "_client_version()" in src


def test_build_reads_the_version_without_importing_the_package():
    """빌드 머신에서 `client` 가 임포트되지 않아 **버전 없이 성공**하는 경로를 막는다.

    ⚠ 「그 문자열이 파일에 없다」로 단언하지 않는다 — 바로 위 문단이 그 문자열을 설명하려고
    쓰고 있어서 자기 설명이 자기 단언을 깬다(§16.7 G11-a). **import 문의 모양**을 본다.
    """
    src = _BUILD.read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"^\s*(?:import|from)\s+client\b", src, re.M)
    assert "CLIENT_VERSION" in src


# ── 9. 브리지 계약 ──────────────────────────────────────────────────────────────

def test_update_apply_is_a_confirmed_action():
    """이 프로그램 전체를 갈아 끼우는 설치기다 — 사람 없이 돌지 않는다.

    ⚠ **두 판정축이 있다** (2026-09-07 두 사용자 결정): `NOTIFIED`(연결·로그인 — 끝난 뒤
    알린다)와 `CONFIRMED`(업데이트 설치 — 미리 묻는다). 업데이트가 알림 쪽으로 넘어가면
    미서명 설치기가 사람 없이 도는 것이 정상 동작이 된다.
    """
    assert "update_apply" in bridge_mod.CONFIRMED
    assert "update_apply" not in bridge_mod.NOTIFIED
    # 조회는 어느 축에도 없다 — 조회까지 물으면 사람이 확인을 습관적으로 넘긴다.
    assert "update_check" not in bridge_mod.CONFIRMED
    assert "update_check" not in bridge_mod.NOTIFIED
    # 연결·로그인은 사용자 결정대로 알림 쪽이다(되묻지 않는다).
    assert {"login", "connect"} <= bridge_mod.NOTIFIED
    assert not ({"login", "connect"} & bridge_mod.CONFIRMED)


def test_confirm_text_for_update_reports_the_version_it_will_install():
    class _Br:
        pending_update = updater.Update(
            version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
            sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
        connected = False

    text = bridge_mod._confirm_text("update_apply", {}, bridge=_Br())
    assert "9.9.9" in text


def test_confirm_text_for_update_without_a_pending_check_does_not_pretend():
    text = bridge_mod._confirm_text("update_apply", {}, bridge=None)
    assert "확인" in text and "9.9.9" not in text


def test_update_now_refuses_in_a_source_tree(tmp_path, monkeypatch):
    """개발 트리에 설치기를 덮어씌우면 방금 고친 코드가 조용히 가려진다.

    ⚠ 판정은 `updater.run_flow` 안에 있다 — 순서의 정본이 하나이므로 그 게이트도 하나다.
    """
    monkeypatch.setattr(updater, "running_frozen", lambda: False)
    plan = core.ConnectPlan(base="https://x.example", token="t", home=tmp_path / "home")
    br = bridge_mod.Bridge(plan, confirm=lambda _m: True)
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    try:
        got = br.update_now(confirmed=True, target=upd)
    finally:
        br.stop()
    assert got["ok"] is False and got["error"] == "not_frozen"


def test_update_check_reports_the_current_version(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda _h: None)
    plan = core.ConnectPlan(base="https://x.example", token="t", home=tmp_path / "home")
    br = bridge_mod.Bridge(plan, confirm=lambda _m: True)
    try:
        got = br.act("update_check", {})
    finally:
        br.stop()
    assert got["ok"] and got["available"] is None
    assert got["current"] == version.CLIENT_VERSION


def test_status_carries_the_version_and_pending_update(tmp_path):
    plan = core.ConnectPlan(base="https://x.example", token="t", home=tmp_path / "home")
    br = bridge_mod.Bridge(plan, confirm=lambda _m: True)
    br.pending_update = updater.Update(
        version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
        sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    try:
        got = br.act("status", {})
    finally:
        br.stop()
    assert got["version"] == version.CLIENT_VERSION
    assert got["update"]["version"] == "9.9.9"


def test_quit_soon_is_a_noop_without_a_shell(tmp_path):
    """껍데기가 종료 손잡이를 주지 않았으면 **조용히 아무것도 하지 않는다**."""
    plan = core.ConnectPlan(base="https://x.example", token="t", home=tmp_path / "home")
    br = bridge_mod.Bridge(plan, confirm=lambda _m: True)
    try:
        br._quit_soon(delay=0.01)     # 예외 없이 끝나야 한다
    finally:
        br.stop()


# ── 10. 트레이 경로가 «아무 일도 없다» 를 만들지 않는다 ─────────────────────────

def _fake_bridge_for_flow(result: dict):
    class _Br:
        def __init__(self):
            self.plan = type("P", (), {"home": Path("/nonexistent-home")})()
            self.pending_update = None
            self.calls = 0

        def update_now(self, confirmed=False, target=None, require_idle=False):
            self.calls += 1
            return result

    return _Br()


def _run_flow(monkeypatch, found, result):
    """`gui._update_flow` 를 헤드리스에서 구동하고 `tell()` 로 나간 문구를 돌려준다."""
    from client import gui  # noqa: PLC0415 — tkinter 는 이 시점에만 필요하다

    said: list[str] = []
    monkeypatch.setattr(gui, "tell", lambda msg, *a, **k: said.append(msg))
    monkeypatch.setattr(gui.updater, "check_detail", lambda _h, **k: (found, ""))
    monkeypatch.setattr(gui.updater, "mark_checked", lambda _h, **k: None)
    monkeypatch.setattr(gui.updater, "log", lambda _h, _l: None)
    br = _fake_bridge_for_flow(result)
    gui._update_flow(br)
    return said, br


def test_tray_says_so_when_already_up_to_date(monkeypatch):
    said, br = _run_flow(monkeypatch, None, {"ok": True})
    assert said and "최신" in said[0]
    assert br.calls == 0, "최신인데 적용을 시도했다"


def test_tray_says_so_when_the_update_fails(monkeypatch):
    """확인창에서 [예] 를 눌렀는데 **아무 일도 일어나지 않는** 상태를 만들지 않는다.

    이 경로에는 로그를 보여 줄 패널이 없다 — 실패를 `_say` 에만 남기면 사용자는 자기가
    승인한 동작의 결과를 어디서도 볼 수 없다.
    """
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    said, br = _run_flow(monkeypatch, upd,
                         {"ok": False, "error": "download_failed",
                          "detail": "무결성 대조에 실패했습니다"})
    assert br.calls == 1
    assert said and "무결성" in said[0]


def test_tray_stays_quiet_when_the_user_declined(monkeypatch):
    """자기 선택을 되돌려 알리는 대화상자는 소음이다."""
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    said, br = _run_flow(monkeypatch, upd, {"ok": False, "error": "declined"})
    assert br.calls == 1
    assert said == []


def test_tray_stays_quiet_on_success_because_the_app_is_restarting(monkeypatch):
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=updater.MIN_SETUP_BYTES)
    said, br = _run_flow(monkeypatch, upd, {"ok": True, "restarting": True})
    assert br.calls == 1
    assert said == []


# ── 11. 확인이 실제로 집행되는가 (적대 리뷰 F3·F4·C6) ───────────────────────────

def _frozen_bridge(tmp_path, monkeypatch, confirm=lambda _m: True):
    monkeypatch.setattr(updater, "running_frozen", lambda: True)
    plan = core.ConnectPlan(base="https://x.example", token="t", home=tmp_path / "home")
    return bridge_mod.Bridge(plan, confirm=confirm)


def _pending(v: str = "9.9.9") -> updater.Update:
    return updater.Update(version=v, filename=f"DQAConnect-Setup-{v}.exe",
                          sha256="0" * 64, size=updater.MIN_SETUP_BYTES)


def test_declining_the_confirm_downloads_nothing(tmp_path, monkeypatch):
    """`DANGEROUS` 멤버십만 단언하면 그 게이트가 **실제로 막는지**는 보지 않는다(C6)."""
    touched: list = []
    monkeypatch.setattr(updater, "download",
                        lambda *a, **k: touched.append(a) or None)
    br = _frozen_bridge(tmp_path, monkeypatch, confirm=lambda _m: False)
    br.pending_update = _pending()
    try:
        got = br.act("update_apply", {})
    finally:
        br.stop()
    assert got["ok"] is False and got["error"] == "declined"
    assert touched == [], "확인을 거절했는데 내려받았다"


def test_apply_refuses_when_nothing_was_checked(tmp_path, monkeypatch):
    """확인창이 「받을 버전을 모른다」고 말한 상태에서 [예] 한 번이 임의 버전을 실행했다(F3).

    런타임 probe 로 재현된 결함이다 — 사용자가 승인한 대상과 실제로 실행되는 대상이 갈렸다.
    """
    called: list = []
    monkeypatch.setattr(updater, "check_detail",
                        lambda *a, **k: called.append(1) or (_pending(), ""))
    monkeypatch.setattr(updater, "download",
                        lambda *a, **k: called.append("dl") or None)
    br = _frozen_bridge(tmp_path, monkeypatch)
    br.pending_update = None
    try:
        got = br.act("update_apply", {})
    finally:
        br.stop()
    assert got["ok"] is False and got["error"] == "no_pending"
    assert called == [], "확인한 것이 없는데 조회·내려받기로 진행했다"


def test_apply_installs_the_version_the_dialog_named(tmp_path, monkeypatch):
    """확인창이 떠 있는 사이 `update_check` 가 `pending_update` 를 갈아 끼워도(§3-7),
    설치되는 것은 **확인 시점에 고정한** 그것이다."""
    seen: list = []
    monkeypatch.setattr(updater, "download",
                        lambda _h, upd, **k: seen.append(upd.version) or None)

    swapped = _pending("8.8.8")

    def _confirm(_m):
        br.pending_update = swapped      # 확인창이 떠 있는 사이 다른 요청이 바꿔치기
        return True

    br = _frozen_bridge(tmp_path, monkeypatch, confirm=_confirm)
    br.pending_update = _pending("9.9.9")
    try:
        br.act("update_apply", {})
    finally:
        br.stop()
    assert seen == ["9.9.9"], f"확인창이 말한 버전과 다른 것을 받았다: {seen}"


def test_the_unattended_path_defers_while_connected(tmp_path, monkeypatch):
    """확인창이 없는 자동 경로에는 「지금 끊긴다」를 판단할 사람이 없다(F4, 규율 6)."""
    touched: list = []
    monkeypatch.setattr(updater, "download",
                        lambda *a, **k: touched.append(a) or None)
    br = _frozen_bridge(tmp_path, monkeypatch)

    class _P:
        def poll(self): return None      # 러너가 살아 있다 = 일하는 중

    br._runner_proc = _P()
    try:
        got = br.update_now(confirmed=True, target=_pending(), require_idle=True)
    finally:
        br.stop()
    assert got["ok"] is False and got["error"] == "busy"
    assert touched == [], "답변 중인데 업데이트를 진행했다"


def test_the_confirmed_human_path_is_not_blocked_while_connected(tmp_path, monkeypatch):
    """사람이 보는 경로에서는 **사실을 말하고 결정은 사람이 한다** — 막지 않는다."""
    monkeypatch.setattr(updater, "download", lambda *a, **k: None)
    br = _frozen_bridge(tmp_path, monkeypatch)

    class _P:
        def poll(self): return None

    br._runner_proc = _P()
    try:
        got = br.update_now(confirmed=True, target=_pending())
    finally:
        br.stop()
    assert got["error"] == "download_failed", got   # busy 로 막히지 않았다


def test_confirm_text_warns_when_the_source_differs_from_the_bundled_address(tmp_path,
                                                                            monkeypatch):
    """TOFU 고정 주소가 동봉된 배포 주소와 다르면 **두 주소를 나란히 보인다**(F5)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.pin_server(home, "https://pinned.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: "https://bundled.example")
    text = updater.confirm_text(_pending(), connected=False, home=home)
    assert "pinned.example" in text and "bundled.example" in text
    assert "아니요" in text


# ── 12. 설치 결과의 관측면 (적대 리뷰 F1) ───────────────────────────────────────

def test_a_failed_install_is_reported_on_the_next_start(tmp_path):
    """설치기를 띄운 것과 설치가 된 것은 다르다 — 다시 뜬 프로세스가 **버전으로** 대조한다."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    updater.mark_pending_install(home, "9.9.9")
    said = updater.settle_pending_install(home, current="1.1.0")
    assert said and "9.9.9" in said and "1.1.0" in said
    # 한 번 말했으면 표식은 사라진다 — 매 기동마다 같은 말을 반복하지 않는다.
    assert updater.settle_pending_install(home, current="1.1.0") is None


def test_a_successful_install_says_nothing(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    updater.mark_pending_install(home, "9.9.9")
    assert updater.settle_pending_install(home, current="9.9.9") is None


def test_no_attempt_means_no_message(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    assert updater.settle_pending_install(home, current="1.1.0") is None


def test_a_failed_check_is_not_reported_as_up_to_date(tmp_path, monkeypatch):
    """확인 실패를 「최신입니다」로 말하면, 못 받는 머신이 스스로를 최신으로 믿는다(§3-3)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "pinned_server", lambda _h: "https://x.example")
    monkeypatch.setattr(core, "bundled_service_base", lambda: None)
    # CA 부재 → 확인 자체가 성립하지 않는다
    found, why = updater.check_detail(home)
    assert found is None and why == "no-ca"


def test_a_failed_check_shortens_the_retry_interval(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    now = 1_000_000.0
    updater.mark_checked(home, now=now, error="TimeoutError")
    # 성공 간격(4시간)은 안 됐지만 실패 간격(30분)은 지났다
    assert updater.due(home, now=now + updater.RETRY_INTERVAL_SEC + 1)
    assert not updater.due(home, now=now + 60)


def test_a_relaunch_owner_is_single(tmp_path):
    """재기동 입구가 둘이면 우리가 아직 살아 있는 사이 새 인스턴스가 잠금에 막힌다(C5)."""
    assert "/RESTARTAPPLICATIONS" not in updater.SILENT_ARGS
    assert "/RELAUNCH" in updater.SILENT_ARGS


def test_downloads_land_in_one_fixed_place(tmp_path):
    """매 회 새 임시 디렉토리를 쓰면 릴리스마다 수십 MB 가 영구 누적된다(C3)."""
    home = tmp_path / "home"
    assert updater.download_dir(home) == home / "update"


def test_a_stale_pending_marker_is_not_reported_as_failure(tmp_path):
    """오래된 표식으로 「실패했다」고 단정하지 않는다.

    그 사이에 사용자가 손으로 설치·제거·되돌렸을 수 있어 우리 주장의 근거가 사라진다 —
    모르는 것을 단정하는 쪽이 침묵보다 나쁘다(§16.7 G7-c).
    """
    import json as _json

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    updater.mark_pending_install(home, "9.9.9")
    # 표식을 유효 기간보다 오래된 것으로 되돌린다.
    doc = _json.loads((home / "update.json").read_text(encoding="utf-8"))
    doc["pending_at"] = doc["pending_at"] - updater.PENDING_MAX_AGE_SEC - 1
    (home / "update.json").write_text(_json.dumps(doc), encoding="utf-8")

    assert updater.settle_pending_install(home, current="1.1.0") is None
    # 판정하지 않았다는 사실은 **기록에는 남는다** — 조용히 사라지지 않는다.
    assert "stale marker" in (home / "update.log").read_text(encoding="utf-8")


class _FakeResp:
    """`updater._open` 자리에 끼우는 가짜 스트림. 청크마다 잠깐 양보해 경합을 만든다."""

    def __init__(self, payload: bytes, status: int = 200, chunk: int = 64 * 1024,
                 stall: float = 0.0):
        self._buf, self.status, self._chunk, self._stall = payload, status, chunk, stall
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        import time as _t
        if self._stall:
            _t.sleep(self._stall)
        take = self._chunk if n is None or n < 0 else min(n, self._chunk)
        out = self._buf[self._pos:self._pos + take]
        self._pos += len(out)
        return out

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _armed_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    core.pin_server(home, "https://real.example")
    (home / "rootCA.crt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(core, "bundled_service_base", lambda: None)
    return home


def test_download_lands_the_exact_bytes_it_verified(tmp_path, monkeypatch):
    """성공 경로의 **행위** 커버리지 — 종전에는 소스 문자열 단언뿐이었다(C-5)."""
    home = _armed_home(tmp_path, monkeypatch)
    payload = b"MZ" + b"G" * (updater.MIN_SETUP_BYTES - 2)
    upd = _update_of(payload)
    monkeypatch.setattr(updater, "_open", lambda *a, **k: _FakeResp(payload))
    got = updater.download(home, upd)
    assert got is not None
    assert got.read_bytes() == payload


def test_download_discards_a_mismatching_stream_and_leaves_no_part(tmp_path, monkeypatch):
    home = _armed_home(tmp_path, monkeypatch)
    payload = b"MZ" + b"G" * (updater.MIN_SETUP_BYTES - 2)
    upd = updater.Update(version="9.9.9", filename="DQAConnect-Setup-9.9.9.exe",
                         sha256="0" * 64, size=len(payload))
    monkeypatch.setattr(updater, "_open", lambda *a, **k: _FakeResp(payload))
    assert updater.download(home, upd) is None
    leftovers = list(updater.download_dir(home).glob("*.part"))
    assert leftovers == [], f".part 잔재가 남았다: {leftovers}"


def test_download_stops_reading_when_the_stream_exceeds_the_declared_size(tmp_path,
                                                                         monkeypatch):
    home = _armed_home(tmp_path, monkeypatch)
    payload = b"MZ" + b"G" * (updater.MIN_SETUP_BYTES - 2)
    upd = _update_of(payload)
    # 선언보다 큰 스트림 — 읽기 자체가 끊겨야 한다.
    monkeypatch.setattr(updater, "_open",
                        lambda *a, **k: _FakeResp(payload + b"X" * 4096))
    assert updater.download(home, upd) is None
    assert list(updater.download_dir(home).glob("*.part")) == []


def test_two_concurrent_flows_each_get_their_own_verified_bytes(tmp_path, monkeypatch):
    """**P1-A 회귀 게이트.** 각 흐름이 돌려준 경로의 내용이 그 흐름이 검사한 바이트여야 한다.

    적대 리뷰가 두 스레드로 재현한 결함이다 — `.part` 이름이 PID 기준이라 같은 프로세스의
    두 스레드가 한 파일을 공유했고, T1 이 검사한 스트림과 T1 이 돌려준 경로의 내용이
    **완전히 달랐다**. 그 경로는 그대로 `apply()` 로 실행된다.

    ⚠ 두 흐름이 같은 `filename` 을 받는 것은 실재 조건이다 — `publish_release.py` 는
    「같은 버전의 다른 파일」을 경고만 하고 허용한다고 자기 docstring 에 적어 두었다.
    """
    import threading as _th

    home = _armed_home(tmp_path, monkeypatch)
    a = b"MZ" + b"A" * (updater.MIN_SETUP_BYTES - 2)
    b = b"MZ" + b"C" * (updater.MIN_SETUP_BYTES - 2)
    upd_a, upd_b = _update_of(a), _update_of(b)
    # 두 흐름은 **같은 파일명**을 받는다(같은 버전, 다른 내용).
    assert upd_a.filename == upd_b.filename

    streams = {"A": a, "C": b}

    def fake_open(url, ca, timeout):
        # 어느 흐름인지 스레드 이름으로 가른다.
        key = "A" if _th.current_thread().name == "flowA" else "C"
        return _FakeResp(streams[key], stall=0.002)

    monkeypatch.setattr(updater, "_open", fake_open)
    out: dict = {}

    def run(name, upd):
        out[name] = updater.download(home, upd)

    t1 = _th.Thread(target=run, args=("A", upd_a), name="flowA")
    t2 = _th.Thread(target=run, args=("C", upd_b), name="flowC")
    t1.start(); t2.start(); t1.join(30); t2.join(30)

    assert out["A"] is not None and out["C"] is not None
    assert out["A"] != out["C"], "두 흐름이 같은 경로를 돌려줬다 — 하나가 다른 하나를 덮는다"
    assert out["A"].read_bytes() == a, "A 가 검사한 바이트와 A 가 돌려준 파일이 다르다"
    assert out["C"].read_bytes() == b, "C 가 검사한 바이트와 C 가 돌려준 파일이 다르다"


def test_verify_file_reads_the_file_that_will_be_executed(tmp_path):
    """§3-b — 판정면과 실행면을 일치시키는 자리."""
    payload = b"MZ" + b"G" * (updater.MIN_SETUP_BYTES - 2)
    upd = _update_of(payload)
    good = tmp_path / "good.exe"
    good.write_bytes(payload)
    assert updater.verify_file(good, upd)
    # 검사 뒤 파일이 바뀌면 **거짓**이다 — 그것이 이 함수의 존재 이유다.
    good.write_bytes(b"MZ" + b"X" * (updater.MIN_SETUP_BYTES - 2))
    assert not updater.verify_file(good, upd)


def test_only_one_update_flow_runs_at_a_time(tmp_path, monkeypatch):
    """입구가 셋이다 — 게이트가 없으면 미서명 설치기 **둘이 동시에** 무음으로 돈다(P1-A)."""
    import threading as _th

    home = _armed_home(tmp_path, monkeypatch)
    monkeypatch.setattr(updater, "running_frozen", lambda: True)
    entered = _th.Event()
    release = _th.Event()

    def slow_download(_h, _u, **_k):
        entered.set()
        release.wait(10)
        return None

    monkeypatch.setattr(updater, "download", slow_download)
    upd = _update_of(b"MZ" + b"G" * (updater.MIN_SETUP_BYTES - 2))
    first: dict = {}
    _th.Thread(target=lambda: first.update(
        updater.run_flow(home, target=upd)), daemon=True).start()
    assert entered.wait(10), "첫 흐름이 시작되지 않았다"
    second = updater.run_flow(home, target=upd)
    release.set()
    assert second["error"] == "already_running", second
