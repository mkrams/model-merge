import { useState } from 'react';
import type { SafetyChain, ChainLevel, Perspective } from '../types/safety';

// Chain is now 5 levels — ASIL is a property of Hazardous Event
const LEVELS: { key: ChainLevel; label: string }[] = [
  { key: 'hazard', label: 'Hazard' },
  { key: 'hazardous_event', label: 'Hazardous Event' },
  { key: 'safety_goal', label: 'Safety Goal' },
  { key: 'fsr', label: 'FSR' },
  { key: 'test_case', label: 'Test Case' },
];

const ASIL_COLORS: Record<string, string> = {
  QM: '#64748b', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};

const PERSPECTIVE_FOCUS: Record<string, ChainLevel[]> = {
  safety_engineer: ['hazard', 'hazardous_event', 'safety_goal'],
  test_engineer: ['test_case', 'fsr'],
  req_engineer: ['fsr', 'safety_goal'],
  manager: [],
};

function getItemForLevel(chain: SafetyChain, level: ChainLevel) {
  switch (level) {
    case 'hazard': return chain.hazard;
    case 'hazardous_event': return chain.hazardous_event;
    case 'safety_goal': return chain.safety_goal;
    case 'fsr': return chain.fsr;
    case 'test_case': return chain.test_case;
  }
}

function getStatus(chain: SafetyChain, level: ChainLevel): string {
  const item = getItemForLevel(chain, level) as any;
  return item?.status || 'gap';
}

function getName(chain: SafetyChain, level: ChainLevel): string {
  const item = getItemForLevel(chain, level) as any;
  return item?.name || '';
}

function getDescription(chain: SafetyChain, level: ChainLevel): string {
  const item = getItemForLevel(chain, level) as any;
  return item?.description || '';
}

function StatusDot({ status }: { status: string }) {
  return <span className={`chain-dot status-${status}`} />;
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
  const asilLevel = chain.asil_determination?.asil_level || '';

  return (
    <div className={`chain-container ${expanded ? 'expanded' : ''}`}>
      {/* Compact row */}
      <div className="chain-row">
        <button
          className="chain-expand-toggle"
          onClick={() => setExpanded(!expanded)}
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>
            <path d="M3 1 L7 5 L3 9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        {LEVELS.map((lvl, i) => {
          const status = getStatus(chain, lvl.key);
          const name = getName(chain, lvl.key);
          const desc = getDescription(chain, lvl.key);
          const isSelected = selectedLevel === lvl.key;
          const isFocused = focusLevels.length === 0 || focusLevels.includes(lvl.key);
          const isHE = lvl.key === 'hazardous_event';

          return (
            <div key={lvl.key} className="chain-cell-wrapper">
              {i > 0 && <span className="chain-connector" />}
              <button
                className={`chain-cell status-${status} ${isSelected ? 'selected' : ''} ${isFocused ? '' : 'dimmed'}`}
                onClick={() => onBlockClick(lvl.key)}
                title={desc ? `${name}\n${desc}` : (name || lvl.label)}
              >
                <div className="chain-cell-top">
                  <StatusDot status={status} />
                  <span className="chain-cell-name">
                    {name ? (name.length > 22 ? name.slice(0, 22) + '\u2026' : name) : lvl.label}
                  </span>
                </div>
                {desc && (
                  <span className="chain-cell-desc">
                    {desc.length > 50 ? desc.slice(0, 50) + '\u2026' : desc}
                  </span>
                )}
                <span className="chain-cell-type">{lvl.label}</span>
                {/* ASIL badge on Hazardous Event */}
                {isHE && asilLevel && (
                  <span
                    className="chain-asil-badge"
                    style={{ background: ASIL_COLORS[asilLevel] || '#64748b' }}
                    onClick={(e) => { e.stopPropagation(); onBlockClick('asil_determination'); }}
                    title={`ASIL ${asilLevel} — click to edit`}
                  >
                    {asilLevel}
                  </span>
                )}
                {isHE && !asilLevel && (
                  <span
                    className="chain-asil-badge chain-asil-badge--empty"
                    onClick={(e) => { e.stopPropagation(); onBlockClick('asil_determination'); }}
                    title="ASIL not determined — click to set"
                  >
                    ?
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Expanded vertical detail view */}
      {expanded && (
        <div className="chain-detail-vertical">
          {LEVELS.map((lvl, i) => {
            const item = getItemForLevel(chain, lvl.key) as any;
            const status = getStatus(chain, lvl.key);
            const isHE = lvl.key === 'hazardous_event';

            return (
              <div key={lvl.key} className="chain-detail-card" onClick={() => onBlockClick(lvl.key)}>
                {i > 0 && <div className="chain-detail-line" />}
                <div className="chain-detail-card-inner">
                  <div className="chain-detail-card-head">
                    <StatusDot status={status} />
                    <span className="chain-detail-card-level">{lvl.label}</span>
                    <span className={`chain-detail-card-status status-${status}`}>{status}</span>
                    {isHE && asilLevel && (
                      <span
                        className="chain-asil-badge"
                        style={{ background: ASIL_COLORS[asilLevel] || '#64748b' }}
                        onClick={(e) => { e.stopPropagation(); onBlockClick('asil_determination'); }}
                      >
                        ASIL {asilLevel}
                      </span>
                    )}
                    {isHE && !asilLevel && (
                      <span
                        className="chain-asil-badge chain-asil-badge--empty"
                        onClick={(e) => { e.stopPropagation(); onBlockClick('asil_determination'); }}
                      >
                        ASIL ?
                      </span>
                    )}
                  </div>
                  <div className="chain-detail-card-title">{item?.name || '(empty)'}</div>
                  {item?.description && (
                    <div className="chain-detail-card-body">{item.description}</div>
                  )}
                  {!item?.description && (
                    <div className="chain-detail-card-empty">No content yet</div>
                  )}
                  {/* Extra attributes */}
                  {isHE && (
                    <>
                      {chain.asil_determination?.severity && (
                        <div className="chain-detail-attr">
                          <span className="chain-detail-attr-label">S/E/C</span>
                          <span>{chain.asil_determination.severity} / {chain.asil_determination.exposure} / {chain.asil_determination.controllability}</span>
                        </div>
                      )}
                      {item?.operating_situation && (
                        <div className="chain-detail-attr">
                          <span className="chain-detail-attr-label">Situation</span>
                          <span>{item.operating_situation}</span>
                        </div>
                      )}
                    </>
                  )}
                  {lvl.key === 'safety_goal' && item?.safe_state && (
                    <div className="chain-detail-attr">
                      <span className="chain-detail-attr-label">Safe State</span>
                      <span>{item.safe_state}</span>
                    </div>
                  )}
                  {lvl.key === 'fsr' && item?.testable_criterion && (
                    <div className="chain-detail-attr">
                      <span className="chain-detail-attr-label">Testable Criterion</span>
                      <span>{item.testable_criterion}</span>
                    </div>
                  )}
                  {lvl.key === 'test_case' && (
                    <>
                      {item?.steps && <div className="chain-detail-attr"><span className="chain-detail-attr-label">Steps</span><span>{item.steps}</span></div>}
                      {item?.expected_result && <div className="chain-detail-attr"><span className="chain-detail-attr-label">Expected</span><span>{item.expected_result}</span></div>}
                      {item?.pass_criteria && <div className="chain-detail-attr"><span className="chain-detail-attr-label">Pass Criteria</span><span>{item.pass_criteria}</span></div>}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
