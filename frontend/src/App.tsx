import { Overlay } from './components/Overlay';
import { ResultsPage } from './components/ResultsPage';
import { Scene } from './scene/Scene';
import { useTelemetrySocket } from './telemetry/connection';
import { useTelemetry } from './telemetry/store';

export default function App() {
  useTelemetrySocket();
  const showResults = useTelemetry((s) => s.showResults);
  return (
    <div className="h-screen w-screen">
      <Scene />
      <Overlay />
      {showResults && <ResultsPage />}
    </div>
  );
}
