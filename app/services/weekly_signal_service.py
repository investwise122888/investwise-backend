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
            "explanation": "Not enough historical data to generate a reliable signal. Check back after a few weeks.",
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
            "debt_to_equity": None,
            "strength_score": 0,
            "strength_label": "HOLD"
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
            "debt_to_equity": None,
            "strength_score": 0,
            "strength_label": "HOLD"
        }

    close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else close
    change_pct = ((close - prev_close) / prev_close) * 100
    indicators = compute_weekly_indicators(df)
    latest_idx = -1
    rsi_val = indicators['rsi'].iloc[latest_idx] if not indicators['rsi'].isna().all() else 50
    macd_line_val = indicators['macd_line'].iloc[latest_idx] if not indicators['macd_line'].isna().all() else 0
    signal_line_val = indicators['signal_line'].iloc[latest_idx] if not indicators['signal_line'].isna().all() else 0
    histogram_val = indicators['histogram'].iloc[latest_idx] if not indicators['histogram'].isna().all() else 0.0
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

    # Compute strength score
    strength_score = compute_strength_score(
        rsi=rsi_val,
        macd_histogram=histogram_val,
        trend=trend,
        momentum=momentum,
        fundamentals_pass=bool(fundamentals_pass)
    )
    strength_label = get_strength_label(strength_score, final)

    # --- New user‑friendly explanation ---
    if final == "INSUFFICIENT_DATA":
        explanation = "Not enough historical data to generate a reliable signal. Check back after a few weeks."
    elif final == "BUY":
        explanation = f"BUY signal with strength {strength_score}/100. The stock shows strong upward momentum and healthy fundamentals. Consider adding to your long‑term portfolio."
    elif final == "SELL":
        explanation = f"SELL signal with strength {strength_score}/100. The stock shows weakness. Consider reducing exposure or waiting for a better entry point."
    else:  # final == "HOLD"
        if fundamental_veto:
            explanation = f"Strength {strength_score}/100. Technical signals suggest BUY, but the company fails our financial health check (e.g., high debt or weak earnings). Hold for now."
        elif strength_score < 40:
            explanation = f"Strength {strength_score}/100. No strong signal. The stock is moving sideways. Wait for clearer direction."
        else:
            explanation = f"Strength {strength_score}/100. The stock is stable but not trending strongly. Hold existing positions."

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
        "debt_to_equity": fundamentals.get("debt_to_equity") if fundamentals else None,
        "strength_score": strength_score,
        "strength_label": strength_label
    }
