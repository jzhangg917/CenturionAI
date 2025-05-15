let currentInterval = "1m";

// Event listeners
document.getElementById("loadBtn").addEventListener("click", fetchSignal);
document.getElementById("intervalSelector").addEventListener("change", fetchSignal);
document.getElementById("tickerInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") fetchSignal();
});

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

async function fetchSignal() {
  const ticker = document.getElementById("tickerInput").value.toUpperCase().trim();
  currentInterval = document.getElementById("intervalSelector").value;
  if (!ticker) return;

  try {
    const res = await fetch(`/run?ticker=${ticker}&interval=${currentInterval}`);
    if (!res.ok) throw new Error("Ticker not found or backend error");

    const data = await res.json();

    document.getElementById("error").innerText = "";
    document.getElementById("ticker").innerText = data.ticker;
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

    loadTradingViewWidget(ticker, currentInterval);

  } catch (err) {
    console.error("Chart rendering failed:", err);
    document.getElementById("error").innerText = err.message;
  }
}

// Load TradingView script once
if (!window.TradingView) {
  const script = document.createElement("script");
  script.src = "https://s3.tradingview.com/tv.js";
  script.onload = () => console.log("TradingView loaded");
  document.head.appendChild(script);
}
