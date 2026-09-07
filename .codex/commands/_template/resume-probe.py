#!/usr/bin/env python3
# `_template:resume` persona 세션 추적기 (deterministic session probe).
#
# 이 스크립트는 `ai-delegated-dev-template-personas` 저장소 소속으로, 소비자 프로젝트의
# `.claude/commands/_template/` submodule 을 통해 배포된다 — project-agnostic:
# 특정 프로젝트 경로·feature id·세션 UUID·OS 계정을 하드코딩하지 않고 항상 `--repo`
# (또는 cwd 의 git toplevel) 로 대상 저장소를 받고, Claude home 루트는 실측 탐지한다.
#
# 매 호출마다 AI 가 inline `python3 -c` heredoc 으로 손수 재발명하던 기계적 단계 —
#   Claude home 루트 탐지 · slug 변종 surface · self/resume-tracker 식별·제외 ·
#   세션 카드 추출(aiTitle/cwd/gitBranch/mtime/중단신호) · 마지막 TodoWrite todos ·
#   마지막 assistant 텍스트 · 직전 user prompt · worktree 매핑 · arg 2-part 분해 ·
#   후보 스코어링(제목 + 중단지점 앵커 + 식별자)
# — 을 한 번에 처리해, AI 가 Phase 4(갭 분석)·Phase 6(재개 실행) "판단"만 하면 되도록
# 구조화된 digest 를 낸다.
#
# 스크립트는 관측된 사실만 낸다 — 제목을 요약하지 않고(round-trip 보존), 후보를 임의로
# 버리지 않으며(제외는 tracker/self 뿐, 사유 명시), 판정이 모호하면 모호하다고 말한다.
#
# 권한: 세션 `.jsonl` 은 보통 `0600 <루트 소유자>` 라 실행자가 다르면 직접 읽기 불가 →
# 자동으로 `sudo -n` 경유로 승격한다. 승격도 실패하면 그 파일을 `read-denied` 로 **명시**
# 표기한다 (조용한 0건과 권한 실패를 절대 섞지 않는다 — 오진의 주 원인).
#
# Usage (소비자 프로젝트 저장소 안에서, 또는 --repo 로 명시):
#   python3 .claude/commands/_template/resume-probe.py --list [-n 12]
#       → no-arg 모드용: 재개 가능한 최근 세션 목록 (제목 verbatim · 중단신호 · worktree)
#   python3 .claude/commands/_template/resume-probe.py --resolve "<사용자 arg 원문>"
#       → arg-given 모드용: arg 2-part 분해 + 후보 스코어링 + 단일 hit 시 중단지점 복원
#   python3 .claude/commands/_template/resume-probe.py --session <UUID|path>
#       → 특정 세션의 카드 전체 (todos · 마지막 assistant 텍스트 · prompt · 중단신호)
#   공통 옵션: --repo <path> · --json · --self <현재 세션 UUID 제외> · --include-trackers(진단용)
#             --list 는 -n/--limit 으로 표시 개수 지정 (해소는 항상 전량 스캔 — recency 컷 없음)
#
# Exit: 0 성공(single / single-probable / ambiguous) / 2 AGENTS.md 부재 → fail-loud
#       4 후보 0건 또는 세션 미발견(fail-loud 신호) / 2 argparse 인자 오류
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# resume persona 주입문 시그니처 — 이 문자열을 담은 세션은 *추적자*이지 추적 *대상*이 아니다.
TRACKER_SIG = "Cross-Session Work Resumption Adapter"

# 중단 원인 마커 (prose 언급이 아닌 실제 시스템 마커만 — 오탐 방지)
STOP_MARKERS = [
    ("limit-중단", "You've hit your session limit"),
    ("context-rollover", "continued from a previous conversation that ran out of context"),
    ("compact", '"isCompactSummary":true'),
]

# 파일 끝에서 역방향으로 훑을 기본 바이트 (마지막 TodoWrite/assistant 텍스트 탐색용).
# 못 찾으면 단계적으로 확장한다 — 28MB 급 세션을 매번 전량 파싱하지 않기 위한 예산.
TAIL_STEPS = [1 << 20, 6 << 20, 24 << 20]


# ── 권한 어댑터 ────────────────────────────────────────────────────────────────
class Priv:
    """직접 읽기 → 실패 시 sudo -n 승격. 승격 불가는 read-denied 로 명시."""

    def __init__(self) -> None:
        self.sudo_ok = self._probe_sudo()
        self.denied: list[str] = []

    @staticmethod
    def _probe_sudo() -> bool:
        try:
            return subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=10).returncode == 0
        except Exception:
            return False

    def _sudo(self, argv: list[str]) -> bytes | None:
        if not self.sudo_ok:
            return None
        try:
            p = subprocess.run(["sudo", "-n", *argv], capture_output=True, timeout=180)
            return p.stdout if p.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def is_file(path: str) -> bool:
        try:
            return Path(path).is_file()
        except (PermissionError, OSError):
            return False

    @staticmethod
    def is_dir(path: str) -> bool:
        """PermissionError 를 삼키지 않되 크래시하지도 않는다 (타 계정 홈 스캔 중 흔함)."""
        try:
            return Path(path).is_dir()
        except (PermissionError, OSError):
            return False

    def listdir(self, path: str) -> list[str]:
        try:
            return sorted(os.listdir(path))
        except PermissionError:
            out = self._sudo(["ls", "-1", path])
            if out is None:
                self.denied.append(path)
                return []
            return sorted(x for x in out.decode("utf-8", "replace").split("\n") if x)
        except OSError:
            return []

    def stat_mtime_size(self, path: str) -> tuple[float, int]:
        try:
            st = os.stat(path)
            return st.st_mtime, st.st_size
        except PermissionError:
            out = self._sudo(["stat", "-c", "%Y %s", path])
            if out:
                a, b = out.decode().split()[:2]
                return float(a), int(b)
            self.denied.append(path)
            return 0.0, 0
        except OSError:
            return 0.0, 0

    def head_bytes(self, path: str, n: int) -> bytes:
        try:
            with open(path, "rb") as fh:
                return fh.read(n)
        except PermissionError:
            out = self._sudo(["head", "-c", str(n), path])
            if out is None:
                self.denied.append(path)
                return b""
            return out
        except OSError:
            return b""

    def tail_bytes(self, path: str, n: int) -> bytes:
        try:
            with open(path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - n))
                return fh.read()
        except PermissionError:
            out = self._sudo(["tail", "-c", str(n), path])
            if out is None:
                self.denied.append(path)
                return b""
            return out
        except OSError:
            return b""

    def grep_has(self, path: str, needle: str) -> bool:
        """고정 문자열 존재 여부 (조기 종료). 권한 실패는 denied 로 기록하고 False."""
        try:
            p = subprocess.run(["grep", "-qsF", "--", needle, path], capture_output=True, timeout=120)
            if p.returncode in (0, 1):
                return p.returncode == 0
        except Exception:
            pass
        out = self._sudo(["grep", "-qsF", "--", needle, path])
        if out is None:
            # returncode!=0 은 "없음" 과 "권한 실패" 둘 다 → 읽기 가능성으로 재확인
            if self.head_bytes(path, 1) == b"":
                self.denied.append(path)
            return False
        return True


PRIV = Priv()


# ── 환경 감지 ──────────────────────────────────────────────────────────────────
def git(args: list[str], cwd: str | None = None) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=60)
        return p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def detect_roots(repo: str | None) -> dict:
    """policy_root(AGENTS.md 소재) · project_root(그 상위) · worktree 인벤토리."""
    start = repo or os.getcwd()
    top = git(["rev-parse", "--show-toplevel"], cwd=start) or start
    policy_root = None
    for cand in (Path(top), Path(top) / "repo", Path(start), Path(start) / "repo"):
        if PRIV.is_file(str(cand / "AGENTS.md")):
            policy_root = str(cand.resolve())
            break
    if policy_root is None:
        return {"error": "AGENTS.md not found", "policy_root": None, "project_root": str(Path(top).resolve())}
    project_root = str(Path(policy_root).parent)

    worktrees = []
    cur: dict = {}
    for line in git(["worktree", "list", "--porcelain"], cwd=policy_root).split("\n"):
        if line.startswith("worktree "):
            if cur:
                worktrees.append(cur)
            cur = {"path": line[9:]}
        elif line.startswith("HEAD "):
            cur["head"] = line[5:][:12]
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line.startswith("detached"):
            cur["branch"] = "(detached)"
    if cur:
        worktrees.append(cur)
    return {
        "policy_root": policy_root,
        "project_root": project_root,
        "branch": git(["branch", "--show-current"], cwd=policy_root) or "(detached)",
        "head": git(["log", "-1", "--format=%h"], cwd=policy_root),
        "worktrees": worktrees,
    }


def claude_homes() -> list[str]:
    """Claude home 루트 실측 탐지 (단일 공식 의존 금지 — 계정마다 별개 루트)."""
    cands = ["/root/.claude", os.path.expanduser("~/.claude")]
    try:
        for d in sorted(os.listdir("/home")):
            cands.append(f"/home/{d}/.claude")
    except OSError:
        pass
    seen, out = set(), []
    for c in cands:
        r = str(Path(c))
        if r in seen:
            continue
        seen.add(r)
        if PRIV.is_dir(str(Path(r, "projects"))) or PRIV.listdir(str(Path(r, "projects"))):
            out.append(r)
    return out


def slug_variants(project_root: str, policy_root: str) -> list[str]:
    """프로젝트 핵심 토큰으로 slug 디렉터리를 실측 surface (언더스코어·점·worktree 변종 포함).

    단일 공식(`cwd` 치환)만 믿으면 repo 진입 세션이 빈 slug 를 가리켜 '세션 없음' 오판.
    """
    def canon(p: str) -> str:
        return p.replace("/", "-").replace("_", "-").replace(".", "-")

    formulas = {canon(project_root), canon(policy_root)}
    token = re.sub(r"[^a-z0-9]+", ".", Path(project_root).name.lower())
    pat = re.compile(token.replace(".", "[-_.]?"), re.I)

    found = []
    for home in claude_homes():
        base = str(Path(home, "projects"))
        for name in PRIV.listdir(base):
            full = str(Path(base, name))
            if not (PRIV.is_dir(full) or PRIV.listdir(full)):
                continue
            if pat.search(name) or name in formulas:
                found.append(full)
    return sorted(set(found))


# ── 세션 카드 추출 ─────────────────────────────────────────────────────────────
def _iter_lines(blob: bytes):
    for raw in blob.split(b"\n"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except Exception:
            continue


def _first_json_str(blob: bytes, key: str) -> str | None:
    m = re.search(rb'"' + re.escape(key.encode()) + rb'"\s*:\s*"((?:[^"\\]|\\.)*)"', blob)
    if not m:
        return None
    try:
        return json.loads(b'"' + m.group(1) + b'"')
    except Exception:
        return m.group(1).decode("utf-8", "replace")


def _blocks(o: dict):
    c = (o.get("message") or {}).get("content")
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict):
                yield b


def session_card(path: str, deep: bool = False) -> dict:
    """세션 1건의 요약 카드. deep=True 면 파일 끝을 확장 스캔해 todos/마지막 텍스트까지."""
    mtime, size = PRIV.stat_mtime_size(path)
    head = PRIV.head_bytes(path, 256 << 10)
    card = {
        "uuid": Path(path).stem,
        "path": path,
        "home": "/root/.claude" if path.startswith("/root/.claude") else str(Path(path).parents[2]),
        "mtime": mtime,
        "size": size,
        "title": None,
        "cwd": None,
        "git_branch": None,
        "stop_signals": [],
        "is_tracker": False,
        "read_denied": False,
        "todos": [],
        "last_assistant_text": None,
        "last_user_prompt": None,
        "first_command": None,
        "worktree_hint": None,
    }
    if not head:
        card["read_denied"] = True
        return card

    card["title"] = _first_json_str(head, "aiTitle")
    card["cwd"] = _first_json_str(head, "cwd")
    card["git_branch"] = _first_json_str(head, "gitBranch")
    m = re.search(rb"<command-name>([^<]{1,120})</command-name>", head)
    if m:
        card["first_command"] = m.group(1).decode("utf-8", "replace")
    card["is_tracker"] = TRACKER_SIG.encode() in head

    # 제목 fallback 체인 (slash-command 진입 세션은 첫 user 텍스트가 persona 주입문)
    if not card["title"]:
        m = re.search(rb"<command-args>(.{1,400}?)</command-args>", head, re.S)
        if m:
            card["title"] = m.group(1).decode("utf-8", "replace").strip()
    if not card["title"]:
        card["title"] = _first_json_str(head, "lastPrompt")

    if deep:
        _fill_tail(card, path, size)
    return card


def _fill_tail(card: dict, path: str, size: int) -> None:
    """파일 끝에서 마지막 TodoWrite todos · 마지막 assistant 텍스트 · 직전 user prompt."""
    for step in TAIL_STEPS:
        blob = PRIV.tail_bytes(path, step)
        if not blob:
            card["read_denied"] = True
            return
        todos, last_text, last_prompt = [], None, None
        wt_hits: dict[str, int] = {}
        for o in _iter_lines(blob):
            for name in re.findall(r"[/\\]\.worktrees[/\\]([A-Za-z0-9._-]+)", json.dumps(o, ensure_ascii=False)):
                wt_hits[name] = wt_hits.get(name, 0) + 1
            t = o.get("type")
            if t == "assistant":
                for b in _blocks(o):
                    if b.get("type") == "tool_use" and b.get("name") == "TodoWrite":
                        todos = (b.get("input") or {}).get("todos") or todos
                    elif b.get("type") == "text":
                        tx = (b.get("text") or "").strip()
                        if len(tx) > 40:
                            last_text = tx
            elif t == "user":
                c = (o.get("message") or {}).get("content")
                if isinstance(c, str):
                    txt = c
                elif isinstance(c, list):
                    if any(b.get("type") == "tool_result" for b in _blocks(o)):
                        continue
                    txt = " ".join(b.get("text", "") for b in _blocks(o) if b.get("type") == "text")
                else:
                    continue
                if txt.strip() and "<task-notification>" not in txt and not txt.startswith("<system-reminder>"):
                    last_prompt = txt.strip()
        card["todos"] = [
            {"status": t.get("status"), "content": t.get("content")} for t in todos if isinstance(t, dict)
        ]
        if wt_hits:
            card["worktree_hint"] = max(wt_hits.items(), key=lambda kv: kv[1])[0]
        card["last_assistant_text"] = last_text
        card["last_user_prompt"] = last_prompt
        sigs = [lb for lb, nd in STOP_MARKERS if nd.encode() in blob]
        if sigs:
            card["stop_signals"] = sigs
        if todos or step >= size:
            return


# ── arg 2-part 분해 (실사용 형태: 제목 + 중단지점 앵커) ────────────────────────
SLASH_CMD = re.compile(r"^/(?:_[a-z]+:|)[a-z0-9_\-]+:?[a-z0-9_\-]*", re.I)


def split_arg(raw: str) -> dict:
    """사용자 arg 를 {title, anchors[], idents[], kind} 로 분해.

    실측 분포(58 세션): title-only 76% · title+snippet 19% · orig-prompt 3% · empty 2%.
    'title+snippet' 은 사용자가 원본 세션의 *마지막 assistant 텍스트* 를 붙여 준 형태로,
    세션 본문에 literal 로 존재하므로 제목보다 강한 앵커다 — 통짜 정규화하면 이 신호를
    제목 토큰에 섞어 버려(겹침 판정 희석) 오식별을 부른다.
    """
    s = (raw or "").strip()
    if not s:
        return {"kind": "empty", "title": "", "anchors": [], "idents": []}

    anchors: list[str] = []

    # 1) 코드펜스 블록 → 앵커
    for m in re.finditer(r"```(?:[a-zA-Z0-9_-]*)\n?(.*?)```", s, re.S):
        a = m.group(1).strip()
        if a:
            anchors.append(a)
    s = re.sub(r"```(?:[a-zA-Z0-9_-]*)\n?.*?```", "\n\n", s, flags=re.S)

    # 2) 선두의 백틱/따옴표로 감싼 세그먼트 = 제목부 (실사용의 표준 형태)
    title = ""
    m = re.match(r'\s*[`"“‘\']\s*(.+?)\s*[`"”’\']\s*(.*)$', s, re.S)
    if m:
        title, rest = m.group(1).strip(), m.group(2).strip()
    else:
        # 빈 줄 2개 또는 개행+따옴표로 제목/앵커 경계 추정
        parts = re.split(r"\n\s*\n", s, maxsplit=1)
        title = parts[0].strip()
        rest = parts[1].strip() if len(parts) > 1 else ""

    # 3) 나머지에서 인용된 스니펫을 앵커로, 나머지는 추가 지시로 보존
    directives = []
    for chunk in re.split(r"\n\s*\n", rest):
        chunk = chunk.strip()
        if not chunk:
            continue
        q = re.match(r'^[`"“‘\']\s*(.+?)\s*[`"”’\']$', chunk, re.S)
        if q:
            anchors.append(q.group(1).strip())
        elif len(chunk) > 24 and not chunk.endswith(("주세요.", "주세요", "해주세요.", "합니다.")):
            anchors.append(chunk)
        else:
            directives.append(chunk)

    # 4) orig-prompt 형태: 제목부가 슬래시 커맨드로 시작 → 제목 매칭 신뢰도 낮음
    kind = "title-only"
    if SLASH_CMD.match(title):
        kind = "orig-prompt"
        stripped = SLASH_CMD.sub("", title, count=1).strip()
        if stripped:
            anchors.insert(0, stripped[:200])
        title = stripped
    elif anchors:
        kind = "title+anchor"

    idents = re.findall(r"feature-\d{3,}[a-z0-9\-]*|ai/[a-z0-9_.\-]+/[a-z0-9_.\-]+", raw or "", re.I)

    norm_anchors = [a for a in (x.strip() for x in anchors) if len(a) >= 12][:4]
    return {
        "kind": kind,
        "title": title,
        "anchors": norm_anchors[:4],
        "idents": sorted(set(idents)),
        "directives": directives,
    }


def anchor_fragments(anchor: str) -> list[str]:
    """앵커 1건 → literal grep 용 짧은 조각들.

    통짜 긴 앵커를 `grep -F` 하면 거의 안 맞는다 — 사용자가 원본 텍스트를 옮길 때
    ① 원문의 **개행이 공백으로 병합**되고(jsonl 에는 `\\n` 리터럴로 저장돼 있다)
    ② 꼬리를 축약하며 ③ 문장부호가 흔들린다. 실측: 143자 통짜는 MISS, 앞 90자는 HIT.
    그래서 **연속 공백을 원문 개행의 흔적으로 보고 문장 경계와 함께 쪼갠 뒤**, 조각
    하나라도 맞으면 hit 으로 센다 (부분 일치의 합으로 동일성을 세운다).
    """
    parts = re.split(r"[\n。.!?…·—]+|\s{2,}", anchor)
    frags = []
    for p in parts:
        p = p.strip().strip("`\"'“”‘’ ")
        if len(p) >= 12:
            frags.append(p[:80])
    frags.sort(key=len, reverse=True)
    return frags[:3] or ([anchor.strip()[:60]] if len(anchor.strip()) >= 12 else [])


def _norm_tokens(s: str) -> list[str]:
    s = re.sub(r"[`\"'“”‘’]", "", s or "")
    s = re.sub(r"[^0-9A-Za-z가-힣]+", " ", s)
    return [t for t in s.lower().split() if t]


def build_idf(titles: list[str]) -> dict:
    """후보 제목 집합에서 토큰 문서빈도 → IDF. 빈출 토큰(프로젝트 상투어)을 감쇠한다."""
    import math
    df: dict[str, int] = {}
    for t in titles:
        for tok in set(_norm_tokens(t or "")):
            df[tok] = df.get(tok, 0) + 1
    n = max(1, len(titles))
    return {tok: math.log(1 + n / c) for tok, c in df.items()}


def title_score(arg_title: str, sess_title: str | None, idf: dict | None = None) -> float:
    if not arg_title or not sess_title:
        return 0.0
    a, b = _norm_tokens(arg_title), _norm_tokens(sess_title)
    if not a or not b:
        return 0.0
    ja, jb = "".join(a), "".join(b)
    if ja == jb or ja in jb or jb in ja:
        return 1.0
    sa, sb = set(a), set(b)
    if idf:
        # 분모는 **arg 토큰** 으로 고정한다 — "사용자가 지목한 (특히 희소한) 토큰을 이 세션이
        # 얼마나 덮는가". min() 으로 잡으면 짧은 무관 제목이 분모가 작아 점수가 부풀어
        # 진짜 후보와 우열이 지워진다 (실측: 0.7 vs 0.525 로 붙어 ambiguous).
        w = lambda toks: sum(idf.get(t, 1.0) for t in toks)          # noqa: E731
        denom = w(sa)
        return round(w(sa & sb) / denom, 3) if denom else 0.0
    return round(len(sa & sb) / max(1, min(len(sa), len(sb))), 3)


# ── 모드 구현 ──────────────────────────────────────────────────────────────────
def collect_sessions(env: dict, n: int, include_trackers: bool, self_uuid: str | None, deep_top: int = 0) -> dict:
    slugs = slug_variants(env["project_root"], env["policy_root"])
    files = []
    for d in slugs:
        for name in PRIV.listdir(d):
            if name.endswith(".jsonl"):
                p = str(Path(d, name))
                mt, sz = PRIV.stat_mtime_size(p)
                files.append((mt, sz, p))
    files.sort(reverse=True)

    cards, trackers, denied = [], [], []
    for mt, sz, p in files:
        c = session_card(p)          # head read 만 — 전량 스캔이 싸다 (grep 전량 없음)
        if c["read_denied"]:
            denied.append(p)
            continue
        if c["uuid"] == self_uuid:
            c["excluded"] = "self"
            trackers.append(c)
            continue
        if c["is_tracker"] and not include_trackers:
            c["excluded"] = "resume-tracker"
            trackers.append(c)
            continue
        cards.append(c)

    for c in cards[:deep_top]:
        _fill_tail(c, c["path"], c["size"])

    wt_by_path = {w["path"]: w for w in env.get("worktrees", [])}
    for c in cards:
        c["worktree"] = None
        cw = c.get("cwd") or ""
        for wp, w in wt_by_path.items():                      # 1차 키: 세션 cwd
            if cw == wp or cw.startswith(wp.rstrip("/") + "/"):
                c["worktree"] = w
                break
        if c["worktree"] is None and (c.get("git_branch") or "").startswith("ai/"):
            for w in env.get("worktrees", []):                # 2차 키: ai/* 브랜치
                if w.get("branch") == c["git_branch"]:
                    c["worktree"] = w
                    break
        if c["worktree"] is None and c.get("worktree_hint"):  # 3차 키: 본문에서 관측된 작업 경로
            for w in env.get("worktrees", []):
                if Path(w["path"]).name == c["worktree_hint"]:
                    c["worktree"] = w
                    break
            else:
                c["worktree"] = {"path": c["worktree_hint"], "branch": "(제거됨/미등록)", "from_hint": True}
    return {"slugs": slugs, "sessions": cards[:n], "excluded": trackers, "read_denied": denied}


def resolve(env: dict, raw_arg: str, self_uuid: str | None, scan: int) -> dict:
    parts = split_arg(raw_arg)
    # **recency 컷을 두지 않는다.** 제목 매칭은 head read 뿐이고 앵커는 본문 literal grep
    # 이라 오래된 세션도 정확히 집어내는데, mtime 상위 N 으로 pool 을 자르면 정답이 범위
    # 밖일 때 0건/오답이 된다 (실측: 최근 25개 컷에서 `none` 4건·오식별 1건이 이 원인).
    pool = collect_sessions(env, max(scan, 10_000), include_trackers=False, self_uuid=self_uuid)
    frag_map = {a: anchor_fragments(a) for a in parts["anchors"]}
    parts["anchor_fragments"] = frag_map
    idf = build_idf([c.get("title") or "" for c in pool["sessions"]])
    cands = []
    for c in pool["sessions"]:
        ts = title_score(parts["title"], c.get("title"), idf)
        # 앵커: 세션 본문에 literal 로 존재하는지 (가장 강한 신호 — 오식별 원리적 차단).
        # 앵커당 조각 하나만 맞아도 그 앵커는 hit (개행 병합·꼬리 축약 내성).
        hits = [a for a, frs in frag_map.items() if any(PRIV.grep_has(c["path"], f) for f in frs)]
        ident_hit = None
        for ident in parts["idents"]:
            if ident.lower() in (c.get("git_branch") or "").lower() or ident.lower() in (c.get("cwd") or "").lower():
                ident_hit = ident
                break
        # 앵커가 **세션 도입부(제목·첫 요청)** 에 있으면 그 세션이 곧 그 요청의 주인이다.
        # 다른 세션이 같은 텍스트를 *본문에 인용* 하면 동점이 되는데, 위치로 갈라야 한다
        # (실측: 인용 세션과 원 요청 세션이 2.0 동점 → 과거 오식별의 실제 구조).
        origin_hit = False
        if hits:
            title_blob = (c.get("title") or "")
            head = PRIV.head_bytes(c["path"], 256 << 10).decode("utf-8", "replace")
            for a in hits:
                for f in frag_map[a]:
                    if f in title_blob or f in head:
                        origin_hit = True
                        break
                if origin_hit:
                    break
        score = ts + 2.0 * len(hits) + (1.5 if origin_hit else 0.0) + (0.5 if ident_hit else 0.0)
        if score <= 0:
            continue
        cands.append({
            "uuid": c["uuid"], "title": c.get("title"), "path": c["path"], "mtime": c["mtime"],
            "home": c["home"], "git_branch": c.get("git_branch"), "cwd": c.get("cwd"),
            "worktree": c.get("worktree"), "stop_signals": c["stop_signals"],
            "title_score": ts, "anchor_hits": hits, "origin_hit": origin_hit,
            "ident_hit": ident_hit, "score": round(score, 3),
        })
    cands.sort(key=lambda x: (-x["score"], -x["mtime"]))

    verdict, chosen = "none", None
    if cands:
        top = cands[0]
        runner = cands[1]["score"] if len(cands) > 1 else 0.0
        # 확정(single): 본문 literal 앵커(도입부) · 제목 동일/포함 · 식별자 직접 매칭 + 우세
        strong = (bool(top["anchor_hits"]) and top.get("origin_hit")) or top["title_score"] >= 0.8 or bool(top["ident_hit"])
        if strong and (len(cands) == 1 or top["score"] >= runner * 1.5):
            verdict, chosen = "single", top
        # 유력(single-probable): 사용자가 제목을 *요약형* 으로 친 흔한 경우 (실사용 76%).
        # IDF 가중 제목이 2위를 2배 이상 앞서면 진행하되 "추정" 으로 표기하고 AI 가
        # worktree/정본 docs 로 교차검증한다. 여기서 AskUserQuestion 을 강제하면 실측상
        # 잘 맞던 title-only 호출에 되레 새 마찰을 만든다 (ambiguous 74% → 질문 폭증).
        elif top["title_score"] >= 0.5 and (len(cands) == 1 or top["score"] >= runner * 2.0):
            verdict, chosen = "single-probable", top
        else:
            verdict = "ambiguous"

    # 후보 컷오프: top 의 60% 미만은 잡음이다. AskUserQuestion 으로 택일 가능한 크기(≤4)로
    # 좁히고, 남은 후보는 **잔여 todos·중단신호까지 채워** 사용자가 한 번에 고를 수 있게 한다
    # (이름만 보여 주면 사용자가 되물어야 하고, 그게 곧 또 한 번의 왕복이다).
    if cands:
        cut = cands[0]["score"] * 0.6
        cands = [c for c in cands if c["score"] >= cut][:4]
        for c in cands:
            card = session_card(c["path"], deep=True)
            c["todos"] = card["todos"]
            c["stop_signals"] = card["stop_signals"]
            c["last_assistant_text"] = card["last_assistant_text"]
            c["last_user_prompt"] = card["last_user_prompt"]
            c["worktree_hint"] = card.get("worktree_hint")
            if c.get("worktree") is None and card.get("worktree_hint"):
                for w in env.get("worktrees", []):
                    if Path(w["path"]).name == card["worktree_hint"]:
                        c["worktree"] = w
                        break
                else:
                    c["worktree"] = {"path": card["worktree_hint"], "branch": "(제거됨/미등록)", "from_hint": True}
    return {"arg_parts": parts, "verdict": verdict, "chosen": chosen,
            "candidates": cands, "read_denied": pool["read_denied"], "slugs": pool["slugs"]}


# ── 출력 ───────────────────────────────────────────────────────────────────────
def ts_fmt(mt: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(mt).strftime("%m-%d %H:%M") if mt else "-"


def wt_label(c: dict) -> str:
    w = c.get("worktree")
    if w:
        tag = "~" if w.get("from_hint") else ""
        return f"{tag}{Path(w['path']).name} / {w.get('branch', '-')}"
    cw = c.get("cwd") or ""
    br = c.get("git_branch") or "-"
    if br in ("HEAD", "main", "master", "(detached)"):
        return f"본체(미-worktree) / {br}"
    return f"{Path(cw).name if cw else '-'} / {br}"


def todo_digest(c: dict) -> str:
    ts = c.get("todos") or []
    if not ts:
        return "-"
    pend = [t for t in ts if t.get("status") != "completed"]
    if not pend:
        return f"todos {len(ts)}건 전부 completed"
    return f"미완 {len(pend)}/{len(ts)}: " + "; ".join((t.get("content") or "")[:48] for t in pend[:3])


def print_list(env: dict, res: dict) -> None:
    print("재개 가능한 최근 세션 (최근순 · 제목은 verbatim):\n")
    print(f"{'#':>2} | {'마지막활동':^12} | {'제목':38} | {'worktree / 브랜치':34} | {'중단신호':16} | 잔여추정")
    print("-" * 160)
    for i, c in enumerate(res["sessions"], 1):
        sig = ",".join(c["stop_signals"]) or "clean-end"
        print(f"{i:>2} | {ts_fmt(c['mtime']):^12} | {(c.get('title') or '-')[:38]:38} | {wt_label(c)[:34]:34} | {sig[:16]:16} | {todo_digest(c)[:60]}")
    print(f"\n(scan: slug {len(res['slugs'])}종 · 제외 {len(res['excluded'])}건(self/resume-tracker)"
          f"{' · read-denied ' + str(len(res['read_denied'])) + '건' if res['read_denied'] else ''})")
    if res["read_denied"]:
        print(f"⚠ read-denied {len(res['read_denied'])}건 — 권한 실패이지 작업 부재가 아님 (sudo 가용: {PRIV.sudo_ok})")
    print('\n→ 이어받을 작업의 제목을 그대로 인자로:  /_template:resume "<위 제목 그대로>"')


def print_resolve(env: dict, res: dict) -> None:
    p = res["arg_parts"]
    print(f"arg 분해: kind={p['kind']} | title={p['title']!r}")
    if p["anchors"]:
        print(f"  중단지점 앵커 {len(p['anchors'])}건: " + " | ".join(repr(a[:70]) for a in p["anchors"]))
    if p["idents"]:
        print(f"  식별자: {p['idents']}")
    if p.get("directives"):
        print(f"  추가 지시(원 의도에 포함 — Resume≠Re-scope 경계 안): {p['directives']}")
    print(f"\n판정: {res['verdict']}")
    for c in res["candidates"]:
        mark = "★" if res["chosen"] and c["uuid"] == res["chosen"]["uuid"] else " "
        print(f" {mark} score={c['score']:<6} title={c['title_score']:<5} anchor={len(c['anchor_hits'])} "
              f"origin={'Y' if c.get('origin_hit') else '-'} ident={c['ident_hit'] or '-'} | "
              f"{ts_fmt(c['mtime'])} | {(c['title'] or '-')[:44]} | {wt_label(c)[:34]}")
    if res["verdict"] in ("single", "single-probable"):
        c = res["chosen"]                      # deep 정보는 컷오프 단계에서 이미 채워짐
        if res["verdict"] == "single-probable":
            print("  (유력 — 제목 요약형 매칭. Phase 7 리마인드에 '추정' 표기 + worktree/정본 docs 로 교차검증)")
        print(f"\n원본 세션 확정: {c['uuid']}  ({c['home']})")
        print(f"  중단신호: {','.join(c['stop_signals']) or 'clean-end'}")
        print(f"  잔여(마지막 TodoWrite): {todo_digest(c)}")
        for t in c.get("todos") or []:
            print(f"    [{t['status']}] {t['content']}")
        if c.get("last_assistant_text"):
            print(f"  마지막 assistant 텍스트: {c['last_assistant_text'][:400]!r}")
        if c.get("last_user_prompt"):
            print(f"  직전 user prompt: {c['last_user_prompt'][:300]!r}")
        w = c.get("worktree")
        if w:
            st = git(["status", "--short"], cwd=w["path"])
            print(f"  worktree: {w['path']} [{w.get('branch')}]  dirty={len(st.splitlines())}건")
            print(f"  log: {git(['log', '--oneline', '-3'], cwd=w['path'])}")
    elif res["verdict"] == "ambiguous":
        print("\n⚠ 후보 다중 — 추정 진행 금지, AskUserQuestion 으로 택일할 것. 각 후보의 잔여:")
        for c in res["candidates"]:
            print(f"  · {(c['title'] or '-')[:50]} [{ts_fmt(c['mtime'])}, "
                  f"{','.join(c['stop_signals']) or 'clean-end'}] → {todo_digest(c)[:90]}")
    else:
        print("\n⚠ 후보 0건.")
        if res["read_denied"]:
            print(f"   read-denied {len(res['read_denied'])}건 존재 → 권한 실패를 먼저 배제할 것 (sudo 가용: {PRIV.sudo_ok})")
        else:
            print("   sudo 가용·tracker 제외 후에도 0건 → fail-loud (재개할 작업 없음).")


def main() -> int:
    ap = argparse.ArgumentParser(description="resume persona 세션 추적기 (deterministic)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="재개 가능한 최근 세션 목록 (no-arg 모드)")
    g.add_argument("--resolve", metavar="ARG", help="사용자 arg 원문으로 대상 해소 (arg-given 모드)")
    g.add_argument("--session", metavar="UUID|PATH", help="특정 세션 카드 전체")
    ap.add_argument("--repo", help="대상 저장소 (기본: cwd 의 git toplevel)")
    ap.add_argument("-n", "--limit", type=int, default=12, help="목록 개수 (기본 12)")
    ap.add_argument("--scan", type=int, default=25, help="해소 시 후보 스캔 개수 (기본 25)")
    ap.add_argument("--self", dest="self_uuid", help="현재 세션 UUID (제외용)")
    ap.add_argument("--include-trackers", action="store_true", help="resume 트래커도 후보에 포함 (진단용)")
    ap.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    a = ap.parse_args()

    env = detect_roots(a.repo)
    if not env.get("policy_root"):
        print("AGENTS.md 를 찾을 수 없습니다 — ai_delegated_dev_template 기반 프로젝트 전용", file=sys.stderr)
        return 2

    if a.list:
        res = collect_sessions(env, a.limit, a.include_trackers, a.self_uuid, deep_top=a.limit)
        out = {"env": env, **res}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str)) if a.json else print_list(env, res)
        return 0

    if a.session:
        path = a.session
        if not PRIV.is_file(path):
            hits = []
            for d in slug_variants(env["project_root"], env["policy_root"]):
                for name in PRIV.listdir(d):
                    if name.startswith(a.session) and name.endswith(".jsonl"):
                        hits.append(str(Path(d, name)))
            if not hits:
                print(f"세션을 찾을 수 없습니다: {a.session}", file=sys.stderr)
                return 4
            path = hits[0]
        card = session_card(path, deep=True)
        if a.json:
            print(json.dumps(card, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"{card['uuid']} ({card['home']}) {ts_fmt(card['mtime'])} size={card['size']:,}")
            print(f"  제목: {card.get('title')!r}\n  cwd: {card.get('cwd')}\n  branch: {card.get('git_branch')}")
            print(f"  중단신호: {','.join(card['stop_signals']) or 'clean-end'} | tracker={card['is_tracker']}")
            print(f"  잔여: {todo_digest(card)}")
            for t in card["todos"]:
                print(f"    [{t['status']}] {t['content']}")
            if card["last_assistant_text"]:
                print(f"  마지막 assistant: {card['last_assistant_text'][:600]!r}")
            if card["last_user_prompt"]:
                print(f"  직전 user prompt: {card['last_user_prompt'][:400]!r}")
        return 0

    res = resolve(env, a.resolve, a.self_uuid, a.scan)
    if a.json:
        print(json.dumps({"env": env, **res}, ensure_ascii=False, indent=2, default=str))
    else:
        print_resolve(env, res)
    return 4 if res["verdict"] == "none" else 0


if __name__ == "__main__":
    sys.exit(main())
