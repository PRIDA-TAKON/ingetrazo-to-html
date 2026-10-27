"""
Exporter engine: Extracts 3D mesh geometry, materials, textures, and exact polygon edge lines
from IngeTrazo scene and generates standalone Three.js HTML viewers that match IngeTrazo's
exact visual style with full texture support.
"""

import base64
from datetime import datetime
import json
import math
import os
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


def compute_planar_uv(
    normal: Tuple[float, float, float],
    points: List[Tuple[float, float, float]],
    sw: float = 1.0,
    sh: float = 1.0,
    rot: float = 0.0,
) -> List[Tuple[float, float]]:
    """
    Computes .skp-style planar UV projection matching IngeTrazo core.texture.planar_uv.
    """
    try:
        from core.texture import planar_uv as native_planar_uv  # type: ignore
        return list(native_planar_uv(normal, points, sw, sh, rot))
    except Exception:
        pass

    # Pure Python implementation of IngeTrazo's projection basis
    nx, ny, nz = normal
    cx = -ny
    cy = nx
    L = math.sqrt(cx * cx + cy * cy)

    if L < 1e-3:
        if nz > 0:
            xr = (1.0, 0.0, 0.0)
            yr = (0.0, 1.0, 0.0)
        else:
            xr = (-1.0, 0.0, 0.0)
            yr = (0.0, 1.0, 0.0)
    else:
        xr = (cx / L, cy / L, 0.0)
        yr = (-nx * nz / L, -ny * nz / L, L)

    rad = math.radians(rot)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    u_axis = (xr[0] * cos_a - yr[0] * sin_a, xr[1] * cos_a - yr[1] * sin_a, xr[2] * cos_a - yr[2] * sin_a)
    v_axis = (xr[0] * sin_a + yr[0] * cos_a, xr[1] * sin_a + yr[1] * cos_a, xr[2] * sin_a + yr[2] * cos_a)

    sw_val = sw if sw > 0 else 1.0
    sh_val = sh if sh > 0 else 1.0

    uvs: List[Tuple[float, float]] = []
    for p in points:
        u = (p[0] * u_axis[0] + p[1] * u_axis[1] + p[2] * u_axis[2]) / sw_val
        v = (p[0] * v_axis[0] + p[1] * v_axis[1] + p[2] * v_axis[2]) / sh_val
        uvs.append((round(u, 5), round(v, 5)))
    return uvs


def compute_affine_uv(
    uvw: Any,
    points: List[Tuple[float, float, float]],
) -> List[Tuple[float, float]]:
    """Evaluates fitted affine UV coordinates matching core.texture.affine_uv."""
    try:
        from core.texture import affine_uv as native_affine_uv  # type: ignore
        return list(native_affine_uv(uvw, points))
    except Exception:
        pass

    uvs: List[Tuple[float, float]] = []
    if isinstance(uvw, (list, tuple)) and len(uvw) >= 8:
        ux, uy, uz, uc = uvw[0], uvw[1], uvw[2], uvw[3]
        vx, vy, vz, vc = uvw[4], uvw[5], uvw[6], uvw[7]
        for p in points:
            u = ux * p[0] + uy * p[1] + uz * p[2] + uc
            v = vx * p[0] + vy * p[1] + vz * p[2] + vc
            uvs.append((round(u, 5), round(v, 5)))
    else:
        for _ in points:
            uvs.append((0.0, 0.0))
    return uvs


def _resolve_texture_path(src: Optional[str], scene: Any = None) -> Optional[Path]:
    """Resolves texture source path against disk, texture cache, and document paths."""
    if not src:
        return None

    cand = Path(src)
    if cand.is_file():
        return cand.resolve()

    # Search in IngeTrazo texture cache root
    cache_roots = []
    try:
        from core.texture import texture_cache_root  # type: ignore
        cache_roots.append(texture_cache_root())
    except Exception:
        pass

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        cache_roots.append(Path(local_app_data) / "IngeTrazo" / "textures")
        cache_roots.append(Path(local_app_data) / "IngeTrazo")

    app_data = os.environ.get("APPDATA")
    if app_data:
        cache_roots.append(Path(app_data) / "ingetrazo" / "textures")

    home = Path.home()
    cache_roots.append(home / ".local" / "share" / "IngeTrazo" / "textures")

    # Document directory if available
    doc_path = getattr(scene, "path", None)
    if doc_path:
        cache_roots.append(Path(doc_path).parent)

    for root in cache_roots:
        if not root or not root.exists():
            continue
        p1 = root / cand
        if p1.is_file():
            return p1.resolve()
        p2 = root / cand.name
        if p2.is_file():
            return p2.resolve()
        # Search skp and embedded subfolders
        p_skp = root / "skp" / cand.name
        if p_skp.is_file():
            return p_skp.resolve()
        p_emb = root / "embedded" / cand.name
        if p_emb.is_file():
            return p_emb.resolve()

    return None


def _image_to_base64_data_uri(img_path: Path) -> str:
    """Reads image file and encodes into Base64 Data URI."""
    data = img_path.read_bytes()
    ext = img_path.suffix.lower()
    mime = "image/png"
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".svg":
        mime = "image/svg+xml"

    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


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
    Extracts vertex positions, face colors, full texture maps with UVs, and
    deduplicated edge lines from an IngeTrazo scene matching its native look.
    """
    faces = collect_scene_faces(scene)
    edge_lines = collect_scene_edges(scene, faces)

    textures_dict: Dict[str, str] = {}         # tex_id -> base64 data URI
    texture_path_to_id: Dict[str, str] = {}    # resolved path string -> tex_id
    next_tex_idx = 0

    # Primitives grouped by material/texture key
    # key: (is_textured, tex_id, col_tuple, opacity)
    grouped_parts: Dict[Any, Dict[str, Any]] = {}

    all_positions: List[float] = []
    all_colors: List[float] = []
    total_face_count = 0

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

        # Extract attributes
        attrs = getattr(f, "attrs", {})
        if not isinstance(attrs, dict):
            attrs = {}

        # 1. Color and Opacity
        col = INGETRAZO_DEFAULT_FRONT_COLOR
        if "color" in attrs:
            col = _parse_color(attrs.get("color"))
        elif hasattr(f, "color"):
            col = _parse_color(getattr(f, "color"))

        opacity = float(attrs.get("opacity", 1.0))

        # 2. Texture extraction
        tex_data = attrs.get("texture")
        tex_id: Optional[str] = None
        sw = 1.0
        sh = 1.0
        rot = 0.0
        uvw = None

        if tex_data is not None:
            raw_src = None
            if isinstance(tex_data, dict):
                raw_src = tex_data.get("path") or tex_data.get("src")
                sw = float(tex_data.get("sw", 1.0))
                sh = float(tex_data.get("sh", 1.0))
                rot = float(tex_data.get("rot", 0.0))
                uvw = tex_data.get("uvw")
            elif hasattr(tex_data, "path"):
                raw_src = getattr(tex_data, "path", None)
                sw = float(getattr(tex_data, "sw", 1.0))
                sh = float(getattr(tex_data, "sh", 1.0))
                rot = float(getattr(tex_data, "rot", 0.0))
                uvw = getattr(tex_data, "uvw", None)
            elif isinstance(tex_data, str):
                raw_src = tex_data

            if raw_src:
                img_path = _resolve_texture_path(str(raw_src), scene)
                if img_path and img_path.is_file():
                    p_str = str(img_path)
                    if p_str in texture_path_to_id:
                        tex_id = texture_path_to_id[p_str]
                    else:
                        tex_id = f"tex_{next_tex_idx}"
                        next_tex_idx += 1
                        texture_path_to_id[p_str] = tex_id
                        try:
                            textures_dict[tex_id] = _image_to_base64_data_uri(img_path)
                        except Exception as e:
                            print(f"[html_export] Warning: Failed to encode texture {img_path}: {e}")
                            tex_id = None

        # Face Normal
        normal = (0.0, 0.0, 1.0)
        if hasattr(f, "normal"):
            n_raw = f.normal() if callable(f.normal) else f.normal
            try:
                normal = _extract_pt_coords(n_raw)
            except Exception:
                pass

        # Determine Material Group Key
        part_key = (tex_id is not None, tex_id, col, round(opacity, 2), sw, sh, rot, uvw is not None)
        if part_key not in grouped_parts:
            grouped_parts[part_key] = {
                "textureId": tex_id,
                "color": [col[0], col[1], col[2]],
                "opacity": opacity,
                "transparent": (opacity < 0.99),
                "vertices": [],
                "uvs": [],
                "colors": [],
            }

        target_part = grouped_parts[part_key]
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

            pts_tri = [p0, p1, p2]

            # Calculate UVs if textured
            tri_uvs: List[Tuple[float, float]] = []
            if tex_id:
                if uvw is not None:
                    tri_uvs = compute_affine_uv(uvw, pts_tri)
                else:
                    tri_uvs = compute_planar_uv(normal, pts_tri, sw, sh, rot)
            else:
                tri_uvs = [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

            # Append to Part
            for i, p in enumerate(pts_tri):
                target_part["vertices"].extend([round(p[0], 5), round(p[1], 5), round(p[2], 5)])
                if tex_id:
                    u, v = tri_uvs[i]
                    target_part["uvs"].extend([round(u, 5), round(v, 5)])
                target_part["colors"].extend([r, g, b])

            # Append to flat lists for statistics & fallback
            all_positions.extend([
                round(p0[0], 5), round(p0[1], 5), round(p0[2], 5),
                round(p1[0], 5), round(p1[1], 5), round(p1[2], 5),
                round(p2[0], 5), round(p2[1], 5), round(p2[2], 5),
            ])
            all_colors.extend([r, g, b, r, g, b, r, g, b])
            total_face_count += 1

    parts_list = list(grouped_parts.values())

    return {
        "parts": parts_list,
        "textures": textures_dict,
        "vertices": all_positions,
        "colors": all_colors,
        "edges": edge_lines,
        "faceCount": total_face_count,
        "edgeCount": len(edge_lines) // 6,
        "vertexCount": len(all_positions) // 3,
        "textureCount": len(textures_dict),
    }


def export_to_html(
    scene: Any,
    output_path: Union[str, Path],
    title: str = "IngeTrazo Model",
    embed_threejs: bool = True,
) -> Dict[str, Any]:
    """
    Exports the IngeTrazo scene into a standalone Three.js HTML file
    faithfully reproducing IngeTrazo's native rendering style with textures.
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
        "texture_count": payload["textureCount"],
    }
