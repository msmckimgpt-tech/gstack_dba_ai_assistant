#!/usr/bin/env python3
"""AI 능동 분석의 굳은 일시 실패 잡을 다시 큐에 올리는 운영자용 유틸 (feature-0016 analysis-retry-resilience).

배경(사용자 리포트 2026-07-30): 노드 분석 잡은 LLM 호출이 네트워크 단절·타임아웃·429·빈 응답으로
실패하면 곧바로 terminal `status='failed'` 로 굳었고, lease 회수는 `running` 만 대상이라 단절이
해소돼도 되살아나지 않았다. alembic 0049 + 워커 재시도(attempts/next_attempt_at)가 **앞으로의**
실패를 자동 회복하게 만들지만, 그 이전에 이미 굳은 행은 이 스크립트로 회수한다.

회수 대상 (`node_analysis.retry_failed_jobs` 와 동일 판정):
  · `error_kind LIKE 'transient%'`            — 재시도 상한을 소진한 일시 실패
  · `error_kind IS NULL AND error LIKE 'LLM %'` — 0049 이전 레거시 LLM 실패
  → 'verification-cleanup(취소)' 같은 인위적 실패와 영구 실패(bad_model/context_length)는 제외.

회수 시 `attempts` 를 0 으로 리셋하고(사람이 명시 요청한 경로라 새 예산을 준다) run 카운터를
복원한다(`failed` 차감 + `status='running'`). 되살린 잡은 insight-worker 다음 틱부터 처리된다.

**LLM 비용**: 회수한 항목마다 분석이 다시 수행된다. 기본은 dry-run 이며, 규모를 먼저 확인하고
`--execute` 로 실행한다.

실행(운영 — agent_kb PG 에 접근 가능한 컨테이너 안. 예: insight-worker / agent):
    python3 scripts/node_analysis_retry_failed.py                          # dry-run, 전체
    python3 scripts/node_analysis_retry_failed.py --scope mysql-42371f8d92bc
    python3 scripts/node_analysis_retry_failed.py --run-id <hex> --execute
    python3 scripts/node_analysis_retry_failed.py --execute --limit 200    # 부분 회수(비용 조절)
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_CORE_SRC = os.path.join(_REPO_ROOT, "unit", "feature-0002-agent-core", "src")
for _p in (_REPO_ROOT, _CORE_SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main() -> int:
    ap = argparse.ArgumentParser(description="굳은 일시 실패 노드 분석 잡 회수")
    ap.add_argument("--scope", default=None, help="datasource scope_key 한정(미지정=전체)")
    ap.add_argument("--run-id", default=None, help="특정 run 한정")
    ap.add_argument("--limit", type=int, default=500, help="1회 회수 상한(기본 500, 최대 5000)")
    ap.add_argument("--execute", action="store_true", help="실제 회수(기본은 dry-run)")
    args = ap.parse_args()

    from modules import node_analysis as na

    # dry-run 집계는 --execute 여부와 무관하게 먼저 보여준다(회수 규모를 로그에 남기기 위함).
    preview = na.retry_failed_jobs(run_id=args.run_id, scope_key=args.scope,
                                   limit=args.limit, dry_run=True)
    if not preview.get("ok"):
        print(f"[node-analysis-retry] 집계 실패: {preview.get('reason')}", file=sys.stderr)
        return 1
    this_run = int(preview.get("retried") or 0)          # 이번 실행량(limit 적용)
    eligible = int(preview.get("eligible") or this_run)   # 전체 대상
    runs = int(preview.get("runs") or 0)
    scope_txt = args.scope or "*"
    run_txt = args.run_id or "*"
    cap_txt = f" (전체 {eligible}건 중 limit={args.limit} 적용)" if preview.get("capped") else ""
    print(f"[node-analysis-retry] 이번 실행 대상: {this_run}건{cap_txt} / run {runs}개 "
          f"(scope={scope_txt} run_id={run_txt})")
    if not eligible:
        print("[node-analysis-retry] 회수할 일시 실패 항목이 없습니다.")
        return 0
    if not args.execute:
        print(f"[node-analysis-retry] dry-run — 실제 회수는 --execute. "
              f"회수 시 {this_run}건에 LLM 분석이 다시 수행됩니다"
              f"{'(나머지는 재실행으로 이어서 회수)' if preview.get('capped') else ''}.")
        return 0

    res = na.retry_failed_jobs(run_id=args.run_id, scope_key=args.scope, limit=args.limit)
    if not res.get("ok"):
        print(f"[node-analysis-retry] 회수 실패: {res.get('reason')}", file=sys.stderr)
        return 1
    print(f"[node-analysis-retry] 회수 완료: {res.get('retried')}건 / run {res.get('runs')}개")
    for rid in (res.get("run_ids") or []):
        print(f"  · run {rid}")
    print("[node-analysis-retry] insight-worker 다음 틱부터 처리됩니다(진행 패널에서 확인).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
