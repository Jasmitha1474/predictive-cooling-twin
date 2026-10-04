import React from 'react';
import { DataCenterScene } from './components/scene/DataCenterScene';
import { StatusBar } from './components/hud/StatusBar';
import { ControlPanel } from './components/hud/ControlPanel';
import { EventStream } from './components/hud/EventStream';
import { ControlRoom } from './components/controlroom/ControlRoom';
import { useWebSocket } from './hooks/useWebSocket';

export default function App() {
  useWebSocket();

  return (
    <div className="w-screen h-screen">
      <StatusBar />
      <DataCenterScene />
      <EventStream />
      <ControlPanel />
      <ControlRoom />
    </div>
  );
}
