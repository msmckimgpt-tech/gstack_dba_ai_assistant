"""TASK-0228 — datasource SSRF 사설망 경계 토글 회귀 테스트.

배경: 사내 환경은 대부분 사설망 IP(RFC1918, 예: 10.200.50.80)로 DB 연결정보를 운영한다.
`_ssrf_check_host` 의 사설/링크로컬 차단(SSRF 방어)이 정당한 사내 host 도 막는다. 운영자가
`AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 으로 **사설망 경계만** 비활성화할 수 있게 한다.
방어 구성 자체는 코드에 보존(기본 활성, secure-by-default) — env 값으로만 토글한다.

불변식(토글과 무관하게 항상 유지, REV-20260611-0228 Finding A/B/C):
  - 클라우드 메타데이터 IP(169.254.169.254 / 100.100.100.200) 하드차단 — IPv4-mapped IPv6 형 포함.
  - loopback(127.x/::1)·link-local(169.254.x/fe80::)·reserved·multicast 차단(토글은 RFC1918 만 완화).
  - DNS rebinding pin(반환 pinned_ip).

검증:
  S1  토글 미설정(기본) → 사설 IP 차단(secure-by-default).
  S2  토글=1 명시 → 사설 IP 차단.
  S3  토글=0 → 사설 IP(RFC1918) 허용 + pinned_ip 반환.
  S4  토글=0 이어도 메타데이터 IP 는 여전히 차단(불변식). IPv4-mapped 형 + loopback/link-local 포함.
  S5  토글=1 이어도 allowlist 등재 사설 host 는 허용(기존 동작 보존).
  S6  공인 IP 는 토글과 무관하게 항상 허용.
  S7  _ssrf_private_guard_enabled 파싱(0/false/no/off → 비활성, 그 외 → 활성).

`make test` (agent 이미지, --no-deps) 에서 DB 없이 실행. host 를 IP 리터럴로 주면
socket.getaddrinfo 가 네트워크 없이 즉시 반환하므로 외부 의존 없음.
"""
from __future__ import annotations

import app
import pytest


_PRIVATE_IP = "10.200.50.80"      # RFC1918 (사용자 보고 host)
_METADATA_IP = "169.254.169.254"  # 클라우드 메타데이터
_PUBLIC_IP = "8.8.8.8"            # 공인(global) IP — is_private/is_reserved 모두 False


def _clear_guard_env(monkeypatch):
    monkeypatch.delenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_DATASOURCE_HOST_ALLOWLIST", raising=False)


# ── S1: 기본(미설정) = 사설 IP 차단 (secure-by-default) ──────────────────────────
def test_default_blocks_private_ip(monkeypatch):
    _clear_guard_env(monkeypatch)
    ok, reason, pin = app._ssrf_check_host(_PRIVATE_IP)
    assert ok is False
    assert "사설" in reason and _PRIVATE_IP in reason
    assert pin == ""


# ── S2: 토글=1 명시 = 사설 IP 차단 ──────────────────────────────────────────────
def test_explicit_enabled_blocks_private_ip(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "1")
    ok, reason, _ = app._ssrf_check_host(_PRIVATE_IP)
    assert ok is False
    assert "사설" in reason


# ── S3: 토글=0 = 사설 IP 허용 + pinned_ip 반환 ──────────────────────────────────
def test_disabled_allows_private_ip(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host(_PRIVATE_IP)
    assert ok is True
    assert reason == ""
    assert pin == _PRIVATE_IP  # DNS rebinding pin 유지


# ── S4: 토글=0 이어도 메타데이터 IP 는 차단(불변식) ─────────────────────────────
def test_disabled_still_blocks_metadata_ip(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host(_METADATA_IP)
    assert ok is False
    assert "메타데이터" in reason
    assert pin == ""


def test_disabled_still_blocks_alibaba_metadata_ip(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, _ = app._ssrf_check_host("100.100.100.200")
    assert ok is False
    assert "메타데이터" in reason


# ── S4b: REV-0228 Finding A/B — IPv4-mapped IPv6 메타데이터 형도 토글 무관 차단 ──────
@pytest.mark.parametrize("mapped", [
    "::ffff:169.254.169.254",   # AWS/GCP/Azure 메타데이터 IPv4-mapped
    "::ffff:100.100.100.200",   # Alibaba 메타데이터 IPv4-mapped
])
def test_disabled_blocks_ipv4_mapped_metadata(monkeypatch, mapped):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host(mapped)
    assert ok is False
    assert "메타데이터" in reason
    assert pin == ""


@pytest.mark.parametrize("mapped", [
    "::ffff:169.254.169.254",
    "::ffff:100.100.100.200",
])
def test_enabled_blocks_ipv4_mapped_metadata(monkeypatch, mapped):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "1")
    ok, reason, _ = app._ssrf_check_host(mapped)
    assert ok is False
    assert "메타데이터" in reason


# ── S4c: REV-0228 Finding C — 토글 OFF 여도 loopback/link-local 은 차단(RFC1918 만 완화) ─
@pytest.mark.parametrize("host", [
    "127.0.0.1",        # loopback
    "169.254.1.5",      # link-local (메타데이터 아님)
])
def test_disabled_still_blocks_loopback_linklocal(monkeypatch, host):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host(host)
    assert ok is False
    assert pin == ""


@pytest.mark.parametrize("host", ["172.28.64.1", "192.168.1.5", "10.0.0.5"])
def test_disabled_allows_other_rfc1918(monkeypatch, host):
    """토글 OFF 시 다른 RFC1918 대역(172.16/12·192.168/16·10/8)도 허용."""
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host(host)
    assert ok is True
    assert pin == host


# ── S5: 토글=1 이어도 allowlist 등재 사설 host 는 허용(기존 동작 보존) ────────────
def test_enabled_allowlist_private_ip_allowed(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "1")
    monkeypatch.setenv("AGENT_DATASOURCE_HOST_ALLOWLIST", _PRIVATE_IP)
    ok, reason, pin = app._ssrf_check_host(_PRIVATE_IP)
    assert ok is True
    assert pin == _PRIVATE_IP


def test_enabled_allowlist_cidr_private_ip_allowed(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "1")
    monkeypatch.setenv("AGENT_DATASOURCE_HOST_ALLOWLIST", "10.200.50.0/24")
    ok, _, pin = app._ssrf_check_host(_PRIVATE_IP)
    assert ok is True
    assert pin == _PRIVATE_IP


# ── S6: 공인 IP 는 토글과 무관하게 항상 허용 ────────────────────────────────────
@pytest.mark.parametrize("toggle", ["1", "0", None])
def test_public_ip_always_allowed(monkeypatch, toggle):
    _clear_guard_env(monkeypatch)
    if toggle is not None:
        monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", toggle)
    ok, reason, pin = app._ssrf_check_host(_PUBLIC_IP)
    assert ok is True
    assert reason == ""
    assert pin == _PUBLIC_IP


# ── S7: _ssrf_private_guard_enabled 파싱 ────────────────────────────────────────
@pytest.mark.parametrize("val,expected", [
    (None, True),     # 미설정 = 기본 활성
    ("1", True),
    ("true", True),
    ("yes", True),
    ("anything", True),  # 알 수 없는 값 = 보수적 활성
    ("0", False),
    ("false", False),
    ("FALSE", False),
    ("no", False),
    ("off", False),
    (" 0 ", False),   # 공백 trim
])
def test_private_guard_enabled_parsing(monkeypatch, val, expected):
    monkeypatch.delenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", raising=False)
    if val is not None:
        monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", val)
    assert app._ssrf_private_guard_enabled() is expected


# ── 부수: 빈 host 는 토글과 무관하게 거부 ───────────────────────────────────────
def test_empty_host_rejected_regardless(monkeypatch):
    _clear_guard_env(monkeypatch)
    monkeypatch.setenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "0")
    ok, reason, pin = app._ssrf_check_host("")
    assert ok is False
    assert "비어있음" in reason
