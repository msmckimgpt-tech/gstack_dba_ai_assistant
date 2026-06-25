"""ITEM-01 eval fixture provisioning — 결정적 합성 datasource(eval_fixture) 보장.

멱등: fixtures/schema.sql(DROP+CREATE+seed)을 적용해 매 호출 동일 ground-truth 를
재구성한다. harness 전용 — 운영 datasource/KB/PII 와 무관(완전 합성).

가드: 본 모듈이 만지는 DB 는 eval_fixture 단 하나. runner 가 평가 datasource 를
이 값으로 강제하고, fixture 외 datasource 평가를 거부한다(폐쇄망/PII 가드).
"""
from __future__ import annotations

import os

import mysql.connector

from shared import config as cfg

FIXTURE_DB = "eval_fixture"
_SCHEMA_SQL = os.path.join(os.path.dirname(__file__), "fixtures", "schema.sql")


def fixture_datasource() -> dict:
    """run_agent(eval_datasource=...) 에 주입할 datasource 좌표.

    agent 의 data-plane 연결은 좌표 dict 를 직접 받아 연결한다(config M-1: database=None
    → schema-prefixed 쿼리만, allowlist 가 게이트). root 직결(합성 DB 라 최소권한 불요).
    """
    return {
        "key": FIXTURE_DB,
        "engine": "mysql",
        "host": cfg.DB_HOST,
        "port": int(cfg.DB_PORT),
        "user": cfg.DB_USER,
        "password": cfg.DB_PASSWORD,
        "default_db": FIXTURE_DB,
        "scope_key": f"mysql://{cfg.DB_HOST}:{cfg.DB_PORT}",
    }


def fixture_conn(database: str | None = FIXTURE_DB):
    """harness 자체 연결(provision + ground-truth/생성SQL 실행). root 직결."""
    params: dict = dict(
        host=cfg.DB_HOST,
        port=int(cfg.DB_PORT),
        user=cfg.DB_USER,
        password=cfg.DB_PASSWORD,
        autocommit=True,
        charset="utf8mb4",
        use_unicode=True,
    )
    if database:
        params["database"] = database
    return mysql.connector.connect(**params)


def _split_statements(script: str) -> list[str]:
    """`--` 주석/빈 줄 제거 후 `;` 로 분할(시드 값에 `;` 없음 → 안전).

    C-extension 커넥터(CMySQLCursor)는 execute(multi=True) 미지원 →
    statement 단위 순차 실행이 필요하다.
    """
    no_comments = "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def ensure_fixture() -> None:
    """schema.sql 적용(멱등) — fixture DB 를 결정적으로 재구성."""
    with open(_SCHEMA_SQL, "r", encoding="utf-8") as f:
        statements = _split_statements(f.read())
    conn = fixture_conn(database=None)
    try:
        cur = conn.cursor()
        try:
            for stmt in statements:
                cur.execute(stmt)
                if getattr(cur, "with_rows", False):
                    cur.fetchall()
        finally:
            cur.close()
    finally:
        conn.close()


def run_sql(sql: str) -> tuple[list[str], list[tuple]]:
    """fixture 에 SQL 실행 → (columns, rows). ground-truth/생성SQL 결과 도출용.

    read-only 보장은 호출측(runner._is_readonly)이 사전 검증한다.
    """
    conn = fixture_conn(database=FIXTURE_DB)
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in (cur.description or [])]
            return columns, rows
        finally:
            cur.close()
    finally:
        conn.close()
