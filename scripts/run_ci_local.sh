#!/bin/bash
# Run Athena continuous integration (CI) checks in a local container.
#
# This script runs the local subset of the GitHub Actions checks.
# It uses the same CI image for checks that run in a container.
# Use rootless Podman where possible. You can also use Docker.
#
# Use one of these commands:
#   ./scripts/run_ci_local.sh              # Run all supported local CI checks.
#   ./scripts/run_ci_local.sh validate     # Validate the plugin distribution.
#   ./scripts/run_ci_local.sh test         # Run contract tests with the minimum coverage requirement.
#   ./scripts/run_ci_local.sh static       # Run lint, format, and type checks.
#   ./scripts/run_ci_local.sh markdownlint # Lint the documentation.
#   ./scripts/run_ci_local.sh workflow     # Validate workflow syntax and schemas.
#
# The script selects a container engine. It tries Podman before Docker.
# To select the engine, set CONTAINER_ENGINE. For example:
#   CONTAINER_ENGINE=docker ./scripts/run_ci_local.sh
#
# The script uses the local 'athena-ci:local' image.
# Before you run the script, build the image with `just ci-build` or this command:
#   podman build -f ci/Containerfile -t athena-ci:local .

set -euo pipefail

# ============================================================================
# Configure the script.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUBSET="${1:-all}"

# The script uses the local image from ci/Containerfile.
# It does not use a GitHub Container Registry (GHCR) alternative.
# The self-contained policy in validate_skills.py prohibits references to other
# HomericIntelligence repositories.
LOCAL_IMAGE="athena-ci:local"

# These values set the output colors.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[CI]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[CI]${NC} $*"; }
log_error() { echo -e "${RED}[CI]${NC} $*" >&2; }
log_step()  { echo -e "\n${BLUE}==>${NC} $*"; }

# ============================================================================
# Detect the container engine.
# ============================================================================

detect_engine() {
    if [ -n "${CONTAINER_ENGINE:-}" ]; then
        if ! command -v "${CONTAINER_ENGINE}" &> /dev/null; then
            log_error "The script cannot find the selected executable '${CONTAINER_ENGINE}'."
            exit 1
        fi
        log_info "The selected container engine is '${CONTAINER_ENGINE}'."
        return
    fi

    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        log_info "The script selected Podman as the rootless container engine."
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        log_info "The script selected Docker as the container engine."
    else
        log_error "The command cannot find Podman or Docker. Install a container engine."
        log_error "Use Podman where possible."
        log_error "Install Podman from 'https://podman.io/getting-started/installation'."
        exit 1
    fi
    export CONTAINER_ENGINE
}

# ============================================================================
# Resolve the image.
# ============================================================================

resolve_image() {
    if "${CONTAINER_ENGINE}" image exists "${LOCAL_IMAGE}" 2>/dev/null || \
       "${CONTAINER_ENGINE}" images -q "${LOCAL_IMAGE}" 2>/dev/null | grep -q .; then
        CI_IMAGE="${LOCAL_IMAGE}"
        log_info "The command uses this local CI image: '${CI_IMAGE}'."
    else
        log_error "The command cannot find the local image '${LOCAL_IMAGE}'."
        log_error "Before you continue, run this command:"
        log_error "just ci-build"
        log_error "Alternatively, run this command:"
        log_error "podman build -f ci/Containerfile -t ${LOCAL_IMAGE} ."
        exit 1
    fi
    export CI_IMAGE
}

# ============================================================================
# Run a command in the CI container.
# ============================================================================
# The /workspace path contains the complete repository.
# The `rw` and `:Z` settings give the container write access and set the SELinux label.
# For Podman, --userns=keep-id maps the host user identifier (UID) into the container.
# The script does not add this Podman-specific setting to Docker commands.

run_in_container() {
    local cmd=("$@")
    local engine_flags=(--rm)

    # Use Podman-specific options for rootless execution.
    # keep-id:uid=1000,gid=1000 runs the process as the image user `ci`.
    # The `ci` user has UID 1000. Podman maps this UID to the host UID.
    # Thus, files in the mounted workspace belong to the host user.
    # This mapping works on development hosts and GitHub runners.
    if [ "${CONTAINER_ENGINE}" = "podman" ]; then
        engine_flags+=(--userns=keep-id:uid=1000,gid=1000)
    fi

    "${CONTAINER_ENGINE}" run \
        "${engine_flags[@]}" \
        --volume "${PROJECT_ROOT}:/workspace:Z" \
        --workdir /workspace \
        "${CI_IMAGE}" \
        "${cmd[@]}"
}

# ============================================================================
# Run the CI steps.
# ============================================================================

run_validate() {
    log_step "Validate the plugin distribution."
    run_in_container uv run python scripts/validate_skills.py
}

run_test() {
    log_step "Run contract tests with the minimum 80 percent coverage requirement."
    run_in_container bash -c '\
        uv run coverage erase && \
        PYTHONDONTWRITEBYTECODE=1 ATHENA_COVERAGE=1 \
            uv run coverage run --branch --parallel-mode --source=scripts,skills -m pytest -q && \
        uv run coverage combine && \
        uv run coverage json -o coverage.json && \
        uv run python scripts/coverage_policy.py coverage.json --minimum 80 && \
        uv run coverage report --show-missing'
}

run_static() {
    log_step "Run Ruff, the format check, and the mypy type check."
    run_in_container uv run ruff check scripts tests skills &&
    run_in_container uv run ruff format --check scripts tests skills &&
    run_in_container uv run mypy --strict --explicit-package-bases scripts tests skills/_cli.py skills/*/scripts/*.py
}

run_markdownlint() {
    log_step "Check Markdown in public documents and skills."
    run_in_container uv run pymarkdown -d MD013,MD024,MD033,MD041,MD046 scan README.md AGENTS.md CLAUDE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md .github docs skills
}

run_workflow() {
    log_step "Validate workflow syntax and schemas."
    run_in_container uv run yamllint .github/workflows &&
    run_in_container uv run check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml
}

# ============================================================================
# Run the selected checks.
# ============================================================================

FAILED=()

run_step() {
    local name="$1"
    local fn="$2"
    if ! "${fn}"; then
        FAILED+=("${name}")
        log_error "The '${name}' check failed."
    fi
}

detect_engine
resolve_image

log_info "The CI subset is '${SUBSET}'."
log_info "The project root is '${PROJECT_ROOT}'."

case "${SUBSET}" in
    validate)
        run_step "validate" run_validate
        ;;
    test)
        run_step "test" run_test
        ;;
    static)
        run_step "static" run_static
        ;;
    markdownlint)
        run_step "markdownlint" run_markdownlint
        ;;
    workflow)
        run_step "workflow" run_workflow
        ;;
    all)
        run_step "validate" run_validate
        run_step "test" run_test
        run_step "static" run_static
        run_step "markdownlint" run_markdownlint
        run_step "workflow" run_workflow
        ;;
    *)
        log_error "The subset is not valid: '${SUBSET}'."
        log_error "Use one of these values:"
        log_error "all, validate, test, static, markdownlint, workflow"
        exit 1
        ;;
esac

echo ""
if [ "${#FAILED[@]}" -eq 0 ]; then
    log_info "All selected local CI checks passed."
else
    log_error "These checks failed: '${FAILED[*]}'."
    exit 1
fi
