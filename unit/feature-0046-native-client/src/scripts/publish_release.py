"""Windows 에서 빌드한 설치기를 **서버가 서빙하는 릴리스 디렉토리**에 올린다.

## 왜 이 스크립트가 있는가 (ROADMAP §10.2 의 해소)

배포는 Linux 컨테이너에서 이뤄지는데 PyInstaller 는 **실행 대상 OS 에서만** 그 OS 용
실행파일을 만든다. 즉 서버 빌드로는 `.exe` 가 나오지 않고, 그래서 종전
`_client_download_url` 이 보던 `static/agent/DQAConnect.exe` 는 라이브에서 **영원히 없었다**.

이 스크립트는 그 사이를 잇는 **유일한 반입 경로**다:

    (Windows) build_client.py  →  DQAConnect-Setup-<ver>.exe
    (서버 호스트) publish_release.py  →  artifacts/client-release/{설치기, manifest.json}
    (컨테이너) /srv/client  →  GET /api/ai/client/latest · GET /client/<파일>

CI 가 생기면 이 스크립트를 그대로 호출하면 된다 — 반입 경로가 바뀌는 것이 아니라 **호출자만**
사람에서 CI 로 바뀐다.

## 이 스크립트가 지키는 것

- **원자적으로 바꾼다.** 매니페스트를 먼저 쓰고 파일을 나중에 놓으면, 그 사이에 조회한
  클라이언트는 「있다는데 없다」를 본다. 파일 → fsync → `os.replace` → 그다음 매니페스트다.
- **버전을 파일명·매니페스트 두 곳에 같은 값으로 적는다.** 서버와 클라이언트가 **둘 다**
  그 일치를 검사하므로, 어긋난 릴리스는 애초에 광고되지 않는다.
- **덮어쓰기를 막지 않되 같은 버전의 다른 파일은 경고한다.** 같은 버전 번호로 내용이 바뀌면
  이미 받은 머신은 영원히 낡은 채로 남는다(클라이언트는 «더 새것일 때만» 받는다).
- **옛 릴리스를 지우지 않는다.** 받는 중인 머신이 있을 수 있고, 되돌리기(`--activate`)의
  대상이기도 하다. 정리는 `--prune` 로 **명시할 때만** 한다.

사용:
    python3 publish_release.py --setup <경로/DQAConnect-Setup-1.1.0.exe>
                               [--dir <릴리스 디렉토리>] [--notes "…"]
                               [--activate <버전>] [--prune <남길 개수>] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

#: 클라이언트 `updater.SETUP_NAME_RE` · 서버 `client_release.SETUP_NAME_RE` 와 **같은 모양**.
#: 셋이 갈리면 한 곳이 통과시킨 이름을 다른 곳이 거절해 그 릴리스는 아무도 못 받는다.
SETUP_NAME_RE = re.compile(r"^DQAConnect-Setup-(?P<ver>[0-9]+(\.[0-9]+){0,3})\.exe$")

MANIFEST_NAME = "manifest.json"

def _default_dir() -> "Path | None":
    """기본 릴리스 디렉토리 — 못 찾으면 **추측하지 않고** `None`. 그러면 `--dir` 을 요구한다.

    ⚠ 종전에는 `parents[5]` 로 셌다(적대 리뷰 2026-09-09 H1). 그 셈은 `repo/` 안에서만
      맞는다. **연결된 worktree** 에서 부르면 `<루트>/.worktrees/artifacts/client-release`
      를 가리키는데, 이 저장소에서는 그 경로가 마침 `../artifacts` 로 가는 심볼릭 링크라
      **라이브 채널로 곧장 이어졌다** — 즉 아무 실험용 worktree 에서 `--setup` 한 번이면
      서명되지 않은 그 바이너리가 **전 사용자에게** 나간다. 확인창도, dry-run 기본값도 없다.
      반대로 그 링크가 없어지면 조용히 `mkdir` 해 **미끼 디렉토리**를 만들고, 바로 뒤의
      `check()` 는 그 미끼를 보고 초록을 찍는다.

    그래서 두 가지를 한다:
      1. 앵커는 `docker-compose.yml` 이 있는 체크아웃 루트다(`parents[N]` 세기를 버린다).
      2. 그 루트가 **연결된 worktree** 면 `None` — 어디로 내는지는 사람이 말해야 한다.
         (git 은 연결된 worktree 의 루트에 `.git` 을 **파일**로 둔다. 주 worktree 는 디렉토리다.)
    """
    for parent in Path(__file__).resolve().parents:
        if not (parent / "docker-compose.yml").is_file():
            continue
        if (parent / ".git").is_file():
            return None
        return parent.parent / "artifacts" / "client-release"
    return None

MIN_SETUP_BYTES = 1_000_000


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _server_view():
    """서버가 릴리스 디렉토리를 보는 **그 모듈**. 판정을 두 벌로 두지 않는다.

    ⚠ 이 스크립트는 웹 컨테이너 밖(호스트)에서 도므로 `sys.path` 를 직접 세워야 한다.
    `check` 와 `prune` 이 둘 다 쓰므로 한 곳에 둔다 — 한쪽에만 있으면 다른 쪽은
    `ModuleNotFoundError` 로 죽는다.
    """
    web_src = (Path(__file__).resolve().parents[3]
               / "feature-0003-agent-web-ui" / "src")
    if str(web_src) not in sys.path:
        sys.path.insert(0, str(web_src))
    from routers import client_release  # noqa: PLC0415

    return client_release


def _write_manifest(release_dir: Path, doc: dict) -> Path:
    """매니페스트를 **원자적으로** 갈아 끼운다.

    같은 디렉토리 임시 파일 → `os.replace`. `/tmp` 를 거치면 파일시스템이 갈릴 수 있고,
    그때는 복사 중 죽으면 반쪽 매니페스트가 남는다(러너 `install_agent_file` 과 같은 근거).
    """
    target = release_dir / MANIFEST_NAME
    fd, tmp = tempfile.mkstemp(prefix=".manifest.", suffix=".json", dir=str(release_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def _place(setup: Path, release_dir: Path) -> Path:
    """설치기를 릴리스 디렉토리에 **먼저** 놓는다(매니페스트보다 앞이다)."""
    target = release_dir / setup.name
    fd, tmp = tempfile.mkstemp(prefix=".setup.", suffix=".part", dir=str(release_dir))
    try:
        with os.fdopen(fd, "wb") as dst, setup.open("rb") as src:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            # ⚠ **쓰기 fd 에 fsync 한다.** 읽기 fd 로는 방금 쓴 바이트가 디스크에 닿았음을
            #   보장하지 못한다 — `os.replace` 는 이름만 원자적이고 내용까지 보장하지 않는다.
            os.fsync(dst.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def publish(setup: Path, release_dir: Path, notes: str = "") -> dict:
    """설치기 1개를 배포 중인 것으로 만든다. 돌려주는 값이 곧 매니페스트다."""
    m = SETUP_NAME_RE.match(setup.name)
    if not m:
        raise SystemExit(f"파일명이 규약과 다릅니다: {setup.name}\n"
                         "  기대: DQAConnect-Setup-<버전>.exe (버전은 숫자와 점만)")
    if not setup.is_file():
        raise SystemExit(f"설치기가 없습니다: {setup}")
    size = setup.stat().st_size
    if size < MIN_SETUP_BYTES:
        raise SystemExit(f"설치기가 너무 작습니다({size:,} bytes) — 빌드가 반쪽일 수 있습니다.")

    release_dir.mkdir(parents=True, exist_ok=True)
    version = m.group("ver")
    digest = _sha256(setup)

    # ⚠ 같은 버전으로 **내용이 다른** 파일을 올리는 것은 사실상 되돌릴 수 없는 실수다 —
    #   이미 받은 머신은 「더 새것일 때만」 받으므로 영원히 낡은 채로 남는다.
    existing = release_dir / setup.name
    if existing.is_file() and _sha256(existing) != digest:
        print(f"⚠ 같은 버전({version})으로 **다른 내용**을 덮어씁니다. 이미 이 버전을 받은 "
              "머신은 새 내용을 받지 못합니다 — 버전을 올리는 것이 옳습니다.", file=sys.stderr)

    placed = _place(setup, release_dir)
    doc = {
        "version": version,
        "filename": placed.name,
        "sha256": digest,
        "size": size,
        "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "notes": str(notes or "").strip()[:400],
    }
    _write_manifest(release_dir, doc)
    return doc


def activate(version: str, release_dir: Path, notes: str = "") -> dict:
    """이미 올라와 있는 버전을 **배포 중인 것으로 되돌린다**(롤백).

    새 버전에 문제가 생겼을 때 옛 설치기를 다시 올릴 필요 없이 매니페스트만 되돌린다.
    ⚠ 이미 새 버전을 설치한 머신은 **자동으로 내려가지 않는다** — 클라이언트는 더 새것일
    때만 받기 때문이다. 그 머신들은 다음 상위 버전에서 합류한다.
    """
    # ⚠ `publish()` 가 거는 검사를 **여기에도** 건다 (적대 리뷰 2026-09-09 M1). 되돌리기는
    #   급할 때 쓰는 길인데, 종전에는 이름 규약도 크기 하한도 보지 않고 인자를 그대로
    #   파일명에 끼워 넣었다. `--activate 1.1.0-hotfix` 같은 값은 매니페스트에 적히지만
    #   서버 `_VERSION_RE` 가 거절해 **채널 전체가 404** 가 되고, 클라이언트는 404 를
    #   「아직 배포된 것이 없음」이라는 **정상 상태**로 읽어 아무도 오류를 남기지 않는다.
    name = f"DQAConnect-Setup-{version}.exe"
    if not SETUP_NAME_RE.match(name):
        raise SystemExit(f"버전 표기가 규약과 다릅니다: {version}\n"
                         "  기대: 숫자와 점만 (예: 1.2.4). 서버가 거절하면 채널이 통째로 닫힙니다.")
    target = release_dir / name
    if not target.is_file():
        raise SystemExit(f"그 버전이 릴리스 디렉토리에 없습니다: {target}")
    size = target.stat().st_size
    if size < MIN_SETUP_BYTES:
        raise SystemExit(f"그 설치기가 너무 작습니다({size:,} bytes) — 반쪽 파일로 되돌리지 않습니다.")
    doc = {
        "version": version,
        "filename": name,
        "sha256": _sha256(target),
        "size": size,
        "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "notes": str(notes or "").strip()[:400],
    }
    _write_manifest(release_dir, doc)
    return doc


def check(release_dir: Path) -> int:
    """서버가 이 디렉토리를 어떻게 볼지 **그대로** 재현한다. 정상이면 0.

    ⚠ 판정 로직을 여기서 다시 구현하지 않는다 — 서버 모듈을 그대로 부른다. 두 벌이면
    「퍼블리시는 통과했는데 서버는 404」가 생기고, 그 차이는 라이브에서만 보인다.
    """
    rel = _server_view().current_release(release_dir)
    if not rel:
        print(f"FAIL — 서버는 이 디렉토리에서 배포할 것을 찾지 못합니다: {release_dir}",
              file=sys.stderr)
        print("  매니페스트 부재 · 파일 부재 · 크기/지문 불일치 · 이름 규약 위반 중 하나입니다.",
              file=sys.stderr)
        return 1
    print(f"OK — 배포 중: {rel['version']} ({rel['filename']}, {rel['size']:,} bytes)")
    print(f"     sha256: {rel['sha256']}")
    print(f"     경로  : {rel['path']}")
    return 0


def prune(release_dir: Path, keep: int) -> list[str]:
    """옛 설치기를 정리한다. **배포 중인 것은 무조건 남긴다.**"""
    active = (_server_view().current_release(release_dir) or {}).get("filename", "")
    files = sorted((p for p in release_dir.glob("DQAConnect-Setup-*.exe")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for p in files[max(1, keep):]:
        if p.name == active:
            continue
        p.unlink(missing_ok=True)
        removed.append(p.name)
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", help="올릴 설치기 경로 (DQAConnect-Setup-<버전>.exe)")
    ap.add_argument("--dir", default=None,
                    help="릴리스 디렉토리 (연결된 worktree 에서는 **필수**)")
    ap.add_argument("--notes", default="", help="사용자에게 보일 한 줄 설명(≤400자)")
    ap.add_argument("--activate", help="이미 올라온 버전으로 되돌린다(롤백)")
    ap.add_argument("--prune", type=int, help="최근 N개만 남기고 옛 설치기 삭제")
    ap.add_argument("--check", action="store_true",
                    help="서버가 이 디렉토리를 어떻게 볼지 확인만 한다")
    args = ap.parse_args(argv)

    chosen = args.dir or _default_dir()
    if chosen is None:
        ap.error("릴리스 디렉토리를 알 수 없습니다 — `--dir <경로>` 로 명시하세요.\n"
                 "  연결된 worktree 에서는 기본값을 쓰지 않습니다: 여기서의 추측 한 번이\n"
                 "  서명되지 않은 설치기를 전 사용자에게 내보낼 수 있습니다(적대 리뷰 H1).")
    release_dir = Path(chosen).resolve()
    if args.check and not (args.setup or args.activate or args.prune):
        return check(release_dir)

    if args.setup:
        doc = publish(Path(args.setup).resolve(), release_dir, args.notes)
        print(f"배포 중: {doc['version']} ({doc['filename']}, {doc['size']:,} bytes)")
        print(f"sha256 : {doc['sha256']}")
    elif args.activate:
        doc = activate(args.activate, release_dir, args.notes)
        print(f"되돌림 : {doc['version']} ({doc['filename']})")
    elif args.prune is None:
        ap.error("--setup / --activate / --prune / --check 중 하나가 필요합니다.")

    if args.prune is not None:
        removed = prune(release_dir, args.prune)
        print(f"정리: {len(removed)}개 삭제" + (f" — {', '.join(removed)}" if removed else ""))

    # 올린 뒤에는 **서버 시선으로 한 번 더 본다**. 「올렸다」와 「서빙된다」는 다른 축이고,
    # 그 차이는 라이브에서만 보이는 종류다(§16.7 G14 — 처방은 결과 대조로 끝난다).
    return check(release_dir)


if __name__ == "__main__":
    raise SystemExit(main())
