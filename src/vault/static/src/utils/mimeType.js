/**
 * MIME type normalization utility for Leyzen Vault.
 *
 * Provides functions to normalize mime types, especially for files that have
 * generic mime types like 'application/octet-stream'.
 */

/**
 * Generic mime types that should be overridden by extension detection.
 */
const GENERIC_MIME_TYPES = [
  "application/octet-stream",
  "application/x-unknown",
  "binary/octet-stream",
];

/**
 * Extension to MIME type mapping.
 * This is a comprehensive mapping of common file extensions to their MIME types.
 */
const EXTENSION_TO_MIME_TYPE = {
  // Images
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  webp: "image/webp",
  svg: "image/svg+xml",
  bmp: "image/bmp",
  tiff: "image/tiff",
  tif: "image/tiff",
  ico: "image/x-icon",
  heic: "image/heic",
  heif: "image/heif",
  avif: "image/avif",
  // Documents
  pdf: "application/pdf",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls: "application/vnd.ms-excel",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ppt: "application/vnd.ms-powerpoint",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  odt: "application/vnd.oasis.opendocument.text",
  ods: "application/vnd.oasis.opendocument.spreadsheet",
  odp: "application/vnd.oasis.opendocument.presentation",
  rtf: "application/rtf",
  // Archives
  zip: "application/zip",
  "7z": "application/x-7z-compressed",
  rar: "application/x-rar-compressed",
  tar: "application/x-tar",
  gz: "application/gzip",
  bz2: "application/x-bzip2",
  xz: "application/x-xz",
  // Video
  mp4: "video/mp4",
  mpeg: "video/mpeg",
  mpg: "video/mpeg",
  avi: "video/x-msvideo",
  mov: "video/quicktime",
  wmv: "video/x-ms-wmv",
  flv: "video/x-flv",
  webm: "video/webm",
  mkv: "video/x-matroska",
  // Audio
  mp3: "audio/mpeg",
  wav: "audio/wav",
  ogg: "audio/ogg",
  flac: "audio/flac",
  aac: "audio/aac",
  m4a: "audio/mp4",
  wma: "audio/x-ms-wma",
  // Text
  txt: "text/plain",
  html: "text/html",
  htm: "text/html",
  css: "text/css",
  js: "text/javascript",
  json: "application/json",
  xml: "application/xml",
  csv: "text/csv",
  md: "text/markdown",
  markdown: "text/markdown",
  // Code
  py: "text/x-python",
  java: "text/x-java",
  c: "text/x-c",
  cpp: "text/x-c++",
  h: "text/x-c",
  hpp: "text/x-c++",
  cs: "text/x-csharp",
  ts: "application/typescript",
  jsx: "text/jsx",
  tsx: "text/tsx",
  sh: "application/x-sh",
  bash: "application/x-sh",
  zsh: "application/x-sh",
  // Other
  iso: "application/x-iso9660-image",
  dmg: "application/x-apple-diskimage",
  exe: "application/x-msdownload",
  deb: "application/vnd.debian.binary-package",
  rpm: "application/x-rpm",
};

/**
 * Get file extension from filename.
 *
 * @param {string} filename - File name
 * @returns {string|null} File extension in lowercase, or null if no extension
 */
function getExtension(filename) {
  if (!filename) return null;
  const parts = filename.split(".");
  if (parts.length < 2) return null;
  return parts.pop()?.toLowerCase() || null;
}

/**
 * Normalize mime type by detecting from file extension if the provided
 * mime type is generic.
 *
 * @param {string} filename - File name with extension
 * @param {string} mimeType - Current mime type (may be generic)
 * @returns {string} Normalized mime type
 */
export function normalizeMimeType(filename, mimeType) {
  // If mime type is not generic, return it as-is
  if (mimeType && !GENERIC_MIME_TYPES.includes(mimeType)) {
    return mimeType;
  }

  // Try to detect from extension
  const extension = getExtension(filename);
  if (extension && EXTENSION_TO_MIME_TYPE[extension]) {
    return EXTENSION_TO_MIME_TYPE[extension];
  }

  // Fallback to provided mime type or generic
  return mimeType || "application/octet-stream";
}

/**
 * Check if a mime type is generic (should be overridden).
 *
 * @param {string} mimeType - MIME type to check
 * @returns {boolean} True if mime type is generic
 */
export function isGenericMimeType(mimeType) {
  return GENERIC_MIME_TYPES.includes(mimeType);
}

/**
 * Get mime type from extension only (without checking current mime type).
 *
 * @param {string} filename - File name with extension
 * @returns {string|null} MIME type or null if not found
 */
export function getMimeTypeFromExtension(filename) {
  const extension = getExtension(filename);
  if (extension && EXTENSION_TO_MIME_TYPE[extension]) {
    return EXTENSION_TO_MIME_TYPE[extension];
  }
  return null;
}
