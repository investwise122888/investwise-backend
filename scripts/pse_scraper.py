import os
import json
import csv
import io
import requests
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

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

def fetch_csv_data():
    """Download from Google Sheets and parse rows using csv module.
    Handles both CSV and TSV formats and quoted fields like "1,184.00"."""
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    text = resp.text.strip()

    # Auto-detect delimiter
    first_line = text.split("\n")[0]
    delimiter = "\t" if "\t" in first_line else ","

    def clean(val: str) -> str:
        return val.replace('"', '').replace(',', '').strip()

    def clean_number(val: str) -> float:
        return float(clean(val))

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    # Normalize header names
    reader.fieldnames = [clean(h).lower() for h in reader.fieldnames]

    required = ["symbol", "open", "high", "low", "close", "volume"]
    for req in required:
        if req not in reader.fieldnames:
            raise ValueError(f"Missing required column: {req}")

    rows = []
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    for row in reader:
        if not row.get("symbol", "").strip():
            continue
        rows.append({
            "symbol": clean(row["symbol"]).upper(),
            "date":   current_date,
            "open":   clean_number(row["open"]),
            "high":   clean_number(row["high"]),
            "low":    clean_number(row["low"]),
            "close":  clean_number(row["close"]),
            "volume": int(clean_number(row["volume"]))
        })
    return rows

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
    # Keep only last 260 entries (~5 years)
    weekly = weekly[-260:]
    ref.set({
        "symbol": symbol,
        "last_updated": firestore.SERVER_TIMESTAMP,
        "weekly": weekly
    }, merge=True)
    print(f"Updated {symbol} for date {entry['date']}")

def main():
    print("Starting scraper from Google Sheets CSV/TSV...")
    try:
        rows = fetch_csv_data()
        print(f"Loaded {len(rows)} rows from data source")
        for row in rows:
            entry = {
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "change_percent": 0.0
            }
            update_firestore(row["symbol"], entry)
        print("Scraper finished successfully.")
    except Exception as e:
        print(f"Scraper failed: {e}")
        raise

if __name__ == "__main__":
    main()
