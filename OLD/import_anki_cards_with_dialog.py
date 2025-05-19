
import csv
import requests
from tkinter import Tk
from tkinter.filedialog import askopenfilename
anki_connect = 'http://localhost:8765'

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

def import_from_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            deck = row['Deck']
            front = row['Front']
            back = row['Back']
            ref = row['Ref']
            tags = row['Tags'].split()
            create_deck(deck)
            result = add_note(deck, front, back, ref, tags)
            print(f"Added card to '{deck}': {front[:60]}... -> {result.get('error')}")

if __name__ == '__main__':
    print("Select the CSV file to import into Anki...")
    Tk().withdraw()  # Hide the root Tkinter window
    file_path = askopenfilename(filetypes=[('CSV Files', '*.csv')])
    if file_path:
        import_from_csv(file_path)
    else:
        print("No file selected.")
