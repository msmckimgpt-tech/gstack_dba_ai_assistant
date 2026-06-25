"""TASK-0219 — datasource 라벨 기반 fact/RAG 키를 **엔드포인트 해시 스코프**로 재키잉 + rag_objects 재생성.

배경: DatasourceKey(라벨)가 admin rename 가능한 단순 식별자로 바뀌면서(동시 TASK-0216/0218),
누적 insight 가 옛 라벨(`main_mysql`/`winsql`/`mssql_local`)로 스코프돼 새 스코핑(엔드포인트 해시)과
어긋났다. 본 스크립트는:

  1. fact_entries / rag_documents 의 `{source}:ds:{old}:{suffix}` → `{source}:ds:{hash}:{suffix}` 재키잉.
  2. 재키잉된 ds fact 로 rag_objects 재생성(_upsert_rag_memory_from_fact — datasource_key 태깅 포함).

매핑은 **라이브 레지스트리(WebDatasources)** 에서 엔진별 scope_key 를 도출(엔드포인트 해시).
옛 라벨→엔진은 의미 고정 상수(OLD_KEY_ENGINE). 멱등(이미 해시면 skip) + --dry-run.

Usage (agent 컨테이너):
    docker exec repo-agent-1 python -m scripts.rekey_datasource_facts --dry-run
    docker exec repo-agent-1 python -m scripts.rekey_datasource_facts
"""
from __future__ import annotations

import argparse
import sys

# 옛 ds 라벨 → 엔진(의미 고정). 엔드포인트/해시는 라이브 레지스트리에서 도출한다.
OLD_KEY_ENGINE = {
    "main_mysql": "mysql",
    "winsql": "mssql",
    "mssql_local": "mssql",
    "mysql_local": "mysql",
}

_DS_SOURCES = ("table_insight", "schema_insight", "table_pref", "schema_pref")


def _connect_mem():
    """agent_memory(MySQL) — 레지스트리 조회용."""
    import agent_core  # type: ignore
    return agent_core._connect_memory()


def _build_rekey_map(mem_conn) -> "dict[str, str]":
    """옛 라벨 → 엔드포인트 해시 scope_key. 라이브 레지스트리 엔진별 scope_key 도출.

    **안전 가드(외부리뷰 Q4)**: OLD_KEY_ENGINE 의 엔진-단위 fallback 은 그 엔진의 datasource 가
    레지스트리에 **정확히 1개**일 때만 모호하지 않다. 같은 엔진 datasource 가 2개 이상(다른
    엔드포인트)이면 옛 라벨 fact 가 엉뚱한 엔드포인트 scope 로 일괄 오병합될 수 있으므로,
    그 엔진의 옛-라벨 매핑은 **생략**(skip)하고 경고한다 — cross-ds 오병합 차단.
    """
    from shared import datasources as dsr
    registry = dsr.all_datasources(mem_conn)
    engine_scopes: dict[str, set] = {}
    engine_to_scope: dict[str, str] = {}
    label_to_scope: dict[str, str] = {}
    for label, ds in registry.items():
        sk = dsr.scope_key(ds)
        if not sk:
            continue
        eng = (ds.get("engine") or "mysql").strip().lower()
        label_to_scope[str(label).strip().lower()] = sk
        engine_scopes.setdefault(eng, set()).add(sk)
        engine_to_scope.setdefault(eng, sk)
    out: dict[str, str] = {}
    # 옛 라벨(의미 고정) → 엔진 → scope (엔진당 datasource 1개일 때만; 다중이면 모호 → skip)
    for old, eng in OLD_KEY_ENGINE.items():
        scopes = engine_scopes.get(eng) or set()
        if len(scopes) == 1:
            out[old] = engine_to_scope[eng]
        elif len(scopes) > 1:
            print(
                f"  ! 엔진 '{eng}' 에 datasource {len(scopes)}개({sorted(scopes)}) — "
                f"옛 라벨 '{old}' 매핑 모호, skip(수동 매핑 필요)",
                file=sys.stderr,
            )
    # 현재 레지스트리 라벨 자체도(라벨≠해시면) → 자기 scope (모호성 없음 — 라벨별 1:1)
    for label, sk in label_to_scope.items():
        if label != sk:
            out[label] = sk
    return out


def _distinct_ds_keys_in_facts(pg) -> "set[str]":
    keys: set[str] = set()
    with pg.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT split_part(fact_key,':',3) FROM public.fact_entries WHERE fact_key LIKE '%:ds:%'"
        )
        for (k,) in cur.fetchall() or []:
            if k:
                keys.add(str(k).strip().lower())
    return keys


def _rekey_table(pg, table: str, old: str, new: str, dry: bool) -> int:
    """{src}:ds:{old}:{suffix} → {src}:ds:{new}:{suffix} per-row.

    해시 접두(18자)가 옛 라벨보다 길어 fact_key(varchar 128) 가 overflow 할 수 있으므로 insight
    write 경로와 **동일한 `_fit_fact_key_storage`(>128 시 head:sha1[:12] 절단)** 를 적용해야 수렴한다.
    타깃 키가 이미 존재(병합/재스캔)하면 old 행 삭제, 아니면 UPDATE.
    """
    from modules.utils import _fit_fact_key_storage  # type: ignore
    old_frag = f":ds:{old}:"
    new_frag = f":ds:{new}:"
    with pg.cursor() as cur:
        cur.execute(
            f"SELECT conversation_id, scope_key, fact_key FROM public.{table} WHERE fact_key LIKE %s",
            (f"%{old_frag}%",),
        )
        rows = cur.fetchall() or []
    if not rows or dry:
        return len(rows)
    changed = 0
    with pg.cursor() as cur:
        for conv, scope, fk in rows:
            new_fk = _fit_fact_key_storage(str(fk).replace(old_frag, new_frag), 128)
            if new_fk == fk:
                continue
            cur.execute(
                f"SELECT 1 FROM public.{table} WHERE conversation_id=%s "
                f"AND scope_key IS NOT DISTINCT FROM %s AND fact_key=%s LIMIT 1",
                (conv, scope, new_fk),
            )
            if cur.fetchone():
                # 타깃 이미 존재(재스캔/병합) → old 행 삭제(중복 제거).
                cur.execute(
                    f"DELETE FROM public.{table} WHERE conversation_id=%s "
                    f"AND scope_key IS NOT DISTINCT FROM %s AND fact_key=%s",
                    (conv, scope, fk),
                )
            else:
                cur.execute(
                    f"UPDATE public.{table} SET fact_key=%s WHERE conversation_id=%s "
                    f"AND scope_key IS NOT DISTINCT FROM %s AND fact_key=%s",
                    (new_fk, conv, scope, fk),
                )
            changed += 1
        pg.commit()
    return changed


def _regen_rag_objects(pg, scope_hashes: "set[str]", dry: bool) -> int:
    """재키잉된 ds fact(해시 스코프)로 rag_objects 재생성. _upsert_rag_memory_from_fact 멱등."""
    from modules import utils  # type: ignore
    rows = []
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT e.conversation_id, e.fact_key, e.scope_key, e.weight, COALESCE(t.text_content,'')
            FROM public.fact_entries e JOIN public.texts t ON t.text_hash = e.text_hash
            WHERE e.fact_key LIKE '%:ds:%'
              AND (e.fact_key LIKE 'table_insight:%' OR e.fact_key LIKE 'schema_insight:%'
                   OR e.fact_key LIKE 'table_pref:%' OR e.fact_key LIKE 'schema_pref:%')
            ORDER BY e.fact_key
            """
        )
        for conv, fk, scope, weight, text in cur.fetchall() or []:
            ds = str(fk).split(":")
            if len(ds) >= 4 and ds[1] == "ds" and ds[2].strip().lower() in scope_hashes:
                rows.append((conv, fk, scope, weight, text))
    if dry:
        return len(rows)
    done = 0
    for conv, fk, scope, weight, text in rows:
        try:
            utils._upsert_rag_memory_from_fact(
                None, str(conv), str(fk), str(text), int(weight or 1),
                scope_key=str(scope or "common"), source_type="insight",
            )
            done += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ! rag_object 재생성 실패 {fk}: {exc}", file=sys.stderr)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="SELECT/계측만, 변경 없음")
    args = ap.parse_args()
    dry = args.dry_run

    from modules.db import _pg_connect  # type: ignore
    mem = _connect_mem()
    try:
        rekey = _build_rekey_map(mem)
    finally:
        try:
            mem.close()
        except Exception:
            pass
    print(f"[rekey-map] {rekey}")
    scope_hashes = set(rekey.values())

    pg = _pg_connect()
    try:
        present = _distinct_ds_keys_in_facts(pg)
        print(f"[facts ds-keys present] {sorted(present)}")
        total = 0
        for old, new in rekey.items():
            if old == new or old not in present:
                continue
            f = _rekey_table(pg, "fact_entries", old, new, dry)
            d = _rekey_table(pg, "rag_documents", old, new, dry)
            print(f"  {old} → {new}: fact_entries={f} rag_documents={d}{' (dry)' if dry else ''}")
            total += f
        objs = _regen_rag_objects(pg, scope_hashes, dry)
        print(f"[rag_objects 재생성] {objs}{' (dry)' if dry else ''}")
        print(f"[done] 재키잉 fact 행 ~{total}, rag_objects {objs}{' (dry-run)' if dry else ''}")
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
