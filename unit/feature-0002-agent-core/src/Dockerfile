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
