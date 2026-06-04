FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends locales tzdata default-mysql-client \
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
COPY unit/feature-0002-agent-core/src/scripts /app/scripts
# TASK-0149 (#15): alembic 프레임워크를 이미지에 baking — `make migrate`/`migrate-stamp` 가
# 빌드 이미지(`/app`)에서 동작하도록(이전엔 src/ 밖이라 미포함=프로덕션 미동작). alembic.ini 의
# script_location=%(here)s/alembic → /app/alembic. env.py 는 AGENT_KB_PG_* 만 읽음(앱 모듈 무의존).
COPY unit/feature-0002-agent-core/alembic.ini /app/alembic.ini
COPY unit/feature-0002-agent-core/alembic /app/alembic
COPY unit/feature-0003-agent-web-ui/src /app/web

# TASK-0126 (#5 split-brain): 배포 provenance. 빌드 시 main HEAD SHA 를 각인하여
# /healthz 가 노출 → web·insight-worker 가 동일 commit 으로 빌드됐는지 검증 가능.
# 늦은 위치에 두어 상위 레이어 캐시를 깨지 않음.
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}

ENTRYPOINT ["python", "/app/agent_core.py"]
