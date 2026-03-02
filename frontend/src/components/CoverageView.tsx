import { useState, useRef } from 'react';
import { api } from '../services/api';
import type { CoverageAnalysis } from '../services/api';

/* ── Score Ring ── */
function ScoreRing({ value, label, color }: { value: number; label: string; color: string }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  return (
    <div className="cov-score-ring">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="#334155" strokeWidth="6" />
        <circle
          cx="44" cy="44" r={r} fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 44 44)"
        />
        <text x="44" y="44" textAnchor="middle" dy="0.35em"
          fill="white" fontSize="18" fontWeight="700">
          {Math.round(value)}%
        </text>
      </svg>
      <span className="cov-score-label">{label}</span>
    </div>
  );
}

/* ── Stat Card ── */
function StatCard({ value, label, sub }: { value: number | string; label: string; sub?: string }) {
  return (
    <div className="cov-stat-card">
      <div className="cov-stat-value">{value}</div>
      <div className="cov-stat-label">{label}</div>
      {sub && <div className="cov-stat-sub">{sub}</div>}
    </div>
  );
}

/* ── Compliance Check Row ── */
function ComplianceRow({ check }: { check: CoverageAnalysis['compliance_checks'][0] }) {
  const icon = check.passed ? '\u2713' : '\u2717';
  return (
    <div className={`cov-check-row ${check.passed ? 'pass' : 'fail'} sev-${check.severity}`}>
      <span className="cov-check-icon">{icon}</span>
      <div className="cov-check-body">
        <div className="cov-check-title">{check.title}</div>
        <div className="cov-check-detail">{check.detail}</div>
      </div>
      <span className="cov-check-std">{check.standard}</span>
      <span className={`cov-check-sev ${check.severity}`}>{check.severity}</span>
    </div>
  );
}

/* ── Package Coverage Bar ── */
function PackageCoverageBar({ pkg }: { pkg: { name: string; total_reqs: number; orphan_reqs: number; coverage_pct: number } }) {
  const color = pkg.coverage_pct >= 80 ? 'var(--green)' : pkg.coverage_pct >= 50 ? 'var(--yellow)' : 'var(--red)';
  return (
    <div className="cov-pkg-row">
      <span className="cov-pkg-name">{pkg.name}</span>
      <div className="cov-pkg-bar-track">
        <div className="cov-pkg-bar-fill" style={{ width: `${pkg.coverage_pct}%`, background: color }} />
      </div>
      <span className="cov-pkg-pct">{pkg.coverage_pct}%</span>
      <span className="cov-pkg-counts">{pkg.total_reqs - pkg.orphan_reqs}/{pkg.total_reqs}</span>
    </div>
  );
}

/* ── Coverage Status Badge ── */
function CoverageBadge({ status }: { status: string }) {
  return <span className={`cov-badge ${status}`}>{status}</span>;
}

/* ── Main Component ── */
export function CoverageView() {
  const [analysis, setAnalysis] = useState<CoverageAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'requirements' | 'orphans' | 'compliance'>('overview');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyzeCoverage(file);
      setAnalysis(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  // Upload phase
  if (!analysis) {
    return (
      <div className="cov-upload">
        <h2>Requirements Coverage Analysis</h2>
        <p className="cov-upload-desc">
          Upload a SysML v2 or ReqIF file to analyze requirements traceability coverage,
          identify orphan requirements, and check compliance readiness against ISO 26262,
          DO-178C, and other safety standards.
        </p>

        <div className="cov-upload-box">
          <input
            ref={fileRef}
            type="file"
            accept=".sysml,.reqif,.xml"
            className="cov-file-input"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file && <span className="cov-file-name">{file.name}</span>}
        </div>

        <button
          className="btn-primary cov-analyze-btn"
          onClick={handleAnalyze}
          disabled={!file || loading}
        >
          {loading ? 'Analyzing...' : 'Analyze Coverage'}
        </button>

        {error && <div className="cov-error">{error}</div>}

        <div className="cov-features">
          <div className="cov-feature">
            <span className="cov-feature-icon">&#x1F50D;</span>
            <strong>Traceability</strong>
            <span>Forward &amp; backward link coverage</span>
          </div>
          <div className="cov-feature">
            <span className="cov-feature-icon">&#x26A0;</span>
            <strong>Orphan Detection</strong>
            <span>Requirements with no links</span>
          </div>
          <div className="cov-feature">
            <span className="cov-feature-icon">&#x2705;</span>
            <strong>Compliance</strong>
            <span>ISO 26262, DO-178C, ASPICE checks</span>
          </div>
        </div>
      </div>
    );
  }

  // Results phase
  const s = analysis.summary;
  const passedChecks = analysis.compliance_checks.filter(c => c.passed).length;
  const totalChecks = analysis.compliance_checks.length;
  const compliancePct = totalChecks > 0 ? (passedChecks / totalChecks) * 100 : 0;

  return (
    <div className="cov-results">
      <div className="cov-results-header">
        <h2>Coverage Analysis</h2>
        <button
          className="btn-secondary"
          onClick={() => { setAnalysis(null); setFile(null); }}
        >
          &#x2190; New Analysis
        </button>
      </div>

      {/* Score Rings */}
      <div className="cov-scores">
        <ScoreRing
          value={s.forward_coverage}
          label="Forward Coverage"
          color={s.forward_coverage >= 80 ? '#10b981' : s.forward_coverage >= 50 ? '#f59e0b' : '#ef4444'}
        />
        <ScoreRing
          value={compliancePct}
          label="Compliance Score"
          color={compliancePct >= 80 ? '#10b981' : compliancePct >= 50 ? '#f59e0b' : '#ef4444'}
        />
        <ScoreRing
          value={s.total_requirements > 0 ? ((s.total_requirements - s.orphan_count) / s.total_requirements) * 100 : 0}
          label="Linked Reqs"
          color={s.orphan_count === 0 ? '#10b981' : s.orphan_count <= 3 ? '#f59e0b' : '#ef4444'}
        />
      </div>

      {/* Stats Grid */}
      <div className="cov-stats-grid">
        <StatCard value={s.total_requirements} label="Requirements" />
        <StatCard value={s.total_elements} label="Total Elements" />
        <StatCard value={s.total_links} label="Trace Links" />
        <StatCard value={s.total_packages} label="Packages" />
        <StatCard value={s.satisfied_count} label="Satisfied" sub={`of ${s.total_requirements}`} />
        <StatCard value={s.verified_count} label="Verified" sub={`of ${s.total_requirements}`} />
        <StatCard value={s.fully_traced_count} label="Fully Traced" sub="satisfy + verify" />
        <StatCard value={s.orphan_count} label="Orphans" sub="no links" />
      </div>

      {/* Tabs */}
      <div className="cov-tabs">
        <button className={`cov-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
          Overview
        </button>
        <button className={`cov-tab ${activeTab === 'requirements' ? 'active' : ''}`} onClick={() => setActiveTab('requirements')}>
          Requirements ({s.total_requirements})
        </button>
        <button className={`cov-tab ${activeTab === 'orphans' ? 'active' : ''}`} onClick={() => setActiveTab('orphans')}>
          Orphans ({s.orphan_count})
        </button>
        <button className={`cov-tab ${activeTab === 'compliance' ? 'active' : ''}`} onClick={() => setActiveTab('compliance')}>
          Compliance ({passedChecks}/{totalChecks})
        </button>
      </div>

      {/* Tab Content */}
      <div className="cov-tab-content">
        {activeTab === 'overview' && (
          <div className="cov-overview">
            {/* Package Coverage */}
            {analysis.package_coverage.length > 0 && (
              <div className="cov-section">
                <h3>Package Coverage</h3>
                <div className="cov-pkg-list">
                  {analysis.package_coverage.map((pkg, i) => (
                    <PackageCoverageBar key={i} pkg={pkg} />
                  ))}
                </div>
              </div>
            )}

            {/* Quality Indicators */}
            <div className="cov-section">
              <h3>Quality Indicators</h3>
              <div className="cov-quality-grid">
                <div className={`cov-quality-item ${s.no_id_count === 0 ? 'good' : 'warn'}`}>
                  <span className="cov-quality-val">{s.total_requirements - s.no_id_count}/{s.total_requirements}</span>
                  <span className="cov-quality-label">Have IDs</span>
                </div>
                <div className={`cov-quality-item ${s.no_doc_count === 0 ? 'good' : 'warn'}`}>
                  <span className="cov-quality-val">{s.total_requirements - s.no_doc_count}/{s.total_requirements}</span>
                  <span className="cov-quality-label">Documented</span>
                </div>
                <div className={`cov-quality-item ${s.no_constraints_count < s.total_requirements / 2 ? 'good' : 'warn'}`}>
                  <span className="cov-quality-val">{s.total_requirements - s.no_constraints_count}/{s.total_requirements}</span>
                  <span className="cov-quality-label">Have Constraints</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'requirements' && (
          <div className="cov-req-table">
            <div className="cov-req-header-row">
              <span>Name</span>
              <span>Req ID</span>
              <span>Package</span>
              <span>Status</span>
              <span>Satisfy</span>
              <span>Verify</span>
            </div>
            {analysis.requirements.map((req, i) => (
              <div key={i} className={`cov-req-row ${req.is_orphan ? 'orphan' : ''}`}>
                <span className="cov-req-name" title={req.doc}>{req.name}</span>
                <span className="cov-req-id">{req.req_id || '—'}</span>
                <span className="cov-req-pkg">{req.package}</span>
                <CoverageBadge status={req.coverage_status} />
                <span className="cov-req-links">
                  {req.satisfied_by.length > 0 ? req.satisfied_by.join(', ') : '—'}
                </span>
                <span className="cov-req-links">
                  {req.verified_by.length > 0 ? req.verified_by.join(', ') : '—'}
                </span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'orphans' && (
          <div className="cov-orphans">
            {analysis.orphan_requirements.length === 0 ? (
              <div className="cov-empty-state">
                <span className="cov-empty-icon">&#x2705;</span>
                <p>No orphan requirements found. All requirements have traceability links.</p>
              </div>
            ) : (
              <>
                <p className="cov-orphan-desc">
                  These requirements have zero traceability links (no satisfy, verify, derive, or dependency connections).
                  They should be linked to design elements or test cases.
                </p>
                <div className="cov-orphan-grid">
                  {analysis.orphan_requirements.map((req, i) => (
                    <div key={i} className="cov-orphan-card">
                      <div className="cov-orphan-name">{req.name}</div>
                      {req.req_id && <div className="cov-orphan-id">{req.req_id}</div>}
                      <div className="cov-orphan-pkg">{req.package}</div>
                      {req.doc && <div className="cov-orphan-doc">{req.doc}</div>}
                      <div className="cov-orphan-meta">
                        {req.has_constraints && <span className="cov-orphan-tag">Has Constraints</span>}
                        {req.has_attributes && <span className="cov-orphan-tag">Has Attributes</span>}
                        {!req.has_constraints && !req.has_attributes && (
                          <span className="cov-orphan-tag warn">No constraints or attributes</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'compliance' && (
          <div className="cov-compliance">
            <div className="cov-compliance-summary">
              <strong>{passedChecks}</strong> of <strong>{totalChecks}</strong> compliance checks passed
            </div>
            <div className="cov-check-list">
              {analysis.compliance_checks.map((check, i) => (
                <ComplianceRow key={i} check={check} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
