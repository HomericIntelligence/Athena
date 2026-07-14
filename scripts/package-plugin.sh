#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

python3 scripts/validate_skills.py --quiet
version=$(python3 -c 'import json; print(json.load(open(".codex-plugin/plugin.json"))["version"])')
archive="dist/athena-plugin-${version}.tar.gz"

mkdir -p dist
tar -czf "$archive" \
  .agents .claude-plugin .codex-plugin \
  AGENTS.md CLAUDE.md LICENSE NOTICE README.md SECURITY.md \
  assets docs skills

tar -tzf "$archive" | grep -q '^skills/repo-review/SKILL.md$'
tar -tzf "$archive" | grep -q '^skills/pr-review/SKILL.md$'
tar -tzf "$archive" | grep -q '^docs/dependency-resolution.md$'
printf 'Built %s\n' "$archive"
