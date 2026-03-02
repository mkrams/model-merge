import type { SafetyChain, ChainLevel } from '../types/safety';

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

function StatusIcon({ status }: { status: string }) {
  if (status === 'approved') return <span className="asil-status-icon approved">{'\u2713'}</span>;
  if (status === 'draft' || status === 'review') return <span className="asil-status-icon draft">{'\u270E'}</span>;
  return <span className="asil-status-icon gap">{'\u25CB'}</span>;
}

interface ChainCardProps {
  chain: SafetyChain;
  selectedLevel: ChainLevel | null;
  onBlockClick: (level: ChainLevel) => void;
}

export function ChainCard({ chain, selectedLevel, onBlockClick }: ChainCardProps) {
  return (
    <div className="asil-chain-row">
      {LEVELS.map((lvl, i) => {
        const status = getStatus(chain, lvl.key);
        const name = getName(chain, lvl.key);
        const isASIL = lvl.key === 'asil_determination';
        const asilLevel = chain.asil_determination?.asil_level || '';
        const isSelected = selectedLevel === lvl.key;

        return (
          <div key={lvl.key} className="asil-block-wrapper">
            {i > 0 && <span className="asil-arrow">&rarr;</span>}
            <button
              className={`asil-block status-${status} ${isSelected ? 'selected' : ''}`}
              onClick={() => onBlockClick(lvl.key)}
              title={name || lvl.label}
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
              <span className="asil-block-type">{lvl.label}</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
