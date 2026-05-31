import os
import json
import requests
from datetime import datetime, timedelta
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

BLUE_CHIPS = ["AC","SM","BDO","JFC","TEL","MER","GLO","ALI","AEV","MBT"]
URL = "https://edge.pse.com.ph/companyInfo/ajax_stockData.ax?securitySymbol={symbol}"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://edge.pse.com.ph/"
}

def scrape(symbol):
    try:
        r = requests.get(URL.format(symbol=symbol), headers=HEADERS, timeout=15)
        r.raise_for_status()
        d = r.json()
        return {
            "open": float(d.get("open", 0)),
            "high": float(d.get("high", 0)),
            "low": float(d.get("low", 0)),
            "close": float(d.get("lastTradedPrice", 0)),
            "volume": int(d.get("totalVolume", 0)),
            "change_percent": float(d.get("percentChange", 0))
        }
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None

def update(symbol, data):
    ref = db.collection("price_history").document(symbol)
    doc = ref.get()
    weekly = doc.to_dict().get("weekly", []) if doc.exists else []
    today = datetime.utcnow()
    monday = today - timedelta(days=today.weekday())
    date_str = monday.strftime("%Y-%m-%d")
    weekly = [w for w in weekly if w.get("date") != date_str]
    weekly.append({"date": date_str, **data})
    weekly = weekly[-260:]
    ref.set({
        "symbol": symbol,
        "last_updated": firestore.SERVER_TIMESTAMP,
        "weekly": weekly
    }, merge=True)
    print(f"Updated {symbol}: close={data['close']}")

def main():
    print("Starting scraper...")
    for s in BLUE_CHIPS:
        d = scrape(s)
        if d:
            update(s, d)
        else:
            print(f"Skipping {s}")
    print("Done.")

if __name__ == "__main__":
    main()
