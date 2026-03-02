import type { SafetyProject, CoverageMetrics, ItemType } from '../types/safety';

const ASIL_COLORS: Record<string, string> = {
  QM: '#94a3b8', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};

const TYPE_LABELS: Record<string, string> = {
  hazard: 'Hazards',
  hazardous_event: 'Haz. Events',
  safety_goal: 'Safety Goals',
  fsr: 'FSRs',
  tsr: 'TSRs',
  verification: 'Verification',
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

function LevelBar({ label, counts }: { label: string; counts: { total: number; approved: number; draft: number; gap: number } }) {
  const total = counts.total;
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
  const projectName = project?.name || 'Safety Project';
  const covColor = coverage.coverage_pct >= 80 ? '#10b981' : coverage.coverage_pct >= 50 ? '#f59e0b' : '#ef4444';

  // Compute approval percentage from items_by_type
  const totalItems = coverage.total_items || 0;
  const totalApproved = Object.values(coverage.items_by_type || {}).reduce((sum, c) => sum + (c.approved || 0), 0);
  const approvalPct = totalItems > 0 ? (totalApproved / totalItems) * 100 : 0;
  const appColor = approvalPct >= 80 ? '#10b981' : approvalPct >= 50 ? '#f59e0b' : '#ef4444';

  // Compute ASIL distribution from hazardous_event items
  const asilDist: Record<string, number> = { QM: 0, A: 0, B: 0, C: 0, D: 0, undetermined: 0 };
  for (const item of project.items) {
    if (item.item_type === 'hazardous_event') {
      const asil = item.attributes?.asil_level;
      if (asil && asilDist[asil] !== undefined) {
        asilDist[asil]++;
      } else {
        asilDist.undetermined++;
      }
    }
  }

  return (
    <div className="asil-dashboard">
      <h3 style={{ marginBottom: 16, fontSize: 18 }}>{projectName} — Coverage Dashboard</h3>
      {/* Score Rings */}
      <div className="asil-dash-rings">
        <ScoreRing value={coverage.coverage_pct} label="Coverage" color={covColor} />
        <ScoreRing value={approvalPct} label="Approved" color={appColor} />
      </div>

      {/* Stats */}
      <div className="asil-dash-stats">
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val">{coverage.total_items}</span>
          <span className="asil-dash-stat-label">Items</span>
        </div>
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val">{coverage.total_links}</span>
          <span className="asil-dash-stat-label">Links</span>
        </div>
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val">{coverage.fully_traced_chains}</span>
          <span className="asil-dash-stat-label">Traced</span>
        </div>
        <div className="asil-dash-stat">
          <span className="asil-dash-stat-val asil-dash-stat-gap">{coverage.gaps?.length || 0}</span>
          <span className="asil-dash-stat-label">Gaps</span>
        </div>
      </div>

      {/* Level Breakdown */}
      <div className="asil-dash-section">
        <h4>Approval Status by Type</h4>
        {Object.entries(coverage.items_by_type || {}).map(([type, counts]) => (
          <LevelBar key={type} label={TYPE_LABELS[type] || type} counts={counts} />
        ))}
      </div>

      {/* ASIL Distribution */}
      <div className="asil-dash-section">
        <h4>ASIL Distribution</h4>
        <div className="asil-dash-dist">
          {Object.entries(asilDist).map(([level, count]) => (
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
