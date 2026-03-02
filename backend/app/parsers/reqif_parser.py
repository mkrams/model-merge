"""
ReqIF parser — converts ReqIF XML into the same AST model used for SysML v2.
Uses xml.etree for parsing since the reqif library may not be installed.
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Optional
from ..models.ast import (
    Package, RequirementDef, Attribute, Constraint, Connection, ParsedModel,
)


# ReqIF XML namespaces
NS = {
    'reqif': 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd',
}


def parse_reqif(text: str, filename: str = "unknown.reqif") -> ParsedModel:
    """Parse ReqIF XML content into a ParsedModel."""
    root = ET.fromstring(text)

    # Try to detect namespace
    tag = root.tag
    ns = ""
    if '{' in tag:
        ns = tag[tag.find('{'):tag.find('}') + 1]

    packages = []

    # Extract header info
    header = root.find(f'.//{ns}REQ-IF-HEADER') or root.find('.//REQ-IF-HEADER')
    title = "ReqIF Model"
    if header is not None:
        title_el = header.find(f'{ns}TITLE') or header.find('TITLE')
        if title_el is not None and title_el.text:
            title = title_el.text

    # Find content section
    content = (
        root.find(f'.//{ns}REQ-IF-CONTENT')
        or root.find('.//REQ-IF-CONTENT')
        or root.find('.//CORE-CONTENT')
        or root
    )

    # Parse datatype definitions for attribute mapping
    datatypes = _parse_datatypes(content, ns)

    # Parse spec object types (attribute definitions)
    attr_defs = _parse_attribute_definitions(content, ns)

    # Parse spec objects (requirements)
    requirements = _parse_spec_objects(content, ns, attr_defs, datatypes)

    # Parse relations
    connections = _parse_relations(content, ns)

    # Parse specifications (hierarchical structure)
    specs = _parse_specifications(content, ns)

    # Build package
    pkg = Package(
        name=title,
        requirement_defs=requirements,
        connections=connections,
    )
    packages.append(pkg)

    # Add sub-packages for each specification
    for spec_name, spec_reqs in specs:
        sub = Package(name=spec_name, requirement_defs=spec_reqs)
        pkg.subpackages.append(sub)

    return ParsedModel(
        filename=filename,
        model_type="reqif",
        packages=packages,
    )


def _parse_datatypes(content, ns: str) -> dict:
    """Parse datatype definitions."""
    types = {}
    for dtype in content.iter():
        if 'DATATYPE' in dtype.tag:
            identifier = dtype.get('IDENTIFIER', '')
            long_name = dtype.get('LONG-NAME', dtype.tag.split('}')[-1] if '}' in dtype.tag else dtype.tag)
            types[identifier] = long_name
    return types


def _parse_attribute_definitions(content, ns: str) -> dict:
    """Parse attribute definitions from spec object types."""
    attr_defs = {}
    for el in content.iter():
        tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag.startswith('ATTRIBUTE-DEFINITION'):
            identifier = el.get('IDENTIFIER', '')
            long_name = el.get('LONG-NAME', identifier)
            attr_defs[identifier] = long_name
    return attr_defs


def _parse_spec_objects(content, ns: str, attr_defs: dict, datatypes: dict) -> list[RequirementDef]:
    """Parse SPEC-OBJECTS into RequirementDef list."""
    requirements = []

    for spec_obj in content.iter():
        tag = spec_obj.tag.split('}')[-1] if '}' in spec_obj.tag else spec_obj.tag
        if tag != 'SPEC-OBJECT':
            continue

        identifier = spec_obj.get('IDENTIFIER', '')
        long_name = spec_obj.get('LONG-NAME', identifier)
        desc = spec_obj.get('DESC', '')
        last_change = spec_obj.get('LAST-CHANGE', '')

        attributes = []
        doc_text = desc

        # Parse attribute values
        for val_el in spec_obj.iter():
            val_tag = val_el.tag.split('}')[-1] if '}' in val_el.tag else val_el.tag
            if val_tag.startswith('ATTRIBUTE-VALUE'):
                value = val_el.get('THE-VALUE', '')
                # Check for XHTML content
                for child in val_el.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == 'THE-VALUE' and child.text:
                        value = child.text
                    # Handle xhtml content
                    if 'xhtml' in child.tag.lower() or child_tag in ('div', 'p', 'span'):
                        if child.text:
                            value = child.text

                # Find the definition reference
                def_ref = ""
                for def_el in val_el.iter():
                    def_tag = def_el.tag.split('}')[-1] if '}' in def_el.tag else def_el.tag
                    if 'DEFINITION' in def_tag:
                        for ref_el in def_el.iter():
                            ref_tag = ref_el.tag.split('}')[-1] if '}' in ref_el.tag else ref_el.tag
                            if ref_tag.endswith('-REF'):
                                def_ref = ref_el.text or ''

                attr_name = attr_defs.get(def_ref.strip(), def_ref) if def_ref else val_tag
                if value:
                    attributes.append(Attribute(
                        name=attr_name,
                        default_value=value,
                    ))
                    if 'description' in attr_name.lower() or 'text' in attr_name.lower():
                        doc_text = value

        req = RequirementDef(
            name=long_name,
            req_id=identifier,
            doc=doc_text,
            attributes=attributes,
        )
        requirements.append(req)

    return requirements


def _parse_relations(content, ns: str) -> list[Connection]:
    """Parse SPEC-RELATIONS into connections."""
    connections = []

    for rel in content.iter():
        tag = rel.tag.split('}')[-1] if '}' in rel.tag else rel.tag
        if tag != 'SPEC-RELATION':
            continue

        identifier = rel.get('IDENTIFIER', '')
        source = ""
        target = ""

        for child in rel.iter():
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == 'SOURCE':
                for ref in child.iter():
                    ref_tag = ref.tag.split('}')[-1] if '}' in ref.tag else ref.tag
                    if ref_tag.endswith('-REF') and ref.text:
                        source = ref.text
            elif child_tag == 'TARGET':
                for ref in child.iter():
                    ref_tag = ref.tag.split('}')[-1] if '}' in ref.tag else ref.tag
                    if ref_tag.endswith('-REF') and ref.text:
                        target = ref.text

        if source or target:
            connections.append(Connection(
                kind="reqif_relation",
                source=source,
                target=target,
                raw=f"Relation {identifier}: {source} -> {target}",
            ))

    return connections


def _parse_specifications(content, ns: str) -> list[tuple[str, list[RequirementDef]]]:
    """Parse SPECIFICATIONS — hierarchical groupings of requirements."""
    specs = []

    for spec in content.iter():
        tag = spec.tag.split('}')[-1] if '}' in spec.tag else spec.tag
        if tag != 'SPECIFICATION':
            continue

        spec_name = spec.get('LONG-NAME', spec.get('IDENTIFIER', 'Specification'))
        # We just capture the hierarchy info, not re-parse objects
        specs.append((spec_name, []))

    return specs
