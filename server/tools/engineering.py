"""Engineering drawing tools — title block population, engineering drawing frame assembly"""

import os

from core.connection import get_connection, import_file, save_document_as
from core.models import ToolResult

_CDR_TEXT_SHAPE = 3


def populate_title_block(
    template_path: str,
    project_name: str = "",
    order_no: str = "",
    part_no: str = "",
    designer: str = "",
    material: str = "",
    finish: str = "",
    scale: str = "1:1",
    sheet_no: str = "",
    revision: str = "A",
    output_path: str = "",
) -> ToolResult:
    """Populate an engineering drawing title block. Opens the engineering drawing CDR template, replaces the
    title block field text shapes with the given parameters and saves to output_path (overwrites the template
    if omitted). Shape names must match the field names (e.g. title_project_name)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    if not os.path.isfile(template_path):
        return ToolResult.fail(f"Template file does not exist: {template_path}")

    save_path = output_path or template_path

    fields = {
        "title_project_name": project_name,
        "title_order_no": order_no,
        "title_part_no": part_no,
        "title_designer": designer,
        "title_material": material,
        "title_finish": finish,
        "title_scale": scale,
        "title_sheet_no": sheet_no,
        "title_revision": revision,
    }
    # Only write non-empty fields
    fields = {k: v for k, v in fields.items() if v}

    def _populate():
        doc = conn.app.OpenDocument(template_path)
        page = doc.ActivePage
        replaced = {}
        skipped = []

        for s in page.Shapes:
            try:
                if s.Type == _CDR_TEXT_SHAPE and s.Name in fields:
                    s.Text.Story = str(fields[s.Name])
                    replaced[s.Name] = str(fields[s.Name])
            except Exception:
                skipped.append(s.Name)

        # Iterate all pages (engineering drawings may have multiple pages)
        for pg in doc.Pages:
            if pg.Index == page.Index:
                continue
            try:
                for s in pg.Shapes:
                    if s.Type == _CDR_TEXT_SHAPE and s.Name in fields and s.Name not in replaced:
                        try:
                            s.Text.Story = str(fields[s.Name])
                            replaced[s.Name] = str(fields[s.Name])
                        except Exception:
                            skipped.append(s.Name)
            except Exception:
                pass

        dirpath = os.path.dirname(save_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        save_document_as(conn.app, doc, save_path)
        doc.Close()
        not_found = [k for k in fields if k not in replaced]
        return {
            "output": save_path,
            "replaced": replaced,
            "not_found": not_found,
            "skipped": skipped,
        }

    result = conn.safe_call(_populate)
    if result["success"]:
        r = result["result"]
        cnt = len(r["replaced"])
        msg = f"Title block populated: {cnt} field(s) → {save_path}"
        if r["not_found"]:
            msg += f", {len(r['not_found'])} field(s) with no matching shape: {r['not_found']}"
        return ToolResult.ok(msg, **r)
    return ToolResult.fail(result.get("error", "Title block population failed"))


def assemble_engineering_drawing(
    design_path: str,
    frame_template_path: str,
    output_path: str,
    title_block_fields: dict = None,
) -> ToolResult:
    """Embed a design file into an engineering drawing frame template, producing a complete engineering drawing CDR.
    First populates the title block, then imports the design file contents into the frame's design_zone
    layer/shape area. title_block_fields is a dict of title block fields, keys matching populate_title_block's
    parameters."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    if not os.path.isfile(design_path):
        return ToolResult.fail(f"Design file does not exist: {design_path}")
    if not os.path.isfile(frame_template_path):
        return ToolResult.fail(f"Engineering drawing frame template does not exist: {frame_template_path}")

    fields = title_block_fields or {}

    def _assemble():
        # Open the engineering drawing frame
        doc = conn.app.OpenDocument(frame_template_path)
        page = doc.ActivePage

        # Populate the title block
        replaced_fields = {}
        field_map = {
            "title_project_name": fields.get("project_name", ""),
            "title_order_no": fields.get("order_no", ""),
            "title_part_no": fields.get("part_no", ""),
            "title_designer": fields.get("designer", ""),
            "title_material": fields.get("material", ""),
            "title_finish": fields.get("finish", ""),
            "title_scale": fields.get("scale", "1:1"),
            "title_sheet_no": fields.get("sheet_no", ""),
            "title_revision": fields.get("revision", "A"),
        }
        for s in page.Shapes:
            try:
                if s.Type == _CDR_TEXT_SHAPE and s.Name in field_map and field_map[s.Name]:
                    s.Text.Story = str(field_map[s.Name])
                    replaced_fields[s.Name] = field_map[s.Name]
            except Exception:
                pass

        # Import the design file into the frame
        import_file(conn.app, doc, design_path)

        dirpath = os.path.dirname(output_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        save_document_as(conn.app, doc, output_path)
        doc.Close()
        return {
            "output": output_path,
            "design_imported": design_path,
            "frame_used": frame_template_path,
            "title_block_filled": replaced_fields,
        }

    result = conn.safe_call(_assemble)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"Engineering drawing assembled: {output_path}", **r)
    return ToolResult.fail(result.get("error", "Engineering drawing assembly failed"))
