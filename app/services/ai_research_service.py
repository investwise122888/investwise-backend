import logging
from datetime import datetime, timedelta
from app.database import db
from app.services.stock_service import get_latest_predictions_from_firestore
from app.services.news_sentiment import get_news_for_symbol
from app.services.real_stock_fetcher import BLUE_CHIPS

logger = logging.getLogger(__name__)

def compute_composite_score(signal: str, strength_score: int, fundamentals_pass: bool, news_sentiment: str) -> int:
    signal_map = {"BUY": 50, "HOLD": 25, "SELL": 0}
    signal_pts = signal_map.get(signal, 0)
    strength_pts = int(strength_score * 0.3) if strength_score else 0
    fundamental_pts = 10 if fundamentals_pass else 0
    news_map = {"positive": 10, "neutral": 5, "negative": 0}
    news_pts = news_map.get(news_sentiment, 0)
    total = signal_pts + strength_pts + fundamental_pts + news_pts
    return min(100, total)

async def refresh_ai_research():
    logger.info("Refreshing AI research rankings...")
    predictions = get_latest_predictions_from_firestore()
    signal_map = {p["symbol"]: p for p in predictions}
    news_map = {}
    for symbol in BLUE_CHIPS:
        news = await get_news_for_symbol(symbol)
        if news:
            labels = [a.get("sentiment_label", "neutral") for a in news]
            pos = labels.count("positive")
            neg = labels.count("negative")
            overall = "positive" if pos > neg else "negative" if neg > pos else "neutral"
        else:
            overall = "neutral"
        news_map[symbol] = overall
    rankings = []
    for symbol in BLUE_CHIPS:
        pred = signal_map.get(symbol, {})
        signal = pred.get("signal", "HOLD")
        strength = pred.get("strength_score", 0)
        fundamentals_pass = pred.get("fundamentals_pass", False)
        news_sent = news_map.get(symbol, "neutral")
        score = compute_composite_score(signal, strength, fundamentals_pass, news_sent)
        explanation = f"Signal {signal} ({strength}/100 strength), fundamentals {fundamentals_pass}, news {news_sent}"
        rankings.append({
            "symbol": symbol,
            "composite_score": score,
            "signal": signal,
            "strength_score": strength,
            "fundamentals_pass": fundamentals_pass,
            "news_sentiment_label": news_sent,
            "explanation_short": explanation
        })
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)
    for idx, item in enumerate(rankings, start=1):
        item["rank"] = idx
    doc_ref = db.collection("ai_research").document("latest")
    doc_ref.set({
        "generated_at": datetime.utcnow(),
        "rankings": rankings
    }, merge=True)
    logger.info(f"AI research rankings saved: {len(rankings)} stocks")
    return rankings

def get_latest_ai_research():
    doc = db.collection("ai_research").document("latest").get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    generated_at = data.get("generated_at")
    # Only trigger refresh if data is older than 24 hours
    if generated_at and isinstance(generated_at, datetime):
        # Ensure datetime is naive for comparison
        if generated_at.tzinfo:
            generated_at = generated_at.replace(tzinfo=None)
        now_naive = datetime.utcnow()
        age = now_naive - generated_at
        if age.total_seconds() > 86400:  # 24 hours
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(refresh_ai_research())
                else:
                    # No running loop – run in a separate thread
                    import threading
                    threading.Thread(target=asyncio.run, args=(refresh_ai_research(),)).start()
            except Exception as e:
                logger.warning(f"Could not trigger background refresh: {e}")
    return data
