"""
Generate a sample 3D architectural model HTML file with textures to demonstrate the standalone viewer.
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from html_export.exporter import export_to_html


def create_procedural_wood_texture(path: Path):
    """Creates a subtle, realistic architectural wood plank texture."""
    img = Image.new("RGB", (256, 256), color=(185, 135, 95))
    draw = ImageDraw.Draw(img)

    # Wood grain and planks
    plank_h = 32
    for y in range(0, 256, plank_h):
        draw.line([(0, y), (256, y)], fill=(120, 85, 55), width=2)
        # Subtle grain streaks
        for streak in range(y + 4, y + plank_h - 2, 6):
            draw.line([(0, streak), (256, streak)], fill=(170, 120, 80), width=1)

    img.save(path, quality=90)


def create_procedural_stone_tiles(path: Path):
    """Creates an architectural stone tile texture for the floor slab."""
    img = Image.new("RGB", (256, 256), color=(210, 215, 220))
    draw = ImageDraw.Draw(img)

    # Grid tile joints
    tile_size = 64
    for x in range(0, 256, tile_size):
        draw.line([(x, 0), (x, 256)], fill=(160, 165, 172), width=2)
    for y in range(0, 256, tile_size):
        draw.line([(0, y), (256, y)], fill=(160, 165, 172), width=2)

    img.save(path, quality=90)


class DemoFace:
    def __init__(self, pts, color=(0.85, 0.85, 0.90), texture=None, normal=None):
        self._pts = pts
        self.attrs = {"color": color}
        if texture:
            self.attrs["texture"] = texture
        self._normal = normal

    def points(self):
        return self._pts

    def normal(self):
        if self._normal:
            return self._normal
        return (0, 0, 1)


def make_box(x, y, z, dx, dy, dz, color, top_texture=None, side_texture=None):
    """Generates 6 faces of a 3D box with optional texture mapping."""
    faces = [
        # Bottom (Z = z)
        DemoFace([(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)], color, normal=(0, 0, -1)),
        # Top (Z = z + dz)
        DemoFace([(x, y, z + dz), (x, y + dy, z + dz), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)], color, texture=top_texture, normal=(0, 0, 1)),
        # Front (Y = y)
        DemoFace([(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)], color, texture=side_texture, normal=(0, -1, 0)),
        # Back (Y = y + dy)
        DemoFace([(x, y + dy, z), (x, y + dy, z + dz), (x + dx, y + dy, z + dz), (x + dx, y + dy, z)], color, texture=side_texture, normal=(0, 1, 0)),
        # Left (X = x)
        DemoFace([(x, y, z), (x, y, z + dz), (x, y + dy, z + dz), (x, y + dy, z)], color, texture=side_texture, normal=(-1, 0, 0)),
        # Right (X = x + dx)
        DemoFace([(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)], color, texture=side_texture, normal=(1, 0, 0)),
    ]
    return faces


def build_modern_pavilion(wood_path: Path, tile_path: Path):
    faces = []

    tex_tile = {"path": str(tile_path), "sw": 2.0, "sh": 2.0}
    tex_wood = {"path": str(wood_path), "sw": 1.5, "sh": 1.5}

    # Floor Slab (Concrete with Stone Tiles on top)
    faces.extend(make_box(0, 0, 0, 10, 8, 0.3, (0.8, 0.82, 0.85), top_texture=tex_tile))

    # 6 Columns (Charcoal / Steel)
    col_w = 0.35
    col_h = 3.5
    col_color = (0.22, 0.25, 0.30)
    for cx in [0.5, 4.8, 9.15]:
        for cy in [0.5, 7.15]:
            faces.extend(make_box(cx, cy, 0.3, col_w, col_w, col_h, col_color))

    # Roof Slab (White Cantilevered)
    faces.extend(make_box(-0.5, -0.5, 3.8, 11, 9, 0.35, (0.95, 0.96, 0.98)))

    # Back Feature Wall (Warm Natural Wood Planks)
    faces.extend(make_box(0.5, 7.15, 0.3, 9.0, 0.2, col_h, (0.76, 0.55, 0.38), side_texture=tex_wood))

    # Glass Partitions (Cyan Glaze with transparency)
    glass_faces = make_box(0.5, 3.8, 0.3, 4.3, 0.08, col_h, (0.35, 0.75, 0.88))
    for f in glass_faces:
        f.attrs["opacity"] = 0.45
    faces.extend(glass_faces)

    return faces


def main():
    root_dir = Path(__file__).resolve().parent.parent
    examples_dir = root_dir / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    # Generate textures in examples folder
    wood_tex = examples_dir / "wood_planks.jpg"
    tile_tex = examples_dir / "stone_tiles.jpg"
    create_procedural_wood_texture(wood_tex)
    create_procedural_stone_tiles(tile_tex)

    demo_faces = build_modern_pavilion(wood_tex, tile_tex)
    out_html = examples_dir / "modern_pavilion.html"

    print(f"Exporting Modern Pavilion demo with textures to {out_html}...")
    stats = export_to_html(demo_faces, out_html, title="Modern Living Pavilion", embed_threejs=True)

    print("Success!")
    print(f"Faces: {stats['face_count']}")
    print(f"Textures: {stats['texture_count']}")
    print(f"Size: {stats['file_size_mb']} MB")
    print(f"Path: {stats['file_path']}")


if __name__ == "__main__":
    main()
