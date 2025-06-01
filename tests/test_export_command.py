"""Test the export command functionality."""

import json

import pytest
from click.testing import CliRunner

from docvault.cli.commands import export_cmd
from tests.utils import mock_app_initialization


class TestExportCommand:
    """Test the export command."""

    @pytest.fixture
    def sample_documents(self, test_db, temp_dir):
        """Create sample documents for testing."""
        from docvault.db.operations import add_document

        # Create storage directories
        html_dir = temp_dir / "html"
        markdown_dir = temp_dir / "markdown"
        html_dir.mkdir()
        markdown_dir.mkdir()

        doc_ids = []

        # Create test documents
        for i in range(1, 4):
            # Create files
            html_path = html_dir / f"doc{i}.html"
            markdown_path = markdown_dir / f"doc{i}.md"

            html_content = f"<h1>Document {i}</h1><p>Content {i}</p>"
            markdown_content = f"# Document {i}\n\nContent {i}"

            html_path.write_text(html_content)
            markdown_path.write_text(markdown_content)

            # Add to database
            doc_id = add_document(
                url=f"https://example.com/doc{i}",
                title=f"Test Document {i}",
                html_path=str(html_path),
                markdown_path=str(markdown_path),
            )
            doc_ids.append(doc_id)

        return doc_ids

    def test_export_single_document(self, sample_documents, tmp_path):
        """Test exporting a single document."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["1", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Successfully exported 1 files" in result.output

            # Check file was created
            exported_files = list(tmp_path.glob("*.md"))
            assert len(exported_files) == 1
            assert "1_Test_Document_1.md" in str(exported_files[0])

            # Check content
            content = exported_files[0].read_text()
            assert "# Document 1" in content
            assert "Content 1" in content

    def test_export_range(self, sample_documents, tmp_path):
        """Test exporting a range of documents."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["1-3", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Successfully exported 3 files" in result.output

            # Check files were created
            exported_files = list(tmp_path.glob("*.md"))
            assert len(exported_files) == 3

    def test_export_list(self, sample_documents, tmp_path):
        """Test exporting a list of documents."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["1,3", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Successfully exported 2 files" in result.output

            # Check files were created
            exported_files = list(tmp_path.glob("*.md"))
            assert len(exported_files) == 2

            filenames = [f.name for f in exported_files]
            assert any("Document_1" in f for f in filenames)
            assert any("Document_3" in f for f in filenames)
            assert not any("Document_2" in f for f in filenames)

    def test_export_all(self, sample_documents, tmp_path):
        """Test exporting all documents."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["all", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Successfully exported 3 files" in result.output

            # Check files were created
            exported_files = list(tmp_path.glob("*.md"))
            assert len(exported_files) == 3

    def test_export_json_format(self, sample_documents, tmp_path):
        """Test exporting in JSON format."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd, ["1", "--format", "json", "--output", str(tmp_path)]
            )

            assert result.exit_code == 0

            # Check JSON file was created
            exported_files = list(tmp_path.glob("*.json"))
            assert len(exported_files) == 1

            # Check JSON content
            with open(exported_files[0]) as f:
                data = json.load(f)
                assert data["content"] == "# Document 1\n\nContent 1"

    def test_export_with_metadata(self, sample_documents, tmp_path):
        """Test exporting with metadata."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd,
                ["1", "--include-metadata", "--output", str(tmp_path)],
            )

            assert result.exit_code == 0

            # Check metadata in markdown
            exported_files = list(tmp_path.glob("*.md"))
            content = exported_files[0].read_text()

            assert "---" in content
            assert "id: 1" in content
            assert "title: Test Document 1" in content
            assert "url: https://example.com/doc1" in content

    def test_export_single_file(self, sample_documents, tmp_path):
        """Test exporting multiple documents to a single file."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd,
                ["1-3", "--single-file", "--output", str(tmp_path)],
            )

            assert result.exit_code == 0
            assert "Successfully exported 1 files" in result.output

            # Check single file was created
            exported_files = list(tmp_path.glob("export.md"))
            assert len(exported_files) == 1

            # Check content includes all documents
            content = exported_files[0].read_text()
            assert "# Document 1" in content
            assert "# Document 2" in content
            assert "# Document 3" in content
            assert "=" * 80 in content  # Separator

    def test_export_html_format(self, sample_documents, tmp_path):
        """Test exporting in HTML format."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd, ["1", "--format", "html", "--output", str(tmp_path)]
            )

            assert result.exit_code == 0

            # Check HTML file was created
            exported_files = list(tmp_path.glob("*.html"))
            assert len(exported_files) == 1

            # Check content (should be converted from HTML)
            content = exported_files[0].read_text()
            assert "Document 1" in content

    def test_export_xml_format(self, sample_documents, tmp_path):
        """Test exporting in XML format."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd, ["1", "--format", "xml", "--output", str(tmp_path)]
            )

            assert result.exit_code == 0

            # Check XML file was created
            exported_files = list(tmp_path.glob("*.xml"))
            assert len(exported_files) == 1

            # Check XML structure
            content = exported_files[0].read_text()
            assert "<?xml version" in content
            assert "<document>" in content
            assert "<content>" in content

    def test_export_llms_format(self, sample_documents, tmp_path):
        """Test exporting in llms.txt format."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd, ["1-2", "--format", "llms", "--output", str(tmp_path)]
            )

            assert result.exit_code == 0

            # Check llms.txt files were created
            exported_files = list(tmp_path.glob("*.llms.txt"))
            assert len(exported_files) == 2

    def test_export_invalid_range(self):
        """Test exporting with invalid document range."""
        runner = CliRunner()

        result = runner.invoke(export_cmd, ["invalid-range"])

        assert result.exit_code == 1
        assert "Invalid document ID specification" in result.output

    def test_export_missing_documents(self, sample_documents, tmp_path):
        """Test exporting with some missing documents."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["1,99,3", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Warning:" in result.output
            assert "documents not found: [99]" in result.output
            assert "Successfully exported 2 files" in result.output

    def test_export_no_documents(self, mock_app_initialization):
        """Test exporting when no documents exist."""
        from unittest.mock import patch

        runner = CliRunner()

        # Mock list_documents to return empty list
        with patch("docvault.db.operations.list_documents", return_value=[]):
            result = runner.invoke(export_cmd, ["all"])

        assert result.exit_code == 1
        assert "No documents found in vault" in result.output

    def test_export_raw_content(self, sample_documents, tmp_path):
        """Test exporting raw content without rendering."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                export_cmd,
                ["1", "--format", "html", "--raw", "--output", str(tmp_path)],
            )

            assert result.exit_code == 0

            # Check raw HTML is preserved
            exported_files = list(tmp_path.glob("*.html"))
            content = exported_files[0].read_text()
            assert "<h1>Document 1</h1>" in content  # Raw HTML tags

    def test_export_complex_range(self, sample_documents, tmp_path):
        """Test exporting with complex range specification."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(export_cmd, ["1-2,3", "--output", str(tmp_path)])

            assert result.exit_code == 0
            assert "Successfully exported 3 files" in result.output
