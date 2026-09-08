"""클라이언트가 띄운 러너의 종료·재시도·출력 수명을 한 곳에서 관리한다."""
from __future__ import annotations

import queue
import subprocess
import threading
import time
from collections import deque

RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 16.0)


class RunnerSupervisor:
    """Popen의 작은 수명 인터페이스. poll은 재시도를 포함한 감독의 종료를 뜻한다."""

    def __init__(self, spawn, on_event=None, *, delays=RETRY_DELAYS, stable_sec=60.0):
        self._spawn = spawn
        self._on_event = on_event or (lambda state, message: None)
        self._delays = delays
        self._stable_sec = stable_sec
        self._stop = threading.Event()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._lines = queue.Queue(maxsize=256)
        self.output_tail = deque(maxlen=40)
        self.stdout = self
        self.returncode = None
        self._proc = spawn()
        self._thread = threading.Thread(target=self._run, name="dqa-runner-watch", daemon=True)
        self._thread.start()

    @property
    def running(self):
        with self._lock:
            return not self._stop.is_set() and self._proc is not None and self._proc.poll() is None

    @property
    def pid(self):
        with self._lock:
            return self._proc.pid if self._proc is not None else None

    def poll(self):
        return self.returncode if self._done.is_set() else None

    def wait(self, timeout=None):
        if not self._done.wait(timeout):
            raise subprocess.TimeoutExpired("runner supervisor", timeout)
        return self.returncode

    def terminate(self):
        # 재시도 대기 중에도 취소된다. spawn과 같은 lock을 써 종료 뒤 새 자식이 남지 않는다.
        self._stop.set()
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass

    def readline(self):
        while True:
            try:
                return self._lines.get(timeout=0.1)
            except queue.Empty:
                if self._done.is_set():
                    return ""

    def _event(self, state, message):
        try:
            self._on_event(state, message)
        except Exception:  # 알림 실패로 감독을 잃지 않는다.
            pass

    def _drain(self, proc):
        if proc.stdout is None:
            return
        try:
            for line in iter(lambda: proc.stdout.readline(8192), ""):
                self.output_tail.append(line.rstrip())
                try:
                    self._lines.put_nowait(line)
                except queue.Full:
                    # 브라우저 껍데기는 stdout을 소비하지 않는다. 파이프는 계속 비운다.
                    try:
                        self._lines.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._lines.put_nowait(line)
                    except queue.Full:
                        pass
        except (OSError, ValueError):
            pass
        finally:
            proc.stdout.close()

    def _run(self):
        attempts = 0
        rc = 1
        try:
            while not self._stop.is_set():
                proc = self._proc
                began = time.monotonic()
                reader = threading.Thread(target=self._drain, args=(proc,), daemon=True)
                reader.start()
                while True:
                    try:
                        rc = proc.wait(timeout=0.25)
                        break
                    except subprocess.TimeoutExpired:
                        if self._stop.is_set():
                            try:
                                rc = proc.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                rc = proc.wait()
                            break
                reader.join(timeout=1)
                if self._stop.is_set():
                    break
                if rc == 0:
                    self._event("disconnected", "연결이 끊겼습니다 — 다시 연결해 주세요.")
                    break
                if time.monotonic() - began >= self._stable_sec:
                    attempts = 0
                while not self._stop.is_set():
                    if attempts >= len(self._delays):
                        self._event("disconnected", "연결이 끊겼습니다 — 자동 복구에 실패했습니다. 다시 연결해 주세요.")
                        return
                    delay = self._delays[attempts]
                    attempts += 1
                    self._event("retrying", f"AI 연결을 다시 시도합니다 ({attempts}/{len(self._delays)}).")
                    if self._stop.wait(delay):
                        break
                    try:
                        with self._lock:
                            if self._stop.is_set():
                                break
                            self._proc = self._spawn()
                        self._event("restarted", "AI 연결을 다시 시작했습니다.")
                        break
                    except OSError:
                        rc = 1
                        continue
        except Exception:
            rc = 1
            self._event("disconnected", "연결이 끊겼습니다 — 다시 연결해 주세요.")
        finally:
            try:
                with self._lock:
                    if self._proc is not None and self._proc.poll() is None:
                        self._proc.terminate()
                        try:
                            self._proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            self._proc.kill()
                            self._proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                rc = 1
            finally:
                self.returncode = rc
                self._done.set()
