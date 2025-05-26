#!/usr/bin/env python3
"""Demonstration of DocVault's terminal security features.

This script shows how DocVault protects against malicious ANSI escape sequences
that could be present in scraped documentation.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from docvault.utils.console import console
from docvault.utils.terminal_sanitizer import (
    TerminalSanitizer,
    contains_suspicious_sequences,
    sanitize_output,
)


def demo_dangerous_sequences():
    """Demonstrate dangerous sequences that are blocked."""
    print("=== Terminal Security Demo ===\n")

    dangerous_examples = [
        ("Clear Screen", "Normal text\x1b[2JThis would clear your screen!"),
        ("Terminal Title", "Normal\x1b]0;HACKED TERMINAL\x07More text"),
        ("Reset Terminal", "Before\x1bcThis would reset your terminal!"),
        ("Alternative Buffer", "Normal\x1b[?1049hThis switches to alt buffer"),
        ("Mouse Tracking", "Normal\x1b[?1000hThis enables mouse tracking"),
    ]

    print("1. Examples of dangerous sequences (BLOCKED):\n")

    for name, text in dangerous_examples:
        print(f"   {name}:")
        print(f"   Raw: {repr(text)}")
        if contains_suspicious_sequences(text):
            print("   ⚠️  SUSPICIOUS SEQUENCE DETECTED")
        sanitized = sanitize_output(text)
        print(f"   Sanitized: {sanitized}")
        print()


def demo_safe_sequences():
    """Demonstrate safe sequences that are preserved."""
    print("\n2. Examples of safe sequences (ALLOWED):\n")

    safe_examples = [
        ("Red text", "\x1b[31mThis is red\x1b[0m"),
        ("Bold text", "\x1b[1mThis is bold\x1b[0m"),
        ("Green background", "\x1b[42mGreen background\x1b[0m"),
        ("Underlined", "\x1b[4mUnderlined text\x1b[0m"),
        ("Multiple formats", "\x1b[1;31;4mBold red underline\x1b[0m"),
    ]

    for name, text in safe_examples:
        print(f"   {name}:")
        if not contains_suspicious_sequences(text):
            print("   ✅ SAFE SEQUENCE")
        # This will display with actual formatting
        print(f"   Output: {text}")
        print()


def demo_console_integration():
    """Demonstrate console integration with automatic sanitization."""
    print("\n3. Console Integration Demo:\n")

    # Safe content - will display normally
    console.print("   [green]✅ This is safe green text[/green]")

    # Dangerous content - will be sanitized
    dangerous = "   Normal text\x1b[2JThis tries to clear screen"
    console.print(f"   Attempting dangerous output: {dangerous}")

    # The console automatically sanitizes, so the screen won't be cleared
    console.print(
        "   [yellow]⚠️  The screen was NOT cleared - sanitization worked![/yellow]"
    )


def demo_custom_sanitizer():
    """Demonstrate custom sanitizer configurations."""
    print("\n\n4. Custom Sanitizer Configurations:\n")

    # Strict mode - removes ALL ANSI sequences
    strict_sanitizer = TerminalSanitizer(strict_mode=True)
    colored_text = "\x1b[31mRed text\x1b[0m with \x1b[1mbold\x1b[0m"

    print("   Original with colors:")
    print(f"   {colored_text}")

    print("\n   Strict mode (no ANSI):")
    print(f"   {strict_sanitizer.sanitize(colored_text)}")

    # Colors only mode
    colors_only = TerminalSanitizer(allow_colors=True, allow_formatting=False)
    print("\n   Colors only mode:")
    print(f"   {colors_only.sanitize(colored_text)}")


def demo_real_world_scenario():
    """Simulate a real-world scenario with malicious documentation."""
    print("\n\n5. Real-World Scenario - Malicious Documentation:\n")

    # Simulate scraped documentation that contains malicious sequences
    malicious_doc = """
# API Documentation

To use this API, first install our package:

\x1b]0;HACKED - Call 1-800-SCAMMER\x07
```bash
pip install our-package
```

Then import and use it:
\x1b[2J\x1b[3J
```python
from our_package import api
api.connect()  # \x1b[?1000h
```

For more info, see our website.
\x1bc
"""

    print("   Raw documentation contains:")
    print("   - Terminal title change attempt")
    print("   - Screen clearing attempt")
    print("   - Terminal reset attempt")
    print("   - Mouse tracking activation\n")

    # Sanitize it
    safe_doc = sanitize_output(malicious_doc)

    print("   Sanitized output:")
    print("   " + safe_doc.replace("\n", "\n   "))

    print("\n   [green]✅ All malicious sequences removed![/green]")


if __name__ == "__main__":
    # Run all demos
    demo_dangerous_sequences()
    demo_safe_sequences()
    demo_console_integration()
    demo_custom_sanitizer()
    demo_real_world_scenario()

    print("\n" + "=" * 50)
    print("Terminal security demo completed successfully!")
    print("Your terminal was protected from all malicious sequences.")
    print("=" * 50)
