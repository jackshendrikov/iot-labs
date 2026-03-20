set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

install:
    uv sync --extra dev

run-agent:
    uv run python -m src.agent.main

run-store:
    uv run python -m src.store.main

run-hub:
    uv run python -m src.hub.main

run-edge:
    python -m src.edge.main

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

docker-up:
    Set-Location docker; docker compose up --build

docker-down:
    Set-Location docker; docker compose down -v

clean:
    Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force
