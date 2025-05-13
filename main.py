from datetime import datetime, timedelta
import time
import json
import threading

import streamlit as st # type: ignore
from streamlit_autorefresh import st_autorefresh # type: ignore
import yfinance as yf # type: ignore
import pandas as pd
import pandas_ta as ta # type: ignore
import requests # type: ignore
import plotly.graph_objects as go  # type: ignore
from textblob import TextBlob # type: ignore
from rapidfuzz import fuzz # type: ignore
import websocket # type: ignore
import pytz

# === Streamlit Setup ===
st.set_page_config(page_title="NeuroTraderAI Dashboard", layout="wide")
st_autorefresh(interval=60000, key="refresh")

# === Global State ===
LIVE_PRICE = None
last_alert_time = None
last_trade_signal = None
last_news_headline = None

# === API Keys & URLs ===
FINNHUB_API_KEY    = "d0e26d1r01qv1dmkj2bgd0e26d1r01qv1dmkj2c0"
FINNHUB_WS         = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
NEWS_API_KEY       = "aa0de5faf38c418bb294c12ac5559726"
DISCORD_WEBHOOK_URL= "https://discord.com/api/webhooks/1369524379959955497/60qtH7hFrkT107Vol5gP4IOwzdYiYJ7KD_EVPxLcBx6bJNedfacpcbtpAMtPLrikCiM4"
POSITIVE_KEYWORDS  = ["beat estimates","record revenue","surges","acquisition","partnership","upgrade","strong guidance","expands"]
NEGATIVE_KEYWORDS  = ["missed estimates","downgrade","layoffs","recall","plunges","investigation","lawsuit","weak demand"]

# === WebSocket Callbacks ===
def on_message(ws, message):
    global LIVE_PRICE
    data = json.loads(message)
    if data.get('type') == 'trade':
        LIVE_PRICE = data['data'][0]['p']

def on_open(ws):
    ws.send(json.dumps({"type":"subscribe","symbol":TICKER}))

def run_ws():
    ws = websocket.WebSocketApp(FINNHUB_WS, on_open=on_open, on_message=on_message)
    ws.run_forever()

# We'll start the WS thread after we know TICKER
ws_thread = None

# === Helper Functions ===

def send_discord_alert(message):
    global last_alert_time
    if not enable_alerts:
        return
    now = datetime.now()
    if last_alert_time and (now - last_alert_time) < timedelta(minutes=5):
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        if r.status_code == 204:
            last_alert_time = now
    except:
        pass

def fetch_news(ticker):
    url = f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&language=en&pageSize=20&apiKey={NEWS_API_KEY}"
    try:
        arts = requests.get(url).json().get("articles", [])
    except:
        return []
    scored = []
    for a in arts:
        h = a.get("title","")
        s = a.get("source",{}).get("name","")
        lower = h.lower()
        score = TextBlob(h).sentiment.polarity
        for kw in POSITIVE_KEYWORDS:
            if kw in lower: score += 0.3
        for kw in NEGATIVE_KEYWORDS:
            if kw in lower: score -= 0.3
        if abs(score) < 0.1: continue
        sentiment_label = "🟢 Positive" if score > 0.1 else "🔴 Negative"
        summary = "Relevant event."
        if "beat" in lower or "record" in lower:
            summary = "Earnings beat/outpaced expectations."
        elif "missed" in lower or "downgrade" in lower:
            summary = "Earnings miss/negative revision."
        scored.append({
            "headline": h, "source": s,
            "sentiment": sentiment_label, "score": score,
            "summary": summary
        })
    # dedupe & sort
    seen = set(); out = []
    for art in scored:
        key = art["headline"].strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(art)
    out.sort(key=lambda x: abs(x["score"]), reverse=True)
    return out[:5]

def fetch_data(ticker, interval, lookback):
    imap = {"1m":1,"5m":5,"15m":15,"1h":60,"1d":1440}
    buf = 60
    minutes = (lookback + buf) * imap[interval]
    period_days = max(1, minutes // 1440 + 1)
    try:
        df = yf.download(ticker, period=f"{period_days}d", interval=interval, progress=False)
    except:
        return None
    if df is None or df.empty or "Close" not in df.columns:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    # Indicators
    df["RSI"] = ta.rsi(df["Close"], length=14)
    if len(df) >= 35:
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        df["MACD"], df["MACD_signal"] = macd["MACD_12_26_9"], macd["MACDs_12_26_9"]
    else:
        df["MACD"], df["MACD_signal"] = None, None
    df["EMA_9"]  = ta.ema(df["Close"], length=9)
    df["EMA_21"] = ta.ema(df["Close"], length=21)
    return df

def plot_candlestick(df):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"]
    )])
    fig.update_layout(
        xaxis_title="Time", yaxis_title="Price",
        xaxis_rangeslider_visible=False, template="plotly_dark",
        height=500, margin=dict(l=10,r=10,t=40,b=10),
        xaxis=dict(type="date", tickformat="%I:%M %p")
    )
    return fig

def analyze_candles(df, lookback=30):
    cdl = df.ta
    vals = {
        "Hammer":            cdl.cdl_hammer().iloc[-1],
        "Shooting Star":     cdl.cdl_shooting_star().iloc[-1],
        "Bullish Engulfing": cdl.cdl_engulfing().iloc[-1],
        "Doji":              cdl.cdl_doji().iloc[-1],
        "Morning Star":      cdl.cdl_morning_star().iloc[-1],
        "Evening Star":      cdl.cdl_evening_star().iloc[-1],
    }
    patterns = []
    for name, v in vals.items():
        if v > 0:
            patterns.append(name)
        elif v < 0 and name == "Bullish Engulfing":
            patterns.append("Bearish Engulfing")
    avg_vol = df["Volume"].tail(lookback).mean()
    last_vol = df["Volume"].iloc[-1]
    vol_spike = last_vol > avg_vol * 1.5
    score = len(patterns) + (1 if vol_spike else 0)
    grade = {0:"C",1:"B",2:"A",3:"A+"}.get(min(score,3),"C")
    return patterns, vol_spike, grade

# === Sidebar Inputs ===
ticker = st.sidebar.text_input("Ticker", "AAPL").upper()
interval = st.sidebar.selectbox("Interval", ["1m","5m","15m","1h","1d"], index=0)
lookback = st.sidebar.slider("History (minutes)", 30, 240, 60, 30)
enable_alerts = st.sidebar.checkbox("Discord Alerts", True)

# Start WebSocket thread with selected ticker
TICKER = ticker
if ws_thread is None:
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

# === Header & Timestamps ===
eastern = pytz.timezone("America/New_York")
now   = datetime.now(eastern).strftime("%I:%M:%S %p %Z")
build = datetime.now(eastern).strftime("%Y-%m-%d %I:%M:%S %p")
st.markdown(f"<h3 style='text-align:center;'>⏱️ Current Time: {now}</h3>", unsafe_allow_html=True)
st.title("💡 NeuroTraderAI Live Dashboard")
st.markdown(f"<p style='text-align:right; color:gray;'>🛠️ Last build: {build} ET</p>", unsafe_allow_html=True)

placeholder = st.empty()

# === Main Loop ===
while True:
    df = fetch_data(ticker, interval, lookback)
    if df is None:
        st.error("❌ Invalid ticker or no data.")
        time.sleep(30)
        continue
    if df["MACD"].isna().all():
        st.warning("⚠️ Not enough data for MACD.")
        time.sleep(60)
        continue

    with placeholder.container():
        # --- Live Price & % Changes ---
        current    = LIVE_PRICE or df["Close"].iloc[-1]
        latest     = df["Close"].iloc[-1]
        real_ch    = current - latest
        real_pct   = (real_ch / latest) * 100
        prev_close = yf.Ticker(ticker).info.get("previousClose", latest)
        day_pct    = (current - prev_close) / prev_close * 100
        arrow      = "🔺" if real_ch > 0 else "🔻" if real_ch < 0 else "⏸️"
        st.markdown(f"### {arrow} ${current:.2f}   (Day: {day_pct:+.2f}%, Candle: {real_pct:+.2f}%)")

        # --- Charts ---
        st.plotly_chart(plot_candlestick(df.tail(lookback)), use_container_width=True)
        st.line_chart(df[["Close","RSI"]].tail(lookback))

        # --- Candlestick Pattern Analysis ---
        patterns, vol_spike, grade = analyze_candles(df, lookback)
        st.markdown("## 🕯️ Candlestick Patterns")
        if patterns:
            st.write("Detected: " + ", ".join(patterns))
        else:
            st.write("No major patterns detected.")
        st.write(f"🔊 Volume spike: {'💥 Yes' if vol_spike else 'No'}")
        st.write(f"🌟 Trader Grade: **{grade}**")

        # --- Indicator Values & Signal Logic ---
        last_rsi         = df["RSI"].dropna().iloc[-1]
        last_macd        = df["MACD"].dropna().iloc[-1]
        last_macd_signal = df["MACD_signal"].dropna().iloc[-1]
        ema_9            = df["EMA_9"].dropna().iloc[-1]
        ema_21           = df["EMA_21"].dropna().iloc[-1]
        st.write(f"Latest RSI: **{last_rsi:.2f}**")
        st.write(f"Latest MACD: **{last_macd:.4f}**, Signal: **{last_macd_signal:.4f}**")
        st.write(f"EMA 9: **{ema_9:.2f}**, EMA 21: **{ema_21:.2f}**")

        checks = []
        bull_score = 0
        if last_rsi < 30:
            bull_score += 1; checks.append("✔️ RSI oversold")
        else:
            checks.append("❌ RSI not oversold")
        if last_macd > last_macd_signal:
            bull_score += 1; checks.append("✔️ MACD bullish")
        else:
            checks.append("❌ MACD not bullish")
        if ema_9 > ema_21:
            bull_score += 1; checks.append("✔️ EMA bullish")
        else:
            checks.append("❌ EMA not bullish")

        confidence = int((bull_score/3)*100)
        if bull_score >= 2:
            signal = "🟢 Buy"
            st.success(f"{signal} — {bull_score}/3 match. Confidence: {confidence}%")
            if enable_alerts and signal != last_trade_signal:
                send_discord_alert(f"{signal} for {ticker}\nConfidence: {confidence}%\n" + "\n".join(checks))
                last_trade_signal = signal
        else:
            bear_score = 0; checks = []
            if last_rsi > 70:
                bear_score += 1; checks.append("✔️ RSI overbought")
            else:
                checks.append("❌ RSI not overbought")
            if last_macd < last_macd_signal:
                bear_score += 1; checks.append("✔️ MACD bearish")
            else:
                checks.append("❌ MACD not bearish")
            if ema_9 < ema_21:
                bear_score += 1; checks.append("✔️ EMA bearish")
            else:
                checks.append("❌ EMA not bearish")
            confidence = int((bear_score/3)*100)
            if bear_score >= 2:
                signal = "🔴 Sell"
                st.warning(f"{signal} — {bear_score}/3 match. Confidence: {confidence}%")
                if enable_alerts and signal != last_trade_signal:
                    send_discord_alert(f"{signal} for {ticker}\nConfidence: {confidence}%\n" + "\n".join(checks))
                    last_trade_signal = signal
            else:
                signal = "⚪ Hold"
                st.info("⚪ Hold — neutral.")
                last_trade_signal = signal

        for c in checks:
            st.write(c)

        # --- Volatility ---
        vol = df["Close"].pct_change().tail(lookback).std()*100
        vol_level = "🔴 High" if vol>1.5 else "🟡 Medium" if vol>0.5 else "🟢 Low"
        st.sidebar.markdown("### 🧠 Trade Summary")
        st.sidebar.markdown(f"**Signal:** {signal}")
        st.sidebar.markdown(f"**Confidence:** {confidence}%")
        st.sidebar.markdown(f"**Volatility:** {vol_level} ({vol:.2f}%)")
        st.sidebar.markdown("---")
        for c in checks:
            st.sidebar.markdown(c)

        # --- News & Sentiment ---
        st.sidebar.markdown("### 📰 News + Sentiment")
        news = fetch_news(ticker)
        pos = neg = neu = 0; total = 0
        for art in news:
            if "Positive" in art["sentiment"]: pos+=1
            elif "Negative" in art["sentiment"]: neg+=1
            else: neu+=1
            total+=art["score"]
            st.sidebar.markdown(f"**{art['sentiment']}** — {art['headline']}\n🧠 *{art['summary']}*\n📣 _{art['source']}_")
            st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Sentiment:** 🟢 {pos} | 🔴 {neg} | ⚪ {neu}")
        avg = total/len(news) if news else 0
        if avg>0.2:
            st.sidebar.success("📈 Suggestion: BUY")
            if enable_alerts and news[0]["headline"]!=last_news_headline:
                send_discord_alert(f"🟢 News BUY: {news[0]['headline']}")
                last_news_headline=news[0]["headline"]
        elif avg< -0.2:
            st.sidebar.error("📉 Suggestion: SELL")
            if enable_alerts and news[0]["headline"]!=last_news_headline:
                send_discord_alert(f"🔴 News SELL: {news[0]['headline']}")
                last_news_headline=news[0]["headline"]
        else:
            st.sidebar.info("📊 Suggestion: HOLD")

    time.sleep(60)
