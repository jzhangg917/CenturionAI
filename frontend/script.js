document.getElementById("loadBtn").addEventListener("click", fetchSignal);
document.getElementById("tickerInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") fetchSignal();
});

function fetchSignal() {
  const ticker = document.getElementById("tickerInput").value.toUpperCase().trim();
  if (!ticker) return;

  fetch(`/run?ticker=${ticker}`)
    .then(res => {
      if (!res.ok) throw new Error("Ticker not found or backend error");
      return res.json();
    })
    .then(data => {
      document.getElementById("error").innerText = "";

      document.getElementById("ticker").innerText = data.ticker;

      const signalSpan = document.getElementById("signal");
      signalSpan.className = "badge";
      if (data.signal === "BUY") {
        signalSpan.textContent = "🟢 BUY";
        signalSpan.classList.add("buy");
      } else if (data.signal === "SELL") {
        signalSpan.textContent = "🔴 SELL";
        signalSpan.classList.add("sell");
      } else {
        signalSpan.textContent = "🟡 HOLD";
        signalSpan.classList.add("hold");
      }

      document.getElementById("confidence").innerText = `${data.confidence}%`;
      document.getElementById("price").innerText = `$${data.price}`;
      document.getElementById("timestamp").setAttribute("data-time", data.timestamp);
      document.getElementById("timestamp").innerText = formatTimeAgo(data.timestamp);

      const logicList = document.getElementById("logic");
      logicList.innerHTML = "";
      data.logic.forEach(rule => {
        const li = document.createElement("li");
        li.textContent = rule;
        logicList.appendChild(li);
      });
    })
    .catch(err => {
      console.error("Backend error", err);
      document.getElementById("error").innerText = err.message;

      ["ticker", "signal", "confidence", "price", "timestamp"].forEach(id => {
        document.getElementById(id).innerText = "";
      });
      document.getElementById("logic").innerHTML = "";
    });
}

// Live-updating timestamp
setInterval(() => {
  const el = document.getElementById("timestamp");
  const ts = el.getAttribute("data-time");
  if (ts) el.innerText = formatTimeAgo(ts);
}, 60000);

function formatTimeAgo(timestamp) {
  const then = new Date(timestamp);
  const now = new Date();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  return then.toLocaleString();
}
