/**
 * Jukebox Gallery component (F-071, F-107).
 * Renders bundled samples or scenes from the active NASA dataset category.
 */

import { getSamples, getSampleImageUrl } from "../api/client.js";

export class GalleryUI {
  /**
   * @param {HTMLElement} container
   * @param {(sampleId: string) => void} onSelect
   */
  constructor(container, onSelect) {
    this.container = container;
    this.emptyEl = document.getElementById("gallery-empty");
    this.panelHeading = document.getElementById("gallery-panel-heading");
    this.panelIntro = document.getElementById("gallery-panel-intro");
    this.onSelect = onSelect;
    this.samples = [];
    this.selectedId = null;
    this.activeCategory = null;
    this.onSelectCategoryExample = null;
    this.onBrowseCategories = null;
  }

  async load() {
    try {
      this.samples = await getSamples();
    } catch {
      this.samples = [];
    }
    this.render();
  }

  /**
   * Update gallery with scenes from the active category.
   *
   * @param {object} category
   * @param {(image: object) => void} onSelectExample
   * @param {() => void} [onBrowseCategories]
   */
  setCategory(category, onSelectExample, onBrowseCategories) {
    this.activeCategory = category;
    this.onSelectCategoryExample = onSelectExample;
    if (onBrowseCategories) {
      this.onBrowseCategories = onBrowseCategories;
    }
    this.render();
  }

  render() {
    if (!this.container) return;

    // Check if we have bundled samples from /api/samples
    const hasBundledSamples = Array.isArray(this.samples) && this.samples.length > 0;
    // Check if we have scenes from the active category
    const categoryImages =
      this.activeCategory && Array.isArray(this.activeCategory.images)
        ? this.activeCategory.images
        : [];
    const hasCategoryScenes = categoryImages.length > 0;

    if (!hasBundledSamples && !hasCategoryScenes) {
      if (this.emptyEl) {
        this.emptyEl.classList.remove("hidden");
        this.emptyEl.textContent =
          "No observations currently selected. Choose an authentic NASA observation from the catalog or upload your own scientific map.";
      }
      if (this.panelHeading) {
        this.panelHeading.textContent = "NASA Dataset Observations";
      }
      if (this.panelIntro) {
        this.panelIntro.textContent =
          "Select an authentic NASA observation from the catalog or upload your own image.";
      }
      const existingCards = this.container.querySelectorAll(
        ".sample-card, .gallery-category-header, .gallery-action-wrap"
      );
      existingCards.forEach((c) => c.remove());

      if (this.onBrowseCategories) {
        const actionWrap = document.createElement("div");
        actionWrap.className = "gallery-action-wrap";
        const browseBtn = document.createElement("button");
        browseBtn.type = "button";
        browseBtn.className = "btn btn-primary btn-block";
        browseBtn.id = "btn-gallery-browse-all";
        browseBtn.textContent = "← Choose NASA Observation";
        browseBtn.addEventListener("click", () => this.onBrowseCategories());
        actionWrap.appendChild(browseBtn);
        this.container.appendChild(actionWrap);
      }
      return;
    }

    if (this.emptyEl) {
      this.emptyEl.classList.add("hidden");
    }

    if (this.activeCategory && this.panelHeading) {
      this.panelHeading.textContent = `Observations: ${this.activeCategory.title}`;
    }
    if (this.activeCategory && this.panelIntro) {
      this.panelIntro.textContent =
        "Choose an observation scene to sonify in this dataset, or switch datasets below:";
    }

    // Clear existing cards
    const existingCards = this.container.querySelectorAll(
      ".sample-card, .gallery-category-header, .gallery-action-wrap"
    );
    existingCards.forEach((c) => c.remove());

    if (hasBundledSamples) {
      this._renderSampleCards(this.samples);
    } else if (hasCategoryScenes) {
      this._renderCategorySceneCards(categoryImages);
    }
  }

  _renderSampleCards(samples) {
    samples.forEach((s, idx) => {
      const card = document.createElement("div");
      card.className = "sample-card";
      card.setAttribute("role", "radio");
      card.setAttribute("tabindex", idx === 0 ? "0" : "-1");
      card.setAttribute("aria-checked", "false");
      card.dataset.id = s.id;

      const thumb = document.createElement("img");
      thumb.className = "sample-thumb";
      thumb.src = s.thumb_url || getSampleImageUrl(s.id);
      thumb.alt = s.title || s.id;
      thumb.loading = "lazy";

      const info = document.createElement("div");
      info.className = "sample-info";

      const title = document.createElement("p");
      title.className = "sample-title";
      title.textContent = s.title || s.id;

      const chip = document.createElement("span");
      chip.className = "sample-chip";
      chip.textContent = s.category || "Earth";

      info.appendChild(title);
      info.appendChild(chip);

      card.appendChild(thumb);
      card.appendChild(info);

      card.addEventListener("click", () => this.select(s.id));
      this._attachKeyNav(card, idx);

      this.container.appendChild(card);
    });
  }

  _renderCategorySceneCards(images) {
    // Header showing active dataset
    const header = document.createElement("div");
    header.className = "gallery-category-header";
    header.innerHTML = `
      <div class="gallery-cat-info">
        <span class="gallery-cat-label">Dataset:</span>
        <strong class="gallery-cat-title">${this.activeCategory.title}</strong>
      </div>
      <span class="gallery-cat-count">${images.length} scene${images.length === 1 ? "" : "s"}</span>
    `;
    this.container.appendChild(header);

    images.forEach((img, idx) => {
      const isSelected = this.selectedId === img.filename || (this.selectedId === null && idx === 0);
      const card = document.createElement("div");
      card.className = `sample-card ${isSelected ? "selected" : ""}`;
      card.setAttribute("role", "radio");
      card.setAttribute("tabindex", isSelected ? "0" : "-1");
      card.setAttribute("aria-checked", String(isSelected));
      card.dataset.id = img.filename;

      const thumb = document.createElement("img");
      thumb.className = "sample-thumb";
      thumb.src = img.thumb_url;
      thumb.alt = img.title || img.filename;
      thumb.loading = "lazy";

      const info = document.createElement("div");
      info.className = "sample-info";

      const title = document.createElement("p");
      title.className = "sample-title";
      title.textContent = img.title || img.filename;

      const chip = document.createElement("span");
      chip.className = "sample-chip";
      chip.textContent = img.filename;

      info.appendChild(title);
      info.appendChild(chip);

      card.appendChild(thumb);
      card.appendChild(info);

      card.addEventListener("click", () => {
        this.selectScene(img);
      });
      this._attachKeyNav(card, idx, () => this.selectScene(img));

      this.container.appendChild(card);
    });

    if (this.onBrowseCategories) {
      const actionWrap = document.createElement("div");
      actionWrap.className = "gallery-action-wrap";
      const browseBtn = document.createElement("button");
      browseBtn.type = "button";
      browseBtn.className = "btn btn-sm btn-secondary btn-block";
      browseBtn.id = "btn-gallery-browse-all";
      browseBtn.textContent = "← Browse All NASA Datasets";
      browseBtn.addEventListener("click", () => this.onBrowseCategories());
      actionWrap.appendChild(browseBtn);
      this.container.appendChild(actionWrap);
    }
  }

  _attachKeyNav(card, idx, onSelectAction = null) {
    card.addEventListener("keydown", (e) => {
      const cards = Array.from(this.container.querySelectorAll(".sample-card"));
      let targetIdx = null;

      if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        targetIdx = (idx + 1) % cards.length;
      } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        targetIdx = (idx - 1 + cards.length) % cards.length;
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (onSelectAction) {
          onSelectAction();
        } else {
          this.select(card.dataset.id);
        }
        return;
      }

      if (targetIdx !== null) {
        e.preventDefault();
        cards.forEach((c) => c.setAttribute("tabindex", "-1"));
        const target = cards[targetIdx];
        target.setAttribute("tabindex", "0");
        target.focus();
      }
    });
  }

  select(id) {
    this.selectedId = id;
    const cards = Array.from(this.container.querySelectorAll(".sample-card"));
    cards.forEach((c) => {
      const isSel = c.dataset.id === id;
      c.classList.toggle("selected", isSel);
      c.setAttribute("aria-checked", String(isSel));
      if (isSel) {
        c.setAttribute("tabindex", "0");
      }
    });

    if (this.onSelect) {
      this.onSelect(id);
    }
  }

  selectScene(img) {
    this.selectedId = img.filename;
    const cards = Array.from(this.container.querySelectorAll(".sample-card"));
    cards.forEach((c) => {
      const isSel = c.dataset.id === img.filename;
      c.classList.toggle("selected", isSel);
      c.setAttribute("aria-checked", String(isSel));
      if (isSel) {
        c.setAttribute("tabindex", "0");
      }
    });

    if (this.onSelectCategoryExample) {
      this.onSelectCategoryExample(img);
    }
  }
}
