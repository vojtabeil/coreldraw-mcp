"""Document management tools — open templates, create/save/close documents, page management"""

from core.connection import get_connection, save_document_as
from core.models import ToolResult

_CDR_MILLIMETER = 3
_UNIT_MAP = {"mm": _CDR_MILLIMETER, "cm": 4, "inch": 1, "pt": 14, "px": 5}


def _get_page_size(doc):
    """Read the current page size (mm)"""
    try:
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0.0, 0.0


def _get_page(doc, page_index: int):
    """Return a CorelDRAW page by 1-based index."""
    return doc.Pages(page_index)


def open_template(path: str) -> ToolResult:
    """Open a CDR template file. path is the absolute path to the template file."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _open():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Template file does not exist: {path}")
        doc = conn.app.OpenDocument(path)
        doc.Unit = _CDR_MILLIMETER
        width, height = _get_page_size(doc)
        return {"path": path, "pages": doc.Pages.Count, "width": width, "height": height}

    result = conn.safe_call(_open)
    if result["success"]:
        return ToolResult.ok(f"Template opened: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to open template"))


def create_document(width: float, height: float, unit: str = "mm") -> ToolResult:
    """Create a new CorelDRAW document of the given size. width/height are the document size; unit supports mm/cm/inch/pt/px."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _create():
        doc = conn.app.CreateDocument()
        cdr_unit = _UNIT_MAP.get(unit.lower(), _CDR_MILLIMETER)
        doc.Unit = cdr_unit
        page = doc.ActivePage
        page.SetSize(width, height)
        return {"width": width, "height": height, "unit": unit, "pages": 1}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"New document created: {width}×{height} {unit}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to create document"))


def save_document(path: str = "") -> ToolResult:
    """Save the current document. If path is empty, save to the original path; otherwise save as the given path."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _save():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        if path:
            save_document_as(conn.app, doc, path)
            saved_path = path
        else:
            doc.Save()
            saved_path = doc.FilePath + doc.FileName if doc.FilePath else "Untitled.cdr"
        return {"path": saved_path}

    result = conn.safe_call(_save)
    if result["success"]:
        return ToolResult.ok(f"Document saved: {result['result']['path']}")
    return ToolResult.fail(result.get("error", "Failed to save document"))


def close_document() -> ToolResult:
    """Close the current document. Reports whether there were unsaved changes."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _close():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        name = doc.FileName or "Untitled"
        modified = doc.Modified if hasattr(doc, "Modified") else False
        doc.Close()
        return {"name": name, "had_unsaved_changes": modified}

    result = conn.safe_call(_close)
    if result["success"]:
        info = result["result"]
        msg = f"Closed: {info['name']}"
        if info.get("had_unsaved_changes"):
            msg += " (had unsaved changes)"
        return ToolResult.ok(msg, **info)
    return ToolResult.fail(result.get("error", "Failed to close document"))


def add_page() -> ToolResult:
    """Add a new page at the end of the current document and activate it."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _add():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        doc.AddPages(1)
        page = doc.Pages.Last
        page.Activate()
        width, height = _get_page_size(doc)
        return {"page_index": page.Index, "total_pages": doc.Pages.Count, "width": width, "height": height}

    result = conn.safe_call(_add)
    if result["success"]:
        return ToolResult.ok("New page added", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to add page"))


def set_page_size(width: float, height: float) -> ToolResult:
    """Change the current page size (mm)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _set():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        page.SetSize(width, height)
        return {"width": width, "height": height, "unit": "mm"}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"Page size set to: {width}×{height} mm", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to set page size"))


def get_document_info() -> ToolResult:
    """Get status info for the current document: path, page count, size, shape count, etc."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _info():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        width, height = _get_page_size(doc)

        shapes_count = 0
        text_shapes = 0
        try:
            shapes = page.Shapes
            shapes_count = shapes.Count
            for s in shapes:
                if s.Type == 3:  # cdrTextShape
                    text_shapes += 1
        except Exception:
            pass

        layers_info = []
        try:
            for layer in page.Layers:
                layers_info.append({
                    "name": layer.Name,
                    "visible": layer.Visible if hasattr(layer, "Visible") else True,
                    "editable": layer.Editable if hasattr(layer, "Editable") else True,
                })
        except Exception:
            pass

        return {
            "name": doc.FileName or "Untitled",
            "path": doc.FilePath or "",
            "pages": doc.Pages.Count,
            "current_page": page.Index,
            "width": round(width, 2),
            "height": round(height, 2),
            "unit": "mm",
            "shapes_count": shapes_count,
            "text_shapes_count": text_shapes,
            "layers": layers_info,
        }

    result = conn.safe_call(_info)
    if result["success"]:
        return ToolResult.ok("Document info retrieved", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to get document info"))


def list_all_text_shapes(page_index: int = 0, content_preview_len: int = 40) -> ToolResult:
    """List all text shapes on the given page of the current document.
    For each shape returns name, shape_id, text_type (artistic/paragraph/curve),
    writable (whether it can be written via set_text_content), content_preview,
    and position and size (x, y, width, height, in mm).
    page_index=0 means the current page; other values are page numbers (1-based).
    Use before a batch merge to confirm the real IDs, positions and writability of title block/placeholder shapes.
    """
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _list():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        if page_index == 0:
            page = doc.ActivePage
        else:
            page = _get_page(doc, page_index)

        items = []
        for s in page.Shapes:
            # Determine whether this is a text shape: Type==3 fast path, otherwise duck-typing
            is_text = False
            try:
                is_text = s.Type == 3
            except Exception:
                pass
            if not is_text:
                try:
                    _ = s.Text.Story
                    is_text = True
                except Exception:
                    pass
            if not is_text:
                continue

            item = {"name": "", "shape_id": "", "text_type": "unknown",
                    "writable": False, "content_preview": "",
                    "x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
            try:
                item["name"] = s.Name or ""
            except Exception:
                pass
            try:
                item["shape_id"] = str(s.StaticID)
            except Exception:
                pass
            try:
                item["x"] = round(s.PositionX, 2)
                item["y"] = round(s.PositionY, 2)
                item["width"] = round(s.SizeWidth, 2)
                item["height"] = round(s.SizeHeight, 2)
            except Exception:
                pass

            # Distinguish artistic text / paragraph text / converted to curves
            try:
                t = s.Text
                story = t.Story
                item["writable"] = True
                item["content_preview"] = (story[:content_preview_len] + "…"
                                           if len(story) > content_preview_len else story)
                try:
                    item["text_type"] = "paragraph" if t.Type == 1 else "artistic"
                except Exception:
                    item["text_type"] = "artistic"
            except Exception:
                item["text_type"] = "curve"  # converted to curves, not writable
                item["writable"] = False

            items.append(item)

        writable = sum(1 for x in items if x["writable"])
        return {"page": page.Index, "total": len(items),
                "writable": writable, "shapes": items}

    result = conn.safe_call(_list)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(
            f"Page {r['page']}: {r['total']} text shapes, {r['writable']} writable",
            **r,
        )
    return ToolResult.fail(result.get("error", "Failed to list text shapes"))


def add_guideline(position: float, orientation: str = "horizontal") -> ToolResult:
    """Add a guideline to the current page. position is the guideline position (mm); orientation is horizontal or vertical."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _add():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        orientation_lower = orientation.lower()
        if orientation_lower not in ("horizontal", "vertical"):
            raise ValueError("orientation must be horizontal or vertical")

        try:
            if orientation_lower == "horizontal":
                guide = page.ActiveLayer.CreateGuide(0, position, page.SizeWidth, position)
            else:
                guide = page.ActiveLayer.CreateGuide(position, 0, position, page.SizeHeight)
        except Exception:
            try:
                guides = page.Guides
                if orientation_lower == "horizontal":
                    guide = guides.Add(position, 0)
                else:
                    guide = guides.Add(position, 90)
            except Exception:
                raise RuntimeError(f"Unable to add {orientation} guideline")

        data = {"position": position, "orientation": orientation_lower}
        try:
            data["shape_id"] = str(guide.StaticID)
        except Exception:
            pass
        return data

    result = conn.safe_call(_add)
    if result["success"]:
        return ToolResult.ok(f"Added {orientation} guideline: {position} mm", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to add guideline"))


def switch_page(page_index: int) -> ToolResult:
    """Switch to the given page. page_index is the page number (1-based)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _switch():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        if page_index < 1 or page_index > doc.Pages.Count:
            raise ValueError(f"Page number {page_index} out of range (1-{doc.Pages.Count})")
        page = _get_page(doc, page_index)
        page.Activate()
        doc.Unit = _CDR_MILLIMETER
        width, height = _get_page_size(doc)
        return {"page_index": page_index, "width": width, "height": height}

    result = conn.safe_call(_switch)
    if result["success"]:
        return ToolResult.ok(f"Switched to page {page_index}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to switch page"))


def delete_page(page_index: int) -> ToolResult:
    """Delete the given page. page_index is the page number (1-based)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _delete():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("No document is open")
        if doc.Pages.Count <= 1:
            raise RuntimeError("Cannot delete the last page")
        if page_index < 1 or page_index > doc.Pages.Count:
            raise ValueError(f"Page number {page_index} out of range (1-{doc.Pages.Count})")
        page = _get_page(doc, page_index)
        page.Delete()
        return {"remaining_pages": doc.Pages.Count}

    result = conn.safe_call(_delete)
    if result["success"]:
        return ToolResult.ok(f"Deleted page {page_index}, {result['result']['remaining_pages']} pages remaining", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to delete page"))
