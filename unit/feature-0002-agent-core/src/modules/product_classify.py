"""feature-0016 §59: 미분류 스키마 → 제품 분류 **AI 제안**(승인 대기) 파이프라인 (ADR-025).

카테고리 밴드의 스키마→제품 매핑(WebProductDatabases)은 그래프 시각화 소스이자 **에이전트 데이터
접근 allowlist** 를 겸한다(admin_products 게이트) — 따라서 LLM 산출을 그 테이블에 직접 기록하지
않는다. 후보를 WebProductDatabasePending(RuleId NULL, Reason 'ai_suggest:<conf>')에 적재하고
사람이 제품 관리 화면에서 승인/거부한다(제안→승인 스테이징 — 기존 rule pending 파이프라인 재사용).

분류 신호: 스키마명 + 테이블명 표본(AGE) + node_analysis 요약(있으면) + 제품명/설명.
후보 화이트리스트 = **그 datasource 에 이미 연결된 제품**(WebProductDatasources)만 — 미연결 제품
제안은 접근면 확장이라 원천 배제. LLM 응답도 입력 스키마·제품 id 실재 검증 후에만 채택(환각 차단).

실행: insight-worker 데몬(AGENT_PRODUCT_CLASSIFY_AUTO, 기본 OFF — XDS 선례) 또는 수동
`python -m modules.product_classify [--dry-run]`.
"""
from __future__ import annotations

import json
import logging
import math
import re

from shared.config import (
    AGENT_PRODUCT_CLASSIFY_BATCH_MAX,
    AGENT_PRODUCT_CLASSIFY_MIN_CONF,
    MEMORY_DB,
)

_log = logging.getLogger("insight")

_REASON_PREFIX = "ai_suggest"
# 패널 MINOR: 제안 단계 방어심층 — 시스템/내부 스키마는 후보에서 원천 제외(엔진 무관 합집합,
#   승인 시점 excluded 검사의 상류 이중화). 이름 검증도 승인 계약(길이·주입 문자)을 미러.
_SYSTEM_SCHEMAS = {"master", "model", "msdb", "tempdb", "sys", "information_schema",
                   "performance_schema", "mysql", "agent_memory"}
_NAME_INJECT_RE = re.compile("[;'\"`\\\\]|\\s")
_NAME_MAX = 64   # WebProductDatabases.SchemaName VARCHAR(64)


def _products_by_datasource(mem_cur) -> "dict[str, list[dict]]":
    """datasource_key(lower) → 활성 제품 [{id,name,description}] (연결 제품 화이트리스트).

    N:M(WebProductDatasources) + 레거시 단일 컬럼(WebProducts.DatasourceKey) 모두 수용
    (_list_products 동형). 실패는 {} — 제안 0건으로 강등(비차단).
    """
    out: dict[str, list[dict]] = {}
    try:
        mem_cur.execute(
            "SELECT p.Id, p.Name, COALESCE(p.Description,''), LOWER(pd.DatasourceKey) "
            "FROM WebProducts p JOIN WebProductDatasources pd ON pd.ProductId = p.Id "
            "WHERE p.IsActive = 1")
        for pid, name, desc, dsk in (mem_cur.fetchall() or []):
            if dsk:
                out.setdefault(str(dsk), []).append(
                    {"id": int(pid), "name": str(name or ""), "description": str(desc or "")})
    except Exception as exc:
        _log.debug("product_classify products join failed: %r", exc)
    try:
        mem_cur.execute(
            "SELECT Id, Name, COALESCE(Description,''), LOWER(COALESCE(DatasourceKey,'')) "
            "FROM WebProducts WHERE IsActive = 1 AND COALESCE(DatasourceKey,'') <> ''")
        for pid, name, desc, dsk in (mem_cur.fetchall() or []):
            lst = out.setdefault(str(dsk), [])
            if not any(int(x["id"]) == int(pid) for x in lst):
                lst.append({"id": int(pid), "name": str(name or ""), "description": str(desc or "")})
    except Exception as exc:
        _log.debug("product_classify legacy products failed: %r", exc)
    return out


def _taken_schemas(mem_cur, dsk: str) -> "set[str]":
    """이미 매핑(WebProductDatabases)됐거나 승인 대기(Pending) 중인 스키마명(lower) — 재제안 제외."""
    taken: set[str] = set()
    for sql in (
        "SELECT LOWER(SchemaName) FROM WebProductDatabases WHERE LOWER(DatasourceKey)=%s",
        "SELECT LOWER(SchemaName) FROM WebProductDatabasePending WHERE LOWER(DatasourceKey)=%s",
    ):
        try:
            mem_cur.execute(sql, (dsk,))
            taken.update(str(r[0]) for r in (mem_cur.fetchall() or []) if r and r[0])
        except Exception as exc:
            _log.debug("product_classify taken query failed: %r", exc)
    return taken


def _schema_evidence(kb_conn, scope: str, schema: dict) -> dict:
    """스키마 1건의 분류 근거 — 테이블명 표본(≤12) + node_analysis 요약(있으면, ≤400자)."""
    from modules import metadata_graph as _mg
    from modules import node_analysis as _na
    skey = str(schema.get("key") or "")
    ev = {"name": str(schema.get("name") or ""), "table_count": schema.get("table_count"),
          "tables": [], "summary": ""}
    try:
        rows = _mg.schema_table_keys(scope, skey, limit=12, conn=kb_conn) or []
        ev["tables"] = [str((t.get("name") if isinstance(t, dict) else t) or "").split(".")[-1]
                        for t in rows][:12]
    except Exception:
        pass
    try:
        got = _na.get_node_analysis(scope, skey, conn=kb_conn) or {}
        a = got.get("analysis") or {}
        if isinstance(a, dict):
            ev["summary"] = str(a.get("summary") or "")[:400]
    except Exception:
        pass
    return ev


def run_classify_pass(kb_conn=None, mem_conn=None, *, dry_run: bool = False) -> dict:
    """미분류 스키마 분류 제안 1-pass. 반환 리포트 {datasources:{dsk:{scope,unmapped,suggested}}, suggested_total}.

    멱등: Pending UNIQUE(Product, Ds, Schema) + INSERT IGNORE + taken(매핑·대기) 선제 제외.
    실패는 datasource 단위 격리(errors 에 loud) — 데몬 루프를 죽이지 않는다.
    """
    from shared.db import connect_with_retry
    from shared import datasources as _dsr
    from modules import metadata_graph as _mg
    from modules.llm import llm_product_classify

    rep: dict = {"datasources": {}, "suggested_total": 0, "errors": [], "dry_run": bool(dry_run)}
    own_mem = False
    if mem_conn is None:
        try:
            mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
            own_mem = True
        except Exception as exc:
            rep["errors"].append(f"mem_conn: {exc!r}")
            return rep
    try:
        cur = mem_conn.cursor()
        prod_map = _products_by_datasource(cur)
        batch_left = max(1, int(AGENT_PRODUCT_CLASSIFY_BATCH_MAX))
        for dsk, products in sorted(prod_map.items()):
            if batch_left <= 0:
                break
            try:
                ds = None
                try:
                    ds = _dsr.resolve(mem_conn, dsk)
                except Exception:
                    ds = None
                scope = str((ds or {}).get("scope_key") or dsk).strip().lower()
                entry = {"scope": scope, "unmapped": 0, "suggested": 0}
                rep["datasources"][dsk] = entry
                nodes = (_mg.scope_schemas(scope, conn=kb_conn) or {}).get("nodes") or []
                taken = _taken_schemas(cur, dsk)
                taken |= {str(MEMORY_DB or "").strip().lower()}

                def _cand(n):
                    nm = str(n.get("name") or "").strip()
                    low = nm.lower()
                    return (nm and low not in taken and low not in _SYSTEM_SCHEMAS
                            and len(nm) <= _NAME_MAX and not _NAME_INJECT_RE.search(nm))
                unmapped = [n for n in nodes if _cand(n)]
                entry["unmapped"] = len(unmapped)
                if not unmapped:
                    continue
                # 패널 MAJOR(기아 방지): pass 예산을 datasource 간 공정 배분 — 앞순위 ds 의 '분류
                #   불가 잔류물'이 전체 예산을 독식해 뒤 ds 가 영구 미스캔되는 것을 차단.
                per_ds = max(3, int(AGENT_PRODUCT_CLASSIFY_BATCH_MAX) // max(1, len(prod_map)))
                unmapped = unmapped[:min(per_ds, batch_left)]
                batch_left -= len(unmapped)
                payload = {
                    "task": "classify_schemas_to_products",
                    "datasource": dsk,
                    "products": [{"id": p["id"], "name": p["name"],
                                  "description": p["description"][:300]} for p in products],
                    "schemas": [_schema_evidence(kb_conn, scope, n) for n in unmapped],
                }
                # 0047: target 은 표시용 datasource 라벨(dsk), scope 는 콘솔 스코프 선택 키.
                obj = llm_product_classify(payload, scope_key=scope)
                if not isinstance(obj, dict):
                    continue
                valid_pid = {int(p["id"]) for p in products}
                by_name = {str(n.get("name") or "").strip().lower(): str(n.get("name") or "").strip()
                           for n in unmapped}
                best: dict[str, tuple] = {}   # schema_lower -> (conf, pid, reason)
                for s in (obj.get("suggestions") or []):
                    try:
                        sname = str((s or {}).get("schema") or "").strip().lower()
                        pid = int((s or {}).get("product_id") or 0)
                        conf = float((s or {}).get("confidence") or 0.0)
                    except (TypeError, ValueError):
                        continue
                    # 환각 차단: 입력 스키마·화이트리스트 제품만, 임계 이상만. 패널 MAJOR:
                    #   json.loads 는 NaN/Infinity 리터럴을 수용하고 NaN 은 < 비교가 항상 False 라
                    #   임계를 우회한다 — 유한성 + (0,1] 범위 밖 폐기.
                    if sname not in by_name or pid not in valid_pid:
                        continue
                    if not math.isfinite(conf) or conf <= 0.0 or conf > 1.0:
                        continue
                    if conf < float(AGENT_PRODUCT_CLASSIFY_MIN_CONF):
                        continue
                    if sname not in best or conf > best[sname][0]:
                        best[sname] = (conf, pid, str((s or {}).get("reason") or "")[:120])
                for sname, (conf, pid, reason) in best.items():
                    if dry_run:
                        entry["suggested"] += 1
                        continue
                    # 패널 NIT: 분류 근거를 Reason 에 동봉(승인자 판단 근거 — UI 툴팁).
                    r1 = " ".join(str(reason or "").split())
                    cur.execute(
                        "INSERT IGNORE INTO WebProductDatabasePending "
                        "(ProductId, DatasourceKey, SchemaName, RuleId, Reason) "
                        "VALUES (%s,%s,%s,NULL,%s)",
                        (pid, dsk, by_name[sname],
                         f"{_REASON_PREFIX}:{conf:.2f}|{r1}"[:64]))
                    if getattr(cur, "rowcount", 0):
                        entry["suggested"] += 1
                rep["suggested_total"] += entry["suggested"]
            except Exception as exc:
                rep["errors"].append(f"{dsk}: {exc!r}")
        cur.close()
    finally:
        if own_mem:
            try:
                mem_conn.close()
            except Exception:
                pass
    return rep


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="미분류 스키마 → 제품 분류 AI 제안(승인 대기) 1-pass (§59)")
    ap.add_argument("--dry-run", action="store_true", help="제안 집계만(Pending 미적재)")
    args = ap.parse_args(argv)
    rep = run_classify_pass(dry_run=args.dry_run)
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
