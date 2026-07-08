#!/usr/bin/env python3
# /daily-report 스킬 사전 집계기 (deterministic pre-aggregation).
#
# 매 호출마다 AI 가 손으로 하던 기계적 단계 —
#   날짜 결정 · 커밋 window 수집 · 보고일 경계(19:00) 분류 · TASK 단위 그룹핑 ·
#   시간대(10–13 / 13–16 / 16–19) 배정 · 머지 커밋 마킹 · 별첨(기능 개발 외) 휴리스틱 ·
#   각주(10:00 이전·19:00 이후 이월·전날 야간분) 사전 계산
# — 을 한 번에 처리해, AI 가 §4.1(산출물 요약·내부 용어 일반화)·§4.2(최종 분류)·§6(출력)
# "판단"만 마감하면 되도록 구조화된 digest 를 낸다.
#
# 스크립트는 git 로그를 "가공"만 한다 — 요약을 지어내거나 커밋을 임의로 버리지 않는다.
# 머지/문서-only 커밋도 버리지 않고 마킹만 하며, 별첨 판정은 힌트일 뿐 AI 가 §4.2 로 확정한다.
#
# Usage:
#   python3 bin/daily-report-collect.py [YYYY-MM-DD]        # 기본 오늘, 사람용 digest
#   python3 bin/daily-report-collect.py 2026-06-09
#   python3 bin/daily-report-collect.py --json [YYYY-MM-DD] # 기계용 JSON
#   python3 bin/daily-report-collect.py --repo /path/to/repo 2026-06-09
#
# 보고일 경계 = 19:00. 다루는 하루 = 전날 19:00 ~ 당일 19:00.
#   전날 19:00 이후  → 10–13 의 '전날(19:00 이후)' 하위 섹션
#   당일 00:00~10:00 → 10–13 에 흡수(각주로 시각 명시)
#   당일 19:00 이후  → 익일 이월(본문 제외, 각주 건수만)
#
# Exit: 0 성공(커밋 유무 무관) / 2 git 저장소 아님 / 3 인자 오류
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 시간대 경계 (보고일 경계 = 19:00) ─────────────────────────────────────────
BUCKETS = [
    ("b1013", "10:00 ~ 13:00", 10, 13),
    ("b1316", "13:00 ~ 16:00", 13, 16),
    ("b1619", "16:00 ~ 19:00", 16, 19),
]
REPORT_BOUNDARY_HOUR = 19  # 하루 경계
DAY_START_HOUR = 10        # 이 시각 이전 당일 커밋은 10–13 에 흡수

# ── TASK 키 추출 — 실데이터의 여러 형식을 모두 흡수 ─────────────────────────────
#   TASK-20260707T013532-reasoning-effort  (date+time+slug)
#   TASK-20260707-kb-candidate-adoption    (date+slug, T-시각 없음)  ← slug 로 서로 구분!
#   TASK-0243                              (짧은 serial)
#   TASK §53 / TASK §55.7                  (feature-0016 계열 섹션형)
# 주의: date(8자리)+slug 패턴을 짧은 serial 패턴보다 "먼저" 둔다.
#       그러지 않으면 TASK-20260707-A 와 TASK-20260707-B 가 date 부만 잡혀 한 그룹으로 오병합된다.
TASK_PATTERNS = [
    re.compile(r"TASK-\d{8}(?:T\d{6})?(?:-[A-Za-z0-9][A-Za-z0-9-]*)?"),
    re.compile(r"TASK-\d{3,}"),
    re.compile(r"TASK\s*§\s*\d+(?:\.\d+)?"),
]

# 단일-parent squash/manual 머지의 backstop. 진짜 머지커밋(parent>1)은 parent 수로 이미 잡힘.
# `Merge .*into ` 같은 광역 패턴은 "Merge X into Y" 류 실제 feature subject 를 오탐하므로 배제.
MERGE_SUBJECT_RE = re.compile(
    r"^(Merge (pull request|remote-tracking branch|branch)\b|merge origin/)",
    re.IGNORECASE,
)

# ── 별첨(기능 개발 외) 휴리스틱 경로 ───────────────────────────────────────────
# 제품(앱) 소스: 사용자·운영자에게 보이는 변경.
PRODUCT_PATH_RE = re.compile(
    r"(?:^|/)("
    r"unit/feature-[^/]+/src/"          # feature 앱 소스
    r"|alembic/versions/"               # DB 마이그레이션 (앱 스키마)
    r")"
)
PRODUCT_SHARED_RE = re.compile(r"^shared/(?!docs/).+\.(py|js|ts|vue|html|css)$")  # 공유 앱 코드
# 별첨 전용: 제품 파일이 하나도 없을 때만 별첨으로 힌트.
APPENDIX_PATH_RE = re.compile(
    r"(?:^|/)("
    r"bin/|scripts/|\.claude/|\.codex/|\.github/"
    r"|docs/|wiki/|meta/|playbooks/|plugins/|tests/"
    r"|unit/feature-[^/]+/docs/"
    r"|unit/feature-[^/]+/tests/"
    r"|\.template-)"
)


def run_git(repo: Path, args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"[daily-report-collect] git 실패: {e.stderr}\n")
        raise
    return out.stdout


def resolve_repo(cli_repo: str | None) -> Path:
    # --repo 가 명시되면 그것만 사용 — 실패 시 조용히 다른 저장소로 폴백하지 않는다
    # (엉뚱한 repo 를 성공(exit 0)으로 보고하는 것을 방지; 명시 의도 존중).
    if cli_repo:
        try:
            top = run_git(Path(cli_repo), ["rev-parse", "--show-toplevel"]).strip()
        except Exception:
            top = ""
        if not top:
            sys.stderr.write(f"[daily-report-collect] --repo 가 git 저장소가 아닙니다: {cli_repo}\n")
            sys.exit(2)
        return Path(top)
    # 기본: 스크립트 소유 repo(bin/의 부모) > cwd 의 git toplevel
    for c in (Path(__file__).resolve().parent.parent, Path.cwd()):
        try:
            top = run_git(c, ["rev-parse", "--show-toplevel"]).strip()
            if top:
                return Path(top)
        except Exception:
            continue
    sys.stderr.write("[daily-report-collect] git 저장소를 찾을 수 없습니다.\n")
    sys.exit(2)


def classify_files(files: list[str]) -> dict:
    product, appendix = [], []
    for f in files:
        if PRODUCT_PATH_RE.search(f) or PRODUCT_SHARED_RE.match(f):
            product.append(f)
        elif APPENDIX_PATH_RE.search(f):
            appendix.append(f)
        else:
            # 분류 불명(루트 설정·기타) → 제품 아님으로 취급(보수적)
            appendix.append(f)
    return {"product": product, "appendix": appendix}


def top_dirs(files: list[str], limit: int = 6) -> list[str]:
    seen: list[str] = []
    for f in files:
        parts = f.split("/")
        # unit/feature-xxxx 는 2단계까지, 그 외는 1단계
        if parts[0] == "unit" and len(parts) >= 2:
            key = "/".join(parts[:2])
        else:
            key = parts[0]
        if key not in seen:
            seen.append(key)
        if len(seen) >= limit:
            break
    return seen


def feature_scopes(files: list[str]) -> list[str]:
    scopes: list[str] = []
    for f in files:
        m = re.match(r"unit/(feature-[0-9]+-[a-z0-9-]+)/", f)
        if m and m.group(1) not in scopes:
            scopes.append(m.group(1))
    return scopes


def extract_task_key(subject: str) -> str | None:
    for pat in TASK_PATTERNS:
        m = pat.search(subject)
        if m:
            # 정규화: 공백 run 축약 + `§` 주변 공백 통일 → "TASK § 56"/"TASK §56" 을 한 키로.
            key = re.sub(r"\s+", " ", m.group(0)).strip()
            return re.sub(r"\s*§\s*", " §", key)
    return None


def collect_commits(repo: Path, day: datetime) -> list[dict]:
    prev = day - timedelta(days=1)
    nxt = day + timedelta(days=1)
    # tz skew margin 을 두고 넓게 fetch 후 Python 에서 벽시계 기준 정밀 필터.
    since = (prev.replace(hour=REPORT_BOUNDARY_HOUR) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    until = (nxt.replace(hour=0, minute=0) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    # record = \x1f 로 필드 구분, \x1e 로 커밋 구분 (subject·파일명에 안 쓰이는 제어문자).
    # \x1e 는 포맷 "앞"에 둔다 — --name-only 파일 목록이 %s 뒤에 붙으므로,
    # 구분자를 뒤에 두면 파일이 다음 레코드 앞머리로 밀린다.
    fmt = "%x1e" + "%x1f".join(["%H", "%h", "%cd", "%P", "%s"])
    raw = run_git(repo, [
        "log", "--all",
        f"--since={since}", f"--until={until}",
        f"--pretty=format:{fmt}",
        "--date=format:%Y-%m-%d %H:%M:%S",
        "--name-only", "--reverse",
    ])
    commits: list[dict] = []
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        lines = record.split("\n")
        parts = lines[0].split("\x1f")
        if len(parts) < 5:
            continue
        full, short, cdate, parents, subject = parts[:5]
        try:
            dt = datetime.strptime(cdate.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        files = [ln for ln in lines[1:] if ln.strip()]
        is_merge = len(parents.split()) > 1 or bool(MERGE_SUBJECT_RE.match(subject))
        commits.append({
            "full": full, "short": short, "dt": dt, "subject": subject,
            "is_merge": is_merge, "files": files,
        })
    return commits


def display_section(bucket: str) -> str:
    """논리 bucket → 보고서 표시 섹션. before_1000(00:00~10:00) 은 10–13(b1013) 에 흡수(§5)."""
    return "b1013" if bucket == "before_1000" else bucket


def bucket_of(dt: datetime, day: datetime) -> str:
    """커밋 벽시계 시각 → 논리 구간 키.

    tz 가정: --date=format:%Y-%m-%d %H:%M:%S 는 커밋 자체 tz 의 벽시계를 낸다.
    단일 tz 팀(KST) 전제 — 경계(19:00 등)를 그 벽시계로 판정한다. 혼합 tz 커밋은
    자기 tz 벽시계로 배정되어 어긋날 수 있음(현 데이터엔 없음; MINOR 알려진 한계).
    """
    prev = day - timedelta(days=1)
    b_prev19 = prev.replace(hour=REPORT_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    d_00 = day.replace(hour=0, minute=0, second=0, microsecond=0)
    d_10 = day.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    d_19 = day.replace(hour=REPORT_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    nxt_00 = d_00 + timedelta(days=1)
    if b_prev19 <= dt < d_00:
        return "prev_night"
    if d_00 <= dt < d_10:
        return "before_1000"
    if d_10 <= dt < d_19:
        for key, _, lo, hi in BUCKETS:
            if day.replace(hour=lo) <= dt < day.replace(hour=hi):
                return key
    if d_19 <= dt < nxt_00:
        return "carryover"
    return "out_of_window"


def group_commits(commits: list[dict], day: datetime) -> dict:
    """TASK 키(없으면 subject) 로 그룹핑. 각 커밋에 구간 태그를 부여."""
    for c in commits:
        c["bucket"] = bucket_of(c["dt"], day)
    in_window = [c for c in commits if c["bucket"] not in ("out_of_window",)]

    # 당일 19:00 이후(carryover) 는 body 에서 제외 — 익일 보고서로 이월(§5). 각주 카운트만.
    body_commits = [c for c in in_window if c["bucket"] != "carryover"]

    # 순수 머지 커밋(태스크 키 없고 머지) 은 별도 노트로 접는다 — §4.1 흡수 대상이라
    # 개별 그룹으로 나열하면 노이즈. 정보 손실 방지를 위해 PR#·브랜치 tail 만 발췌해 보존.
    # --all 리베이스 트윈으로 같은 PR 머지가 여러 ref 에 중복 → PR#(없으면 subject)로 dedup.
    merge_notes: list[dict] = []
    seen_merge: set[str] = set()
    grouped_commits: list[dict] = []
    for c in body_commits:
        if c["is_merge"] and extract_task_key(c["subject"]) is None:
            pr = re.search(r"#(\d+)", c["subject"])
            tail = re.search(r"(feature-[0-9]+-[a-z0-9-]+|ai/[a-z0-9/-]+)", c["subject"])
            dedup_key = f"#{pr.group(1)}" if pr else c["subject"]
            if dedup_key in seen_merge:
                continue
            seen_merge.add(dedup_key)
            merge_notes.append({
                "time": c["dt"].strftime("%H:%M"),
                "bucket": c["bucket"],
                "pr": pr.group(1) if pr else None,
                "ref": tail.group(1) if tail else None,
                "subject": c["subject"],
            })
        else:
            grouped_commits.append(c)

    groups: dict[str, dict] = {}
    order: list[str] = []
    for c in grouped_commits:
        task = extract_task_key(c["subject"])
        # 그룹 키: TASK 키 우선. 없으면 subject 개별.
        gkey = task if task else f"__notask__::{c['subject']}"
        if gkey not in groups:
            groups[gkey] = {"task": task, "commits": []}
            order.append(gkey)
        groups[gkey]["commits"].append(c)

    # 그룹별 파생 정보 계산
    result_groups: list[dict] = []
    for gkey in order:
        g = groups[gkey]
        cs = sorted(g["commits"], key=lambda x: x["dt"])
        all_files: list[str] = []
        for c in cs:
            all_files.extend(c["files"])
        cls = classify_files(all_files)
        non_merge = [c for c in cs if not c["is_merge"]]
        # 대표 구간 = 첫(비머지 우선) 커밋의 bucket. 비머지 없으면 첫 머지.
        anchor = non_merge[0] if non_merge else cs[0]
        # 표시 구간: before_1000(00:00~10:00) 은 10–13 에 흡수(§5). prev_night 은 자체 하위 섹션.
        display_bucket = display_section(anchor["bucket"])
        buckets_hit = sorted({c["bucket"] for c in cs})
        # 표시 섹션(§5 배치 단위) 기준 걸침 판정 — prev_night/before_1000 도 포함해야
        # "전날 20시 + 당일 11시" 같은 걸침을 놓치지 않는다. carryover 는 body 밖이라 제외.
        sections_hit = sorted({display_section(b) for b in buckets_hit})
        # subject 중복 제거(리베이스 트윈) — 동일 subject 는 최초 시각만
        seen_subj: set[str] = set()
        subjects: list[dict] = []
        for c in cs:
            if c["subject"] in seen_subj:
                continue
            seen_subj.add(c["subject"])
            subjects.append({
                "time": c["dt"].strftime("%H:%M"),
                "date": c["dt"].strftime("%m-%d"),
                "subject": c["subject"],
                "is_merge": c["is_merge"],
            })
        has_product = len(cls["product"]) > 0
        # 별첨 힌트: 제품 파일 0 이면 별첨. 하나라도 있으면 제품.
        if has_product:
            hint = "제품"
        else:
            hint = "별첨"
        result_groups.append({
            "task": g["task"],
            "anchor_bucket": anchor["bucket"],
            "display_bucket": display_bucket,
            "anchor_time": anchor["dt"].strftime("%H:%M"),
            "first_time": cs[0]["dt"].strftime("%H:%M"),
            "last_time": cs[-1]["dt"].strftime("%H:%M"),
            "buckets_hit": buckets_hit,
            "sections_hit": sections_hit,
            "spans_multiple": len(sections_hit) > 1,
            "commit_count": len(subjects),  # subject-dedup 후 고유 커밋 수(리베이스 트윈 제외)
            "merge_count": sum(1 for s in subjects if s["is_merge"]),
            "subjects": subjects,
            "top_dirs": top_dirs(all_files),
            "feature_scopes": feature_scopes(all_files),
            "product_files": len(cls["product"]),
            "appendix_files": len(cls["appendix"]),
            "appendix_hint": hint,
        })
    return {"groups": result_groups, "merge_notes": merge_notes, "in_window": in_window}


def compute_footnotes(in_window: list[dict]) -> dict:
    before = sorted(c["dt"].strftime("%H:%M") for c in in_window if c["bucket"] == "before_1000")
    prev_night = [c for c in in_window if c["bucket"] == "prev_night"]
    carryover = [c for c in in_window if c["bucket"] == "carryover"]
    return {
        "before_1000_times": before,
        "before_1000_count": len(before),
        "prev_night_count": len(prev_night),
        "carryover_count": len(carryover),
    }


# ── digest / json 출력 ─────────────────────────────────────────────────────────
def build_payload(repo: Path, day: datetime) -> dict:
    commits = collect_commits(repo, day)
    grouped = group_commits(commits, day)
    footnotes = compute_footnotes(grouped["in_window"])
    total = len(grouped["in_window"])
    merges = sum(1 for c in grouped["in_window"] if c["is_merge"])
    return {
        "date": day.strftime("%Y-%m-%d"),
        "prev": (day - timedelta(days=1)).strftime("%Y-%m-%d"),
        "next": (day + timedelta(days=1)).strftime("%Y-%m-%d"),
        "boundary_hour": REPORT_BOUNDARY_HOUR,
        "repo": str(repo),
        "window": {
            "from": (day - timedelta(days=1)).strftime("%Y-%m-%d") + " 19:00",
            "to": (day + timedelta(days=1)).strftime("%Y-%m-%d") + " 00:00",
        },
        "totals": {
            "commits_in_window": total,
            "merge_commits": merges,
            "groups": len(grouped["groups"]),
        },
        "footnotes": footnotes,
        "groups": grouped["groups"],
        "merge_notes": grouped["merge_notes"],
    }


def _group_label(g: dict) -> str:
    if g["task"]:
        return g["task"]
    # no-TASK: 대표 비머지 subject 앞머리
    for s in g["subjects"]:
        if not s["is_merge"]:
            return f"(no-TASK) {s['subject'][:60]}"
    return f"(no-TASK/merge) {g['subjects'][0]['subject'][:60]}"


def render_digest(p: dict) -> str:
    L: list[str] = []
    L.append("# /daily-report 사전 집계 (스크립트) — 요약·최종분류는 AI 가 §4.1/§4.2 로 마감")
    L.append("")
    L.append(f"대상일: {p['date']}  |  보고일 경계: {p['prev']} 19:00 ~ {p['date']} 19:00")
    L.append(f"저장소: {p['repo']}")
    L.append(f"커밋 window: {p['window']['from']} ~ {p['window']['to']}")
    t = p["totals"]
    n_merge_notes = len(p.get("merge_notes", []))
    carry = p["footnotes"]["carryover_count"]
    grouped_n = sum(g["commit_count"] for g in p["groups"])  # 고유(트윈 제외) 그룹 대상 커밋
    L.append(
        f"수집: 그룹 {t['groups']}개 (대상 커밋 {grouped_n}) · 순수머지 {n_merge_notes}건 "
        f"· 19시이후 이월 {carry}건  [window 원시 {t['commits_in_window']} 커밋]"
    )
    L.append("")

    fn = p["footnotes"]
    L.append("── 각주 (사전 계산 — 최종 각주에 반영) ──")
    if fn["before_1000_count"]:
        L.append(f"- 당일 10:00 이전 커밋 {fn['before_1000_count']}건 ({', '.join(fn['before_1000_times'])}) → 10–13 구간 흡수(각주로 시각 명시)")
    if fn["prev_night_count"]:
        L.append(f"- 전날(19:00 이후) 커밋 {fn['prev_night_count']}건 → 10–13 '전날(19:00 이후)' 하위 섹션")
    if fn["carryover_count"]:
        L.append(f"- 당일 19:00 이후 커밋 {fn['carryover_count']}건 → 익일 보고서로 이월(본문 제외, 각주 건수만)")
    if not any([fn["before_1000_count"], fn["prev_night_count"], fn["carryover_count"]]):
        L.append("- (경계 특이사항 없음)")
    L.append("")

    if t["commits_in_window"] == 0:
        L.append(f"해당일 `repo` 커밋 없음 ({p['window']['from']} ~ {p['window']['to']}).")
        L.append("다른 저장소/브랜치 확인이 필요한지 사용자에게 한 줄로 안내할 것.")
        return "\n".join(L)

    # 구간별 그룹 나열 (별첨 후보는 시간대에서 빼고 마지막에 모음)
    section_order = [
        ("prev_night", "10:00 ~ 13:00 · 전날(19:00 이후) 하위 섹션"),
        ("b1013", "10:00 ~ 13:00 (당일)"),
        ("b1316", "13:00 ~ 16:00"),
        ("b1619", "16:00 ~ 19:00"),
    ]
    groups = p["groups"]
    appendix_candidates = [g for g in groups if g["appendix_hint"] == "별첨"]
    product_like = [g for g in groups if g["appendix_hint"] != "별첨"]

    section_label = {
        "prev_night": "전날야간", "b1013": "10–13", "b1316": "13–16", "b1619": "16–19",
    }

    def emit_group(g: dict) -> None:
        span = ""
        if g["spans_multiple"]:
            labels = [section_label.get(s, s) for s in g["sections_hit"]]
            span = f" · ⚠구간 걸침({'/'.join(labels)}) → §5 로 분할할 것"
        scopes = f" · scope: {', '.join(g['feature_scopes'])}" if g["feature_scopes"] else ""
        L.append(
            f"[{_group_label(g)}]  {g['first_time']}~{g['last_time']} · {g['commit_count']}커밋"
            f"(머지 {g['merge_count']}) · 힌트:{g['appendix_hint']}"
            f" (제품파일 {g['product_files']}/별첨파일 {g['appendix_files']}){span}{scopes}"
        )
        if g["top_dirs"]:
            L.append(f"    changed: {', '.join(g['top_dirs'])}")
        for s in g["subjects"]:
            mk = " [머지→§4.1 흡수]" if s["is_merge"] else ""
            # per-commit 날짜·시각 노출 — 걸침 그룹에서 AI 가 어느 커밋이 어느 구간인지 판별 가능하게.
            L.append(f"    · {s['date']} {s['time']} {s['subject']}{mk}")

    for key, title in section_order:
        sec = [g for g in product_like if g["display_bucket"] == key]
        if not sec:
            continue
        L.append(f"═══ {title} ═══")
        for g in sec:
            emit_group(g)
        L.append("")

    if appendix_candidates:
        L.append("═══ 별첨 후보 (기능 개발 외 — 휴리스틱, AI 가 §4.2 로 확정) ═══")
        L.append("   ※ 시간대 배정 안 함. 제품 영향 있으면 위 구간으로 되돌릴 것.")
        for g in appendix_candidates:
            emit_group(g)
        L.append("")

    mn = p.get("merge_notes", [])
    if mn:
        refs: list[str] = []
        for m in mn:
            r = f"#{m['pr']}" if m["pr"] else (m["ref"] if m["ref"] else None)
            if r and r not in refs:  # --all 리베이스 트윈 중복 제거
                refs.append(r)
        ref_str = ", ".join(refs) if refs else "(PR 번호 없음)"
        L.append(f"── 순수 머지 커밋 {len(mn)}건 (§4.1 흡수 — 위 그룹들이 이미 반영, 보고서 줄로 쓰지 말 것) ──")
        L.append(f"   {ref_str}")
        L.append("")

    L.append("── AI 마감 체크리스트 ──")
    L.append("1. 각 [그룹]의 커밋 subject 를 §4.1(A) 산출물만 남기고 내부 진행 절차 제거 → (B) 내부 약어 일반화 → 한 줄 요약.")
    L.append("2. 머지·docs-only·캐시버스터 등 [머지→§4.1 흡수] 표시분은 별도 줄로 쓰지 말고 산출물 줄에 흡수.")
    L.append("3. '별첨 후보' 는 §4.2 판정('제품 사용자에게 보이/영향?')으로 확정 — 제품이면 시간대로 되돌리고, 맞으면 최하단 별첨.")
    L.append("4. §6 형식으로 출력. 총계 한 줄 + git 로그 재구성 각주. 19:00 이후 이월분 있으면 각주 명시.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description="/daily-report 사전 집계기")
    ap.add_argument("date", nargs="?", help="대상 날짜 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--repo", help="git 저장소 경로 (기본: 스크립트 소유 repo)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            sys.stderr.write(f"[daily-report-collect] 날짜 형식 오류: {args.date} (YYYY-MM-DD 필요)\n")
            return 3
    else:
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    repo = resolve_repo(args.repo)
    payload = build_payload(repo, day)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_digest(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
