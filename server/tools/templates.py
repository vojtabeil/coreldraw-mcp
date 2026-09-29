"""Template tools - list available templates, query size variant rules"""

import json
import os

from core.models import ToolResult

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "../config/template_registry.json")


def _load_registry() -> dict:
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_templates(filter_material: str = "", filter_keyword: str = "") -> ToolResult:
    """List all available templates. filter_material filters by material; filter_keyword filters by a keyword
    in the name/description. Returns each template's name, description, size, placeholder list, and whether it
    has size variant rules."""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"Cannot read template registry config: {e}")

    templates = registry.get("templates", {})
    result = []

    for name, cfg in templates.items():
        if filter_material and filter_material.lower() not in cfg.get("material", "").lower():
            continue
        if filter_keyword:
            kw = filter_keyword.lower()
            if kw not in name.lower() and kw not in cfg.get("description", "").lower():
                continue

        entry = {
            "name": name,
            "description": cfg.get("description", ""),
            "file": cfg.get("file", ""),
            "width_mm": cfg.get("width_mm"),
            "height_mm": cfg.get("height_mm"),
            "material": cfg.get("material", ""),
            "placeholders": list(cfg.get("placeholders", {}).keys()),
            "has_size_variants": "size_variants" in cfg,
        }
        if "size_variants" in cfg:
            entry["size_variants"] = cfg["size_variants"]
        result.append(entry)

    return ToolResult.ok(
        f"Found {len(result)} templates",
        total=len(result),
        templates=result,
    )


def get_template_info(template_name: str) -> ToolResult:
    """Get the full config of a template, including placeholder details, layer descriptions, size variant rules and title block fields."""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"Cannot read template registry config: {e}")

    templates = registry.get("templates", {})
    if template_name not in templates:
        available = list(templates.keys())
        return ToolResult.fail(f"Template '{template_name}' does not exist, available templates: {available}")

    cfg = templates[template_name]
    return ToolResult.ok(f"Template info: {template_name}", name=template_name, **cfg)


def get_size_variant(template_name: str, room_number: str) -> ToolResult:
    """Look up the page size variant for the number of characters in the room number. Used to automatically determine the door sign width."""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"Cannot read template registry config: {e}")

    templates = registry.get("templates", {})
    if template_name not in templates:
        return ToolResult.fail(f"Template '{template_name}' does not exist")

    cfg = templates[template_name]
    if "size_variants" not in cfg:
        return ToolResult.ok(
            "This template has no size variant rules; using default size",
            width_mm=cfg.get("width_mm"),
            height_mm=cfg.get("height_mm"),
            variant_matched=False,
        )

    char_count = len(room_number.strip())
    variants = cfg["size_variants"].get("variants", [])
    for v in variants:
        if v.get("char_count") == char_count:
            return ToolResult.ok(
                f"Room number '{room_number}' ({char_count} chars) → width {v['width_mm']}mm",
                width_mm=v["width_mm"],
                height_mm=cfg.get("height_mm"),
                width_in=v.get("width_in"),
                char_count=char_count,
                variant_matched=True,
                rule=cfg["size_variants"].get("rule", ""),
            )

    return ToolResult.ok(
        f"Room number '{room_number}' ({char_count} chars) has no matching variant; using default size",
        width_mm=cfg.get("width_mm"),
        height_mm=cfg.get("height_mm"),
        char_count=char_count,
        variant_matched=False,
    )
