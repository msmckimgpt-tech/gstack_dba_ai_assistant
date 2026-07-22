#!/usr/bin/env python3
"""ENUM 코드사전 소급 grounding 정리 — 예방 게이트(AGENT_ENUM_SCHEMA_GROUNDING) 도입 전 이미
자동등록된 '환각' (schema, table) 항목을 회수하는 운영자용 1회성 유틸.

배경: 대화 자율수집(_enum_autopropose)이 LLM 이 답변 프로즈에서 뽑은 (schema, table, column) 을
그대로 신뢰해, 해당 datasource 에 실재하지 않는 DB/테이블(예: auth scope 에 없는 dbLog.Currency)
까지 enum_dictionary/enum_feedback 에 등록해 왔다. 신규 등록은 게이트가 차단하지만, 이미 쌓인
행은 본 스크립트로 정리한다.

판정 기준: 각 scope 의 실제 스키마 카탈로그(`table_insight` fact — agent 가 LLM 에 주입하는 grounding
정본)에 (schema, table) 이 존재하는지. 카탈로그가 미가용/빈 scope 는 **fail-open**(건드리지 않음).

동작:
  - 기본 = dry-run: 삭제/거부 대상만 집계·출력(변경 없음).
  - --execute: enum_dictionary 의 source='auto' 행 삭제 + enum_feedback pending/auto_promoted → rejected.
    (수동 큐레이션 source='manual' 은 보존, 감사 추적 유지.)
  - --scope KEY: 특정 scope 만. 미지정 시 enum 테이블에 존재하는 모든 scope.

실행(운영 — 반드시 agent 컨테이너 안, agent_kb PG 접근 가능 환경):
    python3 scripts/enum_grounding_sweep.py                 # dry-run, 전체 scope
    python3 scripts/enum_grounding_sweep.py --scope mysql-kr-an1-auth
    python3 scripts/enum_grounding_sweep.py --execute        # 실제 정리
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


def _distinct_scopes(pg) -> list:
    cur = pg.cursor()
    try:
        cur.execute(
            "SELECT scope_key FROM enum_dictionary "
            "UNION SELECT scope_key FROM enum_feedback ORDER BY 1"
        )
        return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
    finally:
        cur.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="ENUM 코드사전 소급 grounding 정리")
    ap.add_argument("--scope", default=None, help="특정 scope_key 만 (미지정=전체)")
    ap.add_argument("--execute", action="store_true", help="실제 정리(미지정=dry-run)")
    args = ap.parse_args()

    from shared import config as cfg
    from shared.db import _pg_available, _pg_connect
    from modules import kb_glossary as kg
    from modules.utils import FACT_SCOPE_COMMON
    import agent_core  # _enum_known_table_index (활성 datasource 카탈로그 인덱스)

    if not _pg_available():
        print("[sweep] agent_kb PG 미가용 — 중단", file=sys.stderr)
        return 2

    pg = _pg_connect(autocommit=False)
    try:
        scopes = [args.scope] if args.scope else _distinct_scopes(pg)
        if not scopes:
            print("[sweep] 정리할 scope 없음(enum 테이블 비어있음).")
            return 0

        dry_run = not args.execute
        print(f"[sweep] mode={'DRY-RUN' if dry_run else 'EXECUTE'} scopes={len(scopes)}")
        total_dict = total_fb = 0
        for scope in scopes:
            # 해당 scope 를 활성 datasource 로 설정해야 ds_fact_like 가 그 scope 의 카탈로그를 읽는다.
            # common scope 는 라이브에서 active datasource=None(글로벌 non-ds 카탈로그)로 grounding
            # 되므로 sweep 도 None 으로 맞춘다 — 문자열 "common" 을 datasource 키로 넘기면
            # `table_insight:ds:common:%` 를 오조회해 빈 카탈로그→오검출(정리 누락 + 운영자 오도).
            cfg.set_active_datasource(None if scope == FACT_SCOPE_COMMON else scope)
            try:
                known_idx = agent_core._enum_known_table_index()
            finally:
                cfg.set_active_datasource(None)
            if known_idx is None:
                print(f"  - {scope}: 카탈로그 미가용/빈 scope → skip (fail-open)")
                continue
            res = kg.sweep_ungrounded_enum(pg, scope, known_idx, dry_run=dry_run)
            ung = res["ungrounded"]
            if not ung:
                print(f"  - {scope}: grounded (정리 대상 없음, scanned={res['scanned']})")
                continue
            names = ", ".join(f"{u['schema_name'] or '∅'}.{u['table_name']}" for u in ung)
            if dry_run:
                print(f"  - {scope}: 정리대상 {len(ung)}건 [{names}] (dry-run — 미변경)")
            else:
                print(f"  - {scope}: 정리완료 dict_deleted={res['dict_deleted']} "
                      f"feedback_rejected={res['feedback_rejected']} [{names}]")
                total_dict += res["dict_deleted"]
                total_fb += res["feedback_rejected"]

        if not dry_run:
            pg.commit()
            print(f"[sweep] COMMIT — dict_deleted={total_dict} feedback_rejected={total_fb}")
        else:
            print("[sweep] dry-run 종료 — 실제 정리는 --execute")
        return 0
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            pg.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
