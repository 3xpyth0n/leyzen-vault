/** @file icons.js - Lucide Icons system for Leyzen Vault */

import * as lucideIcons from "lucide";
import { createApp, h, render } from "vue";
import * as lucideVue from "lucide-vue-next";

// Mapping from old icon names to Lucide icon names
const ICON_NAME_MAP = {
  folder: "Folder",
  folderOpen: "FolderOpen",
  folderPlus: "FolderPlus",
  file: "File",
  delete: "Trash2",
  star: "Star",
  users: "Users",
  clock: "Clock",
  lock: "Lock",
  key: "Key",
  user: "User",
  settings: "Settings",
  logout: "LogOut",
  upload: "Upload",
  download: "Download",
  link: "Link",
  eye: "Eye",
  edit: "PencilLine",
  clipboard: "Clipboard",
  copy: "Copy",
  move: "Move",
  search: "Search",
  plus: "Plus",
  chart: "BarChart3",
  moon: "Moon",
  sun: "Sun",
  warning: "AlertTriangle",
  moreVertical: "MoreVertical",
  grid: "LayoutGrid",
  list: "LayoutList",
  home: "Home",
  image: "Image",
  chevronDown: "ChevronDown",
  "chevron-down": "ChevronDown",
  check: "Check",
  trash: "Trash2",
  restore: "RotateCcw",
  "refresh-ccw": "RefreshCcw",
  "rotate-cw": "RotateCw",
  success: "CheckCircle",
  error: "XCircle",
  info: "Info",
  scissors: "Scissors",
  clipboardPaste: "ClipboardPaste",
  sparkles: "Sparkles",
  school: "GraduationCap",
  briefcase: "Briefcase",
  heart: "Heart",
  dollarSign: "DollarSign",
  book: "Book",
  calendar: "Calendar",
  shoppingBag: "ShoppingBag",
  car: "Car",
  music: "Music",
  video: "Video",
  camera: "Camera",
  gamepad: "Gamepad2",
  coffee: "Coffee",
  building: "Building",
  graduationCap: "GraduationCap",
  wallet: "Wallet",
  plane: "Plane",
  pin: "Pin",
  unpin: "PinOff",
  "pin-filled": "Pin",
  zip: "FolderArchive",
  funnel: "Filter",
  markdown: "FileText",
  html: "FileCode",
  pdf: "FileText",
  word: "FileText",
  excel: "FileSpreadsheet",
  powerpoint: "FilePresentation",
  code: "Code",
  json: "FileJson",
  xml: "FileCode",
  csv: "FileSpreadsheet",
  text: "FileText",
  iso: "Disc",
  executable: "FileCode",
  archive: "Archive",
  chevronRight: "ChevronRight",
  "chevron-right": "ChevronRight",
  chevronLeft: "ChevronLeft",
  "chevron-left": "ChevronLeft",
  mail: "Mail",
  satellite: "Satellite",
};

// File type to icon mapping
const FILE_ICON_MAP = {
  // Images
  image: "Image",
  // Videos
  video: "Video",
  // Audio
  music: "Music",
  // Documents
  pdf: "FileText",
  word: "FileText",
  excel: "FileSpreadsheet",
  powerpoint: "FilePresentation",
  // Archives
  zip: "Archive",
  archive: "Archive",
  // Code
  code: "Code",
  markdown: "FileText",
  html: "FileCode",
  json: "FileJson",
  xml: "FileCode",
  csv: "FileSpreadsheet",
  text: "FileText",
  // Other
  iso: "Disc",
  executable: "FileCode",
};

/**
 * Get Lucide icon component by name
 * @param {string} iconName - Icon name (old or Lucide name)
 * @returns {object|null} - Lucide icon component or null
 */
function getLucideIcon(iconName) {
  if (!iconName) return null;

  // Try mapped name first
  const mappedName = ICON_NAME_MAP[iconName] || iconName;

  // Try direct name in lucideIcons
  if (lucideIcons[mappedName]) {
    return lucideIcons[mappedName];
  }

  // Try with PascalCase
  const pascalName = mappedName.charAt(0).toUpperCase() + mappedName.slice(1);
  if (lucideIcons[pascalName]) {
    return lucideIcons[pascalName];
  }

  // Try with different casing
  for (const key in lucideIcons) {
    if (key.toLowerCase() === mappedName.toLowerCase()) {
      return lucideIcons[key];
    }
  }

  return null;
}

/**
 * Generate SVG HTML string from Lucide icon
 * @param {string} iconName - Icon name
 * @param {number} size - Icon size
 * @param {string} color - Icon color
 * @returns {string} - SVG HTML string
 */
export function getIcon(iconName, size = 24, color = "currentColor") {
  if (!iconName) {
    return "";
  }

  // Try to generate SVG directly using the icon name
  const svg = generateSVG(iconName, size, color);

  // If we got an empty or invalid SVG, return empty string
  if (
    !svg ||
    !svg.trim() ||
    (svg.includes('viewBox="0 0 24 24"') &&
      !svg.includes("<path") &&
      !svg.includes("<circle") &&
      !svg.includes("<rect") &&
      !svg.includes("<polygon") &&
      !svg.includes("<line") &&
      !svg.includes("<g>"))
  ) {
    return "";
  }

  return svg;
}

/**
 * Generate SVG HTML string from Lucide icon component name
 * @param {string|object} iconNameOrComponent - Icon name or Lucide icon component
 * @param {number} size - Icon size
 * @param {string} color - Icon color
 * @returns {string} - SVG HTML string
 */
function generateSVG(iconNameOrComponent, size, color) {
  // Use Vue render to generate SVG HTML string
  try {
    // Check if Vue is available
    if (typeof h === "undefined" || typeof render === "undefined") {
      throw new Error("Vue is not available");
    }

    // Extract icon name
    let iconName = "";
    if (typeof iconNameOrComponent === "string") {
      iconName = iconNameOrComponent;
    } else if (
      iconNameOrComponent &&
      (iconNameOrComponent.name || iconNameOrComponent.displayName)
    ) {
      iconName =
        iconNameOrComponent.name || iconNameOrComponent.displayName || "";
    } else {
      // If it's the mapped name, try to find the actual icon name
      // For now, just return empty
      throw new Error("Invalid icon name or component");
    }

    // Get mapped name from ICON_NAME_MAP
    const mappedName = ICON_NAME_MAP[iconName] || iconName;

    // Find the Vue component from lucide-vue-next
    let VueIconComponent = null;

    // Try multiple search strategies
    // 1. Try direct name first (exact match)
    if (mappedName && lucideVue[mappedName]) {
      VueIconComponent = lucideVue[mappedName];
    }

    // 2. Try case-insensitive search
    if (!VueIconComponent && mappedName) {
      const foundKey = Object.keys(lucideVue).find(
        (key) => key.toLowerCase() === mappedName.toLowerCase(),
      );
      if (foundKey) {
        VueIconComponent = lucideVue[foundKey];
      }
    }

    // 3. Try removing common suffixes (Icon, Lucide, etc.)
    if (!VueIconComponent && mappedName) {
      const baseName = mappedName
        .replace(/Icon$/, "")
        .replace(/^Lucide/, "")
        .trim();
      if (baseName && lucideVue[baseName]) {
        VueIconComponent = lucideVue[baseName];
      } else if (baseName) {
        const foundKey = Object.keys(lucideVue).find(
          (key) => key.toLowerCase() === baseName.toLowerCase(),
        );
        if (foundKey) {
          VueIconComponent = lucideVue[foundKey];
        }
      }
    }

    // 4. Try adding "Icon" suffix
    if (!VueIconComponent && mappedName) {
      const withSuffix = mappedName + "Icon";
      if (lucideVue[withSuffix]) {
        VueIconComponent = lucideVue[withSuffix];
      }
    }

    // 5. Try with "Lucide" prefix variants
    if (!VueIconComponent && mappedName) {
      const withLucidePrefix = "Lucide" + mappedName;
      if (lucideVue[withLucidePrefix]) {
        VueIconComponent = lucideVue[withLucidePrefix];
      }
    }

    // 6. Case-insensitive search for "Lucide" prefixed name
    if (!VueIconComponent && mappedName) {
      const lucidePrefixedKey = Object.keys(lucideVue).find(
        (key) => key.toLowerCase() === ("lucide" + mappedName).toLowerCase(),
      );
      if (lucidePrefixedKey) {
        VueIconComponent = lucideVue[lucidePrefixedKey];
      }
    }

    // 7. Try "Lucide" prefix with base name
    if (!VueIconComponent && mappedName) {
      const baseName = mappedName
        .replace(/Icon$/, "")
        .replace(/^Lucide/, "")
        .trim();
      const withLucideBase = "Lucide" + baseName;
      if (lucideVue[withLucideBase]) {
        VueIconComponent = lucideVue[withLucideBase];
      } else {
        const foundLucideBase = Object.keys(lucideVue).find(
          (key) => key.toLowerCase() === ("lucide" + baseName).toLowerCase(),
        );
        if (foundLucideBase) {
          VueIconComponent = lucideVue[foundLucideBase];
        }
      }
    }

    // If we found a Vue component, use render to get SVG HTML
    if (VueIconComponent) {
      const tempDiv = document.createElement("div");

      // Create a vnode for the icon
      const vnode = h(VueIconComponent, {
        size: size,
        color: color,
        strokeWidth: 2,
      });

      // Render the vnode to the temporary div
      render(vnode, tempDiv);

      // Get the SVG HTML
      const svgHTML = tempDiv.innerHTML;

      // Clean up by rendering null
      render(null, tempDiv);

      if (svgHTML && svgHTML.trim()) {
        return svgHTML;
      }
    }
  } catch (error) {
    // Silently fail and return empty SVG structure
  }

  // Last resort: create a basic SVG structure
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"></svg>`;
}

/**
 * Get file icon name based on mime type and file name
 * @param {string|null} mimeType - MIME type
 * @param {string|null} fileName - File name
 * @returns {string} - Icon name
 */
export function getFileIconName(mimeType, fileName) {
  if (!mimeType && !fileName) {
    return "file";
  }

  const ext = fileName ? fileName.split(".").pop()?.toLowerCase() || "" : "";

  // Check mime type first
  if (mimeType && typeof mimeType === "string") {
    // Images
    if (mimeType.startsWith("image/")) {
      return "image";
    }

    // Videos
    if (mimeType.startsWith("video/")) {
      return "video";
    }

    // Audio
    if (mimeType.startsWith("audio/")) {
      return "music";
    }

    // PDF
    if (mimeType === "application/pdf") {
      return "pdf";
    }

    // Word documents
    if (
      mimeType === "application/msword" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) {
      return "word";
    }

    // Excel spreadsheets
    if (
      mimeType === "application/vnd.ms-excel" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ) {
      return "excel";
    }

    // PowerPoint presentations
    if (
      mimeType === "application/vnd.ms-powerpoint" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ) {
      return "powerpoint";
    }

    // ZIP archives
    if (
      mimeType === "application/zip" ||
      mimeType === "application/x-zip-compressed"
    ) {
      return "zip";
    }

    // Other archives
    if (
      mimeType === "application/x-rar-compressed" ||
      mimeType === "application/x-rar" ||
      mimeType === "application/x-7z-compressed" ||
      mimeType === "application/x-tar" ||
      mimeType === "application/gzip" ||
      mimeType === "application/x-gzip"
    ) {
      return "archive";
    }

    // Markdown
    if (mimeType === "text/markdown" || mimeType === "text/x-markdown") {
      return "markdown";
    }

    // HTML
    if (mimeType === "text/html") {
      return "html";
    }

    // JSON
    if (mimeType === "application/json" || mimeType === "text/json") {
      return "json";
    }

    // XML
    if (mimeType === "text/xml" || mimeType === "application/xml") {
      return "xml";
    }

    // CSV
    if (mimeType === "text/csv") {
      return "csv";
    }

    // Text files
    if (mimeType === "text/plain") {
      return "text";
    }

    // ISO
    if (
      mimeType === "application/x-iso9660-image" ||
      mimeType === "application/x-cd-image"
    ) {
      return "iso";
    }

    // Executables
    if (mimeType === "application/x-executable") {
      return "executable";
    }

    // Code files
    if (
      mimeType === "text/javascript" ||
      mimeType === "application/javascript" ||
      mimeType === "application/x-python" ||
      mimeType === "text/x-python" ||
      mimeType === "text/x-java" ||
      mimeType === "text/x-c" ||
      mimeType === "text/x-c++" ||
      mimeType === "text/x-csharp" ||
      mimeType === "text/css" ||
      mimeType === "application/x-sh" ||
      mimeType === "application/x-bash"
    ) {
      return "code";
    }
  }

  // Fallback to extension if mime type not recognized
  if (ext) {
    // Images
    if (
      [
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "svg",
        "bmp",
        "tiff",
        "ico",
      ].includes(ext)
    ) {
      return "image";
    }

    // Videos
    if (
      [
        "mp4",
        "avi",
        "mov",
        "wmv",
        "flv",
        "webm",
        "mkv",
        "mpeg",
        "mpg",
      ].includes(ext)
    ) {
      return "video";
    }

    // Audio
    if (["mp3", "wav", "flac", "ogg", "m4a", "aac", "wma"].includes(ext)) {
      return "music";
    }

    // Documents
    if (ext === "pdf") {
      return "pdf";
    }

    if (ext === "doc" || ext === "docx") {
      return "word";
    }

    if (ext === "xls" || ext === "xlsx") {
      return "excel";
    }

    if (ext === "ppt" || ext === "pptx") {
      return "powerpoint";
    }

    // Archives
    if (ext === "zip") {
      return "zip";
    }

    if (["rar", "7z", "tar", "gz", "bz2", "xz"].includes(ext)) {
      return "archive";
    }

    // Markdown
    if (ext === "md" || ext === "markdown") {
      return "markdown";
    }

    // HTML
    if (ext === "html" || ext === "htm") {
      return "html";
    }

    // JSON
    if (ext === "json") {
      return "json";
    }

    // XML
    if (ext === "xml") {
      return "xml";
    }

    // CSV
    if (ext === "csv") {
      return "csv";
    }

    // Text files
    if (["txt", "log", "ini", "conf", "cfg"].includes(ext)) {
      return "text";
    }

    // ISO
    if (ext === "iso" || ext === "dmg") {
      return "iso";
    }

    // Executables
    if (["exe", "app", "deb", "rpm", "msi", "dmg", "pkg"].includes(ext)) {
      return "executable";
    }

    // Code files
    if (
      [
        "js",
        "ts",
        "jsx",
        "tsx",
        "py",
        "java",
        "c",
        "cpp",
        "cc",
        "cxx",
        "h",
        "hpp",
        "cs",
        "php",
        "rb",
        "go",
        "rs",
        "swift",
        "kt",
        "scala",
        "sh",
        "bash",
        "zsh",
        "fish",
        "ps1",
        "bat",
        "cmd",
        "css",
        "scss",
        "sass",
        "less",
        "vue",
        "svelte",
      ].includes(ext)
    ) {
      return "code";
    }
  }

  // Default fallback
  return "file";
}

/**
 * Get all available icon names from Lucide Vue
 * @returns {string[]} - Array of icon names
 */
export function getAllIconNames() {
  try {
    const allKeys = Object.keys(lucideVue || {});

    // Collect all icon names and identify base names
    const allIcons = [];

    for (const name of allKeys) {
      // Basic filtering
      if (!name || name.length === 0) continue;
      if (name[0] !== name[0].toUpperCase()) continue;

      // Skip helper functions
      const skipList = ["createLucideIcon", "Icon", "lucide", "createElement"];
      if (skipList.includes(name)) continue;

      // Check if it's a valid icon component
      const component = lucideVue[name];
      if (!component) continue;
      if (typeof component !== "function" && typeof component !== "object")
        continue;

      // Determine if this is a variant and extract base name
      let baseName = name;
      let isVariant = false;

      if (name.endsWith("Icon")) {
        baseName = name.slice(0, -4); // Remove "Icon" suffix
        isVariant = true;
      } else if (name.startsWith("Lucide")) {
        baseName = name.slice(6); // Remove "Lucide" prefix
        isVariant = true;
      }

      allIcons.push({
        name: name,
        baseName: baseName.toLowerCase(), // Use lowercase for comparison
        length: name.length,
        isVariant: isVariant,
      });
    }

    // Group by base name and keep only the shortest non-variant name
    const iconMap = new Map();

    for (const icon of allIcons) {
      const baseKey = icon.baseName;

      if (!iconMap.has(baseKey)) {
        // First occurrence, add it
        iconMap.set(baseKey, icon);
      } else {
        const existing = iconMap.get(baseKey);
        // Prefer non-variant over variant
        if (!icon.isVariant && existing.isVariant) {
          iconMap.set(baseKey, icon);
        } else if (icon.isVariant && !existing.isVariant) {
          // Keep the existing non-variant
          continue;
        } else {
          // Both same type, prefer shorter name
          if (icon.length < existing.length) {
            iconMap.set(baseKey, icon);
          }
        }
      }
    }

    // Extract final unique icon names (only non-variants)
    const uniqueNames = Array.from(iconMap.values())
      .filter((icon) => !icon.isVariant) // Only keep non-variants
      .map((icon) => icon.name)
      .sort();

    return uniqueNames;
  } catch (error) {
    return [];
  }
}

/**
 * Search icons by name
 * @param {string} query - Search query
 * @returns {string[]} - Array of matching icon names
 */
export function searchIcons(query) {
  if (!query || !query.trim()) {
    return getAllIconNames();
  }

  const lowerQuery = query.toLowerCase().trim();
  return getAllIconNames().filter((name) =>
    name.toLowerCase().includes(lowerQuery),
  );
}

// Export for use in window object (backward compatibility)
if (typeof window !== "undefined") {
  window.Icons = {
    getIcon,
    getFileIconName,
    getAllIconNames,
    searchIcons,
    // Legacy compatibility - map old function calls
    folder: (size, color) => getIcon("folder", size, color),
    folderOpen: (size, color) => getIcon("folderOpen", size, color),
    folderPlus: (size, color) => getIcon("folderPlus", size, color),
    file: (size, color) => getIcon("file", size, color),
    delete: (size, color) => getIcon("delete", size, color),
    star: (size, color) => getIcon("star", size, color),
    users: (size, color) => getIcon("users", size, color),
    clock: (size, color) => getIcon("clock", size, color),
    lock: (size, color) => getIcon("lock", size, color),
    key: (size, color) => getIcon("key", size, color),
    user: (size, color) => getIcon("user", size, color),
    settings: (size, color) => getIcon("settings", size, color),
    logout: (size, color) => getIcon("logout", size, color),
    upload: (size, color) => getIcon("upload", size, color),
    download: (size, color) => getIcon("download", size, color),
    link: (size, color) => getIcon("link", size, color),
    eye: (size, color) => getIcon("eye", size, color),
    edit: (size, color) => getIcon("edit", size, color),
    clipboard: (size, color) => getIcon("clipboard", size, color),
    copy: (size, color) => getIcon("copy", size, color),
    move: (size, color) => getIcon("move", size, color),
    search: (size, color) => getIcon("search", size, color),
    plus: (size, color) => getIcon("plus", size, color),
    chart: (size, color) => getIcon("chart", size, color),
    moon: (size, color) => getIcon("moon", size, color),
    sun: (size, color) => getIcon("sun", size, color),
    warning: (size, color) => getIcon("warning", size, color),
    moreVertical: (size, color) => getIcon("moreVertical", size, color),
    grid: (size, color) => getIcon("grid", size, color),
    list: (size, color) => getIcon("list", size, color),
    home: (size, color) => getIcon("home", size, color),
    image: (size, color) => getIcon("image", size, color),
    chevronDown: (size, color) => getIcon("chevronDown", size, color),
    "chevron-down": (size, color) => getIcon("chevron-down", size, color),
    check: (size, color) => getIcon("check", size, color),
    trash: (size, color) => getIcon("trash", size, color),
    restore: (size, color) => getIcon("restore", size, color),
    "refresh-ccw": (size, color) => getIcon("refresh-ccw", size, color),
    "rotate-cw": (size, color) => getIcon("rotate-cw", size, color),
    success: (size, color) => getIcon("success", size, color),
    error: (size, color) => getIcon("error", size, color),
    info: (size, color) => getIcon("info", size, color),
    sparkles: (size, color) => getIcon("sparkles", size, color),
    school: (size, color) => getIcon("school", size, color),
    briefcase: (size, color) => getIcon("briefcase", size, color),
    heart: (size, color) => getIcon("heart", size, color),
    dollarSign: (size, color) => getIcon("dollarSign", size, color),
    book: (size, color) => getIcon("book", size, color),
    calendar: (size, color) => getIcon("calendar", size, color),
    shoppingBag: (size, color) => getIcon("shoppingBag", size, color),
    car: (size, color) => getIcon("car", size, color),
    music: (size, color) => getIcon("music", size, color),
    video: (size, color) => getIcon("video", size, color),
    camera: (size, color) => getIcon("camera", size, color),
    gamepad: (size, color) => getIcon("gamepad", size, color),
    coffee: (size, color) => getIcon("coffee", size, color),
    building: (size, color) => getIcon("building", size, color),
    graduationCap: (size, color) => getIcon("graduationCap", size, color),
    wallet: (size, color) => getIcon("wallet", size, color),
    plane: (size, color) => getIcon("plane", size, color),
    pin: (size, color) => getIcon("pin", size, color),
    unpin: (size, color) => getIcon("unpin", size, color),
    "pin-filled": (size, color) => getIcon("pin-filled", size, color),
    zip: (size, color) => getIcon("zip", size, color),
    funnel: (size, color) => getIcon("funnel", size, color),
    markdown: (size, color) => getIcon("markdown", size, color),
    html: (size, color) => getIcon("html", size, color),
    pdf: (size, color) => getIcon("pdf", size, color),
    word: (size, color) => getIcon("word", size, color),
    excel: (size, color) => getIcon("excel", size, color),
    powerpoint: (size, color) => getIcon("powerpoint", size, color),
    code: (size, color) => getIcon("code", size, color),
    json: (size, color) => getIcon("json", size, color),
    xml: (size, color) => getIcon("xml", size, color),
    csv: (size, color) => getIcon("csv", size, color),
    text: (size, color) => getIcon("text", size, color),
    iso: (size, color) => getIcon("iso", size, color),
    executable: (size, color) => getIcon("executable", size, color),
    archive: (size, color) => getIcon("archive", size, color),
    scissors: (size, color) => getIcon("scissors", size, color),
    clipboardPaste: (size, color) => getIcon("clipboardPaste", size, color),
    chevronRight: (size, color) => getIcon("chevronRight", size, color),
    "chevron-right": (size, color) => getIcon("chevron-right", size, color),
    chevronLeft: (size, color) => getIcon("chevronLeft", size, color),
    "chevron-left": (size, color) => getIcon("chevron-left", size, color),
    mail: (size, color) => getIcon("mail", size, color),
    satellite: (size, color) => getIcon("satellite", size, color),
  };

  // Add getFileIconName for backward compatibility
  window.Icons.getFileIconName = getFileIconName;
}
