"""feature-0040 db-object-explorer: 역할 기반 DB 객체 introspection → `db_objects` SSOT.

`routines.py`(ADR-016) 의 자매 모듈이다. insight-worker 가 스키마 유지보수 게이트
(`rel_maintenance_due` — relationships/routines introspect 와 동일 cadence) 안에서
데이터소스의 카탈로그를 **역할 축**(`db_object_roles`: view/trigger/schedule/alias/generator)
으로 조회해 `db_objects`(agent_kb PG, alembic 0054) 에 upsert 한다.
`metadata_graph.sync_graph` 가 이 SSOT 를 AGE `DbObject` 노드 + `HAS_OBJECT`(Schema→DbObject)
+ `OBJECT_USES`(DbObject→Table) + `OBJECT_ON`(DbObject→Table, 소유 관계) 로 투영한다.

설계 원칙 (routines.py 동형 — 의도적으로 같은 모양을 유지한다):
  - 연결: `shared.db._pg_conn_pair_rw`. PG 미가용·예외 시 no-op — insight 루프 절대 비차단.
  - **스키마-slot 규약(ADR-007)**: 질의는 실 스키마(MSSQL='dbo' 등), 저장 라벨은 store_schema
    (MSSQL=DB명). 단 `db_objects` 는 실 SQL 스키마도 `sql_schema` 로 함께 저장한다(0054 — 같은
    DB 안 다른 스키마의 동명 객체 충돌 방지).
  - 참조 테이블: 정의 텍스트를 `routines.parse_referenced_tables` 로 파싱한다. **같은 파서를
    재사용하는 것이 핵심** — 뷰의 SELECT·트리거 본문·작업 단계 명령은 전부 SQL 이고, 참조
    추출 규칙(주석 제거·alias-UPDATE 승격·크로스-DB qualifier 4규칙·실재 검증)을 두 벌 두면
    한쪽만 고쳐지는 drift 가 생긴다.
  - 변경 없는 객체는 updated_at 을 올리지 않는다(IS DISTINCT FROM 가드) — 증분 그래프 sync 정합.

**수집 대상 판정은 `Dialect.object_support` 가 단독 소유한다.** UNSUPPORTED 역할은 질의조차
하지 않고(SQL 이 None), PRIVILEGED 역할은 질의하되 **빈 결과를 prune 근거로 쓰지 않는다** —
권한 부족으로 0행이 온 것을 "전부 삭제됐다" 로 읽으면 그래프에서 노드가 통째로 사라지고,
권한이 회복되면 되살아나는 진동이 생긴다(§16.7 G9-b 무음 절단과 동형의 함정).
"""
from __future__ import annotations

import hashlib
import json
import logging

from . import db_object_roles as _roles
from .routines import parse_referenced_tables

_log = logging.getLogger("db_objects")

# graph-cap-audit 규약(routines.py 와 동일): 상한은 **최적화가 아니라 데이터 누락**이므로
# 실사용 최대치의 수십 배로 잡은 안전 가드일 뿐이고, 걸리면 조용히 자르지 않고 WARN 한다.
_OBJECT_CAP_DEFAULT = 20000     # 스키마·역할당 introspect 객체 안전 가드
_DESC_MAXLEN = 20000
_REFS_CAP = 2000

# 정의 본문을 파싱해 참조 테이블을 뽑을 역할. 별칭·값 생성기는 본문이 없다(대상은 owner_object).
_PARSE_REFS_ROLES = frozenset({_roles.ROLE_VIEW, _roles.ROLE_TRIGGER, _roles.ROLE_SCHEDULE})


def _rw_conn(conn):
    from shared.db import _pg_conn_pair_rw
    return _pg_conn_pair_rw(conn)


def _attr_dict(dialect, role: str, row) -> dict:
    """list_objects 행의 ATTR_A/B/C → 표제가 붙은 dict.

    위치 계약(ATTR_A/B/C)을 **저장 시점에 표제로 환원**한다. 그래프 상세 패널과 LLM 페이로드가
    `{"시점": "AFTER", "이벤트": "INSERT"}` 를 그대로 쓸 수 있어야 하는데, 위치 인덱스를 그대로
    저장하면 소비처마다 역할별 표제 표를 다시 들고 있어야 하고 그중 하나는 반드시 stale 이 된다.
    """
    labels = dialect.object_attr_labels(role)
    out: dict = {}
    for i, lb in enumerate(labels):
        key = str(lb or "").strip()
        if not key:
            continue
        try:
            val = str(row[4 + i] or "").strip()
        except (IndexError, TypeError):
            continue
        if val and val != "-":
            out[key] = val[:256]
    return out


def _fetch_objects(db_conn, dialect, role: str, schema: str, allow_dbs=(),
                   sys_exclude_schemas=()) -> "list|None":
    """한 역할의 객체 열거. 조회 불가(미지원)면 None, 실패면 [] (비차단).

    None 과 [] 의 구분이 중요하다 — None(미지원)은 prune 대상이 아니고, [](실패/0건)은 호출측이
    `prunable` 플래그로 따로 판정한다.
    """
    sql = dialect.list_objects(role, keyword="", schema=schema, allow_dbs=allow_dbs,
                               sys_exclude_schemas=sys_exclude_schemas)
    if not sql:
        return None
    cur = db_conn.cursor()
    try:
        cur.execute(sql)
        return list(cur.fetchall() or [])
    except Exception as exc:
        _log.debug("fetch_objects_failed role=%s schema=%s err=%r", role, schema, exc)
        return []
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _fetch_definition(db_conn, dialect, role: str, name: str, schema: str, allow_dbs=()) -> str:
    """객체 1건의 정의 본문(참조 파싱 입력). 실패·부재는 '' (비차단).

    여러 조각(Agent 작업 단계)은 개행으로 이어 붙인다 — 참조 추출은 조각 경계를 신경 쓰지
    않으므로 연접이 정확하고, 해시도 전체 기준이 되어 단계 하나만 바뀌어도 변경이 감지된다.
    """
    sql = dialect.object_definition(role, name, schema=schema, allow_dbs=allow_dbs)
    if not sql:
        return ""
    cur = db_conn.cursor()
    try:
        cur.execute(sql)
        parts = []
        for row in (cur.fetchall() or []):
            try:
                body = str(row[7] or "").strip()
            except (IndexError, TypeError):
                continue
            if body:
                parts.append(body)
        return "\n".join(parts)
    except Exception as exc:
        _log.debug("fetch_definition_failed role=%s name=%s err=%r", role, name, exc)
        return ""
    finally:
        try:
            cur.close()
        except Exception:
            pass


def introspect_and_store(db_conn, schema, table_names, *, dialect=None, kb_conn=None,
                         scope_key="common", datasource_key="", source_run_id=None,
                         store_schema=None, sql_schema="", cap=None, prune=True,
                         allow_dbs=(), sys_exclude_schemas=(), roles=None,
                         inventory_sink=None) -> int:
    """한 schema 의 역할 기반 DB 객체를 introspect 해 `db_objects` 에 upsert.

    반환: **변경 upsert 행 수**(무변경 skip 은 미집계 — `routines.introspect_and_store` 동일 규약).
    예외는 삼켜 0/부분 카운트 반환(insight 루프 비차단).

    `prune`: cap 절단이 없고 **그 역할을 실제로 조회해 성공한 경우에만** 이번 introspect 에 없는
    행을 삭제한다. PRIVILEGED 역할(권한에 따라 빈 결과)이 0행을 냈다고 지워버리면 그래프 노드가
    사라졌다 살아났다 진동한다 — 그래서 prune 은 **역할 단위**로 판정한다.

    `inventory_sink`: dict 를 넘기면 관측한 객체 전량을
    `sink["db_objects"] = {"<role>:<name>": definition_hash}` 로 채운다(자동 재분석 시드 대조용).
    cap 절단·조회 실패 역할이 하나라도 있으면 **키를 넣지 않는다** — 부분집합을 전량으로 오인하면
    절단 밖 객체가 매 사이클 삭제→신규로 진동해 승인 없는 LLM 지출을 반복한다
    (`routines.introspect_and_store` 의 동일 규약).
    """
    if db_conn is None:
        return 0
    if dialect is None:
        from . import dialects as _d
        dialect = _d.active()
    try:
        cap = int(cap) if cap else _OBJECT_CAP_DEFAULT
    except (TypeError, ValueError):
        cap = _OBJECT_CAP_DEFAULT
    target_roles = tuple(roles) if roles else _roles.COLLECTED_ROLES
    label = str(store_schema).strip() if store_schema is not None else str(schema or "")
    sql_sch = str(sql_schema or "").strip()

    kc, kowned = _rw_conn(kb_conn)
    if kc is None:
        return 0
    n = 0
    inventory: dict = {}
    inventory_trustworthy = True
    try:
        # §56 RC2 와 동일한 크로스-DB 실재 검증 집합 — 참조 파서에 그대로 넘긴다.
        from .routines import _external_tables_for
        ext_tables = _external_tables_for(kc, (datasource_key or "").strip() or (scope_key or ""))
        cur = kc.cursor()
        for role in target_roles:
            support = dialect.object_support(role)
            if support in (_roles.UNSUPPORTED, _roles.DELEGATED):
                continue    # 개념 부재/타 서브시스템 소유 — 질의도 prune 도 하지 않는다
            fetched = _fetch_objects(db_conn, dialect, role, schema,
                                     allow_dbs=allow_dbs,
                                     sys_exclude_schemas=sys_exclude_schemas)
            if fetched is None:
                continue
            truncated = len(fetched) > max(1, cap)
            if truncated:
                _log.warning(
                    "db_object_cap_truncated role=%s schema=%s fetched=%d cap=%d dropped=%d "
                    "(그래프에서 이 역할의 노드가 누락된다 — 상한 상향 필요)",
                    role, schema, len(fetched), cap, len(fetched) - max(1, cap))
                inventory_trustworthy = False
            rows = fetched[:max(1, cap)]
            # PRIVILEGED 역할의 빈 결과는 "없음" 이 아니라 "안 보임" 일 수 있다 → prune 금지.
            role_prunable = bool(prune) and not truncated and not (
                support == _roles.PRIVILEGED and not rows)
            seen_names: list = []
            for row in rows:
                try:
                    name = str(row[1] or "").strip()
                    if not name:
                        continue
                    otype = str(row[2] or "").strip()[:32]
                    owner = str(row[3] or "").strip()[:512]
                    attrs = _attr_dict(dialect, role, row)
                    definition = (_fetch_definition(db_conn, dialect, role, name, schema,
                                                    allow_dbs=allow_dbs)
                                  if role in _PARSE_REFS_ROLES else "")
                    refs = []
                    if definition and (table_names or ext_tables):
                        try:
                            refs = parse_referenced_tables(
                                definition, table_names, self_name=name,
                                external_tables=ext_tables, local_label=label)[:_REFS_CAP]
                        except Exception as exc:
                            _log.debug("db_object_parse_failed role=%s name=%s err=%r",
                                       role, name, exc)
                            refs = []
                    # 참조 fqn 은 저장 slot 기준 `label.table`(로컬) / `타스키마.table`(크로스-DB) —
                    # sync_db_object 가 fqn 을 그대로 `<scope>:<fqn>` 으로 앵커한다(sync_routine 동형).
                    refs_fqn = []
                    for x in refs:
                        _e = {"fqn": (f"{x['schema']}.{x['fqn']}" if x.get("schema")
                                      else (f"{label}.{x['fqn']}" if label else x["fqn"])),
                              "kind": x["kind"]}
                        if x.get("schema"):
                            _e["cross"] = 1
                        refs_fqn.append(_e)
                    dhash = hashlib.sha256(
                        (definition or "").encode("utf-8", "replace")).hexdigest() if definition else ""
                    seen_names.append(name)
                    inventory[f"{role}:{name}"] = dhash
                    cur.execute(
                        "INSERT INTO db_objects "
                        "(scope_key, datasource_key, schema_name, sql_schema, object_role, "
                        " object_name, object_type, owner_object, attributes, definition_hash, "
                        " referenced_tables, source_run_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s) "
                        "ON CONFLICT (scope_key, schema_name, sql_schema, object_role, object_name) "
                        "DO UPDATE SET "
                        "  datasource_key = EXCLUDED.datasource_key, "
                        "  object_type = EXCLUDED.object_type, "
                        "  owner_object = EXCLUDED.owner_object, "
                        "  attributes = EXCLUDED.attributes, "
                        "  definition_hash = EXCLUDED.definition_hash, "
                        "  referenced_tables = EXCLUDED.referenced_tables, "
                        "  source_run_id = EXCLUDED.source_run_id "
                        "WHERE (db_objects.object_type, db_objects.owner_object, "
                        "       db_objects.attributes, db_objects.definition_hash, "
                        "       db_objects.referenced_tables) "
                        "      IS DISTINCT FROM "
                        "      (EXCLUDED.object_type, EXCLUDED.owner_object, "
                        "       EXCLUDED.attributes, EXCLUDED.definition_hash, "
                        "       EXCLUDED.referenced_tables)",
                        ((scope_key or "common")[:96], (datasource_key or "")[:96],
                         label[:256], sql_sch[:256], role, name[:256], otype, owner,
                         json.dumps(attrs, ensure_ascii=False), dhash,
                         json.dumps(refs_fqn, ensure_ascii=False), source_run_id))
                    rc = getattr(cur, "rowcount", None)
                    if rc is None or rc != 0:
                        n += 1
                except Exception as exc:
                    _log.debug("db_object_upsert_failed role=%s schema=%s err=%r",
                               role, schema, exc)
                    continue
            if not role_prunable:
                if support == _roles.PRIVILEGED and not rows:
                    inventory_trustworthy = False
                continue
            try:
                cur.execute(
                    "DELETE FROM db_objects "
                    "WHERE scope_key = %s AND schema_name = %s AND object_role = %s "
                    "AND NOT (object_name = ANY(%s))",
                    ((scope_key or "common")[:96], label[:256], role, seen_names))
                rc = getattr(cur, "rowcount", None)
                if isinstance(rc, int) and rc > 0:
                    _log.info("db_objects_pruned role=%s schema=%s count=%s", role, label, rc)
            except Exception as exc:
                _log.debug("db_objects_prune_failed role=%s schema=%s err=%r", role, schema, exc)
        cur.close()
        if inventory_sink is not None and inventory_trustworthy:
            inventory_sink["db_objects"] = inventory
    except Exception as exc:
        _log.warning("db_objects_introspect_store_failed schema=%s err=%r", schema, exc)
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
    return n


def load_for_schema(scope_key, schema_name, kb_conn=None) -> list:
    """그래프 sync 입력 — 한 (scope, schema) 의 객체 전량. 실패 시 [] (비차단).

    반환 entry: {role, name, type, owner, sql_schema, attributes, refs, description}
    """
    kc, kowned = (None, False)
    try:
        kc, kowned = _rw_conn(kb_conn)
        if kc is None:
            return []
        cur = kc.cursor()
        try:
            cur.execute(
                "SELECT object_role, object_name, object_type, owner_object, sql_schema, "
                "       attributes, referenced_tables, description "
                "FROM db_objects WHERE scope_key = %s AND schema_name = %s "
                "ORDER BY object_role, object_name",
                ((scope_key or "common")[:96], str(schema_name or "")[:256]))
            out = []
            for row in (cur.fetchall() or []):
                out.append({
                    "role": str(row[0] or ""), "name": str(row[1] or ""),
                    "type": str(row[2] or ""), "owner": str(row[3] or ""),
                    "sql_schema": str(row[4] or ""),
                    "attributes": row[5] if isinstance(row[5], dict) else {},
                    "refs": row[6] if isinstance(row[6], list) else [],
                    "description": str(row[7] or ""),
                })
            return out
        finally:
            cur.close()
    except Exception as exc:
        _log.debug("db_objects_load_failed scope=%s schema=%s err=%r", scope_key, schema_name, exc)
        return []
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
