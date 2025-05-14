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
    document.getElementById("error").innerText = "";
    document.getElementById("ticker").innerText = data.ticker;

    const signalSpan = document.getElementById("signal");
    signalSpan.className = "badge";
    signalSpan.textContent = data.signal === "BUY" ? "🟢 BUY"
                         : data.signal === "SELL" ? "🔴 SELL"
                         : "🟡 HOLD";
    signalSpan.classList.add(data.signal.toLowerCase());

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

    document.getElementById("entry_signal").innerText = data.entry_signal || "N/A";
    document.getElementById("pattern_stack").innerText = data.pattern_stack?.join(", ") || "None";

    const candles = data.history
      .filter(d =>
        typeof d.t === "string" &&
        typeof d.o === "number" &&
        typeof d.h === "number" &&
        typeof d.l === "number" &&
        typeof d.c === "number"
      )
      .map(d => ({
        x: new Date(d.t).toISOString(),
        o: d.o,
        h: d.h,
        l: d.l,
        c: d.c
      }));

    if (candles.length === 0) throw new Error("No valid candle data");

    const ctx = document.getElementById("priceChart").getContext("2d");
    if (chart) chart.destroy();

    chart = new Chart(ctx, {
      type: 'candlestick',
      data: {
        datasets: [{
          label: `${data.ticker} Candles`,
          data: candles,
          color: {
            up: '#26a69a',
            down: '#ef5350',
            unchanged: '#999'
          }
        }]
      },
      options: {
        scales: {
          x: {
            type: 'time',
            time: {
              tooltipFormat: 'hh:mm a',
              displayFormats: {
                hour: 'hh:mm a',
                minute: 'hh:mm a'
              }
            },
            ticks: {
              source: 'auto',
              autoSkip: true
            }
          },
          y: {
            beginAtZero: false
          }
        },
        plugins: {
          legend: {
            display: false
          }
        }
      }
    });

  } catch (err) {
    console.error("❌ Error rendering chart:", err);
    document.getElementById("error").innerText = err.message;
    ["ticker", "signal", "confidence", "price", "timestamp", "entry_signal", "pattern_stack"].forEach(id => {
      document.getElementById(id).innerText = "";
    });
    document.getElementById("logic").innerHTML = "";
    if (chart) chart.destroy();
  }
}

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
