import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
import requests
import plotly.graph_objects as go
from textblob import TextBlob
import csv
from datetime import datetime
import os
import json


NEWS_API_KEY = "aa0de5faf38c418bb294c12ac5559726"

POSITIVE_KEYWORDS = ["beat estimates", "record revenue", "surges", "acquisition", "partnership", "upgrade", "strong guidance", "expands"]
NEGATIVE_KEYWORDS = ["missed estimates", "downgrade", "layoffs", "recall", "plunges", "investigation", "lawsuit", "weak demand"]

def fetch_news(ticker):
    import requests
    from textblob import TextBlob

    KEYWORDS_POSITIVE = [
        "beat estimates", "record revenue", "acquisition", "partnership", "upgrade",
        "strong guidance", "surge", "buyback", "growth", "momentum"
    ]
    KEYWORDS_NEGATIVE = [
        "missed estimates", "downgrade", "layoffs", "lawsuit", "recall",
        "plunge", "investigation", "weak demand", "fraud", "disappoint"
    ]

    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={ticker}&sortBy=publishedAt&language=en&pageSize=10&apiKey=aa0de5faf38c418bb294c12ac5559726"
    )

    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])
        scored_articles = []

        for a in articles:
            headline = a['title']
            source = a['source']['name']
            lower = headline.lower()
            sentiment_raw = TextBlob(headline).sentiment.polarity

            # Keyword boost scoring
            score = sentiment_raw
            keyword_count = 0
            for kw in KEYWORDS_POSITIVE:
                if kw in lower:
                    score += 0.3
                    keyword_count += 1
            for kw in KEYWORDS_NEGATIVE:
                if kw in lower:
                    score -= 0.3
                    keyword_count += 1

            # Ignore irrelevant headlines
            if keyword_count == 0:
                continue

            sentiment_label = (
                "🟢 Positive" if score > 0.1 else
                "🔴 Negative" if score < -0.1 else
                "⚪ Neutral"
            )

            # Summary logic
            if "beat" in lower or "record" in lower:
                summary = "Earnings or performance exceeded expectations."
            elif "missed" in lower or "downgrade" in lower:
                summary = "Earnings or outlook below expectations."
            elif "acquisition" in lower or "partnership" in lower:
                summary = "Positive business expansion or deal."
            elif "lawsuit" in lower or "investigation" in lower:
                summary = "Legal or regulatory risk could impact stock."
            else:
                summary = "Relevant event, possibly affecting market reaction."

            scored_articles.append({
                "headline": headline,
                "source": source,
                "sentiment": sentiment_label,
                "score": score,
                "summary": summary
            })

        # Sort by strongest sentiment
        scored_articles.sort(key=lambda x: abs(x['score']), reverse=True)

        # Return top 3–5 strongest relevant headlines
        return scored_articles[:5]

    except Exception as e:
        return [{
            "headline": f"❌ Error fetching news: {e}",
            "source": "",
            "sentiment": "⚪ Neutral",
            "score": 0,
            "summary": "N/A"
        }]

def plot_candlestick(df, title="Candlestick Chart"):
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
    title=title,
    xaxis_title="Time",
    yaxis_title="Price",
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    height=500,
    margin=dict(l=10, r=10, t=40, b=10),
    xaxis=dict(
        tickformat="%I:%M %p"  # 👈 this makes it 12-hour AM/PM format
    )
)

    return fig


DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1369524379959955497/60qtH7hFrkT107Vol5gP4IOwzdYiYJ7KD_EVPxLcBx6bJNedfacpcbtpAMtPLrikCiM4"

def send_discord_alert(message):
    if not enable_alerts:
        st.info("Discord alert skipped (alerts disabled).")
        return

    data = {
        "content": message
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            st.success("✅ Discord alert sent.")
        else:
            st.warning(f"⚠️ Failed to send Discord alert. Status code: {response.status_code}")
    except Exception as e:
        st.error(f"Discord alert error: {e}")

ALERT_TRACK_FILE = "last_alert.json"

def load_last_alerts():
    if os.path.exists(ALERT_TRACK_FILE):
        with open(ALERT_TRACK_FILE, "r") as f:
            return json.load(f)
    return {}

def save_last_alerts(data):
    with open(ALERT_TRACK_FILE, "w") as f:
        json.dump(data, f)

def log_signal(ticker, signal_type, confidence, indicators, sentiment_score, headline):
    log_file = "signals_log.csv"
    file_exists = os.path.isfile(log_file)

    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Ticker", "Signal", "Confidence", "Indicators", "News Sentiment", "Headline"])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            ticker.upper(),
            signal_type,
            f"{confidence}%",
            "; ".join(indicators),
            round(sentiment_score, 2),
            headline
        ])

st.set_page_config(page_title="Live Trading Dashboard", layout="wide")

st.title("📈 Live Stock Dashboard")

# Sidebar
ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL")
interval = st.sidebar.selectbox("Select Interval", ["1m", "5m", "15m", "1h", "1d"], index=0)
lookback = st.sidebar.slider("Minutes of History", min_value=30, max_value=240, step=30)
enable_alerts = st.sidebar.checkbox("Enable Discord Alerts", value=True)

# Main chart area
placeholder = st.empty()

def fetch_data():
    interval_minutes = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "1d": 1440
    }

    # Calculate how much total time is needed
    buffer = 60  # extra candles for indicators like MACD
    needed_minutes = lookback + buffer
    interval_length = interval_minutes[interval]
    total_minutes = needed_minutes * interval_length
    period_days = max(1, total_minutes // 1440 + 1)

    df = yf.download(
        tickers=ticker,
        period=f"{period_days}d",
        interval=interval,
        progress=False
    )

    # Flatten MultiIndex (if needed)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)

    # === RSI ===
    df["RSI"] = ta.rsi(df["Close"], length=14)

    # === MACD ===
    if len(df) >= 35:
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACD_signal"] = macd["MACDs_12_26_9"]
    else:
        df["MACD"] = None
        df["MACD_signal"] = None

    # === EMA Crossover ===
    df["EMA_9"] = ta.ema(df["Close"], length=9)
    df["EMA_21"] = ta.ema(df["Close"], length=21)

    return df

last_alerts = load_last_alerts()
last_trade_signal = last_alerts.get("signal")
last_news_headline = last_alerts.get("news")

while True:
    df = fetch_data()

    if df["MACD"].isna().all() or df["MACD_signal"].isna().all():
        st.warning("⚠️ Not enough data to calculate MACD at this interval. Try a smaller timeframe.")
        time.sleep(60)
        continue

    with placeholder.container():
        st.subheader(f"Live price for {ticker} — Interval: {interval}")
        
        # Charts
        st.plotly_chart(plot_candlestick(df.tail(lookback)), use_container_width=True)
        st.line_chart(df[["Close", "RSI"]].tail(lookback))

        # Indicator Values
        last_rsi = df["RSI"].dropna().iloc[-1]
        last_macd = df["MACD"].dropna().iloc[-1]
        last_macd_signal = df["MACD_signal"].dropna().iloc[-1]
        ema_9 = df["EMA_9"].dropna().iloc[-1]
        ema_21 = df["EMA_21"].dropna().iloc[-1]

        st.write(f"Latest RSI: **{round(last_rsi, 2)}**")
        st.write(f"Latest MACD: **{round(last_macd, 4)}**, Signal Line: **{round(last_macd_signal, 4)}**")
        st.write(f"EMA 9: **{round(ema_9, 2)}**, EMA 21: **{round(ema_21, 2)}**")

        # === News Headlines + Sentiment in Sidebar ===
        st.sidebar.markdown("---")
        st.sidebar.subheader("🗞️ News + Sentiment")

        news = fetch_news(ticker)
        sentiment_total = 0

        for article in news:
            st.sidebar.markdown(
                f"**{article['sentiment']}** — {article['headline']}\n"
                f"🧠 *{article['summary']}*\n"
                f"📣 _Source: {article['source']}_"
            )
            st.sidebar.markdown("---")
            sentiment_total += article["score"]

        # News-based recommendation
        avg_sentiment = sentiment_total / len(news) if news else 0

        if avg_sentiment > 0.2:
            st.sidebar.success("📈 Suggestion: BUY — Positive sentiment")
            if enable_alerts and news[0]["headline"] != last_news_headline:
                send_discord_alert(
                    f"**🟢 News Suggests BUY for `{ticker}`**\n"
                    f"{news[0]['headline']} ({news[0]['source']})\n"
                    f"Summary: {news[0]['summary']}"
                )

                # Update memory
                last_alerts["news"] = news[0]["headline"]
                save_last_alerts(last_alerts)

                last_news_headline = news[0]["headline"]
        elif avg_sentiment < -0.2:
            st.sidebar.error("📉 Suggestion: SELL — Negative sentiment")
            if enable_alerts and news[0]["headline"] != last_news_headline:
                send_discord_alert(
                    f"**🔴 News Suggests SELL for `{ticker}`**\n"
                    f"{news[0]['headline']} ({news[0]['source']})\n"
                    f"Summary: {news[0]['summary']}"
                )

                # Update memory
                last_alerts["news"] = news[0]["headline"]
                save_last_alerts(last_alerts)

                last_news_headline = news[0]["headline"]
        else:
            st.sidebar.info("📊 Suggestion: HOLD — Mixed/Neutral sentiment")
            last_news_headline = news[0]["headline"]

        # === Trade Signal Logic (RSI + MACD + EMA) ===
        signal = ""
        reason = ""
        score = 0
        checks = []

        if last_rsi < 30:
            score += 1
            checks.append("✔️ RSI is oversold (< 30)")
        else:
            checks.append("❌ RSI not oversold")

        if last_macd > last_macd_signal:
            score += 1
            checks.append("✔️ MACD crossed above signal")
        else:
            checks.append("❌ MACD not bullish")

        if ema_9 > ema_21:
            score += 1
            checks.append("✔️ EMA 9 > EMA 21 (bullish trend)")
        else:
            checks.append("❌ EMA crossover not bullish")

        confidence = int((score / 3) * 100)

        if score >= 2:
            signal = "🟢 Buy"
            reason = f"{score}/3 indicators aligned. Confidence Score: {confidence}%"
            st.success(f"{signal} — {reason}")
            for check in checks:
                st.write(check)

            if enable_alerts and last_trade_signal != signal:
                send_discord_alert(
                    f"**{signal}** for `{ticker}`\n{reason}\n" + "\n".join(checks)
                )
                log_signal(ticker, signal, confidence, checks, avg_sentiment, news[0]["headline"])
                
                # Update memory
                last_alerts["signal"] = signal
                save_last_alerts(last_alerts)

                last_trade_signal = signal
        else:
            # SELL logic
            score = 0
            checks = []

            if last_rsi > 70:
                score += 1
                checks.append("✔️ RSI is overbought (> 70)")
            else:
                checks.append("❌ RSI not overbought")

            if last_macd < last_macd_signal:
                score += 1
                checks.append("✔️ MACD crossed below signal")
            else:
                checks.append("❌ MACD not bearish")

            if ema_9 < ema_21:
                score += 1
                checks.append("✔️ EMA 9 < EMA 21 (bearish trend)")
            else:
                checks.append("❌ EMA crossover not bearish")

            confidence = int((score / 3) * 100)

            if score >= 2:
                signal = "🔴 Sell"
                reason = f"{score}/3 indicators aligned. Confidence Score: {confidence}%"
                st.warning(f"{signal} — {reason}")
                for check in checks:
                    st.write(check)

                if enable_alerts and last_trade_signal != signal:
                    send_discord_alert(
                        f"**{signal}** for `{ticker}`\n{reason}\n" + "\n".join(checks)
                    )
                    log_signal(ticker, signal, confidence, checks, avg_sentiment, news[0]["headline"])

                    # Update memory
                    last_alerts["signal"] = signal
                    save_last_alerts(last_alerts)

                    last_trade_signal = signal
            else:
                st.info("Indicators are neutral — no strong buy or sell signal right now.")
                last_trade_signal = "Neutral"
            
            # === Signal Log Viewer ===
        st.markdown("---")
        with st.expander("📜 View Signal History"):
            try:
                df_log = pd.read_csv("signals_log.csv")
                st.dataframe(df_log.tail(20), use_container_width=True)
            except FileNotFoundError:
                st.info("No signals logged yet.")

    time.sleep(60)