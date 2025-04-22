#!/usr/bin/env python3
"""
Verify DocVault installation and dependencies.
Run this script after installing DocVault to check that everything is set up correctly.
"""

import importlib
import sqlite3
import subprocess
import sys


def check_python_version():
    """Check that Python version is at least 3.12"""
    required = (3, 12)
    current = sys.version_info[:2]

    print(f"Python version: {'.'.join(map(str, current))}")
    if current >= required:
        print("✅ Python version requirement met")
        return True
    else:
        print(f"❌ Python version should be at least {'.'.join(map(str, required))}")
        return False


def check_package_installed(package_name):
    """Check if a package is installed"""
    try:
        importlib.import_module(package_name)
        print(f"✅ {package_name} is installed")
        return True
    except ImportError:
        print(f"❌ {package_name} is not installed")
        return False


def check_sqlite_vec():
    """Check if sqlite-vec extension is available"""
    try:
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        conn.load_extension("sqlite_vec")
        print("✅ sqlite-vec extension is installed and loaded")
        return True
    except Exception as e:
        # Try to check if it's installed through pip
        try:

            print("✅ sqlite-vec package is installed, but extension loading failed")
            print(f"   Error: {e}")
            print("   This could be due to system permissions or configuration")
            return False
        except ImportError:
            print(f"❌ sqlite-vec extension is not available: {e}")
            print("Please reinstall DocVault or install sqlite-vec manually:")
            print("pip install sqlite-vec")
            return False


def check_ollama():
    """Check if Ollama is running"""
    import json
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if "models" in data:
                models = [model["name"] for model in data["models"]]
                print(f"✅ Ollama is running with models: {', '.join(models)}")
                return True
            else:
                print("⚠️ Ollama is running but no models were found")
                return True
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        print("⚠️ Ollama does not appear to be running")
        print("Start Ollama to enable embedding generation")
        return False
    except Exception as e:
        print(f"⚠️ Error checking Ollama: {e}")
        return False


def check_docvault_cli():
    """Check if DocVault CLI is working"""
    try:
        # First try with direct command
        result = subprocess.run(
            ["dv", "--help"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and "DocVault" in result.stdout:
            print("✅ DocVault CLI is working (dv command found in PATH)")
            return True

        # Try with UV if direct command fails
        result = subprocess.run(
            ["uv", "run", "dv", "--help"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and "DocVault" in result.stdout:
            print("✅ DocVault CLI is working (available through uv run dv)")
            print("   TIP: Copy scripts/dv to your PATH for easier access")
            return True
        else:
            print("❌ DocVault CLI is not working correctly")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ DocVault CLI (dv command) is not found in PATH")
        print("   TIP: Try running with 'uv run dv' or copy scripts/dv to your PATH")
        return False


def main():
    """Run all verification checks"""
    print("DocVault Installation Verification")
    print("=================================")

    all_checks = [
        check_python_version(),
        check_package_installed("docvault"),
        check_package_installed("click"),
        check_package_installed("rich"),
        check_package_installed("mcp"),
        check_sqlite_vec(),
        check_ollama(),
        check_docvault_cli(),
    ]

    print("\nSummary:")
    print(f"Total checks: {len(all_checks)}")
    print(f"Successful: {all_checks.count(True)}")
    print(f"Failed or warnings: {all_checks.count(False)}")

    if False in all_checks:
        print("\nSome checks failed. Please resolve the issues before using DocVault.")
        sys.exit(1)
    else:
        print("\nAll checks passed! DocVault is ready to use.")
        sys.exit(0)


if __name__ == "__main__":
    main()
