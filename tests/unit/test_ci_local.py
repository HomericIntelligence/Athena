"""Behavior tests for the local CI container orchestrator."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_CI_LOCAL = ROOT / "scripts/run_ci_local.sh"


class LocalCiOrchestratorTests(unittest.TestCase):
    @staticmethod
    def _write_executable(path: Path, body: str) -> Path:
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)
        return path

    @staticmethod
    def _run_local_ci(
        environment: dict[str, str], *args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(RUN_CI_LOCAL), *args],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _dirname_target() -> Path:
        dirname = shutil.which("dirname")
        if dirname is None:
            raise RuntimeError("The dirname command is unavailable.")
        return Path(dirname)

    def _create_temp_bin(self, temporary: Path) -> Path:
        bin_directory = temporary / "bin"
        bin_directory.mkdir()
        (bin_directory / "dirname").symlink_to(self._dirname_target())
        return bin_directory

    def _install_fake_engine(self, bin_directory: Path, *names: str) -> Path:
        engine = self._write_executable(
            bin_directory / "fake-container-engine",
            (
                'printf "%s\\n" "$*" >> "$FAKE_LOG"\n'
                'case "$*" in\n'
                '  *"image exists athena-ci:local"*) exit 0 ;;\n'
                '  *"images -q athena-ci:local"*) exit 0 ;;\n'
                "  *) exit 0 ;;\n"
                "esac\n"
            ),
        )
        for name in names:
            (bin_directory / name).symlink_to(engine)
        return engine

    def _install_failing_image_engine(self, bin_directory: Path) -> Path:
        return self._write_executable(
            bin_directory / "fake-container-engine",
            (
                'case "$*" in\n'
                '  *image*) exit 1 ;;\n'
                "  *) exit 0 ;;\n"
                "esac\n"
            ),
        )

    def _assert_log_contains(self, log_text: str, fragments: tuple[str, ...]) -> None:
        log_lines = log_text.splitlines()
        for fragment in fragments:
            self.assertTrue(
                any(fragment in line for line in log_lines),
                fragment,
            )

    def test_prefers_podman_when_both_engines_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            log_path = temporary / "engine.log"
            self._install_fake_engine(bin_directory, "podman", "docker")
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            environment["FAKE_LOG"] = str(log_path)

            result = self._run_local_ci(environment, "validate")
            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode)
        self.assertIn(
            "The script selected Podman as the rootless container engine.",
            result.stdout,
        )
        self.assertIn("All selected local CI checks passed.", result.stdout)
        self.assertEqual("", result.stderr)
        self.assertIn("The command uses this local CI image", result.stdout)
        self.assertIn("image exists athena-ci:local", log_text)
        self.assertIn("run --rm", log_text)

    def test_falls_back_to_docker_when_podman_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            log_path = temporary / "engine.log"
            self._install_fake_engine(bin_directory, "docker")
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            environment["FAKE_LOG"] = str(log_path)

            result = self._run_local_ci(environment, "validate")
            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode)
        self.assertIn(
            "The script selected Docker as the container engine.",
            result.stdout,
        )
        self.assertIn("All selected local CI checks passed.", result.stdout)
        self.assertEqual("", result.stderr)
        self.assertIn("The command uses this local CI image", result.stdout)
        self.assertIn("image exists athena-ci:local", log_text)
        self.assertIn("run --rm", log_text)

    def test_reports_missing_selected_engine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            environment["CONTAINER_ENGINE"] = str(temporary / "missing-engine")

            result = self._run_local_ci(environment, "validate")

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "The script cannot find the selected executable",
            result.stderr,
        )

    def test_reports_when_no_container_engine_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)

            result = self._run_local_ci(environment, "validate")

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "The command cannot find Podman or Docker. Install a container engine.",
            result.stderr,
        )

    def test_reports_image_resolution_failure_before_any_container_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            engine = self._install_failing_image_engine(bin_directory)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            environment["CONTAINER_ENGINE"] = str(engine)

            result = self._run_local_ci(environment, "validate")

        self.assertEqual(1, result.returncode)
        self.assertIn("just ci-build", result.stderr)
        self.assertNotIn("All selected local CI checks passed.", result.stdout)

    def test_dispatches_supported_subsets_to_expected_container_commands(self) -> None:
        cases: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
            (
                ("validate",),
                ("uv run python scripts/validate_skills.py",),
            ),
            (
                ("test",),
                (
                    "uv run coverage erase",
                    "coverage_policy.py coverage.json --minimum 80",
                    "uv run coverage report --show-missing",
                ),
            ),
            (
                ("static",),
                (
                    "uv run ruff check scripts tests skills",
                    "uv run ruff format --check scripts tests skills",
                    "uv run mypy --strict --explicit-package-bases scripts tests",
                    "skills/_cli.py",
                ),
            ),
            (
                ("markdownlint",),
                (
                    "uv run pymarkdown -d MD013,MD024,MD033,MD041,MD046 scan README.md AGENTS.md CLAUDE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md .github docs skills",
                ),
            ),
            (
                ("workflow",),
                (
                    "uv run yamllint .github/workflows",
                    "uv run check-jsonschema --builtin-schema vendor.github-workflows",
                    ".github/workflows",
                ),
            ),
            (
                (),
                (
                    "uv run python scripts/validate_skills.py",
                    "uv run coverage erase",
                    "coverage_policy.py coverage.json --minimum 80",
                    "uv run ruff check scripts tests skills",
                    "uv run ruff format --check scripts tests skills",
                    "uv run mypy --strict --explicit-package-bases scripts tests",
                    "uv run pymarkdown -d MD013,MD024,MD033,MD041,MD046 scan README.md AGENTS.md CLAUDE.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md .github docs skills",
                    "uv run yamllint .github/workflows",
                    "uv run check-jsonschema --builtin-schema vendor.github-workflows",
                    "uv run python scripts/ci_policy.py uv-pins",
                ),
            ),
        )

        for subset, fragments in cases:
            with (
                self.subTest(subset="default" if not subset else subset[0]),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                bin_directory = self._create_temp_bin(temporary)
                log_path = temporary / "engine.log"
                self._install_fake_engine(bin_directory, "podman")
                environment = os.environ.copy()
                environment["PATH"] = str(bin_directory)
                environment["FAKE_LOG"] = str(log_path)

                result = self._run_local_ci(environment, *subset)
                log_text = log_path.read_text(encoding="utf-8")

            self.assertEqual(0, result.returncode)
            self.assertIn("All selected local CI checks passed.", result.stdout)
            self.assertEqual("", result.stderr)
            self.assertIn("The script selected Podman as the rootless container engine.", result.stdout)
            self.assertIn("The command uses this local CI image", result.stdout)
            self._assert_log_contains(log_text, fragments)
            self.assertTrue(
                any(
                    "--volume" in line and "/workspace" in line and "run" in line
                    for line in log_text.splitlines()
                ),
                log_text,
            )

    def test_rejects_unknown_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            bin_directory = self._create_temp_bin(temporary)
            log_path = temporary / "engine.log"
            self._install_fake_engine(bin_directory, "podman")
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            environment["FAKE_LOG"] = str(log_path)

            result = self._run_local_ci(environment, "bogus")

        self.assertEqual(1, result.returncode)
        self.assertIn("The subset is not valid: 'bogus'.", result.stderr)
        self.assertIn(
            "all, validate, test, static, markdownlint, workflow, uv-pins",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
