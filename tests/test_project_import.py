"""Tests for project dependency import functionality."""

import json
import os
import tempfile
from unittest import TestCase, mock

from click.testing import CliRunner

from docvault.cli.commands import import_deps_cmd
from docvault.project import ProjectManager


class TestProjectManager(TestCase):
    """Tests for the ProjectManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.requirements_txt = os.path.join(self.test_dir, "requirements.txt")
        self.package_json = os.path.join(self.test_dir, "package.json")

        # Create a test requirements.txt
        with open(self.requirements_txt, "w", encoding="utf-8") as f:
            f.write(
                """# Test requirements
requests>=2.25.0
pytest>=6.2.0
# This is a comment
beautifulsoup4==4.9.3
"""
            )

        # Create a test package.json
        with open(self.package_json, "w", encoding="utf-8") as f:
            f.write(
                """{
  "name": "test-project",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.17.1",
    "lodash": "4.17.21"
  },
  "devDependencies": {
    "jest": "^27.0.0"
  }
}"""
            )

    def test_parse_requirements_txt(self):
        """Test parsing requirements.txt file."""
        with open(self.requirements_txt, "r", encoding="utf-8") as f:
            content = f.read()

        deps = ProjectManager().parse_requirements_txt(content)
        self.assertEqual(len(deps), 3)
        self.assertEqual(deps[0]["name"], "requests")
        self.assertEqual(deps[1]["name"], "pytest")
        self.assertEqual(deps[2]["name"], "beautifulsoup4")

    def test_parse_package_json(self):
        """Test parsing package.json file."""
        with open(self.package_json, "r", encoding="utf-8") as f:
            content = f.read()

        deps = ProjectManager().parse_package_json(content)
        self.assertEqual(len(deps), 3)
        self.assertEqual(deps[0]["name"], "express")
        self.assertEqual(deps[1]["name"], "lodash")
        self.assertEqual(deps[2]["name"], "jest")

    def test_detect_project_type(self):
        """Test project type detection."""
        # Test with Python project
        self.assertEqual(ProjectManager.detect_project_type(self.test_dir), "python")

        # Test with Node.js project (after removing Python files)
        os.remove(self.requirements_txt)
        self.assertEqual(ProjectManager.detect_project_type(self.test_dir), "nodejs")

        # Test with unknown project
        os.remove(self.package_json)
        self.assertEqual(ProjectManager.detect_project_type(self.test_dir), "unknown")

    @mock.patch("docvault.project.ProjectManager.import_documentation")
    def test_import_deps_cmd(self, mock_import):
        """Test the import-deps CLI command."""
        # Mock the import_documentation method
        mock_import.return_value = {
            "success": [
                {"name": "requests", "version": "2.31.0", "source": "requirements.txt"},
                {"name": "pytest", "version": "7.4.0", "source": "requirements.txt"},
            ],
            "failed": [
                {
                    "name": "nonexistent",
                    "version": "1.0.0",
                    "reason": "Not found",
                    "source": "requirements.txt",
                }
            ],
            "skipped": [],
        }

        runner = CliRunner()
        result = runner.invoke(import_deps_cmd, [self.test_dir, "--format", "json"])

        self.assertEqual(result.exit_code, 0)

        # Parse the JSON output
        output = json.loads(result.output)
        self.assertEqual(len(output["success"]), 2)
        self.assertEqual(len(output["failed"]), 1)
        self.assertEqual(len(output["skipped"]), 0)

        # Verify the import_documentation was called with the correct arguments
        mock_import.assert_called_once()

        # Debug: Print the call arguments
        print("Call args:", mock_import.call_args)

        # Check that the test directory is in the call arguments
        call_args = mock_import.call_args[0] if mock_import.call_args[0] else ()
        call_kwargs = mock_import.call_args[1] if mock_import.call_args[1] else {}

        # The test directory should be the first positional argument
        self.assertTrue(
            any(
                self.test_dir in str(arg)
                for arg in call_args + tuple(call_kwargs.values())
            ),
            f"Test directory {self.test_dir} not found in call arguments",
        )

        # Check the keyword arguments
        self.assertIsNone(call_kwargs.get("project_type"))
        self.assertFalse(call_kwargs.get("include_dev", False))
        self.assertFalse(call_kwargs.get("force", False))

    def test_import_deps_cmd_nonexistent_path(self):
        """Test import-deps with a non-existent path."""
        runner = CliRunner()
        result = runner.invoke(import_deps_cmd, ["/nonexistent/path"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Error", result.output)

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.test_dir):
            for root, dirs, files in os.walk(self.test_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(self.test_dir)
