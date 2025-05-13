# 🧠 NeuroTraderAI

**NeuroTraderAI** is an intelligent trading signal bot that mimics how an elite Wall Street trader might analyze markets. It combines real-time stock data, technical indicators, and pattern recognition to generate actionable BUY/SELL/HOLD alerts — with a simple web interface and Discord/console output.

---

## 🚀 Features

- 📈 Real-time stock data via `yfinance`
- 🧠 Technical indicator analysis (`pandas-ta`, RSI, MACD, EMA, candlestick patterns)
- 🔁 Dynamic ticker input (no hardcoding)
- 💬 Signal output includes:
  - Trade signal (🟢 BUY / 🔴 SELL / 🟡 HOLD)
  - Confidence score
  - Detected logic patterns
  - Price + timestamp
- 🖥️ Clean HTML/JS dashboard for easy viewing
- ⚡ Fast backend via Flask API
- 📤 Discord alert integration (optional)

---

## 📁 Project Structure

NeuroTraderAI/
├── backend/
│ ├── app.py # Flask API server
│ ├── bot.py # Core trading logic
│ ├── backend_utils.py # Indicator + save helpers
│ └── *.json / *.csv # Generated signal/log files
│
├── frontend/
│ ├── index.html # Web dashboard UI
│ ├── script.js # JS to fetch and render signals
│ └── data/ # Stores ticker JSON/CSV for frontend
│
└── requirements.txt # Python dependencies


---

## ⚙️ How It Works

1. **User enters a ticker** on the frontend (e.g. `AAPL`)
2. JS calls `http://localhost:3000/run?ticker=AAPL`
3. Flask backend:
   - Downloads stock data
   - Runs indicators + pattern detection
   - Saves signal as `frontend/data/AAPL_signal.json`
4. JS fetches the signal file and renders it in the UI

---

## 🧪 Local Setup

### 1. Clone and Install
```bash
git clone https://github.com/yourname/NeuroTraderAI.git
cd NeuroTraderAI
pip install -r requirements.txt

cd backend
python app.py

python3 -m http.server 1300

http://localhost:1300/frontend/index.html
