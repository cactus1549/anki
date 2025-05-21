import pytest
from unittest.mock import patch
from utils import safe_input

def test_safe_input_default_used():
    with patch("builtins.input", return_value=""):
        result = safe_input("Prompt: ", default="y")
        assert result == "y"

def test_safe_input_trims_and_lowers():
    with patch("builtins.input", return_value="  Y  "):
        result = safe_input("Prompt: ", default="n")
        assert result == "y"

def test_safe_input_handles_keyboard_interrupt():
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            safe_input("Prompt: ", default="n")
