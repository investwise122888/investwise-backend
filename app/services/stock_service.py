from datetime import datetime, timedelta
from app.services.real_stock_fetcher import BLUE_CHIPS
from app.database import db
from app.models import PREDICTIONS_COLLECTION

def get_latest_predictions_from_firestore() -> list:
    """Retrieve today's predictions from Firestore."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    results = []
    for symbol in BLUE_CHIPS:
        doc_id = f"{symbol}_{today_str}"
        doc = db.collection(PREDICTIONS_COLLECTION).document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            results.append({
                "symbol": data["symbol"],
                "price": data.get("price"),
                "change_percent": data.get("change_percent"),
                "signal": data.get("signal", "NEUTRAL"),
                "explanation": data.get("explanation", "No data")
            })
        else:
            # If no prediction for today, try yesterday's as fallback
            yesterday = (datetime.utcnow().replace(hour=0, minute=0, second=0) - timedelta(days=1)).strftime("%Y-%m-%d")
            doc_yest = db.collection(PREDICTIONS_COLLECTION).document(f"{symbol}_{yesterday}").get()
            if doc_yest.exists:
                data = doc_yest.to_dict()
                results.append({
                    "symbol": symbol,
                    "price": data.get("price"),
                    "change_percent": data.get("change_percent"),
                    "signal": data.get("signal", "NEUTRAL"),
                    "explanation": "Previous day data (market closed)"
                })
            else:
                results.append({
                    "symbol": symbol,
                    "price": None,
                    "change_percent": None,
                    "signal": "NEUTRAL",
                    "explanation": "Awaiting daily update"
                })
    return results

def get_all_predictions():
    """Public API endpoint – returns cached Firestore predictions."""
    return get_latest_predictions_from_firestore()
