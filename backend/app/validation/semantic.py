"""
Lightweight semantic validator for merged models.
Runs fast checks before calling the full compiler.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from ..models.ast import ParsedModel


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "semantic"  # "semantic" or "compiler"

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "source": self.source,
        }


def validate_semantic(model: ParsedModel) -> ValidationResult:
    """Run lightweight semantic validation on a parsed model."""
    result = ValidationResult()

    all_elements = []
    all_names: dict[str, int] = {}
    all_imports = set()
    all_package_names = set()

    for pkg in model.packages:
        all_package_names.add(pkg.name)
        _collect_names(pkg, pkg.name, all_names, all_elements, all_imports)

    # Check 1: Duplicate element names within same scope
    for name, count in all_names.items():
        if count > 1:
            result.warnings.append(f"Duplicate element name: '{name}' appears {count} times")

    # Check 2: Unresolved imports
    for imp in all_imports:
        # Extract the package name from import path
        parts = imp.replace("::*", "").replace("::", ".").split(".")
        base_pkg = parts[0] if parts else ""
        if base_pkg and base_pkg not in all_package_names:
            # Check if it's a standard library import
            std_libs = {
                "ScalarValues", "Quantities", "MeasurementReferences",
                "ISQ", "SI", "ScalarFunctions", "RequirementDerivation",
            }
            if base_pkg not in std_libs:
                result.warnings.append(
                    f"Import '{imp}' references package '{base_pkg}' "
                    f"which is not defined in the merged model (may be an external dependency)"
                )

    # Check 3: Empty packages
    for pkg in model.packages:
        if (not pkg.part_defs and not pkg.port_defs and not pkg.interface_defs
                and not pkg.requirement_defs and not pkg.parts and not pkg.subpackages
                and not pkg.values and not pkg.connections):
            result.warnings.append(f"Package '{pkg.name}' is empty")

    # Check 4: Requirements without constraints or docs
    for pkg in model.packages:
        for req in pkg.requirement_defs:
            if not req.doc and not req.constraints:
                result.warnings.append(
                    f"Requirement '{req.name}' has no documentation or constraints"
                )

    # Check 5: Part references to undefined types
    known_types = set()
    for pkg in model.packages:
        for pdef in pkg.part_defs:
            known_types.add(pdef.name)
        for pdef in pkg.port_defs:
            known_types.add(pdef.name)

    for pkg in model.packages:
        for part in pkg.parts:
            if part.type_ref and part.type_ref not in known_types:
                # Could be imported, so just warn
                result.warnings.append(
                    f"Part '{part.name}' references type '{part.type_ref}' "
                    f"which may not be defined in the merged model"
                )

    if result.errors:
        result.is_valid = False

    return result


def _collect_names(
    pkg,
    prefix: str,
    names: dict[str, int],
    elements: list,
    imports: set,
):
    """Recursively collect all element names and imports from a package."""
    for imp in pkg.imports:
        imports.add(imp.path)

    for pdef in pkg.part_defs:
        fqn = f"{prefix}.{pdef.name}"
        names[fqn] = names.get(fqn, 0) + 1
        elements.append(fqn)

    for pdef in pkg.port_defs:
        fqn = f"{prefix}.{pdef.name}"
        names[fqn] = names.get(fqn, 0) + 1

    for idef in pkg.interface_defs:
        fqn = f"{prefix}.{idef.name}"
        names[fqn] = names.get(fqn, 0) + 1

    for rdef in pkg.requirement_defs:
        fqn = f"{prefix}.{rdef.name}"
        names[fqn] = names.get(fqn, 0) + 1

    for part in pkg.parts:
        fqn = f"{prefix}.{part.name}"
        names[fqn] = names.get(fqn, 0) + 1

    for sub in pkg.subpackages:
        _collect_names(sub, f"{prefix}.{sub.name}", names, elements, imports)
