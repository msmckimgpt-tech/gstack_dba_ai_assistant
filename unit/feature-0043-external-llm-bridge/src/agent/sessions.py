"""대화의 AI 세션 결속. 본문/토큰 없이 ID와 이력 지문만 로컬에 보관한다."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager

from .base import _CONF_DIR, CHILD_TEXT_IO
from .discovery import _resolve_exe
from .logs import log_event
from .selfupdate import agent_install_lock

_SESSION_HELP_CACHE: dict[tuple, bool] = {}
_SESSION_MISSING = "__DQA_SESSION_MISSING__"


def _native_session_id(value) -> str:
    value = str(value or "")
    return value if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) else ""


def _session_supported(kind: str) -> bool:
    if kind not in ("claude", "codex"):
        return False
    try:
        probe = _resolve_exe([kind] + (["exec", "resume"] if kind == "codex" else []) + ["--help"])
    except OSError:
        return False
    key = tuple(probe)
    if key not in _SESSION_HELP_CACHE:
        try:
            result = subprocess.run(probe, capture_output=True, timeout=8, **CHILD_TEXT_IO)
            required = ("--json", "SESSION_ID") if kind == "codex" else ("--resume", "--output-format")
            _SESSION_HELP_CACHE[key] = result.returncode == 0 and all(x in result.stdout for x in required)
        except (OSError, subprocess.SubprocessError):
            _SESSION_HELP_CACHE[key] = False
    return _SESSION_HELP_CACHE[key]


class SessionBinding:
    def __init__(self, path: str, kind: str, history: list[str]):
        # 지문은 수정/삭제 감지 기준점이며 전송 커서가 아니다. 최신 문맥은 항상 다시 보낸다.
        self.path, self.kind, self.history = path, kind, history
        self.result: dict = {"kind": kind}
        try:
            with open(path, encoding="utf-8") as stream:
                previous = json.load(stream)
            count = previous.get("history_count")
            compatible = (type(count) is int and 0 < count <= len(history)
                          and history[count - 1] == previous.get("history_digest"))
            if compatible:
                self.result["resume"] = _native_session_id(previous.get("native_id"))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        # 실행 중 크래시/취소/제출 실패 뒤 오염된 세션으로 돌아가지 않는다.
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def commit(self, receipt: dict | None) -> None:
        native = _native_session_id(self.result.get("native_id"))
        history = receipt.get("history_chain") if isinstance(receipt, dict) else None
        if (not native or not self.result.get("completed") or not isinstance(history, list)
                or len(history) <= len(self.history)
                or history[:len(self.history)] != self.history
                or not all(isinstance(x, str) and re.fullmatch(r"[a-f0-9]{64}", x) for x in history)):
            return
        fd, temporary = tempfile.mkstemp(prefix=".session-", dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"native_id": native, "history_count": len(history),
                           "history_digest": history[-1]}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


@contextmanager
def conversation_session(api, claimed: dict, kind: str, custom):
    scope = claimed.get("conversation_session") or {}
    history = scope.get("history_chain")
    if (custom or claimed.get("kind") == "job" or not scope.get("account_id")
            or not claimed.get("conversation_id") or not isinstance(history, list)
            or not history or not all(isinstance(x, str) and re.fullmatch(r"[a-f0-9]{64}", x) for x in history)
            or not _session_supported(kind)):
        yield None
        return
    try:
        target = _resolve_exe([kind])
    except OSError:
        yield None
        return
    key = hashlib.sha256(json.dumps([
        api.base.rstrip("/"), scope["account_id"], claimed["conversation_id"],
        kind, target, os.environ.get("CODEX_HOME", ""),
        os.environ.get("CLAUDE_CONFIG_DIR", ""), scope.get("context_key"),
    ], sort_keys=True).encode()).hexdigest()
    directory = os.path.join(_CONF_DIR, "conversation-sessions")
    path = os.path.join(directory, key + ".json")
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        lock = agent_install_lock(path, timeout=0)
        lock.__enter__()
    except OSError:
        # 다른 프로세스가 같은 세션을 사용 중이면 서버 문맥으로 독립 실행한다.
        log_event("task.session.unavailable", "세션 저장소를 사용할 수 없어 대화 기록으로 계속합니다.", level="WARN")
        yield None
        return
    try:
        try:
            binding = SessionBinding(path, kind, history)
        except OSError:
            binding = None
            log_event("task.session.unavailable", "세션 상태를 읽지 못해 대화 기록으로 계속합니다.", level="WARN")
        yield binding
    finally:
        lock.__exit__(None, None, None)


def session_command(cmd: list[str], result: dict) -> list[str]:
    kind, native = result["kind"], _native_session_id(result.get("resume"))
    if kind == "claude":
        flags = ["--output-format", "json"] + (["--resume", native] if native else [])
        return [*cmd[:-1], *flags, cmd[-1]]
    if native:
        return [cmd[0], "exec", "resume", *cmd[2:-1], "--json", native, cmd[-1]]
    return [*cmd[:-1], "--json", cmd[-1]]


def decode_session_output(result: dict, out: str, err: str, returncode: int) -> tuple[bool, str]:
    """CLI 메타데이터와 중간 추론/도구 출력을 최종 답변에 섞지 않는다."""
    result.pop("native_id", None)
    result.pop("failure_detail", None)
    result["completed"] = False
    events = []
    if result["kind"] == "claude":
        try:
            value = json.loads(out)
            events = value if isinstance(value, list) else [value]
        except ValueError:
            pass
    else:
        for line in out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    answer, failed = "", False
    for event in events:
        if not isinstance(event, dict):
            continue
        typ = event.get("type")
        if result["kind"] == "claude" and typ == "result":
            result["native_id"] = _native_session_id(event.get("session_id"))
            failed = failed or bool(event.get("is_error")) or event.get("subtype") != "success"
            result["completed"] = not failed
            answer = str(event.get("result") or "")
            if failed:
                result["failure_detail"] = answer or str(event.get("errors") or "")
        elif result["kind"] == "codex":
            if typ == "thread.started":
                result["native_id"] = _native_session_id(event.get("thread_id"))
            elif typ == "item.completed":
                item = event.get("item") or {}
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "agent_message" and item.get("phase") != "commentary":
                    answer = str(item.get("text") or "")
            elif typ == "turn.completed":
                result["completed"] = True
            elif typ in ("turn.failed", "error"):
                failed = True
                error = event.get("error") or event
                if isinstance(error, dict):
                    result["failure_detail"] = str(error.get("message") or "")
    # 셸/모델 오류 문구를 보고 재실행하지 않는다. 시작 전 CLI의 세션 부재만 복구한다.
    missing = re.search(r"(?:No conversation found with session ID|No saved session found with (?:ID|id)|no rollout found for thread id|Session not found):?\s+([0-9a-f-]{36})", err, re.I)
    if (returncode != 0 and result.get("resume") and missing and not events and not out.strip()
            and missing.group(1).lower() == result["resume"].lower()):
        return False, _SESSION_MISSING
    good = returncode == 0 and result["completed"] and not failed and bool(answer.strip())
    if not good:
        if not events and out.strip():
            result["failure_detail"] = out.strip()
        result["completed"] = False
        return False, "연결된 AI가 정상적인 최종 답변을 완료하지 못했습니다."
    return True, answer.strip()
