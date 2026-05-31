from datetime import datetime, timedelta
from app.services.real_stock_fetcher import BLUE_CHIPS
from app.database import db
from app.models import PREDICTIONS_COLLECTION

PH_BLUE_CHIPS = BLUE_CHIPS

def get_latest_predictions_from_firestore() -> list:
    """Retrieve the most recent prediction per symbol (last 7 days) with strength fields."""
    results = []
    for symbol in BLUE_CHIPS:
        found = False
        for days_back in range(0, 8):
            date_str = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            doc = db.collection(PREDICTIONS_COLLECTION).document(f"{symbol}_{date_str}").get()
            if doc.exists:
                data = doc.to_dict()
                signal = data.get("persistent_signal") or data.get("signal", "HOLD")
                results.append({
                    "symbol": data["symbol"],
                    "price": data.get("price"),
                    "change_percent": data.get("change_percent"),
                    "signal": signal,
                    "explanation": data.get("explanation", "No data"),
                    "fundamental_veto": data.get("fundamental_veto", False),
                    "pe_ratio": data.get("pe_ratio"),
                    "fundamentals_pass": data.get("fundamentals_pass"),
                    "strength_score": data.get("strength_score", 0),
                    "strength_label": data.get("strength_label", "")
                })
                found = True
                break
        if not found:
            results.append({
                "symbol": symbol,
                "price": None,
                "change_percent": None,
                "signal": "HOLD",
                "explanation": "Awaiting weekly update",
                "fundamental_veto": False,
                "pe_ratio": None,
                "fundamentals_pass": None,
                "strength_score": 0,
                "strength_label": ""
            })
    return results

def get_all_predictions():
    return get_latest_predictions_from_firestore()

def save_predictions_to_firestore(predictions_list):
    pass
