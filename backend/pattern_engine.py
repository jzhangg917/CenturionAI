import pandas as pd

def detect_swing_highs_lows(df, lookback=3):
    highs, lows = [], []
    for i in range(lookback, len(df) - lookback):
        if df["High"].iloc[i] > df["High"].iloc[i - lookback:i].max() and df["High"].iloc[i] > df["High"].iloc[i + 1:i + 1 + lookback].max():
            highs.append(i)
        if df["Low"].iloc[i] < df["Low"].iloc[i - lookback:i].min() and df["Low"].iloc[i] < df["Low"].iloc[i + 1:i + 1 + lookback].min():
            lows.append(i)
    return highs, lows

def detect_liquidity_sweep(df, swing_highs, swing_lows, threshold=0.1):
    recent_highs = [df["High"].iloc[i] for i in swing_highs[-3:]]
    recent_lows = [df["Low"].iloc[i] for i in swing_lows[-3:]]

    last_high = df["High"].iloc[-1]
    last_low = df["Low"].iloc[-1]

    swept_highs = [h for h in recent_highs if last_high > h * (1 + threshold/100)]
    swept_lows = [l for l in recent_lows if last_low < l * (1 - threshold/100)]

    if swept_highs:
        return "Sell-side Liquidity Sweep"
    elif swept_lows:
        return "Buy-side Liquidity Sweep"
    else:
        return None

def detect_bos(df, structure_len=10):
    recent_closes = df["Close"].tail(structure_len).tolist()
    trend = "up" if recent_closes[-1] > recent_closes[0] else "down"

    if trend == "up" and recent_closes[-1] < min(recent_closes[:-2]):
        return "Break of Structure (Down)"
    elif trend == "down" and recent_closes[-1] > max(recent_closes[:-2]):
        return "Break of Structure (Up)"
    return None