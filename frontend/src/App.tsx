import { useAppStore } from './store/useAppStore';
import { Header } from './components/Header';
import { FileUpload } from './components/FileUpload';
import { MergeView } from './components/MergeView';
import { ValidationPanel } from './components/ValidationPanel';
import './App.css';

function App() {
  const { step, loading, error, setError } = useAppStore();

  return (
    <div className="app">
      <Header currentStep={step} />

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

        {step === 'upload' && <FileUpload />}
        {step === 'merge' && <MergeView />}
        {(step === 'validate' || step === 'download') && <ValidationPanel />}
      </main>

      <footer className="footer">
        <span>ModelMerge v0.1 — SysML v2 + ReqIF Model Merge Tool</span>
      </footer>
    </div>
  );
}

export default App;
