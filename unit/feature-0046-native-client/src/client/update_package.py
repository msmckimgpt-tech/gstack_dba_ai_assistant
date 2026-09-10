"""Prepare an immutable app slot without running an installer."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile

from . import core, installation, version

MAX_EXPANDED_BYTES = 1536 * 1024 * 1024
MAX_FILES = 20000
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(?:\..*)?", re.I)


def plain_directory(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISDIR(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & 0x400)


@contextmanager
def update_lock(root: Path):
    """Share the existing Inno Setup exclusion, including across Windows sessions."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateMutexW(None, False, "Global\\DQAConnectSetup")
        error = ctypes.get_last_error()
        if not handle:
            raise OSError(error, "update lock unavailable")
        try:
            if error == 183:
                raise BlockingIOError("another update is running")
            yield
        finally:
            kernel.CloseHandle(handle)
    else:
        import fcntl
        with (root / ".update.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def extract_payload(archive: Path, slot: Path, target: str) -> None:
    """Validate every Windows filename and expansion budget before writing any file."""
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if not entries or len(entries) > MAX_FILES:
            raise ValueError("invalid file count")
        seen: set[str] = set()
        total = 0
        for entry in entries:
            name = entry.filename
            parts = name.rstrip("/").split("/")
            mode = entry.external_attr >> 16
            if (entry.orig_filename != name or "\\" in name
                    or any(not part or part in (".", "..") or part[-1:] in (" ", ".")
                           or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                           or _RESERVED.fullmatch(part) for part in parts)
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or entry.flag_bits & 1):
                raise ValueError("unsafe package path")
            key = "/".join(parts).casefold()
            if key in seen:
                raise ValueError("duplicate package path")
            seen.add(key)
            total += entry.file_size
            if total > MAX_EXPANDED_BYTES:
                raise ValueError("expanded package too large")
        written = 0
        for entry in entries:
            dest = slot.joinpath(*entry.filename.rstrip("/").split("/"))
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with package.open(entry) as src, dest.open("xb") as out:
                while chunk := src.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_EXPANDED_BYTES:
                        raise ValueError("expanded package too large")
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
    if (slot / "install-complete.txt").read_text(encoding="utf-8-sig").strip() != target:
        raise ValueError("package version mismatch")
    for required in ("DQAConnect.exe", "runtime/python.exe"):
        with (slot / required).open("rb") as exe:
            if exe.read(2) != b"MZ":
                raise ValueError("package executable missing")


def verify_slot(slot: Path) -> bool:
    result = subprocess.run([str(slot / "DQAConnect.exe"), "--verify-install"],
                            cwd=str(slot), timeout=60, **core.hidden_child_kwargs())
    return result.returncode == 0


def activate_slot(root: Path, name: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".active-slot-", dir=root)
    pending = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(name)
            out.flush()
            os.fsync(out.fileno())
        for attempt in range(50):
            try:
                os.replace(pending, root / "active-slot.txt")
                return
            except OSError as exc:
                if attempt == 49 or getattr(exc, "winerror", None) not in (5, 32, 33):
                    raise
                time.sleep(.1)
    finally:
        pending.unlink(missing_ok=True)


def apply_package(archive: Path, target: str) -> str:
    """Return the activated version. Failure leaves the old pointer and processes intact."""
    if version.parse(target) is None:
        raise ValueError("invalid version")
    root = installation.install_root()
    versions = root / "versions"
    if not plain_directory(root) or not plain_directory(versions):
        raise ValueError("invalid installation root")
    if not (root / "DQALauncher.exe").is_file() or not installation.active_version(root):
        raise ValueError("slot launcher unavailable")
    with update_lock(root):
        active = installation.active_version(root)
        if not active:
            raise ValueError("invalid active slot")
        if not version.is_newer(target, active):
            return active
        slot = None
        for number in range(1, 10001):
            candidate = versions / f"{target}-{number}"
            try:
                candidate.mkdir()
                slot = candidate
                break
            except FileExistsError:
                continue
        if slot is None:
            raise OSError("no available slot")
        activated = False
        try:
            extract_payload(archive, slot, target)
            if not verify_slot(slot):
                raise ValueError("payload startup verification failed")
            activate_slot(root, slot.name)
            activated = True
            return target
        finally:
            if not activated:
                shutil.rmtree(slot, ignore_errors=True)
