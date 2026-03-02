"""Parse imported files and extract safety chain items (Hazard → TestCase).

Supports: ReqIF, SysML v2, CSV/Excel.
Strategy: heuristic classification based on naming patterns, attribute names,
package names, and requirement ID prefixes.
"""
from __future__ import annotations
import logging
import re
import csv
import io
from typing import Optional

from ..models.safety import (
    SafetyProject, SafetyChain, Hazard, HazardousEvent,
    ASILDetermination, SafetyGoal, FSR, TestCase, FailureMode,
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
_TC_PATTERNS = re.compile(r'test[\-_\s]?case|tc[\-_]|verification|val[\-_]?test', re.I)
_ASIL_PATTERN = re.compile(r'ASIL[\-_\s]*(QM|A|B|C|D)', re.I)
_FM_PATTERNS = re.compile(r'failure\s*mode|fmea|fm[\-_]', re.I)


def _classify_requirement(name: str, doc: str, req_id: str, pkg_name: str) -> str:
    """Classify a requirement into a chain level based on heuristics.
    Returns: 'hazard', 'hazardous_event', 'safety_goal', 'fsr', 'test_case', or 'unknown'.
    """
    text = f"{name} {doc} {req_id} {pkg_name}".lower()

    # Check ID prefix first (most reliable)
    rid = (req_id or "").upper()
    if rid.startswith("HAZ-") or rid.startswith("H-"):
        return "hazard"
    if rid.startswith("HE-"):
        return "hazardous_event"
    if rid.startswith("SG-"):
        return "safety_goal"
    if rid.startswith("FSR-") or rid.startswith("SR-"):
        return "fsr"
    if rid.startswith("TC-") or rid.startswith("VT-"):
        return "test_case"
    if rid.startswith("FM-"):
        return "failure_mode"

    # Then check name/doc patterns
    if _TC_PATTERNS.search(text):
        return "test_case"
    if _FSR_PATTERNS.search(text):
        return "fsr"
    if _SG_PATTERNS.search(text):
        return "safety_goal"
    if _HE_PATTERNS.search(text):
        return "hazardous_event"
    if _HAZ_PATTERNS.search(text):
        return "hazard"
    if _FM_PATTERNS.search(text):
        return "failure_mode"

    # Default: treat as FSR (most common requirement type)
    return "fsr"


def _extract_asil(text: str) -> Optional[str]:
    """Try to extract ASIL level from text."""
    m = _ASIL_PATTERN.search(text)
    if m:
        return m.group(1).upper()
    return None


# ── SysML v2 Import ─────────────────────────────────────────────

def parse_sysml_safety(raw_text: str, filename: str) -> SafetyProject:
    """Parse SysML v2 file and extract safety chain items."""
    model = parse_sysml_v2(raw_text, filename)
    project = SafetyProject(name=filename, source_filename=filename)

    # Collect all requirements and connections
    requirements = []
    connections = []
    _collect_from_packages(model.packages, requirements, connections, "")

    # Classify requirements
    classified: dict[str, list] = {
        "hazard": [], "hazardous_event": [], "safety_goal": [],
        "fsr": [], "test_case": [], "failure_mode": [], "unknown": [],
    }
    for req in requirements:
        level = _classify_requirement(
            req["name"], req.get("doc", ""), req.get("req_id", ""), req.get("package", "")
        )
        classified[level].append(req)

    # Build connection index (source → targets by kind)
    link_map: dict[str, list[tuple[str, str]]] = {}  # name → [(target, kind)]
    for conn in connections:
        src = conn.get("source", "")
        tgt = conn.get("target", "")
        kind = conn.get("kind", "")
        if src:
            link_map.setdefault(src, []).append((tgt, kind))

    # Build chains: start from hazards, follow links downstream
    for haz_data in classified["hazard"]:
        chain = SafetyChain()
        chain.hazard = Hazard(
            name=haz_data["name"],
            description=haz_data.get("doc", ""),
            status="draft",
        )
        asil_text = haz_data.get("doc", "") + " " + haz_data["name"]
        asil_level = _extract_asil(asil_text)
        if asil_level:
            chain.asil_determination = ASILDetermination(asil_level=asil_level)

        # Try to find downstream items via links
        _try_link_chain(chain, haz_data["name"], classified, link_map)
        project.chains.append(chain)

    # Any safety goals not linked to a hazard → create partial chains
    linked_sg_names = {c.safety_goal.name for c in project.chains if c.safety_goal}
    for sg_data in classified["safety_goal"]:
        if sg_data["name"] not in linked_sg_names:
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")  # Gap — no hazard
            chain.safety_goal = SafetyGoal(
                name=sg_data["name"],
                description=sg_data.get("doc", ""),
                asil_level=_extract_asil(sg_data.get("doc", "")) or "",
                status="draft",
            )
            _try_link_chain_downstream(chain, sg_data["name"], classified, link_map)
            project.chains.append(chain)

    # Any FSRs not in any chain → create minimal chains
    linked_fsr_names = {c.fsr.name for c in project.chains if c.fsr}
    for fsr_data in classified["fsr"]:
        if fsr_data["name"] not in linked_fsr_names:
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")
            chain.safety_goal = SafetyGoal(status="gap")
            chain.fsr = FSR(
                name=fsr_data["name"],
                description=fsr_data.get("doc", ""),
                asil_level=_extract_asil(fsr_data.get("doc", "")) or "",
                status="draft",
            )
            project.chains.append(chain)

    # Failure modes
    for fm_data in classified["failure_mode"]:
        project.failure_modes.append(FailureMode(
            name=fm_data["name"],
            description=fm_data.get("doc", ""),
        ))

    # Fill gaps on all chains
    _fill_chain_gaps(project)

    logger.info(f"Parsed SysML safety: {len(project.chains)} chains, {project.total_gaps} gaps")
    return project


def _collect_from_packages(packages, requirements, connections, parent_pkg):
    """Recursively collect requirements and connections from packages."""
    for pkg in packages:
        pkg_name = pkg.name if hasattr(pkg, 'name') else str(pkg)
        for req in getattr(pkg, 'requirement_defs', []):
            doc = getattr(req, 'doc', '') or ''
            raw = getattr(req, 'raw', '') or ''
            # Fallback: build description from attributes if doc is empty
            attrs = [(a.name, a.default_value or '') for a in getattr(req, 'attributes', [])]
            if not doc:
                # Try common attribute names for the requirement text
                for aname, aval in attrs:
                    aname_l = aname.lower()
                    if aval and any(k in aname_l for k in ['description', 'text', 'content', 'reqif.text', 'object text']):
                        doc = aval
                        break
            # Still empty? Use raw text or first attribute with substantial value
            if not doc and raw:
                doc = raw[:500]
            if not doc:
                for aname, aval in attrs:
                    if aval and len(aval) > 10:
                        doc = aval
                        break
            requirements.append({
                "name": req.name,
                "doc": doc,
                "req_id": getattr(req, 'req_id', ''),
                "package": pkg_name,
                "constraints": [c.expression for c in getattr(req, 'constraints', [])],
                "attributes": attrs,
                "raw": raw,
            })
        for conn in getattr(pkg, 'connections', []):
            connections.append({
                "source": getattr(conn, 'source', ''),
                "target": getattr(conn, 'target', ''),
                "kind": getattr(conn, 'kind', ''),
            })
        _collect_from_packages(getattr(pkg, 'subpackages', []), requirements, connections, pkg_name)


def _try_link_chain(chain, hazard_name, classified, link_map):
    """Try to build chain by following satisfy/verify/derive links from a hazard."""
    targets = link_map.get(hazard_name, [])
    for tgt, kind in targets:
        # Find what this target is
        for sg in classified["safety_goal"]:
            if sg["name"] == tgt and not chain.safety_goal:
                chain.safety_goal = SafetyGoal(
                    name=sg["name"], description=sg.get("doc", ""),
                    hazard_id=chain.hazard.id if chain.hazard else "",
                    asil_level=_extract_asil(sg.get("doc", "")) or "",
                    status="draft",
                )
                _try_link_chain_downstream(chain, tgt, classified, link_map)
                break


def _try_link_chain_downstream(chain, from_name, classified, link_map):
    """Follow links downstream from safety goal to FSR to test case."""
    targets = link_map.get(from_name, [])
    for tgt, kind in targets:
        for fsr in classified["fsr"]:
            if fsr["name"] == tgt and not chain.fsr:
                chain.fsr = FSR(
                    name=fsr["name"], description=fsr.get("doc", ""),
                    safety_goal_id=chain.safety_goal.id if chain.safety_goal else "",
                    status="draft",
                )
                # Look for test cases linked to this FSR
                for tc_tgt, tc_kind in link_map.get(tgt, []):
                    for tc in classified["test_case"]:
                        if tc["name"] == tc_tgt and not chain.test_case:
                            chain.test_case = TestCase(
                                name=tc["name"], description=tc.get("doc", ""),
                                fsr_id=chain.fsr.id,
                                status="draft",
                            )
                            break
                break


# ── ReqIF Import ─────────────────────────────────────────────────

def parse_reqif_safety(raw_text: str, filename: str) -> SafetyProject:
    """Parse ReqIF file and extract safety chain items."""
    model = parse_reqif(raw_text, filename)
    project = SafetyProject(name=filename, source_filename=filename)

    requirements = []
    connections = []
    _collect_from_packages(model.packages, requirements, connections, "")

    # Same classification logic as SysML
    classified: dict[str, list] = {
        "hazard": [], "hazardous_event": [], "safety_goal": [],
        "fsr": [], "test_case": [], "failure_mode": [], "unknown": [],
    }
    for req in requirements:
        level = _classify_requirement(
            req["name"], req.get("doc", ""), req.get("req_id", ""), req.get("package", "")
        )
        classified[level].append(req)

    link_map: dict[str, list[tuple[str, str]]] = {}
    for conn in connections:
        src = conn.get("source", "")
        tgt = conn.get("target", "")
        kind = conn.get("kind", "")
        if src:
            link_map.setdefault(src, []).append((tgt, kind))

    # Build chains from hazards
    for haz_data in classified["hazard"]:
        chain = SafetyChain()
        chain.hazard = Hazard(name=haz_data["name"], description=haz_data.get("doc", ""), status="draft")
        asil_level = _extract_asil(haz_data.get("doc", "") + " " + haz_data["name"])
        if asil_level:
            chain.asil_determination = ASILDetermination(asil_level=asil_level)
        _try_link_chain(chain, haz_data["name"], classified, link_map)
        project.chains.append(chain)

    # Unlinked safety goals
    linked_sg = {c.safety_goal.name for c in project.chains if c.safety_goal}
    for sg in classified["safety_goal"]:
        if sg["name"] not in linked_sg:
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")
            chain.safety_goal = SafetyGoal(name=sg["name"], description=sg.get("doc", ""), status="draft")
            project.chains.append(chain)

    # Unlinked FSRs
    linked_fsr = {c.fsr.name for c in project.chains if c.fsr}
    for fsr in classified["fsr"]:
        if fsr["name"] not in linked_fsr:
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")
            chain.safety_goal = SafetyGoal(status="gap")
            chain.fsr = FSR(name=fsr["name"], description=fsr.get("doc", ""), status="draft")
            project.chains.append(chain)

    # If no hazards found, create chains from whatever we have
    if not classified["hazard"] and not classified["safety_goal"]:
        for fsr in classified["fsr"]:
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")
            chain.safety_goal = SafetyGoal(status="gap")
            chain.fsr = FSR(name=fsr["name"], description=fsr.get("doc", ""), status="draft")
            project.chains.append(chain)

    # If nothing classified at all, make chains from "unknown" requirements
    if not project.chains:
        for req in classified.get("unknown", []) + classified.get("fsr", []):
            chain = SafetyChain()
            chain.hazard = Hazard(status="gap")
            chain.safety_goal = SafetyGoal(status="gap")
            chain.fsr = FSR(name=req["name"], description=req.get("doc", ""), status="draft")
            project.chains.append(chain)

    _fill_chain_gaps(project)
    logger.info(f"Parsed ReqIF safety: {len(project.chains)} chains, {project.total_gaps} gaps")
    return project


# ── CSV / Excel Import ───────────────────────────────────────────

def parse_csv_safety(raw_text: str, filename: str) -> SafetyProject:
    """Parse CSV/TSV and build safety chains. Expects columns matching chain levels."""
    project = SafetyProject(name=filename, source_filename=filename)

    reader = csv.DictReader(io.StringIO(raw_text))
    headers = [h.lower().strip() for h in (reader.fieldnames or [])]

    # Map column names to chain levels
    col_map = {}
    for h in headers:
        if any(k in h for k in ["hazard"]):
            col_map["hazard"] = h
        elif any(k in h for k in ["hazardous event", "haz event", "he "]):
            col_map["hazardous_event"] = h
        elif any(k in h for k in ["asil"]):
            col_map["asil"] = h
        elif any(k in h for k in ["safety goal", "sg"]):
            col_map["safety_goal"] = h
        elif any(k in h for k in ["fsr", "functional safety", "safety req"]):
            col_map["fsr"] = h
        elif any(k in h for k in ["test", "tc", "verification"]):
            col_map["test_case"] = h

    for row in reader:
        chain = SafetyChain()

        # Hazard
        haz_text = row.get(col_map.get("hazard", ""), "").strip()
        if haz_text:
            chain.hazard = Hazard(name=haz_text, description=haz_text, status="draft")
        else:
            chain.hazard = Hazard(status="gap")

        # Hazardous Event
        he_text = row.get(col_map.get("hazardous_event", ""), "").strip()
        if he_text:
            chain.hazardous_event = HazardousEvent(
                name=he_text, description=he_text,
                hazard_id=chain.hazard.id if chain.hazard else "", status="draft",
            )

        # ASIL
        asil_text = row.get(col_map.get("asil", ""), "").strip().upper()
        if asil_text and asil_text in ("QM", "A", "B", "C", "D"):
            chain.asil_determination = ASILDetermination(asil_level=asil_text)

        # Safety Goal
        sg_text = row.get(col_map.get("safety_goal", ""), "").strip()
        if sg_text:
            chain.safety_goal = SafetyGoal(
                name=sg_text, description=sg_text,
                hazard_id=chain.hazard.id if chain.hazard else "",
                asil_level=asil_text or "", status="draft",
            )
        else:
            chain.safety_goal = SafetyGoal(status="gap")

        # FSR
        fsr_text = row.get(col_map.get("fsr", ""), "").strip()
        if fsr_text:
            chain.fsr = FSR(
                name=fsr_text, description=fsr_text,
                safety_goal_id=chain.safety_goal.id if chain.safety_goal else "",
                status="draft",
            )

        # Test Case
        tc_text = row.get(col_map.get("test_case", ""), "").strip()
        if tc_text:
            chain.test_case = TestCase(
                name=tc_text, description=tc_text,
                fsr_id=chain.fsr.id if chain.fsr else "", status="draft",
            )

        if chain.hazard or chain.safety_goal or chain.fsr:
            project.chains.append(chain)

    _fill_chain_gaps(project)
    logger.info(f"Parsed CSV safety: {len(project.chains)} chains, {project.total_gaps} gaps")
    return project


# ── Gap Filling ──────────────────────────────────────────────────

def _fill_chain_gaps(project: SafetyProject):
    """Ensure every chain has all 6 slots (even if gap)."""
    for chain in project.chains:
        if not chain.hazard:
            chain.hazard = Hazard(status="gap")
        if not chain.hazardous_event:
            chain.hazardous_event = HazardousEvent(
                hazard_id=chain.hazard.id, status="gap",
            )
        if not chain.asil_determination:
            chain.asil_determination = ASILDetermination()
        if not chain.safety_goal:
            chain.safety_goal = SafetyGoal(
                hazard_id=chain.hazard.id, status="gap",
            )
        if not chain.fsr:
            chain.fsr = FSR(
                safety_goal_id=chain.safety_goal.id, status="gap",
            )
        if not chain.test_case:
            chain.test_case = TestCase(
                fsr_id=chain.fsr.id, status="gap",
            )


# ── Main entry point ─────────────────────────────────────────────

def parse_safety_chain(raw_text: str, filename: str) -> SafetyProject:
    """Auto-detect format and parse safety chain items."""
    fname = filename.lower()
    if fname.endswith(".reqif") or fname.endswith(".xml"):
        return parse_reqif_safety(raw_text, filename)
    elif fname.endswith(".csv") or fname.endswith(".tsv"):
        return parse_csv_safety(raw_text, filename)
    else:
        # Default: SysML v2
        return parse_sysml_safety(raw_text, filename)
