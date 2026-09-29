"""Color and fill tools — CMYK/RGB/Pantone fills, outlines, color checks"""

from core.connection import get_connection
from core.models import ToolResult

_CDR_TEXT_SHAPE = 6
_FILL_MAP = {"cmyk": 0, "rgb": 1, "pantone": 2}


def _find_shape(shape_id: str):
    """Find a shape by name or StaticID"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if not doc:
        return None
    target = str(shape_id)
    try:
        shapes = doc.ActivePage.Shapes
        try:
            return shapes(shape_id)
        except Exception:
            for s in shapes:
                try:
                    if str(s.StaticID) == target or s.Name == target:
                        return s
                except Exception:
                    continue
        return None
    except Exception:
        return None


def set_fill_cmyk(c: float, m: float, y: float, k: float, shape_id: str = "") -> ToolResult:
    """Set a CMYK fill color on a shape. If shape_id is empty, applies to the selected shapes."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"Shape not found: {shape_id}")
            shape.Fill.UniformColor.CMYKAssign(c, m, y, k)
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("No shapes selected; specify shape_id or select shapes first")
            for s in sel.Shapes:
                try:
                    s.Fill.UniformColor.CMYKAssign(c, m, y, k)
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection", "cmyk": [c, m, y, k]}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"CMYK fill: C{c} M{m} Y{y} K{k}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set CMYK fill"))


def set_fill_rgb(r: int, g: int, b: int, shape_id: str = "") -> ToolResult:
    """Set an RGB fill color on a shape. If shape_id is empty, applies to the selected shapes."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"Shape not found: {shape_id}")
            shape.Fill.UniformColor.RGBAssign(r, g, b)
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("No shapes selected")
            for s in sel.Shapes:
                try:
                    s.Fill.UniformColor.RGBAssign(r, g, b)
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection", "rgb": [r, g, b]}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"RGB fill: ({r}, {g}, {b})", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set RGB fill"))


def set_fill_pantone(shape_id: str, pantone_code: str) -> ToolResult:
    """Set a Pantone spot color fill on a shape. pantone_code e.g. '485 C'."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _fill():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        # Pantone fill requires the Color object's FindPantone or a similar method
        # Try NamedColor or a Pantone lookup via the Application
        try:
            pantone_color = conn.app.CreateRGBColor(0, 0, 0)
            pantone_color.FindPantone(pantone_code)
            shape.Fill.ApplyUniformFill(pantone_color)
        except Exception:
            try:
                color = conn.app.CreateCMYKColor(0, 0, 0, 0)
                color.FindPantone(pantone_code)
                shape.Fill.ApplyUniformFill(color)
            except Exception:
                raise RuntimeError(f"Unable to apply Pantone color: {pantone_code}")
        return {"shape_id": shape_id, "pantone": pantone_code}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"Pantone fill: {pantone_code}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set Pantone fill"))


def set_outline(shape_id: str, width: float, color: str = "", color_mode: str = "CMYK") -> ToolResult:
    """Set a shape's outline width (mm) and color. color format: CMYK e.g. '0,100,100,0', RGB e.g. '255,0,0'.
    color_mode: CMYK (default) or RGB. Empty color keeps the current outline color."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _outline():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        shape.Outline.Width = width
        if color:
            parts = [float(x.strip()) for x in color.split(",")]
            if color_mode.upper() == "CMYK" or len(parts) == 4:
                c, m, y, k = parts
                shape.Outline.Color.CMYKAssign(c, m, y, k)
            elif color_mode.upper() == "RGB" or len(parts) == 3:
                r, g, b = [int(x) for x in parts]
                shape.Outline.Color.RGBAssign(r, g, b)
        return {"shape_id": shape_id, "width": width, "color": color, "color_mode": color_mode}

    result = conn.safe_call(_outline)
    if result["success"]:
        return ToolResult.ok(f"Outline: {width}mm, color={color or 'unchanged'}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set outline"))


def set_no_fill(shape_id: str = "") -> ToolResult:
    """Remove a shape's fill (make it hollow). If shape_id is empty, applies to the selected shapes."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _no_fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"Shape not found: {shape_id}")
            shape.Fill.ApplyNoFill()
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("No shapes selected")
            for s in sel.Shapes:
                try:
                    s.Fill.ApplyNoFill()
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection"}

    result = conn.safe_call(_no_fill)
    if result["success"]:
        return ToolResult.ok("Fill removed", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to remove fill"))


def set_no_outline(shape_id: str = "") -> ToolResult:
    """Remove a shape's outline. If shape_id is empty, applies to the selected shapes."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _no_outline():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"Shape not found: {shape_id}")
            shape.Outline.SetNoOutline()
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("No shapes selected")
            for s in sel.Shapes:
                try:
                    s.Outline.SetNoOutline()
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection"}

    result = conn.safe_call(_no_outline)
    if result["success"]:
        return ToolResult.ok("Outline removed", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to remove outline"))


def check_rgb_colors() -> ToolResult:
    """Detect RGB colors in the document (for preflight; print output requires CMYK)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _check():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        page = doc.ActivePage
        rgb_items = []
        try:
            for s in page.Shapes:
                try:
                    fill_type = s.Fill.Type
                    if fill_type == 1:  # cdrUniformFill
                        try:
                            color = s.Fill.UniformColor
                            if color.Type == 1:  # RGB
                                rgb_items.append({
                                    "name": s.Name,
                                    "type": "fill",
                                    "color": f"R{color.RGBAssign}",
                                })
                        except Exception:
                            pass
                    if s.Outline.Type == 1:
                        try:
                            color = s.Outline.Color
                            if color.Type == 1:
                                rgb_items.append({
                                    "name": s.Name,
                                    "type": "outline",
                                    "color": f"R{color.RGBRed} G{color.RGBGreen} B{color.RGBBlue}",
                                })
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        return {"found": len(rgb_items), "items": rgb_items, "passed": len(rgb_items) == 0}

    result = conn.safe_call(_check)
    if result["success"]:
        r = result["result"]
        if r["passed"]:
            return ToolResult.ok("No RGB colors found, safe to print", **r)
        return ToolResult.ok(f"Found {r['found']} RGB color(s), converting to CMYK is recommended", **r)
    return ToolResult.fail(result.get("error", "RGB check failed"))


def set_fountain_fill(
    shape_id: str,
    fill_type: str,
    c1: float, m1: float, y1: float, k1: float,
    c2: float, m2: float, y2: float, k2: float,
    angle: float = 45.0
) -> ToolResult:
    """Set a fountain fill (gradient) on a shape. fill_type: linear/radial/conical/square.
    Start (c1, m1, y1, k1) and end (c2, m2, y2, k2) colors are CMYK. angle in degrees (default 45)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _fill():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        # CorelDRAW fountain fill constants: linear=1, radial=2, conical=3, square=4.
        type_map = {"linear": 1, "radial": 2, "conical": 3, "square": 4}
        ftype = type_map.get(fill_type.lower())
        if ftype is None:
            raise ValueError(f"Invalid fountain fill type: {fill_type}, supported: linear/radial/conical/square")
        start_color = conn.app.CreateCMYKColor(c1, m1, y1, k1)
        end_color = conn.app.CreateCMYKColor(c2, m2, y2, k2)
        shape.Fill.ApplyFountainFill(start_color, end_color, ftype, angle)
        return {
            "shape_id": shape_id,
            "fill_type": fill_type,
            "from_cmyk": [c1, m1, y1, k1],
            "to_cmyk": [c2, m2, y2, k2],
            "angle": angle
        }

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"Fountain fill: {fill_type}, C{c1}M{y1}Y{y1}K{k1} → C{c2}M{m2}Y{y2}K{k2}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set fountain fill"))


def set_transparency(shape_id: str, opacity: float) -> ToolResult:
    """Set a shape's transparency. opacity: 0-100, 0 = fully transparent, 100 = opaque."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _transparency():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        if opacity < 0 or opacity > 100:
            raise ValueError("opacity must be between 0 and 100")
        transparency = int(round(100 - opacity))
        shape.Transparency.ApplyUniformTransparency(transparency)
        return {"shape_id": shape_id, "opacity": opacity}

    result = conn.safe_call(_transparency)
    if result["success"]:
        return ToolResult.ok(f"Transparency: opacity {opacity}%", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set transparency"))
