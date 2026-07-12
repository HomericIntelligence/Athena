# ===========================================================================
# Athena — task entry points.
#
# Designed so Odysseus's justfile athena-{start,lint,test,bootstrap}
# recipes remain thin delegates into this file.
# ===========================================================================

# Source: pixi.toml env will be active when called via `pixi run just <recipe>`.
# Bare `just <recipe>` falls back to system Python; CI uses pixi.

# Default — show the catalogue.
default:
    @just --list

# ===========================================================================
# Quality gates
# ===========================================================================

# Style + lint (ruff check).
lint:
    pixi run ruff check .

# Apply ruff format (in-place).
format:
    pixi run ruff format .

# Verify ruff format without writing (CI gate).
format-check:
    pixi run ruff format --check .

# Strict mypy over athena/ + any optional utility modules.
typecheck:
    pixi run mypy --strict athena

# Run pytest (unit + integration).
test:
    pixi run pytest -v --strict-markers

# Pip-audit dependency vulnerability scan.
audit:
    pixi run pip-audit

# Validate that .claude-plugin/marketplace.json references real skills/.
validate-marketplace:
    pixi run python -m athena.validate_marketplace

# Markdown lint via .markdownlint.yaml.
markdownlint:
    pixi run markdownlint .

# Aggregate CI-equivalent gate.
check: lint format-check typecheck validate-marketplace
    @echo "Athena: check passed"

# Aggregate including test + audit + markdownlint. Used by `pixi run all`.
all: check test audit markdownlint
    @echo "Athena: all passed"

# ===========================================================================
# Lifecycle
# ===========================================================================

# One-command setup for a fresh clone.
bootstrap:
    pixi install
    pixi run pre-commit install || echo "pre-commit not on PATH; skipping"
    @echo "Athena: bootstrap complete"

# Editable install -e .[dev,automation] into the active environment.
install:
    pixi run pip install --no-deps -e '.[dev,automation]'

# Remove local cache directories.
clean:
    rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov

# ===========================================================================
# Athena-as-a-service (delegated by Odysseus)
# ===========================================================================

# Re-export Odysseus-side recipe names so the Odysseus justfile can
# `cd agentic/Athena && just <recipe>` without copy-pasting the names.
# These are intentionally minimal: Athena itself is metadata-driven; there
# is no daemon to start.

start:
    @echo "Athena: no daemon to start (plugin/skill distribution only)"

# Service-style lint — output goes to the Odysseus aggregate `just lint`.
lint-md: markdownlint

# Display the marketplace as a grep-friendly table (one skill per line).
catalog:
    @echo "Skill catalog (source: .claude-plugin/marketplace.json):"
    @python3 -c "import json,sys; d=json.load(open('.claude-plugin/marketplace.json')); [print(f\"  - {p['name']}: {p['description']}\") for p in d['plugins']]"
