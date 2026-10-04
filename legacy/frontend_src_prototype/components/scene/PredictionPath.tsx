import React from 'react';
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
