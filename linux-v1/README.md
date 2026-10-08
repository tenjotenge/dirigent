# Dirigent Linux launcher (v1)

`run_dirigent.sh` is the Linux/Lubuntu development launcher. It is deliberately
kept entirely under `linux-v1`; it does not replace or alter the Windows
launcher.

## Prerequisites on Lubuntu

Install Node.js/npm, Rust/Cargo, and the system libraries needed by
Tauri/WebKitGTK. Package names vary by Lubuntu release, but these are typical
Debian/Ubuntu packages:

```bash
sudo apt install nodejs npm cargo rustc pkg-config libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
```

On older Lubuntu releases that package WebKitGTK as 4.0, replace
`libwebkit2gtk-4.1-dev` with `libwebkit2gtk-4.0-dev`.

The backend's pinned Pydantic version requires Python 3.12. On Lubuntu
releases without `python3.12` in apt, install Python 3.12 with
[uv](https://docs.astral.sh/uv/getting-started/installation/) and create the
project-local environment:

```bash
cd /path/to/dirigent
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt
cd frontend && npm install
```

The launcher starts Tauri development mode, so the first Rust build may also
download Rust crates. It uses the local `.venv` automatically; activation is
not required. Environments made by `uv venv` may not include `pip`, so use
`uv pip install` for later package changes.

## Run

From any directory:

```bash
/path/to/dirigent/linux-v1/run_dirigent.sh
```

The stages are always printed in this order: virtual environment, backend,
health check, then frontend. The launcher first requests
`http://127.0.0.1:8000/health`; an existing response with `status: ok` is
reused and never stopped. Otherwise it launches `run_backend.py --no-reload`,
records its PID in `linux-v1/runtime/backend.pid`, and logs combined backend
output to `linux-v1/runtime/backend.log`.

Use backend-only mode when diagnosing the API:

```bash
/path/to/dirigent/linux-v1/run_dirigent.sh --backend-only
```

Press Ctrl+C to stop a backend started by this launcher. SIGINT, SIGTERM, and
SIGHUP stop only that managed backend process group. A reused external backend
is never terminated.

## Test

The smoke test needs Bash, `curl`, `flock`, `setsid`, `ps`, and Python 3, but no
Dirigent Python packages, Node, Rust, or desktop environment. It creates an
isolated temporary project with a stdlib health server and verifies managed
backend startup, PID recording, frontend and backend signal cleanup, and
external-backend reuse:

```bash
bash linux-v1/tests/test_launcher.sh
```

It uses port 8000 briefly and refuses to run if that port already serves a
healthy Dirigent-style endpoint.
