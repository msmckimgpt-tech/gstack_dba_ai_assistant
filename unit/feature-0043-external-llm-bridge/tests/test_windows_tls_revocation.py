"""feature-0043 — 윈도우 설치기의 TLS 신뢰·수신 경로를 잠근다 (사용자 제보 2026-08-31).

## 무엇이 터졌나

윈도우 사용자가 `bridge_setup.ps1` 로 연결하면 CA 지문 대조까지 통과한 뒤 러너 수신에서 죽었다:

    [bridge-setup] CA 지문 일치.
    [bridge-setup] 러너를 받는 중…
    curl: (60) schannel: CertGetCertificateChain trust error CERT_TRUST_REVOCATION_STATUS_UNKNOWN
    [bridge-setup] 중단: 러너를 받지 못했습니다. CA 신뢰 또는 네트워크를 확인하세요.

원인은 CA 도 네트워크도 아니다(안내문이 가리킨 두 곳 모두 멀쩡했다). 윈도우 동봉 curl 은 TLS
백엔드가 **Schannel** 이고(실측: `curl 8.13.0 (Windows) libcurl/8.13.0 Schannel`), Schannel 은
체인을 세운 **뒤** 폐기 상태를 조회한다. 그런데 사내 CA 에는 조회할 곳이 없다 — CRL 배포점도
OCSP(AIA)도 없다(실측: root·leaf 양쪽 모두 그 확장 부재). 결과가 «알 수 없음» 이고 curl 은
그것을 하드 실패로 본다. POSIX 판은 OpenSSL curl 이라 폐기검사를 기본으로 하지 않아 이 결함이
없다 — **Windows 전용 divergence** 다.

## 이 스위트가 잠그는 네 축

같은 구간을 고치는 동안 세 개의 결함이 더 드러났고, 넷 다 «조용히 통과하는» 형태였다. 그래서
증상 하나가 아니라 축 넷을 잠근다:

1. **폐기검사 완화의 선택과 순서** — `--ssl-revoke-best-effort` 가 `--ssl-no-revoke` 보다 먼저.
   전자는 «조회할 곳이 없을 때만» 넘어가고 CRL 에 닿아 revoked 면 여전히 멈춘다. 후자는 폐기검사를
   통째로 끈다. 순서가 뒤집히면 잃지 않아도 될 것을 잃는다.
2. **pin 우회 금지** — 러너 수신에 `Invoke-WebRequest` 를 쓰지 않는다. IWR 은 `$CaPath` 를 보지
   않고 **OS 신뢰 저장소**로 검증한다. 실측: 사내 CA 가 이미 `CurrentUser\\Root` 에 있는 머신에서
   **무관한 CA 를 pin 해도 IWR 이 수신을 성공**시켰다 — 신뢰 실패가 조용한 성공이 된다.
3. **fail-open 금지** — 실행 자체가 실패하면(`$exe` 부재) `$LASTEXITCODE` 는 건드려지지 않는다.
   0 으로 초기화해 두면 그것이 «성공» 으로 읽힌다. 실측: 없는 파이썬 경로로 불렀는데 수신 함수가
   `via=python` 을 성공 반환했다(받은 파일은 없었다).
4. **사유 유실 금지** — 네이티브 stderr 를 `SilentlyContinue` 아래에서 파이프로 받으면 ErrorRecord
   가 조용히 버려진다. 실측: curl 이 exit 60 인데 회수된 메시지 길이가 **0** 이었다 — 사유를
   모으려고 만든 구조가 무의미해진다.

## §16.7 G11-a 를 지키는 방법

이 파일이 검사하는 대상의 **주석에는 `--ssl-revoke-best-effort` 가 여러 번 이름으로 등장한다.**
그래서 «있다» 를 전체 텍스트에 대해 검사하면 **대상의 주석이 이 단언을 통과시킨다** — 이 저장소가
이미 세 번 걸린 함정이다(T3-20260814T0735-002). 아래 `_ps_code` 로 주석·here-string 을 걷어낸
코드 영역에만 존재 단언을 건다. **부재 단언**(POSIX 판에 그 옵션이 없다)에는 반대로 리터럴을
제외하지 않는다 — 찾으려는 것이 바로 리터럴 안에 있기 때문이다(G11-a 의 명시 예외).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
_SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
_SERVED_PS1 = (_UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent"
               / "bridge_setup.ps1")
_SERVED_SH = (_UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent"
              / "bridge_setup.sh")

#: Schannel 폐기검사를 완화하는 두 옵션 — **순서가 계약이다**(좁은 것 먼저).
_REVOKE_PREFERRED = "--ssl-revoke-best-effort"
_REVOKE_FALLBACK = "--ssl-no-revoke"


def _ps_code(text: str) -> str:
    """PowerShell 소스에서 **주석과 here-string 본문**을 지운 «코드 영역» 만 남긴다.

    지운다 — `#` 줄 주석, `<# #>` 블록 주석, here-string(`@" "@` / `@' '@`) 본문.
    here-string 은 이 파일에서 사용자 대면 안내문이라 주석과 같은 자기-통과 위험을 갖는다.

    남긴다 — 보통의 따옴표 문자열. PowerShell 에서 curl 플래그는 문자열 리터럴 **그 자체**이므로
    (`@('--ssl-revoke-best-effort', '--ssl-no-revoke')`) 그것까지 지우면 검사 대상이 사라진다.

    ⚠ 줄 단위 `grep -v '^\\s*#'` 휴리스틱이 아니다(G11-a 가 금지하는 형태다 — 블록 주석·
      here-string 에서 실제 코드 줄을 잘못 지운다). 문자 스캐너로 인용 상태를 추적한다.

    **언어 인지 도구와의 대조 (실측 2026-08-31, 실 Windows PowerShell 5.1)**: 이 스트리퍼가
    «주석/here-string/보통 문자열» 을 가르는 경계가 `[PSParser]::Tokenize`(토큰 2,602개,
    tokenizeErrors=0) 의 판정과 일치하는지 프로브별로 대조했다 —
      · `--ssl-revoke-best-effort` → 보통 String 토큰 (여기서 keep 이 맞다)
      · `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` → here-string 토큰 (여기서 drop 이 맞다)
      · `cafile=ca` → 보통 String 토큰
    즉 이 스트리퍼는 «Comment 제외» 가 아니라 **«Comment + here-string 제외»** 이며, 그것이
    의도다(here-string 은 이 파일에서 산문이다). 토크나이저와 «동일» 하지 않고, 위 축에서
    **의도적으로 더 엄격하다**.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "<" and nxt == "#":                      # <# 블록 주석 #>
            j = text.find("#>", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
            continue
        if c == "@" and nxt in ('"', "'"):               # here-string — 종료자는 줄머리에만
            term = nxt + "@"
            j = text.find("\n" + term, i + 2)
            i = n if j == -1 else j + 1 + len(term)
            out.append(" ")
            continue
        if c == "#":                                     # 줄 주석
            j = text.find("\n", i)
            i = n if j == -1 else j
            out.append(" ")
            continue
        if c in ('"', "'"):                              # 보통 문자열 — 통째로 보존
            q = c
            out.append(c)
            i += 1
            while i < n:
                if text[i] == "`" and q == '"':          # 이중따옴표 안 backtick 이스케이프
                    out.append(text[i:i + 2])
                    i += 2
                    continue
                if text[i] == q:
                    if i + 1 < n and text[i + 1] == q:   # 따옴표 이중화 이스케이프
                        out.append(text[i:i + 2])
                        i += 2
                        continue
                    out.append(q)
                    i += 1
                    break
                out.append(text[i])
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _runner_section(text: str) -> str:
    """`# ── 2. 러너` ~ `# ── 3. 프로토콜 핸들러` 구간. CA 수신(1절)과 섞이지 않게 자른다.

    1절은 **평문 HTTP** 로 CA 를 받으므로 `Invoke-WebRequest` 가 정당하다(지문 대조가 덮는다).
    2절의 pin 우회 금지를 파일 전체에 걸면 그 정당한 사용까지 잡아 거짓 FAIL 이 된다.
    """
    m = re.search(r"#\s*──\s*2\.\s*러너", text)
    assert m, "러너 절 헤더를 찾지 못했다 — 구간 슬라이스가 깨졌다(테스트를 갱신하라)"
    end = re.search(r"#\s*──\s*3\.", text[m.end():])
    assert end, "프로토콜 핸들러 절 헤더를 찾지 못했다 — 구간 슬라이스가 깨졌다"
    return text[m.end():m.end() + end.start()]


@pytest.fixture(scope="module")
def ps1_code() -> str:
    return _ps_code(_SETUP_PS1.read_text(encoding="utf-8-sig"))


# ── 축 0. 스트리퍼 자체가 무엇도 검사하지 않는 상태가 아님을 먼저 본다 ──────────────
#
# G11 의 요점은 «게이트로 쓰는 검사가 무엇도 검사하지 않는 상태» 다. 아래 단언들이 전부
# `_ps_code` 에 의존하므로, 그것이 주석을 실제로 걷어내는지부터 확인한다.

def test_ps_code_strips_comments_and_here_strings():
    sample = (
        "$a = 'keep-me'\n"
        "# drop-me-line-comment --ssl-no-revoke\n"
        "<# drop-me-block\n--ssl-no-revoke\n#>\n"
        "$b = @\"\ndrop-me-herestring --ssl-no-revoke\n\"@\n"
        "$c = @'\ndrop-me-single-herestring\n'@\n"
        '$d = "keep # not-a-comment"\n'
    )
    code = _ps_code(sample)
    assert "keep-me" in code
    assert "keep # not-a-comment" in code, "문자열 안의 # 를 주석으로 오인해 내용을 잘랐다"
    for gone in ("drop-me-line-comment", "drop-me-block", "drop-me-herestring",
                 "drop-me-single-herestring"):
        assert gone not in code, f"{gone} 가 남았다 — 주석/here-string 제거가 동작하지 않는다"


def test_ps_code_actually_removes_this_files_own_comments(ps1_code):
    """대상 파일의 주석이 실제로 걷혔는지 — 주석에만 있는 토큰으로 확인한다.

    이 단언이 없으면 `_ps_code` 가 항등함수여도 아래 존재 단언들이 전부 통과한다.
    """
    raw = _SETUP_PS1.read_text(encoding="utf-8-sig")
    only_in_comments = "CERT_TRUST_REVOCATION_STATUS_UNKNOWN"
    assert only_in_comments in raw, (
        "대상 파일이 이 오류 토큰을 더 이상 언급하지 않는다 — 이 테스트의 전제가 깨졌다"
    )
    assert only_in_comments not in ps1_code, (
        "주석/안내문에만 있어야 하는 토큰이 코드 영역에 남았다 — _ps_code 가 제거에 실패했다"
    )


# ── 축 1. 폐기검사 완화 — 선택과 순서 ────────────────────────────────────────

def test_windows_installer_relaxes_schannel_revocation(ps1_code):
    """윈도우 판은 폐기검사 완화 옵션을 **코드에서** 실제로 쓴다."""
    assert _REVOKE_PREFERRED in ps1_code, (
        f"{_REVOKE_PREFERRED} 가 코드 영역에 없다 — Schannel 이 "
        "CERT_TRUST_REVOCATION_STATUS_UNKNOWN 으로 러너 수신을 하드 실패시킨다"
    )


def test_narrow_revoke_option_is_tried_before_the_blunt_one(ps1_code):
    """좁은 완화가 **먼저**. 순서가 곧 보안 선택이다.

    `--ssl-revoke-best-effort` 는 폐기 정보를 «못 구할 때만» 넘어가고, CRL 에 닿아 revoked 라고
    하면 여전히 멈춘다. `--ssl-no-revoke` 는 폐기검사를 통째로 끈다. 뒤집히면 잃지 않아도 될
    것을 잃는다 — 구형 curl(7.70 미만) 대비 폴백으로만 존재해야 한다.

    ⚠ 순서 판정을 **파일 전체**에 걸면 안 된다. 같은 두 이름이 사용자 안내문(`Drop '…'`)에도
      보통 문자열로 등장하므로(토크나이저 실측: 393행 배열 · 400행 안내문), 파일 전체 인덱스
      비교는 안내문의 어순으로도 만족될 수 있다. 실제로 순서를 정하는 **감지 함수의 후보
      목록**만 본다.
    """
    assert _REVOKE_FALLBACK in ps1_code, (
        f"{_REVOKE_FALLBACK} 폴백이 없다 — 7.70 미만 curl 에서 폐기검사를 풀 수단이 사라진다"
    )
    m = re.search(r"function\s+Get-CurlRevokeArgs.*?\n}", ps1_code, re.S)
    assert m, "Get-CurlRevokeArgs 본문을 찾지 못했다"
    body = m.group(0)
    for flag in (_REVOKE_PREFERRED, _REVOKE_FALLBACK):
        assert flag in body, f"{flag} 가 감지 함수의 후보 목록에 없다"
    i_pref = body.index(_REVOKE_PREFERRED)
    i_back = body.index(_REVOKE_FALLBACK)
    assert i_pref < i_back, (
        "감지 함수가 --ssl-no-revoke 를 --ssl-revoke-best-effort 보다 먼저 시도한다 — "
        "폐기검사를 통째로 끄는 쪽이 먼저 잡히면, 좁게 풀어도 됐을 상황에서 넓게 푼다"
    )


def test_revoke_option_is_feature_detected_not_assumed(ps1_code):
    """모르는 옵션을 그냥 붙이면 curl 이 파싱 단계에서 exit 2 로 죽는다 — 감지 후 붙인다.

    감지는 **네트워크를 타지 않아야** 한다(`--version` 로 판정). 도달성 문제와 옵션 지원 문제가
    섞이면, 사내망 밖에서 실행했을 때 "옵션 미지원" 으로 오진한다.
    """
    assert "Get-CurlRevokeArgs" in ps1_code, "폐기검사 옵션 감지 함수가 없다"
    m = re.search(r"function\s+Get-CurlRevokeArgs.*?\n}", ps1_code, re.S)
    assert m, "Get-CurlRevokeArgs 본문을 찾지 못했다"
    body = m.group(0)
    assert "--version" in body, (
        "감지가 --version 이 아닌 수단을 쓴다 — 네트워크 실패와 옵션 미지원이 섞인다"
    )


def test_revoke_relaxation_still_passes_the_pinned_ca(ps1_code):
    """완화하는 것은 폐기검사뿐이다 — `--cacert` pin 은 같은 호출에 그대로 실려야 한다.

    실측 대조군(2026-08-31): 무관한 CA 를 pin 하면 `--ssl-revoke-best-effort` 가 있어도
    `CERT_TRUST_IS_UNTRUSTED_ROOT` 로 실패했다. 즉 완화는 root 신뢰 축을 건드리지 않는다.
    이 단언은 그 성질이 **배선으로** 유지되는지 본다.
    """
    m = re.search(r"Invoke-NativeCapture\s+\$curl\.Source\s+\((.*?)\)\s*$",
                  ps1_code, re.M | re.S)
    assert m, "curl 인자 조립부를 찾지 못했다"
    args = m.group(1)
    assert "--cacert" in args, "curl 호출에서 --cacert pin 이 빠졌다 — 신뢰 앵커가 사라진다"
    assert "CurlRevokeArgs" in args, "감지한 폐기검사 옵션이 실제 호출에 실리지 않는다"


# ── 축 2. pin 우회 금지 ──────────────────────────────────────────────────────

def test_runner_download_never_uses_invoke_webrequest():
    """러너 수신에 `Invoke-WebRequest` 를 쓰지 않는다 — IWR 은 OS 저장소로 검증해 pin 을 우회한다.

    실측(2026-08-31, 실 Windows): 사내 CA 가 이미 `CurrentUser\\Root`·`LocalMachine\\Root` 에
    들어 있는 머신에서 **무관한 CA 를 pin 해도 IWR 이 러너 수신을 성공**시켰다. 그것을 폴백으로
    두면 신뢰 실패가 조용한 성공이 된다.

    1절(CA 수신)의 IWR 은 정당하다 — 평문 HTTP 이고 지문 대조가 덮는다. 그래서 2절만 본다.
    """
    section = _ps_code(_runner_section(_SETUP_PS1.read_text(encoding="utf-8-sig")))
    assert "Invoke-WebRequest" not in section, (
        "러너 수신 경로에 Invoke-WebRequest 가 있다 — $CaPath pin 을 우회해 "
        "무관한 CA 로도 수신이 성공한다"
    )


def test_python_fallback_uses_the_same_trust_anchor_as_the_runner(ps1_code):
    """폴백은 러너와 **같은** 신뢰 경로여야 한다 — 러너는 `--ca $CaPath` 로 파이썬 TLS 를 쓴다.

    다운로드만 다른 평가기(Schannel)로 하면 신뢰 경로가 둘로 갈리고, 이번 결함이 정확히 그
    갈라짐이었다(한쪽만 죽었다).
    """
    m = re.search(r"function\s+Get-RemoteFile.*?\n}", ps1_code, re.S)
    assert m, "Get-RemoteFile 본문을 찾지 못했다"
    body = m.group(0)
    assert "cafile=ca" in body, (
        "파이썬 폴백이 cafile 로 pin 된 CA 를 쓰지 않는다 — 시스템 신뢰로 떨어진다"
    )
    assert "$CaPath" in body, "파이썬 폴백에 $CaPath 가 전달되지 않는다"


# ── 축 3. fail-open 금지 ─────────────────────────────────────────────────────

def test_launch_failure_is_not_reported_as_success(ps1_code):
    """실행 자체가 실패하면 `$LASTEXITCODE` 는 건드려지지 않는다 — 초기값이 실패값이어야 한다.

    실측: 초기값을 0 으로 두면 없는 파이썬 경로로 불렀을 때 수신 함수가 `via=python` 을
    **성공 반환**했다(받은 파일은 없었다).
    """
    m = re.search(r"function\s+Invoke-NativeCapture.*?\n}", ps1_code, re.S)
    assert m, "Invoke-NativeCapture 본문을 찾지 못했다"
    body = m.group(0)
    init = re.search(r"\$global:LASTEXITCODE\s*=\s*(\d+)", body)
    assert init, "Invoke-NativeCapture 가 $LASTEXITCODE 초기값을 세우지 않는다"
    assert init.group(1) != "0", (
        "$LASTEXITCODE 초기값이 0 이다 — 실행조차 못 한 명령이 «성공» 으로 읽힌다"
    )


def test_exit_zero_alone_is_not_treated_as_downloaded(ps1_code):
    """종료코드 0 ≠ 파일이 왔다. 서버가 체크섬을 주지 않는 경로에서는 이것이 유일한 확인이다."""
    assert "function Test-Downloaded" in ps1_code, "수신 실물 확인 함수가 없다"
    m = re.search(r"function\s+Get-RemoteFile.*?\n}", ps1_code, re.S)
    assert m, "Get-RemoteFile 본문을 찾지 못했다"
    body = m.group(0)
    returns = re.findall(r"if\s*\((.*?)\)\s*\{\s*return\s+'(curl|python)'", body, re.S)
    assert len(returns) == 2, (
        f"성공 반환 지점이 2개(curl·python)가 아니다 — {len(returns)}개. "
        "경로가 늘거나 줄면 이 단언을 갱신하라"
    )
    for cond, which in returns:
        assert "Test-Downloaded" in cond, (
            f"'{which}' 성공 반환이 Test-Downloaded 로 보호되지 않는다 — "
            "0바이트·부분 수신·미실행이 성공으로 통과한다"
        )


def test_checksum_retry_checks_its_own_failure(ps1_code):
    """체크섬 재시도의 실패를 검사한다 — 종전에는 검사가 **아예 없었다**.

    그래서 실패한 재시도가 조용히 통과하고, 바로 다음 대조가 "러너 체크섬이 다릅니다" 로
    **오진**했다(실제 원인은 수신 실패). POSIX 판은 같은 자리에 `|| die` 가 있어 무사했다.
    """
    idx = ps1_code.find("Start-Sleep -Seconds 20")
    assert idx != -1, "체크섬 재시도 구간을 찾지 못했다"
    after = ps1_code[idx:idx + 700]
    assert "Get-RemoteFile" in after, "재시도가 단일 수신 경로를 쓰지 않는다(로직 중복 = 드리프트)"
    assert "catch" in after, "재시도 실패를 잡지 않는다 — 낡은 파일이 남고 오진으로 이어진다"


def test_stderr_reason_is_not_discarded(ps1_code):
    """실패 사유를 회수한다 — `SilentlyContinue` 아래 파이프는 ErrorRecord 를 조용히 버린다.

    실측: curl 이 exit 60 인데 회수된 메시지 길이가 **0** 이었다. 사유를 모으려고 만든 구조가
    무의미해진다. `Continue` 만이 던지지도(Stop) 버리지도(SilentlyContinue) 않는다.
    """
    m = re.search(r"function\s+Invoke-NativeCapture.*?\n}", ps1_code, re.S)
    assert m, "Invoke-NativeCapture 본문을 찾지 못했다"
    body = m.group(0)
    pref = re.search(r"\$ErrorActionPreference\s*=\s*'([A-Za-z]+)'", body)
    assert pref, "Invoke-NativeCapture 가 $ErrorActionPreference 를 세우지 않는다"
    assert pref.group(1) == "Continue", (
        f"$ErrorActionPreference='{pref.group(1)}' 이다 — 'Stop' 은 stderr 를 "
        "NativeCommandError 로 던지고, 'SilentlyContinue' 는 그 레코드를 버려 사유가 빈다"
    )


def test_failure_report_collects_every_attempted_path(ps1_code):
    """실패 시 시도한 경로의 사유를 **모아서** 낸다 — 하나만 말하면 다음 사람이 또 헤맨다."""
    m = re.search(r"function\s+Get-RemoteFile.*?\n}", ps1_code, re.S)
    assert m, "Get-RemoteFile 본문을 찾지 못했다"
    body = m.group(0)
    assert len(re.findall(r"\$why\s*\+=", body)) >= 2, (
        "실패 사유를 두 경로(curl·python) 모두에서 누적하지 않는다"
    )
    assert re.search(r"throw\s*\(\s*\$why", body), "누적한 사유를 throw 하지 않는다"


# ── 축 4. POSIX 판과의 의도된 divergence ──────────────────────────────────────

def test_posix_installer_does_not_carry_the_schannel_only_options():
    """POSIX 판에는 Schannel 전용 옵션이 **없어야** 한다.

    리눅스·macOS curl 은 OpenSSL 계열이라 폐기검사를 기본으로 하지 않아 애초에 이 실패가 없고,
    그 옵션은 Schannel 전용이라 거기서는 아무 일도 하지 않는다. "두 판을 같게 맞춘다" 는 이유로
    추가되는 것을 막는다 — 같아야 하는 것은 **계약**이고, 계약을 지키는 수단은 플랫폼마다 다르다.

    ⚠ 이것은 **부재 단언**이라 주석·문자열을 제외하지 **않는다**(§16.7 G11-a 명시 예외) —
      찾으려는 것이 바로 리터럴 안에 있기 때문이다. 다만 divergence 를 설명하는 산문은
      그 옵션 이름을 언급하므로, 실행 라인만 본다.
    """
    src = _SETUP_SH.read_text(encoding="utf-8")
    offending = [
        (i + 1, ln) for i, ln in enumerate(src.splitlines())
        if (_REVOKE_PREFERRED in ln or _REVOKE_FALLBACK in ln)
        and not ln.lstrip().startswith("#")
    ]
    assert not offending, (
        f"POSIX 판 실행 라인에 Schannel 전용 옵션이 있다: {offending}"
    )


def test_posix_installer_explains_the_divergence():
    """divergence 를 **문서로** 남긴다 — 설명 없는 비대칭은 다음 사람이 '버그' 로 읽고 되돌린다."""
    src = _SETUP_SH.read_text(encoding="utf-8")
    assert "Schannel" in src, (
        "POSIX 판이 Windows divergence 를 설명하지 않는다 — 왜 여기엔 그 옵션이 없는지 "
        "적혀 있지 않으면 parity 를 맞추려는 다음 변경이 그것을 되돌린다"
    )


# ── 축 5. 서빙 사본 동일성 (사용자가 실제로 받는 파일) ────────────────────────

@pytest.mark.parametrize("pair", [
    (_SETUP_PS1, _SERVED_PS1),
    (_SETUP_SH, _SERVED_SH),
], ids=["ps1", "sh"])
def test_served_copy_carries_the_fix(pair):
    """정본을 고쳐도 서빙 사본이 낡으면 **사용자는 낡은 것을 받는다**.

    체크섬은 서빙 파일에서 계산되므로 불일치 경보도 나지 않는다 — 조용히 구버전이 배포된다.
    """
    src, served = pair
    assert served.exists(), f"{served.name} 이 서빙 경로에 없다 — 사용자가 받을 수 없다"
    assert src.read_bytes() == served.read_bytes(), (
        f"{served.name} 이 정본과 다르다 — 사용자는 이 수정이 빠진 사본을 받는다"
    )


def test_served_ps1_keeps_the_utf8_bom():
    """BOM 유지 — Windows PowerShell 5.1 은 BOM 없는 .ps1 을 CP949 로 읽어 파서가 죽는다.

    이 수정이 한글 주석을 크게 늘렸으므로 회귀 위험이 커졌다. 편집기가 "UTF-8(BOM 없음)" 으로
    저장하면 그대로 되돌아온다.
    """
    for f in (_SETUP_PS1, _SERVED_PS1):
        head = f.read_bytes()[:3]
        assert head == b"\xef\xbb\xbf", (
            f"{f.name}: UTF-8 BOM 이 없다 — PowerShell 5.1 이 CP949 로 읽어 파서가 죽는다 "
            f"(첫 3바이트={head!r})"
        )
