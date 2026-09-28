/**
 * NewsLens Dashboard Controller & Dynamic Tabs Orchestrator
 */

class NewsLensApp {
  constructor() {
    this.config = null;
    this.currentDigest = null;
    this.activeTopicId = "overview"; // 'overview' or topic.id
    this.configMode = "visual"; // 'visual' or 'yaml'
    this.viewMode = "compact"; // Default: 'compact' (1 precise line) or 'full' (1 line + 5-lines analysis)

    this.initDates();
    this.initEventListeners();
    this.loadConfigAndBuildTabs();
  }

  initDates() {
    const today = new Date();
    const past7 = new Date();
    past7.setDate(today.getDate() - 7);

    const fmt = (d) => d.toISOString().split("T")[0];
    document.getElementById("startDate").value = fmt(past7);
    document.getElementById("endDate").value = fmt(today);
  }

  initEventListeners() {
    // Preset Buttons
    document.querySelectorAll(".btn-preset").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".btn-preset").forEach(b => b.classList.remove("active"));
        e.target.classList.add("active");
        const days = parseInt(e.target.dataset.days, 10);
        const today = new Date();
        const start = new Date();
        start.setDate(today.getDate() - days);

        const fmt = (d) => d.toISOString().split("T")[0];
        document.getElementById("startDate").value = fmt(start);
        document.getElementById("endDate").value = fmt(today);
      });
    });

    // View Density Switcher (1-Line vs 5-Lines)
    const btn1Line = document.getElementById("btnView1Line");
    const btn5Lines = document.getElementById("btnView5Lines");

    btn1Line?.addEventListener("click", () => this.setViewMode("compact"));
    btn5Lines?.addEventListener("click", () => this.setViewMode("full"));

    // Ingestion Button
    document.getElementById("btnFetchNews").addEventListener("click", () => this.runNewsAggregation());

    // Top Voice Command Button
    const btnVoice = document.getElementById("btnVoiceCommand");
    const voiceLabel = document.getElementById("voiceBtnLabel");
    if (btnVoice) {
      btnVoice.addEventListener("click", () => {
        window.agentChatUI.openDrawer();
        window.voiceEngine.startListening(
          (text) => {
            window.agentChatUI.sendMessage(text);
          },
          (listening) => {
            if (listening) {
              btnVoice.classList.add("listening");
              voiceLabel.textContent = "Listening...";
            } else {
              btnVoice.classList.remove("listening");
              voiceLabel.textContent = "Voice Mode";
            }
          }
        );
      });
    }

    // Audio Play All Buttons (Continuous Section-by-Section Spoken Broadcast)
    document.getElementById("btnPlayAllAudio")?.addEventListener("click", () => {
      if (!this.currentDigest || !this.currentDigest.topic_results || this.currentDigest.topic_results.length === 0) {
        alert("Please run Ingestion first to generate an audio digest.");
        return;
      }

      // Build complete section-by-section playlist covering every single topic
      const sections = [];

      // 1. Introductory Overview Section
      if (this.currentDigest.executive_overview) {
        // Extract macro synthesis paragraphs for the introductory broadcast
        const macroMatch = this.currentDigest.executive_overview.match(/### 📊 Macro Strategic Cross-Sector Synthesis\s*([\s\S]+?)(?=\n---|\Z)/);
        let introText = macroMatch ? macroMatch[1] : this.currentDigest.executive_overview;
        introText = introText.replace(/[#*`_\[\]•]/g, "").replace(/\n+/g, " ").trim();
        if (introText.length > 500) {
          introText = introText.slice(0, 500) + "...";
        }

        sections.push({
          id: "overview",
          title: "Executive Cross-Topic Overview",
          icon: "🌐",
          script: `Welcome to your Executive News Intelligence Briefing for ${this.currentDigest.start_date} to ${this.currentDigest.end_date}. ${introText}`,
          storiesCount: this.currentDigest.topic_results.reduce((acc, t) => acc + (t.items ? t.items.length : 0), 0)
        });
      }

      // 2. Add each topic section with its complete full-coverage spoken script
      this.currentDigest.topic_results.forEach(topicRes => {
        if (topicRes.items && topicRes.items.length > 0) {
          let script = topicRes.executive_audio_script;
          const isGeneric = !script || script.length < 80 || script.includes("Intelligence synthesis completed") || script.includes("Intelligence summary for current");
          if (isGeneric) {
            const storyParts = topicRes.items.map((it, idx) => {
              const transition = idx === 0 ? "Starting with" : (idx === topicRes.items.length - 1 && topicRes.items.length > 1 ? "Finally," : "Next in headlines,");
              return `${transition} ${it.title}. ${it.summary.line1_what}`;
            });
            script = `Here is your news briefing for ${topicRes.topic_title}, covering ${topicRes.items.length} developments. ${storyParts.join(" ")} That concludes all updates for ${topicRes.topic_title}.`;
          }

          sections.push({
            id: topicRes.topic_id,
            title: topicRes.topic_title,
            icon: topicRes.topic_icon || "📰",
            script: script,
            storiesCount: topicRes.items.length
          });
        }
      });

      window.voiceEngine.playAllSections(sections, (topicId) => {
        this.switchTab(topicId);
      });
    });

    document.getElementById("btnPlayTopicAudio")?.addEventListener("click", () => {
      if (!this.currentDigest) return;
      const topicRes = this.currentDigest.topic_results.find(t => t.topic_id === this.activeTopicId);
      if (topicRes) {
        let script = topicRes.executive_audio_script;
        const isGeneric = !script || script.length < 80 || script.includes("Intelligence synthesis completed") || script.includes("Intelligence summary for current");
        if (isGeneric && topicRes.items && topicRes.items.length > 0) {
          const storyParts = topicRes.items.map((it, idx) => {
            const transition = idx === 0 ? "Starting with" : (idx === topicRes.items.length - 1 && topicRes.items.length > 1 ? "Finally," : "Next in headlines,");
            return `${transition} ${it.title}. ${it.summary.line1_what}`;
          });
          script = `Here is your news briefing for ${topicRes.topic_title}, covering ${topicRes.items.length} developments. ${storyParts.join(" ")} That concludes all updates for ${topicRes.topic_title}.`;
        }
        window.voiceEngine.playNaturalSpeech(
          script,
          `${topicRes.topic_title} Spoken Briefing`
        );
      }
    });

    // Header LLM Status Badge click
    document.getElementById("headerLlmBadge")?.addEventListener("click", () => this.openConfigModal());

    // Config Modal Listeners
    document.getElementById("btnOpenConfig")?.addEventListener("click", () => this.openConfigModal());
    document.getElementById("btnAddTopicQuick")?.addEventListener("click", () => this.openConfigModal(true));
    document.getElementById("btnCloseConfigModal")?.addEventListener("click", () => this.closeConfigModal());
    document.getElementById("btnCancelConfig")?.addEventListener("click", () => this.closeConfigModal());
    document.getElementById("btnSaveConfig")?.addEventListener("click", () => this.saveConfigFromModal());
    document.getElementById("btnAddNewTopicModal")?.addEventListener("click", () => this.addTopicCardInModal());
    document.getElementById("btnReloadYaml")?.addEventListener("click", () => this.loadRawYamlIntoEditor());

    // Config Mode Switcher (Visual vs YAML)
    document.getElementById("btnModeVisual")?.addEventListener("click", () => this.switchConfigMode("visual"));
    document.getElementById("btnModeYaml")?.addEventListener("click", () => this.switchConfigMode("yaml"));

    // Dynamic LLM Provider Selection Handler
    document.getElementById("configLlmProvider")?.addEventListener("change", (e) => {
      const isLocal = e.target.value === "local";
      document.getElementById("rowApiKey").style.display = isLocal ? "none" : "flex";
      document.getElementById("rowLocalUrl").style.display = isLocal ? "flex" : "none";
      this.populateLlmModels(e.target.value);
    });

    // Dynamic Model Selection dropdown change (handles custom)
    document.getElementById("configLlmModelSelect")?.addEventListener("change", (e) => {
      const rowCustom = document.getElementById("rowCustomModel");
      if (rowCustom) {
        if (e.target.value === "custom") {
          rowCustom.classList.remove("hidden");
        } else {
          rowCustom.classList.add("hidden");
        }
      }
    });

    // Refresh models button
    document.getElementById("btnRefreshModels")?.addEventListener("click", () => {
      const prov = document.getElementById("configLlmProvider")?.value || "deepseek";
      this.populateLlmModels(prov);
    });

    // Test Connection Button
    document.getElementById("btnTestLlmConnection")?.addEventListener("click", () => this.testLlmConnection());

    // Toggle API Key Visibility
    document.getElementById("btnToggleApiKeyVisibility")?.addEventListener("click", () => {
      const input = document.getElementById("configLlmApiKey");
      if (input) {
        input.type = input.type === "password" ? "text" : "password";
      }
    });

    // Quick Keyword Feed & Persistence
    const btnQuickFeed = document.getElementById("btnQuickFeedKeyword");
    const inputQuickKeyword = document.getElementById("quickKeywordInput");
    
    btnQuickFeed?.addEventListener("click", () => this.handleQuickFeedKeyword());
    inputQuickKeyword?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.handleQuickFeedKeyword();
      }
    });

    // Inline Topic Keyword Add
    const btnInlineAdd = document.getElementById("btnInlineAddKeyword");
    const inputInline = document.getElementById("inlineKeywordInput");

    btnInlineAdd?.addEventListener("click", () => this.handleInlineAddKeyword());
    inputInline?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.handleInlineAddKeyword();
      }
    });
  }

  async handleQuickFeedKeyword() {
    const input = document.getElementById("quickKeywordInput");
    const topicSelect = document.getElementById("quickTopicSelect");
    const statusBadge = document.getElementById("keywordSaveStatus");
    const rawVal = input?.value.trim();
    if (!rawVal) return;

    let targetTopicId = topicSelect?.value || (this.activeTopicId !== "overview" ? this.activeTopicId : null);

    try {
      const resp = await fetch("/api/config/keywords/quick-add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword: rawVal,
          topic_id: targetTopicId
        })
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to save keyword");
      }

      const data = await resp.json();
      input.value = "";

      if (statusBadge) {
        statusBadge.textContent = `✓ Saved to ${data.topic.title} in YAML!`;
        statusBadge.classList.remove("hidden");
        setTimeout(() => statusBadge.classList.add("hidden"), 3000);
      }

      await this.loadConfigAndBuildTabs();
      this.switchTab(data.topic.id);
    } catch (err) {
      alert(`Error feeding keyword: ${err.message}`);
    }
  }

  async handleInlineAddKeyword() {
    const input = document.getElementById("inlineKeywordInput");
    const rawVal = input?.value.trim();
    if (!rawVal || this.activeTopicId === "overview") return;

    try {
      const resp = await fetch(`/api/config/topics/${this.activeTopicId}/keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keywords: [rawVal]
        })
      });

      if (!resp.ok) throw new Error("Failed to add keyword");

      input.value = "";
      await this.loadConfigAndBuildTabs();
      this.renderTopicPane(this.activeTopicId);
    } catch (err) {
      alert(`Error adding keyword: ${err.message}`);
    }
  }

  async deleteTopicKeyword(topicId, keyword) {
    try {
      const resp = await fetch(`/api/config/topics/${topicId}/keywords`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword })
      });

      if (!resp.ok) throw new Error("Failed to delete keyword");

      await this.loadConfigAndBuildTabs();
      this.renderTopicPane(topicId);
    } catch (err) {
      alert(`Error deleting keyword: ${err.message}`);
    }
  }

  setViewMode(mode) {
    this.viewMode = mode;
    const btn1Line = document.getElementById("btnView1Line");
    const btn5Lines = document.getElementById("btnView5Lines");

    if (mode === "compact") {
      btn1Line?.classList.add("active");
      btn5Lines?.classList.remove("active");
    } else {
      btn1Line?.classList.remove("active");
      btn5Lines?.classList.add("active");
    }

    const dividerLabel = document.getElementById("overviewStoriesDividerLabel");
    if (dividerLabel) {
      dividerLabel.textContent = mode === "compact"
        ? "TOP STORIES ACROSS ALL TOPICS (1-LINE VIEW)"
        : "TOP STORIES ACROSS ALL TOPICS (FULL 5-LINE ANALYSIS)";
    }

    // Re-render active pane with new view mode
    if (this.activeTopicId === "overview") {
      this.renderOverviewPane();
    } else {
      this.renderTopicPane(this.activeTopicId);
    }
  }

  switchConfigMode(mode) {
    this.configMode = mode;
    const btnVisual = document.getElementById("btnModeVisual");
    const btnYaml = document.getElementById("btnModeYaml");
    const paneVisual = document.getElementById("paneVisualConfig");
    const paneYaml = document.getElementById("paneYamlConfig");

    if (mode === "visual") {
      btnVisual.classList.add("active");
      btnYaml.classList.remove("active");
      paneVisual.classList.remove("hidden");
      paneYaml.classList.add("hidden");
    } else {
      btnVisual.classList.remove("active");
      btnYaml.classList.add("active");
      paneVisual.classList.add("hidden");
      paneYaml.classList.remove("hidden");
      this.loadRawYamlIntoEditor();
    }
  }

  async loadConfigAndBuildTabs() {
    try {
      const resp = await fetch("/api/config");
      if (!resp.ok) throw new Error("Failed to load config");
      this.config = await resp.json();

      if (this.config.ui && this.config.ui.view_mode) {
        this.viewMode = this.config.ui.view_mode;
        this.setViewMode(this.viewMode);
      }

      this.renderDynamicTabs();
      this.updateHeaderLlmBadge();
    } catch (e) {
      console.warn("Using default topics:", e);
    }
  }

  async loadRawYamlIntoEditor() {
    const errorAlert = document.getElementById("yamlErrorAlert");
    if (errorAlert) errorAlert.classList.add("hidden");

    try {
      const resp = await fetch("/api/config/yaml");
      if (!resp.ok) throw new Error("Failed to load YAML configuration");
      const data = await resp.json();

      document.getElementById("rawYamlEditor").value = data.yaml;
      const pathBadge = document.getElementById("configFilePathBadge");
      if (pathBadge && data.path) {
        pathBadge.textContent = data.path.split(/[\\/]/).pop() || "config.user.yaml";
        pathBadge.title = data.path;
      }
    } catch (err) {
      if (errorAlert) {
        errorAlert.textContent = `Error loading YAML: ${err.message}`;
        errorAlert.classList.remove("hidden");
      }
    }
  }

  renderDynamicTabs() {
    const tabList = document.getElementById("dynamicTabBar");
    if (!tabList) return;
    tabList.innerHTML = "";

    const quickSelect = document.getElementById("quickTopicSelect");
    if (quickSelect) {
      quickSelect.innerHTML = `<option value="">🎯 Auto-detect / Current Topic</option>`;
    }

    const totalActive = (this.config?.topics || []).filter(t => t.enabled).length;
    const countEl = document.getElementById("sidebarTopicCount");
    if (countEl) countEl.textContent = `${totalActive} Active`;

    // 1. Executive Overview Tab
    const overviewTab = document.createElement("button");
    overviewTab.className = `tab-item ${this.activeTopicId === "overview" ? "active" : ""}`;
    const allCount = this.currentDigest ? this.currentDigest.topic_results.reduce((acc, t) => acc + (t.items ? t.items.length : 0), 0) : 0;
    overviewTab.innerHTML = `
      <div class="tab-title-group">
        <span>🌐</span>
        <span>Executive Overview</span>
      </div>
      ${allCount > 0 ? `<span class="tab-badge-count">${allCount}</span>` : ""}
    `;
    overviewTab.addEventListener("click", () => this.switchTab("overview"));
    tabList.appendChild(overviewTab);

    // 2. Dynamic Topic Tabs from Config
    if (this.config && this.config.topics) {
      this.config.topics.forEach(topic => {
        if (!topic.enabled) return;

        const count = this.getTopicArticleCount(topic.id);
        const tab = document.createElement("button");
        tab.className = `tab-item ${this.activeTopicId === topic.id ? "active" : ""}`;
        tab.innerHTML = `
          <div class="tab-title-group">
            <span>${topic.icon || "📰"}</span>
            <span>${topic.title}</span>
          </div>
          ${count > 0 ? `<span class="tab-badge-count">${count}</span>` : ""}
        `;
        tab.addEventListener("click", () => this.switchTab(topic.id));
        tabList.appendChild(tab);

        if (quickSelect) {
          const opt = document.createElement("option");
          opt.value = topic.id;
          opt.textContent = `${topic.icon || "📰"} ${topic.title}`;
          quickSelect.appendChild(opt);
        }
      });
    }
  }


  getTopicArticleCount(topicId) {
    if (!this.currentDigest) return 0;
    const t = this.currentDigest.topic_results.find(x => x.topic_id === topicId);
    return t ? t.items.length : 0;
  }

  switchTab(topicId) {
    this.activeTopicId = topicId;
    this.renderDynamicTabs();

    const paneOverview = document.getElementById("paneOverview");
    const paneTopic = document.getElementById("paneTopic");

    if (topicId === "overview") {
      paneOverview.classList.remove("hidden");
      paneTopic.classList.add("hidden");
      this.renderOverviewPane();
    } else {
      paneOverview.classList.add("hidden");
      paneTopic.classList.remove("hidden");
      this.renderTopicPane(topicId);
    }
  }

  async runNewsAggregation() {
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;

    const overlay = document.getElementById("loadingOverlay");
    const statusText = document.getElementById("loadingStatusText");
    const banner = document.getElementById("streamingProgressBanner");
    const bannerText = document.getElementById("streamingProgressText");

    if (banner) banner.classList.remove("hidden");
    if (bannerText) bannerText.textContent = "Connecting to real-time intelligence stream...";
    if (overlay) overlay.classList.remove("hidden");
    if (statusText) statusText.textContent = "Connecting to real-time intelligence stream...";

    // Initialize/reset currentDigest for live progressive updates
    this.currentDigest = {
      start_date: startDate,
      end_date: endDate,
      executive_overview: "Analyzing news streams across active topics in real time...",
      executive_audio_script: "",
      topic_results: [],
      total_articles_indexed: 0
    };

    // Clear overview grid for streaming cards
    const gridOverview = document.getElementById("allTopicsDigestGrid");
    if (gridOverview && this.activeTopicId === "overview") {
      gridOverview.innerHTML = "";
    }

    try {
      const response = await fetch(`/api/news/stream?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`);
      if (!response.ok) throw new Error(`Streaming failed with status ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep remainder

        for (const block of lines) {
          const trimmed = block.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.replace(/^data:\s*/, "");
          try {
            const eventObj = JSON.parse(jsonStr);
            this.handleStreamEvent(eventObj);
          } catch (e) {
            console.warn("Error parsing stream chunk:", e);
          }
        }
      }
    } catch (e) {
      console.error("Streaming error, falling back to aggregate endpoint:", e);
      try {
        const resp = await fetch("/api/news/aggregate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start_date: startDate, end_date: endDate })
        });
        if (resp.ok) {
          this.currentDigest = await resp.json();
          this.renderDynamicTabs();
          this.switchTab(this.activeTopicId);
        }
      } catch (err) {
        alert(`News aggregation error: ${err.message}`);
      }
    } finally {
      if (overlay) overlay.classList.add("hidden");
    }
  }

  handleStreamEvent(eventObj) {
    const statusText = document.getElementById("loadingStatusText");
    const banner = document.getElementById("streamingProgressBanner");
    const bannerText = document.getElementById("streamingProgressText");
    const overlay = document.getElementById("loadingOverlay");

    if (eventObj.event === "start") {
      const msg = `⚡ Ingesting ${eventObj.total_topics} news topic feeds concurrently...`;
      if (statusText) statusText.textContent = msg;
      if (bannerText) bannerText.textContent = msg;
    } else if (eventObj.event === "topic_result") {
      const topicData = eventObj.topic;
      const existingIdx = this.currentDigest.topic_results.findIndex(t => t.topic_id === topicData.topic_id);
      if (existingIdx >= 0) {
        this.currentDigest.topic_results[existingIdx] = topicData;
      } else {
        this.currentDigest.topic_results.push(topicData);
      }

      const msg = `⚡ Ingested (${eventObj.completed_count}/${eventObj.total_topics}): ${topicData.topic_title} (+${topicData.items.length} stories)`;
      if (statusText) statusText.textContent = msg;
      if (bannerText) bannerText.textContent = msg;

      // Hide blocking overlay immediately so user can read cards in real-time
      if (overlay) overlay.classList.add("hidden");

      // Update tab badges dynamically
      this.renderDynamicTabs();

      // Progressively render news cards
      if (this.activeTopicId === "overview") {
        const grid = document.getElementById("allTopicsDigestGrid");
        if (grid) {
          topicData.items.forEach(item => {
            grid.appendChild(this.createNewsCardElement(item, topicData));
          });
        }
      } else if (this.activeTopicId === topicData.topic_id) {
        this.renderTopicPane(topicData.topic_id);
      }
    } else if (eventObj.event === "complete") {
      this.currentDigest = eventObj.digest;
      this.renderDynamicTabs();
      if (this.activeTopicId === "overview") {
        this.renderOverviewPane();
      } else {
        this.renderTopicPane(this.activeTopicId);
      }
      if (overlay) overlay.classList.add("hidden");

      const totalStories = this.currentDigest.topic_results.reduce((acc, t) => acc + (t.items ? t.items.length : 0), 0);
      if (bannerText) bannerText.textContent = `✓ Intelligence Ingestion Complete: ${totalStories} curated stories indexed across ${this.currentDigest.topic_results.length} topics.`;
      setTimeout(() => {
        if (banner) banner.classList.add("hidden");
      }, 4000);
    }
  }


  renderOverviewPane() {
    if (!this.currentDigest) return;

    document.getElementById("digestDateBadge").textContent =
      `Date Window: ${this.currentDigest.start_date} to ${this.currentDigest.end_date} | Total Indexed: ${this.currentDigest.total_articles_indexed} chunks`;

    const overviewDiv = document.getElementById("overviewSummaryContent");
    overviewDiv.innerHTML = this.renderSimpleMarkdown(this.currentDigest.executive_overview);

    const grid = document.getElementById("allTopicsDigestGrid");
    grid.className = `news-cards-grid ${this.viewMode === "compact" ? "compact-layout" : ""}`;
    grid.innerHTML = "";

    this.currentDigest.topic_results.forEach(topicRes => {
      topicRes.items.forEach(item => {
        grid.appendChild(this.createNewsCardElement(item, topicRes));
      });
    });
  }

  renderTopicPane(topicId) {
    const topic = this.config?.topics.find(t => t.id === topicId);
    if (!topic) return;

    document.getElementById("currentTopicTitle").textContent = `${topic.icon || "📰"} ${topic.title}`;
    document.getElementById("currentTopicStrategy").textContent = topic.strategy_prompt;

    // Render Monitored Keywords Chips in YAML
    const keywordsList = document.getElementById("currentTopicKeywordsList");
    if (keywordsList) {
      keywordsList.innerHTML = "";
      (topic.search_queries || []).forEach(kw => {
        const chip = document.createElement("span");
        chip.className = "keyword-chip";
        chip.innerHTML = `${kw} <span class="chip-remove" title="Remove keyword from YAML">✕</span>`;
        chip.querySelector(".chip-remove").addEventListener("click", (e) => {
          e.stopPropagation();
          this.deleteTopicKeyword(topic.id, kw);
        });
        keywordsList.appendChild(chip);
      });
      if (!topic.search_queries || topic.search_queries.length === 0) {
        keywordsList.innerHTML = `<span style="font-size:0.75rem; color:var(--text-muted); font-style:italic;">No custom keywords yet. Type below to add.</span>`;
      }
    }

    const grid = document.getElementById("topicNewsCardsGrid");
    grid.className = `news-cards-grid ${this.viewMode === "compact" ? "compact-layout" : ""}`;
    grid.innerHTML = "";

    if (!this.currentDigest) {
      grid.innerHTML = `<p class="placeholder-text">Click 'Run Ingestion' to fetch news for this topic.</p>`;
      return;
    }

    const topicRes = this.currentDigest.topic_results.find(t => t.topic_id === topicId);
    if (!topicRes || topicRes.items.length === 0) {
      grid.innerHTML = `<p class="placeholder-text">No news articles found for this topic in the selected date window.</p>`;
      return;
    }

    topicRes.items.forEach(item => {
      grid.appendChild(this.createNewsCardElement(item, topicRes));
    });
  }

  createNewsCardElement(item, topicRes) {
    const card = document.createElement("article");
    const s = item.summary;
    const isCompact = this.viewMode === "compact";

    if (isCompact) {
      // Clean Compact Mode
      card.className = "news-card compact-item";
      card.innerHTML = `
        <div class="compact-row">
          <div class="compact-main">
            <div class="compact-headline-line">
              <strong>${item.title}</strong> — <span class="story-desc">${s.line1_what}</span>
            </div>
            <div class="compact-meta">
              <span class="source-badge">${item.publisher}</span>
              <span class="pub-date">${item.published_date}</span>
            </div>
          </div>
          <div class="compact-actions">
            <button class="btn-card-audio" title="Read Aloud">🔊</button>
            <a href="${item.url}" target="_blank" rel="noopener" class="card-source-link" title="Open Source">
              Source ↗
            </a>
          </div>
        </div>
      `;
    } else {
      // Clean Expanded Card Mode
      card.className = "news-card";
      card.innerHTML = `
        <div class="card-header">
          <div class="card-meta-row">
            <span class="source-badge">${item.publisher}</span>
            <span class="pub-date">${item.published_date}</span>
          </div>
          <h3 class="card-title">${item.title}</h3>
        </div>

        <div class="card-story-summary">
          ${s.line1_what}
        </div>

        <div class="card-footer">
          <button class="btn-card-audio">🔊 Read Aloud</button>
          <a href="${item.url}" target="_blank" rel="noopener" class="card-source-link">
            Source Article ↗
          </a>
        </div>
      `;
    }

    // Read Aloud click event
    const btnAudio = card.querySelector(".btn-card-audio");
    btnAudio?.addEventListener("click", (e) => {
      e.stopPropagation();
      const speechText = item.natural_speech || `${item.title}. ${s.line1_what}`;
      window.voiceEngine.playNaturalSpeech(speechText, item.title);
    });

    return card;
  }

  renderSimpleMarkdown(text) {
    if (!text) return "";
    return text
      .replace(/#### (.*)/g, '<h4 class="overview-section-h4">$1</h4>')
      .replace(/### (.*)/g, '<h3 class="overview-section-h3">$1</h3>')
      .replace(/## (.*)/g, '<h2 class="overview-section-h2">$1</h2>')
      .replace(/# (.*)/g, '<h1 class="overview-section-h1">$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^[•\-\*]\s+(.*)/gm, '<div class="overview-story-bullet"><span class="bullet-dot">•</span> <span class="bullet-text">$1</span></div>')
      .replace(/^---$/gm, '<hr class="overview-divider">')
      .replace(/\n\n/g, '<p style="margin-bottom:0.75rem;">')
      .replace(/\n/g, '<br>');
  }

  updateHeaderLlmBadge() {
    const badge = document.getElementById("headerLlmBadge");
    const nameEl = document.getElementById("headerLlmName");
    if (!this.config || !this.config.llm || !nameEl) return;

    const provider = this.config.llm.provider || "deepseek";
    const model = this.config.llm.model || (provider === "deepseek" ? "deepseek-chat" : "deepseek-r1:8b");
    const isDeepSeek = provider === "deepseek";

    if (badge) {
      badge.className = `btn-llm-pill ${isDeepSeek ? "provider-deepseek" : "provider-local"}`;
      badge.title = `Active AI Backend: ${isDeepSeek ? "DeepSeek Cloud API" : "Local Ollama"}. Model: ${model}. Click to configure.`;
    }
    nameEl.textContent = isDeepSeek ? `⚡ DeepSeek: ${model}` : `🖥️ Local: ${model}`;
  }

  async populateLlmModels(provider, targetModel = null) {
    const select = document.getElementById("configLlmModelSelect");
    const rowCustom = document.getElementById("rowCustomModel");
    const inputCustom = document.getElementById("configLlmCustomModel");
    if (!select) return;

    select.innerHTML = `<option value="">Loading models...</option>`;

    try {
      const resp = await fetch(`/api/config/llm/models?provider=${provider}`);
      if (!resp.ok) throw new Error("Failed to fetch models");
      const data = await resp.json();

      select.innerHTML = "";
      const models = data.models || [];
      let matched = false;

      models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        const recBadge = m.recommended ? " ★ Recommended" : "";
        const ctxBadge = m.context_length ? ` [${m.context_length}]` : "";
        opt.textContent = `${m.name}${ctxBadge}${recBadge}`;
        if (targetModel && m.id === targetModel) {
          opt.selected = true;
          matched = true;
        }
        select.appendChild(opt);
      });

      // Append Custom Model Option
      const customOpt = document.createElement("option");
      customOpt.value = "custom";
      customOpt.textContent = "✏️ (Custom / Enter Model ID...)";
      if (targetModel && !matched) {
        customOpt.selected = true;
        matched = true;
        if (inputCustom) inputCustom.value = targetModel;
      }
      select.appendChild(customOpt);

      if (!targetModel && select.options.length > 0) {
        select.options[0].selected = true;
      }

      if (rowCustom) {
        if (select.value === "custom") {
          rowCustom.classList.remove("hidden");
        } else {
          rowCustom.classList.add("hidden");
        }
      }
    } catch (err) {
      console.warn("Could not load dynamic models:", err);
      select.innerHTML = `
        <option value="deepseek-chat">deepseek-chat (DeepSeek-V3 - Ultra Fast)</option>
        <option value="deepseek-reasoner">deepseek-reasoner (DeepSeek-R1 - Deep Reasoning)</option>
        <option value="custom">✏️ Custom Model...</option>
      `;
    }
  }

  async testLlmConnection() {
    const statusPill = document.getElementById("llmTestStatus");
    const provider = document.getElementById("configLlmProvider").value;
    const modelSelect = document.getElementById("configLlmModelSelect");
    let model = modelSelect ? modelSelect.value : "deepseek-chat";
    if (model === "custom") {
      model = document.getElementById("configLlmCustomModel")?.value.trim();
    }
    const apiKey = document.getElementById("configLlmApiKey")?.value.trim();
    const localUrl = document.getElementById("configLlmLocalUrl")?.value.trim();

    if (statusPill) {
      statusPill.className = "test-status-pill testing";
      statusPill.innerHTML = `<span>⏳</span> Testing ${provider} connection with '${model || 'default'}'...`;
      statusPill.classList.remove("hidden");
    }

    try {
      const resp = await fetch("/api/config/llm/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: provider,
          model: model || (provider === "deepseek" ? "deepseek-chat" : "deepseek-r1:8b"),
          api_key: apiKey,
          local_api_base: localUrl
        })
      });

      const data = await resp.json();
      if (!resp.ok || data.status === "error") {
        if (statusPill) {
          statusPill.className = "test-status-pill error";
          statusPill.innerHTML = `<span>✕</span> ${data.message || data.detail || "Connection test failed"}`;
        }
      } else {
        if (statusPill) {
          statusPill.className = "test-status-pill success";
          statusPill.innerHTML = `<span>✓</span> Connected! (${data.latency_ms}ms) Response: "${data.sample_response || 'OK'}"`;
        }
      }
    } catch (err) {
      if (statusPill) {
        statusPill.className = "test-status-pill error";
        statusPill.innerHTML = `<span>✕</span> Network error: ${err.message}`;
      }
    }
  }

  async openConfigModal(focusAddTopic = false) {
    if (!this.config) return;
    const modal = document.getElementById("configModal");
    modal.classList.remove("hidden");

    const statusPill = document.getElementById("llmTestStatus");
    if (statusPill) statusPill.classList.add("hidden");

    document.getElementById("configLlmProvider").value = this.config.llm.provider || "deepseek";
    document.getElementById("configLlmApiKey").value = this.config.llm.api_key || "";
    document.getElementById("configLlmLocalUrl").value = this.config.llm.local_api_base || "http://localhost:11434/v1";

    const isLocal = this.config.llm.provider === "local";
    document.getElementById("rowApiKey").style.display = isLocal ? "none" : "flex";
    document.getElementById("rowLocalUrl").style.display = isLocal ? "flex" : "none";

    await this.populateLlmModels(this.config.llm.provider || "deepseek", this.config.llm.model);

    this.renderTopicsConfigList();
    this.loadRawYamlIntoEditor();

    if (focusAddTopic) {
      this.switchConfigMode("visual");
      this.addTopicCardInModal();
    }
  }

  closeConfigModal() {
    const modal = document.getElementById("configModal");
    if (modal) modal.classList.add("hidden");
    const notice = document.getElementById("yamlStatusNotice");
    if (notice) notice.textContent = "";
    const errorAlert = document.getElementById("yamlErrorAlert");
    if (errorAlert) errorAlert.classList.add("hidden");
    const statusPill = document.getElementById("llmTestStatus");
    if (statusPill) statusPill.classList.add("hidden");
  }

  renderTopicsConfigList() {
    const container = document.getElementById("topicsConfigList");
    container.innerHTML = "";

    this.config.topics.forEach((topic, idx) => {
      const card = document.createElement("div");
      card.className = "topic-config-card";
      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
          <input type="text" class="form-input" style="width:50px; text-align:center;" value="${topic.icon || "📰"}" data-field="icon" data-idx="${idx}">
          <input type="text" class="form-input" style="flex:1; margin:0 0.5rem; font-weight:700;" value="${topic.title}" data-field="title" data-idx="${idx}">
          <button class="btn btn-secondary btn-sm btn-delete-topic" data-idx="${idx}" style="color:var(--accent-rose);">🗑️</button>
        </div>
        <div class="form-row">
          <label>Strategic Focus Prompt:</label>
          <textarea class="form-textarea" rows="2" data-field="strategy_prompt" data-idx="${idx}">${topic.strategy_prompt}</textarea>
        </div>
        <div class="form-row">
          <label>Search Queries (comma-separated):</label>
          <input type="text" class="form-input" value="${(topic.search_queries || []).join(', ')}" data-field="search_queries" data-idx="${idx}">
        </div>
      `;

      card.querySelector(".btn-delete-topic").addEventListener("click", () => {
        this.config.topics.splice(idx, 1);
        this.renderTopicsConfigList();
      });

      container.appendChild(card);
    });
  }

  addTopicCardInModal() {
    const newTopic = {
      id: `topic_${Date.now()}`,
      title: "New Strategic Topic",
      icon: "🎯",
      enabled: true,
      strategy_prompt: "Focus on high-impact breakthroughs, regulatory decisions, and strategic shifts.",
      search_queries: ["industry analysis technology breakthrough"]
    };
    this.config.topics.push(newTopic);
    this.renderTopicsConfigList();
  }

  async saveConfigFromModal() {
    const notice = document.getElementById("yamlStatusNotice");
    const errorAlert = document.getElementById("yamlErrorAlert");
    if (errorAlert) errorAlert.classList.add("hidden");
    if (notice) {
      notice.textContent = "Saving configuration...";
      notice.style.color = "var(--text-secondary)";
    }

    if (this.configMode === "yaml") {
      const rawYaml = document.getElementById("rawYamlEditor").value;
      try {
        const resp = await fetch("/api/config/yaml", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ yaml: rawYaml })
        });

        if (!resp.ok) {
          const errData = await resp.json();
          throw new Error(errData.detail || "Failed to save YAML");
        }

        const resData = await resp.json();
        this.config = resData.config;
        this.renderDynamicTabs();
        this.updateHeaderLlmBadge();
        if (notice) {
          notice.textContent = "✓ YAML Saved & Applied!";
          notice.style.color = "var(--accent-emerald, #34d399)";
        }
        setTimeout(() => {
          this.closeConfigModal();
        }, 600);
      } catch (err) {
        if (errorAlert) {
          errorAlert.textContent = `YAML Save Error: ${err.message}`;
          errorAlert.classList.remove("hidden");
        }
        if (notice) notice.textContent = "";
      }
      return;
    }

    // Save from Visual Form
    const providerVal = document.getElementById("configLlmProvider").value;
    const modelSelect = document.getElementById("configLlmModelSelect");
    let modelVal = modelSelect ? modelSelect.value : "deepseek-chat";
    if (modelVal === "custom") {
      modelVal = document.getElementById("configLlmCustomModel")?.value.trim() || (providerVal === "deepseek" ? "deepseek-chat" : "deepseek-r1:8b");
    }

    this.config.llm.provider = providerVal;
    this.config.llm.model = modelVal;
    this.config.llm.api_key = document.getElementById("configLlmApiKey").value.trim();
    this.config.llm.local_api_base = document.getElementById("configLlmLocalUrl").value.trim();

    const inputs = document.querySelectorAll("#topicsConfigList [data-field]");
    inputs.forEach(input => {
      const idx = parseInt(input.dataset.idx, 10);
      const field = input.dataset.field;
      if (this.config.topics[idx]) {
        if (field === "search_queries") {
          this.config.topics[idx][field] = input.value.split(",").map(s => s.trim()).filter(Boolean);
        } else {
          this.config.topics[idx][field] = input.value;
        }
      }
    });

    try {
      const resp = await fetch("/api/config/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          llm: this.config.llm,
          topics: this.config.topics
        })
      });

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || "Failed to update configuration");
      }

      const resData = await resp.json();
      if (resData.config) {
        this.config = resData.config;
      }

      await this.loadConfigAndBuildTabs();
      this.updateHeaderLlmBadge();

      if (notice) {
        notice.textContent = "✓ Configuration Saved to YAML!";
        notice.style.color = "var(--accent-emerald, #34d399)";
      }

      setTimeout(() => {
        this.closeConfigModal();
      }, 600);
    } catch (e) {
      if (errorAlert) {
        errorAlert.textContent = `Save Error: ${e.message}`;
        errorAlert.classList.remove("hidden");
      }
      if (notice) notice.textContent = "";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.newsApp = new NewsLensApp();
});
