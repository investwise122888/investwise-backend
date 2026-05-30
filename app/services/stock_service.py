from datetime import datetime, timedelta
from app.services.real_stock_fetcher import BLUE_CHIPS
from app.database import db
from app.models import PREDICTIONS_COLLECTION

PH_BLUE_CHIPS = BLUE_CHIPS

def get_latest_predictions_from_firestore() -> list:
    """Retrieve the most recent available predictions for each symbol."""
    results = []
    for symbol in BLUE_CHIPS:
        # Query the latest document for this symbol, ordered by generated_at descending
        docs = (db.collection(PREDICTIONS_COLLECTION)
                .where("symbol", "==", symbol)
                .order_by("generated_at", direction="DESCENDING")
                .limit(1)
                .stream())
        latest_doc = next(docs, None)
        
        if latest_doc:
            data = latest_doc.to_dict()
            # Use persistent_signal if available, else fallback to 'signal' field
            signal = data.get("persistent_signal") or data.get("signal", "NEUTRAL")
            results.append({
                "symbol": data["symbol"],
                "price": data.get("price"),
                "change_percent": data.get("change_percent"),
                "signal": signal,
                "explanation": data.get("explanation", "No data")
            })
        else:
            # No data at all for this symbol
            results.append({
                "symbol": symbol,
                "price": None,
                "change_percent": None,
                "signal": "NEUTRAL",
                "explanation": "No signal data available yet"
            })
    return results

def get_all_predictions():
    """Public API endpoint – returns cached Firestore predictions (latest)."""
    return get_latest_predictions_from_firestore()

def save_predictions_to_firestore(predictions_list):
    """Legacy function kept for compatibility; actual saving done by weekly_signal_service."""
    pass
