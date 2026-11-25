"""Tests for scripts/check_commit_message.py."""

import re
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import check_commit_message
from check_commit_message import check_subject

ROOT = Path(__file__).resolve().parents[2]


class CheckSubjectTest(unittest.TestCase):
    def test_accepts_conventional_subjects(self) -> None:
        for subject in (
            "feat: add a tool",
            "fix(some-tool): handle an empty input",
            "refactor(tool2)!: rename the --out flag",
        ):
            with self.subTest(subject=subject):
                self.assertEqual(check_subject(subject), [])

    def test_accepts_subjects_git_generates(self) -> None:
        for subject in (
            "Merge branch 'main' into topic",
            'Revert "feat: add a tool"',
            "fixup! feat: add a tool",
        ):
            with self.subTest(subject=subject):
                self.assertEqual(check_subject(subject), [])

    def test_rejects_malformed_subjects(self) -> None:
        for subject in (
            "add a tool",
            "feat:add a tool",
            "Feat: add a tool",
            "feat(Some Tool): add a tool",
            "feat(): add a tool",
            "feat: ",
        ):
            with self.subTest(subject=subject):
                self.assertNotEqual(check_subject(subject), [])

    def test_rejects_unlisted_type(self) -> None:
        self.assertNotEqual(check_subject("perf: speed up parsing"), [])

    def test_rejects_long_subject(self) -> None:
        subject = "chore: " + "x" * check_commit_message.MAX_LENGTH
        self.assertNotEqual(check_subject(subject), [])

    def test_accepts_dependabot_single_update_title(self) -> None:
        # Dependabot's prefix is set in .github/dependabot.yaml.
        title = "chore(deps): bump actions/checkout from 7.0.1 to 7.1.0"
        self.assertEqual(check_subject(title), [])


class MainTest(unittest.TestCase):
    def run_main(self, message: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "COMMIT_EDITMSG"
            path.write_text(message)
            with redirect_stderr(StringIO()):
                return check_commit_message.main([str(path)])

    def test_message_file_skips_comments_and_ignores_body(self) -> None:
        message = "# Please enter the commit message.\n\nfix: x\n\nAny body: Here.\n"
        self.assertEqual(self.run_main(message), 0)

    def test_message_file_with_bad_subject_fails(self) -> None:
        self.assertEqual(self.run_main("fixed things\n"), 1)

    def test_title_with_bad_subject_fails(self) -> None:
        with redirect_stderr(StringIO()):
            code = check_commit_message.main(["--title", "fixed things"])
        self.assertEqual(code, 1)


class DocumentationTest(unittest.TestCase):
    def test_contributing_lists_exactly_the_allowed_types(self) -> None:
        text = (ROOT / "CONTRIBUTING.md").read_text()
        documented = re.findall(r"^\| `([a-z]+)` \|", text, re.MULTILINE)
        self.assertCountEqual(documented, check_commit_message.TYPES)


if __name__ == "__main__":
    unittest.main()
