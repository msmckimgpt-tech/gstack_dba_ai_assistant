#!/usr/bin/env python
"""feature-0016 Phase 1c: 관계형 메타데이터 → Apache AGE `metadata_kb` 그래프 동기화 CLI.

워커 컨테이너(insight-worker/ask-worker) 안에서 실행:
    python /app/scripts/metadata_graph_sync.py [--scope KEY] [--quiet] [--incremental|--full]

관계형 SSOT(table_descriptions·column_descriptions·table_relationships·kb_glossary·
glossary_relations)를 AGE 그래프로 멱등 투영한다(modules.metadata_graph.sync_graph).
AGE cutover(shared_preload_libraries='age') 이후에만 실효 — 그 전엔 sync_graph 가 graceful
no-op(errors 카운트, 비차단). bin/metadata-graph-sync.sh 가 본 스크립트를 docker exec 한다.

insight-load-spread (부하 분산):
  - sync_graph 는 노드/엣지를 batched commit(기본 500개/커밋)으로 묶어 WAL fsync 폭주(8K 규모 5.7만 →
    ~100)를 차단한다 — 항상 적용(옵션 무관).
  - --incremental (또는 env AGENT_METADATA_GRAPH_SYNC_INCREMENTAL=1): 직전 성공 sync 이후 변경분
    (updated_at > 워터마크)만 MERGE → 변경 없는 30분 cron 은 거의 no-op(MERGE CPU 절감). 워터마크는
    agent_runtime.kv 에 scope 별 저장. 삭제/파단 반영은 --full 이 담당(주기적으로 병행 권장).
  - --full: 워터마크 무시하고 전량 동기화(삭제된 노드/파단 관계를 그래프에서 정리). --incremental 보다 우선.

Exit: 0 성공 / 1 부분오류 / 2 import 실패.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, "/app")


def main() -> int:
    ap = argparse.ArgumentParser(description="관계형 → AGE metadata_kb 그래프 동기화")
    ap.add_argument("--scope", default=None, help="특정 scope_key 만 동기화 (기본: 전체 scope)")
    ap.add_argument("--quiet", action="store_true", help="telemetry JSON 출력 생략")
    ap.add_argument("--incremental", action="store_true",
                    help="변경분(updated_at > 워터마크)만 동기화 (부하 절감)")
    ap.add_argument("--full", action="store_true",
                    help="전량 동기화(워터마크 무시 — 삭제/파단 반영). --incremental 보다 우선")
    args = ap.parse_args()

    try:
        from modules import metadata_graph as mg
    except Exception as exc:  # pragma: no cover - 환경 의존
        print(json.dumps({"ok": False, "error": f"import failed: {exc!r}"}, ensure_ascii=False))
        return 2

    # incremental 결정: --full 최우선(강제 전량), 아니면 --incremental 또는 env 토글.
    env_inc = os.getenv("AGENT_METADATA_GRAPH_SYNC_INCREMENTAL", "0").strip().lower() in (
        "1", "true", "yes", "on")
    incremental = (not args.full) and (args.incremental or env_inc)
    since = mg.get_sync_watermark(args.scope) if incremental else None

    rep = mg.sync_graph(scope_key=args.scope, since=since)
    rep["ok"] = int(rep.get("errors", 0)) == 0
    # 성공 시 워터마크 전진(다음 --incremental 의 since). full·incremental 모두 저장 — full 후 증분 전환 대비.
    if rep["ok"] and rep.get("synced_at"):
        mg.set_sync_watermark(rep["synced_at"], scope_key=args.scope)
    if not args.quiet:
        print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
