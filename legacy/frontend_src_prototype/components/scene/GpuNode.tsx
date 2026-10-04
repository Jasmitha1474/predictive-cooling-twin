import React from 'react';
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
