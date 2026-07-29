SHELL := /bin/bash
export PATH := /snap/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$(PATH)

DC := COMPOSE_BAKE=false docker compose
DC_QUIET := $(DC) --ansi=never
# TASK-0126 (#5 split-brain): 빌드 시 현재 HEAD SHA 를 컨테이너에 각인.
# docker-compose.yml 의 build.args GIT_COMMIT 으로 전달 → Dockerfile ARG/ENV → /healthz 노출.
GIT_COMMIT := $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
export GIT_COMMIT
RUNTIME_DIR := ../artifacts
SHARED_DIR := $(RUNTIME_DIR)/shared
MYSQL_DATA_DIR := $(RUNTIME_DIR)/mysql-data
MYSQL_BACKUP_DIR := $(RUNTIME_DIR)/mysql-backup
LOG_DIR := $(SHARED_DIR)/logs
OUT_DIR := $(SHARED_DIR)/out
CERT_ROOT := $(RUNTIME_DIR)/certs
CADDY_DATA_DIR := $(RUNTIME_DIR)/caddy-data
CADDY_CONFIG_DIR := $(RUNTIME_DIR)/caddy-config
ENABLE_MCP ?= $(shell sed -n 's/^ENABLE_MCP=//p' .env | tail -n 1)
ENABLE_INSIGHT_WORKER ?= $(shell sed -n 's/^AGENT_INSIGHT_WORKER_ENABLED=//p' .env | tail -n 1)
ENABLE_WEB_TLS ?= $(shell sed -n 's/^ENABLE_WEB_TLS=//p' .env | tail -n 1)
ENABLE_WEB_TLS_PROXY ?= $(shell sed -n 's/^ENABLE_WEB_TLS_PROXY=//p' .env | tail -n 1)
MEMORY_DB ?= $(shell sed -n 's/^AGENT_MEMORY_DB=//p' .env | tail -n 1)
WEB_PORT ?= $(shell sed -n 's/^WEB_PORT=//p' .env | tail -n 1)
WEB_PUBLIC_HOST ?= $(shell sed -n 's/^WEB_PUBLIC_HOST=//p' .env | tail -n 1)
WEB_LAN_IP ?= $(shell sed -n 's/^WEB_LAN_IP=//p' .env | tail -n 1)
BROWSER_PORT ?= $(shell sed -n 's/^BROWSER_PORT=//p' .env | tail -n 1)
BROWSER_URL ?= $(shell sed -n 's/^BROWSER_URL=//p' .env | tail -n 1)
REPLICA_NETWORK_NAME ?= $(shell v=$$(sed -n 's/^REPLICA_NETWORK_NAME=//p' .env | tail -n 1); echo $${v:-replica-net})
SESSION_TAG ?=
SESSION_BASE := $(shell sh -lc 'u=$$(id -un); t=$$(tty 2>/dev/null || true); if [ -n "$$t" ] && [ "$$t" != "not a tty" ]; then t=$${t#/dev/}; echo "$$u_$$t"; else echo "$$u"; fi' | tr -c 'A-Za-z0-9_.-' '_')
SESSION ?= $(SESSION_BASE)$(if $(SESSION_TAG),_$(SESSION_TAG),)
CONV_FILE ?= /shared/conversation_id.$(SESSION)
BROWSER_SESSION_FILE ?= /shared/browser_session_id.$(SESSION)
BROWSER_CTL := $(DC_QUIET) run --rm --entrypoint python --env BROWSER_SESSION_FILE=$(BROWSER_SESSION_FILE) --env BROWSER_URL=$(BROWSER_URL) browser /app/ctl.py

.DEFAULT_GOAL := help

.PHONY: help \
        check-llm-network ensure-replica-network replica-check wait-mysql ensure-memory-db \
        up down start stop restart status build test backup gc embed ps logs init clean clear \
        sh repl ask mysql out dump session-info dc-build \
        migrate migrate-stamp migrate-new \
        mcp-up mcp-down mcp-test \
        convo-list convo-new convo-use convo-delete convo-rename convo-clear \
        web web-down web-tls-cert web-tls-up web-tls-down web-tls-status web-tls-logs \
        insight-up insight-down insight-logs insight-status \
        browser-up browser-down browser-health browser-session \
        browser-goto browser-click browser-type browser-set-value browser-eval \
        browser-press browser-hover browser-mousedown browser-mouseup browser-scroll \
        browser-wait browser-text browser-html browser-shot browser-close

# -----------------------------------------------------------------------------
# help: 사용 가능한 make 타깃 목록을 카테고리별로 출력한다.
# 각 타깃 옆 `## <category>: <설명>` 주석을 카테고리 기준으로 그룹화한다.
# -----------------------------------------------------------------------------
help:  ## meta: 이 도움말을 출력한다 (기본 타깃)
	@awk 'BEGIN { \
		FS = ":.*?## "; \
		printf "\nmysql_ai_delegated_dev — make 타깃 목록\n"; \
		printf "사용법: make <target> [VAR=value ...]\n\n"; \
	} \
	/^[a-zA-Z0-9_-]+:.*?## .+$$/ { \
		split($$2, parts, ": "); \
		cat = parts[1]; \
		desc = $$2; \
		sub(/^[^:]+: /, "", desc); \
		entries[cat] = entries[cat] sprintf("  \033[36m%-22s\033[0m %s\n", $$1, desc); \
		if (!(cat in seen)) { order[++n] = cat; seen[cat] = 1; } \
	} \
	END { \
		for (i = 1; i <= n; i++) { \
			c = order[i]; \
			printf "\033[1m[%s]\033[0m\n%s\n", c, entries[c]; \
		} \
	}' $(MAKEFILE_LIST)

# =============================================================================
# 내부 prerequisites (사용자가 직접 호출하지 않음 — help 에서 숨김)
# =============================================================================

check-llm-network: ensure-replica-network
	@docker network inspect llm-shared >/dev/null 2>&1 || { \
		echo "llm-shared 외부 네트워크를 찾을 수 없습니다." >&2; \
		echo "현재 repo는 Local LLM을 직접 기동하지 않습니다. 먼저 /root/download/docker/local_llm 에서 provider를 준비하세요." >&2; \
		exit 1; \
	}

# replica-net 은 AI 전용 복제 MySQL 이 있는 docker network (기본 이름 replica-net).
# REPLICA_DB_* 를 쓰지 않는 배포에서도 idempotent 하게 스텁 네트워크를 만들어
# compose up 이 external network 미존재로 실패하지 않도록 한다.
ensure-replica-network:
	@docker network inspect $(REPLICA_NETWORK_NAME) >/dev/null 2>&1 \
		|| docker network create $(REPLICA_NETWORK_NAME) >/dev/null

wait-mysql:
	@container_id="$$( $(DC_QUIET) ps -q mysql )"; \
	if [[ -z "$$container_id" ]]; then \
		echo "mysql service container not found" >&2; \
		exit 1; \
	fi; \
	for i in $$(seq 1 60); do \
		status=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$$container_id" 2>/dev/null || true); \
		if [[ "$$status" == "healthy" ]]; then \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "mysql service healthcheck timed out" >&2; \
	exit 1

ensure-memory-db:
	@$(DC_QUIET) exec -T mysql sh -lc 'mysql -uroot -p"$$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS \`$(MEMORY_DB)\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'

# docker compose v5.1.1 + buildx v0.31.1 환경에서 image 빌드 자체는 성공하지만 compose 가
# provenance metadata file 의 후처리(`#16 resolving provenance for metadata file` 직후 임시
# 파일 path 에 random suffix mismatch) 단계에서 EXIT=1 로 종료되는 race 를 흡수한다.
# image 가 정상 생성된 케이스만 EXIT=0 으로 정규화하고 다른 빌드 오류는 그대로 전파한다.
# Usage: $(MAKE) dc-build SERVICE=web
dc-build:
	@if [ -z "$(SERVICE)" ]; then echo "dc-build: SERVICE 변수 필요 (예: SERVICE=web)" >&2; exit 1; fi
	@set -e; \
	tmp_log=$$(mktemp); \
	if $(DC_QUIET) build $(SERVICE) > $$tmp_log 2>&1; then \
		cat $$tmp_log; rm -f $$tmp_log; \
	else \
		status=$$?; cat $$tmp_log; \
		if grep -q "compose-build-metadataFile" $$tmp_log; then \
			echo "[make] note: docker compose v5.1.1+buildx v0.31.1 의 provenance metadata file race 우회 — $(SERVICE) image 빌드 OK, compose EXIT=$$status 무시" >&2; \
			rm -f $$tmp_log; \
		else \
			rm -f $$tmp_log; exit $$status; \
		fi; \
	fi

# =============================================================================
# Lifecycle — 도커 환경 기동/중지/재시작
# =============================================================================

up:  ## lifecycle: 전체 스택 빌드 + 기동 (mysql, web, browser, insight-worker, [mcp], [caddy])
	@$(MAKE) check-llm-network
	@mkdir -p $(SHARED_DIR) $(MYSQL_DATA_DIR) $(MYSQL_BACKUP_DIR) $(LOG_DIR) $(OUT_DIR) $(SHARED_DIR)/web_sessions $(SHARED_DIR)/out/browser $(CERT_ROOT)/$(WEB_PUBLIC_HOST) $(CADDY_DATA_DIR) $(CADDY_CONFIG_DIR)
	@chown -R 999:999 $(MYSQL_DATA_DIR) || true
	@chmod -R 770 $(MYSQL_DATA_DIR) $(MYSQL_BACKUP_DIR) $(LOG_DIR) $(OUT_DIR) || true
	@# docker compose v5.1 + buildx v0.31 은 build 후처리에서 `--metadata-file` 임시파일을
	@# race-unlink 하여 빌드는 성공해도 exit 1 을 반환하는 알려진 이슈가 있다.
	@# 종료코드는 흡수하고, 직후 이미지 존재 여부로 실제 빌드 성공을 검증한다.
	@# feature-0014: web 은 web-a/web-b 두 replica(무중단 롤링). 동일 Dockerfile 이라 빌드
	@# 캐시로 사실상 build-once. (라이브 무중단 재배포는 'make deploy-web' = bin/deploy-web.sh.)
	@# feature-0020: ask-worker 를 빌드 목록에 추가(cold up 시 이미지 미빌드로 기동 불가하던 공백).
	@$(DC_QUIET) build agent memory-init insight-worker ask-worker web-a web-b browser || true
	@for img in repo-agent repo-memory-init repo-insight-worker repo-ask-worker repo-web-a repo-web-b repo-browser; do \
		docker image inspect $$img >/dev/null 2>&1 \
			|| { echo "[make up] 빌드된 이미지 누락: $$img" >&2; exit 1; }; \
	done
	@# 위 build 단계에서 이미 이미지가 만들어졌으므로 후속 `up` 은 `--build` 없이 호출한다.
	@# (`--build` 를 다시 주면 동일 metadata-file race 가 재발한다.)
	@$(DC_QUIET) up -d mysql web-a web-b browser
	@$(MAKE) wait-mysql
	@$(MAKE) ensure-memory-db
	@if [[ "$(ENABLE_WEB_TLS_PROXY)" == "1" ]]; then \
		$(DC_QUIET) up -d caddy; \
	else \
		$(DC_QUIET) stop caddy >/dev/null 2>&1 || true; \
	fi
	@$(DC_QUIET) run --rm memory-init
	@if [[ "$(ENABLE_INSIGHT_WORKER)" != "0" ]]; then \
		$(DC_QUIET) up -d insight-worker; \
	else \
		$(DC_QUIET) stop insight-worker >/dev/null 2>&1 || true; \
	fi
	@# feature-0020 (리뷰 M-4): ask-worker 기동 — web 이 AGENT_ASK_EXECUTION_MODE=worker 로
	@# 운영 중이라(라이브 실측) cold up 에서 워커 부재 시 사용자 질문이 enqueue 만 되고 hang.
	@# inprocess 모드에서는 shadow-safe(떠 있어도 동작 무변경)라 무조건 기동이 안전 기본값.
	@if [[ "$(ENABLE_ASK_WORKER)" != "0" ]]; then \
		$(DC_QUIET) up -d ask-worker; \
	else \
		$(DC_QUIET) stop ask-worker >/dev/null 2>&1 || true; \
	fi
	@if [[ "$(ENABLE_MCP)" == "1" ]]; then \
		$(DC_QUIET) --profile mcp up -d mcp; \
	fi

start:  ## lifecycle: up 후 ps 로 상태 표시 (사용자 편의 alias)
	@echo "Starting docker environment..."
	@$(MAKE) up
	@$(MAKE) ps

down:  ## lifecycle: 전체 스택 정지 (볼륨 보존)
	@$(DC_QUIET) down

stop: down  ## lifecycle: down 의 alias

restart: down up  ## lifecycle: down 후 up

build:  ## lifecycle: 모든 서비스 이미지를 --no-cache 로 재빌드
	@$(DC_QUIET) build --no-cache

# 단위 테스트 컨테이너의 라이브 자원 차단 backstop (test-live-db-isolation, 2026-07-29).
#
# `--no-deps` 는 의존 서비스를 *기동*하지 않을 뿐, **이미 떠 있는 운영 컨테이너와의 연결을
# 막지 않는다**. agent 서비스는 `networks: [dbnet, ...]` + `env_file: .env/.env.mysql` +
# `volumes: ../artifacts/shared:/shared` 를 상속하므로, 운영 스택이 떠 있는 개발 머신에서
# pytest 가 라이브 MySQL(agent_memory)·라이브 스냅샷 파일에 그대로 도달한다.
# 실측 사고: 관리 콘솔 런타임 설정(에이전트/쿼리 실행 타임아웃 등)이 테스트 리터럴 값으로
# 150회 덮어써짐(audit RemoteAddr=testclient, 2026-07-13~29).
#
# 아래 override 로 테스트 프로세스에서 라이브 오염 표면을 끊는다.
#   DB_PORT=1     — memory/data MySQL 을 도달 불가로. 닫힌 포트라 즉시 connection refused
#                   (타임아웃 대기 없음 → 테스트가 느려지지 않는다). DB_HOST 는 건드리지 않는다:
#                   app 이 DB_HOST 를 datasource SSRF allowlist 에 implicit 추가하므로(TASK-0214)
#                   호스트를 바꾸면 SSRF 가드 테스트가 오염된다.
#   RUNTIME_SETTINGS_SNAPSHOT_PATH — `/shared` 공유 볼륨 대신 컨테이너 임시 파일. 스냅샷은
#                   web·워커가 TTL 로 읽는 live 전파 채널이라, DB 를 막아도 여기 쓰면 오염된다.
# PG(AGENT_KB_PG_*) 는 의도적으로 두지 않는다 — 현재 일부 테스트가 라이브 PG 읽기에 의존해
# 통과하고 있어, 함께 끊으면 본 cycle 의 scope 를 넘는 회귀가 난다(REPORT 후속 항목).
# 애플리케이션 레벨 차단(_connect_memory)은 web-ui `tests/conftest.py` 참조 — 2중 방어.
TEST_ISOLATION_ENV := \
  -e DB_PORT=1 \
  -e RUNTIME_SETTINGS_SNAPSHOT_PATH=/tmp/runtime_settings.test.json

test:  ## ci: 단위 테스트(pytest) + 린트(ruff) — agent 이미지 격리 컨테이너에서 실행 (psycopg 등 런타임 의존 포함, --no-deps + 라이브 DB/스냅샷 차단 env)
	@$(MAKE) -s dc-build SERVICE=agent
	@$(DC_QUIET) run --rm --no-deps $(TEST_ISOLATION_ENV) -v "$(CURDIR):/work" -w /work --entrypoint sh agent -lc '\
	  pip install -q --no-cache-dir pytest ruff >/tmp/pip-dev.log 2>&1 || { cat /tmp/pip-dev.log; exit 1; }; \
	  export PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0003-agent-web-ui/src:/work; \
	  echo "=== pytest ==="; \
	  python -m pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests unit/feature-0023-conversation-api-access/tests; rc=$$?; \
	  echo "=== ruff (참고용, 비차단) ==="; \
	  ruff check unit/feature-0002-agent-core/src unit/feature-0003-agent-web-ui/src || true; \
	  exit $$rc'

eval:  ## ci: NL→SQL 평가 harness (ITEM-01) — golden 질문을 실제 파이프라인에 흘려 execution-accuracy 측정. 라이브 Bedrock 소비(judge cap). 옵션: EVAL_ARGS="--limit 6 --judge"
	@$(MAKE) -s dc-build SERVICE=agent
	@$(DC_QUIET) run --rm --no-deps \
	  -e AGENT_MULTI_DATASOURCE_ENABLED=1 \
	  -e EVAL_MAX_JUDGE_CALLS=$${EVAL_MAX_JUDGE_CALLS:-25} \
	  -v "$(CURDIR):/work" -w /work --entrypoint sh agent -lc '\
	  pip install -q --no-cache-dir pyyaml >/tmp/pip-eval.log 2>&1 || { cat /tmp/pip-eval.log; exit 1; }; \
	  export PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0002-agent-core/tests/eval:/work; \
	  python /work/unit/feature-0002-agent-core/tests/eval/runner.py $(EVAL_ARGS); \
	'

kb-retrieval-eval:  ## ci: KB retrieval A/B (ITEM-05) — fusion vs 2-tier precision/recall@k. evalkb scope 격리 + 라이브 bge-m3 임베딩. 옵션: KB_EVAL_ARGS="--provision --purge-after --k 5"
	@$(MAKE) -s dc-build SERVICE=agent
	@$(DC_QUIET) run --rm \
	  -v "$(CURDIR):/work" -w /work --entrypoint sh agent -lc '\
	  pip install -q --no-cache-dir pyyaml >/tmp/pip-kbeval.log 2>&1 || { cat /tmp/pip-kbeval.log; exit 1; }; \
	  export PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0002-agent-core/tests/eval:/work; \
	  python -m kb_eval.retrieval_eval $(KB_EVAL_ARGS); \
	'

backup:  ## ops: 플랫폼 정본 데이터 논리 백업 (PG agent_kb + MySQL agent_memory) — TASK-0130
	@bash bin/backup.sh

restore-rehearsal:  ## ops: 최신 백업을 throwaway DB 로 복원 검증 (복원 가능성 리허설) — feature-0015
	@bash bin/restore-rehearsal.sh $(RESTORE_REHEARSAL_ARGS)

install-backup-cron:  ## ops: 정기 백업(매일) + 복원 리허설(주간) cron 설치(멱등) — feature-0015
	@bash bin/install-backup-cron.sh $(CRON_ARGS)

gc:  ## ops: 운영 데이터 GC — kv 고아행 + 만료 세션 정리 (멱등) — TASK-0134
	@bash bin/gc.sh

embed:  ## ops: KB 임베딩 백필 (texts.embedding NULL 채움, Titan v2) — TASK-0135
	@# feature-0014: web → web-a (2-replica). 어느 replica 에서 실행해도 동일(공유 DB).
	@$(DC_QUIET) exec -T -w /app web-a python -m scripts.kb_embedding_worker || docker exec -w /app repo-web-a-1 python -m scripts.kb_embedding_worker

# =============================================================================
# Status — 상태 / 로그 / 진단
# =============================================================================

ps:  ## status: docker compose ps
	@$(DC_QUIET) ps

status: ps  ## status: ps 의 alias

logs:  ## status: 전체 서비스 로그를 tail -200 으로 follow
	@$(DC_QUIET) logs -f --tail=200

session-info:  ## status: 현재 SESSION 식별자와 conversation/browser 파일 경로 출력
	@echo "SESSION_BASE=$(SESSION_BASE)"
	@echo "SESSION_TAG=$(SESSION_TAG)"
	@echo "SESSION=$(SESSION)"
	@echo "CONV_FILE=$(CONV_FILE)"
	@echo "BROWSER_SESSION_FILE=$(BROWSER_SESSION_FILE)"

out:  ## status: shared/out 과 shared/logs 디렉토리 내용 표시
	@echo "[host $(OUT_DIR)]"; \
	ls -alh $(OUT_DIR) 2>/dev/null || true; \
	echo ""; \
	echo "[host $(LOG_DIR)]"; \
	ls -alh $(LOG_DIR) 2>/dev/null || true

replica-check:  ## status: replica MySQL 네트워크 도달 가능성 점검
	@$(MAKE) check-llm-network
	@./scripts/check_replica.sh

# =============================================================================
# Agent — 대화형/일회성 agent 실행
# =============================================================================

sh:  ## agent: agent 컨테이너에 bash 진입
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --entrypoint bash agent

repl:  ## agent: agent REPL 모드
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --repl

ask: init  ## agent: 1회성 질의 실행 (사용법: make ask q="질문")
	@if [[ -z "$(q)" ]]; then \
		echo '사용법: make ask q="질문"'; \
		exit 1; \
	fi
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent "$(q)"

init:  ## agent: memory DB 초기화 (idempotent — SKIP_INIT=1 로 우회 가능)
	@if [ "$(SKIP_INIT)" = "1" ]; then \
		exit 0; \
	fi
	@$(DC_QUIET) run --rm --remove-orphans memory-init

# =============================================================================
# Database — MySQL 직접 점검 / 덤프
# =============================================================================

mysql: init  ## db: mysql 클라이언트로 SQL 실행 (사용법: make mysql sql="SELECT 1;")
	@if [[ -z "$(sql)" ]]; then \
		echo '사용법: make mysql sql="SELECT 1;"'; \
		exit 1; \
	fi
	@$(MAKE) check-llm-network
	@$(DC_QUIET) run --rm --remove-orphans --entrypoint bash --env SQL="$(sql)" agent -lc 'mysql -h "$$DB_HOST" -P "$$DB_PORT" -u "$$DB_USER" -p"$$DB_PASSWORD" -e "$$SQL"'

dump:  ## db: 특정 데이터베이스 덤프 (사용법: make dump db=name [file=out.sql])
	@if [[ -z "$(db)" ]]; then \
		echo '사용법: make dump db=데이터베이스명 [file=파일명.sql]'; \
		exit 1; \
	fi
	@f="$${file:-$(db)_$$(date +%Y%m%d_%H%M%S).sql}"; \
	$(DC_QUIET) exec -T mysql sh -lc 'mysqldump --defaults-extra-file=/etc/mysql/conf.d/99-mysql-ai-client.cnf --quote-names -uroot -p"$$MYSQL_ROOT_PASSWORD" --databases '"$(db)"' > /shared/mysql-backup/'"$$f"'' \
	&& echo "덤프 저장: $(MYSQL_BACKUP_DIR)/$$f"

# =============================================================================
# Migrations — Alembic (KB Postgres agent_kb) — TASK-0143 (#15)
# 스키마 정본은 unit/feature-0002-agent-core/alembic/. agent 이미지 격리 컨테이너에서
# 실행하고 .env 의 AGENT_KB_PG_* 를 env.py 가 URL 로 조립한다. additive 도입:
# 라이브 기존 DB 는 migrate-stamp 로 baseline 표시(스키마 변경 0), 신규 변경만 versioned.
# 자세한 절차는 unit/feature-0002-agent-core/docs/MIGRATIONS.md 참조.
# =============================================================================
# TASK-0149 (#15): alembic.ini/alembic 는 Dockerfile 이 이미지의 /app 에 baking 한다.
# privileged DDL(스키마 변경)은 postgres 로컬 trust 소켓 전용이므로 적용은
# bin/alembic-migrate.sh 가 담당한다(agent 컨테이너 offline `--sql` → postgres 소켓).
# =============================================================================

# TASK-0149 (#15): privileged DDL 은 postgres 로컬 trust 소켓 전용(agent 컨테이너 TCP scram
# 불가). 그래서 migrate/migrate-stamp 는 bin/alembic-migrate.sh 가 agent 컨테이너에서 offline
# `--sql` 생성 → postgres 컨테이너 로컬 소켓 superuser 로 적용한다(인증 변경 0). app(agent_kb_rw)
# 은 의도적 무-DDL 이라 online alembic 을 app 유저로 돌리면 'permission denied' 로 실패한다.
migrate:  ## db: KB 스키마 마이그레이션 적용 (offline SQL → postgres 로컬 소켓 superuser)
	@$(MAKE) -s dc-build SERVICE=agent
	@bin/alembic-migrate.sh upgrade

migrate-stamp:  ## db: 라이브 기존 DB 를 head baseline 으로 표시 (스키마 변경 0, 멱등)
	@$(MAKE) -s dc-build SERVICE=agent
	@bin/alembic-migrate.sh stamp

migrate-current:  ## db: 라이브 현재 alembic revision 조회
	@bin/alembic-migrate.sh current

migrate-lint:  ## db: 신규 alembic revision 의 expand/contract 안전성 검사 (무중단 배포 게이트, feature-0014)
	@bin/migrate-lint.sh $(MIGRATE_LINT_ARGS)

pg-restart:  ## db: PG primary 를 near-zero RW 단절로 재시작 (pgbouncer PAUSE→restart→RESUME) — feature-0016
	@sudo -E bin/pg-restart.sh $(PG_RESTART_ARGS)

mysql-ddl-lint:  ## db: 신규 MySQL ALTER 의 online-DDL(LOCK=NONE) 강제 검사 (무중단, feature-0015)
	@bin/mysql-ddl-lint.sh $(MYSQL_DDL_LINT_ARGS)

migrate-new:  ## db: 신규 revision 생성 (사용법: make migrate-new name="add_xyz" [auto=1]) — 생성 파일은 repo 의 alembic/versions 에 저장
	@if [[ -z "$(name)" ]]; then \
		echo '사용법: make migrate-new name="add_xyz" [auto=1]'; \
		exit 1; \
	fi
	@$(MAKE) -s dc-build SERVICE=agent
	$(DC_QUIET) run --rm --no-deps -w /app \
	  -v "$(PWD)/unit/feature-0002-agent-core/alembic:/app/alembic" \
	  --entrypoint sh agent -lc '\
	  pip install -q --no-cache-dir alembic "psycopg[binary]" sqlalchemy >/tmp/pip-alembic.log 2>&1 || { cat /tmp/pip-alembic.log; exit 1; }; \
	  alembic revision $(if $(filter 1,$(auto)),--autogenerate ,)-m "$(name)"'

# =============================================================================
# Conversation — agent 대화 슬롯 관리
# =============================================================================

convo-list: init  ## convo: 저장된 대화 목록 표시
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --list-conversations

convo-new: init  ## convo: 새 대화 시작
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --new-conversation

convo-use: init  ## convo: 특정 대화로 전환 (사용법: make convo-use index=N [q="질문"])
	@if [[ -z "$(index)" ]]; then \
		echo '사용법: make convo-use index=1 q="질문"'; \
		exit 1; \
	fi
	@$(MAKE) check-llm-network
	@if [[ -z "$(q)" ]]; then \
		AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --use-conversation-index "$(index)"; \
	else \
		AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --use-conversation-index "$(index)" "$(q)"; \
	fi

convo-delete: init  ## convo: 특정 대화 삭제 (사용법: make convo-delete index=N)
	@if [[ -z "$(index)" ]]; then \
		echo '사용법: make convo-delete index=1'; \
		exit 1; \
	fi
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --delete-conversation-index "$(index)"

convo-rename: init  ## convo: 대화 주제 변경 (사용법: make convo-rename index=N topic="새 주제")
	@if [[ -z "$(index)" || -z "$(topic)" ]]; then \
		echo '사용법: make convo-rename index=1 topic="새 주제"'; \
		exit 1; \
	fi
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent --rename-conversation-index "$(index)" --rename-topic "$(topic)"

convo-clear: init  ## convo: 모든 메모리 테이블 비우기
	@$(MAKE) check-llm-network
	@AGENT_CONVERSATION_ID_FILE=$(CONV_FILE) $(DC_QUIET) run --rm --remove-orphans agent "__CLEAR_MEMORY_TABLES__"

# =============================================================================
# Web — Web UI / TLS Proxy
# =============================================================================

web: init  ## web: Web UI 기동 (web-a/web-b 2-replica + Caddy :443 단일 진입). 라이브 무중단 재배포는 'make deploy-web'.
	@if [ "$(ENABLE_WEB_TLS)" = "1" ]; then $(MAKE) -s web-tls-cert; fi
	@$(MAKE) check-llm-network
	@# feature-0014: 두 replica(web-a/web-b). 동일 Dockerfile 이라 빌드 캐시로 사실상 build-once.
	@$(DC_QUIET) build web-a web-b || true
	@for img in repo-web-a repo-web-b; do docker image inspect $$img >/dev/null 2>&1 || { echo "[make web] 이미지 누락: $$img" >&2; exit 1; }; done
	@$(DC_QUIET) up -d --no-build web-a web-b
	@$(MAKE) -s web-tls-cert
	@mkdir -p $(CADDY_DATA_DIR) $(CADDY_CONFIG_DIR)
	@$(DC_QUIET) up -d caddy
	@echo "Web UI: https://$(WEB_PUBLIC_HOST)  (Caddy :443 단일 진입 — :18080 web 직접 문은 feature-0014 에서 폐기)"
	@if [ -n "$(WEB_LAN_IP)" ]; then echo "LAN 접속: https://$(WEB_PUBLIC_HOST) (LAN IP $(WEB_LAN_IP) → DNS/hosts 매핑)"; fi

deploy-web:  ## web: 라이브 무중단(zero-downtime) 전체 롤아웃 — web 롤링 + 워커 + gateway reconcile (origin/main HEAD). 헤더의 scoped sudo 필요.
	@sudo -E bin/deploy-web.sh

deploy-all: deploy-web  ## web: deploy-web 의 명시적 alias (feature-0020 — 스파인이 전 배포 대상을 커버)

deploy-web-only:  ## web: web(+caddy reconcile)만 롤링 재배포 (구 feature-0014 범위)
	@sudo -E bin/deploy-web.sh --web-only

deploy-workers:  ## web: 워커(insight/ask)+gateway 만 롤아웃 (마이그 없는 워커 코드/설정 변경 전용)
	@sudo -E bin/deploy-web.sh --workers-only

web-rollback:  ## web: 직전 정상 이미지(last-good)로 무중단 롤백 (web + 워커)
	@sudo -E bin/deploy-web.sh --rollback

web-down:  ## web: Web UI + caddy 정지
	@$(DC_QUIET) stop caddy 2>/dev/null || true
	@$(DC_QUIET) stop web-a web-b || true

web-tls-cert:  ## web: 자체 서명 인증서 생성 (이미 있으면 재사용)
	@mkdir -p $(CERT_ROOT)/$(WEB_PUBLIC_HOST)
	@if [ ! -f $(CERT_ROOT)/$(WEB_PUBLIC_HOST)/fullchain.pem ]; then \
		echo "  자체 서명 인증서 생성 중..."; \
		SAN="DNS:$(WEB_PUBLIC_HOST),DNS:localhost,IP:127.0.0.1"; \
		if [ -n "$(WEB_LAN_IP)" ]; then SAN="$$SAN,IP:$(WEB_LAN_IP)"; fi; \
		openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
			-keyout $(CERT_ROOT)/$(WEB_PUBLIC_HOST)/privkey.pem \
			-out $(CERT_ROOT)/$(WEB_PUBLIC_HOST)/fullchain.pem \
			-subj "/CN=$(WEB_PUBLIC_HOST)" \
			-addext "subjectAltName=$$SAN" 2>/dev/null; \
		echo "  인증서 생성 완료: $(CERT_ROOT)/$(WEB_PUBLIC_HOST)/"; \
	else \
		echo "  기존 인증서 사용: $(CERT_ROOT)/$(WEB_PUBLIC_HOST)/"; \
	fi

web-tls-up: init web-tls-cert  ## web: web-a/web-b + caddy 를 TLS 모드로 기동
	@mkdir -p $(CADDY_DATA_DIR) $(CADDY_CONFIG_DIR)
	@$(MAKE) check-llm-network
	@$(DC_QUIET) up -d --build web-a web-b
	@$(DC_QUIET) up -d caddy
	@echo "TLS Web UI: https://$(WEB_PUBLIC_HOST)"
	@if [ -n "$(WEB_LAN_IP)" ]; then echo "LAN 접속: https://$(WEB_PUBLIC_HOST)"; fi

web-tls-down:  ## web: caddy 만 정지
	@$(DC_QUIET) stop caddy || true

web-tls-status:  ## web: web-a/web-b + caddy 컨테이너 상태 표시
	@$(DC_QUIET) ps web-a web-b caddy

web-tls-logs:  ## web: caddy 로그 follow
	@$(DC_QUIET) logs -f --tail=200 caddy

# =============================================================================
# Insight worker
# =============================================================================

insight-up:  ## insight: insight-worker 기동
	@$(MAKE) check-llm-network
	@$(MAKE) -s dc-build SERVICE=insight-worker
	@$(DC_QUIET) up -d --no-build insight-worker

insight-down:  ## insight: insight-worker 정지
	@$(DC_QUIET) stop insight-worker || true

insight-status:  ## insight: insight-worker 컨테이너 상태 표시
	@$(DC_QUIET) ps insight-worker

insight-logs:  ## insight: insight-worker 로그 follow
	@$(DC_QUIET) logs -f --tail=200 insight-worker

# =============================================================================
# Ask worker (feature-0020 — insight 와 대칭 운영 타깃)
# =============================================================================

ask-worker-up:  ## ask-worker: ask-worker 기동
	@$(MAKE) check-llm-network
	@$(MAKE) -s dc-build SERVICE=ask-worker
	@$(DC_QUIET) up -d --no-build ask-worker

ask-worker-down:  ## ask-worker: ask-worker 정지 (graceful — stop_grace 70s, in-flight run 은 lease requeue)
	@$(DC_QUIET) stop ask-worker || true

ask-worker-status:  ## ask-worker: ask-worker 컨테이너 상태 표시
	@$(DC_QUIET) ps ask-worker

ask-worker-logs:  ## ask-worker: ask-worker 로그 follow
	@$(DC_QUIET) logs -f --tail=200 ask-worker

# =============================================================================
# MCP — Model Context Protocol 서버 (선택)
# =============================================================================

mcp-up:  ## mcp: MCP 서버 기동 (profile=mcp)
	@$(DC_QUIET) --profile mcp up -d mcp

mcp-down:  ## mcp: MCP 서버 정지
	@$(DC_QUIET) stop mcp || true

mcp-test:  ## mcp: MCP 엔드포인트 테스트 (unit/feature-0005-qa-mcp)
	@MCP_TEST_URL=http://localhost:$(shell sed -n 's/^MCP_HOST_PORT=//p' .env | tail -n 1)/mcp python3 unit/feature-0005-qa-mcp/src/mcp_tests.py

# =============================================================================
# Browser — 헤드리스 브라우저 제어
# =============================================================================

browser-up:  ## browser: browser 서비스 기동
	@$(MAKE) -s dc-build SERVICE=browser
	@$(DC_QUIET) up -d --no-build browser
	@echo "Browser service: http://localhost:$(BROWSER_PORT)"

browser-down:  ## browser: browser 서비스 정지
	@$(DC_QUIET) stop browser || true

browser-health:  ## browser: health 체크
	@$(BROWSER_CTL) health

browser-session:  ## browser: 세션 시작 (옵션: ip="x.x.x.x")
	@$(BROWSER_CTL) session $(if $(ip),--ip "$(ip)",)

browser-goto:  ## browser: URL 로 이동 (사용법: make browser-goto url="https://...")
	@if [[ -z "$(url)" ]]; then \
		echo '사용법: make browser-goto url="https://example.com"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) goto --url "$(url)"

browser-click:  ## browser: selector 클릭 (사용법: selector="...")
	@if [[ -z "$(selector)" ]]; then \
		echo '사용법: make browser-click selector="css-selector"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) click --selector "$(selector)"

browser-type:  ## browser: input 에 키 입력 (사용법: selector="..." text="...")
	@if [[ -z "$(selector)" || -z "$(text)" ]]; then \
		echo '사용법: make browser-type selector="css-selector" text="입력값"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) type --selector "$(selector)" --text "$(text)"

browser-set-value:  ## browser: input value 직접 설정 (사용법: selector="..." text="...")
	@if [[ -z "$(selector)" || -z "$(text)" ]]; then \
		echo '사용법: make browser-set-value selector="css-selector" text="입력값"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) set_value --selector "$(selector)" --text "$(text)"

browser-eval:  ## browser: JS 평가 (사용법: script="...")
	@if [[ -z "$(script)" ]]; then \
		echo '사용법: make browser-eval script="document.querySelector(...)"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) eval --script "$(script)"

browser-press:  ## browser: 특정 키 입력 (사용법: selector="..." key="Enter")
	@if [[ -z "$(selector)" || -z "$(key)" ]]; then \
		echo '사용법: make browser-press selector="css-selector" key="Enter"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) press --selector "$(selector)" --key "$(key)"

browser-hover:  ## browser: selector 위에 마우스 호버 (사용법: selector="...")
	@if [[ -z "$(selector)" ]]; then \
		echo '사용법: make browser-hover selector="css-selector"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) hover --selector "$(selector)"

browser-mousedown:  ## browser: 마우스 down (옵션: selector="..." button="left")
	@$(BROWSER_CTL) mousedown $(if $(selector),--selector "$(selector)",) $(if $(button),--button "$(button)",)

browser-mouseup:  ## browser: 마우스 up (옵션: selector="..." button="left")
	@$(BROWSER_CTL) mouseup $(if $(selector),--selector "$(selector)",) $(if $(button),--button "$(button)",)

browser-scroll:  ## browser: 스크롤 (사용법: dy=-800 [dx=0])
	@if [[ -z "$(dy)" && -z "$(dx)" ]]; then \
		echo '사용법: make browser-scroll dy=-800 [dx=0]'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) scroll $(if $(dx),--delta-x "$(dx)",) $(if $(dy),--delta-y "$(dy)",)

browser-wait:  ## browser: selector 출현 대기 (사용법: selector="...")
	@if [[ -z "$(selector)" ]]; then \
		echo '사용법: make browser-wait selector="css-selector"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) wait_for --selector "$(selector)"

browser-text:  ## browser: selector 의 textContent 추출
	@if [[ -z "$(selector)" ]]; then \
		echo '사용법: make browser-text selector="css-selector"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) text --selector "$(selector)"

browser-html:  ## browser: selector 의 outerHTML 추출
	@if [[ -z "$(selector)" ]]; then \
		echo '사용법: make browser-html selector="css-selector"'; \
		exit 1; \
	fi
	@$(BROWSER_CTL) html --selector "$(selector)"

browser-shot:  ## browser: 스크린샷 저장 (옵션: path="..." full=1)
	@$(BROWSER_CTL) screenshot $(if $(path),--path "$(path)",) $(if $(full),--full-page,)

browser-close:  ## browser: 현재 세션 닫기
	@$(BROWSER_CTL) close

# =============================================================================
# Cleanup — 정리
# =============================================================================

clean:  ## cleanup: down -v (볼륨 포함 정리)
	@$(DC_QUIET) down -v

clear:  ## cleanup: down + mysql-data 디렉토리 초기화 (DESTRUCTIVE)
	@$(DC_QUIET) down
	@rm -rf $(MYSQL_DATA_DIR)
	@mkdir -p $(MYSQL_DATA_DIR)
	@chown -R 999:999 $(MYSQL_DATA_DIR) || true
	@chmod -R 770 $(MYSQL_DATA_DIR) || true
