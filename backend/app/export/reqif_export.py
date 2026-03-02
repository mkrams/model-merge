"""Export safety chains as tool-agnostic ReqIF XML."""
from __future__ import annotations
import uuid
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from ..models.safety import SafetyProject


def export_to_reqif(project: SafetyProject) -> str:
    """Convert a SafetyProject to ReqIF XML string."""
    root = Element("REQ-IF", {
        "xmlns": "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    })

    header = SubElement(root, "THE-HEADER")
    req_if_header = SubElement(header, "REQ-IF-HEADER", {
        "IDENTIFIER": f"_header_{uuid.uuid4().hex[:8]}",
    })
    SubElement(req_if_header, "COMMENT").text = f"Exported from ModelMerge ASIL Assistant"
    SubElement(req_if_header, "CREATION-TIME").text = datetime.utcnow().isoformat() + "Z"
    SubElement(req_if_header, "TITLE").text = project.name or "Safety Chain Export"

    core = SubElement(root, "CORE-CONTENT")
    content = SubElement(core, "REQ-IF-CONTENT")

    # ── Datatypes ──
    datatypes = SubElement(content, "DATATYPES")
    _dt_string = f"_dt_string_{uuid.uuid4().hex[:6]}"
    _dt_enum_status = f"_dt_enum_status_{uuid.uuid4().hex[:6]}"
    _dt_enum_asil = f"_dt_enum_asil_{uuid.uuid4().hex[:6]}"

    SubElement(datatypes, "DATATYPE-DEFINITION-STRING", {
        "IDENTIFIER": _dt_string, "LONG-NAME": "String", "MAX-LENGTH": "4096",
    })

    enum_status = SubElement(datatypes, "DATATYPE-DEFINITION-ENUMERATION", {
        "IDENTIFIER": _dt_enum_status, "LONG-NAME": "Status",
    })
    vals_status = SubElement(enum_status, "SPECIFIED-VALUES")
    for i, s in enumerate(["gap", "draft", "review", "approved"]):
        SubElement(vals_status, "ENUM-VALUE", {
            "IDENTIFIER": f"_ev_status_{i}", "LONG-NAME": s,
        })

    enum_asil = SubElement(datatypes, "DATATYPE-DEFINITION-ENUMERATION", {
        "IDENTIFIER": _dt_enum_asil, "LONG-NAME": "ASIL",
    })
    vals_asil = SubElement(enum_asil, "SPECIFIED-VALUES")
    for i, a in enumerate(["QM", "A", "B", "C", "D"]):
        SubElement(vals_asil, "ENUM-VALUE", {
            "IDENTIFIER": f"_ev_asil_{i}", "LONG-NAME": a,
        })

    # ── Spec Object Types (one per chain level) ──
    spec_types = SubElement(content, "SPEC-TYPES")
    type_ids = {}
    levels = ["Hazard", "HazardousEvent", "SafetyGoal", "FSR", "TestCase"]

    for level in levels:
        tid = f"_sot_{level}_{uuid.uuid4().hex[:6]}"
        type_ids[level] = tid
        sot = SubElement(spec_types, "SPEC-OBJECT-TYPE", {
            "IDENTIFIER": tid, "LONG-NAME": level,
        })
        attrs = SubElement(sot, "SPEC-ATTRIBUTES")
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{level}_name", "LONG-NAME": "Name",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{level}_desc", "LONG-NAME": "Description",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{level}_id", "LONG-NAME": "ItemID",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))

    # Relation type
    rel_type_id = f"_srt_trace_{uuid.uuid4().hex[:6]}"
    srt = SubElement(spec_types, "SPEC-RELATION-TYPE", {
        "IDENTIFIER": rel_type_id, "LONG-NAME": "Trace",
    })

    # Specification type
    spec_type_id = f"_st_spec_{uuid.uuid4().hex[:6]}"
    SubElement(spec_types, "SPECIFICATION-TYPE", {
        "IDENTIFIER": spec_type_id, "LONG-NAME": "SafetyChainSpec",
    })

    # ── Spec Objects ──
    spec_objects = SubElement(content, "SPEC-OBJECTS")
    obj_ids = {}  # (chain_id, level) → object_id

    for chain in project.chains:
        items = [
            ("Hazard", chain.hazard),
            ("HazardousEvent", chain.hazardous_event),
            ("SafetyGoal", chain.safety_goal),
            ("FSR", chain.fsr),
            ("TestCase", chain.test_case),
        ]
        for level_name, item in items:
            if item and item.status != "gap":
                oid = f"_so_{chain.chain_id}_{level_name}_{uuid.uuid4().hex[:6]}"
                obj_ids[(chain.chain_id, level_name)] = oid

                so = SubElement(spec_objects, "SPEC-OBJECT", {
                    "IDENTIFIER": oid, "LONG-NAME": item.name or f"{level_name} (unnamed)",
                })
                sotype = SubElement(so, "TYPE")
                SubElement(sotype, "SPEC-OBJECT-TYPE-REF").text = type_ids[level_name]

                values = SubElement(so, "VALUES")
                _add_string_value(values, f"_ad_{level_name}_name", item.name)
                _add_string_value(values, f"_ad_{level_name}_desc", item.description)
                _add_string_value(values, f"_ad_{level_name}_id", item.id)

    # ── Spec Relations (trace links) ──
    relations = SubElement(content, "SPEC-RELATIONS")
    link_pairs = [
        ("Hazard", "HazardousEvent"),
        ("HazardousEvent", "SafetyGoal"),
        ("SafetyGoal", "FSR"),
        ("FSR", "TestCase"),
    ]

    for chain in project.chains:
        for src_level, tgt_level in link_pairs:
            src_key = (chain.chain_id, src_level)
            tgt_key = (chain.chain_id, tgt_level)
            if src_key in obj_ids and tgt_key in obj_ids:
                rid = f"_sr_{uuid.uuid4().hex[:8]}"
                rel = SubElement(relations, "SPEC-RELATION", {
                    "IDENTIFIER": rid, "LONG-NAME": f"{src_level} → {tgt_level}",
                })
                rel_type = SubElement(rel, "TYPE")
                SubElement(rel_type, "SPEC-RELATION-TYPE-REF").text = rel_type_id
                source = SubElement(rel, "SOURCE")
                SubElement(source, "SPEC-OBJECT-REF").text = obj_ids[src_key]
                target = SubElement(rel, "TARGET")
                SubElement(target, "SPEC-OBJECT-REF").text = obj_ids[tgt_key]

    # ── Specifications (hierarchy) ──
    specifications = SubElement(content, "SPECIFICATIONS")
    spec = SubElement(specifications, "SPECIFICATION", {
        "IDENTIFIER": f"_spec_{uuid.uuid4().hex[:6]}",
        "LONG-NAME": project.name or "Safety Chains",
    })
    spec_t = SubElement(spec, "TYPE")
    SubElement(spec_t, "SPECIFICATION-TYPE-REF").text = spec_type_id

    children = SubElement(spec, "CHILDREN")
    for chain in project.chains:
        chain_hier = SubElement(children, "SPEC-HIERARCHY", {
            "IDENTIFIER": f"_sh_chain_{chain.chain_id}",
            "LONG-NAME": f"Chain: {chain.chain_id}",
        })
        # Add items as children
        chain_children = SubElement(chain_hier, "CHILDREN")
        for level_name in ["Hazard", "HazardousEvent", "SafetyGoal", "FSR", "TestCase"]:
            key = (chain.chain_id, level_name)
            if key in obj_ids:
                item_hier = SubElement(chain_children, "SPEC-HIERARCHY", {
                    "IDENTIFIER": f"_sh_{uuid.uuid4().hex[:6]}",
                })
                obj_ref = SubElement(item_hier, "OBJECT")
                SubElement(obj_ref, "SPEC-OBJECT-REF").text = obj_ids[key]

    # Format XML
    raw_xml = tostring(root, encoding="unicode")
    try:
        return parseString(raw_xml).toprettyxml(indent="  ", encoding=None)
    except Exception:
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{raw_xml}'


def _type_ref(tag: str, ref_id: str) -> Element:
    """Create a TYPE element with a ref."""
    t = Element("TYPE")
    SubElement(t, tag).text = ref_id
    return t


def _add_string_value(parent: Element, attr_def_id: str, value: str):
    """Add an ATTRIBUTE-VALUE-STRING to parent."""
    av = SubElement(parent, "ATTRIBUTE-VALUE-STRING", {"THE-VALUE": value or ""})
    defn = SubElement(av, "DEFINITION")
    SubElement(defn, "ATTRIBUTE-DEFINITION-STRING-REF").text = attr_def_id
