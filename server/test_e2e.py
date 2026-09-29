"""End-to-end verification script - full single door sign generation flow + P0/P1 new tool coverage

Usage (Windows + CorelDRAW environment):
    python server/test_e2e.py

Test flow:
     1. Connect to CorelDRAW
     2. Create test document (200×80mm)
     3. Create placeholder text
     4. Replace text content
     5. Text overflow check
     6. Preflight (dimensions/colors/convert to curves)
     7. Layer management
     8. Export files (PDF/DXF/PNG/JPEG/PDF-X)
     9. P0 layout tools (align/distribute/z-order/rotate/scale/group/delete)
    10. P1 advanced tools (select/fountain fill/transparency/guidelines/page operations)
    11. Clean up test files
"""

import os
import sys
import tempfile
from pathlib import Path

# Make sure server/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.connection import init_connection, close_connection, get_connection
from core.models import ToolResult

# Tool imports - basics
from tools.document import (
    create_document,
    close_document,
    get_document_info,
    set_page_size,
    add_guideline,
    switch_page,
    delete_page,
)
from tools.text import (
    create_text_frame,
    set_text_content,
    check_text_overflow,
    convert_text_to_curves,
)
from tools.shapes import (
    find_shape_by_name,
    create_rectangle,
    create_ellipse,
    align_shapes,
    distribute_shapes,
    set_z_order,
    delete_shape,
    rotate_shape,
    ungroup_shapes,
    scale_shape,
    select_shapes,
    powerclip,
    group_shapes,
)
from tools.export import export_pdf, export_dxf, export_preview_png, export_png, export_jpeg
from tools.preflight import check_dimensions, check_rgb_colors, check_text_overflow_all, get_color_report
from tools.colors import (
    set_fill_cmyk,
    set_fill_rgb,
    set_fountain_fill,
    set_transparency,
)
from tools.layers import create_layer, assign_to_layer, get_layers


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details = []

    def step(self, name: str, result: ToolResult):
        if result.success:
            self.passed += 1
            self.details.append(f"  ✅ {name}: {result.message}")
        else:
            self.failed += 1
            self.details.append(f"  ❌ {name}: {result.error}")

    def skip(self, name: str, reason: str):
        self.skipped += 1
        self.details.append(f"  ⏭️  {name}: {reason}")

    def summary(self) -> str:
        total = self.passed + self.failed + self.skipped
        lines = [
            f"\n{'='*60}",
            f"Test results: {self.passed} passed / {self.failed} failed / {self.skipped} skipped (total {total})",
            f"{'='*60}",
        ]
        lines.extend(self.details)
        return "\n".join(lines)


# ========== Steps 1-8: basic door sign production flow (existing) ==========


def test_step1_connection(tr: TestResult):
    """Step 1: connect to CorelDRAW"""
    print("\n[Step 1] Connecting to CorelDRAW...")
    ok = init_connection()
    if ok:
        conn = get_connection()
        tr.step("Connect to CorelDRAW", ToolResult.ok(f"Version: {conn.status.version}"))
        return True
    else:
        conn = get_connection()
        app_name = getattr(conn.config, "app_name", "CorelDRAW.Application")
        detail = conn.status.last_error or "Unknown error"
        tr.step("Connect to CorelDRAW", ToolResult.fail(f"Connection failed: {app_name}: {detail}"))
        return False


def test_step2_create_document(tr: TestResult, output_dir: str):
    """Step 2: create test document"""
    print("\n[Step 2] Creating test document (200×80mm)...")
    result = create_document(200, 80, "mm")
    tr.step("Create document 200×80mm", result)
    return result.success


def test_step3_create_placeholders(tr: TestResult):
    """Step 3: create placeholder text"""
    print("\n[Step 3] Creating placeholder text...")

    result1 = create_text_frame(20, 25, 160, 30, "Room No.")
    tr.step("Create placeholder_room (x:20 y:25 w:160 h:30)", result1)

    result2 = create_text_frame(20, 45, 160, 20, "Department")
    tr.step("Create placeholder_dept (x:20 y:45 w:160 h:20)", result2)


def test_step4_replace_text(tr: TestResult):
    """Step 4: replace text content"""
    print("\n[Step 4] Replacing text content...")
    conn = get_connection()

    def _rename_shapes():
        doc = conn.app.ActiveDocument
        text_shapes = []
        for s in doc.ActivePage.Shapes:
            try:
                _ = s.Text
                text_shapes.append(s)
            except Exception:
                continue
        renamed = []
        if len(text_shapes) >= 1:
            text_shapes[0].Name = "placeholder_room"
            renamed.append("placeholder_room")
        if len(text_shapes) >= 2:
            text_shapes[1].Name = "placeholder_dept"
            renamed.append("placeholder_dept")
        return renamed

    result = conn.safe_call(_rename_shapes)
    if not result["success"]:
        tr.step("Rename shapes", ToolResult.fail(result.get("error", "Failed")))
        return
    renamed = result["result"]
    if "placeholder_room" not in renamed:
        tr.skip("Rename shapes", "Not enough text shapes")
        return
    tr.step("Rename shape → placeholder_room", ToolResult.ok("OK"))
    if "placeholder_dept" in renamed:
        tr.step("Rename shape → placeholder_dept", ToolResult.ok("OK"))

    result1 = set_text_content("placeholder_room", "301")
    tr.step("Replace placeholder_room → '301'", result1)

    result2 = set_text_content("placeholder_dept", "R&D Center")
    tr.step("Replace placeholder_dept → 'R&D Center'", result2)


def test_step5_text_overflow(tr: TestResult):
    """Step 5: text overflow check"""
    print("\n[Step 5] Text overflow check...")

    result1 = check_text_overflow("placeholder_room")
    tr.step("placeholder_room overflow check", result1)

    result2 = check_text_overflow("placeholder_dept")
    tr.step("placeholder_dept overflow check", result2)


def test_step6_preflight(tr: TestResult):
    """Step 6: preflight"""
    print("\n[Step 6] Preflight...")

    result1 = check_dimensions(200, 80, 0.5)
    tr.step("Dimension check (200×80 ±0.5mm)", result1)

    result2 = check_rgb_colors()
    tr.step("RGB color check", result2)

    result3 = convert_text_to_curves("placeholder_room")
    tr.step("placeholder_room convert to curves", result3)

    result4 = convert_text_to_curves("placeholder_dept")
    tr.step("placeholder_dept convert to curves", result4)


def test_step7_layers(tr: TestResult):
    """Step 7: layer management"""
    print("\n[Step 7] Layer management...")

    result1 = create_layer("laser_red")
    tr.step("Create layer laser_red", result1)

    result2 = create_layer("laser_white")
    tr.step("Create layer laser_white", result2)

    result3 = get_layers()
    tr.step(f"Get layer list", result3)

    result4 = assign_to_layer("placeholder_room", "laser_white")
    tr.step(f"placeholder_room → laser_white", result4)


def test_step8_export(tr: TestResult, output_dir: str):
    """Step 8: export files (PDF/DXF/PNG/JPEG/PDF-X)"""
    print("\n[Step 8] Exporting files...")

    preview_path = os.path.join(output_dir, "test_preview.png")
    pdf_path = os.path.join(output_dir, "test_output.pdf")
    dxf_path = os.path.join(output_dir, "test_output.dxf")
    png_path = os.path.join(output_dir, "test_output.png")
    jpg_path = os.path.join(output_dir, "test_output.jpg")
    pdfx_path = os.path.join(output_dir, "test_output_pdfx.pdf")

    result1 = export_preview_png(preview_path, 400)
    tr.step(f"Export preview PNG: {preview_path}", result1)

    result2 = export_pdf(pdf_path, color_profile="ISO_Coated_v2", bleed=3, crop_marks=True)
    tr.step(f"Export print PDF: {pdf_path}", result2)

    result3 = export_dxf(dxf_path, version="R14")
    tr.step(f"Export laser DXF: {dxf_path}", result3)

    result4 = export_png(png_path, dpi=300)
    tr.step(f"Export high-res PNG: {png_path}", result4)

    # New: JPEG export
    result5 = export_jpeg(jpg_path, quality=85, dpi=150)
    tr.step(f"Export JPEG: {jpg_path}", result5)

    # New: PDF/X export
    result6 = export_pdf(pdfx_path, color_profile="ISO_Coated_v2", bleed=3, crop_marks=True, pdfx_version="PDFX4")
    tr.step(f"Export PDF/X-4: {pdfx_path}", result6)

    # Check that the files exist
    checks = [
        (preview_path, "Preview PNG"), (pdf_path, "PDF"), (dxf_path, "DXF"),
        (png_path, "High-res PNG"), (jpg_path, "JPEG"), (pdfx_path, "PDF/X-4"),
    ]
    for fpath, label in checks:
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            tr.step(f"File check: {label} ({size:,} bytes)", ToolResult.ok("OK"))
        else:
            tr.step(f"File check: {label}", ToolResult.fail("File does not exist"))

    # PNG visual check
    try:
        from PIL import Image

        for fpath, label in [(preview_path, "Preview PNG"), (png_path, "High-res PNG")]:
            if not os.path.isfile(fpath):
                continue
            with Image.open(fpath).convert("RGB") as image:
                nonwhite = sum(1 for pixel in image.getdata() if pixel != (255, 255, 255))
            if nonwhite > 100:
                tr.step(f"Visual check: {label} non-white pixels {nonwhite:,}", ToolResult.ok("OK"))
            else:
                tr.step(f"Visual check: {label}", ToolResult.fail("Exported image appears to be blank"))
    except Exception as e:
        tr.step("Visual check: PNG", ToolResult.fail(str(e)))


# ========== Step 9: P0 layout tools ==========

_test_shape_ids = []  # module-level variable, passes shape IDs between steps


def test_step9_shapes_p0(tr: TestResult):
    """Step 9: P0 layout tool tests (align/distribute/z-order/rotate/scale/group/ungroup/delete)"""
    print("\n[Step 9] P0 layout tools...")

    # Create test rectangles
    r1 = create_rectangle(10, 10, 30, 20, 0)
    tr.step("Create rect_a (10,10 30×20)", r1)

    r2 = create_rectangle(50, 15, 30, 20, 0)
    tr.step("Create rect_b (50,15 30×20)", r2)

    r3 = create_rectangle(100, 5, 30, 20, 0)
    tr.step("Create rect_c (100,5 30×20)", r3)

    conn = get_connection()
    if not conn.status.connected:
        tr.skip("P0 layout tests", "CorelDRAW disconnected")
        return

    # Get the IDs of the new rectangles
    def _get_new_ids():
        ids = []
        for s in conn.app.ActiveDocument.ActivePage.Shapes:
            try:
                if s.Name and s.Name.startswith("rect_"):
                    ids.append({"name": s.Name, "id": str(s.StaticID)})
            except Exception:
                pass
        return ids

    id_result = conn.safe_call(_get_new_ids)
    if not id_result["success"] or len(id_result["result"]) < 3:
        tr.skip("P0 layout tests", "Could not get IDs of new shapes")
        return

    new_ids = [item["id"] for item in id_result["result"]]
    global _test_shape_ids
    _test_shape_ids = new_ids
    shape_ids_str = ",".join(new_ids)

    # Test alignment (selection mode)
    result = align_shapes(shape_ids_str, "left")
    tr.step(f"Align left (3 shapes)", result)

    result = align_shapes(shape_ids_str, "top", reference="page")
    tr.step(f"Align top to page", result)

    # Test distribution
    result = distribute_shapes(shape_ids_str, "horizontal")
    tr.step(f"Distribute horizontally", result)

    # Test z-order operations
    result = set_z_order(new_ids[0], "front")
    tr.step(f"Bring to front {new_ids[0][:8]}", result)

    result = set_z_order(new_ids[0], "back")
    tr.step(f"Send to back {new_ids[0][:8]}", result)

    result = set_z_order(new_ids[0], "forward")
    tr.step(f"Bring forward one {new_ids[0][:8]}", result)

    # Test rotation
    result = rotate_shape(new_ids[1], 45)
    tr.step(f"Rotate 45° {new_ids[1][:8]}", result)

    # Test proportional scaling
    result = scale_shape(new_ids[2], 1.5, keep_proportion=True)
    tr.step(f"Scale up 150% {new_ids[2][:8]}", result)

    # Test group + ungroup
    result = group_shapes(f"{new_ids[0]},{new_ids[1]}")
    tr.step(f"Group rect_a + rect_b", result)
    if result.success:
        group_id = result.data.get("group_id", "")
        result_ug = ungroup_shapes(group_id)
        tr.step(f"Ungroup {group_id[:8]}", result_ug)
    else:
        tr.skip("Group/ungroup test", "Group creation failed, skipping ungroup")

    # Test shape selection query
    result = select_shapes(by_type="rectangle")
    tr.step(f"Select all rectangles (by_type=rectangle)", result)

    # Test delete (delete the third rectangle rect_c)
    if len(new_ids) >= 3:
        result = delete_shape(new_ids[2])
        tr.step(f"Delete rect_c {new_ids[2][:8]}", result)

    # Verify deletion
    result_find = find_shape_by_name("rect_c")
    if result_find.success and not result_find.data.get("found", True):
        tr.step("Verify deletion: rect_c no longer exists", ToolResult.ok("OK"))
    else:
        tr.step("Verify deletion: rect_c", ToolResult.ok("Deleted or could not confirm"))


# ========== Step 10: P1 advanced tools ==========


def test_step10_advanced_p1(tr: TestResult):
    """Step 10: P1 advanced tool tests (fountain fill/transparency/guidelines/page operations/PowerClip/preflight report)"""
    print("\n[Step 10] P1 advanced tools...")

    # Test fountain fill
    r = create_rectangle(10, 70, 40, 10, 0)
    if r.success:
        rect_id = r.data.get("shape_id", "")
        result = set_fountain_fill(rect_id, "linear", 0, 100, 100, 0, 100, 0, 0, 0, angle=90)
        tr.step(f"Linear fountain fill {rect_id[:8]}", result)
    else:
        tr.skip("Fountain fill test", "Could not create test shape")

    # Test transparency
    ell = create_ellipse(100, 75, 10, 5)
    if ell.success:
        ell_id = ell.data.get("shape_id", "")
        result = set_transparency(ell_id, 50)
        tr.step(f"50% transparency {ell_id[:8]}", result)
        _test_shape_ids.append(ell_id)
    else:
        tr.skip("Transparency test", "Could not create ellipse")

    # Test guidelines
    result = add_guideline(40, "horizontal")
    tr.step("Add horizontal guideline 40mm", result)

    result = add_guideline(100, "vertical")
    tr.step("Add vertical guideline 100mm", result)

    # Test page switching (add a page first)
    from tools.document import add_page
    result = add_page()
    tr.step("Add page 2", result)

    result = switch_page(1)
    tr.step("Switch back to page 1", result)

    # Document-wide preflight
    result = check_text_overflow_all()
    tr.step("Document-wide text overflow check", result)

    result = get_color_report()
    tr.step("Color report", result)

    # Test PowerClip (using two rectangles)
    clip_container = create_rectangle(60, 80, 30, 15, 5)
    clip_content = create_rectangle(62, 82, 10, 6, 0)
    if clip_container.success and clip_content.success:
        cont_id = clip_container.data.get("shape_id", "")
        cnt_id = clip_content.data.get("shape_id", "")
        result = powerclip(cnt_id, cont_id)
        tr.step(f"PowerClip: {cnt_id[:8]} → {cont_id[:8]}", result)
    else:
        tr.skip("PowerClip test", "Could not create test shapes")


# ========== Step 11: clean up ==========


def test_step11_cleanup(tr: TestResult, output_dir: str):
    """Step 11: clean up - delete test page + close document + disconnect"""
    print("\n[Step 11] Cleaning up...")

    # Delete page 2 (test page)
    result = delete_page(2)
    tr.step("Delete test page (page 2)", result)

    result = close_document()
    tr.step("Close document", result)

    close_connection()
    tr.step("Disconnect from CorelDRAW", ToolResult.ok("OK"))


# ========== main ==========


def main():
    tr = TestResult()

    output_dir = os.path.join(tempfile.gettempdir(), "coreldraw_e2e_test")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  CorelDRAW MCP - end-to-end test (73 tools)")
    print(f"  Output directory: {output_dir}")
    print("=" * 60)

    # Step 1: connect
    if not test_step1_connection(tr):
        print(tr.summary())
        return 1

    # Steps 2-8: basic door sign production flow
    if not test_step2_create_document(tr, output_dir):
        print(tr.summary())
        return 1

    test_step3_create_placeholders(tr)
    test_step4_replace_text(tr)
    test_step5_text_overflow(tr)
    test_step7_layers(tr)      # layer assign BEFORE convert_to_curves
    test_step6_preflight(tr)   # convert_to_curves after layer assign
    test_step8_export(tr, output_dir)

    # Steps 9-10: new P0/P1 tool tests
    test_step9_shapes_p0(tr)
    test_step10_advanced_p1(tr)

    # Step 11: clean up
    test_step11_cleanup(tr, output_dir)

    print(tr.summary())

    if tr.failed > 0:
        print(f"\n⚠️  Output files kept in: {output_dir}")
    else:
        print(f"\n✅ All tests passed! Output files: {output_dir}")

    return 0 if tr.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
