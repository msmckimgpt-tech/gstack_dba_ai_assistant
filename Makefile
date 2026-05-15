SHELL := /bin/bash
export PATH := /snap/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$(PATH)

DC := COMPOSE_BAKE=false docker compose
DC_QUIET := $(DC) --ansi=never
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
        up down start stop restart status build ps logs init clean clear \
        sh repl ask mysql out dump session-info dc-build \
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
	@$(DC_QUIET) build agent memory-init insight-worker web browser || true
	@for img in repo-agent repo-memory-init repo-insight-worker repo-web repo-browser; do \
		docker image inspect $$img >/dev/null 2>&1 \
			|| { echo "[make up] 빌드된 이미지 누락: $$img" >&2; exit 1; }; \
	done
	@# 위 build 단계에서 이미 이미지가 만들어졌으므로 후속 `up` 은 `--build` 없이 호출한다.
	@# (`--build` 를 다시 주면 동일 metadata-file race 가 재발한다.)
	@$(DC_QUIET) up -d mysql web browser
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

web: init  ## web: Web UI 기동 (ENABLE_WEB_TLS=1 또는 ENABLE_WEB_TLS_PROXY=1 자동 처리)
	@if [ "$(ENABLE_WEB_TLS)" = "1" ]; then $(MAKE) -s web-tls-cert; fi
	@$(MAKE) check-llm-network
	@$(MAKE) -s dc-build SERVICE=web
	@$(DC_QUIET) up -d --no-build web
	@if [ "$(ENABLE_WEB_TLS)" = "1" ]; then \
		echo "Web UI (HTTPS): https://localhost:$(WEB_PORT)"; \
		if [ -n "$(WEB_LAN_IP)" ]; then echo "LAN 접속: https://$(WEB_LAN_IP):$(WEB_PORT)"; fi; \
	else \
		echo "Web UI: http://localhost:$(WEB_PORT)"; \
	fi
	@if [ "$(ENABLE_WEB_TLS_PROXY)" = "1" ]; then \
		$(MAKE) -s web-tls-cert; \
		mkdir -p $(CADDY_DATA_DIR) $(CADDY_CONFIG_DIR); \
		$(DC_QUIET) up -d caddy; \
		echo "TLS Proxy: https://$(WEB_PUBLIC_HOST)"; \
	fi

web-down:  ## web: Web UI + caddy 정지
	@$(DC_QUIET) stop caddy 2>/dev/null || true
	@$(DC_QUIET) stop web || true

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

web-tls-up: init web-tls-cert  ## web: web + caddy 를 TLS 모드로 기동
	@mkdir -p $(CADDY_DATA_DIR) $(CADDY_CONFIG_DIR)
	@$(MAKE) check-llm-network
	@$(DC_QUIET) up -d --build web
	@$(DC_QUIET) up -d caddy
	@echo "TLS Web UI: https://$(WEB_PUBLIC_HOST)"
	@if [ -n "$(WEB_LAN_IP)" ]; then echo "LAN 접속: https://$(WEB_LAN_IP)"; fi

web-tls-down:  ## web: caddy 만 정지
	@$(DC_QUIET) stop caddy || true

web-tls-status:  ## web: web + caddy 컨테이너 상태 표시
	@$(DC_QUIET) ps web caddy

web-tls-logs:  ## web: caddy 로그 follow
	@$(DC_QUIET) logs -f --tail=200 caddy

# =============================================================================
# Insight worker
# =============================================================================

insight-up:  ## insight: insight-worker 기동
	@$(MAKE) check-llm-network
	@$(DC_QUIET) up -d --build insight-worker

insight-down:  ## insight: insight-worker 정지
	@$(DC_QUIET) stop insight-worker || true

insight-status:  ## insight: insight-worker 컨테이너 상태 표시
	@$(DC_QUIET) ps insight-worker

insight-logs:  ## insight: insight-worker 로그 follow
	@$(DC_QUIET) logs -f --tail=200 insight-worker

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
	@$(DC_QUIET) up -d --build browser
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
