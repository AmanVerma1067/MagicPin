def get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vera Engine — magicpin Merchant Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .chat-bubble-vera { background-color: #e2f7cb; border-radius: 12px 12px 0 12px; }
    .chat-bubble-merchant { background-color: #ffffff; border-radius: 12px 12px 12px 0; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
  <!-- Top Nav -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="h-9 w-9 rounded-lg bg-gradient-to-tr from-amber-500 to-rose-500 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-rose-500/20">V</div>
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            Vera Engine
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">v1.0.0</span>
          </h1>
          <p class="text-xs text-slate-400">magicpin Autonomous Merchant Assistant</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <a href="/docs" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition flex items-center gap-1.5 font-medium">
          <span>Swagger UI</span>
          <svg class="w-3.5 h-3.5 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
        <a href="https://github.com/AmanVerma1067/MaginPin" target="_blank" class="text-xs bg-rose-600 hover:bg-rose-500 text-white px-3 py-1.5 rounded-lg font-medium transition shadow-lg shadow-rose-600/20 flex items-center gap-1.5">
          <span>GitHub</span>
          <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>
        </a>
      </div>
    </div>
  </header>

  <!-- Main Grid -->
  <main class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <!-- Metrics Bar -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
        <span class="text-xs text-slate-400 font-medium">Liveness Status</span>
        <div class="text-xl font-bold text-emerald-400 mt-1 flex items-center gap-2">
          <span class="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span id="stat-status">OK</span>
        </div>
        <p class="text-[11px] text-slate-500 mt-1">Uptime: <span id="stat-uptime">0</span>s</p>
      </div>
      <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
        <span class="text-xs text-slate-400 font-medium">Categories</span>
        <div class="text-2xl font-bold text-white mt-1" id="stat-cat">0</div>
        <p class="text-[11px] text-slate-500 mt-1">Target: 5 verticals</p>
      </div>
      <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
        <span class="text-xs text-slate-400 font-medium">Merchants Loaded</span>
        <div class="text-2xl font-bold text-white mt-1" id="stat-merch">0</div>
        <p class="text-[11px] text-slate-500 mt-1">Target: 50 merchants</p>
      </div>
      <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
        <span class="text-xs text-slate-400 font-medium">Customers Loaded</span>
        <div class="text-2xl font-bold text-white mt-1" id="stat-cust">0</div>
        <p class="text-[11px] text-slate-500 mt-1">Target: 200 customers</p>
      </div>
      <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
        <span class="text-xs text-slate-400 font-medium">Active Triggers</span>
        <div class="text-2xl font-bold text-white mt-1" id="stat-trig">0</div>
        <p class="text-[11px] text-slate-500 mt-1">Target: 100 triggers</p>
      </div>
    </div>

    <!-- Seed Dataset Button -->
    <div class="bg-gradient-to-r from-slate-800 to-slate-800/60 p-4 rounded-xl border border-slate-700 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 class="font-semibold text-white">Local Testing Context Store</h3>
        <p class="text-xs text-slate-400">Preload the expanded 4-context challenge dataset (5 categories, 50 merchants, 200 customers, 100 triggers) into the in-memory store.</p>
      </div>
      <button onclick="loadSeedData()" id="btn-load-seed" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition shadow-lg shadow-indigo-600/20 flex items-center gap-2">
        <span>Load Expanded Dataset</span>
      </button>
    </div>

    <!-- 2-Column Workflow: Proactive Outreach vs Interactive Chat -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Left: Proactive Tick Composer -->
      <div class="bg-slate-800/40 rounded-xl border border-slate-800 flex flex-col h-[600px] overflow-hidden">
        <div class="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <h2 class="font-bold text-white text-sm">Proactive Outreach Simulator</h2>
            <p class="text-xs text-slate-400">Trigger /v1/tick to rank signals and compose WhatsApp outreach</p>
          </div>
          <button onclick="triggerTick()" id="btn-tick" class="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-rose-600/20 transition">
            Run /v1/tick
          </button>
        </div>
        <div id="tick-results" class="p-4 flex-1 overflow-y-auto space-y-4">
          <div class="text-center py-20 text-slate-500 text-sm">
            Click <strong>Run /v1/tick</strong> to simulate a clock tick and evaluate proactive opportunities.
          </div>
        </div>
      </div>

      <!-- Right: Conversational FSM Chat -->
      <div class="bg-slate-800/40 rounded-xl border border-slate-800 flex flex-col h-[600px] overflow-hidden">
        <div class="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <h2 class="font-bold text-white text-sm">Conversational FSM Simulator</h2>
            <p class="text-xs text-slate-400">Test /v1/reply (auto-reply defense, affirmative action, opt-outs)</p>
          </div>
          <span class="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">/v1/reply</span>
        </div>

        <!-- Chat Log -->
        <div id="chat-box" class="p-4 flex-1 overflow-y-auto space-y-3 bg-slate-950/40 font-sans">
          <!-- Initial bot message -->
          <div class="flex flex-col items-start space-y-1">
            <span class="text-[10px] text-slate-500 font-medium">Vera (Outbound Message)</span>
            <div class="max-w-[85%] chat-bubble-vera p-3 text-slate-900 text-xs shadow-sm">
              Dr. Meera, your listing reached 2,410 views in Lajpat Nagar with calls at 18. Shall we launch your Dental Cleaning @ ₹299 to maintain patient momentum?
            </div>
          </div>
        </div>

        <!-- Canned Quick Replies -->
        <div class="px-4 py-2 border-t border-slate-800/80 bg-slate-900/40 flex flex-wrap gap-1.5">
          <button onclick="sendQuickReply('Ok lets do it. Whats next?')" class="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded border border-slate-700 transition">
            "Ok lets do it. Whats next?" (Affirmative)
          </button>
          <button onclick="sendQuickReply('Thank you for contacting us! Our team will respond shortly.')" class="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded border border-slate-700 transition">
            Auto-Reply Canned (Defense)
          </button>
          <button onclick="sendQuickReply('Stop messaging me. This is useless spam.')" class="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded border border-slate-700 transition">
            "Stop messaging me" (Opt-out)
          </button>
        </div>

        <!-- Message Input -->
        <div class="p-3 border-t border-slate-800 bg-slate-900/60 flex items-center gap-2">
          <input type="text" id="chat-input" placeholder="Type a simulated merchant reply..." class="flex-1 bg-slate-950 border border-slate-700 text-xs text-white rounded-lg px-3 py-2 outline-none focus:border-rose-500 transition" onkeydown="if(event.key==='Enter') sendCustomReply()">
          <button onclick="sendCustomReply()" class="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg shadow-md transition">Send</button>
        </div>
      </div>
    </div>
  </main>

  <script>
    async function updateHealth() {
      try {
        const res = await fetch('/v1/healthz');
        const data = await res.json();
        document.getElementById('stat-status').innerText = data.status.toUpperCase();
        document.getElementById('stat-uptime').innerText = Math.round(data.uptime_seconds);
        if (data.contexts_loaded) {
          document.getElementById('stat-cat').innerText = data.contexts_loaded.category || 0;
          document.getElementById('stat-merch').innerText = data.contexts_loaded.merchant || 0;
          document.getElementById('stat-cust').innerText = data.contexts_loaded.customer || 0;
          document.getElementById('stat-trig').innerText = data.contexts_loaded.trigger || 0;
        }
      } catch (e) {
        console.error("Health check error", e);
      }
    }

    async function loadSeedData() {
      const btn = document.getElementById('btn-load-seed');
      btn.innerText = "Loading...";
      btn.disabled = true;
      try {
        const res = await fetch('/v1/load-seed-dataset', { method: 'POST' });
        const data = await res.json();
        alert(`Loaded ${data.loaded_count} contexts into memory!`);
        updateHealth();
      } catch (e) {
        alert("Load failed: " + e);
      } finally {
        btn.innerText = "Load Expanded Dataset";
        btn.disabled = false;
      }
    }

    async function triggerTick() {
      const resultsDiv = document.getElementById('tick-results');
      resultsDiv.innerHTML = '<div class="text-center py-20 text-slate-400 text-sm">Evaluating candidates & composing messages...</div>';
      try {
        const res = await fetch('/v1/tick', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            now: new Date().toISOString(),
            available_triggers: ["trg_001_research_digest_dentists", "trg_004_perf_dip_bharat", "trg_010_ipl_match_delhi", "trg_018_supply_atorvastatin_recall"]
          })
        });
        const data = await res.json();
        if (!data.actions || data.actions.length === 0) {
          resultsDiv.innerHTML = '<div class="text-center py-20 text-slate-400 text-sm">No actions generated this tick (all candidates evaluated or suppressed).</div>';
          return;
        }

        resultsDiv.innerHTML = data.actions.map(a => `
          <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2 shadow-sm">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-rose-400 uppercase tracking-wider">${a.category}</span>
              <span class="text-[11px] font-mono text-slate-400">${a.merchant_id}</span>
            </div>
            <div class="chat-bubble-vera p-3 text-slate-900 text-xs font-normal leading-relaxed">
              ${a.body}
            </div>
            <div class="text-[11px] text-slate-400 flex items-center justify-between pt-1">
              <span><strong>CTA:</strong> ${a.cta}</span>
              <span class="text-slate-500 font-mono text-[10px]">${a.suppression_key || ''}</span>
            </div>
            <p class="text-[11px] text-slate-400 italic bg-slate-950/60 p-2 rounded border border-slate-800">
              💡 ${a.rationale}
            </p>
          </div>
        `).join('');
      } catch (e) {
        resultsDiv.innerHTML = '<div class="text-rose-400 text-xs p-4">Error: ' + e + '</div>';
      }
    }

    async function sendReplyToBot(message) {
      const chatBox = document.getElementById('chat-box');
      // Append merchant bubble
      chatBox.innerHTML += `
        <div class="flex flex-col items-end space-y-1">
          <span class="text-[10px] text-slate-500 font-medium">Merchant Reply</span>
          <div class="max-w-[85%] chat-bubble-merchant p-3 text-slate-900 text-xs shadow-sm">
            ${message}
          </div>
        </div>
      `;
      chatBox.scrollTop = chatBox.scrollHeight;

      try {
        const res = await fetch('/v1/reply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: "conv_ui_demo",
            merchant_id: "m_001_drmeera_dentist_delhi",
            from_role: "merchant",
            message: message,
            turn_number: 2
          })
        });
        const data = await res.json();
        let botContent = '';
        if (data.action === 'send') {
          botContent = `<div class="max-w-[85%] chat-bubble-vera p-3 text-slate-900 text-xs shadow-sm">${data.body}</div>`;
        } else if (data.action === 'wait') {
          botContent = `<div class="max-w-[85%] bg-amber-500/10 border border-amber-500/30 p-2.5 rounded text-amber-300 text-xs">⏸️ <strong>Auto-Reply Filtered (wait):</strong> Backing off ${data.wait_seconds}s for human owner.</div>`;
        } else if (data.action === 'end') {
          botContent = `<div class="max-w-[85%] bg-rose-500/10 border border-rose-500/30 p-2.5 rounded text-rose-300 text-xs">🛑 <strong>Conversation Ended:</strong> ${data.rationale}</div>`;
        }

        chatBox.innerHTML += `
          <div class="flex flex-col items-start space-y-1">
            <span class="text-[10px] text-slate-500 font-medium">Vera [action: ${data.action}]</span>
            ${botContent}
            <span class="text-[10px] text-slate-500 italic pl-1">${data.rationale}</span>
          </div>
        `;
        chatBox.scrollTop = chatBox.scrollHeight;
      } catch (e) {
        chatBox.innerHTML += `<div class="text-rose-400 text-xs p-2">Error sending reply: ${e}</div>`;
      }
    }

    function sendQuickReply(msg) {
      sendReplyToBot(msg);
    }

    function sendCustomReply() {
      const input = document.getElementById('chat-input');
      const msg = input.value.trim();
      if (!msg) return;
      input.value = '';
      sendReplyToBot(msg);
    }

    setInterval(updateHealth, 3000);
    updateHealth();
  </script>
</body>
</html>
"""
