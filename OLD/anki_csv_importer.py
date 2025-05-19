import csv
import requests
from tkinter import Tk
from tkinter.filedialog import askopenfilename

anki_connect = 'http://localhost:8765'

# Default path and base deck
default_csv_root = 'P:/@SYNC/@_ATPL/@SUMMARIES'
default_base_deck = 'ATPL'

def create_deck(deck_name):
    response = requests.post(anki_connect, json={
        'action': 'createDeck',
        'version': 6,
        'params': {'deck': deck_name}
    })
    return response.json()

def add_note(deck, front, back, ref, tags):
    fields = {
        'Front': front,
        'Back': back,
        'Ref': ref,
        'Tags': ' '.join(tags)
    }
    response = requests.post(anki_connect, json={
        'action': 'addNote',
        'version': 6,
        'params': {
            'note': {
                'deckName': deck,
                'modelName': 'Basic',
                'fields': fields,
                'tags': tags,
                'options': {'allowDuplicate': False}
            }
        }
    })
    return response.json()

def import_from_csv(file_path, base_deck=None):
    required_headers = {'Deck', 'Front', 'Back', 'Ref', 'Tags'}
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        headers = set(reader.fieldnames)

        missing = required_headers - headers
        if missing:
            print(f"Missing required columns in CSV: {', '.join(missing)}")
            return

        rows = list(reader)
        if not rows:
            print("CSV file appears to be empty after the header.")
            return

        first_deck = rows[0]['Deck']
        print(f"First deck entry found: '{first_deck}'")

        for col in rows:
            deck = col['Deck']
            if base_deck:
                deck = f"{base_deck}::{deck}"
            front = col['Front']
            back = col['Back']
            ref = col['Ref']
            tags = col['Tags'].split()
            create_deck(deck)
            result = add_note(deck, front, back, ref, tags)
            status = "OK" if result.get('error') is None else result.get('error')
            print(f"Added card to '{deck}': {front[:60]}... -> {status}")

if __name__ == '__main__':
    print("Select the CSV file to import into Anki...")
    Tk().withdraw()
    file_path = askopenfilename(initialdir=default_csv_root, filetypes=[('CSV Files', '*.csv')])
    if file_path:
        user_input = input(f"Enter a base deck name (default = '{default_base_deck}', or leave blank for none): ").strip()
        base_deck = default_base_deck if user_input == '' else None if user_input.lower() == 'none' else user_input
        import_from_csv(file_path, base_deck)
    else:
        print("No file selected.")
