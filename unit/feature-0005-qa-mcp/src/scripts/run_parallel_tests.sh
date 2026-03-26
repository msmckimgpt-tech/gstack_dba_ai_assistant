#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/shared/logs/test_runs/$TS"
mkdir -p "$OUT"

echo "TEST_RUN=$TS" | tee "$OUT/_meta.txt" >/dev/null

default_make() {
  (cd "$ROOT" && make -s "$@")
}

run_case() {
  local name="$1"
  shift
  local session="${name}_${TS}"
  local i=0
  for q in "$@"; do
    i=$((i+1))
    local log="$OUT/${name}_${i}.log"
    {
      echo "[CASE] $name"
      echo "[SESSION] $session"
      echo "[QUESTION_$i] $q"
      echo "[START] $(date -Iseconds)"
      default_make ask SESSION="$session" q="$q"
      echo "[END] $(date -Iseconds)"
    } >"$log" 2>&1 || {
      echo "[END] $(date -Iseconds)" >>"$log" || true
      echo "[EXIT_CODE] $?" >>"$log" || true
    }
  done
}

run_case case1 \
  "현재 DB 목록 보여줘" \
  "사용 가능한 데이터베이스 목록 출력" \
  "DB 리스트 조회해줘" &

run_case case2 \
  "dbgame 스키마 테이블 목록 보여줘" \
  "dbgame 내 테이블 리스트만 간단히" \
  "dbgame 테이블 이름 전부 출력" &

run_case case3 \
  "dbgame.player에서 계정 생성일이 '2026-01-29 06:00:00'~'2026-02-04 06:00:00' 사이인 계정 수 집계. 컬럼은 자동 추론" \
  "player 테이블의 생성일 컬럼을 찾아 기간 내 생성 계정 수 알려줘 (dbgame)" \
  "dbgame.player 기준 기간 필터 적용한 생성 계정 수만 출력해줘. 필요하면 컬럼 탐색" &

run_case case4 \
  "dbgame.dispatchbattle에서 유저별 파견 총횟수와 기간 일평균(기간: '2026-01-29 06:00:00'~'2026-02-04 06:00:00')" \
  "dispatchbattle 테이블로 AccountId별 총 파견 수/일평균 구해줘. 기간 동일, 컬럼 탐색" \
  "dbgame.dispatchbattle 파견 집계: 유저별 총합, 일별, 일평균. 기간 동일." &

run_case case5 \
  "/shared/query/영웅레벨분포.sql 참고해서 영웅 레벨 10단위 분포(비율)와 평균/최대 레벨을 함께 출력" \
  "shared/query/영웅레벨분포.sql 내용 기반으로 레벨 구간별 비율 + 평균/최대 레벨" \
  "영웅레벨분포.sql 참고해서 HeroIndex별 10레벨 구간 분포도와 평균/최대" &

run_case case6 \
  "SQL 실행: SELECT * FROM dbgame.player LIMIT; (문법 오류면 자동 수정)" \
  "SQL 실행: SELECT * FROM dbgame.player LIMIT ; 자동 수정해서 실행" \
  "SQL 실행: SELECT * FROM dbgame.player LIMIT; 결과는 10행만" &

run_case case7 \
  "복원 파일 목록 조회: /shared/mysql-backup 내 .sql 파일" \
  "백업 폴더(/shared/mysql-backup)에서 sql 파일 리스트 보여줘" \
  "mysql-backup 경로의 .sql 파일만 찾아줘" &

run_case case8 \
  "dbgame.player 테이블 컬럼 구조 보여줘" \
  "dbgame.player 컬럼 목록과 타입만 출력" \
  "dbgame.player 샘플 5건과 컬럼 구조 요약" &

wait

SCAN="$OUT/_scan.txt"
: > "$SCAN"

grep_check() {
  local label="$1"
  local pattern="$2"
  if grep -R --line-number -F "$pattern" "$OUT" >/dev/null 2>&1; then
    echo "FOUND:$label:$pattern" >> "$SCAN"
    grep -R --line-number -F "$pattern" "$OUT" | head -n 5 >> "$SCAN"
  else
    echo "OK:$label" >> "$SCAN"
  fi
}

grep_check "internal_log" "MCP 로그"
grep_check "internal_log" "도구 로그"
grep_check "internal_log" "CSV 저장"
grep_check "internal_log" "로컬 도구 단계"
grep_check "internal_log" "MCP 단계"
grep_check "internal_log" "자동 탐색 단계"
grep_check "paths" "/shared/logs/"
grep_check "paths" "/shared/out/"
grep_check "errors" "Traceback"
grep_check "errors" "RuntimeError"
grep_check "errors" "오류:"
grep_check "errors" "Input validation error"
grep_check "prompts" "확인 질문"

echo "SCAN_DONE" >> "$SCAN"

echo "Logs saved under: $OUT"
