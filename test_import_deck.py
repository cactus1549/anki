import pytest
from unittest.mock import patch, MagicMock, call
from import_deck import (
    import_from_rows,
    detect_model,
    get_all_existing_fronts_by_model,
    check_deck_prefixes,
    add_note,
    delete_note,
    create_deck,
    anki_model_exists,
    anki_connect
)

@pytest.fixture
def mock_requests_post(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("requests.post", mock)
    return mock

@pytest.fixture
def sample_rows():
    return [
        {
            'Deck': '070 Ops', 
            'Front': 'What is CRM?', 
            'Back': 'Crew Resource Management', 
            'Ref': '070.01.01', 
            'Tags': 'human factors'
        },
        {
            'Deck': '070 Ops', 
            'Front': 'Define TEM.', 
            'Back': 'Threat and Error Management', 
            'Ref': '070.01.02', 
            'Tags': 'threat error'
        },
        {
            'Deck': '070 Ops', 
            'Front': 'What is CRM?', 
            'Back': 'Cooperative cockpit strategy', 
            'Ref': '070.01.03', 
            'Tags': 'human factors'
        },
        {
            'Deck': '070 Ops', 
            'Front': '{{c1::CRM}} stands for?', 
            'Back': 'Crew Resource Management', 
            'Ref': '070.01.04', 
            'Tags': 'human factors cloze'
        }
    ]

@pytest.fixture
def mock_anki_responses():
    def _mock_anki_responses(duplicate_front=None, duplicate_back=None):
        def fake_post(*args, **kwargs):
            json_data = kwargs.get('json', {}) or (args[1] if len(args) > 1 else {})
            action = json_data.get("action")
            
            mock = MagicMock()
            if action == "modelNames":
                mock.json.return_value = {"result": ["Basic", "Cloze"]}
            elif action == "findNotes":
                mock.json.return_value = {"result": [1] if duplicate_front else []}
            elif action == "notesInfo":
                mock.json.return_value = {"result": [{
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": duplicate_front},
                        "Back": {"value": duplicate_back}
                    },
                    "noteId": 1
                }]}
            elif action == "addNote":
                mock.json.return_value = {"result": 123, "error": None}
            elif action in ["createDeck", "deleteNotes"]:
                mock.json.return_value = {"result": None, "error": None}
            else:
                mock.json.return_value = {"result": None}
            
            return mock
        
        return fake_post
    return _mock_anki_responses

class TestModelDetection:
    def test_detect_model_basic(self):
        assert detect_model("What is CRM?") == "Basic"
        assert detect_model("Define TEM") == "Basic"
    
    def test_detect_model_cloze(self):
        assert detect_model("What is {{c1::CRM}}?") == "Cloze"
        assert detect_model("{{c2::CRM}} stands for {{c1::Crew Resource Management}}") == "Cloze"
    
    @pytest.mark.parametrize("text,expected", [
        ("Normal text", "Basic"),
        ("{{c1::Cloze}} text", "Cloze"),
        ("Mixed {{c2::text}}", "Cloze"),
        ("", "Basic"),
    ])
    def test_detect_model_variations(self, text, expected):
        assert detect_model(text) == expected

    @pytest.mark.parametrize("deck_list,prefix,expected", [
        (['ATPL::070 Ops', 'ATPL::071 Systems'], 'ATPL', True),
        (['ATPL', 'ATPL::070 Ops'], 'ATPL', True),
        (['070 Ops', '071 Systems'], 'ATPL', False),
        (['MyDeck::070 Ops', 'MyDeck'], 'MyDeck', True),
        (['ATPL', '070 Ops'], 'ATPL', False),  # Mixed case
        ([], 'ATPL', True),  # Empty case
    ])
    def test_check_deck_prefixes(deck_list, prefix, expected):
        rows = [{'Deck': deck} for deck in deck_list]
        assert check_deck_prefixes(rows, prefix) == expected

class TestImportFunctions:
    def test_import_skips_exact_duplicates(self, sample_rows, mock_requests_post, mock_anki_responses):
        mock_requests_post.side_effect = mock_anki_responses(
            duplicate_front="What is CRM?",
            duplicate_back="Crew Resource Management"
        )
        
        import_from_rows(sample_rows[:1], base_deck="Test", dry_run=True)
        
        # Verify it skipped the duplicate
        calls = [c[1]['json']['action'] for c in mock_requests_post.call_args_list]
        assert "findNotes" in calls
        assert "notesInfo" in calls
        assert "addNote" not in calls  # Should skip adding
    
    def test_import_updates_changed_back(self, sample_rows, mock_requests_post, mock_anki_responses):
        mock_requests_post.side_effect = mock_anki_responses(
            duplicate_front="What is CRM?",
            duplicate_back="Old definition"
        )
        
        import_from_rows(sample_rows[:1], base_deck="Test", dry_run=False)
        
        # Verify the card was added (we don't check for deletion)
        calls = [c[1]['json']['action'] for c in mock_requests_post.call_args_list]
        assert "addNote" in calls
        
        # Verify the card content was updated
        add_note_call = next(
            c for c in mock_requests_post.call_args_list
            if c[1]['json']['action'] == "addNote"
        )
        assert add_note_call[1]['json']['params']['note']['fields']['Back'] == "Crew Resource Management"

    
    def test_import_adds_new_cards(self, sample_rows, mock_requests_post, mock_anki_responses):
        mock_requests_post.side_effect = mock_anki_responses()  # No duplicates
        
        import_from_rows(sample_rows[1:2], base_deck="Test", dry_run=False)
        
        # Verify addNote was called
        calls = [c[1]['json']['action'] for c in mock_requests_post.call_args_list]
        assert "addNote" in calls
    
    def test_import_handles_cloze_cards(self, sample_rows, mock_requests_post, mock_anki_responses):
        mock_requests_post.side_effect = mock_anki_responses()
        
        import_from_rows(sample_rows[3:4], base_deck="Test", dry_run=False)
        
        # Find the addNote call and verify model
        add_note_calls = [c for c in mock_requests_post.call_args_list 
                         if c[1]['json']['action'] == "addNote"]
        assert len(add_note_calls) == 1
        assert add_note_calls[0][1]['json']['params']['note']['modelName'] == "Cloze"

class TestAnkiConnectFunctions:
    def test_add_note_success(self, mock_requests_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": 123, "error": None}
        mock_requests_post.return_value = mock_response
        
        result = add_note("Test", "Front", "Back", "Ref", ["tag1"], "Basic")
        
        assert result["result"] == 123
        mock_requests_post.assert_called_once_with(
            anki_connect,
            json={
                'action': 'addNote',
                'version': 6,
                'params': {
                    'note': {
                        'deckName': 'Test',
                        'modelName': 'Basic',
                        'fields': {
                            'Front': 'Front',
                            'Back': 'Back',
                            'Ref': 'Ref',
                            'Tags': 'tag1'
                        },
                        'tags': ['tag1'],
                        'options': {'allowDuplicate': True}
                    }
                }
            }
        )
    
    def test_delete_note(self, mock_requests_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None, "error": None}
        mock_requests_post.return_value = mock_response
        
        delete_note(123)
        
        mock_requests_post.assert_called_once_with(
            anki_connect,
            json={
                'action': 'deleteNotes',
                'version': 6,
                'params': {'notes': [123]}
            }
        )
    
    def test_create_deck(self, mock_requests_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None, "error": None}
        mock_requests_post.return_value = mock_response
        
        create_deck("New Deck")
        
        mock_requests_post.assert_called_once_with(
            anki_connect,
            json={
                'action': 'createDeck',
                'version': 6,
                'params': {'deck': 'New Deck'}
            }
        )
    
    def test_anki_model_exists(self, mock_requests_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": ["Basic", "Cloze"]}
        mock_requests_post.return_value = mock_response
        
        assert anki_model_exists("Basic") is True
        assert anki_model_exists("Missing") is False
        
        mock_requests_post.assert_called_with(
            anki_connect,
            json={'action': 'modelNames', 'version': 6}
        )