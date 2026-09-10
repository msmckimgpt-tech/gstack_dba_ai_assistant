#!/usr/bin/env bash
# product-access-repair.sh — 접근 주체가 0인 «고립 Product» 진단·복구 래퍼 (ITEM-03 / DQA-03).
#
# 본 wrapper 는 web 컨테이너 안에서 `unit/feature-0003-agent-web-ui/scripts/product_access_repair.py`
# 를 실행한다. 그 스크립트는 **이미지에 담기지 않으므로**(Dockerfile 은 feature 의 `src/` 만
# `/app/web` 으로 COPY 한다 — `scripts/` 는 미포함) 파일을 stdin 으로 흘려 `python -` 로 돌린다.
# 이미지 재빌드 없이 현재 배포본에 그대로 쓸 수 있고, 컨테이너에 파일을 남기지 않는다.
#
# 기본은 **dry-run(진단만)**. 복구는 운영자가 제품과 계정을 모두 지정해야 한다 — 대상 계정을
# 자동 선택하지 않는다(인가 데이터 부여, AGENTS §12.3 Critical).
#
# Usage:
#   bin/product-access-repair.sh                                  # 진단 (활성+비활성 전부)
#   bin/product-access-repair.sh --active-only                     # 활성 제품만으로 좁힘
#   bin/product-access-repair.sh --json                            # 기계 판독 진단
#   bin/product-access-repair.sh --apply --product 990002 --grant-account 1 --operator 1
#
# `--operator <계정Id>` 는 **이 복구를 수행하는 사람의 계정**이며 감사행의 actor 로 남는다.
# 생략할 수 없다 — 인가 데이터를 만드는 조작이라 「누가 했는지」가 감사에 답해져야 한다.
#
# 절차 (RUNBOOK: unit/feature-0003-agent-web-ui/docs/RUNBOOK-product-access-repair.md)
#   1) dry-run 으로 고립 제품과 «생성자 후보» 를 확인한다.
#   2) 그 제품을 실제로 써야 하는 계정을 사람이 결정한다.
#   3) --apply 로 그 계정 1개에만 부여하고(--operator 에 수행자 계정을 명시),
#      출력 말미의 사후 검증(잔여 0)을 확인한다.
#
# Exit codes:
#   0 — 진단 성공 또는 복구 성공(사후 검증 잔여 0)
#   1 — 인자 오류 / 대상·수행자 오류 (스크립트가 아무것도 쓰지 않음)
#   2 — 실행 가능한 web 컨테이너 부재 · 구세대 이미지(필요 심볼 부재) · 복구 후에도 고립 잔존
#   3 — docker 접근 불가 (권한)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${REPO_ROOT}/unit/feature-0003-agent-web-ui/scripts/product_access_repair.py"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"

if [ ! -f "$SCRIPT" ]; then
  echo "ERROR: 스크립트를 찾을 수 없습니다: ${SCRIPT}" >&2
  exit 1
fi

# docker 는 소켓 권한이 없을 수 있다(배포 계정이 docker 그룹 비소속) → sudo -n 폴백.
# `sudo -n` 은 비대화 — 암호를 물어야 하는 환경에서는 조용히 실패하지 않고 사유를 남긴다.
DOCKER_CMD=()
if docker ps >/dev/null 2>&1; then
  DOCKER_CMD=(docker)
elif sudo -n docker ps >/dev/null 2>&1; then
  DOCKER_CMD=(sudo -n docker)
else
  echo "ERROR: docker 에 접근할 수 없습니다 (소켓 권한). 'sudo -v' 로 자격을 갱신한 뒤 재시도하세요." >&2
  exit 3
fi

RUNNING="$("${DOCKER_CMD[@]}" ps --format '{{.Names}}')"

# web replica 중 살아 있는 첫 컨테이너. 이 스크립트는 **읽기 위주 + 단일 행 INSERT** 라
# 어느 replica 에서 돌아도 같은 DB(agent_memory)를 본다 — replica 선택은 무관하다.
TARGET=""
for svc in web-a web-b; do
  c="${COMPOSE_PROJECT_NAME}-${svc}-1"
  if grep -qx "$c" <<< "$RUNNING"; then TARGET="$c"; break; fi
done

if [ -z "$TARGET" ]; then
  echo "ERROR: 실행 중인 web 컨테이너가 없습니다 (${COMPOSE_PROJECT_NAME}-web-a-1 / -web-b-1)." >&2
  echo "       먼저 'sudo make web/up' 또는 'bin/deploy-web.sh' 로 기동하세요." >&2
  exit 2
fi

echo "[product-access-repair] exec → ${TARGET} (stdin 으로 스크립트 전달)" >&2
exec "${DOCKER_CMD[@]}" exec -i \
  -e PYTHONPATH=/app/web:/app \
  "$TARGET" \
  python - "$@" < "$SCRIPT"
