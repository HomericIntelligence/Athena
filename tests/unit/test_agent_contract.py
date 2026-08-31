"""Behavior tests for the reusable root agent contract."""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import validate_agent_contract as agent_contract_cli
from scripts.policies import agent_contract

ROOT = Path(__file__).resolve().parents[2]


class AgentContractTests(unittest.TestCase):
    """Verify the catalog-derived root document contract."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.fixture = Path(self.temporary_directory.name) / "repository"
        self.fixture.mkdir()
        shutil.copy2(ROOT / "AGENTS.md", self.fixture / "AGENTS.md")
        shutil.copy2(ROOT / "CLAUDE.md", self.fixture / "CLAUDE.md")
        shutil.copytree(
            ROOT / "docs" / "principles", self.fixture / "docs" / "principles"
        )

    def assert_contract_error(self, literal: str) -> None:
        errors = agent_contract.validate_agent_contract(self.fixture)
        self.assertTrue(
            any(literal in error.reason for error in errors),
            errors,
        )

    def _replace_generated_block(self, replacement: str) -> None:
        path = self.fixture / "AGENTS.md"
        text = path.read_text(encoding="utf-8")
        start = text.index(agent_contract.AGENTS_START_MARKER)
        end = text.index(agent_contract.AGENTS_END_MARKER) + len(
            agent_contract.AGENTS_END_MARKER
        )
        path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

    def test_catalog_rejects_each_identity_and_structure_failure(self) -> None:
        def duplicate_identifier(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("### P002", "### P001", 1),
                encoding="utf-8",
            )

        def missing_identifier(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("### P002", "### P092", 1),
                encoding="utf-8",
            )

        def extra_identifier(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8")
                + "\n### P092\n\n[Extra](details/p092-extra.md) — Extra rule.\n",
                encoding="utf-8",
            )
            (path.parent / "details" / "p092-extra.md").write_text(
                "# Extra\n", encoding="utf-8"
            )

        def duplicate_detail_link(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "details/p002-yagni.md", "details/p001-kiss.md", 1
                ),
                encoding="utf-8",
            )

        def missing_detail_file(root: Path) -> None:
            (root / "docs" / "principles" / "details" / "p001-kiss.md").unlink()

        def invalid_structure(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "](details/p001-kiss.md) — ", "](details/p001-kiss.md): ", 1
                ),
                encoding="utf-8",
            )

        def malformed_identifier(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("### P001", "### P01", 1),
                encoding="utf-8",
            )

        def mismatched_detail(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "details/p002-yagni.md", "details/p003-yagni.md", 1
                ),
                encoding="utf-8",
            )
            (path.parent / "details" / "p003-yagni.md").write_text(
                "# YAGNI\n", encoding="utf-8"
            )

        def nonsequential_projection(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("### P002", "### P092", 1).replace(
                    "details/p002-yagni.md", "details/p092-yagni.md", 1
                ),
                encoding="utf-8",
            )
            (path.parent / "details" / "p092-yagni.md").write_text(
                "# YAGNI\n", encoding="utf-8"
            )

        cases: tuple[tuple[str, Callable[[Path], None], str], ...] = (
            (
                "duplicate identifier",
                duplicate_identifier,
                "duplicate principle identifier",
            ),
            ("missing identifier", missing_identifier, "missing principle identifier"),
            ("extra identifier", extra_identifier, "unexpected principle identifier"),
            ("duplicate detail link", duplicate_detail_link, "duplicate detail link"),
            ("missing detail file", missing_detail_file, "detail file is missing"),
            (
                "invalid catalog structure",
                invalid_structure,
                "required catalog structure",
            ),
            ("malformed identifier", malformed_identifier, "catalog structure"),
            ("mismatched detail", mismatched_detail, "does not match"),
            (
                "nonsequential identifier projection",
                nonsequential_projection,
                "P001 through P091 in order",
            ),
        )
        for name, mutate, expected in cases:
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory) / "repository"
                shutil.copytree(self.fixture, root)
                mutate(root)
                errors = agent_contract.validate_agent_contract(root)
                self.assertTrue(
                    any(expected in error.reason for error in errors),
                    errors,
                )

    def test_catalog_rejects_ambiguous_markdown_and_unsafe_text(self) -> None:
        def fenced_catalog(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("### P001", "```markdown\n### P001", 1),
                encoding="utf-8",
            )

        def second_paragraph(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace(
                    "obeys all requirements that evidence shows are necessary.\n\n### P002",
                    "obeys all requirements that evidence shows are necessary.\n"
                    "   \nSecond paragraph.\n\n### P002",
                    1,
                ),
                encoding="utf-8",
            )

        def bidirectional_control(root: Path) -> None:
            path = root / "docs" / "principles" / "README.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("minimum complexity", "minimum \u202ecomplexity", 1),
                encoding="utf-8",
            )

        for name, mutate in (
            ("unterminated fenced catalog", fenced_catalog),
            ("second paragraph", second_paragraph),
            ("bidirectional control", bidirectional_control),
        ):
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory) / "repository"
                shutil.copytree(self.fixture, root)
                mutate(root)

                _, errors = agent_contract.parse_principles_catalog(root)

                self.assertTrue(errors, name)

    def test_catalog_rejects_complete_principle_sections_in_the_wrong_order(
        self,
    ) -> None:
        path = self.fixture / "docs" / "principles" / "README.md"
        text = path.read_text(encoding="utf-8")
        first_start = text.index("### P001\n")
        second_start = text.index("### P002\n")
        third_start = text.index("### P003\n")
        first_section = text[first_start:second_start]
        second_section = text[second_start:third_start]
        path.write_text(
            text[:first_start] + second_section + first_section + text[third_start:],
            encoding="utf-8",
        )

        principles, errors = agent_contract.parse_principles_catalog(self.fixture)

        self.assertEqual(["P002", "P001"], [item.identifier for item in principles[:2]])
        self.assertTrue(
            any("P001 through P091 in order" in error.reason for error in errors),
            errors,
        )

    def test_catalog_normalizes_only_soft_line_wraps(self) -> None:
        path = self.fixture / "docs" / "principles" / "README.md"
        original = path.read_text(encoding="utf-8")
        path.write_text(
            original.replace(
                "minimum complexity that\nobeys",
                "minimum complexity that obeys",
                1,
            ),
            encoding="utf-8",
        )
        principles, errors = agent_contract.parse_principles_catalog(self.fixture)
        self.assertEqual([], errors)
        self._replace_generated_block(
            agent_contract.render_principles_block(principles)
        )
        self.assertEqual([], agent_contract.validate_agent_contract(self.fixture))

        for name, replacement in (
            ("repeated ASCII space", "minimum  complexity that\nobeys"),
            ("nonbreaking space", "minimum\u00a0complexity that\nobeys"),
            ("tab control", "minimum\tcomplexity that\nobeys"),
        ):
            with self.subTest(name=name):
                path.write_text(
                    original.replace("minimum complexity that\nobeys", replacement, 1),
                    encoding="utf-8",
                )
                self.assertTrue(
                    agent_contract.validate_agent_contract(self.fixture),
                    name,
                )

    def test_detail_paths_reject_symbolic_link_components(self) -> None:
        details = self.fixture / "docs" / "principles" / "details"
        real_details = details.with_name("real-details")
        details.rename(real_details)
        details.symlink_to(real_details, target_is_directory=True)

        _, errors = agent_contract.parse_principles_catalog(self.fixture)

        self.assertTrue(
            any("detail file" in error.reason for error in errors),
            errors,
        )

    def test_generated_block_rejects_each_row_failure(self) -> None:
        def mutate_rows(text: str, operation: str) -> str:
            start = text.index(agent_contract.AGENTS_START_MARKER)
            end = text.index(agent_contract.AGENTS_END_MARKER)
            before = text[: start + len(agent_contract.AGENTS_START_MARKER)]
            block = text[start + len(agent_contract.AGENTS_START_MARKER) : end]
            after = text[end:]
            rows = [line for line in block.splitlines() if line.startswith("- [P")]
            if operation == "missing" and rows:
                block = block.replace(f"\n{rows[0]}", "", 1)
            elif operation == "duplicate" and rows:
                block = block.replace(f"\n{rows[0]}", f"\n{rows[0]}\n{rows[0]}", 1)
            elif operation == "reordered" and len(rows) >= 2:
                block = block.replace(
                    f"\n{rows[0]}\n{rows[1]}", f"\n{rows[1]}\n{rows[0]}", 1
                )
            elif operation == "altered name" and rows:
                block = block.replace(
                    "KISS — Keep It Simple", "KISS — Keep  It Simple", 1
                )
            elif operation == "altered description" and rows:
                block = block.replace(rows[0], rows[0] + " altered", 1)
            elif operation == "altered punctuation" and rows:
                block = block.replace(") — Select", "): Select", 1)
            elif operation == "altered detail link" and rows:
                block = block.replace("blob/agent-contract-v1.0.0/", "blob/main/", 1)
            return before + block + after

        for operation in (
            "missing",
            "duplicate",
            "reordered",
            "altered name",
            "altered description",
            "altered punctuation",
            "altered detail link",
        ):
            with self.subTest(operation=operation):
                path = self.fixture / "AGENTS.md"
                original = path.read_text(encoding="utf-8")
                path.write_text(mutate_rows(original, operation), encoding="utf-8")
                self.assert_contract_error(
                    "generated development-principles block does not match"
                )
                path.write_text(original, encoding="utf-8")

    def test_generated_block_requires_standalone_markers_outside_fences(self) -> None:
        path = self.fixture / "AGENTS.md"
        original = path.read_text(encoding="utf-8")
        start = original.index(agent_contract.AGENTS_START_MARKER)
        end = original.index(agent_contract.AGENTS_END_MARKER) + len(
            agent_contract.AGENTS_END_MARKER
        )
        block = original[start:end]
        cases = {
            "backtick-fenced example": (
                original[:start] + "```markdown\n" + block + "\n```\n" + original[end:]
            ),
            "tilde-fenced example": (
                original[:start] + "~~~markdown\n" + block + "\n~~~\n" + original[end:]
            ),
            "start marker mid-line": original.replace(
                agent_contract.AGENTS_START_MARKER,
                f"Example: {agent_contract.AGENTS_START_MARKER}",
                1,
            ),
            "end marker mid-line": original.replace(
                agent_contract.AGENTS_END_MARKER,
                f"{agent_contract.AGENTS_END_MARKER} example",
                1,
            ),
            "duplicate start marker": original.replace(
                agent_contract.AGENTS_START_MARKER,
                f"{agent_contract.AGENTS_START_MARKER}\n"
                f"{agent_contract.AGENTS_START_MARKER}",
                1,
            ),
            "duplicate end marker": original.replace(
                agent_contract.AGENTS_END_MARKER,
                f"{agent_contract.AGENTS_END_MARKER}\n"
                f"{agent_contract.AGENTS_END_MARKER}",
                1,
            ),
            "duplicate full block": original[:end] + "\n" + block + original[end:],
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                path.write_text(text, encoding="utf-8")
                self.assert_contract_error(
                    "must contain one generated development-principles block"
                )
        path.write_text(original, encoding="utf-8")

    def test_renderer_uses_the_versioned_compact_sorted_contract(self) -> None:
        principles, errors = agent_contract.parse_principles_catalog(self.fixture)
        self.assertEqual([], errors)

        rendered = agent_contract.render_principles_block(tuple(reversed(principles)))
        lines = rendered.splitlines()

        self.assertEqual(
            "<!-- BEGIN ATHENA DEVELOPMENT PRINCIPLES: agent-contract-v1.0.0 -->",
            lines[0],
        )
        self.assertEqual(
            "<!-- END ATHENA DEVELOPMENT PRINCIPLES -->",
            lines[-1],
        )
        self.assertNotIn("\n\n", rendered)
        self.assertEqual(
            [f"P{number:03d}" for number in range(1, 92)],
            re.findall(r"^- \[(P[0-9]{3}) — ", rendered, re.MULTILINE),
        )

        nonsequential = principles[:-1] + (
            agent_contract.Principle(
                "P092", "Extra", "Extra decision rule.", "details/p092-extra.md"
            ),
        )
        with self.assertRaisesRegex(ValueError, "P001 through P091"):
            agent_contract.render_principles_block(nonsequential)

    def test_catalog_field_mutations_invalidate_and_rerender_the_mirror(self) -> None:
        catalog_path = self.fixture / "docs" / "principles" / "README.md"
        original_catalog = catalog_path.read_text(encoding="utf-8")
        mutations = {
            "name": ("[KISS — Keep It Simple, Stupid]", "[KISS — Simple First]"),
            "description": (
                "Select the design with minimum complexity",
                "Select a design with minimum complexity",
            ),
            "detail link": ("details/p001-kiss.md", "details/p001-simple.md"),
        }
        for name, (old, new) in mutations.items():
            with (
                self.subTest(field=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory) / "repository"
                shutil.copytree(self.fixture, root)
                path = root / "docs" / "principles" / "README.md"
                path.write_text(original_catalog.replace(old, new, 1), encoding="utf-8")
                if name == "detail link":
                    (
                        root / "docs" / "principles" / "details" / "p001-simple.md"
                    ).write_text("# Simple\n", encoding="utf-8")

                stale_errors = agent_contract.validate_agent_contract(root)
                self.assertTrue(
                    any("does not match" in error.reason for error in stale_errors),
                    stale_errors,
                )
                principles, catalog_errors = agent_contract.parse_principles_catalog(
                    root
                )
                self.assertEqual([], catalog_errors)
                agents_path = root / "AGENTS.md"
                agents = agents_path.read_text(encoding="utf-8")
                start = agents.index(agent_contract.AGENTS_START_MARKER)
                end = agents.index(agent_contract.AGENTS_END_MARKER) + len(
                    agent_contract.AGENTS_END_MARKER
                )
                rendered = agent_contract.render_principles_block(principles)
                agents_path.write_text(
                    agents[:start] + rendered + agents[end:], encoding="utf-8"
                )

                self.assertEqual([], agent_contract.validate_agent_contract(root))

    def test_claude_pointer_rejects_each_byte_difference(self) -> None:
        path = self.fixture / "CLAUDE.md"
        for value in (
            b"@AGENTS.md",
            b"@AGENTS.md\r\n",
            b"\xef\xbb\xbf@AGENTS.md\n",
            b" @AGENTS.md\n",
            b"@AGENTS.md\n\n",
        ):
            with self.subTest(value=value):
                path.write_bytes(value)
                self.assert_contract_error("bytes must equal '@AGENTS.md\\n'")

    def test_root_documents_are_bounded_regular_utf8_files(self) -> None:
        for filename in ("AGENTS.md", "CLAUDE.md"):
            for operation, expected in (
                ("invalid UTF-8", "readable UTF-8"),
                ("oversized", "exceeds"),
                ("symbolic link", "regular file"),
                ("missing", "missing or unreadable"),
            ):
                with (
                    self.subTest(filename=filename, operation=operation),
                    tempfile.TemporaryDirectory() as temporary_directory,
                ):
                    root = Path(temporary_directory) / "repository"
                    shutil.copytree(self.fixture, root)
                    path = root / filename
                    if operation == "invalid UTF-8":
                        path.write_bytes(b"\xff")
                    elif operation == "oversized":
                        path.write_bytes(
                            b"x" * (agent_contract.MAX_ROOT_DOCUMENT_BYTES + 1)
                        )
                    elif operation == "symbolic link":
                        target = root / (
                            "CLAUDE.md" if filename == "AGENTS.md" else "AGENTS.md"
                        )
                        path.unlink()
                        path.symlink_to(target)
                    else:
                        path.unlink()

                    errors = agent_contract.validate_agent_contract(root)

                    self.assertTrue(
                        any(expected in error.reason for error in errors),
                        errors,
                    )

    def test_generated_rows_have_the_complete_sorted_identifier_set(self) -> None:
        text = (self.fixture / "AGENTS.md").read_text(encoding="utf-8")
        start = text.index(agent_contract.AGENTS_START_MARKER)
        end = text.index(agent_contract.AGENTS_END_MARKER)
        identifiers = re.findall(r"^- \[(P[0-9]{3}) — ", text[start:end], re.MULTILINE)

        self.assertEqual([f"P{number:03d}" for number in range(1, 92)], identifiers)
        principles, errors = agent_contract.parse_principles_catalog(self.fixture)
        self.assertEqual([], errors)
        self.assertEqual(
            agent_contract.render_principles_block(principles).encode("utf-8"),
            text[
                start : text.index(agent_contract.AGENTS_END_MARKER)
                + len(agent_contract.AGENTS_END_MARKER)
            ].encode("utf-8"),
        )

    def test_provider_catalog_validates_a_separate_caller_checkout(self) -> None:
        caller = Path(self.temporary_directory.name) / "caller"
        caller.mkdir()
        shutil.copy2(ROOT / "AGENTS.md", caller / "AGENTS.md")
        shutil.copy2(ROOT / "CLAUDE.md", caller / "CLAUDE.md")

        self.assertEqual(
            [],
            agent_contract.validate_agent_contract(caller, catalog_root=ROOT),
        )

        output = StringIO()
        with redirect_stdout(output):
            result = agent_contract_cli.main(
                ["--root", str(caller), "--catalog-root", str(ROOT)]
            )
        self.assertEqual(0, result)
        self.assertIn("passed", output.getvalue())

        (caller / "CLAUDE.md").write_bytes(b"@AGENTS.md")
        errors = StringIO()
        with redirect_stderr(errors):
            result = agent_contract_cli.main(
                ["--root", str(caller), "--catalog-root", str(ROOT)]
            )
        self.assertEqual(1, result)
        self.assertIn("CLAUDE.md", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
