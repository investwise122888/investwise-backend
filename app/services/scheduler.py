from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
import asyncio
import nest_asyncio
from app.services.weekly_signal_service import generate_all_weekly_signals
from app.services.news_sentiment import get_news_for_symbol, save_news_to_firestore
from app.services.real_stock_fetcher import BLUE_CHIPS
from app.services.ai_research_service import refresh_ai_research   # Phase E

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Manila'))

async def refresh_news():
    logger.info("Starting news refresh...")
    for symbol in BLUE_CHIPS:
        try:
            news = await get_news_for_symbol(symbol)
            await save_news_to_firestore(symbol, news)
            logger.info(f"News refreshed for {symbol}")
        except Exception as e:
            logger.error(f"News refresh failed for {symbol}: {e}")

def refresh_all_data():
    logger.info("Running weekly technical signal generation...")
    try:
        generate_all_weekly_signals()
        logger.info("Signal generation completed.")
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
    try:
        # Allow nested event loops (needed inside APScheduler thread)
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(refresh_news())
    except Exception as e:
        logger.error(f"News refresh failed: {e}")
    # Phase E: refresh AI research after signals and news
    try:
        refresh_ai_research()
        logger.info("AI research refresh completed.")
    except Exception as e:
        logger.error(f"AI research refresh failed: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            refresh_all_data,
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0, timezone=pytz.timezone('Asia/Manila')),
            id='weekly_refresh',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Scheduler started. Weekly refresh every Monday at 8:00 AM PHT.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

def manual_refresh():
    logger.info("Manual refresh triggered by admin.")
    refresh_all_data()