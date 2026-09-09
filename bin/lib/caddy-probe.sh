#!/usr/bin/env bash
# Probes share Caddy's network, but never create children inside its PID cgroup.

caddy_read_file() (
  set -o pipefail
  local cid
  cid="$(timeout -k 2 5 "${DC[@]}" ps -q caddy)" || return 1
  [ -n "$cid" ] || return 1
  timeout -k 2 10 docker cp "$cid:$1" - | tar -xOf -
)

caddy_probe() (
  local cid image probe_dir probe_name
  cid="$(timeout -k 2 5 "${DC[@]}" ps -q caddy)" || return 1
  [ -n "$cid" ] || return 1
  image="$(timeout -k 2 5 docker inspect -f '{{.Image}}' "$cid")" || return 1
  [ -n "$image" ] || return 1
  probe_dir="$(mktemp -d "$STATE_DIR/caddy-probe.XXXXXX")" || return 1
  probe_name="dqa-$(basename "$probe_dir")"
  _cleanup_caddy_probe() {
    local created=""
    [ ! -r "$probe_dir/cid" ] || read -r created < "$probe_dir/cid" || true
    if [[ "$created" =~ ^[a-f0-9]{64}$ ]]; then
      timeout -k 2 10 docker rm -f "$created" >/dev/null 2>&1 || true
    fi
    rm -f "$probe_dir/cid"
    rmdir "$probe_dir"
  }
  trap _cleanup_caddy_probe EXIT
  trap 'exit 143' TERM
  trap 'exit 130' INT
  timeout -k 5 15 docker run --rm --init --pull never --name "$probe_name" --cidfile "$probe_dir/cid" --network "container:$cid" \
    --read-only --cap-drop ALL --security-opt no-new-privileges \
    --pids-limit 32 --memory 64m --cpus 0.25 --entrypoint wget "$image" "$@"
)
