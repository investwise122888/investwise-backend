import os
import time
import yfinance as yf
import pandas as pd
import logging
import io
import requests
from datetime import datetime, timedelta
from requests.exceptions import RequestException
from app.database import db
from app.models import PREDICTIONS_COLLECTION

logger = logging.getLogger(__name__)

BLUE_CHIPS = ["AC", "SM", "BDO", "JFC", "TEL", "MER", "GLO", "ALI", "AEV", "MBT"]
SIGNAL_VERSION = "v3_with_fundamentals"
MIN_ROWS_REQUIRED = 42

def fetch_weekly_data_alphavantage(symbol: str) -> pd.DataFrame:
    """Fetch weekly OHLCV data from Alpha Vantage for a given symbol."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY not set, skipping Alpha Vantage.")
        return pd.DataFrame()

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_WEEKLY",
        "symbol": f"{symbol}.PSE",           # PSE suffix for Philippine stocks
        "apikey": api_key,
        "datatype": "json"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        weekly_data = data.get("Weekly Time Series", {})
        if not weekly_data:
            logger.warning(f"No weekly data for {symbol} from Alpha Vantage.")
            return pd.DataFrame()

        rows = []
        for date_str, values in weekly_data.items():
            rows.append({
                "Date": pd.to_datetime(date_str),
                "Open": float(values["1. open"]),
                "High": float(values["2. high"]),
                "Low": float(values["3. low"]),
                "Close": float(values["4. close"]),
                "Volume": float(values["5. volume"])
            })
        df = pd.DataFrame(rows).set_index("Date").sort_index(ascending=True)
        logger.info(f"Alpha Vantage success for {symbol}, rows={len(df)}")
        return df
    except (RequestException, KeyError, ValueError) as e:
        logger.warning(f"Alpha Vantage failed for {symbol}: {e}")
        return pd.DataFrame()

def fetch_weekly_data_stooq(symbol: str) -> pd.DataFrame:
    """Fetch weekly data from Stooq CSV (fallback)."""
    url = f"https://stooq.com/q/d/l/?s={symbol}.ph&i=w"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_csv(io.StringIO(resp.text))
            if not df.empty and 'Date' in df.columns:
                df.index = pd.to_datetime(df['Date'])
                df = df.sort_index(ascending=True)
                df = df.rename(columns={
                    'Open': 'Open', 'High': 'High', 'Low': 'Low', 'Close': 'Close', 'Volume': 'Volume'
                })
                df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                logger.info(f"Stooq direct CSV success for {symbol}, rows={len(df)}")
                return df
    except Exception as e:
        logger.warning(f"Stooq CSV failed for {symbol}: {e}")
    return pd.DataFrame()

def fetch_weekly_data_yfinance(symbol: str, weeks: int = 52) -> pd.DataFrame:
    """Fetch weekly data from yfinance (fallback)."""
    try:
        ticker = yf.Ticker(f"{symbol}.PS")
        df = ticker.history(period=f"{weeks}w", interval="1wk")
        if not df.empty:
            logger.info(f"yfinance success for {symbol}")
            return df
    except Exception as e:
        logger.warning(f"yfinance failed for {symbol}: {e}")
    return pd.DataFrame()

def generate_mock_weekly(symbol: str, weeks: int = 52) -> pd.DataFrame:
    """Generate mock weekly data as final fallback."""
    end = datetime.now()
    start = end - timedelta(weeks=weeks)
    dates = pd.date_range(start=start, end=end, freq='W-MON')
    n = len(dates)
    base = 100 + (pd.RangeIndex(n) * 0.5) + (pd.RangeIndex(n) ** 2 * 0.01)
    noise_factor = hash(symbol) % 100 / 1000
    prices = (base * (1 + 0.1 * noise_factor)).values
    df = pd.DataFrame({
        'Open': prices,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': [1000000] * n
    }, index=dates)
    logger.warning(f"No weekly data for {symbol}, using mock data")
    return df

def fetch_weekly_data(symbol: str, weeks: int = 52) -> pd.DataFrame:
    """Primary: Alpha Vantage → Stooq → yFinance → mock."""
    # 1. Alpha Vantage (primary)
    df = fetch_weekly_data_alphavantage(symbol)
    if not df.empty:
        return df
    # 2. Stooq (fallback)
    df = fetch_weekly_data_stooq(symbol)
    if not df.empty:
        return df
    # 3. yfinance (fallback)
    df = fetch_weekly_data_yfinance(symbol, weeks)
    if not df.empty:
        return df
    # 4. Mock (final fallback)
    return generate_mock_weekly(symbol, weeks)

def compute_weekly_indicators(df):
    close = df['Close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
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
    if close is None or sma20 is None or sma40 is None:
        return "NEUTRAL"
    if close > sma20 and sma20 > sma40:
        return "BULL"
    elif close < sma20 and sma20 < sma40:
        return "BEAR"
    else:
        return "NEUTRAL"

def get_momentum(rsi, macd_line, signal_line):
    if rsi is None or macd_line is None or signal_line is None:
        return "NEUTRAL"
    if 50 <= rsi <= 75 and macd_line > signal_line:
        return "BULL"
    elif rsi < 45 and macd_line < signal_line:
        return "BEAR"
    else:
        return "NEUTRAL"

def check_volume_guard(df, lookback_weeks=10):
    recent_volume = df['Volume'].iloc[-lookback_weeks:]
    zero_volume_count = (recent_volume == 0).sum()
    return zero_volume_count <= 2

def get_raw_signal(trend, momentum):
    bullish_count = (trend == "BULL") + (momentum == "BULL")
    bearish_count = (trend == "BEAR") + (momentum == "BEAR")
    if bullish_count >= 2:
        return "BUY"
    elif bearish_count >= 2:
        return "SELL"
    else:
        return "HOLD"

def apply_persistence(symbol, new_raw_signal):
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
        if all(s == "BUY" for s in history):
            final = "BUY"
        elif all(s == "SELL" for s in history):
            final = "SELL"
        else:
            final = "HOLD"
    else:
        final = "HOLD"
    return final, history

def fetch_fundamentals(symbol):
    doc = db.collection("fundamentals").document(symbol).get()
    if doc.exists:
        return doc.to_dict()
    return None

def generate_weekly_signal(symbol):
    df = fetch_weekly_data(symbol)
    if df.empty:
        logger.error(f"No data for {symbol}")
        return None
    if len(df) < MIN_ROWS_REQUIRED:
        logger.warning(f"{symbol}: only {len(df)} weeks, need {MIN_ROWS_REQUIRED}")
        return {
            "symbol": symbol,
            "signal": "INSUFFICIENT_DATA",
            "explanation": f"Not enough historical data ({len(df)} weeks)",
            "signal_version": SIGNAL_VERSION,
            "price": None,
            "change_percent": None,
            "trend": None,
            "momentum": None,
            "volume_ok": False,
            "generated_at": datetime.utcnow(),
            "raw_signal": None,
            "persistent_signal": None,
            "fundamental_veto": False,
            "fundamentals_pass": None,
            "pe_ratio": None,
            "eps_positive_years": None,
            "debt_to_equity": None
        }
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
            "persistent_signal": None,
            "fundamental_veto": False,
            "fundamentals_pass": None,
            "pe_ratio": None,
            "eps_positive_years": None,
            "debt_to_equity": None
        }
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

    fundamentals = fetch_fundamentals(symbol)
    fundamentals_pass = fundamentals.get("fundamentals_pass") if fundamentals else None
    fundamental_veto = False
    if fundamentals_pass is not None and not fundamentals_pass:
        final = "HOLD"
        fundamental_veto = True

    explanation = f"Trend: {trend}, Momentum: {momentum}. Raw: {raw}. Persistence (3wk): {history} -> Final: {final}"
    if fundamental_veto:
        explanation += " (Fundamentals veto applied)"

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
        "generated_at": datetime.utcnow(),
        "fundamental_veto": fundamental_veto,
        "fundamentals_pass": fundamentals_pass,
        "pe_ratio": fundamentals.get("pe_ratio") if fundamentals else None,
        "eps_positive_years": fundamentals.get("eps_positive_years") if fundamentals else None,
        "debt_to_equity": fundamentals.get("debt_to_equity") if fundamentals else None
    }

def generate_all_weekly_signals():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    results = []
    # Rate limiting: respect free tier (5 requests/minute -> 12 seconds between calls)
    for idx, symbol in enumerate(BLUE_CHIPS):
        signal = generate_weekly_signal(symbol)
        if signal:
            doc_id = f"{symbol}_{today_str}"
            db.collection(PREDICTIONS_COLLECTION).document(doc_id).set(signal, merge=True)
            results.append(signal)
            logger.info(f"Weekly signal for {symbol}: {signal['signal']} (fundamentals_pass={signal.get('fundamentals_pass')})")
        # Delay between calls to avoid API rate limits (Alpha Vantage allows 5 per minute)
        if idx < len(BLUE_CHIPS) - 1:
            time.sleep(12)   # 12 seconds = 5 calls per minute
    logger.info(f"Generated {len(results)} weekly signals")
    return results

def manual_refresh_signals():
    generate_all_weekly_signals()