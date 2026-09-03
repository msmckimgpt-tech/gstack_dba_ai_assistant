"""feature-0043 — 클라이언트 **명칭이 다섯 자리에서 갈리지 않는지** 단정한다.

## 왜 이 테스트가 필요한가

개명(2026-09-03, `mysql-ai-bridge` → `dqa-connect`) 전 이 이름은 **리터럴로 21곳**에 있었다.
그런 배치에서 한 곳을 놓치면 나타나는 결과가 특히 나쁘다 — **웹은 새 스킴으로 열고 OS 에는
옛 스킴이 등록돼 있는** 상태가 되는데, 브라우저는 스킴 핸들러 부재를 **감지하지 못한다.**
버튼은 조용히 죽고 사용자는 「연결이 안 된다」만 본다. 이 저장소는 이미 그 형태를 겪었다
(`bridge_setup.sh` §3-a 2026-08-31 실측: HKCU 키 없음 · 버튼 무동작 · 토큰 4건 하트비트 없음).

그래서 값을 `shared/dqa_identity.py` 하나로 모으고, **그 값이 나머지 네 자리에 실제로 도달하는지**
를 여기서 본다. 「정본을 만들었다」는 「정본이 쓰인다」가 아니다(AGENTS.md §16.7 G14-e).

## 무엇을 모수로 잡는가 (§16.7 G12)

명칭이 **사용자에게 노출되는 면 전체**다. 「이 파일이 만든 것」이 아니라 「이 이름이 실리는
곳 전체」로 정의한다:

  1. `shared/dqa_identity.py`                     — 정본 (웹 두 라우터가 import)
  2. `src/agent/base.py`                          — 러너 런타임 경로·UA
  3. `src/bridge_setup.sh`                        — POSIX 설치·핸들러 등록
  4. `src/bridge_setup.ps1`                       — Windows 설치·핸들러 등록
  5. `feature-0041/src/external_tool_mcp_{server,http}.py` — MCP 서버 self-name

5 번은 최소 컨테이너에서 **stdlib 만으로** 뜨는 것이 계약이라 정본을 import 하지 않는다.
그 대가로 드리프트 위험이 생기므로 **여기서 리터럴을 대조**한다 — 예외를 두되 그 예외가
검사 밖으로 나가지는 않게 한다.

## 값이 아니라 «배선» 도 본다

값만 맞추면 「상수는 옳은데 아무도 안 쓰는」 상태를 통과시킨다. 그래서 스킴이 실제로
핸들러 등록에 **꽂히는지**(MimeType · 레지스트리 키 · 번들 URLScheme)도 함께 단정한다.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_HERE = pathlib.Path(__file__).resolve()
_UNIT = _HERE.parents[2]
_REPO = _HERE.parents[3]

IDENT = _REPO / "shared" / "dqa_identity.py"
AGENT_BASE = _UNIT / "feature-0043-external-llm-bridge" / "src" / "agent" / "base.py"
SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
SETUP_PS = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
MCP_STDIO = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_server.py"
MCP_HTTP = _UNIT / "feature-0041-external-ai-tool-surface" / "src" / "external_tool_mcp_http.py"


def _read(p: pathlib.Path) -> str:
    assert p.is_file(), f"모수에 든 파일이 없다: {p}"
    return p.read_text(encoding="utf-8")


def _assign(text: str, name: str, *, quote: str = "\"'") -> str:
    """`NAME = "값"` / `NAME='값'` / `$Name = '값'` 에서 값만 뽑는다.

    ⚠ 주석·docstring 을 제외하지 않는다 — 이것은 **존재 단언이 아니라 값 추출**이고,
    추출식이 정확히 대입문 형태를 요구하므로 산문이 통과할 수 없다(§16.7 G11-a 는 «X 가
    있다» 류 단언을 대상으로 하며, 여기서는 잘못된 값이 잡히는 방향으로 틀린다).
    """
    m = re.search(rf"^\s*\$?{re.escape(name)}\s*=\s*([{quote}])(.+?)\1\s*$", text, re.M)
    assert m, f"{name} 대입을 찾지 못했다"
    return m.group(2)


@pytest.fixture(scope="module")
def canon() -> dict[str, str]:
    t = _read(IDENT)
    keys = {k: _assign(t, k) for k in
            ("APP_NAME", "SCHEME", "APP_ID", "MCP_SERVER_KEY", "LEGACY_SCHEME")}
    keys["LEGACY_MCP_KEY"] = _assign(t, "LEGACY_MCP_SERVER_KEY")
    return keys


# ── 1. 값이 다섯 자리에서 같은가 ──────────────────────────────────────────────

def test_scheme_is_identical_in_runner_and_both_setup_scripts(canon):
    """스킴이 정본·러너·설치 스크립트 두 벌에서 **같은 문자열**이다.

    갈리면 러너가 쓰는 홈(`~/.<scheme>`)과 설치 스크립트가 만드는 홈이 달라져, 러너는 매
    실행이 「처음 실행」이 되고 설정·CA 를 못 찾는다.
    """
    assert _assign(_read(AGENT_BASE), "_APP_SLUG") == canon["SCHEME"]
    assert _assign(_read(SETUP_SH), "DQA_SCHEME") == canon["SCHEME"]
    assert _assign(_read(SETUP_PS), "DqaScheme") == canon["SCHEME"]


def test_app_name_and_app_id_are_identical_in_both_setup_scripts(canon):
    """제품명·역-DNS id 도 두 설치 스크립트에서 같다 (macOS 번들 · Linux desktop 파일명)."""
    sh, ps = _read(SETUP_SH), _read(SETUP_PS)
    assert _assign(sh, "DQA_APP_NAME") == canon["APP_NAME"]
    assert _assign(ps, "DqaAppName") == canon["APP_NAME"]
    assert _assign(sh, "DQA_APP_ID") == canon["APP_ID"]
    assert _assign(ps, "DqaAppId") == canon["APP_ID"]
    assert _assign(_read(AGENT_BASE), "_APP_NAME") == canon["APP_NAME"]


def test_mcp_server_self_names_follow_the_canonical_key(canon):
    """MCP 서버 self-name 이 정본 키에서 파생된다 (stdlib-only 계약이라 import 대신 대조)."""
    key = canon["MCP_SERVER_KEY"]
    assert f'f"{key}-tools-{{LABEL}}"' in _read(MCP_STDIO), "stdio MCP self-name 이 정본과 다르다"
    assert f'"{key}-tools-http"' in _read(MCP_HTTP), "http MCP self-name 이 정본과 다르다"


# ── 1-b. 모수를 «열거» 가 아니라 «조회» 로 얻는다 (§16.7 G12-b) ────────────────
#
# ⚠ 이 테스트가 존재하는 이유는 실측이다. 위 1~3 을 다 쓴 뒤 `origin/main` 으로 rebase 하니
#   그 사이 `unit/feature-0046-native-client/`(ITEM-08 네이티브 클라이언트)가 새로 착륙해
#   있었고, 그 `core.py` 가 **옛 홈 `~/.mysql-ai-bridge` 를 그대로** 쓰고 있었다. 손으로
#   나열한 모수(정본·러너·설치 2벌·MCP 2벌)의 **밖**이라 위 테스트는 전부 초록이었다 —
#   가드가 성실히 통과하면서 노출면의 결손을 통과시키는, G12 가 기술한 바로 그 상태다.
#
#   그래서 모수를 **저장소 조회로** 구성한다: 나중에 붙는 경로도 자동으로 들어온다.

#: 옛 이름이 남아 있어도 되는 곳 — 정본의 `LEGACY_*` · 이력 기록 · 이 테스트 자신.
#: **경로가 아니라 «역할» 로 면제한다**: 값을 정의하는 곳과 지나간 일을 적은 곳뿐이다.
_LEGACY_ALLOWED = (
    "shared/dqa_identity.py",                                   # LEGACY_* 정의
    "unit/feature-0043-external-llm-bridge/src/bridge_setup.sh",   # 명칭 블록 + 실측 기록
    "unit/feature-0043-external-llm-bridge/src/bridge_setup.ps1",  # 명칭 블록
    "unit/feature-0043-external-llm-bridge/src/agent/base.py",     # 개명 주석 1줄
    "unit/feature-0043-external-llm-bridge/tests/test_name_ssot.py",
    "unit/feature-0043-external-llm-bridge/tests/test_wsl_scheme_handler.py",   # 이력 docstring
    "unit/feature-0003-agent-web-ui/tests/test_answer_model_notice_seal.py",    # 이력 docstring
)


def test_no_source_file_outside_the_allowlist_still_uses_the_old_name(canon):
    """저장소 **전체**를 조회해 옛 이름이 남은 소스가 없는지 본다.

    문서(`docs/`·`wiki/`·`unit/*/docs/`)는 제외한다 — 거기 남은 옛 이름은 **이력**이고, 이력을
    고치면 「있었던 일」이 거짓이 된다. 검사 대상은 **실행되는 것**뿐이다.
    """
    import subprocess

    legacy = canon["LEGACY_SCHEME"]
    r = subprocess.run(
        ["git", "grep", "-l", "--", legacy,
         ":!*/docs/*", ":!docs/*", ":!wiki/*", ":!.template-backups/*"],
        cwd=_REPO, capture_output=True, text=True)
    hits = sorted(p for p in r.stdout.split("\n") if p.strip())
    unexpected = [p for p in hits if p not in _LEGACY_ALLOWED]
    assert not unexpected, (
        "옛 이름이 허용 목록 밖 소스에 남아 있다 — 개명이 그 경로에 도달하지 않았다:\n  "
        + "\n  ".join(unexpected)
        + "\n(이력 기록이라면 `_LEGACY_ALLOWED` 에 사유와 함께 추가하라. 실행되는 값이라면 고쳐라.)")


def test_every_runner_home_reference_uses_the_canonical_scheme(canon):
    """`~/.<scheme>` 형태의 **설치 홈 참조**가 전부 정본 스킴을 쓴다.

    러너·설치 스크립트·네이티브 클라이언트가 각자 홈을 만든다. 하나라도 갈리면 그 컴포넌트는
    설정·CA 를 못 찾고 매 실행이 「처음 실행」이 된다 — 특히 클라이언트는 러너의 껍데기 교체라
    (ROADMAP §0.2) 같은 홈을 봐야 한다.
    """
    import re as _re
    import subprocess

    r = subprocess.run(
        ["git", "grep", "-nE", r"\.(mysql-ai-bridge|dqa-connect)\b", "--",
         ":!*/docs/*", ":!docs/*", ":!wiki/*", ":!.template-backups/*"],
        cwd=_REPO, capture_output=True, text=True)
    bad = []
    for line in r.stdout.split("\n"):
        if not line.strip():
            continue
        path = line.split(":", 1)[0]
        if path in _LEGACY_ALLOWED:
            continue
        for m in _re.finditer(r"\.(mysql-ai-bridge|dqa-connect)\b", line):
            if m.group(1) != canon["SCHEME"]:
                bad.append(line.strip()[:160])
    assert not bad, "정본 스킴이 아닌 설치 홈 참조:\n  " + "\n  ".join(bad)


# ── 2. 값이 실제로 «배선» 되는가 ──────────────────────────────────────────────

def test_scheme_reaches_every_handler_registration_site():
    """스킴 변수가 세 OS 의 등록 지점에 **꽂혀 있다**.

    값이 맞아도 등록 지점이 옛 리터럴을 쓰면 버튼은 죽는다 — 상수와 사용처를 함께 본다.
    """
    sh = _read(SETUP_SH)
    assert "MimeType=x-scheme-handler/$DQA_SCHEME;" in sh, "Linux MimeType 이 정본을 안 쓴다"
    assert "$DQA_APP_ID.desktop" in sh, "Linux desktop 파일명이 역-DNS id 를 안 쓴다"
    assert "HKCU:\\Software\\Classes\\\\$DQA_SCHEME" in sh, "WSL→Windows 레지스트리 키가 정본을 안 쓴다"
    assert "<string>$DQA_SCHEME</string>" in sh, "macOS CFBundleURLSchemes 가 정본을 안 쓴다"
    assert "<string>$DQA_APP_ID</string>" in sh, "macOS 번들 id 가 정본을 안 쓴다"

    ps = _read(SETUP_PS)
    assert '"HKCU:\\Software\\Classes\\$DqaScheme"' in ps, "Windows 레지스트리 키가 정본을 안 쓴다"


def test_web_emits_the_scheme_through_the_canonical_helper():
    """웹이 딥링크를 **정본 헬퍼**로 만든다 — 라우터가 스킴 문자열을 자체 조립하지 않는다."""
    oauth = _read(_UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "oauth_as.py")
    assert "_ident.scheme_url(token)" in oauth, "웹이 정본 헬퍼로 딥링크를 만들지 않는다"
    assert "_ident.MCP_SERVER_KEY" in oauth, "mcpServers 키가 정본에서 오지 않는다"


# ── 3. 옛 이름이 «별칭으로» 되살아나지 않는가 (하드 컷오버 계약) ──────────────

def test_legacy_scheme_is_only_used_for_cleanup_never_registered(canon):
    """옛 스킴은 **정리 대상**으로만 등장하고 등록 경로에는 없다.

    사용자 결정 2026-09-03 = 하드 컷오버. 별칭을 되살리면 두 스킴이 각각 러너를 띄울 수
    있게 되고, 이 feature 가 이미 겪은 «두 러너가 같은 계정으로 대기» 상태로 되돌아간다
    (`docs/TASK-20260901T173000-stale-runner-yield.md`).

    ⚠ **검사축이 이름이면 안 된다.** 초판은 「옛 이름이 쓰인 줄에 `LEGACY` 가 있어야 한다」로
    썼는데, 옛 이름을 담은 변수가 `DQA_LEGACY_SCHEME` 이라 **그 변수를 등록에 쓰면 검사를
    그대로 통과**했다 — 결함 주입 M7 이 생존해서 발견했다(§16.7 G11: 자기 문구가 자기 단언을
    통과시키는 형태). 그래서 축을 이름이 아니라 **등록 동사**로 내린다: 옛 이름(리터럴이든
    변수든)이 «등록하는 줄» 에 있으면 FAIL.
    """
    legacy = canon["LEGACY_SCHEME"]
    # 스킴을 OS 에 **등록**하는 동사들. 여기에 옛 이름이 닿으면 별칭이 되살아난 것이다.
    register_verbs = (
        "xdg-mime default", "MimeType=", "update-desktop-database",
        "New-Item", "New-ItemProperty", "Set-ItemProperty",
        "CFBundleURLSchemes", "CFBundleURLName", "CFBundleIdentifier",
        "lsregister",
    )
    legacy_tokens = (legacy, "DQA_LEGACY_SCHEME", "DqaLegacyScheme",
                     "DQA_LEGACY_HOME", "DqaLegacyHome")
    for path in (SETUP_SH, SETUP_PS):
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("Say "):
                continue  # 주석·사용자 안내 문구는 등록이 아니다
            if not any(tok in line for tok in legacy_tokens):
                continue
            hit = [v for v in register_verbs if v in line]
            assert not hit, (
                f"{path.name}:{lineno} 옛 이름이 **등록 경로**에 있다 (별칭 부활) — "
                f"동사={hit} 줄={stripped!r}")


def test_setup_scripts_remove_the_legacy_install_on_rerun():
    """재실행이 옛 홈·옛 핸들러 등록을 **지운다**.

    하드 컷오버라 옛 등록을 남기면 죽은 핸들러가 옛 홈의 러너를 되살릴 수 있다.
    """
    sh = _read(SETUP_SH)
    assert "cleanup_legacy_install()" in sh, "POSIX 정리 함수가 없다"
    assert "cleanup_legacy_install\n" in sh, "정리 함수가 호출되지 않는다(정의만 있다)"
    assert "$DQA_LEGACY_SCHEME.desktop" in sh, "옛 Linux desktop 파일을 지우지 않는다"
    assert "$DQA_LEGACY_SCHEME" in sh and "/f" in sh, "옛 Windows 레지스트리 키를 지우지 않는다"

    ps = _read(SETUP_PS)
    assert "$DqaLegacyHome" in ps and "Remove-Item" in ps, "Windows 판이 옛 홈을 지우지 않는다"
    assert "$DqaLegacyScheme" in ps, "Windows 판이 옛 레지스트리 키를 지우지 않는다"


def test_legacy_cleanup_refuses_a_directory_that_is_not_ours():
    """이름만 같은 남의 디렉토리를 지우지 않는다 (파괴적 연산 계약 — AGENTS.md §16.3 (a))."""
    sh = _read(SETUP_SH)
    assert 'grep -q "BRIDGE_TOKEN" "$DQA_LEGACY_HOME/bridge_agent.py"' in sh, (
        "POSIX 정리가 표지의 **내용**을 확인하지 않는다 — 이름만 같은 파일에 속는다")
    assert '[ "$DQA_LEGACY_HOME" != "$BRIDGE_HOME" ]' in sh, (
        "BRIDGE_HOME 을 옛 경로로 명시한 사용자의 현행 설치를 지울 수 있다")

    ps = _read(SETUP_PS)
    # POSIX 판과 **같은 계약**: 문자열이 아니라 정규화 후 비교한다(끝 구분자·`..` 회피).
    assert "GetFullPath($DqaLegacyHome)" in ps and "GetFullPath($Home_)" in ps, (
        "Windows 판이 경로를 정규화하지 않고 비교한다 — 끝 구분자 하나로 현행 홈이 삭제된다")
    assert "$_legacyNorm -ieq $_currentNorm" in ps, "Windows 판에 동일-경로 가드가 없다"
    assert "'bridge_agent.py'" in ps and "'launch.ps1'" in ps, (
        "Windows 판이 우리 설치물 표지를 확인하지 않는다")


# ── 4. 정리 로직을 «실제로 돌려» 본다 (소스 검사가 아니라 행위) ────────────────

def _run_cleanup(tmp_path, *, bridge_home: str, legacy_rel: str = ".mysql-ai-bridge",
                 make_marker: bool = True):
    """`cleanup_legacy_install` 만 떼어 실제 `sh` 로 돌린다. 반환: (rc, 옛 홈 잔존 여부)."""
    import subprocess
    import _setup_slice as _naming

    home = tmp_path / "home"
    (home / legacy_rel).mkdir(parents=True, exist_ok=True)
    if make_marker:
        # ⚠ 실물과 같은 표지를 쓴다. 파일 **이름**만 만들면 강화된 내용 검사에 걸린다 —
        #   그리고 그것이 정확히 codex P1-1 이 지적한 「이름만 같은 남의 파일」 케이스다.
        #   실 러너에는 `BRIDGE_TOKEN` 이 9회 나온다(실측).
        (home / legacy_rel / "bridge_agent.py").write_text(
            'import os\nBRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")\n')
    src = SETUP_SH.read_text(encoding="utf-8")
    body = src.split("norm_path() {", 1)[1].split("\n}\n", 1)
    assert len(body) == 2, "norm_path() 슬라이스가 깨졌다"
    fn_norm = "norm_path() {" + body[0] + "\n}\n"
    start = src.index("cleanup_legacy_install() {")
    end = src.index("\n}\n", start) + len("\n}\n")
    fn_clean = src[start:end]
    script = (
        "set -eu\n"
        f'HOME="{home}"\n'
        + _naming.naming_block().replace("$HOME", str(home))
        + f'BRIDGE_HOME="{bridge_home}"\n'
        'say() { :; }\n'
        'is_wsl() { return 1; }\n'
        'win_exe() { return 1; }\n'
        + fn_norm + fn_clean
        + "\ncleanup_legacy_install\n"
    )
    p = tmp_path / "run.sh"
    p.write_text(script)
    r = subprocess.run(["sh", str(p)], capture_output=True, text=True, timeout=30)
    return r, (home / legacy_rel).exists()


def test_cleanup_removes_a_genuine_legacy_install(tmp_path):
    """정상 경로 — 옛 홈이 우리 설치물이면 지운다 (§16.7 G9-c: 차단 로직의 «정상 경로» 실측)."""
    r, still = _run_cleanup(tmp_path, bridge_home=str(tmp_path / "home" / ".dqa-connect"))
    assert r.returncode == 0, r.stderr
    assert not still, "정상 경로인데 옛 홈이 남았다 — 정리가 동작하지 않는다"


def test_cleanup_refuses_a_directory_without_our_marker(tmp_path):
    """이름만 같은 남의 디렉토리는 지우지 않는다."""
    r, still = _run_cleanup(tmp_path, bridge_home=str(tmp_path / "home" / ".dqa-connect"),
                            make_marker=False)
    assert r.returncode == 0, r.stderr
    assert still, "우리 설치물 표지가 없는데 지웠다 — 남의 디렉토리 삭제 경로가 열려 있다"


def test_cleanup_never_deletes_the_current_home_even_with_a_trailing_slash(tmp_path):
    """⭐ `BRIDGE_HOME` 을 옛 경로에 **끝 슬래시 포함**으로 준 사용자를 해치지 않는다.

    자체 감사에서 발견한 실제 구멍이다. 문자열 그대로 비교하면
    `/home/u/.mysql-ai-bridge` != `/home/u/.mysql-ai-bridge/` 가 **참**이 되어, 그 사용자의
    «현행» 홈이 「옛 홈」으로 분류되고 그대로 삭제된다. 사용자가 옛 이름을 계속 쓰겠다고
    명시한 상태에서 그 선택이 데이터 삭제로 처벌받는 형태다.
    """
    legacy_with_slash = str(tmp_path / "home" / ".mysql-ai-bridge") + "/"
    r, still = _run_cleanup(tmp_path, bridge_home=legacy_with_slash)
    assert r.returncode == 0, r.stderr
    assert still, "끝 슬래시 하나로 사용자의 현행 설치가 삭제됐다"


def test_cleanup_never_deletes_the_current_home_via_a_dotdot_path(tmp_path):
    """`..` 를 낀 같은 경로도 같은 곳으로 본다 (정규화가 슬래시 전용이 아님을 확인)."""
    home = tmp_path / "home"
    (home / "x").mkdir(parents=True, exist_ok=True)
    weird = str(home / "x" / ".." / ".mysql-ai-bridge")
    r, still = _run_cleanup(tmp_path, bridge_home=weird)
    assert r.returncode == 0, r.stderr
    assert still, "`..` 를 낀 동일 경로를 다른 경로로 보고 현행 설치를 삭제했다"


# ── 5. codex 적대 리뷰(REV-20260903T120000) 가 잡은 것 ─────────────────────────

def _render_launch(tmp_path, bridge_home: str) -> str:
    """설치 스크립트에게 **실제로 `launch.sh` 를 굽게 하고** 그 내용을 돌려준다."""
    import subprocess
    import _setup_slice as _naming

    src = _read(SETUP_SH)
    blk = src.split('cat > "$LAUNCH_SH" <<LAUNCHEOF\n')[1].split("\nLAUNCHEOF")[0]
    out, gen = tmp_path / "launch.sh", tmp_path / "gen.sh"
    gen.write_text(
        _naming.naming_block()
        + "set -eu\nPY=python3\nBRIDGE_BASE='https://h.test'\nRUNNER_ARGS=''\n"
        + f'BRIDGE_HOME="{bridge_home}"\nLAUNCH_SH="{out}"\n'
        + 'cat > "$LAUNCH_SH" <<LAUNCHEOF\n' + blk + "\nLAUNCHEOF\n")
    r = subprocess.run(["sh", str(gen)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"launch.sh 생성 실패: {r.stderr}"
    return out.read_text(encoding="utf-8")


@pytest.mark.parametrize("home", [
    "/home/u/.dqa-connect",        # 기본
    "/home/u/.mysql-ai-bridge",    # 옛 경로를 계속 쓰겠다고 명시한 사용자
    "/opt/dqa/home",               # 완전히 다른 경로
])
def test_launch_script_bakes_the_effective_home(tmp_path, home):
    """굽힌 `launch.sh` 가 **설치 시점의 유효 홈**을 담는다 (codex 적대 리뷰 P1-2).

    OS 스킴 핸들러는 `launch.sh` 를 부를 때 `BRIDGE_HOME` 환경변수를 **전달하지 않는다**.
    그래서 기본값이 `$HOME/.<scheme>` 로 굳어 있으면, 커스텀 홈으로 설치한 사용자의
    `[내 AI 실행]` 은 엉뚱한 홈에서 러너를 찾다가 **무음 실패**한다.

    ⚠ 이 결함은 개명이 만든 것이 아니라 **선재**다 — 개명 전에는 기본값이 우연히 옛 경로와
    같아 그 사용자만 안 깨졌을 뿐, 다른 커스텀 홈은 내내 깨져 있었다. 개명이 그것을 드러냈다.
    """
    line = [l for l in _render_launch(tmp_path, home).splitlines()
            if l.startswith("BRIDGE_HOME=")]
    assert line, "굽힌 launch.sh 에 BRIDGE_HOME 기본값이 없다"
    assert home in line[0], (
        f"유효 홈이 구워지지 않았다 — 핸들러 재실행이 무음 실패한다: {line[0]!r}")


def test_launch_script_user_agent_is_fully_expanded(tmp_path):
    """굽힌 `launch.sh` 에 **전개되지 않은 변수**가 남지 않는다.

    codex 적대 리뷰 P2-1 은 중첩 `<<'DLEOF'`(quoted)를 근거로 `$DQA_SCHEME` 이 리터럴로
    남는다고 지적했다. **실측으로 반증됐다** — 바깥 `LAUNCHEOF` 가 unquoted 라 설치 시점에
    이미 전개되어 값이 구워진다. 그 반증을 여기 잠가, 누군가 바깥 heredoc 을 quoted 로 바꾸면
    (그러면 P2-1 이 진짜가 된다) 즉시 FAIL 하게 한다.
    """
    t = _render_launch(tmp_path, "/home/u/.dqa-connect")
    assert "$DQA_" not in t and "$DqaSc" not in t, "굽힌 launch.sh 에 미전개 명칭 변수가 남았다"
    assert "dqa-connect-launch" in t, "User-Agent 가 정본 값으로 구워지지 않았다"


def test_connect_guidance_and_json_config_use_the_same_mcp_key(canon):
    """CLI 안내와 JSON 설정이 **같은 MCP 키**를 쓴다 (codex 적대 리뷰 P2-2).

    두 경로가 다른 키를 주면 사용자가 어느 쪽을 따랐는지에 따라 도구 이름이 갈리고
    (`mcp__mysql-ai__*` vs `mcp__dqa__*`), 그 순간 SSOT 계약이 깨진다.
    """
    oauth = _read(_UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "oauth_as.py")
    assert f"claude mcp add --transport http {canon['LEGACY_MCP_KEY']}" not in oauth, (
        "CLI 안내가 옛 MCP 키를 준다")
    assert "claude mcp add --transport http {_ident.MCP_SERVER_KEY}" in oauth, (
        "CLI 안내가 정본 키에서 파생되지 않는다")


def test_served_client_filename_matches_the_build_artifact():
    """웹이 서빙하는 클라이언트 파일명 = 빌드 산출물명.

    갈리면 **배포는 성공하고 다운로드만 404** 가 된다 — 러너 배포본이 이미 겪은 형태라
    배포 스크립트가 그쪽엔 하드 게이트를 걸어 두었다. 클라이언트는 아직 그 게이트가 없다.
    """
    oauth = _read(_UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "oauth_as.py")
    build = _read(_UNIT / "feature-0046-native-client" / "src" / "scripts" / "build_client.py")
    app_name = _assign(build, "_APP_NAME")
    served = re.search(r'_CLIENT_REL\s*=\s*"agent/([^"]+)\.exe"', oauth)
    assert served, "_CLIENT_REL 을 찾지 못했다"
    assert served.group(1) == app_name, (
        f"서빙 파일명({served.group(1)}) 과 빌드 산출물명({app_name}) 이 다르다 — 다운로드 404")


def test_cleanup_refuses_a_lookalike_file_with_our_name_but_not_our_content(tmp_path):
    """이름만 `bridge_agent.py` 인 남의 파일에 속지 않는다 (codex 적대 리뷰 P1-1).

    표지를 파일 **이름**으로만 보면, 다른 프로그램이 `~/.mysql-ai-bridge/bridge_agent.py` 를
    하나 두는 것만으로 그 디렉토리 전체가 `rm -rf` 대상이 된다.
    """
    import subprocess
    import _setup_slice as _naming

    home = tmp_path / "home"
    (home / ".mysql-ai-bridge").mkdir(parents=True)
    # 이름은 같고 내용은 남의 것.
    (home / ".mysql-ai-bridge" / "bridge_agent.py").write_text("print('someone else')\n")
    (home / ".mysql-ai-bridge" / "important.db").write_text("남의 데이터\n")
    src = _read(SETUP_SH)
    fn_norm = "norm_path() {" + src.split("norm_path() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    s = src.index("cleanup_legacy_install() {")
    e = src.index("\n}\n", s) + 3
    script = ("set -eu\n" + f'HOME="{home}"\n'
              + _naming.naming_block().replace("$HOME", str(home))
              + f'BRIDGE_HOME="{home}/.dqa-connect"\n'
              'say() { :; }\nis_wsl() { return 1; }\nwin_exe() { return 1; }\n'
              + fn_norm + src[s:e] + "\ncleanup_legacy_install\n")
    p = tmp_path / "run.sh"
    p.write_text(script)
    r = subprocess.run(["sh", str(p)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert (home / ".mysql-ai-bridge" / "important.db").exists(), (
        "이름만 같은 남의 디렉토리를 지웠다 — 남의 데이터가 사라진다")


def test_powershell_never_interpolates_a_scheme_variable_before_a_colon():
    """`.ps1` 에서 `"$Var://"` 형태를 금지한다 — **파싱 자체가 실패**한다.

    PowerShell 은 `$Name:` 를 네임스페이스 한정 변수(`$env:PATH` 형태)로 읽는다. 스킴 문자열은
    **늘 `://` 를 달고 다니므로** 이 자리는 구조적으로 재발한다 — 실제로 개명 cycle 에서
    `Say "… ($DqaScheme://)."` 한 줄이 `.ps1` 전체를 파싱 불가로 만들었고, **로컬은 `pwsh`
    미설치로 skip 되어 CI 에서야 잡혔다**. `${Var}` 로 감싸야 한다.

    이 단언은 `pwsh` 없이도 도는 것이 요점이다(§16.7 G10 — 재발 클래스를 구조로 잠근다).
    """
    import re as _re

    bad = []
    for path in (SETUP_PS,):
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            # `$env:` 등 의도된 네임스페이스 한정자는 제외하고, 우리 변수 뒤의 `:` 만 본다.
            for m in _re.finditer(r"\$(?!env\b|global\b|script\b|local\b|using\b)"
                                  r"([A-Za-z_][A-Za-z0-9_]*):", line):
                bad.append(f"{path.name}:{lineno} ${m.group(1)}: → ${{{m.group(1)}}} 로 감쌀 것 "
                           f"| {line.strip()[:100]}")
    assert not bad, "PowerShell 변수 뒤 ':' — 파싱 실패한다:\n  " + "\n  ".join(bad)
