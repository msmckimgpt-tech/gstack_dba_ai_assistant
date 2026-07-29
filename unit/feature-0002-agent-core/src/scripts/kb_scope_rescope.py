"""metadata-product-scope — KB 메타데이터 scope 축을 datasource → **제품** 으로 정리하는 운영 스크립트.

배경: 관리 콘솔 > 지식베이스 > 메타데이터의 scope 축이 datasource 였는데, 사용자·메타데이터
관리자가 인식하는 작업 범위는 제품이다. 라이브에서 축이 양방향으로 어긋나 있었다 —
1제품↔N데이터소스(KR_LIVE·KR_QA 각 7개 DS)에서는 등록분이 그 중 1개 DS 질의에서만 주입되고,
1데이터소스↔N제품(mssql-qa-idc 를 5개 제품이 공유)에서는 타 제품 메타데이터가 혼입됐다.
코드는 이미 제품 축(`product.<ProductKey>`)으로 전환됐고, 본 스크립트는 **기존 행**을 정리한다.

대상 테이블(agent_kb / PG) — 같은 scope 축을 쓰는 7개:
  등록분: kb_glossary · enum_dictionary · table_descriptions · column_descriptions · sample_queries
  검토 큐: glossary_feedback · enum_feedback · sample_feedback
           (빠뜨리면 이관 후 pending 큐가 콘솔에서 사라지고 승급도 옛 scope 로 들어간다)
`scope_key='common'`(공용 사전)은 어느 모드에서도 손대지 않는다.

귀속 규칙(assess/migrate 공통):
  1. 그 datasource 를 쓰는 제품이 **정확히 1개** → 그 제품으로 귀속(결정론적).
  2. 공유 datasource + 행에 `schema_name` 있음 → `WebProductDatabases`(제품별 접근DB SSOT)로
     schema → 제품 조회. 소유 제품이 정확히 1개면 귀속.
  3. 그 외(공유 DS + schema 없음/다중 소유) → **모호**. migrate 는 건드리지 않는다.

모드:
  --assess            판정만 출력(기본, 무변경).
  --backup <path>     대상 행 전체를 JSONL 로 덤프(복구용). mutate 모드는 이 덤프를 **강제**한다.
  --migrate           규칙 1·2 로 귀속 가능한 행의 scope_key 를 제품 스코프로 재작성.
  --purge-ambiguous   규칙 3(모호) 잔여 행 삭제.
  --purge-all         common 을 제외한 **모든** 비-제품 scope 행 삭제(사용자 명시 결정 시).
  --apply             실제 실행. 없으면 dry-run(무변경).
  --verify-contract   잔여 레거시(비-제품·비-common) 행 수를 보고. 0 이면 contract 가능.

expand/contract 순서 (배포↔이관은 원자적일 수 없다):
  1. **expand 배포** — 새 코드는 `AGENT_KB_LEGACY_DS_SCOPE_READ=1`(기본)로 제품 스코프 + 레거시
     datasource 스코프를 함께 읽는다. 이 창의 동작은 종전과 동일하며 메타데이터가 사라지지 않는다.
  2. **이관** — `--migrate --purge-ambiguous --backup <path> --apply`.
  3. **검증** — `--verify-contract` 가 0 건이어야 한다.
  4. **contract** — `AGENT_KB_LEGACY_DS_SCOPE_READ=0` 설정 후 web/워커 재기동. 이 단계를 빠뜨리면
     레거시 꼬리가 계속 읽혀 공유 datasource 의 타 제품 혼입이 남는다.

Usage (agent 컨테이너):
    docker exec repo-agent-1 python -m scripts.kb_scope_rescope --assess
    docker exec repo-agent-1 python -m scripts.kb_scope_rescope --migrate --backup /shared/kb-scope-backup.jsonl --apply
    docker exec repo-agent-1 python -m scripts.kb_scope_rescope --purge-all --backup /shared/kb-scope-backup.jsonl --apply
"""
from __future__ import annotations

import argparse
import json
import sys

# (테이블, schema_name 컬럼 보유 여부) — schema 기반 귀속(규칙 2)이 가능한지 결정한다.
# 검토 큐(glossary_feedback / enum_feedback)도 같은 scope 축이라 함께 이관한다 — 빠뜨리면
# 이관 후 콘솔이 제품 스코프만 조회하므로 **기존 pending 큐가 통째로 사라지고**, 그 행을 직접
# promote 해도 옛 datasource scope 로 등록돼 제품 질의에 주입되지 않는다.
_TABLES = (
    ("kb_glossary", False),
    ("enum_dictionary", True),
    ("table_descriptions", True),
    ("column_descriptions", True),
    ("sample_queries", False),
    ("glossary_feedback", False),
    ("enum_feedback", True),
    ("sample_feedback", False),
)

_COMMON = "common"


def _connect_mem():
    """agent_memory(MySQL) — 제품/접근DB/datasource 레지스트리 조회용."""
    import agent_core  # type: ignore
    return agent_core._connect_memory()


def _connect_kb():
    """agent_kb(PG) — KB 메타데이터 저장소."""
    from shared.db import _pg_connect
    return _pg_connect(autocommit=False)


def _build_maps(mem_conn):
    """(scope→제품들, (scope,schema소문자)→제품들, 제품키→제품스코프) 3종 매핑.

    scope 해소는 질의 시점 read 축과 동일한 `ds.get('scope_key') or 라벨` 을 쓴다
    (`_dsr.scope_key` 는 .env ds 에서 해시를 *계산*해 read 축과 어긋나므로 금지 — 기존 계약).
    """
    from shared import config as cfg
    from shared import datasources as dsr

    ds_scope: dict[str, str] = {}
    for label, ds in (dsr.all_datasources(mem_conn) or {}).items():
        sk = str((ds.get("scope_key") or ds.get("key") or label) or "").strip().lower()
        if sk:
            ds_scope[str(label).strip().lower()] = sk

    # 제품/바인딩은 SQL 로 직접 읽는다 — `_list_products` 는 web(feature-0003) 소유라 core 스크립트가
    # 의존하면 cross-unit import 가 생긴다(agent 컨테이너에는 web 코드가 없다).
    pkey_by_id: dict[int, str] = {}
    cur = mem_conn.cursor()
    try:
        cur.execute("SELECT Id, ProductKey FROM WebProducts WHERE IsActive = 1")
        for row in (cur.fetchall() or []):
            pid, pkey = (row[0], row[1]) if not isinstance(row, dict) else (row.get("Id"), row.get("ProductKey"))
            pid = int(pid or 0)
            pkey = str(pkey or "").strip()
            if pid > 0 and pkey:
                pkey_by_id[pid] = pkey
    finally:
        cur.close()

    scope_products: dict[str, set] = {}
    cur = mem_conn.cursor()
    try:
        # 1:N 바인딩(WebProductDatasources) + 하위호환 단일 바인딩(WebProducts.DatasourceKey) 합집합.
        cur.execute("SELECT ProductId, LOWER(DatasourceKey) FROM WebProductDatasources")
        pairs = [(r[0], r[1]) if not isinstance(r, dict) else (r.get("ProductId"), r.get("DatasourceKey"))
                 for r in (cur.fetchall() or [])]
    except Exception:
        pairs = []
    finally:
        cur.close()
    cur = mem_conn.cursor()
    try:
        cur.execute("SELECT Id, LOWER(DatasourceKey) FROM WebProducts WHERE DatasourceKey IS NOT NULL")
        pairs += [(r[0], r[1]) if not isinstance(r, dict) else (r.get("Id"), r.get("DatasourceKey"))
                  for r in (cur.fetchall() or [])]
    finally:
        cur.close()
    for pid, dsk in pairs:
        pkey = pkey_by_id.get(int(pid or 0))
        dsk = str(dsk or "").strip().lower()
        if not pkey or not dsk:
            continue
        scope_products.setdefault(ds_scope.get(dsk, dsk), set()).add(pkey)

    schema_products: dict[tuple, set] = {}
    cur = mem_conn.cursor()
    try:
        cur.execute("SELECT ProductId, DatasourceKey, SchemaName FROM WebProductDatabases")
        for row in (cur.fetchall() or []):
            pid, dsk, sch = (row[0], row[1], row[2]) if not isinstance(row, dict) else (
                row.get("ProductId"), row.get("DatasourceKey"), row.get("SchemaName"))
            pkey = pkey_by_id.get(int(pid or 0))
            sch = str(sch or "").strip().lower()
            if not pkey or not sch:
                continue
            sk = ds_scope.get(str(dsk or "").strip().lower(), str(dsk or "").strip().lower())
            schema_products.setdefault((sk, sch), set()).add(pkey)
    finally:
        cur.close()

    product_scope = {pk: cfg.product_scope_key(pk) for pk in pkey_by_id.values()}
    return scope_products, schema_products, product_scope


def _classify(scope_key, schema_name, scope_products, schema_products):
    """행 1건의 귀속 판정 → (verdict, product_key|None).

    verdict: 'common' | 'already-product' | 'single' | 'schema' | 'ambiguous' | 'orphan'
    """
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == _COMMON:
        return "common", None
    if sk.startswith("product."):
        return "already-product", None
    owners = scope_products.get(sk)
    if not owners:
        return "orphan", None
    if len(owners) == 1:
        return "single", next(iter(owners))
    sch = str(schema_name or "").strip().lower()
    if sch:
        so = schema_products.get((sk, sch))
        if so and len(so) == 1:
            return "schema", next(iter(so))
    return "ambiguous", None


def _is_unique_violation(exc) -> bool:
    """예외가 PG unique violation(SQLSTATE 23505)인지. 드라이버 무관하게 sqlstate/pgcode 를 본다."""
    for attr in ("sqlstate", "pgcode"):
        code = getattr(exc, attr, None)
        if code is None:
            diag = getattr(exc, "diag", None)
            code = getattr(diag, "sqlstate", None) if diag is not None else None
        if str(code or "") == "23505":
            return True
    return False


def _iter_rows(kb_conn):
    """(table, has_schema, id, scope_key, schema_name) 스트림."""
    for table, has_schema in _TABLES:
        cols = "id, scope_key" + (", schema_name" if has_schema else "")
        cur = kb_conn.cursor()
        try:
            cur.execute(f"SELECT {cols} FROM {table} ORDER BY id")  # noqa: S608 — 상수 화이트리스트
            for row in (cur.fetchall() or []):
                yield table, has_schema, row[0], row[1], (row[2] if has_schema else None)
        finally:
            cur.close()


def _dump_backup(kb_conn, path, targets):
    """대상 행을 **전 컬럼** JSONL 로 덤프. 복구는 이 파일로 재INSERT 한다."""
    by_table: dict[str, list] = {}
    for table, _hs, rid, _sk, _sn in targets:
        by_table.setdefault(table, []).append(rid)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for table, ids in by_table.items():
            cur = kb_conn.cursor()
            try:
                cur.execute(f"SELECT * FROM {table} WHERE id = ANY(%s)", (ids,))  # noqa: S608
                colnames = [d[0] for d in cur.description]
                for row in (cur.fetchall() or []):
                    rec = {c: (v.isoformat() if hasattr(v, "isoformat") else v)
                           for c, v in zip(colnames, row)}
                    # embedding(vector) 등 비직렬화 값은 문자열화(복구 시 재계산 대상).
                    fh.write(json.dumps({"table": table, "row": rec}, ensure_ascii=False, default=str) + "\n")
                    n += 1
            finally:
                cur.close()
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KB 메타데이터 scope 축 datasource → 제품 정리")
    ap.add_argument("--assess", action="store_true", help="판정만 출력(기본)")
    ap.add_argument("--migrate", action="store_true", help="귀속 가능 행의 scope_key 를 제품 스코프로 재작성")
    ap.add_argument("--purge-ambiguous", action="store_true", help="모호 잔여 행 삭제")
    ap.add_argument("--purge-all", action="store_true", help="common 제외 전 비-제품 scope 행 삭제")
    ap.add_argument("--backup", default="", help="대상 행 JSONL 덤프 경로(mutate 모드 필수)")
    ap.add_argument("--apply", action="store_true", help="실제 실행(미지정 시 dry-run)")
    ap.add_argument("--verify-contract", action="store_true",
                    help="잔여 레거시 scope 행 수 보고(0 이면 AGENT_KB_LEGACY_DS_SCOPE_READ=0 안전)")
    args = ap.parse_args(argv)

    if args.verify_contract:
        kb = _connect_kb()
        try:
            leftover: dict = {}
            for table, has_schema in _TABLES:
                cur = kb.cursor()
                try:
                    cur.execute(f"SELECT count(*) FROM {table} "  # noqa: S608 — 상수 화이트리스트
                                "WHERE scope_key <> 'common' AND scope_key NOT LIKE 'product.%%'")
                    n = int((cur.fetchone() or [0])[0] or 0)
                finally:
                    cur.close()
                if n:
                    leftover[table] = n
            total = sum(leftover.values())
            print("== 잔여 레거시 scope 행 ==")
            for t, n in sorted(leftover.items(), key=lambda kv: -kv[1]):
                print(f"  {t:24} {n:>6}")
            print(f"  {'합계':24} {total:>6}")
            print("contract 가능(AGENT_KB_LEGACY_DS_SCOPE_READ=0)" if total == 0
                  else "contract 보류 — 잔여 행이 있어 플래그를 내리면 그 행이 안 보이게 된다")
            return 0 if total == 0 else 1
        finally:
            try:
                kb.close()
            except Exception:
                pass

    mutating = args.migrate or args.purge_ambiguous or args.purge_all
    if mutating and not args.backup:
        print("ERROR: mutate 모드는 --backup <path> 가 필수입니다 (되돌릴 수 없는 변경).", file=sys.stderr)
        return 2

    mem = _connect_mem()
    try:
        scope_products, schema_products, product_scope = _build_maps(mem)
    finally:
        try:
            mem.close()
        except Exception:
            pass

    kb = _connect_kb()
    try:
        rows = list(_iter_rows(kb))
        buckets: dict[str, list] = {}
        plan_update: list = []   # (table, id, new_scope)
        plan_delete: list = []   # (table, id)
        for table, has_schema, rid, sk, sn in rows:
            verdict, pkey = _classify(sk, sn, scope_products, schema_products)
            buckets.setdefault(verdict, []).append((table, sk, sn))
            if verdict in ("single", "schema"):
                new_scope = product_scope.get(pkey)
                if new_scope:
                    if args.migrate:
                        plan_update.append((table, rid, new_scope))
                    elif args.purge_all:
                        plan_delete.append((table, rid))
            elif verdict in ("ambiguous", "orphan"):
                if args.purge_ambiguous or args.purge_all:
                    plan_delete.append((table, rid))

        print("== 판정 요약 ==")
        for v in ("common", "already-product", "single", "schema", "ambiguous", "orphan"):
            items = buckets.get(v, [])
            if not items:
                continue
            print(f"  {v:16} {len(items):>6} 건")
        print(f"  {'합계':16} {len(rows):>6} 건")
        print()
        print(f"계획: update {len(plan_update)} 건 · delete {len(plan_delete)} 건 "
              f"({'APPLY' if args.apply else 'DRY-RUN'})")

        if not mutating or not args.apply:
            return 0

        targets = [(t, None, i, None, None) for (t, i, _s) in plan_update] + \
                  [(t, None, i, None, None) for (t, i) in plan_delete]
        n = _dump_backup(kb, args.backup, targets)
        print(f"백업 {n} 건 → {args.backup}")

        # 중복 UNIQUE 키 병합: 한 제품이 여러 datasource 를 쓰고 같은 용어/테이블/컬럼/코드가
        # 각 datasource 에 중복 등록돼 있으면, 하나의 product.* scope 로 모으는 순간 각 테이블의
        # UNIQUE 제약과 충돌한다. 단순 UPDATE 면 트랜잭션 전체가 실패해 이관이 멈추므로,
        # 행마다 SAVEPOINT 를 잡고 충돌 시 그 행을 **중복으로 판정해 삭제**한다(먼저 이관된 행이
        # 승자 — 백업 JSONL 에 원본이 남아 되돌릴 수 있다).
        merged = 0
        cur = kb.cursor()
        try:
            for table, rid, new_scope in plan_update:
                cur.execute("SAVEPOINT kb_rescope_row")
                try:
                    cur.execute(f"UPDATE {table} SET scope_key = %s WHERE id = %s",  # noqa: S608
                                (new_scope, rid))
                    cur.execute("RELEASE SAVEPOINT kb_rescope_row")
                except Exception as exc:
                    # **unique violation(23505) 에서만** 중복 병합으로 처리한다. 모든 예외를 중복으로
                    # 보면 연결 끊김·권한·타임아웃 같은 transient 오류에서도 원본 행을 지워
                    # 데이터가 영구 소실된다 — 그 외 예외는 재-raise 해 트랜잭션 전체를 롤백한다.
                    if _is_unique_violation(exc):
                        cur.execute("ROLLBACK TO SAVEPOINT kb_rescope_row")
                        cur.execute("RELEASE SAVEPOINT kb_rescope_row")
                        cur.execute(f"DELETE FROM {table} WHERE id = %s", (rid,))  # noqa: S608
                        merged += 1
                    else:
                        raise
            for table, rid in plan_delete:
                cur.execute(f"DELETE FROM {table} WHERE id = %s", (rid,))  # noqa: S608
        finally:
            cur.close()
        kb.commit()
        print(f"완료: update {len(plan_update) - merged} · merged(중복 삭제) {merged} · "
              f"delete {len(plan_delete)}")
        print("다음 단계: `--verify-contract` 로 잔여 0 확인 후 "
              "`AGENT_KB_LEGACY_DS_SCOPE_READ=0` 설정 + web/워커 재기동(contract). "
              "이 단계를 빠뜨리면 레거시 꼬리 읽기가 계속돼 타 제품 혼입이 남는다.")
        return 0
    except Exception:
        try:
            kb.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            kb.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
