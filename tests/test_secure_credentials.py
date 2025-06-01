"""Tests for secure credential management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from docvault.utils.secure_credentials import (
    CredentialError,
    SecureCredentialManager,
    get_credential_from_env_or_store,
    get_github_token,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for test credentials."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def credential_manager(temp_config_dir):
    """Create a credential manager with temporary storage."""
    key_file = temp_config_dir / ".test_key"
    credentials_file = temp_config_dir / ".test_credentials"

    # Ensure clean state
    if key_file.exists():
        key_file.unlink()
    if credentials_file.exists():
        credentials_file.unlink()

    manager = SecureCredentialManager(key_file=key_file)
    # Override the credentials file path to use the temp directory
    manager.credentials_file = credentials_file
    return manager


class TestSecureCredentialManager:
    """Test secure credential storage and retrieval."""

    def test_store_and_retrieve_credential(self, credential_manager):
        """Test basic store and retrieve functionality."""
        # Store a credential
        credential_manager.store_credential("test_key", "test_value", "test_category")

        # Retrieve it
        value = credential_manager.get_credential("test_key", "test_category")
        assert value == "test_value"

    def test_credential_not_found(self, credential_manager):
        """Test retrieving non-existent credential."""
        value = credential_manager.get_credential("nonexistent", "test_category")
        assert value is None

    def test_remove_credential(self, credential_manager):
        """Test removing credentials."""
        # Store a credential
        credential_manager.store_credential("to_remove", "value", "test_category")

        # Verify it exists
        assert (
            credential_manager.get_credential("to_remove", "test_category") == "value"
        )

        # Remove it
        result = credential_manager.remove_credential("to_remove", "test_category")
        assert result is True

        # Verify it's gone
        assert credential_manager.get_credential("to_remove", "test_category") is None

        # Try to remove again (should return False)
        result = credential_manager.remove_credential("to_remove", "test_category")
        assert result is False

    def test_list_credentials(self, credential_manager):
        """Test listing credentials."""
        # Store multiple credentials
        credential_manager.store_credential("key1", "value1", "cat1")
        credential_manager.store_credential("key2", "value2", "cat1")
        credential_manager.store_credential("key3", "value3", "cat2")

        # List all
        all_creds = credential_manager.list_credentials()
        assert "cat1" in all_creds
        assert "cat2" in all_creds
        assert "key1" in all_creds["cat1"]
        assert "key2" in all_creds["cat1"]
        assert "key3" in all_creds["cat2"]

        # List by category
        cat1_creds = credential_manager.list_credentials("cat1")
        assert "cat1" in cat1_creds
        assert "cat2" not in cat1_creds

    def test_credential_encryption(self, temp_config_dir):
        """Test that credentials are actually encrypted on disk."""
        manager = SecureCredentialManager(key_file=temp_config_dir / ".key")
        # Set credentials file to temp directory
        manager.credentials_file = temp_config_dir / ".test_credentials_encrypt"

        # Store a credential with a known value
        secret_value = "super_secret_password_123"  # pragma: allowlist secret
        manager.store_credential("test", secret_value, "test")

        # Read the raw encrypted file
        encrypted_content = manager.credentials_file.read_bytes()

        # The secret value should NOT appear in the encrypted file
        assert secret_value.encode() not in encrypted_content
        assert b"super_secret" not in encrypted_content

    def test_key_rotation(self, credential_manager):
        """Test encryption key rotation."""
        # Store some credentials
        credential_manager.store_credential("key1", "value1", "cat1")
        credential_manager.store_credential("key2", "value2", "cat2")

        # Rotate the key
        result = credential_manager.rotate_key()
        assert result is True

        # Verify credentials are still accessible
        assert credential_manager.get_credential("key1", "cat1") == "value1"
        assert credential_manager.get_credential("key2", "cat2") == "value2"

    def test_key_rotation_failure_recovery(self, credential_manager, monkeypatch):
        """Test that key rotation recovers from failures."""
        # Store a credential
        credential_manager.store_credential("key1", "value1", "cat1")

        # Track calls to _save_credentials
        save_calls = []
        original_save = credential_manager._save_credentials

        def failing_save(creds):
            save_calls.append(creds)
            # Let the first call succeed (during key rotation)
            # but fail on any subsequent call
            if len(save_calls) == 1:
                # This is the call during rotation
                raise Exception("Simulated save failure")
            return original_save(creds)

        # Clear any existing cipher to ensure fresh state
        credential_manager._cipher = None

        monkeypatch.setattr(credential_manager, "_save_credentials", failing_save)

        # Attempt rotation (should fail and recover)
        with pytest.raises(CredentialError) as exc_info:
            credential_manager.rotate_key()

        assert "Key rotation failed" in str(exc_info.value)

        # Verify original credentials are still accessible
        assert credential_manager.get_credential("key1", "cat1") == "value1"

    def test_file_permissions(self, credential_manager):
        """Test that credential files have secure permissions."""
        if os.name == "nt":
            pytest.skip("File permission test not applicable on Windows")

        # Store a credential to create files
        credential_manager.store_credential("test", "value", "test")

        # Check key file permissions (should be 600)
        key_stat = credential_manager.key_file.stat()
        assert oct(key_stat.st_mode)[-3:] == "600"

        # Check credentials file permissions (should be 600)
        creds_stat = credential_manager.credentials_file.stat()
        assert oct(creds_stat.st_mode)[-3:] == "600"

    def test_different_categories(self, credential_manager):
        """Test that credentials in different categories are isolated."""
        # Store same key in different categories
        credential_manager.store_credential("api_key", "value1", "production")
        credential_manager.store_credential("api_key", "value2", "staging")

        # Retrieve and verify they're different
        assert credential_manager.get_credential("api_key", "production") == "value1"
        assert credential_manager.get_credential("api_key", "staging") == "value2"


class TestCredentialHelpers:
    """Test credential helper functions."""

    def test_get_credential_from_env(self, monkeypatch):
        """Test getting credential from environment variable."""
        monkeypatch.setenv("TEST_VAR", "env_value")

        value = get_credential_from_env_or_store("test_cred", "TEST_VAR", "test_cat")
        assert value == "env_value"

    def test_get_credential_from_store(self, temp_config_dir, monkeypatch):
        """Test getting credential from secure store."""
        # Ensure env var is not set
        monkeypatch.delenv("TEST_VAR", raising=False)

        # Store credential
        with patch("docvault.utils.secure_credentials.Path") as mock_path:
            mock_path.return_value = temp_config_dir / ".credentials.key"

            manager = SecureCredentialManager(key_file=temp_config_dir / ".key")
            manager.store_credential("test_cred", "stored_value", "test_cat")

            # Get credential (should come from store)
            with patch(
                "docvault.utils.secure_credentials.SecureCredentialManager"
            ) as mock_manager:
                mock_manager.return_value = manager

                value = get_credential_from_env_or_store(
                    "test_cred", "TEST_VAR", "test_cat"
                )
                assert value == "stored_value"

    def test_get_github_token_from_env(self, monkeypatch):
        """Test getting GitHub token from environment."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")

        # Should not prompt since env var is set
        token = get_github_token()
        assert token == "ghp_test_token"

    def test_special_characters_in_credentials(self, credential_manager):
        """Test storing credentials with special characters."""
        special_value = "p@$$w0rd!#$%^&*()_+-=[]{}|;':\",./<>?"

        credential_manager.store_credential("special", special_value, "test")
        retrieved = credential_manager.get_credential("special", "test")

        assert retrieved == special_value

    def test_unicode_in_credentials(self, credential_manager):
        """Test storing credentials with unicode characters."""
        unicode_value = "密码🔐 пароль パスワード"

        credential_manager.store_credential("unicode", unicode_value, "test")
        retrieved = credential_manager.get_credential("unicode", "test")

        assert retrieved == unicode_value

    def test_empty_credential_value(self, credential_manager):
        """Test behavior with empty credential values."""
        # Empty string should be stored
        credential_manager.store_credential("empty", "", "test")
        retrieved = credential_manager.get_credential("empty", "test")
        assert retrieved == ""

        # But it should show up in listings
        creds = credential_manager.list_credentials("test")
        assert "empty" in creds["test"]
