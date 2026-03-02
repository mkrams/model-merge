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

  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [editName, setEditName] = useState(item?.name || '');
  const [editText, setEditText] = useState(item?.description || '');
  const [editSteps, setEditSteps] = useState(item?.steps || '');
  const [editExpected, setEditExpected] = useState(item?.expected_result || '');
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showVersions, setShowVersions] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ role: string; text: string }[]>([]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.draftItem(chainId, level);
      setDraft(result);
      setEditName(result.name || editName);
      setEditText(result.text || '');
      if (result.steps) setEditSteps(result.steps);
      if (result.expected_result) setEditExpected(result.expected_result);
      setChatMessages(prev => [...prev, { role: 'assistant', text: result.text }]);
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
      setDraft(result);
      if (result.name) setEditName(result.name);
      setEditText(result.text || '');
      if (result.steps) setEditSteps(result.steps);
      if (result.expected_result) setEditExpected(result.expected_result);
      setChatMessages(prev => [...prev, { role: 'assistant', text: result.text }]);
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
      if (level === 'test_case') {
        extra.steps = editSteps;
        extra.expected_result = editExpected;
      }
      await api.approveItem(chainId, level, editName, editText, extra);
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
      const fields: Record<string, string> = { name: editName, description: editText };
      if (level === 'test_case') {
        fields.steps = editSteps;
        fields.expected_result = editExpected;
      }
      await api.editItem(chainId, level, fields);
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

      {/* Content Area */}
      <div className="gap-filler-body">
        {isGap && !draft && (
          <div className="gap-filler-empty">
            <p>This item is empty. Generate an AI suggestion or fill it manually.</p>
            <button className="btn-primary" onClick={handleGenerate} disabled={loading}>
              {loading ? 'Generating...' : 'Generate AI Suggestion'}
            </button>
          </div>
        )}

        {/* Edit fields */}
        {(!isGap || draft) && (
          <div className="gap-filler-form">
            <label>Name</label>
            <input
              value={editName}
              onChange={e => setEditName(e.target.value)}
              placeholder="Short name..."
            />
            <label>Description</label>
            <textarea
              value={editText}
              onChange={e => setEditText(e.target.value)}
              placeholder="Full text..."
              rows={5}
            />
            {level === 'test_case' && (
              <>
                <label>Test Steps</label>
                <textarea
                  value={editSteps}
                  onChange={e => setEditSteps(e.target.value)}
                  placeholder="1. Step one&#10;2. Step two..."
                  rows={4}
                />
                <label>Expected Result</label>
                <textarea
                  value={editExpected}
                  onChange={e => setEditExpected(e.target.value)}
                  placeholder="Expected outcome..."
                  rows={2}
                />
              </>
            )}
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
        {(!isGap || draft) && (
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
            {isGap && (
              <button onClick={handleGenerate} disabled={loading} className="btn-secondary">
                Regenerate
              </button>
            )}
          </div>
        )}

        {error && <div className="gap-filler-error">{error}</div>}
      </div>

      {/* Action Bar */}
      <div className="gap-filler-actions">
        <button className="btn-primary" onClick={handleApprove} disabled={loading || (!editName && !editText)}>
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
          {versions.map((v, i) => (
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
