from flask import Flask, request, jsonify, send_from_directory # type: ignore
from backend_utils import fetch_data, analyze, save_outputs # type: ignore
import os

app = Flask(__name__)

# Serve frontend files (HTML, JS, CSS, etc.)
@app.route("/frontend/<path:filename>")
def serve_frontend(filename):
    return send_from_directory("../frontend", filename)

# Run the bot for a given ticker and return signal data
@app.route("/run")
def run_signal():
    ticker = request.args.get("ticker", "").upper()
    
    df = fetch_data(ticker)
    if df is None or df.empty:
        return jsonify({"error": f"{ticker} not found or has no data"}), 404

    sig = analyze(df, ticker)
    if not sig:
        return jsonify({"error": "Failed to compute indicators"}), 500

    save_outputs(ticker, sig)
    return jsonify({"message": f"{ticker} signal generated", "data": sig})

if __name__ == "__main__":
    app.run(debug=True, port=3000)
