import csv
import argparse
import json
import requests
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from collections import Counter
import os, sys
from tqdm import tqdm

anki_connect = 'http://localhost:8765'
default_csv_root = 'P:/@SYNC/@_ATPL/@SUMMARIES'
default_base_deck = 'ATPL'
required_headers = {'Deck', 'Front', 'Back', 'Ref', 'Tags'}
log_file_path = "anki_import_log.txt"

def anki_model_exists(model_name="Basic"):
    response = requests.post(anki_connect, json={'action': 'modelNames', 'version': 6})
    return model_name in response.json().get('result', [])

def check_ankiconnect():
    try:
        response = requests.get(anki_connect, timeout=2)
        return response.status_code == 200
    except requests.ConnectionError:
        return False
    
def create_deck(deck_name):
    requests.post(anki_connect, json={'action': 'createDeck', 'version': 6, 'params': {'deck': deck_name}})

def detect_model(front_text):
    return "Cloze" if "{{c" in front_text else "Basic"

def check_deck_prefixes(rows, base_prefix):
    """Check if all decks already contain the specified prefix"""
    return all(
        row['Deck'].startswith(f"{base_prefix}::") or 
        row['Deck'] == base_prefix
        for row in rows
    )

def suggest_base_deck(rows, default_base, headless=False):
    """Suggest base deck handling based on existing prefixes"""
    if headless:
        return default_base if default_base != '-' else None
        
    if check_deck_prefixes(rows, default_base):
        print(f"\nℹ️  All decks in CSV already contain '{default_base}' prefix")
        user_input = input("Would you like to skip adding base deck prefix? (Y/n): ").strip().lower()
        if user_input in ('', 'y'):
            return None
        else:
            user_input = input(f"Enter a different base deck name (or '-' for none): ").strip()
            return None if user_input.lower() == '-' else user_input
    else:
        user_input = input(f"\nEnter a base deck name (default = '{default_base}', or type '-' for none): ").strip()
        return default_base if user_input == '' else None if user_input.lower() == '-' else user_input

def get_all_existing_fronts_by_model(model):
    field_name = "Front" if model == "Basic" else "Text"
    response = requests.post(anki_connect, json={
        'action': 'findNotes',
        'version': 6,
        'params': {'query': f'{field_name}:*'}
    })
    note_ids = response.json().get('result', [])
    if not note_ids:
        return {}

    fetch_resp = requests.post(anki_connect, json={
        'action': 'notesInfo',
        'version': 6,
        'params': {'notes': note_ids}
    })
    notes_info = fetch_resp.json().get('result', [])
    existing = {}
    for note in notes_info:
        note_model = note['modelName']
        front_field = note['fields'].get("Front" if note_model == "Basic" else "Text", {}).get('value', '')
        back_field = note['fields'].get("Back" if note_model == "Basic" else "Back Extra", {}).get('value', '')
        note_id = note.get('noteId', 0)
        existing[front_field.strip()] = {'back': back_field.strip(), 'id': note_id}
    return existing

def delete_note(note_id):
    requests.post(anki_connect, json={
        'action': 'deleteNotes',
        'version': 6,
        'params': {'notes': [note_id]}
    })

def add_note(deck, front, back, ref, tags, model):
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
                'options': {'allowDuplicate': True}
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

        for row in rows:
            if 'Tags' in row and ',' in row['Tags']:
                row['Tags'] = row['Tags'].replace(',', ' ')
        return reader.fieldnames, rows

def summarize_deck(rows):
    decks = sorted(set(row['Deck'] for row in rows))
    tags_counter = Counter(tag for row in rows for tag in row['Tags'].split())
    model_counter = Counter(detect_model(row['Front']) for row in rows)

    print("\n=== Deck Hierarchy ===")
    for deck in decks:
        print(f"  - {deck}")
    print(f"\nTotal cards: {len(rows)}")
    print(f"Unique decks: {len(decks)}")

    print("\n=== Card Model Summary ===")
    for model, count in model_counter.items():
        print(f"  {model}: {count} cards")

    print("\n=== Tag Summary ===")
    for tag, count in tags_counter.items():
        print(f"  #{tag} — {count} cards")


def import_from_rows(rows, base_deck=None, dry_run=False, cache_path=None):
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    is_preapproved = all('model' in r for r in rows)

    if is_preapproved and not dry_run:
        print("\n🚀 Starting actual import of pre-approved notes...")
        print(f"📦 Total cards to import: {len(rows)}")
        print("----------------------------------------")
        
    if is_preapproved:
        # Fast path: use approved notes
        for idx, note in enumerate(rows, start=1):
            if note.get("replace_id"):
                delete_note(note["replace_id"])
            result = add_note(note["deck"], note["front"], note["back"], note["ref"], note["tags"], note["model"])
            status = "OK" if result.get('error') is None else result.get('error')
            print(f"{'✔️' if status == 'OK' else '❌'} [{idx}/{len(rows)}] {note['front'][:50]}... -> {status}")
        if not dry_run:
            print("\n✅ Import completed successfully!")
        return

    model_cache = {"Basic": get_all_existing_fronts_by_model("Basic"),
                   "Cloze": get_all_existing_fronts_by_model("Cloze")}

    allow_all = False
    disallow_all = False
    replace_all = False

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
                choice = input("Add? [y]es / [n]o / [r]eplace / [Y]es to all / [N]o to all, / [R]eplace all: ").strip()
                if choice == 'n':  # No (lowercase)
                    continue
                elif choice == 'y':  # Yes (lowercase)
                    pass  # proceed normally
                elif choice == 'r':  # Replace (lowercase)
                    replace_id = existing['id']
                elif choice == 'Y':  # Yes to all (uppercase)
                    allow_all = True
                elif choice == 'N':  # No to all (uppercase)
                    disallow_all = True
                    continue
                elif choice == 'R':  # Replace to all (uppercase)
                    replace_all = True
                    replace_id = existing['id']
                else:  # Default action if invalid input
                    print("Invalid choice, skipping by default.")
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
        print("\n🚀 Starting actual import...")
        print(f"📋 Total cards to process: {len(approved_notes)}")
        print("----------------------------------------")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        # Initialize progress bar
        with tqdm(total=len(approved_notes), desc="Importing cards", unit="card") as pbar:
            for idx, note in enumerate(approved_notes, start=1):
                try:
                    if note.get("replace_id"):
                        delete_note(note["replace_id"])
                    
                    result = add_note(note["deck"], note["front"], note["back"], 
                                    note["ref"], note["tags"], note["model"])
                    
                    if result.get('error'):
                        error_count += 1
                        with open(log_file_path, "a", encoding="utf-8") as log_file:
                            log_file.write(f"Card {idx} failed - {note['front'][:50]}...: {result.get('error')}\n")
                    else:
                        success_count += 1
                    
                    # Update progress bar description with current card info
                    pbar.set_postfix({
                        "current": note['front'][:30]+"...",
                        "success": success_count,
                        "errors": error_count
                    })
                    pbar.update(1)
                    
                except Exception as e:
                    error_count += 1
                    with open(log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"Card {idx} crashed - {note['front'][:50]}...: {str(e)}\n")
                    pbar.update(1)
        
        # Final summary
        print("\n✅ Import completed!")
        print("========================================")
        print(f"Total cards processed: {len(approved_notes)}")
        print(f"Successfully imported: {success_count}")
        print(f"Skipped duplicates: {skip_count}")
        print(f"Errors encountered: {error_count}")
        
        if error_count > 0:
            print(f"\n⚠️ See '{log_file_path}' for error details.")


def main(args):
    def process_file(path):
        # Check for existing approved cards cache
        cache_file = f"{os.path.splitext(path)[0]}_approved.json"
        # Initialize use_cache variable
        use_cache = None

        if os.path.exists(cache_file) and not args.use_cache:
            use_cache = input(f"\nFound previously approved cards in '{cache_file}'. Use these? [Y/n] ").strip().lower()
        if use_cache != 'n':  # Default to Yes
            args.use_cache = cache_file
        
        if args.use_cache:
            try:
                with open(args.use_cache, encoding="utf-8") as f:
                    approved = json.load(f)
                print(f"📦 Importing {len(approved)} pre-approved notes from cache...")
                import_from_rows(approved, dry_run=False)
                return
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}. Proceeding with normal import.")

        headers, rows = preview_csv(path)
        if not rows:
            print(f"⚠️ No rows in file: {path}")
            return

        first_deck = rows[0]['Deck']
        print(f"\nFile: {path}")
        print(f"First deck entry: '{first_deck}'")
        summarize_deck(rows)

        base_deck = suggest_base_deck(rows, args.base_deck, args.headless)

        if not anki_model_exists("Basic") or not anki_model_exists("Cloze"):
            print("⚠️ Error: Required Anki models ('Basic' and/or 'Cloze') are not found.")
            exit()

        dry_run = args.dry_run
        if not args.headless and not dry_run:
            dry_run_choice = input("Would you like to do a dry run (Y/n)? ").strip().lower()
            dry_run = dry_run_choice != 'n'

        print("\nStarting import...")
        if dry_run:
            print("🔍 Beginning dry run summary:")
            import_from_rows(rows, base_deck, dry_run=True, cache_path=cache_file)
            
            if not args.headless:
                save_cache = input("\nSave these approved cards for future imports? (Y/n): ").strip().lower()
                if save_cache != 'n':
                    print(f"✅ Approved cards saved to: {cache_file}")
                else:
                    try:
                        os.remove(cache_file)
                    except FileNotFoundError:
                        pass
                    
                proceed = input("\nDry run complete. Proceed with actual import? (y/n): ").strip().lower()
                if proceed == 'y':
                    import_from_rows(rows, base_deck, dry_run=False)
                else:
                    print("Import cancelled.")
        else:
            import_from_rows(rows, base_deck, dry_run=False)

        if os.path.exists(log_file_path):
            print(f"\n⚠️ Some cards were skipped or failed. See '{log_file_path}' for details.")    

    # If file/folder specified, process them
    if args.file:
        process_file(args.file)
    elif args.folder:
        for root, _, files in os.walk(args.folder):
            for file in files:
                if file.endswith('.csv'):
                    process_file(os.path.join(root, file))
    else:
        # Interactive mode - ask user to select file
        print("\nSelect the CSV file to import into Anki...")
        Tk().withdraw()  # Hide the root window
        try:
            file_path = askopenfilename(
                initialdir=default_csv_root,
                filetypes=[('CSV Files', '*.csv')],
                title="Select Anki Import CSV"
            )
            if file_path:
                process_file(file_path)
            else:
                print("No file selected. Operation cancelled.")
        except Exception as e:
            print(f"❌ Error selecting file: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Import decks from CSV into Anki via AnkiConnect.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--file", help="Import a single CSV file")
    parser.add_argument("--folder", help="Import all CSV files in a folder")
    parser.add_argument("--base-deck", help="Prefix deck name (e.g. 'ATPL')", default=default_base_deck)
    parser.add_argument("--dry-run", action="store_true", help="Run without inserting cards, only preview what would be done")
    parser.add_argument("--dry-run-save", help="If set, saves approved cards from dry run to a JSON file")
    parser.add_argument("--use-cache", help="Instead of CSV, import from a previously saved dry-run cache (JSON file)")
    parser.add_argument("--headless", action="store_true", help="Run fully from command line without user prompts")
    parser.add_argument("--overwrite-all", action="store_true", help="Automatically replace all duplicate cards without asking")

    args = parser.parse_args()
    main(args)