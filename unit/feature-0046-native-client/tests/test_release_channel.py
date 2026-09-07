"""릴리스 채널 — 서버가 무엇을 광고하고 무엇을 감추는가 (feature-0046, 2026-09-07).

## 이 스위트가 지키는 것

1. **없는 것을 광고하지 않는다.** 매니페스트가 말하는 파일이 없거나 크기·지문이 어긋나면
   404 다. 가이드와 실제가 어긋나면 사용자는 안내받은 대로 갔다가 막히고 스스로 우회하지
   못한다(P0-I 가 닫은 결함 클래스).
2. **퍼블리시 실수를 서버가 잡는다.** 파일만 바꾸고 매니페스트를 안 고친 상태를 그대로
   내보내면, 그것은 사용자에게 「업데이트가 안 된다」로만 보인다 — 지문은 **실물에서** 계산한다.
3. **반입 → 서빙이 한 바퀴 돈다.** 퍼블리시 스크립트가 올린 것을 서버 모듈이 그대로 통과시키는지
   **같은 테스트 안에서** 확인한다(§16.7 G14 — 처방은 결과 대조로 끝난다).
4. **롤백이 있다.** 새 버전에 문제가 생겼을 때 옛 설치기를 다시 올리지 않고 되돌린다.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_WEB_SRC = (Path(__file__).resolve().parents[2]
            / "feature-0003-agent-web-ui" / "src")
_OAUTH_AS = _WEB_SRC / "routers" / "oauth_as.py"
_APP_PY = _WEB_SRC / "app.py"
_COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def release():
    if str(_WEB_SRC) not in sys.path:
        sys.path.insert(0, str(_WEB_SRC))
    return _load("client_release_rc", _WEB_SRC / "routers" / "client_release.py")


@pytest.fixture()
def publish():
    if str(_WEB_SRC) not in sys.path:
        sys.path.insert(0, str(_WEB_SRC))
    return _load("publish_release_rc", _SRC / "scripts" / "publish_release.py")


def _fake_setup(path: Path, version: str = "9.9.9", filler: bytes = b"\0") -> Path:
    """PE 처럼 보이는 최소 크기 더미. 실행되지 않는다 — 검사만 통과한다."""
    path.mkdir(parents=True, exist_ok=True)
    out = path / f"DQAConnect-Setup-{version}.exe"
    out.write_bytes(b"MZ" + filler * (1_000_000 - 2))
    return out


# ── 1. 반입 → 서빙 한 바퀴 ──────────────────────────────────────────────────────

def test_publish_then_the_server_advertises_it(tmp_path, publish, release):
    setup = _fake_setup(tmp_path / "build")
    rel_dir = tmp_path / "release"
    doc = publish.publish(setup, rel_dir)
    got = release.current_release(rel_dir)
    assert got is not None
    assert got["version"] == "9.9.9" == doc["version"]
    assert got["sha256"] == hashlib.sha256(setup.read_bytes()).hexdigest()
    assert got["path"] == "/client/DQAConnect-Setup-9.9.9.exe"


def test_empty_directory_advertises_nothing(tmp_path, release):
    assert release.current_release(tmp_path) is None


def test_manifest_without_the_file_advertises_nothing(tmp_path, release):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "version": "9.9.9", "filename": "DQAConnect-Setup-9.9.9.exe",
        "sha256": "0" * 64, "size": 1_000_000}), encoding="utf-8")
    assert release.current_release(tmp_path) is None


# ── 2. 퍼블리시 실수를 서버가 잡는다 ────────────────────────────────────────────

def test_a_changed_file_with_a_stale_manifest_is_not_advertised(tmp_path, publish, release):
    """파일만 바꾸고 매니페스트를 안 고친 상태 — 사용자에겐 「업데이트가 안 된다」로만 보인다."""
    rel_dir = tmp_path / "release"
    setup = _fake_setup(tmp_path / "build")
    publish.publish(setup, rel_dir)
    assert release.current_release(rel_dir) is not None
    # 같은 이름으로 **다른 내용**을 덮는다(매니페스트는 그대로).
    (rel_dir / setup.name).write_bytes(b"MZ" + b"\1" * (1_000_000 - 2))
    assert release.current_release(rel_dir) is None


def test_a_size_mismatch_is_not_advertised(tmp_path, publish, release):
    rel_dir = tmp_path / "release"
    setup = _fake_setup(tmp_path / "build")
    publish.publish(setup, rel_dir)
    doc = json.loads((rel_dir / "manifest.json").read_text(encoding="utf-8"))
    doc["size"] = doc["size"] + 1
    (rel_dir / "manifest.json").write_text(json.dumps(doc), encoding="utf-8")
    assert release.current_release(rel_dir) is None


def test_a_filename_that_disagrees_with_the_version_is_not_advertised(tmp_path, publish, release):
    rel_dir = tmp_path / "release"
    setup = _fake_setup(tmp_path / "build")
    publish.publish(setup, rel_dir)
    doc = json.loads((rel_dir / "manifest.json").read_text(encoding="utf-8"))
    doc["version"] = "9.9.8"
    (rel_dir / "manifest.json").write_text(json.dumps(doc), encoding="utf-8")
    assert release.current_release(rel_dir) is None


def test_a_traversal_filename_never_escapes_the_release_directory(tmp_path, release):
    rel_dir = tmp_path / "release"
    rel_dir.mkdir()
    (rel_dir / "manifest.json").write_text(json.dumps({
        "version": "9.9.9", "filename": "../DQAConnect-Setup-9.9.9.exe",
        "sha256": "0" * 64, "size": 1_000_000}), encoding="utf-8")
    (tmp_path / "DQAConnect-Setup-9.9.9.exe").write_bytes(b"MZ" + b"\0" * 999_998)
    assert release.current_release(rel_dir) is None


# ── 3. 롤백·정리 ────────────────────────────────────────────────────────────────

def test_activate_rolls_back_to_an_older_build(tmp_path, publish, release):
    rel_dir = tmp_path / "release"
    build = tmp_path / "build"
    publish.publish(_fake_setup(build, "1.0.0"), rel_dir)
    publish.publish(_fake_setup(build, "1.1.0"), rel_dir)
    assert release.current_release(rel_dir)["version"] == "1.1.0"
    publish.activate("1.0.0", rel_dir)
    assert release.current_release(rel_dir)["version"] == "1.0.0"


def test_prune_never_removes_what_is_being_served(tmp_path, publish, release):
    rel_dir = tmp_path / "release"
    build = tmp_path / "build"
    for v in ("1.0.0", "1.1.0", "1.2.0"):
        publish.publish(_fake_setup(build, v), rel_dir)
    publish.activate("1.0.0", rel_dir)      # 가장 오래된 것을 배포 중으로 되돌린다
    publish.prune(rel_dir, keep=1)
    assert (rel_dir / "DQAConnect-Setup-1.0.0.exe").is_file()
    assert release.current_release(rel_dir)["version"] == "1.0.0"


def test_publish_rejects_a_truncated_build(tmp_path, publish):
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    tiny = build / "DQAConnect-Setup-9.9.9.exe"
    tiny.write_bytes(b"MZ")
    with pytest.raises(SystemExit):
        publish.publish(tiny, tmp_path / "release")


# ── 4. 배선 (없으면 이 채널은 존재만 하고 아무도 못 쓴다) ───────────────────────

def test_the_download_button_prefers_the_release_channel():
    """`_client_download_url` 이 릴리스 채널을 보지 않으면 버튼은 계속 숨어 있다."""
    src = _OAUTH_AS.read_text(encoding="utf-8", errors="replace")
    assert "from routers import client_release" in src
    assert "client_release.download_url(origin)" in src


def test_only_the_advertised_file_is_downloadable(tmp_path, publish, release):
    """**내린 버전은 받아지지 않는다** — 「내렸다」와 「받을 수 없다」가 갈리지 않게.

    ⚠ 종전에는 릴리스 디렉토리를 `StaticFiles` 로 통째로 마운트해, `activate()` 로 되돌린
    뒤에도 옛 설치기가 `/client/<그 이름>` 에서 익명 다운로드됐다(적대 리뷰 C1).
    지금은 서빙 판정이 「이름이 규약에 맞는가」가 아니라 「**지금 광고 중인 그것인가**」다.
    """
    rel_dir = tmp_path / "release"
    build = tmp_path / "build"
    publish.publish(_fake_setup(build, "1.0.0"), rel_dir)
    publish.publish(_fake_setup(build, "1.1.0"), rel_dir)
    release.RELEASE_DIR = rel_dir

    served = release.current_release(rel_dir)
    assert served["filename"] == "DQAConnect-Setup-1.1.0.exe"
    # 광고 중인 것 → 실물 응답
    ok = release.client_download("DQAConnect-Setup-1.1.0.exe")
    assert getattr(ok, "status_code", 200) == 200
    # 디렉토리에 **실재하지만** 광고 중이 아닌 것 → 404
    assert (rel_dir / "DQAConnect-Setup-1.0.0.exe").is_file()
    gone = release.client_download("DQAConnect-Setup-1.0.0.exe")
    assert gone.status_code == 404


def test_an_unrelated_file_in_the_release_dir_is_not_public(tmp_path, publish, release):
    """마운트 원본이 호스트 디렉토리라, 운영자가 둔 무관한 파일이 공개되면 안 된다(C1)."""
    rel_dir = tmp_path / "release"
    publish.publish(_fake_setup(tmp_path / "build", "1.1.0"), rel_dir)
    (rel_dir / "notes-internal.txt").write_text("사내 메모", encoding="utf-8")
    release.RELEASE_DIR = rel_dir
    assert release.client_download("notes-internal.txt").status_code == 404
    assert release.client_download("manifest.json").status_code == 404


def test_the_download_route_reads_the_directory_at_request_time():
    """기동 시점 `is_dir()` 판정이 아니어야 한다 — 나중에 생긴 디렉토리도 서빙된다(§3-5).

    `app.py` 에 마운트가 남아 있으면 그 판정이 되살아나므로, **없음**을 단언한다.
    """
    src = _APP_PY.read_text(encoding="utf-8", errors="replace")
    assert "StaticFiles(directory=_client_release" not in src
    assert 'app.mount(\n    "/client"' not in src
    route = (_WEB_SRC / "routers" / "client_release.py").read_text(encoding="utf-8")
    assert 'DOWNLOAD_PREFIX + "{filename}"' in route


def test_the_release_directory_is_mounted_into_web():
    """호스트에 놓아도 컨테이너가 못 보면 아무 일도 일어나지 않는다."""
    compose = _COMPOSE.read_text(encoding="utf-8", errors="replace")
    assert "../artifacts/client-release:/srv/client:ro" in compose


def test_the_server_default_matches_the_mount_point():
    """마운트 지점과 기본 경로가 갈리면 배포는 성공하고 다운로드만 조용히 없다."""
    src = (_WEB_SRC / "routers" / "client_release.py").read_text(encoding="utf-8")
    assert '"/srv/client"' in src
