import httpx
from datetime import datetime
from typing import List, Dict, Any
from app.database import db

NEWS_COLLECTION = "news"
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"

def simple_sentiment(text: str) -> float:
    """Basic keyword sentiment, returns -1 to 1."""
    positive_words = ["good", "great", "up", "rise", "profit", "growth", "bullish", "positive"]
    negative_words = ["bad", "down", "fall", "loss", "risk", "bearish", "decline", "negative"]
    text_lower = text.lower()
    score = 0
    for w in positive_words:
        if w in text_lower:
            score += 0.2
    for w in negative_words:
        if w in text_lower:
            score -= 0.2
    return max(-1.0, min(1.0, score))

async def fetch_news_for_stock(company_name: str, symbol: str) -> List[Dict[str, Any]]:
    """Fetch news articles for a given stock using GNews API."""
    query = f"{company_name} Philippines stock"
    params = {
        "q": query,
        "lang": "en",
        "max": 5,
        "country": "ph"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GNEWS_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            results = []
            for article in articles[:5]:
                title = article.get("title", "")
                description = article.get("description", "")
                full_text = f"{title}. {description}"
                polarity = simple_sentiment(full_text)
                sentiment_label = "positive" if polarity > 0.1 else "negative" if polarity < -0.1 else "neutral"
                results.append({
                    "title": title,
                    "description": description,
                    "url": article.get("url", ""),
                    "publishedAt": article.get("publishedAt", ""),
                    "sentiment_score": round(polarity, 3),
                    "sentiment_label": sentiment_label
                })
            return results
    except Exception as e:
        print(f"GNews failed for {symbol}: {e}. Returning mock data.")
        return [
            {
                "title": f"{company_name} shows resilience in Philippine market",
                "description": f"Recent trading of {symbol} indicates positive momentum.",
                "url": "https://example.com/mock1",
                "publishedAt": datetime.now().isoformat(),
                "sentiment_score": 0.2,
                "sentiment_label": "positive"
            }
        ]

async def get_news_for_symbol(symbol: str) -> List[Dict[str, Any]]:
    """Get news for a stock symbol (cached from Firestore, or fetch live)."""
    # First try Firestore cache
    doc = db.collection(NEWS_COLLECTION).document(f"{symbol}_latest").get()
    if doc.exists:
        return doc.to_dict().get("articles", [])
    # Otherwise fetch live
    company_names = {
        "AC": "Ayala Corporation", "SM": "SM Investments", "BDO": "BDO Unibank",
        "JFC": "Jollibee Foods", "TEL": "PLDT", "MER": "Meralco",
        "GLO": "Globe Telecom", "ALI": "Ayala Land", "AEV": "Aboitiz Equity Ventures",
        "MBT": "Metropolitan Bank"
    }
    company = company_names.get(symbol.upper(), symbol)
    news = await fetch_news_for_stock(company, symbol.upper())
    # Save to cache
    db.collection(NEWS_COLLECTION).document(f"{symbol}_latest").set({
        "symbol": symbol,
        "articles": news,
        "updated_at": datetime.now()
    })
    return news

async def save_news_to_firestore(symbol: str, news_list: list):
    """Save news to Firestore (used by scheduler)."""
    db.collection(NEWS_COLLECTION).document(f"{symbol}_latest").set({
        "symbol": symbol,
        "articles": news_list,
        "updated_at": datetime.now()
    })

async def get_news_from_firestore(symbol: str) -> list:
    """Retrieve news from Firestore without refetching."""
    doc = db.collection(NEWS_COLLECTION).document(f"{symbol}_latest").get()
    return doc.to_dict().get("articles", []) if doc.exists else []
