# utils.py

import csv
import json
import requests
from collections import Counter
import sys
import os

# Platform handling
try:
    import tty
    import termios
except ImportError:
    tty = None
    termios = None

IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    import msvcrt

from config import ANKI_CONNECT_URL, REQUIRED_HEADERS, LOG_FILE_PATH

class CardModel:
    BASIC = "Basic"
    CLOZE = "Cloze"

def get_single_key(prompt: str, valid_keys: str) -> str:
    valid_keys = valid_keys.lower()
    print(prompt)
    try:
        if IS_WINDOWS:
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'q':
                        raise KeyboardInterrupt("User cancelled operation")
                    if key in valid_keys:
                        return key
                    print(f"Invalid key. Please press one of: {valid_keys} or q to quit")
        else:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while True:
                    key = sys.stdin.read(1).lower()
                    if key == 'q':
                        raise KeyboardInterrupt("User cancelled operation")
                    if key in valid_keys:
                        return key
                    print(f"Invalid key. Please press one of: {valid_keys} or q to quit")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        raise
    except Exception as e:
        print(f"\nInput error: {e}")
        raise

def anki_model_exists(model_name=CardModel.BASIC):
    try:
        response = requests.post(ANKI_CONNECT_URL, json={'action': 'modelNames', 'version': 6})
        result = response.json().get('result')
        return model_name in result if result else False
    except Exception:
        return False

def check_ankiconnect():
    try:
        response = requests.get(ANKI_CONNECT_URL, timeout=2)
        return response.status_code == 200
    except requests.ConnectionError:
        return False

def create_deck(deck_name):
    requests.post(ANKI_CONNECT_URL, json={'action': 'createDeck', 'version': 6, 'params': {'deck': deck_name}})

def detect_model(front_text):
    return CardModel.CLOZE if "{{c" in front_text else CardModel.BASIC

def check_deck_prefixes(rows, base_prefix):
    return all(row['Deck'].startswith(f"{base_prefix}::") or row['Deck'] == base_prefix for row in rows)

def suggest_base_deck(rows, default_base, headless=False):
    if headless:
        return default_base if default_base != '-' else None
    if check_deck_prefixes(rows, default_base):
        print(f"\nℹ️  All decks in CSV already contain '{default_base}' prefix")
        user_input = input("Would you like to skip adding base deck prefix? (Y/n): ").strip().lower()
        if user_input in ('', 'y'):
            return None
        return None if user_input == '-' else user_input
    else:
        user_input = input(f"\nEnter a base deck name (default = '{default_base}', or type '-' for none): ").strip()
        return default_base if user_input == '' else None if user_input == '-' else user_input

def get_all_existing_fronts_by_model(model):
    field_name = "Front" if model == CardModel.BASIC else "Text"
    response = requests.post(ANKI_CONNECT_URL, json={
        'action': 'findNotes',
        'version': 6,
        'params': {'query': f'{field_name}:*'}
    })
    note_ids = response.json().get('result', [])
    if not note_ids:
        return {}

    fetch_resp = requests.post(ANKI_CONNECT_URL, json={
        'action': 'notesInfo',
        'version': 6,
        'params': {'notes': note_ids}
    })
    notes_info = fetch_resp.json().get('result', [])
    existing = {}
    for note in notes_info:
        note_model = note['modelName']
        front = note['fields'].get("Front" if note_model == CardModel.BASIC else "Text", {}).get('value', '')
        back = note['fields'].get("Back" if note_model == CardModel.BASIC else "Back Extra", {}).get('value', '')
        note_id = note.get('noteId', 0)
        existing[front.strip()] = {'back': back.strip(), 'id': note_id}
    return existing

def delete_note(note_id):
    requests.post(ANKI_CONNECT_URL, json={
        'action': 'deleteNotes',
        'version': 6,
        'params': {'notes': [note_id]}
    })

def add_note(deck, front, back, ref, tags, model):
    fields = {
        'Front' if model == CardModel.BASIC else 'Text': front,
        'Back' if model == CardModel.BASIC else 'Back Extra': back,
        'Ref': ref,
        'Tags': ' '.join(tags)
    }
    response = requests.post(ANKI_CONNECT_URL, json={
        'action': 'addNote',
        'version': 6,
        'params': {
            'note': {
                'deckName': deck,
                'modelName': model,
                'fields': fields,
                'tags': tags,
                'options': {'allowDuplicate': True}
            }
        }
    })
    return response.json()

def preview_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames)
        if missing := REQUIRED_HEADERS - headers:
            print(f"Missing required columns: {', '.join(missing)}")
            return None, []
        rows = list(reader)
        for row in rows:
            if 'Tags' in row:
                row['Tags'] = row['Tags'].replace(',', ' ')
        return reader.fieldnames, rows

def summarize_deck(rows):
    decks = sorted({r['Deck'] for r in rows})
    model_counter = Counter(detect_model(r['Front']) for r in rows)
    tag_counter = Counter(tag for r in rows for tag in r['Tags'].split())

    print("\n=== Deck Hierarchy ===")
    for deck in decks:
        print(f"  - {deck}")
    print(f"\nTotal cards: {len(rows)}")
    print("\n=== Model Summary ===")
    for m, c in model_counter.items():
        print(f"  {m}: {c} cards")
    print("\n=== Tags ===")
    for tag, c in tag_counter.items():
        print(f"  #{tag} — {c}")

def print_user_message(arg0, arg1, arg2):
    print(arg0)
    print(f"{arg1}{len(arg2)}")
    print("----------------------------------------")


def import_from_rows(rows, base_deck=None, dry_run=False, cache_path=None):
    from tqdm import tqdm

    if os.path.exists(LOG_FILE_PATH):
        os.remove(LOG_FILE_PATH)

    is_preapproved = all('model' in r for r in rows)
    if is_preapproved and not dry_run:
        print_user_message(
            "\n🚀 Starting actual import of pre-approved notes...",
            '📦 Total cards to import: ',
            rows,
        )

    if is_preapproved:
        for idx, note in enumerate(rows, start=1):
            if note.get("replace_id"):
                delete_note(note["replace_id"])
            result = add_note(note["deck"], note["front"], note["back"], note["ref"], note["tags"], note["model"])
            status = "OK" if result.get('error') is None else result.get('error')
            print(f"{'✔️' if status == 'OK' else '❌'} [{idx}/{len(rows)}] {note['front'][:50]}... -> {status}")
        if not dry_run:
            print("\n✅ Import completed successfully!")
        return

    model_cache = {
        CardModel.BASIC: get_all_existing_fronts_by_model(CardModel.BASIC),
        CardModel.CLOZE: get_all_existing_fronts_by_model(CardModel.CLOZE)
    }

    allow_all = disallow_all = replace_all = False
    approved_notes = []

    print(f"\nProcessing {len(rows)} cards...")
    for idx, col in enumerate(rows, start=1):
        try:
            deck = col['Deck'].strip()
            if base_deck:
                deck = f"{base_deck}::{deck}"
            front = col['Front'].strip()
            back = col['Back'].strip()
            ref = col['Ref'].strip()
            tags = col['Tags'].split()
            model = detect_model(front)

            create_deck(deck)

            existing = model_cache[model].get(front)
            replace_id = None

            if existing and existing['back'] == back:
                print(f"🔁 [{idx}/{len(rows)}] Exact match, skipping: {front[:40]}")
                continue

            if dry_run and existing and not (allow_all or disallow_all or replace_all):
                print(f"\n⚠️ [{idx}/{len(rows)}] Duplicate found:")
                print(f"  Front: {front}")
                print(f"  Existing Back: {existing['back']}")
                print(f"  Proposed Back: {back}")
                try:
                    choice = get_single_key(
                        prompt="Add? [y]es, [n]o, [r]eplace, [Y]es to all, [N]o to all, [R]eplace to all",
                        valid_keys="ynrYNR"
                    )
                    if choice == 'n':
                        continue
                    elif choice == 'r':
                        replace_id = existing['id']
                    elif choice == 'Y':
                        allow_all = True
                    elif choice == 'N':
                        disallow_all = True
                        continue
                    elif choice == 'R':
                        replace_all = True
                        replace_id = existing['id']
                except KeyboardInterrupt:
                    print("\nImport cancelled by user")
                    return
                except Exception as e:
                    print(f"Error getting user input: {e}, skipping card")
                    continue
            elif disallow_all and existing:
                continue
            elif replace_all and existing:
                replace_id = existing['id']

            if dry_run:
                print(f"✔️ [{idx}/{len(rows)}] Add: '{front[:40]}' → '{back[:40]}' to {deck}")

            approved_notes.append({
                "deck": deck,
                "front": front,
                "back": back,
                "ref": ref,
                "tags": tags,
                "model": model,
                "replace_id": replace_id
            })

        except Exception as e:
            print(f"❌ Error processing card {idx}: {e}")

    if dry_run and cache_path:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(approved_notes, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Dry run results saved to: {cache_path}")
        except Exception as e:
            print(f"⚠️ Could not save approved cards: {e}")
    elif not dry_run:
        perform_import(approved_notes, tqdm)


# TODO Rename this here and in `import_from_rows`
def perform_import(approved_notes, tqdm):
    print_user_message(
        "\n🚀 Starting actual import...",
        '📋 Total cards to process: ',
        approved_notes,
    )
    success_count = 0
    error_count = 0
    with tqdm(total=len(approved_notes), desc="Importing cards", unit="card") as pbar:
        for idx, note in enumerate(approved_notes, start=1):
            try:
                if note.get("replace_id"):
                    delete_note(note["replace_id"])
                result = add_note(note["deck"], note["front"], note["back"],
                                  note["ref"], note["tags"], note["model"])
                if result.get('error'):
                    error_count += 1
                    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log:
                        log.write(f"Card {idx} failed - {note['front'][:50]}...: {result['error']}\n")
                else:
                    success_count += 1
                pbar.update(1)
            except Exception as e:
                error_count += 1
                with open(LOG_FILE_PATH, "a", encoding="utf-8") as log:
                    log.write(f"Card {idx} crashed - {note['front'][:50]}...: {e}\n")
                pbar.update(1)

    print("\n✅ Import completed!")
    print("========================================")
    print(f"Total cards processed: {len(approved_notes)}")
    print(f"Successfully imported: {success_count}")
    print(f"Errors encountered: {error_count}")
    if error_count > 0:
        print(f"\n⚠️ See '{LOG_FILE_PATH}' for error details.")
