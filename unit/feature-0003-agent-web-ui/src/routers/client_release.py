"""client-release 도메인 APIRouter (네이티브 클라이언트 배포본의 **매니페스트 단일 표면**).

URL: `/api/ai/client/latest` (익명 · 인스턴스 데이터 0). RBAC 스코프: 없음 — 설치기는 비밀이
아니고 연결 화면의 「연결 프로그램 받기」와 같은 등급이다(`/static/agent/bridge_setup.sh` 선례).
INCLUDE_ORDER=260 — admin_perf(250) 다음 슬롯(순서 변경 금지).

소유 feature: feature-0046-native-client(클라이언트 업데이트 채널). 실물 파일은
`unit/feature-0046-native-client/src/scripts/publish_release.py` 가 릴리스 디렉토리에 놓고,
그 디렉토리는 호스트에서 컨테이너로 **읽기 전용 bind-mount** 된다(`docker-compose.yml` 의
`x-web-extra` — `/srv/trust` 와 같은 형태).
관련 문서: `unit/feature-0046-native-client/docs/FUNCTION.md` §P0-AH ·
`docs/improvements/onboarding-accessibility/ROADMAP.md` §10.2.

## 왜 이미지 안이 아니라 마운트인가 (ROADMAP §10.2 의 해소)

배포는 Linux 컨테이너에서 이뤄지는데 PyInstaller 는 **실행 대상 OS 에서만** 그 OS 용
실행파일을 만든다. 즉 서버 빌드로는 `.exe` 가 나오지 않는다. 그래서 종전
`_client_download_url` 이 보던 `static/agent/DQAConnect.exe` 는 **라이브에서 영원히 없었고**,
「연결 프로그램 받기」는 계속 숨어 있었다.

바이너리를 저장소에 커밋하면 그 문제는 풀리지만 더 나쁜 것을 얻는다 — git 이력이 릴리스마다
수십 MB 씩 부풀고, 이미지 재빌드 없이는 새 버전을 내보낼 수 없다. 마운트는 둘 다 피한다.

## 이 모듈이 지키는 것

- **없는 것을 광고하지 않는다.** 매니페스트가 말하는 파일이 실제로 없거나 크기·지문이
  어긋나면 **404** 다. 가이드와 실제가 어긋나면 사용자는 안내받은 대로 갔다가 막히고,
  그것을 스스로 우회하지 못한다(P0-I 가 닫은 결함 클래스).
- **지문은 서버가 실물에서 계산한다.** 매니페스트의 값을 그대로 옮기지 않는다 — 그러면
  퍼블리시 실수(파일만 바꾸고 매니페스트를 안 고침)가 그대로 클라이언트의 무결성 실패로
  나타나고, 사용자는 「업데이트가 안 된다」만 본다. 여기서 갈리면 **여기서 막는다.**
- **절대 URL 을 싣지 않는다.** 클라이언트는 자기가 고정한 서버(TOFU)에만 붙으므로 상대
  경로면 충분하고, 절대 URL 은 「응답을 바꿀 수 있는 쪽이 실행 파일의 출처를 지목한다」는
  경로를 여는 모양이다(러너 `selfupdate.py` 규율 2 · 클라이언트 `updater.py` 규율 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

INCLUDE_ORDER = 260  # admin_perf(250) 뒤 — 신규 배포 표면 대역 (순서 변경 금지)

router = APIRouter()

#: 릴리스 디렉토리. compose 가 호스트의 `artifacts/client-release` 를 여기에 ro 로 붙인다.
#: env 로 여는 이유는 테스트·개발 실행에서 임의 디렉토리를 가리키기 위해서다.
RELEASE_DIR = Path(os.getenv("CLIENT_RELEASE_DIR", "/srv/client"))

#: 퍼블리시 스크립트가 적는 파일. **이 디렉토리의 유일한 정본**이다.
MANIFEST_NAME = "manifest.json"

#: 받아들이는 설치기 파일명. 클라이언트 `updater.SETUP_NAME_RE` 와 **같은 모양**이어야 한다 —
#: 서버가 통과시킨 이름을 클라이언트가 거절하면 그 릴리스는 아무도 받지 못한다.
SETUP_NAME_RE = re.compile(r"^DQAConnect-Setup-[0-9]+(\.[0-9]+){0,3}\.exe$")

#: 웹에서 실물을 받는 경로 접두. `app.py` 의 `/client` 마운트와 **같은 값**이다.
DOWNLOAD_PREFIX = "/client/"

_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,3}$")
_HEX256_RE = re.compile(r"^[0-9a-f]{64}$")

#: sha256 캐시. 키는 `(경로, st_mtime_ns, st_size)` — 파일이 바뀌면 키가 바뀌므로 stale 이
#: 남지 않는다. 릴리스 파일은 수십~수백 MB 라 매 요청 재계산은 그대로 CPU 낭비다.
_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}
_DIGEST_LOCK = threading.Lock()


def _digest_of(path: Path) -> str:
    """실물의 sha256. 읽지 못하면 빈 문자열."""
    try:
        stat = path.stat()
    except OSError:
        return ""
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _DIGEST_LOCK:
        hit = _DIGEST_CACHE.get(key)
    if hit:
        return hit
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return ""
    value = h.hexdigest()
    with _DIGEST_LOCK:
        # 캐시가 무한히 자라지 않게 — 릴리스는 몇 개 안 되지만 mtime 이 흔들리면 키가 는다.
        if len(_DIGEST_CACHE) > 32:
            _DIGEST_CACHE.clear()
        _DIGEST_CACHE[key] = value
    return value


def current_release(release_dir: Path | None = None) -> dict | None:
    """배포 중인 클라이언트. **실물과 대조해 통과한 것만** 돌려준다. 없으면 `None`.

    돌려주는 dict 는 그대로 응답 본문이 된다 — 매니페스트 원문이 아니라 **여기서 재구성한
    값**이다(모르는 필드를 그대로 흘려 보내지 않는다).
    """
    base = Path(release_dir) if release_dir is not None else RELEASE_DIR
    try:
        raw = (base / MANIFEST_NAME).read_text(encoding="utf-8")
        doc = json.loads(raw)
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 배포 중인 것이 없다
        return None
    if not isinstance(doc, dict):
        return None

    version = str(doc.get("version") or "").strip()
    filename = str(doc.get("filename") or "").strip()
    if not _VERSION_RE.match(version) or not SETUP_NAME_RE.match(filename):
        return None
    # 파일명이 버전을 말하고 매니페스트도 버전을 말한다. 어긋나면 어느 쪽을 믿을지 고르는
    # 문제가 되므로 **거절한다** — 클라이언트도 같은 검사를 한다(둘 다 통과해야 설치된다).
    if filename != f"DQAConnect-Setup-{version}.exe":
        return None

    target = base / filename
    # 이름은 위 정규식이 이미 좁혔지만, 그것이 유일한 방어선이 되지 않게 **해석된 경로가
    # 릴리스 디렉토리 안인지** 한 번 더 본다(심볼릭 링크·상대 경로 우회 차단).
    try:
        if target.resolve().parent != base.resolve():
            return None
        stat = target.stat()
    except OSError:
        return None
    if not target.is_file() or stat.st_size <= 0:
        return None

    declared_size = doc.get("size")
    try:
        declared_size = int(declared_size)
    except (TypeError, ValueError):
        declared_size = -1
    if declared_size != stat.st_size:
        return None                       # 매니페스트와 실물이 갈렸다 — 광고하지 않는다

    digest = _digest_of(target)
    declared = str(doc.get("sha256") or "").strip().lower().replace(":", "")
    if not _HEX256_RE.match(digest) or digest != declared:
        return None                       # 퍼블리시 실수를 **여기서** 막는다

    return {
        "version": version,
        "filename": filename,
        "sha256": digest,
        "size": stat.st_size,
        "published_at": str(doc.get("published_at") or "").strip(),
        "notes": str(doc.get("notes") or "").strip()[:400],
        # ⚠ **상대 경로다.** 절대 URL 을 실으면 이 응답을 바꿀 수 있는 쪽이 클라이언트가
        #   실행할 파일의 출처를 지목하게 된다(`updater.py` 규율 1).
        "path": DOWNLOAD_PREFIX + filename,
    }


def download_url(origin: str, release_dir: Path | None = None) -> str | None:
    """설치기를 **실제로 받을 수 있을 때만** 절대 URL. 없으면 `None`.

    `oauth_as._client_download_url` 이 이것을 쓴다 — 판정을 두 곳에 두면 화면은 「받기」를
    보이는데 클라이언트는 「없다」고 하는 상태가 생긴다.
    """
    rel = current_release(release_dir)
    if not rel:
        return None
    return f"{str(origin or '').rstrip('/')}{rel['path']}"


@router.get("/api/ai/client/latest")
def client_latest() -> JSONResponse:
    """배포 중인 클라이언트 매니페스트. 없으면 **404**.

    ⚠ 200 + `{"available": false}` 로 답하지 않는다. 클라이언트는 「받을 것이 있다」만 알면
    되고, 없는 상태를 성공 응답으로 표현하면 그 응답을 파싱하는 쪽마다 «없음» 의 모양을 다시
    정의하게 된다 — 이 저장소가 tri-state 표시에서 이미 겪은 형태다.
    """
    rel = current_release()
    if not rel:
        return JSONResponse({"error": "no_release"}, status_code=404)
    return JSONResponse(rel, headers={"Cache-Control": "no-store"})


# ⚠ **경로를 리터럴로 적는다.** `bin/gen-routemap.py` 는 데코레이터 인자의
# `ast.Constant` 만 읽으므로 `DOWNLOAD_PREFIX + "{filename}"` 같은 표현식은 ROUTEMAP 에
# `?` 로 떨어진다 — 하필 그 인덱스(`ai_read_priority: 4`, auth 열이 권한 게이트를
# 선고지하는 SSOT)가 이름을 적을 수 없는 라우트가 **익명으로 실행 파일을 서빙하는
# 표면**이 된다(적대 리뷰 C-1). `DOWNLOAD_PREFIX` 와의 일치는 테스트가 잠근다.
@router.get("/client/{filename}")
def client_download(filename: str):
    """설치기 실물. **배포 중인 그 파일만** 준다. 그 외는 404.

    ## 왜 StaticFiles 마운트가 아닌가 (적대 리뷰 C1 · §3-5)

    처음에는 `app.py` 가 릴리스 디렉토리를 `StaticFiles` 로 통째로 마운트했다. 두 가지가
    잘못이었다:

    1. **내린 버전이 계속 받아진다.** `activate()` 로 어떤 버전을 되돌리면(예: 보안 사유로
       내림) 그 설치기는 여전히 `/client/DQAConnect-Setup-<그 버전>.exe` 에서 익명으로
       내려받을 수 있었다 — 「내렸다」와 「받을 수 없다」가 갈린다. 지금은 **광고 중인 파일
       하나만** 서빙하므로 철회가 곧 도달 불가다.
    2. **디렉토리 안 전체가 공개된다.** 마운트 원본이 이미지 밖 호스트 디렉토리라, 운영자가
       거기에 무관한 파일을 두는 순간 그것도 인터넷에 공개됐다. 경로 이탈은 starlette 가
       막지만 문제는 이탈이 아니라 **디렉토리 안** 이었다.
    3. 부수 효과로 **기동 시점 `is_dir()` 판정이 사라졌다.** 종전에는 릴리스 디렉토리가 web
       기동 뒤에 생기면 그 replica 가 영구히 404 였고 그 사실을 알리는 신호가 없었다.
       이 라우트는 **요청 시점에** 디렉토리를 읽으므로 재시작이 필요 없다.

    ⚠ Range 요청은 지원하지 않는다(`FileResponse` 는 전체를 준다). 클라이언트 업데이터는
    한 번에 전량을 받으므로 무관하고, 브라우저 다운로드는 이어받기만 잃는다.
    """
    from fastapi.responses import FileResponse

    rel = current_release()
    if not rel or filename != rel["filename"]:
        # ⚠ 「이름이 규약에 맞는가」가 아니라 「**지금 광고 중인 그것인가**」로 판정한다.
        #   전자만 보면 위 1번(내린 버전 계속 도달)이 그대로 남는다.
        return JSONResponse({"error": "not_found"}, status_code=404)
    return FileResponse(RELEASE_DIR / filename,
                        media_type="application/octet-stream",
                        filename=filename,
                        headers={"Cache-Control": "no-store"})
