# backend/pattern_engine.py

"""
Pattern detection engine for technical analysis.
Contains functions for detecting various chart patterns and market structures.
"""

from datetime import timedelta

def detect_swing_highs_lows(df, lookback=3):
    """
    Detect swing highs and lows in price data.
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to look back/forward for swing detection
        
    Returns:
        Tuple of lists containing indices of swing highs and lows
    """
    highs, lows = [], []
    for i in range(lookback, len(df) - lookback):
        if df["High"].iloc[i] > df["High"].iloc[i - lookback:i].max() and df["High"].iloc[i] > df["High"].iloc[i + 1:i + 1 + lookback].max():
            highs.append(i)
        if df["Low"].iloc[i] < df["Low"].iloc[i - lookback:i].min() and df["Low"].iloc[i] < df["Low"].iloc[i + 1:i + 1 + lookback].min():
            lows.append(i)
    return highs, lows

def detect_liquidity_sweep(df, swing_highs, swing_lows, threshold=0.1):
    """
    Detect liquidity sweeps in price action.
    
    Args:
        df: DataFrame with OHLC data
        swing_highs: List of swing high indices
        swing_lows: List of swing low indices
        threshold: Percentage threshold for sweep detection
        
    Returns:
        Tuple of (sweep type, level) if detected, (None, None) otherwise
    """
    recent_highs = [df["High"].iloc[i] for i in swing_highs[-3:]]
    recent_lows = [df["Low"].iloc[i] for i in swing_lows[-3:]]

    last_high = df["High"].iloc[-1]
    last_low = df["Low"].iloc[-1]

    swept_highs = [h for h in recent_highs if last_high > h * (1 + threshold/100)]
    swept_lows = [l for l in recent_lows if last_low < l * (1 - threshold/100)]

    if swept_highs:
        level = max(swept_highs)
        return "Sell-side Liquidity Sweep", level
    elif swept_lows:
        level = min(swept_lows)
        return "Buy-side Liquidity Sweep", level
    return None, None

def detect_bos(df, structure_len=10):
    """
    Detect Break of Structure (BOS) in price action.
    
    Args:
        df: DataFrame with OHLC data
        structure_len: Length of structure to analyze
        
    Returns:
        Tuple of (BOS type, level) if detected, (None, None) otherwise
    """
    recent_closes = df["Close"].tail(structure_len).tolist()
    trend = "up" if recent_closes[-1] > recent_closes[0] else "down"

    if trend == "up" and recent_closes[-1] < min(recent_closes[:-2]):
        bos_level = min(recent_closes[:-2])
        return "Break of Structure (Down)", bos_level
    elif trend == "down" and recent_closes[-1] > max(recent_closes[:-2]):
        bos_level = max(recent_closes[:-2])
        return "Break of Structure (Up)", bos_level
    return None, None

def detect_fvg(df):
    """
    Detect Fair Value Gaps (FVG) in price action.
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        List of detected FVG patterns with their properties
    """
    patterns = []

    for i in range(2, len(df)):
        prev2 = df.iloc[i - 2]
        prev1 = df.iloc[i - 1]
        curr = df.iloc[i]

        # Check for Fair Value Gap: previous high < current low
        if prev2["High"] < curr["Low"]:
            xMin = df.index[i - 2]
            xMax = df.index[i]

            yMin = prev2["High"]
            yMax = curr["Low"]
            entry = (yMin + yMax) / 2
            stop_loss = yMax + 0.2 * (yMax - yMin)
            take_profit = entry - 2 * (stop_loss - entry)

            patterns.append({
                "name": "Fair Value Gap",
                "xMin": xMin,
                "xMax": xMax,
                "yMin": yMin,
                "yMax": yMax,
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "direction": "short",
                "color": "blue",
                "note": f"FVG detected. Entry: {entry:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}"
            })

    return patterns
