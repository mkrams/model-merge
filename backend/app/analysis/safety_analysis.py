"""Safety analysis for graph-based model: gaps, coverage, perspectives, traces."""
from __future__ import annotations
from ..models.safety import SafetyProject, SafetyItem, ItemType


def detect_gaps(project: SafetyProject) -> list[dict]:
    """Detect gaps in the traceability graph.

    A gap occurs when:
    - A hazard has no downstream hazardous events
    - An FSR has no verification
    - Any item with status='gap'
    """
    gaps = []

    for item in project.items:
        # Item status is gap
        if item.status == "gap":
            gaps.append({
                "item_id": item.item_id,
                "item_type": item.item_type.value if hasattr(item.item_type, 'value') else item.item_type,
                "gap_type": "status_gap",
                "message": f"{item.name or item.item_id} marked as gap",
            })

        # Hazard with no events
        if item.item_type == ItemType.HAZARD:
            children = project.get_children(item.item_id)
            if not any(c.item_type == ItemType.HAZARDOUS_EVENT for c in children):
                gaps.append({
                    "item_id": item.item_id,
                    "item_type": "hazard",
                    "gap_type": "missing_children",
                    "message": f"Hazard '{item.name}' has no hazardous events",
                })

        # FSR with no verification
        if item.item_type == ItemType.FSR:
            children = project.get_children(item.item_id)
            has_verification = any(c.item_type == ItemType.VERIFICATION for c in children)
            has_tsr = any(c.item_type == ItemType.TSR for c in children)
            if not has_verification and not has_tsr:
                gaps.append({
                    "item_id": item.item_id,
                    "item_type": "fsr",
                    "gap_type": "no_verification",
                    "message": f"FSR '{item.name}' has no verification or TSR",
                })

        # TSR with no verification
        if item.item_type == ItemType.TSR:
            children = project.get_children(item.item_id)
            if not any(c.item_type == ItemType.VERIFICATION for c in children):
                gaps.append({
                    "item_id": item.item_id,
                    "item_type": "tsr",
                    "gap_type": "no_verification",
                    "message": f"TSR '{item.name}' has no verification",
                })

    return gaps


def compute_coverage(project: SafetyProject) -> dict:
    """Compute coverage metrics for the project.

    Returns counts of items by type and status, plus % of fully-traced chains.
    """
    items_by_type: dict[str, dict] = {}
    for item_type in ItemType:
        type_str = item_type.value
        items_by_type[type_str] = {
            "total": 0,
            "approved": 0,
            "draft": 0,
            "gap": 0,
        }

    # Count items by type and status
    for item in project.items:
        type_str = item.item_type.value if hasattr(item.item_type, 'value') else item.item_type
        if type_str not in items_by_type:
            items_by_type[type_str] = {"total": 0, "approved": 0, "draft": 0, "gap": 0}

        items_by_type[type_str]["total"] += 1
        if item.status == "approved":
            items_by_type[type_str]["approved"] += 1
        elif item.status == "draft":
            items_by_type[type_str]["draft"] += 1
        elif item.status == "gap":
            items_by_type[type_str]["gap"] += 1

    # Count fully-traced chains (hazard → event → goal → fsr → verification)
    fully_traced = 0
    hazards = project.get_items_by_type(ItemType.HAZARD)
    for hazard in hazards:
        if hazard.status == "gap":
            continue
        # Check downstream to verification
        chain = _trace_chain(project, hazard.item_id)
        if _is_complete_chain(chain):
            fully_traced += 1

    total_items = len(project.items)
    coverage_pct = 0.0
    if total_items > 0:
        filled = sum(1 for i in project.items if i.status != "gap")
        coverage_pct = round((filled / total_items) * 100, 1)

    return {
        "total_items": total_items,
        "items_by_type": items_by_type,
        "total_links": len(project.links),
        "fully_traced_chains": fully_traced,
        "coverage_pct": coverage_pct,
        "gaps": detect_gaps(project),
    }


def _trace_chain(project: SafetyProject, item_id: str) -> dict:
    """Build a chain structure from an item downstream."""
    item = project.get_item(item_id)
    if not item:
        return {}

    chain = {
        "item_id": item_id,
        "item_type": item.item_type.value if hasattr(item.item_type, 'value') else item.item_type,
        "status": item.status,
        "children": [],
    }

    children = project.get_children(item_id)
    for child in children:
        chain["children"].append(_trace_chain(project, child.item_id))

    return chain


def _is_complete_chain(chain: dict) -> bool:
    """Check if a chain has all levels filled (no gaps)."""
    if not chain:
        return False
    if chain.get("status") == "gap":
        return False
    if not chain.get("children"):
        return False
    # Recursively check children
    return any(_is_complete_chain(child) for child in chain.get("children", []))


def get_perspective(project: SafetyProject, perspective: str) -> list[dict]:
    """Return items sorted by perspective/role.

    Perspectives:
    - safety_engineer: Items by ASIL (D → A → QM), hazards first
    - test_engineer: Items by verification status, unverified first
    - req_engineer: Items by approval status
    - manager: Items by completeness (most gaps first)
    """
    items = list(project.items)

    if perspective == "safety_engineer":
        # Sort by ASIL (high to low), then by type (hazard → event → goal)
        asil_order = {"D": 0, "C": 1, "B": 2, "A": 3, "QM": 4}
        type_order = {ItemType.HAZARD: 0, ItemType.HAZARDOUS_EVENT: 1, ItemType.SAFETY_GOAL: 2, ItemType.FSR: 3, ItemType.VERIFICATION: 4}

        def sort_key(item):
            asil = item.attributes.get("asil_level", "")
            asil_rank = asil_order.get(asil, 5)
            type_rank = type_order.get(item.item_type, 5)
            return (asil_rank, type_rank, item.item_id)

        items = sorted(items, key=sort_key)

    elif perspective == "test_engineer":
        # Unverified items first
        type_order = {ItemType.FSR: 0, ItemType.TSR: 1, ItemType.VERIFICATION: 2}

        def sort_key(item):
            type_rank = type_order.get(item.item_type, 5)
            verified = 0 if item.status == "gap" else 1
            return (verified, type_rank, item.item_id)

        items = sorted(items, key=sort_key)

    elif perspective == "req_engineer":
        # By approval status
        status_order = {"gap": 0, "draft": 1, "review": 2, "approved": 3}

        def sort_key(item):
            status_rank = status_order.get(item.status, 0)
            return (-status_rank, item.item_id)  # Approved first

        items = sorted(items, key=sort_key)

    elif perspective == "manager":
        # By item type and status
        type_order = {ItemType.HAZARD: 0, ItemType.HAZARDOUS_EVENT: 1, ItemType.SAFETY_GOAL: 2, ItemType.FSR: 3, ItemType.TSR: 4, ItemType.VERIFICATION: 5}

        def sort_key(item):
            type_rank = type_order.get(item.item_type, 5)
            gaps = 1 if item.status == "gap" else 0
            return (gaps, type_rank, item.item_id)

        items = sorted(items, key=sort_key)

    return [i.to_dict() for i in items]


def get_trace_tree(project: SafetyProject, item_id: str) -> dict:
    """Get full upstream + downstream trace from any item."""
    item = project.get_item(item_id)
    if not item:
        return {"error": f"Item {item_id} not found"}

    tree = item.to_dict()

    # Add upstream parents
    parents = project.get_parents(item_id)
    if parents:
        tree["upstream"] = [p.to_dict() for p in parents]

    # Add downstream children
    children = project.get_children(item_id)
    if children:
        tree["downstream"] = [c.to_dict() for c in children]

    return tree


def get_trace_matrix(project: SafetyProject, source_type: str, target_type: str) -> dict:
    """Return matrix of links between two item types.

    Returns format expected by frontend TraceMatrixView:
    {source_type, target_type, sources: [...], targets: [...], cells: [...]}
    """
    try:
        src_type = ItemType(source_type)
        tgt_type = ItemType(target_type)
    except ValueError:
        return {"error": f"Invalid item types: {source_type}, {target_type}",
                "source_type": source_type, "target_type": target_type,
                "sources": [], "targets": [], "cells": []}

    sources = project.get_items_by_type(src_type)
    targets = project.get_items_by_type(tgt_type)

    # Build link lookup for fast access
    link_lookup: dict[tuple[str, str], str] = {}
    for link in project.links:
        link_lookup[(link.source_id, link.target_id)] = link.link_id

    cells = []
    for src in sources:
        for tgt in targets:
            key = (src.item_id, tgt.item_id)
            linked = key in link_lookup
            cell = {
                "source_id": src.item_id,
                "target_id": tgt.item_id,
                "linked": linked,
            }
            if linked:
                cell["link_id"] = link_lookup[key]
            cells.append(cell)

    return {
        "source_type": source_type,
        "target_type": target_type,
        "sources": [s.to_dict() for s in sources],
        "targets": [t.to_dict() for t in targets],
        "cells": cells,
    }
