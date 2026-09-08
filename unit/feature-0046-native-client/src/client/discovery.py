"""클라이언트별 위치/응답 캐시와 중복 요청을 합치는 비동기 탐색."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from . import core

SUCCESS_TTL = 900
FAILURE_TTL = 60
CATALOG_TTL = 900
MAX_WORKERS = 4


_SERVICE_USERS = frozenset({"gh-runner"})


def _user_visible(where, user):
    return where != "wsl" or user not in _SERVICE_USERS


def locations(on_found=None) -> list[core.RuntimeState]:
    found = [core.RuntimeState(name=n, path=p) for n in core.RUNTIMES
             if (p := core.which_runtime(n))]
    if on_found:
        for st in found: on_found(st)
    if not core._is_windows():
        return found
    rc, out = core._run([core._wsl_exe(), "-l", "-q"], timeout=20, encoding="utf-16-le")
    if rc:
        return found
    distros = [s.strip().lstrip("\ufeff") for s in out.replace("\0", "").splitlines()]
    # 이름만 수집한다. 벤더 자격증명 파일은 열지 않는다.
    script = 'for n in claude codex gemini; do p=$(command -v "$n"); [ -z "$p" ] || printf "%s\\t%s\\n" "$n" "$p"; done'

    def scan(distro):
        rows = []
        rc, passwd = core._run([core._wsl_exe(), "-d", distro, "-e", "getent", "passwd"], timeout=20)
        if rc:
            return rows
        users = []
        for line in passwd.splitlines():
            parts = line.split(":")
            if (len(parts) == 7 and parts[2].isdigit()
                    and (parts[2] == "0" or 1000 <= int(parts[2]) < 65534)
                    and not parts[6].endswith(("/nologin", "/false"))
                    and _user_visible("wsl", parts[0])
                    and re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]*\$?", parts[0])):
                users.append(parts[0])
        for user in users:
            rc, output = core._run([core._wsl_exe(), "-d", distro, "-u", user,
                                    "--cd", "~", "-e", "bash", "-lc", script], timeout=45)
            for line in output.splitlines():
                name, sep, path = line.partition("\t")
                if sep and name in core.RUNTIMES and path.startswith("/"):
                    st = core.RuntimeState(name=name, path=path, where="wsl", distro=distro, user=user)
                    rows.append(st)
                    if on_found: on_found(st)
        return rows

    distros = list(dict.fromkeys(d for d in distros if d and not d.startswith("docker-desktop")))
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for rows in pool.map(scan, distros):
            found.extend(rows)
    return found


def state_json(st: core.RuntimeState) -> dict:
    return {"id": st.label, "name": st.name, "where": st.where, "path": st.path,
            "distro": st.distro, "user": st.user, "logged_in": st.logged_in,
            "answers": st.answers, "usable": st.usable, "detail": st.detail,
            "can_login_here": st.can_login_here, "error_code": st.error_code}


class DiscoveryCache:
    def __init__(self, home: Path):
        self.path = home / "ai-locations.json"
        self.lock = threading.RLock()
        self.states: list[core.RuntimeState] = []
        self.checked: dict[str, float] = {}
        self.preferences: dict[str, str] = {}
        self.catalog_at = 0.0
        self.running = False
        self.force_next = False
        self.completed: set[str] = set()
        self.error = ""
        self.thread: threading.Thread | None = None
        self._load()

    def _load(self):
        try:
            if self.path.stat().st_size > 262144:
                return
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            if doc.get("version") != 1:
                return
            states, checked = [], {}
            for row in doc["locations"]:
                name, path, where = row["name"], row["path"], row["where"]
                if name not in core.RUNTIMES or where not in core.WHERES or not isinstance(path, str):
                    raise ValueError("invalid location")
                distro, user = row.get("distro", ""), row.get("user", "")
                if any(not isinstance(s, str) or len(s) > 1024 or any(ord(c) < 32 for c in s)
                       for s in (path, distro, user)):
                    raise ValueError("invalid location")
                if not _user_visible(where, user):
                    continue
                st = core.RuntimeState(name=name, path=path, where=where, distro=distro, user=user,
                                       logged_in=row.get("logged_in") is True,
                                       answers=row.get("answers") is True)
                if row.get("error_code") == "permission_denied":
                    core._mark_permission_denied(st)
                states.append(st)
                checked[st.label] = float(row.get("checked_at", 0))
            preferences = doc.get("preferences", {})
            self.preferences = {n: value for n, value in preferences.items()
                                if n in core.RUNTIMES and isinstance(value, str) and value in checked}
            self.states, self.checked = states, checked
            self.catalog_at = float(doc.get("catalog_at", 0))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.states, self.checked, self.preferences = [], {}, {}

    def _save(self):
        # 독립 파일에는 위치와 검증 시각만 저장한다. detail(계정 이메일/명령 출력)은 제외한다.
        rows = [{k: getattr(s, k) for k in ("name", "path", "where", "distro", "user", "logged_in", "answers", "error_code")}
                | {"checked_at": self.checked.get(s.label, 0)} for s in self.states]
        doc = {"version": 1, "catalog_at": self.catalog_at, "locations": rows,
               "preferences": self.preferences}
        tmp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".ai-locations-", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass  # 저장이 막혀도 현재 연결은 계속 쓸 수 있다.
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    def remember(self, st):
        with self.lock:
            self.preferences[st.name] = st.label
            self._save()

    def invalidate(self, ident):
        with self.lock:
            self.checked.pop(ident, None)
            if self.running: self.force_next = True

    def snapshot(self):
        with self.lock:
            return {"ok": not bool(self.error), "error": self.error,
                    "runtimes": [state_json(s) for s in self.states],
                    "preferences": dict(self.preferences), "discovering": self.running,
                    "completed_platforms": sorted(self.completed), "cached": self.catalog_at > 0}

    def discover(self, *, force=False, background=False):
        with self.lock:
            if not self.running:
                self.running, self.error = True, ""
                self.completed = set()
                self.thread = threading.Thread(target=self._scan, args=(force,), daemon=True)
                self.thread.start()
            elif force:
                self.force_next = True
            thread = self.thread
        if not background and thread:
            thread.join()
        return self.snapshot()

    def _scan(self, force):
        while True:
            self._scan_once(force)
            with self.lock:
                if self.force_next:
                    self.force_next = False
                    self.completed.clear()
                    force = True
                else:
                    self.running = False
                    return

    def _scan_once(self, force):
        try:
            now = time.time()
            with self.lock:
                reuse = not force and 0 <= now - self.catalog_at < CATALOG_TTL
                candidates = list(self.states) if reuse else None
                old = {s.label: s for s in self.states}
                self.states = []
                self.error = ""
                self.completed.clear()
            pending = {n: 0 for n in core.RUNTIMES}
            enumerated = False
            seen = set()

            def probe(st):
                prev = old.get(st.label)
                age = now - self.checked.get(st.label, 0)
                ttl = SUCCESS_TTL if prev and prev.usable else FAILURE_TTL
                current = core.probe_runtime(st.name, where=st.where, path=st.path,
                                             distro=st.distro, user=st.user)
                if (not force and prev and prev.path == st.path and 0 <= age < ttl
                        and current.logged_in is True and not current.error_code):
                    return replace(current, answers=prev.answers, error_code=prev.error_code,
                                   detail=core._PERMISSION_DETAIL if prev.error_code == "permission_denied" else current.detail), True
                if current.logged_in is not False and not current.error_code:
                    core.verify_answers(current)
                return current, False

            def settle(job, candidate):
                try:
                    result, reused = job.result()
                except Exception:
                    result = replace(candidate, answers=False, detail="확인하지 못했습니다. 다시 찾아 주세요.")
                    reused = False
                with self.lock:
                    self.states = [result if st.label == result.label else st for st in self.states]
                    if not reused:
                        self.checked[result.label] = time.time()
                    pending[result.name] -= 1
                    if enumerated and pending[result.name] == 0:
                        self.completed.add(result.name)

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                def add(st):
                    with self.lock:
                        if st.label in seen or not _user_visible(st.where, st.user): return
                        seen.add(st.label)
                        self.states.append(replace(st, answers=None))
                        pending[st.name] += 1
                    pool.submit(probe, st).add_done_callback(lambda job: settle(job, st))

                # 발견한 위치는 즉시 검증한다. 위치 열거가 끝나야 중복 여부를 확정한다.
                for st in candidates if candidates is not None else locations(on_found=add):
                    add(st)
                with self.lock:
                    self.catalog_at = now
                    enumerated = True
                    self.completed = {n for n, count in pending.items() if count == 0}
            with self.lock:
                self._save()
        except Exception:
            with self.lock:
                self.error = "탐색을 완료하지 못했습니다. 다시 찾아 주세요."
