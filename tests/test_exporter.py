"""
Unit tests for html_export (ingetrazo-to-html).
"""

import json
from pathlib import Path
import tempfile

from html_export.exporter import (
    _parse_color,
    triangulate_polygon,
    extract_mesh_payload,
    export_to_html,
)
from html_export.plugin import HtmlExportPlugin, register_plugin, setup


class MockFace:
    """Mock IngeTrazo Face object for testing."""
    def __init__(self, pts, color="#38bdf8"):
        self._pts = pts
        self.attrs = {"color": color}

    def points(self):
        return self._pts


class MockScene:
    """Mock IngeTrazo Scene object."""
    def __init__(self, faces):
        self._faces = faces

    def faces(self):
        return self._faces


def test_color_parsing():
    # Hex string
    assert _parse_color("#ffffff") == (1.0, 1.0, 1.0)
    assert _parse_color("000000") == (0.0, 0.0, 0.0)

    # RGB 0-255
    assert _parse_color((255, 0, 128)) == (1.0, 0.0, 0.502)

    # RGB 0.0 - 1.0
    assert _parse_color((0.2, 0.5, 0.8)) == (0.2, 0.5, 0.8)

    # Fallback to IngeTrazo default plaster off-white
    assert _parse_color(None) == (0.96, 0.95, 0.925)


def test_triangulation():
    # Triangle (already 3 points)
    tri = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    assert len(triangulate_polygon(tri)) == 1

    # Quad (4 points -> 2 triangles)
    quad = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    tris = triangulate_polygon(quad)
    assert len(tris) == 2


def test_extract_mesh_payload():
    faces = [
        MockFace([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], color="#ff0000"),
        MockFace([(0, 0, 0), (0, 2, 0), (0, 2, 3)], color="#00ff00"),
    ]
    scene = MockScene(faces)
    payload = extract_mesh_payload(scene)

    assert payload["faceCount"] == 3  # 2 from quad + 1 from triangle
    assert payload["vertexCount"] == 9  # 3 triangles * 3 vertices
    assert len(payload["vertices"]) == 27  # 9 vertices * 3 coords (x,y,z)
    assert len(payload["colors"]) == 27    # 9 vertices * 3 rgb
    assert payload["edgeCount"] == 6       # 6 unique deduplicated edge lines
    assert len(payload["edges"]) == 36     # 6 edges * 2 endpoints * 3 coords


def test_export_to_html():
    faces = [
        MockFace([(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)], color="#38bdf8"),
    ]
    scene = MockScene(faces)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "test_model.html"
        stats = export_to_html(scene, out_file, title="Test Villa")

        assert out_file.exists()
        assert stats["success"] is True
        assert stats["face_count"] == 2
        assert stats["file_size_bytes"] > 500000  # Embedded Three.js is > 500KB

        content = out_file.read_text(encoding="utf-8")
        assert "Test Villa" in content
        assert "THREE" in content
        assert "OrbitControls" in content
        assert "MODEL_PAYLOAD" in content


def test_plugin_lifecycle():
    class MockApp:
        def __init__(self):
            self.status_msg = ""
            self.menu_items = []

        def flash_status(self, msg):
            self.status_msg = msg

        def add_menu_action(self, title, action, shortcut, tip):
            self.menu_items.append((title, shortcut))

    app = MockApp()
    plugin = HtmlExportPlugin(app=app)
    assert plugin.name == "html_export"

    # Menu and toolbar registrations
    menu_reg = plugin.get_menu_registration()
    assert menu_reg["menu_path"] == "File > Export"

    toolbar_reg = plugin.get_toolbar_registration()
    assert toolbar_reg["toolbar_name"] == "Export"
    assert toolbar_reg["action"]["label"] == "Export 3D HTML"

    # Setup hook
    setup(app)
    assert len(app.menu_items) >= 1
    assert app.menu_items[0][1] == "Ctrl+Shift+H"
