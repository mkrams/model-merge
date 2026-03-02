import { useState } from 'react';
import type { SafetyChain, ChainLevel, Perspective } from '../types/safety';

const LEVELS: { key: ChainLevel; label: string }[] = [
  { key: 'hazard', label: 'Hazard' },
  { key: 'hazardous_event', label: 'Haz. Event' },
  { key: 'asil_determination', label: 'ASIL' },
  { key: 'safety_goal', label: 'Safety Goal' },
  { key: 'fsr', label: 'FSR' },
  { key: 'test_case', label: 'Test Case' },
];

const ASIL_COLORS: Record<string, string> = {
  QM: '#94a3b8', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};

// Which levels are "highlighted" per perspective
const PERSPECTIVE_FOCUS: Record<string, ChainLevel[]> = {
  safety_engineer: ['hazard', 'hazardous_event', 'asil_determination', 'safety_goal'],
  test_engineer: ['test_case', 'fsr'],
  req_engineer: ['fsr', 'safety_goal'],
  manager: [],
};

function getItemForLevel(chain: SafetyChain, level: ChainLevel) {
  switch (level) {
    case 'hazard': return chain.hazard;
    case 'hazardous_event': return chain.hazardous_event;
    case 'asil_determination': return chain.asil_determination;
    case 'safety_goal': return chain.safety_goal;
    case 'fsr': return chain.fsr;
    case 'test_case': return chain.test_case;
  }
}

function getStatus(chain: SafetyChain, level: ChainLevel): string {
  if (level === 'asil_determination') {
    const asil = chain.asil_determination;
    if (!asil || !asil.asil_level) return 'gap';
    return asil.approved ? 'approved' : 'draft';
  }
  const item = getItemForLevel(chain, level) as any;
  return item?.status || 'gap';
}

function getName(chain: SafetyChain, level: ChainLevel): string {
  if (level === 'asil_determination') {
    return chain.asil_determination?.asil_level || '';
  }
  const item = getItemForLevel(chain, level) as any;
  return item?.name || '';
}

function getDescription(chain: SafetyChain, level: ChainLevel): string {
  if (level === 'asil_determination') {
    const a = chain.asil_determination;
    if (!a) return '';
    return a.asil_level ? `ASIL ${a.asil_level} (S=${a.severity}, E=${a.exposure}, C=${a.controllability})` : '';
  }
  const item = getItemForLevel(chain, level) as any;
  return item?.description || '';
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'approved') return <span className="asil-status-icon approved">{'\u2713'}</span>;
  if (status === 'draft' || status === 'review') return <span className="asil-status-icon draft">{'\u270E'}</span>;
  return <span className="asil-status-icon gap">{'\u25CB'}</span>;
}

interface ChainCardProps {
  chain: SafetyChain;
  selectedLevel: ChainLevel | null;
  onBlockClick: (level: ChainLevel) => void;
  perspective?: Perspective;
}

export function ChainCard({ chain, selectedLevel, onBlockClick, perspective }: ChainCardProps) {
  const [expanded, setExpanded] = useState(false);
  const focusLevels = perspective ? PERSPECTIVE_FOCUS[perspective] || [] : [];

  return (
    <div className={`asil-chain-container ${expanded ? 'expanded' : ''}`}>
      <div className="asil-chain-row">
        <button
          className="asil-expand-btn"
          onClick={() => setExpanded(!expanded)}
          title={expanded ? 'Collapse' : 'Expand chain details'}
        >
          {expanded ? '\u25BC' : '\u25B6'}
        </button>
        {LEVELS.map((lvl, i) => {
          const status = getStatus(chain, lvl.key);
          const name = getName(chain, lvl.key);
          const desc = getDescription(chain, lvl.key);
          const isASIL = lvl.key === 'asil_determination';
          const asilLevel = chain.asil_determination?.asil_level || '';
          const isSelected = selectedLevel === lvl.key;
          const isFocused = focusLevels.length === 0 || focusLevels.includes(lvl.key);

          return (
            <div key={lvl.key} className="asil-block-wrapper">
              {i > 0 && <span className="asil-arrow">&rarr;</span>}
              <button
                className={`asil-block status-${status} ${isSelected ? 'selected' : ''} ${isFocused ? '' : 'dimmed'}`}
                onClick={() => onBlockClick(lvl.key)}
                title={desc ? `${name}\n${desc}` : (name || lvl.label)}
              >
                {isASIL && asilLevel ? (
                  <span
                    className="asil-level-badge"
                    style={{ background: ASIL_COLORS[asilLevel] || '#64748b' }}
                  >
                    ASIL {asilLevel}
                  </span>
                ) : (
                  <>
                    <StatusIcon status={status} />
                    <span className="asil-block-name">
                      {name ? (name.length > 20 ? name.slice(0, 20) + '...' : name) : lvl.label}
                    </span>
                  </>
                )}
                {desc && !isASIL && (
                  <span className="asil-block-desc">
                    {desc.length > 40 ? desc.slice(0, 40) + '...' : desc}
                  </span>
                )}
                <span className="asil-block-type">{lvl.label}</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Expanded detail view */}
      {expanded && (
        <div className="asil-chain-detail">
          {LEVELS.map(lvl => {
            const item = getItemForLevel(chain, lvl.key) as any;
            const status = getStatus(chain, lvl.key);
            if (lvl.key === 'asil_determination') {
              const a = chain.asil_determination;
              return (
                <div key={lvl.key} className="asil-detail-item" onClick={() => onBlockClick(lvl.key)}>
                  <div className="asil-detail-header">
                    <span className={`asil-detail-status status-${status}`}>{status}</span>
                    <strong>{lvl.label}</strong>
                  </div>
                  {a?.asil_level ? (
                    <div className="asil-detail-body">
                      <div><strong>Level:</strong> ASIL {a.asil_level}</div>
                      {a.severity && <div><strong>Severity:</strong> {a.severity} {a.severity_rationale ? `— ${a.severity_rationale}` : ''}</div>}
                      {a.exposure && <div><strong>Exposure:</strong> {a.exposure} {a.exposure_rationale ? `— ${a.exposure_rationale}` : ''}</div>}
                      {a.controllability && <div><strong>Controllability:</strong> {a.controllability} {a.controllability_rationale ? `— ${a.controllability_rationale}` : ''}</div>}
                    </div>
                  ) : (
                    <div className="asil-detail-body asil-detail-gap">Not determined</div>
                  )}
                </div>
              );
            }
            return (
              <div key={lvl.key} className="asil-detail-item" onClick={() => onBlockClick(lvl.key)}>
                <div className="asil-detail-header">
                  <span className={`asil-detail-status status-${status}`}>{status}</span>
                  <strong>{lvl.label}: {item?.name || '(empty)'}</strong>
                </div>
                <div className="asil-detail-body">
                  {item?.description ? (
                    <div className="asil-detail-desc">{item.description}</div>
                  ) : (
                    <div className="asil-detail-gap">No description</div>
                  )}
                  {item?.operating_situation && <div><strong>Situation:</strong> {item.operating_situation}</div>}
                  {item?.safe_state && <div><strong>Safe State:</strong> {item.safe_state}</div>}
                  {item?.testable_criterion && <div><strong>Testable Criterion:</strong> {item.testable_criterion}</div>}
                  {item?.steps && <div><strong>Steps:</strong> {item.steps}</div>}
                  {item?.expected_result && <div><strong>Expected Result:</strong> {item.expected_result}</div>}
                  {item?.pass_criteria && <div><strong>Pass Criteria:</strong> {item.pass_criteria}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
