"""Repository-toolchain security contracts."""

import re
import unittest
from pathlib import Path

import yaml


class ToolchainPolicyTests(unittest.TestCase):
    """Verify the repository-tooling interpreter contract."""

    def test_default_python_pin_is_a_remediated_supported_release(self) -> None:
        """Require the pinned interpreter to stay in the fixed 3.13 line."""
        root = Path(__file__).resolve().parents[2]
        parts = (
            (root / ".python-version").read_text(encoding="utf-8").strip().split(".")
        )

        self.assertEqual(3, len(parts))
        version = tuple(int(part) for part in parts)
        self.assertGreaterEqual(version, (3, 13, 15))
        self.assertLess(version, (3, 14, 0))

    def test_container_stages_use_the_pinned_python_version(self) -> None:
        """Require every CI image stage to use the pinned Python version."""
        root = Path(__file__).resolve().parents[2]
        version = (root / ".python-version").read_text(encoding="utf-8").strip()
        containerfile = (root / "ci" / "Containerfile").read_text(encoding="utf-8")
        stages = re.findall(
            r"^FROM python:(\d+\.\d+\.\d+)-slim@sha256:[0-9a-f]{64}",
            containerfile,
            re.MULTILINE,
        )

        self.assertEqual(3, len(stages))
        self.assertTrue(all(stage == version for stage in stages))

    def test_builder_copies_python_pin_before_environment_install(self) -> None:
        """Require the builder to copy the Python pin before environment setup."""
        root = Path(__file__).resolve().parents[2]
        containerfile = (root / "ci" / "Containerfile").read_text(encoding="utf-8")
        environment_install = containerfile.index("RUN uv sync --locked")
        builder_prefix = containerfile[:environment_install]
        copied_files = re.findall(r"^COPY (.+) \./$", builder_prefix, re.MULTILINE)

        self.assertTrue(
            any(
                ".python-version" in copy_command.split()
                for copy_command in copied_files
            )
        )

    def test_workflow_jobs_provision_the_pinned_python_before_uv_sync(self) -> None:
        """Require host jobs to provision the repository Python pin."""
        root = Path(__file__).resolve().parents[2]
        workflow = yaml.safe_load(
            (root / ".github" / "workflows" / "_required.yml").read_text(
                encoding="utf-8"
            )
        )

        for job_name in ("package", "security-dependency-scan"):
            with self.subTest(job=job_name):
                steps = workflow["jobs"][job_name]["steps"]
                setup_python = [
                    (index, step)
                    for index, step in enumerate(steps)
                    if step.get("uses", "").startswith("actions/setup-python@")
                ]
                uv_sync_index = next(
                    index
                    for index, step in enumerate(steps)
                    if step.get("run") == "uv sync --locked"
                )

                self.assertEqual(1, len(setup_python))
                setup_index, setup_step = setup_python[0]
                self.assertLess(setup_index, uv_sync_index)
                self.assertRegex(
                    setup_step["uses"], r"^actions/setup-python@[0-9a-f]{40}$"
                )
                self.assertEqual(
                    {"python-version-file": ".python-version"}, setup_step["with"]
                )


if __name__ == "__main__":
    unittest.main()
