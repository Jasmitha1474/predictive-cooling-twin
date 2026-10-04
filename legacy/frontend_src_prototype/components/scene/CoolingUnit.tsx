import React from 'react';
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
