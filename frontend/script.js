// frontend/script.js
fetch("signal.json")
  .then(response => response.json())
  .then(data => {
    document.getElementById("ticker").innerText = data.ticker;
    document.getElementById("signal").innerText = data.signal;
    document.getElementById("confidence").innerText = data.confidence;
    document.getElementById("price").innerText = data.price;
    document.getElementById("timestamp").innerText = new Date(data.timestamp).toLocaleString();
    document.getElementById("logic").innerText = data.logic.join(", ");
  })
  .catch(error => {
    document.getElementById("signal-box").innerHTML = "<p>Error loading signal.</p>";
  });