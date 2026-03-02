"""Parse imported files into graph-based safety model with items and links.

Supports: ReqIF, SysML v2, CSV/TSV, Excel (.xlsx/.xls), Word (.docx).
"""
from __future__ import annotations
import logging
import re
import csv
import io
import tempfile
from pathlib import Path
from typing import Optional

from ..models.safety import (
    SafetyProject, SafetyItem, TraceLink, ItemType, LinkType,
    compute_asil,
)
from ..parsers.sysml_v2_parser import parse_sysml_v2
from ..parsers.reqif_parser import parse_reqif

logger = logging.getLogger(__name__)

# ── Classification heuristics ────────────────────────────────────

_HAZ_PATTERNS = re.compile(r'hazard|haz[\-_]|malfunct|failure\s*mode', re.I)
_HE_PATTERNS = re.compile(r'hazardous\s*event|haz[\-_]?event|operating\s*situation', re.I)
_SG_PATTERNS = re.compile(r'safety\s*goal|safe[\-_]?goal|sg[\-_]', re.I)
_FSR_PATTERNS = re.compile(r'functional\s*safety|fsr[\-_]|safety\s*req|safe[\-_]?req', re.I)
_TSR_PATTERNS = re.compile(r'technical\s*safety|tsr[\-_]|technical\s*req', re.I)
_VER_PATTERNS = re.compile(r'verification|test[\-_\s]?case|tc[\-_]|analysis|review', re.I)
_ASIL_PATTERN = re.compile(r'ASIL[\-_\s]*(QM|A|B|C|D)', re.I)


def _classify_requirement(name: str, doc: str, req_id: str, pkg_name: str) -> str:
    """Classify a requirement into a type based on heuristics."""
    text = f"{name} {doc} {req_id} {pkg_name}".lower()
    rid = (req_id or "").upper()

    # Check ID prefix first (most reliable)
    if rid.startswith("HAZ-") or rid.startswith("H-"):
        return "hazard"
    if rid.startswith("HE-"):
        return "hazardous_event"
    if rid.startswith("SG-"):
        return "safety_goal"
    if rid.startswith("FSR-") or rid.startswith("SR-"):
        return "fsr"
    if rid.startswith("TSR-"):
        return "tsr"
    if rid.startswith("TC-") or rid.startswith("VT-"):
        return "verification"

    # Then check name/doc patterns
    if _VER_PATTERNS.search(text):
        return "verification"
    if _TSR_PATTERNS.search(text):
        return "tsr"
    if _FSR_PATTERNS.search(text):
        return "fsr"
    if _SG_PATTERNS.search(text):
        return "safety_goal"
    if _HE_PATTERNS.search(text):
        return "hazardous_event"
    if _HAZ_PATTERNS.search(text):
        return "hazard"

    return "fsr"


def _extract_asil(text: str) -> Optional[str]:
    """Try to extract ASIL level from text."""
    m = _ASIL_PATTERN.search(text)
    if m:
        return m.group(1).upper()
    return None


# ── CSV Import (NEW GRAPH FORMAT) ─────────────────────────────────

def parse_csv_safety(raw_text: str, filename: str) -> SafetyProject:
    """Parse CSV and build graph with items + links.

    Supports row-per-item format with columns: ID, Type, Name, Description, Parent_ID, etc.
    Uses Parent_ID to create links and builds many-to-many traceability.
    """
    project = SafetyProject(name=filename)
    reader = csv.DictReader(io.StringIO(raw_text))
    headers_raw = reader.fieldnames or []
    headers = [h.lower().strip() for h in headers_raw]

    # Check if row-per-item format
    has_type = any("type" in h for h in headers)
    has_id = any(h in ("id", "req_id", "item_id") for h in headers)

    if not (has_type and has_id):
        logger.warning("CSV format not recognized as row-per-item; parsing as best effort")

    # Helper to find column case-insensitively
    def _col(row: dict, *candidates: str) -> str:
        for c in candidates:
            for key in row:
                if key.lower().strip() == c.lower():
                    return (row[key] or "").strip()
        return ""

    # First pass: collect all items
    items_data: dict[str, dict] = {}
    rows_list = list(reader)

    for row in rows_list:
        item_id = _col(row, "id", "req_id", "item_id")
        if not item_id:
            continue

        item_type_str = _col(row, "type").lower()
        name = _col(row, "name", "title")
        desc = _col(row, "description", "text", "doc")
        asil = _col(row, "asil", "asil_level").upper()
        status = _col(row, "status").lower() or "draft"
        parent_id = _col(row, "parent_id", "parent", "derived_from")
        verified_by = _col(row, "verified_by", "verification")
        allocated_to = _col(row, "allocated_to", "component")

        # Classify type
        item_type = ItemType.FSR
        if "hazardous event" in item_type_str or "haz event" in item_type_str or "he" in item_type_str or item_id.upper().startswith("HE-"):
            item_type = ItemType.HAZARDOUS_EVENT
        elif "hazard" in item_type_str or item_id.upper().startswith("HAZ-"):
            item_type = ItemType.HAZARD
        elif "safety goal" in item_type_str or "sg" in item_type_str or item_id.upper().startswith("SG-"):
            item_type = ItemType.SAFETY_GOAL
        elif "tsr" in item_type_str or "technical safety" in item_type_str or item_id.upper().startswith("TSR-"):
            item_type = ItemType.TSR
        elif "fsr" in item_type_str or "functional safety" in item_type_str or item_id.upper().startswith("FSR-"):
            item_type = ItemType.FSR
        elif "test" in item_type_str or "tc" in item_type_str or "analysis" in item_type_str or "review" in item_type_str or item_id.upper().startswith("TC-"):
            item_type = ItemType.VERIFICATION

        items_data[item_id] = {
            "id": item_id,
            "type": item_type,
            "name": name,
            "description": desc,
            "asil": asil if asil in ("QM", "A", "B", "C", "D") else "",
            "status": status if status in ("draft", "approved", "review", "gap") else "draft",
            "parent_id": parent_id,
            "verified_by": verified_by,
            "allocated_to": allocated_to,
        }

    # Second pass: create SafetyItem objects and add to project
    for item_id, item_data in items_data.items():
        attributes = {}
        if item_data["asil"]:
            attributes["asil_level"] = item_data["asil"]
        if item_data["allocated_to"]:
            attributes["allocated_to"] = item_data["allocated_to"]

        item = SafetyItem(
            item_id=item_id,
            item_type=item_data["type"],
            name=item_data["name"],
            description=item_data["description"],
            status=item_data["status"],
            attributes=attributes,
        )
        project.add_item(item)

    # Third pass: create links from Parent_ID and Verified_By/Satisfied_By
    for item_id, item_data in items_data.items():
        parent_id = item_data["parent_id"]
        if parent_id and parent_id in items_data:
            parent_type = items_data[parent_id]["type"]
            child_type = item_data["type"]
            # Infer link type
            link_type = _infer_link_type(parent_type, child_type)
            if link_type:
                project.add_link(parent_id, item_id, link_type, "")

        # Handle Verified_By (item_id → verification_id)
        verified_by = item_data["verified_by"]
        if verified_by and verified_by in items_data:
            ver_type = items_data[verified_by]["type"]
            if ver_type == ItemType.VERIFICATION:
                source_type = item_data["type"]
                link_type = _infer_link_type(source_type, ItemType.VERIFICATION)
                if link_type:
                    project.add_link(item_id, verified_by, link_type, "")

    logger.info(f"Parsed CSV safety graph: {len(project.items)} items, {len(project.links)} links")
    return project


def _infer_link_type(source_type: ItemType, target_type: ItemType) -> Optional[LinkType]:
    """Infer the link type between two item types."""
    source_str = source_type.value if isinstance(source_type, ItemType) else source_type
    target_str = target_type.value if isinstance(target_type, ItemType) else target_type
    key = (source_str, target_str)

    type_map = {
        ("hazard", "hazardous_event"): LinkType.HAZARD_TO_EVENT,
        ("hazardous_event", "safety_goal"): LinkType.EVENT_TO_GOAL,
        ("safety_goal", "fsr"): LinkType.GOAL_TO_FSR,
        ("fsr", "tsr"): LinkType.FSR_TO_TSR,
        ("tsr", "verification"): LinkType.TSR_TO_VERIFICATION,
        ("fsr", "verification"): LinkType.FSR_TO_VERIFICATION,
    }
    return type_map.get(key)


# ── Excel Import ──────────────────────────────────────────────────

def parse_excel_safety(file_bytes: bytes, filename: str) -> SafetyProject:
    """Parse .xlsx/.xls file and build graph."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl required for Excel import — pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

    # Pick the best sheet
    sheet = None
    preferred = ["requirements", "hazards", "safety", "asil", "fsr", "chains"]
    for name in wb.sheetnames:
        if any(p in name.lower() for p in preferred):
            sheet = wb[name]
            break
    if sheet is None:
        sheet = wb.active or wb[wb.sheetnames[0]]

    # Read all rows into CSV text
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return SafetyProject(name=filename)

    # First non-empty row as header
    header_row = None
    data_start = 0
    for i, row in enumerate(rows):
        if any(cell is not None for cell in row):
            header_row = row
            data_start = i + 1
            break

    if header_row is None:
        return SafetyProject(name=filename)

    # Build CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([str(h or "").strip() for h in header_row])
    for row in rows[data_start:]:
        if any(cell is not None for cell in row):
            writer.writerow([str(cell or "").strip() for cell in row])

    csv_text = output.getvalue()
    wb.close()

    # Parse using CSV logic
    project = parse_csv_safety(csv_text, filename)
    logger.info(f"Parsed Excel safety graph: {len(project.items)} items")
    return project


# ── Word (.docx) Import ───────────────────────────────────────────

def parse_docx_safety(file_bytes: bytes, filename: str) -> SafetyProject:
    """Parse .docx file and extract safety items into graph."""
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("python-docx required for Word import — pip install python-docx")

    doc = Document(io.BytesIO(file_bytes))

    # Try tables first
    for table in doc.tables:
        result = _parse_docx_table(table, filename)
        if result and len(result.items) > 0:
            return result

    # Parse structured text
    return _parse_docx_text(doc, filename)


def _parse_docx_table(table, filename: str) -> Optional[SafetyProject]:
    """Parse a Word table into graph items."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows.append(cells)

    if len(rows) < 2:
        return None

    headers = rows[0]
    if not any(h.lower() for h in headers if h):
        return None

    # Build CSV text from table
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows[1:]:
        padded = row[:len(headers)] + [""] * max(0, len(headers) - len(row))
        writer.writerow(padded)

    csv_text = output.getvalue()

    try:
        project = parse_csv_safety(csv_text, filename)
        return project if project.items else None
    except Exception:
        return None


def _parse_docx_text(doc, filename: str) -> SafetyProject:
    """Parse structured text from Word document."""
    project = SafetyProject(name=filename)

    level_patterns = {
        ItemType.HAZARD: re.compile(r"(?:HAZ[-_]?\d+|Hazard\s*:)", re.IGNORECASE),
        ItemType.HAZARDOUS_EVENT: re.compile(r"(?:HE[-_]?\d+|Hazardous\s+Event\s*:)", re.IGNORECASE),
        ItemType.SAFETY_GOAL: re.compile(r"(?:SG[-_]?\d+|Safety\s+Goal\s*:)", re.IGNORECASE),
        ItemType.FSR: re.compile(r"(?:FSR[-_]?\d+|Functional\s+Safety\s+Req)", re.IGNORECASE),
        ItemType.VERIFICATION: re.compile(r"(?:TC[-_]?\d+|Test\s+Case\s*:)", re.IGNORECASE),
    }

    items_by_type: dict[ItemType, list[SafetyItem]] = {t: [] for t in ItemType}
    current_item: Optional[SafetyItem] = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        matched_type = None
        for item_type, pattern in level_patterns.items():
            if pattern.search(text):
                matched_type = item_type
                break

        if matched_type:
            if current_item:
                items_by_type[current_item.item_type].append(current_item)

            id_match = re.match(r"((?:HAZ|HE|SG|FSR|TC)[-_]?\d+)\s*[:\-–]\s*(.*)", text, re.IGNORECASE)
            if id_match:
                item_id = id_match.group(1).upper().replace("_", "-")
                name = id_match.group(2).strip()
            else:
                item_id = f"{matched_type.value.upper()}-{len(project.items)+1}"
                name = re.sub(r"^(?:Hazard|Hazardous\s+Event|Safety\s+Goal|FSR|Test\s+Case)\s*:\s*",
                             "", text, flags=re.IGNORECASE).strip()

            current_item = SafetyItem(
                item_id=item_id,
                item_type=matched_type,
                name=name,
                description="",
                status="draft",
            )
        elif current_item:
            if current_item.description:
                current_item.description += "\n" + text
            else:
                current_item.description = text

    if current_item:
        items_by_type[current_item.item_type].append(current_item)

    # Add items to project
    for item_list in items_by_type.values():
        for item in item_list:
            project.add_item(item)

    # Simple chain linking: pair items by order
    max_len = max(len(v) for v in items_by_type.values()) if items_by_type else 0
    for i in range(max_len):
        pairs = [
            (ItemType.HAZARD, ItemType.HAZARDOUS_EVENT),
            (ItemType.HAZARDOUS_EVENT, ItemType.SAFETY_GOAL),
            (ItemType.SAFETY_GOAL, ItemType.FSR),
            (ItemType.FSR, ItemType.VERIFICATION),
        ]
        for src_type, tgt_type in pairs:
            src_list = items_by_type.get(src_type, [])
            tgt_list = items_by_type.get(tgt_type, [])
            if i < len(src_list) and i < len(tgt_list):
                link_type = _infer_link_type(src_type, tgt_type)
                if link_type:
                    project.add_link(src_list[i].item_id, tgt_list[i].item_id, link_type, "")

    logger.info(f"Parsed DOCX safety graph: {len(project.items)} items, {len(project.links)} links")
    return project


# ── Main entry point ──────────────────────────────────────────────

def parse_safety_chain(raw_text: str, filename: str) -> SafetyProject:
    """Auto-detect format and parse into graph model."""
    fname = filename.lower()
    if fname.endswith(".csv") or fname.endswith(".tsv"):
        return parse_csv_safety(raw_text, filename)
    else:
        # For other text formats, try CSV as fallback
        return parse_csv_safety(raw_text, filename)


def parse_safety_chain_bytes(file_bytes: bytes, filename: str) -> SafetyProject:
    """Parse binary formats or fall back to text parser."""
    fname = filename.lower()
    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        return parse_excel_safety(file_bytes, filename)
    elif fname.endswith(".docx"):
        return parse_docx_safety(file_bytes, filename)
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")
        return parse_safety_chain(raw_text, filename)
