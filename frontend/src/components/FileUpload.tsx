import { useCallback, useState } from 'react';
import { api } from '../services/api';
import { useAppStore } from '../store/useAppStore';
import type { ParsedModel } from '../types';

function ModelSummaryCard({ model, label }: { model: ParsedModel; label: string }) {
  const s = model.summary;
  return (
    <div className="model-summary-card">
      <div className="card-label">{label}</div>
      <div className="card-filename">{model.filename}</div>
      <div className="card-type">{model.model_type.toUpperCase()}</div>
      <div className="card-stats">
        <div><strong>{s.package_count}</strong> packages</div>
        <div><strong>{s.element_count}</strong> elements</div>
        {s.part_defs > 0 && <div><strong>{s.part_defs}</strong> part defs</div>}
        {s.port_defs > 0 && <div><strong>{s.port_defs}</strong> port defs</div>}
        {s.interface_defs > 0 && <div><strong>{s.interface_defs}</strong> interfaces</div>}
        {s.requirement_defs > 0 && <div><strong>{s.requirement_defs}</strong> requirements</div>}
        {s.parts > 0 && <div><strong>{s.parts}</strong> parts</div>}
      </div>
    </div>
  );
}

function DropZone({
  label,
  onUpload,
}: {
  label: string;
  onUpload: (model: ParsedModel) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const setError = useAppStore((s) => s.setError);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      setUploading(true);
      setError(null);
      try {
        const model = await api.uploadModel(file);
        onUpload(model);
      } catch (e: any) {
        setError(e?.response?.data?.detail || e.message || 'Upload failed');
      } finally {
        setUploading(false);
      }
    },
    [onUpload, setError],
  );

  return (
    <div
      className={`drop-zone ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.sysml,.kerml,.reqif,.xml';
        input.onchange = () => handleFiles(input.files);
        input.click();
      }}
    >
      {uploading ? (
        <div className="spinner" />
      ) : (
        <>
          <div className="drop-icon">&#x1F4C1;</div>
          <div className="drop-label">{label}</div>
          <div className="drop-hint">.sysml, .reqif, .xml</div>
        </>
      )}
    </div>
  );
}

export function FileUpload() {
  const { modelA, modelB, setModelA, setModelB, setStep, setLoading, setError, setMergeAnalysis } =
    useAppStore();

  const handleAnalyze = async () => {
    if (!modelA || !modelB) return;
    setLoading(true);
    setError(null);
    try {
      const analysis = await api.analyzeMerge(modelA.model_id, modelB.model_id);
      setMergeAnalysis(analysis);
      setStep('merge');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-section">
      <h2>Upload Models to Merge</h2>
      <p className="subtitle">Select two SysML v2 or ReqIF files to compare and merge</p>

      <div className="upload-grid">
        <div className="upload-slot">
          {modelA ? (
            <ModelSummaryCard model={modelA} label="Model A" />
          ) : (
            <DropZone label="Drop Model A here" onUpload={setModelA} />
          )}
          {modelA && (
            <button className="btn-secondary" onClick={() => setModelA(null)}>
              Replace
            </button>
          )}
        </div>

        <div className="upload-divider">
          <span>+</span>
        </div>

        <div className="upload-slot">
          {modelB ? (
            <ModelSummaryCard model={modelB} label="Model B" />
          ) : (
            <DropZone label="Drop Model B here" onUpload={setModelB} />
          )}
          {modelB && (
            <button className="btn-secondary" onClick={() => setModelB(null)}>
              Replace
            </button>
          )}
        </div>
      </div>

      {modelA && modelB && (
        <button className="btn-primary analyze-btn" onClick={handleAnalyze}>
          Analyze &amp; Merge &#x2192;
        </button>
      )}
    </div>
  );
}
