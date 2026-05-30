import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta
from app.database import db
from app.models import PREDICTIONS_COLLECTION

logger = logging.getLogger(__name__)

BLUE_CHIPS = ["AC", "SM", "BDO", "JFC", "TEL", "MER", "GLO", "ALI", "AEV", "MBT"]
SIGNAL_VERSION = "v1_technical_only"

def fetch_weekly_data(symbol: str, weeks: int = 52):
    """Fetch weekly OHLCV data from yfinance."""
    ticker = yf.Ticker(f"{symbol}.PS")
    df = ticker.history(period=f"{weeks}w", interval="1wk")
    if df.empty:
        logger.warning(f"No weekly data for {symbol}, generating mock weekly")
        df = generate_mock_weekly(symbol, weeks)
    return df

def generate_mock_weekly(symbol: str, weeks: int):
    """Generate mock weekly data for development when yfinance fails."""
    end = datetime.now()
    start = end - timedelta(weeks=weeks)
    dates = pd.date_range(start=start, end=end, freq='W-MON')
    n = len(dates)
    base = 100 + (pd.RangeIndex(n) * 0.5) + (pd.RangeIndex(n) ** 2 * 0.01)
    noise_factor = hash(symbol) % 100 / 1000
    prices = (base * (1 + 0.1 * noise_factor)).values  # <-- .values strips the index
    df = pd.DataFrame({
        'Open': prices,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': [1000000] * n
    }, index=dates)
    return df

def compute_weekly_indicators(df):
    """Compute RSI (14 weeks), MACD (12,26,9), SMA20, SMA40."""
    close = df['Close']
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    # SMAs
    sma20 = close.rolling(20).mean()
    sma40 = close.rolling(40).mean()
    return {
        'rsi': rsi,
        'macd_line': macd_line,
        'signal_line': signal_line,
        'histogram': histogram,
        'sma20': sma20,
        'sma40': sma40,
        'close': close
    }

def get_trend(close, sma20, sma40):
    """Determine trend from weekly data."""
    if close is None or sma20 is None or sma40 is None:
        return "NEUTRAL"
    if close > sma20 and sma20 > sma40:
        return "BULL"
    elif close < sma20 and sma20 < sma40:
        return "BEAR"
    else:
        return "NEUTRAL"

def get_momentum(rsi, macd_line, signal_line):
    """Determine momentum from RSI and MACD."""
    if rsi is None or macd_line is None or signal_line is None:
        return "NEUTRAL"
    if 50 <= rsi <= 75 and macd_line > signal_line:
        return "BULL"
    elif rsi < 45 and macd_line < signal_line:
        return "BEAR"
    else:
        return "NEUTRAL"

def check_volume_guard(df, lookback_weeks=10):
    """Check if more than 2 weeks in last `lookback_weeks` have zero volume."""
    recent_volume = df['Volume'].iloc[-lookback_weeks:]
    zero_volume_count = (recent_volume == 0).sum()
    return zero_volume_count <= 2  # True if enough volume

def get_raw_signal(trend, momentum):
    """2-of-3 rule: bullish_count >=2 -> GOOD; bearish_count >=2 -> AVOID; else NEUTRAL."""
    bullish_count = (trend == "BULL") + (momentum == "BULL")
    bearish_count = (trend == "BEAR") + (momentum == "BEAR")
    if bullish_count >= 2:
        return "GOOD"
    elif bearish_count >= 2:
        return "AVOID"
    else:
        return "NEUTRAL"

def apply_persistence(symbol, new_raw_signal, db_collection=PREDICTIONS_COLLECTION):
    """
    Read last 3 raw signals (including current). If all 3 are GOOD -> final GOOD;
    if all 3 are AVOID -> final AVOID; else final NEUTRAL.
    """
    persist_ref = db.collection("signal_history").document(symbol)
    doc = persist_ref.get()
    if doc.exists:
        history = doc.to_dict().get("raw_signals", [])
    else:
        history = []
    history.append(new_raw_signal)
    if len(history) > 3:
        history.pop(0)
    persist_ref.set({"raw_signals": history})
    if len(history) == 3:
        if all(s == "GOOD" for s in history):
            final = "GOOD"
        elif all(s == "AVOID" for s in history):
            final = "AVOID"
        else:
            final = "NEUTRAL"
    else:
        final = "NEUTRAL"  # not enough history
    return final, history

def generate_weekly_signal(symbol):
    """Compute weekly signal for a single symbol, return dict ready for Firestore."""
    df = fetch_weekly_data(symbol)
    if df.empty:
        logger.error(f"No data for {symbol}")
        return None
    volume_ok = check_volume_guard(df)
    if not volume_ok:
        return {
            "symbol": symbol,
            "signal": "INSUFFICIENT_DATA",
            "explanation": "Volume insufficient (more than 2 zero-volume weeks in last 10)",
            "signal_version": SIGNAL_VERSION,
            "price": None,
            "change_percent": None,
            "trend": None,
            "momentum": None,
            "volume_ok": False,
            "generated_at": datetime.utcnow(),
            "raw_signal": None,
            "persistent_signal": None
        }
    # Get latest values
    close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else close
    change_pct = ((close - prev_close) / prev_close) * 100
    indicators = compute_weekly_indicators(df)
    latest_idx = -1
    rsi_val = indicators['rsi'].iloc[latest_idx] if not indicators['rsi'].isna().all() else 50
    macd_line_val = indicators['macd_line'].iloc[latest_idx] if not indicators['macd_line'].isna().all() else 0
    signal_line_val = indicators['signal_line'].iloc[latest_idx] if not indicators['signal_line'].isna().all() else 0
    sma20_val = indicators['sma20'].iloc[latest_idx] if not indicators['sma20'].isna().all() else close
    sma40_val = indicators['sma40'].iloc[latest_idx] if not indicators['sma40'].isna().all() else close
    trend = get_trend(close, sma20_val, sma40_val)
    momentum = get_momentum(rsi_val, macd_line_val, signal_line_val)
    raw = get_raw_signal(trend, momentum)
    final, history = apply_persistence(symbol, raw)
    explanation = f"Trend: {trend}, Momentum: {momentum}. Raw: {raw}. Persistence (3wk): {history} -> Final: {final}"
    return {
        "symbol": symbol,
        "signal": final,
        "explanation": explanation,
        "signal_version": SIGNAL_VERSION,
        "price": round(close, 2),
        "change_percent": round(change_pct, 2),
        "trend": trend,
        "momentum": momentum,
        "volume_ok": True,
        "raw_signal": raw,
        "persistent_signal": final,
        "generated_at": datetime.utcnow()
    }

def generate_all_weekly_signals():
    """Run weekly signal generation for all blue chips and save to Firestore predictions."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    results = []
    for symbol in BLUE_CHIPS:
        signal = generate_weekly_signal(symbol)
        if signal:
            doc_id = f"{symbol}_{today_str}"
            db.collection(PREDICTIONS_COLLECTION).document(doc_id).set(signal, merge=True)
            results.append(signal)
            logger.info(f"Weekly signal for {symbol}: {signal['signal']}")
    logger.info(f"Generated {len(results)} weekly signals")
    return results

def manual_refresh_signals():
    """Manually trigger weekly signal calculation (for admin testing)."""
    generate_all_weekly_signals()