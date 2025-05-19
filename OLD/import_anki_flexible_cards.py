
import csv
import requests
from tkinter import Tk
from tkinter.filedialog import askopenfilename

anki_connect = 'http://localhost:8765'
default_directory = r'P:\@SYNC\@_ATPL\@SUMMARIES'

def create_deck(deck_name):
    response = requests.post(anki_connect, json={
        'action': 'createDeck',
        'version': 6,
        'params': {'deck': deck_name}
    })
    return response.json()

def add_note(deck, front, back, ref, tags, model="Basic"):
    fields = {
        'Front' if model == "Basic" else 'Text': front,
        'Back' if model == "Basic" else 'Back Extra': back,
        'Ref': ref,
        'Tags': ' '.join(tags)
    }
    
    response = requests.post(anki_connect, json={
        'action': 'addNote',
        'version': 6,
        'params': {
            'note': {
                'deckName': deck,
                'modelName': model,
                'fields': fields,
                'tags': tags,
                'options': {'allowDuplicate': False}
            }
        }
    })
    return response.json()

def detect_model(front_field):
    return "Cloze" if "{{c" in front_field else "Basic"

def import_from_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not all(col in row for col in ["Deck", "Front", "Back", "Ref", "Tags"]):
                print("Missing required column(s). Please ensure: Deck, Front, Back, Ref, Tags")
                return
            deck = row['Deck']
            front = row['Front']
            back = row['Back']
            ref = row['Ref']
            tags = row['Tags'].split()
            model = detect_model(front)
            create_deck(deck)
            result = add_note(deck, front, back, ref, tags, model)
            status = "OK" if result.get("error") is None else f"ERROR: {result.get('error')}"
            print(f"Added {model} card to '{deck}': {front[:60]}... -> {status}")

if __name__ == '__main__':
    print("Select the CSV file to import into Anki...")
    Tk().withdraw()
    file_path = askopenfilename(initialdir=default_directory, filetypes=[('CSV Files', '*.csv')])
    if file_path:
        import_from_csv(file_path)
    else:
        print("No file selected.")
