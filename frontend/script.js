// Interval mapping for TradingView
function convertInterval(interval) {
  const map = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "1d": "D"
  };
  return map[interval] || "1";
}

function formatTimeAgo(timestamp) {
  const then = new Date(timestamp);
  const now = new Date();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  return then.toLocaleString();
}

function loadTradingViewWidget(ticker, interval) {
  document.getElementById("tvchart").innerHTML = ""; // Clear previous chart

  new TradingView.widget({
    autosize: true,
    symbol: `NASDAQ:${ticker}`,
    interval: convertInterval(interval),
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    toolbar_bg: "#111",
    enable_publishing: false,
    hide_top_toolbar: false,
    hide_legend: false,
    container_id: "tvchart"
  });
}

// Load TradingView script
if (!window.TradingView) {
  const script = document.createElement("script");
  script.src = "https://s3.tradingview.com/tv.js";
  script.onload = () => {
    console.log("TradingView loaded");
    initializeTradingView();
  };
  document.head.appendChild(script);
}

function initializeTradingView() {
  new TradingView.widget({
    autosize: true,
    symbol: "NASDAQ:AAPL", // Default symbol
    interval: "1",
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    toolbar_bg: "#111",
    enable_publishing: false,
    hide_top_toolbar: false,
    hide_legend: false,
    container_id: "tvchart",
    studies: [
      "RSI@tv-basicstudies",
      "MACD@tv-basicstudies"
    ],
    save_image: false,
    overrides: {
      "mainSeriesProperties.candleStyle.upColor": "#00c853",
      "mainSeriesProperties.candleStyle.downColor": "#d32f2f",
      "mainSeriesProperties.candleStyle.borderUpColor": "#00c853",
      "mainSeriesProperties.candleStyle.borderDownColor": "#d32f2f",
      "mainSeriesProperties.candleStyle.wickUpColor": "#00c853",
      "mainSeriesProperties.candleStyle.wickDownColor": "#d32f2f"
    }
  });
}

// Listen for symbol changes from TradingView
window.addEventListener('message', async (event) => {
  if (event.data.type === 'symbolChange') {
    const ticker = event.data.symbol.split(':')[1];
    await fetchSignal(ticker);
  }
});

async function fetchSignal(ticker) {
  if (!ticker) return;

  try {
    const res = await fetch(`/run?ticker=${ticker}`);
    if (!res.ok) throw new Error("Ticker not found or backend error");

    const data = await res.json();

    document.getElementById("error").innerText = "";
    document.getElementById("confidence").innerText = `${data.confidence}%`;
    document.getElementById("price").innerText = `$${data.price}`;
    document.getElementById("timestamp").innerText = formatTimeAgo(data.timestamp);
    document.getElementById("entrySignal").innerText = data.entry_signal || "N/A";
    document.getElementById("patternStack").innerText = data.pattern_stack?.join(", ") || "None";

    const signalSpan = document.getElementById("signal");
    signalSpan.className = "badge";
    if (data.signal === "BUY") {
      signalSpan.textContent = "🟢 BUY";
      signalSpan.classList.add("buy");
    } else if (data.signal === "SELL") {
      signalSpan.textContent = "🔴 SELL";
      signalSpan.classList.add("sell");
    } else {
      signalSpan.textContent = "⚪️ WAIT";
      signalSpan.classList.add("wait");
    }

    const logicList = document.getElementById("logicList");
    logicList.innerHTML = "";
    (data.logic || []).forEach(item => {
      const li = document.createElement("li");
      li.textContent = item;
      logicList.appendChild(li);
    });

    // --- Candlestick patterns display ---
    const patternStack = document.getElementById("patternStack");
    let patternText = data.pattern_stack?.join(", ") || "None";
    if (data.candlestick_patterns && data.candlestick_patterns.length > 0) {
      patternText += "\n";
      data.candlestick_patterns.slice(-5).forEach(pat => {
        const color = pat.direction === "bullish" ? "#00c853" : pat.direction === "bearish" ? "#d32f2f" : "#aaa";
        patternText += `\n%c${pat.name} [${pat.direction}]\nEntry: ${pat.entry}  SL: ${pat.stop_loss}  TP: ${pat.take_profit}`;
      });
      // For UI, render as HTML
      patternStack.innerHTML = data.candlestick_patterns.slice(-5).map(pat => {
        const color = pat.direction === "bullish" ? "#00c853" : pat.direction === "bearish" ? "#d32f2f" : "#aaa";
        return `<div style="margin:8px 0;padding:8px 12px;border-radius:8px;background:#18181f;color:${color};font-weight:600;">
          ${pat.name} <span style="font-size:0.95em;font-weight:400;">[${pat.direction}]</span><br>
          <span style="font-size:0.95em;font-weight:400;color:#fff;">Entry: <b>${pat.entry}</b>  SL: <b>${pat.stop_loss}</b>  TP: <b>${pat.take_profit}</b></span>
        </div>`;
      }).join("");
    } else {
      patternStack.innerText = patternText;
    }

  } catch (err) {
    console.error("Error fetching signal:", err);
    document.getElementById("error").innerText = err.message;
  }
}

// --- Ticker input logic ---
const tickerInput = document.getElementById("tickerInput");
const loadBtn = document.getElementById("loadBtn");
let currentTicker = "AAPL";

function updateChartAndSignals(ticker) {
  currentTicker = ticker.toUpperCase().trim();
  if (!currentTicker) return;
  // Update TradingView chart
  document.getElementById("tvchart").innerHTML = "";
  new TradingView.widget({
    autosize: true,
    symbol: `NASDAQ:${currentTicker}`,
    interval: "1",
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    toolbar_bg: "#111",
    enable_publishing: false,
    hide_top_toolbar: false,
    hide_legend: false,
    container_id: "tvchart"
  });
  // Fetch backend signals
  fetchSignal(currentTicker);
}

// Always pass ticker string, not event object
loadBtn.addEventListener("click", () => updateChartAndSignals(tickerInput.value));
tickerInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    updateChartAndSignals(tickerInput.value);
  }
});

const tickerForm = document.getElementById("tickerForm");
tickerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  updateChartAndSignals(tickerInput.value);
});

// On page load, show default ticker
window.addEventListener('DOMContentLoaded', function() {
  tickerInput.value = currentTicker;
  updateChartAndSignals(currentTicker);
});