import type { AppStep } from '../types';

const steps: { key: AppStep; label: string }[] = [
  { key: 'upload', label: '1. Upload' },
  { key: 'merge', label: '2. Merge' },
  { key: 'validate', label: '3. Validate' },
  { key: 'download', label: '4. Download' },
];

interface HeaderProps {
  currentStep: AppStep;
  activeTool?: string | null;
  onToolChange?: (tool: string | null) => void;
}

export function Header({ currentStep, activeTool, onToolChange }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <h1
          className="logo"
          style={{ cursor: 'pointer' }}
          onClick={() => onToolChange?.(null)}
        >
          <span className="logo-icon">&#x2B21;</span> ModelMerge
        </h1>
        <span className="tagline">Engineering Model Merge Tool</span>
      </div>

      <div className="header-right">
        {/* Tools nav */}
        <div className="tools-nav">
          <button
            className={`tool-btn ${!activeTool ? 'active' : ''}`}
            onClick={() => onToolChange?.(null)}
          >
            Merge
          </button>
          <button
            className={`tool-btn ${activeTool === 'reqif-mapping' ? 'active' : ''}`}
            onClick={() => onToolChange?.('reqif-mapping')}
          >
            ReqIF Mapping
          </button>
          <button
            className={`tool-btn ${activeTool === 'asil-assistant' ? 'active' : ''}`}
            onClick={() => onToolChange?.('asil-assistant')}
          >
            ASIL Assistant
          </button>
        </div>

        {/* Step progress (only show when on merge flow) */}
        {!activeTool && (
          <nav className="steps">
            {steps.map((s, i) => (
              <div
                key={s.key}
                className={`step ${s.key === currentStep ? 'active' : ''} ${
                  steps.findIndex((x) => x.key === currentStep) > i ? 'done' : ''
                }`}
              >
                {s.label}
              </div>
            ))}
          </nav>
        )}
      </div>
    </header>
  );
}
