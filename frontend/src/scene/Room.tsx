import { Grid } from '@react-three/drei';
import { CONTROL_ROOM_POS } from './layout';

/** Static hall: floor, walls, ceiling light strips. Nothing here is animated. */
export function Room() {
  return (
    <group>
      <mesh rotation-x={-Math.PI / 2} position={[0, -0.001, 0]} receiveShadow>
        <planeGeometry args={[40, 44]} />
        <meshStandardMaterial color="#0b111b" metalness={0.6} roughness={0.55} />
      </mesh>
      <Grid
        position={[0, 0.001, 0]}
        args={[40, 44]}
        cellSize={0.6}
        cellThickness={0.5}
        cellColor="#16324a"
        sectionSize={3}
        sectionThickness={1}
        sectionColor="#1d4a6e"
        fadeDistance={45}
        infiniteGrid={false}
      />
      {/* walls */}
      {[
        [0, 3, -22, 40, 6, 0.2],
        [0, 3, 22, 40, 6, 0.2],
        [-20, 3, 0, 0.2, 6, 44],
        [20, 3, 0, 0.2, 6, 44],
      ].map(([x, y, z, w, h, d], i) => (
        <mesh key={i} position={[x, y, z]}>
          <boxGeometry args={[w, h, d]} />
          <meshStandardMaterial color="#0d1520" metalness={0.3} roughness={0.8} />
        </mesh>
      ))}
      {/* glass wall separating the control room */}
      <mesh position={[0, 2, CONTROL_ROOM_POS.z + 4]}>
        <boxGeometry args={[14, 4, 0.05]} />
        <meshPhysicalMaterial color="#5fb8ff" transparent opacity={0.08} roughness={0.05} metalness={0} />
      </mesh>
    </group>
  );
}
