from datetime import datetime, timedelta
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Live Trading Dashboard", layout="wide")

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
import requests
import plotly.graph_objects as go
from textblob import TextBlob
from rapidfuzz import fuzz

import websocket
import json
import threading

LIVE_PRICE = None
API_KEY = "d0e26d1r01qv1dmkj2bgd0e26d1r01qv1dmkj2c0"
TICKER = "AAPL"

def on_message(ws, message):
    global LIVE_PRICE
    data = json.loads(message)
    if data['type'] == 'trade':
        LIVE_PRICE = data['data'][0]['p']
        print(f"Live price for {TICKER}: {LIVE_PRICE}")

def on_open(ws):
    ws.send(json.dumps({
        "type": "subscribe",
        "symbol": TICKER
    }))

def run_ws():
    url = f"wss://ws.finnhub.io?token={API_KEY}"
    ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message)
    ws.run_forever()

threading.Thread(target=run_ws, daemon=True).start()

# === Global State ===
last_alert_time = None
last_trade_signal = None
last_news_headline = None
st_autorefresh(interval=60000, key="refresh")

# === Clock (center aligned) ===
now = datetime.now()
current_time = now.strftime("%I:%M:%S %p")
st.markdown(f"<h3 style='text-align:center;'>⏱️ Current Time: {current_time}</h3>", unsafe_allow_html=True)

# === Header ===
st.title("📈 Live Stock Dashboard")

# === Sidebar Inputs ===
ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL")
interval = st.sidebar.selectbox("Select Interval", ["1m", "5m", "15m", "1h", "1d"], index=0)
lookback = st.sidebar.slider("Minutes of History", min_value=30, max_value=240, step=30)
enable_alerts = st.sidebar.checkbox("Enable Discord Alerts", value=True)

placeholder = st.empty()

NEWS_API_KEY = "aa0de5faf38c418bb294c12ac5559726"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1369524379959955497/60qtH7hFrkT107Vol5gP4IOwzdYiYJ7KD_EVPxLcBx6bJNedfacpcbtpAMtPLrikCiM4"

POSITIVE_KEYWORDS = ["beat estimates", "record revenue", "surges", "acquisition", "partnership", "upgrade", "strong guidance", "expands"]
NEGATIVE_KEYWORDS = ["missed estimates", "downgrade", "layoffs", "recall", "plunges", "investigation", "lawsuit", "weak demand"]

def send_discord_alert(message):
    global last_alert_time
    if not enable_alerts:
        st.info("Discord alert skipped (alerts disabled).")
        return
    now = datetime.now()
    if last_alert_time is not None and (now - last_alert_time) < timedelta(minutes=5):
        st.info("⌛ Discord alert skipped (cooldown active).")
        return
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        if response.status_code == 204:
            st.success("✅ Discord alert sent.")
            last_alert_time = now
        else:
            st.warning(f"⚠️ Failed to send Discord alert. Status code: {response.status_code}")
    except Exception as e:
        st.error(f"Discord alert error: {e}")

def fetch_news(ticker):
    url = f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&language=en&pageSize=20&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])
        if not articles:
            return [{"headline": f"No news found for '{ticker.upper()}'", "source": "NewsAPI", "sentiment": "⚪ Neutral", "score": 0, "summary": "No headlines returned."}]
        scored_articles = []
        for a in articles:
            headline = a['title']
            source = a['source']['name']
            lower = headline.lower()
            sentiment_raw = TextBlob(headline).sentiment.polarity
            score = sentiment_raw
            keyword_count = 0
            for kw in POSITIVE_KEYWORDS:
                if kw in lower:
                    score += 0.3
                    keyword_count += 1
            for kw in NEGATIVE_KEYWORDS:
                if kw in lower:
                    score -= 0.3
                    keyword_count += 1
            if keyword_count == 0 and abs(score) < 0.1:
                continue
            sentiment_label = "🟢 Positive" if score > 0.1 else "🔴 Negative" if score < -0.1 else "⚪ Neutral"
            summary = "Relevant event."
            if "beat" in lower or "record" in lower:
                summary = "Earnings or performance exceeded expectations."
            elif "missed" in lower or "downgrade" in lower:
                summary = "Earnings or outlook below expectations."
            elif "acquisition" in lower or "partnership" in lower:
                summary = "Positive business expansion or deal."
            elif "lawsuit" in lower or "investigation" in lower:
                summary = "Legal or regulatory risk could impact stock."
            scored_articles.append({
                "headline": headline,
                "source": source,
                "sentiment": sentiment_label,
                "score": score,
                "summary": summary
            })
        seen = set()
        deduped = []
        for article in scored_articles:
            key = article["headline"].strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(article)
        deduped.sort(key=lambda x: abs(x['score']), reverse=True)
        return deduped[:5] if deduped else [{"headline": f"No strong news found.", "source": "NewsAPI", "sentiment": "⚪ Neutral", "score": 0, "summary": "No headlines matched rules."}]
    except Exception as e:
        return [{"headline": f"❌ Error fetching news: {e}", "source": "", "sentiment": "⚪ Neutral", "score": 0, "summary": "API error"}]

def plot_candlestick(df):
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Candlestick"
            )
        ]
    )
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(tickformat="%I:%M %p")
    )
    return fig

def fetch_data():
    interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
    buffer = 60
    minutes = (lookback + buffer) * interval_map[interval]
    period_days = max(1, minutes // 1440 + 1)
    try:
        df = yf.download(ticker, period=f"{period_days}d", interval=interval, progress=False)
    except Exception as e:
        st.warning(f"⚠️ Data download failed: {e}")
        return None
    if df is None or df.empty or "Close" not in df.columns or df["Close"].dropna().empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    try:
        df["RSI"] = ta.rsi(df["Close"], length=14)
        if len(df) >= 35:
            macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
            df["MACD"] = macd["MACD_12_26_9"]
            df["MACD_signal"] = macd["MACDs_12_26_9"]
        else:
            df["MACD"] = None
            df["MACD_signal"] = None
        df["EMA_9"] = ta.ema(df["Close"], length=9)
        df["EMA_21"] = ta.ema(df["Close"], length=21)
    except Exception as e:
        st.warning(f"⚠️ Indicator error: {e}")
        return None
    return df

# === Main Loop ===
while True:
    df = fetch_data()
    if df is None:
        st.error("❌ Invalid ticker or no data.")
        time.sleep(30)
        continue
    if df["MACD"].isna().all() or df["MACD_signal"].isna().all():
        st.warning("⚠️ Not enough data for MACD.")
        time.sleep(60)
        continue

    with placeholder.container():
        st.subheader(f"Live price for {ticker} — Interval: {interval}")

        try:
            # Use live price if available
            current = LIVE_PRICE if LIVE_PRICE else df["Close"].iloc[-1]

            # 1️⃣ Intra-candle move
            latest_close = df["Close"].iloc[-1]
            real_change = current - latest_close
            real_pct = (real_change / latest_close) * 100

            # 2️⃣ Daily move vs. yesterday’s official close
            try:
                previous_close = yf.Ticker(ticker).info["previousClose"]
                daily_change = current - previous_close
                daily_pct = (daily_change / previous_close) * 100
            except:
                previous_close = None
                daily_pct = 0

            # Display with both changes
            arrow = "🔺" if real_change > 0 else "🔻" if real_change < 0 else "⏸️"
            status = "🟢 Price from latest candle (synced)"
            st.markdown(f"### {arrow} Live Price: **${current:.2f}**  &nbsp;&nbsp; {status}")
            st.caption(f"📊 Daily change vs previous close: {daily_pct:+.2f}%")
            st.caption(f"🕒 Intra-candle move: {real_pct:+.2f}%")
        except:
            st.warning("⚠️ Price fetch failed.")

        st.plotly_chart(plot_candlestick(df.tail(lookback)), use_container_width=True)
        st.line_chart(df[["Close", "RSI"]].tail(lookback))

                # === Indicator Values ===
        last_rsi = df["RSI"].dropna().iloc[-1]
        last_macd = df["MACD"].dropna().iloc[-1]
        last_macd_signal = df["MACD_signal"].dropna().iloc[-1]
        ema_9 = df["EMA_9"].dropna().iloc[-1]
        ema_21 = df["EMA_21"].dropna().iloc[-1]

        st.write(f"Latest RSI: **{last_rsi:.2f}**")
        st.write(f"Latest MACD: **{last_macd:.4f}**, Signal: **{last_macd_signal:.4f}**")
        st.write(f"EMA 9: **{ema_9:.2f}**, EMA 21: **{ema_21:.2f}**")

        # === Trade Signal Logic ===
        checks = []
        bull_score = 0
        if last_rsi < 30:
            bull_score += 1
            checks.append("✔️ RSI oversold")
        else:
            checks.append("❌ RSI not oversold")
        if last_macd > last_macd_signal:
            bull_score += 1
            checks.append("✔️ MACD bullish")
        else:
            checks.append("❌ MACD not bullish")
        if ema_9 > ema_21:
            bull_score += 1
            checks.append("✔️ EMA crossover bullish")
        else:
            checks.append("❌ EMA not bullish")

        confidence = int((bull_score / 3) * 100)

        if bull_score >= 2:
            signal = "🟢 Buy"
            st.success(f"{signal} — {bull_score}/3 indicators match. Confidence: {confidence}%")
            if enable_alerts and signal != last_trade_signal:
                send_discord_alert(f"{signal} for `{ticker}`\nConfidence: {confidence}%\n" + "\n".join(checks))
                last_trade_signal = signal
        else:
            bear_score = 0
            checks = []
            if last_rsi > 70:
                bear_score += 1
                checks.append("✔️ RSI overbought")
            else:
                checks.append("❌ RSI not overbought")
            if last_macd < last_macd_signal:
                bear_score += 1
                checks.append("✔️ MACD bearish")
            else:
                checks.append("❌ MACD not bearish")
            if ema_9 < ema_21:
                bear_score += 1
                checks.append("✔️ EMA crossover bearish")
            else:
                checks.append("❌ EMA not bearish")
            confidence = int((bear_score / 3) * 100)
            if bear_score >= 2:
                signal = "🔴 Sell"
                st.warning(f"{signal} — {bear_score}/3 indicators match. Confidence: {confidence}%")
                if enable_alerts and signal != last_trade_signal:
                    send_discord_alert(f"{signal} for `{ticker}`\nConfidence: {confidence}%\n" + "\n".join(checks))
                    last_trade_signal = signal
            else:
                signal = "⚪ Hold"
                st.info("⚪ Hold — Indicators mixed or neutral.")
                last_trade_signal = signal

        for check in checks:
            st.write(check)

        # === Volatility Summary ===
        volatility = df["Close"].pct_change().tail(lookback).std() * 100
        if volatility > 1.5:
            vol_level = f"🔴 High ({volatility:.2f}%)"
        elif volatility > 0.5:
            vol_level = f"🟡 Medium ({volatility:.2f}%)"
        else:
            vol_level = f"🟢 Low ({volatility:.2f}%)"

        st.sidebar.markdown("### 🧠 Trade Summary")
        st.sidebar.markdown(f"**Signal:** {signal}")
        st.sidebar.markdown(f"**Confidence:** {confidence}%")
        st.sidebar.markdown(f"**Volatility:** {vol_level}")
        st.sidebar.markdown("---")
        for check in checks:
            st.sidebar.markdown(check)

    
    # === News Section ===
        st.sidebar.markdown("### 📰 News + Sentiment")
        news = fetch_news(ticker)
        sentiment_total = 0
        pos, neg, neu = 0, 0, 0
        for article in news:
            if "Positive" in article["sentiment"]:
                pos += 1
            elif "Negative" in article["sentiment"]:
                neg += 1
            else:
                neu += 1
            sentiment_total += article["score"]

        st.sidebar.markdown(f"**Sentiment:** 🟢 {pos} | 🔴 {neg} | ⚪ {neu}")
        st.sidebar.markdown("---")

        for article in news:
            st.sidebar.markdown(
                f"**{article['sentiment']}** — {article['headline']}\n"
                f"🧠 *{article['summary']}*\n"
                f"📣 _Source: {article['source']}_"
            )
            st.sidebar.markdown("---")

        avg_sentiment = sentiment_total / len(news) if news else 0
        if avg_sentiment > 0.2:
            st.sidebar.success("📈 Suggestion: BUY — Positive sentiment")
            if enable_alerts and news[0]["headline"] != last_news_headline:
                send_discord_alert(f"🟢 News Suggests BUY: {news[0]['headline']}")
                last_news_headline = news[0]["headline"]
        elif avg_sentiment < -0.2:
            st.sidebar.error("📉 Suggestion: SELL — Negative sentiment")
            if enable_alerts and news[0]["headline"] != last_news_headline:
                send_discord_alert(f"🔴 News Suggests SELL: {news[0]['headline']}")
                last_news_headline = news[0]["headline"]
        else:
            st.sidebar.info("📊 Suggestion: HOLD — Mixed/Neutral sentiment")

    time.sleep(60)
