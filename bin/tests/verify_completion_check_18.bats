#!/usr/bin/env bats
#
# verify_completion_check_18.bats — check #18 (secret scan, §16.6 인접)
#   격리 테스트. verify-completion.sh 의 check_18_secret_scan 함수만 source 해
#   분기별 입력 (escape hatch / clean / 토큰패턴 / 파일명 / 대입형 / allowlist 3계층 /
#   post-commit) 에서 기대 exit code 와 메시지 키워드를 검증한다.
#
#   근거: inbox T3-20260817T0735-001 — 완료 게이트 PASS 59초 뒤 실토큰 2건 커밋·push
#   (2026-08-14, mysql_conf_tuner). 게이트에 시크릿 축이 전무했다.
#
#   ⚠️ 이 파일의 가짜 토큰은 전부 인접 문자열 연결("ghp_""AAA…")로 조립한다 —
#   소스 파일 자체가 check #18 의 패턴에 걸리지 않게 하기 위함이다 (hop 이 이
#   파일을 운반하는 커밋이 자기 게이트에 걸리는 자기지시 오탐 방지).
#
# Run:
#   cd repo && bats bin/tests/verify_completion_check_18.bats

setup() {
  TESTDIR=$(mktemp -d /tmp/check18-test-XXXXXX)
  cd "$TESTDIR"
  git init --quiet --initial-branch=main
  git config user.email "test@example.invalid"
  git config user.name "Test Runner"

  mkdir -p bin
  cp "${BATS_TEST_DIRNAME}/../verify-completion.sh" bin/verify-completion.sh
  chmod +x bin/verify-completion.sh

  echo "init" > README.md
  git add README.md
  git commit --quiet -m "init"

  # source 가능한 sibling 사본 (main 호출 라인 제거).
  SOURCEABLE="$TESTDIR/bin/verify-completion-sourceable.sh"
  sed 's|^main "\$@"$|# main "$@" — bats source guard|' bin/verify-completion.sh > "$SOURCEABLE"

  # 가짜 시크릿 — 인접 문자열 연결로 조립 (파일 자기지시 오탐 방지)
  FAKE_GHP="ghp_""AbCdEfGhIjKlMnOpQrStUvWx"                # ghp_ + 24 alnum
  FAKE_AKIA="AKIA""IOSFODNN7EXAMPLB"                        # AKIA + 16 upper/digit
  FAKE_KEY_HDR="-----BEGIN RSA ""PRIVATE KEY-----"
}

teardown() {
  cd /
  rm -rf "$TESTDIR"
}

run_check_18() {   # $1 = mode
  local mode="${1:-pre-commit}"
  run bash -c "
    set +e
    cd '$PWD'
    # shellcheck source=/dev/null
    source '$SOURCEABLE'
    check_18_secret_scan '$mode'
  " 2>&1
}

# -----------------------------------------------------------------------------
# 분기 1: escape hatch
# -----------------------------------------------------------------------------

@test "check_18: GSTACK_SKIP_SECRET_SCAN=1 → SKIP+WARN, exit 0" {
  run bash -c "
    cd '$PWD'
    export GSTACK_SKIP_SECRET_SCAN=1
    source '$SOURCEABLE'
    check_18_secret_scan pre-commit
  " 2>&1
  [ "$status" -eq 0 ]
  [[ "$output" == *"WARN"* ]]
  [[ "$output" == *"escape hatch"* ]]
}

# -----------------------------------------------------------------------------
# 분기 2: clean staged diff → PASS
# -----------------------------------------------------------------------------

@test "check_18: 시크릿 없는 staged 변경 → PASS, exit 0" {
  echo "plain content, nothing secret" > notes.md
  git add notes.md
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
  [[ "$output" == *"CHECK#18 PASS"* ]]
}

# -----------------------------------------------------------------------------
# 분기 3: 축2 — 알려진 토큰 prefix
# -----------------------------------------------------------------------------

@test "check_18: staged 추가 라인에 gh 토큰 패턴 → FAIL, exit 1" {
  printf 'token = %s\n' "$FAKE_GHP" > conf.txt
  git add conf.txt
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
  [[ "$output" == *"내용 축"* ]]
  [[ "$output" == *"conf.txt:1"* ]]
}

@test "check_18: AWS access key id 패턴 → FAIL" {
  printf 'aws line %s here\n' "$FAKE_AKIA" > infra.txt
  git add infra.txt
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

@test "check_18: 개인키 헤더 → FAIL" {
  printf '%s\nMIIfake\n' "$FAKE_KEY_HDR" > key.txt
  git add key.txt
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

# -----------------------------------------------------------------------------
# 분기 4: 축1 — 파일명
# -----------------------------------------------------------------------------

@test "check_18: .gstack/browse.json 이 staged → 내용 무관 FAIL + 파일명 축" {
  mkdir -p .gstack
  echo '{"port": 1234}' > .gstack/browse.json
  git add -f .gstack/browse.json
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
  [[ "$output" == *"browse.json"* ]]
}

@test "check_18: terminal-internal-token 파일명 → FAIL" {
  mkdir -p .gstack
  echo "whatever" > .gstack/terminal-internal-token
  git add -f .gstack/terminal-internal-token
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

@test "check_18: .env 는 FAIL 이지만 .env.example 은 PASS (파일명 allowlist)" {
  printf 'DB_HOST=localhost\n' > .env
  git add -f .env
  run_check_18 pre-commit
  [ "$status" -eq 1 ]

  git reset --quiet
  printf 'DB_HOST=localhost\n' > .env.example
  git add .env.example
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
  [[ "$output" == *"CHECK#18 PASS"* ]]
}

# -----------------------------------------------------------------------------
# 분기 5: 축2 — 대입형 + placeholder 제외
# -----------------------------------------------------------------------------

@test "check_18: 장문 대입값 (password: \"…20+자\") → FAIL + 내용 축" {
  printf 'password: "Zq9rT2wXv8bN4mK7pL0sD3fG"\n' > app.yaml
  git add app.yaml
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"내용 축"* ]]
}

@test "check_18: 한 라인이 토큰+대입 동시 매치 → 라인 단위 1건 계수 (이중 계수 금지)" {
  printf 'token = "%s"\n' "$FAKE_GHP" > dual.txt
  git add dual.txt
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"시크릿 의심 1건"* ]]
}

@test "check_18: placeholder 어휘 포함 대입값 → PASS (오탐 제외)" {
  printf 'api_key = "your_example_placeholder_key_here"\n' > app.conf
  git add app.conf
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
}

# -----------------------------------------------------------------------------
# 분기 6: allowlist — 라인 마커 / example 파일
# -----------------------------------------------------------------------------

@test "check_18: verify-secret-allow 마커 라인 → PASS" {
  printf 'token = %s  # verify-secret-allow: docs 예시\n' "$FAKE_GHP" > docs.md
  git add docs.md
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
  [[ "$output" == *"CHECK#18 PASS"* ]]
}

@test "check_18: *.example 파일이라도 내용 축은 스캔 — 토큰 패턴 → FAIL (개명 우회 차단)" {
  # ux R2 P1: example 면제가 양축이면 «*.example 개명» 이 실토큰 커밋 승인 경로가 된다.
  # 면제는 축1(파일명)에만 — 내용의 토큰 모양 값은 마커로 사유를 남겨야 통과한다.
  printf 'token = %s\n' "$FAKE_GHP" > secrets.conf.example
  git add secrets.conf.example
  run_check_18 pre-commit
  [ "$status" -eq 1 ]

  git reset --quiet
  printf 'token = %s  # verify-secret-allow: 문서 예시용 가짜 토큰\n' "$FAKE_GHP" > secrets.conf.example
  git add secrets.conf.example
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
}

@test "check_18: example 파일명·경로가 대입형 내용 스캔을 면제하지 않는다 (ux R3 P1 회귀)" {
  # placeholder 제외가 «경로:행:내용» 전체에 걸리면 경로의 example 이 내용을 면제한다.
  printf 'DB_PASSWORD="Wq8rT2xXv9bN5mK1pL4sD7fJ"\n' > secrets.conf.example
  git add secrets.conf.example
  run_check_18 pre-commit
  [ "$status" -eq 1 ]

  git reset --quiet
  mkdir -p examples
  printf 'password: "Kx3nV7qRt2wYb8mZc5dFg1hJ"\n' > examples/db.conf
  git add examples/db.conf
  run_check_18 pre-commit
  [ "$status" -eq 1 ]

  git reset --quiet
  mkdir -p .gstack
  printf '{"token": "Vb6nM2kXw9qRt4yZp7cLd3fH01"}\n' > .gstack/browse.json.example
  git add .gstack/browse.json.example
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
}

@test "check_18: 내용의 placeholder 어휘는 example 경로 여부와 무관하게 통과 (오탐 회귀)" {
  printf 'password: "example_placeholder_value_here"\n' > examples/clean.conf 2>/dev/null || { mkdir -p examples; printf 'password: "example_placeholder_value_here"\n' > examples/clean.conf; }
  git add examples/clean.conf
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
}

# -----------------------------------------------------------------------------
# 분기 6b: 회귀 — 패널 리뷰 P1 (quoted-path / JSON 대입형 / 위치 출력)
# -----------------------------------------------------------------------------

@test "check_18: 비ASCII(한글) 디렉토리 하위 .env → FAIL (quotepath fail-open 회귀)" {
  mkdir -p "설정"
  printf 'DB_HOST=localhost\n' > "설정/.env"
  git add -f "설정/.env"
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

@test "check_18: 공백 포함 경로 헤더 파싱 — 위치가 정확히 «my conf.example:1» (탭·따옴표 껍질)" {
  printf 'token = %s\n' "$FAKE_GHP" > "my conf.example"
  git add "my conf.example"
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"my conf.example:1"* ]]
}

@test "check_18: '++ ' 시작 콘텐츠 라인의 헤더 스푸핑 → 이후 토큰도 FAIL (qa R2 P1 회귀)" {
  { printf '++ b/whatever.example\n'; printf 'leak = %s\n' "$FAKE_GHP"; } > doc.md
  git add doc.md
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"doc.md:2"* ]]
}

@test "check_18: .gstack/terminal-<id>/ 하위 파일 → FAIL (축1 하위경로, security R2 P2 회귀)" {
  mkdir -p .gstack/terminal-abc123
  echo '{"port": 9}' > .gstack/terminal-abc123/state.json
  git add -f .gstack/terminal-abc123/state.json
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
}

@test "check_18: 무공백 JSON (\"internal_token\":\"…\") → FAIL + 값 비에코 (security R2 이월)" {
  printf '{"internal_token":"Wq8rT2xXv9bN5mK1pL4sD7fJ"}\n' > svc.json  # verify-secret-allow: bats fixture 가짜 값 (조립 아님 — JSON 무공백 회귀는 원문 필요)
  git add svc.json
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" != *"Wq8rT2xXv9bN5mK1pL4sD7fJ"* ]]
}

@test "check_18: JSON quoted-key 대입형 (\"token\": \"…\") → FAIL + 경로:행 출력" {
  printf '{"token": "Zq9rT2wXv8bN4mK7pL0sD3fG"}\n' > cfg.json  # verify-secret-allow: bats fixture 가짜 값 (JSON quoted-key 회귀는 원문 필요)
  git add cfg.json
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"내용 축"* ]]
  [[ "$output" == *"cfg.json:1"* ]]
  # 값 자체는 에코되지 않아야 한다 (전사에 시크릿 재기록 금지)
  [[ "$output" != *"Zq9rT2wXv8bN4mK7pL0sD3fG"* ]]
}

@test "check_18: .gstack/browse-session.jsonl 파일명 → FAIL (축1 확장 — gitignore 5패턴 동면)" {
  mkdir -p .gstack
  echo "log line" > .gstack/browse-session.jsonl
  git add -f .gstack/browse-session.jsonl
  run_check_18 pre-commit
  [ "$status" -eq 1 ]
}

@test "check_18: .env.production 파일명 → FAIL, .env.sample → PASS" {
  printf 'X=1\n' > .env.production
  git add -f .env.production
  run_check_18 pre-commit
  [ "$status" -eq 1 ]

  git reset --quiet
  printf 'X=1\n' > .env.sample
  git add .env.sample
  run_check_18 pre-commit
  [ "$status" -eq 0 ]
}

# -----------------------------------------------------------------------------
# 분기 7: post-commit 모드
# -----------------------------------------------------------------------------

@test "check_18: post-commit — HEAD 커밋에 토큰 → FAIL" {
  printf 'leak = %s\n' "$FAKE_GHP" > leak.txt
  git add leak.txt
  git commit --quiet -m "leak"
  run_check_18 post-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

@test "check_18: post-commit — 깨끗한 HEAD 커밋 → PASS" {
  echo "clean" > clean.txt
  git add clean.txt
  git commit --quiet -m "clean"
  run_check_18 post-commit
  [ "$status" -eq 0 ]
}

@test "check_18: post-commit — root commit(HEAD^ 부재) 토큰 → git show 폴백으로 FAIL" {
  git checkout --quiet --orphan rootbr
  git rm -rq --cached . 2>/dev/null || true
  printf 'leak = %s\n' "$FAKE_GHP" > rootleak.txt
  git add rootleak.txt
  git commit --quiet -m "root leak"
  run_check_18 post-commit
  [ "$status" -eq 1 ]
  [[ "$output" == *"CHECK#18 FAIL"* ]]
}

@test "check_18: post-commit — root commit(HEAD^ 부재) 클린 → PASS" {
  git checkout --quiet --orphan rootbr2
  git rm -rq --cached . 2>/dev/null || true
  printf 'clean root\n' > rootclean.txt
  git add rootclean.txt
  git commit --quiet -m "root clean"
  run_check_18 post-commit
  [ "$status" -eq 0 ]
}

# -----------------------------------------------------------------------------
# 분기 8: 배선 — main 경로에서 #18 이 실제로 실행되는가 (shared 모드 관통)
# -----------------------------------------------------------------------------

@test "check_18: --shared 관통 시 CHECK#18 라인이 출력에 존재" {
  echo "x" > f.txt
  git add f.txt
  run bash -c "cd '$PWD' && bin/verify-completion.sh --shared" 2>&1
  [[ "$output" == *"CHECK#18"* ]]
}
