"""Export graph-based safety project to ReqIF XML format."""
from __future__ import annotations
import uuid
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from ..models.safety import SafetyProject, ItemType


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
    SubElement(req_if_header, "COMMENT").text = "Exported from ModelMerge ASIL Assistant (graph model)"
    SubElement(req_if_header, "CREATION-TIME").text = datetime.utcnow().isoformat() + "Z"
    SubElement(req_if_header, "TITLE").text = project.name or "Safety Project Export"

    core = SubElement(root, "CORE-CONTENT")
    content = SubElement(core, "REQ-IF-CONTENT")

    # ── Datatypes ──
    datatypes = SubElement(content, "DATATYPES")
    _dt_string = f"_dt_string_{uuid.uuid4().hex[:6]}"
    _dt_enum_status = f"_dt_enum_status_{uuid.uuid4().hex[:6]}"

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

    # ── Spec Object Types (one per item type) ──
    spec_types = SubElement(content, "SPEC-TYPES")
    type_ids = {}

    for item_type in ItemType:
        type_str = item_type.value
        tid = f"_sot_{type_str}_{uuid.uuid4().hex[:6]}"
        type_ids[type_str] = tid

        sot = SubElement(spec_types, "SPEC-OBJECT-TYPE", {
            "IDENTIFIER": tid, "LONG-NAME": type_str,
        })
        attrs = SubElement(sot, "SPEC-ATTRIBUTES")
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{type_str}_name", "LONG-NAME": "Name",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{type_str}_desc", "LONG-NAME": "Description",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{type_str}_id", "LONG-NAME": "ItemID",
        }).append(_type_ref("DATATYPE-DEFINITION-STRING-REF", _dt_string))
        SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING", {
            "IDENTIFIER": f"_ad_{type_str}_status", "LONG-NAME": "Status",
        }).append(_type_ref("DATATYPE-DEFINITION-ENUMERATION-REF", _dt_enum_status))

    # Relation type
    rel_type_id = f"_srt_trace_{uuid.uuid4().hex[:6]}"
    srt = SubElement(spec_types, "SPEC-RELATION-TYPE", {
        "IDENTIFIER": rel_type_id, "LONG-NAME": "Trace",
    })

    # ── Spec Objects ──
    spec_objects = SubElement(content, "SPEC-OBJECTS")
    obj_ids = {}  # item_id → object_id

    for item in project.items:
        type_str = item.item_type.value if hasattr(item.item_type, 'value') else item.item_type
        oid = f"_so_{item.item_id}_{uuid.uuid4().hex[:6]}"
        obj_ids[item.item_id] = oid

        so = SubElement(spec_objects, "SPEC-OBJECT", {
            "IDENTIFIER": oid, "LONG-NAME": item.name or item.item_id,
        })
        sotype = SubElement(so, "TYPE")
        SubElement(sotype, "SPEC-OBJECT-TYPE-REF").text = type_ids[type_str]

        values = SubElement(so, "VALUES")
        _add_string_value(values, f"_ad_{type_str}_name", item.name)
        _add_string_value(values, f"_ad_{type_str}_desc", item.description)
        _add_string_value(values, f"_ad_{type_str}_id", item.item_id)
        _add_string_value(values, f"_ad_{type_str}_status", item.status)

    # ── Spec Relations (graph links) ──
    relations = SubElement(content, "SPEC-RELATIONS")

    for link in project.links:
        rid = f"_sr_{uuid.uuid4().hex[:8]}"
        rel = SubElement(relations, "SPEC-RELATION", {
            "IDENTIFIER": rid, "LONG-NAME": f"{link.link_type.value if hasattr(link.link_type, 'value') else link.link_type}",
        })
        rel_type = SubElement(rel, "TYPE")
        SubElement(rel_type, "SPEC-RELATION-TYPE-REF").text = rel_type_id

        source = SubElement(rel, "SOURCE")
        SubElement(source, "SPEC-OBJECT-REF").text = obj_ids.get(link.source_id, "")
        target = SubElement(rel, "TARGET")
        SubElement(target, "SPEC-OBJECT-REF").text = obj_ids.get(link.target_id, "")

    # ── Specifications (hierarchy by type) ──
    specifications = SubElement(content, "SPECIFICATIONS")
    spec = SubElement(specifications, "SPECIFICATION", {
        "IDENTIFIER": f"_spec_{uuid.uuid4().hex[:6]}",
        "LONG-NAME": project.name or "Safety Project",
    })

    children = SubElement(spec, "CHILDREN")

    # Group items by type
    for item_type in ItemType:
        type_str = item_type.value
        type_items = [i for i in project.items if (i.item_type.value if hasattr(i.item_type, 'value') else i.item_type) == type_str]

        if type_items:
            type_hier = SubElement(children, "SPEC-HIERARCHY", {
                "IDENTIFIER": f"_sh_type_{type_str}",
                "LONG-NAME": f"{type_str.replace('_', ' ').title()}s",
            })
            type_children = SubElement(type_hier, "CHILDREN")

            for item in type_items:
                if item.item_id in obj_ids:
                    item_hier = SubElement(type_children, "SPEC-HIERARCHY", {
                        "IDENTIFIER": f"_sh_{uuid.uuid4().hex[:6]}",
                    })
                    obj_ref = SubElement(item_hier, "OBJECT")
                    SubElement(obj_ref, "SPEC-OBJECT-REF").text = obj_ids[item.item_id]

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
