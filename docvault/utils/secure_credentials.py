"""Secure credential management utilities."""

import base64
import json
import os
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from docvault import config


class CredentialError(Exception):
    """Raised when credential operations fail."""

    pass


class SecureCredentialManager:
    """Manages secure storage and retrieval of credentials."""

    def __init__(self, key_file: Path | None = None):
        """Initialize the credential manager.

        Args:
            key_file: Path to encryption key file. If not provided,
                     uses config.CONFIG_DIR / '.credentials.key'
        """
        self.key_file = key_file or Path(config.CONFIG_DIR) / ".credentials.key"
        self.credentials_file = Path(config.CONFIG_DIR) / ".credentials.enc"
        self._cipher = None
        self._ensure_key_exists()

    def _ensure_key_exists(self):
        """Ensure encryption key exists, create if not."""
        if not self.key_file.exists():
            # Generate new key
            key = Fernet.generate_key()

            # Create directory if needed
            self.key_file.parent.mkdir(parents=True, exist_ok=True)

            # Write key with restricted permissions
            self.key_file.write_bytes(key)

            # Set file permissions to 600 (owner read/write only)
            if os.name != "nt":  # Unix-like systems
                os.chmod(self.key_file, 0o600)

    def _get_cipher(self) -> Fernet:
        """Get or create the cipher for encryption/decryption."""
        if self._cipher is None:
            if not self.key_file.exists():
                raise CredentialError("Encryption key not found")

            key = self.key_file.read_bytes()
            self._cipher = Fernet(key)

        return self._cipher

    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def store_credential(self, name: str, value: str, category: str = "default"):
        """Store a credential securely.

        Args:
            name: Credential name/identifier
            value: The secret value to store
            category: Category for organizing credentials
        """
        # Load existing credentials
        credentials = self._load_credentials()

        # Update credential
        if category not in credentials:
            credentials[category] = {}

        credentials[category][name] = value

        # Save encrypted
        self._save_credentials(credentials)

    def get_credential(self, name: str, category: str = "default") -> str | None:
        """Retrieve a credential.

        Args:
            name: Credential name/identifier
            category: Category where credential is stored

        Returns:
            The credential value or None if not found
        """
        credentials = self._load_credentials()

        if category in credentials and name in credentials[category]:
            return credentials[category][name]

        return None

    def remove_credential(self, name: str, category: str = "default") -> bool:
        """Remove a credential.

        Args:
            name: Credential name/identifier
            category: Category where credential is stored

        Returns:
            True if removed, False if not found
        """
        credentials = self._load_credentials()

        if category in credentials and name in credentials[category]:
            del credentials[category][name]

            # Remove empty categories
            if not credentials[category]:
                del credentials[category]

            self._save_credentials(credentials)
            return True

        return False

    def list_credentials(self, category: str | None = None) -> dict[str, list]:
        """List stored credentials (names only, not values).

        Args:
            category: Filter by category, or None for all

        Returns:
            Dictionary mapping categories to credential names
        """
        credentials = self._load_credentials()

        if category:
            if category in credentials:
                return {category: list(credentials[category].keys())}
            else:
                return {}
        else:
            return {cat: list(creds.keys()) for cat, creds in credentials.items()}

    def _load_credentials(self) -> dict[str, dict[str, str]]:
        """Load and decrypt credentials from file."""
        if not self.credentials_file.exists():
            return {}

        try:
            cipher = self._get_cipher()
            encrypted_data = self.credentials_file.read_bytes()
            decrypted_data = cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            raise CredentialError(f"Failed to load credentials: {e}")

    def _save_credentials(self, credentials: dict[str, dict[str, str]]):
        """Encrypt and save credentials to file."""
        try:
            cipher = self._get_cipher()
            data = json.dumps(credentials).encode()
            encrypted_data = cipher.encrypt(data)

            # Ensure directory exists
            self.credentials_file.parent.mkdir(parents=True, exist_ok=True)

            # Write with restricted permissions
            self.credentials_file.write_bytes(encrypted_data)

            # Set file permissions to 600 (owner read/write only)
            if os.name != "nt":  # Unix-like systems
                os.chmod(self.credentials_file, 0o600)
        except Exception as e:
            raise CredentialError(f"Failed to save credentials: {e}")

    def rotate_key(self) -> bool:
        """Rotate the encryption key.

        Returns:
            True if successful
        """
        try:
            # Load credentials with old key
            credentials = self._load_credentials()

            # Generate new key
            new_key = Fernet.generate_key()

            # Create backup of old key
            backup_key_file = self.key_file.with_suffix(".key.bak")
            backup_key_file.write_bytes(self.key_file.read_bytes())

            # Write new key
            self.key_file.write_bytes(new_key)
            if os.name != "nt":
                os.chmod(self.key_file, 0o600)

            # Reset cipher to use new key
            self._cipher = None

            # Re-encrypt credentials with new key
            self._save_credentials(credentials)

            # Remove backup on success
            backup_key_file.unlink()

            return True
        except Exception as e:
            # Restore from backup if available
            backup_key_file = self.key_file.with_suffix(".key.bak")
            if backup_key_file.exists():
                self.key_file.write_bytes(backup_key_file.read_bytes())
                backup_key_file.unlink()

            raise CredentialError(f"Key rotation failed: {e}")


# Environment variable integration
def get_credential_from_env_or_store(
    name: str, env_var: str, category: str = "api_keys", prompt: str | None = None
) -> str | None:
    """Get credential from environment variable or secure store.

    Checks environment variable first, then secure store.
    If not found and prompt provided, asks user.

    Args:
        name: Credential name in secure store
        env_var: Environment variable name
        category: Category in secure store
        prompt: Optional prompt for user input

    Returns:
        The credential value or None
    """
    # Check environment first
    value = os.getenv(env_var)
    if value:
        return value

    # Check secure store
    manager = SecureCredentialManager()
    value = manager.get_credential(name, category)
    if value:
        return value

    # Prompt user if requested
    if prompt:
        import getpass

        value = getpass.getpass(prompt)
        if value:
            # Store for future use
            manager.store_credential(name, value, category)
            return value

    return None


# Convenience functions for common credentials
def get_github_token() -> str | None:
    """Get GitHub token from env or secure store."""
    return get_credential_from_env_or_store(
        "github_token",
        "GITHUB_TOKEN",
        "api_keys",
        "Enter GitHub token (will be stored securely): ",
    )


def get_openai_api_key() -> str | None:
    """Get OpenAI API key from env or secure store."""
    return get_credential_from_env_or_store(
        "openai_api_key",
        "OPENAI_API_KEY",
        "api_keys",
        "Enter OpenAI API key (will be stored securely): ",
    )


def get_database_password() -> str | None:
    """Get database password from env or secure store."""
    return get_credential_from_env_or_store(
        "database_password", "DB_PASSWORD", "database"
    )
