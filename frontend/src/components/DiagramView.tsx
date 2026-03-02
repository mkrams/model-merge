import { useState, useCallback } from 'react';
import type { PackageData, Element } from '../types';

/* ── Color palette per element type ── */
const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  package:         { bg: '#1e293b', border: '#3b82f6', text: '#93c5fd' },
  part_def:        { bg: '#1e3a5f', border: '#3b82f6', text: '#93c5fd' },
  part:            { bg: '#1e3a5f', border: '#60a5fa', text: '#bfdbfe' },
  port_def:        { bg: '#2e1065', border: '#8b5cf6', text: '#c4b5fd' },
  interface_def:   { bg: '#064e3b', border: '#10b981', text: '#6ee7b7' },
  requirement_def: { bg: '#451a03', border: '#f59e0b', text: '#fcd34d' },
  connection:      { bg: '#1c1917', border: '#78716c', text: '#d6d3d1' },
};

const TYPE_LABELS: Record<string, string> = {
  part_def: 'Part Def',
  part: 'Part',
  port_def: 'Port Def',
  interface_def: 'Interface',
  requirement_def: 'Requirement',
  connection: 'Connection',
};

/* ── Helpers ── */
function getElementSummary(el: Element): string[] {
  const lines: string[] = [];
  if (el.type_ref) lines.push(`type: ${el.type_ref}`);
  if (el.req_id) lines.push(`id: ${el.req_id}`);
  if (el.direction) lines.push(`direction: ${el.direction}`);
  if (el.attributes?.length) {
    for (const a of el.attributes.slice(0, 3)) {
      lines.push(`${a.name}${a.type_ref ? ': ' + a.type_ref : ''}${a.default_value ? ' = ' + a.default_value : ''}`);
    }
    if (el.attributes.length > 3) lines.push(`+${el.attributes.length - 3} more`);
  }
  if (el.ports?.length) {
    lines.push(`${el.ports.length} port${el.ports.length > 1 ? 's' : ''}`);
  }
  if (el.constraints?.length) {
    lines.push(`${el.constraints.length} constraint${el.constraints.length > 1 ? 's' : ''}`);
  }
  if (el.doc) {
    const doc = el.doc.length > 60 ? el.doc.slice(0, 57) + '...' : el.doc;
    lines.push(`"${doc}"`);
  }
  return lines;
}

function countPackageElements(pkg: PackageData): number {
  return pkg.part_defs.length + pkg.port_defs.length + pkg.interface_defs.length
    + pkg.requirement_defs.length + pkg.parts.length + pkg.connections.length;
}

/* ── Element Block Component ── */
function ElementBlock({ el, compact }: { el: Element; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const colors = TYPE_COLORS[el.type] || TYPE_COLORS.part;
  const summary = getElementSummary(el);

  return (
    <div
      className="diagram-element"
      style={{ borderColor: colors.border, background: colors.bg }}
      onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
    >
      <div className="diagram-element-header">
        <span className="diagram-type-badge" style={{ background: colors.border }}>
          {TYPE_LABELS[el.type] || el.type}
        </span>
        <span className="diagram-element-name" style={{ color: colors.text }}>
          {el.name}
        </span>
        {el.req_id && <span className="diagram-req-id">{el.req_id}</span>}
      </div>

      {!compact && expanded && summary.length > 0 && (
        <div className="diagram-element-details">
          {summary.map((line, i) => (
            <div key={i} className="diagram-detail-line">{line}</div>
          ))}
        </div>
      )}

      {!compact && el.ports && el.ports.length > 0 && expanded && (
        <div className="diagram-ports-row">
          {el.ports.map((p, i) => (
            <span key={i} className={`diagram-port ${p.direction || 'inout'}`}>
              {p.direction === 'in' ? '→' : p.direction === 'out' ? '←' : '↔'} {p.name}
            </span>
          ))}
        </div>
      )}

      {!compact && !expanded && summary.length > 0 && (
        <div className="diagram-element-preview">
          {summary.slice(0, 2).join(' · ')}
        </div>
      )}
    </div>
  );
}

/* ── Package Block Component ── */
function PackageBlock({ pkg }: { pkg: PackageData }) {
  const [expanded, setExpanded] = useState(true);
  const elementCount = countPackageElements(pkg);

  const sections: { label: string; items: Element[] }[] = [
    { label: 'Part Definitions', items: pkg.part_defs },
    { label: 'Port Definitions', items: pkg.port_defs },
    { label: 'Interfaces', items: pkg.interface_defs },
    { label: 'Requirements', items: pkg.requirement_defs },
    { label: 'Parts', items: pkg.parts },
    { label: 'Connections', items: pkg.connections },
  ].filter(s => s.items.length > 0);

  return (
    <div className="diagram-package">
      <div
        className="diagram-package-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="diagram-package-title">
          <span className="diagram-expand-icon">{expanded ? '▾' : '▸'}</span>
          <span className="diagram-package-badge">pkg</span>
          <span className="diagram-package-name">{pkg.name}</span>
        </div>
        <span className="diagram-package-count">{elementCount} elements</span>
      </div>

      {expanded && (
        <div className="diagram-package-body">
          {pkg.imports.length > 0 && (
            <div className="diagram-imports">
              {pkg.imports.map((imp, i) => (
                <span key={i} className="diagram-import-tag">import {imp.path}</span>
              ))}
            </div>
          )}

          {sections.map((section) => (
            <div key={section.label} className="diagram-section">
              <div className="diagram-section-label">{section.label}</div>
              <div className="diagram-section-grid">
                {section.items.map((el) => (
                  <ElementBlock key={el.id} el={el} />
                ))}
              </div>
            </div>
          ))}

          {pkg.subpackages.length > 0 && (
            <div className="diagram-subpackages">
              <div className="diagram-section-label">Subpackages</div>
              {pkg.subpackages.map((sub) => (
                <PackageBlock key={sub.id} pkg={sub} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Legend Component ── */
function DiagramLegend() {
  return (
    <div className="diagram-legend">
      {Object.entries(TYPE_COLORS).filter(([k]) => k !== 'package').map(([type, colors]) => (
        <span key={type} className="diagram-legend-item">
          <span className="diagram-legend-dot" style={{ background: colors.border }} />
          {TYPE_LABELS[type] || type}
        </span>
      ))}
    </div>
  );
}

/* ── Main DiagramView ── */
export function DiagramView({ packages }: { packages: PackageData[] }) {
  const [viewMode, setViewMode] = useState<'blocks' | 'compact'>('blocks');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredPackages = useCallback(() => {
    if (!searchTerm.trim()) return packages;
    const term = searchTerm.toLowerCase();
    return packages.filter(pkg => {
      if (pkg.name.toLowerCase().includes(term)) return true;
      const allEls = [
        ...pkg.part_defs, ...pkg.port_defs, ...pkg.interface_defs,
        ...pkg.requirement_defs, ...pkg.parts, ...pkg.connections,
      ];
      return allEls.some(el =>
        el.name?.toLowerCase().includes(term) ||
        el.req_id?.toLowerCase().includes(term) ||
        el.type_ref?.toLowerCase().includes(term)
      );
    });
  }, [packages, searchTerm]);

  const totalElements = packages.reduce((sum, p) => sum + countPackageElements(p), 0);

  if (packages.length === 0) {
    return <div className="diagram-empty">No packages to display</div>;
  }

  return (
    <div className="diagram-view">
      {/* Toolbar */}
      <div className="diagram-toolbar">
        <div className="diagram-toolbar-left">
          <div className="diagram-summary">
            <strong>{packages.length}</strong> package{packages.length !== 1 ? 's' : ''} · <strong>{totalElements}</strong> elements
          </div>
          <DiagramLegend />
        </div>
        <div className="diagram-toolbar-right">
          <input
            type="text"
            className="diagram-search"
            placeholder="Search elements..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <div className="diagram-view-toggle">
            <button
              className={`diagram-view-btn ${viewMode === 'blocks' ? 'active' : ''}`}
              onClick={() => setViewMode('blocks')}
            >
              Blocks
            </button>
            <button
              className={`diagram-view-btn ${viewMode === 'compact' ? 'active' : ''}`}
              onClick={() => setViewMode('compact')}
            >
              Compact
            </button>
          </div>
        </div>
      </div>

      {/* Package Grid */}
      <div className={`diagram-packages ${viewMode}`}>
        {filteredPackages().map((pkg) => (
          <PackageBlock key={pkg.id} pkg={pkg} />
        ))}
        {filteredPackages().length === 0 && (
          <div className="diagram-empty">No results for "{searchTerm}"</div>
        )}
      </div>
    </div>
  );
}
