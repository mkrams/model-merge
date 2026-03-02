import { useState } from 'react';
import { useAppStore } from './store/useAppStore';
import { Header } from './components/Header';
import { FileUpload } from './components/FileUpload';
import { MergeView } from './components/MergeView';
import { ValidationPanel } from './components/ValidationPanel';
import { ReqIFMappingView } from './components/ReqIFMappingView';
import { CoverageView } from './components/CoverageView';
import './App.css';

function App() {
  const { step, loading, error, setError } = useAppStore();
  const [activeTool, setActiveTool] = useState<string | null>(null);

  return (
    <div className="app">
      <Header
        currentStep={step}
        activeTool={activeTool}
        onToolChange={setActiveTool}
      />

      <main className="main">
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}

        {loading && (
          <div className="loading-overlay">
            <div className="spinner large" />
            <p>Processing...</p>
          </div>
        )}

        {/* Tool views */}
        {activeTool === 'reqif-mapping' && <ReqIFMappingView />}
        {activeTool === 'coverage' && <CoverageView />}

        {/* Main merge flow */}
        {!activeTool && step === 'upload' && <FileUpload />}
        {!activeTool && step === 'merge' && <MergeView />}
        {!activeTool && (step === 'validate' || step === 'download') && <ValidationPanel />}
      </main>

      <footer className="footer">
        <span>ModelMerge v0.1 — SysML v2 + ReqIF Model Merge Tool</span>
      </footer>
    </div>
  );
}

export default App;
