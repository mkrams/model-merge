import type { Element } from '../types';

const typeColors: Record<string, string> = {
  part_def: '#3b82f6',
  part: '#60a5fa',
  port_def: '#8b5cf6',
  port: '#a78bfa',
  interface_def: '#10b981',
  interface: '#34d399',
  requirement_def: '#f59e0b',
  connection: '#6b7280',
  value: '#ec4899',
};

const typeLabels: Record<string, string> = {
  part_def: 'Part Def',
  part: 'Part',
  port_def: 'Port Def',
  port: 'Port',
  interface_def: 'Interface Def',
  interface: 'Interface',
  requirement_def: 'Requirement',
  connection: 'Connection',
  value: 'Value',
};

export function ElementCard({
  element,
  highlight,
  compact,
}: {
  element: Element;
  highlight?: string;
  compact?: boolean;
}) {
  const color = typeColors[element.type] || '#6b7280';
  const label = typeLabels[element.type] || element.type;

  const highlightClass = highlight
    ? `element-card highlight-${highlight}`
    : 'element-card';

  return (
    <div className={highlightClass} style={{ borderLeftColor: color }}>
      <div className="card-header-row">
        <span className="type-badge" style={{ backgroundColor: color }}>
          {label}
        </span>
        <span className="element-name">{element.name || '(unnamed)'}</span>
        {element.req_id && <span className="req-id">{element.req_id}</span>}
      </div>

      {!compact && element.doc && (
        <div className="element-doc">{element.doc}</div>
      )}

      {!compact && element.type_ref && (
        <div className="element-detail">
          <span className="detail-label">Type:</span> {element.type_ref}
        </div>
      )}

      {!compact && element.multiplicity && (
        <div className="element-detail">
          <span className="detail-label">Multiplicity:</span> [{element.multiplicity}]
        </div>
      )}

      {!compact && element.attributes && element.attributes.length > 0 && (
        <div className="element-attrs">
          {element.attributes.slice(0, 3).map((a, i) => (
            <div key={i} className="attr-line">
              <span className="attr-name">{a.name}</span>
              {a.type_ref && <span className="attr-type">: {a.type_ref}</span>}
            </div>
          ))}
          {element.attributes.length > 3 && (
            <div className="attr-more">+{element.attributes.length - 3} more</div>
          )}
        </div>
      )}

      {!compact && element.constraints && element.constraints.length > 0 && (
        <div className="element-constraints">
          {element.constraints.map((c, i) => (
            <div key={i} className="constraint-line">
              &#x2713; {c.expression.slice(0, 60)}
              {c.expression.length > 60 ? '...' : ''}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
