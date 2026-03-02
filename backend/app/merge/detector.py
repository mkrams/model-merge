"""
Overlap and conflict detector for model merge.
Compares elements from two parsed models and classifies them as
identical, conflicting, or unique to one side.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class MergeConflict:
    conflict_id: str
    conflict_type: str  # "identical", "name_match", "similar", "structural"
    left_element: dict
    right_element: dict
    similarity: float = 1.0
    resolution: Optional[str] = None  # "keep_left", "keep_right", "merge_both"

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "left_element": self.left_element,
            "right_element": self.right_element,
            "similarity": self.similarity,
            "resolution": self.resolution,
        }


@dataclass
class MergeAnalysis:
    merge_id: str
    model_a_id: str
    model_b_id: str
    model_a_name: str = ""
    model_b_name: str = ""
    total_elements_a: int = 0
    total_elements_b: int = 0
    identical: list[MergeConflict] = field(default_factory=list)
    conflicts: list[MergeConflict] = field(default_factory=list)
    unique_to_left: list[dict] = field(default_factory=list)
    unique_to_right: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "merge_id": self.merge_id,
            "model_a_id": self.model_a_id,
            "model_b_id": self.model_b_id,
            "model_a_name": self.model_a_name,
            "model_b_name": self.model_b_name,
            "total_elements_a": self.total_elements_a,
            "total_elements_b": self.total_elements_b,
            "identical_count": len(self.identical),
            "conflict_count": len(self.conflicts),
            "unique_left_count": len(self.unique_to_left),
            "unique_right_count": len(self.unique_to_right),
            "identical": [c.to_dict() for c in self.identical],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "unique_to_left": self.unique_to_left,
            "unique_to_right": self.unique_to_right,
        }


def _element_key(el: dict) -> str:
    """Generate a comparison key for an element."""
    name = el.get("name", "")
    etype = el.get("type", "")
    req_id = el.get("req_id", "")
    if req_id:
        return f"{etype}::{req_id}"
    return f"{etype}::{name}"


def _element_similarity(a: dict, b: dict) -> float:
    """Calculate similarity between two elements (0.0 to 1.0)."""
    # Compare raw representations if available
    raw_a = a.get("raw", "")
    raw_b = b.get("raw", "")
    if raw_a and raw_b:
        return SequenceMatcher(None, raw_a, raw_b).ratio()

    # Compare attributes
    score = 0.0
    total = 0

    # Name match
    name_a = a.get("name", "")
    name_b = b.get("name", "")
    if name_a and name_b:
        total += 1
        score += SequenceMatcher(None, name_a, name_b).ratio()

    # Type match
    if a.get("type") == b.get("type"):
        total += 1
        score += 1.0
    else:
        total += 1

    # Doc match
    doc_a = a.get("doc", "")
    doc_b = b.get("doc", "")
    if doc_a or doc_b:
        total += 1
        if doc_a and doc_b:
            score += SequenceMatcher(None, doc_a, doc_b).ratio()

    return score / max(total, 1)


def analyze_merge(
    elements_a: list[dict],
    elements_b: list[dict],
    model_a_id: str,
    model_b_id: str,
    model_a_name: str = "",
    model_b_name: str = "",
    merge_id: str = "",
    similarity_threshold: float = 0.85,
) -> MergeAnalysis:
    """
    Compare two sets of elements and produce a merge analysis.

    Args:
        elements_a: Flattened elements from model A
        elements_b: Flattened elements from model B
        similarity_threshold: Minimum similarity to consider a match
    """
    analysis = MergeAnalysis(
        merge_id=merge_id,
        model_a_id=model_a_id,
        model_b_id=model_b_id,
        model_a_name=model_a_name,
        model_b_name=model_b_name,
        total_elements_a=len(elements_a),
        total_elements_b=len(elements_b),
    )

    # Index elements by key
    left_by_key: dict[str, dict] = {}
    for el in elements_a:
        key = _element_key(el)
        left_by_key[key] = el

    right_by_key: dict[str, dict] = {}
    for el in elements_b:
        key = _element_key(el)
        right_by_key[key] = el

    matched_right_keys = set()
    conflict_idx = 0

    # Pass 1: Exact key matches
    for key, left_el in left_by_key.items():
        if key in right_by_key:
            right_el = right_by_key[key]
            matched_right_keys.add(key)

            sim = _element_similarity(left_el, right_el)
            conflict_idx += 1

            if sim >= 0.99:
                analysis.identical.append(MergeConflict(
                    conflict_id=f"c{conflict_idx}",
                    conflict_type="identical",
                    left_element=left_el,
                    right_element=right_el,
                    similarity=sim,
                    resolution="keep_left",  # auto-resolve identical
                ))
            else:
                analysis.conflicts.append(MergeConflict(
                    conflict_id=f"c{conflict_idx}",
                    conflict_type="name_match" if sim > similarity_threshold else "structural",
                    left_element=left_el,
                    right_element=right_el,
                    similarity=sim,
                ))

    # Pass 2: Fuzzy matches for remaining elements
    unmatched_left = {k: v for k, v in left_by_key.items() if k not in right_by_key}
    unmatched_right = {k: v for k, v in right_by_key.items() if k not in matched_right_keys}

    fuzzy_matched_right = set()
    for left_key, left_el in unmatched_left.items():
        best_sim = 0.0
        best_right_key = None
        best_right_el = None

        for right_key, right_el in unmatched_right.items():
            if right_key in fuzzy_matched_right:
                continue
            sim = _element_similarity(left_el, right_el)
            if sim > best_sim:
                best_sim = sim
                best_right_key = right_key
                best_right_el = right_el

        if best_sim >= similarity_threshold and best_right_key:
            fuzzy_matched_right.add(best_right_key)
            conflict_idx += 1
            analysis.conflicts.append(MergeConflict(
                conflict_id=f"c{conflict_idx}",
                conflict_type="similar",
                left_element=left_el,
                right_element=best_right_el,
                similarity=best_sim,
            ))
        else:
            analysis.unique_to_left.append(left_el)

    # Remaining unmatched right elements
    for right_key, right_el in unmatched_right.items():
        if right_key not in matched_right_keys and right_key not in fuzzy_matched_right:
            analysis.unique_to_right.append(right_el)

    return analysis
