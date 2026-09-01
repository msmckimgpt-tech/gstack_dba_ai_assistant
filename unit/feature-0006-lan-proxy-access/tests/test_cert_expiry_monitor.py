"""`bin/cert-expiry-check.sh` — 사내 TLS 인증서 만료 감시의 동작과 경계를 잠근다.

## 왜 이 감시가 따로 있는가

`bin/deploy-web.sh` 의 `preflight_tls()` 가 이미 leaf 만료를 본다. 그런데 그것은 **배포할 때만**
돈다 — 배포가 없으면 신호도 없고, 그 사이 만료되면 첫 신호가 **전면 outage** 다. 게다가 그
preflight 는 **Root CA 를 아예 보지 않는다**(CA 만료는 테스터 전원 재설치라 회복 비용이 훨씬 크다).

    deploy-web.sh preflight = 게이트 (배포 직전 · leaf 14일 · WARN 후 배포 계속)
    cert-expiry-check.sh    = 감시   (주기 실행 · leaf 30일 / CA 180일 기본 · exit 로 알림)

## 이 스위트가 텍스트가 아니라 **동작**을 보는 이유 (§16.7 G11)

임계 판정은 «소스에 그 숫자가 있는가» 로 확인할 수 없다. 실제로 그 경계에서 갈리는지는 **그
경계에 걸친 인증서를 만들어 돌려 봐야** 안다. 그래서 openssl 로 수명이 다른 cert 를 생성해
종료코드를 본다 — 텍스트 검사가 아니라 실행 결과다.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "bin" / "cert-expiry-check.sh"
_DEPLOY = _REPO / "bin" / "deploy-web.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="openssl 미설치 — 동작 검증 불가"
)


def _gen(path: Path, days: int, cn: str = "testhost") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", "/dev/null", "-out", str(path), "-days", str(days),
         "-subj", f"/CN={cn}"],
        check=True, capture_output=True,
    )


def _run(certs_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(_SCRIPT), "--certs-dir", str(certs_dir), "--host", "testhost", *extra],
        capture_output=True, text=True,
    )


@pytest.fixture()
def certs(tmp_path: Path) -> Path:
    d = tmp_path / "certs"
    _gen(d / "rootCA.pem", 3650)
    _gen(d / "testhost" / "fullchain.pem", 3650)
    return d


def test_script_exists_and_is_executable():
    assert _SCRIPT.is_file(), f"{_SCRIPT} 가 없다"
    assert _SCRIPT.stat().st_mode & 0o111, "실행 권한이 없다 — cron 이 부르지 못한다"


# ── 임계 동작 (생성한 cert 로 실제 구동) ──────────────────────────────────────

@pytest.mark.parametrize("days,expected,label", [
    (100, 0, "여유 — 정상"),
    (20, 1, "30일 이내 — WARN"),
    (3, 2, "7일 이내 — CRITICAL"),
])
def test_leaf_thresholds_split_at_the_right_boundaries(certs, days, expected, label):
    """leaf 수명에 따라 종료코드가 0/1/2 로 갈린다 — cron 알림이 이 코드로 갈린다."""
    _gen(certs / "testhost" / "fullchain.pem", days)
    r = _run(certs)
    assert r.returncode == expected, (
        f"leaf {days}일 → exit {r.returncode} (기대 {expected}, {label})\n"
        f"stdout={r.stdout}\nstderr={r.stderr}"
    )


def test_root_ca_is_checked_too(certs):
    """Root CA 축 — deploy preflight 가 **보지 않는** 면이라 여기가 유일한 감시다.

    leaf 는 넉넉한데 CA 만 임박한 상태를 만들어, 그 사실만으로 경보가 뜨는지 본다.
    """
    _gen(certs / "testhost" / "fullchain.pem", 3650)   # leaf 는 여유
    _gen(certs / "rootCA.pem", 10)                      # CA 만 임박(<30d crit)
    r = _run(certs)
    assert r.returncode == 2, f"CA 임박이 CRITICAL 로 잡히지 않았다 (exit={r.returncode})"
    assert "rootCA" in (r.stdout + r.stderr), "경보 메시지가 rootCA 축을 지목하지 않는다"


def test_missing_cert_is_reported_not_silently_passed(tmp_path):
    """파일이 없으면 «정상» 이 아니라 경보다 — 부재를 통과시키면 감시가 fail-open 이 된다."""
    empty = tmp_path / "nope"
    empty.mkdir()
    r = _run(empty)
    assert r.returncode >= 1, f"cert 부재인데 exit={r.returncode} 로 통과했다"


# ── 게이트와의 관계 — 드리프트 잠금 ───────────────────────────────────────────

def test_monitor_threshold_cannot_be_narrower_than_the_deploy_gate(certs):
    """감시가 게이트보다 늦게 울리면 아무것도 더해 주지 않는다 — 스크립트가 거절해야 한다."""
    r = _run(certs, "--leaf-warn", "5")
    assert r.returncode == 3, f"게이트보다 좁은 임계를 받아들였다 (exit={r.returncode})"
    assert "게이트" in r.stderr, "거절 사유가 게이트 관계를 설명하지 않는다"


def test_deploy_gate_constant_still_matches_what_the_monitor_assumes():
    """감시는 게이트가 **14일**이라고 가정한다. 그 가정이 배포 스파인과 어긋나면 잠금이 썩는다.

    `deploy-web.sh` 의 `-checkend 1209600`(=14일)이 바뀌면 이 테스트가 FAIL 하고, 그때
    `cert-expiry-check.sh` 의 `DEPLOY_GATE_DAYS` 도 같이 고치게 된다 — 두 파일이 조용히
    갈라지는 것을 막는 유일한 연결이다.
    """
    deploy_src = _DEPLOY.read_text(encoding="utf-8")
    code_lines = [ln for ln in deploy_src.splitlines() if not ln.lstrip().startswith("#")]
    assert any("checkend 1209600" in ln for ln in code_lines), (
        "deploy-web.sh 의 leaf 만료 게이트가 더 이상 1209600초(14일)가 아니다 — "
        "cert-expiry-check.sh 의 DEPLOY_GATE_DAYS 를 함께 갱신하라"
    )
    mon_lines = [ln for ln in _SCRIPT.read_text(encoding="utf-8").splitlines()
                 if not ln.lstrip().startswith("#")]
    assert any("DEPLOY_GATE_DAYS=14" in ln.replace(" ", "") for ln in mon_lines), (
        "cert-expiry-check.sh 의 DEPLOY_GATE_DAYS 가 14 가 아니다 — deploy-web.sh 게이트와 어긋난다"
    )


def test_default_thresholds_are_wider_than_the_gate(certs):
    """기본값으로 돌렸을 때 게이트(14일)보다 먼저 우는가 — 20일 cert 로 확인.

    기본 leaf-warn 이 14 이하로 좁아지면 이 단언이 FAIL 한다.
    """
    _gen(certs / "testhost" / "fullchain.pem", 20)
    r = _run(certs)
    assert r.returncode == 1, (
        f"20일 남은 leaf 를 기본 임계가 경고하지 않았다 (exit={r.returncode}) — "
        "감시가 배포 게이트(14일)보다 늦게 운다"
    )
