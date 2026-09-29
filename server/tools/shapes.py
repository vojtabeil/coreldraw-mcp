"""Shape tools - create/find/modify shapes, boolean operations, asset import, align/distribute/z-order/rotate/scale"""

from core.connection import get_connection, import_file
from core.models import ToolResult


def _static_id(shape) -> str:
    """Return CorelDRAW StaticID in the string form expected by tools."""
    return str(shape.StaticID)


def _shape_matches(shape, shape_id: str) -> bool:
    target = str(shape_id)
    try:
        if str(shape.StaticID) == target:
            return True
    except Exception:
        pass
    try:
        return shape.Name == target
    except Exception:
        return False


def _create_shape_range(shapes):
    conn = get_connection()
    shape_range = conn.app.CreateShapeRange()
    for shape in shapes:
        shape_range.Add(shape)
    return shape_range


def _find_shape(shape_id: str):
    """Find a shape by name or StaticID. Returns the Shape object or None."""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if not doc:
        return None
    try:
        page = doc.ActivePage
        shapes = page.Shapes
        # Try lookup by name first
        try:
            return shapes(shape_id)
        except Exception:
            pass
        # Iterate and match
        for s in shapes:
            if _shape_matches(s, shape_id):
                return s
        return None
    except Exception:
        return None


def _shape_info(shape) -> dict:
    """Extract shape info"""
    try:
        info = {
            "name": shape.Name if shape.Name else "",
            "type": shape.Type,
            "width": round(shape.SizeWidth, 2),
            "height": round(shape.SizeHeight, 2),
        }
        try:
            info["center_x"] = round(shape.CenterX, 2)
            info["center_y"] = round(shape.CenterY, 2)
        except Exception:
            pass
        return info
    except Exception:
        return {"name": "", "type": -1}


def create_rectangle(x: float, y: float, width: float, height: float, corner_radius: float = 0) -> ToolResult:
    """Create a rectangle. x,y are the top-left corner coordinates; supports rounded corners (corner_radius)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        r = corner_radius if corner_radius > 0 else 0
        shape = layer.CreateRectangle(x, y, x + width, y + height, r, r, r, r)
        shape.Name = f"rect_{shape.StaticID}"
        return {"shape_id": _static_id(shape), **_shape_info(shape), "corner_radius": corner_radius}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"Rectangle created: {width}×{height}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create rectangle"))


def create_ellipse(cx: float, cy: float, rx: float, ry: float) -> ToolResult:
    """Create an ellipse. cx,cy are the center coordinates; rx,ry are the X/Y radii."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        left = cx - rx
        top = cy - ry
        right = cx + rx
        bottom = cy + ry
        shape = layer.CreateEllipse(left, top, right, bottom)
        shape.Name = f"ellipse_{shape.StaticID}"
        return {"shape_id": _static_id(shape), **_shape_info(shape), "rx": rx, "ry": ry}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"Ellipse created: rx={rx}, ry={ry}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create ellipse"))


def create_line(x1: float, y1: float, x2: float, y2: float) -> ToolResult:
    """Create a straight line segment."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        shape = layer.CreateLineSegment(x1, y1, x2, y2)
        shape.Name = f"line_{shape.StaticID}"
        return {"shape_id": _static_id(shape), **_shape_info(shape), "x1": x1, "y1": y1, "x2": x2, "y2": y2}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok("Line created", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create line"))


def import_svg(path: str, x: float = 0, y: float = 0) -> ToolResult:
    """Import an SVG file into the current document. Returns info about the imported shape."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _import():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"SVG file does not exist: {path}")
        doc = conn.app.ActiveDocument
        import_file(conn.app, doc, path)
        if x != 0 or y != 0:
            try:
                shapes = doc.ActivePage.Shapes
                if shapes.Count > 0:
                    last_shape = shapes.Last
                    last_shape.SetPosition(x, y)
                    return {"path": path, "shape_id": _static_id(last_shape), **_shape_info(last_shape), "x": x, "y": y}
            except Exception:
                pass
        return {"path": path, "status": "imported"}

    result = conn.safe_call(_import)
    if result["success"]:
        return ToolResult.ok(f"SVG imported: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to import SVG"))


def import_image(path: str, x: float = 0, y: float = 0, width: float = 0, height: float = 0) -> ToolResult:
    """Import a bitmap into the current document. Position and size can be specified."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _import():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Image file does not exist: {path}")
        doc = conn.app.ActiveDocument
        import_file(conn.app, doc, path)
        try:
            shapes = doc.ActivePage.Shapes
            if shapes.Count > 0:
                last_shape = shapes.Last
                if x != 0 or y != 0:
                    last_shape.SetPosition(x, y)
                if width > 0 and height > 0:
                    last_shape.SetSize(width, height)
                return {"path": path, "shape_id": _static_id(last_shape), **_shape_info(last_shape), "x": x, "y": y}
        except Exception:
            pass
        return {"path": path, "status": "imported"}

    result = conn.safe_call(_import)
    if result["success"]:
        return ToolResult.ok(f"Image imported: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to import image"))


def set_shape_size(shape_id: str, width: float, height: float) -> ToolResult:
    """Set the exact size of a shape (mm)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _set():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        shape.SetSize(width, height)
        return {"shape_id": shape_id, "width": width, "height": height}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"Shape size set to: {width}×{height} mm", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set size"))


def set_shape_position(shape_id: str, x: float, y: float) -> ToolResult:
    """Set the position of a shape (mm)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _set():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        shape.SetPosition(x, y)
        return {"shape_id": shape_id, "x": x, "y": y}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"Shape moved to: ({x}, {y})", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set position"))


_BOOLEAN_OPS = {"union": "Weld", "intersect": "Intersect", "subtract": "Trim", "exclude": "Simplify"}


def boolean_operation(shape_ids: str, operation: str) -> ToolResult:
    """Perform a boolean operation on the given shapes. shape_ids is a comma-separated list of IDs; operation supports union/intersect/subtract/exclude."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    if operation not in _BOOLEAN_OPS:
        return ToolResult.fail(f"Unsupported boolean operation: {operation}, options: {', '.join(_BOOLEAN_OPS.keys())}")

    def _operate():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 2:
            raise ValueError("A boolean operation requires at least two shapes")
        page = conn.app.ActiveDocument.ActivePage
        selected = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"Shape not found: {sid}")
            selected.append(shape)
        selection = _create_shape_range(selected)
        method = getattr(selection, _BOOLEAN_OPS[operation])
        method()
        return {"operation": operation, "input_ids": ids, "result": "success"}

    result = conn.safe_call(_operate)
    if result["success"]:
        return ToolResult.ok(f"Boolean operation done: {operation}", **result["result"])
    return ToolResult.fail(result.get("error", "Boolean operation failed"))


def convert_to_curves(shape_id: str) -> ToolResult:
    """Convert a shape to curves (required step before print production)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _convert():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        shape.ConvertToCurves()
        return {"shape_id": shape_id, "converted": True}

    result = conn.safe_call(_convert)
    if result["success"]:
        return ToolResult.ok(f"Converted to curves: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to convert to curves"))


def group_shapes(shape_ids: str) -> ToolResult:
    """Group multiple shapes into one group. shape_ids is a comma-separated list of IDs."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _group():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 2:
            raise ValueError("Grouping requires at least two shapes")
        page = conn.app.ActiveDocument.ActivePage
        selected = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"Shape not found: {sid}")
            selected.append(shape)
        group = _create_shape_range(selected).Group()
        return {"group_id": _static_id(group), "member_count": len(ids), "member_ids": ids}

    result = conn.safe_call(_group)
    if result["success"]:
        return ToolResult.ok(f"Grouped {result['result']['member_count']} shapes", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to group"))


def find_shape_by_name(name: str) -> ToolResult:
    """Find a shape by name. Returns the shape's ID, type, size, etc."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _find():
        shape = _find_shape(name)
        if shape is None:
            return {"found": False, "name": name}
        return {"found": True, **_shape_info(shape), "shape_id": _static_id(shape)}

    result = conn.safe_call(_find)
    if result["success"]:
        if result["result"]["found"]:
            return ToolResult.ok(f"Shape found: {name}", **result["result"])
        return ToolResult.ok(f"Shape not found: {name}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to find shape"))


# ========== P0 layout essentials ==========

_ALIGN_DIRECTIONS = {"left", "center", "right", "top", "middle", "bottom"}
_Z_ORDER_ACTIONS = {"front", "back", "forward", "backward"}
_CDR_MILLIMETER = 3


def _get_shape_bounds(shape):
    """Get a shape's bounds (position + size) for align/distribute calculations. Returns a dict or None."""
    try:
        x = shape.PositionX
        y = shape.PositionY
        w = shape.SizeWidth
        h = shape.SizeHeight
        return {
            "x": x, "y": y, "w": w, "h": h,
            "center_x": x + w / 2, "center_y": y + h / 2,
            "right": x + w, "bottom": y + h,
        }
    except Exception:
        return None


def _get_page_size(doc):
    """Get the width and height of the current page (mm)."""
    try:
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0, 0


def align_shapes(shape_ids: str, alignment: str, reference: str = "selection") -> ToolResult:
    """Align multiple shapes. alignment: left/center/right/top/middle/bottom.
    reference='selection' aligns the shapes to each other; reference='page' aligns them to the page edges.
    shape_ids is a comma-separated list of shape IDs or names."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    alignment = alignment.lower()
    if alignment not in _ALIGN_DIRECTIONS:
        return ToolResult.fail(f"Unsupported alignment: {alignment}, options: {', '.join(sorted(_ALIGN_DIRECTIONS))}")

    def _align():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if not ids:
            raise ValueError("Please provide at least one shape ID")

        shapes = []
        bounds = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"Shape not found: {sid}")
            b = _get_shape_bounds(shape)
            if b is None:
                raise ValueError(f"Cannot read position info of shape {sid}")
            shapes.append(shape)
            bounds.append(b)

        if reference == "page":
            page_w, page_h = _get_page_size(conn.app.ActiveDocument)
            for shape, b in zip(shapes, bounds):
                if alignment == "left":
                    shape.SetPosition(0, b["y"])
                elif alignment == "center":
                    new_x = (page_w - b["w"]) / 2
                    shape.SetPosition(new_x, b["y"])
                elif alignment == "right":
                    shape.SetPosition(page_w - b["w"], b["y"])
                elif alignment == "top":
                    shape.SetPosition(b["x"], 0)
                elif alignment == "middle":
                    new_y = (page_h - b["h"]) / 2
                    shape.SetPosition(b["x"], new_y)
                elif alignment == "bottom":
                    shape.SetPosition(b["x"], page_h - b["h"])
        else:
            # selection mode: align the other shapes to the first shape
            if len(shapes) < 2:
                raise ValueError("selection mode requires at least two shapes (or use reference='page')")
            ref_bounds = bounds[0]
            for shape, b in zip(shapes[1:], bounds[1:]):
                if alignment == "left":
                    shape.SetPosition(ref_bounds["x"], b["y"])
                elif alignment == "center":
                    new_x = ref_bounds["center_x"] - b["w"] / 2
                    shape.SetPosition(new_x, b["y"])
                elif alignment == "right":
                    shape.SetPosition(ref_bounds["right"] - b["w"], b["y"])
                elif alignment == "top":
                    shape.SetPosition(b["x"], ref_bounds["y"])
                elif alignment == "middle":
                    new_y = ref_bounds["center_y"] - b["h"] / 2
                    shape.SetPosition(b["x"], new_y)
                elif alignment == "bottom":
                    shape.SetPosition(b["x"], ref_bounds["bottom"] - b["h"])

        return {"shape_count": len(shapes), "alignment": alignment, "reference": reference}

    result = conn.safe_call(_align)
    if result["success"]:
        return ToolResult.ok(f"Alignment done: {alignment} ({reference})", **result["result"])
    return ToolResult.fail(result.get("error", "Alignment failed"))


def distribute_shapes(shape_ids: str, direction: str = "horizontal", spacing: float = 0) -> ToolResult:
    """Distribute multiple shapes evenly. direction: horizontal/vertical. If spacing>0, a fixed spacing is used;
    otherwise shapes are spread evenly between the minimum and maximum bounds. shape_ids is comma-separated."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    direction = direction.lower()
    if direction not in ("horizontal", "vertical"):
        return ToolResult.fail("direction only supports 'horizontal' or 'vertical'")

    def _distribute():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 3:
            raise ValueError("Distribution requires at least three shapes")

        shapes = []
        bounds = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"Shape not found: {sid}")
            b = _get_shape_bounds(shape)
            if b is None:
                raise ValueError(f"Cannot read position info of shape {sid}")
            shapes.append(shape)
            bounds.append(b)

        if direction == "horizontal":
            # Sort by X
            pairs = sorted(zip(shapes, bounds), key=lambda p: p[1]["x"])
            if spacing > 0:
                # Fixed spacing, starting from the first shape
                ref_x = pairs[0][1]["x"]
                for i, (shape, b) in enumerate(pairs):
                    new_x = ref_x + i * spacing
                    shape.SetPosition(new_x, b["y"])
            else:
                # Even distribution: total span / (n-1)
                min_x = pairs[0][1]["x"]
                max_x = pairs[-1][1]["x"] + pairs[-1][1]["w"]
                total_span = max_x - min_x
                if len(pairs) > 1:
                    step = total_span / (len(pairs) - 1)
                else:
                    step = 0
                for i, (shape, b) in enumerate(pairs[1:-1]):
                    target_center_x = min_x + (i + 1) * step - b["w"] / 2
                    shape.SetPosition(target_center_x, b["y"])
        else:
            # Sort by Y
            pairs = sorted(zip(shapes, bounds), key=lambda p: p[1]["y"])
            if spacing > 0:
                ref_y = pairs[0][1]["y"]
                for i, (shape, b) in enumerate(pairs):
                    new_y = ref_y + i * spacing
                    shape.SetPosition(b["x"], new_y)
            else:
                min_y = pairs[0][1]["y"]
                max_y = pairs[-1][1]["y"] + pairs[-1][1]["h"]
                total_span = max_y - min_y
                if len(pairs) > 1:
                    step = total_span / (len(pairs) - 1)
                else:
                    step = 0
                for i, (shape, b) in enumerate(pairs[1:-1]):
                    target_center_y = min_y + (i + 1) * step - b["h"] / 2
                    shape.SetPosition(b["x"], target_center_y)

        return {"shape_count": len(shapes), "direction": direction, "spacing": spacing}

    result = conn.safe_call(_distribute)
    if result["success"]:
        return ToolResult.ok(f"Distribution done: {direction} ({result['result']['shape_count']} shapes)", **result["result"])
    return ToolResult.fail(result.get("error", "Distribution failed"))


def set_z_order(shape_id: str, action: str) -> ToolResult:
    """Change a shape's stacking order. action: front (bring to front)/back (send to back)/forward (forward one)/backward (back one)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    action = action.lower()
    if action not in _Z_ORDER_ACTIONS:
        return ToolResult.fail(f"Unsupported z-order action: {action}, options: {', '.join(sorted(_Z_ORDER_ACTIONS))}")

    def _order():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        if action == "front":
            shape.OrderToFront()
        elif action == "back":
            shape.OrderToBack()
        elif action == "forward":
            shape.OrderForwardOne()
        elif action == "backward":
            shape.OrderBackOne()
        return {"shape_id": shape_id, "action": action}

    result = conn.safe_call(_order)
    if result["success"]:
        action_names = {"front": "bring to front", "back": "send to back", "forward": "forward one", "backward": "back one"}
        return ToolResult.ok(f"Z-order changed: {shape_id} → {action_names.get(action, action)}", **result["result"])
    return ToolResult.fail(result.get("error", "Z-order action failed"))


def delete_shape(shape_id: str) -> ToolResult:
    """Delete the specified shape."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _delete():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        name = shape.Name or shape_id
        shape.Delete()
        return {"shape_id": shape_id, "name": name, "deleted": True}

    result = conn.safe_call(_delete)
    if result["success"]:
        return ToolResult.ok(f"Deleted: {result['result']['name']}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to delete shape"))


def rotate_shape(shape_id: str, angle: float, center_x: float = 0, center_y: float = 0) -> ToolResult:
    """Rotate a shape. angle is the rotation angle (degrees, positive = counterclockwise); center_x/center_y is the rotation center (0 = the shape's own center)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _rotate():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        old_angle = 0.0
        try:
            old_angle = shape.RotationAngle
        except Exception:
            pass
        if center_x != 0 or center_y != 0:
            try:
                # Try to set the rotation center (supported in CorelDRAW X6+)
                shape.RotationCenterX = center_x
                shape.RotationCenterY = center_y
            except Exception:
                pass
        shape.RotationAngle = angle
        return {"shape_id": shape_id, "angle": angle, "old_angle": round(old_angle, 2)}

    result = conn.safe_call(_rotate)
    if result["success"]:
        return ToolResult.ok(f"Shape rotated: {shape_id} → {angle}°", **result["result"])
    return ToolResult.fail(result.get("error", "Rotation failed"))


def ungroup_shapes(shape_id: str, recursive: bool = False) -> ToolResult:
    """Ungroup. shape_id is the ID of the group shape; recursive=True ungroups all nested subgroups recursively."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _ungroup():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        # Check whether it is a group
        try:
            is_group = shape.Type == 7  # cdrGroupShape
        except Exception:
            is_group = False
        if not is_group:
            # duck-type: try to read child shapes
            try:
                _ = shape.Shapes
                is_group = True
            except Exception:
                pass
        if not is_group:
            raise ValueError(f"Shape {shape_id} is not a group")

        if recursive:
            try:
                shape.UngroupAll()
            except Exception:
                shape.Ungroup()
        else:
            shape.Ungroup()
        return {"shape_id": shape_id, "recursive": recursive, "ungrouped": True}

    result = conn.safe_call(_ungroup)
    if result["success"]:
        detail = "Ungrouped recursively" if recursive else "Ungrouped"
        return ToolResult.ok(f"{detail}: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to ungroup"))


def scale_shape(shape_id: str, scale_x: float, scale_y: float = 0, keep_proportion: bool = False) -> ToolResult:
    """Scale a shape proportionally or non-proportionally. scale_x is the X scale factor (1.0 = original size,
    2.0 = double). scale_y is the Y scale factor; 0 means same as scale_x (proportional).
    keep_proportion=True ignores scale_y and forces proportional scaling."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    if scale_x <= 0:
        return ToolResult.fail(f"Scale factor must be greater than 0, got scale_x={scale_x}")

    scale_y = scale_y if scale_y > 0 else scale_x

    def _scale():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        old_w = shape.SizeWidth
        old_h = shape.SizeHeight
        new_w = old_w * scale_x
        new_h = old_h * (scale_x if keep_proportion else scale_y)
        # Scale while keeping the center point fixed
        cx = shape.PositionX + old_w / 2
        cy = shape.PositionY + old_h / 2
        shape.SetSize(new_w, new_h)
        shape.SetPosition(cx - new_w / 2, cy - new_h / 2)
        return {
            "shape_id": shape_id,
            "scale_x": scale_x,
            "scale_y": scale_x if keep_proportion else scale_y,
            "old_size": {"width": round(old_w, 2), "height": round(old_h, 2)},
            "new_size": {"width": round(new_w, 2), "height": round(new_h, 2)},
        }

    result = conn.safe_call(_scale)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(
            f"Scaled: {r['old_size']['width']}×{r['old_size']['height']} "
            f"→ {r['new_size']['width']}×{r['new_size']['height']}",
            **r,
        )
    return ToolResult.fail(result.get("error", "Scaling failed"))


# ========== P1 enhanced tools ==========


def select_shapes(by_type: str = "", by_layer: str = "", by_name_pattern: str = "") -> ToolResult:
    """Select shapes by criteria and return the list of matching shapes.
    by_type: rectangle/ellipse/curve/text/bitmap/group, etc.
    by_layer: layer name
    by_name_pattern: shapes whose name contains this string

    Does not change the actual selection in CorelDRAW; only returns the matching list for use by other tools."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    _TYPE_MAP = {
        "rectangle": 1, "ellipse": 2, "curve": 4, "text": 3,
        "bitmap": 6, "group": 7, "line": 1, "polygon": 5,
    }

    def _select():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        page = doc.ActivePage
        matched = []

        for s in page.Shapes:
            # Filter by layer
            if by_layer:
                try:
                    if s.Layer.Name != by_layer:
                        continue
                except Exception:
                    continue

            # Filter by type
            if by_type:
                type_lower = by_type.lower()
                expected = _TYPE_MAP.get(type_lower, -1)
                try:
                    if expected >= 0 and s.Type != expected:
                        continue
                except Exception:
                    continue

            # Filter by name pattern
            if by_name_pattern:
                try:
                    name = s.Name or ""
                    if by_name_pattern.lower() not in name.lower():
                        continue
                except Exception:
                    continue

            # Extract shape info
            info = _shape_info(s)
            info["shape_id"] = ""
            try:
                info["shape_id"] = str(s.StaticID)
            except Exception:
                pass
            try:
                info["layer"] = s.Layer.Name
            except Exception:
                info["layer"] = ""
            matched.append(info)

        return {"count": len(matched), "shapes": matched, "criteria": {
            "by_type": by_type, "by_layer": by_layer, "by_name_pattern": by_name_pattern,
        }}

    result = conn.safe_call(_select)
    if result["success"]:
        r = result["result"]
        criteria_parts = []
        if by_type:
            criteria_parts.append(f"type={by_type}")
        if by_layer:
            criteria_parts.append(f"layer={by_layer}")
        if by_name_pattern:
            criteria_parts.append(f"name contains '{by_name_pattern}'")
        return ToolResult.ok(f"Found {r['count']} matching shapes ({', '.join(criteria_parts)})", **r)
    return ToolResult.fail(result.get("error", "Failed to select shapes"))


def powerclip(content_shape_id: str, container_shape_id: str) -> ToolResult:
    """Place the content shape inside the container shape (PowerClip).
    Similar to a clipping mask in Illustrator; used to confine graphics/text to a specific area."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _clip():
        content = _find_shape(content_shape_id)
        if content is None:
            raise ValueError(f"Content shape not found: {content_shape_id}")
        container = _find_shape(container_shape_id)
        if container is None:
            raise ValueError(f"Container shape not found: {container_shape_id}")

        placed = False
        for method in (
            lambda: content.AddToPowerClip(container, -2),
            lambda: _create_shape_range([content]).AddToPowerClip(container, -2),
            lambda: content.CreatePowerClip(container),
            lambda: container.PowerClip.Place(content),
            lambda: conn.app.ActiveDocument.CreatePowerClip(content, container),
        ):
            try:
                method()
                placed = True
                break
            except Exception:
                continue

        if not placed:
            raise RuntimeError("This CorelDRAW version does not support any known PowerClip API")

        return {
            "content_id": content_shape_id,
            "container_id": container_shape_id,
            "powerclip_created": True,
        }

    result = conn.safe_call(_clip)
    if result["success"]:
        return ToolResult.ok(
            f"PowerClip: {content_shape_id} → {container_shape_id}",
            **result["result"],
        )
    return ToolResult.fail(result.get("error", "PowerClip operation failed"))
