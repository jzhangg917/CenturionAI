# backend/bot.py

import sys
import json
from backend_utils import fetch_data, analyze

def run_for_ticker(ticker):
    df = fetch_data(ticker)
    if df is None:
        print(f"❌ No data for {ticker}")
        return
    sig = analyze(df, ticker)
    if sig:
        print(json.dumps(sig, indent=2))
    else:
        print(f"⚠️ Could not generate signal for {ticker}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bot.py TICKER1 [TICKER2 ...]")
        sys.exit(1)

    for ticker in sys.argv[1:]:
        run_for_ticker(ticker.upper())
