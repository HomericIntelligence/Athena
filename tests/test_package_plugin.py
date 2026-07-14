"""Regression tests for the portable plugin archive builder."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


def copy_repository(destination: Path) -> Path:
    """Copy the working repository without VCS, build, or tool-cache state."""
    repository = destination / "repository"
    shutil.copytree(
        ROOT,
        repository,
        ignore=shutil.ignore_patterns(
            ".coverage",
            ".git",
            ".mypy_cache",
            ".pixi",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "*.pyc",
            "dist",
        ),
    )
    subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
    return repository


class PackagePluginTests(unittest.TestCase):
    def test_archive_inspection_does_not_sigpipe_tar(self) -> None:
        """A fast archive consumer must not make packaging fail under pipefail."""
        real_tar = shutil.which("tar")
        self.assertIsNotNone(real_tar)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = copy_repository(temporary_path)
            bin_dir = temporary_path / "bin"
            bin_dir.mkdir()
            fake_tar = bin_dir / "tar"
            fake_tar.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env python3
                    import os
                    import subprocess
                    import sys

                    if "-tzf" not in sys.argv:
                        raise SystemExit(subprocess.call([{real_tar!r}, *sys.argv[1:]]))

                    members = [
                        "skills/repo-review/SKILL.md",
                        "skills/pr-review/SKILL.md",
                        "docs/dependency-resolution.md",
                    ]
                    try:
                        for member in members:
                            print(member, flush=True)
                        for index in range(100_000):
                            print(f"skills/filler-{{index}}/SKILL.md", flush=True)
                    except BrokenPipeError:
                        os._exit(141)
                    """
                ),
                encoding="utf-8",
            )
            fake_tar.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", "scripts/package-plugin.sh"],
                cwd=repository,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_secret_like_python_artifact_is_rejected(self) -> None:
        """Archive roots must fail closed on code and credential artifacts."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = copy_repository(Path(temporary_directory))
            (repository / "docs" / "credentials.py").write_text(
                "placeholder fixture content\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["bash", "scripts/package-plugin.sh"],
                cwd=repository,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("refusing forbidden archive input", result.stderr)


if __name__ == "__main__":
    unittest.main()
