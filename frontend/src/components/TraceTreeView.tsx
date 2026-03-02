import { useState, useMemo } from 'react';
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

interface TreeNode {
  item: SafetyItem;
  children: TreeNode[];
}

const TYPE_ORDER: Record<ItemType, number> = {
  hazard: 0,
  hazardous_event: 1,
  safety_goal: 2,
  fsr: 3,
  tsr: 4,
  verification: 5,
};

export function TraceTreeView({
  project,
  selectedItemId,
  onSelectItem,
  filterType,
  filterStatus,
  searchText,
}: TraceTreeViewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

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

  const itemsSet = new Set(filteredItems.map(i => i.item_id));

  const buildTree = (): TreeNode[] => {
    const itemMap = new Map<string, SafetyItem>();
    filteredItems.forEach(item => {
      itemMap.set(item.item_id, item);
    });

    const incomingLinks = new Map<string, Set<string>>();
    filteredItems.forEach(item => {
      incomingLinks.set(item.item_id, new Set());
    });

    project.links.forEach(link => {
      if (itemsSet.has(link.source_id) && itemsSet.has(link.target_id)) {
        const parents = incomingLinks.get(link.target_id);
        if (parents) parents.add(link.source_id);
      }
    });

    const childrenMap = new Map<string, SafetyItem[]>();
    filteredItems.forEach(item => {
      childrenMap.set(item.item_id, []);
    });

    project.links.forEach(link => {
      if (itemsSet.has(link.source_id) && itemsSet.has(link.target_id)) {
        const children = childrenMap.get(link.source_id);
        if (children) {
          const targetItem = itemMap.get(link.target_id);
          if (targetItem) children.push(targetItem);
        }
      }
    });

    // Find root nodes: items with no parents at their expected level
    const rootItems = filteredItems.filter(item => {
      const parents = incomingLinks.get(item.item_id);
      return !parents || parents.size === 0;
    });

    const buildNode = (item: SafetyItem): TreeNode => {
      const childItems = childrenMap.get(item.item_id) || [];
      // Remove duplicates
      const uniqueChildren = Array.from(new Map(childItems.map(c => [c.item_id, c])).values());
      // Sort by type order and name
      uniqueChildren.sort((a, b) => {
        const typeOrder = TYPE_ORDER[a.item_type] - TYPE_ORDER[b.item_type];
        if (typeOrder !== 0) return typeOrder;
        return a.name.localeCompare(b.name);
      });

      return {
        item,
        children: uniqueChildren.map(buildNode),
      };
    };

    // Sort root nodes by type order and name
    rootItems.sort((a, b) => {
      const typeOrder = TYPE_ORDER[a.item_type] - TYPE_ORDER[b.item_type];
      if (typeOrder !== 0) return typeOrder;
      return a.name.localeCompare(b.name);
    });

    return rootItems.map(buildNode);
  };

  const trees = buildTree();

  const toggleExpanded = (itemId: string) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId);
    } else {
      newExpanded.add(itemId);
    }
    setExpandedIds(newExpanded);
  };

  const getStatusBadgeColor = (status: ItemStatus) => {
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

  const renderNode = (node: TreeNode, level: number = 0) => {
    const isExpanded = expandedIds.has(node.item.item_id);
    const hasChildren = node.children.length > 0;
    const isSelected = selectedItemId === node.item.item_id;

    const statusColor = getStatusBadgeColor(node.item.status);
    const isFilled = node.item.status !== 'gap';

    return (
      <div key={node.item.item_id} className="trace-tree-node">
        <div
          className={`trace-tree-node-content ${isSelected ? 'selected' : ''}`}
          style={{ paddingLeft: `${level * 20}px` }}
        >
          {hasChildren && (
            <button
              className={`trace-tree-expand-btn ${isExpanded ? 'expanded' : ''}`}
              onClick={() => toggleExpanded(node.item.item_id)}
            >
              ▶
            </button>
          )}
          {!hasChildren && <div className="trace-tree-expand-placeholder" />}

          <button
            className="trace-tree-item-btn"
            onClick={() => onSelectItem(node.item.item_id)}
          >
            <svg className="trace-tree-status-badge" width="16" height="16" viewBox="0 0 16 16">
              <circle
                cx="8"
                cy="8"
                r="6"
                fill={isFilled ? statusColor : 'none'}
                stroke={statusColor}
                strokeWidth="1.5"
              />
            </svg>
            <span className="trace-tree-item-name">{node.item.name}</span>
            {node.item.item_type === 'hazardous_event' && node.item.attributes.asil_level && (
              <span className="trace-tree-asil-badge">{node.item.attributes.asil_level}</span>
            )}
            <span className="trace-tree-item-type">{node.item.item_type}</span>
          </button>
        </div>

        {hasChildren && isExpanded && (
          <div className="trace-tree-children">
            {node.children.map(child => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="trace-tree-view">
      <div className="trace-tree-header">
        <h3>Traceability Tree</h3>
        <p className="trace-tree-count">
          {filteredItems.length} item{filteredItems.length !== 1 ? 's' : ''} shown
        </p>
      </div>

      <div className="trace-tree-content">
        {trees.length === 0 ? (
          <div className="trace-tree-empty">
            <p>No items match the current filters</p>
          </div>
        ) : (
          trees.map(tree => renderNode(tree))
        )}
      </div>
    </div>
  );
}
