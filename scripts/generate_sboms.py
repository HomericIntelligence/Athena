#!/usr/bin/env python3
"""Generate deterministic SPDX SBOMs for Athena's plugin and build environment."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
from typing import Any, Final, Sequence

import yaml

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.package_plugin import read_plugin_version  # noqa: E402
from skills._cli import argument_parser  # noqa: E402


SPDX_VERSION: Final = "SPDX-2.3"
REPOSITORY: Final = "https://github.com/HomericIntelligence/Athena"
EXTERNAL_DEPENDENCIES: Final = (
    ("python", "external-command"),
    ("git", "external-command"),
    ("gh", "external-command"),
    ("Mnemosyne", "dynamic-repository"),
    ("Hephaestus", "dynamic-repository"),
)
ACTION_REFERENCE = re.compile(r"^(?P<name>[^@\s]+)@(?P<sha>[0-9a-f]{40})$")


class SbomError(RuntimeError):
    """Raised when SBOM content cannot satisfy Athena's release contract."""


def _spdx_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"SPDXRef-{prefix}-{digest}"


def _checksum_file(path: Path) -> Path:
    checksum = path.with_name(f"{path.name}.sha256")
    checksum.write_text(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n", encoding="utf-8"
    )
    return checksum


def _run_syft(syft: str, source: Path, output_format: str) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["SYFT_FILE_METADATA_SELECTION"] = "all"
    result = subprocess.run(
        [syft, "scan", str(source), "-o", output_format],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise OSError(f"Syft failed while scanning {source}: {detail}")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise OSError(f"Syft returned invalid {output_format}: {error}") from error
    if not isinstance(document, dict):
        raise OSError(f"Syft returned a non-object {output_format} document")
    return document


def _canonicalize(value: Any, source_root: Path) -> Any:
    """Remove scanner volatility and return recursively ordered JSON values."""
    if isinstance(value, dict):
        ignored = {"annotations", "documentDescribes"}
        return {
            key: _canonicalize(item, source_root)
            for key, item in sorted(value.items())
            if key not in ignored
        }
    if isinstance(value, list):
        normalized = [_canonicalize(item, source_root) for item in value]
        if all(isinstance(item, dict) for item in normalized):
            return sorted(
                normalized,
                key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":")
                ),
            )
        return normalized
    if isinstance(value, str):
        return value.replace(str(source_root.resolve()), ".")
    return value


def _base_document(
    raw: dict[str, Any], *, name: str, identity: str, epoch: int, source_root: Path
) -> dict[str, Any]:
    document = _canonicalize(raw, source_root)
    if not isinstance(document, dict):
        raise SbomError("normalized SPDX document is not an object")
    document["spdxVersion"] = SPDX_VERSION
    document["dataLicense"] = "CC0-1.0"
    document["SPDXID"] = "SPDXRef-DOCUMENT"
    document["name"] = name
    document["documentNamespace"] = (
        f"{REPOSITORY}/sbom/{name}/{sha256(identity.encode('utf-8')).hexdigest()}"
    )
    creation = document.get("creationInfo")
    if not isinstance(creation, dict):
        creation = {}
    creators = creation.get("creators", [])
    if not isinstance(creators, list):
        creators = []
    stable_creators = sorted(
        {
            str(creator)
            for creator in creators
            if not str(creator).startswith("Tool: syft-")
        }
    )
    stable_creators.append("Tool: Athena SBOM generator")
    creation["creators"] = stable_creators
    creation["created"] = datetime.fromtimestamp(epoch, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    document["creationInfo"] = creation
    return document


def _package(name: str, kind: str, *, version: str = "dynamic") -> dict[str, Any]:
    return {
        "SPDXID": _spdx_id("Package", f"{kind}:{name}:{version}"),
        "name": name,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "supplier": "NOASSERTION",
        "comment": f"Athena dependency scope: {kind}",
    }


def _archive_files(archive_path: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                raise SbomError(f"cannot read archive member {member.name}")
            content = source.read()
            name = PurePosixPath(member.name).as_posix()
            files.append(
                {
                    "SPDXID": _spdx_id("File", name),
                    "fileName": f"./{name}",
                    "checksums": [
                        {
                            "algorithm": "SHA1",
                            "checksumValue": sha1(content).hexdigest(),
                        },
                        {
                            "algorithm": "SHA256",
                            "checksumValue": sha256(content).hexdigest(),
                        },
                    ],
                    "licenseConcluded": "NOASSERTION",
                    "licenseInfoInFiles": ["NOASSERTION"],
                    "copyrightText": "NOASSERTION",
                }
            )
    if not files:
        raise SbomError("plugin archive contains no regular files")
    return files


def plugin_spdx(
    raw: dict[str, Any], archive_path: Path, version: str, epoch: int
) -> dict[str, Any]:
    """Build the release plugin SPDX document from Syft results and archive bytes."""
    archive_digest = sha256(archive_path.read_bytes()).hexdigest()
    name = f"athena-plugin-{version}"
    document = _base_document(
        raw,
        name=name,
        identity=f"{name}:{archive_digest}",
        epoch=epoch,
        source_root=archive_path,
    )
    root = _package("athena-plugin", "release-artifact", version=version)
    files = _archive_files(archive_path)
    file_sha1s = sorted(
        checksum["checksumValue"]
        for file_entry in files
        for checksum in file_entry["checksums"]
        if checksum["algorithm"] == "SHA1"
    )
    root["filesAnalyzed"] = True
    root["packageVerificationCode"] = {
        "packageVerificationCodeValue": sha1("".join(file_sha1s).encode()).hexdigest()
    }
    dependencies = [_package(name, kind) for name, kind in EXTERNAL_DEPENDENCIES]
    document["packages"] = sorted(
        [root, *dependencies], key=lambda package: str(package["SPDXID"])
    )
    document["files"] = files
    document["documentDescribes"] = [root["SPDXID"]]
    document["relationships"] = sorted(
        [
            {
                "spdxElementId": root["SPDXID"],
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_entry["SPDXID"],
            }
            for file_entry in files
        ]
        + [
            {
                "spdxElementId": root["SPDXID"],
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency["SPDXID"],
            }
            for dependency in dependencies
        ],
        key=lambda relation: json.dumps(relation, sort_keys=True),
    )
    return document


def _workflow_actions(workflow_path: Path) -> list[dict[str, Any]]:
    try:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise SbomError(
            f"cannot read workflow actions from {workflow_path}: {error}"
        ) from error
    if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
        raise SbomError(f"workflow has no jobs mapping: {workflow_path}")
    references: set[tuple[str, str]] = set()
    for job in workflow["jobs"].values():
        if not isinstance(job, dict) or not isinstance(job.get("steps"), list):
            continue
        for step in job["steps"]:
            if not isinstance(step, dict) or not isinstance(step.get("uses"), str):
                continue
            match = ACTION_REFERENCE.fullmatch(step["uses"])
            if match is None:
                raise SbomError(
                    f"workflow action is not pinned to a commit: {step['uses']}"
                )
            references.add((match.group("name"), match.group("sha")))
    return [
        _package(name, "github-action", version=sha) for name, sha in sorted(references)
    ]


def build_spdx(
    raw: dict[str, Any], environment_path: Path, workflow_path: Path, epoch: int
) -> dict[str, Any]:
    """Normalize Syft's environment SPDX and add CI build dependencies."""
    name = "athena-build-linux-64"
    document = _base_document(
        raw,
        name=name,
        identity=name,
        epoch=epoch,
        source_root=environment_path,
    )
    packages = document.get("packages", [])
    if not isinstance(packages, list):
        raise SbomError("Syft SPDX packages field is not a list")
    root = _package("athena-build-linux-64", "build-environment")
    additions = [_package("pixi", "build-tool"), *_workflow_actions(workflow_path)]
    all_packages = [root, *packages, *additions]
    document["packages"] = sorted(
        all_packages, key=lambda package: str(package.get("SPDXID", ""))
    )
    document["documentDescribes"] = [root["SPDXID"]]
    relationships = list(
        {
            "spdxElementId": root["SPDXID"],
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": package["SPDXID"],
        }
        for package in [*packages, *additions]
        if isinstance(package, dict) and isinstance(package.get("SPDXID"), str)
    )
    document["relationships"] = sorted(
        relationships, key=lambda relation: json.dumps(relation, sort_keys=True)
    )
    stable_inventory = {
        "packages": document["packages"],
        "files": document.get("files", []),
    }
    inventory_digest = sha256(
        json.dumps(stable_inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    document["documentNamespace"] = f"{REPOSITORY}/sbom/{name}/{inventory_digest}"
    return document


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def generate(
    *,
    archive_path: Path,
    environment_path: Path,
    workflow_path: Path,
    output_directory: Path,
    native_output: Path,
    epoch: int,
    syft: str,
    repo_root: Path,
    platform_name: str,
) -> tuple[Path, Path]:
    """Generate both checksummed release SBOMs and the internal SCA inventory."""
    if platform_name != "linux":
        raise SbomError("authoritative build SBOM generation requires Linux")
    if epoch < 0:
        raise SbomError("source date epoch must be non-negative")
    version = read_plugin_version(repo_root)
    plugin_raw = _run_syft(syft, archive_path, "spdx-json")
    build_raw = _run_syft(syft, environment_path, "spdx-json")
    native = _run_syft(syft, environment_path, "json")
    plugin_path = output_directory / f"athena-plugin-{version}.spdx.json"
    build_path = output_directory / f"athena-build-linux-64-{version}.spdx.json"
    _write_json(plugin_path, plugin_spdx(plugin_raw, archive_path, version, epoch))
    _write_json(
        build_path, build_spdx(build_raw, environment_path, workflow_path, epoch)
    )
    _write_json(native_output, native)
    _checksum_file(plugin_path)
    _checksum_file(build_path)
    return plugin_path, build_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--environment", type=Path, default=Path(".pixi/envs/default"))
    parser.add_argument(
        "--workflow", type=Path, default=Path(".github/workflows/_required.yml")
    )
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument(
        "--native-output",
        type=Path,
        default=Path("dist-internal/syft-environment.json"),
    )
    parser.add_argument("--source-date-epoch", type=int)
    parser.add_argument("--syft", default="syft")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args(argv)
    try:
        root = arguments.root.resolve()
        archive = arguments.archive
        if archive is None:
            candidates = sorted((root / "dist").glob("athena-plugin-*.tar.gz"))
            if len(candidates) != 1:
                raise SbomError("dist must contain exactly one plugin archive")
            archive = candidates[0]
        epoch = arguments.source_date_epoch
        if epoch is None:
            timestamp = subprocess.run(
                ["git", "show", "-s", "--format=%ct", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            epoch = int(timestamp)
        generated = generate(
            archive_path=archive.resolve(),
            environment_path=arguments.environment.resolve(),
            workflow_path=arguments.workflow.resolve(),
            output_directory=arguments.output.resolve(),
            native_output=arguments.native_output.resolve(),
            epoch=epoch,
            syft=arguments.syft,
            repo_root=root,
            platform_name=sys.platform,
        )
    except SbomError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, tarfile.TarError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("Generated " + " and ".join(str(path) for path in generated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
