
import csv
import requests
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from collections import Counter
import os

anki_connect = 'http://localhost:8765'
default_csv_root = 'P:/@SYNC/@_ATPL/@SUMMARIES'
default_base_deck = 'ATPL'
required_headers = {'Deck', 'Front', 'Back', 'Ref', 'Tags'}
log_file_path = "anki_import_log.txt"

def anki_model_exists(model_name="Basic"):
    response = requests.post(anki_connect, json={
        'action': 'modelNames',
        'version': 6
    })
    return model_name in response.json().get('result', [])

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

def preview_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        headers = set(reader.fieldnames)
        missing = required_headers - headers
        if missing:
            print(f"Missing required columns in CSV: {', '.join(missing)}")
            return None, []

        rows = list(reader)
        if not rows:
            print("CSV file appears to be empty after the header.")
            return None, []

        # Normalize and fix tag fields if needed
        for row in rows:
            if 'Tags' in row and ',' in row['Tags']:
                row['Tags'] = row['Tags'].replace(',', ' ')
        return reader.fieldnames, rows

def summarize_deck(rows):
    decks = sorted(set(row['Deck'] for row in rows))
    tags_counter = Counter(tag for row in rows for tag in row['Tags'].split())
    print("\n=== Deck Hierarchy ===")
    for deck in decks:
        print(f"  - {deck}")
    print(f"\nTotal cards: {len(rows)}")
    print(f"Unique decks: {len(decks)}")
    print("\n=== Tag Summary ===")
    for tag, count in tags_counter.items():
        print(f"  #{tag} — {count} cards")

def import_from_rows(rows, base_deck=None, dry_run=False):
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    for idx, col in enumerate(rows, start=1):
        deck = col['Deck']
        if base_deck:
            deck = f"{base_deck}::{deck}"
        front = col['Front']
        back = col['Back']
        ref = col['Ref']
        tags = col['Tags'].split()

        if dry_run:
            print(f"✔️ Dry run {idx}/{len(rows)}: Would add card to '{deck}'")
            continue

        create_deck(deck)
        result = add_note(deck, front, back, ref, tags)
        status = "OK" if result.get('error') is None else result.get('error')
        print(f"{'✔️' if status == 'OK' else '❌'} Card {idx}/{len(rows)}: {front[:50]}... -> {status}")
        if status != "OK":
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"Deck: {deck}, Front: {front[:60]}, Error: {status}\n")

if __name__ == '__main__':
    print("Select the CSV file to import into Anki...")
    Tk().withdraw()
    file_path = askopenfilename(initialdir=default_csv_root, filetypes=[('CSV Files', '*.csv')])
    if file_path:
        headers, rows = preview_csv(file_path)
        if not rows:
            exit()

        first_deck = rows[0]['Deck']
        print(f"\nFirst deck entry found: '{first_deck}'")

        summarize_deck(rows)

        user_input = input(f"Enter a base deck name (default = '{default_base_deck}', or type 'none' for none): ").strip()
        base_deck = default_base_deck if user_input == '' else None if user_input.lower() == 'none' else user_input

        if not anki_model_exists("Basic"):
            print("⚠️ Error: 'Basic' model does not exist in Anki. Please check your model settings.")
            exit()

        dry_run_choice = input("Would you like to do a dry run (y/n)? ").strip().lower()
        dry_run = dry_run_choice == 'y'

        print("\nStarting import...")
        import_from_rows(rows, base_deck, dry_run=dry_run)

        if os.path.exists(log_file_path):
            print(f"\n❗ Some cards failed to import. See '{log_file_path}' for details.")
    else:
        print("No file selected.")
