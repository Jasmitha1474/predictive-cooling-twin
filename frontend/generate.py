import os
import json

base_dir = "/Users/apple/.gemini/antigravity/scratch/gpu-cooling-digital-twin/frontend"

files = {
    "package.json": """{
  "name": "gpu-cooling-digital-twin-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "@react-spring/three": "^9.7.3",
    "@react-three/drei": "^9.120.0",
    "@react-three/fiber": "^8.17.0",
    "@react-three/xr": "^6.2.0",
    "lucide-react": "^0.446.0",
    "maath": "^0.10.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.7",
    "three": "^0.170.0",
    "zustand": "^5.0.0-rc.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@types/three": "^0.170.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.2.2",
    "vite": "^5.4.8"
  }
}""",
    "vite.config.ts": """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});""",
    "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}""",
    "tsconfig.node.json": """{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}""",
    "tailwind.config.js": """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: '#0a0e17',
        cyan: '#00e5ff',
        blue: '#3b82f6',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [],
}""",
    "postcss.config.js": """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}""",
    "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GPU Cooling Digital Twin</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>""",
    "src/index.css": """@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background-color: #0a0e17;
  color: white;
  overflow: hidden;
  font-family: system-ui, -apple-system, sans-serif;
}
.holographic-panel {
  background: rgba(10, 14, 23, 0.8);
  border: 1px solid #00e5ff;
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.3);
  padding: 1rem;
  border-radius: 0.5rem;
  color: #00e5ff;
  font-family: 'JetBrains Mono', monospace;
  text-shadow: 0 0 5px rgba(0, 229, 255, 0.5);
  pointer-events: none;
}
""",
    "src/main.tsx": """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);""",
    "src/vite-env.d.ts": """/// <reference types="vite/client" />""",
    "src/types/telemetry.ts": """export interface NodeData {
  node_id: string;
  workload: string;
  gpu_utilization: number;
  gpu_power: number;
  gpu_memory: number;
  gpu_clock: number;
  gpu_temperature: number;
  predicted_temperatures: number[];
  predicted_power: number[];
  prediction_horizons: number[];
}
export interface RackData {
  rack_id: string;
  nodes: NodeData[];
  coolant_temperature: number;
  coolant_flow_rate: number;
  valve_position: number;
  cooling_demand: number;
}
export interface Alert {
  time: string;
  type: 'INFO'|'PREDICTION'|'CONTROL'|'WARNING';
  message: string;
}
export interface TelemetryFrame {
  timestamp: string;
  tick: number;
  simulation_speed: number;
  racks: RackData[];
  controller_mode: string;
  alerts: Alert[];
  energy: any;
  model_metrics: any;
}
export type CameraView = 'overview'|'rack'|'gpu'|'cooling'|'thermal'|'control-room';
""",
    "src/store/telemetryStore.ts": """import { create } from 'zustand';
import { TelemetryFrame, Alert, CameraView } from '../types/telemetry';

interface TelemetryState {
  connected: boolean;
  latestFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  selectedRack: string | null;
  selectedNode: string | null;
  currentView: CameraView;
  thermalViewEnabled: boolean;
  simulationRunning: boolean;
  controllerMode: 'reactive' | 'predictive';
  simulationSpeed: number;
  predictionHorizon: number;
  temperatureThreshold: number;
  coolingAggressiveness: 'low' | 'medium' | 'high';
  alerts: Alert[];
  comparisonData: { reactive: any, predictive: any } | null;
  setConnected: (connected: boolean) => void;
  addFrame: (frame: TelemetryFrame) => void;
  setSelectedRack: (id: string | null) => void;
  setSelectedNode: (id: string | null) => void;
  setCurrentView: (view: CameraView) => void;
  setThermalViewEnabled: (enabled: boolean) => void;
  setSimulationRunning: (running: boolean) => void;
  setControllerMode: (mode: 'reactive' | 'predictive') => void;
  setSimulationSpeed: (speed: number) => void;
  setPredictionHorizon: (horizon: number) => void;
  setTemperatureThreshold: (threshold: number) => void;
  setCoolingAggressiveness: (aggressiveness: 'low' | 'medium' | 'high') => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  connected: false,
  latestFrame: null,
  history: [],
  selectedRack: null,
  selectedNode: null,
  currentView: 'overview',
  thermalViewEnabled: false,
  simulationRunning: false,
  controllerMode: 'reactive',
  simulationSpeed: 1,
  predictionHorizon: 30,
  temperatureThreshold: 80,
  coolingAggressiveness: 'medium',
  alerts: [],
  comparisonData: null,
  setConnected: (connected) => set({ connected }),
  addFrame: (frame) => set((state) => {
    const newHistory = [...state.history, frame].slice(-120);
    const newAlerts = [...state.alerts, ...frame.alerts].slice(-100);
    return { latestFrame: frame, history: newHistory, alerts: newAlerts };
  }),
  setSelectedRack: (id) => set({ selectedRack: id }),
  setSelectedNode: (id) => set({ selectedNode: id }),
  setCurrentView: (view) => set({ currentView: view }),
  setThermalViewEnabled: (enabled) => set({ thermalViewEnabled: enabled }),
  setSimulationRunning: (running) => set({ simulationRunning: running }),
  setControllerMode: (mode) => set({ controllerMode: mode }),
  setSimulationSpeed: (speed) => set({ simulationSpeed: speed }),
  setPredictionHorizon: (horizon) => set({ predictionHorizon: horizon }),
  setTemperatureThreshold: (threshold) => set({ temperatureThreshold: threshold }),
  setCoolingAggressiveness: (agg) => set({ coolingAggressiveness: agg }),
}));
""",
    "src/hooks/useWebSocket.ts": """import { useEffect, useRef } from 'react';
import { useTelemetryStore } from '../store/telemetryStore';
import { TelemetryFrame } from '../types/telemetry';

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const { setConnected, addFrame } = useTelemetryStore();

  useEffect(() => {
    let reconnectTimeout: any;
    let delay = 1000;

    const connect = () => {
      ws.current = new WebSocket('ws://localhost:8000/ws/telemetry');
      ws.current.onopen = () => {
        setConnected(true);
        delay = 1000;
      };
      ws.current.onmessage = (event) => {
        try {
          const data: TelemetryFrame = JSON.parse(event.data);
          addFrame(data);
        } catch (e) {
          console.error('Failed to parse frame', e);
        }
      };
      ws.current.onclose = () => {
        setConnected(false);
        reconnectTimeout = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      ws.current.onerror = () => {
        ws.current?.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      ws.current?.close();
    };
  }, [setConnected, addFrame]);
}
""",
    "src/hooks/useSimulation.ts": """import { useTelemetryStore } from '../store/telemetryStore';

export function useSimulation() {
  const store = useTelemetryStore();

  const apiCall = async (endpoint: string, payload: any = {}) => {
    // In a real app this would hit the API
    console.log(`API Call to ${endpoint}`, payload);
  };

  return {
    start: () => { apiCall('/start'); store.setSimulationRunning(true); },
    stop: () => { apiCall('/stop'); store.setSimulationRunning(false); },
    reset: () => apiCall('/reset'),
    pause: () => { apiCall('/pause'); store.setSimulationRunning(false); },
    setWorkload: (type: string, rackId?: string, nodeId?: string, intensity?: string) => 
      apiCall('/workload', { type, rackId, nodeId, intensity }),
    setController: (mode: 'reactive' | 'predictive') => { apiCall('/controller', { mode }); store.setControllerMode(mode); },
    setSpeed: (multiplier: number) => { apiCall('/speed', { multiplier }); store.setSimulationSpeed(multiplier); },
    setSettings: (threshold: number, horizon: number, aggressiveness: string) => 
      apiCall('/settings', { threshold, horizon, aggressiveness }),
  };
}
""",
    "src/utils/colors.ts": """export function temperatureToColor(temp: number): [number, number, number] {
  if (temp < 65) return [0, 0, 1];
  if (temp < 75) return [0, 1, 0];
  if (temp < 80) return [1, 1, 0];
  if (temp < 85) return [1, 0.5, 0];
  return [1, 0, 0];
}

export function temperatureToHex(temp: number): string {
  const [r, g, b] = temperatureToColor(temp);
  return `#${Math.round(r * 255).toString(16).padStart(2, '0')}${Math.round(g * 255).toString(16).padStart(2, '0')}${Math.round(b * 255).toString(16).padStart(2, '0')}`;
}

export function flowRateToSpeed(flowRate: number, maxFlow: number): number {
  return (flowRate / maxFlow) * 2;
}
""",
    "src/utils/interpolation.ts": """export function lerp(start: number, end: number, factor: number): number {
  return start + (end - start) * factor;
}

export function damp(current: number, target: number, lambda: number, dt: number): number {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}
""",
    "src/components/scene/DataCenterScene.tsx": """import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { CameraController } from './CameraController';
import { DataCenterRoom } from './DataCenterRoom';
import { ServerRack } from './ServerRack';
import { CoolingUnit } from './CoolingUnit';
import { CoolantPipe } from './CoolantPipe';
import { ThermalOverlay } from './ThermalOverlay';
import { useTelemetryStore } from '../../store/telemetryStore';
import { EffectComposer, Bloom } from '@react-three/postprocessing';

export function DataCenterScene() {
  const { latestFrame, currentView } = useTelemetryStore();
  const racks = latestFrame?.racks || [];

  return (
    <Canvas
      style={{ background: '#0a0e17' }}
      camera={{ position: [0, 12, 18], fov: 50 }}
      dpr={[1, 2]}
    >
      <fog attach="fog" args={['#0a0e17', 10, 40]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 20, 10]} intensity={1.5} />
      
      <Suspense fallback={null}>
        <DataCenterRoom />
        
        {racks.map((rack, i) => (
          <ServerRack key={rack.rack_id} rackData={rack} position={[(i - racks.length / 2) * 2 + 1, 0, 0]} />
        ))}
        
        <CoolingUnit position={[-8, 0, -5]} />
        
        <ThermalOverlay />
        <CameraController />
        
        <EffectComposer>
          <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} height={300} />
        </EffectComposer>
      </Suspense>
    </Canvas>
  );
}
""",
    "src/components/scene/DataCenterRoom.tsx": """import React from 'react';
import { Grid } from '@react-three/drei';

export function DataCenterRoom() {
  return (
    <group>
      <Grid
        position={[0, -0.01, 0]}
        args={[20, 15]}
        cellSize={1}
        cellThickness={1}
        cellColor="#222"
        sectionSize={5}
        sectionThickness={1.5}
        sectionColor="#00e5ff"
        fadeDistance={30}
      />
      <mesh position={[0, 5, -7.5]} rotation={[0, 0, 0]}>
        <planeGeometry args={[20, 10]} />
        <meshStandardMaterial color="#111" />
      </mesh>
    </group>
  );
}
""",
    "src/components/scene/ServerRack.tsx": """import React, { useMemo } from 'react';
import { Text } from '@react-three/drei';
import { GpuNode } from './GpuNode';
import { RackData } from '../../types/telemetry';
import { useTelemetryStore } from '../../store/telemetryStore';
import { temperatureToColor } from '../../utils/colors';

interface Props {
  rackData: RackData;
  position: [number, number, number];
}

export function ServerRack({ rackData, position }: Props) {
  const { setSelectedRack, setCurrentView } = useTelemetryStore();

  const maxTemp = useMemo(() => {
    return Math.max(...rackData.nodes.map(n => n.gpu_temperature), 20);
  }, [rackData]);

  const color = temperatureToColor(maxTemp);

  const handleClick = (e: any) => {
    e.stopPropagation();
    setSelectedRack(rackData.rack_id);
    setCurrentView('rack');
  };

  return (
    <group position={position} onClick={handleClick}>
      <mesh position={[0, 1, 0]}>
        <boxGeometry args={[0.6, 2.0, 1.0]} />
        <meshStandardMaterial color="#1a1a2e" metalness={0.8} roughness={0.2} />
      </mesh>
      
      <Text position={[0, 2.1, 0.51]} fontSize={0.1} color="#00e5ff">
        {rackData.rack_id}
      </Text>

      {rackData.nodes.map((node, i) => (
        <GpuNode key={node.node_id} nodeData={node} position={[0, 0.2 + i * 0.4, 0]} />
      ))}
    </group>
  );
}
""",
    "src/components/scene/GpuNode.tsx": """import React from 'react';
import { NodeData } from '../../types/telemetry';
import { useTelemetryStore } from '../../store/telemetryStore';
import { temperatureToHex } from '../../utils/colors';
import { HolographicPanel } from './HolographicPanel';
import { PredictionPath } from './PredictionPath';

interface Props {
  nodeData: NodeData;
  position: [number, number, number];
}

export function GpuNode({ nodeData, position }: Props) {
  const { selectedNode, setSelectedNode, setCurrentView } = useTelemetryStore();
  const isSelected = selectedNode === nodeData.node_id;

  const hexColor = temperatureToHex(nodeData.gpu_temperature);

  const handleClick = (e: any) => {
    e.stopPropagation();
    setSelectedNode(nodeData.node_id);
    setCurrentView('gpu');
  };

  return (
    <group position={position} onClick={handleClick}>
      <mesh>
        <boxGeometry args={[0.5, 0.08, 0.9]} />
        <meshStandardMaterial color="#2a2a3a" />
      </mesh>
      
      <mesh position={[0.2, 0, 0.46]}>
        <sphereGeometry args={[0.02]} />
        <meshStandardMaterial color={hexColor} emissive={hexColor} emissiveIntensity={nodeData.gpu_temperature > 85 ? 2 : 1} />
      </mesh>

      {isSelected && (
        <>
          <HolographicPanel nodeData={nodeData} />
          <PredictionPath nodeData={nodeData} />
        </>
      )}
    </group>
  );
}
""",
    "src/components/scene/ColdPlate.tsx": """import React from 'react';

export function ColdPlate() {
  return (
    <mesh position={[0, 0.05, 0]}>
      <boxGeometry args={[0.2, 0.02, 0.2]} />
      <meshStandardMaterial color="#b87333" metalness={0.9} roughness={0.1} />
    </mesh>
  );
}
""",
    "src/components/scene/CoolantPipe.tsx": """import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export function CoolantPipe() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.time.value = state.clock.elapsedTime;
    }
  });

  return (
    <mesh>
      <tubeGeometry args={[new THREE.CatmullRomCurve3([
        new THREE.Vector3(-8, 0.5, -5),
        new THREE.Vector3(-8, 2.5, -5),
        new THREE.Vector3(0, 2.5, -5),
        new THREE.Vector3(0, 2.5, 0),
      ]), 64, 0.05, 8, false]} />
      <shaderMaterial
        ref={materialRef}
        uniforms={{
          time: { value: 0 },
          uSpeed: { value: 1.0 },
          color: { value: new THREE.Color(0x00e5ff) }
        }}
        vertexShader={`
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform float time;
          uniform float uSpeed;
          uniform vec3 color;
          varying vec2 vUv;
          void main() {
            float pulse = sin(vUv.x * 20.0 - time * 5.0 * uSpeed) * 0.5 + 0.5;
            gl_FragColor = vec4(color * (0.5 + pulse * 0.5), 0.8);
          }
        `}
        transparent
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}
""",
    "src/components/scene/CoolantParticles.tsx": """import React from 'react';

export function CoolantParticles() {
  return null; // Implemented inside CoolantPipe shader for performance
}
""",
    "src/components/scene/Valve.tsx": """import React from 'react';
import { Text } from '@react-three/drei';
import { useSpring, animated } from '@react-spring/three';

interface Props {
  position: [number, number, number];
  valvePosition: number;
}

export function Valve({ position, valvePosition }: Props) {
  const { rotation } = useSpring({
    rotation: [0, 0, (valvePosition / 100) * (Math.PI / 2)] as [number, number, number]
  });

  return (
    <group position={position}>
      <mesh>
        <cylinderGeometry args={[0.1, 0.1, 0.3, 16]} />
        <meshStandardMaterial color="#555" />
      </mesh>
      <animated.group rotation={rotation}>
        <mesh position={[0, 0.15, 0]} rotation={[Math.PI/2, 0, 0]}>
          <torusGeometry args={[0.08, 0.02, 16, 32]} />
          <meshStandardMaterial color={valvePosition > 50 ? "#00ff00" : "#00e5ff"} />
        </mesh>
      </animated.group>
      <Text position={[0, 0.3, 0]} fontSize={0.05} color="#fff">
        {`${Math.round(valvePosition)}%`}
      </Text>
    </group>
  );
}
""",
    "src/components/scene/CoolingUnit.tsx": """import React from 'react';
import { Text } from '@react-three/drei';

interface Props {
  position: [number, number, number];
}

export function CoolingUnit({ position }: Props) {
  return (
    <group position={position}>
      <mesh position={[0, 1, 0]}>
        <boxGeometry args={[2, 2, 1.5]} />
        <meshStandardMaterial color="#222" metalness={0.5} roughness={0.5} />
      </mesh>
      <Text position={[0, 2.1, 0]} fontSize={0.2} color="#00e5ff">
        CDU SYSTEM
      </Text>
    </group>
  );
}
""",
    "src/components/scene/ThermalOverlay.tsx": """import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ThermalOverlay() {
  const { thermalViewEnabled } = useTelemetryStore();
  
  if (!thermalViewEnabled) return null;

  return (
    <mesh position={[0, 5, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[20, 15]} />
      <meshBasicMaterial color="#ff0000" transparent opacity={0.1} />
    </mesh>
  );
}
""",
    "src/components/scene/HolographicPanel.tsx": """import React from 'react';
import { Html } from '@react-three/drei';
import { NodeData } from '../../types/telemetry';

interface Props {
  nodeData: NodeData;
}

export function HolographicPanel({ nodeData }: Props) {
  return (
    <Html position={[0.6, 0.2, 0]} center transform sprite>
      <div className="holographic-panel w-48 text-xs">
        <div className="font-bold border-b border-cyan-500 pb-1 mb-1">{nodeData.node_id}</div>
        <div>Temp: {nodeData.gpu_temperature.toFixed(1)}°C</div>
        <div>Power: {nodeData.gpu_power.toFixed(0)}W</div>
        <div>Util: {nodeData.gpu_utilization.toFixed(0)}%</div>
        <div>Mem: {nodeData.gpu_memory.toFixed(0)}MB</div>
      </div>
    </Html>
  );
}
""",
    "src/components/scene/PredictionPath.tsx": """import React from 'react';
import { Line, Text } from '@react-three/drei';
import { NodeData } from '../../types/telemetry';
import * as THREE from 'three';

interface Props {
  nodeData: NodeData;
}

export function PredictionPath({ nodeData }: Props) {
  if (!nodeData.predicted_temperatures || nodeData.predicted_temperatures.length === 0) return null;

  const points = nodeData.predicted_temperatures.map((temp, i) => 
    new THREE.Vector3(0.6 + i * 0.2, (temp - 60) * 0.05, 0.2)
  );

  return (
    <group>
      <Line points={points} color="#ff00ff" lineWidth={2} />
      {points.map((p, i) => (
        <group key={i} position={p}>
          <mesh>
            <sphereGeometry args={[0.01]} />
            <meshBasicMaterial color="#ff00ff" />
          </mesh>
        </group>
      ))}
    </group>
  );
}
""",
    "src/components/scene/CameraController.tsx": """import React, { useEffect, useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { CameraControls } from '@react-three/drei';
import { useTelemetryStore } from '../../store/telemetryStore';
import * as THREE from 'three';

export function CameraController() {
  const { currentView } = useTelemetryStore();
  const controlsRef = useRef<CameraControls>(null);

  useEffect(() => {
    if (!controlsRef.current) return;
    const controls = controlsRef.current;

    switch (currentView) {
      case 'overview':
        controls.setLookAt(0, 12, 18, 0, 0, 0, true);
        break;
      case 'rack':
        controls.setLookAt(0, 5, 5, 0, 1, 0, true);
        break;
      case 'gpu':
        controls.setLookAt(0, 1, 2, 0, 1, 0, true);
        break;
      case 'cooling':
        controls.setLookAt(-8, 8, 15, -8, 1, -5, true);
        break;
      case 'thermal':
        controls.setLookAt(0, 15, 12, 0, 0, 0, true);
        break;
      case 'control-room':
        controls.setLookAt(15, 5, 0, 15, 5, -10, true);
        break;
    }
  }, [currentView]);

  return <CameraControls ref={controlsRef} />;
}
""",
    "src/components/hud/StatusBar.tsx": """import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function StatusBar() {
  const { connected, latestFrame, controllerMode } = useTelemetryStore();

  return (
    <div className="fixed top-0 left-0 right-0 p-2 flex justify-between bg-dark/80 text-cyan border-b border-cyan/30 z-50 font-mono text-xs">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span>{connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
        </div>
        <div>MODE: {controllerMode.toUpperCase()}</div>
      </div>
      {latestFrame && (
        <div className="flex gap-4">
          <div>TICK: {latestFrame.tick}</div>
          <div>SPEED: {latestFrame.simulation_speed}x</div>
        </div>
      )}
    </div>
  );
}
""",
    "src/components/hud/ControlPanel.tsx": """import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ControlPanel() {
  const { currentView, setCurrentView, thermalViewEnabled, setThermalViewEnabled } = useTelemetryStore();

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex gap-2 p-2 bg-dark/80 border border-cyan/50 rounded-full z-50">
      <button onClick={() => setCurrentView('overview')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'overview' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>OVERVIEW</button>
      <button onClick={() => setCurrentView('cooling')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'cooling' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>COOLING</button>
      <button onClick={() => setThermalViewEnabled(!thermalViewEnabled)} className={`px-4 py-2 rounded-full text-xs font-mono ${thermalViewEnabled ? 'bg-red-500 text-white' : 'text-cyan hover:bg-cyan/20'}`}>THERMAL</button>
      <button onClick={() => setCurrentView('control-room')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'control-room' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>DASHBOARD</button>
    </div>
  );
}
""",
    "src/components/hud/WorkloadSelector.tsx": """import React from 'react';

export function WorkloadSelector() {
  return null; // Simplified for now
}
""",
    "src/components/hud/EventStream.tsx": """import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function EventStream() {
  const { alerts } = useTelemetryStore();

  return (
    <div className="fixed bottom-4 left-4 w-64 h-48 bg-dark/80 border border-cyan/30 rounded flex flex-col font-mono text-[10px] overflow-hidden z-40">
      <div className="bg-cyan/20 p-1 border-b border-cyan/30 text-cyan font-bold">EVENT STREAM</div>
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
        {alerts.slice(-15).map((alert, i) => (
          <div key={i} className={`
            ${alert.type === 'INFO' ? 'text-blue-400' : ''}
            ${alert.type === 'PREDICTION' ? 'text-purple-400' : ''}
            ${alert.type === 'CONTROL' ? 'text-green-400' : ''}
            ${alert.type === 'WARNING' ? 'text-orange-400' : ''}
          `}>
            <span className="opacity-50">[{alert.time.split('T')[1]?.substring(0,8)}]</span> {alert.message}
          </div>
        ))}
      </div>
    </div>
  );
}
""",
    "src/components/hud/SettingsPanel.tsx": """import React from 'react';

export function SettingsPanel() {
  return null; // Simplified for now
}
""",
    "src/components/controlroom/ControlRoom.tsx": """import React from 'react';
import { AnalyticsCharts } from './AnalyticsCharts';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ControlRoom() {
  const { currentView } = useTelemetryStore();
  
  if (currentView !== 'control-room') return null;

  return (
    <div className="fixed inset-0 pt-10 pb-20 px-8 bg-dark/95 z-40 overflow-y-auto font-sans">
      <h1 className="text-2xl text-cyan mb-6 font-mono">DASHBOARD</h1>
      <AnalyticsCharts />
    </div>
  );
}
""",
    "src/components/controlroom/AnalyticsCharts.tsx": """import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useTelemetryStore } from '../../store/telemetryStore';

export function AnalyticsCharts() {
  const { history } = useTelemetryStore();

  const data = history.map(frame => {
    let maxTemp = 0;
    let totalPower = 0;
    frame.racks.forEach(r => {
      r.nodes.forEach(n => {
        maxTemp = Math.max(maxTemp, n.gpu_temperature);
        totalPower += n.gpu_power;
      });
    });
    return {
      time: frame.tick,
      maxTemp,
      totalPower
    };
  });

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-dark border border-cyan/30 p-4 h-64">
        <h3 className="text-cyan mb-2">Max Temperature</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="time" stroke="#00e5ff" />
            <YAxis stroke="#00e5ff" domain={['auto', 'auto']} />
            <Tooltip contentStyle={{backgroundColor: '#0a0e17', borderColor: '#00e5ff'}} />
            <Line type="monotone" dataKey="maxTemp" stroke="#ff0000" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-dark border border-cyan/30 p-4 h-64">
        <h3 className="text-cyan mb-2">Total Power</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="time" stroke="#00e5ff" />
            <YAxis stroke="#00e5ff" domain={['auto', 'auto']} />
            <Tooltip contentStyle={{backgroundColor: '#0a0e17', borderColor: '#00e5ff'}} />
            <Line type="monotone" dataKey="totalPower" stroke="#00e5ff" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
""",
    "src/components/comparison/ComparisonView.tsx": """import React from 'react';

export function ComparisonView() {
  return null;
}
""",
    "src/App.tsx": """import React from 'react';
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
"""
}

for filepath, content in files.items():
    full_path = os.path.join(base_dir, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)

print("Files generated successfully.")
