"""ITEM-01 NL→SQL 평가 runner.

golden 질문을 **실제 agent 파이프라인**(run_agent, 내부 temp-0 결정 경로)에 흘려
생성SQL 을 수집하고, fixture 에 생성SQL·정답SQL 을 실행해 execution-accuracy 를 산출,
타임스탬프 회귀 리포트를 artifacts 에 남긴다.

사용:
  python -m tests.eval.runner                 # 전 golden, 단일 run, 회귀 비교
  python -m tests.eval.runner --limit 6       # 앞 N 질문만(스모크/비용 절감)
  python -m tests.eval.runner --judge         # execution mismatch 에 LLM-as-Judge(cap)
  python -m tests.eval.runner --tag det2      # 리포트 라벨(결정성 2-run 비교용)

진입점 `make eval`. AGENT_MULTI_DATASOURCE_ENABLED=1 필요(데이터플레인 좌표 라우팅).
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys

# sys.path: src(modules/agent_core) + tests/eval(sibling 모듈) 가 있어야 한다.
# make eval 가 PYTHONPATH 를 설정. pytest 는 conftest(src 추가) + prepend(tests/eval) 로 충족.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared import config as cfg  # noqa: E402

import fixture_provision as fp  # noqa: E402
import metrics as M  # noqa: E402

# expected_sql(신뢰된 golden) 검증용 보수 가드. `replace`/`merge`/`call` 은 read-only
# 함수로도 쓰여 제외(오탐 방지); 파괴/유출계만 차단(+ INTO OUTFILE/DUMPFILE/LOAD_FILE).
_FORBIDDEN = (r"insert", r"update", r"delete", r"drop", r"alter", r"create",
              r"truncate", r"grant", r"revoke", r"into\s+outfile",
              r"into\s+dumpfile", r"load_file")


def _is_readonly(sql: str) -> bool:
    """SELECT/WITH 로 시작 + 파괴/유출계 키워드 부재. (생성SQL 은 재실행하지 않으므로
    이 가드는 신뢰된 expected_sql 의 golden-저자 실수 insurance 용.)"""
    s = (sql or "").strip().rstrip(";").lower()
    if not s:
        return False
    if not (s.startswith("select") or s.startswith("with")):
        return False
    # 토큰 경계로 차단(컬럼명 'created_at'/'update_count' 등 오탐 방지).
    import re
    for kw in _FORBIDDEN:
        if re.search(rf"(^|[\s(;]){kw}([\s(]|$)", s):
            return False
    return True


def _read_result_csv(path: str) -> tuple[list, list]:
    """agent 가 저장한 결과 CSV(header + rows) 파싱 → (columns, rows)."""
    import csv
    with open(path, "r", encoding="utf-8", newline="") as f:
        all_rows = list(csv.reader(f))
    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1:]


def _load_golden(path: str) -> dict:
    try:
        import yaml
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"PyYAML 필요(make eval 가 설치): {e}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_retrieved_kb_ids(result: dict) -> list:
    """best-effort: steps 에서 검색된 KB 객체 id 추출. 미노출이면 []( retrieval N/A)."""
    ids: list = []
    for step in (result.get("steps") or []):
        if not isinstance(step, dict):
            continue
        for key in ("kb_ids", "retrieved_ids", "rag_ids"):
            v = step.get(key)
            if isinstance(v, (list, tuple)):
                ids.extend(v)
    return ids


def _eval_one(q: dict, ds: dict, model: str, use_judge: bool, judge_budget: list) -> dict:
    """질문 1건 평가 → record dict."""
    import agent_core

    qid = q.get("id", "?")
    nl = q["nl_question"]
    expected_sql = q["expected_sql"]
    rec: dict = {"id": qid, "nl_question": nl, "tags": q.get("tags", [])}

    # 1) 실제 파이프라인 실행(temp-0 결정 경로).
    try:
        result = agent_core.run_agent(
            nl,
            conversation_id=None,
            model=model,
            output_mode="json",
            product_id=None,
            allowed_schemas=[fp.FIXTURE_DB],
            eval_datasource=ds,
            max_steps=int(os.getenv("EVAL_MAX_STEPS", "12")),
        )
    except Exception as e:
        rec.update(generated_sql="", agent_error=f"run_agent raised: {e!r}",
                   execution_success=False, execution_accuracy=False)
        return rec

    generated_sql = (result.get("executed_sql") or "").strip()
    rec["generated_sql"] = generated_sql          # 진단 기록 — harness 가 재실행하지 않음(보안).
    rec["agent_error"] = result.get("error") or ""

    # 2) 정답 ground-truth — expected_sql 는 신뢰된 golden(저자=우리, SELECT·eval_fixture 한정,
    #    golden 무결성 테스트가 강제). read-only 가드는 보수적 insurance.
    if not _is_readonly(expected_sql):
        rec.update(execution_success=False, execution_accuracy=False,
                   harness_error="expected_sql read-only 가드 위반(golden 오류)")
        return rec
    try:
        _, exp_rows = fp.run_sql(expected_sql)
    except Exception as e:
        rec.update(execution_success=False, execution_accuracy=False,
                   harness_error=f"expected_sql 실행 실패(golden 오류?): {e!r}")
        return rec

    # 3) actual = **agent 가 실제 실행해 산출한 결과**(result_csv_paths). 생성SQL 을 harness 가
    #    재실행하지 않는다 — agent 실행은 이미 sql_guard + allowlist([eval_fixture])로 샌드박싱됐고
    #    (REV-…-eval-harness BLOCKER), executed_sql 은 guard *이전* raw 라 root 재실행이 위험(공존
    #    운영 memory DB cross-schema 읽기·INTO OUTFILE 등). agent CSV 가 안전+충실한 정답.
    csv_paths = result.get("result_csv_paths") or []
    if rec["agent_error"]:
        rec.update(execution_success=False, execution_accuracy=False)
    elif not csv_paths:
        rec.update(execution_success=False, execution_accuracy=False,
                   note="agent 결과 CSV 없음(SQL 미실행/빈 답변)")
    else:
        try:
            # 마지막 execute_sql 결과 = 답변 쿼리(golden 은 단일-답변). 다중 execute 시 한계는 note.
            _, act_rows = _read_result_csv(csv_paths[-1])
            rec["execution_success"] = True
            rec["execution_accuracy"] = M.result_equiv(exp_rows, act_rows)
            rec["expected_rowcount"] = len(exp_rows)
            rec["actual_rowcount"] = len(act_rows)
        except Exception as e:
            rec.update(execution_success=False, execution_accuracy=False,
                       harness_error=f"결과 CSV 읽기 실패: {e!r}")

    # 4) retrieval P/R (ground-truth 있을 때만).
    rec["retrieval"] = M.retrieval_precision_recall(
        _extract_retrieved_kb_ids(result), q.get("relevant_kb_ids"))

    # 5) (선택) LLM-as-Judge — execution mismatch 진단, cap 내에서만.
    if use_judge and not rec.get("execution_accuracy") and generated_sql and judge_budget[0] > 0:
        verdict = M.llm_sql_judge(nl, expected_sql, generated_sql)
        if verdict is not None:
            judge_budget[0] -= 1
            rec["judge_equiv"] = verdict
    return rec


def _aggregate(records: list) -> dict:
    n = len(records)
    succ = sum(1 for r in records if r.get("execution_success"))
    acc = sum(1 for r in records if r.get("execution_accuracy"))
    # per-tag
    by_tag: dict = {}
    for r in records:
        for t in r.get("tags", []):
            d = by_tag.setdefault(t, {"n": 0, "acc": 0})
            d["n"] += 1
            d["acc"] += 1 if r.get("execution_accuracy") else 0
    # retrieval(ground-truth 있는 것만)
    rets = [r["retrieval"] for r in records if isinstance(r.get("retrieval"), dict)]
    ret_agg = None
    if rets:
        ret_agg = {
            "n_with_groundtruth": len(rets),
            "mean_precision": round(sum(x["precision"] for x in rets) / len(rets), 4),
            "mean_recall": round(sum(x["recall"] for x in rets) / len(rets), 4),
        }
    judged = [r for r in records if "judge_equiv" in r]
    return {
        "n_total": n,
        "execution_success": succ,
        "execution_success_rate": round(succ / n, 4) if n else 0.0,
        "execution_accuracy": acc,
        "execution_accuracy_rate": round(acc / n, 4) if n else 0.0,
        "by_tag": {t: {"n": d["n"], "accuracy_rate": round(d["acc"] / d["n"], 4)}
                   for t, d in sorted(by_tag.items())},
        "retrieval": ret_agg if ret_agg else "N/A (relevant_kb_ids 비어있음 — KB 자산 후 의미)",
        "judge": {"n_called": len(judged),
                  "n_equiv": sum(1 for r in judged if r.get("judge_equiv"))} if judged else "N/A",
    }


def _find_prior_report(out_dir: str, exclude: str) -> "dict | None":
    cands = sorted(glob.glob(os.path.join(out_dir, "*_nl2sql_eval.json")))
    cands = [c for c in cands if os.path.abspath(c) != os.path.abspath(exclude)]
    if not cands:
        return None
    try:
        with open(cands[-1], "r", encoding="utf-8") as f:
            return {"path": cands[-1], "data": json.load(f)}
    except Exception:
        return None


def _write_report(out_dir: str, agg: dict, records: list, meta: dict) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(out_dir, f"{ts}_{meta.get('tag', 'full')}_nl2sql_eval")
    json_path, md_path = base + ".json", base + ".md"

    prior = _find_prior_report(out_dir, json_path)
    regression = None
    if prior:
        prev_rate = prior["data"].get("aggregate", {}).get("execution_accuracy_rate")
        if isinstance(prev_rate, (int, float)):
            delta = round(agg["execution_accuracy_rate"] - prev_rate, 4)
            regression = {"prior_report": os.path.basename(prior["path"]),
                          "prior_accuracy_rate": prev_rate, "delta": delta,
                          "regressed": delta < -0.0001}

    payload = {"meta": meta, "aggregate": agg, "regression": regression, "records": records}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [f"# NL→SQL eval report — {ts} (tag={meta.get('tag')})", ""]
    lines.append(f"- golden: `{meta.get('golden')}` · datasource: `{meta.get('datasource')}` · model: `{meta.get('model')}`")
    lines.append(f"- **execution_accuracy: {agg['execution_accuracy']}/{agg['n_total']} "
                 f"({agg['execution_accuracy_rate']:.1%})**")
    lines.append(f"- execution_success: {agg['execution_success']}/{agg['n_total']} "
                 f"({agg['execution_success_rate']:.1%})")
    if regression:
        flag = "⚠️ REGRESSION" if regression["regressed"] else "ok"
        lines.append(f"- 회귀(vs {regression['prior_report']}): Δ {regression['delta']:+.4f} [{flag}]")
    lines.append(f"- retrieval: {agg['retrieval']}")
    lines.append("")
    lines.append("| tag | accuracy |")
    lines.append("|---|---|")
    for t, d in agg["by_tag"].items():
        lines.append(f"| {t} | {d['accuracy_rate']:.1%} ({d['n']}) |")
    lines.append("")
    lines.append("| id | acc | succ | tags |")
    lines.append("|---|---|---|---|")
    for r in records:
        lines.append(f"| {r['id']} | {'✓' if r.get('execution_accuracy') else '✗'} | "
                     f"{'✓' if r.get('execution_success') else '✗'} | {','.join(r.get('tags', []))} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return json_path, md_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="NL→SQL eval harness (ITEM-01)")
    here = os.path.dirname(__file__)
    p.add_argument("--golden", default=os.path.join(here, "golden", "eval_fixture.yaml"))
    p.add_argument("--limit", type=int, default=0, help="앞 N 질문만(0=전체)")
    p.add_argument("--model", default=os.getenv("EVAL_MODEL", "claude-sonnet-4"),
                   help="평가 LLM 모델 별칭(구체 claude-* — 'auto'는 로컬tier라 부적합). EVAL_MODEL env.")
    p.add_argument("--judge", action="store_true", help="execution mismatch 에 LLM-as-Judge(cap)")
    p.add_argument("--tag", default="full", help="리포트 라벨")
    p.add_argument("--out", default=os.path.join(cfg.AGENT_OUT_DIR, "eval"))
    args = p.parse_args(argv)

    if not cfg.AGENT_MULTI_DATASOURCE_ENABLED:
        # fail-closed: flag OFF 면 db.connect 가 eval_datasource 좌표를 무시하고 휴리스틱으로
        # 엉뚱한 DB(제어 plane/default)에 연결될 수 있어, 경고가 아닌 하드 중단.
        raise SystemExit("[eval] AGENT_MULTI_DATASOURCE_ENABLED 미설정 — eval_datasource 좌표 "
                         "라우팅 비활성 시 fixture 대신 엉뚱한 DB 연결 위험. `make eval` 로 실행하거나 "
                         "AGENT_MULTI_DATASOURCE_ENABLED=1 을 설정하세요.")

    golden = _load_golden(args.golden)
    ds_name = golden.get("datasource", fp.FIXTURE_DB)
    if ds_name != fp.FIXTURE_DB:
        raise SystemExit(f"[eval] guard: golden datasource 는 {fp.FIXTURE_DB} 만 허용(폐쇄망/PII). got={ds_name}")
    questions = golden.get("questions", [])
    if args.limit > 0:
        questions = questions[: args.limit]

    print(f"[eval] provision fixture({fp.FIXTURE_DB}) …", file=sys.stderr)
    fp.ensure_fixture()
    ds = fp.fixture_datasource()

    judge_budget = [M.judge_cap() if args.judge else 0]
    records = []
    print(f"[eval] model={args.model}", file=sys.stderr)
    for i, q in enumerate(questions, 1):
        print(f"[eval] ({i}/{len(questions)}) {q.get('id')} …", file=sys.stderr)
        rec = _eval_one(q, ds, args.model, args.judge, judge_budget)
        records.append(rec)
        print(f"[eval]   acc={'✓' if rec.get('execution_accuracy') else '✗'} "
              f"succ={'✓' if rec.get('execution_success') else '✗'}", file=sys.stderr)

    agg = _aggregate(records)
    meta = {"tag": args.tag, "golden": os.path.basename(args.golden), "datasource": ds_name,
            "model": args.model, "limit": args.limit,
            "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    json_path, md_path = _write_report(args.out, agg, records, meta)
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    print(f"\n[eval] report: {json_path}\n[eval] report: {md_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
