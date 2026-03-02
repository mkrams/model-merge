import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { ItemType, TraceMatrix } from '../types/safety';
import '../styles/trace-matrix.css';

interface TraceMatrixViewProps {
  project: SafetyProject;
  onProjectChange: () => void;
}

const ITEM_TYPES: ItemType[] = ['hazard', 'hazardous_event', 'safety_goal', 'fsr', 'tsr', 'verification'];

const TYPE_LABELS: Record<ItemType, string> = {
  hazard: 'Hazards',
  hazardous_event: 'Hazardous Events',
  safety_goal: 'Safety Goals',
  fsr: 'FSRs',
  tsr: 'TSRs',
  verification: 'Verification',
};

export function TraceMatrixView({ project, onProjectChange }: TraceMatrixViewProps) {
  const [sourceType, setSourceType] = useState<ItemType>('safety_goal');
  const [targetType, setTargetType] = useState<ItemType>('fsr');
  const [matrix, setMatrix] = useState<TraceMatrix | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingCells, setLoadingCells] = useState<Set<string>>(new Set());
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);
  const [hoveredCol, setHoveredCol] = useState<string | null>(null);

  useEffect(() => {
    loadMatrix();
  }, [sourceType, targetType]);

  const loadMatrix = async () => {
    setLoading(true);
    try {
      const result = await api.getMatrix(sourceType, targetType);
      setMatrix(result);
    } catch (e) {
      console.error('Failed to load matrix:', e);
    } finally {
      setLoading(false);
    }
  };

  const toggleLink = async (sourceId: string, targetId: string, isLinked: boolean) => {
    const cellKey = `${sourceId}:${targetId}`;
    const newLoading = new Set(loadingCells);
    newLoading.add(cellKey);
    setLoadingCells(newLoading);

    try {
      if (isLinked) {
        // Delete the link
        const link = matrix?.cells.find(c => c.source_id === sourceId && c.target_id === targetId);
        if (link && link.link_id) {
          await api.deleteLink(link.link_id);
        }
      } else {
        // Create the link
        await api.createLink(sourceId, targetId);
      }
      await loadMatrix();
      onProjectChange();
    } catch (e) {
      console.error('Failed to toggle link:', e);
    } finally {
      newLoading.delete(cellKey);
      setLoadingCells(newLoading);
    }
  };

  if (!matrix) {
    return <div className="trace-matrix-view">Loading...</div>;
  }

  const linkedCount = matrix.cells.filter(c => c.linked).length;
  const totalCells = matrix.cells.length;
  const linkedPct = totalCells > 0 ? Math.round((linkedCount / totalCells) * 100) : 0;

  const truncate = (text: string, maxLen: number = 20) => {
    if (text.length > maxLen) return text.substring(0, maxLen - 1) + '…';
    return text;
  };

  const getStatusColor = (status: string) => {
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

  return (
    <div className="trace-matrix-view">
      <div className="trace-matrix-header">
        <div className="trace-matrix-controls">
          <div className="trace-matrix-select">
            <label>From:</label>
            <select value={sourceType} onChange={e => setSourceType(e.target.value as ItemType)}>
              {ITEM_TYPES.map(type => (
                <option key={type} value={type}>
                  {TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>
          <div className="trace-matrix-select">
            <label>To:</label>
            <select value={targetType} onChange={e => setTargetType(e.target.value as ItemType)}>
              {ITEM_TYPES.map(type => (
                <option key={type} value={type}>
                  {TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="trace-matrix-stats">
          <strong>{linkedCount} of {totalCells} cells linked ({linkedPct}%)</strong>
        </div>
      </div>

      {loading ? (
        <div className="trace-matrix-loading">Loading matrix...</div>
      ) : (
        <div className="trace-matrix-container">
          <div className="trace-matrix-table">
            {/* Header row (column labels) */}
            <div className="trace-matrix-row trace-matrix-header-row">
              <div className="trace-matrix-row-header" />
              {matrix.targets.map(target => (
                <div
                  key={target.item_id}
                  className={`trace-matrix-cell trace-matrix-header-cell ${
                    hoveredCol === target.item_id ? 'hovered' : ''
                  }`}
                  onMouseEnter={() => setHoveredCol(target.item_id)}
                  onMouseLeave={() => setHoveredCol(null)}
                  title={target.name}
                >
                  <svg className="trace-matrix-status-dot" width="10" height="10" viewBox="0 0 10 10">
                    <circle
                      cx="5"
                      cy="5"
                      r="4"
                      fill={target.status !== 'gap' ? getStatusColor(target.status) : 'none'}
                      stroke={getStatusColor(target.status)}
                      strokeWidth="1"
                    />
                  </svg>
                  <span>{truncate(target.name, 15)}</span>
                </div>
              ))}
            </div>

            {/* Data rows */}
            {matrix.sources.map(source => (
              <div
                key={source.item_id}
                className={`trace-matrix-row ${hoveredRow === source.item_id ? 'hovered' : ''}`}
                onMouseEnter={() => setHoveredRow(source.item_id)}
                onMouseLeave={() => setHoveredRow(null)}
              >
                <div className="trace-matrix-row-header" title={source.name}>
                  <svg className="trace-matrix-status-dot" width="10" height="10" viewBox="0 0 10 10">
                    <circle
                      cx="5"
                      cy="5"
                      r="4"
                      fill={source.status !== 'gap' ? getStatusColor(source.status) : 'none'}
                      stroke={getStatusColor(source.status)}
                      strokeWidth="1"
                    />
                  </svg>
                  <span>{truncate(source.name, 15)}</span>
                </div>

                {matrix.targets.map(target => {
                  const cell = matrix.cells.find(
                    c => c.source_id === source.item_id && c.target_id === target.item_id
                  );
                  const isLinked = cell?.linked ?? false;
                  const cellKey = `${source.item_id}:${target.item_id}`;
                  const isCellLoading = loadingCells.has(cellKey);

                  return (
                    <button
                      key={cellKey}
                      className={`trace-matrix-cell trace-matrix-data-cell ${
                        isLinked ? 'linked' : ''
                      } ${isCellLoading ? 'loading' : ''}`}
                      onClick={() => toggleLink(source.item_id, target.item_id, isLinked)}
                      disabled={isCellLoading}
                      title={isLinked ? 'Click to unlink' : 'Click to create link'}
                    >
                      {isLinked && (
                        <svg className="trace-matrix-link-dot" width="12" height="12" viewBox="0 0 12 12">
                          <circle cx="6" cy="6" r="5" fill="#2563eb" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          {matrix.sources.length === 0 || matrix.targets.length === 0 ? (
            <div className="trace-matrix-empty">
              <p>No items of selected types in project</p>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
