"""Safety analysis: gap detection, coverage metrics, perspective views."""
from __future__ import annotations
from ..models.safety import SafetyProject, SafetyChain


def detect_gaps(project: SafetyProject) -> list[dict]:
    """Return all gaps across all chains."""
    gaps = []
    for chain in project.chains:
        levels = [
            ("hazard", chain.hazard),
            ("hazardous_event", chain.hazardous_event),
            ("asil_determination", chain.asil_determination),
            ("safety_goal", chain.safety_goal),
            ("fsr", chain.fsr),
            ("test_case", chain.test_case),
        ]
        for level_name, item in levels:
            if level_name == "asil_determination":
                if item is None or not item.asil_level:
                    gaps.append({
                        "chain_id": chain.chain_id,
                        "level": level_name,
                        "severity": "high" if chain.hazard and chain.hazard.status != "gap" else "medium",
                        "description": f"ASIL determination missing for chain {chain.chain_id}",
                    })
            elif item is None or item.status == "gap":
                gaps.append({
                    "chain_id": chain.chain_id,
                    "level": level_name,
                    "severity": _gap_severity(level_name),
                    "description": f"{level_name.replace('_', ' ').title()} missing",
                })
    return gaps


def _gap_severity(level: str) -> str:
    return {
        "hazard": "critical",
        "hazardous_event": "high",
        "safety_goal": "critical",
        "fsr": "high",
        "test_case": "medium",
    }.get(level, "medium")


def compute_coverage(project: SafetyProject) -> dict:
    """Compute coverage metrics for the project."""
    total = len(project.chains)
    if total == 0:
        return {"total_chains": 0, "coverage_pct": 0}

    level_counts = {
        "hazard": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
        "hazardous_event": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
        "asil": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
        "safety_goal": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
        "fsr": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
        "test_case": {"filled": 0, "approved": 0, "draft": 0, "gap": 0},
    }

    complete = 0
    for chain in project.chains:
        if chain.is_complete:
            complete += 1

        items = [
            ("hazard", chain.hazard),
            ("hazardous_event", chain.hazardous_event),
            ("safety_goal", chain.safety_goal),
            ("fsr", chain.fsr),
            ("test_case", chain.test_case),
        ]
        for level, item in items:
            if item and item.status != "gap":
                level_counts[level]["filled"] += 1
                if item.approved:
                    level_counts[level]["approved"] += 1
                else:
                    level_counts[level]["draft"] += 1
            else:
                level_counts[level]["gap"] += 1

        # ASIL
        if chain.asil_determination and chain.asil_determination.asil_level:
            level_counts["asil"]["filled"] += 1
            if chain.asil_determination.approved:
                level_counts["asil"]["approved"] += 1
            else:
                level_counts["asil"]["draft"] += 1
        else:
            level_counts["asil"]["gap"] += 1

    # ASIL distribution
    asil_dist = {"QM": 0, "A": 0, "B": 0, "C": 0, "D": 0, "undetermined": 0}
    for chain in project.chains:
        if chain.asil_determination and chain.asil_determination.asil_level:
            asil_dist[chain.asil_determination.asil_level] = asil_dist.get(
                chain.asil_determination.asil_level, 0) + 1
        else:
            asil_dist["undetermined"] += 1

    return {
        "total_chains": total,
        "complete_chains": complete,
        "coverage_pct": project.coverage_pct,
        "total_gaps": project.total_gaps,
        "level_counts": level_counts,
        "asil_distribution": asil_dist,
        "approval_pct": round(
            sum(c.approval_count for c in project.chains) / (total * 6) * 100, 1
        ) if total > 0 else 0,
    }


def get_perspective(project: SafetyProject, perspective: str) -> list[dict]:
    """Return chains sorted/filtered by perspective."""
    chains = project.chains

    if perspective == "safety_engineer":
        # Top-down: hazards first, grouped by ASIL severity
        asil_order = {"D": 0, "C": 1, "B": 2, "A": 3, "QM": 4, "": 5}
        chains = sorted(chains, key=lambda c: (
            asil_order.get(c.asil_determination.asil_level if c.asil_determination else "", 5),
            0 if c.hazard and c.hazard.status != "gap" else 1,
            c.chain_id,
        ))
    elif perspective == "test_engineer":
        # Bottom-up: test cases first, unverified FSRs highlighted
        chains = sorted(chains, key=lambda c: (
            0 if c.test_case and c.test_case.status == "gap" else 1,
            0 if c.fsr and c.fsr.status != "gap" else 1,
            c.chain_id,
        ))
    elif perspective == "req_engineer":
        # FSR-focused: by FSR status
        status_order = {"gap": 0, "draft": 1, "review": 2, "approved": 3}
        chains = sorted(chains, key=lambda c: (
            status_order.get(c.fsr.status if c.fsr else "gap", 0),
            c.chain_id,
        ))
    elif perspective == "manager":
        # By completeness: most gaps first
        chains = sorted(chains, key=lambda c: (-c.gap_count, c.chain_id))

    return [c.to_dict() for c in chains]
