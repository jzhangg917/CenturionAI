"""
Backend utilities for data fetching, analysis, and signal generation.
"""

import os, json
import pandas as pd
import pandas_ta as ta  # type: ignore
from datetime import datetime
import yfinance as yf    # type: ignore
import pytz
from pattern_engine import detect_swing_highs_lows, detect_liquidity_sweep, detect_bos, detect_fvg

OUTPUT_DIR = "../frontend/data"
LOOKBACK = 60
TIMEZONE = "US/Eastern"

def fetch_data(ticker, interval="1m"):
    """
    Fetch and process market data for a given ticker.
    
    Args:
        ticker: Stock ticker symbol
        interval: Data interval (1m, 5m, 15m, 1h, 1d)
        
    Returns:
        DataFrame with OHLC data and technical indicators
    """
    period_map = {
        "1m": "5d",
        "5m": "7d",
        "15m": "30d",
        "1h": "60d",
        "1d": "6mo"
    }
    period = period_map.get(interval, "5d")

    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df.dropna(inplace=True)

    df["RSI"] = ta.rsi(df["Close"], length=14)
    macd = ta.macd(df["Close"])
    df["MACD"] = macd["MACD_12_26_9"] if macd is not None and "MACD_12_26_9" in macd else pd.NA
    df["MACD_signal"] = macd["MACDs_12_26_9"] if macd is not None and "MACDs_12_26_9" in macd else pd.NA
    df["EMA_9"] = ta.ema(df["Close"], length=9)
    df["EMA_21"] = ta.ema(df["Close"], length=21)
    df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

    return df.tail(LOOKBACK)

def analyze(df, ticker):
    """
    Analyze market data and generate trading signals.
    
    Args:
        df: DataFrame with market data and indicators
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary containing trading signals and analysis results
    """
    try:
        rsi = df["RSI"].dropna().iloc[-1]
        macd = df["MACD"].dropna().iloc[-1]
        macd_sig = df["MACD_signal"].dropna().iloc[-1]
        ema_9 = df["EMA_9"].dropna().iloc[-1]
        ema_21 = df["EMA_21"].dropna().iloc[-1]
        atr = df["ATR"].dropna().iloc[-1]
        price = df["Close"].iloc[-1]
    except:
        return None

    score = 0
    logic = []
    if rsi < 30:
        score += 1
        logic.append("RSI oversold")
    if macd > macd_sig:
        score += 1
        logic.append("MACD bullish")
    if ema_9 > ema_21:
        score += 1
        logic.append("EMA bullish")

    base_confidence = int((score / 3) * 100)
    base_signal = "BUY" if score >= 2 else "HOLD"

    highs, lows = detect_swing_highs_lows(df)
    sweep, sweep_level = detect_liquidity_sweep(df, highs, lows)
    bos, bos_level = detect_bos(df)

    pattern_stack = []
    if sweep:
        pattern_stack.append(sweep)
    if bos:
        pattern_stack.append(bos)

    entry_signal = "WAIT"
    entry_price = stop_loss = take_profit = None

    if sweep or bos:
        if "Buy-side" in (sweep or "") and "Up" in (bos or ""):
            entry_signal = "BUY"
            entry_price = round(bos_level + 0.1, 2)
            stop_loss = round(sweep_level - 0.15, 2)
            take_profit = round(entry_price + 2 * (entry_price - stop_loss), 2)
        elif "Sell-side" in (sweep or "") and "Down" in (bos or ""):
            entry_signal = "SELL"
            entry_price = round(bos_level - 0.1, 2)
            stop_loss = round(sweep_level + 0.15, 2)
            take_profit = round(entry_price - 2 * (stop_loss - entry_price), 2)

    stacked_conf = 90 if entry_signal in ["BUY", "SELL"] else 50 if pattern_stack else 0
    ts = datetime.now(pytz.timezone(TIMEZONE)).isoformat()

    df_subset = df.tail(60)
    history = []
    for i, row in df_subset.iterrows():
        history.append({
            "t": row.name.strftime("%Y-%m-%d %H:%M:%S"),
            "o": round(row["Open"], 2),
            "h": round(row["High"], 2),
            "l": round(row["Low"], 2),
            "c": round(row["Close"], 2)
        })

    fvg_patterns = detect_fvg(df)
    if fvg_patterns:
        pattern_stack.append("Fair Value Gap")

    result = {
        "ticker": ticker,
        "signal": base_signal,
        "confidence": max(base_confidence, stacked_conf),
        "price": round(price, 2),
        "timestamp": ts,
        "logic": logic,
        "entry_signal": entry_signal,
        "pattern_stack": pattern_stack,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "history": history,
        "patterns": fvg_patterns  # to render annotations
    }

    return result

def save_outputs(ticker, sig):
    """
    Save trading signals and logs to files.
    
    Args:
        ticker: Stock ticker symbol
        sig: Dictionary containing trading signals
    """
    import shutil

    signal_path = os.path.join(OUTPUT_DIR, f"{ticker}_signal.json")
    log_path = os.path.join(OUTPUT_DIR, f"{ticker}_log.csv")

    with open(signal_path, "w") as f:
        json.dump(sig, f, indent=2)

    line = f'{sig["timestamp"]},{sig["ticker"]},{sig["signal"]},{sig["confidence"]},{sig["price"]},"{",".join(sig["logic"])}"\n'
    if not os.path.exists(log_path):
        with open(log_path, "w") as f:
            f.write("timestamp,ticker,signal,confidence,price,logic\n")
            f.write(line)
    else:
        with open(log_path, "a") as f:
            f.write(line)

    frontend_dir = os.path.join("frontend", "data")
    os.makedirs(frontend_dir, exist_ok=True)
    shutil.copy(signal_path, os.path.join(frontend_dir, f"{ticker}_signal.json"))
    shutil.copy(log_path, os.path.join(frontend_dir, f"{ticker}_log.csv"))
