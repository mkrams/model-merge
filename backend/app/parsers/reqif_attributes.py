"""
ReqIF Attribute Schema Analyzer — extracts attribute definitions, datatypes,
and object types from ReqIF files to enable cross-tool attribute mapping.
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from dataclasses import dataclass, field


@dataclass
class ReqIFDataType:
    identifier: str
    long_name: str
    kind: str  # string, xhtml, integer, real, boolean, date, enumeration
    enum_values: list[str] = field(default_factory=list)
    min_val: str | None = None
    max_val: str | None = None


@dataclass
class ReqIFAttributeDef:
    identifier: str
    long_name: str
    datatype_id: str
    datatype_name: str
    datatype_kind: str
    parent_type_id: str
    parent_type_name: str
    is_editable: bool = True


@dataclass
class ReqIFObjectType:
    identifier: str
    long_name: str
    attributes: list[ReqIFAttributeDef] = field(default_factory=list)


@dataclass
class ReqIFSchema:
    """Complete schema of a ReqIF file — datatypes, object types, attributes."""
    tool_name: str
    datatypes: list[ReqIFDataType] = field(default_factory=list)
    object_types: list[ReqIFObjectType] = field(default_factory=list)
    spec_object_count: int = 0
    spec_relation_count: int = 0

    def all_attributes(self) -> list[ReqIFAttributeDef]:
        """Flat list of all attribute definitions across all object types."""
        attrs = []
        seen = set()
        for ot in self.object_types:
            for a in ot.attributes:
                if a.identifier not in seen:
                    attrs.append(a)
                    seen.add(a.identifier)
        return attrs

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "datatypes": [
                {"id": d.identifier, "name": d.long_name, "kind": d.kind,
                 "enum_values": d.enum_values}
                for d in self.datatypes
            ],
            "object_types": [
                {
                    "id": ot.identifier,
                    "name": ot.long_name,
                    "attributes": [
                        {
                            "id": a.identifier,
                            "name": a.long_name,
                            "datatype": a.datatype_name,
                            "datatype_kind": a.datatype_kind,
                            "parent_type": a.parent_type_name,
                        }
                        for a in ot.attributes
                    ],
                }
                for ot in self.object_types
            ],
            "spec_object_count": self.spec_object_count,
            "spec_relation_count": self.spec_relation_count,
        }


@dataclass
class AttributeMapping:
    """A suggested mapping between two attributes from different files."""
    attr_a: dict  # {id, name, datatype, datatype_kind, parent_type}
    attr_b: dict | None  # None if unmapped
    confidence: float  # 0.0 to 1.0
    match_reason: str  # "exact_name", "fuzzy_name", "same_standard", "manual"
    compatible_types: bool
    status: str = "suggested"  # suggested, accepted, rejected, manual


@dataclass
class AttributeMappingAnalysis:
    """Full attribute mapping analysis between two ReqIF files."""
    schema_a: dict
    schema_b: dict
    mappings: list[dict]
    unmapped_a: list[dict]
    unmapped_b: list[dict]
    stats: dict


def extract_schema(text: str, filename: str = "") -> ReqIFSchema:
    """Extract the full attribute schema from a ReqIF file."""
    root = ET.fromstring(text)

    # Detect namespace
    tag = root.tag
    ns_prefix = ""
    if '{' in tag:
        ns_prefix = tag[tag.find('{'):tag.find('}') + 1]

    # Try to detect tool from header
    tool_name = "Unknown"
    header = root.find(f'.//{ns_prefix}REQ-IF-HEADER')
    if header is not None:
        source = header.get('SOURCE-TOOL-ID', '')
        if not source:
            for child in header:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag == 'SOURCE-TOOL-ID' and child.text:
                    source = child.text
        if source:
            tool_name = source
        else:
            title_el = header.find(f'{ns_prefix}TITLE')
            if title_el is not None and title_el.text:
                tool_name = title_el.text

    content = (
        root.find(f'.//{ns_prefix}REQ-IF-CONTENT')
        or root.find('.//REQ-IF-CONTENT')
        or root
    )

    schema = ReqIFSchema(tool_name=tool_name)

    # Parse datatypes
    datatype_map = {}
    for el in content.iter():
        el_tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if not el_tag.startswith('DATATYPE-DEFINITION'):
            continue
        identifier = el.get('IDENTIFIER', '')
        long_name = el.get('LONG-NAME', el_tag.replace('DATATYPE-DEFINITION-', ''))

        kind = el_tag.replace('DATATYPE-DEFINITION-', '').lower()

        enum_values = []
        if kind == 'enumeration':
            for ev in el.iter():
                ev_tag = ev.tag.split('}')[-1] if '}' in ev.tag else ev.tag
                if ev_tag == 'ENUM-VALUE':
                    ev_name = ev.get('LONG-NAME', ev.get('IDENTIFIER', ''))
                    if ev_name:
                        enum_values.append(ev_name)

        dt = ReqIFDataType(
            identifier=identifier,
            long_name=long_name,
            kind=kind,
            enum_values=enum_values,
        )
        schema.datatypes.append(dt)
        datatype_map[identifier] = dt

    # Parse spec object types and their attribute definitions
    for el in content.iter():
        el_tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if el_tag != 'SPEC-OBJECT-TYPE':
            continue

        ot = ReqIFObjectType(
            identifier=el.get('IDENTIFIER', ''),
            long_name=el.get('LONG-NAME', el.get('IDENTIFIER', 'Unknown')),
        )

        # Find attribute definitions within this type
        for attr_el in el.iter():
            attr_tag = attr_el.tag.split('}')[-1] if '}' in attr_el.tag else attr_el.tag
            if not attr_tag.startswith('ATTRIBUTE-DEFINITION'):
                continue

            attr_id = attr_el.get('IDENTIFIER', '')
            attr_name = attr_el.get('LONG-NAME', attr_id)
            is_editable = attr_el.get('IS-EDITABLE', 'true').lower() == 'true'

            # Find datatype reference
            dt_id = ""
            for ref_el in attr_el.iter():
                ref_tag = ref_el.tag.split('}')[-1] if '}' in ref_el.tag else ref_el.tag
                if ref_tag.endswith('-REF') and ref_el.text:
                    dt_id = ref_el.text.strip()
                    break

            dt = datatype_map.get(dt_id)
            dt_name = dt.long_name if dt else attr_tag.replace('ATTRIBUTE-DEFINITION-', '')
            dt_kind = dt.kind if dt else attr_tag.replace('ATTRIBUTE-DEFINITION-', '').lower()

            ot.attributes.append(ReqIFAttributeDef(
                identifier=attr_id,
                long_name=attr_name,
                datatype_id=dt_id,
                datatype_name=dt_name,
                datatype_kind=dt_kind,
                parent_type_id=ot.identifier,
                parent_type_name=ot.long_name,
                is_editable=is_editable,
            ))

        schema.object_types.append(ot)

    # Count objects and relations
    for el in content.iter():
        el_tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if el_tag == 'SPEC-OBJECT':
            schema.spec_object_count += 1
        elif el_tag == 'SPEC-RELATION':
            schema.spec_relation_count += 1

    return schema


# Standard ReqIF attribute names (used across tools)
STANDARD_ATTRS = {
    'reqif.foreignid', 'reqif.foreigncreatedby', 'reqif.foreigncreatedon',
    'reqif.foreignmodifiedby', 'reqif.foreignmodifiedon',
    'reqif.chaptername', 'reqif.text', 'reqif.name', 'reqif.description',
    'reqif.prefix', 'reqif.category',
}


def _normalize_name(name: str) -> str:
    """Normalize attribute name for comparison."""
    return name.lower().strip().replace(' ', '_').replace('-', '_').replace('.', '_')


def _are_types_compatible(kind_a: str, kind_b: str) -> bool:
    """Check if two datatype kinds are compatible for mapping."""
    if kind_a == kind_b:
        return True
    # String and XHTML are often interchangeable
    compatible = {
        frozenset({'string', 'xhtml'}),
        frozenset({'integer', 'real'}),
    }
    return frozenset({kind_a, kind_b}) in compatible


def analyze_attribute_mapping(schema_a: ReqIFSchema, schema_b: ReqIFSchema) -> dict:
    """Compare two ReqIF schemas and suggest attribute mappings."""
    attrs_a = schema_a.all_attributes()
    attrs_b = schema_b.all_attributes()

    # Build lookup by normalized name
    b_by_name: dict[str, ReqIFAttributeDef] = {}
    for b in attrs_b:
        norm = _normalize_name(b.long_name)
        b_by_name[norm] = b

    mappings: list[dict] = []
    mapped_b_ids: set[str] = set()

    for a in attrs_a:
        norm_a = _normalize_name(a.long_name)
        best_match = None
        best_confidence = 0.0
        match_reason = ""

        # 1. Exact name match
        if norm_a in b_by_name:
            b = b_by_name[norm_a]
            best_match = b
            best_confidence = 1.0
            match_reason = "exact_name"
        else:
            # 2. Standard ReqIF attribute match
            if norm_a.replace('_', '.') in STANDARD_ATTRS or norm_a in STANDARD_ATTRS:
                for bn, b in b_by_name.items():
                    if bn.replace('_', '.') in STANDARD_ATTRS or bn in STANDARD_ATTRS:
                        # Check if they're the same standard attribute
                        a_base = norm_a.split('_')[-1] if '_' in norm_a else norm_a
                        b_base = bn.split('_')[-1] if '_' in bn else bn
                        if a_base == b_base:
                            best_match = b
                            best_confidence = 0.9
                            match_reason = "same_standard"
                            break

            # 3. Fuzzy name match
            if not best_match:
                for bn, b in b_by_name.items():
                    if b.identifier in mapped_b_ids:
                        continue
                    ratio = SequenceMatcher(None, norm_a, bn).ratio()
                    if ratio > 0.7 and ratio > best_confidence:
                        best_match = b
                        best_confidence = ratio
                        match_reason = "fuzzy_name"

        if best_match:
            compatible = _are_types_compatible(a.datatype_kind, best_match.datatype_kind)
            mappings.append({
                "attr_a": {
                    "id": a.identifier, "name": a.long_name,
                    "datatype": a.datatype_name, "datatype_kind": a.datatype_kind,
                    "parent_type": a.parent_type_name,
                },
                "attr_b": {
                    "id": best_match.identifier, "name": best_match.long_name,
                    "datatype": best_match.datatype_name, "datatype_kind": best_match.datatype_kind,
                    "parent_type": best_match.parent_type_name,
                },
                "confidence": round(best_confidence, 2),
                "match_reason": match_reason,
                "compatible_types": compatible,
                "status": "suggested",
            })
            mapped_b_ids.add(best_match.identifier)

    # Find unmapped attributes
    mapped_a_ids = {m["attr_a"]["id"] for m in mappings}
    unmapped_a = [
        {"id": a.identifier, "name": a.long_name, "datatype": a.datatype_name,
         "datatype_kind": a.datatype_kind, "parent_type": a.parent_type_name}
        for a in attrs_a if a.identifier not in mapped_a_ids
    ]
    unmapped_b = [
        {"id": b.identifier, "name": b.long_name, "datatype": b.datatype_name,
         "datatype_kind": b.datatype_kind, "parent_type": b.parent_type_name}
        for b in attrs_b if b.identifier not in mapped_b_ids
    ]

    # Stats
    total_a = len(attrs_a)
    total_b = len(attrs_b)
    exact = sum(1 for m in mappings if m["match_reason"] == "exact_name")
    fuzzy = sum(1 for m in mappings if m["match_reason"] == "fuzzy_name")
    standard = sum(1 for m in mappings if m["match_reason"] == "same_standard")
    incompatible = sum(1 for m in mappings if not m["compatible_types"])

    return {
        "schema_a": schema_a.to_dict(),
        "schema_b": schema_b.to_dict(),
        "mappings": sorted(mappings, key=lambda m: -m["confidence"]),
        "unmapped_a": unmapped_a,
        "unmapped_b": unmapped_b,
        "stats": {
            "total_attrs_a": total_a,
            "total_attrs_b": total_b,
            "mapped_count": len(mappings),
            "unmapped_a_count": len(unmapped_a),
            "unmapped_b_count": len(unmapped_b),
            "exact_matches": exact,
            "fuzzy_matches": fuzzy,
            "standard_matches": standard,
            "incompatible_types": incompatible,
        },
    }
