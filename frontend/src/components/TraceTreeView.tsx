import { useState, useMemo, useRef, useLayoutEffect } from 'react';
import type { SafetyProject, SafetyItem, ItemType, ItemStatus } from '../types/safety';
import '../styles/trace-tree.css';

interface TraceTreeViewProps {
  project: SafetyProject;
  selectedItemId: string | null;
  onSelectItem: (itemId: string) => void;
  filterType?: ItemType | null;
  filterStatus?: ItemStatus | null;
  searchText?: string;
}

const COLUMN_ORDER: ItemType[] = ['hazard', 'hazardous_event', 'safety_goal', 'fsr', 'tsr', 'verification'];

const TYPE_LABELS: Record<ItemType, string> = {
  hazard: 'Hazards',
  hazardous_event: 'Events',
  safety_goal: 'Goals',
  fsr: 'FSRs',
  tsr: 'TSRs',
  verification: 'Verification',
};

interface CardPosition {
  itemId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ConnectorLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  linkId: string;
  status: ItemStatus;
  isHighlighted: boolean;
}

export function TraceTreeView({
  project,
  selectedItemId,
  onSelectItem,
  filterType,
  filterStatus,
  searchText,
}: TraceTreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cardRefsMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const [_cardPositions, setCardPositions] = useState<CardPosition[]>([]);
  void _cardPositions; // positions stored for future use
  const [connectorLines, setConnectorLines] = useState<ConnectorLine[]>([]);

  const filteredItems = useMemo(() => {
    return project.items.filter(item => {
      if (filterType && item.item_type !== filterType) return false;
      if (filterStatus && item.status !== filterStatus) return false;
      if (searchText) {
        const text = searchText.toLowerCase();
        if (!item.name.toLowerCase().includes(text) && !item.description.toLowerCase().includes(text)) {
          return false;
        }
      }
      return true;
    });
  }, [project.items, filterType, filterStatus, searchText]);

  const itemsSet = useMemo(() => new Set(filteredItems.map(i => i.item_id)), [filteredItems]);

  // Get only visible links (both source and target in filtered items)
  const visibleLinks = useMemo(() => {
    return project.links.filter(link => itemsSet.has(link.source_id) && itemsSet.has(link.target_id));
  }, [project.links, itemsSet]);

  // Get items by type and only include types that have items
  const itemsByType = useMemo(() => {
    const grouped: Record<ItemType, SafetyItem[]> = {
      hazard: [],
      hazardous_event: [],
      safety_goal: [],
      fsr: [],
      tsr: [],
      verification: [],
    };

    filteredItems.forEach(item => {
      grouped[item.item_type].push(item);
    });

    // Sort items within each type by name
    Object.values(grouped).forEach(items => {
      items.sort((a, b) => a.name.localeCompare(b.name));
    });

    return grouped;
  }, [filteredItems]);

  const columnsToShow = useMemo(() => {
    return COLUMN_ORDER.filter(type => itemsByType[type].length > 0);
  }, [itemsByType]);

  // Calculate connector positions after cards render
  useLayoutEffect(() => {
    try {
      const positions: CardPosition[] = [];
      const lines: ConnectorLine[] = [];

      // Collect all card positions
      cardRefsMap.current.forEach((element, itemId) => {
        const rect = element.getBoundingClientRect();
        const containerRect = containerRef.current?.getBoundingClientRect() || new DOMRect();

        positions.push({
          itemId,
          x: rect.left - containerRect.left,
          y: rect.top - containerRect.top,
          width: rect.width,
          height: rect.height,
        });
      });

      // Create connector lines for each visible link
      visibleLinks.forEach(link => {
        const sourcePos = positions.find(p => p.itemId === link.source_id);
        const targetPos = positions.find(p => p.itemId === link.target_id);

        if (sourcePos && targetPos) {
          // Get source item status for line color
          const sourceItem = filteredItems.find(i => i.item_id === link.source_id);
          const status = sourceItem?.status || 'draft';
          const isHighlighted = selectedItemId === link.source_id || selectedItemId === link.target_id;

          // Calculate center points
          const x1 = sourcePos.x + sourcePos.width;
          const y1 = sourcePos.y + sourcePos.height / 2;
          const x2 = targetPos.x;
          const y2 = targetPos.y + targetPos.height / 2;

          lines.push({
            x1,
            y1,
            x2,
            y2,
            linkId: link.link_id,
            status,
            isHighlighted,
          });
        }
      });

      setCardPositions(positions);
      setConnectorLines(lines);
    } catch (error) {
      console.error('Error calculating connector positions:', error);
    }
  }, [visibleLinks, filteredItems, selectedItemId]);

  // Handle window resize to recalculate positions
  useLayoutEffect(() => {
    const handleResize = () => {
      // Trigger recalculation by accessing card refs
      if (cardRefsMap.current.size > 0) {
        setCardPositions([]);
        // Will be recalculated in the next useLayoutEffect
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getStatusColor = (status: ItemStatus): string => {
    switch (status) {
      case 'approved':
        return '#2563eb';
      case 'draft':
        return '#f59e0b';
      case 'gap':
        return '#ef4444';
      case 'review':
        return '#06b6d4';
      default:
        return '#9ca3af';
    }
  };

  const getConnectorColor = (_status: ItemStatus, isHighlighted: boolean): string => {
    void _status; // available for future status-based coloring
    if (isHighlighted) {
      return 'rgba(59, 130, 246, 0.7)';
    }
    return 'rgba(100, 116, 139, 0.3)';
  };

  const truncate = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 1) + '…';
  };

  const renderCard = (item: SafetyItem) => {
    const isSelected = selectedItemId === item.item_id;
    const isConnected =
      selectedItemId &&
      (visibleLinks.some(
        link =>
          (link.source_id === selectedItemId && link.target_id === item.item_id) ||
          (link.target_id === selectedItemId && link.source_id === item.item_id),
      ) ||
        selectedItemId === item.item_id);

    const statusColor = getStatusColor(item.status);

    return (
      <div
        key={item.item_id}
        ref={el => {
          if (el) {
            cardRefsMap.current.set(item.item_id, el);
          }
        }}
        className={`graph-card ${isSelected ? 'selected' : ''} ${isConnected ? 'connected' : ''}`}
        data-status={item.status}
        data-item-id={item.item_id}
        onClick={() => onSelectItem(item.item_id)}
        style={{ borderColor: isSelected ? statusColor : undefined }}
      >
        <div className="graph-card-status">
          <svg width="8" height="8" viewBox="0 0 8 8">
            <circle cx="4" cy="4" r="3.5" fill={statusColor} />
          </svg>
        </div>
        <div className="graph-card-content">
          <span className="graph-card-name">{truncate(item.name, 24)}</span>
          {item.description && (
            <span className="graph-card-desc">{truncate(item.description, 40)}</span>
          )}
        </div>
        {item.item_type === 'hazardous_event' && item.attributes.asil_level && (
          <span className="graph-card-asil">{item.attributes.asil_level}</span>
        )}
      </div>
    );
  };

  if (filteredItems.length === 0) {
    return (
      <div className="trace-graph-view">
        <div className="trace-graph-header">
          <h3>Traceability Graph</h3>
          <p className="trace-graph-count">0 items shown</p>
        </div>
        <div className="trace-graph-empty">
          <p>No items match the current filters</p>
        </div>
      </div>
    );
  }

  return (
    <div className="trace-graph-view">
      <div className="trace-graph-header">
        <h3>Traceability Graph</h3>
        <p className="trace-graph-count">
          {filteredItems.length} item{filteredItems.length !== 1 ? 's' : ''} shown
        </p>
      </div>

      <div className="trace-graph-container" ref={containerRef}>
        {/* SVG Connector Lines */}
        <svg className="trace-graph-svg" width="100%" height="100%">
          <defs>
            <marker
              id="arrowhead-primary"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="rgba(59, 130, 246, 0.5)" />
            </marker>
            <marker
              id="arrowhead-secondary"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="rgba(100, 116, 139, 0.2)" />
            </marker>
          </defs>

          {connectorLines.map(line => (
            <path
              key={line.linkId}
              d={`M ${line.x1} ${line.y1} C ${line.x1 + 60} ${line.y1}, ${line.x2 - 60} ${line.y2}, ${line.x2} ${line.y2}`}
              stroke={getConnectorColor(line.status, line.isHighlighted)}
              strokeWidth={line.isHighlighted ? 2 : 1.5}
              fill="none"
              pointerEvents="none"
              markerEnd={line.isHighlighted ? 'url(#arrowhead-primary)' : 'url(#arrowhead-secondary)'}
            />
          ))}
        </svg>

        {/* Columns */}
        <div className="trace-graph-columns">
          {columnsToShow.map(type => (
            <div key={type} className="trace-graph-column">
              <div className="trace-graph-column-header">
                <span className="trace-graph-column-title">{TYPE_LABELS[type]}</span>
                <span className="trace-graph-column-badge">{itemsByType[type].length}</span>
              </div>
              <div className="trace-graph-cards">
                {itemsByType[type].map(item => renderCard(item))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
