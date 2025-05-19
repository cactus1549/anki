
import csv
import requests
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# === Configuration ===
anki_connect = 'http://localhost:8765'
default_csv_root = r'P:\@SYNC\@_ATPL\@SUMMARIES'

# === Anki API Functions ===
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

# === Import Logic ===
def import_from_csv(file_path, base_deck=None):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            subdeck = row['Deck']
            full_deck = f"{base_deck}::{subdeck}" if base_deck else subdeck
            front = row['Front']
            back = row['Back']
            ref = row['Ref']
            tags = row['Tags'].split()
            create_deck(full_deck)
            result = add_note(full_deck, front, back, ref, tags)
            status = "OK" if result.get("error") is None else result.get("error")
            print(f"Added card to '{full_deck}': {front[:60]}... -> {status}")

# === Entry Point ===
if __name__ == '__main__':
    print(f"Select the CSV file to import into Anki (default dir: {default_csv_root})...")
    Tk().withdraw()  # Hide the root Tkinter window
    os.chdir(default_csv_root)  # Set default directory
    file_path = askopenfilename(filetypes=[('CSV Files', '*.csv')])

    if file_path:
        base_deck = input("Optional: Enter a base deck name (or leave blank): ").strip()
        import_from_csv(file_path, base_deck if base_deck else None)
    else:
        print("No file selected.")
