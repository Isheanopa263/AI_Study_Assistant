import os
import re


def sanitize_filename(filename: str) -> str:
    """Sanitize a user-provided filename to prevent directory traversal."""
    clean_name = os.path.basename(filename)
    clean_name = clean_name.replace("\x00", "")
    clean_name = clean_name.replace(" ", "_")
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "", clean_name)
    if not clean_name or clean_name.startswith("."):
        clean_name = f"document_{clean_name}"
    return clean_name


def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def format_file_size(size_bytes: int) -> str:
    """
    Convert raw bytes into a human-readable string.

    Examples:
        512         -> "512 B"
        1048576     -> "1.00 MB"
        10485760    -> "10.00 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"

    size = float(size_bytes)
    for unit in ["KB", "MB", "GB", "TB"]:
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.2f} {unit}"

    return f"{size:.2f} PB"