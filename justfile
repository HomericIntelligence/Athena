# Athena plugin-distribution task entry points.

default:
    @just --list

bootstrap:
    uv sync --locked
    uv run pre-commit install

validate:
    uv run python scripts/validate_skills.py

test:
    uv run coverage erase
    PYTHONDONTWRITEBYTECODE=1 ATHENA_COVERAGE=1 uv run coverage run --branch --parallel-mode --source=scripts,skills -m pytest -q
    uv run coverage combine
    uv run coverage json -o coverage.json
    uv run python scripts/coverage_policy.py coverage.json --minimum 80
    uv run coverage report --show-missing

lint:
    uv run ruff check scripts tests skills

format-check:
    uv run ruff format --check scripts tests skills

typecheck:
    uv run mypy --strict --explicit-package-bases scripts tests skills/_cli.py skills/*/scripts/*.py

static:
    just lint
    just format-check
    just typecheck

markdownlint:
    uv run pymarkdown -d MD013,MD024,MD033,MD041,MD046 scan README.md AGENTS.md CLAUDE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md docs skills

workflow-lint:
    uv run yamllint .github/workflows

workflow-check:
    just workflow-lint
    uv run check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml

package:
    uv run python scripts/package_plugin.py

sbom:
    just package
    uv run python scripts/generate_sboms.py

sca:
    uv run python scripts/scan_vulnerabilities.py --inventory dist-internal/syft-environment.json

check:
    just validate
    just test
    just static
    just markdownlint
    just workflow-check

all:
    just check
    just package

clean:
    rm -rf dist dist-internal .coverage .pytest_cache __pycache__ scripts/__pycache__ scripts/policies/__pycache__ skills/__pycache__ skills/*/scripts/__pycache__ tests/__pycache__ tests/unit/__pycache__ tests/fixtures/__pycache__ .venv

catalog:
    @find skills -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | sed 's/^/  - /'

ci-entrypoints:
    @just --evaluate > /dev/null
    @just --list > /dev/null

# === Containerized CI (podman by default) ===

# Build the continuous integration (CI) container image.
# Try Podman first. If Podman is unavailable, use Docker.
ci-build:
    podman build -f ci/Containerfile -t athena-ci:local . || docker build -f ci/Containerfile -t athena-ci:local .

# Run CI plugin-distribution validation in container
ci-validate:
    ./scripts/run_ci_local.sh validate

# Run CI contract tests in container
ci-test:
    ./scripts/run_ci_local.sh test

# Run CI static checks (ruff, format, mypy) in container
ci-static:
    ./scripts/run_ci_local.sh static

# Run CI markdown lint in container
ci-markdownlint:
    ./scripts/run_ci_local.sh markdownlint

# Run CI workflow validation in container
ci-workflow:
    ./scripts/run_ci_local.sh workflow

# Run all CI checks in container
ci-all:
    ./scripts/run_ci_local.sh all
