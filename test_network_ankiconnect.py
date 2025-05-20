import pytest
from unittest.mock import MagicMock
import utils 

@pytest.fixture
def mock_requests(monkeypatch):
    mock_post = MagicMock()
    mock_get = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)
    return mock_post, mock_get

def test_check_ankiconnect(mock_requests):
    mock_post, mock_get = mock_requests
    mock_get.return_value.status_code = 200
    assert utils.check_ankiconnect() is True

    mock_get.return_value.status_code = 404
    assert utils.check_ankiconnect() is False

def test_anki_model_exists(mock_requests):
    mock_post, _ = mock_requests
    mock_post.return_value.json.return_value = {"result": ["Basic", "Cloze"]}
    assert utils.anki_model_exists("Basic") is True
    assert utils.anki_model_exists("NonExistent") is False
