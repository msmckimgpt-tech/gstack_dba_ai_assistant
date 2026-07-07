"""feature-0016 routine-dbanalysis(§53): 함수·프로시저 introspect **전 datasource 결정론 backfill**.

insight-worker 의 cadence(6h)+rotation 은 funcproc 배포 후 커버리지가 점진 전파되어, routine 을
보유한 datasource 라도 그래프에 ƒ/⚙ 노드가 며칠간 비어 보일 수 있다(사용자 보고 재현: 20개 ds 중
4개만 적재). 본 드라이버는 등록된 전 datasource 를 즉시 순회해 routines.introspect_and_store 를
호출하고 scope 별 sync_graph 로 AGE 에 투영한다 — per-(ds, DB, schema) 카운트/에러를 loud 리포트.

규약 (insight 훅과 동일):
  - MySQL: 비시스템 ROUTINE_SCHEMA 별 introspect, store_schema=schema.
  - MSSQL: 사용자 DB 별 연결(list_server_databases) 후 ROUTINE_SCHEMA 별 introspect,
    store_schema=DB명 (스키마-slot 규약 ADR-007). 한 DB(=store label)에 복수 ROUTINE_SCHEMA 가
    공존하면 prune=False (뒤 스키마의 prune 이 앞 스키마 행을 지우는 결함 차단 — §53).
  - 운영 DB 는 read-only 조회만(information_schema). 쓰기는 agent_kb PG upsert 뿐.
  - 개별 (ds, DB, schema) 실패는 리포트에 남기고 계속(비차단).

실행: bin/routine-backfill.sh (컨테이너 exec 래퍼) 또는
  python -m modules.routine_backfill [--scope <ds>] [--dry-run] [--cap N] [--include-disabled]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

_log = logging.getLogger("routine_backfill")

_MYSQL_SYSTEM_SCHEMAS = {"mysql", "sys", "information_schema", "performance_schema"}
_MSSQL_SYSTEM_DBS = {"master", "model", "msdb", "tempdb", "distribution", "reportservertempdb"}


def _routine_schemas(conn) -> list:
    """현재 연결에서 routine 이 존재하는 스키마 목록(information_schema.ROUTINES 기준)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT ROUTINE_SCHEMA FROM information_schema.ROUTINES")
        return sorted({str(r[0] or "").strip() for r in (cur.fetchall() or []) if r and r[0]})
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _base_tables(conn, schema=None) -> list:
    """BASE TABLE 이름 목록 — schema 지정 시 그 스키마만, 미지정 시 연결 DB 전체(MSSQL per-DB)."""
    cur = conn.cursor()
    try:
        if schema is None:
            cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                        "WHERE TABLE_TYPE = 'BASE TABLE'")
        else:
            cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                        "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = %s", (schema,))
        return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _close(conn) -> None:
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def run(scope_filter=None, dry_run=False, cap=None, include_disabled=False) -> dict:
    """전 datasource routine backfill. 반환 리포트(dict) — 실패는 errors 에 loud."""
    from shared.db import connect, list_server_databases
    from shared import datasources as _dsm
    from modules import routines as _routines
    from modules import metadata_graph as _mg

    report = {"datasources": {}, "stored_total": 0, "errors": []}
    # 안전 가드: 멀티 datasource 플래그 OFF 면 connect(datasource=)가 **기본(primary) DB 로 폴백**해
    # 엉뚱한 DB 를 ds 키로 라벨링한다 — fail-loud 로 전량 차단.
    try:
        from shared import config as _cfg
        if not getattr(_cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False):
            report["errors"].append("AGENT_MULTI_DATASOURCE_ENABLED=0 — datasource 직결이 비활성이라 backfill 을 수행할 수 없습니다.")
            return report
    except Exception as exc:
        report["errors"].append(f"config 확인 실패: {exc!r}")
        return report
    mem_conn = None
    try:
        # 레지스트리 정본 = agent_kb(MEMORY_DB) 의 WebDatasources — DB 미지정 connect() 는
        # default DB 미선택 연결이 되어 _all_db_datasources 가 조용히 {} 를 반환(§18.8 BLOCKING).
        # insight worker 정본 호출(insight.py connect_with_retry(database=MEMORY_DB))과 동일 규약.
        mem_conn = connect(database=_cfg.MEMORY_DB)
        ds_map = _dsm.all_datasources(mem_conn) or {}
    except Exception as exc:
        report["errors"].append(f"datasource 목록 조회 실패: {exc!r}")
        return report
    finally:
        _close(mem_conn)

    for key in sorted(ds_map.keys()):
        ds = ds_map[key]
        # §56 RC4(read-axis 정규화, ADR-014 규약): SSOT/그래프 키는 **read 축 scope**(DB-등록=
        # 엔드포인트 해시 ds.scope_key, .env 레거시=라벨 lower)여야 한다. 종전엔 registry 라벨
        # key('mssql-dk-dev')를 그대로 scope_key/datasource_key/sync_graph 에 써서 (a) insight
        # cadence(해시 scope)와 **이중 적재**(라이브 실측: dk-dev 1,449행 × 2키) (b) 존재하지 않는
        # label 스코프에 그래프 고아 투영 (c) RC2 external_tables 의 rag 조회(해시 키) 불일치로
        # 크로스-DB 검증 무력화가 발생했다.
        scope = str(ds.get("scope_key") or key).strip().lower()
        if scope_filter and scope_filter not in (key, scope):
            continue
        # TASK-0215 parity: 운영자가 insight 탐색을 끈 datasource 는 worker 와 동일하게 순회 제외
        # (비활성 사유가 부하/민감성일 수 있음) — 명시 --include-disabled 시에만 포함.
        if not include_disabled and ds and ds.get("insight_enabled") is False:
            report["datasources"][key] = {"skipped": "insight_enabled=0 (--include-disabled 로 강제 가능)"}
            continue
        engine = str(ds.get("engine") or "").strip().lower()
        entry = {"engine": engine, "scope": scope, "schemas": {}, "stored": 0}
        report["datasources"][key] = entry
        try:
            if engine.startswith("mssql"):
                try:
                    dbs = [d for d in (list_server_databases(ds) or [])
                           if str(d).strip().lower() not in _MSSQL_SYSTEM_DBS]
                except Exception as exc:
                    report["errors"].append(f"{key}: DB 목록 조회 실패: {exc!r}")
                    continue
                for dbname in dbs:
                    conn = None
                    try:
                        conn = connect(database=dbname, datasource=ds)
                        schemas = _routine_schemas(conn)
                        if not schemas:
                            continue
                        tables = _base_tables(conn)   # 참조 파싱 입력 — DB 전체(스키마 무관 leaf 매칭)
                        multi = len(schemas) > 1      # §53 prune-safety: label(DB명) 공유 시 prune 억제
                        for sch in schemas:
                            slot = f"{dbname}//{sch}"
                            if dry_run:
                                entry["schemas"][slot] = "(dry-run)"
                                continue
                            n = _routines.introspect_and_store(
                                conn, sch, tables, scope_key=scope, datasource_key=scope,
                                store_schema=dbname, cap=cap, prune=not multi)
                            entry["schemas"][slot] = int(n or 0)
                            entry["stored"] += int(n or 0)
                    except Exception as exc:
                        report["errors"].append(f"{key}/{dbname}: {exc!r}")
                    finally:
                        _close(conn)
            else:   # mysql 계열
                conn = None
                try:
                    conn = connect(datasource=ds)
                    schemas = [s for s in _routine_schemas(conn)
                               if s.lower() not in _MYSQL_SYSTEM_SCHEMAS]
                    for sch in schemas:
                        if dry_run:
                            entry["schemas"][sch] = "(dry-run)"
                            continue
                        tables = _base_tables(conn, schema=sch)
                        n = _routines.introspect_and_store(
                            conn, sch, tables, scope_key=scope, datasource_key=scope,
                            store_schema=sch, cap=cap, prune=True)
                        entry["schemas"][sch] = int(n or 0)
                        entry["stored"] += int(n or 0)
                except Exception as exc:
                    report["errors"].append(f"{key}: {exc!r}")
                finally:
                    _close(conn)
            report["stored_total"] += entry["stored"]
            # scope 별 그래프 투영 — 변경분 upsert(멱등). dry-run 은 skip.
            if not dry_run and entry["stored"] > 0:
                try:
                    _mg.sync_graph(scope_key=scope)   # §56 RC4: read-axis scope 로 투영(label 고아 방지)
                    entry["graph_synced"] = True
                except Exception as exc:
                    report["errors"].append(f"{key}: sync_graph 실패: {exc!r}")
        except Exception as exc:
            report["errors"].append(f"{key}: {exc!r}")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="routine introspect 전 datasource backfill (§53)")
    ap.add_argument("--scope", default=None, help="특정 datasource key 만")
    ap.add_argument("--dry-run", action="store_true", help="대상 열거만(저장·sync 없음)")
    ap.add_argument("--cap", type=int, default=None, help="스키마당 routine 상한(기본 300)")
    ap.add_argument("--include-disabled", action="store_true",
                    help="insight_enabled=0 (운영자 비활성) datasource 도 포함")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    rep = run(scope_filter=args.scope, dry_run=args.dry_run, cap=args.cap,
              include_disabled=args.include_disabled)
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    return 1 if rep.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
