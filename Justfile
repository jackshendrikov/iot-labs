set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

install:
    uv sync --extra dev

# --- Road Vision pipeline (Lab 1–5) ---
run-agent:
    uv run python -m src.agent.main

run-store:
    uv run python -m src.store.main

run-hub:
    uv run python -m src.hub.main

run-edge:
    uv run python -m src.edge.main

# --- Universal Sensors pipeline ---
run-sensors-agent:
    uv run python -m src.sensors_agent.main

run-sensors-edge:
    uv run python -m src.sensors_edge.main

run-sensors-hub:
    uv run python -m src.sensors_hub.main

generate-sensors:
    uv run python -m src.synthetic.main

seed-sensors:
    uv run python -m src.synthetic.main --seed-db

# --- Якість коду ---
test:
    uv run pytest --tb=line

lint:
    uv run ruff check src tests

format:
    uv run ruff format src tests

typecheck:
    uv run mypy src

precommit:
    uv run pre-commit run --all-files

# --- Docker ---
docker-up:
    Set-Location docker; docker compose up --build

docker-down:
    Set-Location docker; docker compose down -v

docker-logs service="":
    Set-Location docker; docker compose logs -f {{service}}

clean:
    Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force
