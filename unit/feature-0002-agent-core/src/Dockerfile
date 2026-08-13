FROM python:3.11-slim

WORKDIR /app

# feature-0039 (ops-scheduler): postgresql-client 를 PGDG 에서 **서버와 같은 메이저(16)** 로
# 고정 설치한다. Debian trixie 본 저장소는 client-17 만 제공하는데, pg_dump 17 산출물은
# 첫머리에 PG17 전용 GUC `SET transaction_timeout = 0;` 을 넣어 **PG16 서버로 복원 시
# `unrecognized configuration parameter` 로 실패**한다(실측: ON_ERROR_STOP=1 restore rc=3).
# 백업이 복원되지 않으면 백업이 아니므로 메이저를 서버(16.14)에 맞춘다 — 이는 이관 전
# `docker exec <postgres> pg_dump` 가 자연히 갖던 버전 정합을 명시적으로 복원한 것이다.
# mysqldump 는 기존 default-mysql-client(MariaDB 계열)를 그대로 쓴다: MySQL 8.0 대상
# 덤프의 DDL 구간이 서버 내장 mysqldump 산출물과 **바이트 동일**함을 실측 확인했다
# (SHOW CREATE TABLE 패스스루라 서버 문법·콜레이션이 그대로 보존).
RUN apt-get update \
 && apt-get install -y --no-install-recommends locales tzdata default-mysql-client ca-certificates gnupg wget \
 && . /etc/os-release \
 && wget -qO /tmp/pgdg.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && gpg --dearmor -o /usr/share/keyrings/pgdg.gpg /tmp/pgdg.asc \
 && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-16 \
 && apt-get purge -y --auto-remove gnupg wget \
 && rm -f /tmp/pgdg.asc \
 && sed -i 's/^# *ko_KR.UTF-8 UTF-8/ko_KR.UTF-8 UTF-8/' /etc/locale.gen \
 && locale-gen ko_KR.UTF-8 \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul \
    LANG=ko_KR.UTF-8 \
    LANGUAGE=ko_KR:ko \
    LC_ALL=ko_KR.UTF-8 \
    PYTHONIOENCODING=utf-8

COPY unit/feature-0002-agent-core/src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# TASK-0133 (#7): agent_cli.py(216KB) 삭제 — entrypoint/import 0 의 죽은 레거시. live loop 는 agent_core.py.
COPY unit/feature-0002-agent-core/src/agent_core.py ./agent_core.py
COPY unit/feature-0002-agent-core/src/modules /app/modules
# feature-0011 (P5a Step 1): shared/ 공통 패키지를 /app/shared 로 배치 — agent_core·web 양
# 서비스가 `from shared.X` 로 import (모든 서비스가 WORKDIR /app 을 sys.path 에 가짐).
# 회귀 게이트: make test (PYTHONPATH 에 /work=shared 의 부모 추가). 첫 추출: model_catalog.
COPY shared /app/shared
COPY unit/feature-0002-agent-core/src/scripts /app/scripts
# TASK-0149 (#15): alembic 프레임워크를 이미지에 baking — `make migrate`/`migrate-stamp` 가
# 빌드 이미지(`/app`)에서 동작하도록(이전엔 src/ 밖이라 미포함=프로덕션 미동작). alembic.ini 의
# script_location=%(here)s/alembic → /app/alembic. env.py 는 AGENT_KB_PG_* 만 읽음(앱 모듈 무의존).
COPY unit/feature-0002-agent-core/alembic.ini /app/alembic.ini
COPY unit/feature-0002-agent-core/alembic /app/alembic
COPY unit/feature-0003-agent-web-ui/src /app/web
# feature-0041: HTTP/SSE MCP 전송 프로세스(`ext-tool-mcp` 서비스)가 실행하는 스크립트.
# ⚠ 서버측 **보안 모듈은 여기 넣지 않는다** — 그건 /app/web 에 있고 web 이 소비한다.
#   이 디렉터리에는 별도 프로세스로 도는 어댑터만 둔다(2026-08-12 라이브 기동 실패의 교훈:
#   COPY 되지 않는 경로에 서버 코드를 두면 repo 테스트는 통과하고 배포만 죽는다).
COPY unit/feature-0041-external-ai-tool-surface/src/external_tool_mcp_http.py /app/ext_tools/external_tool_mcp_http.py

# ITEM-09 what#3 (AGENTS.md §13.1 v3.35.1 1순위): 정적 자산 ?v= 스탬프 빌드 주입.
# 소스는 고정 placeholder(?v=dev — hand-edit 커밋 금지·병렬 충돌 표면 제거), 빌드가
# static 트리 content-hash 를 계산해 HTML/JS 의 전 ?v= 참조를 일괄 치환한다(멱등).
# deploy-web.sh 가 baked 이미지에 placeholder 잔존 여부를 검증(주입 누락 = 배포 차단).
RUN python3 /app/scripts/inject_asset_stamp.py --root /app/web/static

# TASK-0126 (#5 split-brain): 배포 provenance. 빌드 시 main HEAD SHA 를 각인하여
# /healthz 가 노출 → web·insight-worker 가 동일 commit 으로 빌드됐는지 검증 가능.
# 늦은 위치에 두어 상위 레이어 캐시를 깨지 않음.
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}

ENTRYPOINT ["python", "/app/agent_core.py"]
