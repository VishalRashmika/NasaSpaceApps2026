/**
 * UI Shell: layout, theme toggle, tabs, and error alerts (F-070).
 */

export class ShellUI {
  constructor() {
    this.themeToggleBtn = document.getElementById("theme-toggle");
    this.errorAlert = document.getElementById("error-alert");
    this.errorMessage = this.errorAlert ? this.errorAlert.querySelector(".alert-message") : null;
    this.dismissErrorBtn = document.getElementById("btn-dismiss-error");
    this.qualityBadge = document.getElementById("quality-badge");
    this.fallbackBanner = document.getElementById("fallback-banner");

    this.tabButtons = Array.from(document.querySelectorAll(".sidebar-pane .tab-btn"));
    this.tabPanels = Array.from(document.querySelectorAll(".sidebar-pane .tab-panel"));

    this._initTheme();
    this._initTabs();
    this._initAlerts();
  }

  _initTheme() {
    let savedTheme = "light";
    try {
      const stored = localStorage.getItem("earth-jukebox-theme");
      if (stored === "dark" || stored === "light") {
        savedTheme = stored;
      }
    } catch {
      // localStorage unavailable
    }

    document.documentElement.setAttribute("data-theme", savedTheme);

    if (this.themeToggleBtn) {
      this.themeToggleBtn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        try {
          localStorage.setItem("earth-jukebox-theme", next);
        } catch {
          // ignore
        }
      });
    }
  }

  _initTabs() {
    this.tabButtons.forEach((btn, idx) => {
      btn.addEventListener("click", () => this.selectTab(btn.id));

      // ARIA keyboard navigation for tablist
      btn.addEventListener("keydown", (e) => {
        let targetIdx = null;
        if (e.key === "ArrowRight") {
          targetIdx = (idx + 1) % this.tabButtons.length;
        } else if (e.key === "ArrowLeft") {
          targetIdx = (idx - 1 + this.tabButtons.length) % this.tabButtons.length;
        } else if (e.key === "Home") {
          targetIdx = 0;
        } else if (e.key === "End") {
          targetIdx = this.tabButtons.length - 1;
        }

        if (targetIdx !== null) {
          e.preventDefault();
          const targetBtn = this.tabButtons[targetIdx];
          targetBtn.focus();
          this.selectTab(targetBtn.id);
        }
      });
    });
  }

  selectTab(tabId) {
    this.tabButtons.forEach((btn) => {
      const isSelected = btn.id === tabId;
      btn.setAttribute("aria-selected", String(isSelected));
      btn.classList.toggle("active", isSelected);

      const panelId = btn.getAttribute("aria-controls");
      const panel = document.getElementById(panelId);
      if (panel) {
        panel.classList.toggle("hidden", !isSelected);
        panel.classList.toggle("active", isSelected);
      }
    });
  }

  _initAlerts() {
    if (this.dismissErrorBtn) {
      this.dismissErrorBtn.addEventListener("click", () => this.hideError());
    }
  }

  showError(msg) {
    if (this.errorMessage) {
      this.errorMessage.textContent = msg;
    }
    if (this.errorAlert) {
      this.errorAlert.classList.remove("hidden");
    }
  }

  hideError() {
    if (this.errorAlert) {
      this.errorAlert.classList.add("hidden");
    }
  }

  setQualityBadge(confidence, badge) {
    if (!this.qualityBadge) return;
    this.qualityBadge.className = "quality-badge";
    const b = (badge || "neutral").toLowerCase();
    this.qualityBadge.classList.add(`badge-${b}`);
    if (typeof confidence === "number") {
      this.qualityBadge.textContent = `${badge} (${(confidence * 100).toFixed(1)}%)`;
    } else {
      this.qualityBadge.textContent = badge || "No analysis";
    }
  }

  setFallbackBannerVisible(visible) {
    if (this.fallbackBanner) {
      this.fallbackBanner.classList.toggle("hidden", !visible);
    }
  }
}
