import os
import time
from werkzeug.utils import secure_filename


def _default_storage_root():
    """Resolve handbook storage root, preferring /data when available."""
    env_root = os.environ.get("HANDBOOK_STORAGE_ROOT")
    if env_root:
        return env_root
    if os.path.isdir("/data"):
        return os.path.join("/data", "handbooks")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(project_root, "data", "handbooks")


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _safe_segment(value):
    if not value:
        return ""
    return secure_filename(str(value)) or ""


def get_storage_root():
    """Get base directory for handbook storage."""
    return _ensure_dir(_default_storage_root())


def get_upload_dir(handbook_id, subdir=None):
    """Get upload directory for a handbook, optionally with a subdir."""
    handbook_dir = os.path.join(get_storage_root(), "uploads", str(handbook_id))
    if subdir:
        handbook_dir = os.path.join(handbook_dir, _safe_segment(subdir))
    return _ensure_dir(handbook_dir)


def get_generated_dir(handbook_id):
    """Get generated files directory for a handbook."""
    return _ensure_dir(os.path.join(get_storage_root(), "generated", str(handbook_id)))


def save_uploaded_file(file_storage, handbook_id, subdir=None, filename=None):
    """
    Save an uploaded file to the handbook upload directory.
    Returns the absolute saved path.
    """
    if not file_storage:
        return None
    upload_dir = get_upload_dir(handbook_id, subdir=subdir)
    original_name = filename or getattr(file_storage, "filename", "") or ""
    safe_name = secure_filename(original_name)
    if not safe_name:
        safe_name = f"upload_{int(time.time())}"
    saved_path = os.path.join(upload_dir, safe_name)
    file_storage.save(saved_path)
    return saved_path


def save_text_content(content, handbook_id, subdir=None, filename="content.txt"):
    """Save text content into a file under the handbook upload directory."""
    if content is None:
        return None
    upload_dir = get_upload_dir(handbook_id, subdir=subdir)
    safe_name = secure_filename(filename) or f"text_{int(time.time())}.txt"
    saved_path = os.path.join(upload_dir, safe_name)
    with open(saved_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return saved_path
