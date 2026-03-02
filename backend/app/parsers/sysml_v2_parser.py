"""
Lightweight SysML v2 parser.
Uses regex-based tokenization and recursive descent to extract
structural elements into the AST. Not a full compiler — extracts
enough structure for merge operations and visualization.
"""
from __future__ import annotations
import re
from typing import Optional
from ..models.ast import (
    Package, PartDef, Part, PortDef, Port, InterfaceDef, Interface,
    RequirementDef, Attribute, Constraint, Connection, Import, ParsedModel,
)


class SysMLv2Parser:
    def __init__(self, text: str, filename: str = "unknown.sysml"):
        self.text = text
        self.filename = filename
        self.pos = 0
        self.length = len(text)

    def parse(self) -> ParsedModel:
        packages = []
        while self.pos < self.length:
            self._skip_ws_and_comments()
            if self.pos >= self.length:
                break
            if self._peek_keyword("package"):
                packages.append(self._parse_package())
            else:
                # Skip unknown top-level content
                self.pos += 1
        return ParsedModel(
            filename=self.filename,
            model_type="sysmlv2",
            packages=packages,
        )

    # ── Utility methods ──────────────────────────────────────────────

    def _skip_ws_and_comments(self):
        while self.pos < self.length:
            # Skip whitespace
            if self.text[self.pos].isspace():
                self.pos += 1
                continue
            # Skip line comments
            if self.text[self.pos:self.pos+2] == "//":
                end = self.text.find("\n", self.pos)
                self.pos = end + 1 if end != -1 else self.length
                continue
            # Skip block comments
            if self.text[self.pos:self.pos+2] == "/*":
                end = self.text.find("*/", self.pos + 2)
                self.pos = end + 2 if end != -1 else self.length
                continue
            break

    def _peek_keyword(self, kw: str) -> bool:
        self._skip_ws_and_comments()
        if self.pos + len(kw) > self.length:
            return False
        rest = self.text[self.pos:]
        if rest.startswith(kw):
            after = self.pos + len(kw)
            if after >= self.length or not self.text[after].isalnum() and self.text[after] != '_':
                return True
        return False

    def _match_keyword(self, kw: str) -> bool:
        if self._peek_keyword(kw):
            self.pos += len(kw)
            return True
        return False

    def _read_name(self) -> str:
        self._skip_ws_and_comments()
        start = self.pos
        # Handle quoted names like 'REQ-42'
        if self.pos < self.length and self.text[self.pos] == '<':
            end = self.text.find('>', self.pos)
            if end != -1:
                self.pos = end + 1
                return self.text[start:self.pos]
        # Regular identifier (allows :: for qualified names)
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '_-:.~#'):
            self.pos += 1
        name = self.text[start:self.pos].strip()
        return name

    def _read_until_closing_brace(self) -> str:
        """Read content between matching { } braces. Assumes opening { already consumed."""
        depth = 1
        start = self.pos
        while self.pos < self.length and depth > 0:
            ch = self.text[self.pos]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            elif ch == '/' and self.pos + 1 < self.length:
                if self.text[self.pos + 1] == '/':
                    end = self.text.find('\n', self.pos)
                    self.pos = end if end != -1 else self.length
                elif self.text[self.pos + 1] == '*':
                    end = self.text.find('*/', self.pos + 2)
                    self.pos = end + 1 if end != -1 else self.length
            self.pos += 1
        return self.text[start:self.pos - 1]

    def _expect_char(self, ch: str):
        self._skip_ws_and_comments()
        if self.pos < self.length and self.text[self.pos] == ch:
            self.pos += 1
        # silently skip if not found (lenient parser)

    def _skip_to_semicolon_or_brace(self) -> str:
        """Read until ; or {, return the content."""
        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == ';':
                result = self.text[start:self.pos]
                self.pos += 1
                return result
            if ch == '{':
                return self.text[start:self.pos]
            self.pos += 1
        return self.text[start:self.pos]

    def _read_doc(self) -> str:
        """Read a doc comment if present (doc /* ... */)."""
        self._skip_ws_and_comments()
        if not self._match_keyword("doc"):
            return ""
        self._skip_ws_and_comments()
        if self.pos < self.length and self.text[self.pos:self.pos+2] == "/*":
            self.pos += 2
            end = self.text.find("*/", self.pos)
            if end != -1:
                doc = self.text[self.pos:end].strip()
                self.pos = end + 2
                return doc
        return ""

    # ── Package ──────────────────────────────────────────────────────

    def _parse_package(self) -> Package:
        start = self.pos
        self._match_keyword("package")
        name = self._read_name()
        self._skip_ws_and_comments()
        self._expect_char("{")

        pkg = Package(name=name)
        pkg.doc = self._read_doc()

        # Parse package body
        while self.pos < self.length:
            self._skip_ws_and_comments()
            if self.pos >= self.length:
                break
            if self.text[self.pos] == '}':
                self.pos += 1
                break

            saved = self.pos
            if self._peek_keyword("private") or self._peek_keyword("public"):
                vis = "private" if self._match_keyword("private") else ""
                if not vis:
                    self._match_keyword("public")
                    vis = "public"
                self._skip_ws_and_comments()
                if self._peek_keyword("import"):
                    imp = self._parse_import(vis)
                    pkg.imports.append(imp)
                    continue
                # It's some other visibility-qualified thing, reset
                self.pos = saved

            if self._peek_keyword("import"):
                imp = self._parse_import("private")
                pkg.imports.append(imp)
            elif self._peek_keyword("part") and self._check_def_ahead():
                pkg.part_defs.append(self._parse_part_def())
            elif self._peek_keyword("part"):
                pkg.parts.append(self._parse_part())
            elif self._peek_keyword("port") and self._check_def_ahead():
                pkg.port_defs.append(self._parse_port_def())
            elif self._peek_keyword("interface") and self._check_def_ahead():
                pkg.interface_defs.append(self._parse_interface_def())
            elif self._peek_keyword("interface"):
                iface = self._parse_interface_usage()
                if iface:
                    pkg.connections.append(iface)
            elif self._peek_keyword("requirement"):
                pkg.requirement_defs.append(self._parse_requirement())
            elif self._peek_keyword("package"):
                pkg.subpackages.append(self._parse_package())
            elif self._peek_keyword("satisfy"):
                conn = self._parse_satisfy()
                if conn:
                    pkg.connections.append(conn)
            elif self._peek_keyword("#derivation") or self._peek_keyword("connection"):
                conn = self._parse_connection_block()
                if conn:
                    pkg.connections.append(conn)
            else:
                # Try to parse as value assignment (e.g., T1 = 10.0 [N * m];)
                val = self._try_parse_value()
                if val:
                    pkg.values.append(val)
                else:
                    # Skip unknown content
                    self.pos += 1

        pkg.raw = self.text[start:self.pos]
        return pkg

    def _check_def_ahead(self) -> bool:
        """Check if 'def' follows the current keyword without consuming."""
        saved = self.pos
        self._read_name()  # skip current keyword match
        self._skip_ws_and_comments()
        result = self._peek_keyword("def")
        self.pos = saved
        return result

    # ── Imports ──────────────────────────────────────────────────────

    def _parse_import(self, visibility: str) -> Import:
        self._match_keyword("import")
        self._skip_ws_and_comments()
        path_start = self.pos
        while self.pos < self.length and self.text[self.pos] != ';':
            self.pos += 1
        path = self.text[path_start:self.pos].strip()
        self._expect_char(";")
        return Import(path=path, visibility=visibility)

    # ── Part Definitions ─────────────────────────────────────────────

    def _parse_part_def(self) -> PartDef:
        start = self.pos
        self._match_keyword("part")
        self._skip_ws_and_comments()
        self._match_keyword("def")
        name = self._read_name()
        self._skip_ws_and_comments()

        pdef = PartDef(name=name)

        if self.pos < self.length and self.text[self.pos] == ';':
            self.pos += 1
            pdef.raw = self.text[start:self.pos]
            return pdef

        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            pdef.doc = self._read_doc()
            self._parse_part_body(pdef)

        pdef.raw = self.text[start:self.pos]
        return pdef

    def _parse_part_body(self, container):
        """Parse the body of a part def or part usage, populating attributes/ports/children."""
        while self.pos < self.length:
            self._skip_ws_and_comments()
            if self.pos >= self.length:
                break
            if self.text[self.pos] == '}':
                self.pos += 1
                break

            if self._peek_keyword("attribute"):
                attr = self._parse_attribute()
                if attr:
                    container.attributes.append(attr)
            elif self._peek_keyword("port"):
                port = self._parse_port_usage()
                container.ports.append(port)
            elif self._peek_keyword("part"):
                child = self._parse_part()
                container.children.append(child)
            elif self._peek_keyword("interface"):
                iface = self._parse_interface_usage()
                if iface and hasattr(container, 'interfaces'):
                    container.interfaces.append(
                        Interface(name=iface.source, type_ref=iface.kind, raw=iface.raw)
                    )
            elif self._peek_keyword("flow"):
                self._skip_statement()
            elif self._peek_keyword("end"):
                self._skip_statement()
            elif self._peek_keyword("doc"):
                container.doc = self._read_doc()
            else:
                self._skip_statement()

    def _parse_attribute(self) -> Optional[Attribute]:
        start = self.pos
        self._match_keyword("attribute")
        self._skip_ws_and_comments()

        if self._peek_keyword("redefines"):
            self._match_keyword("redefines")

        name = self._read_name()
        rest = self._skip_to_semicolon_or_brace()
        if self.pos < self.length and self.text[self.pos - 1] != ';':
            if self.text[self.pos] == '{':
                self.pos += 1
                self._read_until_closing_brace()

        # Parse type ref and default value from rest
        type_ref = None
        default_value = None
        if ':>' in rest:
            type_ref = rest.split(':>')[1].strip().rstrip(';').strip()
        if '=' in rest:
            parts = rest.split('=', 1)
            default_value = parts[1].strip().rstrip(';').strip()

        return Attribute(
            name=name,
            type_ref=type_ref,
            default_value=default_value,
            raw=self.text[start:self.pos],
        )

    # ── Port Definitions ─────────────────────────────────────────────

    def _parse_port_def(self) -> PortDef:
        start = self.pos
        self._match_keyword("port")
        self._skip_ws_and_comments()
        self._match_keyword("def")
        name = self._read_name()
        self._skip_ws_and_comments()

        pdef = PortDef(name=name)
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            body = self._read_until_closing_brace()
            # Extract flow directions
            for line in body.split(';'):
                line = line.strip()
                if line.startswith('in '):
                    pdef.direction = "in"
                    pdef.flows.append(line)
                elif line.startswith('out '):
                    pdef.direction = "out"
                    pdef.flows.append(line)
        elif self.pos < self.length and self.text[self.pos] == ';':
            self.pos += 1

        pdef.raw = self.text[start:self.pos]
        return pdef

    def _parse_port_usage(self) -> Port:
        start = self.pos
        self._match_keyword("port")
        self._skip_ws_and_comments()
        name = self._read_name()
        rest = self._skip_to_semicolon_or_brace()

        type_ref = None
        if ':' in rest:
            type_ref = rest.split(':', 1)[1].strip().rstrip(';').strip()
            # Handle conjugated ports (~PortName)
            type_ref = type_ref.lstrip('~').strip()

        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            self._read_until_closing_brace()

        return Port(
            name=name,
            type_ref=type_ref,
            raw=self.text[start:self.pos],
        )

    # ── Interface Definitions ────────────────────────────────────────

    def _parse_interface_def(self) -> InterfaceDef:
        start = self.pos
        self._match_keyword("interface")
        self._skip_ws_and_comments()
        self._match_keyword("def")
        name = self._read_name()
        self._skip_ws_and_comments()

        idef = InterfaceDef(name=name)
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            idef.doc = self._read_doc()
            body = self._read_until_closing_brace()
            for line in body.split(';'):
                line = line.strip()
                if line.startswith('end '):
                    idef.ends.append(line)
                elif line.startswith('flow '):
                    idef.flows.append(line)

        idef.raw = self.text[start:self.pos]
        return idef

    def _parse_interface_usage(self) -> Optional[Connection]:
        start = self.pos
        self._match_keyword("interface")
        self._skip_ws_and_comments()
        rest = self._skip_to_semicolon_or_brace()
        body = ""
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            body = self._read_until_closing_brace()

        raw = self.text[start:self.pos]
        # Extract connect targets
        source = ""
        target = ""
        connect_match = re.search(r'connect\s+(.+?)\s+to\s+(.+?)(?:;|\{|$)', rest + " " + body)
        if connect_match:
            source = connect_match.group(1).strip()
            target = connect_match.group(2).strip()

        return Connection(
            kind="interface_connect",
            source=source,
            target=target,
            raw=raw,
        )

    # ── Parts (usage) ────────────────────────────────────────────────

    def _parse_part(self) -> Part:
        start = self.pos
        self._match_keyword("part")
        self._skip_ws_and_comments()

        redefines = None
        if self._peek_keyword("redefines"):
            self._match_keyword("redefines")
            self._skip_ws_and_comments()
            redefines = "redefines"

        name = self._read_name()
        rest = self._skip_to_semicolon_or_brace()

        # Parse type reference, multiplicity, subsets
        type_ref = None
        multiplicity = None
        subsets = None

        # Extract multiplicity [n] or [n..m]
        mult_match = re.search(r'\[([^\]]+)\]', rest)
        if mult_match:
            multiplicity = mult_match.group(1)

        # Extract type reference (after :)
        if ':' in rest:
            type_part = rest.split(':', 1)[1].strip()
            type_part = re.sub(r'\[.*?\]', '', type_part).strip()
            type_ref = type_part.split()[0] if type_part else None

        # Extract subsets
        subsets_match = re.search(r'subsets\s+(\S+)', rest)
        if subsets_match:
            subsets = subsets_match.group(1)

        # Extract redefines from rest
        redef_match = re.search(r'redefines\s+(\S+)', rest)
        if redef_match:
            redefines = redef_match.group(1)

        part = Part(
            name=name,
            type_ref=type_ref,
            multiplicity=multiplicity,
            subsets=subsets,
            redefines=redefines,
        )

        if self.pos <= self.length and self.pos > 0 and self.text[self.pos - 1] != ';':
            if self.pos < self.length and self.text[self.pos] == '{':
                self.pos += 1
                part.doc = self._read_doc()
                self._parse_part_body(part)

        part.raw = self.text[start:self.pos]
        return part

    # ── Requirements ─────────────────────────────────────────────────

    def _parse_requirement(self) -> RequirementDef:
        start = self.pos
        self._match_keyword("requirement")
        self._skip_ws_and_comments()

        if self._peek_keyword("def"):
            return self._parse_requirement_def(start)

        # Requirement usage (with optional ID)
        req_id = None
        if self.pos < self.length and self.text[self.pos] == '<':
            end = self.text.find('>', self.pos)
            if end != -1:
                req_id = self.text[self.pos + 1:end].strip("'")
                self.pos = end + 1

        self._skip_ws_and_comments()
        name = self._read_name()
        self._skip_ws_and_comments()

        req = RequirementDef(name=name, req_id=req_id)

        rest = self._skip_to_semicolon_or_brace()
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            self._parse_requirement_body(req)

        req.raw = self.text[start:self.pos]
        return req

    def _parse_requirement_def(self, start: int) -> RequirementDef:
        self._match_keyword("def")
        name = self._read_name()
        self._skip_ws_and_comments()

        req = RequirementDef(name=name)

        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            req.doc = self._read_doc()
            self._parse_requirement_body(req)

        req.raw = self.text[start:self.pos]
        return req

    def _parse_requirement_body(self, req: RequirementDef):
        while self.pos < self.length:
            self._skip_ws_and_comments()
            if self.pos >= self.length:
                break
            if self.text[self.pos] == '}':
                self.pos += 1
                break

            if self._peek_keyword("doc"):
                req.doc = self._read_doc()
            elif self._peek_keyword("attribute"):
                attr = self._parse_attribute()
                if attr:
                    req.attributes.append(attr)
            elif self._peek_keyword("subject"):
                self._skip_statement()
            elif self._peek_keyword("require") or self._peek_keyword("assert"):
                self._match_keyword("require") or self._match_keyword("assert")
                self._skip_ws_and_comments()
                if self._peek_keyword("constraint"):
                    self._match_keyword("constraint")
                    self._skip_ws_and_comments()
                    if self.pos < self.length and self.text[self.pos] == '{':
                        self.pos += 1
                        expr = self._read_until_closing_brace()
                        req.constraints.append(Constraint(expression=expr.strip()))
            else:
                self._skip_statement()

    # ── Connections (satisfy, derivation) ────────────────────────────

    def _parse_satisfy(self) -> Optional[Connection]:
        start = self.pos
        self._match_keyword("satisfy")
        rest = self._skip_to_semicolon_or_brace()
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            self._read_until_closing_brace()

        source = ""
        target = ""
        by_match = re.search(r'(.+?)\s+by\s+(.+)', rest)
        if by_match:
            source = by_match.group(1).strip()
            target = by_match.group(2).strip().rstrip(';')

        return Connection(
            kind="satisfy",
            source=source,
            target=target,
            raw=self.text[start:self.pos],
        )

    def _parse_connection_block(self) -> Optional[Connection]:
        start = self.pos
        # skip #derivation or connection keyword
        self._read_name()
        self._skip_ws_and_comments()
        if self._peek_keyword("connection"):
            self._match_keyword("connection")
        self._skip_ws_and_comments()
        if self.pos < self.length and self.text[self.pos] == '{':
            self.pos += 1
            body = self._read_until_closing_brace()
            return Connection(
                kind="derivation",
                source=body.strip(),
                raw=self.text[start:self.pos],
            )
        self._skip_statement()
        return Connection(kind="connection", raw=self.text[start:self.pos])

    # ── Values ───────────────────────────────────────────────────────

    def _try_parse_value(self) -> Optional[Attribute]:
        """Try to parse a top-level value like T1 = 10.0 [N * m];"""
        saved = self.pos
        self._skip_ws_and_comments()
        # Check for pattern: name = value;
        name_start = self.pos
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '_'):
            self.pos += 1
        name = self.text[name_start:self.pos].strip()
        if not name:
            self.pos = saved
            return None

        self._skip_ws_and_comments()
        if self.pos < self.length and self.text[self.pos] == '=':
            self.pos += 1
            val_start = self.pos
            while self.pos < self.length and self.text[self.pos] != ';':
                self.pos += 1
            value = self.text[val_start:self.pos].strip()
            self._expect_char(";")
            return Attribute(name=name, default_value=value, raw=f"{name} = {value};")

        self.pos = saved
        return None

    # ── Helpers ──────────────────────────────────────────────────────

    def _skip_statement(self):
        """Skip to the end of a statement (;) or block ({...})."""
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == ';':
                self.pos += 1
                return
            if ch == '{':
                self.pos += 1
                self._read_until_closing_brace()
                return
            self.pos += 1


def parse_sysml_v2(text: str, filename: str = "unknown.sysml") -> ParsedModel:
    """Parse SysML v2 text and return a ParsedModel."""
    parser = SysMLv2Parser(text, filename)
    return parser.parse()
