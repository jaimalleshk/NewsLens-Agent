/**
 * Natural Voice Engine & Speech Recognition (TTS & STT)
 * Supports Continuous Section-by-Section Spoken News Anchor
 */

class VoiceEngine {
  constructor() {
    this.audioPlayer = document.getElementById("globalAudioPlayer");
    this.banner = document.getElementById("audioBriefingBanner");
    this.bannerTitle = document.getElementById("audioBriefingTitle");
    this.sectionTracker = document.getElementById("audioSectionTracker");
    this.speedSelect = document.getElementById("audioPlaybackSpeed");
    this.isListening = false;
    this.recognition = null;

    // Playlist state for continuous section-by-section broadcast
    this.playlist = [];
    this.currentIndex = -1;
    this.onSectionChangeCallback = null;
    this.currentBlobUrl = null;

    this.initSTT();
    this.initAudioEvents();
  }

  initAudioEvents() {
    const btnClose = document.getElementById("btnCloseAudio");
    if (btnClose) {
      btnClose.addEventListener("click", () => {
        this.stopAudio();
        this.banner.classList.add("hidden");
      });
    }

    const btnNext = document.getElementById("btnNextSectionAudio");
    if (btnNext) {
      btnNext.addEventListener("click", () => this.nextSection());
    }

    const btnPrev = document.getElementById("btnPrevSectionAudio");
    if (btnPrev) {
      btnPrev.addEventListener("click", () => this.prevSection());
    }

    if (this.speedSelect) {
      this.speedSelect.addEventListener("change", (e) => {
        const speed = parseFloat(e.target.value);
        if (this.audioPlayer) this.audioPlayer.playbackRate = speed;
      });
    }

    if (this.audioPlayer) {
      this.audioPlayer.addEventListener("ended", () => {
        if (this.playlist.length > 0 && this.currentIndex >= 0 && this.currentIndex < this.playlist.length - 1) {
          // Automatically advance to the next section!
          this.nextSection();
        } else if (this.playlist.length > 0 && this.currentIndex >= this.playlist.length - 1) {
          if (this.sectionTracker) {
            this.sectionTracker.textContent = "✓ Briefing Complete";
          }
        }
      });
    }
  }

  /**
   * Start continuous broadcast covering every section sequentially
   */
  async playAllSections(sectionsList, onSectionChange = null) {
    if (!sectionsList || sectionsList.length === 0) {
      alert("No news sections available to broadcast. Run ingestion first.");
      return;
    }

    this.playlist = sectionsList;
    this.currentIndex = 0;
    this.onSectionChangeCallback = onSectionChange;

    if (this.sectionTracker) this.sectionTracker.classList.remove("hidden");
    await this.playCurrentSection();
  }

  async playCurrentSection() {
    if (this.currentIndex < 0 || this.currentIndex >= this.playlist.length) return;

    const item = this.playlist[this.currentIndex];
    const total = this.playlist.length;
    const speed = this.speedSelect ? parseFloat(this.speedSelect.value) : 1.0;

    if (this.sectionTracker) {
      this.sectionTracker.textContent = `Section ${this.currentIndex + 1} of ${total}`;
    }

    const titleText = `${item.icon || "📰"} ${item.title} (${item.storiesCount || item.items?.length || 0} stories)`;
    
    // Notify caller to switch UI active tab to this section
    if (this.onSectionChangeCallback && item.id) {
      this.onSectionChangeCallback(item.id);
    }

    await this.playNaturalSpeech(item.script, titleText, speed);
  }

  nextSection() {
    if (this.currentIndex < this.playlist.length - 1) {
      this.currentIndex++;
      this.playCurrentSection();
    }
  }

  prevSection() {
    if (this.currentIndex > 0) {
      this.currentIndex--;
      this.playCurrentSection();
    }
  }

  /**
   * Play text as natural broadcast audio synthesized via FastAPI Edge-TTS
   */
  async playNaturalSpeech(text, title = "Intelligence Audio Briefing", playbackSpeed = 1.0) {
    if (!text || !text.trim()) return;

    this.banner.classList.remove("hidden");
    this.bannerTitle.textContent = title;

    try {
      const resp = await fetch("/api/voice/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });

      if (!resp.ok) throw new Error("TTS generation failed");

      if (this.currentBlobUrl) {
        URL.revokeObjectURL(this.currentBlobUrl);
      }

      const blob = await resp.blob();
      this.currentBlobUrl = URL.createObjectURL(blob);

      this.audioPlayer.src = this.currentBlobUrl;
      this.audioPlayer.playbackRate = this.speedSelect ? parseFloat(this.speedSelect.value) : playbackSpeed;
      await this.audioPlayer.play();
    } catch (err) {
      console.warn("Backend TTS playback failed, fallback to Web Speech API:", err);
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.rate = this.speedSelect ? parseFloat(this.speedSelect.value) : 1.1;
        utter.pitch = 1.0;
        utter.onend = () => {
          if (this.playlist.length > 0 && this.currentIndex < this.playlist.length - 1) {
            this.nextSection();
          }
        };
        window.speechSynthesis.speak(utter);
      }
    }
  }

  stopAudio() {
    this.playlist = [];
    this.currentIndex = -1;
    if (this.audioPlayer) {
      this.audioPlayer.pause();
      this.audioPlayer.currentTime = 0;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }

  /**
   * Initialize Web Speech Recognition for voice commands & voice search
   */
  initSTT() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = false;
    this.recognition.lang = "en-US";
  }

  startListening(onResult, onStatusChange) {
    if (!this.recognition) {
      alert("Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    if (this.isListening) {
      this.recognition.stop();
      this.isListening = false;
      if (onStatusChange) onStatusChange(false);
      return;
    }

    this.isListening = true;
    if (onStatusChange) onStatusChange(true);

    this.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      this.isListening = false;
      if (onStatusChange) onStatusChange(false);
      if (onResult) onResult(transcript);
    };

    this.recognition.onerror = (err) => {
      console.warn("Speech recognition error:", err);
      this.isListening = false;
      if (onStatusChange) onStatusChange(false);
    };

    this.recognition.onend = () => {
      this.isListening = false;
      if (onStatusChange) onStatusChange(false);
    };

    try {
      this.recognition.start();
    } catch (e) {
      console.warn("Could not start recognition:", e);
      this.isListening = false;
      if (onStatusChange) onStatusChange(false);
    }
  }
}

window.voiceEngine = new VoiceEngine();

