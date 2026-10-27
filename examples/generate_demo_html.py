"""
Generate a sample 3D architectural model HTML file to demonstrate the standalone viewer.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from html_export.exporter import export_to_html


class DemoFace:
    def __init__(self, pts, color=(0.85, 0.85, 0.90)):
        self._pts = pts
        self.attrs = {"color": color}

    def points(self):
        return self._pts


def make_box(x, y, z, dx, dy, dz, color):
    """Generates 6 faces of a 3D box."""
    faces = [
        # Bottom (Z = z)
        DemoFace([(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)], color),
        # Top (Z = z + dz)
        DemoFace([(x, y, z + dz), (x, y + dy, z + dz), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)], color),
        # Front (Y = y)
        DemoFace([(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)], color),
        # Back (Y = y + dy)
        DemoFace([(x, y + dy, z), (x, y + dy, z + dz), (x + dx, y + dy, z + dz), (x + dx, y + dy, z)], color),
        # Left (X = x)
        DemoFace([(x, y, z), (x, y, z + dz), (x, y + dy, z + dz), (x, y + dy, z)], color),
        # Right (X = x + dx)
        DemoFace([(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)], color),
    ]
    return faces


def build_modern_pavilion():
    faces = []

    # Floor Slab (Concrete Gray)
    faces.extend(make_box(0, 0, 0, 10, 8, 0.3, (0.8, 0.82, 0.85)))

    # 6 Columns (Charcoal / Steel)
    col_w = 0.35
    col_h = 3.5
    col_color = (0.25, 0.28, 0.35)
    for cx in [0.5, 4.8, 9.15]:
        for cy in [0.5, 7.15]:
            faces.extend(make_box(cx, cy, 0.3, col_w, col_w, col_h, col_color))

    # Roof Slab (White Cantilevered)
    faces.extend(make_box(-0.5, -0.5, 3.8, 11, 9, 0.35, (0.95, 0.96, 0.98)))

    # Back Feature Wall (Warm Wood / Accent)
    faces.extend(make_box(0.5, 7.15, 0.3, 9.0, 0.2, col_h, (0.76, 0.55, 0.38)))

    # Glass Partitions (Cyan Glaze)
    faces.extend(make_box(0.5, 3.8, 0.3, 4.3, 0.08, col_h, (0.35, 0.75, 0.88)))

    return faces


def main():
    root = Path(__file__).resolve().parent.parent
    examples_dir = root / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    demo_faces = build_modern_pavilion()
    out_html = examples_dir / "modern_pavilion.html"

    print(f"Exporting Modern Pavilion demo to {out_html}...")
    stats = export_to_html(demo_faces, out_html, title="Modern Living Pavilion", embed_threejs=True)

    print("Success!")
    print(f"Faces: {stats['face_count']}")
    print(f"Size: {stats['file_size_mb']} MB")
    print(f"Path: {stats['file_path']}")


if __name__ == "__main__":
    main()
