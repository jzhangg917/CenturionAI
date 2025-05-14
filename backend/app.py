from flask import Flask, request, jsonify, send_from_directory # type: ignore
from backend_utils import fetch_data, analyze, save_outputs
import os
import requests # type: ignore

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

@app.route("/logo")
def get_logo():
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "Missing ticker"}), 400

    try:
        yahoo_url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}"
        res = requests.get(yahoo_url, timeout=3)
        data = res.json()

        quotes = data.get("quotes", [])
        for q in quotes:
            if q.get("symbol", "").upper() == ticker:
                logo_url = q.get("logo_url")
                return jsonify({"logo_url": logo_url if logo_url else None})

        return jsonify({"logo_url": None})  # fallback if no match
    except Exception as e:
        print("LOGO FETCH ERROR:", e)
        return jsonify({"logo_url": None})  # return null, not 500

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/data/<path:filename>")
def data_files(filename):
    return send_from_directory(os.path.join(app.static_folder, "data"), filename)

@app.route("/run")
def run_signal():
    ticker = request.args.get("ticker", "").upper()

    df = fetch_data(ticker)
    if df is None or df.empty:
        return jsonify({"error": f"{ticker} not found or has no data"}), 404

    sig = analyze(df, ticker)
    if not sig:
        return jsonify({"error": "Failed to compute indicators"}), 500

    # Add history (last 60 closing prices)
    sig["history"] = df["Close"].dropna().tail(60).round(2).tolist()

    return jsonify(sig)



if __name__ == "__main__":
    app.run(debug=True, port=3000)
