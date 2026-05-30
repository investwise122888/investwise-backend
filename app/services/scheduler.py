from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
from app.services.weekly_signal_service import generate_all_weekly_signals

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Manila'))

def refresh_all_data():
    """Weekly refresh: generate technical signals for all stocks."""
    logger.info("Running weekly technical signal generation...")
    try:
        generate_all_weekly_signals()
        logger.info("Weekly signal generation completed.")
    except Exception as e:
        logger.error(f"Weekly refresh failed: {e}")

def start_scheduler():
    if not scheduler.running:
        # Run every Monday at 8:00 AM PHT (after market close on Friday, but Monday morning is safe)
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