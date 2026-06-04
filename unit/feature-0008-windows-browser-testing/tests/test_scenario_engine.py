"""feature-0008 win-browser.py 시나리오 엔진 단위 테스트.

connect_over_cdp 자체는 표준 Playwright API 이므로, 본 테스트는 드라이버의
bespoke 로직 — 시나리오 step dispatch (`_run_step`) 와 브리지 endpoint 자동 감지
(`candidate_endpoints`) — 을 fake page 로 검증한다. 실제 CDP wire 는 브리지
setup (bin/win-browser-setup.ps1 또는 mirrored) 가 구성된 환경에서만 동작하며,
`doctor` 가 이를 게이팅한다.

실행:
  pytest unit/feature-0008-windows-browser-testing/tests
"""
import importlib.util
import os

import pytest

# bin/win-browser.py 는 하이픈 파일명이라 import 불가 — importlib 로 로드.
_HERE = os.path.dirname(__file__)
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_DRIVER = os.path.join(_REPO_ROOT, "bin", "win-browser.py")
_spec = importlib.util.spec_from_file_location("win_browser", _DRIVER)
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)


class _Resp:
    status = 200


class FakePage:
    """Playwright Page 의 최소 stub — 호출을 기록한다."""

    def __init__(self, *, text_map=None, title="FakeTitle"):
        self.calls = []
        self._text_map = text_map or {}
        self._title = title

    def goto(self, url, wait_until="domcontentloaded", timeout=0):
        self.calls.append(("goto", url, wait_until))
        return _Resp()

    def title(self):
        return self._title

    def click(self, selector, timeout=0):
        self.calls.append(("click", selector))

    def fill(self, selector, value, timeout=0):
        self.calls.append(("fill", selector, value))

    def type(self, selector, text, timeout=0):
        self.calls.append(("type", selector, text))

    def press(self, selector, key, timeout=0):
        self.calls.append(("press", selector, key))

    def hover(self, selector, timeout=0):
        self.calls.append(("hover", selector))

    def wait_for_selector(self, selector, state=None, timeout=0):
        self.calls.append(("wait_for_selector", selector, state))
        if selector == "#missing":
            raise RuntimeError("timeout")

    def wait_for_timeout(self, timeout=0):
        self.calls.append(("wait_for_timeout", timeout))

    def evaluate(self, script):
        self.calls.append(("evaluate", script))
        return "evaluated:" + script

    def text_content(self, selector):
        return self._text_map.get(selector, "")

    def screenshot(self, path=None, full_page=True):
        self.calls.append(("screenshot", path, full_page))
        # 캡처 흉내 — 실제 파일 생성 (디렉토리 생성 책임은 _run_step).
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n")


def test_goto_dispatch():
    page = FakePage()
    rec = wb._run_step(page, {"action": "goto", "url": "/login"}, "http://localhost:18080", "/tmp/x", 1)
    assert rec["ok"] is True
    assert rec["url"] == "http://localhost:18080/login"
    assert ("goto", "http://localhost:18080/login", "domcontentloaded") in page.calls
    assert rec["status"] == 200


def test_absolute_url_passthrough():
    page = FakePage()
    rec = wb._run_step(page, {"action": "goto", "url": "https://example.com/x"}, "http://localhost:18080", "/tmp/x", 1)
    assert rec["url"] == "https://example.com/x"


def test_type_and_click():
    page = FakePage()
    wb._run_step(page, {"action": "type", "selector": "#email", "text": "a@b.c"}, "", "/tmp/x", 1)
    wb._run_step(page, {"action": "click", "selector": "button"}, "", "/tmp/x", 2)
    assert ("fill", "#email", "") in page.calls       # clear 먼저
    assert ("type", "#email", "a@b.c") in page.calls
    assert ("click", "button") in page.calls


def test_assert_text_pass_and_fail():
    page = FakePage(text_map={"h1": "Welcome Dashboard"})
    ok = wb._run_step(page, {"action": "assert_text", "selector": "h1", "contains": "Dashboard"}, "", "/tmp/x", 1)
    assert ok["ok"] is True
    bad = wb._run_step(page, {"action": "assert_text", "selector": "h1", "contains": "Nope"}, "", "/tmp/x", 2)
    assert bad["ok"] is False
    assert bad["error"] == "assert_text_failed"


def test_assert_visible_fail_on_missing():
    page = FakePage()
    rec = wb._run_step(page, {"action": "assert_visible", "selector": "#missing"}, "", "/tmp/x", 1)
    assert rec["ok"] is False
    assert rec["error"] == "not_visible"


def test_screenshot_writes_file(tmp_path):
    page = FakePage()
    rec = wb._run_step(page, {"action": "screenshot", "path": "shot.png"}, "", str(tmp_path), 3)
    assert rec["ok"] is True
    assert os.path.isfile(rec["path"])


def test_unknown_action():
    page = FakePage()
    rec = wb._run_step(page, {"action": "frobnicate"}, "", "/tmp/x", 1)
    assert rec["ok"] is False
    assert rec["error"].startswith("unknown_action")


def test_eval_dispatch():
    page = FakePage()
    rec = wb._run_step(page, {"action": "eval", "script": "document.title"}, "", "/tmp/x", 1)
    assert rec["result"] == "evaluated:document.title"


def test_candidate_endpoints_includes_relay(monkeypatch):
    monkeypatch.setattr(wb, "win_host_ip", lambda: "172.28.64.1")
    cands = wb.candidate_endpoints()
    modes = {m for m, _ in cands}
    eps = {ep for _, ep in cands}
    assert "mirrored" in modes
    assert "relay" in modes
    assert f"http://localhost:{wb.CDP_PORT}" in eps
    assert f"http://172.28.64.1:{wb.RELAY_PORT}" in eps


def test_forced_endpoint_overrides(monkeypatch):
    monkeypatch.setenv("WIN_BROWSER_CDP_ENDPOINT", "http://example:9999")
    cands = wb.candidate_endpoints()
    assert cands == [("forced", "http://example:9999")]
