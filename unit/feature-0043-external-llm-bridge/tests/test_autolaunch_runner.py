"""feature-0043 — 이미 연결해 본 사용자에게는 **[내 AI 실행] 을 자동으로** (사용자 요청 2026-09-02).

    "이미 한 번 연결이 진행된 사용자들의 대상으로는 자동으로 '내 AI 실행' 이 진행될 수 있도록"
    "- 미연결 상태에서 '연결 필요' 버튼을 누를 경우
     - 로그인을 통해 서비스에 진입했을 경우"
    "'업데이트 필요' 가 버튼에 나타날 경우, 사용자가 해당 버튼을 클릭하는 것 만으로도
     러너가 재구성될 수 있도록"

## 이 파일이 잠그는 것 — 그리고 왜 그것들인가

1. **자격 판정의 근거는 서버가 아는 사실이다.** 「한 번 연결해 봤다」를 브라우저 로컬 저장에
   두면 다른 브라우저·기기에서 로그인한 같은 사람에게는 그 사실이 사라진다. 서버의 `last_os`
   는 러너가 *실제로 연결됐을 때만* 기록되므로 그 존재가 곧 이력이다.
2. **사용자 활성화를 잃지 않는다.** 실행은 `location.href = <스킴 URL>` 이고 그 URL 에는 토큰이
   실린다. 「클릭 → await 토큰 발급 → 이동」 순서면 이동 시점에 활성화가 이미 끊겨 크롬이
   조용히 거른다. 그래서 자격이 확인되는 순간 **미리 받아 두고** 클릭은 동기적으로 이동한다.
3. **토큰을 함부로 발급하지 않는다.** 프리페치는 자격 확인 뒤에만, 그리고 겹쳐 부르지 않는다.
4. **로그인 진입은 창을 열지 않는다.** 실패했다고 로그인하자마자 모달이 튀어나오면 그건
   접근성 개선이 아니라 방해다. 명시 클릭에서만 창으로 떨어진다.
5. **「업데이트 필요」는 실행만으로 풀려야 한다.** 종전 런처는 **디스크의 파일을 그대로** 다시
   띄웠다 — 그래서 갱신하려고 눌러도 같은 낡은 러너가 떴다. 런처가 최신본을 받아 교체한다.
6. **갱신 실패가 기동을 막지 않는다.** 못 받았거나 깨진 파일이면 있던 것을 그대로 쓴다 —
   갱신하려다 멀쩡한 러너를 못 띄우게 만드는 것이 가장 나쁜 결말이다.
"""
from __future__ import annotations

import pathlib
import re

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"
MODAL_JS = _WEB / "static" / "app" / "connect-modal.js"
SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"


def _js() -> str:
    return MODAL_JS.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """주석을 걷어낸 코드만. 구조 단언이 **설명문**에 걸려 참이 되지 않게 한다.

    (이 저장소가 이미 겪은 함정 — 문구를 손보면 통과하거나 깨지는 단언은 계약이 아니다.)
    """
    out = []
    for ln in text.splitlines():
        s = ln.lstrip()
        if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
            continue
        out.append(ln)
    return "\n".join(out)


def _fn(name: str) -> str:
    src = _code(_js())
    body = src.split(f"function {name}(", 1)[1]
    # 다음 톱레벨 선언까지
    cut = re.search(r"\n(?:async function|function|export |let |const \w+ = \()", body)
    return body[:cut.start()] if cut else body


# ── 1. 자격 판정 ──────────────────────────────────────────────────────────────


def test_history_comes_from_the_server_not_local_storage():
    """연결 이력의 근거는 서버의 `last_os` — 브라우저 로컬 저장이 아니다."""
    src = _code(_js())
    assert "_everConnected = !!String(b.last_os" in src, "서버 사실로 이력을 판정하지 않는다"
    assert "localStorage" not in src and "sessionStorage" not in src, \
        "이력을 브라우저에 두면 다른 기기·브라우저에서 같은 사람이 다른 취급을 받는다"


def test_eligibility_requires_history_and_excludes_usable_state():
    body = _fn("_autoLaunchEligible")
    assert "_everConnected" in body, "이력 없는 사용자에게 실행을 쏘면 안 된다(설치부터 필요)"
    assert "_connOk(_lastObs)" in body, "이미 쓸 수 있는 상태면 멀쩡한 러너를 갈아치우게 된다"


def test_stale_runner_is_an_eligible_target():
    """「업데이트 필요」가 자동 실행 대상이어야 한다 — 요청의 절반이 그것이다.

    `_connOk` 는 `listening && !stale` 이므로 stale 은 «쓸 수 없음» 으로 분류되고,
    따라서 `_autoLaunchEligible` 이 참이 된다. 그 연결고리를 여기서 고정한다.
    """
    body = _code(_js()).split("function _connOk(", 1)[1].split("\n}", 1)[0]
    assert "listening === true" in body and "stale !== true" in body, \
        "«쓸 수 있다» 판정에서 stale 축이 빠지면 업데이트 경로가 자동 실행 대상에서 사라진다"


# ── 2. 사용자 활성화 (이 기능이 조용히 죽는 유일한 방식) ──────────────────────


def test_click_path_navigates_without_an_await_in_front_of_it():
    """프리페치가 있으면 이동 앞에 `await` 가 없어야 한다 — 있으면 크롬이 조용히 거른다."""
    body = _fn("autoLaunch")
    head = body[:body.index("window.location.href")]
    # 유일하게 허용되는 await 는 «프리페치가 없을 때만» 도는 폴백이다.
    awaits = [ln for ln in head.splitlines() if "await" in ln]
    assert len(awaits) <= 1, f"이동 앞에 await 가 여러 개다: {awaits}"
    if awaits:
        assert "fallbackModal ?" in awaits[0], \
            "프리페치가 있는 정상 경로에서도 await 를 타면 활성화가 끊긴다"


def test_prefetch_happens_when_eligibility_is_known():
    """자격이 확인되는 지점(상태 조회 응답)에서 미리 받아 둔다."""
    body = _fn("_maybeAutoEntry")
    assert "_prefetchLaunch()" in body
    assert body.index("_autoLaunchEligible") < body.index("_prefetchLaunch()"), \
        "자격 확인 전에 발급하면 한 번도 연결한 적 없는 사람에게도 토큰이 발급된다"


def test_prefetch_is_not_duplicated():
    """겹쳐 부르면 토큰만 여러 개 발급된다."""
    body = _fn("_prefetchLaunch")
    assert "if (_prefetched) return" in body
    assert "if (_prefetching) return _prefetching" in body


def test_used_launch_url_is_discarded():
    """한 번 쓴 URL 은 버린다 — 재사용하면 만료·로그아웃된 토큰으로 조용히 실패한다."""
    body = _fn("autoLaunch")
    i_nav = body.index("window.location.href")
    assert "_prefetched = null" in body[i_nav:], "쓴 URL 을 남기면 다음 시도가 낡은 토큰을 쏜다"


# ── 3. 진입점별 동작 ──────────────────────────────────────────────────────────


def test_chip_and_gate_button_share_one_entry():
    """칩과 잠금 패널 버튼이 **같은 함수**로 간다 — 두 벌이면 한쪽만 고쳐진다."""
    src = _code(_js())
    assert src.count("_connectEntry") >= 3          # 정의 1 + 칩 + 게이트
    body = _fn("_connectEntry")
    assert "_autoLaunchEligible()" in body and "openConnectModal()" in body, \
        "이력 없는 사용자(설치 필요)는 종전대로 창으로 가야 한다"


def test_entry_autolaunch_runs_once_per_document():
    body = _fn("_maybeAutoEntry")
    assert "_autoEntryTried" in body, "페이지당 1회 제한이 없으면 상태 조회마다 러너를 재기동한다"


def test_entry_path_never_opens_the_modal():
    """로그인 진입 실패가 창을 열면 그건 접근성 개선이 아니라 방해다."""
    body = _fn("_maybeAutoEntry")
    assert "fallbackModal: false" in body
    assert "openConnectModal" not in body


def test_click_path_falls_back_to_the_modal():
    """명시 클릭은 막다른 길로 끝나면 안 된다 — 실패하면 종전 경로를 연다."""
    body = _fn("autoLaunch")
    assert body.count("openConnectModal()") >= 2, \
        "실행 불가·응답 없음 두 갈래 모두에서 창으로 떨어져야 한다"
    assert "fallbackModal" in body


def test_overlapping_launches_are_suppressed():
    body = _fn("autoLaunch")
    assert "_launchBusy" in body, "겹친 발사는 러너를 두 번 재기동하고 판정을 흐린다"


# ── 4. 판정 로직은 한 곳 ──────────────────────────────────────────────────────


def test_wait_verdict_is_single_sourced():
    """자동 실행과 [내 AI 실행] 버튼이 **같은 대기·판정 함수**를 쓴다.

    두 벌이면 한쪽만 고쳐지고, 그 순간 같은 상황에 다른 답을 하게 된다.
    """
    src = _code(_js())
    assert src.count("async function _awaitUsable(") == 1
    # 정의 1 + 호출 2(자동·수동). 정의도 같은 문자열이라 3 이 «호출부 둘» 의 표현이다.
    assert src.count("_awaitUsable(attempt, epoch)") == 3, "호출부가 둘(자동·수동)이어야 한다"


def test_verdict_distinguishes_no_answer_from_no_service():
    """«아무도 응답 안 함» 과 «서비스 응답 자체를 못 받음» 을 뭉치면 장애가 설치 안내로 둔갑한다."""
    body = _fn("_awaitUsable")
    assert "observed === 0 ? null : false" in body


def test_toast_can_fire_more_than_once_per_page():
    """러너는 한 세션에서도 여러 번 꺼졌다 붙는다 — 알림이 1회로 굳으면 안 된다."""
    body = _fn("autoLaunch")
    assert "_announced = false" in body
    assert body.index("_announced = false") < body.index("_announceConnected("), \
        "잠금을 풀기 전에 알리면 첫 성공 이후로는 영영 조용하다"


# ── 5. 「업데이트 필요」가 실행만으로 풀린다 ───────────────────────────────────


def _launcher_block(text: str, start: str, end: str) -> str:
    """생성되는 런처 스크립트 본문만 잘라 낸다.

    ⚠ here-doc 은 여는 구분자와 닫는 구분자가 **같은 문자열**이라, 단순히 `split(end)` 하면
    여는 쪽에 걸려 빈 조각이 나온다 — 그러면 이 단언들이 «찾지 못했다» 로 조용히 통과하거나
    엉뚱한 곳에서 깨진다. 여는 줄을 먼저 넘긴다.
    """
    after = text.split(start, 1)[1]
    after = after.split("\n", 1)[1]          # 여는 구분자가 있는 줄을 버린다
    return after.split(end, 1)[0]


def _sh_code(text: str) -> str:
    """주석을 걷어낸 셸 코드만.

    ⚠ 순서 단언에 주석이 섞이면 **설명문에 등장한 단어**가 코드 위치로 오인된다 — 실제로
    이 파일의 첫 판이 「`pkill` 은 검증 뒤에」 를 설명하는 주석에 걸려 거짓 실패했다.
    """
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def test_posix_launcher_refreshes_the_runner_before_starting():
    """런처가 최신본을 받아 교체한다 — 종전엔 디스크의 낡은 파일을 그대로 다시 띄웠다."""
    sh = SETUP_SH.read_text(encoding="utf-8")
    body = _launcher_block(sh, 'cat > "$LAUNCH_SH"', "\nLAUNCHEOF")
    assert "/static/agent/bridge_agent.py" in body, "런처가 러너를 받아 오지 않는다"
    assert "--cacert" in body, "받는 경로에 CA 대조가 없다"
    assert "bridge_agent.py" in body.split("mv -f", 1)[1][:120], "받은 파일로 교체하지 않는다"


def test_posix_launcher_refresh_never_blocks_startup():
    """갱신 실패는 **종전 동작**으로 떨어진다 — 있던 파일로 그대로 뜬다."""
    sh = SETUP_SH.read_text(encoding="utf-8")
    body = _launcher_block(sh, 'cat > "$LAUNCH_SH"', "\nLAUNCHEOF")
    refresh = body.split("_new=", 1)[1].split("nohup", 1)[0]
    assert "bail" not in refresh, "갱신 실패가 기동을 중단시킨다"
    assert "ast.parse" in refresh, "깨진 파일을 그대로 얹으면 러너가 문법 오류로 죽는다"
    assert "-s " in refresh or "-s \"" in refresh, "빈 파일 검사가 없다"


def test_windows_launcher_has_the_same_contract():
    ps = SETUP_PS1.read_text(encoding="utf-8")
    body = _launcher_block(ps, "$LaunchPs = Join-Path", "Set-Content -Encoding UTF8 $LaunchPs")
    assert "/static/agent/bridge_agent.py" in body
    assert "ast.parse" in body
    assert "try {" in body and "} catch { }" in body, "갱신 실패가 기동을 막으면 안 된다"


def test_refresh_runs_after_token_validation():
    """토큰을 검증하기 **전에** 파일을 건드리지 않는다.

    이 스킴은 아무 웹페이지나 열 수 있다 — 검증 전 부수효과는 임의 사이트가 남의 러너 파일을
    갈아치우게 하는 통로가 된다(같은 이유로 `pkill` 도 검증 뒤에 있다).
    """
    sh = SETUP_SH.read_text(encoding="utf-8")
    body = _sh_code(_launcher_block(sh, 'cat > "$LAUNCH_SH"', "\nLAUNCHEOF"))
    assert body.index("--check") < body.index("_new="), "검증 전에 러너 파일을 교체한다"
    assert body.index("_new=") < body.index("pkill"), "교체가 종료보다 뒤면 낡은 파일로 다시 뜬다"


# ── 6. 진입 자동 시도가 사용자의 클릭을 삼키지 않는다 (라이브 실측 2026-09-02) ──


def test_user_click_beats_an_in_flight_entry_attempt():
    """진입 자동 시도의 ~30초 대기창 안에 누른 클릭이 **조용히 삼켜지면 안 된다**.

    배포 후 실 브라우저에서 정확히 그것이 관측됐다 — 칩을 눌렀는데 실행도 안 되고 창도 안
    열렸다. 그건 이 개선 **이전**(무조건 창 열기)보다 나쁘다. 자동 시도는 사용자를 돕는
    장치이지 막는 장치가 아니다.
    """
    body = _fn("autoLaunch")
    guard = body[:body.index("const ready")]
    assert "_launchBusyReason" in guard, "진행 중 시도의 성격을 구분하지 않는다(클릭도 함께 막힌다)"
    assert 'reason === "click"' in guard, "클릭이 자동 시도를 대체할 길이 없다"


def test_duplicate_clicks_are_still_suppressed():
    """클릭끼리의 중복은 그대로 막는다 — 러너를 두 번 재기동할 이유가 없다."""
    guard = _fn("autoLaunch")
    guard = guard[:guard.index("const ready")]
    assert '_launchBusyReason !== "click"' in guard, "클릭 중복까지 통과시킨다"


def test_superseded_attempt_does_not_undo_the_newer_one():
    """대체된 시도는 잠금을 풀지도, 창을 열지도 않는다.

    풀면 새 시도의 중복 방어가 사라지고, 창을 열면 사용자가 방금 시작한 흐름 위로 남의 시도가
    만든 창이 덮인다.
    """
    body = _fn("autoLaunch")
    assert "const seq = ++_launchSeq" in body
    assert "if (seq !== _launchSeq) return true;" in body, "대체 판정 없이 결과를 반영한다"
    fin = body[body.index("} finally {"):]
    assert "if (seq === _launchSeq)" in fin, "대체된 시도가 잠금을 푼다"
