/**
 * Time mode UI component (F-093).
 *
 * Renders an accessible frame strip with synced highlight and seeking.
 */

export class TimeModeUI {
  /**
   * @param {object} options
   * @param {HTMLElement|null} [options.container]
   * @param {(frameIndex: number) => void} [options.onSelectFrame]
   */
  constructor({ container = null, onSelectFrame = () => {} } = {}) {
    this.container = container || document.getElementById("time-mode-strip");
    this.onSelectFrame = onSelectFrame;
    this.currentIndex = 0;
    this.totalFrames = 0;
    this.buttons = [];
  }

  /**
   * Render frame thumbnails or chips in the strip.
   *
   * @param {string[]} framePreviews Array of base64 PNG data URLs
   * @param {(frameIndex: number) => void} [onSelectFrame]
   */
  renderFrames(framePreviews, onSelectFrame) {
    if (onSelectFrame) {
      this.onSelectFrame = onSelectFrame;
    }

    if (!this.container) return;

    if (!framePreviews || framePreviews.length <= 1) {
      this.clear();
      return;
    }

    this.totalFrames = framePreviews.length;
    this.currentIndex = 0;
    this.container.innerHTML = "";
    this.container.classList.remove("hidden");
    this.container.setAttribute("aria-hidden", "false");

    const header = document.createElement("div");
    header.className = "frame-strip-header";

    const title = document.createElement("span");
    title.id = "frame-strip-heading";
    title.className = "frame-strip-title";
    title.textContent = `Time Mode: ${this.totalFrames} Frames`;
    header.appendChild(title);

    const statusBadge = document.createElement("span");
    statusBadge.id = "frame-status-badge";
    statusBadge.className = "frame-status-badge";
    statusBadge.textContent = "Frame 1";
    header.appendChild(statusBadge);

    this.container.appendChild(header);

    const list = document.createElement("div");
    list.className = "frame-strip-list";
    list.setAttribute("role", "tablist");
    list.setAttribute("aria-labelledby", "frame-strip-heading");

    this.buttons = [];

    framePreviews.forEach((previewUrl, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `frame-thumb-btn ${idx === 0 ? "active" : ""}`;
      btn.setAttribute("role", "tab");
      btn.id = `frame-tab-${idx}`;
      btn.setAttribute("aria-selected", idx === 0 ? "true" : "false");
      btn.setAttribute("aria-label", `Frame ${idx + 1} of ${this.totalFrames}`);
      btn.dataset.frameIndex = String(idx);

      if (previewUrl) {
        const img = document.createElement("img");
        img.src = previewUrl;
        img.alt = "";
        img.className = "frame-thumb-img";
        btn.appendChild(img);
      }

      const badge = document.createElement("span");
      badge.className = "frame-thumb-num";
      badge.textContent = `F${idx + 1}`;
      btn.appendChild(badge);

      btn.addEventListener("click", () => {
        this.setActiveFrame(idx, false);
        if (this.onSelectFrame) {
          this.onSelectFrame(idx);
        }
      });

      // Keyboard arrow navigation
      btn.addEventListener("keydown", (e) => {
        let targetIdx = -1;
        if (e.key === "ArrowRight") {
          targetIdx = Math.min(this.totalFrames - 1, idx + 1);
        } else if (e.key === "ArrowLeft") {
          targetIdx = Math.max(0, idx - 1);
        } else if (e.key === "Home") {
          targetIdx = 0;
        } else if (e.key === "End") {
          targetIdx = this.totalFrames - 1;
        }

        if (targetIdx >= 0 && targetIdx !== idx) {
          e.preventDefault();
          const targetBtn = this.buttons[targetIdx];
          if (targetBtn) {
            targetBtn.focus();
            targetBtn.click();
          }
        }
      });

      this.buttons.push(btn);
      list.appendChild(btn);
    });

    this.container.appendChild(list);
  }

  /**
   * Updates visual highlight on the active frame.
   *
   * @param {number} frameIndex
   * @param {boolean} [isRest=false]
   */
  setActiveFrame(frameIndex, isRest = false) {
    if (this.buttons.length === 0) return;
    this.currentIndex = Math.max(0, Math.min(this.totalFrames - 1, frameIndex));

    this.buttons.forEach((btn, idx) => {
      const isActive = idx === this.currentIndex;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
      if (isActive && !isRest) {
        btn.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    });

    const statusBadge = document.getElementById("frame-status-badge");
    if (statusBadge) {
      if (isRest) {
        statusBadge.textContent = `Rest (Between Frames)`;
      } else {
        statusBadge.textContent = `Frame ${this.currentIndex + 1} of ${this.totalFrames}`;
      }
    }
  }

  /**
   * Hide and reset the frame strip.
   */
  clear() {
    this.totalFrames = 0;
    this.currentIndex = 0;
    this.buttons = [];
    if (this.container) {
      this.container.innerHTML = "";
      this.container.classList.add("hidden");
      this.container.setAttribute("aria-hidden", "true");
    }
  }
}
