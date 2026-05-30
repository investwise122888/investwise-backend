from fastapi import APIRouter, HTTPException
from app.services.news_sentiment import get_news_for_symbol
from app.services.stock_service import PH_BLUE_CHIPS
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
            continue  # skip this symbol and move on
    return {"stocks": all_news}

@router.get("/{symbol}")
async def get_stock_news(symbol: str):
    """Get latest news and sentiment for a specific stock symbol."""
    symbol = symbol.upper()
    if symbol not in PH_BLUE_CHIPS:
        raise HTTPException(status_code=404, detail="Symbol not in Philippine blue chips list")
    try:
        news = await get_news_for_symbol(symbol)
        if not news:
            raise HTTPException(status_code=503, detail="News service unavailable")
        return {"symbol": symbol, "articles": news}
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        raise HTTPException(status_code=503, detail="News service temporarily unavailable")