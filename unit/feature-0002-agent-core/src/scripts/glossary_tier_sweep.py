#!/usr/bin/env python3
"""용어사전 소급 정리 — 범용 용어 회수 + 표기변형/교차 scope 중복 병합 (0057).

## 무엇을 고치나

`term_tier` 축이 생기기 전(2026-09-01 이전)에 등록된 행은 **전부 제품 scope**에 있다. 그중
상당수가 범용 RDBMS 지식이고, 같은 개념이 제품마다·표기마다 흩어져 있다. 라이브 실측:

    kb_glossary 732행 / 고유 692 · 34개 용어가 2~4 scope · `멱등성` 한 개념이 7행(4 scope)

이 스크립트는 그 잔재를 세 갈래로 정리한다:

| 분류 | 판정 | 조치 |
|---|---|---|
| `general` | `kb_glossary.classify_term_tier` 결정적 목록·SQL 키워드 | `source='auto'` 행 삭제 + 큐에 `skipped_general` 기록 |
| `duplicate` | 정규화 표면형이 같은 행이 2개 이상 | 대표 1행만 남기고 나머지 `source='auto'` 삭제 |
| `keep` | 그 외 | 손대지 않음 (`term_tier='product'` 유지) |

## 안전 계약 (파괴적 스크립트 — 이 절이 계약이다)

- **기본이 dry-run 이다.** 실제 변경은 `--apply` 를 명시해야 일어난다.
- **`source='manual'` 행은 절대 건드리지 않는다.** 사람이 큐레이션한 것은 이 스크립트의
  판정보다 우선한다 — 자동 판정으로 사람의 결정을 뒤집지 않는다.
- **삭제 전에 되돌리기 매니페스트를 쓴다** (`--manifest`). 삭제된 행 전체(정의 포함)를 JSON
  으로 남기므로 `--restore <manifest>` 로 되돌릴 수 있다. 매니페스트를 못 쓰면 **삭제하지
  않는다** (fail-closed — 되돌릴 수 없는 삭제를 만들지 않는다).
- **중복 병합의 대표 선정은 결정적이다**: manual > 전역(common) > 정의가 긴 것 > id 작은 것.
  무작위·타임스탬프 의존이면 두 번 돌릴 때 다른 행이 살아남는다.
- **삭제된 general 용어는 큐에 남는다** (`glossary_feedback.status='skipped_general'`).
  관리자가 콘솔에서 보고 「그래도 등록」으로 되살릴 수 있다.

## 사용법

    # 1) 무엇이 바뀌는지 본다 (변경 없음)
    python3 src/scripts/glossary_tier_sweep.py

    # 2) 특정 scope 만
    python3 src/scripts/glossary_tier_sweep.py --scope product.gz_qa_g

    # 3) 실제 적용 (매니페스트 필수)
    python3 src/scripts/glossary_tier_sweep.py --apply --manifest /tmp/gloss-sweep.json

    # 4) 되돌리기
    python3 src/scripts/glossary_tier_sweep.py --restore /tmp/gloss-sweep.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from modules import kb_glossary as kg  # noqa: E402


def _connect():
    from shared.db import _pg_connect
    return _pg_connect(autocommit=False)


def _fetch(conn, scope_filter):
    """정리 대상 행. `source='manual'` 은 애초에 가져오지 않는다 — 판정 실수의 여지를 없앤다."""
    clauses = ["source <> 'manual'"]
    params: list = []
    if scope_filter:
        clauses.append("scope_key = %s")
        params.append(scope_filter)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, scope_key, role_key, term, definition, source, term_tier "
            "FROM kb_glossary WHERE " + " AND ".join(clauses) + " ORDER BY id",
            tuple(params),
        )
        return [
            {"id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
             "term": str(r[3] or ""), "definition": str(r[4] or ""),
             "source": str(r[5] or ""), "term_tier": str(r[6] or "product")}
            for r in (cur.fetchall() or [])
        ]
    finally:
        cur.close()


def _pick_survivor(rows):
    """중복 그룹의 대표 1행. **결정적** — 같은 입력이면 언제나 같은 행이 살아남는다.

    우선순위: ① 정의가 긴 것(정보량) ② id 작은 것(먼저 등록된 것).
    (`manual` 은 `_fetch` 가 이미 제외했으므로 여기 오지 않는다.)
    """
    return sorted(rows, key=lambda r: (-len(r["definition"]), r["id"]))[0]


def plan(rows):
    """정리 계획 산출 — 순수 함수(DB 무접촉).

    반환: `{"general": [...], "duplicate": [...], "cross_scope": [...]}`
    (`cross_scope` 는 **보고 전용** — 삭제 대상이 아니다).

    ## 세 갈래로 나누는 이유 — 교차 제품 병합은 삭제가 아니라 **데이터 손실**이다

    초판은 정규화 표면형이 같으면 scope 를 넘어 하나로 합쳤다. 라이브 dry-run 이 그것이
    틀렸음을 즉시 보여 줬다:

        [product.dk_dev] SponsorCode  →  대표 [product.gz_dev] SponsorCode

    읽기 캐스케이드는 `[그 제품, common]` 이다 — **한 제품은 다른 제품의 scope 를 읽지
    않는다.** 그러니 `dk_dev` 행을 지우고 `gz_dev` 를 대표로 남기면 `dk_dev` 대화에서 그
    용어는 **그냥 사라진다.** 게다가 같은 이름이 제품마다 다른 뜻일 수 있다(`CharacterID`·
    `AID`·`LogType` 이 실제로 그렇다) — 이름이 같다는 것은 같은 개념이라는 증거가 아니다.

    그래서 삭제는 **읽기 경로가 보장될 때만** 한다:

    | 분류 | 조건 | 조치 |
    |---|---|---|
    | `general` | 범용 RDBMS 지식 | 삭제 (어느 제품에도 남길 이유가 없다) |
    | `duplicate` | **같은 scope** 안의 표기변형 · 또는 `common` 에 같은 표면형 존재 | 삭제 (대표를 그 scope 또는 전역이 읽는다) |
    | `cross_scope` | 서로 다른 제품 scope 에 같은 표면형 | **보고만** — 사람이 보고 전역으로 올릴지 정한다 |

    판정 순서: **general 이 먼저**다. 범용 용어는 어느 대표를 고르든 남길 이유가 없으므로,
    중복 병합으로 하나를 살려 두면 그 하나가 계속 프롬프트에 실린다.
    """
    general: list = []
    remaining: list = []
    for r in rows:
        tier, reason = kg.classify_term_tier(r["term"], r["term_tier"])
        if tier == kg.TIER_GENERAL:
            general.append({**r, "reason": reason})
        else:
            remaining.append(r)

    # 전역(common)에 이미 있는 표면형 — 그 제품 행은 캐스케이드가 덮으므로 지워도 읽힌다.
    global_surface = {
        (kg.normalize_term_surface(r["term"]), r["role_key"]): r
        for r in remaining if r["scope_key"] == kg.GLOBAL_SCOPE
    }

    scoped: "defaultdict[tuple, list]" = defaultdict(list)
    for r in remaining:
        scoped[(kg.normalize_term_surface(r["term"]), r["role_key"], r["scope_key"])].append(r)

    duplicate: list = []
    survivors: list = []
    for (surface, role, scope), grp in scoped.items():
        gl = global_surface.get((surface, role))
        if gl is not None and scope != kg.GLOBAL_SCOPE:
            # 전역이 덮는다 — 이 scope 의 행 **전부** 제거 대상.
            for r in grp:
                duplicate.append({**r, "survivor_id": gl["id"],
                                  "survivor_scope": gl["scope_key"],
                                  "survivor_term": gl["term"], "rule": "covered-by-global"})
            continue
        survivor = _pick_survivor(grp)
        survivors.append(survivor)
        for r in grp:
            if r["id"] != survivor["id"]:
                duplicate.append({**r, "survivor_id": survivor["id"],
                                  "survivor_scope": survivor["scope_key"],
                                  "survivor_term": survivor["term"], "rule": "same-scope-variant"})

    # 보고 전용 — 살아남은 행 중 표면형이 여러 제품에 걸친 것.
    by_surface: "defaultdict[tuple, list]" = defaultdict(list)
    for r in survivors:
        by_surface[(kg.normalize_term_surface(r["term"]), r["role_key"])].append(r)
    cross_scope = [
        {"surface": k[0], "role_key": k[1],
         "rows": [{"id": r["id"], "scope_key": r["scope_key"], "term": r["term"]} for r in grp]}
        for k, grp in by_surface.items() if len(grp) > 1
    ]
    cross_scope.sort(key=lambda c: (-len(c["rows"]), c["surface"]))
    return {"general": general, "duplicate": duplicate, "cross_scope": cross_scope}


def _delete_rows(conn, rows):
    if not rows:
        return 0
    cur = conn.cursor()
    try:
        # `source <> 'manual'` 을 **여기서 다시** 건다. `_fetch` 이후 사람이 편집했다면 그
        # 편집이 이 삭제를 이겨야 한다(읽은 시점과 지우는 시점 사이의 창).
        cur.execute("DELETE FROM kb_glossary WHERE id = ANY(%s) AND source <> 'manual'",
                    ([r["id"] for r in rows],))
        return int(cur.rowcount or 0)
    finally:
        cur.close()


def _queue_general(conn, rows):
    """삭제한 범용 용어를 큐에 `skipped_general` 로 남긴다 — 조용한 삭제를 만들지 않는다."""
    n = 0
    for r in rows:
        try:
            ok = kg.record_glossary_suggestion(
                conn, kg.GLOBAL_SCOPE, r["role_key"], r["term"], r["definition"],
                confidence=0.0, status=kg.STATUS_SKIPPED_GENERAL,
                approved_by=f"sweep:{r.get('reason', 'lexicon')}", term_tier=kg.TIER_GENERAL,
            )
            n += 1 if ok else 0
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 큐 기록 실패 term={r['term']!r}: {exc}", file=sys.stderr)
    return n


def _write_manifest(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def restore(conn, manifest_path):
    """매니페스트의 행을 되돌린다(id 는 새로 부여된다 — 참조가 아니라 내용을 복원한다)."""
    with open(manifest_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = (payload.get("general") or []) + (payload.get("duplicate") or [])
    n = 0
    for r in rows:
        try:
            kg.upsert_glossary_term(
                conn, r["scope_key"], r["term"], r["definition"],
                role_key=r.get("role_key") or "*", source=r.get("source") or "auto",
                term_tier=r.get("term_tier") or kg.TIER_PRODUCT,
            )
            n += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 복원 실패 term={r.get('term')!r}: {exc}", file=sys.stderr)
    conn.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", default=None, help="특정 scope_key 만 (기본: 전체)")
    ap.add_argument("--apply", action="store_true", help="실제 적용 (기본: dry-run)")
    ap.add_argument("--manifest", default=None, help="되돌리기 매니페스트 경로 (--apply 시 필수)")
    ap.add_argument("--restore", default=None, help="매니페스트로 되돌리기")
    ap.add_argument("--limit-print", type=int, default=40, help="목록 출력 상한")
    args = ap.parse_args()

    conn = _connect()
    try:
        if args.restore:
            n = restore(conn, args.restore)
            print(f"복원 {n}건 (매니페스트 {args.restore})")
            return 0

        rows = _fetch(conn, args.scope)
        result = plan(rows)
        gen, dup, cross = result["general"], result["duplicate"], result["cross_scope"]

        print(f"대상 스캔 {len(rows)}행 (source<>'manual'"
              + (f", scope={args.scope}" if args.scope else "") + ")")
        print(f"  범용 판정  : {len(gen)}행 삭제 예정")
        for r in gen[:args.limit_print]:
            print(f"    - [{r['scope_key']}] {r['term']}  ({r['reason']})")
        if len(gen) > args.limit_print:
            print(f"    … 외 {len(gen) - args.limit_print}행")
        print(f"  중복 병합  : {len(dup)}행 삭제 예정 (같은 scope 표기변형 · 전역이 덮는 행)")
        for r in dup[:args.limit_print]:
            print(f"    - [{r['scope_key']}] {r['term']} → 대표 id={r['survivor_id']} "
                  f"[{r['survivor_scope']}] {r['survivor_term']}  ({r['rule']})")
        if len(dup) > args.limit_print:
            print(f"    … 외 {len(dup) - args.limit_print}행")
        # 삭제하지 않는다 — 제품이 서로의 scope 를 읽지 않으므로 병합은 곧 소실이다.
        print(f"  교차 제품  : {len(cross)}개 표면형 (삭제 안 함 — 검토용)")
        for c in cross[:args.limit_print]:
            locs = " · ".join(f"[{r['scope_key']}] {r['term']}" for r in c["rows"])
            print(f"    ? {c['surface']}: {locs}")
        if len(cross) > args.limit_print:
            print(f"    … 외 {len(cross) - args.limit_print}개")

        if not args.apply:
            print("\n(dry-run — 변경 없음. 적용하려면 --apply --manifest <path>)")
            return 0

        if not args.manifest:
            print("\n[중단] --apply 에는 --manifest 가 필요합니다 — 되돌릴 수 없는 삭제를 "
                  "만들지 않습니다.", file=sys.stderr)
            return 2
        try:
            _write_manifest(args.manifest, result)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[중단] 매니페스트를 쓸 수 없습니다({exc}) — 삭제하지 않습니다.",
                  file=sys.stderr)
            return 2

        queued = _queue_general(conn, gen)
        d1 = _delete_rows(conn, gen)
        d2 = _delete_rows(conn, dup)
        conn.commit()
        print(f"\n적용 완료 — 범용 삭제 {d1}행(큐 기록 {queued}) · 중복 삭제 {d2}행")
        print(f"매니페스트: {args.manifest}  (되돌리기: --restore {args.manifest})")
        return 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
