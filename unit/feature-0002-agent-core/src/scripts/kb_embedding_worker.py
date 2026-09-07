"""M3 (TASK-0023) — texts.embedding 컬럼 일괄 생성 worker.

§2.1.3 M3 phase + ADR-0021 Blocker B-4 결정: TextHash 별 단일 embedding. 동일 TextHash
의 fact_entries / rag_documents / rag_objects 가 texts join 시 자연 참조.

특성:
- **Batch API call**: OpenAI `text-embedding-3-small` (default) 의 batch endpoint 활용
  — 1 API call 당 N text (default 100). cost 효율.
- **Resumable**: WHERE embedding IS NULL 만 SELECT — 처리된 row 자동 skip. 별 state
  file 불필요.
- **Idempotent**: UPDATE texts SET embedding = ... WHERE text_hash = ? — 재실행 safe.
- **--dry-run**: SELECT count + estimated cost 만, OpenAI 호출 안 함.
- **--max-rows N**: 처리 상한 (cost cap). default: 무제한.
- **--model M**: AGENT_KB_EMBEDDING_MODEL override.

Usage:
    docker exec repo-agent-1 python -m scripts.kb_embedding_worker --dry-run
    docker exec repo-agent-1 python -m scripts.kb_embedding_worker --max-rows 5000
    docker exec repo-agent-1 python -m scripts.kb_embedding_worker --model text-embedding-3-large

Exit codes:
    0 — 모든 NULL embedding row 처리 또는 --max-rows 도달
    1 — API call 실패 또는 일부 row 처리 실패
    2 — invalid args / 환경 부재
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Pricing — text-embedding-3-small / -3-large (2026-Q2 가격 기준 추정).
# 본 추정은 dry-run 의 cost 표시용 — 실 청구는 OpenAI usage report 기준.
# ─────────────────────────────────────────────────────────────────────────────

PRICING_PER_1M_TOKENS = {
    "text-embedding-3-small": 0.02,   # USD per 1M tokens
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}


def open_pg_conn():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared.db import _pg_connect  # type: ignore
    return _pg_connect()


def get_settings() -> dict:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared import config  # type: ignore
    return {
        "model": config.AGENT_KB_EMBEDDING_MODEL,
        "dim": config.AGENT_KB_EMBEDDING_DIM,
        "batch_size": config.AGENT_KB_EMBEDDING_BATCH_SIZE,
        "timeout": config.AGENT_KB_EMBEDDING_TIMEOUT_SEC,
        "max_attempts": config.AGENT_KB_EMBEDDING_MAX_ATTEMPTS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI embedding call — best-effort retry + timeout.
# ─────────────────────────────────────────────────────────────────────────────


def call_openai_embeddings(texts: list[str], model: str, timeout_sec: int, max_attempts: int) -> list[list[float]]:
    """Batch embedding API call. (timeout + retry on transient error).

    Returns: list of float vectors, one per input text. Order preserved.
    Raises: Exception on final failure.
    """
    from shared.config import normalize_kb_embedding_model
    model = normalize_kb_embedding_model(model)
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"openai SDK 미설치: {e}") from e

    # local-llm-decommission(2026-09-07): LOCAL_LLM_* fallback 제거.
    #   종전에는 BEDROCK_GATEWAY_* 가 비면 LOCAL_LLM_API_KEY/BASE 로 강등했는데, 라이브 `.env` 에
    #   그 두 값이 폐기된 게이트웨이(local-llm-gateway)를 가리킨 채 남아 있어 **도달 불가 백엔드로
    #   조용히 흐르는 fail-open 경로**였다(shared/config._select_llm_provider 와 동일 축).
    #   이제 Bedrock 게이트웨이 자격증명이 없으면 정직하게 실패한다.
    # ⚠ **모델 미설정이면 여기서 차단한다 (공유 chokepoint)** — codex 확인 라운드 R2 P2 (2026-09-07).
    #   R1 의 P2 를 `run_embedding_pass` 진입 가드로만 고쳤더니 **형제 진입점 `main()`**
    #   (= `bin/kb-embedding-worker.sh`)이 그 가드를 우회해 `model=""` 를 게이트웨이로 보냈다.
    #   §16.7 G8-a 「모든 호출 경로 열거」의 재발이고, G10 은 재발 클래스를 점수정이 아니라
    #   **구조로 잠그라**고 요구한다. 두 진입점이 반드시 지나는 이 함수에 가드를 둬서 앞으로
    #   추가되는 진입점도 자동으로 덮이게 한다(진입점별 가드는 다음 진입점에서 다시 벌어진다).
    #   호출측 UX 는 각자 담당한다 — `main()` 은 exit 0 + "비활성" 안내,
    #   `run_embedding_pass` 는 PG 연결조차 열지 않는 조기 no-op.
    if not str(model or "").strip():
        raise RuntimeError(
            "임베딩 모델 미설정 — AGENT_KB_EMBEDDING_MODEL 이 빈 값이다. "
            "local-llm-decommission(2026-09-07)으로 임베딩 제공자가 제거됐으므로 이것이 기본 상태다. "
            "임베딩이 필요하면 도달 가능한 제공자를 복구한 뒤 그 alias 를 지정한다."
        )

    # ⚠ **URL·KEY 를 함께 요구한다 (fail-closed)** — codex 적대 리뷰 P1 (2026-09-07).
    #   `base_url` 을 지정하지 않으면 OpenAI SDK 가 기본값 `https://api.openai.com/v1` 로 나간다.
    #   즉 KEY 만 있고 URL 이 없는 구성에서는 **게이트웨이 자격증명과 KB 텍스트가 OpenAI 로 전송**된다.
    #   `docs/SECURITY.md`(CHG-20260522-0006, 사용자 결정 2026-05-22)는 "LLM 호출 entry 는 게이트웨이만
    #   허용" 이고 OpenAI direct 경로를 의도적으로 폐기했으므로, 이 무지정 상태는 그 결정을 우회한다.
    #   `shared/config._select_llm_provider()` 의 **paired tuple** 규약(CHG-20260522-0003)과 같은 축이다.
    api_key = os.environ.get("BEDROCK_GATEWAY_API_KEY")
    api_base = os.environ.get("BEDROCK_GATEWAY_URL")
    if not api_key or not api_base:
        missing = [n for n, v in (("BEDROCK_GATEWAY_URL", api_base),
                                  ("BEDROCK_GATEWAY_API_KEY", api_key)) if not v]
        raise RuntimeError(
            "임베딩 게이트웨이 설정 부재 — " + ", ".join(missing) + " 필요. "
            "둘 중 하나만 있으면 SDK 기본 endpoint(api.openai.com)로 나가므로 진행하지 않는다 "
            "(docs/SECURITY.md — LLM 호출 entry 는 게이트웨이만 허용)."
        )

    client = OpenAI(api_key=api_key, base_url=api_base, timeout=timeout_sec)
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.embeddings.create(model=model, input=texts)
            return [d.embedding for d in resp.data]
        except Exception as e:
            last_exc = e
            wait = min(2 ** attempt, 30)
            print(
                f"[WARN] embedding API attempt {attempt}/{max_attempts} 실패: {e} "
                f"(retry in {wait}s)",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError(f"embedding API 최종 실패 ({max_attempts}회 attempt): {last_exc}") from last_exc


# ─────────────────────────────────────────────────────────────────────────────
# DB I/O — SELECT pending + UPDATE embedding.
# ─────────────────────────────────────────────────────────────────────────────


def count_pending(pg_conn) -> int:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM texts WHERE embedding IS NULL")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def fetch_pending_batch(pg_conn, batch_size: int) -> list[tuple[str, str]]:
    """(text_hash, text_content) tuple list."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT text_hash, text_content FROM texts "
            "WHERE embedding IS NULL "
            "ORDER BY created_at ASC "
            "LIMIT %s",
            (batch_size,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def update_embeddings(pg_conn, hashes: list[str], embeddings: list[list[float]], model: str) -> int:
    """Batch UPDATE — n=len(hashes). returns rowcount sum."""
    if len(hashes) != len(embeddings):
        raise ValueError(f"hashes ({len(hashes)}) ≠ embeddings ({len(embeddings)})")
    sql = (
        "UPDATE texts SET embedding = %s::vector, "
        "embedding_model = %s, embedded_at = now() "
        "WHERE text_hash = %s"
    )
    total = 0
    with pg_conn.cursor() as cur:
        for h, emb in zip(hashes, embeddings):
            cur.execute(sql, (emb, model, h))
            total += cur.rowcount or 0
    pg_conn.commit()
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Cost estimation (dry-run).
# ─────────────────────────────────────────────────────────────────────────────


def estimate_cost_usd(text_lengths: list[int], model: str) -> float:
    """평균 token ≈ char count / 4 (영문 기준 추정; 한국어는 0.5x). 보수적 추정."""
    total_chars = sum(text_lengths)
    estimated_tokens = total_chars / 3.0  # 한국어/혼합 보수 비율
    price_per_1m = PRICING_PER_1M_TOKENS.get(model, 0.10)
    return (estimated_tokens / 1_000_000.0) * price_per_1m


def main() -> int:
    parser = argparse.ArgumentParser(description="texts.embedding 일괄 생성 worker")
    parser.add_argument("--model", default=None, help="default: env AGENT_KB_EMBEDDING_MODEL")
    parser.add_argument("--batch-size", type=int, default=None, help="default: env AGENT_KB_EMBEDDING_BATCH_SIZE")
    parser.add_argument("--max-rows", type=int, default=None, help="처리 상한 (cost cap). default: 무제한")
    parser.add_argument("--dry-run", action="store_true", help="count + cost 추정만, API 호출 안 함")
    args = parser.parse_args()

    settings = get_settings()
    from shared.config import normalize_kb_embedding_model
    model = normalize_kb_embedding_model(args.model or settings["model"])
    batch_size = args.batch_size or settings["batch_size"]
    max_rows = args.max_rows

    # local-llm-decommission(2026-09-07) — codex 확인 라운드 R2 P2.
    #   모델이 비어 있으면 **비활성 상태**이므로 exit 0 으로 조용히 끝낸다. API 실패로
    #   끝내면 cron·래퍼가 이를 "장애" 로 보고 재시도·알림을 쌓는다 — 비활성 ≠ 실패.
    #   `--model` 명시 override 는 위에서 이미 반영되므로 운영자가 제공자를 복구하고
    #   `--model <alias>` 로 부르면 정상 경로를 그대로 탄다(정상 경로 미차단, §16.7 G9-c).
    if not model:
        print(
            "[DISABLED] 임베딩 모델 미설정 (AGENT_KB_EMBEDDING_MODEL 빈 값) — 처리할 것이 없다.\n"
            "           local-llm-decommission(2026-09-07)으로 임베딩 제공자가 제거된 기본 상태다.\n"
            "           제공자를 복구했다면 --model <alias> 또는 .env 의 AGENT_KB_EMBEDDING_MODEL 로 지정한다.",
            file=sys.stderr,
        )
        return 0

    print(f"[INFO] model={model} batch={batch_size} max_rows={max_rows or 'unlimited'} dry-run={args.dry_run}", file=sys.stderr)

    pg_conn = open_pg_conn()
    try:
        pending = count_pending(pg_conn)
        print(f"[INFO] pending embedding rows: {pending}", file=sys.stderr)

        if pending == 0:
            print("[DONE] no pending embeddings", file=sys.stderr)
            return 0

        if args.dry_run:
            # Sample 1 batch for cost estimation
            sample = fetch_pending_batch(pg_conn, min(batch_size, 100))
            sample_lengths = [len(t or "") for _, t in sample]
            avg_len = sum(sample_lengths) / max(len(sample_lengths), 1)
            estimated_total_chars = int(avg_len * pending)
            cost = estimate_cost_usd([estimated_total_chars], model)
            print(
                f"[DRY-RUN] estimated total cost: USD {cost:.4f} "
                f"(sample avg_len={avg_len:.0f}, est_total_chars={estimated_total_chars})",
                file=sys.stderr,
            )
            return 0

        # Real processing
        processed = 0
        failed = 0
        start_ts = time.monotonic()
        while True:
            remaining_budget = (max_rows - processed) if max_rows else None
            this_batch = batch_size if remaining_budget is None else min(batch_size, remaining_budget)
            if this_batch <= 0:
                print(f"[INFO] --max-rows {max_rows} 도달 — 종료", file=sys.stderr)
                break

            batch = fetch_pending_batch(pg_conn, this_batch)
            if not batch:
                print("[DONE] 모든 pending 처리 완료", file=sys.stderr)
                break

            hashes = [h for h, _ in batch]
            texts = [t or "" for _, t in batch]
            try:
                embeddings = call_openai_embeddings(
                    texts, model, settings["timeout"], settings["max_attempts"],
                )
            except Exception as e:
                print(f"[FAIL] batch embedding 실패: {e}", file=sys.stderr)
                failed += len(batch)
                # batch 단위 fail 시 stop — caller 가 root cause 확인 후 재진입.
                break

            try:
                updated = update_embeddings(pg_conn, hashes, embeddings, model)
                processed += updated
            except Exception as e:
                print(f"[FAIL] batch UPDATE 실패: {e}", file=sys.stderr)
                failed += len(batch)
                break

            elapsed = time.monotonic() - start_ts
            rate = processed / max(elapsed, 0.001)
            print(
                f"[PROGRESS] processed={processed} pending_remaining={pending - processed} "
                f"elapsed={elapsed:.1f}s rate={rate:.1f}/s",
                file=sys.stderr,
            )

        return 0 if failed == 0 else 1
    finally:
        try:
            pg_conn.close()
        except Exception:
            pass


def run_embedding_pass(max_rows: "int | None" = None) -> dict:
    """TASK-0307: bounded embedding 백필 1회 — NULL embedding texts 를 max_rows 까지 임베딩.

    main() 의 CLI 루프와 동일 batch 로직을 라이브러리로 노출(insight-worker tick 재사용).
    **fail-soft**: batch(임베딩/UPDATE) 실패 시 그 batch 에서 중단하고 지금까지 처리분 + 에러를
    dict 로 반환(예외 전파 안 함 — caller 루프를 깨지 않음). resumable(WHERE embedding IS NULL).
    max_rows=None 이면 모두, 0/음수면 no-op. 반환: {processed, failed, error, remaining}.
    """
    if max_rows is not None and max_rows <= 0:
        return {"processed": 0, "failed": 0, "error": "", "remaining": None}
    settings = get_settings()
    from shared.config import normalize_kb_embedding_model
    model = normalize_kb_embedding_model(settings["model"])
    # ⚠ **모델 미설정이면 백필 자체를 no-op 으로 둔다** — codex 적대 리뷰 P2 (2026-09-07).
    #   local-llm-decommission 으로 `AGENT_KB_EMBEDDING_MODEL` 기본값이 빈 값이 됐는데,
    #   `AGENT_KB_EMBEDDING_AUTO` 는 여전히 기본 활성(shared/config.py)이라 insight-worker 의
    #   백필 데몬이 `INTERVAL_SEC` 마다 빈 모델명으로 임베딩을 시도한다. 쿼리 임베딩만
    #   `_embed_query_vector` 에서 no-op 이 됐고 **백필 경로는 그 방어를 공유하지 않았다**
    #   (§16.7 G8-a — 결정을 일부 경로에만 반영). 여기서 진입 자체를 막는다.
    #   `error` 를 비워 두는 이유: 이것은 실패가 아니라 **비활성 상태**다 — caller(insight
    #   데몬)가 error 를 로그로 올리므로 사유를 실으면 매 tick 마다 경고가 쌓인다.
    if not model:
        return {"processed": 0, "failed": 0, "error": "", "remaining": None,
                "skipped": "embedding-model-unset"}
    batch_size = settings["batch_size"]
    conn = open_pg_conn()
    processed = 0
    failed = 0
    error = ""
    remaining = None
    try:
        while True:
            remaining_budget = (max_rows - processed) if max_rows else None
            this_batch = batch_size if remaining_budget is None else min(batch_size, remaining_budget)
            if this_batch <= 0:
                break
            batch = fetch_pending_batch(conn, this_batch)
            if not batch:
                break
            hashes = [h for h, _ in batch]
            texts = [t or "" for _, t in batch]
            try:
                embeddings = call_openai_embeddings(
                    texts, model, settings["timeout"], settings["max_attempts"],
                )
                processed += update_embeddings(conn, hashes, embeddings, model)
            except Exception as exc:  # fail-soft — 그 batch 중단, caller 다음 tick 재진입
                failed = len(batch)
                error = str(exc)[:200]
                break
        try:
            remaining = count_pending(conn)
        except Exception:
            remaining = None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"processed": processed, "failed": failed, "error": error, "remaining": remaining}


if __name__ == "__main__":
    sys.exit(main())
