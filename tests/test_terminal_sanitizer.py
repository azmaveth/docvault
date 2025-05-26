"""Tests for terminal output sanitization."""

from docvault.utils.terminal_sanitizer import (
    TerminalSanitizer,
    contains_suspicious_sequences,
    sanitize_for_display,
    sanitize_output,
    strip_ansi,
)


class TestTerminalSanitizer:
    """Test terminal sanitization functionality."""

    def test_safe_color_codes_preserved(self):
        """Test that safe color codes are preserved."""
        text = "\x1b[31mRed text\x1b[0m"
        result = sanitize_output(text)
        assert result == text  # Should be preserved

        text = "\x1b[1m\x1b[32mBold green\x1b[0m"
        result = sanitize_output(text)
        assert result == text

    def test_dangerous_sequences_removed(self):
        """Test that dangerous sequences are removed."""
        # Terminal title change
        text = "Normal text\x1b]0;Malicious Title\x07More text"
        result = sanitize_output(text)
        assert result == "Normal textMore text"

        # Clear screen
        text = "Before\x1b[2JAfter"
        result = sanitize_output(text)
        assert result == "BeforeAfter"

        # Reset terminal
        text = "Before\x1bcAfter"
        result = sanitize_output(text)
        assert result == "BeforeAfter"

    def test_strict_mode_removes_all(self):
        """Test that strict mode removes all ANSI sequences."""
        text = "\x1b[31mRed\x1b[0m \x1b[1mBold\x1b[0m"
        result = sanitize_output(text, strict=True)
        assert result == "Red Bold"
        assert "\x1b" not in result

    def test_strip_ansi(self):
        """Test ANSI stripping function."""
        text = "\x1b[31;1mError:\x1b[0m Something went wrong"
        result = strip_ansi(text)
        assert result == "Error: Something went wrong"
        assert "\x1b" not in result

    def test_contains_suspicious_sequences(self):
        """Test detection of suspicious sequences."""
        # Safe sequences
        assert not contains_suspicious_sequences("\x1b[31mRed\x1b[0m")
        assert not contains_suspicious_sequences("\x1b[1mBold\x1b[0m")

        # Dangerous sequences
        assert contains_suspicious_sequences("\x1b]0;Title\x07")
        assert contains_suspicious_sequences("\x1b[2J")
        assert contains_suspicious_sequences("\x1bc")
        assert contains_suspicious_sequences("\x1b[?1049h")  # Alt buffer

    def test_sanitize_for_display_truncation(self):
        """Test sanitization with truncation."""
        text = "This is a very long text that needs to be truncated"
        result = sanitize_for_display(text, max_length=20)
        assert result == "This is a very lo..."
        assert len(strip_ansi(result)) == 20

    def test_sanitize_for_display_with_ansi(self):
        """Test truncation preserves ANSI codes correctly."""
        text = "\x1b[31mThis is red text that is very long\x1b[0m"
        result = sanitize_for_display(text, max_length=15)
        # Should preserve color codes and add reset before truncation
        assert "\x1b[31m" in result
        assert "\x1b[0m" in result
        assert result.endswith("...")

    def test_custom_sanitizer_colors_only(self):
        """Test custom sanitizer that allows only colors."""
        sanitizer = TerminalSanitizer(allow_colors=True, allow_formatting=False)

        # Colors should be preserved
        text = "\x1b[31mRed\x1b[0m"
        assert sanitizer.sanitize(text) == text

        # Formatting should be removed (except reset)
        text = "\x1b[1mBold\x1b[0m"
        assert sanitizer.sanitize(text) == "Bold\x1b[0m"

    def test_binary_sequence_removal(self):
        """Test removal of binary escape sequences."""
        # Device Control String
        text = "Normal\x1bPSome DCS\x1b\\More"
        result = sanitize_output(text)
        assert result == "NormalMore"

        # OSC with different terminators
        text = "Text\x1b]2;Title\x1b\\More"
        result = sanitize_output(text)
        assert result == "TextMore"

    def test_mouse_tracking_removal(self):
        """Test removal of mouse tracking sequences."""
        text = "Normal\x1b[?1000hMouse tracking on"
        result = sanitize_output(text)
        assert result == "NormalMouse tracking on"

        text = "Normal\x1b[?1003lMouse tracking off"
        result = sanitize_output(text)
        assert result == "NormalMouse tracking off"

    def test_alternate_buffer_removal(self):
        """Test removal of alternate buffer sequences."""
        text = "Normal\x1b[?1049hAlternate buffer"
        result = sanitize_output(text)
        assert result == "NormalAlternate buffer"

    def test_empty_input(self):
        """Test handling of empty input."""
        assert sanitize_output("") == ""
        assert sanitize_output(None) is None
        assert strip_ansi("") == ""
        assert sanitize_for_display("", max_length=10) == ""

    def test_unicode_handling(self):
        """Test handling of unicode with ANSI sequences."""
        text = "\x1b[31m错误\x1b[0m: \x1b[32m成功\x1b[0m"
        result = sanitize_output(text)
        assert result == text  # Should preserve unicode and safe colors

        # Strict mode should remove ANSI but preserve unicode
        result = sanitize_output(text, strict=True)
        assert result == "错误: 成功"

    def test_nested_sequences(self):
        """Test handling of nested/complex sequences."""
        # Multiple formatting
        text = "\x1b[1;31;4mBold red underline\x1b[0m"
        result = sanitize_output(text)
        assert "\x1b[0m" in result  # Reset should be preserved

        # Mixed safe and unsafe
        text = "\x1b[31mRed\x1b]0;Title\x07\x1b[32mGreen\x1b[0m"
        result = sanitize_output(text)
        assert result == "\x1b[31mRed\x1b[32mGreen\x1b[0m"


class TestIntegration:
    """Test integration with console output."""

    def test_console_integration(self):
        """Test that console properly sanitizes output."""
        from docvault.utils.console import LoggingConsole

        # This would normally clear the screen - should be sanitized
        dangerous_text = "Normal\x1b[2JCleared"

        # We can verify the sanitization logic works
        assert contains_suspicious_sequences(dangerous_text)

        # Create console to ensure it initializes properly
        LoggingConsole(sanitize=True)

    def test_environment_variable_disable(self, monkeypatch):
        """Test that sanitization can be disabled via environment variable."""
        from docvault.utils.console import LoggingConsole

        # Enable sanitization disable
        monkeypatch.setenv("DOCVAULT_DISABLE_SANITIZATION", "1")

        console = LoggingConsole()
        assert not console.sanitize

        # Remove env var
        monkeypatch.delenv("DOCVAULT_DISABLE_SANITIZATION")

        console = LoggingConsole()
        assert console.sanitize
