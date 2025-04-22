"""Basic tests that don't require extensive mocking"""

from pathlib import Path


def test_version():
    """Test the version is accessible"""
    from docvault import __version__

    assert __version__ == "0.1.0"


def test_config_defaults():
    """Test that config has default values"""
    from docvault import config

    # Check that basic config attributes exist
    assert hasattr(config, "DEFAULT_BASE_DIR")
    assert hasattr(config, "DB_PATH")
    assert hasattr(config, "STORAGE_PATH")
    assert isinstance(config.DEFAULT_BASE_DIR, Path)
