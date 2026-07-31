"""analysis_verify — 노드 분석문의 사실성 판정 (feature-0036, ITEM-10).

**왜.** 생성된 분석문의 사실성을 아무도 확인하지 않았다. 1만여 건이 쌓였고 그것이 클러스터
요약의 입력이 되고 대화 답변에 주입되는데(feature-0033·0034), 그 어느 지점에도 "이 서술이
실제 데이터와 맞는가"를 묻는 층이 없었다. feature-0031 이 증거를 만들었으니 대조가 가능하다.

**정직성이 이 모듈의 전부다.**

  판정 실패(LLM 오류·타임아웃·예산 소진·증거 없음)는 **행을 만들지 않는다** = 미검증.
  그것을 `supported` 로도 `unverifiable` 로도 기록하지 않는다.

  fail-open 이 "검증됨"으로 둔갑하면 이 층은 있는 것보다 나쁘다 — 아무도 확인하지 않은 서술에
  확인 도장이 찍히고, 그 도장을 근거로 위층(요약·답변)이 더 확신하게 된다.
  그래서 이 모듈의 fail-soft 는 "조용히 아무 기록도 남기지 않는다"이지 "통과시킨다"가 아니다.

**대상**: 분석문(`node_analysis_jobs.status='done'`)과 증거(`metadata_table_stats`)가 **둘 다**
있고, 아직 그 분석문 버전으로 판정되지 않은 것. 증거가 없으면 대조할 것이 없으므로 대상이 아니다
— 커버리지가 차면(feature-0035 플래너) 대상도 함께 는다.

**비용**: pass 당 상한 + 백그라운드 토큰 예산(feature-0032) + task 예산 + kill-switch 하위.
판정은 1건 1콜이다(배치하면 한 건의 오판이 다른 건으로 번진다).
"""
from __future__ import annotations

import hashlib
import json
import logging

_log = logging.getLogger("analysis_verify")

VERDICTS = ("supported", "contradicted", "unverifiable")

#: pass 당 판정 건수 상한. 1건 1콜이라 이 값이 곧 콜 수다.
_DEFAULT_MAX_PER_PASS = 20

#: payload 에 싣는 컬럼 통계 수 — 전부 실으면 토큰이 커지고 판정이 산만해진다.
_EVIDENCE_COLUMN_CAP = 30

#: 분석문 절단(문자). 프롬프트 계약이 1~2문장이라 넉넉하다.
_ANALYSIS_CLIP = 800


def analysis_hash(text) -> str:
    """판정 대상 분석문의 지문. 분석이 갱신되면 해시가 달라져 자연히 미검증으로 돌아간다."""
    s = " ".join(str(text or "").split())
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32] if s else ""


def enabled() -> bool:
    """검증 스위치 — 콘솔 live override 우선. 조회 실패는 비활성(모르면 지출하지 않는다)."""
    try:
        from shared import runtime_settings as _rts
        return bool(int(_rts.get_int("AGENT_ANALYSIS_VERIFY_ENABLED")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return bool(int(getattr(_cfg, "AGENT_ANALYSIS_VERIFY_ENABLED", 0) or 0))
    except Exception:
        return False


def max_per_pass() -> int:
    try:
        from shared import runtime_settings as _rts
        return max(0, int(_rts.get_int("AGENT_ANALYSIS_VERIFY_MAX_PER_PASS")))
    except Exception:
        pass
    try:
        from shared import config as _cfg
        return max(0, int(getattr(_cfg, "AGENT_ANALYSIS_VERIFY_MAX_PER_PASS",
                                  _DEFAULT_MAX_PER_PASS) or 0))
    except Exception:
        return 0


def _savepoint(cur):
    """조회·적재 실패가 호출측 트랜잭션을 오염시키지 않게 한다.

    ⚠ load-bearing: 이 모듈은 워커와 같은 커넥션·커서를 쓴다. 신규 테이블이 아직 없는 배포
    창에서 SELECT 가 실패하면 non-autocommit 커넥션은 트랜잭션 전체가 aborted 가 된다
    (feature-0031·0033 에서 같은 결함을 두 번 겪었다). autocommit 이면 no-op 이다."""
    import contextlib

    @contextlib.contextmanager
    def _sp():
        name = "sp_analysis_verify"
        opened = False
        try:
            cur.execute(f"SAVEPOINT {name}")
            opened = True
        except Exception:
            opened = False
        try:
            yield
        except Exception:
            if opened:
                try:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
                except Exception:
                    pass
            raise
        else:
            if opened:
                try:
                    cur.execute(f"RELEASE SAVEPOINT {name}")
                except Exception:
                    pass

    return _sp()


def pending_targets(cur, limit: int) -> list:
    """판정 대상. 조회 실패는 빈 목록.

    분석문과 증거가 **둘 다** 있고 그 분석문 버전으로 아직 판정되지 않은 것. 증거의 수집
    깊이(stage)가 깊은 것부터 — 얕은 증거로 내린 판정은 정보가 적다.
    """
    if limit <= 0:
        return []
    try:
        with _savepoint(cur):
            # ⚠ 기존 판정의 `analysis_hash` 를 **함께 가져온다**(codex P1). "판정 행이 있으면
            #   제외"로 두면 분석문이 갱신돼도 옛 판정이 남아 재판정되지 않는다 — 문서에 적은
            #   "분석 갱신 시 자연히 미검증" 계약과 정반대로 동작한다. 해시 비교는 호출측이
            #   파이썬에서 한다(SQL 로 분석문 해시를 계산할 수 없다).
            #   `store_verdict` 가 노드당 1행만 유지하므로 이 LEFT JOIN 은 행을 늘리지 않는다.
            cur.execute(
                "SELECT j.scope_key, j.node_key, j.node_name, j.analysis, "
                "       m.schema_name, m.table_name, m.stage, v.analysis_hash "
                "FROM node_analysis_jobs j "
                "JOIN metadata_table_stats m "
                "  ON j.node_key = m.scope_key || ':' || m.schema_name || '.' || m.table_name "
                "LEFT JOIN node_analysis_verdicts v "
                "  ON v.scope_key = j.scope_key AND v.node_key = j.node_key "
                "WHERE j.status = 'done' AND j.node_label = 'Table' AND j.analysis IS NOT NULL "
                "  AND m.error IS NULL "
                "ORDER BY m.stage DESC, j.updated_at DESC "
                "LIMIT %s",
                (int(limit) * 5,))
            return cur.fetchall() or []
    except Exception as exc:
        _log.debug("verify_targets_unavailable err=%r", exc)
        return []


def load_evidence(cur, scope_key, schema_name, table_name, stage) -> dict:
    """판정 payload 의 evidence 블록. 조회 실패는 빈 dict(=대상에서 제외된다)."""
    try:
        with _savepoint(cur):
            cur.execute(
                # ⚠ 여기서도 `error IS NULL` 을 본다(codex P1): 대상 조회와 이 조회 사이에
                #   수집 실패가 기록되면 **실패한 통계로 판정**하게 된다.
                "SELECT row_count_est, column_count, pk_columns, index_columns, fk_out, fk_in, "
                "       sampled_rows "
                "FROM metadata_table_stats "
                "WHERE scope_key=%s AND schema_name=%s AND table_name=%s AND error IS NULL",
                (scope_key, schema_name, table_name))
            trow = cur.fetchone()
            if not trow:
                return {}
            cur.execute(
                "SELECT column_name, data_type, is_nullable, distinct_est, null_ratio, "
                "       num_min, num_max, len_avg, value_pattern, unique_in_sample "
                "FROM metadata_column_stats "
                "WHERE scope_key=%s AND schema_name=%s AND table_name=%s "
                "ORDER BY column_name LIMIT %s",
                (scope_key, schema_name, table_name, _EVIDENCE_COLUMN_CAP))
            crows = cur.fetchall() or []
    except Exception as exc:
        _log.debug("verify_evidence_unavailable %s.%s err=%r", schema_name, table_name, exc)
        return {}

    ev = {"stage": int(stage or 0), "sampled_rows": int(trow[6] or 0)}
    if trow[0] is not None:
        ev["row_count_est"] = int(trow[0])
    if trow[1]:
        ev["column_count"] = int(trow[1])
    if trow[2]:
        ev["pk_columns"] = [str(x) for x in trow[2]][:16]
    if trow[3]:
        ev["indexed_columns"] = [str(x) for x in trow[3]][:24]
    if trow[4] is not None:
        ev["fk_out"] = int(trow[4])
    if trow[5] is not None:
        ev["fk_in"] = int(trow[5])
    cols = []
    for r in crows:
        item = {"name": str(r[0])}
        if r[1]:
            item["type"] = str(r[1])
        if r[2] is not None:
            item["nullable"] = bool(r[2])
        if r[3] is not None:
            item["distinct_est"] = int(r[3])
        if r[4] is not None:
            item["null_ratio"] = float(r[4])
        if r[5] is not None:
            item["min"] = float(r[5])
        if r[6] is not None:
            item["max"] = float(r[6])
        if r[7] is not None:
            item["len_avg"] = float(r[7])
        if r[8]:
            item["pattern"] = str(r[8])
        if r[9]:
            item["unique_in_sample"] = True
        cols.append(item)
    if cols:
        ev["columns"] = cols
    return ev


def parse_analysis(text) -> dict:
    """분석문 JSON → 판정 payload 의 analysis 블록. 파싱 불가면 빈 dict."""
    try:
        obj = json.loads(text) if isinstance(text, (str, bytes)) else text
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    out = {}
    for k in ("summary", "relationships", "usage", "caveats"):
        v = " ".join(str(obj.get(k) or "").split())
        if v:
            out[k] = v[:_ANALYSIS_CLIP]
    return out


def normalize_verdict(res) -> tuple:
    """LLM 응답 → (verdict, reason). **인정할 수 없으면 (None, '')**.

    ⚠ 미지의 verdict 문자열을 `supported` 로 보정하지 않는다 — 판정자가 계약을 벗어난 응답을
    했다면 그것은 판정이 아니다. 모르면 기록하지 않는다.
    """
    if not isinstance(res, dict):
        return None, ""
    v = str(res.get("verdict") or "").strip().lower()
    if v not in VERDICTS:
        return None, ""
    reason = " ".join(str(res.get("reason") or "").split())[:500]
    # ⚠ 근거 없는 판정은 판정이 아니다(codex P1). 프롬프트는 "어떤 숫자가 판정을 갈랐는지"를
    #   한 문장으로 요구하는데, 그것이 없으면 사람이 그 판정을 재확인할 방법이 없다 —
    #   근거 없는 확인 도장이야말로 이 층이 저지를 수 있는 최악의 실패다.
    if not reason:
        return None, ""
    return v, reason


def store_verdict(cur, scope_key, node_key, a_hash, verdict, reason, stage, model) -> bool:
    """판정 적재. 반환 True=저장됨. 실패는 False(미검증으로 남는다)."""
    try:
        with _savepoint(cur):
            # 노드당 **1행만** 유지한다 — 분석이 갱신될 때마다 행이 쌓이면 무한 증식이고,
            # 대상 조회의 LEFT JOIN 도 행을 늘려 같은 노드가 여러 번 판정된다.
            cur.execute(
                "DELETE FROM node_analysis_verdicts "
                "WHERE scope_key=%s AND node_key=%s AND analysis_hash <> %s",
                (scope_key, node_key, a_hash))
            cur.execute(
                "INSERT INTO node_analysis_verdicts "
                "(scope_key, node_key, analysis_hash, verdict, reason, evidence_stage, model, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,now()) "
                "ON CONFLICT (scope_key, node_key, analysis_hash) DO UPDATE SET "
                " verdict=EXCLUDED.verdict, reason=EXCLUDED.reason, "
                " evidence_stage=EXCLUDED.evidence_stage, model=EXCLUDED.model, "
                " created_at=EXCLUDED.created_at",
                (scope_key, node_key, a_hash, verdict, reason or None,
                 int(stage or 0), str(model or "")[:64]))
        return True
    except Exception as exc:
        _log.debug("verify_store_failed node=%s err=%r", node_key, exc)
        return False


def run_verification_pass(conn=None, limit=None) -> dict:
    """판정 pass. 반환 telemetry.

    `conn` 이 없으면 **자체 agent_kb PG 연결**을 연다(`node_analysis.process_pending` 과 동형) —
    insight tick 의 `mem_conn` 은 agent_memory 라 여기서 쓸 수 없다.

    실패는 전부 **미검증**(행 없음)으로 남는다 — 이 함수는 어떤 경로로도 확인되지 않은 분석문에
    확인 도장을 찍지 않는다.
    """
    rep = {"checked": 0, "supported": 0, "contradicted": 0, "unverifiable": 0,
           "skipped": None}
    if not enabled():
        rep["skipped"] = "disabled"
        return rep
    # 호출측 limit 은 설정 상한을 **넘을 수 없다**(codex P2) — 인자로 상한을 우회하면 knob 이
    #   거짓 컨트롤이 된다.
    configured = max_per_pass()
    cap = configured if limit is None else min(configured, max(0, int(limit)))
    if cap <= 0:
        rep["skipped"] = "cap_zero"
        return rep
    # ⚠ 예산 모듈을 못 읽으면 **중단한다**(codex P2). 이 모듈의 원칙은 "모르면 하지 않는다"이고,
    #   그것은 지출에도 적용된다. 다른 fail-soft 와 방향이 반대인 이유다.
    try:
        from shared import llm_budget as _lb
    except Exception:
        rep["skipped"] = "budget_unavailable"
        return rep
    if not _lb.allowed(conn):
        rep["skipped"] = "llm_token_budget"
        return rep
    try:
        from . import llm as _llm
    except Exception:
        rep["skipped"] = "llm_unavailable"
        return rep
    try:
        from shared import resource_budget as _rb
    except Exception:
        rep["skipped"] = "budget_unavailable"
        return rep

    # ⚠ `cursor()` 도 try **안**에서 얻는다 — 밖에 두면 커넥션이 죽었을 때 예외가 워커로
    #   전파돼 분석 tick 이 함께 죽는다. 이 계열의 실수를 feature-0031·0033·0034 에서
    #   반복했다: **자원 획득은 언제나 try 안**.
    owned = False
    if conn is None:
        try:
            from shared import db as _db
            conn = _db._pg_connect()
            owned = conn is not None
        except Exception as exc:
            _log.debug("verify_conn_failed err=%r", exc)
            conn = None
    if conn is None:
        rep["skipped"] = "pg_unavailable"
        return rep
    cur = None
    try:
        cur = conn.cursor()
        rows = pending_targets(cur, cap)
        if not rows:
            rep["skipped"] = "no_targets"
            return rep
        try:
            from shared import config as _cfg
            model = str(getattr(_cfg, "AGENT_NODE_ANALYSIS_MODEL", "") or "")
        except Exception:
            model = ""
        for (scope_key, node_key, node_name, analysis, schema_name, table_name,
             stage, judged_hash) in rows:
            if rep["checked"] >= cap:
                break
            # 배치마다 토큰 예산을 다시 본다 — 긴 pass 도중 소진되면 그 자리에서 멈춘다.
            if not _lb.allowed(conn):
                _log.info("분석 검증 중단 — 백그라운드 LLM 토큰 예산 소진(다음 pass 재시도)")
                break
            a_block = parse_analysis(analysis)
            if not a_block:
                continue     # 파싱 불가 분석문은 판정 대상이 아니다(미검증으로 남김)
            a_hash = analysis_hash(analysis)
            if not a_hash:
                continue
            if judged_hash and str(judged_hash) == a_hash:
                continue     # 이 분석문 버전은 이미 판정됐다
            ev = load_evidence(cur, scope_key, schema_name, table_name, stage)
            if not ev:
                continue     # 증거 없음 = 대조 불가. 판정하지 않는다
            payload = {"task": "analysis_verify",
                       "table": f"{schema_name}.{table_name}",
                       "analysis": a_block, "evidence": ev}
            with _rb.acquire("llm") as _ok:
                if not _ok:
                    _log.info("분석 검증 보류 — 공유 LLM 예산 여유 없음(다음 pass 재시도)")
                    break
                res = _verify_call(_llm, payload, scope_key)
            verdict, reason = normalize_verdict(res)
            if verdict is None:
                continue     # ⚠ 판정 실패 = 미검증. 도장을 찍지 않는다
            if store_verdict(cur, scope_key, node_key, a_hash, verdict, reason, stage, model):
                rep["checked"] += 1
                rep[verdict] = rep.get(verdict, 0) + 1
    except Exception as exc:
        _log.warning("analysis_verify pass 실패(다음 pass 재시도): %r", exc)
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if owned and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if rep["checked"]:
        _log.info("분석 검증 pass — 판정 %s (뒷받침 %s · 모순 %s · 판정불가 %s)",
                  rep["checked"], rep["supported"], rep["contradicted"], rep["unverifiable"])
    return rep


def _verify_call(_llm, payload, scope_key):
    """판정 LLM 1회. 예외는 None(= 미검증)."""
    try:
        return _llm.llm_verify_analysis(payload, scope_key=scope_key)
    except Exception as exc:
        _log.warning("llm_verify_analysis 실패(미검증으로 남김): %r", exc)
        return None
