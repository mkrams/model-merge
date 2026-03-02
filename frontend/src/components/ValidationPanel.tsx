import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { api } from '../services/api';
import type { ConfigStatus } from '../services/api';
import { DiagramView } from './DiagramView';
import type { ValidationResponse } from '../types';

function ApiKeySetup({ onConfigured }: { onConfigured: () => void }) {
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.setApiKey(apiKey.trim());
      onConfigured();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to save API key');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="api-key-setup">
      <div className="api-key-header">
        <strong>AI Validation Setup</strong>
        <p className="api-key-desc">
          Enter your Anthropic API key to enable AI-powered SysML v2 validation.
          The key is stored in memory only — never persisted.
        </p>
      </div>
      <div className="api-key-input-row">
        <input
          type="password"
          placeholder="sk-ant-..."
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          className="api-key-input"
        />
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={!apiKey.trim() || saving}
        >
          {saving ? 'Saving...' : 'Enable AI Validation'}
        </button>
      </div>
      {error && <div className="api-key-error">{error}</div>}
      <div className="api-key-link">
        Get a key at <a href="https://console.anthropic.com" target="_blank" rel="noreferrer">console.anthropic.com</a>
      </div>
    </div>
  );
}

export function ValidationPanel() {
  const {
    mergedResult,
    mergeAnalysis,
    validation,
    setValidation,
    setStep,
    setError,
  } = useAppStore();

  const [showCode, setShowCode] = useState(false);
  const [validating, setValidating] = useState(false);
  const [config, setConfig] = useState<ConfigStatus | null>(null);

  useEffect(() => {
    api.getConfigStatus().then(setConfig).catch(() => {});
  }, []);

  if (!mergedResult || !mergeAnalysis) return null;

  const handleValidate = async () => {
    setValidating(true);
    setError(null);
    try {
      const result = await api.validateMerge(mergeAnalysis.merge_id);
      setValidation(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([mergedResult.sysml_text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = mergedResult.filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const needsSetup = config && config.validation_method === 'semantic_only';

  return (
    <div className="validation-panel">
      <div className="validation-header">
        <h2>Merged Model</h2>
        <div className="merged-stats">
          <span><strong>{mergedResult.summary.package_count}</strong> packages</span>
          <span><strong>{mergedResult.summary.element_count}</strong> elements</span>
          {config && (
            <span className={`validation-method ${config.validation_method}`}>
              Validator: {config.validation_method === 'ai' ? 'AI (Claude)' : config.validation_method === 'monticore' ? 'MontiCore' : 'Semantic only'}
            </span>
          )}
        </div>
      </div>

      {/* Diagram */}
      <div className="section">
        <h3>Model Diagram</h3>
        <DiagramView packages={mergedResult.packages} />
      </div>

      {/* Code view toggle */}
      <div className="section">
        <button className="btn-secondary" onClick={() => setShowCode(!showCode)}>
          {showCode ? 'Hide' : 'Show'} Generated SysML v2 Code
        </button>
        {showCode && (
          <pre className="code-view">{mergedResult.sysml_text}</pre>
        )}
      </div>

      {/* API Key Setup (if needed) */}
      {needsSetup && !validation && (
        <div className="section">
          <ApiKeySetup
            onConfigured={() => {
              api.getConfigStatus().then(setConfig).catch(() => {});
            }}
          />
        </div>
      )}

      {/* Validation */}
      <div className="section">
        <h3>Validation</h3>
        {!validation && !validating && (
          <button className="btn-primary" onClick={handleValidate}>
            {config?.validation_method === 'ai' ? 'Run AI Validation' : 'Run Validation'}
          </button>
        )}
        {validating && (
          <div className="validating-status">
            <div className="spinner" />
            <span>
              {config?.validation_method === 'ai'
                ? 'AI is analyzing your merged SysML v2 model...'
                : 'Running validation...'}
            </span>
          </div>
        )}
        {validation && <ValidationResults validation={validation} />}
        {validation && (
          <button
            className="btn-secondary"
            style={{ marginTop: 12 }}
            onClick={() => { setValidation(null); handleValidate(); }}
          >
            Re-run Validation
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="merge-actions">
        <button className="btn-secondary" onClick={() => setStep('merge')}>
          &#x2190; Back to Merge
        </button>
        <button className="btn-primary" onClick={handleDownload}>
          &#x2B07; Download Merged Model
        </button>
      </div>
    </div>
  );
}

function ValidationResults({ validation }: { validation: ValidationResponse }) {
  return (
    <div className="validation-results">
      <ValidationSection title="Semantic Check" result={validation.semantic} />
      <ValidationSection
        title={validation.compiler.source === 'ai_validator' ? 'AI Validation (Claude)' : 'Compiler Check'}
        result={validation.compiler}
      />
    </div>
  );
}

function ValidationSection({
  title,
  result,
}: {
  title: string;
  result: { is_valid: boolean; errors: string[]; warnings: string[]; source: string };
}) {
  const statusIcon = result.is_valid ? '&#x2705;' : '&#x274C;';
  const statusClass = result.is_valid ? 'valid' : 'invalid';

  return (
    <div className={`validation-section ${statusClass}`}>
      <div className="validation-title">
        <span dangerouslySetInnerHTML={{ __html: statusIcon }} />
        <strong>{title}</strong>
        {result.source === 'compiler_unavailable' && (
          <span className="source-badge">Not configured</span>
        )}
        {result.source === 'ai_validator' && (
          <span className="source-badge ai">AI-powered</span>
        )}
      </div>

      {result.errors.length > 0 && (
        <div className="error-list">
          {result.errors.map((err, i) => (
            <div key={i} className="error-item">&#x274C; {err}</div>
          ))}
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="warning-list">
          {result.warnings.map((warn, i) => (
            <div key={i} className="warning-item">&#x26A0; {warn}</div>
          ))}
        </div>
      )}

      {result.errors.length === 0 && result.warnings.length === 0 && (
        <div className="success-msg">All checks passed</div>
      )}
    </div>
  );
}
