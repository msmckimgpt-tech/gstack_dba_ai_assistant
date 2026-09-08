#!/usr/bin/env bats
# bin/tests/board_lifecycle.bats — agent-board 실사용 결함 4건 (META-CYCLE-072, v3.54.1; mysql_ai_delegated_dev 2026-09-07 실측 근거). 실 assertion.
#   ① SessionEnd(reason other/logout) 는 suspended — 같은 session id 의 resume 가 살아남는다; 유산·sweep 종단은 되살아난다; 사람의 end --yes 만 비가역
#   ② $CLAUDE_ENV_FILE 부모 0775 허용(other-writable 만 거부)  ③ SessionStart 를 놓친 세션의 첫 fire 자동 등록  ④ cycle-init 착수 / cycle-finalize 완료·done 자동 이정표
REPO="$(cd "$BATS_TEST_DIRNAME/../.." && pwd -P)"
B="$REPO/bin/board.sh"; H="$REPO/bin/hooks/board-hook.sh"
nogrep() { if grep "$@"; then return 1; fi; return 0; }
setup() {
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/xdg"
  W="$BATS_TEST_TMPDIR/wrapper"; mkdir -p "$W/repo"
  unset CLAUDE_CODE_SESSION_ID CLAUDE_ENV_FILE AGENT_BOARD_SID AGENT_BOARD_TOKEN AGENT_BOARD_DISABLE BOARD_NOW
  ( cd "$W/repo" && git init -q && printf -- '---\ntemplate_version: v3.54.1\n---\n# AGENTS\n' > AGENTS.md && mkdir -p bin/hooks && printf '#!/usr/bin/env bash\nexit 0\n' > bin/hooks/board-hook.sh \
    && git add -A && git -c user.email=t@t -c user.name=t commit -qm init )
  cd "$W/repo"; bash "$B" init --mode private >/dev/null; ROOT="$(grep '^root=' "$W/.board-root" | cut -d= -f2)"; touch "$ROOT/control/TEST_CLOCK"
  SA="$(bash "$B" register --native-id aaaa-1111 --platform claude --alias alpha --work -)"
}
hook() { printf '%s' "$1" | bash "$H" --platform claude; }
ctx() { python3 -c 'import json,sys;o=json.load(sys.stdin);print(o.get("hookSpecificOutput",{}).get("additionalContext",""))'; }

@test "L1 SessionEnd reason other/logout → suspended(ended 아님); SessionStart(resume) 가 active 로 복귀하고 그 뒤 게시물을 수신한다; done 세션은 resume 뒤에도 done 유지" {
  hook '{"hook_event_name":"SessionStart","session_id":"s-0001","source":"startup"}' >/dev/null; SID="claude:$(id -un):s-0001"
  for r in other logout prompt_input_exit; do
    printf '{"session_id":"s-0001","reason":"%s"}' "$r" | bash "$B" end --hook --platform claude --stdin-json -
    grep -q '"state":"suspended"' "$ROOT/sessions/$SID.json"; nogrep -q '"ended_by"' "$ROOT/sessions/$SID.json"
    hook '{"hook_event_name":"SessionStart","session_id":"s-0001","source":"resume"}' >/dev/null; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"
  done
  bash "$B" post --sid "$SA" --channel public --kind note -m "after-resume" >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0001"}'; echo "$output" | ctx | grep -q '"body":"after-resume"'
  nogrep -q tombstone "$ROOT/log/$(id -un).jsonl"
  CLAUDE_CODE_SESSION_ID=s-0001 bash "$B" done >/dev/null; printf '{"session_id":"s-0001","reason":"other"}' | bash "$B" end --hook --platform claude --stdin-json -
  grep -q '"prev_state":"done"' "$ROOT/sessions/$SID.json"; hook '{"hook_event_name":"SessionStart","session_id":"s-0001","source":"resume"}' >/dev/null; grep -q '"state":"done"' "$ROOT/sessions/$SID.json"
}
@test "L2 v3.53.x 유산 tombstone(ended, ended_by 없음) 은 SessionStart(resume) 가 되살린다(legacy_tombstone_resumed); 사람의 end --yes(ended_by=cli) 는 그대로 tombstone" {
  hook '{"hook_event_name":"SessionStart","session_id":"s-0002","source":"startup"}' >/dev/null; SID="claude:$(id -un):s-0002"
  python3 - "$ROOT/sessions/$SID.json" <<'PY'
import sys,json; p=sys.argv[1]; o=json.load(open(p)); o["state"]="ended"; o["ended_at"]="2026-09-07T05:00:00.000Z"; o.pop("ended_by",None); json.dump(o,open(p,"w"))
PY
  run hook '{"hook_event_name":"SessionStart","session_id":"s-0002","source":"resume"}'; [ "$status" -eq 0 ]
  grep -q '"state":"active"' "$ROOT/sessions/$SID.json"; grep -q legacy_tombstone_resumed "$ROOT/log/$(id -un).jsonl"
  bash "$B" end --yes --sid "$SID" --reason logout >/dev/null; grep -q '"ended_by":"cli"' "$ROOT/sessions/$SID.json"
  run hook '{"hook_event_name":"SessionStart","session_id":"s-0002","source":"resume"}'; grep -q '"state":"ended"' "$ROOT/sessions/$SID.json"; grep -q '"session-start","reason":"tombstone"' "$ROOT/log/$(id -un).jsonl"
  bash "$B" post --sid "$SA" --channel public --kind note -m x >/dev/null; run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0002"}'; [ -z "$output" ]
}
@test "L3 stale sweep 은 ended_by=sweep 을 남기지만 비가역이 아니다 — hook 등록 presence 의 pid 는 hook 셸(이미 죽음)이라 liveness 판정이 늘 거짓이므로, resume 가 되살린다" {
  hook '{"hook_event_name":"SessionStart","session_id":"s-0003","source":"startup"}' >/dev/null; SID="claude:$(id -un):s-0003"
  pid=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["pid"])' "$ROOT/sessions/$SID.json"); [ ! -e "/proc/$pid" ]
  python3 - "$ROOT/sessions/$SID.json" <<'PY'
import sys,json; p=sys.argv[1]; o=json.load(open(p)); o["stale_since"]="2026-09-01T00:00:00.000Z"; json.dump(o,open(p,"w"))
PY
  run bash "$B" sessions --all --sweep-ended; [[ "$output" == *"ended(sweep)"* ]]; grep -q '"ended_by":"sweep"' "$ROOT/sessions/$SID.json"
  run hook '{"hook_event_name":"SessionStart","session_id":"s-0003","source":"resume"}'; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"; nogrep -q '"stale_since"' "$ROOT/sessions/$SID.json"
  bash "$B" post --sid "$SA" --channel public --kind note -m after-sweep >/dev/null; run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0003"}'; echo "$output" | ctx | grep -q '"body":"after-sweep"'
}
@test "L4 CLAUDE_ENV_FILE: 부모 0775(자기 소유) → export 2줄 생성 0600; 부모 0777(other-writable) → 거부 (타인 소유 부모 거부는 st_uid 검사 — 비root 로는 재현 불가)" {
  d="$BATS_TEST_TMPDIR/session-env/s-0004"; mkdir -p "$d"; chmod 775 "$d"
  CLAUDE_ENV_FILE="$d/env" hook '{"hook_event_name":"SessionStart","session_id":"s-0004","source":"startup"}' >/dev/null
  [ -f "$d/env" ]; [ "$(stat -c %a "$d/env")" = 600 ]; grep -q '^export AGENT_BOARD_SID=' "$d/env"; grep -q '^export AGENT_BOARD_TOKEN=' "$d/env"
  [ "$(grep -c 'export AGENT_BOARD' "$d/env")" -eq 2 ]
  d2="$BATS_TEST_TMPDIR/session-env/s-0005"; mkdir -p "$d2"; chmod 777 "$d2"
  CLAUDE_ENV_FILE="$d2/env" hook '{"hook_event_name":"SessionStart","session_id":"s-0005","source":"startup"}' >/dev/null
  [ ! -e "$d2/env" ]; grep -q 'parent_not_owned_or_other_writable' "$ROOT/log/$(id -un).jsonl"
  ( . "$d/env"; run bash "$B" post --channel public --kind note -m via-env; [ "$status" -eq 0 ] )
}
@test "L5 SessionStart 를 놓친 세션: 첫 UserPromptSubmit 에서 자동 등록(cursor «지금»), 다음 게시물부터 수신; 유산 ended 도 재시작 없이 첫 fire 에서 부활; env 와 다른 id 는 등록 안 함" {
  bash "$B" post --sid "$SA" --channel public --kind note -m before >/dev/null
  SID="claude:$(id -un):s-0006"; [ ! -e "$ROOT/sessions/$SID.json" ]
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0006"}'; [ "$status" -eq 0 ]; [ -z "$output" ]
  [ -f "$ROOT/sessions/$SID.json" ]; grep -q '"deliver","reason":"auto_registered"' "$ROOT/log/$(id -un).jsonl"
  bash "$B" post --sid "$SA" --channel public --kind note -m after >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0006"}'; echo "$output" | ctx | grep -q '"body":"after"'; nogrep -q '"body":"before"' <<<"$(echo "$output" | ctx)"
  python3 - "$ROOT/sessions/$SID.json" <<'PY'
import sys,json; p=sys.argv[1]; o=json.load(open(p)); o["state"]="ended"; o["ended_at"]="2026-09-07T05:00:00.000Z"; o.pop("ended_by",None); json.dump(o,open(p,"w"))
PY
  bash "$B" post --sid "$SA" --channel public --kind note -m revived >/dev/null
  run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0006"}'; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"; grep -q '"deliver","reason":"legacy_tombstone_resumed"' "$ROOT/log/$(id -un).jsonl"
  CLAUDE_CODE_SESSION_ID=s-0006 run hook '{"hook_event_name":"UserPromptSubmit","session_id":"s-0099"}'; [ -z "$output" ]; [ ! -e "$ROOT/sessions/claude:$(id -un):s-0099.json" ]
}
@test "L6 CLI sid 유추: CLAUDE_CODE_SESSION_ID 가 있으면 --sid 없이 자기 세션으로 동작하고, **미등록이면 자기 세션을 등록한다 — 다른 active 세션으로 폴백하지 않는다**(타 세션 done/명의 도용 차단)" {
  before=$(md5sum "$ROOT/sessions/$SA.json")
  CLAUDE_CODE_SESSION_ID=zzzz-9999 run bash "$B" done; [ "$status" -eq 0 ]
  [ "$(md5sum "$ROOT/sessions/$SA.json")" = "$before" ]; grep -q '"state":"done"' "$ROOT/sessions/claude:$(id -un):zzzz-9999.json"; grep -q harness_auto_registered "$ROOT/log/$(id -un).jsonl"
  CLAUDE_CODE_SESSION_ID=yyyy-8888 run bash "$B" post --channel public --kind note -m mine; [ "$status" -eq 0 ]; grep -q "\"sid\":\"claude:$(id -un):yyyy-8888\"" "$ROOT/channels/public/$output.md"
  AGENT_BOARD_SID="claude:$(id -un):xxxx-7777" run bash "$B" post --channel public --kind note -m x; [ "$status" -eq 3 ]; [[ "$output" == *token_missing* || "$output" == *sid_required* ]]; [ ! -e "$ROOT/sessions/claude:$(id -un):xxxx-7777.json" ]
  hook '{"hook_event_name":"SessionStart","session_id":"s-0007","source":"startup"}' >/dev/null; SID="claude:$(id -un):s-0007"
  SB="$(bash "$B" register --native-id bbbb-2222 --platform claude --work -)"
  run bash "$B" post --channel public --kind note -m nosid; [ "$status" -eq 3 ]; [[ "$output" == *sid_required* ]]
  CLAUDE_CODE_SESSION_ID=s-0007 run bash "$B" post --channel public --kind note -m withenv; [ "$status" -eq 0 ]
  grep -q "\"sid\":\"$SID\"" "$ROOT/channels/public/$output.md"
  CLAUDE_CODE_SESSION_ID=s-0007 run bash "$B" done; [ "$status" -eq 0 ]; grep -q '"state":"done"' "$ROOT/sessions/$SID.json"
  CLAUDE_CODE_SESSION_ID=s-0007 run bash "$B" reactivate; [ "$status" -eq 0 ]; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"
}
@test "L7 milestone: 자기 sid 로 status 게시(등록 없으면 등록), 다른 세션이 수신; 보드/세션 id 없으면 exit 0 + stderr 안내; redaction 도 exit 0" {
  CLAUDE_CODE_SESSION_ID=s-0008 run bash "$B" milestone --kind status --work META-0001 -m "착수 META-0001 — worktree x"; [ "$status" -eq 0 ]; id="$output"
  [ -f "$ROOT/channels/public/$id.md" ]; grep -q '"kind":"status"' "$ROOT/channels/public/$id.md"; grep -q '"work_ref":"META-0001"' "$ROOT/sessions/claude:$(id -un):s-0008.json"
  printf '{}' | bash "$B" deliver --platform claude --event on_prompt --sid "$SA" --stdin-json - 2>/dev/null | ctx | grep -q '착수 META-0001'
  run bash "$B" milestone -m "no session"; [ "$status" -eq 0 ]; [[ "$output" == *"세션 id 불명"* ]]
  CLAUDE_CODE_SESSION_ID=s-0008 run bash "$B" milestone -m "secret AKIAEXAMPLE000000000"; [ "$status" -eq 0 ]; [[ "$output" == *"skip (redaction"* ]]
  W2="$BATS_TEST_TMPDIR/noboard"; mkdir -p "$W2/repo"; cp AGENTS.md "$W2/repo/"; ( cd "$W2/repo" && CLAUDE_CODE_SESSION_ID=s-0008 run bash "$B" milestone -m x; [ "$status" -eq 0 ]; [[ "$output" == *"보드 없음"* ]] )
}
@test "L8 cycle-init 이 착수 status 를 자동 게시한다 (worktree·branch·base 포함) — 다른 세션이 수신" {
  O="$BATS_TEST_TMPDIR/origin.git"; git init -q --bare "$O"; git -C "$W/repo" remote add origin "$O"; DEF="$(git -C "$W/repo" rev-parse --abbrev-ref HEAD)"; git -C "$W/repo" push -q -u origin "$DEF"
  CLAUDE_CODE_SESSION_ID=ci-0001 run bash "$REPO/bin/cycle-init.sh" --feature feature-0042-board --agent t --base "$DEF"; [ "$status" -eq 0 ]
  f="$(ls "$ROOT/channels/public"/*.md | head -1)"; grep -q '"kind":"status"' "$f"; grep -q '착수 feature-0042-board' "$f"; grep -q "base $DEF" "$f"
  grep -q '"work_ref":"feature-0042-board"' "$ROOT/sessions/claude:$(id -un):ci-0001.json"
  printf '{}' | bash "$B" deliver --platform claude --event on_prompt --sid "$SA" --stdin-json - 2>/dev/null | ctx | grep -q '착수 feature-0042-board'
}
@test "L9 cycle-finalize e2e(gh 스텁): 머지 확정 뒤 «완료 PR #N» status 1건 게시 + 정리 뒤 자기 세션 done; 다른 세션이 수신; --dry-run 은 게시 0" {
  git -C "$W/repo" branch -M main
  O="$BATS_TEST_TMPDIR/origin.git"; git init -q --bare "$O"; git -C "$W/repo" remote add origin "$O"; DEF=main; git -C "$W/repo" push -q -u origin "$DEF"
  CLAUDE_CODE_SESSION_ID=fin-0001 bash "$REPO/bin/cycle-init.sh" --feature feature-0043-fin --agent t --base "$DEF" >/dev/null 2>&1
  WT="$W/.worktrees/feature-0043-fin"; [ -d "$WT" ]
  stub="$BATS_TEST_TMPDIR/stub"; mkdir -p "$stub"
  cat > "$stub/gh" <<'GH'
#!/usr/bin/env bash
case "$1 $2" in
  "pr view") printf '{"state":"MERGED","mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","headRefName":"ai/t/feature-0043-fin","title":"feat: fin \"quoted\" title"}\n' ;;
  "pr merge") exit 0 ;;
  *) exit 0 ;;
esac
GH
  chmod +x "$stub/gh"
  n0=$(ls "$ROOT/channels/public" | grep -c '\.md$' || true)
  ( cd "$WT" && PATH="$stub:$PATH" CLAUDE_CODE_SESSION_ID=fin-0001 bash "$REPO/bin/cycle-finalize.sh" --pr 7 --keep-worktree --keep-branch --dry-run >"$BATS_TEST_TMPDIR/dry.log" 2>&1 ) || { cat "$BATS_TEST_TMPDIR/dry.log"; false; }
  n1=$(ls "$ROOT/channels/public" | grep -c '\.md$' || true)
  [ "$n1" -eq "$n0" ] || { echo "dry-run posted: n0=$n0 n1=$n1"; tail -20 "$BATS_TEST_TMPDIR/dry.log"; false; }
  ( cd "$WT" && PATH="$stub:$PATH" CLAUDE_CODE_SESSION_ID=fin-0001 bash "$REPO/bin/cycle-finalize.sh" --pr 7 --keep-worktree --keep-branch >"$BATS_TEST_TMPDIR/fin.log" 2>&1 ) || { cat "$BATS_TEST_TMPDIR/fin.log"; false; }
  f="$(grep -l '완료 PR #7' "$ROOT/channels/public"/*.md | head -1)"; [ -n "$f" ]; grep -q '"kind":"status"' "$f"; grep -q 'fin' "$f"
  [ "$(grep -l '완료 PR #7' "$ROOT/channels/public"/*.md | wc -l)" -eq 1 ]
  grep -q '"state":"done"' "$ROOT/sessions/claude:$(id -un):fin-0001.json"
  printf '{}' | bash "$B" deliver --platform claude --event on_prompt --sid "$SA" --stdin-json - 2>/dev/null | ctx | grep -q '완료 PR #7'
}
@test "L10 milestone 이 suspended 세션을 되살릴 때 토큰을 회전시키지 않는다 — env 주입 토큰으로 이어서 post 가능" {
  d="$BATS_TEST_TMPDIR/env10"; mkdir -p "$d"; chmod 775 "$d"
  CLAUDE_ENV_FILE="$d/env" hook '{"hook_event_name":"SessionStart","session_id":"s-0010","source":"startup"}' >/dev/null; SID="claude:$(id -un):s-0010"
  t1="$(cat "$ROOT/sessions/$SID.token")"; grep -q "$t1" "$d/env"
  printf '{"session_id":"s-0010","reason":"other"}' | bash "$B" end --hook --platform claude --stdin-json -; grep -q '"state":"suspended"' "$ROOT/sessions/$SID.json"
  CLAUDE_CODE_SESSION_ID=s-0010 run bash "$B" milestone --kind status -m "after suspend"; [ "$status" -eq 0 ]; grep -q '"state":"active"' "$ROOT/sessions/$SID.json"
  [ "$(cat "$ROOT/sessions/$SID.token")" = "$t1" ]
  ( . "$d/env"; run bash "$B" post --channel public --kind note -m with-old-env-token; [ "$status" -eq 0 ] )
}
