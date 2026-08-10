#!/bin/bash
# Run the Athena CI suite locally inside a container.
#
# Mirrors what GitHub Actions runs, using the same CI container image.
# Supports both Podman (rootless, no SU — preferred) and Docker.
#
# Usage:
#   ./scripts/run_ci_local.sh              # Run all CI checks
#   ./scripts/run_ci_local.sh validate     # Plugin-distribution validation only
#   ./scripts/run_ci_local.sh test         # Contract tests with coverage threshold
#   ./scripts/run_ci_local.sh static       # Lint + format-check + typecheck
#   ./scripts/run_ci_local.sh markdownlint # Documentation lint
#   ./scripts/run_ci_local.sh workflow     # Workflow syntax + schema validation
#
# Container engine: auto-detected (podman first, docker fallback).
# Override: CONTAINER_ENGINE=docker ./scripts/run_ci_local.sh
#
# Image: uses 'athena-ci:local' if available, falls back to GHCR image.
# Build locally: just ci-build  (or: podman build -f ci/Containerfile -t athena-ci:local .)

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUBSET="${1:-all}"

# CI image: built locally from ci/Containerfile.
# (No GHCR fallback: Athena's validate_skills.py self-contained policy forbids
# scripts from referencing other HomericIntelligence repositories.)
LOCAL_IMAGE="athena-ci:local"

# Colors
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
# Container engine detection
# ============================================================================

detect_engine() {
    if [ -n "${CONTAINER_ENGINE:-}" ]; then
        if ! command -v "${CONTAINER_ENGINE}" &> /dev/null; then
            log_error "CONTAINER_ENGINE=${CONTAINER_ENGINE} not found in PATH"
            exit 1
        fi
        log_info "Container engine: ${CONTAINER_ENGINE} (from env)"
        return
    fi

    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        log_info "Container engine: podman (rootless)"
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        log_info "Container engine: docker"
    else
        log_error "No container engine found. Install podman (recommended) or docker."
        log_error "  Podman: https://podman.io/getting-started/installation"
        exit 1
    fi
    export CONTAINER_ENGINE
}

# ============================================================================
# Image resolution
# ============================================================================

resolve_image() {
    if "${CONTAINER_ENGINE}" image exists "${LOCAL_IMAGE}" 2>/dev/null || \
       "${CONTAINER_ENGINE}" images -q "${LOCAL_IMAGE}" 2>/dev/null | grep -q .; then
        CI_IMAGE="${LOCAL_IMAGE}"
        log_info "Using local CI image: ${CI_IMAGE}"
    else
        log_error "Local image '${LOCAL_IMAGE}' not found."
        log_error "Build it first: just ci-build"
        log_error "  (podman build -f ci/Containerfile -t ${LOCAL_IMAGE} .)"
        exit 1
    fi
    export CI_IMAGE
}

# ============================================================================
# Run a command inside the CI container
# ============================================================================
# Volume mounts:
#   /workspace  — the full repo (rw, :Z for SELinux/Podman)
# --userns=keep-id — Podman: map host UID into container (fixes mounted file ownership)
# No effect on Docker (flag ignored or equivalent to default behavior)

run_in_container() {
    local cmd=("$@")
    local engine_flags=()

    # Podman-specific flags for rootless execution.
    # keep-id:uid=1000,gid=1000 runs the process as the image's non-root 'ci'
    # user (uid 1000) while mapping it to the invoking host UID, so files
    # written into the mounted workspace are owned by the host user — works
    # both on dev hosts (uid 1000) and GitHub runners (uid 1001).
    if [ "${CONTAINER_ENGINE}" = "podman" ]; then
        engine_flags+=(--userns=keep-id:uid=1000,gid=1000)
    fi

    "${CONTAINER_ENGINE}" run --rm \
        "${engine_flags[@]}" \
        --volume "${PROJECT_ROOT}:/workspace:Z" \
        --workdir /workspace \
        "${CI_IMAGE}" \
        "${cmd[@]}"
}

# ============================================================================
# CI steps
# ============================================================================

run_validate() {
    log_step "Validate plugin distribution"
    run_in_container uv run python scripts/validate_skills.py
}

run_test() {
    log_step "Contract tests with coverage threshold (>=80%)"
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
    log_step "Static checks (ruff lint, format-check, mypy typecheck)"
    run_in_container uv run ruff check scripts tests skills
    run_in_container uv run ruff format --check scripts tests skills
    run_in_container uv run mypy --strict --explicit-package-bases scripts tests skills/_cli.py skills/*/scripts/*.py
}

run_markdownlint() {
    log_step "Markdown lint (public docs and skills)"
    run_in_container uv run pymarkdown -d MD013,MD024,MD033,MD041,MD046 scan README.md AGENTS.md CLAUDE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md docs skills
}

run_workflow() {
    log_step "Workflow syntax + schema validation"
    run_in_container uv run yamllint .github/workflows
    run_in_container uv run check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml
}

# ============================================================================
# Main
# ============================================================================

FAILED=()

run_step() {
    local name="$1"
    local fn="$2"
    if ! "${fn}"; then
        FAILED+=("${name}")
        log_error "${name} FAILED"
    fi
}

detect_engine
resolve_image

log_info "CI subset: ${SUBSET}"
log_info "Project root: ${PROJECT_ROOT}"

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
        log_error "Unknown subset: ${SUBSET}"
        log_error "Valid values: all, validate, test, static, markdownlint, workflow"
        exit 1
        ;;
esac

echo ""
if [ "${#FAILED[@]}" -eq 0 ]; then
    log_info "All CI checks passed."
else
    log_error "Failed: ${FAILED[*]}"
    exit 1
fi
