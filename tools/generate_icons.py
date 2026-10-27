"""
Generate crisp PNG icons from SVG geometry using Pillow.
Outputs icon.png (24x24 / 32x32 / 64x64 / 256x256).
"""

from pathlib import Path
from PIL import Image, ImageDraw

def render_minimal_cube_icon(size: int = 64) -> Image.Image:
    """Renders a modern minimal 3D isometric cube + HTML brackets icon."""
    scale = size / 24.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def pt(x: float, y: float):
        return (x * scale, y * scale)

    # Geometry coordinates based on 24x24 grid
    p_top = pt(12, 2.5)
    p_top_r = pt(20.5, 7.2)
    p_center = pt(12, 11.9)
    p_top_l = pt(3.5, 7.2)
    p_bot_l = pt(3.5, 16.8)
    p_bot = pt(12, 21.5)
    p_bot_r = pt(20.5, 16.8)

    # Colors
    col_line = (56, 189, 248, 255)      # Cyan / Sky blue
    col_bracket = (34, 211, 238, 255)   # Bright Cyan
    col_top_fill = (56, 189, 248, 45)   # Semi-transparent Sky
    col_left_fill = (2, 132, 199, 35)   # Deeper blue
    col_right_fill = (6, 182, 212, 40)  # Cyan tint
    col_node = (255, 255, 255, 255)

    stroke_w = max(1, int(1.75 * scale))
    bracket_w = max(1, int(1.6 * scale))

    # Fills
    draw.polygon([p_top, p_top_r, p_center, p_top_l], fill=col_top_fill)
    draw.polygon([p_top_l, p_center, p_bot, p_bot_l], fill=col_left_fill)
    draw.polygon([p_top_r, p_center, p_bot, p_bot_r], fill=col_right_fill)

    # Wireframe Outlines
    draw.line([p_top, p_top_r, p_center, p_top_l, p_top], fill=col_line, width=stroke_w, joint="curve")
    draw.line([p_top_l, p_center, p_bot, p_bot_l, p_top_l], fill=col_line, width=stroke_w, joint="curve")
    draw.line([p_top_r, p_center, p_bot, p_bot_r, p_top_r], fill=col_line, width=stroke_w, joint="curve")
    draw.line([p_center, p_bot], fill=col_line, width=stroke_w)

    # Brackets "<" and ">"
    b_left = [pt(9, 14.2), pt(6.5, 15.7), pt(9, 17.2)]
    draw.line(b_left, fill=col_bracket, width=bracket_w, joint="curve")

    b_right = [pt(15, 14.2), pt(17.5, 15.7), pt(15, 17.2)]
    draw.line(b_right, fill=col_bracket, width=bracket_w, joint="curve")

    # Center Node Dot
    cx, cy = pt(12, 7.2)
    radius = max(1.5, 1.3 * scale)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=col_node)

    return img


def main():
    root = Path(__file__).resolve().parent.parent
    res_dir = root / "html_export" / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)

    # Standard toolbar icon (24x24, 32x32, 64x64)
    img_24 = render_minimal_cube_icon(24)
    img_24.save(res_dir / "icon.png")

    img_64 = render_minimal_cube_icon(64)
    img_64.save(res_dir / "icon_64.png")

    img_256 = render_minimal_cube_icon(256)
    img_256.save(res_dir / "icon_256.png")

    print(f"Generated icons in {res_dir}")

if __name__ == "__main__":
    main()
