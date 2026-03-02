"""
AST models for SysML v2 and ReqIF parsed elements.
These dataclasses define the internal representation used by the parser,
merge engine, and API serialization.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid


def _id() -> str:
    return str(uuid.uuid4())[:8]


@dataclass
class Import:
    path: str
    visibility: str = "private"  # "private" or "public"

    def to_dict(self) -> dict:
        return {"path": self.path, "visibility": self.visibility}


@dataclass
class Attribute:
    name: str
    type_ref: Optional[str] = None
    default_value: Optional[str] = None
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type_ref": self.type_ref,
            "default_value": self.default_value,
            "raw": self.raw,
        }


@dataclass
class PortDef:
    name: str
    direction: Optional[str] = None  # "in", "out", or None
    type_ref: Optional[str] = None
    flows: list[str] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "port_def",
            "direction": self.direction,
            "type_ref": self.type_ref,
            "flows": self.flows,
            "raw": self.raw,
        }


@dataclass
class Port:
    name: str
    type_ref: Optional[str] = None
    direction: Optional[str] = None
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "port",
            "type_ref": self.type_ref,
            "direction": self.direction,
            "raw": self.raw,
        }


@dataclass
class Constraint:
    expression: str
    raw: str = ""

    def to_dict(self) -> dict:
        return {"expression": self.expression, "raw": self.raw}


@dataclass
class RequirementDef:
    name: str
    req_id: Optional[str] = None
    doc: str = ""
    subject: Optional[str] = None
    attributes: list[Attribute] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "requirement_def",
            "req_id": self.req_id,
            "doc": self.doc,
            "subject": self.subject,
            "attributes": [a.to_dict() for a in self.attributes],
            "constraints": [c.to_dict() for c in self.constraints],
            "raw": self.raw,
        }


@dataclass
class InterfaceDef:
    name: str
    doc: str = ""
    ends: list[str] = field(default_factory=list)
    flows: list[str] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "interface_def",
            "doc": self.doc,
            "ends": self.ends,
            "flows": self.flows,
            "raw": self.raw,
        }


@dataclass
class Interface:
    name: str
    type_ref: Optional[str] = None
    connections: list[str] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "interface",
            "type_ref": self.type_ref,
            "connections": self.connections,
            "raw": self.raw,
        }


@dataclass
class PartDef:
    name: str
    doc: str = ""
    attributes: list[Attribute] = field(default_factory=list)
    ports: list[Port] = field(default_factory=list)
    children: list[Part] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "part_def",
            "doc": self.doc,
            "attributes": [a.to_dict() for a in self.attributes],
            "ports": [p.to_dict() for p in self.ports],
            "children": [c.to_dict() for c in self.children],
            "raw": self.raw,
        }


@dataclass
class Part:
    name: str
    type_ref: Optional[str] = None
    doc: str = ""
    multiplicity: Optional[str] = None
    subsets: Optional[str] = None
    redefines: Optional[str] = None
    attributes: list[Attribute] = field(default_factory=list)
    ports: list[Port] = field(default_factory=list)
    children: list[Part] = field(default_factory=list)
    interfaces: list[Interface] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "part",
            "type_ref": self.type_ref,
            "doc": self.doc,
            "multiplicity": self.multiplicity,
            "subsets": self.subsets,
            "redefines": self.redefines,
            "attributes": [a.to_dict() for a in self.attributes],
            "ports": [p.to_dict() for p in self.ports],
            "children": [c.to_dict() for c in self.children],
            "interfaces": [i.to_dict() for i in self.interfaces],
            "raw": self.raw,
        }


@dataclass
class Connection:
    """Represents flow, satisfy, or derivation connections."""
    kind: str  # "flow", "satisfy", "derivation", "interface_connect"
    source: str = ""
    target: str = ""
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "connection",
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "raw": self.raw,
        }


@dataclass
class Package:
    name: str
    doc: str = ""
    imports: list[Import] = field(default_factory=list)
    part_defs: list[PartDef] = field(default_factory=list)
    port_defs: list[PortDef] = field(default_factory=list)
    interface_defs: list[InterfaceDef] = field(default_factory=list)
    requirement_defs: list[RequirementDef] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    values: list[Attribute] = field(default_factory=list)
    subpackages: list[Package] = field(default_factory=list)
    raw: str = ""
    id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": "package",
            "doc": self.doc,
            "imports": [i.to_dict() for i in self.imports],
            "part_defs": [p.to_dict() for p in self.part_defs],
            "port_defs": [p.to_dict() for p in self.port_defs],
            "interface_defs": [i.to_dict() for i in self.interface_defs],
            "requirement_defs": [r.to_dict() for r in self.requirement_defs],
            "parts": [p.to_dict() for p in self.parts],
            "connections": [c.to_dict() for c in self.connections],
            "values": [v.to_dict() for v in self.values],
            "subpackages": [s.to_dict() for s in self.subpackages],
            "raw": self.raw,
        }

    def all_elements(self) -> list[dict]:
        """Flatten all elements into a list for the merge view."""
        elements = []
        elements.extend(p.to_dict() for p in self.part_defs)
        elements.extend(p.to_dict() for p in self.port_defs)
        elements.extend(i.to_dict() for i in self.interface_defs)
        elements.extend(r.to_dict() for r in self.requirement_defs)
        elements.extend(p.to_dict() for p in self.parts)
        elements.extend(c.to_dict() for c in self.connections)
        elements.extend({"id": _id(), "name": v.name, "type": "value", **v.to_dict()} for v in self.values)
        for sub in self.subpackages:
            elements.extend(sub.all_elements())
        return elements


@dataclass
class ParsedModel:
    """Top-level parsed model container."""
    filename: str
    model_type: str  # "sysmlv2" or "reqif"
    packages: list[Package] = field(default_factory=list)
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        all_elements = []
        for pkg in self.packages:
            all_elements.extend(pkg.all_elements())
        return {
            "model_id": self.model_id,
            "filename": self.filename,
            "model_type": self.model_type,
            "packages": [p.to_dict() for p in self.packages],
            "elements": all_elements,
            "summary": {
                "package_count": len(self.packages),
                "element_count": len(all_elements),
                "part_defs": sum(len(p.part_defs) for p in self.packages),
                "port_defs": sum(len(p.port_defs) for p in self.packages),
                "interface_defs": sum(len(p.interface_defs) for p in self.packages),
                "requirement_defs": sum(len(p.requirement_defs) for p in self.packages),
                "parts": sum(len(p.parts) for p in self.packages),
            },
        }
