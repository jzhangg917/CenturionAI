document.getElementById("loadBtn").addEventListener("click", fetchSignal);
document.getElementById("tickerInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") fetchSignal();
});

let chart = null;

async function fetchSignal() {
    const ticker = document.getElementById("tickerInput").value.toUpperCase().trim();
    if (!ticker) return;
  
    try {
      const res = await fetch(`/run?ticker=${ticker}`);
      if (!res.ok) throw new Error("Ticker not found or backend error");
  
      const data = await res.json();
  
      // Clear errors
      document.getElementById("error").innerText = "";
  
      // Display signal details
      document.getElementById("ticker").innerText = data.ticker;
  
      const signalSpan = document.getElementById("signal");
      signalSpan.className = "badge"; // reset classes
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
  
      // Logic bullets
      const logicList = document.getElementById("logic");
      logicList.innerHTML = "";
      data.logic.forEach(rule => {
        const li = document.createElement("li");
        li.textContent = rule;
        logicList.appendChild(li);
      });
  
      // Entry Signal & Pattern Stack
      document.getElementById("entry_signal").innerText = data.entry_signal || "N/A";
      document.getElementById("pattern_stack").innerText = data.pattern_stack?.join(", ") || "None";
  
      // Company logo
      fetchLogo(ticker);
  
      // Chart rendering
      if (data.history && Array.isArray(data.history)) {
        const ctx = document.getElementById("priceChart").getContext("2d");
        const labels = data.history.map((_, i) => `T-${data.history.length - i}`);
        const prices = data.history;
  
        if (chart) chart.destroy();
  
        chart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [{
              label: `${ticker} Price`,
              data: prices,
              borderColor: '#00b894',
              backgroundColor: 'rgba(0,184,148,0.1)',
              tension: 0.3,
            }]
          },
          options: {
            scales: {
              x: { display: false },
              y: { beginAtZero: false }
            },
            plugins: {
              legend: {
                display: false
              }
            }
          }
        });
      }
  
    } catch (err) {
      console.error("Backend error", err);
      document.getElementById("error").innerText = err.message;
  
      ["ticker", "signal", "confidence", "price", "timestamp", "entry_signal", "pattern_stack"].forEach(id => {
        document.getElementById(id).innerText = "";
      });
  
      document.getElementById("logic").innerHTML = "";
      document.getElementById("logo").style.display = "none";
      if (chart) chart.destroy();
    }
  }  

// ✅ Live-updating timestamp
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

async function fetchLogo(ticker) {
    const logo = document.getElementById("logo");
    logo.style.display = "none";
  
    try {
      const res = await fetch(`/logo?ticker=${ticker}`);
      const data = await res.json();
      if (data.logo_url) {
        logo.src = data.logo_url;
        logo.style.display = "inline-block";
      }
    } catch (err) {
      console.warn("Logo fetch failed", err);
    }
  }  