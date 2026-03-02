import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { SafetyItem, SafetyProject } from '../types/safety';

const ASIL_COLORS: Record<string, string> = {
  QM: '#94a3b8', A: '#3b82f6', B: '#f59e0b', C: '#f97316', D: '#ef4444',
};

interface ASILWizardProps {
  item: SafetyItem;
  project: SafetyProject;
  onClose: () => void;
  onUpdate: () => void;
}

export function ASILWizard({ item, project, onClose, onUpdate }: ASILWizardProps) {
  const [defs, setDefs] = useState<any>(null);
  const [severity, setSeverity] = useState(item.attributes?.severity || '');
  const [sevRationale, setSevRationale] = useState((item.attributes as any)?.severity_rationale || '');
  const [exposure, setExposure] = useState(item.attributes?.exposure || '');
  const [expRationale, setExpRationale] = useState((item.attributes as any)?.exposure_rationale || '');
  const [controllability, setControllability] = useState(item.attributes?.controllability || '');
  const [ctrlRationale, setCtrlRationale] = useState((item.attributes as any)?.controllability_rationale || '');
  const [computedASIL, setComputedASIL] = useState(item.attributes?.asil_level || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(0); // 0=severity, 1=exposure, 2=controllability, 3=result

  useEffect(() => {
    api.getASILDefinitions().then(setDefs).catch(() => {});
  }, []);

  // Find parent hazard for context
  const parentHazard = project.items.find(i =>
    i.item_type === 'hazard' &&
    project.links.some(l => l.source_id === i.item_id && l.target_id === item.item_id)
  );

  const handleCompute = async () => {
    if (!severity || !exposure || !controllability) return;
    setLoading(true);
    try {
      const result = await api.determineASIL(item.item_id, severity, exposure, controllability);
      setComputedASIL(result.attributes?.asil_level || (result as any).asil_level || '');
      setStep(3);
      onUpdate();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'ASIL determination failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAISuggest = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.determineASIL(item.item_id); // no ratings -> AI suggests
      if ((result as any).suggestion) {
        const s = (result as any).suggestion;
        if (s.severity) {
          setSeverity(s.severity);
          setSevRationale(s.severity_rationale || '');
        }
        if (s.exposure) {
          setExposure(s.exposure);
          setExpRationale(s.exposure_rationale || '');
        }
        if (s.controllability) {
          setControllability(s.controllability);
          setCtrlRationale(s.controllability_rationale || '');
        }
      }
      if ((result as any).error) {
        setError((result as any).error);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'AI suggestion failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    try {
      await api.approveItem(item.item_id);
      onUpdate();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Approval failed');
    }
  };

  const sevDefs = defs?.severity || {};
  const expDefs = defs?.exposure || {};
  const ctrlDefs = defs?.controllability || {};

  return (
    <div className="gap-filler-panel asil-wizard">
      <div className="gap-filler-header">
        <div>
          <h3>ASIL Determination</h3>
          {parentHazard && (
            <span className="asil-wizard-hazard">for: {parentHazard.name}</span>
          )}
        </div>
        <button className="gap-filler-close" onClick={onClose}>&times;</button>
      </div>

      <div className="asil-wizard-body">
        {/* AI Suggest Button */}
        <button className="btn-secondary asil-wizard-suggest" onClick={handleAISuggest} disabled={loading}>
          {loading ? 'AI thinking...' : 'AI Suggest S/E/C'}
        </button>

        {/* Steps */}
        <div className="asil-wizard-steps">
          {['Severity', 'Exposure', 'Controllability', 'Result'].map((label, i) => (
            <button
              key={i}
              className={`asil-wizard-step ${step === i ? 'active' : ''} ${i < step ? 'done' : ''}`}
              onClick={() => setStep(i)}
            >
              {i + 1}. {label}
            </button>
          ))}
        </div>

        {/* Severity */}
        {step === 0 && (
          <div className="asil-wizard-section">
            <h4>Severity (S0–S3)</h4>
            <p className="asil-wizard-hint">How severe are potential injuries?</p>
            <div className="asil-wizard-options">
              {Object.entries(sevDefs).map(([key, desc]) => (
                <label key={key} className={`asil-wizard-option ${severity === key ? 'selected' : ''}`}>
                  <input type="radio" name="severity" value={key} checked={severity === key} onChange={() => setSeverity(key)} />
                  <strong>{key}</strong>
                  <span>{String(desc)}</span>
                </label>
              ))}
            </div>
            <textarea
              className="asil-wizard-rationale"
              value={sevRationale}
              onChange={e => setSevRationale(e.target.value)}
              placeholder="Rationale for severity rating..."
              rows={2}
            />
            <button className="btn-primary" onClick={() => setStep(1)} disabled={!severity}>Next &rarr;</button>
          </div>
        )}

        {/* Exposure */}
        {step === 1 && (
          <div className="asil-wizard-section">
            <h4>Exposure (E0–E4)</h4>
            <p className="asil-wizard-hint">How often is the vehicle in this operational situation?</p>
            <div className="asil-wizard-options">
              {Object.entries(expDefs).map(([key, desc]) => (
                <label key={key} className={`asil-wizard-option ${exposure === key ? 'selected' : ''}`}>
                  <input type="radio" name="exposure" value={key} checked={exposure === key} onChange={() => setExposure(key)} />
                  <strong>{key}</strong>
                  <span>{String(desc)}</span>
                </label>
              ))}
            </div>
            <textarea
              className="asil-wizard-rationale"
              value={expRationale}
              onChange={e => setExpRationale(e.target.value)}
              placeholder="Rationale for exposure rating..."
              rows={2}
            />
            <div className="asil-wizard-nav">
              <button className="btn-secondary" onClick={() => setStep(0)}>&larr; Back</button>
              <button className="btn-primary" onClick={() => setStep(2)} disabled={!exposure}>Next &rarr;</button>
            </div>
          </div>
        )}

        {/* Controllability */}
        {step === 2 && (
          <div className="asil-wizard-section">
            <h4>Controllability (C0–C3)</h4>
            <p className="asil-wizard-hint">Can the driver or other persons control the situation?</p>
            <div className="asil-wizard-options">
              {Object.entries(ctrlDefs).map(([key, desc]) => (
                <label key={key} className={`asil-wizard-option ${controllability === key ? 'selected' : ''}`}>
                  <input type="radio" name="controllability" value={key} checked={controllability === key} onChange={() => setControllability(key)} />
                  <strong>{key}</strong>
                  <span>{String(desc)}</span>
                </label>
              ))}
            </div>
            <textarea
              className="asil-wizard-rationale"
              value={ctrlRationale}
              onChange={e => setCtrlRationale(e.target.value)}
              placeholder="Rationale for controllability rating..."
              rows={2}
            />
            <div className="asil-wizard-nav">
              <button className="btn-secondary" onClick={() => setStep(1)}>&larr; Back</button>
              <button className="btn-primary" onClick={handleCompute} disabled={loading || !controllability}>
                {loading ? 'Computing...' : 'Compute ASIL'}
              </button>
            </div>
          </div>
        )}

        {/* Result */}
        {step === 3 && (
          <div className="asil-wizard-section asil-wizard-result">
            <div className="asil-wizard-result-badge" style={{ background: ASIL_COLORS[computedASIL] || '#64748b' }}>
              ASIL {computedASIL || '?'}
            </div>
            <div className="asil-wizard-result-details">
              <div><strong>Severity:</strong> {severity} — {sevRationale || sevDefs[severity]}</div>
              <div><strong>Exposure:</strong> {exposure} — {expRationale || expDefs[exposure]}</div>
              <div><strong>Controllability:</strong> {controllability} — {ctrlRationale || ctrlDefs[controllability]}</div>
            </div>
            <div className="asil-wizard-nav">
              <button className="btn-secondary" onClick={() => setStep(0)}>Recalculate</button>
              <button className="btn-primary" onClick={handleApprove}>Approve ASIL {computedASIL}</button>
            </div>
          </div>
        )}

        {error && <div className="gap-filler-error">{error}</div>}
      </div>
    </div>
  );
}
