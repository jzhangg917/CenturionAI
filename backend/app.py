"""
Flask web application for serving trading signals and frontend.
"""

from flask import Flask, request, jsonify, send_from_directory # type: ignore
from backend_utils import fetch_data, analyze, save_outputs
import os
import requests # type: ignore
from datetime import datetime
from dotenv import load_dotenv # type: ignore
import pandas as pd

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

@app.route("/logo")
def get_logo():
    """
    Get company logo URL for a given ticker from Yahoo Finance.
    
    Returns:
        JSON response with logo_url or error message
    """
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "Missing ticker"}), 400
    try:
        yahoo_url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}"
        res = requests.get(yahoo_url, timeout=3).json()
        for q in res.get("quotes", []):
            if q.get("symbol", "").upper() == ticker:
                return jsonify({"logo_url": q.get("logo_url")})
        return jsonify({"logo_url": None})
    except:
        return jsonify({"logo_url": None})

@app.route("/")
def index():
    """
    Serve the main index.html file.
    """
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:filename>")
def frontend_files(filename):
    """
    Serve frontend static files.
    """
    return send_from_directory(app.static_folder, filename)

@app.route("/data/<path:filename>")
def data_files(filename):
    """
    Serve data files from the data directory.
    """
    return send_from_directory(os.path.join(app.static_folder, "data"), filename)

@app.route("/run")
def run_signal():
    """
    Generate and return trading signals for a given ticker.
    
    Returns:
        JSON response with trading signals and price history
    """
    ticker = request.args.get("ticker", "").upper()
    interval = request.args.get("interval", "1m")
    df = fetch_data(ticker, interval)
    if df is None or df.empty:
        return jsonify({"error": "No data"}), 404

    sig = analyze(df, ticker)
    if not sig:
        return jsonify({"error": "Analysis failed"}), 500

    df_tail = df.dropna().tail(60)
    sig["history"] = [
        {
            "t": i.strftime('%Y-%m-%dT%H:%M:%SZ') if isinstance(i, datetime) else str(i),
            "o": round(r["Open"], 2),
            "h": round(r["High"], 2),
            "l": round(r["Low"], 2),
            "c": round(r["Close"], 2)
        } for i, r in df_tail.iterrows()
    ]
    return jsonify(sig)

@app.route("/news")
def get_news():
    """
    Fetch latest news for a given ticker using Finnhub API.
    Returns JSON list of news articles (headline, summary, url, datetime, source, image)
    """
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "Missing ticker"}), 400
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return jsonify({"error": "Missing Finnhub API key"}), 500
    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2023-01-01&to=2025-12-31&token={api_key}"
        res = requests.get(url, timeout=5)
        news = res.json()
        # Only keep relevant fields and limit to 10 articles
        articles = [
            {
                "headline": n.get("headline"),
                "summary": n.get("summary"),
                "url": n.get("url"),
                "datetime": n.get("datetime"),
                "source": n.get("source"),
                "image": n.get("image")
            }
            for n in news[:10]
        ]
        return jsonify(articles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backtest")
def backtest():
    """
    Run backtest for a given ticker, interval, and date range.
    Returns JSON with list of signals and performance metrics.
    """
    ticker = request.args.get("ticker", "").upper()
    interval = request.args.get("interval", "1d")
    start = request.args.get("start")
    end = request.args.get("end")
    if not ticker or not start or not end:
        return jsonify({"error": "Missing ticker, start, or end"}), 400

    # Fetch historical data for the range
    df = fetch_data(ticker, interval)
    if df is None or df.empty:
        return jsonify({"error": "No data"}), 404
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    if df.index.tz is not None:
        if start_dt.tzinfo is None:
            start_dt = start_dt.tz_localize('UTC')
        else:
            start_dt = start_dt.tz_convert('UTC')
        if end_dt.tzinfo is None:
            end_dt = end_dt.tz_localize('UTC')
        else:
            end_dt = end_dt.tz_convert('UTC')
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
    if df.empty:
        return jsonify({"error": "No data in range"}), 404

    signals = []
    last_signal = None
    returns = []
    entry_price = None
    for i in range(1, len(df)):
        sub_df = df.iloc[:i+1]
        result = analyze(sub_df, ticker)
        if not result:
            continue
        signal = result["signal"]
        price = sub_df["Close"].iloc[-1]
        ts = sub_df.index[-1].strftime("%Y-%m-%d %H:%M:%S")
        if signal != last_signal and signal in ["BUY", "SELL"]:
            signals.append({"timestamp": ts, "signal": signal, "price": price})
            if last_signal == "BUY" and signal == "SELL" and entry_price is not None:
                returns.append((price - entry_price) / entry_price)
                entry_price = None
            elif signal == "BUY":
                entry_price = price
            last_signal = signal

    win_trades = [r for r in returns if r > 0]
    loss_trades = [r for r in returns if r <= 0]
    win_rate = round(100 * len(win_trades) / len(returns), 2) if returns else 0
    avg_return = round(100 * sum(returns) / len(returns), 2) if returns else 0
    max_drawdown = round(100 * (min(returns) if returns else 0), 2)

    metrics = {
        "total_trades": len(returns),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "max_drawdown": max_drawdown
    }
    return jsonify({"signals": signals, "metrics": metrics})

if __name__ == "__main__":
    app.run(debug=True, port=3000)
