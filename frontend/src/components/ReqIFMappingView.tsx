import { useState, useRef } from 'react';
import { api } from '../services/api';
import type { ReqIFMappingAnalysis, ReqIFMapping, ReqIFAttr } from '../services/api';

/* ── Confidence Badge ── */
function ConfidenceBadge({ value, reason }: { value: number; reason: string }) {
  const pct = Math.round(value * 100);
  const cls = pct === 100 ? 'exact' : pct >= 80 ? 'high' : pct >= 50 ? 'medium' : 'low';
  const label =
    reason === 'exact_name' ? 'Exact' :
    reason === 'same_standard' ? 'Standard' :
    reason === 'fuzzy_name' ? 'Fuzzy' : 'Manual';

  return (
    <span className={`mapping-confidence ${cls}`}>
      {pct}% {label}
    </span>
  );
}

/* ── Type Badge ── */
function TypeBadge({ kind }: { kind: string }) {
  return <span className={`mapping-type-badge ${kind}`}>{kind}</span>;
}

/* ── Attr Card (left or right side) ── */
function AttrCard({ attr, side }: { attr: ReqIFAttr; side: 'a' | 'b' }) {
  return (
    <div className={`mapping-attr-card ${side}`}>
      <div className="mapping-attr-name">{attr.name}</div>
      <div className="mapping-attr-meta">
        <TypeBadge kind={attr.datatype_kind} />
        <span className="mapping-attr-parent">{attr.parent_type}</span>
      </div>
    </div>
  );
}

/* ── Mapping Row ── */
function MappingRow({ mapping }: { mapping: ReqIFMapping }) {
  const [status, setStatus] = useState(mapping.status);

  return (
    <div className={`mapping-row ${status} ${mapping.compatible_types ? '' : 'incompatible'}`}>
      <AttrCard attr={mapping.attr_a} side="a" />

      <div className="mapping-center">
        <ConfidenceBadge value={mapping.confidence} reason={mapping.match_reason} />
        {!mapping.compatible_types && (
          <span className="mapping-warning">Type mismatch</span>
        )}
        <div className="mapping-actions">
          <button
            className={`mapping-btn ${status === 'accepted' ? 'active-accept' : ''}`}
            onClick={() => setStatus(status === 'accepted' ? 'suggested' : 'accepted')}
            title="Accept mapping"
          >
            &#x2713;
          </button>
          <button
            className={`mapping-btn ${status === 'rejected' ? 'active-reject' : ''}`}
            onClick={() => setStatus(status === 'rejected' ? 'suggested' : 'rejected')}
            title="Reject mapping"
          >
            &#x2717;
          </button>
        </div>
      </div>

      {mapping.attr_b ? (
        <AttrCard attr={mapping.attr_b} side="b" />
      ) : (
        <div className="mapping-attr-card empty">No match</div>
      )}
    </div>
  );
}

/* ── Unmapped Attribute ── */
function UnmappedCard({ attr, side }: { attr: ReqIFAttr; side: 'a' | 'b' }) {
  return (
    <div className={`unmapped-card ${side}`}>
      <span className="unmapped-name">{attr.name}</span>
      <div className="unmapped-meta">
        <TypeBadge kind={attr.datatype_kind} />
        <span className="mapping-attr-parent">{attr.parent_type}</span>
      </div>
    </div>
  );
}

/* ── Schema Summary Card ── */
function SchemaSummary({ schema, label }: { schema: ReqIFMappingAnalysis['schema_a']; label: string }) {
  return (
    <div className="schema-summary-card">
      <div className="schema-label">{label}</div>
      <div className="schema-tool">{schema.tool_name}</div>
      <div className="schema-stats-row">
        <span><strong>{schema.object_types.length}</strong> object types</span>
        <span><strong>{schema.datatypes.length}</strong> datatypes</span>
        <span><strong>{schema.spec_object_count}</strong> objects</span>
        <span><strong>{schema.spec_relation_count}</strong> relations</span>
      </div>
      <div className="schema-types-list">
        {schema.object_types.map((ot) => (
          <span key={ot.id} className="schema-type-tag">
            {ot.name} <span className="schema-type-count">({ot.attributes.length} attrs)</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Main Component ── */
export function ReqIFMappingView() {
  const [analysis, setAnalysis] = useState<ReqIFMappingAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const refA = useRef<HTMLInputElement>(null);
  const refB = useRef<HTMLInputElement>(null);

  const handleAnalyze = async () => {
    if (!fileA || !fileB) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyzeReqifAttributes(fileA, fileB);
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
      <div className="reqif-mapping-upload">
        <h2>ReqIF Attribute Mapping</h2>
        <p className="reqif-mapping-desc">
          Compare attribute schemas of two ReqIF files from different tools.
          See which attributes match, which have type mismatches, and which are unique to each file.
        </p>

        <div className="reqif-upload-grid">
          <div className="reqif-upload-slot">
            <label className="reqif-upload-label">File A (e.g. DOORS export)</label>
            <input
              ref={refA}
              type="file"
              accept=".reqif,.xml"
              className="reqif-file-input"
              onChange={(e) => setFileA(e.target.files?.[0] || null)}
            />
            {fileA && <span className="reqif-file-name">{fileA.name}</span>}
          </div>

          <div className="reqif-upload-divider">vs</div>

          <div className="reqif-upload-slot">
            <label className="reqif-upload-label">File B (e.g. Polarion export)</label>
            <input
              ref={refB}
              type="file"
              accept=".reqif,.xml"
              className="reqif-file-input"
              onChange={(e) => setFileB(e.target.files?.[0] || null)}
            />
            {fileB && <span className="reqif-file-name">{fileB.name}</span>}
          </div>
        </div>

        <button
          className="btn-primary analyze-btn"
          onClick={handleAnalyze}
          disabled={!fileA || !fileB || loading}
        >
          {loading ? 'Analyzing...' : 'Analyze Attribute Schemas'}
        </button>

        {error && <div className="reqif-error">{error}</div>}
      </div>
    );
  }

  // Results phase
  const { stats } = analysis;

  return (
    <div className="reqif-mapping-results">
      <div className="reqif-mapping-header">
        <h2>ReqIF Attribute Mapping</h2>
        <button
          className="btn-secondary"
          onClick={() => { setAnalysis(null); setFileA(null); setFileB(null); }}
        >
          &#x2190; New Comparison
        </button>
      </div>

      {/* Schema Summaries */}
      <div className="schema-summaries">
        <SchemaSummary schema={analysis.schema_a} label="File A" />
        <SchemaSummary schema={analysis.schema_b} label="File B" />
      </div>

      {/* Stats Bar */}
      <div className="mapping-stats-bar">
        <span className="mapping-stat mapped">
          <strong>{stats.mapped_count}</strong> mapped
        </span>
        <span className="mapping-stat exact">
          <strong>{stats.exact_matches}</strong> exact
        </span>
        <span className="mapping-stat fuzzy">
          <strong>{stats.fuzzy_matches}</strong> fuzzy
        </span>
        <span className="mapping-stat standard">
          <strong>{stats.standard_matches}</strong> standard
        </span>
        {stats.incompatible_types > 0 && (
          <span className="mapping-stat incompatible">
            <strong>{stats.incompatible_types}</strong> type mismatch
          </span>
        )}
        <span className="mapping-stat unmapped-a">
          <strong>{stats.unmapped_a_count}</strong> only in A
        </span>
        <span className="mapping-stat unmapped-b">
          <strong>{stats.unmapped_b_count}</strong> only in B
        </span>
      </div>

      {/* Mapped Attributes */}
      {analysis.mappings.length > 0 && (
        <div className="mapping-section">
          <h3>Mapped Attributes ({analysis.mappings.length})</h3>
          <div className="mapping-columns-header">
            <span>File A: {analysis.schema_a.tool_name}</span>
            <span className="center">Match</span>
            <span>File B: {analysis.schema_b.tool_name}</span>
          </div>
          <div className="mapping-list">
            {analysis.mappings.map((m, i) => (
              <MappingRow key={i} mapping={m} />
            ))}
          </div>
        </div>
      )}

      {/* Unmapped A */}
      {analysis.unmapped_a.length > 0 && (
        <div className="mapping-section">
          <h3>Only in File A ({analysis.unmapped_a.length})</h3>
          <p className="unmapped-desc">
            These attributes exist only in File A and will be lost if not mapped.
          </p>
          <div className="unmapped-grid">
            {analysis.unmapped_a.map((a, i) => (
              <UnmappedCard key={i} attr={a} side="a" />
            ))}
          </div>
        </div>
      )}

      {/* Unmapped B */}
      {analysis.unmapped_b.length > 0 && (
        <div className="mapping-section">
          <h3>Only in File B ({analysis.unmapped_b.length})</h3>
          <p className="unmapped-desc">
            These attributes exist only in File B and will be added to the merged output.
          </p>
          <div className="unmapped-grid">
            {analysis.unmapped_b.map((b, i) => (
              <UnmappedCard key={i} attr={b} side="b" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
