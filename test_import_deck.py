
import pytest
from unittest.mock import patch, MagicMock
from import_deck import import_from_rows, detect_model, get_all_existing_fronts_by_model

@pytest.fixture
def mock_requests_post(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("requests.post", mock)
    return mock

@pytest.fixture
def sample_rows():
    return [
        {'Deck': '070 Ops', 'Front': 'What is CRM?', 'Back': 'Crew Resource Management', 'Ref': '070.01.01', 'Tags': 'human factors'},
        {'Deck': '070 Ops', 'Front': 'Define TEM.', 'Back': 'Threat and Error Management', 'Ref': '070.01.02', 'Tags': 'threat error'},
        {'Deck': '070 Ops', 'Front': 'What is CRM?', 'Back': 'Cooperative cockpit strategy', 'Ref': '070.01.03', 'Tags': 'human factors'}
    ]

def test_detect_model_cloze_and_basic():
    assert detect_model("What is {{c1::CRM}}?") == "Cloze"
    assert detect_model("What is CRM?") == "Basic"

def test_import_skips_duplicates(sample_rows, mock_requests_post):
    # Simulate AnkiConnect responses for findNotes and notesInfo
    def fake_post(url, json):
        if json["action"] == "findNotes":
            return MagicMock(json=lambda: {"result": [1]})
        elif json["action"] == "notesInfo":
            return MagicMock(json=lambda: {"result": [{
                "modelName": "Basic",
                "fields": {
                    "Front": {"value": "What is CRM?"},
                    "Back": {"value": "Crew Resource Management"}
                }
            }]})
        elif json["action"] == "addNote":
            return MagicMock(json=lambda: {"result": None, "error": None})
        elif json["action"] == "modelNames":
            return MagicMock(json=lambda: {"result": ["Basic", "Cloze"]})
        elif json["action"] == "createDeck":
            return MagicMock(json=lambda: {"result": None})
        return MagicMock(json=lambda: {"result": []})

    mock_requests_post.side_effect = fake_post

    import_from_rows(sample_rows, base_deck="Test", dry_run=True)
