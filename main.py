import argparse
import json
import os
import sys
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename

from utils import (
    preview_csv,
    summarize_deck,
    suggest_base_deck,
    anki_model_exists,
    import_from_rows,
    LOG_FILE_PATH,
    safe_input
)

DEFAULT_CSV_ROOT = 'P:/@SYNC/@_ATPL/@SUMMARIES'
DEFAULT_BASE_DECK = 'ATPL'

def get_cache_path(csv_path: str) -> str:
    return f"{os.path.splitext(csv_path)[0]}_approved.json"

def main(args):
    def process_file(path):
        cache_file = get_cache_path(path)
        use_cache = None

        if os.path.exists(cache_file) and not args.use_cache:
            try:
                use_cache = safe_input(f"\nFound previously approved cards in '{cache_file}'. Use these? [Y/n] ", default='y')
            except KeyboardInterrupt:
                return
        if use_cache != 'n':
            args.use_cache = cache_file

        if args.use_cache:
            try:
                with open(args.use_cache, encoding="utf-8") as f:
                    approved = json.load(f)
                print(f"\U0001F4E6 Importing {len(approved)} pre-approved notes from cache...")
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

        try:
            base_deck = suggest_base_deck(rows, args.base_deck, args.headless)
        except KeyboardInterrupt:
            return

        if not anki_model_exists("Basic") or not anki_model_exists("Cloze"):
            print("⚠️ Error: Required Anki models ('Basic' and/or 'Cloze') are not found.")
            exit()

        dry_run = args.dry_run
        if not args.headless and not dry_run:
            try:
                dry_run_choice = safe_input("Would you like to do a dry run (Y/n)?", default='y')
                dry_run = dry_run_choice != 'n'
            except KeyboardInterrupt:
                return

        print("\nStarting import...")
        if dry_run:
            print("\U0001F50D Beginning dry run summary:")
            try:
                import_from_rows(rows, base_deck, dry_run=True, cache_path=cache_file)
            except KeyboardInterrupt:
                print("\n❌ Dry run cancelled by user.")
                return

            if not args.headless:
                try:
                    save_cache = safe_input("\nSave these approved cards for future imports? (Y/n):", default='y')
                    if save_cache != 'n':
                        print(f"✅ Approved cards saved to: {cache_file}")
                    else:
                        try:
                            os.remove(cache_file)
                        except FileNotFoundError:
                            pass

                    proceed = safe_input("\nDry run complete. Proceed with actual import? (y/n):", default='n')
                    if proceed == 'y':
                        import_from_rows(rows, base_deck, dry_run=False)
                    else:
                        print("Import cancelled.")
                except KeyboardInterrupt:
                    return
        else:
            import_from_rows(rows, base_deck, dry_run=False)

        if os.path.exists(LOG_FILE_PATH):
            print(f"\n⚠️ Some cards were skipped or failed. See '{LOG_FILE_PATH}' for details.")

    try:
        if args.file:
            process_file(args.file)
        elif args.folder:
            for root, _, files in os.walk(args.folder):
                for file in files:
                    if file.endswith('.csv'):
                        process_file(os.path.join(root, file))
        else:
            print("\nSelect the CSV file to import into Anki...")
            Tk().withdraw()
            try:
                file_path = askopenfilename(
                    initialdir=DEFAULT_CSV_ROOT,
                    filetypes=[('CSV Files', '*.csv')],
                    title="Select Anki Import CSV"
                )
                if file_path:
                    process_file(file_path)
                else:
                    print("No file selected. Operation cancelled.")
            except Exception as e:
                print(f"❌ Error selecting file: {e}")
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Import decks from CSV into Anki via AnkiConnect.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
Example usage:
  python main.py --file questions.csv --dry-run
  python main.py --folder ./exports --base-deck MyDeck
        """
    )
    parser.add_argument("--file", help="Import a single CSV file")
    parser.add_argument("--folder", help="Import all CSV files in a folder")
    parser.add_argument("--base-deck", help="Prefix deck name (e.g. 'ATPL')", default=DEFAULT_BASE_DECK)
    parser.add_argument("--dry-run", action="store_true", help="Run without inserting cards, only preview what would be done")
    parser.add_argument("--dry-run-save", help="If set, saves approved cards from dry run to a JSON file")
    parser.add_argument("--use-cache", help="Instead of CSV, import from a previously saved dry-run cache (JSON file)")
    parser.add_argument("--headless", action="store_true", help="Run fully from command line without user prompts")
    parser.add_argument("--overwrite-all", action="store_true", help="Automatically replace all duplicate cards without asking")

    args = parser.parse_args()
    main(args)
