"""
IngeTrazo Plugin Entry Point for html_export (ingetrazo-to-html).
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import webbrowser

from html_export.exporter import export_to_html

try:
    from ingetrazo.sdk import Tool  # type: ignore
except ImportError:
    class Tool:
        """Fallback base Tool class when IngeTrazo SDK is not present in test environment."""
        def __init__(self, name: str = "HtmlExportTool") -> None:
            self.name = name
            self.active = False

        def activate(self) -> None:
            self.active = True

        def deactivate(self) -> None:
            self.active = False


class HtmlExportPlugin(Tool):
    """
    Plugin implementation for exporting IngeTrazo 3D scenes into standalone Three.js HTML.
    """

    def __init__(self, app: Optional[Any] = None) -> None:
        super().__init__(name="html_export")
        self.app = app
        self.resources_dir = Path(__file__).resolve().parent / "resources"
        self.icon_svg = self.resources_dir / "icon.svg"
        self.icon_png = self.resources_dir / "icon.png"

    def get_menu_registration(self) -> Dict[str, Any]:
        """
        Returns menu configuration to register in IngeTrazo menu bar.
        """
        return {
            "menu_path": "File > Export",
            "items": [
                {
                    "label": "Export 3D HTML...",
                    "action": self.export_to_html_dialog,
                    "shortcut": "Ctrl+Shift+H",
                    "tooltip": "Export completed 3D scene to standalone Three.js HTML",
                }
            ],
        }

    def get_toolbar_registration(self) -> Dict[str, Any]:
        """
        Returns toolbar action configuration with SVG/PNG icon.
        """
        icon_path = self.icon_svg if self.icon_svg.exists() else self.icon_png
        return {
            "toolbar_name": "Export",
            "action": {
                "label": "Export 3D HTML",
                "tooltip": "Export 3D model to standalone Three.js HTML (Ctrl+Shift+H)",
                "icon": str(icon_path),
                "action": self.export_to_html_dialog,
            },
        }

    def _resolve_scene(self) -> Optional[Any]:
        """Resolves the active 3D scene object from the application instance."""
        if self.app is None:
            return None

        if hasattr(self.app, "scene") and callable(self.app.scene):
            return self.app.scene()
        elif hasattr(self.app, "scene"):
            return self.app.scene

        # Try window viewport
        win = getattr(self.app, "_window", getattr(self.app, "window", None))
        if win and hasattr(win, "viewport") and hasattr(win.viewport, "scene"):
            return win.viewport.scene

        if hasattr(self.app, "viewport") and hasattr(self.app.viewport, "scene"):
            return self.app.viewport.scene

        return None

    def export_to_html_dialog(self, auto_open: bool = True) -> Optional[Dict[str, Any]]:
        """
        Opens a save file dialog and exports the active scene to standalone HTML.
        """
        scene = self._resolve_scene()
        if scene is None:
            self._flash_status("Error: No active IngeTrazo scene found to export")
            return None

        # Determine target file via PySide6 dialog
        file_path_str: Optional[str] = None
        try:
            from PySide6.QtWidgets import QFileDialog  # type: ignore
            win = getattr(self.app, "_window", getattr(self.app, "window", None)) if self.app else None
            path, _ = QFileDialog.getSaveFileName(
                win,
                "Export 3D HTML Viewer",
                "model.html",
                "HTML Files (*.html *.htm);;All Files (*.*)",
            )
            if path:
                file_path_str = path
        except Exception:
            # Fallback if headless or testing
            file_path_str = "exported_model.html"

        if not file_path_str:
            return None

        return self.export_scene(scene, file_path_str, auto_open=auto_open)

    def export_scene(
        self,
        scene: Any,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        auto_open: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes export on the specified scene.
        """
        out_path = Path(output_path).resolve()
        model_title = title or out_path.stem.replace("_", " ").title()

        stats = export_to_html(
            scene=scene,
            output_path=out_path,
            title=model_title,
            embed_threejs=True,
        )

        msg = f"HTML Exported: {stats['face_count']} faces ({stats['file_size_mb']} MB) -> {out_path.name}"
        self._flash_status(msg)

        if auto_open and out_path.exists():
            try:
                webbrowser.open(out_path.as_uri())
            except Exception:
                pass

        return stats

    def _flash_status(self, text: str) -> None:
        """Displays a message on IngeTrazo status bar or viewport."""
        if not self.app:
            print(f"[html_export] {text}")
            return

        if hasattr(self.app, "flash_status") and callable(self.app.flash_status):
            self.app.flash_status(text)
        elif hasattr(self.app, "_window") and hasattr(self.app._window, "viewport"):
            viewport = self.app._window.viewport
            if hasattr(viewport, "flash_status"):
                viewport.flash_status(text)
        else:
            print(f"[html_export] {text}")


_active_plugin_instance: Optional[HtmlExportPlugin] = None


def register_plugin(app: Optional[Any] = None) -> HtmlExportPlugin:
    """Factory helper to register and retain singleton plugin instance."""
    global _active_plugin_instance
    if _active_plugin_instance is None or app is not None:
        _active_plugin_instance = HtmlExportPlugin(app=app)
    return _active_plugin_instance


def setup(app: Any) -> None:
    """
    Standard IngeTrazo extension hook invoked when extension is initialized.
    """
    plugin = register_plugin(app)

    def on_export() -> None:
        try:
            plugin.export_to_html_dialog(auto_open=True)
        except Exception as e:
            plugin._flash_status(f"Export failed: {e}")

    # Register in IngeTrazo menu
    if hasattr(app, "add_menu"):
        sub = app.add_menu("Export")
        if sub is not None:
            sub.addAction("Export 3D HTML...", on_export)
    elif hasattr(app, "add_menu_action"):
        app.add_menu_action(
            "Export: 3D HTML Viewer...",
            on_export,
            "Ctrl+Shift+H",
            "Export completed 3D scene to standalone Three.js HTML",
        )
