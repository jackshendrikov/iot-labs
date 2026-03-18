set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

install:
    uv sync --extra dev

run:
    uv run python -m src.main

test:
    uv run pytest -q

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

clean:
    Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force
