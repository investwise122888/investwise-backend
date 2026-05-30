import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from app.database import db
from app.services.stock_service import get_latest_predictions_from_firestore

NEWS_COLLECTION = "news"
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"

_analyzer = SentimentIntensityAnalyzer()

def simple_sentiment(text: str) -> float:
    return _analyzer.polarity_scores(text)['compound']

def generate_ai_remark(symbol: str, sentiment_label: str, sentiment_score: float, signal: str) -> str:
    if sentiment_label == "positive":
        if signal == "BUY":
            return f"Positive news + bullish technicals suggest upside for {symbol}."
        elif signal == "SELL":
            return f"News is positive but technicals are bearish – caution advised for {symbol}."
        else:
            return f"Favorable news coverage may support {symbol} in the near term."
    elif sentiment_label == "negative":
        if signal == "SELL":
            return f"Negative news aligns with technical sell signals – consider reducing exposure to {symbol}."
        elif signal == "BUY":
            return f"News is negative but technicals remain strong – watch for dips in {symbol}."
        else:
            return f"Unfavorable news may pressure {symbol} in the short run."
    else:
        if signal == "BUY":
            return f"Neutral sentiment, but technicals point to a potential move higher for {symbol}."
        elif signal == "SELL":
            return f"Neutral sentiment, but technical weakness suggests caution for {symbol}."
        else:
            return f"Mixed signals; monitor news flow and price action for {symbol}."

async def fetch_news_for_stock(company_name: str, symbol: str) -> List[Dict[str, Any]]:
    query = f"{company_name} Philippines stock"
    params = {"q": query, "lang": "en", "max": 5, "country": "ph"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GNEWS_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            results = []
            all_signals = get_latest_predictions_from_firestore()
            signal_map = {s["symbol"]: s.get("signal", "HOLD") for s in all_signals}
            current_signal = signal_map.get(symbol, "HOLD")
            for article in articles[:5]:
                title = article.get("title", "")
                description = article.get("description", "")
                full_text = f"{title}. {description}"
                polarity = simple_sentiment(full_text)
                sentiment_label = "positive" if polarity > 0.1 else "negative" if polarity < -0.1 else "neutral"
                ai_remark = generate_ai_remark(symbol, sentiment_label, polarity, current_signal)
                results.append({
                    "title": title,
                    "description": description,
                    "url": article.get("url", ""),
                    "publishedAt": article.get("publishedAt", ""),
                    "sentiment_score": round(polarity, 3),
                    "sentiment_label": sentiment_label,
                    "ai_remark": ai_remark
                })
            return results
    except Exception as e:
        print(f"GNews failed for {symbol}: {e}. Returning mock.")
        return [
            {
                "title": f"{company_name} shows resilience in Philippine market",
                "description": f"Recent trading of {symbol} indicates positive momentum.",
                "url": "https://example.com/mock1",
                "publishedAt": datetime.now().isoformat(),
                "sentiment_score": 0.2,
                "sentiment_label": "positive",
                "ai_remark": f"Mock positive news for {symbol} – technicals remain supportive."
            }
        ]

async def get_news_for_symbol(symbol: str) -> List[Dict[str, Any]]:
    cache_doc = db.collection(NEWS_COLLECTION).document(f"{symbol}_latest")
    doc = cache_doc.get()
    if doc.exists:
        data = doc.to_dict()
        updated_at = data.get("updated_at")
        if updated_at:
            # Firestore Timestamp → Python datetime (naive UTC)
            if hasattr(updated_at, 'replace'):
                updated_at = updated_at.replace(tzinfo=None)
            if datetime.utcnow() - updated_at < timedelta(hours=24):
                return data.get("articles", [])
    company_names = {
        "AC": "Ayala Corporation", "SM": "SM Investments", "BDO": "BDO Unibank",
        "JFC": "Jollibee Foods", "TEL": "PLDT", "MER": "Meralco",
        "GLO": "Globe Telecom", "ALI": "Ayala Land", "AEV": "Aboitiz Equity Ventures",
        "MBT": "Metropolitan Bank"
    }
    company = company_names.get(symbol.upper(), symbol)
    news = await fetch_news_for_stock(company, symbol.upper())
    cache_doc.set({
        "symbol": symbol,
        "articles": news,
        "updated_at": datetime.utcnow()
    })
    return news

async def save_news_to_firestore(symbol: str, news_list: list):
    db.collection(NEWS_COLLECTION).document(f"{symbol}_latest").set({
        "symbol": symbol,
        "articles": news_list,
        "updated_at": datetime.utcnow()
    })