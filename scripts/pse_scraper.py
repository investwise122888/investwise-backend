import os
import json
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

# Get Google Sheet CSV URL from environment
CSV_URL = os.getenv("GOOGLE_SHEET_CSV_URL")
if not CSV_URL:
    raise RuntimeError("GOOGLE_SHEET_CSV_URL missing")

def fetch_csv_data():
    """Download CSV from Google Sheets and parse rows."""
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    lines = resp.text.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("CSV has no data rows")
    headers = [h.strip().lower() for h in lines[0].split(",")]
    # Expected columns: symbol, date, open, high, low, close, volume
    required = ["symbol", "date", "open", "high", "low", "close", "volume"]
    for req in required:
        if req not in headers:
            raise ValueError(f"Missing required column: {req}")
    # Map header to index
    idx = {h: i for i, h in enumerate(headers)}
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < len(headers):
            continue
        row = {
            "symbol": parts[idx["symbol"]].strip().upper(),
            "date": parts[idx["date"]].strip(),
            "open": float(parts[idx["open"]]),
            "high": float(parts[idx["high"]]),
            "low": float(parts[idx["low"]]),
            "close": float(parts[idx["close"]]),
            "volume": int(float(parts[idx["volume"]]))
        }
        rows.append(row)
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
    print("Starting scraper from Google Sheets CSV...")
    try:
        rows = fetch_csv_data()
        print(f"Loaded {len(rows)} rows from CSV")
        for row in rows:
            # Each row becomes a weekly entry
            entry = {
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "change_percent": 0.0  # compute later if needed
            }
            update_firestore(row["symbol"], entry)
        print("Scraper finished successfully.")
    except Exception as e:
        print(f"Scraper failed: {e}")
        raise

if __name__ == "__main__":
    main()
