"""
Merge engine — applies merge decisions and produces merged output.
Takes a MergeAnalysis with user decisions and generates the final
merged model, including SysML v2 text or ReqIF XML regeneration.
"""
from __future__ import annotations
from ..models.ast import ParsedModel, Package, Import
from .detector import MergeAnalysis
import uuid
import copy


def apply_merge(
    model_a: ParsedModel,
    model_b: ParsedModel,
    analysis: MergeAnalysis,
    decisions: dict[str, str],
) -> ParsedModel:
    """
    Apply merge decisions and produce a merged model.

    Args:
        model_a: Left model
        model_b: Right model
        analysis: Conflict analysis
        decisions: Map of conflict_id -> resolution ("keep_left", "keep_right", "merge_both")

    Returns:
        A new ParsedModel containing the merged result.
    """
    merged = ParsedModel(
        filename=f"merged_{model_a.filename}",
        model_type=model_a.model_type,
        model_id=str(uuid.uuid4()),
    )

    # Start with a copy of model A's packages as the base
    merged_packages: dict[str, Package] = {}
    for pkg in model_a.packages:
        merged_packages[pkg.name] = _deep_copy_package(pkg)

    # Process model B's packages
    for pkg_b in model_b.packages:
        if pkg_b.name in merged_packages:
            # Same package name — merge contents
            _merge_package_contents(merged_packages[pkg_b.name], pkg_b, analysis, decisions)
        else:
            # New package from B — add it
            merged_packages[pkg_b.name] = _deep_copy_package(pkg_b)

    # Apply conflict decisions for elements
    resolved_elements = _resolve_conflicts(analysis, decisions)

    merged.packages = list(merged_packages.values())

    # Deduplicate imports across merged packages
    for pkg in merged.packages:
        seen_imports = set()
        deduped = []
        for imp in pkg.imports:
            if imp.path not in seen_imports:
                seen_imports.add(imp.path)
                deduped.append(imp)
        pkg.imports = deduped

    return merged


def _deep_copy_package(pkg: Package) -> Package:
    """Deep copy a package."""
    return copy.deepcopy(pkg)


def _merge_package_contents(
    target: Package,
    source: Package,
    analysis: MergeAnalysis,
    decisions: dict[str, str],
):
    """Merge contents of source package into target package."""
    # Merge imports
    existing_imports = {imp.path for imp in target.imports}
    for imp in source.imports:
        if imp.path not in existing_imports:
            target.imports.append(copy.deepcopy(imp))
            existing_imports.add(imp.path)

    # For part_defs, port_defs, etc., check if they conflict
    existing_part_def_names = {p.name for p in target.part_defs}
    for pdef in source.part_defs:
        if pdef.name not in existing_part_def_names:
            target.part_defs.append(copy.deepcopy(pdef))

    existing_port_def_names = {p.name for p in target.port_defs}
    for pdef in source.port_defs:
        if pdef.name not in existing_port_def_names:
            target.port_defs.append(copy.deepcopy(pdef))

    existing_iface_def_names = {i.name for i in target.interface_defs}
    for idef in source.interface_defs:
        if idef.name not in existing_iface_def_names:
            target.interface_defs.append(copy.deepcopy(idef))

    existing_req_names = {r.name for r in target.requirement_defs}
    for rdef in source.requirement_defs:
        if rdef.name not in existing_req_names:
            target.requirement_defs.append(copy.deepcopy(rdef))

    existing_part_names = {p.name for p in target.parts}
    for part in source.parts:
        if part.name not in existing_part_names:
            target.parts.append(copy.deepcopy(part))

    # Merge values
    existing_val_names = {v.name for v in target.values}
    for val in source.values:
        if val.name not in existing_val_names:
            target.values.append(copy.deepcopy(val))

    # Merge connections
    existing_conn_raws = {c.raw for c in target.connections}
    for conn in source.connections:
        if conn.raw not in existing_conn_raws:
            target.connections.append(copy.deepcopy(conn))

    # Merge subpackages
    existing_sub_names = {s.name for s in target.subpackages}
    for sub in source.subpackages:
        if sub.name in existing_sub_names:
            target_sub = next(s for s in target.subpackages if s.name == sub.name)
            _merge_package_contents(target_sub, sub, analysis, decisions)
        else:
            target.subpackages.append(copy.deepcopy(sub))


def _resolve_conflicts(
    analysis: MergeAnalysis,
    decisions: dict[str, str],
) -> list[dict]:
    """Resolve conflicts based on user decisions, return resolved elements."""
    resolved = []

    for conflict in analysis.conflicts:
        decision = decisions.get(conflict.conflict_id, "keep_left")
        if decision == "keep_left":
            resolved.append(conflict.left_element)
        elif decision == "keep_right":
            resolved.append(conflict.right_element)
        elif decision == "merge_both":
            resolved.append(conflict.left_element)
            resolved.append(conflict.right_element)

    return resolved


# ── SysML v2 Text Generation ──────────────────────────────────────────

def generate_sysml_v2(model: ParsedModel) -> str:
    """Generate SysML v2 text from a ParsedModel."""
    lines = []
    for pkg in model.packages:
        lines.append(_gen_package(pkg, indent=0))
    return "\n\n".join(lines)


def _gen_package(pkg: Package, indent: int) -> str:
    tab = "\t" * indent
    lines = [f"{tab}package {pkg.name} {{"]

    if pkg.doc:
        lines.append(f"{tab}\tdoc")
        lines.append(f"{tab}\t/*")
        lines.append(f"{tab}\t * {pkg.doc}")
        lines.append(f"{tab}\t */")

    # Imports
    for imp in pkg.imports:
        lines.append(f"{tab}\t{imp.visibility} import {imp.path};")

    if pkg.imports:
        lines.append("")

    # Values
    for val in pkg.values:
        if val.default_value:
            lines.append(f"{tab}\t{val.name} = {val.default_value};")

    if pkg.values:
        lines.append("")

    # Port definitions
    for pdef in pkg.port_defs:
        if pdef.flows:
            lines.append(f"{tab}\tport def {pdef.name} {{")
            for flow in pdef.flows:
                lines.append(f"{tab}\t\t{flow};")
            lines.append(f"{tab}\t}}")
        else:
            lines.append(f"{tab}\tport def {pdef.name};")

    # Part definitions
    for pdef in pkg.part_defs:
        lines.append(_gen_part_def(pdef, indent + 1))

    # Interface definitions
    for idef in pkg.interface_defs:
        lines.append(_gen_interface_def(idef, indent + 1))

    # Requirement definitions
    for rdef in pkg.requirement_defs:
        lines.append(_gen_requirement(rdef, indent + 1))

    # Parts
    for part in pkg.parts:
        lines.append(_gen_part(part, indent + 1))

    # Connections
    for conn in pkg.connections:
        if conn.raw:
            for raw_line in conn.raw.strip().split("\n"):
                lines.append(f"{tab}\t{raw_line.strip()}")

    # Subpackages
    for sub in pkg.subpackages:
        lines.append(_gen_package(sub, indent + 1))

    lines.append(f"{tab}}}")
    return "\n".join(lines)


def _gen_part_def(pdef, indent: int) -> str:
    tab = "\t" * indent
    has_body = pdef.attributes or pdef.ports or pdef.children or pdef.doc
    if not has_body:
        return f"{tab}part def {pdef.name};"

    lines = [f"{tab}part def {pdef.name} {{"]
    if pdef.doc:
        lines.append(f"{tab}\tdoc /* {pdef.doc} */")
    for attr in pdef.attributes:
        lines.append(_gen_attribute(attr, indent + 1))
    for port in pdef.ports:
        lines.append(f"{tab}\tport {port.name}: {port.type_ref or 'unknown'};")
    for child in pdef.children:
        lines.append(_gen_part(child, indent + 1))
    lines.append(f"{tab}}}")
    return "\n".join(lines)


def _gen_part(part, indent: int) -> str:
    tab = "\t" * indent
    header = f"{tab}part "
    if part.redefines and part.redefines != "redefines":
        header += f"redefines {part.redefines}"
    else:
        header += part.name
    if part.multiplicity:
        header += f"[{part.multiplicity}]"
    if part.type_ref:
        header += f": {part.type_ref}"
    if part.subsets:
        header += f" subsets {part.subsets}"

    has_body = part.attributes or part.ports or part.children or part.interfaces or part.doc
    if not has_body:
        return header + ";"

    lines = [header + " {"]
    if part.doc:
        lines.append(f"{tab}\tdoc /* {part.doc} */")
    for attr in part.attributes:
        lines.append(_gen_attribute(attr, indent + 1))
    for port in part.ports:
        lines.append(f"{tab}\tport {port.name}: {port.type_ref or 'unknown'};")
    for child in part.children:
        lines.append(_gen_part(child, indent + 1))
    for iface in part.interfaces:
        lines.append(f"{tab}\t{iface.raw}" if iface.raw else f"{tab}\tinterface {iface.name};")
    lines.append(f"{tab}}}")
    return "\n".join(lines)


def _gen_attribute(attr, indent: int) -> str:
    tab = "\t" * indent
    parts = [f"{tab}attribute {attr.name}"]
    if attr.type_ref:
        parts.append(f" :> {attr.type_ref}")
    if attr.default_value:
        parts.append(f" = {attr.default_value}")
    return "".join(parts) + ";"


def _gen_interface_def(idef, indent: int) -> str:
    tab = "\t" * indent
    lines = [f"{tab}interface def {idef.name} {{"]
    if idef.doc:
        lines.append(f"{tab}\tdoc /* {idef.doc} */")
    for end in idef.ends:
        lines.append(f"{tab}\t{end};")
    for flow in idef.flows:
        lines.append(f"{tab}\t{flow};")
    lines.append(f"{tab}}}")
    return "\n".join(lines)


def _gen_requirement(rdef, indent: int) -> str:
    tab = "\t" * indent
    name_part = rdef.name
    if rdef.req_id:
        name_part = f"<'{rdef.req_id}'> {rdef.name}"

    has_body = rdef.doc or rdef.attributes or rdef.constraints
    if not has_body:
        return f"{tab}requirement {name_part};"

    lines = [f"{tab}requirement def {name_part} {{"]
    if rdef.doc:
        lines.append(f"{tab}\tdoc /* {rdef.doc} */")
    for attr in rdef.attributes:
        lines.append(_gen_attribute(attr, indent + 1))
    for constraint in rdef.constraints:
        lines.append(f"{tab}\trequire constraint {{ {constraint.expression} }}")
    lines.append(f"{tab}}}")
    return "\n".join(lines)
