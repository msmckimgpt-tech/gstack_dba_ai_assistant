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

COPY unit/feature-0002-agent-core/src/agent_cli.py ./agent_cli.py
COPY unit/feature-0002-agent-core/src/agent_core.py ./agent_core.py
COPY unit/feature-0002-agent-core/src/modules /app/modules
COPY unit/feature-0002-agent-core/src/scripts /app/scripts
COPY unit/feature-0003-agent-web-ui/src /app/web

# TASK-0126 (#5 split-brain): 배포 provenance. 빌드 시 main HEAD SHA 를 각인하여
# /healthz 가 노출 → web·insight-worker 가 동일 commit 으로 빌드됐는지 검증 가능.
# 늦은 위치에 두어 상위 레이어 캐시를 깨지 않음.
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}

ENTRYPOINT ["python", "/app/agent_core.py"]
