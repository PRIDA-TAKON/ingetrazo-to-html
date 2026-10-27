"""
Exporter engine: Extracts 3D mesh geometry and exact polygon edge lines from IngeTrazo scene
and generates standalone Three.js HTML viewers that match IngeTrazo's exact visual style.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# IngeTrazo Default Palette Constants
INGETRAZO_DEFAULT_FRONT_COLOR = (0.96, 0.95, 0.925)   # Warm architectural plaster white
INGETRAZO_EDGE_COLOR = (0.13, 0.17, 0.23)             # Deep charcoal navy (#212b3b)
INGETRAZO_BG_COLOR = (0.90, 0.91, 0.92)               # Viewport background (#e6e8eb)


def _extract_pt_coords(pt: Any) -> Tuple[float, float, float]:
    """Safely extracts (x, y, z) coordinates from various point types."""
    if hasattr(pt, "x") and callable(pt.x):
        return (float(pt.x()), float(pt.y()), float(pt.z()))
    elif hasattr(pt, "x"):
        return (float(pt.x), float(pt.y), float(pt.z))
    elif isinstance(pt, (tuple, list)) and len(pt) >= 3:
        return (float(pt[0]), float(pt[1]), float(pt[2]))
    else:
        raise ValueError(f"Unsupported point type: {type(pt)} -> {repr(pt)}")


def _parse_color(color_attr: Any) -> Tuple[float, float, float]:
    """Normalizes color into float RGB tuple (0.0 to 1.0)."""
    if color_attr is None:
        return INGETRAZO_DEFAULT_FRONT_COLOR

    # Hex string e.g. "#ffffff" or "ffffff"
    if isinstance(color_attr, str):
        s = color_attr.strip().lstrip("#")
        if len(s) == 6:
            try:
                r = int(s[0:2], 16) / 255.0
                g = int(s[2:4], 16) / 255.0
                b = int(s[4:6], 16) / 255.0
                return (round(r, 3), round(g, 3), round(b, 3))
            except ValueError:
                return INGETRAZO_DEFAULT_FRONT_COLOR

    # Tuple / List
    if isinstance(color_attr, (tuple, list)) and len(color_attr) >= 3:
        try:
            r, g, b = float(color_attr[0]), float(color_attr[1]), float(color_attr[2])
            # If values are in 0-255 range, normalize to 0-1
            if r > 1.0 or g > 1.0 or b > 1.0:
                r, g, b = r / 255.0, g / 255.0, b / 255.0
            return (round(r, 3), round(g, 3), round(b, 3))
        except (ValueError, TypeError):
            return INGETRAZO_DEFAULT_FRONT_COLOR

    return INGETRAZO_DEFAULT_FRONT_COLOR


def triangulate_polygon(pts: List[Any]) -> List[List[Any]]:
    """Simple fan triangulation for planar polygons."""
    if len(pts) < 3:
        return []
    if len(pts) == 3:
        return [pts]
    tris = []
    for i in range(1, len(pts) - 1):
        tris.append([pts[0], pts[i], pts[i + 1]])
    return tris


def collect_scene_faces(scene: Any) -> List[Any]:
    """Collects all renderable faces from IngeTrazo scene or raw face list."""
    if isinstance(scene, (list, tuple)):
        return list(scene)

    faces: List[Any] = []

    # 1. Try IngeTrazo native formats.meshexport.world_faces
    try:
        from formats.meshexport import world_faces  # type: ignore
        faces = list(world_faces(scene))
        if faces:
            return faces
    except Exception:
        pass

    # 2. Try scene.faces
    if hasattr(scene, "faces"):
        try:
            f_iter = scene.faces() if callable(scene.faces) else scene.faces
            if f_iter:
                faces.extend(list(f_iter))
        except Exception:
            pass

    # 3. Try scene.mesh.faces
    mesh = getattr(scene, "mesh", None)
    if mesh is not None and hasattr(mesh, "faces"):
        try:
            f_iter = mesh.faces() if callable(mesh.faces) else mesh.faces
            if f_iter:
                faces.extend(list(f_iter))
        except Exception:
            pass

    # 4. Check scene.groups if any
    groups = getattr(scene, "groups", [])
    if hasattr(groups, "__iter__"):
        for g in groups:
            g_mesh = getattr(g, "mesh", None)
            if g_mesh is not None and hasattr(g_mesh, "faces"):
                try:
                    f_iter = g_mesh.faces() if callable(g_mesh.faces) else g_mesh.faces
                    if f_iter:
                        faces.extend(list(f_iter))
                except Exception:
                    pass

    return faces


def collect_scene_edges(scene: Any, faces: List[Any]) -> List[float]:
    """
    Collects unique line segments representing model edges matching IngeTrazo's edge look.
    Returns flat list of coordinates [x1, y1, z1, x2, y2, z2, ...].
    """
    edge_set: Set[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = set()

    # 1. Check if scene or mesh has native edges
    mesh = getattr(scene, "mesh", None)
    if mesh is not None and hasattr(mesh, "edges"):
        try:
            for e in mesh.edges:
                p0 = _extract_pt_coords(e.a)
                p1 = _extract_pt_coords(e.b)
                p0_r = (round(p0[0], 4), round(p0[1], 4), round(p0[2], 4))
                p1_r = (round(p1[0], 4), round(p1[1], 4), round(p1[2], 4))
                if p0_r != p1_r:
                    edge_key = (min(p0_r, p1_r), max(p0_r, p1_r))
                    edge_set.add(edge_key)
        except Exception:
            pass

    # 2. Extract boundary edges from all faces
    for f in faces:
        pts: List[Any] = []
        if hasattr(f, "points"):
            pts = list(f.points() if callable(f.points) else f.points)
        elif hasattr(f, "vertices"):
            pts = list(f.vertices() if callable(f.vertices) else f.vertices)
        elif hasattr(f, "__iter__") and not isinstance(f, (str, bytes)):
            pts = list(f)

        if len(pts) >= 2:
            n = len(pts)
            for i in range(n):
                try:
                    p0 = _extract_pt_coords(pts[i])
                    p1 = _extract_pt_coords(pts[(i + 1) % n])
                    p0_r = (round(p0[0], 4), round(p0[1], 4), round(p0[2], 4))
                    p1_r = (round(p1[0], 4), round(p1[1], 4), round(p1[2], 4))
                    if p0_r != p1_r:
                        edge_key = (min(p0_r, p1_r), max(p0_r, p1_r))
                        edge_set.add(edge_key)
                except Exception:
                    continue

    flat_edges: List[float] = []
    for p0_r, p1_r in edge_set:
        flat_edges.extend([
            p0_r[0], p0_r[1], p0_r[2],
            p1_r[0], p1_r[1], p1_r[2],
        ])

    return flat_edges


def extract_mesh_payload(scene: Any) -> Dict[str, Any]:
    """
    Extracts vertex positions, face colors, exact edge lines, and bounding statistics
    from an IngeTrazo scene matching its native visual appearance.
    """
    faces = collect_scene_faces(scene)
    edge_lines = collect_scene_edges(scene, faces)

    positions: List[float] = []
    colors: List[float] = []
    face_count = 0

    for f in faces:
        triangles: List[Any] = []

        # Check native face.triangulate()
        if hasattr(f, "triangulate") and callable(f.triangulate):
            try:
                triangles = list(f.triangulate())
            except Exception:
                triangles = []

        # Fallback to points / vertices attribute or iterating face directly
        if not triangles:
            pts: List[Any] = []
            if hasattr(f, "points"):
                pts = list(f.points() if callable(f.points) else f.points)
            elif hasattr(f, "vertices"):
                pts = list(f.vertices() if callable(f.vertices) else f.vertices)
            elif hasattr(f, "__iter__") and not isinstance(f, (str, bytes)):
                pts = list(f)

            if pts:
                triangles = triangulate_polygon(pts)

        if not triangles:
            continue

        # Extract color
        attrs = getattr(f, "attrs", {})
        col = INGETRAZO_DEFAULT_FRONT_COLOR
        if isinstance(attrs, dict):
            col = _parse_color(attrs.get("color"))
        elif hasattr(f, "color"):
            col = _parse_color(getattr(f, "color"))

        r, g, b = col

        for tri in triangles:
            if len(tri) < 3:
                continue
            try:
                p0 = _extract_pt_coords(tri[0])
                p1 = _extract_pt_coords(tri[1])
                p2 = _extract_pt_coords(tri[2])
            except Exception:
                continue

            # Append 3 vertices (9 floats)
            positions.extend([
                round(p0[0], 5), round(p0[1], 5), round(p0[2], 5),
                round(p1[0], 5), round(p1[1], 5), round(p1[2], 5),
                round(p2[0], 5), round(p2[1], 5), round(p2[2], 5),
            ])

            # Append matching vertex colors (3 vertices * 3 floats)
            colors.extend([r, g, b, r, g, b, r, g, b])
            face_count += 1

    return {
        "vertices": positions,
        "colors": colors,
        "edges": edge_lines,
        "faceCount": face_count,
        "edgeCount": len(edge_lines) // 6,
        "vertexCount": len(positions) // 3,
    }


def export_to_html(
    scene: Any,
    output_path: Union[str, Path],
    title: str = "IngeTrazo Model",
    embed_threejs: bool = True,
) -> Dict[str, Any]:
    """
    Exports the IngeTrazo scene into a standalone Three.js HTML file
    faithfully reproducing IngeTrazo's native rendering style.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    payload = extract_mesh_payload(scene)

    plugin_dir = Path(__file__).resolve().parent
    template_path = plugin_dir / "template.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Viewer template not found: {template_path}")

    html_content = template_path.read_text(encoding="utf-8")

    # Read Three.js and OrbitControls
    res_dir = plugin_dir / "resources"
    three_file = res_dir / "three.min.js"
    orbit_file = res_dir / "OrbitControls.js"

    three_code = ""
    orbit_code = ""

    if embed_threejs and three_file.exists() and orbit_file.exists():
        three_code = three_file.read_text(encoding="utf-8")
        orbit_code = orbit_file.read_text(encoding="utf-8")
    else:
        # Fallback to CDN tags
        three_code = "/* Loaded via CDN */\nconsole.log('Loading Three.js via CDN...');"
        orbit_code = "/* Loaded via CDN */"
        cdn_header = """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
        """
        html_content = html_content.replace("</head>", f"{cdn_header}\n</head>")

    # Replace placeholders
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    json_data = json.dumps(payload, separators=(",", ":"))

    html_content = html_content.replace("__MODEL_TITLE__", title)
    html_content = html_content.replace("__MODEL_DATE__", today_str)
    html_content = html_content.replace("/* __THREE_JS__ */", three_code)
    html_content = html_content.replace("/* __ORBIT_CONTROLS__ */", orbit_code)
    html_content = html_content.replace("/* __MODEL_DATA__ */", json_data)

    out_file.write_text(html_content, encoding="utf-8")

    file_size = out_file.stat().st_size

    return {
        "success": True,
        "file_path": str(out_file),
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "face_count": payload["faceCount"],
        "edge_count": payload["edgeCount"],
        "vertex_count": payload["vertexCount"],
    }
