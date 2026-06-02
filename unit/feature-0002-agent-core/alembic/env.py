"""Alembic 마이그레이션 환경 — TASK-0143 (#15).

목표: KB Postgres(`agent_kb`) 스키마를 versioned migration 으로 관리하기 위한
env. sqlalchemy URL 은 `.env` 의 `AGENT_KB_PG_*` 환경변수(modules/db.py 의
`_pg_connect()` 와 동일 키)에서 조립한다. 자격증명은 alembic.ini 에 두지 않는다.

드라이버: psycopg (v3) — `postgresql+psycopg://`. 라이브 코드(db.py)가 이미
psycopg v3 를 사용하므로 동일 드라이버로 통일.

offline(`--sql`) 모드:
  - 환경변수가 채워져 있으면 그 값으로 URL 을 조립해 렌더한다.
  - 환경변수가 비어 있어도(예: CI/검증 컨테이너) placeholder URL 로 fallback 해
    `alembic upgrade head --sql` 이 DB 연결 없이 SQL 을 렌더할 수 있게 한다.

online 모드:
  - 실제 DB 에 연결. 단 본 baseline 운영 절차는 `alembic stamp head` 이며,
    기존 라이브 스키마를 alter 하지 않는다(baseline upgrade 는 no-op).
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 본 baseline 은 ORM metadata 를 두지 않는다(스키마 정본은 scripts/agent_kb_schema.sql
# 의 raw DDL). autogenerate 는 후속 단계에서 metadata 도입 시 활성화. 지금은 None.
target_metadata = None


def _build_url() -> str:
    """`.env` 의 AGENT_KB_PG_* 에서 sqlalchemy URL 을 조립한다.

    modules/db.py 의 _pg_connect() 와 동일한 환경변수 키를 재사용해 단일 정본을
    유지한다. host/user 가 비어 있으면(검증 컨테이너 등) offline 렌더를 위한
    placeholder 로 fallback 한다 — 이때 online 연결은 실패하므로 주의.
    """
    host = os.getenv("AGENT_KB_PG_HOST", "").strip() or "localhost"
    port = os.getenv("AGENT_KB_PG_PORT", "").strip() or "5432"
    db = os.getenv("AGENT_KB_PG_DB", "").strip() or "agent_kb"
    user = os.getenv("AGENT_KB_PG_USER", "").strip() or "postgres"
    password = os.getenv("AGENT_KB_PG_PASSWORD", "")
    sslmode = os.getenv("AGENT_KB_PG_SSLMODE", "").strip() or "prefer"

    auth = user
    if password:
        auth = f"{user}:{password}"
    return f"postgresql+psycopg://{auth}@{host}:{port}/{db}?sslmode={sslmode}"


def run_migrations_offline() -> None:
    """offline 모드: 엔진 없이 SQL 을 렌더한다 (`--sql`)."""
    url = config.get_main_option("sqlalchemy.url") or _build_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """online 모드: 실제 DB 에 연결해 마이그레이션을 적용한다."""
    section = config.get_section(config.config_ini_section, {})
    if not section.get("sqlalchemy.url"):
        section["sqlalchemy.url"] = _build_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
