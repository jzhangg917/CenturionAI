# backend/backend_utils.py

import os, json
import pandas as pd
import pandas_ta as ta # type: ignore
from datetime import datetime
import yfinance as yf # type: ignore
import pytz

OUTPUT_DIR = "../frontend/data"
LOOKBACK = 60
INTERVAL = "1m"
TIMEZONE = "US/Eastern"

def fetch_data(ticker):
    df = yf.download(ticker, period="5d", interval=INTERVAL, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df.dropna(inplace=True)

    df["RSI"] = ta.rsi(df["Close"], length=14)
    macd = ta.macd(df["Close"])
    if macd is not None and "MACD_12_26_9" in macd and "MACDs_12_26_9" in macd:
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACD_signal"] = macd["MACDs_12_26_9"]
    else:
        df["MACD"] = df["MACD_signal"] = pd.NA
    df["EMA_9"] = ta.ema(df["Close"], length=9)
    df["EMA_21"] = ta.ema(df["Close"], length=21)
    df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

    return df.tail(LOOKBACK)

def analyze(df, ticker):
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
    if rsi < 30: score += 1; logic.append("RSI oversold")
    if macd > macd_sig: score += 1; logic.append("MACD bullish")
    if ema_9 > ema_21: score += 1; logic.append("EMA bullish")

    confidence = int((score / 3) * 100)
    signal = "BUY" if score >= 2 else "HOLD"
    ts = datetime.now(pytz.timezone(TIMEZONE)).isoformat()

    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        "price": round(price, 2),
        "timestamp": ts,
        "logic": logic
    }

def save_outputs(ticker, sig):
    import shutil

    # Save in backend
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

    # ✅ Copy to frontend/data
    frontend_dir = os.path.join("frontend", "data")
    os.makedirs(frontend_dir, exist_ok=True)
    shutil.copy(signal_path, os.path.join(frontend_dir, f"{ticker}_signal.json"))
    shutil.copy(log_path, os.path.join(frontend_dir, f"{ticker}_log.csv"))
