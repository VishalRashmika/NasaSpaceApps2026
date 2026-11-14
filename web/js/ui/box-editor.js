/**
 * Canvas Map Display and Box Overlay Editor (F-072, F-073).
 */

export class BoxEditorUI {
  constructor() {
    this.canvas = document.getElementById("map-canvas");
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.container = document.getElementById("canvas-container");
    this.playheadLine = document.getElementById("playhead-line");
    this.overlayCBox = document.getElementById("overlay-cbox");
    this.overlayMBox = document.getElementById("overlay-mbox");
    this.readoutValue = document.getElementById("readout-value");

    this.cboxX = document.getElementById("cbox-x");
    this.cboxY = document.getElementById("cbox-y");
    this.cboxW = document.getElementById("cbox-w");
    this.cboxH = document.getElementById("cbox-h");

    this.currentImage = null;
    this.imageNaturalWidth = 800;
    this.imageNaturalHeight = 400;

    this.colorbarBox = null;
    this.mapBox = null;

    this._initInputs();
    this._initResizeHandling();
  }

  _initInputs() {
    const onInput = () => {
      const x = Number(this.cboxX?.value || 0);
      const y = Number(this.cboxY?.value || 0);
      const w = Number(this.cboxW?.value || 0);
      const h = Number(this.cboxH?.value || 0);

      if (w > 0 && h > 0) {
        this.colorbarBox = { x, y, w, h };
      } else {
        this.colorbarBox = null;
      }
      this.updateOverlays();
    };

    [this.cboxX, this.cboxY, this.cboxW, this.cboxH].forEach((el) => {
      if (el) el.addEventListener("input", onInput);
    });
  }

  _initResizeHandling() {
    if (typeof window !== "undefined") {
      window.addEventListener("resize", () => {
        this.updateOverlays();
      });
      if (typeof ResizeObserver !== "undefined" && this.container) {
        this.resizeObserver = new ResizeObserver(() => {
          this.updateOverlays();
        });
        this.resizeObserver.observe(this.container);
      }
    }
  }

  async loadImage(srcOrBlob) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this.currentImage = img;
        this.imageNaturalWidth = img.naturalWidth || img.width;
        this.imageNaturalHeight = img.naturalHeight || img.height;

        if (this.canvas && this.ctx) {
          this.canvas.width = this.imageNaturalWidth;
          this.canvas.height = this.imageNaturalHeight;
          this.ctx.drawImage(img, 0, 0);
        }
        this.updateOverlays();
        resolve({ width: this.imageNaturalWidth, height: this.imageNaturalHeight });
      };
      img.onerror = reject;

      if (typeof srcOrBlob === "string") {
        img.src = srcOrBlob;
      } else if (srcOrBlob instanceof Blob) {
        img.src = URL.createObjectURL(srcOrBlob);
      }
    });
  }

  setBoxes({ colorbarBox, mapBox }) {
    this.colorbarBox = colorbarBox || null;
    this.mapBox = mapBox || null;

    if (this.colorbarBox) {
      if (this.cboxX) this.cboxX.value = String(Math.round(this.colorbarBox.x));
      if (this.cboxY) this.cboxY.value = String(Math.round(this.colorbarBox.y));
      if (this.cboxW) this.cboxW.value = String(Math.round(this.colorbarBox.w));
      if (this.cboxH) this.cboxH.value = String(Math.round(this.colorbarBox.h));
    } else {
      if (this.cboxX) this.cboxX.value = "";
      if (this.cboxY) this.cboxY.value = "";
      if (this.cboxW) this.cboxW.value = "";
      if (this.cboxH) this.cboxH.value = "";
    }

    this.updateOverlays();
  }

  updateOverlays() {
    if (!this.canvas || this.imageNaturalWidth <= 0 || this.imageNaturalHeight <= 0) {
      return;
    }

    const rect = this.canvas.getBoundingClientRect();
    const containerRect = this.container ? this.container.getBoundingClientRect() : rect;
    const offsetX = rect.left - containerRect.left;
    const offsetY = rect.top - containerRect.top;

    const scaleX = rect.width / this.imageNaturalWidth;
    const scaleY = rect.height / this.imageNaturalHeight;

    if (this.colorbarBox && this.overlayCBox) {
      this.overlayCBox.classList.remove("hidden");
      this.overlayCBox.style.left = `${offsetX + this.colorbarBox.x * scaleX}px`;
      this.overlayCBox.style.top = `${offsetY + this.colorbarBox.y * scaleY}px`;
      this.overlayCBox.style.width = `${this.colorbarBox.w * scaleX}px`;
      this.overlayCBox.style.height = `${this.colorbarBox.h * scaleY}px`;
    } else if (this.overlayCBox) {
      this.overlayCBox.classList.add("hidden");
    }

    if (this.mapBox && this.overlayMBox) {
      this.overlayMBox.classList.remove("hidden");
      this.overlayMBox.style.left = `${offsetX + this.mapBox.x * scaleX}px`;
      this.overlayMBox.style.top = `${offsetY + this.mapBox.y * scaleY}px`;
      this.overlayMBox.style.width = `${this.mapBox.w * scaleX}px`;
      this.overlayMBox.style.height = `${this.mapBox.h * scaleY}px`;
    } else if (this.overlayMBox) {
      this.overlayMBox.classList.add("hidden");
    }
  }

  setPlayheadPosition(pixelX) {
    if (!this.playheadLine || !this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const containerRect = this.container ? this.container.getBoundingClientRect() : rect;
    const offsetX = rect.left - containerRect.left;
    this.playheadLine.style.display = "block";
    this.playheadLine.style.left = `${offsetX + pixelX}px`;
  }

  hidePlayhead() {
    if (this.playheadLine) {
      this.playheadLine.style.display = "none";
    }
  }

  setReadout(text) {
    if (this.readoutValue) {
      this.readoutValue.textContent = text;
    }
  }

  getMapBounds() {
    if (!this.canvas) return { left: 0, width: 800 };
    const rect = this.canvas.getBoundingClientRect();
    return {
      left: 0,
      width: rect.width || this.canvas.clientWidth || 800,
    };
  }
}
