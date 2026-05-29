from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
from datetime import datetime
from app.services.real_stock_fetcher import get_all_prices, BLUE_CHIPS
from app.database import db
from app.models import PREDICTIONS_COLLECTION

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Manila'))

def refresh_all_data():
    """Fetch real PSE prices and save predictions to Firestore."""
    logger.info("Starting scheduled refresh of stock predictions...")
    prices = get_all_prices()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    success_count = 0
    for symbol in BLUE_CHIPS:
        data = prices.get(symbol)
        if data and data.get("success"):
            price = data["price"]
            change = data["change"]
            # Simple signal based on change
            if change > 1:
                signal = "GOOD"
                explanation = f"Price up {change:.2f}% today"
            elif change < -1:
                signal = "AVOID"
                explanation = f"Price down {change:.2f}% today"
            else:
                signal = "NEUTRAL"
                explanation = "Small change, wait for direction"
            prediction = {
                "symbol": symbol,
                "price": price,
                "change_percent": change,
                "signal": signal,
                "explanation": explanation,
                "date": datetime.utcnow()
            }
            doc_id = f"{symbol}_{today_str}"
            db.collection(PREDICTIONS_COLLECTION).document(doc_id).set(prediction)
            success_count += 1
            logger.info(f"Saved {symbol}: ₱{price} ({change:+.2f}%)")
        else:
            logger.warning(f"No real data for {symbol}, keeping old Firestore value")
    logger.info(f"Refresh completed. Saved {success_count}/{len(BLUE_CHIPS)} predictions.")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            refresh_all_data,
            trigger=CronTrigger(hour=18, minute=0, timezone=pytz.timezone('Asia/Manila')),
            id='daily_refresh',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Scheduler started. Daily refresh at 6:00 PM PHT.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

def manual_refresh():
    logger.info("Manual refresh triggered by admin.")
    refresh_all_data()
