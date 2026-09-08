"""Shell relaunch metadata must not retain launch credentials or opaque icon backgrounds."""
from pathlib import Path
from html.parser import HTMLParser
import re
import subprocess
import sys

import pytest

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from client import branding  # noqa: E402


@pytest.mark.parametrize('frozen', [False, True])
def test_relaunch_drops_credentials_and_keeps_paths_with_spaces(monkeypatch, frozen):
    monkeypatch.setattr(sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(sys, 'executable', '/Program Files/DQA/DQAConnect.exe')
    monkeypatch.setattr(sys, 'argv', ['client', '--token', 'secret-test-token',
                                     'dqa-connect://start?token=secret-in-link'])
    actual = branding.relaunch_command()
    expected = [sys.executable]
    if not frozen:
        expected.append(str(SRC / 'dqa_connect.py'))
    assert actual == subprocess.list2cmdline(expected)
    assert 'secret' not in actual and '--token' not in actual and 'start?' not in actual


def test_application_shortcuts_share_runtime_identity():
    source = (SRC / 'installer/DQAConnect.iss').read_text()
    appid = re.search(r'#define MyAppUserModelID "([^"]+)"', source).group(1)
    assert appid == branding.APP_USER_MODEL_ID
    icons = source.split('[Icons]', 1)[1].split('[Registry]', 1)[0]
    app_shortcuts = [line for line in icons.splitlines()
                     if line.startswith('Name:') and '{#MyAppExe}' in line]
    assert len(app_shortcuts) == 3
    assert all('AppUserModelID: "{#MyAppUserModelID}"' in line for line in app_shortcuts)


def test_web_shells_use_the_same_icon_assets_as_the_native_client():
    web = SRC.parents[2] / 'unit/feature-0003-agent-web-ui/src/static'

    class Icons(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == 'link' and values.get('rel') == 'icon':
                self.urls.append(values['href'])

    for name in ('index', 'admin', 'share', 'ai-connect', 'oauth-callback', 'oauth-consent'):
        parser = Icons()
        parser.feed((web / f'{name}.html').read_text())
        assert set(parser.urls) == {'/static/brand/dqa.ico?v=dev', '/static/brand/dqa.svg?v=dev'}
    for name in ('dqa.ico', 'dqa.svg'):
        assert (web / 'brand' / name).read_bytes() == (SRC / 'client/assets' / name).read_bytes()

    for name, count in (('index', 3), ('admin', 1)):
        html = (web / f'{name}.html').read_text()
        assert html.count('<img src="/static/brand/dqa.svg?v=dev"') == count
        assert '/static/logo-dqa.svg' not in html
