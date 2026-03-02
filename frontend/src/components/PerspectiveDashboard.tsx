import type { SafetyProject, CoverageMetrics } from '../types/safety';

const ASIL_COLORS: Record<string, string> = {
  QM: '#94a3b8', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};

interface Props {
  coverage: CoverageMetrics;
  project: SafetyProject;
}

function ScoreRing({ value, label, color }: { value: number; label: string; color: string }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  return (
    <div className="asil-dash-ring">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#334155" strokeWidth="6" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 48 48)" />
        <text x="48" y="48" textAnchor="middle" dy="0.35em" fill="white" fontSize="20" fontWeight="700">
          {Math.round(value)}%
        </text>
      </svg>
      <span className="asil-dash-ring-label">{label}</span>
    </div>
  );
}

function LevelBar({ label, counts }: { label: string; counts: { filled: number; approved: number; draft: number; gap: number } }) {
  const total = counts.filled + counts.gap;
  if (total === 0) return null;
  const approvedPct = (counts.approved / total) * 100;
  const draftPct = (counts.draft / total) * 100;
  const gapPct = (counts.gap / total) * 100;

  return (
    <div className="asil-dash-level">
      <span className="asil-dash-level-name">{label}</span>
      <div className="asil-dash-level-bar">
        <div className="asil-dash-level-seg approved" style={{ width: `${approvedPct}%` }} />
        <div className="asil-dash-level-seg draft" style={{ width: `${draftPct}%` }} />
        <div className="asil-dash-level-seg gap" style={{ width: `${gapPct}%` }} />
      </div>
      <span className="asil-dash-level-count">{counts.approved}/{total}</span>
    </div>
  );
}

export function PerspectiveDashboard({ coverage, project }: Props) {
  // Use project name in the dashboard title
  const projectName = project?.name || 'Safety Project';
  const covColor = coverage.coverage_pct >= 80 ? '#10b981' : coverage.coverage_pct >= 50 ? '#f59e0b' : '#ef4444';
  const appColor = coverage.approval_pct >= 80 ? '#10b981' : coverage.approval_pct >= 50 ? '#f59e0b' : '#ef4444';

  return (
    <div className="asil-dashboard">
      <h3 style={{ marginBottom: 16, fontSize: 18 }}>{projectName} — Coverage Dashboard</h3>
      {/* Score Rings */}
      <div className="asil-dash-rings">
        <ScoreRing value={coverage.coverage_pct} label="Coverage" color={covColor} />
        <ScoreRing value={coverage.approval_pct} label="Approved" color={appColor} />
      </div>

      {/* Stats */}
      <div className="asil-dash-stats">
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val">{coverage.total_chains}</span>
          <span className="asil-dash-stat-label">Chains</span>
        </div>
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val">{coverage.complete_chains}</span>
          <span className="asil-dash-stat-label">Complete</span>
        </div>
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val asil-dash-stat-gap">{coverage.total_gaps}</span>
          <span className="asil-dash-stat-label">Gaps</span>
        </div>
      </div>

      {/* Level Breakdown */}
      <div className="asil-dash-section">
        <h4>Approval Status by Level</h4>
        {Object.entries(coverage.level_counts).map(([level, counts]) => (
          <LevelBar key={level} label={level.replace('_', ' ')} counts={counts} />
        ))}
      </div>

      {/* ASIL Distribution */}
      <div className="asil-dash-section">
        <h4>ASIL Distribution</h4>
        <div className="asil-dash-dist">
          {Object.entries(coverage.asil_distribution).map(([level, count]) => (
            count > 0 && (
              <div key={level} className="asil-dash-dist-item">
                <span
                  className="asil-dash-dist-badge"
                  style={{ background: ASIL_COLORS[level] || '#64748b' }}
                >
                  {level === 'undetermined' ? '?' : level}
                </span>
                <span className="asil-dash-dist-count">{count}</span>
              </div>
            )
          ))}
        </div>
      </div>
    </div>
  );
}
