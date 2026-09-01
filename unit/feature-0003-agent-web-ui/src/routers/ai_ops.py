"""routers/ai_ops.py — AI 운영 관제 패널 API (TASK-AIOPS).

관리 콘솔 > 감사 > AI 운영 현황 탭의 데이터 소스. `GET /api/admin/ai-ops`.
권한: `console.aiops.read` (admin 전용). **읽기 전용** — 파괴적 쓰기 없음.

설계:
  - 상태 축(worst-of 롤업): provider / ask-worker / insight-worker / datasource-scan.
    ask-worker 는 `_is_worker_mode()==False`(inprocess)면 **N/A** 로 롤업에서 제외
    (정상 inprocess 배포를 '중단'으로 오판 방지 — heartbeat 부재가 정상이므로).
  - 배너 = 축 worst-of. + KPI / Attention / 최근 활동 feed / 카테고리 드릴다운 / 계측 커버리지.
  - PG(agent_runtime) 집계는 **부분 degrade** — PG 미가용도 200 반환, PG 의존 지표만 unknown/빈값.
    admin_usage 의 503-전체실패 패턴을 쓰지 않는다(MySQL/heartbeat 기반 배너는 살아남음).
  - PG read 는 `_pg_connect_ro`(least-privilege). `llm_usage.latency_ms` 컬럼 부재(마이그 전)도
    쿼리별 try/except 로 삼켜 부분 degrade.
  - uniform `import app` + `app.X` 동적 접근(테스트 monkeypatch 보존, admin_usage 패턴). DI seam
    (require_permission/get_conn)도 `Depends(app.X)` — app 정본과 동일 객체(dependency_overrides 정합).

순환 안전: app 정의 후 맨 끝 include_router.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app
from shared.model_catalog import canonical_usage_model, canonical_usage_model_sql

INCLUDE_ORDER = 220  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()

_log = logging.getLogger(__name__)

# 상태 severity — worst-of 롤업용(높을수록 나쁨). "na"(해당없음)는 롤업에서 제외.
_SEV = {"ok": 0, "unknown": 1, "degraded": 2, "down": 3}
_SEV_LABEL = {"ok": "정상", "unknown": "부분 가시", "degraded": "저하", "down": "중단", "na": "해당 없음"}

# ── 외부AI 운영축 상수 (TASK-20260901T110000) ─────────────────────────────────
# 이름 리터럴을 여기 다시 적지 않는다 — 정본이 바뀌는 날 관제만 낡아, 있는 기능을
# "없다" 고 표시하게 된다(그 오표시는 사용자에게 재설치를 시킨다).
try:
    from shared.bridge_tasks import (
        RUNNER_FEATURE_CONSOLE_JOBS as _CONSOLE_JOBS_FEATURE,
        RUNNER_FEATURE_SELF_REVIEW as _SELF_REVIEW_FEATURE,
    )
except Exception:  # pragma: no cover — import 실패 시에도 라우터는 서야 한다
    _CONSOLE_JOBS_FEATURE, _SELF_REVIEW_FEATURE = "console_jobs", "self_review"
try:
    from shared.self_review import AXIS_LABELS as _AXIS_LABELS
except Exception:  # pragma: no cover
    _AXIS_LABELS = {}


# ── 상태 축 ─────────────────────────────────────────────────────────────────────
def _provider_axis() -> dict:
    """LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health cheap read).

    ⚠ **차단 중에는 롤업에서 빠진다** (`state="na"`, TASK-20260901T110000).

    이 축은 서버 계정으로 LLM 을 부를 때의 외부 제한을 말한다. 게이트가 닫힌 배포에서는
    아무도 그 경로를 쓰지 않으므로, 여기서 `degraded` 가 나와도 **서비스에는 아무 일도
    일어나지 않는다**. 그런데 종전에는 그 값이 종합 배너의 worst-of 에 참여해, 쓰지 않는
    provider 의 제한 하나가 화면 전체를 '저하' 로 물들였다 — 그리고 그 '저하' 는 운영자가
    실제로 확인해야 할 브리지 신호를 같은 색으로 덮었다.

    다만 **원본 상태는 계속 싣는다**(`raw_state`). 게이트를 되돌리는 날 되살아날 제한이라,
    전환 전에 그것을 확인할 수 있어야 한다 — 롤업에서 빼는 것과 감추는 것은 다르다.
    """
    # feature-0043(codex 리뷰 P2): **관리자 관제는 마스킹된 값을 보면 안 된다.**
    # 대화 UI 는 차단 중 provider 상태를 non-restricted 로 덮는다(전송에 영향이 없고, 복구 ping
    # 이 불가능해 배너가 영구 고착되므로). 그 마스킹이 이 화면까지 오면 운영자는 "정상" 만 보고,
    # 게이트를 되돌리는 순간 숨어 있던 제한이 되살아난다 — 전환 전 위험 확인이 불가능해진다.
    # 그래서 여기서는 **원본**을 읽고, 차단 사실은 별도 필드로 함께 싣는다.
    blocked = False
    try:
        raw = app._read_llm_provider_status_admin() or {}
        blocked = bool(raw.get("server_llm_blocked"))
        st = str(raw.get("state") or "unknown").lower()
    except Exception:
        st = "unknown"
    if st == "ok":
        state = "ok"
    elif st in ("down", "error", "unavailable"):
        state = "down"
    elif st == "unknown":
        state = "unknown"
    else:  # restricted / throttled / credential_expired 등
        state = "degraded"
    detail = f"state={st}"
    if blocked:
        # 차단 중임을 **관제에는 명시**한다. 이걸 빼면 운영자는 degraded 를 보고 "왜 아무도
        # 영향을 안 받지?" 를, 반대로 ok 를 보고 "정말 괜찮은가?" 를 판단할 근거가 없다.
        detail += " · 서버 계정 LLM 미사용 — 이 축은 지금 서비스에 영향을 주지 않습니다"
        return {"key": "provider", "label": "서버 계정 LLM (미사용)", "state": "na",
                "detail": detail, "raw_state": state, "server_llm_blocked": True}
    return {"key": "provider", "label": "LLM 제공자", "state": state, "detail": detail,
            "raw_state": state, "server_llm_blocked": blocked}


def _bridge_axis(conn) -> dict:
    """feature-0043 TASK-20260831T100000 — **외부 AI 브리지** 상태 축.

    ## 왜 이 축이 필요한가

    서버 계정 LLM 이 차단된 뒤 실제 추론은 전부 개인 AI 러너가 한다. 그런데 관제에는 그
    사실을 볼 자리가 없었다 — `LLM 제공자` 축은 쓰이지 않는 provider 를 계속 보고했고,
    운영자는 "누가 연결돼 있나 / 대기가 밀렸나" 를 어디서도 확인할 수 없었다.

    이 축이 없으면 **차단 상태의 정상/비정상이 구분되지 않는다**: 러너 0대(아무 질문도
    처리되지 않음)와 러너 5대(정상 운영)가 화면에서 똑같이 보인다.

    ## 판정

    | 상태 | 조건 | 뜻 |
    |---|---|---|
    | `na` | 게이트 열림 | 브리지를 쓰지 않는 배포 — 롤업에서 제외 |
    | `down` | 듣는 러너 0 | 들어오는 질문이 **아무도 처리하지 못한다** |
    | `degraded` | 점유되지 않은 채 오래된 작업 있음 | 러너는 있는데 소화하지 못한다 |
    | `ok` | 그 외 | |

    실패는 `unknown` — 조회 실패를 `ok` 로 접으면 관제가 침묵으로 안심시킨다.
    """
    from shared.bridge_tasks import (
        KIND_JOB, ORIGIN_BATCH, RUNNER_FEATURE_CONSOLE_JOBS, STATUS_OPEN,
    )
    from shared.llm_gate import server_llm_enabled

    if server_llm_enabled():
        return {"key": "bridge", "label": "외부 AI 브리지", "state": "na",
                "detail": "서버 계정 LLM 사용 중 (브리지 미사용)", "metrics": {}}
    if conn is None:
        # MySQL 핸들 자체가 없다 — 이것은 **브리지의 사실이 아니라 핸들러의 상태**다.
        # `unknown`(롤업 참여)으로 두면 DB 미가용 배포에서 종합 상태가 브리지 때문에
        # 나빠진 것처럼 보인다. 다른 축(`_ask_worker_axis` 의 inprocess)이 같은 상황에서
        # `na` 를 쓰는 것과 같은 이유로 롤업에서 빠진다 — 감추는 것이 아니라, DB 미가용은
        # 이 화면의 다른 곳이 이미 말한다.
        return {"key": "bridge", "label": "외부 AI 브리지", "state": "na",
                "detail": "DB 미가용 — 브리지 상태를 평가할 수 없습니다", "metrics": {}}

    metrics = {"connected_accounts": 0, "listening_runners": 0, "console_capable": 0,
               "open_tasks": 0, "working_tasks": 0, "stale_tasks": 0,
               "open_jobs": 0, "job_failures": 0}
    try:
        import oauth_store as _store

        cur = conn.cursor()
        try:
            # 연결(살아 있는 토큰) · 듣고 있음(최근 하트비트) · 콘솔 작업 가능(기능 신고).
            # 집계는 `oauth_store` 안에서 한다 — 살아 있음의 술어는 그 모듈의 것이고,
            # 여기로 복사해 오면 인증과 관제가 서로 다른 "살아 있음" 을 보게 된다(P0-R).
            runners = _store.count_live_runners(cur, RUNNER_FEATURE_CONSOLE_JOBS)
            metrics["connected_accounts"] = runners["connected"]
            metrics["listening_runners"] = runners["listening"]
            metrics["console_capable"] = runners["with_feature"]

            # 대기·처리중·정체. `stale` 은 **미점유인 채로** 오래된 것 — 점유된 것은
            # 개인 머신에서 돌고 있는 정상 상태라 여기 섞으면 거짓 경보가 된다.
            cur.execute(
                "SELECT "
                "  SUM(Status = %s AND ClaimedBy IS NULL), "
                "  SUM(Status = %s AND ClaimedBy IS NOT NULL), "
                "  SUM(Status = %s AND ClaimedBy IS NULL "
                "      AND CreatedAt < DATE_SUB(NOW(), INTERVAL 10 MINUTE)), "
                "  SUM(Status = %s AND Kind = %s), "
                "  SUM(Kind = %s AND JobApplyError IS NOT NULL) "
                "FROM WebAiTasks WHERE Origin IN ('web', %s)",
                (STATUS_OPEN, STATUS_OPEN, STATUS_OPEN, STATUS_OPEN, KIND_JOB,
                 KIND_JOB, ORIGIN_BATCH))
            r2 = cur.fetchone() or (0, 0, 0, 0, 0)
            metrics["open_tasks"] = int(r2[0] or 0)
            metrics["working_tasks"] = int(r2[1] or 0)
            metrics["stale_tasks"] = int(r2[2] or 0)
            metrics["open_jobs"] = int(r2[3] or 0)
            metrics["job_failures"] = int(r2[4] or 0)
        finally:
            cur.close()
    except Exception as exc:  # noqa: BLE001
        _log.warning("[ai-ops] 브리지 축 조회 실패: %r", exc)
        return {"key": "bridge", "label": "외부 AI 브리지", "state": "unknown",
                "detail": "상태를 읽지 못했습니다", "metrics": metrics}

    if metrics["listening_runners"] == 0:
        state = "down"
        detail = ("듣고 있는 개인 AI 러너가 없습니다 — 들어오는 질문이 처리되지 않습니다"
                  f" (연결 계정 {metrics['connected_accounts']})")
    elif metrics["stale_tasks"] > 0:
        state = "degraded"
        detail = (f"러너 {metrics['listening_runners']} · 10분 넘게 아무도 가져가지 않은 질문 "
                  f"{metrics['stale_tasks']}건")
    else:
        state = "ok"
        detail = (f"러너 {metrics['listening_runners']} (콘솔 작업 가능 {metrics['console_capable']})"
                  f" · 대기 {metrics['open_tasks']} · 처리중 {metrics['working_tasks']}")
    return {"key": "bridge", "label": "외부 AI 브리지", "state": state,
            "detail": detail, "metrics": metrics}


def _delegated_jobs(conn, limit: int = 30) -> list[dict]:
    """위임된 콘솔 작업의 **상태와 소유 계정** (사용자 결정 2026-08-31 명시 표기 요구).

    > "해당 작업이 어떤 상태인지, 어느 계정에서 진행되고 있는지 등. 명시적인 표기가
    >  가능해야 합니다."

    소유(`AccountId` — 누가 시켰나)와 수행(`ClaimedBy` — 누가 하고 있나)을 **나눠서** 준다.
    관리자 작업은 둘이 같지만 배치는 다르다(워커가 열고 아무 러너나 집는다) — 합치면
    "내가 시킨 적 없는 작업이 내 이름으로" 또는 그 반대가 된다.

    실패는 빈 목록 + 로그. 이 표가 비는 것보다 관제 전체가 500 이 되는 쪽이 나쁘다.
    """
    from shared.bridge_tasks import KIND_JOB, job_label

    out: list[dict] = []
    if conn is None:
        return out
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT t.TaskId, t.JobKind, t.Status, t.Origin, t.CreatedAt, t.ClaimedAt, "
                "       t.SubmittedAt, t.JobAppliedAt, t.JobApplyError, "
                "       owner.Username, worker.Username "
                "FROM WebAiTasks t "
                "LEFT JOIN WebAccounts owner  ON owner.Id  = t.AccountId "
                "LEFT JOIN WebAccounts worker ON worker.Id = t.ClaimedBy "
                "WHERE t.Kind = %s "
                "ORDER BY t.CreatedAt DESC LIMIT %s",
                (KIND_JOB, int(limit)))
            for r in (cur.fetchall() or []):
                out.append({
                    "task_id": str(r[0] or ""),
                    "job_kind": str(r[1] or ""),
                    "label": job_label(r[1]),
                    "status": str(r[2] or ""),
                    "origin": str(r[3] or ""),
                    "created_at": _iso(r[4]),
                    "claimed_at": _iso(r[5]),
                    "submitted_at": _iso(r[6]),
                    "applied_at": _iso(r[7]),
                    # 실패 사유를 감추지 않는다 — "제출됐는데 반영 안 됨" 은 화면이 말해야
                    # 하는 상태이고, 감추면 운영자는 성공으로 읽는다.
                    "apply_error": str(r[8] or ""),
                    "owner": str(r[9] or ""),      # 누가 시켰나 (배치는 비어 있을 수 있다)
                    "worker": str(r[10] or ""),    # 누가 하고 있나 / 했나
                })
        finally:
            cur.close()
    except Exception as exc:  # noqa: BLE001
        _log.warning("[ai-ops] 위임 작업 목록 조회 실패: %r", exc)
    return out


def _iso(v) -> str:
    """datetime → ISO 문자열. 값이 없거나 datetime 이 아니면 빈 문자열."""
    return v.isoformat() if hasattr(v, "isoformat") else ""


def _runner_roster(conn, limit: int = 100) -> dict:
    """계정별 **러너 명부** — 누가 연결했고, 지금 듣고 있고, 무엇을 다룰 줄 아는가.

    ## 왜 수가 아니라 명부인가 (TASK-20260901T110000)

    서버가 추론하지 않는 배포에서 운영자가 실제로 받는 질문은 "이 사람 질문이 왜 처리가
    안 되나" 다. 「러너 3대」로는 답할 수 없다 — 답은 계정 단위 사실이고, 그 사실마다
    **조치가 다르다**: 토큰 없음(연결 안내) · 토큰 있고 미수신(러너 기동) · 수신하는데
    기능 미신고(갱신) · 신고했는데 지문 불일치(재설치).

    배포본 지문과 대조해 `stale_build` 를 함께 준다. 그 대조가 없으면 「재설치했는데 그대로」
    (2026-08-31 사용자 제보)를 화면이 다시 설명하지 못한다.
    """
    out: dict = {"available": False, "items": [], "deployed_build": ""}
    if conn is None:
        out["reason"] = "DB 미가용 — 러너 명부를 조회할 수 없습니다."
        return out
    try:
        import oauth_store as _store

        cur = conn.cursor()
        try:
            items = _store.list_live_runners(cur, limit=limit)
        finally:
            cur.close()
    except Exception as exc:  # noqa: BLE001
        # `available` 은 False 로 남는다 — 화면이 **「러너 0대」가 아니라 「조회 불가」**로
        # 말한다. 둘을 합치면 조회 실패 한 번이 "아무도 처리하지 못합니다" 라는 장애 선언이
        # 된다(이 cycle 이 없애려던 오독과 같은 형태).
        _log.warning("[ai-ops] 러너 명부 조회 실패: %r", exc)
        out["reason"] = "러너 명부를 읽지 못했습니다."
        return out

    deployed = ""
    try:
        # 서버가 **배포 중인** 러너 파일의 지문. 하트비트의 지문과 다르면 그 사용자는
        # 옛 파일을 돌리고 있다. 판정은 이미 `ai_tools` 가 하고 있으므로 그 함수를 부른다 —
        # 여기서 다시 계산하면 두 곳의 "배포본" 이 갈릴 준비를 마친다.
        from routers.ai_tools import _deployed_runner_build

        deployed = str(_deployed_runner_build() or "")
    except Exception:
        deployed = ""
    for it in items:
        build = str(it.get("runner_build") or "")
        # 둘 중 하나라도 모르면 **대조하지 않는다**(False). 모르는 것을 'stale' 로 적으면
        # 멀쩡한 러너에게 재설치를 시킨다.
        it["stale_build"] = bool(deployed and build and build != deployed)
        it["console_capable"] = _CONSOLE_JOBS_FEATURE in (it.get("features") or [])
        it["self_review_capable"] = _SELF_REVIEW_FEATURE in (it.get("features") or [])
    out["available"] = True
    out["items"] = items
    out["deployed_build"] = deployed
    return out


def _self_review_stats(days: int) -> dict:
    """외부 AI **자가 검증** 집계 (`redteam_reviews.source='external'`).

    서버측 이력(`source='server'`)과 **합산하지 않는다.** 서버 검증은 게이트가 닫힌 뒤
    늘지 않는 과거 기록이고 외부 검증은 현행이다 — 합치면 "검증이 줄고 있다" 는 착시가
    생기는데, 실제로 일어난 일은 주체가 바뀐 것뿐이다.

    컬럼 부재(0057 미적용 이미지)는 `available: False` — 0 으로 접으면 "검증이 하나도 없다"
    로 읽히고, 그것은 마이그레이션 상태가 아니라 운영 상태에 대한 거짓말이 된다.
    """
    out: dict = {"available": False, "reviews": 0, "pass_count": 0, "revise_count": 0,
                 "block_count": 0, "warn_count": 0, "by_axis": []}
    try:
        from shared.db import _pg_connect_ro

        pg = _pg_connect_ro()
    except Exception:
        out["reason"] = "계측 저장소(PG)를 조회할 수 없습니다."
        return out
    if pg is None:
        out["reason"] = "계측 저장소(PG)를 조회할 수 없습니다."
        return out
    try:
        with pg.cursor() as cur:
            win = f"now() - interval '{int(days)} days'"
            cur.execute(
                "SELECT count(*), "
                "       count(*) FILTER (WHERE verdict = 'pass'), "
                "       count(*) FILTER (WHERE verdict = 'revise'), "
                "       COALESCE(sum(block_count), 0), COALESCE(sum(warn_count), 0) "
                "FROM agent_runtime.redteam_reviews "
                f"WHERE source = 'external' AND created_at >= {win}")
            r = cur.fetchone() or (0, 0, 0, 0, 0)
            out.update({"available": True, "reviews": int(r[0] or 0),
                        "pass_count": int(r[1] or 0), "revise_count": int(r[2] or 0),
                        "block_count": int(r[3] or 0), "warn_count": int(r[4] or 0)})
            # 축별 분포 — "어디가 반복해서 걸리나" 는 프롬프트·데이터 어느 쪽을 고칠지의 신호다.
            cur.execute(
                "SELECT f->>'axis' AS axis, f->>'severity' AS sev, count(*) "
                "FROM agent_runtime.redteam_reviews r, "
                "     LATERAL jsonb_array_elements(COALESCE(r.findings, '[]'::jsonb)) AS f "
                f"WHERE r.source = 'external' AND r.created_at >= {win} "
                "GROUP BY 1, 2 ORDER BY 3 DESC")
            fold: dict[str, dict] = {}
            for row in (cur.fetchall() or []):
                axis = str(row[0] or "")
                if not axis:
                    continue
                e = fold.setdefault(axis, {"axis": axis, "label": _AXIS_LABELS.get(axis, axis),
                                           "block": 0, "warn": 0})
                if str(row[1] or "") == "BLOCK":
                    e["block"] += int(row[2] or 0)
                else:
                    e["warn"] += int(row[2] or 0)
            out["by_axis"] = sorted(fold.values(),
                                    key=lambda x: (x["block"], x["warn"]), reverse=True)
    except Exception:
        # 0057 미적용 배포 — 컬럼이 없다. 조용히 0 으로 접지 않는다(위 docstring).
        _log.debug("ai_ops self-review stats query failed (source 컬럼 부재?)", exc_info=True)
        out["available"] = False
        out["reason"] = "자가 검증 원장이 아직 준비되지 않았습니다(마이그레이션 대기)."
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return out


def _ask_worker_axis(conn) -> dict:
    """요청 처리(ask) 워커 heartbeat. inprocess 모드면 N/A(롤업 제외).
    임계: age≤60s 정상 / 60<age≤120s 저하 / >120s·부재 중단 (WEB_ASK_WORKER_READY_MAX_AGE_SEC=60 정합)."""
    try:
        worker_mode = bool(app._is_worker_mode())
    except Exception:
        worker_mode = False
    if not worker_mode:
        return {"key": "ask_worker", "label": "요청 처리 워커", "state": "na",
                "detail": "inprocess 모드 (별도 워커 미사용)", "age_sec": None}
    try:
        age = app._ask_worker_age_sec(conn)
    except Exception:
        age = None
    if age is None:
        return {"key": "ask_worker", "label": "요청 처리 워커", "state": "down",
                "detail": "heartbeat 없음", "age_sec": None}
    if age <= 60:
        state = "ok"
    elif age <= 120:
        state = "degraded"
    else:
        state = "down"
    return {"key": "ask_worker", "label": "요청 처리 워커", "state": state,
            "detail": f"heartbeat {int(age)}s 전", "age_sec": int(age)}


def _insight_worker_axis(conn) -> dict:
    """insight 워커 heartbeat. 임계: alive(status ok/skip_locked & age≤max(30,STALE)) 정상 /
    age≤60s 저하 / 그 외·부재 중단. (_insight_worker_liveness 반환 재사용)."""
    try:
        liv = app._insight_worker_liveness(conn) or {}
    except Exception:
        liv = {}
    age = liv.get("age_sec")
    status = str(liv.get("status") or "")
    if liv.get("alive"):
        state = "ok"
    elif age is None:
        state = "down"
    elif age <= 60:
        state = "degraded"
    else:
        state = "down"
    detail = (f"status={status or '?'}" +
              (f", {int(age)}s 전" if age is not None else ", heartbeat 없음"))
    return {"key": "insight_worker", "label": "인사이트 워커", "state": state, "detail": detail,
            "age_sec": (int(age) if age is not None else None)}


def _datasource_axis() -> dict:
    """insight 스캔 관점 datasource health(PG agent_runtime.datasource_health) worst-of.
    매핑: ok→정상 / unstable·degraded·error·partial→저하 / circuit_open·perm_failed·failed→중단.
    스캔 이력 없음/PG 미가용({})은 unknown(부분 가시)."""
    try:
        health = app._read_insight_datasource_health() or {}
    except Exception:
        health = {}
    if not health:
        return {"key": "datasource", "label": "데이터소스 스캔", "state": "unknown",
                "detail": "스캔 상태 미가용", "scopes": 0}
    worst = "ok"
    deg = 0
    down = 0
    for _scope, h in health.items():
        st = str(h.get("status") or "").lower()
        outcome = str(h.get("scan_outcome") or "").lower()
        if outcome == "circuit_open" or st in ("perm_failed", "failed"):
            cur = "down"; down += 1
        elif st in ("unstable", "degraded") or outcome in ("error", "partial"):
            cur = "degraded"; deg += 1
        elif st == "ok":
            cur = "ok"
        else:
            cur = "degraded"; deg += 1
        if _SEV.get(cur, 0) > _SEV.get(worst, 0):
            worst = cur
    return {"key": "datasource", "label": "데이터소스 스캔", "state": worst,
            "detail": f"{len(health)}개 스코프 (저하 {deg}, 중단 {down})", "scopes": len(health)}


# ── 계측 커버리지 (정직 노출 — '전체 비용' 오해 방지) ────────────────────────────
_COVERAGE = {
    "instrumented": [
        "에이전트 추론", "보조 추론(검증·요약·분류·주제·SQL수정)", "인사이트 분석(스키마·테이블·계정·노드)",
        "용어사전 후보", "프롬프트 자동생성(수동 + 자율 sweep)", "메타데이터 자동완성",
    ],
    "uninstrumented": [
        {"name": "임베딩 (backfill·쿼리·샘플 3경로)", "reason": "embeddings.create 응답에 usage 필드 없음(SDK 한계)"},
        {"name": "LLM provider health probe", "reason": "헬스체크 전용 — 의도적 계측 제외"},
    ],
    "note": "위 미계측 활동은 llm_usage 에 기록되지 않아 KPI·비용 합계에서 제외됩니다('전체 비용' 아님).",
}

#: 서버 계정 LLM 이 차단된 배포의 커버리지. 위 목록을 그대로 보이면 **하지 않는 일을
#: "계측됨" 으로 나열**하게 된다 — 커버리지 표의 목적이 정직 노출인데 그 자리에서 거짓을
#: 말하는 셈이다.
_COVERAGE_EXTERNAL = {
    "instrumented": [
        "외부 AI 도구 호출(조회·조사 — 호출·행수·바이트)",
        "브리지 작업(대화 질문·콘솔 위임·배경 배치의 개설·점유·제출·반영)",
        "외부 AI 자가 검증 판정(5축)",
        "러너 연결·수신·기능 신고",
    ],
    "uninstrumented": [
        {"name": "개인 AI 의 토큰·비용", "reason": "추론이 각자의 머신·계정에서 일어나 우리 원장에 남지 않는다(구조적)"},
        {"name": "개인 AI 의 내부 단계·지연", "reason": "러너가 신고하는 진행 단계 외에는 관측 경로가 없다"},
        {"name": "임베딩 (로컬 bge-m3)", "reason": "embeddings.create 응답에 usage 필드 없음(SDK 한계)"},
    ],
    # ⚠ 마크다운 강조를 쓰지 않는다 — 이 문자열은 `esc()` 를 거쳐 **평문으로** 렌더되므로
    #   별표가 그대로 화면에 뜬다(라이브 실측 2026-09-01).
    "note": ("추론 비용·토큰은 각 사용자의 AI 계정에서 발생하므로 이 화면에 합계가 없습니다 — "
             "0 이 아니라 우리가 세는 축이 아닙니다. 서버가 직접 호출하던 시절의 토큰·비용 "
             "기록은 '기록' 탭에 보존되어 있습니다."),
}

_ACTIVITY_LIMIT_DEFAULT = 30
_ACTIVITY_LIMIT_MAX = 100


def _query_activity(cur, taxonomy_for, *, cursor=None, limit=_ACTIVITY_LIMIT_DEFAULT):
    """llm_usage 활동 feed 를 id DESC(=created_at DESC — id BIGSERIAL 단조증가) 로 cursor 페이징.
    cursor(id) 미지정=최신부터. `WHERE id < cursor` + limit+1 조회로 has_more 판정 → 안정적
    keyset 페이징(OFFSET 아님). 반환 (items, next_cursor). 과거 기록 조회용(더 보기)."""
    # TASK-20260702-audit-nav-ux: '최근 활동' 클릭 상세 확장을 위해 SELECT 컬럼을 확장한다.
    #   요청 별칭(model)과 서빙 모델(resolved_model)을 분리 보존(요청→서빙 표시), run_id(요청 식별자),
    #   conversation_id(연결 대화 드릴다운)를 추가. 기존 반환 필드(model=served/total/cost/latency/...)는
    #   보존 — 상세 필드는 순수 additive(overview activity feed + /activity 페이징 공용, 신규 엔드포인트 무).
    _BASE_COLS = ("id, task, model, resolved_model, total_tokens, prompt_tokens, "
                  "completion_tokens, latency_ms, created_at, run_id, conversation_id")

    # TASK-20260703-aiops-target(0032): '최근 활동' 에 인사이트 분석 대상(schema/schema.table/노드 FQN)을
    # 표시하기 위해 target 컬럼을 additive 로 SELECT(맨 끝 인덱스 11). 컬럼 부재(마이그 미적용 / agent image
    # stale — memory: deploy-migration-stale-agent-image)면 base 컬럼만으로 재조회해 피드가 깨지지 않게
    # 자가치유(has_target=False → target=None). SELECT 전용이라 rollback 은 무손실.
    def _fetch(cols: str):
        if cursor is not None:
            cur.execute(
                "SELECT " + cols + " FROM agent_runtime.llm_usage WHERE id < %s ORDER BY id DESC LIMIT %s",
                (int(cursor), int(limit) + 1),
            )
        else:
            cur.execute(
                "SELECT " + cols + " FROM agent_runtime.llm_usage ORDER BY id DESC LIMIT %s",
                (int(limit) + 1,),
            )
        return cur.fetchall() or []

    # usage-metric-charts(2026-08-13): 캐시 토큰(0056)을 사다리 최상단에 추가한다. 행 단위 비용이
    #   캐시 할인 단가를 반영해야 관리 콘솔 사용량 집계와 같은 값이 된다. 컬럼 부재(마이그 미적용·
    #   stale image)면 한 단계씩 내려가 피드 자체는 계속 뜬다(기존 target 자가치유와 동형).
    has_cache = True
    has_target = True
    try:
        rows = _fetch(_BASE_COLS + ", target, cache_read_tokens, cache_write_tokens")
    except Exception:
        has_cache = False
        try:
            cur.connection.rollback()
        except Exception:
            pass
        try:
            rows = _fetch(_BASE_COLS + ", target")
        except Exception:
            try:
                cur.connection.rollback()  # abort 트랜잭션 정리 후 target 제외 재조회
            except Exception:
                pass
            rows = _fetch(_BASE_COLS)
            has_target = False
    has_more = len(rows) > limit
    items = []
    for r in rows[:limit]:
        tx = taxonomy_for(r[1])
        served = r[3] or r[2]  # COALESCE(resolved_model, model) — 비용 계산·라우팅 상세의 서빙 기준
        # aiops-model-canonical: 활동 목록의 주 모델 배지는 canonical family 로 표시 → 관리 콘솔
        # LLM 사용량 도넛/기타 표기와 정합(라우팅 변형·실 모델 ID·gemma 폴백이 통일된 실 모델명으로 노출).
        # req_model(요청 alias)·resolved_model(실 서빙)은 아래에서 raw 로 보존 → 상세 펼침의
        # '요청 → 서빙' 라우팅(계정 분기·gemma 폴백 등) audit 정보는 그대로 유지(정보 손실 없음).
        served_canonical = canonical_usage_model(served)
        prompt_t = int(r[5] or 0)
        completion_t = int(r[6] or 0)
        # 인덱스 12/13 = cache_read/cache_write (사다리 최상단 경로에서만 존재).
        cache_r = int(r[12] or 0) if (has_cache and len(r) > 12) else 0
        cache_w = int(r[13] or 0) if (has_cache and len(r) > 13) else 0
        items.append({
            "id": int(r[0]), "task": r[1], "category": tx["category"], "label": tx["label"],
            "model": served_canonical, "total_tokens": int(r[4] or 0),
            "cost_usd": app._estimate_llm_cost_usd(served, prompt_t, completion_t, cache_r, cache_w),
            "latency_ms": (int(r[7]) if r[7] is not None else None),
            "created_at": (r[8].isoformat() if r[8] else None),
            # ── 상세 확장용 additive 필드 ──
            "req_model": r[2], "resolved_model": r[3],
            "prompt_tokens": prompt_t, "completion_tokens": completion_t,
            "run_id": r[9], "conversation_id": r[10],
            # 0032: 인사이트 분석 대상(schema/schema.table/노드 FQN). 대상 없는 활동(추론·요약 등)·컬럼 부재 시 None.
            #   len(r) > 11 가드: 폴백 경로(base 컬럼만)나 target 미포함 행에서 IndexError 방지(방어심층).
            "target": ((r[11] or None) if (has_target and len(r) > 11) else None),
        })
    next_cursor = items[-1]["id"] if (has_more and items) else None
    return items, next_cursor


# ── 워커 공유 자원 예산 (T0b worker-ds-budget) ────────────────────────────────
#: 워커가 flush 한 스냅샷 디렉토리(컨테이너 `/shared` = 호스트 artifacts/shared). web 도 같은
#: 볼륨을 마운트하므로 **PG 테이블·마이그레이션 없이** 파일로 읽는다 — 카운터는 워커 프로세스
#: 메모리에 있고 이 프로세스는 그것을 직접 볼 수 없다.
_WORKER_RES_DIR = "/shared/perf"
#: 파일당 상한(바이트) — 신뢰 경계 안(우리 워커가 쓴 파일)이지만 손상·거대 파일에 대한 방어.
_WORKER_RES_MAX_BYTES = 64 * 1024
#: 표시 상한 — 워커 컨테이너 수는 소수(insight/ask)라 넉넉하다.
_WORKER_RES_MAX_FILES = 8
#: stale 판정(초) — flush 는 insight cycle 마다 일어난다. 초과 시 값 대신 stale 표식을 준다.
_WORKER_RES_STALE_SEC = 1800


def _safe_int(v) -> int:
    """JSON 직렬화 안전 정수 변환. NaN/Infinity/비수치는 0.

    ⚠ `float("NaN")`·`float("Infinity")` 는 파이썬에서 정상 float 이지만 **표준 JSON 이 아니어서**
    `JSONResponse` 직렬화가 `ValueError` 를 내 500 이 된다 — 관측 조회가 콘솔을 깨는 fail-open 위반
    (codex P1, REV-20260730T1430). 손상된 스냅샷 파일이 그 값을 담을 수 있으므로 경계에서 막는다.
    """
    import math
    try:
        if isinstance(v, bool) or v is None:
            return 0
        f = float(v)
        if not math.isfinite(f):
            return 0
        return int(f)
    except Exception:
        return 0


def _safe_float(v) -> float:
    """JSON 직렬화 안전 실수 변환. NaN/Infinity/비수치는 0.0 (`_safe_int` 와 동일 사유)."""
    import math
    try:
        if isinstance(v, bool) or v is None:
            return 0.0
        f = float(v)
        if not math.isfinite(f):
            return 0.0
        return round(f, 4)
    except Exception:
        return 0.0


def _worker_resources() -> dict:
    """워커 자원 예산·계측 스냅샷 수집 (read-only, fail-open).

    반환 `{"available": bool, "workers": [...], "reason": str?}`. 파일 부재·손상·권한 오류는
    전부 `available: false` + reason 으로 강등한다 — 관측 조회가 콘솔 응답을 깨면 본말전도다
    (§20 ai-ops 의 부분 degrade 규약 답습).
    """
    import glob
    import json
    import os
    import time
    out: dict = {"available": False, "workers": []}
    try:
        # **최신 우선 정렬(mtime DESC)** — 표시 상한(_WORKER_RES_MAX_FILES)에 도달해도 현행 워커가
        #   남는다. 파일명 사전순이면 어느 것이 잘릴지 예측할 수 없어 살아 있는 워커가 유령
        #   스냅샷에 밀릴 수 있다(라이브에서 실제로 스냅샷이 누적됐다 — role 안정화와 한 쌍의 방어).
        cands = glob.glob(os.path.join(_WORKER_RES_DIR, "worker-resources-*.json"))
        def _mtime(p):
            try:
                return os.stat(p).st_mtime
            except Exception:
                return 0.0
        # mtime 동률이면 경로 오름차순으로 **결정적** 정렬(codex P2) — tie-break 가 없으면
        #   glob 반환 순서에 따라 상한 밖으로 밀리는 파일이 실행마다 달라진다.
        paths = sorted(cands, key=lambda p: (-_mtime(p), p))
    except Exception as exc:
        out["reason"] = f"디렉토리 조회 실패: {exc.__class__.__name__}"
        return out
    if not paths:
        out["reason"] = "워커 스냅샷 없음 — 워커가 아직 flush 하지 않았거나 구 이미지"
        return out
    now = time.time()
    for path in paths[:_WORKER_RES_MAX_FILES]:
        try:
            # P2 방어: 공유 볼륨은 다른 컨테이너도 쓴다. symlink 를 따라가면 그 컨테이너가 임의
            #   JSON 파일을 읽히게 만들 수 있으므로 **링크는 건너뛰고**, realpath 가 스냅샷
            #   디렉토리 하위인지 재확인한다(디렉토리 이탈 차단). 지표 위조 자체는 볼륨 쓰기
            #   권한을 가진 주체(우리 워커)의 신뢰 문제라 여기서 막지 않는다 — 읽기 표면만 좁힌다.
            if os.path.islink(path):
                continue
            real = os.path.realpath(path)
            base_real = os.path.realpath(_WORKER_RES_DIR)
            if os.path.dirname(real) != base_real:
                continue
            st = os.stat(real)
            if not os.path.isfile(real) or st.st_size > _WORKER_RES_MAX_BYTES:
                continue
            path = real
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            age = max(0.0, now - st.st_mtime)
            entry = {
                "role": str(data.get("role") or os.path.basename(path))[:64],
                "flushed_at": str(data.get("flushed_at") or "")[:32],
                "age_sec": int(age),
                "stale": age > _WORKER_RES_STALE_SEC,
                "background_enabled": bool(data.get("background_enabled", True)),
                "resources": {},
                "conns": {},
            }
            for key, val in (data.get("resources") or {}).items():
                if not isinstance(val, dict):
                    continue
                entry["resources"][str(key)[:16]] = {
                    "limit": _safe_int(val.get("limit")),
                    "peak": _safe_int(val.get("peak")),
                    "in_use": _safe_int(val.get("in_use")),
                    "acquired": _safe_int(val.get("acquired")),
                    "rejected": _safe_int(val.get("rejected")),
                    "reject_ratio": _safe_float(val.get("reject_ratio")),
                }
            for key, val in (data.get("conns") or {}).items():
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue          # 문자열·None 등 손상 값은 제외(계약: 정수 카운터)
                entry["conns"][str(key)[:16]] = _safe_int(val)
            out["workers"].append(entry)
        except Exception:
            continue          # 파일 하나가 손상돼도 나머지는 보여준다
    out["available"] = bool(out["workers"])
    if not out["available"]:
        out["reason"] = "스냅샷 파싱 실패 — 파일 손상 또는 권한"
    return out


# ── 외부AI 운영축 엔드포인트 3종 (TASK-20260901T110000) ───────────────────────
#
# 종전 관제는 전부 `llm_usage`(서버 계정 호출)를 봤다. 서버가 추론하지 않는 배포에서 그
# 원장은 늘지 않으므로 화면 전체가 0 으로 수렴했고, 그 0 은 "아무도 AI 를 안 쓴다" 로
# 읽혔다 — 실제로는 **우리가 세지 않는 곳에서** 쓰고 있었다. 아래 셋이 그 공백을 메운다.

_PERM_MSG = "AI 운영 현황 조회 권한이 필요합니다 (운영자 전용)."


@router.get("/api/admin/ai-ops/tools")
def admin_ai_ops_tools(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message=_PERM_MSG)),
) -> JSONResponse:
    """**도구 사용량** — 외부 AI 가 우리 도구로 무엇을 얼마나 읽었나 (`tool_call_usage`).

    외부AI 세계에서 「서버에 남는 실제 활동」은 이것뿐이다. 토큰이 아니라 **호출·행·바이트**
    를 센다(비용은 그쪽이 내고 부하는 우리 DB 가 낸다 — `tool_ledger` 가 그 원장이다).

    Query: days(기본 7, 1~90). PG 미가용 시 부분 degrade(200 유지, `pg_available:false`).
    """
    try:
        days = int(request.query_params.get("days", "7"))
    except Exception:
        days = 7
    days = max(1, min(90, days))

    out: dict = {"window_days": days, "pg_available": True, "totals": {},
                 "by_tool": [], "by_datasource": [], "by_account": [], "by_day": []}
    try:
        from shared.db import _pg_connect_ro

        pg = _pg_connect_ro()
    except Exception:
        pg = None
    if pg is None:
        out["pg_available"] = False
        return JSONResponse(out)
    win = f"now() - interval '{days} days'"
    try:
        with pg.cursor() as cur:
            def _q(sql: str) -> list:
                try:
                    cur.execute(sql)
                    return cur.fetchall() or []
                except Exception:
                    # 질의 하나가 실패해도 나머지는 보여 준다. 실패한 트랜잭션을 정리하지
                    # 않으면 뒤따르는 질의가 전부 25P02 로 죽는다(같은 파일 `_query_activity`
                    # 가 같은 이유로 rollback 한다).
                    _log.debug("ai_ops tools query failed", exc_info=True)
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                    return []

            r = _q("SELECT count(*), COALESCE(sum(rows_returned),0), "
                   "       COALESCE(sum(bytes_out),0), count(DISTINCT account_id), "
                   "       count(DISTINCT task_id), "
                   "       count(*) FILTER (WHERE outcome <> 'ok') "
                   f"FROM agent_runtime.tool_call_usage WHERE created_at >= {win}")
            if r:
                out["totals"] = {
                    "calls": int(r[0][0] or 0), "rows": int(r[0][1] or 0),
                    "bytes": int(r[0][2] or 0), "accounts": int(r[0][3] or 0),
                    "tasks": int(r[0][4] or 0), "not_ok": int(r[0][5] or 0),
                }
            # 도구별. `outcome` 을 접지 않고 함께 센다 — 「많이 불렸다」와 「많이 거절됐다」는
            # 다른 사실이고, 후자만이 조치를 요구한다.
            out["by_tool"] = [{
                "tool": str(x[0] or ""), "calls": int(x[1] or 0),
                "rows": int(x[2] or 0), "bytes": int(x[3] or 0),
                "denied": int(x[4] or 0), "gated": int(x[5] or 0), "errors": int(x[6] or 0),
                "p95_ms": (round(float(x[7]), 1) if x[7] is not None else None),
            } for x in _q(
                "SELECT tool, count(*), COALESCE(sum(rows_returned),0), "
                "       COALESCE(sum(bytes_out),0), "
                "       count(*) FILTER (WHERE outcome = 'denied'), "
                "       count(*) FILTER (WHERE outcome = 'gated'), "
                "       count(*) FILTER (WHERE outcome = 'error'), "
                "       percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) "
                f"FROM agent_runtime.tool_call_usage WHERE created_at >= {win} "
                "GROUP BY tool ORDER BY 2 DESC LIMIT 40")]
            out["by_datasource"] = [{
                "datasource_key": str(x[0] or "(없음)"), "calls": int(x[1] or 0),
                "rows": int(x[2] or 0), "bytes": int(x[3] or 0),
            } for x in _q(
                "SELECT COALESCE(datasource_key, ''), count(*), "
                "       COALESCE(sum(rows_returned),0), COALESCE(sum(bytes_out),0) "
                f"FROM agent_runtime.tool_call_usage WHERE created_at >= {win} "
                "GROUP BY 1 ORDER BY 2 DESC LIMIT 30")]
            # 계정별 — 상한(`AGENT_EXT_TOOL_*`)이 계정 단위라 이 축이 곧 「누가 상한에
            # 가까운가」다.
            out["by_account"] = [{
                # 이름은 이 원장에 없다(PG 는 id 만 안다) — 아래 `_attach_usernames` 가 MySQL
                # 에서 합류시킨다. 여기서 빈 문자열을 두는 이유는 실패 시에도 키가 존재하게
                # 하기 위해서다(프론트가 `username || 계정 #id` 로 떨어진다).
                "account_id": int(x[0] or 0), "username": "",
                "calls": int(x[1] or 0), "rows": int(x[2] or 0), "bytes": int(x[3] or 0),
            } for x in _q(
                "SELECT account_id, count(*), COALESCE(sum(rows_returned),0), "
                "       COALESCE(sum(bytes_out),0) "
                f"FROM agent_runtime.tool_call_usage WHERE created_at >= {win} "
                "GROUP BY account_id ORDER BY 2 DESC LIMIT 30")]
            out["by_day"] = [{
                "day": (x[0].isoformat() if hasattr(x[0], "isoformat") else str(x[0] or "")),
                "calls": int(x[1] or 0), "rows": int(x[2] or 0), "bytes": int(x[3] or 0),
            } for x in _q(
                "SELECT date_trunc('day', created_at)::date, count(*), "
                "       COALESCE(sum(rows_returned),0), COALESCE(sum(bytes_out),0) "
                f"FROM agent_runtime.tool_call_usage WHERE created_at >= {win} "
                "GROUP BY 1 ORDER BY 1")]
    finally:
        try:
            pg.close()
        except Exception:
            pass

    # 계정 이름은 MySQL 에 있다(PG 원장은 id 만 안다). 이름 없이 id 만 보여 주면 운영자가
    # 그 줄로 아무 판단도 할 수 없으므로 여기서 합류시킨다 — 실패하면 id 만 남는다.
    _attach_usernames(out["by_account"])
    return JSONResponse(out)


def _attach_usernames(rows: list) -> None:
    """`account_id` 만 있는 행에 `username` 을 채운다(best-effort, 실패 시 그대로 둔다)."""
    ids = sorted({int(r.get("account_id") or 0) for r in rows if r.get("account_id")})
    if not ids:
        return
    try:
        conn = app._connect_memory()
    except Exception:
        return
    try:
        cur = conn.cursor()
        try:
            marks = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({marks})", ids)
            names = {int(a): str(b or "") for a, b in (cur.fetchall() or [])}
        finally:
            cur.close()
    except Exception:
        return
    finally:
        try:
            conn.close()
        except Exception:
            pass
    for r in rows:
        r["username"] = names.get(int(r.get("account_id") or 0), "")


#: 작업 원장 페이지 크기. 상한을 두는 이유는 한 조회가 `WebAiTasks` 를 통째로 끌어오지
#: 않게 하기 위해서다(질문 본문이 실린다 — 행마다 무겁다).
_TASKS_LIMIT_DEFAULT = 40
_TASKS_LIMIT_MAX = 200


@router.get("/api/admin/ai-ops/tasks")
def admin_ai_ops_tasks(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message=_PERM_MSG)),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """**브리지 작업 통합 원장** — 대화 질문 · 콘솔 위임 · 배경 배치 · 외부 AI 세션.

    종전에는 두 화면이 이 표를 반쪽씩 보고 있었다: 「위임 작업 현황」은 `Kind='job'` 만,
    「외부 AI 작업」은 `Origin` 무관이지만 상태·소유·수행 계정을 싣지 않았다. 그래서
    **대화 질문이 밀려 있는 것**은 어느 화면에도 나오지 않았다 — 정작 사용자가 기다리는
    것이 그것인데.

    소유(`AccountId` — 누가 시켰나)와 수행(`ClaimedBy` — 누가 하고 있나)을 나눠서 준다.
    관리자 작업은 둘이 같지만 배치는 다르다(워커가 열고 아무 러너나 집는다).

    Query: kind(chat|job) · origin(web|batch|external) · status · limit · offset.
    """
    from shared.bridge_tasks import job_label

    try:
        limit = int(request.query_params.get("limit") or _TASKS_LIMIT_DEFAULT)
        offset = max(0, int(request.query_params.get("offset") or 0))
    except (TypeError, ValueError):
        limit, offset = _TASKS_LIMIT_DEFAULT, 0
    limit = max(1, min(_TASKS_LIMIT_MAX, limit))

    where, params = ["1=1"], []
    for col, key in (("Kind", "kind"), ("Origin", "origin"), ("Status", "status")):
        val = str(request.query_params.get(key) or "").strip()
        if val:
            # allowlist 가 아니라 **파라미터 바인딩**으로 막는다 — 값 목록을 여기 복제하면
            # `bridge_tasks` 가 종류를 늘리는 날 이 필터만 낡아 새 종류가 조회되지 않는다.
            where.append(f"t.{col} = %s")
            params.append(val[:32])

    items: list[dict] = []
    total = 0
    if conn is not None:
        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM WebAiTasks t WHERE " + " AND ".join(where),
                            tuple(params))
                total = int((cur.fetchone() or (0,))[0] or 0)
                cur.execute(
                    "SELECT t.TaskId, t.Kind, t.Origin, t.Status, t.JobKind, "
                    "       t.CreatedAt, t.ClaimedAt, t.SubmittedAt, t.JobAppliedAt, "
                    "       t.JobApplyError, owner.Username, worker.Username, "
                    "       t.ConversationId, t.Question, t.DatasourceKey, "
                    "       t.InjectionVerdict, t.AnswerVerdict, t.AnswerBytes, "
                    "       (t.Answer IS NOT NULL) "
                    "FROM WebAiTasks t "
                    "LEFT JOIN WebAccounts owner  ON owner.Id  = t.AccountId "
                    "LEFT JOIN WebAccounts worker ON worker.Id = t.ClaimedBy "
                    "WHERE " + " AND ".join(where) +
                    " ORDER BY t.Id DESC LIMIT %s OFFSET %s",
                    (*params, limit, offset))
                for r in (cur.fetchall() or []):
                    kind = str(r[1] or "")
                    items.append({
                        "task_id": str(r[0] or ""),
                        "kind": kind,
                        "origin": str(r[2] or ""),
                        "status": str(r[3] or ""),
                        "job_kind": str(r[4] or ""),
                        # 대화 질문에는 job_kind 가 없다 — 라벨을 지어내지 않고 종류로 말한다.
                        "label": (job_label(r[4]) if str(r[4] or "") else ""),
                        "created_at": _iso(r[5]), "claimed_at": _iso(r[6]),
                        "submitted_at": _iso(r[7]), "applied_at": _iso(r[8]),
                        "apply_error": str(r[9] or ""),
                        "owner": str(r[10] or ""), "worker": str(r[11] or ""),
                        "conversation_id": str(r[12] or ""),
                        # 목록에는 **머리만** 싣는다. 전문은 상세(`/api/ai/tasks/{id}`)가 준다 —
                        # 목록에 본문을 실으면 한 페이지가 수 MB 가 되고, 외부 각인 블록이
                        # 목록 응답으로 흘러 나간다.
                        "question_head": str(r[13] or "")[:160],
                        "datasource_key": str(r[14] or ""),
                        "injection_verdict": str(r[15] or ""),
                        "answer_verdict": str(r[16] or ""),
                        "answer_bytes": (int(r[17]) if r[17] is not None else None),
                        "has_answer": bool(r[18]),
                    })
            finally:
                cur.close()
        except Exception as exc:  # noqa: BLE001
            _log.warning("[ai-ops] 작업 원장 조회 실패: %r", exc)

    # 각 작업의 자가 검증 판정을 붙인다 — 답변 옆에 있어야 의미가 있다(별도 화면에 두면
    # 「이 답변이 검증을 통과했나」를 두 화면을 오가며 맞춰야 한다).
    _attach_reviews(items)
    return JSONResponse({"items": items, "total": total, "limit": limit, "offset": offset})


def _attach_reviews(items: list) -> None:
    """작업 목록에 `review`(외부 자가 검증 요약)를 붙인다. 실패는 조용히 넘어간다.

    붙지 않은 것과 `verdict='pass'` 는 **다른 사실**이므로, 값이 없으면 키 자체를 두지
    않는다(프론트가 `undefined` 를 '검증 없음' 으로 그린다). 빈 dict 로 채우면 화면이
    그것을 통과로 그릴 여지가 생긴다.
    """
    ids = [str(i.get("task_id") or "") for i in items if i.get("task_id")]
    if not ids:
        return
    try:
        from shared.db import _pg_connect_ro

        pg = _pg_connect_ro()
    except Exception:
        return
    if pg is None:
        return
    found: dict[str, dict] = {}
    try:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (task_id) task_id, verdict, block_count, warn_count, "
                "       findings, created_at "
                "FROM agent_runtime.redteam_reviews "
                "WHERE source = 'external' AND task_id = ANY(%s) "
                "ORDER BY task_id, id DESC",
                (ids,))
            for r in (cur.fetchall() or []):
                raw_findings = r[4] if isinstance(r[4], list) else []
                # 축 한글 라벨은 **서버가 붙인다**. 프론트에 표를 두면 축을 늘리는 날 화면만
                # 낡아 새 축이 영문 원문으로 샌다 — 그 원문은 외부 AI 가 쓴 문자열이다.
                findings = []
                for f in raw_findings:
                    if not isinstance(f, dict):
                        continue
                    axis = str(f.get("axis") or "")
                    findings.append({**f, "axis_label": _AXIS_LABELS.get(axis, axis)})
                found[str(r[0])] = {
                    "verdict": str(r[1] or ""), "block_count": int(r[2] or 0),
                    "warn_count": int(r[3] or 0),
                    "findings": findings,
                    "created_at": _iso(r[5]),
                }
    except Exception:
        _log.debug("ai_ops task review join failed (0057 미적용?)", exc_info=True)
        return
    finally:
        try:
            pg.close()
        except Exception:
            pass
    for it in items:
        rv = found.get(str(it.get("task_id") or ""))
        if rv:
            it["review"] = rv


@router.get("/api/admin/ai-ops/runners")
def admin_ai_ops_runners(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message=_PERM_MSG)),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """**러너 명부** — 계정별 연결·수신·기능·버전·지문. (`_runner_roster` 참조)"""
    try:
        limit = max(1, min(200, int(request.query_params.get("limit") or 100)))
    except (TypeError, ValueError):
        limit = 100
    return JSONResponse(_runner_roster(conn, limit=limit))


@router.get("/api/admin/ai-ops/activity")
def admin_ai_ops_activity(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message="AI 운영 현황 조회 권한이 필요합니다 (운영자 전용).")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """AI 운영 현황 '최근 활동' 과거 기록 페이징 — cursor(id) keyset 로 더 오래된 활동 조회.
    Query: cursor(id, 이 값보다 오래된 것), limit(기본 30, 1~100). PG 미가용 시 부분 degrade."""
    from shared.model_catalog import taxonomy_for

    try:
        limit = int(request.query_params.get("limit", str(_ACTIVITY_LIMIT_DEFAULT)))
    except Exception:
        limit = _ACTIVITY_LIMIT_DEFAULT
    limit = max(1, min(_ACTIVITY_LIMIT_MAX, limit))
    cursor_raw = request.query_params.get("cursor")
    cursor = None
    if cursor_raw:
        try:
            cursor = int(cursor_raw)
        except Exception:
            cursor = None

    items: list[dict] = []
    next_cursor = None
    pg_available = True
    try:
        from shared.db import _pg_connect_ro
        pg = _pg_connect_ro()
    except Exception:
        pg = None
        pg_available = False
    if pg is not None:
        try:
            with pg.cursor() as cur:
                items, next_cursor = _query_activity(cur, taxonomy_for, cursor=cursor, limit=limit)
        except Exception:
            _log.debug("ai_ops activity paging query failed", exc_info=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    return JSONResponse({"items": items, "next_cursor": next_cursor, "pg_available": pg_available})


@router.get("/api/admin/ai-ops")
def admin_ai_ops(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message="AI 운영 현황 조회 권한이 필요합니다 (운영자 전용).")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """AI 운영 관제 종합 — 상태 배너/축 + KPI + Attention + 카테고리 드릴다운 + 최근 활동 + 커버리지.

    Query: days(기본 7, 1~90). 읽기 전용. PG 미가용 시 부분 degrade(200 유지)."""
    from shared.model_catalog import taxonomy_for, ai_categories

    try:
        days = int(request.query_params.get("days", "7"))
    except Exception:
        days = 7
    days = max(1, min(90, days))

    # ── 상태 축 → worst-of 배너 ──
    # ⚠ **순서 고정** — 아래 `kpis` 가 `axes[0]`(provider) · `axes[1]`·`axes[2]`(워커)를
    #   위치로 읽는다. 새 축은 반드시 **뒤에** 붙인다(앞에 끼우면 KPI 가 조용히 다른 축을
    #   보고, 그 오독은 화면상 아무 표시 없이 일어난다).
    axes = [_provider_axis(), _ask_worker_axis(conn), _insight_worker_axis(conn),
            _datasource_axis(), _bridge_axis(conn)]
    rolled = [a for a in axes if a["state"] != "na"]
    banner_state = "ok"
    for a in rolled:
        if _SEV.get(a["state"], 0) > _SEV.get(banner_state, 0):
            banner_state = a["state"]
    banner = {"state": banner_state, "label": _SEV_LABEL.get(banner_state, banner_state)}

    # ── PG 집계 (부분 degrade) ──
    pg_available = True
    categories: list[dict] = []
    activity: list[dict] = []
    activity_next_cursor = None
    latency = {"measured_calls": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None,
               "multistep_requests": 0, "agent_requests": 0}
    activity_24h = {"calls": 0, "requests": 0}
    unmapped_tasks: list[str] = []

    try:
        from shared.db import _pg_connect_ro
        pg = _pg_connect_ro()
    except Exception:
        pg = None
        pg_available = False

    if pg is not None:
        try:
            win = f"now() - interval '{days} days'"
            cat_fold: dict[str, dict] = {}
            lat_by_task: dict[str, dict] = {}
            with pg.cursor() as cur:
                # 1) 카테고리/태스크 × 모델 (호출·토큰·비용). taxonomy self-surface.
                # usage-model-canonical 정합(aiops-model-canonical): 서빙 모델을 canonical family 로 접어
                # 집계. 출력은 taxonomy 카테고리 롤업이라 모델 차원이 노출되지 않는다. calls/total_tokens 는
                # 정수 sum 이라 그룹 세분도와 무관하게 카테고리 합계가 불변. cost 는 _estimate 가 호출마다
                # round(…,4) 하므로 raw 다중 그룹→canonical 단일 그룹 재결합으로 카테고리 cost 가 최하위
                # 4번째 소수(≈$0.0001) 수준에서 미세 변동할 수 있다(단일 round 라 오히려 더 정확 — pricing 은
                # _estimate 내부 canonical 로 이미 정확했음). 마지막 raw 모델 그룹핑을 제거해 향후 모델 차원
                # 노출 시 라우팅 변형 재분점을 구조적으로 예방하는 것이 본 변경의 실질 효과.
                try:
                    # usage-metric-charts: 캐시 인지 비용. 컬럼 부재(0056 미적용)면 리터럴 0 판으로 재실행.
                    app._usage_cache_exec(cur, pg, lambda cr, cw: (
                        f"SELECT task, {canonical_usage_model_sql('COALESCE(resolved_model, model)')} AS m, count(*), "
                        f"sum(prompt_tokens), sum(completion_tokens), sum(total_tokens), "
                        f"sum({cr}), sum({cw}) "
                        f"FROM agent_runtime.llm_usage WHERE created_at >= {win} GROUP BY task, 2"
                    ))
                    for r in (cur.fetchall() or []):
                        task, m = r[0], r[1]
                        calls, pt, ct, tt = int(r[2] or 0), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                        crw, cww = int(r[6] or 0), int(r[7] or 0)
                        tx = taxonomy_for(task)
                        e = cat_fold.setdefault(tx["category"], {
                            "category": tx["category"], "calls": 0, "total_tokens": 0,
                            "cost_usd": 0.0, "_tasks": {},
                        })
                        e["calls"] += calls
                        e["total_tokens"] += tt
                        e["cost_usd"] += app._estimate_llm_cost_usd(m, pt, ct, crw, cww)
                        te = e["_tasks"].setdefault(task, {
                            "task": task, "label": tx["label"], "calls": 0, "total_tokens": 0,
                        })
                        te["calls"] += calls
                        te["total_tokens"] += tt
                except Exception:
                    _log.debug("ai_ops categories query failed", exc_info=True)

                # 2) 태스크별 지연 = 단계 간 간격 (TASK-20260703-aiops-ttft-latency, 정의 A). p50/p95 는
                #    step_gap_ms(에이전트 라운드 사이 도구·오케스트레이션 간격)로 집계 — 호출 전체 왕복이
                #    아닌 '단계 간 간격'. step_gap_ms 는 다단계 agentic 루프(task='agent')만 비-NULL이라
                #    사실상 에이전트 추론 전용. 컬럼 부재/마이그(0033) 전이면 실패 → 스킵(부분 degrade).
                try:
                    cur.execute(
                        f"SELECT task, count(step_gap_ms), avg(step_gap_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY step_gap_ms) "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win} AND step_gap_ms IS NOT NULL GROUP BY task"
                    )
                    for r in (cur.fetchall() or []):
                        lat_by_task[r[0]] = {
                            "measured": int(r[1] or 0),
                            "avg_ms": (round(float(r[2]), 1) if r[2] is not None else None),
                            "p50_ms": (round(float(r[3]), 1) if r[3] is not None else None),
                            "p95_ms": (round(float(r[4]), 1) if r[4] is not None else None),
                        }
                except Exception:
                    _log.debug("ai_ops step-gap-by-task query failed (step_gap_ms 컬럼 부재?)", exc_info=True)

                # 3) 전체 지연 KPI = 단계 간 간격. 계측(0033) 이후 — step_gap_ms=NULL(첫 라운드·단발 호출·
                #    마이그 이전 행) 은 집계에서 자동 제외(aggregate 는 NULL 무시 → cutover 오염 0). '지연' =
                #    사용자가 답변을 받는 총 시간이 아니라 각 추론 단계 간 나타나는 간격(도구 실행 + 오케스트레이션).
                #    F2(observability): 다단계 요청 분모도 함께 — step_gap 은 다단계(≥2 라운드) 요청에서만
                #    표본이 나오므로, 단발 요청 위주 window 에서 빈 tile 을 '고장' 으로 오인하지 않도록
                #    multistep_requests(간격 표본 있는 run_id 수) / agent_requests(전체 에이전트 요청 수) 노출.
                try:
                    cur.execute(
                        f"SELECT count(step_gap_ms), avg(step_gap_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"count(DISTINCT run_id) FILTER (WHERE step_gap_ms IS NOT NULL), "
                        f"count(DISTINCT run_id) FILTER (WHERE task = 'agent') "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win}"
                    )
                    lr = cur.fetchone()
                    if lr:
                        latency = {
                            "measured_calls": int(lr[0] or 0),
                            "avg_ms": (round(float(lr[1]), 1) if lr[1] is not None else None),
                            "p50_ms": (round(float(lr[2]), 1) if lr[2] is not None else None),
                            "p95_ms": (round(float(lr[3]), 1) if lr[3] is not None else None),
                            "multistep_requests": int(lr[4] or 0),
                            "agent_requests": int(lr[5] or 0),
                        }
                except Exception:
                    _log.debug("ai_ops step-gap KPI query failed", exc_info=True)

                # 4) 최근 24h 활동.
                try:
                    cur.execute(
                        "SELECT count(*), count(distinct run_id) FROM agent_runtime.llm_usage "
                        "WHERE created_at >= now() - interval '24 hours'"
                    )
                    ar = cur.fetchone() or (0, 0)
                    activity_24h = {"calls": int(ar[0] or 0), "requests": int(ar[1] or 0)}
                except Exception:
                    _log.debug("ai_ops 24h activity query failed", exc_info=True)

                # 5) 최근 활동 feed ("방금 무엇을 했나") — 최신 페이지 + 과거 페이징용 next_cursor.
                try:
                    activity, activity_next_cursor = _query_activity(
                        cur, taxonomy_for, limit=_ACTIVITY_LIMIT_DEFAULT)
                except Exception:
                    _log.debug("ai_ops activity feed query failed", exc_info=True)

            # 카테고리 정리 + latency 병합 + unmapped self-surface.
            cat_labels = ai_categories()
            for cat, e in cat_fold.items():
                tasks = sorted(e.pop("_tasks").values(), key=lambda x: x["total_tokens"], reverse=True)
                for t in tasks:
                    lt = lat_by_task.get(t["task"])
                    if lt:
                        t["p50_ms"] = lt["p50_ms"]
                        t["p95_ms"] = lt["p95_ms"]
                        t["measured"] = lt["measured"]
                e["label"] = cat_labels.get(cat, cat)
                e["cost_usd"] = round(e["cost_usd"], 4)
                e["tasks"] = tasks
                categories.append(e)
                if cat == "ai.other.unmapped":
                    unmapped_tasks = [t["task"] for t in tasks]
            categories.sort(key=lambda x: x["total_tokens"], reverse=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    # ── Attention zone (심각도 우선 부상) ──
    attention: list[dict] = []
    for a in rolled:
        if a["state"] in ("degraded", "down"):
            attention.append({"level": a["state"], "label": a["label"], "detail": a["detail"]})
    if unmapped_tasks:
        attention.append({
            "level": "degraded", "label": "미분류 AI 활동",
            "detail": f"taxonomy 미등록 task {len(unmapped_tasks)}종: " + ", ".join(unmapped_tasks[:5]),
        })
    if not pg_available:
        attention.append({
            "level": "unknown", "label": "계측 저장소(PG) 미가용",
            "detail": "AI 활동·비용·지연 지표를 일시적으로 조회할 수 없습니다.",
        })
    # T0b: 워커 자원 예산이 실제로 병목이면(거절 발생) attention 으로 부상시킨다 — 상한을 올릴지
    #   판단해야 하는 신호다. 거절 0 이면 게이트 미발동(정상)이라 조용히 둔다.
    worker_resources = _worker_resources()
    for w in worker_resources.get("workers") or []:
        if not w.get("background_enabled", True):
            attention.append({
                "level": "degraded", "label": "백그라운드 분석 정지",
                "detail": f"{w.get('role')}: 전역 사용 스위치가 꺼져 있습니다(분석·클러스터링·분류 중단).",
            })
        for rk, rv in (w.get("resources") or {}).items():
            if int(rv.get("rejected") or 0) > 0:
                attention.append({
                    "level": "degraded", "label": f"자원 예산 병목({rk})",
                    "detail": (f"{w.get('role')}: 상한 {rv.get('limit')} · 최대 점유 {rv.get('peak')} · "
                               f"거절 {rv.get('rejected')}회(거절률 {rv.get('reject_ratio')}). "
                               "상한을 올리거나 처리량을 낮추세요."),
                })

    # feature-0032: 백그라운드 LLM 토큰 예산(rolling 24h). 소진되면 자동 분석이 다음 주기로
    #   밀리므로 "왜 분석이 안 도나" 의 1차 답이 된다 — attention 으로 부상시킨다.
    try:
        from shared import llm_budget as _lb
        llm_token_budget = _lb.snapshot()
    except Exception:
        llm_token_budget = {"enabled": False, "measurable": False, "exhausted": False}
    if llm_token_budget.get("exhausted"):
        attention.append({
            "level": "degraded", "label": "백그라운드 LLM 토큰 상한 도달",
            "detail": (f"최근 24시간 {llm_token_budget.get('spent')}/{llm_token_budget.get('cap')} 토큰. "
                       "새 자동 분석·요약·분류가 다음 주기로 밀립니다(대화 답변은 정상). "
                       "상한을 올리거나 처리량을 낮추세요."),
        })
    elif llm_token_budget.get("enabled") and (llm_token_budget.get("used_ratio") or 0) >= 0.8:
        attention.append({
            "level": "watch", "label": "백그라운드 LLM 토큰 상한 임박",
            "detail": (f"최근 24시간 {llm_token_budget.get('spent')}/{llm_token_budget.get('cap')} 토큰 "
                       f"({int((llm_token_budget.get('used_ratio') or 0) * 100)}%) 사용."),
        })

    return JSONResponse({
        "window_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "banner": banner,
        "axes": axes,
        "kpis": {
            "activity_24h": activity_24h,
            "latency": latency,
            "provider_state": axes[0]["state"],
            "workers_ok": sum(1 for a in (axes[1], axes[2]) if a["state"] == "ok"),
            "workers_total": sum(1 for a in (axes[1], axes[2]) if a["state"] != "na"),
        },
        "attention": attention,
        # ── feature-0043 TASK-20260831T100000 ────────────────────────────────────
        # 브리지 축의 수치를 KPI 로도 꺼내 둔다(축 `detail` 문자열을 프론트가 파싱해서
        # 쓰지 않게 — 문자열을 파싱하면 문구를 고치는 순간 KPI 가 깨진다).
        "bridge": axes[4].get("metrics") or {},
        # 위임 작업 현황 — **어떤 작업이 · 어떤 상태로 · 어느 계정에서**(사용자 결정 2026-08-31).
        "delegated_jobs": _delegated_jobs(conn),
        # ── TASK-20260901T110000 (외부AI 정합 재편) ──────────────────────────────
        # 러너 명부 — 「러너 N대」로는 답할 수 없는 "이 사람 질문이 왜 안 되나" 의 답.
        "runners": _runner_roster(conn),
        # 외부 AI 자가 검증 집계. 서버측 이력과 **합산하지 않는다**(주체가 다르다).
        "self_review": _self_review_stats(days),
        # 이 배포가 서버 계정 LLM 을 쓰는가. 화면이 「기록」 라벨을 붙일지 판단하는 축이다 —
        # `axes` 를 뒤져 찾게 하면 축 순서를 바꾸는 날 라벨이 조용히 사라진다.
        "server_llm_blocked": bool(axes[0].get("server_llm_blocked")),
        "categories": categories,
        "activity": activity,
        "activity_next_cursor": activity_next_cursor,
        # 커버리지는 **이 배포가 실제로 무엇을 세는가**를 말한다. 서버가 추론하지 않는데
        # 서버 추론 목록을 '계측됨' 으로 보이면, 정직 노출을 위한 표가 그 자리에서 거짓말한다.
        "coverage": (_COVERAGE_EXTERNAL if axes[0].get("server_llm_blocked") else _COVERAGE),
        "pg_available": pg_available,
        # T0b: 워커 공유 자원 예산·계측(파일 스냅샷). 라우트 추가 없음 — 기존 응답 확장.
        "worker_resources": worker_resources,
        # feature-0032: 백그라운드 LLM 토큰 예산 현황(rolling 24h) — 라우트 추가 없이 응답 확장.
        "llm_token_budget": llm_token_budget,
        # 위젯 deep-link 계약: 대시보드 타일 → 이 탭. data-admin-tab 값(hyphen)과 정확히 일치.
        "tab": "ai-ops",
    })
