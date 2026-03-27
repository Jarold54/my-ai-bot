<!DOCTYPE html>
<html>
<head>
  <title>My AI Bot</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial; background: #1a1a2e; color: white; height: 100vh; display: flex; flex-direction: column; }
    header { background: #16213e; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
    h2 { color: #00d4ff; }
    #correction-count { background: #e94560; padding: 5px 12px; border-radius: 20px; font-size: 13px; }
    #chatbox { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
    .user-msg { background: #0f3460; padding: 12px 16px; border-radius: 12px; align-self: flex-end; max-width: 70%; }
    .bot-msg { background: #16213e; padding: 12px 16px; border-radius: 12px; align-self: flex-start; max-width: 80%; border: 1px solid #00d4ff33; }
    .searched-tag { font-size: 11px; color: #00d4ff; margin-bottom: 6px; }
    .graph-container { width: 100%; margin-top: 10px; border-radius: 10px; overflow: hidden; }
    .correct-btn { background: none; border: 1px solid #666; color: #aaa; padding: 4px 10px; border-radius: 8px; cursor: pointer; font-size: 12px; margin-top: 8px; }
    .correct-btn:hover { border-color: #e94560; color: #e94560; }
    #input-area { background: #16213e; padding: 15px 20px; display: flex; gap: 10px; }
    #input { flex: 1; background: #0f3460; border: 1px solid #00d4ff44; color: white; padding: 12px; border-radius: 10px; font-size: 15px; }
    #send { background: #00d4ff; color: #1a1a2e; border: none; padding: 12px 24px; border-radius: 10px; cursor: pointer; font-weight: bold; }
    pre { background: #0d0d0d; padding: 10px; border-radius: 8px; overflow-x: auto; margin-top: 8px; font-size: 13px; }
    .agent-tag { font-size: 11px; color: #00ff88; margin-bottom: 6px; }
  </style>
</head>
<body>
  <header>
    <h2>🤖 My AI Bot</h2>
    <span id="correction-count">0 corrections learned</span>
  </header>
  <div id="chatbox"></div>
  <div id="input-area">
    <input id="input" type="text" placeholder="Chat, code, search, or ask for a graph..." />
    <button id="send" onclick="sendMessage()">Send</button>
  </div>

  <script>
    let correctionCount = 0;
    let graphCount = 0;

    async function sendMessage() {
      const input = document.getElementById("input");
      const chatbox = document.getElementById("chatbox");
      const message = input.value.trim();
      if (!message) return;

      chatbox.innerHTML += `<div class="user-msg">${message}</div>`;
      input.value = "";
      chatbox.innerHTML += `<div class="bot-msg" id="thinking">⏳ Thinking...</div>`;
      chatbox.scrollTop = chatbox.scrollHeight;

      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await res.json();
      const thinking = document.getElementById("thinking");
      thinking.removeAttribute("id");

      let html = "";
      if (data.searched) html += `<div class="searched-tag">🌐 Web searched</div>`;
      if (data.graph) html += `<div class="agent-tag">📊 Data Analysis Agent</div>`;
      html += data.reply.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre>$2</pre>');

      if (data.graph) {
        graphCount++;
        html += `<div class="graph-container" id="graph-${graphCount}"></div>`;
      }

      html += `<br><button class="correct-btn" onclick="correctThis(this)">✏️ Correct this</button>`;
      thinking.innerHTML = html;

      if (data.graph) {
        const graphData = JSON.parse(data.graph);
        Plotly.newPlot(`graph-${graphCount}`, graphData.data, graphData.layout, {responsive: true});
      }

      chatbox.scrollTop = chatbox.scrollHeight;
    }

    async function correctThis(btn) {
      const correction = prompt("What was wrong with this response?");
      if (!correction) return;

      await fetch("/correct", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correction })
      });

      correctionCount++;
      document.getElementById("correction-count").textContent = `${correctionCount} corrections learned`;
      btn.textContent = "✅ Correction saved";
      btn.disabled = true;
    }

    document.getElementById("input").addEventListener("keypress", e => {
      if (e.key === "Enter") sendMessage();
    });
  </script>
</body>
</html>
