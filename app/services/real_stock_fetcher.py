import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the static prices file
STATIC_PRICES_PATH = Path(__file__).parent.parent.parent / "static_prices.json"

BLUE_CHIPS = ["AC", "SM", "BDO", "JFC", "TEL", "MER", "GLO", "ALI", "AEV", "MBT"]

def load_static_prices():
    """Load static stock prices from JSON file."""
    try:
        with open(STATIC_PRICES_PATH, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load static_prices.json: {e}")
        return {}

def get_real_stock_price(symbol):
    """Return price from static JSON."""
    prices = load_static_prices()
    if symbol in prices:
        price = prices[symbol]["price"]
        change = prices[symbol]["change"]
        logger.info(f"Static data for {symbol}: ₱{price} ({change:+.2f}%)")
        return price, change, True
    logger.warning(f"Symbol {symbol} not found in static prices")
    return None, None, False

def get_all_prices():
    """Return dict of symbol -> {price, change, success} from static file."""
    prices = load_static_prices()
    results = {}
    for symbol in BLUE_CHIPS:
        if symbol in prices:
            results[symbol] = {
                "price": prices[symbol]["price"],
                "change": prices[symbol]["change"],
                "success": True
            }
        else:
            results[symbol] = {"success": False, "price": None, "change": None}
    return results
