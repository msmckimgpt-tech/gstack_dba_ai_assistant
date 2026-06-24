"""ITEM-05 **적대적** retrieval A/B — fusion vs 2-tier, evalkb_adv scope.

retrieval_eval.py 의 적대 corpus 버전. provision_kb_adv(evalkb_adv) 를 대상으로
fusion ON/OFF + 파라미터 대조(NORMALIZE on/off, ALPHA/BETA)를 같은 질문에 흘려
precision/recall/f1@k(k=3,5) + MRR 를 산출하고, per-question rank 진단(정답 doc 의
2-tier rank vs fusion rank)을 포함한 리포트를 낸다.

격리: evalkb_adv scope + __evalkb_adv__ conversation. 측정 후 --purge-after 로 정리.

진입점:
  python -m kb_eval.retrieval_eval_adv [--provision] [--purge-after] [--sweep]
  --provision   : 실행 전 provision_kb_adv.provision()
  --purge-after : 실행 후 provision_kb_adv.purge()
  --sweep       : 파라미터 대조(NORMALIZE on/off · ALPHA/BETA 조합)까지 실행
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

if __package__ in (None, ""):
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_HERE))

from kb_eval import provision_kb_adv as P  # noqa: E402


def _load_golden(path: str) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _metrics(ranked: list[str], relevant: list[str], k: int) -> dict:
    rel = {str(x) for x in (relevant or [])}
    ranked = [str(x) for x in (ranked or [])]
    topk = ranked[:k]
    tp = len(set(topk) & rel)
    precision = (tp / len(topk)) if topk else 0.0
    recall = (tp / len(rel)) if rel else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    rr = 0.0
    ans_rank = None
    for i, key in enumerate(ranked, 1):
        if key in rel:
            rr = 1.0 / i
            ans_rank = i
            break
    return {
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4), "rr": round(rr, 4), "ans_rank": ans_rank,
    }


def _retrieve(question: str, hybrid_enabled: bool) -> list[str]:
    from modules import config as cfg  # type: ignore
    from modules import kb_retrieval  # type: ignore

    prev = cfg.AGENT_KB_HYBRID_ENABLED
    cfg.AGENT_KB_HYBRID_ENABLED = bool(hybrid_enabled)
    try:
        rows = kb_retrieval._load_rag_documents_for_request_pg(
            [P.EVAL_CONVERSATION_ID], question, [P.EVAL_SCOPE, ""],
        )
    finally:
        cfg.AGENT_KB_HYBRID_ENABLED = prev
    if rows is None:
        return []
    return [str(r.get("key") or "") for r in rows if r.get("key")]


def _eval_mode(questions: list[dict], hybrid_enabled: bool, ks: list[int]) -> dict:
    per_q = []
    agg = {k: {"p": 0.0, "r": 0.0, "f": 0.0} for k in ks}
    sum_rr = 0.0
    for q in questions:
        ranked = _retrieve(q["nl_question"], hybrid_enabled)
        row = {"id": q.get("id"), "ranked": ranked, "relevant": q.get("relevant_doc_keys")}
        for k in ks:
            m = _metrics(ranked, q.get("relevant_doc_keys"), k)
            row[f"p@{k}"] = m["precision"]
            row[f"r@{k}"] = m["recall"]
            row[f"f@{k}"] = m["f1"]
            agg[k]["p"] += m["precision"]
            agg[k]["r"] += m["recall"]
            agg[k]["f"] += m["f1"]
        m_full = _metrics(ranked, q.get("relevant_doc_keys"), max(ks))
        row["rr"] = m_full["rr"]
        row["ans_rank"] = m_full["ans_rank"]
        sum_rr += m_full["rr"]
        per_q.append(row)
    n = max(len(questions), 1)
    out = {
        "mode": "fusion" if hybrid_enabled else "2-tier",
        "n_questions": len(questions),
        "mrr": round(sum_rr / n, 4),
        "per_question": per_q,
    }
    for k in ks:
        out[f"mean_precision@{k}"] = round(agg[k]["p"] / n, 4)
        out[f"mean_recall@{k}"] = round(agg[k]["r"] / n, 4)
        out[f"mean_f1@{k}"] = round(agg[k]["f"] / n, 4)
    return out


def _run_ab(questions: list[dict], ks: list[int]) -> dict:
    two_tier = _eval_mode(questions, hybrid_enabled=False, ks=ks)
    fusion = _eval_mode(questions, hybrid_enabled=True, ks=ks)
    delta = {"mrr": round(fusion["mrr"] - two_tier["mrr"], 4)}
    for k in ks:
        delta[f"precision@{k}"] = round(fusion[f"mean_precision@{k}"] - two_tier[f"mean_precision@{k}"], 4)
        delta[f"recall@{k}"] = round(fusion[f"mean_recall@{k}"] - two_tier[f"mean_recall@{k}"], 4)
        delta[f"f1@{k}"] = round(fusion[f"mean_f1@{k}"] - two_tier[f"mean_f1@{k}"], 4)
    improved = any(v > 0.0001 for v in delta.values())
    regressed = any(v < -0.0001 for v in delta.values())
    if improved and not regressed:
        verdict = "IMPROVED — fusion 이 적대 corpus 에서 lift"
    elif improved and regressed:
        verdict = "MIXED — 일부 상승 일부 하락"
    elif regressed and not improved:
        verdict = "REGRESSION — fusion 이 더 나쁨"
    else:
        verdict = "NEUTRAL — 동등(lift 없음)"
    return {"two_tier": two_tier, "fusion": fusion, "delta": delta, "verdict": verdict}


def _apply_cfg(normalize: bool, alpha: float, beta: float):
    from modules import config as cfg  # type: ignore
    prev = (cfg.AGENT_KB_HYBRID_NORMALIZE, cfg.AGENT_KB_HYBRID_ALPHA, cfg.AGENT_KB_HYBRID_BETA)
    cfg.AGENT_KB_HYBRID_NORMALIZE = bool(normalize)
    cfg.AGENT_KB_HYBRID_ALPHA = float(alpha)
    cfg.AGENT_KB_HYBRID_BETA = float(beta)
    return prev


def _restore_cfg(prev):
    from modules import config as cfg  # type: ignore
    cfg.AGENT_KB_HYBRID_NORMALIZE, cfg.AGENT_KB_HYBRID_ALPHA, cfg.AGENT_KB_HYBRID_BETA = prev


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="ITEM-05 적대적 KB retrieval A/B (fusion vs 2-tier)")
    p.add_argument("--golden", default=os.path.join(here, "golden_retrieval_adv.yaml"))
    p.add_argument("--provision", action="store_true")
    p.add_argument("--purge-after", action="store_true")
    p.add_argument("--sweep", action="store_true", help="NORMALIZE on/off + ALPHA/BETA 대조")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    from modules import config as cfg  # type: ignore

    if args.provision:
        print("[adv] provisioning evalkb_adv …", file=sys.stderr)
        P.provision()

    golden = _load_golden(args.golden)
    questions = golden.get("questions", [])
    if not questions:
        raise SystemExit("[adv] golden 질문 없음")
    ks = [3, 5]

    # 기본 A/B — 현 config 기본값(NORMALIZE=1, ALPHA=0.6, BETA=0.4).
    print(f"[adv] base A/B — {len(questions)}Q, NORM={cfg.AGENT_KB_HYBRID_NORMALIZE} "
          f"α={cfg.AGENT_KB_HYBRID_ALPHA} β={cfg.AGENT_KB_HYBRID_BETA}", file=sys.stderr)
    base = _run_ab(questions, ks)

    sweep_results = []
    if args.sweep:
        combos = [
            (True, 0.6, 0.4), (True, 0.5, 0.5), (True, 0.7, 0.3), (True, 0.3, 0.7),
            (True, 0.4, 0.6),
            (False, 0.6, 0.4), (False, 0.5, 0.5),
        ]
        for norm, a, b in combos:
            prev = _apply_cfg(norm, a, b)
            try:
                r = _run_ab(questions, ks)
            finally:
                _restore_cfg(prev)
            sweep_results.append({
                "normalize": norm, "alpha": a, "beta": b,
                "two_tier_mrr": r["two_tier"]["mrr"], "fusion_mrr": r["fusion"]["mrr"],
                "delta": r["delta"], "verdict": r["verdict"],
                "fusion_p@3": r["fusion"]["mean_precision@3"],
                "fusion_r@5": r["fusion"]["mean_recall@5"],
            })
            print(f"[adv][sweep] norm={norm} α={a} β={b} → "
                  f"2tier_mrr={r['two_tier']['mrr']} fusion_mrr={r['fusion']['mrr']} "
                  f"Δmrr={r['delta']['mrr']:+.4f} {r['verdict']}", file=sys.stderr)

    payload = {
        "meta": {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "golden": os.path.basename(args.golden),
            "ks": ks, "n_questions": len(questions),
            "scope": P.EVAL_SCOPE, "model": cfg.AGENT_KB_EMBEDDING_MODEL,
            "base_alpha": float(cfg.AGENT_KB_HYBRID_ALPHA),
            "base_beta": float(cfg.AGENT_KB_HYBRID_BETA),
            "base_normalize": bool(cfg.AGENT_KB_HYBRID_NORMALIZE),
            "trigram_floor": float(cfg.AGENT_KB_HYBRID_TRIGRAM_FLOOR),
        },
        "base": base,
        "sweep": sweep_results,
    }

    out_dir = args.out or os.path.join(cfg.AGENT_OUT_DIR, "eval")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(out_dir, f"{ts}_kb_retrieval_adv_ab.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # stdout 요약
    print(json.dumps({
        "base_verdict": base["verdict"],
        "base_delta": base["delta"],
        "two_tier": {k: base["two_tier"][k] for k in base["two_tier"] if k.startswith("mean") or k == "mrr"},
        "fusion": {k: base["fusion"][k] for k in base["fusion"] if k.startswith("mean") or k == "mrr"},
        "per_question_ranks": [
            {"id": q["id"], "tt_rank": tt["ans_rank"], "fu_rank": fu["ans_rank"],
             "tt_top": tt["ranked"][:3], "fu_top": fu["ranked"][:3]}
            for tt, fu, q in zip(base["two_tier"]["per_question"], base["fusion"]["per_question"], questions)
        ],
    }, ensure_ascii=False, indent=2))
    print(f"\n[adv] report: {json_path}", file=sys.stderr)

    if args.purge_after:
        print("[adv] purging evalkb_adv …", file=sys.stderr)
        P.purge()
    return 0


if __name__ == "__main__":
    sys.exit(main())
