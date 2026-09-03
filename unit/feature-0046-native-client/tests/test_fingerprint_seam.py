"""서버가 **실제로 내는 모양**의 지문을 클라이언트가 받아들이는지 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

실제 Windows 에서 GUI 버튼을 눌러 연결을 시도했더니 여기서 멈췄다:

    CA 지문이 다릅니다.
      기대: F5:B9:C5:81:5C:9B:47:A9:…:3C:1C      ← 서버가 준 값
      실제: f5b9c5815c9b47a99a499e759373f11c…    ← 클라이언트가 계산한 값

**두 값은 같은 지문이었다.** 서버는 OpenSSL 관례(대문자·콜론)로 내고 클라이언트는
`hashlib` 기본(소문자·구분자 없음)으로 계산하는데, 비교가 `.lower()` 만 했다. 즉
클라이언트는 **누구에게서도 연결에 성공할 수 없었다**.

## 왜 기존 20건이 못 잡았나

`test_client_core.py` 는 `install_ca` 를 자기가 만든 지문으로 호출했다 — 클라이언트가
계산하는 것과 **같은 모양**의 값이라 항상 통과했다. 프로세스 경계 양쪽을 각각 테스트하면
값의 «모양»이 어긋나는 것은 잡히지 않는다. 봉투는 **상대 소스에서 재현**해야 한다.

그래서 이 파일은 서버의 포맷터를 `oauth_as.py` 에서 **읽어 와** 봉투를 만든다. 서버가
형식을 바꾸면 이 테스트가 따라 바뀌고, 클라이언트가 그것을 못 받으면 여기서 깨진다.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_UNIT / "src"))

from client import core  # noqa: E402

_REPO = _UNIT.parents[1]
_SERVER = _REPO / "unit/feature-0003-agent-web-ui/src/routers/oauth_as.py"


def _server_format(digest_hex: str) -> str:
    """서버가 지문을 내는 **그 방식**을 서버 소스에서 확인하고 재현한다.

    리터럴을 손으로 쓰면 서버가 형식을 바꿔도 이 테스트는 옛 모양으로 계속 통과한다.
    """
    src = _SERVER.read_text(encoding="utf-8")
    assert "hashlib.sha256(der).hexdigest().upper()" in src, \
        "서버의 지문 생성 방식이 바뀌었다 — 이 테스트의 전제를 다시 확인할 것"
    assert re.search(r'":"\.join\(hexed\[i:i \+ 2\]', src), \
        "서버가 더 이상 콜론으로 잇지 않는다 — 전제를 다시 확인할 것"
    up = digest_hex.upper()
    return ":".join(up[i:i + 2] for i in range(0, len(up), 2))


# ── 1. 결함 재현: 서버 모양을 클라이언트가 받는가 ──────────────────────────────────

def test_client_accepts_the_shape_the_server_actually_sends():
    """**이 단정이 종전 클라이언트를 잡는다.**"""
    der = b"\x30\x82fake-der-bytes"
    digest = hashlib.sha256(der).hexdigest()
    envelope = _server_format(digest)

    assert ":" in envelope and envelope.isupper() or ":" in envelope, "봉투가 서버 모양이 아니다"
    assert core.normalize_fingerprint(envelope) == core.normalize_fingerprint(digest), \
        f"서버 모양({envelope[:20]}…)과 클라이언트 계산({digest[:20]}…)이 같게 취급되지 않는다"


def test_the_two_shapes_are_not_equal_without_normalization():
    """대조군 — 정규화가 없으면 정말 다르다(테스트가 vacuous 하지 않다는 증명)."""
    digest = hashlib.sha256(b"x").hexdigest()
    envelope = _server_format(digest)
    assert envelope.lower() != digest.lower(), \
        "봉투와 원본이 이미 같다면 이 결함을 재현하지 못한다"


# ── 2. install_ca 를 **서버 봉투**로 구동 ──────────────────────────────────────────

_PEM_DER = b"\x30\x82\x01\x0a\x02\x82\x01\x01\x00pretend-certificate-body"


def _pem(der: bytes) -> bytes:
    import base64
    b64 = base64.b64encode(der)
    return b"-----BEGIN CERTIFICATE-----\n" + b64 + b"\n-----END CERTIFICATE-----\n"


@pytest.fixture()
def plan(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "fetch", lambda url, **kw: _pem(_PEM_DER))
    digest = hashlib.sha256(_PEM_DER).hexdigest()
    return core.ConnectPlan(base="https://h", token="t",
                            ca_sha256=_server_format(digest), home=tmp_path)


def test_install_ca_succeeds_with_server_shaped_fingerprint(plan):
    out = core.install_ca(plan)
    assert out.exists() and out.read_bytes() == _pem(_PEM_DER)


def test_install_ca_still_rejects_a_genuinely_different_certificate(plan):
    """정규화가 **검증을 무력화하지 않았다**는 확인 — 다른 인증서는 여전히 막는다."""
    plan.ca_sha256 = _server_format(hashlib.sha256(b"attacker").hexdigest())
    with pytest.raises(core.IntegrityError):
        core.install_ca(plan)


def test_install_ca_rejects_truncated_fingerprint(plan):
    """정규화가 **접두 일치**로 느슨해지지 않았는지 — 길이가 다르면 불일치다."""
    plan.ca_sha256 = plan.ca_sha256[:20]
    with pytest.raises(core.IntegrityError):
        core.install_ca(plan)


# ── 3. 정규화 자체의 계약 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("given, expect_same", [
    ("AA:BB:CC", True),        # 서버 모양
    ("aabbcc", True),          # 클라이언트 모양
    ("  AA:BB:CC \n", True),   # 복사·붙여넣기로 공백이 섞인 경우
    ("aa-bb-cc", True),        # 하이픈 구분(다른 도구 관례)
    ("AABBCD", False),         # 실제로 다른 값
])
def test_normalize_fingerprint_contract(given, expect_same):
    assert (core.normalize_fingerprint(given) == "aabbcc") is expect_same


def test_normalize_does_not_swallow_case_sensitive_difference():
    """소문자화가 **서로 다른 16진값**을 같게 만들지 않는지."""
    assert core.normalize_fingerprint("AB") != core.normalize_fingerprint("BA")


# ── 4. 두 축이 같은 정규화를 쓰는가 (한쪽만 고쳐지는 것을 막는다) ──────────────────

def test_both_integrity_checks_use_the_same_matcher():
    """`install_ca` 와 `install_runner` 가 **둘 다** `fingerprints_match` 를 쓴다.

    한쪽만 고치면 서버가 러너 체크섬 형식을 바꾸는 날 그 축만 조용히 깨진다. 그리고
    직접 `normalize_fingerprint` 를 부르면 codex 가 지적한 **형식 검증이 빠진다** —
    비교는 반드시 matcher 를 거쳐야 한다.
    """
    src = (_UNIT / "src" / "client" / "core.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for fname in ("install_ca", "install_runner"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == fname)
        calls = {getattr(c.func, "id", None) for c in ast.walk(fn) if isinstance(c, ast.Call)}
        assert "fingerprints_match" in calls, \
            f"{fname} 이 공용 matcher 를 쓰지 않는다 — 축이 갈렸다"
        assert "normalize_fingerprint" not in calls, \
            f"{fname} 이 정규화를 직접 불러 형식 검증을 건너뛴다"


def test_shell_installer_and_client_agree_on_normalization():
    """셸 설치 스크립트와 **같은 정규화**인지 확인한다.

    클라이언트는 셸 경로의 껍데기 교체다(ROADMAP §0.2). 두 경로가 같은 서버 값을 받는데
    한쪽만 통과하면, 사용자는 「스크립트는 되는데 프로그램은 안 된다」를 겪는다 — 실제로
    그랬다. 셸은 `tr 'A-Z' 'a-z' | tr -d ':'` 를 한다.
    """
    sh = (_REPO / "unit/feature-0043-external-llm-bridge/src/bridge_setup.sh"
          ).read_text(encoding="utf-8")
    assert "tr 'A-Z' 'a-z'" in sh and "tr -d ':'" in sh, \
        "셸 쪽 정규화가 바뀌었다 — 클라이언트와 함께 다시 맞출 것"
    digest = hashlib.sha256(b"seam").hexdigest()
    shell_result = _server_format(digest).lower().replace(":", "")
    assert core.normalize_fingerprint(_server_format(digest)) == shell_result


# ── 5. codex 적대 리뷰 반영 (2026-09-03) ──────────────────────────────────────────
#
# 지적: 정규화가 표기만 지우고 **형식은 검증하지 않는다**. 그래서 「둘 다 빈 문자열」이
# 일치가 되는 모양이 남는다. 지금 계산 경로는 항상 64자를 내므로 도달 불가능하지만,
# 무결성 검사가 「우연히 도달 불가」에 기대게 두지 않는다.

def test_both_sides_normalizing_to_empty_is_not_a_match():
    """**핵심 단정** — 기대값이 `":"` 처럼 truthy 하지만 지문이 아닌 경우."""
    assert core.fingerprints_match("", ":") is False
    assert core.fingerprints_match(":", ":") is False
    assert core.fingerprints_match("   ", "") is False


@pytest.mark.parametrize("bad", [
    "",                      # 빈 값
    ":",                     # 구분자만
    "zz" * 32,               # 16진이 아닌 문자
    "ab" * 31,               # 62자 (짧다)
    "ab" * 33,               # 66자 (길다)
    "0x" + "a" * 62,         # 접두사가 섞임
])
def test_malformed_expected_never_matches(bad):
    good = hashlib.sha256(b"real").hexdigest()
    assert core.fingerprints_match(good, bad) is False


def test_valid_pair_still_matches_across_shapes():
    good = hashlib.sha256(b"real").hexdigest()
    assert core.fingerprints_match(good, _server_format(good)) is True
    assert core.fingerprints_match(good, good.upper()) is True
    assert core.fingerprints_match(good, f"  {good}\n") is True


def test_install_ca_rejects_malformed_expected_fingerprint(plan):
    """형식이 아닌 기대값은 **조용히 통과하지 않고** 중단시킨다."""
    plan.ca_sha256 = ":"
    with pytest.raises(core.IntegrityError):
        core.install_ca(plan)
