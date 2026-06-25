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
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"openai SDK 미설치: {e}") from e

    api_key = (
        os.environ.get("BEDROCK_GATEWAY_API_KEY")
        or os.environ.get("LOCAL_LLM_API_KEY")
    )
    if not api_key:
        raise RuntimeError("LLM API 자격증명 부재 (BEDROCK_GATEWAY_API_KEY 또는 LOCAL_LLM_API_KEY 필요)")

    api_base = (
        os.environ.get("BEDROCK_GATEWAY_URL")
        or os.environ.get("LOCAL_LLM_API_BASE")
    )
    client_kwargs: dict = {"api_key": api_key, "timeout": timeout_sec}
    if api_base:
        client_kwargs["base_url"] = api_base
    client = OpenAI(**client_kwargs)
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
    model = args.model or settings["model"]
    batch_size = args.batch_size or settings["batch_size"]
    max_rows = args.max_rows

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
    model = settings["model"]
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
