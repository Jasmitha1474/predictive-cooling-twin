import React from 'react';
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
