import os
import json
import requests
from datetime import datetime, timedelta   # <-- added timedelta here
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Firebase Initialization ----------
def init_firebase():
    """Initialize Firebase Admin SDK using GitHub secret."""
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT environment variable not set")
    cred_dict = json.loads(sa_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")

init_firebase()
db = firestore.client()

# ---------- Configuration ----------
BLUE_CHIPS = ["AC", "SM", "BDO", "JFC", "TEL", "MER", "GLO", "ALI", "AEV", "MBT"]
PSE_API_URL = "https://edge.pse.com.ph/companyInfo/ajax_stockData.ax?securitySymbol={symbol}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://edge.pse.com.ph/"
}

def scrape_symbol(symbol: str):
    """Fetch OHLCV data for a single symbol from PSE Edge."""
    url = PSE_API_URL.format(symbol=symbol)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": float(data.get("lastTradedPrice", 0)),
            "volume": int(data.get("totalVolume", 0)),
            "change_percent": float(data.get("percentChange", 0)),
        }
    except Exception as e:
        print(f"Error scraping {symbol}: {e}")
        return None

def update_firestore(symbol: str, new_data: dict):
    """Append weekly data to Firestore array (keep last 260 weeks)."""
    doc_ref = db.collection("price_history").document(symbol)
    doc = doc_ref.get()
    if doc.exists:
        weekly = doc.to_dict().get("weekly", [])
    else:
        weekly = []

    # Align to previous Monday
    today = datetime.utcnow()
    days_since_monday = today.weekday()  # Monday=0
    monday = today - timedelta(days=days_since_monday)
    date_str = monday.strftime("%Y-%m-%d")

    # Remove existing entry for same date (avoid duplicates)
    weekly = [w for w in weekly if w.get("date") != date_str]

    new_entry = {
        "date": date_str,
        "open": new_data["open"],
        "high": new_data["high"],
        "low": new_data["low"],
        "close": new_data["close"],
        "volume": new_data["volume"],
        "change_percent": new_data["change_percent"]
    }
    weekly.append(new_entry)
    # Keep last 260 weeks (~5 years)
    weekly = weekly[-260:]

    doc_ref.set({
        "symbol": symbol,
        "last_updated": firestore.SERVER_TIMESTAMP,
        "weekly": weekly
    }, merge=True)
    print(f"Updated {symbol}: close = {new_data['close']}")

def main():
    print("Starting PSE scraper...")
    for symbol in BLUE_CHIPS:
        data = scrape_symbol(symbol)
        if data:
            update_firestore(symbol, data)
        else:
            print(f"Skipping {symbol} due to error")
    print("Scraper finished.")

if __name__ == "__main__":
    main()
