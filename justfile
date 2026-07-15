# Athena plugin-distribution task entry points.

default:
    @just --list

bootstrap:
    pixi install --locked
    pixi run pre-commit install

validate:
    pixi run validate

test:
    pixi run test

lint:
    pixi run lint

format-check:
    pixi run format-check

typecheck:
    pixi run typecheck

static:
    pixi run static

markdownlint:
    pixi run markdownlint

workflow-lint:
    pixi run workflow-lint

workflow-check:
    pixi run workflow-check

package:
    pixi run package

check:
    pixi run check

all:
    pixi run all

clean:
    pixi run clean

catalog:
    @find skills -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | sed 's/^/  - /'

ci-entrypoints:
    @just --evaluate > /dev/null
    @just --list > /dev/null
