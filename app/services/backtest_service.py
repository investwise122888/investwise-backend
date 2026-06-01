import logging
from datetime import datetime
from app.database import db

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "backtest_cache"

async def compute_backtest_stats(holding_weeks: int = 4):
    cache_doc = db.collection(CACHE_COLLECTION).document(f"stats_{holding_weeks}w")
    cached = cache_doc.get()
    if cached.exists:
        data = cached.to_dict()
        computed_at = data.get("computed_at")
        if computed_at and (datetime.utcnow() - computed_at.replace(tzinfo=None)).total_seconds() < 86400:
            return data

    signals = []
    docs = db.collection("signal_log").where("signal", "in", ["BUY", "SELL"]).stream()
    for doc in docs:
        signals.append(doc.to_dict())

    results = []
    for sig in signals:
        symbol = sig["symbol"]
        signal_date = sig["generated_at"].date()
        price_doc = db.collection("price_history").document(symbol).get()
        if not price_doc.exists:
            continue
        weekly = price_doc.to_dict().get("weekly", [])
        weeks_data = []
        for entry in weekly:
            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            weeks_data.append({"date": entry_date, "close": entry["close"]})
        weeks_data.sort(key=lambda x: x["date"])
        signal_idx = None
        for i, w in enumerate(weeks_data):
            if w["date"] >= signal_date:
                signal_idx = i
                break
        if signal_idx is None or signal_idx + holding_weeks >= len(weeks_data):
            continue
        entry_price = weeks_data[signal_idx]["close"]
        exit_price = weeks_data[signal_idx + holding_weeks]["close"]
        return_pct = (exit_price - entry_price) / entry_price * 100
        results.append({
            "symbol": symbol,
            "signal": sig["signal"],
            "entry_date": signal_date.isoformat(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return_pct": round(return_pct, 2),
            "holding_weeks": holding_weeks
        })

    buy_returns = [r["return_pct"] for r in results if r["signal"] == "BUY"]
    sell_returns = [r["return_pct"] for r in results if r["signal"] == "SELL"]

    total_buy = len(buy_returns)
    winning_buy = sum(1 for r in buy_returns if r > 0)
    win_rate_buy = (winning_buy / total_buy * 100) if total_buy > 0 else 0
    avg_return_buy = sum(buy_returns) / total_buy if total_buy > 0 else 0
    max_return_buy = max(buy_returns) if buy_returns else 0
    min_return_buy = min(buy_returns) if buy_returns else 0

    total_sell = len(sell_returns)
    winning_sell = sum(1 for r in sell_returns if r > 0)
    win_rate_sell = (winning_sell / total_sell * 100) if total_sell > 0 else 0
    avg_return_sell = sum(sell_returns) / total_sell if total_sell > 0 else 0

    stats = {
        "holding_weeks": holding_weeks,
        "total_signals": len(results),
        "buy_signals": total_buy,
        "sell_signals": total_sell,
        "buy_win_rate": round(win_rate_buy, 1),
        "buy_avg_return": round(avg_return_buy, 2),
        "buy_max_return": round(max_return_buy, 2),
        "buy_min_return": round(min_return_buy, 2),
        "sell_win_rate": round(win_rate_sell, 1),
        "sell_avg_return": round(avg_return_sell, 2),
        "computed_at": datetime.utcnow()
    }
    cache_doc.set(stats, merge=True)
    return stats
