"""Layer tools - create/lock/show/hide layers, assign shapes to layers"""

from core.connection import get_connection
from core.models import ToolResult


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


def create_layer(name: str, color: str = "") -> ToolResult:
    """Create a new layer. color is used to identify the layer (for the laser machine), e.g. 'red' / 'blue'."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        page = conn.app.ActiveDocument.ActivePage
        layer = page.CreateLayer(name)
        # Ensure layer is visible and printable (X6 defaults can vary)
        for attr in ("Visible", "Printable", "Editable"):
            try:
                setattr(layer, attr, True)
            except Exception:
                pass
        if color:
            try:
                layer.Color = color
            except Exception:
                pass
        return {"name": name, "color": color, "visible": True, "editable": True}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"Layer created: {name}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create layer"))


def get_layers() -> ToolResult:
    """Get info about all layers on the current page."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _list():
        page = conn.app.ActiveDocument.ActivePage
        layers_list = []
        try:
            for layer in page.Layers:
                layer_info = {"name": layer.Name}
                try:
                    layer_info["visible"] = layer.Visible
                except Exception:
                    layer_info["visible"] = True
                try:
                    layer_info["editable"] = layer.Editable
                except Exception:
                    layer_info["editable"] = True
                try:
                    layer_info["locked"] = not layer.Editable
                except Exception:
                    layer_info["locked"] = False
                try:
                    c = layer.Color
                    layer_info["color"] = int(c) if isinstance(c, int) else str(c)
                except Exception:
                    layer_info["color"] = ""
                try:
                    layer_info["shapes_count"] = layer.Shapes.Count
                except Exception:
                    layer_info["shapes_count"] = 0
                layers_list.append(layer_info)
        except Exception:
            pass
        return {"layers": layers_list, "count": len(layers_list)}

    result = conn.safe_call(_list)
    if result["success"]:
        return ToolResult.ok(f"{result['result']['count']} layers in total", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to get layer list"))


def assign_to_layer(shape_id: str, layer_name: str) -> ToolResult:
    """Move a shape to the specified layer."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _assign():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"Shape not found: {shape_id}")
        page = conn.app.ActiveDocument.ActivePage
        target_layer = None
        try:
            target_layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"Layer not found: {layer_name}")
        target_layer.Activate()
        # Move the shape to the target layer
        try:
            shape.MoveToLayer(target_layer)
        except Exception:
            try:
                shape.Layer = target_layer
            except Exception:
                raise RuntimeError(f"Cannot move shape to layer: {layer_name}")
        return {"shape_id": shape_id, "layer": layer_name}

    result = conn.safe_call(_assign)
    if result["success"]:
        return ToolResult.ok(f"Shape moved to layer: {layer_name}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to assign layer"))


def set_layer_visible(layer_name: str, visible: bool) -> ToolResult:
    """Set the visibility of a layer."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _set():
        page = conn.app.ActiveDocument.ActivePage
        try:
            layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"Layer not found: {layer_name}")
        layer.Visible = visible
        return {"layer": layer_name, "visible": visible}

    result = conn.safe_call(_set)
    if result["success"]:
        status = "visible" if visible else "hidden"
        return ToolResult.ok(f"Layer {layer_name} set to {status}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set layer visibility"))


def lock_layer(layer_name: str) -> ToolResult:
    """Lock a layer to prevent accidental edits."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _lock():
        page = conn.app.ActiveDocument.ActivePage
        try:
            layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"Layer not found: {layer_name}")
        layer.Editable = False
        return {"layer": layer_name, "locked": True}

    result = conn.safe_call(_lock)
    if result["success"]:
        return ToolResult.ok(f"Layer locked: {layer_name}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to lock layer"))
