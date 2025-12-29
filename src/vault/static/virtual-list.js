/** @file virtual-list.js - Virtual scrolling for large file/folder lists */

// Helper function to safely clear an element without using innerHTML
function clearElement(element) {
  if (!element) return;
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

class VirtualList {
  constructor(container, options = {}) {
    this.container = container;
    this.itemHeight = options.itemHeight || 80; // Height of each item in list view
    this.gridItemHeight = options.gridItemHeight || 200; // Height of grid items
    this.gridItemWidth = options.gridItemWidth || 180;
    this.overscan = options.overscan || 5; // Number of items to render outside viewport
    this.viewMode = options.viewMode || "grid"; // 'grid' or 'list'

    this.items = [];
    this.scrollTop = 0;
    this.containerHeight = 0;
    this.visibleItems = [];
    this.startIndex = 0;
    this.endIndex = 0;

    this.init();
  }

  init() {
    // Setup container
    this.container.style.position = "relative";
    this.container.style.overflow = "auto";

    // Create viewport
    this.viewport = document.createElement("div");
    this.viewport.className = "virtual-list-viewport";
    this.viewport.style.position = "relative";

    // Create spacer for items before viewport
    this.spacerBefore = document.createElement("div");
    this.spacerBefore.className = "virtual-list-spacer-before";

    // Create item container
    this.itemContainer = document.createElement("div");
    this.itemContainer.className = "virtual-list-items";

    // Create spacer for items after viewport
    this.spacerAfter = document.createElement("div");
    this.spacerAfter.className = "virtual-list-spacer-after";

    this.viewport.appendChild(this.spacerBefore);
    this.viewport.appendChild(this.itemContainer);
    this.viewport.appendChild(this.spacerAfter);

    // Clear container and add viewport
    clearElement(this.container);
    this.container.appendChild(this.viewport);

    // Setup scroll listener
    this.container.addEventListener("scroll", () => this.handleScroll());

    // Setup resize observer
    this.resizeObserver = new ResizeObserver(() => this.update());
    this.resizeObserver.observe(this.container);

    // Initial update
    this.update();
  }

  /**
   * Set items
   */
  setItems(items) {
    this.items = items;
    this.update();
  }

  /**
   * Set view mode
   */
  setViewMode(mode) {
    this.viewMode = mode;
    this.update();
  }

  /**
   * Handle scroll
   */
  handleScroll() {
    this.scrollTop = this.container.scrollTop;
    this.updateVisibleItems();
  }

  /**
   * Calculate visible range
   */
  calculateVisibleRange() {
    const itemHeight =
      this.viewMode === "list" ? this.itemHeight : this.gridItemHeight;
    const containerHeight = this.container.clientHeight || this.containerHeight;

    let itemsPerRow = 1;
    if (this.viewMode === "grid") {
      const containerWidth = this.container.clientWidth || 800;
      itemsPerRow = Math.floor(containerWidth / this.gridItemWidth);
      itemsPerRow = Math.max(1, itemsPerRow);
    }

    const startIndex = Math.max(
      0,
      Math.floor(this.scrollTop / itemHeight) - this.overscan,
    );
    const visibleCount = Math.ceil(containerHeight / itemHeight);
    const endIndex = Math.min(
      this.items.length,
      startIndex + visibleCount + this.overscan * 2,
    );

    return { startIndex, endIndex, itemsPerRow };
  }

  /**
   * Update visible items
   */
  updateVisibleItems() {
    const { startIndex, endIndex, itemsPerRow } = this.calculateVisibleRange();

    this.startIndex = startIndex;
    this.endIndex = endIndex;

    // Adjust for grid view
    const adjustedStartIndex =
      this.viewMode === "grid"
        ? Math.floor(startIndex / itemsPerRow) * itemsPerRow
        : startIndex;

    const adjustedEndIndex =
      this.viewMode === "grid"
        ? Math.ceil(endIndex / itemsPerRow) * itemsPerRow
        : endIndex;

    // Get visible items
    this.visibleItems = this.items.slice(adjustedStartIndex, adjustedEndIndex);

    const itemHeight =
      this.viewMode === "list" ? this.itemHeight : this.gridItemHeight;
    const spacerBeforeHeight = adjustedStartIndex * itemHeight;
    const spacerAfterHeight =
      (this.items.length - adjustedEndIndex) * itemHeight;

    this.spacerBefore.style.height = `${spacerBeforeHeight}px`;
    this.spacerAfter.style.height = `${spacerAfterHeight}px`;

    this.renderItems();
  }

  /**
   * Render visible items
   */
  renderItems() {
    const { startIndex, endIndex, itemsPerRow } = this.calculateVisibleRange();

    // Adjust for grid
    const adjustedStartIndex =
      this.viewMode === "grid"
        ? Math.floor(startIndex / itemsPerRow) * itemsPerRow
        : startIndex;

    // Clear container
    clearElement(this.itemContainer);

    if (this.viewMode === "grid") {
      this.renderGrid(adjustedStartIndex, endIndex, itemsPerRow);
    } else {
      this.renderList(adjustedStartIndex, endIndex);
    }
  }

  /**
   * Render grid view
   */
  renderGrid(startIndex, endIndex, itemsPerRow) {
    const gridContainer = document.createElement("div");
    gridContainer.className = "virtual-list-grid";
    gridContainer.style.display = "grid";
    gridContainer.style.gridTemplateColumns = `repeat(${itemsPerRow}, ${this.gridItemWidth}px)`;
    gridContainer.style.gap = "var(--space-4)";

    for (let i = startIndex; i < endIndex && i < this.items.length; i++) {
      const item = this.items[i];
      const itemElement = this.createItemElement(item, i);
      gridContainer.appendChild(itemElement);
    }

    if (window.vaultHTMLPolicy) {
      try {
        this.itemContainer.innerHTML = window.vaultHTMLPolicy.createHTML(
          gridContainer.outerHTML,
        );
      } catch (e) {
        this.itemContainer.appendChild(gridContainer);
      }
    } else {
      this.itemContainer.appendChild(gridContainer);
    }
  }

  /**
   * Render list view
   */
  renderList(startIndex, endIndex) {
    for (let i = startIndex; i < endIndex && i < this.items.length; i++) {
      const item = this.items[i];
      const itemElement = this.createItemElement(item, i);
      this.itemContainer.appendChild(itemElement);
    }
  }

  /**
   * Create item element
   */
  createItemElement(item, index) {
    // This will be overridden by the caller

    const element = document.createElement("div");
    element.className = "virtual-list-item";
    element.style.height =
      this.viewMode === "list"
        ? `${this.itemHeight}px`
        : `${this.gridItemHeight}px`;
    element.dataset.index = index;
    return element;
  }

  /**
   * Set item renderer
   */
  setItemRenderer(renderer) {
    this.itemRenderer = renderer;
  }

  /**
   * Update
   */
  update() {
    this.containerHeight = this.container.clientHeight || this.containerHeight;
    this.updateVisibleItems();
  }

  /**
   * Scroll to index
   */
  scrollToIndex(index) {
    const itemHeight =
      this.viewMode === "list" ? this.itemHeight : this.gridItemHeight;
    const scrollTop = index * itemHeight;
    this.container.scrollTop = scrollTop;
    this.updateVisibleItems();
  }

  /**
   * Get visible items
   */
  getVisibleItems() {
    return this.visibleItems;
  }

  /**
   * Get total height
   */
  getTotalHeight() {
    const itemHeight =
      this.viewMode === "list" ? this.itemHeight : this.gridItemHeight;
    return this.items.length * itemHeight;
  }

  /**
   * Destroy
   */
  destroy() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    this.container.removeEventListener("scroll", this.handleScroll);
  }
}

// Virtual list manager for files and folders
class VirtualListManager {
  constructor() {
    this.virtualLists = new Map();
  }

  /**
   * Create virtual list for container
   */
  createList(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return null;

    const virtualList = new VirtualList(container, options);
    this.virtualLists.set(containerId, virtualList);
    return virtualList;
  }

  /**
   * Get virtual list
   */
  getList(containerId) {
    return this.virtualLists.get(containerId);
  }

  /**
   * Destroy virtual list
   */
  destroyList(containerId) {
    const list = this.virtualLists.get(containerId);
    if (list) {
      list.destroy();
      this.virtualLists.delete(containerId);
    }
  }
}

let virtualListManager = null;

document.addEventListener("DOMContentLoaded", () => {
  virtualListManager = new VirtualListManager();

  if (typeof window !== "undefined") {
    window.VirtualList = VirtualList;
    window.VirtualListManager = VirtualListManager;
    window.virtualListManager = virtualListManager;
  }
});

if (typeof window !== "undefined") {
  window.VirtualList = VirtualList;
  window.VirtualListManager = VirtualListManager;
}
