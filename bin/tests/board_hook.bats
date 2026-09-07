#!/usr/bin/env bats
# bin/tests/board_hook.bats — agent-board Claude Code 어댑터 (IMPLEMENTATION_BRIEF §2.5, 실 assertion).
# P1 은 Claude 만 (Q-8). Codex/Gemini 는 «platform_unsupported 로 무출력 exit 0» 만 단언한다.
# 출력 계약 정본: DESIGN §10 «플랫폼별 최종 JSON» (2026-09-04 Claude 2.1.227 실측 — watchPaths 는 hookSpecificOutput 안).

# (self-contained — test_helper 불필요: assert_* 미사용, 소비자 트리에서도 단독 실행)

REPO="$(cd "$BATS_TEST_DIRNAME/../.." && pwd -P)"
B="$REPO/bin/board.sh"
H="$REPO/bin/hooks/board-hook.sh"

setup() {
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/xdg"
  W="$BATS_TEST_TMPDIR/wrapper"; mkdir -p "$W/repo"
  printf -- '---\ntemplate_version: v3.52.0\n---\n# AGENTS\n' > "$W/repo/AGENTS.md"
  unset CLAUDE_CODE_SESSION_ID CLAUDE_ENV_FILE AGENT_BOARD_SID AGENT_BOARD_TOKEN AGENT_BOARD_DISABLE BOARD_NOW
  cd "$W/repo"
  bash "$B" init --mode private >/dev/null
  ROOT="$(grep '^root=' "$W/.board-root" | cut -d= -f2)"
  touch "$ROOT/control/TEST_CLOCK"
  SA="$(bash "$B" register --native-id writer-0001 --platform claude --alias writer --work -)"
  SID="claude:$(id -un):hook-sess-1"
}
hook() { printf '%s' "$1" | bash "$H" --platform "${2:-claude}"; }
jq_() { python3 -c "import json,sys;o=json.load(sys.stdin);print($1)"; }
# 부정 단언: bash 의 `set -e` 는 `! cmd` 의 실패를 무시한다(bats-core gotcha — `! grep` 은 항진). grep 이 매치하면 실패하는 wrapper 를 쓴다.
nogrep() { if grep "$@"; then return 1; fi; return 0; }

@test "SessionStart(startup): JSON 1개, hookSpecificOutput{hookEventName,watchPaths=[<root>/seq/SEQ]}, top-level watchPaths 없음, decision/continue 없음" {
  run hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup","model":"claude-fable-5-1"}'
  [ "$status" -eq 0 ]
  echo "$output" | jq_ 'sorted(o.keys())' | grep -qx "\['hookSpecificOutput'\]"
  echo "$output" | jq_ 'o["hookSpecificOutput"]["hookEventName"]' | grep -qx SessionStart
  echo "$output" | jq_ 'o["hookSpecificOutput"]["watchPaths"][0]' | grep -q "/seq/SEQ$"
  [ -f "$ROOT/sessions/$SID.json" ]; [ -f "$ROOT/sessions/$SID.token" ]
  grep -q '"model":"claude-fable-5-1"' "$ROOT/sessions/$SID.json"
}
@test "UserPromptSubmit: 다른 세션 게시물 → hookSpecificOutput.additionalContext (≤4096B), 없으면 0바이트" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1","prompt":"x"}'; [ -z "$output" ]
  bash "$B" post --sid "$SA" --channel public --kind note -m "for hook" >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1","prompt":"x"}'
  echo "$output" | jq_ 'o["hookSpecificOutput"]["hookEventName"]' | grep -qx UserPromptSubmit
  echo "$output" | jq_ 'o["hookSpecificOutput"]["additionalContext"]' | grep -q '"body":"for hook"'
  [ "$(printf '%s' "$output" | wc -c)" -le 4096 ]
  echo "$output" | nogrep -q '"decision"\|"continue"'
}
@test "Stop: hookSpecificOutput(hookEventName=Stop) 비차단; stop_hook_active=true → 0바이트; 같은 prompt_id 2회 → 두 번째 0바이트" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  bash "$B" post --sid "$SA" --channel public --kind note -m s1 >/dev/null
  run hook '{"hook_event_name":"Stop","session_id":"hook-sess-1","stop_hook_active":true}'; [ -z "$output" ]
  run hook '{"hook_event_name":"Stop","session_id":"hook-sess-1","stop_hook_active":false,"prompt_id":"p1"}'
  echo "$output" | jq_ 'o["hookSpecificOutput"]["hookEventName"]' | grep -qx Stop
  bash "$B" post --sid "$SA" --channel public --kind note -m s2 >/dev/null
  run hook '{"hook_event_name":"Stop","session_id":"hook-sess-1","prompt_id":"p1"}'; [ -z "$output" ]
}
@test "FileChanged: file_path==<root>/seq/SEQ ∧ event∈{change,add} ∧ active → {systemMessage} 만 + PENDING; 위조 경로·unlink·done 세션 → 0바이트·PENDING 없음" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  run hook "{\"hook_event_name\":\"FileChanged\",\"session_id\":\"hook-sess-1\",\"file_path\":\"$ROOT/seq/SEQ\",\"event\":\"change\"}"
  [ "$output" = '{"systemMessage":"agent-board: 새 게시물"}' ]; [ -f "$ROOT/cursors/$SID/PENDING" ]
  rm "$ROOT/cursors/$SID/PENDING"
  run hook "{\"hook_event_name\":\"FileChanged\",\"session_id\":\"hook-sess-1\",\"file_path\":\"$ROOT/seq/SEQ\",\"event\":\"add\"}"; [ -n "$output" ]; rm "$ROOT/cursors/$SID/PENDING"
  run hook '{"hook_event_name":"FileChanged","session_id":"hook-sess-1","file_path":"/etc/passwd","event":"change"}'; [ -z "$output" ]
  run hook "{\"hook_event_name\":\"FileChanged\",\"session_id\":\"hook-sess-1\",\"file_path\":\"$ROOT/seq/SEQ\",\"event\":\"unlink\"}"; [ -z "$output" ]
  [ ! -e "$ROOT/cursors/$SID/PENDING" ]
  bash "$B" done --sid "$SID" >/dev/null
  run hook "{\"hook_event_name\":\"FileChanged\",\"session_id\":\"hook-sess-1\",\"file_path\":\"$ROOT/seq/SEQ\",\"event\":\"change\"}"; [ -z "$output" ]
}
@test "PENDING 이 있으면 다음 deliver 가 SEQ 게이트를 건너뛰고 소비한다" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  bash "$B" post --sid "$SA" --channel public --kind note -m p >/dev/null
  hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1"}' >/dev/null   # seq_last 갱신
  hook "{\"hook_event_name\":\"FileChanged\",\"session_id\":\"hook-sess-1\",\"file_path\":\"$ROOT/seq/SEQ\",\"event\":\"change\"}" >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1"}'; [ ! -e "$ROOT/cursors/$SID/PENDING" ]
}
@test "SessionEnd: reason=clear → suspended (SessionStart resume 로 복귀); logout/prompt_input_exit/other/미지값 → ended; 항상 exit 0" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  run hook '{"hook_event_name":"SessionEnd","session_id":"hook-sess-1","reason":"clear"}'; [ "$status" -eq 0 ]; [ -z "$output" ]
  grep -q '"state":"suspended"' "$ROOT/sessions/$SID.json"
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"resume"}' >/dev/null; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"
  for r in logout prompt_input_exit other something_new; do
    S2="claude:$(id -un):end-$r"; hook "{\"hook_event_name\":\"SessionStart\",\"session_id\":\"end-$r\",\"source\":\"startup\"}" >/dev/null
    run hook "{\"hook_event_name\":\"SessionEnd\",\"session_id\":\"end-$r\",\"reason\":\"$r\"}"; [ "$status" -eq 0 ]
    grep -q '"state":"ended"' "$ROOT/sessions/$S2.json"
  done
}
@test "ended tombstone: 같은 session_id 로 SessionStart → 재등록 거부, 최소 JSON(watchPaths 만) 출력" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  hook '{"hook_event_name":"SessionEnd","session_id":"hook-sess-1","reason":"logout"}' >/dev/null
  run hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}'
  echo "$output" | jq_ '"additionalContext" in o["hookSpecificOutput"]' | grep -qx False
  echo "$output" | jq_ 'len(o["hookSpecificOutput"]["watchPaths"])' | grep -qx 1
  grep -q '"state":"ended"' "$ROOT/sessions/$SID.json"
}
@test "SessionStart(compact) → on_compact 재주입 (Claude); presence 는 그대로" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  bash "$B" post --sid "$SA" --channel dm --to "$SID" --kind question -m "unread dm" >/dev/null
  run hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"compact"}'
  echo "$output" | jq_ 'o["hookSpecificOutput"]["additionalContext"]' | grep -q '"body":"unread dm"'
  grep -q '"state":"active"' "$ROOT/sessions/$SID.json"
}
@test "done 세션: SessionStart 는 최소 JSON, 그 외 이벤트는 0바이트 (MUST-14)" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  bash "$B" done --sid "$SID" >/dev/null
  for i in 1 2 3; do bash "$B" post --sid "$SA" --channel public --kind note -m "after$i" >/dev/null; done
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1"}'; [ -z "$output" ]
  run hook '{"hook_event_name":"Stop","session_id":"hook-sess-1","prompt_id":"z"}'; [ -z "$output" ]
  before=$(wc -l < "$ROOT/cursors/$SID/usage.jsonl" 2>/dev/null || echo 0)
  run hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"resume"}'
  echo "$output" | jq_ '"additionalContext" in o["hookSpecificOutput"]' | grep -qx False
  # done 뒤에는 usage 레코드가 한 줄도 늘지 않는다 (0바이트 = 계량도 0)
  [ "$(wc -l < "$ROOT/cursors/$SID/usage.jsonl" 2>/dev/null || echo 0)" -eq "$before" ]
  grep -q '"state":"done"' "$ROOT/sessions/$SID.json"       # SessionStart(resume) 가 done 을 active 로 되돌리지 않는다
}
@test "플랫폼 선언: --platform 미선언 → 0바이트 exit 0; codex/gemini → 0바이트 exit 0 + platform_unsupported 로그 (Q-8)" {
  run bash -c "printf '%s' '{\"hook_event_name\":\"UserPromptSubmit\",\"session_id\":\"x1\"}' | bash '$H'"; [ "$status" -eq 0 ]; [ -z "$output" ]
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"c1","model":"gpt"}' codex; [ "$status" -eq 0 ]; [ -z "$output" ]
  run hook '{"hook_event_name":"SessionStart","session_id":"g1","source":"startup"}' gemini; [ "$status" -eq 0 ]; [ "$output" = "{}" ]
  grep -q platform_unsupported "$ROOT/log/$(id -un).jsonl"
}
@test "platform_mismatch: CLAUDE_CODE_SESSION_ID 가 stdin session_id 와 다르면 주입 없이 {} + 로그" {
  CLAUDE_CODE_SESSION_ID=other-session run hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}'
  [ "$output" = "{}" ]; grep -q platform_mismatch "$ROOT/log/$(id -un).jsonl"
}
@test "어떤 입력에도 exit 0: 손상 JSON·빈 stdin·미지 이벤트·PreCompact → 0바이트" {
  for inp in 'not json' '' '{"hook_event_name":"Weird","session_id":"a"}' '{"hook_event_name":"PreCompact","session_id":"hook-sess-1","trigger":"auto"}'; do
    run hook "$inp"; [ "$status" -eq 0 ]; [ -z "$output" ]
  done
}
@test "출력 JSON 에 board.sh·절대경로 문자열 부재 (wrapper 는 명령·경로 없음, watchPaths 제외)" {
  hook '{"hook_event_name":"SessionStart","session_id":"hook-sess-1","source":"startup"}' >/dev/null
  bash "$B" post --sid "$SA" --channel public --kind note -m "plain" >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"hook-sess-1"}'
  c="$(echo "$output" | jq_ 'o["hookSpecificOutput"]["additionalContext"]')"
  echo "$c" | nogrep -q 'board.sh'; echo "$c" | nogrep -qE '(^|[^"])/(root|tmp|home)/'
}
@test "install-hooks 블록: 5 이벤트(SessionStart/UserPromptSubmit/Stop/SessionEnd/FileChanged), FileChanged matcher=SEQ, PostToolUse/PostToolBatch 미등록, command 는 절대경로+--platform claude" {
  W2="$BATS_TEST_TMPDIR/w2"; mkdir -p "$W2/repo/bin/hooks"; cp "$W/repo/AGENTS.md" "$W2/repo/"; cp "$H" "$W2/repo/bin/hooks/"; cd "$W2/repo"
  bash "$B" init --mode private --install-hooks >/dev/null; R2="$(grep '^root=' "$W2/.board-root" | cut -d= -f2)"
  python3 - "$R2/hooks/claude-settings.json" "$W2/repo/bin/hooks/board-hook.sh" <<'PY'
import sys,json,shlex,os; d=json.load(open(sys.argv[1]))["hooks"]
assert sorted(d)==["FileChanged","SessionEnd","SessionStart","Stop","UserPromptSubmit"], sorted(d)
assert d["FileChanged"][0]["matcher"]=="SEQ"
for ev,blocks in d.items():
    cmd=blocks[0]["hooks"][0]["command"]; parts=shlex.split(cmd)
    assert parts[0]=="bash" and os.path.isabs(parts[1]) and parts[1]==os.path.realpath(sys.argv[2]) and parts[2:]==["--platform","claude"], cmd
PY
  [ ! -e "$R2/hooks/codex-hooks.json" ]
}
