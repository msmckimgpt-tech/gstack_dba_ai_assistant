#!/usr/bin/env python
"""feature-0016 Phase 1c: 관계형 메타데이터 → Apache AGE `metadata_kb` 그래프 동기화 CLI.

워커 컨테이너(insight-worker/ask-worker) 안에서 실행:
    python /app/scripts/metadata_graph_sync.py [--scope KEY] [--quiet]

관계형 SSOT(table_descriptions·column_descriptions·table_relationships·kb_glossary·
glossary_relations)를 AGE 그래프로 멱등 투영한다(modules.metadata_graph.sync_graph).
AGE cutover(shared_preload_libraries='age') 이후에만 실효 — 그 전엔 sync_graph 가 graceful
no-op(errors 카운트, 비차단). bin/metadata-graph-sync.sh 가 본 스크립트를 docker exec 한다.

Exit: 0 성공 / 1 부분오류 / 2 import 실패.
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "/app")


def main() -> int:
    ap = argparse.ArgumentParser(description="관계형 → AGE metadata_kb 그래프 동기화")
    ap.add_argument("--scope", default=None, help="특정 scope_key 만 동기화 (기본: 전체 scope)")
    ap.add_argument("--quiet", action="store_true", help="telemetry JSON 출력 생략")
    args = ap.parse_args()

    try:
        from modules import metadata_graph as mg
    except Exception as exc:  # pragma: no cover - 환경 의존
        print(json.dumps({"ok": False, "error": f"import failed: {exc!r}"}, ensure_ascii=False))
        return 2

    rep = mg.sync_graph(scope_key=args.scope)
    rep["ok"] = int(rep.get("errors", 0)) == 0
    if not args.quiet:
        print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
