"""
Package the html_export extension into a distributable zip archive.
"""

import hashlib
import zipfile
from pathlib import Path

def package():
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / "html_export.zip"

    plugin_dir = repo_root / "html_export"
    if not plugin_dir.exists():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_dir}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in plugin_dir.rglob("*"):
            if f.is_file() and not any(part.startswith("__pycache__") for part in f.parts):
                arcname = f.relative_to(repo_root)
                zf.write(f, arcname)

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"Extension packaged successfully: {zip_path}")
    print(f"SHA-256: {sha256}")

if __name__ == "__main__":
    package()
