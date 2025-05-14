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

    document.getElementById("confidence").innerText = data.confidence + "%";
    document.getElementById("price").innerText = `$${data.price}`;
    document.getElementById("updated").innerText = "Just now";
    document.getElementById("entrySignal").innerText = data.entry_signal || "N/A";
    document.getElementById("patternStack").innerText = data.pattern_stack || "None";

    // Logic list
    const logicList = document.getElementById("logicList");
    logicList.innerHTML = "";
    (data.logic || []).forEach(item => {
      const li = document.createElement("li");
      li.textContent = item;
      logicList.appendChild(li);
    });

    // Convert time to Unix timestamp (milliseconds)
    const candles = data.candles.map(d => ({
      x: new Date(d.t).getTime(),
      o: d.o,
      h: d.h,
      l: d.l,
      c: d.c
    }));

    // Debug log
    console.log("Final candles:", candles);
    console.log("Sample candle:", candles[0]);

    if (chart) chart.destroy();

    const ctx = document.getElementById("chart").getContext("2d");
    chart = new Chart(ctx, {
      type: 'candlestick',
      data: {
        datasets: [{
          label: `${ticker} Candlestick`,
          data: candles
        }]
      },
      options: {
        responsive: true,
        plugins: {
            legend: { display: false },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                label: context => {
                    const o = context.raw.o;
                    const h = context.raw.h;
                    const l = context.raw.l;
                    const c = context.raw.c;
                    return `O: ${o}  H: ${h}  L: ${l}  C: ${c}`;
                },
                title: (ctx) => {
                    try {
                    const ts = ctx[0].parsed.x;
                    return luxon.DateTime.fromMillis(ts).toFormat("MMM dd yyyy HH:mm");
                    } catch (e) {
                    console.warn("Tooltip timestamp parse fail:", e);
                    return "Unknown Time";
                    }
                }
                }
            }
        },
        scales: {
          x: {
            type: 'time',
            time: {
              parser: 'x',
              tooltipFormat: 'MMM dd, yyyy HH:mm'
            },
            adapters: {
              date: {
                zone: 'local',
              }
            },
            ticks: {
              source: 'auto'
            }
          },
          y: {
            beginAtZero: false
          }
        }
      }
    });

  } catch (err) {
    console.error(err);
    document.getElementById("error").innerText = err.message;
  }
}
