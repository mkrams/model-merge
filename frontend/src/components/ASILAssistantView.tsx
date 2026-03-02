import { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';
import type {
  SafetyProject, SafetyChain, DraftResponse, ChainLevel, Perspective,
  CoverageMetrics, ASILDefinitions,
} from '../types/safety';
import { ChainCard } from './ChainCard';
import { GapFiller } from './GapFiller';
import { ASILWizard } from './ASILWizard';
import { PerspectiveDashboard } from './PerspectiveDashboard';

const PERSPECTIVES: { key: Perspective; label: string; icon: string }[] = [
  { key: 'safety_engineer', label: 'Safety Engineer', icon: '\u{1F6E1}' },
  { key: 'test_engineer', label: 'Test Engineer', icon: '\u{1F9EA}' },
  { key: 'req_engineer', label: 'Requirements', icon: '\u{1F4CB}' },
  { key: 'manager', label: 'Manager', icon: '\u{1F4CA}' },
];

export function ASILAssistantView() {
  const [project, setProject] = useState<SafetyProject | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [perspective, setPerspective] = useState<Perspective>('safety_engineer');
  const [selectedChain, setSelectedChain] = useState<string | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<ChainLevel | null>(null);
  const [coverage, setCoverage] = useState<CoverageMetrics | null>(null);
  const [showDashboard, setShowDashboard] = useState(false);
  const [perspectiveChains, setPerspectiveChains] = useState<SafetyChain[] | null>(null);
  // Save/Load
  const [showSave, setShowSave] = useState(false);
  const [saveUser, setSaveUser] = useState('');
  const [savePass, setSavePass] = useState('');
  const [saveMsg, setSaveMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Load coverage when project changes
  useEffect(() => {
    if (project) {
      api.getSafetyCoverage().then(setCoverage).catch(() => {});
    }
  }, [project]);

  // Load perspective chains
  useEffect(() => {
    if (project) {
      api.getPerspective(perspective).then(setPerspectiveChains).catch(() => {});
    }
  }, [project, perspective]);

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.importSafetyChain(file);
      setProject(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const refreshProject = async () => {
    try {
      const result = await api.getProject(project?.project_id);
      setProject(result);
    } catch (e) {
      // ignore
    }
  };

  const handleAddChain = async () => {
    try {
      await api.addChain();
      await refreshProject();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to add chain');
    }
  };

  const handleExport = async () => {
    try {
      const xml = await api.exportReqIF();
      const blob = new Blob([xml], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${project?.name || 'safety_chain'}_export.reqif`;
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

  const handleBlockClick = (chainId: string, level: ChainLevel) => {
    setSelectedChain(chainId);
    setSelectedLevel(level);
    setShowDashboard(false);
  };

  const handleClosePanel = () => {
    setSelectedChain(null);
    setSelectedLevel(null);
  };

  const chains = perspectiveChains || project?.chains || [];

  // ── Import Phase ──
  if (!project) {
    return (
      <div className="asil-upload">
        <h2>ASIL Assistant</h2>
        <p className="asil-upload-desc">
          Import an existing requirements file (SysML v2, ReqIF, or CSV) to analyze the
          ISO 26262 safety chain. The tool identifies hazards, safety goals, FSRs, and
          test cases — then highlights gaps for AI-assisted completion.
        </p>

        <div className="asil-upload-box">
          <input
            ref={fileRef}
            type="file"
            accept=".sysml,.reqif,.xml,.csv,.tsv"
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
            <strong>Full Safety Chain</strong>
            <span>Hazard &rarr; Event &rarr; ASIL &rarr; Goal &rarr; FSR &rarr; Test</span>
          </div>
          <div className="asil-feature">
            <strong>AI Gap-Filling</strong>
            <span>Click any gap for AI-drafted suggestions</span>
          </div>
          <div className="asil-feature">
            <strong>4 Perspectives</strong>
            <span>Safety, Test, Requirements, Manager views</span>
          </div>
          <div className="asil-feature">
            <strong>ReqIF Export</strong>
            <span>Download fully traced chain</span>
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

  // ── Chain Editor Phase ──
  return (
    <div className={`asil-editor ${selectedChain ? 'panel-open' : ''}`}>
      {/* Top Bar */}
      <div className="asil-topbar">
        <div className="asil-topbar-left">
          <button className="btn-secondary asil-back-btn" onClick={() => { setProject(null); setFile(null); setPerspectiveChains(null); }}>
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

      {error && <div className="asil-error">{error}</div>}

      {/* Dashboard or Chain List */}
      <div className="asil-content">
        {showDashboard && coverage ? (
          <PerspectiveDashboard coverage={coverage} project={project} />
        ) : (
          <div className="asil-chain-list">
            <div className="asil-chain-header">
              <span className="asil-chain-header-label">Hazard</span>
              <span className="asil-chain-header-arrow">&rarr;</span>
              <span className="asil-chain-header-label">Haz. Event</span>
              <span className="asil-chain-header-arrow">&rarr;</span>
              <span className="asil-chain-header-label">ASIL</span>
              <span className="asil-chain-header-arrow">&rarr;</span>
              <span className="asil-chain-header-label">Safety Goal</span>
              <span className="asil-chain-header-arrow">&rarr;</span>
              <span className="asil-chain-header-label">FSR</span>
              <span className="asil-chain-header-arrow">&rarr;</span>
              <span className="asil-chain-header-label">Test Case</span>
            </div>
            {chains.map((chain) => (
              <ChainCard
                key={chain.chain_id}
                chain={chain}
                selectedLevel={selectedChain === chain.chain_id ? selectedLevel : null}
                onBlockClick={(level) => handleBlockClick(chain.chain_id, level)}
              />
            ))}
            <button className="asil-add-chain-btn" onClick={handleAddChain}>
              + Add Chain
            </button>
          </div>
        )}

        {/* GapFiller Side Panel */}
        {selectedChain && selectedLevel && (
          selectedLevel === 'asil_determination' ? (
            <ASILWizard
              chainId={selectedChain}
              chain={chains.find(c => c.chain_id === selectedChain) || null}
              onClose={handleClosePanel}
              onUpdate={refreshProject}
            />
          ) : (
            <GapFiller
              chainId={selectedChain}
              level={selectedLevel}
              chain={chains.find(c => c.chain_id === selectedChain) || null}
              onClose={handleClosePanel}
              onUpdate={refreshProject}
            />
          )
        )}
      </div>
    </div>
  );
}
