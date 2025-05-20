import pytest
from unittest.mock import patch, MagicMock
import import_deck

@pytest.fixture
def sample_rows():
    return [
        {'Deck': 'Test', 'Front': 'Question 1', 'Back': 'Answer 1', 'Ref': 'Ref1', 'Tags': 'tag1'},
        {'Deck': 'Test', 'Front': 'Question 2', 'Back': 'Answer 2', 'Ref': 'Ref2', 'Tags': 'tag2'},
        {'Deck': 'Test', 'Front': '{{c1::Cloze}} question', 'Back': 'Extra info', 'Ref': 'Ref3', 'Tags': 'tag3'}
    ]

@pytest.fixture
def mock_anki_responses():
    def _mock_responses(duplicate_front=None, duplicate_back=None):
        def fake_post(url, json=None, **kwargs):
            mock = MagicMock()
            action = json.get("action") if json else None
            if action == "findNotes":
                mock.json.return_value = {"result": [1] if duplicate_front else []}
            elif action == "notesInfo":
                mock.json.return_value = {"result": [{
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": duplicate_front},
                        "Back": {"value": duplicate_back},
                        "Ref": {"value": "Ref1"},
                        "Tags": {"value": "tag1"}
                    },
                    "noteId": 1
                }]}
            elif action == "addNote":
                mock.json.return_value = {"result": 123, "error": None}
            elif action == "deleteNotes":
                mock.json.return_value = {"result": None, "error": None}
            elif action == "createDeck":
                mock.json.return_value = {"result": True, "error": None}
            elif action == "modelNames":
                mock.json.return_value = {"result": ["Basic", "Cloze"]}
            else:
                mock.json.return_value = {"result": None}
            return mock
        return fake_post
    return _mock_responses

@pytest.fixture
def mock_requests(monkeypatch):
    mock_post = MagicMock()
    mock_get = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)
    return mock_post, mock_get

def test_import_new_cards(sample_rows, mock_requests, mock_anki_responses):
    mock_post, _ = mock_requests
    mock_post.side_effect = mock_anki_responses()
    import_deck.import_from_rows(sample_rows, base_deck="Test", dry_run=False)

    add_note_calls = [c[1]["json"]["action"] for c in mock_post.call_args_list]
    assert add_note_calls.count("addNote") == len(sample_rows)

def test_import_skip_duplicates(sample_rows, mock_requests, mock_anki_responses):
    mock_post, _ = mock_requests
    mock_post.side_effect = mock_anki_responses(
        duplicate_front="Question 1",
        duplicate_back="Answer 1"
    )

    import_deck.import_from_rows(sample_rows[:1], base_deck="Test", dry_run=False)
    actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
    assert "addNote" not in actions

def test_import_dry_run(sample_rows, mock_requests, mock_anki_responses):
    mock_post, _ = mock_requests
    mock_post.side_effect = mock_anki_responses()
    import_deck.import_from_rows(sample_rows, base_deck="Test", dry_run=True)
    actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
    assert "addNote" not in actions
