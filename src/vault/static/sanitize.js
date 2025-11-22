/** @file sanitize.js - HTML sanitization utilities for XSS prevention */

/**
 * Strict HTML sanitizer that removes all potentially dangerous content.
 * This is intentionally very restrictive - when in doubt, it removes content.
 *
 * Based on the approach: only allow known-safe tags and attributes, deny everything else.
 *
 * @param {string} html - The HTML string to sanitize
 * @returns {string} - The sanitized HTML string
 */
function sanitizeHTML(html) {
  if (!html || typeof html !== "string") {
    return "";
  }

  // Create a temporary DOM element to parse the HTML
  const temp = document.createElement("div");
  temp.innerHTML = html;

  // Allowed tags (very restrictive list)
  const allowedTags = new Set([
    "div",
    "span",
    "p",
    "br",
    "button",
    "label",
    "svg",
    "path",
    "circle",
    "rect",
    "line",
    "polyline",
    "polygon",
    "ellipse",
    "g",
    "defs",
    "clippath",
    "mask",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "a",
    "img",
  ]);

  // Allowed attributes (whitelist approach)
  const allowedAttributes = new Set([
    "class",
    "id",
    "style",
    "data-file-id",
    "data-folder-id",
    "data-id",
    "data-icon",
    "data-metric-value",
    "title",
    "alt",
    "aria-label",
    "aria-hidden",
    "aria-expanded",
    "aria-controls",
    "role",
    "tabindex",
    "type",
    "disabled",
    "readonly",
    "checked",
    "selected",
    "href",
    "target",
    "rel",
    "src",
    "width",
    "height",
    // SVG specific attributes
    "viewBox",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "d",
    "cx",
    "cy",
    "r",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "points",
    "transform",
    "xmlns",
  ]);

  // Dangerous attribute patterns
  const dangerousAttributePatterns = [
    /^on/i, // onclick, onerror, onload, etc.
    /^formaction$/i,
    /^action$/i,
    /^srcdoc$/i,
  ];

  /**
   * Check if an attribute is safe
   */
  function isAttributeSafe(attrName, attrValue) {
    const lowerAttrName = attrName.toLowerCase();

    // Check against dangerous patterns
    for (const pattern of dangerousAttributePatterns) {
      if (pattern.test(lowerAttrName)) {
        return false;
      }
    }

    // Check if attribute is in allowed list (or starts with data-)
    if (
      !allowedAttributes.has(lowerAttrName) &&
      !lowerAttrName.startsWith("data-")
    ) {
      return false;
    }

    // Check for dangerous protocols in URLs
    if (["href", "src", "action", "formaction"].includes(lowerAttrName)) {
      const value = (attrValue || "").trim().toLowerCase();
      if (
        value.startsWith("javascript:") ||
        value.startsWith("data:") ||
        value.startsWith("vbscript:") ||
        value.startsWith("file:")
      ) {
        return false;
      }
    }

    // Check for dangerous content in style attributes
    if (lowerAttrName === "style") {
      const value = (attrValue || "").toLowerCase();
      if (
        value.includes("javascript:") ||
        value.includes("expression(") ||
        value.includes("import") ||
        value.includes("behavior:")
      ) {
        return false;
      }
    }

    return true;
  }

  /**
   * Recursively sanitize a DOM node and its children
   */
  function sanitizeNode(node) {
    // Text nodes are safe
    if (node.nodeType === Node.TEXT_NODE) {
      return node.cloneNode(false);
    }

    // Only process element nodes
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return null;
    }

    const tagName = node.tagName.toLowerCase();

    // Remove disallowed tags completely
    if (!allowedTags.has(tagName)) {
      return null;
    }

    // Create a new clean element
    const cleanElement = document.createElement(tagName);

    // Copy only safe attributes
    for (const attr of node.attributes) {
      if (isAttributeSafe(attr.name, attr.value)) {
        cleanElement.setAttribute(attr.name, attr.value);
      }
    }

    // Recursively sanitize children
    for (const child of node.childNodes) {
      const cleanChild = sanitizeNode(child);
      if (cleanChild) {
        cleanElement.appendChild(cleanChild);
      }
    }

    return cleanElement;
  }

  // Sanitize all children of the temp element
  const cleanDiv = document.createElement("div");
  for (const child of temp.childNodes) {
    const cleanChild = sanitizeNode(child);
    if (cleanChild) {
      cleanDiv.appendChild(cleanChild);
    }
  }

  return cleanDiv.innerHTML;
}

/**
 * Create a safe DOM element with text content (never uses innerHTML)
 *
 * @param {string} tag - The HTML tag name
 * @param {Object} attributes - Object of attributes to set
 * @param {string|Node|Array} content - Text content, DOM node, or array of nodes
 * @returns {HTMLElement} - The created element
 */
function createSafeElement(tag, attributes = {}, content = null) {
  const element = document.createElement(tag);

  // Set attributes safely
  for (const [key, value] of Object.entries(attributes)) {
    if (value !== null && value !== undefined) {
      // For data attributes and other safe attributes
      if (
        key.startsWith("data-") ||
        [
          "class",
          "id",
          "title",
          "role",
          "aria-label",
          "type",
          "disabled",
        ].includes(key)
      ) {
        element.setAttribute(key, String(value));
      } else if (key === "className") {
        element.className = String(value);
      }
    }
  }

  // Set content safely
  if (content !== null && content !== undefined) {
    if (typeof content === "string") {
      // Always use textContent for strings
      element.textContent = content;
    } else if (content instanceof Node) {
      element.appendChild(content);
    } else if (Array.isArray(content)) {
      content.forEach((item) => {
        if (item instanceof Node) {
          element.appendChild(item);
        } else if (typeof item === "string") {
          element.appendChild(document.createTextNode(item));
        }
      });
    }
  }

  return element;
}

/**
 * Safely set text content on an element (wrapper for clarity)
 *
 * @param {HTMLElement} element - The target element
 * @param {string} text - The text content to set
 */
function setSafeText(element, text) {
  if (element && text !== null && text !== undefined) {
    element.textContent = String(text);
  }
}

/**
 * Create a text node safely
 *
 * @param {string} text - The text content
 * @returns {Text} - The text node
 */
function createSafeTextNode(text) {
  return document.createTextNode(String(text || ""));
}

/**
 * Escape HTML special characters
 * This is for cases where you're building HTML strings before parsing
 *
 * @param {string} text - The text to escape
 * @returns {string} - The escaped text
 */
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Export functions for use in other modules
if (typeof window !== "undefined") {
  window.sanitizeHTML = sanitizeHTML;
  window.createSafeElement = createSafeElement;
  window.setSafeText = setSafeText;
  window.createSafeTextNode = createSafeTextNode;
  window.escapeHtml = escapeHtml;
}
