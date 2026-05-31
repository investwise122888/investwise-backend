from fastapi import APIRouter, HTTPException
from app.services.news_sentiment import get_news_for_symbol
from app.services.stock_service import get_latest_predictions_from_firestore, PH_BLUE_CHIPS
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
async def get_all_news():
    """Aggregated news for all blue chip stocks (first article per stock) with error resilience."""
    all_news = []
    for symbol in PH_BLUE_CHIPS:
        try:
            news = await get_news_for_symbol(symbol)
            if news:
                all_news.append({
                    "symbol": symbol,
                    "top_article": news[0] if news else None
                })
        except Exception as e:
            logger.warning(f"News fetch failed for {symbol}: {e}")
            continue
    return {"stocks": all_news}

@router.get("/{symbol}")
async def get_stock_news(symbol: str):
    """Get latest news and sentiment for a specific stock symbol."""
    symbol = symbol.upper()
    if symbol not in PH_BLUE_CHIPS:
        raise HTTPException(status_code=404, detail="Symbol not in Philippine blue chips list")
    try:
        news = await get_news_for_symbol(symbol)
        
        # Fetch current signal for this symbol
        signals = get_latest_predictions_from_firestore()
        signal_map = {s["symbol"]: s.get("signal", "HOLD") for s in signals}
        current_signal = signal_map.get(symbol, "HOLD")
        
        # Handle case where no news articles are returned
        if not news:
            return {
                "symbol": symbol,
                "articles": [],
                "overall_sentiment": "neutral",
                "overall_score": 0.0,
                "overall_remark": f"No recent news available for {symbol}.",
                "signal": current_signal
            }
        
        # Compute overall sentiment statistics from articles
        sentiments = [a.get("sentiment_score", 0) for a in news]
        avg_score = sum(sentiments) / len(sentiments)
        if avg_score > 0.1:
            overall_label = "positive"
        elif avg_score < -0.1:
            overall_label = "negative"
        else:
            overall_label = "neutral"
        
        # AI remark for overall
        from app.services.news_sentiment import generate_ai_remark
        overall_remark = generate_ai_remark(symbol, overall_label, avg_score, current_signal)
        
        return {
            "symbol": symbol,
            "articles": news,
            "overall_sentiment": overall_label,
            "overall_score": round(avg_score, 3),
            "overall_remark": overall_remark,
            "signal": current_signal
        }
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        # Return graceful fallback instead of 503
        return {
            "symbol": symbol,
            "articles": [],
            "overall_sentiment": "neutral",
            "overall_score": 0.0,
            "overall_remark": f"News service temporarily unavailable for {symbol}. Please try again later.",
            "signal": "HOLD"
        }