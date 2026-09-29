"""Data merge tools — Excel data reading, batch merge, barcode/QR code generation"""

import os
import tempfile

from core.connection import get_connection, import_file, save_document_as
from core.models import ToolResult


def read_excel_data(path: str, sheet: int = 0, has_header: bool = True) -> ToolResult:
    """Read an Excel data source (.xlsx/.xls/.csv) and return a list of row records.
    sheet is the worksheet index (0-based). has_header: the first row contains column names."""
    try:
        import pandas as pd
    except ImportError:
        return ToolResult.fail("pandas is not installed, run: pip install pandas openpyxl xlrd")

    if not os.path.isfile(path):
        return ToolResult.fail(f"File does not exist: {path}")

    try:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        elif ext == ".xls":
            df = pd.read_excel(path, sheet_name=sheet, engine="xlrd")
        elif ext == ".csv":
            df = pd.read_csv(path)
        else:
            return ToolResult.fail(f"Unsupported file format: {ext}, supported: .xlsx/.xls/.csv")

        if has_header:
            records = df.to_dict(orient="records")
        else:
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
            records = df.to_dict(orient="records")

        # Convert NaN etc. to None
        clean_records = []
        for r in records:
            clean = {}
            for k, v in r.items():
                if pd.isna(v):
                    clean[k] = ""
                else:
                    clean[k] = str(v) if not isinstance(v, (int, float, bool, str)) else v
            clean_records.append(clean)

        return ToolResult.ok(
            f"Read succeeded: {len(clean_records)} records",
            path=path,
            sheet=sheet,
            total=len(clean_records),
            records=clean_records,
            columns=list(df.columns),
        )
    except Exception as e:
        return ToolResult.fail(f"Failed to read Excel: {e}")


def merge_record(template_path: str, data: dict, output_path: str) -> ToolResult:
    """Merge a single record: open the template, replace placeholders from the data dict, save to output_path.
    data keys correspond to placeholder (text shape) names."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _merge():
        doc = conn.app.OpenDocument(template_path)
        page = doc.ActivePage
        replaced = {}
        for key, value in data.items():
            try:
                shapes = page.Shapes
                for s in shapes:
                    try:
                        if s.Type == 3 and s.Name == key:  # cdrTextShape
                            s.Text.Story = str(value)
                            replaced[key] = str(value)[:30]
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        dirpath = os.path.dirname(output_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        save_document_as(conn.app, doc, output_path)
        doc.Close()
        return {"template": template_path, "output": output_path, "replaced": replaced}

    result = conn.safe_call(_merge)
    if result["success"]:
        cnt = len(result["result"]["replaced"])
        return ToolResult.ok(f"Merge finished: {cnt} replacement(s) → {output_path}", **result["result"])
    return ToolResult.fail(result.get("error", "Data merge failed"))


def batch_merge(template_path: str, data_path: str, output_dir: str, naming_pattern: str = "{room}") -> ToolResult:
    """Batch merge: read data from Excel and generate one file per record. naming_pattern supports {col_name} placeholders."""
    from core.connection import get_connection

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    # Read the data first
    read_result = read_excel_data(data_path)
    if not read_result.success:
        return ToolResult.fail(read_result.error or "Failed to read data source")

    records = read_result.data["records"]
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for i, record in enumerate(records):
        try:
            filename = naming_pattern
            for key, value in record.items():
                filename = filename.replace("{" + key + "}", str(value))
            filename = filename.format(**record) if "{" in filename else filename
        except Exception:
            filename = f"output_{i:03d}"
        output_path = os.path.join(output_dir, f"{filename}.cdr")

        merge_result = merge_record(template_path, record, output_path)
        results.append({
            "index": i,
            "filename": f"{filename}.cdr",
            "success": merge_result.success,
            "error": merge_result.error if not merge_result.success else "",
        })

    succeeded = sum(1 for r in results if r["success"])
    return ToolResult.ok(
        f"Batch merge finished: {succeeded}/{len(results)} succeeded",
        output_dir=output_dir,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )


def generate_barcode(barcode_type: str, data: str, x: float, y: float, width: float, height: float) -> ToolResult:
    """Generate a barcode and import it into CorelDRAW. barcode_type: code128/ean13/code39.
    x, y: position; width, height: size."""
    try:
        import barcode
        from barcode.writer import SVGWriter
    except ImportError:
        return ToolResult.fail("python-barcode is not installed, run: pip install python-barcode")

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _generate():
        type_map = {"code128": "code128", "ean13": "ean13", "code39": "code39"}
        if barcode_type not in type_map:
            raise ValueError(f"Unsupported barcode type: {barcode_type}, options: {', '.join(type_map.keys())}")

        bc_class = barcode.get_barcode_class(barcode_type)
        bc = bc_class(data, writer=SVGWriter())

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            svg_path = tmp.name
        try:
            bc.save(svg_path.replace(".svg", ""))
            final_svg = svg_path.replace(".svg", "") + ".svg" if os.path.exists(svg_path.replace(".svg", "") + ".svg") else svg_path
            if os.path.exists(final_svg):
                doc = conn.app.ActiveDocument
                import_file(conn.app, doc, final_svg)
                page = doc.ActivePage
                shapes = page.Shapes
                if shapes.Count > 0:
                    last_shape = shapes.Last
                    last_shape.SetPosition(x, y)
                    last_shape.SetSize(width, height)
                    last_shape.Name = f"barcode_{barcode_type}_{data}"
                    return {
                        "shape_id": str(last_shape.StaticID),
                        "type": barcode_type,
                        "data": data,
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                    }
            raise RuntimeError("Barcode SVG generation failed")
        finally:
            for f in [svg_path, svg_path.replace(".svg", "") + ".svg"]:
                try:
                    os.remove(f)
                except Exception:
                    pass

    result = conn.safe_call(_generate)
    if result["success"]:
        return ToolResult.ok(f"Barcode generated: {barcode_type} - {data}", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to generate barcode"))


def generate_qrcode(data: str, x: float, y: float, size: float) -> ToolResult:
    """Generate a QR code and import it into CorelDRAW. x, y: position; size: side length."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ToolResult.fail("qrcode is not installed, run: pip install qrcode[pil]")

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW is not connected")

    def _generate():
        factory = qrcode.image.svg.SvgImage
        qr = qrcode.QRCode(version=None, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(image_factory=factory)

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            svg_path = tmp.name
        try:
            img.save(svg_path)
            doc = conn.app.ActiveDocument
            import_file(conn.app, doc, svg_path)
            page = doc.ActivePage
            shapes = page.Shapes
            if shapes.Count > 0:
                last_shape = shapes.Last
                last_shape.SetPosition(x, y)
                last_shape.SetSize(size, size)
                last_shape.Name = f"qrcode_{data[:20]}"
                return {
                    "shape_id": str(last_shape.StaticID),
                    "type": "qr",
                    "data": data,
                    "x": x,
                    "y": y,
                    "size": size,
                }
            raise RuntimeError("QR code import failed")
        finally:
            try:
                os.remove(svg_path)
            except Exception:
                pass

    result = conn.safe_call(_generate)
    if result["success"]:
        return ToolResult.ok(f"QR code generated: {data[:30]}...", **result["result"])
    return ToolResult.fail(result.get("error", "Failed to generate QR code"))
