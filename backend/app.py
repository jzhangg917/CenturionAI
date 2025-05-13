from flask import Flask, request, jsonify, send_from_directory # type: ignore
from backend_utils import fetch_data, analyze, save_outputs
import os

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

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

    return jsonify(sig)


if __name__ == "__main__":
    app.run(debug=True, port=3000)
