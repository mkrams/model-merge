import { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';
import type {
  SafetyProject, SafetyItem, Perspective,
  CoverageMetrics, ItemType,
} from '../types/safety';
import { TraceTreeView } from './TraceTreeView';
import { TraceMatrixView } from './TraceMatrixView';
import { GapFiller } from './GapFiller';
import { ASILWizard } from './ASILWizard';
import { PerspectiveDashboard } from './PerspectiveDashboard';

const PERSPECTIVES: { key: Perspective; label: string; icon: string; hint: string }[] = [
  { key: 'safety_engineer', label: 'Safety Engineer', icon: '\u{1F6E1}', hint: 'Top-down view from hazards. Focus on ASIL severity and safety goals.' },
  { key: 'test_engineer', label: 'Test Engineer', icon: '\u{1F9EA}', hint: 'Bottom-up view from verification items. Focus on test coverage.' },
  { key: 'req_engineer', label: 'Requirements', icon: '\u{1F4CB}', hint: 'Requirements-focused view. FSRs and TSRs sorted by status.' },
  { key: 'manager', label: 'Manager', icon: '\u{1F4CA}', hint: 'Overview sorted by completeness. Items with gaps appear first.' },
];

const TYPE_LABELS: Record<ItemType, string> = {
  hazard: 'Hazards',
  hazardous_event: 'Events',
  safety_goal: 'Goals',
  fsr: 'FSRs',
  tsr: 'TSRs',
  verification: 'Verification',
};

export function ASILAssistantView() {
  const [project, setProject] = useState<SafetyProject | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [viewMode, setViewMode] = useState<'tree' | 'matrix'>('tree');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [showASILWizard, setShowASILWizard] = useState(false);
  const [coverage, setCoverage] = useState<CoverageMetrics | null>(null);
  const [perspective, setPerspective] = useState<Perspective>('safety_engineer');
  const [showDashboard, setShowDashboard] = useState(false);
  // Save/Load
  const [showSave, setShowSave] = useState(false);
  const [saveUser, setSaveUser] = useState('');
  const [savePass, setSavePass] = useState('');
  const [saveMsg, setSaveMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Load coverage when project changes
  useEffect(() => {
    if (project) {
      api.getCoverage().then(setCoverage).catch(() => {});
    }
  }, [project]);

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.importSafetyProject(file);
      setProject(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const refreshProject = async () => {
    try {
      if (project) {
        const result = await api.getProject(project.project_id);
        setProject(result);
        // Also refresh coverage
        api.getCoverage().then(setCoverage).catch(() => {});
      }
    } catch (e) {
      // ignore
    }
  };

  const handleExport = async () => {
    try {
      const xml = await api.exportReqIF();
      const blob = new Blob([xml], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${project?.name || 'safety_graph'}_export.reqif`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError('Export failed: ' + (e?.message || ''));
    }
  };

  const handleSave = async () => {
    if (!saveUser) return;
    try {
      await api.saveData(saveUser, savePass);
      setSaveMsg('Saved successfully!');
    } catch (e: any) {
      setSaveMsg(e?.response?.data?.detail || 'Save failed');
    }
  };

  const handleLoad = async () => {
    if (!saveUser) return;
    try {
      const result = await api.loadData(saveUser, savePass);
      if (result.projects.length > 0) {
        // Load the first project
        setProject(result.projects[0] as SafetyProject);
        setSaveMsg(`Loaded ${result.count} project(s)`);
      } else {
        setSaveMsg('No saved projects found');
      }
    } catch (e: any) {
      setSaveMsg(e?.response?.data?.detail || 'Load failed');
    }
  };

  const handleSelectItem = (itemId: string) => {
    setSelectedItemId(itemId);
    setShowASILWizard(false);
  };

  const handleASILBadgeClick = () => {
    setShowASILWizard(true);
  };

  const handleClosePanel = () => {
    setSelectedItemId(null);
    setShowASILWizard(false);
  };

  const getSelectedItem = (): SafetyItem | null => {
    if (!project || !selectedItemId) return null;
    return project.items.find(item => item.item_id === selectedItemId) || null;
  };

  const selectedItem = getSelectedItem();

  // ── Import Phase ──
  if (!project) {
    return (
      <div className="asil-upload">
        <h2>ASIL Assistant</h2>
        <p className="asil-upload-desc">
          Import an existing requirements file (SysML v2, ReqIF, CSV, Excel, or Word) to analyze the
          ISO 26262 safety graph. The tool identifies hazards, safety goals, FSRs, and
          verification items — then highlights gaps for AI-assisted completion.
        </p>

        <div className="asil-upload-box">
          <input
            ref={fileRef}
            type="file"
            accept=".sysml,.reqif,.xml,.csv,.tsv,.xlsx,.xls,.docx"
            className="asil-file-input"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file && <span className="asil-file-name">{file.name}</span>}
        </div>

        <button className="btn-primary asil-import-btn" onClick={handleImport} disabled={!file || loading}>
          {loading ? 'Importing...' : 'Import & Analyze'}
        </button>

        {error && <div className="asil-error">{error}</div>}

        <div className="asil-features">
          <div className="asil-feature">
            <strong>Graph-Based Traceability</strong>
            <span>Many-to-many relationships between hazards, events, goals, FSRs, and verification</span>
          </div>
          <div className="asil-feature">
            <strong>Multiple Views</strong>
            <span>Tree view for hierarchical navigation, matrix view for systematic tracing</span>
          </div>
          <div className="asil-feature">
            <strong>AI Gap-Filling</strong>
            <span>Click any item to get AI-drafted suggestions</span>
          </div>
          <div className="asil-feature">
            <strong>4 Perspectives</strong>
            <span>Safety, Test, Requirements, Manager views for different stakeholders</span>
          </div>
        </div>

        {/* Save/Load */}
        <div className="asil-save-section">
          <button className="btn-secondary" onClick={() => setShowSave(!showSave)}>
            Load Saved Project
          </button>
          {showSave && (
            <div className="asil-save-form">
              <input placeholder="Username" value={saveUser} onChange={e => setSaveUser(e.target.value)} />
              <input placeholder="Password" type="password" value={savePass} onChange={e => setSavePass(e.target.value)} />
              <button className="btn-secondary" onClick={handleLoad}>Load</button>
              {saveMsg && <span className="asil-save-msg">{saveMsg}</span>}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Graph Editor Phase ──
  return (
    <div className={`asil-editor ${selectedItemId ? 'panel-open' : ''}`}>
      {/* Top Bar */}
      <div className="asil-topbar">
        <div className="asil-topbar-left">
          <button className="btn-secondary asil-back-btn" onClick={() => { setProject(null); setFile(null); setSelectedItemId(null); }}>
            &larr; New Import
          </button>
          <h3 className="asil-project-name">{project.name}</h3>
          {coverage && (
            <div className="asil-coverage-pill">
              <div className="asil-coverage-bar">
                <div className="asil-coverage-fill" style={{ width: `${coverage.coverage_pct}%` }} />
              </div>
              <span>{coverage.coverage_pct}% covered</span>
            </div>
          )}
        </div>
        <div className="asil-topbar-right">
          <div className="asil-perspectives">
            {PERSPECTIVES.map(p => (
              <button
                key={p.key}
                className={`asil-persp-btn ${perspective === p.key ? 'active' : ''}`}
                onClick={() => { setPerspective(p.key); setShowDashboard(false); }}
                title={p.label}
              >
                {p.icon} {p.label}
              </button>
            ))}
          </div>
          <button
            className={`asil-persp-btn ${showDashboard ? 'active' : ''}`}
            onClick={() => setShowDashboard(!showDashboard)}
          >
            Dashboard
          </button>
          <button className="btn-secondary" onClick={handleExport}>Export ReqIF</button>
          <button className="btn-secondary" onClick={() => setShowSave(!showSave)}>Save</button>
        </div>
      </div>

      {/* Save dialog */}
      {showSave && (
        <div className="asil-save-bar">
          <input placeholder="Username" value={saveUser} onChange={e => setSaveUser(e.target.value)} />
          <input placeholder="Password" type="password" value={savePass} onChange={e => setSavePass(e.target.value)} />
          <button className="btn-primary" onClick={handleSave}>Save</button>
          <button className="btn-secondary" onClick={handleLoad}>Load</button>
          {saveMsg && <span className="asil-save-msg">{saveMsg}</span>}
        </div>
      )}

      {/* Perspective hint */}
      <div className="asil-perspective-hint">
        {PERSPECTIVES.find(p => p.key === perspective)?.icon}{' '}
        {PERSPECTIVES.find(p => p.key === perspective)?.hint}
      </div>

      {error && <div className="asil-error">{error}</div>}

      {/* Main content area */}
      <div className="asil-content">
        {/* View toggle and content */}
        <div className="asil-main-area">
          <div className="asil-view-controls">
            <button
              className={`asil-view-btn ${viewMode === 'tree' ? 'active' : ''}`}
              onClick={() => setViewMode('tree')}
            >
              Tree View
            </button>
            <button
              className={`asil-view-btn ${viewMode === 'matrix' ? 'active' : ''}`}
              onClick={() => setViewMode('matrix')}
            >
              Matrix View
            </button>
          </div>

          {showDashboard && coverage ? (
            <PerspectiveDashboard coverage={coverage} project={project} />
          ) : viewMode === 'tree' ? (
            <TraceTreeView
              project={project}
              selectedItemId={selectedItemId}
              onSelectItem={handleSelectItem}
              onProjectChange={refreshProject}
            />
          ) : (
            <TraceMatrixView
              project={project}
              onProjectChange={refreshProject}
            />
          )}
        </div>

        {/* Side Panel - Item Editor or ASIL Wizard */}
        {selectedItem && project && (
          <div className="asil-side-panel">
            <div className="asil-panel-header">
              <h4>{selectedItem.name}</h4>
              <button className="btn-icon" onClick={handleClosePanel}>×</button>
            </div>

            {selectedItem.item_type === 'hazardous_event' && showASILWizard ? (
              <ASILWizard
                item={selectedItem}
                project={project}
                onClose={handleClosePanel}
                onUpdate={refreshProject}
              />
            ) : (
              <GapFiller
                item={selectedItem}
                project={project}
                onClose={handleClosePanel}
                onUpdate={refreshProject}
                onShowASILWizard={selectedItem.item_type === 'hazardous_event' ? handleASILBadgeClick : undefined}
              />
            )}
          </div>
        )}
      </div>

      {/* Bottom bar - item counts */}
      <div className="asil-bottom-bar">
        <div className="asil-item-counts">
          {Object.entries(TYPE_LABELS).map(([type, label]) => {
            const count = project.items.filter(item => item.item_type === type as ItemType).length;
            return (
              <div key={type} className="asil-count-item">
                <span className="asil-count-label">{label}</span>
                <span className="asil-count-value">{count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
