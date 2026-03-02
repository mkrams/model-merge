import { useState, useMemo, useRef, useLayoutEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { SafetyProject, SafetyItem, ItemType, ItemStatus } from '../types/safety';
import '../styles/trace-tree.css';

interface TraceTreeViewProps {
  project: SafetyProject;
  selectedItemId: string | null;
  onSelectItem: (itemId: string) => void;
  onProjectChange?: () => void;
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

const TYPE_SINGULAR: Record<ItemType, string> = {
  hazard: 'Hazard',
  hazardous_event: 'Hazardous Event',
  safety_goal: 'Safety Goal',
  fsr: 'FSR',
  tsr: 'TSR',
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
  isInChain: boolean;
}

/**
 * Traverse the full trace chain from a starting item.
 * Walks up to all ancestors and down to all descendants.
 */
function getFullChain(project: SafetyProject, startItemId: string): Set<string> {
  const chain = new Set<string>();
  if (!startItemId) return chain;

  const visited = new Set<string>();

  // Walk UP (parents): follow links where this item is the target
  const walkUp = (itemId: string) => {
    if (visited.has(itemId)) return;
    visited.add(itemId);
    chain.add(itemId);
    for (const link of project.links) {
      if (link.target_id === itemId) {
        walkUp(link.source_id);
      }
    }
  };

  // Walk DOWN (children): follow links where this item is the source
  const walkDown = (itemId: string) => {
    if (visited.has(itemId)) return;
    visited.add(itemId);
    chain.add(itemId);
    for (const link of project.links) {
      if (link.source_id === itemId) {
        walkDown(link.target_id);
      }
    }
  };

  // First walk up from start, then walk down from start
  // We need separate visited sets so we traverse both directions fully
  const visitedUp = new Set<string>();
  const goUp = (itemId: string) => {
    if (visitedUp.has(itemId)) return;
    visitedUp.add(itemId);
    chain.add(itemId);
    for (const link of project.links) {
      if (link.target_id === itemId) {
        goUp(link.source_id);
      }
    }
  };

  const visitedDown = new Set<string>();
  const goDown = (itemId: string) => {
    if (visitedDown.has(itemId)) return;
    visitedDown.add(itemId);
    chain.add(itemId);
    for (const link of project.links) {
      if (link.source_id === itemId) {
        goDown(link.target_id);
      }
    }
  };

  goUp(startItemId);
  goDown(startItemId);

  return chain;
}

/**
 * Get all link IDs that belong to the full chain.
 */
function getChainLinkIds(project: SafetyProject, chainItemIds: Set<string>): Set<string> {
  const linkIds = new Set<string>();
  for (const link of project.links) {
    if (chainItemIds.has(link.source_id) && chainItemIds.has(link.target_id)) {
      linkIds.add(link.link_id);
    }
  }
  return linkIds;
}

export function TraceTreeView({
  project,
  selectedItemId,
  onSelectItem,
  onProjectChange,
  filterType,
  filterStatus,
  searchText,
}: TraceTreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cardRefsMap = useRef<Map<string, HTMLDivElement>>(new Map());
  const [connectorLines, setConnectorLines] = useState<ConnectorLine[]>([]);
  const [addingType, setAddingType] = useState<ItemType | null>(null);
  const [newItemName, setNewItemName] = useState('');
  const [linkingFrom, setLinkingFrom] = useState<string | null>(null);
  const [addingLoading, setAddingLoading] = useState(false);

  // Compute the full chain for the selected item
  const chainItemIds = useMemo(() => {
    if (!selectedItemId) return new Set<string>();
    return getFullChain(project, selectedItemId);
  }, [project, selectedItemId]);

  const chainLinkIds = useMemo(() => {
    if (!selectedItemId) return new Set<string>();
    return getChainLinkIds(project, chainItemIds);
  }, [project, selectedItemId, chainItemIds]);

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

  const visibleLinks = useMemo(() => {
    return project.links.filter(link => itemsSet.has(link.source_id) && itemsSet.has(link.target_id));
  }, [project.links, itemsSet]);

  const itemsByType = useMemo(() => {
    const grouped: Record<ItemType, SafetyItem[]> = {
      hazard: [], hazardous_event: [], safety_goal: [],
      fsr: [], tsr: [], verification: [],
    };
    filteredItems.forEach(item => { grouped[item.item_type].push(item); });
    Object.values(grouped).forEach(items => { items.sort((a, b) => a.name.localeCompare(b.name)); });
    return grouped;
  }, [filteredItems]);

  // Always show all 6 columns so users can add items to empty ones
  const columnsToShow = COLUMN_ORDER;

  // Calculate connector positions after cards render
  useLayoutEffect(() => {
    try {
      const positions: CardPosition[] = [];
      const lines: ConnectorLine[] = [];

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

      visibleLinks.forEach(link => {
        const sourcePos = positions.find(p => p.itemId === link.source_id);
        const targetPos = positions.find(p => p.itemId === link.target_id);
        if (sourcePos && targetPos) {
          const sourceItem = filteredItems.find(i => i.item_id === link.source_id);
          const status = sourceItem?.status || 'draft';
          const isInChain = chainLinkIds.has(link.link_id);

          const x1 = sourcePos.x + sourcePos.width;
          const y1 = sourcePos.y + sourcePos.height / 2;
          const x2 = targetPos.x;
          const y2 = targetPos.y + targetPos.height / 2;

          lines.push({ x1, y1, x2, y2, linkId: link.link_id, status, isInChain });
        }
      });

      setConnectorLines(lines);
    } catch (error) {
      console.error('Error calculating connector positions:', error);
    }
  }, [visibleLinks, filteredItems, selectedItemId, chainLinkIds]);

  useLayoutEffect(() => {
    const handleResize = () => {
      if (cardRefsMap.current.size > 0) {
        setConnectorLines([]);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getStatusColor = (status: ItemStatus): string => {
    switch (status) {
      case 'approved': return '#2563eb';
      case 'draft': return '#f59e0b';
      case 'gap': return '#ef4444';
      case 'review': return '#06b6d4';
      default: return '#9ca3af';
    }
  };

  const getConnectorColor = (isInChain: boolean): string => {
    if (isInChain) return 'rgba(59, 130, 246, 0.8)';
    if (selectedItemId) return 'rgba(100, 116, 139, 0.12)';
    return 'rgba(100, 116, 139, 0.3)';
  };

  const truncate = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 1) + '\u2026';
  };

  // Add item handler
  const handleAddItem = useCallback(async (type: ItemType) => {
    if (!newItemName.trim()) return;
    setAddingLoading(true);
    try {
      await api.createItem({
        item_type: type,
        name: newItemName.trim(),
        description: '',
      });
      setNewItemName('');
      setAddingType(null);
      onProjectChange?.();
    } catch (e) {
      console.error('Failed to create item:', e);
    } finally {
      setAddingLoading(false);
    }
  }, [newItemName, onProjectChange]);

  // Link handler: click a card while in linking mode
  const handleLinkTo = useCallback(async (targetId: string) => {
    if (!linkingFrom || linkingFrom === targetId) return;
    try {
      await api.createLink(linkingFrom, targetId);
      setLinkingFrom(null);
      onProjectChange?.();
    } catch (e: any) {
      // Try reverse direction if first fails
      try {
        await api.createLink(targetId, linkingFrom);
        setLinkingFrom(null);
        onProjectChange?.();
      } catch {
        console.error('Failed to create link:', e);
        setLinkingFrom(null);
      }
    }
  }, [linkingFrom, onProjectChange]);

  const handleCardClick = (item: SafetyItem) => {
    if (linkingFrom) {
      handleLinkTo(item.item_id);
    } else {
      onSelectItem(item.item_id);
    }
  };

  const renderCard = (item: SafetyItem) => {
    const isSelected = selectedItemId === item.item_id;
    const isInChain = chainItemIds.has(item.item_id);
    const isDimmed = selectedItemId !== null && !isInChain;
    const isLinkSource = linkingFrom === item.item_id;
    const statusColor = getStatusColor(item.status);

    return (
      <div
        key={item.item_id}
        ref={el => { if (el) cardRefsMap.current.set(item.item_id, el); }}
        className={`graph-card ${isSelected ? 'selected' : ''} ${isInChain && !isSelected ? 'in-chain' : ''} ${isDimmed ? 'dimmed' : ''} ${isLinkSource ? 'link-source' : ''}`}
        data-status={item.status}
        onClick={() => handleCardClick(item)}
        style={{ borderColor: isSelected ? statusColor : undefined }}
      >
        <div className="graph-card-status">
          <svg width="8" height="8" viewBox="0 0 8 8">
            <circle cx="4" cy="4" r="3.5" fill={statusColor} />
          </svg>
        </div>
        <div className="graph-card-content">
          <span className="graph-card-name">{truncate(item.name, 28)}</span>
          {item.description && (
            <span className="graph-card-desc">{truncate(item.description, 50)}</span>
          )}
        </div>
        <div className="graph-card-actions">
          {item.item_type === 'hazardous_event' && item.attributes.asil_level && (
            <span className="graph-card-asil">{item.attributes.asil_level}</span>
          )}
          <button
            className="graph-card-link-btn"
            title="Link to another item"
            onClick={(e) => {
              e.stopPropagation();
              setLinkingFrom(linkingFrom === item.item_id ? null : item.item_id);
            }}
          >
            {linkingFrom === item.item_id ? '\u2715' : '\u{1F517}'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="trace-graph-view">
      <div className="trace-graph-header">
        <h3>Traceability Graph</h3>
        <div className="trace-graph-header-right">
          {linkingFrom && (
            <span className="trace-graph-linking-hint">
              Click a target item to create link&hellip;
              <button className="trace-graph-cancel-link" onClick={() => setLinkingFrom(null)}>Cancel</button>
            </span>
          )}
          <p className="trace-graph-count">
            {filteredItems.length} item{filteredItems.length !== 1 ? 's' : ''} &middot; {visibleLinks.length} link{visibleLinks.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <div className="trace-graph-container" ref={containerRef}>
        {/* SVG Connector Lines */}
        <svg className="trace-graph-svg" width="100%" height="100%">
          <defs>
            <marker id="arrow-chain" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <polygon points="0 0, 10 3, 0 6" fill="rgba(59, 130, 246, 0.7)" />
            </marker>
            <marker id="arrow-dim" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <polygon points="0 0, 10 3, 0 6" fill="rgba(100, 116, 139, 0.2)" />
            </marker>
            <marker id="arrow-normal" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <polygon points="0 0, 10 3, 0 6" fill="rgba(100, 116, 139, 0.3)" />
            </marker>
          </defs>

          {/* Render non-chain lines first, chain lines on top */}
          {connectorLines
            .sort((a, b) => (a.isInChain ? 1 : 0) - (b.isInChain ? 1 : 0))
            .map(line => (
              <path
                key={line.linkId}
                d={`M ${line.x1} ${line.y1} C ${line.x1 + 60} ${line.y1}, ${line.x2 - 60} ${line.y2}, ${line.x2} ${line.y2}`}
                stroke={getConnectorColor(line.isInChain)}
                strokeWidth={line.isInChain ? 2.5 : 1.2}
                fill="none"
                pointerEvents="none"
                markerEnd={line.isInChain ? 'url(#arrow-chain)' : selectedItemId ? 'url(#arrow-dim)' : 'url(#arrow-normal)'}
                style={{ transition: 'stroke 0.2s, stroke-width 0.2s, opacity 0.2s' }}
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

                {/* Add Item UI */}
                {addingType === type ? (
                  <div className="graph-add-form">
                    <input
                      className="graph-add-input"
                      placeholder={`New ${TYPE_SINGULAR[type]}...`}
                      value={newItemName}
                      onChange={e => setNewItemName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleAddItem(type);
                        if (e.key === 'Escape') { setAddingType(null); setNewItemName(''); }
                      }}
                      autoFocus
                      disabled={addingLoading}
                    />
                    <div className="graph-add-actions">
                      <button
                        className="graph-add-confirm"
                        onClick={() => handleAddItem(type)}
                        disabled={!newItemName.trim() || addingLoading}
                      >
                        {addingLoading ? '...' : 'Add'}
                      </button>
                      <button
                        className="graph-add-cancel"
                        onClick={() => { setAddingType(null); setNewItemName(''); }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    className="graph-add-btn"
                    onClick={() => { setAddingType(type); setNewItemName(''); }}
                  >
                    + Add {TYPE_SINGULAR[type]}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
