import type { AppStep } from '../types';

const steps: { key: AppStep; label: string }[] = [
  { key: 'upload', label: '1. Upload' },
  { key: 'merge', label: '2. Merge' },
  { key: 'validate', label: '3. Validate' },
  { key: 'download', label: '4. Download' },
];

export function Header({ currentStep }: { currentStep: AppStep }) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="logo">
          <span className="logo-icon">&#x2B21;</span> ModelMerge
        </h1>
        <span className="tagline">Engineering Model Merge Tool</span>
      </div>
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
    </header>
  );
}
