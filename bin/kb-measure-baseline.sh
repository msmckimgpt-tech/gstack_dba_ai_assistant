#!/usr/bin/env bash
# kb-measure-baseline.sh — M-1 phase 의 KB 5종 정본 사전 baseline 측정 (read-only)
#
# 본 스크립트는 feature-0002-agent-core 의 KB Postgres pgvector 마이그레이션
# multi-cycle plan (TASK.md §2.1) 의 M-1 phase 산출물이다. 후속 M0~M5 phase 의
# 회귀 판정 baseline 을 정량 측정으로 확보한다.
#
# 측정 항목 (M-1 cycle 에서 4/5 + M0 cycle 부터 5/5 — latency mode 추가):
#   --rows    5종 KB 테이블 row count (FactEntries / Texts / RagDocuments / RagObjects / Facts VIEW)
#   --explain 주요 KB query 5건의 EXPLAIN FORMAT=JSON 결과
#   --joins   비-KB ↔ KB cross-table JOIN audit (정적 grep)
#   --rbac    PERMISSION_DEFINITIONS 의 kb.* / memory.* / agent_kb.* 항목 카운트
#   --latency `make ask` 5종 시나리오 latency p50/p99 측정 — N 회 (default 3)
#             COMPOSE_PROJECT_NAME=repo 강제 + docker compose run --rm agent 직접 호출
#             (또는 docker exec ${PROJ}-web-1 의 web-only 경로) — M-1 cycle 의 deferral 보완
#   --all     위 5종 모두 실행 후 단일 JSON artifact 로 저장
#
# --latency runtime cost: ~30s/ask × 5 시나리오 × N 회. default N=3 → 약 7~8 분.
# 외부 LLM API 호출 비용 (text-embedding 아닌 chat completion) 발생 — N=3 시 USD <0.05 추정.
#
# Usage:
#   bin/kb-measure-baseline.sh --all [--out <path>] [--container <name>] [--db <name>] [--password <env-var>] [--latency-n N]
#   bin/kb-measure-baseline.sh --rows
#   bin/kb-measure-baseline.sh --explain
#   bin/kb-measure-baseline.sh --joins
#   bin/kb-measure-baseline.sh --rbac
#   bin/kb-measure-baseline.sh --latency [--latency-n 10]
#
# Defaults:
#   --container repo-mysql-1
#   --db        agent_memory
#   --password  MYSQL_ROOT_PASSWORD  (env var name, value extracted from main worktree .env)
#   --out       artifacts/shared/kb-baseline-$(date -I).json

set -euo pipefail

# Locate repo root (works in main worktree + ai/* worktrees).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Resolve wrapper root: in main worktree REPO_ROOT = <wrapper>/repo,
# in ai/* worktree REPO_ROOT = <wrapper>/.worktrees/<name>. The wrapper root is
# always one level up from a directory that contains the main `repo/` checkout.
WRAPPER_CANDIDATE_A="$(dirname "$REPO_ROOT")"           # main worktree case: this is the wrapper
WRAPPER_CANDIDATE_B="$(dirname "$WRAPPER_CANDIDATE_A")" # ai/* worktree case: dirname dirname
if [ -d "${WRAPPER_CANDIDATE_A}/repo" ] && [ -f "${WRAPPER_CANDIDATE_A}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_A"
elif [ -d "${WRAPPER_CANDIDATE_B}/repo" ] && [ -f "${WRAPPER_CANDIDATE_B}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_B"
else
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_A"
fi
MAIN_REPO_ROOT="${WRAPPER_ROOT}/repo"
if [ ! -f "${REPO_ROOT}/.env" ] && [ -f "${MAIN_REPO_ROOT}/.env" ]; then
  ENV_FILE="${MAIN_REPO_ROOT}/.env"
else
  ENV_FILE="${REPO_ROOT}/.env"
fi
ARTIFACTS_ROOT="${WRAPPER_ROOT}/artifacts"

CONTAINER="repo-mysql-1"
DB="agent_memory"
PASSWORD_VAR="MYSQL_ROOT_PASSWORD"
OUT_PATH="${ARTIFACTS_ROOT}/shared/kb-baseline-$(date -I).json"
MODE=""
LATENCY_N=3  # M0 cycle 의 default — N=10 권장이지만 본 turn 에서는 sample 3 회

while [ $# -gt 0 ]; do
  case "$1" in
    --rows|--explain|--joins|--rbac|--latency|--all)
      MODE="${1#--}"; shift ;;
    --container)  CONTAINER="$2"; shift 2 ;;
    --db)         DB="$2"; shift 2 ;;
    --password)   PASSWORD_VAR="$2"; shift 2 ;;
    --out)        OUT_PATH="$2"; shift 2 ;;
    --latency-n)  LATENCY_N="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,35p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$MODE" ] || { echo "specify one of --rows / --explain / --joins / --rbac / --latency / --all" >&2; exit 2; }
[ -f "$ENV_FILE" ] || { echo "missing .env at $ENV_FILE" >&2; exit 1; }

PWD_VALUE="$(grep -E "^${PASSWORD_VAR}=" "$ENV_FILE" | cut -d= -f2-)"
[ -n "$PWD_VALUE" ] || { echo "missing ${PASSWORD_VAR} in $ENV_FILE" >&2; exit 1; }

# M0 cycle: COMPOSE_PROJECT_NAME 강제 — main worktree 의 repo 프로젝트와 동일
# 컨테이너 세트를 참조하여 본 ai/* worktree 안에서 호출되어도 port 충돌 없음.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"

docker_exec_mysql() {
  local sql="$1"
  docker exec -i "$CONTAINER" mysql -uroot -p"$PWD_VALUE" --skip-column-names -B -e "$sql" "$DB" 2>/dev/null
}

docker_exec_mysql_explain() {
  local sql="$1"
  # Wrap with fallback so a single bad query does not abort the whole run.
  local out
  out=$(docker exec -i "$CONTAINER" mysql -uroot -p"$PWD_VALUE" --skip-column-names --raw -B -e "EXPLAIN FORMAT=JSON ${sql}" "$DB" 2>&1 || true)
  # Drop the "Using a password" warning line so output is pure JSON.
  out=$(printf '%s' "$out" | grep -v '^mysql: \[Warning\]' || true)
  if printf '%s' "$out" | grep -q '^ERROR '; then
    # On error, return a JSON object describing the failure (keeps outer JSON valid).
    printf '{"error": %s}' "$(printf '%s' "$out" | head -c 300 | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '"unknown"')"
  else
    printf '%s' "$out"
  fi
}

# ----- Measurement functions ----------------------------------------------

measure_rows() {
  local fact_entries texts rag_docs rag_objects facts_view facts_view_is_view
  fact_entries=$(docker_exec_mysql "SELECT COUNT(*) FROM AgentMemoryFactEntries;" | tr -d '[:space:]')
  texts=$(docker_exec_mysql "SELECT COUNT(*) FROM AgentMemoryTexts;" | tr -d '[:space:]')
  rag_docs=$(docker_exec_mysql "SELECT COUNT(*) FROM AgentMemoryRagDocuments;" | tr -d '[:space:]')
  rag_objects=$(docker_exec_mysql "SELECT COUNT(*) FROM AgentMemoryRagObjects;" | tr -d '[:space:]')
  facts_view=$(docker_exec_mysql "SELECT COUNT(*) FROM AgentMemoryFacts;" | tr -d '[:space:]')
  facts_view_is_view=$(docker_exec_mysql "SELECT TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA='${DB}' AND TABLE_NAME='AgentMemoryFacts';" | tr -d '[:space:]')

  printf '"rows": {\n'
  printf '  "AgentMemoryFactEntries": %s,\n' "${fact_entries:-null}"
  printf '  "AgentMemoryTexts": %s,\n' "${texts:-null}"
  printf '  "AgentMemoryRagDocuments": %s,\n' "${rag_docs:-null}"
  printf '  "AgentMemoryRagObjects": %s,\n' "${rag_objects:-null}"
  printf '  "AgentMemoryFacts_view_count": %s,\n' "${facts_view:-null}"
  printf '  "AgentMemoryFacts_object_type": "%s"\n' "${facts_view_is_view}"
  printf '}'
}

measure_explain() {
  # Q1: _load_kb_entries (knowledge.py:761)
  local q1='SELECT e.FactKey, e.ScopeKey, e.Weight, e.SourceType, t.TextContent FROM AgentMemoryFactEntries e LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash WHERE e.ConversationId IN ('"'"'__global__'"'"') AND e.FactKey LIKE '"'"'schema_insight:%'"'"' ORDER BY e.UpdatedAt DESC LIMIT 50;'
  # Q2: _load_rag_documents_for_request (insight.py:200)
  local q2='SELECT d.FactKey, d.ScopeKey, d.Weight, d.UpdatedAt, t.TextContent FROM AgentMemoryRagDocuments d LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash WHERE d.ConversationId IN ('"'"'__global__'"'"') ORDER BY d.Weight DESC LIMIT 50;'
  # Q3: _load_rag_objects_for_request (insight.py:244) — RagObjects uses ObjectKey/ObjectType (no FactKey column)
  local q3='SELECT o.ObjectKey, o.ObjectType, o.ScopeKey, o.SchemaName, o.TableName, o.ColumnName, o.CategoryDomain, o.CategoryEventType, o.Weight, t.TextContent FROM AgentMemoryRagObjects o LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash WHERE o.ConversationId IN ('"'"'__global__'"'"') ORDER BY o.Weight DESC LIMIT 50;'
  # Q4: _load_existing_table_insight_map
  local q4='SELECT FactKey, TextHash FROM AgentMemoryFactEntries WHERE FactKey LIKE '"'"'table_insight:%'"'"' AND ConversationId = '"'"'__global__'"'"';'
  # Q5: RagObjects category-filtered (D2 routing) — ObjectKey is the primary identifier
  local q5='SELECT o.ObjectKey, o.SchemaName, o.TableName, o.Weight FROM AgentMemoryRagObjects o WHERE o.ConversationId = '"'"'__global__'"'"' AND o.CategoryDomain IS NOT NULL ORDER BY o.UpdatedAt DESC LIMIT 30;'

  printf '"explain": {\n'
  printf '  "Q1_load_kb_entries": '
  docker_exec_mysql_explain "$q1" | tr '\n' ' '
  printf ',\n'
  printf '  "Q2_load_rag_documents_for_request": '
  docker_exec_mysql_explain "$q2" | tr '\n' ' '
  printf ',\n'
  printf '  "Q3_load_rag_objects_for_request": '
  docker_exec_mysql_explain "$q3" | tr '\n' ' '
  printf ',\n'
  printf '  "Q4_load_existing_table_insight_map": '
  docker_exec_mysql_explain "$q4" | tr '\n' ' '
  printf ',\n'
  printf '  "Q5_rag_objects_category_d2": '
  docker_exec_mysql_explain "$q5" | tr '\n' ' '
  printf '\n}'
}

measure_joins() {
  # Audit: any code that JOINs non-KB tables (Conversations / Messages / Steps)
  # with KB tables (FactEntries / Texts / RagDocuments / RagObjects / Facts).
  # Bidirectional grep to catch both orderings.
  local src_root="${REPO_ROOT}/unit/feature-0002-agent-core/src"
  if [ ! -d "$src_root" ]; then
    src_root="${MAIN_REPO_ROOT}/unit/feature-0002-agent-core/src"
  fi

  local kb_names='AgentMemoryFactEntries|AgentMemoryRagDocuments|AgentMemoryRagObjects|AgentMemoryTexts|AgentMemoryFacts'
  local nonkb_names='AgentMemoryConversations|AgentMemoryMessages|AgentMemorySteps'

  # Direction 1: non-KB followed by KB on the same line within ~200 chars (JOIN candidate).
  local d1
  d1=$( { grep -rEn -B0 "(${nonkb_names}).{0,300}(${kb_names})" "$src_root" 2>/dev/null || true; } | { grep -iE 'JOIN|FROM' || true; } | wc -l | tr -d ' ')
  # Direction 2: KB followed by non-KB.
  local d2
  d2=$( { grep -rEn -B0 "(${kb_names}).{0,300}(${nonkb_names})" "$src_root" 2>/dev/null || true; } | { grep -iE 'JOIN|FROM' || true; } | wc -l | tr -d ' ')

  printf '"joins": {\n'
  printf '  "src_root": "%s",\n' "$src_root"
  printf '  "non_kb_to_kb_join_candidates": %s,\n' "${d1:-0}"
  printf '  "kb_to_non_kb_join_candidates": %s,\n' "${d2:-0}"
  printf '  "expected": 0,\n'
  printf '  "note": "비-KB (Conversations/Messages/Steps) 와 KB 5종 간 cross-table JOIN audit. 0 이면 KB Postgres 이전 시 cross-DB JOIN 우려 없음 — outside-voice review Open Q #9 충족."\n'
  printf '}'
}

measure_rbac() {
  local app_py="${MAIN_REPO_ROOT}/unit/feature-0003-agent-web-ui/src/app.py"
  if [ ! -f "$app_py" ]; then
    app_py="${REPO_ROOT}/unit/feature-0003-agent-web-ui/src/app.py"
  fi

  local kb_count memory_count agent_kb_count perm_total
  if [ -f "$app_py" ]; then
    # PERMISSION_DEFINITIONS uses dict-of-dicts: {"code": "<area>.<verb>.<scope>", ...}.
    # Count "code": "<prefix>...." entries for each KB-relevant prefix.
    kb_count=$({ grep -cE '"code":\s*"kb\.' "$app_py" || true; } | head -1)
    memory_count=$({ grep -cE '"code":\s*"memory\.' "$app_py" || true; } | head -1)
    agent_kb_count=$({ grep -cE '"code":\s*"agent_kb\.' "$app_py" || true; } | head -1)
    perm_total=$({ grep -cE '"code":\s*"[a-z_]+\.' "$app_py" || true; } | head -1)
    kb_count="${kb_count:-0}"; memory_count="${memory_count:-0}"; agent_kb_count="${agent_kb_count:-0}"; perm_total="${perm_total:-0}"
  else
    kb_count=null; memory_count=null; agent_kb_count=null; perm_total=null
  fi

  printf '"rbac": {\n'
  printf '  "catalog_file": "%s",\n' "$app_py"
  printf '  "kb_permissions": %s,\n' "${kb_count:-0}"
  printf '  "memory_permissions": %s,\n' "${memory_count:-0}"
  printf '  "agent_kb_permissions": %s,\n' "${agent_kb_count:-0}"
  printf '  "permission_definitions_total_approx": %s,\n' "${perm_total:-0}"
  printf '  "note": "현재 PERMISSION_DEFINITIONS 에 kb.* / memory.* / agent_kb.* 항목 카운트. 0 이면 KB 접근이 RBAC catalog 외부 (connection-level) — Postgres 분리 후 agent_kb_rw/ro role 신설 필수. outside-voice review Section D 식별."\n'
  printf '}'
}

measure_latency() {
  # M0 cycle 의 `make ask` latency baseline 측정. M-1 deferral 보완 (Blocker B-2 잔여 1/5).
  #
  # 구조: 5종 시나리오 × LATENCY_N 회 반복. 각 run 마다 docker compose -p repo run --rm
  # agent "<question>" 시간 측정 (bash time builtin). 결과를 JSON 배열로 출력.
  #
  # M0 cycle 의 산출은 measurement_ready 상태 — 본 함수의 implementation 자체. 실 측정
  # 실행은 사용자가 별 turn 에서 docker 환경 (postgres 컨테이너 가동 + agent_kb DB
  # 존재 + LLM API key 유효) 확보 후 `bin/kb-measure-baseline.sh --latency --latency-n 10`
  # 호출. 본 함수가 호출되면 실 측정 진행.

  local s1='최근 7일간 가입한 사용자 수를 알려줘'
  local s2='그 중 PaymentMethod 가 카드인 비율은?'
  local s3='최근에 trend 가 어떻게 되고 있어?'
  local s4='users 관련 테이블이 뭐가 있어?'
  local s5='관리자 권한이 있는 사용자 중 마지막 로그인이 7일 이상 지난 사용자는 누구야?'

  local scenarios=("S1:$s1" "S2:$s2" "S3:$s3" "S4:$s4" "S5:$s5")
  local samples_json=""
  local sid label question idx start_ts end_ts dur_ms rc
  local n
  n="$LATENCY_N"

  # docker compose run 사용 — main repo path 의 compose.yml 사용 위해 -f 명시.
  # COMPOSE_PROJECT_NAME=repo 는 이미 export 됨.
  local compose_file="${MAIN_REPO_ROOT}/docker-compose.yml"
  [ -f "$compose_file" ] || compose_file="${REPO_ROOT}/docker-compose.yml"

  for sid in "${scenarios[@]}"; do
    label="${sid%%:*}"
    question="${sid#*:}"
    for idx in $(seq 1 "$n"); do
      start_ts=$(date +%s%3N)
      rc=0
      docker compose -f "$compose_file" -p "$COMPOSE_PROJECT_NAME" \
        run --rm --remove-orphans agent "$question" >/dev/null 2>&1 || rc=$?
      end_ts=$(date +%s%3N)
      dur_ms=$((end_ts - start_ts))
      if [ -n "$samples_json" ]; then samples_json+=", "; fi
      samples_json+=$(printf '{"scenario": "%s", "iter": %d, "duration_ms": %d, "exit_code": %d}' \
        "$label" "$idx" "$dur_ms" "$rc")
    done
  done

  printf '"latency": {\n'
  printf '  "iterations_per_scenario": %d,\n' "$n"
  printf '  "scenarios_catalog": {"S1": "단순", "S2": "follow-up", "S3": "모호", "S4": "메타탐색", "S5": "복구"},\n'
  printf '  "compose_file": "%s",\n' "$compose_file"
  printf '  "compose_project_name": "%s",\n' "$COMPOSE_PROJECT_NAME"
  printf '  "samples": [%s],\n' "$samples_json"
  printf '  "note": "각 sample 의 duration_ms 는 docker compose run --rm agent 의 wall-clock. p50/p99 집계는 후처리 (python -c). M4 cutover gate 의 latency p99 +50%% 임계 baseline."\n'
  printf '}'
}

# ----- Top-level orchestrator ---------------------------------------------

emit_json() {
  local cycle_id="TASK-0017"
  local feature_id="feature-0002-agent-core"
  local now_iso
  now_iso="$(date -Iseconds)"
  local host_kernel
  host_kernel="$(uname -srm)"
  local mysql_version
  mysql_version="$(docker exec "$CONTAINER" mysql -uroot -p"$PWD_VALUE" --skip-column-names -B -e 'SELECT VERSION();' 2>/dev/null | tr -d '[:space:]' || true)"

  mkdir -p "$(dirname "$OUT_PATH")"

  {
    printf '{\n'
    printf '"meta": {\n'
    printf '  "task_cycle": "%s",\n' "$cycle_id"
    printf '  "feature_id": "%s",\n' "$feature_id"
    printf '  "measured_at": "%s",\n' "$now_iso"
    printf '  "host_kernel": "%s",\n' "$host_kernel"
    printf '  "mysql_container": "%s",\n' "$CONTAINER"
    printf '  "mysql_version": "%s",\n' "$mysql_version"
    printf '  "agent_memory_db": "%s",\n' "$DB"
    printf '  "compose_project_name": "%s",\n' "$COMPOSE_PROJECT_NAME"
    printf '  "plan_reference": "unit/feature-0002-agent-core/docs/TASK.md §2.1.3 M0 (TASK-0017) + M-1 (TASK-0016)"\n'
    printf '},\n'

    if [ "$MODE" = "all" ] || [ "$MODE" = "rows" ]; then
      measure_rows; printf ',\n'
    fi
    if [ "$MODE" = "all" ] || [ "$MODE" = "explain" ]; then
      measure_explain; printf ',\n'
    fi
    if [ "$MODE" = "all" ] || [ "$MODE" = "joins" ]; then
      measure_joins; printf ',\n'
    fi
    if [ "$MODE" = "all" ] || [ "$MODE" = "rbac" ]; then
      measure_rbac; printf ',\n'
    fi
    if [ "$MODE" = "all" ] || [ "$MODE" = "latency" ]; then
      measure_latency; printf '\n'
    else
      # latency 측정 안 함 — placeholder 로 deferred 표기.
      printf '"latency": {\n'
      printf '  "status": "not_measured_this_run",\n'
      printf '  "reason": "MODE=%s — 본 호출은 latency mode 미포함. bin/kb-measure-baseline.sh --latency [--latency-n N] 으로 별도 호출.",\n' "$MODE"
      printf '  "scenarios_catalog_ref": "TASK.md §2.1.3 M-1 의 S1~S5 (단순 / follow-up / 모호 / 메타탐색 / 복구)"\n'
      printf '}\n'
    fi

    printf '}\n'
  } > "$OUT_PATH"

  echo "wrote: $OUT_PATH"
}

emit_json
