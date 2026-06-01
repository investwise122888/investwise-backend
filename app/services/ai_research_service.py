import logging
from datetime import datetime
from app.database import db
from app.services.stock_service import get_latest_predictions_from_firestore
from app.services.news_sentiment import get_news_for_symbol   # correct import
from app.services.stock_data_fetcher import BLUE_CHIPS

logger = logging.getLogger(__name__)

def compute_composite_score(signal: str, strength_score: int, fundamentals_pass: bool, news_sentiment: str) -> int:
    """Calculate composite score (0-100) based on four factors."""
    # 1. Signal value (max 50)
    signal_map = {"BUY": 50, "HOLD": 25, "SELL": 0}
    signal_pts = signal_map.get(signal, 0)
    
    # 2. Strength score (0-100) * 0.3 (max 30)
    strength_pts = int(strength_score * 0.3) if strength_score else 0
    
    # 3. Fundamentals (10 pts if pass)
    fundamental_pts = 10 if fundamentals_pass else 0
    
    # 4. News sentiment (10, 5, or 0)
    news_map = {"positive": 10, "neutral": 5, "negative": 0}
    news_pts = news_map.get(news_sentiment, 0)
    
    total = signal_pts + strength_pts + fundamental_pts + news_pts
    return min(100, total)

async def refresh_ai_research():
    """Compute composite scores for all blue chips, rank them, and store in Firestore."""
    logger.info("Refreshing AI research rankings...")
    
    # 1. Get current signals and fundamentals (sync call)
    predictions = get_latest_predictions_from_firestore()
    signal_map = {p["symbol"]: p for p in predictions}
    
    # 2. Get latest news sentiment for each symbol using async function
    news_map = {}
    for symbol in BLUE_CHIPS:
        news = await get_news_for_symbol(symbol)   # returns list of articles
        if news:
            # Aggregate overall sentiment (simple majority of article labels)
            labels = [a.get("sentiment_label", "neutral") for a in news]
            if not labels:
                overall = "neutral"
            else:
                # Majority vote (if tie, neutral)
                pos = labels.count("positive")
                neg = labels.count("negative")
                overall = "positive" if pos > neg else "negative" if neg > pos else "neutral"
        else:
            overall = "neutral"
        news_map[symbol] = overall
    
    # 3. Compute rankings
    rankings = []
    for symbol in BLUE_CHIPS:
        pred = signal_map.get(symbol, {})
        signal = pred.get("signal", "HOLD")
        strength = pred.get("strength_score", 0)
        fundamentals_pass = pred.get("fundamentals_pass", False)
        news_sent = news_map.get(symbol, "neutral")
        
        score = compute_composite_score(signal, strength, fundamentals_pass, news_sent)
        
        # Short explanation
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
    
    # 4. Sort descending by score
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)
    
    # 5. Assign rank numbers (1-based)
    for idx, item in enumerate(rankings, start=1):
        item["rank"] = idx
    
    # 6. Save to Firestore (overwrite document 'latest')
    doc_ref = db.collection("ai_research").document("latest")
    doc_ref.set({
        "generated_at": datetime.utcnow(),
        "rankings": rankings
    }, merge=True)
    logger.info(f"AI research rankings saved: {len(rankings)} stocks")
    return rankings

def get_latest_ai_research():
    """Retrieve the latest AI research document from Firestore."""
    doc = db.collection("ai_research").document("latest").get()
    if doc.exists:
        return doc.to_dict()
    return None