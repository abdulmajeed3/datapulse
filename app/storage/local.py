"""Local filesystem storage for uploaded dataset files.

Files are stored at: {upload_dir}/{user_id}/{dataset_id}/{safe_filename}

This abstraction can be replaced with a cloud-storage backend without
changing the calling code.

Limitations:
- Files are stored on the local filesystem. If the process is restarted
  or the container is replaced, files may be lost unless a persistent
  volume is mounted at UPLOAD_DIR.
- This implementation is not suitable for multi-instance deployments
  without a shared filesystem.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_UNSAFE_CHARS = re.compile(r"[^\w\-. ]")


def _safe_filename(filename: str) -> str:
    """Return a safe version of a filename, preventing path traversal."""
    # Take only the basename
    name = Path(filename).name
    # Replace unsafe characters
    name = _UNSAFE_CHARS.sub("_", name)
    # Prevent leading dots
    name = name.lstrip(".")
    # Truncate
    return name[:200] or "file"


def _storage_path(user_id: uuid.UUID, dataset_id: uuid.UUID, filename: str) -> Path:
    settings = get_settings()
    safe = _safe_filename(filename)
    return settings.upload_dir / str(user_id) / str(dataset_id) / safe


def save_upload(
    content: bytes,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    original_filename: str,
) -> str:
    """Persist upload bytes; return the storage path (relative to upload_dir)."""
    path = _storage_path(user_id, dataset_id, original_filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_bytes(content)
    logger.debug("Saved upload to %s (%d bytes)", path, len(content))

    # Return path relative to upload_dir for storage
    settings = get_settings()
    return str(path.relative_to(settings.upload_dir))


def load_upload(storage_path: str) -> bytes:
    """Read uploaded file bytes from storage."""
    settings = get_settings()
    full_path = settings.upload_dir / storage_path

    # Resolve and verify path stays within upload_dir (prevent traversal)
    resolved = full_path.resolve()
    if not str(resolved).startswith(str(settings.upload_dir.resolve())):
        raise PermissionError(f"Path traversal attempt blocked: {storage_path}")

    return resolved.read_bytes()


def delete_upload(storage_path: str) -> None:
    """Delete a stored file. Does not raise if the file is already absent."""
    settings = get_settings()
    full_path = settings.upload_dir / storage_path
    resolved = full_path.resolve()

    if not str(resolved).startswith(str(settings.upload_dir.resolve())):
        raise PermissionError(f"Path traversal attempt blocked: {storage_path}")

    try:
        resolved.unlink()
        logger.debug("Deleted upload: %s", resolved)
    except FileNotFoundError:
        pass
