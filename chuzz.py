import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time

st.set_page_config(page_title="Live Trading Dashboard", layout="wide")

st.title("📈 Live Stock Dashboard")

# Sidebar
ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL")
interval = st.sidebar.selectbox("Select Interval", ["1m", "5m", "15m", "1h", "1d"], index=0)
lookback = st.sidebar.slider("Minutes of History", min_value=30, max_value=240, step=30)

# Main chart area
placeholder = st.empty()

def fetch_data():
    df = yf.download(tickers=ticker, period="1d", interval=interval, progress=False)
    
    # Flatten multi-index columns (fixes your error!)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df.dropna(inplace=True)
    df["RSI"] = ta.rsi(df["Close"], length=14)
    return df


while True:
    df = fetch_data()
    with placeholder.container():
        st.subheader(f"Live price for {ticker} — Interval: {interval}")
        st.line_chart(df[["Close", "RSI"]].tail(lookback))

        last_rsi = df["RSI"].dropna().iloc[-1]
        st.write(f"Latest RSI: **{round(last_rsi, 2)}**")

        if last_rsi < 30:
            st.error("🔔 RSI < 30 — Potential Buy Signal!")
        elif last_rsi > 70:
            st.warning("🔔 RSI > 70 — Potential Sell Signal!")
        else:
            st.info("RSI is neutral.")

    time.sleep(60)  # Refresh every 60 seconds
