"""Basic test to diagnose the environment"""

import sys


def test_environment():
    """Print environment details to diagnose issues"""
    print("\nPython path:")
    for path in sys.path:
        print(f"  - {path}")

    print("\nPython executable:")
    print(f"  - {sys.executable}")

    print("\nPython version:")
    print(f"  - {sys.version}")

    # Try to import modules directly
    print("\nModule check:")
    modules_to_check = [
        "click",
        "rich",
        "pytest",
        "pytest_asyncio",
        "aiohttp",
        "numpy",
        "markupsafe",
        "httpx",
        "bs4",
    ]

    for module in modules_to_check:
        try:
            __import__(module)
            print(f"  - {module}: OK")
        except ImportError:
            print(f"  - {module}: MISSING")

    # Basic assertion to make test pass
    assert True
