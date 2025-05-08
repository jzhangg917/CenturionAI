import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
import requests
import plotly.graph_objects as go
from textblob import TextBlob
from datetime import datetime
from fuzzywuzzy import fuzz


NEWS_API_KEY = "aa0de5faf38c418bb294c12ac5559726"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1369524379959955497/60qtH7hFrkT107Vol5gP4IOwzdYiYJ7KD_EVPxLcBx6bJNedfacpcbtpAMtPLrikCiM4"

POSITIVE_KEYWORDS = ["beat estimates", "record revenue", "surges", "acquisition", "partnership", "upgrade", "strong guidance", "expands"]
NEGATIVE_KEYWORDS = ["missed estimates", "downgrade", "layoffs", "recall", "plunges", "investigation", "lawsuit", "weak demand"]

st.set_page_config(page_title="Live Trading Dashboard", layout="wide")
st.title("📈 Live Stock Dashboard")

ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL")
interval = st.sidebar.selectbox("Select Interval", ["1m", "5m", "15m", "1h", "1d"], index=0)
lookback = st.sidebar.slider("Minutes of History", min_value=30, max_value=240, step=30)
enable_alerts = st.sidebar.checkbox("Enable Discord Alerts", value=True)

placeholder = st.empty()

def send_discord_alert(message):
    if not enable_alerts:
        st.info("Discord alert skipped (alerts disabled).")
        return
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        if response.status_code == 204:
            st.success("✅ Discord alert sent.")
        else:
            st.warning(f"⚠️ Failed to send Discord alert. Status code: {response.status_code}")
    except Exception as e:
        st.error(f"Discord alert error: {e}")

def fetch_news(ticker):
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={ticker}&sortBy=publishedAt&language=en&pageSize=20&apiKey={NEWS_API_KEY}"
    )

    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])

        if not articles:
            return [{
                "headline": f"No news found for '{ticker.upper()}'",
                "source": "NewsAPI",
                "sentiment": "⚪ Neutral",
                "score": 0,
                "summary": "No headlines returned for this symbol."
            }]

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

            sentiment_label = (
                "🟢 Positive" if score > 0.1 else
                "🔴 Negative" if score < -0.1 else
                "⚪ Neutral"
            )

            summary = "Relevant event, possibly affecting market reaction."
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

        # Basic deduplication by headline string
        seen = set()
        deduped = []
        for article in scored_articles:
            key = article["headline"].strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(article)

        deduped.sort(key=lambda x: abs(x['score']), reverse=True)
        return deduped[:5] if deduped else [{
            "headline": f"No strong relevant news found for '{ticker.upper()}'",
            "source": "NewsAPI",
            "sentiment": "⚪ Neutral",
            "score": 0,
            "summary": "No headlines matched filtering rules."
        }]

    except Exception as e:
        return [{
            "headline": f"❌ Error fetching news for '{ticker.upper()}': {e}",
            "source": "",
            "sentiment": "⚪ Neutral",
            "score": 0,
            "summary": "API request failed or timed out."
        }]

def plot_candlestick(df, title="Candlestick Chart"):
    import plotly.graph_objects as go

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
        xaxis=dict(tickformat="%I:%M %p")
    )
    return fig

def fetch_data():
    interval_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
    buffer = 60
    total_min = (lookback + buffer) * interval_minutes[interval]
    period_days = max(1, total_min // 1440 + 1)

    try:
        df = yf.download(ticker, period=f"{period_days}d", interval=interval, progress=False)
    except Exception as e:
        st.warning(f"⚠️ Failed to download data: {e}")
        return None

    # Check for garbage or missing data
    if (
        df is None or
        df.empty or
        "Close" not in df.columns or
        df["Close"].dropna().empty
    ):
        return None

    # Fix MultiIndex if it exists
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)

    try:
        # === Technical Indicators ===
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
        st.warning(f"⚠️ Failed to calculate indicators: {e}")
        return None

    return df

last_trade_signal = None
last_news_headline = None

while True:
    df = fetch_data()

    if df is None:
        st.error("❌ Invalid ticker or no available data. Please try another symbol.")
        time.sleep(30)
        continue

    if df["MACD"].isna().all() or df["MACD_signal"].isna().all():
        st.warning("⚠️ Not enough data to calculate MACD at this interval.")
        time.sleep(60)
        continue

    with placeholder.container():
        st.subheader(f"Live price for {ticker} — Interval: {interval}")

        try:
            info = yf.Ticker(ticker).fast_info
            current = info["last_price"]
            previous = info["previous_close"]
            change = current - previous
            pct = (change / previous) * 100
            arrow = "🔺" if change > 0 else "🔻" if change < 0 else "⏸️"
            st.markdown(
                f"### {arrow} Real-Time Price: **${current:.2f}** ({pct:+.2f}%)  &nbsp;&nbsp; 🕒 Updated: {datetime.now().strftime('%I:%M:%S %p')}",
                unsafe_allow_html=True
            )
        except Exception as e:
            st.warning("⚠️ Could not fetch real-time price.")

        st.plotly_chart(plot_candlestick(df.tail(lookback)), use_container_width=True)
        st.line_chart(df[["Close", "RSI"]].tail(lookback))

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
            else:
                signal = "⚪ Hold"
                st.info("⚪ Hold — Indicators mixed or neutral.")

        for check in checks:
            st.write(check)

        # === Volatility Meter (simple) ===
        volatility = df["Close"].pct_change().tail(lookback).std() * 100
        if volatility > 1.5:
            vol_level = "🔴 High"
        elif volatility > 0.5:
            vol_level = "🟡 Medium"
        else:
            vol_level = "🟢 Low"

        # === Sidebar Summary (Pinned to top) ===
        st.sidebar.markdown("### 🧠 Trade Summary")
        st.sidebar.markdown(f"**Signal:** {signal}")
        st.sidebar.markdown(f"**Confidence:** {confidence}%")
        st.sidebar.markdown(f"**Volatility:** {vol_level}")
        st.sidebar.markdown("---")
        for check in checks:
            st.sidebar.markdown(check)

        # === News + Sentiment Section ===
        st.sidebar.markdown("### 📰 News + Sentiment")
        news = fetch_news(ticker)
        sentiment_total = 0
        count_pos = 0
        count_neg = 0
        count_neu = 0

        for article in news:
            if "Positive" in article["sentiment"]:
                count_pos += 1
            elif "Negative" in article["sentiment"]:
                count_neg += 1
            else:
                count_neu += 1
            sentiment_total += article["score"]

        st.sidebar.markdown(f"**Sentiment:** 🟢 {count_pos} | 🔴 {count_neg} | ⚪ {count_neu}")
        st.sidebar.markdown("---")

        for article in news:
            st.sidebar.markdown(
                f"**{article['sentiment']}** — {article['headline']}\n"
                f"🧠 *{article['summary']}*\n"
                f"📣 _Source: {article['source']}_"
            )
            st.sidebar.markdown("---")

        # === Discord Alert for News Signal ===
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
