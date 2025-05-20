import pytest
from unittest.mock import patch, MagicMock
import sys
import importlib

@pytest.fixture(autouse=True)
def patch_termios_and_tty(monkeypatch):
    mock_termios = MagicMock()
    mock_termios.tcgetattr.return_value = [0]
    mock_termios.tcsetattr.return_value = None

    mock_tty = MagicMock()

    # Patch sys.modules BEFORE anything is imported
    monkeypatch.setitem(sys.modules, "termios", mock_termios)
    monkeypatch.setitem(sys.modules, "tty", mock_tty)

    yield mock_termios, mock_tty

def test_get_single_key_unix(patch_termios_and_tty):
    mock_termios, _ = patch_termios_and_tty
    mock_stdin = MagicMock()
    mock_stdin.read.return_value = 'y'

    with patch.dict('sys.modules', {'termios': mock_termios, 'tty': MagicMock()}):
        import importlib
        import import_deck
        importlib.reload(import_deck)

        with patch('import_deck.IS_WINDOWS', False), \
             patch('sys.stdin', mock_stdin), \
             patch('builtins.print'):
            key = import_deck.get_single_key("Prompt", "ynr")

    assert key == 'y'


def test_get_single_key_quit_unix(patch_termios_and_tty):
    mock_termios, _ = patch_termios_and_tty
    mock_stdin = MagicMock()
    mock_stdin.read.return_value = 'q'

    with patch.dict('sys.modules', {'termios': mock_termios, 'tty': MagicMock()}):
        import importlib
        import import_deck
        importlib.reload(import_deck)

        with patch('import_deck.IS_WINDOWS', False), \
             patch('sys.stdin', mock_stdin), \
             patch('builtins.print'):
            with pytest.raises(KeyboardInterrupt):
                import_deck.get_single_key("Prompt", "ynr")

    mock_stdin.read.assert_called_once_with(1)
    mock_termios.tcgetattr.assert_called()

   
