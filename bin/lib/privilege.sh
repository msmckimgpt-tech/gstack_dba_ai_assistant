#!/usr/bin/env bash
# bin/lib/privilege.sh
#
# Cycle 스크립트 공용 권한 어댑터 (AGENTS.md §13.2.10).
#
# ── 문제 ──────────────────────────────────────────────────────────────────
# 같은 프로젝트를 여러 OS 계정(root / claude-corp / …)이 번갈아 다루면, 공유 운영
# 파일 `<project_root>/worktrees/REGISTRY.md` 의 소유자가 매 cycle 바뀐다. `mktemp` 는
# 파일을 0600 으로 만들고 `mv` 는 그 모드를 그대로 남기므로, 원자 rewrite 를 한 번
# 거칠 때마다 파일이 `0600 <직전 실행자>` 로 굳는다. POSIX ACL 이 걸린 배치에서는
# `chmod` 의 group 비트가 ACL `mask` 를 덮어써 `mask::---` 가 되고
# `user:<other>:rwx` 가 `#effective:---` 로 무효화된다 → 다음 cycle 을 다른 계정으로
# 돌리면 REGISTRY 접근이 통째로 막힌다 (2026-07-27 라이브 실증: cycle-init 기록 실패
# + cycle-finalize Step 6 이 그 권한 실패를 "비-META-0029 스키마" 로 오진).
#
# ── 설계: 최소 권한, 최소 개입 ────────────────────────────────────────────
# "non-root 면 스크립트 전체를 sudo 로 재실행" 방식을 먼저 시도했고, §18.8 적대 검증이
# 격리 sandbox 실측으로 그 방식의 결함 3건을 재현해 **폐기**했다 (REV-20260727T190500):
#   ① `sudo` 는 `-E` 를 줘도 `USER`/`LOGNAME` 을 runas 로 덮어쓴다 → `--agent` 기본값이
#      `root` 가 되어 브랜치가 `ai/root/<feat>` 로 생성(그리고 dry-run 프리뷰와 실제
#      실행의 브랜치명이 어긋남).
#   ② `run_or_dryrun` 의 `eval` 이 root 로 실행되어, 기계가 만든 feature slug 한 개가
#      root 임의 명령 실행이 된다.
#   ③ git 이 root 로 돌면 `.git/worktrees/<name>` · `.worktrees` · `FETCH_HEAD` ·
#      `refs/heads/<branch>` 가 root 소유로 남아, ACL 없는 배치에서는 cycle-init 성공
#      직후 원 호출자가 `git add` 조차 못 한다.
# 부수적으로 `secure_path` 가 PATH 를 교체해 `~/.local/bin` 의 `gh` 를 잃고, sudo 가
# umask 를 0022 로 강제해 group-write 공유 배치를 무력화하는 회귀도 확인됐다.
#
# 그래서 **git 은 언제나 원 호출자로 실행**하고, 권한 승격은 다음 한 가지에만 쓴다:
#
#   `priv_ensure_writable <file>` — 공유 운영 파일이 **현재 실행자가 쓸 수 없는 상태로
#   굳어 있을 때만** `sudo` 로 접근권을 복구한다. 정상 상태에서는 sudo 를 **한 번도**
#   호출하지 않는다 (이미 쓸 수 있으면 즉시 return).
#
# 복구는 최소 단계로 올라간다: ① chmod 0664 (ACL 배치에서는 이것만으로 `mask` 가
# 복원돼 named-user ACL 이 살아난다) → ② 그래도 안 되면 chown 현재 실행자. 즉 소유권
# 이전은 정말 필요할 때만 일어난다.
#
# 쓰기 **직후**에는 `priv_share_file` 로 0664 를 되감아 다음 계정이 막히지 않게 한다.
# 이건 자기가 만든 파일에 대한 chmod 이므로 sudo 가 필요 없다 — 위 mktemp 0600 열화의
# 직접 해독제다.
#
# 모든 함수는 **실패해도 호출부를 죽이지 않는다** (cycle 진행 비차단). `sudo` 가 없거나
# passwordless 가 아니면(`sudo -n` 실패) 경고 후 그대로 진행한다 — hook·cron 처럼
# 비대화 컨텍스트에서 암호 프롬프트에 걸려 멈추는 쪽이 더 나쁘다.
#
# 우회: `PRIV_NO_SUDO=1` (승격 시도 억제 — 디버깅·sudo 부재 컨테이너).

# 이미 로드됐으면 재정의하지 않는다 (다중 source 안전).
[ -n "${PRIV_LIB_LOADED:-}" ] && return 0
PRIV_LIB_LOADED=1

priv_log()  { printf "[privilege] %s\n"       "$*" >&2; }
priv_warn() { printf "[privilege] WARN: %s\n" "$*" >&2; }

# ── sudo 가용성 (한 번만 판정해 캐시) ─────────────────────────────────────
# `-n` 고정: 절대 프롬프트하지 않는다. hook/cron 무한 대기 차단의 핵심.
priv_sudo_ok() {
  [ "${PRIV_NO_SUDO:-0}" = "1" ] && return 1
  if [ -z "${_PRIV_SUDO_OK:-}" ]; then
    if [ "$(id -u)" -eq 0 ]; then
      _PRIV_SUDO_OK=root                       # 이미 root — 승격 불필요
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
      _PRIV_SUDO_OK=yes
    else
      _PRIV_SUDO_OK=no
    fi
  fi
  [ "$_PRIV_SUDO_OK" != "no" ]
}

# root 로 실행 중인가 (승격이 아예 필요 없는 상태).
priv_is_root() { [ "$(id -u)" -eq 0 ]; }

# ── 판별: 읽을 수 없다 / 쓸 수 없다 ──────────────────────────────────────
# "부재" 와 "권한으로 접근 불가" 를 갈라야 한다. `grep`·`awk` 는 읽지 못하면 조용히
# 빈 결과/false 를 내므로, 구분하지 않으면 권한 문제가 스키마 문제로 둔갑한다.
priv_unreadable() {
  local p="${1:-}"
  [ -n "$p" ] || return 1
  [ -e "$p" ] && [ ! -r "$p" ]
}

# 쓸 수 없다 = 파일이 있는데 -w 아님, 또는 파일이 없고 부모 디렉터리가 -w 아님.
# 원자 rewrite(mktemp+mv)와 lock 파일 생성은 **부모 디렉터리** 쓰기 권한을 요구하므로
# 파일 자체의 -w 만 보는 것으로는 실패 원인을 놓친다.
priv_unwritable() {
  local p="${1:-}"
  [ -n "$p" ] || return 1
  if [ -e "$p" ]; then
    [ ! -w "$p" ] && return 0
    local d; d="$(dirname "$p")"
    [ ! -w "$d" ]                              # rewrite 는 디렉터리 쓰기도 필요
  else
    [ ! -w "$(dirname "$p")" ]
  fi
}

# 접근 불가 원인을 한 줄로 (호출부 진단 메시지용).
priv_access_reason() {
  local p="${1:-}"
  if priv_unreadable "$p"; then printf 'read-denied'
  elif priv_unwritable "$p"; then printf 'write-denied'
  else printf 'ok'; fi
}

# ── 승격: 공유 운영 파일 접근권 복구 (유일한 sudo 사용처) ────────────────
# 사용: priv_ensure_writable <file>
#   0 = 이제 쓸 수 있다 (원래 가능했거나 복구 성공) / 1 = 여전히 불가
# 정상 상태에서는 첫 줄에서 return — sudo 호출 0회.
priv_ensure_writable() {
  local f="${1:-}"
  [ -n "$f" ] || return 1
  priv_unwritable "$f" || return 0             # 이미 쓸 수 있다 (일반 경로)

  # symlink 는 건드리지 않는다 — chmod/chown 은 링크를 추종하므로, 호출자가 쓸 수 있는
  # 디렉터리에 놓인 링크를 통해 임의 파일의 모드·소유권을 바꿔줄 수 있다(적대 검증 §5).
  if [ -L "$f" ]; then
    priv_warn "공유 파일이 symlink 입니다 — 권한 복구를 거부합니다 (링크 추종 방지): $f"
    return 1
  fi

  if priv_is_root; then
    return 1                                   # root 가 못 쓰면 승격으로 해결될 문제가 아니다
  fi
  if ! priv_sudo_ok; then
    priv_warn "$f 접근 불가($(priv_access_reason "$f")) + passwordless sudo 불가 — 권한 복구 생략."
    return 1
  fi

  # ① 모드만 복구 시도. ACL 배치에서는 chmod 0664 가 mask 를 rw- 로 되살려
  #    `user:<me>:rwx` 가 effective 해진다 → 소유권 이전 없이 해결.
  if [ -e "$f" ]; then
    sudo -n chmod 0664 -- "$f" 2>/dev/null || true
    priv_unwritable "$f" || { priv_log "공유 파일 접근권 복구(chmod 0664): $f"; return 0; }
    # ② 그래도 안 되면 소유권을 현재 실행자로. --no-dereference: 링크 추종 금지.
    sudo -n chown --no-dereference "$(id -u):$(id -g)" -- "$f" 2>/dev/null || true
    sudo -n chmod 0664 -- "$f" 2>/dev/null || true
    priv_unwritable "$f" || { priv_log "공유 파일 접근권 복구(chown+chmod): $f"; return 0; }
  else
    # 파일 부재 + 부모 디렉터리에 쓸 수 없는 경우 — 디렉터리 쪽을 푼다.
    local d; d="$(dirname "$f")"
    if [ -d "$d" ] && [ ! -L "$d" ]; then
      sudo -n chmod 0775 -- "$d" 2>/dev/null || true
      priv_unwritable "$f" || { priv_log "공유 디렉터리 접근권 복구(chmod 0775): $d"; return 0; }
      sudo -n chown --no-dereference "$(id -u):$(id -g)" -- "$d" 2>/dev/null || true
      priv_unwritable "$f" || { priv_log "공유 디렉터리 접근권 복구(chown+chmod): $d"; return 0; }
    fi
  fi

  priv_warn "$f 접근권 복구 실패 (원인: $(priv_access_reason "$f"))"
  return 1
}

# ── 쓰기 후 모드 되감기 (sudo 불요 — 자기 파일) ──────────────────────────
# 여러 계정이 번갈아 쓰는 파일을 group-writable 로 되돌린다. mktemp+mv 가 남긴 0600
# 열화를 그 자리에서 해독하고, ACL 배치에서는 `mask` 도 함께 복원한다.
priv_share_file() {
  local f="${1:-}"
  [ -n "$f" ] && [ -e "$f" ] || return 0
  [ -L "$f" ] && return 0                      # 링크 추종 금지 (위와 동일 이유)
  chmod 0664 -- "$f" 2>/dev/null || true
  return 0
}

priv_share_dir() {
  local d="${1:-}"
  [ -n "$d" ] && [ -d "$d" ] || return 0
  [ -L "$d" ] && return 0
  chmod 0775 -- "$d" 2>/dev/null || true
  return 0
}
