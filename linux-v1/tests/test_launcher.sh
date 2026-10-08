#!/usr/bin/env bash
# Portable integration test for linux-v1/run_dirigent.sh.
set -Eeuo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TEMP_ROOT="$(mktemp -d)"
LAUNCHER_PID=""
EXTERNAL_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$LAUNCHER_PID" ]]; then
    kill "$LAUNCHER_PID" 2>/dev/null || true
    wait "$LAUNCHER_PID" 2>/dev/null || true
  fi
  [[ -n "$EXTERNAL_PID" ]] && kill "$EXTERNAL_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  rm -rf -- "$TEMP_ROOT"
}
trap cleanup EXIT

health() {
  curl --silent --fail --max-time 1 http://127.0.0.1:8000/health \
    | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'
}

if health; then
  echo 'Refusing to test: port 8000 already has a healthy Dirigent-style backend.' >&2
  exit 1
fi

mkdir -p "$TEMP_ROOT/project/linux-v1/tests" "$TEMP_ROOT/project/.venv/bin"
cp "$SOURCE_ROOT/linux-v1/run_dirigent.sh" "$TEMP_ROOT/project/linux-v1/run_dirigent.sh"
chmod +x "$TEMP_ROOT/project/linux-v1/run_dirigent.sh"
ln -s "$(command -v python3)" "$TEMP_ROOT/project/.venv/bin/python"

cat > "$TEMP_ROOT/project/run_backend.py" <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            body = json.dumps({'status': 'ok'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        pass

HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
PY

(cd "$TEMP_ROOT" && exec "$TEMP_ROOT/project/linux-v1/run_dirigent.sh" --backend-only) \
  >"$TEMP_ROOT/managed.out" 2>&1 &
LAUNCHER_PID=$!
for _ in {1..40}; do health && break; sleep 0.25; done
health
test -s "$TEMP_ROOT/project/linux-v1/runtime/backend.pid"
for _ in {1..40}; do
  grep -q 'Dirigent is ready.' "$TEMP_ROOT/managed.out" && break
  sleep 0.1
done
grep -q 'Dirigent is ready.' "$TEMP_ROOT/managed.out"
kill -TERM "$LAUNCHER_PID"
wait "$LAUNCHER_PID" || true
LAUNCHER_PID=""
! health
test ! -e "$TEMP_ROOT/project/linux-v1/runtime/backend.pid"

mkdir -p "$TEMP_ROOT/project/frontend/node_modules" "$TEMP_ROOT/bin"
cat > "$TEMP_ROOT/bin/npm" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$$" > "$FRONTEND_PID_FILE"
exec sleep 30
SH
chmod +x "$TEMP_ROOT/bin/npm"
FRONTEND_PID_FILE="$TEMP_ROOT/frontend.pid" PATH="$TEMP_ROOT/bin:$PATH" \
  "$TEMP_ROOT/project/linux-v1/run_dirigent.sh" >"$TEMP_ROOT/frontend.out" 2>&1 &
LAUNCHER_PID=$!
for _ in {1..40}; do
  [[ -s "$TEMP_ROOT/frontend.pid" ]] && break
  sleep 0.25
done
test -s "$TEMP_ROOT/frontend.pid"
FRONTEND_PID="$(<"$TEMP_ROOT/frontend.pid")"
health
grep -q '\[4/4\] Launching frontend' "$TEMP_ROOT/frontend.out"
kill -TERM "$LAUNCHER_PID"
wait "$LAUNCHER_PID" || true
LAUNCHER_PID=""
! health
test ! -e "$TEMP_ROOT/project/linux-v1/runtime/backend.pid"
! kill -0 "$FRONTEND_PID" 2>/dev/null
FRONTEND_PID=""

python3 "$TEMP_ROOT/project/run_backend.py" >"$TEMP_ROOT/external.out" 2>&1 &
EXTERNAL_PID=$!
for _ in {1..40}; do health && break; sleep 0.25; done
health
"$TEMP_ROOT/project/linux-v1/run_dirigent.sh" --backend-only >"$TEMP_ROOT/reused.out" 2>&1
grep -q 'reusing it' "$TEMP_ROOT/reused.out"
health
kill "$EXTERNAL_PID"
wait "$EXTERNAL_PID" || true
EXTERNAL_PID=""

echo 'Linux launcher smoke test passed.'
