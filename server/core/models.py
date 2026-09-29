"""Pydantic data model definitions"""

from typing import Optional, List, Literal, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ========== Enums ==========


class Unit(str, Enum):
    """Dimension unit"""
    MM = "mm"
    CM = "cm"
    INCH = "inch"
    POINT = "pt"
    PIXEL = "px"


class ColorMode(str, Enum):
    """Color mode"""
    CMYK = "CMYK"
    RGB = "RGB"
    PANTONE = "Pantone"
    SPOT = "Spot"


class ExportFormat(str, Enum):
    """Export format"""
    PDF = "pdf"
    DXF = "dxf"
    AI = "ai"
    SVG = "svg"
    PNG = "png"
    CDR = "cdr"


class BooleanOp(str, Enum):
    """Boolean operation type"""
    UNION = "union"
    INTERSECT = "intersect"
    SUBTRACT = "subtract"
    EXCLUDE = "exclude"


# ========== Document models ==========


class DocumentInfo(BaseModel):
    """Document info"""
    name: Optional[str] = None
    path: Optional[str] = None
    pages: int = 1
    width: float = 0
    height: float = 0
    unit: Unit = Unit.MM
    has_modified: bool = False


class PageInfo(BaseModel):
    """Page info"""
    index: int
    name: Optional[str] = None
    width: float
    height: float
    unit: Unit = Unit.MM


class SizeInput(BaseModel):
    """Size input"""
    width: float = Field(..., gt=0, description="Width")
    height: float = Field(..., gt=0, description="Height")
    unit: Unit = Field(default=Unit.MM, description="Unit")


# ========== Shape models ==========


class RectangleInput(BaseModel):
    """Rectangle creation input"""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    width: float = Field(..., gt=0, description="Width")
    height: float = Field(..., gt=0, description="Height")
    corner_radius: Optional[float] = Field(default=0, ge=0, description="Corner radius")


class EllipseInput(BaseModel):
    """Ellipse creation input"""
    cx: float = Field(..., description="Center X coordinate")
    cy: float = Field(..., description="Center Y coordinate")
    rx: float = Field(..., gt=0, description="X-axis radius")
    ry: float = Field(..., gt=0, description="Y-axis radius")


class LineInput(BaseModel):
    """Line creation input"""
    x1: float
    y1: float
    x2: float
    y2: float


class ShapeQuery(BaseModel):
    """Shape query"""
    name: Optional[str] = Field(None, description="Find by name")
    layer: Optional[str] = Field(None, description="Find by layer")
    type: Optional[str] = Field(None, description="Find by type")


# ========== Text models ==========


class TextStyle(BaseModel):
    """Text style"""
    font: Optional[str] = Field(None, description="Font name")
    size: Optional[float] = Field(None, gt=0, description="Font size")
    bold: Optional[bool] = Field(None, description="Bold")
    italic: Optional[bool] = Field(None, description="Italic")
    color: Optional[str] = Field(None, description="Color (CMYK or RGB)")
    alignment: Optional[Literal["left", "center", "right"]] = Field(None, description="Alignment")
    line_spacing: Optional[float] = Field(None, gt=0, description="Line spacing")
    char_spacing: Optional[float] = Field(None, ge=0, description="Character spacing")


class TextContentUpdate(BaseModel):
    """Text content update"""
    shape_id: str = Field(..., description="Shape ID or name")
    content: str = Field(..., description="New text content")


# ========== Color models ==========


class CMYKColor(BaseModel):
    """CMYK color"""
    c: float = Field(..., ge=0, le=100, description="Cyan 0-100")
    m: float = Field(..., ge=0, le=100, description="Magenta 0-100")
    y: float = Field(..., ge=0, le=100, description="Yellow 0-100")
    k: float = Field(..., ge=0, le=100, description="Black 0-100")


class RGBColor(BaseModel):
    """RGB color"""
    r: int = Field(..., ge=0, le=255, description="Red 0-255")
    g: int = Field(..., ge=0, le=255, description="Green 0-255")
    b: int = Field(..., ge=0, le=255, description="Blue 0-255")


class PantoneColor(BaseModel):
    """Pantone spot color"""
    code: str = Field(..., min_length=1, description="Pantone color code, e.g. '485 C'")


class FillUpdate(BaseModel):
    """Fill update"""
    shape_id: str
    cmyk: Optional[CMYKColor] = None
    rgb: Optional[RGBColor] = None
    pantone: Optional[PantoneColor] = None
    no_fill: bool = False


class OutlineUpdate(BaseModel):
    """Outline update"""
    shape_id: str
    width: float = Field(..., ge=0, description="Outline width")
    color_mode: ColorMode = ColorMode.CMYK
    color: Optional[str] = None
    no_outline: bool = False


# ========== Layer models ==========


class LayerInfo(BaseModel):
    """Layer info"""
    name: str
    visible: bool = True
    locked: bool = False
    color: Optional[str] = Field(None, description="Layer color tag")


class LayerAssign(BaseModel):
    """Layer assignment"""
    shape_id: str
    layer_name: str


# ========== Export models ==========


class PDFExportOptions(BaseModel):
    """PDF export options"""
    color_profile: str = Field(default="ISO_Coated_v2", description="Color profile")
    bleed: float = Field(default=3.0, ge=0, description="Bleed in mm")
    crop_marks: bool = Field(default=True, description="Whether to include crop marks")
    compression: Literal["none", "jpeg", "zip"] = "zip"
    multi_page: bool = Field(default=False, description="Whether to export multiple pages")


class DXFExportOptions(BaseModel):
    """DXF export options"""
    version: Literal["R12", "R14", "R2000", "R2004"] = Field(default="R14")
    layer_filter: Optional[List[str]] = Field(None, description="List of layers to export")
    export_hidden: bool = Field(default=False, description="Whether to export hidden layers")


class PNGExportOptions(BaseModel):
    """PNG export options"""
    dpi: int = Field(default=300, ge=72, description="Resolution (DPI)")
    color_mode: ColorMode = ColorMode.RGB
    width: Optional[int] = Field(None, ge=100, description="Output width (px)")
    background_transparent: bool = Field(default=False)


# ========== Preflight models ==========


class DimensionCheck(BaseModel):
    """Dimension check request"""
    expected_width: float
    expected_height: float
    tolerance: float = Field(default=0.5, ge=0, description="Tolerance in mm")


class ColorReport(BaseModel):
    """Color report"""
    rgb_colors: List[Dict[str, Any]] = Field(default_factory=list, description="RGB colors found")
    pantone_colors: List[str] = Field(default_factory=list, description="Pantone color codes used")
    spot_colors: List[str] = Field(default_factory=list, description="Spot colors used")


class QualityCheckResult(BaseModel):
    """Preflight result"""
    passed: bool
    issues: List[str] = Field(default_factory=list)
    details: Optional[Dict[str, Any]] = None


# ========== Data merge models ==========


class DataSourceConfig(BaseModel):
    """Data source config"""
    path: str
    sheet: Optional[int] = Field(default=0, description="Worksheet index")
    has_header: bool = Field(default=True, description="Whether the data has a header row")


class MergeRecord(BaseModel):
    """Single merge record"""
    template_path: str
    data: Dict[str, str]
    output_path: str


class BatchMergeConfig(BaseModel):
    """Batch merge config"""
    template_path: str
    data_path: str
    output_dir: str
    naming_pattern: str = Field(default="{room}", description="Output file naming pattern")


# ========== Barcode models ==========


class BarcodeSpec(BaseModel):
    """Barcode spec"""
    type: Literal["code128", "ean13", "code39", "qr"] = Field(..., description="Barcode type")
    data: str = Field(..., min_length=1)
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    width: float = Field(..., gt=0, description="Width")
    height: float = Field(..., gt=0, description="Height")


# ========== Tool result model ==========


class ToolResult(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, msg: Optional[str] = None, **data) -> "ToolResult":
        return cls(success=True, message=msg, data=data if data else None)

    @classmethod
    def fail(cls, err: str, msg: Optional[str] = None) -> "ToolResult":
        return cls(success=False, error=err, message=msg)


# ========== Tool context ==========


class ToolContext(BaseModel):
    """Tool call context (injected automatically)"""
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None