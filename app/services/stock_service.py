from datetime import datetime, timedelta
from app.services.real_stock_fetcher import BLUE_CHIPS
from app.database import db
from app.models import PREDICTIONS_COLLECTION

PH_BLUE_CHIPS = BLUE_CHIPS

def get_latest_predictions_from_firestore() -> list:
    """Retrieve the most recent prediction per symbol (last 7 days). No composite index needed."""
    results = []
    for symbol in BLUE_CHIPS:
        found = False
        for days_back in range(0, 8):  # check today back to 7 days ago
            date_str = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            doc = db.collection(PREDICTIONS_COLLECTION).document(f"{symbol}_{date_str}").get()
            if doc.exists:
                data = doc.to_dict()
                # Use persistent_signal if available, else fallback to 'signal' field
                signal = data.get("persistent_signal") or data.get("signal", "NEUTRAL")
                results.append({
                    "symbol": data["symbol"],
                    "price": data.get("price"),
                    "change_percent": data.get("change_percent"),
                    "signal": signal,
                    "explanation": data.get("explanation", "No data")
                })
                found = True
                break
        if not found:
            results.append({
                "symbol": symbol,
                "price": None,
                "change_percent": None,
                "signal": "NEUTRAL",
                "explanation": "Awaiting weekly update"
            })
    return results

def get_all_predictions():
    """Public API endpoint – returns cached Firestore predictions (latest)."""
    return get_latest_predictions_from_firestore()

def save_predictions_to_firestore(predictions_list):
    """Legacy function kept for compatibility; actual saving done by weekly_signal_service."""
    pass
