#!/usr/bin/env python3
"""Scan a Syft inventory with Grype and enforce Athena's vulnerability policy."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import subprocess
import sys
from typing import Sequence

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.policies.vulnerabilities import (  # noqa: E402
    VulnerabilityPolicyError,
    evaluate_report,
    load_exceptions,
    load_report,
)
from skills._cli import argument_parser  # noqa: E402


def scan(
    *,
    inventory: Path,
    config: Path,
    exceptions_path: Path,
    report_path: Path,
    grype: str,
) -> list[str]:
    """Run Grype, retain its full JSON report, and return blocking findings."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            grype,
            f"sbom:{inventory}",
            "--config",
            str(config),
            "--output",
            "json",
            "--file",
            str(report_path),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"Grype failed with exit status {result.returncode}")
    exceptions = load_exceptions(exceptions_path, today=date.today())
    return evaluate_report(load_report(report_path), exceptions)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("security/grype.yaml"))
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=Path("security/vulnerability-exceptions.yaml"),
    )
    parser.add_argument("--report", type=Path, default=Path("dist-internal/grype.json"))
    parser.add_argument("--grype", default="grype")
    arguments = parser.parse_args(argv)
    try:
        blocking = scan(
            inventory=arguments.inventory.resolve(),
            config=arguments.config.resolve(),
            exceptions_path=arguments.exceptions.resolve(),
            report_path=arguments.report.resolve(),
            grype=arguments.grype,
        )
    except VulnerabilityPolicyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if blocking:
        print("\n".join(blocking), file=sys.stderr)
        return 1
    print(f"Vulnerability policy passed; full report: {arguments.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
