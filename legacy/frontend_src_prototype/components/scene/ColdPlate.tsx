import React from 'react';

export function ColdPlate() {
  return (
    <mesh position={[0, 0.05, 0]}>
      <boxGeometry args={[0.2, 0.02, 0.2]} />
      <meshStandardMaterial color="#b87333" metalness={0.9} roughness={0.1} />
    </mesh>
  );
}
