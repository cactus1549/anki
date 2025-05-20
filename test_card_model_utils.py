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


def test_detect_model():
    assert utils.detect_model("Normal question") == "Basic"
    assert utils.detect_model("{{c1::Cloze}} question") == "Cloze"

def test_get_all_existing_fronts_by_model(mock_requests):
    mock_post, _ = mock_requests

    find_mock = MagicMock()
    find_mock.json.return_value = {"result": [1, 2]}

    info_mock = MagicMock()
    info_mock.json.return_value = {
        "result": [
            {
                "modelName": "Basic",
                "fields": {
                    "Front": {"value": "Question 1"},
                    "Back": {"value": "Answer 1"}
                },
                "noteId": 1
            },
            {
                "modelName": "Basic",
                "fields": {
                    "Front": {"value": "Question 2"},
                    "Back": {"value": "Answer 2"}
                },
                "noteId": 2
            }
        ]
    }

    mock_post.side_effect = [find_mock, info_mock]

    result = utils.get_all_existing_fronts_by_model("Basic")
    assert len(result) == 2
    assert "Question 1" in result
    assert result["Question 1"]["back"] == "Answer 1"