"""
html_export: Standalone 3D HTML Exporter Plugin for IngeTrazo.
"""

import sys
from pathlib import Path

# Ensure the plugin directory is accessible
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from html_export.plugin import HtmlExportPlugin, register_plugin, setup
from html_export.exporter import export_to_html

__version__ = "0.1.0"

__all__ = ["HtmlExportPlugin", "register_plugin", "setup", "export_to_html", "__version__"]
