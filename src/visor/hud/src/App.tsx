import { useState, useEffect } from 'react';
import { GraphCanvas } from './components/GraphCanvas';
import { TelemetryHUD } from './components/TelemetryHUD';
import { ErrorBoundary } from './components/ErrorBoundary';

function MainApp() {
  const initialMode = (window as any).INITIAL_VIEW_MODE || 'sidebar';
  const [viewMode, setViewMode] = useState<'sidebar' | 'panel'>(initialMode);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data.command === 'init') {
        if (event.data.viewType === 'sidebar' || event.data.viewType === 'panel') {
          setViewMode(event.data.viewType);
        }
      }
    };
    
    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    }
  }, []);

  return (
    <>
      {viewMode === 'panel' && (
        <GraphCanvas />
      )}
      <TelemetryHUD viewMode={viewMode} />
    </>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <MainApp />
    </ErrorBoundary>
  );
}
