"""Download a trusted update ZIP and prepare it in-process; preserve current work."""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import core, version, installation, update_package

#: 매니페스트를 묻는 자리. **고정이다** — 서버 응답의 값을 쓰지 않는다(규율 1).
MANIFEST_PATH = "/api/ai/client/latest"

#: 설치기를 받는 자리의 접두. 뒤에 매니페스트의 `filename` 이 붙되, 그 이름은 아래
#: `UPDATE_NAME_RE` 를 통과해야 한다 — 경로 구분자·`..`·인자로 읽히는 선두 `-` 를 배제한다.
DOWNLOAD_PREFIX = "/client/"

#: 받아들이는 설치기 파일명. **`publish_release.py` 가 만드는 이름과 같은 모양**이다.
UPDATE_NAME_RE = re.compile(r"^DQAConnect-Update-[0-9]+(\.[0-9]+){0,3}\.zip$")

#: 매니페스트·다운로드 상한(초). 업데이트는 급한 일이 아니므로 짧게 끊고 다음 기회를 기다린다.
MANIFEST_TIMEOUT_SEC = 20.0
DOWNLOAD_TIMEOUT_SEC = 600.0

#: 확인 간격의 바닥(초). 기동 때 한 번 보고, 상주 중에는 이 간격으로 다시 본다.
#: 러너의 120초보다 훨씬 긴 이유: 저쪽은 파일 한 장 교체지만 이쪽은 **설치기 실행**이라
#: 사용자에게 확인창이 뜬다 — 자주 물으면 사용자가 습관적으로 넘기게 되고, 그러면 정작
#: 위험한 순간의 확인도 같이 넘어간다(`bridge.DANGEROUS` 가 조회를 제외한 것과 같은 근거).
CHECK_INTERVAL_SEC = 4 * 60 * 60.0

#: 설치기가 이보다 작으면 설치기일 리 없다 — 오류 페이지·잘린 응답·리다이렉트 본문을 거른다.
MIN_SETUP_BYTES = 1_000_000
#: 상한. 매니페스트가 거짓 크기를 말해도 디스크를 다 쓰지 않게 읽기 자체를 끊는다.
MAX_SETUP_BYTES = 400 * 1024 * 1024

#: 홈에 두는 업데이트 설정·기록. `server.json` 과 **별개 파일**이다 — 서버 고정은 보안
#: 판정이고 이쪽은 사용자 취향이라, 한 파일에 섞으면 한쪽 쓰기 실패가 다른 쪽을 잃는다.
_STATE_FILE = "update.json"

#: 회차별 결과를 남기는 곳. **배포된 클라이언트는 원격 디버깅이 불가능하다** — 「업데이트가
#: 안 된다」는 신고가 왔을 때 원인(마운트 부재·매니페스트 불일치·CA 만료·TLS 실패·설치 실패)을
#: 가릴 신호가 한 줄도 없으면 그 신고는 재현 불가로 남는다(적대 리뷰 C2).
_LOG_FILE = "update.log"
_LOG_MAX_BYTES = 256 * 1024

#: 내려받은 설치기를 두는 **고정 자리**. 매번 새 `mkdtemp` 를 쓰면 릴리스마다 수십 MB 가
#: `%TEMP%` 에 영구 누적되고, 실패가 반복되면(4시간 주기) 디스크를 조용히 먹는다(C3).
_DOWNLOAD_DIR = "update"

#: 사내 CA. `core.install_ca` 가 연결 성공 시 여기에 적어 둔 것과 같은 자리다.
_CA_FILE = "rootCA.crt"

#: 확인 실패 후 다시 볼 때까지의 간격(초). 성공 간격보다 **짧다** — TLS·CA·네트워크 실패를
#: 성공과 같은 주기로 묻으면 「CA 가 만료돼 4시간마다 조용히 실패하는 머신」이 「최신인 머신」과
#: 구분되지 않는다(적대 리뷰 §3-3).
RETRY_INTERVAL_SEC = 30 * 60.0

#: 설치 시도 표식의 유효 기간(초). 이보다 오래된 표식은 **판정하지 않는다** — 그 사이에
#: 사용자가 손으로 설치·제거·되돌렸을 수 있어 「실패했다」는 주장의 근거가 사라진다.
PENDING_MAX_AGE_SEC = 24 * 60 * 60.0


@dataclass(frozen=True)
class Update:
    """받을 수 있는 새 버전. **매니페스트 원문이 아니라 검증을 통과한 값만** 담는다."""
    version: str
    filename: str
    sha256: str
    size: int
    notes: str = ""

    @property
    def label(self) -> str:
        return f"{core.DISPLAY_NAME} {self.version}"


# ── 설정·기록 ────────────────────────────────────────────────────────────────────

def _state(home: Path) -> dict:
    try:
        data = json.loads((home / _STATE_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 기본값으로 시작한다
        return {}


def _write_state(home: Path, **fields) -> None:
    """`server.json` 과 같은 방식 — 읽고 합쳐 다시 쓴다. 실패는 조용히 넘긴다."""
    doc = _state(home)
    doc.update({k: v for k, v in fields.items() if v is not None})
    try:
        home.mkdir(parents=True, exist_ok=True)
        (home / _STATE_FILE).write_text(json.dumps(doc, ensure_ascii=False),
                                        encoding="utf-8")
    except Exception:  # noqa: BLE001 — 설정을 못 적는다고 프로그램이 죽지 않는다
        pass


def auto_apply(home: Path) -> bool:
    """확인 없이 적용해도 되는가. **기본값은 거짓** (사용자 결정 2026-09-07).

    ⚠ 이 배포본은 서명되지 않았다. 무음 적용을 기본으로 두면 「알 수 없는 게시자」의 설치기가
    사용자 모르게 도는 것이 정상 동작이 된다.
    """
    return bool(_state(home).get("auto_apply") is True)


def set_auto_apply(home: Path, value: bool) -> None:
    _write_state(home, auto_apply=bool(value))


def due(home: Path, now: float | None = None,
        interval: float = CHECK_INTERVAL_SEC) -> bool:
    """지금 확인할 차례인가. 사용자가 직접 누른 확인은 이 게이트를 타지 않는다.

    ⚠ **직전 회차가 실패였으면 더 짧게 다시 본다.** 실패를 성공과 같은 주기로 묻으면
    「사내 CA 가 만료돼 조용히 실패하는 머신」과 「최신인 머신」이 구분되지 않는다.
    """
    now = time.time() if now is None else now
    doc = _state(home)
    last = doc.get("last_check")
    try:
        last = float(last)
    except (TypeError, ValueError):
        return True
    # 시계가 뒤로 갔으면(재부팅·NTP 보정) 「아직 멀었다」로 굳지 않게 다시 본다.
    if last > now:
        return True
    if doc.get("last_error"):
        interval = min(interval, RETRY_INTERVAL_SEC)
    return (now - last) >= interval


def mark_checked(home: Path, now: float | None = None,
                 error: str | None = None) -> None:
    """이번 회차의 결과를 남긴다. `error` 가 있으면 **실패로** 기록한다.

    ⚠ 성공과 실패를 같은 필드로 접지 않는다 — 접으면 위 `due()` 가 backoff 를 가를 근거를
    잃고, 운영자는 「확인은 돌았는데 왜 안 오르나」를 답할 자료가 없다(적대 리뷰 §3-3).
    """
    _write_state(home, last_check=float(time.time() if now is None else now),
                 last_error=(str(error)[:200] if error else ""))


def log(home: Path, line: str) -> None:
    """회차 결과를 `update.log` 에 append 한다. **실패해도 조용히 넘긴다.**

    ⚠ 자격증명·토큰을 쓰지 않는다 — 이 파일은 사용자가 지원 요청에 첨부할 수 있는 것이다.
    """
    try:
        home.mkdir(parents=True, exist_ok=True)
        path = home / _LOG_FILE
        # 무한 성장 금지 — 상한을 넘으면 새로 시작한다(회전 파일을 두지 않는다: 이 로그의
        # 가치는 「최근에 무슨 일이 있었나」이고 장기 이력이 아니다).
        if path.exists() and path.stat().st_size > _LOG_MAX_BYTES:
            path.unlink(missing_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] v{version.CLIENT_VERSION} {line}\n")
    except Exception:  # noqa: BLE001
        pass


# ── 적용 결과의 관측면 ───────────────────────────────────────────────────────────
#
# ⚠ **설치기를 띄운 것과 설치가 된 것은 다르다.** `apply()` 는 `Popen` 이 성공했는지만 알 수
#   있고, `/SUPPRESSMSGBOXES` 때문에 설치기 자신의 오류 대화상자도 뜨지 않는다. 그 상태에서
#   우리는 스스로 종료하므로, 설치가 실패하면 사용자는 **프로그램이 사라지고 돌아오지 않는**
#   상태를 얻는다 — 화면은 방금 「다시 시작됩니다」라고 말했다(적대 리뷰 F1).
#
#   그래서 종료 **전에** 「무엇을 시도했는지」를 남기고, 다시 뜬 프로세스가 **자기 버전으로**
#   그 시도의 결과를 판정한다. 이것이 Inno 의 프로세스 모델·재시작 관리자와 무관하게
#   성립하는 유일한 대조다 (§16.7 G14 — 처방은 결과 대조로 끝난다).

def mark_pending_install(home: Path, target: str) -> None:
    _write_state(home, pending_install=str(target),
                 pending_at=float(time.time()))
    log(home, f"apply start → {target}")


def clear_pending_install(home: Path) -> None:
    """시도가 **없었던** 것으로 되돌린다 — 설치기를 띄우지 못한 경우.

    ⚠ 표식을 남기면 다음 기동이 「설치가 완료되지 않았습니다」라고 말한다. 그런데 그 경우는
    이미 그 자리에서 「설치 프로그램을 실행하지 못했습니다」라고 말했으므로, 같은 실패를
    두 번 다르게 말하는 것이 된다.
    """
    _write_state(home, pending_install="", pending_at=0.0)


def settle_pending_install(home: Path,
                           current: str = version.CLIENT_VERSION) -> str | None:
    """기동 시 1회 호출. **시도가 이뤄지지 않았으면** 사용자에게 할 말을 돌려준다.

    - 시도한 적 없음 → `None`
    - 시도했고 버전이 올랐음 → 표식을 지우고 `None` (조용히 성공)
    - 시도했는데 버전이 그대로 → 표식을 지우고 **안내 문구**를 돌려준다
    """
    doc = _state(home)
    target = str(doc.get("pending_install") or "").strip()
    if not target:
        return None
    try:
        age = time.time() - float(doc.get("pending_at") or 0.0)
    except (TypeError, ValueError):
        age = 0.0
    _write_state(home, pending_install="", pending_at=0.0)
    if age > PENDING_MAX_AGE_SEC or age < 0:
        # ⚠ 오래된 표식으로 「실패했다」고 말하지 않는다. 그 사이에 사용자가 손으로
        #   설치·제거·되돌렸을 수 있고, 그러면 우리 주장은 근거가 없다 — 모르는 것을
        #   단정하는 쪽이 침묵보다 나쁘다(§16.7 G7-c). 기록에는 남긴다.
        log(home, f"apply UNKNOWN → stale marker {target} (age {int(age)}s)")
        return None
    if not version.is_newer(target, current) or installation.active_version() == target:
        log(home, f"apply ok → now v{current}")
        return None
    log(home, f"apply FAILED → still v{current} (wanted {target})")
    return (f"업데이트({target}) 준비가 완료되지 않았습니다 — 지금은 {current} 로 실행 중입니다.\n\n"
            "다운로드나 파일 적용이 중단되었을 수 있습니다. "
            "다시 시도하려면 알림 영역 아이콘을 오른쪽 클릭 → [업데이트 확인] 을 누르세요.")


# ── 신뢰 앵커 ────────────────────────────────────────────────────────────────────

def update_base(home: Path) -> str:
    """설치기를 받을 서버. 근거가 약하면 **빈 문자열**(= 확인하지 않는다).

    ⚠ `core.startup_base` 와 **일부러 다르다.** 저쪽은 「창을 어디로 열까」라서
    `remembered_base`(사용자가 받아들인 딥링크 주소)까지 본다. 여기서 그 값을 쓰면, 남이 만든
    링크를 한 번 수락한 것만으로 그 서버가 **이 컴퓨터에서 실행될 설치기**를 지목하게 된다.

    ⚠ **동봉 주소가 고정 주소를 이긴다** (적대 리뷰 §3-a — 종전에는 반대였다). 동봉값은
    *이 설치본을 만든 배포*가 적어 둔 것이므로 **설치 행위 자체가 인증한 앵커**다. 고정
    (TOFU)은 한 번 연결에 성공한 딥링크의 주소일 수 있어 그보다 약하다. 창을 여는 근거와
    실행 파일을 받는 근거를 세기로 가르는 것이 규율 2 인데, 우선순위에서 약한 쪽이 이기면
    그 규율은 선언만 남는다.

    동봉값이 없는 빌드(개발·`--service-base` 미지정)에서는 고정 주소가 유일한 앵커다 —
    그 사실을 기록에 남긴다(조용히 약한 앵커로 내려가지 않는다).
    """
    bundled = core.usable_base(core.bundled_service_base() or "")
    if bundled and bundled.lower().startswith("https://"):
        return bundled
    pinned = core.usable_base(core.pinned_server(home) or "")
    if pinned and pinned.lower().startswith("https://"):
        log(home, "update source = pinned server (no bundled address in this build)")
        return pinned
    return ""


def ca_path(home: Path) -> str:
    """사내 CA 파일. 없으면 빈 문자열 — 그때는 확인 자체를 하지 않는다.

    전역 신뢰 저장소로 폴백하지 않는다. 이 서버의 인증서는 사내 CA 가 서명한 것이라
    전역 검증은 어차피 실패하고, 성공한다면 그것은 **다른 서버**라는 뜻이다.
    """
    p = home / _CA_FILE
    return str(p) if p.is_file() else ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise OSError("update redirects are not allowed")


def _open(url: str, ca: str, timeout: float):
    ctx = ssl.create_default_context(cafile=ca)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect())
    return opener.open(urllib.request.Request(url, method="GET"), timeout=timeout)


# ── 확인 ─────────────────────────────────────────────────────────────────────────

def parse_manifest_detail(raw: bytes, current: str = version.CLIENT_VERSION
                         ) -> "tuple[Update | None, str]":
    """`(Update 또는 None, 사유)`. **정상적으로 낡은 것**은 사유가 빈 문자열이다.

    ⚠ 「이미 최신이다」와 「매니페스트를 읽지 못했다」는 다른 사실이다(적대 리뷰 C-3).
    종전에는 둘 다 `None` 이라, 엣지 오류 본문(200 + HTML)·잘린 JSON·퍼블리시 버전 실수가
    전부 사용자에게 **「이미 최신입니다」**로 보고됐다 — 못 받는 머신이 스스로를 최신으로
    믿는다. 전송 계층만 갈라 놓고 내용 계층을 접어 두면 그 구멍은 그대로다.
    """
    upd = parse_manifest(raw, current)
    if upd is not None:
        return upd, ""
    # 왜 거절했는지 한 단계 더 본다 — JSON 이 아니거나 필드가 깨졌으면 «실패**다.
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None, "bad-manifest"
    if not isinstance(doc, dict):
        return None, "bad-manifest"
    ver = str(doc.get("version") or "").strip()
    if version.parse(ver) is None:
        return None, "bad-manifest"
    if not version.is_newer(ver, current):
        return None, ""              # 정상적으로 낡음 — 실패가 아니다
    return None, "bad-manifest"      # 버전은 새것인데 나머지가 어긋났다


def parse_manifest(raw: bytes, current: str = version.CLIENT_VERSION) -> Update | None:
    """매니페스트 → 검증 통과한 `Update`. 하나라도 어긋나면 `None`.

    **순수 함수다** — 네트워크·파일시스템을 만지지 않으므로 테스트가 모든 거절 경로를 돈다.
    """
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(doc, dict):
        return None

    ver = str(doc.get("version") or "").strip()
    if not version.is_newer(ver, current):
        return None                       # 규율 4 — 같거나 낡으면 아무것도 하지 않는다

    package = doc.get("update")
    if not isinstance(package, dict):
        return None
    name = str(package.get("filename") or "").strip()
    if not UPDATE_NAME_RE.match(name):
        return None                       # 규율 1 — 이름이 곧 경로다
    # 파일명이 버전을 말하고 매니페스트도 버전을 말한다. **두 값이 어긋나면 거절한다** —
    # 어느 쪽을 믿을지 고르는 순간 나머지 하나는 검증이 아니라 장식이 된다.
    if name != f"DQAConnect-Update-{ver}.zip":
        return None

    digest = core.normalize_fingerprint(str(package.get("sha256") or ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None                       # 지문이 아닌 것은 지문으로 받지 않는다

    size = package.get("size")
    if type(size) is not int:
        return None
    if not (MIN_SETUP_BYTES <= size <= MAX_SETUP_BYTES):
        return None

    notes = str(doc.get("notes") or "").strip()[:400]
    return Update(version=ver, filename=name, sha256=digest, size=size, notes=notes)


def check_detail(home: Path,
                 current: str = version.CLIENT_VERSION) -> "tuple[Update | None, str]":
    """`(새 버전 또는 None, 실패 사유)`. **최신이면 사유도 빈 문자열**이다.

    ## 왜 사유를 따로 돌려주는가 (적대 리뷰 §3-3)

    `check()` 는 「최신이다」와 「확인하지 못했다」를 **둘 다 `None`** 으로 접는다. 그러면
    사내 CA 가 만료돼 조용히 실패하는 머신이 최신인 머신과 구분되지 않고, 운영자는
    「업데이트가 안 나간다」는 신고에 답할 자료가 없다. 사유를 따로 두면 호출부가 그것을
    기록·backoff 에 쓸 수 있다.

    ⚠ **어떤 실패도 예외로 새어 나가지 않는다.** 이 함수는 기동 경로와 상주 루프에서 불리고,
    거기서 던지면 사용자가 보는 것은 「업데이트를 못 봤다」가 아니라 **프로그램이 죽는 것**이다.
    """
    base, ca = update_base(home), ca_path(home)
    if not base:
        return None, "no-pinned-server"
    if not ca:
        return None, "no-ca"
    try:
        with _open(base + MANIFEST_PATH, ca, MANIFEST_TIMEOUT_SEC) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            if status != 200:
                # ⚠ 이 분기는 **2xx 비-200**(204 등)만 온다 — `urlopen` 은 4xx/5xx 를 예외로
                #   올리므로 아래 `except` 가 그 진짜 입구다(적대 리뷰 C-3 가 지적한 죽은 분기).
                return None, f"http-{status}"
            raw = resp.read(64 * 1024)
    except Exception as exc:  # noqa: BLE001 — 네트워크·TLS·타임아웃·HTTP 오류
        code = getattr(exc, "code", None)
        if code == 404:
            # 404 = 「배포 중인 것이 없다」는 **정상 상태**다 — 실패로 기록하지 않는다.
            return None, ""
        if isinstance(code, int):
            # 403·500·502 를 한 덩어리로 접지 않는다 — 운영자가 원인을 가릴 값이다.
            return None, f"http-{code}"
        return None, type(exc).__name__
    prepared = installation.prepared_version(current)
    return parse_manifest_detail(raw, prepared or current)


def check(home: Path, current: str = version.CLIENT_VERSION) -> Update | None:
    """서버에 더 새 버전이 있는가. 없거나 확인할 수 없으면 `None`.

    사유가 필요한 호출부는 `check_detail()` 을 쓴다 — 이쪽은 그 얇은 껍데기다.
    """
    return check_detail(home, current)[0]


# ── 내려받기 ─────────────────────────────────────────────────────────────────────

def download_dir(home: Path) -> Path:
    """받은 설치기를 두는 자리. **고정이다** — 매 회 새 임시 디렉토리를 만들지 않는다.

    ⚠ 종전에는 `tempfile.mkdtemp()` 였고 성공·실패 어느 경로에서도 지우지 않아, 릴리스마다
    수십 MB 가 `%TEMP%` 에 영구 누적됐다(적대 리뷰 C3). 고정 자리를 쓰면 다음 회차가 이전
    파일을 덮으므로 누적이 구조적으로 사라진다.
    """
    return home / _DOWNLOAD_DIR


def download(home: Path, update: Update, dest_dir: Path | None = None) -> Path | None:
    """설치기를 받아 **검사까지 통과한** 파일 경로. 하나라도 어긋나면 `None`.

    받는 곳은 `update_base()` + `DOWNLOAD_PREFIX` + 검증된 파일명이다 — 매니페스트가 실어
    보낸 어떤 URL 도 쓰지 않는다(규율 1).

    ⚠ **스트리밍이다.** 종전에는 `resp.read(size+1)` 로 최대 400MB 를 한 번에 버퍼링했다 —
    적대적 서버가 큰 크기를 선언하면 그만큼 메모리를 점유한다(적대 리뷰 C3). 지금은 파일로
    흘리며 sha256 을 증분 계산하고, 상한을 넘으면 **읽기 자체를 끊는다**.

    ⚠ 판정은 `matches()` **한 곳**이다 — 스트리밍 경로와 바이트 경로가 각자 판정하면
    한쪽만 고쳐지는 드리프트가 난다.
    """
    base, ca = update_base(home), ca_path(home)
    if not base or not ca:
        return None
    if not UPDATE_NAME_RE.fullmatch(update.filename):
        # ⚠ `match` 가 아니라 `fullmatch` 다. Python 의 `$` 는 **말미 개행 앞에서도** 매치해
        #   `"…exe\n"` 이 통과한다 — 현재는 뒤 단계가 막지만, 무결성 검사가 «우연히 도달
        #   불가» 에 기대는 것은 옳지 않다(`core.fingerprints_match` 가 세운 기준).
        return None
    out_dir = Path(dest_dir) if dest_dir else download_dir(home)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        return None
    # ⚠ **흐름별로 유일한 이름**이다. 종전에는 PID 를 붙였는데 트레이 동작·주기 감시·웹
    #   패널은 **같은 프로세스의 다른 스레드**라 한 파일을 공유했다 — 적대 리뷰가 두 스레드로
    #   재현했다: T1 이 검사한 스트림과 T1 이 돌려준 경로의 내용이 **완전히 달랐다**.
    #   `mkstemp` 는 커널이 유일성을 보장하므로 그 형태가 구조적으로 불가능해진다.
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f"{update.filename}.", suffix=".part",
                                        dir=str(out_dir))
        os.close(fd)
    except Exception:  # noqa: BLE001
        return None
    tmp = Path(tmp_name)
    h = hashlib.sha256()
    total = 0
    head = b""
    try:
        with _open(base + DOWNLOAD_PREFIX + update.filename, ca,
                   DOWNLOAD_TIMEOUT_SEC) as resp, tmp.open("wb") as f:
            if int(getattr(resp, "status", 0) or 0) != 200:
                raise OSError("status")
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SETUP_BYTES or total > update.size:
                    # 「선언보다 크다」를 관측하는 지점이다 — 더 읽지 않는다.
                    raise OSError("oversize")
                if not head:
                    head = chunk[:2]
                h.update(chunk)
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    except Exception:  # noqa: BLE001 — 네트워크·TLS·디스크·상한
        tmp.unlink(missing_ok=True)
        return None
    if not matches(total, h.hexdigest(), head, update):
        tmp.unlink(missing_ok=True)
        return None
    # ⚠ **최종 이름도 흐름별로 유일하다.** 공용 이름(`<filename>`)에 `os.replace` 하면,
    #   그 inode 를 다른 흐름이 계속 쓰는 동안 우리가 그 경로를 실행 대상으로 돌려주게
    #   된다 — 검사한 바이트와 실행되는 바이트가 갈리는 그 형태다(적대 리뷰 P1-A).
    #   `mkstemp` 가 잡아 둔 이름을 그대로 쓰고, 확장자만 실행 가능한 형태로 바꾼다.
    final = tmp.with_name(tmp.name[:-len(".part")] + ".zip")
    try:
        os.replace(tmp, final)
    except Exception:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        return None
    # 이전 회차의 잔재를 여기서 정리한다 — 고정 자리를 쓰는 대가를 여기서 갚는다(C3).
    _sweep_old_downloads(out_dir, keep=final)
    return final


def _sweep_old_downloads(out_dir: Path, keep: Path, max_age_sec: float = 3600.0) -> None:
    """이번 회차 파일 말고 **오래된** 잔재만 지운다. 실패는 조용히 넘긴다.

    ⚠ 진행 중인 다른 흐름의 파일을 지우지 않게 **나이**로 자른다 — 이름만 보면 동시 실행
    중인 형제를 지우게 된다.
    """
    now = time.time()
    try:
        for child in out_dir.iterdir():
            if child == keep or not child.is_file():
                continue
            if not (child.name.endswith(".part") or child.name.endswith((".exe", ".zip"))):
                continue
            try:
                if now - child.stat().st_mtime > max_age_sec:
                    child.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass


def matches(size: int, digest: str, magic: bytes, update: Update) -> bool:
    """받은 것이 **매니페스트가 말한 그것**인가. 네 축 전부를 본다. **판정의 단일 정본.**

    ⚠ 크기만 보거나 지문만 보지 않는다. 지문이 유일한 방어선이면 매니페스트를 바꿀 수 있는
    상대가 지문도 함께 바꾼다 — 그 시나리오에서 남는 것은 **고정된 출처**(규율 1·2)이고,
    나머지 축은 그 출처가 온전할 때 «전송 중 손상·잘린 응답» 을 잡는다.
    """
    if size != update.size:
        return False
    if not (MIN_SETUP_BYTES <= size <= MAX_SETUP_BYTES):
        return False
    if magic[:2] != b"PK":
        return False                      # Windows 실행 파일이 아니다(HTML 오류 본문 등)
    return core.fingerprints_match(digest, update.sha256)


def verify(payload: bytes, update: Update) -> bool:
    """바이트열 판정 — `matches()` 에 위임한다(같은 술어, 다른 입구)."""
    return matches(len(payload), hashlib.sha256(payload).hexdigest(),
                   payload[:2], update)


# ── 적용 ─────────────────────────────────────────────────────────────────────────

def confirm_text(update: Update, connected: bool, home: Path | None = None) -> str:
    """Explain the installation source and when the new version takes effect."""
    lines = [f"{update.label} 로 업데이트합니다.",
             f"현재 버전: {version.CLIENT_VERSION}"]
    if update.notes:
        lines.append("")
        lines.append(update.notes)
    if home is not None:
        pinned = core.pinned_server(home) or ""
        bundled = core.bundled_service_base() or ""
        if pinned and bundled and pinned.rstrip("/") != bundled.rstrip("/"):
            lines.append("")
            lines.append("⚠ 연결된 서버와 업데이트 서버가 다릅니다.")
            lines.append(f"  연결 서버:  {pinned}")
            lines.append(f"  업데이트 서버:  {bundled}")
            lines.append("직접 요청한 것이 아니라면 [아니요] 를 누르세요.")
    lines.append("")
    lines.append("별도 설치 프로그램 없이 DQA 안에서 업데이트를 준비합니다.")
    lines.append("현재 앱과 AI 연결은 유지됩니다.")
    lines.append("새 버전은 DQA를 종료한 뒤 다시 실행할 때 적용됩니다.")
    lines.append("알림 영역 아이콘이 있는 동안 창 닫기는 숨기기입니다. 적용하려면 [종료]를 선택하세요.")
    return "\n".join(lines)


def verify_file(path: Path, update: Update) -> bool:
    """**디스크의 그 파일**이 매니페스트가 말한 그것인가.

    ⚠ 이것이 §16.7 G14(「처방은 결과 대조로 끝난다」)를 취득 경로에 적용한 자리다.
    `download()` 가 판정하는 것은 «내가 읽은 스트림» 이고, `apply()` 가 실행하는 것은
    «디스크의 경로» 다 — 그 둘이 같다는 보장은 어디에도 없었다(적대 리뷰 P1-A: 두 스레드로
    재현). 흐름별 유일 이름이 지금 관측된 재현 경로를 막지만, 계열을 닫는 것은 **실행할
    바로 그 바이트를 다시 세는** 이 함수다 — 백신 격리·복원, 같은 자리에 쓰는 다른 프로세스,
    아직 상상하지 못한 경로가 전부 여기 걸린다.
    """
    h = hashlib.sha256()
    total = 0
    head = b""
    try:
        with Path(path).open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                if not head:
                    head = chunk[:2]
                total += len(chunk)
                if total > MAX_SETUP_BYTES:
                    return False
                h.update(chunk)
    except OSError:
        return False
    return matches(total, h.hexdigest(), head, update)


#: 한 프로세스에서 업데이트 흐름은 **하나만** 돈다.
#:
#: ⚠ 입구가 셋이다 — 트레이 [업데이트 확인](클릭마다 새 스레드) · 웹 패널 `update_apply`
#: (요청마다 새 스레드) · 주기 감시의 자동 적용. 게이트가 없으면 트레이를 두 번 누르면
#: 확인창 둘 · 다운로드 둘 · **미서명 설치기 둘이 같은 설치 디렉토리에 무음으로** 돈다.
#: 반쯤 설치된 앱이 남으면 앱 자체가 사라지므로 사용자가 업데이트 채널로 돌아올 입구가 없다.
#: 이 저장소는 같은 위험을 러너에 대해 이미 P1 로 판정했다(`ClientApp._connect_gate`) —
#: 여기는 러너가 아니라 설치기라 대가가 더 크다.
_FLOW_LOCK = threading.Lock()


def run_flow(home: Path, *, target: Update, confirm=None, say=None,
             is_connected=None, require_idle: bool = False, on_started=None) -> dict:
    """Install into a separate slot; success requires exit 0 and an activated payload."""
    say = say or (lambda _l: None)
    if not running_frozen():
        return {"ok": False, "error": "not_frozen",
                "detail": "개발 트리에서는 업데이트를 적용하지 않습니다."}
    if not _FLOW_LOCK.acquire(blocking=False):
        detail = "업데이트가 이미 진행 중입니다."
        say(detail)
        return {"ok": False, "error": "already_running", "detail": detail}
    try:
        connected = bool(is_connected()) if is_connected else False
        if confirm is not None and not confirm(confirm_text(target, connected, home=home)):
            return {"ok": False, "error": "declined"}

        say(f"업데이트를 받는 중… ({target.version})")
        path = download(home, target)
        if path is None:
            detail = ("업데이트 파일을 받지 못했거나 무결성 대조에 실패했습니다 — "
                      "지금 버전으로 계속합니다.")
            say(detail)
            log(home, f"download FAILED → {target.version}")
            return {"ok": False, "error": "download_failed", "detail": detail}

        # ⚠ **실행할 바로 그 파일을 다시 센다** (§3-b · G14). 스트림 판정만으로는 실행 대상이
        #   검증되지 않는다 — 그 둘이 갈리는 것이 P1-A 였다.
        if not verify_file(path, target):
            detail = "받은 파일이 실행 직전 검사에서 어긋났습니다 — 적용하지 않습니다."
            say(detail)
            log(home, f"pre-apply verify FAILED → {target.version}")
            path.unlink(missing_ok=True)
            return {"ok": False, "error": "verify_failed", "detail": detail}

        # Even a stale UI target must not reinstall a version already prepared.
        active = installation.active_version()
        if active and not version.is_newer(target.version, active):
            return {"ok": True, "restarting": False, "prepared": True,
                    "version": active, "detail": prepared_text(active)}

        # 띄우기 **전에** 시도를 남긴다 — 이 표식이 없으면 설치 실패를 판정할 근거가 사라진다.
        mark_pending_install(home, target.version)
        _write_state(home, install_status="installing", install_error="")
        say("새 버전을 준비하는 중입니다. 현재 작업을 계속할 수 있습니다.")
        try:
            applied_version = update_package.apply_package(path, target.version)
        except Exception as exc:  # The old slot remains active on every failure.
            log(home, f"package apply failed: {type(exc).__name__}")
            detail = "업데이트를 완료하지 못했습니다 — 지금 버전과 연결을 유지합니다."
            say(detail)
            log(home, f"install FAILED → {target.version}")
            _write_state(home, install_status="failed", install_error=detail)
            clear_pending_install(home)
            return {"ok": False, "error": "install_failed", "detail": detail}

        if installation.active_version() != applied_version:
            detail = "업데이트 결과를 확인하지 못했습니다. 현재 버전과 연결을 유지합니다."
            clear_pending_install(home)
            _write_state(home, install_status="failed", install_error=detail)
            log(home, f"activation FAILED → {target.version}")
            return {"ok": False, "error": "activation_failed", "detail": detail}
        clear_pending_install(home)
        _write_state(home, install_status="prepared", install_error="")
        detail = prepared_text(applied_version)
        say(detail)
        log(home, f"prepared → {target.version}; running → {version.CLIENT_VERSION}")
        return {"ok": True, "restarting": False, "prepared": True,
                "version": applied_version, "detail": detail}
    finally:
        _FLOW_LOCK.release()


def running_frozen() -> bool:
    """지금 도는 것이 **동결된 배포본**인가.

    ⚠ 소스 트리에서는 업데이트를 시도하지 않는다. 개발 중인 트리에 설치기를 덮어씌우는 것은
    의미가 없고(그 설치본은 다른 폴더에 산다), 개발자가 방금 고친 코드를 배포본이 조용히
    가려 버린다 — 러너 `selfupdate.running_bundle_path` 가 지문으로 막는 것과 같은 축이다.
    """
    return bool(getattr(sys, "frozen", False))


def prepared_text(target: str) -> str:
    return (f"{target} 업데이트 준비가 완료되었습니다. 현재 작업은 계속할 수 있습니다. "
            "알림 영역의 DQA 아이콘을 오른쪽 클릭해 [종료]한 뒤 다시 실행하면 적용됩니다.")


def installation_status(home: Path) -> dict:
    state = _state(home)
    prepared = installation.prepared_version()
    phase = state.get("install_status", "")
    if phase == "prepared" and not prepared:
        phase = ""
    return {"state": phase,
            "prepared_version": prepared,
            "error": state.get("install_error", "")}
