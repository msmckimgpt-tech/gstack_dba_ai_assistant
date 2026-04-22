"""TASK-0034 검증/리포트 생성 스크립트.

- task0034_runs/ 의 api-Q*.json + local-Q*.json 을 읽는다.
- tests/task0034_truth.sql 에서 각 질문에 대한 기준 쿼리를 발췌해,
  docker compose exec mysql 로 실제 실행한 결과와 assistant 답변 표를 비교한다.
- 결과는 tests/TASK-0034-REPORT.md 로 저장.

parsing 규칙 (간단 휴리스틱):
  - assistant 답변에서 `|` 로 둘러싸인 markdown table 첫 매치만 추출
  - (col1, col2, ...) 첫 2 개 컬럼을 key 로 삼아 truth 결과와 set 비교
  - Q 마다 별도 기준 컬럼 정의.

사람이 돌리는 truth 쿼리는 tests/task0034_truth.sql 의 `-- Q{N}` 섹션.
이 스크립트가 자동으로 실행하기는 어려우므로(여러 구문 복합), 각 Q 에 대한
단일 대표 쿼리를 내장하고 `docker compose exec` 로 직접 실행한다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
RUNS_DIR = THIS_DIR / "task0034_runs"
REPORT_PATH = THIS_DIR / "TASK-0034-REPORT.md"
REPO_ROOT = THIS_DIR.parents[2]


TRUTH_QUERIES = {
    "Q1_hero_top_tech": """
        SELECT hero_index, skill_combo, cnt
        FROM (
          SELECT JSON_EXTRACT(j.hero, '$.Index') AS hero_index,
                 REPLACE(REPLACE(REPLACE(JSON_EXTRACT(j.hero, '$.Skill'), ',', '-'), '[', ''), ']', '') AS skill_combo,
                 COUNT(*) AS cnt,
                 ROW_NUMBER() OVER (PARTITION BY JSON_EXTRACT(j.hero, '$.Index') ORDER BY COUNT(*) DESC) rn
          FROM dblog.battlebegin b,
               JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
          WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
          GROUP BY hero_index, skill_combo
        ) t
        WHERE rn <= 5 AND hero_index IN (1,2,3,4,5,15,25)
        ORDER BY hero_index, cnt DESC;
    """,
    "Q1_global_top_tech": """
        SELECT skill_combo, COUNT(*) AS cnt
        FROM (
          SELECT REPLACE(REPLACE(REPLACE(JSON_EXTRACT(j.hero, '$.Skill'), ',', '-'), '[', ''), ']', '') AS skill_combo
          FROM dblog.battlebegin b,
               JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
          WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
        ) e
        GROUP BY skill_combo
        ORDER BY cnt DESC
        LIMIT 20;
    """,
    "Q2_hero_top50": """
        SELECT JSON_EXTRACT(j.hero, '$.Index') AS hero_index,
               COUNT(*) AS appearances,
               ROUND(COUNT(*) * 100.0 / (
                 SELECT COUNT(*) FROM dblog.battlebegin
                 WHERE MyHeroInfo IS NOT NULL AND MyHeroInfo <> ''
               ), 2) AS adoption_pct
        FROM dblog.battlebegin b,
             JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
        WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
        GROUP BY hero_index
        ORDER BY appearances DESC
        LIMIT 50;
    """,
    "Q3_gacha_category_state": """
        SELECT cat, gacha_state, COUNT(*) AS cnt
        FROM (
          SELECT TRIM(jt.cat) AS cat,
                 CASE WHEN r.GachaIndex = 3 THEN 'attempt' ELSE 'expose' END AS gacha_state
          FROM dblog.equipgacharecord r,
               JSON_TABLE(
                 CONCAT('[\"', REPLACE(r.HighGachaCategory, ',', '\",\"'), '\"]'),
                 '$[*]' COLUMNS (cat VARCHAR(20) PATH '$')
               ) jt
          WHERE r.HighGachaCategory REGEXP '^[0-9,]+$'
        ) t
        GROUP BY cat, gacha_state
        ORDER BY cat, gacha_state;
    """,
    "Q4_battletype_join": """
        SELECT bb.BattleType,
               COUNT(*) AS battles,
               ROUND(SUM(be.Win) * 100.0 / COUNT(*), 2) AS win_rate_pct,
               ROUND(AVG(be.PlayTime), 1) AS avg_playtime,
               ROUND(AVG(be.Star), 2) AS avg_star
        FROM dblog.battlebegin bb
        JOIN dblog.battleend be
          ON be.AccountId = bb.AccountId
         AND be.Time >= bb.Time
         AND be.Time <  bb.Time + INTERVAL 5 MINUTE
        WHERE bb.BattleType IS NOT NULL
        GROUP BY bb.BattleType
        ORDER BY battles DESC
        LIMIT 10;
    """,
    "Q5_meta_hero_top20": """
        SELECT hero_index,
               COUNT(*) AS appearances,
               MAX(CAST(lvl AS UNSIGNED)) AS max_level,
               ROUND(AVG(CAST(lvl AS UNSIGNED)), 2) AS avg_level,
               ROUND(AVG(CASE WHEN CAST(star AS UNSIGNED) >= 2 THEN 1 ELSE 0 END), 4) AS star2_ratio,
               ROUND(LOG10(COUNT(*) + 1) * AVG(CAST(lvl AS UNSIGNED)) *
                     (1 + AVG(CASE WHEN CAST(star AS UNSIGNED) >= 2 THEN 1 ELSE 0 END)), 2) AS score
        FROM (
          SELECT JSON_EXTRACT(j.hero, '$.Index') AS hero_index,
                 JSON_EXTRACT(j.hero, '$.Level') AS lvl,
                 JSON_EXTRACT(j.hero, '$.Star')  AS star
          FROM dblog.battlebegin b,
               JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero JSON PATH '$')) j
          WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
        ) s
        GROUP BY hero_index
        ORDER BY score DESC
        LIMIT 20;
    """,
}


def run_mysql(sql: str, db: str = "dblog") -> list[list[str]]:
    """Run an SQL via docker compose exec, returning parsed rows (no header)."""
    cmd = [
        "docker", "compose", "exec", "-T", "mysql",
        "mysql", "-uroot", "-pchange_me", "-N", "-B", db, "-e", sql,
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return [["ERROR", proc.stderr.strip()[:300]]]
    rows: list[list[str]] = []
    for line in proc.stdout.splitlines():
        if line.startswith("mysql:"):
            continue
        cols = line.split("\t")
        rows.append(cols)
    return rows


def extract_markdown_tables(text: str) -> list[list[list[str]]]:
    """Return all markdown tables from a string, each as list of row lists."""
    if not text:
        return []
    tables: list[list[list[str]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("|") and ln.endswith("|"):
            # Check next line is separator |---|---|...
            if i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
                table: list[list[str]] = []
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    raw = lines[i].strip()
                    if re.match(r"^\|[\s\-:|]+\|$", raw):
                        i += 1
                        continue
                    cells = [c.strip() for c in raw.strip("|").split("|")]
                    table.append(cells)
                    i += 1
                if len(table) >= 2:
                    tables.append(table)
                continue
        i += 1
    return tables


def load_run(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def qid_summary(run: dict) -> dict:
    turns = run.get("turns", [])
    if not turns:
        return {"status": "no-run", "last_answer": "", "tables": []}
    # Last turn with answer
    last_ok = None
    for t in reversed(turns):
        if t.get("http_status") == 200 and t.get("answer"):
            last_ok = t
            break
    if last_ok is None:
        return {
            "status": "no-200-turn",
            "last_answer": (turns[-1].get("answer") or "")[:400],
            "tables": [],
        }
    tables = extract_markdown_tables(last_ok.get("answer") or "")
    return {
        "status": "ok" if run.get("final_verdict", "").startswith("stopped") else run.get("final_verdict", ""),
        "last_answer": last_ok.get("answer") or "",
        "tables": tables,
        "turn_idx": last_ok.get("turn_idx"),
        "total_turns": len(turns),
        "total_elapsed_s": run.get("total_elapsed_s"),
        "model": run.get("model"),
        "conv_id": run.get("conversation_id"),
    }


def compare_hero_top50(assistant_answer_table: list[list[str]], truth_rows: list[list[str]]) -> str:
    """Q2: Check top N hero_index set."""
    if not assistant_answer_table or len(assistant_answer_table) < 2:
        return "assistant 응답에 표 없음 — 비교 불가"
    header = [h.lower() for h in assistant_answer_table[0]]
    body = assistant_answer_table[1:]

    def find_col(hints):
        for i, h in enumerate(header):
            for hint in hints:
                if hint in h:
                    return i
        return None
    hi = find_col(["hero_index", "hero", "index", "영웅"])
    ai = find_col(["appearances", "count", "참여", "횟수", "등장"])
    if hi is None:
        return f"assistant 표에서 hero_index 컬럼 식별 실패 (header={header})"
    assistant_heroes = []
    for row in body:
        if len(row) <= hi:
            continue
        cell = row[hi].replace(",", "").replace("`", "").strip()
        try:
            idx = int(cell)
            assistant_heroes.append(idx)
        except Exception:
            continue
    truth_heroes = []
    for row in truth_rows:
        if not row or row[0] == "ERROR":
            continue
        try:
            truth_heroes.append(int(row[0]))
        except Exception:
            continue
    # Order-sensitive match of top K
    k = min(len(assistant_heroes), len(truth_heroes), 10)
    match = sum(1 for i in range(k) if assistant_heroes[i] == truth_heroes[i])
    assistant_set = set(assistant_heroes)
    truth_set = set(truth_heroes[:len(assistant_heroes)]) if assistant_heroes else set()
    set_match = len(assistant_set & truth_set)
    return (
        f"Top-{k} 순서 일치 {match}/{k} · 집합 일치 {set_match}/{len(assistant_heroes) or 1} · "
        f"assistant_first={assistant_heroes[:8]} · truth_first={truth_heroes[:8]}"
    )


def compare_global_skill_top20(assistant_answer_table, truth_rows):
    if not assistant_answer_table or len(assistant_answer_table) < 2:
        return "assistant 응답에 표 없음"
    header = [h.lower() for h in assistant_answer_table[0]]
    body = assistant_answer_table[1:]
    ai_combos = [r[0] for r in body if r]
    truth_combos = [r[0] for r in truth_rows if r and r[0] != "ERROR"]
    k = min(len(ai_combos), len(truth_combos), 10)
    match = sum(1 for i in range(k) if ai_combos[i].replace(" ", "") == truth_combos[i].replace(" ", ""))
    return f"글로벌 Top-{k} 순서 일치 {match}/{k} · assistant_first={ai_combos[:5]} · truth_first={truth_combos[:5]}"


def main() -> int:
    report_lines: list[str] = []
    report_lines.append("# TASK-0034 복잡 QA 성능 테스트 결과 리포트")
    report_lines.append("")
    report_lines.append(f"- 생성 시각: {subprocess.check_output(['date','+%Y-%m-%d %H:%M:%S']).decode().strip()}")
    report_lines.append("- 실행 환경: bootstrap_admin 계정, gpt-5.4-mini (API) × core (local LLM)")
    report_lines.append("- 최대 턴 한도: 20, heuristic stop on (table + ranking + length ≥ 400)")
    report_lines.append("")
    qids = ["Q1", "Q2", "Q3", "Q4", "Q5"]

    # Truth queries (cache once)
    truth_cache: dict[str, list[list[str]]] = {}
    for key, sql in TRUTH_QUERIES.items():
        print(f"running truth: {key}", flush=True)
        truth_cache[key] = run_mysql(sql)

    for qid in qids:
        report_lines.append(f"## {qid}")
        for side in ("api", "local"):
            run = load_run(RUNS_DIR / f"{side}-{qid}.json")
            summary = qid_summary(run)
            report_lines.append(f"### {side} · model={summary.get('model','?')}")
            report_lines.append("")
            report_lines.append(f"- 대화 ID: `{summary.get('conv_id','-')}`")
            report_lines.append(f"- 총 턴: {summary.get('total_turns','-')} / elapsed {summary.get('total_elapsed_s','-')}s / verdict: `{run.get('final_verdict','-')}`")
            report_lines.append(f"- 표 개수 (최종 답변): {len(summary.get('tables', []))}")
            if summary["tables"]:
                first_tbl = summary["tables"][0]
                report_lines.append("- 답변 첫 표 미리보기 (상위 6 행):")
                report_lines.append("")
                for row in first_tbl[:6]:
                    report_lines.append("  " + " | ".join(row))
                report_lines.append("")
            report_lines.append("- DB truth 대조:")
            try:
                if qid == "Q1" and summary["tables"]:
                    cmp = compare_global_skill_top20(summary["tables"][-1], truth_cache["Q1_global_top_tech"])
                elif qid == "Q2" and summary["tables"]:
                    cmp = compare_hero_top50(summary["tables"][0], truth_cache["Q2_hero_top50"])
                elif qid == "Q5" and summary["tables"]:
                    cmp = compare_hero_top50(summary["tables"][0], truth_cache["Q5_meta_hero_top20"])
                elif qid == "Q4" and summary["tables"]:
                    cmp = compare_hero_top50(summary["tables"][0], truth_cache["Q4_battletype_join"])
                elif qid == "Q3":
                    rows = truth_cache["Q3_gacha_category_state"]
                    nz = sum(1 for r in rows if r and r[0] != "ERROR")
                    cmp = f"truth 쿼리 row count={nz} (희소 데이터 — 수치 일치보다 논리 해석 타당성 위주 판정)"
                else:
                    cmp = "비교 불가 (assistant 표 없음)"
            except Exception as exc:
                cmp = f"비교 실패: {exc!r}"
            report_lines.append(f"  - {cmp}")
            report_lines.append("")
            report_lines.append("<details><summary>assistant 최종 답변 (접힘)</summary>")
            report_lines.append("")
            report_lines.append("```")
            ans = summary.get("last_answer") or ""
            report_lines.append(ans[:4000] + ("…(truncated)" if len(ans) > 4000 else ""))
            report_lines.append("```")
            report_lines.append("</details>")
            report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    # Truth query excerpt appendix
    report_lines.append("## Appendix: DB truth 쿼리 실행 결과 (최대 15 행)")
    for key, rows in truth_cache.items():
        report_lines.append(f"### {key}")
        report_lines.append("")
        report_lines.append("```")
        for r in rows[:15]:
            report_lines.append("\t".join(r))
        report_lines.append(f"...total {len(rows)} rows")
        report_lines.append("```")
        report_lines.append("")

    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
