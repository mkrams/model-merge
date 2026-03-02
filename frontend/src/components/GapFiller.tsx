import { useState } from 'react';
import { api } from '../services/api';
import type { SafetyChain, ChainLevel, DraftResponse } from '../types/safety';

const LEVEL_LABELS: Record<string, string> = {
  hazard: 'Hazard',
  hazardous_event: 'Hazardous Event',
  safety_goal: 'Safety Goal',
  fsr: 'Functional Safety Requirement',
  test_case: 'Test Case',
};

// Fields per level
const LEVEL_FIELDS: Record<string, { key: string; label: string; type: 'input' | 'textarea' }[]> = {
  hazard: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description', type: 'textarea' },
  ],
  hazardous_event: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'operating_situation', label: 'Operating Situation', type: 'textarea' },
  ],
  safety_goal: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description (shall statement)', type: 'textarea' },
    { key: 'safe_state', label: 'Safe State', type: 'textarea' },
  ],
  fsr: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description (shall statement)', type: 'textarea' },
    { key: 'testable_criterion', label: 'Testable Criterion', type: 'textarea' },
  ],
  test_case: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Objective', type: 'textarea' },
    { key: 'steps', label: 'Test Steps', type: 'textarea' },
    { key: 'expected_result', label: 'Expected Result', type: 'textarea' },
    { key: 'pass_criteria', label: 'Pass Criteria', type: 'textarea' },
  ],
};

function getItem(chain: SafetyChain, level: ChainLevel): any {
  switch (level) {
    case 'hazard': return chain.hazard;
    case 'hazardous_event': return chain.hazardous_event;
    case 'safety_goal': return chain.safety_goal;
    case 'fsr': return chain.fsr;
    case 'test_case': return chain.test_case;
    default: return null;
  }
}

interface GapFillerProps {
  chainId: string;
  level: ChainLevel;
  chain: SafetyChain | null;
  onClose: () => void;
  onUpdate: () => void;
}

export function GapFiller({ chainId, level, chain, onClose, onUpdate }: GapFillerProps) {
  const item = chain ? getItem(chain, level) : null;
  const isGap = !item || item.status === 'gap';
  const fields = LEVEL_FIELDS[level] || LEVEL_FIELDS.hazard;

  // Initialize field values from existing item
  const initFieldValues = (): Record<string, string> => {
    const vals: Record<string, string> = {};
    for (const f of fields) {
      vals[f.key] = item?.[f.key] || '';
    }
    return vals;
  };

  const [fieldValues, setFieldValues] = useState<Record<string, string>>(initFieldValues);
  // AI overwrite toggles: which fields should AI overwrite (default: all empty fields)
  const [aiOverwrite, setAiOverwrite] = useState<Record<string, boolean>>(() => {
    const ow: Record<string, boolean> = {};
    for (const f of fields) {
      ow[f.key] = !(item?.[f.key]); // toggle ON for empty fields, OFF for filled
    }
    return ow;
  });

  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showVersions, setShowVersions] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ role: string; text: string }[]>([]);
  const [lastRationale, setLastRationale] = useState('');

  const setField = (key: string, value: string) => {
    setFieldValues(prev => ({ ...prev, [key]: value }));
  };

  const toggleAiOverwrite = (key: string) => {
    setAiOverwrite(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const applyAiResult = (result: DraftResponse) => {
    // Map AI result keys to field keys
    const mapping: Record<string, string> = {
      name: result.name || '',
      description: result.text || '',
      operating_situation: (result as any).operating_situation || '',
      safe_state: (result as any).safe_state || '',
      testable_criterion: (result as any).testable_criterion || '',
      steps: result.steps || '',
      expected_result: result.expected_result || '',
      pass_criteria: result.pass_criteria || '',
    };

    setFieldValues(prev => {
      const next = { ...prev };
      for (const f of fields) {
        if (aiOverwrite[f.key] && mapping[f.key]) {
          next[f.key] = mapping[f.key];
        }
      }
      return next;
    });

    if (result.rationale) {
      setLastRationale(result.rationale);
    }
    setChatMessages(prev => [...prev, { role: 'assistant', text: result.text || result.name || 'AI suggestion applied' }]);
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.draftItem(chainId, level);
      applyAiResult(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'AI generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRevise = async () => {
    if (!feedback.trim()) return;
    setLoading(true);
    setError('');
    setChatMessages(prev => [...prev, { role: 'user', text: feedback }]);
    try {
      const result = await api.reviseItem(chainId, level, feedback);
      applyAiResult(result);
      setFeedback('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Revision failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    setLoading(true);
    setError('');
    try {
      const extra: Record<string, string> = {};
      for (const f of fields) {
        if (f.key !== 'name' && f.key !== 'description') {
          extra[f.key] = fieldValues[f.key] || '';
        }
      }
      await api.approveItem(chainId, level, fieldValues.name || '', fieldValues.description || '', extra);
      onUpdate();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Approval failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    setLoading(true);
    try {
      const saveFields: Record<string, string> = {};
      for (const f of fields) {
        if (f.key === 'description') {
          saveFields.description = fieldValues.description || '';
        } else {
          saveFields[f.key] = fieldValues[f.key] || '';
        }
      }
      await api.editItem(chainId, level, saveFields);
      onUpdate();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRevert = async (idx: number) => {
    try {
      await api.revertItem(chainId, level, idx);
      onUpdate();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Revert failed');
    }
  };

  const versions = item?.versions || [];

  // Context bar
  const contextItems: { label: string; value: string; status: string }[] = [];
  if (chain) {
    if (chain.hazard && chain.hazard.status !== 'gap') contextItems.push({ label: 'Hazard', value: chain.hazard.name, status: chain.hazard.status });
    if (chain.asil_determination?.asil_level) contextItems.push({ label: 'ASIL', value: chain.asil_determination.asil_level, status: chain.asil_determination.approved ? 'approved' : 'draft' });
    if (chain.safety_goal && chain.safety_goal.status !== 'gap') contextItems.push({ label: 'Safety Goal', value: chain.safety_goal.name, status: chain.safety_goal.status });
    if (chain.fsr && chain.fsr.status !== 'gap') contextItems.push({ label: 'FSR', value: chain.fsr.name, status: chain.fsr.status });
    if (chain.test_case && chain.test_case.status !== 'gap') contextItems.push({ label: 'Test', value: chain.test_case.name, status: chain.test_case.status });
  }

  return (
    <div className="gap-filler-panel">
      <div className="gap-filler-header">
        <div>
          <h3>{LEVEL_LABELS[level] || level}</h3>
          <span className={`gap-filler-status status-${item?.status || 'gap'}`}>
            {item?.status || 'gap'}
          </span>
        </div>
        <button className="gap-filler-close" onClick={onClose}>&times;</button>
      </div>

      {/* Context */}
      {contextItems.length > 0 && (
        <div className="gap-filler-context">
          <span className="gap-filler-context-label">Chain context:</span>
          {contextItems.map((ci, i) => (
            <span key={i} className={`gap-filler-context-item status-${ci.status}`}>
              {ci.label}: {ci.value}
            </span>
          ))}
        </div>
      )}

      {/* AI Generate Bar */}
      <div className="gap-filler-ai-bar">
        <button className="btn-ai" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating...' : 'Generate with AI'}
        </button>
        <div className="gap-filler-ai-toggles">
          <span className="gap-filler-ai-toggles-label">Overwrite:</span>
          {fields.map(f => (
            <label key={f.key} className="gap-filler-ai-toggle">
              <input
                type="checkbox"
                checked={aiOverwrite[f.key]}
                onChange={() => toggleAiOverwrite(f.key)}
              />
              <span>{f.label.split(' ')[0]}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Content Area — always show fields */}
      <div className="gap-filler-body">
        <div className="gap-filler-form">
          {fields.map(f => (
            <div key={f.key} className="gap-filler-field">
              <label>{f.label}</label>
              {f.type === 'input' ? (
                <input
                  value={fieldValues[f.key] || ''}
                  onChange={e => setField(f.key, e.target.value)}
                  placeholder={`Enter ${f.label.toLowerCase()}...`}
                />
              ) : (
                <textarea
                  value={fieldValues[f.key] || ''}
                  onChange={e => setField(f.key, e.target.value)}
                  placeholder={`Enter ${f.label.toLowerCase()}...`}
                  rows={f.key === 'description' ? 5 : 3}
                />
              )}
            </div>
          ))}
        </div>

        {/* AI Rationale */}
        {lastRationale && (
          <div className="gap-filler-rationale">
            <strong>AI Rationale:</strong> {lastRationale}
          </div>
        )}

        {/* Chat Messages */}
        {chatMessages.length > 0 && (
          <div className="gap-filler-chat">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`gap-filler-msg ${msg.role}`}>
                <span className="gap-filler-msg-role">{msg.role === 'user' ? 'You' : 'AI'}</span>
                <p>{msg.text.length > 200 ? msg.text.slice(0, 200) + '...' : msg.text}</p>
              </div>
            ))}
          </div>
        )}

        {/* Revision Input */}
        <div className="gap-filler-revise">
          <input
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Ask AI to revise... (e.g., 'make it more specific')"
            onKeyDown={e => e.key === 'Enter' && handleRevise()}
          />
          <button onClick={handleRevise} disabled={loading || !feedback.trim()}>
            {loading ? '...' : 'Revise'}
          </button>
        </div>

        {error && <div className="gap-filler-error">{error}</div>}
      </div>

      {/* Action Bar */}
      <div className="gap-filler-actions">
        <button className="btn-primary" onClick={handleApprove} disabled={loading || (!fieldValues.name && !fieldValues.description)}>
          Approve
        </button>
        <button className="btn-secondary" onClick={handleSaveEdit} disabled={loading}>
          Save Draft
        </button>
        {versions.length > 0 && (
          <button className="btn-secondary" onClick={() => setShowVersions(!showVersions)}>
            Versions ({versions.length})
          </button>
        )}
      </div>

      {/* Version History */}
      {showVersions && versions.length > 0 && (
        <div className="gap-filler-versions">
          <h4>Version History</h4>
          {versions.map((v: { version: number; text: string; author: string; timestamp: string }, i: number) => (
            <div key={i} className="gap-filler-version">
              <div className="gap-filler-version-header">
                <span>v{v.version} — {v.author}</span>
                <span className="gap-filler-version-time">{new Date(v.timestamp).toLocaleString()}</span>
                <button onClick={() => handleRevert(i)}>Restore</button>
              </div>
              <p className="gap-filler-version-text">{v.text.slice(0, 100)}...</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
