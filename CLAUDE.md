# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Luminary** — FastAPI web application with an aurora-animated SPA frontend, developed inside a **Podman pod** via `podman-compose`.

## Dev Environment (Podman)

All development happens inside the container. The `app/` directory is bind-mounted with live reload enabled, so edits on the host are immediately reflected.

```bash
make build   # Build the container image
make up      # Start the pod in the background
make down    # Stop and remove the pod
make logs    # Tail container logs
make shell   # Open a bash shell inside the api container
```

## Common Commands (run inside the container via `make shell` or `podman-compose exec api ...`)

```bash
# Tests
make test                             # Run full test suite
podman-compose exec api pytest tests/test_main.py -v   # Run a single test file

# Lint
make lint                             # Ruff lint check
podman-compose exec api ruff check app/ --fix           # Auto-fix lint issues
```

## Architecture

```
luminary/   (directory: myproject/)
├── app/
│   └── main.py          # FastAPI app instance and routes
├── tests/
│   └── test_main.py     # pytest tests using FastAPI TestClient
├── Containerfile        # Container image definition (python:3.12-slim)
├── compose.yaml         # Podman pod/service definition; mounts app/ with :z SELinux label
├── Makefile             # Shortcuts for podman-compose commands
├── pyproject.toml       # Project metadata and tool config (pytest, ruff)
└── requirements.txt     # All dependencies (app + dev)
```

- The FastAPI app lives in `app/main.py` and is imported as `app.main:app`.
- New routers should be created in `app/routers/` and included in `app/main.py`.
- The `compose.yaml` volume mount uses `:z` for SELinux compatibility with Podman — keep this when adding new bind mounts.
- `uvicorn` runs with `--reload` in the container, so code changes in `app/` take effect immediately without restarting the pod.
