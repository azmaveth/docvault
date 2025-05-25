"""Tests for backup and restore CLI commands."""

import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docvault.main import cli


class TestBackupCommand:
    """Test the backup command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ProjectManager."""
        with patch("docvault.cli.commands.ProjectManager") as mock:
            yield mock

    @pytest.fixture
    def temp_backup_dir(self, tmp_path):
        """Create a temporary backup directory."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        return backup_dir

    def test_backup_default_destination(
        self, cli_runner, mock_project_manager, temp_backup_dir
    ):
        """Test creating backup with default destination."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        with patch("docvault.cli.commands.Path.cwd", return_value=temp_backup_dir):
            with patch("tarfile.open") as mock_tar:
                mock_tar_obj = MagicMock()
                mock_tar.__enter__.return_value = mock_tar_obj

                result = cli_runner.invoke(cli, ["backup"])

                assert result.exit_code == 0
                assert "Backup created successfully" in result.output
                assert "docvault_backup_" in result.output
                mock_tar_obj.add.assert_called_with(
                    mock_pm.docvault_dir, arcname="docvault"
                )

    def test_backup_custom_destination(
        self, cli_runner, mock_project_manager, temp_backup_dir
    ):
        """Test creating backup with custom destination."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        custom_path = temp_backup_dir / "custom_backup.tar.gz"

        with patch("tarfile.open") as mock_tar:
            mock_tar_obj = MagicMock()
            mock_tar.__enter__.return_value = mock_tar_obj

            result = cli_runner.invoke(cli, ["backup", str(custom_path)])

            assert result.exit_code == 0
            assert "Backup created successfully" in result.output
            assert str(custom_path) in result.output
            mock_tar.assert_called_with(str(custom_path), "w:gz")

    def test_backup_docvault_not_exists(self, cli_runner, mock_project_manager):
        """Test backup when docvault directory doesn't exist."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = False
        mock_project_manager.return_value = mock_pm

        result = cli_runner.invoke(cli, ["backup"])

        assert result.exit_code == 1
        assert "DocVault directory not found" in result.output

    def test_backup_error_handling(self, cli_runner, mock_project_manager):
        """Test backup error handling."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        with patch("tarfile.open") as mock_tar:
            mock_tar.side_effect = Exception("Backup error")

            result = cli_runner.invoke(cli, ["backup"])

            assert result.exit_code == 1
            assert "Failed to create backup" in result.output
            assert "Backup error" in result.output


class TestImportBackupCommand:
    """Test the import-backup command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ProjectManager."""
        with patch("docvault.cli.commands.ProjectManager") as mock:
            yield mock

    @pytest.fixture
    def temp_backup_file(self, tmp_path):
        """Create a temporary backup file."""
        backup_file = tmp_path / "test_backup.tar.gz"

        # Create a mock tarfile
        with tarfile.open(backup_file, "w:gz") as tar:
            # Add a mock file
            info = tarfile.TarInfo(name="docvault/test.txt")
            info.size = 4
            tar.addfile(info, fileobj=None)

        return backup_file

    def test_import_backup_success(
        self, cli_runner, mock_project_manager, temp_backup_file
    ):
        """Test successful backup import."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = False
        mock_project_manager.return_value = mock_pm

        with patch("tarfile.open") as mock_tar:
            mock_tar_obj = MagicMock()
            mock_tar.__enter__.return_value = mock_tar_obj

            result = cli_runner.invoke(cli, ["import-backup", str(temp_backup_file)])

            assert result.exit_code == 0
            assert "Backup imported successfully" in result.output
            mock_tar_obj.extractall.assert_called_once()

    def test_import_backup_existing_data(
        self, cli_runner, mock_project_manager, temp_backup_file
    ):
        """Test importing backup when data already exists."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        result = cli_runner.invoke(cli, ["import-backup", str(temp_backup_file)])

        assert result.exit_code == 1
        assert "DocVault directory already exists" in result.output

    def test_import_backup_force(
        self, cli_runner, mock_project_manager, temp_backup_file
    ):
        """Test force importing backup."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        with patch("tarfile.open") as mock_tar:
            mock_tar_obj = MagicMock()
            mock_tar.__enter__.return_value = mock_tar_obj

            with patch("shutil.rmtree") as mock_rmtree:
                with patch("click.confirm", return_value=True):
                    result = cli_runner.invoke(
                        cli, ["import-backup", str(temp_backup_file), "--force"]
                    )

                    assert result.exit_code == 0
                    assert "Backup imported successfully" in result.output
                    mock_rmtree.assert_called_once_with(mock_pm.docvault_dir)

    def test_import_backup_force_abort(
        self, cli_runner, mock_project_manager, temp_backup_file
    ):
        """Test aborting force import."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = True
        mock_project_manager.return_value = mock_pm

        with patch("click.confirm", return_value=False):
            result = cli_runner.invoke(
                cli, ["import-backup", str(temp_backup_file), "--force"]
            )

            assert result.exit_code == 1

    def test_import_backup_file_not_found(self, cli_runner, mock_project_manager):
        """Test importing non-existent backup file."""
        mock_pm = MagicMock()
        mock_project_manager.return_value = mock_pm

        result = cli_runner.invoke(cli, ["import-backup", "/nonexistent/backup.tar.gz"])

        assert result.exit_code == 1
        assert "Backup file not found" in result.output

    def test_import_backup_invalid_format(
        self, cli_runner, mock_project_manager, tmp_path
    ):
        """Test importing invalid backup file."""
        mock_pm = MagicMock()
        mock_pm.docvault_dir = Path("/test/docvault")
        mock_pm.docvault_dir.exists.return_value = False
        mock_project_manager.return_value = mock_pm

        # Create invalid file
        invalid_file = tmp_path / "invalid.tar.gz"
        invalid_file.write_text("invalid content")

        with patch("tarfile.open") as mock_tar:
            mock_tar.side_effect = tarfile.ReadError("Invalid format")

            result = cli_runner.invoke(cli, ["import-backup", str(invalid_file)])

            assert result.exit_code == 1
            assert "Failed to extract backup" in result.output
