import React, { useMemo } from 'react';
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
