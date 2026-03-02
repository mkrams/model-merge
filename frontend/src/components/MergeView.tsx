import { useAppStore } from '../store/useAppStore';
import { api } from '../services/api';
import { ElementCard } from './ElementCard';
import type { MergeConflict, Element } from '../types';

function ConflictRow({ conflict }: { conflict: MergeConflict }) {
  const { decisions, setDecision } = useAppStore();
  const current = decisions[conflict.conflict_id] || '';

  const simPct = Math.round(conflict.similarity * 100);

  return (
    <div className="conflict-row">
      <div className="conflict-left">
        <ElementCard
          element={conflict.left_element}
          highlight={current === 'keep_left' ? 'selected' : undefined}
        />
      </div>

      <div className="conflict-center">
        <div className="similarity-badge">
          {simPct}% match
        </div>
        <div className="conflict-type">{conflict.conflict_type}</div>
        <div className="resolution-buttons">
          <button
            className={`res-btn ${current === 'keep_left' ? 'active' : ''}`}
            onClick={() => setDecision(conflict.conflict_id, 'keep_left')}
            title="Keep Model A version"
          >
            &#x2190; A
          </button>
          <button
            className={`res-btn both ${current === 'merge_both' ? 'active' : ''}`}
            onClick={() => setDecision(conflict.conflict_id, 'merge_both')}
            title="Keep both versions"
          >
            A+B
          </button>
          <button
            className={`res-btn ${current === 'keep_right' ? 'active' : ''}`}
            onClick={() => setDecision(conflict.conflict_id, 'keep_right')}
            title="Keep Model B version"
          >
            B &#x2192;
          </button>
        </div>
      </div>

      <div className="conflict-right">
        <ElementCard
          element={conflict.right_element}
          highlight={current === 'keep_right' ? 'selected' : undefined}
        />
      </div>
    </div>
  );
}

function UniqueElements({ elements, side }: { elements: Element[]; side: 'left' | 'right' }) {
  if (elements.length === 0) return null;
  return (
    <div className={`unique-section unique-${side}`}>
      <h4>
        Unique to {side === 'left' ? 'Model A' : 'Model B'} ({elements.length})
        <span className="auto-include"> — auto-included</span>
      </h4>
      <div className="unique-cards">
        {elements.map((el, i) => (
          <ElementCard key={i} element={el} highlight="unique" compact />
        ))}
      </div>
    </div>
  );
}

export function MergeView() {
  const {
    mergeAnalysis,
    decisions,
    setStep,
    setMergedResult,
    setLoading,
    setError,
  } = useAppStore();

  if (!mergeAnalysis) return null;

  const allConflictsResolved =
    mergeAnalysis.conflicts.length === 0 ||
    mergeAnalysis.conflicts.every((c) => decisions[c.conflict_id]);

  const handleApply = async () => {
    setLoading(true);
    setError(null);
    try {
      const decisionList = Object.entries(decisions).map(([conflict_id, resolution]) => ({
        conflict_id,
        resolution,
      }));

      // Auto-resolve identical as keep_left
      for (const identical of mergeAnalysis.identical) {
        if (!decisions[identical.conflict_id]) {
          decisionList.push({
            conflict_id: identical.conflict_id,
            resolution: 'keep_left',
          });
        }
      }

      const result = await api.applyMerge(mergeAnalysis.merge_id, decisionList);
      setMergedResult(result);
      setStep('validate');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Merge failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="merge-view">
      <div className="merge-header">
        <h2>Merge Analysis</h2>
        <div className="merge-stats">
          <span className="stat identical">
            &#x2713; {mergeAnalysis.identical_count} identical
          </span>
          <span className="stat conflict">
            &#x26A0; {mergeAnalysis.conflict_count} conflicts
          </span>
          <span className="stat unique">
            &#x2190; {mergeAnalysis.unique_left_count} unique to A
          </span>
          <span className="stat unique">
            &#x2192; {mergeAnalysis.unique_right_count} unique to B
          </span>
        </div>
      </div>

      <div className="merge-columns-header">
        <div className="col-label">Model A: {mergeAnalysis.model_a_name}</div>
        <div className="col-label center">Resolution</div>
        <div className="col-label">Model B: {mergeAnalysis.model_b_name}</div>
      </div>

      {/* Conflicts */}
      {mergeAnalysis.conflicts.length > 0 && (
        <div className="conflicts-section">
          <h3>Conflicts ({mergeAnalysis.conflicts.length})</h3>
          {mergeAnalysis.conflicts.map((c) => (
            <ConflictRow key={c.conflict_id} conflict={c} />
          ))}
        </div>
      )}

      {/* Identical elements */}
      {mergeAnalysis.identical.length > 0 && (
        <div className="identical-section">
          <h3>Identical Elements ({mergeAnalysis.identical_count})</h3>
          <div className="identical-cards">
            {mergeAnalysis.identical.map((c, i) => (
              <ElementCard key={i} element={c.left_element} highlight="identical" compact />
            ))}
          </div>
        </div>
      )}

      {/* Unique elements */}
      <UniqueElements elements={mergeAnalysis.unique_to_left} side="left" />
      <UniqueElements elements={mergeAnalysis.unique_to_right} side="right" />

      <div className="merge-actions">
        <button className="btn-secondary" onClick={() => setStep('upload')}>
          &#x2190; Back
        </button>
        <button
          className="btn-primary"
          disabled={!allConflictsResolved}
          onClick={handleApply}
        >
          Apply Merge &amp; Validate &#x2192;
        </button>
      </div>
    </div>
  );
}
