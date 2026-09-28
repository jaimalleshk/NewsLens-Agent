/**
 * Interactive Agent Chat & Voice Dialogue Drawer
 */

class AgentChatUI {
  constructor() {
    this.drawer = document.getElementById("agentChatDrawer");
    this.btnToggle = document.getElementById("btnToggleChat");
    this.btnClose = document.getElementById("btnCloseChat");
    this.btnSend = document.getElementById("btnSendChat");
    this.btnMic = document.getElementById("btnChatMic");
    this.input = document.getElementById("chatInputText");
    this.messagesContainer = document.getElementById("chatMessages");

    this.initEvents();
  }

  initEvents() {
    if (this.btnToggle) {
      this.btnToggle.addEventListener("click", () => this.toggleDrawer());
    }
    if (this.btnClose) {
      this.btnClose.addEventListener("click", () => this.closeDrawer());
    }
    if (this.btnSend) {
      this.btnSend.addEventListener("click", () => this.sendMessage());
    }
    if (this.input) {
      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }
    if (this.btnMic) {
      this.btnMic.addEventListener("click", () => {
        window.voiceEngine.startListening(
          (text) => {
            this.input.value = text;
            this.sendMessage();
          },
          (listening) => {
            this.btnMic.textContent = listening ? "🔴" : "🎙️";
          }
        );
      });
    }
  }

  toggleDrawer() {
    this.drawer.classList.toggle("closed");
    if (!this.drawer.classList.contains("closed")) {
      this.input.focus();
    }
  }

  openDrawer() {
    this.drawer.classList.remove("closed");
    this.input.focus();
  }

  closeDrawer() {
    this.drawer.classList.add("closed");
  }

  appendMessage(text, sender = "agent", sources = []) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}-bubble`;

    let html = `<p>${text.replace(/\n/g, "<br>")}</p>`;

    if (sources && sources.length > 0) {
      html += `<div class="chat-sources"><strong>Cited Sources:</strong><ul>`;
      sources.slice(0, 3).forEach(s => {
        html += `<li><a href="${s.url}" target="_blank" style="color:var(--accent-cyan); text-decoration:underline;">${s.title}</a> (${s.source})</li>`;
      });
      html += `</ul></div>`;
    }

    bubble.innerHTML = html;
    this.messagesContainer.appendChild(bubble);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  async sendMessage(customText = null) {
    const text = customText || this.input.value.trim();
    if (!text) return;

    this.input.value = "";
    this.appendMessage(text, "user");

    const startDate = document.getElementById("startDate")?.value || "";
    const endDate = document.getElementById("endDate")?.value || "";

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          start_date: startDate,
          end_date: endDate
        })
      });

      if (!resp.ok) throw new Error("Chat request failed");

      const data = await resp.json();
      this.appendMessage(data.reply, "agent", data.rag_sources);

      // Play natural voice response
      if (data.spoken_reply && window.voiceEngine) {
        window.voiceEngine.playNaturalSpeech(data.spoken_reply, "Agent Voice Response");
      }

      // If configuration mutated (e.g. topic added/deleted), refresh app tabs
      if (data.config_mutated && window.newsApp) {
        window.newsApp.loadConfigAndBuildTabs();
      }
    } catch (err) {
      this.appendMessage(`Sorry, I encountered an error: ${err.message}`, "agent");
    }
  }
}

window.agentChatUI = new AgentChatUI();
