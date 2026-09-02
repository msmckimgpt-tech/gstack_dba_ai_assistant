"""feature-0043 — 런처의 러너 갱신은 **기동 때 정한 CA** 로만 받는다.

## 무엇이 잘못돼 있었나 (사용자 제보 2026-09-02)

    "'업데이트 필요' 에 따라 자동으로 연결이 진행되었지만, 러너 파일이 그대로라는
     오류 메세지가 나타났습니다."

`TASK-20260902T100000` 이 런처에 러너 최신화를 넣었는데, **Windows 판만** 그것을
`Invoke-WebRequest` 로 했다. IWR 은 `--ca` 로 준 `rootCA.crt` 를 **보지 않고** OS 신뢰
저장소로 검증한다. 그런데 이 설치기는 CA 를 그 저장소에 넣지 않는다 —
`bridge_setup.ps1` 자신이 그렇게 적어 두고(«Windows 는 CA 를 시스템 저장소에 넣지
않고도 요청별로 신뢰시키기 어려워, curl.exe 가 있으면 --cacert 로») 설치 다운로드는
curl·파이썬으로만 한다. **그 스크립트가 굽는 런처만 예외였다.**

결과는 두 방향 모두 나쁘다:

  · 사내 CA 가 OS 저장소에 **없으면** → TLS 실패 → `catch { }` 가 삼킴 →
    갱신이 **조용히** 일어나지 않는다. 재설치해도 같은 자리로 돌아오므로 막다른 길이 된다.
  · 사내 CA 가 OS 저장소에 **있으면** → 우리가 pin 한 CA 와 **무관하게** 통과한다 —
    설치 스크립트가 지킨다고 말하는 그 pin 이 런처에서만 풀린다.

POSIX 판(`launch.sh`)은 `curl --cacert` 로, `agent/selfupdate.py` 는 `cafile=` 로
처음부터 pin 을 지켰다. 축 하나만 어긋나 있었고, 그 축이 사용자가 쓰는 축이었다.

## 이 스위트가 잠그는 것

L1 정본 CA 면 러너가 **실제로 교체된다** (POSIX · curl 부재 → 파이썬 경로).
L2 **엉뚱한 CA 면 교체되지 않는다** — pin 이 살아 있다는 증거. IWR 회귀를 잡는 축이다.
L3 너무 작은 응답(오류 페이지)은 교체하지 않는다.
L4 Windows 판이 IWR 을 쓰지 않고 `rootCA.crt` 를 넘긴다.
L5 Windows 판 다운로더가 **실제로** pin 을 지킨다 — 굽힌 코드를 꺼내 돌린다.
L6 두 축이 **같은 신뢰 앵커 파일**을 쓴다.

L1~L3·L5 는 소스에 문자열이 있는지 보지 않는다. 실제 TLS 서버를 세우고 런처를 돌려
**파일이 바뀌었는지**를 본다 — 이 결함은 «코드는 있는데 동작하지 않는» 형태였으므로,
문자열 검사는 정확히 이것을 놓쳤을 검사다.
"""
from __future__ import annotations

import http.server
import os
import re
import shutil
import ssl
import subprocess
import threading
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
_SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"

#: 러너 페이로드는 **크기 바닥(20000B)을 넘어야** 한다 — `agent/selfupdate.py` 와 같은 값.
#: 그 바닥이 오류 페이지·잘린 응답을 걸러내므로, 테스트 페이로드도 진짜처럼 커야 한다.
_NEW_AGENT = "# updated runner\nMARKER = 'NEW-RUNNER-PAYLOAD'\n" + ("# pad\n" * 7000)
_OLD_AGENT = "# old runner\nMARKER = 'OLD'\n"


# ── TLS 하네스 ────────────────────────────────────────────────────────────────

def _make_ca(tmp: Path, name: str) -> tuple[Path, Path, Path]:
    """자체서명 CA 하나와 그것이 서명한 `127.0.0.1` 서버 인증서를 만든다.

    두 벌을 만들 수 있어야 L2(엉뚱한 CA)가 성립한다 — «틀린 CA» 는 형식이 깨진 파일이
    아니라 **멀쩡하지만 다른** CA 여야 한다. 형식 오류로 실패하면 pin 이 아니라 파서를
    시험하는 것이 된다.
    """
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    ca_key, ca_crt = d / "ca.key", d / "ca.crt"
    srv_key, srv_crt = d / "srv.key", d / "srv.crt"
    csr, ext = d / "srv.csr", d / "srv.ext"

    def run(*a: str) -> None:
        r = subprocess.run(a, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"openssl 실패: {' '.join(a)}\n{r.stderr}"

    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(ca_key), "-out", str(ca_crt), "-days", "1",
        "-subj", f"/CN=test-ca-{name}")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(srv_key), "-out", str(csr), "-subj", "/CN=127.0.0.1")
    ext.write_text("subjectAltName=IP:127.0.0.1,DNS:localhost\n")
    run("openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca_crt),
        "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(srv_crt),
        "-days", "1", "-extfile", str(ext))
    return ca_crt, srv_crt, srv_key


class _Serve(http.server.BaseHTTPRequestHandler):
    body = _NEW_AGENT.encode()

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):  # 테스트 출력을 더럽히지 않는다
        pass


class _Redirect(http.server.BaseHTTPRequestHandler):
    target = ""

    def do_GET(self):  # noqa: N802
        self.send_response(302)
        self.send_header("Location", self.target)
        self.end_headers()

    def log_message(self, *a):
        pass


def _https_server(srv_crt: Path, srv_key: Path, payload: bytes, redirect_to: str = ""):
    """`bridge_agent.py` 를 내주는 일회용 https 서버. `(base_url, stop)` 을 돌려준다.

    `redirect_to` 를 주면 본문 대신 `302 Location:` 을 낸다 — pin 한 오리진이 **다른 곳을
    지목**하는 상황을 재현한다(오리진 침해·open redirect).
    """
    handler = (type("R", (_Redirect,), {"target": redirect_to}) if redirect_to
               else type("H", (_Serve,), {"body": payload}))
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(srv_crt), keyfile=str(srv_key))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"https://127.0.0.1:{httpd.server_port}", httpd.shutdown


def _plain_server(payload: bytes):
    """**평문** http 서버. 리다이렉트 목적지이자 「평문 base」 재현에 쓴다."""
    handler = type("P", (_Serve,), {"body": payload})
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_port}", httpd.shutdown


def _render_launch_sh(tmp: Path, base: str) -> Path:
    """설치 스크립트의 heredoc 을 **실제 sh 로 전개해** `launch.sh` 를 만든다.

    파이썬 문자열 치환으로 흉내내면 이스케이프가 실물과 갈린다(`test_wsl_scheme_handler`
    가 같은 이유로 같은 방식을 쓴다). 생성 자체를 셸에 맡긴다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    blk = src.split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    out, gen = tmp / "launch.sh", tmp / "gen.sh"
    gen.write_text(
        f"set -eu\nPY=python3\nBRIDGE_BASE='{base}'\nRUNNER_ARGS=''\n"
        f'LAUNCH_SH="{out}"\n'
        'cat > "$LAUNCH_SH" <<LAUNCHEOF\n' + blk + "\nLAUNCHEOF\n"
    )
    r = subprocess.run(["sh", str(gen)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"launch.sh 생성 실패: {r.stderr}"
    out.chmod(0o755)
    return out


def _bridge_home(tmp: Path, ca_crt: Path) -> Path:
    bh = tmp / "home" / ".mysql-ai-bridge"
    bh.mkdir(parents=True, exist_ok=True)
    (bh / "bridge_agent.py").write_text(_OLD_AGENT)
    (bh / "rootCA.crt").write_text(ca_crt.read_text())
    return bh


def _stub_bin(tmp: Path, *, with_curl: bool) -> Path:
    """`--check`/`--resume` 만 가로채고 **나머지는 진짜 파이썬에 넘기는** 스텁.

    갱신 블록은 진짜 파이썬이 돌아야 의미가 있다(TLS 를 실제로 평가하는 것이 이 테스트의
    대상이다). 그래서 러너 흉내와 다운로더 실행을 같은 이름 안에서 갈라 준다.
    """
    b = tmp / "bin"
    b.mkdir(exist_ok=True)
    real = shutil.which("python3") or "/usr/bin/python3"
    (b / "python3").write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  [ "$a" = "--check" ] && exit 0\n'
        '  [ "$a" = "--resume" ] && { echo "[bridge] stub up"; sleep 30; exit 0; }\n'
        "done\n"
        f'exec {real} "$@"\n'
    )
    (b / "pkill").write_text("#!/bin/sh\nexit 0\n")   # 실제 프로세스를 죽이지 않는다
    if not with_curl:
        # curl 을 «없는» 것으로 만든다 — 파이썬 경로가 실제로 도는지 보려면 이것이 필요하다.
        (b / "curl").write_text("#!/bin/sh\nexit 127\n")
    for f in b.iterdir():
        f.chmod(0o755)
    return b


def _run_launch(launch: Path, home: Path, binp: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=str(home), PATH=f"{binp}:{os.environ['PATH']}")
    if not (binp / "curl").exists():
        pass
    return subprocess.run(
        ["sh", str(launch), "mysql-ai-bridge://start/?token=mat_STUBTOKEN"],
        capture_output=True, text=True, timeout=90, env=env)


# ── L1~L3 · POSIX 실동작 ──────────────────────────────────────────────────────

#: ⚠ **두 손을 다 돌린다.** 처음 스위트는 세 검사 모두 curl 을 죽여 놓고 돌려서, curl 이
#: 있는 «거의 모든 실사용 머신» 의 경로가 검증 밖이었다 — 그 손에서 `--cacert` 를 `-k` 로
#: 바꾸면 pin 이 통째로 사라지는데도 전건 통과했다(적대 리뷰 실측).
_HANDS = [pytest.param(True, id="curl"), pytest.param(False, id="python")]


@pytest.mark.parametrize("with_curl", _HANDS)
def test_l1_correct_ca_actually_replaces_the_runner(with_curl: bool, tmp_path: Path):
    """정본 CA 면 러너가 **실제로** 최신본으로 바뀐다 — 두 손 모두에서.

    종전 POSIX 판은 `command -v curl` 이 실패하면 갱신을 통째로 건너뛰었다 — Windows 가
    IWR 로 겪은 «조용한 미갱신» 의 약한 판이다. 이제 두 번째 손이 있다.
    """
    ca, sc, sk = _make_ca(tmp_path, "good")
    base, stop = _https_server(sc, sk, _NEW_AGENT.encode())
    try:
        bh = _bridge_home(tmp_path, ca)
        launch = _render_launch_sh(tmp_path, base)
        b = _stub_bin(tmp_path, with_curl=with_curl)
        r = _run_launch(launch, tmp_path / "home", b)
        assert r.returncode == 0, f"정상 경로인데 실패: {r.stderr!r}"
        got = (bh / "bridge_agent.py").read_text()
        assert "NEW-RUNNER-PAYLOAD" in got, (
            "러너가 그대로다 — 갱신 경로가 끊겨 있다(사용자가 본 바로 그 상태)")
    finally:
        stop()


@pytest.mark.parametrize("with_curl", _HANDS)
def test_l2_wrong_ca_must_not_replace_the_runner(with_curl: bool, tmp_path: Path):
    """**엉뚱한 CA 면 갈아 끼우지 않는다** — 이 파일이 지키는 계약의 핵심.

    서버는 CA-A 로 서명했는데 런처는 CA-B 를 pin 한다. 다음 순간 **실행될** 파일이므로
    여기서 통과시키면 신뢰 앵커가 아무것도 아닌 것이 된다. `Invoke-WebRequest` 판이
    정확히 이 자리에서 OS 저장소를 보고 통과할 수 있었고, curl 손에서는 `-k` 한 글자가
    같은 결과를 만든다.
    """
    good_ca, sc, sk = _make_ca(tmp_path, "good")
    other_ca, _, _ = _make_ca(tmp_path, "other")
    base, stop = _https_server(sc, sk, _NEW_AGENT.encode())
    try:
        bh = _bridge_home(tmp_path, other_ca)          # ← 서버와 무관한 CA 를 pin
        launch = _render_launch_sh(tmp_path, base)
        b = _stub_bin(tmp_path, with_curl=with_curl)
        _run_launch(launch, tmp_path / "home", b)
        got = (bh / "bridge_agent.py").read_text()
        assert "NEW-RUNNER-PAYLOAD" not in got, (
            "pin 하지 않은 CA 로 서명된 파일을 받아 실행 대상으로 갈아 끼웠다")
        assert got == _OLD_AGENT, "실패했는데 있던 파일까지 망가뜨렸다"
    finally:
        stop()


def test_l3_too_small_response_is_not_installed(tmp_path: Path):
    """잘린 응답은 러너가 아니다 — **크기 바닥**에서 걸러낸다.

    ⚠ 페이로드는 **유효 파이썬이면서 작아야** 한다. `<html>login</html>` 로 검사하면
    `ast.parse` 가 먼저 죽여서 크기 바닥을 지워도 통과한다(적대 리뷰가 그 vacuous 를 실증).
    두 방어선은 다른 실패를 막으므로 각자 시험해야 한다 — 그리고 «문법은 맞는데 잘린 응답»
    이 정확히 부분 다운로드의 모양이다.
    """
    ca, sc, sk = _make_ca(tmp_path, "good")
    base, stop = _https_server(sc, sk, b"MARKER='TINY-BUT-VALID-PYTHON'\n")
    try:
        bh = _bridge_home(tmp_path, ca)
        launch = _render_launch_sh(tmp_path, base)
        b = _stub_bin(tmp_path, with_curl=False)
        _run_launch(launch, tmp_path / "home", b)
        assert (bh / "bridge_agent.py").read_text() == _OLD_AGENT, (
            "러너가 아닌 응답을 러너 자리에 넣었다 — 다음 기동에서 죽는다")
    finally:
        stop()


# ── L4~L5 · Windows 축 ───────────────────────────────────────────────────────

def _launch_ps1_block() -> str:
    """굽는 `launch.ps1` 본문. **구간이 안 잡히면 요란하게 죽는다.**

    `split(...)[0]` 은 구분자가 사라지면 조용히 «파일 나머지 전부» 를 돌려준다 — 그러면
    「금지어가 없다」류 검사가 더 넓은 범위를 보게 되어 통과하고, 계약이 풀린 사실이 초록
    뒤에 숨는다(형제 `test_windows_tls_revocation` 은 같은 자리를 assert 로 잠근다).
    """
    src = _SETUP_PS1.read_text(encoding="utf-8")
    m = re.search(r"\$LaunchPs = Join-Path(.*?)Set-Content -Encoding UTF8 \$LaunchPs", src, re.S)
    assert m, "launch.ps1 구간 슬라이스가 깨졌다 — 굽는 형태가 바뀌었으면 이 테스트도 따라가야 한다"
    return m.group(1)


def _code_only(block: str) -> str:
    """주석 줄을 걷어낸 **실행 코드**만.

    필요한 구분이다: 이 결함을 설명하는 주석에는 `Invoke-WebRequest` 가 당연히 나온다.
    주석까지 세면 「금지어가 없다」 검사는 설명을 못 쓰게 만들고, 반대로 「pin 이 있다」
    검사는 주석 한 줄로 vacuous 하게 통과한다. 둘 다 코드를 봐야 한다.
    """
    return "\n".join(ln for ln in block.splitlines() if not ln.strip().startswith("#"))


def test_l4_windows_launcher_does_not_use_invoke_webrequest(tmp_path: Path):
    """Windows 런처의 갱신은 IWR 로 하지 않고 **pin 한 CA 를 넘긴다**.

    `bridge_setup.ps1` 본체가 이미 «IWR 을 폴백으로 두지 않는다» 고 적고 그대로 지킨다.
    그것이 굽는 런처만 반대로 하고 있었다 — 같은 파일 안에서 갈렸다.
    """
    code = _code_only(_launch_ps1_block())
    # ⚠ **철자 하나를 금지하는 것으로는 부족하다.** `iwr` 은 `Invoke-WebRequest` 의 기본
    #   별칭이고 `wget`·`curl` 도 PowerShell 에서 같은 cmdlet 을 가리킨다 — 원래 결함이
    #   이름만 바꿔 그대로 돌아올 수 있다(적대 리뷰 실측: `iwr` 로 바꾸자 전건 통과했다).
    banned = re.search(
        r"\b(Invoke-WebRequest|iwr|wget|curl(\.exe)?|Invoke-RestMethod|irm|Start-BitsTransfer)\b",
        code, re.I)
    assert not banned, (
        f"런처가 OS 신뢰 저장소를 쓰는 수단({banned.group(0) if banned else ''})으로 러너를 받는다 — "
        "rootCA.crt 를 보지 않으므로 사내 CA 머신에서 조용히 실패하거나, pin 과 무관하게 통과한다")
    assert "rootCA.crt" in code, "받는 쪽에 신뢰 앵커가 전달되지 않는다"
    assert "cafile=ca" in code, "pin 을 실제로 적용하는 인자가 없다"


def test_l5b_windows_call_site_is_wired_correctly(tmp_path: Path):
    """다운로더가 옳은 것과 **런처가 그것을 옳게 부르는 것**은 다른 축이다.

    L5 는 다운로더를 격리 실행하므로 호출부를 보지 못한다 — 그 사각지대에서 «인자 순서
    뒤바꿈»·«CA 를 다른 경로로»·«받아 놓고 설치 안 함» 이 모두 살아남았다(적대 리뷰 실측).
    pwsh 가 없어 실행은 못 하지만, **호출의 모양**은 여기서 잠근다.
    """
    code = _code_only(_launch_ps1_block())
    m = re.search(r"&\s*'\$Py'\s+`?\$dl\s+(.+?)2>&1", code, re.S)
    assert m, "다운로더를 파이썬으로 부르는 자리가 없다"
    argv = m.group(1)
    # 순서는 다운로더가 읽는 순서(url, dest, ca)와 같아야 한다 — 프로세스 경계의 «모양» 이다.
    order = [
        argv.index("/static/agent/bridge_agent.py"),
        argv.index("`$new"),
        argv.index("rootCA.crt"),
    ]
    assert order == sorted(order), f"인자 순서가 다운로더가 읽는 순서와 다르다: {argv!r}"
    # CA 는 러너가 --check/--resume 에 쓰는 것과 **같은 자리**에서 와야 한다.
    assert re.search(r"Join-Path\s+`\$home_\s+'rootCA\.crt'", argv), (
        "갱신이 러너와 다른 곳의 인증서를 쓴다 — 한쪽만 조용히 죽는다")
    # 받기만 하고 설치하지 않으면 「러너 파일이 그대로」가 그대로 남는다.
    assert re.search(r"Move-Item\s+-Force\s+`\$new\s+\(Join-Path\s+`\$home_\s+'bridge_agent\.py'\)", code), (
        "받은 파일을 러너 자리에 설치하지 않는다")


def test_l5c_both_axes_ship_the_same_downloader(tmp_path: Path):
    """두 축의 다운로더 본문이 **같다**.

    부분문자열 두어 개로 「축 대칭」을 주장하면, 한쪽에만 방어를 넣은 상태에서도 초록이
    유지된다 — 이 cycle 이 실제로 그 상태를 한 번 지났다(PS 에만 리다이렉트 방어가 있고
    sh 에는 없던 구간). 같은 계약을 주장하려면 **같은 코드**여야 한다.
    """
    a = _downloader(_SETUP_SH, tmp_path).read_text().strip()
    b = _downloader(_SETUP_PS1, tmp_path).read_text().strip()
    assert a == b, "두 축의 다운로더가 갈렸다 — 한쪽에만 들어간 방어는 다른 OS 를 지키지 않는다"


def test_l5_windows_downloader_enforces_the_pin(tmp_path: Path):
    """굽힌 파이썬 다운로더를 **꺼내서 돌린다** — 정본 CA 는 받고, 틀린 CA 는 거부한다.

    pwsh 가 없는 환경이라 런처 전체는 못 돌린다. 그러나 이 결함이 살던 자리는 «어떤
    신뢰 앵커로 받는가» 한 곳이고, 그 코드는 여기서 그대로 실행할 수 있다. 문자열이
    있는지 보는 대신 **같은 코드가 같은 판정을 하는지** 본다.
    """
    blk = _launch_ps1_block()
    lines: list[str] = []
    for raw in blk.split("Set-Content -Encoding ASCII -Path `$dl -Value @(", 1)[1].splitlines():
        s = raw.strip()
        if s.startswith(")"):
            break
        if s.startswith("'"):
            lines.append(s.strip(",").strip().strip("'"))
    assert lines, "다운로더 본문을 찾지 못했다 — 굽는 형태가 바뀌었으면 이 테스트도 따라가야 한다"
    dl = tmp_path / "dl.py"
    dl.write_text("\n".join(lines) + "\n")

    good_ca, sc, sk = _make_ca(tmp_path, "good")
    other_ca, _, _ = _make_ca(tmp_path, "other")
    base, stop = _https_server(sc, sk, _NEW_AGENT.encode())
    url = base + "/static/agent/bridge_agent.py"
    try:
        ok = tmp_path / "ok.py"
        r = subprocess.run(["python3", str(dl), url, str(ok), str(good_ca)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and ok.exists(), f"정본 CA 인데 못 받았다: {r.stderr!r}"
        assert "NEW-RUNNER-PAYLOAD" in ok.read_text()

        bad = tmp_path / "bad.py"
        r = subprocess.run(["python3", str(dl), url, str(bad), str(other_ca)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode != 0, "pin 하지 않은 CA 로 서명된 응답을 받아들였다"
        assert not bad.exists(), "검증 실패인데 파일을 남겼다"
    finally:
        stop()


# ── L7~L10 · 적대 리뷰가 실증한 우회 (2026-09-02 보안 패널) ──────────────────
#
# 아래 넷은 「pin 을 지킨다」는 이 cycle 의 주장이 **실증적으로 거짓이던** 자리다. 처음 스위트는
# L1·L2 로 pin 을 구동해 놓고도 이것들을 보지 못했다 — 하네스가 리다이렉트를 내지 않았고,
# `https://` 로만 돌렸고, curl 을 죽여 놓고 크기 바닥을 검사했기 때문이다.

def _downloader(path: Path, tmp: Path) -> Path:
    """굽힌 런처에서 파이썬 다운로더를 꺼낸다. 두 축 모두 **같은 본문**이어야 한다."""
    if path is _SETUP_SH:
        launch = _render_launch_sh(tmp, "https://placeholder.invalid")
        m = re.search(r"<<'DLEOF'[^\n]*\n(.*?)\nDLEOF", launch.read_text(), re.S)
        assert m, "sh 축 다운로더를 찾지 못했다"
        body = m.group(1)
    else:
        blk = _launch_ps1_block()
        lines: list[str] = []
        for raw in blk.split("Set-Content -Encoding ASCII -Path `$dl -Value @(", 1)[1].splitlines():
            s = raw.strip()
            if s.startswith(")"):
                break
            if s.startswith("'"):
                lines.append(s.strip(",").strip().strip("'"))
        assert lines, "ps1 축 다운로더를 찾지 못했다"
        body = "\n".join(lines)
    out = tmp / f"dl_{path.stem}_{path.suffix.lstrip('.')}.py"
    out.write_text(body + "\n")
    # ⚠ 기준선을 먼저 세운다 — 추출이 어긋나 SyntaxError 가 나면 모든 «거부» 가 거짓 양성이 된다
    #   (실측: `|| true` 를 추가하자 split 기준이 밀려 첫 줄이 깨졌고, 그때도 rc≠0 이었다).
    import ast as _ast
    _ast.parse(out.read_text())
    return out


@pytest.mark.parametrize("axis", [_SETUP_SH, _SETUP_PS1])
def test_l7_redirect_to_plaintext_is_refused(axis: Path, tmp_path: Path):
    """pin 한 오리진이 `302 Location: http://…` 를 주면 **따라가지 않는다**.

    `urlopen` 은 리다이렉트를 무조건 따르고 https→http 다운그레이드도 허용한다. `context` 는
    https 레그에만 걸리므로 평문 레그에서 CA 는 아무 역할도 하지 않는다 — 즉 **오리진 응답을
    바꿀 수 있는 누구든 러너가 실행할 파일을 지목**할 수 있었다(`selfupdate.py` 규율 2 가
    막겠다고 선언한 바로 그 형태). 적대 리뷰가 실제로 재현했다.
    """
    ca, sc, sk = _make_ca(tmp_path, "good")
    plain, stop_p = _plain_server(_NEW_AGENT.encode())
    base, stop = _https_server(sc, sk, b"", redirect_to=plain + "/evil.py")
    try:
        dl = _downloader(axis, tmp_path)
        dest = tmp_path / f"got_{axis.suffix}.py"
        r = subprocess.run(["python3", str(dl), base + "/static/agent/bridge_agent.py",
                            str(dest), str(ca)], capture_output=True, text=True, timeout=60)
        assert r.returncode != 0, "리다이렉트를 따라가 평문에서 받았다"
        assert not dest.exists(), "검증 없이 받은 파일을 실행 대상 자리에 남겼다"
    finally:
        stop(); stop_p()


@pytest.mark.parametrize("axis", [_SETUP_SH, _SETUP_PS1])
def test_l8_plaintext_base_is_refused(axis: Path, tmp_path: Path):
    """`BRIDGE_BASE` 가 `http://` 면 받지 않는다 — CA 를 넘겨도 평문에서는 무의미하다.

    `ssl` 컨텍스트를 만들어 넘겨도 URL 이 평문이면 **조용히 무시**된다. `selfupdate.py:92` 가
    같은 이유로 같은 가드를 갖고 있다(「이 파일은 다음 순간 실행될 것이다」).
    """
    ca, _, _ = _make_ca(tmp_path, "good")
    plain, stop_p = _plain_server(_NEW_AGENT.encode())
    try:
        dl = _downloader(axis, tmp_path)
        dest = tmp_path / f"plain_{axis.suffix}.py"
        r = subprocess.run(["python3", str(dl), plain + "/static/agent/bridge_agent.py",
                            str(dest), str(ca)], capture_output=True, text=True, timeout=60)
        assert r.returncode != 0, "평문으로 러너를 받았다"
        assert not dest.exists()
    finally:
        stop_p()


def test_l9_size_floor_applies_to_the_curl_branch_too(tmp_path: Path):
    """크기 바닥은 **두 손 모두**에 있어야 한다 — curl 이 있는 쪽이 기본 경로다.

    파이썬 분기에만 두고 「검사한다」고 적으면 계약이 코드보다 넓어진다. 적대 리뷰가
    31바이트짜리 문법상 올바른 응답으로 실제 런처를 통과시켰다.
    """
    ca, sc, sk = _make_ca(tmp_path, "good")
    tiny = b"MARKER='TINY-BUT-VALID-PYTHON'\n"
    base, stop = _https_server(sc, sk, tiny)
    try:
        bh = _bridge_home(tmp_path, ca)
        launch = _render_launch_sh(tmp_path, base)
        b = _stub_bin(tmp_path, with_curl=True)      # ← curl 을 **살려 둔다**
        _run_launch(launch, tmp_path / "home", b)
        assert (bh / "bridge_agent.py").read_text() == _OLD_AGENT, (
            "curl 경로가 잘린 응답을 러너 자리에 넣었다 — 다음 기동에서 죽는다")
    finally:
        stop()


def test_l10_update_failure_never_kills_the_launcher(tmp_path: Path):
    """갱신 임시 파일을 못 써도 **러너는 뜬다**.

    `cat > "$_dl"` 은 `else` 본문이라 `set -e` 가 그대로 걸린다. 디스크 가득참·쿼터·읽기전용
    홈에서 리다이렉션이 실패하면 런처가 거기서 죽고, 사용자에게는 「눌렀는데 아무 일도
    안 일어남」이 된다 — 이 블록이 막겠다고 적은 바로 그 결말이다(적대 리뷰 실측).

    ⚠ **검사가 두 겹인 이유**: 이 스위트는 root 로도 돌고, root 는 권한 검사를 **우회**한다 —
    `chmod 500` 으로 쓰기 실패를 만들려던 처음 판은 그래서 vacuous 였고, `|| true` 를 지워도
    통과했다(실측). 그래서 계약을 먼저 정적으로 잠그고, 실제 실패 주입은 그것이 의미를 갖는
    환경에서만 돌린다.
    """
    blk = _SETUP_SH.read_text(encoding="utf-8") \
        .split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    m = re.search(r"cat > \"\\?\$_dl\" <<'DLEOF'([^\n]*)", blk)
    assert m, "다운로더를 굽는 자리를 찾지 못했다"
    assert "|| true" in m.group(1), (
        "heredoc 리다이렉션이 set -e 아래 그대로 노출됐다 — 임시 파일을 못 쓰는 순간 "
        "런처가 러너를 띄우지도 못하고 죽는다")
    # 받은 것이 없을 때 그것을 쓰지 않는지도 함께 본다(`|| true` 는 실패를 통과시키므로).
    assert re.search(r"\[ -s \"\\?\$_dl\" \]", blk), "쓰지 못한 다운로더를 그대로 실행한다"

    if os.geteuid() == 0:
        pytest.skip("root 는 권한 검사를 우회한다 — 실패 주입이 성립하지 않는다(위 정적 계약으로 대체)")

    ca, sc, sk = _make_ca(tmp_path, "good")
    base, stop = _https_server(sc, sk, _NEW_AGENT.encode())
    try:
        bh = _bridge_home(tmp_path, ca)
        launch = _render_launch_sh(tmp_path, base)
        b = _stub_bin(tmp_path, with_curl=False)
        os.chmod(bh, 0o500)                           # 읽기·실행만 — 새 파일을 못 만든다
        try:
            r = _run_launch(launch, tmp_path / "home", b)
        finally:
            os.chmod(bh, 0o700)
        assert "stub up" in (r.stdout + r.stderr) or r.returncode == 0, (
            f"갱신이 실패했다고 런처가 러너를 못 띄웠다: rc={r.returncode} {r.stderr[-300:]!r}")
    finally:
        stop()


# ── L6 · 축 대칭 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [_SETUP_SH, _SETUP_PS1])
def test_l6_both_axes_pin_the_same_anchor(path: Path):
    """두 축이 **같은 파일**을 신뢰 앵커로 쓴다.

    한쪽만 앵커를 바꾸면 «한 OS 에서만 갱신되는» 상태가 되는데, 그것은 사용자 화면에서
    구별되지 않는다 — 이번 결함이 정확히 그 모양이었다.
    """
    src = path.read_text(encoding="utf-8")
    if path is _SETUP_SH:
        blk = src.split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    else:
        blk = _launch_ps1_block()
    upd = blk.split("러너 최신화", 1)
    assert len(upd) == 2, "러너 최신화 블록이 없다"
    # 주석이 아니라 **코드**에 있어야 한다 — 설명만으로는 아무것도 pin 되지 않는다.
    body = _code_only(upd[1])
    assert "rootCA.crt" in body, "갱신이 신뢰 앵커 없이 이뤄진다"
    assert "20000" in body, "크기 바닥이 없다 — 오류 페이지를 러너 자리에 넣을 수 있다"

    # ⚠ **배선까지 본다.** 다운로더가 pin 을 지키는 것과 런처가 그 다운로더에 «맞는» 앵커를
    #   넘기는 것은 다른 축이고, 뒤엣것은 다운로더를 직접 부르는 검사로는 영원히 보이지
    #   않는다(실측: 런처가 엉뚱한 파일명을 넘기도록 바꿔도 나머지 검사가 전부 통과했다).
    #   런처 안에서 쓰이는 인증서 파일은 **하나여야** 한다 — 둘이면 그중 하나는 틀린 것이고,
    #   그 갈라짐이 이번 결함의 형태다.
    anchors = set(re.findall(r"([A-Za-z0-9_.-]+\.crt)\b", _code_only(blk)))
    assert anchors == {"rootCA.crt"}, (
        f"런처가 신뢰 앵커를 하나로 쓰지 않는다: {sorted(anchors)} — "
        "러너가 --ca 로 검증하는 파일과 갱신을 받는 파일이 갈리면 한쪽만 조용히 죽는다")

    if path is _SETUP_SH:
        # curl 손의 pin — **정적으로도** 잠근다. 동작 축(L1/L2 의 curl 파라미터)은 런처를
        # 통째로 돌리느라 느려서, 뮤턴트 판정이 타임아웃에 걸려 «판정 불가» 로 끝났다.
        # 계약 자체는 한 줄이므로 여기서 즉시 가른다. `-k` 한 글자가 pin 전체를 무効化한다.
        curl_line = re.search(r"curl -fsS --max-time 30 ([^\n]*)", _code_only(blk))
        assert curl_line, "curl 손이 사라졌다"
        assert "--cacert" in curl_line.group(1), (
            "curl 손이 신뢰 앵커 없이 받는다 — OS 저장소로 검증하게 되어 pin 이 풀린다")
        assert not re.search(r"\s(-k|--insecure)\b", curl_line.group(1)), (
            "curl 손이 검증을 끈다(-k/--insecure) — 이 파일이 지킨다고 말하는 그 pin 이다")
