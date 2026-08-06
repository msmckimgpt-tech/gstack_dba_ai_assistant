#!/usr/bin/env python3
"""attach-chain-merge — 이름이 갈라져 분열된 첨부 버전 체인을 하나로 병합한다.

배경 (2026-08-06 사용자 지시 "갈라진 첨부파일에 대해서는 하나의 체인으로 합쳐주세요"):
    선행 cycle `20260806T1820-attach-multi-upload` 이전에는 assistant 편집본이
    `<stem>_v<n>.<ext>` 라는 **다른 파일명**으로 저장됐다. 버전 체인 스코프가
    `(ConversationId, AccountId, OriginalFilename)` 이라 이름이 갈리면
      ① 원본이 supersede 되어 head 에서 빠지고
      ② 사용자가 원본 이름으로 다시 올릴 때 같은 이름의 head 를 못 찾아 **새 root(v1)** 가 생긴다.
    결과로 한 논리 파일이 여러 체인으로 쪼개져 목록에 나란히 남는다.
    코드는 이미 고쳐졌고(편집본이 원본명 승계), 본 스크립트는 **이미 갈라진 기존 데이터**를 정리한다.

동작:
    논리 파일 = `(ConversationId, AccountId, base(OriginalFilename))`.
    대상 = 그룹 안에 root 가 둘 이상이거나 · 이름이 둘 이상이거나 · **live(`SupersededAt IS NULL`)가
    둘 이상**인 경우(마지막은 supersede 누락이 남긴 선재 결함 — 증상이 같으므로 함께 정리).
    `base()` 는 파일명 끝의 `_v<숫자>` 접미를 제거한 것(`x_v3.sql` → `x.sql`).
    그룹 안 row 를 **CreatedAt 오름차순**으로 정렬해
      - 첫 row: `RootAttachmentId=NULL`, `VersionNumber=1`
      - 이후:   `RootAttachmentId=<첫 row Id>`, `VersionNumber=2..N`
      - `OriginalFilename` 을 base 이름으로 통일 + `FilenameHmac` 재계산
      - `SupersededAt`: 마지막 1건만 NULL, 나머지는 **다음 버전의 CreatedAt**
    `ObjectKey`·MinIO 객체·본문·`Sha256` 은 건드리지 않는다(파일 실체 무이동).

안전장치:
    - **기본 dry-run.** 실제 반영은 `--apply` 명시가 필요하다.
    - 실행 전 대상 row 의 변경 전 상태를 JSON 스냅샷 + **롤백 SQL** 로 저장한다.
    - 단일 트랜잭션 + `UNIQUE(RootAttachmentId, VersionNumber)` 충돌 회피 2단계 UPDATE.
    - 사용자가 **직접** `_v<n>` 이름으로 올린 파일(assistant 편집 흔적 없음)만 있는 그룹은
      제외한다 — 그것은 분열이 아니라 사용자가 고른 이름일 수 있다.
    - `--days N` 으로 범위 한정(그룹 내 최신 CreatedAt 기준). 미지정 시 전체.
    - 변경분은 PG 미러로 동기화한다(라이브 목록 read 가 PG 우선이라 미러가 어긋나면
      같은 첨부가 두 줄로 보인다 — `_mirror_chain` 과 같은 규약).

실행 (web 컨테이너 안):
    python /app/web/scripts/attach_chain_merge.py                 # dry-run 전체
    python /app/web/scripts/attach_chain_merge.py --days 7        # dry-run 최근 7일
    python /app/web/scripts/attach_chain_merge.py --apply         # 실제 반영
    python /app/web/scripts/attach_chain_merge.py --rollback <snapshot.json>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, "/app/web")
sys.path.insert(0, "/app")

import app  # noqa: E402  (경로 주입 후 import — 컨테이너 실행 전제)

_VER_SUFFIX_RE = re.compile(r"_v\d+$")


def base_name(name: str) -> str:
    """파일명 끝의 `_v<숫자>` 접미 제거. 확장자는 보존."""
    n = (name or "").strip()
    if "." in n:
        stem, ext = n.rsplit(".", 1)
        return _VER_SUFFIX_RE.sub("", stem) + "." + ext
    return _VER_SUFFIX_RE.sub("", n)


def _meta(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def load_rows(conn) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT Id, ConversationId, AccountId, OriginalFilename, FilenameHmac,
                   VersionNumber, RootAttachmentId, SupersededAt, CreatedByRole,
                   CreatedAt, MetaJson
            FROM WebConversationAttachments
            WHERE DeletedAt IS NULL AND DeletePending = 0
            ORDER BY CreatedAt, Id
            """
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def build_plan(rows: list[dict], days: int | None) -> tuple[list[dict], list[dict]]:
    """(변경 계획, 제외된 그룹) 산출. 계획 항목 = row 단위 before/after."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["ConversationId"], r["AccountId"], base_name(r["OriginalFilename"]))].append(r)

    cutoff = None
    if days is not None:
        cutoff = _dt.datetime.now() - _dt.timedelta(days=int(days))

    plan: list[dict] = []
    skipped: list[dict] = []
    for (conv, acct, base), members in sorted(groups.items()):
        chains = {int(m["RootAttachmentId"] or m["Id"]) for m in members}
        names = {str(m["OriginalFilename"]) for m in members}
        # 체인이 하나로 모여 있어도 `SupersededAt IS NULL` 이 둘 이상이면 목록에 **같은 파일이
        # 여러 줄**로 뜬다(업로드 경로의 supersede 누락이 남긴 선재 결함 — 라이브 실측 1건).
        # 분열(root/이름)과 원인은 다르지만 사용자가 보는 증상과 해소 수단(체인 재정렬)이
        # 같으므로 같은 판정에 넣는다.
        lives = sum(1 for m in members if not m["SupersededAt"])
        if len(chains) <= 1 and len(names) <= 1 and lives <= 1:
            continue  # 이미 단일 체인 · 단일 이름 · live 1건 — 손댈 것 없음
        if cutoff is not None and max(m["CreatedAt"] for m in members) < cutoff:
            continue  # 범위 밖

        # 제외 규칙: base 이름 row 가 하나도 없고, `_v<n>` 이름을 **사용자가 직접** 올린 것만
        # 모여 있으면 분열이 아니라 사용자가 고른 이름일 수 있다 → 건드리지 않는다.
        has_base_named = any(str(m["OriginalFilename"]) == base for m in members)
        assistant_edits = [m for m in members
                           if m["CreatedByRole"] == "assistant" and _meta(m["MetaJson"]).get("assistant_edit_of")]
        if not has_base_named and not assistant_edits:
            skipped.append({"conversation_id": conv, "account_id": acct, "base": base,
                            "reason": "user-named _v<n> only (분열 아님으로 판단)",
                            "ids": [int(m["Id"]) for m in members]})
            continue

        ordered = sorted(members, key=lambda m: (m["CreatedAt"], int(m["Id"])))
        root_id = int(ordered[0]["Id"])
        for idx, m in enumerate(ordered):
            ver = idx + 1
            is_last = idx == len(ordered) - 1
            new_root = None if idx == 0 else root_id
            # supersede 시각 = 다음 버전의 생성 시각(사실에 가장 가까운 값).
            new_superseded = None if is_last else ordered[idx + 1]["CreatedAt"]
            before = {
                "OriginalFilename": str(m["OriginalFilename"]),
                "FilenameHmac": str(m["FilenameHmac"] or ""),
                "RootAttachmentId": (int(m["RootAttachmentId"]) if m["RootAttachmentId"] else None),
                "VersionNumber": int(m["VersionNumber"] or 1),
                "SupersededAt": m["SupersededAt"],
            }
            after = {
                "OriginalFilename": base,
                "FilenameHmac": app._hmac_filename(base),
                "RootAttachmentId": new_root,
                "VersionNumber": ver,
                "SupersededAt": new_superseded,
            }
            if all(before[k] == after[k] for k in before):
                continue  # 이미 정합한 row 는 UPDATE 대상에서 제외(무의미 write 회피)
            plan.append({
                "id": int(m["Id"]), "conversation_id": conv, "account_id": acct,
                "base": base, "created_at": m["CreatedAt"], "before": before, "after": after,
            })
    return plan, skipped


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def write_snapshot(path: str, plan: list[dict], skipped: list[dict]) -> None:
    payload = {
        "generated_at": _dt.datetime.now().isoformat(),
        "row_count": len(plan),
        "skipped_groups": skipped,
        "rows": [
            {"id": p["id"], "conversation_id": p["conversation_id"], "base": p["base"],
             "before": {k: _iso(v) for k, v in p["before"].items()},
             "after": {k: _iso(v) for k, v in p["after"].items()}}
            for p in plan
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    # 사람이 읽고 직접 되돌릴 수 있는 SQL 도 함께 남긴다(도구 없이 복구 가능해야 한다).
    with open(path.replace(".json", ".rollback.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- attach-chain-merge rollback (before-state 복원)\n")
        fh.write("START TRANSACTION;\n")
        for p in plan:
            b = p["before"]
            root = "NULL" if b["RootAttachmentId"] is None else str(b["RootAttachmentId"])
            sup = "NULL" if b["SupersededAt"] is None else "'%s'" % b["SupersededAt"]
            fh.write(
                "UPDATE WebConversationAttachments SET "
                f"OriginalFilename={json.dumps(b['OriginalFilename'], ensure_ascii=False)}, "
                f"FilenameHmac='{b['FilenameHmac']}', RootAttachmentId={root}, "
                f"VersionNumber={b['VersionNumber']}, SupersededAt={sup} "
                f"WHERE Id={p['id']};\n"
            )
        fh.write("COMMIT;\n")


def apply_plan(conn, plan: list[dict]) -> int:
    """2단계 UPDATE — UNIQUE(RootAttachmentId, VersionNumber) 충돌 회피.

    같은 체인 안에서 버전 번호를 재배열하면 중간 상태가 기존 행과 충돌할 수 있다
    (예: v1→v2 를 쓰는 순간 이미 v2 인 행과 부딪친다). 1단계에서 모든 대상 행의
    VersionNumber 를 충분히 큰 오프셋으로 밀어 두고, 2단계에서 최종값을 넣는다.
    """
    ids = [p["id"] for p in plan]
    if not ids:
        return 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(VersionNumber), 0) FROM WebConversationAttachments")
        offset = int(cur.fetchone()[0] or 0) + 1000
        # 1단계: 대상 행 전부를 충돌 불가 영역으로 이동(Id 를 더해 서로도 안 부딪치게).
        for p in plan:
            cur.execute(
                "UPDATE WebConversationAttachments SET VersionNumber = %s WHERE Id = %s",
                (offset + p["id"], p["id"]),
            )
        # 2단계: 최종 상태 기록.
        for p in plan:
            a = p["after"]
            cur.execute(
                """
                UPDATE WebConversationAttachments
                   SET OriginalFilename = %s, FilenameHmac = %s, RootAttachmentId = %s,
                       VersionNumber = %s, SupersededAt = %s
                 WHERE Id = %s
                """,
                (a["OriginalFilename"], a["FilenameHmac"], a["RootAttachmentId"],
                 a["VersionNumber"], a["SupersededAt"], p["id"]),
            )
        conn.commit()
        return len(plan)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def mirror(conn, ids: list[int]) -> str:
    """변경분을 PG 미러로 **2단계**로 동기화. 실패는 fail-soft(사유 반환) — MySQL 이 정본이다.

    ⚠️ 단순 호출로는 안 된다(2026-08-07 라이브 실측): PG 에도 MySQL 과 같은
    `UNIQUE(root_attachment_id, version_number)` 제약이 있고 미러는 row 단위 upsert 라,
    재배열된 번호를 순서대로 밀어 넣는 도중 **기존 행과 충돌**한다
    (`duplicate key ... (699, 4) already exists` — 29 row 가 옛 상태로 남았다).
    MySQL 쪽에서 쓴 것과 같은 회피를 PG 에도 적용한다:
      ① 영향 **대화 전체**의 PG row 를 충돌 불가 오프셋으로 선이동
         (변경 대상만 밀면 그 자리를 차지한 *기존* 행과 다시 부딪친다)
      ② MySQL 정본으로 재미러
    """
    if not ids:
        return "no-op"
    try:
        from web.modules import attachment_pg_mirror as _apm
        from shared import db as _db
    except Exception as exc:  # noqa: BLE001
        return f"failed(import): {exc}"

    targets = sorted(set(int(i) for i in ids))
    # 영향 대화 전체로 확장 — 충돌 상대까지 함께 밀어야 중간 상태가 풀린다.
    cur = conn.cursor()
    try:
        marks = ",".join(["%s"] * len(targets))
        cur.execute(
            f"""SELECT Id FROM WebConversationAttachments
                 WHERE ConversationId IN (
                     SELECT DISTINCT ConversationId FROM WebConversationAttachments WHERE Id IN ({marks}))
                   AND DeletedAt IS NULL AND DeletePending = 0""",
            targets,
        )
        scope = sorted({int(r[0]) for r in cur.fetchall()}) or targets
    except Exception:
        scope = targets
    finally:
        cur.close()

    try:
        rw = _db._pg_connect()
        w = rw.cursor()
        try:
            w.execute("SELECT COALESCE(MAX(version_number), 0) FROM agent_runtime.core_attachments")
            off = int(w.fetchone()[0] or 0) + 100000
            for i in scope:
                w.execute(
                    "UPDATE agent_runtime.core_attachments SET version_number = %s WHERE id = %s",
                    (off + i, i),
                )
            rw.commit()
        finally:
            w.close()
            rw.close()
    except Exception as exc:  # noqa: BLE001
        return f"failed(pre-shift): {exc}"

    try:
        _apm.mirror_attachments(conn, scope)
        return f"ok (scope={len(scope)} row)"
    except Exception as exc:  # noqa: BLE001
        return f"failed(mirror): {exc}"


def do_rollback(conn, snapshot_path: str) -> int:
    with open(snapshot_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = payload.get("rows") or []
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(VersionNumber), 0) FROM WebConversationAttachments")
        offset = int(cur.fetchone()[0] or 0) + 1000
        for r in rows:
            cur.execute("UPDATE WebConversationAttachments SET VersionNumber = %s WHERE Id = %s",
                        (offset + int(r["id"]), int(r["id"])))
        for r in rows:
            b = r["before"]
            cur.execute(
                """
                UPDATE WebConversationAttachments
                   SET OriginalFilename = %s, FilenameHmac = %s, RootAttachmentId = %s,
                       VersionNumber = %s, SupersededAt = %s
                 WHERE Id = %s
                """,
                (b["OriginalFilename"], b["FilenameHmac"], b["RootAttachmentId"],
                 b["VersionNumber"], b["SupersededAt"], int(r["id"])),
            )
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="분열된 첨부 버전 체인 병합 (기본 dry-run)")
    ap.add_argument("--apply", action="store_true", help="실제 DB 반영 (미지정 시 dry-run)")
    ap.add_argument("--days", type=int, default=None, help="그룹 내 최신 CreatedAt 기준 최근 N일만")
    ap.add_argument("--snapshot", default=None, help="스냅샷 JSON 경로 (기본 /tmp/attach-chain-merge-<ts>.json)")
    ap.add_argument("--rollback", default=None, help="스냅샷 JSON 으로 before-state 복원")
    ap.add_argument("--limit-print", type=int, default=20, help="dry-run 출력 행 수 상한")
    args = ap.parse_args()

    conn = app._connect_memory()
    try:
        if args.rollback:
            n = do_rollback(conn, args.rollback)
            print(f"rollback: {n} row 복원")
            with open(args.rollback, encoding="utf-8") as fh:
                ids = [int(r["id"]) for r in (json.load(fh).get("rows") or [])]
            print("pg mirror:", mirror(conn, ids))
            return 0

        rows = load_rows(conn)
        plan, skipped = build_plan(rows, args.days)
        groups = {(p["conversation_id"], p["base"]) for p in plan}
        convs = {p["conversation_id"] for p in plan}
        scope = f"최근 {args.days}일" if args.days else "전체"
        print(f"[attach-chain-merge] 범위={scope} · 활성 첨부 {len(rows)} row 검사")
        print(f"  변경 대상: {len(plan)} row / {len(groups)} 논리파일 / {len(convs)} 대화")
        if skipped:
            print(f"  제외: {len(skipped)} 그룹 (사용자가 직접 _v<n> 이름으로 올린 것으로 판단)")
            for s in skipped[:5]:
                print(f"    - {s['base']} (conv={s['conversation_id']}) ids={s['ids']}")
        for p in plan[:args.limit_print]:
            b, a = p["before"], p["after"]
            print(f"  #{p['id']} {b['OriginalFilename']!r} v{b['VersionNumber']}"
                  f"(root={b['RootAttachmentId']}) → {a['OriginalFilename']!r} v{a['VersionNumber']}"
                  f"(root={a['RootAttachmentId']}, superseded={'Y' if a['SupersededAt'] else 'N'})")
        if len(plan) > args.limit_print:
            print(f"  … 외 {len(plan) - args.limit_print} row")

        if not args.apply:
            print("\n(dry-run — 반영하려면 --apply)")
            return 0
        if not plan:
            print("변경 대상 없음 — 종료")
            return 0

        snap = args.snapshot or f"/tmp/attach-chain-merge-{_dt.datetime.now():%Y%m%dT%H%M%S}.json"
        write_snapshot(snap, plan, skipped)
        print(f"\n스냅샷: {snap} (+ .rollback.sql)")
        n = apply_plan(conn, plan)
        print(f"적용: {n} row")
        print("pg mirror:", mirror(conn, [p["id"] for p in plan]))

        # 사후 검증 — 같은 판정을 다시 돌려 잔여가 0 인지 확인한다.
        rows2 = load_rows(conn)
        plan2, _ = build_plan(rows2, args.days)
        print(f"사후 검증: 잔여 변경 대상 {len(plan2)} row (0 이어야 정상)")
        return 0 if not plan2 else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
