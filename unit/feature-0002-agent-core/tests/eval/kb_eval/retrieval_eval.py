"""ITEM-05 retrieval A/B eval — fusion(하이브리드) vs 2-tier, precision/recall@k.

각 golden 질문에 대해 **retrieval 함수를 직접 호출**한다(전체 agent 파이프라인 불요 —
쿼리 임베딩 1회 + PG 검색만, 저비용). fusion ON(AGENT_KB_HYBRID_ENABLED=True)과
2-tier OFF(False) 두 모드로 동일 질문을 흘려 반환 doc keys vs golden relevant_doc_keys 로
precision/recall@k 를 계산하고, A/B 수치를 artifacts(JSON + MD)에 리포트한다.

격리: evalkb scope + __evalkb__ conversation 으로만 검색(운영 KB 무관). provision_kb 가
사전 적재해야 한다(없으면 0 docs → 안내 후 종료).

진입점: `python -m kb_eval.retrieval_eval [--k 5] [--provision] [--purge-after]`
  --provision   : 실행 전 provision_kb.provision() 호출(멱등 적재)
  --purge-after : 실행 후 provision_kb.purge() 로 evalkb 정리
  --k           : precision/recall@k 의 k (기본 5)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

# 직접 실행(python kb_eval/retrieval_eval.py) 대비 — 패키지/모듈 경로 보강.
if __package__ in (None, ""):
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_HERE))  # tests/eval (kb_eval 패키지 부모)

from kb_eval import provision_kb as P  # noqa: E402


def _load_golden(path: str) -> dict:
    import yaml  # make/runner 가 설치
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _precision_recall_at_k(retrieved_keys: list[str], relevant: list[str], k: int) -> dict:
    """retrieved_keys(랭킹 순) 상위 k vs relevant set → precision/recall@k + MRR.

    MRR(mean reciprocal rank, 여기선 단일 질문의 RR): 첫 relevant doc 의 1/rank.
    소규모 corpus 에서 recall@k 가 1.0 로 포화될 때 랭킹 품질(상위에 올렸는가)을
    변별하는 rank-aware 지표 — fusion 의 재랭킹 효과를 잡아낸다.
    """
    rel = {str(x) for x in (relevant or [])}
    ranked = [str(x) for x in (retrieved_keys or [])]
    topk = ranked[:k]
    topk_set = set(topk)
    tp = len(topk_set & rel)
    precision = (tp / len(topk)) if topk else 0.0
    recall = (tp / len(rel)) if rel else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    # RR — 전체 랭킹에서 첫 relevant 의 역순위.
    rr = 0.0
    for i, key in enumerate(ranked, 1):
        if key in rel:
            rr = 1.0 / i
            break
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "rr": round(rr, 4),
        "tp": tp,
        "n_retrieved_topk": len(topk),
        "n_relevant": len(rel),
    }


def _retrieve(question: str, hybrid_enabled: bool) -> list[str]:
    """retrieval 함수 직접 호출 → 반환 doc keys(랭킹 순). hybrid_enabled 로 fusion/2-tier 토글."""
    from shared import config as cfg  # type: ignore
    from modules import kb_retrieval  # type: ignore

    prev = cfg.AGENT_KB_HYBRID_ENABLED
    cfg.AGENT_KB_HYBRID_ENABLED = bool(hybrid_enabled)
    try:
        rows = kb_retrieval._load_rag_documents_for_request_pg(
            [P.EVAL_CONVERSATION_ID],
            question,
            [P.EVAL_SCOPE, ""],
        )
    finally:
        cfg.AGENT_KB_HYBRID_ENABLED = prev
    if rows is None:
        return []
    return [str(r.get("key") or "") for r in rows if r.get("key")]


def _eval_mode(questions: list[dict], hybrid_enabled: bool, k: int) -> dict:
    per_q = []
    sum_p = sum_r = sum_f = sum_rr = 0.0
    for q in questions:
        keys = _retrieve(q["nl_question"], hybrid_enabled)
        pr = _precision_recall_at_k(keys, q.get("relevant_doc_keys"), k)
        per_q.append({
            "id": q.get("id"),
            "retrieved_topk": keys[:k],
            "relevant": q.get("relevant_doc_keys"),
            **pr,
        })
        sum_p += pr["precision"]
        sum_r += pr["recall"]
        sum_f += pr["f1"]
        sum_rr += pr["rr"]
    n = max(len(questions), 1)
    return {
        "mode": "fusion" if hybrid_enabled else "2-tier",
        "k": k,
        "n_questions": len(questions),
        "mean_precision": round(sum_p / n, 4),
        "mean_recall": round(sum_r / n, 4),
        "mean_f1": round(sum_f / n, 4),
        "mrr": round(sum_rr / n, 4),
        "per_question": per_q,
    }


def _write_report(out_dir: str, payload: dict) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(out_dir, f"{ts}_kb_retrieval_ab")
    json_path, md_path = base + ".json", base + ".md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    fu = payload["fusion"]
    tt = payload["two_tier"]
    d = payload["delta"]
    lines = [f"# KB retrieval A/B — fusion vs 2-tier ({ts})", ""]
    lines.append(f"- golden: `{payload['meta']['golden']}` · k={payload['meta']['k']} · "
                 f"docs={payload['meta']['n_questions']}Q · scope=`{P.EVAL_SCOPE}`")
    lines.append(f"- α={payload['meta']['alpha']} β={payload['meta']['beta']} · model=`{payload['meta']['model']}`")
    lines.append("")
    lines.append("| metric | 2-tier | fusion | Δ(fusion−2tier) |")
    lines.append("|---|---|---|---|")
    lines.append(f"| mean_precision@{fu['k']} | {tt['mean_precision']} | {fu['mean_precision']} | {d['precision']:+.4f} |")
    lines.append(f"| mean_recall@{fu['k']} | {tt['mean_recall']} | {fu['mean_recall']} | {d['recall']:+.4f} |")
    lines.append(f"| mean_f1@{fu['k']} | {tt['mean_f1']} | {fu['mean_f1']} | {d['f1']:+.4f} |")
    lines.append(f"| MRR | {tt['mrr']} | {fu['mrr']} | {d['mrr']:+.4f} |")
    lines.append("")
    verdict = payload["verdict"]
    lines.append(f"- **verdict**: {verdict}")
    lines.append("")
    lines.append("## per-question (fusion)")
    lines.append("| id | P | R | retrieved@k | relevant |")
    lines.append("|---|---|---|---|---|")
    for r in fu["per_question"]:
        lines.append(f"| {r['id']} | {r['precision']} | {r['recall']} | "
                     f"{','.join(r['retrieved_topk'])} | {','.join(r['relevant'])} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return json_path, md_path


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="ITEM-05 KB retrieval A/B (fusion vs 2-tier)")
    p.add_argument("--golden", default=os.path.join(here, "golden_retrieval.yaml"))
    p.add_argument("--k", type=int, default=3,
                   help="precision/recall@k 의 k (기본 3 — 소규모 corpus 에서 랭킹 변별).")
    p.add_argument("--provision", action="store_true", help="실행 전 evalkb 멱등 적재")
    p.add_argument("--purge-after", action="store_true", help="실행 후 evalkb 정리")
    p.add_argument("--out", default=None, help="리포트 출력 디렉터리(기본 AGENT_OUT_DIR/eval)")
    args = p.parse_args(argv)

    from shared import config as cfg  # type: ignore

    if args.provision:
        print("[retrieval_eval] provisioning evalkb …", file=sys.stderr)
        P.provision()

    golden = _load_golden(args.golden)
    questions = golden.get("questions", [])
    if not questions:
        raise SystemExit("[retrieval_eval] golden 질문 없음")

    print(f"[retrieval_eval] {len(questions)}Q · k={args.k} · fusion ON/OFF 양쪽 실행 …", file=sys.stderr)
    two_tier = _eval_mode(questions, hybrid_enabled=False, k=args.k)
    fusion = _eval_mode(questions, hybrid_enabled=True, k=args.k)

    delta = {
        "precision": round(fusion["mean_precision"] - two_tier["mean_precision"], 4),
        "recall": round(fusion["mean_recall"] - two_tier["mean_recall"], 4),
        "f1": round(fusion["mean_f1"] - two_tier["mean_f1"], 4),
        "mrr": round(fusion["mrr"] - two_tier["mrr"], 4),
    }
    # 회귀 판정: fusion 이 2-tier 보다 P/R/F1/MRR 어느것도 유의하게 나쁘지 않으면 PASS.
    regressed = any(delta[m] < -0.0001 for m in ("precision", "recall", "f1", "mrr"))
    improved = any(delta[m] > 0.0001 for m in ("precision", "recall", "f1", "mrr"))
    if regressed and not improved:
        verdict = "REGRESSION — fusion 이 2-tier 보다 나쁨"
    elif improved and not regressed:
        verdict = "IMPROVED — fusion 이 2-tier 보다 좋음"
    elif improved and regressed:
        verdict = "MIXED — 일부 지표 상승, 일부 하락"
    else:
        verdict = "NEUTRAL — 동등(회귀 없음)"

    out_dir = args.out or os.path.join(cfg.AGENT_OUT_DIR, "eval")
    payload = {
        "meta": {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "golden": os.path.basename(args.golden),
            "k": args.k,
            "n_questions": len(questions),
            "alpha": float(cfg.AGENT_KB_HYBRID_ALPHA),
            "beta": float(cfg.AGENT_KB_HYBRID_BETA),
            "model": cfg.AGENT_KB_EMBEDDING_MODEL,
            "scope": P.EVAL_SCOPE,
        },
        "two_tier": two_tier,
        "fusion": fusion,
        "delta": delta,
        "verdict": verdict,
    }
    json_path, md_path = _write_report(out_dir, payload)

    _keys = ("mean_precision", "mean_recall", "mean_f1", "mrr")
    print(json.dumps({"two_tier": {k: two_tier[k] for k in _keys},
                      "fusion": {k: fusion[k] for k in _keys},
                      "delta": delta, "verdict": verdict}, ensure_ascii=False, indent=2))
    print(f"\n[retrieval_eval] report: {json_path}\n[retrieval_eval] report: {md_path}", file=sys.stderr)

    if args.purge_after:
        print("[retrieval_eval] purging evalkb …", file=sys.stderr)
        P.purge()
    return 0


if __name__ == "__main__":
    sys.exit(main())
