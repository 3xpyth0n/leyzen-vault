"""MIME type detection utility for Leyzen Vault.

Detects MIME types from file extensions and file content.
Falls back to application/octet-stream only as a last resort.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import BinaryIO

# Try to import optional libraries for content-based detection
try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def detect_mime_type_from_extension(filename: str) -> str | None:
    """Detect MIME type from file extension using Python's mimetypes module.

    Args:
        filename: File name with extension

    Returns:
        MIME type string or None if not found
    """
    if not filename:
        return None

    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def get_extension_from_mime_type(mime_type: str) -> str | None:
    """Get file extension from MIME type using Python's mimetypes module.

    Args:
        mime_type: MIME type string (e.g., "image/png", "application/pdf")

    Returns:
        File extension string (e.g., ".png", ".pdf") or None if not found
    """
    if not mime_type:
        return None

    # Use mimetypes.guess_extension() to get extension from MIME type
    extension = mimetypes.guess_extension(mime_type)
    return extension


def detect_mime_type_from_content(file_data: bytes) -> str | None:
    """Detect MIME type from file content using magic bytes.

    Args:
        file_data: File data bytes

    Returns:
        MIME type string or None if not found
    """
    if not file_data:
        return None

    # Try python-magic if available
    if MAGIC_AVAILABLE:
        try:
            mime = magic.Magic(mime=True)
            detected = mime.from_buffer(file_data)
            if detected and detected != "application/octet-stream":
                return detected
        except Exception:
            pass

    # Try PIL for images
    if PIL_AVAILABLE:
        try:
            import io

            image = Image.open(io.BytesIO(file_data))
            format_to_mime = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "GIF": "image/gif",
                "WEBP": "image/webp",
                "BMP": "image/bmp",
                "TIFF": "image/tiff",
                "ICO": "image/x-icon",
            }
            detected = format_to_mime.get(image.format)
            if detected:
                return detected
        except Exception:
            pass

    # Check magic bytes for common formats
    if file_data.startswith(b"%PDF"):
        return "application/pdf"
    if file_data.startswith(b"PK\x03\x04"):  # ZIP file signature
        return "application/zip"
    if file_data.startswith(b"Rar!\x1a\x07"):  # RAR file signature
        return "application/x-rar-compressed"
    if file_data.startswith(b"7z\xbc\xaf\x27\x1c"):  # 7z file signature
        return "application/x-7z-compressed"
    if file_data.startswith(b"\x1f\x8b"):  # GZIP file signature
        return "application/gzip"

    return None


def detect_mime_type(
    filename: str | None = None,
    file_data: bytes | None = None,
    provided_mime_type: str | None = None,
) -> str:
    """Detect MIME type using multiple methods.

    Priority:
    1. Extension-based detection (mimetypes module)
    2. Content-based detection (magic bytes, PIL, python-magic) if file_data available
    3. Provided MIME type (only if not generic)
    4. Fallback to application/octet-stream (last resort)

    Args:
        filename: File name with extension
        file_data: File data bytes (optional, for content-based detection)
        provided_mime_type: MIME type provided by client (optional)

    Returns:
        Detected MIME type string
    """
    # Generic MIME types that should be overridden
    generic_types = {
        "application/octet-stream",
        "application/x-unknown",
        "binary/octet-stream",
        None,
    }

    # Priority 1: Extension-based detection (most reliable for files with extensions)
    if filename:
        extension_mime = detect_mime_type_from_extension(filename)
        if extension_mime and extension_mime not in generic_types:
            return extension_mime

    # Priority 2: Content-based detection (file-magic) if file data is available
    # This is useful when there's no extension or extension detection failed
    if file_data:
        content_mime = detect_mime_type_from_content(file_data)
        if content_mime and content_mime not in generic_types:
            return content_mime

    # Priority 3: Provided MIME type (only if not generic)
    # Client-provided types are less reliable, so we check them last
    if provided_mime_type and provided_mime_type not in generic_types:
        return provided_mime_type

    # Priority 4: Last resort - return generic type
    return "application/octet-stream"


__all__ = [
    "detect_mime_type",
    "detect_mime_type_from_extension",
    "detect_mime_type_from_content",
    "get_extension_from_mime_type",
]
