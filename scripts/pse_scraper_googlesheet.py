import os
import json
import csv
import io
import requests
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Firebase Initialization ----------
def init_firebase():
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT missing")
    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred)

init_firebase()
db = firestore.client()

# Get Google Sheet CSV/TSV URL from environment
CSV_URL = os.getenv("GOOGLE_SHEET_CSV_URL")
if not CSV_URL:
    raise RuntimeError("GOOGLE_SHEET_CSV_URL missing")

# ---------- Helper functions ----------
def clean_number(val: str):
    """Convert to float, handling commas and quotes. Return None on failure."""
    if not val or val.strip() == "":
        return None
    try:
        # Remove commas, quotes, and whitespace
        cleaned = str(val).replace(',', '').replace('"', '').strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None

def safe_str(val: str) -> str:
    """Return stripped string or empty string."""
    return str(val).strip() if val else ""

# ---------- Data fetching and parsing ----------
def fetch_csv_data():
    """Download from Google Sheets and parse rows.
    Handles both CSV and TSV formats. Skips rows with missing or invalid numeric data.
    """
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise ValueError("Empty response from Google Sheets")

    # Auto-detect delimiter
    first_line = text.split("\n")[0]
    delimiter = "\t" if "\t" in first_line else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    # Normalize header names (lowercase, trim)
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

    required = ["symbol", "open", "high", "low", "close", "volume"]
    for req in required:
        if req not in reader.fieldnames:
            raise ValueError(f"Missing required column: {req}")

    rows = []
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    for row_num, row in enumerate(reader, start=2):  # row 1 is header
        symbol = safe_str(row.get("symbol", ""))
        if not symbol:
            print(f"Row {row_num}: Skipped (empty symbol)")
            continue

        # Convert numeric fields, skip on failure
        open_val = clean_number(row.get("open", ""))
        high_val = clean_number(row.get("high", ""))
        low_val = clean_number(row.get("low", ""))
        close_val = clean_number(row.get("close", ""))
        volume_val = clean_number(row.get("volume", ""))

        if None in [open_val, high_val, low_val, close_val, volume_val]:
            missing = []
            if open_val is None: missing.append("open")
            if high_val is None: missing.append("high")
            if low_val is None: missing.append("low")
            if close_val is None: missing.append("close")
            if volume_val is None: missing.append("volume")
            print(f"Row {row_num} (symbol {symbol}): Skipped due to invalid numeric data in fields: {missing}")
            continue

        rows.append({
            "symbol": symbol.upper(),
            "date": current_date,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": int(volume_val)
        })

    print(f"Loaded {len(rows)} valid rows from {len(reader.fieldnames)} columns")
    return rows

# ---------- Firestore update ----------
def update_firestore(symbol, entry):
    """Append weekly entry to price_history document."""
    ref = db.collection("price_history").document(symbol)
    doc = ref.get()
    if doc.exists:
        weekly = doc.to_dict().get("weekly", [])
    else:
        weekly = []
    # Remove existing entry with same date (avoid duplicates)
    weekly = [w for w in weekly if w.get("date") != entry["date"]]
    weekly.append(entry)
    # Keep only last 260 weeks (~5 years)
    weekly = weekly[-260:]
    ref.set({
        "symbol": symbol,
        "last_updated": firestore.SERVER_TIMESTAMP,
        "weekly": weekly
    }, merge=True)
    print(f"Updated {symbol} for date {entry['date']}")

# ---------- Main ----------
def main():
    print("Starting Google Sheets scraper (robust mode)...")
    try:
        rows = fetch_csv_data()
        for row in rows:
            entry = {
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "change_percent": 0.0  # placeholder, not used
            }
            update_firestore(row["symbol"], entry)
        print("Scraper finished successfully.")
    except Exception as e:
        print(f"Scraper failed: {e}")
        raise

if __name__ == "__main__":
    main()