"""Terminal output sanitization utilities.

This module provides functions to sanitize output before displaying it in the terminal,
preventing malicious ANSI escape sequences from affecting the user's terminal.
"""

import re

# ANSI escape sequence patterns
ANSI_ESCAPE_PATTERN = re.compile(
    r"""
    \x1B  # ESC character
    (?:   # Start of non-capturing group
        [@-Z\\-_]  # Single character sequences
        |
        \[  # CSI sequences
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
        |
        \]  # OSC sequences
        [^\x07\x1B]*  # OSC string
        (?:\x07|\x1B\\)  # String terminator
        |
        [PX^_]  # Other escape sequences
        [^\x1B]*  # String data
        \x1B\\  # String terminator
    )
    """,
    re.VERBOSE,
)

# Additional dangerous sequences that might not be caught by the main pattern
DANGEROUS_SEQUENCES = [
    # Terminal title/icon changes
    re.compile(rb"\x1B\]0;.*?\x07"),  # Set window title
    re.compile(rb"\x1B\]1;.*?\x07"),  # Set icon name
    re.compile(rb"\x1B\]2;.*?\x07"),  # Set window title
    re.compile(rb"\x1B\]\d+;[^\x07\x1B]*(?:\x07|\x1B\\)"),  # General OSC
    # Cursor manipulation
    re.compile(rb"\x1B\[2J"),  # Clear entire screen
    re.compile(rb"\x1B\[3J"),  # Clear entire screen and scrollback
    re.compile(rb"\x1Bc"),  # Reset terminal
    # Dangerous DCS sequences
    re.compile(rb"\x1BP[^\x1B]*\x1B\\"),  # Device Control String
    # Alternative buffer switching (could hide content)
    re.compile(rb"\x1B\[\?1049[hl]"),  # Switch to/from alternate buffer
    re.compile(rb"\x1B\[\?47[hl]"),  # Save/restore screen
    # Mouse tracking (privacy concern)
    re.compile(rb"\x1B\[\?100[0-6][hl]"),  # Various mouse tracking modes
]

# Safe ANSI sequences (colors, basic formatting)
SAFE_SEQUENCES = {
    # Basic formatting
    "\x1b[0m",  # Reset
    "\x1b[1m",  # Bold
    "\x1b[2m",  # Dim
    "\x1b[3m",  # Italic
    "\x1b[4m",  # Underline
    "\x1b[5m",  # Blink
    "\x1b[7m",  # Reverse
    "\x1b[8m",  # Hidden
    "\x1b[9m",  # Strikethrough
    # Reset specific formatting
    "\x1b[21m",  # Reset bold
    "\x1b[22m",  # Reset dim
    "\x1b[23m",  # Reset italic
    "\x1b[24m",  # Reset underline
    "\x1b[25m",  # Reset blink
    "\x1b[27m",  # Reset reverse
    "\x1b[28m",  # Reset hidden
    "\x1b[29m",  # Reset strikethrough
}

# Add color codes to safe sequences (30-37, 40-47, 90-97, 100-107)
for i in range(30, 38):
    SAFE_SEQUENCES.add(f"\x1b[{i}m")  # Foreground colors
for i in range(40, 48):
    SAFE_SEQUENCES.add(f"\x1b[{i}m")  # Background colors
for i in range(90, 98):
    SAFE_SEQUENCES.add(f"\x1b[{i}m")  # Bright foreground colors
for i in range(100, 108):
    SAFE_SEQUENCES.add(f"\x1b[{i}m")  # Bright background colors

# Default color resets
SAFE_SEQUENCES.add("\x1b[39m")  # Default foreground
SAFE_SEQUENCES.add("\x1b[49m")  # Default background


class TerminalSanitizer:
    """Sanitizes terminal output to prevent malicious escape sequences."""

    def __init__(
        self,
        allow_colors: bool = True,
        allow_formatting: bool = True,
        strict_mode: bool = False,
    ):
        """Initialize the sanitizer.

        Args:
            allow_colors: Whether to allow color codes
            allow_formatting: Whether to allow basic formatting (bold, italic, etc)
            strict_mode: If True, strips ALL ANSI sequences
        """
        self.allow_colors = allow_colors
        self.allow_formatting = allow_formatting
        self.strict_mode = strict_mode
        self._safe_sequences = self._build_safe_sequences()

    def _build_safe_sequences(self) -> set[str]:
        """Build the set of allowed sequences based on settings."""
        if self.strict_mode:
            return set()

        safe = set()

        if self.allow_formatting:
            # Add basic formatting (non-color codes)
            for seq in SAFE_SEQUENCES:
                # Check if it's a formatting code (not a color)
                if seq.endswith("m"):
                    # Extract the number
                    match = re.match(r"\x1B\[(\d+)m", seq)
                    if match:
                        num = int(match.group(1))
                        # Formatting codes: 0-9, 21-29
                        if num < 30 or seq == "\x1b[0m":
                            safe.add(seq)

        if self.allow_colors:
            # Add color codes (30-49, 90-107)
            for seq in SAFE_SEQUENCES:
                if seq.endswith("m"):
                    # Extract the number
                    match = re.match(r"\x1B\[(\d+)m", seq)
                    if match:
                        num = int(match.group(1))
                        # Color codes: 30-49, 90-107
                        if (30 <= num <= 49) or (90 <= num <= 107):
                            safe.add(seq)

        # Always allow reset
        safe.add("\x1b[0m")

        return safe

    def sanitize(self, text: str) -> str:
        """Sanitize text by removing dangerous ANSI sequences.

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text with dangerous sequences removed
        """
        if not text:
            return text

        # First, check for and remove dangerous binary sequences
        text_bytes = text.encode("utf-8", errors="ignore")
        for pattern in DANGEROUS_SEQUENCES:
            text_bytes = pattern.sub(b"", text_bytes)

        # Convert back to string
        text = text_bytes.decode("utf-8", errors="ignore")

        # Handle remaining ANSI sequences
        if self.strict_mode:
            # Remove all ANSI sequences
            return ANSI_ESCAPE_PATTERN.sub("", text)

        # Replace sequences selectively
        def replace_sequence(match):
            seq = match.group(0)
            if seq in self._safe_sequences:
                return seq
            return ""  # Remove unsafe sequences

        return ANSI_ESCAPE_PATTERN.sub(replace_sequence, text)

    def sanitize_for_display(
        self, text: str, max_length: int | None = None, truncate_marker: str = "..."
    ) -> str:
        """Sanitize text and optionally truncate for safe display.

        Args:
            text: The text to sanitize
            max_length: Maximum length of output (counts visible characters only)
            truncate_marker: String to append when truncating

        Returns:
            Sanitized and possibly truncated text
        """
        # First sanitize
        sanitized = self.sanitize(text)

        if max_length is None:
            return sanitized

        # Count visible characters (excluding ANSI sequences)
        visible_length = len(ANSI_ESCAPE_PATTERN.sub("", sanitized))

        if visible_length <= max_length:
            return sanitized

        # Need to truncate - this is tricky with ANSI sequences
        # We'll build the result character by character
        result = []
        visible_count = 0
        in_sequence = False
        current_sequence = []

        for char in sanitized:
            if char == "\x1b":
                in_sequence = True
                current_sequence = [char]
            elif in_sequence:
                current_sequence.append(char)
                # Check if sequence is complete
                if (
                    char
                    in "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
                    "abcdefghijklmnopqrstuvwxyz{|}~"
                ):
                    in_sequence = False
                    result.extend(current_sequence)
                    current_sequence = []
            else:
                if visible_count < max_length - len(truncate_marker):
                    result.append(char)
                    visible_count += 1
                else:
                    break

        # Add reset sequence if we had any formatting
        if self._has_formatting(sanitized):
            result.append("\x1b[0m")

        result.append(truncate_marker)
        return "".join(result)

    def _has_formatting(self, text: str) -> bool:
        """Check if text contains any ANSI formatting."""
        return bool(ANSI_ESCAPE_PATTERN.search(text))


# Convenience functions
_default_sanitizer = TerminalSanitizer()
_strict_sanitizer = TerminalSanitizer(strict_mode=True)


def sanitize_output(text: str, strict: bool = False) -> str:
    """Sanitize text for terminal output.

    Args:
        text: Text to sanitize
        strict: If True, removes ALL ANSI sequences

    Returns:
        Sanitized text
    """
    sanitizer = _strict_sanitizer if strict else _default_sanitizer
    return sanitizer.sanitize(text)


def sanitize_for_display(
    text: str, max_length: int | None = None, strict: bool = False
) -> str:
    """Sanitize and optionally truncate text for display.

    Args:
        text: Text to sanitize
        max_length: Maximum visible length
        strict: If True, removes ALL ANSI sequences

    Returns:
        Sanitized and possibly truncated text
    """
    sanitizer = _strict_sanitizer if strict else _default_sanitizer
    return sanitizer.sanitize_for_display(text, max_length)


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text.

    Args:
        text: Text to strip

    Returns:
        Text with all ANSI sequences removed
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


def contains_suspicious_sequences(text: str) -> bool:
    """Check if text contains potentially dangerous sequences.

    Args:
        text: Text to check

    Returns:
        True if suspicious sequences are found
    """
    # Check for dangerous binary sequences
    text_bytes = text.encode("utf-8", errors="ignore")
    for pattern in DANGEROUS_SEQUENCES:
        if pattern.search(text_bytes):
            return True

    # Check for any non-safe ANSI sequences
    for match in ANSI_ESCAPE_PATTERN.finditer(text):
        if match.group(0) not in SAFE_SEQUENCES:
            return True

    return False
