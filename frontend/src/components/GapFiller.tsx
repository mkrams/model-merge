import { useState } from 'react';
import { api } from '../services/api';
import type { SafetyItem, SafetyProject, ItemType, DraftResponse } from '../types/safety';

const TYPE_LABELS: Record<string, string> = {
  hazard: 'Hazard',
  hazardous_event: 'Hazardous Event',
  safety_goal: 'Safety Goal',
  fsr: 'Functional Safety Requirement',
  tsr: 'Technical Safety Requirement',
  verification: 'Verification Item',
};

// Fields per item type
const FIELDS_BY_TYPE: Record<ItemType, { key: string; label: string; type: 'input' | 'textarea'; attrKey?: string }[]> = {
  hazard: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description', type: 'textarea' },
  ],
  hazardous_event: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'operating_situation', label: 'Operating Situation', type: 'textarea', attrKey: 'operating_situation' },
  ],
  safety_goal: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description (shall statement)', type: 'textarea' },
    { key: 'safe_state', label: 'Safe State', type: 'textarea', attrKey: 'safe_state' },
  ],
  fsr: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description (shall statement)', type: 'textarea' },
    { key: 'testable_criterion', label: 'Testable Criterion', type: 'textarea', attrKey: 'testable_criterion' },
  ],
  tsr: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Description (shall statement)', type: 'textarea' },
    { key: 'testable_criterion', label: 'Testable Criterion', type: 'textarea', attrKey: 'testable_criterion' },
    { key: 'allocated_to', label: 'Allocated To (component)', type: 'input', attrKey: 'allocated_to' },
  ],
  verification: [
    { key: 'name', label: 'Name', type: 'input' },
    { key: 'description', label: 'Objective', type: 'textarea' },
    { key: 'method', label: 'Method', type: 'input', attrKey: 'method' },
    { key: 'steps', label: 'Steps', type: 'textarea', attrKey: 'steps' },
    { key: 'expected_result', label: 'Expected Result', type: 'textarea', attrKey: 'expected_result' },
    { key: 'pass_criteria', label: 'Pass Criteria', type: 'textarea', attrKey: 'pass_criteria' },
  ],
};

interface GapFillerProps {
  item: SafetyItem;
  project: SafetyProject;
  onClose: () => void;
  onUpdate: () => void;
  onShowASILWizard?: () => void;
}

export function GapFiller({ item, project, onClose, onUpdate, onShowASILWizard }: GapFillerProps) {
  const fields = FIELDS_BY_TYPE[item.item_type] || FIELDS_BY_TYPE.hazard;

  // Initialize field values from item (top-level props and attributes)
  const initFieldValues = (): Record<string, string> => {
    const vals: Record<string, string> = {};
    for (const f of fields) {
      if (f.key === 'name') {
        vals[f.key] = item.name || '';
      } else if (f.key === 'description') {
        vals[f.key] = item.description || '';
      } else if (f.attrKey) {
        vals[f.key] = item.attributes?.[f.attrKey] || '';
      } else {
        vals[f.key] = '';
      }
    }
    return vals;
  };

  const [fieldValues, setFieldValues] = useState<Record<string, string>>(initFieldValues);
  // AI overwrite toggles: which fields should AI overwrite (default: all empty fields)
  const [aiOverwrite, setAiOverwrite] = useState<Record<string, boolean>>(() => {
    const ow: Record<string, boolean> = {};
    for (const f of fields) {
      let fieldValue = '';
      if (f.key === 'name') fieldValue = item.name || '';
      else if (f.key === 'description') fieldValue = item.description || '';
      else if (f.attrKey) fieldValue = item.attributes?.[f.attrKey] || '';

      ow[f.key] = !fieldValue; // toggle ON for empty fields, OFF for filled
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
      const result = await api.draftItem(item.item_id);
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
      const result = await api.reviseItem(item.item_id, feedback);
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
      await api.approveItem(item.item_id);
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
      const updateData: Record<string, string> = {
        name: fieldValues.name || '',
        description: fieldValues.description || '',
      };

      // Add attribute fields
      for (const f of fields) {
        if (f.attrKey) {
          updateData[f.attrKey] = fieldValues[f.key] || '';
        }
      }

      await api.updateItem(item.item_id, updateData);
      onUpdate();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRevert = async (idx: number) => {
    try {
      await api.revertItem(item.item_id, idx);
      onUpdate();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Revert failed');
    }
  };

  const versions = item.versions || [];

  // Find parent and child items from the graph
  const parents = project.items.filter(i =>
    project.links.some(l => l.source_id === i.item_id && l.target_id === item.item_id)
  );
  const children = project.items.filter(i =>
    project.links.some(l => l.source_id === item.item_id && l.target_id === i.item_id)
  );

  // Build context items
  const contextItems: { label: string; value: string; status: string }[] = [];

  // Add ASIL badge for hazardous_event items
  if (item.item_type === 'hazardous_event' && item.attributes?.asil_level) {
    contextItems.push({
      label: 'ASIL',
      value: item.attributes.asil_level,
      status: item.status,
    });
  }

  // Add parents and children
  for (const p of parents) {
    contextItems.push({
      label: TYPE_LABELS[p.item_type],
      value: p.name,
      status: p.status,
    });
  }
  for (const c of children) {
    contextItems.push({
      label: TYPE_LABELS[c.item_type],
      value: c.name,
      status: c.status,
    });
  }

  return (
    <div className="gap-filler-panel">
      <div className="gap-filler-header">
        <div>
          <h3>{TYPE_LABELS[item.item_type] || item.item_type}</h3>
          <span className={`gap-filler-status status-${item.status}`}>
            {item.status}
          </span>
        </div>
        <button className="gap-filler-close" onClick={onClose}>&times;</button>
      </div>

      {/* Context */}
      {contextItems.length > 0 && (
        <div className="gap-filler-context">
          <span className="gap-filler-context-label">Context:</span>
          {contextItems.map((ci, i) => (
            <span
              key={i}
              className={`gap-filler-context-item status-${ci.status}`}
              onClick={ci.label === 'ASIL' && onShowASILWizard ? onShowASILWizard : undefined}
              style={ci.label === 'ASIL' ? { cursor: 'pointer' } : {}}
            >
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
