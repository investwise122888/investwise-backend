import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# For compatibility with existing code that imports from real_stock_fetcher
BLUE_CHIPS = ["AC", "SM", "BDO", "JFC", "TEL", "MER", "GLO", "ALI", "AEV", "MBT"]

# This file is now only for providing BLUE_CHIPS and static fallback price (if needed)
# The actual signal generation is in weekly_signal_service.py

def get_all_prices():
    """Legacy function – not used in Phase A, but kept for compatibility."""
    logger.warning("get_all_prices called but signals are now generated weekly.")
    return {}