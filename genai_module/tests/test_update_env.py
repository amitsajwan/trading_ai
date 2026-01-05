"""Tests for update_env.py tool."""
import os
from unittest.mock import patch, mock_open

from genai_module.tools.update_env import update_env_file


class TestUpdateEnvFile:
    """Test update_env_file function."""

    def test_creates_new_env_file_with_groq_config(self):
        """Test creating a new .env file with Groq configuration."""
        # Mock file operations for new file
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = False

                with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-123"}):
                    update_env_file()

        # Check that file was opened for writing
        mock_file.assert_called_once_with(mock_path, "w")

        # Check content that was written
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)

        assert "# GenAI Trading System Configuration" in written_content
        assert "# LLM Provider: Groq" in written_content
        assert "GROQ_API_KEY=test-key-123" in written_content
        assert "LLM_PROVIDER=groq" in written_content
        assert "LLM_MODEL=llama-3.3-70b-versatile" in written_content

    def test_updates_existing_env_file_preserving_other_vars(self):
        """Test updating existing .env file while preserving other variables."""
        # Mock existing file content
        existing_content = """# Existing config
EXISTING_VAR=value1
ANOTHER_VAR=value2

# Comment line
"""
        mock_file = mock_open(read_data=existing_content)
        with patch("builtins.open", mock_file):
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = True

                with patch.dict(os.environ, {"GROQ_API_KEY": "new-key-456"}):
                    update_env_file()

        # Check content that was written
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)

        # Check existing variables are preserved
        assert "EXISTING_VAR=value1" in written_content
        assert "ANOTHER_VAR=value2" in written_content

        # Check new Groq config is added
        assert "GROQ_API_KEY=new-key-456" in written_content
        assert "LLM_PROVIDER=groq" in written_content
        assert "LLM_MODEL=llama-3.3-70b-versatile" in written_content

        # Check header is added at top
        lines = written_content.split("\n")
        assert lines[0] == "# GenAI Trading System Configuration"
        assert lines[1] == "# LLM Provider: Groq"

    def test_overwrites_existing_groq_config(self):
        """Test that existing Groq config is overwritten with new values."""
        existing_content = """GROQ_API_KEY=old-key
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
OTHER_VAR=preserved
"""
        mock_file = mock_open(read_data=existing_content)
        with patch("builtins.open", mock_file):
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = True

                with patch.dict(os.environ, {"GROQ_API_KEY": "updated-key-789"}):
                    update_env_file()

        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)

        # Check old config is overwritten
        assert "GROQ_API_KEY=updated-key-789" in written_content
        assert "LLM_MODEL=llama-3.3-70b-versatile" in written_content
        # Other var should be preserved
        assert "OTHER_VAR=preserved" in written_content

        # Old model should be gone
        assert "llama-3.1-8b-instant" not in written_content

    def test_skips_when_no_api_key_in_env_and_user_skips(self):
        """Test that function returns early when no API key and user skips."""
        mock_file = mock_open()
        with patch("builtins.open", mock_file) as mock_open_call:
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = False

                # Ensure no GROQ_API_KEY in env
                with patch.dict(os.environ, {}, clear=True):
                    with patch("builtins.input", return_value=""):  # User presses Enter to skip
                        update_env_file()

            # Check that no file was opened for writing
            mock_open_call.assert_not_called()

    def test_prompts_for_api_key_when_not_in_env(self):
        """Test prompting for API key when not found in environment."""
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = False

                # Ensure no GROQ_API_KEY in env
                with patch.dict(os.environ, {}, clear=True):
                    with patch("builtins.input", return_value="user-entered-key"):
                        update_env_file()

        # Check content that was written
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
        assert "GROQ_API_KEY=user-entered-key" in written_content

    def test_variables_sorted_alphabetically(self):
        """Test that variables are written in alphabetical order."""
        # Create existing file with variables in random order
        existing_content = """Z_VAR=last
A_VAR=first
M_VAR=middle
"""
        mock_file = mock_open(read_data=existing_content)
        with patch("builtins.open", mock_file):
            with patch("genai_module.tools.update_env.Path") as mock_path_class:
                mock_path = mock_path_class.return_value
                mock_path.exists.return_value = True

                with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                    update_env_file()

        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
        lines = [line for line in written_content.split("\n") if line and not line.startswith("#") and "=" in line]

        # Variables should be in alphabetical order
        var_names = [line.split("=", 1)[0] for line in lines]
        assert var_names == sorted(var_names)
