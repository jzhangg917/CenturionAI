from flask import Flask, request, jsonify # type: ignore
import os, json
from backend_utils import fetch_data, analyze, save_outputs  # type: ignore
# seperate logic into different files

app = Flask(__name__)

@app.route("/run")
def run_signal():
    ticker = request.args.get("ticker", "").upper().strip()

    if not ticker:
        return jsonify({"error": "Missing ticker"}), 400

    df = fetch_data(ticker)
    if df is None or df.empty:
        return jsonify({"error": f"No data found for {ticker}"}), 404

    sig = analyze(df, ticker)
    if not sig:
        return jsonify({"error": "Failed to compute indicators"}), 500

    save_outputs(ticker, sig)
    return jsonify({"message": f"{ticker} signal generated", "data": sig})
    
if __name__ == "__main__":
    app.run(debug=True, port=3000)
