"""Text tools — replace text content, set styles, check overflow, create text frames"""

from core.connection import get_connection
from core.models import ToolResult

_CDR_TEXT_SHAPE = 3
_CDR_PARAGRAPH_TEXT = 1
_CDR_MILLIMETER = 3
# cdrAlignment: cdrNoAlignment=0, cdrLeftAlignment=1, cdrRightAlignment=2, cdrCenterAlignment=3, cdrFullJustifyAlignment=4
_ALIGNMENT_MAP = {"left": 1, "center": 3, "right": 2, "justify": 4, "none": 0}


def _find_text_shape(shape_id: str):
    """Find a text shape, making sure it is of text type"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if doc is None:
        return None
    target = str(shape_id)
    try:
        shapes = doc.ActivePage.Shapes
        try:
            shape = shapes(shape_id)
        except Exception:
            for s in shapes:
                try:
                    if str(s.StaticID) == target or s.Name == target:
                        shape = s
                        break
                except Exception:
                    continue
            else:
                return None
        try:
            if shape.Type == _CDR_TEXT_SHAPE:
                return shape
        except Exception:
            pass
        try:
            _ = shape.Text
        except Exception:
            return None
        return shape
    except Exception:
        return None


def _get_text_content(text) -> str:
    for getter in (
        lambda: text.Contents,
        lambda: text.GetContents(),
        lambda: text.Story.Text,
        lambda: text.Story,
    ):
        try:
            value = getter()
            if isinstance(value, str):
                return value
        except Exception:
            continue
    return ""


def _to_corel_newlines(content: str) -> str:
    """CorelDRAW separates paragraphs with CR; LF is silently dropped."""
    return content.replace("\r\n", "\r").replace("\n", "\r")


def _set_text_content(text, content: str) -> None:
    content = _to_corel_newlines(content)
    for setter in (
        lambda: setattr(text, "Contents", content),
        lambda: text.SetContents(2, content),
        lambda: setattr(text, "Story", content),
    ):
        try:
            setter()
            return
        except Exception:
            continue
    raise RuntimeError("This CorelDRAW version does not support any known API for writing text content")


def _set_text_font(text, font: str) -> None:
    for setter in (
        lambda: setattr(text.Story, "Font", font),
        lambda: setattr(text.FontProperties, "Name", font),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_size(text, size: float) -> None:
    for setter in (
        lambda: setattr(text.Story, "Size", size),
        lambda: setattr(text.FontProperties, "Size", size),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_bold(text, bold: bool) -> None:
    for setter in (
        lambda: setattr(text.Story, "Bold", bold),
        lambda: setattr(text.FontProperties, "Bold", bold),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _apply_default_text_style(shape, frame_height: float) -> None:
    text = shape.Text
    size = max(8.0, min(18.0, frame_height * 0.55))
    _set_text_size(text, size)
    try:
        shape.Fill.UniformColor.CMYKAssign(0, 0, 0, 100)
    except Exception:
        pass


def set_text_content(shape_id: str, content: str) -> ToolResult:
    """Replace the text content of a text shape. shape_id is the shape name or ID."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _set():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"Text shape not found: {shape_id}")
        old_content = _get_text_content(shape.Text)
        _set_text_content(shape.Text, content)
        text_type = "paragraph" if shape.Text.Type == _CDR_PARAGRAPH_TEXT else "artistic"
        return {"shape_id": shape_id, "old_content": old_content, "new_content": content, "text_type": text_type}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"Text replaced: '{result['result']['old_content']}' → '{content}'", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to replace text"))


def set_text_style(
    shape_id: str,
    font: str = "",
    size: float = 0,
    bold: bool = False,
    italic: bool = False,
    alignment: str = "",
) -> ToolResult:
    """Set the style of a text shape: font, size, bold, italic, alignment (left/center/right)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _style():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"Text shape not found: {shape_id}")
        changes = {}
        text = shape.Text
        if font:
            _set_text_font(text, font)
            changes["font"] = font
        if size > 0:
            _set_text_size(text, size)
            changes["size"] = size
        if bold:
            _set_text_bold(text, True)
            changes["bold"] = True
        if italic:
            try:
                text.FontProperties.Italic = True
                changes["italic"] = True
            except Exception:
                pass
        if alignment and alignment in _ALIGNMENT_MAP:
            value = _ALIGNMENT_MAP[alignment]
            for setter in (
                lambda: setattr(text.Story, "Alignment", value),
                lambda: setattr(text, "Alignment", value),
            ):
                try:
                    setter()
                    changes["alignment"] = alignment
                    break
                except Exception:
                    continue
        if not changes:
            raise ValueError("No style changes specified")
        return {"shape_id": shape_id, "changes": changes}

    result = conn.safe_call(_style)
    if result["success"]:
        changes = result["result"]["changes"]
        return ToolResult.ok(f"Text style updated: {changes}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set text style"))


def fit_text_to_frame(shape_id: str) -> ToolResult:
    """Fit paragraph text to its text frame size (paragraph text only)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _fit():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"Text shape not found: {shape_id}")
        if shape.Text.Type != _CDR_PARAGRAPH_TEXT:
            raise ValueError(f"Fit-to-frame only works on paragraph text, current type: {shape.Text.Type}")
        shape.Text.FitTextToFrame = True
        return {"shape_id": shape_id, "fitted": True}

    result = conn.safe_call(_fit)
    if result["success"]:
        return ToolResult.ok(f"Text fitted to frame", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to fit text to frame"))


def check_text_overflow(shape_id: str) -> ToolResult:
    """Check whether text exceeds its text frame (text overflow). Returns the overflow status."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _check():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"Text shape not found: {shape_id}")
        text_type = shape.Text.Type
        overflowing = False
        if text_type == _CDR_PARAGRAPH_TEXT:
            try:
                overflowing = shape.Text.Overflows
            except Exception:
                try:
                    overflowing = shape.Text.IsOverflowing
                except Exception:
                    pass
        content_length = 0
        content_length = len(_get_text_content(shape.Text))
        return {
            "shape_id": shape_id,
            "overflowing": overflowing,
            "text_type": "paragraph" if text_type == _CDR_PARAGRAPH_TEXT else "artistic",
            "content_length": content_length,
        }

    result = conn.safe_call(_check)
    if result["success"]:
        status = "overflow" if result["result"]["overflowing"] else "ok"
        return ToolResult.ok(f"Text status: {status}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to check text overflow"))


def convert_text_to_curves(shape_id: str) -> ToolResult:
    """Convert text to curves (required before print, removes font dependency)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _convert():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"Text shape not found: {shape_id}")
        shape.ConvertToCurves()
        return {"shape_id": shape_id, "converted": True}

    result = conn.safe_call(_convert)
    if result["success"]:
        return ToolResult.ok(f"Text converted to curves: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to convert text to curves"))


def create_text_frame(x: float, y: float, width: float, height: float, text: str) -> ToolResult:
    """Create a paragraph text frame. Returns the shape ID."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        doc = conn.app.ActiveDocument
        doc.Unit = _CDR_MILLIMETER
        layer = doc.ActivePage.ActiveLayer
        left, top = x, y
        right, bottom = x + width, y + height
        shape = layer.CreateParagraphText(left, top, right, bottom, _to_corel_newlines(text))
        _apply_default_text_style(shape, height)
        shape.Name = f"text_{shape.StaticID}"
        return {
            "shape_id": str(shape.StaticID),
            "name": shape.Name,
            "width": width,
            "height": height,
            "x": x,
            "y": y,
            "content": text,
        }

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"Text frame created: {width}×{height}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create text frame"))
