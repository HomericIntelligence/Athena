#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

python3 scripts/validate_skills.py --quiet
version=$(python3 -c 'import json; print(json.load(open(".codex-plugin/plugin.json"))["version"])')
archive="dist/athena-plugin-${version}.tar.gz"
checksum="${archive}.sha256"

mkdir -p dist
rm -f "$archive" "$checksum"

# Build and inspect with the standard library so archive metadata and gzip
# headers are reproducible, and membership checks cannot trigger SIGPIPE under
# `set -o pipefail`.
ARCHIVE="$archive" python3 - <<'PY'
from __future__ import annotations

import gzip
import io
import os
from pathlib import Path, PurePosixPath
import tarfile

archive = Path(os.environ["ARCHIVE"])
roots = (
    ".agents",
    ".claude-plugin",
    ".codex-plugin",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "SECURITY.md",
    "assets",
    "docs",
    "skills",
)
required = {
    "skills/repo-review/SKILL.md",
    "skills/pr-review/SKILL.md",
    "docs/dependency-resolution.md",
}
secret_tokens = ("credential", "private-key", "private_key", "secret")
secret_names = {
    ".npmrc",
    ".pypirc",
    "id_ed25519",
    "id_rsa",
}
secret_suffixes = {".key", ".p12", ".pem", ".pfx"}


def forbidden_name(path: PurePosixPath) -> bool:
    """Return whether a portable archive member looks executable or sensitive."""
    lowered_parts = tuple(part.lower() for part in path.parts)
    lowered_name = path.name.lower()
    return (
        "__pycache__" in lowered_parts
        or path.suffix.lower() in {".py", ".pyc", ".pyo", ".pyw"}
        or lowered_name in secret_names
        or lowered_name == ".env"
        or lowered_name.startswith(".env.")
        or path.suffix.lower() in secret_suffixes
        or any(token in lowered_name for token in secret_tokens)
    )


def paths_to_archive() -> list[Path]:
    paths: list[Path] = []
    for root_name in roots:
        root = Path(root_name)
        if root.is_symlink():
            raise SystemExit(f"refusing forbidden archive input (symlink): {root}")
        if forbidden_name(PurePosixPath(root.as_posix())):
            raise SystemExit(f"refusing forbidden archive input (name): {root}")
        if not root.is_file() and not root.is_dir():
            raise SystemExit(f"refusing forbidden archive input (type): {root}")
        paths.append(root)
        if root.is_dir():
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise SystemExit(f"refusing forbidden archive input (symlink): {path}")
                if forbidden_name(PurePosixPath(path.as_posix())):
                    raise SystemExit(f"refusing forbidden archive input (name): {path}")
                if not path.is_file() and not path.is_dir():
                    raise SystemExit(f"refusing forbidden archive input (type): {path}")
                paths.append(path)
    return sorted(paths, key=lambda path: path.as_posix())


tar_buffer = io.BytesIO()
with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as output:
    for path in paths_to_archive():
        info = output.gettarinfo(str(path), arcname=path.as_posix())
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        info.gname = "root"
        info.mtime = 0
        info.pax_headers = {}
        info.mode = 0o755 if info.isdir() or (info.mode & 0o111) else 0o644
        if info.isfile():
            with path.open("rb") as source:
                output.addfile(info, source)
        else:
            output.addfile(info)

with archive.open("wb") as raw_output:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as output:
        output.write(tar_buffer.getvalue())

with tarfile.open(archive, mode="r:gz") as built:
    members = built.getmembers()
    names = [member.name for member in members]
    if len(names) != len(set(names)):
        raise SystemExit("archive contains duplicate members")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"archive contains unsafe path: {member.name}")
        if not path.parts or path.parts[0] not in roots:
            raise SystemExit(f"archive contains disallowed member: {member.name}")
        if forbidden_name(path):
            raise SystemExit(f"archive contains forbidden member: {member.name}")
        if member.issym() or member.islnk():
            raise SystemExit(f"archive contains link: {member.name}")
        if not member.isfile() and not member.isdir():
            raise SystemExit(f"archive contains special member: {member.name}")
    missing = sorted(required.difference(names))
    if missing:
        raise SystemExit(f"archive is missing required members: {', '.join(missing)}")
PY

python3 - "$archive" "$checksum" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

archive = Path(sys.argv[1])
checksum = Path(sys.argv[2])
checksum.write_text(f"{sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
PY

printf 'Built %s and %s\n' "$archive" "$checksum"
