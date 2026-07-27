"""feature-0016 graph-funcproc-uxfix: 함수·프로시저(routine) introspection → routine_objects SSOT (ADR-016).

insight-worker 가 스키마 유지보수 게이트(rel_maintenance_due — relationships introspect 와 동일 cadence)
안에서 데이터소스의 INFORMATION_SCHEMA.ROUTINES / PARAMETERS(MySQL·MSSQL 공통 뷰)를 조회해
`routine_objects` (agent_kb PG, alembic 0034) 에 upsert 한다. metadata_graph.sync_graph 가 이 SSOT 를
AGE `Routine` 노드 + `HAS_ROUTINE`(Schema→Routine) + `ROUTINE_USES`(Routine→Table) 로 투영한다.

설계 원칙 (relationships.py 동형):
  - 연결: shared.db._pg_connect(autocommit). PG 미가용·예외 시 no-op — insight 루프 절대 비차단.
  - **스키마-slot 규약(ADR-007)**: 질의는 실 스키마(schema, MSSQL='dbo')로, 저장 라벨은
    store_schema(MSSQL=DB명)로 분리 — 그래프 Table 키(`db.table`)·column_descriptions 규약 정합.
  - 참조 테이블: 정의(ROUTINE_DEFINITION) 텍스트를 보수적 정규식으로 파싱해 **그 스키마에 실재하는
    테이블만** 채택(가비지 차단). MSSQL 정의는 4000자 절단본이라 부분 커버(정확도보다 안전 우선).
  - 변경 없는 routine 은 updated_at 을 올리지 않는다(IS DISTINCT FROM 가드) — 증분 그래프 sync 정합.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

_log = logging.getLogger("routines")

_ROUTINE_CAP_DEFAULT = 300   # 스키마당 1회 introspect 최대 routine 수(폭주 방지)
_PARAMS_MAXLEN = 500
_REFS_CAP = 40               # routine 당 참조 테이블 상한

# 정의 텍스트에서 테이블 참조 후보를 뽑는 보수적 토큰 스캔.
#   write 동사(INTO/UPDATE/DELETE FROM/MERGE INTO)를 FROM/JOIN 보다 먼저 배치 — 같은 위치에서
#   "DELETE FROM t" 가 write 로 잡히고, finditer 는 매치 끝 이후를 잇는다(FROM 중복 매치 없음).
_REF_RE = re.compile(
    r"(?i)\b(DELETE\s+FROM|MERGE\s+INTO|INSERT\s+INTO|UPDATE|FROM|JOIN)\s+"
    r"([\[\]`\"A-Za-z0-9_$#.]+)")
_WRITE_KW = ("DELETE", "MERGE", "INSERT", "UPDATE")
# §18.8 패널(MINOR): 주석(-- 줄 / /* 블록 */) 안의 FROM/JOIN 이 유령 참조를 만들던 오탐 차단.
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
# §18.8 패널(MINOR): MSSQL alias-UPDATE(`UPDATE a SET … FROM T_User a`) — UPDATE 캡처가 alias 라
#   폐기되고 실제 write 대상이 read 로 남던 오분류를, alias 역참조로 FROM 절 테이블을 write 승격.
_ALIAS_UPDATE_RE = re.compile(
    r"(?is)\bUPDATE\s+([A-Za-z0-9_]+)\s+SET\b.*?\bFROM\s+([\[\]`\"A-Za-z0-9_$#.]+)\s+(?:AS\s+)?\1\b")


def _unquote(ident: str) -> str:
    return str(ident or "").strip().strip("`\"[]").strip()


def parse_referenced_tables(definition, table_names, self_name="", *,
                            external_tables=None, local_label="") -> list:
    """routine 정의 텍스트 → 참조 테이블 목록 (실재 검증 통과분만).

    반환 entry:
      - 로컬:      {fqn: '<Table>', kind: 'read|write'}
      - 크로스-DB: {fqn: '<Table>', kind, schema: '<타 effective 스키마(DB)>'} (§56 RC2)

    table_names 는 그 스키마의 실 테이블명 목록(대소문자 무관 매칭). 임시테이블(#)·변수(@)·
    서브쿼리·자기 자신·주석 안 참조는 제외. 테이블당 1 entry — write 가 read 보다 우선.

    §56 qualifier 해석(RC2 — 프로시저 중심 환경의 크로스-DB 가시화 + 동명 오귀속 차단):
      external_tables: {(schema_lower, table_lower): (schema, table)} — 같은 datasource 의
      **다른** effective 스키마(DB) 테이블 집합(rag_objects 실재 검증). local_label: 저장
      스키마-slot(MSSQL=DB명). qualified 참조([db].[dbo].[T] · db..T · db.T)는:
        ① qualifier == local_label 또는 'dbo'(기본 스키마) → 로컬 귀속(기존 동작).
        ② (qualifier, leaf) ∈ external_tables → **크로스-DB 참조** 채택(schema 필드 동반).
        ③ qualifier 가 알려진 타 스키마인데 그 테이블 미실재 → **폐기** — 기존 leaf-정규화가
           동명 로컬 테이블로 오귀속하던 결함 차단.
        ④ qualifier 미상(추적 밖 스키마 등) → 레거시 폴백: leaf 로컬 실재 시 로컬(recall 보존).
    알려진 한계(ADR-016): 동적 SQL(EXEC(@s))·MSSQL 4000자 절단 정의는 부분 커버.
    """
    if not definition or not (table_names or external_tables):
        return []
    text = _COMMENT_RE.sub(" ", str(definition))
    canon = {}   # lower -> 실 테이블명(원 케이스 보존)
    for t in (table_names or []):
        s = str(t or "").strip()
        if s:
            canon.setdefault(s.lower(), s)
    ext = external_tables if isinstance(external_tables, dict) else {}
    ext_schemas = {k[0] for k in ext}          # 알려진 타 스키마(lower)
    local_low = _unquote(local_label).lower()
    self_low = _unquote(self_name).lower()
    found = {}     # lower table -> kind (로컬)
    found_x = {}   # (schema_lower, table_lower) -> kind (크로스-DB)

    def _mark(leaf, kind):
        low = leaf.lower()
        if not low or low == self_low or low not in canon:
            return
        prev = found.get(low)
        if prev != "write":
            found[low] = kind if prev is None or kind == "write" else prev

    def _route(raw, kind):
        # qualifier 판정 — 빈 세그먼트 보존('db..T' → ['db','','T']) 후 leaf/첫 세그먼트 추출.
        segs = str(raw).rstrip(";,)(").split(".")
        leaf = _unquote(segs[-1]) if segs else ""
        if not leaf or leaf.startswith("#") or leaf.startswith("@"):
            return
        qual_low = _unquote(segs[0]).lower() if len(segs) >= 2 else ""
        if not qual_low or qual_low == "dbo" or qual_low == local_low:
            _mark(leaf, kind)                            # ① 무자격/기본 스키마/자기 라벨 → 로컬
            return
        leaf_low = leaf.lower()
        if (qual_low, leaf_low) in ext:
            prev = found_x.get((qual_low, leaf_low))     # ② 실재 크로스-DB 참조
            if prev != "write":
                found_x[(qual_low, leaf_low)] = kind if prev is None or kind == "write" else prev
            return
        if qual_low in ext_schemas:
            return                                       # ③ 타 스키마 지정·미실재 — 오귀속 차단(폐기)
        _mark(leaf, kind)                                # ④ 미상 qualifier — 레거시 로컬 폴백

    for m in _REF_RE.finditer(text):
        if len(found) + len(found_x) >= _REFS_CAP:
            break
        kw = (m.group(1) or "").upper()
        raw = m.group(2) or ""
        if raw.startswith("(") or raw.startswith("@") or raw.startswith("#"):
            continue
        _route(raw, "write" if any(kw.startswith(w) for w in _WRITE_KW) else "read")
    # alias-UPDATE write 승격(위 스캔이 read 로 남긴 실제 write 대상 보정)
    for m in _ALIAS_UPDATE_RE.finditer(text):
        alias, raw = m.group(1) or "", m.group(2) or ""
        if alias.lower() in canon:
            continue   # alias 가 실 테이블명이면 위 스캔이 이미 write 처리
        _route(raw, "write")
    out = [{"fqn": canon[low], "kind": kind} for low, kind in sorted(found.items())]
    out += [{"fqn": ext[k][1], "kind": kind, "schema": ext[k][0]}
            for k, kind in sorted(found_x.items())]
    return out


def _fetch_routines(db_conn, schema) -> list:
    """INFORMATION_SCHEMA.ROUTINES → [{name, rtype, definition}]. 실패 시 [] (비차단).

    교차-방언 공통 컬럼만 조회한다 — 반환형(MySQL=DTD_IDENTIFIER / MSSQL=DATA_TYPE)은 컬럼셋이
    갈리므로 여기서 뽑지 않고 PARAMETERS 의 ORDINAL_POSITION=0(양쪽 공통 규약)에서 얻는다.
    MSSQL ROUTINE_DEFINITION 은 4000자 절단본(참조 파싱엔 충분 — 부분 커버 수용)."""
    out = []
    cur = db_conn.cursor()
    try:
        # ORDER BY(§18.8 NIT): cap 절단이 결정적이도록 — 엔진 임의 순서면 cycle 간 introspect
        # subset 이 흔들리고 cap 밖 잔여가 영구 미수집될 수 있다.
        cur.execute(
            "SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_DEFINITION "
            "FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = %s "
            "ORDER BY ROUTINE_NAME, ROUTINE_TYPE", (schema,))
        for row in (cur.fetchall() or []):
            try:
                name = str(row[0] or "").strip()
                rtype = str(row[1] or "").strip().lower()
                if not name or rtype not in ("function", "procedure"):
                    continue
                out.append({"name": name, "rtype": rtype, "definition": str(row[2] or "")})
            except Exception:
                continue
    finally:
        try:
            cur.close()
        except Exception:
            pass
    return out


def _fetch_params(db_conn, schema):
    """INFORMATION_SCHEMA.PARAMETERS → (params_map, returns_map).

    params_map  = {routine_name_lower: "IN a int, OUT b varchar"} (ORDINAL_POSITION > 0)
    returns_map = {routine_name_lower: "int"}                     (ORDINAL_POSITION = 0 — 함수 반환형)
    실패 시 ({}, {}) — 비차단(파라미터 없이도 노드는 유효)."""
    params, returns = {}, {}
    cur = db_conn.cursor()
    try:
        cur.execute(
            "SELECT SPECIFIC_NAME, ORDINAL_POSITION, PARAMETER_MODE, PARAMETER_NAME, DATA_TYPE "
            "FROM information_schema.PARAMETERS "
            "WHERE SPECIFIC_SCHEMA = %s "
            "ORDER BY SPECIFIC_NAME, ORDINAL_POSITION", (schema,))
        for sname, pos, mode, pname, ptype in (cur.fetchall() or []):
            key = str(sname or "").strip().lower()
            if not key:
                continue
            try:
                pos = int(pos)
            except (TypeError, ValueError):
                pos = 1
            if pos == 0:
                returns[key] = str(ptype or "").strip()[:256]
                continue
            piece = " ".join(x for x in (str(mode or "").strip(), str(pname or "").strip(),
                                         str(ptype or "").strip()) if x)
            if not piece:
                continue
            cur_v = params.get(key, "")
            if len(cur_v) < _PARAMS_MAXLEN:
                params[key] = (cur_v + ", " + piece) if cur_v else piece
    except Exception as exc:
        _log.debug("fetch_params_failed schema=%s err=%r", schema, exc)
    finally:
        try:
            cur.close()
        except Exception:
            pass
    return params, returns


def _rw_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect
    if not _pg_available():
        return None, False
    return _pg_connect(autocommit=True), True


# §56 RC2: 크로스-DB 참조 실재 검증용 — datasource 의 effective 스키마(DB) 테이블 집합 TTL 캐시.
#   backfill/cadence 가 같은 ds 의 스키마 수십 개를 연쇄 introspect 하므로 rag_objects 1회 조회를 재사용.
_EXT_TTL_SEC = 600
_EXT_CACHE: dict = {}   # dsk -> (monotonic_ts, {(schema_lower, table_lower): (schema, table)})


def _external_tables_for(kc, dsk) -> dict:
    """같은 datasource 의 effective 스키마(DB) 테이블 집합(rag_objects) — parse 의 external_tables 원천.

    실패 시 {} (비차단 — 크로스-DB 검증만 비활성, 로컬 파싱 불변). 캐시는 프로세스 로컬(TTL 600s)."""
    import time
    key = str(dsk or "").strip()
    if not key:
        return {}
    hit = _EXT_CACHE.get(key)
    if hit and (time.monotonic() - hit[0]) < _EXT_TTL_SEC:
        return hit[1]
    ext: dict = {}
    try:
        from .semantic_cluster import _effective_schema
        cur = kc.cursor()
        try:
            cur.execute("SELECT schema_name, table_name, object_key FROM rag_objects "
                        "WHERE object_type='table' AND datasource_key=%s AND table_name<>''", (key,))
            for sch, tbl, okey in cur.fetchall():
                eff = _effective_schema(key, okey, sch)
                if eff and tbl:
                    ext[(str(eff).lower(), str(tbl).lower())] = (str(eff), str(tbl))
        finally:
            cur.close()
    except Exception as exc:
        # §18.8 패널(§56): 실패 결과({})는 **캐시하지 않는다** — TTL 600s 동안 크로스-DB 검증이
        # 침묵 비활성(레거시 오귀속 재발 창)으로 남는 것을 방지. 다음 호출이 재시도한다.
        _log.debug("external_tables_load_failed ds=%s err=%r", key, exc)
        return {}
    _EXT_CACHE[key] = (time.monotonic(), ext)
    return ext


def introspect_and_store(db_conn, schema, table_names, *, kb_conn=None, scope_key="common",
                         datasource_key="", source_run_id=None, store_schema=None,
                         cap=None, prune=True, inventory_sink=None) -> int:
    """한 schema 의 함수·프로시저를 introspect 해 routine_objects 에 upsert. 반환: **변경 upsert 행 수**
    (무변경 skip 은 미집계 — cur.rowcount 기준, §18.8 NIT).

    질의 스키마(schema)와 저장 스키마-slot(store_schema, ADR-007) 분리. 예외는 삼켜서
    0/부분 카운트 반환(insight 루프 비차단). 변경 없는 행은 updated_at 을 건드리지 않는다.
    **prune(§18.8 MAJOR-보완)**: cap 절단이 없는 완전 스캔일 때, 이번 introspect 에 없는
    (scope, schema) 행을 삭제해 drop 된 routine 의 SSOT 잔존을 막는다(그래프 노드 prune 은
    테이블과 동일하게 투영 범위 밖 — ADR-016 알려진 한계).
    **inventory_sink(change-reanalysis, 2026-07-27)**: dict 를 넘기면 이번 introspect 가 관측한
    **루틴 전량**을 `sink["routines"] = {routine_name: definition_hash}` 로 채운다(반환형 불변 —
    기존 호출자 무영향). insight-worker 가 이 인벤토리를 구조 스냅샷과 대조해 자동 재분석 시드를
    만든다. **cap 절단(truncated) 시에는 `"routines"` 키를 넣지 않는다** — 부분집합을 전량으로
    오인하면 절단 밖 루틴이 매 사이클 삭제→신규로 진동해 승인 없는 LLM 지출을 반복한다(prune 이
    완전 스캔에서만 도는 것과 동일 규약). 키 유무가 곧 "인벤토리 신뢰 가능" 신호이므로, 루틴이
    실제로 0건인 스키마(빈 dict)와 절단·조회 실패(키 부재)가 구분된다.
    upsert 성공 여부와 무관하게 담는다 — 인벤토리는 DB 관측 사실이라, 일부 행의 upsert 예외로
    항목이 빠지면 다음 사이클에 '신규'로 오탐된다.
    """
    if db_conn is None:
        return 0
    try:
        cap = int(cap) if cap else _ROUTINE_CAP_DEFAULT
    except (TypeError, ValueError):
        cap = _ROUTINE_CAP_DEFAULT
    try:
        fetched = _fetch_routines(db_conn, schema)
    except Exception as exc:
        _log.debug("fetch_routines_failed schema=%s err=%r", schema, exc)
        return 0
    truncated = len(fetched) > max(1, cap)
    routines = fetched[:max(1, cap)]
    if inventory_sink is not None and not truncated:
        # change-reanalysis: 완전 스캔일 때만 전량 인벤토리를 노출(부분집합 = 진동 원인).
        # upsert 루프 밖에서 계산 — 개별 행의 upsert 예외가 인벤토리를 갉지 않게 한다.
        inventory_sink["routines"] = {
            r["name"]: hashlib.sha256(
                (r["definition"] or "").encode("utf-8", "replace")).hexdigest()
            for r in routines if r.get("definition")
        }
    params_map, returns_map = _fetch_params(db_conn, schema) if routines else ({}, {})
    label = str(store_schema).strip() if store_schema is not None else str(schema or "")
    kc, kowned = _rw_conn(kb_conn)
    if kc is None:
        return 0
    n = 0
    try:
        # §56 RC2: 크로스-DB 참조 실재 검증 집합(같은 ds 의 타 effective 스키마 테이블) — 실패 시 {}(로컬 파싱 불변).
        ext_tables = _external_tables_for(kc, (datasource_key or "").strip() or (scope_key or ""))
        cur = kc.cursor()
        for r in routines:
            try:
                refs = parse_referenced_tables(r["definition"], table_names, self_name=r["name"],
                                               external_tables=ext_tables, local_label=label)
                # 참조 fqn 은 저장 slot 기준 `label.table`(로컬) / `타스키마.table`(크로스-DB, §56 RC2 —
                # sync_routine 이 fqn 그대로 <scope>:<fqn> 으로 앵커해 크로스 클러스터 ROUTINE_USES 성립).
                refs_fqn = [{"fqn": (f"{x['schema']}.{x['fqn']}" if x.get("schema")
                                     else (f"{label}.{x['fqn']}" if label else x["fqn"])),
                             "kind": x["kind"], **({"cross": 1} if x.get("schema") else {})}
                            for x in refs]
                dhash = hashlib.sha256((r["definition"] or "").encode("utf-8", "replace")).hexdigest() \
                    if r["definition"] else ""
                cur.execute(
                    "INSERT INTO routine_objects "
                    "(scope_key, datasource_key, schema_name, routine_name, routine_type, "
                    " params, returns, definition_hash, referenced_tables, source_run_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) "
                    "ON CONFLICT (scope_key, schema_name, routine_name, routine_type) DO UPDATE SET "
                    "  datasource_key = EXCLUDED.datasource_key, "
                    "  params = EXCLUDED.params, returns = EXCLUDED.returns, "
                    "  definition_hash = EXCLUDED.definition_hash, "
                    "  referenced_tables = EXCLUDED.referenced_tables, "
                    "  source_run_id = EXCLUDED.source_run_id "
                    "WHERE (routine_objects.params, routine_objects.returns, "
                    "       routine_objects.definition_hash, routine_objects.referenced_tables) "
                    "      IS DISTINCT FROM "
                    "      (EXCLUDED.params, EXCLUDED.returns, EXCLUDED.definition_hash, "
                    "       EXCLUDED.referenced_tables)",
                    ((scope_key or "common")[:96], (datasource_key or "")[:96], label[:256],
                     r["name"][:256], r["rtype"],
                     (params_map.get(r["name"].lower(), ""))[:_PARAMS_MAXLEN],
                     returns_map.get(r["name"].lower(), ""), dhash,
                     json.dumps(refs_fqn, ensure_ascii=False), source_run_id))
                rc = getattr(cur, "rowcount", None)
                if rc is None or rc != 0:
                    n += 1   # 무변경 skip(IS DISTINCT FROM) 은 rowcount 0 — 변경분만 집계(-1/미상은 시도로 집계)
            except Exception as exc:
                _log.debug("routine_upsert_failed schema=%s routine=%s err=%r",
                           schema, r.get("name"), exc)
                continue
        # prune — 완전 스캔(cap 미절단)일 때만: drop 된 routine 의 SSOT 행 회수(멱등).
        # routine-dbanalysis(§53): prune 은 (scope, store-label) 범위 삭제라, 한 label(MSSQL=DB명)에
        #   복수 ROUTINE_SCHEMA 가 공존하면 뒤 스키마 introspect 가 앞 스키마 행을 지운다 — caller 가
        #   label 당 복수 스키마를 아는 경우(backfill) prune=False 로 억제한다(기본 True=기존 동작).
        if prune and not truncated:
            try:
                names = [r["name"] for r in routines]
                cur.execute(
                    "DELETE FROM routine_objects "
                    "WHERE scope_key = %s AND schema_name = %s "
                    "AND NOT (routine_name = ANY(%s))",
                    ((scope_key or "common")[:96], label[:256], names))
                rc = getattr(cur, "rowcount", None)
                if isinstance(rc, int) and rc > 0:
                    _log.info("routines_pruned schema=%s count=%s", label, rc)
            except Exception as exc:
                _log.debug("routines_prune_failed schema=%s err=%r", schema, exc)
        cur.close()
    except Exception as exc:
        _log.warning("routines_introspect_store_failed schema=%s err=%r", schema, exc)
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
    return n


def purge_case_variant_labels(scope_key, store_label, kb_conn=None) -> int:
    """§56 RC5 보완(적대 패널 MAJOR): 방금 lower store label 로 재적재된 DB 의 **케이스-변형 label
    행**을 멱등 회수. introspect 성공 직후 그 label 의 fresh truth 가 SSOT 에 있으므로 같은
    (scope, lower(label)) 에서 label 케이스만 다른 행은 정의상 stale 이중 키다 — 수동 정리
    runbook 의 코드화(행 단위 twin-검증 불요·introspect 실패 DB 는 호출 자체가 없어 안전).
    stale pre-RC5 writer 가 mixed 행을 재생성해도 다음 backfill 이 자동 치유한다. 케이스-변형
    label 행이 없으면 no-op. 예외는 삼켜 0 반환(루프 비차단 — introspect_and_store 관례)."""
    if not store_label:
        return 0
    kc, kowned = (None, False)
    try:
        kc, kowned = _rw_conn(kb_conn)
        if kc is None:
            return 0
        cur = kc.cursor()
        cur.execute(
            "DELETE FROM routine_objects "
            "WHERE scope_key = %s AND schema_name <> %s AND lower(schema_name) = %s",
            ((scope_key or "common")[:96], store_label[:256], store_label[:256]))
        rc = getattr(cur, "rowcount", None)
        n = rc if isinstance(rc, int) and rc > 0 else 0
        if n:
            _log.info("routine_case_variants_purged label=%s count=%s", store_label, n)
        return n
    except Exception as exc:
        _log.warning("purge_case_variant_labels_failed label=%s err=%r", store_label, exc)
        return 0
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
