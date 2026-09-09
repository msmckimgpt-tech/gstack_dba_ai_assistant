#!/usr/bin/env bash
# Called under deploy-web's flock. Web mounts this directory read-only.

ui_release_write() { # status, revision, optional asset stamp
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] UI release $1 $2"; return 0; }
  python3 - "$STATE_DIR/ui-release/current.json" "$1" "$2" "${3:-}" <<'PY'
import json, os, re, sys, tempfile, time
from pathlib import Path
path, status, release, stamp = Path(sys.argv[1]), *sys.argv[2:]
assert status in ('pending', 'complete')
assert re.fullmatch(r'[a-f0-9]{7,40}', release)
assert status != 'complete' or re.fullmatch(r'[a-f0-9]{12}', stamp)
path.parent.mkdir(parents=True, exist_ok=True)
previous = 0
try:
    previous = int(json.loads(path.read_text()).get('generation', 0))
except (OSError, ValueError, TypeError, AttributeError):
    pass
generation = max(int(time.time() * 1000), previous + 1)
assert 0 < generation < 2**53
value = dict(status=status, release=release, generation=generation)
if status == 'complete':
    value['asset_stamp'] = stamp
fd, name = tempfile.mkstemp(dir=path.parent, prefix='.release-')
try:
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out)
        out.flush()
        os.fsync(out.fileno())
        os.fchmod(out.fileno(), 0o644)
    os.replace(name, path)
finally:
    if os.path.exists(name):
        os.unlink(name)
PY
}

ui_release_replica() { # service -> ready revision + baked asset stamp
  "${DC[@]}" exec -T "$1" python -c '
import json, os, pathlib, ssl, sys, urllib.request
ctx = ssl._create_unverified_context()  # container loopback, same readyz probe boundary
for url in ("https://localhost:8000/readyz", "http://localhost:8000/readyz"):
    try:
        with urllib.request.urlopen(url, timeout=5, context=ctx) as response:
            data = json.load(response)
        stamp = pathlib.Path("/app/web/static/.asset-stamp").read_text().strip()
        if data.get("status") == "ready" and not data.get("draining"):
            print(data["git_commit"], stamp)
            sys.exit(0)
    except Exception:
        pass
sys.exit(1)
' 2>/dev/null
}

ui_release_identity() { # expected revision -> shared stamp; refuse partial deployment
  local left right revision stamp extra
  left="$(ui_release_replica web-a)" || return 1
  right="$(ui_release_replica web-b)" || return 1
  [ "$left" = "$right" ] || return 1
  read -r revision stamp extra <<< "$left"
  [[ "$revision" = "$1" && "$stamp" =~ ^[a-f0-9]{12}$ && -z "$extra" ]] || return 1
  printf '%s\n' "$stamp"
}

ui_release_complete_for() {
  [ "$DRY_RUN" -eq 1 ] && return 1
  local stamp
  stamp="$(ui_release_identity "$1")" || return 1
  python3 - "$STATE_DIR/ui-release/current.json" "$1" "$stamp" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as source:
        value = json.load(source)
    assert value['status'] == 'complete'
    assert value['release'] == sys.argv[2] and value['asset_stamp'] == sys.argv[3]
    assert type(value['generation']) is int and 0 < value['generation'] < 2**53
except (OSError, ValueError, TypeError, KeyError, AssertionError):
    sys.exit(1)
PY
}

publish_ui_release() {
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] UI release publish $1"; return 0; }
  local stamp
  stamp="$(ui_release_identity "$1")" || {
    err "UI 완료 신호 미게시 — 두 web replica의 ready/revision/asset stamp 불일치."
    return 1
  }
  ui_release_write complete "$1" "$stamp" || return 1
  log "UI 완료 신호 게시 — release=$1 asset_stamp=$stamp (두 replica 일치)."
}
