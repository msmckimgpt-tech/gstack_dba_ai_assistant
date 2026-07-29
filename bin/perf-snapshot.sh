#!/usr/bin/env bash
# feature-0026-perf-observability (M5): 성능 신호 일괄 스냅샷 CLI.
#
# 산재한 성능 신호 — pg_stat_statements(primary) / 답변 E2E(ask_jobs) / LLM task 지연
# (llm_usage) / red-team 지연(redteam_reviews) / duration_breakdown(messages.meta_json) /
# pgbouncer 풀 / MySQL InnoDB 버퍼풀·digest / 그래프 sync churn(cron.log) / web [perf-http]
# / 컨테이너 자원 — 을 1회 실행으로 수집해 `artifacts/perf/<UTC-ts>/` 에 남긴다.
#
# **read-only**: 어떤 서비스 상태도 변경하지 않는다 (DB 는 SELECT/SHOW 만).
# 병목 개선 전/후 비교(before/after)가 1차 용도 — ANCHOR §3 시나리오 참조.
#
# Usage:
#   bin/perf-snapshot.sh              # 스냅샷 수집 + 요약 stdout
#   bin/perf-snapshot.sh --days 3     # SQL 집계 창 변경 (기본 7일)
#
# Exit: 0 성공(부분 실패 섹션은 파일에 내장 기록) / 1 필수 도구 부재
set -uo pipefail

DAYS=7
while [ $# -gt 0 ]; do
  case "$1" in
    --days) DAYS="${2:-7}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
case "$DAYS" in (*[!0-9]*|"") echo "--days 는 양의 정수" >&2; exit 1;; esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${REPO_DIR}/../artifacts/perf/${TS}"
RAW="${OUT_DIR}/raw"
umask 077   # §18.8 sec B3: 스냅샷 산출물(쿼리 텍스트 포함)은 소유자 전용
mkdir -p "$RAW"
chmod 700 "$OUT_DIR"

# docker 호출 (docker 그룹 미소속 환경 대비 sudo 폴백 — FIRST_REQUEST 배포 정책과 동일)
DOCKER="timeout 60 docker"
if ! $DOCKER ps >/dev/null 2>&1; then DOCKER="timeout 60 sudo docker"; fi
if ! $DOCKER ps >/dev/null 2>&1; then echo "docker 접근 불가" >&2; exit 1; fi

P="repo-postgres-1"; R="repo-postgres-replica-1"; M="repo-mysql-1"; B="repo-pgbouncer-1"

psql_p() { $DOCKER exec "$P" psql -U postgres -d agent_kb -X -q "$@" 2>&1; }
psql_r() { $DOCKER exec "$R" psql -U postgres -d agent_kb -X -q "$@" 2>&1; }

section() {  # section <name> <file> — stdout 헤더 + 파일 기록 시작
  echo ""; echo "═══ $1 ═══"
}

run_to() {  # run_to <file> <cmd...> — 출력을 raw 파일 + stdout 요약 헤드에
  local f="$1"; shift
  "$@" >"$RAW/$f" 2>&1 || true
  head -n "${HEAD_N:-25}" "$RAW/$f"
}

{
echo "# perf-snapshot ${TS} (window: ${DAYS}d)"
echo "# host: $(hostname) / cores: $(nproc) / $(free -h | awk 'NR==2{print "mem used "$3" avail "$7}')"

section "1. 컨테이너 자원 (docker stats 1-shot)"
run_to containers.txt $DOCKER stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

section "2. 답변 E2E (ask_jobs, ${DAYS}d) — 큐 대기 / 실행 p50·p95"
run_to ask_e2e.txt psql_p -c "
SELECT count(*) AS jobs,
       round(avg(extract(epoch FROM started_at-created_at))::numeric,2)  AS q_wait_avg_s,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM started_at-created_at)))::numeric,1) AS q_wait_p95_s,
       round(avg(extract(epoch FROM finished_at-started_at))::numeric,1) AS run_avg_s,
       round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY extract(epoch FROM finished_at-started_at)))::numeric,1) AS run_p50_s,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM finished_at-started_at)))::numeric,1) AS run_p95_s
FROM agent_runtime.ask_jobs
WHERE created_at > now()-interval '${DAYS} days' AND finished_at IS NOT NULL"

section "3. 답변 duration_breakdown 집계 (messages.meta_json, ${DAYS}d)"
run_to breakdown.txt psql_p -c "
WITH b AS (
  SELECT (meta_json->'duration_breakdown'->>'total_ms')::float     AS total_ms,
         (meta_json->'duration_breakdown'->>'queued_ms')::float    AS queued_ms,
         (meta_json->'duration_breakdown'->>'init_ms')::float      AS init_ms,
         (meta_json->'duration_breakdown'->>'inference_ms')::float AS inference_ms,
         (meta_json->'duration_breakdown'->>'redteam_ms')::float   AS redteam_ms
  FROM agent_runtime.messages
  WHERE role='assistant' AND meta_json ? 'duration_breakdown'
    AND created_at > now()-interval '${DAYS} days')
SELECT count(*) AS answers,
       round(avg(total_ms)::numeric)     AS total_avg_ms,
       round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY total_ms))::numeric) AS total_p50,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms))::numeric) AS total_p95,
       round(avg(queued_ms)::numeric)    AS queued_avg,
       round(avg(init_ms)::numeric)      AS init_avg,
       round(avg(inference_ms)::numeric) AS inference_avg,
       round(avg(redteam_ms)::numeric)   AS redteam_avg
FROM b"

section "3b. init_detail 단계별 평균 (신규 계측, ${DAYS}d)"
run_to init_detail.txt psql_p -c "
SELECT d.key AS stage, count(*) AS n, round(avg(d.value::float)::numeric,1) AS avg_ms,
       round(max(d.value::float)::numeric,1) AS max_ms
FROM agent_runtime.messages m,
     jsonb_each_text(m.meta_json->'duration_breakdown'->'init_detail') d
WHERE m.role='assistant' AND m.meta_json->'duration_breakdown' ? 'init_detail'
  AND m.created_at > now()-interval '${DAYS} days'
GROUP BY d.key ORDER BY avg_ms DESC"

section "3b-2. inference_detail — inference_ms 내부 분해 (feature-0031, ${DAYS}d)"
# other_ms 가 핵심: inference 는 답변 지연의 최대 구간인데 LLM/도구를 빼고도 설명 안 되는
# 잔차가 7일 평균 33.0초(23%)였다. 그 잔차가 어디로 가는지가 다음 개선 대상을 정한다.
run_to inference_detail.txt psql_p -c "
SELECT count(*) AS answers,
       round(avg((d->>'llm_ms')::float)::numeric)   AS llm_ms,
       round(avg((d->>'llm_calls')::float)::numeric,1) AS llm_calls,
       round(avg((d->>'tool_ms')::float)::numeric)  AS tool_ms,
       round(avg((d->>'tool_calls')::float)::numeric,1) AS tool_calls,
       round(avg((d->>'other_ms')::float)::numeric) AS other_ms,
       round(100.0*avg((d->>'other_ms')::float)::numeric
             / NULLIF(avg((m.meta_json->'duration_breakdown'->>'inference_ms')::float)::numeric,0)) AS other_pct,
       count(*) FILTER (WHERE (d->>'residual_clamped')::boolean) AS clamped
FROM agent_runtime.messages m,
     LATERAL (SELECT m.meta_json->'duration_breakdown'->'inference_detail') AS x(d)
WHERE m.role='assistant' AND m.meta_json->'duration_breakdown' ? 'inference_detail'
  AND m.created_at > now()-interval '${DAYS} days'"

section "3b-3. inference 도구별 소요 (답변당 상위 6 도구만 집계 — §3b-2 의 tool_ms 합계와 일치하지 않을 수 있음, ${DAYS}d)"
# avg_ms_per_call 은 반드시 sum(ms)/sum(n) — avg(ms/n) 은 '답변별 평균의 평균'이라
# 느린 호출 1건짜리 답변이 빠른 100건짜리 답변을 압도한다(§18.8 패널 MAJOR-4: 라이브
# 합성 데이터로 228ms 를 9,025ms 로 40배 과대보고). 이 컬럼이 다음 최적화 대상을 고르는 값이다.
run_to inference_tools.txt psql_p -c "
SELECT t.key AS tool, sum((t.value->>'n')::int) AS calls,
       round(sum((t.value->>'ms')::float)::numeric) AS total_ms,
       round(sum((t.value->>'ms')::float)::numeric
             / NULLIF(sum((t.value->>'n')::int),0)) AS avg_ms_per_call
FROM agent_runtime.messages m,
     jsonb_each(m.meta_json->'duration_breakdown'->'inference_detail'->'tool_top') t
WHERE m.role='assistant' AND m.meta_json->'duration_breakdown'->'inference_detail' ? 'tool_top'
  AND m.created_at > now()-interval '${DAYS} days'
GROUP BY t.key ORDER BY total_ms DESC"

section "3b-4. inference llm_ms 교차검증 (llm_usage 대조 — 실패 호출·누락 식별, ${DAYS}d)"
# llm_ms 는 성공한 provider 왕복만 담는다. 실패한 LLM 호출의 시간은 other_ms 로 흘러가
# '오케스트레이션이 느리다'로 오독될 수 있다 — llm_calls 와 llm_usage 건수를 대조해 구분한다.
run_to inference_llm_xcheck.txt psql_p -c "
WITH a AS (
  SELECT m.meta_json->>'run_id' AS rid,
         (m.meta_json->'duration_breakdown'->'inference_detail'->>'llm_ms')::float AS acc_ms,
         (m.meta_json->'duration_breakdown'->'inference_detail'->>'llm_calls')::int AS acc_n
  FROM agent_runtime.messages m
  WHERE m.role='assistant' AND m.meta_json->'duration_breakdown' ? 'inference_detail'
    AND m.created_at > now()-interval '${DAYS} days'),
u AS (SELECT run_id, count(*) n, sum(latency_ms) ms FROM agent_runtime.llm_usage
      WHERE task='agent' AND created_at > now()-interval '${DAYS} days' GROUP BY 1)
SELECT count(*) AS answers,
       round(avg(a.acc_ms)::numeric) AS acc_llm_ms, round(avg(a.acc_n)::numeric,1) AS acc_calls,
       round(avg(COALESCE(u.ms,0))::numeric) AS usage_llm_ms, round(avg(COALESCE(u.n,0))::numeric,1) AS usage_calls,
       count(*) FILTER (WHERE a.acc_n <> COALESCE(u.n,0)) AS call_count_mismatch
FROM a LEFT JOIN u ON u.run_id = a.rid"

section "3c. post-answer 큐레이션 (KV last_post_answer_ms — feature-0027 이후 terminal *후* 실행, 체감 지연 아님)"
run_to post_answer.txt psql_p -c "
SELECT count(*) AS convs, round(avg(value::float)::numeric) AS avg_ms,
       round(max(value::float)::numeric) AS max_ms
FROM agent_runtime.kv WHERE key='last_post_answer_ms'
  AND updated_at > now()-interval '${DAYS} days'"

section "4. LLM task 별 지연 (llm_usage, ${DAYS}d) — 워커 포함 (M2 백필 후 전 task 채워짐)"
run_to llm_tasks.txt psql_p -c "
SELECT coalesce(task,'?') AS task, count(*) AS calls,
       count(latency_ms) AS measured,
       round(avg(latency_ms)) AS avg_ms,
       round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms))::numeric) AS p50,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))::numeric) AS p95,
       sum(total_tokens) AS tokens
FROM agent_runtime.llm_usage
WHERE created_at > now()-interval '${DAYS} days'
GROUP BY 1 ORDER BY calls DESC LIMIT 20"

section "5. red-team 리뷰 (${DAYS}d)"
run_to redteam.txt psql_p -c "
SELECT count(*) AS reviews, count(*) FILTER (WHERE verdict='BLOCK') AS blocks,
       count(*) FILTER (WHERE revision_applied) AS revised,
       count(*) FILTER (WHERE rederive_applied) AS rederived,
       round(avg(latency_ms)) AS avg_ms,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))::numeric) AS p95_ms
FROM agent_runtime.redteam_reviews WHERE created_at > now()-interval '${DAYS} days'"

section "6. PG primary pg_stat_statements TOP 15 (total_exec_time)"
run_to pg_stat_primary.txt psql_p -c "
SELECT round(total_exec_time::numeric/1000,1) AS total_s, calls,
       round(mean_exec_time::numeric,1) AS mean_ms, rows,
       left(regexp_replace(regexp_replace(query,'''[^'']*''','''?''','g'),'\s+',' ','g'),110) AS q
FROM pg_stat_statements
WHERE query !~* '(password|secret|identified by)'
ORDER BY total_exec_time DESC LIMIT 15"
psql_p -tAc "SELECT 'stats_since: '||stats_reset FROM pg_stat_statements_info" 2>/dev/null || true

section "6b. PG replica pg_stat_statements TOP 10 (RO 핫패스 — preload 필요)"
HEAD_N=14 run_to pg_stat_replica.txt psql_r -c "
SELECT round(total_exec_time::numeric/1000,1) AS total_s, calls,
       round(mean_exec_time::numeric,1) AS mean_ms,
       left(regexp_replace(regexp_replace(query,'''[^'']*''','''?''','g'),'\s+',' ','g'),100) AS q
FROM pg_stat_statements
WHERE query !~* '(password|secret|identified by)'
ORDER BY total_exec_time DESC LIMIT 10"

section "6c. 복제 지연 (pg_stat_replication)"
run_to replication.txt psql_p -c "
SELECT application_name, state, sync_state,
       write_lag, flush_lag, replay_lag FROM pg_stat_replication"

section "7. pgbouncer 풀 (SHOW POOLS) — §82 풀 소진 재발 감시"
PGB_PW="$(sed -n 's/^AGENT_KB_PG_PASSWORD=//p' "${REPO_DIR}/.env.postgres" 2>/dev/null | tail -1)"
PGB_USER="$(sed -n 's/^AGENT_KB_PG_USER=//p' "${REPO_DIR}/.env" 2>/dev/null | tail -1)"
PGB_USER="${PGB_USER:-agent_kb_rw}"
if [ -n "$PGB_PW" ]; then
  # 비밀번호는 argv 가 아닌 stdin 으로 전달 — host /proc/<pid>/cmdline 노출 차단 (§18.8 C-3)
  printf '%s\n' "$PGB_PW" | $DOCKER exec -i "$B" sh -c \
    'read -r PW; PGPASSWORD="$PW" psql -h 127.0.0.1 -p 5432 -U "'"$PGB_USER"'" pgbouncer -c "SHOW POOLS" -c "SHOW STATS"' \
    >"$RAW/pgbouncer.txt" 2>&1 || true
  head -20 "$RAW/pgbouncer.txt"
else
  echo "(skip: .env.postgres 의 AGENT_KB_PG_PASSWORD 미독취)" | tee "$RAW/pgbouncer.txt"
fi

section "8. MySQL — 버퍼풀 히트율·스레드·digest TOP (performance_schema, ADR-0020 digest-first)"
$DOCKER exec "$M" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "
SHOW GLOBAL VARIABLES LIKE \"innodb_buffer_pool_size\";
SHOW GLOBAL STATUS WHERE Variable_name IN (\"Innodb_buffer_pool_read_requests\",\"Innodb_buffer_pool_reads\",\"Threads_connected\",\"Threads_running\",\"Slow_queries\",\"Questions\");
SELECT LEFT(digest_text,90) AS q, count_star, ROUND(avg_timer_wait/1e9,1) AS avg_ms, ROUND(sum_timer_wait/1e12,1) AS total_s
FROM performance_schema.events_statements_summary_by_digest
ORDER BY sum_timer_wait DESC LIMIT 12;"' >"$RAW/mysql.txt" 2>&1 || true
head -30 "$RAW/mysql.txt"

section "9. 그래프 sync churn (cron.log 최근 12회 — duration_ms 는 M4 배포 후 포함)"
tail -24 "${REPO_DIR}/../artifacts/metadata-graph/cron.log" 2>/dev/null \
  | grep -o '{.*}' | tail -12 | tee "$RAW/graph_sync.txt" \
  | python3 -c "
import sys, json
tot = {'relationships':0,'relationships_deleted':0,'columns':0,'commits':0}
n=0
for ln in sys.stdin:
    try: d=json.loads(ln)
    except Exception: continue
    n+=1
    for k in tot: tot[k]+=int(d.get(k,0) or 0)
    if 'duration_ms' in d: tot.setdefault('duration_ms_sum',0); tot['duration_ms_sum']+=d['duration_ms']
print(f'last {n} runs churn:', tot)" || true

section "10. web [perf-http] 최신 스냅샷 (replica 별 — M1 배포 후 주기 flush)"
for W in repo-web-a-1 repo-web-b-1; do
  echo "-- $W"
  $DOCKER logs "$W" 2>&1 | grep '\[perf-http\]' | tail -1 | tee -a "$RAW/web_perf_http.txt" || true
done

section "11. ask 큐 현재 깊이"
run_to queue_depth.txt psql_p -c "
SELECT status, count(*) FROM agent_runtime.ask_jobs
WHERE created_at > now()-interval '1 day' GROUP BY status ORDER BY 2 DESC"

section "12. 워커 공유 자원 예산 (worker-resource-isolation T0 — 워커가 주기 flush 한 파일)"
# 카운터는 워커 프로세스 메모리에 있어 이 CLI 가 직접 읽을 수 없다 — insight cycle 이
# `/shared/perf/worker-resources-<role>.json`(호스트 artifacts/shared/perf)로 원자 flush 한 것을
# 수집한다. peak/limit 과 rejected 가 "상한을 조여도 되는가 / 이미 병목인가" 의 1차 근거다.
# rejected 0 = 게이트 미발동(현행 동등). 파일 부재 = 아직 flush 전(워커 미기동·구 이미지).
_WR_DIR="${REPO_DIR}/../artifacts/shared/perf"
if compgen -G "${_WR_DIR}/worker-resources-*.json" > /dev/null 2>&1; then
  for _f in "${_WR_DIR}"/worker-resources-*.json; do
    echo "-- $(basename "$_f")"
    cp -p "$_f" "$RAW/" 2>/dev/null || true
    python3 - "$_f" <<'PY' 2>/dev/null || cat "$_f"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"  flushed_at={d.get('flushed_at','?')} background_enabled={d.get('background_enabled')}")
for k, v in (d.get("resources") or {}).items():
    print(f"  {k:4s} peak={v.get('peak')}/{v.get('limit')} in_use={v.get('in_use')} "
          f"acquired={v.get('acquired')} rejected={v.get('rejected')} "
          f"reject_ratio={v.get('reject_ratio')} held_ms={v.get('held_ms_total')}")
c = d.get("conns") or {}
if any(c.values()):
    print("  conns " + " ".join(f"{k}={v}" for k, v in c.items() if v))
PY
  done
else
  echo "(no worker-resources-*.json — 워커 flush 전 또는 구 이미지)"
fi

echo ""
echo "# 저장: ${OUT_DIR}"
} | tee "${OUT_DIR}/snapshot.md"

exit 0
